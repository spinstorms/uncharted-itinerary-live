#!/usr/bin/env python3
"""
StayOdds Sparse-Data Real Enrichment Pass (Zero Fake Data)
==========================================================
1. Targets all Supabase properties with a `nuitee_hotel_id` that are missing
   any of: standout, watch_out, pool_heating, beach_or_reef, or transfer_logistics.
2. Pulls ONLY FREE Nuitée Connect `/v3.0/data/hotel?hotelId=...` metadata and
   extracts verified facilities (pools, beach/coast/ski/golf/spa/kids club,
   airport transfers, check-in/out times, dining/restaurants) and verified
   guest sentiment pros/cons. NEVER overwrites founder stay notes or existing
   non-empty fields.
3. Also retries indicative GBP nightly price snapshots on a warm-season
   benchmark window (May 2027) for mapped LiteAPI hotels that were closed/seasonal
   in Jan/Feb (e.g. Mediterranean summer-only resorts in Greece, Italy, Ibiza, Bodrum)
   and merges them into data/price-snapshots.json.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
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
        req = urllib.request.Request(
            f"{sb_url}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}",
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


def nuitee_get(path: str, api_key: str) -> dict[str, Any] | None:
    req = urllib.request.Request(
        f"https://api.liteapi.travel{path}",
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "StayOddsRichFacts/1.0"},
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


def extract_rich_verified_facts(detail: dict[str, Any]) -> dict[str, str]:
    facilities = [str(f).strip() for f in (detail.get("hotelFacilities") or []) if f]
    fac_low = [f.lower() for f in facilities]
    desc_raw = re.sub(r"<[^>]+>", " ", str(detail.get("hotelDescription") or ""))
    desc = re.sub(r"\s+", " ", desc_raw).strip()
    desc_low = desc.lower()
    blob = " ".join(fac_low) + " " + desc_low

    # 1. Pool / Wellness fact (strictly from verified facilities/description)
    pool_heating = ""
    if any("heated pool" in f for f in fac_low) or "heated pool" in desc_low:
        pool_heating = "Heated pool confirmed"
    elif any("indoor pool" in f for f in fac_low) and any("outdoor pool" in f for f in fac_low):
        pool_heating = "Indoor & outdoor pools"
    elif any("private pool" in f or "plunge pool" in f for f in fac_low) or "private pool" in desc_low:
        pool_heating = "Private / plunge pools listed"
    elif any("infinity pool" in f for f in fac_low) or "infinity pool" in desc_low:
        pool_heating = "Infinity pool on property"
    elif any("indoor pool" in f for f in fac_low) or "indoor pool" in desc_low:
        pool_heating = "Indoor swimming pool"
    elif any("swimming pool" in f or "outdoor pool" in f or "pool" == f for f in fac_low):
        pool_heating = "Outdoor pool on property"
    elif any("spa" in f or "sauna" in f or "hot tub" in f or "hammam" in f or "thermal" in f for f in fac_low):
        pool_heating = "Full-service spa & wellness"

    # 2. Beach / Setting fact (strictly from verified facilities/description)
    beach_or_reef = ""
    has_private_beach = any("private beach" in f for f in fac_low) or "private beach" in desc_low
    # Strict keywords only: a bare "beach" substring also matches "beach towels", "beach shuttle", city-hotel
    # "beach umbrellas" etc. and previously mislabelled alpine/city/lake hotels as beachfront.
    has_beachfront = any(k in f for f in fac_low for k in ("beachfront", "on the beach", "beach access")) or "beachfront" in desc_low
    mountain_ctx = bool(re.search(r"\b(ski[- ]in|ski[- ]out|ski resort|skiing|alps|alpine|chairlift|ski slopes?|mountain resort|courchevel|st\.? moritz|zermatt|verbier|aspen|gstaad)\b", blob))
    if mountain_ctx and not any("private beach" in f for f in fac_low):
        has_beachfront = False
    has_snorkel = any("snorkeling" in f or "diving" in f for f in fac_low)
    has_ski = any("ski" in f for f in fac_low) and bool(re.search(r"\b(ski[- ]in|ski[- ]out|ski lift|ski slopes?|ski resort|piste|skiing)\b", blob))
    has_golf = any("golf" in f for f in fac_low)
    if has_private_beach and has_snorkel:
        beach_or_reef = "Private beach with snorkeling/diving access"
    elif has_private_beach:
        beach_or_reef = "Private beach area"
    elif has_beachfront and has_snorkel:
        beach_or_reef = "Beachfront with snorkeling/diving"
    elif has_beachfront:
        beach_or_reef = "Direct beachfront / coastal access"
    elif has_ski:
        beach_or_reef = "Alpine / ski access listed"
    elif has_golf:
        beach_or_reef = "On-site or adjacent golf course"

    # 3. Transfer / Check-in logistics (strictly from airportCode, facilities, checkinCheckoutTimes)
    airport = str(detail.get("airportCode") or "").strip().upper()
    has_shuttle = any("airport shuttle" in f or "airport transfer" in f or "shuttle service" in f for f in fac_low)
    ci_co = detail.get("checkinCheckoutTimes") or {}
    ci = str(ci_co.get("checkin") or ci_co.get("checkinStart") or "").strip()
    co = str(ci_co.get("checkout") or "").strip()
    t_bits = []
    if airport and has_shuttle:
        t_bits.append(f"Airport transfers listed ({airport})")
    elif airport:
        t_bits.append(f"Nearest airport: {airport}")
    elif has_shuttle:
        t_bits.append("Airport shuttle / transfer service listed")
    if ci and co:
        t_bits.append(f"Check-in {ci} / Out {co}")
    transfer = " • ".join(t_bits)

    # 4. Standout & Watch-Out from sentiment_analysis or factual amenity summary
    sa = detail.get("sentiment_analysis") or {}
    pros = [str(p).strip() for p in (sa.get("pros") or []) if p]
    cons = [str(c).strip() for c in (sa.get("cons") or []) if c]

    standout = " • ".join(pros[:2]) if pros else ""
    if not standout:
        # Build factual amenity highlights strictly from verified facilities list
        highlights = []
        if "all-inclusive" in blob or "all inclusive" in blob:
            highlights.append("All-inclusive option")
        if any("kids club" in f or "children" in f or "babysitting" in f for f in fac_low):
            highlights.append("Family & kids facilities")
        if any("michelin" in desc_low for _ in [1]) or any("fine dining" in desc_low for _ in [1]):
            highlights.append("Fine dining on property")
        elif any("restaurant" in f for f in fac_low):
            highlights.append("On-site dining")
        if any("spa" in f for f in fac_low):
            highlights.append("Spa & wellness center")
        if any("fitness" in f or "gym" in f for f in fac_low):
            highlights.append("Fitness center")
        if highlights:
            standout = "Verified amenities: " + " • ".join(highlights[:3])

    watch_out = " • ".join(cons[:2]) if cons else ""

    return {
        "pool_heating": pool_heating,
        "beach_or_reef": beach_or_reef,
        "transfer_logistics": transfer,
        "standout": standout,
        "watch_out": watch_out,
    }


def retry_may_prices(nuitee_key: str, props: list[dict[str, Any]]) -> int:
    snap_path = ROOT / "data" / "price-snapshots.json"
    snap_data = json.loads(snap_path.read_text(encoding="utf-8")) if snap_path.exists() else {"prices": {}}
    existing = snap_data.get("prices", {})
    missing = [(p["id"], str(p["nuitee_hotel_id"]).strip()) for p in props if p.get("nuitee_hotel_id") and p["id"] not in existing]
    if not missing:
        return 0
    print(f"Retrying warm-season (2027-05-14 -> 2027-05-16) indicative GBP rates for {len(missing)} unpriced mapped hotels...", flush=True)
    added = 0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for i in range(0, len(missing), 35):
        batch = missing[i : i + 35]
        nid_to_slug = {nid: slug for slug, nid in batch}
        payload = {
            "hotelIds": list(nid_to_slug.keys()),
            "checkin": "2027-05-14",
            "checkout": "2027-05-16",
            "occupancies": [{"adults": 2}],
            "currency": "GBP",
            "guestNationality": "GB",
            "maxRatesPerHotel": 1,
        }
        req = urllib.request.Request(
            "https://api.liteapi.travel/v3.0/hotels/rates",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "X-API-Key": nuitee_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "StayOddsPriceMay/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=22) as resp:
                data = json.loads(resp.read().decode("utf-8")).get("data") or []
            for h_obj in data:
                hid = str(h_obj.get("hotelId") or "").strip()
                slug = nid_to_slug.get(hid)
                if not slug or slug in existing:
                    continue
                min_total = None
                for rt in h_obj.get("roomTypes") or []:
                    for rate in rt.get("rates") or []:
                        tot = (rate.get("retailRate") or {}).get("total")
                        if isinstance(tot, list) and tot:
                            amt = tot[0].get("amount")
                        elif isinstance(tot, dict):
                            amt = tot.get("amount")
                        else:
                            amt = None
                        if amt is not None:
                            try:
                                v = float(amt)
                                if v > 0 and (min_total is None or v < min_total):
                                    min_total = v
                            except (TypeError, ValueError):
                                pass
                if min_total is not None:
                    nightly = max(25, int(round((min_total / 2.0) / 5.0) * 5))
                    existing[slug] = {
                        "nightlyGbp": nightly,
                        "label": f"From £{nightly:,}/nt",
                        "currency": "GBP",
                        "source": "LiteAPI Indicative Snapshot",
                        "sampleCheckin": "2027-05-14",
                        "checkedAt": today,
                    }
                    added += 1
        except Exception:
            continue
    snap_data["prices"] = existing
    snap_data["count"] = len(existing)
    snap_data["updatedAt"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    snap_path.write_text(json.dumps(snap_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return added


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    nuitee_key = os.environ["NUITEE_API_KEY"].strip()

    props = sb_get_all(sb_url, sb_secret, "properties", "id,name,nuitee_hotel_id,visited_by_founder")
    facts_existing = {
        r["property_id"]: r
        for r in sb_get_all(
            sb_url,
            sb_secret,
            "property_facts",
            "property_id,standout,watch_out,pool_heating,beach_or_reef,transfer_logistics,red_flag_tags,source_note",
        )
    }

    targets = [
        p
        for p in props
        if p.get("nuitee_hotel_id")
        and (
            not (facts_existing.get(p["id"], {}).get("standout") or "").strip()
            or not (facts_existing.get(p["id"], {}).get("watch_out") or "").strip()
            or not (facts_existing.get(p["id"], {}).get("pool_heating") or "").strip()
            or not (facts_existing.get(p["id"], {}).get("beach_or_reef") or "").strip()
            or not (facts_existing.get(p["id"], {}).get("transfer_logistics") or "").strip()
        )
    ]
    print(f"Enriching verified property facts for {len(targets)} mapped hotels via FREE Nuitée Connect...", flush=True)

    def fetch_one(p: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        res = nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(str(p['nuitee_hotel_id']))}", nuitee_key)
        return p, (res or {}).get("data")

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    updated_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futs = [pool.submit(fetch_one, p) for p in targets]
        done = 0
        for fut in as_completed(futs):
            p, detail = fut.result()
            done += 1
            if done % 60 == 0 or done == len(targets):
                print(f"  Fetched {done}/{len(targets)}...", flush=True)
            if not detail:
                continue
            pid = p["id"]
            ef = extract_rich_verified_facts(detail)
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
            if any(
                merged[k] != (cur.get(k) or "").strip()
                for k in ("standout", "watch_out", "pool_heating", "beach_or_reef", "transfer_logistics")
            ):
                updated_rows.append(merged)

    if updated_rows:
        sb_upsert(sb_url, sb_secret, "property_facts", updated_rows, "property_id")

    may_prices_added = retry_may_prices(nuitee_key, props)
    print(f"SPARSE ENRICHMENT COMPLETE: updated_facts={len(updated_rows)} hotels, may_seasonal_prices_added={may_prices_added}")


if __name__ == "__main__":
    main()
