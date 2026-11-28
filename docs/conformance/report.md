# gds-dtx readiness: cyberdudeuk/dam-capability-playbooks

**READY WITH EXCEPTIONS**: 10 of 10 MUST checks met; 7 of 11 SHOULD checks met.

Checked on 2026-11-27 with `tools/conformance.py` from [cyberdudeuk/github-repos-asset-catalogue](https://github.com/cyberdudeuk/github-repos-asset-catalogue/blob/main/tools/conformance.py), against the GDS Way as published in alphagov/gds-way@7bc40fb (25 Nov 2026). Rerun it to check this page is still true.

| Check | Strength | What the GDS Way asks | Status | Evidence |
| --- | --- | --- | --- | --- |
| GA-01 | MUST | [Third-party actions pinned to a full commit SHA](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#pinning-actions) (page reviewed 2025-08-04) | PASS | all third-party actions pinned to a SHA |
| GA-02 | MUST | [Workflow permissions set to only what is needed](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#permissions) (page reviewed 2025-08-04) | PASS | top-level permissions set in every workflow |
| GA-03 | MUST | [No risky triggers](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#triggers) (page reviewed 2025-08-04) | PASS | no risky triggers |
| GA-04 | MUST | [No script injection from user-controlled event fields](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#script-injections) (page reviewed 2025-08-04) | PASS | no user-controlled fields interpolated into commands |
| GA-05 | MUST | [No personal access tokens in workflows](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#personal-access-tokens) (page reviewed 2025-08-04) | PASS | only GITHUB_TOKEN or app tokens |
| GA-06 | MUST | [AWS reached with OIDC, not access keys](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#authenticating-with-aws-and-other-external-services) (page reviewed 2025-08-04) | N/A | no AWS access keys |
| MS-01 | MUST | [Non-public repositories have HANDLING_INSTRUCTIONS.md](https://gds-way.digital.cabinet-office.gov.uk/standards/managing-sensitive-information.html) (page reviewed 2025-10-01) | N/A | public repository |
| SC-01 | MUST | [README](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | README.md |
| SC-02 | MUST | [Informative commit messages](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | 30 of 30 recent summaries say what changed |
| SC-03 | MUST | [MIT and OGL licence files](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | MIT: yes, LICENSE; OGL: yes, CONTENT-LICENCE.md |
| SC-04 | MUST | [An email address for security bug reports](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | EXCEPTION | SECURITY.md has no email address; private route: GitHub private vulnerability reporting, Cabinet Office VDP. Recorded exception (reviewed 2026-11-27): Owner decision (3 November 2026): no email address is published on any artefact; contact is by form only. Security reports go privately through GitHub private vulnerability reporting (switched on), as SECURITY.md explains. This departs from the GDS Way rule to give an email address for security reports. [SECURITY.md] |
| SC-05 | MUST | [If third parties are affected: changelog, release notes, known issues, semantic version](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | changelog: CHANGELOG.md; semantic version in it: yes; public issues: yes |
| AD-01 | SHOULD | [Architecture decisions recorded](https://gds-way.digital.cabinet-office.gov.uk/standards/architecture-decisions.html) (page reviewed n/a) | PASS | docs/adr |
| GT-01 | SHOULD | [Default branch is main](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/working-with-git.html#default-branch-name) (page reviewed 2025-02-18) | PASS | default branch main |
| GT-02 | SHOULD | [Commit summaries of 50 characters or fewer](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/working-with-git.html#structure) (page reviewed 2025-02-18) | FAIL | 12 of 30 recent summaries are 50 characters or fewer |
| SC-06 | SHOULD | [Contributing guidelines](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | CONTRIBUTING found |
| SC-07 | SHOULD | [Tests run in public CI](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/#publish-open-source-code) (page reviewed 2026-03-19) | PASS | CI on push or pull request: artefacts.yml, codeql.yml, dependency-review.yml, labels.yml, pages.yml, release.yml |
| TD-01 | SHOULD | [Automated dependency updates](https://gds-way.digital.cabinet-office.gov.uk/standards/tracking-dependencies.html) (page reviewed 2026-09-22) | PASS | .github/dependabot.yml |
| TD-02 | SHOULD | [Dependency update cooldown](https://gds-way.digital.cabinet-office.gov.uk/standards/tracking-dependencies.html) (page reviewed 2026-09-22) | FAIL | no cooldown |
| TD-03 | SHOULD | [Open update pull request limit of 10 or more](https://gds-way.digital.cabinet-office.gov.uk/standards/tracking-dependencies.html) (page reviewed 2026-09-22) | FAIL | default limit of 5 |
| VD-01 | SHOULD | [Published sites point security.txt at the Cabinet Office programme](https://gds-way.digital.cabinet-office.gov.uk/standards/vulnerability-disclosure.html) (page reviewed 2025-02-18) | FAIL | no security.txt pointing at vdp.cabinetoffice.gov.uk |
| GA-07 | CONSIDER | [CODEOWNERS covers .github/workflows](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/using-github-actions.html#user-permissions) (page reviewed 2025-08-04) | PASS | .github/CODEOWNERS covers workflows |
| UG-01 | CONSIDER | [Main branch protected](https://gds-way.digital.cabinet-office.gov.uk/standards/source-code/use-github.html#configuring-github-repositories) (page reviewed 2025-07-19) | PASS | main is protected (ruleset or branch protection) |
| DX-01 | GDS-DTX | [Pre-commit hooks with detect-secrets](https://github.com/gds-dtx/gds-dtx-github-users-tf/blob/main/.pre-commit-config.yaml) (page reviewed observed 27 Nov 2026) | PASS | pre-commit with detect-secrets |
| DX-02 | GDS-DTX | [Third-party actions listed for the gds-dtx Actions allowlist](https://github.com/gds-dtx/gds-dtx-github-users-tf/issues/13) (page reviewed observed 27 Nov 2026) | MANUAL | third-party actions to allowlist: ossf/scorecard-action |

## What the statuses mean

- **PASS**: the evidence shown meets the check.
- **EXCEPTION**: the check is not met, and a decision with a reason, review date and reference is recorded in `docs/compliance/exceptions.yaml`.
- **FAIL**: not met, and no decision is recorded.
- **MANUAL**: a repository setting or a person has to confirm it. It is never counted as a pass.
- **N/A**: the check does not apply here, for the reason shown.
- **GDS-DTX** checks follow what gds-dtx does in its own repositories. They are good practice, not GDS Way rules, and never decide the verdict.

## Do the same for your repository

1. Copy `tools/conformance.py` and `tools/conformance_meta.sh` from the catalogue, or run them from a clone of it.
2. `sh tools/conformance_meta.sh OWNER/REPO > meta.json` (needs the GitHub CLI, signed in).
3. `python3 -I tools/conformance.py PATH/TO/REPO --meta meta.json --write`
4. Fix each FAIL, or record a decision for it in `docs/compliance/exceptions.yaml` (check, rationale, reviewed, reference).
5. Commit `docs/conformance/` and add the badge to your README.
