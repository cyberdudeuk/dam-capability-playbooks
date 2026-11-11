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
    resolve_workbooks(d)
    validate(d)
    return d


TEMPLATE_MODES = {'BAU': 'Business as usual', 'Change': 'Change programmes', 'Both': 'Business as usual and change'}


def resolve_workbooks(d):
    """A workbook template (version 1.11.0) is a set of tabs. A tab either lists its own fields or reuses another
    template's fields with 'from', so a log defined once is never retyped. Its flat field list is 'Tab: field'."""
    tm = {t['id']: t for c in d['capabilities'] for t in c.get('templates', [])}
    for t in tm.values():
        if not t.get('sheets'):
            continue
        for sh in t['sheets']:
            if 'from' in sh:
                if sh['from'] not in tm or tm[sh['from']].get('sheets'):
                    raise ContentError(f"{t['id']}: tab {sh['name']} reuses unknown or workbook template {sh['from']}")
                sh['fields'] = list(tm[sh['from']]['fields'])
            if not sh.get('fields'):
                raise ContentError(f"{t['id']}: tab {sh['name']} has no fields")
        t['fields'] = [f"{sh['name']}: {f}" for sh in t['sheets'] for f in sh['fields']]



def write_ods(path, sheets):
    """A minimal OpenDocument spreadsheet (version 1.11.0): one tab per sheet with a header row, written
    without third-party libraries and with fixed timestamps, so the same content always gives the same bytes."""
    import zipfile
    from xml.sax.saxutils import escape as xesc

    def row(cells):
        return '<table:table-row>' + ''.join(f'<table:table-cell office:value-type="string"><text:p>{xesc(c)}</text:p></table:table-cell>' for c in cells) + '</table:table-row>'
    tables = ''.join(f'<table:table table:name="{xesc(name, {chr(34): "&quot;"})}"><table:table-column table:number-columns-repeated="{len(fields)}"/>{row(fields)}</table:table>' for name, fields in sheets)
    ns = ('xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
          'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"')
    content = f'<?xml version="1.0" encoding="UTF-8"?><office:document-content {ns} office:version="1.3"><office:body><office:spreadsheet>{tables}</office:spreadsheet></office:body></office:document-content>'
    styles = f'<?xml version="1.0" encoding="UTF-8"?><office:document-styles {ns} office:version="1.3"/>'
    manifest = ('<?xml version="1.0" encoding="UTF-8"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                '<manifest:file-entry manifest:full-path="/" manifest:media-type="application/vnd.oasis.opendocument.spreadsheet"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/></manifest:manifest>')
    with zipfile.ZipFile(path, 'w') as z:
        for name, data, method in [('mimetype', 'application/vnd.oasis.opendocument.spreadsheet', zipfile.ZIP_STORED),
                                   ('content.xml', content, zipfile.ZIP_DEFLATED), ('styles.xml', styles, zipfile.ZIP_DEFLATED),
                                   ('META-INF/manifest.xml', manifest, zipfile.ZIP_DEFLATED)]:
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = method
            z.writestr(zi, data)

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
        for t in c.get('templates', []):
            reg(t['id'], 'templates')
            if t.get('mode') not in TEMPLATE_MODES:
                errs.append(f"{t['id']}: mode must be one of {', '.join(TEMPLATE_MODES)}")
    for c in d['capabilities']:
        if 'metadata' not in c:
            continue
        det = {x['prop']: x for x in c.get('metadata_detail', [])}
        vls = {v['id'] for v in c.get('value_lists', [])}
        for x in c['metadata']:
            if x['prop'] not in det:
                errs.append(f"metadata {x['prop']}: no data dictionary detail (type, format, cardinality, example)")
        for k, x in det.items():
            # An unquoted comma in a YAML flow mapping silently makes a stray key with no value (found while writing 1.11.0).
            stray = set(x) - {'prop', 'type', 'format', 'card', 'values', 'example'}
            missing = {'type', 'format', 'card', 'example'} - set(x)
            if stray or missing or any(v in (None, '') for v in x.values()):
                errs.append(f"metadata_detail {k}: unexpected keys {sorted(stray)} or missing {sorted(missing)}; quote any value that contains a comma")
            if k not in {m['prop'] for m in c['metadata']}:
                errs.append(f"metadata_detail {k}: not a metadata property")
            if x.get('values') and x['values'] not in vls:
                errs.append(f"metadata_detail {k}: unknown value list {x['values']}")
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
        if r['code'] not in ROLE_ICONS: errs.append(f"role {r['code']}: no icon chosen")
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
    pages_known = {k for k, _, _ in NAV} | {'contact', 'status', 'whats-new', 'all', 'data', 'test', 'guide', 'site-map', 'reuse', 'research', 'involve'}
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
    for x in d.get('lenses', {}).get('items', []):
        for r in x['refs']:
            if r not in rb: errs.append(f"{x['id']}: unknown rulebook entry {r}")
        for r in x['cr']:
            if r not in crs: errs.append(f"{x['id']}: unknown capability {r}")
        for r in x['ch']:
            if r not in {c['id'] for c in d['change']['items']}: errs.append(f"{x['id']}: unknown practice {r}")
        for p in x['profs']:
            if p not in profs: errs.append(f"{x['id']}: unknown profession {p}")
        for k in ('cover_before', 'cover_now', 'actions'):
            if set(x[k]) != set(d['lenses']['caps_order']): errs.append(f"{x['id']}: {k} must cover every capability")
        for v in list(x['cover_before'].values()) + list(x['cover_now'].values()):
            if v not in ('Strong', 'Partial', 'Gap'): errs.append(f"{x['id']}: bad coverage {v}")
    if 'dama' in d:
        pids = {p['id'] for p in d['personas']}
        names = {k for c in d['capmap'] for k in c['dmbok']}
        for a in d['dama']['areas']:
            if set(a['uses']) != pids: errs.append(f"{a['id']}: role guidance must cover every persona")
        for r in d['dama']['im_refs']:
            if r not in rb: errs.append(f"dama: unknown rulebook entry {r}")
        for k in names - {a['dmbok'] for a in d['dama']['areas']}: errs.append(f"capability model uses knowledge area '{k}' that is not on the wheel")
    for r in d.get('change', {}).get('programme_roles', {}).get('rows', []):
        if r['role'] not in roles: errs.append(f"programme role {r['role']}: unknown role")
        for w in r['works_with']:
            if w not in roles: errs.append(f"programme role {r['role']}: unknown role {w}")
        for x in r['refs']:
            if x not in rb: errs.append(f"programme role {r['role']}: unknown rulebook entry {x}")
    for x in d.get('joinup', {}).get('recs', []):
        for w in x['who']:
            if w not in roles: errs.append(f"{x['id']}: unknown role {w}")
    for c in d.get('joinup', {}).get('communities', []):
        for p in c['for_']:
            if p not in {pp['id'] for pp in d['personas']}: errs.append(f"community {c['name']}: unknown persona {p}")
        if not c['url'].startswith('https://'): errs.append(f"community {c['name']}: url must be https")
    if 'related' in d:
        R = d['related']
        pids = {p['id'] for p in R['portals']}
        for p in R['portals']:
            if not p['url'].startswith('https://') or not p['url'].endswith('/'): errs.append(f"related portal {p['id']}: url must be https and end with /")
        for page, items in R['placements'].items():
            if page not in {k for k, _, _ in NAV} | {'contact', 'status', 'whats-new', 'data', 'test', 'guide', 'site-map', 'reuse', 'research', 'involve'}: errs.append(f"related: unknown page {page}")
            for it in items:
                if it['portal'] not in pids: errs.append(f"related on {page}: unknown portal {it['portal']}")
                if '://' in it['path'] or it['path'].startswith('/'): errs.append(f"related on {page}: path must be relative to the portal")
    if 'tooling' in d:
        T = d['tooling']
        pids = {x['id'] for x in T['patterns']}
        areas = {a['id'] for a in d.get('dama', {}).get('areas', [])}
        mats = {'Established', 'Emerging', 'Vendor-specific'}
        for c in T['categories']:
            for r in c['standards']:
                if r not in rb: errs.append(f"{c['id']}: unknown rulebook entry {r}")
            for x in c['patterns']:
                if x not in pids: errs.append(f"{c['id']}: unknown integration pattern {x}")
            for a in c['dama']:
                if a not in areas: errs.append(f"{c['id']}: unknown DAMA area {a}")
        for x in T['pairs']:
            if x['maturity'] not in mats: errs.append(f"tooling pair {x['between']}: maturity must be one of {sorted(mats)}")
        for x in T['patterns']:
            if x['risk'] not in ('low', 'medium', 'high'): errs.append(f"{x['id']}: risk must be low, medium or high")
    if 'testing' in d:
        tids = [x['id'] for x in d['testing']['tasks']]
        if len(tids) != len(set(tids)): errs.append('duplicate testing task ids')
        for x in d['testing']['tasks']:
            for r in x['roles']:
                if r != 'all' and r not in personas: errs.append(f"{x['id']}: unknown role {r}")
            page = x['start'].split('#')[0]
            if page[:-5] not in {k for k, _, _ in NAV} | {'contact', 'data', 'test'}: errs.append(f"{x['id']}: unknown start page {page}")
    mt = d['maturity']
    if len(mt['topics']) != 10 or len(mt['levels']) != 5: errs.append('maturity: expected 10 topics and 5 levels')
    for st in mt['strands']:
        if len(st['levels']) != 5: errs.append(f"maturity strand {st['id']}: needs 5 level indicators")
        for r in st['cr']:
            if r not in crs: errs.append(f"maturity strand {st['id']}: unknown capability {r}")
    validate_research(d, errs, rb)
    validate_involvement(d, errs)


# ---------------------------------------------------------------------------
# Version 1.9: research, roadmap, backlog and ideas, in the open
# ---------------------------------------------------------------------------
RESEARCH_STATUS = {'now': 'Now', 'next': 'Next', 'later': 'Later', 'done': 'Done', 'out': 'Out of scope'}
RESEARCH_TYPES = {'feature': 'Feature', 'research': 'Research', 'content': 'Content', 'decision': 'Decision'}
SIGNUP_HOSTS = ('https://forms.cloud.microsoft/', 'https://forms.office.com/', 'https://forms.microsoft.com/', 'https://forms.service.gov.uk/')


def vote_band(votes, bands):
    """Demand score earned by votes: the highest band whose threshold the votes reach."""
    return max([b for t, b in bands if votes >= t] or [0])


def research_score(item, R, ideas=None):
    """Score out of 100: each criterion scored 0 to 3, weighted, summed. Votes can raise demand, never lower it."""
    a = dict(item['assess'])
    v = (ideas or {}).get(item.get('idea'), {}).get('votes', 0) if item.get('idea') else 0
    a['demand'] = max(a['demand'], vote_band(v, R['vote_bands']))
    score = round(sum(c['weight'] * a[c['id']] / 3 for c in R['criteria']))
    band = next(b for m, b, _ in R['bands'] if score >= m)
    return score, band, a, v


def validate_research(d, errs, rb):
    R = d.get('research')
    if not R:
        return
    src = {s['id'] for s in d['sources']}
    orr = {x['id'] for x in d.get('open_register', [])}
    hyp = {h['id'] for h in d.get('design', {}).get('research', {}).get('hypotheses', [])}
    crit = [c['id'] for c in R['criteria']]
    if sum(c['weight'] for c in R['criteria']) != 100: errs.append('research: criteria weights must sum to 100')
    if len(crit) != len(set(crit)) or 'demand' not in crit: errs.append('research: criteria ids must be unique and include demand')
    for c in R['criteria']:
        if len(c['scale']) != 4: errs.append(f"research criterion {c['id']}: scale needs 4 points, 0 to 3")
    url = R['signup']['url']
    if url and not url.startswith(SIGNUP_HOSTS): errs.append('research: sign-up must be a private form (Microsoft Forms or GOV.UK Forms), never GitHub')
    for k in ('new_url', 'list_url'):
        if '://' in R['ideas'][k] or not R['ideas'][k].startswith('discussions/'): errs.append(f'research ideas {k}: must be a path in this repository\'s discussions')
    mids = {m['id'] for m in R['methods']}
    for r in R['rounds']:
        if r['status'] not in ('now', 'next', 'later', 'done'): errs.append(f"{r['id']}: bad status")
        for m in r['methods']:
            if m not in mids: errs.append(f"{r['id']}: unknown method {m}")
        for h in r['answers']:
            if h not in hyp: errs.append(f"{r['id']}: unknown hypothesis {h}")
    sids = {s['id'] for s in R['strategies']}
    for s in R['strategies']:
        if s['ref'] and s['ref'] not in rb and s['ref'] not in src: errs.append(f"research strategy {s['id']}: unknown reference {s['ref']}")
    ids = [x['id'] for x in R['backlog']]
    if len(ids) != len(set(ids)): errs.append('research: duplicate backlog ids')
    decided = {x['item'] for x in R['decisions']}
    for x in R['decisions']:
        if x['item'] not in ids: errs.append(f"research decision on unknown item {x['item']}")
    for x in R['backlog']:
        i = x['id']
        if not re.fullmatch(r'BL-\d{2}', i): errs.append(f'{i}: id must look like BL-01')
        if x['status'] not in RESEARCH_STATUS: errs.append(f'{i}: bad status')
        if x['type'] not in RESEARCH_TYPES: errs.append(f'{i}: bad type')
        if set(x['assess']) != set(crit) or any(v not in (0, 1, 2, 3) for v in x['assess'].values()): errs.append(f'{i}: assess every criterion 0 to 3')
        for s in x['strategy']:
            if s not in sids: errs.append(f'{i}: unknown strategy {s}')
        if re.fullmatch(r'OR-\d{2}', x['source']) and x['source'] not in orr: errs.append(f'{i}: unknown open register item {x["source"]}')
        if x['status'] == 'done' and not x.get('release'): errs.append(f'{i}: done items need a release')
        if x['status'] == 'out' and not x.get('reason'): errs.append(f'{i}: out of scope items need a reason')
        if chr(64) in x['story'] + x['title']: errs.append(f'{i}: no addresses in the backlog')
        if x['status'] in ('now', 'next', 'later') and 'assess' in x and set(x['assess']) == set(crit):
            _, band, _, _ = research_score(x, R)
            if band != x['status'] and i not in decided: errs.append(f'{i}: status {x["status"]} differs from its score band {band}; record why in the decisions log')
    if sum(1 for x in R['backlog'] if x['status'] == 'now') > R['wip_limit']: errs.append(f"research: more than {R['wip_limit']} items in Now")


def validate_involvement(d, errs):
    """Version 1.10: boards and networks, Get involved, badges, toolkit and easy read."""
    B, I = d.get('bodies'), d.get('involve')
    if B:
        ids = [x['id'] for x in B['items']]
        if len(ids) != len(set(ids)): errs.append('bodies: duplicate ids')
        for x in B['items']:
            if not re.fullmatch(r'(GB|NW)-[A-Z]+', x['id']): errs.append(f"bodies {x['id']}: id must be GB- (board) or NW- (network)")
            if not x['url'].startswith('https://'): errs.append(f"bodies {x['id']}: source must be https")
            for k in ('purpose', 'outcomes', 'dam', 'engage', 'tor'):
                if not x.get(k): errs.append(f"bodies {x['id']}: {k} missing")
            if chr(64) in ' '.join(str(v) for v in x.values()): errs.append(f"bodies {x['id']}: no email addresses")
        for s in B['flow']:
            if s['id'] not in ids + ['networks']: errs.append(f"bodies flow: unknown {s['id']}")
    if I:
        bids = {b['id'] for b in I['badges']}
        for r in I['routes']:
            if r['badge'] and r['badge'] not in bids: errs.append(f"involve {r['id']}: unknown badge {r['badge']}")
        for b in I['badges']:
            if not re.fullmatch(r'#[0-9a-f]{6}', b['colour']): errs.append(f"badge {b['id']}: colour must be #rrggbb")
            if b['claim'] not in ('self', 'request'): errs.append(f"badge {b['id']}: claim must be self or request")
        for tk in I['toolkit']:
            if chr(64) in tk['text']: errs.append(f"toolkit {tk['id']}: no email addresses")
            if '{site}' not in tk['text']: errs.append(f"toolkit {tk['id']}: must link to the portal")
    for k in (d.get('easy_read') or {}):
        if k not in PAGE_LEVEL: errs.append(f'easy read: unknown page {k}')


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
KNOWN_CHECKS = {f"C-{i:02d}" for i in range(1, 39)} | {f"B-{i:02d}" for i in range(1, 19)} | {'HL-01', 'HL-02', 'T-VAL'}
ICON_SET = json.loads((ROOT / 'site_src' / 'icons.json').read_text())['icons']

STAGE_ICONS = {
    'mandate': 'scroll-text', 'frame': 'book-marked', 'assign': 'user-check', 'operate': 'settings-2', 'assure': 'clipboard-check',
    'mobilise': 'flag', 'discover': 'search', 'designate': 'stamp', 'own': 'key-round', 'describe': 'pencil-line',
    'publish': 'share-2', 'report': 'send', 'maintain': 'calendar-clock', 'identify': 'crosshair', 'define': 'ruler',
    'baseline': 'chart-column', 'prioritise': 'list-ordered', 'improve': 'wrench', 'sustain': 'activity', 'review': 'calendar-check',
}
ROLE_ICONS = {'CDO': 'building-2', 'COO': 'clipboard-list', 'BRD': 'gavel', 'OWN': 'key-round', 'IAO': 'lock-keyhole',
              'STW': 'user-cog', 'CUS': 'server', 'CAT': 'database', 'DQL': 'chart-line', 'DPO': 'scale', 'USR': 'user-search', 'PUB': 'users',
              'SRO': 'flag', 'PDM': 'calendar-check', 'SVO': 'layers', 'ARC': 'network', 'MIG': 'arrow-right-left', 'CML': 'handshake', 'PMO': 'clipboard-check'}
CAP_ICONS = {'gov': 'shield-check', 'cat': 'library-big', 'dq': 'gauge'}
LEVELS = {'Foundation': 'award', 'Practitioner': 'graduation-cap', 'Advanced': 'milestone'}
PAGE_LEVEL = {**{k: 'Foundation' for k in ('index', 'dam', 'personas', 'learning', 'guide', 'inclusion', 'research', 'involve', 'test', 'contact', 'site-map', 'about', 'whats-new', 'accessibility')},
              **{k: 'Practitioner' for k in ('governance', 'cataloguing', 'quality', 'together', 'sectors', 'change', 'perspectives', 'community', 'library', 'knowledge', 'professions', 'data', 'bodies', 'status', 'notices')},
              **{k: 'Advanced' for k in ('capability-model', 'tooling', 'reuse', 'design')}}
LEVEL_TEXT = {'Foundation': 'For anyone: no data management background needed.', 'Practitioner': 'For people who do data governance, cataloguing or quality work.',
              'Advanced': 'For specialists: detailed models, standards and technical reuse.'}
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


def col_sizes(headers, rows):
    """Size each column from the length of its visible text: short columns shrink, long-text columns get room (version 1.8)."""
    out = []
    for j, h in enumerate(headers):
        vals = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', str(r[j]))).strip() for r in rows if j < len(r)]
        avg = (sum(len(v) for v in vals) / len(vals)) if vals else len(h)
        longest_word = max([len(w) for v in vals for w in v.split()] + [len(w) for w in h.split()] + [1])
        out.append('c-xs' if avg <= 12 and longest_word <= 14 else 'c-sm' if avg <= 32 else 'c-md' if avg <= 90 else 'c-lg')
    return out


def table(cap_id, caption, headers, rows, cls=None, row_attrs=None, tbody_id=None):
    sizes = col_sizes(headers, rows)
    th = ''.join(f'<th scope="col" class="{sizes[i]}{" raci" if (cls and h in cls) else ""}">{E(h)}</th>' for i, h in enumerate(headers))
    body = []
    for i, r in enumerate(rows):
        cells = []
        for j, c in enumerate(r):
            tag = 'th scope="row"' if j == 0 else 'td'
            klass = f' class="{sizes[j]}"' if j < len(sizes) else ''
            if cls and headers[j] in cls:
                klass = f' class="{sizes[j]} raci r-{E(c)}"' if c else f' class="{sizes[j]} raci"'
            cells.append(f'<{tag}{klass}>{c}</{tag.split()[0]}>')
        body.append(f'<tr{row_attrs[i] if row_attrs else ""}>' + ''.join(cells) + '</tr>')
    tb = f' id="{tbody_id}"' if tbody_id else ''
    return (f'<div class="table-wrap" role="region" aria-labelledby="{cap_id}" tabindex="0"><table>'
            f'<caption id="{cap_id}">{E(caption)}</caption><thead><tr>{th}</tr></thead><tbody{tb}>{"".join(body)}</tbody></table></div>')


def ul(items, raw=False, cls=''):
    c = f' class="{cls}"' if cls else ''
    return f'<ul{c}>' + ''.join(f'<li>{i if raw else E(i)}</li>' for i in items) + '</ul>'


def md_code(html):
    """Changelog text uses Markdown backticks for file names; show them as code, never as raw backticks (D-031)."""
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', html)


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
    ('capability-model', 'Capability model', 'radar'), ('perspectives', 'Perspectives', 'eye'), ('community', 'Working together', 'handshake'), ('professions', 'Professions and skills', 'briefcase'), ('tooling', 'Tools and interoperability', 'plug'), ('bodies', 'Boards and networks', 'building-2'),
    ('personas', 'Your role', 'users-round'), ('learning', 'Learning', 'graduation-cap'), ('library', 'Library', 'library'),
    ('knowledge', 'Knowledge', 'network'), ('inclusion', 'Inclusion', 'heart-handshake'), ('about', 'About', 'info'),
]
# Grouped menus keep the global bar to about ten top-level destinations (build standard: use hubs before adding more)
NAV_GROUPS = {'Playbooks': ['governance', 'cataloguing', 'quality', 'sectors', 'together', 'change'],
              'Frameworks': ['capability-model', 'perspectives', 'community', 'professions', 'tooling', 'bodies']}
