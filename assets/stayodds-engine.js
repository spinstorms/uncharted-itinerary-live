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
      entry.sourceName.trim().length > 0 &&
      entry.normalized100 != null &&
      !Number.isNaN(Number(entry.normalized100))
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
    if (typeof data.rating !== "number") return null;
    return data;
  } catch {
    return null;
  }
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

  const ours100 = firstHand ? Math.round(Number(hotel.overall) * 20) : null;

  // Combine sourced editorial ratings + scored official awards (both strictly require sourceUrl)
  const scoredCriticInputs = [
    ...editorialRatings.map((r) => Number(r.normalized100)),
    ...officialAwards
      .filter((a) => a.normalized100 != null && !Number.isNaN(Number(a.normalized100)))
      .map((a) => Number(a.normalized100)),
  ];
  const critic100 =
    scoredCriticInputs.length > 0
      ? Math.round(scoredCriticInputs.reduce((acc, v) => acc + v, 0) / scoredCriticInputs.length)
      : null;

  const guest100 = verifiedGuest ? verifiedGuest.normalized100 : null;

  let weights = { firstHand: 0, critics: 0, guests: 0 };
  let overallIndex = null;
  let greatStayOdds = null;
  let spread100 = null;
  let statusBadge = "Live Ratings Pending";
  let statusTone = "slate";
  let isConsensusBadge = false;
  let formulaSummary = "Awaiting live verified guest ratings & sourced critic links.";

  const activeScores = [ours100, critic100, guest100].filter((v) => v != null);
  const sourceCount = activeScores.length;

  if (firstHand) {
    if (critic100 != null && guest100 != null) {
      weights = { firstHand: 40, critics: 30, guests: 30 };
      overallIndex = Math.round(ours100 * 0.4 + critic100 * 0.3 + guest100 * 0.3);
      formulaSummary = "40% First-Hand Stay • 30% Sourced Critics & Awards • 30% Live Verified Guests";
    } else if (guest100 != null) {
      weights = { firstHand: 55, critics: 0, guests: 45 };
      overallIndex = Math.round(ours100 * 0.55 + guest100 * 0.45);
      formulaSummary = "55% First-Hand Stay • 45% Live Verified Guests (auto-reweighted)";
    } else if (critic100 != null) {
      weights = { firstHand: 55, critics: 45, guests: 0 };
      overallIndex = Math.round(ours100 * 0.55 + critic100 * 0.45);
      formulaSummary = "55% First-Hand Stay • 45% Sourced Critics & Awards (auto-reweighted)";
    } else {
      weights = { firstHand: 100, critics: 0, guests: 0 };
      overallIndex = ours100;
      greatStayOdds = ours100;
      statusBadge = "First-Hand Only";
      statusTone = "accent";
      formulaSummary = "100% First-Hand Verified Stay — open breakdown for live Google guest rating.";
    }
  } else {
    if (critic100 != null && guest100 != null) {
      if (scoredCriticInputs.length >= 2) {
        weights = { firstHand: 0, critics: 40, guests: 60 };
        overallIndex = Math.round(critic100 * 0.4 + guest100 * 0.6);
        formulaSummary = "40% Sourced Critics & Awards (2+) • 60% Live Verified Guests";
      } else {
        weights = { firstHand: 0, critics: 25, guests: 75 };
        overallIndex = Math.round(critic100 * 0.25 + guest100 * 0.75);
        formulaSummary = "25% Sourced Critic/Award • 75% Live Verified Guests";
      }
    } else if (guest100 != null) {
      weights = { firstHand: 0, critics: 0, guests: 100 };
      overallIndex = guest100;
      greatStayOdds = guest100;
      statusBadge = "Guest Data Only";
      statusTone = "teal";
      formulaSummary = "100% Live Verified Guest Ratings (no sourced critic/award score linked yet).";
    } else if (critic100 != null) {
      weights = { firstHand: 0, critics: 100, guests: 0 };
      overallIndex = critic100;
      greatStayOdds = critic100;
      statusBadge = "Editorial Only";
      statusTone = "slate";
      formulaSummary = "100% Sourced Editorial & Official Awards (live guest ratings pending).";
    }
  }

  // Consensus status badges unlock ONLY when >= 2 verified numeric layers exist
  if (sourceCount >= 2 && overallIndex != null) {
    isConsensusBadge = true;
    spread100 = Math.max(...activeScores) - Math.min(...activeScores);
    if (spread100 <= 6) {
      statusBadge = "Strong Consensus";
      statusTone = "accent";
      greatStayOdds = Math.min(98, overallIndex + 2);
    } else if (spread100 <= 12) {
      statusBadge = "Mostly Aligned";
      statusTone = "teal";
      greatStayOdds = overallIndex;
    } else {
      statusBadge = "Split Verdict";
      statusTone = "amber";
      greatStayOdds = Math.max(50, overallIndex - 4);
    }
  }

  // Dual-Mode Opinion Gap Module ("My Score vs Real Guests" OR "Critics & Awards vs Real Guests")
  const left100 = firstHand ? ours100 : critic100;
  const right100 = guest100;
  const delta100 = left100 != null && right100 != null ? left100 - right100 : null;

  let gapHeadline = firstHand
    ? "Awaiting live guest rating to calculate My Score vs. Crowd delta"
    : "Awaiting both sourced critics/awards and live guest rating";
  if (delta100 != null) {
    if (Math.abs(delta100) <= 5) {
      gapHeadline = firstHand
        ? `Tight agreement (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — my stay matched real guest scores`
        : `Hype matches reality (${delta100 >= 0 ? `+${delta100}` : delta100} pts) — critics & guests agree`;
    } else if (delta100 > 5) {
      gapHeadline = firstHand
        ? `I rated this +${delta100} pts higher than real guests`
        : `Critics & awards rate this +${delta100} pts higher than real guests (Watch for hype)`;
    } else {
      gapHeadline = firstHand
        ? `I rated this ${delta100} pts stricter than real guests — read caveats`
        : `Real guests rate this +${Math.abs(delta100)} pts higher than critics (Quiet overachiever)`;
    }
  }

  const opinionGap = {
    mode: firstHand ? "my_vs_guests" : "critics_vs_guests",
    title: firstHand ? "My Score vs. Real Guest Score" : "Critics & Official Awards vs. Real Guest Score",
    leftLabel: firstHand ? "My First-Hand Stay" : "Critics & Official Awards",
    left100,
    leftDisplay: firstHand
      ? `${formatPersonalScore(hotel.overall)} / 5`
      : critic100 != null
      ? `${critic100} / 100`
      : "0 sourced yet",
    rightLabel: verifiedGuest ? `${verifiedGuest.sourceName}` : "Real Guest Score",
    right100,
    rightDisplay: verifiedGuest
      ? `${verifiedGuest.rating.toFixed(1)} / ${verifiedGuest.scale}`
      : "Live API",
    delta100,
    deltaLabel: delta100 != null ? `${delta100 > 0 ? "+" : ""}${delta100} pts` : "Pending",
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
    ours100,
    critic100,
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
