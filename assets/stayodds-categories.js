/**
 * StayOdds — Travel Style subcategories (shared by /compare/ and /hotels/).
 *
 * Strict Zero-Fake-Data Rule:
 * - Categories are derived ONLY from verified text already stored on each property
 *   (name, location, country, region, priceRange, standout, verdict, watchOut, keyFacts).
 * - Negative/contradictory statements (e.g. "no beach", "no house reef", "Optional All-Inclusive")
 *   and mountain/alpine/inland-city properties are strictly excluded from Beach Resorts.
 */

const NO_BEACH_RE =
  /\b(no\s+(?:swimmable\s+)?(?:resort\s+)?beach|not\s+on\s+the\s+beach|not\s+(?:a\s+)?beachfront|inland\s+mountain|inland\s+unesco|beach\s+road|alpine\s*\/\s*ski)\b/i;
const BEACH_RE =
  /\b(beachfront|white-sand|sandy\s+bay|private\s+island|atoll|oceanfront|seafront|coastal\s+resort|private\s+cove|private\s+peninsula|swimmable\s+beach|beach\s+club|beach\s+villas?|beach\s+resort)\b/i;

const NO_REEF_RE =
  /\b(no\s+(?:house\s+)?reef|not\s+a\s+house[- ]reef|lacks\s+a\s+house\s+reef|no\s+snorkell?ing|minimal\s+(?:natural\s+)?coral|poor\s+reef|dead\s+reef)\b/i;
const REEF_RE =
  /\b(house\s+reef|coral\s+reef|snorkell?ing|snorkel|diving|dive\s+cent(?:er|re)|marine\s+reserve|manta\s+rays?|whale\s+sharks?|sea\s+turtles|barrier\s+reef|fringing\s+reef)\b/i;

// Strictly overwater ACCOMMODATIONS — never overwater cabanas, sun decks, spas, piers, or restaurants
const OVERWATER_VILLA_RE =
  /\b(over-?water\s+(?:[a-z0-9&-]+\s+){0,3}(?:villas?|bungalows?|suites?|reserves?|residences?|retreats?)|water\s+(?:villas?|bungalows?|reserves?))\b/i;
const NO_OVERWATER_RE = /\b(no\s+over-?water|beach[- ]only|all[- ]beach)\b/i;

const CITY_RE =
  /\b(tokyo|paris|london|new\s+york|manhattan|bangkok|singapore|hong\s+kong|seoul|madrid|rome|milan|florence|venice|dubai|doha|abu\s+dhabi|kuala\s+lumpur|sydney|melbourne|chicago|los\s+angeles|beverly\s+hills|west\s+hollywood|san\s+francisco|boston|washington|toronto|vancouver|mexico\s+city|buenos\s+aires|santiago|lima|s[aã]o\s+paulo|lisbon|barcelona|amsterdam|vienna|zurich|geneva|munich|berlin|istanbul|athens|cairo|johannesburg|mumbai|new\s+delhi|shanghai|beijing|taipei|osaka|kyoto)\b/i;
const NON_CITY_LOCATION_RE =
  /\b(desert\s+conservation|vancouver\s+island|private\s+island|nurai\s+island|wilderness\s+lodge|athens\s+riviera)\b/i;

// Inland cities, lakes, mountains, valleys & deserts that must NEVER match Beach Resorts
const STRICT_NON_BEACH_LOC_RE =
  /\b(courchevel|st\.?\s*moritz|zermatt|gstaad|andermatt|aspen|vail|deer\s+valley|jackson\s+hole|whistler|banff|niseko|dolomites|meg[eè]ve|chamonix|verbier|lech|kitzb|big\s+sky|moonlight\s+basin|hakone|kyoto|tokyo|osaka|seoul|taipei|bangkok|kuala\s+lumpur|singapore|hong\s+kong|shanghai|beijing|paris|london|madrid|milan|florence|rome|vienna|zurich|geneva|munich|berlin|amsterdam|new\s+york|manhattan|chicago|las\s+vegas|beverly\s+hills|west\s+hollywood|mexico\s+city|mendoza|cusco|san\s+miguel\s+de\s+allende|marrakec?h|jaipur|udaipur|jodhpur|new\s+delhi|hyderabad|bengaluru|luxor|cairo|giza|alula|chiang\s+mai|chiang\s+rai|ubud|cotswolds|wiltshire|gleneagles|serengeti|masai\s+mara|kruger|okavango|botswana|rwanda|namibia|atacama|patagonia|douro\s+valley|montalcino|lake\s+como|moltrasio|cernobbio|tremezzo|lago\s+di\s+como|chochol[aá])\b/i;

