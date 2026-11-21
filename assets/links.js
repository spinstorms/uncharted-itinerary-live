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
  if (!iso) return "Updated recently";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Updated recently";
  return `Last synced ${d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })}`;
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

    items.push({
      id: `live-sheet-${idx}`,
      source: "curated",
      featured: ["true", "1", "yes"].includes((obj.featured || "").toLowerCase()),
      category: obj.category || "Travel & Perks",
      title,
      badge: obj["offer badge"] || obj.badge || "",
      description: obj.description || "",
      promoCode: obj["promo code"] || obj.code || "",
      url,
      buttonLabel: obj["button label"] || "Explore Deal",
      sortOrder: Number(obj["sort order"] || obj.sort || idx) || idx,
    });
  }
  items.sort((a, b) => Number(b.featured) - Number(a.featured) || a.sortOrder - b.sortOrder);
  return items;
}

function getAllDeals() {
  return [...state.curated, ...state.fromVideos];
}

function renderDealCard(deal, highlightFeatured = false) {
  const mentions = deal.mentionedIn || [];
  const mentionLabel =
    mentions.length > 1
      ? `Featured in ${mentions.length}+ videos`
      : mentions.length === 1
      ? `From: ${mentions[0].title.slice(0, 34)}${mentions[0].title.length > 34 ? "…" : ""}`
      : deal.source === "youtube"
      ? "Auto-pulled from YouTube"
      : "Curated pick";

  return `
    <article class="deal-card ${highlightFeatured && deal.featured ? "is-featured" : ""}">
      <div class="deal-top">
        <span class="tag">${escapeHtml(deal.category || "Travel")}</span>
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
        <a class="btn ${highlightFeatured ? "btn-primary" : "btn-dark"}" href="${escapeHtml(
          deal.url
        )}" target="_blank" rel="sponsored noopener noreferrer">
          ${escapeHtml(deal.buttonLabel || "Open Deal")} &nearr;
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

function renderFeaturedDeals() {
  const section = qs("#featuredDealsSection");
  const grid = qs("#featuredDealsGrid");
  if (!section || !grid) return;

  const featured = state.curated.filter((d) => d.featured).slice(0, 3);
  if (!featured.length) {
    section.style.display = "none";
    return;
  }
  section.style.display = "";
  grid.innerHTML = featured.map((d) => renderDealCard(d, true)).join("");
  wireCopyButtons(grid);
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
  if (state.fromVideos.length) {
    counts.set("From Recent Videos", state.fromVideos.length);
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
      renderDealsGrid();
    });
  });
}

function renderDealsGrid() {
  const grid = qs("#dealsGrid");
  if (!grid) return;

  const q = state.searchQuery.trim().toLowerCase();
  const sourceList =
    state.activeCategory === "From Recent Videos"
      ? state.fromVideos
      : getAllDeals().filter(
          (d) => state.activeCategory === "All" || d.category === state.activeCategory
        );

  const filtered = sourceList.filter((d) => {
    if (!q) return true;
    const hay = [d.title, d.category, d.badge, d.description, d.promoCode]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });

  if (!filtered.length) {
    grid.innerHTML = `<div class="empty-state">No deals matched "${escapeHtml(
      state.searchQuery
    )}". Try clearing your search.</div>`;
    return;
  }

  grid.innerHTML = filtered.map((d) => renderDealCard(d, false)).join("");
  wireCopyButtons(grid);
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

async function boot() {
  initCommonUi();

  qs("#dealSearch")?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value || "";
    renderDealsGrid();
  });

  let liveCsvUrl = "";

  try {
    const [affRes, cfgRes] = await Promise.all([
      fetch(`../data/affiliates.json?v=${Date.now()}`),
      fetch(`../config.json?v=${Date.now()}`).catch(() => null),
    ]);
    if (!affRes.ok) throw new Error(`HTTP ${affRes.status}`);
    const data = await affRes.json();
    const cfg = cfgRes && cfgRes.ok ? await cfgRes.json() : null;

    state.curated = data.curated || [];
    state.fromVideos = data.fromVideos || [];
    liveCsvUrl = (cfg?.affiliates?.googleSheetCsvUrl || data.googleSheetCsvUrl || "").trim();

    if (data.disclosure) {
      const box = qs("#disclosureBox");
      if (box) box.innerHTML = `<strong>Affiliate Disclosure:</strong> ${escapeHtml(data.disclosure)}`;
    }

    const updatedEl = qs("#affiliatesUpdatedText");
    if (updatedEl) updatedEl.textContent = formatSyncTime(data.updatedAt);

    renderFeaturedDeals();
    renderFilters();
    renderDealsGrid();

    // If a published Google Sheet CSV URL is configured, refresh live in the browser too!
    if (liveCsvUrl) {
      try {
        const liveItems = await fetchLiveGoogleSheet(liveCsvUrl);
        if (liveItems.length) {
          state.curated = liveItems;
          const statusEl = qs("#sheetStatusText");
          if (statusEl) statusEl.textContent = "Live from Google Sheets + YouTube";
          renderFeaturedDeals();
          renderFilters();
          renderDealsGrid();
        }
      } catch (sheetErr) {
        console.warn("Live sheet refresh skipped, using synced snapshot:", sheetErr);
      }
    }
  } catch (err) {
    const grid = qs("#dealsGrid");
    if (grid) {
      grid.innerHTML = `<div class="empty-state">Unable to load deals right now. Please refresh in a moment.</div>`;
    }
    console.error("Failed to load affiliates.json:", err);
  }
}

boot();
