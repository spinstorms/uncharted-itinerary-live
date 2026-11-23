import {
  BRAND,
  computeStayOdds,
  formatPersonalScore,
  isFirstHandVerified,
  isVisitedProperty,
} from "./stayodds-engine.js?v=7";
import {
  getPropertyStatusMeta,
  openVsShareModal,
} from "./stayodds-share-card.js?v=1";

const PAGE_SIZE = 24;
const oddsCache = new WeakMap();

function getOdds(h) {
  let cached = oddsCache.get(h);
  if (!cached) {
    cached = computeStayOdds(h);
    oddsCache.set(h, cached);
  }
  return cached;
}

const SHORTLIST_KEY = "stayodds_shortlist_v1";
const POINTS_BRAND_RE = /\b(marriott|st\.?\s*regis|ritz-carlton|luxury collection|w hotels|edition|jw marriott|hyatt|park hyatt|alila|andaz|hilton|waldorf|conrad|lxr|ihg|six senses|regent|intercontinental|kimpton)\b/i;

function getShortlistIds() {
  if (window.stayOddsShortlist && typeof window.stayOddsShortlist.get === "function") {
    return window.stayOddsShortlist.get();
  }
  try {
    const raw = localStorage.getItem(SHORTLIST_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch (_) {
    return [];
  }
}

const VERIFIED_FEATURES = [
  { id: "all", label: "All", match: () => true },
  {
    id: "michelin",
    label: "MICHELIN Key",
    match: (h) => (h.officialAwards || []).some((a) => /michelin/i.test(`${a.awardBody || ""} ${a.label || ""}`)),
  },
  {
    id: "forbes",
    label: "Forbes Five-Star",
    match: (h) => (h.officialAwards || []).some((a) => /forbes/i.test(`${a.awardBody || ""} ${a.label || ""}`)),
  },
  {
    id: "50best",
    label: "World's 50 Best",
    match: (h) => (h.officialAwards || []).some((a) => /50\s*best/i.test(`${a.awardBody || ""} ${a.label || ""}`)),
  },
  {
    id: "video",
    label: "Video Reviews",
    match: (h) => Boolean(h.videoId || (h.youtubeReviews && h.youtubeReviews.length > 0)),
  },
  {
    id: "points",
    label: "Points Brands",
    match: (h) => POINTS_BRAND_RE.test(`${h.brand || ""} ${h.name || ""}`),
  },
  {
    id: "beach",
    label: "House Reef / Beach",
    match: (h) => Boolean((h.keyFacts && h.keyFacts.beachOrReef) || h.region === "Maldives"),
  },
];

const state = {
  hotels: [],
  visitedCount: 0,
  worldCount: 0,
  scope: "all", // "all" | "visited" | "world" | "saved"
  region: "All",
  feature: "all",
  verdict: "All",
  sortBy: "visited",
  search: "",
  searchA: "",
  searchB: "",
  visibleLimit: PAGE_SIZE,
  idA: "taaktana-labuan-bajo",
  idB: "st-regis-bali",
};

const qs = (sel) => document.querySelector(sel);

function escapeHtml(str = "") {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

const isEmbedParam = new URLSearchParams(window.location.search).get("embed") === "1";

function getSeoHref(h) {
  return isEmbedParam
    ? `../stayodds/${encodeURIComponent(h.id)}/?embed=1`
    : `../stayodds/${encodeURIComponent(h.id)}/`;
}

function getTripAdvisorUrl(h) {
  const q = `${h.name || ""} ${h.location || h.country || ""}`.trim();
  return `https://www.tripadvisor.com/Search?q=${encodeURIComponent(q)}&ssrc=h`;
}

function matchRegionParam(rawRegion, hotels) {
  if (!rawRegion) return null;
  const target = rawRegion.trim().toLowerCase();
  if (!target || target === "all") return "All";
  const regions = Array.from(new Set(hotels.map((h) => h.region).filter(Boolean)));
  const exact = regions.find((r) => r.toLowerCase() === target);
  if (exact) return exact;
  const partial = regions.find((r) => r.toLowerCase().includes(target));
  return partial || null;
}

function syncUrlParams(includeCompare = false) {
  try {
    const url = new URL(window.location.href);
    if (state.region && state.region !== "All") url.searchParams.set("region", state.region);
    else url.searchParams.delete("region");
    if (state.scope && state.scope !== "all") url.searchParams.set("scope", state.scope);
    else url.searchParams.delete("scope");
    if (includeCompare && state.idA && state.idB) {
      url.searchParams.set("a", state.idA);
      url.searchParams.set("b", state.idB);
    }
    window.history.replaceState({}, "", url.toString());
  } catch (_) {}
}

function resolveThumb(thumb) {
  if (!thumb) return "../assets/placeholders/default-stayodds.webp";
  if (/^https?:\/\//i.test(thumb) || thumb.startsWith("../") || thumb.startsWith("/")) return thumb;
  return `../${thumb}`;
}

function getReviewHref(h) {
  if (!h.videoId) return "";
  if (h.coverageType === "Short Tour") {
    return `https://www.youtube.com/shorts/${encodeURIComponent(h.videoId)}`;
  }
  if (h.inLiveFeed) return `../?video=${encodeURIComponent(h.videoId)}`;
  return `https://www.youtube.com/watch?v=${encodeURIComponent(h.videoId)}`;
}

function isExternalReview(h) {
  if (h.coverageType === "Short Tour") return true;
  return !(h.inLiveFeed && h.videoId);
}

function initCommonUi() {
  if (new URLSearchParams(window.location.search).get("embed") === "1") {
    document.body.classList.add("embed-mode");
  }
  const yearEl = qs("#yearNow");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  const menuBtn = qs("#mobileMenuBtn");
  const mobileNav = qs("#mobileNav");
  if (menuBtn && mobileNav) {
    menuBtn.addEventListener("click", () => {
      const open = mobileNav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
  }
}

function matchesSelectorQuery(h, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return true;
  const hay = `${h.name || ""} ${h.location || ""} ${h.country || ""} ${h.brand || ""} ${h.region || ""}`.toLowerCase();
  return q.split(/\s+/).every((tok) => hay.includes(tok));
}

function populateSingleSelector(side) {
  const isA = side === "A";
  const sel = qs(isA ? "#compareSelectA" : "#compareSelectB");
  const clearBtn = qs(isA ? "#compareClearA" : "#compareClearB");
  const metaEl = qs(isA ? "#compareMetaA" : "#compareMetaB");
  const emptyEl = qs(isA ? "#compareEmptyA" : "#compareEmptyB");
  if (!sel) return;

  const query = isA ? state.searchA : state.searchB;
  const trimmed = query.trim();
  if (clearBtn) clearBtn.classList.toggle("is-visible", trimmed.length > 0);

  const filtered = state.hotels.filter((h) => matchesSelectorQuery(h, trimmed));
  const visited = filtered.filter(isVisitedProperty);
  const globalOnly = filtered.filter((h) => !isVisitedProperty(h));

  const renderOpt = (h) =>
    `<option value="${escapeHtml(h.id)}">${escapeHtml(h.name)} (${escapeHtml(h.location)}, ${escapeHtml(h.country)})</option>`;

  if (!filtered.length) {
    sel.innerHTML = `<option value="" disabled selected>No matching hotels found</option>`;
    sel.disabled = true;
    if (metaEl) metaEl.textContent = `0 of ${state.hotels.length} hotels matched`;
    if (emptyEl) {
      emptyEl.textContent = `No hotels matched "${trimmed}". Try a different hotel name, city, country, or brand — or click × to clear.`;
      emptyEl.classList.add("is-visible");
    }
    return;
  }

  sel.disabled = false;
  if (emptyEl) {
    emptyEl.textContent = "";
    emptyEl.classList.remove("is-visible");
  }
  if (metaEl) {
    metaEl.textContent = trimmed
      ? `Showing ${filtered.length} of ${state.hotels.length} matching hotels`
      : `${state.hotels.length} verified hotels available`;
  }

  let html = "";
  if (visited.length) {
    html += `<optgroup label="★ First-Hand Stays &amp; Shorts (${visited.length})">${visited.map(renderOpt).join("")}</optgroup>`;
  }
  if (globalOnly.length) {
    html += `<optgroup label="🌍 Global Luxury Directory (${globalOnly.length})">${globalOnly.map(renderOpt).join("")}</optgroup>`;
  }
  sel.innerHTML = html;

  const currentId = isA ? state.idA : state.idB;
  if (filtered.some((h) => h.id === currentId)) {
    sel.value = currentId;
  } else {
    const nextId = filtered[0].id;
    sel.value = nextId;
    if (isA) state.idA = nextId;
    else state.idB = nextId;
  }
}

function populateH2HSelectors() {
  if (!state.hotels.some((h) => h.id === state.idA)) {
    const visited = state.hotels.filter(isVisitedProperty);
    if (visited.length) state.idA = visited[0].id;
    else if (state.hotels.length) state.idA = state.hotels[0].id;
  }
  if (!state.hotels.some((h) => h.id === state.idB)) {
    if (state.hotels.length > 1) state.idB = state.hotels[1].id;
  }
  populateSingleSelector("A");
  populateSingleSelector("B");
}

function renderH2HCard(h, opponent) {
  const o = getOdds(h);
  const oo = getOdds(opponent);
  const s = h.scores || {};
  const os = opponent.scores || {};
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
  const st = getPropertyStatusMeta(h);

  const metricRow = (label, a, b, suffix = "", missingText = "—") => {
    const aMissing = a == null;
    const bMissing = b == null;
    const wins = !aMissing && !bMissing && Number(a) > Number(b);
    const display = aMissing ? missingText : `${a}${suffix}`;
    return `
      <div class="h2h-metric ${wins ? "is-best" : ""}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(display)} ${wins ? "★" : ""}</strong>
      </div>
    `;
  };

  const guestDisplay = o.verifiedGuest
    ? `${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}`
    : null;
  const unratedLabel = o.visited
    ? h.coverageType === "Short Tour"
      ? "Short Tour"
      : "Filmed (Unscored)"
    : "Not Visited";

  const criticDisplay =
    o.scoredEditorial.length === 1
      ? `${o.primaryCritic.rawScore || `${o.critic100}/100`} (${o.primaryCritic.sourceName})`
      : o.scoredEditorial.length > 1
      ? `${o.critic100}/100 (${o.scoredEditorial.length} critics)`
      : null;

  const awardsHtml =
    o.officialAwards.length > 0
      ? o.officialAwards
          .map(
            (a) =>
              `<a href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:underline;">${escapeHtml(a.label)} ↗</a>`
          )
          .join(" • ")
      : "None listed";

  const statusToneClass =
    st.tone === "danger"
      ? "is-danger"
      : st.tone === "warn"
      ? "is-warn"
      : st.tone === "open"
      ? "is-open"
      : "";
  const statusTagClass =
    st.tone === "danger"
      ? "tag-danger"
      : st.tone === "warn"
      ? "tag-caution"
      : st.tone === "open"
      ? "tag-teal"
      : "tag-slate";

  const statusHtml = `
    <div class="h2h-status-strip ${statusToneClass}">
      <div class="h2h-status-strip-head">
        <span>Property Status &amp; Works</span>
        <span class="tag ${statusTagClass}" style="font-size:10.5px;padding:2px 7px;">${escapeHtml(st.badge)}</span>
      </div>
      <div>${escapeHtml(st.shortSummary)}</div>
      ${
        st.sourceUrl
          ? `<div style="margin-top:4px;font-size:11.5px;"><a href="${escapeHtml(st.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--accent);text-decoration:underline;">Verified source &nearr;</a></div>`
          : ""
      }
    </div>
  `;

  return `
    <article class="h2h-card" data-resort-name="${escapeHtml(h.name)}">
      <div class="h2h-card-head">
        <img src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" decoding="async" />
        <div>
          <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${escapeHtml(o.tierLabel)}</span>
          <h3><a class="consensus-title-link" href="${getSeoHref(h)}">${escapeHtml(h.name)}</a></h3>
          <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)}${h.brand ? ` &bull; ${escapeHtml(h.brand)}` : ""}</div>
        </div>
      </div>

      <div class="h2h-odds-strip">
        <div class="odds-big">
          <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : o.officialAwards.length ? "Awarded" : "Open"}</strong>
          <span>${escapeHtml(o.statusBadge)}</span>
        </div>
        <div class="index-big">
          <strong>${escapeHtml(o.opinionGap.deltaLabel)}</strong>
          <span>Opinion Gap</span>
        </div>
      </div>

      ${statusHtml}

      <div class="h2h-metrics-list">
        ${metricRow("My First-Hand Stay", o.ours100, oo.ours100, "", unratedLabel).replace(
          `${o.ours100}`,
          o.personalScoreLabel || unratedLabel
        )}
        ${metricRow("Verified Guest Score", o.guest100, oo.guest100, "", "Open Breakdown").replace(
          `${o.guest100}`,
          guestDisplay || "Open Breakdown"
        )}
        ${metricRow("Published Critics", o.critic100, oo.critic100, "", "No critic score").replace(
          `${o.critic100}`,
          criticDisplay || "No critic score"
        )}
        <div class="h2h-metric">
          <span>Official Awards</span>
          <strong style="text-align:right;font-size:12.5px;">${awardsHtml}</strong>
        </div>
        ${metricRow("Value", o.firstHand ? formatPersonalScore(s.value) : null, oo.firstHand ? formatPersonalScore(os.value) : null, " / 5", unratedLabel)}
        ${metricRow("Room Quality", o.firstHand ? formatPersonalScore(s.rooms) : null, oo.firstHand ? formatPersonalScore(os.rooms) : null, " / 5", unratedLabel)}
        ${metricRow("Vibe", o.firstHand ? formatPersonalScore(s.grounds) : null, oo.firstHand ? formatPersonalScore(os.grounds) : null, " / 5", unratedLabel)}
        ${metricRow("Food", o.firstHand ? formatPersonalScore(s.food) : null, oo.firstHand ? formatPersonalScore(os.food) : null, " / 5", unratedLabel)}
        ${metricRow("Service", o.firstHand ? formatPersonalScore(s.service) : null, oo.firstHand ? formatPersonalScore(os.service) : null, " / 5", unratedLabel)}
      </div>

      <p class="h2h-diff"><strong>${escapeHtml(o.opinionGap.title)}:</strong> ${escapeHtml(o.opinionGap.headline)}${
        h.whereWeDiffer ? `<br><span style="color:#334155;"><strong>My Take:</strong> ${escapeHtml(h.whereWeDiffer)}</span>` : ""
      }</p>

      <div class="scorecard-actions">
        <a class="btn btn-primary" href="${getSeoHref(h)}">Full Breakdown &rarr;</a>
        ${
          reviewHref
            ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${h.coverageType === "Short Tour" ? "Watch Short" : "Watch Review"}</a>`
            : ""
        }
        <button type="button" class="btn btn-outline shortlist-btn" data-shortlist-id="${escapeHtml(h.id)}" data-shortlist-compact="1" data-resort-name="${escapeHtml(h.name)}" aria-pressed="false">&#9825; Save</button>
        <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
      </div>
      <div style="margin-top:8px;">
        <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
      </div>
    </article>
  `;
}

function renderH2H() {
  const out = qs("#h2hOutput");
  if (!out) return;
  const a = state.hotels.find((h) => h.id === state.idA) || state.hotels[0];
  const b = state.hotels.find((h) => h.id === state.idB) || state.hotels[1];
  if (!a || !b) return;
  out.innerHTML = renderH2HCard(a, b) + renderH2HCard(b, a);
  window.stayOddsShortlist?.syncButtons?.();
}

function getScopedHotels() {
  if (state.scope === "visited") return state.hotels.filter(isVisitedProperty);
  if (state.scope === "world") return state.hotels.filter((h) => !isVisitedProperty(h));
  if (state.scope === "saved") {
    const savedSet = new Set(getShortlistIds());
    return state.hotels.filter((h) => savedSet.has(h.id));
  }
  return state.hotels;
}

function renderScopeTabs() {
  const container = qs("#stayOddsScopeTabs");
  if (!container) return;
  const savedIds = getShortlistIds();
  const savedCount = state.hotels.filter((h) => savedIds.includes(h.id)).length;
  const tabs = [
    { id: "all", label: `All Luxury Properties (${state.hotels.length})` },
    { id: "visited", label: `First-Hand Verified & Shorts (${state.visitedCount})` },
    { id: "world", label: `Global Directory (${state.worldCount})` },
    { id: "saved", label: `♥ Saved (${savedCount})` },
  ];
  container.innerHTML = tabs
    .map(
      (t) =>
        `<button class="scope-pill ${state.scope === t.id ? "active" : ""}" data-scope="${t.id}" type="button">${escapeHtml(
          t.label
        )}</button>`
    )
    .join("");

  container.querySelectorAll("[data-scope]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.scope = btn.dataset.scope || "all";
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `scope:${state.scope}`);
      }
      const scoped = getScopedHotels();
      if (state.region !== "All" && !scoped.some((h) => h.region === state.region)) {
        state.region = "All";
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderScopeTabs();
      renderRegionPills();
      renderFeaturePills();
      renderLeaderboard();
    });
  });
}

function renderRegionPills() {
  const container = qs("#consensusRegionPills");
  if (!container) return;
  const scoped = getScopedHotels();
  const regions = ["All", ...Array.from(new Set(scoped.map((h) => h.region)))];
  container.innerHTML = regions
    .map((r) => {
      const cnt = r === "All" ? scoped.length : scoped.filter((h) => h.region === r).length;
      return `<button class="pill ${state.region === r ? "active" : ""}" data-region="${escapeHtml(
        r
      )}" role="tab">${escapeHtml(r)} (${cnt})</button>`;
    })
    .join("");

  container.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.region = btn.dataset.region || "All";
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `region:${state.region}`);
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderRegionPills();
      renderFeaturePills();
      renderLeaderboard();
    });
  });
}

