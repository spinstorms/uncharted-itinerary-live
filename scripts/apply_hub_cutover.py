#!/usr/bin/env python3
"""
Stage / Apply the uncharteditinerary.com -> stayodds.com hub cutover.
RUN ONLY ON THE STAGING BRANCH (stage/stayodds-cutover) OR AFTER ADSENSE CLEARS!

What this script does:
1. Points StayOdds navigation links on The Uncharted Itinerary hub pages
   (/, /cameras/, /links/, /about/, /faq/, /contact/, /privacy/) directly to
   https://stayodds.com/, https://stayodds.com/hotels/, and https://stayodds.com/brands/.
2. Replaces legacy StayOdds pages on uncharteditinerary.com (/compare/, /hotels/,
   /brands/, /stayodds/<slug>/, /destinations/<slug>/) with fast, query-preserving
   redirects to https://stayodds.com/... that ALSO carry over any saved
   localStorage shortlist (stayodds_shortlist_v1) via ?import_saved=.
3. Updates uncharteditinerary.com/sitemap.xml to publish only the hub routes
   (avoiding duplicate StayOdds URLs across both sitemaps).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HUB_URL = "https://uncharteditinerary.com"
STAYODDS_URL = "https://stayodds.com"


def make_redirect_html(dest_url: str, title: str, carry_shortlist: bool = False) -> str:
    shortlist_js = ""
    if carry_shortlist:
        shortlist_js = """
      try {
        var raw = localStorage.getItem("stayodds_shortlist_v1");
        if (raw) {
          var arr = JSON.parse(raw);
          if (Array.isArray(arr) && arr.length) {
            var u = new URL(target);
            if (!u.searchParams.has("import_saved")) {
              u.searchParams.set("import_saved", arr.slice(0, 60).join(","));
            }
            target = u.toString();
          }
        }
      } catch (_) {}"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{title} — Moved to StayOdds.com</title>
  <meta name="robots" content="noindex, follow" />
  <link rel="canonical" href="{dest_url}" />
  <script>
    (function () {{
      var target = {json.dumps(dest_url)} + (window.location.search || "") + (window.location.hash || "");{shortlist_js}
      window.location.replace(target);
    }})();
  </script>
  <noscript><meta http-equiv="refresh" content="0;url={dest_url}" /></noscript>
</head>
<body>
  <p>StayOdds has moved to <a href="{dest_url}">{dest_url}</a>…</p>
</body>
</html>
"""


def update_hub_nav(path: Path) -> None:
    if not path.is_file():
        return
    txt = path.read_text(encoding="utf-8")
    # Root index.html relative links
    txt = txt.replace('href="compare/"', f'href="{STAYODDS_URL}/"')
    txt = txt.replace('href="./compare/"', f'href="{STAYODDS_URL}/"')
    txt = txt.replace('href="hotels/"', f'href="{STAYODDS_URL}/hotels/"')
    txt = txt.replace('href="./hotels/"', f'href="{STAYODDS_URL}/hotels/"')
    txt = txt.replace('href="brands/"', f'href="{STAYODDS_URL}/brands/"')
    txt = txt.replace('href="./brands/"', f'href="{STAYODDS_URL}/brands/"')
    # Subdirectory hub pages (../compare/, ../hotels/, ../brands/)
    txt = txt.replace('href="../compare/"', f'href="{STAYODDS_URL}/"')
    txt = txt.replace('href="../hotels/"', f'href="{STAYODDS_URL}/hotels/"')
    txt = txt.replace('href="../brands/"', f'href="{STAYODDS_URL}/brands/"')
    txt = re.sub(r'href="(?:\.\./)?compare/\?', f'href="{STAYODDS_URL}/?', txt)
    txt = re.sub(r'href="(?:\.\./)?stayodds/', f'href="{STAYODDS_URL}/stayodds/', txt)
    txt = re.sub(r'href="(?:\.\./)?destinations/', f'href="{STAYODDS_URL}/destinations/', txt)
    path.write_text(txt, encoding="utf-8")


def main() -> None:
    # 1. Update hub pages nav links
    hub_pages = [
        ROOT / "index.html",
        ROOT / "cameras" / "index.html",
        ROOT / "links" / "index.html",
        ROOT / "about" / "index.html",
        ROOT / "faq" / "index.html",
        ROOT / "contact" / "index.html",
        ROOT / "privacy" / "index.html",
    ]
    for p in hub_pages:
        update_hub_nav(p)

    # 2. Replace StayOdds routes with query + shortlist-preserving redirects
    (ROOT / "compare" / "index.html").write_text(
        make_redirect_html(f"{STAYODDS_URL}/", "StayOdds Compare", carry_shortlist=True),
        encoding="utf-8",
    )
    (ROOT / "hotels" / "index.html").write_text(
        make_redirect_html(f"{STAYODDS_URL}/hotels/", "StayOdds World Hotel Map", carry_shortlist=True),
        encoding="utf-8",
    )
    (ROOT / "brands" / "index.html").write_text(
        make_redirect_html(f"{STAYODDS_URL}/brands/", "StayOdds Brand Leaderboard", carry_shortlist=False),
        encoding="utf-8",
    )

    dir_hotels = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8")).get("hotels", [])
    for h in dir_hotels:
        slug = h["id"]
        pdir = ROOT / "stayodds" / slug
        if pdir.is_dir():
            (pdir / "index.html").write_text(
                make_redirect_html(f"{STAYODDS_URL}/stayodds/{slug}/", h["name"], carry_shortlist=False),
                encoding="utf-8",
            )

    dest_dir = ROOT / "destinations"
    if dest_dir.is_dir():
        for d in sorted(dest_dir.iterdir()):
            if d.is_dir() and (d / "index.html").is_file():
                (d / "index.html").write_text(
                    make_redirect_html(f"{STAYODDS_URL}/destinations/{d.name}/", f"StayOdds {d.name.title()} Guide", carry_shortlist=False),
                    encoding="utf-8",
                )

    # 3. Clean hub-only sitemap.xml for uncharteditinerary.com
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    hub_urls = [
        (f"{HUB_URL}/", "daily", "1.0"),
        (f"{HUB_URL}/cameras/", "monthly", "0.85"),
        (f"{HUB_URL}/links/", "weekly", "0.85"),
        (f"{HUB_URL}/about/", "monthly", "0.85"),
        (f"{HUB_URL}/faq/", "monthly", "0.85"),
        (f"{HUB_URL}/contact/", "monthly", "0.80"),
        (f"{HUB_URL}/privacy/", "monthly", "0.60"),
    ]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, prio in hub_urls:
        sm.append(f"  <url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>")
    sm.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
    print(f"Applied staged hub cutover: {len(hub_pages)} hub pages updated, {len(dir_hotels)} hotel redirects + 19 destination redirects written, hub-only sitemap.xml ({len(hub_urls)} URLs).")


if __name__ == "__main__":
    main()
