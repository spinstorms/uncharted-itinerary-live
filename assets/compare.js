import {
  BRAND,
  MACRO_REGIONS,
  buildDatedBookingUrl,
  computeStayOdds,
  fetchLiveHotelRates,
  formatPersonalScore,
  getPriceDisplay,
  isFirstHandVerified,
  isScoreUnverified,
  isVisitedProperty,
} from "./stayodds-engine.js?v=10";
import { TRAVEL_STYLES, matchesTravelStyle } from "./stayodds-categories.js?v=2";
import {
  MONTH_LABELS,
  normalizeBrandName,
  getBrandCategories,
  matchesBrandCategory,
  getPartnerPrograms,
  getBestMonthsMeta,
  matchesBestMonth,
  getGuestProfile,
  getVerifiedRoomTip,
  exportHotelsToCsv,
} from "./stayodds-insights.js?v=4";

function getPropertyStatusMeta(hotel) {
  const st = (hotel && hotel.propertyStatus) || {};
  const op = (st.operatingStatus || "").trim();
  const reno = (st.renovationsExtensions || "").trim();
  const nearby = (st.nearbyConstruction || "").trim();
  const srcUrl = (st.sourceUrl || "").trim();
  const srcNote = (st.sourceNote || "").trim();
  const verifiedAt = (st.verifiedAt || "").trim();
  const hasDetails = Boolean(op || reno || nearby);
  const lower = op.toLowerCase();

  let badge = op || "No Works Listed";
  let tone = "neutral";
  if (lower.includes("closed")) {
    tone = "danger";
  } else if (lower.includes("rebrand") || lower.includes("transition") || nearby) {
    tone = "warn";
  } else if (op === "Open" && reno) {
    tone = "open";
    badge = "Open · Recent Works";
  } else if (op === "Open") {
    tone = "open";
  }

  let shortSummary = "No confirmed renovations, closures, or nearby works listed";
  if (lower.includes("closed")) {
    shortSummary = reno || `${op} — check reopening status before booking.`;
  } else if (lower.includes("rebrand") || lower.includes("transition")) {
    shortSummary = reno || `${op} — verify current brand & operator.`;
  } else if (reno && nearby) {
    shortSummary = `${reno} Nearby: ${nearby}`;
  } else if (reno) {
    shortSummary = reno;
  } else if (nearby) {
    shortSummary = `Nearby works: ${nearby}`;
  }

  return {
    hasDetails,
    operatingStatus: op || "No confirmed works listed",
    badge,
    tone,
    renovationsExtensions: reno,
    nearbyConstruction: nearby,
    sourceUrl: srcUrl,
    sourceNote: srcNote,
    verifiedAt,
    shortSummary,
  };
}

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
    id: "50best_50",
    label: "🏆 Top 50 (#1–50)",
    autoSort: "award_50best",
    match: (h) => {
      const r = getW50BestRank(h);
      return r != null && r >= 1 && r <= 50;
    },
  },
  {
    id: "50best_100",
    label: "💯 Top 100 (#1–100)",
    autoSort: "award_50best",
    match: (h) => {
      const r = getW50BestRank(h);
      return r != null && r >= 1 && r <= 100;
    },
  },
  {
    id: "50best_51_100",
    label: "Top 51–100",
    autoSort: "award_50best",
    match: (h) => {
      const r = getW50BestRank(h);
      return r != null && r >= 51 && r <= 100;
    },
  },
  {
    id: "michelin",
    label: "🗝️ MICHELIN Keys (3→1)",
    autoSort: "award_michelin",
    match: (h) => getMichelinKeyCount(h) != null,
  },
  {
    id: "michelin_3",
    label: "🗝️ 3 MICHELIN Keys",
    autoSort: "award_michelin",
    match: (h) => getMichelinKeyCount(h) === 3,
  },
  {
    id: "michelin_2",
    label: "🗝️ 2 MICHELIN Keys",
    autoSort: "award_michelin",
    match: (h) => getMichelinKeyCount(h) === 2,
  },
  {
    id: "michelin_1",
    label: "🗝️ 1 MICHELIN Key",
    autoSort: "award_michelin",
    match: (h) => getMichelinKeyCount(h) === 1,
  },
  {
    id: "forbes",
    label: "⭐ Forbes Star-Rated",
    autoSort: "award_forbes",
    match: (h) => getForbesRank(h) != null,
  },
  {
    id: "adults",
    label: "🥂 Adults-Only",
    match: (h) => getGuestProfile(h).isAdultsOnly,
  },
  {
    id: "family",
    label: "👨‍👩‍👧 Family & Kids",
    match: (h) => getGuestProfile(h).isFamilyFriendly,
  },
  {
    id: "preferred",
    label: "✨ Preferred Partner",
    match: (h) => getPartnerPrograms(h).hasPreferredPerks,
  },
  {
    id: "points",
    label: "Points Brands",
    match: (h) => getPartnerPrograms(h).isPointsEligible || POINTS_BRAND_RE.test(`${h.brand || ""} ${h.name || ""}`),
  },
  {
    id: "video",
    label: "Video Reviews",
    match: (h) => Boolean(h.videoId || (h.youtubeReviews && h.youtubeReviews.length > 0)),
  },
  {
    id: "beach",
    label: "House Reef / Beach",
    match: (h) => Boolean((h.keyFacts && h.keyFacts.beachOrReef) || h.region === "Maldives"),
  },
];

function applyFeatureSelection(featureId) {
  const normalized = featureId === "50best" ? "50best_100" : featureId || "all";
  state.feature = normalized;
  const meta = VERIFIED_FEATURES.find((f) => f.id === normalized);
  const sortEl = qs("#consensusSort");
  if (meta && meta.autoSort) {
    state.sortBy = meta.autoSort;
    state.tableSortKey = null;
    if (sortEl) sortEl.value = meta.autoSort;
  } else if (
    normalized === "all" &&
    (state.sortBy === "award_50best" || state.sortBy === "award_michelin" || state.sortBy === "award_forbes")
  ) {
    state.sortBy = "visited";
    if (sortEl) sortEl.value = "visited";
  }
}

function getMichelinKeyCount(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/michelin/i.test(txt)) {
      const m = String(a.label || "").match(/([123])\s*michelin\s*key/i);
      const val = m ? Number(m[1]) : 1;
      if (best == null || val > best) best = val;
    }
  }
  return best;
}

function getW50BestRank(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/50\s*best/i.test(txt)) {
      const m = String(a.label || "").match(/(?:No\.?|#)\s*(\d{1,3})/i);
      const val = m ? Number(m[1]) : 999;
      if (best == null || val < best) best = val;
    }
  }
  return best;
}

function getForbesRank(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/forbes/i.test(txt)) {
      let val = 1;
      if (/five[- ]star/i.test(txt)) val = 5;
      else if (/four[- ]star/i.test(txt)) val = 4;
      else if (/recommended/i.test(txt)) val = 3;
      if (best == null || val > best) best = val;
    }
  }
  return best;
}

const state = {
  hotels: [],
  visitedCount: 0,
  worldCount: 0,
  scope: "all", // "all" | "visited" | "world" | "saved"
  region: "All",
  feature: "all",
  style: "all",
  month: 0, // 0 = All Months, 1..12 = Jan..Dec
  priceTier: "all",
  brandFilter: "",
  sharedSavedIds: null, // populated when opened via ?saved=slug1,slug2
  lastFilteredList: [],
  verdict: "All",
  sortBy: "visited",
  viewMode: "cards", // "cards" | "table"
  tableSortKey: null, // clickable column header sort
  tableSortDir: "desc",
  search: "",
  searchA: "",
  searchB: "",
  searchC: "",
  threeWay: false,
  checkin: "",
  checkout: "",
  adults: 2,
  liveRates: {},
  visibleLimit: PAGE_SIZE,
  idA: "taaktana-labuan-bajo",
  idB: "st-regis-bali",
  idC: "w-maldives",
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
    if (state.style && state.style !== "all") url.searchParams.set("style", state.style);
    else url.searchParams.delete("style");
    if (state.month && state.month >= 1 && state.month <= 12) url.searchParams.set("month", String(state.month));
    else url.searchParams.delete("month");
    if (state.brandFilter) url.searchParams.set("brand", state.brandFilter);
    else url.searchParams.delete("brand");
    if (includeCompare && state.idA && state.idB) {
      url.searchParams.set("a", state.idA);
      url.searchParams.set("b", state.idB);
      if (state.threeWay && state.idC) url.searchParams.set("c", state.idC);
      else url.searchParams.delete("c");
    }
    window.history.replaceState({}, "", url.toString());
  } catch (_) {}
}

