const state = {
  hotels: [],
  region: "All",
  brand: "All",
  coverage: "All",
  sortBy: "overall",
  search: "",
  viewMode: "cards",
  map: null,
  markersLayer: null,
  markerById: new Map(),
};

const qs = (sel) => document.querySelector(sel);

function escapeHtml(str = "") {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getReviewHref(hotel) {
  if (hotel.coverageType === "Short Tour" && hotel.videoId) {
    return `https://www.youtube.com/shorts/${encodeURIComponent(hotel.videoId)}`;
  }
  if (hotel.inLiveFeed && hotel.videoId) {
    return `../?video=${encodeURIComponent(hotel.videoId)}`;
  }
  if (hotel.videoId) {
    return `https://www.youtube.com/watch?v=${encodeURIComponent(hotel.videoId)}`;
  }
  return "https://www.uncharteditinerary.com/";
}

function isExternalReview(hotel) {
  if (hotel.coverageType === "Short Tour") return true;
  return !(hotel.inLiveFeed && hotel.videoId);
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];
    if (inQuotes) {
      if (ch === '"' && next === '"') {
        field += '"';
        i++;
      } else if (ch === '"') {
        inQuotes = false;
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field.trim());
      field = "";
    } else if (ch === "\n") {
      row.push(field.trim());
      if (row.some((c) => c !== "")) rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field.trim());
    if (row.some((c) => c !== "")) rows.push(row);
  }
  if (rows.length < 2) return [];
  const headers = rows[0].map((h) => h.toLowerCase().trim());
  return rows.slice(1).map((vals) => {
    const o = {};
    headers.forEach((h, i) => {
      o[h] = (vals[i] || "").trim();
    });
    return o;
  });
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

function initMap() {
  const mapEl = qs("#hotelMap");
  if (!mapEl || typeof L === "undefined") return;

  const map = L.map("hotelMap", {
    scrollWheelZoom: false,
    worldCopyJump: true,
  }).setView([4.0, 96.0], 3);

  const cartoLayer = L.tileLayer(
    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png?key=cb1_5db3_1_c3957b21042bb79553569521",
    {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
      maxZoom: 19,
    }
  );

  let switchedToFallback = false;
  cartoLayer.on("tileerror", () => {
    if (switchedToFallback) return;
    switchedToFallback = true;
    map.removeLayer(cartoLayer);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);
  });

  cartoLayer.addTo(map);

  state.map = map;
  state.markersLayer = L.layerGroup().addTo(map);
}

