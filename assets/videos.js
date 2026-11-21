const state = {
  videos: [],
  shorts: [],
  activeCategory: "All",
  searchQuery: "",
  activeModalVideo: null,
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

function buildEmbedUrl(videoId, startSeconds = 0, autoplay = true) {
  const params = new URLSearchParams({
    rel: "0",
    modestbranding: "1",
    autoplay: autoplay ? "1" : "0",
  });
  if (startSeconds > 0) params.set("start", String(startSeconds));
  return `https://www.youtube-nocookie.com/embed/${encodeURIComponent(videoId)}?${params.toString()}`;
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

function renderFeatured(video) {
  const container = qs("#featuredContainer");
  if (!container || !video) return;

  const summary = video.summary || {};
  const highlights = (summary.highlights || []).slice(0, 3);
  const linkCount = (video.affiliateLinks || []).length;

  container.innerHTML = `
    <article class="featured-card">
      <div class="featured-media" id="featuredMediaWrap">
        <img
          src="${escapeHtml(video.thumbnail)}"
          onerror="this.onerror=null;this.src='${escapeHtml(video.fallbackThumbnail)}'"
          alt="${escapeHtml(video.title)}"
          loading="eager"
        />
        <button class="play-trigger" id="featuredPlayBtn" aria-label="Play ${escapeHtml(video.title)}">
          <span class="play-circle">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="currentColor"><polygon points="7,4 20,12 7,20"/></svg>
          </span>
          <span class="play-label">Watch Latest Episode</span>
        </button>
      </div>

      <div class="featured-body">
        <div>
          <div class="meta-line">
            <span class="tag tag-accent">Latest Release</span>
            <span class="tag">${escapeHtml(video.category || "Hotel Reviews")}</span>
            <span>${escapeHtml(video.location || "")}</span>
            <span>&bull;</span>
            <span>${escapeHtml(formatDate(video.publishedDate))}</span>
          </div>

          <h2 class="featured-title">${escapeHtml(video.title)}</h2>
        </div>

        <div class="ai-summary-box">
          <div class="ai-summary-label">AI Editorial Summary</div>
          <p class="ai-summary-tldr">${escapeHtml(summary.tldr || "")}</p>
          ${
            highlights.length
              ? `<ul class="highlights-list">${highlights
                  .map((h) => `<li>${escapeHtml(h)}</li>`)
                  .join("")}</ul>`
              : ""
          }
        </div>

        <div class="featured-actions">
          <button class="btn btn-dark" id="featuredDetailsBtn">
            Full Summary &amp; Chapters (${(video.chapters || []).length})
          </button>
          ${
            linkCount
              ? `<a class="btn btn-outline" href="./links/">Gear &amp; Deals (${linkCount})</a>`
              : ""
          }
        </div>
      </div>
    </article>
  `;

  qs("#featuredPlayBtn")?.addEventListener("click", () => {
    const wrap = qs("#featuredMediaWrap");
    if (!wrap) return;
    wrap.innerHTML = `<iframe src="${buildEmbedUrl(video.id, 0, true)}" title="${escapeHtml(
      video.title
    )}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`;
  });

  qs("#featuredDetailsBtn")?.addEventListener("click", () => openModal(video));
}

function renderFilters() {
  const container = qs("#categoryFilters");
  if (!container) return;

  const counts = new Map();
  for (const v of state.videos) {
    const cat = v.category || "Hotel Reviews";
    counts.set(cat, (counts.get(cat) || 0) + 1);
  }

  const orderedCats = ["All", ...Array.from(counts.keys()).sort()];
  container.innerHTML = orderedCats
    .map((cat) => {
      const count = cat === "All" ? state.videos.length : counts.get(cat) || 0;
      const isActive = state.activeCategory === cat;
      return `<button class="pill ${isActive ? "active" : ""}" data-cat="${escapeHtml(
        cat
      )}" role="tab" aria-selected="${isActive}">${escapeHtml(cat)} (${count})</button>`;
    })
    .join("");

  container.querySelectorAll(".pill").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.activeCategory = btn.dataset.cat || "All";
      renderFilters();
      renderVideoGrid();
    });
  });
}

