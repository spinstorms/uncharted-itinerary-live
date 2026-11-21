const state = {
  hotels: [],
  region: "All",
  verdict: "All",
  sortBy: "chance",
  search: "",
  idA: "ritz-carlton-bali",
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

function getReviewHref(h) {
  if (h.inLiveFeed && h.videoId) return `../?video=${encodeURIComponent(h.videoId)}`;
  if (h.videoId) return `https://www.youtube.com/watch?v=${encodeURIComponent(h.videoId)}`;
  return "https://www.uncharteditinerary.com/";
}

function isExternalReview(h) {
  return !(h.inLiveFeed && h.videoId);
}

function formatReviews(n) {
  const num = Number(n || 0);
  if (!num) return "Verified guests";
  return `${num.toLocaleString("en-GB")} reviews`;
}

function getConsensus(h) {
  if (h.consensus) return h.consensus;
  const ours = Number(h.overall || 4.2);
  const idx = Math.round(ours * 20);
  return {
    overallIndex: idx,
    greatStayChance: Math.min(95, idx),
    agreement: "Mostly Aligned",
    spread: 0.1,
    googleRating: ours,
    googleReviews: 0,
    criticScore: ours,
    award: h.brand || "Reviewed Stay",
    sources: ["The Uncharted Itinerary"],
    otherReviewersSay: "Benchmarked against our first-hand stay.",
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

  const opts = state.hotels
    .map((h) => `<option value="${escapeHtml(h.id)}">${escapeHtml(h.name)} (${escapeHtml(h.location)})</option>`)
    .join("");
  selA.innerHTML = opts;
  selB.innerHTML = opts;

  if (state.hotels.some((h) => h.id === state.idA)) selA.value = state.idA;
  if (state.hotels.some((h) => h.id === state.idB)) selB.value = state.idB;
  else if (state.hotels.length > 1) {
    state.idA = state.hotels[0].id;
    state.idB = state.hotels[1].id;
    selA.value = state.idA;
    selB.value = state.idB;
  }
}

function renderH2HCard(h, opponent) {
  const c = getConsensus(h);
  const oc = getConsensus(opponent);
  const s = h.scores || {};
  const os = opponent.scores || {};
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  const metricRow = (label, a, b, suffix = "") => {
    const wins = Number(a) > Number(b);
    return `
      <div class="h2h-metric ${wins ? "is-best" : ""}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(String(a))}${suffix} ${wins ? "★" : ""}</strong>
      </div>
    `;
  };

  return `
    <article class="h2h-card">
      <div class="h2h-card-head">
        <img src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div>
          <span class="tag tag-accent">${escapeHtml(c.award || h.brand || "")}</span>
          <h3><a class="consensus-title-link" href="./hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a></h3>
          <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)} &bull; ${escapeHtml(h.priceRange || "")}</div>
        </div>
      </div>

      <div class="h2h-odds-strip">
        <div class="odds-big">
          <strong>${c.greatStayChance}%</strong>
          <span>Chance of a Great Stay</span>
        </div>
        <div class="index-big">
          <strong>${c.overallIndex}<span>/100</span></strong>
          <span>Consensus Index</span>
        </div>
      </div>

      <div class="h2h-metrics-list">
        ${metricRow("Our First-Hand Score", Number(h.overall).toFixed(1), Number(opponent.overall).toFixed(1), " / 5")}
        ${metricRow("Booking.com Guests", Number(c.bookingOverall || c.googleRating * 2).toFixed(1), Number(oc.bookingOverall || oc.googleRating * 2).toFixed(1), " / 10")}
        ${metricRow("Google Guests", Number(c.googleRating).toFixed(1), Number(oc.googleRating).toFixed(1), " ★")}
        ${metricRow("Critics & YouTube", Number(c.criticScore).toFixed(1), Number(oc.criticScore).toFixed(1), " / 5")}
        ${metricRow("Rooms & Villas", Number(s.rooms || 0).toFixed(1), Number(os.rooms || 0).toFixed(1), " / 5")}
        ${metricRow("Food & Breakfast", Number(s.food || 0).toFixed(1), Number(os.food || 0).toFixed(1), " / 5")}
        ${metricRow("Service", Number(s.service || 0).toFixed(1), Number(os.service || 0).toFixed(1), " / 5")}
        ${metricRow("Value for Money", Number(s.value || 0).toFixed(1), Number(os.value || 0).toFixed(1), " / 5")}
      </div>

      <p class="h2h-diff"><strong>Our take vs. others:</strong> ${escapeHtml(c.whereWeDiffer)}</p>

      <div class="scorecard-actions">
        <a class="btn btn-primary" href="./hotel/?id=${encodeURIComponent(h.id)}">Full Breakdown &rarr;</a>
        <a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>Watch Review</a>
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

function renderRegionPills() {
  const container = qs("#consensusRegionPills");
  if (!container) return;
  const regions = ["All", ...Array.from(new Set(state.hotels.map((h) => h.region)))];
  container.innerHTML = regions
    .map(
      (r) =>
        `<button class="pill ${state.region === r ? "active" : ""}" data-region="${escapeHtml(
          r
        )}" role="tab">${escapeHtml(r)}</button>`
    )
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
  const list = state.hotels.filter((h) => {
    const c = getConsensus(h);
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.verdict !== "All" && c.agreement !== state.verdict) return false;
    if (!q) return true;
    const hay = [h.name, h.location, h.country, h.brand, c.award, c.otherReviewersSay, c.whereWeDiffer, ...(c.sources || [])]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  list.sort((a, b) => {
    const ca = getConsensus(a);
    const cb = getConsensus(b);
    if (state.sortBy === "index") return cb.overallIndex - ca.overallIndex || cb.greatStayChance - ca.greatStayChance;
    if (state.sortBy === "gap") return (cb.spread || 0) - (ca.spread || 0);
    if (state.sortBy === "reviews") return (cb.googleReviews || 0) - (ca.googleReviews || 0);
    return cb.greatStayChance - ca.greatStayChance || cb.overallIndex - ca.overallIndex;
  });

  if (!list.length) {
    container.innerHTML = `<div class="empty-state">No resorts matched your filters. Try resetting the verdict or region filter.</div>`;
    return;
  }

  container.innerHTML = list
    .map((h, i) => {
      const c = getConsensus(h);
      const reviewHref = getReviewHref(h);
      const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
      const isContrarian = c.agreement === "Contrarian Verdict";
      const isShortOnly = h.coverageType === "Short Tour";
      const shortCount = Array.isArray(h.shorts) ? h.shorts.length : 0;

      return `
        <article class="consensus-row-card">
          <div class="consensus-rank-col">
            <span class="consensus-rank-num">#${i + 1}</span>
            <div class="consensus-chance-ring ${isContrarian ? "is-caution" : ""}">
              <strong>${c.greatStayChance}%</strong>
              <span>Great-Stay Odds</span>
            </div>
            <div class="consensus-index-chip">Overall: <strong>${c.overallIndex}/100</strong></div>
          </div>

          <div class="consensus-main-col">
            <div class="meta-line">
              <span class="tag ${isContrarian ? "tag-caution" : "tag-accent"}">${escapeHtml(c.agreement)}</span>
              ${isShortOnly ? `<span class="tag">Short Tour</span>` : ""}
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
              <div class="pillar-box">
                <small>The Uncharted Itinerary</small>
                <strong>${Number(h.overall).toFixed(1)} / 5.0</strong>
              </div>
              <div class="pillar-box">
                <small>Booking.com Guests</small>
                <strong>${Number(c.bookingOverall || c.googleRating * 2).toFixed(1)} / 10</strong>
              </div>
              <div class="pillar-box">
                <small>Google (${escapeHtml(formatReviews(c.googleReviews))})</small>
                <strong>${Number(c.googleRating).toFixed(1)} / 5.0</strong>
              </div>
              <div class="pillar-box">
                <small>Critics &amp; YouTube</small>
                <strong>${Number(c.criticScore).toFixed(1)} / 5.0</strong>
              </div>
            </div>

            <div class="consensus-compare-notes">
              <p><strong>What top channels &amp; online reviewers say:</strong> ${escapeHtml(c.otherReviewersSay)}</p>
              <p><strong>Our stay vs. consensus:</strong> ${escapeHtml(c.whereWeDiffer)}</p>
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
            <a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Short" : "Watch Our Review"}</a>
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
    const res = await fetch(`../data/hotels.json?v=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.hotels = data.hotels || [];

    const statEl = qs("#consensusSummaryStat");
    if (statEl) {
      const totalReviews = state.hotels.reduce((acc, h) => acc + (h.consensus?.googleReviews || 0), 0);
      statEl.textContent = `${state.hotels.length} Resorts • ${totalReviews.toLocaleString("en-GB")}+ Guest Reviews`;
    }

    populateH2HSelectors();
    renderH2H();
    renderRegionPills();
    renderLeaderboard();
  } catch (err) {
    const el = qs("#consensusList");
    if (el) el.innerHTML = `<div class="empty-state">Unable to load consensus ratings right now.</div>`;
    console.error("Failed to load hotels.json:", err);
  }
}

boot();
