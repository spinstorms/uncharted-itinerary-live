#!/usr/bin/env python3
"""Real Google Maps star rating and review count for each hotel, saved to data/google-ratings.json.

Uses the hotel's Google place id (already matched to that exact hotel) and the Places API (New) Place Details
with only the rating fields. Rechecks a hotel every --refresh-days (default 180). Nothing is estimated: a hotel
without a place id or without a rating is simply left out.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY, GOOGLE_PLACES_API_KEY
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "google-ratings.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=1500)
    ap.add_argument("--refresh-days", type=int, default=180)
    args = ap.parse_args()
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not key:
        print("Google ratings: no GOOGLE_PLACES_API_KEY - skipped")
        return 0
    store = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"hotels": {}}
    today = date.today()

    def fresh(stamp: str | None) -> bool:
        try:
            return (today - date.fromisoformat(str(stamp)[:10])).days < args.refresh_days
        except Exception:
            return False

    corr = json.loads((ROOT / "data" / "property-corrections.json").read_text(encoding="utf-8")).get("properties", {}) \
        if (ROOT / "data" / "property-corrections.json").exists() else {}
    wrong = {k for k, v in corr.items() if "google_place_id" in v and not v["google_place_id"]}
    for k in wrong:
        store["hotels"].pop(k, None)  # its Google listing was a different place
    props = [p for p in sb_all("properties", "id,name,google_place_id") if p.get("google_place_id") and p["id"] not in wrong]
    todo = [p for p in props if not fresh((store["hotels"].get(p["id"]) or {}).get("fetched"))]
    print(f"Google ratings: {len(todo)} hotels to check (budget {args.max_calls})")
    stamp = datetime.now(timezone.utc).date().isoformat()
    calls = got = 0
    for p in todo:
        if calls >= args.max_calls:
            break
        req = urllib.request.Request(
            f"https://places.googleapis.com/v1/places/{urllib.parse.quote(p['google_place_id'])}",
            headers={"X-Goog-Api-Key": key, "X-Goog-FieldMask": "displayName,rating,userRatingCount", "Accept-Language": "en"},
        )
        calls += 1
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            print(f"  {p['id']}: HTTP {e.code}")
            if e.code in (403, 429):
                break
            continue
        except Exception as e:  # noqa: BLE001
            print(f"  {p['id']}: {e}")
            continue
        if d.get("rating") is not None and d.get("userRatingCount"):
            store["hotels"][p["id"]] = {
                "rating": float(d["rating"]), "reviewCount": int(d["userRatingCount"]),
                "name": (d.get("displayName") or {}).get("text", ""), "fetched": stamp,
            }
            got += 1
        time.sleep(0.05)
    store["hotels"] = dict(sorted(store["hotels"].items()))
    store["updated"] = stamp
    OUT.write_text(json.dumps(store, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Google ratings: {calls} calls, {got} ratings saved this run, {len(store['hotels'])} stored")
    return 0


if __name__ == "__main__":
    sys.exit(main())
