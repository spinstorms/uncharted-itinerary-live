const state = {
  curated: [],
  fromVideos: [],
  activeCategory: "All",
  searchQuery: "",
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

function showToast(message) {
  const toast = qs("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add("show");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => toast.classList.remove("show"), 2400);
}

function formatSyncTime(iso) {
  if (!iso) return "Recently updated";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Recently updated";
  return `Updated ${d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })}`;
}

function inferSection(item) {
  const explicit = (item.section || "").toLowerCase();
  if (explicit.includes("shop") || explicit.includes("gear")) return "Shopping & Gear";
  if (explicit.includes("promo") || explicit.includes("offer") || explicit.includes("code")) {
    return "Promotions & Codes";
  }
  const cat = (item.category || "").toLowerCase();
  const url = (item.url || "").toLowerCase();
  if (
    url.includes("amazon") ||
    url.includes("amzn.to") ||
    url.includes("geni.us") ||
    cat.includes("gear") ||
    cat.includes("luggage") ||
    cat.includes("shopping") ||
    cat.includes("resort & beach")
  ) {
    return "Shopping & Gear";
  }
  return "Promotions & Codes";
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
      if (row.some((cell) => cell !== "")) rows.push(row);
      row = [];
      field = "";
    } else if (ch !== "\r") {
      field += ch;
    }
  }
  if (field.length || row.length) {
    row.push(field.trim());
    if (row.some((cell) => cell !== "")) rows.push(row);
  }
  if (rows.length < 2) return [];

  const headers = rows[0].map((h) => h.toLowerCase().trim());
  return rows.slice(1).map((vals, idx) => {
    const obj = {};
    headers.forEach((h, i) => {
      obj[h] = (vals[i] || "").trim();
    });
    return { obj, idx: idx + 1 };
  });
}

async function fetchLiveGoogleSheet(csvUrl) {
  const res = await fetch(csvUrl, { cache: "no-store" });
  if (!res.ok) throw new Error(`Sheet HTTP ${res.status}`);
  const csvText = await res.text();
  const parsed = parseCsv(csvText);

  const items = [];
  for (const { obj, idx } of parsed) {
    const active = (obj.active || "true").toLowerCase();
    if (["false", "0", "no", "off"].includes(active)) continue;
    const url = (obj.url || "").trim();
    const title = (obj.title || "").trim();
    if (!url || !title) continue;

    const item = {
      id: `live-sheet-${idx}`,
      source: "curated",
      section: obj.section || "",
      featured: ["true", "1", "yes"].includes((obj.featured || "").toLowerCase()),
      category: obj.category || "Travel & Perks",
      title,
      badge: obj["offer badge"] || obj.badge || "",
      description: obj.description || "",
      promoCode: obj["promo code"] || obj.code || "",
      url,
      buttonLabel: obj["button label"] || "Explore Deal",
      sortOrder: Number(obj["sort order"] || obj.sort || idx) || idx,
    };
    item.section = inferSection(item);
    items.push(item);
  }
  items.sort((a, b) => Number(b.featured) - Number(a.featured) || a.sortOrder - b.sortOrder);
  return items;
}

