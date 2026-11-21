/**
 * StayOdds — Centralized Brand Config, Source-URL Enforcement & Dynamic Confidence-Weighted Engine
 *
 * Strict integrity rules:
 * 1. Zero AI-estimated or hardcoded external scores are ever read or fabricated.
 * 2. No third-party critic, editorial rating, official award, or YouTube review may render
 *    unless it includes a real HTTP(S) `sourceUrl`.
 * 3. Consensus status badges ("Strong Consensus", "Mostly Aligned", "Split Verdict") are ONLY
 *    assigned when >= 2 independent verified numeric layers exist.
 */

export const BRAND = Object.freeze({
  name: "StayOdds",
  appStoreTitle: "StayOdds: Hotel Score Compare",
  subtitle: "Critics vs Real Guest Reviews",
  foundingContributor: "The Uncharted Itinerary",
  foundingContributorUrl: "https://www.uncharteditinerary.com/",
  bundleId: "com.stayodds.app",
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
 * Kept strictly separate from numeric editorial scores (creator link + stated sentiment).
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
 * Reads ONLY live/verified API guest ratings (never legacy AI-estimated consensus fields).
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
      verifiedAt: vg.google.verifiedAt || null,
      attribution: "Powered by Google",
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
    };
  }

  return null;
}

/**
 * Dynamic Confidence-Weighted StayOdds Calculation
 *
 * Tier 1 — First-Hand Verified (Visited & Scored):
 *   - All 3 layers (First-Hand + Verified Critics + Verified Guests): 40% / 30% / 30%
 *   - First-Hand + Verified Guests only: 55% / 45%
 *   - First-Hand + Verified Critics only: 55% / 45%
 *   - First-Hand only (no external live layers yet): 100% First-Hand -> badge "First-Hand Only"
 *
 * Tier 2 — Global Directory / Short Preview (No First-Hand Score):
 *   - >=2 Verified Critics + Verified Guests: 40% Critics / 60% Guests
 *   - 1 Verified Critic + Verified Guests: 25% Critics / 75% Guests
 *   - 0 Verified Critics + Verified Guests: 100% Guests -> badge "Guest Data Only"
 *   - Verified Critics only: 100% Critics -> badge "Editorial Only"
 *   - 0 Verified Numeric Sources yet: null -> badge "Live Ratings Pending"
 */
export function computeStayOdds(hotel) {
  const firstHand = isFirstHandVerified(hotel);
  const visited = isVisitedProperty(hotel);
  const editorialRatings = getVerifiedEditorialRatings(hotel);
  const youtubeReviews = getVerifiedYoutubeReviews(hotel);
  const officialAwards = getVerifiedAwards(hotel);
  const verifiedGuest = getVerifiedGuestScore(hotel);

  const ours100 = firstHand ? Math.round(Number(hotel.overall) * 20) : null;
  const critic100 =
    editorialRatings.length > 0
      ? Math.round(
          editorialRatings.reduce((acc, item) => acc + Number(item.normalized100), 0) /
            editorialRatings.length
        )
      : null;
  const guest100 = verifiedGuest ? verifiedGuest.normalized100 : null;

  let weights = { firstHand: 0, critics: 0, guests: 0 };
  let overallIndex = null;
  let greatStayOdds = null;
  let spread100 = null;
  let statusBadge = "Live Ratings Pending";
  let statusTone = "slate"; // "accent" | "teal" | "amber" | "slate"
  let isConsensusBadge = false;
  let formulaSummary = "Awaiting live verified guest ratings & sourced critic links (Phase 1B).";

  const activeScores = [ours100, critic100, guest100].filter((v) => v != null);
  const sourceCount = activeScores.length;

  if (firstHand) {
    if (critic100 != null && guest100 != null) {
      weights = { firstHand: 40, critics: 30, guests: 30 };
      overallIndex = Math.round(ours100 * 0.4 + critic100 * 0.3 + guest100 * 0.3);
      formulaSummary = "40% First-Hand Stay • 30% Sourced Critics • 30% Live Verified Guests";
    } else if (guest100 != null) {
      weights = { firstHand: 55, critics: 0, guests: 45 };
      overallIndex = Math.round(ours100 * 0.55 + guest100 * 0.45);
      formulaSummary = "55% First-Hand Stay • 45% Live Verified Guests (auto-reweighted; no critic score linked yet)";
    } else if (critic100 != null) {
      weights = { firstHand: 55, critics: 45, guests: 0 };
      overallIndex = Math.round(ours100 * 0.55 + critic100 * 0.45);
      formulaSummary = "55% First-Hand Stay • 45% Sourced Critics (auto-reweighted; live guest feed pending)";
    } else {
      weights = { firstHand: 100, critics: 0, guests: 0 };
      overallIndex = ours100;
      greatStayOdds = ours100;
      statusBadge = "First-Hand Only";
      statusTone = "accent";
      formulaSummary = "100% First-Hand Verified Stay — external live guest API connects in Phase 1B.";
    }
  } else {
    if (critic100 != null && guest100 != null) {
      if (editorialRatings.length >= 2) {
        weights = { firstHand: 0, critics: 40, guests: 60 };
        overallIndex = Math.round(critic100 * 0.4 + guest100 * 0.6);
        formulaSummary = "40% Sourced Critics (2+ outlets) • 60% Live Verified Guests";
      } else {
        weights = { firstHand: 0, critics: 25, guests: 75 };
        overallIndex = Math.round(critic100 * 0.25 + guest100 * 0.75);
        formulaSummary = "25% Sourced Critic (1 outlet) • 75% Live Verified Guests";
      }
    } else if (guest100 != null) {
      weights = { firstHand: 0, critics: 0, guests: 100 };
      overallIndex = guest100;
      greatStayOdds = guest100;
      statusBadge = "Guest Data Only";
      statusTone = "teal";
      formulaSummary = "100% Live Verified Guest Ratings (no sourced critic ratings logged yet).";
    } else if (critic100 != null) {
      weights = { firstHand: 0, critics: 100, guests: 0 };
      overallIndex = critic100;
      greatStayOdds = critic100;
      statusBadge = "Editorial Only";
      statusTone = "slate";
      formulaSummary = "100% Sourced Editorial Ratings (live guest ratings pending).";
    }
  }

  // Only compute Consensus Status Badges when >= 2 independent verified numeric layers exist
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
    editorialRatings,
    youtubeReviews,
    officialAwards,
    verifiedGuest,
  };
}
