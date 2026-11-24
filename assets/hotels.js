import {
  MACRO_REGIONS,
  computeStayOdds,
  formatPersonalScore,
  getPriceDisplay,
  isFirstHandVerified,
  isScoreUnverified,
  isVisitedProperty,
} from "./stayodds-engine.js?v=9";
import { TRAVEL_STYLES, matchesTravelStyle } from "./stayodds-categories.js?v=2";
import {
  MONTH_LABELS,
  getBrandCategories,
  matchesBrandCategory,
  getPartnerPrograms,
  matchesBestMonth,
  getGuestProfile,
  exportHotelsToCsv,
} from "./stayodds-insights.js?v=3";

const PAGE_SIZE = 24;
const oddsCache = new WeakMap();

function getOdds(h) {
  let c = oddsCache.get(h);
  if (!c) {
    c = computeStayOdds(h);
    oddsCache.set(h, c);
  }
  return c;
}

const state = {
  hotels: [],
  scope: "all", // "all" | "visited" | "global" | "michelin" | "w50"
  region: "All",
  brand: "All",
  style: "all",
  profileFilter: "all", // "all" | "adults" | "family" | "preferred" | "points"
  month: 0, // 0 = All Months, 1..12 = Jan..Dec
  coverage: "All",
  sortBy: "stayodds",
  tableSortKey: null, // null | "name" | "location" | "odds" | "overall" | "critic" | "guest" | "gap" | "michelin" | "w50" | "forbes"
  tableSortDir: "desc",
  search: "",
  viewMode: "cards",
  visibleLimit: PAGE_SIZE,
  map: null,
  markersLayer: null,
  markerById: new Map(),
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
  const q = new URLSearchParams({ from: "map" });
  if (isEmbedParam) q.set("embed", "1");
  return `../stayodds/${encodeURIComponent(h.id)}/?${q.toString()}`;
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

function syncUrlParams() {
  try {
    const url = new URL(window.location.href);
    if (state.region && state.region !== "All") url.searchParams.set("region", state.region);
    else url.searchParams.delete("region");
    if (state.scope && state.scope !== "all") url.searchParams.set("scope", state.scope);
    else url.searchParams.delete("scope");
    if (state.style && state.style !== "all") url.searchParams.set("style", state.style);
    else url.searchParams.delete("style");
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

function hasMichelinKey(h) {
  return getMichelinKeyCount(h) != null;
}

function hasW50Best(h) {
  return getW50BestRank(h) != null;
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

function initMap() {
  const mapEl = qs("#hotelMap");
  if (!mapEl || typeof L === "undefined") return;

  const map = L.map("hotelMap", {
    scrollWheelZoom: false,
    worldCopyJump: true,
    preferCanvas: true,
  }).setView([20.0, 20.0], 2);

  const cartoLayer = L.tileLayer(
    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=cb1_5db3_1_c3957b21042bb79553569521",
    {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }
  );

  let switched = false;
  cartoLayer.on("tileerror", () => {
    if (switched) return;
    switched = true;
    map.removeLayer(cartoLayer);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);
  });

  cartoLayer.addTo(map);
  state.map = map;
  state.canvasRenderer = L.canvas({ padding: 0.5 });
  state.markersLayer = L.layerGroup().addTo(map);
}

function getScopedHotels() {
  if (state.scope === "visited") return state.hotels.filter(isVisitedProperty);
  if (state.scope === "global") return state.hotels.filter((h) => !isVisitedProperty(h));
  if (state.scope === "michelin") return state.hotels.filter(hasMichelinKey);
  if (state.scope === "w50") return state.hotels.filter(hasW50Best);
  return state.hotels;
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

function getFilteredHotels() {
  const q = state.search.trim().toLowerCase();
  const list = getScopedHotels().filter((h) => {
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.brand !== "All" && !matchesBrandCategory(h, state.brand)) return false;
    if (!matchesTravelStyle(h, state.style)) return false;
    if (state.month && !matchesBestMonth(h, state.month)) return false;
    if (state.profileFilter !== "all") {
      const gp = getGuestProfile(h);
      const pp = getPartnerPrograms(h);
      if (state.profileFilter === "adults" && !gp.isAdultsOnly) return false;
      if (state.profileFilter === "family" && !gp.isFamilyFriendly) return false;
      if (state.profileFilter === "preferred" && !pp.hasPreferredPerks) return false;
      if (state.profileFilter === "points" && !pp.isPointsEligible) return false;
    }
    if (state.coverage !== "All" && (h.coverageType || "Global Directory") !== state.coverage) {
      return false;
    }
    if (!q) return true;
    const hay = [
      h.name,
      h.location,
      h.country,
      h.region,
      h.brand,
      h.verdict,
      h.standout,
      ...(h.officialAwards || []).map((a) => a.label),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  const getDisagreementPts = (o) => {
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

    if (state.sortBy === "name") return a.name.localeCompare(b.name);
    if (state.sortBy === "odds") {
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "gap") {
      const ga = getDisagreementPts(oa) ?? -1;
      const gb = getDisagreementPts(ob) ?? -1;
      if (gb !== ga) return gb - ga;
      if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "overall") {
      const av = oa.firstHand ? Number(a.overall || 0) : -1;
      const bv = ob.firstHand ? Number(b.overall || 0) : -1;
      if (bv !== av) return bv - av;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    if (state.sortBy === "awards") {
      const aa = (a.officialAwards || []).length;
      const ba = (b.officialAwards || []).length;
      if (ba !== aa) return ba - aa;
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    // Default "stayodds": First-Hand Verified first, then Short Tours, then Global Directory by StayOdds %
    if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
    return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
  });

  return list;
}

function renderScopeTabs() {
  const container = qs("#mapScopeTabs");
  if (!container) return;
  const visitedCnt = state.hotels.filter(isVisitedProperty).length;
  const globalCnt = state.hotels.length - visitedCnt;
  const michelinCnt = state.hotels.filter(hasMichelinKey).length;
  const w50Cnt = state.hotels.filter(hasW50Best).length;

  const tabs = [
    { id: "all", label: `All Luxury Hotels (${state.hotels.length})` },
    { id: "visited", label: `My First-Hand Stays (${visitedCnt})` },
    { id: "global", label: `Global Directory (${globalCnt})` },
    { id: "michelin", label: `2026 MICHELIN Keys (${michelinCnt})` },
    { id: "w50", label: `World's 50 Best (${w50Cnt})` },
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
      renderStylePills();
      renderAll(true);
    });
  });
}

function renderRegionPills() {
  const container = qs("#regionPills");
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
      renderStylePills();
      renderAll(true);
    });
  });
}

