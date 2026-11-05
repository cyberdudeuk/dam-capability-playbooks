#!/usr/bin/env python3
"""Health run (self-updating SR26, self-reviewing SR09, self-reporting SR33, self-costing SR34).

Checks, without changing any content:
  - the review date has not passed
  - every source can still be reached, and GOV.UK sources have not been updated since they were last verified
  - every page stays inside the page-weight envelope

Writes a machine-readable report (status.json) that tools/build.py renders as the Status page.
Exit code 0 when healthy, 2 when something needs a person's attention.

Usage:
  python tools/health.py --out build/status.json            # report only
  python tools/health.py --record                           # a person re-baselines sources after reviewing them
"""
import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / 'content' / 'source-state.json'
PAGE_ENVELOPE = 1_500_000  # bytes per page, including shared assets
UA = 'dam-capability-playbooks-health/1.1 (+https://github.com/cyberdudeuk/dam-capability-playbooks)'


HTML_ACCEPT = 'text/html,application/xhtml+xml,*/*;q=0.8'  # D-013: a JSON-first Accept header made some GOV.UK pages answer 406


def fetch(url, timeout=20, accept=HTML_ACCEPT):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def govuk_updated(url):
    """Use the GOV.UK Content API for a page's public_updated_at date."""
    path = urllib.parse.urlparse(url).path
    status, body = fetch('https://www.gov.uk/api/content' + path, accept='application/json')
    j = json.loads(body)
    return status, j.get('public_updated_at') or j.get('updated_at')


def check_sources(d, state):
    out = []
    for s in d['sources']:
        row = {'id': s['id'], 'title': s['title'], 'url': s['url'], 'state': 'ok', 'detail': ''}
        try:
            if urllib.parse.urlparse(s['url']).netloc == 'www.gov.uk':
                code, updated = govuk_updated(s['url'])
                row['updated'] = updated
                known = state.get(s['id'], {}).get('updated')
                if known is None:
                    row['state'], row['detail'] = 'unbaselined', 'No baseline recorded yet'
                elif updated != known:
                    row['state'], row['detail'] = 'changed', f'GOV.UK page updated {updated}; last verified version {known}. Review and re-verify.'
            else:
                code, _ = fetch(s['url'])
                if code >= 400:
                    row['state'], row['detail'] = 'unreachable', f'HTTP {code}'
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            row['state'], row['detail'] = 'unreachable', str(e)[:160]
        out.append(row)
    return out


def external_links(site):
    import re
    urls = set()
    for f in site.glob('*.html'):
        for u in re.findall(r'href="(https?://[^"]+)"', f.read_text(encoding='utf-8')):
            u = u.replace('&amp;', '&').split('#')[0]
            if '/issues/new' in u or '/edit/' in u or u.startswith('https://cyberdudeuk.github.io/dam-capability-playbooks'):
                continue  # pre-filled forms and our own pages are checked elsewhere
            urls.add(u)
    out = []
    for u in sorted(urls):
        row = {'url': u, 'state': 'ok'}
        try:
            code, _ = fetch(u)
        except urllib.error.HTTPError as e:
            code = e.code
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
            code, row['detail'] = None, str(e)[:120]
        row['code'] = code
        if code in (401, 403, 405, 429):
            row['state'] = 'blocked'  # the site refuses automated checks; not a broken link
        elif code is None or code >= 400:
            row['state'] = 'broken'
        out.append(row)
    return out


def page_weights(site):
    shared = sum(f.stat().st_size for f in (site / 'assets').glob('*') if f.is_file()) if (site / 'assets').exists() else 0
    rows = []
    for f in sorted(site.glob('*.html')):
        total = f.stat().st_size + shared
        rows.append({'page': f.name, 'bytes': total, 'ok': total <= PAGE_ENVELOPE})
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'build' / 'status.json'))
    ap.add_argument('--site', default=str(ROOT / 'site'))
    ap.add_argument('--record', action='store_true', help='re-baseline source dates after a person has reviewed them')
    ap.add_argument('--today', help='YYYY-MM-DD, for testing')
    ap.add_argument('--no-links', action='store_true', help='skip the external link check')
    a = ap.parse_args(argv)
    d = yaml.safe_load((ROOT / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    review = dt.date.fromisoformat(str(d['meta']['review']))
    sources = check_sources(d, state)
    if a.record:
        new = {r['id']: {'updated': r.get('updated'), 'recorded': today.isoformat()} for r in sources if r.get('updated')}
        STATE.write_text(json.dumps(new, indent=1, sort_keys=True) + '\n')
        print(f'Recorded {len(new)} GOV.UK source dates. Commit content/source-state.json in a reviewed pull request.')
        return 0
    weights = page_weights(Path(a.site))
    links = external_links(Path(a.site)) if not a.no_links else []
    problems = []
    if today > review:
        problems.append(f'Review date {review} has passed')
    problems += [f'{r["id"]}: {r["state"]} - {r["detail"]}' for r in sources if r['state'] in ('changed', 'unreachable')]
    problems += [f'Broken link: {l["url"]} ({l.get("code") or l.get("detail")})' for l in links if l['state'] == 'broken']
    problems += [f'{w["page"]} weighs {w["bytes"]} bytes, over the {PAGE_ENVELOPE} byte envelope' for w in weights if not w['ok']]
    report = {
        'generated': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'today': today.isoformat(), 'review_date': review.isoformat(), 'review_due': today > review,
        'healthy': not problems, 'problems': problems, 'sources': sources, 'pages': weights,
        'envelope_bytes': PAGE_ENVELOPE, 'links': links,
        'links_checked': len(links), 'links_blocked': sum(1 for l in links if l['state'] == 'blocked'),
    }
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1))
    print(('Healthy' if not problems else 'Needs attention') + f': {len(problems)} problem(s)')
    for p in problems:
        print(' -', p)
    return 0 if not problems else 2


if __name__ == '__main__':
    sys.exit(main())