const CULTURE_RE =
  /\b(heritage|historic|palace|castle|ch[aâ]teau|monastery|convents?|temple|shrine|museum|renaissance|belle\s+[eé]poque|riad|medina|grand\s+dame|1[6-9]th-century|kyoto|rome|florence|venice|paris|vienna|istanbul|athens|marrakec?h|marrakesh|udaipur|jaipur|jodhpur|cusco|machu\s+picchu|san\s+miguel\s+de\s+allende|ubud|luang\s+prabang|angkor|siem\s+reap)\b/i;
const CULTURE_FALSE_POS_RE =
  /\b(castle\s+harbour|castle-and-village|official\s+french\s+palace|unesco\s+(?:biosphere|coastal|marine))\b/i;

const SAFARI_NATURE_RE =
  /\b(safari\s+(?:lodge|camp|tents?)|big\s+five|big-game|game\s+reserve|masai\s+mara|serengeti|kruger|sabi\s+sand|okavango|shamwari|singita|tented\s+camp|tented\s+lodge|tented\s+sanctuary|cloud\s+forest|conservancy|sandstone\s+mesa|desert\s+dunes|red\s+dunes|empty\s+quarter|desert\s+resort|arenal|patagonia|atacama|gal[aá]pagos|nyungwe|yala\s+national\s+park|banff\s+national\s+park|ise-shima\s+national\s+park|n[uú]i\s+ch[uú]a\s+national\s+park|wilderness\s+lodge|rainforest\s+(?:valley|clifftop|canopy|treehouse|meets-beach)|bamboo-jungle|jungle\s+(?:hideaway|pavilions?|pool\s+villas?|riverside))\b/i;

const MOUNTAIN_SKI_RE =
  /\b(ski-in|ski\s+valet|ski\s+lodge|ski\s+resort|alpine|alps|dolomites|chalet|glacier|himalaya[sn]?|andes|rockies|aspen|courchevel|st\.?\s*moritz|zermatt|gstaad|andermatt|whistler|banff|jackson\s+hole|big\s+sky|moonlight\s+basin|park\s+city|deer\s+valley|telluride|vail|niseko|meg[eè]ve|chamonix|verbier|blackberry\s+mountain|highland\s+rainforest\s+mountain|inland\s+mountain\s+pine)\b/i;

const WELLNESS_BODY_RE =
  /\b(spa|wellness|wellbeing|onsen|hot\s+springs?|thermal|hammam|ayurveda|hydrotherapy|longevity|meditation|holistic)\b/i;
const WELLNESS_BRAND_RE =
  /\b(joali\s+being|sensei|como\s+shambhala|chiva-som|canyon\s+ranch|clinique\s+la\s+prairie|palma[ïi]a|euphoria\s+retreat|ananda\s+in\s+the\s+himalayas)\b/i;

const ALL_INCLUSIVE_RE = /\b(all-inclusive|all\s+inclusive|full\s+board\s+included)\b/i;
const NOT_AI_RE =
  /\b(optional\s+all[- ]inclusive|not\s+(?:an?\s+)?all[- ]inclusive|non[- ]all[- ]inclusive|vs\.?\s*all[- ]inclusive|unlike\s+all[- ]inclusive)\b/i;

function posText(h) {
  const kf = h.keyFacts || {};
  return [h.name, h.location, h.country, h.region, h.priceRange, h.standout, h.verdict, kf.beachOrReef]
    .filter(Boolean)
    .join(" ");
}

