/**
 * StayOdds Branded Share Card Generator & Social Share Modal
 * - Pure HTML5 <canvas> vector/typography renderer (ZERO cross-origin images -> NEVER taints!)
 * - Supports 1:1 Feed (1080x1080) and 9:16 Story (1080x1920) with pure-JS ISO-18004 QR code
 * - Supports both Head-to-Head VS Scorecard AND Single-Hotel StayOdds Card
 * - Strict Zero-Fabrication Rule: only renders real verified scores, facts, and status
 */

/* ==================== Pure-JS QR Code Encoder (ISO/IEC 18004 Byte Mode, ECC-M) ==================== */
const QR_EC_M = [
  null,
  { total: 26, ecPerBlock: 10, blocks: [[1, 16]] },
  { total: 44, ecPerBlock: 16, blocks: [[1, 28]] },
  { total: 70, ecPerBlock: 26, blocks: [[1, 44]] },
  { total: 100, ecPerBlock: 18, blocks: [[2, 32]] },
  { total: 134, ecPerBlock: 24, blocks: [[2, 43]] },
  { total: 172, ecPerBlock: 16, blocks: [[4, 27]] },
  { total: 196, ecPerBlock: 18, blocks: [[4, 31]] },
  { total: 242, ecPerBlock: 22, blocks: [[2, 38], [2, 39]] },
  { total: 292, ecPerBlock: 22, blocks: [[3, 36], [2, 37]] },
  { total: 346, ecPerBlock: 26, blocks: [[4, 43], [1, 44]] },
];

const QR_ALIGN = [
  [],
  [],
  [6, 18],
  [6, 22],
  [6, 26],
  [6, 30],
  [6, 34],
  [6, 22, 38],
  [6, 24, 42],
  [6, 26, 46],
  [6, 28, 50],
];

