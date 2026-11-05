# 4. Sector content: one home, signposted where it is used

Date: 2026-11-05. Status: accepted.

## Context
Version 1.3 delivered supplements for all 14 sector themes the earlier sector-depth assessment identified, so the assessment of
"where more sector content is needed" no longer describes a gap. Sector content still needs signalling: a steward working
through the quality method on social care data should not have to know the Sectors section exists.

## Options considered
1. Embed sector content inside each capability playbook. Rejected: each supplement spans all three capabilities, so it would be
   split three ways and repeated, and the rule library and finder would have no home.
2. Keep a separate Sectors section only. Rejected: it relies on people finding it.
3. One home, signposted at the point of use. Chosen.

## Decision
- The Sectors section stays the single home for supplements, the finder and the rule library.
- Each capability playbook has a Sectors tab listing the supplements that add to it and what each adds for that capability
  (governance points and risks, catalogue fields and identifiers, or runnable quality rules).
- The step-by-step method opens with a short callout linking to the finder and the relevant supplements.
- The capability model links sector-dependent capabilities to the Sectors section.
- The sector-depth assessment is removed from the Library and the capability pages; its themes remain in the content file as
  the source of each supplement's priority and sectors.

## Consequences
Sector content is written once and found from three places. A new supplement appears in every relevant playbook automatically,
because the signposts are generated from the supplement's capabilities.
