#!/usr/bin/env python3
"""Read the public ideas from this repository's GitHub Discussions (Ideas category) for the Have your say page.

Run in CI before the final build:  python tools/ideas.py --out build/ideas.json
Needs GITHUB_TOKEN (or GH_TOKEN) with discussions: read, and GITHUB_REPOSITORY (owner/name).

It never fails the build. If the list cannot be read, it writes {"available": false, ...} and the page says so.
It keeps only what is already public on GitHub: number, title, link, votes, comments and dates.
It drops any idea whose title contains an email address, so the page never republishes one (C-04, C-36).
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

API = 'https://api.github.com'
EMAIL = re.compile(r'[\w.+-]+' + chr(64) + r'[\w-]+\.[\w.-]+')
CATEGORY = 'ideas'


def get(url, token):
    req = urllib.request.Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'dam-capability-playbooks-ideas',
                                               'X-GitHub-Api-Version': '2022-11-28', **({'Authorization': f'Bearer {token}'} if token else {})})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def votes(x):
    """An idea's votes are its upvotes, or its thumbs-up reactions if the API does not give upvotes."""
    return max(int(x.get('upvote_count') or 0), int((x.get('reactions') or {}).get('+1') or 0))


def collect(repo, token, fetch=None, pages=10):
    fetch = fetch or get
    owner_repo = repo.strip('/')
    out = []
    for page in range(1, pages + 1):
        batch = fetch(f'{API}/repos/{owner_repo}/discussions?per_page=100&page={page}', token)
        if not batch:
            break
        for x in batch:
            cat = (x.get('category') or {}).get('slug') or ''
            if cat != CATEGORY:
                continue
            title = (x.get('title') or '').strip()
            if not title or EMAIL.search(title) or chr(64) in title:
                continue
            url = x.get('html_url') or ''
            if not url.startswith(f'https://github.com/{owner_repo}/discussions/'):
                continue
            out.append({'n': x['number'], 'title': title[:140], 'url': url, 'votes': votes(x), 'comments': int(x.get('comments') or 0),
                        'created': (x.get('created_at') or '')[:10], 'updated': (x.get('updated_at') or '')[:10],
                        'labels': [l.get('name') for l in (x.get('labels') or []) if l.get('name')],
                        'closed': (x.get('state') == 'closed')})
        if len(batch) < 100:
            break
    out.sort(key=lambda i: (-i['votes'], -i['comments'], i['n']))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='build/ideas.json')
    a = ap.parse_args(argv)
    repo = os.environ.get('GITHUB_REPOSITORY', 'cyberdudeuk/dam-capability-playbooks')
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN') or ''
    now = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d')
    try:
        ideas = collect(repo, token)
        res = {'available': True, 'as_of': now, 'category': CATEGORY, 'ideas': ideas}
        print(f'{len(ideas)} ideas read from {repo}')
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        res = {'available': False, 'as_of': now, 'reason': type(e).__name__, 'ideas': []}
        print(f'ideas not available: {type(e).__name__}', file=sys.stderr)
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())