function publicTrendingCopy(title, category, url) {
  const low = `${title} ${category} ${url}`.toLowerCase();
  if (low.includes("saily")) return ["Travel eSIM", "Fast, reliable international travel eSIM by Nord Security — install in minutes and skip roaming fees.", "Get Saily eSIM"];
  if (low.includes("airalo")) return ["Travel eSIM", "Affordable global and regional travel eSIM data plans across 200+ destinations.", "Explore Airalo"];
  if (low.includes("klook")) return ["Tours & Transfers", "Book airport transfers, island day trips, beach clubs, and local tours across Asia and worldwide.", "Browse Klook"];
  if (low.includes("viator") || low.includes("getyourguide")) return ["Tours & Excursions", "Trusted private drivers, boat excursions, and guided day trips with flexible cancellation.", "Browse Experiences"];
  if (low.includes("wise")) return ["Travel Money", "Multi-currency travel card with the real exchange rate and low fees in IDR, THB, EUR, and USD.", "Get Wise Card"];
  if (low.includes("priority pass")) return ["Airport Lounges", "Access 1,500+ airport lounges worldwide on long-haul economy flights and layovers.", "Explore Priority Pass"];
  if (low.includes("safetywing") || low.includes("heymondo") || low.includes("insurance")) return ["Travel Cover", "Flexible medical and trip protection built for frequent international travelers.", "Check Travel Cover"];
  if (low.includes("nordvpn") || low.includes("surfshark")) return ["Travel Security", "Keep public hotel and airport Wi-Fi private and stream your home apps abroad.", "Get VPN Deal"];
  if (/booking\.com|agoda|trip\.com|expedia|hotels\.com/.test(low)) return ["Hotel Partner", "Compare live luxury resort rates, member deals, and flexible cancellation options.", "Check Live Rates"];
  if (low.includes("mic mini") || low.includes("microphone")) return ["Travel Audio", "Ultra-compact wireless microphone we tested head-to-head on our Bali camera shootout.", "Shop on Amazon"];
  if (low.includes("pocket") || low.includes("dji")) return ["Filming Gear", "Compact 4K pocket gimbal camera gear featured in our real-world travel camera tests.", "Shop on Amazon"];
  if (/amazon|amzn\.to|link\.amazon/.test(low)) return ["Travel Pick", `One of our go-to ${category.toLowerCase()} essentials we pack for luxury resort trips and long-haul flights.`, "Shop on Amazon"];
  return ["Travel Pick", `Recommended ${category.toLowerCase()} partner we use on trips around the world.`, "Explore Offer"];
}

async function fetchTrendingGoogleSheet(csvUrl) {
  const res = await fetch(csvUrl, { cache: "no-store" });
  if (!res.ok) throw new Error(`Trending Sheet HTTP ${res.status}`);
  const csvText = await res.text();
  const parsed = parseCsv(csvText);

  const items = [];
  for (const { obj, idx } of parsed) {
    const rawLink = obj["your affiliate link (paste here)"] || obj["your generated affiliate link"] || obj["affiliate link"] || "";
    const urlMatch = rawLink.match(/https?:\/\/[^\s<>"')\]]+/);
    if (!urlMatch) continue;
    const url = urlMatch[0].replace(/[.,;:!?)>\]]+$/, "");
    const title = obj["travel product / affiliate program"] || obj["product / brand"] || obj.title || "";
    if (!title) continue;
    const codeMatch = rawLink.match(/code\s*[:=]?\s*([A-Z0-9]{4,16})/i);
    const promoCode = codeMatch ? codeMatch[1].toUpperCase() : "";
    const category = obj.category || "Travel & Gear";
    const [badge, description, buttonLabel] = publicTrendingCopy(title, category, url);
    const isPromo = /esim|points|money|tours|hotel|lounge|insurance|security|tpx\.lu|wise\.com|holafly/i.test(`${category} ${url}`);
    const item = {
      id: `live-trending-${idx}`,
      source: "curated",
      section: isPromo ? "Promotions & Codes" : "",
      featured: /saily|airalo|klook|wise|pocket 4|mic mini/i.test(title),
      category,
      title,
      badge,
      description,
      promoCode,
      url,
      buttonLabel,
      sortOrder: 30 + idx,
    };
    item.section = inferSection(item);
    items.push(item);
  }
  return items;
}

function getAllDeals() {
  return [...state.curated, ...state.fromVideos].map((item) => ({
    ...item,
    section: inferSection(item),
  }));
}

