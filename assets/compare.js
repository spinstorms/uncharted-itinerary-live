const state = {
  hotels: [],
  visitedCount: 0,
  worldCount: 0,
  scope: "all", // "all" | "visited" | "world"
  region: "All",
  verdict: "All",
  sortBy: "chance",
  search: "",
  idA: "ritz-carlton-bali",
  idB: "bulgari-resort-bali",
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

function formatMyScore(val) {
  if (val == null || Number.isNaN(Number(val))) return null;
  const num = Number(val);
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

function isRatedHotel(h) {
  return h.overall != null && h.scores != null;
}

function isVisitedHotel(h) {
  return h.visitedByUs !== false && h.coverageType !== "Global Directory";
}

function formatReviews(n) {
  const num = Number(n || 0);
  if (!num) return "Verified guests";
  return `${num.toLocaleString("en-GB")} reviews`;
}

function getConsensus(h) {
  if (h.consensus) return h.consensus;
  const ours = h.overall != null ? Number(h.overall) : null;
  const idx = ours != null ? Math.round(ours * 20) : 90;
  return {
    overallIndex: idx,
    greatStayChance: Math.min(95, idx),
    agreement: ours != null ? "Mostly Aligned" : "Global StayScore",
    spread: ours != null ? 0.1 : null,
    oursIncluded: ours != null,
    googleRating: ours || 4.6,
    googleReviews: 0,
    criticScore: ours || 4.6,
    award: h.brand || "Luxury Stay",
    sources: ["StayScore"],
    otherReviewersSay: "Benchmarked against verified guest & critic ratings.",
    whereWeDiffer: "First-hand review from The Uncharted Itinerary.",
  };
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

  const visited = state.hotels.filter(isVisitedHotel);
  const globalOnly = state.hotels.filter((h) => !isVisitedHotel(h));

  const renderOpt = (h) =>
    `<option value="${escapeHtml(h.id)}">${escapeHtml(h.name)} (${escapeHtml(h.location)}, ${escapeHtml(h.country)})</option>`;

  const opts = `
    <optgroup label="★ Visited &amp; Filmed by Uncharted (${visited.length})">
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
  const c = getConsensus(h);
  const oc = getConsensus(opponent);
  const s = h.scores || {};
  const os = opponent.scores || {};
  const rated = isRatedHotel(h);
  const oppRated = isRatedHotel(opponent);
  const visited = isVisitedHotel(h);
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  const metricRow = (label, a, b, suffix = "", unratedText = "Not visited yet") => {
    const aMissing = a == null;
    const bMissing = b == null;
    const wins = !aMissing && !bMissing && Number(a) > Number(b);
    const display = aMissing ? unratedText : `${a}${suffix}`;
    return `
      <div class="h2h-metric ${wins ? "is-best" : ""}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(display)} ${wins ? "★" : ""}</strong>
      </div>
    `;
  };

  const unratedLabel = visited ? "Short (Unrated)" : "Not visited yet";
  const pendingAxis = visited ? "Pending full review" : "Global StayScore";

  return `
    <article class="h2h-card">
      <div class="h2h-card-head">
        <img src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div>
          <span class="tag ${visited ? "tag-accent" : "tag-slate"}">${visited ? "Visited by Uncharted" : "Global Directory"}</span>
          <h3><a class="consensus-title-link" href="./hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a></h3>
          <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)} &bull; ${escapeHtml(h.priceRange || "")}</div>
        </div>
      </div>

      <div class="h2h-odds-strip">
        <div class="odds-big">
          <strong>${c.greatStayChance}%</strong>
          <span>${rated ? "Chance of a Great Stay" : "Global Great-Stay Odds"}</span>
        </div>
        <div class="index-big">
          <strong>${c.overallIndex}<span>/100</span></strong>
          <span>StayScore Index</span>
        </div>
      </div>

      <div class="h2h-metrics-list">
        ${metricRow("Our First-Hand Score", rated ? formatMyScore(h.overall) : null, oppRated ? formatMyScore(opponent.overall) : null, " / 5", unratedLabel)}
        ${metricRow("Booking.com Guests", Number(c.bookingOverall || c.googleRating * 2).toFixed(1), Number(oc.bookingOverall || oc.googleRating * 2).toFixed(1), " / 10")}
        ${metricRow("Google Guests", Number(c.googleRating).toFixed(1), Number(oc.googleRating).toFixed(1), " ★")}
        ${metricRow("Critics & YouTube", Number(c.criticScore).toFixed(1), Number(oc.criticScore).toFixed(1), " / 5")}
        ${metricRow("Rooms & Villas", rated ? formatMyScore(s.rooms) : null, oppRated ? formatMyScore(os.rooms) : null, " / 5", pendingAxis)}
        ${metricRow("Food & Breakfast", rated ? formatMyScore(s.food) : null, oppRated ? formatMyScore(os.food) : null, " / 5", pendingAxis)}
        ${metricRow("Service", rated ? formatMyScore(s.service) : null, oppRated ? formatMyScore(os.service) : null, " / 5", pendingAxis)}
        ${metricRow("Value for Money", rated ? formatMyScore(s.value) : null, oppRated ? formatMyScore(os.value) : null, " / 5", pendingAxis)}
      </div>

      <p class="h2h-diff"><strong>${rated ? "Our take vs. others:" : "Why it stands out:"}</strong> ${escapeHtml(rated ? c.whereWeDiffer : h.standout || c.otherReviewersSay)}</p>

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
  if (state.scope === "visited") return state.hotels.filter(isVisitedHotel);
  if (state.scope === "world") return state.hotels.filter((h) => !isVisitedHotel(h));
  return state.hotels;
}

