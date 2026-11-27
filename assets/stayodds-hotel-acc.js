/* Hotel pages: the details below "Score explained" fold into tidy rows that open on tap (photo-first, less data up front). */
(function () {
  var fd = document.getElementById("full-details");
  if (!fd || !fd.parentNode) return;
  var LABELS = [
    ["guest-rank", "How guests rank it", "Where it sits among hotels nearby"],
    ["so2-three", "Why this score", "Our stay, guests and critics, side by side"],
    ["so2-section", "Before you book", "Best months, prices and tips"],
    ["so2-two", "What guests love", "And what to know before you go"],
    ["more-reviews", "Every review and score", "Each source and how we weigh it"]
  ];
  function label(el) {
    for (var i = 0; i < LABELS.length; i++) {
      if (el.id === LABELS[i][0] || el.classList.contains(LABELS[i][0])) return LABELS[i];
    }
    var h = el.querySelector("h2,h3");
    return h ? [null, h.textContent.trim(), ""] : null;
  }
  var css = document.createElement("style");
  css.textContent = ".so-acc{background:#fff;border:1px solid #EDE5D6;border-radius:16px;margin:0 0 12px;overflow:hidden}" +
    ".so-acc>summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;font-weight:700;font-size:17px;color:#1B2A42}" +
    ".so-acc>summary::-webkit-details-marker{display:none}.so-acc>summary small{display:block;font-weight:500;font-size:13px;color:#6B7480;margin-top:2px}" +
    ".so-acc>summary::after{content:'';width:10px;height:10px;border-right:2px solid #1B2A42;border-bottom:2px solid #1B2A42;transform:rotate(45deg);transition:transform .2s;flex-shrink:0;margin-right:4px}" +
    ".so-acc[open]>summary::after{transform:rotate(-135deg)}.so-acc>.so-acc-body{padding:0 12px 12px}.so-acc>.so-acc-body>*{margin-top:0!important}";
  document.head.appendChild(css);
  var el = fd.nextElementSibling, first = null;
  while (el) {
    var next = el.nextElementSibling, l = label(el);
    if (l && el.offsetHeight > 40 && !el.classList.contains("so-acc")) {
      var d = document.createElement("details"); d.className = "so-acc";
      var s = document.createElement("summary");
      var t = document.createElement("span"); t.textContent = l[1];
      if (l[2]) { var sm = document.createElement("small"); sm.textContent = l[2]; t.appendChild(sm); }
      s.appendChild(t); d.appendChild(s);
      var body = document.createElement("div"); body.className = "so-acc-body";
      el.parentNode.insertBefore(d, el); body.appendChild(el); d.appendChild(body);
      if (!first) first = d;
    }
    el = next;
  }
  // "Score explained below" opens the first row
  document.querySelectorAll('a[href="#full-details"]').forEach(function (a) {
    a.addEventListener("click", function () { if (first) first.open = true; });
  });
  if (location.hash && first) {
    var target = document.querySelector(location.hash);
    var acc = target && target.closest && target.closest(".so-acc");
    if (acc) acc.open = true;
  }
})();
