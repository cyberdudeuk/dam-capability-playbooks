---
artefact:id: P02-FTIR-001
artefact:version: 1.0.0
artefact:as-of: 2026-11-20
artefact:review-date: 2027-02-20
project: P02 DAM capability playbooks
grade: G3
profile: public sector > central > work
---

# Functional, technical and integration requirements (FTIR): DAM capability playbooks

> **How to read this.** Facts marked V were read from this repository on 20 November 2026. Assumptions, measures and risks are proposals written for this kit, not findings. U means unconfirmed. Where another document in this repository already covers a topic, this one links to it rather than repeating it.

Requirements are stated once, in [03-prd.md](03-prd.md). This document says how each is met and checked.

## Functional

| ID | Requirement | Priority | Verified by | State |
|---|---|---|---|---|
| F01 | Map every DAM Policy requirement to its strength, source and the step that meets it | Must | tests/test_checks.py; tools/check_site.py | Has a check |
| F02 | Step-by-step playbooks for governance, cataloguing and quality, with roles, templates, measures and escalation | Must | tools/check_site.py | Has a check |
| F03 | Sector supplements with a finder | Should | tools/check_site.py | Has a check |
| F04 | Role routes for six roles across learn, prepare, do, report and improve | Should | not yet traced to a check (U) | Not traced |
| F05 | Capability model (DAMA wheel), 32 capabilities flagged explicit, implicit or inferred, with deep links | Should | content/source-anchors.json; check_site | Has a check |
| F06 | Knowledge layer: glossary, thesaurus, taxonomy, knowledge graph and data dictionary | Must | tools/check_site.py | Has a check |
| F07 | Open data with a DCAT catalogue for harvesting | Should | tests/test_publiccode.py (publiccode); DCAT not separately tested (U) | Check named; coverage unconfirmed (U) |
| F08 | Status page with health run results, release notes, open and defect registers | Must | tools/health.py | Has a check |
| F09 | Link, not copy, for GOV.UK content (ADR 0002) | Must | tests/test_hosts.py | Has a check |
| F10 | Contact by form only; no email address published | Must | tests/test_lint.py (U: confirm it covers email) | Check named; coverage unconfirmed (U) |

## Technical

| ID | Requirement | State |
|---|---|---|
| T01 | Code scanning | Present (V: .github/workflows) |
| T02 | Dependency review on pull requests | Present (V: .github/workflows) |
| T03 | OpenSSF Scorecard | Present (V: .github/workflows) |
| T04 | Automated release | Present (V: .github/workflows) |
| T05 | Published by workflow (Pages) | Present (V: .github/workflows) |
| T06 | Documentation kit checked in CI | Present (V: .github/workflows) |

Workflows present (V): `codeql.yml`, `dependency-review.yml`, `digest.yml`, `labels.yml`, `pages.yml`, `release.yml`, `scorecard.yml`, `triage.yml`.

Tests present (V): `test_automation.py`, `test_checks.py`, `test_dependencies.py`, `test_explorer.py`, `test_hosts.py`, `test_licences.py`, `test_lint.py`, `test_publiccode.py`, `test_release.py`.

## Integration

| ID | Integration | Direction | State |
|---|---|---|---|
| I01 | GOV.UK DAM Policy and guidance | Link out, deep-linked anchors | Live |
| I02 | Public Sector Data Quality Commons | Quality rules the Commons kit can run | Live |
| I03 | DAM Policy Explorer | Explorer links to playbook steps | Live (explorer/) |
| I04 | Compass (compass/) | Navigation data | Live |
| I05 | Estate register (govukOS ops/portfolio) | Manifest harvested | From this change |