function renderDealCard(deal) {
  const mentions = deal.mentionedIn || [];
  const isShop = deal.section === "Shopping & Gear";
  const mentionLabel =
    mentions.length > 1
      ? `Featured in ${mentions.length}+ videos`
      : mentions.length === 1
      ? `From: ${mentions[0].title.slice(0, 32)}${mentions[0].title.length > 32 ? "…" : ""}`
      : isShop
      ? "Travel & filming kit"
      : "Active offer";

  return `
    <article class="deal-card ${deal.featured ? "is-featured" : ""}">
      <div class="deal-top">
        <span class="tag">${escapeHtml(deal.category || (isShop ? "Travel Gear" : "Promotion"))}</span>
        ${deal.badge ? `<span class="tag tag-accent">${escapeHtml(deal.badge)}</span>` : ""}
      </div>

      <h3 class="deal-title">${escapeHtml(deal.title)}</h3>
      ${deal.description ? `<p class="deal-desc">${escapeHtml(deal.description)}</p>` : ""}

      ${
        deal.promoCode
          ? `<div class="promo-code-row">
              <span>Code: <span class="promo-code-val">${escapeHtml(deal.promoCode)}</span></span>
              <button class="copy-code-btn" data-copy-code="${escapeHtml(deal.promoCode)}">Copy Code</button>
            </div>`
          : ""
      }

      <div class="deal-footer">
        <span class="deal-mentions">${escapeHtml(mentionLabel)}</span>
        <a class="btn ${isShop ? "btn-outline" : "btn-primary"}" href="${escapeHtml(
          deal.url
        )}" target="_blank" rel="sponsored noopener noreferrer">
          ${escapeHtml(deal.buttonLabel || (isShop ? "Shop Now" : "Claim Offer"))} &nearr;
        </a>
      </div>
    </article>
  `;
}

function wireCopyButtons(root) {
  root.querySelectorAll("[data-copy-code]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const code = btn.dataset.copyCode || "";
      try {
        await navigator.clipboard.writeText(code);
        showToast(`Copied code: ${code}`);
      } catch {
        showToast(`Promo code: ${code}`);
      }
    });
  });
}

function renderFilters() {
  const container = qs("#dealCategoryFilters");
  if (!container) return;

  const all = getAllDeals();
  const counts = new Map();
  for (const d of all) {
    const cat = d.category || "Travel & Perks";
    counts.set(cat, (counts.get(cat) || 0) + 1);
  }

  const ordered = ["All", ...Array.from(counts.keys())];
  container.innerHTML = ordered
    .map((cat) => {
      const count = cat === "All" ? all.length : counts.get(cat) || 0;
      const active = state.activeCategory === cat;
      return `<button class="pill ${active ? "active" : ""}" data-cat="${escapeHtml(
        cat
      )}" role="tab" aria-selected="${active}">${escapeHtml(cat)} (${count})</button>`;
    })
    .join("");

  container.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeCategory = btn.dataset.cat || "All";
      renderFilters();
      renderSections();
    });
  });
}

