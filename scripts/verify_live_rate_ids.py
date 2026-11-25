#!/usr/bin/env python3
"""Check that every stored LiteAPI hotel id really is the hotel we think it is.

Each property carries a LiteAPI id (``nuitee_hotel_id``) that was matched by name. For each one this script
fetches the LiteAPI hotel record and compares its location and name with ours:

  verified  within 5 km and the names overlap -> added to ``verifiedLiveRates``. These keep live pricing even if
            a heuristic price rule would otherwise hide them.
  conflict  more than 10 km away but same name -> left alone (our coordinates are probably off); listed in report
  mismatch  more than 10 km away, names differ -> added to ``blockLiveRates``. Live pricing is hidden and the
            page explains why (see scripts/live_rate_policy.py).
  unchecked API error, no coordinates, 5-10 km away or weak name overlap -> left exactly as it is.

Hotels listed under ``officialSites`` (Aman) are skipped: they are official-site-only by design.

Needs SUPABASE_URL, SUPABASE_SECRET_KEY and NUITEE_API_KEY (all already GitHub secrets). The key is never
printed or written anywhere. Normally run by the "Verify LiteAPI hotel ids" workflow:

    python3 scripts/verify_live_rate_ids.py            # report only
    python3 scripts/verify_live_rate_ids.py --write    # also update data/live-rate-coverage.json
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enrich_missing_hotels import km_between, norm_tokens, nuitee_get  # noqa: E402
from live_rate_policy import POLICY_PATH, load_policy  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "data" / "live-rate-verification.json"
VERIFIED_KM = 5.0
MISMATCH_KM = 10.0


def strong_name_match(ours: set[str], theirs: set[str]) -> bool:
    if not ours or not theirs:
        return False
    inter = len(ours & theirs)
    if inter / len(ours | theirs) >= 0.8:
        return True
    return ours <= theirs and len(ours) >= 3


def classify(
    our_name: str, our_lat: Any, our_lng: Any, detail: dict[str, Any] | None
) -> tuple[str, float | None, str]:
    """Return (status, distance_km, liteapi_name) for one property."""
    if not detail:
        return "unchecked", None, ""
    lite_name = str(detail.get("name") or "")
    loc = detail.get("location") or {}
    km = km_between(our_lat, our_lng, loc.get("latitude"), loc.get("longitude"))
    if km is None:
        return "unchecked", None, lite_name
    ours, theirs = norm_tokens(our_name), norm_tokens(lite_name)
    if km > MISMATCH_KM:
        # Same name but far away usually means OUR coordinates are off: report it, don't hide live pricing.
        return ("conflict" if strong_name_match(ours, theirs) else "mismatch"), km, lite_name
    overlap = len(ours & theirs) / max(1, min(len(ours), len(theirs)))
    if km <= VERIFIED_KM and overlap >= 0.5:
        return "verified", km, lite_name
    return "unchecked", km, lite_name


def verify(
    props: list[dict[str, Any]],
    fetch_detail: Callable[[str], dict[str, Any] | None],
    skip_ids: set[str],
    workers: int = 6,
) -> dict[str, Any]:
    targets = [p for p in props if p.get("nuitee_hotel_id") and p["id"] not in skip_ids]
    cache: dict[str, dict[str, Any] | None] = {}
    unique = sorted({str(p["nuitee_hotel_id"]).strip() for p in targets})
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for nid, detail in zip(unique, ex.map(fetch_detail, unique)):
            cache[nid] = detail
    rows = []
    for p in targets:
        nid = str(p["nuitee_hotel_id"]).strip()
        status, km, lite_name = classify(p.get("name") or "", p.get("lat"), p.get("lng"), cache.get(nid))
        rows.append(
            {
                "id": p["id"],
                "name": p.get("name"),
                "liteapiId": nid,
                "liteapiName": lite_name,
                "km": None if km is None else round(km, 1),
                "status": status,
            }
        )
    return {"counts": dict(Counter(r["status"] for r in rows)), "rows": rows}


def update_policy(policy_path: Path, rows: list[dict[str, Any]]) -> tuple[int, int]:
    """Merge verified/mismatch results into the policy file. Returns (verified_total, blocked_added)."""
    raw = json.loads(policy_path.read_text(encoding="utf-8"))
    blocks = dict(raw.get("blockLiveRates") or {})
    verified = set(raw.get("verifiedLiveRates") or [])
    added = 0
    for r in rows:
        if r["status"] == "mismatch":
            verified.discard(r["id"])
            if r["id"] not in blocks:
                added += 1
            blocks[r["id"]] = f"id_mismatch: LiteAPI id is '{r['liteapiName']}', {r['km']} km away"
        else:
            if r["status"] == "verified":
                verified.add(r["id"])
            if str(blocks.get(r["id"], "")).startswith("id_mismatch"):
                del blocks[r["id"]]  # an earlier automatic block that no longer applies
    raw["blockLiveRates"] = dict(sorted(blocks.items()))
    raw["verifiedLiveRates"] = sorted(verified)
    raw["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    policy_path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(verified), added


def main(argv: list[str]) -> int:
    write = "--write" in argv
    key = os.environ.get("NUITEE_API_KEY", "").strip()
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SECRET_KEY", "")
    if not (key and sb_url and sb_key):
        print("Missing NUITEE_API_KEY, SUPABASE_URL or SUPABASE_SECRET_KEY in the environment.", file=sys.stderr)
        return 2

    from enrich_missing_hotels import sb_get_all  # same Supabase reader the enrichment script uses

    props = sb_get_all(sb_url, sb_key, "properties", "id,name,lat,lng,nuitee_hotel_id")
    policy = load_policy(POLICY_PATH)
    result = verify(
        props,
        lambda nid: ((nuitee_get(f"/v3.0/data/hotel?hotelId={nid}", key) or {}).get("data")),
        skip_ids=set(policy["officialSites"]),
    )
    rows = result["rows"]
    print(f"Checked {len(rows)} properties: {result['counts']}")
    mism = [r for r in rows if r["status"] == "mismatch"]
    for r in sorted(mism, key=lambda x: -(x["km"] or 0)):
        print(f"  MISMATCH {r['id']}: ours '{r['name']}' vs LiteAPI '{r['liteapiName']}' ({r['km']} km)")

    REPORT_PATH.write_text(
        json.dumps(
            {
                "checkedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "counts": result["counts"],
                "mismatch": mism,
                "conflict": [r for r in rows if r["status"] == "conflict"],
                "unchecked": [r for r in rows if r["status"] == "unchecked"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    if write:
        verified_total, added = update_policy(POLICY_PATH, rows)
        print(f"Policy updated: {verified_total} verified ids, {added} newly blocked")
    else:
        print("Report only (no --write): policy file unchanged")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
