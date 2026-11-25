/* StayOdds in-page video player.
   Any element with [data-yt-id] opens our YouTube review in a larger panel
   directly underneath the main page content (no leaving the page, no tiny
   inline player). Elements that used to play in place ([data-yt-inline]) now
   open the same panel. Uses youtube-nocookie.com; falls back to the normal
   YouTube link if the player can't be created. */
(function () {
  "use strict";
  if (window.__stayOddsVideoReady) return;
  window.__stayOddsVideoReady = true;

  var ID_RE = /^[A-Za-z0-9_-]{6,20}$/;
  var panel = null;
  var lastFocus = null;

  function embedUrl(id) {
    return (
      "https://www.youtube-nocookie.com/embed/" +
      encodeURIComponent(id) +
      "?autoplay=1&rel=0&modestbranding=1&playsinline=1"
    );
  }

  function watchUrl(id, isShort) {
    return isShort
      ? "https://www.youtube.com/shorts/" + encodeURIComponent(id)
      : "https://www.youtube.com/watch?v=" + encodeURIComponent(id);
  }

  function makeIframe(id, title) {
    var f = document.createElement("iframe");
    f.src = embedUrl(id);
    f.title = title || "The Uncharted Itinerary video review";
    f.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.referrerPolicy = "strict-origin-when-cross-origin";
    return f;
  }

  function buildPanel() {
    var el = document.createElement("section");
    el.className = "yt-panel";
    el.id = "yt-panel";
    el.setAttribute("aria-label", "Video review player");
    el.hidden = true;
    el.innerHTML =
      '<div class="container">' +
      '<div class="yt-panel-inner">' +
      '<div class="yt-panel-head">' +
      '<span class="yt-panel-brand"><span class="yt-badge-logo" aria-hidden="true"></span>' +
      '<span class="yt-panel-title"></span></span>' +
      '<button type="button" class="yt-panel-close" data-yt-close aria-label="Close video">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>' +
      "</button></div>" +
      '<div class="yt-panel-stage"></div>' +
      '<div class="yt-panel-foot">' +
      '<a class="yt-panel-yt" target="_blank" rel="noopener noreferrer">Watch on YouTube &nearr;</a>' +
      '<a class="yt-panel-sub" href="https://www.youtube.com/@TheUnchartedItinerary?sub_confirmation=1" target="_blank" rel="noopener noreferrer">Subscribe to The Uncharted Itinerary</a>' +
      "</div></div></div>";

    // Sit directly underneath the main page content (between <main> and the footer).
    var main = document.querySelector("main");
    if (main && main.parentNode) {
      main.parentNode.insertBefore(el, main.nextSibling);
    } else {
      var footer = document.querySelector("footer");
      if (footer && footer.parentNode) footer.parentNode.insertBefore(el, footer);
      else document.body.appendChild(el);
    }
    return el;
  }

  function prefersReducedMotion() {
    try {
      return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (e) {
      return false;
    }
  }

  function openPanel(id, opts) {
    if (!ID_RE.test(id)) return false;
    if (!panel) panel = buildPanel();
    lastFocus = document.activeElement;
    var stage = panel.querySelector(".yt-panel-stage");
    stage.innerHTML = ""; // replaces any video already playing
    panel.classList.toggle("is-short", !!opts.isShort);
    stage.appendChild(makeIframe(id, opts.title));
    panel.querySelector(".yt-panel-title").textContent = opts.title || "The Uncharted Itinerary";
    panel.querySelector(".yt-panel-yt").href = watchUrl(id, opts.isShort);
    panel.hidden = false;
    try {
      panel.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
    } catch (e) {
      panel.scrollIntoView();
    }
    try {
      panel.querySelector(".yt-panel-close").focus({ preventScroll: true });
    } catch (e) {}
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", "play_video_inpage", { event_category: "video", event_label: opts.title || id });
      }
    } catch (e) {}
    return true;
  }

  function closePanel() {
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    panel.querySelector(".yt-panel-stage").innerHTML = ""; // stops playback
    if (lastFocus && typeof lastFocus.focus === "function") {
      try {
        lastFocus.focus();
      } catch (e) {}
    }
  }

  document.addEventListener(
    "click",
    function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest("[data-yt-close]")) {
        ev.preventDefault();
        closePanel();
        return;
      }
      var el = t.closest("[data-yt-id]");
      if (!el) return;
      var id = el.getAttribute("data-yt-id") || "";
      var ok = openPanel(id, {
        isShort: el.getAttribute("data-yt-short") === "1",
        title: el.getAttribute("data-yt-title") || "",
      });
      if (ok) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      // if not ok, the element's own href (if any) opens YouTube normally
    },
    true
  );

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closePanel();
  });
})();