const GF_EXP = new Uint8Array(512);
const GF_LOG = new Uint8Array(256);
(() => {
  let x = 1;
  for (let i = 0; i < 255; i++) {
    GF_EXP[i] = x;
    GF_LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  for (let i = 255; i < 512; i++) GF_EXP[i] = GF_EXP[i - 255];
})();

function gfMul(a, b) {
  if (a === 0 || b === 0) return 0;
  return GF_EXP[GF_LOG[a] + GF_LOG[b]];
}

function rsGeneratorPoly(degree) {
  let poly = [1];
  for (let i = 0; i < degree; i++) {
    const next = new Array(poly.length + 1).fill(0);
    const factor = GF_EXP[i];
    for (let j = 0; j < poly.length; j++) {
      next[j] ^= poly[j];
      next[j + 1] ^= gfMul(poly[j], factor);
    }
    poly = next;
  }
  return poly;
}

function rsRemainder(data, ecLen) {
  const gen = rsGeneratorPoly(ecLen);
  const res = new Uint8Array(ecLen);
  for (let i = 0; i < data.length; i++) {
    const factor = data[i] ^ res[0];
    for (let j = 0; j < ecLen - 1; j++) res[j] = res[j + 1];
    res[ecLen - 1] = 0;
    if (factor !== 0) {
      for (let j = 0; j < ecLen; j++) res[j] ^= gfMul(gen[j + 1], factor);
    }
  }
  return res;
}

function qrFormatBits(mask) {
  // ECC M = 00 (2 bits), mask = 3 bits -> 5 data bits
  const data = (0b00 << 3) | (mask & 7);
  let rem = data << 10;
  const poly = 0b10100110111;
  for (let i = 14; i >= 10; i--) {
    if ((rem >> i) & 1) rem ^= poly << (i - 10);
  }
  return ((data << 10) | rem) ^ 0b101010000010010;
}

function qrVersionBits(ver) {
  let rem = ver << 12;
  const poly = 0b1111100100101;
  for (let i = 17; i >= 12; i--) {
    if ((rem >> i) & 1) rem ^= poly << (i - 12);
  }
  return (ver << 12) | rem;
}

export function encodeQrMatrix(text) {
  const bytes = new TextEncoder().encode(String(text || ""));
  let ver = 1;
  for (; ver <= 10; ver++) {
    const spec = QR_EC_M[ver];
    const dataCap = spec.blocks.reduce((sum, [cnt, cw]) => sum + cnt * cw, 0);
    const countBits = ver <= 9 ? 8 : 16;
    const totalBits = 4 + countBits + bytes.length * 8;
    if (Math.ceil(totalBits / 8) <= dataCap) break;
  }
  if (ver > 10) ver = 10;

  const spec = QR_EC_M[ver];
  const dataCap = spec.blocks.reduce((sum, [cnt, cw]) => sum + cnt * cw, 0);
  const countBits = ver <= 9 ? 8 : 16;
  const bits = [];
  const pushBits = (val, len) => {
    for (let i = len - 1; i >= 0; i--) bits.push((val >> i) & 1);
  };
  pushBits(0b0100, 4); // Byte mode
  pushBits(Math.min(bytes.length, dataCap - 2), countBits);
  for (let i = 0; i < Math.min(bytes.length, dataCap - 2); i++) pushBits(bytes[i], 8);
  const maxBits = dataCap * 8;
  for (let i = 0; i < 4 && bits.length < maxBits; i++) bits.push(0);
  while (bits.length % 8 !== 0) bits.push(0);

  const dataCW = [];
  for (let i = 0; i < bits.length; i += 8) {
    let b = 0;
    for (let j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
    dataCW.push(b);
  }
  let padIdx = 0;
  while (dataCW.length < dataCap) {
    dataCW.push(padIdx++ % 2 === 0 ? 0xec : 0x11);
  }

  // Split blocks & compute RS ECC
  const dataBlocks = [];
  const ecBlocks = [];
  let offset = 0;
  for (const [cnt, cw] of spec.blocks) {
    for (let i = 0; i < cnt; i++) {
      const blk = dataCW.slice(offset, offset + cw);
      offset += cw;
      dataBlocks.push(blk);
      ecBlocks.push(Array.from(rsRemainder(blk, spec.ecPerBlock)));
    }
  }

  const codewords = [];
  const maxDataLen = Math.max(...dataBlocks.map((b) => b.length));
  for (let i = 0; i < maxDataLen; i++) {
    for (const b of dataBlocks) if (i < b.length) codewords.push(b[i]);
  }
  for (let i = 0; i < spec.ecPerBlock; i++) {
    for (const b of ecBlocks) codewords.push(b[i]);
  }

  const size = ver * 4 + 17;
  const modules = Array.from({ length: size }, () => new Uint8Array(size));
  const isFunc = Array.from({ length: size }, () => new Uint8Array(size));

  const setFunc = (r, c, dark) => {
    if (r >= 0 && r < size && c >= 0 && c < size) {
      modules[r][c] = dark ? 1 : 0;
      isFunc[r][c] = 1;
    }
  };

  const drawFinder = (r0, c0) => {
    for (let dr = -1; dr <= 7; dr++) {
      for (let dc = -1; dc <= 7; dc++) {
        const r = r0 + dr;
        const c = c0 + dc;
        if (r < 0 || r >= size || c < 0 || c >= size) continue;
        const dist = Math.max(Math.abs(dr - 3), Math.abs(dc - 3));
        setFunc(r, c, dist !== 2 && dist !== 4);
      }
    }
  };
  drawFinder(0, 0);
  drawFinder(0, size - 7);
  drawFinder(size - 7, 0);

  // Timing patterns
  for (let i = 8; i < size - 8; i++) {
    setFunc(6, i, i % 2 === 0);
    setFunc(i, 6, i % 2 === 0);
  }

  // Alignment patterns
  const alignPos = QR_ALIGN[ver];
  for (const r of alignPos) {
    for (const c of alignPos) {
      if (isFunc[r][c]) continue;
      for (let dr = -2; dr <= 2; dr++) {
        for (let dc = -2; dc <= 2; dc++) {
          setFunc(r + dr, c + dc, Math.max(Math.abs(dr), Math.abs(dc)) !== 1);
        }
      }
    }
  }

  // Reserve format info + dark module
  for (let i = 0; i <= 8; i++) {
    if (i !== 6) {
      setFunc(8, i, false);
      setFunc(i, 8, false);
    }
  }
  for (let i = size - 8; i < size; i++) {
    setFunc(8, i, false);
    setFunc(i, 8, false);
  }
  setFunc(size - 8, 8, true);

  // Version info (ver >= 7)
  if (ver >= 7) {
    const vBits = qrVersionBits(ver);
    for (let i = 0; i < 18; i++) {
      const bit = Boolean((vBits >> i) & 1);
      const a = size - 11 + (i % 3);
      const b = Math.floor(i / 3);
      setFunc(a, b, bit);
      setFunc(b, a, bit);
    }
  }

  // Place data bits in zigzag
  let bitIdx = 0;
  const totalDataBits = codewords.length * 8;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    const upward = ((right + 1) & 2) === 0;
    for (let step = 0; step < size; step++) {
      const r = upward ? size - 1 - step : step;
      for (let j = 0; j < 2; j++) {
        const c = right - j;
        if (!isFunc[r][c]) {
          let dark = 0;
          if (bitIdx < totalDataBits) {
            dark = (codewords[bitIdx >> 3] >> (7 - (bitIdx & 7))) & 1;
            bitIdx++;
          }
          modules[r][c] = dark;
        }
      }
    }
  }

  // Apply mask 0..7 and choose lowest penalty
  const maskFns = [
    (r, c) => (r + c) % 2 === 0,
    (r) => r % 2 === 0,
    (_, c) => c % 3 === 0,
    (r, c) => (r + c) % 3 === 0,
    (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
    (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
    (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0,
    (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0,
  ];

  const writeFormat = (grid, mask) => {
    const fb = qrFormatBits(mask);
    const bits15 = Array.from({ length: 15 }, (_, i) => (fb >> i) & 1);
    for (let i = 0; i <= 5; i++) grid[8][i] = bits15[14 - i];
    grid[8][7] = bits15[8];
    grid[8][8] = bits15[7];
    grid[7][8] = bits15[6];
    for (let i = 9; i < 15; i++) grid[14 - i][8] = bits15[14 - i];
    for (let i = 0; i < 8; i++) grid[size - 1 - i][8] = bits15[14 - i];
    for (let i = 8; i < 15; i++) grid[8][size - 15 + i] = bits15[14 - i];
    grid[size - 8][8] = 1;
  };

  let bestGrid = null;
  let bestScore = Infinity;
  for (let m = 0; m < 8; m++) {
    const grid = modules.map((row) => new Uint8Array(row));
    const fn = maskFns[m];
    for (let r = 0; r < size; r++) {
      for (let c = 0; c < size; c++) {
        if (!isFunc[r][c] && fn(r, c)) grid[r][c] ^= 1;
      }
    }
    writeFormat(grid, m);
    // Penalty calculation (runs + 2x2 blocks + balance)
    let score = 0;
    for (let r = 0; r < size; r++) {
      let run = 1;
      for (let c = 1; c < size; c++) {
        if (grid[r][c] === grid[r][c - 1]) run++;
        else {
          if (run >= 5) score += 3 + (run - 5);
          run = 1;
        }
      }
      if (run >= 5) score += 3 + (run - 5);
    }
    for (let c = 0; c < size; c++) {
      let run = 1;
      for (let r = 1; r < size; r++) {
        if (grid[r][c] === grid[r - 1][c]) run++;
        else {
          if (run >= 5) score += 3 + (run - 5);
          run = 1;
        }
      }
      if (run >= 5) score += 3 + (run - 5);
    }
    for (let r = 0; r < size - 1; r++) {
      for (let c = 0; c < size - 1; c++) {
        const v = grid[r][c];
        if (v === grid[r][c + 1] && v === grid[r + 1][c] && v === grid[r + 1][c + 1]) score += 3;
      }
    }
    if (score < bestScore) {
      bestScore = score;
      bestGrid = grid;
    }
  }
  return { size, grid: bestGrid };
}

/* ==================== Helpers & Verified Fact Builders ==================== */

export function getPropertyStatusMeta(hotel) {
  const st = (hotel && hotel.propertyStatus) || {};
  const op = (st.operatingStatus || "").trim();
  const reno = (st.renovationsExtensions || "").trim();
  const nearby = (st.nearbyConstruction || "").trim();
  const srcUrl = (st.sourceUrl || "").trim();
  const srcNote = (st.sourceNote || "").trim();
  const verifiedAt = (st.verifiedAt || "").trim();

  const hasDetails = Boolean(op || reno || nearby);
  const lower = op.toLowerCase();

  let badge = op || "No Works Listed";
  let tone = "neutral"; // neutral | open | warn | danger
  if (lower.includes("closed")) {
    tone = "danger";
  } else if (lower.includes("rebrand") || lower.includes("transition") || nearby) {
    tone = "warn";
  } else if (op === "Open" && reno) {
    tone = "open";
    badge = "Open · Recent Works";
  } else if (op === "Open") {
    tone = "open";
  }

  let shortSummary = "No confirmed renovations, closures, or nearby works listed";
  if (lower.includes("closed")) {
    shortSummary = reno || `${op} — check reopening status before booking.`;
  } else if (lower.includes("rebrand") || lower.includes("transition")) {
    shortSummary = reno || `${op} — verify current brand & operator.`;
  } else if (reno && nearby) {
    shortSummary = `${reno} Nearby: ${nearby}`;
  } else if (reno) {
    shortSummary = reno;
  } else if (nearby) {
    shortSummary = `Nearby works: ${nearby}`;
  }

  return {
    hasDetails,
    operatingStatus: op || "No confirmed works listed",
    badge,
    tone,
    renovationsExtensions: reno,
    nearbyConstruction: nearby,
    sourceUrl: srcUrl,
    sourceNote: srcNote,
    verifiedAt,
    shortSummary,
  };
}

export function extractTopKeyFacts(hotel, odds, maxCount = 3) {
  const facts = [];
  if (odds && Array.isArray(odds.keyFacts)) {
    for (const kf of odds.keyFacts) {
      if (kf && kf.label && kf.value) facts.push({ label: kf.label, value: String(kf.value) });
    }
  } else if (hotel && hotel.keyFacts) {
    const kf = hotel.keyFacts;
    if (kf.beachOrReef) facts.push({ label: "Beach / Reef", value: kf.beachOrReef });
    if (kf.transferLogistics) facts.push({ label: "Transfers", value: kf.transferLogistics });
    if (kf.poolHeating) facts.push({ label: "Pool Heating", value: kf.poolHeating });
    if (kf.renovationYear) facts.push({ label: "Renovated", value: String(kf.renovationYear) });
  }
  if (facts.length < maxCount && hotel && hotel.priceRange && !facts.some((f) => /tier|price/i.test(f.label))) {
    facts.push({ label: "Price Tier", value: hotel.priceRange });
  }
  if (facts.length < maxCount && hotel && hotel.standout && !facts.some((f) => /standout/i.test(f.label))) {
    facts.push({ label: "Standout", value: hotel.standout });
  }
  return facts.slice(0, maxCount);
}

const LOCAL_IMG_CACHE = new Map();

function hasChannelVideo(hotel) {
  return Boolean(
    hotel &&
      (hotel.videoId ||
        hotel.coverageType === "Full Review" ||
        hotel.coverageType === "Short Tour" ||
        (Array.isArray(hotel.shorts) && hotel.shorts.length > 0))
  );
}

function getYouTubeVideoBadge(hotel) {
  if (!hasChannelVideo(hotel)) return "";
  if (hotel.coverageType === "Short Tour" && !hotel.inLiveFeed) {
    return "▶ YOUTUBE SHORT";
  }
  return "▶ VIDEO ON YOUTUBE";
}

function toSameOriginUrl(relPath) {
  if (!relPath || /^https?:\/\//i.test(relPath)) return "";
  const clean = String(relPath).trim().replace(/^\.+\//, "").replace(/^\//, "");
  if (!clean) return "";
  try {
    const u = new URL(`/${clean}`, window.location.origin);
    if (u.origin !== window.location.origin) return "";
    return u.href;
  } catch (_) {
    return "";
  }
}

function getCandidatePhotoUrls(hotel) {
  if (!hotel) return [];
  const slug = hotel.id ? String(hotel.id).trim() : "";
  const urls = [];
  // For filmed/YouTube-thumbnail properties, prefer clean official resort photo (no YouTube text overlay)
  if (hotel.cardPhoto) {
    const u = toSameOriginUrl(hotel.cardPhoto);
    if (u) urls.push(u);
  }
  if (slug && hasChannelVideo(hotel)) {
    const u = toSameOriginUrl(`assets/card-photos/${encodeURIComponent(slug)}.webp`);
    if (u && !urls.includes(u)) urls.push(u);
  }
  if (hotel.thumbnail) {
    const u = toSameOriginUrl(hotel.thumbnail);
    if (u && !urls.includes(u)) urls.push(u);
  }
  if (slug) {
    const u = toSameOriginUrl(`assets/thumbs/${encodeURIComponent(slug)}.webp`);
    if (u && !urls.includes(u)) urls.push(u);
  }
  return urls;
}

function loadImgOnce(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

function loadSameOriginHotelImg(hotel) {
  const candidates = getCandidatePhotoUrls(hotel);
  if (!candidates.length) return Promise.resolve(null);
  const cacheKey = (hotel && hotel.id) || candidates[0];
  const cached = LOCAL_IMG_CACHE.get(cacheKey);
  if (cached) {
    return cached instanceof Promise ? cached : Promise.resolve(cached);
  }
  const p = (async () => {
    for (const u of candidates) {
      const img = await loadImgOnce(u);
      if (img) {
        LOCAL_IMG_CACHE.set(cacheKey, img);
        return img;
      }
    }
    LOCAL_IMG_CACHE.set(cacheKey, null);
    return null;
  })();
  LOCAL_IMG_CACHE.set(cacheKey, p);
  return p;
}

function getCachedHotelImg(hotel) {
  if (!hotel) return null;
  const cacheKey = hotel.id || getCandidatePhotoUrls(hotel)[0];
  if (!cacheKey) return null;
  const val = LOCAL_IMG_CACHE.get(cacheKey);
  return val && !(val instanceof Promise) ? val : null;
}

function drawRoundedImageCover(
  ctx,
  img,
  x,
  y,
  w,
  h,
  r,
  borderCol = "rgba(255,255,255,0.16)",
  badgeText = "",
  ytBadgeText = ""
) {
  if (!img || !img.naturalWidth || !img.naturalHeight) return false;
  ctx.save();
  roundRectPath(ctx, x, y, w, h, r);
  ctx.clip();

  const imgRatio = img.naturalWidth / img.naturalHeight;
  const boxRatio = w / h;
  let sx = 0, sy = 0, sw = img.naturalWidth, sh = img.naturalHeight;
  if (imgRatio > boxRatio) {
    sw = img.naturalHeight * boxRatio;
    sx = (img.naturalWidth - sw) / 2;
  } else {
    sh = img.naturalWidth / boxRatio;
    sy = (img.naturalHeight - sh) / 2;
  }
  ctx.drawImage(img, sx, sy, sw, sh, x, y, w, h);

  // Subtle dark bottom vignette for legibility when badgeText exists
  const grad = ctx.createLinearGradient(x, y + h * 0.45, x, y + h);
  grad.addColorStop(0, "rgba(7, 19, 35, 0)");
  grad.addColorStop(1, badgeText ? "rgba(7, 19, 35, 0.80)" : "rgba(7, 19, 35, 0.30)");
  ctx.fillStyle = grad;
  ctx.fillRect(x, y, w, h);

  if (ytBadgeText) {
    const compact = w < 310;
    ctx.font = `800 ${compact ? 10 : 11}px ${FONT_STACK}`;
    const tw = ctx.measureText(ytBadgeText).width;
    const pw = tw + (compact ? 16 : 20);
    const ph = compact ? 22 : 25;
    const bx = x + w - pw - 10;
    const by = y + 10;
    fillRoundRect(ctx, bx, by, pw, ph, ph / 2, "rgba(220, 38, 38, 0.94)", "rgba(255, 255, 255, 0.35)", 1);
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText(ytBadgeText, bx + (compact ? 8 : 10), by + (compact ? 15 : 16.5));
  }

  if (badgeText) {
    ctx.font = `700 ${w < 310 ? 12 : 13}px ${FONT_STACK}`;
    ctx.fillStyle = "#F8FAFC";
    drawWrappedText(ctx, badgeText, x + 12, y + h - 13, w - 24, 17, 1);
  }
  ctx.restore();

  if (borderCol) {
    fillRoundRect(ctx, x, y, w, h, r, null, borderCol, 1.5);
  }
  return true;
}

function shortCriticSource(name = "") {
  const s = String(name || "").trim();
  if (!s) return "";
  if (/flip-flop/i.test(s)) return "Flip-Flop";
  if (/walker/i.test(s)) return "Walker Index";
  if (/nonstop\s*dan/i.test(s)) return "Nonstop Dan";
  if (/telegraph/i.test(s)) return "Telegraph";
  if (/fat\s*voyage/i.test(s)) return "Fat Voyage";
  if (/forbes/i.test(s)) return "Forbes";
  return s.length > 14 ? `${s.slice(0, 13)}…` : s;
}

/**
 * Formats the verified "Critics / Other Reviews" slot under strict Zero-Fake-Data rules:
 * - Numeric score ONLY when a real verified critic/editorial/YouTube numeric score exists.
 * - Explicit "Unverified" if a source awards scores that could not be verified.
 * - Explicit "Review Only" if verified qualitative editorial/YouTube reviews exist with no number.
 * - Clean neutral "—" / "None listed" when no verified review is on record.
 */
export function formatCriticSlot(odds) {
  if (!odds) return { compact: "—", sub: "None listed", full: "None listed" };
  const scored = Array.isArray(odds.scoredEditorial) ? odds.scoredEditorial : [];
  const unverified = Array.isArray(odds.unverifiedEditorial) ? odds.unverifiedEditorial : [];
  const edTotal = Array.isArray(odds.editorialRatings)
    ? odds.editorialRatings.length
    : Number(odds.editorialCount || 0);
  const ytTotal = Array.isArray(odds.youtubeReviews)
    ? odds.youtubeReviews.length
    : Number(odds.youtubeCount || 0);

  if (odds.critic100 != null) {
    if (scored.length === 1) {
      const src = scored[0].sourceName || "";
      return {
        compact: `${odds.critic100}/100`,
        sub: shortCriticSource(src) || "Verified",
        full: `${scored[0].rawScore || `${odds.critic100}/100`}${src ? ` (${src})` : ""}`,
      };
    }
    if (scored.length > 1) {
      return {
        compact: `${odds.critic100}/100`,
        sub: `${scored.length} critics`,
        full: `${odds.critic100}/100 (${scored.length} verified critics)`,
      };
    }
    return {
      compact: `${odds.critic100}/100`,
      sub: "Verified",
      full: `${odds.critic100}/100`,
    };
  }

  if (unverified.length > 0) {
    const src = unverified[0].sourceName || "";
    return {
      compact: "Unverified",
      sub: shortCriticSource(src) || "Score unverified",
      full: `Score awarded — unverified${src ? ` (${src})` : ""}`,
    };
  }

  const qualCount = edTotal + ytTotal;
  if (qualCount > 0) {
    return {
      compact: "Review Only",
      sub: `${qualCount} linked`,
      full: `${qualCount} verified review${qualCount > 1 ? "s" : ""} (no numeric score)`,
    };
  }

  return { compact: "—", sub: "None listed", full: "None listed" };
}

export function buildFactualVsVerdict(hotelA, hotelB, oddsA, oddsB) {
  const stA = getPropertyStatusMeta(hotelA);
  const stB = getPropertyStatusMeta(hotelB);
  const aClosed = stA.tone === "danger";
  const bClosed = stB.tone === "danger";

  const scoreA = oddsA && oddsA.greatStayOdds != null ? oddsA.greatStayOdds : null;
  const scoreB = oddsB && oddsB.greatStayOdds != null ? oddsB.greatStayOdds : null;

  let headline = "Verified Head-to-Head Breakdown";
  let detail = "";

  if (aClosed && !bClosed) {
    headline = `Status Alert: ${hotelA.name} is ${stA.operatingStatus}`;
    detail = `${hotelB.name} is the active option right now${scoreB != null ? ` (${scoreB}% StayOdds)` : ""}. Verify ${hotelA.name} reopening dates before planning travel.`;
    return { headline, detail, winnerSide: "B" };
  }
  if (bClosed && !aClosed) {
    headline = `Status Alert: ${hotelB.name} is ${stB.operatingStatus}`;
    detail = `${hotelA.name} is the active option right now${scoreA != null ? ` (${scoreA}% StayOdds)` : ""}. Verify ${hotelB.name} reopening dates before planning travel.`;
    return { headline, detail, winnerSide: "A" };
  }

  if (scoreA != null && scoreB != null) {
    const diff = scoreA - scoreB;
    if (Math.abs(diff) === 0) {
      headline = `Dead Heat at ${scoreA}% StayOdds`;
      const tierNote =
        oddsA.firstHand && !oddsB.firstHand
          ? `${hotelA.name} includes a first-hand stay scorecard.`
          : oddsB.firstHand && !oddsA.firstHand
          ? `${hotelB.name} includes a first-hand stay scorecard.`
          : "Compare verified Critics/Other scores, Key Facts, and Opinion Gap below.";
      detail = tierNote;
      return { headline, detail, winnerSide: "TIE" };
    }
    const winH = diff > 0 ? hotelA : hotelB;
    const loseH = diff > 0 ? hotelB : hotelA;
    const winO = diff > 0 ? oddsA : oddsB;
    const loseO = diff > 0 ? oddsB : oddsA;
    const margin = Math.abs(diff);

    headline = `${winH.name} leads by +${margin}% (${winO.greatStayOdds}% vs ${loseO.greatStayOdds}%)`;
    const reasons = [];
    if (winO.firstHand && winO.personalScoreLabel) {
      reasons.push(`Uncharted Stay ${winO.personalScoreLabel}`);
    }
    if (winO.critic100 != null) {
      const cSlot = formatCriticSlot(winO);
      reasons.push(`Critics ${cSlot.compact}${cSlot.sub && cSlot.sub !== "Verified" ? ` (${cSlot.sub})` : ""}`);
    }
    if (winO.verifiedGuest) {
      reasons.push(`Guests ${winO.verifiedGuest.rating.toFixed(1)}/${winO.verifiedGuest.scale}`);
    }
    if (winO.statusBadge) {
      reasons.push(winO.statusBadge);
    }
    detail = reasons.length
      ? `Backed by ${reasons.join(" • ")}. Compare verified facts & caveats against ${loseH.name}.`
      : `Leads on verified StayOdds data across available guest & critic sources.`;
    return { headline, detail, winnerSide: diff > 0 ? "A" : "B" };
  }

  if (scoreA != null || scoreB != null) {
    const scoredH = scoreA != null ? hotelA : hotelB;
    const scoredO = scoreA != null ? oddsA : oddsB;
    headline = `${scoredH.name}: ${scoredO.greatStayOdds}% Verified StayOdds`;
    detail = `Only ${scoredH.name} has a static verified numeric score so far — check live Google reviews & verified Key Facts on StayOdds.`;
    return { headline, detail, winnerSide: scoreA != null ? "A" : "B" };
  }

  headline = `${hotelA.name} vs ${hotelB.name}`;
  detail = "Compare verified official awards, key property facts, and live guest ratings side by side — zero fabricated numbers.";
  return { headline, detail, winnerSide: "TIE" };
}

export function buildVsDeepLink(hotelA, hotelB) {
  return `https://stayodds.com/?a=${encodeURIComponent(hotelA.id)}&b=${encodeURIComponent(hotelB.id)}`;
}

export function buildThreeWayDeepLink(hotelA, hotelB, hotelC) {
  return `https://stayodds.com/?a=${encodeURIComponent(hotelA.id)}&b=${encodeURIComponent(hotelB.id)}&c=${encodeURIComponent(hotelC.id)}`;
}

export function buildSingleDeepLink(hotel) {
  return `https://stayodds.com/stayodds/${encodeURIComponent(hotel.id)}/`;
}

export function buildFactualThreeWayVerdict(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC) {
  const entries = [
    { side: "A", hotel: hotelA, odds: oddsA, st: getPropertyStatusMeta(hotelA) },
    { side: "B", hotel: hotelB, odds: oddsB, st: getPropertyStatusMeta(hotelB) },
    { side: "C", hotel: hotelC, odds: oddsC, st: getPropertyStatusMeta(hotelC) },
  ];

  const scored = entries
    .filter((e) => e.odds && e.odds.greatStayOdds != null && e.st.tone !== "danger")
    .sort((x, y) => y.odds.greatStayOdds - x.odds.greatStayOdds);

  const closedList = entries.filter((e) => e.st.tone === "danger");

  if (scored.length >= 2) {
    const top = scored[0];
    const second = scored[1];
    const scoreLine = entries
      .map((e) => (e.odds && e.odds.greatStayOdds != null ? `${e.odds.greatStayOdds}%` : "Open"))
      .join(" vs ");
    if (top.odds.greatStayOdds === second.odds.greatStayOdds) {
      const tiedNames = scored
        .filter((e) => e.odds.greatStayOdds === top.odds.greatStayOdds)
        .map((e) => e.hotel.name)
        .join(" & ");
      return {
        headline: `Tied at Top: ${tiedNames} (${top.odds.greatStayOdds}% StayOdds)`,
        detail: `3-Hotel StayOdds split: ${scoreLine}. Compare verified Uncharted Stay, Critics/Other, Guests, and Key Facts below.`,
        winnerSide: "TIE",
      };
    }
    const margin = top.odds.greatStayOdds - second.odds.greatStayOdds;
    const reasons = [];
    if (top.odds.firstHand && top.odds.personalScoreLabel) reasons.push(`Uncharted Stay ${top.odds.personalScoreLabel}`);
    if (top.odds.critic100 != null) {
      const cSlot = formatCriticSlot(top.odds);
      reasons.push(`Critics ${cSlot.compact}`);
    }
    if (top.odds.verifiedGuest) {
      reasons.push(`Guests ${top.odds.verifiedGuest.rating.toFixed(1)}/${top.odds.verifiedGuest.scale}`);
    }
    if (closedList.length) {
      reasons.push(`Note: ${closedList[0].hotel.name} is ${closedList[0].st.operatingStatus}`);
    }
    return {
      headline: `${top.hotel.name} leads 3-hotel matchup by +${margin}% (${scoreLine})`,
      detail: reasons.length
        ? `Backed by ${reasons.join(" • ")}. Zero fabricated numbers.`
        : `Highest verified StayOdds across all 3 properties (${scoreLine}).`,
      winnerSide: top.side,
    };
  }

  if (scored.length === 1) {
    const top = scored[0];
    return {
      headline: `${top.hotel.name}: ${top.odds.greatStayOdds}% Verified StayOdds`,
      detail: `Only ${top.hotel.name} has a static verified score so far — open live Google reviews & awards on StayOdds.`,
      winnerSide: top.side,
    };
  }

  return {
    headline: `${hotelA.name} vs ${hotelB.name} vs ${hotelC.name}`,
    detail: "Compare verified official awards, key property facts, and live guest ratings across 3 luxury hotels — zero fabricated numbers.",
    winnerSide: "TIE",
  };
}

export function buildRedditMarkdownThreeWay(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC) {
  const verdict = buildFactualThreeWayVerdict(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC);
  const stA = getPropertyStatusMeta(hotelA);
  const stB = getPropertyStatusMeta(hotelB);
  const stC = getPropertyStatusMeta(hotelC);
  const factsStr = (h, o) =>
    (extractTopKeyFacts(h, o, 2)
      .map((f) => `${f.label}: ${f.value}`)
      .join("; ") || "—").replace(/\|/g, "/");
  const guestStr = (o) =>
    o && o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)}/${o.verifiedGuest.scale}` : "Live on page";
  const myStr = (o) =>
    o && o.personalScoreLabel ? o.personalScoreLabel : o && o.visited ? "Filmed (Unscored)" : "Not Visited";
  const criticStr = (o) => formatCriticSlot(o).full;
  const oddsStr = (o) => (o && o.greatStayOdds != null ? `**${o.greatStayOdds}%**` : "Open Breakdown");
  const statusStr = (st) => (st.hasDetails ? `${st.operatingStatus}: ${st.shortSummary}` : "No confirmed works listed");

  const url = buildThreeWayDeepLink(hotelA, hotelB, hotelC);
  return [
    `### ${hotelA.name} vs ${hotelB.name} vs ${hotelC.name} — StayOdds 3-Hotel Verified Breakdown`,
    ``,
    `**Verdict:** ${verdict.headline}${verdict.detail ? ` — ${verdict.detail}` : ""}`,
    ``,
    `| Metric | ${hotelA.name} | ${hotelB.name} | ${hotelC.name} |`,
    `| :--- | :--- | :--- | :--- |`,
    `| **Location** | ${hotelA.location}, ${hotelA.country} | ${hotelB.location}, ${hotelB.country} | ${hotelC.location}, ${hotelC.country} |`,
    `| **StayOdds %** | ${oddsStr(oddsA)} | ${oddsStr(oddsB)} | ${oddsStr(oddsC)} |`,
    `| **Consensus Badge** | ${oddsA.statusBadge} | ${oddsB.statusBadge} | ${oddsC.statusBadge} |`,
    `| **Uncharted Stay** | ${myStr(oddsA)} | ${myStr(oddsB)} | ${myStr(oddsC)} |`,
    `| **Critics / Other Reviews** | ${criticStr(oddsA)} | ${criticStr(oddsB)} | ${criticStr(oddsC)} |`,
    `| **Verified Guests** | ${guestStr(oddsA)} | ${guestStr(oddsB)} | ${guestStr(oddsC)} |`,
    `| **Opinion Gap** | ${oddsA.opinionGap.deltaLabel} | ${oddsB.opinionGap.deltaLabel} | ${oddsC.opinionGap.deltaLabel} |`,
    `| **Status & Works** | ${statusStr(stA)} | ${statusStr(stB)} | ${statusStr(stC)} |`,
    `| **Verified Key Facts** | ${factsStr(hotelA, oddsA)} | ${factsStr(hotelB, oddsB)} | ${factsStr(hotelC, oddsC)} |`,
    ``,
    `*Zero fabricated scores — real verified ratings, awards, and property facts only at **[stayodds.com](https://stayodds.com)**.*`,
    `Explore at https://stayodds.com • Direct 3-hotel comparison: ${url}`,
  ].join("\n");
}

export function buildRedditMarkdownVs(hotelA, hotelB, oddsA, oddsB) {
  const verdict = buildFactualVsVerdict(hotelA, hotelB, oddsA, oddsB);
  const stA = getPropertyStatusMeta(hotelA);
  const stB = getPropertyStatusMeta(hotelB);
  const factsA = extractTopKeyFacts(hotelA, oddsA, 2)
    .map((f) => `${f.label}: ${f.value}`)
    .join("; ") || "—";
  const factsB = extractTopKeyFacts(hotelB, oddsB, 2)
    .map((f) => `${f.label}: ${f.value}`)
    .join("; ") || "—";

  const guestStr = (o) =>
    o && o.verifiedGuest ? `${o.verifiedGuest.rating.toFixed(1)}/${o.verifiedGuest.scale}` : "Live on page";
  const myStr = (h, o) =>
    o && o.personalScoreLabel ? o.personalScoreLabel : o && o.visited ? "Filmed (Unscored)" : "Not Visited";
  const criticStr = (o) => formatCriticSlot(o).full;
  const oddsStr = (o) => (o && o.greatStayOdds != null ? `**${o.greatStayOdds}%**` : "Open Breakdown");

  const url = buildVsDeepLink(hotelA, hotelB);
  return [
    `### ${hotelA.name} vs ${hotelB.name} — StayOdds Verified Breakdown`,
    ``,
    `**Verdict:** ${verdict.headline}${verdict.detail ? ` — ${verdict.detail}` : ""}`,
    ``,
    `| Metric | ${hotelA.name} | ${hotelB.name} |`,
    `| :--- | :--- | :--- |`,
    `| **Location** | ${hotelA.location}, ${hotelA.country} | ${hotelB.location}, ${hotelB.country} |`,
    `| **StayOdds %** | ${oddsStr(oddsA)} | ${oddsStr(oddsB)} |`,
    `| **Consensus Badge** | ${oddsA.statusBadge} | ${oddsB.statusBadge} |`,
    `| **Uncharted Stay** | ${myStr(hotelA, oddsA)} | ${myStr(hotelB, oddsB)} |`,
    `| **Critics / Other Reviews** | ${criticStr(oddsA)} | ${criticStr(oddsB)} |`,
    `| **Verified Guests** | ${guestStr(oddsA)} | ${guestStr(oddsB)} |`,
    `| **Opinion Gap** | ${oddsA.opinionGap.deltaLabel} | ${oddsB.opinionGap.deltaLabel} |`,
    `| **Status & Works** | ${stA.hasDetails ? `${stA.operatingStatus}: ${stA.shortSummary}` : "No confirmed works listed"} | ${stB.hasDetails ? `${stB.operatingStatus}: ${stB.shortSummary}` : "No confirmed works listed"} |`,
    `| **Verified Key Facts** | ${factsA.replace(/\|/g, "/")} | ${factsB.replace(/\|/g, "/")} |`,
    ``,
    `*Zero fabricated scores — real verified ratings, awards, and property facts only at **[stayodds.com](https://stayodds.com)**.*`,
    `Explore at https://stayodds.com • Direct comparison: ${url}`,
  ].join("\n");
}

export function buildRedditMarkdownSingle(hotel, odds) {
  const st = getPropertyStatusMeta(hotel);
  const facts = extractTopKeyFacts(hotel, odds, 3);
  const url = buildSingleDeepLink(hotel);
  const lines = [
    `### ${hotel.name} (${hotel.location}, ${hotel.country}) — StayOdds Verified Scorecard`,
    ``,
    `| Metric | Verified Data |`,
    `| :--- | :--- |`,
    `| **StayOdds %** | ${odds.greatStayOdds != null ? `**${odds.greatStayOdds}%**` : "Open Breakdown"} |`,
    `| **Status Badge** | ${odds.statusBadge} (${odds.tierLabel}) |`,
    `| **Uncharted Stay** | ${odds.personalScoreLabel || (odds.visited ? "Filmed (Unscored)" : "Not Visited")} |`,
    `| **Critics / Other Reviews** | ${formatCriticSlot(odds).full} |`,
    `| **Verified Guests** | ${odds.verifiedGuest ? `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}` : "Live Google on page"} |`,
    `| **Opinion Gap** | ${odds.opinionGap.deltaLabel} — ${odds.opinionGap.headline} |`,
    `| **Property Status & Works** | ${st.hasDetails ? `${st.operatingStatus}: ${st.shortSummary}` : "No confirmed renovations, closures, or nearby works listed"} |`,
  ];
  for (const f of facts) {
    lines.push(`| **${f.label}** | ${f.value.replace(/\|/g, "/")} |`);
  }
  lines.push(
    ``,
    `*Zero fabricated scores — real verified data only at **[stayodds.com](https://stayodds.com)**.*`,
    `Explore at https://stayodds.com • Direct breakdown: ${url}`
  );
  return lines.join("\n");
}

/* ==================== Canvas Drawing Primitives (100% Untainted Local Vector) ==================== */

const FONT_STACK = `'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`;

function roundRectPath(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function fillRoundRect(ctx, x, y, w, h, r, fill, stroke = null, strokeWidth = 1) {
  roundRectPath(ctx, x, y, w, h, r);
  if (fill) {
    ctx.fillStyle = fill;
    ctx.fill();
  }
  if (stroke) {
    ctx.strokeStyle = stroke;
    ctx.lineWidth = strokeWidth;
    ctx.stroke();
  }
}

function wrapLines(ctx, text, maxWidth, maxLines = 3) {
  const clean = String(text || "").replace(/\s+/g, " ").trim();
  if (!clean) return [];
  const words = clean.split(" ");
  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (ctx.measureText(test).width <= maxWidth) {
      line = test;
    } else {
      if (line) lines.push(line);
      line = word;
      if (lines.length === maxLines - 1) break;
    }
  }
  if (line && lines.length < maxLines) lines.push(line);
  // Ellipsize last line if overflowed
  const joined = lines.join(" ");
  if (joined.length < clean.length && lines.length > 0) {
    let last = lines[lines.length - 1];
    while (last.length > 4 && ctx.measureText(`${last}…`).width > maxWidth) {
      last = last.slice(0, -1).trimEnd();
    }
    lines[lines.length - 1] = `${last}…`;
  }
  return lines;
}

function drawWrappedText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 3) {
  const lines = wrapLines(ctx, text, maxWidth, maxLines);
  lines.forEach((ln, idx) => ctx.fillText(ln, x, y + idx * lineHeight));
  return lines.length;
}

function drawQrOnCanvas(ctx, text, x, y, sizePx) {
  const { size, grid } = encodeQrMatrix(text);
  const quiet = 2;
  const totalMods = size + quiet * 2;
  const cell = Math.floor(sizePx / totalMods);
  const actual = cell * totalMods;
  const padX = Math.floor((sizePx - actual) / 2);
  const padY = Math.floor((sizePx - actual) / 2);

  fillRoundRect(ctx, x, y, sizePx, sizePx, 18, "#FFFFFF");
  ctx.fillStyle = "#071323";
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (grid[r][c]) {
        ctx.fillRect(x + padX + (c + quiet) * cell, y + padY + (r + quiet) * cell, cell, cell);
      }
    }
  }
}

function drawCardBackground(ctx, W, H) {
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#071323");
  bg.addColorStop(0.55, "#0B1D35");
  bg.addColorStop(1, "#06101E");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Subtle decorative glows
  const glow1 = ctx.createRadialGradient(W * 0.14, H * 0.08, 10, W * 0.14, H * 0.08, W * 0.52);
  glow1.addColorStop(0, "rgba(255, 93, 34, 0.22)");
  glow1.addColorStop(1, "rgba(255, 93, 34, 0)");
  ctx.fillStyle = glow1;
  ctx.fillRect(0, 0, W, H);

  const glow2 = ctx.createRadialGradient(W * 0.88, H * 0.88, 10, W * 0.88, H * 0.88, W * 0.48);
  glow2.addColorStop(0, "rgba(20, 184, 166, 0.18)");
  glow2.addColorStop(1, "rgba(20, 184, 166, 0)");
  ctx.fillStyle = glow2;
  ctx.fillRect(0, 0, W, H);

  // Outer crisp frame border
  fillRoundRect(ctx, 22, 22, W - 44, H - 44, 34, null, "rgba(255,255,255,0.09)", 2);
}

function drawHeaderBrand(ctx, W, padX, topY, rightTag) {
  ctx.textBaseline = "alphabetic";
  ctx.font = `800 44px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  ctx.fillText("StayOdds", padX, topY);
  const w1 = ctx.measureText("StayOdds").width;
  ctx.fillStyle = "#FF5D22";
  ctx.fillText(".", padX + w1, topY);

  ctx.font = `700 19px ${FONT_STACK}`;
  ctx.fillStyle = "#FF5D22";
  ctx.fillText("by The Uncharted Itinerary", padX, topY + 28);

  // Right pill
  ctx.font = `800 17px ${FONT_STACK}`;
  const tw = ctx.measureText(rightTag).width;
  const pw = tw + 34;
  fillRoundRect(ctx, W - padX - pw, topY - 32, pw, 40, 20, "rgba(255,93,34,0.16)", "rgba(255,93,34,0.55)", 1.5);
  ctx.fillStyle = "#FF8B5E";
  ctx.fillText(rightTag, W - padX - pw + 17, topY - 6);
}

function statusPillColors(tone) {
  if (tone === "danger") return { bg: "rgba(239,68,68,0.18)", border: "rgba(248,113,113,0.65)", fg: "#FCA5A5" };
  if (tone === "warn") return { bg: "rgba(245,158,11,0.18)", border: "rgba(251,191,36,0.65)", fg: "#FCD34D" };
  if (tone === "open") return { bg: "rgba(20,184,166,0.16)", border: "rgba(45,212,191,0.5)", fg: "#5EEAD4" };
  return { bg: "rgba(148,163,184,0.14)", border: "rgba(148,163,184,0.3)", fg: "#CBD5E1" };
}

/* ==================== Render VS Card (1:1 or 9:16) ==================== */
export function renderVsCanvas(canvas, hotelA, hotelB, oddsA, oddsB, format = "1:1") {
  const isStory = format === "9:16";
  const W = 1080;
  const H = isStory ? 1920 : 1080;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  drawCardBackground(ctx, W, H);
  const padX = 56;
  drawHeaderBrand(ctx, W, padX, isStory ? 104 : 88, "VERIFIED HEAD-TO-HEAD");

  const verdict = buildFactualVsVerdict(hotelA, hotelB, oddsA, oddsB);
  const deepLink = buildVsDeepLink(hotelA, hotelB);

  // Verdict Banner
  const vY = isStory ? 156 : 132;
  const vH = isStory ? 148 : 114;
  fillRoundRect(ctx, padX, vY, W - padX * 2, vH, 22, "rgba(255,93,34,0.13)", "rgba(255,93,34,0.48)", 2);
  ctx.font = `800 15px ${FONT_STACK}`;
  ctx.fillStyle = "#FF8B5E";
  ctx.fillText("VERIFIED VERDICT", padX + 24, vY + 32);

  ctx.font = `800 ${isStory ? 28 : 25}px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  drawWrappedText(ctx, verdict.headline, padX + 24, vY + (isStory ? 68 : 64), W - padX * 2 - 48, 32, 1);

  ctx.font = `500 ${isStory ? 20 : 17}px ${FONT_STACK}`;
  ctx.fillStyle = "#CBD5E1";
  drawWrappedText(ctx, verdict.detail, padX + 24, vY + (isStory ? 102 : 93), W - padX * 2 - 48, 25, isStory ? 2 : 1);

  // Draw Hotel Columns (side-by-side in 1:1; stacked generous cards in 9:16)
  const drawHotelPanel = (hotel, odds, side, x, y, w, h) => {
    const isWin = verdict.winnerSide === side;
    const accent = side === "A" ? "#FF5D22" : "#14B8A6";
    const borderCol = isWin ? accent : "rgba(255,255,255,0.12)";
    fillRoundRect(ctx, x, y, w, h, 26, "rgba(15, 29, 50, 0.88)", borderCol, isWin ? 2.5 : 1.5);

    // Side & Tier badges + Top-Right Score Box (zero collision layout)
    const p = 22;
    const scoreW = isStory ? 124 : 112;
    const scoreH = isStory ? 64 : 58;
    const scoreX = x + w - p - scoreW;
    const scoreY = y + p - 2;

    fillRoundRect(ctx, x + p, y + p, 108, 28, 14, side === "A" ? "rgba(255,93,34,0.22)" : "rgba(20,184,166,0.22)");
    ctx.font = `800 13.5px ${FONT_STACK}`;
    ctx.fillStyle = side === "A" ? "#FF8B5E" : "#5EEAD4";
    ctx.fillText(`HOTEL ${side}${isWin ? " ★" : ""}`, x + p + 14, y + p + 19);

    ctx.font = `700 12px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    if (isStory) {
      drawWrappedText(ctx, odds.statusBadge.toUpperCase(), x + p + 120, y + p + 19, Math.max(120, scoreX - (x + p + 132)), 16, 1);
    } else {
      // On 1:1 columns, stack status cleanly BELOW HOTEL A/B pill so it NEVER touches the score % box
      drawWrappedText(ctx, odds.statusBadge.toUpperCase(), x + p + 2, y + p + 47, Math.max(120, scoreX - (x + p + 14)), 15, 1);
    }

    // Score pill top-right
    const scoreText = odds.greatStayOdds != null ? `${odds.greatStayOdds}%` : "OPEN";
    fillRoundRect(ctx, scoreX, scoreY, scoreW, scoreH, 16, "rgba(7,19,35,0.92)", accent, 2);
    ctx.font = `800 ${isStory ? 31 : 28}px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    const sw = ctx.measureText(scoreText).width;
    ctx.fillText(scoreText, scoreX + scoreW / 2 - sw / 2, scoreY + (isStory ? 36 : 33));
    ctx.font = `700 10.5px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    const lbl = "STAYODDS";
    ctx.fillText(lbl, scoreX + scoreW / 2 - ctx.measureText(lbl).width / 2, scoreY + (isStory ? 54 : 50));

    // Hotel Name & Location (always below the score box on 1:1 so long titles never collide)
    const nameY = isStory ? y + p + 68 : y + p + 84;
    const nameMaxW = isStory ? w - p * 2 - scoreW - 18 : w - p * 2;
    ctx.font = `800 ${isStory ? 30 : 23}px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    const nameLines = drawWrappedText(ctx, hotel.name, x + p, nameY, nameMaxW, isStory ? 35 : 27, 2);

    const locY = nameY + nameLines * (isStory ? 34 : 26) + 2;
    ctx.font = `500 ${isStory ? 18.5 : 15}px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    drawWrappedText(
      ctx,
      `${hotel.location}, ${hotel.country}${hotel.brand ? ` • ${hotel.brand}` : ""}`,
      x + p,
      locY,
      w - p * 2,
      20,
      1
    );

    // Score Progress Bar
    const barY = locY + (isStory ? 24 : 16);
    const barW = w - p * 2;
    fillRoundRect(ctx, x + p, barY, barW, 11, 5.5, "rgba(255,255,255,0.09)");
    if (odds.greatStayOdds != null) {
      fillRoundRect(ctx, x + p, barY, Math.max(24, (barW * odds.greatStayOdds) / 100), 11, 5.5, accent);
    }

    // Verified 4-Slot Pillars (Uncharted Stay | Critics / Other | Guests | Opinion Gap)
    const criticInfo = formatCriticSlot(odds);
    const pillars = [
      {
        label: "UNCHARTED STAY",
        val: odds.personalScoreLabel ? odds.personalScoreLabel.replace(/ /g, "") : odds.visited ? "Filmed" : "—",
        sub: odds.personalScoreLabel ? "YouTube Review" : odds.visited ? "Unscored" : "Not stayed",
      },
      {
        label: "CRITICS / OTHER",
        val: criticInfo.compact,
        sub: criticInfo.sub,
      },
      {
        label: "GUESTS",
        val: odds.verifiedGuest ? `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}` : "Live",
        sub: odds.verifiedGuest ? "Verified" : "Google Maps",
      },
      {
        label: "OPINION GAP",
        val: odds.opinionGap ? odds.opinionGap.deltaLabel : "—",
        sub: odds.opinionGap && odds.opinionGap.deltaLabel && odds.opinionGap.deltaLabel !== "—" ? "Spread" : "No gap yet",
      },
    ];

    const boxY = barY + (isStory ? 22 : 16);
    let afterBoxesY;
    if (isStory) {
      // Wide 9:16 Story panel -> crisp 4-column horizontal row
      const boxH = 90;
      const gap = 10;
      const boxW = (barW - gap * 3) / 4;
      pillars.forEach((pl, idx) => {
        const bx = x + p + idx * (boxW + gap);
        fillRoundRect(ctx, bx, boxY, boxW, boxH, 14, "rgba(255,255,255,0.04)", "rgba(255,255,255,0.09)", 1);
        ctx.font = `700 11px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText(pl.label, bx + 12, boxY + 22);
        ctx.font = `800 22px ${FONT_STACK}`;
        ctx.fillStyle = pl.val === "—" ? "#64748B" : "#FFFFFF";
        drawWrappedText(ctx, pl.val, bx + 12, boxY + 54, boxW - 22, 24, 1);
        ctx.font = `600 12px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        drawWrappedText(ctx, pl.sub, bx + 12, boxY + 76, boxW - 22, 16, 1);
      });
      afterBoxesY = boxY + boxH;
    } else {
      // 1:1 side-by-side column -> generous 2x2 grid so all 4 labels & scores never clip
      const gapX = 10;
      const gapY = 9;
      const boxW = (barW - gapX) / 2;
      const boxH = 62;
      pillars.forEach((pl, idx) => {
        const col = idx % 2;
        const row = Math.floor(idx / 2);
        const bx = x + p + col * (boxW + gapX);
        const by = boxY + row * (boxH + gapY);
        fillRoundRect(ctx, bx, by, boxW, boxH, 12, "rgba(255,255,255,0.04)", "rgba(255,255,255,0.09)", 1);
        ctx.font = `700 10.5px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText(pl.label, bx + 10, by + 18);
        ctx.font = `800 17.5px ${FONT_STACK}`;
        ctx.fillStyle = pl.val === "—" ? "#64748B" : "#FFFFFF";
        drawWrappedText(ctx, pl.val, bx + 10, by + 41, boxW - 18, 20, 1);
        ctx.font = `600 10.5px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        drawWrappedText(ctx, pl.sub, bx + 10, by + 56, boxW - 18, 13, 1);
      });
      afterBoxesY = boxY + boxH * 2 + gapY;
    }

    // Property Status & Works Strip
    const st = getPropertyStatusMeta(hotel);
    const stCol = statusPillColors(st.tone);
    const stY = afterBoxesY + (isStory ? 18 : 12);
    const stH = isStory ? 84 : 64;
    fillRoundRect(ctx, x + p, stY, barW, stH, 14, stCol.bg, stCol.border, 1.2);
    ctx.font = `800 11.5px ${FONT_STACK}`;
    ctx.fillStyle = stCol.fg;
    ctx.fillText(`STATUS & WORKS • ${st.badge.toUpperCase()}`, x + p + 12, stY + 20);
    ctx.font = `500 ${isStory ? 17 : 13}px ${FONT_STACK}`;
    ctx.fillStyle = "#F1F5F9";
    drawWrappedText(ctx, st.shortSummary, x + p + 12, stY + 41, barW - 24, isStory ? 22 : 16, 2);

    // Bottom Section: Verified Key Facts + Real Local Hotel Photo (fills card cleanly with zero dead space)
    const facts = extractTopKeyFacts(hotel, odds, isStory ? 3 : 2);
    const imgObj = getCachedHotelImg(hotel);
    const awardLine =
      odds.officialAwards && odds.officialAwards.length
        ? `🏆 ${odds.officialAwards.slice(0, 2).map((a) => a.label).join(" • ")}`
        : hotel.priceRange
        ? `${hotel.location}, ${hotel.country} • ${hotel.priceRange}`
        : `${hotel.location}, ${hotel.country}`;

    if (isStory) {
      // Wide 9:16 Story bottom: 2-column split — 16:9 Hotel Photo (left) + Facts & Watch-Out (right)
      const splitY = stY + stH + 18;
      const splitH = Math.max(170, y + h - 18 - splitY);
      const photoW = imgObj ? Math.min(368, Math.round(splitH * (16 / 9))) : 0;
      const photoGap = imgObj ? 22 : 0;
      if (imgObj) {
        drawRoundedImageCover(ctx, imgObj, x + p, splitY, photoW, splitH, 16, "rgba(255,255,255,0.16)", awardLine, getYouTubeVideoBadge(hotel));
      }

      const textX = x + p + photoW + photoGap;
      const textW = barW - photoW - photoGap;
      let fy = splitY + 14;
      ctx.font = `800 12px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      ctx.fillText("VERIFIED KEY FACTS", textX, fy);
      fy += 24;

      facts.forEach((f) => {
        if (fy > y + h - 42) return;
        ctx.font = `700 15.5px ${FONT_STACK}`;
        ctx.fillStyle = accent;
        ctx.fillText(`• ${f.label}:`, textX, fy);
        const lw = ctx.measureText(`• ${f.label}: `).width;
        ctx.font = `500 15.5px ${FONT_STACK}`;
        ctx.fillStyle = "#E2E8F0";
        const used = drawWrappedText(ctx, f.value, textX + lw, fy, Math.max(120, textW - lw), 21, 2);
        fy += used * 21 + 8;
      });

      if (hotel.watchOut && fy < y + h - 44) {
        ctx.font = `800 13.5px ${FONT_STACK}`;
        ctx.fillStyle = "#FBBF24";
        ctx.fillText("WATCH-OUT:", textX, fy + 4);
        const wlw = ctx.measureText("WATCH-OUT: ").width;
        ctx.font = `500 14.5px ${FONT_STACK}`;
        ctx.fillStyle = "#CBD5E1";
        drawWrappedText(ctx, hotel.watchOut, textX + wlw, fy + 4, Math.max(120, textW - wlw), 20, 2);
      }
    } else {
      // 1:1 Feed bottom: Compact Key Facts + Exact 16:9 Rounded Hotel Photo (zero overlap!)
      const photoW = imgObj ? 320 : 0;
      const photoH = imgObj ? 180 : 0; // exact 16:9
      const photoX = x + p + Math.round((barW - photoW) / 2);
      const photoY = y + h - 16 - photoH;
      let fy = stY + stH + 15;
      const maxFactY = imgObj ? photoY - 10 : y + h - 24;
      if (fy < maxFactY - 12) {
        ctx.font = `800 11px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText("VERIFIED KEY FACTS", x + p, fy);
        fy += 17;
        facts.forEach((f) => {
          if (fy > maxFactY - 6) return;
          ctx.font = `700 12.5px ${FONT_STACK}`;
          ctx.fillStyle = accent;
          ctx.fillText(`• ${f.label}:`, x + p, fy);
          const lw = ctx.measureText(`• ${f.label}: `).width;
          ctx.font = `500 12.5px ${FONT_STACK}`;
          ctx.fillStyle = "#E2E8F0";
          const used = drawWrappedText(ctx, f.value, x + p + lw, fy, Math.max(100, barW - lw), 15, 1);
          fy += used * 15 + 5;
        });
      }

      if (imgObj) {
        drawRoundedImageCover(ctx, imgObj, photoX, photoY, photoW, photoH, 14, "rgba(255,255,255,0.18)", awardLine, getYouTubeVideoBadge(hotel));
      } else if (hotel.watchOut && fy < y + h - 42) {
        ctx.font = `800 12.5px ${FONT_STACK}`;
        ctx.fillStyle = "#FBBF24";
        ctx.fillText("WATCH-OUT:", x + p, fy + 6);
        ctx.font = `500 13px ${FONT_STACK}`;
        ctx.fillStyle = "#CBD5E1";
        drawWrappedText(ctx, hotel.watchOut, x + p, fy + 24, barW, 17, 3);
      }
    }
  };

  if (isStory) {
    const cardW = W - padX * 2;
    const cardH = 596;
    drawHotelPanel(hotelA, oddsA, "A", padX, 330, cardW, cardH);

    // Center VS divider badge
    fillRoundRect(ctx, W / 2 - 44, 938, 88, 44, 22, "#FF5D22");
    ctx.font = `800 22px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("VS", W / 2 - ctx.measureText("VS").width / 2, 968);

    drawHotelPanel(hotelB, oddsB, "B", padX, 994, cardW, cardH);

    // Story Footer with Scannable QR Code
    const footY = 1626;
    fillRoundRect(ctx, padX, footY, W - padX * 2, 232, 26, "rgba(255,255,255,0.05)", "rgba(255,255,255,0.12)", 1.5);
    drawQrOnCanvas(ctx, deepLink, W - padX - 210, footY + 21, 190);

    ctx.font = `800 16px ${FONT_STACK}`;
    ctx.fillStyle = "#FF8B5E";
    ctx.fillText("SCAN TO OPEN LIVE COMPARISON", padX + 28, footY + 52);

    ctx.font = `800 34px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX + 28, footY + 96);

    ctx.font = `500 18px ${FONT_STACK}`;
    ctx.fillStyle = "#CBD5E1";
    drawWrappedText(
      ctx,
      "Compare live Google guest ratings, official MICHELIN & Forbes awards, Opinion Gap, and verified property status — zero fabricated scores.",
      padX + 28,
      footY + 132,
      W - padX * 2 - 260,
      26,
      3
    );
  } else {
    const colGap = 24;
    const colW = (W - padX * 2 - colGap) / 2;
    const cardY = 266;
    const cardH = 684;
    drawHotelPanel(hotelA, oddsA, "A", padX, cardY, colW, cardH);
    drawHotelPanel(hotelB, oddsB, "B", padX + colW + colGap, cardY, colW, cardH);

    // Center VS badge placed cleanly on the top seam between cards (never overlaps score % or HOTEL B pill!)
    fillRoundRect(ctx, W / 2 - 30, cardY - 20, 60, 36, 18, "#FF5D22", "#071323", 4);
    ctx.font = `800 17px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("VS", W / 2 - ctx.measureText("VS").width / 2, cardY + 4);

    // Compact 1:1 Footer
    const footY = 974;
    ctx.font = `800 22px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX, footY + 30);
    ctx.font = `500 16px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    const rightTxt = "Zero fabricated scores • Real verified data only";
    ctx.fillText(rightTxt, W - padX - ctx.measureText(rightTxt).width, footY + 30);
  }
}

/* ==================== Render Single-Hotel Card (1:1 or 9:16) ==================== */
export function renderSingleHotelCanvas(canvas, hotel, odds, format = "1:1") {
  const isStory = format === "9:16";
  const W = 1080;
  const H = isStory ? 1920 : 1080;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  drawCardBackground(ctx, W, H);
  const padX = 60;
  drawHeaderBrand(ctx, W, padX, isStory ? 104 : 84, odds.tierLabel.toUpperCase());

  const deepLink = buildSingleDeepLink(hotel);
  const st = getPropertyStatusMeta(hotel);
  const stCol = statusPillColors(st.tone);

  // Main Hero Panel (generous height on 1:1 so 2-line titles + location NEVER collide with pillar boxes)
  const heroY = isStory ? 156 : 132;
  const heroH = isStory ? 364 : 302;
  fillRoundRect(ctx, padX, heroY, W - padX * 2, heroH, 28, "rgba(15, 29, 50, 0.9)", "rgba(255,93,34,0.4)", 2);

  // Big StayOdds score box top-right
  const scoreBoxW = 176;
  const scoreBoxH = isStory ? 124 : 112;
  const scoreBoxX = W - padX - 28 - scoreBoxW;
  const scoreBoxY = heroY + 24;
  const scoreTxt = odds.greatStayOdds != null ? `${odds.greatStayOdds}%` : "OPEN";
  fillRoundRect(ctx, scoreBoxX, scoreBoxY, scoreBoxW, scoreBoxH, 22, "#071323", "#FF5D22", 2.5);
  ctx.font = `800 ${isStory ? 52 : 48}px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  ctx.fillText(scoreTxt, scoreBoxX + scoreBoxW / 2 - ctx.measureText(scoreTxt).width / 2, scoreBoxY + (isStory ? 68 : 62));
  ctx.font = `800 13.5px ${FONT_STACK}`;
  ctx.fillStyle = "#FF8B5E";
  const subLbl = "STAYODDS";
  ctx.fillText(subLbl, scoreBoxX + scoreBoxW / 2 - ctx.measureText(subLbl).width / 2, scoreBoxY + (isStory ? 98 : 92));

  // Status badge pill (sized dynamically, capped safely left of score box)
  const badgeUpper = odds.statusBadge.toUpperCase();
  ctx.font = `800 13.5px ${FONT_STACK}`;
  const badgeMaxW = scoreBoxX - (padX + 46);
  const badgeW = Math.min(badgeMaxW, Math.max(160, ctx.measureText(badgeUpper).width + 34));
  fillRoundRect(ctx, padX + 28, heroY + 24, badgeW, 32, 16, "rgba(255,93,34,0.18)");
  ctx.fillStyle = "#FF8B5E";
  drawWrappedText(ctx, badgeUpper, padX + 44, heroY + 45, badgeW - 30, 18, 1);

  // Title & Location (kept strictly left of scoreBoxX and well above pillar boxes)
  const leftMaxW = scoreBoxX - (padX + 28) - 22;
  ctx.font = `800 ${isStory ? 44 : 34}px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  const nLines = drawWrappedText(ctx, hotel.name, padX + 28, heroY + (isStory ? 104 : 94), leftMaxW, isStory ? 50 : 40, 2);

  ctx.font = `600 ${isStory ? 22 : 18.5}px ${FONT_STACK}`;
  ctx.fillStyle = "#94A3B8";
  drawWrappedText(
    ctx,
    `${hotel.location}, ${hotel.country}${hotel.brand ? ` • ${hotel.brand}` : ""}${hotel.priceRange ? ` • ${hotel.priceRange}` : ""}`,
    padX + 28,
    heroY + (isStory ? 110 : 98) + nLines * (isStory ? 48 : 38),
    leftMaxW,
    24,
    1
  );

  // 4 Pillars inside hero bottom (Uncharted Stay | Critics / Other | Guests | Opinion Gap)
  const criticInfo = formatCriticSlot(odds);
  const pH = isStory ? 94 : 78;
  const pY = heroY + heroH - pH - 20;
  const pGap = 12;
  const pW = (W - padX * 2 - 56 - pGap * 3) / 4;
  const pillars = [
    {
      label: "UNCHARTED STAY",
      val: odds.personalScoreLabel ? odds.personalScoreLabel.replace(/ /g, "") : odds.visited ? "Filmed" : "—",
      sub: odds.personalScoreLabel ? "YouTube Review" : odds.visited ? "Unscored" : "Not stayed",
    },
    {
      label: "CRITICS / OTHER",
      val: criticInfo.compact,
      sub: criticInfo.sub,
    },
    {
      label: "VERIFIED GUESTS",
      val: odds.verifiedGuest ? `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}` : "Live",
      sub: odds.verifiedGuest ? "Verified" : "Google Maps",
    },
    {
      label: "OPINION GAP",
      val: odds.opinionGap ? odds.opinionGap.deltaLabel : "—",
      sub: odds.opinionGap && odds.opinionGap.deltaLabel && odds.opinionGap.deltaLabel !== "—" ? "Spread" : "No gap yet",
    },
  ];
  pillars.forEach((pl, idx) => {
    const bx = padX + 28 + idx * (pW + pGap);
    fillRoundRect(ctx, bx, pY, pW, pH, 16, "rgba(255,255,255,0.05)", "rgba(255,255,255,0.1)", 1);
    ctx.font = `700 11px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    ctx.fillText(pl.label, bx + 13, pY + 22);
    ctx.font = `800 ${isStory ? 23 : 19.5}px ${FONT_STACK}`;
    ctx.fillStyle = pl.val === "—" ? "#64748B" : "#FFFFFF";
    drawWrappedText(ctx, pl.val, bx + 13, pY + (isStory ? 55 : 49), pW - 22, 24, 1);
    ctx.font = `600 11.5px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    drawWrappedText(ctx, pl.sub, bx + 13, pY + (isStory ? 78 : 68), pW - 22, 15, 1);
  });

  // Opinion Gap Box
  const ogY = heroY + heroH + (isStory ? 26 : 16);
  const ogH = isStory ? 172 : 114;
  fillRoundRect(ctx, padX, ogY, W - padX * 2, ogH, 24, "rgba(20, 184, 166, 0.1)", "rgba(45, 212, 191, 0.35)", 1.5);
  ctx.font = `800 13.5px ${FONT_STACK}`;
  ctx.fillStyle = "#5EEAD4";
  drawWrappedText(ctx, `OPINION GAP • ${odds.opinionGap.title.toUpperCase()}`, padX + 28, ogY + 32, W - padX * 2 - 220, 18, 1);

  fillRoundRect(ctx, W - padX - 178, ogY + 18, 150, 42, 14, "#071323", "#14B8A6", 1.5);
  ctx.font = `800 21px ${FONT_STACK}`;
  ctx.fillStyle = "#5EEAD4";
  const dTxt = odds.opinionGap.deltaLabel || "—";
  ctx.fillText(dTxt, W - padX - 103 - ctx.measureText(dTxt).width / 2, ogY + 46);

  ctx.font = `600 ${isStory ? 22 : 18}px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  drawWrappedText(ctx, odds.opinionGap.headline, padX + 28, ogY + (isStory ? 74 : 68), W - padX * 2 - 216, isStory ? 30 : 23, 2);

  // Property Status & Works Box
  const stY = ogY + ogH + (isStory ? 26 : 16);
  const stH = isStory ? 192 : 108;
  fillRoundRect(ctx, padX, stY, W - padX * 2, stH, 24, stCol.bg, stCol.border, 1.5);
  ctx.font = `800 13.5px ${FONT_STACK}`;
  ctx.fillStyle = stCol.fg;
  ctx.fillText(`PROPERTY STATUS & WORKS • ${st.badge.toUpperCase()}`, padX + 28, stY + 31);
  ctx.font = `600 ${isStory ? 21 : 17}px ${FONT_STACK}`;
  ctx.fillStyle = "#F8FAFC";
  drawWrappedText(ctx, st.shortSummary, padX + 28, stY + 64, W - padX * 2 - 56, isStory ? 29 : 22, isStory ? 3 : 2);

  // Key Facts & Highlights Panel (+ Real Local Hotel Photo)
  const kfY = stY + stH + (isStory ? 24 : 16);
  const kfH = isStory ? 616 : 264;
  fillRoundRect(ctx, padX, kfY, W - padX * 2, kfH, 24, "rgba(15, 29, 50, 0.85)", "rgba(255,255,255,0.1)", 1.5);
  ctx.font = `800 14.5px ${FONT_STACK}`;
  ctx.fillStyle = "#FF8B5E";
  ctx.fillText("VERIFIED KEY FACTS & PROPERTY SNAPSHOT", padX + 28, kfY + 34);

  const imgObj = getCachedHotelImg(hotel);
  const awardOverlay =
    odds.officialAwards && odds.officialAwards.length
      ? `🏆 ${odds.officialAwards.slice(0, 2).map((a) => a.label).join(" • ")}`
      : `${hotel.location}, ${hotel.country}`;

  const facts = extractTopKeyFacts(hotel, odds, isStory ? 4 : 3);
  if (isStory) {
    let fy = kfY + 62;
    if (imgObj) {
      const phW = W - padX * 2 - 56;
      const phH = 264;
      drawRoundedImageCover(ctx, imgObj, padX + 28, fy, phW, phH, 18, "rgba(255,255,255,0.16)", awardOverlay, getYouTubeVideoBadge(hotel));
      fy += phH + 34;
    } else {
      fy = kfY + 76;
    }
    facts.forEach((f) => {
      if (fy > kfY + kfH - 60) return;
      ctx.font = `800 20px ${FONT_STACK}`;
      ctx.fillStyle = "#5EEAD4";
      ctx.fillText(`${f.label}:`, padX + 28, fy);
      const lw = ctx.measureText(`${f.label}: `).width;
      ctx.font = `500 20px ${FONT_STACK}`;
      ctx.fillStyle = "#E2E8F0";
      const linesUsed = drawWrappedText(ctx, f.value, padX + 28 + lw, fy, W - padX * 2 - 56 - lw, 27, 2);
      fy += linesUsed * 27 + 14;
    });
    if (hotel.watchOut && fy < kfY + kfH - 48) {
      ctx.font = `800 19px ${FONT_STACK}`;
      ctx.fillStyle = "#FBBF24";
      ctx.fillText("Watch-Out:", padX + 28, fy + 6);
      ctx.font = `500 19px ${FONT_STACK}`;
      ctx.fillStyle = "#E2E8F0";
      drawWrappedText(ctx, hotel.watchOut, padX + 28, fy + 34, W - padX * 2 - 56, 26, 3);
    }
  } else {
    // 1:1 Single Card: Left = Facts + Watch-Out, Right = crisp 16:9 Hotel Photo
    const photoW = imgObj ? 320 : 0;
    const photoH = 180;
    const textMaxW = imgObj ? W - padX * 2 - 56 - photoW - 24 : W - padX * 2 - 56;
    if (imgObj) {
      drawRoundedImageCover(
        ctx,
        imgObj,
        W - padX - 28 - photoW,
        kfY + 56,
        photoW,
        photoH,
        16,
        "rgba(255,255,255,0.16)",
        awardOverlay,
        getYouTubeVideoBadge(hotel)
      );
    }
    let fy = kfY + 70;
    facts.forEach((f) => {
      if (fy > kfY + kfH - 36) return;
      ctx.font = `800 15.5px ${FONT_STACK}`;
      ctx.fillStyle = "#5EEAD4";
      ctx.fillText(`${f.label}:`, padX + 28, fy);
      const lw = ctx.measureText(`${f.label}: `).width;
      ctx.font = `500 15.5px ${FONT_STACK}`;
      ctx.fillStyle = "#E2E8F0";
      const linesUsed = drawWrappedText(ctx, f.value, padX + 28 + lw, fy, Math.max(160, textMaxW - lw), 20, 2);
      fy += linesUsed * 20 + 9;
    });
    if (hotel.watchOut && fy < kfY + kfH - 36) {
      ctx.font = `800 14.5px ${FONT_STACK}`;
      ctx.fillStyle = "#FBBF24";
      ctx.fillText("Watch-Out:", padX + 28, fy + 4);
      ctx.font = `500 14.5px ${FONT_STACK}`;
      ctx.fillStyle = "#E2E8F0";
      drawWrappedText(ctx, hotel.watchOut, padX + 28, fy + 24, textMaxW, 19, 2);
    }
  }

  // Footer
  if (isStory) {
    const footY = 1626;
    fillRoundRect(ctx, padX, footY, W - padX * 2, 232, 26, "rgba(255,255,255,0.05)", "rgba(255,255,255,0.12)", 1.5);
    drawQrOnCanvas(ctx, deepLink, W - padX - 210, footY + 21, 190);
    ctx.font = `800 16px ${FONT_STACK}`;
    ctx.fillStyle = "#FF8B5E";
    ctx.fillText("SCAN FOR FULL VERIFIED BREAKDOWN", padX + 28, footY + 52);
    ctx.font = `800 34px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX + 28, footY + 96);
    ctx.font = `500 18px ${FONT_STACK}`;
    ctx.fillStyle = "#CBD5E1";
    drawWrappedText(
      ctx,
      "Compare 832+ luxury hotels • Zero fabricated scores • Real verified data only",
      padX + 28,
      footY + 134,
      W - padX * 2 - 260,
      26,
      2
    );
  } else {
    const footY = 994;
    ctx.font = `800 22px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX, footY + 26);
    ctx.font = `500 15px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    const rightTxt = "Zero fabricated scores • Real verified data only";
    ctx.fillText(rightTxt, W - padX - ctx.measureText(rightTxt).width, footY + 26);
  }
}

