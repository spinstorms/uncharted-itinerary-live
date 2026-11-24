/* StayOdds in-page video player.
   Any element with [data-yt-id] opens our YouTube review in a lightbox player
   (no leaving the page). Elements with [data-yt-inline] play in place instead.
   Uses youtube-nocookie.com; falls back to the normal YouTube link if the
   player can't be created. */
(function () {
  "use strict";
  if (window.__stayOddsVideoReady) return;
  window.__stayOddsVideoReady = true;

  var ID_RE = /^[A-Za-z0-9_-]{6,20}$/;
  var modal = null;
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

  function buildModal() {
    var el = document.createElement("div");
    el.className = "yt-modal";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-modal", "true");
    el.setAttribute("aria-label", "Video review player");
    el.hidden = true;
    el.innerHTML =
      '<div class="yt-modal-backdrop" data-yt-close></div>' +
      '<div class="yt-modal-panel">' +
      '<div class="yt-modal-head">' +
      '<span class="yt-modal-brand"><span class="yt-badge-logo" aria-hidden="true"></span>' +
      '<span class="yt-modal-title"></span></span>' +
      '<button type="button" class="yt-modal-close" data-yt-close aria-label="Close video">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>' +
      "</button></div>" +
      '<div class="yt-modal-stage"></div>' +
      '<div class="yt-modal-foot">' +
      '<a class="yt-modal-yt" target="_blank" rel="noopener noreferrer">Watch on YouTube &nearr;</a>' +
      '<a class="yt-modal-sub" href="https://www.youtube.com/@TheUnchartedItinerary?sub_confirmation=1" target="_blank" rel="noopener noreferrer">Subscribe to The Uncharted Itinerary</a>' +
      "</div></div>";
    document.body.appendChild(el);
    return el;
  }

  function openModal(id, opts) {
    if (!ID_RE.test(id)) return false;
    if (!modal) modal = buildModal();
    lastFocus = document.activeElement;
    var stage = modal.querySelector(".yt-modal-stage");
    stage.innerHTML = "";
    stage.className = "yt-modal-stage";
    modal.classList.toggle("is-short", !!opts.isShort);
    stage.appendChild(makeIframe(id, opts.title));
    modal.querySelector(".yt-modal-title").textContent = opts.title || "The Uncharted Itinerary";
    modal.querySelector(".yt-modal-yt").href = watchUrl(id, opts.isShort);
    modal.hidden = false;
    document.documentElement.classList.add("yt-modal-open");
    modal.querySelector(".yt-modal-close").focus();
    try {
      if (typeof window.gtag === "function") {
        window.gtag("event", "play_video_inpage", { event_category: "video", event_label: opts.title || id });
      }
    } catch (e) {}
    return true;
  }

  function closeModal() {
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    modal.querySelector(".yt-modal-stage").innerHTML = ""; // stops playback
    document.documentElement.classList.remove("yt-modal-open");
    if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
  }

  function playInline(trigger, id, title) {
    var host = trigger.closest("[data-yt-host]");
    if (!host || !ID_RE.test(id)) return false;
    host.classList.add("is-playing");
    var existing = host.querySelector("iframe");
    if (existing) existing.remove();
    host.appendChild(makeIframe(id, title));
    return true;
  }

  document.addEventListener(
    "click",
    function (ev) {
      var t = ev.target;
      if (!t || !t.closest) return;
      if (t.closest("[data-yt-close]")) {
        ev.preventDefault();
        closeModal();
        return;
      }
      var el = t.closest("[data-yt-id]");
      if (!el) return;
      var id = el.getAttribute("data-yt-id") || "";
      var opts = {
        isShort: el.getAttribute("data-yt-short") === "1",
        title: el.getAttribute("data-yt-title") || "",
      };
      var ok =
        el.hasAttribute("data-yt-inline") && el.closest("[data-yt-host]")
          ? playInline(el, id, opts.title)
          : openModal(id, opts);
      if (ok) {
        ev.preventDefault();
        ev.stopPropagation();
      }
      // if not ok, the element's own href (if any) opens YouTube normally
    },
    true
  );

  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") closeModal();
    if (ev.key === "Tab" && modal && !modal.hidden) {
      var f = modal.querySelectorAll("button, a[href]");
      if (!f.length) return;
      var first = f[0];
      var last = f[f.length - 1];
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault();
        last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault();
        first.focus();
      }
    }
  });
})();
