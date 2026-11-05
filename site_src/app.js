/* Data Asset Management (DAM) capability playbooks: progressive enhancement.
   Every page can be read without this file. Shed order when scripts fail (SR18): search, progress tracking,
   display options, tooltips, filters, graph highlighting. Content, tables and links never depend on it. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.remove('no-js');
  var mem = {};
  var store = {
    get: function (k) { try { var v = window.localStorage.getItem(k); return v === null ? (mem[k] || null) : v; } catch (e) { return mem[k] || null; } },
    set: function (k, v) { mem[k] = v; try { window.localStorage.setItem(k, v); } catch (e) { /* in-memory only */ } },
    del: function (k) { delete mem[k]; try { window.localStorage.removeItem(k); } catch (e) { /* ignore */ } }
  };
  function $(s, r) { return (r || doc).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function json(id) { var n = doc.getElementById(id); if (!n) return null; try { return JSON.parse(n.textContent); } catch (e) { return null; } }
  var narrow = window.matchMedia('(max-width: 60rem)');

  /* display options: text size, spacing, colours */
  var dp = { text: store.get('dcp-text') || '', space: store.get('dcp-space') || '', theme: store.get('dcp-theme') || '' };
  function applyDisplay() {
    if (dp.text) root.setAttribute('data-text', dp.text); else root.removeAttribute('data-text');
    if (dp.space) root.setAttribute('data-space', dp.space); else root.removeAttribute('data-space');
    if (dp.theme) root.setAttribute('data-theme', dp.theme); else root.removeAttribute('data-theme');
  }
  applyDisplay();
  var dpBtn = $('#display-toggle'), dpPanel = $('#display-panel');
  if (dpBtn && dpPanel) {
    dpBtn.hidden = false;
    [['dp-text', 'text'], ['dp-space', 'space'], ['dp-theme', 'theme']].forEach(function (pair) {
      $$('input[name="' + pair[0] + '"]', dpPanel).forEach(function (r) {
        r.checked = r.value === dp[pair[1]];
        r.addEventListener('change', function () { dp[pair[1]] = r.value; store.set('dcp-' + pair[1], r.value); applyDisplay(); });
      });
    });
    dpBtn.addEventListener('click', function () {
      var open = dpPanel.hidden; dpPanel.hidden = !open; dpBtn.setAttribute('aria-expanded', String(open));
      if (open) { var f = dpPanel.querySelector('input:checked') || dpPanel.querySelector('input'); if (f) f.focus(); }
    });
  }

  /* drawer: in-page navigation only */
  var drawer = $('#drawer'), dsw = $('#drawer-toggle');
  function setDrawer(open, save) {
    if (!drawer || !dsw) return;
    drawer.hidden = !open;
    dsw.setAttribute('aria-checked', open ? 'true' : 'false');
    if (save && !narrow.matches) store.set('dcp-drawer', open ? '1' : '0');
  }
  if (drawer && dsw) {
    dsw.hidden = false;
    setDrawer(narrow.matches ? false : store.get('dcp-drawer') !== '0', false);
    dsw.addEventListener('click', function () {
      var open = dsw.getAttribute('aria-checked') !== 'true';
      setDrawer(open, true);
      if (open && narrow.matches) { var f = drawer.querySelector('a,summary'); if (f) f.focus(); }
    });
    drawer.addEventListener('click', function (e) { if (e.target.closest('a') && narrow.matches) setDrawer(false, false); });
    var onMq = function () { setDrawer(narrow.matches ? false : store.get('dcp-drawer') !== '0', false); };
    if (narrow.addEventListener) narrow.addEventListener('change', onMq); else if (narrow.addListener) narrow.addListener(onMq);
  }

  /* global bar: fold overflowing items into a More menu */
  var bar = $('#gbar');
  function fold() {
    if (!bar) return;
    var list = bar.querySelector('ul.top'), more = bar.querySelector('li.more'), mlist = more && more.querySelector('ul');
    if (!list || !more) return;
    $$('li', mlist).forEach(function (li) { list.insertBefore(li, more); });
    more.hidden = true; bar.classList.add('folding');
    var guard = 0;
    while (list.scrollWidth > list.clientWidth + 1 && guard++ < 20) {
      more.hidden = false;
      var items = $$(':scope > li:not(.more)', list);
      if (items.length < 2) break;
      var last = items[items.length - 1];
      if ((last.querySelector('[aria-current]') || last.classList.contains('current')) && items.length > 2) last = items[items.length - 2];
      mlist.insertBefore(last, mlist.firstChild);
    }
    if (!mlist.children.length) more.hidden = true;
  }
  if (bar) {
    $$('li.group > button', bar).forEach(function (gb) {
      gb.addEventListener('click', function () {
        var li = gb.parentNode, open = !li.classList.contains('open');
        $$('li.group.open', bar).forEach(function (o) { if (o !== li) { o.classList.remove('open'); o.querySelector('button').setAttribute('aria-expanded', 'false'); } });
        li.classList.toggle('open', open); gb.setAttribute('aria-expanded', String(open));
      });
    });
    doc.addEventListener('click', function (e) { if (!e.target.closest('#gbar')) $$('li.group.open,li.more.open', bar).forEach(function (o) { o.classList.remove('open'); o.querySelector('button').setAttribute('aria-expanded', 'false'); }); });
    var mb = bar.querySelector('li.more > button');
    if (mb) mb.addEventListener('click', function () {
      var li = mb.parentNode, open = !li.classList.contains('open');
      li.classList.toggle('open', open); mb.setAttribute('aria-expanded', String(open));
    });
    fold();
    var ft; window.addEventListener('resize', function () { clearTimeout(ft); ft = setTimeout(fold, 80); });
  }

  /* tabs */
  function activate(tab, focus) {
    var list = tab.closest('[role="tablist"]');
    $$('[role="tab"]', list).forEach(function (t) {
      var on = t === tab;
      t.setAttribute('aria-selected', on ? 'true' : 'false');
      t.tabIndex = on ? 0 : -1;
      var p = doc.getElementById(t.getAttribute('aria-controls'));
      if (p) p.hidden = !on;
    });
    if (focus) tab.focus();
  }
  $$('[role="tablist"]').forEach(function (list) {
    list.addEventListener('click', function (e) { var t = e.target.closest('[role="tab"]'); if (t) { activate(t); history.replaceState(null, '', '#' + t.getAttribute('aria-controls')); } });
    list.addEventListener('keydown', function (e) {
      var tabs = $$('[role="tab"]', list), i = tabs.indexOf(doc.activeElement);
      if (i < 0) return;
      var j = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
      if (j === null) return;
      e.preventDefault(); activate(tabs[(j + tabs.length) % tabs.length], true);
    });
  });
  function openFromHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return;
    var target = doc.getElementById(id);
    if (!target) return;
    var panel = target.closest('[role="tabpanel"]');
    if (panel) { var tab = doc.querySelector('[role="tab"][aria-controls="' + panel.id + '"]'); if (tab) activate(tab); }
    var det = target.tagName === 'DETAILS' ? target : (target.classList.contains('sbs-step') ? target.querySelector('details.sbs-details') : null);
    if (det) det.open = true;
    if (target !== panel) target.scrollIntoView();
  }
  window.addEventListener('hashchange', openFromHash);
  openFromHash();

  /* step by step: show or hide all steps */
  $$('[data-sbs-all]').forEach(function (b) {
    var box = b.closest('[data-sbs]');
    b.addEventListener('click', function () {
      var open = b.getAttribute('aria-expanded') !== 'true';
      $$('details.sbs-details', box).forEach(function (d) { d.open = open; });
      b.setAttribute('aria-expanded', String(open));
      b.querySelector('span').textContent = open ? 'Hide all steps' : 'Show all steps';
    });
  });

  /* progress: kept in this browser only */
  var KEY = 'dcp-progress-v1', MODS = window.DCP_MODULES || {};
  var state = {};
  (store.get(KEY) || '').split(' ').forEach(function (k) { if (k) state[k] = 1; });
  function save() { store.set(KEY, Object.keys(state).join(' ')); }
  function isDone(id) {
    if (id.indexOf('mod:') === 0) { var acts = MODS[id.slice(4)] || []; return acts.length > 0 && acts.every(function (a) { return state[a]; }); }
    return !!state[id];
  }
  function refresh() {
    $$('input[data-progress]').forEach(function (c) { c.checked = !!state[c.getAttribute('data-progress')]; var li = c.closest('.sbs-step,.activity,li'); if (li) li.classList.toggle('is-done', c.checked); });
    $$('[data-progress-of]').forEach(function (el) {
      var ids = el.getAttribute('data-progress-of').split(' ').filter(Boolean), n = ids.filter(isDone).length;
      el.querySelector('.fill').style.width = (ids.length ? Math.round(n / ids.length * 100) : 0) + '%';
      el.querySelector('.progress-text').textContent = n + ' of ' + ids.length + ' done';
      el.classList.toggle('complete', n === ids.length && n > 0);
    });
    $$('[data-status-of]').forEach(function (el) {
      var ids = el.getAttribute('data-status-of').split(' ').filter(Boolean);
      var n = ids.filter(isDone).length, part = ids.some(function (id) { if (id.indexOf('mod:') === 0) return (MODS[id.slice(4)] || []).some(function (a) { return state[a]; }); return false; });
      var s = n === ids.length ? 'Completed' : (n > 0 || part) ? 'In progress' : 'Not started';
      el.textContent = s; el.className = 'status js-only s-' + s.toLowerCase().replace(' ', '-');
    });
  }
  doc.addEventListener('change', function (e) {
    var c = e.target;
    if (c.matches && c.matches('input[data-progress]')) {
      var id = c.getAttribute('data-progress');
      if (c.checked) state[id] = 1; else delete state[id];
      save(); refresh();
    }
  });
  $$('[data-progress-reset]').forEach(function (b) {
    var label = b.lastChild.textContent;
    b.addEventListener('click', function () {
      if (b.getAttribute('data-confirm') !== '1') { b.setAttribute('data-confirm', '1'); b.lastChild.textContent = 'Select again to confirm'; return; }
      state = {}; store.del(KEY); refresh(); b.removeAttribute('data-confirm'); b.lastChild.textContent = label;
    });
  });
  refresh();

  /* knowledge checks */
  $$('fieldset.kc').forEach(function (fs) {
    var btn = fs.querySelector('[data-check]'), out = fs.querySelector('.kc-feedback');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var sel = fs.querySelector('input[type="radio"]:checked');
      if (!sel) { out.textContent = 'Choose an answer first.'; out.className = 'kc-feedback'; return; }
      var right = sel.value === fs.getAttribute('data-answer');
      out.textContent = right ? 'Correct.' : 'Not quite. Open "Show the answer" to see why.';
      out.className = 'kc-feedback ' + (right ? 'ok' : 'no');
      if (right) { var d = fs.querySelector('details'); if (d) d.open = true; }
    });
  });

  /* filters */
  $$('[data-filter]').forEach(function (box) {
    var target = doc.getElementById(box.getAttribute('data-filter'));
    if (!target) return;
    var out = box.querySelector('.count-out'), controls = $$('select,input', box);
    function run() {
      var qi = box.querySelector('input[type="search"]'), q = qi ? qi.value.trim().toLowerCase() : '';
      var shown = 0, items = $$('[data-item]', target);
      items.forEach(function (it) {
        var ok = true;
        controls.forEach(function (c) {
          if (c.tagName === 'SELECT' && c.value && (it.getAttribute('data-' + c.name) || '').split(' ').indexOf(c.value) < 0) ok = false;
        });
        if (ok && q && it.textContent.toLowerCase().indexOf(q) < 0) ok = false;
        it.hidden = !ok; if (ok) shown++;
      });
      if (out) out.textContent = shown + ' of ' + items.length + ' shown';
    }
    controls.forEach(function (c) { c.addEventListener(c.tagName === 'SELECT' ? 'change' : 'input', run); });
    run();
  });

  /* sector supplement finder */
  var wiz = $('.wizard');
  if (wiz) {
    var outp = $('#wizard-out'), names = {};
    $$('#sup-list [data-sup]').forEach(function (li) { names[li.getAttribute('data-sup')] = li.querySelector('strong').textContent; });
    var showW = function () {
      var want = {};
      $$('input[data-q]', wiz).forEach(function (c) { if (c.checked) c.getAttribute('data-sups').split(' ').forEach(function (s) { want[s] = 1; }); });
      var ids = Object.keys(want);
      outp.innerHTML = ids.length ? '<ul>' + ids.map(function (s) { return '<li><a href="#' + esc(s) + '">' + esc(names[s] || s) + '</a></li>'; }).join('') + '</ul>' : 'Tick a statement to see which supplements apply.';
    };
    $$('input[data-q]', wiz).forEach(function (c) { c.addEventListener('change', showW); });
  }

  /* contact form: builds a pre-filled GitHub issue; nothing is stored here */
  var cf = $('#contact-form');
  if (cf) cf.addEventListener('submit', function (e) {
    e.preventDefault();
    var errs = [], kind = cf.querySelector('input[name="kind"]:checked'), detail = $('#cf-detail', cf), priv = $('#cf-privacy', cf);
    if (!kind) errs.push(['cf-kind-0', 'Select what your message is about']);
    if (!detail.value.trim()) errs.push(['cf-detail', 'Enter your message']);
    if (!priv.checked) errs.push(['cf-privacy', 'Confirm you have not included personal or sensitive information']);
    var box = $('#cf-errors', cf);
    if (errs.length) {
      box.querySelector('ul').innerHTML = errs.map(function (x) { return '<li><a href="#' + x[0] + '">' + esc(x[1]) + '</a></li>'; }).join('');
      box.hidden = false; box.focus(); return;
    }
    box.hidden = true;
    var p = new URLSearchParams();
    p.set('template', 'contact.yml'); p.set('title', '[Contact] ' + kind.value);
    p.set('kind', kind.value); p.set('capability', $('#cf-part', cf).value);
    p.set('page', $('#cf-page', cf).value); p.set('detail', detail.value);
    location.href = cf.getAttribute('data-target') + '?' + p.toString();
  });

  /* search palette */
  var idx = window.DCP_INDEX || [];
  var pal = $('#palette'), pin = $('#palette-input'), plist = $('#palette-list'), opener = null, sel = 0;
  function render() {
    var q = pin.value.trim().toLowerCase(), words = q.split(/\s+/).filter(Boolean);
    var hits = idx.map(function (r, i) {
      var t = r.t.toLowerCase(), h = (r.t + ' ' + r.k + ' ' + r.s).toLowerCase();
      if (!words.every(function (w) { return h.indexOf(w) >= 0; })) return null;
      var score = t === q ? 0 : t.indexOf(q) === 0 ? 1 : words.every(function (w) { return t.indexOf(w) >= 0; }) ? 2 : 3;
      return { r: r, s: score, i: i };
    }).filter(Boolean).sort(function (a, b) { return a.s - b.s || a.i - b.i; }).slice(0, 30).map(function (x) { return x.r; });
    sel = 0;
    plist.innerHTML = hits.map(function (r, i) {
      return '<li><a href="' + esc(r.u) + '" id="pr-' + i + '" role="option" aria-selected="' + (i === 0) + '">' + esc(r.t) + '<small>' + esc(r.k) + '</small></a></li>';
    }).join('') || '<li>No matches. Try fewer words.</li>';
    $('#palette-status').textContent = hits.length + ' results';
  }
  function openPal() { opener = doc.activeElement; pal.hidden = false; pin.value = ''; render(); pin.focus(); }
  function closePal() { pal.hidden = true; if (opener && opener.focus) opener.focus(); }
  if (pal) {
    $$('[data-open-search]').forEach(function (b) { b.hidden = false; b.addEventListener('click', openPal); });
    pin.addEventListener('input', render);
    pal.addEventListener('click', function (e) { if (e.target === pal) closePal(); });
    pal.addEventListener('keydown', function (e) {
      var opts = $$('a[role="option"]', plist);
      if (e.key === 'Escape') { e.preventDefault(); closePal(); }
      else if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && opts.length) {
        e.preventDefault(); sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + opts.length) % opts.length;
        opts.forEach(function (o, i) { o.setAttribute('aria-selected', String(i === sel)); });
        opts[sel].scrollIntoView({ block: 'nearest' }); pin.setAttribute('aria-activedescendant', opts[sel].id);
      } else if (e.key === 'Enter' && doc.activeElement === pin && opts[sel]) { e.preventDefault(); location.href = opts[sel].href; }
      else if (e.key === 'Tab') {
        var f = $$('input,a', pal); if (!f.length) return;
        if (e.shiftKey && doc.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
        else if (!e.shiftKey && doc.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
      }
    });
  }
  doc.addEventListener('keydown', function (e) {
    var typing = /INPUT|SELECT|TEXTAREA/.test((doc.activeElement || {}).tagName || '');
    if (pal && ((e.key === 'k' && (e.ctrlKey || e.metaKey)) || (e.key === '/' && !typing))) { e.preventDefault(); openPal(); }
    if (e.key === 'Escape') {
      if (drawer && narrow.matches && !drawer.hidden) { setDrawer(false, false); if (dsw) dsw.focus(); }
      if (dpPanel && !dpPanel.hidden) { dpPanel.hidden = true; dpBtn.setAttribute('aria-expanded', 'false'); dpBtn.focus(); }
      $$('.gbar li.more.open, .gbar li.group.open').forEach(function (li) { li.classList.remove('open'); li.querySelector('button').setAttribute('aria-expanded', 'false'); });
      hideTip();
    }
  });

  /* glossary tooltips */
  var tip = doc.createElement('div'); tip.className = 'tooltip'; tip.id = 'tooltip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true; doc.body.appendChild(tip);
  function showTip(a) {
    tip.textContent = a.getAttribute('data-tip'); tip.hidden = false;
    var r = a.getBoundingClientRect();
    tip.style.left = Math.max(8, Math.min(window.scrollX + r.left, window.scrollX + root.clientWidth - tip.offsetWidth - 8)) + 'px';
    tip.style.top = (window.scrollY + r.bottom + 6) + 'px';
    a.setAttribute('aria-describedby', 'tooltip');
  }
  function hideTip() { tip.hidden = true; $$('[data-tip][aria-describedby="tooltip"]').forEach(function (a) { a.removeAttribute('aria-describedby'); }); }
  /* version 1.8: tooltips on every element that carries data-tip, by hover and by keyboard focus */
  $$('[data-tip]').forEach(function (a) {
    a.addEventListener('mouseenter', function () { showTip(a); }); a.addEventListener('focus', function () { showTip(a); });
    a.addEventListener('mouseleave', hideTip); a.addEventListener('blur', hideTip);
  });

  /* knowledge graph */
  var g = json('graph-data'), gw = $('#graph');
  if (g && gw) {
    var detail = $('#graph-detail'), nodes = {}, adj = {};
    g.nodes.forEach(function (n) { nodes[n.id] = n; adj[n.id] = []; });
    g.edges.forEach(function (e) { adj[e[0]].push(e[1]); adj[e[1]].push(e[0]); });
    function pick(id) {
      var hot = {}; hot[id] = 1; adj[id].forEach(function (x) { hot[x] = 1; });
      gw.classList.add('dim');
      $$('.node', gw).forEach(function (el) { el.classList.toggle('hot', !!hot[el.getAttribute('data-id')]); });
      $$('line', gw).forEach(function (l) { l.classList.toggle('hot', l.getAttribute('data-a') === id || l.getAttribute('data-b') === id); });
      var n = nodes[id];
      detail.innerHTML = '<h3>' + esc(n.label) + '</h3><p>' + esc(n.kind) + (n.text ? ': ' + esc(n.text) : '') + '</p>' +
        (n.url ? '<p><a href="' + esc(n.url) + '">Open ' + esc(n.label) + '</a></p>' : '') +
        '<p>Connected to: ' + adj[id].map(function (x) { return esc(nodes[x].label); }).join('; ') + '</p>';
    }
    gw.addEventListener('click', function (e) { var n = e.target.closest('.node'); if (n) pick(n.getAttribute('data-id')); });
    gw.addEventListener('keydown', function (e) { var n = e.target.closest('.node'); if (n && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); pick(n.getAttribute('data-id')); } });
    var clr = $('#graph-clear'); if (clr) clr.addEventListener('click', function () { gw.classList.remove('dim'); detail.textContent = 'Select a shape to see what it connects to.'; });
  }
  /* self-assessment: answers kept in this browser only; draws a radar and bars with SVG built through the DOM */
  var saData = json('sa-data'), saChart = $('#sa-chart');
  if (saData && saChart) {
    var SAK = 'dcp-selfassess-v1', NS = 'http://www.w3.org/2000/svg', sa = {};
    try { sa = JSON.parse(store.get(SAK) || '{}') || {}; } catch (e) { sa = {}; }
    var el = function (n, a) { var x = doc.createElementNS(NS, n); for (var k in a) x.setAttribute(k, a[k]); return x; };
    var lvl = function (v) { return v ? v + '. ' + saData.levels[v - 1] : 'Not assessed'; };
    var drawSA = function () {
      var ts = saData.topics, n = ts.length, cx = 170, cy = 150, R = 105, done = 0;
      var svg = el('svg', { viewBox: '0 0 340 300', 'aria-hidden': 'true', focusable: 'false' });
      for (var r = 1; r <= 5; r++) {
        var ring = [];
        for (var i = 0; i < n; i++) { var a = -Math.PI / 2 + i * 2 * Math.PI / n; ring.push((cx + Math.cos(a) * R * r / 5).toFixed(1) + ',' + (cy + Math.sin(a) * R * r / 5).toFixed(1)); }
        svg.appendChild(el('polygon', { 'class': 'grid', points: ring.join(' ') }));
      }
      var pts = [];
      ts.forEach(function (t, i) {
        var a = -Math.PI / 2 + i * 2 * Math.PI / n, v = +sa[t.id] || 0; if (v) done++;
        svg.appendChild(el('line', { 'class': 'grid', x1: cx, y1: cy, x2: (cx + Math.cos(a) * R).toFixed(1), y2: (cy + Math.sin(a) * R).toFixed(1) }));
        var lx = cx + Math.cos(a) * (R + 22), ly = cy + Math.sin(a) * (R + 16);
        var tx = el('text', { 'class': 'lbl', x: lx.toFixed(1), y: (ly + 4).toFixed(1), 'text-anchor': Math.abs(Math.cos(a)) < 0.3 ? 'middle' : (Math.cos(a) > 0 ? 'start' : 'end') });
        tx.textContent = String(i + 1); svg.appendChild(tx);
        pts.push([(cx + Math.cos(a) * R * v / 5), (cy + Math.sin(a) * R * v / 5)]);
      });
      if (done) {
        svg.appendChild(el('polygon', { 'class': 'area', points: pts.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ') }));
        pts.forEach(function (p) { svg.appendChild(el('circle', { 'class': 'dot', cx: p[0].toFixed(1), cy: p[1].toFixed(1), r: 3.5 })); });
      }
      saChart.textContent = '';
      saChart.appendChild(svg);
      saChart.setAttribute('aria-label', 'Radar chart of maturity topics: ' + ts.map(function (t, i) { return (i + 1) + ' ' + t.name + ' ' + lvl(+sa[t.id] || 0); }).join('; '));
      var bars = '<h4>DAM strands</h4><ul class="sa-bars">' + saData.strands.map(function (s) {
        var v = +sa[s.id] || 0;
        return '<li><span>' + esc(s.name) + ': <strong>' + esc(lvl(v)) + '</strong></span><span class="sa-bar" aria-hidden="true"><span data-w="' + (v * 20) + '"></span></span></li>';
      }).join('') + '</ul><p>' + done + ' of ' + n + ' topics assessed. Numbers on the chart are topic numbers; the outer ring is level 5.</p>';
      $('#sa-summary').innerHTML = bars;
      $$('#sa-summary [data-w]').forEach(function (b) { b.style.width = b.getAttribute('data-w') + '%'; });
      var rows = [['area', 'item', 'level', 'level_name']];
      saData.strands.forEach(function (s) { var v = +sa[s.id] || ''; rows.push(['DAM strand', s.name, v, v ? saData.levels[v - 1] : '']); });
      ts.forEach(function (t, i) { var v = +sa[t.id] || ''; rows.push(['Maturity topic ' + (i + 1), t.name, v, v ? saData.levels[v - 1] : '']); });
      var csv = rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(','); }).join('\n');
      $('#sa-csv').setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv));
    };
    $$('[data-sa]').forEach(function (c) {
      var k = c.getAttribute('data-sa');
      if (c.type === 'radio') c.checked = String(sa[k] || '') === c.value; else c.value = sa[k] || '';
      c.addEventListener('change', function () { if (c.value) sa[k] = +c.value; else delete sa[k]; store.set(SAK, JSON.stringify(sa)); drawSA(); });
    });
    $('#sa-print').addEventListener('click', function () { window.print(); });
    $('#sa-clear').addEventListener('click', function () { sa = {}; store.del(SAK); $$('[data-sa]').forEach(function (c) { if (c.type === 'radio') c.checked = false; else c.value = ''; }); drawSA(); });
    drawSA();
  }
  /* DAMA view: role selector opens each area's role guidance and highlights the chosen role (version 1.7) */
  var dr = $('#dama-role');
  if (dr) {
    var names = {};
    $$('#dama-role option').forEach(function (o) { names[o.value] = o.textContent; });
    var applyDr = function () {
      var v = dr.value;
      $$('.dama-uses').forEach(function (det) {
        det.open = !!v;
        $$('tbody tr', det).forEach(function (tr) { var th = tr.querySelector('th'); tr.classList.toggle('me', !!v && th && th.textContent === names[v]); });
      });
      store.set('dcp-dama-role', v);
    };
    dr.value = store.get('dcp-dama-role') || '';
    dr.addEventListener('change', applyDr);
    applyDr();
  }
  /* share this page (version 1.8): copy link; email and Teams links work without scripts */
  $$('[data-copy-link]').forEach(function (b) {
    b.hidden = false;
    b.addEventListener('click', function () {
      var st = b.closest('.share').querySelector('.share-status'), url = location.href.split('#')[0] + (location.hash || '');
      var done = function (ok) { st.textContent = ok ? 'Link copied.' : 'Could not copy. Select the address bar and copy it.'; };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(function () { done(true); }, function () { done(false); });
      else done(false);
    });
  });
  $$('[data-native-share]').forEach(function (b) {
    if (!navigator.share) return;
    b.hidden = false;
    b.addEventListener('click', function () { navigator.share({ title: doc.title, url: location.href }).catch(function () {}); });
  });
  doc.addEventListener('click', function (e) { $$('details.share[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; }); });

  /* guided tours (version 1.8): steps come from the page; each highlights an element and explains it */
  var tours = json('tour-data');
  if (tours) {
    var shade, box, cur = null, step = 0, lastFocus = null; /* not "idx": that name holds the search index in this scope (D-024) */
    var clear = function () { $$('.tour-target').forEach(function (n) { n.classList.remove('tour-target'); }); };
    var end = function () {
      clear(); if (shade) shade.remove(); if (box) box.remove(); shade = box = null;
      if (cur) store.set('dcp-tour-' + cur.id, 'done'); cur = null;
      if (lastFocus) lastFocus.focus();
    };
    var show = function () {
      var st = cur.steps[step];
      if (st.click) { var c = $(st.click); if (c) c.click(); }
      clear();
      var t = $(st.sel);
      var tp = t && t.closest('[role=tabpanel]');
      if (tp && tp.hidden) { var tb = doc.getElementById('tab-' + tp.id); if (tb) tb.click(); }
      if (t) { t.classList.add('tour-target'); t.scrollIntoView({ block: 'center' }); }
      box.innerHTML = '<p class="tour-n">' + esc(cur.title) + ': step ' + (step + 1) + ' of ' + cur.steps.length + '</p><h2 id="tour-h">' + esc(st.title) + '</h2><p>' + esc(st.text) + '</p>' +
        '<p class="tour-nav">' + (step > 0 ? '<button type="button" class="btn secondary" data-t="back">Back</button>' : '') +
        (step < cur.steps.length - 1 ? '<button type="button" class="btn" data-t="next">Next</button>' : '<button type="button" class="btn" data-t="end">Finish</button>') +
        '<button type="button" class="btn secondary" data-t="end">Close tour</button></p>';
      var h2 = box.querySelector('h2'); h2.setAttribute('tabindex', '-1'); h2.focus();
    };
    var start = function (id) {
      cur = tours.filter(function (x) { return x.id === id; })[0]; if (!cur) return;
      step = 0; lastFocus = doc.activeElement;
      shade = doc.createElement('div'); shade.className = 'tour-shade'; shade.addEventListener('click', end); doc.body.appendChild(shade);
      box = doc.createElement('div'); box.className = 'tour-box'; box.setAttribute('role', 'dialog'); box.setAttribute('aria-modal', 'false'); box.setAttribute('aria-labelledby', 'tour-h');
      box.addEventListener('click', function (e) { var b = e.target.closest('[data-t]'); if (!b) return; var a = b.getAttribute('data-t'); if (a === 'next') { step++; show(); } else if (a === 'back') { step--; show(); } else end(); });
      doc.body.appendChild(box);
      show();
    };
    doc.addEventListener('keydown', function (e) { if (box && e.key === 'Escape') end(); });
    $$('[data-tour]').forEach(function (b) { b.hidden = false; b.addEventListener('click', function () { start(b.getAttribute('data-tour')); }); });
    var m = /[#&]tour=([a-z0-9-]+)/.exec(location.hash); if (m) setTimeout(function () { start(m[1]); }, 200);
  }
})();
