#!/usr/bin/env python3
"""Additive award + review enrichment for StayOdds (never deletes anything).

Subcommands (run by .github/workflows/add-award-hotels.yml with the repo secrets):

  awards      upsert the 2026 World's 50 Best rank for every ranked hotel that is missing its tag, and the 2026
              MICHELIN Keys listed in data/awards-michelin-2026.json
  youtube     find real YouTube review videos (public search page, no API key), verify each through YouTube oEmbed
              and upsert them into youtube_reviews
  editorial   find The Luxury Travel Expert review pages, read the published "Overall experience: x/10" score and
              upsert it into editorial_ratings (feeds the StayOdds critic score)

Integrity rules: only data a source actually published is stored. A video must come back HTTP 200 from oEmbed and
its title must contain the hotel's distinctive name words. A score is only stored if it is printed on the page.
Founder videos and known spam channels are excluded. Missing data stays missing.

Options:  --only slug1,slug2   limit to those properties
          --missing            (youtube/editorial) only hotels that currently have none
          --limit N            stop after N hotels (testing)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_awards import W50B_2026_MISSING_TAGS, W50B_2026_NEW  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
W50B_TOP50_URL = "https://www.the50.com/hotels/best-in-the-world/list/1-50"
W50B_51_100_URL = "https://www.the50.com/stories/News/the-50-best-hotels-2026-the-51-100-list.html"
MICHELIN_GLOBAL_URL = "https://guide.michelin.com/en/article/travel/all-the-key-hotels-in-the-world-michelin-guide"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

BLOCKED_YT_AUTHORS = {
    "the uncharted itinerary", "hotel review world", "triptalestoday", "six star hotels", "hotel critic",
    "hotel guide", "world hotel guide", "five star finds", "luxury hotels", "via privata",
}
STOP = {
    "the", "hotel", "hotels", "resort", "spa", "a", "an", "and", "at", "in", "of", "by", "de", "di", "du", "la", "le",
    "el", "collection", "belmond", "regent", "luxury", "grand", "palace", "residences", "villas", "villa",
}
REVIEW_WORDS = ("review", "tour", "stay", "suite", "room", "worth", "honest", "vlog", "first look", "experience")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sb(method: str, path: str, body: Any = None, extra: dict[str, str] | None = None) -> Any:
    url = os.environ["SUPABASE_URL"].rstrip("/") + path
    key = os.environ["SUPABASE_SECRET_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers.update(extra or {})
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else None


def sb_all(table: str, select: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    off = 0
    while True:
        chunk = sb("GET", f"/rest/v1/{table}?select={select}&limit=1000&offset={off}") or []
        out += chunk
        if len(chunk) < 1000:
            return out
        off += 1000


def upsert(table: str, rows: list[dict[str, Any]], conflict: str) -> int:
    for i in range(0, len(rows), 100):
        sb(
            "POST",
            f"/rest/v1/{table}?on_conflict={urllib.parse.quote(conflict)}",
            rows[i : i + 100],
            {"Prefer": "resolution=merge-duplicates,return=minimal"},
        )
    return len(rows)


def http_get(url: str, timeout: int = 25, headers: dict[str, str] | None = None) -> tuple[int, str]:
    h = {"User-Agent": UA, "Accept-Language": "en-GB,en;q=0.9", "Cookie": "CONSENT=YES+cb; SOCS=CAI"}
    h.update(headers or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return 0, ""


def norm_words(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower().replace("&", " and ")
    return [w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w]


def distinctive(name: str) -> set[str]:
    return {w for w in norm_words(name) if w not in STOP and len(w) > 1}


# --------------------------------------------------------------------------- awards
BRAND_FIXES = {"capella-lodge": "Luxury Lodges of Australia"}  # not part of Capella Hotels


def run_awards(props: dict[str, dict[str, Any]], only: set[str] | None) -> None:
    for pid, brand in BRAND_FIXES.items():
        if pid in props:
            sb("PATCH", f"/rest/v1/properties?id=eq.{pid}", {"brand": brand}, {"Prefer": "return=minimal"})
    ep = ROOT / "data" / "editorial-manual.json"
    if ep.exists():
        manual = [
            {**r, "verified_at": now_iso()}
            for r in json.loads(ep.read_text(encoding="utf-8")).get("ratings", [])
            if r.get("property_id") in props
        ]
        if manual:
            print(f"Editorial (hand-checked): upserting {len(manual)}")
            upsert("editorial_ratings", manual, "property_id,source_name,source_url")
    rows: list[dict[str, Any]] = []
    ranks = {**W50B_2026_MISSING_TAGS, **W50B_2026_NEW}
    for pid, rank in ranks.items():
        if only and pid not in only:
            continue
        if pid not in props:
            print(f"  skip rank {rank}: {pid} is not in Supabase yet")
            continue
        norm = 98 if rank <= 10 else 96 if rank <= 25 else 94 if rank <= 50 else 91
        rows.append(
            {
                "property_id": pid,
                "award_body": "The World's 50 Best Hotels",
                "label": f"No. {rank} in the World (2026)",
                "award_year": "2026",
                "normalized_100": norm,
                "source_url": W50B_TOP50_URL if rank <= 50 else W50B_51_100_URL,
                "verified_at": now_iso(),
            }
        )
    print(f"World's 50 Best: upserting {len(rows)} rank tags")
    upsert("official_awards", rows, "property_id,award_body,label")

    mp = ROOT / "data" / "awards-michelin-2026.json"
    if mp.exists():
        data = json.loads(mp.read_text(encoding="utf-8"))
        label = {3: "3 MICHELIN Keys", 2: "2 MICHELIN Keys", 1: "1 MICHELIN Key"}
        norm = {3: 98, 2: 92, 1: 86}
        mrows = []
        have_michelin = {}
        for r in sb_all("official_awards", "property_id,award_body,label"):
            if r["award_body"] == "MICHELIN Guide":
                have_michelin.setdefault(r["property_id"], set()).add(r["label"])
        for pid, rec in data.get("hotels", {}).items():
            if only and pid not in only:
                continue
            if pid not in props:
                print(f"  skip Michelin: {pid} is not in Supabase yet")
                continue
            keys = int(rec["keys"])
            existing_labels = have_michelin.get(pid, set())
            if existing_labels and label[keys] not in existing_labels:
                if not rec.get("replace"):
                    print(f"  CONFLICT {pid}: site has {sorted(existing_labels)}, list says {label[keys]} - left unchanged")
                    continue
                # an official 2026 country list supersedes an older tag
                print(f"  UPDATE {pid}: {sorted(existing_labels)} -> {label[keys]}")
                sb(
                    "DELETE",
                    f"/rest/v1/official_awards?property_id=eq.{urllib.parse.quote(pid)}&award_body=eq.{urllib.parse.quote('MICHELIN Guide')}",
                    None,
                    {"Prefer": "return=minimal"},
                )
            mrows.append(
                {
                    "property_id": pid,
                    "award_body": "MICHELIN Guide",
                    "label": label[keys],
                    "award_year": "2026",
                    "normalized_100": norm[keys],
                    "source_url": rec.get("url") or MICHELIN_GLOBAL_URL,
                    "verified_at": now_iso(),
                }
            )
        print(f"MICHELIN Keys: upserting {len(mrows)} tags")
        upsert("official_awards", mrows, "property_id,award_body,label")


# --------------------------------------------------------------------------- youtube
def yt_search(query: str) -> list[dict[str, Any]]:
    code, html = http_get("https://www.youtube.com/results?hl=en&gl=GB&search_query=" + urllib.parse.quote(query))
    if code != 200:
        return []
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except Exception:
        return []
    found: list[dict[str, Any]] = []

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            vr = o.get("videoRenderer")
            if isinstance(vr, dict) and vr.get("videoId"):
                title = "".join(r.get("text", "") for r in (vr.get("title") or {}).get("runs", []))
                owner = "".join(r.get("text", "") for r in (vr.get("ownerText") or {}).get("runs", []))
                length = (vr.get("lengthText") or {}).get("simpleText", "")
                found.append({"id": vr["videoId"], "title": title, "owner": owner, "length": length})
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(data)
    return found


def length_seconds(s: str) -> int:
    if not s:
        return 0
    parts = [int(p) for p in s.split(":") if p.isdigit()]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def oembed(vid: str) -> dict[str, Any] | None:
    url = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={vid}")
    code, body = http_get(url, timeout=15)
    if code != 200:
        return None
    try:
        return json.loads(body)
    except Exception:
        return None


def run_youtube(props: dict[str, dict[str, Any]], only: set[str] | None, missing: bool, limit: int | None) -> None:
    existing = sb_all("youtube_reviews", "property_id,source_url")
    have = {r["property_id"] for r in existing}
    founder: set[str] = set()
    for r in sb("GET", "/rest/v1/first_hand_reviews?select=youtube_video_id,shorts&limit=1000") or []:
        if r.get("youtube_video_id"):
            founder.add(r["youtube_video_id"])
        for sh in r.get("shorts") or []:
            if isinstance(sh, dict) and sh.get("videoId"):
                founder.add(sh["videoId"])
    targets = [p for p in props.values() if (not only or p["id"] in only) and not (missing and p["id"] in have)]
    if limit:
        targets = targets[:limit]
    print(f"YouTube: searching for {len(targets)} hotels")
    rows: list[dict[str, Any]] = []
    for i, p in enumerate(targets, 1):
        need = distinctive(p["name"])
        if not need:
            continue
        kept = 0
        for query in (f"{p['name']} hotel review", f"{p['name']} {p.get('city') or ''} room tour"):
            for v in yt_search(query):
                if kept >= 3 or v["id"] in founder:
                    continue
                words = set(norm_words(v["title"]))
                if len(need & words) < max(1, int(len(need) * 0.75 + 0.5)):
                    continue
                if not any(w in v["title"].lower() for w in REVIEW_WORDS):
                    continue
                if length_seconds(v["length"]) < 150:
                    continue
                info = oembed(v["id"])
                if not info:
                    continue
                author = str(info.get("author_name") or v["owner"]).strip()
                if not author or any(b in author.lower() for b in BLOCKED_YT_AUTHORS):
                    continue
                url = f"https://www.youtube.com/watch?v={v['id']}"
                if any(r["property_id"] == p["id"] and r["source_url"] == url for r in rows):
                    continue
                title = str(info.get("title") or v["title"]).strip()
                rows.append(
                    {
                        "property_id": p["id"],
                        "creator_name": author,
                        "source_url": url,
                        "sentiment": "Review",
                        "takeaway": f'Video: "{title}"'[:260],
                        "published_at": None,
                        "verified_at": now_iso(),
                    }
                )
                kept += 1
            time.sleep(1.0)
            if kept >= 3:
                break
        if i % 25 == 0:
            print(f"  {i}/{len(targets)} searched, {len(rows)} verified videos so far", flush=True)
    print(f"YouTube: upserting {len(rows)} verified videos across {len({r['property_id'] for r in rows})} hotels")
    upsert("youtube_reviews", rows, "property_id,source_url")


# --------------------------------------------------------------------------- editorial (The Luxury Travel Expert)
LTE = "https://theluxurytravelexpert.com"


def run_editorial(props: dict[str, dict[str, Any]], only: set[str] | None, missing: bool, limit: int | None) -> None:
    have = {r["property_id"] for r in sb_all("editorial_ratings", "property_id")}
    targets = [p for p in props.values() if (not only or p["id"] in only) and not (missing and p["id"] in have)]
    if limit:
        targets = targets[:limit]
    print(f"Editorial: checking {len(targets)} hotels on The Luxury Travel Expert")
    rows: list[dict[str, Any]] = []
    stats = {"searched": 0, "with_candidates": 0, "name_match": 0, "no_score": 0}
    for i, p in enumerate(targets, 1):
        need = distinctive(p["name"])
        if not need:
            continue
        urls = []
        code, body = http_get(f"{LTE}/wp-json/wp/v2/posts?per_page=10&_fields=link&search={urllib.parse.quote(p['name'])}")
        time.sleep(1.0)
        if code == 200:
            try:
                urls = [x["link"] for x in json.loads(body) if "review" in x.get("link", "")]
            except Exception:
                urls = []
        if not urls:
            code, html = http_get(f"{LTE}/?s={urllib.parse.quote(p['name'])}")
            time.sleep(1.0)
            for u in re.findall(r'href="((?:https://theluxurytravelexpert\.com)?/[^"#?]*review-[^"#?]*)"', html):
                u = u if u.startswith("http") else LTE + u
                if u not in urls and "/amp" not in u:
                    urls.append(u)
        stats["searched"] += 1
        stats["with_candidates"] += 1 if urls else 0
        for u in urls[:4]:
            slug_words = set(norm_words(u.rstrip("/").rsplit("/", 1)[-1]))
            if len(need & slug_words) < max(1, int(len(need) * 0.75 + 0.5)):
                continue
            stats["name_match"] += 1
            c2, page = http_get(u)
            time.sleep(1.0)
            if c2 != 200:
                continue
            m = re.search(r"Overall experience:[^0-9]{0,60}(\d{1,2}(?:\.\d)?)\s*/\s*10", re.sub(r"<[^>]+>", " ", page))
            if not m:
                stats["no_score"] += 1
                continue
            score = float(m.group(1))
            if not 0 < score <= 10:
                continue
            t = re.search(r"<title>(.*?)</title>", page, re.S)
            title = re.sub(r"\s*[-–|]\s*(The\s+)?Luxury Travel Expert.*$", "", (t.group(1) if t else "").strip())
            title = re.sub(r"&#8211;|&amp;", lambda mm: "-" if mm.group(0) == "&#8211;" else "&", title).strip()
            d = re.search(r'"datePublished":"(\d{4}-\d{2}-\d{2})', page)
            rows.append(
                {
                    "property_id": p["id"],
                    "source_name": "The Luxury Travel Expert",
                    "source_url": u,
                    "raw_score": f"{score:g}/10",
                    "normalized_100": int(round(score * 10)),
                    "takeaway": (f"First-hand hotel verdict ({score:g}/10): {title}" if title else f"First-hand hotel verdict ({score:g}/10).")[:260],
                    "published_at": d.group(1) if d else None,
                    "verified_at": now_iso(),
                }
            )
            break
        if i % 25 == 0:
            print(f"  {i}/{len(targets)} checked, {len(rows)} scored reviews so far", flush=True)
    print(f"Editorial diagnostics: {stats}")
    print(f"Editorial: upserting {len(rows)} real published scores")
    upsert("editorial_ratings", rows, "property_id,source_name,source_url")


# --------------------------------------------------------------------------- coordinates (OpenStreetMap)
_TOWN_FILE = Path(__file__).resolve().parent.parent / "data" / "town-points.json"
try:  # town centres already looked up on earlier runs (OpenStreetMap allows ~1 lookup a second)
    _CITY_CACHE: dict[str, tuple[float, float] | None] = {
        k: (tuple(v) if v else None) for k, v in json.loads(_TOWN_FILE.read_text(encoding="utf-8")).items()
    }
except Exception:
    _CITY_CACHE = {}
_CITY_NEW = False


def _save_towns() -> None:
    if _CITY_NEW:
        _TOWN_FILE.write_text(json.dumps({k: v for k, v in sorted(_CITY_CACHE.items()) if v}, indent=0, ensure_ascii=False) + "\n", encoding="utf-8")


import atexit  # noqa: E402

atexit.register(_save_towns)
NOMINATIM_UA = {"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; map pins for hotel directory)"}


def city_point(city: str, country: str) -> tuple[float, float] | None:
    """Centre of the hotel's stated town/area (OpenStreetMap), used to sanity-check every pin."""
    q = ", ".join(x for x in (str(city or "").strip(), str(country or "").strip()) if x)
    if not q:
        return None
    if q in _CITY_CACHE:
        return _CITY_CACHE[q]
    # only accept a real town/city/region result in the hotel's country; vague or ambiguous names give no point
    pt = None
    for extra in ({"featureType": "settlement"}, {}):
        code, body = http_get(
            "https://nominatim.openstreetmap.org/search?"
            + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": "3", "accept-language": "en", "addressdetails": "1", **extra}),
            headers=NOMINATIM_UA,
        )
        time.sleep(1.1)
        try:
            res = json.loads(body) if code == 200 else []
        except Exception:
            res = []
        want_country = str(country or "").strip().lower()
        for r0 in res:
            ctry = str((r0.get("address") or {}).get("country") or "").lower()
            if want_country and ctry and want_country not in ctry and ctry not in want_country:
                continue
            if r0.get("category") in ("natural", "waterway") or r0.get("addresstype") in ("ocean", "sea", "reef", "water"):
                continue
            pt = (float(r0["lat"]), float(r0["lon"]))
            break
        if pt:
            break
    global _CITY_NEW
    _CITY_CACHE[q] = pt
    _CITY_NEW = True
    return pt


