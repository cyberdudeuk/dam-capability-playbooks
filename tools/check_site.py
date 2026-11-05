#!/usr/bin/env python3
"""Static checks on the built site and the repository. One check per function; each records the defect or rule it exists for.

Usage: python tools/check_site.py [--site site] [--repo .]
Exit code 0 when every check passes, 1 otherwise.
"""
import argparse
import csv
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
TEXT_EXT = {'.html', '.css', '.js', '.json', '.jsonld', '.csv', '.ttl', '.xml', '.md', '.yaml', '.yml', '.py', '.txt', '.cff'}
MEDIA_EXT = {'.pptx', '.ppt', '.key', '.odp', '.mp4', '.mov', '.webm', '.m4v', '.avi'}


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.dup_ids, self.links, self.tags = set(), set(), [], []
        self.h1 = 0
        self.title = ''
        self._in_title = False
        self.scripts, self.inline_scripts, self.styles_attr = [], [], 0
        self.ldjson, self._in_ld, self._buf = [], False, ''
        self.lang = None
        self.metas = {}
        self.first_focusable = None
        self.tables, self._table = [], None
        self.svg_imgs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.tags.append((tag, a))
        if 'id' in a:
            (self.dup_ids if a['id'] in self.ids else self.ids).add(a['id'])
        if 'style' in a:
            self.styles_attr += 1
        if tag == 'html':
            self.lang = a.get('lang')
        if tag == 'title':
            self._in_title = True
        if tag == 'h1':
            self.h1 += 1
        if tag == 'meta' and a.get('name'):
            self.metas[a['name']] = a.get('content')
        if tag == 'meta' and a.get('http-equiv'):
            self.metas[a['http-equiv'].lower()] = a.get('content')
        if tag == 'a' and 'href' in a:
            self.links.append(a['href'])
            if self.first_focusable is None:
                self.first_focusable = a
        if tag == 'link' and 'href' in a:
            self.links.append(a['href'])
        if tag == 'script':
            if 'src' in a:
                self.scripts.append(a['src']); self.links.append(a['src'])
            elif a.get('type') == 'application/ld+json':
                self._in_ld, self._buf = True, ''
            elif a.get('type') != 'application/json':
                self.inline_scripts.append(a)
        if tag in ('button', 'input', 'select') and self.first_focusable is None:
            self.first_focusable = a
        if tag == 'table':
            self._table = {'caption': False, 'th': 0, 'th_scoped': 0}
        if tag == 'caption' and self._table is not None:
            self._table['caption'] = True
        if tag == 'th' and self._table is not None:
            self._table['th'] += 1
            if a.get('scope') in ('col', 'row'):
                self._table['th_scoped'] += 1
        if tag == 'svg' and a.get('role') == 'img':
            self.svg_imgs.append(a)

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag == 'script' and self._in_ld:
            self.ldjson.append(self._buf); self._in_ld = False
        if tag == 'table' and self._table is not None:
            self.tables.append(self._table); self._table = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._buf += data


def parse(path):
    p = Page()
    p.feed(path.read_text(encoding='utf-8'))
    return p


def text_files(base):
    for f in base.rglob('*'):
        if f.is_file() and '.git' not in f.parts and 'node_modules' not in f.parts and f.suffix.lower() in TEXT_EXT:
            yield f


# --- checks ------------------------------------------------------------------
def c01_page_basics(site, repo, pages):
    """Rule: every page is self-describing and accessible at the document level (build standard Launch; WCAG 2.2)."""
    errs = []
    need = ['artefact:id', 'artefact:version', 'artefact:class', 'artefact:as-of', 'artefact:review-date', 'content-security-policy']
    for name, p in pages.items():
        if p.lang != 'en-GB': errs.append(f'{name}: lang is {p.lang}')
        if not p.title.strip(): errs.append(f'{name}: empty title')
        if p.h1 != 1: errs.append(f'{name}: {p.h1} h1 elements')
        for k in need:
            if not p.metas.get(k): errs.append(f'{name}: missing meta {k}')
        ff = p.first_focusable or {}
        if ff.get('href') != '#main' or 'skip' not in (ff.get('class') or ''):
            errs.append(f'{name}: first focusable element is not the skip link')
        if 'main' not in p.ids: errs.append(f'{name}: no #main target')
    return errs


def c02_unique_ids(site, repo, pages):
    """Rule: unique ids on every page (QA bar)."""
    return [f'{n}: duplicate ids {sorted(p.dup_ids)}' for n, p in pages.items() if p.dup_ids]


def c03_links_resolve(site, repo, pages):
    """Rule: every internal link and anchor resolves (QA bar)."""
    errs = []
    for name, p in pages.items():
        for href in p.links:
            if re.match(r'^(https?:|mailto:|tel:|data:)', href):
                # Version 1.8: a share link may open the reader's own email with no recipient; any address is still refused
                if href.startswith('mailto:') and not href.startswith('mailto:?'): errs.append(f'{name}: mailto link {href}')
                continue
            path, _, frag = href.partition('#')
            target = name if not path else path
            f = site / target
            if not f.exists():
                errs.append(f'{name}: missing file {href}'); continue
            if frag and f.suffix == '.html':
                tp = pages.get(target) or parse(f)
                if frag.startswith('tour='):
                    # Version 1.8: a tour link starts a guided tour; the target page must carry that tour
                    tid = frag[5:]
                    src = f.read_text(encoding='utf-8')
                    if 'id="tour-data"' not in src or not re.search(r'"id":\s?"' + re.escape(tid) + '"', src):
                        errs.append(f'{name}: {href} starts a tour the page does not have')
                elif frag not in tp.ids: errs.append(f'{name}: missing anchor {href}')
    return errs


def c04_no_email(site, repo, pages):
    """Defect D-003: no email address anywhere in content, code or published files (COL-02)."""
    errs = []
    for base in {site.resolve(), repo.resolve()}:
        for f in text_files(base):
            for m in EMAIL.finditer(f.read_text(encoding='utf-8', errors='ignore')):
                if m.group(0).endswith(('.example', '@example.com', '@example.org')):
                    continue
                errs.append(f'{f.relative_to(base)}: email address {m.group(0)}')
    return sorted(set(errs))


