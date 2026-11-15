"""D-048: code scanning found host checks done by substring, and a contact form that would follow any target.
These tests keep the whole-host comparisons and the issue-form allow-list (CodeQL #1, #2, #22 to #24)."""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Hosts(unittest.TestCase):
    def test_no_substring_host_tests_remain(self):
        for f in ('tools/build.py', 'tools/check_site.py'):
            s = (ROOT / f).read_text(encoding='utf-8')
            self.assertNotRegex(s, r"'github\.(com|io)/?' in ", f)
            self.assertNotRegex(s, r"'\.github\.io/' in ", f)

    def test_contact_form_follows_only_an_issue_form(self):
        js = (ROOT / 'site_src' / 'app.js').read_text(encoding='utf-8')
        m = re.search(r"if \(!(/\^https:.*?\$/)\.test\(target\)\) return;", js)
        self.assertTrue(m, 'the allow-list guard is missing')
        cases = ['https://github.com/cyberdudeuk/dam-capability-playbooks/issues/new', 'https://evil.example/issues/new',
                 'javascript:alert(1)', 'https://github.com.evil.example/a/b/issues/new', '']
        out = subprocess.run(['node', '-e', f'const r={m.group(1)};console.log(JSON.stringify({cases!r}.map(t=>r.test(t))))'],
                             capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual('[true,false,false,false,false]', out)


if __name__ == '__main__':
    unittest.main()