function renderStylePills() {
  const container = qs("#mapStylePills");
  if (!container) return;
  const base = getScopedHotels().filter((h) => state.region === "All" || h.region === state.region);
  container.innerHTML = TRAVEL_STYLES.map((s) => {
    const cnt = s.id === "all" ? base.length : base.filter(s.match).length;
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
      renderAll(true);
    });
  });
}

function populateBrands() {
  const sel = qs("#brandFilter");
  if (!sel) return;
  const parentSet = new Set(["Marriott Bonvoy", "World of Hyatt", "Hilton Honors", "IHG One Rewards", "Accor", "LVMH Hospitality"]);
  const parentCounts = new Map();
  const brandCounts = new Map();
  for (const h of state.hotels) {
    const { primaryBrand, allBrands } = getBrandCategories(h);
    if (primaryBrand && !parentSet.has(primaryBrand)) {
      brandCounts.set(primaryBrand, (brandCounts.get(primaryBrand) || 0) + 1);
    }
    for (const b of allBrands) {
      if (parentSet.has(b)) {
        parentCounts.set(b, (parentCounts.get(b) || 0) + 1);
      }
    }
  }
  const parents = Array.from(parentCounts.entries()).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const brands = Array.from(brandCounts.entries()).sort((a, b) => a[0].localeCompare(b[0]));

  sel.innerHTML =
    `<option value="All">All Hotel Brands &amp; Groups (${brands.length + parents.length})</option>` +
    `<optgroup label="★ Parent Hotel &amp; Loyalty Groups">` +
    parents.map(([b, c]) => `<option value="${escapeHtml(b)}">${escapeHtml(b)} (${c})</option>`).join("") +
    `</optgroup>` +
    `<optgroup label="🏨 Luxury Hotel Brands">` +
    brands.map(([b, c]) => `<option value="${escapeHtml(b)}">${escapeHtml(b)} (${c})</option>`).join("") +
    `</optgroup>`;
}

