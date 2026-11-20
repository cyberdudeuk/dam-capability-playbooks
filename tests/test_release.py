"""D-052 (issue 50): the release step must attach files to a release a person already made, not fail.
D-062: pressing Run must release the commit it names, only when the typed version matches that commit's content,
and must create the tag with the release (tag pushes cannot be relied on; releases here are immutable).

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


def step_named(prefix):
    wf = yaml.safe_load((ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8'))
    runs = [s['run'] for s in wf['jobs']['release']['steps'] if s.get('name', '').startswith(prefix)]
    assert len(runs) == 1, prefix
    return runs[0]


def run_tag_step(event, confirm, version='1.16.0', changelog='## 1.16.0 (2026-11-20)\n'):
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / 'content').mkdir()
        (Path(d) / 'content' / 'playbooks.yaml').write_text(f'meta:\n  title: x\n  version: {version}\n')
        (Path(d) / 'CHANGELOG.md').write_text('# Changelog\n\n## Unreleased\n' + changelog)
        env_file = Path(d) / 'env'
        env_file.write_text('')
        env = dict(os.environ, GITHUB_EVENT_NAME=event, CONFIRM=confirm, GITHUB_ENV=str(env_file), GITHUB_REF_NAME='v7.7.7')
        done = subprocess.run(['bash', '-e', '-c', step_named('Work out the tag')], env=env, cwd=d, capture_output=True, text=True)
        return done.returncode, env_file.read_text(), done.stdout


def run_step(script, release_exists):
    with tempfile.TemporaryDirectory() as d:
        # A stand-in git answers rev-parse with a fixed commit id, so no repository is needed.
        (Path(d) / 'git').write_text('#!/bin/sh\necho 0123456789abcdef0123456789abcdef01234567\n')
        (Path(d) / 'git').chmod(0o755)
        log = Path(d) / 'calls'
        fake = Path(d) / 'gh'
        # The stand-in records every call; "release view" succeeds only when the release exists.
        fake.write_text('#!/bin/sh\necho "$@" >> "%s"\n[ "$1 $2" = "release view" ] && exit %d\nexit 0\n'
                        % (log, 0 if release_exists else 1))
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f'{d}:{os.environ["PATH"]}', GITHUB_REF_NAME='v9.9.9', TAG='v9.9.9')
        subprocess.run(['bash', '-e', '-c', script], env=env, check=True, cwd=d)
        return log.read_text().splitlines()


class Release(unittest.TestCase):
    def test_existing_release_gets_the_files(self):
        calls = run_step(release_step(), release_exists=True)
        self.assertTrue(any(c.startswith('release upload v9.9.9') and '--clobber' in c for c in calls), calls)
        self.assertFalse(any(c.startswith('release create') for c in calls), calls)

    def test_new_release_is_created_with_its_tag_on_the_checked_commit(self):
        calls = run_step(release_step(), release_exists=False)
        self.assertTrue(any(c.startswith('release create v9.9.9') and '--target 0123456789abcdef0123456789abcdef01234567' in c for c in calls), calls)

    def test_run_button_tags_the_version_typed(self):
        code, env, _ = run_tag_step('workflow_dispatch', '1.16.0')
        self.assertEqual((code, env.strip()), (0, 'TAG=v1.16.0'))

    def test_run_button_refuses_a_version_that_does_not_match(self):
        code, env, out = run_tag_step('workflow_dispatch', '1.17.0')
        self.assertNotEqual(code, 0)
        self.assertEqual(env, '')
        self.assertIn('Nothing was released', out)

    def test_run_button_refuses_a_version_with_no_changelog_section(self):
        code, env, _ = run_tag_step('workflow_dispatch', '1.16.0', changelog='')
        self.assertNotEqual(code, 0)
        self.assertEqual(env, '')

    def test_tag_push_uses_the_pushed_tag(self):
        code, env, _ = run_tag_step('push', '')
        self.assertEqual((code, env.strip()), (0, 'TAG=v7.7.7'))

    def test_d062_break_release_without_target_is_caught(self):
        # Deliberate break: without --target, Run would tag whatever GitHub picks (the default branch), not the
        # commit that was checked.
        broken = release_step().replace(' --target "$(git rev-parse HEAD)"', '')
        calls = run_step(broken, release_exists=False)
        self.assertFalse(any('--target ' in c for c in calls), calls)

    def test_checkout_refuses_anything_but_a_commit_id_and_a_commit_off_main(self):
        step = step_named('Check out the commit')
        self.assertIn('^[0-9a-f]{7,40}$', step)
        self.assertIn('merge-base --is-ancestor HEAD origin/main', step)
        self.assertIn('COMMIT: ${{ inputs.commit }}', (ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8'))

    def test_d052_break_unguarded_create_is_caught(self):
        # Deliberate break: the old step, which always creates, must fail the existing-release test's expectation.
        old = 'gh release create "$GITHUB_REF_NAME" "dam-capability-playbooks-${GITHUB_REF_NAME}.zip" --generate-notes'
        calls = run_step(old, release_exists=True)
        self.assertFalse(any(c.startswith('release upload') for c in calls), calls)


if __name__ == '__main__':
    unittest.main()
