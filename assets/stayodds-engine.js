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
  foundingContributorUrl: "https://www.uncharteditinerary.com/",
  bundleId: "com.stayodds.app",
  supabaseUrl: "https://yfupehkygkkccybefuam.supabase.co",
  supabasePublishableKey: "sb_publishable_uOxstpHWaiYEhRUnmKY4hg_o_30iq0U",
  liveGoogleEdgeUrl: "https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-google-rating",
});

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
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
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
    return {
      sourceName: "Google Reviews",
      rating: vg.google.rating,
      scale: 5,
      reviewCount: typeof vg.google.reviewCount === "number" ? vg.google.reviewCount : null,
      normalized100: Math.round(vg.google.rating * 20),
      verifiedAt: vg.google.fetchedAt || vg.google.verifiedAt || null,
      attribution: "Powered by Google",
      googleMapsUri: vg.google.googleMapsUri || null,
    };
  }

  if (vg.licensed && typeof vg.licensed.normalized100 === "number" && vg.licensed.normalized100 > 0) {
    return {
      sourceName: vg.licensed.sourceName || "Verified Guest Feed",
      rating: vg.licensed.rating ?? Number((vg.licensed.normalized100 / 10).toFixed(1)),
      scale: vg.licensed.scale || 10,
      reviewCount: typeof vg.licensed.reviewCount === "number" ? vg.licensed.reviewCount : null,
      normalized100: Math.round(vg.licensed.normalized100),
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
  if (hotel?.priceRange) items.push({ label: "Price Tier", value: hotel.priceRange });
  return items;
}

/**
 * Fetch live Google Places rating on-demand for Detail & Compare views ONLY via Supabase Edge Function.
 */
export async function fetchLiveGoogleRating(googlePlaceId) {
  if (!googlePlaceId) return null;
  try {
    const res = await fetch(
      `${BRAND.liveGoogleEdgeUrl}?place_id=${encodeURIComponent(googlePlaceId)}`,
      { headers: { Accept: "application/json" } }
    );
    if (!res.ok) return null;
    const data = await res.json();
    if (data.status !== "ok" || typeof data.rating !== "number") return null;
    return data;
  } catch {
    return null;
  }
}

export function getPersonalScore25(hotel) {
  if (!isFirstHandVerified(hotel) || !hotel?.scores) return null;
  const s = hotel.scores;
  const vals = [s.value, s.rooms, s.grounds, s.food, s.service].map(Number);
  if (vals.some((v) => Number.isNaN(v))) return null;
  return vals.reduce((a, b) => a + b, 0);
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

  const personalScore25 = getPersonalScore25(hotel);
  const ours100 =
    personalScore25 != null
      ? Math.round(personalScore25 * 4)
      : firstHand
      ? Math.round(Number(hotel.overall) * 20)
      : null;

  // STRICT RULE: Numeric critic score ONLY comes from published numeric critic reviews (e.g. 9/10, 18/20).
  // Non-scored editorial articles (e.g. The Points Guy) and official awards (MICHELIN Keys, Forbes Five-Star,
  // World's 50 Best) are ALWAYS displayed with direct clickable links, never turned into invented /100 scores.
  const scoredEditorial = editorialRatings.filter(
    (r) => r.normalized100 != null && !Number.isNaN(Number(r.normalized100))
  );
  const scoredCriticInputs = scoredEditorial.map((r) => Number(r.normalized100));
  const critic100 =
    scoredCriticInputs.length > 0
      ? Math.round(scoredCriticInputs.reduce((acc, v) => acc + v, 0) / scoredCriticInputs.length)
      : null;

  const primaryCritic = scoredEditorial.length > 0 ? scoredEditorial[0] : null;
  const guest100 = verifiedGuest ? verifiedGuest.normalized100 : null;

  let weights = { firstHand: 0, critics: 0, guests: 0 };
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

  if (firstHand) {
    if (critic100 != null && guest100 != null) {
      weights = { firstHand: 40, critics: 30, guests: 30 };
      overallIndex = Math.round(ours100 * 0.4 + critic100 * 0.3 + guest100 * 0.3);
      formulaSummary = "40% My Stay • 30% Published Critics • 30% Verified Guests";
    } else if (guest100 != null) {
      weights = { firstHand: 55, critics: 0, guests: 45 };
      overallIndex = Math.round(ours100 * 0.55 + guest100 * 0.45);
      formulaSummary = "55% My Stay • 45% Verified Guests";
    } else if (critic100 != null) {
      weights = { firstHand: 55, critics: 45, guests: 0 };
      overallIndex = Math.round(ours100 * 0.55 + critic100 * 0.45);
      formulaSummary = "55% My Stay • 45% Published Critics";
    } else {
      weights = { firstHand: 100, critics: 0, guests: 0 };
      overallIndex = ours100;
      greatStayOdds = ours100;
      statusBadge = "First-Hand Verified";
      statusTone = "accent";
      formulaSummary = "100% My First-Hand Stay — open breakdown for live Google reviews.";
    }
  } else {
    if (critic100 != null && guest100 != null) {
      weights = { firstHand: 0, critics: 35, guests: 65 };
      overallIndex = Math.round(critic100 * 0.35 + guest100 * 0.65);
      formulaSummary = "35% Published Critics • 65% Verified Guests";
    } else if (guest100 != null) {
      weights = { firstHand: 0, critics: 0, guests: 100 };
      overallIndex = guest100;
      greatStayOdds = guest100;
      statusBadge = "Verified Guest Score";
      statusTone = "teal";
      formulaSummary = "100% Verified Guest Ratings";
    } else if (critic100 != null) {
      weights = { firstHand: 0, critics: 100, guests: 0 };
      overallIndex = critic100;
      greatStayOdds = critic100;
      statusBadge = "Critic Reviewed";
      statusTone = "slate";
      formulaSummary = "100% Published Critic Reviews — open breakdown for live Google reviews.";
    }
  }

  // Agreement / Difference badges ONLY unlock when >= 2 real numeric scores exist
  if (sourceCount >= 2 && overallIndex != null) {
    isConsensusBadge = true;
    spread100 = Math.max(...activeScores) - Math.min(...activeScores);
    if (spread100 <= 6) {
      statusBadge = "Strong Agreement";
      statusTone = "accent";
      greatStayOdds = Math.min(98, overallIndex + 2);
    } else if (spread100 <= 12) {
      statusBadge = "Mostly Aligned";
      statusTone = "teal";
      greatStayOdds = overallIndex;
    } else {
      statusBadge = "Opinions Differ";
      statusTone = "amber";
      greatStayOdds = Math.max(50, overallIndex - 4);
    }
  }

  // Dual-Mode Opinion Gap Module ("My Score vs Real Guests" OR "Published Critics vs Real Guests")
  const left100 = firstHand ? ours100 : critic100;
  const right100 = guest100;
  const delta100 = left100 != null && right100 != null ? left100 - right100 : null;

  let gapHeadline = firstHand
    ? "My first-hand stay notes below — open breakdown to compare with live Google guest reviews."
    : officialAwards.length > 0
    ? `Recognised with ${officialAwards.map((a) => a.label).join(" • ")} — compare with real guest reviews below.`
    : "Compare verified guest reviews and linked video tours below.";

  if (delta100 != null) {
    const criticName =
      scoredEditorial.length === 1 ? primaryCritic.sourceName : `${scoredEditorial.length} published critics`;
    if (Math.abs(delta100) <= 5) {
      gapHeadline = firstHand
        ? `Tight agreement (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — my stay matched real guest reviews.`
        : `Tight agreement (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — ${criticName} and real guests agree.`;
    } else if (delta100 > 5) {
      gapHeadline = firstHand
        ? `I rated this +${delta100} pts higher than real guests — see what I loved below.`
        : `${criticName} rated this +${delta100} pts higher than real guests.`;
    } else {
      gapHeadline = firstHand
        ? `I rated this ${delta100} pts stricter than real guests — see what stood out & what held it back.`
        : `Real guests rated this +${Math.abs(delta100)} pts higher than ${criticName}.`;
    }
  }

  const leftDisplay = firstHand
    ? personalScore25 != null
      ? `${personalScore25} / 25`
      : `${formatPersonalScore(hotel.overall)} / 5`
    : scoredEditorial.length === 1
    ? primaryCritic.rawScore || `${critic100} / 100`
    : scoredEditorial.length > 1
    ? `${critic100} / 100 (${scoredEditorial.length} critics)`
    : "No critic score";

  const opinionGap = {
    mode: firstHand ? "my_vs_guests" : "critics_vs_guests",
    title: firstHand ? "My Score vs. Real Guest Score" : "Published Critics vs. Real Guest Score",
    leftLabel: firstHand
      ? "My First-Hand Stay"
      : scoredEditorial.length === 1
      ? primaryCritic.sourceName
      : "Published Critics",
    left100,
    leftDisplay,
    rightLabel: verifiedGuest ? `${verifiedGuest.sourceName}` : "Real Guest Score",
    right100,
    rightDisplay: verifiedGuest
      ? `${verifiedGuest.rating.toFixed(1)} / ${verifiedGuest.scale}`
      : "Open Breakdown",
    delta100,
    deltaLabel: delta100 != null ? `${delta100 > 0 ? "+" : ""}${delta100} pts` : "—",
    headline: gapHeadline,
    narrative: firstHand
      ? hotel.whereWeDiffer || hotel.verdict || ""
      : hotel.standout || hotel.verdict || "",
  };

  return {
    tier: firstHand ? "first_hand_verified" : visited ? "short_preview" : "global_directory",
    tierLabel: firstHand
      ? "First-Hand Verified"
      : visited
      ? "Short Tour Preview"
      : "Global Directory",
    firstHand,
    visited,
    personalScore25,
    ours100,
    critic100,
    primaryCritic,
    scoredEditorial,
    guest100,
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