function buildPopupHtml(h) {
  const o = getOdds(h);
  const priceInfo = getPriceDisplay(h);
  const awardsBadges = (h.officialAwards || [])
    .slice(0, 1)
    .map((a) => `<span class="tag tag-teal" style="font-size:10.5px;">🏆 ${escapeHtml(a.label)}</span>`)
    .join(" ");

  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  return `
    <div class="map-popup-card">
      <div class="map-popup-media">
        <img src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" loading="lazy" decoding="async" />
        <span class="map-popup-score">${
          o.greatStayOdds != null
            ? `${o.greatStayOdds}% ${o.scoreTrack === "verified" ? "Verified" : "Market"}`
            : escapeHtml(o.scoreTrackLabel)
        }</span>
      </div>
      <div class="map-popup-body">
        <div style="display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px;">
          <span class="tag ${o.scoreTrack === "verified" ? "tag-accent" : "tag-slate"}" style="font-size:10.5px;">${escapeHtml(o.scoreTrackLabel)}</span>
          ${o.personalScoreLabel ? `<span class="tag tag-accent" style="font-size:10.5px;">My Stay ${escapeHtml(o.personalScoreLabel)}</span>` : ""}
          ${priceInfo.label ? `<span class="price-chip-indicative" style="font-size:10.5px;padding:2px 6px;">${escapeHtml(priceInfo.label)}</span>` : ""}
          ${awardsBadges}
        </div>
        <h4>${escapeHtml(h.name)}</h4>
        <div class="map-popup-loc">${escapeHtml(h.location)}, ${escapeHtml(h.country)}${
    h.brand ? ` &bull; ${escapeHtml(h.brand)}` : ""
  }</div>
        <p>${escapeHtml(h.whereWeDiffer || h.verdict || h.standout || o.opinionGap.headline)}</p>
        <div class="map-popup-actions">
          <a class="btn btn-primary" href="${getSeoHref(h)}">StayOdds Page</a>
          <a class="btn btn-outline" href="../compare/?a=${encodeURIComponent(h.id)}">Compare VS</a>
          ${
            reviewHref
              ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>Video</a>`
              : `<a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates ↗</a>`
          }
        </div>
        <div style="margin-top:8px;">
          <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
        </div>
      </div>
    </div>
  `;
}

function renderMapMarkers(hotels, fitBounds = true) {
  if (!state.map || !state.markersLayer) return;
  state.markersLayer.clearLayers();
  state.markerById.clear();

  const bounds = [];
  for (const h of hotels) {
    if (typeof h.lat !== "number" || typeof h.lng !== "number" || (h.lat === 0 && h.lng === 0)) {
      continue;
    }
    bounds.push([h.lat, h.lng]);

    const o = getOdds(h);
    const isVisited = isVisitedProperty(h);
    const isMichelin = hasMichelinKey(h);

    let marker;
    if (isVisited) {
      const pinClass = o.firstHand ? "" : "is-short";
      const pinText = o.personalScoreLabel
        ? o.personalScoreLabel.replace(/ /g, "")
        : h.coverageType === "Short Tour"
        ? "Short"
        : "Filmed";
      const zOffset = o.firstHand ? 600 : 500;

      const icon = L.divIcon({
        className: "hotel-score-pin-wrap",
        html: `<div class="hotel-score-pin ${pinClass}"><span>${pinText}</span></div>`,
        iconSize: [40, 34],
        iconAnchor: [20, 34],
        popupAnchor: [0, -30],
      });

      marker = L.marker([h.lat, h.lng], { icon, zIndexOffset: zOffset });
    } else {
      // 60fps Canvas circleMarker for all 264 Global Directory properties (zero DOM lag!)
      marker = L.circleMarker([h.lat, h.lng], {
        renderer: state.canvasRenderer,
        radius: isMichelin ? 7.5 : 6.5,
        fillColor: "#0f766e",
        color: isMichelin ? "#fbbf24" : "#ffffff",
        weight: isMichelin ? 2.5 : 2,
        opacity: 1,
        fillOpacity: 0.92,
      });
      marker.bindTooltip(
        `<strong>${escapeHtml(h.name)}</strong>${o.greatStayOdds != null ? ` • ${o.greatStayOdds}%` : ""}`,
        { direction: "top", offset: [0, -8] }
      );
    }

    marker
      .bindPopup(() => buildPopupHtml(h), { className: "uncharted-popup", maxWidth: 310 })
      .addTo(state.markersLayer);

    state.markerById.set(h.id, marker);
  }

  if (fitBounds && bounds.length) {
    if (state.region === "All" && state.scope === "all" && !state.search && state.brand === "All") {
      state.map.setView([20.0, 20.0], 2, { animate: false });
    } else if (bounds.length === 1) {
      state.map.setView(bounds[0], 11, { animate: true });
    } else {
      state.map.fitBounds(bounds, { padding: [36, 36], maxZoom: 11, animate: true });
    }
  }
}

function renderScorecards(hotels) {
  const grid = qs("#scorecardGrid");
  const tableWrap = qs("#scorecardTableWrap");
  if (!grid || !tableWrap) return;

  if (!hotels.length) {
    grid.style.display = "";
    tableWrap.style.display = "none";
    grid.innerHTML = `<div class="empty-state">No hotels matched those filters. Try switching back to "All Luxury Hotels".</div>`;
    return;
  }

  const visible = hotels.slice(0, state.visibleLimit);
  const remaining = hotels.length - visible.length;

  if (state.viewMode === "table") {
    grid.style.display = "none";
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
          ${visible
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
                    <a class="btn btn-outline" style="padding:6px 10px;font-size:12px;" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates ↗</a>
                    <a class="tripadvisor-link" style="margin-left:4px;" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor ↗</a>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
      ${
        remaining > 0
          ? `<div style="display:flex;gap:12px;justify-content:center;padding:18px 0;">
              <button class="btn btn-primary" id="mapLoadMoreBtn" type="button">Show ${Math.min(PAGE_SIZE, remaining)} More (${visible.length} of ${hotels.length})</button>
              <button class="btn btn-outline" id="mapShowAllBtn" type="button">Show All ${hotels.length}</button>
            </div>`
          : ""
      }
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
        renderScorecards(getFilteredHotels());
      });
    });
  } else {
    grid.style.display = "";
    tableWrap.style.display = "none";

    const cardsHtml = visible
      .map((h) => {
        const o = getOdds(h);
        const reviewHref = getReviewHref(h);
        const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
        const s = h.scores;
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

        const bar = (lbl, val) => {
          if (val == null || Number.isNaN(Number(val))) return "";
          const pct = Math.round((Number(val) / 5) * 100);
          return `
            <div class="score-bar-row">
              <div class="score-bar-top"><span>${lbl}</span><strong>${formatPersonalScore(val)}/5</strong></div>
              <div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%"></div></div>
            </div>
          `;
        };

        const topAwardChip = (h.officialAwards || []).length
          ? `<a class="tag tag-teal" href="${escapeHtml(h.officialAwards[0].sourceUrl)}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">🏆 ${escapeHtml(h.officialAwards[0].label)} ↗</a>`
          : "";

        const editorialUrlSet = new Set((o.editorialRatings || []).map((e) => e.sourceUrl));
        const linkedReviewsHtml = [
          ...(h.officialAwards || []).map(
            (a) => `<a class="source-chip" href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">🏆 ${escapeHtml(a.label)} ↗</a>`
          ),
          ...(o.editorialRatings || []).map((e) => {
            const suffix = isScoreUnverified(e)
              ? " (unverified)"
              : e.rawScore
              ? ` (${escapeHtml(e.rawScore)})`
              : "";
            return `<a class="source-chip" href="${escapeHtml(e.sourceUrl)}" target="_blank" rel="noopener noreferrer">📰 ${escapeHtml(e.sourceName)}${suffix} ↗</a>`;
          }),
          ...(o.youtubeReviews || [])
            .filter((y) => !editorialUrlSet.has(y.sourceUrl))
            .slice(0, 2)
            .map(
              (y) =>
                `<a class="source-chip" href="${escapeHtml(y.sourceUrl)}" target="_blank" rel="noopener noreferrer">▶ ${escapeHtml(y.creatorName)} ↗</a>`
            ),
        ].join("");

        const takeawayLine = h.whereWeDiffer || h.standout || o.opinionGap.headline || "";

        return `
          <article class="scorecard-card ${trackCls}" data-resort-name="${escapeHtml(h.name)}">
            <div class="scorecard-media">
              <a href="${getSeoHref(h)}">
                <img src="${escapeHtml(resolveThumb(h.thumbnail))}" alt="${escapeHtml(h.name)}" loading="lazy" decoding="async" />
              </a>
              <div class="scorecard-badge-overall ${trackCls}">
                <strong>${
                  o.greatStayOdds != null
                    ? `${o.greatStayOdds}%`
                    : o.officialAwards.length
                    ? "Award"
                    : "Open"
                }</strong>
                <span>${o.scoreTrack === "verified" ? "Verified" : "Market Odds"}</span>
              </div>
              <button class="map-focus-btn" data-focus-id="${escapeHtml(h.id)}" type="button" title="Locate on map">
                📍 Map
              </button>
            </div>

            <div class="scorecard-body">
              <div class="meta-line">
                <span class="tag ${o.scoreTrack === "verified" ? "tag-accent" : "tag-slate"}">${escapeHtml(o.scoreTrackLabel)}</span>
                ${o.personalScoreLabel ? `<span class="tag tag-accent">My Stay ${escapeHtml(o.personalScoreLabel)}</span>` : ""}
                ${
                  o.founderVsMarketLabel
                    ? `<span class="founder-delta-pill ${deltaToneCls}">${escapeHtml(o.founderVsMarketLabel)}</span>`
                    : topAwardChip || (h.brand ? `<span class="tag">${escapeHtml(h.brand)}</span>` : "")
                }
                ${priceInfo.label ? `<span class="price-chip-indicative">${escapeHtml(priceInfo.label)}</span>` : ""}
              </div>
              <h3 class="scorecard-title"><a href="${getSeoHref(h)}">${escapeHtml(h.name)}</a></h3>
              <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)}${h.brand ? ` &bull; ${escapeHtml(h.brand)}` : ""}</div>

              ${
                o.firstHand && s
                  ? `<div class="score-bars-list">
                      ${bar("Value", s.value)}
                      ${bar("Room Quality", s.rooms)}
                      ${bar("Vibe / Layout", s.grounds)}
                      ${bar("Food", s.food)}
                      ${bar("Service", s.service)}
                    </div>`
                  : takeawayLine
                  ? `<p class="card-takeaway-line" style="margin:8px 0 10px;"><strong>${escapeHtml(o.opinionGap.title)}:</strong> ${escapeHtml(takeawayLine)}</p>`
                  : ""
              }

              ${
                o.firstHand && takeawayLine
                  ? `<p class="card-takeaway-line" style="margin:6px 0 10px;"><strong>My Take:</strong> ${escapeHtml(takeawayLine)}</p>`
                  : ""
              }

              <details class="card-details-expander" style="margin-bottom:12px;">
                <summary>Sources &amp; Details &#9662;</summary>
                <div class="card-details-body">
                  ${h.standout && h.standout !== takeawayLine ? `<div style="font-size:12.5px;margin-bottom:5px;"><strong>Standout:</strong> ${escapeHtml(h.standout)}</div>` : ""}
                  ${h.watchOut ? `<div style="font-size:12.5px;margin-bottom:6px;"><strong>Watch out:</strong> ${escapeHtml(h.watchOut)}</div>` : ""}
                  <div class="consensus-sources">
                    ${linkedReviewsHtml}
                    <a class="tripadvisor-link" href="${escapeHtml(getTripAdvisorUrl(h))}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
                  </div>
                </div>
              </details>

              <div class="scorecard-actions">
                <a class="btn btn-primary" href="${getSeoHref(h)}">Breakdown</a>
                ${
                  reviewHref
                    ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${h.coverageType === "Short Tour" ? "Short" : "Review"}</a>`
                    : `<a class="btn btn-outline" href="../compare/?a=${encodeURIComponent(h.id)}">VS</a>`
                }
                <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    const pagerHtml =
      remaining > 0
        ? `<div style="grid-column:1 / -1;display:flex;gap:12px;justify-content:center;padding:18px 0;flex-wrap:wrap;">
            <button class="btn btn-primary" id="mapLoadMoreBtn" type="button">Show ${Math.min(PAGE_SIZE, remaining)} More (${visible.length} of ${hotels.length} shown)</button>
            <button class="btn btn-outline" id="mapShowAllBtn" type="button">Show All ${hotels.length}</button>
          </div>`
        : "";

    grid.innerHTML = cardsHtml + pagerHtml;

    grid.querySelectorAll("[data-focus-id]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const marker = state.markerById.get(btn.dataset.focusId);
        if (marker && state.map) {
          qs("#hotelMap")?.scrollIntoView({ behavior: "smooth", block: "center" });
          state.map.setView(marker.getLatLng(), 11, { animate: true });
          setTimeout(() => marker.openPopup(), 350);
        }
      });
    });
  }

  qs("#mapLoadMoreBtn")?.addEventListener("click", () => {
    state.visibleLimit += PAGE_SIZE;
    renderScorecards(hotels);
  });
  qs("#mapShowAllBtn")?.addEventListener("click", () => {
    state.visibleLimit = hotels.length;
    renderScorecards(hotels);
  });
}