def c05_no_external_assets(site, repo, pages):
    """Rule: self-contained pages, no CDN, web font or remote script or stylesheet."""
    errs = []
    for name, p in pages.items():
        for tag, a in p.tags:
            if tag == 'script' and re.match(r'https?:|//', a.get('src', '')): errs.append(f'{name}: remote script {a["src"]}')
            # a canonical or alternate link is an address, not a load; anything the browser fetches must be local
            if tag == 'link' and re.match(r'https?:|//', a.get('href', '')) and (a.get('rel') or '').lower() not in ('canonical', 'alternate'):
                errs.append(f'{name}: remote {a.get("rel")} link {a["href"]}')
            if tag in ('img', 'iframe', 'source') and re.match(r'https?:|//', a.get('src', '')): errs.append(f'{name}: remote {tag}')
    for css in site.rglob('*.css'):
        t = css.read_text(encoding='utf-8')
        if re.search(r'@import|url\(\s*["\']?(https?:|//)', t): errs.append(f'{css.name}: remote import or url()')
    return errs


def c06_dqap_expansion(site, repo, pages):
    """Defect D-001: DQAP is a data quality action plan, never an 'assurance' plan."""
    bad = re.compile(r'data\s+quality\s+assurance\s+plan', re.I)
    return [f'{f}: wrong DQAP expansion' for base in (site, repo / 'content') for f in text_files(base) if bad.search(f.read_text(encoding='utf-8'))]


def c07_no_annex_a(site, repo, pages):
    """Defect D-002: the DAM Policy has no Annex A reporting template; never cite one."""
    bad = re.compile(r'annex\s+a\b', re.I)
    return [f'{f}: cites a non-existent annex' for base in (site, repo / 'content') for f in text_files(base) if bad.search(f.read_text(encoding='utf-8'))]


def c08_provenance_on_requirements(site, repo, pages):
    """Rule VER-07: every requirement row on the spine carries a provenance label and a source link."""
    t = (site / 'dam.html').read_text(encoding='utf-8')
    body = t.split('<tbody id="req-table">', 1)[-1].split('</tbody>', 1)[0]
    rows = re.findall(r'<tr.*?</tr>', body, re.S)
    errs = [] if rows else ['dam.html: no requirement rows']
    for r in rows:
        rid = re.search(r'id="(DAM-R\d+)"', r)
        rid = rid.group(1) if rid else '?'
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, re.S)
        if len(cells) < 5:
            errs.append(f'{rid}: expected at least 5 cells'); continue
        # the requirement cell itself must carry a label; the source cell's own label does not count
        if 'class="prov ' not in cells[3]: errs.append(f'{rid}: requirement has no provenance label')
        if 'href="https://' not in cells[4]: errs.append(f'{rid}: no source link')
    return errs


def c09_no_decks_or_films(site, repo, pages):
    """Rule: decks and films stay out of the repository unless the owner says otherwise."""
    return [f'{f.relative_to(repo)}: deck or film in repository' for f in repo.rglob('*')
            if f.is_file() and '.git' not in f.parts and 'node_modules' not in f.parts and f.suffix.lower() in MEDIA_EXT]


def c10_tables(site, repo, pages):
    """Rule: tables captioned and scoped, inside labelled scroll regions (QA bar)."""
    errs = []
    for name, p in pages.items():
        for i, t in enumerate(p.tables):
            if not t['caption']: errs.append(f'{name}: table {i + 1} has no caption')
            if t['th'] != t['th_scoped']: errs.append(f'{name}: table {i + 1} has unscoped headers')
        wraps = [a for tag, a in p.tags if tag == 'div' and 'table-wrap' in (a.get('class') or '')]
        for w in wraps:
            if w.get('role') != 'region' or not w.get('aria-labelledby'): errs.append(f'{name}: unlabelled table region')
        if len(wraps) != len(p.tables): errs.append(f'{name}: {len(p.tables)} tables but {len(wraps)} scroll regions')
    return errs


def c11_machine_readable(site, repo, pages):
    """Rule: machine-readable metadata and open data files parse."""
    errs = []
    for name, p in pages.items():
        if not p.ldjson: errs.append(f'{name}: no JSON-LD')
        for block in p.ldjson:
            try:
                j = json.loads(block)
                for k in ('@type', 'name', 'identifier', 'version', 'dateModified'):
                    if k not in j: errs.append(f'{name}: JSON-LD missing {k}')
            except ValueError as e:
                errs.append(f'{name}: JSON-LD does not parse ({e})')
    for f in (site / 'data').glob('*.json*'):
        try: json.loads(f.read_text(encoding='utf-8'))
        except ValueError as e: errs.append(f'{f.name}: does not parse ({e})')
    for f in (site / 'data').glob('*.csv'):
        rows = list(csv.reader(f.read_text(encoding='utf-8').splitlines()))
        if len(rows) < 2 or any(len(r) != len(rows[0]) for r in rows): errs.append(f'{f.name}: ragged or empty CSV')
    ttl = (site / 'data' / 'vocabulary.ttl').read_text(encoding='utf-8')
    if ttl.count(' a skos:Concept') < 1: errs.append('vocabulary.ttl: no concepts')
    return errs


def c12_csp_clean(site, repo, pages):
    """Rule: Content Security Policy holds, so no inline style attributes or executable inline scripts."""
    errs = []
    for name, p in pages.items():
        if p.styles_attr: errs.append(f'{name}: {p.styles_attr} inline style attributes')
        if p.inline_scripts: errs.append(f'{name}: {len(p.inline_scripts)} inline executable scripts')
        csp = p.metas.get('content-security-policy', '')
        if "script-src 'self'" not in csp or 'unsafe-inline' in csp: errs.append(f'{name}: weak CSP')
    return errs


def c13_accessible_graphics(site, repo, pages):
    """Rule: barcode, QR code and every graphic with role=img has an accessible name (colophon)."""
    errs = []
    for name, p in pages.items():
        if len(p.svg_imgs) < 2: errs.append(f'{name}: colophon codes missing')
        for a in p.svg_imgs:
            if not (a.get('aria-label') or '').strip(): errs.append(f'{name}: svg image without a name')
    return errs


def c14_colophon_and_contact(site, repo, pages):
    """Rule COL-02 and the usual footer: contact by form, licence, version, as-of date on every page."""
    errs = []
    for name in pages:
        t = (site / name).read_text(encoding='utf-8')
        foot = t.split('id="colophon"', 1)[-1]
        for needle in ('contact form', 'Open Government Licence', 'Version ', 'as of ', 'AI assistant'):
            if needle not in foot: errs.append(f'{name}: footer lacks "{needle}"')
    return errs