# Section colour coding (version 1.8): every page carries a section, styled as an accent colour for orientation
SECTION = {'index': 'home', 'dam': 'policy', 'governance': 'gov', 'cataloguing': 'cat', 'quality': 'dq', 'sectors': 'sectors', 'together': 'together',
           'change': 'change', 'capability-model': 'model', 'perspectives': 'lens', 'community': 'community', 'professions': 'skills',
           'personas': 'roles', 'learning': 'learning', 'library': 'library', 'knowledge': 'knowledge', 'inclusion': 'inclusion',
           'data': 'data', 'test': 'test', 'guide': 'guide', 'site-map': 'guide', 'reuse': 'reuse', 'tooling': 'tooling', 'research': 'research', 'bodies': 'community', 'involve': 'research'}
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
    'data': 'Open data from the DAM capability playbooks: requirements, vocabulary, capability map, quality rules and more, with a DCAT catalogue for harvesting.',
    'perspectives': 'The DAM Policy through data, digital, cyber, technology, commercial and legacy lenses: questions, actions by capability, pitfalls and verified sources.',
    'community': 'How data, records, security, digital, technology, analysis, commercial and delivery professionals can work together on critical data assets.',
    'test': 'Help test the Data Asset Management (DAM) capability playbooks: short tasks for each role and a feedback form.',
    'design': 'Theory of change, research plan, service blueprint, requirements traceability, architecture and Service Standard self-assessment for the portal.',
    'notices': 'Disclaimers, transparency notices, credits and full citations for every source used by the DAM capability playbooks.',
    'accessibility': 'Accessibility statement for the DAM capability playbooks, following the GOV.UK model statement for public sector websites.',
    'tooling': 'How catalogue, data quality, lineage, master data and governance tools work together, the open standards that connect them, and RFI questions to avoid lock-in.',
    'guide': 'User guide for the DAM capability playbooks: getting around, what the colours and labels mean, guided tours, tutorials and keyboard shortcuts.',
    'site-map': 'Every page on the DAM capability playbooks portal, grouped the way the menus are, with the main sections of each page.',
    'reuse': 'Ways to use the DAM capability playbooks content: intranet links, embedding, open data, white-label copies, AI assistants and an MCP server.',
    'research': 'Have your say: take part in user research, suggest and vote for ideas, and see the roadmap, backlog and how priorities are decided, in the open.',
    'bodies': 'Boards, councils and networks for data asset management in government: purpose, aims, outcomes, terms of reference and how to take part.',
    'involve': 'Get involved: ways to take part, rules of engagement, a champions toolkit of emails and posts, and badges for your profile and signature.',
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
        self.search, self.build_id, self.reg = [], None, {}
        sp = ROOT / 'build' / 'status.json'
        self.status = json.loads(sp.read_text()) if sp.exists() else None
        ip = ROOT / 'build' / 'ideas.json'
        self.ideas = json.loads(ip.read_text(encoding='utf-8')) if ip.exists() else {'available': False, 'reason': 'not run', 'ideas': []}

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
        return ' '.join(f'<a class="pill {self.req[i]["cap"]}" href="dam.html#{i}" data-tip="{E(self.req[i]["text"])}">{E(i)}</a>' for i in ids)

    def stage_url(self, ref):
        c, st = self.stage[ref]
        return f'{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}'

    def stage_ref(self, ref):
        c, st = self.stage[ref]
        return f'<a class="pill {c["id"]}" href="{self.stage_url(ref)}" data-tip="{E(st["goal"])}">{E(c["short"])} {st["n"]}: {E(st["name"])}</a>'

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
        tag, easy = self.level_and_easy()
        return (f'<div class="hero {kind}">{tile(ic, "lg " + kind)}<div><p class="caption">{E(caption)}{tag}</p><h1>{E(title)}</h1>'
                f'<p class="lede">{lede}</p>{mt}</div></div>{b}{easy}')

    def add_search(self, title, kind, url, snippet=''):
        self.search.append({'t': title, 'k': kind, 'u': url, 's': snippet[:160]})

    # -- page shell ------------------------------------------------------------
    def page(self, key, title, body, drawer=None, desc='', crumbs=None, jsonld=None, extra_json=None):
        m = self.m
        self.reg[key] = (title, drawer or [])
        tours = [t for t in self.d.get('tours', []) if t['page'] == key]
        if tours:
            extra_json = dict(extra_json or {}, **{'tour-data': tours})
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
                sub = ''.join(f'<li><a href="{mk}.html" data-tip="{E(PAGE_DESC.get(mk, ""))}"{" aria-current=" + chr(34) + "page" + chr(34) if mk == key else ""}>{icon(mic)}<span>{E(ml)}</span></a></li>' for mk, ml, mic in members)
                nav += (f'<li class="group{" current" if cur else ""}"><button type="button" aria-expanded="false">{icon(NAV_GROUP_ICONS[grp])}<span>{E(grp)}</span>{icon("chevron-down")}</button>'
                        f'<ul aria-label="{E(grp)}">{sub}</ul></li>')
            else:
                nav += f'<li><a href="{k}.html" data-tip="{E(PAGE_DESC.get(k, m["subtitle"]))}"{" aria-current=" + chr(34) + "page" + chr(34) if k == key else ""}>{icon(ic)}<span>{E(lbl)}</span></a></li>'
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
<link rel="alternate" type="application/ld+json" href="data/catalogue.jsonld" title="Open data catalogue (DCAT, JSON-LD)">
<link rel="alternate" type="text/turtle" href="data/catalogue.ttl" title="Open data catalogue (DCAT, Turtle)">
<link rel="alternate" type="application/atom+xml" href="feed.xml" title="Releases (Atom feed)">
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
<body data-section="{E(SECTION.get(key, "other"))}">
<a class="skip" href="#main">Skip to main content</a>
<header class="mast">
<div class="mast-in"><a class="name" href="index.html"><img class="brand-mark" src="assets/favicon.svg" alt="" width="36" height="36"><span>{E(m["title"])}</span></a>
<div class="mast-tools">
<button type="button" data-open-search hidden aria-haspopup="dialog">{icon("search")}<span>Search</span> <kbd>Ctrl K</kbd></button>
<button type="button" id="display-toggle" aria-expanded="false" aria-controls="display-panel" hidden>{icon("a-large-small")}<span>Display options</span></button>
<a class="mast-link" href="research.html">{icon("megaphone")}<span>Have your say</span></a><a class="mast-link" href="guide.html">{icon("circle-help")}<span>Help</span></a><a class="mast-link" href="site-map.html">{icon("map")}<span>Site map</span></a></div></div>
{display}
</header>
<div class="banner"><strong class="tag">Prototype</strong>This is not an official GOV.UK service or published guidance. Where it repeats GDS guidance, the GOV.UK page is the authority. <a href="test.html">Help us test it</a> or <a href="contact.html">use the contact form</a> to tell us what you think.</div>
<nav class="gbar" id="gbar" aria-label="Portal sections"><ul class="top">{nav}<li class="more" hidden><button type="button" aria-expanded="false">{icon("chevron-down")}More sections</button><ul></ul></li></ul></nav>
<div class="wrap">
{drawer_html}
<main id="main" tabindex="-1">
{crumb_html}
<div class="toolbar">{toggle}<div class="page-actions">{self.page_actions(key, title, canonical)}</div></div>
{body}
{self.related_html(key)}
{self.edit_links(key, title)}
</main>
</div>
{self.footer(key, title)}
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
<script src="assets/journey-bar.js"></script>
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
        priv = (f' <a class="private" href="{E(self.ms_form_link(self.ms_where(key, title)))}" rel="noopener" data-ms-form>{icon("lock-keyhole")}Tell us privately, without GitHub</a>'
                if self.ms_form_url() else '')
        return (meta + f'<p class="useful"><a href="{gh}/issues/new?{E(fb)}">{icon("message-square-text")}Was this page useful? Tell us</a>{priv}</p>'
                f'<nav class="edit-links" aria-label="Help improve this page">'
                f'<a href="{gh}/issues/new?{E(q)}">{icon("message-square-text")}Report a problem with this page</a>'
                f'<a href="{gh}/edit/main/content/playbooks.yaml">{icon("pencil-line")}Suggest a change</a>'
                f'<a href="{gh}/commits/main/content/playbooks.yaml">{icon("clock")}See the change history</a>'
                f'<a href="{gh}/discussions">{icon("users")}Ask the community</a></nav>')

    def page_actions(self, key, title, url):
        enc = urllib.parse.quote
        tour = ''.join(f'<button type="button" class="tour-btn" data-tour="{t["id"]}" hidden>{icon("play")}Take the tour</button>' for t in self.d.get('tours', []) if t['page'] == key)
        mail = f'mailto:?subject={enc(title + " - " + self.m["short_title"])}&amp;body={enc("I thought this might be useful: " + url)}'
        teams = f'https://teams.microsoft.com/share?href={enc(url, safe="")}&amp;msgText={enc(title)}'
        share = (f'<details class="share"><summary>{icon("share-2")}Share this page</summary><ul>'
                 f'<li><button type="button" data-copy-link hidden>{icon("link")}Copy link</button></li>'
                 f'<li><button type="button" data-native-share hidden>{icon("send")}Share using your device</button></li>'
                 f'<li><a href="{mail}">{icon("message-square-text")}Email a link</a></li>'
                 f'<li><a href="{teams}">{icon("users")}Share in Microsoft Teams</a></li>'
                 f'<li class="share-status" aria-live="polite"></li></ul></details>')
        return tour + share

    def related_html(self, key):
        """Signposts to the sister portals (version 1.8.1). Shown only where they help, named with each portal's status and owner model, never merged into this portal's own journeys."""
        R = self.d.get('related') or {}
        items = (R.get('placements') or {}).get(key) or []
        if not items:
            return ''
        P = {p['id']: p for p in R['portals']}
        lis = ''
        for it in items:
            p = P[it['portal']]
            url = p['url'] + it['path']
            lis += (f'<li><a href="{E(url)}" rel="noopener">{E(it["title"])}</a> <span class="rel-portal" data-tip="{E(p["nature"] + " " + p["licence"] + ".")}">'
                    f'in {E(p["name"])} <span class="rel-status">{E(p["status"])}</span></span><br><span class="hint">{E(it["why"])}</span></li>')
        return (f'<aside class="related" id="related-{key}" aria-labelledby="rel-h-{key}"><h2 id="rel-h-{key}">{icon("signpost")} Related elsewhere</h2>'
                f'<p class="hint">{E(R["intro"])}</p><ul>{lis}</ul>'
                f'<p class="compass-link">{icon("compass")}Not sure which portal you need, or in what order? <a href="compass/">Take a bearing with the estate compass</a>.</p></aside>')

    def write_xref(self):
        """Cross-reference manifest (version 1.8.1): this portal's shared keys and where each lives, for sister portals and tools to link to. Ids only, no copied text."""
        d, base = self.d, self.m['site_url']
        man = {'portal': self.m['title'], 'id': 'dam', 'version': self.m['version'], 'as_of': self.m['as_of'], 'url': base,
               'status': 'Prototype guidance for implementing the DAM Policy; central ownership', 'licence': self.d['meta'].get('licence_content', 'Open Government Licence v3.0'),
               'keys': {
                   'dama_areas': [{'id': a['id'], 'name': a['name'], 'url': f'{base}capability-model.html#{a["id"].lower()}'} for a in d.get('dama', {}).get('areas', [])],
                   'requirements': [{'id': r['id'], 'strength': r['strength'], 'url': f'{base}dam.html#{r["id"]}'} for r in d['requirements']],
                   'capabilities': [{'id': c['id'], 'name': c['name'], 'dmbok': c['dmbok'], 'url': f'{base}capability-model.html#{c["id"]}'} for c in d.get('capmap', [])],
                   'practices': [{'id': x['id'], 'title': x['title'], 'url': f'{base}change.html#{x["id"]}'} for x in d.get('change', {}).get('items', [])],
                   'sectors': [{'id': x['id'], 'title': x['title'], 'url': f'{base}sectors.html#{x["id"]}'} for x in d.get('supplements', [])],
                   'roles': [{'code': r['code'], 'name': r['name'], 'url': f'{base}together.html#role-{r["code"]}'} for r in d['roles']],
                   'tool_categories': [{'id': c['id'], 'name': c['name'], 'url': f'{base}tooling.html#{c["id"]}'} for c in d.get('tooling', {}).get('categories', [])]},
               'related': [{k: p[k] for k in ('id', 'name', 'url', 'status', 'licence')} for p in (d.get('related') or {}).get('portals', [])]}
        (self.out / 'data' / 'xref.json').write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding='utf-8')

    def ms_form_url(self):
        return (self.d.get('ms_form') or {}).get('url') or ''

    def refs_by_group(self, refs):
        """Version 1.11.0: supplements list their obligations grouped by kind (legislation, standards, health and care and so on),
        not as one undifferentiated list of policy references."""
        groups = {}
        for r in refs:
            groups.setdefault(self.rb[r]['group'], []).append(r)
        return '<dl class="ref-groups">' + ''.join(f'<dt>{E(g)}</dt>' + ''.join(f'<dd>{self.rb_link(r)}</dd>' for r in rs) for g, rs in groups.items()) + '</dl>'

    def dictionary_rows(self):
        """Version 1.11.0: the dictionary shows type, format, cardinality, controlled values and an example for each property."""
        cat = self.caps['cat']
        det = {x['prop']: x for x in cat['metadata_detail']}
        vl = {v['id']: v for v in cat['value_lists']}
        rows = []
        for x in cat['metadata']:
            t = det[x['prop']]
            typ = E(t['type']) + (f' <a href="#vl-{t["values"]}">({E(vl[t["values"]]["name"].lower())} list)</a>' if t.get('values') else '')
            rows.append([f'<code id="dict-{x["prop"]}">{E(x["prop"])}</code>', E(x['mem']), E(x['obligation']), typ, E(t['format']), E(t['card']), f'<code>{E(t["example"])}</code>', E(x['rule'])])
        return rows

    def value_lists_html(self):
        out = ''
        for v in self.caps['cat']['value_lists']:
            vals = (ul([f"<code>{E(x)}</code>" for x in v["values"]], raw=True) if v['values'] else '')
            link = f' <a href="{E(v["url"])}">{E(v["name"])} source</a>' if v.get('url') else ''
            used = ', '.join(f'<a href="#dict-{x["prop"]}"><code>{E(x["prop"])}</code></a>' for x in self.caps['cat']['metadata_detail'] if x.get('values') == v['id'])
            out += f'<section id="vl-{v["id"]}"><h4>{E(v["name"])}{prov(v["prov"])}</h4><p>{E(v["note"])}{link}</p>{vals}<p class="hint">Used by {used}.</p></section>'
        return f'<h3 id="value-lists">{icon("list-checks")} Controlled value lists</h3>{out}'

    def template_privacy(self):
        """Version 1.11.0: the old line said never to record named individuals or personal email addresses, which read as
        banning names from a team's own working copies. The rule is about publishing, not recording."""
        return (f'<div class="notice-box" id="template-privacy">{icon("lock-keyhole")}<p><strong>Names and email addresses.</strong> Your own working copies can name the '
                'people who hold each role and give their work email addresses, handled under your organisation\'s data protection rules. Do not publish them: '
                'anything you put on GitHub or anywhere public should name roles only.</p></div>')

    def template_modes_note(self):
        return ('<p class="hint">Each template says whether it is for business as usual, change programmes or both. Artefacts that only change programmes need, '
                'such as project governance and design authority inputs, are on the <a href="change.html">Change</a> page.</p>')

    def template_html(self, t):
        mode = f'<span class="pill mode-{t["mode"].lower()}">{E(TEMPLATE_MODES[t["mode"]])}</span>'
        note = f'<p>{E(t["note"])}</p>' if t.get('note') else ''
        if t.get('sheets'):
            body = ''.join(f'<details><summary>{E(sh["name"])} tab ({len(sh["fields"])} fields)'
                           + (f' <span class="hint">same fields as {E(sh["from"])}</span>' if sh.get('from') else '') + f'</summary>{ul(sh["fields"], cls="fields")}</details>'
                           for sh in t['sheets'])
            dl = (f'<a href="data/templates/{t["id"]}.ods">{icon("download")}Download the workbook (OpenDocument spreadsheet, {len(t["sheets"])} tabs)</a> · '
                  + ' · '.join(f'<a href="data/templates/{t["id"]}-{slug(sh["name"])}.csv">{E(sh["name"])} (CSV)</a>' for sh in t['sheets']))
        else:
            body = ul(t['fields'], cls='fields')
            dl = f'<a href="data/templates/{t["id"]}.csv">{icon("download")}Download this template (CSV)</a>'
        return (f'<section class="template" id="{t["id"]}"><h3>{icon("file-text")} {E(t["name"])} <small>({E(t["id"])})</small></h3><p>{mode}</p>{note}{body}'
                f'<p>{dl} · <a href="data/templates.csv">All templates (CSV)</a></p></section>')

    def ms_form_link(self, where='', topic=''):
        """The private form, opened with the page or task filled in (version 1.10.2). Microsoft Forms reads
        r<question id>=<answer>; a choice answer must be a JSON string matching the choice exactly."""
        url = self.ms_form_url()
        if not url:
            return ''
        p = (self.d.get('ms_form') or {}).get('prefill') or {}
        q = []
        if topic and p.get('topic'):
            if topic not in (p.get('topics') or {}):
                raise ContentError(f'ms_form.prefill: unknown topic {topic}')
            q.append((p['topic'], json.dumps(p['topics'][topic], ensure_ascii=False)))
        if where and p.get('where'):
            q.append((p['where'], where))
        return url + ''.join(f'&{k}={urllib.parse.quote(v, safe="")}' for k, v in q)

    def ms_where(self, key, title):
        """What the form's 'which page' question is filled in with: the page title and its file, so a response can be traced to a page."""
        return f'{title} ({"index" if key == "index" else key}.html)'

    def ms_form_block(self, key='', title='', topic=''):
        """The private feedback route. Shown only when a form address is set, so an empty setting never leaves a dead link."""
        f, url = self.d.get('ms_form') or {}, self.ms_form_url()
        if not url:
            return ''
        link = self.ms_form_link(self.ms_where(key, title) if key else '', topic)
        priv = ''.join(f'<li>{E(x)}</li>' for x in f.get('privacy', []))
        return (f'<div class="notice-box ms-form" id="private-feedback">{icon("lock-keyhole")}<div><h2 class="fs-h">Prefer not to use GitHub?</h2>'
                f'<p>{E(f["note"])}</p><p><a class="btn secondary" href="{E(link)}" rel="noopener" data-ms-form>{icon("message-square-text")}{E(f["title"])}</a></p>'
                + (f'<details><summary>How we use your answers and any contact details</summary><ul>{priv}</ul></details>' if priv else '')
                + f'<p class="hint">Apart from your own contact details, if you choose to give them, do not include names, personal data or anything above OFFICIAL.</p></div></div>')

    def ms_privacy_html(self):
        """The private feedback form's privacy wording on About > Privacy, which the form itself links to (version 1.10.2)."""
        f = self.d.get('ms_form') or {}
        if not self.ms_form_url() or not f.get('privacy'):
            return ''
        return (f'<h3 id="privacy-feedback-form">{icon("lock-keyhole")} The private feedback form</h3>'
                f'<p>The <a href="{E(self.ms_form_link())}" rel="noopener" data-ms-form>private feedback form</a> is a Microsoft form. It opens with the page or task you came from filled in.</p>'
                f'<ul>{"".join(f"<li>{E(x)}</li>" for x in f["privacy"])}</ul>')

    def footer(self, key='', title=''):
        m = self.m
        return f'''<footer class="site" id="colophon">
<div class="cols">
<div><h2>{icon("info")} About this portal</h2>
<p>{E(m["status"])}</p>
<p>Written with help from an AI assistant (Claude). Every fact is labelled with where it came from, and a person reviews each release before it is published.</p>
<ul class="foot-links"><li><a href="accessibility.html">Accessibility statement</a></li><li><a href="notices.html">Disclaimers, credits and citations</a></li><li><a href="design.html">Service design</a></li><li><a href="status.html">Status and health</a></li><li><a href="whats-new.html">What's new</a></li><li><a href="about.html#provenance">How sources are labelled</a></li><li><a href="about.html#privacy">Privacy</a></li><li><a href="about.html#limitations">Known limitations</a></li><li><a href="data.html">Open data</a></li><li><a href="research.html">Have your say: research, roadmap and ideas</a></li><li><a href="involve.html">Get involved, champions and badges</a></li><li><a href="test.html">Help us test</a></li><li><a href="guide.html">User guide and tours</a></li><li><a href="site-map.html">Site map</a></li><li><a href="reuse.html">Use and reuse this content</a></li><li><a href="compass/">Estate compass: find your way across four portals</a></li></ul></div>
<div><h2>{icon("message-square-text")} Contact</h2>
<p><a href="contact.html">Use the contact form</a> to ask a question, report a problem or suggest an improvement.</p>{f'<p>Or <a href="{E(self.ms_form_link(self.ms_where(key, title) if key else ""))}" rel="noopener" data-ms-form>give feedback privately about this page</a> (Microsoft Forms, no sign-in or GitHub account needed).</p>' if self.ms_form_url() else ''}
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
        for f in sorted((ROOT / 'site_src').glob('*')) + sorted((ROOT / 'compass').glob('*')) + [Path(__file__), ROOT / 'tools' / 'compass.py']:
            h.update(f.read_bytes())
        self.build_id = f'{m["id"]}-{m["version"]}-{h.hexdigest()[:8].upper()}'
        self.codes = (f'<figure>{barcode_svg(self.build_id, "Barcode of build identifier " + self.build_id)}<figcaption>{E(self.build_id)}</figcaption></figure>'
                      f'<figure>{qr_svg(m["site_url"], "QR code linking to " + m["site_url"])}<figcaption>Portal address</figcaption></figure>')
        self.collect_search()
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / 'assets').mkdir(parents=True)
        (self.out / 'data').mkdir()
        for f in ('style.css', 'app.js', 'journey-bar.js', 'favicon.svg'):
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
                 'professions': self.p_professions, 'change': self.p_change, 'perspectives': self.p_lenses, 'community': self.p_community, 'about': self.p_about, 'contact': self.p_contact, 'status': self.p_status,
                 'whats-new': self.p_whats_new, 'design': self.p_design, 'notices': self.p_notices, 'data': self.p_data, 'test': self.p_test,
                 'accessibility': self.p_accessibility, 'guide': self.p_guide, 'reuse': self.p_reuse, 'tooling': self.p_tooling, 'research': self.p_research, 'bodies': self.p_bodies, 'involve': self.p_involve, '404': self.p_404}
        for k, fn in pages.items():
            self._key = k
            (self.out / f'{k}.html').write_text(fn(), encoding='utf-8')
        self._key = 'site-map'
        # The estate compass: a neutral page across the three portals, built from compass/ (version 1.8.2)
        sys.path.insert(0, str(ROOT / 'tools'))
        import compass as _compass
        try:
            self.compass_id = _compass.build(self.out, self.d, ICON_SET, barcode_svg, qr_svg)
        except ValueError as e:
            raise ContentError(str(e))
        # The site map is built last, from the registry every other page has filled
        (self.out / 'site-map.html').write_text(self.p_sitemap(), encoding='utf-8')
        self.write_llms()
        self.embed_ids = self.write_embeds()
        self.write_badges()
        self.write_feed()
        mods = {mm['id']: self.mod_units(mm['id']) for mm in d['modules']}
        (self.out / 'assets' / 'search-index.js').write_text(
            'window.DCP_INDEX=' + json_safe(self.search) + ';\nwindow.DCP_MODULES=' + json_safe(mods) + ';\n', encoding='utf-8')
        self.write_xref()
        self.exports()
        # D-030: the Open data page lists files that exist, so it is built again once every data file is written
        self._key = 'data'
        (self.out / 'data.html').write_text(self.p_data(), encoding='utf-8')
        (self.out / '.nojekyll').write_text('')
        self.write_offline()
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
        for x in self.d.get('lenses', {}).get('items', []):
            self.add_search(f'{x["name"]} perspective', 'Perspective', f'perspectives.html#{x["id"]}', x['means'])
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
        body = f'''<div class="hero home">{tile("library-big", "lg")}<div><p class="caption">Data asset management (DAM) policy{self.level_and_easy()[0]}</p><h1>{E(m["title"])}</h1>
