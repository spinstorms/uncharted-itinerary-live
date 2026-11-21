const MAIN_VIDEO_ID = "5H-BBvM9O70";

const LUNA_LINKS_FALLBACK = [
  {
    title: "Insta360 Luna Ultra — Standard Kit",
    category: "Camera & Travel Gear",
    badge: "My Daily Camera",
    description: "The core Luna Ultra gimbal with the detachable wireless screen — the setup I kept for filming hotel tours.",
    url: "https://link.amazon/B0fpiIMTi",
    buttonLabel: "Shop on Amazon",
    featured: true,
  },
  {
    title: "Insta360 Luna Ultra — Creator Kit (Black)",
    category: "Camera & Travel Gear",
    badge: "Creator Bundle",
    description: "Matte Black Creator Kit bundling key accessories for travel vlogging right out of the box.",
    url: "https://link.amazon/B03YstgcC",
    buttonLabel: "Shop on Amazon",
    featured: true,
  },
  {
    title: "Insta360 Luna Ultra — Creator Kit (White)",
    category: "Camera & Travel Gear",
    badge: "Creator Bundle",
    description: "Arctic White Creator Kit — lightweight, sleek, and easy to spot in a packed travel bag.",
    url: "https://link.amazon/B09TARLyD",
    buttonLabel: "Shop on Amazon",
    featured: false,
  },
  {
    title: "Insta360 Luna Ultra Wide Angle Lens",
    category: "Must-Have Accessory",
    badge: "Hotel Room Essential",
    description: "Snap-on ultra-wide attachment — makes a huge difference when filming suites, villas, and bathrooms.",
    url: "https://link.amazon/B00hjVInJ",
    buttonLabel: "Shop on Amazon",
    featured: true,
  },
  {
    title: "Insta360 Luna Ultra Battery Handle",
    category: "Must-Have Accessory",
    badge: "All-Day Power",
    description: "Extra grip and battery life for shooting full-property resort walkthroughs without running low.",
    url: "https://link.amazon/B0cxr0rKz",
    buttonLabel: "Shop on Amazon",
    featured: false,
  },
];

const DJI_LINKS_FALLBACK = [
  {
    title: "DJI Osmo Pocket 4P — Standard Edition",
    category: "Camera & Travel Gear",
    badge: "Best Value Pick",
    description: "Compact, familiar DJI gimbal ergonomics with crisp 4K footage and strong price-to-performance.",
    url: "https://www.amazon.co.uk/s?k=DJI+Osmo+Pocket+4P",
    buttonLabel: "Check on Amazon",
    featured: false,
  },
  {
    title: "DJI Osmo Pocket 4P — Vlog / Creator Combo",
    category: "Camera & Travel Gear",
    badge: "Value Bundle",
    description: "The full DJI bundle compared in our Bali test — great all-in-one value if you love the DJI ecosystem.",
    url: "https://www.amazon.co.uk/s?k=DJI+Osmo+Pocket+4P+Creator+Combo",
    buttonLabel: "Check on Amazon",
    featured: false,
  },
  {
    title: "DJI Mic Mini 2",
    category: "Travel Audio",
    badge: "Wireless Mic",
    description: "Ultra-compact wireless microphone tested head-to-head against the Insta360 Mic Pro in this review.",
    url: "https://www.amazon.co.uk/s?k=DJI+Mic+Mini+2",
    buttonLabel: "Check on Amazon",
    featured: false,
  },
];

const KEY_CHAPTERS = [
  { time: "01:18", seconds: 78, label: "Akula Bingin Villa Tour" },
  { time: "03:17", seconds: 197, label: "Night Mode (1x)" },
  { time: "03:59", seconds: 239, label: "Low Light (3x)" },
  { time: "04:34", seconds: 274, label: "Beach Audio Test" },
  { time: "06:50", seconds: 410, label: "Screen as a Mic" },
  { time: "08:03", seconds: 483, label: "Build & Weight" },
  { time: "08:50", seconds: 530, label: "3x & 12x Zoom" },
  { time: "10:48", seconds: 648, label: "Combos Compared" },
  { time: "15:08", seconds: 908, label: "Mic Mini 2 vs Mic Pro" },
  { time: "16:40", seconds: 1000, label: "Price Comparison" },
  { time: "21:30", seconds: 1290, label: "Final Verdict" },
];

const qs = (sel) => document.querySelector(sel);

function escapeHtml(str = "") {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function buildEmbedUrl(videoId, startSeconds = 0, autoplay = true) {
  const params = new URLSearchParams({
    rel: "0",
    modestbranding: "1",
    autoplay: autoplay ? "1" : "0",
  });
  if (startSeconds > 0) params.set("start", String(startSeconds));
  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${params.toString()}`;
}

function playMainVideoAt(seconds = 0) {
  const wrap = qs("#cameraPlayerWrap");
  if (!wrap) return;
  wrap.innerHTML = `<iframe src="${buildEmbedUrl(
    MAIN_VIDEO_ID,
    seconds,
    true
  )}" title="DJI Pocket 4P vs Luna Ultra: Ultimate 2026 Travel Setup?" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`;
  wrap.scrollIntoView({ behavior: "smooth", block: "center" });
}