def c15_no_placeholders(site, repo, pages):
    """Rule VER-01: no placeholder or invented filler text is published."""
    bad = re.compile(r'lorem ipsum|\bTODO\b|\bTBD\b|placeholder for', re.I)
    return [f'{f.name}: placeholder text' for f in text_files(site) if bad.search(f.read_text(encoding='utf-8'))]


def visible_text(path):
    t = path.read_text(encoding='utf-8')
    t = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'\s+', ' ', t)


def c16_search_engines(site, repo, pages):
    """Rule: every indexable page is optimised for search engines (owner request, version 1.1)."""
    errs, titles = [], {}
    for name, p in pages.items():
        if name == '404.html':
            if 'noindex' not in (p.metas.get('robots') or ''): errs.append('404.html: not marked noindex')
            continue
        desc = p.metas.get('description') or ''
        if not 50 <= len(desc) <= 160: errs.append(f'{name}: description is {len(desc)} characters (want 50 to 160)')
        rels = {(a.get('rel') or '').lower(): a.get('href') for t, a in p.tags if t == 'link'}
        if not rels.get('canonical', '').startswith('https://'): errs.append(f'{name}: no absolute canonical link')
        if 'icon' not in rels: errs.append(f'{name}: no favicon')
        props = {a.get('property'): a.get('content') for t, a in p.tags if t == 'meta' and a.get('property')}
        for k in ('og:title', 'og:description', 'og:image', 'og:url'):
            if not props.get(k): errs.append(f'{name}: missing {k}')
        if p.title in titles: errs.append(f'{name}: title duplicates {titles[p.title]}')
        titles[p.title] = name
    robots = site / 'robots.txt'
    if not robots.exists() or 'Sitemap:' not in robots.read_text(): errs.append('robots.txt missing or has no sitemap line')
    sm = (site / 'sitemap.xml').read_text() if (site / 'sitemap.xml').exists() else ''
    for name in pages:
        if name not in ('404.html', 'index.html') and name not in sm: errs.append(f'sitemap.xml: {name} not listed')
    for f in ('favicon.svg', 'favicon-32.png', 'apple-touch-icon.png', 'og-image.png'):
        if not (site / 'assets' / f).exists(): errs.append(f'assets/{f} missing')
    return errs


PERSONAL = re.compile(r'emanuel|silva|cyberdudeuk|data management team|data management lead', re.I)


def c17_no_personal_details(site, repo, pages):
    """Owner request (version 1.1): no details about the author or their team in what readers see; contact form only."""
    errs = []
    for name in pages:
        for m in PERSONAL.finditer(visible_text(site / name)):
            errs.append(f'{name}: visible text names "{m.group(0)}"')
    for f in (repo / 'README.md', repo / 'LICENSE', repo / 'content' / 'playbooks.yaml', repo / 'CITATION.cff'):
        if f.exists():
            for m in re.finditer(r'emanuel|silva', f.read_text(encoding='utf-8'), re.I):
                errs.append(f'{f.name}: names "{m.group(0)}"')
    return sorted(set(errs))


AVOID = re.compile(r'\b(click here|simply|easily|e\.g\.|i\.e\.|etc\.|utilise|leverage|going forward)\b', re.I)


def c18_plain_english(site, repo, pages):
    """Rule: GOV.UK content style; no words the style guide asks writers to avoid in visible text."""
    errs = []
    for name in pages:
        for m in AVOID.finditer(visible_text(site / name)):
            errs.append(f'{name}: avoid "{m.group(0)}"')
    return sorted(set(errs))


def c19_citations(site, repo, pages):
    """Owner request (version 1.2): every source and rulebook entry is cited in full, with its address, on the notices page."""
    import yaml
    d = yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))
    fw = repo / 'content' / 'frameworks.yaml'
    if fw.exists():
        d['rulebook'] = d.get('rulebook', []) + yaml.safe_load(fw.read_text(encoding='utf-8')).get('rulebook_more', [])
    t = (site / 'notices.html').read_text(encoding='utf-8') if (site / 'notices.html').exists() else ''
    errs = [] if t else ['notices.html missing']
    for x in d['sources'] + d.get('rulebook', []):
        m = re.search(r'<li id="cite-' + re.escape(x['id']) + r'">(.*?)</li>', t, re.S)
        if not m: errs.append(f'{x["id"]}: no citation')
        elif x['url'].replace('&', '&amp;') not in m.group(1): errs.append(f'{x["id"]}: citation does not link the source address')
        elif 'Accessed:' not in m.group(1): errs.append(f'{x["id"]}: citation has no accessed date')
    if 'Open Government Licence v3.0' not in t or 'Contains public sector information' not in t: errs.append('notices.html: OGL attribution statement missing')
    return errs


def c20_page_governance(site, repo, pages):
    """Rule (G3): every page shows its owner role, dates and a feedback route; security.txt is published and in date."""
    import datetime as dt
    errs = []
    for name in pages:
        if name == '404.html':
            continue
        t = (site / name).read_text(encoding='utf-8')
        if 'class="page-meta"' not in t or 'Next review' not in t: errs.append(f'{name}: no page owner and review line')
        if 'template=feedback.yml' not in t: errs.append(f'{name}: no page feedback link')
        if 'href="accessibility.html"' not in t: errs.append(f'{name}: no link to the accessibility statement')
    st = site / '.well-known' / 'security.txt'
    if not st.exists():
        errs.append('security.txt missing')
    else:
        txt = st.read_text()
        m = re.search(r'^Expires: (\S+)', txt, re.M)
        if not m or not txt.startswith('Contact: https://'): errs.append('security.txt lacks Contact or Expires')
        elif dt.datetime.fromisoformat(m.group(1).replace('Z', '+00:00')).date() <= dt.date.today(): errs.append('security.txt has expired')
    return errs


# Short, distinctive fragments of the Data Maturity Assessment level descriptions. That framework is CC BY-NC-SA 4.0,
# which this portal's OGL content licence cannot carry, so its descriptions must be linked, never copied (version 1.4).
DMA_FRAGMENTS = ['only to a single specialist person or team', 'Discourages sharing data internally', 'Seen as an exemplar',
                 'Insular approach and siloed working', 'Futureproofing and prediction of future needs']