<p class="lede">Practical guidance for people who govern, catalogue and manage the quality of critical data assets in UK government departments and arm's length bodies.</p></div></div>
<div class="in-brief" role="note" aria-label="In brief"><h2 class="ib-h">{icon("list-checks")} In brief</h2>
<ul><li>The DAM Policy asks every department and arm's length body to identify, describe, own and manage the quality of its critical data assets.</li>
<li>Three capabilities make that possible: data governance, data cataloguing and data quality. This portal puts them side by side.</li>
<li>It is more detailed than GOV.UK guidance and written for specialists. GOV.UK remains the authority on what the policy requires.</li></ul></div>{self.level_and_easy()[1]}
<h2 id="role">{icon("users-round")} Start from your role</h2>
<ul class="persona-grid">{personas}</ul>
<section class="ask js-only" aria-labelledby="ask"><h2 id="ask">{icon("circle-help")} Ask a question</h2>
<form class="ask-form" data-ask><label for="ask-q">Ask in your own words, for example "who signs off a data quality action plan?"</label>
<div class="ask-row"><input id="ask-q" name="q" type="search" autocomplete="off"><button type="submit" class="btn">{icon("search")}Ask</button></div></form>
<div id="ask-out" aria-live="polite"></div><p class="hint">Answers are the pages of this portal that best match your question, found in your browser. Nothing is sent anywhere. Read the page, and GOV.UK, before relying on it.</p></section>
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
            {'id': 'ask', 'label': 'Ask a question', 'icon': 'circle-help', 'new': True},
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
        tmpl = ''.join(self.template_html(t) for t in c.get('templates', []))
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
                            + f'<p><a href="knowledge.html#dict">{icon("database")}See the data dictionary</a> for each property\'s data type, format, how many values it takes, its controlled value list and an example. '
                              f'For the entities and relationships inside a data asset, use the <a href="#T-CAT-4">entity and relationship list</a>.</p>'
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
            ('method', 'Step by step', f'<h2 id="stages">{icon("route")} {E(c["method_name"])}{prov(c["method_prov"])}</h2><p>{E(c["method_intro"])}</p>{self.sector_callout(cid)}{self.step_by_step(c)}{extra_method}'),
            ('roles', 'Roles', f'<h2 id="role-list">{icon("users")} Roles</h2><ul class="icon-list">{roles}</ul><h2 id="raci">{icon("list-checks")} Who does what</h2>{self.raci_table(c, "t-raci-" + cid)}'),
            ('templates', 'Templates', f'<h2 id="template-list">{icon("file-text")} Templates</h2><p>Blank structures to copy into your own tools.</p>{self.template_privacy()}{self.template_modes_note()}{tmpl}'),
            ('escalation', 'Measures', f'<h2 id="measures">{icon("chart-column")} Measures</h2>{table("t-meas-" + cid, "Measures for " + c["name"].lower(), ["Measure", "Target"], meas_rows)}'
             + (f'<div class="warning" role="note">{icon("triangle-alert")}<span>Finding F-01: Table 4 of the GOV.UK issues framework gives 96.75% as the High band start for a 97.5% target, but its own rule gives 96.25%. These playbooks follow the rule. <a href="about.html#F-01">Read the finding</a>.</span></div>' if cid == 'dq' else '')
             + (f'<h2 id="ladder">{icon("triangle-alert")} Escalation</h2><p>{E(c["escalation_note"])}</p>{table("t-esc-" + cid, "Escalation for " + c["name"].lower(), ["Level", "Who", "Trigger", "Timescale"], esc_rows)}' if esc_rows
                else f'<h2 id="ladder">{icon("triangle-alert")} Escalation</h2><p>Cataloguing issues go up the <a href="governance.html#ladder">governance escalation ladder</a>.</p>')),
            ('sector-supplements', 'Sectors', self.cap_sectors(cid)),
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
                                                              {'id': 'sector-list', 'label': 'Sector supplements', 'icon': 'layers', 'count': len(self.cap_sups(cid)), 'new': True},
                                                              {'id': 'source-list', 'label': 'Sources', 'icon': 'library', 'count': len(srcs)}]},
        ]
        return self.page(p, c['name'], body, drawer, crumbs=[c['name']], desc=c['purpose'],
                         jsonld={'@type': ['WebPage', 'HowTo'], 'name': c['name'], 'step': [{'@type': 'HowToStep', 'position': st['n'], 'name': st['name'], 'text': st['goal']} for st in c['stages']]})

    def rb_link(self, rid):
        x = self.rb[rid]
        return f'<a href="{E(x["url"])}" data-tip="{E(x["publisher"] + ": " + x["why"])}">{E(x["title"])}</a>{prov(x["prov"], self.m["verified_on"])}'

    def rulebook_html(self, items, filt_id):
        groups = []
        for g in dict.fromkeys(x['group'] for x in items):
            rows = ''.join(f'<li id="{x["id"]}" data-item data-cap="{" ".join(x["caps"])}" data-group="{slug(x["group"])}">{self.rb_link(x["id"])}'
                           f'<span class="hint">{E(x["publisher"])}{" · updated " + E(x["updated"]) if x.get("updated") else ""}</span>{E(x["why"])}</li>' for x in items if x['group'] == g)
            groups.append(f'<h3>{E(g)}</h3><ul class="rulebook">{rows}</ul>')
        return f'<div id="{filt_id}">{"".join(groups)}</div>'

    # Sector signposting (version 1.5, ADR 0004): one home for sector content (the Sectors page), signposted where it is used
    def cap_sups(self, cid):
        dd = {x['id']: x for x in self.d['domain_depth']}
        return [x for x in self.d['supplements'] if cid in dd[x['dd']]['caps']]

    def sup_adds(self, x, cid):
        return {'gov': f'{len(x["gov"])} governance points and {len(x["risks"])} risks',
                'cat': f'{len(x["cat"])} extra catalogue fields' + (f' and {len(x.get("identifiers", []))} identifiers' if x.get('identifiers') else ''),
                'dq': f'{len(x["rules"])} quality rules you can run'}[cid]

    def sector_callout(self, cid):
        sups = self.cap_sups(cid)
        chips = ' '.join(f'<a class="pill" href="sectors.html#{x["id"]}">{icon(x["icon"])}{E(x["title"])}</a>' for x in sups)
        return (f'<aside class="sector-callout" aria-label="Sector supplements">{icon("layers")}<div><p><strong>Working with sector-specific data?</strong> '
                f'{len(sups)} sector supplements add to this method. <a href="sectors.html#which">Find which apply to your asset</a> or <a href="#sector-list">see what each adds</a>.</p><p class="chips">{chips}</p></div></aside>')

    def cap_sectors(self, cid):
        rows = [[f'<a href="sectors.html#{x["id"]}">{icon(x["icon"])} {E(x["title"])}</a>', E(x['summary']), E(self.sup_adds(x, cid))] for x in self.cap_sups(cid)]
        return (f'<h2 id="sector-list">{icon("layers")} Sector supplements for {E(self.caps[cid]["name"].lower())}</h2>'
                f'<p>The method on this page works for any critical data asset. Some kinds of data need more: extra rules, fields or safeguards. Those live in one place, the <a href="sectors.html">Sectors</a> section, and are listed here with what each adds to {E(self.caps[cid]["name"].lower())}.</p>'
                f'<p><a class="btn-link" href="sectors.html#which">{icon("compass")}Find which supplements apply to your asset</a></p>'
                + table(f't-sups-{cid}', f'Sector supplements that add to {self.caps[cid]["name"].lower()}', ['Supplement', 'What it covers', f'What it adds to {self.caps[cid]["short"].lower()}'], rows))

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
                                ('No GitHub account? Use the private feedback form further down this page.' if self.ms_form_url() else 'If you cannot use this form, ask a colleague to send it for you.')])
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
{self.ms_form_block('contact', 'Contact form')}
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
        tlist = [(c, t) for c in d['capabilities'] for t in c.get('templates', [])]
        tm = [[f'<a href="{CAP_PAGE[c["id"]]}.html#{t["id"]}">{E(t["name"])}</a>', f'<span class="pill {c["id"]}">{E(c["short"])}</span>', E(TEMPLATE_MODES[t['mode']]), str(len(t['fields'])),
               (f'<a href="data/templates/{t["id"]}.ods">ODS</a>' if t.get('sheets') else f'<a href="data/templates/{t["id"]}.csv">CSV</a>')] for c, t in tlist]
        tm_attrs = [f' data-item data-mode="{"bau change" if t["mode"] == "Both" else t["mode"].lower()}" data-cap="{c["id"]}"' for c, t in tlist]
        tfilt = ('<div class="filters" data-filter="tmpl-table" role="group" aria-label="Filter templates"><div><label for="t-mode">Used in</label><select id="t-mode" name="mode">'
                 '<option value="">All</option><option value="bau">Business as usual</option><option value="change">Change programmes</option></select></div>'
                 '<p class="count-out" aria-live="polite"></p></div>')
        dl = [('data/playbooks.json', 'Full content (JSON)'), ('data/requirements.csv', 'Requirements (CSV)'), ('data/templates.csv', 'Templates (CSV)'),
              ('data/glossary.csv', 'Glossary (CSV)'), ('data/vocabulary.ttl', 'Vocabulary (SKOS, Turtle)'), ('data/vocabulary.jsonld', 'Vocabulary (SKOS, JSON-LD)'),
              ('data/catalogue.jsonld', 'Catalogue of sources (DCAT, JSON-LD)'), ('data/metadata-dictionary.csv', 'Metadata data dictionary (CSV)')]
        body = self.hero('library', 'Library', 'Library', 'All playbook material for the three capabilities: published GOV.UK guidance, standards, tools, and practitioner material not yet published. Published items link to their authoritative source.',
                         brief=['Filter by capability, type or status.', 'Templates are blank structures to copy into your own tools, one at a time or all together.', 'Everything on this portal is also available as open data.'])
        body += f'''<h2 id="library">{icon("library")} All material</h2>{filt}{tbl}
<h2 id="templates">{icon("file-text")} Templates</h2>{self.template_privacy()}{self.template_modes_note()}{tfilt}{table("t-tmpl", "Templates in the three playbooks", ["Template", "Capability", "Used in", "Fields", "Download"], tm, row_attrs=tm_attrs, tbody_id="tmpl-table")}
<h2 id="sectors">{icon("layers")} Sector supplements</h2>
<p>Extra governance, catalogue fields and quality rules for {len(d["supplements"])} kinds of data are in the <a href="sectors.html">Sectors</a> section, and signposted from each capability playbook.</p>
<h2 id="data">{icon("download")} Open data</h2><p>Everything on this portal is also published as open data, described in a catalogue other portals can harvest. See <a href="data.html">Open data</a> for every dataset, its formats and licence.</p>'''
        drawer = [{'label': 'Library', 'icon': 'library', 'items': [
            {'id': 'library', 'label': 'All material', 'icon': 'library', 'count': len(d['library'])},
            {'id': 'templates', 'label': 'Templates', 'icon': 'file-text', 'count': len(tm)},
            {'id': 'sectors', 'label': 'Sector supplements', 'icon': 'layers', 'count': len(d['supplements'])},
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
        mrows = self.dictionary_rows()
        tabs = [
            ('glossary', 'Glossary', f'<h2 id="gl">{icon("book-open")} Glossary and thesaurus</h2><p>Every term, with other names it goes by (the thesaurus) and its broader term (the taxonomy).</p>{filt}{gl}'),
            ('taxonomy', 'Taxonomy', f'<h2 id="tax">{icon("network")} Taxonomy</h2><p>Terms arranged from broader to narrower meaning.</p><div class="tree">{tree(None)}</div>'),
            ('graph-tab', 'Knowledge graph', f'<h2 id="kg">{icon("network")} Knowledge graph</h2><p>Capabilities, their steps, the requirements they meet and the sources behind them. Select a shape to see what it connects to. The same information is in the tables on the policy and capability pages.</p>'
             f'<p class="legend"><span class="lg-cap">Capability (large circle)</span><span class="lg-stage">Step (square)</span><span class="lg-req">Requirement (diamond)</span><span class="lg-src">Source (small circle)</span></p>'
             f'<div class="graph-wrap" id="graph">{svg}</div><p><button type="button" class="btn secondary" id="graph-clear">{icon("x")}Clear selection</button></p><div id="graph-detail" aria-live="polite">Select a shape to see what it connects to.</div>'),
            ('dictionary', 'Data dictionary', f'<h2 id="dict">{icon("database")} Data dictionary</h2><p>The fields of a critical data asset catalogue record: what each holds, in what format, how many values a record can have, and an example.</p>'
             f'<p class="hint">Type follows the range of the DCAT or Dublin Core term{prov("K")}. "How many" is proposed by this portal; the MEM and the GOV.UK guidance do not set it{prov("O")}. Examples are illustrative and synthetic.</p>'
             f'{table("t-dict", "Catalogue record fields", ["Property", "MEM slot", "Obligation", "Type", "Format", "How many", "Example", "Rule"], mrows)}'
             f'<div class="notice-box" id="dict-standards">{icon("signpost")}<p><strong>Catalogue standard and sector standards work together.</strong> The {self.src_link("SRC-MEM")} describes the asset in a catalogue, '
             f'using DCAT as {self.rb_link("RB-DCATGOV")} recommends. Sector standards, such as {self.rb_link("RB-FHIRUK")} and {self.rb_link("RB-SNOMED")} for health, describe the data inside it: record them in <code>conformsTo</code>. '
             f'A UK application profile of DCAT that evolves the MEM has been proposed but not endorsed; it is <a href="cataloguing.html#related-cataloguing">signposted on the Cataloguing page</a>, and the MEM remains the endorsed model. Sector-specific fields are in the <a href="sectors.html">sector supplements</a>.</p></div>'
             f'{self.value_lists_html()}'
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
        lim = [o for o in d['open_register'] if o.get('reader')]
        orr = ''.join(f'<tr id="{o["id"]}"><th scope="row">{E(o["id"])}</th><td><strong>{E(o["reader"])}.</strong> {E(o["item"])}</td></tr>' for o in sorted(lim, key=lambda o: o['id']))
        provs = ''.join(f'<li>{prov(k)} {E(v)}</li>' for k, v in PROV_TEXT.items())
        body = self.hero('info', 'About', 'About this portal', E(m['subtitle']) + '.',
                         brief=['A prototype that brings together the playbooks for the three capabilities behind the DAM Policy.',
                                'Every fact is labelled with where it came from.', 'What it cannot yet do is listed openly under known limitations.'])
        body += f'''<h2 id="intent">{icon("target")} Purpose</h2><p>{E(m["intent"])}</p>
<h2 id="provenance">{icon("tag")} How sources are labelled</h2><ul>{provs}</ul>
<p>Requirement strength follows the wording of the source. Step sequences are labelled as synthesis or practitioner material; they are not GOV.UK requirements.</p>
<h2 id="findings">{icon("search")} Verification findings</h2>
{"".join(f'<section class="finding" id="{x["id"]}"><h3>{E(x["id"])}: {E(x["title"])}</h3><p>{E(x["detail"])}</p><p><strong>Action:</strong> {E(x["action"])} <span class="hint">Verified {E(x["verified"])} against {self.finding_src(x)}</span></p></section>' for x in d["findings"])}
<h2 id="explain">{icon("lightbulb")} How the portal decides things</h2>
<ul><li><strong>Search order.</strong> Exact title matches first, then titles that start with your words, then titles containing all your words, then other matches, each in page order.</li>
<li><strong>Progress.</strong> A step is done when you mark it. A module is done when all its activities are marked. A route counts both.</li>
<li><strong>Status page.</strong> A weekly automated run checks sources, the review date and page weight. It never changes content; it opens an issue for a person to act on.</li></ul>
<h2 id="limitations">{icon("clipboard-list")} Known limitations</h2>
<p>What this prototype cannot yet do or promise. Bear these in mind while you test it, and tell us through the <a href="test.html">testing page</a> or the <a href="contact.html">contact form</a> if you can help close one.</p>
<div class="table-wrap" role="region" aria-labelledby="t-open" tabindex="0"><table><caption id="t-open">Known limitations of this prototype</caption><thead><tr><th scope="col">ID</th><th scope="col">Limitation</th></tr></thead><tbody>{orr}</tbody></table></div>
<h2 id="accessibility">{icon("accessibility")} Accessibility statement</h2>
<p>This portal aims to meet WCAG 2.2 at level AA. Each release is checked automatically with axe-core in a real browser, for keyboard use, for sideways scrolling from 320 to 1920 pixels wide, and in light and dark modes. You can change text size, line spacing and colours in Display options.</p>
<p>Known limitations: it has not been tested in person with disabled users or with assistive technology users (OR-09). The knowledge graph is a visual aid; the same relationships are in tables on the policy and capability pages. Progress tracking needs scripts; every page can be read without them.</p>
<p>If you find a problem, use the <a href="contact.html">contact form</a>. If you cannot use it, ask a colleague to send it for you. If you are not happy with the response, contact the Equality Advisory and Support Service (EASS).</p>
<h2 id="privacy">{icon("lock-keyhole")} Privacy</h2><p>The portal sets no cookies and loads nothing from other sites. Your display choices and progress are kept only in your own browser and can be cleared from the home page. The contact form opens GitHub, where messages are public. Ideas and votes are GitHub Discussions, which are public too. If you sign up for user research, a separate private form collects your contact details; <a href="research.html#privacy">see how we look after them</a>.</p>{self.ms_privacy_html()}
<h2 id="build">{icon("badge-check")} Build and checks</h2><p>Build {E(self.build_id)}. Generated from one content file. Each release runs structural, link, provenance, email, language, accessibility and layout checks. Each check is shown to fail on a deliberate break before it is trusted. Defects and the checks that now prevent each one are recorded in the repository, with the build report and the full register of open items: <a href="https://github.com/{E(m["repo"])}/tree/main/docs">repository documents</a>.</p>'''
        drawer = [{'label': 'About', 'icon': 'info', 'items': [
            {'id': 'intent', 'label': 'Purpose', 'icon': 'target'},
            {'id': 'provenance', 'label': 'Source labels', 'icon': 'tag', 'count': 5},
            {'id': 'findings', 'label': 'Verification findings', 'icon': 'search', 'count': len(d['findings']), 'new': True},
            {'id': 'explain', 'label': 'How the portal decides', 'icon': 'lightbulb', 'count': 3},
            {'id': 'limitations', 'label': 'Known limitations', 'icon': 'clipboard-list', 'count': len(lim)},
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
<div class="mod-head">{tile(x["icon"], "lg")}<div><p class="caption">{E(x["id"])} · <strong class="moscow m-{slug(t["moscow"])}">{E(t["moscow"])} have</strong></p><h3 id="h-{x["id"]}">{E(x["title"])}</h3>{caps}</div></div>
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
<h4>{icon("scale")} Legislation, standards and frameworks that apply</h4>{self.refs_by_group(x["refs"])}</section>'''
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
        return f'<a class="pill" href="capability-model.html#{cid}" data-tip="{E(c["note"])}">{E(cid)} {E(c["name"])}</a>'

    def role_pills(self, codes):
        return ' '.join(f'<a class="pill" href="together.html#role-{c}" data-tip="{E(self.roles[c]["text"])}">{E(self.roles[c]["name"])}</a>' for c in codes)

    def skill_link(self, anchor, name=None):
        nm = name or next((s[0] for r in self.d['professions']['roles'] for s in r['skills'] if s[1] == anchor), anchor)
        return f'<a href="https://ddat-capability-framework.service.gov.uk/skills/#{E(anchor)}">{E(nm)}</a>'

    @staticmethod
    def stage_pills(ch, sid):
        return ' '.join(f'<a class="pill" href="#{x["id"]}">{E(x["id"])}</a>' for x in ch['items'] if x['stage'] == sid)

    @staticmethod
    def cr_ids(ids):
        return ' '.join(f'<a class="pill" href="capability-model.html#{c}">{E(c)}</a>' for c in ids) or 'all capabilities'

    def flag_check_url(self, c):
        q = urllib.parse.urlencode({'template': 'flag-check.yml', 'title': f'[Flag] {c["id"]}: {c["name"]}', 'capability': c['id'], 'current': FLAGS[c['flag']][0]})
        return f'https://github.com/{self.m["repo"]}/issues/new?{q}'

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
<dt>{icon(cov)} In this portal</dt><dd><strong>{E(c["coverage"])}</strong>: <a href="{E(c["playbook"])}">{E({k: l for k, l, _ in NAV}.get(c["playbook"][:-5], c["playbook"]))}</a></dd></dl>
<p class="flag-check"><a href="{E(self.flag_check_url(c))}">{icon("flag")}Check this flag</a> <span class="hint">Think {E(c["id"])} should be flagged differently? Tell us why.</span></p></li>'''
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
                ('cm-dama', 'DAMA wheel', self.dama_html()), ('cm-self', 'Self-assessment', selfa), ('cm-cross', 'Crosswalk', cross)]
        body = self.hero('radar', 'Frameworks', 'Capability model',
                         'Everything the DAM Policy and its related guidance need an organisation to be able to do, how each need is stated, and how mature you are.',
                         brief=[f'{fc["E"]} capabilities are explicit in the policy, {fc["I"]} implicit and {fc["N"]} inferred.', 'Every flag points to the section of GOV.UK guidance it comes from.', 'Assess yourself against the government maturity model and four DAM strands.'],
                         meta=[('radar', f'{len(cm)} capabilities'), ('signpost', f'{sum(len(c["signposts"]) for c in cm)} signposts'), ('layers', '10 topics, 6 themes, 5 levels')])
        body += self.tabbed(tabs, 'Capability model views')
        drawer = [{'label': 'Views', 'icon': 'radar', 'items': [{'id': k, 'label': l, 'icon': ic} for (k, l, _), ic in zip(tabs, ['grid-3x3', 'signpost', 'layers', 'circle', 'chart-column', 'arrow-right-left'])]},
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
{self.change_roles_html()}
<h2 id="practices">{icon("list-checks")} Practices</h2>{progress_widget(all_ids, "All practices")}
<div class="filters" data-filter="ch-list" role="group" aria-label="Filter practices"><div><label for="c-m">Setting</label><select id="c-m" name="mode"><option value="">All</option><option value="bau">Business as usual</option><option value="change">Change programmes</option></select></div>
<div><label for="c-s">Stage</label><select id="c-s" name="stage"><option value="">All</option>{st_opts}</select></div><div><label for="c-q">Contains</label><input id="c-q" type="search" name="q"></div><p class="count-out" aria-live="polite"></p></div>
<ul class="cr-list" id="ch-list">{cards}</ul>
<p>Download every action as <a href="data/change-checklist.csv">CSV</a> to load into your own plan or tracker.</p>
<div class="notice-box">{icon("info")}<p>These practices are this portal's synthesis{prov("O")} of the rulebook entries listed with each one. They add no new requirements; where they differ from your department's own delivery or assurance rules, follow your department.</p></div>'''
        drawer = [{'label': 'Delivery and change', 'icon': 'construction', 'items': [
            {'id': 'gaps', 'label': 'What the policy leaves to you', 'icon': 'flag', 'count': len(gaps)},
            {'id': 'lifecycle', 'label': 'Across the life cycle', 'icon': 'route', 'count': len(ch['stages'])},
            {'id': 'programme-roles', 'label': 'Programme roles', 'icon': 'users-round', 'count': len(ch['programme_roles']['rows']), 'new': True},
            {'id': 'blueprint', 'label': 'Programme blueprint', 'icon': 'workflow', 'count': len(ch['programme_roles']['blueprint']), 'new': True},
            {'id': 'practices', 'label': 'Practices', 'icon': 'list-checks', 'count': len(ch['items'])}]},
                  {'label': 'Practices', 'icon': 'list-checks', 'items': [{'id': x['id'], 'label': x['title'], 'icon': x['icon']} for x in ch['items']]}]
        return self.page('change', 'Delivery and change', body, drawer, crumbs=['Playbooks', 'Delivery and change'])

    # -- version 1.5.1: open data and testing ------------------------------------------------
    def datasets(self):
        """Each dataset the portal publishes, with its files. The DCAT catalogue, the Open data page and check C-28 all use this list."""
        d = self.d
        ds = [
            ('requirements', 'DAM Policy requirements', 'Every requirement in the DAM Policy and its guidance, with strength, capability, source and provenance.', ['requirements.csv'], ['requirements', 'policy']),
            ('capability-map', 'Capability requirements map', f'{len(d.get("capmap", []))} capabilities the policy and adjacent guidance need, flagged explicit, implicit or inferred, with signposts to the exact GOV.UK sections.', ['capability-map.csv'], ['capability model', 'maturity']),
            ('maturity-structure', 'Data maturity model structure', 'Topics, themes and row counts of the Data Maturity Assessment for Government, with links to each topic. Structure only; the framework text is not copied.', ['maturity-structure.csv'], ['data maturity']),
            ('vocabulary', 'Data asset management vocabulary', 'Glossary and thesaurus as SKOS concepts, with definitions, alternative labels and broader terms.', ['vocabulary.ttl', 'vocabulary.jsonld', 'glossary.csv'], ['glossary', 'SKOS', 'thesaurus']),
            ('metadata-dictionary', 'Metadata data dictionary', 'The metadata properties to record for critical data assets, with obligation and Metadata Exchange Model slot.', ['metadata-dictionary.csv'], ['metadata', 'DCAT']),
            ('templates', 'Playbook templates', 'Fields of every template in the three playbooks, all together and one template at a time; workbooks also as tabbed spreadsheets.',
             ['templates.csv'] + [f for c in d['capabilities'] for t in c.get('templates', []) for f in
                                  ([f'templates/{t["id"]}.ods'] + [f'templates/{t["id"]}-{slug(sh["name"])}.csv' for sh in t['sheets']] if t.get('sheets') else [f'templates/{t["id"]}.csv'])],
             ['templates']),
            ('sector-rules', 'Sector data quality rules', f'{sum(len(x["rules"]) for x in d.get("supplements", []))} starter quality rules for {len(d.get("supplements", []))} kinds of data, runnable with the Data Quality Commons kit.',
             ['sector-rules.csv'] + [f'rules/{x["id"].lower()}.yaml' for x in d.get('supplements', [])], ['data quality', 'rules', 'dqkit']),
            ('change-checklist', 'Delivery and change actions', 'Actions for embedding the DAM Policy in business as usual and change programmes.', ['change-checklist.csv'], ['change', 'delivery']),
            ('xref', 'Cross-reference manifest', 'The shared keys this portal uses (DAMA areas, requirements, capabilities, practices, sectors, roles, tool categories) and where each lives, so sister portals and tools can link to them.', ['xref.json'], ['interoperability', 'linked data']),
            ('interoperability-questions', 'Tool interoperability questions', 'Questions for a request for information or tender for catalogue, data quality, lineage and governance tools, to test interoperability and avoid lock-in.', ['interoperability-questions.csv'], ['procurement', 'interoperability', 'RFI']),
            ('backlog', 'Product backlog and roadmap', 'Every backlog item with its user story, source, status, strategy links, assessment and score, and the roadmap it produces.', ['backlog.csv', 'backlog.json'], ['roadmap', 'backlog', 'user research']),
            ('lineage', 'Ontology and lineage', 'An OWL ontology of the portal and PROV-O lineage from sources to policy requirements, capabilities, portal requirements, pages and checks.', ['ontology.ttl', 'lineage.ttl'], ['lineage', 'PROV-O', 'OWL']),
            ('ddat-role-skills', 'Data role skills and levels', 'Skills and skill levels for Digital and Data capability framework roles with data asset management duties.', ['ddat-role-skills.csv'], ['skills', 'professions']),
            ('rulebook', 'Related policies, standards and legislation', 'Every policy, standard, piece of legislation and framework the portal links to, with publisher and update date.', ['rulebook.csv', 'sources.jsonld'], ['rulebook', 'standards']),
            ('traceability', 'Portal requirements traceability', 'Each portal requirement, the features that meet it and the checks that prove it.', ['traceability.csv'], ['traceability']),
            ('playbooks', 'Full portal content', 'Everything on the portal in one JSON file.', ['playbooks.json'], ['playbooks']),
            ('status', 'Portal health', 'Latest automated health run: source currency, signposted sections, links and page weight.', ['status.json'], ['status']),
        ]
        return [dict(id=a, title=b, desc=c, files=[f for f in fs if (self.out / 'data' / f).exists() or f == 'status.json' and self.status], kw=k) for a, b, c, fs, k in ds]

    MEDIA = {'.csv': 'text/csv', '.ods': 'application/vnd.oasis.opendocument.spreadsheet', '.json': 'application/json', '.jsonld': 'application/ld+json', '.ttl': 'text/turtle', '.yaml': 'application/yaml'}

    def write_catalogue(self, out):
        """A DCAT 3 catalogue of the portal's own datasets, as JSON-LD and Turtle, for harvesters such as CKAN and data.gov.uk."""
        m, base = self.m, self.m['site_url']
        lic = m['licence_content_url']
        pub = {'@id': base + '#publisher', '@type': 'foaf:Agent', 'foaf:name': m['title'] + ' (prototype)'}
        contact = {'@type': 'vcard:Kind', 'vcard:fn': 'Contact form', 'vcard:hasURL': {'@id': base + 'contact.html'}}
        dsets = []
        for x in self.datasets():
            dsets.append({'@id': base + 'data.html#' + x['id'], '@type': 'dcat:Dataset', 'dcterms:identifier': f'{m["id"]}-{x["id"]}',
                          'dcterms:title': {'@value': x['title'], '@language': 'en-GB'}, 'dcterms:description': {'@value': x['desc'], '@language': 'en-GB'},
                          'dcat:keyword': x['kw'], 'dcterms:license': {'@id': lic}, 'dcterms:publisher': pub, 'dcat:contactPoint': contact,
                          'dcterms:modified': {'@value': m['as_of'], '@type': 'xsd:date'}, 'dcat:version': m['version'],
                          'dcat:landingPage': {'@id': base + 'data.html#' + x['id']},
                          'dcat:distribution': [{'@id': base + 'data/' + f + '#distribution', '@type': 'dcat:Distribution', 'dcterms:title': f,
                                                 'dcat:downloadURL': {'@id': base + 'data/' + f}, 'dcat:accessURL': {'@id': base + 'data/' + f},
                                                 'dcat:mediaType': {'@id': 'https://www.iana.org/assignments/media-types/' + self.MEDIA[Path(f).suffix]},
                                                 'dcterms:license': {'@id': lic}} for f in x['files']]})
        cat = {'@context': {'dcat': 'http://www.w3.org/ns/dcat#', 'dcterms': 'http://purl.org/dc/terms/', 'foaf': 'http://xmlns.com/foaf/0.1/',
                            'vcard': 'http://www.w3.org/2006/vcard/ns#', 'xsd': 'http://www.w3.org/2001/XMLSchema#'},
               '@id': base + 'data/catalogue.jsonld', '@type': 'dcat:Catalog', 'dcterms:title': {'@value': m['title'] + ': open data', '@language': 'en-GB'},
               'dcterms:description': {'@value': 'Open data published by the DAM capability playbooks prototype. Not an official government catalogue.', '@language': 'en-GB'},
               'dcterms:publisher': pub, 'dcterms:license': {'@id': lic}, 'dcterms:modified': {'@value': m['as_of'], '@type': 'xsd:date'},
               'dcat:contactPoint': contact, 'foaf:homepage': {'@id': base}, 'dcat:dataset': dsets}
        (out / 'catalogue.jsonld').write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding='utf-8')
        q = lambda t: '"' + str(t).replace('\\', '\\\\').replace('"', '\\"') + '"'
        ttl = ['@prefix dcat: <http://www.w3.org/ns/dcat#> .', '@prefix dcterms: <http://purl.org/dc/terms/> .', '@prefix foaf: <http://xmlns.com/foaf/0.1/> .',
               '@prefix vcard: <http://www.w3.org/2006/vcard/ns#> .', '@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .', '',
               f'<{base}#publisher> a foaf:Agent ; foaf:name {q(pub["foaf:name"])}@en-GB .', '',
               f'<{base}data/catalogue.jsonld> a dcat:Catalog ; dcterms:title {q(m["title"] + ": open data")}@en-GB ; dcterms:publisher <{base}#publisher> ;',
               f'  dcterms:description {q("Open data published by the DAM capability playbooks prototype. Not an official government catalogue.")}@en-GB ;',
               f'  dcat:contactPoint [ a vcard:Kind ; vcard:fn "Contact form" ; vcard:hasURL <{base}contact.html> ] ;',
               f'  dcterms:license <{lic}> ; dcterms:modified "{m["as_of"]}"^^xsd:date ; foaf:homepage <{base}> ;',
               '  dcat:dataset ' + ' , '.join(f'<{base}data.html#{x["id"]}>' for x in self.datasets()) + ' .', '']
        for x in self.datasets():
            dist = ' , '.join(f'<{base}data/{f}#distribution>' for f in x['files'])
            ttl.append(f'<{base}data.html#{x["id"]}> a dcat:Dataset ; dcterms:identifier {q(m["id"] + "-" + x["id"])} ; dcterms:title {q(x["title"])}@en-GB ;\n'
                       f'  dcterms:description {q(x["desc"])}@en-GB ; ' + ' ; '.join(f'dcat:keyword {q(k)}@en-GB' for k in x['kw']) + ' ;\n'
                       f'  dcterms:license <{lic}> ; dcterms:publisher <{base}#publisher> ; dcterms:modified "{m["as_of"]}"^^xsd:date ; dcat:version {q(m["version"])} ;\n'
                       f'  dcat:contactPoint [ a vcard:Kind ; vcard:fn "Contact form" ; vcard:hasURL <{base}contact.html> ] ;\n'
                       f'  dcat:landingPage <{base}data.html#{x["id"]}> ; dcat:distribution {dist} .')
            for f in x['files']:
                ttl.append(f'<{base}data/{f}#distribution> a dcat:Distribution ; dcterms:title {q(f)} ; dcat:downloadURL <{base}data/{f}> ; dcat:accessURL <{base}data/{f}> ;\n'
                           f'  dcat:mediaType <https://www.iana.org/assignments/media-types/{self.MEDIA[Path(f).suffix]}> ; dcterms:license <{lic}> .')
            ttl.append('')
        (out / 'catalogue.ttl').write_text('\n'.join(ttl), encoding='utf-8')

    def p_data(self):
        m, base = self.m, self.m['site_url']
        ds = self.datasets()
        rows = []
        for x in ds:
            files = ' '.join(f'<a class="pill" href="data/{E(f)}">{icon("download")}{E(f.split("/")[-1])}</a>' for f in x['files'][:6])
            more = (f' <details class="more-files"><summary>{len(x["files"]) - 6} more files</summary>'
                    + ' '.join(f'<a class="pill" href="data/{E(f)}">{icon("download")}{E(f.split("/")[-1])}</a>' for f in x['files'][6:]) + '</details>') if len(x['files']) > 6 else ''
            rows.append([f'<span id="{x["id"]}">{E(x["title"])}</span>', E(x['desc']), files + more])
        sd = {'@type': 'DataCatalog', 'name': m['title'] + ': open data', 'url': base + 'data.html',
              'dataset': [{'@type': 'Dataset', 'name': x['title'], 'description': x['desc'], 'url': base + 'data.html#' + x['id'],
                           'identifier': f'{m["id"]}-{x["id"]}', 'keywords': x['kw'], 'license': m['licence_content_url'], 'isAccessibleForFree': True,
                           'dateModified': m['as_of'], 'version': m['version'], 'creator': {'@type': 'Organization', 'name': m['title'] + ' (prototype)', 'url': base},
                           'distribution': [{'@type': 'DataDownload', 'contentUrl': base + 'data/' + f, 'encodingFormat': self.MEDIA[Path(f).suffix]} for f in x['files']]} for x in ds]}
        body = self.hero('download', 'Open data', 'Open data', 'Everything on this portal is also published as open data that people and other portals can reuse.',
                         brief=['Download any dataset in open formats, under the Open Government Licence.', 'Harvest the whole set through a DCAT catalogue.', 'Files can be fetched directly from other websites.'],
                         meta=[('database', f'{len(ds)} datasets'), ('file-text', f'{sum(len(x["files"]) for x in ds)} files'), ('scale', m['licence_content'])])
        body += f'''<h2 id="datasets">{icon("database")} Datasets</h2>
{table("t-datasets", "Datasets published by this portal", ["Dataset", "What it contains", "Download"], rows)}
<h2 id="harvest">{icon("share-2")} Harvesting and reuse</h2>
<ul><li><strong>Catalogue.</strong> A DCAT 3 catalogue of every dataset and file: <a href="data/catalogue.jsonld">JSON-LD</a> and <a href="data/catalogue.ttl">Turtle</a>. Every page links to it in its header, so harvesters can find it from any address.</li>
<li><strong>Each dataset</strong> carries an identifier, title, description, keywords, licence, publisher, contact point (the contact form), modification date and version.</li>
<li><strong>Search engines.</strong> This page describes each dataset with schema.org markup, which dataset search services read.</li>
<li><strong>Direct access.</strong> Files are served with permission for other websites to fetch them, so other portals and tools can read them directly.</li>
<li><strong>Vocabulary.</strong> Concepts are published as SKOS, so other glossaries and catalogues can link to them.</li>
<li><strong>Updates.</strong> Files change only with a release. The version and date are in every file's catalogue entry and on <a href="whats-new.html">What's new</a>.</li></ul>
<div class="notice-box">{icon("info")}<p>This is a prototype, not an official government catalogue. Where data repeats GOV.UK guidance, the GOV.UK page is the authority. The sources it draws on are catalogued separately in <a href="data/sources.jsonld">sources.jsonld</a>.</p></div>'''
        drawer = [{'label': 'Open data', 'icon': 'download', 'items': [{'id': 'datasets', 'label': 'Datasets', 'icon': 'database', 'count': len(ds)},
                                                                        {'id': 'harvest', 'label': 'Harvesting and reuse', 'icon': 'share-2', 'count': 6}]}]
        return self.page('data', 'Open data', body, drawer, crumbs=['Open data'], jsonld={'mainEntity': sd})

    def p_test(self):
        d, m, t = self.d, self.m, self.d['testing']
        pers = {p['id']: p for p in d['personas']}
        form = f'https://github.com/{m["repo"]}/issues/new'
        cards = ''
        for x in t['tasks']:
            who = 'Everyone' if 'all' in x['roles'] else ', '.join(pers[r]['title'] for r in x['roles'])
            fb = form + '?' + urllib.parse.urlencode({'template': t['feedback_form'], 'title': f'[Testing] {x["id"]}: {x["title"]}', 'task': x['id']})
            data_roles = 'all ' + ' '.join(pers) if 'all' in x['roles'] else ' '.join(x['roles'])
            cards += (f'<li class="cr-card test-task" id="{x["id"]}" data-item data-role="{data_roles}"><div class="cr-head"><span class="lv-n">{E(x["id"][2:])}</span><div><p class="caption">{E(x["id"])} · {E(who)}</p><h3>{E(x["title"])}</h3></div></div>'
                      f'<p><strong>Done when:</strong> {E(x["done"])}</p>'
                      f'<p class="sa-actions"><a class="btn secondary" href="{E(x["start"])}">{icon("play")}Start this task</a> <a class="btn secondary" href="{E(fb)}">{icon("message-square-text")}Tell us how it went</a> '
                      + (f'<a class="btn secondary" href="{E(self.ms_form_link(x["id"] + ": " + x["title"], "task"))}" rel="noopener" data-ms-form>{icon("lock-keyhole")}Tell us privately</a> ' if self.ms_form_url() else '')
                      + f'{mark_done("test:" + x["id"], "Done")}</p></li>')
        opts = ''.join(f'<option value="{p["id"]}">{E(p["title"])}</option>' for p in d['personas'])
        ids = ['test:' + x['id'] for x in t['tasks']]
        body = self.hero('play', 'Help us test', 'Help us test this portal', E(t['intro']),
                         brief=['Pick the tasks closest to your role.', 'Try each one without help, then tell us how it went.', 'Task feedback is public on GitHub' + (', or tell us privately with the Microsoft form, which needs no sign-in' if self.ms_form_url() else '') + '. Do not include names or sensitive information.'],
                         meta=[('list-checks', f'{len(t["tasks"])} tasks'), ('clock', 'About 20 minutes'), ('users-round', f'{len(d["personas"])} roles')])
        body += f'''<h2 id="how">{icon("route")} How to take part</h2>
<ol><li>Choose your role below to see the tasks for it.</li><li>Select <strong>Start this task</strong>. Try to finish it without asking anyone.</li>
<li>Select <strong>Tell us how it went</strong>. Say whether you finished, how easy it was from 1 to 7, and what got in your way.</li>
<li>Tick <strong>Done</strong> to keep track. This is kept in your browser only.</li></ol>
<p>If you use a screen reader, magnifier, voice control or other assistive technology, your feedback is especially valuable. The form lets you say so.</p>
<h2 id="tasks">{icon("list-checks")} Tasks</h2>{progress_widget(ids, "Tasks done")}
<div class="filters" data-filter="task-list" role="group" aria-label="Filter tasks by role"><div><label for="t-role">Your role</label><select id="t-role" name="role"><option value="">All roles</option>{opts}</select></div><p class="count-out" aria-live="polite"></p></div>
<ul class="cr-list two" id="task-list">{cards}</ul>
<h2 id="after">{icon("message-square-text")} What happens to your feedback</h2>
<p>Feedback is read by the people maintaining this prototype, grouped by task and role, and used to decide what to change. Changes are listed on <a href="whats-new.html">What's new</a>.</p>
<p>The task feedback links open GitHub, where messages are public and you need a free account. <strong>Tell us privately</strong> opens a Microsoft form instead, with the task filled in; you do not need to sign in.</p>{self.ms_form_block('test', 'Help us test', 'task')}
<h2 id="other">{icon("circle-help")} Anything else</h2><p>For anything not covered by a task, use the <a href="contact.html">contact form</a> or the "was this page useful?" link at the bottom of every page.</p>'''
        drawer = [{'label': 'Testing', 'icon': 'play', 'items': [{'id': 'how', 'label': 'How to take part', 'icon': 'route', 'count': 4},
                                                                  {'id': 'tasks', 'label': 'Tasks', 'icon': 'list-checks', 'count': len(t['tasks'])},
                                                                  {'id': 'after', 'label': 'What happens next', 'icon': 'message-square-text'},
                                                                  {'id': 'other', 'label': 'Anything else', 'icon': 'circle-help'}]}]
        return self.page('test', 'Help us test', body, drawer, crumbs=['Help us test'])

    # -- version 1.6: perspectives (lenses) ----------------------------------------------------
    def ch_pills(self, ids):
        t = {x['id']: x for x in self.d['change']['items']}
        return ' '.join(f'<a class="pill" href="change.html#{c}" data-tip="{E(t[c]["why"])}">{E(c)} {E(t[c]["title"])}</a>' for c in ids)

    def p_lenses(self):
        d, L = self.d, self.d['lenses']
        caps = L['caps_order']
        lvl = {'Strong': 3, 'Partial': 2, 'Gap': 1}
        def cell(v, before=None):
            arrow = f' <span class="hint">(was {E(before)})</span>' if before and before != v else ''
            return f'<span class="cov cov-{v.lower()}">{E(v)}</span>{arrow}'
        rows = [[f'<a href="#{x["id"]}">{icon(x["icon"])} {E(x["name"])}</a>'] + [cell(x['cover_now'][c], x['cover_before'][c]) for c in caps] for x in L['items']]
        assess = (f'<p>How well this portal covers each capability through each lens, judged against the questions and actions each community needs{prov("O")}. '
                  'Where a rating changed in this release, the earlier rating is shown.</p>'
                  + table('t-lens-cov', 'Coverage of each capability through each lens', ['Lens'] + [self.caps[c]['name'] for c in caps], rows)
                  + '<p class="hint">Strong: questions, actions and verified sources for every capability. Partial: covered in general terms or for some capabilities. Gap: not covered.</p>')
        tabs = [('lens-overview', 'Overview', f'<p>{E(L["intro"])}</p><h2 id="coverage">{icon("grid-3x3")} Coverage assessment</h2>{assess}')]
        for x in L['items']:
            acts = ''.join(f'<div class="panel"><h4>{icon(CAP_ICONS[c])} {E(self.caps[c]["name"])}</h4>{ul(x["actions"][c], cls="ticks")}</div>' for c in caps)
            prof = ' '.join(f'<a class="pill" href="professions.html#{p}">{E(self.prof[p]["name"].split(" (")[0])}</a>' for p in x['profs'])
            body = (f'<section id="{x["id"]}" aria-labelledby="h-{x["id"]}"><div class="cr-head">{tile(x["icon"], "lg")}<div><p class="caption">Lens</p><h2 id="h-{x["id"]}">{E(x["name"])}</h2></div></div>'
                    f'<p class="lede">{E(x["means"])}{prov("O")}</p>'
                    f'<h3>{icon("circle-help")} Questions to ask</h3>{ul(x["questions"])}'
                    f'<h3>{icon("list-checks")} What to do, by capability</h3><div class="cols">{acts}</div>'
                    f'<h3>{icon("triangle-alert")} Pitfalls</h3>{ul(x["pitfalls"])}'
                    f'<h3>{icon("signpost")} Where to go next</h3><p><strong>Capabilities:</strong> {" ".join(self.cr_pill(c) for c in x["cr"])}</p>'
                    f'<p><strong>Practices:</strong> {self.ch_pills(x["ch"])}</p>'
                    f'<p><strong>Professions:</strong> {prof}</p>'
                    f'<h3>{icon("scale")} Rulebook</h3><ul>{"".join(f"<li>{self.rb_link(r)}</li>" for r in x["refs"])}</ul>'
                    f'<p class="hint"><strong>Coverage:</strong> {E(x["gap"])}</p></section>')
            tabs.append((f'tab-{x["id"].lower()}', x['name'], body))
        hero = self.hero('eye', 'Frameworks', 'Perspectives', 'What the DAM Policy means for data, digital, cyber, technology and commercial teams, and for tackling legacy, with what each should ask and do.',
                         brief=['Find your own community\'s lens.', 'Each lens gives questions, actions for each capability, pitfalls and verified sources.', 'A coverage assessment shows where the portal is strong and where it is still thin.'],
                         meta=[('eye', f'{len(L["items"])} lenses'), ('scale', f'{len({r for x in L["items"] for r in x["refs"]})} sources')])
        drawer = [{'label': 'Lenses', 'icon': 'eye', 'items': [{'id': 'coverage', 'label': 'Coverage assessment', 'icon': 'grid-3x3', 'count': len(L['items'])}]
                   + [{'id': x['id'], 'label': x['name'], 'icon': x['icon'], 'new': True} for x in L['items']]}]
        return self.page('perspectives', 'Perspectives', hero + self.tabbed(tabs, 'Perspectives'), drawer, crumbs=['Frameworks', 'Perspectives'])

    # -- version 1.7: programme roles, DAMA view, working together ------------------------------
    def change_roles_html(self):
        ch, pr = self.d['change'], self.d['change']['programme_roles']
        stg = {s['id']: s['name'] for s in ch['stages']}
        rows = [[f'<span id="role-{r["role"]}">{E(self.roles[r["role"]]["name"])}</span>', ul(r['resp']), E(', '.join(stg[s] for s in r['stages'])),
                 self.role_pills(r['works_with']), '; '.join(self.rb_link(x) for x in r['refs'])] for r in pr['rows']]
        lanes = [('user', 'What the programme does'), ('front', 'What users and boards see'), ('back', 'Behind the scenes'), ('data', 'Data roles'), ('support', 'Support and assurance')]
        bp = '<div class="table-wrap" role="region" aria-labelledby="t-bp-chg" tabindex="0"><table class="blueprint"><caption id="t-bp-chg">Service blueprint: data asset management across a programme</caption><thead><tr><th scope="col">Lane</th>' + ''.join(f'<th scope="col">{E(stg[b["stage"]])}</th>' for b in pr['blueprint']) + '</tr></thead><tbody>'
        bp += ''.join(f'<tr><th scope="row">{E(lbl)}</th>' + ''.join(f'<td>{E(b[k])}</td>' for b in pr['blueprint']) + '</tr>' for k, lbl in lanes) + '</tbody></table></div>'
        return (f'<h2 id="programme-roles">{icon("users-round")} Programme roles with data responsibilities</h2><p>{E(pr["intro"])}{prov("O")}</p>'
                + table('t-prg-roles', 'Data responsibilities of programme and project roles', ['Role', 'Data responsibilities', 'Stages', 'Works with', 'Rules'], rows)
                + f'<p>These roles also appear on the <a href="together.html#roles">roles list</a>, the <a href="personas.html#persona-prg">programme or project lead route</a> and in the practices below.</p>'
                + f'<h2 id="blueprint">{icon("workflow")} Service blueprint for a programme</h2><p>What happens to critical data at each stage, front stage and back stage{prov("O")}.</p>{bp}')

    def dama_wheel_svg(self, areas, counts):
        cx = cy = 260
        r0, r1 = 92, 245
        outer = [a for a in areas if a['id'] != self.d['dama']['hub']]
        hub = next(a for a in areas if a['id'] == self.d['dama']['hub'])
        n = len(outer)
        mx = max(counts.values()) or 1
        parts = []
        for i, a in enumerate(outer):
            t0 = -math.pi / 2 + i * 2 * math.pi / n + 0.012
            t1 = -math.pi / 2 + (i + 1) * 2 * math.pi / n - 0.012
            p = lambda r, t: f'{cx + r * math.cos(t):.1f},{cy + r * math.sin(t):.1f}'
            path = f'M{p(r0, t0)} L{p(r1, t0)} A{r1},{r1} 0 0 1 {p(r1, t1)} L{p(r0, t1)} A{r0},{r0} 0 0 0 {p(r0, t0)} Z'
            h = 0 if not counts[a['id']] else min(4, 1 + counts[a['id']] * 4 // (mx + 1))
            tm, rm = (t0 + t1) / 2, (r0 + r1) / 2 + 8
            words, lines, cur = a['name'].split(), [], ''
            for w in words:
                if len(cur) + len(w) > 13 and cur:
                    lines.append(cur); cur = w
                else:
                    cur = (cur + ' ' + w).strip()
            lines.append(cur)
            lx, ly = cx + rm * math.cos(tm), cy + rm * math.sin(tm) - (len(lines) - 1) * 7
            txt = ' '.join(f'<tspan x="{lx:.1f}" y="{ly + k * 14:.1f}">{E(l)}</tspan>' for k, l in enumerate(lines))
            parts.append(f'<a href="#{a["id"].lower()}" data-area="{a["id"]}"><title>{E(a["name"])}: {counts[a["id"]]} DAM capabilities</title><path class="seg h{h}" d="{path}"/><text class="seg-l h{h}" text-anchor="middle">{txt}</text></a>')
        parts.append(f'<a href="#{hub["id"].lower()}" data-area="{hub["id"]}"><title>{E(hub["name"])}: {counts[hub["id"]]} DAM capabilities</title><circle class="seg hub" cx="{cx}" cy="{cy}" r="{r0 - 6}"/>'
                     f'<text class="seg-l hub" text-anchor="middle"><tspan x="{cx}" y="{cy - 4}">Data</tspan> <tspan x="{cx}" y="{cy + 14}">governance</tspan></text></a>')
        return f'<svg class="dama-wheel" viewBox="0 0 520 520" role="group" aria-label="Data management knowledge areas arranged as a wheel around data governance">{"".join(parts)}</svg>'

    def topic_pills(self, topics):
        mt = self.d['maturity']
        return ' '.join(f'<a class="pill" href="{E(mt["url"])}#{E(mt["topics"][t - 1]["anchor"])}">{t}. {E(mt["topics"][t - 1]["name"])}</a>' for t in topics) or 'None'

    def dama_html(self):
        d, dm = self.d, self.d['dama']
        pers = {p['id']: p for p in d['personas']}
        caps_for = {a['id']: [c for c in d['capmap'] if a['dmbok'] in c['dmbok']] for a in dm['areas']}
        counts = {k: len(v) for k, v in caps_for.items()}
        mt = d['maturity']
        cards = ''
        for a in dm['areas']:
            cs = caps_for[a['id']]
            topics = sorted({t for c in cs for t in c['dma']})
            urows = ''.join(f'<tr data-r="{pid}"><th scope="row">{E(pers[pid]["title"])}</th><td>{E(u)}</td></tr>' for pid, u in a['uses'].items())
            cards += (f'<section class="cr-card dama-area" id="{a["id"].lower()}" aria-labelledby="h-{a["id"]}"><h3 id="h-{a["id"]}">{E(a["name"])}</h3>'
                      f'<p>{E(a["desc"])}{prov("O")}</p>'
                      f'<dl class="cr-dl"><dt>{icon("radar")} DAM capabilities</dt><dd>{" ".join(self.cr_pill(c["id"]) for c in cs) or "None directly; it supports analysis built on critical assets."}</dd>'
                      f'<dt>{icon("layers")} Maturity topics</dt><dd>{self.topic_pills(topics)}</dd>'
                      f'<dt>{icon("archive")} Records and information counterpart</dt><dd>{E(a["im"])}</dd></dl>'
                      f'<details class="dama-uses"><summary>How each role uses it</summary>{table("t-uses-" + a["id"], "How each role uses " + a["name"].lower(), ["Role", "Use"], [[E(pers[p]["title"]), E(u)] for p, u in a["uses"].items()])}</details></section>')
        opts = ''.join(f'<option value="{p}">{E(pers[p]["title"])}</option>' for p in pers)
        life = [[E(x['data']), E(x['records']), E(x['dam']), E(x['who'])] for x in dm['lifecycle']]
        return (f'<p>{E(dm["intro"])}</p><p class="hint">Knowledge area names follow DAMA-DMBOK{prov("K")}; this wheel, its descriptions and the role guidance are this portal\'s own{prov("O")}. See {self.rb_link("RB-DAMA")}.</p>'
                f'<div class="dama-wrap"><div>{self.dama_wheel_svg(dm["areas"], counts)}<p class="hint">Darker segments are touched by more DAM capabilities. Select a segment to read about it.</p></div>'
                f'<div class="dama-side"><div class="field js-only"><label for="dama-role"><strong>Show guidance for</strong></label><select id="dama-role"><option value="">All roles</option>{opts}</select></div>'
                f'<p>Choosing a role opens "How each role uses it" in every area and highlights your row.</p>'
                + table('t-dama-count', 'DAM capabilities in each knowledge area', ['Knowledge area', 'Capabilities'], [[f'<a href="#{a["id"].lower()}">{E(a["name"])}</a>', str(counts[a["id"]])] for a in dm['areas']]) + '</div></div>'
                f'<div class="dama-areas">{cards}</div>'
                f'<h3 id="lifecycles">{icon("refresh-cw")} Data and records life cycles side by side</h3>'
                + table('t-lifecycles', 'The data life cycle, the records life cycle and where DAM acts', ['Data life cycle', 'Records life cycle', 'Where DAM acts', 'Who'], life)
                + f'<h3>{icon("book-marked")} Records and information management frameworks and standards</h3><ul>{"".join(f"<li>{self.rb_link(r)}</li>" for r in dm["im_refs"])}</ul>')

    def p_community(self):
        d, j = self.d, self.d['joinup']
        pers = {p['id']: p for p in d['personas']}
        recs = ''
        for x in j['recs']:
            recs += (f'<li class="cr-card" id="{x["id"]}"><div class="cr-head"><span class="lv-n">{E(x["id"][2:])}</span><div><p class="caption">{E(x["id"])}</p><h3>{E(x["title"])}</h3></div>{mark_done("join:" + x["id"], "Done")}</div>'
                     f'<p><strong>Do:</strong> {E(x["action"])}</p><p><strong>Outcome:</strong> {E(x["outcome"])}</p><p><strong>Measure:</strong> {E(x["measure"])}</p>'
                     f'<p><strong>Who:</strong> {self.role_pills(x["who"])}</p></li>')
        com = ''.join(f'<li data-item data-role="{" ".join(c["for_"])}"><a href="{E(c["url"])}">{E(c["name"])}</a>{prov(c["prov"], self.m["verified_on"])}<span class="hint">{E(c["what"])} For: {E(", ".join(pers[p]["title"] for p in c["for_"]))}</span></li>' for c in j['communities'])
        opts = ''.join(f'<option value="{p}">{E(pers[p]["title"])}</option>' for p in pers)
        profs = d['professions']['profs']
        mrows = []
        for c in d['capmap']:
            mrows.append([f'<a href="capability-model.html#{c["id"]}">{E(c["id"])} {E(c["name"])}</a>'] + [('<span class="sk sk-P" title="Contributes">Yes</span>' if p['id'] in c['profs'] else '') for p in profs])
        ids = ['join:' + x['id'] for x in j['recs']]
        body = self.hero('handshake', 'Frameworks', 'Working together', 'How data, records and information, security, digital, technology, analysis, commercial and delivery professionals can act on the same critical assets.',
                         brief=['Ten practical recommendations, each with an action, an outcome and a measure.', 'Communities and networks to join, filtered by role.', 'A map of which professions contribute to which capabilities.'],
                         meta=[('handshake', f'{len(j["recs"])} recommendations'), ('users-round', f'{len(j["communities"])} communities'), ('briefcase', f'{len(profs)} professions')])
        body += (f'<h2 id="recommendations">{icon("list-checks")} Recommendations</h2><p>{E(j["intro"])}{prov("O")}</p>{progress_widget(ids, "Recommendations done")}<ul class="cr-list two">{recs}</ul>'
                 f'<h2 id="communities">{icon("users-round")} Communities and networks</h2>'
                 f'<div class="filters" data-filter="com-list" role="group" aria-label="Filter communities by role"><div><label for="c-role">Your role</label><select id="c-role" name="role"><option value="">All roles</option>{opts}</select></div><p class="count-out" aria-live="polite"></p></div>'
                 f'<ul class="rulebook" id="com-list">{com}</ul>'
                 f'<h2 id="map">{icon("grid-3x3")} Who contributes to what</h2><p>Professions that contribute to each capability, from the capability model. Use it to decide who to bring to the table for each asset.</p>'
                 + table('t-prof-map', 'Professions contributing to each capability', ['Capability'] + [p['name'].split(' (')[0] for p in profs], mrows)
                 + f'<p>See also <a href="perspectives.html">Perspectives</a> for what each community should ask and do, and <a href="professions.html">Professions and skills</a> for career routes.</p>')
        drawer = [{'label': 'Working together', 'icon': 'handshake', 'items': [{'id': 'recommendations', 'label': 'Recommendations', 'icon': 'list-checks', 'count': len(j['recs'])},
                                                                              {'id': 'communities', 'label': 'Communities', 'icon': 'users-round', 'count': len(j['communities'])},
                                                                              {'id': 'map', 'label': 'Who contributes to what', 'icon': 'grid-3x3', 'count': len(d['capmap'])}]}]
        return self.page('community', 'Working together', body, drawer, crumbs=['Frameworks', 'Working together'])

    # -- version 1.8: user guide, site map, use and reuse -----------------------------------------
    SECTION_NAMES = [('policy', 'The policy and home'), ('gov', 'Data governance'), ('cat', 'Data cataloguing'), ('dq', 'Data quality'),
                     ('sectors', 'Sector supplements'), ('together', 'Joined up'), ('change', 'Delivery and change'), ('model', 'Capability model'),
                     ('lens', 'Perspectives'), ('community', 'Working together'), ('skills', 'Professions and skills'), ('roles', 'Your role'),
                     ('learning', 'Learning'), ('library', 'Library'), ('knowledge', 'Knowledge'), ('inclusion', 'Inclusion'), ('data', 'Open data'),
                     ('test', 'Help us test'), ('guide', 'Guide and site map'), ('reuse', 'Use and reuse'), ('tooling', 'Tools and interoperability'), ('research', 'Have your say'), ('other', 'About, contact and notices')]

    def p_guide(self):
        d = self.d
        tours = d.get('tours', [])
        tour_rows = [[E(t['title']), E(self.reg.get(t['page'], (t['page'],))[0] if t['page'] in self.reg else t['page']), f'{len(t["steps"])} steps',
                      f'<a href="{"index" if t["page"] == "index" else t["page"]}.html#tour={t["id"]}">{icon("play")}Start this tour</a>'] for t in tours]
        sw = ''.join(f'<li><span class="swatch sw-{k}" aria-hidden="true"></span>{E(v)}</li>' for k, v in self.SECTION_NAMES)
        badges = ''.join(f'<li>{prov(k)} {E(v)}</li>' for k, v in PROV_TEXT.items())
        flags = ''.join(f'<li>{self.flag(k)} {E(v[1])}</li>' for k, v in FLAGS.items())
        tutorials = [
            ('tut-return', 'Prepare your first return', [('dam.html', 'Read what the policy requires and which requirements are "must".'), ('cataloguing.html#method', 'Follow the cataloguing steps to find and designate critical assets.'), ('governance.html#method', 'Confirm a named data owner for each one.'), ('cataloguing.html#metadata', 'Record the core metadata for each asset.'), ('together.html', 'Use the yearly cycle to plan the return and the annual review.')]),
            ('tut-dqap', 'Write a data quality action plan', [('quality.html#method', 'Work through the eight quality steps.'), ('sectors.html#which', 'Check whether any sector supplement adds rules for your asset.'), ('quality.html#escalation', 'Set targets and performance bands, and agree escalation.'), ('learning.html#M08', 'Check your understanding with the DQAP module.')]),
            ('tut-maturity', 'Assess maturity and plan improvements', [('capability-model.html#cm-overview', 'Read the capabilities the policy depends on.'), ('capability-model.html#cm-self', 'Run the self-assessment and download your profile.'), ('capability-model.html#cm-dama', 'Choose your role on the DAMA wheel to see what to improve.'), ('change.html#CH-12', 'Set target levels with dates.')]),
            ('tut-programme', 'Build data asset management into a programme', [('personas.html#persona-prg', 'Follow the programme or project lead route.'), ('change.html#programme-roles', 'Agree data responsibilities with each programme role.'), ('change.html#blueprint', 'Use the programme blueprint as an overlay on your plan.'), ('perspectives.html', 'Check the commercial, cyber and technology lenses with those teams.')]),
            ('tut-tools', 'Specify interoperable tools', [('tooling.html#categories', 'Map the kinds of tool you have or plan, and the DAMA areas they support.'), ('tooling.html#pairs', 'Choose the open standard for each boundary between tools.'), ('tooling.html#barriers', 'Check the commercial barriers in current and planned contracts.'), ('tooling.html#rfi', 'Download the RFI questions and add them to your tender.'), ('change.html#CH-14', 'Record the decision and exit plan in your programme.')]),
            ('tut-reuse', 'Bring the content into your organisation', [('reuse.html', 'Choose an approach: link, embed, data, white-label or AI.'), ('data.html', 'Download the datasets you need or harvest the catalogue.'), ('community.html', 'Agree join-up actions with other professions.')]),
        ]
        tut_html = ''.join(f'<section id="{tid}" class="cr-card"><h3>{icon("route")} {E(t)}</h3><ol class="tut">' + ''.join(f'<li><a href="{u}">{E(x)}</a></li>' for u, x in steps) + '</ol></section>' for tid, t, steps in tutorials)
        keys = [('<kbd>Ctrl</kbd> + <kbd>K</kbd> or <kbd>/</kbd>', 'Open search from any page'), ('<kbd>Esc</kbd>', 'Close search, menus, tooltips or a tour'),
                ('<kbd>Tab</kbd> and <kbd>Shift</kbd> + <kbd>Tab</kbd>', 'Move between links and controls'), ('Arrow keys', 'Move between tabs once a tab is selected'),
                ('<kbd>Enter</kbd> or <kbd>Space</kbd>', 'Open a menu, tab or step, or tick a checkbox')]
        faqs = [('Is this official guidance?', 'No. It is a prototype. Where it repeats GOV.UK guidance, the GOV.UK page is the authority.'),
                ('Is my progress saved?', 'Only in your own browser. Nothing is sent anywhere. Clear it from the home page.'),
                ('What do the coloured edges and badges mean?', 'Colours show which part of the portal you are in. Badges show where each fact comes from; see the legends above.'),
                ('Can I use this content in my organisation?', 'Yes. See Use and reuse for links, embedding, data, your own copy and AI options.'),
                ('How do I give feedback?', 'Use the testing page, the contact form or the "was this page useful?" link at the bottom of every page.')]
        body = self.hero('circle-help', 'Help', 'User guide', 'How the portal is organised, how to find your way around, what the labels mean, guided tours and step-by-step tutorials.',
                         brief=['Take a guided tour on the pages that have one.', 'Follow a tutorial for common jobs.', 'Use the site map to see everything at once.'],
                         meta=[('play', f'{len(tours)} tours'), ('route', f'{len(tutorials)} tutorials'), ('map', 'Site map')])
        body += f'''<h2 id="around">{icon("compass")} Getting around</h2>
<ul class="ticks"><li><strong>Portal sections bar</strong> at the top lists every part of the portal. Playbooks and Frameworks open menus. On small screens, items fold into More sections.</li>
<li><strong>On this page</strong> panel on the left lists the sections of the current page, with counts and "New" flags. The Page contents switch hides or shows it.</li>
<li><strong>Tabs</strong> split long pages. A link to a section opens the right tab.</li>
<li><strong>Breadcrumbs</strong> above each page show where you are.</li>
<li><strong>Site map</strong> shows every page and its sections: <a href="site-map.html">open the site map</a>.</li>
<li><strong>Share this page</strong> copies a link, emails it or shares it in Microsoft Teams.</li></ul>
<h2 id="finding">{icon("search")} Finding things</h2>
<ul class="ticks"><li><strong>Search</strong> covers steps, requirements, capabilities, practices, glossary terms, modules and more.</li>
<li><strong>Filters</strong> above long lists narrow them by capability, role, priority or stage, and show how many items match.</li>
<li><strong>Tooltips</strong> appear when you hover over or move to a dotted term, a pill, a menu item or a source link.</li></ul>
<h2 id="labels">{icon("tag")} What the colours and labels mean</h2>
<h3>Section colours</h3><p>Each part of the portal has its own colour on headings, tiles and borders, so you can tell where you are at a glance. Text always stays in the standard high-contrast colours.</p><ul class="legend-swatches">{sw}</ul>
<h3>Where facts come from</h3><ul>{badges}</ul>
<h3>How the policy states a capability</h3><ul>{flags}</ul>
<h2 id="tours">{icon("play")} Guided tours</h2><p>Tours highlight each part of a page and explain it. Press <kbd>Esc</kbd> to leave a tour at any time.</p>
{table("t-tours", "Guided tours", ["Tour", "Page", "Length", "Start"], tour_rows)}
<h2 id="tutorials">{icon("route")} Tutorials</h2><div class="cr-list two">{tut_html}</div>
<h2 id="keyboard">{icon("a-large-small")} Keyboard shortcuts</h2>{table("t-keys", "Keyboard shortcuts", ["Keys", "What they do"], [[k, E(v)] for k, v in keys])}
<h2 id="faq">{icon("circle-help")} Common questions</h2>{"".join(f'<details class="kc-answer"><summary>{E(q)}</summary><p>{E(a)}</p></details>' for q, a in faqs)}'''
        drawer = [{'label': 'User guide', 'icon': 'circle-help', 'items': [
            {'id': 'around', 'label': 'Getting around', 'icon': 'compass', 'count': 6}, {'id': 'finding', 'label': 'Finding things', 'icon': 'search', 'count': 3},
            {'id': 'labels', 'label': 'Colours and labels', 'icon': 'tag'}, {'id': 'tours', 'label': 'Guided tours', 'icon': 'play', 'count': len(tours), 'new': True},
            {'id': 'tutorials', 'label': 'Tutorials', 'icon': 'route', 'count': len(tutorials), 'new': True}, {'id': 'keyboard', 'label': 'Keyboard shortcuts', 'icon': 'a-large-small', 'count': len(keys)},
            {'id': 'faq', 'label': 'Common questions', 'icon': 'circle-help', 'count': len(faqs)}]}]
        return self.page('guide', 'User guide', body, drawer, crumbs=['User guide'])

    def p_sitemap(self):
        groups = [('Start here', 'house', ['index', 'dam', 'personas', 'learning', 'guide']),
                  ('Playbooks', 'book-open', NAV_GROUPS['Playbooks']),
                  ('Frameworks', 'grid-3x3', NAV_GROUPS['Frameworks']),
                  ('Reference', 'library', ['library', 'knowledge', 'inclusion', 'data', 'reuse']),
                  ('About and help', 'info', ['about', 'research', 'involve', 'test', 'contact', 'status', 'whats-new', 'design', 'notices', 'accessibility'])]
        colours = {'Start here': '#1d70b8', 'Playbooks': '#00703c', 'Frameworks': '#3949ab', 'Reference': '#455a64', 'About and help': '#505a5f'}
        seen, out = set(), ''
        for name, ic, keys in groups:
            items = ''
            for k in keys:
                if k not in self.reg:
                    continue
                seen.add(k)
                title, drawer = self.reg[k]
                secs = [it for g in drawer for it in g['items']][:12]
                sub = ('<ul>' + ''.join(f'<li><a href="{k}.html#{E(it["id"])}">{E(it["label"])}</a></li>' for it in secs) + '</ul>') if secs else ''
                items += f'<li><a href="{"index" if k == "index" else k}.html"><strong>{E(title)}</strong></a><br><span class="hint">{E(PAGE_DESC.get(k, ""))}</span>{sub}</li>'
            out += f'<li class="map-group map-{slug(name)}"><h2>{icon(ic)} {E(name)}</h2><ul>{items}</ul></li>'
        body = self.hero('map', 'Help', 'Site map', 'Every page on the portal, grouped the way the menus are, with the main sections of each page.',
                         meta=[('file-text', f'{len(seen)} pages')])
        body += f'<ul class="map-tree">{out}</ul>'
        return self.page('site-map', 'Site map', body, None, crumbs=['Site map'])

    def p_reuse(self):
        r = self.d['reuse']
        groups = list(dict.fromkeys(a['group'] for a in r['approaches']))
        cards = ''
        for a in r['approaches']:
            cards += (f'<li class="cr-card" id="{a["id"]}" data-item data-grp="{slug(a["group"])}" data-effort="{a["effort"]}"><div class="cr-head">{tile(a["icon"], "sm")}<div><p class="caption">{E(a["id"])} · {E(a["group"])}</p><h3>{E(a["title"])}</h3></div>'
                      f'<span class="effort e-{a["effort"]}">{E(a["effort"].capitalize())} effort</span></div><p>{E(a["what"])}</p>'
                      f'<h4>{icon("list-checks")} How</h4><ol>{"".join(f"<li>{E(x)}</li>" for x in a["how"])}</ol>'
                      f'<p><strong>Choose this when:</strong> {E(a["when"])}</p><h4>{icon("triangle-alert")} Watch out for</h4>{ul(a["cautions"])}</li>')
        opts = ''.join(f'<option value="{slug(g)}">{E(g)}</option>' for g in groups)
        endpoints = [('data/catalogue.jsonld', 'DCAT catalogue of every dataset (JSON-LD)'), ('data/catalogue.ttl', 'The same catalogue in Turtle'), ('data/playbooks.json', 'All content in one file'),
                     ('llms.txt', 'Short guide for AI tools'), ('llms-full.txt', 'Full text for AI tools'), ('sitemap.xml', 'Every page address'), ('feed.xml', 'Releases as an Atom feed'), ('data/ontology.ttl', 'Ontology of the portal (OWL, Turtle)'), ('data/lineage.ttl', 'Lineage from sources to requirements, pages and checks (PROV-O, Turtle)')]
        ep = [[f'<a href="{u}"><code>{E(u)}</code></a>', E(t)] for u, t in endpoints]
        mcp = '''{
  "mcpServers": {
    "dam-playbooks": {
      "command": "python3",
      "args": ["integrations/mcp/server.py"],
      "env": {"DAM_PLAYBOOKS_FILE": "/path/to/playbooks.json"}
    }
  }
}'''
        tools = [('search_portal', 'Search steps, requirements, capabilities, practices, sector supplements and glossary terms.'), ('get_capability', 'Get one capability from the capability model, with its signposts.'),
                 ('get_requirement', 'Get one DAM Policy requirement with its source and strength.'), ('get_practice', 'Get one delivery and change practice with its actions.'),
                 ('list_sector_rules', 'List the quality rules for a sector supplement.')]
        body = self.hero('share-2', 'Reference', 'Use and reuse this content', E(r['intro']),
                         brief=['Ten approaches, from a link on your intranet to your own branded copy.', 'AI options: an assistant that cites the portal, and a reference MCP server.', 'Each approach says what it takes and what to watch out for.'],
                         meta=[('share-2', f'{len(r["approaches"])} approaches'), ('network', 'MCP server'), ('scale', 'Open licences')])
        body += f'''<h2 id="approaches">{icon("layers")} Approaches</h2>
<div class="filters" data-filter="reuse-list" role="group" aria-label="Filter approaches"><div><label for="r-g">Kind</label><select id="r-g" name="grp"><option value="">All</option>{opts}</select></div>
<div><label for="r-e">Effort</label><select id="r-e" name="effort"><option value="">All</option><option value="low">Low</option><option value="medium">Medium</option></select></div><p class="count-out" aria-live="polite"></p></div>
<ul class="approach-grid" id="reuse-list">{cards}</ul>
<h2 id="embed">{icon("code-xml")} Embed a requirement or capability</h2>
<p>Show one DAM Policy requirement or one capability on your intranet or in a document that accepts web content. Each has its own small page, with a link back here. Copy this code and change the identifier, for example <code>DAM-R01</code> or <code>CR-01</code>:</p>
<pre class="code" id="embed-code" tabindex="0">{self.site_addr(E('<iframe src="{site}embed/DAM-R01.html" title="DAM Policy requirement DAM-R01" width="100%" height="220" loading="lazy"></iframe>'))}</pre>
<p><button type="button" class="btn secondary" data-copy-target="embed-code" hidden>{icon("link")}Copy code</button> <span class="copy-status" aria-live="polite"></span> Preview: <a href="embed/DAM-R01.html">DAM-R01</a> · <a href="embed/CR-01.html">CR-01</a>. Embedded pages do not change when your copy is cached; they always show the latest release.</p>
<h2 id="offline">{icon("download")} Offline copy</h2>
<p>If your network blocks this site, download the <a href="dam-playbooks-offline.zip">whole portal as a zip file</a>, unzip it, and open <code>index.html</code> in your browser. Search, filters and progress work offline. The copy is for this release only: check <a href="whats-new.html">What's new</a> for updates.</p>
<h2 id="endpoints">{icon("database")} Addresses for tools and AI</h2>{table("t-endpoints", "Machine-readable addresses", ["Address", "What it is"], ep)}
<h2 id="ai">{icon("brain")} AI assistants and search</h2>
<p>The built-in search finds pages, steps and terms by their words. An AI assistant can answer questions in plain language, combining several pages. This portal does not run its own chatbot: there is no server, and nothing you type is sent anywhere. Instead it publishes its content in forms that assistants your organisation already approves can use, with the page each answer comes from.</p>
<ul class="ticks"><li><strong>llms.txt</strong> is a short, structured guide to the portal for AI tools, following a common convention; <strong>llms-full.txt</strong> holds the full text.</li>
<li><strong>Knowledge sources</strong>: add the site address or <code>data/playbooks.json</code> to an assistant builder, such as Microsoft Copilot Studio.</li>
<li><strong>Always check</strong> an answer against the page it cites, and against GOV.UK, which remains the authority.</li></ul>
<h2 id="mcp">{icon("network")} Model Context Protocol (MCP) server</h2>
<p>A reference server in the repository, <code>integrations/mcp/server.py</code>, lets an MCP-compatible assistant use the portal as a set of tools. It uses only the Python standard library, reads the published content, and returns links to the pages it draws on. It is for testing and adaptation, not a supported service.</p>
{table("t-mcp-tools", "Tools the MCP server provides", ["Tool", "What it does"], [[f"<code>{E(a)}</code>", E(b)] for a, b in tools])}
<p>Download the <a href="data/playbooks.json">full content file</a>, or set <code>DAM_PLAYBOOKS_URL</code> to its full address to read the live copy. Example configuration for an assistant that reads MCP servers from a JSON file:</p><pre class="code" tabindex="0" aria-label="Example MCP configuration"><code>{E(mcp)}</code></pre>
<div class="notice-box">{icon("info")}<p>Whatever route you choose, keep the prototype status, the attribution statement and the licences with the content, and agree who in your organisation keeps your copy up to date.</p></div>'''
        drawer = [{'label': 'Use and reuse', 'icon': 'share-2', 'items': [
            {'id': 'approaches', 'label': 'Approaches', 'icon': 'layers', 'count': len(r['approaches'])},
            {'id': 'embed', 'label': 'Embed a requirement', 'icon': 'code-xml', 'new': True}, {'id': 'offline', 'label': 'Offline copy', 'icon': 'download', 'new': True},
            {'id': 'endpoints', 'label': 'Addresses for tools', 'icon': 'database', 'count': len(endpoints)},
            {'id': 'ai', 'label': 'AI assistants', 'icon': 'brain'}, {'id': 'mcp', 'label': 'MCP server', 'icon': 'network', 'count': len(tools)}]}]
        return self.page('reuse', 'Use and reuse', body, drawer, crumbs=['Use and reuse'])

    def write_llms(self):
        m, base, d = self.m, self.m['site_url'], self.d
        lines = [f'# {m["title"]}', '', f'> {m["subtitle"]}. A prototype, not official GOV.UK guidance; where it repeats GOV.UK, the GOV.UK page is the authority.', '',
                 'Content is under the Open Government Licence v3.0. Cite the page each answer comes from.', '', '## Pages', '']
        for k, (title, _) in self.reg.items():
            if k == '404':
                continue
            lines.append(f'- [{title}]({base}{"" if k == "index" else k + ".html"}): {re.sub(r"<[^>]+>", "", PAGE_DESC.get(k, m["subtitle"]))}')
        lines += ['', '## Data', '', f'- [Open data catalogue (DCAT, JSON-LD)]({base}data/catalogue.jsonld)', f'- [Full content (JSON)]({base}data/playbooks.json)', f'- [Full text for AI tools]({base}llms-full.txt)', '']
        (self.out / 'llms.txt').write_text('\n'.join(lines), encoding='utf-8')
        full = ['# ' + m['title'] + ' (full text)', '', f'Version {m["version"]}, as of {m["as_of"]}. {m["status"]}', '']
        full += ['## DAM Policy requirements', ''] + [f'- {r["id"]} ({r["strength"]}): {r["text"]} [{base}dam.html#{r["id"]}]' for r in d['requirements']]
        for c in d['capabilities']:
            full += ['', f'## {c["name"]}', '', c['purpose'], ''] + [f'{st["n"]}. {st["name"]}: {st["goal"]} ' + ' '.join(st['steps']) + f' [{base}{CAP_PAGE[c["id"]]}.html#{c["id"]}-{st["id"]}]' for st in c['stages']]
        full += ['', '## Capability model', ''] + [f'- {c["id"]} {c["name"]} ({FLAGS[c["flag"]][0]}): {c["note"]} [{base}capability-model.html#{c["id"]}]' for c in d.get('capmap', [])]
        full += ['', '## Delivery and change practices', ''] + [f'- {x["id"]} {x["title"]}: {x["why"]} Actions: ' + ' '.join(x['actions']) + f' [{base}change.html#{x["id"]}]' for x in d.get('change', {}).get('items', [])]
        full += ['', '## Sector supplements', ''] + [f'- {x["title"]}: {x["summary"]} [{base}sectors.html#{x["id"]}]' for x in d.get('supplements', [])]
        full += ['', '## Glossary', ''] + [f'- {c["term"]}: {c["def"]}' for c in d['concepts']]
        (self.out / 'llms-full.txt').write_text('\n'.join(full) + '\n', encoding='utf-8')

    # -- version 1.8: tools and interoperability ------------------------------------------------
    MATURITY_TEXT = {'Established': 'Open standards exist and are widely implemented', 'Emerging': 'Open standards exist but support varies between products',
                     'Vendor-specific': 'No common open standard; each product does it its own way'}

    def p_tooling(self):
        T, dama = self.d['tooling'], {a['id']: a for a in self.d['dama']['areas']}
        pats = {p['id']: p for p in T['patterns']}
        std_of = lambda ids: '; '.join(self.rb_link(r) for r in ids)
        cards = ''
        for c in T['categories']:
            areas = ' '.join(f'<a class="pill" href="capability-model.html#{a.lower()}" data-tip="DAMA knowledge area">{E(dama[a]["name"])}</a>' for a in c['dama'])
            pp = ' '.join(f'<a class="pill" href="#{p}" data-tip="{E(pats[p]["how"])}">{E(pats[p]["name"])}</a>' for p in c['patterns'])
            cards += (f'<li class="cr-card" id="{c["id"]}" data-item data-cap="{" ".join(c["caps"])}"><div class="cr-head">{tile(c["icon"], "sm")}<div><p class="caption">{E(c["id"])}</p><h3>{E(c["name"])}</h3></div></div>'
                      f'<p>{E(c["what"])}{prov("O")}</p><p><strong>DAMA area:</strong> {areas}</p>'
                      f'<p><strong>Open standards:</strong> {std_of(c["standards"])}</p><p><strong>Integration patterns:</strong> {pp}</p>'
                      f'<p class="ask">{icon("circle-help")}<strong>Ask:</strong> {E(c["ask"])}</p></li>')
        filt = ('<div class="filters" data-filter="tool-list" role="group" aria-label="Filter tool categories"><div><label for="tl-cap">Capability</label><select id="tl-cap" name="cap"><option value="">All</option>'
                '<option value="gov">Data governance</option><option value="cat">Data cataloguing</option><option value="dq">Data quality</option></select></div><p class="count-out" aria-live="polite"></p></div>')
        overview = (f'<p class="lede">{E(T["intro"])}</p><h2 id="principles">{icon("compass")} Five principles</h2>'
                    + '<ol class="principles">' + ''.join(f'<li>{E(x)}</li>' for x in T['principles']) + f'</ol><p class="hint">This portal\'s synthesis{prov("O")} of {self.rb_link("RB-OSP")}, {self.rb_link("RB-TCOP11")} and {self.rb_link("RB-LOCKIN")}.</p>'
                    + f'<h2 id="categories">{icon("layers")} Kinds of tool</h2><p>Each kind of tool supports one or more DAMA knowledge areas. Products often cover several kinds; judge each kind separately.</p>{filt}<ul class="approach-grid" id="tool-list">{cards}</ul>')
        stds = []
        seen = []
        for c in T['categories']:
            for r in c['standards']:
                if r not in seen:
                    seen.append(r)
        for r in seen:
            used = ', '.join(c['name'] for c in T['categories'] if r in c['standards'])
            stds.append([self.rb_link(r), E(self.rb[r]['publisher']), E(used)])
        prow = [[f'<span id="{p["id"]}"><strong>{E(p["name"])}</strong></span>', E(p['how']), E(p['when']), f'<span class="effort e-{"low" if p["risk"] == "low" else "medium"}">{E(p["risk"].capitalize())}</span>', E(p['watch'])] for p in T['patterns']]
        standards = (f'<h2 id="open-standards">{icon("scale")} Open standards at the boundaries</h2><p>Standards that let tools exchange catalogue records, vocabularies, quality results, lineage, contracts and API descriptions. '
                     f'For data shared within government and published data, also follow {self.rb_link("RB-METASTD")} and the {self.src_link("SRC-MEM")}.</p>'
                     + table('t-tool-std', 'Open standards for tool interoperability', ['Standard', 'Maintained by', 'Used between'], stds)
                     + f'<h2 id="patterns">{icon("workflow")} Integration patterns</h2><p>How tools connect, and the lock-in risk each pattern carries{prov("O")}.</p>'
                     + table('t-tool-pat', 'Integration patterns', ['Pattern', 'How it works', 'Use it for', 'Lock-in risk', 'Watch out for'], prow))
        mrow = [[f'<strong>{E(x["between"])}</strong>', E(x['flows']), E(x['open']), f'<span class="mat mat-{slug(x["maturity"])}" data-tip="{E(self.MATURITY_TEXT[x["maturity"]])}">{E(x["maturity"])}</span>', E(x['fallback']), E(x['watch'])] for x in T['pairs']]
        counts = {k: sum(1 for x in T['pairs'] if x['maturity'] == k) for k in self.MATURITY_TEXT}
        matrix = (f'<h2 id="pairs">{icon("network")} Which tools need to work together</h2><p>The common pairings, what flows between them, the open route if there is one, and what to do where there is not{prov("O")}. '
                  f'Of {len(T["pairs"])} pairings, {counts["Established"]} have established open standards, {counts["Emerging"]} have emerging ones and {counts["Vendor-specific"]} depend on each product.</p>'
                  + table('t-tool-pairs', 'Interoperability between kinds of tool', ['Between', 'What flows', 'Open route', 'Maturity', 'If there is no open route', 'Watch out for'], mrow)
                  + '<ul class="legend-swatches">' + ''.join(f'<li><span class="mat mat-{slug(k)}">{E(k)}</span> {E(v)}</li>' for k, v in self.MATURITY_TEXT.items()) + '</ul>'
                  + '<p class="hint">Whether two named products interoperate changes with each release. Ask suppliers to show it with your data, and ask other organisations what they found.</p>')
        B = T['bundles']
        brow = [[f'<strong>{E(b["name"])}</strong>', E(b['detail']), E(b['mitigate'])] for b in T['barriers']]
        bundles = (f'<h2 id="bundles">{icon("package")} One supplier or several</h2><p>A bundled suite from one supplier and a set of tools from several suppliers can both work. What matters is whether you can change one part without changing the rest{prov("O")}.</p>'
                   f'<div class="cols"><div class="panel"><h3>{icon("circle-check")} What a bundle can offer</h3>{ul(B["pros"], cls="ticks")}</div>'
                   f'<div class="panel"><h3>{icon("triangle-alert")} Where a bundle can lock you in</h3>{ul(B["cons"])}</div></div>'
                   f'<h3>{icon("circle-help")} Three tests for any bundle</h3>{ul(B["tests"])}'
                   f'<h2 id="barriers">{icon("scale")} Commercial barriers and how to avoid them</h2>'
                   f'<p>Barriers that arise with catalogue, data quality and bundled tools{prov("O")}. The Competition and Markets Authority\'s {self.rb_link("RB-CMACLOUD")} found that data egress fees and barriers to interoperability restrict switching and multi-cloud, and raised concerns about software licensing in cloud; see the {self.rb_link("RB-CMAPKG")}.</p>'
                   + table('t-tool-barriers', 'Commercial barriers', ['Barrier', 'What happens', 'How to avoid it'], brow)
                   + f'<div class="notice-box">{icon("info")}<p>For services supplied into the European Union, the {self.rb_link("RB-EUDA")} phases out switching charges, including egress charges for a switch. It is not UK law, but suppliers may offer the same terms to UK buyers: ask.</p></div>')
        qhtml, qn = '', 0
        for g in T['questions']:
            items = ''
            for q in g['items']:
                qn += 1
                items += f'<li id="RFI-{qn:02d}"><span class="caption">RFI-{qn:02d}</span> {E(q)}</li>'
            qhtml += f'<section class="cr-card"><h3>{icon("list-checks")} {E(g["group"])}</h3><ol class="rfi">{items}</ol></section>'
        steps = ''.join(f'<li><strong>{E(s["name"])}.</strong> {E(s["text"])}</li>' for s in T['steps'])
        procure = (f'<h2 id="steps">{icon("route")} Six steps to buy without lock-in</h2><ol class="tut">{steps}</ol>'
                   f'<p>These steps support {self.rb_link("RB-TCOP11")} and {self.rb_link("RB-TCOP4")}, and the delivery and change practices on <a href="change.html#CH-06">building DAM into contracts</a>, <a href="change.html#CH-14">designing out lock-in</a> and <a href="change.html#CH-16">buying routes and contract terms</a>.</p>'
                   f'<h2 id="rfi">{icon("circle-help")} Questions for a request for information or tender</h2><p>{qn} questions, grouped. Use them as written or adapt them{prov("O")}. '
                   f'Download them as <a href="data/interoperability-questions.csv">CSV</a> to load into your own RFI template. They focus on what the DAM Policy needs from a tool; for product-level questions, a lock-in checker and a test script, see <a href="#related-tooling">Related elsewhere</a> at the end of this page.</p><div class="cr-list two">{qhtml}</div>')
        res_groups = [('Government policy and guidance', ['RB-OSP', 'RB-TCOP4', 'RB-TCOP11', 'RB-PPN0715', 'RB-LOCKIN', 'RB-API', 'RB-REFARCH', 'RB-DDATPB', 'RB-SOURCING']),
                      ('Data standards for government', ['RB-METASTD', 'RB-DSACAT', 'RB-DSA']),
                      ('Open standards and reference projects', ['RB-DCAT', 'RB-DQV', 'RB-SKOS', 'RB-PROVO', 'RB-CSVW', 'RB-OLINEAGE', 'RB-ODCS', 'RB-ODPS', 'RB-OAS', 'RB-EGERIA', 'RB-MCPSPEC']),
                      ('Buying routes and market evidence', ['RB-GCLOUD', 'RB-GCSEARCH', 'RB-FTS', 'RB-PA23G', 'RB-MSC', 'RB-CMACLOUD', 'RB-CMAPKG', 'RB-EUDA'])]
        res = f'<h2 id="resources">{icon("library")} Where to find out more</h2><p>Each link is checked automatically every week.</p>'
        for g, ids in res_groups:
            res += f'<h3>{E(g)}</h3><ul>' + ''.join(f'<li>{self.rb_link(r)}</li>' for r in ids) + '</ul>'
        res += f'<p>The {self.src_link("SRC-MEM")} is the government model for recording critical data assets; ask suppliers to show they support it.</p>'
        tabs = [('tl-overview', 'Overview', overview), ('tl-standards', 'Standards and patterns', standards), ('tl-pairs', 'Working together', matrix),
                ('tl-bundles', 'Bundles and commercial', bundles), ('tl-procure', 'Procurement', procure), ('tl-resources', 'Resources', res)]
        hero = self.hero('plug', 'Frameworks', 'Tools and interoperability', 'How catalogue, data quality, lineage, master data and governance tools can work together, which open standards connect them, and how to buy them without lock-in.',
                         brief=[f'{len(T["categories"])} kinds of tool, mapped to DAMA knowledge areas, with the open standards that connect them.', f'{len(T["pairs"])} common pairings rated for how mature their open routes are.', f'{qn} questions for a request for information or tender, as CSV.'],
                         meta=[('layers', f'{len(T["categories"])} kinds of tool'), ('scale', f'{len(seen)} open standards'), ('circle-help', f'{qn} RFI questions')])
        drawer = [{'label': 'Tools and interoperability', 'icon': 'plug', 'items': [
            {'id': 'principles', 'label': 'Five principles', 'icon': 'compass', 'count': len(T['principles']), 'new': True},
            {'id': 'categories', 'label': 'Kinds of tool', 'icon': 'layers', 'count': len(T['categories']), 'new': True},
            {'id': 'open-standards', 'label': 'Open standards', 'icon': 'scale', 'count': len(seen)},
            {'id': 'patterns', 'label': 'Integration patterns', 'icon': 'workflow', 'count': len(T['patterns'])},
            {'id': 'pairs', 'label': 'Which tools work together', 'icon': 'network', 'count': len(T['pairs']), 'new': True},
            {'id': 'bundles', 'label': 'One supplier or several', 'icon': 'package'},
            {'id': 'barriers', 'label': 'Commercial barriers', 'icon': 'scale', 'count': len(T['barriers'])},
            {'id': 'steps', 'label': 'Six steps to buy', 'icon': 'route', 'count': len(T['steps'])},
            {'id': 'rfi', 'label': 'RFI questions', 'icon': 'circle-help', 'count': qn, 'new': True},
            {'id': 'resources', 'label': 'Where to find out more', 'icon': 'library'}]}]
        return self.page('tooling', 'Tools and interoperability', hero + self.tabbed(tabs, 'Tools and interoperability'), drawer, crumbs=['Frameworks', 'Tools and interoperability'])

    # -- version 1.9: have your say (research, roadmap, backlog and ideas, in the open) -------------------
    def research_items(self):
        """Backlog items with their score, band, votes and linked idea, computed once for the page and the data files."""
        R = self.d['research']
        ideas = {i['n']: i for i in self.ideas.get('ideas', [])}
        out = []
        for x in R['backlog']:
            score, band, a, v = research_score(x, R, ideas)
            out.append(dict(x, score=score, band=band, scored=a, votes=v, idea_url=ideas.get(x.get('idea'), {}).get('url', '')))
        return out

    def p_research(self):
        d, m, R = self.d, self.m, self.d['research']
        gh = f'https://github.com/{m["repo"]}'
        items = self.research_items()
        crit = {c['id']: c for c in R['criteria']}
        strat = {s['id']: s for s in R['strategies']}
        bandname = {b: lbl for _, b, lbl in R['bands']}
        decided = {}
        for x in R['decisions']:
            decided.setdefault(x['item'], []).append(x)
        signup = R['signup']['url'] or self.ms_form_url()

        def strat_pills(ids):
            return ' '.join(f'<a class="pill" href="#strategy-{s}" data-tip="{E(strat[s]["name"])}">{E(strat[s]["name"].split(" (")[0])}</a>' for s in ids)

        def card(x):
            dec = ' '.join(f'<a href="#decision-{x["id"]}">decided differently</a>' for _ in decided.get(x['id'], [])[:1]) if x['band'] != x['status'] and x['status'] in ('now', 'next', 'later') else ''
            idea = f' <a href="{E(x["idea_url"])}" rel="noopener">{icon("thumbs-up")}{x["votes"]} votes</a>' if x['idea_url'] else ''
            return (f'<li class="cr-card rm-card" id="{x["id"]}" data-item data-type="{x["type"]}" data-status="{x["status"]}"><p class="caption">{E(x["id"])} · {E(RESEARCH_TYPES[x["type"]])}</p>'
                    f'<h4>{E(x["title"])}</h4><p class="hint">{E(x["story"])}</p>'
                    f'<p><span class="score" data-tip="Score out of 100 from the six criteria under How we prioritise">Score {x["score"]}</span> {E(bandname[x["band"]])}{" · " + dec if dec else ""}{idea}</p>'
                    f'<p>{strat_pills(x["strategy"])}</p></li>')

        # Take part --------------------------------------------------------------
        meth = ''.join(f'<li class="cr-card" id="{x["id"]}"><div class="cr-head">{tile(x["icon"], "sm")}<div><p class="caption">{E(x["time"])} · {E(x["how"])}</p><h3>{E(x["name"])}</h3></div></div><p>{E(x["what"])}</p></li>' for x in R['methods'])
        rnd_rows = [[f'<strong>{E(r["id"])}</strong>', E(r['name']), E(r['goal']), ', '.join(E(next(mm['name'] for mm in R['methods'] if mm['id'] == i)) for i in r['methods']),
                     f'<span class="rm-badge rm-{r["status"]}">{E(RESEARCH_STATUS[r["status"]])}</span>', ', '.join(E(h) for h in r['answers']) or 'None yet'] for r in R['rounds']]
        if signup:
            su = (f'<p><a class="btn" href="{E(signup)}" rel="noopener">{icon("clipboard-list")}Sign up to take part</a></p>'
                  + ('' if R['signup']['url'] else f'<p class="hint">{E(R["signup"]["note"])}</p>'))
        else:
            su = f'<p>{E(R["signup"]["note"])} Or <a href="contact.html">use the contact form</a>.</p>'
        url = m['site_url'] + 'research.html'
        enc = urllib.parse.quote
        mail = (f'mailto:?subject={enc("Have your say on the DAM capability playbooks")}&amp;body='
                + enc(f'The Data Asset Management (DAM) capability playbooks are a prototype portal for putting the DAM Policy into practice. '
                      f'The team wants people in our kind of role to try it, take part in research and suggest ideas.\n\nFind out more and sign up: {url}\n'))
        take = (f'<p class="lede">{E(R["intro"])}</p>'
                f'<h2 id="why">{icon("lightbulb")} Why take part</h2>{ul(R["why_take_part"], cls="ticks")}'
                f'<p class="notice-box">{icon("hand-helping")}<span>Want to do more? <a href="involve.html">Get involved</a>: improve the content, champion the portal in your team, and earn badges.</span></p>'
                f'<h2 id="ways">{icon("list-checks")} Ways to take part</h2><p>Choose as many or as few as suit you. Every session is online unless you ask otherwise, and you can stop at any time.</p><ul class="approach-grid">{meth}</ul>'
                f'<h2 id="who">{icon("users-round")} Who we want to hear from</h2><p>{E(R["who"])} See <a href="personas.html">Your role</a> for the roles.</p>'
                f'<h2 id="sign-up">{icon("clipboard-list")} Sign up</h2>{su}<p>The form asks for:</p>{ul(R["signup"]["collects"])}'
                f'<p>If you use assistive technology, tell us what you use and anything we should arrange. We follow the Service Manual on {self.rb_link("RB-SMDISABLED")}.</p>'
                f'<h2 id="privacy">{icon("lock-keyhole")} How we look after you and your information</h2>{ul(R["privacy"])}'
                f'<p class="hint">This follows the Service Manual on {self.rb_link("RB-SMCONSENT")} and {self.rb_link("RB-SMPRIVACY")}.</p>'
                f'<h2 id="rounds">{icon("route")} Research rounds</h2><p>Each round answers questions from the research plan on <a href="design.html">Service design</a>, and tests its hypotheses.</p>'
                + table('t-rounds', 'Research rounds', ['Round', 'Name', 'What it will find out', 'Methods', 'When', 'Hypotheses tested'], rnd_rows)
                + f'<h2 id="introduce">{icon("megaphone")} Introduce the portal to your team</h2>'
                f'<p>Share this page with colleagues who manage, describe or use data assets. Teams can take part together in a review panel.</p>'
                f'<p><a class="btn secondary" href="{mail}">{icon("send")}Email a link to your team</a></p>')

        # Roadmap --------------------------------------------------------------
        cols = ''
        for st, lede in (('now', 'Being worked on, or next to start.'), ('next', 'Planned once Now has room.'), ('later', 'Wanted, but not yet planned.')):
            these = sorted((x for x in items if x['status'] == st), key=lambda x: -x['score'])
            cols += (f'<section class="rm-col rm-{st}" aria-labelledby="rm-h-{st}"><h3 id="rm-h-{st}">{icon({"now": "flag", "next": "calendar-clock", "later": "clock"}[st])} {RESEARCH_STATUS[st]} <span class="count">{len(these)}</span></h3>'
                     f'<p class="hint">{lede}</p><ul class="cr-list">{"".join(card(x) for x in these)}</ul></section>')
        done = ''.join(f'<li><strong>{E(x["id"])}</strong> {E(x["title"])} <span class="hint">released in {E(x["release"])}</span></li>' for x in items if x['status'] == 'done')
        out_ = ''.join(f'<li id="{x["id"]}"><strong>{E(x["id"])}</strong> {E(x["title"])}. {E(x["reason"])}</li>' for x in items if x['status'] == 'out')
        nnow = sum(1 for x in items if x['status'] == 'now')
        roadmap = (f'<h2 id="roadmap">{icon("kanban")} Roadmap</h2><p>What is being worked on now, next and later, modelled on the {self.rb_link("RB-DGUROADMAP")}. '
                   f'Now holds at most {R["wip_limit"]} items at a time, so work gets finished; it holds {nnow}. Reviewed at least every 3 months and after each research round.</p>'
                   f'<div class="rm-board">{cols}</div>'
                   f'<h3 id="done">{icon("circle-check")} Done</h3><ul class="ticks">{done}</ul><p>Every change is on <a href="whats-new.html">What\'s new</a>.</p>'
                   f'<h3 id="out-of-scope">{icon("ban")} Out of scope</h3><ul>{out_}</ul>')

        # Backlog --------------------------------------------------------------
        rows, attrs = [], []
        for x in sorted(items, key=lambda x: (list(RESEARCH_STATUS).index(x['status']), -x['score'])):
            src = f'<a href="about.html#{x["source"]}">{E(x["source"])}</a>' if re.fullmatch(r'OR-\d{2}', x['source']) else E(x['source'])
            rows.append([f'<strong id="bl-{x["id"]}">{E(x["id"])}</strong>', f'<strong>{E(x["title"])}</strong><br>{E(x["story"])}', E(RESEARCH_TYPES[x['type']]), src,
                         f'<span class="rm-badge rm-{x["status"]}">{E(RESEARCH_STATUS[x["status"]])}</span>', str(x['score']), strat_pills(x['strategy'])])
            attrs.append(f' data-item data-status="{x["status"]}" data-type="{x["type"]}"')
        sopt = ''.join(f'<option value="{k}">{E(v)}</option>' for k, v in RESEARCH_STATUS.items())
        topt = ''.join(f'<option value="{k}">{E(v)}</option>' for k, v in RESEARCH_TYPES.items())
        backlog = (f'<h2 id="backlog">{icon("list-ordered")} Backlog</h2><p>Every item is written as a user story, with where it came from: research, the <a href="about.html#limitations">open register</a>, an idea, or a review. '
                   f'Download it as <a href="data/backlog.csv">CSV</a> or <a href="data/backlog.json">JSON</a>.</p>'
                   f'<div class="filters" data-filter="bl-body" role="group" aria-label="Filter the backlog"><div><label for="bl-status">Status</label><select id="bl-status" name="status"><option value="">All</option>{sopt}</select></div>'
                   f'<div><label for="bl-type">Type</label><select id="bl-type" name="type"><option value="">All</option>{topt}</select></div><p class="count-out" aria-live="polite"></p></div>'
                   + table('t-backlog', 'Product backlog', ['ID', 'Story', 'Type', 'Came from', 'Status', 'Score', 'Fits'], rows, row_attrs=attrs, tbody_id='bl-body'))

        # Ideas ----------------------------------------------------------------
        I = R['ideas']
        on_bl = {x.get('idea'): x['id'] for x in items if x.get('idea')}
        if not self.ideas.get('available'):
            live = f'<p>The list of ideas could not be read when this page was built. <a href="{gh}/{I["list_url"]}">See every idea on GitHub</a>.</p>'
        elif not self.ideas['ideas']:
            live = f'<p>No ideas yet. <a href="{gh}/{I["new_url"]}">Be the first to suggest one</a>.</p>'
        else:
            lis = ''.join(f'<li><a href="{E(i["url"])}" rel="noopener">{E(i["title"])}</a> <span class="hint">{i["votes"]} votes · {i["comments"]} comments'
                          f'{" · on the backlog as " + on_bl[i["n"]] if i["n"] in on_bl else ""}{" · closed" if i["closed"] else ""}</span></li>' for i in self.ideas['ideas'][:15])
            live = f'<p>The most voted ideas when this page was built, on {E(self.ideas["as_of"])}.</p><ol class="ideas">{lis}</ol><p><a href="{gh}/{I["list_url"]}">See every idea on GitHub</a>.</p>'
        vb = '; '.join(f'{t} or more votes scores {b}' for t, b in R['vote_bands'])
        ideas = (f'<h2 id="ideas">{icon("lightbulb")} Ideas and voting</h2><p>Suggest a feature, a page, a fix or a whole new idea. Vote for the ideas you want most. Ideas are public, so everyone can see them and how each one is handled.</p>'
                 f'<p><a class="btn" href="{gh}/{I["new_url"]}">{icon("lightbulb")}Suggest an idea</a> <a class="btn secondary" href="{gh}/{I["list_url"]}">{icon("thumbs-up")}Vote for ideas</a></p>'
                 f'<div class="notice-box">{icon("info")}<p>{E(I["note"])} You need a free GitHub account. If you do not have one, use the {"private feedback form" if self.ms_form_url() else "contact form"} and we will add your idea for you, without your name.</p></div>'
                 f'<h3 id="top-ideas">{icon("trophy")} Most voted ideas</h3>{live}'
                 f'<h3 id="idea-journey">{icon("route")} What happens to an idea</h3><ol class="tut">'
                 f'<li><strong>Suggested.</strong> Anyone can suggest an idea and anyone can vote.</li>'
                 f'<li><strong>Triaged within 2 weeks.</strong> We reply, link related ideas and ask questions if we need to.</li>'
                 f'<li><strong>Assessed.</strong> If it fits the portal\'s purpose, it becomes a backlog item with a user story and is scored against the six criteria. Votes count towards user demand: {vb}.</li>'
                 f'<li><strong>Placed.</strong> Its score suggests Now, Next or Later. Where we decide differently, we say why in the decisions log.</li>'
                 f'<li><strong>Closed with a reason.</strong> Done ideas link to the release. Ideas we will not do are marked out of scope, with the reason.</li></ol>')

        # How we prioritise ------------------------------------------------------
        crow = [[f'<strong>{tile(c["icon"], "sm")} {E(c["name"])}</strong>', f'{c["weight"]}%', E(c['ask']),
                 '<ol class="scale" start="0">' + ''.join(f'<li>{E(s)}</li>' for s in c['scale']) + '</ol>'] for c in R['criteria']]
        brow = [[f'{mn} or more' if mn else 'Under 50', E(lbl)] for mn, _, lbl in R['bands']]
        slis = ''
        for s in R['strategies']:
            link = (self.rb_link(s['ref']) if s['ref'] in self.rb else self.src_link(s['ref'])) if s['ref'] else f'{E(s["name"])} <span class="tag">Not yet published: unconfirmed</span>'
            slis += f'<li id="strategy-{s["id"]}">{link}</li>'
        ex = next(x for x in items if x['id'] == 'BL-12')
        exrow = ' + '.join(f'{crit[k]["weight"]} × {v}/3' for k, v in ex['scored'].items())
        prio = (f'<h2 id="prioritise">{icon("scale")} How we prioritise</h2><p>Votes tell us what people want. They are one input, not the decision. Each backlog item is also assessed by the service team for policy, strategy, feasibility, capacity and inclusion{prov("O")}.</p>'
                + table('t-criteria', 'Prioritisation criteria', ['Criterion', 'Weight', 'Question', 'Scores from 0 to 3'], crow)
                + f'<h3 id="score">{icon("chart-column")} The score</h3><p>Score = the sum, for each criterion, of its weight × its score ÷ 3. The result is out of 100.</p>'
                f'<p class="hint">Example, {E(ex["id"])} {E(ex["title"])}: {exrow} = {ex["score"]}.</p>'
                + table('t-bands', 'What a score suggests', ['Score', 'Suggests'], brow)
                + f'<p>A score suggests a place on the roadmap; it does not decide it. When we place an item differently, for example because it depends on something else, the reason is in the decisions log below. Now holds at most {R["wip_limit"]} items.</p>'
                f'<h3 id="strategies">{icon("compass")} Government strategies we align to</h3><p>An item scores higher on government strategy when it helps deliver one of these.</p><ul>{slis}</ul>'
                f'<p class="hint">The {E(strat["sdr"]["name"])}. When it is published, it will be added and every item reassessed against it.</p>'
                f'<h3 id="decisions">{icon("history")} Decisions log</h3>'
                + table('t-decisions', 'Decisions log', ['Date', 'Item', 'Decision', 'Why'],
                        [[E(x['date']), f'<a href="#bl-{x["item"]}" id="decision-{x["item"]}">{E(x["item"])}</a>' if R['decisions'].index(x) == next(i for i, y in enumerate(R['decisions']) if y['item'] == x['item']) else f'<a href="#bl-{x["item"]}">{E(x["item"])}</a>', E(x['decision']), E(x['why'])] for x in R['decisions']]))

        # What we have learned -----------------------------------------------------
        if R['learned']:
            lr = ''.join(f'<li><strong>{E(x["round"])}:</strong> {E(x["finding"])} <span class="hint">Changed: {E(x["change"])}</span></li>' for x in R['learned'])
            learned = f'<h2 id="learned">{icon("book-open")} What we have learned</h2><ul>{lr}</ul>'
        else:
            learned = (f'<h2 id="learned">{icon("book-open")} What we have learned</h2><p>Nothing yet: Round 0 is recruiting. After each round we publish what we found, '
                       f'what we changed because of it, and which hypotheses held or failed. Findings name roles, never people.</p>')

        tabs = [('rs-take-part', 'Take part', take), ('rs-roadmap', 'Roadmap', roadmap), ('rs-backlog', 'Backlog', backlog),
                ('rs-ideas', 'Ideas and voting', ideas), ('rs-prioritise', 'How we prioritise', prio), ('rs-learned', 'What we have learned', learned)]
        hero = self.hero('megaphone', 'Have your say', 'Have your say: shape this portal', 'Take part in user research, suggest and vote for ideas, and see what is planned and why. We work in the open.',
                         brief=['Sign up for research that suits you: from a 5 minute survey to an hour on a call.', 'Suggest ideas and vote for the ones you want; votes count towards priority.',
                                f'See the roadmap, the backlog of {len(items)} items and how each is scored against government strategy.'],
                         meta=[('list-checks', f'{len(R["methods"])} ways to take part'), ('kanban', f'{nnow} items in Now'), ('scale', f'{len(R["criteria"])} criteria')])
        drawer = [{'label': 'Have your say', 'icon': 'megaphone', 'items': [
            {'id': 'ways', 'label': 'Ways to take part', 'icon': 'list-checks', 'count': len(R['methods']), 'new': True},
            {'id': 'sign-up', 'label': 'Sign up', 'icon': 'clipboard-list'},
            {'id': 'privacy', 'label': 'Your information', 'icon': 'lock-keyhole'},
            {'id': 'rounds', 'label': 'Research rounds', 'icon': 'route', 'count': len(R['rounds'])},
            {'id': 'roadmap', 'label': 'Roadmap', 'icon': 'kanban', 'new': True},
            {'id': 'backlog', 'label': 'Backlog', 'icon': 'list-ordered', 'count': len(items)},
            {'id': 'ideas', 'label': 'Ideas and voting', 'icon': 'lightbulb', 'new': True},
            {'id': 'prioritise', 'label': 'How we prioritise', 'icon': 'scale'},
            {'id': 'decisions', 'label': 'Decisions log', 'icon': 'history', 'count': len(R['decisions'])},
            {'id': 'learned', 'label': 'What we have learned', 'icon': 'book-open'}]}]
        for x in items:
            self.add_search(f'{x["id"]} {x["title"]}', 'Backlog', f'research.html#bl-{x["id"]}', x['story'])
        return self.page('research', 'Have your say', hero + self.tabbed(tabs, 'Have your say'), drawer, crumbs=['Have your say'],
                         jsonld={'@type': 'WebPage', 'about': 'User research, product roadmap and backlog for the portal'})

    # -- version 1.10: level labels and easy read (BL-17) ------------------------------------------
    def level_and_easy(self):
        k = getattr(self, '_key', None)
        lv = PAGE_LEVEL.get(k)
        tag = f' <span class="level-tag lv-{lv.lower()}" data-tip="{E(LEVEL_TEXT[lv])}">{icon(LEVELS[lv])}Level: {E(lv)}</span>' if lv else ''
        er = (self.d.get('easy_read') or {}).get(k)
        easy = (f'<details class="easy-read" id="easy-read"><summary>{icon("book-open")}Easy read summary</summary><ul>' + ''.join(f'<li>{E(x)}</li>' for x in er) + '</ul></details>') if er else ''
        return tag, easy

    # -- version 1.10: boards, councils and networks ------------------------------------------------
    def p_bodies(self):
        B = self.d['bodies']
        boards = [x for x in B['items'] if x['id'].startswith('GB-')]
        nets = [x for x in B['items'] if x['id'].startswith('NW-')]

        def card(x):
            caps = ' '.join(f'<span class="pill {c}">{E({"gov": "Governance", "cat": "Cataloguing", "dq": "Quality"}[c])}</span>' for c in x['caps'])
            warn = f'<p class="tag">{icon("triangle-alert")}Status unclear</p>' if x.get('unclear') else ''
            return (f'<li class="cr-card body-card" id="{x["id"]}" data-item data-kind="{slug(x["kind"])}"><div class="cr-head">{tile("building-2" if x["id"].startswith("GB-") else "handshake", "sm")}'
                    f'<div><p class="caption">{E(x["kind"])} · {E(x["host"])}</p><h3>{E(x["name"])}</h3></div></div>{warn}'
                    f'<p><strong>Purpose:</strong> {E(x["purpose"])}{prov("V", B["checked"])}</p>'
                    f'<dl class="cr-dl"><dt>{icon("target")} Aims</dt><dd>{ul(x["aims"])}</dd>'
                    f'<dt>{icon("flag")} Expected outcomes</dt><dd>{E(x["outcomes"])}</dd>'
                    f'<dt>{icon("landmark")} Link to the DAM Policy</dt><dd>{E(x["dam"])}{prov("O")}</dd>'
                    f'<dt>{icon("handshake")} How to take part</dt><dd>{E(x["engage"])}</dd>'
                    f'<dt>{icon("scroll-text")} Terms of reference</dt><dd>{E(x["tor"])}</dd></dl>'
                    f'<p>{caps} <a href="{E(x["url"])}" rel="noopener">{icon("link")}Source page</a></p></li>')
        flow = ''.join(f'<li><a href="#{s["id"]}" class="flow-step"><strong>{E(s["step"])}</strong><span>{E(s["does"])}</span></a></li>' for s in B['flow'])
        route = [['A question or a problem with a DAM Policy requirement', 'Your DAM Policy coordinator, then the <a href="#NW-DMC">Data Management Community</a>'],
                 ['A data quality method or tool', 'The <a href="#NW-GDQC">Government Data Quality Community</a>'],
                 ['A proposed data or metadata standard', 'An open standards challenge to the <a href="#GB-OSB">Open Standards Board</a>, or the DSA through the <a href="#GB-PRG">Peer Review Group</a>'],
                 ['A data sharing blocker', 'The <a href="#NW-DSNE">Data Sharing Network of Experts</a>'],
                 ['A data model, taxonomy or architecture question', 'The <a href="#NW-GDAC">Government Data Architecture Community</a> and <a href="#GB-TOG">Taxonomy Oversight Group</a>'],
                 ['A strategic risk for your organisation', 'Your chief data officer, who can take it to the <a href="#GB-CDO">CDO Council</a>'],
                 ['Something about this portal', '<a href="research.html">Have your say</a>, not the government bodies above']]
        body = self.hero('building-2', 'Frameworks', 'Boards, councils and networks', E(B['intro']),
                         brief=[f'{len(boards)} boards and groups that decide or advise, with how decisions flow.', f'{len(nets)} communities, networks and champion networks you can join.', 'Where to take each kind of issue.'],
                         meta=[('building-2', f'{len(boards)} boards'), ('handshake', f'{len(nets)} networks'), ('clock', f'Checked {B["checked"]}')])
        body += (f'<h2 id="how-decisions">{icon("workflow")} How standards and decisions flow</h2>'
                 f'<p>For data standards, practitioners develop a proposal in a community; the Peer Review Group reviews it; the DSA Steering Board endorses it{prov("V", B["checked"])}.</p>'
                 f'<ol class="flow" aria-label="How a data standard is developed and endorsed">{flow}</ol>'
                 f'<p>Alongside this chain, the <a href="#GB-CDO">CDO Council</a> sets strategy and weighs strategic risk, the <a href="#GB-OSB">Open Standards Board</a> decides on open standards, and the <a href="#GB-DTADA">architecture design authority</a> decides on data architecture.</p>'
                 f'<p class="hint">Source: <a href="https://www.gov.uk/government/publications/data-standards-authority-operational-model-and-processes/data-standards-authority-operational-model-and-processes">Data Standards Authority: operational model and processes</a>.</p>'
                 f'<h2 id="boards">{icon("building-2")} Boards and groups that decide or advise</h2><ul class="cr-list two">{"".join(card(x) for x in boards)}</ul>'
                 f'<h2 id="networks">{icon("handshake")} Communities and networks you can join</h2><p>Most are open to anyone working in the public sector. Join details are on each source page; this portal never lists email addresses.</p><ul class="cr-list two">{"".join(card(x) for x in nets)}</ul>'
                 f'<h2 id="where">{icon("signpost")} Where to take an issue</h2>' + table('t-where', 'Where to take each kind of issue', ['Your issue', 'Where to take it'], route)
                 + f'<p class="hint">Bodies change. If an entry is out of date, <a href="contact.html">tell us</a>. Membership lists and minutes are on the source pages.</p>')
        drawer = [{'label': 'Boards and networks', 'icon': 'building-2', 'items': [
            {'id': 'how-decisions', 'label': 'How decisions flow', 'icon': 'workflow', 'new': True},
            {'id': 'boards', 'label': 'Boards and groups', 'icon': 'building-2', 'count': len(boards)},
            {'id': 'networks', 'label': 'Communities and networks', 'icon': 'handshake', 'count': len(nets)},
            {'id': 'where', 'label': 'Where to take an issue', 'icon': 'signpost', 'count': len(route)}]}]
        for x in B['items']:
            self.add_search(x['name'], 'Board or network', f'bodies.html#{x["id"]}', x['purpose'])
        return self.page('bodies', 'Boards, councils and networks', body, drawer, crumbs=['Frameworks', 'Boards and networks'])

    # -- version 1.10: get involved, champions and badges ------------------------------------------------
    def badge_url(self, b, ext='svg'):
        return '{site}' + f'badges/{b}.{ext}'

    @staticmethod
    def site_addr(html):
        """Write the portal's own address as a placeholder the reader's browser fills from the page address, so no account name is printed in the page (C-17)."""
        return html.replace('{site}', '<span class="site-addr" data-site-addr>[this portal\'s address]/</span>')

    def p_involve(self):
        I, m = self.d['involve'], self.m
        gh = f'https://github.com/{m["repo"]}'
        site = m['site_url']
        B = {b['id']: b for b in I['badges']}
        routes = ''
        for r in I['routes']:
            bd = f'<p><img src="badges/{r["badge"]}.svg" alt="Earns the {E(B[r["badge"]]["name"])} badge" height="20"></p>' if r['badge'] else ''
            routes += (f'<li class="cr-card" id="{r["id"]}"><div class="cr-head">{tile(r["icon"], "sm")}<div><p class="caption">{E(r["time"])}</p><h3>{E(r["name"])}</h3></div></div>'
                       f'<p>{E(r["how"])}</p>{bd}<p><a class="btn-link" href="{E(r["link"])}">{icon("arrow-right")}Start</a></p></li>')
        contrib = (f'<h2 id="contribute">{icon("pencil-line")} Improve the content</h2><ol class="tut">'
                   f'<li><strong>Small fix or question:</strong> use "Report a problem with this page" at the foot of any page, or the <a href="contact.html">contact form</a>.</li>'
                   f'<li><strong>Change a page:</strong> select "Suggest a change" at the foot of a page. GitHub makes your own copy, you edit the content file, and you open a pull request. The owner reviews it.</li>'
                   f'<li><strong>New topic or sector supplement:</strong> post it as an <a href="{gh}/discussions/new?category=ideas">idea</a> first, so others can add evidence.</li>'
                   f'<li><strong>Check a capability flag:</strong> on the <a href="capability-model.html#cm-map">capability model</a>, select "Check this flag" on any capability.</li></ol>'
                   f'<p>Read the <a href="{gh}/blob/main/CONTRIBUTING.md">contributing guide</a> and <a href="{gh}/blob/main/CODE_OF_CONDUCT.md">code of conduct</a> first.</p>')
        C = I['champion']
        champ = (f'<h2 id="champions">{icon("megaphone")} Champions and ambassadors</h2><p>Champions bring the portal into their own teams; ambassadors carry it across organisations. {E(C["time"])}</p>'
                 f'<div class="cols"><div class="panel"><h3>{icon("megaphone")} What a champion does</h3>{ul(C["does"])}</div>'
                 f'<div class="panel"><h3>{icon("award")} What you get</h3>{ul(C["gets"], cls="ticks")}</div>'
                 f'<div class="panel"><h3>{icon("users-round")} What an ambassador does</h3>{ul(C["ambassador"])}</div></div>'
                 f'<p><a class="btn" href="{gh}/issues/new?template=badge-claim.yml&amp;title=%5BBadge%5D%20Champion">{icon("megaphone")}Become a champion</a> '
                 + (f'<a class="btn secondary" href="{E(self.ms_form_link("Get involved: becoming a champion (involve.html#champions)", "idea"))}" rel="noopener" data-ms-form>{icon("lock-keyhole")}Tell us privately instead</a>' if self.ms_form_url() else '') + '</p>')
        tk = ''
        for t in I['toolkit']:
            txt = t['text'].rstrip()
            extra = ''
            if t['id'] == 'TK-EMAIL':
                subj, _, rest = txt.partition('\n')
                q = urllib.parse.quote
                extra = f' <a class="btn secondary" href="mailto:?subject={q(subj.replace("Subject: ", ""))}&amp;body={q(rest.strip().replace("{site}", site))}">{icon("send")}Open in your email</a>'
            tk += (f'<section class="cr-card toolkit" id="{t["id"]}"><h3>{icon(t["icon"])} {E(t["name"])}</h3><pre class="code" id="{t["id"]}-text" tabindex="0">{self.site_addr(E(txt))}</pre>'
                   f'<p><button type="button" class="btn secondary" data-copy-target="{t["id"]}-text" hidden>{icon("link")}Copy text</button>{extra} <span class="copy-status" aria-live="polite"></span></p></section>')
        toolkit = (f'<h2 id="toolkit">{icon("send")} Toolkit: bring others in</h2><p>Ready-made text for email, Microsoft Teams, Slack, Viva Engage, your intranet and a team meeting. Copy it, change what you like, and send it from your own account. Nothing here contains anyone\'s contact details.</p>'
                   f'<div class="cr-list two">{tk}</div>')
        brows = []
        snippets = ''
        for b in I['badges']:
            how = 'Self-declared: display it once you have done it.' if b['claim'] == 'self' else f'<a href="{gh}/issues/new?template=badge-claim.yml&amp;title=%5BBadge%5D%20{urllib.parse.quote(b["name"])}">Claim it</a>, with {E(b["evidence"][0].lower() + b["evidence"][1:])}'
            brows.append([f'<img src="badges/{b["id"]}.svg" alt="{E(b["name"])} badge" height="20"><br><strong id="badge-{b["id"]}">{E(b["name"])}</strong>', E(b['earn']), how])
            md = f'[![DAM capability playbooks {b["name"]}]({self.badge_url(b["id"])})]' + '({site}involve.html#badges)'
            html = '<a href="{site}involve.html#badges"><img src="' + self.badge_url(b['id'], 'png') + f'" alt="DAM capability playbooks {b["name"]}" height="20"></a>'
            sig = f'DAM capability playbooks {b["name"]} · ' + '{site}involve.html'
            snippets += (f'<details class="snip"><summary>{E(b["name"])}: code for your profile and signature</summary>'
                         f'<p>GitHub profile (Markdown):</p><pre class="code" id="sn-{b["id"]}-md" tabindex="0">{self.site_addr(E(md))}</pre><p><button type="button" class="btn secondary" data-copy-target="sn-{b["id"]}-md" hidden>{icon("link")}Copy</button> <span class="copy-status" aria-live="polite"></span></p>'
                         f'<p>Email signature or web page (HTML):</p><pre class="code" id="sn-{b["id"]}-html" tabindex="0">{self.site_addr(E(html))}</pre><p><button type="button" class="btn secondary" data-copy-target="sn-{b["id"]}-html" hidden>{icon("link")}Copy</button> <span class="copy-status" aria-live="polite"></span></p>'
                         f'<p>Plain text signature:</p><pre class="code" id="sn-{b["id"]}-txt" tabindex="0">{self.site_addr(E(sig))}</pre><p><button type="button" class="btn secondary" data-copy-target="sn-{b["id"]}-txt" hidden>{icon("link")}Copy</button> <span class="copy-status" aria-live="polite"></span></p>'
                         f'<p>Downloads: <a href="badges/{b["id"]}.svg" download>SVG</a> · <a href="badges/{b["id"]}.png" download>PNG for social media and email</a></p></details>')
        badges = (f'<h2 id="badges">{icon("award")} Badges</h2><p>Every way of taking part earns a badge you can show on your GitHub profile, on social media or in your email signature. {E(I["badge_note"])}</p>'
                  + table('t-badges', 'Badges and how to earn them', ['Badge', 'How to earn it', 'How to get it'], brows)
                  + f'<p class="hint">Claims are public GitHub issues that show your GitHub username only. Do not include your name or anything above OFFICIAL. No GitHub account? Use the private feedback form and say which badge.</p>'
                  + f'<h3 id="badge-code">{icon("code-xml")} Add a badge to your profile or signature</h3>{snippets}'
                  + f'<h2 id="recognition">{icon("trophy")} Recognition</h2><p>People who claim Contributor, Reviewer, Champion or Ambassador badges can be listed here by GitHub username, if they choose. None yet: be the first.</p>')
        rules = f'<h2 id="rules">{icon("scale")} Rules of engagement</h2>{ul(I["rules"])}'
        body = self.hero('hand-helping', 'Have your say', 'Get involved', E(I['intro']),
                         brief=[f'{len(I["routes"])} ways to take part, from 2 minutes to an ongoing role.', 'A toolkit of emails, posts and a walk-through to bring your team in.', f'{len(I["badges"])} badges for your profile and signature.'],
                         meta=[('route', f'{len(I["routes"])} ways'), ('send', f'{len(I["toolkit"])} templates'), ('award', f'{len(I["badges"])} badges')])
        body += (f'<h2 id="ways">{icon("route")} Ways to take part</h2><ul class="approach-grid">{routes}</ul>' + rules + contrib + champ + toolkit + badges
                 + f'<p>See also <a href="research.html">Have your say</a> for research, the roadmap and ideas, and <a href="bodies.html#networks">Boards, councils and networks</a> for government communities to join.</p>')
        drawer = [{'label': 'Get involved', 'icon': 'hand-helping', 'items': [
            {'id': 'ways', 'label': 'Ways to take part', 'icon': 'route', 'count': len(I['routes']), 'new': True},
            {'id': 'rules', 'label': 'Rules of engagement', 'icon': 'scale', 'count': len(I['rules'])},
            {'id': 'contribute', 'label': 'Improve the content', 'icon': 'pencil-line'},
            {'id': 'champions', 'label': 'Champions and ambassadors', 'icon': 'megaphone', 'new': True},
            {'id': 'toolkit', 'label': 'Toolkit', 'icon': 'send', 'count': len(I['toolkit'])},
            {'id': 'badges', 'label': 'Badges', 'icon': 'award', 'count': len(I['badges']), 'new': True},
            {'id': 'recognition', 'label': 'Recognition', 'icon': 'trophy'}]}]
        return self.page('involve', 'Get involved', body, drawer, crumbs=['Have your say', 'Get involved'])

    def write_badges(self):
        out = self.out / 'badges'
        out.mkdir(exist_ok=True)
        from PIL import Image, ImageDraw, ImageFont
        left = 'DAM playbooks'
        for b in self.d['involve']['badges']:
            lw, rw = 8 + len(left) * 7, 12 + len(b['name']) * 7.4
            w = lw + rw
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="20" role="img" aria-label="{left}: {b["name"]}"><title>{left}: {b["name"]}</title>'
                   f'<rect width="{w:.0f}" height="20" rx="3" fill="#505a5f"/><rect x="{lw:.0f}" width="{rw:.0f}" height="20" rx="3" fill="{b["colour"]}"/><rect x="{lw:.0f}" width="4" height="20" fill="{b["colour"]}"/>'
                   f'<g fill="#ffffff" font-family="Verdana,DejaVu Sans,sans-serif" font-size="11"><text x="{lw / 2:.1f}" y="14" text-anchor="middle">{left}</text>'
                   f'<text x="{lw + rw / 2:.1f}" y="14" text-anchor="middle" font-weight="bold">{b["name"]}</text></g></svg>')
            (out / f'{b["id"]}.svg').write_text(svg, encoding='utf-8')
            s = 4
            im = Image.new('RGBA', (int(w * s), 20 * s), (0, 0, 0, 0))
            dr = ImageDraw.Draw(im)
            hexc = tuple(int(b['colour'][i:i + 2], 16) for i in (1, 3, 5))
            dr.rounded_rectangle([0, 0, w * s - 1, 20 * s - 1], radius=3 * s, fill=(80, 90, 95))
            dr.rounded_rectangle([lw * s, 0, w * s - 1, 20 * s - 1], radius=3 * s, fill=hexc)
            dr.rectangle([lw * s, 0, lw * s + 4 * s, 20 * s - 1], fill=hexc)
            f1 = ImageFont.load_default(size=11 * s)
            for txt, cx in ((left, lw / 2), (b['name'], lw + rw / 2)):
                tw = dr.textlength(txt, font=f1)
                dr.text((cx * s - tw / 2, 3 * s), txt, font=f1, fill=(255, 255, 255))
            im.save(out / f'{b["id"]}.png', optimize=True)

    # -- version 1.10: embeds (BL-16) ---------------------------------------------------------------------
    def write_embeds(self):
        out = self.out / 'embed'
        out.mkdir(exist_ok=True)
        m, base = self.m, self.m['site_url']
        css = ('body{font-family:Arial,Helvetica,sans-serif;margin:0;padding:12px 14px;color:#0b0c0c;background:#fff;line-height:1.45;font-size:16px}'
               'h1{font-size:1.1rem;margin:.2rem 0 .4rem}.cap{font-size:.85rem;color:#484949;margin:0}.str{font-weight:700;text-transform:uppercase;font-size:.8rem;border:2px solid currentColor;padding:0 .3rem;border-radius:3px}'
               'a{color:#1d70b8}a:focus{outline:3px solid #ffdd00;background:#ffdd00;color:#0b0c0c}footer{border-top:1px solid #b1b4b6;margin-top:.6rem;padding-top:.4rem;font-size:.8rem;color:#484949}')
        (out / 'embed.css').write_text(css, encoding='utf-8')
        items = [(r['id'], f'DAM Policy requirement {r["id"]}', r['text'], f'<span class="str">{E(r["strength"])}</span> {E(self.caps[r["cap"]]["name"])}', f'dam.html#{r["id"]}') for r in self.d['requirements']]
        items += [(c['id'], f'{c["id"]}: {c["name"]}', c['note'], f'{E(c["cluster"])} · {E(FLAGS[c["flag"]][0])} in the DAM Policy', f'capability-model.html#{c["id"]}') for c in self.d.get('capmap', [])]
        for i, title, text, cap, url in items:
            (out / f'{i}.html').write_text(f'''<!DOCTYPE html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'">
<meta name="robots" content="noindex"><meta name="referrer" content="no-referrer"><title>{E(title)} - {E(m["short_title"])}</title><link rel="stylesheet" href="embed.css"></head>
<body><main><p class="cap">{cap}</p><h1>{E(title)}</h1><p>{E(text)}</p></main>
<footer><a href="{base}{url}" target="_top" rel="noopener">Open in the {E(m["title"])}</a>. A prototype, not official GOV.UK guidance. Open Government Licence v3.0.</footer></body></html>''', encoding='utf-8')
        return [x[0] for x in items]

    # -- version 1.10: releases feed (BL-19) ----------------------------------------------------------
    def write_feed(self):
        m, base = self.m, self.m['site_url']
        cl = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        entries = ''
        for ptxt in re.split(r'^## ', cl, flags=re.M)[1:]:
            head, *lines = ptxt.strip().split('\n')
            mm = re.match(r'([\d.]+) \((\d{4}-\d{2}-\d{2})\)', head)
            if not mm:
                continue
            items = ''.join(f'<li>{md_code(E(l.strip()[2:]))}</li>' for l in lines if l.strip().startswith('- '))
            entries += (f'<entry><title>Release {mm.group(1)}</title><id>{base}whats-new.html#v{slug(head)}</id><updated>{mm.group(2)}T00:00:00Z</updated>'
                        f'<link rel="alternate" type="text/html" href="{base}whats-new.html#v{slug(head)}"/><content type="html">{E("<ul>" + items + "</ul>")}</content></entry>\n')
        feed = (f'<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom"><title>{E(m["title"])}: releases</title><id>{base}feed.xml</id>'
                f'<updated>{m["as_of"]}T00:00:00Z</updated><link rel="self" href="{base}feed.xml"/><link rel="alternate" href="{base}whats-new.html"/>'
                f'<author><name>The portal\'s service owner</name></author><rights>Open Government Licence v3.0</rights>\n{entries}</feed>\n')
        (self.out / 'feed.xml').write_text(feed, encoding='utf-8')

    # -- version 1.10: ontology and lineage (BL-20) -----------------------------------------------------
    def write_ontology(self, out):
        base = self.m['site_url']
        V = f'{base}ontology#'
        onto = [f'@prefix dcp: <{V}> .', '@prefix owl: <http://www.w3.org/2002/07/owl#> .', '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .',
                '@prefix prov: <http://www.w3.org/ns/prov#> .', '@prefix dcterms: <http://purl.org/dc/terms/> .', '',
                f'<{base}ontology> a owl:Ontology ; rdfs:label "DAM capability playbooks ontology" ; dcterms:license <https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/> ; owl:versionInfo "{self.m["version"]}" .', '']
        for c, label, sup in [('PolicyRequirement', 'DAM Policy requirement', 'prov:Entity'), ('Capability', 'Capability', 'prov:Entity'), ('PortalRequirement', 'Portal requirement', 'prov:Entity'),
                              ('Check', 'Automated check', 'prov:Plan'), ('Page', 'Portal page', 'prov:Entity'), ('Source', 'Source document', 'prov:Entity'), ('BacklogItem', 'Backlog item', 'prov:Entity')]:
            onto.append(f'dcp:{c} a owl:Class ; rdfs:label "{label}" ; rdfs:subClassOf {sup} .')
        for p, label, dom, rng in [('metBy', 'met by', 'PolicyRequirement', 'Page'), ('provedBy', 'proved by', 'PortalRequirement', 'Check'), ('realisedIn', 'realised in', 'PortalRequirement', 'Page'),
                                   ('needs', 'needs', 'Capability', 'Source'), ('strength', 'strength', 'PolicyRequirement', None)]:
            onto.append(f'dcp:{p} a {"owl:ObjectProperty" if rng else "owl:DatatypeProperty"} ; rdfs:label "{label}" ; rdfs:domain dcp:{dom}' + (f' ; rdfs:range dcp:{rng} .' if rng else ' .'))
        (out / 'ontology.ttl').write_text('\n'.join(onto) + '\n', encoding='utf-8')

        def lit(s):
            return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ') + '"'
        L = [f'@prefix dcp: <{V}> .', '@prefix prov: <http://www.w3.org/ns/prov#> .', '@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .', '']
        for s in self.d['sources']:
            L.append(f'<{s["url"]}> a dcp:Source ; rdfs:label {lit(s["title"])} .')
        for r in self.d['requirements']:
            L.append(f'<{base}dam.html#{r["id"]}> a dcp:PolicyRequirement ; rdfs:label {lit(r["id"])} ; dcp:strength {lit(r["strength"])} ; prov:wasDerivedFrom <{self.src[r["src"]]["url"]}> ; dcp:metBy <{base}{CAP_PAGE[r["cap"]]}.html> .')
        for c in self.d.get('capmap', []):
            ref = f' ; prov:wasDerivedFrom <{self.src["SRC-DAM"]["url"]}#{c["dam"]}>' if c['dam'] else ''
            L.append(f'<{base}capability-model.html#{c["id"]}> a dcp:Capability ; rdfs:label {lit(c["name"])}{ref} .')
        for r in self.d['design']['requirements']:
            pages = ' , '.join(f'<{base}{"" if f == "index" else f + ".html"}>' for f in r['features'] if f != 'all') or None
            checks = ' , '.join(f'dcp:check-{c}' for c in r['checks'])
            L.append(f'<{base}design.html#{r["id"]}> a dcp:PortalRequirement ; rdfs:label {lit(r["id"] + ": " + r["text"])}' + (f' ; dcp:realisedIn {pages}' if pages else '') + (f' ; dcp:provedBy {checks}' if checks else '') + ' .')
        for c in sorted(KNOWN_CHECKS):
            L.append(f'dcp:check-{c} a dcp:Check ; rdfs:label {lit(c)} .')
        for x in self.research_items():
            L.append(f'<{base}research.html#bl-{x["id"]}> a dcp:BacklogItem ; rdfs:label {lit(x["id"] + ": " + x["title"])} .')
        (out / 'lineage.ttl').write_text('\n'.join(L) + '\n', encoding='utf-8')

    def write_offline(self):
        import zipfile
        z = self.out / 'dam-playbooks-offline.zip'
        with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in sorted(self.out.rglob('*')):
                if f.is_file() and f != z:
                    zi = zipfile.ZipInfo(f'dam-playbooks/{f.relative_to(self.out).as_posix()}', date_time=(2026, 1, 1, 0, 0, 0))
                    zi.compress_type = zipfile.ZIP_DEFLATED
                    zf.writestr(zi, f.read_bytes())

    def rfi_rows(self):
        n, rows = 0, []
        for g in self.d.get('tooling', {}).get('questions', []):
            for q in g['items']:
                n += 1
                rows.append([f'RFI-{n:02d}', g['group'], q])
        return rows

    def by_role(self, text):
        """Replace any address in the owner's GitHub account or Pages site with what it is, keeping the page (D-028)."""
        owner = self.m['repo'].split('/')[0]
        names = {self.m['repo'].split('/')[1]: 'this portal'}
        for p in (self.d.get('related') or {}).get('portals', []):
            m = re.match(r'https://[^/]+\.github\.io/([^/]+)/', p['url'])
            if m:
                names[m.group(1)] = 'the ' + p['name']
        pat = r'https?://(?:github\.com/' + re.escape(owner) + r'/|' + re.escape(owner) + r'\.github\.io/)([A-Za-z0-9._-]+)/?([^\s)]*)'

        def sub(m):
            kind = 'repository' if 'github.com' in m.group(0) else 'site'
            what = names.get(m.group(1), "another project in the owner's account")
            return f'{kind} of {what}' + (f', {m.group(2)}' if m.group(2) else '')
        return re.sub(pat, sub, text)

    def p_status(self):
        st = self.status
        if not st:
            body = self.hero('activity', 'Status', 'Status and health', 'No health run has been recorded for this build yet. The weekly run publishes its results here.')
            return self.page('status', 'Status and health', body, None, crumbs=['Status'])
        good = st['healthy']
        srows = [[E(x['title']), f'<strong class="status s-{"completed" if x["state"] == "ok" else "in-progress" if x["state"] == "unbaselined" else "not-started"}">{E(x["state"])}</strong>', E(x.get('updated') or '-'), E(x['detail'] or '-')] for x in st['sources']]
        prow = [[E(x['page']), f'{x["bytes"] / 1000:.0f} kB', 'Within envelope' if x['ok'] else 'Over envelope'] for x in st['pages']]
        # D-019, D-028: problems quote addresses; name repositories and sites by role, never by the owner's account name
        probs = ul([self.by_role(p) for p in st['problems']]) if st['problems'] else '<p>No problems found.</p>'
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
            rel += f'<section class="release" id="v{slug(head)}"><h2>{icon("milestone")} {E(head)}</h2>{ul([md_code(E(i)) for i in items], raw=True)}</section>'
        body = self.hero('milestone', "What's new", "What's new", 'Changes in each release, newest first. Releases are also listed on GitHub with their source code. Follow releases in any feed reader with the <a href="feed.xml">Atom feed</a>.')
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
        write_csv('templates.csv', ['template_id', 'template', 'capability', 'field_order', 'field', 'mode'],
                  [[t['id'], t['name'], c['id'], i + 1, f, t['mode']] for c in d['capabilities'] for t in c.get('templates', []) for i, f in enumerate(t['fields'])])
        # Version 1.11.0: each template on its own, as a header row ready to fill in, and workbooks as tabbed spreadsheets.
        (out / 'templates').mkdir(exist_ok=True)
        for c in d['capabilities']:
            for t in c.get('templates', []):
                if t.get('sheets'):
                    write_ods(out / 'templates' / f'{t["id"]}.ods', [(sh['name'], sh['fields']) for sh in t['sheets']])
                    for sh in t['sheets']:
                        write_csv(f'templates/{t["id"]}-{slug(sh["name"])}.csv', sh['fields'], [])
                else:
                    write_csv(f'templates/{t["id"]}.csv', t['fields'], [])
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
            if d.get('tooling'):
                write_csv('interoperability-questions.csv', ['id', 'group', 'question'], self.rfi_rows())
            write_csv('change-checklist.csv', ['id', 'title', 'mode', 'stage', 'action', 'roles', 'rulebook', 'capabilities'],
                      [[x['id'], x['title'], x['mode'], x['stage'], a, ' '.join(x['roles']), ' '.join(x['refs']), ' '.join(x['cr'])] for x in d['change']['items'] for a in x['actions']])
            write_csv('maturity-structure.csv', ['topic', 'topic_name', 'section_url'] + [t['name'] for t in d['maturity']['themes']],
                      [[t['n'], t['name'], d['maturity']['url'] + '#' + t['anchor']] + [t['rows'][th['name']] for th in d['maturity']['themes']] for t in d['maturity']['topics']])
        if d.get('research'):
            ri = self.research_items()
            keys = [c['id'] for c in d['research']['criteria']]
            write_csv('backlog.csv', ['id', 'title', 'type', 'story', 'source', 'status', 'release', 'reason', 'strategies', 'score', 'suggests', 'votes'] + keys,
                      [[x['id'], x['title'], x['type'], x['story'], x['source'], x['status'], x.get('release', ''), x.get('reason', ''), ' '.join(x['strategy']), x['score'], x['band'], x['votes']]
                       + [x['scored'][k] for k in keys] for x in ri])
            (out / 'backlog.json').write_text(json.dumps({'as_of': m['as_of'], 'version': m['version'], 'wip_limit': d['research']['wip_limit'],
                                                          'criteria': d['research']['criteria'], 'vote_bands': d['research']['vote_bands'], 'bands': d['research']['bands'],
                                                          'strategies': d['research']['strategies'], 'decisions': d['research']['decisions'],
                                                          'items': [{k: v for k, v in x.items() if k != 'assess'} for x in ri],
                                                          'ideas': {'available': self.ideas.get('available', False), 'as_of': self.ideas.get('as_of', ''), 'count': len(self.ideas.get('ideas', []))}},
                                                         indent=1, ensure_ascii=False), encoding='utf-8')
        self.write_ontology(out)
        det = {x['prop']: x for x in self.caps['cat']['metadata_detail']}
        write_csv('metadata-dictionary.csv', ['property', 'mem_slot', 'obligation', 'rule', 'type', 'format', 'cardinality', 'value_list', 'example'],
                  [[x['prop'], x['mem'], x['obligation'], x['rule'], det[x['prop']]['type'], det[x['prop']]['format'], det[x['prop']]['card'],
                    det[x['prop']].get('values', ''), det[x['prop']]['example']] for x in self.caps['cat']['metadata']])
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
               '@id': m['site_url'] + 'data/sources.jsonld', '@type': 'dcat:Catalog', 'dcterms:title': m['title'] + ': sources',
               'dcterms:modified': m['as_of'], 'dcat:contactPoint': {'@type': 'http://www.w3.org/2006/vcard/ns#Kind', 'http://www.w3.org/2006/vcard/ns#hasURL': m['site_url'] + 'contact.html'},
               'dcat:resource': [{'@id': s['url'], '@type': 'dcat:Resource', 'dcterms:title': s['title'], 'dcterms:publisher': s['publisher'],
                                  'dcterms:type': s['type'], 'dcterms:description': s['note']} for s in d['sources']]
               + [{'@id': x['url'], '@type': 'dcat:Resource', 'dcterms:title': x['title'], 'dcterms:publisher': x['publisher'],
                   'dcterms:type': x['group'], 'dcterms:description': x['why']} for x in d['rulebook']]}
        (out / 'sources.jsonld').write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding='utf-8')
        self.write_catalogue(out)
        sm = ''.join(f'<url><loc>{m["site_url"]}{"" if k == "index" else k + ".html"}</loc><lastmod>{m["as_of"]}</lastmod></url>' for k in [x[0] for x in NAV] + ['contact', 'status', 'whats-new', 'design', 'notices', 'accessibility', 'data', 'test', 'guide', 'site-map', 'reuse', 'research', 'involve'])
        (self.out / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>', encoding='utf-8')


def write_registers(d, docs):
    write_owner_docs(d, docs)
    _write_registers(d, docs)


def write_owner_docs(d, docs):
    """Full open register, build report and build standard assessment: for the service team, kept in the repository (version 1.5.1)."""
    docs.mkdir(exist_ok=True)
    cell = lambda t: str(t).replace('|', '\\|').replace('\n', ' ')
    head = 'Generated from `content/` by `tools/build.py`. Do not edit by hand.\n\n'
    rows = '\n'.join(f'| {o["id"]} | {"Yes" if o.get("reader") else "No"} | {cell(o["item"])} | {cell(o["who"])} |' for o in sorted(d['open_register'], key=lambda o: o['id']))
    (docs / 'open-register.md').write_text('# Open register\n\n' + head + 'Items design cannot close, and who must act. "On portal" items appear as known limitations on the About page.\n\n'
                                           '| ID | On portal | Item | Who must act |\n|---|---|---|---|\n' + rows + '\n', encoding='utf-8')
    rows = '\n'.join(f'| {x["id"]} | {cell(x["name"])} | {x["moscow"]} | {x["status"]} | {cell(x["how"])} |' for x in d['standards'])
    (docs / 'build-standard-assessment.md').write_text('# Assessment against the build standard\n\n' + head + f'{cell(d["meta"]["profile"])} {cell(d["meta"]["grade_reason"])}\n\n'
                                                       '| ID | Routine or practice | MoSCoW | Status | How |\n|---|---|---|---|---|\n' + rows + '\n', encoding='utf-8')
    m = d['meta']
    (docs / 'checkpoint.md').write_text(f'''# Checkpoint

{head}Version {m["version"]}, as of {m["as_of"]}.

**Brief.** Bring together the playbook material for data governance, data cataloguing and data quality in one interactive portal, organised around the people who use it and how they learn; then add the capabilities the DAM Policy relies on, the maturity model, professions and skills, sector supplements and delivery and change guidance.

**Arc of development.** See `CHANGELOG.md` for each release from 1.0.0.

**Against the brief.** Met for governance, quality, the capability model, professions and skills, sector supplements and delivery and change. Partly met for cataloguing, which is built from public guidance because the fuller cataloguing playbook is not yet published (OR-01). Not yet tested with users (OR-04) or with disabled people (OR-09); the testing page and form exist to start that.
''', encoding='utf-8')


def _write_registers(d, docs):
    """Defect register and challenge review live in the repository, not on the portal (version 1.5). C-27 keeps them in step."""
    docs.mkdir(exist_ok=True)
    cell = lambda t: str(t).replace('|', '\\|').replace('\n', ' ')
    rows = '\n'.join(f'| {x["id"]} | {cell(x["found"])} | {cell(x["defect"])} | {cell(x["cause"])} | {cell(x["check"])} |' for x in d['defects'])
    (docs / 'defect-register.md').write_text(
        '# Defect register\n\nGenerated from `content/playbooks.yaml` by `tools/build.py`. Do not edit by hand.\n\n'
        'Every defect has a root cause and a check, written in the same change as the fix, that stops it coming back. '
        'The set of checks never shrinks.\n\n| ID | Found | Defect | Root cause | Check that now prevents it |\n|---|---|---|---|---|\n' + rows + '\n', encoding='utf-8')
    rows = '\n'.join(f'| {cell(a["challenge"])} | {cell(a["answer"])} |' for a in d['adversarial'])
    (docs / 'challenge-review.md').write_text(
        '# Challenge review\n\nGenerated from `content/playbooks.yaml` by `tools/build.py`. Do not edit by hand.\n\n'
        'The strongest arguments against the portal and how each is answered. Where an answer depends on something not yet done, '
        'the open register on the portal\'s About page tracks it.\n\n| Challenge | Answer |\n|---|---|\n' + rows + '\n', encoding='utf-8')


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
    write_registers(d, Path(a.content).resolve().parent.parent / 'docs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
