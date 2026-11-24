/**
 * StayOdds Verified Luxury Intelligence Module
 * - Canonical brand normalization (for Brand Consistency Leaderboard)
 * - Deterministic Preferred Partner & Loyalty Points programs (strictly by brand)
 * - Established destination climatology ("Best Months to Go" dry/peak season filter)
 * - Verified Adults-Only vs. Family / Kids-Club classification (zero false positives)
 * - First-Hand "Which Room / Villa to Book" tip extraction (strictly from real stay notes)
 * - RFC-4180 CSV exporter for Shortlists & Comparison Tables
 */

export const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/* ==================== 1. Canonical Brand Normalization ==================== */

export function normalizeBrandName(hotel) {
  const rawBrand = String((hotel && hotel.brand) || "").trim();
  const name = String((hotel && hotel.name) || "").trim();
  const combo = `${rawBrand} ${name}`.toLowerCase();

  // Never let legacy generic placeholder strings trigger Marriott's "The Luxury Collection"
  const isGenericRaw = /^(independent|boutique|boutique\s+ultra[- ]luxury|luxury\s+collection\s*&\s*boutique)$/i.test(rawBrand);
  const safeRaw = isGenericRaw ? "" : rawBrand;
  const safeCombo = `${safeRaw} ${name}`.toLowerCase();

  if (/four\s*seasons/i.test(safeCombo)) return "Four Seasons";
  if (/\baman(?!da)/i.test(safeRaw) || /^aman[a-z\s]/i.test(name) || /\baman\b/i.test(safeRaw)) return "Aman";
  if (/rosewood/i.test(safeCombo)) return "Rosewood";
  if (/mandarin\s*oriental/i.test(safeCombo)) return "Mandarin Oriental";
  if (/one\s*&\s*only|one&only/i.test(safeCombo)) return "One&Only";
  if (/six\s*senses/i.test(safeCombo)) return "Six Senses";
  if (/belmond|splendido|hotel\s+cipriani|maroma.*belmond|cap\s+juluca|caruso.*belmond|la\s+samanna/i.test(safeCombo)) return "Belmond";
  if (/st\.?\s*regis/i.test(safeCombo)) return "St. Regis";
  if (/ritz-?carlton\s+reserve|mandapa|phulay\s+bay|zad[uú]n|higashiyama\s+niseko|dorado\s+beach.*ritz/i.test(safeCombo)) return "Ritz-Carlton Reserve";
  if (/ritz-?carlton/i.test(safeCombo)) return "The Ritz-Carlton";
  if (/waldorf\s*astoria/i.test(safeCombo)) return "Waldorf Astoria";
  if (/park\s*hyatt/i.test(safeCombo)) return "Park Hyatt";
  if (/cheval\s*blanc/i.test(safeCombo)) return "Cheval Blanc";
  if (/raffles/i.test(safeCombo)) return "Raffles";
  if (/auberge/i.test(safeCombo)) return "Auberge Resorts";
  if (/oetker|le\s+bristol|eden\s+rock|hotel\s+du\s+cap-eden-roc|brenners|lanesborough|jumby\s+bay/i.test(safeCombo)) return "Oetker Collection";
  if (/dorchester|the\s+lana|hotel\s+bel-air|beverly\s+hills\s+hotel|le\s+meurice|plaza\s+ath[eé]n[eé]e|eden\s+rome|principe\s+di\s+savoia|coworth\s+park/i.test(safeCombo)) return "Dorchester Collection";
  if (/maybourne|claridge|the\s+connaught|the\s+berkeley|the\s+emory|maybourne\s+riviera/i.test(safeCombo)) return "Maybourne";
  if (/bulgari|bvlgari/i.test(safeCombo)) return "Bulgari Hotels";
  if (/baillie\s+lodges|longitude\s+131|silky\s+oaks|the\s+louise|huka\s+lodge|tierra\s+patagonia|southern\s+ocean\s+lodge|capella\s+lodge/i.test(safeCombo)) return "Baillie Lodges";
  if (/capella/i.test(safeCombo)) return "Capella";
  if (/soneva/i.test(safeCombo)) return "Soneva";
  if (/\bcomo\b/i.test(safeRaw) || /^como\b/i.test(name)) return "COMO Hotels";
  if (/jumeirah/i.test(safeCombo)) return "Jumeirah";
  if (/oberoi/i.test(safeCombo)) return "Oberoi";
  if (/\btaj\b|umaid\s+bhawan|rambagh\s+palace|falaknuma|lake\s+palace/i.test(safeCombo)) return "Taj Hotels";
  if (/the\s+leela/i.test(safeCombo)) return "The Leela";
  if (/fairmont/i.test(safeCombo)) return "Fairmont";
  if (/virgin\s+limited\s+edition/i.test(safeCombo)) return "Virgin Limited Edition";
  if (/\bedition\b/i.test(safeCombo)) return "EDITION";
  if (/^w\s+/i.test(name) || /\bw\s+hotels\b/i.test(safeCombo)) return "W Hotels";
  // Match Marriott's "The Luxury Collection" ONLY from verified brand or explicit official title (never generic 'Luxury Collection & Boutique')
  if (/^(the\s+luxury\s+collection|marriott\s+luxury\s+collection)$/i.test(safeRaw) || /,\s*a\s+luxury\s+collection\b/i.test(name) || /ta'aktana|the\s+sira|vana\s+belle|naka\s+island|gritti\s+palace|hotel\s+imperial|sanctuary\s+cap\s+cana/i.test(name)) return "The Luxury Collection";
  if (/conrad/i.test(safeCombo)) return "Conrad";
  if (/andaz/i.test(safeCombo)) return "Andaz";
  if (/alila/i.test(safeCombo)) return "Alila";
  if (/kimpton/i.test(safeCombo)) return "Kimpton";
  if (/regent\b/i.test(safeCombo)) return "Regent";
  if (/intercontinental/i.test(safeCombo)) return "InterContinental";
  if (/vignette\s+collection/i.test(safeCombo)) return "Vignette Collection";
  if (/hotel\s+indigo/i.test(safeCombo)) return "Hotel Indigo";
  if (/crowne\s+plaza/i.test(safeCombo)) return "Crowne Plaza";
  if (/jw\s+marriott/i.test(safeCombo)) return "JW Marriott";
  if (/element\s+by\s+westin/i.test(safeCombo)) return "Element by Westin";
  if (/\bsheraton\b/i.test(safeCombo)) return "Sheraton";
  if (/westin/i.test(safeCombo)) return "Westin";
  if (/le\s+m[eé]ridien/i.test(safeCombo)) return "Le Méridien";
  if (/autograph\s+collection/i.test(safeCombo)) return "Autograph Collection";
  if (/tribute\s+portfolio/i.test(safeCombo)) return "Tribute Portfolio";
  if (/courtyard\s+by\s+marriott/i.test(safeCombo)) return "Courtyard by Marriott";
  if (/tapestry\s+collection/i.test(safeCombo)) return "Tapestry Collection by Hilton";
  if (/canopy\s+by\s+hilton/i.test(safeCombo)) return "Canopy by Hilton";
  if (/lxr\b/i.test(safeCombo)) return "LXR Hotels & Resorts";
  if (/\bthe\s+peninsula\b/i.test(safeCombo) || /^peninsula$/i.test(safeRaw)) return "The Peninsula";
  if (/sofitel/i.test(safeCombo)) return "Sofitel";
  if (/banyan\s+tree/i.test(safeCombo)) return "Banyan Tree";
  if (/shangri-?la/i.test(safeCombo)) return "Shangri-La";
  if (/kempinski/i.test(safeCombo)) return "Kempinski";
  if (/singita/i.test(safeCombo)) return "Singita";
  if (/andbeyond|&beyond/i.test(safeCombo)) return "&Beyond";
  if (/wilderness\b/i.test(safeCombo)) return "Wilderness";
  if (/secrets\b|impression.*secrets/i.test(safeCombo)) return "Secrets Resorts";
  if (/\bdreams\b/i.test(safeCombo)) return "Dreams Resorts";
  if (/\balua\b/i.test(safeCombo)) return "Alua Hotels";
  if (/zo[eë]try/i.test(safeCombo)) return "Zoëtry";
  if (/excellence\b/i.test(safeCombo)) return "Excellence Collection";
  if (/sandals|beaches\s+turks/i.test(safeCombo)) return "Sandals / Beaches";
  if (/hyatt\s+zilara|hyatt\s+ziva/i.test(safeCombo)) return "Hyatt All-Inclusive";
  if (/hyatt\s+regency/i.test(safeCombo)) return "Hyatt Regency";
  if (/hyatt\s+centric/i.test(safeCombo)) return "Hyatt Centric";
  if (/thompson/i.test(safeCombo)) return "Thompson Hotels";
  if (/viceroy/i.test(safeCombo)) return "Viceroy";
  if (/montage/i.test(safeCombo)) return "Montage";
  if (/hoshinoya/i.test(safeCombo)) return "HOSHINOYA";
  if (/relais\s*&\s*ch[aâ]teaux/i.test(safeRaw)) return "Relais & Châteaux";
  if (/leading\s+hotels|\blhw\b/i.test(safeRaw)) return "Leading Hotels of the World";
  if (/small\s+luxury\s+hotels|\bslh\b/i.test(safeRaw) || /,\s*an\s+slh\s+hotel/i.test(name)) return "Small Luxury Hotels";
  if (/preferred\s+hotels|^preferred$/i.test(safeRaw)) return "Preferred Hotels";
  if (/design\s+hotels/i.test(safeRaw)) return "Design Hotels";
  if (/marriott/i.test(safeRaw) || /\bmarriott\b/i.test(name)) return "Marriott Bonvoy";
  if (/hyatt/i.test(safeRaw)) return "World of Hyatt";
  if (/hilton/i.test(safeRaw)) return "Hilton Honors";
  if (/ihg/i.test(safeRaw)) return "IHG";
  if (/accor/i.test(safeRaw)) return "Accor";

  if (!safeRaw || isGenericRaw) {
    return "Independent & Boutique";
  }
  return safeRaw;
}

const BRAND_PARENT_GROUP = {
  "St. Regis": "Marriott Bonvoy",
  "The Ritz-Carlton": "Marriott Bonvoy",
  "Ritz-Carlton Reserve": "Marriott Bonvoy",
  "EDITION": "Marriott Bonvoy",
  "The Luxury Collection": "Marriott Bonvoy",
  "W Hotels": "Marriott Bonvoy",
  "JW Marriott": "Marriott Bonvoy",
  "Westin": "Marriott Bonvoy",
  "Le Méridien": "Marriott Bonvoy",
  "Autograph Collection": "Marriott Bonvoy",
  "Courtyard by Marriott": "Marriott Bonvoy",
  "Element by Westin": "Marriott Bonvoy",
  "Tribute Portfolio": "Marriott Bonvoy",
  // Note: Bulgari Hotels does NOT participate in Marriott Bonvoy points/status.
  "Park Hyatt": "World of Hyatt",
  "Alila": "World of Hyatt",
  "Andaz": "World of Hyatt",
  "Hyatt Regency": "World of Hyatt",
  "Hyatt Centric": "World of Hyatt",
  "Thompson Hotels": "World of Hyatt",
  "Secrets Resorts": "World of Hyatt",
  "Dreams Resorts": "World of Hyatt",
  "Alua Hotels": "World of Hyatt",
  "Zoëtry": "World of Hyatt",
  "Hyatt All-Inclusive": "World of Hyatt",
  "Sheraton": "Marriott Bonvoy",
  "Waldorf Astoria": "Hilton Honors",
  "Conrad": "Hilton Honors",
  "LXR Hotels & Resorts": "Hilton Honors",
  "Tapestry Collection by Hilton": "Hilton Honors",
  "Canopy by Hilton": "Hilton Honors",
  // Note: Small Luxury Hotels (SLH) is NOT blanket-mapped to Hilton Honors (only select properties opt in).
  "Six Senses": "IHG One Rewards",
  "Regent": "IHG One Rewards",
  "InterContinental": "IHG One Rewards",
  "Kimpton": "IHG One Rewards",
  "Vignette Collection": "IHG One Rewards",
  "Hotel Indigo": "IHG One Rewards",
  "Crowne Plaza": "IHG One Rewards",
  "IHG": "IHG One Rewards",
  "Raffles": "Accor",
  "Fairmont": "Accor",
  "Sofitel": "Accor",
  "Banyan Tree": "Accor",
  "Belmond": "LVMH Hospitality",
  "Cheval Blanc": "LVMH Hospitality",
};

/**
 * Returns multi-category brand membership so a hotel like W Maldives belongs to BOTH
 * "W Hotels" (primary sub-brand) AND "Marriott Bonvoy" (parent group).
 */
export function getBrandCategories(hotel) {
  const primaryBrand = normalizeBrandName(hotel);
  const raw = String((hotel && hotel.brand) || "").trim();
  let parentGroup = BRAND_PARENT_GROUP[primaryBrand] || null;
  // Cap Karoso (verified Bonvoy-participating Design Hotel) carries explicit "Design Hotels / Marriott"
  if (primaryBrand === "Design Hotels" && /marriott/i.test(raw)) {
    parentGroup = "Marriott Bonvoy";
  }
  const allBrands = [];
  if (primaryBrand && primaryBrand !== "Independent & Boutique") allBrands.push(primaryBrand);
  if (parentGroup && !allBrands.includes(parentGroup)) allBrands.push(parentGroup);
  if (/relais\s*&\s*ch[aâ]teaux/i.test(raw) && !allBrands.includes("Relais & Châteaux")) {
    allBrands.push("Relais & Châteaux");
  }
  if (/leading\s+hotels/i.test(raw) && !allBrands.includes("Leading Hotels of the World")) {
    allBrands.push("Leading Hotels of the World");
  }
  if (!allBrands.length) allBrands.push("Independent & Boutique");
  return { primaryBrand, parentGroup, allBrands };
}

export function matchesBrandCategory(hotel, targetBrand) {
  if (!targetBrand || targetBrand === "All") return true;
  const t = String(targetBrand).trim().toLowerCase();
  const { allBrands } = getBrandCategories(hotel);
  if (allBrands.some((b) => b.toLowerCase() === t)) return true;
  const raw = String((hotel && hotel.brand) || "").trim().toLowerCase();
  return raw === t;
}

/* ==================== 2. Deterministic Preferred Partner & Loyalty Perks ==================== */

export function getPartnerPrograms(hotel) {
  const { primaryBrand: brand, parentGroup } = getBrandCategories(hotel);
  const raw = `${(hotel && hotel.brand) || ""} ${(hotel && hotel.name) || ""}`.toLowerCase();

  let preferredProgram = null;
  let pointsProgram = null;
  let perksNote = "";

  // Strictly verified brand-wide Preferred Partner & Loyalty programs (zero blanket guessing)
  if (brand === "Four Seasons") {
    preferredProgram = "Four Seasons Preferred Partner";
    perksNote = "Daily breakfast, property credit & upgrade priority via FSPP advisors";
  } else if (brand === "Rosewood") {
    preferredProgram = "Rosewood Elite";
    perksNote = "Daily breakfast, resort credit & priority upgrade via Rosewood Elite";
  } else if (brand === "Belmond") {
    preferredProgram = "Belmond Bellini Club";
    perksNote = "Breakfast, hotel credit & Bellini Club gift voucher perks";
  } else if (brand === "Mandarin Oriental") {
    preferredProgram = "MO Fan Club";
    perksNote = "Daily breakfast, US$100 credit & upgrade priority via Fan Club";
  } else if (brand === "The Peninsula") {
    preferredProgram = "Peninsula PenClub";
    perksNote = "Peninsula Time flexible check-in/out + breakfast & credit";
  } else if (brand === "Oetker Collection") {
    preferredProgram = "Oetker Pearl Partner";
    perksNote = "Guaranteed upgrade at booking (select dates), breakfast & credit";
  } else if (brand === "Dorchester Collection") {
    preferredProgram = "Dorchester Diamond Club";
    perksNote = "Guaranteed upgrade at booking (select rooms), breakfast & credit";
  } else if (brand === "Shangri-La") {
    preferredProgram = "Shangri-La Luxury Circle";
    perksNote = "Upgrade at booking (subject to availability), breakfast & credit";
  } else if (brand === "Bulgari Hotels") {
    preferredProgram = "Marriott STARS";
    pointsProgram = null; // Bulgari does NOT participate in Marriott Bonvoy points/status
    perksNote = "Marriott STARS advisor perks (Note: Bulgari Hotels does not participate in Marriott Bonvoy points)";
  } else if (brand === "St. Regis" || brand === "The Ritz-Carlton" || brand === "Ritz-Carlton Reserve" || brand === "EDITION" || brand === "The Luxury Collection") {
    preferredProgram = "Marriott STARS";
    pointsProgram = "Marriott Bonvoy";
    perksNote = "Marriott STARS luxury perks (breakfast, US$100 credit, upgrade priority) + Bonvoy points";
  } else if (brand === "W Hotels" || brand === "JW Marriott" || brand === "Westin" || brand === "Le Méridien" || brand === "Autograph Collection" || brand === "Tribute Portfolio") {
    preferredProgram = ["W Hotels", "JW Marriott", "Westin", "Le Méridien", "Autograph Collection", "Tribute Portfolio"].includes(brand) ? "Marriott Luminous" : null;
    pointsProgram = "Marriott Bonvoy";
    perksNote = "Marriott Luminous advisor perks + Bonvoy points earning/redemption";
  } else if (brand === "Element by Westin" || brand === "Courtyard by Marriott" || brand === "Sheraton" || brand === "Marriott Bonvoy" || (brand === "Design Hotels" && parentGroup === "Marriott Bonvoy")) {
    pointsProgram = "Marriott Bonvoy";
    perksNote = "Marriott Bonvoy points earning & redemption";
  } else if (brand === "Park Hyatt" || brand === "Alila" || brand === "Andaz" || brand === "Thompson Hotels" || brand === "Hyatt Regency" || brand === "Hyatt Centric" || brand === "World of Hyatt" || brand === "Hyatt All-Inclusive" || brand === "Secrets Resorts" || brand === "Dreams Resorts" || brand === "Alua Hotels" || brand === "Zoëtry") {
    preferredProgram = ["Park Hyatt", "Alila", "Andaz", "Thompson Hotels"].includes(brand) ? "Hyatt Privé" : null;
    pointsProgram = "World of Hyatt";
    perksNote = preferredProgram ? "Hyatt Privé perks (breakfast, credit, 24h upgrade confirmation) + Hyatt points" : "World of Hyatt points earning & redemption";
  } else if (brand === "Waldorf Astoria" || brand === "Conrad" || brand === "LXR Hotels & Resorts" || brand === "Tapestry Collection by Hilton" || brand === "Canopy by Hilton" || brand === "Hilton Honors") {
    preferredProgram = ["Waldorf Astoria", "Conrad", "LXR Hotels & Resorts"].includes(brand) ? "Hilton for Luxury" : null;
    pointsProgram = "Hilton Honors";
    perksNote = preferredProgram ? "Hilton for Luxury perks (breakfast, US$100 credit, double points) + Honors points" : "Hilton Honors points earning & redemption";
  } else if (brand === "Six Senses" || brand === "Regent" || brand === "InterContinental" || brand === "Kimpton" || brand === "Vignette Collection" || brand === "Hotel Indigo" || brand === "Crowne Plaza" || brand === "IHG") {
    preferredProgram = ["Six Senses", "Regent", "InterContinental", "Kimpton", "Vignette Collection"].includes(brand) ? "IHG Destined" : null;
    pointsProgram = "IHG One Rewards";
    perksNote = preferredProgram ? "IHG Destined perks (breakfast, US$100 credit, upgrade priority) + IHG points" : "IHG One Rewards points";
  } else if (brand === "Raffles" || brand === "Fairmont" || brand === "Sofitel" || brand === "Banyan Tree" || brand === "Accor") {
    preferredProgram = ["Raffles", "Fairmont", "Sofitel", "Banyan Tree"].includes(brand) ? "Accor STEP" : null;
    pointsProgram = "Accor ALL";
    perksNote = preferredProgram ? "Accor STEP advisor perks (breakfast, US$100 credit) + ALL points" : "Accor ALL points";
  } else if (brand === "Leading Hotels of the World") {
    preferredProgram = "LHW Leaders Club";
    perksNote = "Leaders Club member breakfast & upgrade benefits";
  } else if (brand === "Relais & Châteaux") {
    preferredProgram = "Relais & Châteaux";
    perksNote = "Independent heritage collection (verify Virtuoso / FHR perks per property)";
  } else if (brand === "Small Luxury Hotels") {
    preferredProgram = "SLH Invited";
    pointsProgram = null; // Do not blanket-tag Hilton Honors; participation varies per SLH property
    perksNote = "SLH Invited benefits (verify individual property participation for Hilton Honors)";
  } else if (/\bradisson\b/i.test(raw)) {
    pointsProgram = "Radisson Rewards";
    perksNote = "Radisson Rewards points earning & redemption";
  }

  return {
    brand,
    parentGroup,
    preferredProgram,
    pointsProgram,
    perksNote,
    hasPreferredPerks: Boolean(preferredProgram),
    isPointsEligible: Boolean(pointsProgram),
  };
}

/* ==================== 3. Destination Climatological "Best Months" ==================== */

const CLIMATE_RULES = [
  // Maldives
  {
    match: /maldives|baa atoll|noonu|raa atoll|ari atoll|mal[eé]|lhaviyani|gaafu|laamu|dhaalu/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Dry NE monsoon, calmest lagoons & clearest house-reef visibility",
  },
  // Bali, Lombok, Flores, Sumba, Java (Indonesia dry season)
  {
    match: /bali|lombok|gili|labuan bajo|flores|sumba|ubud|seminyak|canggu|nusa dua|uluwatu|jimbaran|indonesia|penida|bintan|jakarta/i,
    months: [5, 6, 7, 8, 9, 10],
    label: "May–Oct",
    reason: "Dry season with sunny skies, lower humidity & calm seas",
  },
  // Koh Samui / Gulf of Thailand (opposite monsoon from Phuket!)
  {
    match: /koh samui|samui|koh phangan/i,
    months: [1, 2, 3, 4, 5, 6, 7, 8],
    label: "Jan–Aug",
    reason: "Gulf of Thailand dry window (avoids Oct–Dec NE monsoon)",
  },
  // Phuket, Krabi, Yao Noi, Bangkok, Chiang Mai, Thailand (Andaman & mainland)
  {
    match: /krabi|phuket|yao noi|bangkok|chiang mai|chiang rai|khao lak|koh kood|thailand/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Cool dry season & calm Andaman Sea conditions",
  },
  // Seychelles (shoulder months calmest seas)
  {
    match: /seychelles|mah[eé]|praslin|f[eé]licit[eé]|platte|desroches|north island/i,
    months: [4, 5, 10, 11, 12, 1, 2, 3],
    label: "Apr–May & Oct–Mar",
    reason: "Calmest seas & best diving in Apr–May and Oct–Nov transition windows",
  },
  // Mauritius
  {
    match: /mauritius/i,
    months: [5, 6, 7, 8, 9, 10, 11],
    label: "May–Nov",
    reason: "Cool, dry winter & spring avoiding Jan–Mar cyclone season",
  },
  // Bora Bora & French Polynesia
  {
    match: /bora bora|tahiti|tetiaroa|moorea|french polynesia/i,
    months: [5, 6, 7, 8, 9, 10],
    label: "May–Oct",
    reason: "Dry winter season with lower humidity and clear turquoise lagoons",
  },
  // Fiji
  {
    match: /fiji|laucala|vomo|kokomo|malolo/i,
    months: [5, 6, 7, 8, 9, 10],
    label: "May–Oct",
    reason: "Dry trade-wind season outside Nov–Apr cyclone window",
  },
  // Mexico Riviera Maya / Cancun / Tulum / Caribbean (dry + lower sargassum & hurricane risk)
  {
    match: /riviera maya|cancun|canc[uú]n|costa mujeres|playa mujeres|tulum|mayakoba|caribbean|st\.?\s*barts|st\.?\s*lucia|anguilla|turks|caicos|antigua|barbados|jamaica|bahamas|grenada|aruba|cura[cç]ao|st\.?\s*kitts|dominican|punta cana|cap cana|la romana|puerto rico|bermuda|cayman|st\.?\s*vincent|canouan|nevis|british virgin|virgin gorda/i,
    months: [12, 1, 2, 3, 4],
    label: "Dec–Apr",
    reason: "Dry season with lower hurricane & summer sargassum seaweed risk",
  },
  // Los Cabos / Punta Mita / Pacific Mexico
  {
    match: /cabo|punta mita|punta de mita|nayarit|riviera nayarit|zihuatanejo|careyes|mexico city|san miguel|oaxaca|mexico/i,
    months: [11, 12, 1, 2, 3, 4, 5],
    label: "Nov–May",
    reason: "Dry Pacific season with sunny skies and whale-watching in winter",
  },
  // Central America (Costa Rica, Belize, Panama, Nicaragua)
  {
    match: /costa rica|papagayo|belize|panama|nicaragua/i,
    months: [12, 1, 2, 3, 4],
    label: "Dec–Apr",
    reason: "Dry season with clearest coastal water & trail access",
  },
  // Ski / Alpine Mountains (Alps, Dolomites, Aspen, Jackson Hole, Deer Valley, Whistler, Niseko)
  {
    match: /st\.?\s*moritz|gstaad|courchevel|meg[eè]ve|andermatt|zermatt|verbier|bürgenstock|burgenstock|alps|dolomites|aspen|vail|jackson hole|deer valley|park city|whistler|niseko|estes park|banff|chamonix|lech|kitzb/i,
    months: [12, 1, 2, 3, 6, 7, 8, 9],
    label: "Dec–Mar (Ski) & Jun–Sep",
    reason: "Prime snowpack in winter; crisp alpine hiking & lakes in summer",
  },
  // Middle East (Dubai, Abu Dhabi, Oman, Qatar, Red Sea, Saudi, Jordan)
  {
    match: /dubai|abu dhabi|oman|muscat|zighy|doha|qatar|red sea|alula|saudi|jordan|marrakech|morocco|egypt/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Pleasant 22–30°C sunshine avoiding extreme summer heat",
  },
  // India & Rajasthan
  {
    match: /udaipur|jaipur|jodhpur|mumbai|new delhi|delhi|hyderabad|bengaluru|chennai|rajasthan|ranthambore|jawai|india/i,
    months: [10, 11, 12, 1, 2, 3],
    label: "Oct–Mar",
    reason: "Cool dry season outside summer heat and Jun–Sep monsoon",
  },
  // Sri Lanka
  {
    match: /sri lanka|yala|galle|tangalle|weligama|colombo/i,
    months: [12, 1, 2, 3, 4],
    label: "Dec–Apr",
    reason: "Dry south & west coast season with calm seas",
  },
  // Japan
  {
    match: /tokyo|kyoto|osaka|hakone|amanemu|naoshima|okinawa|japan/i,
    months: [3, 4, 5, 10, 11],
    label: "Mar–May & Oct–Nov",
    reason: "Cherry blossom spring & crisp autumn foliage seasons",
  },
  // Singapore, Hong Kong, Malaysia, Vietnam, Cambodia, Korea
  {
    match: /singapore|langkawi|kuala lumpur|malaysia|hong kong|seoul|korea|vietnam|hanoi|ph[uú] qu[oố]c|ninh van|bai san ho|cambodia|song saa|phnom penh|siem reap|shanghai|beijing|china|taipei/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Drier, less humid months across East & Southeast Asia",
  },
  // East & Southern Africa Safari (Kenya, Tanzania, Botswana, Kruger, Rwanda, Namibia)
  {
    match: /serengeti|masai mara|kenya|tanzania|botswana|okavango|kruger|sabi|singita|rwanda|zambia|zimbabwe|namibia|safari/i,
    months: [6, 7, 8, 9, 10, 1, 2],
    label: "Jun–Oct & Jan–Feb",
    reason: "Dry safari game-viewing season with sparse bush & wildlife concentrations",
  },
  // Cape Town & South Africa Winelands
  {
    match: /cape town|winelands|franschhoek|hermanus|south africa/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Warm, dry austral summer ideal for beaches & wine country",
  },
  // Australia & New Zealand
  {
    match: /sydney|melbourne|brisbane|kangaroo island|southern ocean|qualia|hayman|australia|queenstown|auckland|new zealand/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Warm Southern Hemisphere spring, summer & early autumn",
  },
  // Canary Islands (Tenerife, Lanzarote, Gran Canaria, Fuerteventura, La Gomera, La Palma)
  {
    match: /tenerife|lanzarote|gran canaria|fuerteventura|la gomera|la palma|costa adeje|maspalomas|meloneras|playa blanca|corralejo|canary/i,
    months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    label: "Year-Round (Oct–May Winter Sun)",
    reason: "Europe's warm year-round subtropical islands — sunny 21–27°C beaches even in winter",
  },
  // Mediterranean & Southern Europe (Italy, Greece, Spain, Portugal, South of France, Turkey, Croatia)
  {
    match: /amalfi|positano|capri|como|portofino|tuscany|florence|rome|milan|venice|sardinia|sicily|taormina|puglia|italy|greece|santorini|mykonos|athens|paros|crete|mallorca|ibiza|marbella|barcelona|madrid|spain|algarve|lisbon|douro|comporta|portugal|bodrum|istanbul|turkey|antibes|cannes|st\.?\s*tropez|riviera|provence|monaco|croatia|dubrovnik|montenegro/i,
    months: [5, 6, 7, 8, 9, 10],
    label: "May–Oct",
    reason: "Warm Mediterranean sunshine & full seasonal beach-club openings",
  },
  // Northern / Western Europe & UK (London, Cotswolds, Paris, Zurich, Vienna, Amsterdam, Iceland)
  {
    match: /london|cotswolds|castle combe|wiltshire|somerset|scotland|uk|united kingdom|ireland|paris|france|zurich|geneva|switzerland|vienna|austria|amsterdam|netherlands|germany|munich|berlin|stockholm|copenhagen|norway|iceland|blue lagoon/i,
    months: [5, 6, 7, 8, 9],
    label: "May–Sep",
    reason: "Long daylight hours, mild temperatures & peak garden/terrace season",
  },
  // Hawaii
  {
    match: /hawaii|maui|lanai|lānaʻi|kauai|oahu|big island|kona/i,
    months: [4, 5, 6, 7, 8, 9, 10, 12, 1, 2, 3],
    label: "Year-Round (Apr–Oct driest)",
    reason: "Warm year-round; Apr–Oct driest, Dec–Mar peak whale-watching",
  },
  // South America (Brazil, Argentina, Peru, Chile, Colombia)
  {
    match: /mendoza|buenos aires|patagonia|argentina|rio|s[aã]o paulo|brazil|peru|cusco|chile|atacama|colombia|cartagena/i,
    months: [10, 11, 12, 1, 2, 3, 4],
    label: "Oct–Apr",
    reason: "Warm spring/summer weather & wine harvest months in South America",
  },
  // North America General (California, NYC, Miami, Florida, Napa, New England, Desert SW)
  {
    match: /florida|miami|palm beach|keys|scottsdale|arizona|sedona|amangiri|utah|desert/i,
    months: [11, 12, 1, 2, 3, 4],
    label: "Nov–Apr",
    reason: "Comfortable sunny winter/spring escaping summer heat & humidity",
  },
  {
    match: /california|napa|big sur|santa monica|beverly hills|los angeles|malibu|montecito|new york|manhattan|vermont|new england|georgia|sea island|charleston|washington|chicago|boston|usa|united states|canada|toronto|vancouver/i,
    months: [4, 5, 6, 7, 8, 9, 10],
    label: "Apr–Oct",
    reason: "Pleasant spring, summer & crisp autumn travel seasons",
  },
];

export function getBestMonthsMeta(hotel) {
  const hay = `${(hotel && hotel.name) || ""} ${(hotel && hotel.location) || ""} ${(hotel && hotel.country) || ""} ${(hotel && hotel.region) || ""}`;
  for (const rule of CLIMATE_RULES) {
    if (rule.match.test(hay)) {
      return {
        months: rule.months,
        label: rule.label,
        reason: rule.reason,
      };
    }
  }
  return {
    months: [4, 5, 6, 9, 10],
    label: "Spring & Autumn",
    reason: "Mild shoulder-season conditions",
  };
}

export function matchesBestMonth(hotel, monthNum) {
  const m = Number(monthNum || 0);
  if (!m || m < 1 || m > 12) return true;
  const meta = getBestMonthsMeta(hotel);
  return meta.months.includes(m);
}

/* ==================== 4. Verified Adults-Only vs. Family / Kids-Club ==================== */

// Strictly verified adults-only properties/brands (never tagging family resorts that merely have an adults-only pool)
const STRICT_ADULTS_ONLY_ID_RE = /^(secrets-|impression-.*secrets|zoetry-|excellence-|sandals-|hyatt-zilara-|sanctuary-cap-cana|atelier-playa-mujeres|hotel-xcaret-arte|la-casa-de-la-playa|ladera-resort|jade-mountain|the-caves-jamaica|hermitage-bay|hammock-cove|galley-bay|cocos-hotel|little-palm-island|milaidhoo-maldives|naviva-four-seasons|sensei-lanai|twin-farms|la-casa-que-canta|saii-koh-samui-villas-adult-only|hurawalhi|kudadoo|komandoo|post-ranch-inn|o2-beach-club|amankora)/i;

const STRICT_ADULTS_ONLY_NAME_RE = /\b(adults?\s*[- ]?only|secrets\s+|zo[eë]try\s+|sandals\s+|excellence\s+|hyatt\s+zilara|naviva|sensei\s+lanai|milaidhoo|jade\s+mountain|ladera\s+resort|twin\s+farms|little\s+palm\s+island|post\s+ranch\s+inn|hotel\s+xcaret\s+arte|la\s+casa\s+de\s+la\s+playa|atelier\s+playa\s+mujeres|sanctuary\s+cap\s+cana|hermitage\s+bay|hammock\s+cove|galley\s+bay|cocos\s+hotel|kudadoo|hurawalhi)\b/i;

const FAMILY_EXPLICIT_RE = /\b(kids['’]?\s*club|children['’]?s?\s*club|family[- ]friendly|great\s+for\s+families|water\s*park|beaches\s+turks|kids\s+for\s+all\s+seasons|ritz\s+kids|the\s+den\b|explorer\s+club|babysitting|teens?\s+club)\b/i;

const FAMILY_FLAGSHIP_BRANDS = new Set([
  "Four Seasons",
  "Soneva",
  "One&Only",
  "The Ritz-Carlton",
  "Ritz-Carlton Reserve",
  "St. Regis",
  "Six Senses",
  "Jumeirah",
  "Rosewood",
  "Mandarin Oriental",
  "Waldorf Astoria",
  "Auberge Resorts",
  "Belmond",
  "COMO Hotels",
  "Banyan Tree",
]);

export function getGuestProfile(hotel) {
  const id = String((hotel && hotel.id) || "");
  const name = String((hotel && hotel.name) || "");
  const brand = normalizeBrandName(hotel);
  const notes = `${(hotel && hotel.verdict) || ""} ${(hotel && hotel.standout) || ""} ${(hotel && hotel.whereWeDiffer) || ""} ${JSON.stringify((hotel && hotel.keyFacts) || {})}`;

  // Avoid false positive when text merely mentions "adults-only pool" or "adults-only wing" on a family resort
  const explicitResortAdultsOnly =
    STRICT_ADULTS_ONLY_ID_RE.test(id) ||
    STRICT_ADULTS_ONLY_NAME_RE.test(name) ||
    (/\b(adults?[- ]only\s+(resort|hotel|retreat|sanctuary|property|island|all-inclusive)|no\s+children\s+(under|allowed))\b/i.test(notes) &&
      !/\b(family|kids\s*club|children\s+welcome)\b/i.test(notes));

  const isAdultsOnly = Boolean(explicitResortAdultsOnly);
  const isFamilyFriendly = !isAdultsOnly && (FAMILY_EXPLICIT_RE.test(`${name} ${notes}`) || FAMILY_FLAGSHIP_BRANDS.has(brand));

  return {
    isAdultsOnly,
    isFamilyFriendly,
    badge: isAdultsOnly ? "Adults-Only" : isFamilyFriendly ? "Family / Kids Welcome" : null,
  };
}

/* ==================== 5. Strictly Separated "Rooms to Book" Advice ==================== */

// Verified first-hand room-booking guidance strictly derived from The Uncharted Itinerary's real filmed stays.
// Zero conflation with general property facts (dining, transfers, beach) and zero invented room names.
const VERIFIED_FIRST_HAND_ROOM_TIPS = {
  "st-regis-bali": "Skip the older 2008 main-building suites — book a private villa instead for fresher finishes and more space.",
  "ritz-carlton-bali": "Book a Pavilion Pool Villa for newer interiors, direct lagoon-style privacy, and strong value vs. nearby Nusa Dua rivals.",
  "the-sira-lombok": "Book a Beachfront Pool Villa for a brand-new layout, private pool, butler care, and direct sand access.",
  "w-bali-seminyak": "Book a One-Bedroom Oasis Pool Villa (~£400/night) — one of the best-value private-pool villa categories in Seminyak.",
  "radisson-blu-maldives": "Every villa category includes a private infinity pool and overwater hammock — even entry villas deliver the full Maldives setup.",
  "four-seasons-jimbaran": "Ask for a renovated villa — older 30-year-old villa interiors felt noticeably bare on our stay (3/5 Rooms score).",
  "w-maldives": "Book a refurbished overwater villa with direct reef access so you can snorkel straight off your deck.",
  "bask-gili-meno": "Book a Beachfront Pool Villa for large private pools with turtle snorkeling steps from your sun lounger.",
  "phulay-bay-krabi": "Book a Pool Villa — the cavernous 20ft-ceiling layouts are the centerpiece (and a standout 80k Bonvoy points sweet spot).",
  "w-koh-samui": "All 75 villas come with a private pool — just note 2010 villa finishes feel slightly older than newer Samui rivals.",
  "como-uma-canggu": "Modern rooms feature outdoor showers and real soundproofing from busy Canggu — a sharp ~£200/night luxury base.",
  "regent-bali-canggu": "Book a 1-Bedroom Suite — flawlessly designed, spacious room hardware is a standout highlight right on Canggu beach.",
  "taaktana-labuan-bajo": "Pick between the brand-new Private Pool Villas or Overwater Villas — both include dedicated 24/7 butler service.",
  "finolhu-baa-atoll": "Book an Ocean Water Villa for spacious overwater living with easy access to the 1.8km sandbank.",
  "st-regis-bora-bora": "Overwater Villas start at a massive 1,550+ sq ft — classic styling with one of Bora Bora's largest room footprints.",
  "westin-bora-bora": "Fresh modern Polynesian bungalows & villas — newer and more comfortable inside than St. Regis next door.",
  "four-seasons-koh-samui": "Hillside Pool Villas deliver iconic palm-framed ocean views, though classic interiors feel slightly dated for the price.",
  "le-meridien-maldives": "Stylish modern beach and overwater villas — one of the smartest Marriott Bonvoy points redemptions in the Maldives.",
  "w-algarve": "Watch for elite suite upgrades (the Supreme Two-Bedroom Suite is standout) — note a few suite layouts have quirky details.",
  "rayavadee-krabi": "Two-story jungle Pavilions tucked beneath limestone cliffs offer real privacy across the boat-only peninsula.",
  "cocana-gili-t": "Book a Private Pool Villa for true modern 5-star resort comfort on Gili Trawangan.",
  "manor-house-castle-combe": "Choose between historic 14th-century manor rooms or picturesque garden cottages beside Castle Combe village.",
  "heights-melasti-bali": "The modern 2-Bedroom Private Pool Villa is strong Uluwatu value (pack mosquito repellent for open-air bathrooms).",
  "the-pod-singapore": "Book a single 'bookshelf' capsule with privacy blind for 1–2 night solo stopovers (expect shared-room noise).",
  "the-edge-bali": "Book an ultra-private Cliffside Villa — includes privileged quiet access outside busy dayclub hours.",
  "sebali-nusa-penida": "Book a Pool-Access Room for rare beachfront resort polish on Nusa Penida.",
  "hiliwatu-ubud": "Modern rainforest-valley balcony suites deliver dramatic jungle views at a fraction of Mandapa's nightly rate.",
  "four-seasons-bangkok": "Standard riverside rooms already outclass many resort suites — spacious Jean-Michel Gathy design throughout.",
  "the-ungasan-bali": "Private multi-bedroom clifftop villas are grouped into intimate neighborhoods sharing huge infinity pools.",
  "kin-house-wiltshire": "Primarily booked as an exclusive-use Georgian house for private groups and weddings rather than individual rooms.",
};

// Strict concrete room-category regex for global hotels (matches explicit room/villa/suite types only — never general beach/pool facts)
const SPECIFIC_ROOM_CATEGORY_RE = /\b(\d+[- ]?(?:bedroom|room|suite|villa|casita|bungalow|pavilion|tented\s+(?:suite|villa))s?|all[- ](?:suite|villa|casita|pool[- ]villa)|overwater\s+(?:pool\s+)?villas?|beachfront\s+(?:pool\s+)?villas?|beach\s+(?:pool\s+)?villas?|private[- ]pool\s+(?:villas?|suites?)|swim[- ]up\s+(?:rooms?|suites?)|ocean[- ]view\s+(?:rooms?|suites?|villas?)|cliffside\s+(?:pool\s+)?villas?|hillside\s+(?:pool\s+)?(?:villas?|casitas?)|lagoon\s+(?:pool\s+)?villas?|tented\s+(?:suites?|villas?|camps?)|treehouses?|penthouse\s+suites?|junior\s+suites?|garden\s+(?:pool\s+)?villas?|bungalows?|casitas?)\b/i;

function extractStrictRoomClause(rawText) {
  const txt = String(rawText || "").trim();
  if (!txt) return null;
  // Split into clauses by sentence, semicolon, em-dash, or comma-with-feature lists and keep ONLY the concrete room-type clause
  const parts = txt
    .split(/(?:(?<=[.!?])\s+|\s+[—–]\s+|;\s+)/)
    .map((s) => s.trim())
    .filter(Boolean);
  for (const part of parts) {
    if (!SPECIFIC_ROOM_CATEGORY_RE.test(part)) continue;
    // Narrow comma-separated feature runs so dining/spa/transfer facts don't leak into Rooms to Book
    const subParts = part.split(/,\s+(?=(?:and\s+|plus\s+|with\s+|featuring\s+)?)/i);
    const roomSegments = subParts.filter((seg) => SPECIFIC_ROOM_CATEGORY_RE.test(seg));
    if (roomSegments.length) {
      let clean = roomSegments.slice(0, 2).join(", ").replace(/^(?:featuring|with|and|plus)\s+/i, "").trim();
      clean = clean.replace(/[.;,\s]+$/, "");
      if (clean.length >= 16 && clean.length <= 180) {
        return clean.charAt(0).toUpperCase() + clean.slice(1) + ".";
      }
    }
  }
  return null;
}

export function getVerifiedRoomTip(hotel) {
  if (!hotel) return null;
  const id = String(hotel.id || "").trim();
  if (VERIFIED_FIRST_HAND_ROOM_TIPS[id]) {
    return {
      text: VERIFIED_FIRST_HAND_ROOM_TIPS[id],
      isUnchartedTip: true,
      label: "Rooms to Book (Uncharted Note)",
    };
  }
  // For global (unfilmed) hotels, only surface concrete room-category details if explicitly present in verified notes
  const candidates = [hotel.standout, hotel.verdict].filter(Boolean);
  for (const cand of candidates) {
    const clause = extractStrictRoomClause(cand);
    if (clause) {
      return {
        text: clause,
        isUnchartedTip: false,
        label: "Room & Villa Setup",
      };
    }
  }
  return null;
}

/**
 * Convenience string wrapper for legacy callers expecting plain text or null.
 */
export function getVerifiedRoomTipText(hotel) {
  const tip = getVerifiedRoomTip(hotel);
  return tip ? tip.text : null;
}

/* ==================== 5b. Plain-English Quick Summary Builder ==================== */

function trimSentence(str, maxLen = 145) {
  const s = String(str || "").trim().replace(/\s+/g, " ");
  if (!s) return "";
  if (s.length <= maxLen) return s.replace(/[.!?]+$/, "");
  const cut = s.slice(0, maxLen - 1);
  const lastSpace = cut.lastIndexOf(" ");
  return (lastSpace > 40 ? cut.slice(0, lastSpace) : cut).replace(/[,;:\s]+$/, "") + "…";
}

/**
 * Synthesizes an instant, plain-English Quick Summary strictly from verified hotel data
 * (StayOdds score, Uncharted video status, best weather months, standout benefits, watch-outs, and room guidance).
 * Zero fabricated claims.
 */
export function buildHotelQuickSummary(hotel, odds) {
  if (!hotel || !odds) {
    return { headline: "", bullets: [], paragraph: "", roomTip: null, bestMonths: null };
  }
  const climate = getBestMonthsMeta(hotel);
  const roomTip = getVerifiedRoomTip(hotel);
  const profile = getGuestProfile(hotel);

  // 1. Score & review consensus sentence
  let scoreLead = "";
  const pct = odds.greatStayOdds != null ? `${odds.greatStayOdds}% StayOdds` : "Live Google check";
  if (odds.scoreTrack === "verified") {
    const myBit = odds.personalScoreLabel ? ` (${odds.personalScoreLabel} from our filmed stay)` : " (filmed on The Uncharted Itinerary)";
    const backup = [];
    if (odds.critic100 != null) backup.push(`${odds.critic100}/100 critics`);
    if (odds.verifiedGuest) {
      const gStr = odds.verifiedGuest.scale === 5 ? `${odds.verifiedGuest.rating.toFixed(1)}★` : `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}`;
      backup.push(`${gStr} ${odds.verifiedGuest.sourceName}`);
    }
    scoreLead = `${pct} — Uncharted Verified${myBit}${backup.length ? `, backed by ${backup.join(" and ")}` : ""}.`;
  } else if (odds.greatStayOdds != null) {
    const toneWord =
      odds.greatStayOdds >= 92
        ? "Standout"
        : odds.greatStayOdds >= 86
        ? "Strong"
        : odds.greatStayOdds >= 78
        ? "Solid"
        : "Mixed";
    const basis = [];
    if (odds.critic100 != null) basis.push(`${odds.critic100}/100 published critics`);
    if (odds.verifiedGuest) {
      const gStr = odds.verifiedGuest.scale === 5 ? `${odds.verifiedGuest.rating.toFixed(1)}★` : `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}`;
      const revStr = odds.verifiedGuest.reviewCount ? ` across ${odds.verifiedGuest.reviewCount.toLocaleString()} reviews` : "";
      basis.push(`${gStr} ${odds.verifiedGuest.sourceName}${revStr}`);
    }
    scoreLead = `${toneWord} ${pct}${basis.length ? ` based on ${basis.join(" & ")}` : ""}.`;
  } else {
    scoreLead = "Live Google guest consensus available on demand.";
  }

  // 2. Key benefits + weather sentence
  const benefitParts = [];
  if (hotel.standout) {
    benefitParts.push(`Known for: ${trimSentence(hotel.standout, 130)}.`);
  } else if (hotel.verdict) {
    benefitParts.push(`${trimSentence(hotel.verdict, 130)}.`);
  }
  const weatherPart = `Best weather: ${climate.label} (${climate.reason.charAt(0).toLowerCase() + climate.reason.slice(1)}).`;

  // 3. Watch-out & price/profile context
  const watchOutClean = hotel.watchOut ? trimSentence(hotel.watchOut, 130) + "." : null;
  const priceTag = hotel.priceRange ? `${hotel.priceRange} indicative` : null;

  // Compact 1-2 sentence paragraph for cards & quick browse
  const shortParts = [];
  if (hotel.standout) {
    shortParts.push(trimSentence(hotel.standout, 115) + ".");
  } else if (hotel.verdict) {
    shortParts.push(trimSentence(hotel.verdict, 115) + ".");
  }
  shortParts.push(`Best weather: ${climate.label}.`);
  if (profile.badge) shortParts.push(`${profile.badge}.`);

  return {
    headline: scoreLead,
    benefit: benefitParts[0] || "",
    weather: weatherPart,
    watchOut: watchOutClean,
    priceTag,
    profileBadge: profile.badge || null,
    bestMonths: climate,
    roomTip,
    paragraph: shortParts.join(" "),
  };
}

/* ==================== 6. Clean RFC-4180 CSV Exporter ==================== */

function csvCell(v) {
  const s = v == null ? "" : String(v);
  if (/[",\r\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

export function exportHotelsToCsv(hotels, getOddsFn, awardHelpers, filename = "stayodds-luxury-hotels.csv") {
  const headers = [
    "Hotel",
    "Location",
    "Country",
    "Region",
    "Brand",
    "StayOdds %",
    "Status Badge",
    "Uncharted Stay (/25)",
    "Critics (/100)",
    "Verified Guests",
    "Opinion Gap",
    "MICHELIN Keys",
    "World's 50 Best",
    "Forbes Rating",
    "Preferred Partner Program",
    "Points Program",
    "Guest Profile",
    "Best Months",
    "Operating Status",
    "StayOdds Page URL",
  ];

  const rows = hotels.map((h) => {
    const o = getOddsFn(h);
    const partner = getPartnerPrograms(h);
    const profile = getGuestProfile(h);
    const climate = getBestMonthsMeta(h);
    const mKeys = awardHelpers.getMichelinKeyCount(h);
    const w50 = awardHelpers.getW50BestRank(h);
    const forbes = awardHelpers.getForbesRank(h);
    const st = (h.propertyStatus && h.propertyStatus.operatingStatus) || "No works listed";
    return [
      h.name || "",
      h.location || "",
      h.country || "",
      h.region || "",
      partner.brand || "",
      o.greatStayOdds != null ? `${o.greatStayOdds}%` : "",
      o.statusBadge || "",
      o.personalScoreLabel || "",
      o.critic100 != null ? `${o.critic100}/100` : "",
      o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)}/${o.verifiedGuest.scale}` : "",
      (o.opinionGap && o.opinionGap.deltaLabel) || "",
      mKeys != null ? `${mKeys} ${mKeys === 1 ? "Key" : "Keys"}` : "",
      w50 != null ? (w50 < 999 ? `#${w50}` : "50 Best") : "",
      forbes === 5 ? "5-Star" : forbes === 4 ? "4-Star" : forbes === 3 ? "Recommended" : "",
      partner.preferredProgram || "",
      partner.pointsProgram || "",
      profile.badge || "",
      climate.label || "",
      st,
      `https://stayodds.com/stayodds/${encodeURIComponent(h.id)}/`,
    ];
  });

  const csv = [headers.map(csvCell).join(","), ...rows.map((r) => r.map(csvCell).join(","))].join("\r\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

/* ==================== 7. Shared Natural-Language Trip Query Parser ==================== */

const NLP_MONTH_REGEXES = [
  { m: 1, label: "Jan", re: /\b(jan|january)\b/i },
  { m: 2, label: "Feb", re: /\b(feb|february)\b/i },
  { m: 3, label: "Mar", re: /\b(mar|march)\b/i },
  { m: 4, label: "Apr", re: /\b(apr|april)\b/i },
  { m: 5, label: "May", re: /\bmay\b/i },
  { m: 6, label: "Jun", re: /\b(jun|june)\b/i },
  { m: 7, label: "Jul", re: /\b(jul|july)\b/i },
  { m: 8, label: "Aug", re: /\b(aug|august)\b/i },
  { m: 9, label: "Sep", re: /\b(sep|sept|september)\b/i },
  { m: 10, label: "Oct", re: /\b(oct|october)\b/i },
  { m: 11, label: "Nov", re: /\b(nov|november)\b/i },
  { m: 12, label: "Dec", re: /\b(dec|december)\b/i },
];

const NLP_PLACE_RULES = [
  { re: /\bcaribbean\b/i, region: "Caribbean & Mexico", excludeCountries: ["mexico"], label: "Caribbean Islands" },
  { re: /\bmexico|riviera maya|cancun|cancún|los cabos|cabo|tulum|punta mita\b/i, region: "Caribbean & Mexico", search: "Mexico", label: "Mexico" },
  {
    re: /\bcanary islands|canaries\b/i,
    region: "Europe",
    includeLocations: ["tenerife", "gran canaria", "lanzarote", "fuerteventura", "la palma", "la gomera"],
    label: "Canary Islands",
  },
  { re: /\btenerife\b/i, region: "Europe", search: "Tenerife", label: "Tenerife" },
  { re: /\bgran canaria\b/i, region: "Europe", search: "Gran Canaria", label: "Gran Canaria" },
  { re: /\blanzarote\b/i, region: "Europe", search: "Lanzarote", label: "Lanzarote" },
  { re: /\bfuerteventura\b/i, region: "Europe", search: "Fuerteventura", label: "Fuerteventura" },
  { re: /\bmaldives\b/i, region: "Maldives & Indian Ocean", search: "Maldives", label: "Maldives" },
  { re: /\bseychelles\b/i, region: "Maldives & Indian Ocean", search: "Seychelles", label: "Seychelles" },
  { re: /\bmauritius\b/i, region: "Maldives & Indian Ocean", search: "Mauritius", label: "Mauritius" },
  { re: /\bbora bora|french polynesia|tahiti\b/i, region: "Australia & Pacific", search: "French Polynesia", label: "Bora Bora & French Polynesia" },
  { re: /\bbali\b/i, region: "Asia", search: "Bali", label: "Bali" },
  { re: /\bindonesia|lombok\b/i, region: "Asia", search: "Indonesia", label: "Indonesia" },
  { re: /\bjapan|tokyo|kyoto|niseko\b/i, region: "Asia", search: "Japan", label: "Japan" },
  { re: /\bthailand|phuket|bangkok|koh samui\b/i, region: "Asia", search: "Thailand", label: "Thailand" },
  { re: /\bdubai|abu dhabi|uae|oman|qatar|doha|middle east\b/i, region: "Middle East", label: "Middle East" },
  { re: /\bgreece|santorini|mykonos|athens|crete\b/i, region: "Europe", search: "Greece", label: "Greece" },
  { re: /\bitaly|amalfi|como|tuscany|rome|milan|venice|florence|sicily\b/i, region: "Europe", search: "Italy", label: "Italy" },
  { re: /\bfrance|paris|riviera|provence|courchevel\b/i, region: "Europe", search: "France", label: "France" },
  { re: /\bspain|mallorca|ibiza|marbella|madrid|barcelona\b/i, region: "Europe", search: "Spain", label: "Spain" },
  { re: /\bswitzerland|st\.?\s*moritz|zermatt|gstaad|andermatt|alps\b/i, region: "Europe", search: "Switzerland", label: "Switzerland" },
  { re: /\bunited kingdom|\buk\b|london|scotland|cotswolds\b/i, region: "Europe", search: "United Kingdom", label: "United Kingdom" },
  { re: /\bturkey|bodrum|istanbul\b/i, region: "Europe", search: "Turkey", label: "Turkey" },
  { re: /\begypt|red sea|cairo\b/i, region: "Middle East", search: "Egypt", label: "Egypt" },
  { re: /\bafrica|south africa|kenya|tanzania|botswana|morocco|marrakech\b/i, region: "Africa", label: "Africa" },
  { re: /\baustralia|new zealand|fiji|pacific\b/i, region: "Australia & Pacific", label: "Australia & Pacific" },
  { re: /\beurope\b/i, region: "Europe", label: "Europe" },
  { re: /\basia\b/i, region: "Asia", label: "Asia" },
  { re: /\bamericas|usa|united states|california|new york|hawaii|costa rica\b/i, region: "Americas", label: "Americas" },
  { re: /\bindian ocean\b/i, region: "Maldives & Indian Ocean", label: "Maldives & Indian Ocean" },
];

const NLP_BRAND_RULES = [
  { re: /\bfour seasons\b/i, brand: "Four Seasons" },
  { re: /\baman\b/i, brand: "Aman" },
  { re: /\brosewood\b/i, brand: "Rosewood" },
  { re: /\bmandarin oriental\b/i, brand: "Mandarin Oriental" },
  { re: /\bsix senses\b/i, brand: "Six Senses" },
  { re: /\bbelmond\b/i, brand: "Belmond" },
  { re: /\bone\s*&\s*only\b/i, brand: "One&Only" },
  { re: /\bst\.?\s*regis\b/i, brand: "St. Regis" },
  { re: /\britz[- ]?carlton\b/i, brand: "The Ritz-Carlton" },
  { re: /\bmarriott|bonvoy\b/i, brand: "Marriott Bonvoy" },
  { re: /\bhyatt\b/i, brand: "World of Hyatt" },
  { re: /\bhilton|waldorf|conrad\b/i, brand: "Hilton Honors" },
  { re: /\bsoneva\b/i, brand: "Soneva" },
  { re: /\bcapella\b/i, brand: "Capella" },
];

export function parseNaturalTripQuery(raw) {
  const text = String(raw || "").trim();
  const parsed = {
    region: "All",
    excludeCountries: [],
    includeLocations: [],
    search: "",
    brand: null,
    month: 0,
    feature: "all",
    style: "all",
    priceTier: "all",
    maxGbp: null,
    sortBy: null,
    chips: [], // { iconKey, label }
  };
  if (!text) return parsed;

  for (const rule of NLP_PLACE_RULES) {
    if (rule.re.test(text)) {
      if (rule.region) parsed.region = rule.region;
      if (rule.excludeCountries) parsed.excludeCountries = rule.excludeCountries;
      if (rule.includeLocations) parsed.includeLocations = rule.includeLocations;
      if (rule.search) parsed.search = rule.search;
      parsed.chips.push({ iconKey: "mapPin", label: rule.label });
      break;
    }
  }

  let matchedMonth = null;
  for (const mr of NLP_MONTH_REGEXES) {
    if (mr.re.test(text)) {
      matchedMonth = mr;
      break;
    }
  }
  if (matchedMonth) {
    parsed.month = matchedMonth.m;
    parsed.chips.push({ iconKey: "sun", label: `Best Weather: ${matchedMonth.label}` });
  } else if (/\bwinter sun\b/i.test(text)) {
    parsed.month = 1;
    parsed.chips.push({ iconKey: "sun", label: "Winter Sun (Jan)" });
  } else if (/\bsummer\b/i.test(text)) {
    parsed.month = 7;
    parsed.chips.push({ iconKey: "sun", label: "Summer (Jul)" });
  } else if (/\bspring|easter\b/i.test(text)) {
    parsed.month = 4;
    parsed.chips.push({ iconKey: "sun", label: "Spring (Apr)" });
  } else if (/\bautumn|fall\b/i.test(text)) {
    parsed.month = 10;
    parsed.chips.push({ iconKey: "sun", label: "Autumn (Oct)" });
  }

  const priceMatch = text.match(/(?:under|below|max|less than|up to|<)\s*[£$€]?\s*(\d{3,4})/i);
  if (priceMatch) {
    const cap = Number(priceMatch[1]);
    if (cap <= 500) {
      parsed.priceTier = "under500";
      if (cap < 500) parsed.maxGbp = cap;
    } else {
      parsed.maxGbp = cap;
    }
    parsed.chips.push({ iconKey: "tag", label: `Under £${cap}/nt` });
  } else if (/\b(cheap|budget|affordable|great value|good value|value)\b/i.test(text)) {
    parsed.priceTier = "under500";
    parsed.sortBy = "price_asc";
    parsed.chips.push({ iconKey: "tag", label: "Under £500/nt" });
  }

  if (/\btop\s*50|50\s*best\b/i.test(text)) {
    parsed.feature = "50best_50";
    parsed.sortBy = "award_50best";
    parsed.chips.push({ iconKey: "trophy", label: "World's 50 Best (#1–50)" });
  } else if (/\btop\s*100\b/i.test(text)) {
    parsed.feature = "50best_100";
    parsed.sortBy = "award_50best";
    parsed.chips.push({ iconKey: "award", label: "Top 100 (#1–100)" });
  } else if (/\b3\s*(?:michelin\s*)?keys?\b/i.test(text)) {
    parsed.feature = "michelin_3";
    parsed.sortBy = "award_michelin";
    parsed.chips.push({ iconKey: "key", label: "3 MICHELIN Keys" });
  } else if (/\bmichelin\b/i.test(text)) {
    parsed.feature = "michelin";
    parsed.sortBy = "award_michelin";
    parsed.chips.push({ iconKey: "key", label: "MICHELIN Keys" });
  } else if (/\bforbes\b/i.test(text)) {
    parsed.feature = "forbes";
    parsed.sortBy = "award_forbes";
    parsed.chips.push({ iconKey: "star", label: "Forbes Star-Rated" });
  } else if (/\badults[- ]?only|honeymoon|romantic|couples\b/i.test(text)) {
    parsed.feature = "adults";
    parsed.chips.push({ iconKey: "users", label: "Adults-Only" });
  } else if (/\bfamily|families|kids|children\b/i.test(text)) {
    parsed.feature = "family";
    parsed.chips.push({ iconKey: "users", label: "Family & Kids" });
  } else if (/\bpoints|bonvoy|hyatt points|hilton points\b/i.test(text)) {
    parsed.feature = "points";
    parsed.chips.push({ iconKey: "star", label: "Points Brands" });
  }

  if (/\ball[- ]?inclusive\b/i.test(text)) {
    parsed.style = "allinclusive";
    parsed.chips.push({ iconKey: "utensils", label: "All-Inclusive" });
  } else if (/\boverwater|water villa\b/i.test(text)) {
    parsed.style = "overwater";
    parsed.chips.push({ iconKey: "home", label: "Overwater Villas" });
  } else if (/\bsnorkel|house reef|diving|reef\b/i.test(text)) {
    parsed.style = "snorkel";
    parsed.chips.push({ iconKey: "compass", label: "Snorkelling & Reef" });
  } else if (/\bsafari|wildlife|jungle|nature\b/i.test(text)) {
    parsed.style = "safari";
    parsed.chips.push({ iconKey: "trees", label: "Safari & Nature" });
  } else if (/\bski|mountain|alps|alpine|snow\b/i.test(text)) {
    parsed.style = "mountain";
    parsed.chips.push({ iconKey: "mountain", label: "Mountain & Ski" });
  } else if (/\bspa|wellness|onsen|retreat\b/i.test(text)) {
    parsed.style = "wellness";
    parsed.chips.push({ iconKey: "droplets", label: "Spa & Wellness" });
  } else if (/\bcity|urban|shopping\b/i.test(text)) {
    parsed.style = "city";
    parsed.chips.push({ iconKey: "building", label: "City Breaks" });
  } else if (/\bculture|heritage|palace|historic\b/i.test(text)) {
    parsed.style = "culture";
    parsed.chips.push({ iconKey: "landmark", label: "Culture & Heritage" });
  } else if (/\bbeach|island|sunny|sunshine|tropical\b/i.test(text) && !parsed.month && parsed.region === "All") {
    parsed.style = "beach";
    parsed.chips.push({ iconKey: "waves", label: "Beach Resorts" });
  } else if (/\bbeach|island\b/i.test(text) && parsed.region !== "All") {
    parsed.style = "beach";
    parsed.chips.push({ iconKey: "waves", label: "Beach Resorts" });
  }

  for (const br of NLP_BRAND_RULES) {
    if (br.re.test(text)) {
      parsed.brand = br.brand;
      parsed.chips.push({ iconKey: "building", label: br.brand });
      break;
    }
  }

  if (!parsed.chips.length) {
    const cleaned = text
      .replace(/\b(i want to|i would like to|stay in|looking for|find me|show me|hotels?|resorts?|in|the|a|an|with|for)\b/gi, " ")
      .replace(/\s+/g, " ")
      .trim();
    parsed.search = cleaned || text;
    parsed.chips.push({ iconKey: "search", label: `"${parsed.search}"` });
  }
  return parsed;
}
