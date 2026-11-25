#!/usr/bin/env python3
"""Real Tripadvisor rating, review count, ranking and awards for each hotel, saved to data/tripadvisor.json.

Uses the owner's Tripadvisor (Terra) API key from TRIPADVISOR_API_KEY. One search call per hotel: the search result
already carries the full location record (traveler_ratings, rankings, awards, coordinates, Tripadvisor URL).
A result is only accepted when the name matches (same strict rule as map pins) AND it is within 3 km of our pin
(or, with no pin, in the same country). Nothing is estimated: unmatched hotels are simply left without Tripadvisor data.

  --max-calls N   stop after about N locations have been returned (Tripadvisor bills per location: $0.015 each for
                  the first 1,000 a month, so the default 900 caps a run at about $13.50)
  --refresh-days  re-check a hotel only after this many days (default 180)
Order: World's 50 Best and MICHELIN Key hotels first, then hotels without a guest score, then the rest.
Switch off everywhere by setting "enabled": false in data/tripadvisor-settings.json.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY, TRIPADVISOR_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import km_between, name_ok, sb_all  # noqa: E402
from enrich_missing_hotels import COUNTRY_TO_ISO2  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "tripadvisor.json"
BASE = "https://terra.tripadvisor.com/api"


def ta_get(path: str, params: list[tuple[str, str]], key: str) -> tuple[int, Any]:
    url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"X-API-Key": key, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code == 429 and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            return e.code, body
        except Exception as e:  # noqa: BLE001
            if attempt < 2:
                time.sleep(2)
                continue
            return 0, str(e)
    return 0, "retries exhausted"


def primary_name(loc: dict[str, Any]) -> str:
    names = loc.get("names") or []
    for n in names:
        if n.get("primary"):
            return str(n.get("value") or "")
    return str((names[0] if names else {}).get("value") or "")


def summarise(loc: dict[str, Any]) -> dict[str, Any]:
    tr = (loc.get("traveler_ratings") or {}).get("overall") or {}
    ranks = loc.get("rankings") or []
    rank = next((r for r in ranks if "hotel" in str(r.get("category") or "").lower()), ranks[0] if ranks else None)
    awards = [
        {"name": a.get("name") or a.get("type"), "year": a.get("year")}
        for a in (loc.get("awards") or []) if a.get("name") or a.get("type")
    ]
    awards.sort(key=lambda a: a.get("year") or 0, reverse=True)
    return {
        "locationId": loc.get("id"),
        "name": primary_name(loc),
        "rating": tr.get("rating"),
        "reviewCount": tr.get("count"),
        "ranking": (rank or {}).get("display_text") or (
            f"#{rank['rank']} of {rank['total']} {rank.get('category') or 'hotels'} in {rank.get('geo')}" if rank and rank.get("rank") else None),
        "awards": awards[:3],
        "url": ((loc.get("urls") or {}).get("tripadvisor") or {}).get("main"),
        "status": (loc.get("status") or {}).get("value"),
    }


def priority(props: list[dict[str, Any]]) -> list[dict[str, Any]]:
    award_ids: set[str] = set()
    try:
        d = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))
        for h in d.get("hotels") or []:
            if any(re.search(r"50 ?best|michelin", f"{a.get('awardBody', '')} {a.get('label', '')}", re.I)
                   for a in h.get("officialAwards") or []):
                award_ids.add(h["id"])
    except Exception:
        pass
    guest = {r["property_id"] for r in sb_all("licensed_guest_scores", "property_id,review_count")
             if (r.get("review_count") or 0) >= 20}
    return sorted(props, key=lambda p: (p["id"] not in award_ids, p["id"] in guest, p["name"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=900)
    ap.add_argument("--refresh-days", type=int, default=180)
    args = ap.parse_args()
    key = os.environ.get("TRIPADVISOR_API_KEY", "").strip()
    if not key:
        print("Tripadvisor: no TRIPADVISOR_API_KEY secret yet - skipped")
        return 0
    store = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"hotels": {}, "unmatched": {}}
    today = date.today()

    def fresh(stamp: str | None) -> bool:
        try:
            return (today - date.fromisoformat(str(stamp)[:10])).days < args.refresh_days
        except Exception:
            return False

    props = sb_all("properties", "id,name,city,country,lat,lng")
    todo = [p for p in priority(props)
            if not fresh((store["hotels"].get(p["id"]) or {}).get("fetched")) and not fresh(store["unmatched"].get(p["id"]))]
    print(f"Tripadvisor: {len(todo)} hotels to check, budget {args.max_calls} calls")
    calls = matched = 0
    stamp = datetime.now(timezone.utc).date().isoformat()
    for p in todo:
        if calls >= args.max_calls:
            break
        iso = (COUNTRY_TO_ISO2.get(p.get("country") or "") or "").upper()
        params = [("query", p["name"]), ("category", "HOTEL"), ("size", "3"), ("version", "1")]
        if iso:
            params.append(("country_code", iso))
        code, res = ta_get("/locations/search", params, key)
        # billing is per location returned, so count every location in the response against the budget
        calls += max(1, len(res.get("data") or [])) if isinstance(res, dict) else 1
        if code in (401, 403):
            print(f"Tripadvisor: API refused the key ({code}): {res}")
            break
        if code == 402 or (code == 429 and calls > 5):
            print(f"Tripadvisor: quota or spending limit reached ({code}) - stopping for now")
            break
        if code != 200 or not isinstance(res, dict):
            print(f"  {p['id']}: HTTP {code} {str(res)[:120]}")
            continue
        hit = None
        for item in res.get("data") or []:
            loc = item.get("location") or {}
            if not name_ok(p["name"], primary_name(loc)):
                continue
            c = loc.get("coordinates") or {}
            if isinstance(p.get("lat"), (int, float)) and p.get("lat") and c.get("latitude") is not None:
                if km_between((p["lat"], p["lng"]), (float(c["latitude"]), float(c["longitude"]))) > 3:
                    continue
            elif iso:
                cc = next((a.get("country_code") for a in loc.get("addresses") or [] if a.get("country_code")), "")
                if cc and cc.upper() != iso:
                    continue
            hit = loc
            break
        if hit and (hit.get("traveler_ratings") or {}).get("overall", {}).get("rating") is not None:
            store["hotels"][p["id"]] = {**summarise(hit), "fetched": stamp}
            store["unmatched"].pop(p["id"], None)
            matched += 1
            s = store["hotels"][p["id"]]
            print(f"  {p['id']}: {s['rating']}/5 from {s['reviewCount']} reviews ({s['name']})")
        else:
            store["unmatched"][p["id"]] = stamp
            print(f"  {p['id']}: no confident Tripadvisor match")
    store["hotels"] = dict(sorted(store["hotels"].items()))
    store["unmatched"] = dict(sorted(store["unmatched"].items()))
    store["updated"] = stamp
    OUT.write_text(json.dumps(store, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Tripadvisor: {calls} calls, {matched} hotels matched this run, {len(store['hotels'])} stored in total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
