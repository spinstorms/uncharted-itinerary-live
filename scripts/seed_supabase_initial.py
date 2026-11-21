#!/usr/bin/env python3
"""
Seed StayOdds Supabase Postgres with verified property records and resolve permanent
Google Place IDs using the $0 unlimited Places API (New) Essentials (IDs Only) field mask.

Zero AI-estimated scores are ever written.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent


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


def resolve_google_place_id(name: str, city: str, country: str, api_key: str) -> str | None:
    """Uses Places API (New) Text Search Essentials (IDs Only) -> $0 unlimited SKU."""
    query = f"{name} {city} {country}".strip()
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=json.dumps({"textQuery": query, "maxResultCount": 1}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.id",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            places = payload.get("places") or []
            if places and places[0].get("id"):
                return str(places[0]["id"])
    except Exception as exc:
        print(f"  [warn] Place ID lookup failed for {name}: {exc}", file=sys.stderr)
    return None


def supabase_upsert(url: str, secret_key: str, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    endpoint = f"{url}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(rows).encode("utf-8"),
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


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    places_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()

    visited_data = json.loads((ROOT / "data" / "hotels.json").read_text(encoding="utf-8"))
    world_data = json.loads((ROOT / "data" / "world-hotels.json").read_text(encoding="utf-8"))

    visited_hotels = visited_data.get("hotels", [])
    visited_ids = {h["id"] for h in visited_hotels}
    visited_names = {h["name"].lower() for h in visited_hotels}
    world_hotels = [
        h
        for h in world_data.get("hotels", [])
        if h["id"] not in visited_ids and h["name"].lower() not in visited_names
    ]

    all_hotels = [(h, True) for h in visited_hotels] + [(h, False) for h in world_hotels]
    print(f"Preparing {len(visited_hotels)} visited + {len(world_hotels)} global = {len(all_hotels)} properties...")

    # Check existing place IDs in Supabase to avoid redundant lookups
    existing_place_ids: dict[str, str] = {}
    try:
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/properties?select=id,google_place_id",
            headers={"apikey": sb_secret, "Authorization": f"Bearer {sb_secret}"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            for row in json.loads(resp.read().decode("utf-8")):
                if row.get("google_place_id"):
                    existing_place_ids[row["id"]] = row["google_place_id"]
    except Exception:
        pass

    prop_rows: list[dict[str, Any]] = []
    fact_rows: list[dict[str, Any]] = []
    fh_rows: list[dict[str, Any]] = []
    booking_rows: list[dict[str, Any]] = []

    resolved_count = 0
    for idx, (h, visited) in enumerate(all_hotels, start=1):
        pid = h["id"]
        place_id = existing_place_ids.get(pid)
        if not place_id and places_key:
            place_id = resolve_google_place_id(h["name"], h.get("location", ""), h.get("country", ""), places_key)
            if place_id:
                resolved_count += 1
            time.sleep(0.06)

        rated = visited and h.get("overall") is not None and h.get("scores") is not None
        tier = "first_hand_verified" if rated else ("short_preview" if visited else "global_directory")

        prop_rows.append(
            {
                "id": pid,
                "name": h["name"],
                "brand": h.get("brand", ""),
                "city": h.get("location", ""),
                "country": h.get("country", ""),
                "region": h.get("region", "Global"),
                "lat": h.get("lat"),
                "lng": h.get("lng"),
                "tier": tier,
                "visited_by_founder": visited,
                "google_place_id": place_id,
                "price_tier": h.get("priceRange", ""),
                "hero_image_url": h.get("thumbnail", ""),
                "image_license_source": "youtube_founder" if visited else "unsplash_editorial",
            }
        )

        fact_rows.append(
            {
                "property_id": pid,
                "standout": h.get("standout", ""),
                "watch_out": h.get("watchOut", ""),
                "source_note": "Founder first-hand stay notes" if visited else "Curated property facts",
            }
        )

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
                }
            )

        b_url = (h.get("bookingUrl") or "").strip()
        if b_url.startswith("http"):
            is_booking = "booking.com" in b_url.lower()
            booking_rows.append(
                {
                    "property_id": pid,
                    "channel_type": "ota_affiliate",
                    "partner_name": "Booking.com" if is_booking else "Hotel Partner",
                    "url": b_url,
                    "mobile_allowed": not is_booking,  # Respect Travelpayouts Booking.com Content Website rule
                    "priority": 1,
                }
            )

        if idx % 25 == 0 or idx == len(all_hotels):
            print(f"  Processed {idx}/{len(all_hotels)} (resolved {resolved_count} new Google Place IDs)...")

    supabase_upsert(sb_url, sb_secret, "properties", prop_rows, "id")
    supabase_upsert(sb_url, sb_secret, "property_facts", fact_rows, "property_id")
    supabase_upsert(sb_url, sb_secret, "first_hand_reviews", fh_rows, "property_id")
    supabase_upsert(sb_url, sb_secret, "booking_links", booking_rows, "property_id,channel_type,partner_name")

    total_with_pid = sum(1 for r in prop_rows if r.get("google_place_id"))
    print(f"DONE! Upserted {len(prop_rows)} properties ({total_with_pid} with Google Place IDs), {len(fh_rows)} first-hand reviews, {len(booking_rows)} booking links.")


if __name__ == "__main__":
    main()
