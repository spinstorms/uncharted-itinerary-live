/**
 * StayOdds — Centralized Brand Config, Supabase Live Config, Source-URL Enforcement
 * & Dynamic Confidence-Weighted Engine (with Dual-Mode Opinion Gap & Key Facts)
 *
 * Strict integrity rules:
 * 1. Zero AI-estimated or hardcoded external scores are ever read or fabricated.
 * 2. No third-party critic, editorial rating, official award, or YouTube review may render
 *    unless it includes a real HTTP(S) `sourceUrl`.
 * 3. Google Places ratings are fetched LIVE on detail/compare views via our Supabase Edge
 *    Function and are NEVER permanently stored in Postgres.
 * 4. Consensus status badges ("Strong Consensus", "Mostly Aligned", "Split Verdict") only
 *    unlock once >= 2 independent verified numeric layers exist.
 */

export const BRAND = Object.freeze({
  name: "StayOdds",
  appStoreTitle: "StayOdds: Hotel Score Compare",
  subtitle: "Critics vs Real Guest Reviews",
  foundingContributor: "The Uncharted Itinerary",
  foundingContributorUrl: "https://uncharteditinerary.com/",
  bundleId: "com.stayodds.app",
  supabaseUrl: "https://yfupehkygkkccybefuam.supabase.co",
  supabasePublishableKey: "sb_publishable_uOxstpHWaiYEhRUnmKY4hg_o_30iq0U",
  liveGoogleEdgeUrl: "https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-google-rating",
  liveHotelRatesEdgeUrl: "https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-hotel-rates",
});

export const MACRO_REGIONS = Object.freeze([
  "Europe",
  "Asia",
  "Maldives & Indian Ocean",
  "Australia & Pacific",
  "Americas",
  "Caribbean & Mexico",
  "Middle East",
  "Africa",
]);

export function isValidHttpUrl(url) {
  return typeof url === "string" && /^https?:\/\/[^\s]+$/i.test(url.trim());
}

export function isFirstHandVerified(hotel) {
  return Boolean(
    hotel &&
      hotel.visitedByUs !== false &&
      hotel.coverageType !== "Global Directory" &&
      hotel.overall != null &&
      !Number.isNaN(Number(hotel.overall)) &&
      hotel.scores != null
  );
}

export function isVisitedProperty(hotel) {
  return Boolean(hotel && hotel.visitedByUs !== false && hotel.coverageType !== "Global Directory");
}

export function formatPersonalScore(val) {
  if (val == null || Number.isNaN(Number(val))) return null;
  const num = Number(val);
  if (Number.isInteger(num)) return String(num);
  return String(Number(num.toFixed(2)));
}

/**
 * Calibrated Bayesian dampening ONLY for small review samples (<40 reviews)
 * using prior weight m=8 toward 90: keeps 1–3 review 100% outliers moderated (91–93%)
 * while preserving genuine 8–35 review ultra-luxury boutique & island icons.
 */
export function dampenThinGuestScore(raw100, reviewCount) {
  if (raw100 == null || Number.isNaN(Number(raw100))) return null;
  const r = Number(raw100);
  const n = Number(reviewCount);
  if (!Number.isFinite(n) || n <= 0 || n >= 40) return Math.round(r);
  return Math.round((r * n + 90 * 8) / (n + 8));
}

/**
 * Returns indicative price display & numeric GBP nightly estimate from weekly
 * cached LiteAPI snapshot or curated priceRange string.
 */
export function getPriceDisplay(hotel) {
  const snap = hotel?.priceSnapshot;
  if (snap && typeof snap.nightlyGbp === "number" && snap.nightlyGbp > 0) {
    const gbp = Math.round(snap.nightlyGbp);
    const bucket = gbp < 500 ? "under500" : gbp < 1000 ? "500to1000" : gbp < 1800 ? "1000to1800" : "1800plus";
    return {
      label: snap.label || `From £${gbp.toLocaleString("en-GB")}/nt`,
      numericGbp: gbp,
      isIndicative: true,
      checkedAt: snap.checkedAt || null,
      tierBucket: bucket,
    };
  }
  const raw = String(hotel?.priceRange || "").trim();
  if (raw) {
    const m = raw.match(/([\d,]{3,6})/);
    const num = m ? Number(m[1].replace(/,/g, "")) : null;
    const bucket =
      num == null ? null : num < 500 ? "under500" : num < 1000 ? "500to1000" : num < 1800 ? "1000to1800" : "1800plus";
    return {
      label: raw,
      numericGbp: num,
      isIndicative: false,
      checkedAt: null,
      tierBucket: bucket,
    };
  }
  return { label: null, numericGbp: null, isIndicative: false, checkedAt: null, tierBucket: null };
}