function renderHotelShorts(hotels) {
  const rail = qs("#hotelShortsRail");
  const sec = qs("#hotelShortsSection");
  if (!rail || !sec) return;
  const items = [];
  const seen = new Set();
  for (const h of hotels) {
    for (const sh of h.shorts || []) {
      if (!seen.has(sh.id)) {
        seen.add(sh.id);
        items.push({ ...sh, hotelName: h.name });
      }
    }
  }
  if (!items.length) {
    sec.style.display = "none";
    return;
  }
  sec.style.display = "";
  rail.innerHTML = items
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

function renderMapActiveFiltersAndBadge() {
  const badge = qs("#mapFilterCountBadge");
  const strip = qs("#mapActiveFiltersStrip");
  const chips = [];
  if (state.brand !== "All") chips.push({ key: "brand", label: `Brand: ${state.brand}` });
  if (state.coverage !== "All") chips.push({ key: "coverage", label: `Tier: ${state.coverage}` });
  if (state.profileFilter !== "all") {
    const mapP = { adults: "Adults-Only", family: "Family & Kids", preferred: "Preferred Perks", points: "Points Brands" };
    chips.push({ key: "profile", label: mapP[state.profileFilter] || state.profileFilter });
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
              `<button type="button" class="active-filter-chip" data-clear-map-filter="${escapeHtml(c.key)}">${escapeHtml(c.label)} &times;</button>`
          )
          .join("") +
        `<button type="button" class="btn-link-clear" id="mapStripClearAll">Clear all</button>`;

      strip.querySelectorAll("[data-clear-map-filter]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const k = btn.dataset.clearMapFilter;
          if (k === "brand") {
            state.brand = "All";
            const el = qs("#brandFilter");
            if (el) el.value = "All";
          } else if (k === "coverage") {
            state.coverage = "All";
            const el = qs("#coverageFilter");
            if (el) el.value = "All";
          } else if (k === "profile") {
            state.profileFilter = "all";
            const el = qs("#mapProfileFilter");
            if (el) el.value = "all";
          } else if (k === "style") {
            state.style = "all";
            renderStylePills();
          } else if (k === "month") {
            state.month = 0;
            window._renderMapMonthPills?.();
          }
          state.visibleLimit = PAGE_SIZE;
          syncUrlParams();
          renderAll(true);
        });
      });
      strip.querySelector("#mapStripClearAll")?.addEventListener("click", () => {
        qs("#mapClearDrawerFiltersBtn")?.click();
      });
    }
  }
}