function renderSections() {
  const promosSection = qs("#promotionsSection");
  const promosGrid = qs("#promotionsGrid");
  const shopSection = qs("#shoppingSection");
  const shopGrid = qs("#shoppingGrid");
  if (!promosGrid || !shopGrid) return;

  const q = state.searchQuery.trim().toLowerCase();
  const filtered = getAllDeals().filter((d) => {
    const catOk = state.activeCategory === "All" || d.category === state.activeCategory;
    if (!catOk) return false;
    if (!q) return true;
    const hay = [d.title, d.section, d.category, d.badge, d.description, d.promoCode]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  const promos = filtered
    .filter((d) => d.section === "Promotions & Codes")
    .sort((a, b) => Number(b.featured) - Number(a.featured) || (a.sortOrder || 99) - (b.sortOrder || 99));

  const shopping = filtered
    .filter((d) => d.section === "Shopping & Gear")
    .sort((a, b) => Number(b.featured) - Number(a.featured) || (a.sortOrder || 99) - (b.sortOrder || 99));

  if (!filtered.length) {
    promosSection.style.display = "";
    shopSection.style.display = "none";
    promosGrid.innerHTML = `<div class="empty-state">No promotions or gear matched "${escapeHtml(
      state.searchQuery
    )}". Try clearing your search.</div>`;
    return;
  }

  if (promos.length) {
    promosSection.style.display = "";
    promosGrid.innerHTML = promos.map((d) => renderDealCard(d)).join("");
    wireCopyButtons(promosGrid);
  } else {
    promosSection.style.display = "none";
  }

  if (shopping.length) {
    shopSection.style.display = "";
    shopGrid.innerHTML = shopping.map((d) => renderDealCard(d)).join("");
    wireCopyButtons(shopGrid);
  } else {
    shopSection.style.display = "none";
  }
}

function initCommonUi() {
  if (new URLSearchParams(window.location.search).get("embed") === "1") {
    document.body.classList.add("embed-mode");
  }
  const yearEl = qs("#yearNow");
  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  const menuBtn = qs("#mobileMenuBtn");
  const mobileNav = qs("#mobileNav");
  if (menuBtn && mobileNav && !menuBtn.dataset.menuBound) {
    menuBtn.addEventListener("click", () => {
      const open = mobileNav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", String(open));
    });
  }
}

async function boot() {
  initCommonUi();

  qs("#dealSearch")?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value || "";
    renderSections();
  });

  let liveCsvUrl = "";

  try {
    const [affRes, cfgRes, vidRes] = await Promise.all([
      fetch(`../data/affiliates.json?v=20261121c`),
      fetch(`../config.json?v=20261121c`).catch(() => null),
      fetch(`../data/videos.json?v=20261121c`).catch(() => null),
    ]);
    if (!affRes.ok) throw new Error(`HTTP ${affRes.status}`);
    const data = await affRes.json();
    const cfg = cfgRes && cfgRes.ok ? await cfgRes.json() : null;
    const vidData = vidRes && vidRes.ok ? await vidRes.json() : null;

    const rail = qs("#linksShortsRail");
    const sec = qs("#linksShortsSection");
    if (rail && vidData?.shorts?.length) {
      rail.innerHTML = vidData.shorts
        .slice(0, 14)
        .map(
          (s) => `
          <a class="short-card" href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">
            <div class="short-thumb">
              <img src="${escapeHtml(s.thumbnail)}" alt="${escapeHtml(s.title)}" loading="lazy" />
              <span class="short-badge">Short</span>
            </div>
            <div class="short-info">
              <h3 class="short-title">${escapeHtml(s.title)}</h3>
              <div class="short-date">${escapeHtml(s.viewsText || s.location || "YouTube Short")}</div>
            </div>
          </a>
        `
        )
        .join("");
    } else if (sec) {
      sec.style.display = "none";
    }

    state.curated = data.curated || [];
    state.fromVideos = data.fromVideos || [];
    liveCsvUrl = (cfg?.affiliates?.googleSheetCsvUrl || data.googleSheetCsvUrl || "").trim();
    const trendingCsvUrl = (cfg?.affiliates?.trendingSheetCsvUrl || "").trim();

    if (data.disclosure) {
      const box = qs("#disclosureBox");
      if (box) box.innerHTML = `<strong>Affiliate Disclosure:</strong> ${escapeHtml(data.disclosure)}`;
    }

    const updatedEl = qs("#affiliatesUpdatedText");
    if (updatedEl) updatedEl.textContent = formatSyncTime(data.updatedAt);

    renderFilters();
    renderSections();

    if (liveCsvUrl || trendingCsvUrl) {
      try {
        const [liveItems, trendingItems] = await Promise.all([
          liveCsvUrl ? fetchLiveGoogleSheet(liveCsvUrl).catch(() => []) : Promise.resolve([]),
          trendingCsvUrl ? fetchTrendingGoogleSheet(trendingCsvUrl).catch(() => []) : Promise.resolve([]),
        ]);
        const merged = [...liveItems];
        const seenUrls = new Set(merged.map((x) => (x.url || "").toLowerCase().replace(/\/+$/, "")));
        for (const item of trendingItems) {
          const key = (item.url || "").toLowerCase().replace(/\/+$/, "");
          if (key && !seenUrls.has(key)) {
            seenUrls.add(key);
            merged.push(item);
          }
        }
        if (merged.length) {
          state.curated = merged;
          const statusEl = qs("#sheetStatusText");
          if (statusEl) statusEl.textContent = `Personally curated (${merged.length} active offers)`;
          renderFilters();
          renderSections();
        }
      } catch (sheetErr) {
        console.warn("Curated offers refresh skipped:", sheetErr);
      }
    }
  } catch (err) {
    const grid = qs("#promotionsGrid");
    if (grid) {
      grid.innerHTML = `<div class="empty-state">Unable to load deals right now. Please refresh in a moment.</div>`;
    }
    console.error("Failed to load affiliates.json:", err);
  }
}

boot();
