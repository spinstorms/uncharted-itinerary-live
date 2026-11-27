/* StayOdds languages: one small JSON per language, swapped in on the page. No extra page copies. */
(function () {
  var LANGS = [["en","English"],["es","Español"],["pt-BR","Português (BR)"],["fr","Français"],["de","Deutsch"],["it","Italiano"],["ar","العربية"],["ja","日本語"],["id","Bahasa Indonesia"],["fa","فارسی"],["zh-Hans","简体中文"],["ko","한국어"]];
  var RTL = { ar: 1, fa: 1 };
  var KEY = "stayodds-lang";
  function pick() {
    try { var s = localStorage.getItem(KEY); if (s) return s; } catch (e) {}
    var n = (navigator.languages && navigator.languages[0]) || navigator.language || "en";
    n = n.toLowerCase();
    if (n.indexOf("pt") === 0) return "pt-BR";
    if (n.indexOf("in") === 0) return "id";
    if (n.indexOf("zh") === 0) return "zh-Hans";
    for (var i = 0; i < LANGS.length; i++) if (n.indexOf(LANGS[i][0].toLowerCase().slice(0, 2)) === 0) return LANGS[i][0];
    return "en";
  }
  var SO_I18N_V = "20261128";
  var lang = pick(), dict = null, lc = {}, originals = new WeakMap();
  function norm(s) { return s.replace(/\s+/g, " ").trim(); }
  function swapNode(n) {
    var orig = originals.has(n) ? originals.get(n) : n.nodeValue;
    var key = norm(orig);
    if (!key || key.length > 2000) return;
    var tr = dict && (dict[key] || lc[key.toLowerCase()]);
    if (!tr && dict && /\d/.test(key)) {
      var nums = key.match(/\d[\d,]*/g), names = ["{n}", "{m}"];
      if (nums && nums.length <= 2) {
        var i = 0, pat = key.replace(/\d[\d,]*/g, function () { return names[i++]; });
        var t2 = dict[pat] || lc[pat.toLowerCase()];
        if (t2) tr = t2.replace("{n}", nums[0]).replace("{m}", nums[1] || "");
      }
    }
    if (tr) { if (!originals.has(n)) originals.set(n, orig); n.nodeValue = orig.match(/^\s*/)[0] + tr + orig.match(/\s*$/)[0]; if (n.parentNode && n.parentNode.setAttribute) n.parentNode.setAttribute('dir', 'auto'); }
    else if (originals.has(n) && lang === "en") n.nodeValue = orig;
  }
  function walk(root) {
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentNode && n.parentNode.nodeName;
        return p === "SCRIPT" || p === "STYLE" || p === "NOSCRIPT" ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
      }
    });
    var n; while ((n = w.nextNode())) swapNode(n);
    if (root.querySelectorAll) root.querySelectorAll("[placeholder],[aria-label],[title],[alt]").forEach(function (el) {
      ["placeholder", "aria-label", "title", "alt"].forEach(function (a) {
        var v = el.getAttribute(a); if (!v) return;
        var o = el.getAttribute("data-en-" + a) || v;
        var tr = dict && dict[norm(o)];
        if (tr) { el.setAttribute("data-en-" + a, o); el.setAttribute(a, tr); }
        else if (lang === "en" && el.hasAttribute("data-en-" + a)) el.setAttribute(a, o);
      });
    });
  }
  var obs = null;
  function apply() {
    document.documentElement.lang = lang;
    document.documentElement.classList.toggle("so-rtl", !!RTL[lang]);
    walk(document.body);
    if (!obs && lang !== "en") {
      obs = new MutationObserver(function (ms) {
        ms.forEach(function (m) { m.addedNodes.forEach(function (n) { if (n.nodeType === 3) swapNode(n); else if (n.nodeType === 1) walk(n); }); });
      });
      obs.observe(document.body, { childList: true, subtree: true });
    }
    var b = document.getElementById("so-lang-btn"); if (b) b.querySelector("span").textContent = lang.slice(0, 2).toUpperCase();
  }
  function load(l, cb) {
    if (l === "en") { dict = null; cb(); return; }
    // the small UI dictionary, plus the full-site translations: text shared by many pages and this page's own text
    var pk = location.pathname.replace(/index\.html$|\.html$/, "").replace(/^\/+|\/+$/g, "").replace(/[^A-Za-z0-9_-]+/g, "__") || "home";
    function get(u) { return fetch(u).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; }); }
    Promise.all([get("/assets/i18n/" + l + ".json?v=2"), get("/assets/i18n/" + l + "/common.json?v=" + SO_I18N_V), get("/assets/i18n/" + l + "/p/" + pk + ".json?v=" + SO_I18N_V)]).then(function (ds) {
      var d = {}; ds.forEach(function (x) { for (var k in x) d[k] = x[k]; });
      dict = d; lc = {}; for (var k in d) lc[k.toLowerCase()] = d[k]; cb();
    });
  }
  function setLang(l) {
    lang = l; try { localStorage.setItem(KEY, l); } catch (e) {}
    load(l, apply);
  }
  function switcher() {
    var css = document.createElement("style");
    css.textContent = "#so-lang{position:relative;display:inline-flex;margin-left:10px}#so-lang-btn{display:inline-flex;align-items:center;gap:6px;background:transparent;border:1px solid rgba(255,255,255,.35);color:#fff;border-radius:999px;padding:6px 11px;font:600 12px/1 inherit;cursor:pointer}#so-lang-menu{position:fixed;right:12px;top:64px;max-height:calc(100vh - 80px);overflow:auto;background:#fff;color:#0F2B33;border-radius:14px;box-shadow:0 12px 32px rgba(15,43,51,.18);padding:6px;min-width:190px;z-index:2147483000;display:none}#so-lang-menu.open{display:block}#so-lang-menu button{display:block;width:100%;text-align:start;background:none;border:0;padding:9px 12px;border-radius:9px;font:500 14px/1.2 inherit;color:inherit;cursor:pointer}#so-lang-menu button:hover,#so-lang-menu button[aria-current]{background:#E6F2F2;color:#0B7A7A}html.so-rtl [dir=auto]{unicode-bidi:plaintext}";
    document.head.appendChild(css);
    var host = document.querySelector(".stayodds-site-header .header-inner") || document.querySelector("header");
    if (!host) return;
    var wrap = document.createElement("div"); wrap.id = "so-lang";
    wrap.innerHTML = '<button id="so-lang-btn" type="button" aria-haspopup="true" aria-label="Language"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg><span>EN</span></button><div id="so-lang-menu" role="menu"></div>';
    var menu = wrap.querySelector("#so-lang-menu");
    LANGS.forEach(function (x) {
      var b = document.createElement("button"); b.type = "button"; b.textContent = x[1]; b.setAttribute("dir", "auto"); b.setAttribute("translate", "no");
      if (x[0] === lang) b.setAttribute("aria-current", "true");
      b.onclick = function () {
        menu.querySelectorAll("button").forEach(function (o) { o.removeAttribute("aria-current"); }); b.setAttribute("aria-current", "true");
        menu.classList.remove("open"); setLang(x[0]);
      };
      menu.appendChild(b);
    });
    wrap.querySelector("#so-lang-btn").onclick = function (e) {
      e.stopPropagation();
      // fixed to the screen so a header with overflow:hidden can't clip it (was invisible on phones)
      var r = this.getBoundingClientRect();
      menu.style.top = Math.round(r.bottom + 8) + "px";
      menu.style.right = Math.max(8, Math.round(window.innerWidth - r.right)) + "px";
      if (menu.parentNode !== document.body) document.body.appendChild(menu);
      menu.classList.toggle("open");
    };
    window.addEventListener("scroll", function () { menu.classList.remove("open"); }, { passive: true });
    document.addEventListener("click", function () { menu.classList.remove("open"); });
    var burger = host.querySelector(".mobile-menu-toggle, .menu-toggle, button[aria-controls]");
    if (burger) host.insertBefore(wrap, burger); else host.appendChild(wrap);
  }
  function start() { switcher(); load(lang, apply); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
