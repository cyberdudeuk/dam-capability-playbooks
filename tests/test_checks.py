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
    for f in ('playbooks.yaml', 'frameworks.yaml', 'source-anchors.json'):
        shutil.copy(ROOT / 'content' / f, repo / 'content' / f)
    for f in ('README.md', 'LICENSE', 'CITATION.cff'):
        shutil.copy(ROOT / f, repo / f)
    shutil.copytree(ROOT / '.github', repo / '.github')
    site = repo / 'site'
    build.Site(build.load(repo / 'content' / 'playbooks.yaml'), site).build()
    return tmp, repo, site


def edit(path, old, new, count=1):
    t = path.read_text(encoding='utf-8')
    assert old in t, f'break target not found in {path.name}: {old[:60]}'
    path.write_text(t.replace(old, new, count), encoding='utf-8')


class HealthRun(unittest.TestCase):
    def test_d013_links_request_html(self):
        import health
        seen = {}

        class Fake:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b''

        def fake_urlopen(req, timeout=0):
            seen['accept'] = req.get_header('Accept')
            return Fake()
        orig = health.urllib.request.urlopen
        health.urllib.request.urlopen = fake_urlopen
        try:
            health.fetch('https://www.gov.uk/government/organisations/example')
        finally:
            health.urllib.request.urlopen = orig
        self.assertTrue(seen['accept'].startswith('text/html'), 'page checks must ask for HTML first (D-013)')


    def test_hl02_missing_anchor_is_reported(self):
        import json as _json
        import health
        import yaml
        d = yaml.safe_load((ROOT / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))
        orig = health.fetch
        health.fetch = lambda url, timeout=20, accept=None: (200, _json.dumps({'details': {'body': '<h2 id="something-else">x</h2>'}}).encode())
        try:
            rows = health.check_anchors(d)
        finally:
            health.fetch = orig
        self.assertTrue(rows and all(r['missing'] for r in rows), 'a page without the signposted sections must be reported (HL-02)')


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

    def test_c19_missing_citation(self):
        t = (self.s / 'notices.html').read_text(encoding='utf-8')
        t = re.sub(r'<li id="cite-RB-DUAA">.*?</li>', '', t, flags=re.S)
        (self.s / 'notices.html').write_text(t, encoding='utf-8')
        self.fails('c19_citations')

    def test_c19_missing_attribution(self):
        edit(self.s / 'notices.html', 'Contains public sector information', 'Contains information', 3)
        self.fails('c19_citations')

    def test_c20_missing_page_meta(self):
        edit(self.s / 'quality.html', 'class="page-meta"', 'class="x"')
        self.fails('c20_page_governance')

    def test_c20_expired_security_txt(self):
        p = self.s / '.well-known' / 'security.txt'
        p.write_text(re.sub(r'Expires: \S+', 'Expires: 2020-01-01T00:00:00.000Z', p.read_text()))
        self.fails('c20_page_governance')

    def test_build_rejects_unknown_rulebook_ref(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, 'DD-11: [RB-TNA]', 'DD-11: [RB-NOPE]')
        with self.assertRaises(build.ContentError):
            build.load(y)

    def test_build_rejects_unknown_check_in_trace(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, 'checks: [C-03, C-08]}', 'checks: [C-99]}')
        with self.assertRaises(build.ContentError):
            build.load(y)

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

    # version 1.4
    def test_c21_framework_text_copied(self):
        edit(self.s / 'capability-model.html', '</main>', '<p>Makes data available by default only to a single specialist person or team.</p></main>')
        self.fails('c21_no_restricted_licence_text')

    def test_c22_unverified_anchor(self):
        edit(self.s / 'capability-model.html', '#data-ownership"', '#data-owners-old-section"')
        self.fails('c22_signposts_verified')

    def test_c22_missing_flag(self):
        t = (self.s / 'capability-model.html').read_text(encoding='utf-8')
        i = t.index('<li class="cr-card" id="CR-05"')
        j = t.index('class="flag-badge', i)
        (self.s / 'capability-model.html').write_text(t[:j] + 'class="no-badge' + t[j + len('class="flag-badge'):], encoding='utf-8')
        self.fails('c22_signposts_verified')

    def test_c23_blank_citation(self):
        (self.r / 'CITATION.cff').write_text('', encoding='utf-8')
        self.fails('c23_repository_metadata')

    def test_c23_citation_version_drift(self):
        edit(self.r / 'CITATION.cff', 'version: 1.4.0', 'version: 1.3.9')
        self.fails('c23_repository_metadata')

    def test_c24_unpinned_action(self):
        edit(self.r / '.github' / 'workflows' / 'codeql.yml', 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1', 'actions/checkout@v7')
        self.fails('c24_actions_pinned')

    def test_build_rejects_unverified_signpost(self):
        y = self.r / 'content' / 'frameworks.yaml'
        edit(y, 'a: identify-your-critical-data-assets', 'a: identify-your-critical-data-assets-v2')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_explicit_without_clause(self):
        y = self.r / 'content' / 'frameworks.yaml'
        edit(y, "  flag: E\n  dam: data-ownership", "  flag: E\n  dam: null")
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_unknown_skill(self):
        y = self.r / 'content' / 'frameworks.yaml'
        edit(y, '  - data-maturity\n', '  - data-wizardry\n')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')


class SectorRulesRun(unittest.TestCase):
    """T-VAL: every generated sector rule file is valid for, and runs in, the Data Quality Commons kit (dqkit)."""
    def test_rule_files_validate_and_run(self):
        import os
        extra = os.environ.get('DQKIT_PATH')
        if extra:
            sys.path.insert(0, extra)
        try:
            import pandas as pd
            from dqkit import rules as dq
        except ImportError:
            self.skipTest('dqkit not available; CI installs it from a pinned commit')
        import yaml
        files = sorted((ROOT / 'site' / 'data' / 'rules').glob('*.yaml'))
        self.assertTrue(files, 'no generated rule files; run tools/build.py first')
        for f in files:
            spec = yaml.safe_load(f.read_text(encoding='utf-8'))
            dq.validate_spec(spec)
        spec = yaml.safe_load((ROOT / 'site' / 'data' / 'rules' / 'sup-hlt.yaml').read_text(encoding='utf-8'))
        cols = {r['column'] for r in spec['rules'] if 'column' in r}
        df = pd.DataFrame({c: ['x'] for c in cols})
        res = dq.run(df, spec)
        self.assertTrue(res, 'dqkit returned no result')


if __name__ == '__main__':
    unittest.main()
