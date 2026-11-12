# Changelog

## Unreleased
- Data portals compass 1.3 (formerly the estate compass):
  - Renamed after an assessment shown on the page: "estate" is shorthand many readers do not know; "data portals" says what it covers, and the compass picture stays. The address is unchanged.
  - Says plainly what it is, who it is for, what it helps you do and what it is not, at the top of the page, without repeating the masthead.
  - Words explained: 34 terms in plain English, each with other names (thesaurus), a broader term and related terms, searchable and A to Z. Dotted terms on the page show their meaning on hover or keyboard focus and open their entry.
  - Fixed (D-035): opening the page jumped to the first tab and outlined it, because the address was written while the page loaded.
- Estate compass 1.2:
  - The DAMA wheel: Data governance at the centre, selected when the page opens, with the ten other knowledge areas around it. Select an area to drill down to its capabilities, the activities under each (playbook recipe stages, change items, perspectives and maturity strands) and their individual steps, with where each is in the DAM playbooks and the other three portals.
  - A lineage diagram for whatever is selected, a traceability table of every activity and gap (filter, search, CSV), a search box across areas, capabilities, activities and steps, and My pathway: your own ordered list of activities, started from your role's recipe stages, kept in the page address, with copy link, download and print.
  - The compass rose names and links the four portals at their bearings; tooltips on the wheel, capabilities, activity kinds, the lineage diagram, the rose and the tabs; the prototype strip moved to the top.
  - Kept up to date automatically: a daily check reads every link into the other portals, hides any that are gone, shows when each portal last changed, and opens a compass-sync issue for a person. Sister portals can trigger a rebuild with a `portal-updated` repository dispatch. The DAMA wheel itself is rebuilt from the DAM content at every build.
  - Fixed (D-034): DCAT-AP-UK moved to `dcat-ap-uk`; the compass and the DAM pages' Related links now use the new address.
- From the Project Compass pilot session (11 November 2026), built now:
  - Templates: names and work email addresses may be kept in a team's own working copies; only what is published, on GitHub or anywhere public, must name roles alone. The old line read as banning named people from a team's own RACI.
  - Every template says whether it is for business as usual, change programmes or both, and the Library can filter by it. Each template downloads on its own as a CSV header row (`data/templates/`), as well as all together.
  - New T-GOV-5 day-to-day management workbook: one OpenDocument spreadsheet with tabs for risks, assumptions, issues, dependencies, decisions, actions and exceptions. Decisions and exceptions reuse the fields of T-GOV-3 and T-GOV-4, so each log is still defined once.
  - New T-CAT-4 entity and relationship list, an interim home for relationship artefacts until a data architecture playbook exists.
  - Data dictionary: data type, format, how many values, controlled value lists you can click through to, and a synthetic example for every catalogue property; the same columns in `data/metadata-dictionary.csv`.
  - Health and care supplement: HL7 FHIR UK Core, SNOMED CT, DCB0129 and DCB0160 signposted, with steps to record them in `conformsTo` and to record clinical safety. Every supplement now groups its legislation, standards and frameworks by kind.
  - Retention: how to approve keeping an asset longer through the exception register, and The National Archives' advice that there is no single government-wide period, so "seven years" is an example to check against your own schedule.
  - Data sharing: check Part 5 Digital Economy Act agreements against the published register.
  - Service assessments (change item CH-02): show the panel that data was considered; templates stay the team's working record.
  - The proposed DCAT Application Profile for the UK is signposted from Cataloguing, labelled proposed, not endorsed.