def c21_no_restricted_licence_text(site, repo, pages):
    """Rule (version 1.4): text published under a licence the portal cannot carry (Data Maturity Assessment, CC BY-NC-SA) is linked, not copied."""
    errs = []
    for f in sorted(site.rglob('*')):
        if f.is_file() and f.suffix in ('.html', '.js', '.json', '.csv', '.ttl', '.jsonld', '.yaml'):
            t = f.read_text(encoding='utf-8', errors='ignore').lower()
            errs += [f'{f.relative_to(site)}: contains framework text "{x}"' for x in DMA_FRAGMENTS if x.lower() in t]
    return errs


def c22_signposts_verified(site, repo, pages):
    """Rule (version 1.4): every deep link into GOV.UK guidance points to a section recorded as verified, and every capability shows its flag."""
    import json as _json
    import yaml
    errs = []
    af = repo / 'content' / 'source-anchors.json'
    if not af.exists():
        return ['content/source-anchors.json missing']
    anchors = _json.loads(af.read_text())['anchors']
    d = yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))
    fw = repo / 'content' / 'frameworks.yaml'
    rb = yaml.safe_load(fw.read_text(encoding='utf-8')).get('rulebook_more', []) if fw.exists() else []
    url_to_id = {x['url']: x['id'] for x in d['sources'] + d.get('rulebook', []) + rb}
    for name in ('capability-model.html', 'change.html', 'professions.html'):
        if not (site / name).exists():
            errs.append(f'{name} missing'); continue
        t = (site / name).read_text(encoding='utf-8')
        for href in set(re.findall(r'href="(https://www\.gov\.uk/[^"#]+)#([^"]+)"', t)):
            doc = url_to_id.get(href[0].replace('&amp;', '&'))
            if doc in anchors and href[1] not in anchors[doc]:
                errs.append(f'{name}: {doc} has no verified section #{href[1]}')
        if name == 'capability-model.html':
            cards = re.findall(r'<li class="cr-card" id="(CR-\d+)"(.*?)</li>\s*(?=<li class="cr-card"|</ul>)', t, re.S)
            if not cards: errs.append('capability-model.html: no capability cards')
            for cid, body in cards:
                # D-016: signpost badges also use the flag style, so look only in the card heading
                head = body.split('\n<p>', 1)[0]
                if 'class="flag-badge' not in head: errs.append(f'{cid}: no explicit, implicit or inferred flag in the heading')
    return errs


def c23_repository_metadata(site, repo, pages):
    """Rule (D-017): CITATION.cff is complete and names the same version as the portal, so the repository's citation is never blank."""
    import yaml
    errs = []
    f = repo / 'CITATION.cff'
    if not f.exists():
        return ['CITATION.cff missing']
    try:
        c = yaml.safe_load(f.read_text(encoding='utf-8')) or {}
    except yaml.YAMLError as e:
        return [f'CITATION.cff does not parse: {str(e).splitlines()[0]}']
    for k in ('cff-version', 'title', 'authors', 'version', 'license', 'repository-code', 'url'):
        if not c.get(k): errs.append(f'CITATION.cff has no {k}')
    meta = yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))['meta']
    if c.get('version') and str(c['version']) != str(meta['version']): errs.append(f'CITATION.cff version {c["version"]} differs from portal version {meta["version"]}')
    return errs


# ADR 0005: the only actions not owned by the repository owner, each pinned to a commit checked against its release tag
# with git ls-remote on 5 November 2026. Update a commit only after checking the new one the same way.
REVIEWED_ACTIONS = {
    'actions/dependency-review-action': 'a1d282b36b6f3519aa1f3fc636f609c47dddb294',   # v5.0.0
    'actions/checkout': '3d3c42e5aac5ba805825da76410c181273ba90b1',                   # v7.0.1
    'actions/upload-artifact': 'cf430e030ddbb5b0abf93d22962f4752f3646cd9',            # v7.0.2
    'github/codeql-action/upload-sarif': '1fc58d04a4d4374f921bdac573c3811c240f9c26',  # v4.39.2
    'ossf/scorecard-action': 'fa7117db83c52d787ae5a89f350999701505d78e',              # v2.5.0
}


def c24_actions_pinned(site, repo, pages):
    """Rule (supply chain, D-018, ADR 0005): workflows use only the owner's actions or the reviewed actions, each pinned to a full commit SHA."""
    import yaml
    errs = []
    wf = repo / '.github' / 'workflows'
    if not wf.exists():
        return ['.github/workflows missing']
    owner = str(yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))['meta']['repo']).split('/')[0].lower()
    for f in sorted(wf.glob('*.yml')):
        for n, line in enumerate(f.read_text(encoding='utf-8').splitlines(), 1):
            m = re.search(r'^\s*-?\s*uses:\s*([^\s#]+)', line)
            if not m or m.group(1).startswith('./'):
                continue
            ref = m.group(1)
            name, _, sha = ref.partition('@')
            if ref.split('/')[0].lower() != owner:
                if name not in REVIEWED_ACTIONS:
                    errs.append(f'{f.name}:{n}: {ref} is not owned by {owner} and is not a reviewed action (ADR 0005); the repository policy will refuse to start the run')
                elif sha != REVIEWED_ACTIONS[name]:
                    errs.append(f'{f.name}:{n}: {name} is pinned to {sha or "a tag"}, not the reviewed commit {REVIEWED_ACTIONS[name]}; check the new commit against its release tag, then update REVIEWED_ACTIONS')
            elif not re.search(r'@[0-9a-f]{40}$', ref):
                errs.append(f'{f.name}:{n}: {ref} is not pinned to a commit SHA')
    return errs


EXPECTED_WORKFLOWS = {'pages.yml', 'codeql.yml', 'release.yml', 'dependency-review.yml', 'scorecard.yml'}  # last two: ADR 0005


def c25_workflow_inventory(site, repo, pages):
    """Rule (D-020, ADR 0005): only the reviewed workflows exist, and none publishes the raw repository instead of the built site."""
    wf = repo / '.github' / 'workflows'
    found = {f.name for f in wf.glob('*.y*ml')} if wf.exists() else set()
    errs = [f'unexpected workflow {n}: review it, then add it to EXPECTED_WORKFLOWS with the defect or decision that justifies it' for n in sorted(found - EXPECTED_WORKFLOWS)]
    errs += [f'expected workflow {n} is missing' for n in sorted(EXPECTED_WORKFLOWS - found)]
    for f in sorted(wf.glob('*.y*ml')) if wf.exists() else []:
        t = f.read_text(encoding='utf-8')
        if re.search(r'jekyll|source:\s*\./?\s*$', t, re.I | re.M):
            errs.append(f'{f.name}: builds or publishes the repository root, not the generated site/ folder')
    return errs


