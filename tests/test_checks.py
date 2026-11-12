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
    shutil.copytree(ROOT / 'docs', repo / 'docs')
    shutil.copytree(ROOT / 'integrations', repo / 'integrations')
    shutil.copytree(ROOT / 'compass', repo / 'compass')
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


    def test_d019_one_server_error_is_not_broken(self):
        import health
        calls = []

        def flaky(url, timeout=20, accept=None):
            calls.append(url)
            if len(calls) == 1:
                raise health.urllib.error.HTTPError(url, 504, 'Gateway Timeout', {}, None)
            return 200, b''
        d = Path(tempfile.mkdtemp(prefix='dcp-h-'))
        (d / 'a.html').write_text('<a href="https://example.org/x">x</a>')
        orig, sleep = health.fetch, health.time.sleep
        health.fetch, health.time.sleep = flaky, (lambda s: None)
        try:
            rows = health.external_links(d)
        finally:
            health.fetch, health.time.sleep = orig, sleep
            shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(rows[0]['state'], 'ok', 'a single 504 followed by success must not be reported as broken (D-019)')

    def test_d019_persistent_server_error_is_unavailable_not_broken(self):
        import health
        def down(url, timeout=20, accept=None):
            raise health.urllib.error.HTTPError(url, 503, 'Service Unavailable', {}, None)
        d = Path(tempfile.mkdtemp(prefix='dcp-h-'))
        (d / 'a.html').write_text('<a href="https://example.org/y">y</a>')
        orig, sleep = health.fetch, health.time.sleep
        health.fetch, health.time.sleep = down, (lambda s: None)
        try:
            rows = health.external_links(d)
        finally:
            health.fetch, health.time.sleep = orig, sleep
            shutil.rmtree(d, ignore_errors=True)
        self.assertEqual(rows[0]['state'], 'unavailable')

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
        edit(y, 'DD-11: [RB-TNA, RB-TNARET]', 'DD-11: [RB-NOPE, RB-TNARET]')
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
        edit(self.r / 'CITATION.cff', 'version: 1.10.1', 'version: 1.3.9')
        self.fails('c23_repository_metadata')

    def test_c24_third_party_action(self):
        edit(self.r / '.github' / 'workflows' / 'codeql.yml', '    steps:\n', '    steps:\n      - uses: someone/some-action@3d3c42e5aac5ba805825da76410c181273ba90b1\n')
        self.fails('c24_actions_pinned')

    def test_c24_reviewed_action_at_another_commit(self):
        edit(self.r / '.github' / 'workflows' / 'scorecard.yml', 'ossf/scorecard-action@fa7117db83c52d787ae5a89f350999701505d78e', 'ossf/scorecard-action@0000000000000000000000000000000000000000')
        self.fails('c24_actions_pinned')

    def test_c24_reviewed_action_by_tag(self):
        edit(self.r / '.github' / 'workflows' / 'dependency-review.yml', 'actions/dependency-review-action@a1d282b36b6f3519aa1f3fc636f609c47dddb294', 'actions/dependency-review-action@v5')
        self.fails('c24_actions_pinned')

    def test_c24_unpinned_own_action(self):
        edit(self.r / '.github' / 'workflows' / 'codeql.yml', '    steps:\n', '    steps:\n      - uses: cyberdudeuk/some-action@v1\n')
        self.fails('c24_actions_pinned')

    def test_c25_unexpected_workflow(self):
        (self.r / '.github' / 'workflows' / 'jekyll-gh-pages.yml').write_text('name: x\non: push\njobs: {}\n', encoding='utf-8')
        self.fails('c25_workflow_inventory')

    def test_c25_publishes_repository_root(self):
        edit(self.r / '.github' / 'workflows' / 'release.yml', 'permissions:', '# source: ./\npermissions:')
        t = (self.r / '.github' / 'workflows' / 'release.yml').read_text()
        (self.r / '.github' / 'workflows' / 'release.yml').write_text(t.replace('# source: ./', 'env:\n  source: ./'), encoding='utf-8')
        self.fails('c25_workflow_inventory')

    def test_d019_status_page_hides_owner_account(self):
        import json as _json
        st = {'generated': 'x', 'today': '2026-11-05', 'review_date': '2027-02-05', 'review_due': False, 'healthy': False,
              'problems': ['Broken link: https://github.com/cyberdudeuk/dam-capability-playbooks/releases (404)'], 'sources': [], 'pages': [],
              'envelope_bytes': 1, 'links': [], 'anchors': []}
        (self.r / 'build').mkdir(exist_ok=True)
        site = build.Site(build.load(self.r / 'content' / 'playbooks.yaml'), self.s)
        site.status = st
        site.build()
        failed = check_site.run(self.s, self.r, only={'c17_no_personal_details'}, quiet=True)
        self.assertEqual(failed, {}, 'the Status page must not print the owner account name (D-019)')

    def test_d028_status_page_hides_owner_account_in_sister_links(self):
        st = {'generated': 'x', 'today': '2026-11-05', 'review_date': '2027-02-05', 'review_due': False, 'healthy': False,
              'problems': ['Broken link: https://cyberdudeuk.github.io/dq-commons/ecosystem.html (404)',
                           'Broken link: https://github.com/cyberdudeuk/github-repos-asset-catalogue/pull/9 (404)'],
              'sources': [], 'pages': [], 'envelope_bytes': 1, 'links': [], 'anchors': []}
        site = build.Site(build.load(self.r / 'content' / 'playbooks.yaml'), self.s)
        site.status = st
        site.build()
        failed = check_site.run(self.s, self.r, only={'c17_no_personal_details'}, quiet=True)
        self.assertEqual(failed, {}, 'the Status page must name sister portals by role, not by the owner account (D-028)')
        self.assertIn('site of the Public Sector Data Quality Commons, ecosystem.html', (self.s / 'status.html').read_text(encoding='utf-8'))

    def test_c26_unrelated_commit_identity(self):
        import subprocess
        g = ['git', '-C', str(self.r)]
        subprocess.run(g + ['init', '-q'], check=True)
        subprocess.run(g + ['add', 'README.md'], check=True)
        subprocess.run(g + ['-c', 'user.name=x', '-c', 'user.email=noreply' + chr(64) + 'users.noreply.github.com', 'commit', '-q', '-m', 'x'], check=True)
        self.fails('c26_commit_identity')

    def test_c27_register_out_of_date(self):
        t = (self.r / 'docs' / 'defect-register.md').read_text(encoding='utf-8')
        (self.r / 'docs' / 'defect-register.md').write_text(re.sub(r'^\| D-022 \|.*\n', '', t, flags=re.M), encoding='utf-8')
        self.fails('c27_registers_in_repository')

    def test_c27_register_back_on_portal(self):
        edit(self.s / 'about.html', '</main>', '<h2 id="defects">Defect register</h2></main>')
        self.fails('c27_registers_in_repository')

    def test_c27_checkpoint_back_on_portal(self):
        edit(self.s / 'about.html', '</main>', '<h2 id="checkpoint">Checkpoint</h2></main>')
        self.fails('c27_registers_in_repository')

    def test_c28_file_missing_from_catalogue(self):
        (self.s / 'data' / 'extra.csv').write_text('a\n1\n', encoding='utf-8')
        self.fails('c28_open_data_catalogue')

    def test_c28_page_without_catalogue_link(self):
        edit(self.s / 'library.html', 'href="data/catalogue.jsonld"', 'href="data/elsewhere.jsonld"')
        self.fails('c28_open_data_catalogue')

    def test_c28_dataset_without_licence(self):
        import json as _json
        p = self.s / 'data' / 'catalogue.jsonld'
        c = _json.loads(p.read_text(encoding='utf-8'))
        del c['dcat:dataset'][0]['dcterms:license']
        p.write_text(_json.dumps(c), encoding='utf-8')
        self.fails('c28_open_data_catalogue')

    def test_c29_unexplained_reference(self):
        edit(self.s / 'dam.html', '</main>', '<p>See OR-10.</p></main>')
        self.fails('c29_limitations_referenced')

    def test_c30_task_without_feedback_link(self):
        edit(self.s / 'test.html', 'template=testing.yml', 'template=other.yml')
        self.fails('c30_testing_pack')

    def test_c03_share_email_with_address(self):
        edit(self.s / 'dam.html', 'href="mailto:?', 'href="mailto:someone' + chr(64) + 'example.org?')
        self.fails('c03_links_resolve')

    def test_c03_tour_link_to_missing_tour(self):
        edit(self.s / 'guide.html', 'sectors.html#tour=sectors', 'sectors.html#tour=nosuchtour')
        self.fails('c03_links_resolve')

    def test_c31_page_without_share_menu(self):
        edit(self.s / 'library.html', '<details class="share">', '<details class="shared">')
        self.fails('c31_navigation_aids')

    def test_c31_page_missing_from_site_map(self):
        edit(self.s / 'site-map.html', 'href="tooling.html"', 'href="tooling-old.html"', count=99)
        self.fails('c31_navigation_aids')

    def test_c31_tour_step_points_at_nothing(self):
        edit(self.s / 'change.html', 'id="programme-roles"', 'id="programme-roles-x"')
        self.fails('c31_navigation_aids')

    def test_c31_llms_missing(self):
        (self.s / 'llms.txt').unlink()
        self.fails('c31_navigation_aids')

    def test_c32_mcp_version_mismatch(self):
        edit(self.r / 'integrations' / 'mcp' / 'server.py', "'version': '1.10.1'", "'version': '0.0.1'")
        self.fails('c32_mcp_server')

    def test_c32_mcp_tool_undescribed(self):
        edit(self.s / 'reuse.html', '<code>list_sector_rules</code>', '<code>list_rules</code>', count=99)
        self.fails('c32_mcp_server')

    def test_c33_rfi_question_dropped(self):
        edit(self.s / 'tooling.html', '<li id="RFI-07">', '<li id="RFI-7x">')
        self.fails('c33_tooling_and_feedback')

    def test_c33_rfi_csv_short(self):
        f = self.s / 'data' / 'interoperability-questions.csv'
        lines = f.read_text(encoding='utf-8').splitlines()
        f.write_text('\n'.join(lines[:-1]) + '\n', encoding='utf-8')
        self.fails('c33_tooling_and_feedback')

    def test_c33_private_feedback_missing(self):
        edit(self.s / 'contact.html', 'id="private-feedback"', 'id="feedback-x"')
        self.fails('c33_tooling_and_feedback')

    # Private form wiring (version 1.10.2): the form used to open blank from every page and task.
    def test_c33_private_form_page_not_filled_in(self):
        edit(self.s / 'governance.html', 'Data%20governance%20%28governance.html%29', 'Data%20governance', count=99)
        self.fails('c33_tooling_and_feedback')

    def test_c33_private_form_task_not_marked_as_task(self):
        f = self.s / 'test.html'
        h = f.read_text(encoding='utf-8')
        i = h.index('id="T-04"')
        f.write_text(h[:i] + h[i:].replace('%22Feedback%20on%20a%20test%20task%22', '%22A%20question%22', 1), encoding='utf-8')
        self.fails('c33_tooling_and_feedback')

    def test_c33_private_form_link_elsewhere(self):
        edit(self.s / 'quality.html', 'href="https://forms.cloud.microsoft/Pages/ResponsePage.aspx?id=', 'href="https://example.org/form?id=', count=99)
        self.fails('c33_tooling_and_feedback')

    def test_c33_private_form_bad_question_id(self):
        edit(self.r / 'content' / 'frameworks.yaml', 'where: r3660656614cc47b499a593f8ceb06013', 'where: question3')
        self.fails('c33_tooling_and_feedback')

    def test_c33_private_form_privacy_missing(self):
        edit(self.s / 'about.html', 'id="privacy-feedback-form"', 'id="privacy-x"')
        self.fails('c33_tooling_and_feedback')

    def test_build_rejects_unknown_private_form_topic(self):
        s = build.Site(build.load(self.r / 'content' / 'playbooks.yaml'), self.s)
        with self.assertRaises(build.ContentError):
            s.ms_form_link('x', 'not-a-topic')

    # Version 1.11.0: what the Project Compass pilot asked for (C-38).
    def test_c38_old_template_wording_returns(self):
        edit(self.s / 'quality.html', 'Blank structures to copy into your own tools.', 'Record roles, never named individuals or personal email addresses.')
        self.fails('c38_pilot_requirements')

    def test_c38_template_privacy_note_missing(self):
        edit(self.s / 'governance.html', 'id="template-privacy"', 'id="tp-x"')
        self.fails('c38_pilot_requirements')

    def test_c38_template_without_mode(self):
        edit(self.s / 'cataloguing.html', 'class="pill mode-bau"', 'class="pill"')
        self.fails('c38_pilot_requirements')

    def test_c38_template_download_missing(self):
        (self.s / 'data' / 'templates' / 'T-DQ-2.csv').unlink()
        self.fails('c38_pilot_requirements')

    def test_c38_workbook_mimetype_compressed(self):
        import zipfile
        f = self.s / 'data' / 'templates' / 'T-GOV-5.ods'
        with zipfile.ZipFile(f) as z:
            parts = [(i.filename, z.read(i.filename)) for i in z.infolist()]
        with zipfile.ZipFile(f, 'w', zipfile.ZIP_DEFLATED) as z:
            for n, b in parts:
                z.writestr(n, b)
        self.fails('c38_pilot_requirements')

    def test_c38_workbook_missing_tab(self):
        import zipfile
        f = self.s / 'data' / 'templates' / 'T-GOV-5.ods'
        with zipfile.ZipFile(f) as z:
            parts = [(i, z.read(i.filename)) for i in z.infolist()]
        with zipfile.ZipFile(f, 'w') as z:
            for i, b in parts:
                if i.filename == 'content.xml':
                    b = b.replace(b'table:name="Dependencies"', b'table:name="Deps"')
                z.writestr(i, b)
        self.fails('c38_pilot_requirements')

    def test_c38_dictionary_without_type(self):
        edit(self.s / 'knowledge.html', '<td class="c-sm">Period of time</td>', '<td class="c-sm"></td>')
        self.fails('c38_pilot_requirements')

    def test_c38_value_list_missing(self):
        edit(self.s / 'knowledge.html', 'id="vl-classification"', 'id="vl-x"')
        self.fails('c38_pilot_requirements')

    def test_c38_supplement_obligations_ungrouped(self):
        edit(self.s / 'sectors.html', 'class="ref-groups"', 'class="refs"')
        self.fails('c38_pilot_requirements')

    def test_build_rejects_stray_dictionary_key(self):
        edit(self.r / 'content' / 'playbooks.yaml', 'format: "Plain English, up to about 100 characters"', 'format: Plain English, up to about 100 characters')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_template_without_mode(self):
        edit(self.r / 'content' / 'playbooks.yaml', '{id: T-DQ-3, mode: BAU, ', '{id: T-DQ-3, ')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_workbook_tab_from_unknown_template(self):
        edit(self.r / 'content' / 'playbooks.yaml', '{name: Decisions, from: T-GOV-3}', '{name: Decisions, from: T-GOV-9}')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    # Version 1.12.0: backlog issues #18 to #22 (C-39) and D-034.
    def test_c39_architecture_supplement_missing(self):
        edit(self.s / 'sectors.html', 'id="SUP-ARC"', 'id="SUP-X"')
        self.fails('c39_backlog_18_22')

    def test_c39_diagram_drifts_from_list(self):
        edit(self.s / 'data' / 'templates' / 'T-CAT-4-example.mmd', 'APPOINTMENT }o--|| CASE : "is held for"', 'APPOINTMENT }o--|| PERSON : "is held for"')
        self.fails('c39_backlog_18_22')

    def test_c39_sharing_agreement_loses_gateway(self):
        edit(self.r / 'content' / 'playbooks.yaml', 'Lawful basis for each party, Legal gateway or power,', 'Lawful basis for each party,')
        self.fails('c39_backlog_18_22')

    def test_c39_retention_fields_removed(self):
        edit(self.r / 'content' / 'playbooks.yaml', 'Next review, Retention period, Disposal action]}', 'Next review]}')
        self.fails('c39_backlog_18_22')

    def test_c39_layer_missing_from_page(self):
        edit(self.s / 'governance.html', '<li class="layer layer-4">', '<li class="layer">')
        self.fails('c39_backlog_18_22')

    def test_c39_health_loses_section_251(self):
        edit(self.s / 'sectors.html', 'sets aside the duty of confidentiality', 'applies')
        self.fails('c39_backlog_18_22')

    def test_c39_health_loses_medical_device_step(self):
        edit(self.s / 'sectors.html', 'check whether it is a medical device', 'consider it')
        self.fails('c39_backlog_18_22')

    def test_c39_mvp_verdict_missing(self):
        edit(self.s / 'research.html', '<strong>After the MVP</strong>', '<strong>Pending</strong>')
        self.fails('c39_backlog_18_22')

    def test_build_rejects_unknown_dama_area(self):
        edit(self.r / 'content' / 'frameworks.yaml', 'dama: [DM-ARC, DM-MOD]', 'dama: [DM-XYZ]')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_split_template_field(self):
        edit(self.r / 'content' / 'playbooks.yaml', '"Ownership option (IAO, data owner or hybrid)"', 'Ownership option (IAO, data owner or hybrid)')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_unknown_layer_role(self):
        edit(self.r / 'content' / 'playbooks.yaml', '{n: 4, name: Custody and operation, roles: [CUS]', '{n: 4, name: Custody and operation, roles: [XYZ]')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_erd_relationship_to_unknown_entity(self):
        edit(self.r / 'content' / 'playbooks.yaml', 'to: PERSON, rel: "is about"', 'to: CLIENT, rel: "is about"')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_c34_related_link_to_other_site(self):
        f = self.s / 'quality.html'
        h = f.read_text(encoding='utf-8')
        i = h.index('<aside class="related"')
        f.write_text(h[:i] + h[i:].replace('href="https://cyberdudeuk.github.io/dq-commons/check.html"', 'href="https://example.org/check.html"', 1), encoding='utf-8')
        self.fails('c34_sister_portals')

    def test_c34_related_without_status(self):
        edit(self.s / 'tooling.html', '<span class="rel-status">Community project</span>', '<span class="rel-status"></span>', count=99)
        self.fails('c34_sister_portals')

    def test_c34_related_moved_into_a_tab(self):
        t = (self.s / 'tooling.html').read_text(encoding='utf-8')
        box = t[t.index('<aside class="related"'):t.index('</aside>') + 8]
        t = t.replace(box, '')
        i = t.index('<section role="tabpanel"')
        j = t.index('>', i) + 1
        (self.s / 'tooling.html').write_text(t[:j] + box + t[j:], encoding='utf-8')
        self.fails('c34_sister_portals')

    def test_c34_xref_points_at_missing_anchor(self):
        edit(self.s / 'data' / 'xref.json', 'dam.html#DAM-R01"', 'dam.html#DAM-R99"')
        self.fails('c34_sister_portals')

    def test_build_rejects_related_on_unknown_page(self):
        y = self.r / 'content' / 'frameworks.yaml'
        edit(y, '  placements:\n    quality:', '  placements:\n    qualityx:')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_c35_compass_can_call_network(self):
        edit(self.s / 'compass' / 'index.html', "default-src 'none';", "default-src 'none'; connect-src https:;")
        self.fails('c35_estate_compass')

    def test_c35_compass_link_outside_portals(self):
        edit(self.s / 'compass' / 'index.html', '"https://cyberdudeuk.github.io/dq-commons/check.html"', '"https://example.org/check.html"', count=99)
        self.fails('c35_estate_compass')

    def test_c35_compass_link_to_missing_anchor(self):
        edit(self.s / 'compass' / 'index.html', 'dam.html#requirements', 'dam.html#requirementz', count=99)
        self.fails('c35_estate_compass')

    def test_c35_compass_stores_raw_form_value(self):
        # CodeQL js/xss-through-dom (PR 11): the change handler must not store e.target.value as it is
        edit(self.s / 'compass' / 'index.html', 'const v=q&&opt(q.id,e.target.value);if(!v)return;ans[q.id]=v;', 'ans[e.target.name]=e.target.value;')
        self.fails('c35_estate_compass')

    def test_c35_compass_escape_misses_apostrophe(self):
        edit(self.s / 'compass' / 'index.html', ",\"'\":'&#39;'", '')
        self.fails('c35_estate_compass')

    def test_c35_compass_without_colophon(self):
        edit(self.s / 'compass' / 'index.html', 'aria-label="QR code linking to', 'aria-label="Picture of')
        self.fails('c35_estate_compass')

    def test_build_rejects_compass_route_in_one_portal(self):
        y = self.r / 'compass' / 'compass.yaml'
        t = y.read_text(encoding='utf-8')
        i = t.index('  estate:')
        j = t.index('  learn:', i)
        y.write_text(t[:i] + t[i:j].replace('{p: dam,', '{p: cat,').replace('{p: dqc,', '{p: cat,') + t[j:], encoding='utf-8')
        sys.path.insert(0, str(self.r / 'tools'))
        import importlib, compass
        compass.SRC = self.r / 'compass'
        try:
            errs = compass.validate(compass.load(), build.load(self.r / 'content' / 'playbooks.yaml'))
        finally:
            compass.SRC = ROOT / 'compass'
        self.assertTrue(any('stays in one portal' in e for e in errs), errs)

    def test_build_rejects_unknown_tool_standard(self):
        y = self.r / 'content' / 'frameworks.yaml'
        edit(y, '    standards: [RB-OLINEAGE, RB-PROVO]', '    standards: [RB-OLINEAGE, RB-NOPE]')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_lens_without_capability_actions(self):
        y = self.r / 'content' / 'frameworks.yaml'
        t = y.read_text(encoding='utf-8')
        i = t.index('id: L-CYBER')
        j = t.index('      dq:', i)
        y.write_text(t[:j] + '      dx:' + t[j + len('      dq:'):], encoding='utf-8')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_role_without_icon(self):
        y = self.r / 'content' / 'playbooks.yaml'
        edit(y, '- {code: SRO, name: Senior responsible owner,', '- {code: XRO, name: Senior responsible owner,')
        with self.assertRaises(build.ContentError):
            build.load(y)

    def test_build_rejects_wheel_area_missing_a_role(self):
        y = self.r / 'content' / 'frameworks.yaml'
        t = y.read_text(encoding='utf-8')
        i = t.index('id: DM-ARC')
        j = t.index('      prg:', i)
        y.write_text(t[:j] + '      zzz:' + t[j + len('      prg:'):], encoding='utf-8')
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

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

    # -- version 1.9: Have your say (C-36) ------------------------------------------------------
    def test_c36_signup_goes_to_github(self):
        edit(self.s / 'research.html', '<p>The form asks for:</p>', '<p><a class="btn" href="https://github.com/cyberdudeuk/dam-capability-playbooks/issues/new">Sign up to take part</a></p><p>The form asks for:</p>')
        self.fails('c36_have_your_say')

    def test_c36_idea_link_to_another_repository(self):
        edit(self.s / 'research.html', 'dam-capability-playbooks/discussions/new?category=ideas', 'someone-else/discussions/new?category=ideas', count=99)
        self.fails('c36_have_your_say')

    def test_c36_published_score_wrong(self):
        import json
        p = self.s / 'data' / 'backlog.json'
        j = json.loads(p.read_text(encoding='utf-8'))
        j['items'][0]['score'] += 1
        p.write_text(json.dumps(j), encoding='utf-8')
        self.fails('c36_have_your_say')

    def test_c36_table_score_wrong(self):
        t = (self.s / 'research.html').read_text(encoding='utf-8')
        i = t.index('id="bl-BL-12"')
        j = t.index('<td class="c-xs">77</td>', i)
        (self.s / 'research.html').write_text(t[:j] + '<td class="c-xs">97</td>' + t[j + len('<td class="c-xs">77</td>'):], encoding='utf-8')
        self.fails('c36_have_your_say')

    def test_c36_now_over_limit(self):
        t = (self.s / 'research.html').read_text(encoding='utf-8')
        i = t.index('<section class="rm-col rm-now"')
        a = t.index('<li class="cr-card rm-card"', i)
        b = t.index('</li>', a) + 5
        (self.s / 'research.html').write_text(t[:b] + t[a:b] * 3 + t[b:], encoding='utf-8')
        self.fails('c36_have_your_say')

    def test_c36_placed_against_score_without_decision(self):
        edit(self.s / 'research.html', 'id="decision-BL-11"', 'id="decision-gone"')
        self.fails('c36_have_your_say')

    def test_c36_unpublished_strategy_not_labelled(self):
        edit(self.s / 'research.html', 'Not yet published: unconfirmed', 'Not yet published')
        self.fails('c36_have_your_say')

    def test_c36_address_in_backlog(self):
        p = self.s / 'data' / 'backlog.csv'
        p.write_text(p.read_text(encoding='utf-8') + 'BL-99,x,feature,mail team' + chr(64) + 'example.gov.uk,,,,,,0,later,0,0,0,0,0,0,0\n', encoding='utf-8')
        self.fails('c36_have_your_say')

    def test_c36_page_without_have_your_say(self):
        edit(self.s / 'learning.html', 'href="research.html"', 'href="index.html"', count=99)
        self.fails('c36_have_your_say')

    def _rejects(self, old, new, count=1):
        edit(self.r / 'content' / 'frameworks.yaml', old, new, count)
        with self.assertRaises(build.ContentError):
            build.load(self.r / 'content' / 'playbooks.yaml')

    def test_build_rejects_weights_not_100(self):
        self._rejects('name: User demand, weight: 25', 'name: User demand, weight: 30')

    def test_build_rejects_signup_on_github(self):
        self._rejects("  signup:\n    url: ''", "  signup:\n    url: 'https://github.com/cyberdudeuk/dam-capability-playbooks/issues/new'")

    def test_build_rejects_status_against_score_without_decision(self):
        self._rejects("item: BL-11, decision:", "item: BL-12, decision:")

    def test_build_rejects_now_over_limit(self):
        self._rejects('wip_limit: 5', 'wip_limit: 2')

    def test_build_rejects_unknown_open_register_source(self):
        self._rejects('source: OR-15,', 'source: OR-95,')

    def test_c28_d030_data_page_missing_download(self):
        edit(self.s / 'data.html', 'href="data/backlog.csv"', 'href="data/backlogx.csv"', count=99)
        self.fails('c28_open_data_catalogue')

    # -- version 1.10: involvement and reuse (C-37) -------------------------------------------------
    def test_c37_d031_backticks_on_whats_new(self):
        edit(self.s / 'whats-new.html', '<code>', '`', count=99)
        self.fails('c37_involvement_and_reuse')

    def test_c37_body_without_source(self):
        edit(self.s / 'bodies.html', 'href="https://www.gov.uk/government/groups/open-standards-board" rel="noopener"', 'href="#" rel="noopener"')
        self.fails('c37_involvement_and_reuse')

    def test_c37_missing_badge_png(self):
        (self.s / 'badges' / 'champion.png').unlink()
        self.fails('c37_involvement_and_reuse')

    def test_c37_broken_badge_svg(self):
        edit(self.s / 'badges' / 'tester.svg', '</svg>', '')
        self.fails('c37_involvement_and_reuse')

    def test_c37_missing_toolkit_template(self):
        edit(self.s / 'involve.html', 'id="TK-SLACK-text"', 'id="TK-GONE-text"')
        self.fails('c37_involvement_and_reuse')

    def test_c37_missing_embed(self):
        (self.s / 'embed' / 'DAM-R03.html').unlink()
        self.fails('c37_involvement_and_reuse')

    def test_c37_embed_links_nowhere(self):
        edit(self.s / 'embed' / 'CR-01.html', 'capability-model.html#CR-01', 'capability-model.html#CR-99')
        self.fails('c37_involvement_and_reuse')

    def test_c37_feed_without_current_version(self):
        import yaml
        v = yaml.safe_load((self.r / 'content' / 'playbooks.yaml').read_text(encoding='utf-8'))['meta']['version']
        edit(self.s / 'feed.xml', f'<title>Release {v}</title>', '<title>Release 0.0.0</title>')
        self.fails('c37_involvement_and_reuse')

    def test_c37_lineage_does_not_parse(self):
        p = self.s / 'data' / 'lineage.ttl'
        p.write_text(p.read_text(encoding='utf-8') + '\nthis is not turtle <\n', encoding='utf-8')
        self.fails('c37_involvement_and_reuse')

    def test_c37_offline_copy_incomplete(self):
        import zipfile
        z = self.s / 'dam-playbooks-offline.zip'
        with zipfile.ZipFile(z) as src:
            keep = [(n, src.read(n)) for n in src.namelist() if not n.endswith('/tooling.html')]
        with zipfile.ZipFile(z, 'w') as dst:
            for n, b in keep:
                dst.writestr(n, b)
        self.fails('c37_involvement_and_reuse')

    def test_c37_capability_without_flag_check(self):
        edit(self.s / 'capability-model.html', 'capability=CR-05&', 'capability=XX-05&')
        self.fails('c37_involvement_and_reuse')

    def test_c37_page_without_level(self):
        edit(self.s / 'quality.html', 'class="level-tag', 'class="lvl-gone')
        self.fails('c37_involvement_and_reuse')

    def test_c37_address_in_toolkit(self):
        edit(self.s / 'involve.html', '[Your name]', 'team' + chr(64) + 'example.gov.uk')
        self.fails('c37_involvement_and_reuse')

    def test_build_rejects_email_in_toolkit(self):
        self._rejects('      [Your name]\n  - id: TK-TEAMS', '      mail us at a' + chr(64) + 'b.gov.uk\n  - id: TK-TEAMS')

    def test_build_rejects_unknown_badge_on_route(self):
        self._rejects('badge: explorer}', 'badge: wizard}')

    def test_build_rejects_body_without_terms_status(self):
        self._rejects('    tor: Terms of reference not found published on GOV.UK.\n', "    tor: ''\n")


