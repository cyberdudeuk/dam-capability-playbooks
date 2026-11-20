---
artefact:id: P02-PRD-001
artefact:version: 1.0.0
artefact:as-of: 2026-11-20
artefact:review-date: 2027-02-20
project: P02 DAM capability playbooks
grade: G3
profile: public sector > central > work
---

# Product requirements (PRD): DAM capability playbooks

> **How to read this.** Facts marked V were read from this repository on 20 November 2026. Assumptions, measures and risks are proposals written for this kit, not findings. U means unconfirmed. Where another document in this repository already covers a topic, this one links to it rather than repeating it.

## Problem and outcome
Departments and arm's length bodies must meet the Data Asset Management Policy for their critical data assets, but GOV.UK guidance says what is required more than how to do it, step by step, across governance, cataloguing and quality.

Outcome sought: Organisations meet the DAM Policy for their critical data assets with less effort and more consistency, because each requirement has a practical, role-based route to meet it. See [01-theory-of-change.md](01-theory-of-change.md).

## Users
- Chief data officers and lead policy coordinators
- Data owners and data stewards
- Catalogue managers
- Data quality leads

User evidence: [02-ur-bundle.md](02-ur-bundle.md).

## Scope
**In:**
- Playbooks for governance, cataloguing and quality
- The policy requirement map with strengths and sources
- Sector supplements and finder
- Delivery and change; joined-up hand-offs
- Capability model and self-assessment
- Library, templates and the knowledge layer
- Status, registers, service design pages
- Open data with a DCAT catalogue

**Out:**
- Collecting returns (that is the DAM Policy Explorer and the return process)
- Personal data of any kind
- Being policy: GOV.UK stays the authority

## Requirements
Derived from what this repository says it does (V: README and ADRs). The last column is the check that proves each one, where one exists. U means no check was found that clearly covers it; that is a gap to close, not a pass.

| ID | Requirement | Priority | Verified by |
|---|---|---|---|
| P02-R01 | Map every DAM Policy requirement to its strength, source and the step that meets it | Must | tests/test_checks.py; tools/check_site.py |
| P02-R02 | Step-by-step playbooks for governance, cataloguing and quality, with roles, templates, measures and escalation | Must | tools/check_site.py |
| P02-R03 | Sector supplements with a finder | Should | tools/check_site.py |
| P02-R04 | Role routes for six roles across learn, prepare, do, report and improve | Should | not yet traced to a check (U) |
| P02-R05 | Capability model (DAMA wheel), 32 capabilities flagged explicit, implicit or inferred, with deep links | Should | content/source-anchors.json; check_site |
| P02-R06 | Knowledge layer: glossary, thesaurus, taxonomy, knowledge graph and data dictionary | Must | tools/check_site.py |
| P02-R07 | Open data with a DCAT catalogue for harvesting | Should | tests/test_publiccode.py (publiccode); DCAT not separately tested (U) |
| P02-R08 | Status page with health run results, release notes, open and defect registers | Must | tools/health.py |
| P02-R09 | Link, not copy, for GOV.UK content (ADR 0002) | Must | tests/test_hosts.py |
| P02-R10 | Contact by form only; no email address published | Must | tests/test_lint.py (U: confirm it covers email) |

## Non-functional requirements
- WCAG 2.2 AA; browser checks via tools/check_browser.py
- Self-contained pages; vendored icons (Lucide, ISC)
- Every GitHub Action reviewed and pinned (ADR 0005)
- Content under OGL v3 (work content about GOV.UK policy); code under MIT

## Status
Prototype; not official GOV.UK guidance (V: README)
