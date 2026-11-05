# 5. Allow a short list of reviewed actions for dependency review and Scorecard

Date: 2026-11-05. Status: accepted (repository owner's decision).

## Context
Since D-018 the workflows have used plain commands only, and the repository's Actions policy allows only actions owned by the
repository owner. Two checks that the sister portals already run need actions that are not: dependency review on every pull
request, and the OpenSSF Scorecard. Rebuilding them as plain commands would take longer and be harder to keep current.

## Options considered
1. Plain-command versions. Rejected by the owner: slower to build and to maintain.
2. Allow all GitHub-owned and verified-creator actions. Rejected: wider than needed.
3. Allow exactly the actions these two workflows need, each pinned to a commit checked against its release tag. Chosen.

## Decision
- Reviewed actions, recorded in `REVIEWED_ACTIONS` in `tools/check_site.py`:
  - `actions/dependency-review-action` v5.0.0 (`a1d282b3`)
  - `actions/checkout` v7.0.1 (`3d3c42e5`)
  - `actions/upload-artifact` v7.0.2 (`cf430e03`)
  - `github/codeql-action/upload-sarif` v4.39.2 (`1fc58d04`)
  - `ossf/scorecard-action` v2.5.0 (`fa7117db`)
- Each commit was checked against the upstream tag with `git ls-remote` on 5 November 2026.
- C-24 fails on any other action, or on a listed action at a different commit. C-25 lists the two new workflows.
- Dependabot proposes new commits; a person checks each against its tag and updates the list in the same pull request.
- The build, check and publish workflow keeps using plain commands only.

## What the owner must change on GitHub
Settings, Actions, General, "Allow cyberdudeuk, and select non-cyberdudeuk, actions and reusable workflows": tick
"Allow actions created by GitHub", and add `ossf/scorecard-action@*` to the allowed list. Until then GitHub refuses to start
these two workflows (as in D-018); nothing else is affected, because neither runs on a push to main.

## Consequences
More supply-chain surface than plain commands, held to five pinned, reviewed commits from GitHub and the OpenSSF.