function formatMyScore(val) {
  if (val == null || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  return Number.isInteger(num) ? String(num) : num.toFixed(1);
}

function isRatedHotel(h) {
  return h.overall != null && h.scores != null;
}

function getFilteredHotels() {
  const q = state.search.trim().toLowerCase();
  const list = state.hotels.filter((h) => {
    if (state.region !== "All" && h.region !== state.region) return false;
    if (state.brand !== "All" && h.brand !== state.brand) return false;
    if (state.coverage !== "All" && (h.coverageType || "Full Review") !== state.coverage) return false;
    if (!q) return true;
    const hay = [h.name, h.location, h.country, h.region, h.brand, h.verdict, h.standout]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  list.sort((a, b) => {
    if (state.sortBy === "newest") {
      return (b.reviewedDate || "").localeCompare(a.reviewedDate || "");
    }
    const aRated = isRatedHotel(a) ? 1 : 0;
    const bRated = isRatedHotel(b) ? 1 : 0;
    if (bRated !== aRated) return bRated - aRated;
    if (state.sortBy === "overall") {
      return (
        (b.overall || 0) - (a.overall || 0) ||
        (b.consensus?.greatStayChance || 0) - (a.consensus?.greatStayChance || 0) ||
        (b.scores?.value || 0) - (a.scores?.value || 0)
      );
    }
    return (
      (b.scores?.[state.sortBy] || 0) - (a.scores?.[state.sortBy] || 0) ||
      (b.overall || 0) - (a.overall || 0)
    );
  });
  return list;
}

function renderMapMarkers(hotels, fitBounds = true) {
  if (!state.map || !state.markersLayer) return;
  state.markersLayer.clearLayers();
  state.markerById.clear();

  const bounds = [];
  for (const h of hotels) {
    if (typeof h.lat !== "number" || typeof h.lng !== "number") continue;
    bounds.push([h.lat, h.lng]);

    const rated = isRatedHotel(h);
    const pinText = rated ? `${formatMyScore(h.overall)}/5` : "Short";
    const icon = L.divIcon({
      className: "hotel-score-pin-wrap",
      html: `<div class="hotel-score-pin ${rated ? "" : "is-short"}"><span>${pinText}</span></div>`,
      iconSize: [46, 34],
      iconAnchor: [23, 34],
      popupAnchor: [0, -32],
    });

    const popupScore = rated
      ? `${formatMyScore(h.overall)} / 5`
      : "Short Preview · Unrated";
    const popupHtml = `
      <div class="map-popup-card">
        <img class="map-popup-img" src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" />
        <div class="map-popup-body">
          <div class="map-popup-top">
            <span class="map-popup-loc">${escapeHtml(h.location)}</span>
            <span class="map-popup-score">${escapeHtml(popupScore)}</span>
          </div>
          <h4>${escapeHtml(h.name)}</h4>
          <p>${escapeHtml(h.verdict)}</p>
          <div class="map-popup-actions">
            <a class="map-btn-primary" href="../compare/hotel/?id=${encodeURIComponent(h.id)}">Score Breakdown</a>
            <a class="map-btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
          </div>
        </div>
      </div>
    `;

    const marker = L.marker([h.lat, h.lng], { icon }).bindPopup(popupHtml, {
      maxWidth: 300,
      className: "uncharted-popup",
    });
    marker.addTo(state.markersLayer);
    state.markerById.set(h.id, marker);
  }

  if (fitBounds && bounds.length) {
    if (bounds.length === 1) {
      state.map.setView(bounds[0], 11, { animate: true });
    } else {
      state.map.fitBounds(bounds, { padding: [45, 45], maxZoom: 11, animate: true });
    }
  }
}

function renderRegionPills() {
  const container = qs("#regionPills");
  if (!container) return;

  const counts = new Map();
  for (const h of state.hotels) {
    counts.set(h.region, (counts.get(h.region) || 0) + 1);
  }
  const order = ["All", "Bali & Indonesia", "Maldives", "Thailand", "Europe", "Bora Bora"].filter(
    (r) => r === "All" || counts.has(r)
  );
  for (const r of counts.keys()) {
    if (!order.includes(r)) order.push(r);
  }

  container.innerHTML = order
    .map((r) => {
      const count = r === "All" ? state.hotels.length : counts.get(r) || 0;
      const active = state.region === r;
      return `<button class="pill ${active ? "active" : ""}" data-region="${escapeHtml(
        r
      )}" role="tab" aria-selected="${active}">${escapeHtml(r)} (${count})</button>`;
    })
    .join("");

  container.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.region = btn.dataset.region || "All";
      renderRegionPills();
      renderAll(true);
    });
  });
}

function populateBrands() {
  const sel = qs("#brandFilter");
  if (!sel) return;
  const brands = Array.from(new Set(state.hotels.map((h) => h.brand).filter(Boolean))).sort();
  sel.innerHTML =
    `<option value="All">All Hotel Brands</option>` +
    brands.map((b) => `<option value="${escapeHtml(b)}">${escapeHtml(b)}</option>`).join("");
}

function renderScoreBar(label, value) {
  const num = Number(value || 0);
  const pct = Math.max(0, Math.min(100, (num / 5) * 100));
  return `
    <div class="score-bar-row">
      <span class="score-bar-label">${escapeHtml(label)}</span>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%"></div></div>
      <span class="score-bar-val">${escapeHtml(formatMyScore(num))}</span>
    </div>
  `;
}