/* ==================== Interactive Share Modal UI ==================== */

let modalEl = null;

function ensureModalDom() {
  if (modalEl) return modalEl;
  const wrap = document.createElement("div");
  wrap.id = "stayOddsShareModal";
  wrap.className = "so-share-modal-backdrop";
  wrap.setAttribute("role", "dialog");
  wrap.setAttribute("aria-modal", "true");
  wrap.setAttribute("aria-labelledby", "soShareModalTitle");
  wrap.style.display = "none";
  wrap.innerHTML = `
    <div class="so-share-modal-card">
      <div class="so-share-modal-head">
        <div>
          <span class="so-share-eyebrow">BRANDED STAYODDS EXPORT</span>
          <h3 id="soShareModalTitle">Share Verified Scorecard</h3>
        </div>
        <button type="button" class="so-share-close" id="soShareCloseBtn" aria-label="Close share dialog">&times;</button>
      </div>

      <div class="so-share-format-row" role="tablist" aria-label="Choose export aspect ratio">
        <button type="button" class="so-format-pill active" data-so-format="1:1" role="tab" aria-selected="true">
          <strong>1:1 Feed</strong>
          <small>1080 &times; 1080 (X / IG / Reddit)</small>
        </button>
        <button type="button" class="so-format-pill" data-so-format="9:16" role="tab" aria-selected="false">
          <strong>9:16 Story + QR</strong>
          <small>1080 &times; 1920 (Stories / WhatsApp)</small>
        </button>
      </div>

      <div class="so-share-preview-wrap">
        <canvas id="soShareCanvas" class="so-share-canvas"></canvas>
      </div>

      <div class="so-share-toast" id="soShareToast" role="status" aria-live="polite"></div>

      <div class="so-share-actions-grid">
        <button type="button" class="btn btn-primary so-share-primary" id="soDownloadPngBtn">&#x2B07; Download / Share PNG</button>
        <button type="button" class="btn btn-outline" id="soPostXBtn">&#x1D54F; Post to X</button>
        <button type="button" class="btn btn-outline" id="soCopyRedditBtn">&#x1F4CB; Copy Reddit / FlyerTalk Table</button>
        <button type="button" class="btn btn-outline" id="soCopyLinkBtn">&#x1F517; Copy Deep Link</button>
      </div>
    </div>
  `;
  document.body.appendChild(wrap);

  wrap.addEventListener("click", (e) => {
    if (e.target === wrap) closeShareModal();
  });
  wrap.querySelector("#soShareCloseBtn").addEventListener("click", closeShareModal);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && wrap.style.display !== "none") closeShareModal();
  });
  modalEl = wrap;
  return wrap;
}