/**
 * Date-aware outbound booking URL builder (zero API calls).
 * Appends checkin, checkout, and group_adults to Booking.com links cleanly.
 */
export function buildDatedBookingUrl(rawUrl, checkin, checkout, adults = 2) {
  if (!rawUrl) return "";
  if (!checkin || !checkout) return rawUrl;
  try {
    const u = new URL(rawUrl);
    if (/booking\.com/i.test(u.hostname)) {
      u.searchParams.set("checkin", checkin);
      u.searchParams.set("checkout", checkout);
      u.searchParams.set("group_adults", String(Math.max(1, Math.min(6, Number(adults) || 2))));
      u.searchParams.set("no_rooms", "1");
    }
    return u.toString();
  } catch {
    return rawUrl;
  }
}

const liveRatesMemoryCache = new Map();

/**
 * On-demand live rate lookup via cost-capped Supabase Edge Function (LiteAPI).
 * ONLY invoked when a user explicitly clicks "Check Live Rates" for specific dates.
 */
export async function fetchLiveHotelRates(nuiteeHotelIds, checkin, checkout, adults = 2, currency = "GBP") {
  const ids = Array.from(new Set((nuiteeHotelIds || []).map((x) => String(x || "").trim()).filter(Boolean)));
  if (!ids.length || !checkin || !checkout) return { status: "no_mapped_ids", rates: {} };
  const key = `${ids.slice().sort().join(",")}|${checkin}|${checkout}|${adults}|${currency}`;
  if (liveRatesMemoryCache.has(key)) return liveRatesMemoryCache.get(key);
  try {
    const params = new URLSearchParams({
      hotel_ids: ids.join(","),
      checkin,
      checkout,
      adults: String(Math.max(1, Math.min(6, Number(adults) || 2))),
      currency,
    });
    const res = await fetch(`${BRAND.liveHotelRatesEdgeUrl}?${params.toString()}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return { status: "unavailable", rates: {} };
    const data = await res.json();
    if (data && data.status === "ok") {
      liveRatesMemoryCache.set(key, data);
    }
    return data || { status: "unavailable", rates: {} };
  } catch {
    return { status: "unavailable", rates: {} };
  }
}

/**
 * STRICT CODE-LEVEL RULE: Only editorial ratings with a verified sourceUrl may pass.
 */
export function getVerifiedEditorialRatings(hotel) {
  const list = Array.isArray(hotel?.editorialRatings) ? hotel.editorialRatings : [];
  return list.filter(
    (entry) =>
      entry &&
      isValidHttpUrl(entry.sourceUrl) &&
      typeof entry.sourceName === "string" &&
      entry.sourceName.trim().length > 0
  );
}

/**
 * STRICT CODE-LEVEL RULE: Only third-party YouTube reviews with a verified sourceUrl may pass.
 */
export function getVerifiedYoutubeReviews(hotel) {
  const list = Array.isArray(hotel?.youtubeReviews) ? hotel.youtubeReviews : [];
  return list.filter(
    (entry) =>
      entry &&
      isValidHttpUrl(entry.sourceUrl) &&
      typeof entry.creatorName === "string" &&
      entry.creatorName.trim().length > 0
  );
}

/**
 * STRICT CODE-LEVEL RULE: Only official awards with a verified sourceUrl may pass.
 */
export function getVerifiedAwards(hotel) {
  const list = Array.isArray(hotel?.officialAwards) ? hotel.officialAwards : [];
  return list.filter(
    (entry) =>
      entry &&
      isValidHttpUrl(entry.sourceUrl) &&
      typeof entry.label === "string" &&
      entry.label.trim().length > 0
  );
}

/**
 * Reads ONLY live/verified API guest ratings (never legacy AI-estimated fields).
 */
export function getVerifiedGuestScore(hotel) {
  const vg = hotel?.verifiedGuest;
  if (!vg || typeof vg !== "object") return null;

  if (vg.google && typeof vg.google.rating === "number" && vg.google.rating > 0) {
    const raw100 = Math.round(vg.google.rating * 20);
    const rc = typeof vg.google.reviewCount === "number" ? vg.google.reviewCount : null;
    return {
      sourceName: "Google Reviews",
      rating: vg.google.rating,
      scale: 5,
      reviewCount: rc,
      rawNormalized100: raw100,
      normalized100: dampenThinGuestScore(raw100, rc),
      wasDampened: rc != null && rc > 0 && rc < 40,
      verifiedAt: vg.google.fetchedAt || vg.google.verifiedAt || null,
      attribution: "Powered by Google",
      googleMapsUri: vg.google.googleMapsUri || null,
    };
  }

  if (vg.licensed && typeof vg.licensed.normalized100 === "number" && vg.licensed.normalized100 > 0) {
    const raw100 = Math.round(vg.licensed.normalized100);
    const rc = typeof vg.licensed.reviewCount === "number" ? vg.licensed.reviewCount : null;
    return {
      sourceName: vg.licensed.sourceName || "Verified Guest Feed",
      rating: vg.licensed.rating ?? Number((raw100 / 10).toFixed(1)),
      scale: vg.licensed.scale || 10,
      reviewCount: rc,
      rawNormalized100: raw100,
      normalized100: dampenThinGuestScore(raw100, rc),
      wasDampened: rc != null && rc > 0 && rc < 40,
      verifiedAt: vg.licensed.verifiedAt || null,
      attribution: vg.licensed.attribution || vg.licensed.sourceName || "Licensed Partner Feed",
      googleMapsUri: null,
    };
  }

  return null;
}

/**
 * Returns only non-empty verified Middle Key Facts for display (blank fields cleanly omitted).
 */
export function getKeyFactsList(hotel) {
  const f = hotel?.keyFacts || {};
  const items = [];
  if (f.poolHeating) items.push({ label: "Pool Heating", value: f.poolHeating });
  if (f.beachOrReef) items.push({ label: "Beach & Reef", value: f.beachOrReef });
  if (f.renovationYear) items.push({ label: "Opened / Renovated", value: String(f.renovationYear) });
  if (f.transferLogistics) items.push({ label: "Transfer Logistics", value: f.transferLogistics });
  const price = getPriceDisplay(hotel);
  if (price.label) items.push({ label: price.isIndicative ? "Indicative Rate" : "Price Tier", value: price.label });
  return items;
}

const liveGoogleMemoryCache = new Map();
const liveGoogleInFlight = new Map();

/**
 * Fetch live Google Places rating on-demand for Detail & Compare views ONLY via Supabase Edge Function.
 * Deduplicated in memory during the current page session (never persisted to localStorage per Google ToS).
 */
export async function fetchLiveGoogleRating(googlePlaceId) {
  if (!googlePlaceId) return null;
  if (liveGoogleMemoryCache.has(googlePlaceId)) {
    return liveGoogleMemoryCache.get(googlePlaceId);
  }
  if (liveGoogleInFlight.has(googlePlaceId)) {
    return liveGoogleInFlight.get(googlePlaceId);
  }
  const req = (async () => {
    try {
      const res = await fetch(
        `${BRAND.liveGoogleEdgeUrl}?place_id=${encodeURIComponent(googlePlaceId)}`,
        { headers: { Accept: "application/json" } }
      );
      if (!res.ok) return null;
      const data = await res.json();
      if (data.status !== "ok" || typeof data.rating !== "number") return null;
      liveGoogleMemoryCache.set(googlePlaceId, data);
      return data;
    } catch {
      return null;
    } finally {
      liveGoogleInFlight.delete(googlePlaceId);
    }
  })();
  liveGoogleInFlight.set(googlePlaceId, req);
  return req;
}

export function isScoreUnverified(entry) {
  if (!entry || typeof entry !== "object") return false;
  if (entry.scoreUnverified === true) return true;
  const text = `${entry.rawScore || ""} ${entry.takeaway || ""} ${entry.quote || ""}`;
  return /unable to verify|unverified/i.test(text);
}

export function getPersonalScoreStats(hotel) {
  if (!isFirstHandVerified(hotel) || !hotel?.scores) return null;
  const s = hotel.scores;
  const vals = [s.value, s.rooms, s.grounds, s.food, s.service]
    .filter((v) => v != null && v !== "" && !Number.isNaN(Number(v)))
    .map(Number);
  if (!vals.length) return null;
  const sum = Number(vals.reduce((a, b) => a + b, 0).toFixed(2));
  const max = vals.length * 5;
  return { sum, max, label: `${formatPersonalScore(sum)} / ${max}` };
}

export function getPersonalScore25(hotel) {
  const st = getPersonalScoreStats(hotel);
  return st ? st.sum : null;
}

export function computeStayOdds(hotel) {
  const firstHand = isFirstHandVerified(hotel);
  const visited = isVisitedProperty(hotel);
  const editorialRatings = getVerifiedEditorialRatings(hotel);
  const youtubeReviews = getVerifiedYoutubeReviews(hotel);
  const officialAwards = getVerifiedAwards(hotel);
  const verifiedGuest = getVerifiedGuestScore(hotel);
  const keyFacts = getKeyFactsList(hotel);
  const redFlags = Array.isArray(hotel?.redFlags) ? hotel.redFlags.filter(Boolean) : [];

  const personalStats = getPersonalScoreStats(hotel);
  const personalScore25 = personalStats ? personalStats.sum : null;
  const personalScoreMax = personalStats ? personalStats.max : 25;
  const personalScoreLabel = personalStats ? personalStats.label : null;
  const ours100 =
    personalStats != null
      ? Math.round((personalStats.sum / personalStats.max) * 100)
      : firstHand
      ? Math.round(Number(hotel.overall) * 20)
      : null;

  const scoredEditorial = editorialRatings.filter(
    (r) => r.normalized100 != null && !Number.isNaN(Number(r.normalized100)) && !isScoreUnverified(r)
  );
  const unverifiedEditorial = editorialRatings.filter((r) => isScoreUnverified(r));
  const scoredCriticInputs = scoredEditorial.map((r) => Number(r.normalized100));
  const critic100 =
    scoredCriticInputs.length > 0
      ? Math.round(scoredCriticInputs.reduce((acc, v) => acc + v, 0) / scoredCriticInputs.length)
      : null;

  const primaryCritic = scoredEditorial.length > 0 ? scoredEditorial[0] : null;
  const guest100 = verifiedGuest ? verifiedGuest.normalized100 : null;

  // LAYER 1: Universal External Consensus Baseline (0-100%)
  let marketOdds = null;
  let marketSourceCount = 0;
  let marketFormulaSummary = "No external numeric score yet";
  let sourceBasisShort = "Live Google";
  if (critic100 != null && guest100 != null) {
    marketOdds = Math.round(critic100 * 0.35 + guest100 * 0.65);
    marketSourceCount = 2;
    marketFormulaSummary = "Based on 2 sources: Published Critics (35%) + Verified Guests (65%)";
    sourceBasisShort = "2 sources • Critics + Guests";
  } else if (guest100 != null) {
    marketOdds = guest100;
    marketSourceCount = 1;
    const gName = verifiedGuest?.sourceName || "Verified Guests";
    marketFormulaSummary = verifiedGuest?.wasDampened
      ? `Based on 1 source (${gName}, small-sample adjusted)`
      : `Based on 1 source (${gName})`;
    sourceBasisShort = `1 source • ${gName}`;
  } else if (critic100 != null) {
    marketOdds = critic100;
    marketSourceCount = 1;
    marketFormulaSummary = "Based on 1 source (Published Critics)";
    sourceBasisShort = "1 source • Critics";
  }

  // LAYER 2: Two-Track Headline Score ("Uncharted Verified" vs "StayOdds")
  const scoreTrack = firstHand && ours100 != null ? "verified" : "market";
  const scoreTrackLabel =
    scoreTrack === "verified"
      ? "Uncharted Verified"
      : marketSourceCount >= 2
      ? `StayOdds • ${marketSourceCount} Sources`
      : marketSourceCount === 1
      ? "StayOdds • 1 Source"
      : "StayOdds";

  let weights = { firstHand: 0, market: 0, critics: 0, guests: 0 };
  let overallIndex = null;
  let greatStayOdds = null;
  let spread100 = null;
  let statusBadge = officialAwards.length > 0 ? "Award-Winning" : "Global Directory";
  let statusTone = officialAwards.length > 0 ? "teal" : "slate";
  let isConsensusBadge = false;
  let formulaSummary =
    officialAwards.length > 0
      ? `Awarded ${officialAwards.map((a) => a.label).join(" • ")} — open breakdown for live Google reviews.`
      : "Open breakdown to check live Google guest reviews.";

  const activeScores = [ours100, critic100, guest100].filter((v) => v != null);
  const sourceCount = activeScores.length;

  const founderVsMarketDelta =
    firstHand && ours100 != null && marketOdds != null ? ours100 - marketOdds : null;
  const founderVsMarketLabel =
    founderVsMarketDelta != null
      ? `Uncharted ${founderVsMarketDelta > 0 ? "+" : ""}${founderVsMarketDelta} pts vs Consensus`
      : null;

  if (scoreTrack === "verified") {
    if (marketOdds != null) {
      overallIndex = Math.round(ours100 * 0.7 + marketOdds * 0.3);
      weights = {
        firstHand: 70,
        market: 30,
        critics: critic100 != null && guest100 != null ? 11 : critic100 != null ? 30 : 0,
        guests: critic100 != null && guest100 != null ? 19 : guest100 != null ? 30 : 0,
      };
      formulaSummary = `70% Uncharted Video Stay (${personalScoreLabel || `${ours100}%`}) • 30% Consensus (${marketOdds}%)`;
      sourceBasisShort = `Uncharted Stay + ${marketSourceCount} source${marketSourceCount === 1 ? "" : "s"}`;
    } else {
      overallIndex = ours100;
      weights = { firstHand: 100, market: 0, critics: 0, guests: 0 };
      statusBadge = "Uncharted Video Stay";
      statusTone = "accent";
      formulaSummary = `100% Uncharted Itinerary Stay (${personalScoreLabel || `${ours100}%`})`;
      sourceBasisShort = "1 source • Uncharted Video Stay";
    }
  } else {
    overallIndex = marketOdds;
    if (critic100 != null && guest100 != null) {
      weights = { firstHand: 0, market: 100, critics: 35, guests: 65 };
      formulaSummary = marketFormulaSummary;
    } else if (guest100 != null) {
      weights = { firstHand: 0, market: 100, critics: 0, guests: 100 };
      statusBadge = "1 Data Source";
      statusTone = "teal";
      formulaSummary = marketFormulaSummary;
    } else if (critic100 != null) {
      weights = { firstHand: 0, market: 100, critics: 100, guests: 0 };
      statusBadge = "1 Data Source";
      statusTone = "slate";
      formulaSummary = marketFormulaSummary;
    }
  }

  greatStayOdds = overallIndex;
  if (sourceCount >= 2 && overallIndex != null) {
    isConsensusBadge = true;
    spread100 =
      scoreTrack === "verified" && founderVsMarketDelta != null
        ? Math.abs(founderVsMarketDelta)
        : Math.max(...activeScores) - Math.min(...activeScores);
    if (spread100 <= 6) {
      statusBadge = "Strong Agreement";
      statusTone = "accent";
    } else if (spread100 <= 12) {
      statusBadge = "Mostly Aligned";
      statusTone = "teal";
    } else {
      statusBadge = "Opinions Differ";
      statusTone = "amber";
    }
  }

  // Dual-Mode Opinion Gap Module ("The Uncharted Itinerary vs. Consensus" OR "Published Critics vs. Real Guests")
  const left100 = firstHand ? ours100 : critic100;
  const right100 = firstHand ? marketOdds : guest100;
  const delta100 = left100 != null && right100 != null ? left100 - right100 : null;

  let gapHeadline = firstHand
    ? "The Uncharted Itinerary's filmed stay score leads here — open breakdown to compare with live Google reviews."
    : unverifiedEditorial.length > 0 && scoredEditorial.length === 0
    ? `${unverifiedEditorial.map((u) => u.sourceName).join(", ")} awards a score (unverified figure — excluded from numeric math).`
    : officialAwards.length > 0
    ? `Recognised with ${officialAwards.map((a) => a.label).join(" • ")} — compare with real guest reviews below.`
    : marketFormulaSummary !== "No external numeric score yet"
    ? `${marketFormulaSummary}.`
    : "Open breakdown to check live Google guest reviews.";

  if (delta100 != null) {
    const criticName =
      scoredEditorial.length === 1 ? primaryCritic.sourceName : `${scoredEditorial.length} published critics`;
    if (Math.abs(delta100) <= 5) {
      gapHeadline = firstHand
        ? `Tight agreement (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — The Uncharted Itinerary matched the wider consensus.`
        : `Tight agreement (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — ${criticName} and real guests agree.`;
    } else if (delta100 > 5) {
      gapHeadline = firstHand
        ? `The Uncharted Itinerary rated this +${delta100} pts higher than consensus — see what stood out.`
        : `${criticName} rated this +${delta100} pts higher than real guests.`;
    } else {
      gapHeadline = firstHand
        ? `The Uncharted Itinerary rated this ${delta100} pts stricter than consensus — see what held it back.`
        : `Real guests rated this +${Math.abs(delta100)} pts higher than ${criticName}.`;
    }
  }

  const leftDisplay = firstHand
    ? personalScoreLabel || `${formatPersonalScore(hotel.overall)} / 5`
    : scoredEditorial.length === 1
    ? primaryCritic.rawScore || `${critic100} / 100`
    : scoredEditorial.length > 1
    ? `${critic100} / 100 (${scoredEditorial.length} critics)`
    : unverifiedEditorial.length > 0
    ? "Score awarded — unverified"
    : "No critic score";

  const opinionGap = {
    mode: firstHand ? "my_vs_market" : "critics_vs_guests",
    title: firstHand ? "The Uncharted Itinerary vs. Consensus" : "Published Critics vs. Real Guests",
    leftLabel: firstHand
      ? "The Uncharted Itinerary (Video Stay)"
      : scoredEditorial.length === 1
      ? primaryCritic.sourceName
      : scoredEditorial.length === 0 && unverifiedEditorial.length === 1
      ? unverifiedEditorial[0].sourceName
      : "Published Critics",
    left100,
    leftDisplay,
    rightLabel: firstHand ? "Guest & Critic Consensus" : verifiedGuest ? `${verifiedGuest.sourceName}` : "Real Guest Score",
    right100,
    rightDisplay: firstHand
      ? marketOdds != null
        ? `${marketOdds}%`
        : "Open Breakdown"
      : verifiedGuest
      ? `${verifiedGuest.rating.toFixed(1)} / ${verifiedGuest.scale}`
      : "Open Breakdown",
    delta100,
    deltaLabel: delta100 != null ? `${delta100 > 0 ? "+" : ""}${delta100} pts` : "—",
    headline: gapHeadline,
    narrative: firstHand
      ? hotel.whereWeDiffer || hotel.verdict || ""
      : hotel.standout || hotel.verdict || "",
  };

  const isFullUnscored = visited && !firstHand && hotel.coverageType !== "Short Tour";
  return {
    tier: firstHand ? "first_hand_verified" : visited ? "short_preview" : "global_directory",
    tierLabel: firstHand
      ? "Uncharted Verified"
      : isFullUnscored
      ? "Uncharted Video Stay"
      : visited
      ? "Uncharted Short"
      : "Global Directory",
    scoreTrack,
    scoreTrackLabel,
    sourceBasisShort,
    firstHand,
    visited,
    personalScore25,
    personalScoreMax,
    personalScoreLabel,
    ours100,
    critic100,
    primaryCritic,
    scoredEditorial,
    unverifiedEditorial,
    guest100,
    marketOdds,
    marketSourceCount,
    marketFormulaSummary,
    founderVsMarketDelta,
    founderVsMarketLabel,
    overallIndex,
    greatStayOdds,
    spread100,
    sourceCount,
    isConsensusBadge,
    statusBadge,
    statusTone,
    weights,
    formulaSummary,
    opinionGap,
    keyFacts,
    redFlags,
    editorialRatings,
    youtubeReviews,
    officialAwards,
    verifiedGuest,
  };
}
