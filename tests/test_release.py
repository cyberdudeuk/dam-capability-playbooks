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


def release_runs():
    wf = yaml.safe_load((ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8'))
    return [s.get('run', '') for s in wf['jobs']['release']['steps']]


def browser_before_tests(runs):
    install = [i for i, r in enumerate(runs) if 'playwright install' in r]
    tests = [i for i, r in enumerate(runs) if 'unittest discover' in r]
    return bool(install and tests and install[0] < tests[0])


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


def run_step(script, state, event='push'):
    """Run the release step with stand-ins. state: None (no release), 'draft', 'complete' or 'published'."""
    with tempfile.TemporaryDirectory() as d:
        # A stand-in git answers rev-parse with a fixed commit id, so no repository is needed.
        (Path(d) / 'git').write_text('#!/bin/sh\necho 0123456789abcdef0123456789abcdef01234567\n')
        (Path(d) / 'git').chmod(0o755)
        log = Path(d) / 'calls'
        fake = Path(d) / 'gh'
        # The stand-in records every call. "release view" prints the state the real --jq filter would print, or fails
        # when there is no release.
        view = 'exit 1' if state is None else f'echo {state}; exit 0'
        fake.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\nif [ "$1 $2" = "release view" ]; then {view}; fi\nexit 0\n')
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        env = dict(os.environ, PATH=f'{d}:{os.environ["PATH"]}', GITHUB_REF_NAME='v9.9.9', TAG='v9.9.9',
                   GITHUB_EVENT_NAME=event)
        subprocess.run(['bash', '-e', '-c', script], env=env, check=True, cwd=d)
        return log.read_text().splitlines()


class Release(unittest.TestCase):
    def test_existing_release_gets_the_files(self):
        calls = run_step(release_step(), 'draft')
        self.assertTrue(any(c.startswith('release upload v9.9.9') and '--clobber' in c for c in calls), calls)
        self.assertFalse(any(c.startswith('release create') for c in calls), calls)

    def test_run_button_makes_a_draft_on_the_checked_commit(self):
        # D-065: the workflow token cannot create the tag, so Run leaves a draft for a person to publish.
        calls = run_step(release_step(), None, event='workflow_dispatch')
        made = [c for c in calls if c.startswith('release create v9.9.9')]
        self.assertTrue(made and '--draft' in made[0] and '--target 0123456789abcdef0123456789abcdef01234567' in made[0], calls)

    def test_tag_push_with_no_release_publishes_one(self):
        calls = run_step(release_step(), None, event='push')
        made = [c for c in calls if c.startswith('release create v9.9.9')]
        self.assertTrue(made and '--draft' not in made[0], calls)

    def test_complete_release_is_left_alone(self):
        # D-065: publishing the draft pushes the tag; the release is already complete and immutable.
        calls = run_step(release_step(), 'complete')
        self.assertFalse(any(c.startswith(('release upload', 'release create')) for c in calls), calls)

    def test_d065_break_uploading_to_a_complete_release_is_caught(self):
        broken = release_step().replace('complete) echo', 'complete) gh release upload "$TAG" "$zip" --clobber; echo')
        calls = run_step(broken, 'complete')
        self.assertTrue(any(c.startswith('release upload') for c in calls), calls)

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

    def test_d063_browser_installed_before_the_tests(self):
        # D-063: the release ran the full test suite without a browser, so the two browser tests errored and 1.16.0
        # could not be released.
        self.assertTrue(browser_before_tests(release_runs()))

    def test_d063_break_no_browser_is_caught(self):
        runs = [r for r in release_runs() if 'playwright install' not in r]
        self.assertFalse(browser_before_tests(runs))

    def test_d062_break_release_without_target_is_caught(self):
        # Deliberate break: without --target, Run would tag whatever GitHub picks (the default branch), not the
        # commit that was checked.
        broken = release_step().replace(' --target "$(git rev-parse HEAD)"', '')
        calls = run_step(broken, None, event='workflow_dispatch')
        self.assertFalse(any('--target ' in c for c in calls), calls)

    def test_checkout_refuses_anything_but_a_commit_id_and_a_commit_off_main(self):
        step = step_named('Check out the commit')
        self.assertIn('^[0-9a-f]{7,40}$', step)
        self.assertIn('merge-base --is-ancestor HEAD origin/main', step)
        self.assertIn('COMMIT: ${{ inputs.commit }}', (ROOT / '.github' / 'workflows' / 'release.yml').read_text(encoding='utf-8'))

    def test_d052_break_unguarded_create_is_caught(self):
        # Deliberate break: the old step, which always creates, must fail the existing-release test's expectation.
        old = 'gh release create "$GITHUB_REF_NAME" "dam-capability-playbooks-${GITHUB_REF_NAME}.zip" --generate-notes'
        calls = run_step(old, 'draft')
        self.assertFalse(any(c.startswith('release upload') for c in calls), calls)


if __name__ == '__main__':
    unittest.main()
