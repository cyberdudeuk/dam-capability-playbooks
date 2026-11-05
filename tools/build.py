#!/usr/bin/env python3
"""Build the DAM capability playbooks portal from content/playbooks.yaml.

Usage: python tools/build.py [--out site]

Everything in the output folder is generated. Edit content/playbooks.yaml, site_src/ or this script, never the output.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import math
import random
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
E = lambda s: html.escape(str(s if s is not None else ''), quote=True)


class ContentError(Exception):
    pass


# ---------------------------------------------------------------------------
# Load and validate
# ---------------------------------------------------------------------------
def load(path):
    d = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
    validate(d)
    return d


def validate(d):
    errs = []
    ids = {}
    def reg(i, where):
        if i in ids:
            errs.append(f'duplicate id {i} in {where} (also {ids[i]})')
        ids[i] = where
    for s in d['sources']: reg(s['id'], 'sources')
    for r in d['requirements']: reg(r['id'], 'requirements')
    for r in d['roles']: reg('role:' + r['code'], 'roles')
    for c in d['capabilities']:
        reg('cap:' + c['id'], 'capabilities')
        for st in c['stages']:
            reg(f"{c['id']}.{st['id']}", 'stages')
        for t in c.get('templates', []): reg(t['id'], 'templates')
    for c in d['concepts']: reg('c:' + c['id'], 'concepts')
    for l in d['library']: reg(l['id'], 'library')
    for j in d['journeys']: reg(j['id'], 'journeys')
    for x in d['interlocks']: reg(x['id'], 'interlocks')
    src = {s['id'] for s in d['sources']}
    req = {r['id'] for r in d['requirements']}
    roles = {r['code'] for r in d['roles']}
    caps = {c['id'] for c in d['capabilities']}
    stages = {f"{c['id']}.{st['id']}" for c in d['capabilities'] for st in c['stages']}
    concepts = {c['id'] for c in d['concepts']}
    provs = {'V', 'P', 'O', 'K', 'U'}
    for r in d['requirements']:
        if r['src'] not in src: errs.append(f"{r['id']}: unknown source {r['src']}")
        if r['cap'] not in caps: errs.append(f"{r['id']}: unknown capability {r['cap']}")
        if r['prov'] not in provs: errs.append(f"{r['id']}: bad provenance {r['prov']}")
        if r['strength'] not in {'must', 'should', 'may', 'method', 'gap'}: errs.append(f"{r['id']}: bad strength")
    for s in d['sources']:
        if s['prov'] not in provs: errs.append(f"{s['id']}: bad provenance")
        if not str(s['url']).startswith('https://'): errs.append(f"{s['id']}: url must be https")
    for r in d['roles']:
        if r.get('src') and r['src'] not in src: errs.append(f"role {r['code']}: unknown source")
    for c in d['capabilities']:
        for st in c['stages']:
            for rq in st.get('reqs', []):
                if rq not in req: errs.append(f"{c['id']}.{st['id']}: unknown requirement {rq}")
            accountable = [k for k, v in st['raci'].items() if v == 'A']
            for k in st['raci']:
                if k not in roles: errs.append(f"{c['id']}.{st['id']}: unknown role {k}")
            if not accountable: errs.append(f"{c['id']}.{st['id']}: RACI has no accountable role")
        for rc in c['roles']:
            if rc not in roles: errs.append(f"{c['id']}: unknown role {rc}")
    for x in d['interlocks']:
        for k in ('from', 'to'):
            if x[k] not in stages: errs.append(f"{x['id']}: unknown stage {x[k]}")
    for c in d['concepts']:
        if c['broader'] and c['broader'] not in concepts: errs.append(f"concept {c['id']}: unknown broader {c['broader']}")
        if c.get('src') and c['src'] not in src: errs.append(f"concept {c['id']}: unknown source")
        if c['prov'] not in provs: errs.append(f"concept {c['id']}: bad provenance")
    for l in d['library']:
        if l.get('src') and l['src'] not in src: errs.append(f"{l['id']}: unknown source")
        for cp in l['cap']:
            if cp not in caps: errs.append(f"{l['id']}: unknown capability {cp}")
    if errs:
        raise ContentError('\n'.join(errs))


# ---------------------------------------------------------------------------
# Small HTML helpers
# ---------------------------------------------------------------------------
ICONS = {
    'home': '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
    'spine': '<path d="M12 2v20"/><path d="M5 6h14M5 12h14M5 18h14"/>',
    'shield': '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/>',
    'book': '<path d="M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4z"/><path d="M20 4h-4a2 2 0 0 0-2 2"/><path d="M20 4v14h-6"/>',
    'gauge': '<path d="M4 18a8 8 0 1 1 16 0"/><path d="M12 18l4-6"/>',
    'link': '<path d="M10 14a4 4 0 0 0 6 0l3-3a4 4 0 0 0-6-6l-1 1"/><path d="M14 10a4 4 0 0 0-6 0l-3 3a4 4 0 0 0 6 6l1-1"/>',
    'route': '<circle cx="6" cy="19" r="2"/><circle cx="18" cy="5" r="2"/><path d="M8 19h6a4 4 0 0 0 0-8H10a4 4 0 0 1 0-8h6"/>',
    'library': '<path d="M4 4v16M9 4v16M14 4l5 16"/>',
    'graph': '<circle cx="6" cy="6" r="2"/><circle cx="18" cy="8" r="2"/><circle cx="10" cy="18" r="2"/><path d="M8 7l8 1M7 8l2 8M17 10l-6 7"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.5"/>',
    'list': '<path d="M9 6h11M9 12h11M9 18h11M4 6h.5M4 12h.5M4 18h.5"/>',
    'users': '<circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0"/><path d="M16 5a3 3 0 0 1 0 6M21 20a6 6 0 0 0-4-5.6"/>',
    'check': '<path d="M4 12l5 5L20 6"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'flag': '<path d="M5 21V4h11l-2 4 2 4H5"/>',
    'file': '<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v4h4"/>',
    'search': '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    'moon': '<path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10z"/>',
    'alert': '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17v.5"/>',
    'tag': '<path d="M3 12V3h9l9 9-9 9z"/><circle cx="7.5" cy="7.5" r="1"/>',
    'cycle': '<path d="M20 12a8 8 0 0 1-14 5"/><path d="M4 12a8 8 0 0 1 14-5"/><path d="M18 3v4h-4M6 21v-4h4"/>',
}


def icon(name):
    return f'<svg class="i" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICONS[name]}</svg>'


PROV_TEXT = {
    'V': 'Verified against the primary source',
    'P': 'From the owner\'s own playbook suites or portfolio material',
    'O': 'This playbook\'s own synthesis or operating rule',
    'K': 'Background knowledge, not checked this session',
    'U': 'Unconfirmed',
}


def prov(code, date=None):
    t = PROV_TEXT[code] + (f' on {date}' if code == 'V' and date else '')
    return f'<abbr class="prov {code}" title="{E(t)}">{code}<span class="visually-hidden">: {E(t)}</span></abbr>'


def table(cap_id, caption, headers, rows, cls=None, row_attrs=None):
    th = ''.join(f'<th scope="col"{" class=raci" if (cls and h in cls) else ""}>{E(h)}</th>' for h in headers)
    body = []
    for i, r in enumerate(rows):
        cells = []
        for j, c in enumerate(r):
            tag = 'th scope="row"' if j == 0 else 'td'
            klass = ''
            if cls and headers[j] in cls:
                klass = f' class="raci r-{E(c)}"' if c else ' class="raci"'
            cells.append(f'<{tag}{klass}>{c}</{tag.split()[0]}>')
        attrs = row_attrs[i] if row_attrs else ''
        body.append(f'<tr{attrs}>' + ''.join(cells) + '</tr>')
    return (f'<div class="table-wrap" role="region" aria-labelledby="{cap_id}" tabindex="0"><table>'
            f'<caption id="{cap_id}">{E(caption)}</caption><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def ul(items, raw=False):
    return '<ul>' + ''.join(f'<li>{i if raw else E(i)}</li>' for i in items) + '</ul>'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------------------------------------------------------------------------
# Codes for the colophon: QR (segno) and Code 128 barcode (drawn as rects)
# ---------------------------------------------------------------------------
def qr_svg(text, label):
    import segno
    q = segno.make(text, error='m')
    m = q.matrix
    n = len(m)
    border, scale = 2, 3
    size = (n + 2 * border) * scale
    d = []
    for y, row in enumerate(m):
        x = 0
        while x < n:
            if row[x]:
                x0 = x
                while x < n and row[x]:
                    x += 1
                d.append(f'M{(x0 + border) * scale} {(y + border) * scale}h{(x - x0) * scale}v{scale}h-{(x - x0) * scale}z')
            else:
                x += 1
    return (f'<svg role="img" aria-label="{E(label)}" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#ffffff"/><path fill="#0b0c0c" d="{"".join(d)}"/></svg>')


def barcode_svg(text, label):
    import barcode
    code = barcode.get('code128', text)
    bits = code.build()[0]
    w, h, q = 1.5, 46, 10
    rects, x = [], q
    i = 0
    while i < len(bits):
        if bits[i] == '1':
            j = i
            while j < len(bits) and bits[j] == '1':
                j += 1
            rects.append(f'<rect x="{x + i * w:.1f}" y="0" width="{(j - i) * w:.1f}" height="{h}"/>')
            i = j
        else:
            i += 1
    width = len(bits) * w + 2 * q
    return (f'<svg role="img" aria-label="{E(label)}" viewBox="0 0 {width:.0f} {h}" width="{width:.0f}" height="{h}">'
            f'<rect width="{width:.0f}" height="{h}" fill="#ffffff"/><g fill="#0b0c0c">{"".join(rects)}</g></svg>')


# ---------------------------------------------------------------------------
# Site model
# ---------------------------------------------------------------------------
NAV = [
    ('index', 'Home', 'home'),
    ('dam', 'DAM Policy', 'spine'),
    ('governance', 'Governance', 'shield'),
    ('cataloguing', 'Cataloguing', 'book'),
    ('quality', 'Quality', 'gauge'),
    ('together', 'Joined up', 'link'),
    ('journeys', 'By role', 'route'),
    ('library', 'Library', 'library'),
    ('knowledge', 'Knowledge', 'graph'),
    ('about', 'About', 'info'),
]
CAP_PAGE = {'gov': 'governance', 'cat': 'cataloguing', 'dq': 'quality'}


class Site:
    def __init__(self, d, out):
        self.d, self.out = d, Path(out)
        self.m = d['meta']
        self.src = {s['id']: s for s in d['sources']}
        self.req = {r['id']: r for r in d['requirements']}
        self.roles = {r['code']: r for r in d['roles']}
        self.caps = {c['id']: c for c in d['capabilities']}
        self.concepts = {c['id']: c for c in d['concepts']}
        self.search = []
        self.build_id = None

    # -- glossary linking -------------------------------------------------
    def gloss(self, text, used=None):
        """Escape text, then link the first mention of selected glossary terms with a tooltip."""
        out = E(text)
        used = used if used is not None else set()
        skip = {'purpose', 'return', 'role', 'recipe', 'metadata', 'raci', 'exception', 'charter'}
        for c in self.d['concepts']:
            if c['id'] in skip or c['id'] in used:
                continue
            for label in [c['term']] + list(c.get('alt') or []):
                if len(label) < 4:
                    continue
                pat = re.compile(r'(?<![\w>/-])(' + re.escape(E(label)) + r')(?![\w<])', re.I)
                m = pat.search(out)
                if m and not self._inside_tag(out, m.start()):
                    a = (f'<a class="term" href="knowledge.html#c-{c["id"]}" data-tip="{E(c["term"] + ": " + c["def"])}">'
                         f'{m.group(1)}</a>')
                    out = out[:m.start()] + a + out[m.end():]
                    used.add(c['id'])
                    break
        return out

    @staticmethod
    def _inside_tag(s, pos):
        lt, gt = s.rfind('<', 0, pos), s.rfind('>', 0, pos)
        if lt > gt:
            return True
        open_a, close_a = s.rfind('<a ', 0, pos), s.rfind('</a>', 0, pos)
        return open_a > close_a

    def src_link(self, sid):
        if not sid:
            return 'Owner\'s internal material'
        s = self.src[sid]
        return f'<a href="{E(s["url"])}">{E(s["title"])}</a>{prov(s["prov"], self.m["verified_on"])}'

    def req_links(self, ids):
        return ' '.join(f'<a class="pill {self.req[i]["cap"]}" href="dam.html#{i}">{E(i)}</a>' for i in ids)

    def add_search(self, title, kind, url, snippet=''):
        self.search.append({'t': title, 'k': kind, 'u': url, 's': snippet[:160]})

    # -- page shell ----------------------------------------------------------
    def page(self, key, title, body, drawer=None, desc='', crumbs=None, jsonld=None, extra_json=None):
        m = self.m
        nav = ''.join(
            f'<li><a href="{k}.html"{" aria-current=page" if k == key else ""}>{icon(ic)}{E(lbl)}</a></li>'
            for k, lbl, ic in NAV)
        nav = nav.replace('aria-current=page', 'aria-current="page"')
        drawer_html, toggle = '', ''
        if drawer:
            groups = []
            for g in drawer:
                items = ''.join(
                    f'<li><a href="#{E(it["id"])}">{icon(it.get("icon", "list"))}<span>{E(it["label"])}</span>'
                    + (f'<span class="count" aria-label="{it["count"]} items">{it["count"]}</span>' if it.get('count') is not None else '')
                    + ('<span class="flag">New</span>' if it.get('new') else '') + '</a></li>'
                    for it in g['items'])
                groups.append(f'<details open><summary>{icon(g.get("icon", "list"))}{E(g["label"])}'
                              f'<span class="count" aria-label="{len(g["items"])} sections">{len(g["items"])}</span></summary><ul>{items}</ul></details>')
            drawer_html = (f'<nav class="drawer" id="drawer" aria-label="On this page"><h2>On this page</h2>{"".join(groups)}</nav>')
            toggle = ('<button type="button" class="switch" id="drawer-toggle" role="switch" aria-checked="true" aria-controls="drawer" hidden>'
                      '<span class="track" aria-hidden="true"><span class="knob"></span></span>Page contents</button>')
        crumb_html = ''
        if crumbs:
            crumb_html = ('<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="index.html">Home</a></li>'
                          + ''.join(f'<li>{E(c)}</li>' for c in crumbs) + '</ol></nav>')
        ld = {
            '@context': 'https://schema.org', '@type': 'WebPage', 'name': f'{title} - {m["title"]}',
            'identifier': f'{m["id"]}-{key}', 'version': m['version'], 'dateModified': m['as_of'],
            'isPartOf': {'@type': 'WebSite', 'name': m['title'], 'url': m['site_url']},
            'license': m['licence_content_url'], 'inLanguage': 'en-GB',
        }
        if jsonld:
            ld.update(jsonld)
        foot = self.footer()
        extra = ''
        if extra_json:
            for k, v in extra_json.items():
                extra += f'<script type="application/json" id="{k}">{json_safe(v)}</script>'
        return f'''<!DOCTYPE html>
<html lang="en-GB" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'">
<meta name="referrer" content="no-referrer">
<title>{E(title)} - {E(m["title"])}</title>
<meta name="description" content="{E(desc or m["subtitle"])}">
<meta name="artefact:id" content="{E(m["id"])}-{key}">
<meta name="artefact:version" content="{E(m["version"])}">
<meta name="artefact:class" content="portal">
<meta name="artefact:as-of" content="{E(m["as_of"])}">
<meta name="artefact:review-date" content="{E(m["review"])}">
<meta name="artefact:build" content="{E(self.build_id)}">
<link rel="stylesheet" href="assets/style.css">
<script type="application/ld+json">{json_safe(ld)}</script>
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header class="mast">
<div class="mast-in"><a class="name" href="index.html">{E(m["title"])}</a>
<button type="button" data-open-search hidden aria-haspopup="dialog">{icon("search")}Search <kbd>Ctrl K</kbd></button>
<button type="button" id="theme-toggle">{icon("moon")}<span class="label">Dark mode</span></button></div>
</header>
<div class="banner"><strong class="tag">Prototype</strong>Not an official GOV.UK service or published GDS guidance. Where it repeats GDS guidance, the GOV.UK page is the authority. <a href="{E(m["contact_form"])}">Tell us what you think (contact form)</a>.</div>
<nav class="gbar" id="gbar" aria-label="Portal sections"><ul class="top">{nav}<li class="more" hidden><button type="button" aria-expanded="false">More sections</button><ul></ul></li></ul></nav>
<div class="wrap">
{drawer_html}
<main id="main" tabindex="-1">
{crumb_html}
<div class="toolbar">{toggle}</div>
{body}
</main>
</div>
{foot}
<div class="palette" id="palette" hidden role="dialog" aria-modal="true" aria-labelledby="palette-title">
<div class="palette-box"><h2 id="palette-title" class="visually-hidden">Search the playbooks</h2>
<label for="palette-input" class="visually-hidden">Search</label>
<input id="palette-input" type="search" autocomplete="off" placeholder="Search stages, requirements, terms, templates" aria-controls="palette-list">
<p id="palette-status" class="visually-hidden" aria-live="polite"></p>
<ul id="palette-list" role="listbox" aria-label="Results"></ul>
<p><small>Up and down arrows to move, Enter to open, Escape to close.</small></p></div></div>
<script src="assets/search-index.js"></script>
{extra}
<script src="assets/app.js"></script>
</body>
</html>
'''

    def footer(self):
        m = self.m
        return f'''<footer class="site" id="colophon">
<div class="cols">
<div><h2>About this portal</h2>
<p>{E(m["status"])}</p>
<p>Profile: {E(m["profile"])}</p>
<p>Built with help from an AI assistant (Claude). Every fact carries a provenance label; a person reviews and publishes every release.</p>
<p><a href="about.html#provenance">How we label sources</a> · <a href="about.html#accessibility">Accessibility statement</a> · <a href="about.html#open">Open register</a></p></div>
<div><h2>Contact</h2>
<p><a href="{E(m["contact_form"])}">Use the contact form</a>. Never include personal data: issues are public.</p>
<p>{E(m["contact_note"])}</p></div>
<div><h2>Licence and version</h2>
<p>Content: <a href="{E(m["licence_content_url"])}">{E(m["licence_content"])}</a>, except where stated. Code: {E(m["licence_code"])}.</p>
<p>Version {E(m["version"])}, as of {E(m["as_of"])}, next review {E(m["review"])}. Build {E(self.build_id)}.</p>
<p>Attribution: {E(m["attribution"])}.</p>
<div class="codes">{self.codes}</div></div>
</div>
</footer>'''

    # -- pages ----------------------------------------------------------------
    def build(self):
        d, m = self.d, self.m
        h = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode())
        for f in sorted((ROOT / 'site_src').glob('*')) + [Path(__file__)]:
            h.update(f.read_bytes())
        digest = h.hexdigest()[:8].upper()
        self.build_id = f'{m["id"]}-{m["version"]}-{digest}'
        self.codes = (f'<figure>{barcode_svg(self.build_id, "Barcode of build identifier " + self.build_id)}<figcaption>{E(self.build_id)}</figcaption></figure>'
                      f'<figure>{qr_svg(m["site_url"], "QR code linking to " + m["site_url"])}<figcaption>Portal address</figcaption></figure>')
        self.collect_search()
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / 'assets').mkdir(parents=True)
        (self.out / 'data').mkdir()
        for f in ('style.css', 'app.js'):
            shutil.copy(ROOT / 'site_src' / f, self.out / 'assets' / f)
        pages = {
            'index': self.p_index, 'dam': self.p_dam, 'governance': lambda: self.p_cap('gov'),
            'cataloguing': lambda: self.p_cap('cat'), 'quality': lambda: self.p_cap('dq'),
            'together': self.p_together, 'journeys': self.p_journeys, 'library': self.p_library,
            'knowledge': self.p_knowledge, 'about': self.p_about,
        }
        for k, fn in pages.items():
            (self.out / f'{k}.html').write_text(fn(), encoding='utf-8')
        (self.out / '404.html').write_text(self.p_404(), encoding='utf-8')
        (self.out / 'assets' / 'search-index.js').write_text('window.DCP_INDEX=' + json_safe(self.search_index) + ';\n', encoding='utf-8')
        self.exports()
        (self.out / '.nojekyll').write_text('')
        return self.build_id

    @property
    def search_index(self):
        return self.search

    def collect_search(self):
        self.search = []
        for k, lbl, _ in NAV:
            self.add_search(lbl, 'Page', f'{k}.html')
        for c in self.d['capabilities']:
            p = CAP_PAGE[c['id']]
            for st in c['stages']:
                self.add_search(f'{c["short"]} {st["n"]}: {st["name"]}', f'{c["name"]} stage', f'{p}.html#{c["id"]}-{st["id"]}', st['goal'] + ' ' + ' '.join(st['steps']))
            for t in c.get('templates', []):
                self.add_search(t['name'], f'{c["name"]} template', f'{p}.html#{t["id"]}', ' '.join(t['fields']))
        for r in self.d['requirements']:
            self.add_search(f'{r["id"]} ({r["strength"]})', 'DAM Policy requirement', f'dam.html#{r["id"]}', r['text'])
        for c in self.d['concepts']:
            self.add_search(c['term'], 'Glossary term', f'knowledge.html#c-{c["id"]}', c['def'] + ' ' + ' '.join(c.get('alt') or []))
        for r in self.d['roles']:
            self.add_search(r['name'], 'Role', f'together.html#role-{r["code"]}', r['text'])
        for l in self.d['library']:
            self.add_search(l['title'], f'Library: {l["type"]}', f'library.html#{l["id"]}', l.get('note', ''))
        for j in self.d['journeys']:
            self.add_search(j['who'], 'Journey', f'journeys.html#{j["id"]}', j['need'])
        for o in self.d['open_register']:
            self.add_search(o['id'], 'Open register', f'about.html#{o["id"]}', o['item'])

    def counts(self):
        d = self.d
        return {
            'reqs': len(d['requirements']), 'must': sum(1 for r in d['requirements'] if r['strength'] == 'must'),
            'stages': sum(len(c['stages']) for c in d['capabilities']),
            'templates': sum(len(c.get('templates', [])) for c in d['capabilities']),
            'concepts': len(d['concepts']), 'library': len(d['library']), 'sources': len(d['sources']),
            'verified': sum(1 for s in d['sources'] if s['prov'] == 'V'),
        }

    def p_index(self):
        d, m, n = self.d, self.m, self.counts()
        cards = ''
        for c in d['capabilities']:
            p = CAP_PAGE[c['id']]
            musts = [r for r in d['requirements'] if r['cap'] == c['id'] and r['strength'] == 'must']
            cards += (f'<div class="card {c["id"]}"><h3>{icon(c["icon"])} <a href="{p}.html">{E(c["name"])}</a></h3>'
                      f'<p><strong>{E(c["question"])}</strong></p><p>{self.gloss(c["purpose"])}</p>'
                      f'<p><span class="big cap-{c["id"]}">{len(c["stages"])}</span>{E(c["method_name"].lower())} · {len(musts)} policy musts</p>'
                      f'<p><a href="{p}.html#method">Start the {E(c["short"].lower())} method</a></p></div>')
        roles = ''.join(f'<li><a href="journeys.html#{j["id"]}">{E(j["who"])}</a>: {E(j["need"])}</li>' for j in d['journeys'])
        body = f'''<h1>{E(m["title"])}</h1>
<p class="lede">{E(m["subtitle"])}. The Data Asset Management (DAM) Policy asks every UK government department and arm's length body to identify, describe, own and manage the quality of its critical data assets. These playbooks put the three capabilities that make that possible side by side, with the policy as the spine.</p>
<h2 id="capabilities">The three capabilities</h2>
<div class="cards">{cards}</div>
<h2 id="start">Start here</h2>
<div class="cards">
<div class="card"><h3>{icon("spine")} <a href="dam.html">What the policy requires</a></h3><p>{n["reqs"]} requirements traced to GOV.UK guidance, {n["must"]} of them 'must'. Each is tagged to the capability that meets it.</p></div>
<div class="card"><h3>{icon("link")} <a href="together.html">How the three join up</a></h3><p>One role model, {len(d["interlocks"])} hand-offs between capabilities and one annual cycle, so nothing is recorded twice.</p></div>
<div class="card"><h3>{icon("search")} Search everything</h3><p>Press Ctrl and K, or the slash key, to search {len(self.search)} stages, requirements, terms and templates. Or use the <a href="knowledge.html">knowledge pages</a>.</p></div>
</div>
<h2 id="roles">Start from your role</h2>
<ul>{roles}</ul>
<h2 id="numbers">In numbers</h2>
{table("t-numbers", "What the portal brings together (counted from the content file at build time)", ["Item", "Count"], [
    ["Method stages across the three capabilities", str(n["stages"])], ["Policy requirements traced", str(n["reqs"])],
    ["Templates", str(n["templates"])], ["Glossary concepts", str(n["concepts"])],
    ["Library items", str(n["library"])], [f"Sources ({n['verified']} verified this release)", str(n["sources"])]])}
'''
        drawer = [{'label': 'Home', 'icon': 'home', 'items': [
            {'id': 'capabilities', 'label': 'The three capabilities', 'icon': 'shield', 'count': 3},
            {'id': 'start', 'label': 'Start here', 'icon': 'flag'},
            {'id': 'roles', 'label': 'Start from your role', 'icon': 'users', 'count': len(d['journeys'])},
            {'id': 'numbers', 'label': 'In numbers', 'icon': 'list'}]}]
        return self.page('index', 'Home', body, drawer, jsonld={'@type': 'WebPage', 'about': ['Data governance', 'Data cataloguing', 'Data quality']})

    def p_dam(self):
        d = self.d
        rows, attrs = [], []
        for r in d['requirements']:
            c = self.caps[r['cap']]
            rows.append([f'<span id="{r["id"]}">{E(r["id"])}</span>', f'<span class="strength {r["strength"]}">{E(r["strength"])}</span>',
                         f'<a class="pill {c["id"]}" href="{CAP_PAGE[c["id"]]}.html">{E(c["short"])}</a>',
                         self.gloss(r['text']) + prov(r['prov'], self.m['verified_on']), self.src_link(r['src']),
                         ' '.join(f'<a class="pill {cc["id"]}" href="{CAP_PAGE[cc["id"]]}.html#{cc["id"]}-{st["id"]}">{E(cc["short"])} {st["n"]}</a>'
                                  for cc in d['capabilities'] for st in cc['stages'] if r['id'] in st.get('reqs', [])) or 'Not met by a stage (see open register)'])
            attrs.append(f' data-item data-cap="{r["cap"]}" data-strength="{r["strength"]}"')
        filt = f'''<div class="filters" data-filter="req-table" role="group" aria-label="Filter requirements">
<div><label for="f-cap">Capability</label><select id="f-cap" name="cap"><option value="">All</option>{"".join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in d["capabilities"])}</select></div>
<div><label for="f-str">Strength</label><select id="f-str" name="strength"><option value="">All</option>{"".join(f'<option>{s}</option>' for s in ["must", "should", "method", "gap"])}</select></div>
<div><label for="f-q">Contains</label><input id="f-q" type="search" name="q"></div>
<p class="count-out" aria-live="polite"></p></div>'''
        tl = ''.join(f'<li class="{E(t["kind"])}"><strong>{E(t["when"])}</strong> {E(t["what"])}{prov(t["prov"])}</li>' for t in d['timeline'])
        sup = ''.join(f'<li><strong>{E(s["name"])}</strong>: {E(s["detail"])}{prov(s["prov"])}</li>' for s in d['support'])
        tbl = table('t-reqs', 'DAM Policy requirements and the stages that meet them', ['ID', 'Strength', 'Capability', 'Requirement', 'Source', 'Met by'], rows, row_attrs=attrs)
        tbl = tbl.replace('<tbody>', '<tbody id="req-table">', 1)
        scope = self.req['DAM-R01']
        body = f'''<h1>The DAM Policy spine</h1>
<p class="lede">What the <a href="{E(self.src["SRC-DAM"]["url"])}">data asset management policy in government</a> and its linked guidance require, which capability meets each requirement, and which stage of which playbook does the work.</p>
<div class="inset"><p><strong>Who it applies to.</strong> UK government departments and their arm's length bodies, including executive agencies, non-departmental public bodies and non-ministerial departments. Optional for public corporations. It does not apply to councils. The devolved governments have their own data sharing governance{prov("V", self.m["verified_on"])}.</p>
<p><strong>What is in scope.</strong> {E(scope["text"])}</p></div>
<h2 id="requirements">Requirements</h2>
<p>'Must' and 'should' follow the wording of the source. 'Method' is a prescribed technique. 'Gap' means the source promises something it does not yet specify.</p>
{filt}{tbl}
<h2 id="accountability">Who is accountable</h2>
{table("t-acc", "Accountability under the policy", ["Body", "Responsibility"], [
    ["GDS", "Sets guidance and standards; develops the discoverability service; works with organisations to prioritise assets with proven reuse value"],
    ["Chief Data Officer Council", "Oversees implementation"], ["Chief data officer of each organisation", "Implements the policy in the organisation"],
    ["Minister for Digital Government and Data", "Writes to ministers each year on progress"],
    ["Departments", "Identify and report assets, provide metadata, coordinate and assure ALB returns"],
    ["ALBs", "Identify and report in-scope assets with their department"], ["Named data owners", "Accountable for decisions about each asset"]])}
<p>Source: {self.src_link("SRC-DAM")}</p>
<h2 id="timeline">Rollout and reporting dates</h2>
<p class="warning">These dates come from the owner's internal portfolio material, not a public GOV.UK page. Confirm before relying on them (open item OR-07).</p>
<ol class="timeline">{tl}</ol>
<h2 id="support">Support already on offer</h2>
<ul>{sup}</ul>
'''
        drawer = [{'label': 'DAM Policy', 'icon': 'spine', 'items': [
            {'id': 'requirements', 'label': 'Requirements', 'icon': 'check', 'count': len(d['requirements']), 'new': True},
            {'id': 'accountability', 'label': 'Who is accountable', 'icon': 'users', 'count': 7},
            {'id': 'timeline', 'label': 'Rollout and reporting dates', 'icon': 'clock', 'count': len(d['timeline'])},
            {'id': 'support', 'label': 'Support on offer', 'icon': 'flag', 'count': len(d['support'])}]}]
        return self.page('dam', 'DAM Policy spine', body, drawer, crumbs=['DAM Policy'],
                         desc='What the DAM Policy requires and which capability meets it')

    def raci_table(self, c, tid):
        codes = c['roles']
        rows = [[f'<a href="#{c["id"]}-{st["id"]}">{st["n"]}. {E(st["name"])}</a>'] + [E(st['raci'].get(k, '')) for k in codes] for st in c['stages']]
        return table(tid, f'Who does what in {c["name"].lower()} (A accountable, R responsible, C consulted, I informed)',
                     ['Stage'] + codes, rows, cls=set(codes))

    def p_cap(self, cid):
        c, d = self.caps[cid], self.d
        p = CAP_PAGE[cid]
        used = set()
        stages = ''
        for st in c['stages']:
            extra = f' · DQAP {E(st["dqap"])}' if st.get('dqap') else ''
            stages += (f'<section class="stage {cid}" id="{cid}-{st["id"]}" aria-labelledby="h-{cid}-{st["id"]}">'
                       f'<h3 id="h-{cid}-{st["id"]}">{st["n"]}. {E(st["name"])}</h3>'
                       f'<p class="meta">Trigger: {E(st["trigger"])}{extra}</p><p><strong>{self.gloss(st["goal"], used)}</strong></p>'
                       f'<div class="cols"><div><h4>Steps</h4><ol>{"".join(f"<li>{self.gloss(s, used)}</li>" for s in st["steps"])}</ol></div>'
                       f'<div><h4>Outputs</h4>{ul(st["outputs"])}<h4>Checklist</h4>{ul(st["checklist"])}</div></div>'
                       f'<p>Meets: {self.req_links(st.get("reqs", []))} · Accountable: {E(", ".join(self.roles[k]["name"] for k, v in st["raci"].items() if v == "A"))}</p>'
                       + (f'<p class="tip"><strong>Practitioner tip.</strong> {E(st["tip"])}</p>' if st.get('tip') else '')
                       + '</section>')
        reqs = [r for r in d['requirements'] if r['cap'] == cid]
        req_rows = [[f'<a href="dam.html#{r["id"]}">{E(r["id"])}</a>', f'<span class="strength {r["strength"]}">{E(r["strength"])}</span>', E(r['text']) + prov(r['prov'])] for r in reqs]
        roles = ''.join(f'<li id="{cid}-role-{r}"><strong>{E(self.roles[r]["name"])}</strong> ({E(r)}): {E(self.roles[r]["text"])}{prov(self.roles[r]["prov"])}</li>' for r in c['roles'])
        tmpl = ''.join(f'<section id="{t["id"]}"><h3>{E(t["name"])} <small>({E(t["id"])})</small></h3>{ul(t["fields"])}</section>' for t in c.get('templates', []))
        esc_rows = [[E(e['level']), E(e['who']), E(e['trigger']), E(e['when'])] for e in c.get('escalation', [])]
        meas_rows = [[E(x['name']), E(x['target'])] for x in c['measures']]
        srcs = sorted({s['id'] for s in d['sources'] if cid in s['caps']})
        src_list = ''.join(f'<li>{self.src_link(s)}: {E(self.src[s]["note"])} <small>({E(self.src[s]["dates"])})</small></li>' for s in srcs)
        lib = ''.join(f'<li><a href="library.html#{l["id"]}">{E(l["title"])}</a> ({E(l["status"])})</li>' for l in d['library'] if cid in l['cap'] and not l.get('src'))
        ils = [x for x in d['interlocks'] if x['from'].startswith(cid + '.') or x['to'].startswith(cid + '.')]
        il_html = ''.join(f'<li><a href="together.html#{x["id"]}">{E(x["id"])}</a> {self.stage_ref(x["from"])} → {self.stage_ref(x["to"])}: {E(x["what"])}</li>' for x in ils)
        extra_tab, extra_drawer = '', []
        if cid == 'cat':
            mrows = [[f'<code>{E(x["prop"])}</code>', E(x['obligation']), E(x['mem']), E(x['rule'])] for x in c['metadata']]
            extra_tab = ('<h2 id="metadata">Metadata properties</h2>'
                         f'<p>From {self.src_link("SRC-MD")}, mapped to the {self.src_link("SRC-MEM")}. The guidance does not give one mandatory or recommended column, so the obligation follows the wording of each section. "Listed" means it is in the list of information to record without a stated strength.</p>'
                         + table('t-meta', 'Metadata to record for each critical data asset', ['Property', 'Obligation', 'MEM slot', 'How to record it'], mrows)
                         + '<p>Write in plain English, expand acronyms, use ISO 8601 dates, and use "unknown" or "not applicable" instead of leaving a property blank. Links must work from outside your organisation.</p>')
            extra_drawer = [{'id': 'metadata', 'label': 'Metadata properties', 'icon': 'tag', 'count': len(c['metadata'])}]
        if cid == 'dq':
            dims = ''.join(f'<li><strong>{E(x["name"])}</strong>: {E(x["text"])}</li>' for x in c['dimensions'])
            pr = ''.join(f'<li>{E(x["name"])}</li>' for x in c['principles'])
            tools = ''.join(f'<li><a href="{E(t["url"])}">{E(t["name"])}</a></li>' for t in c['tools'])
            extra_tab = (f'<h2 id="principles">Principles and dimensions</h2><p>From {self.src_link("SRC-GDQF")}.</p><h3>Five principles</h3><ol>{pr}</ol>'
                         f'<h3>Six dimensions</h3><ul>{dims}</ul><h2 id="tools">Tools</h2><p>The Data Quality Commons is the master for these tools{prov("P")}. Nothing is uploaded when you check a file.</p><ul>{tools}</ul>')
            extra_drawer = [{'id': 'principles', 'label': 'Principles and dimensions', 'icon': 'list', 'count': 11},
                            {'id': 'tools', 'label': 'Tools', 'icon': 'gauge', 'count': len(c['tools'])}]
        tabs = [
            ('overview', 'Overview', f'''<h2 id="why">Why it matters</h2><p class="lede">{self.gloss(c["purpose"])}</p><p>{E(c["why"])}</p>
<h2 id="policy">What the policy requires of it</h2>{table(f"t-req-{cid}", f"Policy requirements met by {c['name'].lower()}", ["ID", "Strength", "Requirement"], req_rows)}
<h2 id="links">How it joins the other two</h2><ul>{il_html}</ul>'''),
            ('method', 'Method', f'<h2 id="stages">{E(c["method_name"])}{prov(c["method_prov"])}</h2><p>{E(c["method_intro"])}</p>{stages}{extra_tab}'),
            ('roles', 'Roles and RACI', f'<h2 id="role-list">Roles</h2><ul>{roles}</ul><h2 id="raci">Decision rights</h2>{self.raci_table(c, "t-raci-" + cid)}'),
            ('templates', 'Templates', f'<h2 id="template-list">Templates</h2><p>Blank structures. Record roles, never named individuals or personal email addresses.</p>{tmpl}'),
            ('escalation', 'Measures and escalation', f'<h2 id="measures">Measures</h2>{table("t-meas-" + cid, "Measures for " + c["name"].lower(), ["Measure", "Target"], meas_rows)}'
                                                      + (f'<h2 id="ladder">Escalation</h2><p>{E(c["escalation_note"])}</p>{table("t-esc-" + cid, "Escalation for " + c["name"].lower(), ["Level", "Who", "Trigger", "Timescale"], esc_rows)}' if esc_rows else '<h2 id="ladder">Escalation</h2><p>Cataloguing issues escalate through the governance ladder (see <a href="governance.html#ladder">governance escalation</a>).</p>')),
            ('sources', 'Sources', f'<h2 id="source-list">Sources</h2><ul>{src_list}</ul>' + (f'<h2 id="internal">Internal material behind this playbook</h2><ul>{lib}</ul>' if lib else '')),
        ]
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(lbl)}</button>' for i, (k, lbl, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{body}</section>' for i, (k, lbl, body) in enumerate(tabs))
        body = (f'<p class="caption">Capability playbook</p><h1>{icon(c["icon"])} {E(c["name"])}</h1><p class="lede"><strong>{E(c["question"])}</strong></p>'
                f'<div class="tabs">{"<div role=tablist aria-label=" + chr(34) + E(c["name"]) + " sections" + chr(34) + ">" + tablist + "</div>"}{panels}</div>')
        body = body.replace('<div role=tablist', '<div role="tablist"')
        drawer = [
            {'label': 'Overview', 'icon': 'info', 'items': [{'id': 'why', 'label': 'Why it matters', 'icon': 'info'},
                                                             {'id': 'policy', 'label': 'Policy requirements', 'icon': 'spine', 'count': len(reqs)},
                                                             {'id': 'links', 'label': 'Joins with the others', 'icon': 'link', 'count': len(ils), 'new': True}]},
            {'label': 'Method', 'icon': c['icon'], 'items': [{'id': f'{cid}-{st["id"]}', 'label': f'{st["n"]}. {st["name"]}', 'icon': 'check'} for st in c['stages']] + extra_drawer},
            {'label': 'Using it', 'icon': 'users', 'items': [{'id': 'role-list', 'label': 'Roles', 'icon': 'users', 'count': len(c['roles'])},
                                                              {'id': 'raci', 'label': 'Decision rights', 'icon': 'list'},
                                                              {'id': 'template-list', 'label': 'Templates', 'icon': 'file', 'count': len(c.get('templates', []))},
                                                              {'id': 'measures', 'label': 'Measures', 'icon': 'gauge', 'count': len(c['measures'])},
                                                              {'id': 'ladder', 'label': 'Escalation', 'icon': 'alert', 'count': len(c.get('escalation', [])) or None},
                                                              {'id': 'source-list', 'label': 'Sources', 'icon': 'library', 'count': len(srcs)}]},
        ]
        return self.page(p, c['name'], body, drawer, crumbs=[c['name']], desc=c['purpose'],
                         jsonld={'@type': ['WebPage', 'HowTo'], 'name': c['name'], 'step': [{'@type': 'HowToStep', 'position': st['n'], 'name': st['name'], 'text': st['goal']} for st in c['stages']]})

    def stage_ref(self, ref):
        cid, sid = ref.split('.')
        c = self.caps[cid]
        st = next(s for s in c['stages'] if s['id'] == sid)
        return f'<a class="pill {cid}" href="{CAP_PAGE[cid]}.html#{cid}-{sid}">{E(c["short"])} {st["n"]} {E(st["name"])}</a>'

    def p_together(self):
        d = self.d
        il = [[f'<span id="{x["id"]}">{E(x["id"])}</span>', self.stage_ref(x['from']), self.stage_ref(x['to']), E(x['what'])] for x in d['interlocks']]
        cyc = [[E(r['when']), E(r['gov']), E(r['cat']), E(r['dq'])] for r in d['cycle']]
        codes = [r['code'] for r in d['roles']]
        rows = []
        for c in d['capabilities']:
            for st in c['stages']:
                rows.append([f'<a href="{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}">{E(c["short"])} {st["n"]}. {E(st["name"])}</a>'] + [E(st['raci'].get(k, '')) for k in codes])
        roles = ''.join(f'<li id="role-{r["code"]}"><strong>{E(r["name"])}</strong> ({E(r["code"])}): {E(r["text"])}{prov(r["prov"])}</li>' for r in d['roles'])
        body = f'''<h1>How the three capabilities join up</h1>
<p class="lede">Governance gives each asset an owner and a place to decide. Cataloguing describes the asset so others can find it. Quality proves it is fit to use. Done separately, the same owner, the same review and the same evidence get recorded three times. These hand-offs make each one record once.</p>
<h2 id="interlocks">Hand-offs between capabilities</h2>
{table("t-il", "Where one capability's output is another's input", ["ID", "From", "To", "What passes"], il)}
<h2 id="cycle">One joined-up year</h2>
{table("t-cycle", "What each capability does at each point in the year", ["When", "Governance", "Cataloguing", "Quality"], cyc)}
<h2 id="roles">One role model</h2>
<p>The same roles appear in all three playbooks. Records hold roles, never named individuals.</p>
<ul>{roles}</ul>
<h2 id="raci">Who does what across all three</h2>
{table("t-raci-all", "Decision rights across every stage (A accountable, R responsible, C consulted, I informed)", ["Stage"] + codes, rows, cls=set(codes))}
'''
        drawer = [{'label': 'Joined up', 'icon': 'link', 'items': [
            {'id': 'interlocks', 'label': 'Hand-offs', 'icon': 'link', 'count': len(d['interlocks']), 'new': True},
            {'id': 'cycle', 'label': 'One joined-up year', 'icon': 'cycle', 'count': len(d['cycle']), 'new': True},
            {'id': 'roles', 'label': 'One role model', 'icon': 'users', 'count': len(d['roles'])},
            {'id': 'raci', 'label': 'Who does what', 'icon': 'list', 'count': len(rows)}]}]
        return self.page('together', 'Joined up', body, drawer, crumbs=['Joined up'], desc='How governance, cataloguing and quality join up')

    def p_journeys(self):
        d = self.d
        out = ''
        for j in d['journeys']:
            steps = ''.join(f'<li><a href="{s["page"]}.html#{s["anchor"]}">{E(s["label"])}</a></li>' for s in j['steps'])
            out += (f'<section id="{j["id"]}" class="card"><h2>{E(j["who"])}</h2><p>{E(j["need"])}</p><ol>{steps}</ol>'
                    f'<p class="meta">About {j["minutes"]} minutes. Assumed need, not yet validated with users (OR-04).</p></section>')
        body = f'<h1>Start from your role</h1><p class="lede">Each route links the stages you need, across all three capabilities, in the order you need them.</p><div class="cards">{out}</div>'
        drawer = [{'label': 'Roles', 'icon': 'route', 'items': [{'id': j['id'], 'label': j['who'], 'icon': 'users', 'count': len(j['steps'])} for j in d['journeys']]}]
        return self.page('journeys', 'Start from your role', body, drawer, crumbs=['By role'])

    def p_library(self):
        d = self.d
        rows, attrs = [], []
        for l in d['library']:
            where = self.src_link(l['src']) if l.get('src') else 'Internal, not published' + prov(l['prov'])
            caps = ' '.join(f'<a class="pill {c}" href="{CAP_PAGE[c]}.html">{E(self.caps[c]["short"])}</a>' for c in l['cap'])
            rows.append([f'<span id="{l["id"]}">{E(l["title"])}</span>', E(l['type']), caps, E(l['status']), E(l['audience']), where + (f'<br><small>{E(l["note"])}</small>' if l.get('note') else '')])
            attrs.append(f' data-item data-cap="{" ".join(l["cap"])}" data-type="{slug(l["type"])}" data-status="{slug(l["status"])}"')
        types = sorted({l['type'] for l in d['library']})
        statuses = sorted({l['status'] for l in d['library']})
        filt = f'''<div class="filters" data-filter="lib-table" role="group" aria-label="Filter the library">
<div><label for="l-cap">Capability</label><select id="l-cap" name="cap"><option value="">All</option>{"".join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in d["capabilities"])}</select></div>
<div><label for="l-type">Type</label><select id="l-type" name="type"><option value="">All</option>{"".join(f'<option value="{slug(t)}">{E(t)}</option>' for t in types)}</select></div>
<div><label for="l-status">Status</label><select id="l-status" name="status"><option value="">All</option>{"".join(f'<option value="{slug(s)}">{E(s)}</option>' for s in statuses)}</select></div>
<div><label for="l-q">Contains</label><input id="l-q" type="search" name="q"></div>
<p class="count-out" aria-live="polite"></p></div>'''
        tbl = table('t-lib', 'Every piece of playbook material, wherever it lives', ['Title', 'Type', 'Capability', 'Status', 'For', 'Where'], rows, row_attrs=attrs).replace('<tbody>', '<tbody id="lib-table">', 1)
        tm = []
        for c in d['capabilities']:
            for t in c.get('templates', []):
                tm.append([f'<a href="{CAP_PAGE[c["id"]]}.html#{t["id"]}">{E(t["name"])}</a>', f'<span class="pill {c["id"]}">{E(c["short"])}</span>', str(len(t['fields'])), f'<a href="data/templates.csv">CSV</a>'])
        body = f'''<h1>Library</h1><p class="lede">Every piece of playbook material for the three capabilities: published GOV.UK guidance, standards, tools and the internal suites this portal consolidates. Published items link to their master; nothing is copied.</p>
<h2 id="library">All material</h2>{filt}{tbl}
<h2 id="templates">Templates</h2>{table("t-tmpl", "Templates in the three playbooks", ["Template", "Capability", "Fields", "Download"], tm)}
<h2 id="data">Open data</h2><p>Everything on this portal is generated from one content file, also published in open formats:</p>
<ul><li><a href="data/playbooks.json">Full content (JSON)</a></li><li><a href="data/requirements.csv">Requirements (CSV)</a></li><li><a href="data/templates.csv">Templates (CSV)</a></li>
<li><a href="data/glossary.csv">Glossary (CSV)</a></li><li><a href="data/vocabulary.ttl">Vocabulary (SKOS, Turtle)</a></li><li><a href="data/vocabulary.jsonld">Vocabulary (SKOS, JSON-LD)</a></li>
<li><a href="data/catalogue.jsonld">Catalogue of sources (DCAT, JSON-LD)</a></li><li><a href="data/metadata-dictionary.csv">Metadata data dictionary (CSV)</a></li></ul>'''
        drawer = [{'label': 'Library', 'icon': 'library', 'items': [
            {'id': 'library', 'label': 'All material', 'icon': 'library', 'count': len(d['library'])},
            {'id': 'templates', 'label': 'Templates', 'icon': 'file', 'count': len(tm)},
            {'id': 'data', 'label': 'Open data', 'icon': 'list', 'count': 8}]}]
        return self.page('library', 'Library', body, drawer, crumbs=['Library'])

    def graph(self):
        d = self.d
        nodes, edges = [], []
        def add(i, label, kind, k, text='', url=''):
            nodes.append({'id': i, 'label': label, 'kind': kind, 'k': k, 'text': text, 'url': url})
        for c in d['capabilities']:
            add('cap:' + c['id'], c['name'], 'Capability', 'cap', c['question'], CAP_PAGE[c['id']] + '.html')
            for st in c['stages']:
                sid = f'{c["id"]}.{st["id"]}'
                add(sid, f'{c["short"]} {st["n"]} {st["name"]}', 'Stage', 'stage', st['goal'], f'{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}')
                edges.append(['cap:' + c['id'], sid])
                for r in st.get('reqs', []):
                    edges.append([sid, r])
        for r in d['requirements']:
            add(r['id'], r['id'], f'Requirement ({r["strength"]})', 'req', r['text'], f'dam.html#{r["id"]}')
            edges.append([r['id'], r['src']])
        used_src = {e[1] for e in edges if e[1].startswith('SRC-')}
        for s in d['sources']:
            if s['id'] in used_src:
                add(s['id'], s['title'][:38], 'Source', 'src', s['title'], s['url'])
        for x in d['interlocks']:
            edges.append([x['from'], x['to']])
        # deterministic force layout
        rnd = random.Random(7)
        W, H = 1100, 760
        pos = {n['id']: [rnd.uniform(80, W - 80), rnd.uniform(60, H - 60)] for n in nodes}
        anchors = {'cap:gov': (250, 200), 'cap:cat': (850, 200), 'cap:dq': (550, 640)}
        for a, p in anchors.items():
            pos[a] = list(p)
        ids = [n['id'] for n in nodes]
        for it in range(320):
            disp = {i: [0.0, 0.0] for i in ids}
            k = 58
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    pa, pb = pos[ids[a]], pos[ids[b]]
                    dx, dy = pa[0] - pb[0], pa[1] - pb[1]
                    dist = max(math.hypot(dx, dy), 1)
                    f = k * k / dist
                    disp[ids[a]][0] += dx / dist * f; disp[ids[a]][1] += dy / dist * f
                    disp[ids[b]][0] -= dx / dist * f; disp[ids[b]][1] -= dy / dist * f
            for a, b in edges:
                pa, pb = pos[a], pos[b]
                dx, dy = pa[0] - pb[0], pa[1] - pb[1]
                dist = max(math.hypot(dx, dy), 1)
                f = dist * dist / k
                disp[a][0] -= dx / dist * f; disp[a][1] -= dy / dist * f
                disp[b][0] += dx / dist * f; disp[b][1] += dy / dist * f
            t = 18 * (1 - it / 320) + 0.5
            for i in ids:
                if i in anchors:
                    continue
                dx, dy = disp[i]
                dl = max(math.hypot(dx, dy), 1)
                pos[i][0] = min(W - 70, max(70, pos[i][0] + dx / dl * min(dl, t)))
                pos[i][1] = min(H - 30, max(30, pos[i][1] + dy / dl * min(dl, t)))
        r_of = {'cap': 16, 'stage': 7, 'req': 6, 'src': 7}
        lines = ''.join(f'<line x1="{pos[a][0]:.0f}" y1="{pos[a][1]:.0f}" x2="{pos[b][0]:.0f}" y2="{pos[b][1]:.0f}" data-a="{E(a)}" data-b="{E(b)}"/>' for a, b in edges)
        gs = ''
        for n in nodes:
            x, y = pos[n['id']]
            short = n['label'] if n['k'] in ('cap', 'req') else ''
            gs += (f'<g class="node" tabindex="0" role="button" data-id="{E(n["id"])}" aria-label="{E(n["kind"] + ": " + n["label"])}">'
                   f'<circle class="k-{n["k"]}" cx="{x:.0f}" cy="{y:.0f}" r="{r_of[n["k"]]}"/>'
                   + (f'<text x="{x + r_of[n["k"]] + 3:.0f}" y="{y + 4:.0f}">{E(short)}</text>' if short else '') + '<title>' + E(n['label']) + '</title></g>')
        svg = f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Knowledge graph of capabilities, stages, requirements and sources">{lines}{gs}</svg>'
        return svg, {'nodes': nodes, 'edges': edges}

    def p_knowledge(self):
        d = self.d
        conc = sorted(d['concepts'], key=lambda c: c['term'].lower())
        rows, attrs = [], []
        for c in conc:
            b = self.concepts.get(c['broader']) if c['broader'] else None
            rows.append([f'<span id="c-{c["id"]}">{E(c["term"])}</span>', self.gloss(c['def'], {c['id']}) + prov(c['prov'], self.m['verified_on']),
                         E(', '.join(c.get('alt') or [])) or '-', f'<a href="#c-{b["id"]}">{E(b["term"])}</a>' if b else '-',
                         ' '.join(f'<span class="pill {x}">{E(self.caps[x]["short"])}</span>' for x in c['caps']),
                         self.src_link(c['src']) if c.get('src') else 'Owner\'s playbook suites'])
            attrs.append(f' data-item data-cap="{" ".join(c["caps"])}"')
        filt = f'''<div class="filters" data-filter="gl-table" role="group" aria-label="Filter the glossary">
<div><label for="g-cap">Capability</label><select id="g-cap" name="cap"><option value="">All</option>{"".join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in d["capabilities"])}</select></div>
<div><label for="g-q">Contains</label><input id="g-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>'''
        gl = table('t-gl', 'Glossary and thesaurus', ['Term', 'Definition', 'Also called', 'Broader term', 'Capability', 'Source'], rows, row_attrs=attrs).replace('<tbody>', '<tbody id="gl-table">', 1)
        def tree(parent):
            kids = [c for c in conc if c['broader'] == parent]
            if not kids:
                return ''
            return '<ul>' + ''.join(f'<li><a href="#c-{k["id"]}">{E(k["term"])}</a>{tree(k["id"])}</li>' for k in kids) + '</ul>'
        svg, gdata = self.graph()
        mrows = [[f'<code>{E(x["prop"])}</code>', E(x['mem']), E(x['obligation']), E(x['rule'])] for x in self.caps['cat']['metadata']]
        tabs = [
            ('glossary', 'Glossary', f'<h2 id="gl">Glossary and thesaurus</h2><p>Every term with its alternative labels (the thesaurus) and its broader term (the taxonomy).</p>{filt}{gl}'),
            ('taxonomy', 'Taxonomy', f'<h2 id="tax">Taxonomy</h2><p>Terms arranged by broader and narrower meaning.</p><div class="tree">{tree(None)}</div>'),
            ('graph-tab', 'Knowledge graph', f'<h2 id="kg">Knowledge graph</h2><p>Capabilities, their stages, the policy requirements they meet and the sources behind them. Select a node to see what it connects to; the same information is in the tables on the DAM Policy and capability pages.</p>'
                                             f'<p class="legend"><span class="lg-cap">Capability</span><span class="lg-stage">Stage</span><span class="lg-req">Requirement</span><span class="lg-src">Source</span></p>'
                                             f'<div class="graph-wrap" id="graph">{svg}</div><p><button type="button" class="btn secondary" id="graph-clear">Clear selection</button></p><div id="graph-detail" aria-live="polite">Select a node to see what it connects to.</div>'),
            ('dictionary', 'Data dictionary', f'<h2 id="dict">Data dictionary</h2><p>The fields of a critical data asset catalogue record.</p>{table("t-dict", "Catalogue record fields", ["Property", "MEM slot", "Obligation", "Rule"], mrows)}'
                                              f'<p>Ontology: the <a href="data/vocabulary.ttl">SKOS vocabulary</a> uses <code>skos:prefLabel</code>, <code>skos:altLabel</code>, <code>skos:broader</code> and <code>skos:definition</code>, with <code>dcterms:source</code> for provenance.</p>'),
        ]
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(l)}</button>' for i, (k, l, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{b}</section>' for i, (k, l, b) in enumerate(tabs))
        body = f'<h1>Knowledge</h1><p class="lede">The shared vocabulary of the three playbooks, and how everything connects.</p><div class="tabs"><div role="tablist" aria-label="Knowledge views">{tablist}</div>{panels}</div>'
        drawer = [{'label': 'Knowledge', 'icon': 'graph', 'items': [
            {'id': 'gl', 'label': 'Glossary and thesaurus', 'icon': 'list', 'count': len(conc)},
            {'id': 'tax', 'label': 'Taxonomy', 'icon': 'tag'},
            {'id': 'kg', 'label': 'Knowledge graph', 'icon': 'graph', 'count': len(gdata['nodes']), 'new': True},
            {'id': 'dict', 'label': 'Data dictionary', 'icon': 'file', 'count': len(mrows)}]}]
        return self.page('knowledge', 'Knowledge', body, drawer, crumbs=['Knowledge'], extra_json={'graph-data': gdata},
                         jsonld={'@type': ['WebPage', 'DefinedTermSet'], 'hasDefinedTerm': [{'@type': 'DefinedTerm', 'name': c['term'], 'description': c['def']} for c in conc]})

    def p_about(self):
        d, m = self.d, self.m
        orr = ''.join(f'<tr id="{o["id"]}"><th scope="row">{E(o["id"])}</th><td>{E(o["item"])}</td><td>{E(o["who"])}</td></tr>' for o in d['open_register'])
        dfr = [[E(x['id']), E(x['found']), E(x['defect']), E(x['cause']), E(x['check'])] for x in d['defects']]
        adv = ''.join(f'<li><strong>{E(a["challenge"])}</strong><br>{E(a["answer"])}</li>' for a in d['adversarial'])
        n = self.counts()
        provs = ''.join(f'<li>{prov(k)} {E(v)}</li>' for k, v in PROV_TEXT.items())
        body = f'''<h1>About this portal</h1>
<h2 id="intent">Intent</h2><p>{E(m["intent"])}</p>
<p>Profile and grade: {E(m["profile"])} {E(m["grade_reason"])}</p>
<h2 id="checkpoint">Checkpoint</h2>
<p><strong>Brief.</strong> Identify, consolidate and assemble all playbook material along governance, cataloguing and quality, and deliver it through an interactive, easy-to-navigate portal published on GitHub Pages.</p>
<p><strong>Arc.</strong> Material was found in the GOV.UK guidance behind the policy ({n["verified"]} sources verified on {E(m["verified_on"])}), the Data Quality Commons playbook, the owner's Data Governance Playbook suite, the Metadata Exchange Model and the OCDO portfolio material. It was reconciled into one content file with a requirements spine, three methods, one role model and the hand-offs between them.</p>
<p><strong>Against the brief.</strong> Met for governance and quality. Partly met for cataloguing: the internal Data Cataloguing Playbook could not be read here, so the cataloguing method is a synthesis of public guidance (OR-01).</p>
<h2 id="provenance">How sources are labelled</h2><ul>{provs}</ul>
<p>Requirement strength follows the source wording. Stage sequences are labelled as synthesis or as coming from the owner's suites; they are not GOV.UK requirements.</p>
<h2 id="adversarial">The case against, answered</h2><ul>{adv}</ul>
<h2 id="open">Open register</h2>
<div class="table-wrap" role="region" aria-labelledby="t-open" tabindex="0"><table><caption id="t-open">What design cannot close, and who must act</caption><thead><tr><th scope="col">ID</th><th scope="col">Item</th><th scope="col">Who must act</th></tr></thead><tbody>{orr}</tbody></table></div>
<h2 id="defects">Defect register</h2><p>Every defect gets a check that stops it coming back. The check suite never shrinks.</p>
{table("t-def", "Defects and the checks that prevent them", ["ID", "Found", "Defect", "Root cause", "Check"], dfr)}
<h2 id="accessibility">Accessibility statement</h2>
<p>This portal aims to meet WCAG 2.2 at level AA. Each release is checked automatically with axe-core in a real browser, for keyboard use, for horizontal scrolling from 320 to 1920 pixels wide, and in light and dark modes.</p>
<p>Known limitations: it has not been tested in person with disabled users or with assistive technology users (OR-09). The knowledge graph is a visual aid; the same relationships are in the tables on the DAM Policy and capability pages.</p>
<p>If you find a problem, use the <a href="{E(m["contact_form"])}">contact form</a>. If you cannot use it, ask a colleague to raise it for you. You can also contact the Equality Advisory and Support Service (EASS) if you are not happy with how we respond.</p>
<h2 id="privacy">Privacy</h2><p>The portal sets no cookies and loads nothing from other sites. Your theme and drawer choices are kept only in your own browser. The contact form is a public GitHub issue: do not include personal data.</p>
<h2 id="build">Build and checks</h2><p>Build {E(self.build_id)}. Generated from one content file. Each release runs structural, link, provenance, email, banned-phrase, accessibility and layout checks; every check is proved to fail on a deliberate break before it is trusted.</p>'''
        drawer = [{'label': 'About', 'icon': 'info', 'items': [
            {'id': 'intent', 'label': 'Intent', 'icon': 'flag'}, {'id': 'checkpoint', 'label': 'Checkpoint', 'icon': 'check'},
            {'id': 'provenance', 'label': 'Source labels', 'icon': 'tag', 'count': 5},
            {'id': 'adversarial', 'label': 'The case against', 'icon': 'alert', 'count': len(d['adversarial'])},
            {'id': 'open', 'label': 'Open register', 'icon': 'list', 'count': len(d['open_register'])},
            {'id': 'defects', 'label': 'Defect register', 'icon': 'alert', 'count': len(d['defects'])},
            {'id': 'accessibility', 'label': 'Accessibility', 'icon': 'users'},
            {'id': 'privacy', 'label': 'Privacy', 'icon': 'shield'}, {'id': 'build', 'label': 'Build and checks', 'icon': 'check'}]}]
        return self.page('about', 'About', body, drawer, crumbs=['About'])

    def p_404(self):
        return self.page('404', 'Page not found', '<h1>Page not found</h1><p>If you typed the address, check it is correct.</p><p><a href="index.html">Go to the home page</a> or press Ctrl and K to search.</p>')

    # -- exports ---------------------------------------------------------------
    def exports(self):
        d, m, out = self.d, self.m, self.out / 'data'
        (out / 'playbooks.json').write_text(json.dumps(d, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
        def write_csv(name, header, rows):
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator='\n')
            w.writerow(header); w.writerows(rows)
            (out / name).write_text(buf.getvalue(), encoding='utf-8')
        write_csv('requirements.csv', ['id', 'capability', 'strength', 'requirement', 'source', 'source_url', 'provenance'],
                  [[r['id'], r['cap'], r['strength'], r['text'], self.src[r['src']]['title'], self.src[r['src']]['url'], r['prov']] for r in d['requirements']])
        write_csv('templates.csv', ['template_id', 'template', 'capability', 'field_order', 'field'],
                  [[t['id'], t['name'], c['id'], i + 1, f] for c in d['capabilities'] for t in c.get('templates', []) for i, f in enumerate(t['fields'])])
        write_csv('glossary.csv', ['id', 'term', 'alt_labels', 'broader', 'definition', 'capabilities', 'provenance'],
                  [[c['id'], c['term'], '; '.join(c.get('alt') or []), c['broader'] or '', c['def'], ' '.join(c['caps']), c['prov']] for c in d['concepts']])
        write_csv('metadata-dictionary.csv', ['property', 'mem_slot', 'obligation', 'rule'],
                  [[x['prop'], x['mem'], x['obligation'], x['rule']] for x in self.caps['cat']['metadata']])
        base = m['site_url'] + 'vocab#'
        ttl = ['@prefix skos: <http://www.w3.org/2004/02/skos/core#> .', '@prefix dcterms: <http://purl.org/dc/terms/> .', f'@prefix dcp: <{base}> .', '',
               f'dcp:scheme a skos:ConceptScheme ; dcterms:title "{m["title"]} vocabulary"@en-GB ; dcterms:modified "{m["as_of"]}" .', '']
        def lit(s):
            return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"@en-GB'
        for c in d['concepts']:
            parts = [f'dcp:{c["id"]} a skos:Concept', 'skos:inScheme dcp:scheme', f'skos:prefLabel {lit(c["term"])}', f'skos:definition {lit(c["def"])}']
            parts += [f'skos:altLabel {lit(a)}' for a in (c.get('alt') or [])]
            if c['broader']:
                parts.append(f'skos:broader dcp:{c["broader"]}')
            else:
                parts.append('skos:topConceptOf dcp:scheme')
            if c.get('src'):
                parts.append(f'dcterms:source <{self.src[c["src"]]["url"]}>')
            ttl.append(' ;\n  '.join(parts) + ' .\n')
        (out / 'vocabulary.ttl').write_text('\n'.join(ttl), encoding='utf-8')
        jl = {'@context': {'skos': 'http://www.w3.org/2004/02/skos/core#', 'dcterms': 'http://purl.org/dc/terms/'},
              '@graph': [{'@id': base + c['id'], '@type': 'skos:Concept', 'skos:prefLabel': {'@value': c['term'], '@language': 'en-GB'},
                          'skos:definition': {'@value': c['def'], '@language': 'en-GB'},
                          'skos:altLabel': [{'@value': a, '@language': 'en-GB'} for a in (c.get('alt') or [])],
                          **({'skos:broader': {'@id': base + c['broader']}} if c['broader'] else {})} for c in d['concepts']]}
        (out / 'vocabulary.jsonld').write_text(json.dumps(jl, indent=1, ensure_ascii=False), encoding='utf-8')
        cat = {'@context': {'dcat': 'http://www.w3.org/ns/dcat#', 'dcterms': 'http://purl.org/dc/terms/'},
               '@id': m['site_url'] + 'data/catalogue.jsonld', '@type': 'dcat:Catalog', 'dcterms:title': m['title'] + ': sources',
               'dcterms:modified': m['as_of'], 'dcat:contactPoint': {'@type': 'http://www.w3.org/2006/vcard/ns#Kind', 'http://www.w3.org/2006/vcard/ns#hasURL': m['contact_form']},
               'dcat:resource': [{'@id': s['url'], '@type': 'dcat:Resource', 'dcterms:title': s['title'], 'dcterms:publisher': s['publisher'],
                                  'dcterms:type': s['type'], 'dcterms:description': s['note']} for s in d['sources']]}
        (out / 'catalogue.jsonld').write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding='utf-8')
        sm = ''.join(f'<url><loc>{m["site_url"]}{k}.html</loc><lastmod>{m["as_of"]}</lastmod></url>' for k, _, _ in NAV)
        (self.out / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding='utf-8')


def json_safe(v):
    return json.dumps(v, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--content', default=str(ROOT / 'content' / 'playbooks.yaml'))
    ap.add_argument('--out', default=str(ROOT / 'site'))
    a = ap.parse_args(argv)
    try:
        d = load(a.content)
    except ContentError as e:
        print('Content errors:\n' + str(e), file=sys.stderr)
        return 1
    bid = Site(d, a.out).build()
    print(f'Built {bid} into {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
