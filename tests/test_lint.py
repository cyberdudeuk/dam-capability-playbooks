"""D-047: no linter ran in CI. These tests keep both linters, pinned, in the Build, check and publish workflow."""
import unittest
from pathlib import Path

import json

ROOT = Path(__file__).resolve().parent.parent


class Lint(unittest.TestCase):
    def test_workflow_runs_both_linters(self):
        wf = (ROOT / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
        self.assertIn('ruff check .', wf)
        self.assertIn('npx eslint .', wf)

    def test_linters_are_pinned_and_configured(self):
        self.assertIn('ruff==', (ROOT / 'requirements.txt').read_text(encoding='utf-8'))
        dev = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['devDependencies']
        self.assertRegex(dev.get('eslint', ''), r'^\d+\.\d+\.\d+$')
        self.assertTrue((ROOT / 'ruff.toml').exists())
        self.assertIn('js.configs.recommended', (ROOT / 'eslint.config.mjs').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
