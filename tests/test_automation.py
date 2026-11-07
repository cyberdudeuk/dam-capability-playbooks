"""The automation policy holds (estate contract, ops/automation.yaml).

Every workflow is declared with a tier and is in the reviewed inventory; tier 1 routines other than publishing honour
the kill switch; every workflow declares its permissions and uses no third-party action; nothing runs untrusted pull
request code with write access; the contract labels are declared; and the triage rules behave.

Run: python -m unittest discover -s tests
"""
import datetime as dt
import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / '.github' / 'workflows'
POLICY = yaml.safe_load((ROOT / 'ops' / 'automation.yaml').read_text(encoding='utf-8'))
sys.path.insert(0, str(ROOT / 'tools'))
import check_site  # noqa: E402
import triage  # noqa: E402

CONTRACT_LABELS = {'routine', 'digest', 'health', 'review due', 'owner action', 'needs-reply', 'overdue'}


class Policy(unittest.TestCase):
    def test_every_workflow_is_declared(self):
        declared = {r['workflow'] for r in POLICY['routines']}
        for f in WF.glob('*.y*ml'):
            with self.subTest(workflow=f.name):
                self.assertIn(f.name, declared, 'add it to ops/automation.yaml with its tier')
        for r in POLICY['routines']:
            with self.subTest(routine=r['id']):
                self.assertTrue((WF / r['workflow']).exists())
                self.assertIn(r['tier'], (0, 1, 2, 3))
                for k in ('when', 'does', 'changes'):
                    self.assertTrue(r.get(k))

    def test_policy_and_inventory_agree(self):
        self.assertEqual({r['workflow'] for r in POLICY['routines']}, check_site.EXPECTED_WORKFLOWS)

    def test_tier1_routines_honour_the_kill_switch(self):
        for r in POLICY['routines']:
            if r['tier'] == 1 and r['id'] != 'pages':
                with self.subTest(routine=r['id']):
                    self.assertIn('AUTOMATION: ${{ vars.AUTOMATION }}', (WF / r['workflow']).read_text(encoding='utf-8'))

    def test_permissions_declared_and_no_pull_request_target(self):
        for f in WF.glob('*.y*ml'):
            t = f.read_text(encoding='utf-8')
            with self.subTest(workflow=f.name):
                self.assertRegex(t, r'(?m)^permissions:', 'declare permissions at the top')
                self.assertNotIn('pull_request_target', t, 'never run pull request code with write access')

    def test_never_list_is_kept(self):
        self.assertTrue(any('Merge' in n for n in POLICY['never']))
        self.assertTrue(any('settings' in n for n in POLICY['never']))
        self.assertEqual(POLICY['kill_switch'], {'variable': 'AUTOMATION', 'off_value': 'off'})

    def test_contract_labels_are_declared(self):
        names = {x['name'] for x in yaml.safe_load((ROOT / '.github' / 'labels.yml').read_text(encoding='utf-8'))}
        self.assertTrue(CONTRACT_LABELS <= names, CONTRACT_LABELS - names)
        pattern = re.compile(r"^- \{name: (.+?), color: '([0-9a-f]{6})', description: (.+)\}\s*$")
        for line in (ROOT / '.github' / 'labels.yml').read_text(encoding='utf-8').splitlines():
            if line.startswith('- '):
                with self.subTest(line=line):
                    self.assertRegex(line, pattern, 'the labels workflow reads this exact shape')


NOW = dt.datetime(2026, 11, 20, 12, tzinfo=dt.timezone.utc)  # a Friday


def issue(labels, created='2026-11-02T09:00:00Z', user='someone'):
    return {'labels': [{'name': n} for n in labels], 'created_at': created, 'user': {'login': user}}


class Triage(unittest.TestCase):
    def test_working_days_skip_weekends(self):
        monday = dt.datetime(2026, 11, 2, 9, tzinfo=dt.timezone.utc)
        self.assertEqual(triage.working_days(monday, monday + dt.timedelta(days=7)), 5)

    def test_waiting_contact_gets_both_labels(self):
        self.assertEqual(triage.decide(issue(['contact']), [], {'owner'}, NOW), ['needs-reply', 'overdue'])

    def test_negative_a_maintainer_reply_stops_needs_reply(self):
        comments = [{'user': {'login': 'owner'}}]
        self.assertEqual(triage.decide(issue(['contact']), comments, {'owner'}, NOW), ['overdue'])

    def test_negative_unrelated_labels_and_existing_labels_are_left_alone(self):
        self.assertEqual(triage.decide(issue(['question']), [], {'owner'}, NOW), [])
        self.assertEqual(triage.decide(issue(['contact', 'needs-reply', 'overdue']), [], {'owner'}, NOW), [])

    def test_negative_a_new_issue_is_not_labelled(self):
        self.assertEqual(triage.decide(issue(['contact'], created='2026-11-19T09:00:00Z'), [], {'owner'}, NOW), [])


if __name__ == '__main__':
    unittest.main()