- New check C-38 with nine deliberate breaks and three build-time rejections.
- Fixed (D-033): an unquoted comma in a YAML value silently split the data dictionary's title format; the build now rejects stray or empty keys.
- Private feedback form, finished and wired in: every page's footer and "Was this page useful?" line, the contact page, Get involved and each Help us test task now open the Microsoft form with the page or task already filled in (tasks are also marked as task feedback), so each response can be traced to where it came from. Anyone can respond without signing in; contact details are optional and asked for only to reply or to email a copy of the answers. About > Privacy now says how the form uses answers and contact details. Open item OR-02 is narrowed to what the data protection officer still has to confirm.
- In the form itself (8 November 2026): a new introduction linking back to the portal and its privacy wording, a "Something else" topic, labelled 1 to 7 ease scale, guidance on what to tell us and where the correct information is, new optional questions (what would make it better, browser and assistive technology, organisation type, whether to contact you or email a copy, email address, organisation), a reworded privacy confirmation, a thank-you message pointing to What's new, and a solid blue theme closer to the portal's own colours.
- Fixed (D-032): the private form opened blank from everywhere and the portal said it might ask people to sign in. C-33 now checks the wiring on every page and task, proved by five deliberate breaks and a build-time rejection.
- Journeys across the three portals: every page now loads `assets/journey-bar.js`, so a journey started on the Data Quality Commons ("Three portals, one journey") shows its step and a link to the next one here too. The script is the same file the Commons publishes, needs no styles or libraries, sends nothing anywhere and shows nothing unless you started a journey (Commons BL-34).
- Estate compass 1.1.1: South is now called DCAT-AP-UK, the DCAT Application Profile for the UK, as the profile renamed itself after other national DCAT-AP profiles (DCAT-AP-NO, -SE, -NL) in its release 1.2.0-rc.1. Its address is unchanged until its owner renames the repository.

## 1.10.1 (2026-11-06)
- Estate compass 1.1.0: a fourth bearing. South is the DCAT-UK Application Profile (DCAT-UK AP), the proposed successor to the xGov MEM: how to describe data so others can find it. It has a portal card, a "describe data so others can find it" situation and route, steps in the policy and reuse routes, a worked example, when to use it, links for each DAMA area, a lane on the route trail, and its links in the link table. North, east and west are unchanged. DCAT-UK AP is proposed, not endorsed, and the card says so.

## 1.10.0 (2026-11-05)
- Boards, councils and networks (`bodies.html`, under Frameworks): 7 boards and groups that decide or advise (CDO Council, DSA Steering Board, Peer Review Group, Open Standards Board, the data and technology architecture design authority, Taxonomy Oversight Group, and the Data Steering Group, marked status unclear) and 10 communities and networks, each with purpose, aims, expected outcomes, link to the DAM Policy, how to take part and whether terms of reference are published; how standards and decisions flow; and where to take each kind of issue. Checked on GOV.UK and data.gov.uk on 5 November 2026. No email addresses are listed.
- Get involved (`involve.html`): nine ways to take part, rules of engagement, how to improve the content, champions and ambassadors, a toolkit of ready-made text (email, Microsoft Teams, Slack, Viva Engage, intranet news, a 15 minute walk-through and an email signature line) with copy buttons, and six badges (Explorer, Tester, Contributor, Reviewer, Champion, Ambassador) as SVG and PNG with code for GitHub profiles, web pages and email signatures. Badges are claimed through a new public form that shows a GitHub username only.
- Backlog items delivered: Check this flag on every capability (BL-15); embed pages for every requirement and capability (BL-16); level labels on every page and easy read summaries on eight pages (BL-17); Ask a question on the home page, answered in the browser from the portal's own pages (BL-18); an Atom releases feed (BL-19); an OWL ontology and PROV-O lineage from sources to requirements, pages and checks (BL-20); and an offline copy of the whole site (BL-21).
- New check C-37 and browser check B-18, with 12 deliberate breaks, 3 build-time rejections and a new break mode.
- Fixed (D-030): the Open data page said "1 files" and offered only a few downloads, because it was built before the data files existed. It is now built after them, lists every file, and C-28 checks every catalogued file has a download link.
- Fixed (D-031): What's new showed raw Markdown backticks around file names; they now show as code.
- Packs for the backlog items that need people (sign-up form, recruitment, clearance, expert review, metadata terms, Welsh) in `docs/backlog-packs.md`.

