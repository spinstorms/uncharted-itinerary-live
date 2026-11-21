import {
  BRAND,
  computeStayOdds,
  formatPersonalScore,
  isFirstHandVerified,
  isVisitedProperty,
} from "./stayodds-engine.js?v=1";

const state = {
  hotels: [],
  visitedCount: 0,
  worldCount: 0,
  scope: "all", // "all" | "visited" | "world"
  region: "All",
  verdict: "All",
  sortBy: "visited",
  search: "",
  idA: "taaktana-labuan-bajo",
  idB: "ritz-carlton-bali",
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

function populateH2HSelectors() {
  const selA = qs("#compareSelectA");
  const selB = qs("#compareSelectB");
  if (!selA || !selB) return;

  const visited = state.hotels.filter(isVisitedProperty);
  const globalOnly = state.hotels.filter((h) => !isVisitedProperty(h));

  const renderOpt = (h) =>
    `<option value="${escapeHtml(h.id)}">${escapeHtml(h.name)} (${escapeHtml(h.location)}, ${escapeHtml(h.country)})</option>`;

  const opts = `
    <optgroup label="★ First-Hand Stays &amp; Shorts (${visited.length})">
      ${visited.map(renderOpt).join("")}
    </optgroup>
    <optgroup label="🌍 Global Luxury Directory (${globalOnly.length})">
      ${globalOnly.map(renderOpt).join("")}
    </optgroup>
  `;
  selA.innerHTML = opts;
  selB.innerHTML = opts;

  if (state.hotels.some((h) => h.id === state.idA)) selA.value = state.idA;
  else if (visited.length) {
    state.idA = visited[0].id;
    selA.value = state.idA;
  }
  if (state.hotels.some((h) => h.id === state.idB)) selB.value = state.idB;
  else if (state.hotels.length > 1) {
    state.idB = state.hotels[1].id;
    selB.value = state.idB;
  }
}

function renderH2HCard(h, opponent) {
  const o = computeStayOdds(h);
  const oo = computeStayOdds(opponent);
  const s = h.scores || {};
  const os = opponent.scores || {};
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  const metricRow = (label, a, b, suffix = "", missingText = "Pending live data") => {
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

  const guestLabel = o.verifiedGuest
    ? `${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}`
    : null;
  const oppGuestLabel = oo.verifiedGuest
    ? `${oo.verifiedGuest.rating.toFixed(1)} / ${oo.verifiedGuest.scale}`
    : null;

  const unratedLabel = o.visited ? "Short Tour (Unrated)" : "Not Visited Yet";

  return `
    <article class="h2h-card">
      <div class="h2h-card-head">
        <img src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div>
          <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${escapeHtml(o.tierLabel)}</span>
          <h3><a class="consensus-title-link" href="./hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a></h3>
          <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)}${h.priceRange ? ` &bull; ${escapeHtml(h.priceRange)}` : ""}</div>
        </div>
      </div>

      <div class="h2h-odds-strip">
        <div class="odds-big">
          <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : "—"}</strong>
          <span>${escapeHtml(o.statusBadge)}</span>
        </div>
        <div class="index-big">
          <strong>${o.overallIndex != null ? `${o.overallIndex}<span>/100</span>` : "Pending"}</strong>
          <span>${escapeHtml(BRAND.name)} Index</span>
        </div>
      </div>

      <div class="h2h-metrics-list">
        ${metricRow("First-Hand Verified Score", o.firstHand ? formatPersonalScore(h.overall) : null, oo.firstHand ? formatPersonalScore(opponent.overall) : null, " / 5", unratedLabel)}
        ${metricRow("Live Verified Guests", o.guest100 != null ? guestLabel : null, oo.guest100 != null ? oppGuestLabel : null, "", "Phase 1B Live API")}
        ${metricRow("Sourced Editorial Critics", o.critic100, oo.critic100, " / 100", "0 linked yet")}
        ${metricRow("Rooms & Villas", o.firstHand ? formatPersonalScore(s.rooms) : null, oo.firstHand ? formatPersonalScore(os.rooms) : null, " / 5", unratedLabel)}
        ${metricRow("Grounds & Pools", o.firstHand ? formatPersonalScore(s.grounds) : null, oo.firstHand ? formatPersonalScore(os.grounds) : null, " / 5", unratedLabel)}
        ${metricRow("Food & Breakfast", o.firstHand ? formatPersonalScore(s.food) : null, oo.firstHand ? formatPersonalScore(os.food) : null, " / 5", unratedLabel)}
        ${metricRow("Service", o.firstHand ? formatPersonalScore(s.service) : null, oo.firstHand ? formatPersonalScore(os.service) : null, " / 5", unratedLabel)}
        ${metricRow("Value for Money", o.firstHand ? formatPersonalScore(s.value) : null, oo.firstHand ? formatPersonalScore(os.value) : null, " / 5", unratedLabel)}
      </div>

      <p class="h2h-diff"><strong>Formula:</strong> ${escapeHtml(o.formulaSummary)}</p>

      <div class="scorecard-actions">
        <a class="btn btn-primary" href="./hotel/?id=${encodeURIComponent(h.id)}">Full Breakdown &rarr;</a>
        ${
          reviewHref
            ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${h.coverageType === "Short Tour" ? "Watch Short" : "Watch Review"}</a>`
            : ""
        }
        <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
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
}

function getScopedHotels() {
  if (state.scope === "visited") return state.hotels.filter(isVisitedProperty);
  if (state.scope === "world") return state.hotels.filter((h) => !isVisitedProperty(h));
  return state.hotels;
}

function renderScopeTabs() {
  const container = qs("#stayOddsScopeTabs");
  if (!container) return;
  const tabs = [
    { id: "all", label: `All Luxury Properties (${state.hotels.length})` },
    { id: "visited", label: `First-Hand Verified & Shorts (${state.visitedCount})` },
    { id: "world", label: `Global Directory (${state.worldCount})` },
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
      state.region = "All";
      renderScopeTabs();
      renderRegionPills();
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
      renderRegionPills();
      renderLeaderboard();
    });
  });
}

