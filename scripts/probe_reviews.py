#!/usr/bin/env python3
"""Read-only probe: what guest-review data LiteAPI's /data/reviews returns for a few hotels (counts, sources, sentiment).

Writes nothing to the database. Env: SUPABASE_URL, SUPABASE_SECRET_KEY, NUITEE_API_KEY
"""
from __future__ import annotations

import collections
import json
import os
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb_all  # noqa: E402
from sync_250_hotels import nuitee_get  # noqa: E402

IDS = sys.argv[1:] or [
    "cheval-blanc-paris", "rosewood-hong-kong", "forestis-dolomites", "corte-della-maesta",
    "desert-rock-resort", "bawah-reserve", "capella-bangkok", "the-upper-house-hong-kong",
]


def main() -> int:
    key = os.environ["NUITEE_API_KEY"]
    props = {p["id"]: p for p in sb_all("properties", "id,name,nuitee_hotel_id")}
    for pid in IDS:
        p = props.get(pid)
        if not p or not p.get("nuitee_hotel_id"):
            print(f"\n== {pid}: no LiteAPI id")
            continue
        hid = p["nuitee_hotel_id"]
        det = (nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(hid)}", key) or {}).get("data") or {}
        print(f"\n== {pid} ({p['name']}) liteapi={hid} detail rating={det.get('rating')} reviewCount={det.get('reviewCount')}")
        res = nuitee_get(f"/v3.0/data/reviews?hotelId={urllib.parse.quote(hid)}&limit=1000&getSentiment=true&timeout=30", key) or {}
        rows = res.get("data") or []
        srcs = collections.Counter(str(r.get("source") or "?") for r in rows)
        scores = [float(r["averageScore"]) for r in rows if isinstance(r.get("averageScore"), (int, float))]
        dates = sorted(str(r.get("date") or "")[:10] for r in rows if r.get("date"))
        print(f"   reviews returned: {len(rows)}  sources: {dict(srcs)}")
        if scores:
            print(f"   mean score: {sum(scores) / len(scores):.2f}/10 over {len(scores)}  dates {dates[0] if dates else '?'} .. {dates[-1] if dates else '?'}")
        other = {k: v for k, v in res.items() if k != "data"}
        print("   other keys:", json.dumps(other, ensure_ascii=False)[:1500])
        for r in rows[:2]:
            print("   sample:", json.dumps({k: r.get(k) for k in ("source", "date", "averageScore", "headline", "pros", "cons", "type", "country")}, ensure_ascii=False)[:500])
    return 0


if __name__ == "__main__":
    sys.exit(main())
