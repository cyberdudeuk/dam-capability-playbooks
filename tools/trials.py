"""Trials: experiments that fly in a declared envelope, with an end date and a kill switch (estate contract; ADR 0018 in dcat-ap-uk).

A trial is how something new is tried without risking what already works. It is the test flight of the estate's
flight-operations model: it states what it is trying to learn, what it may touch (its envelope), how success is
measured, when to abort, and when it ends. The build fails if a trial is malformed or has run past its end date, so a
trial is always either landed (made a routine, through a person's pull request) or stopped, never left running.

    python3 tools/trials.py check            # validate ops/automation.yaml trials; exit 1 on any problem
    python3 tools/trials.py gate --id <id>   # exit 0 only if the trial may run now; workflows call this first

Each trial has its own kill switch, the repository variable TRIAL_<ID> (upper case, hyphens as underscores), and the
estate-wide AUTOMATION=off stops every trial too.
"""
import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MAX_DAYS = 90
FIELDS = ('id', 'hypothesis', 'envelope', 'measure', 'abort', 'started', 'ends', 'owner')
# A trial may never touch what the policy keeps for a person. These words in an envelope fail the check.
FORBIDDEN = ('merge', 'setting', 'ruleset', 'secret', 'delete', 'release', 'email', 'conformance', 'endorse', 'main branch')


def kill_variable(tid):
    return 'TRIAL_' + re.sub(r'[^A-Z0-9]', '_', tid.upper())


def _date(v):
    return v if isinstance(v, dt.date) else dt.date.fromisoformat(str(v))


def problems(trials, today=None):
    """Return a list of problems with the trials; an empty list means they are all in order."""
    today = today or dt.date.today()
    out, seen = [], set()
    for t in trials or []:
        tid = t.get('id', '?')
        for f in FIELDS:
            if not t.get(f):
                out.append(f'{tid}: missing {f}')
        if tid in seen:
            out.append(f'{tid}: duplicate id')
        seen.add(tid)
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', str(tid)):
            out.append(f'{tid}: id must be lower case letters, digits and hyphens')
        if t.get('tier', 2) not in (0, 2):
            out.append(f'{tid}: a trial may only observe (0) or propose (2)')
        env = ' '.join(t.get('envelope') or []) if isinstance(t.get('envelope'), list) else str(t.get('envelope', ''))
        for w in FORBIDDEN:
            if w in env.lower():
                out.append(f'{tid}: envelope touches "{w}", which is kept for a person')
        try:
            s, e = _date(t['started']), _date(t['ends'])
            if (e - s).days > MAX_DAYS:
                out.append(f'{tid}: runs {(e - s).days} days; the limit is {MAX_DAYS}')
            if e < s:
                out.append(f'{tid}: ends before it starts')
            if today > e:
                out.append(f'{tid}: ended {e}; land it as a routine through a pull request, or remove it')
        except (KeyError, ValueError, TypeError):
            out.append(f'{tid}: started and ends must be dates (YYYY-MM-DD)')
    return out


def load():
    return yaml.safe_load((ROOT / 'ops' / 'automation.yaml').read_text(encoding='utf-8')).get('trials') or []


def gate(tid, trials=None, env=None, today=None):
    """True only if the trial exists, is in order, is in date and neither kill switch is off."""
    env = os.environ if env is None else env
    trials = load() if trials is None else trials
    match = [t for t in trials if t.get('id') == tid]
    if not match:
        return False, f'No trial called {tid} in ops/automation.yaml.'
    if env.get('AUTOMATION', '').lower() == 'off':
        return False, 'Kill switch is off (AUTOMATION). The trial does nothing.'
    if env.get(kill_variable(tid), '').lower() == 'off':
        return False, f'Kill switch is off ({kill_variable(tid)}). The trial does nothing.'
    p = problems(match, today)
    if p:
        return False, 'Trial is not in order: ' + '; '.join(p)
    return True, f'Trial {tid} may run until {match[0]["ends"]}.'


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check')
    g = sub.add_parser('gate')
    g.add_argument('--id', required=True)
    a = ap.parse_args()
    if a.cmd == 'check':
        p = problems(load())
        for x in p:
            print('TRIAL', x)
        print(f'{len(load())} trials, {len(p)} problems')
        sys.exit(1 if p else 0)
    ok, why = gate(a.id)
    print(why)
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
