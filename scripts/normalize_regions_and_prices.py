#!/usr/bin/env python3
"""
StayOdds Macro-Region Consolidation & Batched Indicative Price Snapshot Pipeline
1. Consolidates fragmented Supabase `properties.region` strings into 8 clean,
   mutually exclusive macro regions:
     - Europe
     - Asia
     - Maldives & Indian Ocean
     - Australia & Pacific
     - Americas
     - Caribbean & Mexico
     - Middle East
     - Africa
2. Queries LiteAPI (/v3.0/hotels/rates) in batches of 40 hotelIds across all
   properties with a mapped `nuitee_hotel_id` for a fixed benchmark 2-night
   window (+45 days out, 2 adults, GBP) and writes `data/price-snapshots.json`
   so directory/compare cards can display indicative "From £X/nt" pricing with
   ZERO per-pageview API calls.

Flags:
  --regions-only   Only normalize regions in Supabase
  --prices-only    Only refresh data/price-snapshots.json (used by weekly GitHub Action)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

COUNTRY_TO_MACRO_REGION: dict[str, str] = {
    # Maldives & Indian Ocean
    "Maldives": "Maldives & Indian Ocean",
    "Seychelles": "Maldives & Indian Ocean",
    "Mauritius": "Maldives & Indian Ocean",
    "Madagascar": "Maldives & Indian Ocean",
    "Sri Lanka": "Asia",
    # Australia & Pacific
    "Australia": "Australia & Pacific",
    "New Zealand": "Australia & Pacific",
    "French Polynesia": "Australia & Pacific",
    "Fiji": "Australia & Pacific",
    "Cook Islands": "Australia & Pacific",
    # Caribbean & Mexico
    "Mexico": "Caribbean & Mexico",
    "Dominican Republic": "Caribbean & Mexico",
    "Antigua and Barbuda": "Caribbean & Mexico",
    "Saint Lucia": "Caribbean & Mexico",
    "St. Lucia": "Caribbean & Mexico",
    "Turks and Caicos Islands": "Caribbean & Mexico",
    "Turks & Caicos": "Caribbean & Mexico",
    "Jamaica": "Caribbean & Mexico",
    "Bahamas": "Caribbean & Mexico",
    "The Bahamas": "Caribbean & Mexico",
    "Barbados": "Caribbean & Mexico",
    "Anguilla": "Caribbean & Mexico",
    "Saint Barthélemy": "Caribbean & Mexico",
    "St. Barths": "Caribbean & Mexico",
    "British Virgin Islands": "Caribbean & Mexico",
    "Cayman Islands": "Caribbean & Mexico",
    "Puerto Rico": "Caribbean & Mexico",
    "Grenada": "Caribbean & Mexico",
    "Dominica": "Caribbean & Mexico",
    "Aruba": "Caribbean & Mexico",
    "Curaçao": "Caribbean & Mexico",
    "Saint Kitts and Nevis": "Caribbean & Mexico",
    "Saint Vincent and the Grenadines": "Caribbean & Mexico",
    "Bermuda": "Caribbean & Mexico",
    "US Virgin Islands": "Caribbean & Mexico",
    "U.S. Virgin Islands": "Caribbean & Mexico",
    "Trinidad and Tobago": "Caribbean & Mexico",
    "Martinique": "Caribbean & Mexico",
    "Guadeloupe": "Caribbean & Mexico",
    "Saint Martin": "Caribbean & Mexico",
    "Sint Maarten": "Caribbean & Mexico",
    "Bonaire": "Caribbean & Mexico",
    "Cuba": "Caribbean & Mexico",
    # Americas
    "United States": "Americas",
    "USA": "Americas",
    "Canada": "Americas",
    "Costa Rica": "Americas",
    "Brazil": "Americas",
    "Argentina": "Americas",
    "Chile": "Americas",
    "Peru": "Americas",
    "Colombia": "Americas",
    "Ecuador": "Americas",
    "Panama": "Americas",
    "Belize": "Americas",
    "Nicaragua": "Americas",
    "Uruguay": "Americas",
    # Middle East
    "United Arab Emirates": "Middle East",
    "UAE": "Middle East",
    "Oman": "Middle East",
    "Qatar": "Middle East",
    "Saudi Arabia": "Middle East",
    "Jordan": "Middle East",
    "Bahrain": "Middle East",
    "Israel": "Middle East",
    # Africa
    "Egypt": "Africa",
    "South Africa": "Africa",
    "Morocco": "Africa",
    "Kenya": "Africa",
    "Tanzania": "Africa",
    "Rwanda": "Africa",
    "Botswana": "Africa",
    "Namibia": "Africa",
    "Zambia": "Africa",
    "Zimbabwe": "Africa",
    "Mozambique": "Africa",
    # Asia
    "Japan": "Asia",
    "Indonesia": "Asia",
    "Thailand": "Asia",
    "India": "Asia",
    "Vietnam": "Asia",
    "Singapore": "Asia",
    "Malaysia": "Asia",
    "Hong Kong": "Asia",
    "China": "Asia",
    "South Korea": "Asia",
    "Taiwan": "Asia",
    "Cambodia": "Asia",
    "Laos": "Asia",
    "Philippines": "Asia",
    "Bhutan": "Asia",
    "Nepal": "Asia",
    "Macau": "Asia",
    # Europe
    "Italy": "Europe",
    "United Kingdom": "Europe",
    "UK": "Europe",
    "Greece": "Europe",
    "France": "Europe",
    "Spain": "Europe",
    "Turkey": "Europe",
    "Switzerland": "Europe",
    "Portugal": "Europe",
    "Austria": "Europe",
    "Germany": "Europe",
    "Ireland": "Europe",
    "Croatia": "Europe",
    "Netherlands": "Europe",
    "Norway": "Europe",
    "Denmark": "Europe",
    "Sweden": "Europe",
    "Iceland": "Europe",
    "Monaco": "Europe",
    "Czech Republic": "Europe",
    "Czechia": "Europe",
    "Hungary": "Europe",
    "Montenegro": "Europe",
    "Cyprus": "Europe",
    "Malta": "Europe",
    "Belgium": "Europe",
    "Finland": "Europe",
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


def sb_request(sb_url: str, sb_key: str, method: str, path: str, body: Any = None, extra_headers: dict[str, str] | None = None) -> Any:
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{sb_url}/rest/v1/{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def sb_get_all(sb_url: str, sb_key: str, table: str, select: str = "*") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        chunk = sb_request(
            sb_url,
            sb_key,
            "GET",
            f"{table}?select={urllib.parse.quote(select)}&limit=1000&offset={offset}",
        ) or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return rows


def resolve_macro_region(country: str, existing_region: str) -> str:
    c = (country or "").strip()
    if c in COUNTRY_TO_MACRO_REGION:
        return COUNTRY_TO_MACRO_REGION[c]
    r = (existing_region or "").lower()
    if "maldives" in r or "indian ocean" in r:
        return "Maldives & Indian Ocean"
    if "caribbean" in r or "mexico" in r:
        return "Caribbean & Mexico"
    if "australia" in r or "pacific" in r or "bora" in r:
        return "Australia & Pacific"
    if "europe" in r:
        return "Europe"
    if "middle east" in r:
        return "Middle East"
    if "africa" in r:
        return "Africa"
    if "america" in r:
        return "Americas"
    return "Asia"


def normalize_regions(sb_url: str, sb_key: str, props: list[dict[str, Any]]) -> None:
    changes: list[tuple[str, str, str]] = []
    counts: dict[str, int] = {}
    for p in props:
        old_r = (p.get("region") or "").strip()
        new_r = resolve_macro_region(p.get("country") or "", old_r)
        counts[new_r] = counts.get(new_r, 0) + 1
        if new_r != old_r:
            changes.append((p["id"], old_r, new_r))

    print(f"Macro-region distribution across {len(props)} properties:")
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}")
    print(f"Updating {len(changes)} properties in Supabase...")

    by_new_region: dict[str, list[str]] = {}
    for pid, _, new_r in changes:
        by_new_region.setdefault(new_r, []).append(pid)

    for new_r, pids in by_new_region.items():
        for i in range(0, len(pids), 60):
            chunk = pids[i : i + 60]
            in_clause = ",".join(chunk)
            sb_request(
                sb_url,
                sb_key,
                "PATCH",
                f"properties?id=in.({urllib.parse.quote(in_clause, safe=',')})",
                body={"region": new_r},
                extra_headers={"Prefer": "return=minimal"},
            )
    print(f"Normalized {len(changes)} region records cleanly!")


def fetch_liteapi_batch(hotel_ids: list[str], checkin: str, checkout: str, api_key: str) -> dict[str, int]:
    payload = json.dumps(
        {
            "hotelIds": hotel_ids,
            "checkin": checkin,
            "checkout": checkout,
            "currency": "GBP",
            "guestNationality": "GB",
            "occupancies": [{"adults": 2}],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.liteapi.travel/v3.0/hotels/rates",
        data=payload,
        headers={
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    out: dict[str, int] = {}
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for row in data.get("data") or []:
            hid = str(row.get("hotelId") or "")
            if not hid:
                continue
            totals: list[float] = []
            for rt in row.get("roomTypes") or []:
                amt = (rt.get("offerRetailRate") or {}).get("amount")
                if amt is not None:
                    try:
                        val = float(amt)
                        if val > 40:
                            totals.append(val)
                    except Exception:
                        pass
            if totals:
                # 2-night benchmark window -> indicative nightly rate rounded to nearest £5
                per_night = min(totals) / 2.0
                rounded = max(50, int(round(per_night / 5.0) * 5))
                out[hid] = rounded
    except Exception as e:
        print(f"  Batch warning ({len(hotel_ids)} ids): {e}")
    return out


def sync_price_snapshots(props: list[dict[str, Any]], nuitee_key: str) -> None:
    # Skip hotels blocked in data/live-rate-coverage.json (official-site-only brands etc.): no point pricing them.
    from live_rate_policy import blocked_ids

    skip = blocked_ids()
    mapped = [
        (p["id"], str(p["nuitee_hotel_id"]).strip()) for p in props if p.get("nuitee_hotel_id") and p["id"] not in skip
    ]
    id_by_nuitee: dict[str, list[str]] = {}
    for slug, nid in mapped:
        id_by_nuitee.setdefault(nid, []).append(slug)

    unique_nids = list(id_by_nuitee.keys())
    # Benchmark window: 45 days out, 2 nights (mid-range indicative rate)
    ci_date = date.today() + timedelta(days=45)
    co_date = ci_date + timedelta(days=2)
    ci, co = ci_date.isoformat(), co_date.isoformat()

    batches = [unique_nids[i : i + 35] for i in range(0, len(unique_nids), 35)]
    print(f"Fetching indicative GBP nightly snapshots for {len(unique_nids)} LiteAPI hotels ({len(batches)} batches, {ci} -> {co})...")

    nid_rates: dict[str, int] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(fetch_liteapi_batch, b, ci, co, nuitee_key) for b in batches]
        for f in concurrent.futures.as_completed(futs):
            nid_rates.update(f.result())

    # Retry misses once with a 75-day window (catches seasonal closures / sold-out weekends)
    misses = [nid for nid in unique_nids if nid not in nid_rates]
    if misses:
        ci2 = (date.today() + timedelta(days=75)).isoformat()
        co2 = (date.today() + timedelta(days=77)).isoformat()
        retry_batches = [misses[i : i + 35] for i in range(0, len(misses), 35)]
        print(f"Retrying {len(misses)} seasonal/unavailable hotels on secondary window ({ci2} -> {co2})...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(fetch_liteapi_batch, b, ci2, co2, nuitee_key) for b in retry_batches]
            for f in concurrent.futures.as_completed(futs):
                for k, v in f.result().items():
                    nid_rates.setdefault(k, v)

    now_iso = datetime.now(timezone.utc).isoformat()
    snapshots: dict[str, dict[str, Any]] = {}
    for nid, rate_gbp in nid_rates.items():
        for slug in id_by_nuitee.get(nid, []):
            snapshots[slug] = {
                "nightlyGbp": rate_gbp,
                "label": f"From £{rate_gbp:,}/nt",
                "currency": "GBP",
                "source": "LiteAPI Indicative Snapshot",
                "sampleCheckin": ci,
                "checkedAt": now_iso[:10],
            }

    out_path = ROOT / "data" / "price-snapshots.json"
    out_path.write_text(
        json.dumps(
            {
                "updatedAt": now_iso,
                "currency": "GBP",
                "benchmarkWindow": f"{ci} to {co}",
                "totalMapped": len(unique_nids),
                "totalPriced": len(snapshots),
                "prices": snapshots,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Saved {len(snapshots)}/{len(unique_nids)} indicative nightly price snapshots -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions-only", action="store_true")
    parser.add_argument("--prices-only", action="store_true")
    args = parser.parse_args()

    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_PUBLISHABLE_KEY") or ""
    nuitee_key = os.environ.get("NUITEE_API_KEY", "")

    props = sb_get_all(sb_url, sb_key, "properties", "id,country,region,nuitee_hotel_id")
    if not args.prices_only:
        normalize_regions(sb_url, sb_key, props)
    if not args.regions_only and nuitee_key:
        sync_price_snapshots(props, nuitee_key)


if __name__ == "__main__":
    main()
