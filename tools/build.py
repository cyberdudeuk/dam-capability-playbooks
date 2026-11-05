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
import urllib.parse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
E = lambda s: html.escape(str(s if s is not None else ''), quote=True)


class ContentError(Exception):
    pass


# ---------------------------------------------------------------------------
# Load and validate: refuse to build on any broken reference
# ---------------------------------------------------------------------------
def load(path):
    path = Path(path)
    d = yaml.safe_load(path.read_text(encoding='utf-8'))
    extra = path.parent / 'frameworks.yaml'
    if extra.exists():
        f = yaml.safe_load(extra.read_text(encoding='utf-8'))
        d['rulebook'] = list(d.get('rulebook', [])) + list(f.pop('rulebook_more', []))
        d.update(f)
    anchors = path.parent / 'source-anchors.json'
    d['_anchors'] = json.loads(anchors.read_text())['anchors'] if anchors.exists() else {}
    validate(d)
    return d


def validate(d):
    errs, ids = [], {}

    def reg(i, where):
        if i in ids:
            errs.append(f'duplicate id {i} in {where} (also {ids[i]})')
        ids[i] = where
    for s in d['sources']: reg(s['id'], 'sources')
    for r in d['requirements']: reg(r['id'], 'requirements')
    for r in d['roles']: reg('role:' + r['code'], 'roles')
    for c in d['capabilities']:
        reg('cap:' + c['id'], 'capabilities')
        for st in c['stages']: reg(f"{c['id']}.{st['id']}", 'stages')
        for t in c.get('templates', []): reg(t['id'], 'templates')
    for c in d['concepts']: reg('c:' + c['id'], 'concepts')
    for l in d['library']: reg(l['id'], 'library')
    for x in d['interlocks']: reg(x['id'], 'interlocks')
    for p in d['personas']: reg('persona:' + p['id'], 'personas')
    for m in d['modules']: reg(m['id'], 'modules')
    src = {s['id'] for s in d['sources']}
    req = {r['id'] for r in d['requirements']}
    roles = {r['code'] for r in d['roles']}
    caps = {c['id'] for c in d['capabilities']}
    stages = {f"{c['id']}.{st['id']}" for c in d['capabilities'] for st in c['stages']}
    concepts = {c['id'] for c in d['concepts']}
    mods = {m['id'] for m in d['modules']}
    provs = {'V', 'P', 'O', 'S', 'K', 'U'}
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
        for k in ('in_brief', 'before_you_start', 'you_get'):
            if not c.get(k): errs.append(f"{c['id']}: missing {k}")
        for st in c['stages']:
            if st['id'] not in STAGE_ICONS: errs.append(f"{c['id']}.{st['id']}: no icon chosen for this stage")
            for rq in st.get('reqs', []):
                if rq not in req: errs.append(f"{c['id']}.{st['id']}: unknown requirement {rq}")
            for k in st['raci']:
                if k not in roles: errs.append(f"{c['id']}.{st['id']}: unknown role {k}")
            if not [k for k, v in st['raci'].items() if v == 'A']: errs.append(f"{c['id']}.{st['id']}: RACI has no accountable role")
        for rc in c['roles']:
            if rc not in roles: errs.append(f"{c['id']}: unknown role {rc}")
        # D-008: the portal's own service owner must never appear as an actor inside a playbook method
        for e in c.get('escalation', []):
            if e['who'].lower().startswith('service owner'): errs.append(f"{c['id']} {e['level']}: escalation names the portal's service owner, not a data role")
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
    for m in d['modules']:
        if m['level'] not in LEVELS: errs.append(f"{m['id']}: unknown level {m['level']}")
        if not m.get('outcomes') or not m.get('activities') or not m.get('check'): errs.append(f"{m['id']}: needs outcomes, activities and a check")
        aids = [a['id'] for a in m['activities']]
        if len(aids) != len(set(aids)): errs.append(f"{m['id']}: duplicate activity ids")
        for q in m['check']:
            if len(q['options']) < 2 or not (0 <= q['answer'] < len(q['options'])): errs.append(f"{m['id']}: bad question '{q['q']}'")
    for p in d['personas']:
        if p['role'] not in roles: errs.append(f"persona {p['id']}: unknown role {p['role']}")
        for mid in p['modules']:
            if mid not in mods: errs.append(f"persona {p['id']}: unknown module {mid}")
        if [j['stage'] for j in p['journey']] != JOURNEY_STAGES: errs.append(f"persona {p['id']}: journey stages must be {JOURNEY_STAGES}")
        for j in p['journey']:
            for t in j['tasks']:
                if 'p' in t and t['p'] not in stages: errs.append(f"persona {p['id']}: unknown stage {t['p']}")
                if 'm' in t and t['m'] not in mods: errs.append(f"persona {p['id']}: unknown module {t['m']}")
                if 'p' in t and not t.get('label'): errs.append(f"persona {p['id']}: task {t['p']} needs a label")
    # D-009: an unquoted comma in a YAML flow list silently splits one item into fragments
    lists = [(f"module {m['id']} outcomes", m['outcomes']) for m in d['modules']]
    for p in d['personas']:
        lists += [(f"persona {p['id']} {k}", p[k]) for k in ('goals', 'pains', 'design_for')]
    for c in d['capabilities']:
        lists += [(f"{c['id']} {k}", c[k]) for k in ('in_brief', 'before_you_start', 'you_get')]
    for x in d.get('domain_depth', []):
        lists.append((f"{x['id']} needed", x['needed']))
    for where, items in lists:
        for it in items:
            if len(str(it).split()) < 3:
                errs.append(f"{where}: '{it}' looks like a fragment; quote list items that contain commas")
    for x in d.get('domain_depth', []):
        if x['moscow'] not in ('Must', 'Should', 'Could', "Won't"): errs.append(f"{x['id']}: bad MoSCoW")
        for cp in x['caps']:
            if cp not in caps: errs.append(f"{x['id']}: unknown capability {cp}")
    rb = {x['id'] for x in d.get('rulebook', [])}
    if len(rb) != len(d.get('rulebook', [])): errs.append('duplicate rulebook ids')
    for x in d.get('rulebook', []):
        if x['prov'] not in ('V', 'S', 'K'): errs.append(f"{x['id']}: bad provenance")
        if not x['url'].startswith('https://'): errs.append(f"{x['id']}: url must be https")
        for cp in x['caps']:
            if cp not in caps: errs.append(f"{x['id']}: unknown capability {cp}")
    dd = {x['id'] for x in d.get('domain_depth', [])}
    for k, refs in (d.get('depth_refs') or {}).items():
        if k not in dd: errs.append(f"depth_refs: unknown theme {k}")
        for r in refs:
            if r not in rb: errs.append(f"depth_refs {k}: unknown rulebook entry {r}")
    sups = {x['id'] for x in d.get('supplements', [])}
    rule_ids = []
    for x in d.get('supplements', []):
        if x['dd'] not in dd: errs.append(f"{x['id']}: unknown theme {x['dd']}")
        if x['icon'] not in ICON_SET: errs.append(f"{x['id']}: unknown icon {x['icon']}")
        for r in x['refs']:
            if r not in rb: errs.append(f"{x['id']}: unknown rulebook entry {r}")
        for r in x['rules']:
            rule_ids.append(r['id'])
            if r['check'] not in DQKIT_CHECKS: errs.append(f"{r['id']}: check {r['check']} is not a dqkit check")
            if r['check'] == 'identifier' and r['params'].get('scheme') not in DQKIT_SCHEMES: errs.append(f"{r['id']}: unknown identifier scheme")
            if r['dimension'] not in ('completeness', 'uniqueness', 'consistency', 'timeliness', 'validity', 'accuracy'): errs.append(f"{r['id']}: dimension not one of the six")
        if not x['example'].startswith('Illustrative, synthetic'): errs.append(f"{x['id']}: example must be labelled illustrative and synthetic")
    if len(rule_ids) != len(set(rule_ids)): errs.append('duplicate sector rule ids')
    for q in d.get('applicability', []):
        for sp in q['sups']:
            if sp not in sups: errs.append(f"{q['id']}: unknown supplement {sp}")
    covered = {x['dd'] for x in d.get('supplements', [])}
    for x in d.get('domain_depth', []):
        if x['moscow'] == 'Must' and x['id'] not in covered: errs.append(f"{x['id']}: a Must-have theme has no supplement")
    pages_known = {k for k, _, _ in NAV} | {'contact', 'status', 'whats-new', 'all'}
    for r in d.get('design', {}).get('requirements', []):
        for c in r['checks']:
            if c not in KNOWN_CHECKS: errs.append(f"{r['id']}: unknown check {c}")
        for f in r['features']:
            if f not in pages_known: errs.append(f"{r['id']}: unknown feature page {f}")
    for x in d.get('standards', []):
        if x['status'] not in ('Met', 'Partly', 'Not yet'): errs.append(f"{x['id']}: bad status")
    validate_frameworks(d, errs, src, roles)
    if errs:
        raise ContentError('\n'.join(errs))


def validate_frameworks(d, errs, src, roles):
    """Version 1.4: capability requirements map, maturity, professions and change content."""
    if 'capmap' not in d:
        return
    rb = {x['id'] for x in d['rulebook']}
    anchors = d.get('_anchors', {})
    profs = {p['id'] for p in d['professions']['profs']}
    ddat = {r['id'] for r in d['professions']['roles']}
    skills = {s[1] for r in d['professions']['roles'] for s in r['skills']}
    personas = {p['id'] for p in d['personas']}
    crs = [c['id'] for c in d['capmap']]
    if len(crs) != len(set(crs)): errs.append('duplicate capability map ids')
    for c in d['capmap']:
        if c['flag'] not in FLAGS: errs.append(f"{c['id']}: flag must be E, I or N")
        if c['coverage'] not in ('Covered', 'Partial', 'New'): errs.append(f"{c['id']}: bad coverage")
        if c['cluster'] not in CLUSTERS: errs.append(f"{c['id']}: unknown cluster {c['cluster']}")
        if c['icon'] not in ICON_SET: errs.append(f"{c['id']}: unknown icon {c['icon']}")
        if c['flag'] in ('E', 'I') and not c['dam'] and not any(sg['flag'] == 'E' for sg in c['signposts']):
            errs.append(f"{c['id']}: an explicit or implicit capability needs a clause to point to")
        if c['flag'] == 'E' and not c['dam']: errs.append(f"{c['id']}: 'explicit' must point to the DAM Policy clause that states it")
        if c['dam'] and c['dam'] not in anchors.get('SRC-DAM', []): errs.append(f"{c['id']}: DAM Policy has no section #{c['dam']}")
        if not c['signposts']: errs.append(f"{c['id']}: needs at least one signpost")
        for sg in c['signposts']:
            if sg['doc'] not in src and sg['doc'] not in rb: errs.append(f"{c['id']}: unknown signpost document {sg['doc']}")
            if sg['flag'] not in FLAGS: errs.append(f"{c['id']}: bad signpost flag")
            if sg['a'] and sg['a'] not in anchors.get(sg['doc'], []): errs.append(f"{c['id']}: {sg['doc']} has no verified section #{sg['a']}")
        for t in c['dma']:
            if not 1 <= t <= 10: errs.append(f"{c['id']}: maturity topic {t} out of range")
        for k in c['skills']:
            if k not in skills: errs.append(f"{c['id']}: unknown skill {k}")
        for p in c['profs']:
            if p not in profs: errs.append(f"{c['id']}: unknown profession {p}")
    for p in d['professions']['profs']:
        if p['rb'] not in rb: errs.append(f"{p['id']}: unknown rulebook entry {p['rb']}")
    for m in d['professions']['persona_map']:
        if m['persona'] not in personas: errs.append(f"persona map: unknown persona {m['persona']}")
        for r in m['roles']:
            if r not in ddat: errs.append(f"persona map {m['persona']}: unknown role {r}")
        for x in m['learn'] + m['profs']:
            if x not in rb and x not in profs: errs.append(f"persona map {m['persona']}: unknown reference {x}")
    for st in d['professions']['learning']:
        for x in st['items']:
            if x not in rb: errs.append(f"learning route: unknown rulebook entry {x}")
    stages = {x['id'] for x in d['change']['stages']}
    if set(d['change']['touchpoints']) != stages: errs.append('change: every stage needs touchpoints')
    for x in d['change']['items']:
        if x['mode'] not in ('BAU', 'Change', 'Both'): errs.append(f"{x['id']}: bad mode")
        if x['stage'] not in stages: errs.append(f"{x['id']}: unknown stage")
        for r in x['roles']:
            if r not in roles: errs.append(f"{x['id']}: unknown role {r}")
        for r in x['refs']:
            if r not in rb: errs.append(f"{x['id']}: unknown rulebook entry {r}")
        for r in x['cr']:
            if r not in crs: errs.append(f"{x['id']}: unknown capability {r}")
    mt = d['maturity']
    if len(mt['topics']) != 10 or len(mt['levels']) != 5: errs.append('maturity: expected 10 topics and 5 levels')
    for st in mt['strands']:
        if len(st['levels']) != 5: errs.append(f"maturity strand {st['id']}: needs 5 level indicators")
        for r in st['cr']:
            if r not in crs: errs.append(f"maturity strand {st['id']}: unknown capability {r}")


FLAGS = {'E': ('Explicit', 'The text names this as a requirement or responsibility.'),
         'I': ('Implicit', 'The text depends on it to meet an explicit requirement but does not name it as one.'),
         'N': ('Inferred', 'Not in the text. This portal\'s judgement from good practice and adjacent rulebooks.')}
CLUSTERS = ['Direction and oversight', 'Core DAM capabilities', 'Data management enablers', 'Protection, ethics and trust', 'People and culture', 'Delivery, change and value']
CLUSTER_ICONS = dict(zip(CLUSTERS, ['compass', 'layers', 'settings-2', 'shield-check', 'users-round', 'workflow']))


# ---------------------------------------------------------------------------
# Icons (Lucide, ISC, vendored by tools/vendor_icons.py)
# ---------------------------------------------------------------------------
# Checks and identifier schemes supported by dqkit (Public Sector Data Quality Commons, dqkit/rules.py), so sector rules run as written
DQKIT_CHECKS = {'not_null', 'required_columns', 'unique', 'type', 'regex', 'in_set', 'range', 'not_future', 'compare', 'sum_max', 'freshness',
                'no_gaps', 'header_has_unit', 'not_unknown', 'group_disparity', 'identifier', 'outlier'}
DQKIT_SCHEMES = {'nhs_number', 'nino', 'uk_postcode', 'lei', 'uprn', 'gss_code', 'company_number', 'charity_number', 'school_urn', 'ods_code'}
KNOWN_CHECKS = {f"C-{i:02d}" for i in range(1, 25)} | {f'B-{i:02d}' for i in range(1, 14)} | {'HL-01', 'HL-02', 'T-VAL'}
ICON_SET = json.loads((ROOT / 'site_src' / 'icons.json').read_text())['icons']

STAGE_ICONS = {
    'mandate': 'scroll-text', 'frame': 'book-marked', 'assign': 'user-check', 'operate': 'settings-2', 'assure': 'clipboard-check',
    'mobilise': 'flag', 'discover': 'search', 'designate': 'stamp', 'own': 'key-round', 'describe': 'pencil-line',
    'publish': 'share-2', 'report': 'send', 'maintain': 'calendar-clock', 'identify': 'crosshair', 'define': 'ruler',
    'baseline': 'chart-column', 'prioritise': 'list-ordered', 'improve': 'wrench', 'sustain': 'activity', 'review': 'calendar-check',
}
ROLE_ICONS = {'CDO': 'building-2', 'COO': 'clipboard-list', 'BRD': 'gavel', 'OWN': 'key-round', 'IAO': 'lock-keyhole',
              'STW': 'user-cog', 'CUS': 'server', 'CAT': 'database', 'DQL': 'chart-line', 'DPO': 'scale', 'USR': 'user-search', 'PUB': 'users'}
CAP_ICONS = {'gov': 'shield-check', 'cat': 'library-big', 'dq': 'gauge'}
LEVELS = {'Foundation': 'award', 'Practitioner': 'graduation-cap', 'Advanced': 'milestone'}
JOURNEY_STAGES = ['Learn', 'Prepare', 'Do', 'Report', 'Improve']
STAGE_ROW_ICONS = {'Learn': 'graduation-cap', 'Prepare': 'clipboard-list', 'Do': 'wrench', 'Report': 'send', 'Improve': 'refresh-cw'}
ACTIVITY_ICONS = {'Read': 'book-open', 'Do': 'pencil-line', 'Reflect': 'lightbulb'}


def icon(name, cls='i'):
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{ICON_SET[name]}</svg>'


def tile(name, kind=''):
    return f'<span class="tile {kind}" aria-hidden="true">{icon(name)}</span>'


PROV_TEXT = {
    'V': 'Verified against the primary source',
    'P': 'Practitioner material from cross-government playbooks not yet published',
    'O': "This playbook's own synthesis of published guidance",
    'S': 'Found by web search; the site blocked automated checking, so open it before relying on it',
    'K': 'General knowledge, not checked against a source in this release',
    'U': 'Unconfirmed',
}


def prov(code, date=None):
    t = PROV_TEXT[code] + (f' on {date}' if code == 'V' and date else '')
    return f'<abbr class="prov {code}" title="{E(t)}">{code}<span class="visually-hidden">: {E(t)}</span></abbr>'


def table(cap_id, caption, headers, rows, cls=None, row_attrs=None, tbody_id=None):
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
        body.append(f'<tr{row_attrs[i] if row_attrs else ""}>' + ''.join(cells) + '</tr>')
    tb = f' id="{tbody_id}"' if tbody_id else ''
    return (f'<div class="table-wrap" role="region" aria-labelledby="{cap_id}" tabindex="0"><table>'
            f'<caption id="{cap_id}">{E(caption)}</caption><thead><tr>{th}</tr></thead><tbody{tb}>{"".join(body)}</tbody></table></div>')