function resolveThumb(thumb) {
  if (!thumb) return "../assets/placeholders/default-stayodds.webp?v=169";
  if (/^https?:\/\//i.test(thumb)) return thumb;
  const rel = thumb.startsWith("../") || thumb.startsWith("/") ? thumb : `../${thumb}`;
  return rel.includes("?") ? rel : `${rel}?v=169`;
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

const SELECTOR_SIDES = {
  A: {
    sel: "#compareSelectA",
    clear: "#compareClearA",
    meta: "#compareMetaA",
    empty: "#compareEmptyA",
    searchKey: "searchA",
    idKey: "idA",
  },
  B: {
    sel: "#compareSelectB",
    clear: "#compareClearB",
    meta: "#compareMetaB",
    empty: "#compareEmptyB",
    searchKey: "searchB",
    idKey: "idB",
  },
  C: {
    sel: "#compareSelectC",
    clear: "#compareClearC",
    meta: "#compareMetaC",
    empty: "#compareEmptyC",
    searchKey: "searchC",
    idKey: "idC",
  },
};

function populateSingleSelector(side) {
  const cfg = SELECTOR_SIDES[side];
  if (!cfg) return;
  const sel = qs(cfg.sel);
  const clearBtn = qs(cfg.clear);
  const metaEl = qs(cfg.meta);
  const emptyEl = qs(cfg.empty);
  if (!sel) return;

  const query = state[cfg.searchKey] || "";
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

  const currentId = state[cfg.idKey];
  if (filtered.some((h) => h.id === currentId)) {
    sel.value = currentId;
  } else {
    const nextId = filtered[0].id;
    sel.value = nextId;
    state[cfg.idKey] = nextId;
  }
}

function populateH2HSelectors() {
  if (!state.hotels.some((h) => h.id === state.idA)) {
    const visited = state.hotels.filter(isVisitedProperty);
    if (visited.length) state.idA = visited[0].id;
    else if (state.hotels.length) state.idA = state.hotels[0].id;
  }
  if (!state.hotels.some((h) => h.id === state.idB)) {
    const fallbackB = state.hotels.find((h) => h.id !== state.idA);
    if (fallbackB) state.idB = fallbackB.id;
  }
  if (!state.hotels.some((h) => h.id === state.idC) || state.idC === state.idA || state.idC === state.idB) {
    const visitedC = state.hotels.find((h) => isVisitedProperty(h) && h.id !== state.idA && h.id !== state.idB);
    const anyC = state.hotels.find((h) => h.id !== state.idA && h.id !== state.idB);
    if (visitedC) state.idC = visitedC.id;
    else if (anyC) state.idC = anyC.id;
  }
  populateSingleSelector("A");
  populateSingleSelector("B");
  populateSingleSelector("C");
}

function syncThreeWayUi() {
  const wrap = qs("#h2hSelectorsWrap");
  const out = qs("#h2hOutput");
  const vs2 = qs("#compareVs2");
  const colC = qs("#compareColC");
  const toggleBtn = qs("#toggleThreeWayBtn");
  const shareBtn = qs("#shareVsCardBtn");
  const copyBtn = qs("#copyVsLinkBtn");

  if (wrap) wrap.classList.toggle("is-three-way", state.threeWay);
  if (out) out.classList.toggle("is-three-way", state.threeWay);
  if (vs2) vs2.hidden = !state.threeWay;
  if (colC) colC.hidden = !state.threeWay;

  if (toggleBtn) {
    toggleBtn.setAttribute("aria-pressed", String(state.threeWay));
    toggleBtn.classList.toggle("is-active", state.threeWay);
    toggleBtn.textContent = state.threeWay ? "− Back to 2 Hotels" : "+ Add 3rd Hotel";
  }
  if (shareBtn) {
    shareBtn.innerHTML = state.threeWay ? "&#x1F4F8; Share 3-Hotel Card" : "&#x1F4F8; Share VS Card";
  }
  if (copyBtn && !copyBtn.classList.contains("is-copied")) {
    copyBtn.innerHTML = state.threeWay ? "&#128279; Copy 3-Hotel Link" : "&#128279; Copy VS Link";
  }
}

function renderH2HCard(h, allCompared) {
  const o = getOdds(h);
  const otherOdds = allCompared.filter((x) => x !== h).map((x) => ({ h: x, o: getOdds(x), s: x.scores || {} }));
  const s = h.scores || {};
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
  const st = getPropertyStatusMeta(h);

  const metricRow = (label, a, otherVals, suffix = "", missingText = "—", customDisplay = null) => {
    const aMissing = a == null || Number.isNaN(Number(a));
    const validOthers = (otherVals || []).filter((v) => v != null && !Number.isNaN(Number(v))).map(Number);
    const wins = !aMissing && validOthers.length > 0 && Number(a) > Math.max(...validOthers);
    const display = aMissing ? missingText : customDisplay != null ? customDisplay : `${a}${suffix}`;
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
      : o.unverifiedEditorial && o.unverifiedEditorial.length > 0
      ? `Score awarded — unverified (${o.unverifiedEditorial[0].sourceName})`
      : (o.editorialRatings.length + o.youtubeReviews.length) > 0
      ? `${o.editorialRatings.length + o.youtubeReviews.length} review${o.editorialRatings.length + o.youtubeReviews.length > 1 ? "s" : ""} (no score)`
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

  const anyFirstHandCompared = allCompared.some((x) => getOdds(x).firstHand);
  const priceInfo = getPriceDisplay(h);
  const liveRate = h.nuiteeHotelId ? state.liveRates[h.nuiteeHotelId] : null;
  const datedBookingUrl = buildDatedBookingUrl(h.bookingUrl, state.checkin, state.checkout, state.adults);
  const trackCls = o.scoreTrack === "verified" ? "is-verified-track" : "is-market-track";
  const deltaToneCls =
    o.founderVsMarketDelta != null
      ? o.founderVsMarketDelta < -4
        ? "is-neg"
        : o.founderVsMarketDelta > 4
        ? "is-pos"
        : ""
      : "";

  // Zero-API-waste relative indicative price comparison across compared hotels
  const effectiveGbp = (item) => {
    const lr = item.nuiteeHotelId ? state.liveRates[item.nuiteeHotelId] : null;
    if (lr && Number(lr.perNight) > 0) return Math.round(Number(lr.perNight));
    const pi = getPriceDisplay(item);
    return pi.numericGbp != null ? Math.round(pi.numericGbp) : null;
  };
  const myGbp = effectiveGbp(h);
  const otherGbps = allCompared.filter((x) => x !== h).map(effectiveGbp).filter((v) => v != null);
  const allGbps = [myGbp, ...otherGbps].filter((v) => v != null);
  const minGbp = allGbps.length >= 2 ? Math.min(...allGbps) : null;
  const isLowestPrice = myGbp != null && minGbp != null && otherGbps.length > 0 && myGbp < Math.min(...otherGbps);
  let priceDeltaNote = "";
  if (myGbp != null && minGbp != null && otherGbps.length > 0) {
    const diffVsMin = myGbp - minGbp;
    if (isLowestPrice) {
      const nextMin = Math.min(...otherGbps);
      priceDeltaNote = `£${(nextMin - myGbp).toLocaleString("en-GB")}/nt less`;
    } else if (diffVsMin > 0) {
      priceDeltaNote = `+£${diffVsMin.toLocaleString("en-GB")}/nt vs lowest`;
    }
  }
  const priceRowDisplay = liveRate
    ? `£${Number(liveRate.perNight).toLocaleString("en-GB")}/nt (live)`
    : priceInfo.label
    ? `${priceInfo.label}${priceDeltaNote ? ` · ${priceDeltaNote}` : ""}`
    : "Check Dates";

  const partner = getPartnerPrograms(h);
  const profile = getGuestProfile(h);
  const climate = getBestMonthsMeta(h);
  const roomTip = getVerifiedRoomTip(h);

  const personalPillarRowsHtml = anyFirstHandCompared
    ? `
        ${metricRow(
          "Value",
          o.firstHand ? formatPersonalScore(s.value) : null,
          otherOdds.map((x) => (x.o.firstHand ? formatPersonalScore(x.s.value) : null)),
          " / 5",
          unratedLabel
        )}
        ${metricRow(
          "Room Quality",
          o.firstHand ? formatPersonalScore(s.rooms) : null,
          otherOdds.map((x) => (x.o.firstHand ? formatPersonalScore(x.s.rooms) : null)),
          " / 5",
          unratedLabel
        )}
        ${metricRow(
          "Vibe",
          o.firstHand ? formatPersonalScore(s.grounds) : null,
          otherOdds.map((x) => (x.o.firstHand ? formatPersonalScore(x.s.grounds) : null)),
          " / 5",
          unratedLabel
        )}
        ${metricRow(
          "Food",
          o.firstHand ? formatPersonalScore(s.food) : null,
          otherOdds.map((x) => (x.o.firstHand ? formatPersonalScore(x.s.food) : null)),
          " / 5",
          unratedLabel
        )}
        ${metricRow(
          "Service",
          o.firstHand ? formatPersonalScore(s.service) : null,
          otherOdds.map((x) => (x.o.firstHand ? formatPersonalScore(x.s.service) : null)),
          " / 5",
          unratedLabel
        )}
      `
    : "";

  const tagsHtml = [
    partner.preferredProgram ? `<span class="tag tag-accent" title="${escapeHtml(partner.perksNote)}">✨ ${escapeHtml(partner.preferredProgram)}</span>` : "",
    partner.pointsProgram ? `<span class="tag tag-teal">★ ${escapeHtml(partner.pointsProgram)}</span>` : "",
    profile.isAdultsOnly ? `<span class="tag tag-slate">🥂 Adults-Only</span>` : profile.isFamilyFriendly ? `<span class="tag tag-slate">👨‍👩‍👧 Family / Kids</span>` : "",
  ].filter(Boolean).join("");

  const roomTipHtml = roomTip
    ? `<div class="h2h-room-tip-box"><strong>🛏️ First-Hand Room / Booking Tip:</strong> ${escapeHtml(roomTip)}</div>`
    : "";

  return `
    <article class="h2h-card ${trackCls}" data-resort-name="${escapeHtml(h.name)}">
      <div class="h2h-card-head">
        <img src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" decoding="async" />
        <div>
          <span class="tag ${o.scoreTrack === "verified" ? "tag-accent" : "tag-slate"}">${escapeHtml(o.scoreTrackLabel)}</span>
          <h3><a class="consensus-title-link" href="${getSeoHref(h)}">${escapeHtml(h.name)}</a></h3>
          <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)}${h.brand && !/^independent$/i.test(h.brand) ? ` &bull; ${escapeHtml(h.brand)}` : ""}</div>
        </div>
      </div>

      <div class="h2h-odds-strip">
        <div class="odds-big">
          <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : o.officialAwards.length ? "Awarded" : "Open"}</strong>
          <span>${escapeHtml(o.scoreTrack === "verified" ? "Verified StayOdds" : `Market Odds (${o.marketSourceCount} src)`)}</span>
        </div>
        <div class="index-big">
          <strong>${escapeHtml(o.founderVsMarketDelta != null ? `${o.founderVsMarketDelta > 0 ? "+" : ""}${o.founderVsMarketDelta} pts` : o.opinionGap.deltaLabel)}</strong>
          <span>${o.firstHand ? "Founder vs Market" : "Opinion Gap"}</span>
        </div>
      </div>

      ${
        liveRate
          ? `<div class="h2h-live-rate-pill">&#128176; Live: £${Number(liveRate.perNight).toLocaleString("en-GB")}/nt (£${Number(liveRate.total).toLocaleString("en-GB")} for ${liveRate.nights}nt${liveRate.refundable ? " · Refundable" : ""})</div>`
          : priceInfo.label
          ? `<div style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:6px;align-items:center;"><span class="price-chip-indicative">${escapeHtml(priceInfo.label)}${priceInfo.isIndicative ? " (indicative)" : ""}</span>${
              priceDeltaNote ? `<span class="tag ${isLowestPrice ? "tag-teal" : "tag-slate"}" style="font-size:11px;">${escapeHtml(priceDeltaNote)}</span>` : ""
            }${
              o.founderVsMarketLabel
                ? `<span class="founder-delta-pill ${deltaToneCls}">${escapeHtml(o.founderVsMarketLabel)}</span>`
                : ""
            }</div>`
          : o.founderVsMarketLabel
          ? `<div style="margin-bottom:10px;"><span class="founder-delta-pill ${deltaToneCls}">${escapeHtml(o.founderVsMarketLabel)}</span></div>`
          : ""
      }

      ${statusHtml}

      <div class="h2h-metrics-list">
        ${metricRow(
          "My First-Hand Stay",
          o.ours100,
          otherOdds.map((x) => x.o.ours100),
          "",
          unratedLabel,
          o.personalScoreLabel || unratedLabel
        )}
        ${metricRow(
          "Market Odds Baseline",
          o.marketOdds,
          otherOdds.map((x) => x.o.marketOdds),
          "%",
          "—",
          o.marketOdds != null ? `${o.marketOdds}%` : "—"
        )}
        ${metricRow(
          "Critics / Other Reviews",
          o.critic100,
          otherOdds.map((x) => x.o.critic100),
          "",
          criticDisplay || "— (None listed)",
          criticDisplay || "— (None listed)"
        )}
        ${metricRow(
          "Verified Guests",
          o.guest100,
          otherOdds.map((x) => x.o.guest100),
          "",
          "Open Breakdown",
          guestDisplay || "Open Breakdown"
        )}
        <div class="h2h-metric ${isLowestPrice ? "is-best" : ""}">
          <span>Indicative Nightly Rate</span>
          <strong>${escapeHtml(priceRowDisplay)}${isLowestPrice ? " ★" : ""}</strong>
        </div>
        <div class="h2h-metric" title="${escapeHtml(climate.reason)}">
          <span>Best Dry Months</span>
          <strong>&#9728; ${escapeHtml(climate.label)}</strong>
        </div>
        <div class="h2h-metric">
          <span>Official Awards</span>
          <strong style="text-align:right;font-size:12.5px;">${awardsHtml}</strong>
        </div>
        ${personalPillarRowsHtml}
      </div>

      ${roomTipHtml}

      <p class="h2h-diff"><strong>${escapeHtml(o.opinionGap.title)}:</strong> ${escapeHtml(o.opinionGap.headline)}${
        h.whereWeDiffer && h.whereWeDiffer !== roomTip ? `<br><span style="color:#334155;"><strong>My Take:</strong> ${escapeHtml(h.whereWeDiffer)}</span>` : ""
      }</p>

      ${tagsHtml ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;">${tagsHtml}</div>` : ""}

      <div class="scorecard-actions">
        <a class="btn btn-primary" href="${getSeoHref(h)}">Full Breakdown &rarr;</a>
        ${
          reviewHref
            ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${h.coverageType === "Short Tour" ? "Watch Short" : "Watch Review"}</a>`
            : ""
        }
        <button type="button" class="btn btn-outline shortlist-btn" data-shortlist-id="${escapeHtml(h.id)}" data-shortlist-compact="1" data-resort-name="${escapeHtml(h.name)}" aria-pressed="false">&#9825; Save</button>
        <a class="btn btn-outline" href="${escapeHtml(datedBookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
      </div>
      <div style="margin-top:8px;">
        <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
      </div>
    </article>
  `;
}

function renderH2H() {
  syncThreeWayUi();
  const out = qs("#h2hOutput");
  if (!out) return;
  const a = state.hotels.find((h) => h.id === state.idA) || state.hotels[0];
  const b = state.hotels.find((h) => h.id === state.idB) || state.hotels[1];
  if (!a || !b) return;
  const compared = [a, b];
  if (state.threeWay) {
    const c =
      state.hotels.find((h) => h.id === state.idC) ||
      state.hotels.find((h) => h.id !== a.id && h.id !== b.id);
    if (c) compared.push(c);
  }
  out.innerHTML = compared.map((h) => renderH2HCard(h, compared)).join("");
  window.stayOddsShortlist?.syncButtons?.();
}

function getActiveShortlistIds() {
  if (Array.isArray(state.sharedSavedIds) && state.sharedSavedIds.length > 0) {
    return state.sharedSavedIds;
  }
  return getShortlistIds();
}

function getScopedHotels() {
  let base = state.hotels;
  if (state.scope === "visited") base = base.filter(isVisitedProperty);
  else if (state.scope === "world") base = base.filter((h) => !isVisitedProperty(h));
  else if (state.scope === "saved") {
    const savedSet = new Set(getActiveShortlistIds());
    base = base.filter((h) => savedSet.has(h.id));
  }
  if (state.brandFilter) {
    base = base.filter((h) => matchesBrandCategory(h, state.brandFilter));
  }
  return base;
}

function renderActiveBrandBanner() {
  const el = qs("#activeBrandBanner");
  if (!el) return;
  if (!state.brandFilter) {
    el.style.display = "none";
    return;
  }
  const cnt = state.hotels.filter((h) => matchesBrandCategory(h, state.brandFilter)).length;
  el.style.display = "flex";
  el.innerHTML = `
    <span><strong>Brand Filter Active:</strong> Showing all <strong>${cnt}</strong> verified <strong>${escapeHtml(state.brandFilter)}</strong> properties.</span>
    <div style="display:flex;gap:8px;">
      <a class="btn btn-outline" href="../brands/" style="font-size:12px;padding:5px 10px;">&larr; Brand Leaderboard</a>
      <button type="button" class="btn btn-primary" id="clearBrandFilterBtn" style="font-size:12px;padding:5px 10px;">&times; Show All Brands</button>
    </div>
  `;
  qs("#clearBrandFilterBtn")?.addEventListener("click", () => {
    state.brandFilter = "";
    state.visibleLimit = PAGE_SIZE;
    syncUrlParams();
    renderActiveBrandBanner();
    renderScopeTabs();
    renderRegionPills();
    renderFeaturePills();
    renderStylePills();
    renderMonthPills();
    renderLeaderboard();
  });
}

function renderShortlistUtilityBar() {
  const bar = qs("#shortlistUtilityBar");
  const txt = qs("#shortlistUtilityText");
  const importBtn = qs("#importSharedShortlistBtn");
  if (!bar) return;

  const isSavedView = state.scope === "saved";
  const activeIds = getActiveShortlistIds();
  if (!isSavedView || !activeIds.length) {
    bar.style.display = "none";
    return;
  }
  bar.style.display = "flex";
  const isShared = Array.isArray(state.sharedSavedIds) && state.sharedSavedIds.length > 0;
  if (txt) {
    txt.innerHTML = isShared
      ? `<strong>Shared Shortlist (${activeIds.length} hotels):</strong> Someone shared this verified StayOdds shortlist with you. Save it to your browser or export to CSV.`
      : `<strong>Your Saved Shortlist (${activeIds.length} hotel${activeIds.length === 1 ? "" : "s"}):</strong> Share a direct link with a partner or travel advisor, or download as a CSV spreadsheet.`;
  }
  if (importBtn) {
    importBtn.style.display = isShared ? "" : "none";
  }
}

function renderScopeTabs() {
  const container = qs("#stayOddsScopeTabs");
  if (!container) return;
  const savedIds = getActiveShortlistIds();
  const savedCount = state.hotels.filter((h) => savedIds.includes(h.id)).length;
  const isShared = Array.isArray(state.sharedSavedIds) && state.sharedSavedIds.length > 0;
  const tabs = [
    { id: "all", label: `All Luxury Properties (${state.hotels.length})` },
    { id: "visited", label: `First-Hand Verified & Shorts (${state.visitedCount})` },
    { id: "world", label: `Global Directory (${state.worldCount})` },
    { id: "saved", label: isShared ? `♥ Shared Shortlist (${savedCount})` : `♥ Saved (${savedCount})` },
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
      if (state.scope !== "saved") state.sharedSavedIds = null;
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
      renderShortlistUtilityBar();
      renderRegionPills();
      renderFeaturePills();
      renderStylePills();
      renderMonthPills();
      renderLeaderboard();
    });
  });
}

function getAwardsCompositeRank(h) {
  const m = getMichelinKeyCount(h);
  const w50 = getW50BestRank(h);
  const f = getForbesRank(h);
  if (m == null && w50 == null && f == null && !(h.officialAwards && h.officialAwards.length)) return null;
  let score = 0;
  if (m != null) score += m * 300;
  if (w50 != null) score += w50 <= 50 ? 250 + (51 - w50) * 3 : 180;
  if (f != null) score += f === 5 ? 140 : f === 4 ? 80 : 40;
  score += (h.officialAwards || []).length * 10;
  return score;
}

function renderActiveFiltersAndDrawerBadge() {
  const badge = qs("#compareFilterCountBadge");
  const strip = qs("#compareActiveFiltersStrip");
  const chips = [];
  if (state.verdict !== "All") {
    chips.push({ key: "verdict", label: `Status: ${state.verdict}` });
  }
  if (state.priceTier !== "all") {
    const pLabels = {
      under500: "Under £500/nt",
      "500to1000": "£500–£1,000/nt",
      "1000to1800": "£1,000–£1,800/nt",
      "1800plus": "£1,800+/nt",
    };
    chips.push({ key: "priceTier", label: `Budget: ${pLabels[state.priceTier] || state.priceTier}` });
  }
  if (state.feature !== "all") {
    const fObj = VERIFIED_FEATURES.find((f) => f.id === state.feature);
    chips.push({ key: "feature", label: fObj ? fObj.label : state.feature });
  }
  if (state.style !== "all") {
    const sObj = TRAVEL_STYLES.find((s) => s.id === state.style);
    chips.push({ key: "style", label: sObj ? `${sObj.icon ? sObj.icon + " " : ""}${sObj.label}` : state.style });
  }
  if (state.month >= 1 && state.month <= 12) {
    chips.push({ key: "month", label: `Best in ${MONTH_LABELS[state.month - 1]}` });
  }

  if (badge) {
    badge.textContent = String(chips.length);
    badge.hidden = chips.length === 0;
  }
  if (strip) {
    if (!chips.length) {
      strip.hidden = true;
      strip.innerHTML = "";
    } else {
      strip.hidden = false;
      strip.innerHTML =
        chips
          .map(
            (c) =>
              `<button type="button" class="active-filter-chip" data-clear-filter="${escapeHtml(c.key)}">${escapeHtml(c.label)} &times;</button>`
          )
          .join("") +
        `<button type="button" class="btn-link-clear" id="compareStripClearAll">Clear all</button>`;

      strip.querySelectorAll("[data-clear-filter]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const k = btn.dataset.clearFilter;
          if (k === "verdict") {
            state.verdict = "All";
            const el = qs("#verdictFilter");
            if (el) el.value = "All";
          } else if (k === "priceTier") {
            state.priceTier = "all";
            const el = qs("#priceTierFilter");
            if (el) el.value = "all";
          } else if (k === "feature") {
            applyFeatureSelection("all");
          } else if (k === "style") {
            state.style = "all";
          } else if (k === "month") {
            state.month = 0;
          }
          state.visibleLimit = PAGE_SIZE;
          syncUrlParams();
          renderFeaturePills();
          renderStylePills();
          renderMonthPills();
          renderLeaderboard();
        });
      });
      strip.querySelector("#compareStripClearAll")?.addEventListener("click", () => {
        qs("#compareClearDrawerFiltersBtn")?.click();
      });
    }
  }
  syncQuickPresetsUI();
}

