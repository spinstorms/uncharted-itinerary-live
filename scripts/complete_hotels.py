#!/usr/bin/env python3
"""Bring every StayOdds property up to the same data standard (additive, never deletes).

For every property in Supabase:
  1. No LiteAPI hotel id  -> search LiteAPI by coordinates (when known) and by name within the country; accept only a
                             strong name match (and, with coordinates, within 3 km). Never reuse an id another
                             property already has.
  2. Has a LiteAPI id     -> fill whatever is still missing from the licensed LiteAPI hotel record:
                             photo (when the card shows the placeholder), map pin, verified guest score and the
                             guest-review standout / watch-out facts.

Visited (first-hand) properties are never touched: their photos and notes come from the founder's own stays.
Everything written comes from the LiteAPI record itself; nothing is estimated.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY, NUITEE_API_KEY
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import unicodedata
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import city_point, km_between, name_ok, sb, sb_all, upsert  # noqa: E402
from enrich_missing_hotels import COUNTRY_TO_ISO2, strip_accents  # noqa: E402
from sync_250_hotels import extract_key_facts_from_nuitee, nuitee_get  # noqa: E402

PLACEHOLDER = "placeholders/default-stayodds"
# hosts that refuse hot-linking; the site build treats these as "no photo"
BLOCKED_IMG = ("www.fourseasons.com", "www.lungarnocollection.com")


def needs_photo(url: Any) -> bool:
    u = str(url or "")
    return not u or PLACEHOLDER in u or any(b in u for b in BLOCKED_IMG)


def pick_photo(d: dict[str, Any]) -> str:
    urls = [str(d.get("main_photo") or "")]
    for im in d.get("hotelImages") or []:
        if isinstance(im, dict):
            urls += [str(im.get("urlHd") or ""), str(im.get("url") or "")]
    for u in urls:
        if u.startswith("http") and not any(b in u for b in BLOCKED_IMG):
            return u
    return ""
STOP = {
    "the", "hotel", "hotels", "resort", "resorts", "spa", "a", "an", "and", "at", "in", "of", "by", "de", "di", "du",
    "la", "le", "el", "les", "collection", "luxury", "residences", "auberge", "belmond", "dorchester", "firmdale",
    "rocco", "forte", "a", "&", "hôtel", "boutique", "lodge" ,
}
MAX_KM = 3.0
# brand and generic words: sharing only these does not make two hotels the same
BRANDW = {
    "four", "seasons", "mandarin", "oriental", "rosewood", "aman", "ritz", "carlton", "park", "hyatt", "peninsula",
    "st", "regis", "waldorf", "astoria", "bulgari", "capella", "six", "senses", "banyan", "tree", "one", "only",
    "raffles", "fairmont", "kempinski", "langham", "intercontinental", "jw", "marriott", "sofitel", "legend",
    "anantara", "montage", "pendry", "alila", "cheval", "blanc", "airelles", "jumeirah", "shangri", "conrad",
    "westin", "sheraton", "hilton", "palace", "grand", "royal", "villa", "villas", "house", "inn", "suites",
    "retreat", "estate", "camp", "island", "beach", "reserve", "editions", "edition", "orient", "express",
    "kimpton", "nobu", "w", "the", "regent", "oberoi", "taj", "leela", "como", "zannier", "soneva", "belmond",
}
EXTRA_ISO = {"macau": "MO", "virgin islands (us)": "VI", "st barts": "BL"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def words(s: str) -> set[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("bvlgari", "bulgari").replace("&", " ")
    return {w for w in re.sub(r"[^a-z0-9]+", " ", s).split() if w and w not in STOP and len(w) > 1}


def km(a: float, b: float, c: float, d: float) -> float:
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = math.radians(c - a), math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


def similarity(ours: set[str], theirs: set[str]) -> float:
    if not ours or not theirs:
        return 0.0
    inter = len(ours & theirs)
    jac = inter / len(ours | theirs)
    contain = inter / len(ours)  # how much of OUR name appears in theirs
    return max(jac, contain * 0.9 if inter >= 2 or len(ours) == 1 else 0.0)


def has_coords(p: dict[str, Any]) -> bool:
    return isinstance(p.get("lat"), (int, float)) and isinstance(p.get("lng"), (int, float)) and bool(p["lat"] or p["lng"])


def candidates(p: dict[str, Any], iso2: str, key: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if has_coords(p):
        qs = urllib.parse.urlencode({"latitude": p["lat"], "longitude": p["lng"], "radius": 3000, "limit": 200})
        out += (nuitee_get(f"/v3.0/data/hotels?{qs}", key) or {}).get("data") or []
    names = [p["name"], re.split(r"[,—–(]| - ", p["name"])[0].strip()]
    for q in dict.fromkeys(n for n in names if len(n) >= 4):
        params = {"hotelName": q, "limit": 20}
        if iso2:
            params["countryCode"] = iso2
        out += (nuitee_get(f"/v3.0/data/hotels?{urllib.parse.urlencode(params)}", key) or {}).get("data") or []
    return out


def best_match(p: dict[str, Any], iso2: str, key: str, used: set[str]) -> tuple[dict[str, Any] | None, str]:
    ours = words(p["name"])
    city = words(p.get("city") or "")
    best, best_s, why = None, 0.0, "no candidates"
    core = ours - BRANDW - city
    for c in candidates(p, iso2, key):
        cid = str(c.get("id") or "")
        if not cid or cid in used:
            continue
        theirs = words(str(c.get("name") or ""))
        tcore = theirs - BRANDW - city - words(str(c.get("city") or ""))
        # the words that make this hotel different from its brand-mates must match
        if core and not (core & theirs):
            continue
        if not core and tcore - ours:
            continue
        s = similarity(ours, theirs)
        clat, clng = c.get("latitude"), c.get("longitude")
        if has_coords(p) and isinstance(clat, (int, float)) and isinstance(clng, (int, float)):
            d = km(p["lat"], p["lng"], clat, clng)
            if d > MAX_KM:
                continue
            need = 0.6
        else:
            # no pin to check against: demand a stronger name match, and the city if LiteAPI gives one
            need = 0.75
            ccity = words(str(c.get("city") or "") + " " + str(c.get("address") or ""))
            if city and ccity and not (city & ccity):
                continue
        if s >= need and s > best_s:
            best, best_s, why = c, s, f"name match {s:.2f}"
    return best, why


def main() -> int:
    key = os.environ["NUITEE_API_KEY"]
    props = sb_all("properties", "id,name,city,country,lat,lng,tier,visited_by_founder,nuitee_hotel_id,hero_image_url")
    guest = {r["property_id"] for r in sb_all("licensed_guest_scores", "property_id")}
    facts = {r["property_id"]: r for r in sb_all("property_facts", "property_id,standout,watch_out")}
    used = {str(p["nuitee_hotel_id"]) for p in props if p.get("nuitee_hotel_id")}
    print(f"{len(props)} properties | {len(used)} with a LiteAPI id")

    # ---- 1. match missing ids
    todo = [p for p in props if not p.get("nuitee_hotel_id") and not p.get("visited_by_founder")]
    print(f"Matching {len(todo)} properties without a LiteAPI id...")

    def job(p):
        cn = strip_accents(str(p.get("country") or "")).lower().strip()
        iso2 = COUNTRY_TO_ISO2.get(cn) or EXTRA_ISO.get(cn, "")
        return p, *best_match(p, iso2, key, used)

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(job, todo))
    matched = 0
    for p, m, why in results:
        if not m:
            print(f"  no safe match: {p['id']} ({p['name']})")
            continue
        mid = str(m["id"])
        if mid in used:  # another worker took it first
            continue
        used.add(mid)
        sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(p['id'])}", {"nuitee_hotel_id": mid}, {"Prefer": "return=minimal"})
        p["nuitee_hotel_id"] = mid
        matched += 1
        print(f"  matched {p['id']} -> {m.get('name')} ({why})")
    print(f"Matched {matched} new LiteAPI ids")

    # ---- 2. fill gaps from the LiteAPI record
    def needs(p):
        if p.get("visited_by_founder") or not p.get("nuitee_hotel_id"):
            return False
        f = facts.get(p["id"]) or {}
        return (
            needs_photo(p.get("hero_image_url"))
            or not has_coords(p) or p["id"] not in guest
            or not (f.get("standout") or "").strip() or not (f.get("watch_out") or "").strip()
        )

    fill = [p for p in props if needs(p)]
    print(f"Filling photos / pins / guest scores / facts for {len(fill)} properties...")

    def detail(p):
        res = nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(str(p['nuitee_hotel_id']))}", key)
        return p, (res or {}).get("data") or {}

    with ThreadPoolExecutor(max_workers=6) as ex:
        details = list(ex.map(detail, fill))

    stats = {"photo": 0, "pin": 0, "guest": 0, "facts": 0}
    far: dict[str, str] = {}
    trusted: dict[str, str] = {}
    guest_rows, fact_rows = [], []
    for p, d in details:
        if not d:
            continue
        patch: dict[str, Any] = {}
        if needs_photo(p.get("hero_image_url")):
            photo = pick_photo(d)
            if photo:
                patch.update({"hero_image_url": photo, "image_license_source": "nuitee_connect"})
                stats["photo"] += 1
        loc = d.get("location") or {}
        if not has_coords(p) and isinstance(loc.get("latitude"), (int, float)) and isinstance(loc.get("longitude"), (int, float)):
            pt = (float(loc["latitude"]), float(loc["longitude"]))
            cp = city_point(p.get("city") or "", p.get("country") or "")
            if cp and km_between(pt, cp) > 60 and not name_ok(p["name"], str(d.get("name") or "")) and similarity(words(p["name"]), words(str(d.get("name") or ""))) < 0.6:
                # the LiteAPI record is not this hotel: no pin from it, and no live prices from it either
                far[p["id"]] = f"far_from_town: LiteAPI hotel '{d.get('name')}' is {km_between(pt, cp):.0f} km from {p.get('city')}"
                print(f"  wrong LiteAPI record for {p['id']}: {far[p['id']]}")
            else:
                patch.update({"lat": pt[0], "lng": pt[1]})
                stats["pin"] += 1
                if cp and km_between(pt, cp) > 60:
                    # far from the geocoded town but the LiteAPI record has the same name: the town lookup was vague
                    trusted[p["id"]] = f"LiteAPI '{d.get('name')}'"
        if patch:
            patch["updated_at"] = now_iso()
            sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(p['id'])}", patch, {"Prefer": "return=minimal"})

        if p["id"] not in guest:
            try:
                r = float(d.get("rating") or 0)
            except (TypeError, ValueError):
                r = 0.0
            if r > 0:
                scale = 10.0 if r > 5 else 5.0
                try:
                    cnt = int(d.get("reviewCount")) if d.get("reviewCount") not in (None, "") else None
                except (TypeError, ValueError):
                    cnt = None
                guest_rows.append({
                    "property_id": p["id"], "partner_source": "nuitee_connect", "rating": round(r, 2), "scale": scale,
                    "normalized_100": max(1, min(100, int(round(r / scale * 100)))), "review_count": cnt,
                    "attribution": "Verified Guest Score", "verified_at": now_iso(),
                })
                stats["guest"] += 1

        f = facts.get(p["id"]) or {}
        if not (f.get("standout") or "").strip() or not (f.get("watch_out") or "").strip():
            kf = extract_key_facts_from_nuitee(d)
            row = {
                "property_id": p["id"],
                "standout": (f.get("standout") or "").strip() or kf.get("guest_standout") or "",
                "watch_out": (f.get("watch_out") or "").strip() or kf.get("guest_watch_out") or "",
                "verified_at": now_iso(),
            }
            for k in ("pool_heating", "beach_or_reef", "transfer_logistics", "red_flag_tags"):
                if kf.get(k):
                    row[k] = kf[k]
            if row["standout"] or row["watch_out"]:
                row["source_note"] = "Nuitée Connect verified facilities & guest themes"
                fact_rows.append(row)
                stats["facts"] += 1

    if guest_rows:
        upsert("licensed_guest_scores", guest_rows, "property_id,partner_source")
    if fact_rows:
        # rows have different key sets; send them one shape at a time
        by_shape: dict[tuple, list] = {}
        for r in fact_rows:
            by_shape.setdefault(tuple(sorted(r)), []).append(r)
        for rows in by_shape.values():
            upsert("property_facts", rows, "property_id")
    print(f"Filled: {stats}")
    if trusted:
        tp = Path(__file__).resolve().parent.parent / "data" / "pin-trusted.json"
        cur = json.loads(tp.read_text(encoding="utf-8")) if tp.exists() else {}
        cur.update(trusted)
        tp.write_text(json.dumps(dict(sorted(cur.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if far:
        pol_path = Path(__file__).resolve().parent.parent / "data" / "live-rate-coverage.json"
        pol = json.loads(pol_path.read_text(encoding="utf-8"))
        pol.setdefault("blockLiveRates", {}).update(far)
        for k in far:
            if k in (pol.get("verifiedLiveRates") or []):
                pol["verifiedLiveRates"].remove(k)
        pol_path.write_text(json.dumps(pol, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Blocked live pricing for {len(far)} LiteAPI records that are not the listed hotel")

    after = sb_all("properties", "id,lat,lng,nuitee_hotel_id,hero_image_url")
    print(
        "Coverage now: "
        f"LiteAPI ids {sum(1 for p in after if p.get('nuitee_hotel_id'))}/{len(after)}, "
        f"pins {sum(1 for p in after if has_coords(p))}/{len(after)}, "
        f"real photos {sum(1 for p in after if not needs_photo(p.get('hero_image_url')))}/{len(after)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