function renderScorecards(hotels) {
  const grid = qs("#scorecardGrid");
  const tableWrap = qs("#scorecardTableWrap");
  if (!grid || !tableWrap) return;

  if (!hotels.length) {
    grid.style.display = "";
    tableWrap.style.display = "none";
    grid.innerHTML = `<div class="empty-state">No hotels matched your filter. Try selecting "All" regions or clearing your search.</div>`;
    return;
  }

  if (state.viewMode === "table") {
    grid.style.display = "none";
    tableWrap.style.display = "";
    tableWrap.innerHTML = `
      <table class="comparison-table">
        <thead>
          <tr>
            <th>Resort / Hotel</th>
            <th>Region</th>
            <th>Overall</th>
            <th>Rooms</th>
            <th>Grounds</th>
            <th>Food</th>
            <th>Service</th>
            <th>Value</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          ${hotels
            .map((h) => {
              const rated = isRatedHotel(h);
              const s = h.scores || {};
              return `
                <tr>
                  <td>
                    <a href="../compare/hotel/?id=${encodeURIComponent(h.id)}" style="color:var(--ink-primary);font-weight:600;">${escapeHtml(h.name)}</a><br />
                    <span style="font-size:12px;color:var(--ink-muted);">${escapeHtml(h.location)} &bull; ${escapeHtml(h.brand || "")}</span>
                  </td>
                  <td>${escapeHtml(h.region)}</td>
                  <td>${
                    rated
                      ? `<strong style="color:var(--accent);">${escapeHtml(formatMyScore(h.overall))} / 5</strong>`
                      : `<span class="tag">Short · Unrated</span>`
                  }</td>
                  <td>${rated ? escapeHtml(formatMyScore(s.rooms)) : "—"}</td>
                  <td>${rated ? escapeHtml(formatMyScore(s.grounds)) : "—"}</td>
                  <td>${rated ? escapeHtml(formatMyScore(s.food)) : "—"}</td>
                  <td>${rated ? escapeHtml(formatMyScore(s.service)) : "—"}</td>
                  <td>${rated ? escapeHtml(formatMyScore(s.value)) : "—"}</td>
                  <td style="white-space:nowrap;">
                    <a href="../compare/hotel/?id=${encodeURIComponent(h.id)}" style="color:var(--accent);font-weight:600;margin-right:10px;">Breakdown</a>
                    <a href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer" style="font-weight:500;">Rates &nearr;</a>
                  </td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    `;
    return;
  }

  tableWrap.style.display = "none";
  grid.style.display = "";
  grid.innerHTML = hotels
    .map((h) => {
      const rated = isRatedHotel(h);
      const s = h.scores || {};
      const reviewHref = getReviewHref(h);
      const ext = isExternalReview(h) ? ' target="_blank" rel="noopener noreferrer"' : "";
      return `
        <article class="scorecard-card">
          <div class="scorecard-top">
            <a href="../compare/hotel/?id=${encodeURIComponent(h.id)}">
              <img class="scorecard-thumb" src="${escapeHtml(h.thumbnail)}" alt="${escapeHtml(h.name)}" loading="lazy" />
            </a>
            <div class="scorecard-badge-overall ${rated ? "" : "is-short"}">
              ${
                rated
                  ? `<strong>${escapeHtml(formatMyScore(h.overall))}</strong><span>/ 5</span>`
                  : `<strong>Short</strong><span>Unrated</span>`
              }
            </div>
            <button class="pin-focus-btn" data-focus-id="${escapeHtml(h.id)}" title="Show on map">
              Show on Map
            </button>
          </div>

          <div class="scorecard-body">
            <div class="meta-line">
              <span class="tag tag-accent">${escapeHtml(h.brand || "Luxury Stay")}</span>
              ${h.coverageType === "Short Tour" ? `<span class="tag">Short Tour · Unrated</span>` : ""}
              ${Array.isArray(h.shorts) && h.shorts.length ? `<span class="tag">${h.shorts.length} Short${h.shorts.length === 1 ? "" : "s"}</span>` : ""}
              <span class="tag">${escapeHtml(h.priceRange || "")}</span>
            </div>

            <h3 class="scorecard-title">
              <a class="consensus-title-link" href="../compare/hotel/?id=${encodeURIComponent(h.id)}">${escapeHtml(h.name)}</a>
            </h3>
            <div class="scorecard-location">${escapeHtml(h.location)}, ${escapeHtml(h.country)}</div>

            <p class="scorecard-verdict">${escapeHtml(h.verdict)}</p>

            ${
              rated
                ? `
            <div class="score-bars">
              ${renderScoreBar("Rooms", s.rooms)}
              ${renderScoreBar("Grounds", s.grounds)}
              ${renderScoreBar("Food", s.food)}
              ${renderScoreBar("Service", s.service)}
              ${renderScoreBar("Value", s.value)}
            </div>
                `
                : `
            <div class="scorecard-unrated-box">
              <strong>Featured in a YouTube Short (Not Ranked Yet)</strong>
              <p style="margin:0;">We haven’t published a full scored video review yet. Open <em>Score Breakdown</em> to see verified Booking.com &amp; Google guest consensus (${h.consensus?.greatStayChance || 90}% external odds).</p>
            </div>
                `
            }

            <div class="scorecard-notes">
              <div><strong>Standout:</strong> ${escapeHtml(h.standout)}</div>
              <div><strong>Watch out:</strong> ${escapeHtml(h.watchOut)}</div>
            </div>

            <div class="scorecard-actions">
              <a class="btn btn-primary" href="../compare/hotel/?id=${encodeURIComponent(h.id)}">Score Breakdown</a>
              <a class="btn btn-outline" href="${escapeHtml(reviewHref)}"${ext}>${h.coverageType === "Short Tour" ? "Watch Short" : "Watch Review"}</a>
              <a class="btn btn-outline" href="${escapeHtml(h.bookingUrl)}" target="_blank" rel="sponsored noopener noreferrer">Rates &nearr;</a>
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-focus-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const marker = state.markerById.get(btn.dataset.focusId);
      if (marker && state.map) {
        qs("#hotelMap")?.scrollIntoView({ behavior: "smooth", block: "center" });
        state.map.setView(marker.getLatLng(), 11, { animate: true });
        setTimeout(() => marker.openPopup(), 350);
      }
    });
  });
}