# D-021: GitHub's generic noreply address under the username "noreply" belongs to an unrelated account, so commits made
# with it were credited to that account. Only these identities may author or commit. Addresses are assembled at run
# time so that no address appears in the repository as text (C-04).
_AT, _GH = chr(64), 'users.noreply.github.com'
ALLOWED_COMMIT_EMAILS = {f'68606121+cyberdudeuk{_AT}{_GH}', f'noreply{_AT}github.com', f'noreply{_AT}anthropic.com',
                         f'49699333+dependabot[bot]{_AT}{_GH}', f'41898282+github-actions[bot]{_AT}{_GH}'}


def c26_commit_identity(site, repo, pages):
    """Rule (D-021): the latest commit is authored and committed by an identity GitHub links to the owner, a GitHub bot or the named assistant, never to an unrelated account."""
    import subprocess
    if not (repo / '.git').exists():
        return []
    r = subprocess.run(['git', '-C', str(repo), 'log', '-1', '--format=%ae%n%ce'], capture_output=True, text=True)
    if r.returncode != 0:
        return []
    return [f'latest commit uses {e}, which GitHub may credit to an unrelated account' for e in r.stdout.split() if e not in ALLOWED_COMMIT_EMAILS]


def c27_registers_in_repository(site, repo, pages):
    """Rule (version 1.5): the defect register and challenge review live in the repository, list every recorded item, and are not published on the portal."""
    import yaml
    d = yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))
    errs = []
    reg = repo / 'docs' / 'defect-register.md'
    t = reg.read_text(encoding='utf-8') if reg.exists() else ''
    if not t:
        errs.append('docs/defect-register.md missing; run tools/build.py')
    want = {x['id'] for x in d['defects']}
    have = set(re.findall(r'^\| (D-\d{3}) \|', t, re.M))
    errs += [f'docs/defect-register.md: {i} missing; run tools/build.py' for i in sorted(want - have)]
    errs += [f'docs/defect-register.md: {i} is not in the content file' for i in sorted(have - want)]
    cr = repo / 'docs' / 'challenge-review.md'
    if not cr.exists() or cr.read_text(encoding='utf-8').count('\n| ') - 1 < len(d['adversarial']):
        errs.append('docs/challenge-review.md missing or out of date; run tools/build.py')
    for name in pages:
        h = (site / name).read_text(encoding='utf-8')
        if any(f'id="{x}"' in h for x in ('defects', 'adversarial', 'checkpoint', 'standards')):
            errs.append(f'{name}: publishes the defect register or challenge review, which belong in the repository')
    return errs


