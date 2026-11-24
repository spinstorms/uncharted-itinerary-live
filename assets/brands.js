import { computeStayOdds, formatPersonalScore, isFirstHandVerified } from "./stayodds-engine.js?v=8";
import { normalizeBrandName, getPartnerPrograms, getVerifiedRoomTip } from "./stayodds-insights.js?v=2";

const qs = (s) => document.querySelector(s);
const oddsCache = new WeakMap();
const getOdds = (h) => {
  let c = oddsCache.get(h);
  if (!c) {
    c = computeStayOdds(h);
    oddsCache.set(h, c);
  }
  return c;
};

function escapeHtml(str = "") {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getMichelinKeyCount(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/michelin/i.test(txt)) {
      const m = String(a.label || "").match(/([123])\s*michelin\s*key/i);
      const val = m ? Number(m[1]) : 1;
      if (best == null || val > best) best = val;
    }
  }
  return best;
}

function getW50BestRank(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/50\s*best/i.test(txt)) {
      const m = String(a.label || "").match(/(?:No\.?|#)\s*(\d{1,3})/i);
      const val = m ? Number(m[1]) : 999;
      if (best == null || val < best) best = val;
    }
  }
  return best;
}

function getForbesRank(h) {
  let best = null;
  for (const a of h.officialAwards || []) {
    const txt = `${a.awardBody || ""} ${a.label || ""}`;
    if (/forbes/i.test(txt)) {
      let val = 1;
      if (/five[- ]star/i.test(txt)) val = 5;
      else if (/four[- ]star/i.test(txt)) val = 4;
      else if (/recommended/i.test(txt)) val = 3;
      if (best == null || val > best) best = val;
    }
  }
  return best;
}

const state = {
  hotels: [],
  brands: [],
  filterMode: "default", // "default" (3+) | "points" | "preferred" | "all2"
  search: "",
  sortKey: "avgOdds",
  sortDir: "desc",
  pillar: "rooms",
};

function computeBrandStats(hotels) {
  const byBrand = new Map();
  for (const h of hotels) {
    const brand = normalizeBrandName(h);
    if (!brand || brand === "Independent & Boutique") continue;
    if (!byBrand.has(brand)) byBrand.set(brand, []);
    byBrand.get(brand).push(h);
  }

  const rows = [];
  for (const [brand, list] of byBrand.entries()) {
    const samplePartner = getPartnerPrograms(list[0]);
    const oddsVals = [];
    const guestVals = [];
    const myVals = [];
    const gapVals = [];
    let michelinKeysTotal = 0;
    let michelinHotels = 0;
    let w50Count = 0;
    let forbes5Count = 0;

    for (const h of list) {
      const o = getOdds(h);
      if (o.greatStayOdds != null) oddsVals.push(Number(o.greatStayOdds));
      if (o.guest100 != null) guestVals.push(Number(o.guest100));
      if (o.firstHand && o.personalScore25 != null) myVals.push(Number(o.personalScore25));
      if (o.opinionGap && o.opinionGap.delta100 != null) gapVals.push(Math.abs(Number(o.opinionGap.delta100)));
      const mk = getMichelinKeyCount(h);
      if (mk != null) {
        michelinKeysTotal += mk;
        michelinHotels += 1;
      }
      if (getW50BestRank(h) != null) w50Count += 1;
      if (getForbesRank(h) === 5) forbes5Count += 1;
    }

    const avg = (arr) => (arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null);
    const avgOdds = avg(oddsVals);
    const consistencyPct = oddsVals.length
      ? Math.round((oddsVals.filter((v) => v >= 85).length / oddsVals.length) * 100)
      : null;

    rows.push({
      brand,
      count: list.length,
      scoredCount: oddsVals.length,
      avgOdds: avgOdds != null ? Number(avgOdds.toFixed(1)) : null,
      consistencyPct,
      avgMyStay: avg(myVals) != null ? Number(avg(myVals).toFixed(1)) : null,
      myStayCount: myVals.length,
      avgGuests10: avg(guestVals) != null ? Number((avg(guestVals) / 10).toFixed(2)) : null,
      avgGap: avg(gapVals) != null ? Number(avg(gapVals).toFixed(1)) : null,
      michelinKeysTotal,
      michelinHotels,
      w50Count,
      forbes5Count,
      preferredProgram: samplePartner.preferredProgram,
      pointsProgram: samplePartner.pointsProgram,
      hasPreferredPerks: samplePartner.hasPreferredPerks,
      isPointsEligible: samplePartner.isPointsEligible,
    });
  }
  return rows;
}

