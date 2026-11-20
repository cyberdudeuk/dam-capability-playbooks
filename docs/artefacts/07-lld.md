---
artefact:id: P02-LLD-001
artefact:version: 1.0.0
artefact:as-of: 2026-11-20
artefact:review-date: 2027-02-20
project: P02 DAM capability playbooks
grade: G3
profile: public sector > central > work
---

# Low-level design (LLD): DAM capability playbooks

> **How to read this.** Facts marked V were read from this repository on 20 November 2026. Assumptions, measures and risks are proposals written for this kit, not findings. U means unconfirmed. Where another document in this repository already covers a topic, this one links to it rather than repeating it.

## Build and check commands (V: README)
```
python3 -I tools/build.py
python3 -I tools/check_site.py
python3 -I -m pytest tests
```

## Scripts (V: file tree)
- `tools/build.py`
- `tools/check_browser.py`
- `tools/check_site.py`
- `tools/compass.py`
- `tools/compass_sync.py`
- `tools/digest.py`
- `tools/health.py`
- `tools/ideas.py`
- `tools/triage.py`
- `tools/trials.py`
- `tools/vendor_icons.py`

## Tests (V: file tree)
- `tests/test_automation.py`
- `tests/test_checks.py`
- `tests/test_dependencies.py`
- `tests/test_explorer.py`
- `tests/test_hosts.py`
- `tests/test_licences.py`
- `tests/test_lint.py`
- `tests/test_publiccode.py`
- `tests/test_release.py`

## Workflows (V: .github/workflows)
- `codeql.yml`
- `dependency-review.yml`
- `digest.yml`
- `labels.yml`
- `pages.yml`
- `release.yml`
- `scorecard.yml`
- `triage.yml`

## Repository size
100 files tracked on 20 November 2026.

## Documentation kit
- `docs/artefacts/manifest.yaml` lists every core document, where it is, and its review date.
- `tools/artefact_check.py` checks the kit (rules AC-01 to AC-08, each with a negative test). Run `python3 tools/artefact_check.py --self-test` then `python3 tools/artefact_check.py .`.

## Handover
Someone new can rebuild and verify with the commands above, then read [03-prd.md](03-prd.md) and [05-sad.md](05-sad.md).
