#!/usr/bin/env python3
"""StayOdds live-rate / indicative-price coverage policy.

Why this exists
---------------
Each hotel carries a LiteAPI id (``nuiteeHotelId``) that was matched by name. For one-word
names that match can land on a lookalike in the same country (Amandari in Ubud was matched
to a budget hotel, so the page showed "From £50/nt"). That one id feeds both the on-demand
"Check Live Rate" button and the indicative "From £X/nt" snapshot.

This module decides, per hotel, whether those prices can be trusted. Where they cannot:
  * ``nuiteeHotelId`` and ``priceSnapshot`` are removed (no wrong price is ever shown),
  * ``liveRateUnavailable`` records why, so the pages can say so and suggest alternatives,
  * for hotels not sold through Booking.com (see ``officialSites`` in
    data/live-rate-coverage.json) the booking link is switched to the official site.

Run on its own to clean the committed data files (safe to re-run):
    python3 scripts/live_rate_policy.py            # apply
    python3 scripts/live_rate_policy.py --check    # report only, change nothing
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "data" / "live-rate-coverage.json"
HOTEL_FILES = ("stayodds-directory.json", "stayodds-index.json", "stayodds-visited.json")
SNAPSHOT_FILE = "price-snapshots.json"

DEFAULT_MIN_NIGHTLY_GBP = 90
DEFAULT_MIN_SHARE_OF_FLOOR = 0.35


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {
        "minPlausibleNightlyGbp": raw.get("minPlausibleNightlyGbp", DEFAULT_MIN_NIGHTLY_GBP),
        "minShareOfStatedPriceFloor": raw.get("minShareOfStatedPriceFloor", DEFAULT_MIN_SHARE_OF_FLOOR),
        "officialSites": dict(raw.get("officialSites") or {}),
        "blockLiveRates": dict(raw.get("blockLiveRates") or {}),
        "verifiedLiveRates": set(raw.get("verifiedLiveRates") or []),
    }


def blocked_ids(policy: dict[str, Any] | None = None) -> set[str]:
    """Ids that are blocked by the policy file itself (used to skip pointless API calls)."""
    p = policy or load_policy()
    return (set(p["officialSites"]) | set(p["blockLiveRates"])) - p["verifiedLiveRates"]


def _price_floor(price_range: Any) -> int | None:
    m = re.search(r"£\s*([\d,]+)", str(price_range or ""))
    return int(m.group(1).replace(",", "")) if m else None


def compute_decisions(hotels: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, str]:
    """Return {hotel id: reason} for every hotel whose live/indicative price must be hidden."""
    p = policy or load_policy()
    id_counts = Counter(str(h["nuiteeHotelId"]).strip() for h in hotels if h.get("nuiteeHotelId"))
    decisions: dict[str, str] = {}
    for h in hotels:
        hid = h.get("id")
        if not hid:
            continue
        if hid in p["officialSites"]:
            decisions[hid] = "official_site_only"
            continue
        if hid in p["verifiedLiveRates"]:
            continue
        if hid in p["blockLiveRates"]:
            decisions[hid] = str(p["blockLiveRates"][hid] or "blocked")
            continue
        nid = h.get("nuiteeHotelId")
        if nid and id_counts[str(nid).strip()] > 1:
            decisions[hid] = "duplicate_id"
            continue
        nightly = (h.get("priceSnapshot") or {}).get("nightlyGbp")
        if nightly:
            floor = _price_floor(h.get("priceRange"))
            if nightly < p["minPlausibleNightlyGbp"] or (
                floor and nightly < floor * p["minShareOfStatedPriceFloor"]
            ):
                decisions[hid] = "price_implausible"
    return decisions


def apply_decisions(
    hotels: list[dict[str, Any]], decisions: dict[str, str], policy: dict[str, Any] | None = None
) -> int:
    """Mutate hotels in place. Safe to call repeatedly. Returns how many records were touched."""
    p = policy or load_policy()
    touched = 0
    for h in hotels:
        reason = decisions.get(h.get("id"))
        if not reason:
            continue
        touched += 1
        h.pop("nuiteeHotelId", None)
        h.pop("priceSnapshot", None)
        h["liveRateUnavailable"] = reason
        site = p["officialSites"].get(h["id"])
        if not site:
            continue
        h["officialSite"] = {"partner": site["partner"], "url": site["url"]}
        h["bookingUrl"] = site["url"]
        links = h.get("bookingLinks")
        if isinstance(links, list):
            if any(isinstance(x, dict) and x.get("partnerName") == site["partner"] for x in links):
                continue
            official = {
                "channelType": "direct_brand",
                "partnerName": site["partner"],
                "url": site["url"],
                "mobileAllowed": True,
                "perksSummary": "Official rates & availability",
                "priority": 1,
            }
            kept = [
                x
                for x in links
                if not (
                    isinstance(x, dict)
                    and (x.get("partnerName") == "Booking.com" or "booking.com" in str(x.get("url", "")).lower())
                )
            ]
            h["bookingLinks"] = [official] + kept
    return touched


def apply_live_rate_policy(hotels: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, str]:
    """Compute and apply in one step (used by the site build). Returns the decisions."""
    p = policy or load_policy()
    decisions = compute_decisions(hotels, p)
    apply_decisions(hotels, decisions, p)
    return decisions


def _dump(obj: Any, compact: bool) -> str:
    if compact:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    policy = load_policy()
    data_dir = ROOT / "data"
    directory = json.loads((data_dir / "stayodds-directory.json").read_text(encoding="utf-8"))
    decisions = compute_decisions(directory["hotels"], policy)

    by_reason = Counter(decisions.values())
    print(f"Hotels affected: {len(decisions)} -> {dict(by_reason)}")
    for reason in ("duplicate_id", "price_implausible"):
        ids = sorted(i for i, r in decisions.items() if r == reason)
        if ids:
            print(f"  {reason}: {', '.join(ids)}")
    if check_only:
        print("--check: no files changed")
        return 0

    for name in HOTEL_FILES:
        path = data_dir / name
        if not path.exists():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        n = apply_decisions(doc["hotels"], decisions, policy)
        path.write_text(_dump(doc, compact=True), encoding="utf-8")
        print(f"  {name}: {n} records updated")

    snap_path = data_dir / SNAPSHOT_FILE
    if snap_path.exists():
        snap = json.loads(snap_path.read_text(encoding="utf-8"))
        prices = snap.get("prices") or {}
        removed = [i for i in decisions if i in prices]
        for i in removed:
            del prices[i]
        if "count" in snap:
            snap["count"] = len(prices)
        snap_path.write_text(_dump(snap, compact=False), encoding="utf-8")
        print(f"  {SNAPSHOT_FILE}: {len(removed)} snapshots removed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