def km_between(a: tuple[float, float], b: tuple[float, float]) -> float:
    import math

    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = math.radians(b[0] - a[0]), math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def name_ok(hotel_name: str, candidate_name: str) -> bool:
    """The words that make this hotel unique (not just its brand) must be in the candidate's name."""
    from complete_hotels import BRANDW

    need = distinctive(hotel_name)
    core = need - BRANDW - {"lodge"}
    got = set(norm_words(candidate_name))
    target = core or need
    if not target:
        return False
    hit = len(target & got)
    return hit >= max(1, -(-len(target) * 4 // 5))  # at least 80% of the distinctive words


def run_pincheck(props: dict[str, dict[str, Any]], only: set[str] | None) -> None:
    """Clear pins that sit far from the hotel's stated town (they are re-found from a reliable source next)."""
    addr_path = ROOT / "data" / "hotel-addresses.json"
    sourced = set(json.loads(addr_path.read_text(encoding="utf-8")).get("hotels", {})) if addr_path.exists() else set()
    tp = ROOT / "data" / "pin-trusted.json"
    if tp.exists():
        sourced |= set(json.loads(tp.read_text(encoding="utf-8")))  # same-name LiteAPI pins in vaguely named areas
    rows = sb_all("properties", "id,name,city,country,lat,lng,visited_by_founder")
    cleared = checked = 0
    for r in rows:
        if only and r["id"] not in only:
            continue
        if r["id"] in sourced or not isinstance(r.get("lat"), (int, float)) or not isinstance(r.get("lng"), (int, float)):
            continue
        cp = city_point(r.get("city") or "", r.get("country") or "")
        if not cp:
            continue
        checked += 1
        d = km_between((r["lat"], r["lng"]), cp)
        if d > 150:
            print(f"  far pin cleared: {r['id']} ({r['name']}) is {d:.0f} km from {r.get('city')}, {r.get('country')}")
            sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(r['id'])}", {"lat": None, "lng": None}, {"Prefer": "return=minimal"})
            cleared += 1
    print(f"Pin check: {checked} pins compared with their town, {cleared} cleared for re-locating")
def run_coords(props: dict[str, dict[str, Any]], only: set[str] | None) -> None:
    """Fill missing lat/lng from OpenStreetMap Nominatim (free, 1 request/second).

    A result is kept only if it is in the hotel's country and its OSM name contains the hotel's distinctive words.
    """
    from catalog_awards import AWARD_HOTEL_ADDITIONS
    from catalog_critics import CRITIC_HOTEL_ADDITIONS
    from catalog_michelin import MICHELIN_HOTEL_ADDITIONS

    iso = {t[0]: t[4].lower() for t in list(AWARD_HOTEL_ADDITIONS) + list(MICHELIN_HOTEL_ADDITIONS) + list(CRITIC_HOTEL_ADDITIONS)}
    addr_path = ROOT / "data" / "hotel-addresses.json"
    addresses = json.loads(addr_path.read_text(encoding="utf-8")).get("hotels", {}) if addr_path.exists() else {}
    rows = sb_all("properties", "id,name,city,country,lat,lng,google_place_id")
    missing = [
        r for r in rows
        if (not only or r["id"] in only)
        and not (isinstance(r.get("lat"), (int, float)) and isinstance(r.get("lng"), (int, float)) and (r["lat"] or r["lng"]))
    ]
    print(f"Coordinates: {len(missing)} hotels without a map pin")
    fixed = 0
    for r in missing:
        need = distinctive(r["name"])
        cc = iso.get(r["id"], "")
        found = None
        a = addresses.get(r["id"])
        if a and isinstance(a.get("lat"), (int, float)):
            found = (float(a["lat"]), float(a["lng"]), f"source page: {a.get('source', '')[:70]}")
        elif a and "guide.michelin.com" in str(a.get("source") or ""):
            pt = michelin_page_coords(a["source"])
            cp = city_point(r.get("city") or "", r.get("country") or "")
            if pt and (not cp or km_between(pt, cp) <= 60):
                found = (pt[0], pt[1], f"MICHELIN page: {a['source'][:70]}")
        for q in ((f"{r['name']}, {r.get('city') or ''}", r["name"]) if not found else ()):
            params = {"q": q, "format": "jsonv2", "limit": "5", "addressdetails": "1", "accept-language": "en"}
            if cc:
                params["countrycodes"] = cc
            code, body = http_get(
                "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params),
                headers={"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; map pins for hotel directory)"},
            )
            time.sleep(1.1)
            if code != 200:
                continue
            try:
                results = json.loads(body)
            except Exception:
                continue
            for res in results:
                if not name_ok(r["name"], res.get("name") or res.get("display_name", "").split(",")[0]):
                    continue
                if cc and (res.get("address") or {}).get("country_code", "") != cc:
                    continue
                pt = (float(res["lat"]), float(res["lon"]))
                cp = city_point(r.get("city") or "", r.get("country") or "")
                if cp and km_between(pt, cp) > 60:
                    continue
                found = (pt[0], pt[1], res.get("display_name", "")[:90])
                break
            if found:
                break
        if not found and r["id"] in addresses:
            a2 = addresses[r["id"]]
            params = {"q": a2["address"], "format": "jsonv2", "limit": "1", "accept-language": "en"}
            if cc:
                params["countrycodes"] = cc
            code, body = http_get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params),
                                  headers={"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; map pins for hotel directory)"})
            time.sleep(1.1)
            try:
                res = json.loads(body) if code == 200 else []
            except Exception:
                res = []
            if res:
                found = (float(res[0]["lat"]), float(res[0]["lon"]), f"address: {a2['address'][:70]}")
        if not found:
            # Photon (OpenStreetMap data, fuzzier name search)
            pr = {"q": f"{r['name']} {r.get('city') or ''}".strip(), "limit": "8", "lang": "en"}
            code, body = http_get("https://photon.komoot.io/api/?" + urllib.parse.urlencode(pr),
                                  headers={"User-Agent": "StayOddsBot/1.0 (https://stayodds.com)"})
            time.sleep(1.0)
            if code == 200:
                try:
                    feats = json.loads(body).get("features") or []
                except Exception:
                    feats = []
                for f in feats:
                    pp = f.get("properties") or {}
                    if cc and str(pp.get("countrycode") or "").lower() != cc:
                        continue
                    if not name_ok(r["name"], pp.get("name") or ""):
                        continue
                    lng_, lat_ = f["geometry"]["coordinates"][:2]
                    cp = city_point(r.get("city") or "", r.get("country") or "")
                    if cp and km_between((float(lat_), float(lng_)), cp) > 60:
                        continue
                    found = (float(lat_), float(lng_), f"photon: {pp.get('name')}, {pp.get('city') or ''}")
                    break
        if not found and r["id"] in addresses:
            # street address taken from the hotel's own website (data/hotel-addresses.json), geocoded with OSM
            a = addresses[r["id"]]
            params = {"q": a["address"], "format": "jsonv2", "limit": "1", "accept-language": "en"}
            if cc:
                params["countrycodes"] = cc
            code, body = http_get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params),
                                  headers={"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; map pins for hotel directory)"})
            time.sleep(1.1)
            try:
                res = json.loads(body) if code == 200 else []
            except Exception:
                res = []
            if res:
                found = (float(res[0]["lat"]), float(res[0]["lon"]), f"address: {a['address'][:70]}")
        if not found and not r.get("google_place_id"):
            print(f"  {r['id']} has no Google place id")
        if not found and r.get("google_place_id") and os.environ.get("GOOGLE_PLACES_API_KEY"):
            # the hotel's own Google Maps listing (already matched to this hotel by place id); name must still match
            try:
                req = urllib.request.Request(
                    f"https://places.googleapis.com/v1/places/{urllib.parse.quote(r['google_place_id'])}",
                    headers={"X-Goog-Api-Key": os.environ["GOOGLE_PLACES_API_KEY"],
                             "X-Goog-FieldMask": "displayName,location", "Accept-Language": "en"})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    gp = json.loads(resp.read().decode("utf-8"))
                gname = (gp.get("displayName") or {}).get("text", "")
                loc = gp.get("location") or {}
                if not (loc and name_ok(r["name"], gname)):
                    print(f"  google listing for {r['id']} is '{gname}' - name does not match, not used")
                if loc and name_ok(r["name"], gname):
                    pt = (float(loc["latitude"]), float(loc["longitude"]))
                    cp = city_point(r.get("city") or "", r.get("country") or "")
                    if not cp or km_between(pt, cp) <= 60:
                        found = (pt[0], pt[1], f"Google Maps listing: {gname}")
            except Exception as e:  # noqa: BLE001
                print(f"  google listing lookup failed for {r['id']}: {e}")
        if found:
            patch = {"lat": found[0], "lng": found[1]}
            if a and a.get("city"):
                patch["city"] = a["city"]
            sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(r['id'])}", patch, {"Prefer": "return=minimal"})
            fixed += 1
            print(f"  pin {r['id']}: {found[0]:.4f},{found[1]:.4f} ({found[2]})")
        else:
            print(f"  no confident match: {r['id']} ({r['name']})")
    print(f"Coordinates: added {fixed} map pins")