function getFilteredVideos() {
  const q = state.searchQuery.trim().toLowerCase();
  return state.videos.filter((v) => {
    const catMatch = state.activeCategory === "All" || v.category === state.activeCategory;
    if (!catMatch) return false;
    if (!q) return true;
    const hay = [
      v.title,
      v.location,
      v.category,
      v.summary?.tldr,
      ...(v.summary?.highlights || []),
      v.summary?.bestFor,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

function renderVideoGrid() {
  const grid = qs("#videoGrid");
  if (!grid) return;

  const list = getFilteredVideos();
  if (!list.length) {
    grid.innerHTML = `<div class="empty-state">No episodes matched "${escapeHtml(
      state.searchQuery
    )}". Try clearing your filter or searching another destination.</div>`;
    return;
  }

  grid.innerHTML = list
    .map((v) => {
      const tldr = v.summary?.tldr || "";
      const chapterCount = (v.chapters || []).length;
      return `
        <article class="video-card">
          <button class="card-thumb" data-open-id="${escapeHtml(v.id)}" aria-label="Watch and summarize ${escapeHtml(v.title)}">
            <img
              src="${escapeHtml(v.thumbnail)}"
              onerror="this.onerror=null;this.src='${escapeHtml(v.fallbackThumbnail)}'"
              alt="${escapeHtml(v.title)}"
              loading="lazy"
            />
            <span class="thumb-location">${escapeHtml(v.location || "Travel")}</span>
            <span class="thumb-play" aria-hidden="true">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><polygon points="7,4 20,12 7,20"/></svg>
            </span>
          </button>

          <div class="card-content">
            <div class="meta-line">
              <span class="tag">${escapeHtml(v.category || "Review")}</span>
              <span>${escapeHtml(formatDate(v.publishedDate))}</span>
            </div>

            <h3 class="card-title">${escapeHtml(v.title)}</h3>
            <p class="card-summary">${escapeHtml(tldr)}</p>

            <div class="card-footer">
              <button class="summary-btn" data-open-id="${escapeHtml(v.id)}">
                AI Summary &amp; Watch &rarr;
              </button>
              <span class="card-submeta">${chapterCount ? `${chapterCount} chapters` : "Full tour"}</span>
            </div>
          </div>
        </article>
      `;
    })
    .join("");

  grid.querySelectorAll("[data-open-id]").forEach((el) => {
    el.addEventListener("click", () => {
      const vid = state.videos.find((item) => item.id === el.dataset.openId);
      if (vid) openModal(vid);
    });
  });
}

function renderShorts() {
  const rail = qs("#shortsRail");
  const section = qs("#shortsSection");
  if (!rail || !section) return;

  if (!state.shorts.length) {
    section.style.display = "none";
    return;
  }

  rail.innerHTML = state.shorts
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
          <span class="short-badge">Short</span>
        </div>
        <div class="short-info">
          <h3 class="short-title">${escapeHtml(s.title)}</h3>
          <div class="short-date">${escapeHtml(formatDate(s.publishedDate))}</div>
        </div>
      </a>
    `
    )
    .join("");
}

function openModal(video, startSeconds = 0) {
  state.activeModalVideo = video;
  const modal = qs("#videoModal");
  const meta = qs("#modalMeta");
  const player = qs("#modalPlayer");
  const body = qs("#modalBody");
  if (!modal || !meta || !player || !body) return;

  const summary = video.summary || {};
  const highlights = summary.highlights || [];
  const chapters = video.chapters || [];
  const links = video.affiliateLinks || [];

  meta.innerHTML = `
    <span class="tag tag-accent">${escapeHtml(video.category || "Review")}</span>
    <span class="tag">${escapeHtml(video.location || "Global")}</span>
    <span>${escapeHtml(formatDate(video.publishedDate))}</span>
  `;

  player.innerHTML = `<iframe id="modalIframe" src="${buildEmbedUrl(
    video.id,
    startSeconds,
    true
  )}" title="${escapeHtml(
    video.title
  )}" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`;

  body.innerHTML = `
    <div>
      <h2 class="modal-title" id="modalVideoTitle">${escapeHtml(video.title)}</h2>
    </div>

    <div class="modal-grid">
      <div class="ai-summary-box">
        <div class="ai-summary-label">AI Travel Summary</div>
        <p class="ai-summary-tldr">${escapeHtml(summary.tldr || "")}</p>
        ${
          highlights.length
            ? `<ul class="highlights-list">${highlights
                .map((h) => `<li>${escapeHtml(h)}</li>`)
                .join("")}</ul>`
            : ""
        }
        ${
          summary.bestFor
            ? `<p style="margin:14px 0 0;font-size:13px;color:var(--ink-secondary);"><strong>Best for:</strong> ${escapeHtml(
                summary.bestFor
              )}</p>`
            : ""
        }
      </div>

      <div>
        <div class="ai-summary-label" style="margin-bottom:10px;">${
          chapters.length ? `Jump to Chapter (${chapters.length})` : "Watch on YouTube"
        }</div>
        ${
          chapters.length
            ? `<div class="chapters-list">${chapters
                .map(
                  (c) => `
                <button class="chapter-btn" data-jump-sec="${c.seconds}">
                  <span class="chapter-time">${escapeHtml(c.time)}</span>
                  <span>${escapeHtml(c.label)}</span>
                </button>`
                )
                .join("")}</div>`
            : `<p style="font-size:13.5px;color:var(--ink-secondary);margin:0 0 12px;">Open this full tour directly on YouTube to comment or subscribe.</p>
               <a class="btn btn-primary" href="${escapeHtml(video.url)}" target="_blank" rel="noopener noreferrer">Open on YouTube &rarr;</a>`
        }
      </div>
    </div>

    ${
      links.length
        ? `<div>
            <div class="ai-summary-label" style="margin-bottom:10px;">Links &amp; Gear Mentioned in This Video</div>
            <div class="video-links-list">
              ${links
                .slice(0, 6)
                .map(
                  (l) => `
                  <a class="mini-link-card" href="${escapeHtml(l.url)}" target="_blank" rel="sponsored noopener noreferrer">
                    <span>${escapeHtml(l.title)}</span>
                    <span style="color:var(--accent);">&nearr;</span>
                  </a>`
                )
                .join("")}
            </div>
          </div>`
        : ""
    }
  `;

  body.querySelectorAll("[data-jump-sec]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const sec = Number(btn.dataset.jumpSec || 0);
      const iframe = qs("#modalIframe");
      if (iframe) iframe.src = buildEmbedUrl(video.id, sec, true);
    });
  });

  modal.classList.add("open");
  document.body.style.overflow = "hidden";
}

