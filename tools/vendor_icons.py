#!/usr/bin/env python3
"""Copy the icons the portal uses from the pinned lucide-static package into site_src/icons.json.

Run after changing ICON_NAMES or the lucide-static version: python tools/vendor_icons.py
The icons are ISC-licensed (see THIRD-PARTY-NOTICES.md). Only the inner SVG markup is kept.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ICON_NAMES = """house landmark shield-check library-big gauge workflow users-round graduation-cap library network info
message-square-text search moon sun circle-check list-checks clock flag file-text triangle-alert tag refresh-cw building-2
clipboard-list key-round user-cog database chart-line users gavel lock-keyhole server scale user-search scroll-text
book-marked user-check settings-2 clipboard-check stamp pencil-line share-2 send calendar-clock crosshair ruler chart-column
list-ordered wrench presentation activity calendar-check accessibility heart-handshake target lightbulb circle-help book-open
route map arrow-right download printer type award timer layers circle chevron-down chevron-right x rotate-ccw panel-left
compass milestone badge-check signpost hand-helping languages eye brain a-large-small sliders-horizontal play link
banknote construction handshake arrow-right-left trending-up radar archive briefcase grid-3x3 school
ban check circle-x code-xml footprints git-branch history kanban map-pin megaphone mountain navigation package plug sparkles thumbs-up trophy vote""".split()


def main():
    src = ROOT / 'node_modules' / 'lucide-static' / 'icons'
    version = json.loads((ROOT / 'node_modules' / 'lucide-static' / 'package.json').read_text())['version']
    out, missing = {}, []
    for n in ICON_NAMES:
        f = src / f'{n}.svg'
        if not f.exists():
            missing.append(n)
            continue
        inner = re.search(r'<svg[^>]*>(.*)</svg>', f.read_text(), re.S).group(1)
        inner = re.sub(r'\s*\n\s*', '', inner).replace(' />', '/>')
        out[n] = inner
    if missing:
        print('missing icons: ' + ', '.join(missing), file=sys.stderr)
        return 1
    (ROOT / 'site_src' / 'icons.json').write_text(json.dumps({'source': 'lucide-static', 'version': version, 'licence': 'ISC', 'icons': out}, indent=0, sort_keys=True))
    print(f'{len(out)} icons from lucide-static {version}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