function renderScopeTabs() {
  const container = qs("#stayScoreScopeTabs");
  if (!container) return;
  const tabs = [
    { id: "all", label: `All Global Luxury (${state.hotels.length})` },
    { id: "visited", label: `Visited by Uncharted (${state.visitedCount})` },
    { id: "world", label: `Global Directory Only (${state.worldCount})` },
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
    const c = getConsensus(h);
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.verdict !== "All" && c.agreement !== state.verdict) return false;
    if (!q) return true;
    const hay = [h.name, h.location, h.country, h.region, h.brand, c.award, c.otherReviewersSay, c.whereWeDiffer, h.standout, ...(c.sources || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  list.sort((a, b) => {
    const ca = getConsensus(a);
    const cb = getConsensus(b);
    if (state.sortBy === "index") return cb.overallIndex - ca.overallIndex || cb.greatStayChance - ca.greatStayChance;
    if (state.sortBy === "gap") return (cb.spread ?? -1) - (ca.spread ?? -1);
    if (state.sortBy === "reviews") return (cb.googleReviews || 0) - (ca.googleReviews || 0);
    if (state.sortBy === "visited") {
      const av = isVisitedHotel(a) ? 1 : 0;
      const bv = isVisitedHotel(b) ? 1 : 0;
      if (bv !== av) return bv - av;
    }
    return cb.greatStayChance - ca.greatStayChance || cb.overallIndex - ca.overallIndex;
  });

  if (!list.length) {
    container.innerHTML = `<div class="empty-state">No resorts matched your filters. Try switching to "All Global Luxury" or clearing your search.</div>`;
    return;
  }

  container.innerHTML = list
    .map((h, i) => {
      const c = getConsensus(h);
      const reviewHref = getReviewHref(h);
      const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
      const isContrarian = c.agreement === "Contrarian Verdict";
      const isShortOnly = h.coverageType === "Short Tour";
      const visited = isVisitedHotel(h);
      const rated = isRatedHotel(h);
      const shortCount = Array.isArray(h.shorts) ? h.shorts.length : 0;
      const verdictClass = isContrarian
        ? "is-contrarian"
        : !rated || c.agreement === "External Consensus" || c.agreement === "Global StayScore"
        ? "is-external"
        : c.agreement === "Strong Consensus"
        ? "is-strong"
        : "is-aligned";
      const tagClass = isContrarian
        ? "tag-caution"
        : verdictClass === "is-strong"
        ? "tag-accent"
        : verdictClass === "is-aligned"
        ? "tag-teal"
        : "tag-slate";

      return `
        <article class="consensus-row-card ${verdictClass}">
          <div class="consensus-rank-col">
            <span class="consensus-rank-num">#${i + 1}</span>
            <div class="consensus-chance-ring ${verdictClass}">
              <strong>${c.greatStayChance}%</strong>
              <span>${rated ? "Great-Stay Odds" : "Global Odds"}</span>
            </div>
            <div class="consensus-index-chip">StayScore: <strong>${c.overallIndex}/100</strong></div>
          </div>

          <div class="consensus-main-col">
            <div class="meta-line">
              <span class="tag ${tagClass}">${escapeHtml(c.agreement)}</span>
              ${visited ? `<span class="tag tag-accent">Visited by Uncharted</span>` : `<span class="tag tag-slate">Global Directory</span>`}
              ${isShortOnly ? `<span class="tag">Short Tour · Unrated</span>` : ""}
              ${shortCount ? `<span class="tag">${shortCount} Short${shortCount === 1 ? "" : "s"}</span>` : ""}
              <span class="tag">${escapeHtml(c.award || h.brand || "")}</span>
              <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
              <span>&bull;</span>
              <span>${escapeHtml(h.priceRange || "")}</span>
            </div>

            <h3 class="consensus-title">
              <a class="consensus-title-link" href="./hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a>
            </h3>

            <div class="three-pillar-strip">
              <div class="pillar-box is-ours">
                <small>The Uncharted Itinerary</small>
                <strong>${rated ? `${formatMyScore(h.overall)} / 5` : visited ? "Short · Unrated" : "Not Visited Yet"}</strong>
              </div>
              <div class="pillar-box is-booking">
                <small>Booking.com Guests</small>
                <strong>${Number(c.bookingOverall || c.googleRating * 2).toFixed(1)} / 10</strong>
              </div>
              <div class="pillar-box is-google">
                <small>Google (${escapeHtml(formatReviews(c.googleReviews))})</small>
                <strong>${Number(c.googleRating).toFixed(1)} / 5.0</strong>
              </div>
              <div class="pillar-box is-critics">
                <small>Critics &amp; YouTube</small>
                <strong>${Number(c.criticScore).toFixed(1)} / 5.0</strong>
              </div>
            </div>

            <div class="consensus-compare-notes">
              <p><strong>What top channels &amp; online reviewers say:</strong> ${escapeHtml(c.otherReviewersSay)}</p>
              <p><strong>${rated ? "Our stay vs. consensus:" : visited ? "Our coverage status:" : "Standout & caveat:"}</strong> ${escapeHtml(rated || visited ? c.whereWeDiffer : `${h.standout} — Watch out: ${h.watchOut}`)}</p>
            </div>

            <div class="consensus-sources">
              ${(c.sources || []).map((src) => `<span class="source-chip">${escapeHtml(src)}</span>`).join("")}
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
            <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Rates &nearr;</a>
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
    state.sortBy = e.target.value || "chance";
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

    const statEl = qs("#consensusSummaryStat");
    if (statEl) {
      const totalReviews = state.hotels.reduce((acc, h) => acc + (h.consensus?.googleReviews || 0), 0);
      statEl.textContent = `${state.hotels.length} Global Luxury Hotels • ${totalReviews.toLocaleString("en-GB")}+ Reviews`;
    }

    populateH2HSelectors();
    renderH2H();
    renderScopeTabs();
    renderRegionPills();
    renderLeaderboard();
  } catch (err) {
    const el = qs("#consensusList");
    if (el) el.innerHTML = `<div class="empty-state">Unable to load StayScore ratings right now.</div>`;
    console.error("Failed to load StayScore data:", err);
  }
}

boot();
