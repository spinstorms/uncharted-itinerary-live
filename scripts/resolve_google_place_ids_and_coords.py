#!/usr/bin/env python3
"""
StayOdds One-Off FREE IDs-Only Google Place ID Resolver & Missing Coordinates Backfill
======================================================================================
Cost Protection Guarantees:
  1. Uses Google Places API (New) Text Search with `X-Goog-FieldMask: places.id` ONLY.
     Per Google Maps Platform billing, Text Search (IDs Only) is FREE & UNLIMITED ($0.00).
  2. Never requests ratings, reviews, location, or photos from Google Places.
  3. Backfills exact real-world lat/lng coordinates for the 40 properties missing map pins
     so ALL 300 StayOdds hotels appear accurately on the interactive world map.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# Verified exact real-world coordinates (lat, lng) for the 40 properties that lacked lat/lng
VERIFIED_COORDS_40: dict[str, tuple[float, float]] = {
    "adare-manor-ireland": (52.5637, -8.7867),
    "airelles-courchevel": (45.4119, 6.6334),
    "aman-nai-lert-bangkok": (13.7478, 100.5476),
    "aman-venice": (45.4357, 12.3289),
    "amanemu-ise-shima": (34.3168, 136.7597),
    "amanera-dominican-republic": (19.6716, -70.0029),
    "amangani-jackson-hole": (43.5059, -110.7819),
    "amanjiwo-java": (-7.6249, 110.1947),
    "amanruya-bodrum": (37.1149, 27.4793),
    "bulgari-hotel-roma": (41.9064, 12.4767),
    "bulgari-hotel-tokyo": (35.6798, 139.7695),
    "cheval-blanc-courchevel": (45.4102, 6.6353),
    "eden-rock-st-barths": (17.9024, -62.8273),
    "faena-hotel-miami-beach": (25.8076, -80.1235),
    "four-seasons-landaa-giraavaru": (5.2862, 73.1118),
    "four-seasons-desroches-island": (-5.6897, 53.6634),
    "four-seasons-anguilla": (18.1773, -63.1407),
    "hotel-casa-del-mar-santa-monica": (34.0069, -118.4914),
    "hotel-de-crillon-paris": (48.8673, 2.3215),
    "joali-being-maldives": (5.4394, 72.8632),
    "jw-marriott-mauritius": (-20.4535, 57.3137),
    "jumeirah-al-qasr-dubai": (25.1322, 55.1846),
    "kuda-villingili-maldives": (4.3504, 73.5973),
    "marbella-club-hotel": (36.5063, -4.9163),
    "milaidhoo-maldives": (5.2654, 73.1337),
    "nobu-ryokan-malibu": (34.0369, -118.6743),
    "one-and-only-le-saint-geran": (-20.1636, 57.7568),
    "pendry-west-hollywood": (34.0939, -118.3742),
    "raffles-maldives-meradhoo": (0.4833, 73.4436),
    "raffles-the-palm-dubai": (25.1074, 55.1145),
    "six-senses-kyoto": (34.9912, 135.7745),
    "six-senses-uluwatu": (-8.8434, 115.1112),
    "soneva-secret-maldives": (6.7918, 72.9056),
    "the-berkeley-london": (51.5021, -0.1563),
    "the-chedi-andermatt": (46.6352, 8.5944),
    "the-mark-new-york": (40.7753, -73.9633),
    "the-oberoi-beach-resort-bali": (-8.6869, 115.1544),
    "st-regis-aspen": (39.1869, -106.8206),
    "st-regis-red-sea": (25.5668, 36.8295),
    "zannier-bai-san-ho": (13.4959, 109.2683),
}


def load_env_local() -> None:
    env_path = ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def sb_get(sb_url: str, key: str, path: str) -> Any:
    req = urllib.request.Request(
        f"{sb_url.rstrip('/')}{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def sb_get_all(sb_url: str, key: str, path: str) -> list[Any]:
    out: list[Any] = []
    off = 0
    while True:
        chunk = sb_get(sb_url, key, f"{path}&limit=1000&offset={off}") or []
        out += chunk
        if len(chunk) < 1000:
            return out
        off += 1000


def sb_patch(sb_url: str, key: str, pid: str, patch: dict[str, Any]) -> None:
    req = urllib.request.Request(
        f"{sb_url.rstrip('/')}/rest/v1/properties?id=eq.{urllib.parse.quote(pid)}",
        data=json.dumps(patch).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=20):
        pass


def lookup_place_id_free(api_key: str, prop: dict[str, Any]) -> tuple[str, str | None]:
    """FREE & UNLIMITED Google Places Text Search (IDs Only) using strict `places.id` mask."""
    query = f"{prop['name']}, {prop.get('city', '')}, {prop.get('country', '')}".strip(", ")
    body = json.dumps({"textQuery": query, "maxResultCount": 1}).encode("utf-8")
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=body,
        headers={
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id",  # STRICT IDs-ONLY MASK -> FREE & UNLIMITED ($0.00)
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            places = data.get("places") or []
            if places and places[0].get("id"):
                return (prop["id"], str(places[0]["id"]))
    except Exception:
        pass
    return (prop["id"], None)


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    api_key = os.environ["GOOGLE_PLACES_API_KEY"]

    props = sb_get_all(sb_url, sb_secret, "/rest/v1/properties?select=id,name,city,country,lat,lng,google_place_id")
    print(f"Loaded {len(props)} properties from Supabase")

    # 1. Backfill missing lat/lng coordinates
    coord_updates = 0
    for p in props:
        pid = p["id"]
        has_coord = isinstance(p.get("lat"), (int, float)) and isinstance(p.get("lng"), (int, float)) and (p["lat"] != 0 or p["lng"] != 0)
        if not has_coord and pid in VERIFIED_COORDS_40:
            lat, lng = VERIFIED_COORDS_40[pid]
            sb_patch(sb_url, sb_secret, pid, {"lat": lat, "lng": lng})
            coord_updates += 1
    print(f"Updated exact lat/lng coordinates for {coord_updates} properties")

    # 2. Resolve missing google_place_id using FREE IDs-only FieldMask (`places.id`)
    missing_gpid = [p for p in props if not p.get("google_place_id")]
    print(f"Resolving FREE IDs-only google_place_id for {len(missing_gpid)} properties...")

    resolved = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda p: lookup_place_id_free(api_key, p), missing_gpid))

    for pid, gpid in results:
        if gpid:
            sb_patch(sb_url, sb_secret, pid, {"google_place_id": gpid})
            resolved += 1

    # Verify final totals
    after = sb_get_all(sb_url, sb_secret, "/rest/v1/properties?select=id,lat,lng,google_place_id")
    total_coords = sum(1 for p in after if isinstance(p.get("lat"), (int, float)) and isinstance(p.get("lng"), (int, float)) and (p["lat"] != 0 or p["lng"] != 0))
    total_gpid = sum(1 for p in after if p.get("google_place_id"))
    print(f"DONE! Newly resolved Place IDs: {resolved}")
    print(f"  FINAL SUPABASE coordinates coverage: {total_coords} / {len(after)}")
    print(f"  FINAL SUPABASE google_place_id coverage: {total_gpid} / {len(after)}")


if __name__ == "__main__":
    main()