## 1.9.0 (2026-11-05)
- Have your say (`research.html`), linked from the top of every page: user research, the roadmap, the backlog and ideas, in the open.
  - Take part: six ways to take part (interview, usability session, tree test, survey, accessibility session, review panel), who we want to hear from, a private sign-up (never GitHub), how participants' information is looked after, four research rounds tied to the research plan's hypotheses, and an email link to introduce the portal to a team.
  - Roadmap: Now, Next and Later, with Done and Out of scope, modelled on the data.gov.uk roadmap. Now holds at most 5 items.
  - Backlog: 21 items written as user stories, each with where it came from (open register, research, ideas, the portal comparison), filterable, and downloadable as CSV and JSON.
  - Ideas and voting: GitHub Discussions (Ideas category) with an idea form; the most voted ideas are read at each build by `tools/ideas.py`, which drops any title with an address and never fails the build. Votes count towards user demand.
  - How we prioritise: six weighted criteria (user demand 25, DAM Policy 20, government strategy 20, feasibility 15, capacity 10, inclusion 10), the score formula with a worked example, what each score suggests, the government strategies items are aligned to, and a decisions log for every item placed differently from its score. The strategic roadmap for public sector data is listed as in development and unconfirmed: announced for April 2026, not found published on 5 November 2026.
- Six verified rulebook entries: A roadmap for modern digital government 2025 to 2030, four GOV.UK Service Manual user research pages, and the data.gov.uk roadmap.
- New check C-36 (Have your say on every page, private sign-up, idea links only to this repository, scores recomputed and matched, Now limit, decisions for every override, unconfirmed strategy labelled, no addresses), proved by nine deliberate breaks, with five build-time rejections and tests for the ideas reader.
- Fixed (D-029): re-vendoring icons would have dropped 11 icons; the vendor list now covers every icon and a test checks it.

## 1.8.3 (2026-11-05)
- Related elsewhere links to the new parts of the Data Quality Commons (release 2.10.0): the standards catalogue (open standards for data, digital, cyber and technology with their GOV.UK status) on the cataloguing and tools pages; the Commons data management wheel and "Three portals, one journey", where a DAMA area, role or standard can be traced through all three portals, on the capability model page; and data quality in change programmes on the delivery and change page. The metadata weaver signpost now mentions its DQV output.
- The Commons now links back: its wheel areas and roles open the same area (`capability-model.html#dm-xx`) and role (`together.html#role-CODE`) here, and its page "Three portals, one journey" reads this portal's `data/xref.json` to check the shared keys still match. The estate compass's table of links between the portals is updated to say so.
- Fixed (D-028): the Status page printed the owner's account name when a link to a sister portal was broken (here, a Commons page committed but not yet published). Addresses in the owner's account are now named by what they are, keeping the page name.
- Fixed (D-027): a break script crashed on the compass page, which has none of this portal's own objects, and stopped the 1.8.2 publish. Every break script is now safe on any page, a test runs each one on an empty page, and the runbook says to run every break mode before adding a page to the browser checks.

## 1.8.2 (2026-11-05)
- Estate compass at `compass/`: a neutral page that orients people across the DAM capability playbooks (north: the obligation), the Data Quality Commons (east: the practice) and the GitHub Repos Asset Catalogue (west: what already exists). Four questions (situation, role, whether the DAM Policy applies, comfort with GitHub) give a route of steps across the portals, each with the question to ask yourself, why it matters and what you get, and the compass needle turns to the starting portal. Also: what each portal is for, its mission, outcomes, audience, owner model, how binding it is and its licence; the order of precedence; eight worked examples; when to use or skip each portal; data management areas across the portals; and how the portals link. Routes can be shared as links. Linked from every page's footer and every Related elsewhere section.
- Dependency review on every pull request and a weekly OpenSSF Scorecard, using five GitHub and OpenSSF actions pinned to commits checked against their release tags (ADR 0005). C-24 now allows exactly those commits; Dependabot proposes updates for a person to check.
- New checks C-35 (compass self-contained, links only to the three portals, every link into this portal resolves, every situation has a cross-portal route, usual footer) and B-17 (every situation gives its route, the needle points to the start, shared links restore the route), with deliberate breaks. The compass also checks itself in the reader's browser.
- Nine Lucide icons added for the compass (navigation, map pin, footprints, mountain, trophy, sparkles, check, code and branch).