function renderLeaderboard() {
  const container = qs("#consensusList");
  if (!container) return;

  const q = state.search.trim().toLowerCase();
  const list = getScopedHotels().filter((h) => {
    const o = computeStayOdds(h);
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.verdict !== "All" && o.statusBadge !== state.verdict) return false;
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
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  list.sort((a, b) => {
    const oa = computeStayOdds(a);
    const ob = computeStayOdds(b);
    if (state.sortBy === "name") return a.name.localeCompare(b.name);
    if (state.sortBy === "odds") {
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
    }
    // Default: First-Hand Verified first, then Short Tours, then Global Directory
    const rank = (o) => (o.firstHand ? 2 : o.visited ? 1 : 0);
    if (rank(ob) !== rank(oa)) return rank(ob) - rank(oa);
    return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1) || a.name.localeCompare(b.name);
  });

  if (!list.length) {
    container.innerHTML = `<div class="empty-state">No resorts matched your filters. Try switching to "All Luxury Properties" or clearing your search.</div>`;
    return;
  }

  container.innerHTML = list
    .map((h, i) => {
      const o = computeStayOdds(h);
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

      return `
        <article class="consensus-row-card ${toneClass}">
          <div class="consensus-rank-col">
            <span class="consensus-rank-num">#${i + 1}</span>
            <div class="consensus-chance-ring ${toneClass}">
              <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : "—"}</strong>
              <span>${o.greatStayOdds != null ? "StayOdds" : "Live API Pending"}</span>
            </div>
            <div class="consensus-index-chip">
              ${o.sourceCount > 0 ? `<strong>${o.sourceCount}</strong> verified layer${o.sourceCount === 1 ? "" : "s"}` : "Global Metadata"}
            </div>
          </div>

          <div class="consensus-main-col">
            <div class="meta-line">
              <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${escapeHtml(o.tierLabel)}</span>
              <span class="tag ${tagClass}">${escapeHtml(o.statusBadge)}</span>
              ${shortCount ? `<span class="tag">${shortCount} Short${shortCount === 1 ? "" : "s"}</span>` : ""}
              ${h.brand ? `<span class="tag">${escapeHtml(h.brand)}</span>` : ""}
              <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
              ${h.priceRange ? `<span>&bull;</span><span>${escapeHtml(h.priceRange)}</span>` : ""}
            </div>

            <h3 class="consensus-title">
              <a class="consensus-title-link" href="./hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a>
            </h3>

            <div class="three-pillar-strip">
              <div class="pillar-box is-ours">
                <small>First-Hand (${o.weights.firstHand}%)</small>
                <strong>${o.firstHand ? `${formatPersonalScore(h.overall)} / 5` : o.visited ? "Short Preview" : "Not Visited"}</strong>
              </div>
              <div class="pillar-box is-critics">
                <small>Sourced Critics (${o.weights.critics}%)</small>
                <strong>${o.critic100 != null ? `${o.critic100} / 100` : "0 linked"}</strong>
              </div>
              <div class="pillar-box is-google">
                <small>Live Guests (${o.weights.guests}%)</small>
                <strong>${o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}` : "Phase 1B API"}</strong>
              </div>
              <div class="pillar-box is-booking">
                <small>Linked Videos</small>
                <strong>${(reviewHref ? 1 : 0) + o.youtubeReviews.length} video${(reviewHref ? 1 : 0) + o.youtubeReviews.length === 1 ? "" : "s"}</strong>
              </div>
            </div>

            <div class="consensus-compare-notes">
              <p><strong>${o.firstHand ? "First-Hand Verdict:" : "Property Overview:"}</strong> ${escapeHtml(h.verdict || h.standout || "")}</p>
              ${h.watchOut ? `<p><strong>Watch-Out:</strong> ${escapeHtml(h.watchOut)}</p>` : ""}
            </div>

            <div class="consensus-sources">
              <span class="source-chip">${escapeHtml(o.formulaSummary)}</span>
              ${o.officialAwards.map((a) => `<a class="source-chip" href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.label)} ↗</a>`).join("")}
            </div>
          </div>

          <div class="consensus-cta-col">
            <a href="./hotel/?id=${encodeURIComponent(h.id)}">
              <img class="consensus-thumb" src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" loading="lazy" />
            </a>
            <a class="btn btn-primary" href="./hotel/?id=${encodeURIComponent(h.id)}">Full Breakdown &rarr;</a>
            ${
              reviewHref
                ? `<a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Short" : "Watch Our Review"}</a>`
                : ""
            }
            <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &nearr;</a>
            <button class="copy-link-btn" data-compare-id="${escapeHtml(h.id)}" type="button">Compare Above &uarr;</button>
          </div>
        </article>
      `;
    })
    .join("");

  // Populate Quick Hotel Shorts rail from all filtered stays
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
              <img src="https://i.ytimg.com/vi/${encodeURIComponent(sh.id)}/hqdefault.jpg" alt="${escapeHtml(sh.title)}" loading="lazy" />
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

  container.querySelectorAll("[data-compare-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = btn.dataset.compareId;
      if (!id) return;
      state.idB = state.idA;
      state.idA = id;
      const selA = qs("#compareSelectA");
      const selB = qs("#compareSelectB");
      if (selA) selA.value = state.idA;
      if (selB) selB.value = state.idB;
      renderH2H();
      qs(".h2h-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

async function boot() {
  initCommonUi();

  const params = new URLSearchParams(window.location.search);
  if (params.get("a")) state.idA = params.get("a");
  if (params.get("b")) state.idB = params.get("b");
  if (["all", "visited", "world"].includes(params.get("scope"))) {
    state.scope = params.get("scope");
  }

  qs("#compareSelectA")?.addEventListener("change", (e) => {
    state.idA = e.target.value;
    renderH2H();
  });
  qs("#compareSelectB")?.addEventListener("change", (e) => {
    state.idB = e.target.value;
    renderH2H();
  });
  qs("#verdictFilter")?.addEventListener("change", (e) => {
    state.verdict = e.target.value || "All";
    renderLeaderboard();
  });
  qs("#consensusSort")?.addEventListener("change", (e) => {
    state.sortBy = e.target.value || "visited";
    renderLeaderboard();
  });
  qs("#consensusSearch")?.addEventListener("input", (e) => {
    state.search = e.target.value || "";
    renderLeaderboard();
  });

  try {
    const bust = Date.now();
    const [resVisited, resWorld] = await Promise.all([
      fetch(`../data/hotels.json?v=${bust}`),
      fetch(`../data/world-hotels.json?v=${bust}`).catch(() => null),
    ]);
    if (!resVisited.ok) throw new Error(`HTTP ${resVisited.status}`);
    const visitedData = await resVisited.json();
    const worldData = resWorld && resWorld.ok ? await resWorld.json() : { hotels: [] };

    const visitedHotels = (visitedData.hotels || []).map((h) => ({ ...h, visitedByUs: true }));
    const visitedIds = new Set(visitedHotels.map((h) => h.id));
    const visitedNames = new Set(visitedHotels.map((h) => h.name.toLowerCase()));

    const worldHotels = (worldData.hotels || [])
      .filter((h) => !visitedIds.has(h.id) && !visitedNames.has((h.name || "").toLowerCase()))
      .map((h) => ({ ...h, visitedByUs: false }));

    state.visitedCount = visitedHotels.length;
    state.worldCount = worldHotels.length;
    state.hotels = [...visitedHotels, ...worldHotels];

    const ratedCount = visitedHotels.filter(isFirstHandVerified).length;
    const statEl = qs("#consensusSummaryStat");
    if (statEl) {
      statEl.textContent = `${ratedCount} First-Hand Verified • ${state.worldCount} Global Directory`;
    }

    populateH2HSelectors();
    renderH2H();
    renderScopeTabs();
    renderRegionPills();
    renderLeaderboard();
  } catch (err) {
    const el = qs("#consensusList");
    if (el) el.innerHTML = `<div class="empty-state">Unable to load ${escapeHtml(BRAND.name)} right now.</div>`;
    console.error("Failed to load StayOdds data:", err);
  }
}

boot();
