# Runbook

## Publish a change
1. Edit `content/playbooks.yaml` on a branch and open a pull request.
2. The workflow builds, runs every check and its vaccination, and shows the result on the pull request.
3. A person reviews and merges. The merge to `main` publishes to GitHub Pages.

## Before adding a page or a section on a new topic (D-026)
1. Search the sister portals for the topic: the [Data Quality Commons](https://cyberdudeuk.github.io/dq-commons/sitemap.html) site map and API (`api/pages.json`), and the [GitHub Repos Asset Catalogue](https://cyberdudeuk.github.io/github-repos-asset-catalogue/) hubs.
2. If one of them already covers it, write only what the DAM Policy adds, and add the sister page to `related.placements` in `content/frameworks.yaml`. Check C-34 keeps those signposts pointing at the sister portals, naming them and their status.
3. Keep each portal distinct: they have different owners, licences, audiences and status. Link to them; never copy their text into this portal.

## Cut a release
1. Add a section to `CHANGELOG.md` and bump `meta.version` in `content/playbooks.yaml`.
2. Merge, then push a tag such as `v1.2.0`. The release workflow builds, checks and attaches the site as a zip, with generated notes.
3. To roll back, revert the merge on `main`, or re-deploy an earlier release's zip.

## When the weekly health run opens an issue
- **Source changed:** read the GOV.UK page, update any affected requirement or step, then run `python tools/health.py --record` and commit `content/source-state.json` in the same pull request.
- **Source unreachable:** check the address; if it has moved, update `sources` in the content file.
- **Signposted sections no longer on the page (HL-02):** the GOV.UK page was restructured. Find the new section, update the signpost in `content/frameworks.yaml`, re-record the page's anchors in `content/source-anchors.json` from the GOV.UK Content API, and re-check the explicit, implicit or inferred flag still holds.
- **Review date passed:** review the content, then move `meta.review` forward.
- **Page over the weight envelope:** find what grew (the Status page lists each page) and reduce it.
Close the issue when every problem is resolved. Automation never changes content itself.

## Update the professions and skills data
Role levels, grades and skills on the Professions and skills page were read from the Government Digital and Data capability framework on 2026-11-05. When the framework's update history changes, re-read the role pages and update `professions.roles` in `content/frameworks.yaml`. The Data Maturity Assessment is CC BY-NC-SA 4.0: record only its structure, never its level descriptions (check C-21).

## Change an icon
Add the Lucide icon name to `ICON_NAMES` in `tools/vendor_icons.py`, run `npm ci && python tools/vendor_icons.py`, and commit `site_src/icons.json`.

## Repository settings the owner keeps switched on
Pages (source: Deploy from a branch, gh-pages, / (root); the workflow pushes the built site there), Issues, Discussions, private vulnerability reporting, Dependabot alerts, secret scanning,
and branch protection on `main` requiring the "Build, check and publish" workflow and one review.
