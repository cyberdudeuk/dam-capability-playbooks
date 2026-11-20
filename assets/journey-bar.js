/* Cross-portal journey bar (Commons v2.15, BL-34), for the three portals on the same site.
 * A journey started on the Commons ("Three portals, one journey") is kept in localStorage under "dqp-journey".
 * Any page of the Commons, the DAM capability playbooks or the GitHub repos catalogue that includes this script
 * shows a small bar with the step you are on and a link to the next one. Self-contained: no styles or libraries
 * needed, nothing sent anywhere, and nothing shown unless you started a journey. MIT licence.
 */
(function () {
  var st; try { st = JSON.parse(localStorage.getItem("dqp-journey") || "null"); } catch (e) { return; }
  if (!st || !st.steps || !st.steps.length || document.querySelector(".dqp-jbar")) return;
  var path = location.origin + location.pathname, at = -1, loose = -1;
  st.steps.forEach(function (s, k) {
    try { var u = new URL(s.url, location.href);
      if (u.origin + u.pathname === path) { if (u.hash && u.hash === location.hash) at = k; else if (loose < 0 || (typeof st.i === "number" && k === st.i)) loose = k; }
    } catch (e) {}
  });
  if (at < 0) at = loose;
  if (at < 0) return;
  st.i = at; try { localStorage.setItem("dqp-journey", JSON.stringify(st)); } catch (e) {}
  var n = st.steps.length, nx = st.steps[at + 1], pv = st.steps[at - 1];
  var esc = function (x) { return String(x).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); };
  // Styles are set on the elements themselves (not a style element), so pages whose security policy blocks inline
  // style sheets still show the bar properly.
  var dark = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches;
  var C = dark ? {bg: "#172129", fg: "#e5ecef", line: "#9aa9b3", acc: "#7cc9c4", accFg: "#0b1418"} : {bg: "#ffffff", fg: "#17212b", line: "#56636e", acc: "#0d6b6e", accFg: "#ffffff"};
  var font = "system-ui,-apple-system,'Segoe UI',sans-serif";
  function set(e, o) { Object.keys(o).forEach(function (k) { e.style.setProperty(k, o[k]); }); return e; }
  function btn(e, go) {
    set(e, {"font": "600 15px/1 " + font, "min-height": "40px", "padding": "8px 12px", "border-radius": "8px", "border": "1px solid " + (go ? C.acc : C.line),
      "background": go ? C.acc : "transparent", "color": go ? C.accFg : C.fg, "cursor": "pointer", "text-decoration": "none", "display": "inline-flex", "align-items": "center", "box-sizing": "border-box"});
    e.addEventListener("focus", function () { e.style.setProperty("outline", "3px solid #ffbf47"); e.style.setProperty("outline-offset", "2px"); });
    e.addEventListener("blur", function () { e.style.removeProperty("outline"); });
    return e;
  }
  function add() {
    var bar = set(document.createElement("aside"), {"position": "fixed", "z-index": "2147483000", "left": "50%", "transform": "translateX(-50%)", "bottom": "12px",
      "width": "min(760px, calc(100vw - 24px))", "background": C.bg, "color": C.fg, "border": "2px solid " + C.acc, "border-radius": "12px",
      "box-shadow": "0 10px 30px rgba(0,0,0,.25)", "padding": "10px 14px", "display": "flex", "flex-wrap": "wrap", "gap": "8px 12px", "align-items": "center",
      "font": "500 15px/1.4 " + font, "box-sizing": "border-box", "margin": "0"});
    bar.className = "dqp-jbar"; bar.setAttribute("aria-label", "Your journey");
    var txt = set(document.createElement("span"), {"flex": "1 1 220px"});
    txt.innerHTML = "<b>" + esc(st.name) + "</b> \u00b7 step " + (at + 1) + " of " + n + ": " + esc(st.steps[at].text);
    bar.appendChild(txt);
    if (pv) { var b1 = btn(document.createElement("a")); b1.href = pv.url; b1.textContent = "Back"; bar.appendChild(b1); }
    if (nx) { var b2 = btn(document.createElement("a"), true); b2.href = nx.url; b2.textContent = "Next: " + (nx.portal || "next step") + " \u2192"; bar.appendChild(b2); }
    else { var last = document.createElement("span"); last.innerHTML = "<b>Last step.</b>"; bar.appendChild(last); }
    var stop = btn(document.createElement("button")); stop.type = "button"; stop.textContent = nx ? "Stop the journey" : "Finish"; bar.appendChild(stop);
    document.body.appendChild(bar);
    window.addEventListener("beforeprint", function () { bar.style.display = "none"; });
    window.addEventListener("afterprint", function () { bar.style.display = "flex"; });
    var pad = document.body.style.paddingBottom;
    document.body.style.paddingBottom = Math.max(parseInt(getComputedStyle(document.body).paddingBottom, 10) || 0, bar.offsetHeight + 24) + "px";
    stop.addEventListener("click", function () { try { localStorage.removeItem("dqp-journey"); } catch (e) {} bar.remove(); document.body.style.paddingBottom = pad; });
  }
  if (document.body) add(); else document.addEventListener("DOMContentLoaded", add);
})();
