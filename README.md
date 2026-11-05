# DAM capability playbooks

Data governance, data cataloguing and data quality for critical data assets, in one portal, with the
[data asset management (DAM) policy in government](https://www.gov.uk/government/publications/data-asset-management-policy-in-government)
as the spine.

**Use it:** https://cyberdudeuk.github.io/dam-capability-playbooks/

**Status:** prototype, version 1.0.0, as of 5 November 2026. Not an official GOV.UK service or published GDS guidance.
Where it repeats GDS guidance, the GOV.UK page is the authority. Content under the
[Open Government Licence v3.0](docs/CONTENT-LICENCE.md); code under the [MIT licence](LICENSE).

## What is in it

| Page | What it gives you |
|---|---|
| DAM Policy | Every requirement in the policy and its linked guidance, its strength (must, should, method, gap), its source, and the stage that meets it |
| Governance | Five recipes: Mandate, Frame, Assign, Operate, Assure |
| Cataloguing | Eight stages from mobilising to annual review, plus the metadata properties mapped to the cross-government Metadata Exchange Model |
| Quality | Eight stages over the seven DQAP steps, with the issues framework and links to the Data Quality Commons tools |
| Joined up | The hand-offs between the three, one role model, one annual cycle, one RACI |
| By role | Routes for CDOs, coordinators, owners, stewards, catalogue managers and data quality leads |
| Library | All playbook material, published and internal, filterable, with open data downloads |
| Knowledge | Glossary and thesaurus, taxonomy, knowledge graph and data dictionary |
| About | Intent, checkpoint, source labels, the case against, open register, defect register, accessibility statement |

## How it is built

- `content/playbooks.yaml` is the single source of truth. Every page and export is generated from it.
- `tools/build.py` writes the site to `site/`. Never edit `site/` by hand.
- `site_src/` holds the stylesheet and the progressive-enhancement script. No CDN, web font or remote asset.
- Every fact carries a provenance label: V verified (with date), P owner's own material, O this playbook's synthesis, K background knowledge, U unconfirmed.

```
pip install -r requirements.txt && npm ci && python -m playwright install chromium
python tools/build.py                 # build
python -m unittest discover -s tests  # every static check fails on a deliberate break
python tools/check_site.py            # 15 static checks
python tools/check_browser.py         # 8 real-browser checks (axe, overflow 320-1920, keyboard, no-script, filters)
python tools/check_browser.py --break overflow   # prove a browser check fails when it should
```

The workflow in `.github/workflows/pages.yml` runs all of this on every change and publishes `site/` to GitHub Pages from `main`.

## Rules this repository keeps

- Contact is by [contact form](https://github.com/cyberdudeuk/dam-capability-playbooks/issues/new/choose) only. No email address appears anywhere; a check fails the build if one does.
- Decks and films are never committed here. A check fails the build if one is.
- Every defect gets a check in the same commit as its fix, recorded in the defect register (About page). The check suite never shrinks.
- Records name roles, never people.

## Contributing

Use the [contact form](https://github.com/cyberdudeuk/dam-capability-playbooks/issues/new/choose) for questions and problems.
Changes come as pull requests that edit `content/playbooks.yaml` (or the build), with the checks passing.

Attribution: Emanuel Silva, Data Management Team, Government Data directorate, GDS.
