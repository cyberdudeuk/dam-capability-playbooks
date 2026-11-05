"""Vaccination tests (VER-05): every static check must fail on a deliberate break before it is trusted.

Run: python -m unittest discover -s tests
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'tools'))
import build  # noqa: E402
import check_site  # noqa: E402


def fresh():
    tmp = Path(tempfile.mkdtemp(prefix='dcp-'))
    repo = tmp / 'repo'
    (repo / 'content').mkdir(parents=True)
    shutil.copy(ROOT / 'content' / 'playbooks.yaml', repo / 'content' / 'playbooks.yaml')
    for f in ('README.md', 'LICENSE', 'CITATION.cff'):
        shutil.copy(ROOT / f, repo / f)
    site = repo / 'site'
    build.Site(build.load(repo / 'content' / 'playbooks.yaml'), site).build()
    return tmp, repo, site


def edit(path, old, new, count=1):
    t = path.read_text(encoding='utf-8')
    assert old in t, f'break target not found in {path.name}: {old[:60]}'
    path.write_text(t.replace(old, new, count), encoding='utf-8')


class Vaccination(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.repo, cls.site = fresh()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='dcp-case-'))
        shutil.copytree(self.repo, self.work / 'repo')
        self.r = self.work / 'repo'
        self.s = self.r / 'site'

    def tearDown(self):
        shutil.rmtree(self.work, ignore_errors=True)

    def fails(self, name):
        failed = check_site.run(self.s, self.r, only={name}, quiet=True)
        self.assertIn(name, failed, f'{name} did not catch the deliberate break')

    def test_clean_build_passes(self):
        self.assertEqual(check_site.run(self.s, self.r, quiet=True), {})

    def test_c01_skip_link_moved(self):
        edit(self.s / 'index.html', '<a class="skip" href="#main">Skip to main content</a>', '')
        self.fails('c01_page_basics')

    def test_c02_duplicate_id(self):
        edit(self.s / 'dam.html', 'id="timeline"', 'id="requirements"')
        self.fails('c02_unique_ids')

    def test_c03_broken_anchor(self):
        edit(self.s / 'index.html', 'href="dam.html"', 'href="dam.html#no-such-anchor"')
        self.fails('c03_links_resolve')

    def test_c04_email_in_page(self):
        edit(self.s / 'about.html', '<h1>', '<p>team' + '@' + 'dsit.gov.uk</p><h1>')
        self.fails('c04_no_email')

    def test_c04_email_in_content(self):
        edit(self.r / 'content' / 'playbooks.yaml', 'contact_note: >-', 'contact_note: >-\n    write to someone' + '@' + 'gov.uk')
        self.fails('c04_no_email')

    def test_c05_cdn_script(self):
        edit(self.s / 'index.html', '<script src="assets/app.js"></script>', '<script src="https://cdn.example.net/x.js"></script>')
        self.fails('c05_no_external_assets')

    def test_c06_wrong_dqap(self):
        edit(self.s / 'quality.html', '<h1>', '<h1>Data Quality Assur' + 'ance Plan ')
        self.fails('c06_dqap_expansion')

    def test_c07_annex(self):
        edit(self.s / 'dam.html', '<h1>', '<h1>Annex' + ' A ')
        self.fails('c07_no_annex_a')

    def test_c08_missing_provenance(self):
        t = (self.s / 'dam.html').read_text(encoding='utf-8')
        head, body = t.split('<tbody id="req-table">', 1)
        body = body.replace('class="prov V"', 'class="x"', 1)
        (self.s / 'dam.html').write_text(head + '<tbody id="req-table">' + body, encoding='utf-8')
        self.fails('c08_provenance_on_requirements')

    def test_c09_deck_committed(self):
        (self.r / 'showcase.pptx').write_bytes(b'PK')
        self.fails('c09_no_decks_or_films')

    def test_c10_uncaptioned_table(self):
        edit(self.s / 'dam.html', '<caption id="t-reqs">', '<caption id="t-reqs" hidden>')
        edit(self.s / 'dam.html', '<caption id="t-reqs" hidden>', '<span id="t-reqs">')
        self.fails('c10_tables')

    def test_c11_bad_jsonld(self):
        edit(self.s / 'index.html', '<script type="application/ld+json">{', '<script type="application/ld+json">{,')
        self.fails('c11_machine_readable')

    def test_c12_inline_style(self):
        edit(self.s / 'index.html', '<main id="main"', '<main style="color:red" id="main"')
        self.fails('c12_csp_clean')

    def test_c13_unnamed_qr(self):
        t = (self.s / 'index.html').read_text(encoding='utf-8')
        i = t.index('aria-label="QR code')
        j = t.index('"', i + len('aria-label="'))
        (self.s / 'index.html').write_text(t[:i] + 'aria-label=""' + t[j + 1:], encoding='utf-8')
        self.fails('c13_accessible_graphics')

    def test_c14_footer_without_form(self):
        t = (self.s / 'library.html').read_text(encoding='utf-8')
        head, foot = t.split('id="colophon"', 1)
        (self.s / 'library.html').write_text(head + 'id="colophon"' + foot.replace('contact form', 'contact us'), encoding='utf-8')
        self.fails('c14_colophon_and_contact')

    def test_c15_placeholder(self):
        edit(self.s / 'about.html', '<h1>', '<h1>TODO ')
        self.fails('c15_no_placeholders')

    def test_c16_missing_canonical(self):
        t = (self.s / 'learning.html').read_text(encoding='utf-8')
        t = re.sub(r'<link rel="canonical"[^>]*>', '', t)
        (self.s / 'learning.html').write_text(t, encoding='utf-8')
        self.fails('c16_search_engines')

    def test_c16_missing_favicon(self):
        (self.s / 'assets' / 'og-image.png').unlink()
        self.fails('c16_search_engines')

    def test_c17_name_in_page(self):
        edit(self.s / 'about.html', '<h1>', '<h1>Written by Eman' + 'uel ')
        self.fails('c17_no_personal_details')

    def test_c17_team_in_readme(self):
        (self.r / 'README.md').write_text('Contact the Data Manage' + 'ment Team. Author: Sil' + 'va')
        self.fails('c17_no_personal_details')

    def test_c18_avoid_words(self):
        edit(self.s / 'library.html', '<h1>', '<h1>Click ' + 'here ')
        self.fails('c18_plain_english')

    def test_build_rejects_comma_split(self):
        y = self.r / 'content' / 'playbooks.yaml'
        t = y.read_text(encoding='utf-8')
        t = t.replace('"Set up a decision log and an exception register"', 'Set up a decision log, logs')
        y.write_text(t, encoding='utf-8')
        with self.assertRaises(build.ContentError):
            build.load(y)

    def test_build_rejects_service_owner_in_method(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, '{level: High, who: Data owner,', '{level: High, who: Service owner,')
        with self.assertRaises(build.ContentError):
            build.load(y)

    def test_build_rejects_missing_accountable(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, 'raci: {CDO: A, COO: R, CAT: R, STW: C, OWN: C, USR: C}', 'raci: {CDO: R, COO: R, CAT: R, STW: C, OWN: C, USR: C}')
        with self.assertRaises(build.ContentError):
            build.load(y)

    def test_build_rejects_unknown_requirement(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, 'reqs: [DAM-R08, DAM-R14]', 'reqs: [DAM-R08, DAM-R99]')
        with self.assertRaises(build.ContentError):
            build.load(y)


if __name__ == '__main__':
    unittest.main()
