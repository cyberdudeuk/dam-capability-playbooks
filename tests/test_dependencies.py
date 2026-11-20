"""Dependency manifests say one thing, once (defects D-058 and D-059).

D-058: package.json listed @eslint/js, axe-core and eslint twice with different versions. JSON parsers keep the last
value without warning, so the manifest read one way and installed another.
D-059: site_src/icons.json was drawn from lucide-static 1.69.0 while package.json pinned 1.73.0, so the vendored icons
no longer matched the dependency the runbook tells people to regenerate them from.
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def duplicate_keys(text):
    """Every key that appears more than once in any one JSON object."""
    found = []

    def hook(pairs):
        keys = [k for k, _ in pairs]
        found.extend(sorted({k for k in keys if keys.count(k) > 1}))
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return found


def icon_drift(icons_text, package_text):
    """A problem if the vendored icons were not drawn from the pinned lucide-static version."""
    vendored = json.loads(icons_text)["version"]
    pinned = json.loads(package_text)["devDependencies"]["lucide-static"]
    return [] if vendored == pinned else [f"icons.json is lucide-static {vendored}; package.json pins {pinned}"]


class Manifests(unittest.TestCase):
    def test_no_duplicate_keys(self):
        for name in ("package.json", "package-lock.json"):
            self.assertEqual(duplicate_keys(read(name)), [], name)

    def test_duplicate_keys_are_caught(self):
        # Negative test: the manifest before D-058 was fixed.
        broken = '{"devDependencies": {"eslint": "9.39.5", "globals": "17.14.0", "eslint": "10.15.0"}}'
        self.assertEqual(duplicate_keys(broken), ["eslint"])

    def test_icons_match_the_pinned_version(self):
        self.assertEqual(icon_drift(read("site_src", "icons.json"), read("package.json")), [])

    def test_icon_drift_is_caught(self):
        # Negative test: the state before D-059 was fixed.
        self.assertEqual(len(icon_drift('{"version": "1.69.0", "icons": {}}', '{"devDependencies": {"lucide-static": "1.73.0"}}')), 1)


if __name__ == "__main__":
    unittest.main()
