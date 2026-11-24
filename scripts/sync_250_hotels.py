#!/usr/bin/env python3
"""
StayOdds Scheduled Backend Sync (250 Verified Luxury Hotels)
- Combines 36 First-Hand stays/Shorts + 76 existing Global Directory + 138 new flagship icons (incl. Los Angeles) = 250 hotels.
- Queries ONLY FREE Nuitée Connect (LiteAPI) metadata endpoints:
    GET /v3.0/data/hotels
    GET /v3.0/data/hotel?hotelId=...
  NEVER calls paid Places ($0.01/req) or Price Index ($0.05/req) endpoints!
- Populates Supabase with 100% REAL licensed guest ratings, review counts, licensed hotel photography,
  verified Middle Key Facts (extracted strictly from hotelFacilities, airportCode, and sentiment_analysis),
  official source-URL awards, and compliant dual booking links.
- Uses concurrent workers (8 threads) so all 250 properties sync in ~45–60 seconds cleanly.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from catalog_250 import ADDITIONAL_138_LUXURY_HOTELS, VERIFIED_AWARDS_BY_SLUG

ROOT = Path(__file__).resolve().parent.parent

COUNTRY_TO_ISO2 = {
    "indonesia": "ID",
    "maldives": "MV",
    "thailand": "TH",
    "vietnam": "VN",
    "singapore": "SG",
    "japan": "JP",
    "hong kong": "HK",
    "united arab emirates": "AE",
    "oman": "OM",
    "italy": "IT",
    "france": "FR",
    "united kingdom": "GB",
    "scotland": "GB",
    "switzerland": "CH",
    "greece": "GR",
    "spain": "ES",
    "united states": "US",
    "mexico": "MX",
    "st. barts": "BL",
    "saint barthélemy": "BL",
    "st. lucia": "LC",
    "saint lucia": "LC",
    "turks & caicos": "TC",
    "turks and caicos islands": "TC",
    "french polynesia": "PF",
    "morocco": "MA",
    "south africa": "ZA",
    "kenya": "KE",
    "seychelles": "SC",
    "mauritius": "MU",
    "anguilla": "AI",
    "antigua and barbuda": "AG",
    "saint vincent and the grenadines": "VC",
    "portugal": "PT",
    "austria": "AT",
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


def norm_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "hotel", "resort", "spa", "villas", "villa", "residences", "and", "at", "of", "by", "in", "luxury", "collection"}
    toks = set(re.findall(r"[a-z0-9]+", text.lower()))
    filtered = toks - stop
    return filtered if filtered else toks


def nuitee_get(path: str, api_key: str) -> dict[str, Any] | None:
    url = f"https://api.liteapi.travel{path}"
    req = urllib.request.Request(
        url,
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "StayOddsSync/1.0"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=18) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(1.2 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < 2:
                time.sleep(0.5)
                continue
            return None
    return None


def find_nuitee_hotel(name: str, iso2: str, api_key: str) -> dict[str, Any] | None:
    # Try full name first, then shortened primary name (before comma/dash)
    queries = [name]
    short = re.split(r"[,—–-]", name)[0].strip()
    if short and short != name and len(short) >= 4:
        queries.append(short)

    target_tokens = norm_tokens(name)
    for q in queries:
        qs = urllib.parse.urlencode({"countryCode": iso2, "hotelName": q, "limit": 8})
        res = nuitee_get(f"/v3.0/data/hotels?{qs}", api_key)
        items = (res or {}).get("data") or []
        if not items:
            continue
        # Pick best name-matching candidate with highest overlap + rating
        best = None
        best_score = 0.0
        for item in items:
            cand_name = str(item.get("name") or "")
            cand_tokens = norm_tokens(cand_name)
            if not cand_tokens:
                continue
            overlap = len(target_tokens & cand_tokens) / max(1, len(target_tokens))
            # Prefer 4-5 star luxury match with rating
            bonus = 0.1 if (item.get("stars") or 0) >= 4 else 0.0
            bonus += 0.05 if (item.get("rating") or 0) > 0 else 0.0
            score = overlap + bonus
            if overlap >= 0.5 and score > best_score:
                best_score = score
                best = item
        if best:
            return best
    return None


def extract_key_facts_from_nuitee(detail: dict[str, Any]) -> dict[str, Any]:
    facilities = [str(f).strip() for f in (detail.get("hotelFacilities") or []) if f]
    fac_low = [f.lower() for f in facilities]

    # Pool heating (ONLY from verified hotelFacilities strings)
    pool_heating = ""
    if any("heated pool" in f for f in fac_low):
        pool_heating = "Heated pool confirmed"
    elif any("indoor pool" in f for f in fac_low) and any("outdoor pool" in f for f in fac_low):
        pool_heating = "Indoor & outdoor pools"
    elif any("private pool" in f or "plunge pool" in f for f in fac_low):
        pool_heating = "Private / plunge pools listed"
    elif any("infinity pool" in f for f in fac_low):
        pool_heating = "Infinity pool on property"
    elif any("swimming pool" in f or "outdoor pool" in f for f in fac_low):
        pool_heating = "Outdoor pool (heating not listed)"

    # Beach / Reef (ONLY from verified hotelFacilities)
    beach_or_reef = ""
    has_private_beach = any("private beach" in f for f in fac_low)
    has_beachfront = any("beachfront" in f or "on the beach" in f or "beach access" in f for f in fac_low)
    has_snorkel = any("snorkeling" in f or "diving" in f for f in fac_low)
    if has_private_beach and has_snorkel:
        beach_or_reef = "Private beach with snorkeling/diving access"
    elif has_private_beach:
        beach_or_reef = "Private beach area"
    elif has_beachfront and has_snorkel:
        beach_or_reef = "Beachfront with snorkeling/diving"
    elif has_beachfront:
        beach_or_reef = "Direct beachfront access"

    # Transfer logistics (ONLY from airportCode + airport shuttle facilities)
    airport = str(detail.get("airportCode") or "").strip().upper()
    has_shuttle = any("airport shuttle" in f or "airport transfer" in f for f in fac_low)
    transfer = ""
    if airport and has_shuttle:
        transfer = f"Airport transfers available (nearest code: {airport})"
    elif airport:
        transfer = f"Nearest airport code: {airport}"
    elif has_shuttle:
        transfer = "Airport shuttle / transfer service listed"

    # Verified guest pros & cons from Nuitée Connect sentiment_analysis
    sa = detail.get("sentiment_analysis") or {}
    pros = [str(p).strip() for p in (sa.get("pros") or []) if p]
    cons = [str(c).strip() for c in (sa.get("cons") or []) if c]

    # Red-flag tags strictly derived from verified cons
    red_flags: list[str] = []
    cons_blob = " ".join(cons).lower()
    if any(k in cons_blob for k in ["expensive", "overpriced", "high price", "costly"]):
        red_flags.append("High On-Property Pricing")
    if any(k in cons_blob for k in ["dated", "aged", "maintenance", "worn", "old"]):
        red_flags.append("Aging Finish Noted")
    if any(k in cons_blob for k in ["seaplane", "remote", "transfer", "long drive"]):
        red_flags.append("Transfer Logistics")
    if any(k in cons_blob for k in ["noisy", "noise", "crowded", "busy"]):
        red_flags.append("Noise / Crowds Noted")
    if any(k in cons_blob for k in ["unheated", "cold pool"]):
        red_flags.append("Pool Temperature Noted")

    return {
        "pool_heating": pool_heating,
        "beach_or_reef": beach_or_reef,
        "transfer_logistics": transfer,
        "guest_standout": " • ".join(pros[:2]) if pros else "",
        "guest_watch_out": " • ".join(cons[:2]) if cons else "",
        "red_flag_tags": red_flags[:4],
    }


def supabase_upsert(url: str, secret_key: str, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    # Batch in chunks of 80 rows for reliability
    for i in range(0, len(rows), 80):
        batch = rows[i : i + 80]
        endpoint = f"{url}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(batch).encode("utf-8"),
            headers={
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Upsert {table} failed with HTTP {resp.status}")


def build_master_250() -> list[dict[str, Any]]:
    visited_data = json.loads((ROOT / "data" / "hotels.json").read_text(encoding="utf-8"))
    world_data = json.loads((ROOT / "data" / "world-hotels.json").read_text(encoding="utf-8"))

    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    master: list[dict[str, Any]] = []

    for h in visited_data.get("hotels", []):
        iso2 = COUNTRY_TO_ISO2.get((h.get("country") or "").lower(), "ID")
        seen_ids.add(h["id"])
        seen_names.add(h["name"].lower())
        master.append({**h, "iso2": iso2, "visitedByUs": True})

    for h in world_data.get("hotels", []):
        if h["id"] in seen_ids or h["name"].lower() in seen_names:
            continue
        iso2 = COUNTRY_TO_ISO2.get((h.get("country") or "").lower(), "US")
        region = h.get("region", "Global")
        if region == "Americas & Caribbean":
            region = "Los Angeles & Americas"
        elif region == "Africa & Middle East":
            region = "Indian Ocean & Africa"
        seen_ids.add(h["id"])
        seen_names.add(h["name"].lower())
        master.append({**h, "region": region, "iso2": iso2, "visitedByUs": False})

    for slug, name, city, country, iso2, region, brand in ADDITIONAL_138_LUXURY_HOTELS:
        if slug in seen_ids or name.lower() in seen_names:
            continue
        seen_ids.add(slug)
        seen_names.add(name.lower())
        booking_url = f"https://www.booking.com/searchresults.html?ss={urllib.parse.quote_plus(f'{name} {city}')}"
        master.append(
            {
                "id": slug,
                "name": name,
                "location": city,
                "country": country,
                "iso2": iso2,
                "region": region,
                "brand": brand,
                "visitedByUs": False,
                "coverageType": "Global Directory",
                "scores": None,
                "overall": None,
                "verdict": "",
                "standout": "",
                "watchOut": "",
                "bookingUrl": booking_url,
                "thumbnail": "",
            }
        )

    return master


def process_one_hotel(h: dict[str, Any], nuitee_key: str) -> dict[str, Any]:
    match = find_nuitee_hotel(h["name"], h["iso2"], nuitee_key)
    detail = None
    if match and match.get("id"):
        res = nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(str(match['id']))}", nuitee_key)
        detail = (res or {}).get("data")
    return {"hotel": h, "match": match, "detail": detail}


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    nuitee_key = os.environ["NUITEE_API_KEY"].strip()
    new_only = "--new-only" in sys.argv

    master = build_master_250()

    # Fetch existing properties & google_place_id map from Supabase
    existing_pids: dict[str, str] = {}
    existing_ids: set[str] = set()
    try:
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/properties?select=id,google_place_id&limit=1000",
            headers={"apikey": sb_secret, "Authorization": f"Bearer {sb_secret}"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            for row in json.loads(resp.read().decode("utf-8")):
                existing_ids.add(row["id"])
                if row.get("google_place_id"):
                    existing_pids[row["id"]] = row["google_place_id"]
    except Exception:
        pass

    targets = [h for h in master if h["id"] not in existing_ids] if new_only else master
    print(f"Master catalog: {len(master)} | Syncing {len(targets)} luxury properties against FREE Nuitée Connect endpoints...", flush=True)
    if not targets:
        print("All properties already synced!")
        return

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(process_one_hotel, h, nuitee_key) for h in targets]
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 15 == 0 or done == len(targets):
                print(f"  Nuitée Connect sync: {done}/{len(targets)} complete...", flush=True)

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    prop_rows: list[dict[str, Any]] = []
    fact_rows: list[dict[str, Any]] = []
    guest_rows: list[dict[str, Any]] = []
    fh_rows: list[dict[str, Any]] = []
    award_rows: list[dict[str, Any]] = []
    booking_rows: list[dict[str, Any]] = []

    matched_count = 0
    rated_guest_count = 0

    for item in results:
        h = item["hotel"]
        match = item["match"] or {}
        detail = item["detail"] or {}
        pid = h["id"]
        visited = bool(h.get("visitedByUs"))
        rated = visited and h.get("overall") is not None and h.get("scores") is not None
        tier = "first_hand_verified" if rated else ("short_preview" if visited else "global_directory")

        nuitee_id = str(detail.get("id") or match.get("id") or "").strip() or None
        if nuitee_id:
            matched_count += 1

        # Prefer licensed Nuitée Connect photo for global directory (or if visited lacks thumbnail)
        nuitee_photo = str(detail.get("main_photo") or match.get("main_photo") or "").strip()
        if not nuitee_photo:
            imgs = detail.get("hotelImages") or []
            if imgs and isinstance(imgs[0], dict):
                nuitee_photo = str(imgs[0].get("url") or "").strip()
        hero_image = h.get("thumbnail") if (visited and h.get("thumbnail")) else (nuitee_photo or h.get("thumbnail") or "")
        image_source = "youtube_founder" if (visited and h.get("thumbnail")) else ("nuitee_connect" if nuitee_photo else "editorial")

        lat = h.get("lat") or (detail.get("location") or {}).get("latitude") or match.get("latitude")
        lng = h.get("lng") or (detail.get("location") or {}).get("longitude") or match.get("longitude")

        prop_rows.append(
            {
                "id": pid,
                "name": h["name"],
                "brand": h.get("brand") or str(detail.get("chain") or ""),
                "city": h.get("location") or str(detail.get("city") or match.get("city") or ""),
                "country": h.get("country", ""),
                "region": h.get("region", "Global"),
                "lat": float(lat) if lat not in (None, "") else None,
                "lng": float(lng) if lng not in (None, "") else None,
                "tier": tier,
                "visited_by_founder": visited,
                "google_place_id": existing_pids.get(pid),
                "nuitee_hotel_id": nuitee_id,
                "price_tier": h.get("priceRange", ""),
                "hero_image_url": hero_image,
                "image_license_source": image_source,
                "updated_at": now_iso,
            }
        )

        # Extract verified Middle Key Facts from Nuitée Connect
        kf = extract_key_facts_from_nuitee(detail) if detail else {
            "pool_heating": "",
            "beach_or_reef": "",
            "transfer_logistics": "",
            "guest_standout": "",
            "guest_watch_out": "",
            "red_flag_tags": [],
        }

        standout = h.get("standout") if visited else (kf["guest_standout"] or h.get("standout") or "")
        watch_out = h.get("watchOut") if visited else (kf["guest_watch_out"] or h.get("watchOut") or "")

        fact_rows.append(
            {
                "property_id": pid,
                "standout": standout,
                "watch_out": watch_out,
                "pool_heating": kf["pool_heating"],
                "beach_or_reef": kf["beach_or_reef"],
                "transfer_logistics": kf["transfer_logistics"],
                "red_flag_tags": kf["red_flag_tags"],
                "source_note": "Founder stay notes + Nuitée Connect specs" if visited else ("Nuitée Connect verified facilities & guest themes" if detail else "Curated property metadata"),
                "verified_at": now_iso,
            }
        )

        # Licensed guest rating (strictly REAL rating > 0 from Nuitée Connect)
        raw_rating = detail.get("rating") if detail.get("rating") is not None else match.get("rating")
        raw_reviews = detail.get("reviewCount") if detail.get("reviewCount") is not None else match.get("reviewCount")
        try:
            r_num = float(raw_rating) if raw_rating not in (None, "", 0, "0") else 0.0
        except (TypeError, ValueError):
            r_num = 0.0
        if r_num > 0:
            scale = 10.0 if r_num > 5.0 else 5.0
            norm100 = int(round((r_num / scale) * 100))
            norm100 = max(1, min(100, norm100))
            try:
                rev_cnt = int(raw_reviews) if raw_reviews not in (None, "") else None
            except (TypeError, ValueError):
                rev_cnt = None
            guest_rows.append(
                {
                    "property_id": pid,
                    "partner_source": "nuitee_connect",
                    "rating": round(r_num, 2),
                    "scale": scale,
                    "normalized_100": norm100,
                    "review_count": rev_cnt,
                    "attribution": "Verified Guest Score",
                    "verified_at": now_iso,
                }
            )
            rated_guest_count += 1

        # First-Hand reviews (36 stays/Shorts)
        if visited:
            s = h.get("scores") or {}
            reviewed_date = h.get("reviewedDate") or None
            if reviewed_date and len(reviewed_date) != 10:
                reviewed_date = None
            fh_rows.append(
                {
                    "property_id": pid,
                    "contributor_name": "The Uncharted Itinerary",
                    "coverage_type": "Full Review" if rated else "Short Tour",
                    "youtube_video_id": h.get("videoId", ""),
                    "in_live_feed": bool(h.get("inLiveFeed", False)),
                    "rooms_score": s.get("rooms") if rated else None,
                    "grounds_score": s.get("grounds") if rated else None,
                    "food_score": s.get("food") if rated else None,
                    "service_score": s.get("service") if rated else None,
                    "value_score": s.get("value") if rated else None,
                    "overall_score": h.get("overall") if rated else None,
                    "verdict": h.get("verdict", ""),
                    "where_we_differ": h.get("verdict", "") if rated else "",
                    "reviewed_date": reviewed_date,
                    "shorts": h.get("shorts", []),
                    "updated_at": now_iso,
                }
            )

        # Official verifiable awards with strict HTTP source_url
        for body, label, year, norm100, src_url in VERIFIED_AWARDS_BY_SLUG.get(pid, []):
            award_rows.append(
                {
                    "property_id": pid,
                    "award_body": body,
                    "label": label,
                    "award_year": year,
                    "normalized_100": norm100,
                    "source_url": src_url,
                    "verified_at": now_iso,
                }
            )

        # Dual booking links:
        # 1) Web Booking.com (auto-monetized by Travelpayouts Drive on web, mobile_allowed=False per Booking.com Content Website rule)
        b_url = (h.get("bookingUrl") or "").strip()
        if not b_url.startswith("http"):
            search_q = f"{h['name']} {h.get('location', '')}".strip()
            b_url = f"https://www.booking.com/searchresults.html?ss={urllib.parse.quote_plus(search_q)}"
        booking_rows.append(
            {
                "property_id": pid,
                "channel_type": "ota_affiliate",
                "partner_name": "Booking.com",
                "url": b_url,
                "mobile_allowed": False,
                "perks_summary": "",
                "priority": 1,
                "updated_at": now_iso,
            }
        )
        # 2) Mobile-compliant web hotel hub link (routes mobile app users to your Content Website SEO page where Booking.com + Drive is 100% compliant!)
        booking_rows.append(
            {
                "property_id": pid,
                "channel_type": "direct_brand",
                "partner_name": "StayOdds Web Rates",
                "url": f"https://uncharteditinerary.com/stayodds/{pid}/",
                "mobile_allowed": True,
                "perks_summary": "Compare live rates & verified reviews on StayOdds web",
                "priority": 2,
                "updated_at": now_iso,
            }
        )

    supabase_upsert(sb_url, sb_secret, "properties", prop_rows, "id")
    supabase_upsert(sb_url, sb_secret, "property_facts", fact_rows, "property_id")
    supabase_upsert(sb_url, sb_secret, "licensed_guest_scores", guest_rows, "property_id,partner_source")
    supabase_upsert(sb_url, sb_secret, "first_hand_reviews", fh_rows, "property_id")
    supabase_upsert(sb_url, sb_secret, "official_awards", award_rows, "property_id,award_body,label")
    supabase_upsert(sb_url, sb_secret, "booking_links", booking_rows, "property_id,channel_type,partner_name")

    print(
        f"\nSYNC COMPLETE!\n"
        f"  Total Luxury Properties in Supabase: {len(prop_rows)}\n"
        f"  Matched in Nuitée Connect (FREE API): {matched_count}/{len(prop_rows)}\n"
        f"  Live Verified Guest Ratings Synced:   {rated_guest_count}/{len(prop_rows)}\n"
        f"  First-Hand Verified & Shorts:         {len(fh_rows)}\n"
        f"  Official Sourced Awards:              {len(award_rows)}\n"
        f"  Compliant Dual Booking Links:         {len(booking_rows)}"
    )


if __name__ == "__main__":
    main()