function syncQuickPresetsUI() {
  document.querySelectorAll("[data-quick-preset]").forEach((btn) => {
    const p = btn.dataset.quickPreset;
    let isActive = false;
    if (p === "50best_50" || p === "50best_100" || p === "michelin" || p === "michelin_3" || p === "adults") {
      isActive = state.feature === p;
    } else if (p === "style_island") {
      isActive = state.style === "island";
    } else if (p === "budget_under500") {
      isActive = state.priceTier === "under500";
    }
    btn.classList.toggle("active", isActive);
    btn.setAttribute("aria-pressed", String(isActive));
  });
}

function renderRegionPills() {
  const container = qs("#consensusRegionPills");
  if (!container) return;
  const scoped = getScopedHotels();
  const present = new Set(scoped.map((h) => h.region).filter(Boolean));
  const ordered = MACRO_REGIONS.filter((r) => present.has(r));
  for (const r of present) {
    if (!ordered.includes(r)) ordered.push(r);
  }
  const regions = ["All", ...ordered];
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
      renderStylePills();
      renderMonthPills();
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
      applyFeatureSelection(btn.dataset.feature || "all");
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `feature:${state.feature}`);
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderFeaturePills();
      renderStylePills();
      renderMonthPills();
      renderLeaderboard();
    });
  });
}

