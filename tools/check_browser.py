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
    'contact': ('b09_contact_form', "var f=document.getElementById('contact-form');if(f){f.replaceWith(f.cloneNode(true));}"),
    'progress': ('b10_progress', "Storage.prototype.setItem=function(){};"),
    'display': ('b11_display', "var d=document.getElementById('display-panel');if(d){d.replaceWith(d.cloneNode(true));}"),
    'finder': ('b12_sector_finder', "document.querySelectorAll('input[data-q]').forEach(function(x){x.replaceWith(x.cloneNode(true))});"),
    'navclip': ('b14_menus_usable', ""),
    'damarole': ('b15_dama_role', "var x=document.getElementById('dama-role');if(x){x.replaceWith(x.cloneNode(true));}"),
    'tours': ('b16_tours_and_share', ""),
    'compass': ('b17_compass', "var f=document.getElementById('wayfinder');if(f){f.replaceWith(f.cloneNode(true));}"),
    'selfassess': ('b13_self_assessment', "document.querySelectorAll('[data-sa]').forEach(function(x){x.replaceWith(x.cloneNode(true))});"),
}
BREAK_CSS = {
    'tours': '.tour-box{display:none!important}',
    'navclip': '.gbar ul.top{overflow:hidden!important}',
    'overflow': '.x{white-space:nowrap;font-size:20px}',
    'contrast': '.lowc{color:#cccccc!important}',
    'focusfill': '.break-focus [role="tabpanel"]:focus-visible,.break-focus .table-wrap:focus-visible{background:#ffdd00!important}',
}


