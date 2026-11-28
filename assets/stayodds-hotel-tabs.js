/* Hotel pages, layout C: below the score, the details sit in tabs (Scores open first, Prices last).
   Each tab shows a short note on hover (or under the tabs on phones) saying what's inside. */
(function () {
  var fd = document.getElementById("full-details");
  if (!fd || !fd.parentNode) return;
  var TABS = [
    { key: "scores", label: "Scores", tip: "Our filmed stay, guests and critics side by side, and how it ranks against hotels nearby", pick: ["so2-three", "guest-rank"] },
    { key: "guests", label: "What guests say", tip: "What guests love, what to know, and every review source with how we weigh it", pick: ["so2-two", "more-reviews"] },
    { key: "before", label: "Before you book", tip: "Best months to go, the room to book, tips and similar hotels to compare", pick: ["so2-section"] },
    { key: "prices", label: "Prices", tip: "Live prices for your dates, holiday dates and partner sites", pick: ["so2-dates", "detail-ota-strip"] }
  ];
  function find(name) {
    return document.getElementById(name) || document.querySelector("." + name);
  }
  var panels = [], used = 0;
  TABS.forEach(function (t) {
    var p = document.createElement("div");
    p.className = "so-tab-panel"; p.id = "so-tab-" + t.key; p.setAttribute("role", "tabpanel"); p.hidden = true;
    t.pick.forEach(function (n) { var el = find(n); if (el && !p.contains(el)) { p.appendChild(el); used++; } });
    t.panel = p;
  });
  if (!used) return;
  // anything else that followed "Score explained" goes under Scores, so nothing is lost
  var el = fd.nextElementSibling;
  while (el) { var nx = el.nextElementSibling; if (/^(SECTION|DIV|DETAILS)$/.test(el.tagName) && el.offsetHeight > 30) TABS[0].panel.appendChild(el); el = nx; }
  var css = document.createElement("style");
  css.textContent = ".so-tabs{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 6px;position:relative}" +
    ".so-tab{position:relative;border:1px solid #E2D8C6;background:#fff;color:#1B2A42;border-radius:999px;padding:10px 16px;font:700 14px/1.2 inherit;cursor:pointer}" +
    ".so-tab[aria-selected=true]{background:#1B2A42;border-color:#1B2A42;color:#fff}" +
    ".so-tab .so-tip{position:absolute;left:50%;top:calc(100% + 10px);transform:translateX(-50%);width:max-content;max-width:260px;background:#1B2A42;color:#fff;font:500 12.5px/1.4 inherit;padding:9px 12px;border-radius:10px;box-shadow:0 10px 24px rgba(27,42,66,.2);opacity:0;pointer-events:none;transition:opacity .15s;z-index:30;text-align:left;white-space:normal}" +
    ".so-tab .so-tip::before{content:'';position:absolute;top:-5px;left:50%;margin-left:-5px;border:5px solid transparent;border-top:0;border-bottom-color:#1B2A42}" +
    "@media (hover:hover){.so-tab:hover .so-tip,.so-tab:focus-visible .so-tip{opacity:1}}" +
    ".so-tab-note{font-size:13px;color:#6B7480;margin:2px 0 14px}@media (hover:hover){.so-tab-note{display:none}}" +
    ".so-tab-panel>*{margin-top:0}";
  document.head.appendChild(css);
  var bar = document.createElement("div"); bar.className = "so-tabs"; bar.setAttribute("role", "tablist");
  var note = document.createElement("p"); note.className = "so-tab-note";
  var wrap = document.createElement("div"); wrap.className = "so-tabs-wrap";
  function show(i, scroll) {
    TABS.forEach(function (t, j) {
      t.btn.setAttribute("aria-selected", i === j ? "true" : "false");
      t.panel.hidden = i !== j;
    });
    note.textContent = TABS[i].tipText.textContent;
    if (scroll) wrap.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  TABS.forEach(function (t, i) {
    var b = document.createElement("button"); b.type = "button"; b.className = "so-tab"; b.setAttribute("role", "tab");
    b.setAttribute("aria-controls", "so-tab-" + t.key);
    var l = document.createElement("span"); l.textContent = t.label; b.appendChild(l);
    var tip = document.createElement("span"); tip.className = "so-tip"; tip.setAttribute("role", "tooltip"); tip.textContent = t.tip; b.appendChild(tip);
    t.btn = b; t.tipText = tip;
    b.addEventListener("click", function () { show(i, false); });
    bar.appendChild(b);
  });
  wrap.appendChild(bar); wrap.appendChild(note);
  TABS.forEach(function (t) { wrap.appendChild(t.panel); });
  fd.parentNode.insertBefore(wrap, fd.nextSibling);
  show(0, false);
  // "Score explained below" and "Check prices" buttons open the right tab
  document.querySelectorAll('a[href="#full-details"]').forEach(function (a) { a.addEventListener("click", function () { show(0, false); }); });
  document.querySelectorAll("a[href='#so2-dates'], a[href='#dates']").forEach(function (a) {
    if (!a.closest(".so-tab-panel")) a.addEventListener("click", function (e) { e.preventDefault(); show(3, true); });
  });
  if (location.hash) {
    var target = document.querySelector(location.hash);
    var p = target && target.closest && target.closest(".so-tab-panel");
    if (p) TABS.forEach(function (t, i) { if (t.panel === p) show(i, false); });
  }
})();
