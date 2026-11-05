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
                if href.startswith('mailto:'): errs.append(f'{name}: mailto link {href}')
                continue
            path, _, frag = href.partition('#')
            target = name if not path else path
            f = site / target
            if not f.exists():
                errs.append(f'{name}: missing file {href}'); continue
            if frag and f.suffix == '.html':
                tp = pages.get(target) or parse(f)
                if frag not in tp.ids: errs.append(f'{name}: missing anchor {href}')
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
            if tag == 'link' and re.match(r'https?:|//', a.get('href', '')): errs.append(f'{name}: remote link {a["href"]}')
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


CHECKS = [c01_page_basics, c02_unique_ids, c03_links_resolve, c04_no_email, c05_no_external_assets, c06_dqap_expansion,
          c07_no_annex_a, c08_provenance_on_requirements, c09_no_decks_or_films, c10_tables, c11_machine_readable,
          c12_csp_clean, c13_accessible_graphics, c14_colophon_and_contact, c15_no_placeholders]


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
