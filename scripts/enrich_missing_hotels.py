#!/usr/bin/env python3
"""
StayOdds Missing-Data Completeness Enrichment Pass (Strict Zero-Fake-Data)
==========================================================================
1. Finds all properties in Supabase missing `nuitee_hotel_id`, missing a
   `licensed_guest_scores` record, or missing `standout` / `watch_out` facts.
2. Uses ONLY FREE Nuitée Connect (LiteAPI) metadata endpoints
   (`/v3.0/data/hotels` and `/v3.0/data/hotel?hotelId=...`) with a complete
   country-to-ISO2 map and diacritic-safe strict name matching.
3. Backfills ONLY real, verified licensed guest scores (> 0), Nuitee hotel IDs,
   and verified facilities/sentiment pros & cons (never overwriting founder notes).
4. Updates `booking_links` ("StayOdds Web Rates") to https://stayodds.com/stayodds/<slug>/.
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

COUNTRY_TO_ISO2: dict[str, str] = {
    "anguilla": "AI",
    "antigua and barbuda": "AG",
    "antigua": "AG",
    "argentina": "AR",
    "aruba": "AW",
    "australia": "AU",
    "austria": "AT",
    "bahamas": "BS",
    "barbados": "BB",
    "belgium": "BE",
    "belize": "BZ",
    "bermuda": "BM",
    "bhutan": "BT",
    "botswana": "BW",
    "brazil": "BR",
    "british virgin islands": "VG",
    "cambodia": "KH",
    "canada": "CA",
    "cayman islands": "KY",
    "chile": "CL",
    "china": "CN",
    "colombia": "CO",
    "costa rica": "CR",
    "croatia": "HR",
    "curacao": "CW",
    "curaçao": "CW",
    "cyprus": "CY",
    "czech republic": "CZ",
    "czechia": "CZ",
    "denmark": "DK",
    "dominica": "DM",
    "dominican republic": "DO",
    "ecuador": "EC",
    "egypt": "EG",
    "england": "GB",
    "fiji": "FJ",
    "finland": "FI",
    "france": "FR",
    "french polynesia": "PF",
    "germany": "DE",
    "greece": "GR",
    "grenada": "GD",
    "hong kong": "HK",
    "hungary": "HU",
    "iceland": "IS",
    "india": "IN",
    "indonesia": "ID",
    "ireland": "IE",
    "israel": "IL",
    "italy": "IT",
    "jamaica": "JM",
    "japan": "JP",
    "jordan": "JO",
    "kenya": "KE",
    "laos": "LA",
    "malaysia": "MY",
    "maldives": "MV",
    "malta": "MT",
    "mauritius": "MU",
    "mexico": "MX",
    "monaco": "MC",
    "montenegro": "ME",
    "morocco": "MA",
    "mozambique": "MZ",
    "namibia": "NA",
    "netherlands": "NL",
    "new zealand": "NZ",
    "nicaragua": "NI",
    "norway": "NO",
    "oman": "OM",
    "panama": "PA",
    "peru": "PE",
    "philippines": "PH",
    "poland": "PL",
    "portugal": "PT",
    "puerto rico": "PR",
    "qatar": "QA",
    "rwanda": "RW",
    "saint barthélemy": "BL",
    "saint barthelemy": "BL",
    "st. barts": "BL",
    "st barts": "BL",
    "saint kitts and nevis": "KN",
    "st. kitts and nevis": "KN",
    "saint lucia": "LC",
    "st. lucia": "LC",
    "saint vincent and the grenadines": "VC",
    "st. vincent and the grenadines": "VC",
    "saudi arabia": "SA",
    "scotland": "GB",
    "seychelles": "SC",
    "singapore": "SG",
    "south africa": "ZA",
    "south korea": "KR",
    "spain": "ES",
    "sri lanka": "LK",
    "sweden": "SE",
    "switzerland": "CH",
    "taiwan": "TW",
    "tanzania": "TZ",
    "thailand": "TH",
    "turkey": "TR",
    "türkiye": "TR",
    "turks & caicos": "TC",
    "turks and caicos": "TC",
    "turks and caicos islands": "TC",
    "u.s. virgin islands": "VI",
    "us virgin islands": "VI",
    "uae": "AE",
    "united arab emirates": "AE",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "usa": "US",
    "uruguay": "UY",
    "vietnam": "VN",
    "zambia": "ZM",
    "zimbabwe": "ZW",
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


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_tokens(text: str) -> set[str]:
    stop = {
        "the", "a", "an", "hotel", "hotels", "resort", "resorts", "spa", "villas",
        "villa", "residences", "and", "at", "of", "by", "in", "luxury", "collection",
        "beach", "island", "private", "club", "palace", "lodge", "camp", "retreat",
    }
    clean = strip_accents(text).lower().replace("&", " ")
    toks = set(re.findall(r"[a-z0-9]+", clean))
    filtered = toks - stop
    return filtered if filtered else toks


def sb_get_all(sb_url: str, key: str, table: str, select: str = "*") -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    offset = 0
    while True:
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/{table}?select={urllib.parse.quote(select)}&limit=1000&offset={offset}",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            chunk = json.loads(resp.read().decode("utf-8"))
        out.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return out


def sb_upsert(sb_url: str, key: str, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    for i in range(0, len(rows), 80):
        batch = rows[i : i + 80]
        endpoint = f"{sb_url}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(batch).encode("utf-8"),
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Upsert {table} failed: HTTP {resp.status}")


def sb_patch(sb_url: str, key: str, table: str, match_qs: str, payload: dict[str, Any]) -> None:
    req = urllib.request.Request(
        f"{sb_url}/rest/v1/{table}?{match_qs}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        method="PATCH",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"PATCH {table} failed: HTTP {resp.status}")


def nuitee_get(path: str, api_key: str) -> dict[str, Any] | None:
    url = f"https://api.liteapi.travel{path}"
    req = urllib.request.Request(
        url,
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "StayOddsEnrich/1.0"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=16) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < 2:
                time.sleep(0.4)
                continue
            return None
    return None


MAX_MATCH_KM = 10.0  # a LiteAPI candidate further than this from our stored coordinates is a lookalike


def km_between(lat1: Any, lng1: Any, lat2: Any, lng2: Any) -> float | None:
    """Great-circle distance in km, or None when either point is missing/invalid."""
    try:
        la1, lo1, la2, lo2 = (math.radians(float(v)) for v in (lat1, lng1, lat2, lng2))
    except (TypeError, ValueError):
        return None
    a = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def find_nuitee_hotel_smart(
    name: str,
    city: str,
    iso2: str,
    api_key: str,
    lat: float | None = None,
    lng: float | None = None,
) -> dict[str, Any] | None:
    if not iso2:
        return None
    ascii_name = strip_accents(name).strip()
    queries: list[str] = []
    for candidate in [
        name,
        ascii_name,
        re.sub(r"^the\s+", "", ascii_name, flags=re.I).strip(),
        re.split(r"[,—–-]", ascii_name)[0].strip(),
        re.sub(r"\b(a luxury collection|a tribute portfolio|resort & spa|hotel & spa|resort and spa)\b.*", "", ascii_name, flags=re.I).strip(),
    ]:
        if candidate and len(candidate) >= 4 and candidate not in queries:
            queries.append(candidate)

    target_tokens = norm_tokens(name)
    city_tokens = norm_tokens(city or "")

    for q in queries[:4]:
        qs = urllib.parse.urlencode({"countryCode": iso2, "hotelName": q, "limit": 10})
        res = nuitee_get(f"/v3.0/data/hotels?{qs}", api_key)
        items = (res or {}).get("data") or []
        if not items:
            continue
        best = None
        best_score = 0.0
        for item in items:
            cand_name = str(item.get("name") or "")
            cand_tokens = norm_tokens(cand_name)
            if not cand_tokens:
                continue
            # Name alone is not enough for one-word names (e.g. "Amandari" vs a budget hotel elsewhere in the
            # country), so reject any candidate whose coordinates are far from ours.
            dist_km = km_between(lat, lng, item.get("latitude"), item.get("longitude"))
            if dist_km is not None and dist_km > MAX_MATCH_KM:
                continue
            overlap_t = len(target_tokens & cand_tokens) / max(1, len(target_tokens))
            overlap_c = len(target_tokens & cand_tokens) / max(1, len(cand_tokens))
            # Strict dual check: avoid matching generic single-word chains in wrong city
            if overlap_t < 0.55 and overlap_c < 0.7:
                continue
            cand_city = norm_tokens(str(item.get("city") or ""))
            city_bonus = 0.12 if (city_tokens and (city_tokens & cand_city)) else 0.0
            star_bonus = 0.08 if (item.get("stars") or 0) >= 4 else 0.0
            rate_bonus = 0.06 if (item.get("rating") or 0) > 0 else 0.0
            score = (overlap_t * 0.6 + overlap_c * 0.4) + city_bonus + star_bonus + rate_bonus
            if score > best_score:
                best_score = score
                best = item
        if best and best_score >= 0.58:
            return best
    return None


def extract_facts(detail: dict[str, Any]) -> dict[str, Any]:
    facilities = [str(f).strip() for f in (detail.get("hotelFacilities") or []) if f]
    fac_low = [f.lower() for f in facilities]

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

    airport = str(detail.get("airportCode") or "").strip().upper()
    has_shuttle = any("airport shuttle" in f or "airport transfer" in f for f in fac_low)
    transfer = ""
    if airport and has_shuttle:
        transfer = f"Airport transfers available (nearest code: {airport})"
    elif airport:
        transfer = f"Nearest airport code: {airport}"
    elif has_shuttle:
        transfer = "Airport shuttle / transfer service listed"

    sa = detail.get("sentiment_analysis") or {}
    pros = [str(p).strip() for p in (sa.get("pros") or []) if p]
    cons = [str(c).strip() for c in (sa.get("cons") or []) if c]

    return {
        "pool_heating": pool_heating,
        "beach_or_reef": beach_or_reef,
        "transfer_logistics": transfer,
        "standout": " • ".join(pros[:2]) if pros else "",
        "watch_out": " • ".join(cons[:2]) if cons else "",
    }


def process_prop(
    prop: dict[str, Any],
    nuitee_key: str,
    existing_nuitee_id: str | None,
) -> dict[str, Any]:
    nid = existing_nuitee_id
    match = None
    if not nid:
        iso2 = COUNTRY_TO_ISO2.get(strip_accents(str(prop.get("country") or "")).lower().strip(), "")
        match = find_nuitee_hotel_smart(
            prop["name"], prop.get("city") or "", iso2, nuitee_key, prop.get("lat"), prop.get("lng")
        )
        if match and match.get("id"):
            nid = str(match["id"]).strip()

    detail = None
    if nid:
        res = nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(nid)}", nuitee_key)
        detail = (res or {}).get("data")
    return {"prop": prop, "nid": nid, "match": match, "detail": detail}


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    nuitee_key = os.environ["NUITEE_API_KEY"].strip()

    props = sb_get_all(sb_url, sb_secret, "properties", "id,name,city,country,nuitee_hotel_id,visited_by_founder,hero_image_url,lat,lng")
    guest_existing = {r["property_id"]: r for r in sb_get_all(sb_url, sb_secret, "licensed_guest_scores", "property_id,rating,review_count")}
    facts_existing = {r["property_id"]: r for r in sb_get_all(sb_url, sb_secret, "property_facts", "property_id,standout,watch_out,pool_heating,beach_or_reef,transfer_logistics,red_flag_tags,source_note")}

    targets = [
        p for p in props
        if not p.get("nuitee_hotel_id")
        or p["id"] not in guest_existing
        or not (facts_existing.get(p["id"], {}).get("standout") or "").strip()
        or not (facts_existing.get(p["id"], {}).get("watch_out") or "").strip()
    ]
    print(f"Loaded {len(props)} properties | Targeting {len(targets)} with missing Nuitee ID, guest score, or standout/watch-out facts...", flush=True)

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(process_prop, p, nuitee_key, p.get("nuitee_hotel_id")) for p in targets]
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 30 == 0 or done == len(targets):
                print(f"  Enriched {done}/{len(targets)}...", flush=True)

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    new_nid_count = 0
    new_guest_rows: list[dict[str, Any]] = []
    updated_fact_rows: list[dict[str, Any]] = []

    for item in results:
        p = item["prop"]
        pid = p["id"]
        nid = item["nid"]
        match = item["match"] or {}
        detail = item["detail"] or {}

        # Patch nuitee_hotel_id (and missing lat/lng/hero if empty) on properties table
        patch_payload: dict[str, Any] = {}
        if nid and not p.get("nuitee_hotel_id"):
            patch_payload["nuitee_hotel_id"] = nid
            new_nid_count += 1
        if not p.get("lat") and (detail.get("location") or {}).get("latitude"):
            patch_payload["lat"] = float(detail["location"]["latitude"])
            patch_payload["lng"] = float(detail["location"]["longitude"])
        if patch_payload:
            patch_payload["updated_at"] = now_iso
            sb_patch(sb_url, sb_secret, "properties", f"id=eq.{urllib.parse.quote(pid)}", patch_payload)

        # Licensed guest rating if missing and real rating > 0
        if pid not in guest_existing and (detail or match):
            raw_rating = detail.get("rating") if detail.get("rating") is not None else match.get("rating")
            raw_reviews = detail.get("reviewCount") if detail.get("reviewCount") is not None else match.get("reviewCount")
            try:
                r_num = float(raw_rating) if raw_rating not in (None, "", 0, "0") else 0.0
            except (TypeError, ValueError):
                r_num = 0.0
            if r_num > 0:
                scale = 10.0 if r_num > 5.0 else 5.0
                norm100 = max(1, min(100, int(round((r_num / scale) * 100))))
                try:
                    rev_cnt = int(raw_reviews) if raw_reviews not in (None, "") else None
                except (TypeError, ValueError):
                    rev_cnt = None
                new_guest_rows.append(
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

        # Property facts backfill (ONLY empty fields; NEVER overwrite founder notes)
        if detail:
            ef = extract_facts(detail)
            cur = facts_existing.get(pid) or {}
            merged = {
                "property_id": pid,
                "standout": (cur.get("standout") or "").strip() or ef["standout"],
                "watch_out": (cur.get("watch_out") or "").strip() or ef["watch_out"],
                "pool_heating": (cur.get("pool_heating") or "").strip() or ef["pool_heating"],
                "beach_or_reef": (cur.get("beach_or_reef") or "").strip() or ef["beach_or_reef"],
                "transfer_logistics": (cur.get("transfer_logistics") or "").strip() or ef["transfer_logistics"],
                "red_flag_tags": cur.get("red_flag_tags") or [],
                "source_note": cur.get("source_note") or "Nuitée Connect verified facilities & guest themes",
                "verified_at": now_iso,
            }
            changed = any(
                merged[k] != (cur.get(k) or "").strip()
                for k in ("standout", "watch_out", "pool_heating", "beach_or_reef", "transfer_logistics")
            )
            if changed:
                updated_fact_rows.append(merged)

    if new_guest_rows:
        sb_upsert(sb_url, sb_secret, "licensed_guest_scores", new_guest_rows, "property_id,partner_source")
    if updated_fact_rows:
        sb_upsert(sb_url, sb_secret, "property_facts", updated_fact_rows, "property_id")

    # Update mobile web-rate booking links to point directly to https://stayodds.com/stayodds/<slug>/
    booking_updates = [
        {
            "property_id": p["id"],
            "channel_type": "direct_brand",
            "partner_name": "StayOdds Web Rates",
            "url": f"https://stayodds.com/stayodds/{p['id']}/",
            "mobile_allowed": True,
            "perks_summary": "Compare live rates & verified reviews on StayOdds.com",
            "priority": 2,
            "updated_at": now_iso,
        }
        for p in props
    ]
    sb_upsert(sb_url, sb_secret, "booking_links", booking_updates, "property_id,channel_type,partner_name")

    print(
        f"\nENRICHMENT COMPLETE:\n"
        f"  New Nuitee Hotel IDs matched: {new_nid_count}\n"
        f"  New Verified Guest Ratings:   {len(new_guest_rows)}\n"
        f"  Updated Property Facts rows:  {len(updated_fact_rows)}\n"
        f"  Updated StayOdds Web Links:   {len(booking_updates)} -> https://stayodds.com/stayodds/<slug>/"
    )


if __name__ == "__main__":
    main()