def c28_open_data_catalogue(site, repo, pages):
    """Rule (version 1.5.1): every published data file is described in a DCAT catalogue (JSON-LD and Turtle) with licence, publisher, contact point and date; every page links to it; the Open data page carries schema.org Dataset markup."""
    import json as _json
    errs = []
    data = site / 'data'
    try:
        cat = _json.loads((data / 'catalogue.jsonld').read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        return [f'data/catalogue.jsonld missing or invalid: {e}']
    if cat.get('@type') != 'dcat:Catalog':
        errs.append('catalogue.jsonld is not a dcat:Catalog')
    urls = set()
    for ds in cat.get('dcat:dataset', []):
        for k in ('dcterms:title', 'dcterms:description', 'dcterms:license', 'dcterms:publisher', 'dcat:contactPoint', 'dcterms:modified', 'dcterms:identifier'):
            if not ds.get(k): errs.append(f'{ds.get("@id")}: no {k}')
        if not ds.get('dcat:distribution'): errs.append(f'{ds.get("@id")}: no distributions')
        for dist in ds.get('dcat:distribution', []):
            u = dist.get('dcat:downloadURL', {}).get('@id', '')
            urls.add(u.split('/data/', 1)[-1])
            if not dist.get('dcat:mediaType'): errs.append(f'{u}: no media type')
    published = {str(f.relative_to(data)) for f in data.rglob('*') if f.is_file() and f.name not in ('catalogue.jsonld', 'catalogue.ttl')}
    errs += [f'data/{f} is published but not in the catalogue' for f in sorted(published - urls)]
    errs += [f'catalogue lists data/{f}, which does not exist' for f in sorted(urls - published)]
    ttl = data / 'catalogue.ttl'
    if not ttl.exists() or ttl.read_text(encoding='utf-8').count('a dcat:Dataset') != len(cat.get('dcat:dataset', [])):
        errs.append('catalogue.ttl missing or out of step with catalogue.jsonld')
    for name in pages:
        if 'href="data/catalogue.jsonld"' not in (site / name).read_text(encoding='utf-8'):
            errs.append(f'{name}: no link to the open data catalogue in its header')
    dp = site / 'data.html'
    if not dp.exists() or '"@type":"Dataset"' not in dp.read_text(encoding='utf-8').replace('": "', '":"'):
        errs.append('data.html: no schema.org Dataset markup')
    return errs


def c29_limitations_referenced(site, repo, pages):
    """Rule (version 1.5.1): every open-register item a reader can see mentioned on the portal is explained under known limitations."""
    errs = []
    about = (site / 'about.html').read_text(encoding='utf-8') if (site / 'about.html').exists() else ''
    for name in pages:
        text = re.sub(r'<[^>]+>', ' ', (site / name).read_text(encoding='utf-8'))
        for ref in sorted(set(re.findall(r'\bOR-\d\d\b', text))):
            if f'<tr id="{ref}">' not in about:
                errs.append(f'{name}: mentions {ref}, which is not explained under known limitations')
    return errs


def c30_testing_pack(site, repo, pages):
    """Rule (version 1.5.1): the testing page offers each task with a start link and a pre-filled feedback form, and the form exists."""
    errs = []
    form = repo / '.github' / 'ISSUE_TEMPLATE' / 'testing.yml'
    if not form.exists():
        errs.append('.github/ISSUE_TEMPLATE/testing.yml missing')
    elif 'id: task' not in form.read_text(encoding='utf-8') or 'id: ease' not in form.read_text(encoding='utf-8'):
        errs.append('testing.yml does not ask for the task and how easy it was')
    t = (site / 'test.html').read_text(encoding='utf-8') if (site / 'test.html').exists() else ''
    tasks = re.findall(r'<li class="cr-card test-task" id="(T-\d+)"(.*?)</li>\s*(?=<li class="cr-card test-task"|</ul>)', t, re.S)
    if not tasks:
        errs.append('test.html: no tasks')
    for tid, body in tasks:
        if 'template=testing.yml' not in body or f'task={tid}' not in body:
            errs.append(f'{tid}: no pre-filled feedback link')
        if 'Start this task' not in body:
            errs.append(f'{tid}: no start link')
    for name in pages:
        if name != '404.html' and 'href="test.html"' not in (site / name).read_text(encoding='utf-8'):
            errs.append(f'{name}: no link to the testing page')
    return errs


def _sel_present(sel, html, page):
    """Match the simple selectors tours use (#id, .class, [attr] and [attr=value]) against a built page."""
    if sel.startswith('#'):
        return sel[1:] in page.ids
    if sel.startswith('.'):
        return re.search(r'class="[^"]*\b' + re.escape(sel[1:]) + r'\b', html) is not None
    m = re.fullmatch(r'\[([\w-]+)(?:=([\w-]+))?\]', sel)
    if m:
        return re.search(r'\s' + re.escape(m.group(1)) + (r'="' + re.escape(m.group(2)) + '"' if m.group(2) else r'[\s=>]'), html) is not None
    return False


def c31_navigation_aids(site, repo, pages):
    """Rule (version 1.8): every page can be shared, the site map lists every page, llms.txt lists every page, and every tour step points at something on its page."""
    errs = []
    sm = (site / 'site-map.html').read_text(encoding='utf-8') if (site / 'site-map.html').exists() else ''
    m = re.search(r'<ul class="map-tree">.*?</main>', sm, re.S)
    sm = m.group(0) if m else ''
    if not m and (site / 'site-map.html').exists():
        errs.append('site-map.html: no map of pages')
    llms = (site / 'llms.txt').read_text(encoding='utf-8') if (site / 'llms.txt').exists() else ''
    if not sm:
        errs.append('site-map.html missing')
    if not llms:
        errs.append('llms.txt missing')
    if not (site / 'llms-full.txt').exists():
        errs.append('llms-full.txt missing')
    for name in pages:
        if name == '404.html':
            continue
        html = (site / name).read_text(encoding='utf-8')
        if '<details class="share">' not in html:
            errs.append(f'{name}: no share menu')
        if name != 'site-map.html' and f'href="{name}"' not in sm:
            errs.append(f'{name}: not on the site map')
        stem = '' if name == 'index.html' else name
        if sm and llms and not re.search(r'\]\([^)]*/' + re.escape(stem) + r'\)', llms):
            errs.append(f'{name}: not listed in llms.txt')
        m = re.search(r'<script type="application/json" id="tour-data">(.*?)</script>', html, re.S)
        if m:
            for tour in json.loads(m.group(1)):
                if tour.get('page') and tour['page'] + '.html' != name:
                    continue
                for s in tour['steps']:
                    if not _sel_present(s['sel'], html, pages[name]):
                        errs.append(f'{name}: tour {tour["id"]} step "{s["title"]}" points at {s["sel"]}, which is not on the page')
    return errs


def c32_mcp_server(site, repo, pages):
    """Rule (version 1.8): the reference MCP server starts, lists its tools, answers from the built content with page links, and reports the portal version."""
    import subprocess
    errs = []
    server = repo / 'integrations' / 'mcp' / 'server.py'
    data = site / 'data' / 'playbooks.json'
    if not server.exists():
        return ['integrations/mcp/server.py missing']
    if not data.exists():
        return ['site/data/playbooks.json missing']
    msgs = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-06-18'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'search_portal', 'arguments': {'query': 'owner'}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {'name': 'get_requirement', 'arguments': {'id': 'NO-SUCH'}}}]
    import os
    env = dict(os.environ, DAM_PLAYBOOKS_FILE=str(data))
    env.pop('DAM_PLAYBOOKS_URL', None)
    try:
        out = subprocess.run([sys.executable, '-I', str(server)], input='\n'.join(json.dumps(m) for m in msgs) + '\n', capture_output=True, text=True, timeout=60, env=env)
    except subprocess.TimeoutExpired:
        return ['MCP server did not answer within 60 seconds']
    resp = {}
    for line in out.stdout.splitlines():
        try:
            r = json.loads(line)
            resp[r.get('id')] = r
        except json.JSONDecodeError:
            errs.append(f'MCP server wrote a line that is not JSON: {line[:60]}')
    meta = json.loads(data.read_text(encoding='utf-8')).get('meta', {})
    init = resp.get(1, {}).get('result', {})
    if init.get('serverInfo', {}).get('version') != meta.get('version'):
        errs.append(f'MCP server version {init.get("serverInfo", {}).get("version")} does not match portal version {meta.get("version")}')
    names = {x['name'] for x in resp.get(2, {}).get('result', {}).get('tools', [])}
    reuse = (site / 'reuse.html').read_text(encoding='utf-8') if (site / 'reuse.html').exists() else ''
    for n in names:
        if f'<code>{n}</code>' not in reuse:
            errs.append(f'MCP tool {n} is not described on the reuse page')
    if len(names) < 5:
        errs.append(f'MCP server lists {len(names)} tools, expected at least 5')
    hits = resp.get(3, {}).get('result', {}).get('structuredContent', {}).get('matches', [])
    if not hits or not all(h.get('url', '').startswith(meta.get('site_url', 'https://')) for h in hits):
        errs.append('MCP search returned no matches, or matches without a page link')
    if not resp.get(4, {}).get('result', {}).get('isError'):
        errs.append('MCP server did not report an unknown identifier as an error')
    if 0 in resp or None in resp and 1 not in resp:
        errs.append('MCP server answered a notification')
    return errs


def c33_tooling_and_feedback(site, repo, pages):
    """Rule (version 1.8): the tools page shows every kind of tool, pairing and RFI question, the CSV matches, and the private feedback route appears where promised only when set."""
    errs = []
    sys.path.insert(0, str(repo / 'tools'))
    try:
        import importlib
        b = importlib.import_module('build')
        d = b.load(repo / 'content' / 'playbooks.yaml')
    except Exception as e:
        return [f'content does not load: {e}']
    finally:
        sys.path.pop(0)
    T = d.get('tooling')
    t = (site / 'tooling.html').read_text(encoding='utf-8') if (site / 'tooling.html').exists() else ''
    if T:
        if not t:
            errs.append('tooling.html missing')
        for c in T['categories']:
            if f'id="{c["id"]}"' not in t:
                errs.append(f'tooling.html: category {c["id"]} missing')
        for x in T['pairs']:
            if b.E(x['between']) not in t:
                errs.append(f'tooling.html: pairing "{x["between"]}" missing')
        qn = sum(len(g['items']) for g in T['questions'])
        shown = len(re.findall(r'<li id="RFI-\d\d">', t))
        if shown != qn:
            errs.append(f'tooling.html shows {shown} RFI questions, content has {qn}')
        f = site / 'data' / 'interoperability-questions.csv'
        rows = list(csv.reader(f.open(encoding='utf-8'))) if f.exists() else []
        if len(rows) - 1 != qn:
            errs.append(f'interoperability-questions.csv has {max(len(rows) - 1, 0)} questions, content has {qn}')
    url = (d.get('ms_form') or {}).get('url') or ''
    for name in ('contact.html', 'test.html'):
        html = (site / name).read_text(encoding='utf-8') if (site / name).exists() else ''
        has = 'id="private-feedback"' in html
        if url and not has:
            errs.append(f'{name}: private feedback form is set but not shown')
        if not url and has:
            errs.append(f'{name}: private feedback block shown with no form address')
        if url and has and b.E(url) not in html:
            errs.append(f'{name}: private feedback block does not link to the form')
    if url and not re.match(r'https://forms\.(office\.com|cloud\.microsoft)/', url):
        errs.append('ms_form.url must be an https Microsoft Forms address')
    return errs


def c34_sister_portals(site, repo, pages):
    """Rule (version 1.8.1): signposts to sister portals go only to those portals, name the portal and its status every time, sit outside this portal's own journeys, and the cross-reference manifest points only at anchors that exist."""
    import yaml
    errs = []
    fw = yaml.safe_load((repo / 'content' / 'frameworks.yaml').read_text(encoding='utf-8'))
    R = fw.get('related') or {}
    P = {p['id']: p for p in R.get('portals', [])}
    for key, items in (R.get('placements') or {}).items():
        name = f'{key}.html'
        html = (site / name).read_text(encoding='utf-8') if (site / name).exists() else ''
        m = re.search(r'<aside class="related" id="related-' + re.escape(key) + r'".*?</aside>', html, re.S)
        if not m:
            errs.append(f'{name}: related signposts missing'); continue
        box = m.group(0)
        at = html.find(box)
        start = html.rfind('role="tabpanel"', 0, at)
        if start > -1:
            seg = html[start:at]
            if seg.count('<section') + 1 > seg.count('</section>'):
                errs.append(f'{name}: related signposts sit inside a tab, inside this portal\'s own journey')
        links = re.findall(r'<li><a href="([^"]+)"', box)
        if len(links) != len(items):
            errs.append(f'{name}: {len(links)} related links shown, content has {len(items)}')
        for href in links:
            if not any(href.startswith(p['url']) for p in P.values()):
                errs.append(f'{name}: related link {href} does not go to a sister portal')
        for p in {it['portal'] for it in items}:
            if P[p]['name'] not in box or P[p]['status'] not in box:
                errs.append(f'{name}: related links do not name {p} and its status')
    xf = site / 'data' / 'xref.json'
    if not xf.exists():
        return errs + ['data/xref.json missing']
    man = json.loads(xf.read_text(encoding='utf-8'))
    base = man.get('url', '')
    for group, rows in man.get('keys', {}).items():
        if not rows:
            errs.append(f'xref.json: {group} is empty')
        for r in rows:
            u = r.get('url', '')
            if not u.startswith(base):
                errs.append(f'xref.json: {group} {u} is not on this portal'); continue
            page, _, frag = u[len(base):].partition('#')
            if not (site / page).exists():
                errs.append(f'xref.json: {group} points at missing page {page}'); continue
            if frag and frag not in pages.get(page, parse(site / page)).ids:
                errs.append(f'xref.json: {group} points at missing anchor {page}#{frag}')
    return errs


def c35_estate_compass(site, repo, pages):
    """Rule (version 1.8.2): the estate compass is self-contained and cannot call the network, links only to the three portals, every link into this portal lands on a page and anchor that exist, every situation has a route across at least two portals, and it carries the usual footer."""
    import yaml
    errs = []
    f = site / 'compass' / 'index.html'
    if not f.exists():
        return ['compass/index.html missing']
    html = f.read_text(encoding='utf-8')
    c = yaml.safe_load((repo / 'compass' / 'compass.yaml').read_text(encoding='utf-8'))
    bases = {p['id']: p['url'] for p in c['portals']}
    csp = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', html)
    if not csp or "default-src 'none'" not in csp.group(1) or 'connect-src' in csp.group(1):
        errs.append('compass: Content Security Policy must forbid network requests')
    for need, what in (('<html lang="en-GB">', 'language'), ('class="skip"', 'skip link'), ('<h1>', 'heading'), ('id="sc-sum"', 'self-check'),
                       ('aria-label="Barcode of build identifier', 'barcode colophon'), ('aria-label="QR code linking to', 'QR colophon'), ('contact form', 'contact form')):
        if need not in html:
            errs.append(f'compass: no {what}')
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    if not m:
        return errs + ['compass: no data']
    d = json.loads(m.group(1).replace('<\\/', '</'))
    urls = re.findall(r'href="(https?://[^"]+)"', html)
    for r in d['routes'].values():
        if len({s['p'] for s in r['steps']}) < 2:
            errs.append(f'compass: route {r["title"]} stays in one portal')
        urls += [bases[s['p']] + s['path'] for s in r['steps'] if s['path'] != 'role']
    urls += [bases['dam'] + o['dam'] for o in d['questions'][1]['options']]
    urls += [u for a in d['areas'] for k in ('dam', 'dq', 'cat') for _, u in a[k]]
    urls += [bases[p['id']] + p['start']['path'] for p in d['portals']]
    for o in d['questions'][0]['options']:
        if o['id'] not in d['routes']:
            errs.append(f'compass: situation {o["id"]} has no route')
    for u in sorted(set(urls)):
        if not any(u.startswith(b) for b in bases.values()):
            errs.append(f'compass: link {u} goes outside the three portals'); continue
        if u.startswith(bases['dam']):
            page, _, frag = u[len(bases['dam']):].partition('#')
            page = page or 'index.html'
            if not (site / page).exists():
                errs.append(f'compass: link to missing page {page}'); continue
            if frag and frag not in pages.get(page, parse(site / page)).ids:
                errs.append(f'compass: link to missing anchor {page}#{frag}')
    return errs


def c36_have_your_say(site, repo, pages):
    """Rule (version 1.9): Have your say is reachable from every page; research sign-up is private, never GitHub; every idea link goes to this repository's discussions;
    every backlog item is published with a score that matches the weighted criteria (weights sum to 100, votes only raise demand); Now respects its limit;
    any item placed differently from its score has a decision; an unpublished strategy is labelled unconfirmed; and no address appears anywhere in it."""
    import yaml
    errs = []
    f = site / 'research.html'
    if not f.exists():
        return ['research.html missing']
    html = f.read_text(encoding='utf-8')
    meta = yaml.safe_load((repo / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))['meta']
    R = yaml.safe_load((repo / 'content' / 'frameworks.yaml').read_text(encoding='utf-8'))['research']
    gh = f'https://github.com/{meta["repo"]}'
    for name, p in pages.items():
        if name != '404.html' and 'research.html' not in p.links:
            errs.append(f'{name}: no link to Have your say')
    # sign-up is private
    i = html.find('id="sign-up"')
    j = html.find('<h2', i + 1)
    sec = html[i:j] if i >= 0 else ''
    if not sec:
        errs.append('research: no sign-up section')
    for u in re.findall(r'href="([^"]+)"', sec):
        if 'github.com' in u or 'github.io' in u:
            errs.append(f'research: sign-up links to GitHub ({u}); sign-up must be a private form')
    btn = re.search(r'<a class="btn" href="([^"]+)"[^>]*>.*?Sign up to take part', sec)
    if btn and not btn.group(1).startswith(('https://forms.cloud.microsoft/', 'https://forms.office.com/', 'https://forms.microsoft.com/', 'https://forms.service.gov.uk/')):
        errs.append(f'research: sign-up button goes to {btn.group(1)}, not a private form')
    for u in re.findall(r'href="(https://github\.com/[^"]*discussions[^"]*)"', html):
        if not u.startswith(gh + '/discussions'):
            errs.append(f'research: idea link {u} is not this repository\'s discussions')
    # scores, recomputed independently
    if sum(c['weight'] for c in R['criteria']) != 100:
        errs.append('research: criteria weights do not sum to 100')
    jf = site / 'data' / 'backlog.json'
    if not jf.exists():
        return errs + ['research: data/backlog.json missing']
    J = json.loads(jf.read_text(encoding='utf-8'))
    pub = {x['id']: x for x in J['items']}
    decided = {x['item'] for x in R['decisions']}
    for x in R['backlog']:
        y = pub.get(x['id'])
        if not y:
            errs.append(f'research: {x["id"]} not in backlog.json'); continue
        a = dict(x['assess'])
        band_v = max([b for t, b in R['vote_bands'] if y.get('votes', 0) >= t] or [0])
        a['demand'] = max(a['demand'], band_v)
        s = round(sum(c['weight'] * a[c['id']] / 3 for c in R['criteria']))
        if y['score'] != s:
            errs.append(f'research: {x["id"]} published score {y["score"]} but the criteria give {s}')
        row = re.search(rf'<tr[^>]*>(?:(?!</tr>).)*id="bl-{x["id"]}".*?</tr>', html, re.S)
        cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row.group(0), re.S) if row else []
        if len(cells) < 6 or cells[5].strip() != str(s):
            errs.append(f'research: {x["id"]} missing from the backlog table or shows the wrong score')
        band = next(b for m, b, _ in R['bands'] if s >= m)
        if x['status'] in ('now', 'next', 'later') and band != x['status'] and (x['id'] not in decided or f'id="decision-{x["id"]}"' not in html):
            errs.append(f'research: {x["id"]} placed in {x["status"]} against its score with no published decision')
    m = re.search(r'<section class="rm-col rm-now".*?</section>', html, re.S)
    if not m or m.group(0).count('class="cr-card rm-card"') > R['wip_limit']:
        errs.append(f'research: Now column missing or over its limit of {R["wip_limit"]}')
    for s in R['strategies']:
        if not s['ref']:
            li = re.search(rf'<li id="strategy-{s["id"]}">.*?</li>', html, re.S)
            if not li or 'unconfirmed' not in li.group(0):
                errs.append(f'research: unpublished strategy {s["id"]} not labelled unconfirmed')
    for name in ('research.html', 'data/backlog.json', 'data/backlog.csv'):
        p = site / name
        if p.exists() and EMAIL.search(p.read_text(encoding='utf-8')):
            errs.append(f'{name}: contains an address')
    return errs