function renderAll(fitBounds = false) {
  renderMapActiveFiltersAndBadge();
  const filtered = getFilteredHotels();
  const badge = qs("#hotelCountBadge");
  if (badge) {
    badge.textContent = `${filtered.length} Mapped Hotel${filtered.length === 1 ? "" : "s"}`;
  }
  renderMapMarkers(filtered, fitBounds);
  renderScorecards(filtered);
  renderHotelShorts(filtered);
}

async function boot() {
  initCommonUi();
  initMap();

  const params = new URLSearchParams(window.location.search);
  if (["all", "visited", "global", "michelin", "w50"].includes(params.get("scope"))) {
    state.scope = params.get("scope");
  }

  const mapDrawerBtn = qs("#mapMoreFiltersBtn");
  const mapDrawerEl = qs("#mapMoreFiltersDrawer");
  if (mapDrawerBtn && mapDrawerEl) {
    mapDrawerBtn.addEventListener("click", () => {
      const nextHidden = !mapDrawerEl.hidden;
      mapDrawerEl.hidden = nextHidden;
      mapDrawerBtn.setAttribute("aria-expanded", String(!nextHidden));
      mapDrawerBtn.classList.toggle("is-open", !nextHidden);
    });
  }
  qs("#mapClearDrawerFiltersBtn")?.addEventListener("click", () => {
    state.brand = "All";
    state.coverage = "All";
    state.profileFilter = "all";
    state.style = "all";
    state.month = 0;
    const bf = qs("#brandFilter");
    if (bf) bf.value = "All";
    const cf = qs("#coverageFilter");
    if (cf) cf.value = "All";
    const pf = qs("#mapProfileFilter");
    if (pf) pf.value = "all";
    state.visibleLimit = PAGE_SIZE;
    syncUrlParams();
    renderStylePills();
    window._renderMapMonthPills?.();
    renderAll(true);
  });

  qs("#brandFilter")?.addEventListener("change", (e) => {
    state.brand = e.target.value || "All";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `brand:${state.brand}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderAll(true);
  });
  qs("#coverageFilter")?.addEventListener("change", (e) => {
    state.coverage = e.target.value || "All";
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `coverage:${state.coverage}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderAll(true);
  });
  qs("#sortControl")?.addEventListener("change", (e) => {
    state.sortBy = e.target.value || "stayodds";
    state.tableSortKey = null;
    if (typeof window.trackEvent === "function") {
      window.trackEvent("use_filter", "filter", `sort:${state.sortBy}`);
    }
    state.visibleLimit = PAGE_SIZE;
    renderAll(false);
  });
  let searchTimer = null;
  qs("#hotelSearch")?.addEventListener("input", (e) => {
    state.search = e.target.value || "";
    state.visibleLimit = PAGE_SIZE;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => renderAll(false), 120);
  });
  qs("#mapProfileFilter")?.addEventListener("change", (e) => {
    state.profileFilter = e.target.value || "all";
    state.visibleLimit = PAGE_SIZE;
    renderAll(true);
  });
  qs("#mapExportCsvBtn")?.addEventListener("click", () => {
    const list = getFilteredHotels();
    if (!list.length) return;
    exportHotelsToCsv(
      list,
      getOdds,
      { getMichelinKeyCount, getW50BestRank, getForbesRank },
      "stayodds-hotel-map.csv"
    );
  });
  qs("#viewCardsBtn")?.addEventListener("click", () => {
    state.viewMode = "cards";
    qs("#viewCardsBtn")?.classList.add("active");
    qs("#viewTableBtn")?.classList.remove("active");
    renderScorecards(getFilteredHotels());
  });
  qs("#viewTableBtn")?.addEventListener("click", () => {
    state.viewMode = "table";
    qs("#viewTableBtn")?.classList.add("active");
    qs("#viewCardsBtn")?.classList.remove("active");
    renderScorecards(getFilteredHotels());
  });

  function renderMapMonthPills() {
    const container = qs("#mapMonthPills");
    if (!container) return;
    const base = getScopedHotels().filter((h) => state.region === "All" || h.region === state.region);
    container.innerHTML = [
      `<button class="feature-pill month-pill ${state.month === 0 ? "active" : ""}" data-month="0" type="button">All Months (${base.length})</button>`,
      ...MONTH_LABELS.map((lbl, idx) => {
        const m = idx + 1;
        const cnt = base.filter((h) => matchesBestMonth(h, m)).length;
        return `<button class="feature-pill month-pill ${state.month === m ? "active" : ""}" data-month="${m}" type="button">${lbl} (${cnt})</button>`;
      }),
    ].join("");
    container.querySelectorAll("[data-month]").forEach((btn) => {
      btn.addEventListener("click", () => {
        state.month = Number(btn.dataset.month || 0);
        state.visibleLimit = PAGE_SIZE;
        renderMapMonthPills();
        renderAll(true);
      });
    });
  }
  window._renderMapMonthPills = renderMapMonthPills;

  try {
    const IDX_CACHE_KEY = "stayodds_index_cache_v20261124c";
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
      const res = await fetch(`../data/stayodds-index.json?v=20261124c`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      payload = await res.json();
      try {
        localStorage.setItem(IDX_CACHE_KEY, JSON.stringify({ ts: Date.now(), data: payload }));
      } catch (_) {}
    }
    state.hotels = payload.hotels || [];

    const matchedRegion = matchRegionParam(params.get("region"), getScopedHotels());
    if (matchedRegion) {
      state.region = matchedRegion;
    }

    const styleParam = params.get("style");
    if (styleParam && TRAVEL_STYLES.some((s) => s.id === styleParam)) state.style = styleParam;
    const monthParam = Number(params.get("month") || 0);
    if (monthParam >= 1 && monthParam <= 12) state.month = monthParam;
    renderScopeTabs();
    renderRegionPills();
    renderStylePills();
    renderMapMonthPills();
    populateBrands();
    renderAll(true);
  } catch (err) {
    const grid = qs("#scorecardGrid");
    if (grid) grid.innerHTML = `<div class="empty-state">Unable to load the hotel world map right now.</div>`;
    console.error("Failed to load stayodds-index.json:", err);
  }
}

boot();
