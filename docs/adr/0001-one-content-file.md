# ADR 0001: One content file, generated pages

Date: 2026-11-05. Status: accepted.

## Context
Playbook material for the three capabilities was scattered across GOV.UK guidance, the Data Quality Commons, an internal
governance suite and portfolio material. Earlier suites suffered from hand-edited outputs drifting from their sources
(defects D-001 and D-002) and from build scripts lost between sessions.

## Options
1. Hand-written HTML pages. Fast to start; every fact repeated on several pages, so drift is certain.
2. A static site generator (Jekyll, MkDocs). Familiar on GitHub Pages; adds a toolchain and theme dependencies, and makes the cross-capability tables (requirements to stages, RACI across all three) awkward.
3. One YAML content file and a small Python generator. Every page, CSV, SKOS and DCAT export comes from the same data; validation can refuse broken references before anything is written.

## Decision
Option 3. The generator validates references (requirements, sources, roles, stages, concepts) and refuses to build on any error.

## Consequences
Editors change one file. Pages cannot disagree with each other. The trade-off is that layout changes need Python, not a theme.