def ul(items, raw=False, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<ul{c}>' + ''.join(f'<li>{i if raw else E(i)}</li>' for i in items) + '</ul>'


def slug(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


def progress_widget(ids, label, kind='bar'):
    """A progress readout; filled in by app.js from the viewer's own browser storage. Hidden without scripts."""
    return (f'<div class="progress js-only" data-progress-of="{E(" ".join(ids))}" data-total="{len(ids)}">'
            f'<span class="progress-label">{E(label)}</span>'
            f'<span class="bar" aria-hidden="true"><span class="fill"></span></span>'
            f'<span class="progress-text" aria-live="polite">0 of {len(ids)} done</span></div>')


def status_tag(ids):
    return f'<strong class="status js-only" data-status-of="{E(" ".join(ids))}">Not started</strong>'


def mark_done(pid, label='Mark this step as done'):
    return (f'<label class="mark js-only"><input type="checkbox" data-progress="{E(pid)}"> '
            f'<span>{E(label)}</span></label>')


# ---------------------------------------------------------------------------
# Colophon codes: QR (segno) and Code 128 barcode, drawn as paths
# ---------------------------------------------------------------------------
def qr_svg(text, label):
    import segno
    m = segno.make(text, error='m').matrix
    n, border, scale = len(m), 2, 3
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
    bits = barcode.get('code128', text).build()[0]
    w, h, q = 1.5, 46, 10
    rects, i = [], 0
    while i < len(bits):
        if bits[i] == '1':
            j = i
            while j < len(bits) and bits[j] == '1':
                j += 1
            rects.append(f'<rect x="{q + i * w:.1f}" y="0" width="{(j - i) * w:.1f}" height="{h}"/>')
            i = j
        else:
            i += 1
    width = len(bits) * w + 2 * q
    return (f'<svg role="img" aria-label="{E(label)}" viewBox="0 0 {width:.0f} {h}" width="{width:.0f}" height="{h}">'
            f'<rect width="{width:.0f}" height="{h}" fill="#ffffff"/><g fill="#0b0c0c">{"".join(rects)}</g></svg>')


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
NAV = [
    ('index', 'Home', 'house'), ('dam', 'The policy', 'landmark'), ('governance', 'Governance', 'shield-check'),
    ('cataloguing', 'Cataloguing', 'library-big'), ('quality', 'Quality', 'gauge'), ('sectors', 'Sectors', 'layers'), ('together', 'Joined up', 'workflow'),
    ('change', 'Delivery and change', 'construction'),
    ('capability-model', 'Capability model', 'radar'), ('professions', 'Professions and skills', 'briefcase'),
    ('personas', 'Your role', 'users-round'), ('learning', 'Learning', 'graduation-cap'), ('library', 'Library', 'library'),
    ('knowledge', 'Knowledge', 'network'), ('inclusion', 'Inclusion', 'heart-handshake'), ('about', 'About', 'info'),
]
# Grouped menus keep the global bar to about ten top-level destinations (build standard: use hubs before adding more)
NAV_GROUPS = {'Playbooks': ['governance', 'cataloguing', 'quality', 'sectors', 'together', 'change'],
              'Frameworks': ['capability-model', 'professions']}
NAV_GROUP_ICONS = {'Playbooks': 'book-open', 'Frameworks': 'grid-3x3'}
CAP_PAGE = {'gov': 'governance', 'cat': 'cataloguing', 'dq': 'quality'}
PAGE_DESC = {
    'together': 'How data governance, data cataloguing and data quality hand off to each other, with one set of roles and one yearly cycle.',
    'personas': 'Routes through the DAM capability playbooks for chief data officers, coordinators, data owners, stewards, catalogue managers and analysts.',
    'learning': 'Short learning modules on the DAM Policy, data governance, cataloguing and data quality, with outcomes, activities and checks.',
    'library': 'Guidance, standards, templates and tools for data governance, data cataloguing and data quality, with open data downloads.',
    'knowledge': 'Glossary, thesaurus, taxonomy, knowledge graph and data dictionary for data asset management in UK government.',
    'inclusion': 'Equality, diversity, inclusion and accessibility checks for data governance, data cataloguing and data quality work.',
    'about': 'Purpose, sources, open register, defect register, accessibility statement and build standard assessment for the DAM capability playbooks.',
    'contact': 'Ask a question, report a problem or suggest an improvement to the DAM capability playbooks using the contact form.',
    'status': 'Latest automated health check of the DAM capability playbooks: source currency, review date and page weight.',
    'sectors': 'Sector supplements for health, social care, geospatial, statistics, data sharing, AI and more: governance overlays, catalogue fields and quality rule libraries.',
    'capability-model': 'Every capability the DAM Policy and related guidance need, flagged explicit, implicit or inferred, with a data maturity model and self-assessment.',
    'professions': 'Government professions, Digital and Data capability framework roles, career pathways, skills and learning routes for data asset management.',
    'change': 'Embedding the DAM Policy in business as usual and in change programmes: business cases, assurance, legacy exits, contracts and handover.',
    'design': 'Theory of change, research plan, service blueprint, requirements traceability, architecture and Service Standard self-assessment for the portal.',
    'notices': 'Disclaimers, transparency notices, credits and full citations for every source used by the DAM capability playbooks.',
    'accessibility': 'Accessibility statement for the DAM capability playbooks, following the GOV.UK model statement for public sector websites.',
    'whats-new': 'Changes in each release of the Data Asset Management (DAM) capability playbooks, newest first.',
    '404': 'The page you were looking for could not be found on the DAM capability playbooks portal.',
}


class Site:
    def __init__(self, d, out):
        self.d, self.out, self.m = d, Path(out), d['meta']
        self.src = {s['id']: s for s in d['sources']}
        self.req = {r['id']: r for r in d['requirements']}
        self.roles = {r['code']: r for r in d['roles']}
        self.caps = {c['id']: c for c in d['capabilities']}
        self.concepts = {c['id']: c for c in d['concepts']}
        self.mods = {m['id']: m for m in d['modules']}
        self.stage = {f"{c['id']}.{st['id']}": (c, st) for c in d['capabilities'] for st in c['stages']}
        self.rb = {x['id']: x for x in d.get('rulebook', [])}
        self.cr = {c['id']: c for c in d.get('capmap', [])}
        self.prof = {p['id']: p for p in d['professions']['profs']} if 'professions' in d else {}
        self.search, self.build_id = [], None
        sp = ROOT / 'build' / 'status.json'
        self.status = json.loads(sp.read_text()) if sp.exists() else None

    # -- helpers --------------------------------------------------------------
    def gloss(self, text, used=None):
        """Escape text, then link the first mention of selected glossary terms with an accessible tooltip."""
        out = E(text)
        used = used if used is not None else set()
        skip = {'purpose', 'return', 'role', 'recipe', 'metadata', 'raci', 'exception', 'charter'}
        for c in self.d['concepts']:
            if c['id'] in skip or c['id'] in used:
                continue
            for label in [c['term']] + list(c.get('alt') or []):
                if len(label) < 4:
                    continue
                m = re.compile(r'(?<![\w>/-])(' + re.escape(E(label)) + r')(?![\w<])', re.I).search(out)
                if m and not self._inside_tag(out, m.start()):
                    a = (f'<a class="term" href="knowledge.html#c-{c["id"]}" data-tip="{E(c["term"] + ": " + c["def"])}">{m.group(1)}</a>')
                    out = out[:m.start()] + a + out[m.end():]
                    used.add(c['id'])
                    break
        return out

    @staticmethod
    def _inside_tag(s, pos):
        lt, gt = s.rfind('<', 0, pos), s.rfind('>', 0, pos)
        if lt > gt:
            return True
        return s.rfind('<a ', 0, pos) > s.rfind('</a>', 0, pos)

    def src_link(self, sid):
        if not sid:
            return 'Practitioner material (not yet published)'
        s = self.src[sid]
        return f'<a href="{E(s["url"])}">{E(s["title"])}</a>{prov(s["prov"], self.m["verified_on"])}'

    def req_links(self, ids):
        return ' '.join(f'<a class="pill {self.req[i]["cap"]}" href="dam.html#{i}">{E(i)}</a>' for i in ids)

    def stage_url(self, ref):
        c, st = self.stage[ref]
        return f'{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}'

    def stage_ref(self, ref):
        c, st = self.stage[ref]
        return f'<a class="pill {c["id"]}" href="{self.stage_url(ref)}">{E(c["short"])} {st["n"]}: {E(st["name"])}</a>'

    def mod_units(self, mid):
        return [f'{mid}.{a["id"]}' for a in self.mods[mid]['activities']]

    def persona_units(self, p):
        units = []
        for j in p['journey']:
            for t in j['tasks']:
                units.append(t['p'] if 'p' in t else 'mod:' + t['m'])
        return units

    def hero(self, ic, caption, title, lede, kind='', brief=None, meta=None):
        b = ''
        if brief:
            b = f'<div class="in-brief" role="note" aria-label="In brief"><h2 class="ib-h">{icon("list-checks")} In brief</h2>{ul(brief)}</div>'
        mt = ''
        if meta:
            mt = '<ul class="hero-meta">' + ''.join(f'<li>{icon(i)}<span>{E(t)}</span></li>' for i, t in meta) + '</ul>'
        return (f'<div class="hero {kind}">{tile(ic, "lg " + kind)}<div><p class="caption">{E(caption)}</p><h1>{E(title)}</h1>'
                f'<p class="lede">{lede}</p>{mt}</div></div>{b}')

    def add_search(self, title, kind, url, snippet=''):
        self.search.append({'t': title, 'k': kind, 'u': url, 's': snippet[:160]})

    # -- page shell ------------------------------------------------------------
    def page(self, key, title, body, drawer=None, desc='', crumbs=None, jsonld=None, extra_json=None):
        m = self.m
        canonical = m['site_url'] + ('' if key == 'index' else f'{key}.html')
        seo_desc = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', desc or PAGE_DESC.get(key) or m['subtitle'])).strip()
        if len(seo_desc) > 158:
            seo_desc = seo_desc[:155].rsplit(' ', 1)[0] + '...'
        if key == 'index':
            title = m['short_title'] + ': governance, cataloguing and quality'
        nav, done = '', set()
        for k, lbl, ic in NAV:
            grp = next((g for g, members in NAV_GROUPS.items() if k in members), None)
            if grp and grp in done:
                continue
            if grp:
                done.add(grp)
                members = [x for x in NAV if x[0] in NAV_GROUPS[grp]]
                cur = key in NAV_GROUPS[grp]
                sub = ''.join(f'<li><a href="{mk}.html"{" aria-current=" + chr(34) + "page" + chr(34) if mk == key else ""}>{icon(mic)}<span>{E(ml)}</span></a></li>' for mk, ml, mic in members)
                nav += (f'<li class="group{" current" if cur else ""}"><button type="button" aria-expanded="false">{icon(NAV_GROUP_ICONS[grp])}<span>{E(grp)}</span>{icon("chevron-down")}</button>'
                        f'<ul aria-label="{E(grp)}">{sub}</ul></li>')
            else:
                nav += f'<li><a href="{k}.html"{" aria-current=" + chr(34) + "page" + chr(34) if k == key else ""}>{icon(ic)}<span>{E(lbl)}</span></a></li>'
        drawer_html, toggle = '', ''
        if drawer:
            groups = []
            for g in drawer:
                items = ''.join(
                    f'<li><a href="#{E(it["id"])}">{icon(it.get("icon", "chevron-right"))}<span>{E(it["label"])}</span>'
                    + (f'<span class="count" aria-label="{it["count"]} items">{it["count"]}</span>' if it.get('count') else '')
                    + ('<span class="flag">New</span>' if it.get('new') else '') + '</a></li>' for it in g['items'])
                groups.append(f'<details open><summary>{icon(g.get("icon", "list-checks"))}<span>{E(g["label"])}</span>'
                              f'<span class="count" aria-label="{len(g["items"])} sections">{len(g["items"])}</span></summary><ul>{items}</ul></details>')
            drawer_html = f'<nav class="drawer" id="drawer" aria-label="On this page"><h2>{icon("panel-left")} On this page</h2>{"".join(groups)}</nav>'
            toggle = ('<button type="button" class="switch" id="drawer-toggle" role="switch" aria-checked="true" aria-controls="drawer" hidden>'
                      '<span class="track" aria-hidden="true"><span class="knob"></span></span>Page contents</button>')
        crumb_html = ''
        if crumbs:
            crumb_html = ('<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="index.html">Home</a></li>'
                          + ''.join(f'<li>{E(c)}</li>' for c in crumbs) + '</ol></nav>')
        ld = {'@context': 'https://schema.org', '@type': 'WebPage', 'name': f'{title} - {m["title"]}',
              'identifier': f'{m["id"]}-{key}', 'version': m['version'], 'dateModified': m['as_of'],
              'isPartOf': {'@type': 'WebSite', 'name': m['title'], 'url': m['site_url']},
              'license': m['licence_content_url'], 'inLanguage': 'en-GB'}
        if jsonld:
            ld.update(jsonld)
        ld['url'] = canonical
        ld['description'] = seo_desc
        if crumbs:
            ld['breadcrumb'] = {'@type': 'BreadcrumbList', 'itemListElement': [{'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': m['site_url']}]
                                + [{'@type': 'ListItem', 'position': i + 2, 'name': c} for i, c in enumerate(crumbs)]}
        extra = ''.join(f'<script type="application/json" id="{k}">{json_safe(v)}</script>' for k, v in (extra_json or {}).items())
        display = f'''<div class="display-panel" id="display-panel" hidden>
<h2 class="dp-h">{icon("sliders-horizontal")} Display options</h2>
<fieldset><legend>Text size</legend>
<label><input type="radio" name="dp-text" value=""> Standard</label><label><input type="radio" name="dp-text" value="l"> Large</label><label><input type="radio" name="dp-text" value="xl"> Largest</label></fieldset>
<fieldset><legend>Line spacing</legend>
<label><input type="radio" name="dp-space" value=""> Standard</label><label><input type="radio" name="dp-space" value="wide"> Wider</label></fieldset>
<fieldset><legend>Colours</legend>
<label><input type="radio" name="dp-theme" value=""> Match my device</label><label><input type="radio" name="dp-theme" value="light"> Light</label><label><input type="radio" name="dp-theme" value="dark"> Dark</label></fieldset>
<p class="hint">Your choices are kept in this browser only.</p></div>'''
        return f'''<!DOCTYPE html>
<html lang="en-GB" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; object-src 'none'">
<meta name="referrer" content="no-referrer">
<title>{E(title)} - {E(m["title"])}</title>
<meta name="description" content="{E(seo_desc)}">
<meta name="robots" content="{"noindex" if key == "404" else "index, follow"}">
<link rel="canonical" href="{E(canonical)}">
<link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
<link rel="icon" href="assets/favicon-32.png" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<meta name="theme-color" content="#1d70b8">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{E(m["title"])}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(seo_desc)}">
<meta property="og:url" content="{E(canonical)}">
<meta property="og:image" content="{E(m["site_url"])}assets/og-image.png">
<meta property="og:image:alt" content="{E(m["title"])}">
<meta property="og:locale" content="en_GB">
<meta name="twitter:card" content="summary_large_image">
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
<div class="mast-in"><a class="name" href="index.html"><img class="brand-mark" src="assets/favicon.svg" alt="" width="36" height="36"><span>{E(m["title"])}</span></a>
<div class="mast-tools">
<button type="button" data-open-search hidden aria-haspopup="dialog">{icon("search")}<span>Search</span> <kbd>Ctrl K</kbd></button>
<button type="button" id="display-toggle" aria-expanded="false" aria-controls="display-panel" hidden>{icon("a-large-small")}<span>Display options</span></button></div></div>
{display}
</header>
<div class="banner"><strong class="tag">Prototype</strong>This is not an official GOV.UK service or published guidance. Where it repeats GDS guidance, the GOV.UK page is the authority. <a href="contact.html">Use the contact form</a> to tell us what you think.</div>
<nav class="gbar" id="gbar" aria-label="Portal sections"><ul class="top">{nav}<li class="more" hidden><button type="button" aria-expanded="false">{icon("chevron-down")}More sections</button><ul></ul></li></ul></nav>
<div class="wrap">
{drawer_html}
<main id="main" tabindex="-1">
{crumb_html}
<div class="toolbar">{toggle}</div>
{body}
{self.edit_links(key, title)}
</main>
</div>
{self.footer()}
<div class="palette" id="palette" hidden role="dialog" aria-modal="true" aria-labelledby="palette-title">
<div class="palette-box"><h2 id="palette-title" class="visually-hidden">Search the playbooks</h2>
<label for="palette-input" class="visually-hidden">Search</label>
<input id="palette-input" type="search" autocomplete="off" placeholder="Search steps, requirements, terms, modules" aria-controls="palette-list">
<p id="palette-status" class="visually-hidden" aria-live="polite"></p>
<ul id="palette-list" role="listbox" aria-label="Results"></ul>
<p><small>Use the up and down arrows to move, Enter to open and Escape to close.</small></p></div></div>
<script src="assets/search-index.js"></script>
{extra}
<script src="assets/app.js"></script>
</body>
</html>
'''

    def edit_links(self, key, title):
        if key == '404':
            return ''
        m = self.m
        gh = f'https://github.com/{m["repo"]}'
        q = urllib.parse.urlencode({'template': 'content-error.yml', 'title': f'[Page] {title}', 'page': m['site_url'] + f'{key}.html'})
        fb = urllib.parse.urlencode({'template': 'feedback.yml', 'title': f'[Feedback] {title}', 'page': m['site_url'] + f'{key}.html'})
        meta = (f'<p class="page-meta">{icon("info")}Page owner: the portal\'s service owner (a role) · Published 5 November 2026 · '
                f'Last updated {E(m["as_of"])} · Next review {E(m["review"])}</p>')
        return (meta + f'<p class="useful"><a href="{gh}/issues/new?{E(fb)}">{icon("message-square-text")}Was this page useful? Tell us</a></p>'
                f'<nav class="edit-links" aria-label="Help improve this page">'
                f'<a href="{gh}/issues/new?{E(q)}">{icon("message-square-text")}Report a problem with this page</a>'
                f'<a href="{gh}/edit/main/content/playbooks.yaml">{icon("pencil-line")}Suggest a change</a>'
                f'<a href="{gh}/commits/main/content/playbooks.yaml">{icon("clock")}See the change history</a>'
                f'<a href="{gh}/discussions">{icon("users")}Ask the community</a></nav>')

    def footer(self):
        m = self.m
        return f'''<footer class="site" id="colophon">
<div class="cols">
<div><h2>{icon("info")} About this portal</h2>
<p>{E(m["status"])}</p>
<p>Written with help from an AI assistant (Claude). Every fact is labelled with where it came from, and a person reviews each release before it is published.</p>
<ul class="foot-links"><li><a href="accessibility.html">Accessibility statement</a></li><li><a href="notices.html">Disclaimers, credits and citations</a></li><li><a href="design.html">Service design</a></li><li><a href="status.html">Status and health</a></li><li><a href="whats-new.html">What's new</a></li><li><a href="about.html#provenance">How sources are labelled</a></li><li><a href="about.html#privacy">Privacy</a></li><li><a href="about.html#open">Open register</a></li></ul></div>
<div><h2>{icon("message-square-text")} Contact</h2>
<p><a href="contact.html">Use the contact form</a> to ask a question, report a problem or suggest an improvement.</p>
<p>{E(m["contact_note"])}</p></div>
<div><h2>{icon("file-text")} Licence and version</h2>
<p>Content: <a href="{E(m["licence_content_url"])}">{E(m["licence_content"])}</a>, except where stated. Code: {E(m["licence_code"])}. Icons: Lucide (ISC).</p>
<p>{E(self.d["attribution_statement"])}</p>
<p>Version {E(m["version"])}, as of {E(m["as_of"])}, next review {E(m["review"])}. Build {E(self.build_id)}.</p>
<div class="codes">{self.codes}</div></div>
</div>
</footer>'''

    # -- build ---------------------------------------------------------------------
    def build(self):
        d, m = self.d, self.m
        h = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode())
        for f in sorted((ROOT / 'site_src').glob('*')) + [Path(__file__)]:
            h.update(f.read_bytes())
        self.build_id = f'{m["id"]}-{m["version"]}-{h.hexdigest()[:8].upper()}'
        self.codes = (f'<figure>{barcode_svg(self.build_id, "Barcode of build identifier " + self.build_id)}<figcaption>{E(self.build_id)}</figcaption></figure>'
                      f'<figure>{qr_svg(m["site_url"], "QR code linking to " + m["site_url"])}<figcaption>Portal address</figcaption></figure>')
        self.collect_search()
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / 'assets').mkdir(parents=True)
        (self.out / 'data').mkdir()
        for f in ('style.css', 'app.js', 'favicon.svg'):
            shutil.copy(ROOT / 'site_src' / f, self.out / 'assets' / f)
        make_images(self.out / 'assets', m)
        wk = self.out / '.well-known'
        wk.mkdir()
        sec = (f'Contact: https://github.com/{m["repo"]}/security/advisories/new\n'
               f'Policy: https://github.com/{m["repo"]}/blob/main/SECURITY.md\n'
               f'Expires: 2027-11-05T00:00:00.000Z\nPreferred-Languages: en\nCanonical: {m["site_url"]}.well-known/security.txt\n')
        (wk / 'security.txt').write_text(sec)
        (self.out / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nDisallow: /404.html\nSitemap: {m["site_url"]}sitemap.xml\n')
        pages = {'index': self.p_index, 'dam': self.p_dam, 'governance': lambda: self.p_cap('gov'),
                 'cataloguing': lambda: self.p_cap('cat'), 'quality': lambda: self.p_cap('dq'), 'together': self.p_together,
                 'personas': self.p_personas, 'learning': self.p_learning, 'library': self.p_library, 'knowledge': self.p_knowledge,
                 'inclusion': self.p_inclusion, 'sectors': self.p_sectors, 'capability-model': self.p_model,
                 'professions': self.p_professions, 'change': self.p_change, 'about': self.p_about, 'contact': self.p_contact, 'status': self.p_status,
                 'whats-new': self.p_whats_new, 'design': self.p_design, 'notices': self.p_notices,
                 'accessibility': self.p_accessibility, '404': self.p_404}
        for k, fn in pages.items():
            (self.out / f'{k}.html').write_text(fn(), encoding='utf-8')
        mods = {mm['id']: self.mod_units(mm['id']) for mm in d['modules']}
        (self.out / 'assets' / 'search-index.js').write_text(
            'window.DCP_INDEX=' + json_safe(self.search) + ';\nwindow.DCP_MODULES=' + json_safe(mods) + ';\n', encoding='utf-8')
        self.exports()
        (self.out / '.nojekyll').write_text('')
        return self.build_id

    def collect_search(self):
        self.search = []
        for k, lbl, _ in NAV:
            self.add_search(lbl, 'Page', f'{k}.html')
        self.add_search('Contact form', 'Page', 'contact.html', 'Ask a question, report a problem')
        for c in self.d['capabilities']:
            p = CAP_PAGE[c['id']]
            for st in c['stages']:
                self.add_search(f'{c["short"]} step {st["n"]}: {st["name"]}', f'{c["name"]} step', f'{p}.html#{c["id"]}-{st["id"]}', st['goal'] + ' ' + ' '.join(st['steps']))
            for t in c.get('templates', []):
                self.add_search(t['name'], f'{c["name"]} template', f'{p}.html#{t["id"]}', ' '.join(t['fields']))
        for r in self.d['requirements']:
            self.add_search(f'{r["id"]} ({r["strength"]})', 'Policy requirement', f'dam.html#{r["id"]}', r['text'])
        for c in self.d['concepts']:
            self.add_search(c['term'], 'Glossary term', f'knowledge.html#c-{c["id"]}', c['def'] + ' ' + ' '.join(c.get('alt') or []))
        for r in self.d['roles']:
            self.add_search(r['name'], 'Role', f'together.html#role-{r["code"]}', r['text'])
        for l in self.d['library']:
            self.add_search(l['title'], f'Library: {l["type"]}', f'library.html#{l["id"]}', l.get('note', ''))
        for p in self.d['personas']:
            self.add_search(p['title'], 'Your role: route and learning journey', f'personas.html#persona-{p["id"]}', p['summary'])
        for mm in self.d['modules']:
            self.add_search(f'{mm["id"]} {mm["title"]}', f'Learning module ({mm["level"]})', f'learning.html#{mm["id"]}', ' '.join(mm['outcomes']))
        for x in self.d['supplements']:
            self.add_search(x['title'], 'Sector supplement', f'sectors.html#{x["id"]}', x['summary'])
            for r in x['rules']:
                self.add_search(f'{r["id"]} {r["rule"]}', f'{x["title"]} quality rule', f'sectors.html#{r["id"]}', r['element'])
        for x in self.d['rulebook']:
            self.add_search(x['title'], f'Rulebook: {x["group"]}', f'dam.html#{x["id"]}', x['why'])
        for x in self.d['findings']:
            self.add_search(f'{x["id"]} {x["title"]}', 'Verification finding', f'about.html#{x["id"]}', x['detail'])
        for x in self.d['design']['requirements']:
            self.add_search(f'{x["id"]} {x["text"]}', 'Portal requirement', f'design.html#{x["id"]}', '')
        for o in self.d['open_register']:
            self.add_search(o['id'], 'Open register', f'about.html#{o["id"]}', o['item'])
        for c in self.d.get('capmap', []):
            self.add_search(f'{c["id"]} {c["name"]}', f'Capability ({FLAGS[c["flag"]][0].lower()})', f'capability-model.html#{c["id"]}', c['note'])
        for t in self.d.get('maturity', {}).get('topics', []):
            self.add_search(f'Maturity topic {t["n"]}: {t["name"]}', 'Data maturity model', 'capability-model.html#cm-maturity', '')
        for r in self.d.get('professions', {}).get('roles', []):
            self.add_search(r['title'], 'Career pathway', f'professions.html#role-{r["id"]}', ' '.join(s[0] for s in r['skills']))
        for p in self.d.get('professions', {}).get('profs', []):
            self.add_search(p['name'], 'Profession', f'professions.html#{p["id"]}', p['why'])
        for x in self.d.get('change', {}).get('items', []):
            self.add_search(f'{x["id"]} {x["title"]}', f'Delivery and change ({x["mode"]})', f'change.html#{x["id"]}', x['why'])

    def counts(self):
        d = self.d
        return {'reqs': len(d['requirements']), 'must': sum(1 for r in d['requirements'] if r['strength'] == 'must'),
                'stages': sum(len(c['stages']) for c in d['capabilities']),
                'templates': sum(len(c.get('templates', [])) for c in d['capabilities']),
                'concepts': len(d['concepts']), 'library': len(d['library']), 'sources': len(d['sources']),
                'verified': sum(1 for s in d['sources'] if s['prov'] == 'V'), 'modules': len(d['modules']),
                'minutes': sum(mm['minutes'] for mm in d['modules'])}

    # -- pages -----------------------------------------------------------------------
    def p_index(self):
        d, m, n = self.d, self.m, self.counts()
        personas = ''.join(
            f'<li class="persona-card"><a href="personas.html#persona-{p["id"]}">{tile(p["icon"], "role")}<span class="pc-body"><strong>{E(p["title"])}</strong>'
            f'<span>{E(p["summary"])}</span></span>{icon("arrow-right", "i go")}</a>{progress_widget(self.persona_units(p), "Your route")}</li>' for p in d['personas'])
        caps = ''
        for c in d['capabilities']:
            p = CAP_PAGE[c['id']]
            sids = [f'{c["id"]}.{st["id"]}' for st in c['stages']]
            caps += (f'<div class="card cap {c["id"]}"><div class="card-head">{tile(CAP_ICONS[c["id"]], c["id"])}<h3><a href="{p}.html">{E(c["name"])}</a></h3></div>'
                     f'<p class="q">{E(c["question"])}</p><p>{self.gloss(c["purpose"])}</p>'
                     f'<p class="stat"><span class="big">{len(c["stages"])}</span> steps</p>{progress_widget(sids, "Steps done")}'
                     f'<p><a class="btn-link" href="{p}.html#method">{icon("play")}Start the step by step</a></p></div>')
        how = ''.join(f'<li>{tile(ic, "step")}<div><h3>{E(h)}</h3><p>{E(t)}</p></div></li>' for ic, h, t in [
            ('users-round', '1. Choose your role', 'Each role has its own route through the three capabilities, with the steps in the order you need them.'),
            ('graduation-cap', '2. Learn what you need', f'{n["modules"]} short modules, about {n["minutes"]} minutes in total, each with a quick check of understanding.'),
            ('list-checks', '3. Follow the steps and track progress', 'Mark steps as done. Your progress shows on your route and on each playbook, in this browser only.')])
        body = f'''<div class="hero home">{tile("library-big", "lg")}<div><p class="caption">Data asset management (DAM) policy</p><h1>{E(m["title"])}</h1>
<p class="lede">Practical guidance for people who govern, catalogue and manage the quality of critical data assets in UK government departments and arm's length bodies.</p></div></div>
<div class="in-brief" role="note" aria-label="In brief"><h2 class="ib-h">{icon("list-checks")} In brief</h2>
<ul><li>The DAM Policy asks every department and arm's length body to identify, describe, own and manage the quality of its critical data assets.</li>
<li>Three capabilities make that possible: data governance, data cataloguing and data quality. This portal puts them side by side.</li>
<li>It is more detailed than GOV.UK guidance and written for specialists. GOV.UK remains the authority on what the policy requires.</li></ul></div>
<h2 id="role">{icon("users-round")} Start from your role</h2>
<ul class="persona-grid">{personas}</ul>
<h2 id="how">{icon("route")} How the playbooks work</h2>
<ol class="how">{how}</ol>
<h2 id="capabilities">{icon("layers")} The three capabilities</h2>
<div class="cards three">{caps}</div>
<h2 id="also">{icon("compass")} Also useful</h2>
<div class="cards">
<div class="card">{tile("landmark")}<h3><a href="dam.html">What the policy requires</a></h3><p>{n["reqs"]} requirements traced to GOV.UK guidance, {n["must"]} of them 'must', each linked to the step that meets it.</p></div>
<div class="card">{tile("workflow")}<h3><a href="together.html">How the three join up</a></h3><p>One set of roles, {len(d["interlocks"])} hand-offs and one yearly cycle, so each fact is recorded once.</p></div>
<div class="card">{tile("radar")}<h3><a href="capability-model.html">Capability model</a></h3><p>Every capability the policy and related guidance need, flagged explicit, implicit or inferred, with a maturity self-assessment.</p></div>
<div class="card">{tile("construction")}<h3><a href="change.html">Delivery and change</a></h3><p>Build the policy into business cases, assurance, legacy exits, contracts and handover to business as usual.</p></div>
<div class="card">{tile("briefcase")}<h3><a href="professions.html">Professions and skills</a></h3><p>Career pathways, skills and learning routes for each role in the policy.</p></div>
<div class="card">{tile("heart-handshake")}<h3><a href="inclusion.html">Inclusive data practice</a></h3><p>Equality, inclusion and accessibility checks for each capability.</p></div>
<div class="card">{tile("search")}<h3>Search everything</h3><p>Press Ctrl and K, or the forward slash key, to search steps, requirements, terms and modules.</p></div></div>
<div class="js-only progress-reset"><h2 id="your-progress">{icon("activity")} Your progress</h2><p>Progress is kept in this browser only. Nothing is sent anywhere.</p>
<button type="button" class="btn secondary" data-progress-reset>{icon("rotate-ccw")}Clear my progress</button></div>'''
        drawer = [{'label': 'Home', 'icon': 'house', 'items': [
            {'id': 'role', 'label': 'Start from your role', 'icon': 'users-round', 'count': len(d['personas'])},
            {'id': 'how', 'label': 'How the playbooks work', 'icon': 'route', 'count': 3},
            {'id': 'capabilities', 'label': 'The three capabilities', 'icon': 'layers', 'count': 3},
            {'id': 'also', 'label': 'Also useful', 'icon': 'compass', 'count': 4}]}]
        return self.page('index', 'Home', body, drawer, jsonld={'about': ['Data governance', 'Data cataloguing', 'Data quality']})

    def p_dam(self):
        d = self.d
        rows, attrs = [], []
        for r in d['requirements']:
            c = self.caps[r['cap']]
            met = ' '.join(f'<a class="pill {cc["id"]}" href="{CAP_PAGE[cc["id"]]}.html#{cc["id"]}-{st["id"]}">{E(cc["short"])} {st["n"]}</a>'
                           for cc in d['capabilities'] for st in cc['stages'] if r['id'] in st.get('reqs', []))
            rows.append([f'<span id="{r["id"]}">{E(r["id"])}</span>', f'<span class="strength {r["strength"]}">{E(r["strength"])}</span>',
                         f'<a class="pill {c["id"]}" href="{CAP_PAGE[c["id"]]}.html">{E(c["short"])}</a>',
                         self.gloss(r['text']) + prov(r['prov'], self.m['verified_on']), self.src_link(r['src']),
                         met or 'No step yet (see the open register)'])
            attrs.append(f' data-item data-cap="{r["cap"]}" data-strength="{r["strength"]}"')
        filt = f'''<div class="filters" data-filter="req-table" role="group" aria-label="Filter requirements">
<div><label for="f-cap">Capability</label><select id="f-cap" name="cap"><option value="">All</option>{"".join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in d["capabilities"])}</select></div>
<div><label for="f-str">Strength</label><select id="f-str" name="strength"><option value="">All</option>{"".join(f'<option>{s}</option>' for s in ["must", "should", "method", "gap"])}</select></div>
<div><label for="f-q">Contains</label><input id="f-q" type="search" name="q"></div>
<p class="count-out" aria-live="polite"></p></div>'''
        tl = ''.join(f'<li class="{E(t["kind"])}"><strong>{E(t["when"])}</strong> {E(t["what"])}{prov(t["prov"])}</li>' for t in d['timeline'])
        sup = ''.join(f'<li>{tile("hand-helping", "sm")}<div><strong>{E(s["name"])}</strong>{prov(s["prov"])}<br>{E(s["detail"])}</div></li>' for s in d['support'])
        tbl = table('t-reqs', 'Policy requirements and the steps that meet them', ['ID', 'Strength', 'Capability', 'Requirement', 'Source', 'Met by'], rows, row_attrs=attrs, tbody_id='req-table')
        musts = {c['id']: sum(1 for r in d['requirements'] if r['cap'] == c['id'] and r['strength'] == 'must') for c in d['capabilities']}
        mustcards = ''.join(f'<div class="stat-card {c["id"]}">{tile(CAP_ICONS[c["id"]], c["id"])}<span class="big">{musts[c["id"]]}</span><span>&#39;must&#39; requirements met by {E(c["name"].lower())}</span></div>' for c in d['capabilities'])
        body = self.hero('landmark', 'The spine of the playbooks', 'What the DAM Policy requires',
                         f'What the <a href="{E(self.src["SRC-DAM"]["url"])}">data asset management policy in government</a> and its linked guidance require, which capability meets each requirement, and which step does the work.',
                         brief=['The policy applies to UK government departments and their arm\'s length bodies. It is optional for public corporations and does not apply to councils.',
                                'In-scope assets are classified OFFICIAL, critical across government and within your own ownership.',
                                'You must catalogue and report them, review the records every year, name an owner for each and have a data quality action plan.'])
        body += f'''<div class="stat-row">{mustcards}</div>
<h2 id="scope">{icon("target")} Who it applies to and what is in scope</h2>
<div class="inset"><p><strong>Who.</strong> UK government departments and their arm's length bodies, including executive agencies, non-departmental public bodies and non-ministerial departments. It is optional for public corporations and does not apply to councils. The devolved governments have their own data sharing governance{prov("V", self.m["verified_on"])}.</p>
<p><strong>What.</strong> {E(self.req["DAM-R01"]["text"])}</p></div>
<h2 id="requirements">{icon("list-checks")} Requirements</h2>
<p>'Must' and 'should' follow the wording of the source. 'Method' is a prescribed technique. 'Gap' means the source promises something it does not yet set out.</p>
{filt}{tbl}
<h2 id="accountability">{icon("users")} Who is accountable</h2>
{table("t-acc", "Accountability under the policy", ["Body", "Responsibility"], [
            ["GDS", "Sets guidance and standards; develops the discoverability service; works with organisations to prioritise assets with proven reuse value"],
            ["Chief Data Officer Council", "Oversees implementation"], ["Chief data officer of each organisation", "Implements the policy in the organisation"],
            ["Minister for Digital Government and Data", "Writes to ministers each year on progress"],
            ["Departments", "Identify and report assets, provide metadata, coordinate and assure ALB returns"],
            ["Arm's length bodies", "Identify and report in-scope assets with their department"], ["Named data owners", "Accountable for decisions about each asset"]])}
<p>Source: {self.src_link("SRC-DAM")}</p>
<h2 id="timeline">{icon("calendar-clock")} Rollout and reporting dates</h2>
<div class="warning" role="note">{icon("triangle-alert")}<span>These dates come from practitioner material, not a public GOV.UK page. Check them before you rely on them (open item OR-07).</span></div>
<ol class="timeline">{tl}</ol>
<h2 id="support">{icon("hand-helping")} Support available</h2>
<ul class="icon-list">{sup}</ul>
<h2 id="rulebook">{icon("scale")} Related policies, standards, legislation and rulebooks</h2>
<p>Other government and public sector rules that apply alongside the DAM Policy. Each link was checked on {E(self.m["verified_on"])}: V means the page was fetched and its title confirmed; S means the site blocked automated checking, so open it before relying on it.</p>
<div class="filters" data-filter="rb-list" role="group" aria-label="Filter the rulebook"><div><label for="r-cap">Capability</label><select id="r-cap" name="cap"><option value="">All</option><option value="gov">Data governance</option><option value="cat">Data cataloguing</option><option value="dq">Data quality</option></select></div>
<div><label for="r-q">Contains</label><input id="r-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>
{self.rulebook_html(d["rulebook"], "rb-list")}'''
        drawer = [{'label': 'The policy', 'icon': 'landmark', 'items': [
            {'id': 'scope', 'label': 'Who and what is in scope', 'icon': 'target'},
            {'id': 'requirements', 'label': 'Requirements', 'icon': 'list-checks', 'count': len(d['requirements'])},
            {'id': 'accountability', 'label': 'Who is accountable', 'icon': 'users', 'count': 7},
            {'id': 'timeline', 'label': 'Rollout and reporting dates', 'icon': 'calendar-clock', 'count': len(d['timeline'])},
            {'id': 'support', 'label': 'Support available', 'icon': 'hand-helping', 'count': len(d['support'])},
            {'id': 'rulebook', 'label': 'Related rulebooks', 'icon': 'scale', 'count': len(d['rulebook']), 'new': True}]}]
        return self.page('dam', 'What the DAM Policy requires', body, drawer, crumbs=['The policy'], desc='What the DAM Policy requires and which capability meets it')

    def raci_table(self, c, tid):
        codes = c['roles']
        rows = [[f'<a href="#{c["id"]}-{st["id"]}">{st["n"]}. {E(st["name"])}</a>'] + [E(st['raci'].get(k, '')) for k in codes] for st in c['stages']]
        return table(tid, f'Who does what in {c["name"].lower()} (A accountable, R responsible, C consulted, I informed)', ['Step'] + codes, rows, cls=set(codes))

    def step_by_step(self, c):
        cid = c['id']
        used = set()
        steps = ''
        ids = []
        for st in c['stages']:
            pid = f'{cid}.{st["id"]}'
            ids.append(pid)
            acc = ', '.join(self.roles[k]['name'] for k, v in st['raci'].items() if v == 'A')
            dq = f'<span class="chip">{icon("clipboard-check")}DQAP {E(st["dqap"])}</span>' if st.get('dqap') else ''
            steps += f'''<li class="sbs-step {cid}" id="{cid}-{st["id"]}">
<div class="sbs-head"><span class="sbs-num" aria-hidden="true">{st["n"]}</span>{tile(STAGE_ICONS[st["id"]], cid + " sm")}
<h3 id="h-{cid}-{st["id"]}"><span class="visually-hidden">Step {st["n"]}: </span>{E(st["name"])}</h3>{status_tag([pid])}</div>
<p class="sbs-goal">{self.gloss(st["goal"], used)}</p>
<p class="sbs-meta"><span class="chip">{icon("flag")}When: {E(st["trigger"])}</span><span class="chip">{icon("key-round")}Accountable: {E(acc)}</span>{dq}</p>
<details class="sbs-details"><summary>{icon("chevron-right", "i chev")}How to do it</summary>
<div class="cols"><div><h4>{icon("list-ordered")} Do this</h4><ol class="do">{"".join(f"<li>{self.gloss(s, used)}</li>" for s in st["steps"])}</ol></div>
<div><h4>{icon("download")} You will have</h4>{ul(st["outputs"], cls="ticks")}<h4>{icon("list-checks")} Check before you move on</h4>{ul(st["checklist"], cls="checks")}</div></div>
<p class="meets">{icon("landmark")} Meets: {self.req_links(st.get("reqs", []))}</p>
{f'<div class="tip">{icon("lightbulb")}<p><strong>Tip.</strong> {E(st["tip"])}</p></div>' if st.get("tip") else ""}
</details>
{mark_done(pid)}
</li>'''
        return (f'<div class="sbs" data-sbs>{progress_widget(ids, "Your progress through " + c["name"].lower())}'
                f'<p class="js-only"><button type="button" class="btn secondary" data-sbs-all aria-expanded="false">{icon("chevron-down")}<span>Show all steps</span></button></p>'
                f'<ol class="sbs-list">{steps}</ol></div>')

    def p_cap(self, cid):
        c, d = self.caps[cid], self.d
        p = CAP_PAGE[cid]
        reqs = [r for r in d['requirements'] if r['cap'] == cid]
        req_rows = [[f'<a href="dam.html#{r["id"]}">{E(r["id"])}</a>', f'<span class="strength {r["strength"]}">{E(r["strength"])}</span>', E(r['text']) + prov(r['prov'])] for r in reqs]
        roles = ''.join(f'<li id="{cid}-role-{r}">{tile(ROLE_ICONS[r], "sm")}<div><strong>{E(self.roles[r]["name"])}</strong> ({E(r)}){prov(self.roles[r]["prov"])}<br>{E(self.roles[r]["text"])}</div></li>' for r in c['roles'])
        tmpl = ''.join(f'<section class="template" id="{t["id"]}"><h3>{icon("file-text")} {E(t["name"])} <small>({E(t["id"])})</small></h3>{ul(t["fields"], cls="fields")}<p><a href="data/templates.csv">{icon("download")}Download all templates (CSV)</a></p></section>' for t in c.get('templates', []))
        esc_rows = [[E(e['level']), E(e['who']), E(e['trigger']), E(e['when'])] for e in c.get('escalation', [])]
        meas_rows = [[E(x['name']), E(x['target'])] for x in c['measures']]
        srcs = sorted({s['id'] for s in d['sources'] if cid in s['caps']})
        src_list = ''.join(f'<li>{self.src_link(s)}: {E(self.src[s]["note"])} <small>({E(self.src[s]["dates"])})</small></li>' for s in srcs)
        lib = ''.join(f'<li><a href="library.html#{l["id"]}">{E(l["title"])}</a> ({E(l["status"])})</li>' for l in d['library'] if cid in l['cap'] and not l.get('src'))
        ils = [x for x in d['interlocks'] if x['from'].startswith(cid + '.') or x['to'].startswith(cid + '.')]
        il_html = ''.join(f'<li>{self.stage_ref(x["from"])} {icon("arrow-right")} {self.stage_ref(x["to"])}<br>{E(x["what"])} <a href="together.html#{x["id"]}">({E(x["id"])})</a></li>' for x in ils)
        mods = [mm for mm in d['modules'] if cid in mm['caps']]
        mod_html = ''.join(f'<li><a href="learning.html#{mm["id"]}">{icon(mm["icon"])}{E(mm["title"])}</a> <span class="chip">{E(mm["level"])}</span> <span class="chip">{mm["minutes"]} min</span></li>' for mm in mods)
        extra_method, extra_drawer = '', []
        if cid == 'cat':
            mrows = [[f'<code>{E(x["prop"])}</code>', E(x['obligation']), E(x['mem']), E(x['rule'])] for x in c['metadata']]
            extra_method = (f'<h2 id="metadata">{icon("tag")} Metadata properties</h2>'
                            f'<p>From {self.src_link("SRC-MD")}, mapped to the {self.src_link("SRC-MEM")}. The guidance does not give one mandatory or recommended column, so the obligation follows the wording of each section. "Listed" means it appears in the list of information to record without a stated strength.</p>'
                            + table('t-meta', 'Metadata to record for each critical data asset', ['Property', 'Obligation', 'MEM slot', 'How to record it'], mrows)
                            + f'<h3 id="mem-proposal">Proposed terms for the four properties missing from the MEM{prov("K")}</h3><p>A proposal to close finding F-04, not an agreed standard (OR-06).</p>'
                            + table('t-memprop', 'Proposed crosswalk for guidance properties with no MEM slot', ['Property', 'Proposed term', 'Note'],
                                    [[f'<code>{E(x["prop"])}</code>', f'<code>{E(x["term"])}</code>', E(x['note'])] for x in self.d['mem_proposal']])
                            + '<p>Write in plain English, expand acronyms, use ISO 8601 dates, and use "unknown" or "not applicable" rather than leaving a property blank. Make sure links work from outside your organisation.</p>')
            extra_drawer = [{'id': 'metadata', 'label': 'Metadata properties', 'icon': 'tag', 'count': len(c['metadata'])}]
        if cid == 'dq':
            dims = ''.join(f'<li>{tile("target", "sm dq")}<div><strong>{E(x["name"])}</strong><br>{E(x["text"])}</div></li>' for x in c['dimensions'])
            pr = ''.join(f'<li>{E(x["name"])}</li>' for x in c['principles'])
            tools = ''.join(f'<li><a href="{E(t["url"])}">{icon("wrench")}{E(t["name"])}</a></li>' for t in c['tools'])
            extra_method = (f'<h2 id="principles">{icon("compass")} Principles and dimensions</h2><p>From {self.src_link("SRC-GDQF")}.</p><h3>Five principles</h3><ol>{pr}</ol>'
                            f'<h3>Six dimensions</h3><ul class="icon-list">{dims}</ul><h2 id="tools">{icon("wrench")} Tools</h2><p>The Data Quality Commons is the authoritative home for these tools{prov("P")}. Files you check stay on your device.</p><ul class="link-list">{tools}</ul>')
            extra_drawer = [{'id': 'principles', 'label': 'Principles and dimensions', 'icon': 'compass', 'count': 11},
                            {'id': 'tools', 'label': 'Tools', 'icon': 'wrench', 'count': len(c['tools'])}]
        before = ul(c['before_you_start'], cls='checks')
        get = ul(c['you_get'], cls='ticks')
        tabs = [
            ('overview', 'Overview', f'''<h2 id="why">{icon("target")} Why it matters</h2><p class="lede">{self.gloss(c["purpose"])}</p><p>{E(c["why"])}</p>
<div class="cols"><div class="panel"><h3>{icon("clipboard-list")} Before you start</h3>{before}</div><div class="panel"><h3>{icon("award")} What you will have at the end</h3>{get}</div></div>
<h2 id="policy">{icon("landmark")} What the policy requires</h2>{table(f"t-req-{cid}", f"Policy requirements met by {c['name'].lower()}", ["ID", "Strength", "Requirement"], req_rows)}
<h2 id="links">{icon("workflow")} How it joins the other two</h2><ul class="hand-offs">{il_html}</ul>
<h2 id="learn">{icon("graduation-cap")} Learn it</h2><ul class="link-list">{mod_html}</ul>'''),
            ('method', 'Step by step', f'<h2 id="stages">{icon("route")} {E(c["method_name"])}{prov(c["method_prov"])}</h2><p>{E(c["method_intro"])}</p>{self.step_by_step(c)}{extra_method}'),
            ('roles', 'Roles', f'<h2 id="role-list">{icon("users")} Roles</h2><ul class="icon-list">{roles}</ul><h2 id="raci">{icon("list-checks")} Who does what</h2>{self.raci_table(c, "t-raci-" + cid)}'),
            ('templates', 'Templates', f'<h2 id="template-list">{icon("file-text")} Templates</h2><p>Blank structures to copy into your own tools. Record roles, never named individuals or personal email addresses.</p>{tmpl}'),
            ('escalation', 'Measures', f'<h2 id="measures">{icon("chart-column")} Measures</h2>{table("t-meas-" + cid, "Measures for " + c["name"].lower(), ["Measure", "Target"], meas_rows)}'
             + (f'<div class="warning" role="note">{icon("triangle-alert")}<span>Finding F-01: Table 4 of the GOV.UK issues framework gives 96.75% as the High band start for a 97.5% target, but its own rule gives 96.25%. These playbooks follow the rule. <a href="about.html#F-01">Read the finding</a>.</span></div>' if cid == 'dq' else '')
             + (f'<h2 id="ladder">{icon("triangle-alert")} Escalation</h2><p>{E(c["escalation_note"])}</p>{table("t-esc-" + cid, "Escalation for " + c["name"].lower(), ["Level", "Who", "Trigger", "Timescale"], esc_rows)}' if esc_rows
                else f'<h2 id="ladder">{icon("triangle-alert")} Escalation</h2><p>Cataloguing issues go up the <a href="governance.html#ladder">governance escalation ladder</a>.</p>')),
            ('depth', 'Sector depth', f'<h2 id="sector-depth">{icon("layers")} Where this playbook needs sector-specific content</h2><p>Themes where the general method is not enough, ranked by MoSCoW for the next releases. Use them to plan local supplements, and tell us through the <a href="contact.html">contact form</a> if you can contribute.</p>'
             + self.depth_list([x for x in d['domain_depth'] if cid in x['caps']])),
            ('sources', 'Sources', f'<h2 id="source-list">{icon("library")} Sources</h2><ul>{src_list}</ul><h2 id="related-rules">{icon("scale")} Related rulebooks</h2>'
             + self.rulebook_html([x for x in d['rulebook'] if cid in x['caps']], f'rb-{cid}') + (f'<h2 id="internal">{icon("lock-keyhole")} Practitioner material behind this playbook</h2><ul>{lib}</ul>' if lib else '')),
        ]
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(lbl)}</button>' for i, (k, lbl, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{b}</section>' for i, (k, lbl, b) in enumerate(tabs))
        hero = self.hero(CAP_ICONS[cid], 'Capability playbook', c['name'], f'<strong>{E(c["question"])}</strong>', kind=cid, brief=c['in_brief'],
                         meta=[('list-ordered', f'{len(c["stages"])} steps'), ('users', f'{len(c["roles"])} roles'), ('file-text', f'{len(c.get("templates", []))} templates'), ('graduation-cap', f'{len(mods)} learning modules')])
        body = hero + f'<div class="tabs"><div role="tablist" aria-label="{E(c["name"])} sections">{tablist}</div>{panels}</div>'
        drawer = [
            {'label': 'Overview', 'icon': 'info', 'items': [{'id': 'why', 'label': 'Why it matters', 'icon': 'target'},
                                                             {'id': 'policy', 'label': 'Policy requirements', 'icon': 'landmark', 'count': len(reqs)},
                                                             {'id': 'links', 'label': 'Joins with the others', 'icon': 'workflow', 'count': len(ils)},
                                                             {'id': 'learn', 'label': 'Learn it', 'icon': 'graduation-cap', 'count': len(mods)}]},
            {'label': 'Step by step', 'icon': CAP_ICONS[cid], 'items': [{'id': f'{cid}-{st["id"]}', 'label': f'{st["n"]}. {st["name"]}', 'icon': STAGE_ICONS[st['id']]} for st in c['stages']] + extra_drawer},
            {'label': 'Using it', 'icon': 'users', 'items': [{'id': 'role-list', 'label': 'Roles', 'icon': 'users', 'count': len(c['roles'])},
                                                              {'id': 'raci', 'label': 'Who does what', 'icon': 'list-checks'},
                                                              {'id': 'template-list', 'label': 'Templates', 'icon': 'file-text', 'count': len(c.get('templates', []))},
                                                              {'id': 'measures', 'label': 'Measures', 'icon': 'chart-column', 'count': len(c['measures'])},
                                                              {'id': 'ladder', 'label': 'Escalation', 'icon': 'triangle-alert', 'count': len(esc_rows)},
                                                              {'id': 'sector-depth', 'label': 'Sector depth', 'icon': 'layers', 'count': len([x for x in d['domain_depth'] if cid in x['caps']]), 'new': True},
                                                              {'id': 'source-list', 'label': 'Sources', 'icon': 'library', 'count': len(srcs)}]},
        ]
        return self.page(p, c['name'], body, drawer, crumbs=[c['name']], desc=c['purpose'],
                         jsonld={'@type': ['WebPage', 'HowTo'], 'name': c['name'], 'step': [{'@type': 'HowToStep', 'position': st['n'], 'name': st['name'], 'text': st['goal']} for st in c['stages']]})

    def rb_link(self, rid):
        x = self.rb[rid]
        return f'<a href="{E(x["url"])}">{E(x["title"])}</a>{prov(x["prov"], self.m["verified_on"])}'

    def rulebook_html(self, items, filt_id):
        groups = []
        for g in dict.fromkeys(x['group'] for x in items):
            rows = ''.join(f'<li id="{x["id"]}" data-item data-cap="{" ".join(x["caps"])}" data-group="{slug(x["group"])}">{self.rb_link(x["id"])}'
                           f'<span class="hint">{E(x["publisher"])}{" · updated " + E(x["updated"]) if x.get("updated") else ""}</span>{E(x["why"])}</li>' for x in items if x['group'] == g)
            groups.append(f'<h3>{E(g)}</h3><ul class="rulebook">{rows}</ul>')
        return f'<div id="{filt_id}">{"".join(groups)}</div>'

    def depth_list(self, items):
        out = ''
        for x in items:
            caps = ' '.join(f'<span class="pill {c}">{E(self.caps[c]["short"])}</span>' for c in x['caps'])
            sup = next((sp for sp in self.d.get('supplements', []) if sp['dd'] == x['id']), None)
            out += (f'<section class="depth" id="{x["id"]}" data-item data-cap="{" ".join(x["caps"])}" data-moscow="{slug(x["moscow"])}">'
                    f'<div class="depth-head"><h3>{E(x["theme"])}</h3><strong class="moscow m-{slug(x["moscow"])}">{E(x["moscow"])} have</strong></div>'
                    f'<p class="hint">{E(x["id"])} · For: {E("; ".join(x["sectors"]))}</p>{caps}<p>{E(x["why"])}</p>'
                    f'<h4>{icon("list-checks")} Content needed</h4>{ul(x["needed"], cls="checks")}'
                    + (f'<p><a class="btn-link" href="sectors.html#{sup["id"]}">{icon("arrow-right")}Open the {E(sup["title"].lower())} supplement</a></p>' if sup else '')
                    + (f'<p class="leads"><strong>Related rulebook:</strong> {"; ".join(self.rb_link(r) for r in (self.d.get("depth_refs") or {}).get(x["id"], []))}</p>' if (self.d.get("depth_refs") or {}).get(x["id"]) else '')
                    + f'<p class="leads"><strong>Leads to verify:</strong> {E("; ".join(x["leads"]))}{prov("K")}</p></section>')
        return out

    def p_together(self):
        d = self.d
        il = [[f'<span id="{x["id"]}">{E(x["id"])}</span>', self.stage_ref(x['from']), self.stage_ref(x['to']), E(x['what'])] for x in d['interlocks']]
        codes = [r['code'] for r in d['roles']]
        rows = [[f'<a href="{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}">{E(c["short"])} {st["n"]}. {E(st["name"])}</a>'] + [E(st['raci'].get(k, '')) for k in codes]
                for c in d['capabilities'] for st in c['stages']]
        roles = ''.join(f'<li id="role-{r["code"]}">{tile(ROLE_ICONS[r["code"]], "sm")}<div><strong>{E(r["name"])}</strong> ({E(r["code"])}){prov(r["prov"])}<br>{E(r["text"])}</div></li>' for r in d['roles'])
        cycle = ''.join(f'<li><h3>{icon("calendar-clock")} {E(r["when"])}</h3><ul class="cyc">'
                        + ''.join(f'<li class="{k}">{icon(CAP_ICONS[k])}<span><strong>{E(self.caps[k]["short"])}:</strong> {E(r[k])}</span></li>' for k in ('gov', 'cat', 'dq'))
                        + '</ul></li>' for r in d['cycle'])
        body = self.hero('workflow', 'Bringing the three together', 'How the three capabilities join up',
                         'Governance gives each asset an owner and a place to decide. Cataloguing describes it so others can find it. Quality proves it is fit to use. The hand-offs below mean each fact is recorded once.',
                         brief=['Record the owner once, in the ownership register, and reuse it in the catalogue record and the DQAP.',
                                'Use one annual review date per asset for the record, the owner and the DQAP.',
                                'Build the GDS return and the governance evidence from the same records.'])
        body += f'''<h2 id="interlocks">{icon("workflow")} Hand-offs between capabilities</h2>
{table("t-il", "Where one capability's output is another's input", ["ID", "From", "To", "What passes"], il)}
<h2 id="cycle">{icon("refresh-cw")} One joined-up year</h2><ol class="cycle">{cycle}</ol>
<h2 id="roles">{icon("users")} One set of roles</h2><p>The same roles appear in all three playbooks. Records name roles, never individuals.</p><ul class="icon-list two">{roles}</ul>
<h2 id="raci">{icon("list-checks")} Who does what across all three</h2>
{table("t-raci-all", "Who does what at every step (A accountable, R responsible, C consulted, I informed)", ["Step"] + codes, rows, cls=set(codes))}'''
        drawer = [{'label': 'Joined up', 'icon': 'workflow', 'items': [
            {'id': 'interlocks', 'label': 'Hand-offs', 'icon': 'workflow', 'count': len(d['interlocks'])},
            {'id': 'cycle', 'label': 'One joined-up year', 'icon': 'refresh-cw', 'count': len(d['cycle'])},
            {'id': 'roles', 'label': 'One set of roles', 'icon': 'users', 'count': len(d['roles'])},
            {'id': 'raci', 'label': 'Who does what', 'icon': 'list-checks', 'count': len(rows)}]}]
        return self.page('together', 'Joined up', body, drawer, crumbs=['Joined up'])

    def task_li(self, t):
        if 'm' in t:
            mm = self.mods[t['m']]
            return (f'<li class="task"><span class="task-name">{icon(mm["icon"])}<a href="learning.html#{mm["id"]}">Learn: {E(mm["title"])}</a>'
                    f'<span class="hint">{mm["minutes"]} minutes, {E(mm["level"].lower())}</span></span>{status_tag(["mod:" + mm["id"]])}</li>')
        c, st = self.stage[t['p']]
        return (f'<li class="task"><span class="task-name">{icon(STAGE_ICONS[st["id"]])}<a href="{self.stage_url(t["p"])}">{E(t["label"])}</a>'
                f'<span class="hint">{E(c["name"])}, step {st["n"]}</span></span>{status_tag([t["p"]])}</li>')

    def p_personas(self):
        d = self.d
        cards = ''.join(f'<li class="persona-card"><a href="#persona-{p["id"]}">{tile(p["icon"], "role")}<span class="pc-body"><strong>{E(p["title"])}</strong><span>{E(p["summary"])}</span></span>{icon("arrow-right", "i go")}</a></li>' for p in d['personas'])
        tabs = []
        for p in d['personas']:
            needs = ''.join(f'<li>As a {E(p["title"].lower())}, I need {E(n["need"])}, so that {E(n["so"])}.</li>' for n in p['needs'])
            jm = ''.join(f'<li class="jstage"><h4>{icon(STAGE_ROW_ICONS[j["stage"]])} {E(j["stage"])}</h4><ul class="tasks">{"".join(self.task_li(t) for t in j["tasks"])}</ul></li>' for j in p['journey'])
            lj = ''.join(f'<li><a href="learning.html#{mid}">{icon(self.mods[mid]["icon"])}{E(mid)} {E(self.mods[mid]["title"])}</a> <span class="chip">{E(self.mods[mid]["level"])}</span> <span class="chip">{self.mods[mid]["minutes"]} min</span>{status_tag(["mod:" + mid])}</li>' for mid in p['modules'])
            mins = sum(self.mods[mid]['minutes'] for mid in p['modules'])
            body = f'''<div class="persona-head" id="persona-{p["id"]}">{tile(p["icon"], "lg role")}<div><h2>{E(p["title"])}</h2><p class="lede">{E(p["summary"])}</p>
{progress_widget(self.persona_units(p), "Your route")}</div></div>
<div class="profile">
<div class="panel"><h3>{icon("compass")} Your context</h3><p>{E(p["context"])}</p></div>
<div class="panel"><h3>{icon("target")} Your goals</h3>{ul(p["goals"], cls="ticks")}</div>
<div class="panel"><h3>{icon("message-square-text")} What you need</h3><ul>{needs}</ul></div>
<div class="panel"><h3>{icon("triangle-alert")} What gets in the way</h3>{ul(p["pains"])}</div>
<div class="panel"><h3>{icon("accessibility")} We design for</h3>{ul(p["design_for"])}<p class="hint">Illustrative access needs, not drawn from research with this audience (OR-04).</p></div>
<div class="panel success"><h3>{icon("badge-check")} Success looks like</h3><p>{E(p["success"])}</p></div></div>
<h3 class="sec">{icon("route")} Your route, step by step</h3>
<p>Work through each stage. Status updates as you mark steps and learning activities as done.</p>
<ol class="journey">{jm}</ol>
<h3 class="sec">{icon("graduation-cap")} Your learning journey ({len(p["modules"])} modules, about {mins} minutes)</h3>
<ol class="learn-path">{lj}</ol>'''
            tabs.append((f'p-{p["id"]}', p['title'], body))
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(l)}</button>' for i, (k, l, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{b}</section>' for i, (k, l, b) in enumerate(tabs))
        body = self.hero('users-round', 'Routes by role', 'Start from your role', E(d['pages']['personas']['lede']),
                         brief=['Pick the role closest to yours. Roles describe responsibilities, not job titles; you may hold more than one.',
                                'Each route has five stages: learn, prepare, do, report and improve.',
                                'Mark steps as done to track your progress. It is saved in this browser only.'])
        body += f'<h2 id="choose">{icon("users-round")} Choose a role</h2><ul class="persona-grid">{cards}</ul><div class="tabs" id="routes"><div role="tablist" aria-label="Roles">{tablist}</div>{panels}</div>'
        drawer = [{'label': 'Roles', 'icon': 'users-round', 'items': [{'id': 'choose', 'label': 'Choose a role', 'icon': 'users-round', 'count': len(d['personas'])}]
                   + [{'id': f'persona-{p["id"]}', 'label': p['title'], 'icon': p['icon']} for p in d['personas']]}]
        return self.page('personas', 'Start from your role', body, drawer, crumbs=['Your role'])

    def p_learning(self):
        d = self.d
        n = self.counts()
        levels = ''.join(f'<li>{tile(ic, "sm")}<div><strong>{E(lv)}</strong><br>{E(txt)}</div></li>' for lv, ic, txt in [
            ('Foundation', LEVELS['Foundation'], 'For anyone new to the policy or to a data role.'),
            ('Practitioner', LEVELS['Practitioner'], 'For people doing the work of a capability day to day.'),
            ('Advanced', LEVELS['Advanced'], 'For people running all three capabilities together.')])
        paths = ''
        for p in d['personas']:
            steps = ''.join(f'<li><a href="#{mid}">{E(mid)}</a></li>' for mid in p['modules'])
            paths += f'<li>{tile(p["icon"], "sm role")}<div><a href="personas.html#persona-{p["id"]}"><strong>{E(p["title"])}</strong></a>{progress_widget(["mod:" + x for x in p["modules"]], "Modules done")}<ol class="path">{steps}</ol></div></li>'
        cards = ''
        details = ''
        for mm in d['modules']:
            units = self.mod_units(mm['id'])
            caps = ' '.join(f'<span class="pill {c}">{E(self.caps[c]["short"])}</span>' for c in mm['caps'])
            cards += (f'<li class="mod-card" data-item data-level="{slug(mm["level"])}" data-cap="{" ".join(mm["caps"])}"><a href="#{mm["id"]}">{tile(mm["icon"], "sm")}'
                      f'<span><strong>{E(mm["id"])} {E(mm["title"])}</strong><span class="hint">{icon(LEVELS[mm["level"]])}{E(mm["level"])} · {icon("timer")}{mm["minutes"]} min</span></span></a>'
                      f'{caps}{status_tag(units)}</li>')
            acts = ''.join(f'<li class="activity">{icon(ACTIVITY_ICONS[a["type"]])}<div><strong>{E(a["type"])}.</strong> '
                           + (f'<a href="{E(a["link"])}">{E(a["text"])}</a>' if a.get('link') else E(a['text']))
                           + f'{mark_done(mm["id"] + "." + a["id"], "Done")}</div></li>' for a in mm['activities'])
            qs = ''
            for qi, q in enumerate(mm['check']):
                name = f'{mm["id"]}-q{qi}'
                opts = ''.join(f'<label><input type="radio" name="{name}" value="{oi}"> {E(o)}</label>' for oi, o in enumerate(q['options']))
                qs += (f'<fieldset class="kc" data-answer="{q["answer"]}"><legend>{E(q["q"])}</legend>{opts}'
                       f'<p class="js-only"><button type="button" class="btn secondary" data-check>{icon("circle-help")}Check my answer</button></p>'
                       f'<p class="kc-feedback" aria-live="polite"></p>'
                       f'<details class="kc-answer"><summary>Show the answer</summary><p><strong>{E(q["options"][q["answer"]])}.</strong> {E(q["why"])}</p></details></fieldset>')
            details += f'''<section class="module" id="{mm["id"]}" aria-labelledby="h-{mm["id"]}">
<div class="mod-head">{tile(mm["icon"], "lg")}<div><p class="caption">{E(mm["id"])} · {E(mm["level"])} · {mm["minutes"]} minutes</p><h3 id="h-{mm["id"]}">{E(mm["title"])}</h3>{caps}</div></div>
{progress_widget(units, "Activities done")}
<div class="cols"><div><h4>{icon("target")} By the end you will be able to</h4>{ul(mm["outcomes"], cls="ticks")}</div>
<div><h4>{icon("list-checks")} Activities</h4><ol class="activities">{acts}</ol></div></div>
<h4>{icon("circle-help")} Check your understanding</h4>{qs}</section>'''
        filt = '''<div class="filters" data-filter="mod-list" role="group" aria-label="Filter modules">
<div><label for="m-level">Level</label><select id="m-level" name="level"><option value="">All</option><option value="foundation">Foundation</option><option value="practitioner">Practitioner</option><option value="advanced">Advanced</option></select></div>
<div><label for="m-cap">Capability</label><select id="m-cap" name="cap"><option value="">All</option><option value="gov">Data governance</option><option value="cat">Data cataloguing</option><option value="dq">Data quality</option></select></div>
<p class="count-out" aria-live="polite"></p></div>'''
        body = self.hero('graduation-cap', 'Learning journeys', 'Learn the playbooks', E(d['pages']['learning']['lede']),
                         brief=[f'{n["modules"]} modules, about {n["minutes"]} minutes in total, at three levels.',
                                'Each module has outcomes, a short set of activities and a check of understanding.',
                                'Follow the journey for your role, or pick any module.'],
                         meta=[('graduation-cap', f'{n["modules"]} modules'), ('timer', f'{n["minutes"]} minutes'), ('layers', '3 levels')])
        body += f'''<h2 id="levels">{icon("layers")} Levels</h2><ul class="icon-list three">{levels}</ul>
<h2 id="journeys">{icon("route")} Journeys by role</h2><ul class="icon-list paths">{paths}</ul>
<h2 id="modules">{icon("book-open")} All modules</h2>{filt}<ul class="mod-grid" id="mod-list">{cards}</ul>
<h2 id="module-detail">{icon("graduation-cap")} Modules in full</h2>{details}'''
        drawer = [{'label': 'Learning', 'icon': 'graduation-cap', 'items': [
            {'id': 'levels', 'label': 'Levels', 'icon': 'layers', 'count': 3}, {'id': 'journeys', 'label': 'Journeys by role', 'icon': 'route', 'count': len(d['personas'])},
            {'id': 'modules', 'label': 'All modules', 'icon': 'book-open', 'count': len(d['modules'])}]},
                  {'label': 'Modules', 'icon': 'book-open', 'items': [{'id': mm['id'], 'label': f'{mm["id"]} {mm["title"]}', 'icon': mm['icon']} for mm in d['modules']]}]
        return self.page('learning', 'Learning', body, drawer, crumbs=['Learning'],
                         jsonld={'@type': ['WebPage', 'Course'], 'name': 'DAM capability playbooks learning modules',
                                 'hasPart': [{'@type': 'LearningResource', 'name': mm['title'], 'educationalLevel': mm['level'], 'timeRequired': f'PT{mm["minutes"]}M', 'teaches': mm['outcomes']} for mm in d['modules']]})

    def p_inclusion(self):
        d, inc = self.d, self.d['inclusion']
        duties = ''.join(f'<li>{tile("scale", "sm")}<div><strong>{E(x["name"])}</strong>{prov(x["prov"])}<br>{E(x["text"])}</div></li>' for x in inc['duties'])
        checks = ''.join(f'<div class="card {c["cap"]}"><div class="card-head">{tile(CAP_ICONS[c["cap"]], c["cap"])}<h3>{E(self.caps[c["cap"]]["name"])}</h3></div>{ul(c["items"], cls="checks")}</div>' for c in inc['checks'])
        qs = ''.join(f'<li>{mark_done("inc.q" + str(i), "Considered")}<span>{E(q)}</span></li>' for i, q in enumerate(inc['questions']))
        portal = ul(inc['portal'], cls='ticks')
        body = self.hero('heart-handshake', 'Diversity, equity, equality, inclusion and accessibility', 'Inclusive data practice', E(d['pages']['inclusion']['lede']),
                         brief=['Poor or missing data often falls hardest on the people services most need to reach.',
                                'Each capability has its own inclusion checks; use them at the steps where decisions are made.',
                                'This portal is designed to be usable by everyone, and says where it falls short.'])
        body += f'''<h2 id="duties">{icon("scale")} Duties that apply</h2><ul class="icon-list">{duties}</ul>
<p class="hint">Duties marked K are general knowledge: confirm how they apply to your organisation with your equality and legal advisers.</p>
<h2 id="checks">{icon("list-checks")} Inclusion checks for each capability</h2><div class="cards three">{checks}</div>
<h2 id="questions">{icon("circle-help")} Questions to ask about any critical data asset</h2>
{progress_widget(["inc.q" + str(i) for i in range(len(inc["questions"]))], "Questions considered")}
<ol class="questions">{qs}</ol>
<h2 id="portal">{icon("accessibility")} How this portal is designed for everyone</h2>{portal}
<p>Read the <a href="about.html#accessibility">accessibility statement</a>, or change text size, spacing and colours in <strong>Display options</strong> at the top of every page.</p>'''
        drawer = [{'label': 'Inclusion', 'icon': 'heart-handshake', 'items': [
            {'id': 'duties', 'label': 'Duties that apply', 'icon': 'scale', 'count': len(inc['duties'])},
            {'id': 'checks', 'label': 'Checks by capability', 'icon': 'list-checks', 'count': 3},
            {'id': 'questions', 'label': 'Questions to ask', 'icon': 'circle-help', 'count': len(inc['questions'])},
            {'id': 'portal', 'label': 'Designed for everyone', 'icon': 'accessibility', 'count': len(inc['portal'])}]}]
        return self.page('inclusion', 'Inclusive data practice', body, drawer, crumbs=['Inclusion'])

    def p_contact(self):
        m = self.m
        repo_issue = f'https://github.com/{m["repo"]}/issues/new'
        kinds = ['A question', 'Something is wrong or out of date', 'An accessibility problem', 'An idea or improvement']
        parts = ['Data governance', 'Data cataloguing', 'Data quality', 'DAM Policy spine', 'The whole portal']
        body = self.hero('message-square-text', 'Contact', 'Contact form', E(self.d['pages']['contact']['lede']),
                         brief=['Messages are sent through GitHub and are public. Do not include personal data, names of colleagues or anything above OFFICIAL.',
                                'You need a free GitHub account to send the message.',
                                'If you cannot use this form, ask a colleague to send it for you.'])
        body += f'''<form class="contact" id="contact-form" data-target="{E(repo_issue)}" novalidate>
<div class="error-summary" id="cf-errors" tabindex="-1" hidden role="alert"><h2>There is a problem</h2><ul></ul></div>
<fieldset><legend><h2 class="fs-h">{icon("message-square-text")} What is this about?</h2></legend>
{"".join(f'<label for="cf-kind-{i}"><input type="radio" id="cf-kind-{i}" name="kind" value="{E(k)}"> {E(k)}</label>' for i, k in enumerate(kinds))}</fieldset>
<div class="field"><label for="cf-part"><strong>Which part of the portal?</strong></label>
<select id="cf-part" name="capability">{"".join(f'<option>{E(p)}</option>' for p in parts)}</select></div>
<div class="field"><label for="cf-page"><strong>Page address</strong> <span class="hint">(optional)</span></label><input id="cf-page" name="page" type="text" autocomplete="off"></div>
<div class="field"><label for="cf-detail"><strong>Tell us more</strong></label><p class="hint" id="cf-detail-hint">Say what you were trying to do and what happened.</p>
<textarea id="cf-detail" name="detail" rows="6" aria-describedby="cf-detail-hint"></textarea></div>
<div class="field"><label class="check"><input type="checkbox" id="cf-privacy" name="privacy"> I have not included personal data or anything sensitive</label></div>
<p><button type="submit" class="btn">{icon("send")}Continue to send on GitHub</button></p>
<p class="hint">You will see your message on GitHub before you send it.</p></form>
<noscript><p><a href="{E(m["contact_form"])}">Open the contact form on GitHub</a>.</p></noscript>
<h2 id="privacy-notice">{icon("lock-keyhole")} Privacy notice</h2>
<p>This form does not store anything. It opens GitHub with your message filled in. When you send it, GitHub publishes it as a public issue under your GitHub account, and GitHub's own privacy statement applies. Only include what is needed to answer you.</p>'''
        return self.page('contact', 'Contact form', body, None, crumbs=['Contact'])

    def p_library(self):
        d = self.d
        rows, attrs = [], []
        for l in d['library']:
            where = self.src_link(l['src']) if l.get('src') else 'Not published' + prov(l['prov'])
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
        tbl = table('t-lib', 'Playbook material for the three capabilities, wherever it lives', ['Title', 'Type', 'Capability', 'Status', 'For', 'Where'], rows, row_attrs=attrs, tbody_id='lib-table')
        tm = [[f'<a href="{CAP_PAGE[c["id"]]}.html#{t["id"]}">{E(t["name"])}</a>', f'<span class="pill {c["id"]}">{E(c["short"])}</span>', str(len(t['fields'])), '<a href="data/templates.csv">CSV</a>']
              for c in d['capabilities'] for t in c.get('templates', [])]
        dl = [('data/playbooks.json', 'Full content (JSON)'), ('data/requirements.csv', 'Requirements (CSV)'), ('data/templates.csv', 'Templates (CSV)'),
              ('data/glossary.csv', 'Glossary (CSV)'), ('data/vocabulary.ttl', 'Vocabulary (SKOS, Turtle)'), ('data/vocabulary.jsonld', 'Vocabulary (SKOS, JSON-LD)'),
              ('data/catalogue.jsonld', 'Catalogue of sources (DCAT, JSON-LD)'), ('data/metadata-dictionary.csv', 'Metadata data dictionary (CSV)')]
        body = self.hero('library', 'Library', 'Library', 'All playbook material for the three capabilities: published GOV.UK guidance, standards, tools, and practitioner material not yet published. Published items link to their authoritative source.',
                         brief=['Filter by capability, type or status.', 'Templates are blank structures to copy into your own tools.', 'Everything on this portal is also available as open data.'])
        body += f'''<h2 id="library">{icon("library")} All material</h2>{filt}{tbl}
<h2 id="templates">{icon("file-text")} Templates</h2>{table("t-tmpl", "Templates in the three playbooks", ["Template", "Capability", "Fields", "Download"], tm)}
<h2 id="depth">{icon("layers")} Where more sector-specific content is needed</h2>
<p>An assessment of themes where the three playbooks need more specific capability, domain or sector content. MoSCoW sets the order for the next releases.</p>
<div class="filters" data-filter="depth-list" role="group" aria-label="Filter the assessment"><div><label for="d-cap">Capability</label><select id="d-cap" name="cap"><option value="">All</option><option value="gov">Data governance</option><option value="cat">Data cataloguing</option><option value="dq">Data quality</option></select></div>
<div><label for="d-m">Priority</label><select id="d-m" name="moscow"><option value="">All</option><option value="must">Must have</option><option value="should">Should have</option><option value="could">Could have</option></select></div><p class="count-out" aria-live="polite"></p></div>
<div id="depth-list">{self.depth_list(d["domain_depth"])}</div>
<h2 id="data">{icon("download")} Open data</h2><p>Every page is generated from one content file, also published in open formats.</p>
<ul class="link-list">{"".join(f'<li><a href="{u}">{icon("download")}{E(t)}</a></li>' for u, t in dl)}</ul>'''
        drawer = [{'label': 'Library', 'icon': 'library', 'items': [
            {'id': 'library', 'label': 'All material', 'icon': 'library', 'count': len(d['library'])},
            {'id': 'templates', 'label': 'Templates', 'icon': 'file-text', 'count': len(tm)},
            {'id': 'depth', 'label': 'Sector depth needed', 'icon': 'layers', 'count': len(d['domain_depth']), 'new': True},
            {'id': 'data', 'label': 'Open data', 'icon': 'download', 'count': len(dl)}]}]
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
                add(sid, f'{c["short"]} {st["n"]} {st["name"]}', 'Step', 'stage', st['goal'], f'{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}')
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
        shape = {'cap': 'circle', 'stage': 'rect', 'req': 'diamond', 'src': 'circle'}
        lines = ''.join(f'<line x1="{pos[a][0]:.0f}" y1="{pos[a][1]:.0f}" x2="{pos[b][0]:.0f}" y2="{pos[b][1]:.0f}" data-a="{E(a)}" data-b="{E(b)}"/>' for a, b in edges)
        gs = ''
        for n in nodes:
            x, y = pos[n['id']]
            r = r_of[n['k']]
            if shape[n['k']] == 'rect':
                mark = f'<rect class="k-{n["k"]}" x="{x - r:.0f}" y="{y - r:.0f}" width="{2 * r}" height="{2 * r}"/>'
            elif shape[n['k']] == 'diamond':
                mark = f'<polygon class="k-{n["k"]}" points="{x:.0f},{y - r - 2:.0f} {x + r + 2:.0f},{y:.0f} {x:.0f},{y + r + 2:.0f} {x - r - 2:.0f},{y:.0f}"/>'
            else:
                mark = f'<circle class="k-{n["k"]}" cx="{x:.0f}" cy="{y:.0f}" r="{r}"/>'
            short = n['label'] if n['k'] in ('cap', 'req') else ''
            gs += (f'<g class="node" tabindex="0" role="button" data-id="{E(n["id"])}" aria-label="{E(n["kind"] + ": " + n["label"])}">{mark}'
                   + (f'<text x="{x + r + 4:.0f}" y="{y + 4:.0f}">{E(short)}</text>' if short else '') + '<title>' + E(n['label']) + '</title></g>')
        svg = f'<svg viewBox="0 0 {W} {H}" role="group" aria-label="Knowledge graph of capabilities, steps, requirements and sources">{lines}{gs}</svg>'
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
                         self.src_link(c['src']) if c.get('src') else 'Practitioner material'])
            attrs.append(f' data-item data-cap="{" ".join(c["caps"])}"')
        filt = f'''<div class="filters" data-filter="gl-table" role="group" aria-label="Filter the glossary">
<div><label for="g-cap">Capability</label><select id="g-cap" name="cap"><option value="">All</option>{"".join(f'<option value="{c["id"]}">{E(c["name"])}</option>' for c in d["capabilities"])}</select></div>
<div><label for="g-q">Contains</label><input id="g-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>'''
        gl = table('t-gl', 'Glossary and thesaurus', ['Term', 'Definition', 'Also called', 'Broader term', 'Capability', 'Source'], rows, row_attrs=attrs, tbody_id='gl-table')

        def tree(parent):
            kids = [c for c in conc if c['broader'] == parent]
            if not kids:
                return ''
            return '<ul>' + ''.join(f'<li><a href="#c-{k["id"]}">{E(k["term"])}</a>{tree(k["id"])}</li>' for k in kids) + '</ul>'
        svg, gdata = self.graph()
        mrows = [[f'<code>{E(x["prop"])}</code>', E(x['mem']), E(x['obligation']), E(x['rule'])] for x in self.caps['cat']['metadata']]
        tabs = [
            ('glossary', 'Glossary', f'<h2 id="gl">{icon("book-open")} Glossary and thesaurus</h2><p>Every term, with other names it goes by (the thesaurus) and its broader term (the taxonomy).</p>{filt}{gl}'),
            ('taxonomy', 'Taxonomy', f'<h2 id="tax">{icon("network")} Taxonomy</h2><p>Terms arranged from broader to narrower meaning.</p><div class="tree">{tree(None)}</div>'),
            ('graph-tab', 'Knowledge graph', f'<h2 id="kg">{icon("network")} Knowledge graph</h2><p>Capabilities, their steps, the requirements they meet and the sources behind them. Select a shape to see what it connects to. The same information is in the tables on the policy and capability pages.</p>'
             f'<p class="legend"><span class="lg-cap">Capability (large circle)</span><span class="lg-stage">Step (square)</span><span class="lg-req">Requirement (diamond)</span><span class="lg-src">Source (small circle)</span></p>'
             f'<div class="graph-wrap" id="graph">{svg}</div><p><button type="button" class="btn secondary" id="graph-clear">{icon("x")}Clear selection</button></p><div id="graph-detail" aria-live="polite">Select a shape to see what it connects to.</div>'),
            ('dictionary', 'Data dictionary', f'<h2 id="dict">{icon("database")} Data dictionary</h2><p>The fields of a critical data asset catalogue record.</p>{table("t-dict", "Catalogue record fields", ["Property", "MEM slot", "Obligation", "Rule"], mrows)}'
             f'<p>Ontology: the <a href="data/vocabulary.ttl">SKOS vocabulary</a> uses <code>skos:prefLabel</code>, <code>skos:altLabel</code>, <code>skos:broader</code> and <code>skos:definition</code>, with <code>dcterms:source</code> for provenance.</p>'),
        ]
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(l)}</button>' for i, (k, l, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{b}</section>' for i, (k, l, b) in enumerate(tabs))
        body = self.hero('network', 'Shared vocabulary', 'Knowledge', 'The terms the three playbooks share, and how everything connects.',
                         brief=['Hover over or focus on a dotted term anywhere in the portal to see its definition.', 'Terms are also published as SKOS for other systems to reuse.'])
        body += f'<div class="tabs"><div role="tablist" aria-label="Knowledge views">{tablist}</div>{panels}</div>'
        drawer = [{'label': 'Knowledge', 'icon': 'network', 'items': [
            {'id': 'gl', 'label': 'Glossary and thesaurus', 'icon': 'book-open', 'count': len(conc)}, {'id': 'tax', 'label': 'Taxonomy', 'icon': 'network'},
            {'id': 'kg', 'label': 'Knowledge graph', 'icon': 'network', 'count': len(gdata['nodes'])}, {'id': 'dict', 'label': 'Data dictionary', 'icon': 'database', 'count': len(mrows)}]}]
        return self.page('knowledge', 'Knowledge', body, drawer, crumbs=['Knowledge'], extra_json={'graph-data': gdata},
                         jsonld={'@type': ['WebPage', 'DefinedTermSet'], 'hasDefinedTerm': [{'@type': 'DefinedTerm', 'name': c['term'], 'description': c['def']} for c in conc]})

    def p_about(self):
        d, m = self.d, self.m
        orr = ''.join(f'<tr id="{o["id"]}"><th scope="row">{E(o["id"])}</th><td>{E(o["item"])}</td><td>{E(o["who"])}</td></tr>' for o in d['open_register'])
        dfr = [[E(x['id']), E(x['found']), E(x['defect']), E(x['cause']), E(x['check'])] for x in d['defects']]
        adv = ''.join(f'<li><strong>{E(a["challenge"])}</strong><br>{E(a["answer"])}</li>' for a in d['adversarial'])
        n = self.counts()
        provs = ''.join(f'<li>{prov(k)} {E(v)}</li>' for k, v in PROV_TEXT.items())
        body = self.hero('info', 'About', 'About this portal', E(m['subtitle']) + '.',
                         brief=['A prototype that brings together the playbooks for the three capabilities behind the DAM Policy.',
                                'Every fact is labelled with where it came from.', 'What it cannot yet do is listed openly in the open register.'])
        body += f'''<h2 id="intent">{icon("target")} Purpose</h2><p>{E(m["intent"])}</p>
<p>Standard applied: {E(m["profile"])} {E(m["grade_reason"])}</p>
<h2 id="checkpoint">{icon("milestone")} Checkpoint</h2>
<p><strong>Brief.</strong> Bring together the playbook material for governance, cataloguing and quality in one interactive portal, organised around the people who use it and how they learn.</p>
<p><strong>How it was built.</strong> Material came from the GOV.UK guidance behind the policy ({n["verified"]} sources checked on {E(m["verified_on"])}), the Data Quality Commons playbook, the cross-government Data Governance Playbook draft and the Metadata Exchange Model. It was combined into one content file with a requirements spine, three step-by-step methods, one set of roles, routes for {len(d["personas"])} roles and {n["modules"]} learning modules.</p>
<p><strong>Against the brief.</strong> Met for governance and quality. Partly met for cataloguing, which is built from public guidance because the fuller cataloguing playbook is not yet published (OR-01). Routes and personas are not yet tested with users (OR-04).</p>
<h2 id="provenance">{icon("tag")} How sources are labelled</h2><ul>{provs}</ul>
<p>Requirement strength follows the wording of the source. Step sequences are labelled as synthesis or practitioner material; they are not GOV.UK requirements.</p>
<h2 id="findings">{icon("search")} Verification findings</h2>
{"".join(f'<section class="finding" id="{x["id"]}"><h3>{E(x["id"])}: {E(x["title"])}</h3><p>{E(x["detail"])}</p><p><strong>Action:</strong> {E(x["action"])} <span class="hint">Verified {E(x["verified"])} against {self.finding_src(x)}</span></p></section>' for x in d["findings"])}
<h2 id="standards">{icon("badge-check")} Assessment against the build standard</h2>
<p>How this portal meets the self-routines and practices of the reusable build standard, rated MoSCoW for a shared portal. Status is what is in place in this release.</p>
{table("t-std", "Build standard assessment", ["ID", "Routine or practice", "MoSCoW", "Status", "How"], [[E(x["id"]), E(x["name"]), E(x["moscow"]), f'<strong class="status s-{slug(x["status"]).replace("met", "completed").replace("partly", "in-progress").replace("not-yet", "not-started")}">{E(x["status"])}</strong>', E(x["how"])] for x in d["standards"]])}
<h2 id="explain">{icon("lightbulb")} How the portal decides things</h2>
<ul><li><strong>Search order.</strong> Exact title matches first, then titles that start with your words, then titles containing all your words, then other matches, each in page order.</li>
<li><strong>Progress.</strong> A step is done when you mark it. A module is done when all its activities are marked. A route counts both.</li>
<li><strong>Status page.</strong> A weekly automated run checks sources, the review date and page weight. It never changes content; it opens an issue for a person to act on.</li></ul>
<h2 id="adversarial">{icon("scale")} The case against, answered</h2><ul>{adv}</ul>
<h2 id="open">{icon("clipboard-list")} Open register</h2>
<div class="table-wrap" role="region" aria-labelledby="t-open" tabindex="0"><table><caption id="t-open">What design cannot close, and who must act</caption><thead><tr><th scope="col">ID</th><th scope="col">Item</th><th scope="col">Who must act</th></tr></thead><tbody>{orr}</tbody></table></div>
<h2 id="defects">{icon("wrench")} Defect register</h2><p>Every defect gets a check that stops it coming back. The set of checks never shrinks.</p>
{table("t-def", "Defects and the checks that prevent them", ["ID", "Found", "Defect", "Root cause", "Check"], dfr)}
<h2 id="accessibility">{icon("accessibility")} Accessibility statement</h2>
<p>This portal aims to meet WCAG 2.2 at level AA. Each release is checked automatically with axe-core in a real browser, for keyboard use, for sideways scrolling from 320 to 1920 pixels wide, and in light and dark modes. You can change text size, line spacing and colours in Display options.</p>
<p>Known limitations: it has not been tested in person with disabled users or with assistive technology users (OR-09). The knowledge graph is a visual aid; the same relationships are in tables on the policy and capability pages. Progress tracking needs scripts; every page can be read without them.</p>
<p>If you find a problem, use the <a href="contact.html">contact form</a>. If you cannot use it, ask a colleague to send it for you. If you are not happy with the response, contact the Equality Advisory and Support Service (EASS).</p>
<h2 id="privacy">{icon("lock-keyhole")} Privacy</h2><p>The portal sets no cookies and loads nothing from other sites. Your display choices and progress are kept only in your own browser and can be cleared from the home page. The contact form opens GitHub, where messages are public.</p>
<h2 id="build">{icon("badge-check")} Build and checks</h2><p>Build {E(self.build_id)}. Generated from one content file. Each release runs structural, link, provenance, email, language, accessibility and layout checks. Each check is shown to fail on a deliberate break before it is trusted.</p>'''
        drawer = [{'label': 'About', 'icon': 'info', 'items': [
            {'id': 'intent', 'label': 'Purpose', 'icon': 'target'}, {'id': 'checkpoint', 'label': 'Checkpoint', 'icon': 'milestone'},
            {'id': 'provenance', 'label': 'Source labels', 'icon': 'tag', 'count': 5},
            {'id': 'findings', 'label': 'Verification findings', 'icon': 'search', 'count': len(d['findings']), 'new': True},
            {'id': 'standards', 'label': 'Build standard assessment', 'icon': 'badge-check', 'count': len(d['standards'])},
            {'id': 'explain', 'label': 'How the portal decides', 'icon': 'lightbulb', 'count': 3},
            {'id': 'adversarial', 'label': 'The case against', 'icon': 'scale', 'count': len(d['adversarial'])},
            {'id': 'open', 'label': 'Open register', 'icon': 'clipboard-list', 'count': len(d['open_register'])},
            {'id': 'defects', 'label': 'Defect register', 'icon': 'wrench', 'count': len(d['defects'])},
            {'id': 'accessibility', 'label': 'Accessibility', 'icon': 'accessibility'},
            {'id': 'privacy', 'label': 'Privacy', 'icon': 'lock-keyhole'}, {'id': 'build', 'label': 'Build and checks', 'icon': 'badge-check'}]}]
        return self.page('about', 'About', body, drawer, crumbs=['About'])

    def p_sectors(self):
        d = self.d
        dd = {x['id']: x for x in d['domain_depth']}
        qs = ''.join(f'<li><label class="check"><input type="checkbox" data-q="{E(q["id"])}" data-sups="{E(" ".join(q["sups"]))}"> {E(q["text"])}</label></li>' for q in d['applicability'])
        title_of = {x['id']: x['title'] for x in d['supplements']}
        nojs = [[E(q['text']), ' '.join(f'<a class="pill" href="#{sp}">{E(title_of[sp])}</a>' for sp in q['sups'])] for q in d['applicability']]
        cards, detail, all_rules = '', '', []
        for x in d['supplements']:
            t = dd[x['dd']]
            caps = ' '.join(f'<span class="pill {c}">{E(self.caps[c]["short"])}</span>' for c in t['caps'])
            cl_ids = [x['id'] + '.c' + str(i) for i in range(len(x['checklist']))]
            cards += (f'<li class="mod-card" data-item data-moscow="{slug(t["moscow"])}" data-cap="{" ".join(t["caps"])}" data-sup="{x["id"]}"><a href="#{x["id"]}">{tile(x["icon"], "sm")}'
                      f'<span><strong>{E(x["title"])}</strong><span class="hint">{E(x["summary"])}</span></span></a>'
                      f'<span><strong class="moscow m-{slug(t["moscow"])}">{E(t["moscow"])} have</strong> {caps}</span>'
                      f'{progress_widget(cl_ids, "Checklist")}</li>')
            catrows = [[f'<code>{E(c["prop"])}</code>', f'<code>{E(c["term"])}</code>', E(c['rule'])] for c in x['cat']]
            rrows = []
            for r in x['rules']:
                pr = {k: v for k, v in r['params'].items() if k != 'inner'}
                params = ', '.join(f'{k}={v}' for k, v in pr.items()) + (f', inner={r["params"]["inner"]["check"]}({r["params"]["inner"]["column"]})' if 'inner' in r['params'] else '')
                row = [f'<span class="nowrap" id="{r["id"]}">{E(r["id"])}</span>', E(r['element']), E(r['rule']), E(r['dimension']), f'<code>{E(r["check"])}</code>', f'<code>{E(params)}</code>']
                rrows.append(row)
                all_rules.append(([f'<a href="#{r["id"]}">{E(r["id"])}</a>', E(x['title'])] + row[1:5], x['id'], r['dimension']))
            ids = ''.join(f'<li><strong>{E(i["name"])}</strong>: {E(i["format"])}{prov(i["prov"])}</li>' for i in x.get('identifiers', []))
            extra = ''
            if x.get('checks_from_guidance'):
                extra += (f'<h4>{icon("list-checks")} Self-assessment areas from the GOV.UK AI-ready data guidance{prov("V", self.m["verified_on"])}</h4>'
                          + ''.join(f'<details class="kc-answer"><summary>{E(a["area"])} ({len(a["items"])})</summary>{ul(a["items"], cls="checks")}</details>' for a in x['checks_from_guidance'])
                          + f'<p class="hint">Summarised from {self.rb_link("RB-AIREADY")}.</p>')
            if x.get('four_nations'):
                extra += (f'<h4>{icon("map")} Four nations view</h4>' + table(f't-4n-{x["id"]}', 'Who the policy applies to, by nation and tier', ['Who', 'Position'],
                          [[E(n['nation']), E(n['position']) + prov(n['prov'], self.m['verified_on'])] for n in x['four_nations']]) + f'<p class="hint">Source: {self.src_link("SRC-IDC")}</p>')
            checklist = ''.join(f'<li>{mark_done(cid, "Done")}<span>{E(c)}</span></li>' for cid, c in zip(cl_ids, x['checklist']))
            ids_html = f'<h4>{icon("tag")} Identifiers</h4><ul>{ids}</ul>' if ids else ''
            detail += f'''<section class="module supplement" id="{x["id"]}" aria-labelledby="h-{x["id"]}">
<div class="mod-head">{tile(x["icon"], "lg")}<div><p class="caption">{E(x["id"])} · from assessment <a href="library.html#{t["id"]}">{E(t["id"])}</a> · <strong class="moscow m-{slug(t["moscow"])}">{E(t["moscow"])} have</strong></p><h3 id="h-{x["id"]}">{E(x["title"])}</h3>{caps}</div></div>
<p class="lede">{E(x["summary"])}</p><p class="hint">For: {E("; ".join(t["sectors"]))}. A synthesis of the sources below{prov("O")}.</p>
<div class="cols"><div class="panel"><h4>{icon("shield-check")} Governance overlay</h4>{ul(x["gov"], cls="ticks")}</div>
<div class="panel"><h4>{icon("triangle-alert")} Risks to check</h4>{ul(x["risks"])}</div></div>
<h4>{icon("library-big")} Extra catalogue fields</h4>{table(f"t-cat-{x['id']}", f"Catalogue fields to add for {x['title'].lower()}", ["Field", "Suggested term", "How to record it"], catrows)}
<p class="hint">"Local extension" means no agreed cross-government term exists yet; record it in your catalogue's own field.{prov("K")}</p>
<h4>{icon("gauge")} Quality rule library</h4>{table(f"t-rules-{x['id']}", f"Starter quality rules for {x['title'].lower()}", ["ID", "Data element", "Rule", "Dimension", "Check", "Parameters"], rrows)}
<p><a href="data/rules/{x["id"].lower()}.yaml">{icon("download")}Download these rules for the Data Quality Commons kit (YAML)</a>. Column names are examples; map them to your data.</p>
{ids_html}{extra}
<div class="tip">{icon("lightbulb")}<p><strong>Worked example.</strong> {E(x["example"])}</p></div>
<h4>{icon("list-checks")} Checklist</h4>{progress_widget(cl_ids, "Checklist done")}<ol class="questions">{checklist}</ol>
<h4>{icon("scale")} Related rulebook</h4><ul>{"".join(f"<li>{self.rb_link(r)}</li>" for r in x["refs"])}</ul></section>'''
        rule_tbl = table('t-allrules', 'Every sector quality rule', ['ID', 'Supplement', 'Data element', 'Rule', 'Dimension', 'Check'],
                         [r[0] for r in all_rules], row_attrs=[f' data-item data-sup="{r[1]}" data-dim="{r[2]}"' for r in all_rules], tbody_id='rule-table')
        sup_opts = ''.join(f'<option value="{x["id"]}">{E(x["title"])}</option>' for x in d['supplements'])
        dims = ''.join(f'<option>{v}</option>' for v in ['completeness', 'uniqueness', 'consistency', 'timeliness', 'validity', 'accuracy'])
        body = self.hero('layers', 'Sector and domain supplements', 'Sector supplements', 'Extra governance, catalogue fields and quality rules for kinds of data the core playbooks treat only in general terms.',
                         brief=['Answer a few questions to see which supplements apply to your asset.', 'Each supplement adds to the three capabilities; it never replaces the core method.', 'Quality rules download in a format the Data Quality Commons kit can run.'],
                         meta=[('layers', f'{len(d["supplements"])} supplements'), ('gauge', f'{len(all_rules)} quality rules'), ('scale', 'Linked to the rulebook')])
        body += f'''<h2 id="which">{icon("compass")} Which supplements apply to your asset?</h2>
<div class="wizard js-only"><fieldset><legend>Tick everything that is true of the critical data asset</legend><ul class="plain">{qs}</ul></fieldset>
<div class="wizard-result"><h3>Supplements that apply</h3><div id="wizard-out" aria-live="polite">Tick a statement to see which supplements apply.</div></div></div>
<div class="no-js-only">{table("t-which", "Which supplements apply", ["If this is true of the asset", "Use these supplements"], nojs)}</div>
<h2 id="all">{icon("layers")} All supplements</h2>
<div class="filters" data-filter="sup-list" role="group" aria-label="Filter supplements"><div><label for="s-m">Priority</label><select id="s-m" name="moscow"><option value="">All</option><option value="must">Must have</option><option value="should">Should have</option><option value="could">Could have</option></select></div>
<div><label for="s-cap">Capability</label><select id="s-cap" name="cap"><option value="">All</option><option value="gov">Data governance</option><option value="cat">Data cataloguing</option><option value="dq">Data quality</option></select></div><p class="count-out" aria-live="polite"></p></div>
<ul class="mod-grid" id="sup-list">{cards}</ul>
<h2 id="rule-library">{icon("gauge")} Sector rule library</h2>
<p>Every rule across the supplements. Download them all as <a href="data/sector-rules.csv">CSV</a>, or each supplement's rules as YAML.</p>
<div class="filters" data-filter="rule-table" role="group" aria-label="Filter rules"><div><label for="ru-s">Supplement</label><select id="ru-s" name="sup"><option value="">All</option>{sup_opts}</select></div>
<div><label for="ru-d">Dimension</label><select id="ru-d" name="dim"><option value="">All</option>{dims}</select></div><div><label for="ru-q">Contains</label><input id="ru-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>
{rule_tbl}
<h2 id="detail">{icon("book-open")} Supplements in full</h2>{detail}'''
        drawer = [{'label': 'Sectors', 'icon': 'layers', 'items': [
            {'id': 'which', 'label': 'Which apply to you', 'icon': 'compass', 'count': len(d['applicability'])},
            {'id': 'all', 'label': 'All supplements', 'icon': 'layers', 'count': len(d['supplements'])},
            {'id': 'rule-library', 'label': 'Sector rule library', 'icon': 'gauge', 'count': len(all_rules), 'new': True}]},
                  {'label': 'Supplements', 'icon': 'book-open', 'items': [{'id': x['id'], 'label': x['title'], 'icon': x['icon']} for x in d['supplements']]}]
        return self.page('sectors', 'Sector supplements', body, drawer, crumbs=['Sectors'])

    # -- version 1.4: frameworks ------------------------------------------------------
    def finding_src(self, x):
        if x.get('src'):
            return f'<a href="{E(self.src[x["src"]]["url"])}">{E(self.src[x["src"]]["title"])}</a>'
        if x.get('rb'):
            return f'<a href="{E(self.rb[x["rb"]]["url"])}">{E(self.rb[x["rb"]]["title"])}</a>'
        if x.get('url'):
            return f'<a href="{E(x["url"])}">{E(x["url_title"])}</a>'
        return 'the live page named above'

    def doc_url(self, doc, a=None):
        base = self.src[doc]['url'] if doc in self.src else self.rb[doc]['url']
        return base + (f'#{a}' if a else '')

    def doc_title(self, doc):
        return self.src[doc]['title'] if doc in self.src else self.rb[doc]['title']

    def flag(self, f, short=False):
        name, meaning = FLAGS[f]
        return f'<abbr class="flag-badge f-{f}" title="{E(meaning)}">{E(f if short else name)}<span class="visually-hidden">: {E(meaning)}</span></abbr>'

    def cr_pill(self, cid):
        c = self.cr[cid]
        return f'<a class="pill" href="capability-model.html#{cid}">{E(cid)} {E(c["name"])}</a>'

    def role_pills(self, codes):
        return ' '.join(f'<a class="pill" href="together.html#role-{c}">{E(self.roles[c]["name"])}</a>' for c in codes)

    def skill_link(self, anchor, name=None):
        nm = name or next((s[0] for r in self.d['professions']['roles'] for s in r['skills'] if s[1] == anchor), anchor)
        return f'<a href="https://ddat-capability-framework.service.gov.uk/skills/#{E(anchor)}">{E(nm)}</a>'

    @staticmethod
    def stage_pills(ch, sid):
        return ' '.join(f'<a class="pill" href="#{x["id"]}">{E(x["id"])}</a>' for x in ch['items'] if x['stage'] == sid)

    @staticmethod
    def cr_ids(ids):
        return ' '.join(f'<a class="pill" href="capability-model.html#{c}">{E(c)}</a>' for c in ids) or 'all capabilities'

    def p_model(self):
        d, mt, v = self.d, self.d['maturity'], self.m['verified_on']
        cm = d['capmap']
        fc = {f: sum(1 for c in cm if c['flag'] == f) for f in FLAGS}
        new = [c for c in cm if c['coverage'] == 'New']
        legend = ''.join(f'<li>{self.flag(f)} <span>{E(FLAGS[f][1])} ({fc[f]})</span></li>' for f in FLAGS)
        # overview: capability house
        bands = ''
        for cl in CLUSTERS:
            items = [c for c in cm if c['cluster'] == cl]
            tiles = ''.join(f'<li class="cr-tile f-{c["flag"]}"><a href="#{c["id"]}">{icon(c["icon"])}<span class="cr-id">{E(c["id"])}</span><span class="cr-name">{E(c["name"])}</span>{self.flag(c["flag"], True)}</a></li>' for c in items)
            bands += f'<section class="cr-band" aria-labelledby="band-{slug(cl)}"><h3 id="band-{slug(cl)}">{icon(CLUSTER_ICONS[cl])} {E(cl)} <span class="count">{len(items)}</span></h3><ul class="cr-tiles">{tiles}</ul></section>'
        overview = f'''<p>The DAM Policy names three core capabilities, but meeting it depends on more. This model sets out <strong>{len(cm)} capabilities</strong> the policy, its guidance and adjacent rulebooks need, grouped in six clusters. Each is flagged by how the DAM Policy itself treats it.</p>
<ul class="flag-legend">{legend}</ul>
<div class="cr-house">{bands}</div>
<div class="tip">{icon("lightbulb")}<p><strong>Not yet accounted for elsewhere.</strong> {len(new)} capabilities are new in this release and are covered on the <a href="change.html">delivery and change</a>, <a href="professions.html">professions and skills</a> and this page: {E(", ".join(c["name"].lower() for c in new))}.</p></div>
<p class="hint">Grouping and flags are this portal's own analysis{prov("O")}; every clause they point to was checked on {E(v)}{prov("V", v)}.</p>'''
        # requirements map
        cards = ''
        for c in cm:
            dam = (f'<a href="{E(self.doc_url("SRC-DAM", c["dam"]))}">DAM Policy: {E(c["dam"].replace("-", " ").capitalize())}</a>' if c['dam'] else '<span>Not stated in the DAM Policy</span>')
            sgs = ''.join(f'<li>{self.flag(sg["flag"], True)} <a href="{E(self.doc_url(sg["doc"], sg["a"]))}">{E(sg["label"])}</a> <span class="hint">({E(self.doc_title(sg["doc"]))})</span></li>' for sg in c['signposts'])
            dma = ' '.join(f'<a class="pill" href="{E(mt["url"])}#{E(mt["topics"][t - 1]["anchor"])}">{t}. {E(mt["topics"][t - 1]["name"])}</a>' for t in c['dma'])
            sk = ', '.join(self.skill_link(k) for k in c['skills'])
            pr = ' '.join(f'<a class="pill" href="professions.html#{p}">{E(self.prof[p]["name"].split(" (")[0])}</a>' for p in c['profs'])
            cov = {'Covered': 'circle-check', 'Partial': 'circle', 'New': 'flag'}[c['coverage']]
            cards += f'''<li class="cr-card" id="{c["id"]}" data-item data-cluster="{slug(c["cluster"])}" data-flag="{c["flag"]}" data-cov="{c["coverage"].lower()}">
<div class="cr-head">{tile(c["icon"], "sm")}<div><p class="caption">{E(c["id"])} · {E(c["cluster"])}</p><h3>{E(c["name"])}</h3></div>{self.flag(c["flag"])}</div>
<p>{E(c["note"])}{prov(c["prov"])}</p>
<dl class="cr-dl"><dt>{icon("landmark")} Policy clause</dt><dd>{dam}</dd>
<dt>{icon("signpost")} Signposts</dt><dd><ul class="plain">{sgs}</ul></dd>
<dt>{icon("radar")} Maturity topics</dt><dd>{dma}</dd>
<dt>{icon("briefcase")} Skills</dt><dd>{sk} <span class="hint">(Digital and Data capability framework)</span></dd>
<dt>{icon("users-round")} Professions</dt><dd>{pr}</dd>
<dt>{icon("book-open")} Industry models</dt><dd>DAMA-DMBOK: {E("; ".join(c["dmbok"]))}. DCAM: {E("; ".join(c["dcam"]))}.{prov("K")}</dd>
<dt>{icon(cov)} In this portal</dt><dd><strong>{E(c["coverage"])}</strong>: <a href="{E(c["playbook"])}">{E({k: l for k, l, _ in NAV}.get(c["playbook"][:-5], c["playbook"]))}</a></dd></dl></li>'''
        cl_opts = ''.join(f'<option value="{slug(x)}">{E(x)}</option>' for x in CLUSTERS)
        reqmap = f'''<p>Filter by cluster, by how the policy treats the capability, or by how far this portal covers it. Download the map as <a href="data/capability-map.csv">CSV</a>.</p>
<div class="filters" data-filter="cr-list" role="group" aria-label="Filter capabilities"><div><label for="f-cl">Cluster</label><select id="f-cl" name="cluster"><option value="">All</option>{cl_opts}</select></div>
<div><label for="f-fl">In the DAM Policy</label><select id="f-fl" name="flag"><option value="">All</option><option value="E">Explicit</option><option value="I">Implicit</option><option value="N">Inferred</option></select></div>
<div><label for="f-cv">In this portal</label><select id="f-cv" name="cov"><option value="">All</option><option value="covered">Covered</option><option value="partial">Partial</option><option value="new">New in 1.4</option></select></div>
<div><label for="f-q">Contains</label><input id="f-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>
<ul class="cr-list" id="cr-list">{cards}</ul>'''
        # maturity
        th = ''.join(f'<th scope="col">{E(t["name"])}</th>' for t in mt['themes'])
        mx = max(n for t in mt['topics'] for n in t['rows'].values())
        rows = ''
        for t in mt['topics']:
            cells = ''.join(f'<td class="heat h{0 if not t["rows"][x["name"]] else min(4, 1 + (t["rows"][x["name"]] * 4) // (mx + 1))}">{t["rows"][x["name"]] or ""}<span class="visually-hidden">{" rows" if t["rows"][x["name"]] else "none"}</span></td>' for x in mt['themes'])
            rows += f'<tr><th scope="row"><a href="{E(mt["url"])}#{E(t["anchor"])}">{icon(t["icon"])} {t["n"]}. {E(t["name"])}</a></th>{cells}<td>{sum(t["rows"].values())}</td></tr>'
        total = sum(sum(t['rows'].values()) for t in mt['topics'])
        heat = (f'<div class="table-wrap" role="region" aria-labelledby="t-heat" tabindex="0"><table class="heatmap"><caption id="t-heat">Rows in the Data Maturity Assessment for Government, by topic and theme ({total} rows)</caption>'
                f'<thead><tr><th scope="col">Topic</th>{th}<th scope="col">Rows</th></tr></thead><tbody>{rows}</tbody></table></div>')
        ladder = ''.join(f'<li class="lv lv{i + 1}"><a href="{E(mt["url"])}#{E(mt["level_anchors"][i])}"><span class="lv-n">{i + 1}</span><span>{E(n)}</span></a></li>' for i, n in enumerate(mt['levels']))
        themes = ''.join(f'<li><strong>{E(t["name"])}</strong>: {E(t["gloss"])}</li>' for t in mt['themes'])
        srows = [[f'{icon(st["icon"])} {E(st["name"])}'] + [E(x) for x in st['levels']] for st in mt['strands']]
        maturity = f'''<p>Government's shared model is the <a href="{E(self.rb["RB-DMAF"]["url"])}">Data Maturity Assessment for Government</a>{prov("V", v)}: <strong>10 topics</strong>, each split into rows that belong to one of <strong>6 themes</strong>, and every row described at <strong>5 levels</strong>. Select a topic to read its rows on GOV.UK.</p>
<ol class="ladder" aria-label="Maturity levels">{ladder}</ol>
{heat}
<h3>{icon("layers")} The six themes</h3><ul>{themes}</ul><p class="hint">Themes summarised in this portal's words{prov("O")}.</p>
<div class="notice-box">{icon("scale")}<p><strong>Licence.</strong> The framework is published under {E(mt["licence"])}, which does not allow commercial reuse and requires adaptations to be shared alike. This portal therefore links to it and records only its structure (names and row counts). It does not copy the level descriptions. For use inside government, the framework asks organisations to contact the Central Digital and Data Office.</p></div>
<h3 id="strands">{icon("radar")} What each level looks like for the DAM Policy</h3>
<p>Indicators for four DAM strands, written for this portal{prov("O")} to sit alongside the government framework. They are not part of it.</p>
{table("t-strands", "DAM strand indicators by maturity level", ["Strand"] + [f"{i + 1}. {n}" for i, n in enumerate(mt["levels"])], srows)}'''
        # self-assessment
        sf = ''
        for st in mt['strands']:
            opts = ''.join(f'<label class="sa-opt"><input type="radio" name="sa-{st["id"]}" value="{i + 1}" data-sa="{st["id"]}"> <span><strong>{i + 1}. {E(mt["levels"][i])}</strong> {E(x)}</span></label>' for i, x in enumerate(st['levels']))
            sf += f'<fieldset class="sa"><legend>{icon(st["icon"])} {E(st["name"])}</legend>{opts}</fieldset>'
        tf = ''.join(f'<li><label for="sa-t{t["n"]}">{t["n"]}. {E(t["name"])}</label><select id="sa-t{t["n"]}" data-sa="t{t["n"]}"><option value="">Not assessed</option>'
                     + ''.join(f'<option value="{i + 1}">{i + 1}. {E(n)}</option>' for i, n in enumerate(mt['levels'])) + '</select></li>' for t in mt['topics'])
        selfa = f'''<p>A quick first pass, not a substitute for a full assessment. Choose the description closest to your organisation today. Answers are kept in this browser only and nothing is sent anywhere.</p>
<div class="sa-wrap"><div class="sa-forms"><h3>{icon("key-round")} DAM strands</h3>{sf}
<h3>{icon("radar")} Government maturity topics</h3><p class="hint">Read each topic's rows on GOV.UK first, then choose the level most rows match.</p><ul class="plain sa-topics">{tf}</ul></div>
<div class="sa-out js-only"><h3>{icon("chart-column")} Your profile</h3><div id="sa-chart" role="img" aria-label="Radar chart of your self-assessment">Choose levels to draw your profile.</div>
<div id="sa-summary" aria-live="polite"></div>
<p class="sa-actions"><a class="btn secondary" id="sa-csv" href="#" download="dam-self-assessment.csv">{icon("download")}Download as CSV</a> <button type="button" class="btn secondary" id="sa-print">{icon("printer")}Print</button> <button type="button" class="btn secondary" id="sa-clear">{icon("rotate-ccw")}Clear answers</button></p></div></div>'''
        # crosswalk
        cw = [[E(x['level']), E(x['cmmi']), E(x['iso8000']), E(x['note'])] for x in mt['crosswalk']]
        dmb = sorted({k for c in cm for k in c['dmbok']})
        dmb_rows = [[E(k), ' '.join(f'<a class="pill" href="#{c["id"]}">{E(c["id"])}</a>' for c in cm if k in c['dmbok'])] for k in dmb]
        dcm = sorted({k for c in cm for k in c['dcam']})
        dcm_rows = [[E(k), ' '.join(f'<a class="pill" href="#{c["id"]}">{E(c["id"])}</a>' for c in cm if k in c['dcam'])] for k in dcm]
        cross = f'''<p>How the government model lines up with widely used industry models. These are approximate alignments made for this portal{prov("O")}, using general knowledge of the industry models{prov("K")}; the owners of those models have not checked them.</p>
{table("t-cw", "Maturity levels compared", ["Government level", "CMMI level", "ISO 8000-61 process view", "Note"], cw)}
{table("t-dmbok", "DAMA-DMBOK knowledge areas and the capabilities that use them", ["Knowledge area", "Capabilities"], dmb_rows)}
{table("t-dcam", "DCAM components and the capabilities that use them", ["Component", "Capabilities"], dcm_rows)}
<p>Model owners: {self.rb_link("RB-DAMA")}; {self.rb_link("RB-DCAM")}; {self.rb_link("RB-CMMI")}.</p>'''
        tabs = [('cm-overview', 'Overview', overview), ('cm-map', 'Requirements map', reqmap), ('cm-maturity', 'Maturity model', maturity),
                ('cm-self', 'Self-assessment', selfa), ('cm-cross', 'Crosswalk', cross)]
        body = self.hero('radar', 'Frameworks', 'Capability model',
                         'Everything the DAM Policy and its related guidance need an organisation to be able to do, how each need is stated, and how mature you are.',
                         brief=[f'{fc["E"]} capabilities are explicit in the policy, {fc["I"]} implicit and {fc["N"]} inferred.', 'Every flag points to the section of GOV.UK guidance it comes from.', 'Assess yourself against the government maturity model and four DAM strands.'],
                         meta=[('radar', f'{len(cm)} capabilities'), ('signpost', f'{sum(len(c["signposts"]) for c in cm)} signposts'), ('layers', '10 topics, 6 themes, 5 levels')])
        body += self.tabbed(tabs, 'Capability model views')
        drawer = [{'label': 'Views', 'icon': 'radar', 'items': [{'id': k, 'label': l, 'icon': ic} for (k, l, _), ic in zip(tabs, ['grid-3x3', 'signpost', 'layers', 'chart-column', 'arrow-right-left'])]},
                  {'label': 'Clusters', 'icon': 'layers', 'items': [{'id': f'band-{slug(cl)}', 'label': cl, 'icon': CLUSTER_ICONS[cl], 'count': sum(1 for c in cm if c['cluster'] == cl)} for cl in CLUSTERS]}]
        return self.page('capability-model', 'Capability model', body, drawer, crumbs=['Frameworks', 'Capability model'], extra_json={'sa-data': {
            'levels': mt['levels'], 'strands': [{'id': s['id'], 'name': s['name']} for s in mt['strands']], 'topics': [{'id': f't{t["n"]}', 'name': t['name']} for t in mt['topics']]}})

    def p_professions(self):
        d, pf, v = self.d, self.d['professions'], self.m['verified_on']
        roles = {r['id']: r for r in pf['roles']}
        pers = {p['id']: p for p in d['personas']}
        LV = {'A': 'Awareness', 'W': 'Working', 'P': 'Practitioner', 'E': 'Expert', '-': 'Not listed'}

        def ref(x):
            return f'<a class="pill" href="#{x}">{E(self.prof[x]["name"].split(" (")[0])}</a>' if x in self.prof else self.rb_link(x)
        cards = ''
        for m in pf['persona_map']:
            p = pers[m['persona']]
            rl = ''.join(f'<li><a href="#role-{r}">{E(roles[r]["title"])}</a></li>' for r in m['roles']) or '<li>No single data role: see the skills data owners need below</li>'
            cards += (f'<li class="route-card"><div class="cr-head">{tile(p["icon"], "sm")}<h3><a href="personas.html#persona-{p["id"]}">{E(p["title"])}</a></h3></div>'
                      f'<h4>Framework roles</h4><ul class="plain">{rl}</ul><h4>Professions</h4><p>{" ".join(ref(x) for x in m["profs"])}</p>'
                      f'<h4>Start learning with</h4><ul class="plain">{"".join(f"<li>{self.rb_link(x)}</li>" for x in m["learn"])}</ul></li>')
        own_note = f'<p class="hint">Data owners: the data ownership model lists <a href="{E(self.doc_url("SRC-OWN", "skills-that-data-owners-need"))}">the skills data owners need</a>{prov("V", v)}.</p>'
        route = f'<p>Start from your role in the policy. Each card shows the closest roles in the Government Digital and Data capability framework, the professions to join, and where to start learning.</p><ul class="route-grid">{cards}</ul>{own_note}'
        # career pathways
        paths = ''
        for r in pf['roles']:
            if r['levels']:
                ladder = ''.join(f'<li class="lv lv{min(5, i + 2)}"><a href="{E(r["url"])}#{E(L["anchor"])}"><span class="lv-n">{i + 1}</span><span>{E(L["name"])}<span class="hint">{E(", ".join(L["grades"]))}</span></span></a></li>' for i, L in enumerate(r['levels']))
                hdr = ['Skill'] + [L['name'] for L in r['levels']]
                srows = [[self.skill_link(s[1], s[0])] + [f'<span class="sk sk-{x}" title="{LV[x]}">{LV[x]}</span>' for x in s[2].split()] for s in r['skills']]
                grid = table(f't-sk-{r["id"]}', f'Skills and levels for {r["title"].lower()} roles', hdr, srows)
            else:
                ladder = f'<li class="lv lv5"><a href="{E(r["url"])}"><span class="lv-n">SCS</span><span>{E(r["title"])}<span class="hint">{E(r.get("grades", ""))}</span></span></a></li>'
                grid = '<p>Skills for this role:</p>' + ul([self.skill_link(s[1], s[0]) for s in r['skills']], raw=True)
            paths += (f'<section class="pathway" id="role-{r["id"]}" aria-labelledby="h-role-{r["id"]}"><h3 id="h-role-{r["id"]}">{icon("route")} <a href="{E(r["url"])}">{E(r["title"])}</a></h3>'
                      f'<ol class="ladder" aria-label="Role levels for {E(r["title"].lower())}">{ladder}</ol>{grid}</section>')
        pathways = (f'<p>Roles from the <a href="{E(self.rb["RB-DDAT"]["url"])}">Government Digital and Data capability framework</a>{prov("V", v)} that carry DAM responsibilities. '
                    'Each shows its levels, the Civil Service grades they are most often done at, and the skill level needed at each step: awareness, working, practitioner or expert. Grades are typical, not mandatory.</p>'
                    + paths + f'<p>Download every role and skill as <a href="data/ddat-role-skills.csv">CSV</a>. Framework content is Crown copyright under the Open Government Licence.</p>')
        # professions
        pcards = ''
        for p in pf['profs']:
            used = [c['id'] for c in d['capmap'] if p['id'] in c['profs']]
            pcards += (f'<li class="cr-card" id="{p["id"]}"><div class="cr-head">{tile(p["icon"], "sm")}<div><p class="caption">{E(p["aligned"])}</p><h3>{E(p["name"])}</h3></div></div>'
                       f'<p>{E(p["why"])}</p><p>{self.rb_link(p["rb"])}</p><p class="hint">Supports: {self.cr_ids(used)}</p></li>')
        profs = (f'<p>Every civil servant should belong to at least one government profession. These are the ones most involved in data asset management. See the full list of {self.rb_link("RB-PROFS")}.</p>'
                 f'<ul class="cr-list two">{pcards}</ul>')
        # learning routes
        steps = ''
        for i, st in enumerate(pf['learning']):
            ids = [f'learn:{x}' for x in st['items']]
            items = ''.join(f'<li>{mark_done(f"learn:{x}", "Done")}<span>{self.rb_link(x)}</span></li>' for x in st['items'])
            steps += (f'<li class="lr-step"><div class="lr-head"><span class="lv-n">{i + 1}</span>{icon(st["icon"])}<h3>{E(st["stage"])}</h3>{status_tag(ids)}</div>'
                      f'<p>{E(st["note"])}</p><ul class="plain">{items}</ul></li>')
        allids = [f'learn:{x}' for st in pf['learning'] for x in st['items']]
        campus = ''.join(f'<li><a href="{E(c["url"])}">{E(c["name"])}</a></li>' for c in pf['campus'])
        learn = f'''<p>Four stages from awareness to leadership. Tick what you have done; progress is kept in this browser only.</p>
{progress_widget(sorted(set(allids)), "Learning route")}
<ol class="lr">{steps}</ol>
<h3>{icon("school")} Government Campus prospectus: data-related strands</h3><ul>{campus}</ul>
<div class="notice-box">{icon("info")}<p><strong>Signing in.</strong> Courses are booked through Civil Service Learning and the Government Skills Campus platform, which need a government account. This portal does not link to sign-in pages; your learning team can confirm which platform your organisation uses. Start from {self.rb_link("RB-GSKILLS")}.</p></div>'''
        # other frameworks
        sk_rows = [[f'<a href="capability-model.html#{c["id"]}">{E(c["id"])} {E(c["name"])}</a>', ', '.join(self.skill_link(k) for k in c['skills'])] for c in d['capmap']]
        others = ''.join(f'<li>{self.rb_link(x)}: {E(self.rb[x]["why"])}</li>' for x in ['RB-SFIA', 'RB-PKSB', 'RB-RSS', 'RB-DAMA', 'RB-APPDA', 'RB-SUCCESS', 'RB-AFCAREER', 'RB-GSS'])
        frame = f'''<h3>{icon("book-marked")} Other recognised frameworks</h3><ul>{others}</ul>
<h3>{icon("grid-3x3")} Skills each capability needs</h3>{table("t-crskills", "Digital and Data framework skills for each capability", ["Capability", "Skills"], sk_rows)}'''
        tabs = [('pf-route', 'By role in the policy', route), ('pf-paths', 'Career pathways', pathways), ('pf-profs', 'Professions', profs),
                ('pf-learn', 'Learning routes', learn), ('pf-frameworks', 'Skills frameworks', frame)]
        body = self.hero('briefcase', 'Frameworks', 'Professions and skills',
                         'The government professions, framework roles, skills and learning that sit behind each role in the DAM Policy.',
                         brief=['Find the framework roles and professions closest to your role in the policy.', 'See each career pathway with grades and skill levels.', 'Follow a learning route and track your progress.'],
                         meta=[('briefcase', f'{len(pf["roles"])} framework roles'), ('users-round', f'{len(pf["profs"])} professions'), ('graduation-cap', f'{len(set(allids))} learning resources')])
        body += self.tabbed(tabs, 'Professions and skills views')
        drawer = [{'label': 'Views', 'icon': 'briefcase', 'items': [{'id': k, 'label': l, 'icon': ic} for (k, l, _), ic in zip(tabs, ['users-round', 'route', 'building-2', 'graduation-cap', 'book-marked'])]},
                  {'label': 'Career pathways', 'icon': 'route', 'items': [{'id': f'role-{r["id"]}', 'label': r['title'], 'icon': 'route'} for r in pf['roles']]}]
        return self.page('professions', 'Professions and skills', body, drawer, crumbs=['Frameworks', 'Professions and skills'])

    def p_change(self):
        d, ch = self.d, self.d['change']
        stg = {s['id']: s for s in ch['stages']}
        strip = ''.join(f'<li class="lc-stage" id="stage-{s["id"]}"><div class="lc-head">{icon(s["icon"])}<h3>{E(s["name"])}</h3></div>{ul(ch["touchpoints"][s["id"]])}'
                        f'<p class="hint">{self.stage_pills(ch, s["id"])}</p></li>' for s in ch['stages'])
        cards, all_ids = '', []
        for x in ch['items']:
            ids = [f'{x["id"]}.a{i}' for i in range(len(x['actions']))]
            all_ids += ids
            acts = ''.join(f'<li>{mark_done(i, "Done")}<span>{E(a)}</span></li>' for i, a in zip(ids, x['actions']))
            refs = ''.join(f'<li>{self.rb_link(r)}</li>' for r in x['refs'])
            cards += f'''<li class="cr-card ch-card" id="{x["id"]}" data-item data-mode="{x["mode"].lower()} {"bau change" if x["mode"] == "Both" else ""}" data-stage="{x["stage"]}">
<div class="cr-head">{tile(x["icon"], "sm")}<div><p class="caption">{E(x["id"])} · {E({"BAU": "Business as usual", "Change": "Change programmes", "Both": "Business as usual and change"}[x["mode"]])} · {E(stg[x["stage"]]["name"])}</p><h3>{E(x["title"])}</h3></div>{status_tag(ids)}</div>
<p>{E(x["why"])}{prov(x["prov"])}</p>{progress_widget(ids, "Actions done")}
<h4>{icon("list-checks")} Actions</h4><ol class="questions">{acts}</ol>
<div class="cols"><div><h4>{icon("file-text")} Evidence</h4>{ul(x["evidence"])}</div><div><h4>{icon("users-round")} Roles</h4><p>{self.role_pills(x["roles"])}</p>
<h4>{icon("radar")} Capabilities</h4><p>{" ".join(self.cr_pill(c) for c in x["cr"])}</p></div></div>
{f'<h4>{icon("scale")} Rulebook</h4><ul>{refs}</ul>' if refs else ''}</li>'''
        gaps = [c for c in d['capmap'] if c['flag'] in ('I', 'N')]
        gap_rows = [[f'<a href="capability-model.html#{c["id"]}">{E(c["id"])}</a>', E(c['name']), self.flag(c['flag']), E(c['coverage']),
                     ' '.join(f'<a class="pill" href="#{x["id"]}">{E(x["id"])}</a>' for x in ch['items'] if c['id'] in x['cr']) or 'See the capability model'] for c in gaps]
        st_opts = ''.join(f'<option value="{s["id"]}">{E(s["name"])}</option>' for s in ch['stages'])
        body = self.hero('construction', 'Playbooks', 'Delivery and change',
                         'How to make the DAM Policy stick: in the yearly business-as-usual cycle, and inside the programmes and projects that create, change and retire data assets.',
                         brief=['Most critical data assets are created or replaced by change programmes, so controls belong in them.', 'Each item lists actions, evidence, roles and the rules behind it.', 'Tick actions as you go; progress stays in your browser.'],
                         meta=[('construction', f'{len(ch["items"])} practices'), ('list-checks', f'{len(all_ids)} actions'), ('workflow', f'{len(ch["stages"])} life cycle stages')])
        body += f'''<h2 id="gaps">{icon("flag")} What the policy leaves to you</h2>
<p>The policy states its requirements briefly. These capabilities are needed to meet it but are only implied, or not stated at all. They are where organisations most often need help.</p>
{table("t-gaps", "Implicit and inferred capabilities, and where this page helps", ["ID", "Capability", "In the policy", "Portal coverage", "Practices"], gap_rows)}
<h2 id="lifecycle">{icon("route")} DAM across the delivery life cycle</h2>
<p>Stages follow the GOV.UK Service Manual phases and the project delivery standard. Use it as an overlay on your own programme plan.</p>
<ol class="lc-strip">{strip}</ol>
<h2 id="practices">{icon("list-checks")} Practices</h2>{progress_widget(all_ids, "All practices")}
<div class="filters" data-filter="ch-list" role="group" aria-label="Filter practices"><div><label for="c-m">Setting</label><select id="c-m" name="mode"><option value="">All</option><option value="bau">Business as usual</option><option value="change">Change programmes</option></select></div>
<div><label for="c-s">Stage</label><select id="c-s" name="stage"><option value="">All</option>{st_opts}</select></div><div><label for="c-q">Contains</label><input id="c-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>
<ul class="cr-list" id="ch-list">{cards}</ul>
<p>Download every action as <a href="data/change-checklist.csv">CSV</a> to load into your own plan or tracker.</p>
<div class="notice-box">{icon("info")}<p>These practices are this portal's synthesis{prov("O")} of the rulebook entries listed with each one. They add no new requirements; where they differ from your department's own delivery or assurance rules, follow your department.</p></div>'''
        drawer = [{'label': 'Delivery and change', 'icon': 'construction', 'items': [
            {'id': 'gaps', 'label': 'What the policy leaves to you', 'icon': 'flag', 'count': len(gaps)},
            {'id': 'lifecycle', 'label': 'Across the life cycle', 'icon': 'route', 'count': len(ch['stages'])},
            {'id': 'practices', 'label': 'Practices', 'icon': 'list-checks', 'count': len(ch['items'])}]},
                  {'label': 'Practices', 'icon': 'list-checks', 'items': [{'id': x['id'], 'label': x['title'], 'icon': x['icon']} for x in ch['items']]}]
        return self.page('change', 'Delivery and change', body, drawer, crumbs=['Playbooks', 'Delivery and change'])

    def p_status(self):
        st = self.status
        if not st:
            body = self.hero('activity', 'Status', 'Status and health', 'No health run has been recorded for this build yet. The weekly run publishes its results here.')
            return self.page('status', 'Status and health', body, None, crumbs=['Status'])
        good = st['healthy']
        srows = [[E(x['title']), f'<strong class="status s-{"completed" if x["state"] == "ok" else "in-progress" if x["state"] == "unbaselined" else "not-started"}">{E(x["state"])}</strong>', E(x.get('updated') or '-'), E(x['detail'] or '-')] for x in st['sources']]
        prow = [[E(x['page']), f'{x["bytes"] / 1000:.0f} kB', 'Within envelope' if x['ok'] else 'Over envelope'] for x in st['pages']]
        # D-019: problems quote addresses; show the portal's own repository by role, not by its owner's account name
        repo_url = f'https://github.com/{self.m["repo"]}'
        probs = ul([p.replace(repo_url, "the portal's repository") for p in st['problems']]) if st['problems'] else '<p>No problems found.</p>'
        body = self.hero('activity', 'Status', 'Status and health', 'Results of the latest automated health run. It checks that sources are current, the review date has not passed and pages stay light.',
                         meta=[('circle-check' if good else 'triangle-alert', 'Healthy' if good else 'Needs attention'), ('clock', f'Run {st["generated"]}'), ('calendar-check', f'Review due {st["review_date"]}')])
        body += f'''<h2 id="problems">{icon("triangle-alert")} Problems</h2>{probs}
<p>Problems open an issue in the <a href="https://github.com/{E(self.m["repo"])}/issues?q=label%3Ahealth">repository's issue list</a> for a person to act on.</p>
<h2 id="sources">{icon("library")} Sources</h2>{table("t-src-health", "Source checks", ["Source", "State", "Last updated (GOV.UK)", "Detail"], srows)}
<h2 id="weight">{icon("gauge")} Page weight</h2><p>Envelope: {st["envelope_bytes"] // 1000} kB per page including shared files.</p>{table("t-weight", "Page weight", ["Page", "Weight", "Result"], prow)}
<h2 id="links">{icon("link")} External links</h2><p>{st.get("links_checked", 0)} links checked; {st.get("links_blocked", 0)} sites refused automated checking and {st.get("links_unavailable", 0)} were temporarily unavailable (neither counted as broken); {sum(1 for l in st.get("links", []) if l["state"] == "broken")} broken.</p>
<h2 id="signposts">{icon("signpost")} Signposted sections</h2><p>{sum(x["checked"] for x in st.get("anchors", []))} GOV.UK sections linked from the capability model checked across {len(st.get("anchors", []))} pages; {sum(len(x["missing"]) for x in st.get("anchors", []))} no longer found.</p>
<p>Machine-readable: <a href="data/status.json">status.json</a>.</p>'''
        drawer = [{'label': 'Status', 'icon': 'activity', 'items': [{'id': 'problems', 'label': 'Problems', 'icon': 'triangle-alert', 'count': len(st['problems'])},
                                                                     {'id': 'sources', 'label': 'Sources', 'icon': 'library', 'count': len(srows)},
                                                                     {'id': 'weight', 'label': 'Page weight', 'icon': 'gauge', 'count': len(prow)},
                                                                     {'id': 'links', 'label': 'External links', 'icon': 'link', 'count': st.get('links_checked', 0)}]}]
        return self.page('status', 'Status and health', body, drawer, crumbs=['Status'])

    def p_whats_new(self):
        cl = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        parts = re.split(r'^## ', cl, flags=re.M)[1:]
        rel = ''
        for ptxt in parts:
            head, *lines = ptxt.strip().split('\n')
            items = [l[2:] for l in lines if l.startswith('- ')]
            rel += f'<section class="release" id="v{slug(head)}"><h2>{icon("milestone")} {E(head)}</h2>{ul(items)}</section>'
        body = self.hero('milestone', "What's new", "What's new", 'Changes in each release, newest first. Releases are also listed on GitHub with their source code.')
        body += rel + f'<p><a href="https://github.com/{E(self.m["repo"])}/releases">{icon("download")}See all releases on GitHub</a></p>'
        return self.page('whats-new', "What's new", body, None, crumbs=["What's new"])

    def tabbed(self, tabs, label):
        tablist = ''.join(f'<button type="button" role="tab" id="tab-{k}" aria-controls="{k}" aria-selected="{"true" if i == 0 else "false"}" tabindex="{0 if i == 0 else -1}">{E(l)}</button>' for i, (k, l, _) in enumerate(tabs))
        panels = ''.join(f'<section role="tabpanel" id="{k}" aria-labelledby="tab-{k}" tabindex="0"{"" if i == 0 else " hidden"}>{b}</section>' for i, (k, l, b) in enumerate(tabs))
        return f'<div class="tabs"><div role="tablist" aria-label="{E(label)}">{tablist}</div>{panels}</div>'

    def p_design(self):
        ds = self.d['design']
        toc = ds['theory_of_change']
        chain = ''.join(f'<li class="toc-step" id="{c["id"]}"><h3>{E(c["stage"])}</h3>{ul(c["items"])}</li>' for c in toc['chain'])
        hyp = [[E(h['id']), E(h['statement']), E(h['falsified_if'])] for h in ds['research']['hypotheses']]
        bp = [[E(b['stage']), E(b['user']), E(b['front']), E(b['back']), E(b['support'])] for b in ds['blueprint']]
        req_rows = []
        for r in ds['requirements']:
            feats = ' '.join(f'<a class="pill" href="{f}.html">{E(f)}</a>' if f != 'all' else 'every page' for f in r['features'])
            req_rows.append([f'<span class="nowrap" id="{r["id"]}">{E(r["id"])}</span>', E(r['kind']), E(r['moscow']), E(r['text']), feats, E(', '.join(r['checks']))])
        comps = ''.join(f'<li id="{c["id"]}">{tile("layers", "sm")}<div><strong>{E(c["id"])} {E(c["name"])}</strong><br>{E(c["detail"])}</div></li>' for c in ds['architecture']['components'])
        flows = ul(ds['architecture']['flows'])
        stat = {'Met': 'completed', 'Partly': 'in-progress', 'Not yet': 'not-started'}
        ss = [[str(x['n']), E(x['point']), f'<strong class="status s-{stat[x["rating"]]}">{E(x["rating"])}</strong>', E(x['evidence'])] for x in ds['service_standard']]
        tabs = [
            ('theory', 'Theory of change', f'<h2 id="toc">{icon("route")} Theory of change</h2><p class="lede">{E(toc["problem"])}</p><ol class="toc-chain">{chain}</ol><h3>Assumptions to test</h3>{ul(toc["assumptions"])}'),
            ('research', 'Research plan', f'<h2 id="research-plan">{icon("user-search")} Research plan</h2><h3>Questions</h3>{ul(ds["research"]["questions"])}<h3>Methods</h3>{ul(ds["research"]["methods"])}'
             f'<h3>Hypotheses and how they would be disproved</h3>{table("t-hyp", "Hypotheses and falsification conditions", ["ID", "Hypothesis", "Disproved if"], hyp)}<h3>Ethics and consent</h3><p>{E(ds["research"]["ethics"])}</p>'),
            ('blueprint', 'Service blueprint', f'<h2 id="service-blueprint">{icon("workflow")} Service blueprint</h2>{table("t-bp", "Service blueprint: what the user does and what supports it", ["Stage", "User action", "Front stage", "Back stage", "Support process"], bp)}'),
            ('requirements', 'Requirements', f'<h2 id="traceability">{icon("list-checks")} Requirements and traceability</h2><p>Each requirement traces to the pages that meet it and the checks that prove it. Also available as <a href="data/traceability.csv">CSV</a>.</p>'
             f'{table("t-trace", "Requirements traced to features and checks", ["ID", "Kind", "MoSCoW", "Requirement", "Met by", "Proved by"], req_rows)}'
             '<p>Check prefixes: C static checks, B browser checks, HL the weekly health run, T-VAL build validation. Each is described on the About page and in the repository.</p>'),
            ('architecture', 'Architecture', f'<h2 id="solution-architecture">{icon("layers")} Solution architecture</h2><h3>Components</h3><ul class="icon-list">{comps}</ul><h3>Flows</h3>{flows}<h3>Data</h3><p>{E(ds["architecture"]["data"])}</p>'),
            ('standard', 'Service Standard', f'<h2 id="service-standard">{icon("badge-check")} Service Standard self-assessment</h2><div class="warning" role="note">{icon("triangle-alert")}<span>Self-assessed against the <a href="{E(self.rb["RB-SVC"]["url"])}">Service Standard</a>. It has not been through a service assessment and claims no conformance.</span></div>'
             f'{table("t-ss", "Service Standard self-assessment", ["Point", "Standard", "Self-rating", "Evidence"], ss)}'),
        ]
        body = self.hero('workflow', 'How the portal is designed', 'Service design and architecture', 'The design artefacts behind this portal: why it exists, how it will be tested with users, how it works and how each requirement is proved.',
                         brief=['Every requirement traces to the pages that meet it and the checks that prove it.', 'The research plan says how each assumption could be proved wrong.', 'The Service Standard rating is a self-assessment, not an assessment.'])
        body += self.tabbed(tabs, 'Design artefacts')
        drawer = [{'label': 'Service design', 'icon': 'workflow', 'items': [
            {'id': 'toc', 'label': 'Theory of change', 'icon': 'route', 'count': len(toc['chain'])},
            {'id': 'research-plan', 'label': 'Research plan', 'icon': 'user-search', 'count': len(ds['research']['hypotheses'])},
            {'id': 'service-blueprint', 'label': 'Service blueprint', 'icon': 'workflow', 'count': len(bp)},
            {'id': 'traceability', 'label': 'Requirements', 'icon': 'list-checks', 'count': len(req_rows)},
            {'id': 'solution-architecture', 'label': 'Architecture', 'icon': 'layers', 'count': len(ds['architecture']['components'])},
            {'id': 'service-standard', 'label': 'Service Standard', 'icon': 'badge-check', 'count': len(ss)}]}]
        return self.page('design', 'Service design and architecture', body, drawer, crumbs=['Service design'])

    @staticmethod
    def _year(*vals):
        for v in vals:
            m = re.search(r'(19|20)\d\d', str(v or ''))
            if m:
                return m.group(0)
        return 'n.d.'

    def citations(self):
        acc = '5 November 2026'
        items = [(s['publisher'], self._year(s.get('dates')), s['title'], s['url'], s['id']) for s in self.d['sources']]
        items += [(x['publisher'], self._year(x.get('updated')), x['title'], x['url'], x['id']) for x in self.d['rulebook']]
        items.sort(key=lambda t: (t[0].lower(), t[2].lower()))
        def shown(u):
            # addresses on a personal GitHub Pages host are linked but not printed, so no account name appears in the text (C-17)
            return 'GitHub Pages' if '.github.io/' in u else u
        return ''.join(f'<li id="cite-{E(i)}">{E(pub)} ({E(y)}) <cite>{E(t)}</cite>. Available at: <a href="{E(u)}">{E(shown(u))}</a> (Accessed: {acc}).</li>' for pub, y, t, u, i in items), len(items)

    def p_notices(self):
        d = self.d
        notes = ''.join(f'<section class="notice" id="{n["id"]}"><h3>{icon("info")} {E(n["title"])}</h3><p>{E(n["text"])}</p></section>' for n in d['notices'])
        cred = [[E(c['who']), E(c['what']), E(c['licence'])] for c in d['credits']]
        cites, ncite = self.citations()
        body = self.hero('scale', 'Notices', 'Disclaimers, credits and citations', 'What this portal is and is not, who and what it relies on, and a full citation for every source.',
                         brief=['This is a prototype, not official guidance or legal advice.', 'Do not submit personal data or anything above OFFICIAL.', 'Every source is cited in full, with the date it was accessed.'])
        body += f'''<h2 id="disclaimers">{icon("triangle-alert")} Disclaimers and transparency notices</h2>{notes}
<h2 id="attribution">{icon("file-text")} Attribution</h2><p>{E(d["attribution_statement"])} Material quoted or summarised from GOV.UK is Crown copyright. Re-use it under the <a href="{E(self.m["licence_content_url"])}">Open Government Licence v3.0</a>.</p>
<h2 id="credits">{icon("award")} Credits and acknowledgements</h2>{table("t-credits", "Credits and licences", ["Who", "What we use", "Licence"], cred)}
<h2 id="citations">{icon("library")} Citations ({ncite})</h2><p>Sources and rulebook entries, by publisher. Accessed dates are the date of verification for this release.</p><ol class="citations">{cites}</ol>'''
        drawer = [{'label': 'Notices', 'icon': 'scale', 'items': [
            {'id': 'disclaimers', 'label': 'Disclaimers and notices', 'icon': 'triangle-alert', 'count': len(d['notices'])},
            {'id': 'attribution', 'label': 'Attribution', 'icon': 'file-text'},
            {'id': 'credits', 'label': 'Credits', 'icon': 'award', 'count': len(cred)},
            {'id': 'citations', 'label': 'Citations', 'icon': 'library', 'count': ncite}]}]
        return self.page('notices', 'Disclaimers, credits and citations', body, drawer, crumbs=['Notices'])

    def p_accessibility(self):
        m = self.m
        body = f'''<h1>Accessibility statement for the DAM capability playbooks</h1>
<p>The maintainers of this portal are committed to making it accessible, in accordance with the Public Sector Bodies (Websites and Mobile Applications) (No. 2) Accessibility Regulations 2018.</p>
<p>This accessibility statement applies to the <a href="index.html">DAM capability playbooks website</a> and all its pages.</p>
<p>You should be able to change colours, text size and line spacing using Display options; zoom up to 400% without the text spilling off the screen; navigate the whole website using just a keyboard; and use it with a screen reader. Every page can be read with scripts turned off.</p>
<h2 id="compliance">Compliance status</h2>
<p>This website is partially compliant with the Web Content Accessibility Guidelines version 2.2 AA standard, due to the non-compliances listed below.</p>
<h2 id="non-accessible">Non-accessible content</h2>
<p>The content listed below is non-accessible for the following reasons.</p>
<h3>Non-compliance with the accessibility regulations</h3>
<ul><li>The website has not yet been tested by disabled people or with assistive technology in person. Automated testing cannot find every issue, so some may remain against any success criterion (open item OR-09).</li>
<li>The knowledge graph on the Knowledge page is a visual diagram. Its shapes can be reached with a keyboard and have names, but the layout is not meaningful to screen reader users. The same relationships are available as tables on the policy and capability pages (success criterion 1.3.1).</li></ul>
<h3>Content that is not within the scope of the accessibility regulations</h3>
<p>Pages on GitHub that this website links to, including the contact form and Discussions, are run by GitHub and are not covered by this statement.</p>
<h2 id="preparation">Preparation of this accessibility statement</h2>
<p>This statement was prepared on 5 November 2026. It was last reviewed on {E(m["as_of"])}.</p>
<p>The website was evaluated by self-assessment. Every page is tested on each change with axe-core against WCAG 2.2 A and AA rules in light and dark modes, for sideways scrolling at six widths from 320 to 1920 pixels, for keyboard use of search, menus, tabs and the contact form, and with scripts turned off. Each of these tests is shown to fail on a deliberate break before it is trusted.</p>
<h2 id="feedback">Feedback and contact information</h2>
<p>If you find a problem or need information on this website in a different format, use the <a href="contact.html">contact form</a> and choose "An accessibility problem". If you cannot use the form, ask a colleague to send it for you. We aim to reply within 10 working days.</p>
<h2 id="enforcement">Enforcement procedure</h2>
<p>The Equality and Human Rights Commission (EHRC) is responsible for enforcing the Public Sector Bodies (Websites and Mobile Applications) (No. 2) Accessibility Regulations 2018 (the 'accessibility regulations'). If you're not happy with how we respond to your complaint, contact the <a href="https://www.equalityadvisoryservice.com/">Equality Advisory and Support Service (EASS)</a>.</p>
<p>This statement follows the <a href="{E(self.rb["RB-MODEL"]["url"])}">GOV.UK model accessibility statement</a>.</p>'''
        return self.page('accessibility', 'Accessibility statement', body, None, crumbs=['Accessibility statement'])

    def p_404(self):
        return self.page('404', 'Page not found', '<h1>Page not found</h1><p>If you typed the address, check it is correct.</p><p><a href="index.html">Go to the home page</a> or press Ctrl and K to search.</p>')

    # -- exports ---------------------------------------------------------------------
    def exports(self):
        d, m, out = self.d, self.m, self.out / 'data'
        if self.status:
            (out / 'status.json').write_text(json.dumps(self.status, indent=1), encoding='utf-8')
        (out / 'playbooks.json').write_text(json.dumps({k: v for k, v in d.items() if not k.startswith('_')}, indent=1, ensure_ascii=False, default=str), encoding='utf-8')

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
        write_csv('traceability.csv', ['requirement', 'kind', 'moscow', 'text', 'features', 'checks'],
                  [[r['id'], r['kind'], r['moscow'], r['text'], ' '.join(r['features']), ' '.join(r['checks'])] for r in d['design']['requirements']])
        write_csv('sector-rules.csv', ['supplement', 'rule_id', 'element', 'rule', 'dimension', 'check', 'params'],
                  [[x['id'], r['id'], r['element'], r['rule'], r['dimension'], r['check'], json.dumps(r['params'], sort_keys=True)] for x in d['supplements'] for r in x['rules']])
        (out / 'rules').mkdir(exist_ok=True)
        for x in d['supplements']:
            doc = {'asset': {'id': f'example-{slug(x["title"])}', 'title': f'Starter rules: {x["title"]} (adapt column names to your data)', 'owner': 'Your organisation', 'importance': 3},
                   'rules': [dict({'id': r['id'], 'check': r['check'], 'description': r['rule'], 'dimension': r['dimension']}, **r['params']) for r in x['rules']]}
            (out / 'rules' / f'{x["id"].lower()}.yaml').write_text(
                f'# {x["title"]}: starter quality rules in the Data Quality Commons (dqkit) format.\n# Generated from content/playbooks.yaml. Column names are examples; map them to your own data.\n'
                + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding='utf-8')
        write_csv('rulebook.csv', ['id', 'group', 'title', 'publisher', 'url', 'updated', 'provenance', 'capabilities'],
                  [[x['id'], x['group'], x['title'], x['publisher'], x['url'], x.get('updated') or '', x['prov'], ' '.join(x['caps'])] for x in d['rulebook']])
        if 'capmap' in d:
            write_csv('capability-map.csv', ['id', 'capability', 'cluster', 'flag', 'flag_meaning', 'dam_policy_section', 'signposts', 'dma_topics', 'dmbok', 'dcam', 'ddat_skills', 'professions', 'portal_coverage', 'note'],
                      [[c['id'], c['name'], c['cluster'], FLAGS[c['flag']][0], FLAGS[c['flag']][1], (self.src['SRC-DAM']['url'] + '#' + c['dam']) if c['dam'] else '',
                        ' | '.join(f"{sg['label']} ({FLAGS[sg['flag']][0]}): {self.doc_url(sg['doc'], sg['a'])}" for sg in c['signposts']),
                        ' '.join(str(t) for t in c['dma']), '; '.join(c['dmbok']), '; '.join(c['dcam']), ' '.join(c['skills']), ' '.join(c['profs']), c['coverage'], c['note']] for c in d['capmap']])
            write_csv('ddat-role-skills.csv', ['role', 'role_url', 'skill', 'skill_url', 'levels_by_role_level'],
                      [[r['title'], r['url'], s[0], 'https://ddat-capability-framework.service.gov.uk/skills/#' + s[1], s[2]] for r in d['professions']['roles'] for s in r['skills']])
            write_csv('change-checklist.csv', ['id', 'title', 'mode', 'stage', 'action', 'roles', 'rulebook', 'capabilities'],
                      [[x['id'], x['title'], x['mode'], x['stage'], a, ' '.join(x['roles']), ' '.join(x['refs']), ' '.join(x['cr'])] for x in d['change']['items'] for a in x['actions']])
            write_csv('maturity-structure.csv', ['topic', 'topic_name', 'section_url'] + [t['name'] for t in d['maturity']['themes']],
                      [[t['n'], t['name'], d['maturity']['url'] + '#' + t['anchor']] + [t['rows'][th['name']] for th in d['maturity']['themes']] for t in d['maturity']['topics']])
        write_csv('metadata-dictionary.csv', ['property', 'mem_slot', 'obligation', 'rule'],
                  [[x['prop'], x['mem'], x['obligation'], x['rule']] for x in self.caps['cat']['metadata']])
        base = m['site_url'] + 'vocab#'

        def lit(s):
            return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"@en-GB'
        ttl = ['@prefix skos: <http://www.w3.org/2004/02/skos/core#> .', '@prefix dcterms: <http://purl.org/dc/terms/> .', f'@prefix dcp: <{base}> .', '',
               f'dcp:scheme a skos:ConceptScheme ; dcterms:title "{m["title"]} vocabulary"@en-GB ; dcterms:modified "{m["as_of"]}" .', '']
        for c in d['concepts']:
            parts = [f'dcp:{c["id"]} a skos:Concept', 'skos:inScheme dcp:scheme', f'skos:prefLabel {lit(c["term"])}', f'skos:definition {lit(c["def"])}']
            parts += [f'skos:altLabel {lit(a)}' for a in (c.get('alt') or [])]
            parts.append(f'skos:broader dcp:{c["broader"]}' if c['broader'] else 'skos:topConceptOf dcp:scheme')
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
               'dcterms:modified': m['as_of'], 'dcat:contactPoint': {'@type': 'http://www.w3.org/2006/vcard/ns#Kind', 'http://www.w3.org/2006/vcard/ns#hasURL': m['site_url'] + 'contact.html'},
               'dcat:resource': [{'@id': s['url'], '@type': 'dcat:Resource', 'dcterms:title': s['title'], 'dcterms:publisher': s['publisher'],
                                  'dcterms:type': s['type'], 'dcterms:description': s['note']} for s in d['sources']]
               + [{'@id': x['url'], '@type': 'dcat:Resource', 'dcterms:title': x['title'], 'dcterms:publisher': x['publisher'],
                   'dcterms:type': x['group'], 'dcterms:description': x['why']} for x in d['rulebook']]}
        (out / 'catalogue.jsonld').write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding='utf-8')
        sm = ''.join(f'<url><loc>{m["site_url"]}{"" if k == "index" else k + ".html"}</loc><lastmod>{m["as_of"]}</lastmod></url>' for k in [x[0] for x in NAV] + ['contact', 'status', 'whats-new', 'design', 'notices', 'accessibility'])
        (self.out / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding='utf-8')