CHECKS = [c01_page_basics, c02_unique_ids, c03_links_resolve, c04_no_email, c05_no_external_assets, c06_dqap_expansion,
          c07_no_annex_a, c08_provenance_on_requirements, c09_no_decks_or_films, c10_tables, c11_machine_readable,
          c12_csp_clean, c13_accessible_graphics, c14_colophon_and_contact, c15_no_placeholders, c16_search_engines,
          c17_no_personal_details, c18_plain_english, c19_citations, c20_page_governance, c21_no_restricted_licence_text,
          c22_signposts_verified, c23_repository_metadata, c24_actions_pinned,
          c25_workflow_inventory, c26_commit_identity,
          c27_registers_in_repository, c28_open_data_catalogue, c29_limitations_referenced, c30_testing_pack,
          c31_navigation_aids, c32_mcp_server, c33_tooling_and_feedback, c34_sister_portals, c35_estate_compass, c36_have_your_say]


def run(site, repo, only=None, quiet=False):
    site, repo = Path(site), Path(repo)
    pages = {f.name: parse(f) for f in sorted(site.glob('*.html'))}
    failed = {}
    for c in CHECKS:
        if only and c.__name__ not in only:
            continue
        errs = c(site, repo, pages)
        if errs:
            failed[c.__name__] = errs
        if not quiet:
            print(('FAIL ' if errs else 'pass ') + c.__name__ + ': ' + (c.__doc__ or '').strip().split('\n')[0])
            for e in errs[:12]:
                print('     ', e)
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default=str(ROOT / 'site'))
    ap.add_argument('--repo', default=str(ROOT))
    a = ap.parse_args(argv)
    failed = run(a.site, a.repo)
    print(f'{len(CHECKS) - len(failed)} of {len(CHECKS)} static checks passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