function renderStylePills() {
  const container = qs("#travelStylePills");
  if (!container) return;
  const baseList = getScopedHotels().filter((h) => state.region === "All" || h.region === state.region);
  container.innerHTML = TRAVEL_STYLES.map((s) => {
    const cnt = s.id === "all" ? baseList.length : baseList.filter(s.match).length;
    if (s.id !== "all" && cnt === 0 && state.style !== s.id) return "";
    return `<button class="feature-pill style-pill ${state.style === s.id ? "active" : ""}" data-style="${escapeHtml(
      s.id
    )}" type="button">${s.icon ? `${s.icon} ` : ""}${escapeHtml(s.label)} (${cnt})</button>`;
  }).join("");

  container.querySelectorAll("[data-style]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.style = btn.dataset.style || "all";
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `style:${state.style}`);
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderStylePills();
      renderMonthPills();
      renderLeaderboard();
    });
  });
}

function renderMonthPills() {
  const container = qs("#bestMonthPills");
  if (!container) return;
  const baseList = getScopedHotels().filter((h) => state.region === "All" || h.region === state.region);
  const pills = [
    `<button class="feature-pill month-pill ${state.month === 0 ? "active" : ""}" data-month="0" type="button">All Months (${baseList.length})</button>`,
    ...MONTH_LABELS.map((lbl, idx) => {
      const m = idx + 1;
      const cnt = baseList.filter((h) => matchesBestMonth(h, m)).length;
      return `<button class="feature-pill month-pill ${state.month === m ? "active" : ""}" data-month="${m}" type="button">${lbl} (${cnt})</button>`;
    }),
  ];
  container.innerHTML = pills.join("");
  container.querySelectorAll("[data-month]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.month = Number(btn.dataset.month || 0);
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "filter", `month:${state.month}`);
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderMonthPills();
      renderLeaderboard();
    });
  });
}

