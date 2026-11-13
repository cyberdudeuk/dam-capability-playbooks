#!/usr/bin/env python3
"""Keep the estate compass in step with the four portals (compass 1.2).

Run in CI before the build:  python tools/compass_sync.py --out build/compass-sync.json
It reads every page the compass links to in the other three portals, checks the page is there and the anchor still exists,
takes each portal's last-changed date from its pages, and lists pages a portal publishes in its sitemap that the compass
does not yet point to. The build then drops links that are gone (so no wayfinder or pathway sends anyone to a missing page),
shows when each portal was last checked and changed, and the workflow opens an issue for a person when anything needs a decision.

It never fails the build: if a portal cannot be reached, the compass keeps its links and says they were not checked.
The DAM playbooks' own links are checked by C-35 at every build, so this reads only the other portals.
"""
import argparse
import datetime as dt
import email.utils
import json
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))


class Ids(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        for k, v in attrs:
            if k in ('id', 'name', 'data-view', 'data-hub', 'data-route') and v:
                self.ids.add(v)


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'estate-compass-sync'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode('utf-8', 'replace')
        lm = r.headers.get('Last-Modified')
        return r.status, body, (email.utils.parsedate_to_datetime(lm).date().isoformat() if lm else '')


def links(c, d):
    """Every link the compass makes into the other three portals, with where it is used."""
    import compass
    P = {p['id']: p for p in c['portals']}
    out = {}

    def add(u, where):
        out.setdefault(u, set()).add(where)
    for a in compass.areas(c, d):
        for k in ('dq', 'cat', 'ap'):
            for _, u in a[k]:
                add(u, 'area ' + a['id'])
    for rid, r in c['routes'].items():
        for s in r['steps']:
            if s['p'] != 'dam' and s['path'] != 'role':
                add(P[s['p']]['url'] + s['path'], 'route ' + rid)
    for p in c['portals']:
        if p['id'] != 'dam':
            add(p['url'] + p['start']['path'], 'start ' + p['id'])
    return {u: sorted(w) for u, w in out.items()}


def sitemap_pages(base, fetcher):
    try:
        st, body, _ = fetcher(base + 'sitemap.xml')
    except (urllib.error.URLError, OSError, ValueError):
        return None
    return sorted(set(re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', body)))


def sync(c, d, fetcher=fetch):
    P = {p['id']: p for p in c['portals']}
    pages = {}
    res = {'checked': dt.date.today().isoformat(), 'links': {}, 'portals': {}, 'unmapped': {}}
    for u, where in links(c, d).items():
        page, _, frag = u.partition('#')
        if page not in pages:
            try:
                st, body, lm = fetcher(page)
                p = Ids()
                p.feed(body)
                pages[page] = {'ok': 200 <= st < 300, 'ids': p.ids, 'lm': lm, 'body': body}
            except urllib.error.HTTPError as e:
                pages[page] = {'ok': False, 'status': e.code, 'ids': set(), 'lm': '', 'body': ''}
            except (urllib.error.URLError, OSError, ValueError) as e:
                pages[page] = {'ok': None, 'error': type(e).__name__, 'ids': set(), 'lm': '', 'body': ''}
        pg = pages[page]
        if pg['ok'] is None:
            state = 'unchecked'
        elif not pg['ok']:
            state = 'gone'
        elif frag and frag not in pg['ids'] and f'#{frag}' not in pg['body'] and f"'{frag}'" not in pg['body'] and f'"{frag}"' not in pg['body']:
            state = 'anchor-missing'
        else:
            state = 'ok'
        res['links'][u] = {'state': state, 'used_by': where}
    for pid, p in P.items():
        if pid == 'dam':
            continue
        dates = [v['lm'] for k, v in pages.items() if k.startswith(p['url']) and v['lm']]
        res['portals'][pid] = {'last_changed': max(dates) if dates else '', 'reached': any(v['ok'] for k, v in pages.items() if k.startswith(p['url']))}
        sm = sitemap_pages(p['url'], fetcher)
        if sm:
            mapped = {u.partition('#')[0] for u in res['links']}
            known = mapped | {P[g['portal']]['url'] + g['path'] for g in (c.get('pages') or {}).get('pages', []) if g['portal'] == pid}
            res['unmapped'][pid] = [u for u in sm if u not in known and u.rstrip('/') + '/' != p['url'] and not u.endswith('404.html')]
    return res


def stale_facts(c, today=None, limit=30):
    """Portals whose facts in compass.yaml were last checked more than `limit` days ago. The page's own self-check flagged
    the Repos Asset Catalogue at 36 days while nothing in CI did (D-041), so the daily sync reports it too."""
    today = today or dt.date.today()
    out = []
    for p in c['portals']:
        d = dt.date.fromisoformat(str(p.get('data_as_of') or c['meta']['as_of']))
        if (today - d).days > limit:
            out.append((p['short'], (today - d).days))
    return out


def report(res):
    lines = []
    for name, days in res.get('stale', []):
        lines.append(f'- Facts about {name} in compass/compass.yaml were last checked {days} days ago; check them against the live site and update data_as_of.')
    if lines:
        lines.insert(0, 'Portal facts older than 30 days:')
    bad = {u: v for u, v in res['links'].items() if v['state'] in ('gone', 'anchor-missing')}
    if bad:
        lines.append('Links the compass has stopped showing until a person fixes the mapping in tools/compass.py or compass/compass.yaml:')
        lines += [f'- {v["state"]}: {u} (used by {", ".join(v["used_by"])})' for u, v in sorted(bad.items())]
    for pid, us in res['unmapped'].items():
        if us:
            lines.append(f'\nNew pages in {pid} that the compass does not know yet (add each to compass/pages.yaml with its data management areas):')
            lines += [f'- {u}' for u in us[:40]]
    return '\n'.join(lines)


def main(argv=None):
    import compass
    import build
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='build/compass-sync.json')
    ap.add_argument('--report', default='build/compass-sync.txt')
    a = ap.parse_args(argv)
    c = compass.load()
    d = build.load(ROOT / 'content' / 'playbooks.yaml')
    try:
        res = sync(c, d)
        res['available'] = True
    except Exception as e:  # never fail the build
        res = {'available': False, 'reason': type(e).__name__, 'links': {}, 'portals': {}, 'unmapped': {}, 'checked': dt.date.today().isoformat()}
    res['stale'] = stale_facts(c)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1), encoding='utf-8')
    rep = report(res)
    Path(a.report).write_text(rep, encoding='utf-8')
    print(f'compass sync: {sum(1 for v in res["links"].values() if v["state"] == "ok")} of {len(res["links"])} links ok' + (' ; needs attention' if rep else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
