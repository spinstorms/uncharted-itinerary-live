#!/usr/bin/env python3
"""Apply the hand corrections in data/property-corrections.json to the database (PATCH by property id).

A value of "from data/hotels.json" copies that field from the first-hand hotel list (used for Shorts lists).
Env: SUPABASE_URL, SUPABASE_SECRET_KEY.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY = {"properties": "id", "property_facts": "property_id", "first_hand_reviews": "property_id"}


def main() -> int:
    cfg = json.loads((ROOT / "data" / "property-corrections.json").read_text(encoding="utf-8"))
    visited = {h["id"]: h for h in json.loads((ROOT / "data" / "hotels.json").read_text(encoding="utf-8"))["hotels"]}
    n = 0
    for table, col in KEY.items():
        for pid, fields in (cfg.get(table) or {}).items():
            body = {k: (visited.get(pid, {}).get(k) if v == "from data/hotels.json" else v) for k, v in fields.items()}
            try:
                sb("PATCH", f"/rest/v1/{table}?{col}=eq.{urllib.parse.quote(pid)}", body, {"Prefer": "return=minimal"})
                n += 1
                print(f"  {table} {pid}: {', '.join(body)}")
            except Exception as e:  # noqa: BLE001
                print(f"  {table} {pid}: failed ({e})")
    print(f"Corrections: {n} applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
