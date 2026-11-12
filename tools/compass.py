"""Estate compass (version 1.1): a neutral page that orients people across four distinct portals.

Built from compass/compass.yaml and compass/template.html into site/compass/index.html by the DAM playbooks build,
with the DAMA areas and capabilities taken from this repository's own content. Checked by C-35 and by the browser checks.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'compass'

# Commons pages and catalogue views suggested for each DAMA knowledge area (this compass's own mapping, labelled so on the page)
DQMAP = {'DM-GOV': [('Roles and responsibilities', 'roles.html'), ('Data quality management playbook', 'playbook.html'), ('Operating model and help routes', 'operate.html')],
         'DM-ARC': [('Interoperability', 'interop.html'), ('Capability models', 'models.html')],
         'DM-MOD': [('Capability models and information model', 'models.html'), ('Metadata weaver', 'weaver.html')],
         'DM-OPS': [('Weekly pipeline', 'pipeline.html'), ('Data debt and migration', 'legacy.html')],
         'DM-SEC': [('Frameworks and standards', 'frameworks.html')],
         'DM-INT': [('Interoperability', 'interop.html'), ('Catalogues and quality tools', 'catalogues.html')],
         'DM-DOC': [],
         'DM-REF': [('Interoperability: Metadata Rosetta', 'interop.html'), ('Check a file (identifier checks)', 'check.html')],
         'DM-BI': [('Weekly pipeline', 'pipeline.html')],
         'DM-META': [('Metadata weaver', 'weaver.html'), ('Catalogues and quality tools', 'catalogues.html'), ('Knowledge', 'knowledge.html')],
         'DM-DQ': [('Check a file', 'check.html'), ('Issues framework calculator', 'guidance.html'), ('Data quality playbook', 'playbook.html'), ('Maturity', 'maturity.html'), ('Baseline', 'baseline.html')]}
CATMAP = {'DM-GOV': [('Data and metadata management', 'dam'), ('How well code is looked after', 'practice')],
          'DM-ARC': [('Legacy and technical debt', 'legacy'), ('Data interoperability', 'interop')],
          'DM-MOD': [('Data catalogues and standards', 'standards')],
          'DM-OPS': [('Legacy and technical debt', 'legacy')],
          'DM-SEC': [('How well code is looked after', 'practice')],
          'DM-INT': [('Data interoperability', 'interop'), ('API catalogue', 'apis')],
          'DM-DOC': [('Guidance, policy and playbooks', 'guidance')],
          'DM-REF': [('Registers and authoritative sources', 'registers')],
          'DM-BI': [('Analytics dashboard', 'insights')],
          'DM-META': [('Data catalogues and standards', 'standards'), ('Knowledge layer', 'knowledge')],
          'DM-DQ': [('Data tools and suppliers', 'suppliers')]}

# DCAT-AP-UK pages for each DAMA knowledge area (version 1.1; this compass's own mapping, labelled so on the page)
APMAP = {'DM-GOV': [('Responsible roles, not names', 'class-attribution.html'), ('How the profile is governed and changed', 'governance.html#change')],
         'DM-ARC': [('How the classes connect', 'profile.html#model'), ('Where the profile sits in a pan-UK infrastructure', 'strategy.html#layers')],
         'DM-MOD': [('Every property', 'properties.html'), ('Shapes, schema and data dictionary', 'downloads.html#files')],
         'DM-OPS': [],
         'DM-SEC': [('Security classification', 'properties.html#p-securityClassification'), ('Personal data', 'properties.html#p-personalData')],
         'DM-INT': [('Alignment with DCAT-AP', 'changes.html#dcatap'), ('Downloads and API', 'downloads.html')],
         'DM-DOC': [('Documentation property', 'properties.html#p-documentation')],
         'DM-REF': [('Codelists', 'codelists.html'), ('GOV.UK organisations', 'codelists.html#orgs')],
         'DM-BI': [],
         'DM-META': [('The profile at a glance', 'profile.html'), ('Build a record', 'builder.html'), ('Check records', 'validate.html')],
         'DM-DQ': [('Data quality annotation', 'properties.html#p-qualityAnnotation')]}


# Version 1.2: the DAMA wheel drill-down. Which capabilities (CR) each playbook recipe stage serves.
# This compass's own mapping, labelled so on the page; change items, lenses and maturity strands carry their own CR links in the content.
STAGE_CR = {'gov': {'mandate': ['CR-01', 'CR-02'], 'frame': ['CR-01', 'CR-07'], 'assign': ['CR-07'], 'operate': ['CR-07', 'CR-19'], 'assure': ['CR-03', 'CR-04']},
            'cat': {'mobilise': ['CR-05', 'CR-01'], 'discover': ['CR-05'], 'designate': ['CR-05'], 'own': ['CR-07'], 'describe': ['CR-06'],
                    'publish': ['CR-06', 'CR-11'], 'report': ['CR-03'], 'maintain': ['CR-06', 'CR-04']},
            'dq': {'identify': ['CR-08'], 'define': ['CR-08'], 'baseline': ['CR-08', 'CR-23'], 'prioritise': ['CR-08'], 'improve': ['CR-09'],
                   'report': ['CR-08', 'CR-03'], 'sustain': ['CR-08', 'CR-09'], 'review': ['CR-04', 'CR-08']}}
CAP_PAGE = {'gov': 'governance.html', 'cat': 'cataloguing.html', 'dq': 'quality.html'}
# The wayfinder's role answers, matched to the DAMA view's roles (this compass's own matching)
ROLE_MAP = {'leader': 'cdo', 'coordinator': 'coo', 'owner': 'own', 'dq': 'dql', 'tech': 'stw', 'commercial': 'prg', 'service': 'prg'}
RACI_MAP = {'leader': ['CDO'], 'coordinator': ['COO'], 'owner': ['OWN', 'IAO'], 'dq': ['DQL'], 'tech': ['STW', 'CAT'], 'commercial': [], 'service': ['OWN'], 'other': []}
ROLE_NAMES = {'cdo': 'Chief data officer', 'coo': 'Policy coordinator', 'own': 'Data owner', 'stw': 'Data steward', 'cat': 'Catalogue manager',
              'dql': 'Data quality lead', 'prg': 'Programme lead'}


def wheel(c, d, pb):
    """Areas, capabilities and activities (with their lowest-level steps) for the DAMA wheel drill-down, each with where it is in the four portals."""
    P = {p['id']: p for p in c['portals']}
    dam = P['dam']['url']
    caps = {}
    name_to_area = {a['dmbok']: a['id'] for a in d['dama']['areas']}
    for cap in d['capmap']:
        caps[cap['id']] = {'id': cap['id'], 'name': cap['name'], 'cluster': cap['cluster'], 'coverage': cap['coverage'], 'flag': cap['flag'],
                           'note': cap['note'], 'url': dam + 'capability-model.html#' + cap['id'], 'page': dam + cap['playbook'],
                           'areas': [name_to_area[n] for n in cap['dmbok'] if n in name_to_area],
                           'sign': [s['label'] for s in cap.get('signposts', [])], 'acts': []}
    acts = []

    def add(aid, kind, group, title, url, steps, crs, extra=None):
        crs = [x for x in crs if x in caps]
        if not crs:
            return
        a = {'id': aid, 'kind': kind, 'group': group, 'title': title, 'url': url, 'steps': steps, 'caps': crs}
        a.update(extra or {})
        acts.append(a)
        for x in crs:
            caps[x]['acts'].append(aid)
    for cp in pb['capabilities']:
        for s in cp['stages']:
            add(f'{cp["id"]}-{s["id"]}', 'Playbook recipe', cp['name'], f'{s["n"]}. {s["name"]}', dam + f'{CAP_PAGE[cp["id"]]}#{cp["id"]}-{s["id"]}',
                s['steps'], STAGE_CR[cp['id']].get(s['id'], []), {'goal': s['goal'], 'reqs': [[r, dam + 'dam.html#' + r] for r in s['reqs']], 'raci': s.get('raci', {}), 'order': len(acts)})
    for x in d['change']['items']:
        add(x['id'], 'Change and programmes', x['mode'], x['title'], dam + 'change.html#' + x['id'], x['actions'], x['cr'], {'goal': x['why']})
    for x in d['lenses']['items']:
        steps = [f'{ {"gov": "Governance", "cat": "Cataloguing", "dq": "Quality"}[k]}: {v}' for k in ('gov', 'cat', 'dq') for v in x['actions'].get(k, [])]
        add(x['id'], 'Perspective', x['name'], f'{x["name"]} perspective', dam + 'perspectives.html#' + x['id'], steps, x['cr'], {'goal': x['means']})
    for x in d['maturity']['strands']:
        add('MS-' + x['id'], 'Maturity strand', 'Assess', f'Assess: {x["name"]}', dam + 'capability-model.html#strands',
            [f'Level {i + 1}: {lv}' for i, lv in enumerate(x['levels'])], x['cr'])
    # where each area is in the other portals (the area mappings above)
    ar = {a['id']: a for a in areas(c, d)}
    out_areas = []
    for a in d['dama']['areas']:
        cids = sorted(k for k, v in caps.items() if a['id'] in v['areas'])
        out_areas.append({'id': a['id'], 'name': a['name'], 'desc': a['desc'], 'im': a['im'], 'uses': a.get('uses', {}),
                          'wheel': dam + 'capability-model.html#' + a['id'].lower(), 'caps': cids,
                          'dq': ar[a['id']]['dq'], 'cat': ar[a['id']]['cat'], 'ap': ar[a['id']]['ap']})
    return {'hub': d['dama']['hub'], 'areas': out_areas, 'caps': caps, 'acts': acts, 'roles': ROLE_NAMES, 'role_map': ROLE_MAP, 'raci_map': RACI_MAP,
            'raci_names': {r['code']: r['name'] for r in pb.get('roles', [])}}


def validate_wheel(w, d, pb):
    errs = []
    stages = {cp['id']: {s['id'] for s in cp['stages']} for cp in pb['capabilities']}
    for k, m in STAGE_CR.items():
        if set(m) != stages.get(k, set()):
            errs.append(f'compass wheel: STAGE_CR for {k} must map every recipe stage')
        for s, crs in m.items():
            for x in crs:
                if x not in w['caps']:
                    errs.append(f'compass wheel: {k}-{s} maps to unknown capability {x}')
    for cid, cap in w['caps'].items():
        if not cap['areas']:
            errs.append(f'compass wheel: {cid} is on no area of the wheel')
    if len({a['id'] for a in w['acts']}) != len(w['acts']):
        errs.append('compass wheel: duplicate activity ids')
    if set(ROLE_MAP.values()) - set(ROLE_NAMES):
        errs.append('compass wheel: role map names an unknown role')
    return errs


def load():
    return yaml.safe_load((SRC / 'compass.yaml').read_text(encoding='utf-8'))


def validate(c, d):
    errs = []
    P = {p['id']: p for p in c['portals']}
    if {p['bearing'] for p in c['portals']} != {'N', 'E', 'W', 'S'}:
        errs.append('compass: portals must take the bearings N, E, W and S')
    sit = [o['id'] for o in c['questions'][0]['options']]
    for s in sit:
        if s not in c['routes']:
            errs.append(f'compass: situation {s} has no route')
    for rid, r in c['routes'].items():
        if len({s['p'] for s in r['steps']}) < 2:
            errs.append(f'compass: route {rid} stays in one portal; it does not need the compass')
        for s in r['steps']:
            if s['p'] not in P:
                errs.append(f'compass: route {rid} step {s["title"]}: unknown portal {s["p"]}')
            for k in ('ask', 'why', 'gets'):
                if not s.get(k):
                    errs.append(f'compass: route {rid} step {s["title"]}: missing {k}')
    for x in c['scenarios']:
        if x['route'] not in c['routes'] or x['start'] not in P or any(p not in P for p in x['then']):
            errs.append(f'compass: example "{x["situation"][:40]}" refers to an unknown route or portal')
    areas = {a['id'] for a in d['dama']['areas']}
    if set(DQMAP) != areas or set(CATMAP) != areas or set(APMAP) != areas:
        errs.append('compass: the area mappings must cover every DAMA area in the content')
    g = c.get('glossary', [])
    gids = [x['id'] for x in g]
    if len(gids) != len(set(gids)):
        errs.append('compass: duplicate glossary ids')
    for x in g:
        for r in x.get('related', []):
            if r not in gids:
                errs.append(f'compass: glossary {x["id"]} relates to unknown term {r}')
        if not x.get('def') or len(x['def'].split()) > 45:
            errs.append(f'compass: glossary {x["id"]} needs a plain definition of 45 words or fewer')
    if not c.get('about', {}).get('what'):
        errs.append('compass: say what the compass is (about.what)')
    blob = json.dumps(c)
    if re.search(r'[\w.+-]+' + chr(64) + r'[\w-]+\.[\w.]+', blob):
        errs.append('compass: an email address')
    return errs


def areas(c, d):
    P = {p['id']: p for p in c['portals']}
    by = {}
    for cap in d['capmap']:
        for n in cap['dmbok']:
            by.setdefault(n, []).append((cap['id'], cap['name']))
    out = []
    for a in d['dama']['areas']:
        caps = sorted(set(by.get(a['dmbok'], [])))
        out.append({'id': a['id'], 'name': a['name'], 'desc': a['desc'], 'im': a['im'],
                    'dam': [['DAMA wheel: ' + a['name'], P['dam']['url'] + 'capability-model.html#' + a['id'].lower()]] + [[f'{i} {n}', P['dam']['url'] + 'capability-model.html#' + i] for i, n in caps],
                    'dq': [[t, P['dqc']['url'] + u] for t, u in DQMAP[a['id']]],
                    'cat': [[t, P['cat']['url'] + '#' + h] for t, h in CATMAP[a['id']]] + [['Data management wheel', P['cat']['url'] + '#dama']],
                    'ap': [[t, P['ap']['url'] + u] for t, u in APMAP[a['id']]]})
    return out


def rose(c):
    """The compass rose: four portals on their bearings, you at the centre, and a needle the page turns to your starting portal."""
    P = {p['bearing']: p for p in c['portals']}
    pts = ''
    for k, r in (('N', 0), ('E', 90), ('S', 180), ('W', 270)):
        pts += f'<path d="M150 150 L141 150 L150 {28} Z" fill="#f2c14e" transform="rotate({r} 150 150)"/><path d="M150 150 L159 150 L150 28 Z" fill="#c9a23a" transform="rotate({r} 150 150)"/>'
    for r in (45, 135, 225, 315):
        pts += f'<path d="M150 150 L145 150 L150 70 Z" fill="#8fa3bf" transform="rotate({r} 150 150)"/><path d="M150 150 L155 150 L150 70 Z" fill="#6d84a3" transform="rotate({r} 150 150)"/>'
    ticks = ''.join(f'<line x1="150" y1="18" x2="150" y2="{26 if i % 3 else 30}" stroke="#cfd6de" stroke-width="{2 if i % 3 == 0 else 1}" transform="rotate({i * 10} 150 150)"/>' for i in range(36))

    def lab(b, x, y, anchor):
        """Each bearing's portal: its icon and name, linked to the portal (compass 1.2)."""
        p = dict(P[b])
        p['metaline_safe'] = p['metaphor_line'].replace('"', '&quot;')
        name = p['short']
        tx, ty = {'N': (x, y - 38), 'S': (x, y + 36), 'E': (x + 26, y), 'W': (x - 26, y)}[b]
        words = name.split(' ')
        if b in ('E', 'W') and len(name) > 12:
            mid = (len(words) + 1) // 2
            lines = [' '.join(words[:mid]), ' '.join(words[mid:])]
        else:
            lines = [name]
        txt = ''.join(f'<tspan x="{tx}" dy="{0 if i == 0 else 15}">{l}</tspan>' for i, l in enumerate(lines))
        ty -= 7 * (len(lines) - 1)
        return (f'<a href="{p["url"]}" class="rose-link" data-tip="{p["bearing_name"]}, {p["metaphor"].lower()}: {p["question"]} {p["metaline_safe"]}">'
                f'<circle cx="{x}" cy="{y}" r="17" fill="#0b2545" stroke="#f2c14e" stroke-width="2"/>'
                f'<svg x="{x - 10}" y="{y - 10}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" style="color:#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><use href="#i-{p["icon"]}"/></svg>'
                f'<text x="{tx}" y="{ty}" text-anchor="{anchor}" font-size="13" font-weight="700" fill="#ffffff" class="rose-name">{txt}'
                f'<tspan x="{tx}" dy="14" font-size="10.5" font-weight="400" fill="#f2c14e">{p["metaphor"]}</tspan></text></a>')
    labels = lab('N', 150, 18, 'middle') + lab('E', 282, 150, 'start') + lab('W', 18, 150, 'end') + lab('S', 150, 282, 'middle')
    you = ''  # version 1.1: South is DCAT-AP-UK; you stand at the centre, where the needle pivots
    desc = 'Compass rose. North: ' + P['N']['name'] + '. East: ' + P['E']['name'] + '. West: ' + P['W']['name'] + '. South: ' + P['S']['name'] + '. You are at the centre. The needle turns to the portal where your route starts. Select a portal to open it.'
    return (f'<svg class="rose" viewBox="-118 -50 536 384" role="group" aria-label="{desc}">'
            '<circle cx="150" cy="150" r="140" fill="#102f57" stroke="#f2c14e" stroke-width="3"/><circle cx="150" cy="150" r="118" fill="none" stroke="#3b5577" stroke-width="1"/>'
            f'{ticks}{pts}<circle cx="150" cy="150" r="60" fill="none" stroke="#3b5577" stroke-dasharray="3 5"/>'
            '<g id="needle" class="needle" style="transform:rotate(45deg)"><path d="M150 52 L162 150 L150 160 L138 150 Z" fill="#d4351c" stroke="#ffffff" stroke-width="1.5"/><path d="M150 248 L162 150 L150 140 L138 150 Z" fill="#e8e8e8" stroke="#0b2545" stroke-width="1"/></g>'
            '<circle cx="150" cy="150" r="9" fill="#f2c14e" stroke="#0b2545" stroke-width="2"/>'
            f'{labels}{you}'
            '<text x="150" y="58" text-anchor="middle" font-size="15" font-weight="700" fill="#ffffff">N</text>'
            '<text x="244" y="155" text-anchor="middle" font-size="15" font-weight="700" fill="#ffffff">E</text>'
            '<text x="56" y="155" text-anchor="middle" font-size="15" font-weight="700" fill="#ffffff">W</text>'
            '<text x="150" y="252" text-anchor="middle" font-size="15" font-weight="700" fill="#ffffff">S</text></svg>')


