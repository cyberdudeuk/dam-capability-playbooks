#!/usr/bin/env python3
"""Real-browser checks (Playwright, Chromium). Serves the site locally, then checks every page.

Usage: python tools/check_browser.py [--site site] [--axe node_modules/axe-core/axe.min.js]
Pass --break NAME to apply a deliberate break and prove the matching check fails (vaccination, VER-05).
"""
import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
WIDTHS = [320, 390, 768, 1024, 1440, 1920]
FOCUS_YELLOW = 'rgb(255, 221, 0)'


def serve(site):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass
    handler = functools.partial(Quiet, directory=str(site))
    httpd = socketserver.TCPServer(('127.0.0.1', 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}'


BREAKS = {
    # name: (check it should trip, JS run on the page before checks)
    'overflow': ('b02_no_horizontal_overflow', "document.querySelector('main').insertAdjacentHTML('afterbegin','<div class=\"x\">'+'W'.repeat(400)+'</div>');var s=document.createElement('style');document.head.appendChild(s);"),
    'contrast': ('b01_axe', "document.querySelector('h1').setAttribute('class','lowc');document.querySelectorAll('main p').forEach(function(p){p.classList.add('lowc')});"),
    'focusfill': ('b03_container_focus', "document.documentElement.classList.add('break-focus');"),
    'consoleerror': ('b04_no_console_errors', "console.error('deliberate break');"),
    'search': ('b05_keyboard', "window.DCP_INDEX.length = 0;"),
    'tabs': ('b06_tabs', "document.querySelectorAll('[role=tablist]').forEach(function(l){l.replaceWith(l.cloneNode(true))});"),
    'filters': ('b08_filters', "document.querySelectorAll('.filters select').forEach(function(x){x.replaceWith(x.cloneNode(true))});"),
    'noscript': ('b07_no_script', ""),
}
BREAK_CSS = {
    'overflow': '.x{white-space:nowrap;font-size:20px}',
    'contrast': '.lowc{color:#cccccc!important}',
    'focusfill': '.break-focus [role="tabpanel"]:focus-visible,.break-focus .table-wrap:focus-visible{background:#ffdd00!important}',
}


def run(site, axe_path, brk=None, pages=None):
    site = Path(site)
    pages = pages or sorted(p.name for p in site.glob('*.html'))
    axe = Path(axe_path).read_text(encoding='utf-8')
    httpd, base = serve(site)
    failed = {}

    def fail(check, msg):
        failed.setdefault(check, []).append(msg)

    def prep(pg):
        if brk:
            if brk in BREAK_CSS:
                pg.add_style_tag(content=BREAK_CSS[brk])
            if BREAKS[brk][1]:
                pg.evaluate(BREAKS[brk][1])

    with sync_playwright() as p:
        b = p.chromium.launch()
        # B-01 axe (WCAG 2.2 AA, light and dark), B-04 console errors
        for scheme in ('light', 'dark'):
            ctx = b.new_context(viewport={'width': 1280, 'height': 900}, color_scheme=scheme, bypass_csp=bool(brk))
            pg = ctx.new_page()
            errors = []
            pg.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
            pg.on('pageerror', lambda e: errors.append(str(e)))
            for name in pages:
                errors.clear()
                pg.goto(f'{base}/{name}')
                pg.wait_for_load_state('load')
                prep(pg)
                pg.add_script_tag(content=axe) if False else pg.evaluate(axe)
                # reveal every tab panel so axe sees all content
                pg.evaluate("document.querySelectorAll('[role=tabpanel][hidden]').forEach(function(p){p.hidden=false})")
                res = pg.evaluate("""async () => { const r = await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa','best-practice']}});
                    return r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical').map(v => v.id + ' (' + v.nodes.length + '): ' + v.nodes[0].target.join(' ')); }""")
                for v in res:
                    fail('b01_axe', f'{name} [{scheme}] {v}')
                if errors:
                    fail('b04_no_console_errors', f'{name} [{scheme}] {errors[:3]}')
            ctx.close()
        # B-02 overflow at every width
        ctx = b.new_context(bypass_csp=bool(brk))
        pg = ctx.new_page()
        for w in WIDTHS:
            pg.set_viewport_size({'width': w, 'height': 900})
            for name in pages:
                pg.goto(f'{base}/{name}')
                prep(pg)
                pg.evaluate("document.querySelectorAll('[role=tabpanel][hidden]').forEach(function(p){p.hidden=false})")
                over = pg.evaluate('document.documentElement.scrollWidth - document.documentElement.clientWidth')
                if over > 0:
                    fail('b02_no_horizontal_overflow', f'{name} at {w}px overflows by {over}px')
        # B-03 containers never fill with the focus colour (D-004)
        pg.set_viewport_size({'width': 1280, 'height': 900})
        for name in ('governance.html', 'knowledge.html', 'dam.html'):
            pg.goto(f'{base}/{name}')
            prep(pg)
            for sel in ('[role="tabpanel"]:not([hidden])', '.table-wrap'):
                if not pg.locator(sel).count():
                    continue
                pg.keyboard.press('Tab')
                pg.locator(sel).first.focus()
                pg.evaluate("document.documentElement.classList.add('kbd')")
                bg = pg.evaluate(f"""() => {{ const el = document.querySelector('{sel}'); el.focus({{focusVisible:true}}); return getComputedStyle(el).backgroundColor; }}""")
                if bg == FOCUS_YELLOW:
                    fail('b03_container_focus', f'{name} {sel} fills with the focus colour')
        # B-05 keyboard: palette opens and closes and returns focus; Escape closes the drawer on narrow screens
        pg.goto(f'{base}/index.html')
        prep(pg)
        pg.locator('[data-open-search]').focus()
        pg.keyboard.press('Control+k')
        if pg.locator('#palette').is_hidden():
            fail('b05_keyboard', 'Ctrl+K does not open search')
        pg.keyboard.type('owner')
        n = pg.locator('#palette-list a').count()
        if n == 0:
            fail('b05_keyboard', 'search for "owner" finds nothing')
        pg.keyboard.press('Escape')
        if not pg.locator('#palette').is_hidden():
            fail('b05_keyboard', 'Escape does not close search')
        if pg.evaluate("document.activeElement && document.activeElement.hasAttribute('data-open-search')") is not True:
            fail('b05_keyboard', 'focus does not return to the search button')
        pg.set_viewport_size({'width': 390, 'height': 800})
        pg.goto(f'{base}/governance.html')
        pg.locator('#drawer-toggle').click()
        if pg.locator('#drawer').is_hidden():
            fail('b05_keyboard', 'drawer toggle does not open the drawer on a phone')
        pg.keyboard.press('Escape')
        if not pg.locator('#drawer').is_hidden():
            fail('b05_keyboard', 'Escape does not close the drawer on a phone')
        # B-06 tabs: arrow keys move between tabs; a hash opens the right tab
        pg.set_viewport_size({'width': 1280, 'height': 900})
        pg.goto(f'{base}/quality.html')
        prep(pg)
        pg.locator('#tab-overview').focus()
        pg.keyboard.press('ArrowRight')
        if pg.locator('#method').is_hidden():
            fail('b06_tabs', 'ArrowRight does not open the next tab')
        pg.goto(f'{base}/cataloguing.html#metadata')
        if pg.locator('#method').is_hidden():
            fail('b06_tabs', 'deep link to #metadata does not open the Method tab')
        # B-07 script blocked: content still readable (degraded mode)
        ctx2 = b.new_context(java_script_enabled=False)
        pg2 = ctx2.new_page()
        if brk == 'noscript':
            css = (site / 'assets' / 'style.css').read_text(encoding='utf-8').replace('.no-js .tabs [role="tabpanel"][hidden]{display:block}', '')
            pg2.route('**/assets/style.css', lambda r: r.fulfill(status=200, content_type='text/css', body=css))
        pg2.goto(f'{base}/governance.html')
        if not pg2.locator('#method').is_visible():
            fail('b07_no_script', 'with scripts blocked, the Method panel is hidden')
        ctx2.close()
        # B-08 filters bind to change and report counts
        pg.goto(f'{base}/library.html')
        prep(pg)
        pg.select_option('#l-cap', 'dq')
        shown = pg.evaluate("document.querySelectorAll('#lib-table [data-item]:not([hidden])').length")
        total = pg.evaluate("document.querySelectorAll('#lib-table [data-item]').length")
        if not (0 < shown < total):
            fail('b08_filters', f'capability filter shows {shown} of {total}')
        b.close()
    httpd.shutdown()
    return failed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--site', default=str(ROOT / 'site'))
    ap.add_argument('--axe', default=str(ROOT / 'node_modules' / 'axe-core' / 'axe.min.js'))
    ap.add_argument('--break', dest='brk', choices=sorted(BREAKS))
    a = ap.parse_args(argv)
    failed = run(a.site, a.axe, a.brk)
    if a.brk:
        want = BREAKS[a.brk][0]
        ok = want in failed
        print(('pass ' if ok else 'FAIL ') + f'vaccination {a.brk}: {want} ' + ('caught the break' if ok else 'did not catch the break'))
        return 0 if ok else 1
    names = ['b01_axe', 'b02_no_horizontal_overflow', 'b03_container_focus', 'b04_no_console_errors', 'b05_keyboard', 'b06_tabs', 'b07_no_script', 'b08_filters']
    for n in names:
        print(('FAIL ' if n in failed else 'pass ') + n)
        for e in failed.get(n, [])[:15]:
            print('     ', e)
    print(f'{len(names) - len(failed)} of {len(names)} browser checks passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
