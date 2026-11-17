# Keeping the playbooks, the compass and the explorer joined

Version 1.16.0, 17 November 2026. This page records how the three ways in to the same material reach each other, which
cross-references keep them aligned, and the priority (MoSCoW) of each. Check C-47 enforces every Must.

- **The playbooks** (this portal): the capability model, the three capability playbooks, capability playbooks, knowledge areas.
- **The data portals compass** (`compass/`): one page that finds your way across four websites, with a DAMA wheel and a directory.
- **The asset governance explorer** (`explorer/`): where data asset management meets information asset management.

All three use the same 32 capability identifiers, CR-01 to CR-32, from `content/frameworks.yaml` (`capmap`). That shared key
is what keeps them aligned.

## How each is reached today

| From | To the compass | To the explorer | Back to the playbooks |
|---|---|---|---|
| Every playbooks page | Global bar, Find your way menu; footer | Global bar, Find your way menu; footer | n/a |
| Capability model, each capability | "See this capability in" row | "See this capability in" row (opens the Capabilities view) | n/a |
| Capability playbooks, each capability | "See this capability in" row | "See this capability in" row | n/a |
| Knowledge areas | Link to the compass lineage view | Not yet (Should, below) | n/a |
| The compass | n/a | Directory entry | Directory lists every playbooks page; wheel links each capability to its page |
| The explorer | Not yet (Should, below) | n/a | Links to the playbooks home |

Before this release the compass and the explorer were reached only from the footer, and from seven pages' related-links
panels for the compass. Nothing checked that the three named the capabilities the same way.

## Cross-references by priority

| Priority | Cross-reference | Status | Check |
|---|---|---|---|
| Must | Every page reaches the compass and the explorer from the global bar | Done | C-47 |
| Must | The compass wheel and the explorer list the same 32 capability identifiers, with the same names, as the capability model | Done | C-47 |
| Must | Every capability on the capability model links to its playbook, the compass and the explorer | Done | C-47 |
| Must | The compass directory lists every playbooks page, including Capability playbooks and New or leading, and the explorer | Done | C-47, C-35 |
| Must | The explorer links back to the playbooks | Done | C-47 |
| Must | Every link into a hash-routed view resolves to a view the page declares | Done | C-03 |
| Should | The compass wheel drills down to capability playbook activities, as it does to knowledge area activities | Backlog | |
| Should | The explorer links each capability to its capability model entry and to the compass | Backlog: the explorer is produced from a working edition by its own checked transform, so the change belongs there | |
| Should | Knowledge areas link to the explorer's information wheel where an area is shared with information management | Backlog | |
| Could | One release note across the three, so a change to a capability shows in all three at once | Backlog | |
| Could | A shared machine-readable capability list (`data/xref.json` already carries the keys) that the compass and explorer read at build time instead of keeping their own copies | Backlog | |
| Won't (this time) | Merge the three into one page | Rejected: each serves a different starting point, and the shared key and checks give one source of truth without merging | |

## The case against, and the answer

*Three ways in to the same material is two too many.* Each starts from a different question: what do I do (playbooks),
where is it across four websites (compass), how does this meet information management (explorer). The shared key and C-47
mean a change to a capability's name or number fails the build until all three agree, so they cannot drift apart silently.