def sprite(names, icon_set):
    return ('<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false"><defs>'
            + ''.join(f'<symbol id="i-{n}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{icon_set[n]}</symbol>' for n in sorted(names))
            + '</defs></svg>')


def build(out, d, icon_set, barcode_svg, qr_svg, pb=None, page_names=None):
    c = load()
    errs = validate(c, d)
    w = wheel(c, d, pb) if pb else None
    if w:
        errs += validate_wheel(w, d, pb)
    if errs:
        raise ValueError('\n'.join(errs))
    t = (SRC / 'template.html').read_text(encoding='utf-8')
    data = {k: c[k] for k in ('meta', 'portals', 'precedence', 'questions', 'routes', 'scenarios', 'when', 'links_today', 'about', 'glossary')}
    data['areas'] = areas(c, d)
    if w:
        w['page_names'] = page_names or {}
        data['wheel'] = w
    # compass 1.2: the latest automatic check of the other portals (tools/compass_sync.py, run in CI before the build).
    # Links found missing are dropped from the area mappings and flagged on routes, so no wayfinder or pathway sends anyone to a missing page.
    sp = ROOT / 'build' / 'compass-sync.json'
    sync = json.loads(sp.read_text(encoding='utf-8')) if sp.exists() else {'available': False}
    bad = sorted(u for u, v in sync.get('links', {}).items() if v.get('state') in ('gone', 'anchor-missing'))
    data['sync'] = {'available': bool(sync.get('available')), 'checked': sync.get('checked', ''), 'portals': sync.get('portals', {}), 'bad': bad,
                    'unmapped': {k: len(v) for k, v in sync.get('unmapped', {}).items()}}
    if bad:
        for a in data['areas'] + (w['areas'] if w else []):
            for k in ('dq', 'cat', 'ap'):
                a[k] = [x for x in a[k] if x[1] not in bad]
    blob = json.dumps(data, ensure_ascii=False)
    used = set(re.findall(r'#i-([a-z0-9-]+)', t)) | set(re.findall(r"ic\('([a-z0-9-]+)'", t))
    used |= {p['icon'] for p in c['portals']} | {x['icon'] for x in c['precedence']} | {q['icon'] for q in c['questions']} | {x['icon'] for x in c['scenarios']} | {'map-pin'}
    missing = sorted(n for n in used if n not in icon_set)
    if missing:
        raise ValueError(f'compass: icons not in the icon set: {missing}')
    m = c['meta']
    bid = f'COMPASS-{m["version"]}-{m["as_of"].replace("-", "")}'
    codes = (f'<figure>{barcode_svg(bid, "Barcode of build identifier " + bid)}<figcaption>{bid}</figcaption></figure>'
             f'<figure>{qr_svg(m["url"], "QR code linking to " + m["url"])}<figcaption>This page</figcaption></figure>')
    html = (t.replace('__SPRITE__', sprite(used, icon_set)).replace('__ROSE__', rose(c)).replace('__CODES__', codes)
            .replace('__DATA__', blob.replace('</', '<\\/')).replace('__TITLE__', m['title']).replace('__SUBTITLE__', m['subtitle'])
            .replace('__URL__', m['url']).replace('__VERSION__', m['version']).replace('__ASOF__', m['as_of'])
            .replace('__HOSTNOTE__', m['host_note']).replace('__CONTACT__', m['contact']))
    (Path(out) / 'compass').mkdir(parents=True, exist_ok=True)
    (Path(out) / 'compass' / 'index.html').write_text(html, encoding='utf-8')
    return bid
