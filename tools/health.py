#!/usr/bin/env python3
"""Health run (self-updating SR26, self-reviewing SR09, self-reporting SR33, self-costing SR34).

Checks, without changing any content:
  - the review date has not passed
  - every source can still be reached, and GOV.UK sources have not been updated since they were last verified
  - every page stays inside the page-weight envelope
  - every GOV.UK section the capability map signposts still exists (HL-02)

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
import time
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


def fetch_meta(url, timeout=20, accept=HTML_ACCEPT):
    """Like fetch, but also returns the response headers, so a bot challenge can be told apart from the page (D-045)."""
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read(), dict(r.headers)


# D-045: some sites answer automated checks with a bot challenge instead of the page. EUR-Lex returns 202 with
# x-amzn-waf-action: challenge, for real and made-up laws alike, and a 404 to some runners. Either way the checker never
# saw the page, so the link is neither ok nor broken: it is blocked, and a person checks it.
CHALLENGE_HEADERS = ('x-amzn-waf-action', 'cf-mitigated')


def is_challenge(code, headers):
    h = {k.lower(): v for k, v in (headers or {}).items()}
    return any(k in h for k in CHALLENGE_HEADERS) or code == 202


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


def check_anchors(d):
    """HL-02 (version 1.4): every section the capability map signposts still exists on the live GOV.UK page."""
    fw = ROOT / 'content' / 'frameworks.yaml'
    if not fw.exists():
        return []
    f = yaml.safe_load(fw.read_text(encoding='utf-8'))
    urls = {s['id']: s['url'] for s in d['sources']}
    urls.update({x['id']: x['url'] for x in d.get('rulebook', []) + f.get('rulebook_more', [])})
    want = {}
    for c in f.get('capmap', []):
        if c.get('dam'):
            want.setdefault('SRC-DAM', set()).add(c['dam'])
        for sg in c['signposts']:
            if sg.get('a'):
                want.setdefault(sg['doc'], set()).add(sg['a'])
    out = []
    for doc, anchors in sorted(want.items()):
        url = urls[doc]
        row = {'doc': doc, 'url': url, 'checked': len(anchors), 'missing': [], 'state': 'ok'}
        try:
            path = urllib.parse.urlparse(url).path
            _, body = fetch('https://www.gov.uk/api/content' + path, accept='application/json')
            j = json.loads(body)
            det = j.get('details', {})
            html_body = det.get('body', '') or ''.join(x.get('body', '') for x in det.get('parts', []))
            row['missing'] = sorted(a for a in anchors if f'id="{a}"' not in html_body)
            if row['missing']:
                row['state'] = 'changed'
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
        code, headers = None, {}
        for attempt in range(3):  # D-019: retry, because a single 5xx or timeout is not evidence of a broken link
            try:
                code, _, headers = fetch_meta(u)
                row.pop('detail', None)
            except urllib.error.HTTPError as e:
                code, headers = e.code, dict(e.headers or {})
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
                code, row['detail'] = None, str(e)[:120]
            if code is not None and code < 500:
                break
            time.sleep(2 * (attempt + 1))
        row['code'] = code
        if code is not None and is_challenge(code, headers):
            row['state'], row['detail'] = 'blocked', 'bot challenge; the page was never seen, so a person checks it (D-045)'
        elif code in (401, 403, 405, 429):
            row['state'] = 'blocked'  # the site refuses automated checks; not a broken link
        elif code in (404, 410):
            row['state'] = 'broken'
        elif code is None or code >= 500:
            row['state'] = 'unavailable'  # still failing after retries; reported, but not counted as broken
        elif code >= 400:
            row['state'] = 'broken'
        out.append(row)
    return out


HAND = ROOT / 'content' / 'hand-checked-links.yaml'


def apply_hand_checks(links, today, hand=None):
    """Backstop for D-045 (issue 42): a bot challenge can reach a runner as a plain 404 with no challenge header. A link a person checked by hand within
    expire_days counts as blocked, not broken, and says when it was checked. An expired check, or a link the register does not
    name, stays broken, so nothing is waved through for good."""
    if hand is None:
        hand = yaml.safe_load(HAND.read_text(encoding='utf-8')) if HAND.exists() else {'links': []}
    days = int(hand.get('expire_days', 90))
    by_url = {h['url']: h for h in hand.get('links', [])}
    for row in links:
        h = by_url.get(row['url'])
        if row['state'] != 'broken' or not h:
            continue
        age = (today - dt.date.fromisoformat(str(h['checked']))).days
        if 0 <= age <= days:
            row['state'], row['detail'] = 'blocked', f'checked by hand on {h["checked"]}: {h["how"]}'
        else:
            row['detail'] = f'the hand check of {h["checked"]} has expired ({age} days, limit {days}); open it again and record a new date'
    return links


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
    anchors = check_anchors(d) if not a.no_links else []
    weights = page_weights(Path(a.site))
    links = apply_hand_checks(external_links(Path(a.site)), today) if not a.no_links else []
    problems = []
    if today > review:
        problems.append(f'Review date {review} has passed')
    problems += [f'{r["id"]}: {r["state"]} - {r["detail"]}' for r in sources if r['state'] in ('changed', 'unreachable')]
    problems += [f'{r["doc"]}: signposted sections no longer on the page: {", ".join(r["missing"])}' for r in anchors if r['missing']]
    problems += [f'Broken link: {l["url"]} ({l.get("code") or l.get("detail")})' for l in links if l['state'] == 'broken']
    problems += [f'{w["page"]} weighs {w["bytes"]} bytes, over the {PAGE_ENVELOPE} byte envelope' for w in weights if not w['ok']]
    report = {
        'generated': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        'today': today.isoformat(), 'review_date': review.isoformat(), 'review_due': today > review,
        'healthy': not problems, 'problems': problems, 'sources': sources, 'pages': weights,
        'envelope_bytes': PAGE_ENVELOPE, 'links': links, 'anchors': anchors,
        'links_checked': len(links), 'links_blocked': sum(1 for l in links if l['state'] == 'blocked'),
        'links_unavailable': sum(1 for l in links if l['state'] == 'unavailable'),
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