def make_images(assets, m):
    """Favicon PNGs and the social sharing image, drawn with Pillow from the same design as favicon.svg."""
    from PIL import Image, ImageDraw, ImageFont
    navy, bars = (11, 38, 83), [(143, 193, 234), (127, 211, 166), (242, 178, 122)]

    def mark(size):
        im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 6, fill=navy)
        for i, col in enumerate(bars):
            y0 = size * (0.22 + i * 0.22)
            dr.rounded_rectangle([size * 0.2, y0, size * 0.8, y0 + size * 0.14], radius=max(1, size // 20), fill=col)
        return im
    mark(32).save(assets / 'favicon-32.png')
    mark(180).save(assets / 'apple-touch-icon.png')
    og = Image.new('RGB', (1200, 630), navy)
    og.paste(mark(220), (80, 205), mark(220))
    dr = ImageDraw.Draw(og)
    f1, f2 = ImageFont.load_default(size=58), ImageFont.load_default(size=32)
    y = 170
    for line in ['Data Asset Management (DAM)', 'capability playbooks']:
        dr.text((350, y), line, font=f1, fill=(255, 255, 255)); y += 76
    y += 20
    for line in ['Data governance, data cataloguing and', 'data quality for critical data assets']:
        dr.text((350, y), line, font=f2, fill=(210, 226, 241)); y += 44
    og.save(assets / 'og-image.png', optimize=True)


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
    print(f'Built {Site(d, a.out).build()} into {a.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
