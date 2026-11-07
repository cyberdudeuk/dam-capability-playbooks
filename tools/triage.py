#!/usr/bin/env python3
"""Triage (tier 0 routine, ops/automation.yaml).

Every working day, labels issues that have waited too long for a maintainer's reply (needs-reply) or for a decision
(overdue). Adds labels only; never closes, edits or deletes anything.

Plain commands only (D-018): the standard library and the GitHub CLI that the runner provides.

Run: python tools/triage.py            (adds labels; needs GH_TOKEN and GITHUB_REPOSITORY)
     python tools/triage.py --dry-run  (prints what it would label and changes nothing)
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse

# Working days to a first reply and to a decision, by issue label (the labels the issue forms apply).
# A person sets these; the routine only applies them.
SLA = {'contact': (2, 10), 'content': (2, 10), 'accessibility': (2, 10), 'feedback': (5, 20), 'testing': (5, 20)}


def gh(*args):
    return json.loads(subprocess.run(['gh', 'api', *args], check=True, capture_output=True, text=True).stdout or 'null')


def gh_all(path):
    r = subprocess.run(['gh', 'api', '--paginate', '--slurp', path], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'gh api {path}: {r.stderr.strip()}')
    out = r.stdout
    return [x for page in json.loads(out or '[]') for x in page]


def working_days(since, now):
    """Whole working days (Monday to Friday) after `since`, up to `now`."""
    d, n = since, 0
    while True:
        d += dt.timedelta(days=1)
        if d > now:
            return n
        if d.weekday() < 5:
            n += 1


def decide(issue, comments, maintainers, now):
    """The labels to add to one issue, or an empty list."""
    have = {l['name'] for l in issue['labels']}
    kinds = [SLA[l] for l in have if l in SLA]
    if not kinds:
        return []
    reply, decision = min(k[0] for k in kinds), min(k[1] for k in kinds)
    age = working_days(dt.datetime.fromisoformat(issue['created_at'].replace('Z', '+00:00')), now)
    replied = any(c['user']['login'] in maintainers and c['user']['login'] != issue['user']['login'] for c in comments)
    add = []
    if not replied and age > reply and 'needs-reply' not in have:
        add.append('needs-reply')
    if age > decision and 'overdue' not in have:
        add.append('overdue')
    return add


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry-run', action='store_true', help='print what would be labelled and change nothing')
    a = ap.parse_args(argv)
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not repo:
        sys.exit('GITHUB_REPOSITORY is not set')
    now = dt.datetime.now(dt.timezone.utc)
    try:
        maintainers = {u['login'] for u in gh_all(f'repos/{repo}/collaborators?permission=triage&per_page=100')}
    except RuntimeError as e:  # a token that cannot list collaborators still knows the owner
        print(f'Could not list collaborators ({e}); counting only the repository owner as a maintainer.')
        maintainers = {repo.split('/')[0]}
    seen = set()
    for label in SLA:
        for i in gh_all(f'repos/{repo}/issues?state=open&per_page=100&labels={urllib.parse.quote(label)}'):
            if i.get('pull_request') or i['number'] in seen:
                continue
            seen.add(i['number'])
            add = decide(i, gh_all(f"repos/{repo}/issues/{i['number']}/comments?per_page=100"), maintainers, now)
            if not add:
                continue
            print(f"#{i['number']}: {', '.join(add)}")
            if not a.dry_run:
                gh('-X', 'POST', f"repos/{repo}/issues/{i['number']}/labels", *[x for l in add for x in ('-f', f'labels[]={l}')])
    return 0


if __name__ == '__main__':
    sys.exit(main())
