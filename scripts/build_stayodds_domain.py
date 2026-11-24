#!/usr/bin/env python3
"""
Build the standalone https://stayodds.com static site bundle into .stayodds-dist/
directly from the single-source-of-truth files in uncharted-itinerary-live.

IMPORTANT:
- Strictly READ-ONLY on uncharted-itinerary-live's live site files (never modifies
  uncharteditinerary.com pages, assets, or sitemap.xml).
- Rewrites StayOdds routes (/ comparator root, /compare/ alias, /hotels/, /brands/,
  /stayodds/<slug>/, /destinations/<slug>/) with:
    * https://stayodds.com canonicals, OG URLs, JSON-LD, robots.txt & sitemap.xml
    * Root-absolute /assets/ and /data/ paths (safe at every route depth)
    * Seamless cross-domain nav: StayOdds tabs stay on stayodds.com, Hub tabs
      (Videos, Cameras, Deals & Gear, About, FAQ, Contact, Privacy) link directly
      to https://uncharteditinerary.com/...
    * Automatic ?import_saved= shortlist migration support for zero-loss cutover.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_TEMPLATES = ROOT / "stayodds-src"
DIST = ROOT / ".stayodds-dist"
HUB_URL = "https://uncharteditinerary.com"
STAYODDS_URL = "https://stayodds.com"
STAYODDS_GA4_ID = "G-NR74H0P96J"

STAYODDS_GA4_SNIPPET = f"""  <!-- Google tag (gtag.js) — StayOdds.com -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={STAYODDS_GA4_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{STAYODDS_GA4_ID}');
  </script>"""

STAYODDS_DRIVE_SNIPPET = """  <script nowprocket data-noptimize="1" data-cfasync="false" data-wpfc-render="false" seraph-accel-crit="1" data-no-defer="1" data-cmp-ab="2">
    (function () {
        var script = document.createElement("script");
        script.async = 1;
        script.setAttribute("data-cmp-ab","2");
        script.src = 'https://emrld.ltd/NjA2MTYz.js?t=606163';
        document.head.appendChild(script);
    })();
  </script>"""

EMRLD_SCRIPT_RE = re.compile(
    r'<script\b[^>]*>(?:(?!</script>)[\s\S])*?emrld\.ltd/(?:(?!</script>)[\s\S])*?</script>',
    re.IGNORECASE,
)


def rewrite_html_for_stayodds(html: str, page_kind: str) -> str:
    """
    Transform a StayOdds HTML page into its standalone stayodds.com counterpart.
    page_kind: 'root_compare' | 'hotels' | 'brands' | 'detail' | 'destination'
    """
    # 1. Canonical / OG / JSON-LD domain swaps for StayOdds routes
    html = html.replace(f"{HUB_URL}/compare/", f"{STAYODDS_URL}/")
    html = html.replace(f"{HUB_URL}/hotels/", f"{STAYODDS_URL}/hotels/")
    html = html.replace(f"{HUB_URL}/brands/", f"{STAYODDS_URL}/brands/")
    html = html.replace(f"{HUB_URL}/stayodds/", f"{STAYODDS_URL}/stayodds/")
    html = html.replace(f"{HUB_URL}/destinations/", f"{STAYODDS_URL}/destinations/")
    html = html.replace(f"{HUB_URL}/assets/", f"{STAYODDS_URL}/assets/")
    html = html.replace("stayodds_v3_bright_og_hero_1200x630.png", "stayodds_v5_og_hero_1200x630.png")
    html = html.replace("stayodds_v4_bright_og_hero_1200x630.png", "stayodds_v5_og_hero_1200x630.png")

    # 2. Root-absolute assets, favicons, data preloads & banner CSS vars
    html = re.sub(r'((?:href|src)=["\'])(?:\.\./)+assets/', r'\1/assets/', html)
    html = re.sub(r'((?:href|src)=["\'])(?:\.\./)+data/', r'\1/data/', html)
    html = re.sub(r'((?:href|src)=["\'])(?:\.\./)+favicon\.ico', r'\1/favicon.ico?v=2', html)
    html = re.sub(r"url\(['\"]?(?:\.\./)+assets/", "url('/assets/", html)
    html = re.sub(r'data-hero-base=["\'](?:\.\./)+assets/', 'data-hero-base="/assets/', html)
    html = html.replace('import("../../assets/stayodds-share-card.js', 'import("/assets/stayodds-share-card.js')
    html = re.sub(r'styles\.min\.css\?v=\d+', 'styles.min.css?v=44', html)

    # 3. Cross-domain navigation links to The Uncharted Itinerary Hub
    for hub_section in ("cameras", "links", "about", "faq", "contact", "privacy"):
        html = re.sub(
            rf'href=["\'](?:\.\./)+{hub_section}/["\']',
            f'href="{HUB_URL}/{hub_section}/"',
            html,
        )
    # Relative links pointing back to the Hub home ("../" or "../../")
    html = re.sub(r'href=["\'](?:\.\./)+["\']', f'href="{HUB_URL}/"', html)

    # 4. StayOdds internal links -> clean root-absolute paths
    html = re.sub(r'href=["\'](?:\.\./)+compare/\?', 'href="/?', html)
    html = re.sub(r'href=["\'](?:\.\./)+compare/["\']', 'href="/"', html)
    html = re.sub(r'href=["\'](?:\.\./)+hotels/', 'href="/hotels/', html)
    html = re.sub(r'href=["\'](?:\.\./)+brands/', 'href="/brands/', html)
    html = re.sub(r'href=["\'](?:\.\./)+stayodds/', 'href="/stayodds/', html)
    html = re.sub(r'href=["\'](?:\.\./)+destinations/', 'href="/destinations/', html)

    # On root_compare (/index.html), replace "./" self-links with "/"
    if page_kind == "root_compare":
        html = html.replace('href="./"', 'href="/"')
        html = html.replace('href="./?', 'href="/?')

    # On detail pages (/stayodds/<slug>/), update inline breadcrumb JS routes too
    if page_kind == "detail":
        html = html.replace('"../../hotels/"', '"/hotels/"')
        html = html.replace('"../../hotels/?region="', '"/hotels/?region="')
        html = html.replace('"../../compare/?region="', '"/?region="')
        html = html.replace('"../../compare/?embed=1"', '"/?embed=1"')
        html = html.replace('href="../', 'href="/stayodds/')
        html = html.replace('href="../../compare/"', 'href="/"')

    # On destination pages (/destinations/<slug>/), fix sibling guide links & compare links
    if page_kind == "destination":
        html = re.sub(r'href="\.\./([a-z0-9-]+)/"', r'href="/destinations/\1/"', html)

    # 5. Swap Travelpayouts Drive/Emerald script to StayOdds.com project (NjA2MTYz.js?t=606163)
    if EMRLD_SCRIPT_RE.search(html):
        html = EMRLD_SCRIPT_RE.sub(STAYODDS_DRIVE_SNIPPET.strip(), html, count=1)
    elif "</head>" in html:
        html = html.replace("</head>", f"{STAYODDS_DRIVE_SNIPPET}\n</head>", 1)

    # 6. Inject StayOdds.com Google Analytics 4 tag (G-NR74H0P96J)
    if STAYODDS_GA4_ID not in html and "</head>" in html:
        html = html.replace("</head>", f"{STAYODDS_GA4_SNIPPET}\n</head>", 1)

    return html


def rewrite_js_for_stayodds(assets_dir: Path) -> None:
    """Rewrite relative paths & share URLs inside .stayodds-dist/assets/*.js."""
    # 1. compare.js
    cmp_path = assets_dir / "compare.js"
    cmp = cmp_path.read_text(encoding="utf-8")
    cmp = cmp.replace('`../stayodds/${encodeURIComponent(h.id)}/?embed=1`', '`/stayodds/${encodeURIComponent(h.id)}/?embed=1`')
    cmp = cmp.replace('`../stayodds/${encodeURIComponent(h.id)}/`', '`/stayodds/${encodeURIComponent(h.id)}/`')
    cmp = cmp.replace('"../assets/placeholders/default-stayodds.webp?v=169"', '"/assets/placeholders/default-stayodds.webp?v=169"')
    cmp = cmp.replace('`../${thumb}`', '`/${thumb}`')
    cmp = cmp.replace('`../?video=${encodeURIComponent(h.videoId)}`', f'`{HUB_URL}/?video=${{encodeURIComponent(h.videoId)}}`')
    cmp = cmp.replace('href="../brands/"', 'href="/brands/"')
    cmp = cmp.replace(f'{HUB_URL}/compare/?a=', f'{STAYODDS_URL}/?a=')
    cmp = cmp.replace(f'{HUB_URL}/compare/?scope=saved&saved=', f'{STAYODDS_URL}/?scope=saved&saved=')
    cmp = cmp.replace('`../data/stayodds-index.json', '`/data/stayodds-index.json')

    # Inject automatic ?import_saved=slug1,slug2 shortlist handoff right inside boot()
    import_snippet = """  // Seamless cross-domain shortlist import when redirected from uncharteditinerary.com
  const importSavedRaw = params.get("import_saved");
  if (importSavedRaw) {
    const incoming = importSavedRaw.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 60);
    if (incoming.length) {
      const merged = Array.from(new Set([...getShortlistIds(), ...incoming]));
      try { localStorage.setItem(SHORTLIST_KEY, JSON.stringify(merged)); } catch (_) {}
      window.stayOddsShortlist?.syncButtons?.();
    }
    try {
      const cleanUrl = new URL(window.location.href);
      cleanUrl.searchParams.delete("import_saved");
      window.history.replaceState({}, "", cleanUrl.toString());
    } catch (_) {}
  }
"""
    anchor = '  const savedParam = (params.get("saved") || "").trim();'
    if anchor not in cmp:
        raise RuntimeError("Could not find savedParam anchor in compare.js for import_saved injection")
    if "import_saved" not in cmp:
        cmp = cmp.replace(anchor, import_snippet + "\n" + anchor, 1)
    cmp_path.write_text(cmp, encoding="utf-8")

    # 2. hotels.js
    hot_path = assets_dir / "hotels.js"
    hot = hot_path.read_text(encoding="utf-8")
    hot = hot.replace('`../stayodds/${encodeURIComponent(h.id)}/?${q.toString()}`', '`/stayodds/${encodeURIComponent(h.id)}/?${q.toString()}`')
    hot = hot.replace('"../assets/placeholders/default-stayodds.webp?v=169"', '"/assets/placeholders/default-stayodds.webp?v=169"')
    hot = hot.replace('`../${thumb}`', '`/${thumb}`')
    hot = hot.replace('`../?video=${encodeURIComponent(h.videoId)}`', f'`{HUB_URL}/?video=${{encodeURIComponent(h.videoId)}}`')
    hot = hot.replace('href="../compare/?a=', 'href="/?a=')
    hot = hot.replace('`../data/stayodds-index.json', '`/data/stayodds-index.json')
    hot_path.write_text(hot, encoding="utf-8")

    # 3. brands.js
    br_path = assets_dir / "brands.js"
    br = br_path.read_text(encoding="utf-8")
    br = br.replace('href="../compare/?brand=', 'href="/?brand=')
    br = br.replace('href="../compare/?a=', 'href="/?a=')
    br = br.replace('href="../stayodds/', 'href="/stayodds/')
    br = br.replace('`../data/stayodds-index.json', '`/data/stayodds-index.json')
    br_path.write_text(br, encoding="utf-8")

    # 4. stayodds-share-card.js
    sc_path = assets_dir / "stayodds-share-card.js"
    sc = sc_path.read_text(encoding="utf-8")
    sc = sc.replace(f'{HUB_URL}/compare/?a=', f'{STAYODDS_URL}/?a=')
    sc = sc.replace(f'{HUB_URL}/stayodds/', f'{STAYODDS_URL}/stayodds/')
    sc = sc.replace('**[uncharteditinerary.com](https://uncharteditinerary.com)**', '**[stayodds.com](https://stayodds.com)**')
    sc = sc.replace('Explore at https://uncharteditinerary.com', 'Explore at https://stayodds.com')
    sc = sc.replace('"uncharteditinerary.com"', '"stayodds.com"')
    sc = sc.replace('(uncharteditinerary.com)', '(stayodds.com)')
    sc_path.write_text(sc, encoding="utf-8")

    # 5. stayodds-feedback.js
    fb_path = assets_dir / "stayodds-feedback.js"
    fb = fb_path.read_text(encoding="utf-8")
    fb = fb.replace('|| "../assets/banners/"', '|| "/assets/banners/"')
    fb_path.write_text(fb, encoding="utf-8")


def write_compare_alias_redirect(out_dir: Path) -> None:
    """Keep https://stayodds.com/compare/?a=...&b=... working cleanly by redirecting to / with query preserved."""
    cmp_dir = out_dir / "compare"
    cmp_dir.mkdir(parents=True, exist_ok=True)
    (cmp_dir / "index.html").write_text(
        """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>StayOdds. — Luxury Hotel Comparison</title>
  <meta name="robots" content="noindex, follow" />
  <link rel="canonical" href="https://stayodds.com/" />
  <script>
    (function () {
      var target = "/" + (window.location.search || "") + (window.location.hash || "");
      window.location.replace(target);
    })();
  </script>
  <noscript><meta http-equiv="refresh" content="0;url=https://stayodds.com/" /></noscript>
</head>
<body>
  <p>Redirecting to <a href="https://stayodds.com/">StayOdds.</a>…</p>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_404_page(out_dir: Path) -> None:
    (out_dir / "404.html").write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Page Not Found — StayOdds.</title>
  <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg?v=2" />
  <link rel="stylesheet" href="/assets/styles.min.css?v=44" />
{STAYODDS_GA4_SNIPPET}
</head>
<body style="background:#f8f6f1;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;">
  <div style="max-width:520px;background:#fff;border:1px solid #e2e8f0;border-radius:20px;padding:32px;text-align:center;box-shadow:0 14px 36px rgba(15,23,42,0.08);">
    <div style="font-size:28px;font-weight:800;color:#071323;margin-bottom:8px;">StayOdds<span style="color:#ff5d22;">.</span></div>
    <h1 style="font-size:22px;margin:0 0 10px;color:#0f172a;">That hotel page wasn&rsquo;t found</h1>
    <p style="font-size:14.5px;color:#475569;margin:0 0 22px;line-height:1.6;">Compare all 832 verified luxury hotels, explore the interactive world map, or head back to The Uncharted Itinerary.</p>
    <div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:center;">
      <a class="btn btn-primary" href="/">Open StayOdds Compare</a>
      <a class="btn btn-outline" href="/hotels/">World Map</a>
      <a class="btn btn-outline" href="/brands/">Brand Leaderboard</a>
      <a class="btn btn-outline" href="{HUB_URL}/">The Uncharted Itinerary &nearr;</a>
    </div>
  </div>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_pages_workflow(out_dir: Path) -> None:
    wf_dir = out_dir / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    (wf_dir / "deploy-pages.yml").write_text(
        """name: Deploy StayOdds to GitHub Pages

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "stayodds-pages"
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Configure Pages
        uses: actions/configure-pages@v5
      - name: Upload site artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: "."

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
""",
        encoding="utf-8",
    )


def main() -> None:
    # Run repeatable brand & loyalty audit gate before assembling stayodds.com
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from audit_brands_and_loyalty import audit_hotels, format_audit_summary
    from build_stayodds_site import render_static_pages_from_directory

    dir_data = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))
    hotels = dir_data.get("hotels", [])
    errs, warns = audit_hotels(hotels)
    print(format_audit_summary(hotels, errs, warns))
    if errs:
        raise RuntimeError(f"Brand audit failed with {len(errs)} error(s); aborting stayodds.com bundle build.")

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    # 1. Domain config & static root files
    (DIST / "CNAME").write_text("stayodds.com\n", encoding="utf-8")
    (DIST / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {STAYODDS_URL}/sitemap.xml\n",
        encoding="utf-8",
    )
    if (ROOT / "ads.txt").exists():
        shutil.copy2(ROOT / "ads.txt", DIST / "ads.txt")
    if (ROOT / "favicon.ico?v=2").exists():
        shutil.copy2(ROOT / "favicon.ico?v=2", DIST / "favicon.ico?v=2")

    # 2. Copy assets/ and required data/ JSONs
    shutil.copytree(ROOT / "assets", DIST / "assets")
    (DIST / "data").mkdir(parents=True, exist_ok=True)
    for jf in ("stayodds-index.json", "stayodds-directory.json", "stayodds-visited.json", "price-snapshots.json"):
        src = ROOT / "data" / jf
        if src.exists():
            shutil.copy2(src, DIST / "data" / jf)

    # 3. Rewrite JS files inside .stayodds-dist/assets/ for stayodds.com
    rewrite_js_for_stayodds(DIST / "assets")

    # 4. Root comparator (/index.html) + /compare/ alias + /hotels/ + /brands/
    def load_template(rel: str) -> str:
        t_path = SRC_TEMPLATES / rel
        if not t_path.is_file():
            t_path = ROOT / rel
        return t_path.read_text(encoding="utf-8")

    (DIST / "index.html").write_text(
        rewrite_html_for_stayodds(load_template("compare/index.html"), "root_compare"),
        encoding="utf-8",
    )
    write_compare_alias_redirect(DIST)

    for section in ("hotels", "brands"):
        sec_dir = DIST / section
        sec_dir.mkdir(parents=True, exist_ok=True)
        (sec_dir / "index.html").write_text(
            rewrite_html_for_stayodds(load_template(f"{section}/index.html"), section),
            encoding="utf-8",
        )

    # 5 & 6. Render all 832 hotel SEO pages + 19 destination guides straight from directory JSON into DIST
    hotel_count, dest_slugs = render_static_pages_from_directory(hotels, DIST, write_root_sitemap=False)
    for h in hotels:
        pfile = DIST / "stayodds" / h["id"] / "index.html"
        if pfile.is_file():
            pfile.write_text(rewrite_html_for_stayodds(pfile.read_text(encoding="utf-8"), "detail"), encoding="utf-8")
    for dslug in dest_slugs:
        dfile = DIST / "destinations" / dslug / "index.html"
        if dfile.is_file():
            dfile.write_text(rewrite_html_for_stayodds(dfile.read_text(encoding="utf-8"), "destination"), encoding="utf-8")

    # 7. Dedicated stayodds.com sitemap.xml
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls: list[tuple[str, str, str]] = [
        (f"{STAYODDS_URL}/", "1.0", "daily"),
        (f"{STAYODDS_URL}/hotels/", "0.9", "weekly"),
        (f"{STAYODDS_URL}/brands/", "0.9", "weekly"),
    ]
    for dslug in dest_slugs:
        urls.append((f"{STAYODDS_URL}/destinations/{dslug}/", "0.9", "weekly"))
    for h in hotels:
        prio = "0.9" if h.get("tier") == "first_hand_verified" else "0.8"
        urls.append((f"{STAYODDS_URL}/stayodds/{h['id']}/", prio, "weekly"))

    sm_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, prio, freq in urls:
        sm_lines.append(
            f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        )
    sm_lines.append("</urlset>\n")
    (DIST / "sitemap.xml").write_text("\n".join(sm_lines), encoding="utf-8")

    # 8. 404.html + GitHub Pages deploy workflow for spinstorms/stayodds-live
    write_404_page(DIST)
    write_pages_workflow(DIST)

    print(
        f"BUILT STAYODDS.COM BUNDLE -> {DIST}\n"
        f"  Root comparator: /index.html + /compare/ alias\n"
        f"  Hub views: /hotels/ + /brands/\n"
        f"  Hotel SEO pages: {hotel_count} -> /stayodds/<slug>/\n"
        f"  Destination guides: {len(dest_slugs)} -> /destinations/<slug>/\n"
        f"  Sitemap URLs: {len(urls)} -> /sitemap.xml\n"
        f"  Tracking: GA4 {STAYODDS_GA4_ID} + Travelpayouts Drive NjA2MTYz + AdSense"
    )


if __name__ == "__main__":
    main()
