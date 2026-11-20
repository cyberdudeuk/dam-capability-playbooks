---
artefact:id: P02-SAD-001
artefact:version: 1.0.0
artefact:as-of: 2026-11-20
artefact:review-date: 2027-02-20
project: P02 DAM capability playbooks
grade: G3
profile: public sector > central > work
---

# Solution architecture (SAD): DAM capability playbooks

> **How to read this.** Facts marked V were read from this repository on 20 November 2026. Assumptions, measures and risks are proposals written for this kit, not findings. U means unconfirmed. Where another document in this repository already covers a topic, this one links to it rather than repeating it.

## Context
Departments and arm's length bodies must meet the Data Asset Management Policy for their critical data assets, but GOV.UK guidance says what is required more than how to do it, step by step, across governance, cataloguing and quality.

The solution is described in [03-prd.md](03-prd.md). It connects with: GOV.UK DAM Policy and guidance; Public Sector Data Quality Commons; DAM Policy Explorer; Compass (compass/); Estate register (govukOS ops/portfolio).

## Architecturally significant decisions
These are the decisions already recorded in this repository (V):

- [0001-one-content-file.md](../adr/0001-one-content-file.md)
- [0002-link-not-copy.md](../adr/0002-link-not-copy.md)
- [0003-github-native-features.md](../adr/0003-github-native-features.md)
- [0004-sector-signalling.md](../adr/0004-sector-signalling.md)
- [0005-reviewed-github-actions.md](../adr/0005-reviewed-github-actions.md)
- [0006-research-roadmap-and-ideas-in-the-open.md](../adr/0006-research-roadmap-and-ideas-in-the-open.md)

## Quality attributes

| Attribute | How it is met |
|---|---|
| WCAG 2.2 AA | WCAG 2.2 AA; browser checks via tools/check_browser.py |
| Self-contained pages | Self-contained pages; vendored icons (Lucide, ISC) |
| Every GitHub Action reviewed and pinned | Every GitHub Action reviewed and pinned (ADR 0005) |
| Content under OGL v3 | Content under OGL v3 (work content about GOV.UK policy); code under MIT |
| Contact | By form only; no email address anywhere (estate rule) |
| Documentation | This kit, checked in CI by `tools/artefact_check.py` |

## Constraints
- Prototype; not official GOV.UK guidance (V: README).
- No personal data unless a DPIA has been done first.
- Contact by form only.

## Risks (proposed ratings)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Drift from GOV.UK after policy updates | Medium | High | Health routine re-checks anchors; review dates |
| Mistaken for official guidance | Medium | High | Status banner on every page; GOV.UK named as authority |
| No research with users yet | High | Medium | EST-UR-001 field research; 'Help us test' page |
