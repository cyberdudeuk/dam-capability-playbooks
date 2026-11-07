#!/usr/bin/env python3
"""Weekly operations digest (tier 0 routine, ops/automation.yaml).

The owner's one place to look each week. Lists the Status page's verdict, what routines committed, which workflow
runs failed and what is waiting for a person, then opens one issue labelled digest and closes last week's.
Reads and reports only: it never changes content. The estate conductor reads these digests across repositories.

Plain commands only (D-018): the standard library and the GitHub CLI that the runner provides.

Run: python tools/digest.py            (opens the issue; needs GH_TOKEN and GITHUB_REPOSITORY)
     python tools/digest.py --dry-run  (prints the body and changes nothing)
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

WAITING_LABELS = ['owner action', 'review due', 'health', 'routine', 'overdue', 'needs-reply', 'content', 'contact']
TITLE = 'Operations digest, week from {day}'


def gh(*args):
    return json.loads(subprocess.run(['gh', 'api', *args], check=True, capture_output=True, text=True).stdout or 'null')


def gh_pages(path):
    r = subprocess.run(['gh', 'api', '--paginate', '--slurp', path], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'gh api {path}: {r.stderr.strip()}')
    out = r.stdout
    pages = json.loads(out or '[]')
    items = []
    for p in pages:
        items.extend(p.get('workflow_runs', []) if isinstance(p, dict) else p)
    return items


def status_lines(site):
    try:
        with urllib.request.urlopen(site + 'data/status.json', timeout=30) as r:
            st = json.load(r)
    except Exception as e:  # report, never fail: the digest must still be written
        return ['## Status: could not read data/status.json', str(e)]
    lines = [f"## Status: {'healthy' if st.get('healthy') else 'needs attention'}",
             f"Health run {st.get('generated', 'date unknown')}. Review date {st.get('review_date', 'unknown')}"
             f"{' (review due)' if st.get('review_due') else ''}. [Status page]({site}status.html)"]
    for p in st.get('problems') or []:
        lines.append(f'- Problem: {p}')
    return lines


def body(repo, since):
    day = since.date().isoformat()
    owner, name = repo.split('/')
    site = f'https://{owner}.github.io/{name}/'
    lines = [f'Week from {day}. Written by the digest routine (tier 0, ops/automation.yaml): it reports, a person decides.', '']
    lines += status_lines(site)
    commits = gh_pages(f'repos/{repo}/commits?since={since.strftime("%Y-%m-%dT%H:%M:%SZ")}&per_page=100')
    routine = [c for c in commits if '\nRoutine: ' in c['commit']['message']]
    lines += ['', f'## Changes made by routines ({len(routine)})']
    lines += [f"- {c['commit']['message'].splitlines()[0]} ({c['sha'][:7]}; undo: revert it)" for c in routine] or ['- None.']
    lines += ['', f'People committed {len(commits) - len(routine)} other change(s).']
    page = gh(f'repos/{repo}/actions/runs?created=%3E%3D{day}&per_page=100')  # the latest 100, as in the reference
    runs, total = page['workflow_runs'], page['total_count']
    failed = [r for r in runs if r.get('conclusion') == 'failure']
    lines += ['', f'## Workflow runs: {total}, failed {len(failed)}' + (f' (of the latest {len(runs)})' if total > len(runs) else '')]
    lines += [f"- Failed: [{r['name']} #{r['run_number']}]({r['html_url']}) on {r['head_branch']}, {r['created_at'][:10]}" for r in failed]
    lines += ['', '## Waiting for a person']
    waiting = 0
    for label in WAITING_LABELS:
        items = [i for i in gh_pages(f'repos/{repo}/issues?state=open&per_page=100&labels={urllib.parse.quote(label)}')
                 if not i['title'].startswith('Operations digest')]
        if not items:
            continue
        waiting += len(items)
        lines.append(f'**{label}** ({len(items)})')
        lines += [f"- [#{i['number']} {i['title']}]({i['html_url']}){' (pull request)' if i.get('pull_request') else ''}" for i in items[:10]]
    prs = gh_pages(f'repos/{repo}/pulls?state=open&per_page=100')
    lines.append(f'**Open pull requests** ({len(prs)})')
    lines += [f"- [#{p['number']} {p['title']}]({p['html_url']}) by {'a routine or bot' if p['user']['type'] == 'Bot' else 'a person'}" for p in prs[:10]]
    if not waiting and not prs:
        lines.append('Nothing is waiting.')
    lines += ['', 'This repository has no tier 1 routines that change content. See ops/automation.yaml.']
    return TITLE.format(day=day), '\n'.join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dry-run', action='store_true', help='print the digest and change nothing')
    a = ap.parse_args(argv)
    repo = os.environ.get('GITHUB_REPOSITORY')
    if not repo:
        sys.exit('GITHUB_REPOSITORY is not set')
    since = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) - dt.timedelta(days=7)
    title, text = body(repo, since)
    if a.dry_run:
        print(title, text, sep='\n\n')
        return 0
    old = [i for i in gh_pages(f'repos/{repo}/issues?state=open&labels=digest&per_page=100') if not i.get('pull_request')]
    new = gh('-X', 'POST', f'repos/{repo}/issues', '-f', f'title={title}', '-f', f'body={text}', '-f', 'labels[]=digest')
    for o in old:
        gh('-X', 'POST', f"repos/{repo}/issues/{o['number']}/comments", '-f', f"body=Replaced by #{new['number']}.")
        gh('-X', 'PATCH', f"repos/{repo}/issues/{o['number']}", '-f', 'state=closed', '-f', 'state_reason=completed')
    print(f"Opened #{new['number']}; closed {len(old)} earlier digest(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