function getFilteredBrands() {
  const q = state.search.trim().toLowerCase();
  const minCount = state.filterMode === "all2" ? 2 : 3;
  let rows = state.brands.filter((b) => {
    if (b.count < minCount) return false;
    if (state.filterMode === "points" && !b.isPointsEligible) return false;
    if (state.filterMode === "preferred" && !b.hasPreferredPerks) return false;
    if (q) {
      const hay = `${b.brand} ${b.preferredProgram || ""} ${b.pointsProgram || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  const cmpNullable = (a, b, dir) => {
    const an = a == null || Number.isNaN(a);
    const bn = b == null || Number.isNaN(b);
    if (an && bn) return 0;
    if (an) return 1;
    if (bn) return -1;
    return dir === "asc" ? a - b : b - a;
  };

  rows.sort((a, b) => {
    const k = state.sortKey;
    const d = state.sortDir;
    let diff = 0;
    if (k === "brand") diff = d === "asc" ? a.brand.localeCompare(b.brand) : b.brand.localeCompare(a.brand);
    else if (k === "count") diff = cmpNullable(a.count, b.count, d);
    else if (k === "avgOdds") diff = cmpNullable(a.avgOdds, b.avgOdds, d);
    else if (k === "consistencyPct") diff = cmpNullable(a.consistencyPct, b.consistencyPct, d);
    else if (k === "avgMyStay") diff = cmpNullable(a.avgMyStay, b.avgMyStay, d);
    else if (k === "avgGuests10") diff = cmpNullable(a.avgGuests10, b.avgGuests10, d);
    else if (k === "michelinKeysTotal") diff = cmpNullable(a.michelinKeysTotal || null, b.michelinKeysTotal || null, d);
    else if (k === "w50Count") diff = cmpNullable(a.w50Count || null, b.w50Count || null, d);
    else if (k === "forbes5Count") diff = cmpNullable(a.forbes5Count || null, b.forbes5Count || null, d);
    if (diff !== 0) return diff;
    return (b.avgOdds ?? -1) - (a.avgOdds ?? -1) || b.count - a.count || a.brand.localeCompare(b.brand);
  });
  return rows;
}

function renderBrandsTable() {
  const wrap = qs("#brandsTableWrap");
  if (!wrap) return;
  const rows = getFilteredBrands();

  if (!rows.length) {
    wrap.innerHTML = `<div class="empty-state">No brands matched your filter. Try clearing the search box.</div>`;
    return;
  }

  const cols = [
    { key: "brand", label: "Luxury Brand", defaultDir: "asc" },
    { key: "count", label: "Hotels", defaultDir: "desc" },
    { key: "avgOdds", label: "Avg StayOdds", defaultDir: "desc" },
    { key: "consistencyPct", label: "Consistency (≥85%)", defaultDir: "desc" },
    { key: "avgMyStay", label: "Avg My Stay", defaultDir: "desc" },
    { key: "avgGuests10", label: "Avg Guests", defaultDir: "desc" },
    { key: "michelinKeysTotal", label: "MICHELIN Keys", defaultDir: "desc" },
    { key: "w50Count", label: "50 Best", defaultDir: "desc" },
    { key: "forbes5Count", label: "Forbes 5★", defaultDir: "desc" },
  ];

  const thHtml = cols
    .map((c) => {
      const isActive = state.sortKey === c.key;
      const arrow = isActive ? (state.sortDir === "asc" ? "▲" : "▼") : "⇅";
      const ariaSort = isActive ? (state.sortDir === "asc" ? "ascending" : "descending") : "none";
      return `<th class="is-sortable ${isActive ? "is-sorted" : ""}" data-sort-col="${c.key}" data-default-dir="${c.defaultDir}" aria-sort="${ariaSort}"><button type="button" class="sort-th-btn">${escapeHtml(c.label)} <span class="sort-arrow">${arrow}</span></button></th>`;
    })
    .join("");

  wrap.innerHTML = `
    <table class="comparison-table">
      <thead>
        <tr>
          ${thHtml}
          <th>Perks &amp; Points</th>
          <th>Explore</th>
        </tr>
      </thead>
      <tbody>
        ${rows
          .map((b, idx) => {
            const perkBadges = [
              b.preferredProgram ? `<span class="table-rank-pill is-forbes">${escapeHtml(b.preferredProgram)}</span>` : "",
              b.pointsProgram ? `<span class="table-rank-pill is-key">${escapeHtml(b.pointsProgram)}</span>` : "",
            ]
              .filter(Boolean)
              .join(" ");
            return `
              <tr>
                <td>
                  <strong>#${idx + 1} ${escapeHtml(b.brand)}</strong>
                  <div class="table-sub">${b.scoredCount} scored of ${b.count} tracked</div>
                </td>
                <td><strong>${b.count}</strong></td>
                <td><strong>${b.avgOdds != null ? `${b.avgOdds}%` : "—"}</strong></td>
                <td>
                  <strong>${b.consistencyPct != null ? `${b.consistencyPct}%` : "—"}</strong>
                  <div class="table-sub">${b.consistencyPct != null ? "scored ≥85%" : "no scores yet"}</div>
                </td>
                <td>${b.avgMyStay != null ? `<strong>${b.avgMyStay} / 25</strong><div class="table-sub">${b.myStayCount} stay${b.myStayCount === 1 ? "" : "s"}</div>` : "—"}</td>
                <td>${b.avgGuests10 != null ? `<strong>${b.avgGuests10.toFixed(1)} / 10</strong>` : "—"}</td>
                <td>${b.michelinKeysTotal ? `<span class="table-rank-pill is-key">${b.michelinKeysTotal} Keys</span><div class="table-sub">${b.michelinHotels} hotel${b.michelinHotels === 1 ? "" : "s"}</div>` : "—"}</td>
                <td>${b.w50Count ? `<span class="table-rank-pill is-50">${b.w50Count}</span>` : "—"}</td>
                <td>${b.forbes5Count ? `<span class="table-rank-pill is-forbes">${b.forbes5Count}</span>` : "—"}</td>
                <td>${perkBadges || `<span class="table-sub">Independent perks</span>`}</td>
                <td style="white-space:nowrap;">
                  <a class="btn btn-primary" style="padding:6px 12px;font-size:12px;" href="../compare/?brand=${encodeURIComponent(b.brand)}">View ${b.count} Hotels &rarr;</a>
                </td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
  `;

  wrap.querySelectorAll("th[data-sort-col]").forEach((th) => {
    th.addEventListener("click", () => {
      const col = th.dataset.sortCol;
      const def = th.dataset.defaultDir || "desc";
      if (state.sortKey === col) state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      else {
        state.sortKey = col;
        state.sortDir = def;
      }
      renderBrandsTable();
    });
  });
}

function renderPillarLeaderboard() {
  const wrap = qs("#pillarLeaderboardWrap");
  if (!wrap) return;
  const key = state.pillar;
  const labelMap = {
    rooms: "Room Quality (Hard Product)",
    service: "Service",
    food: "Food & Breakfast",
    grounds: "Vibe & Layout",
    value: "Value",
  };
  const scored = state.hotels
    .filter((h) => isFirstHandVerified(h) && h.scores && h.scores[key] != null)
    .sort((a, b) => {
      const diff = Number(b.scores[key]) - Number(a.scores[key]);
      if (diff !== 0) return diff;
      return Number(b.overall || 0) - Number(a.overall || 0) || a.name.localeCompare(b.name);
    });

  wrap.innerHTML = `
    <table class="comparison-table">
      <thead>
        <tr>
          <th>Rank</th>
          <th>Hotel</th>
          <th>Destination</th>
          <th>${escapeHtml(labelMap[key] || key)}</th>
          <th>My Stay Total</th>
          <th>StayOdds %</th>
          <th>First-Hand Room / Takeaway</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        ${scored
          .map((h, i) => {
            const o = getOdds(h);
            const tip = getVerifiedRoomTip(h) || h.whereWeDiffer || h.standout || "";
            return `
              <tr>
                <td><strong>#${i + 1}</strong></td>
                <td><strong><a href="../stayodds/${encodeURIComponent(h.id)}/">${escapeHtml(h.name)}</a></strong><div class="table-sub">${escapeHtml(normalizeBrandName(h))}</div></td>
                <td>${escapeHtml(h.location)}, ${escapeHtml(h.country)}</td>
                <td><span class="table-rank-pill is-key" style="font-size:13px;">${escapeHtml(formatPersonalScore(h.scores[key]))} / 5</span></td>
                <td><strong>${escapeHtml(o.personalScoreLabel || "—")}</strong></td>
                <td><strong>${o.greatStayOdds != null ? `${o.greatStayOdds}%` : "Live"}</strong></td>
                <td style="max-width:340px;font-size:12.5px;color:#334155;">${escapeHtml(tip.slice(0, 150))}${tip.length > 150 ? "…" : ""}</td>
                <td style="white-space:nowrap;">
                  <a class="btn btn-primary" style="padding:6px 10px;font-size:12px;" href="../stayodds/${encodeURIComponent(h.id)}/">Open</a>
                  <a class="btn btn-outline" style="padding:6px 10px;font-size:12px;" href="../compare/?a=${encodeURIComponent(h.id)}">VS</a>
                </td>
              </tr>
            `;
          })
          .join("")}
      </tbody>
    </table>
  `;
}

function exportBrandsCsv() {
  const rows = getFilteredBrands();
  const headers = [
    "Rank",
    "Brand",
    "Hotels Tracked",
    "Avg StayOdds %",
    "Consistency (% >= 85%)",
    "Avg My Stay (/25)",
    "Avg Guests (/10)",
    "MICHELIN Keys Total",
    "World's 50 Best Hotels",
    "Forbes 5-Star Hotels",
    "Preferred Partner Program",
    "Points Program",
  ];
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [
    headers.map(esc).join(","),
    ...rows.map((b, i) =>
      [
        i + 1,
        b.brand,
        b.count,
        b.avgOdds != null ? `${b.avgOdds}%` : "",
        b.consistencyPct != null ? `${b.consistencyPct}%` : "",
        b.avgMyStay != null ? `${b.avgMyStay}/25` : "",
        b.avgGuests10 != null ? `${b.avgGuests10}/10` : "",
        b.michelinKeysTotal || 0,
        b.w50Count || 0,
        b.forbes5Count || 0,
        b.preferredProgram || "",
        b.pointsProgram || "",
      ]
        .map(esc)
        .join(",")
    ),
  ];
  const blob = new Blob(["\uFEFF" + lines.join("\r\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "stayodds-luxury-brand-leaderboard.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
}

async function boot() {
  const y = qs("#yearNow");
  if (y) y.textContent = String(new Date().getFullYear());
  const menuBtn = qs("#mobileMenuBtn");
  const mobileNav = qs("#mobileNav");
  if (menuBtn && mobileNav) {
    menuBtn.addEventListener("click", () => {
      const open = mobileNav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
  }

  const filterButtons = [
    ["#brandFilterAllBtn", "default"],
    ["#brandFilterPointsBtn", "points"],
    ["#brandFilterPreferredBtn", "preferred"],
    ["#brandFilterEveryBtn", "all2"],
  ];
  filterButtons.forEach(([sel, mode]) => {
    qs(sel)?.addEventListener("click", () => {
      state.filterMode = mode;
      filterButtons.forEach(([s2, m2]) => qs(s2)?.classList.toggle("active", m2 === mode));
      renderBrandsTable();
    });
  });

  qs("#brandSearchInput")?.addEventListener("input", (e) => {
    state.search = e.target.value || "";
    renderBrandsTable();
  });

  qs("#exportBrandsCsvBtn")?.addEventListener("click", exportBrandsCsv);

  qs("#pillarTabsBar")?.querySelectorAll("[data-pillar]").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.pillar = btn.dataset.pillar || "rooms";
      qs("#pillarTabsBar").querySelectorAll("[data-pillar]").forEach((b) => b.classList.toggle("active", b === btn));
      renderPillarLeaderboard();
    });
  });

  try {
    const IDX_CACHE_KEY = "stayodds_index_cache_v20261124";
    const IDX_TTL_MS = 6 * 60 * 60 * 1000;
    let payload = null;
    try {
      const raw = localStorage.getItem(IDX_CACHE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.ts && Date.now() - parsed.ts < IDX_TTL_MS && parsed.data && Array.isArray(parsed.data.hotels)) {
          payload = parsed.data;
        }
      }
    } catch (_) {}
    if (!payload) {
      const res = await fetch(`../data/stayodds-index.json?v=20261124a`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      payload = await res.json();
      try {
        localStorage.setItem(IDX_CACHE_KEY, JSON.stringify({ ts: Date.now(), data: payload }));
      } catch (_) {}
    }

    state.hotels = payload.hotels || [];
    state.brands = computeBrandStats(state.hotels);
    const statEl = qs("#brandsSummaryStat");
    if (statEl) {
      const majorCount = state.brands.filter((b) => b.count >= 3).length;
      statEl.textContent = `${majorCount} Major Luxury Brands • ${state.hotels.length} Verified Hotels`;
    }
    renderBrandsTable();
    renderPillarLeaderboard();
  } catch (err) {
    const wrap = qs("#brandsTableWrap");
    if (wrap) wrap.innerHTML = `<div class="empty-state">Unable to load Brand Consistency Leaderboard right now.</div>`;
    console.error("Failed to load brands:", err);
  }
}

boot();