function renderFeaturePills() {
  const container = qs("#featureFilterPills");
  if (!container) return;
  const baseList = getScopedHotels().filter((h) => state.region === "All" || h.region === state.region);
  container.innerHTML = VERIFIED_FEATURES.map((f) => {
    const cnt = f.id === "all" ? baseList.length : baseList.filter(f.match).length;
    return `<button class="feature-pill ${state.feature === f.id ? "active" : ""}" data-feature="${escapeHtml(
      f.id
    )}" type="button">${escapeHtml(f.label)} (${cnt})</button>`;
  }).join("");

  container.querySelectorAll("[data-feature]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.feature = btn.dataset.feature || "all";
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `feature:${state.feature}`);
      }
      state.visibleLimit = PAGE_SIZE;
      renderFeaturePills();
      renderLeaderboard();
    });
  });
}

function renderLeaderboard() {
  const container = qs("#consensusList");
  if (!container) return;

  const q = state.search.trim().toLowerCase();
  const activeFeature = VERIFIED_FEATURES.find((f) => f.id === state.feature) || VERIFIED_FEATURES[0];
  const list = getScopedHotels().filter((h) => {
    const o = getOdds(h);
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.verdict !== "All" && o.statusBadge !== state.verdict) return false;
    if (activeFeature.id !== "all" && !activeFeature.match(h)) return false;
    if (!q) return true;
    const hay = [
      h.name,
      h.location,
      h.country,
      h.region,
      h.brand,
      h.verdict,
      h.standout,
      h.watchOut,
      o.tierLabel,
      o.statusBadge,
      ...o.keyFacts.map((f) => f.value),
      ...o.redFlags,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  list.sort((a, b) => {
    const oa = getOdds(a);
    const ob = getOdds(b);
    if (state.sortBy === "name") return a.name.localeCompare(b.name);
    if (state.sortBy === "odds") {
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    const rank = (o) => (o.firstHand ? 2 : o.visited ? 1 : 0);
    if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
    return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
  });

  if (!list.length) {
    const emptyMsg =
      state.scope === "saved" && getShortlistIds().length === 0
        ? `Your Shortlist is empty — tap "♡ Save" on any hotel card or breakdown page to build your personal comparison list (saved right in your browser, no login needed).`
        : `No resorts matched your filters. Try switching to "All Luxury Properties" or clearing your search.`;
    container.innerHTML = `<div class="empty-state">${escapeHtml(emptyMsg)}</div>`;
    return;
  }

  const visibleList = list.slice(0, state.visibleLimit);
  const remaining = list.length - visibleList.length;

  const cardsHtml = visibleList
    .map((h, i) => {
      const o = getOdds(h);
      const reviewHref = getReviewHref(h);
      const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
      const isShortOnly = h.coverageType === "Short Tour";
      const shortCount = Array.isArray(h.shorts) ? h.shorts.length : 0;

      const toneClass =
        o.statusTone === "amber"
          ? "is-contrarian"
          : o.statusTone === "accent"
          ? "is-strong"
          : o.statusTone === "teal"
          ? "is-aligned"
          : "is-external";
      const tagClass =
        o.statusTone === "amber"
          ? "tag-caution"
          : o.statusTone === "accent"
          ? "tag-accent"
          : o.statusTone === "teal"
          ? "tag-teal"
          : "tag-slate";

      const keyFactChips = [
        ...o.keyFacts.slice(0, 3).map((kf) => `<span class="card-key-fact-chip"><strong>${escapeHtml(kf.label)}:</strong> ${escapeHtml(kf.value)}</span>`),
        ...o.redFlags.slice(0, 2).map((rf) => `<span class="tag tag-caution">⚠ ${escapeHtml(rf)}</span>`),
      ].join("");

      const criticBoxHtml =
        o.scoredEditorial.length === 1
          ? `<small>Published Critic (${o.weights.critics}%)</small>
             <strong><a href="${escapeHtml(o.primaryCritic.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${escapeHtml(
               o.primaryCritic.rawScore || `${o.critic100}/100`
             )} ↗</a></strong>`
          : o.scoredEditorial.length > 1
          ? `<small>${o.scoredEditorial.length} Published Critics (${o.weights.critics}%)</small>
             <strong>${o.critic100} / 100</strong>`
          : o.editorialRatings.length > 0
          ? `<small>Website Review</small>
             <strong style="font-size:13px;"><a href="${escapeHtml(o.editorialRatings[0].sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${escapeHtml(
               o.editorialRatings[0].sourceName
             )} ↗</a></strong>`
          : `<small>Published Critics</small>
             <strong>No critic score</strong>`;

      const awardsBoxHtml =
        o.officialAwards.length > 0
          ? `<small>Official Awards</small>
             <strong style="font-size:13px;line-height:1.25;">${o.officialAwards
               .slice(0, 2)
               .map(
                 (a) =>
                   `<a href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${escapeHtml(
                     a.label
                   )} ↗</a>`
               )
               .join("<br>")}</strong>`
          : `<small>Official Awards</small>
             <strong>None listed</strong>`;

      const sourceChips = [
        ...o.officialAwards.map(
          (a) =>
            `<a class="source-chip" href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">🏆 ${escapeHtml(
              a.label
            )} ↗</a>`
        ),
        ...o.editorialRatings.map(
          (e) =>
            `<a class="source-chip" href="${escapeHtml(e.sourceUrl)}" target="_blank" rel="noopener noreferrer">📰 ${escapeHtml(
              e.sourceName
            )}${e.rawScore ? ` (${escapeHtml(e.rawScore)})` : ""} ↗</a>`
        ),
        ...o.youtubeReviews.slice(0, 3).map(
          (y) =>
            `<a class="source-chip" href="${escapeHtml(y.sourceUrl)}" target="_blank" rel="noopener noreferrer">▶ ${escapeHtml(
              y.creatorName
            )} ↗</a>`
        ),
      ].join("");

      const propStatus = getPropertyStatusMeta(h);
      const propStatusPill =
        propStatus.tone === "danger"
          ? `<span class="tag tag-danger">⚠ ${escapeHtml(propStatus.badge)}</span>`
          : propStatus.tone === "warn"
          ? `<span class="tag tag-caution">ⓘ ${escapeHtml(propStatus.badge)}</span>`
          : "";

      return `
        <article class="consensus-row-card ${toneClass}" data-resort-name="${escapeHtml(h.name)}">
          <div class="consensus-rank-col">
            <span class="consensus-rank-num">#${i + 1}</span>
            <div class="consensus-chance-ring ${toneClass}">
              <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : o.officialAwards.length ? "Award" : "Open"}</strong>
              <span>${o.greatStayOdds != null ? "StayOdds" : "See Details"}</span>
            </div>
            <div class="consensus-index-chip">
              ${
                o.sourceCount > 0
                  ? `<strong>${o.sourceCount}</strong> scored source${o.sourceCount === 1 ? "" : "s"}`
                  : o.officialAwards.length
                  ? `<strong>${o.officialAwards.length}</strong> official award${o.officialAwards.length === 1 ? "" : "s"}`
                  : "Open for Google"
              }
            </div>
          </div>

          <div class="consensus-main-col">
            <div class="meta-line">
              <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${escapeHtml(o.tierLabel)}</span>
              <span class="tag ${tagClass}">${escapeHtml(o.statusBadge)}</span>
              ${propStatusPill}
              ${shortCount ? `<span class="tag">${shortCount} Short${shortCount === 1 ? "" : "s"}</span>` : ""}
              ${h.brand ? `<span class="tag">${escapeHtml(h.brand)}</span>` : ""}
              <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
            </div>

            <h3 class="consensus-title">
              <a class="consensus-title-link" href="${getSeoHref(h)}">${escapeHtml(h.name)}</a>
            </h3>

            <div class="three-pillar-strip">
              <div class="pillar-box is-ours">
                <small>My Stay${o.weights.firstHand ? ` (${o.weights.firstHand}%)` : ""}</small>
                <strong>${
                  o.personalScoreLabel
                    ? escapeHtml(o.personalScoreLabel)
                    : o.visited
                    ? h.coverageType === "Short Tour"
                      ? "Short Tour"
                      : "Filmed Stay"
                    : "Not Visited"
                }</strong>
              </div>
              <div class="pillar-box is-critics">
                ${criticBoxHtml}
              </div>
              <div class="pillar-box is-google">
                <small>Verified Guests${o.weights.guests ? ` (${o.weights.guests}%)` : ""}</small>
                <strong>${o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}` : "Open Breakdown"}</strong>
              </div>
              <div class="pillar-box is-booking">
                ${awardsBoxHtml}
              </div>
            </div>

            <div class="card-opinion-strip">
              <span><strong>${escapeHtml(o.opinionGap.title)}:</strong> ${escapeHtml(o.opinionGap.headline)}</span>
              ${o.opinionGap.delta100 != null ? `<span class="card-opinion-delta">${escapeHtml(o.opinionGap.deltaLabel)}</span>` : ""}
            </div>

            ${keyFactChips ? `<div class="card-key-facts-strip">${keyFactChips}</div>` : ""}

            <div class="consensus-compare-notes">
              ${
                h.whereWeDiffer
                  ? `<p><strong>What I Liked &amp; Where I Differ:</strong> ${escapeHtml(h.whereWeDiffer)}</p>`
                  : ""
              }
              ${h.standout && h.standout !== h.whereWeDiffer ? `<p><strong>Standout:</strong> ${escapeHtml(h.standout)}</p>` : ""}
              ${h.watchOut ? `<p><strong>Watch-Out:</strong> ${escapeHtml(h.watchOut)}</p>` : ""}
            </div>

            <div class="consensus-sources">
              ${sourceChips}
              <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
              <span class="source-chip">${escapeHtml(o.formulaSummary)}</span>
            </div>
          </div>

          <div class="consensus-cta-col">
            <a href="${getSeoHref(h)}">
              <img class="consensus-thumb" src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" loading="lazy" decoding="async" />
            </a>
            <a class="btn btn-primary" href="${getSeoHref(h)}">Full Breakdown &rarr;</a>
            ${
              reviewHref
                ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Short" : "Watch Our Review"}</a>`
                : ""
            }
            <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &nearr;</a>
            <button type="button" class="btn btn-outline shortlist-btn" data-shortlist-id="${escapeHtml(h.id)}" data-shortlist-compact="1" data-resort-name="${escapeHtml(h.name)}" aria-pressed="false">&#9825; Save</button>
            <button class="copy-link-btn" data-compare-id="${escapeHtml(h.id)}" type="button">Compare Above &uarr;</button>
          </div>
        </article>
      `;
    })
    .join("");

  const pagerHtml =
    remaining > 0
      ? `<div class="load-more-bar" style="display:flex;gap:12px;justify-content:center;align-items:center;padding:20px 0 8px;flex-wrap:wrap;">
          <button class="btn btn-primary" id="loadMoreHotelsBtn" type="button">Show ${Math.min(PAGE_SIZE, remaining)} More (${visibleList.length} of ${list.length} shown)</button>
          <button class="btn btn-outline" id="showAllHotelsBtn" type="button">Show All ${list.length}</button>
        </div>`
      : "";

  container.innerHTML = cardsHtml + pagerHtml;
  window.stayOddsShortlist?.syncButtons?.();

  qs("#loadMoreHotelsBtn")?.addEventListener("click", () => {
    state.visibleLimit += PAGE_SIZE;
    renderLeaderboard();
  });
  qs("#showAllHotelsBtn")?.addEventListener("click", () => {
    state.visibleLimit = list.length;
    renderLeaderboard();
  });

  const shortsRail = qs("#compareShortsRail");
  const shortsSec = qs("#compareShortsSection");
  if (shortsRail && shortsSec) {
    const collected = [];
    const seenS = new Set();
    for (const h of list) {
      for (const sh of h.shorts || []) {
        if (!seenS.has(sh.id)) {
          seenS.add(sh.id);
          collected.push({ ...sh, hotelName: h.name, hotelId: h.id });
        }
      }
    }
    if (!collected.length) {
      shortsSec.style.display = "none";
    } else {
      shortsSec.style.display = "";
      shortsRail.innerHTML = collected
        .slice(0, 24)
        .map(
          (sh) => `
          <a class="short-card" href="https://www.youtube.com/shorts/${encodeURIComponent(sh.id)}" target="_blank" rel="noopener noreferrer">
            <div class="short-thumb">
              <img src="https://i.ytimg.com/vi/${encodeURIComponent(sh.id)}/hqdefault.jpg" alt="${escapeHtml(sh.title)}" loading="lazy" decoding="async" />
              <span class="short-badge">Short</span>
            </div>
            <div class="short-info">
              <h3 class="short-title">${escapeHtml(sh.title)}</h3>
              <div class="short-date">${escapeHtml(sh.hotelName.split(",")[0])} &bull; ${escapeHtml(sh.viewsText || "Short")}</div>
            </div>
          </a>
        `
        )
        .join("");
    }
  }

  function trackCompareSelection() {
    if (typeof window.trackEvent !== "function") return;
    const ha = state.hotels.find((h) => h.id === state.idA);
    const hb = state.hotels.find((h) => h.id === state.idB);
    if (ha && hb) {
      window.trackEvent("compare_resorts", "resorts", `${ha.name} vs ${hb.name}`);
    }
  }

  container.querySelectorAll("[data-compare-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.compareId;
      if (!id) return;
      state.idB = state.idA;
      state.idA = id;
      state.searchA = "";
      state.searchB = "";
      const inpA = qs("#compareSearchA");
      const inpB = qs("#compareSearchB");
      if (inpA) inpA.value = "";
      if (inpB) inpB.value = "";
      populateH2HSelectors();
      renderH2H();
      syncUrlParams(true);
      trackCompareSelection();
      qs(".h2h-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

async function boot() {
  initCommonUi();

  const params = new URLSearchParams(window.location.search);
  const hadCompareParams = Boolean(params.get("a") || params.get("b"));
  if (params.get("a")) state.idA = params.get("a");
  if (params.get("b")) state.idB = params.get("b");
  if (["all", "visited", "world", "saved"].includes(params.get("scope"))) {
    state.scope = params.get("scope");
  }

  function trackH2HDropdown() {
    if (typeof window.trackEvent !== "function") return;
    const ha = state.hotels.find((h) => h.id === state.idA);
    const hb = state.hotels.find((h) => h.id === state.idB);
    if (ha && hb) {
      window.trackEvent("compare_resorts", "resorts", `${ha.name} vs ${hb.name}`);
    }
  }

  qs("#shareVsCardBtn")?.addEventListener("click", () => {
    const ha = state.hotels.find((h) => h.id === state.idA) || state.hotels[0];
    const hb = state.hotels.find((h) => h.id === state.idB) || state.hotels[1];
    if (!ha || !hb) return;
    openVsShareModal(ha, hb, getOdds(ha), getOdds(hb));
    if (typeof window.trackEvent === "function") {
      window.trackEvent("open_share_card", "vs_pair", `${ha.name} vs ${hb.name}`);
    }
  });

  qs("#swapVsBtn")?.addEventListener("click", () => {
    const prevA = state.idA;
    state.idA = state.idB;
    state.idB = prevA;
    const prevSearchA = state.searchA;
    state.searchA = state.searchB;
    state.searchB = prevSearchA;
    const inpA = qs("#compareSearchA");
    const inpB = qs("#compareSearchB");
    if (inpA) inpA.value = state.searchA;
    if (inpB) inpB.value = state.searchB;
    populateH2HSelectors();
    renderH2H();
    syncUrlParams(true);
    trackH2HDropdown();
  });

  const wireSelectorSearch = (side) => {
    const isA = side === "A";
    const inp = qs(isA ? "#compareSearchA" : "#compareSearchB");
    const clearBtn = qs(isA ? "#compareClearA" : "#compareClearB");
    inp?.addEventListener("input", (e) => {
      const val = e.target.value || "";
      if (isA) state.searchA = val;
      else state.searchB = val;
      const prevId = isA ? state.idA : state.idB;
      populateSingleSelector(side);
      const nextId = isA ? state.idA : state.idB;
      if (nextId !== prevId) {
        renderH2H();
        syncUrlParams(true);
      }
    });
    clearBtn?.addEventListener("click", () => {
      if (isA) state.searchA = "";
      else state.searchB = "";
      if (inp) {
        inp.value = "";
        inp.focus();
      }
      populateSingleSelector(side);
    });
  };
  wireSelectorSearch("A");
  wireSelectorSearch("B");

  qs("#copyVsLinkBtn")?.addEventListener("click", async () => {
    const btn = qs("#copyVsLinkBtn");
    const shareUrl = `https://live.uncharteditinerary.com/compare/?a=${encodeURIComponent(state.idA)}&b=${encodeURIComponent(state.idB)}`;
    const ha = state.hotels.find((h) => h.id === state.idA);
    const hb = state.hotels.find((h) => h.id === state.idB);
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(shareUrl);
      } else {
        const tmp = document.createElement("textarea");
        tmp.value = shareUrl;
        tmp.style.position = "fixed";
        tmp.style.opacity = "0";
        document.body.appendChild(tmp);
        tmp.select();
        document.execCommand("copy");
        tmp.remove();
      }
      if (typeof window.trackEvent === "function" && ha && hb) {
        window.trackEvent("share_comparison", "vs_pair", `${ha.name} vs ${hb.name}`);
      }
      if (btn) {
        btn.classList.add("is-copied");
        btn.textContent = "✓ Copied VS Link!";
        setTimeout(() => {
          btn.classList.remove("is-copied");
          btn.innerHTML = "&#128279; Copy VS Link";
        }, 2200);
      }
    } catch (_) {
      window.prompt("Copy this Head-to-Head comparison link:", shareUrl);
    }
  });

  window.addEventListener("stayodds:shortlist-changed", () => {
    renderScopeTabs();
    if (state.scope === "saved") {
      renderRegionPills();
      renderFeaturePills();
      renderLeaderboard();
    }
  });

  qs("#compareSelectA")?.addEventListener("change", (e) => {
    state.idA = e.target.value;
    renderH2H();
    syncUrlParams(true);
    trackH2HDropdown();
  });
  qs("#compareSelectB")?.addEventListener("change", (e) => {
    state.idB = e.target.value;
    renderH2H();
    syncUrlParams(true);
    trackH2HDropdown();
  });
  qs("#verdictFilter")?.addEventListener("change", (e) => {
    state.verdict = e.target.value || "All";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `verdict:${state.verdict}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderLeaderboard();
  });
  qs("#consensusSort")?.addEventListener("change", (e) => {
    state.sortBy = e.target.value || "visited";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `sort:${state.sortBy}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderLeaderboard();
  });
  let searchTimer = null;
  qs("#consensusSearch")?.addEventListener("input", (e) => {
    state.search = e.target.value || "";
    state.visibleLimit = PAGE_SIZE;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => renderLeaderboard(), 120);
  });

  try {
    const res = await fetch(`../data/stayodds-index.json?v=20261123c`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload = await res.json();

    const hotels = payload.hotels || [];
    state.hotels = hotels;
    state.visitedCount = hotels.filter(isVisitedProperty).length;
    state.worldCount = hotels.length - state.visitedCount;

    const ratedCount = hotels.filter(isFirstHandVerified).length;
    const statEl = qs("#consensusSummaryStat");
    if (statEl) {
      statEl.textContent = `${hotels.length} Luxury Properties • ${ratedCount} First-Hand Verified`;
    }

    const matchedRegion = matchRegionParam(params.get("region"), getScopedHotels());
    if (matchedRegion) {
      state.region = matchedRegion;
    }

    populateH2HSelectors();
    renderH2H();
    renderScopeTabs();
    renderRegionPills();
    renderFeaturePills();
    renderLeaderboard();

    if (hadCompareParams) {
      requestAnimationFrame(() => {
        qs(".h2h-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } else if (matchedRegion && matchedRegion !== "All") {
      requestAnimationFrame(() => {
        qs(".leaderboard-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  } catch (err) {
    const el = qs("#consensusList");
    if (el) el.innerHTML = `<div class="empty-state">Unable to load ${escapeHtml(BRAND.name)} right now.</div>`;
    console.error("Failed to load StayOdds directory:", err);
  }
}

boot();