function placeText(h) {
  const kf = h.keyFacts || {};
  return [h.name, h.location, h.country, h.standout, kf.beachOrReef].filter(Boolean).join(" ");
}

export const TRAVEL_STYLES = [
  { id: "all", label: "All Styles", iconKey: "", match: () => true },
  {
    id: "beach",
    label: "Beach Resorts",
    iconKey: "waves",
    match: (h) => {
      const kfReef = (h.keyFacts && h.keyFacts.beachOrReef) || "";
      const locName = [h.name, h.location, h.country].filter(Boolean).join(" ");
      // Hard guard: never classify snowy/mountain/ski or strictly inland urban/lake/safari hotels as Beach Resorts
      if (MOUNTAIN_SKI_RE.test(`${locName} ${kfReef}`)) return false;
      if (STRICT_NON_BEACH_LOC_RE.test(locName)) return false;
      const checkNeg = [h.name, kfReef, h.watchOut].filter(Boolean).join(" ");
      if (NO_BEACH_RE.test(checkNeg)) return false;
      if (h.country === "Maldives" || h.region === "Maldives" || h.region === "Bora Bora") return true;
      return BEACH_RE.test(posText(h));
    },
  },
  {
    id: "snorkel",
    label: "Snorkelling & Reef",
    iconKey: "compass",
    match: (h) => {
      const kfReef = (h.keyFacts && h.keyFacts.beachOrReef) || "";
      const locName = [h.name, h.location, h.country].filter(Boolean).join(" ");
      if (MOUNTAIN_SKI_RE.test(`${locName} ${kfReef}`)) return false;
      if (STRICT_NON_BEACH_LOC_RE.test(locName)) return false;
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
    iconKey: "home",
    match: (h) => {
      const full = `${posText(h)} ${h.watchOut || ""}`;
      if (NO_OVERWATER_RE.test(full)) return false;
      if (h.country === "Maldives" || h.region === "Maldives") return true;
      if (/bora\s+bora/i.test(`${h.location || ""} ${h.name || ""}`)) return true;
      return OVERWATER_VILLA_RE.test(posText(h));
    },
  },
  {
    id: "city",
    label: "City Breaks",
    iconKey: "building",
    match: (h) => {
      if (["Maldives", "Bora Bora", "Caribbean"].includes(h.region)) return false;
      const locName = [h.location, h.name].filter(Boolean).join(" ");
      if (NON_CITY_LOCATION_RE.test(`${locName} ${h.standout || ""}`)) return false;
      return CITY_RE.test(locName);
    },
  },
  {
    id: "culture",
    label: "Culture & Heritage",
    iconKey: "landmark",
    match: (h) => {
      const cleaned = posText(h).replace(CULTURE_FALSE_POS_RE, "");
      return CULTURE_RE.test(cleaned);
    },
  },
  {
    id: "safari",
    label: "Safari & Nature",
    iconKey: "trees",
    match: (h) => SAFARI_NATURE_RE.test(placeText(h)),
  },
  {
    id: "mountain",
    label: "Mountain & Ski",
    iconKey: "mountain",
    match: (h) => MOUNTAIN_SKI_RE.test(placeText(h)),
  },
  {
    id: "wellness",
    label: "Spa & Wellness",
    iconKey: "droplets",
    match: (h) => {
      const kf = h.keyFacts || {};
      const body = [h.standout, h.verdict, kf.poolHeating].filter(Boolean).join(" ");
      return WELLNESS_BODY_RE.test(body) || WELLNESS_BRAND_RE.test(h.name || "");
    },
  },
  {
    id: "allinclusive",
    label: "All-Inclusive",
    iconKey: "utensils",
    match: (h) => {
      const full = `${posText(h)} ${h.watchOut || ""}`;
      if (NOT_AI_RE.test(full)) return false;
      return ALL_INCLUSIVE_RE.test(posText(h));
    },
  },
];

export function getTravelStyle(id) {
  return TRAVEL_STYLES.find((s) => s.id === id) || TRAVEL_STYLES[0];
}

export function matchesTravelStyle(h, id) {
  if (!id || id === "all") return true;
  return getTravelStyle(id).match(h);
}
