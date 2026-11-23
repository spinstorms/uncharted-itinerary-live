/**
 * StayOdds — Travel Style subcategories (shared by /compare/ and /hotels/).
 *
 * Zero-fake-data rule: categories are derived ONLY from text already stored on each
 * property (name, location, country, region, standout, verdict, key facts). Nothing is
 * guessed or AI-generated — if a hotel's verified description doesn't mention it, the
 * hotel is simply not tagged.
 */

const NO_REEF_RE = /\b(no\s+(?:house\s+)?reef|not\s+a\s+house[- ]reef|lacks\s+a\s+house\s+reef|no\s+snorkell?ing|minimal\s+(?:natural\s+)?coral)\b/i;
const REEF_RE = /\b(house\s+reef|coral\s+reef|snorkell?ing|snorkel|diving|dive\s+cent(?:er|re)|marine\s+reserve|manta\s+rays?|whale\s+sharks?|sea\s+turtles|barrier\s+reef|fringing\s+reef)\b/i;
const BEACH_RE = /\b(beach|beachfront|sandy\s+bay|white-sand|lagoon|private\s+island|overwater|atoll|oceanfront|seafront|coastal\s+resort|private\s+cove|private\s+peninsula)\b/i;
const OVERWATER_RE = /\b(overwater|over-water|water\s+villas?|water\s+bungalows?)\b/i;
const CITY_RE = /\b(tokyo|paris|london|new\s+york|manhattan|bangkok|singapore|hong\s+kong|seoul|madrid|rome|milan|florence|venice|dubai|doha|abu\s+dhabi|kuala\s+lumpur|sydney|melbourne|chicago|los\s+angeles|beverly\s+hills|west\s+hollywood|san\s+francisco|boston|washington|toronto|vancouver|mexico\s+city|buenos\s+aires|santiago|lima|s[aã]o\s+paulo|lisbon|barcelona|amsterdam|vienna|zurich|geneva|munich|berlin|istanbul|athens|cairo|johannesburg|mumbai|new\s+delhi|shanghai|beijing|taipei|osaka|kyoto)\b/i;
const CULTURE_RE = /\b(heritage|historic|palace|castle|ch[aâ]teau|monastery|convents?|temple|shrine|unesco|museum|renaissance|belle\s+[eé]poque|riad|medina|grand\s+dame|1[6-9]th-century|kyoto|rome|florence|venice|paris|vienna|istanbul|athens|marrakec?h|marrakesh|udaipur|jaipur|jodhpur|cusco|machu\s+picchu|san\s+miguel\s+de\s+allende|ubud|luang\s+prabang|angkor|siem\s+reap)\b/i;
const SAFARI_RE = /\b(safari|wildlife|game\s+reserve|masai\s+mara|serengeti|kruger|sabi\s+sand|okavango|shamwari|singita|tented\s+camp|rainforest|cloud\s+forest|national\s+park|conservancy|canyon|desert\s+dunes|red\s+dunes|empty\s+quarter|volcano|arenal|patagonia|atacama|gal[aá]pagos|jungle)\b/i;
const MOUNTAIN_RE = /\b(mountain|alpine|alps|ski|ski-in|dolomites|chalet|glacier|himalaya|andes|rockies|aspen|courchevel|st\.?\s*moritz|zermatt|gstaad|whistler|banff|jackson\s+hole|big\s+sky|moonlight\s+basin|park\s+city|deer\s+valley|telluride|vail)\b/i;
const WELLNESS_RE = /\b(spa|wellness|onsen|hot\s+springs?|thermal|hammam|ayurveda|hydrotherapy|sensei|longevity|meditation|holistic)\b/i;
const ALL_INCLUSIVE_RE = /\b(all-inclusive|all\s+inclusive|full\s+board\s+included)\b/i;

function posText(h) {
  const kf = h.keyFacts || {};
  return [h.name, h.location, h.country, h.region, h.priceRange, h.standout, h.verdict, kf.beachOrReef]
    .filter(Boolean)
    .join(" ");
}

function placeText(h) {
  return [h.name, h.location, h.country, h.standout].filter(Boolean).join(" ");
}

export const TRAVEL_STYLES = [
  { id: "all", label: "All Styles", icon: "", match: () => true },
  {
    id: "beach",
    label: "Beach Resorts",
    icon: "🏖️",
    match: (h) => BEACH_RE.test(posText(h)) || h.region === "Maldives" || h.region === "Bora Bora",
  },
  {
    id: "snorkel",
    label: "Snorkelling & Reef",
    icon: "🤿",
    match: (h) => {
      const kfReef = (h.keyFacts && h.keyFacts.beachOrReef) || "";
      const p = [h.name, h.standout, h.verdict, kfReef].filter(Boolean).join(" ");
      if (NO_REEF_RE.test(p) || NO_REEF_RE.test(h.watchOut || "")) {
        if (!REEF_RE.test(kfReef) || NO_REEF_RE.test(kfReef)) return false;
      }
      return REEF_RE.test(p);
    },
  },
  {
    id: "overwater",
    label: "Overwater Villas",
    icon: "🛖",
    match: (h) => OVERWATER_RE.test(posText(h)) || h.region === "Maldives" || h.region === "Bora Bora",
  },
  {
    id: "city",
    label: "City Breaks",
    icon: "🏙️",
    match: (h) =>
      !["Maldives", "Bora Bora", "Caribbean"].includes(h.region) &&
      CITY_RE.test([h.location, h.name].filter(Boolean).join(" ")),
  },
  { id: "culture", label: "Culture & Heritage", icon: "🏛️", match: (h) => CULTURE_RE.test(posText(h)) },
  { id: "safari", label: "Safari & Nature", icon: "🦁", match: (h) => SAFARI_RE.test(placeText(h)) },
  { id: "mountain", label: "Mountain & Ski", icon: "🏔️", match: (h) => MOUNTAIN_RE.test(placeText(h)) },
  { id: "wellness", label: "Spa & Wellness", icon: "🧖", match: (h) => WELLNESS_RE.test(posText(h)) },
  { id: "allinclusive", label: "All-Inclusive", icon: "🍹", match: (h) => ALL_INCLUSIVE_RE.test(posText(h)) },
];

export function getTravelStyle(id) {
  return TRAVEL_STYLES.find((s) => s.id === id) || TRAVEL_STYLES[0];
}

export function matchesTravelStyle(h, id) {
  if (!id || id === "all") return true;
  return getTravelStyle(id).match(h);
}
