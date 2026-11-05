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
| Sectors | Supplements for health, social care, geospatial, statistics, sharing, AI and more, with a finder and quality rules the Data Quality Commons kit can run |
| Delivery and change | Embedding the policy in business as usual and in programmes: business cases, spend control, assurance, legacy exits, contracts, handover and benefits |
| Joined up | Hand-offs between the three, one set of roles, one yearly cycle |
| Capability model | A DAMA-DMBOK wheel view with role guidance and the records life cycle alongside; 32 capabilities the policy and adjacent guidance need, each flagged explicit, implicit or inferred with signposts to the exact section; the government data maturity model; a self-assessment; crosswalks to industry models |
| Working together | Ten recommendations for join-up between data, records, security, digital, technology, analysis, commercial and delivery professionals; communities to join; who contributes to what |
| Perspectives | The policy through data, digital, cyber, technology, commercial and legacy lenses, with a coverage assessment |
| Tools and interoperability | Nine kinds of data management tool mapped to DAMA areas, the open standards and integration patterns that connect them, a maturity rating for nine common pairings, bundles and commercial barriers, and 23 RFI questions as CSV |
| Professions and skills | Government professions, Digital and Data framework career pathways with grades and skill levels, and learning routes |
| Your role | Routes for six roles across learn, prepare, do, report and improve |
| Learning | Modules with outcomes, activities and checks of understanding |
| Library | All material, templates, an assessment of where sector-specific content is needed, and open data |
| Knowledge | Glossary, thesaurus, taxonomy, knowledge graph and data dictionary |
| Inclusion | Equality, inclusion and accessibility checks for each capability |
| Status, What's new, About | Health run results, release notes, findings, open and defect registers, build standard assessment |
| Service design | Theory of change, research plan, blueprint, requirements traceability, architecture, Service Standard self-assessment |
| Open data, Help us test | Datasets with a DCAT catalogue for harvesting; testing tasks and feedback forms |
| Boards and networks, Get involved | Boards, councils and networks with purpose, outcomes and terms of reference; ways to take part, a champions toolkit and badges |
| Have your say | Take part in user research (private sign-up), suggest and vote for ideas (GitHub Discussions, Ideas), and see the roadmap, backlog, prioritisation criteria and decisions log, in the open (ADR 0006) |
| User guide, Site map, Use and reuse | How to get around, guided tours and tutorials; every page at a glance; ten ways to reuse the content, including AI assistants and a reference MCP server |
| Notices, Accessibility | Disclaimers, credits, full citations and the accessibility statement |

## How the repository supports the portal

| Portal feature | GitHub feature |
|---|---|
| Contact form | Issue forms (`.github/ISSUE_TEMPLATE`), plus an optional private Microsoft Forms route set in `content/frameworks.yaml` (`ms_form.url`) |
| Report a problem with this page | Pre-filled issue form |
| Suggest a change, change history | Edit and commit history of `content/playbooks.yaml` |
| Ask the community | Discussions |
| Status page | Weekly scheduled workflow; failures open an issue labelled `health` |
| What's new | `CHANGELOG.md` and tag-triggered releases |
| Hosting | GitHub Pages from the `gh-pages` branch, which the workflow publishes from `main` using plain commands (no third-party actions) |
| Supply chain | Dependency review on pull requests and a weekly OpenSSF Scorecard, using five reviewed actions pinned to commits (ADR 0005) |
| Security | CodeQL, Dependabot, secret scanning, private vulnerability reporting |

Nothing in the portal depends on any service other than GitHub and GitHub Pages, except the optional private feedback form.

Not sure which portal you need? The [estate compass](https://cyberdudeuk.github.io/dam-capability-playbooks/compass/) (`compass/`, built with this site) suggests where to start and in what order across all three.

Two sister portals are signposted, not merged: the [Public Sector Data Quality Commons](https://cyberdudeuk.github.io/dq-commons/) (a community project) and the [GitHub Repos Asset Catalogue](https://cyberdudeuk.github.io/github-repos-asset-catalogue/) (a specialist evidence tool). Their links live in `related` in `content/frameworks.yaml`; `data/xref.json` publishes this portal's shared keys for them to link back.

`integrations/mcp/server.py` is a reference Model Context Protocol server: standard library only, reading the published `data/playbooks.json`. See `integrations/mcp/README.md`.

## How it is built

- `content/playbooks.yaml` and `content/frameworks.yaml` are the single source of truth; `tools/build.py` generates `site/` from them and refuses to build on a broken reference, including a signpost to a GOV.UK section not recorded in `content/source-anchors.json`.
- `tools/check_site.py` (static checks) and `tools/check_browser.py` (real-browser checks) run on every change. `tests/` proves each check fails on a deliberate break.
- `tools/health.py` checks sources, signposted GOV.UK sections, external links, the review date and page weight. It never changes content.

```
pip install -r requirements.txt && npm ci && python -m playwright install chromium
python tools/build.py
DQKIT_PATH=../dq-commons python -m unittest discover -s tests   # DQKIT_PATH is optional; without it the sector rule run is skipped
python tools/check_site.py
python tools/check_browser.py
python tools/health.py
```

See [docs/RUNBOOK.md](docs/RUNBOOK.md) for routine operations and [CONTRIBUTING.md](CONTRIBUTING.md) to propose a change.