function renderLeaderboard() {
  const container = qs("#consensusList");
  const tableWrap = qs("#consensusTableWrap");
  if (!container) return;

  renderActiveBrandBanner();
  renderShortlistUtilityBar();
  renderActiveFiltersAndDrawerBadge();

  const q = state.search.trim().toLowerCase();
  const activeFeature = VERIFIED_FEATURES.find((f) => f.id === state.feature) || VERIFIED_FEATURES[0];
  const list = getScopedHotels().filter((h) => {
    const o = getOdds(h);
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.verdict !== "All" && o.statusBadge !== state.verdict) return false;
    if (state.priceTier !== "all") {
      const pd = getPriceDisplay(h);
      if (!pd.tierBucket || pd.tierBucket !== state.priceTier) return false;
    }
    if (activeFeature.id !== "all" && !activeFeature.match(h)) return false;
    if (!matchesTravelStyle(h, state.style)) return false;
    if (state.month && !matchesBestMonth(h, state.month)) return false;
    if (!q) return true;
    const partner = getPartnerPrograms(h);
    const hay = [
      h.name,
      h.location,
      h.country,
      h.region,
      h.brand,
      partner.brand,
      partner.preferredProgram,
      partner.pointsProgram,
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

  const getDisagreementPtsNullable = (o) => {
    const absDelta = o.opinionGap && o.opinionGap.delta100 != null ? Math.abs(Number(o.opinionGap.delta100)) : null;
    const spread = o.spread100 != null ? Number(o.spread100) : null;
    if (absDelta == null && spread == null) return null;
    return Math.max(absDelta ?? -1, spread ?? -1);
  };

  const cmpNullableNum = (va, vb, dir) => {
    const aNull = va == null || Number.isNaN(va);
    const bNull = vb == null || Number.isNaN(vb);
    if (aNull && bNull) return 0;
    if (aNull) return 1; // Always keep missing/unscored rows at the bottom
    if (bNull) return -1;
    return dir === "asc" ? va - vb : vb - va;
  };

  list.sort((a, b) => {
    const oa = getOdds(a);
    const ob = getOdds(b);
    const rank = (o) => (o.firstHand ? 2 : o.visited ? 1 : 0);

    if (state.tableSortKey) {
      const k = state.tableSortKey;
      const d = state.tableSortDir;
      let diff = 0;
      if (k === "name") {
        diff = d === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
      } else if (k === "location") {
        const la = `${a.location || ""}, ${a.country || ""}`;
        const lb = `${b.location || ""}, ${b.country || ""}`;
        diff = d === "asc" ? la.localeCompare(lb) : lb.localeCompare(la);
      } else if (k === "odds") {
        diff = cmpNullableNum(oa.greatStayOdds, ob.greatStayOdds, d);
      } else if (k === "overall") {
        diff = cmpNullableNum(
          oa.firstHand && a.overall != null ? Number(a.overall) : null,
          ob.firstHand && b.overall != null ? Number(b.overall) : null,
          d
        );
      } else if (k === "critic") {
        diff = cmpNullableNum(oa.critic100, ob.critic100, d);
      } else if (k === "guest") {
        diff = cmpNullableNum(oa.guest100, ob.guest100, d);
      } else if (k === "awards") {
        diff = cmpNullableNum(getAwardsCompositeRank(a), getAwardsCompositeRank(b), d);
      } else if (k === "price") {
        diff = cmpNullableNum(getPriceDisplay(a).numericGbp, getPriceDisplay(b).numericGbp, d);
      }
      if (diff !== 0) return diff;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }

    if (state.sortBy.startsWith("pillar_")) {
      const pKey = state.sortBy.replace("pillar_", "");
      const va = oa.firstHand && a.scores && a.scores[pKey] != null ? Number(a.scores[pKey]) : null;
      const vb = ob.firstHand && b.scores && b.scores[pKey] != null ? Number(b.scores[pKey]) : null;
      const diff = cmpNullableNum(va, vb, "desc");
      if (diff !== 0) return diff;
      const totDiff = cmpNullableNum(
        oa.firstHand && a.overall != null ? Number(a.overall) : null,
        ob.firstHand && b.overall != null ? Number(b.overall) : null,
        "desc"
      );
      if (totDiff !== 0) return totDiff;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }

    if (state.sortBy === "name") return a.name.localeCompare(b.name);
    if (state.sortBy === "award_50best") {
      const diff = cmpNullableNum(getW50BestRank(a), getW50BestRank(b), "asc");
      if (diff !== 0) return diff;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "award_michelin") {
      const diff = cmpNullableNum(getMichelinKeyCount(a), getMichelinKeyCount(b), "desc");
      if (diff !== 0) return diff;
      if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "award_forbes") {
      const diff = cmpNullableNum(getForbesRank(a), getForbesRank(b), "desc");
      if (diff !== 0) return diff;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "odds") {
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "price_asc") {
      const diff = cmpNullableNum(getPriceDisplay(a).numericGbp, getPriceDisplay(b).numericGbp, "asc");
      if (diff !== 0) return diff;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "gap") {
      const ga = getDisagreementPtsNullable(oa) ?? -1;
      const gb = getDisagreementPtsNullable(ob) ?? -1;
      if (gb !== ga) return gb - ga;
      if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "reviews") {
      const ra = oa.verifiedGuest && oa.verifiedGuest.reviewCount != null ? Number(oa.verifiedGuest.reviewCount) : -1;
      const rb = ob.verifiedGuest && ob.verifiedGuest.reviewCount != null ? Number(ob.verifiedGuest.reviewCount) : -1;
      if (rb !== ra) return rb - ra;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
    return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
  });

  state.lastFilteredList = list;

  if (!list.length) {
    container.style.display = "";
    if (tableWrap) tableWrap.style.display = "none";
    const emptyMsg =
      state.scope === "saved" && getShortlistIds().length === 0
        ? `Your Shortlist is empty — tap "♡ Save" on any hotel card or breakdown page to build your personal comparison list (saved right in your browser, no login needed).`
        : `No resorts matched your filters. Try switching to "All Luxury Properties" or clearing your search/drawer filters.`;
    container.innerHTML = `<div class="empty-state">${escapeHtml(emptyMsg)}</div>`;
    return;
  }

  const visibleList = list.slice(0, state.visibleLimit);
  const remaining = list.length - visibleList.length;

  const pagerHtml =
    remaining > 0
      ? `<div class="load-more-bar" style="display:flex;gap:12px;justify-content:center;align-items:center;padding:20px 0 8px;flex-wrap:wrap;">
          <button class="btn btn-primary" id="loadMoreHotelsBtn" type="button">Show ${Math.min(PAGE_SIZE, remaining)} More (${visibleList.length} of ${list.length} shown)</button>
          <button class="btn btn-outline" id="showAllHotelsBtn" type="button">Show All ${list.length}</button>
        </div>`
      : "";

  const activeRoot = state.viewMode === "table" && tableWrap ? tableWrap : container;

  if (state.viewMode === "table" && tableWrap) {
    container.style.display = "none";
    tableWrap.style.display = "";

    const cols = [
      { key: "name", label: "Hotel", defaultDir: "asc" },
      { key: "location", label: "Destination", defaultDir: "asc" },
      { key: "odds", label: "StayOdds", defaultDir: "desc" },
      { key: "overall", label: "My Stay", defaultDir: "desc" },
      { key: "critic", label: "Critics", defaultDir: "desc" },
      { key: "guest", label: "Guests", defaultDir: "desc" },
      { key: "awards", label: "Awards", defaultDir: "desc" },
      { key: "price", label: "Indicative Rate", defaultDir: "asc" },
    ];

    const thHtml = cols
      .map((c) => {
        const isActive = state.tableSortKey === c.key;
        const arrow = isActive ? (state.tableSortDir === "asc" ? "▲" : "▼") : "⇅";
        const ariaSort = isActive ? (state.tableSortDir === "asc" ? "ascending" : "descending") : "none";
        return `<th class="is-sortable ${isActive ? "is-sorted" : ""}" data-sort-col="${c.key}" data-default-dir="${c.defaultDir}" aria-sort="${ariaSort}"><button type="button" class="sort-th-btn">${escapeHtml(c.label)} <span class="sort-arrow">${arrow}</span></button></th>`;
      })
      .join("");

    tableWrap.innerHTML = `
      <table class="comparison-table">
        <thead>
          <tr>
            ${thHtml}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${visibleList
            .map((h) => {
              const o = getOdds(h);
              const mKeys = getMichelinKeyCount(h);
              const w50Rank = getW50BestRank(h);
              const forbesRank = getForbesRank(h);
              const priceInfo = getPriceDisplay(h);
              const criticCell =
                o.critic100 != null
                  ? `<strong>${o.critic100}/100</strong><div class="table-sub">${escapeHtml(
                      o.scoredEditorial && o.scoredEditorial.length === 1
                        ? o.scoredEditorial[0].sourceName
                        : o.scoredEditorial && o.scoredEditorial.length > 1
                        ? `${o.scoredEditorial.length} critics`
                        : "Verified"
                    )}</div>`
                  : o.unverifiedEditorial && o.unverifiedEditorial.length > 0
                  ? `<span class="table-sub">Unverified</span>`
                  : "—";
              const awardPills = [
                mKeys != null ? `<span class="table-rank-pill is-key">${mKeys}K</span>` : "",
                w50Rank != null ? `<span class="table-rank-pill is-50">${w50Rank < 999 ? `#${w50Rank}` : "50B"}</span>` : "",
                forbesRank === 5
                  ? `<span class="table-rank-pill is-forbes">5★</span>`
                  : forbesRank === 4
                  ? `<span class="table-rank-pill is-forbes">4★</span>`
                  : "",
              ]
                .filter(Boolean)
                .join(" ");
              const oddsTrackSub =
                o.scoreTrack === "verified"
                  ? `Verified${o.founderVsMarketDelta != null ? ` (${o.founderVsMarketDelta > 0 ? "+" : ""}${o.founderVsMarketDelta})` : ""}`
                  : "Market Odds";

              return `
                <tr data-resort-name="${escapeHtml(h.name)}">
                  <td><strong><a href="${getSeoHref(h)}">${escapeHtml(h.name)}</a></strong><div class="table-sub">${escapeHtml(h.brand || "")}</div></td>
                  <td>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</td>
                  <td><strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : "Live"}</strong><div class="table-sub">${escapeHtml(oddsTrackSub)}</div></td>
                  <td>${o.personalScoreLabel ? `<strong>${escapeHtml(o.personalScoreLabel)}</strong>` : `<span class="table-sub">${escapeHtml(o.visited ? o.tierLabel : "—")}</span>`}</td>
                  <td>${criticCell}</td>
                  <td>${o.verifiedGuest ? `<strong>${o.verifiedGuest.rating.toFixed(1)}/${o.verifiedGuest.scale}</strong>` : `<span class="table-sub">Live</span>`}</td>
                  <td style="white-space:nowrap;">${awardPills || "—"}</td>
                  <td style="white-space:nowrap;">${priceInfo.label ? `<strong>${escapeHtml(priceInfo.label)}</strong>` : `<span class="table-sub">—</span>`}</td>
                  <td style="white-space:nowrap;">
                    <a class="btn btn-primary" style="padding:6px 10px;font-size:12px;" href="${getSeoHref(h)}">Open</a>
                    <button type="button" class="btn btn-outline" style="padding:6px 10px;font-size:12px;" data-compare-id="${escapeHtml(h.id)}">VS &uarr;</button>
                    <button type="button" class="btn btn-outline shortlist-btn" style="padding:6px 10px;font-size:12px;" data-shortlist-id="${escapeHtml(h.id)}" data-shortlist-compact="1" data-resort-name="${escapeHtml(h.name)}" aria-pressed="false">&#9825;</button>
                    <a class="btn btn-outline" style="padding:6px 10px;font-size:12px;" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
      ${pagerHtml}
    `;

    tableWrap.querySelectorAll("th[data-sort-col]").forEach((th) => {
      th.addEventListener("click", () => {
        const col = th.dataset.sortCol;
        const defDir = th.dataset.defaultDir || "desc";
        if (state.tableSortKey === col) {
          state.tableSortDir = state.tableSortDir === "asc" ? "desc" : "asc";
        } else {
          state.tableSortKey = col;
          state.tableSortDir = defDir;
        }
        state.visibleLimit = Math.max(state.visibleLimit, 50);
        if (typeof window.trackEvent === "function") {
          window.trackEvent("use_filter", "table_sort", `${col}:${state.tableSortDir}`);
        }
        renderLeaderboard();
      });
    });
  } else {
    container.style.display = "";
    if (tableWrap) tableWrap.style.display = "none";

    const cardsHtml = visibleList
      .map((h, i) => {
        const o = getOdds(h);
        const reviewHref = getReviewHref(h);
        const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
        const isShortOnly = h.coverageType === "Short Tour";
        const priceInfo = getPriceDisplay(h);
        const trackCls = o.scoreTrack === "verified" ? "is-verified-track" : "is-market-track";
        const deltaToneCls =
          o.founderVsMarketDelta != null
            ? o.founderVsMarketDelta < -4
              ? "is-neg"
              : o.founderVsMarketDelta > 4
              ? "is-pos"
              : ""
            : "";

        const keyFactChips = [
          ...o.keyFacts.slice(0, 3).map((kf) => `<span class="card-key-fact-chip"><strong>${escapeHtml(kf.label)}:</strong> ${escapeHtml(kf.value)}</span>`),
          ...o.redFlags.slice(0, 2).map((rf) => `<span class="tag tag-caution">⚠ ${escapeHtml(rf)}</span>`),
        ].join("");

        const criticBoxHtml =
          o.scoredEditorial.length === 1
            ? `<small>Critics (${o.primaryCritic.sourceName})</small>
               <strong><a href="${escapeHtml(o.primaryCritic.sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${escapeHtml(
                 o.primaryCritic.rawScore || `${o.critic100}/100`
               )} ↗</a></strong>`
            : o.scoredEditorial.length > 1
            ? `<small>${o.scoredEditorial.length} Published Critics</small>
               <strong>${o.critic100} / 100</strong>`
            : o.unverifiedEditorial && o.unverifiedEditorial.length > 0
            ? `<small>${escapeHtml(o.unverifiedEditorial[0].sourceName)}</small>
               <strong style="font-size:12px;"><a href="${escapeHtml(o.unverifiedEditorial[0].sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">Awarded ↗</a></strong>`
            : o.editorialRatings.length > 0
            ? `<small>Editorial Review</small>
               <strong style="font-size:13px;"><a href="${escapeHtml(o.editorialRatings[0].sourceUrl)}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:underline;">${escapeHtml(
                 o.editorialRatings[0].sourceName
               )} ↗</a></strong>`
            : `<small>Published Critics</small>
               <strong>—</strong>`;

        const editorialUrlSet = new Set(o.editorialRatings.map((e) => e.sourceUrl));
        const sourceChips = [
          ...o.officialAwards.map(
            (a) =>
              `<a class="source-chip" href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">🏆 ${escapeHtml(
                a.label
              )} ↗</a>`
          ),
          ...o.editorialRatings.map((e) => {
            const suffix = isScoreUnverified(e)
              ? " (unverified)"
              : e.rawScore
              ? ` (${escapeHtml(e.rawScore)})`
              : "";
            return `<a class="source-chip" href="${escapeHtml(e.sourceUrl)}" target="_blank" rel="noopener noreferrer">📰 ${escapeHtml(
              e.sourceName
            )}${suffix} ↗</a>`;
          }),
          ...o.youtubeReviews
            .filter((y) => !editorialUrlSet.has(y.sourceUrl))
            .slice(0, 3)
            .map(
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

        const partner = getPartnerPrograms(h);
        const profile = getGuestProfile(h);
        const climate = getBestMonthsMeta(h);
        const activePillarKey = state.sortBy.startsWith("pillar_") ? state.sortBy.replace("pillar_", "") : null;
        const pillarLabels = { rooms: "Rooms", service: "Service", food: "Food", grounds: "Vibe", value: "Value" };
        const activePillarPill =
          activePillarKey && o.firstHand && h.scores && h.scores[activePillarKey] != null
            ? `<span class="tag tag-accent">★ ${pillarLabels[activePillarKey]}: ${escapeHtml(formatPersonalScore(h.scores[activePillarKey]))}/5</span>`
            : "";

        // Highlight exact award rank when filtering/sorting by Top 50, Top 100, MICHELIN Keys, or Forbes
        const w50Rank = getW50BestRank(h);
        const mKeysCard = getMichelinKeyCount(h);
        const fRankCard = getForbesRank(h);
        let activeAwardRankPill = "";
        if ((state.sortBy === "award_50best" || state.feature.startsWith("50best")) && w50Rank != null) {
          activeAwardRankPill = `<span class="award-rank-pill-highlight">&#127942; World&rsquo;s 50 Best #${w50Rank}</span>`;
        } else if ((state.sortBy === "award_michelin" || state.feature.startsWith("michelin")) && mKeysCard != null) {
          activeAwardRankPill = `<span class="award-rank-pill-highlight">&#128477;&#65039; ${mKeysCard} MICHELIN Key${mKeysCard > 1 ? "s" : ""}</span>`;
        } else if ((state.sortBy === "award_forbes" || state.feature === "forbes") && fRankCard != null) {
          const fLbl = fRankCard === 5 ? "Forbes Five-Star" : fRankCard === 4 ? "Forbes Four-Star" : "Forbes Recommended";
          activeAwardRankPill = `<span class="award-rank-pill-highlight">&#11088; ${fLbl}</span>`;
        }

        // Max 3 high-signal top badges (+ indicative price chip)
        const topAwardChip = o.officialAwards.length
          ? `<span class="tag tag-teal">🏆 ${escapeHtml(o.officialAwards[0].label)}</span>`
          : "";
        const secondaryTopBadge =
          activeAwardRankPill ||
          activePillarPill ||
          propStatusPill ||
          topAwardChip ||
          (h.brand ? `<span class="tag">${escapeHtml(h.brand)}</span>` : "");

        const takeawayLine = h.whereWeDiffer || h.standout || o.opinionGap.headline || "";

        const secondaryMetaPills = [
          h.brand ? `<span class="tag">${escapeHtml(h.brand)}</span>` : "",
          partner.preferredProgram ? `<span class="tag" title="${escapeHtml(partner.perksNote)}">✨ ${escapeHtml(partner.preferredProgram)}</span>` : "",
          partner.pointsProgram ? `<span class="tag tag-teal">★ ${escapeHtml(partner.pointsProgram)}</span>` : "",
          profile.isAdultsOnly ? `<span class="tag tag-slate">🥂 Adults-Only</span>` : profile.isFamilyFriendly ? `<span class="tag">👨‍👩‍👧 Family</span>` : "",
          `<span class="tag" title="${escapeHtml(climate.reason)}">📅 Best: ${escapeHtml(climate.label)}</span>`,
        ]
          .filter(Boolean)
          .join("");

        return `
          <article class="consensus-row-card ${trackCls}" data-resort-name="${escapeHtml(h.name)}">
            <div class="consensus-rank-col">
              <span class="consensus-rank-num">#${i + 1}</span>
              <div class="consensus-chance-ring ${trackCls}">
                <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : o.officialAwards.length ? "Award" : "Open"}</strong>
                <span>${o.scoreTrack === "verified" ? "Verified" : "Market Odds"}</span>
              </div>
              <div class="consensus-index-chip">
                ${
                  o.personalScoreLabel
                    ? `<strong>${escapeHtml(o.personalScoreLabel)}</strong> My Stay`
                    : o.marketSourceCount > 0
                    ? `<strong>${o.marketSourceCount}</strong> source${o.marketSourceCount === 1 ? "" : "s"}`
                    : o.officialAwards.length
                    ? `<strong>${o.officialAwards.length}</strong> award${o.officialAwards.length === 1 ? "" : "s"}`
                    : "Live Google"
                }
              </div>
            </div>

            <div class="consensus-main-col">
              <div class="meta-line">
                <span class="tag ${o.scoreTrack === "verified" ? "tag-accent" : "tag-slate"}">${escapeHtml(o.scoreTrackLabel)}</span>
                ${
                  o.founderVsMarketLabel
                    ? `<span class="founder-delta-pill ${deltaToneCls}">${escapeHtml(o.founderVsMarketLabel)}</span>`
                    : ""
                }
                ${secondaryTopBadge}
                ${priceInfo.label ? `<span class="price-chip-indicative">${escapeHtml(priceInfo.label)}</span>` : ""}
                <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
              </div>

              <h3 class="consensus-title">
                <a class="consensus-title-link" href="${getSeoHref(h)}">${escapeHtml(h.name)}</a>
              </h3>

              <div class="three-pillar-strip is-three-col">
                <div class="pillar-box is-ours">
                  <small>${o.firstHand ? "My Stay (70%)" : "First-Hand Stay"}</small>
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
                  <small>Verified Guests${o.marketOdds != null && o.firstHand ? ` · Mkt ${o.marketOdds}%` : ""}</small>
                  <strong>${o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}` : "Open Breakdown"}</strong>
                </div>
              </div>

              ${
                takeawayLine
                  ? `<p class="card-takeaway-line"><strong>${o.firstHand ? "My Take:" : `${escapeHtml(o.opinionGap.title)}:`}</strong> ${escapeHtml(takeawayLine)}</p>`
                  : ""
              }

              <details class="card-details-expander">
                <summary>Details, Perks &amp; Sources &#9662;</summary>
                <div class="card-details-body">
                  <div class="meta-line" style="margin-bottom:8px;">${secondaryMetaPills}</div>
                  ${keyFactChips ? `<div class="card-key-facts-strip" style="margin-bottom:8px;">${keyFactChips}</div>` : ""}
                  ${h.standout && h.standout !== takeawayLine ? `<p style="margin:0 0 6px;font-size:13px;"><strong>Standout:</strong> ${escapeHtml(h.standout)}</p>` : ""}
                  ${h.watchOut ? `<p style="margin:0 0 8px;font-size:13px;"><strong>Watch-Out:</strong> ${escapeHtml(h.watchOut)}</p>` : ""}
                  <div class="consensus-sources">
                    ${sourceChips}
                    <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
                    <span class="source-chip">${escapeHtml(o.formulaSummary)}</span>
                  </div>
                </div>
              </details>
            </div>

            <div class="consensus-cta-col">
              <a href="${getSeoHref(h)}">
                <img class="consensus-thumb" src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" loading="lazy" decoding="async" />
              </a>
              <a class="btn btn-primary" href="${getSeoHref(h)}">Full Breakdown &rarr;</a>
              ${
                reviewHref
                  ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Short" : "Watch Review"}</a>`
                  : ""
              }
              <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
              <div style="display:flex;gap:6px;">
                <button type="button" class="btn btn-outline shortlist-btn" style="flex:1;padding:6px 8px;font-size:12px;" data-shortlist-id="${escapeHtml(h.id)}" data-shortlist-compact="1" data-resort-name="${escapeHtml(h.name)}" aria-pressed="false">&#9825; Save</button>
                <button class="copy-link-btn" style="flex:1;" data-compare-id="${escapeHtml(h.id)}" type="button">VS &uarr;</button>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    container.innerHTML = cardsHtml + pagerHtml;
  }

  window.stayOddsShortlist?.syncButtons?.();

  activeRoot.querySelector("#loadMoreHotelsBtn")?.addEventListener("click", () => {
    state.visibleLimit += PAGE_SIZE;
    renderLeaderboard();
  });
  activeRoot.querySelector("#showAllHotelsBtn")?.addEventListener("click", () => {
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
    const hc = state.threeWay ? state.hotels.find((h) => h.id === state.idC) : null;
    if (ha && hb) {
      window.trackEvent("compare_resorts", "resorts", hc ? `${ha.name} vs ${hb.name} vs ${hc.name}` : `${ha.name} vs ${hb.name}`);
    }
  }

  activeRoot.querySelectorAll("[data-compare-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.compareId;
      if (!id) return;
      if (state.threeWay) {
        if (id !== state.idA && id !== state.idB && id !== state.idC) {
          state.idC = state.idB;
          state.idB = state.idA;
          state.idA = id;
        }
      } else {
        if (id !== state.idA) {
          state.idB = state.idA;
          state.idA = id;
        }
      }
      state.searchA = "";
      state.searchB = "";
      state.searchC = "";
      ["#compareSearchA", "#compareSearchB", "#compareSearchC"].forEach((sel) => {
        const inp = qs(sel);
        if (inp) inp.value = "";
      });
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
  const hadCompareParams = Boolean(params.get("a") || params.get("b") || params.get("c"));
  if (params.get("a")) state.idA = params.get("a");
  if (params.get("b")) state.idB = params.get("b");
  if (params.get("c")) {
    state.idC = params.get("c");
    state.threeWay = true;
  }
  if (["all", "visited", "world", "saved"].includes(params.get("scope"))) {
    state.scope = params.get("scope");
  }
  if (params.get("brand")) {
    state.brandFilter = params.get("brand").trim();
  }
  const monthParam = Number(params.get("month") || 0);
  if (monthParam >= 1 && monthParam <= 12) {
    state.month = monthParam;
  }
  const savedParam = (params.get("saved") || "").trim();
  if (savedParam) {
    const parsedSaved = savedParam
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (parsedSaved.length) {
      state.sharedSavedIds = Array.from(new Set(parsedSaved));
      state.scope = "saved";
    }
  }

  function trackH2HDropdown() {
    if (typeof window.trackEvent !== "function") return;
    const ha = state.hotels.find((h) => h.id === state.idA);
    const hb = state.hotels.find((h) => h.id === state.idB);
    const hc = state.threeWay ? state.hotels.find((h) => h.id === state.idC) : null;
    if (ha && hb) {
      window.trackEvent("compare_resorts", "resorts", hc ? `${ha.name} vs ${hb.name} vs ${hc.name}` : `${ha.name} vs ${hb.name}`);
    }
  }

  const setThreeWayMode = (enabled) => {
    state.threeWay = Boolean(enabled);
    if (state.threeWay) {
      if (!state.hotels.some((h) => h.id === state.idC) || state.idC === state.idA || state.idC === state.idB) {
        const nextC =
          state.hotels.find((h) => isVisitedProperty(h) && h.id !== state.idA && h.id !== state.idB) ||
          state.hotels.find((h) => h.id !== state.idA && h.id !== state.idB);
        if (nextC) state.idC = nextC.id;
      }
      populateSingleSelector("C");
    }
    renderH2H();
    syncUrlParams(true);
    if (typeof window.trackEvent === "function") {
      window.trackEvent("toggle_three_way", "resorts", state.threeWay ? "on" : "off");
    }
  };

  qs("#toggleThreeWayBtn")?.addEventListener("click", () => setThreeWayMode(!state.threeWay));
  qs("#removeHotelCBtn")?.addEventListener("click", () => setThreeWayMode(false));

  qs("#h2hQuickMatchups")?.querySelectorAll("[data-matchup-a]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const a = btn.dataset.matchupA;
      const b = btn.dataset.matchupB;
      if (!a || !b) return;
      state.threeWay = false;
      state.idA = a;
      state.idB = b;
      state.searchA = "";
      state.searchB = "";
      state.liveRates = {};
      ["#compareSearchA", "#compareSearchB", "#compareSearchC"].forEach((sel) => {
        const inp = qs(sel);
        if (inp) inp.value = "";
      });
      populateH2HSelectors();
      renderH2H();
      syncUrlParams(true);
      trackH2HDropdown();
    });
  });

  qs("#shareVsCardBtn")?.addEventListener("click", async () => {
    const ha = state.hotels.find((h) => h.id === state.idA) || state.hotels[0];
    const hb = state.hotels.find((h) => h.id === state.idB) || state.hotels[1];
    if (!ha || !hb) return;
    if (state.threeWay) {
      const hc =
        state.hotels.find((h) => h.id === state.idC) ||
        state.hotels.find((h) => h.id !== ha.id && h.id !== hb.id);
      if (hc) {
        const { openThreeWayShareModal } = await import("./stayodds-share-card.js?v=8");
        openThreeWayShareModal(ha, hb, hc, getOdds(ha), getOdds(hb), getOdds(hc));
        if (typeof window.trackEvent === "function") {
          window.trackEvent("open_share_card", "vs_three_hotel", `${ha.name} vs ${hb.name} vs ${hc.name}`);
        }
        return;
      }
    }
    const { openVsShareModal } = await import("./stayodds-share-card.js?v=8");
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
    const cfg = SELECTOR_SIDES[side];
    if (!cfg) return;
    const inp = qs(`#compareSearch${side}`);
    const clearBtn = qs(cfg.clear);
    inp?.addEventListener("input", (e) => {
      state[cfg.searchKey] = e.target.value || "";
      const prevId = state[cfg.idKey];
      populateSingleSelector(side);
      const nextId = state[cfg.idKey];
      if (nextId !== prevId) {
        renderH2H();
        syncUrlParams(true);
      }
    });
    clearBtn?.addEventListener("click", () => {
      state[cfg.searchKey] = "";
      if (inp) {
        inp.value = "";
        inp.focus();
      }
      populateSingleSelector(side);
    });
  };
  wireSelectorSearch("A");
  wireSelectorSearch("B");
  wireSelectorSearch("C");

  const copyToClipboard = async (text) => {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const tmp = document.createElement("textarea");
      tmp.value = text;
      tmp.style.position = "fixed";
      tmp.style.opacity = "0";
      document.body.appendChild(tmp);
      tmp.select();
      document.execCommand("copy");
      tmp.remove();
    }
  };

  qs("#copyVsLinkBtn")?.addEventListener("click", async () => {
    const btn = qs("#copyVsLinkBtn");
    const baseShare = `https://stayodds.com/?a=${encodeURIComponent(state.idA)}&b=${encodeURIComponent(state.idB)}`;
    const shareUrl = state.threeWay && state.idC ? `${baseShare}&c=${encodeURIComponent(state.idC)}` : baseShare;
    const ha = state.hotels.find((h) => h.id === state.idA);
    const hb = state.hotels.find((h) => h.id === state.idB);
    const hc = state.threeWay ? state.hotels.find((h) => h.id === state.idC) : null;
    try {
      await copyToClipboard(shareUrl);
      if (typeof window.trackEvent === "function" && ha && hb) {
        window.trackEvent(
          "share_comparison",
          hc ? "vs_three_hotel" : "vs_pair",
          hc ? `${ha.name} vs ${hb.name} vs ${hc.name}` : `${ha.name} vs ${hb.name}`
        );
      }
      if (btn) {
        btn.classList.add("is-copied");
        btn.textContent = state.threeWay ? "✓ Copied 3-Hotel Link!" : "✓ Copied VS Link!";
        setTimeout(() => {
          btn.classList.remove("is-copied");
          btn.innerHTML = state.threeWay ? "&#128279; Copy 3-Hotel Link" : "&#128279; Copy VS Link";
        }, 2200);
      }
    } catch (_) {
      window.prompt("Copy this comparison link:", shareUrl);
    }
  });

  const triggerCsvExport = (isShortlist = false) => {
    const targetList = state.lastFilteredList && state.lastFilteredList.length ? state.lastFilteredList : getScopedHotels();
    if (!targetList.length) return;
    const fname = isShortlist
      ? "stayodds-saved-shortlist.csv"
      : state.brandFilter
      ? `stayodds-${state.brandFilter.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.csv`
      : "stayodds-luxury-hotels.csv";
    exportHotelsToCsv(
      targetList,
      getOdds,
      { getMichelinKeyCount, getW50BestRank, getForbesRank },
      fname
    );
    if (typeof window.trackEvent === "function") {
      window.trackEvent("export_csv", isShortlist ? "shortlist" : "directory", String(targetList.length));
    }
  };

  qs("#exportDirectoryCsvBtn")?.addEventListener("click", () => triggerCsvExport(false));
  qs("#exportShortlistCsvBtn")?.addEventListener("click", () => triggerCsvExport(true));

  qs("#shareShortlistBtn")?.addEventListener("click", async () => {
    const btn = qs("#shareShortlistBtn");
    const ids = getActiveShortlistIds().slice(0, 40);
    if (!ids.length) return;
    const shareUrl = `https://stayodds.com/?scope=saved&saved=${encodeURIComponent(ids.join(","))}`;
    try {
      await copyToClipboard(shareUrl);
      if (btn) {
        const orig = btn.innerHTML;
        btn.textContent = "✓ Copied Shortlist Link!";
        setTimeout(() => {
          btn.innerHTML = orig;
        }, 2200);
      }
    } catch (_) {
      window.prompt("Copy this shareable Shortlist link:", shareUrl);
    }
  });

  qs("#importSharedShortlistBtn")?.addEventListener("click", () => {
    if (!Array.isArray(state.sharedSavedIds) || !state.sharedSavedIds.length) return;
    const existing = getShortlistIds();
    const merged = Array.from(new Set([...existing, ...state.sharedSavedIds]));
    try {
      localStorage.setItem(SHORTLIST_KEY, JSON.stringify(merged));
    } catch (_) {}
    state.sharedSavedIds = null;
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete("saved");
      window.history.replaceState({}, "", url.toString());
    } catch (_) {}
    window.stayOddsShortlist?.syncButtons?.();
    renderScopeTabs();
    renderShortlistUtilityBar();
    renderLeaderboard();
  });

  window.addEventListener("stayodds:shortlist-changed", () => {
    renderScopeTabs();
    renderShortlistUtilityBar();
    if (state.scope === "saved") {
      renderRegionPills();
      renderFeaturePills();
      renderStylePills();
      renderMonthPills();
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
  qs("#compareSelectC")?.addEventListener("change", (e) => {
    state.idC = e.target.value;
    renderH2H();
    syncUrlParams(true);
    trackH2HDropdown();
  });

  const setViewMode = (mode) => {
    state.viewMode = mode === "table" ? "table" : "cards";
    qs("#consensusViewCardsBtn")?.classList.toggle("active", state.viewMode === "cards");
    qs("#consensusViewTableBtn")?.classList.toggle("active", state.viewMode === "table");
    if (state.viewMode === "table" && state.visibleLimit < 50) {
      state.visibleLimit = 50;
    }
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "view_mode", `compare:${state.viewMode}`);
    }
    renderLeaderboard();
  };
  qs("#consensusViewCardsBtn")?.addEventListener("click", () => setViewMode("cards"));
  qs("#consensusViewTableBtn")?.addEventListener("click", () => setViewMode("table"));

  qs("#verdictFilter")?.addEventListener("change", (e) => {
    state.verdict = e.target.value || "All";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `verdict:${state.verdict}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderLeaderboard();
  });
  qs("#priceTierFilter")?.addEventListener("change", (e) => {
    state.priceTier = e.target.value || "all";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `priceTier:${state.priceTier}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderLeaderboard();
  });

  // More Filters collapsible drawer + hover preview popover + Quick Presets
  const drawerBtn = qs("#compareMoreFiltersBtn");
  const drawerEl = qs("#compareMoreFiltersDrawer");
  const previewPopover = qs("#compareFiltersPreviewPopover");
  const setDrawerOpen = (open) => {
    if (!drawerBtn || !drawerEl) return;
    drawerEl.hidden = !open;
    drawerBtn.setAttribute("aria-expanded", String(open));
    drawerBtn.classList.toggle("is-open", open);
    if (previewPopover) previewPopover.dataset.drawerOpen = String(open);
  };
  if (drawerBtn && drawerEl) {
    drawerBtn.addEventListener("click", () => {
      setDrawerOpen(drawerEl.hidden);
    });
  }
  document.querySelectorAll("[data-open-more-drawer]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setDrawerOpen(true);
      drawerEl?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  });
  document.querySelectorAll("[data-quick-preset]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const preset = btn.dataset.quickPreset;
      if (preset === "50best_50" || preset === "50best_100" || preset === "michelin" || preset === "michelin_3" || preset === "adults") {
        applyFeatureSelection(state.feature === preset ? "all" : preset);
      } else if (preset === "style_island") {
        state.style = state.style === "island" ? "all" : "island";
      } else if (preset === "budget_under500") {
        state.priceTier = state.priceTier === "under500" ? "all" : "under500";
        const pf = qs("#priceTierFilter");
        if (pf) pf.value = state.priceTier;
      }
      if (typeof window.trackEvent === "function") {
        window.trackEvent("use_filter", "quick_preset", String(preset));
      }
      state.visibleLimit = PAGE_SIZE;
      syncUrlParams();
      renderFeaturePills();
      renderStylePills();
      renderMonthPills();
      renderLeaderboard();
    });
  });
  qs("#compareClearDrawerFiltersBtn")?.addEventListener("click", () => {
    state.verdict = "All";
    state.priceTier = "all";
    applyFeatureSelection("all");
    state.style = "all";
    state.month = 0;
    const vf = qs("#verdictFilter");
    if (vf) vf.value = "All";
    const pf = qs("#priceTierFilter");
    if (pf) pf.value = "all";
    state.visibleLimit = PAGE_SIZE;
    syncUrlParams();
    renderFeaturePills();
    renderStylePills();
    renderMonthPills();
    renderLeaderboard();
  });

  // H2H date-aware outbound links + explicit on-demand Check Live Rates
  const pad2 = (n) => String(n).padStart(2, "0");
  const toIso = (d) => `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
  const defaultCi = new Date(Date.now() + 45 * 86400000);
  const defaultCo = new Date(Date.now() + 47 * 86400000);
  const ciInput = qs("#h2hCheckin");
  const coInput = qs("#h2hCheckout");
  const adultsSel = qs("#h2hAdults");
  const liveStatusEl = qs("#h2hLiveRatesStatus");
  if (ciInput) {
    ciInput.min = toIso(new Date(Date.now() + 86400000));
    ciInput.value = toIso(defaultCi);
    state.checkin = ciInput.value;
    ciInput.addEventListener("change", () => {
      state.checkin = ciInput.value || "";
      if (coInput && state.checkin && (!coInput.value || coInput.value <= state.checkin)) {
        const d = new Date(state.checkin + "T00:00:00");
        d.setDate(d.getDate() + 2);
        coInput.value = toIso(d);
        state.checkout = coInput.value;
      }
      state.liveRates = {};
      renderH2H();
    });
  }
  if (coInput) {
    coInput.min = toIso(new Date(Date.now() + 2 * 86400000));
    coInput.value = toIso(defaultCo);
    state.checkout = coInput.value;
    coInput.addEventListener("change", () => {
      state.checkout = coInput.value || "";
      state.liveRates = {};
      renderH2H();
    });
  }
  if (adultsSel) {
    state.adults = Number(adultsSel.value || 2);
    adultsSel.addEventListener("change", () => {
      state.adults = Number(adultsSel.value || 2);
      state.liveRates = {};
      renderH2H();
    });
  }
  qs("#h2hCheckLiveRatesBtn")?.addEventListener("click", async () => {
    const btn = qs("#h2hCheckLiveRatesBtn");
    const ci = state.checkin;
    const co = state.checkout;
    if (!ci || !co || co <= ci) {
      if (liveStatusEl) liveStatusEl.textContent = "Please choose a valid check-in and check-out date first.";
      return;
    }
    const comparedIds = [state.idA, state.idB, state.threeWay ? state.idC : null].filter(Boolean);
    const hotelsToCheck = comparedIds.map((id) => state.hotels.find((h) => h.id === id)).filter(Boolean);
    const nuiteeIds = hotelsToCheck.map((h) => h.nuiteeHotelId).filter(Boolean);
    if (!nuiteeIds.length) {
      if (liveStatusEl) {
        liveStatusEl.textContent = "Live rate API isn't mapped for these properties yet — click Rates ↗ to view Booking.com with your dates pre-filled.";
      }
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Checking live rates…";
    }
    if (liveStatusEl) liveStatusEl.textContent = `Fetching live GBP rates for ${ci} → ${co}…`;
    const res = await fetchLiveHotelRates(nuiteeIds, ci, co, state.adults, "GBP");
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "&#128176; Check Live Rates";
    }
    if (res && res.status === "ok" && res.rates && Object.keys(res.rates).length > 0) {
      state.liveRates = { ...state.liveRates, ...res.rates };
      renderH2H();
      const foundCnt = Object.keys(res.rates).length;
      if (liveStatusEl) {
        liveStatusEl.textContent = `Live GBP rates loaded for ${foundCnt} of ${hotelsToCheck.length} compared hotel${hotelsToCheck.length === 1 ? "" : "s"} (${ci} → ${co}).`;
      }
    } else if (res && res.status === "quota_exceeded") {
      if (liveStatusEl) {
        liveStatusEl.textContent = "Daily live-rate lookup limit reached — click Rates ↗ on each card to view Booking.com with your dates pre-filled.";
      }
    } else {
      if (liveStatusEl) {
        liveStatusEl.textContent = "No live rooms returned for those exact dates — try different dates or click Rates ↗ to check Booking.com directly.";
      }
    }
  });

  qs("#consensusSort")?.addEventListener("change", (e) => {
    state.sortBy = e.target.value || "visited";
    state.tableSortKey = null;
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
    const IDX_CACHE_KEY = "stayodds_index_cache_v20261124d";
    const IDX_TTL_MS = 6 * 60 * 60 * 1000;
    let payload = null;
    try {
      const raw = localStorage.getItem(IDX_CACHE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.ts && Date.now() - parsed.ts < IDX_TTL_MS && parsed.data && Array.isArray(parsed.data.hotels)) {
          payload = parsed.data;
        }
      }
    } catch (_) {}
    if (!payload) {
      const res = await fetch(`../data/stayodds-index.json?v=20261124d`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      payload = await res.json();
      try {
        localStorage.setItem(IDX_CACHE_KEY, JSON.stringify({ ts: Date.now(), data: payload }));
      } catch (_) {}
    }

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
    const styleParam = params.get("style");
    if (styleParam && TRAVEL_STYLES.some((s) => s.id === styleParam)) state.style = styleParam;

    populateH2HSelectors();
    renderH2H();
    renderScopeTabs();
    renderRegionPills();
    renderFeaturePills();
    renderStylePills();
    renderMonthPills();
    renderLeaderboard();

    if (hadCompareParams) {
      requestAnimationFrame(() => {
        qs(".h2h-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } else if (state.brandFilter || state.sharedSavedIds || (matchedRegion && matchedRegion !== "All")) {
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
