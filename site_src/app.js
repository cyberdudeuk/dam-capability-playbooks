/* DAM capability playbooks: progressive enhancement. Every page works without this file. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.remove('no-js');
  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return store.mem[k] || null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { store.mem[k] = v; } },
    mem: {}
  };
  function $(s, r) { return (r || doc).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || doc).querySelectorAll(s)); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function json(id) { var n = doc.getElementById(id); if (!n) return null; try { return JSON.parse(n.textContent); } catch (e) { return null; } }
  var narrow = window.matchMedia('(max-width: 60rem)');

  /* theme */
  var themeBtn = $('#theme-toggle');
  function applyTheme(t) {
    if (t === 'dark' || t === 'light') root.setAttribute('data-theme', t); else root.removeAttribute('data-theme');
    if (themeBtn) themeBtn.querySelector('.label').textContent = t === 'dark' ? 'Light mode' : 'Dark mode';
  }
  var savedTheme = store.get('dcp-theme');
  if (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches) savedTheme = 'dark';
  applyTheme(savedTheme);
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    applyTheme(next); store.set('dcp-theme', next);
  });

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
    var pref = store.get('dcp-drawer');
    setDrawer(narrow.matches ? false : pref !== '0', false);
    dsw.addEventListener('click', function () {
      var open = dsw.getAttribute('aria-checked') !== 'true';
      setDrawer(open, true);
      if (open && narrow.matches) { var f = drawer.querySelector('a,summary'); if (f) f.focus(); }
    });
    drawer.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (a && narrow.matches) { setDrawer(false, false); }
    });
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
      mlist.insertBefore(last, mlist.firstChild);
    }
    if (!mlist.children.length) more.hidden = true;
  }
  if (bar) {
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
    if (panel) {
      var tab = doc.querySelector('[role="tab"][aria-controls="' + panel.id + '"]');
      if (tab) activate(tab);
      if (target !== panel) target.scrollIntoView();
    }
  }
  window.addEventListener('hashchange', openFromHash);
  openFromHash();

  /* filters: any [data-filter] block filters items in its target */
  $$('[data-filter]').forEach(function (box) {
    var target = doc.getElementById(box.getAttribute('data-filter'));
    if (!target) return;
    var out = box.querySelector('.count-out');
    var controls = $$('select,input', box);
    function run() {
      var q = (box.querySelector('input[type="search"]') || {}).value || '';
      q = q.trim().toLowerCase();
      var shown = 0, items = $$('[data-item]', target);
      items.forEach(function (it) {
        var ok = true;
        controls.forEach(function (c) {
          if (c.tagName === 'SELECT' && c.value) {
            var vals = (it.getAttribute('data-' + c.name) || '').split(' ');
            if (vals.indexOf(c.value) < 0) ok = false;
          }
        });
        if (ok && q && it.textContent.toLowerCase().indexOf(q) < 0) ok = false;
        it.hidden = !ok; if (ok) shown++;
      });
      if (out) out.textContent = shown + ' of ' + items.length + ' shown';
    }
    controls.forEach(function (c) { c.addEventListener(c.tagName === 'SELECT' ? 'change' : 'input', run); });
    var reset = box.querySelector('button[type="reset"]');
    if (reset) reset.addEventListener('click', function () { setTimeout(run, 0); });
    run();
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
      $$('.gbar li.more.open').forEach(function (li) { li.classList.remove('open'); li.querySelector('button').setAttribute('aria-expanded', 'false'); });
      hideTip();
    }
  });

  /* glossary tooltips */
  var tip = doc.createElement('div'); tip.className = 'tooltip'; tip.id = 'tooltip'; tip.setAttribute('role', 'tooltip'); tip.hidden = true; doc.body.appendChild(tip);
  function showTip(a) {
    tip.textContent = a.getAttribute('data-tip'); tip.hidden = false;
    var r = a.getBoundingClientRect();
    tip.style.left = Math.max(8, Math.min(window.scrollX + r.left, window.scrollX + doc.documentElement.clientWidth - tip.offsetWidth - 8)) + 'px';
    tip.style.top = (window.scrollY + r.bottom + 6) + 'px';
    a.setAttribute('aria-describedby', 'tooltip');
  }
  function hideTip() { tip.hidden = true; $$('a.term[aria-describedby]').forEach(function (a) { a.removeAttribute('aria-describedby'); }); }
  $$('a.term[data-tip]').forEach(function (a) {
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
    var clr = $('#graph-clear'); if (clr) clr.addEventListener('click', function () { gw.classList.remove('dim'); detail.textContent = 'Select a node to see what it connects to.'; });
  }
})();
