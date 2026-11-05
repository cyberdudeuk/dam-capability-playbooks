"""Estate compass (version 1.0): a neutral page that orients people across three distinct portals.

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


def load():
    return yaml.safe_load((SRC / 'compass.yaml').read_text(encoding='utf-8'))


def validate(c, d):
    errs = []
    P = {p['id']: p for p in c['portals']}
    if {p['bearing'] for p in c['portals']} != {'N', 'E', 'W'}:
        errs.append('compass: portals must take the bearings N, E and W')
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
    if set(DQMAP) != areas or set(CATMAP) != areas:
        errs.append('compass: the area mappings must cover every DAMA area in the content')
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
                    'cat': [[t, P['cat']['url'] + '#' + h] for t, h in CATMAP[a['id']]] + [['Data management wheel', P['cat']['url'] + '#dama']]})
    return out


def rose(c):
    """The compass rose: three portals on their bearings, you at the centre, and a needle the page turns to your starting portal."""
    P = {p['bearing']: p for p in c['portals']}
    pts = ''
    for k, r in (('N', 0), ('E', 90), ('S', 180), ('W', 270)):
        pts += f'<path d="M150 150 L141 150 L150 {28} Z" fill="#f2c14e" transform="rotate({r} 150 150)"/><path d="M150 150 L159 150 L150 28 Z" fill="#c9a23a" transform="rotate({r} 150 150)"/>'
    for r in (45, 135, 225, 315):
        pts += f'<path d="M150 150 L145 150 L150 70 Z" fill="#8fa3bf" transform="rotate({r} 150 150)"/><path d="M150 150 L155 150 L150 70 Z" fill="#6d84a3" transform="rotate({r} 150 150)"/>'
    ticks = ''.join(f'<line x1="150" y1="18" x2="150" y2="{26 if i % 3 else 30}" stroke="#cfd6de" stroke-width="{2 if i % 3 == 0 else 1}" transform="rotate({i * 10} 150 150)"/>' for i in range(36))

    def lab(b, x, y, anchor):
        p = P[b]
        return (f'<g><circle cx="{x}" cy="{y}" r="17" fill="#0b2545" stroke="#f2c14e" stroke-width="2"/>'
                f'<svg x="{x - 10}" y="{y - 10}" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><use href="#i-{p["icon"]}"/></svg></g>')
    labels = lab('N', 150, 10 + 8, 'middle') + lab('E', 282, 150, 'start') + lab('W', 18, 150, 'end')
    you = ('<g><circle cx="150" cy="282" r="17" fill="#0b2545" stroke="#f2c14e" stroke-width="2"/>'
           '<svg x="140" y="272" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><use href="#i-map-pin"/></svg></g>')
    desc = 'Compass rose. North: ' + P['N']['name'] + '. East: ' + P['E']['name'] + '. West: ' + P['W']['name'] + '. South, at the centre: you. The needle turns to the portal where your route starts.'
    return (f'<svg class="rose" viewBox="-8 -8 316 316" role="img" aria-label="{desc}">'
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


def build(out, d, icon_set, barcode_svg, qr_svg):
    c = load()
    errs = validate(c, d)
    if errs:
        raise ValueError('\n'.join(errs))
    t = (SRC / 'template.html').read_text(encoding='utf-8')
    data = {k: c[k] for k in ('meta', 'portals', 'precedence', 'questions', 'routes', 'scenarios', 'when', 'links_today')}
    data['areas'] = areas(c, d)
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