function renderHotelShorts(hotels) {
  const rail = qs("#hotelShortsRail");
  const sec = qs("#hotelShortsSection");
  if (!rail || !sec) return;
  const items = [];
  const seen = new Set();
  for (const h of hotels) {
    for (const sh of h.shorts || []) {
      if (!seen.has(sh.id)) {
        seen.add(sh.id);
        items.push({ ...sh, hotelName: h.name });
      }
    }
  }
  if (!items.length) {
    sec.style.display = "none";
    return;
  }
  sec.style.display = "";
  rail.innerHTML = items
    .slice(0, 24)
    .map(
      (sh) => `
      <a class="short-card" href="https://www.youtube.com/shorts/${encodeURIComponent(sh.id)}" target="_blank" rel="noopener noreferrer">
        <div class="short-thumb">
          <img src="https://i.ytimg.com/vi/${encodeURIComponent(sh.id)}/hqdefault.jpg" alt="${escapeHtml(sh.title)}" loading="lazy" />
          <span class="short-badge">Short</span>
        </div>
        <div class="short-info">
          <h3 class="short-title">${escapeHtml(sh.title)}</h3>
          <div class="short-date">${escapeHtml(sh.hotelName.split(",")[0])} &bull; ${escapeHtml(sh.viewsText || "Short")}</div>
        </div>
      </a>
    `
    )
    .join("");
}

function renderAll(fitBounds = false) {
  const filtered = getFilteredHotels();
  const badge = qs("#hotelCountBadge");
  if (badge) badge.textContent = `${filtered.length} Reviewed Stay${filtered.length === 1 ? "" : "s"}`;
  renderMapMarkers(filtered, fitBounds);
  renderScorecards(filtered);
  renderHotelShorts(filtered);
}

async function applyLiveBookingSheet(csvUrl) {
  if (!csvUrl) return;
  try {
    const res = await fetch(csvUrl, { cache: "no-store" });
    if (!res.ok) return;
    const rows = parseCsv(await res.text());
    const byName = new Map();
    for (const r of rows) {
      const name = (r["hotel name"] || r.name || "").toLowerCase();
      const url = (r["booking affiliate url"] || r["booking.com / travelpayouts url"] || r["agoda / trip.com url"] || r.url || "").trim();
      if (name && url) byName.set(name, url);
    }
    let updated = 0;
    for (const h of state.hotels) {
      const custom = byName.get(h.name.toLowerCase());
      if (custom) {
        h.bookingUrl = custom;
        updated++;
      }
    }
    if (updated) renderAll(false);
  } catch (err) {
    console.warn("Hotel booking sheet refresh skipped:", err);
  }
}

async function boot() {
  initCommonUi();
  initMap();

  qs("#brandFilter")?.addEventListener("change", (e) => {
    state.brand = e.target.value || "All";
    renderAll(true);
  });
  qs("#coverageFilter")?.addEventListener("change", (e) => {
    state.coverage = e.target.value || "All";
    renderAll(true);
  });
  qs("#sortControl")?.addEventListener("change", (e) => {
    state.sortBy = e.target.value || "overall";
    renderAll(false);
  });
  qs("#hotelSearch")?.addEventListener("input", (e) => {
    state.search = e.target.value || "";
    renderAll(false);
  });
  qs("#viewCardsBtn")?.addEventListener("click", () => {
    state.viewMode = "cards";
    qs("#viewCardsBtn")?.classList.add("active");
    qs("#viewTableBtn")?.classList.remove("active");
    renderScorecards(getFilteredHotels());
  });
  qs("#viewTableBtn")?.addEventListener("click", () => {
    state.viewMode = "table";
    qs("#viewTableBtn")?.classList.add("active");
    qs("#viewCardsBtn")?.classList.remove("active");
    renderScorecards(getFilteredHotels());
  });

  try {
    const [hRes, cfgRes] = await Promise.all([
      fetch(`../data/hotels.json?v=${Date.now()}`),
      fetch(`../config.json?v=${Date.now()}`).catch(() => null),
    ]);
    if (!hRes.ok) throw new Error(`HTTP ${hRes.status}`);
    const data = await hRes.json();
    const cfg = cfgRes && cfgRes.ok ? await cfgRes.json() : null;

    state.hotels = data.hotels || [];
    renderRegionPills();
    populateBrands();
    renderAll(true);

    const sheetUrl = (cfg?.affiliates?.hotelBookingSheetCsvUrl || "").trim();
    if (sheetUrl) {
      applyLiveBookingSheet(sheetUrl);
    }
  } catch (err) {
    const grid = qs("#scorecardGrid");
    if (grid) grid.innerHTML = `<div class="empty-state">Unable to load hotel scorecards right now.</div>`;
    console.error("Failed to load hotels.json:", err);
  }
}

boot();
