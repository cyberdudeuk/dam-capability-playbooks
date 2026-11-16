"""The asset governance explorer (explorer/) is the public edition of a working resource.

It is generated from a version that holds internal planning material, so these tests guard that nothing internal
reaches the published files, that the page keeps its Content Security Policy, and that it loads nothing from another
site. Each guard has a test showing it fails on a deliberate break. Browser behaviour is checked by B-19.
"""
import os
import re
import unittest
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ("index.html", "explorer.js", "explorer.css")
# Phrases that only appear in the internal working version, or must never be published
INTERNAL = re.compile(r"KIM Baseline|away day|check-in|working draft|Government Information Accountability|meeting notes|"
                      r"Purview pilot|DM Hub|Risk Baseline|Discoverability Platform|Data Management Team|\bOCDO\b|"
                      r"Office of the Chief Data Officer|OFFICIAL|claude\.ai/artifact|case against")
# The page's own guard patterns name the phrases they block; those two lines are the only allowed mention
GUARD_LINES = re.compile(r"add\('K(11|24)'|const forbidden=\[")


def read(name):
    with open(os.path.join(ROOT, "explorer", name), encoding="utf-8") as f:
        return f.read()


def internal_material(text):
    return sorted({m.group(0) for line in text.splitlines() if not GUARD_LINES.search(line) for m in INTERNAL.finditer(line)})


def csp_problems(html):
    m = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)"', html)
    if not m:
        return ["no Content Security Policy"]
    csp, out = m.group(1), []
    if "script-src 'self'" not in csp or re.search(r"script-src[^;]*unsafe-(inline|eval)", csp):
        out.append("scripts are not limited to this site")
    found = Inline()
    found.feed(html)
    if found.scripts:
        out.append("inline script")
    if found.handlers:
        out.append("inline event handler")
    return out


class Inline(HTMLParser):
    """Finds inline scripts and event handler attributes with a real HTML parser, so tag case and spacing do not matter
    (code scanning alert 54: a regular expression missed upper case SCRIPT tags)."""
    def __init__(self):
        super().__init__()
        self.scripts, self.handlers, self._in = 0, 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.handlers += sum(1 for k in a if k.startswith("on"))
        self._in = tag == "script" and not a.get("src")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in = False

    def handle_data(self, data):
        if self._in and data.strip():
            self.scripts += 1


def remote_loads(html):
    return re.findall(r'<(?:script|img|iframe)[^>]+src="(https?:|//)[^"]*"|<link(?![^>]*rel="(?:canonical|alternate)")[^>]+href="(?:https?:|//)[^"]*"', html)


class Explorer(unittest.TestCase):
    def test_no_internal_material_published(self):
        for name in FILES:
            self.assertEqual(internal_material(read(name)), [], name)

    def test_guard_catches_planted_material(self):
        self.assertEqual(internal_material("see the KIM Baseline"), ["KIM Baseline"])
        self.assertEqual(internal_material("<strong>OFFICIAL</strong>"), ["OFFICIAL"])

    def test_content_security_policy_holds(self):
        self.assertEqual(csp_problems(read("index.html")), [])

    def test_csp_guard_catches_breaks(self):
        good = read("index.html")
        self.assertIn("inline script", csp_problems(good.replace("</body>", "<script>alert(1)</script></body>")))
        self.assertIn("scripts are not limited to this site", csp_problems(good.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'")))
        self.assertIn("inline event handler", csp_problems(good.replace("<body>", '<body onload="x()">')))
        self.assertIn("inline script", csp_problems(good.replace("</body>", "<SCRIPT >alert(1)</SCRIPT ></body>")))
        self.assertIn("inline event handler", csp_problems(good.replace("<body>", '<body ONLOAD = "x()">')))

    def test_nothing_loaded_from_another_site(self):
        self.assertEqual(remote_loads(read("index.html")), [])
        self.assertTrue(remote_loads('<script src="https://cdn.example/x.js"></script>'))

    def test_version_matches_barcode(self):
        js, html = read("explorer.js"), read("index.html")
        v = re.search(r"const META=\{version:'([\d.]+)'", js).group(1)
        self.assertIn(f"AGE-{v}-PUB", html)


if __name__ == "__main__":
    unittest.main()