function closeShareModal() {
  if (modalEl) {
    modalEl.style.display = "none";
    document.body.style.overflow = "";
  }
}

let toastTimer = null;
function showToast(msg) {
  const el = modalEl && modalEl.querySelector("#soShareToast");
  if (!el) return;
  el.textContent = msg;
  el.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("is-visible"), 3200);
}

async function copyText(str) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(str);
  } else {
    const ta = document.createElement("textarea");
    ta.value = str;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    ta.remove();
  }
}

function openModalInternal({ title, filePrefix, deepLink, tweetText, redditMarkdown, preloadHotels = [], renderFn }) {
  const wrap = ensureModalDom();
  let currentFormat = "1:1";
  const canvas = wrap.querySelector("#soShareCanvas");
  wrap.querySelector("#soShareModalTitle").textContent = title;

  const rerender = () => {
    renderFn(canvas, currentFormat);
    canvas.classList.toggle("is-story", currentFormat === "9:16");
    wrap.querySelectorAll("[data-so-format]").forEach((btn) => {
      const active = btn.dataset.soFormat === currentFormat;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-selected", String(active));
    });
  };

  const imagesReady = Promise.all((preloadHotels || []).map((h) => loadSameOriginHotelImg(h))).then(() => {
    if (wrap.style.display === "flex") rerender();
  });

  wrap.querySelectorAll("[data-so-format]").forEach((btn) => {
    btn.onclick = () => {
      currentFormat = btn.dataset.soFormat || "1:1";
      rerender();
    };
  });

  wrap.querySelector("#soDownloadPngBtn").onclick = async () => {
    await imagesReady.catch(() => {});
    const filename = `${filePrefix}-${currentFormat === "9:16" ? "story-9x16" : "feed-1x1"}.png`;
    canvas.toBlob(async (blob) => {
      if (!blob) {
        showToast("Could not generate PNG.");
        return;
      }
      const file = new File([blob], filename, { type: "image/png" });
      if (navigator.share && navigator.canShare && navigator.canShare({ files: [file] })) {
        try {
          await navigator.share({
            title,
            text: tweetText,
            url: deepLink,
            files: [file],
          });
          showToast("Shared scorecard PNG!");
          return;
        } catch (err) {
          if (err && err.name === "AbortError") return;
        }
      }
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(objUrl), 5000);
      await copyText(deepLink).catch(() => {});
      showToast("PNG downloaded & deep link copied to clipboard!");
    }, "image/png");
  };

  wrap.querySelector("#soPostXBtn").onclick = () => {
    const intent = `https://x.com/intent/tweet?text=${encodeURIComponent(tweetText)}&url=${encodeURIComponent(deepLink)}`;
    window.open(intent, "_blank", "noopener,noreferrer");
  };

  wrap.querySelector("#soCopyRedditBtn").onclick = async () => {
    await copyText(redditMarkdown);
    showToast("✓ Reddit / FlyerTalk Markdown table copied!");
  };

  wrap.querySelector("#soCopyLinkBtn").onclick = async () => {
    await copyText(deepLink);
    showToast("✓ Shareable deep link copied!");
  };

  wrap.style.display = "flex";
  document.body.style.overflow = "hidden";
  rerender();
}