def michelin_page_coords(url: str) -> tuple[float, float] | None:
    """The MICHELIN Guide hotel page carries the hotel's own map position (JSON-LD geo / map data)."""
    code, body = http_get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; StayOddsBot/1.0; +https://stayodds.com)",
                                        "Accept-Language": "en"})
    time.sleep(1.0)
    if code != 200 or not body:
        return None
    text = body if isinstance(body, str) else body.decode("utf-8", "replace")
    pats = [
        (r'"latitude"\s*:\s*"?(-?\d{1,3}\.\d+)', r'"longitude"\s*:\s*"?(-?\d{1,3}\.\d+)'),
        (r'data-lat="(-?\d{1,3}\.\d+)"', r'data-lng="(-?\d{1,3}\.\d+)"'),
        (r'\blat(?:itude)?["\']?\s*[:=]\s*["\']?(-?\d{1,3}\.\d{3,})', r'\b(?:lng|lon|longitude)["\']?\s*[:=]\s*["\']?(-?\d{1,3}\.\d{3,})'),
    ]
    for la, lo in pats:
        m1, m2 = re.search(la, text), re.search(lo, text)
        if m1 and m2:
            lat, lng = float(m1.group(1)), float(m2.group(1))
            if -90 <= lat <= 90 and -180 <= lng <= 180 and (lat or lng):
                return lat, lng
    return None