class IdeasRun(unittest.TestCase):
    """Version 1.9: tools/ideas.py keeps only Ideas, drops any title with an address, counts votes, and never fails the build."""
    def test_filters_and_counts(self):
        import ideas
        repo = 'cyberdudeuk/dam-capability-playbooks'
        base = f'https://github.com/{repo}/discussions/'
        batch = [{'number': 1, 'title': 'Embed tables', 'html_url': base + '1', 'category': {'slug': 'ideas'}, 'upvote_count': 4, 'reactions': {'+1': 2}, 'comments': 1},
                 {'number': 2, 'title': 'Contact me at a' + chr(64) + 'b.gov.uk', 'html_url': base + '2', 'category': {'slug': 'ideas'}, 'upvote_count': 9},
                 {'number': 3, 'title': 'A question', 'html_url': base + '3', 'category': {'slug': 'q-a'}, 'upvote_count': 9},
                 {'number': 4, 'title': 'Welsh', 'html_url': base + '4', 'category': {'slug': 'ideas'}, 'reactions': {'+1': 7}},
                 {'number': 5, 'title': 'Elsewhere', 'html_url': 'https://github.com/other/repo/discussions/5', 'category': {'slug': 'ideas'}}]
        got = ideas.collect(repo, '', fetch=lambda url, tok: batch if 'page=1' in url else [])
        self.assertEqual([i['n'] for i in got], [4, 1])
        self.assertEqual(got[0]['votes'], 7)

    def test_fails_soft(self):
        import ideas
        out = Path(tempfile.mkdtemp(prefix='dcp-i-')) / 'ideas.json'

        def boom(url, token):
            raise ideas.urllib.error.URLError('offline')
        orig = ideas.get
        ideas.get = boom
        try:
            self.assertEqual(ideas.main(['--out', str(out)]), 0)
        finally:
            ideas.get = orig
        import json
        self.assertFalse(json.loads(out.read_text())['available'])