function renderGearCard(item, primaryCta = false) {
  return `
    <article class="deal-card ${item.featured ? "is-featured" : ""}">
      <div class="deal-top">
        <span class="tag">${escapeHtml(item.category || "Camera Gear")}</span>
        ${item.badge ? `<span class="tag tag-accent">${escapeHtml(item.badge)}</span>` : ""}
      </div>
      <h3 class="deal-title">${escapeHtml(item.title)}</h3>
      ${item.description ? `<p class="deal-desc">${escapeHtml(item.description)}</p>` : ""}
      <div class="deal-footer">
        <span class="deal-mentions">Tested in this review</span>
        <a class="btn ${primaryCta ? "btn-primary" : "btn-outline"}" href="${escapeHtml(
          item.url
        )}" target="_blank" rel="sponsored noopener noreferrer">
          ${escapeHtml(item.buttonLabel || "Shop Now")} &nearr;
        </a>
      </div>
    </article>
  `;
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

function renderChapters(chapters) {
  const container = qs("#cameraChapterChips");
  if (!container) return;
  container.innerHTML = chapters
    .map(
      (c) => `
      <button class="chapter-chip" data-jump-sec="${c.seconds}">
        <span class="chapter-time">${escapeHtml(c.time)}</span>
        <span>${escapeHtml(c.label)}</span>
      </button>`
    )
    .join("");

  container.querySelectorAll("[data-jump-sec]").forEach((btn) => {
    btn.addEventListener("click", () => {
      playMainVideoAt(Number(btn.dataset.jumpSec || 0));
    });
  });
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(`${dateStr}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

async function boot() {
  initCommonUi();

  qs("#cameraPlayBtn")?.addEventListener("click", () => playMainVideoAt(0));
  renderChapters(KEY_CHAPTERS);

  // Render default gear grids immediately, then enrich from live affiliates.json if user adds DJI links in Sheet
  const lunaGrid = qs("#lunaGearGrid");
  const djiGrid = qs("#djiGearGrid");
  if (lunaGrid) lunaGrid.innerHTML = LUNA_LINKS_FALLBACK.map((x) => renderGearCard(x, true)).join("");
  if (djiGrid) djiGrid.innerHTML = DJI_LINKS_FALLBACK.map((x) => renderGearCard(x, false)).join("");

  try {
    const [affRes, vidRes] = await Promise.all([
      fetch(`../data/affiliates.json?v=20261121c`).catch(() => null),
      fetch(`../data/videos.json?v=20261121c`).catch(() => null),
    ]);

    if (affRes && affRes.ok) {
      const aff = await affRes.json();
      const all = [...(aff.curated || []), ...(aff.fromVideos || [])];

      const lunaLive = all.filter((x) => /luna|insta360/i.test(`${x.title} ${x.url}`));
      if (lunaLive.length && lunaGrid) {
        lunaGrid.innerHTML = lunaLive.map((x) => renderGearCard(x, true)).join("");
      }

      // Show only the actual Pocket 4P & DJI Mic Mini 2 tested in this shootout
      const djiLive = all.filter((x) => /pocket\s*4p|mic\s*mini\s*2/i.test(`${x.title} ${x.url}`));
      if (djiLive.length && djiGrid) {
        djiGrid.innerHTML = djiLive.map((x) => renderGearCard(x, true)).join("");
      }
    }

    if (vidRes && vidRes.ok) {
      const data = await vidRes.json();
      const gearShorts = (data.shorts || []).filter(
        (s) =>
          s.category === "Travel Gear" ||
          /insta360|luna|pocket|osmo|dji|mic|camera/i.test(s.title || "")
      );
      const rail = qs("#cameraShortsRail");
      const section = qs("#cameraClipsSection");
      if (rail && section) {
        if (!gearShorts.length) {
          section.style.display = "none";
        } else {
          rail.innerHTML = gearShorts
            .map(
              (s) => `
              <a class="short-card" href="${escapeHtml(s.url)}" target="_blank" rel="noopener noreferrer">
                <div class="short-thumb">
                  <img
                    src="${escapeHtml(s.thumbnail)}"
                    onerror="this.onerror=null;this.src='${escapeHtml(s.fallbackThumbnail)}'"
                    alt="${escapeHtml(s.title)}"
                    loading="lazy"
                  />
                  <span class="short-badge">Demo Short</span>
                </div>
                <div class="short-info">
                  <h3 class="short-title">${escapeHtml(s.title)}</h3>
                  <div class="short-date">${escapeHtml(formatDate(s.publishedDate) || s.viewsText || "YouTube Short")}</div>
                </div>
              </a>`
            )
            .join("");
        }
      }
    }
  } catch (err) {
    console.warn("Camera page live hydration skipped:", err);
  }
}

boot();