## 1.8.1 (2026-11-05)
- Related elsewhere: signposts to the Data Quality Commons and the GitHub Repos Asset Catalogue at the end of eight pages (quality, cataloguing, tools, perspectives, delivery and change, capability model and reuse), each naming the portal and its status (community project, specialist evidence tool). The portals stay distinct: different owners, licences, audiences and status; nothing is copied across.
- Tools and interoperability now frames its questions by what the DAM Policy needs and points to the Commons for named products, the lock-in checker, the RFI builder and the test script (D-026).
- Cross-reference manifest `data/xref.json`: this portal's shared keys (DAMA areas, requirements, capabilities, practices, sectors, roles, tool categories) and their addresses, listed in the DCAT catalogue.
- New check C-34 (signposts go only to the sister portals, name them and their status and sit outside this portal's tabs; every manifest address exists), proved by four deliberate breaks. The runbook now starts each new topic with a search of the sister portals.

## 1.8.0 (2026-11-05)
- Tools and interoperability page: nine kinds of data management tool (catalogue, glossary, data quality, lineage, master data, governance workflow, data contracts, records, AI assistants) mapped to DAMA knowledge areas, with the open standards and integration patterns that connect them; nine common pairings rated established, emerging or vendor-specific; one supplier or several; eight commercial barriers with how to avoid them; six steps to buy without lock-in; and 23 questions for a request for information or tender, downloadable as CSV.
- 21 new verified rulebook entries, including the Open Standards principles, Technology Code of Practice points 4 and 11, Managing technical lock-in in the cloud, PPN 07/15, the Data Standards Authority catalogue and metadata standards, the CMA cloud services market investigation and follow-up actions, Find a Tender, OpenLineage, the Open Data Contract and Data Product Standards, PROV-O, SKOS, CSVW, OpenAPI, Egeria and the Model Context Protocol. G-Cloud 14 updated to G-Cloud 15. The EU Data Act is labelled as found by search.
- Private feedback: a Microsoft Forms route on the contact and testing pages and in every footer, for people without a GitHub account. Shown only when a form address is set.
- Finding your way: a share menu on every page (copy link, your device's share, email with no recipient, Microsoft Teams), a site map, a user guide with six guided tours and six tutorials, tooltips on terms, pills and sources, and a colour for each part of the portal.
- Tables size their columns to their content, so long text gets the room.
- Use and reuse page: ten approaches from intranet links to white-label copies; addresses for tools; llms.txt and llms-full.txt for AI assistants; and a reference MCP server (integrations/mcp/server.py) with five tools.
- Fixed before release: search stopped working because the tour script reused the search index's name (D-024); key hints failed contrast and a code example overflowed on phones (D-025).
- New checks C-31 (share menu, site map, llms.txt and tour targets), C-32 (MCP server answers with page links and the right version), C-33 (tools page, RFI CSV and private feedback route) and B-16 (every tour runs and the share menu works), each proved by deliberate breaks.

## 1.7.0 (2026-11-05)
- Programme roles: seven roles found in medium and large programmes (senior responsible owner, programme or project manager, service or product owner, design authority or solution architect, data migration lead, commercial lead, programme office and assurance) now have data responsibilities, appear in the roles list and the delivery and change practices, and have a new route: "Programme or project lead".
- Service blueprint for a programme on the Delivery and change page: five lanes across six stages, from business case to retirement.
- DAMA wheel on the Capability model page: eleven knowledge areas around data governance, shaded by how many DAM capabilities touch each, with what each area is, the DAM capabilities and maturity topics it maps to, its records and information management counterpart, and how each of seven roles uses it. Choose a role to see your guidance. The data and records life cycles are shown side by side with where DAM acts.
- Working together page: ten recommendations for join-up between professions, each with an action, an outcome and a measure; 15 verified communities and networks filtered by role; and a map of which professions contribute to each capability.
- 10 new verified rulebook entries, including the role of the senior responsible owner, the Public Records Act 1958, The National Archives guidance, the Data Standards Authority and the Government Data Quality Hub. ISO 15489 and ISO 23081 are labelled as found by search because the site blocks automated checks.
- Test tasks T-12 to T-14. The build now refuses a role without an icon and a wheel area without guidance for every role.

## 1.6.0 (2026-11-05)
- Perspectives: the DAM Policy through six lenses (data, digital and service, cyber and security, technology and architecture, commercial and suppliers, legacy and technical debt). Each gives questions to ask, actions for each capability, pitfalls, related capabilities, practices and professions, and verified sources, with a coverage assessment of every lens against every capability.
- Coverage gaps closed: cyber and commercial were the thinnest lenses. New capabilities CR-31 (cyber resilience and incident response for data assets) and CR-32 (avoiding future legacy: open standards, portability and exit); new practices CH-14 (design out lock-in), CH-15 (prepare for a cyber incident) and CH-16 (buying routes and contract terms that protect data).
- 20 new verified rulebook entries, including the NCSC Cyber Assessment Framework, the Government Cyber Security Strategy, GovS 007, Secure by design, Cloud First, the API technical and data standards, the Model Services Contract, the Procurement Act 2023 and G-Cloud 14. Government Commercial Function added to the professions.
- New test task T-11 for each team's lens.

## 1.5.1 (2026-11-05)
- Ready for user testing: a "Help us test" page with 10 tasks filtered by role, each with a start link and a pre-filled feedback form asking whether it was completed, how easy it was (1 to 7) and what got in the way. Linked from the prototype banner and every page footer.
- Open data page listing 13 datasets and 30 files, and a DCAT 3 catalogue of the portal's own datasets in JSON-LD and Turtle with licence, publisher, contact point, version and media types. Every page links to the catalogue in its header; the Open data page carries schema.org Dataset markup for dataset search. Sources move to their own catalogue, sources.jsonld.
- About page: the open register becomes "Known limitations", showing only what readers need to know. The build report, the build standard assessment and the full open register move to the repository's docs folder.
- New checks C-28 (catalogue complete and linked), C-29 (every limitation mentioned is explained) and C-30 (testing pack complete), each proved by deliberate breaks.

## 1.5.0 (2026-11-05)
- Fixed: the Playbooks and Frameworks menus opened but could not be seen or clicked (D-022). New browser check B-14 opens every grouped menu on desktop and phone and follows its links.
- Sector content is now signposted where it is used: each capability playbook has a Sectors tab showing what each supplement adds to it, and its step-by-step method opens with a link to the finder (ADR 0004). The sector-depth assessment is removed now that every theme has a supplement.
- The defect register and the challenge review move from the About page to the repository (docs/defect-register.md and docs/challenge-review.md). New check C-27 keeps them complete and off the portal.

## 1.4.1 (2026-11-05)
- Fixed: one temporary server error from github.com counted as a broken link and blocked publishing (D-019). Links are now retried and only 404 and 410 count as broken; the Status page names the repository by role.
- Fixed: a suggested Jekyll workflow and Pages publishing from main would have published raw repository files (D-020). Removed; Pages publishes the built site from gh-pages. New check C-25 keeps the workflow set to the three reviewed ones.
- Commits from automated sessions are now attributed to the repository owner's own noreply address, so GitHub no longer credits an unrelated account named "noreply" (D-021).

## 1.4.0 (2026-11-05)
- Capability model: 30 capabilities the DAM Policy, its guidance and adjacent rulebooks need, in six clusters. Each is flagged explicit, implicit or inferred, with 76 signposts to the exact GOV.UK section, maturity topics, Digital and Data framework skills, professions and industry model areas.
- Government data maturity model shown by topic, theme and level with links to each topic, plus indicators for four DAM strands and crosswalks to CMMI, ISO 8000-61, DAMA-DMBOK and DCAM.
- Self-assessment with a radar profile, kept in your browser only, downloadable as CSV.
- Professions and skills: routes from each role in the policy to framework roles and professions; career pathways for 7 Digital and Data roles with grades and skill levels; learning routes from awareness to leadership with progress tracking; Government Campus prospectus strands.
- Delivery and change: what the policy leaves to you, a life cycle overlay and 13 practices with 44 trackable actions for business as usual and change programmes, including business cases, spend control, assurance, legacy exits, contracts, risk, handover and benefits.
- 43 new rulebook entries for delivery, investment, assurance, skills and professions, each checked live.
- New learning module M11. Findings F-05 (maturity framework licence), F-06 (legacy guidance asks for a separate asset register) and F-07 (learning platform accessibility).
- New checks: C-21 (no copying of text under a licence the portal cannot carry), C-22 (every signpost verified, every capability flagged), B-12 (sector finder), B-13 (self-assessment), HL-02 (signposted sections still exist) and a dqkit run of every sector rule file. Defects D-015 and D-016 recorded.
- Fixed: workflow runs had stopped starting since 1.2.0 because the repository only allows its owner's actions pinned to a commit SHA, so the portal was not being published (D-018). Workflows now use plain commands only and publish to the gh-pages branch; CodeQL runs from its pinned, digest-checked command-line bundle. Check C-24 enforces the policy. Pillow 13.0.0, Playwright 1.64.1 and axe-core 4.14.0 replace versions flagged by Dependabot.
- Fixed: the repository citation file had been published empty since 1.2.0 (D-017). New check C-23 keeps it complete and in step with the release.

## 1.3.0 (2026-11-05)
- Sector supplements for 14 themes, each with a governance overlay, risks, extra catalogue fields, a quality rule library, a worked example, a checklist and related rulebook entries.
- A finder that shows which supplements apply to an asset, and a library of 50 sector quality rules downloadable as CSV and as YAML files the Data Quality Commons kit can run.
- Playbooks are grouped in one menu so the top bar stays within the screen.

## 1.2.0 (2026-11-05)
- Related policies, standards, legislation and rulebooks: 40 entries, each checked live and labelled with how it was checked.
- Sector assessment now links to the related rulebook entries.
- Verification findings published, including a contradiction in Table 4 of the GOV.UK issues framework (F-01) and the renamed Data and AI Ethics Framework (F-02).
- Proposed crosswalk for the four metadata properties missing from the Metadata Exchange Model.
- New pages: service design (theory of change, research plan, blueprint, requirements traceability, architecture, Service Standard self-assessment), disclaimers, credits and citations, and an accessibility statement following the GOV.UK model.
- Every page now shows its owner role, dates and a "was this page useful?" link. A security.txt is published.
- The weekly health run now checks every external link.
- New checks C-19 and C-20 and a health-run test, each proved by a deliberate break; defect D-013 recorded.

## 1.1.0 (2026-11-05)
- Title spells out Data Asset Management (DAM). New favicon, social sharing image and search engine metadata on every page.
- Routes for six roles, each with a profile, user needs, a five-stage journey and a learning journey.
- Ten learning modules with outcomes, activities, progress tracking and checks of understanding.
- Step-by-step methods with "mark as done" progress that shows on each role's route.
- Inclusion page: duties, checks for each capability and questions to ask of any critical data asset.
- Display options for text size, line spacing and colours. Professional icon set (Lucide).
- Contact form page, "report a problem with this page", Discussions, releases and a weekly health run with a Status page.
- Assessment of where each capability needs sector-specific content, and of the portal against the build standard.
- Personal and team details removed; contact is by form only.

## 1.0.0 (2026-11-05)
- First release: DAM Policy spine (16 requirements), governance (5 recipes), cataloguing (8 stages, 14 metadata properties), quality (8 stages over the 7 DQAP steps).
- Joined-up view: 9 hand-offs, one role model of 12 roles, one annual cycle, one RACI across all stages.
- Knowledge layer: 35 concepts as glossary, thesaurus, taxonomy, SKOS and JSON-LD; knowledge graph; data dictionary.
- 15 static checks and 8 browser checks, each proved to fail on a deliberate break. Defects D-001 to D-007 recorded with their checks.