function closeModal() {
  const modal = qs("#videoModal");
  const player = qs("#modalPlayer");
  if (!modal) return;
  modal.classList.remove("open");
  if (player) player.innerHTML = "";
  document.body.style.overflow = "";
  state.activeModalVideo = null;
}

async function boot() {
  initCommonUi();

  qs("#modalCloseBtn")?.addEventListener("click", closeModal);
  qs("#videoModal")?.addEventListener("click", (e) => {
    if (e.target === qs("#videoModal")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && state.activeModalVideo) closeModal();
  });

  const searchInput = qs("#videoSearch");
  searchInput?.addEventListener("input", (e) => {
    state.searchQuery = e.target.value || "";
    renderVideoGrid();
  });

  try {
    const res = await fetch(`./data/videos.json?v=${Date.now()}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    state.videos = data.videos || [];
    state.shorts = data.shorts || [];

    const updatedEl = qs("#lastUpdatedText");
    if (updatedEl) updatedEl.textContent = formatSyncTime(data.updatedAt);

    if (state.videos.length) {
      renderFeatured(state.videos[0]);
    }
    renderFilters();
    renderVideoGrid();
    renderShorts();
  } catch (err) {
    const grid = qs("#videoGrid");
    if (grid) {
      grid.innerHTML = `<div class="empty-state">Unable to load the live video feed right now. Visit <a href="https://www.youtube.com/@TheUnchartedItinerary" style="color:var(--accent);text-decoration:underline;">@TheUnchartedItinerary on YouTube</a>.</div>`;
    }
    console.error("Failed to load videos.json:", err);
  }
}

boot();