def guestcheck() -> None:
    """Remove LiteAPI guest scores based on fewer than 20 reviews (one 10/10 review is not a 100% guest score)."""
    rows = sb_all("licensed_guest_scores", "property_id,partner_source,review_count,rating")
    bad = [r for r in rows if r.get("partner_source") == "nuitee_connect"
           and (r.get("review_count") is None or int(r["review_count"]) < 20)]
    for r in bad:
        sb("DELETE", f"/rest/v1/licensed_guest_scores?property_id=eq.{urllib.parse.quote(r['property_id'])}"
                     f"&partner_source=eq.nuitee_connect", None, {"Prefer": "return=minimal"})
        print(f"  removed thin guest score: {r['property_id']} ({r.get('rating')} from {r.get('review_count')} reviews)")
    print(f"Guest scores: removed {len(bad)} based on fewer than 20 reviews")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"awards", "youtube", "editorial", "coords", "pincheck", "guestcheck"}:
        print(__doc__)
        return 2
    cmd = argv[0]
    only = None
    limit = None
    for i, a in enumerate(argv):
        if a == "--only" and i + 1 < len(argv):
            only = {s.strip() for s in argv[i + 1].split(",") if s.strip()}
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1])
    missing = "--missing" in argv
    if "--award-set" in argv:  # every hotel added or re-tagged from the 2026 award lists
        from catalog_awards import AWARD_HOTEL_ADDITIONS

        only = {a[0] for a in AWARD_HOTEL_ADDITIONS} | set(W50B_2026_MISSING_TAGS)
        mp = ROOT / "data" / "awards-michelin-2026.json"
        if mp.exists():
            only |= set(json.loads(mp.read_text(encoding="utf-8")).get("hotels", {}))
    props = {p["id"]: p for p in sb_all("properties", "id,name,city,country")}
    print(f"{len(props)} properties in Supabase")
    if cmd == "awards":
        run_awards(props, only)
    elif cmd == "coords":
        run_coords(props, only)
    elif cmd == "pincheck":
        run_pincheck(props, only)
    elif cmd == "guestcheck":
        guestcheck()
    elif cmd == "youtube":
        run_youtube(props, only, missing, limit)
    else:
        run_editorial(props, only, missing, limit)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
