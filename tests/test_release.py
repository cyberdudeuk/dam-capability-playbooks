"""D-052 (issue 50): the release step must attach files to a release a person already made, not fail.

These tests run the workflow's own shell step with a stand-in for the gh command, so they test what the step does,
not only what it says.
"""
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def release_step():
    wf = yaml.safe_load((ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8'))
    runs = [s['run'] for s in wf['jobs']['release']['steps'] if 'gh release' in s.get('run', '')]
    assert len(runs) == 1, runs
    return runs[0]


def run_step(script, release_exists):
    with tempfile.TemporaryDirectory() as d:
        log = Path(d) / 'calls'
        fake = Path(d) / 'gh'
        # The stand-in records every call; "release view" succeeds only when the release exists.
        fake.write_text('#!/bin/sh\necho "$@" >> "%s"\n[ "$1 $2" = "release view" ] && exit %d\nexit 0\n'
                        % (log, 0 if release_exists else 1))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f'{d}:{os.environ["PATH"]}', GITHUB_REF_NAME='v9.9.9')
        subprocess.run(['bash', '-e', '-c', script], env=env, check=True, cwd=d)
        return log.read_text().splitlines()


class Release(unittest.TestCase):
    def test_existing_release_gets_the_files(self):
        calls = run_step(release_step(), release_exists=True)
        self.assertTrue(any(c.startswith('release upload v9.9.9') and '--clobber' in c for c in calls), calls)
        self.assertFalse(any(c.startswith('release create') for c in calls), calls)

    def test_new_release_is_created(self):
        calls = run_step(release_step(), release_exists=False)
        self.assertTrue(any(c.startswith('release create v9.9.9') for c in calls), calls)

    def test_d052_break_unguarded_create_is_caught(self):
        # Deliberate break: the old step, which always creates, must fail the existing-release test's expectation.
        old = 'gh release create "$GITHUB_REF_NAME" "dam-capability-playbooks-${GITHUB_REF_NAME}.zip" --generate-notes'
        calls = run_step(old, release_exists=True)
        self.assertFalse(any(c.startswith('release upload') for c in calls), calls)


if __name__ == '__main__':
    unittest.main()
