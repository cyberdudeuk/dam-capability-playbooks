# Changelog

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
