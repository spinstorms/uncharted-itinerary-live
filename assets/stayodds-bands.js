/* Orange title band (like the map page) on every page whose title sits in a plain header:
   award lists, holidays, destination guides, insights and brands. */
(function () {
  function band(el) { if (el && !el.classList.contains("so-band")) el.classList.add("so-band"); }
  // award lists, holidays and other generated list pages: eyebrow + h1 + intro
  document.querySelectorAll(".al-wrap > .al-eyebrow").forEach(function (eb) {
    if (eb.parentNode.querySelector(".so-band")) return;
    var box = document.createElement("div"); box.className = "so-band";
    var h1 = eb.nextElementSibling, sub = h1 && h1.nextElementSibling;
    eb.parentNode.insertBefore(box, eb); box.appendChild(eb);
    if (h1 && h1.tagName === "H1") { box.appendChild(h1); if (sub && /\bal-sub\b/.test(sub.className)) box.appendChild(sub); }
  });
  band(document.querySelector(".gi > .wrap > header, .gi header"));
  band(document.querySelector(".brands-banner"));
  document.querySelectorAll(".compare-mode-banner").forEach(band);
})();
