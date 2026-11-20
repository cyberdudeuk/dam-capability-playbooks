---
artefact:id: P02-TOC-001
artefact:version: 1.0.0
artefact:as-of: 2026-11-20
artefact:review-date: 2027-02-20
project: P02 DAM capability playbooks
grade: G3
profile: public sector > central > work
---

# Theory of change: DAM capability playbooks

> **How to read this.** Facts marked V were read from this repository on 20 November 2026. Assumptions, measures and risks are proposals written for this kit, not findings. U means unconfirmed. Where another document in this repository already covers a topic, this one links to it rather than repeating it.

## Problem
Departments and arm's length bodies must meet the Data Asset Management Policy for their critical data assets, but GOV.UK guidance says what is required more than how to do it, step by step, across governance, cataloguing and quality.

## Long-term outcome
Organisations meet the DAM Policy for their critical data assets with less effort and more consistency, because each requirement has a practical, role-based route to meet it.

## Chain

| Inputs | Activities | Outputs | Short-term outcomes | Medium-term outcomes |
|---|---|---|---|---|
| The DAM Policy and its GOV.UK guidance; DAMA-DMBOK; sector guidance; the Data Quality Commons; source anchors that deep-link each requirement | Write step-by-step playbooks for governance, cataloguing and quality; map every policy requirement to the step that meets it; provide templates, measures, role routes, sector supplements, a capability model and a self-assessment | One static site generated from YAML content files: playbooks, policy map, sector finder, capability model, library, knowledge layer, status and registers | Coordinators find the step for each requirement in one place; fewer repeated questions to the policy team | DAM returns are more complete and consistent; organisations reuse templates instead of writing their own |

## Assumptions (proposed; each one testable)

| # | Assumption | How to test it | Evidence today |
|---|---|---|---|
| A1 | Practitioners want more detail than GOV.UK gives, in one place | Usability round with coordinators (EST-UR-001 §7) | S01 and S06 support this (strong) |
| A2 | Linking to GOV.UK rather than copying keeps the site trustworthy | Track link rot and drift with the health routine | ADR 0002 records the choice |
| A3 | Role routes match how people actually work | Tree test of the six role routes | Not tested |

## Measures (proposed)
- Every policy requirement mapped to a step (checkable now)
- Broken or drifted GOV.UK links at zero (health routine)
- Time to find the step for 5 benchmark requirements (baseline from usability round 1)

No target is set before a baseline exists.

## What would prove this wrong
If coordinators complete returns as well from GOV.UK alone, fold the playbooks into the DAM Policy Explorer as a reference layer instead of a separate site.

## Status
Prototype; not official GOV.UK guidance (V: README). Live site: https://cyberdudeuk.github.io/dam-capability-playbooks/
