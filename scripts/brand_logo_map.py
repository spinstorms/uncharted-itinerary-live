#!/usr/bin/env python3
"""Brand -> logo lookups shared by the build.

data/brand-logos.json   brand name -> logo file (+ source)
data/brand-raw-map.json raw hotel 'brand' string -> leaderboard brand names (same order as getBrandCategories in JS)
Writes assets/brand-logos/map.json for the browser (brand leaderboard).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str) -> dict:
    try:
        return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


LOGOS = {k: v for k, v in (_load("brand-logos.json").get("brands") or {}).items() if (ROOT / v.get("file", "~")).exists()}
RAW = _load("brand-raw-map.json")


def logo_for_brand(name: str | None) -> tuple[str, str] | None:
    """(site path, brand name) for a leaderboard brand name, or None."""
    if name and name in LOGOS:
        return "/" + LOGOS[name]["file"], name
    return None


def logo_for_hotel(raw_brand: str | None) -> tuple[str, str] | None:
    """Most specific logo for a hotel's brand string: its own brand first, then its collection or parent group."""
    if not raw_brand:
        return None
    for cand in [raw_brand] + list(RAW.get(raw_brand) or []):
        got = logo_for_brand(cand)
        if got:
            return got
    return None


def write_browser_map() -> Path:
    out = ROOT / "assets" / "brand-logos" / "map.json"
    out.write_text(json.dumps({k: "/" + v["file"] for k, v in sorted(LOGOS.items())}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(write_browser_map())
