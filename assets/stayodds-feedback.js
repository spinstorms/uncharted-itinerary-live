(() => {
  "use strict";

  const WEB3FORMS_URL = "https://api.web3forms.com/submit";
  const WEB3FORMS_KEY = "dd98b520-df29-4647-9613-87671569c0c1";
  const LS_FEEDBACK_KEY = "stayodds_feedback_done_v1";

  function trackEvent(eventName, tagKey, tagValue) {
    if (!eventName) return;
    try {
      if (typeof window.clarity === "function") {
        if (tagKey && tagValue !== undefined && tagValue !== null && String(tagValue).trim() !== "") {
          window.clarity("set", String(tagKey), String(tagValue));
        }
        window.clarity("event", String(eventName));
      }
    } catch (_) {
      // Never block user interaction on analytics failure
    }
  }

  window.trackEvent = trackEvent;

  function resolveResortName(el) {
    if (!el) return "";
    const direct = el.getAttribute("data-resort-name") || el.closest("[data-resort-name]")?.getAttribute("data-resort-name");
    if (direct) return direct.trim();
    const card = el.closest(".consensus-row-card, .scorecard-card, .h2h-card, .related-card, .leaflet-popup-content");
    if (card) {
      const heading = card.querySelector("h2, h3, h4, strong");
      if (heading && heading.textContent) return heading.textContent.trim();
    }
    const pageTitle = document.querySelector("h1.detail-title");
    if (pageTitle && pageTitle.textContent) return pageTitle.textContent.trim();
    return document.title.split("—")[0].trim();
  }

  // Global delegated click tracking for links across static & dynamic pages
  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-open-resort-request]");
    if (trigger) {
      e.preventDefault();
      openResortModal();
      return;
    }

    const link = e.target.closest("a[href]");
    if (!link) return;

    const customEvent = link.getAttribute("data-track-event");
    if (customEvent) {
      const tagKey = link.getAttribute("data-track-key") || "resort";
      const tagVal = link.getAttribute("data-track-val") || resolveResortName(link);
      trackEvent(customEvent, tagKey, tagVal);
      return;
    }

    const href = link.getAttribute("href") || "";
    const rel = (link.getAttribute("rel") || "").toLowerCase();
    const lowerHref = href.toLowerCase();
    const resortName = resolveResortName(link);

    if (lowerHref.includes("tripadvisor.com")) {
      trackEvent("click_tripadvisor", "resort", resortName);
    } else if (
      rel.includes("sponsored") ||
      lowerHref.includes("booking.com") ||
      lowerHref.includes("tp.media") ||
      lowerHref.includes("aviasales") ||
      lowerHref.includes("hotellook") ||
      /check\s+(live\s+)?rates|rates\s*↗/i.test(link.textContent || "")
    ) {
      trackEvent("click_rates", "resort", resortName);
    } else if (lowerHref.includes("youtube.com") || lowerHref.includes("youtu.be")) {
      trackEvent("click_youtube", "resort", resortName);
    } else if (
      /\/stayodds\/[^/?#]+/i.test(lowerHref) ||
      /^\.\.\/[a-z0-9-]+\/?$/i.test(lowerHref) ||
      /full breakdown|stayodds breakdown/i.test(link.textContent || "")
    ) {
      trackEvent("open_breakdown", "resort", resortName);
    }
  });

  // Track landing on an individual resort breakdown page
  function trackBreakdownLanding() {
    const detailTitle = document.querySelector("h1.detail-title");
    if (detailTitle && detailTitle.textContent) {
      trackEvent("open_breakdown", "resort", detailTitle.textContent.trim());
    }
  }

  // ---------- Floating Quick Feedback Widget ----------
  let feedbackRoot = null;
  let feedbackPopover = null;
  let feedbackToggleBtn = null;

  function hasSubmittedFeedback() {
    try {
      return localStorage.getItem(LS_FEEDBACK_KEY) === "1";
    } catch (_) {
      return false;
    }
  }

  function markFeedbackSubmitted() {
    try {
      localStorage.setItem(LS_FEEDBACK_KEY, "1");
    } catch (_) {
      // Ignore storage errors in private browsing / restricted iframes
    }
  }

  function mountFeedbackWidget() {
    if (document.getElementById("soFeedbackRoot")) return;

    const alreadyDone = hasSubmittedFeedback();
    feedbackRoot = document.createElement("div");
    feedbackRoot.id = "soFeedbackRoot";
    feedbackRoot.className = "so-fb-root" + (alreadyDone ? " is-done" : "");
    feedbackRoot.innerHTML = `
      <div class="so-fb-popover" id="soFbPopover" role="dialog" aria-label="Quick Feedback" aria-hidden="true">
        <div class="so-fb-head">
          <div class="so-fb-title">Quick Feedback</div>
          <button type="button" class="so-fb-close" id="soFbClose" aria-label="Close feedback">&times;</button>
        </div>

        <form id="soFbForm" class="so-fb-body" novalidate>
          <input type="checkbox" name="botcheck" id="soFbBotcheck" tabindex="-1" autocomplete="off" style="display:none;" />

          <div class="so-fb-step1">
            <p class="so-fb-question">Is Stay Odds useful?</p>
            <div class="so-fb-choice-row">
              <button type="button" class="so-fb-choice" data-useful="Yes" id="soFbYes">
                <span aria-hidden="true">&#128077;</span> Yes
              </button>
              <button type="button" class="so-fb-choice" data-useful="Not yet" id="soFbNo">
                <span aria-hidden="true">&#128078;</span> Not yet
              </button>
            </div>
          </div>

          <div class="so-fb-step2" id="soFbStep2" hidden>
            <div class="so-fb-field">
              <label class="so-fb-label">Would you use this as an app?</label>
              <div class="so-fb-toggle-row">
                <button type="button" class="so-fb-toggle" data-app="Yes, an app">Yes, an app</button>
                <button type="button" class="so-fb-toggle" data-app="Website is fine">Website is fine</button>
              </div>
            </div>

            <div class="so-fb-field">
              <label class="so-fb-label" for="soFbComment">What is missing, confusing, or could be better?</label>
              <textarea id="soFbComment" class="so-fb-textarea" rows="3" maxlength="800" placeholder="Optional — a quick sentence helps a lot…"></textarea>
            </div>

            <div class="so-fb-error" id="soFbError" role="alert" hidden></div>

            <button type="submit" class="so-fb-submit" id="soFbSubmit">Submit Feedback</button>
          </div>

          <div class="so-fb-thanks" id="soFbThanks" hidden>
            <div class="so-fb-thanks-icon" aria-hidden="true">&#10003;</div>
            <p class="so-fb-thanks-title">Thanks for helping improve Stay Odds!</p>
            <p class="so-fb-thanks-sub">Your feedback goes straight to our roadmap.</p>
          </div>
        </form>
      </div>

      <button type="button" class="so-fb-fab" id="soFbFab" aria-expanded="false" aria-controls="soFbPopover">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span>Feedback</span>
      </button>
    `;

    document.body.appendChild(feedbackRoot);

    feedbackPopover = document.getElementById("soFbPopover");
    feedbackToggleBtn = document.getElementById("soFbFab");
    const closeBtn = document.getElementById("soFbClose");
    const form = document.getElementById("soFbForm");
    const step2 = document.getElementById("soFbStep2");
    const thanks = document.getElementById("soFbThanks");
    const errorEl = document.getElementById("soFbError");
    const submitBtn = document.getElementById("soFbSubmit");
    const commentEl = document.getElementById("soFbComment");
    const botcheckEl = document.getElementById("soFbBotcheck");

    let usefulChoice = "";
    let appChoice = "";
    let firedUsefulEvent = false;

    function setOpen(open) {
      feedbackPopover.classList.toggle("is-open", open);
      feedbackPopover.setAttribute("aria-hidden", String(!open));
      feedbackToggleBtn.setAttribute("aria-expanded", String(open));
    }

    feedbackToggleBtn.addEventListener("click", () => {
      const next = !feedbackPopover.classList.contains("is-open");
      setOpen(next);
    });

    closeBtn.addEventListener("click", () => setOpen(false));

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && feedbackPopover.classList.contains("is-open")) {
        setOpen(false);
      }
    });

    document.addEventListener("click", (e) => {
      if (
        feedbackPopover.classList.contains("is-open") &&
        !feedbackRoot.contains(e.target)
      ) {
        setOpen(false);
      }
    });

    feedbackRoot.querySelectorAll(".so-fb-choice").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-useful") || "";
        usefulChoice = val;
        feedbackRoot.querySelectorAll(".so-fb-choice").forEach((b) => {
          b.classList.toggle("is-selected", b === btn);
        });
        if (!firedUsefulEvent) {
          firedUsefulEvent = true;
          trackEvent(val === "Yes" ? "feedback_useful_yes" : "feedback_useful_no");
        }
        step2.hidden = false;
        thanks.hidden = true;
        errorEl.hidden = true;
      });
    });

    feedbackRoot.querySelectorAll(".so-fb-toggle").forEach((btn) => {
      btn.addEventListener("click", () => {
        const val = btn.getAttribute("data-app") || "";
        appChoice = appChoice === val ? "" : val;
        feedbackRoot.querySelectorAll(".so-fb-toggle").forEach((b) => {
          b.classList.toggle("is-selected", b.getAttribute("data-app") === appChoice);
        });
      });
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!usefulChoice) {
        errorEl.textContent = "Please tap Yes or Not yet first.";
        errorEl.hidden = false;
        return;
      }

      errorEl.hidden = true;
      submitBtn.disabled = true;
      const origText = submitBtn.textContent;
      submitBtn.textContent = "Sending…";

      try {
        const payload = {
          access_key: WEB3FORMS_KEY,
          subject: "Stay Odds Website Feedback",
          botcheck: Boolean(botcheckEl && botcheckEl.checked),
          useful: usefulChoice,
          app_preference: appChoice || "Not answered",
          comment: (commentEl.value || "").trim() || "(No comment)",
          page_url: window.location.href,
          device_width: window.innerWidth,
        };

        const response = await fetch(WEB3FORMS_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
          throw new Error(data.message || "Could not send feedback right now.");
        }

        feedbackRoot.querySelector(".so-fb-step1").hidden = true;
        step2.hidden = true;
        thanks.hidden = false;
        markFeedbackSubmitted();
        feedbackRoot.classList.add("is-done");
      } catch (err) {
        errorEl.textContent = (err && err.message) || "Something went wrong. Please try again.";
        errorEl.hidden = false;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
      }
    });
  }

  // ---------- "+ Request a Resort" Modal ----------
  let resortModal = null;

  function ensureResortModal() {
    if (resortModal) return resortModal;

    resortModal = document.createElement("div");
    resortModal.id = "soRequestModal";
    resortModal.className = "so-modal-backdrop";
    resortModal.setAttribute("aria-hidden", "true");
    resortModal.innerHTML = `
      <div class="so-modal-card" role="dialog" aria-modal="true" aria-labelledby="soReqTitle">
        <div class="so-modal-head">
          <div>
            <h3 class="so-modal-title" id="soReqTitle">Request a Resort</h3>
            <p class="so-modal-sub">Tell us which luxury hotel or resort you want added to StayOdds.</p>
          </div>
          <button type="button" class="so-fb-close" id="soReqClose" aria-label="Close modal">&times;</button>
        </div>

        <form id="soReqForm" class="so-modal-body" novalidate>
          <input type="checkbox" name="botcheck" id="soReqBotcheck" tabindex="-1" autocomplete="off" style="display:none;" />

          <div class="so-fb-field">
            <label class="so-fb-label" for="soReqName">Resort Name <span class="so-req-star">*</span></label>
            <input type="text" id="soReqName" class="so-input" required maxlength="140" placeholder="e.g. Amanpulo, Six Senses Fiji, Four Seasons Bora Bora" />
          </div>

          <div class="so-fb-field">
            <label class="so-fb-label" for="soReqDest">Country / Destination <span class="so-req-star">*</span></label>
            <input type="text" id="soReqDest" class="so-input" required maxlength="120" placeholder="e.g. Philippines, Maldives, Lake Como" />
          </div>

          <div class="so-fb-field">
            <label class="so-fb-label" for="soReqNote">Comparing it against another hotel? <span class="so-opt-tag">(Optional)</span></label>
            <textarea id="soReqNote" class="so-fb-textarea" rows="2" maxlength="500" placeholder="e.g. Deciding between this and Soneva Fushi for October…"></textarea>
          </div>

          <div class="so-fb-error" id="soReqError" role="alert" hidden></div>

          <div class="so-modal-actions">
            <button type="button" class="btn btn-outline" id="soReqCancel">Cancel</button>
            <button type="submit" class="btn btn-primary" id="soReqSubmit">Submit Request</button>
          </div>
        </form>

        <div class="so-modal-success" id="soReqSuccess" hidden>
          <div class="so-fb-thanks-icon" aria-hidden="true">&#10003;</div>
          <h4 class="so-fb-thanks-title">Resort request received!</h4>
          <p class="so-fb-thanks-sub" id="soReqSuccessMsg">Thanks — we&rsquo;ll verify its awards, critic reviews, and guest ratings and add it to the StayOdds queue.</p>
          <div class="so-modal-actions" style="justify-content:center;margin-top:14px;">
            <button type="button" class="btn btn-outline" id="soReqAnother">Request Another</button>
            <button type="button" class="btn btn-primary" id="soReqDone">Done</button>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(resortModal);

    const closeBtn = document.getElementById("soReqClose");
    const cancelBtn = document.getElementById("soReqCancel");
    const doneBtn = document.getElementById("soReqDone");
    const anotherBtn = document.getElementById("soReqAnother");
    const form = document.getElementById("soReqForm");
    const successEl = document.getElementById("soReqSuccess");
    const successMsg = document.getElementById("soReqSuccessMsg");
    const errorEl = document.getElementById("soReqError");
    const submitBtn = document.getElementById("soReqSubmit");
    const nameInput = document.getElementById("soReqName");
    const destInput = document.getElementById("soReqDest");
    const noteInput = document.getElementById("soReqNote");
    const botcheckEl = document.getElementById("soReqBotcheck");

    function closeModal() {
      resortModal.classList.remove("is-open");
      resortModal.setAttribute("aria-hidden", "true");
    }

    function resetForm() {
      form.reset();
      form.hidden = false;
      successEl.hidden = true;
      errorEl.hidden = true;
      setTimeout(() => nameInput.focus(), 50);
    }

    closeBtn.addEventListener("click", closeModal);
    cancelBtn.addEventListener("click", closeModal);
    doneBtn.addEventListener("click", closeModal);
    anotherBtn.addEventListener("click", resetForm);

    resortModal.addEventListener("click", (e) => {
      if (e.target === resortModal) closeModal();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && resortModal.classList.contains("is-open")) {
        closeModal();
      }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resortName = (nameInput.value || "").trim();
      const destination = (destInput.value || "").trim();
      const comparisonNote = (noteInput.value || "").trim();

      if (!resortName || !destination) {
        errorEl.textContent = "Please enter both the resort name and country / destination.";
        errorEl.hidden = false;
        if (!resortName) nameInput.focus();
        else destInput.focus();
        return;
      }

      errorEl.hidden = true;
      submitBtn.disabled = true;
      const origText = submitBtn.textContent;
      submitBtn.textContent = "Submitting…";

      try {
        const payload = {
          access_key: WEB3FORMS_KEY,
          subject: "Stay Odds - Resort Request",
          botcheck: Boolean(botcheckEl && botcheckEl.checked),
          resort_name: resortName,
          destination,
          comparison_note: comparisonNote || "(None)",
          page_url: window.location.href,
          device_width: window.innerWidth,
        };

        const response = await fetch(WEB3FORMS_URL, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json",
          },
          body: JSON.stringify(payload),
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
          throw new Error(data.message || "Could not submit your request right now.");
        }

        trackEvent("request_resort", "resort", resortName);
        if (successMsg) {
          successMsg.textContent = `Thanks! "${resortName}" (${destination}) has been added to our StayOdds research queue.`;
        }
        form.hidden = true;
        successEl.hidden = false;
      } catch (err) {
        errorEl.textContent = (err && err.message) || "Something went wrong. Please try again.";
        errorEl.hidden = false;
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = origText;
      }
    });

    return resortModal;
  }

  function openResortModal() {
    const modal = ensureResortModal();
    const form = document.getElementById("soReqForm");
    const successEl = document.getElementById("soReqSuccess");
    const errorEl = document.getElementById("soReqError");
    if (form && successEl && form.hidden) {
      form.reset();
      form.hidden = false;
      successEl.hidden = true;
    }
    if (errorEl) errorEl.hidden = true;
    modal.classList.add("is-open");
    modal.setAttribute("aria-hidden", "false");
    setTimeout(() => document.getElementById("soReqName")?.focus(), 60);
  }

  window.openResortRequestModal = openResortModal;

  // ---------- Rotating Tropical Hero Banners ----------
  const HERO_BANNER_FILES = ["maldives.jpg", "bali.jpg", "bora-bora.jpg", "seychelles.jpg"];

  function initHeroBannerRotator() {
    const cards = document.querySelectorAll(".hero-banner-card[data-hero-rotate]");
    if (!cards.length) return;
    const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    cards.forEach((card) => {
      const base = card.getAttribute("data-hero-base") || "../assets/banners/";
      let idx = Math.max(0, parseInt(card.getAttribute("data-hero-start") || "0", 10) || 0) % HERO_BANNER_FILES.length;
      const urls = HERO_BANNER_FILES.map((f) => base + f);

      const layerA = document.createElement("div");
      const layerB = document.createElement("div");
      const scrim = document.createElement("div");
      layerA.className = "hero-bg-layer is-active";
      layerB.className = "hero-bg-layer";
      scrim.className = "hero-bg-scrim";
      layerA.style.backgroundImage = `url('${urls[idx]}')`;

      card.insertBefore(scrim, card.firstChild);
      card.insertBefore(layerB, card.firstChild);
      card.insertBefore(layerA, card.firstChild);

      if (reducedMotion || urls.length < 2) return;

      let showingA = true;
      setInterval(() => {
        if (document.hidden) return;
        const nextIdx = (idx + 1) % urls.length;
        const nextUrl = urls[nextIdx];
        const preloader = new Image();
        preloader.onload = () => {
          idx = nextIdx;
          if (showingA) {
            layerB.style.backgroundImage = `url('${nextUrl}')`;
            layerB.classList.add("is-active");
            layerA.classList.remove("is-active");
          } else {
            layerA.style.backgroundImage = `url('${nextUrl}')`;
            layerA.classList.add("is-active");
            layerB.classList.remove("is-active");
          }
          showingA = !showingA;
        };
        preloader.src = nextUrl;
      }, 8500);
    });
  }

  // ---------- Zero-Login Hotel Shortlist (localStorage) ----------
  const LS_SHORTLIST_KEY = "stayodds_shortlist_v1";

  function readShortlist() {
    try {
      const raw = localStorage.getItem(LS_SHORTLIST_KEY);
      if (!raw) return [];
      const arr = JSON.parse(raw);
      return Array.isArray(arr) ? arr.filter((x) => typeof x === "string" && x.trim()) : [];
    } catch (_) {
      return [];
    }
  }

  function writeShortlist(ids) {
    const unique = Array.from(new Set(ids));
    try {
      localStorage.setItem(LS_SHORTLIST_KEY, JSON.stringify(unique));
    } catch (_) {}
    return unique;
  }

  function syncShortlistButtons() {
    const saved = new Set(readShortlist());
    document.querySelectorAll("[data-shortlist-id]").forEach((btn) => {
      const id = btn.getAttribute("data-shortlist-id");
      if (!id) return;
      const isSaved = saved.has(id);
      btn.classList.toggle("is-saved", isSaved);
      btn.setAttribute("aria-pressed", String(isSaved));
      const compact = btn.getAttribute("data-shortlist-compact") === "1";
      btn.innerHTML = isSaved
        ? (compact ? "&#9829; Saved" : "&#9829; Saved to Shortlist")
        : (compact ? "&#9825; Save" : "&#9825; Save to Shortlist");
    });
  }

  function toggleShortlistId(id, resortName) {
    if (!id) return false;
    const current = readShortlist();
    const exists = current.includes(id);
    const next = exists ? current.filter((x) => x !== id) : [id, ...current];
    writeShortlist(next);
    syncShortlistButtons();
    trackEvent(exists ? "remove_shortlist" : "add_shortlist", "resort", resortName || id);
    window.dispatchEvent(new CustomEvent("stayodds:shortlist-changed", { detail: { ids: next, id, saved: !exists } }));
    return !exists;
  }

  window.stayOddsShortlist = {
    get: readShortlist,
    has: (id) => readShortlist().includes(id),
    toggle: toggleShortlistId,
    syncButtons: syncShortlistButtons,
  };

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-shortlist-id]");
    if (!btn) return;
    e.preventDefault();
    const id = btn.getAttribute("data-shortlist-id");
    const name = btn.getAttribute("data-resort-name") || resolveResortName(btn);
    toggleShortlistId(id, name);
  });

  window.addEventListener("storage", (e) => {
    if (e.key === LS_SHORTLIST_KEY) {
      syncShortlistButtons();
      window.dispatchEvent(new CustomEvent("stayodds:shortlist-changed", { detail: { ids: readShortlist() } }));
    }
  });

  function boot() {
    initHeroBannerRotator();
    mountFeedbackWidget();
    trackBreakdownLanding();
    syncShortlistButtons();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
