#!/usr/bin/env python3
"""Fill missing hotel photos and map pins from Wikipedia / Wikidata / Wikimedia Commons (free, openly licensed).

Only for properties that still show the placeholder photo or have no map pin after the LiteAPI pass.
  * The Wikipedia article must be about the hotel: its title must carry the hotel's distinctive name words and its
    short description / Wikidata type must say hotel, resort, lodge, inn, ryokan, palace, castle, etc.
  * Photos are used only when Commons reports an open licence (CC0, public domain, CC BY, CC BY-SA); the licence and
    author are stored so the hotel page shows a credit line.
  * Pins come from the article's coordinates.
Visited (first-hand) properties are never touched.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import http_get, sb, sb_all  # noqa: E402
from complete_hotels import BRANDW, has_coords, needs_photo, words  # noqa: E402

UA = {"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; hotel directory photo credits)"}
WP = "https://en.wikipedia.org/w/api.php"
HOTELISH = re.compile(
    r"\b(hotel|resort|lodge|inn|ryokan|palace|castle|ch[aâ]teau|manor|villa|estate|camp|retreat|guest ?house|"
    r"hacienda|masseria|relais|spa|island)\b",
    re.I,
)
OPEN_LICENCE = re.compile(r"^(cc0|public domain|pd|cc[ -]by(-sa)?[ -]?\d|cc[ -]by(-sa)?$)", re.I)


def api(params: dict[str, Any]) -> dict[str, Any]:
    params = {**params, "format": "json", "formatversion": "2"}
    code, body = http_get(f"{WP}?{urllib.parse.urlencode(params)}", headers=UA)
    time.sleep(0.3)
    if code != 200:
        return {}
    try:
        return json.loads(body)
    except Exception:
        return {}


def strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def find_article(name: str, city: str) -> dict[str, Any] | None:
    ours = words(name)
    core = ours - BRANDW - words(city)
    for q in (f"{name} {city}".strip(), name):
        res = api({"action": "query", "list": "search", "srsearch": q, "srlimit": 6})
        for hit in (res.get("query") or {}).get("search") or []:
            title = hit.get("title", "")
            tw = words(re.sub(r"\(.*?\)", "", title))
            inter = len(ours & tw)
            if not inter or inter / len(ours | tw) < 0.6 and inter / max(1, len(ours)) < 0.85:
                continue
            if core and not (core & tw):
                continue
            page = api({
                "action": "query", "titles": title, "prop": "pageprops|coordinates|pageimages|description",
                "piprop": "name", "redirects": 1,
            })
            pages = (page.get("query") or {}).get("pages") or []
            if not pages:
                continue
            pg = pages[0]
            desc = (pg.get("description") or "") + " " + strip_tags(hit.get("snippet", ""))
            if not HOTELISH.search(desc) and not HOTELISH.search(title):
                continue
            return pg
    return None


def commons_image(filename: str) -> tuple[str, str, str, str] | None:
    """(thumb url, licence, artist, file page) for an openly licensed Commons file, else None."""
    if not filename:
        return None
    res = api({
        "action": "query", "titles": f"File:{filename}", "prop": "imageinfo",
        "iiprop": "url|extmetadata", "iiurlwidth": 1280,
    })
    pages = (res.get("query") or {}).get("pages") or []
    if not pages or not pages[0].get("imageinfo"):
        return None
    ii = pages[0]["imageinfo"][0]
    meta = ii.get("extmetadata") or {}
    lic = strip_tags((meta.get("LicenseShortName") or {}).get("value", ""))
    if not OPEN_LICENCE.match(lic):
        return None
    artist = strip_tags((meta.get("Artist") or {}).get("value", ""))[:80]
    return ii.get("thumburl") or ii.get("url"), lic, artist, ii.get("descriptionurl", "")


def main() -> int:
    props = sb_all("properties", "id,name,city,country,lat,lng,visited_by_founder,hero_image_url")
    todo = [
        p for p in props
        if not p.get("visited_by_founder")
        and (not has_coords(p) or needs_photo(p.get("hero_image_url")))
    ]
    print(f"Wikipedia / Commons: {len(todo)} properties missing a photo or pin")
    photos = pins = 0
    for p in todo:
        pg = find_article(p["name"], p.get("city") or "")
        if not pg:
            print(f"  no article: {p['id']}")
            continue
        patch: dict[str, Any] = {}
        if not has_coords(p) and pg.get("coordinates"):
            c = pg["coordinates"][0]
            patch.update({"lat": float(c["lat"]), "lng": float(c["lon"])})
            pins += 1
        if needs_photo(p.get("hero_image_url")):
            img = commons_image(pg.get("pageimage", ""))
            if img and img[0]:
                url, lic, artist, page = img
                patch.update({
                    "hero_image_url": url,
                    "image_license_source": f"wikimedia|{lic}|{artist.replace('|', '/')}|{page}",
                })
                photos += 1
        if patch:
            sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(p['id'])}", patch, {"Prefer": "return=minimal"})
            print(f"  {p['id']}: {pg.get('title')} -> {', '.join(patch)}")
    print(f"Wikipedia / Commons: added {photos} photos and {pins} map pins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
