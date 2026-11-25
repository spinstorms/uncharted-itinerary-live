#!/usr/bin/env python3
"""Restaurants at our MICHELIN-listed hotels, with each restaurant's MICHELIN distinction.

For each hotel we tag with MICHELIN Keys, finds its MICHELIN Guide hotel page (from the public hotel sitemap), reads
the "Dine at the hotel" block (restaurants the Guide lists at that hotel) and each restaurant's distinction
(3/2/1 Stars, Bib Gourmand, Selected). Facts with a link to the Guide; nothing is scored from them.
Saved once per hotel in data/hotel-dining.json and only re-checked after 90 days (polite: one request at a time).
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import http_get, sb_all  # noqa: E402
from strict_names import same_hotel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "hotel-dining.json"
BASE = "https://guide.michelin.com"
UA = {"User-Agent": "StayOddsBot/1.0 (+https://stayodds.com; hotel restaurant facts with source links)"}
DIST = {"3 star": "3 MICHELIN Stars", "2 star": "2 MICHELIN Stars", "1 star": "1 MICHELIN Star",
        "bib gourmand": "Bib Gourmand", "plate": "MICHELIN Guide selected", "selected": "MICHELIN Guide selected"}
RANK = {"3 MICHELIN Stars": 0, "2 MICHELIN Stars": 1, "1 MICHELIN Star": 2, "Bib Gourmand": 3, "MICHELIN Guide selected": 4}


def get(url: str) -> str:
    time.sleep(1.0)
    code, page = http_get(url, headers=UA)
    return page if code == 200 else ""


def hotel_urls() -> list[str]:
    idx = get(f"{BASE}/sitemap.xml")
    maps = [u for u in re.findall(r"<loc>([^<]+)</loc>", idx) if "/sitemap/hotel/en/" in u]
    urls = []
    for m in maps:
        urls += [u for u in re.findall(r"<loc>([^<]+)</loc>", get(m)) if "/en/hotels-stays/" in u]
    return sorted(set(urls))


def slug_words(url: str) -> tuple[str, str]:
    parts = url.rstrip("/").split("/")
    city, slug = parts[-2], re.sub(r"-\d+$", "", parts[-1])
    return slug.replace("-", " "), city.replace("-", " ")


def main() -> int:
    keyed = set(json.loads((ROOT / "data" / "awards-michelin-2026.json").read_text(encoding="utf-8"))["hotels"])
    try:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        saved = {}
    today = date.today()
    fresh = {k for k, v in saved.items() if (today - date.fromisoformat(v.get("checked", "1970-01-01"))).days < 90}
    props = [p for p in sb_all("properties", "id,name,city,country") if p["id"] in keyed and p["id"] not in fresh]
    if not props:
        print("Dining: all hotels checked within 90 days")
        return 0
    urls = hotel_urls()
    print(f"Dining: {len(urls)} MICHELIN hotel pages in the sitemap; {len(props)} of our keyed hotels to check")
    cand = [(u, *slug_words(u)) for u in urls]
    done = 0
    for p in props:
        hits = [u for u, name, city in cand
                if same_hotel(p["name"], name, f'{p.get("city") or ""} {city}', p.get("country") or "")]
        if len(hits) != 1:
            saved[p["id"]] = {"checked": today.isoformat(), "michelinPage": None, "restaurants": [],
                              "note": "no single matching MICHELIN page" if not hits else f"{len(hits)} possible pages"}
            continue
        page = get(hits[0])
        rests = []
        for m in re.finditer(r'<a href="(/en/[^"]+/restaurant/[^"]+)"[^>]*data-event="block_the_hotel_restaurant"[^>]*data-restaurant-name="([^"]+)"', page):
            rurl, rname = BASE + m.group(1), html.unescape(m.group(2))
            if any(r["url"] == rurl for r in rests):
                continue
            rp = get(rurl)
            d = re.search(r"dLayer\['distinction'\]\s*=\s*'([^']*)'", rp)
            dist = DIST.get((d.group(1) if d else "").strip().lower())
            if dist:
                rests.append({"name": rname, "url": rurl, "distinction": dist})
        rests.sort(key=lambda r: RANK.get(r["distinction"], 9))
        saved[p["id"]] = {"checked": today.isoformat(), "michelinPage": hits[0], "restaurants": rests}
        done += 1
        if rests:
            print(f"  {p['id']}: " + "; ".join(f"{r['name']} ({r['distinction']})" for r in rests))
        if done % 25 == 0:
            OUT.write_text(json.dumps(dict(sorted(saved.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUT.write_text(json.dumps(dict(sorted(saved.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = sum(1 for v in saved.values() if v.get("restaurants"))
    print(f"Dining: {n} hotels have MICHELIN-listed restaurants on site")
    return 0


if __name__ == "__main__":
    sys.exit(main())
