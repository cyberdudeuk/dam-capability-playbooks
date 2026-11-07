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
  var css = ".dqp-jbar{position:fixed;z-index:2147483000;left:50%;transform:translateX(-50%);bottom:12px;width:min(760px,calc(100vw - 24px));" +
    "background:#ffffff;color:#17212b;border:2px solid #0d6b6e;border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,.25);padding:10px 14px;" +
    "display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;font:500 15px/1.4 system-ui,-apple-system,'Segoe UI',sans-serif;box-sizing:border-box}" +
    ".dqp-jbar .grow{flex:1 1 220px}.dqp-jbar b{font-weight:700}" +
    ".dqp-jbar a,.dqp-jbar button{font:600 15px/1 system-ui,-apple-system,'Segoe UI',sans-serif;min-height:40px;padding:8px 12px;border-radius:8px;" +
    "border:1px solid #56636e;background:transparent;color:#17212b;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center}" +
    ".dqp-jbar a.go{background:#0d6b6e;color:#ffffff;border-color:#0d6b6e}" +
    ".dqp-jbar a:focus-visible,.dqp-jbar button:focus-visible{outline:3px solid #ffbf47;outline-offset:2px}" +
    "@media (prefers-color-scheme:dark){.dqp-jbar{background:#172129;color:#e5ecef;border-color:#7cc9c4}.dqp-jbar a,.dqp-jbar button{color:#e5ecef;border-color:#9aa9b3}.dqp-jbar a.go{background:#7cc9c4;color:#0b1418;border-color:#7cc9c4}}" +
    "@media (forced-colors:active){.dqp-jbar{border-color:CanvasText}}@media print{.dqp-jbar{display:none!important}}";
  function add() {
    var s = document.createElement("style"); s.textContent = css; document.head.appendChild(s);
    var bar = document.createElement("aside"); bar.className = "dqp-jbar"; bar.setAttribute("aria-label", "Your journey");
    bar.innerHTML = '<span class="grow"><b>' + esc(st.name) + "</b> · step " + (at + 1) + " of " + n + ": " + esc(st.steps[at].text) + "</span>" +
      (pv ? '<a href="' + esc(pv.url) + '">Back</a>' : "") +
      (nx ? '<a class="go" href="' + esc(nx.url) + '">Next: ' + esc(nx.portal || "next step") + " →</a>" : "<span><b>Last step.</b></span>") +
      '<button type="button">' + (nx ? "Stop the journey" : "Finish") + "</button>";
    document.body.appendChild(bar);
    document.body.style.paddingBottom = Math.max(parseInt(getComputedStyle(document.body).paddingBottom, 10) || 0, bar.offsetHeight + 24) + "px";
    bar.querySelector("button").addEventListener("click", function () { try { localStorage.removeItem("dqp-journey"); } catch (e) {} bar.remove(); document.body.style.paddingBottom = ""; });
  }
  if (document.body) add(); else document.addEventListener("DOMContentLoaded", add);
})();
