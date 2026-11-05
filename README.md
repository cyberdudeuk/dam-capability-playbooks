# Data Asset Management (DAM) capability playbooks

Step-by-step guidance on data governance, data cataloguing and data quality for critical data assets in UK government,
with the [data asset management policy in government](https://www.gov.uk/government/publications/data-asset-management-policy-in-government)
as the spine.

**Use it:** https://cyberdudeuk.github.io/dam-capability-playbooks/

**Status:** prototype. Not an official GOV.UK service or published guidance. Where it repeats GDS guidance, the GOV.UK page is
the authority. Content under the [Open Government Licence v3.0](docs/CONTENT-LICENCE.md); code under the [MIT licence](LICENSE);
icons from Lucide (ISC, see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)).

## Who it is for

Chief data officers, lead policy coordinators, data owners, data stewards, catalogue managers and data quality leads in
UK government departments and arm's length bodies. It is more detailed than GOV.UK guidance and written for specialists.

## What is in it

| Page | What it gives you |
|---|---|
| The policy | Every requirement, its strength and source, and the step that meets it |
| Governance, Cataloguing, Quality | Step-by-step methods with progress tracking, roles, templates, measures, escalation and sector depth |
| Joined up | Hand-offs between the three, one set of roles, one yearly cycle |
| Your role | Routes for six roles across learn, prepare, do, report and improve |
| Learning | Modules with outcomes, activities and checks of understanding |
| Library | All material, templates, an assessment of where sector-specific content is needed, and open data |
| Knowledge | Glossary, thesaurus, taxonomy, knowledge graph and data dictionary |
| Inclusion | Equality, inclusion and accessibility checks for each capability |
| Status, What's new, About | Health run results, release notes, findings, open and defect registers, build standard assessment |
| Service design | Theory of change, research plan, blueprint, requirements traceability, architecture, Service Standard self-assessment |
| Notices, Accessibility | Disclaimers, credits, full citations and the accessibility statement |

## How the repository supports the portal

| Portal feature | GitHub feature |
|---|---|
| Contact form | Issue forms (`.github/ISSUE_TEMPLATE`) |
| Report a problem with this page | Pre-filled issue form |
| Suggest a change, change history | Edit and commit history of `content/playbooks.yaml` |
| Ask the community | Discussions |
| Status page | Weekly scheduled workflow; failures open an issue labelled `health` |
| What's new | `CHANGELOG.md` and tag-triggered releases |
| Hosting | GitHub Pages, deployed by Actions from `main` |
| Security | CodeQL, Dependabot, secret scanning, private vulnerability reporting |

Nothing in the portal depends on any service other than GitHub and GitHub Pages.

## How it is built

- `content/playbooks.yaml` is the single source of truth; `tools/build.py` generates `site/` from it and refuses to build on a broken reference.
- `tools/check_site.py` (static checks) and `tools/check_browser.py` (real-browser checks) run on every change. `tests/` proves each check fails on a deliberate break.
- `tools/health.py` checks sources, the review date and page weight. It never changes content.

```
pip install -r requirements.txt && npm ci && python -m playwright install chromium
python tools/build.py
python -m unittest discover -s tests
python tools/check_site.py
python tools/check_browser.py
python tools/health.py
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for routine operations and [CONTRIBUTING.md](CONTRIBUTING.md) to propose a change.