export function openVsShareModal(hotelA, hotelB, oddsA, oddsB) {
  const verdict = buildFactualVsVerdict(hotelA, hotelB, oddsA, oddsB);
  const deepLink = buildVsDeepLink(hotelA, hotelB);
  const tweetText = `${hotelA.name} vs ${hotelB.name} on StayOdds (stayodds.com): ${verdict.headline}. Verified scores & key facts — zero made-up numbers:`;
  openModalInternal({
    title: `${hotelA.name} vs ${hotelB.name}`,
    filePrefix: `stayodds-${hotelA.id}-vs-${hotelB.id}`,
    deepLink,
    tweetText,
    redditMarkdown: buildRedditMarkdownVs(hotelA, hotelB, oddsA, oddsB),
    preloadHotels: [hotelA, hotelB],
    renderFn: (canvas, fmt) => renderVsCanvas(canvas, hotelA, hotelB, oddsA, oddsB, fmt),
  });
}

/* ==================== Render 3-Hotel Comparison Card (1:1 or 9:16) ==================== */
export function renderThreeWayCanvas(canvas, hotelA, hotelB, hotelC, oddsA, oddsB, oddsC, format = "1:1") {
  const isStory = format === "9:16";
  const W = 1080;
  const H = isStory ? 1920 : 1080;
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");

  drawCardBackground(ctx, W, H);
  const padX = isStory ? 48 : 44;
  drawHeaderBrand(ctx, W, padX, isStory ? 96 : 86, "VERIFIED 3-HOTEL COMPARE");

  const verdict = buildFactualThreeWayVerdict(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC);
  const deepLink = buildThreeWayDeepLink(hotelA, hotelB, hotelC);

  // Verdict Banner
  const vY = isStory ? 142 : 128;
  const vH = isStory ? 124 : 106;
  fillRoundRect(ctx, padX, vY, W - padX * 2, vH, 22, "rgba(255,93,34,0.13)", "rgba(255,93,34,0.48)", 2);
  ctx.font = `800 14px ${FONT_STACK}`;
  ctx.fillStyle = "#FF8B5E";
  ctx.fillText("VERIFIED 3-HOTEL VERDICT", padX + 22, vY + 30);

  ctx.font = `800 ${isStory ? 26 : 23}px ${FONT_STACK}`;
  ctx.fillStyle = "#FFFFFF";
  drawWrappedText(ctx, verdict.headline, padX + 22, vY + (isStory ? 64 : 60), W - padX * 2 - 44, 30, 1);

  ctx.font = `500 ${isStory ? 18.5 : 16}px ${FONT_STACK}`;
  ctx.fillStyle = "#CBD5E1";
  drawWrappedText(ctx, verdict.detail, padX + 22, vY + (isStory ? 96 : 88), W - padX * 2 - 44, 23, isStory ? 2 : 1);

  const items = [
    { side: "A", hotel: hotelA, odds: oddsA, accent: "#FF5D22", badgeBg: "rgba(255,93,34,0.22)", badgeFg: "#FF8B5E" },
    { side: "B", hotel: hotelB, odds: oddsB, accent: "#14B8A6", badgeBg: "rgba(20,184,166,0.22)", badgeFg: "#5EEAD4" },
    { side: "C", hotel: hotelC, odds: oddsC, accent: "#818CF8", badgeBg: "rgba(99,102,241,0.24)", badgeFg: "#A5B4FC" },
  ];

  const makePillars = (odds) => {
    const criticInfo = formatCriticSlot(odds);
    return [
      {
        label: "UNCHARTED",
        val: odds.personalScoreLabel ? odds.personalScoreLabel.replace(/ /g, "") : odds.visited ? "Filmed" : "—",
        sub: odds.personalScoreLabel ? "YouTube Review" : odds.visited ? "Unscored" : "Not stayed",
      },
      {
        label: "CRITICS",
        val: criticInfo.compact,
        sub: criticInfo.sub,
      },
      {
        label: "GUESTS",
        val: odds.verifiedGuest ? `${odds.verifiedGuest.rating.toFixed(1)}/${odds.verifiedGuest.scale}` : "Live",
        sub: odds.verifiedGuest ? "Verified" : "Google Maps",
      },
      {
        label: "GAP",
        val: odds.opinionGap ? odds.opinionGap.deltaLabel : "—",
        sub: odds.opinionGap && odds.opinionGap.deltaLabel && odds.opinionGap.deltaLabel !== "—" ? "Spread" : "No gap yet",
      },
    ];
  };

  if (isStory) {
    // 9:16 Story: 3 stacked horizontal wide panels + exact 16:9 photos + QR footer
    const cardW = W - padX * 2;
    const cardH = 420;
    const gapY = 18;
    const startY = 286;

    items.forEach((it, idx) => {
      const { side, hotel, odds, accent, badgeBg, badgeFg } = it;
      const isWin = verdict.winnerSide === side;
      const x = padX;
      const y = startY + idx * (cardH + gapY);
      const p = 20;
      const innerW = cardW - p * 2;

      fillRoundRect(ctx, x, y, cardW, cardH, 24, "rgba(15, 29, 50, 0.88)", isWin ? accent : "rgba(255,255,255,0.12)", isWin ? 2.5 : 1.5);

      // Side badge + Status
      fillRoundRect(ctx, x + p, y + p, 108, 28, 14, badgeBg);
      ctx.font = `800 13px ${FONT_STACK}`;
      ctx.fillStyle = badgeFg;
      ctx.fillText(`HOTEL ${side}${isWin ? " ★" : ""}`, x + p + 14, y + p + 19);

      ctx.font = `700 12.5px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      ctx.fillText(odds.statusBadge.toUpperCase(), x + p + 120, y + p + 19);

      // Score box top-right
      const scoreText = odds.greatStayOdds != null ? `${odds.greatStayOdds}%` : "OPEN";
      fillRoundRect(ctx, x + cardW - p - 118, y + p - 2, 118, 62, 16, "rgba(7,19,35,0.92)", accent, 2);
      ctx.font = `800 30px ${FONT_STACK}`;
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(scoreText, x + cardW - p - 59 - ctx.measureText(scoreText).width / 2, y + p + 33);
      ctx.font = `700 10.5px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      ctx.fillText("STAYODDS", x + cardW - p - 59 - ctx.measureText("STAYODDS").width / 2, y + p + 50);

      // Hotel Name & Location
      ctx.font = `800 26px ${FONT_STACK}`;
      ctx.fillStyle = "#FFFFFF";
      drawWrappedText(ctx, hotel.name, x + p, y + p + 58, innerW - 134, 30, 1);

      ctx.font = `500 16.5px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      drawWrappedText(
        ctx,
        `${hotel.location}, ${hotel.country}${hotel.brand ? ` • ${hotel.brand}` : ""}`,
        x + p,
        y + p + 82,
        innerW - 134,
        20,
        1
      );

      // Progress bar
      const barY = y + p + 96;
      fillRoundRect(ctx, x + p, barY, innerW, 10, 5, "rgba(255,255,255,0.09)");
      if (odds.greatStayOdds != null) {
        fillRoundRect(ctx, x + p, barY, Math.max(20, (innerW * odds.greatStayOdds) / 100), 10, 5, accent);
      }

      // 4-column metric strip
      const pillars = makePillars(odds);
      const boxY = barY + 18;
      const boxH = 74;
      const gapX = 10;
      const boxW = (innerW - gapX * 3) / 4;
      pillars.forEach((pl, pi) => {
        const bx = x + p + pi * (boxW + gapX);
        fillRoundRect(ctx, bx, boxY, boxW, boxH, 12, "rgba(255,255,255,0.04)", "rgba(255,255,255,0.09)", 1);
        ctx.font = `700 11px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText(pl.label, bx + 11, boxY + 20);
        ctx.font = `800 19.5px ${FONT_STACK}`;
        ctx.fillStyle = pl.val === "—" ? "#64748B" : "#FFFFFF";
        drawWrappedText(ctx, pl.val, bx + 11, boxY + 46, boxW - 20, 22, 1);
        ctx.font = `600 11.5px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        drawWrappedText(ctx, pl.sub, bx + 11, boxY + 64, boxW - 20, 14, 1);
      });

      // Bottom split: exact 16:9 photo (288x162) on left + status & key facts on right
      const splitY = boxY + boxH + 16;
      const imgObj = getCachedHotelImg(hotel);
      const photoW = imgObj ? 288 : 0;
      const photoH = 162; // exact 16:9
      const photoGap = imgObj ? 20 : 0;
      const awardOverlay =
        odds.officialAwards && odds.officialAwards.length
          ? `🏆 ${odds.officialAwards.slice(0, 2).map((a) => a.label).join(" • ")}`
          : `${hotel.location}, ${hotel.country}`;
      if (imgObj) {
        drawRoundedImageCover(ctx, imgObj, x + p, splitY, photoW, photoH, 14, "rgba(255,255,255,0.16)", awardOverlay, getYouTubeVideoBadge(hotel));
      }

      const textX = x + p + photoW + photoGap;
      const textW = innerW - photoW - photoGap;
      const st = getPropertyStatusMeta(hotel);
      const stCol = statusPillColors(st.tone);
      fillRoundRect(ctx, textX, splitY, textW, 56, 12, stCol.bg, stCol.border, 1.1);
      ctx.font = `800 11px ${FONT_STACK}`;
      ctx.fillStyle = stCol.fg;
      ctx.fillText(`STATUS & WORKS • ${st.badge.toUpperCase()}`, textX + 12, splitY + 19);
      ctx.font = `500 13.5px ${FONT_STACK}`;
      ctx.fillStyle = "#F1F5F9";
      drawWrappedText(ctx, st.shortSummary, textX + 12, splitY + 39, textW - 24, 17, 1);

      const facts = extractTopKeyFacts(hotel, odds, 2);
      let fy = splitY + 80;
      facts.forEach((f) => {
        if (fy > y + cardH - 16) return;
        ctx.font = `700 14.5px ${FONT_STACK}`;
        ctx.fillStyle = accent;
        ctx.fillText(`• ${f.label}:`, textX, fy);
        const lw = ctx.measureText(`• ${f.label}: `).width;
        ctx.font = `500 14.5px ${FONT_STACK}`;
        ctx.fillStyle = "#E2E8F0";
        const used = drawWrappedText(ctx, f.value, textX + lw, fy, Math.max(120, textW - lw), 19, 2);
        fy += used * 19 + 8;
      });
    });

    // Story Footer with QR Code
    const footY = 1618;
    fillRoundRect(ctx, padX, footY, W - padX * 2, 238, 26, "rgba(255,255,255,0.05)", "rgba(255,255,255,0.12)", 1.5);
    drawQrOnCanvas(ctx, deepLink, W - padX - 210, footY + 24, 190);

    ctx.font = `800 16px ${FONT_STACK}`;
    ctx.fillStyle = "#FF8B5E";
    ctx.fillText("SCAN TO OPEN LIVE 3-HOTEL COMPARISON", padX + 28, footY + 56);

    ctx.font = `800 34px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX + 28, footY + 100);

    ctx.font = `500 18px ${FONT_STACK}`;
    ctx.fillStyle = "#CBD5E1";
    drawWrappedText(
      ctx,
      "Compare 3 luxury hotels side by side with live Google guest ratings, MICHELIN & Forbes awards, and verified property facts.",
      padX + 28,
      footY + 136,
      W - padX * 2 - 260,
      25,
      3
    );
  } else {
    // 1:1 Feed: 3 side-by-side columns with exact 16:9 photos pinned cleanly at bottom
    const colGap = 16;
    const colW = (W - padX * 2 - colGap * 2) / 3; // 320px
    const cardY = 252;
    const cardH = 710;

    items.forEach((it, idx) => {
      const { side, hotel, odds, accent, badgeBg, badgeFg } = it;
      const isWin = verdict.winnerSide === side;
      const x = padX + idx * (colW + colGap);
      const y = cardY;
      const p = 16;
      const innerW = colW - p * 2; // 288px

      fillRoundRect(ctx, x, y, colW, cardH, 22, "rgba(15, 29, 50, 0.88)", isWin ? accent : "rgba(255,255,255,0.12)", isWin ? 2.5 : 1.5);

      // Side badge top-left
      fillRoundRect(ctx, x + p, y + p, 96, 26, 13, badgeBg);
      ctx.font = `800 12.5px ${FONT_STACK}`;
      ctx.fillStyle = badgeFg;
      ctx.fillText(`HOTEL ${side}${isWin ? " ★" : ""}`, x + p + 11, y + p + 17);

      // Score box top-right
      const scoreText = odds.greatStayOdds != null ? `${odds.greatStayOdds}%` : "OPEN";
      fillRoundRect(ctx, x + colW - p - 92, y + p - 2, 92, 54, 14, "rgba(7,19,35,0.92)", accent, 1.8);
      ctx.font = `800 25px ${FONT_STACK}`;
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(scoreText, x + colW - p - 46 - ctx.measureText(scoreText).width / 2, y + p + 28);
      ctx.font = `700 9.5px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      ctx.fillText("STAYODDS", x + colW - p - 46 - ctx.measureText("STAYODDS").width / 2, y + p + 44);

      // Hotel Name & Location
      ctx.font = `800 20px ${FONT_STACK}`;
      ctx.fillStyle = "#FFFFFF";
      const nameLines = drawWrappedText(ctx, hotel.name, x + p, y + p + 80, innerW, 24, 2);

      const locY = y + p + 82 + nameLines * 24;
      ctx.font = `500 13.5px ${FONT_STACK}`;
      ctx.fillStyle = "#94A3B8";
      drawWrappedText(ctx, `${hotel.location}, ${hotel.country}`, x + p, locY, innerW, 18, 1);

      // Progress Bar
      const barY = locY + 14;
      fillRoundRect(ctx, x + p, barY, innerW, 9, 4.5, "rgba(255,255,255,0.09)");
      if (odds.greatStayOdds != null) {
        fillRoundRect(ctx, x + p, barY, Math.max(18, (innerW * odds.greatStayOdds) / 100), 9, 4.5, accent);
      }

      // 2x2 Metrics Grid
      const pillars = makePillars(odds);
      const boxY = barY + 18;
      const gapX = 8;
      const gapY = 8;
      const boxW = (innerW - gapX) / 2;
      const boxH = 60;
      pillars.forEach((pl, pi) => {
        const col = pi % 2;
        const row = Math.floor(pi / 2);
        const bx = x + p + col * (boxW + gapX);
        const by = boxY + row * (boxH + gapY);
        fillRoundRect(ctx, bx, by, boxW, boxH, 10, "rgba(255,255,255,0.04)", "rgba(255,255,255,0.09)", 1);
        ctx.font = `700 10px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText(pl.label, bx + 9, by + 18);
        ctx.font = `800 16px ${FONT_STACK}`;
        ctx.fillStyle = pl.val === "—" ? "#64748B" : "#FFFFFF";
        drawWrappedText(ctx, pl.val, bx + 9, by + 40, boxW - 16, 18, 1);
        ctx.font = `600 10px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        drawWrappedText(ctx, pl.sub, bx + 9, by + 54, boxW - 16, 12, 1);
      });

      // Status Strip
      const st = getPropertyStatusMeta(hotel);
      const stCol = statusPillColors(st.tone);
      const stY = boxY + boxH * 2 + gapY + 12;
      const stH = 62;
      fillRoundRect(ctx, x + p, stY, innerW, stH, 12, stCol.bg, stCol.border, 1.1);
      ctx.font = `800 10.5px ${FONT_STACK}`;
      ctx.fillStyle = stCol.fg;
      ctx.fillText(`STATUS • ${st.badge.toUpperCase()}`, x + p + 10, stY + 19);
      ctx.font = `500 12px ${FONT_STACK}`;
      ctx.fillStyle = "#F1F5F9";
      drawWrappedText(ctx, st.shortSummary, x + p + 10, stY + 37, innerW - 20, 15, 2);

      // Exact 16:9 Hotel Photo pinned cleanly at bottom (288 x 162 -> exact 16:9)
      const imgObj = getCachedHotelImg(hotel);
      const photoW = imgObj ? innerW : 0;
      const photoH = imgObj ? 162 : 0;
      const photoY = y + cardH - p - photoH;
      const awardOverlay =
        odds.officialAwards && odds.officialAwards.length
          ? `🏆 ${odds.officialAwards.slice(0, 1).map((a) => a.label).join("")}`
          : `${hotel.location}, ${hotel.country}`;

      // Verified Key Facts between Status & Photo
      const facts = extractTopKeyFacts(hotel, odds, 2);
      let fy = stY + stH + 18;
      const maxFactY = imgObj ? photoY - 12 : y + cardH - 22;
      if (fy < maxFactY - 14) {
        ctx.font = `800 10.5px ${FONT_STACK}`;
        ctx.fillStyle = "#94A3B8";
        ctx.fillText("KEY FACTS", x + p, fy);
        fy += 16;
        facts.forEach((f) => {
          if (fy > maxFactY - 8) return;
          ctx.font = `700 12px ${FONT_STACK}`;
          ctx.fillStyle = accent;
          ctx.fillText(`• ${f.label}:`, x + p, fy);
          const lw = ctx.measureText(`• ${f.label}: `).width;
          ctx.font = `500 12px ${FONT_STACK}`;
          ctx.fillStyle = "#E2E8F0";
          const used = drawWrappedText(ctx, f.value, x + p + lw, fy, Math.max(80, innerW - lw), 15, 1);
          fy += used * 15 + 6;
        });
      }

      if (imgObj) {
        drawRoundedImageCover(ctx, imgObj, x + p, photoY, photoW, photoH, 12, "rgba(255,255,255,0.18)", awardOverlay, getYouTubeVideoBadge(hotel));
      }
    });

    // 1:1 Footer
    const footY = 986;
    ctx.font = `800 22px ${FONT_STACK}`;
    ctx.fillStyle = "#FFFFFF";
    ctx.fillText("stayodds.com", padX, footY + 26);
    ctx.font = `500 15.5px ${FONT_STACK}`;
    ctx.fillStyle = "#94A3B8";
    const rightTxt = "Zero fabricated scores • Real verified data only";
    ctx.fillText(rightTxt, W - padX - ctx.measureText(rightTxt).width, footY + 26);
  }
}

export function openThreeWayShareModal(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC) {
  const verdict = buildFactualThreeWayVerdict(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC);
  const deepLink = buildThreeWayDeepLink(hotelA, hotelB, hotelC);
  const tweetText = `${hotelA.name} vs ${hotelB.name} vs ${hotelC.name} on StayOdds (stayodds.com): ${verdict.headline}. Verified 3-hotel breakdown — zero made-up numbers:`;
  openModalInternal({
    title: `${hotelA.name} vs ${hotelB.name} vs ${hotelC.name}`,
    filePrefix: `stayodds-${hotelA.id}-vs-${hotelB.id}-vs-${hotelC.id}`,
    deepLink,
    tweetText,
    redditMarkdown: buildRedditMarkdownThreeWay(hotelA, hotelB, hotelC, oddsA, oddsB, oddsC),
    preloadHotels: [hotelA, hotelB, hotelC],
    renderFn: (canvas, fmt) => renderThreeWayCanvas(canvas, hotelA, hotelB, hotelC, oddsA, oddsB, oddsC, fmt),
  });
}

export function openSingleHotelShareModal(hotel, odds) {
  const deepLink = buildSingleDeepLink(hotel);
  const scorePart = odds.greatStayOdds != null ? ` (${odds.greatStayOdds}% StayOdds)` : "";
  const tweetText = `${hotel.name}${scorePart} — ${odds.statusBadge} on StayOdds (stayodds.com). Real verified guest ratings, official awards & property status:`;
  openModalInternal({
    title: `${hotel.name} — StayOdds Card`,
    filePrefix: `stayodds-${hotel.id}`,
    deepLink,
    tweetText,
    redditMarkdown: buildRedditMarkdownSingle(hotel, odds),
    preloadHotels: [hotel],
    renderFn: (canvas, fmt) => renderSingleHotelCanvas(canvas, hotel, odds, fmt),
  });
}
