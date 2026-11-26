#!/usr/bin/env python3
"""Telegraph hotel review scores (x/10) from data/isthewaterfree.json -> editorial_ratings, so they count in the critics score.

Only published numeric critic scores are added. Reader polls (Conde Nast Readers' Choice, Travel + Leisure) and LaListe
(which blends in traveller reviews, so would double-count guests) stay as awards, never points.
Env: SUPABASE_URL, SUPABASE_SECRET_KEY.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import now_iso, sb_all, upsert  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TEL = re.compile(r"The Telegraph review (\d{4}):\s*(\d+(?:\.\d+)?)/10", re.I)


def main() -> int:
    data = json.loads((ROOT / "data" / "isthewaterfree.json").read_text(encoding="utf-8"))
    have = {(r["property_id"]) for r in sb_all("editorial_ratings", "property_id,source_name") if "telegraph" in str(r.get("source_name") or "").lower()}
    rows = []
    for pid, v in data.items():
        if pid.startswith("_") or pid in have:
            continue
        for c in v.get("critics") or []:
            m = TEL.search(c)
            if not m:
                continue
            year, score = m.group(1), float(m.group(2))
            if not 0 < score <= 10:
                continue
            rows.append({"property_id": pid, "source_name": "The Telegraph", "source_url": v["url"],
                         "raw_score": f"{score:g}/10", "normalized_100": int(round(score * 10)),
                         "takeaway": f"The Telegraph's {year} review scored it {score:g}/10 (as listed by isthewaterfree.com).",
                         "verified_at": now_iso()})
            break
    print(f"Telegraph: adding {len(rows)} published review scores ({len(have)} hotels already had one)")
    if rows:
        upsert("editorial_ratings", rows, "property_id,source_name,source_url")
    return 0


if __name__ == "__main__":
    sys.exit(main())
