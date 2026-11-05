# Runbook

## Publish a change
1. Edit `content/playbooks.yaml` on a branch and open a pull request.
2. The workflow builds, runs every check and its vaccination, and shows the result on the pull request.
3. A person reviews and merges. The merge to `main` publishes to GitHub Pages.

## Cut a release
1. Add a section to `CHANGELOG.md` and bump `meta.version` in `content/playbooks.yaml`.
2. Merge, then push a tag such as `v1.2.0`. The release workflow builds, checks and attaches the site as a zip, with generated notes.
3. To roll back, revert the merge on `main`, or re-deploy an earlier release's zip.

## When the weekly health run opens an issue
- **Source changed:** read the GOV.UK page, update any affected requirement or step, then run `python tools/health.py --record` and commit `content/source-state.json` in the same pull request.
- **Source unreachable:** check the address; if it has moved, update `sources` in the content file.
- **Review date passed:** review the content, then move `meta.review` forward.
- **Page over the weight envelope:** find what grew (the Status page lists each page) and reduce it.
Close the issue when every problem is resolved. Automation never changes content itself.

## Change an icon
Add the Lucide icon name to `ICON_NAMES` in `tools/vendor_icons.py`, run `npm ci && python tools/vendor_icons.py`, and commit `site_src/icons.json`.

## Repository settings the owner keeps switched on
Pages (source: GitHub Actions), Issues, Discussions, private vulnerability reporting, Dependabot alerts, secret scanning,
and branch protection on `main` requiring the "Build, check and publish" workflow and one review.
