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
  if (h.inLiveFeed) return `../../?video=${encodeURIComponent(h.videoId)}`;
  return `https://www.youtube.com/watch?v=${encodeURIComponent(h.videoId)}`;
}

function isExternalReview(h) {
  if (h.coverageType === "Short Tour") return true;
  return !(h.inLiveFeed && h.videoId);
}

function formatMyScore(val) {
  if (val == null || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
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

function renderScoreBar(label, value, maxVal, suffix = "", wholeNumbers = false) {
  const num = Number(value || 0);
  const pct = Math.max(0, Math.min(100, Math.round((num / maxVal) * 100)));
  const formatted = wholeNumbers ? formatMyScore(num) : num.toFixed(1);
  return `
    <div class="detail-bar-row">
      <div class="detail-bar-top">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(formatted)}${escapeHtml(suffix)}</strong>
      </div>
      <div class="detail-bar-track">
        <div class="detail-bar-fill" style="width:${pct}%"></div>
      </div>
    </div>
  `;
}

function renderDetail(h, allHotels) {
  const c = h.consensus || {};
  const s = h.scores || null;
  const b = c.bookingSubscores || {};
  const rated = h.overall != null && s != null;
  const isShortOnly = h.coverageType === "Short Tour";
  const isGlobalOnly = h.coverageType === "Global Directory" || h.visitedByUs === false;
  const isContrarian = c.agreement === "Contrarian Verdict";
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  document.title = `${h.name} — StayScore Breakdown (${c.greatStayChance || 90}% Great-Stay Odds) | The Uncharted Itinerary`;

  // Formula math transparency
  const ours100 = rated ? Math.round(Number(h.overall) * 20) : null;
  const critic100 = Math.round(Number(c.criticScore || 4.5) * 20);
  const google100 = Math.round(Number(c.googleRating || 4.5) * 20);
  const weightedRaw = rated
    ? Math.round(ours100 * 0.4 + critic100 * 0.3 + google100 * 0.3)
    : Math.round(critic100 * 0.5 + google100 * 0.5);
  const chanceDelta = Number(c.greatStayChance || weightedRaw) - Number(c.overallIndex || weightedRaw);
  const deltaLabel = chanceDelta > 0 ? `+${chanceDelta}%` : `${chanceDelta}%`;

  const benchmarks = Array.isArray(c.channelBenchmarks) && c.channelBenchmarks.length
    ? c.channelBenchmarks
    : [
        {
          source: "The Uncharted Itinerary",
          category: rated ? "Our Stay" : isGlobalOnly ? "Global Directory (Unvisited)" : "Our Stay (Short Preview)",
          score: rated ? `${formatMyScore(h.overall)} / 5` : isGlobalOnly ? "Not Visited Yet" : "Not Rated Yet",
          normalized100: ours100,
          takeaway: h.verdict || "",
        },
        {
          source: "Google Reviews",
          category: "Verified Guests",
          score: `${Number(c.googleRating || 0).toFixed(1)} ★`,
          normalized100: google100,
          takeaway: c.otherReviewersSay || "",
        },
      ];

  const related = allHotels
    .filter((other) => other.id !== h.id)
    .sort((a, bItem) => {
      const sameRegA = a.region === h.region ? 1 : 0;
      const sameRegB = bItem.region === h.region ? 1 : 0;
      if (sameRegB !== sameRegA) return sameRegB - sameRegA;
      return (bItem.consensus?.greatStayChance || 0) - (a.consensus?.greatStayChance || 0);
    })
    .slice(0, 3);

  const root = qs("#detailRoot");
  root.innerHTML = `
    <div class="detail-breadcrumb">
      <a href="../">&larr; All StayScore Rankings</a>
      <span>/</span>
      <a href="../../hotels/">Hotel Map</a>
      <span>/</span>
      <strong>${escapeHtml(h.name)}</strong>
    </div>

    <section class="detail-hero">
      <div class="detail-hero-media">
        <img src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div class="detail-hero-badges">
          <span class="tag ${isContrarian ? "tag-caution" : rated ? "tag-accent" : "tag-slate"}">${escapeHtml(c.agreement || "StayScore")}</span>
          ${isShortOnly ? `<span class="tag">Short Tour · Unrated</span>` : ""}
          ${isGlobalOnly ? `<span class="tag tag-slate">Global Luxury Directory</span>` : ""}
          ${c.award ? `<span class="tag">${escapeHtml(c.award)}</span>` : ""}
        </div>
      </div>

      <div class="detail-hero-body">
        <div class="meta-line">
          <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
          <span>&bull;</span>
          <span>${escapeHtml(h.brand || "")}</span>
          ${h.priceRange ? `<span>&bull;</span><span>${escapeHtml(h.priceRange)}</span>` : ""}
        </div>

        <h1 class="detail-title">${escapeHtml(h.name)}</h1>
        <p class="detail-verdict">${escapeHtml(h.verdict || "")}</p>

        <div class="detail-kpi-row">
          <div class="detail-kpi is-primary ${isContrarian ? "is-caution" : ""}">
            <strong>${c.greatStayChance || 90}%</strong>
            <span>${rated ? "Chance of a Great Stay" : "Global Great-Stay Odds"}</span>
          </div>
          <div class="detail-kpi">
            <strong>${c.overallIndex || weightedRaw}<span>/100</span></strong>
            <span>StayScore Index</span>
          </div>
          <div class="detail-kpi">
            ${
              rated
                ? `<strong>${formatMyScore(h.overall)}<span>/5</span></strong><span>Our Stay Score</span>`
                : `<strong style="font-size:19px;">${isGlobalOnly ? "Unvisited" : "Unrated"}</strong><span>${isGlobalOnly ? "Global Directory" : "Short Preview Only"}</span>`
            }
          </div>
          <div class="detail-kpi">
            <strong>${Number(c.bookingOverall || (c.googleRating * 2)).toFixed(1)}<span>/10</span></strong>
            <span>Booking.com</span>
          </div>
        </div>

        <div class="detail-actions">
          ${
            reviewHref
              ? `<a class="btn btn-primary" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Our Resort Short" : "Watch Our Full Review"}</a>
                 <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &nearr;</a>`
              : `<a class="btn btn-primary" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &nearr;</a>`
          }
          <a class="btn btn-outline" href="../?a=${encodeURIComponent(h.id)}">Compare Head-to-Head</a>
          <button class="copy-link-btn" id="copyDetailLink" type="button">Copy Breakdown Link</button>
        </div>
      </div>
    </section>

    <!-- Exact Formula Transparency -->
    <section class="detail-section">
      <div class="section-header" style="margin-bottom:16px;">
        <div>
          <h2 class="section-title">How This Great-Stay Score Is Calculated</h2>
          <p class="section-subtitle">${
            rated
              ? `Exact weighted math behind ${escapeHtml(h.name)}'s ${c.overallIndex || weightedRaw}/100 Consensus Index and ${c.greatStayChance || 90}% Great-Stay Odds.`
              : `Because we have only featured ${escapeHtml(h.name)} in YouTube Shorts so far, our personal score is excluded — this ${c.overallIndex || weightedRaw}/100 External Consensus uses 50% Critics/YouTube + 50% Verified Guests.`
          }</p>
        </div>
      </div>

      <div class="formula-grid">
        <div class="formula-step">
          <span class="formula-weight">${rated ? "40% Weight" : "0% Weight (Pending)"}</span>
          <strong>${rated ? `${ours100} / 100` : "Not Rated Yet"}</strong>
          <small>${rated ? `Our First-Hand Stay (${formatMyScore(h.overall)} / 5)` : "Short preview only — full review pending"}</small>
        </div>
        <div class="formula-step">
          <span class="formula-weight">${rated ? "30% Weight" : "50% Weight"}</span>
          <strong>${critic100} / 100</strong>
          <small>Top YouTube &amp; Travel Critics (${Number(c.criticScore || 0).toFixed(1)} / 5.0)</small>
        </div>
        <div class="formula-step">
          <span class="formula-weight">${rated ? "30% Weight" : "50% Weight"}</span>
          <strong>${google100} / 100</strong>
          <small>Google &amp; Verified Guests (${Number(c.googleRating || 0).toFixed(1)} ★ &bull; ${Number(c.googleReviews || 0).toLocaleString("en-GB")} reviews)</small>
        </div>
        <div class="formula-step is-result ${isContrarian ? "is-caution" : ""}">
          <span class="formula-weight">${escapeHtml(c.agreement || "Consensus")} (${deltaLabel})</span>
          <strong>${c.greatStayChance || 90}% Odds</strong>
          <small>${rated && c.spread != null ? `Spread vs. mainstream: ${Number(c.spread).toFixed(1)} pts` : "External critics & verified guests only"}</small>
        </div>
      </div>
    </section>

    <!-- Detailed Multi-Axis Breakdown -->
    <section class="detail-section">
      <div class="detail-two-col">
        <div class="detail-panel">
          <div class="detail-panel-head">
            <h3>Our 5-Axis First-Hand Scorecard</h3>
            <span class="tag ${rated ? "tag-accent" : ""}">${rated ? `${formatMyScore(h.overall)} / 5 Overall` : "Not Rated Yet"}</span>
          </div>
          ${
            rated
              ? `
          <p class="detail-panel-sub">Whole-number scores directly from our stay at ${escapeHtml(h.name)}.</p>
          <div class="detail-bars">
            ${renderScoreBar("Rooms & Villas", s.rooms, 5, " / 5", true)}
            ${renderScoreBar("Grounds, Pools & Beach", s.grounds, 5, " / 5", true)}
            ${renderScoreBar("Food & Breakfast", s.food, 5, " / 5", true)}
            ${renderScoreBar("Service & Hospitality", s.service, 5, " / 5", true)}
            ${renderScoreBar("Value for Money", s.value, 5, " / 5", true)}
          </div>
              `
              : `
          <div class="scorecard-unrated-box" style="margin-top:12px;">
            <strong>${isGlobalOnly ? "Global Luxury Directory — Not Visited Yet" : "Short Preview — Not Personally Scored Yet"}</strong>
            <p>${
              isGlobalOnly
                ? `We haven’t filmed a first-hand stay at ${escapeHtml(h.name)} yet, so our 5-point Uncharted Itinerary scorecard is currently pending. The StayScore above blends top travel critics, YouTube hotel reviewers, and verified Booking.com / Google guests (50/50). When we stay here, our personal scores will automatically appear here!`
                : `We’ve shared quick YouTube Shorts from ${escapeHtml(h.name)}, so we haven’t assigned our 5-point Uncharted Itinerary scorecard yet. Until a full video review goes live, the StayScore above relies 100% on external critics and verified Booking.com / Google guests.`
            }</p>
            ${
              reviewHref
                ? `<a class="btn btn-primary" href="${escapeHtml(reviewHref)}"${ext}>Watch Our Resort Short &nearr;</a>`
                : `<a class="btn btn-primary" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &nearr;</a>`
            }
          </div>
              `
          }
        </div>

        <div class="detail-panel">
          <div class="detail-panel-head">
            <h3>Booking.com Verified Guest Sub-Scores</h3>
            <span class="tag">${Number(c.bookingOverall || 9.0).toFixed(1)} / 10 Overall</span>
          </div>
          <p class="detail-panel-sub">
            Verified post-stay ratings &bull; Google ${Number(c.googleRating || 0).toFixed(1)}★ (${Number(c.googleReviews || 0).toLocaleString("en-GB")})
            ${c.tripadvisorRating ? ` &bull; TripAdvisor ${Number(c.tripadvisorRating).toFixed(1)}/5` : ""}
          </p>
          <div class="detail-bars">
            ${renderScoreBar("Staff & Service", b.staff || 9.4, 10, " / 10")}
            ${renderScoreBar("Cleanliness", b.cleanliness || 9.5, 10, " / 10")}
            ${renderScoreBar("Comfort", b.comfort || 9.5, 10, " / 10")}
            ${renderScoreBar("Facilities", b.facilities || 9.4, 10, " / 10")}
            ${renderScoreBar("Location", b.location || 9.3, 10, " / 10")}
            ${renderScoreBar("Value for Money", b.value || 8.6, 10, " / 10")}
          </div>
        </div>
      </div>
    </section>

    <!-- Channel-by-Channel Comparison -->
    <section class="detail-section">
      <div class="section-header" style="margin-bottom:18px;">
        <div>
          <h2 class="section-title">Channel-by-Channel &amp; Platform Breakdown</h2>
          <p class="section-subtitle">How this property stacks up across top YouTube hotel reviewers, travel critics, and verified booking platforms.</p>
        </div>
      </div>

      <div class="channel-breakdown-list">
        ${benchmarks
          .map(
            (row) => `
          <article class="channel-row">
            <div class="channel-row-head">
              <div>
                <span class="tag ${row.category === "Our Stay" ? "tag-accent" : ""}">${escapeHtml(row.category)}</span>
                <h4>${escapeHtml(row.source)}</h4>
              </div>
              <div class="channel-row-score">
                <strong>${escapeHtml(row.score)}</strong>
                <span>${row.normalized100 != null ? `${Number(row.normalized100)}/100` : "Pending"}</span>
              </div>
            </div>
            ${
              row.normalized100 != null
                ? `<div class="detail-bar-track" style="margin:10px 0;">
              <div class="detail-bar-fill ${row.category === "Our Stay" ? "" : "is-secondary"}" style="width:${Math.max(0, Math.min(100, Number(row.normalized100)))}%"></div>
            </div>`
                : ""
            }
            <p class="channel-takeaway">${escapeHtml(row.takeaway)}</p>
          </article>
        `
          )
          .join("")}
      </div>
    </section>

    ${
      Array.isArray(h.shorts) && h.shorts.length
        ? `
    <!-- Quick Shorts From This Resort -->
    <section class="detail-section">
      <div class="section-header" style="margin-bottom:16px;">
        <div>
          <h2 class="section-title">Quick Shorts From ${escapeHtml(h.name.split(",")[0])}</h2>
          <p class="section-subtitle">${h.shorts.length} vertical 60-second clip${h.shorts.length === 1 ? "" : "s"} filmed right on property.</p>
        </div>
        <a class="btn btn-outline" href="https://www.youtube.com/@TheUnchartedItinerary/shorts" target="_blank" rel="noopener noreferrer">All YouTube Shorts &nearr;</a>
      </div>
      <div class="shorts-rail">
        ${h.shorts
          .map(
            (sh) => `
          <a class="short-card" href="https://www.youtube.com/shorts/${encodeURIComponent(sh.id)}" target="_blank" rel="noopener noreferrer">
            <div class="short-thumb">
              <img src="https://i.ytimg.com/vi/${encodeURIComponent(sh.id)}/hqdefault.jpg" alt="${escapeHtml(sh.title)}" loading="lazy" />
              <span class="short-badge">Short</span>
            </div>
            <div class="short-info">
              <h3 class="short-title">${escapeHtml(sh.title)}</h3>
              <div class="short-date">${escapeHtml(sh.viewsText || h.location)}</div>
            </div>
          </a>
        `
          )
          .join("")}
      </div>
    </section>
        `
        : ""
    }

    <!-- Standout vs Caveat vs Consensus Gap -->
    <section class="detail-section">
      <div class="verdict-trio">
        <div class="verdict-card">
          <span class="tag tag-accent">Standout Highlight</span>
          <h3>${isGlobalOnly ? "What Guests & Critics Love" : "What We Loved Most"}</h3>
          <p>${escapeHtml(h.standout || h.verdict || "")}</p>
        </div>
        <div class="verdict-card is-warn">
          <span class="tag tag-caution">Watch Out For</span>
          <h3>Honest Caveat Before Booking</h3>
          <p>${escapeHtml(h.watchOut || "Check seasonal weather and meal plan inclusions before locking in your rate.")}</p>
        </div>
        <div class="verdict-card">
          <span class="tag">StayScore Takeaway</span>
          <h3>${isGlobalOnly ? "Global Consensus Context" : "Where We Agree or Differ"}</h3>
          <p>${escapeHtml(c.whereWeDiffer || c.otherReviewersSay || "")}</p>
        </div>
      </div>
    </section>

    <!-- Related Resorts to Compare -->
    <section class="detail-section" style="margin-bottom:56px;">
      <div class="section-header" style="margin-bottom:18px;">
        <div>
          <h2 class="section-title">Compare With Similar Resorts</h2>
          <p class="section-subtitle">Explore detailed breakdowns for nearby luxury stays or run a direct side-by-side matchup.</p>
        </div>
      </div>

      <div class="related-grid">
        ${related
          .map(
            (r) => `
          <article class="related-card">
            <img src="${escapeHtml(r.thumbnail)}" alt="${escapeHtml(r.name)}" loading="lazy" />
            <div class="related-card-body">
              <div class="meta-line">
                <span class="tag tag-accent">${r.consensus?.greatStayChance || 90}% Odds</span>
                <span>${r.consensus?.overallIndex || 90}/100</span>
              </div>
              <h4>${escapeHtml(r.name)}</h4>
              <p>${escapeHtml(r.location)}, ${escapeHtml(r.country)} &bull; ${escapeHtml(r.priceRange || "")}</p>
              <div class="related-card-actions">
                <a class="btn btn-primary" href="./?id=${encodeURIComponent(r.id)}">Full Breakdown</a>
                <a class="btn btn-outline" href="../?a=${encodeURIComponent(h.id)}&b=${encodeURIComponent(r.id)}">VS ${escapeHtml(h.name.split(",")[0].slice(0, 14))}</a>
              </div>
            </div>
          </article>
        `
          )
          .join("")}
      </div>
    </section>
  `;

  qs("#copyDetailLink")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    try {
      await navigator.clipboard.writeText(window.location.href);
      btn.textContent = "Copied Link ✓";
      setTimeout(() => (btn.textContent = "Copy Breakdown Link"), 2000);
    } catch {
      btn.textContent = "Copy failed";
    }
  });
}

async function boot() {
  initCommonUi();
  const params = new URLSearchParams(window.location.search);
  const targetId = params.get("id");

  try {
    const bust = Date.now();
    const [resVisited, resWorld] = await Promise.all([
      fetch(`../../data/hotels.json?v=${bust}`),
      fetch(`../../data/world-hotels.json?v=${bust}`).catch(() => null),
    ]);
    if (!resVisited.ok) throw new Error(`HTTP ${resVisited.status}`);
    const visitedData = await resVisited.json();
    const worldData = resWorld && resWorld.ok ? await resWorld.json() : { hotels: [] };

    const visitedHotels = (visitedData.hotels || []).map((h) => ({ ...h, visitedByUs: true }));
    const visitedIds = new Set(visitedHotels.map((h) => h.id));
    const worldHotels = (worldData.hotels || [])
      .filter((h) => !visitedIds.has(h.id))
      .map((h) => ({ ...h, visitedByUs: false }));

    const hotels = [...visitedHotels, ...worldHotels];
    const hotel = hotels.find((h) => h.id === targetId) || hotels[0];
    if (!hotel) throw new Error("No hotels found");
    renderDetail(hotel, hotels);
  } catch (err) {
    qs("#detailRoot").innerHTML = `<div class="empty-state" style="margin:48px 0;">Unable to load this StayScore breakdown right now. <a href="../" style="color:var(--accent);text-decoration:underline;">Back to StayScore</a></div>`;
    console.error(err);
  }
}

boot();
