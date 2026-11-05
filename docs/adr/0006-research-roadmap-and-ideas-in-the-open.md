# 6. Research, roadmap and ideas in the open

Date: 2026-11-05
Status: Accepted

## Context

The portal is a prototype with no research with real users yet (OR-04). Its owner wants users and teams to take part in research, suggest and vote for ideas, and see the roadmap, backlog and how priorities are set, following GDS "working in the open". The portal is static, has no server and sends nothing anywhere. Contact details must never be published, and no email address may appear on any artefact.

## Decision

1. One page, Have your say (`research.html`), built from `content/frameworks.yaml` (`research`), linked from the top of every page.
2. Research sign-up uses a private form (Microsoft Forms or GOV.UK Forms), set as `research.signup.url`. The build rejects any other host, so sign-up can never go to GitHub. Until it is set, the page points to the private feedback form.
3. Ideas and votes use this repository's GitHub Discussions, Ideas category, with a form (`.github/DISCUSSION_TEMPLATE/ideas.yml`). They are public by design. `tools/ideas.py` reads them at each build with the workflow's own token (`discussions: read`), keeps only what GitHub already shows, drops any title containing an address, and never fails the build.
4. Each backlog item is scored by six weighted criteria (user demand 25, DAM Policy 20, government strategy 20, feasibility 15, capacity 10, inclusion 10). Votes can raise user demand, never lower it. The score suggests Now, Next or Later; any item placed differently needs an entry in the decisions log. Now holds at most 5 items.
5. Check C-36 recomputes every score independently and fails on any mismatch, a missing decision, a GitHub sign-up, a link to another repository's discussions, an unlabelled unpublished strategy or an address.

## Consequences

- People without a GitHub account can take part in research and send ideas through the private form; a person adds their idea without their name.
- The Ideas category must exist (it is one of GitHub's defaults) and Discussions must stay enabled.
- The strategic roadmap for public sector data is listed as unconfirmed until it is published; when it is, add it to the rulebook and reassess every item.
