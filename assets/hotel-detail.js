import {
  BRAND,
  computeStayOdds,
  formatPersonalScore,
} from "./stayodds-engine.js?v=1";

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
  const formatted = wholeNumbers ? formatPersonalScore(num) || "—" : num.toFixed(1);
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
  const o = computeStayOdds(h);
  const s = h.scores || null;
  const isShortOnly = h.coverageType === "Short Tour";
  const isGlobalOnly = !o.visited;
  const reviewHref = getReviewHref(h);
  const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";

  const tagClass =
    o.statusTone === "amber"
      ? "tag-caution"
      : o.statusTone === "accent"
      ? "tag-accent"
      : o.statusTone === "teal"
      ? "tag-teal"
      : "tag-slate";

  document.title = `${h.name} — ${BRAND.name} Breakdown | ${BRAND.subtitle}`;

  const related = allHotels
    .filter((other) => other.id !== h.id)
    .sort((a, bItem) => {
      const sameRegA = a.region === h.region ? 1 : 0;
      const sameRegB = bItem.region === h.region ? 1 : 0;
      if (sameRegB !== sameRegA) return sameRegB - sameRegA;
      const oa = computeStayOdds(a);
      const ob = computeStayOdds(bItem);
      return (ob.greatStayOdds ?? -1) - (oa.greatStayOdds ?? -1);
    })
    .slice(0, 3);

  const root = qs("#detailRoot");
  root.innerHTML = `
    <div class="detail-breadcrumb">
      <a href="../">&larr; All ${escapeHtml(BRAND.name)} Properties</a>
      <span>/</span>
      <a href="../../hotels/">Hotel Map</a>
      <span>/</span>
      <strong>${escapeHtml(h.name)}</strong>
    </div>

    <section class="detail-hero">
      <div class="detail-hero-media">
        <img src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div class="detail-hero-badges">
          <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${escapeHtml(o.tierLabel)}</span>
          <span class="tag ${tagClass}">${escapeHtml(o.statusBadge)}</span>
          ${o.officialAwards.map((aw) => `<a class="tag" href="${escapeHtml(aw.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(aw.label)} ↗</a>`).join("")}
        </div>
      </div>

      <div class="detail-hero-body">
        <div class="meta-line">
          <span>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</span>
          ${h.brand ? `<span>&bull;</span><span>${escapeHtml(h.brand)}</span>` : ""}
          ${h.priceRange ? `<span>&bull;</span><span>${escapeHtml(h.priceRange)}</span>` : ""}
        </div>

        <h1 class="detail-title">${escapeHtml(h.name)}</h1>
        <p class="detail-verdict">${escapeHtml(h.verdict || h.standout || "")}</p>

        <div class="detail-kpi-row">
          <div class="detail-kpi is-primary ${o.statusTone === "amber" ? "is-caution" : ""}">
            <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : "Pending"}</strong>
            <span>${escapeHtml(o.statusBadge)}</span>
          </div>
          <div class="detail-kpi">
            <strong>${o.overallIndex != null ? `${o.overallIndex}<span>/100</span>` : "—"}</strong>
            <span>${escapeHtml(BRAND.name)} Index</span>
          </div>
          <div class="detail-kpi">
            ${
              o.firstHand
                ? `<strong>${formatPersonalScore(h.overall)}<span>/5</span></strong><span>First-Hand Verified</span>`
                : `<strong style="font-size:18px;">${isGlobalOnly ? "Unvisited" : "Short Only"}</strong><span>${escapeHtml(o.tierLabel)}</span>`
            }
          </div>
          <div class="detail-kpi">
            <strong>${o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)}<span>/${o.verifiedGuest.scale}</span>` : "Phase 1B"}</strong>
            <span>${o.verifiedGuest ? escapeHtml(o.verifiedGuest.sourceName) : "Live Guest API"}</span>
          </div>
        </div>

        <div class="detail-actions">
          ${
            reviewHref
              ? `<a class="btn btn-primary" href="${escapeHtml(reviewHref)}"${ext}>${isShortOnly ? "Watch Our Resort Short" : "Watch Our Full Review"}</a>
                 <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &amp; Reviews &nearr;</a>`
              : `<a class="btn btn-primary" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &amp; Reviews &nearr;</a>`
          }
          <a class="btn btn-outline" href="../?a=${encodeURIComponent(h.id)}">Compare Head-to-Head</a>
          <button class="copy-link-btn" id="copyDetailLink" type="button">Copy Link</button>
        </div>
      </div>
    </section>

    <!-- Dynamic Confidence-Weighted Formula Transparency -->
    <section class="detail-section">
      <div class="section-header" style="margin-bottom:16px;">
        <div>
          <h2 class="section-title">How This ${escapeHtml(BRAND.name)} Rating Is Weighted</h2>
          <p class="section-subtitle">${escapeHtml(o.formulaSummary)}</p>
        </div>
      </div>

      <div class="formula-grid">
        <div class="formula-step">
          <span class="formula-weight">${o.weights.firstHand}% Active Weight</span>
          <strong>${o.ours100 != null ? `${o.ours100} / 100` : "Not Rated"}</strong>
          <small>${o.firstHand ? `First-Hand Verified (${formatPersonalScore(h.overall)} / 5 by ${escapeHtml(BRAND.foundingContributor)})` : isShortOnly ? "Short preview only — full stay pending" : "Global Directory property — not stayed yet"}</small>
        </div>
        <div class="formula-step">
          <span class="formula-weight">${o.weights.critics}% Active Weight</span>
          <strong>${o.critic100 != null ? `${o.critic100} / 100` : "0 Sourced"}</strong>
          <small>${o.editorialRatings.length ? `${o.editorialRatings.length} verified editorial link${o.editorialRatings.length === 1 ? "" : "s"}` : "Only source-linked editorial ratings count"}</small>
        </div>
        <div class="formula-step">
          <span class="formula-weight">${o.weights.guests}% Active Weight</span>
          <strong>${o.guest100 != null ? `${o.guest100} / 100` : "Live API Pending"}</strong>
          <small>${o.verifiedGuest ? `${o.verifiedGuest.sourceName} (${o.verifiedGuest.rating.toFixed(1)}/${o.verifiedGuest.scale}${o.verifiedGuest.reviewCount ? ` • ${o.verifiedGuest.reviewCount.toLocaleString("en-GB")} reviews` : ""})` : "Connecting live Google Places & licensed feed in Phase 1B"}</small>
        </div>
        <div class="formula-step is-result ${o.statusTone === "amber" ? "is-caution" : ""}">
          <span class="formula-weight">${escapeHtml(o.statusBadge)}</span>
          <strong>${o.greatStayOdds != null ? `${o.greatStayOdds}% Odds` : "Pending"}</strong>
          <small>${o.isConsensusBadge && o.spread100 != null ? `Cross-source spread: ${o.spread100} pts` : "Consensus status unlocks at 2+ verified sources"}</small>
        </div>
      </div>
    </section>

    <!-- Detailed Breakdown: First-Hand Scorecard vs Live Guest Feed -->
    <section class="detail-section">
      <div class="detail-two-col">
        <div class="detail-panel">
          <div class="detail-panel-head">
            <h3>First-Hand 5-Axis Scorecard</h3>
            <span class="tag ${o.firstHand ? "tag-accent" : "tag-slate"}">${o.firstHand ? `${formatPersonalScore(h.overall)} / 5 Overall` : escapeHtml(o.tierLabel)}</span>
          </div>
          ${
            o.firstHand
              ? `
          <p class="detail-panel-sub">Whole-number 1–5 scores from ${escapeHtml(BRAND.foundingContributor)}’s stay at ${escapeHtml(h.name)}.</p>
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
                ? `The Uncharted Itinerary has not filmed a full first-hand stay at ${escapeHtml(h.name)} yet. When a full stay is filmed, whole-number 5-axis scores will automatically unlock and upgrade this property to Tier 1 First-Hand Verified.`
                : `We’ve filmed quick YouTube Shorts at ${escapeHtml(h.name)} without assigning a full 5-axis stay scorecard yet.`
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
            <h3>Live Verified Guest Ratings &amp; Booking</h3>
            <span class="tag ${o.verifiedGuest ? "tag-teal" : "tag-slate"}">${o.verifiedGuest ? escapeHtml(o.verifiedGuest.attribution) : "Phase 1B Live API"}</span>
          </div>
          ${
            o.verifiedGuest
              ? `
          <p class="detail-panel-sub">Live API rating: <strong>${o.verifiedGuest.rating.toFixed(1)} / ${o.verifiedGuest.scale}</strong>${o.verifiedGuest.reviewCount ? ` across ${o.verifiedGuest.reviewCount.toLocaleString("en-GB")} verified guest reviews` : ""}.</p>
              `
              : `
          <div class="scorecard-unrated-box" style="margin-top:12px;">
            <strong>Zero Guessed or Estimated Guest Scores</strong>
            <p>${escapeHtml(BRAND.name)} never displays estimated Google, Booking.com, or TripAdvisor ratings. Live API guest ratings connect in Phase 1B via Google Places API and licensed hotel data feeds. In the meantime, check verified guest reviews and live nightly rates directly below.</p>
            <a class="btn btn-primary" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates &amp; Guest Reviews &nearr;</a>
          </div>
              `
          }
        </div>
      </div>
    </section>

    <!-- Separated Layers: Structured Editorial Ratings/Awards vs Linked YouTube Reviews -->
    <section class="detail-section">
      <div class="detail-two-col">
        <div class="detail-panel">
          <div class="detail-panel-head">
            <h3>Structured Editorial Ratings &amp; Awards</h3>
            <span class="tag">${o.editorialRatings.length + o.officialAwards.length} verified</span>
          </div>
          ${
            o.editorialRatings.length || o.officialAwards.length
              ? `
          <div class="channel-breakdown-list" style="margin-top:12px;">
            ${o.editorialRatings
              .map(
                (r) => `
              <article class="channel-row">
                <div class="channel-row-head">
                  <div>
                    <span class="tag">Editorial</span>
                    <h4><a href="${escapeHtml(r.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(r.sourceName)} &nearr;</a></h4>
                  </div>
                  <div class="channel-row-score">
                    <strong>${escapeHtml(r.rawScore || `${r.normalized100}/100`)}</strong>
                    <span>${Number(r.normalized100)}/100</span>
                  </div>
                </div>
                ${r.takeaway ? `<p class="channel-takeaway">${escapeHtml(r.takeaway)}</p>` : ""}
              </article>
            `
              )
              .join("")}
            ${o.officialAwards
              .map(
                (a) => `
              <article class="channel-row">
                <div class="channel-row-head">
                  <div>
                    <span class="tag tag-accent">Official Award</span>
                    <h4><a href="${escapeHtml(a.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.label)} &nearr;</a></h4>
                  </div>
                  <div class="channel-row-score"><strong>${escapeHtml(a.year || "Verified")}</strong></div>
                </div>
              </article>
            `
              )
              .join("")}
          </div>
              `
              : `<p class="detail-panel-sub" style="margin-top:12px;">No source-linked editorial ratings or official award URLs logged for this property yet. ${escapeHtml(BRAND.name)} strictly requires a direct verified URL before displaying any editorial score.</p>`
          }
        </div>

        <div class="detail-panel">
          <div class="detail-panel-head">
            <h3>Linked YouTube Video Reviews</h3>
            <span class="tag">${(reviewHref ? 1 : 0) + o.youtubeReviews.length} linked</span>
          </div>
          <div class="channel-breakdown-list" style="margin-top:12px;">
            ${
              reviewHref
                ? `
            <article class="channel-row">
              <div class="channel-row-head">
                <div>
                  <span class="tag tag-accent">Founding Contributor</span>
                  <h4><a href="${escapeHtml(reviewHref)}"${ext}>${escapeHtml(BRAND.foundingContributor)} — ${isShortOnly ? "Resort Short" : "Full Review"} &nearr;</a></h4>
                </div>
                <div class="channel-row-score">
                  <strong>${o.firstHand ? `${formatPersonalScore(h.overall)} / 5` : "Short"}</strong>
                </div>
              </div>
              <p class="channel-takeaway">${escapeHtml(h.verdict || "")}</p>
            </article>
                `
                : ""
            }
            ${o.youtubeReviews
              .map(
                (yt) => `
              <article class="channel-row">
                <div class="channel-row-head">
                  <div>
                    <span class="tag">${escapeHtml(yt.sentiment || "Video Review")}</span>
                    <h4><a href="${escapeHtml(yt.sourceUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(yt.creatorName)} &nearr;</a></h4>
                  </div>
                </div>
                ${yt.takeaway ? `<p class="channel-takeaway">${escapeHtml(yt.takeaway)}</p>` : ""}
              </article>
            `
              )
              .join("")}
            ${
              !reviewHref && !o.youtubeReviews.length
                ? `<p class="detail-panel-sub">No third-party YouTube reviews linked yet. Every creator video added here requires a direct YouTube URL and represents their actual stated take without inventing synthetic scores.</p>`
                : ""
            }
          </div>
        </div>
      </div>
    </section>

    ${
      Array.isArray(h.shorts) && h.shorts.length
        ? `
    <section class="detail-section">
      <div class="section-header" style="margin-bottom:16px;">
        <div>
          <h2 class="section-title">Quick Shorts From ${escapeHtml(h.name.split(",")[0])}</h2>
          <p class="section-subtitle">${h.shorts.length} vertical 60-second clip${h.shorts.length === 1 ? "" : "s"} filmed on property.</p>
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

    <!-- Standout vs Caveat -->
    <section class="detail-section">
      <div class="verdict-trio">
        <div class="verdict-card">
          <span class="tag tag-accent">Standout Highlight</span>
          <h3>${isGlobalOnly ? "Key Property Highlight" : "What Stood Out Most"}</h3>
          <p>${escapeHtml(h.standout || h.verdict || "")}</p>
        </div>
        <div class="verdict-card is-warn">
          <span class="tag tag-caution">Watch Out For</span>
          <h3>Honest Caveat Before Booking</h3>
          <p>${escapeHtml(h.watchOut || "Check seasonal weather, transfer costs, and room categories before booking.")}</p>
        </div>
        <div class="verdict-card">
          <span class="tag">${escapeHtml(BRAND.name)} Transparency</span>
          <h3>Data Integrity Status</h3>
          <p>${escapeHtml(o.formulaSummary)}</p>
        </div>
      </div>
    </section>

    <!-- Related Resorts -->
    <section class="detail-section" style="margin-bottom:56px;">
      <div class="section-header" style="margin-bottom:18px;">
        <div>
          <h2 class="section-title">Compare With Similar Resorts</h2>
          <p class="section-subtitle">Explore nearby luxury stays or run a direct head-to-head matchup.</p>
        </div>
      </div>

      <div class="related-grid">
        ${related
          .map((r) => {
            const ro = computeStayOdds(r);
            return `
          <article class="related-card">
            <img src="${escapeHtml(r.thumbnail)}" alt="${escapeHtml(r.name)}" loading="lazy" />
            <div class="related-card-body">
              <div class="meta-line">
                <span class="tag ${ro.firstHand ? "tag-accent" : "tag-slate"}">${ro.greatStayOdds != null ? `${ro.greatStayOdds}% StayOdds` : escapeHtml(ro.tierLabel)}</span>
                <span>${escapeHtml(ro.statusBadge)}</span>
              </div>
              <h4>${escapeHtml(r.name)}</h4>
              <p>${escapeHtml(r.location)}, ${escapeHtml(r.country)}${r.priceRange ? ` &bull; ${escapeHtml(r.priceRange)}` : ""}</p>
              <div class="related-card-actions">
                <a class="btn btn-primary" href="./?id=${encodeURIComponent(r.id)}">Full Breakdown</a>
                <a class="btn btn-outline" href="../?a=${encodeURIComponent(h.id)}&b=${encodeURIComponent(r.id)}">VS ${escapeHtml(h.name.split(",")[0].slice(0, 14))}</a>
              </div>
            </div>
          </article>
        `;
          })
          .join("")}
      </div>
    </section>
  `;

  qs("#copyDetailLink")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    try {
      await navigator.clipboard.writeText(window.location.href);
      btn.textContent = "Copied Link ✓";
      setTimeout(() => (btn.textContent = "Copy Link"), 2000);
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
    qs("#detailRoot").innerHTML = `<div class="empty-state" style="margin:48px 0;">Unable to load this ${escapeHtml(BRAND.name)} breakdown right now. <a href="../" style="color:var(--accent);text-decoration:underline;">Back to ${escapeHtml(BRAND.name)}</a></div>`;
    console.error(err);
  }
}

boot();