def run(site, axe_path, brk=None, pages=None):
    site = Path(site)
    pages = pages or sorted(p.name for p in site.glob('*.html')) + (['compass/index.html'] if (site / 'compass' / 'index.html').exists() else [])
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
        # B-09 contact form: errors are summarised and focused; a valid form opens a pre-filled GitHub issue form
        pg.goto(f'{base}/contact.html')
        prep(pg)
        pg.click('#contact-form button[type=submit]')
        if pg.locator('#cf-errors').is_hidden() or pg.evaluate("document.activeElement.id") != 'cf-errors':
            fail('b09_contact_form', 'empty submission does not show and focus the error summary')
        elif pg.evaluate("Array.from(document.querySelectorAll('#cf-errors a')).some(a => !document.getElementById(a.getAttribute('href').slice(1)))"):
            fail('b09_contact_form', 'an error summary link points to a field that does not exist (D-011)')
        else:
            pg.check('#contact-form input[name=kind] >> nth=0')
            pg.fill('#cf-detail', 'Test message')
            pg.check('#cf-privacy')
            captured = []
            pg.route('https://github.com/**', lambda r: (captured.append(r.request.url), r.fulfill(status=200, body='ok')))
            pg.click('#contact-form button[type=submit]')
            pg.wait_for_timeout(500)
            if not captured or 'template=contact.yml' not in captured[0] or 'detail=Test+message' not in captured[0]:
                fail('b09_contact_form', f'valid submission did not open the pre-filled issue form ({captured[:1]})')
        # B-10 progress persists across pages and shows on the role route
        ctx3 = b.new_context(bypass_csp=bool(brk))
        pg3 = ctx3.new_page()
        pg3.goto(f'{base}/governance.html#method')
        prep(pg3)
        pg3.check('input[data-progress="gov.mandate"]')
        pg3.goto(f'{base}/personas.html')
        txt = pg3.locator('#p-cdo .progress-text').first.text_content() or ''
        if not txt.startswith('1 of'):
            fail('b10_progress', f'marking a step did not show on the chief data officer route ("{txt}")')
        ctx3.close()
        # B-11 display options change text size and are remembered
        pg.goto(f'{base}/index.html')
        prep(pg)
        try:
            pg.click('#display-toggle', timeout=3000)
            pg.check('input[name=dp-text][value=xl]', timeout=3000)
            pg.reload()
            if pg.evaluate("document.documentElement.getAttribute('data-text')") != 'xl':
                fail('b11_display', 'largest text size was not applied and remembered')
        except Exception as e:  # a control that cannot be used is a failure, not a crash
            fail('b11_display', f'display options could not be used: {str(e).splitlines()[0]}')
        # B-12 sector finder: ticking a statement lists the supplements that apply, as links that resolve
        pg.goto(f'{base}/sectors.html')
        prep(pg)
        pg.check('input[data-q] >> nth=0')
        links = pg.evaluate("Array.from(document.querySelectorAll('#wizard-out a')).map(a => a.getAttribute('href'))")
        if not links:
            fail('b12_sector_finder', 'ticking a statement listed no supplements')
        elif pg.evaluate("(l) => l.some(h => !document.getElementById(h.slice(1)))", links):
            fail('b12_sector_finder', 'a listed supplement does not exist on the page')
        # B-13 self-assessment: answers draw the profile, survive a reload and can be cleared
        ctx4 = b.new_context(bypass_csp=bool(brk))
        pg4 = ctx4.new_page()
        pg4.goto(f'{base}/capability-model.html#cm-self')
        prep(pg4)
        try:
            pg4.check('input[name="sa-own"][value="3"]', timeout=3000)
            pg4.select_option('#sa-t1', '4', timeout=3000)
            if pg4.locator('#sa-chart polygon.area').count() != 1:
                fail('b13_self_assessment', 'choosing a level did not draw the profile')
            pg4.reload()
            if not pg4.is_checked('input[name="sa-own"][value="3"]') or pg4.input_value('#sa-t1') != '4':
                fail('b13_self_assessment', 'answers were not remembered after a reload')
            if 'data:text/csv' not in (pg4.get_attribute('#sa-csv', 'href') or ''):
                fail('b13_self_assessment', 'the CSV download was not prepared')
            pg4.click('#sa-clear')
            if pg4.locator('#sa-chart polygon.area').count() != 0:
                fail('b13_self_assessment', 'clearing answers left the profile drawn')
        except Exception as e:
            fail('b13_self_assessment', f'self-assessment could not be used: {str(e).splitlines()[0]}')
        ctx4.close()
        # B-15 (version 1.7): choosing a role on the DAMA wheel opens every area's guidance with that role highlighted
        pg.goto(f'{base}/capability-model.html#cm-dama')
        prep(pg)
        try:
            pg.select_option('#dama-role', 'prg', timeout=3000)
            n_open = pg.evaluate("document.querySelectorAll('.dama-uses[open]').length")
            n_all = pg.evaluate("document.querySelectorAll('.dama-uses').length")
            n_me = pg.evaluate("document.querySelectorAll('.dama-uses tr.me').length")
            if not n_all or n_open != n_all or n_me != n_all:
                fail('b15_dama_role', f'role choice opened {n_open} of {n_all} areas and highlighted {n_me}')
            seg = pg.evaluate("(() => { const a = document.querySelector('.dama-wheel a'); return a ? a.getAttribute('href') : null; })()")
            if not seg or not pg.evaluate("(h) => !!document.getElementById(h.slice(1))", seg):
                fail('b15_dama_role', 'wheel segments do not link to their area')
        except Exception as e:
            fail('b15_dama_role', f'DAMA role choice could not be used: {str(e).splitlines()[0]}')
        # B-16 (version 1.8): every guided tour opens, shows each step next to a visible target, and closes; the share menu copies a link
        ctx6 = b.new_context(viewport={'width': 1280, 'height': 900}, bypass_csp=bool(brk))
        try:
            ctx6.grant_permissions(['clipboard-read', 'clipboard-write'])
        except Exception:
            pass
        pg6 = ctx6.new_page()
        tour_pages = [n for n in pages if n != '404.html']
        for name in tour_pages:
            pg6.goto(f'{base}/{name}')
            tours = pg6.evaluate("(() => { const s = document.getElementById('tour-data'); return s ? JSON.parse(s.textContent) : []; })()")
            for tour in tours:
                if tour.get('page') and tour['page'] + '.html' != name:
                    continue
                pg6.goto(f'{base}/{name}#tour={tour["id"]}')
                pg6.reload()
                prep(pg6)
                try:
                    pg6.wait_for_selector('.tour-box', state='attached', timeout=3000)
                    for i, st in enumerate(tour['steps']):
                        pg6.wait_for_timeout(120)
                        vis = pg6.evaluate("""(sel) => { const box = document.querySelector('.tour-box'); const t = document.querySelector(sel);
                            const seen = n => { if (!n) return false; const r = n.getBoundingClientRect(); const cs = getComputedStyle(n); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
                            return {box: seen(box), target: seen(t), marked: !!(t && t.classList.contains('tour-target'))}; }""", st['sel'])
                        if not (vis['box'] and vis['target'] and vis['marked']):
                            fail('b16_tours_and_share', f'{name} tour {tour["id"]} step {i + 1} "{st["title"]}": {vis}')
                            break
                        pg6.locator('.tour-box [data-t="next"], .tour-box [data-t="end"].btn:not(.secondary)').first.click(timeout=2000)
                    pg6.wait_for_timeout(120)
                    if pg6.locator('.tour-box').count():
                        fail('b16_tours_and_share', f'{name} tour {tour["id"]}: the tour did not close at the end')
                except Exception as e:
                    fail('b16_tours_and_share', f'{name} tour {tour["id"]}: could not be used: {str(e).splitlines()[0]}')
        pg6.goto(f'{base}/tooling.html')
        prep(pg6)
        try:
            pg6.click('details.share > summary', timeout=2000)
            pg6.click('details.share [data-copy-link]', timeout=2000)
            pg6.wait_for_timeout(200)
            msg = pg6.inner_text('details.share .share-status')
            if not msg.strip():
                fail('b16_tours_and_share', 'copying the link gave no confirmation')
            mail = pg6.get_attribute('details.share a[href^="mailto:"]', 'href') or ''
            if not mail.startswith('mailto:?'):
                fail('b16_tours_and_share', 'the email share link names a recipient')
        except Exception as e:
            fail('b16_tours_and_share', f'share menu could not be used: {str(e).splitlines()[0]}')
        ctx6.close()
        # B-17 (version 1.8.2): the estate compass gives a route for every situation, turns its needle to the starting portal,
        # keeps the answers in the address, and restores the route from a shared link
        if (site / 'compass' / 'index.html').exists():
            ctx7 = b.new_context(viewport={'width': 1280, 'height': 900}, bypass_csp=bool(brk))
            pg7 = ctx7.new_page()
            pg7.goto(f'{base}/compass/index.html')
            prep(pg7)
            try:
                data = pg7.evaluate("JSON.parse(document.getElementById('data').textContent)")
                for o in data['questions'][0]['options']:
                    pg7.check(f'input[name=why][value={o["id"]}]', timeout=2000)
                    pg7.wait_for_timeout(100)
                    want = len(data['routes'][o['id']]['steps'])
                    got = pg7.locator('#route ol.steps > li').count()
                    if got != want:
                        fail('b17_compass', f'situation {o["id"]}: {got} steps shown, route has {want}')
                    first = data['routes'][o['id']]['steps'][0]['p']
                    name = next(p['short'] for p in data['portals'] if p['id'] == first)
                    if name not in pg7.inner_text('#bearing-now'):
                        fail('b17_compass', f'situation {o["id"]}: the compass does not point to {name}')
                pg7.check('input[name=role][value=owner]'); pg7.check('input[name=scope][value=none]'); pg7.check('input[name=skill][value=new]')
                h = pg7.evaluate('location.hash')
                if '/' not in h or 'owner' not in h:
                    fail('b17_compass', f'answers are not kept in the address: {h}')
                pg7.goto(f'{base}/compass/index.html#bearing/quality,owner,none,new')
                pg7.reload()
                pg7.wait_for_timeout(200)
                if pg7.locator('#route ol.steps > li').count() == 0 or pg7.locator('.flagnote').count() == 0:
                    fail('b17_compass', 'a shared link does not restore the route, or optional policy steps are not marked for an organisation outside the policy')
            except Exception as e:
                fail('b17_compass', f'compass could not be used: {str(e).splitlines()[0]}')
            ctx7.close()
        # B-14 (D-022): every grouped menu opens, its links can actually be clicked, and they navigate, on desktop and phone
        for w in (1440, 390):
            ctx5 = b.new_context(viewport={'width': w, 'height': 900}, bypass_csp=bool(brk))
            pg5 = ctx5.new_page()
            pg5.goto(f'{base}/index.html')
            prep(pg5)
            groups = pg5.evaluate("Array.from(document.querySelectorAll('#gbar li.group > button')).map(b => b.textContent.trim())")
            if not groups:
                fail('b14_menus_usable', f'{w}px: no grouped menus found')
            for gi, name in enumerate(groups):
                pg5.goto(f'{base}/index.html')
                prep(pg5)
                pg5.wait_for_timeout(150)
                btn = pg5.locator('#gbar li.group > button').nth(gi)
                try:
                    if not btn.is_visible():
                        pg5.locator('#gbar li.more > button').click(timeout=2000)
                    btn.click(timeout=2000)
                    pg5.wait_for_timeout(150)
                    hit = pg5.evaluate("""(gi) => { const li = document.querySelectorAll('#gbar li.group')[gi]; const a = li && li.querySelector('ul a');
                        if (!a) return 'no link'; const r = a.getBoundingClientRect(); if (!r.width || !r.height) return 'link has no size';
                        const e = document.elementFromPoint(r.x + Math.min(10, r.width / 2), r.y + r.height / 2);
                        return e && (e === a || a.contains(e)) ? 'ok' : 'link is covered or clipped'; }""", gi)
                    if hit != 'ok':
                        fail('b14_menus_usable', f'{w}px "{name}": {hit}')
                        continue
                    href = pg5.evaluate("(gi) => document.querySelectorAll('#gbar li.group')[gi].querySelector('ul a').getAttribute('href')", gi)
                    pg5.locator('#gbar li.group').nth(gi).locator('ul a').first.click(timeout=2000)
                    pg5.wait_for_load_state()
                    if not pg5.url.endswith(href):
                        fail('b14_menus_usable', f'{w}px "{name}": clicking the first item did not open {href}')
                except Exception as e:
                    fail('b14_menus_usable', f'{w}px "{name}": menu could not be used: {str(e).splitlines()[0]}')
            ctx5.close()
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
    names = ['b01_axe', 'b02_no_horizontal_overflow', 'b03_container_focus', 'b04_no_console_errors', 'b05_keyboard', 'b06_tabs', 'b07_no_script', 'b08_filters',
             'b09_contact_form', 'b10_progress', 'b11_display', 'b12_sector_finder', 'b13_self_assessment', 'b14_menus_usable', 'b15_dama_role', 'b16_tours_and_share', 'b17_compass']
    for n in names:
        print(('FAIL ' if n in failed else 'pass ') + n)
        for e in failed.get(n, [])[:15]:
            print('     ', e)
    print(f'{len(names) - len(failed)} of {len(names)} browser checks passed')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