class IconVendoring(unittest.TestCase):
    """D-029: every icon the site uses is in the vendor list, so re-vendoring never drops one."""
    def test_vendor_list_covers_icon_set(self):
        import vendor_icons
        missing = set(build.ICON_SET) - set(vendor_icons.ICON_NAMES)
        self.assertFalse(missing, f'icons not in tools/vendor_icons.py ICON_NAMES: {sorted(missing)}')


class BreakScripts(unittest.TestCase):
    """D-027: every deliberate-break script runs on every page, so it must not throw where its target is absent."""
    def test_break_scripts_are_null_safe(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright not installed')
        import check_browser
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.set_content('<!DOCTYPE html><html><body><p>No portal objects here.</p></body></html>')
            bad = []
            for name, (_, js) in check_browser.BREAKS.items():
                if not js:
                    continue
                try:
                    pg.evaluate(js)
                except Exception as e:
                    bad.append(f'{name}: {str(e).splitlines()[0]}')
            b.close()
        self.assertEqual(bad, [], 'break scripts must do nothing where their target is absent (D-027)')

    def test_null_safety_test_catches_unsafe_script(self):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.set_content('<!DOCTYPE html><html><body></body></html>')
            with self.assertRaises(Exception):
                pg.evaluate("window.DCP_INDEX.length = 0;")
            b.close()


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
