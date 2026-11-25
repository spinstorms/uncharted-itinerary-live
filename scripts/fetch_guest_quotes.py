#!/usr/bin/env python3
"""Real guest comments for every hotel, from LiteAPI's /data/reviews feed (reviews written by guests, with their date,
source and own score). No AI sentiment or AI category ratings are requested or stored.

  * Skips hotels whose LiteAPI id is blocked as a wrong match (data/live-rate-coverage.json), so no other hotel's
    reviews can be attached.
  * Keeps the most recent reviews that have written text, whatever their score (no cherry-picking), preferring
    English text, up to 4 per hotel.
  * Writes data/guest-quotes.json: {hotel_id: {"fetched": date, "provider": "LiteAPI", "quotes": [...]}}

Env: SUPABASE_URL, SUPABASE_SECRET_KEY, NUITEE_API_KEY
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb_all  # noqa: E402
from sync_250_hotels import nuitee_get  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "guest-quotes.json"
SOURCE_NAMES = {"tripadvisor": "Tripadvisor", "nuitee": "Verified booking guest", "booking": "Booking.com", "expedia": "Expedia"}


def clean(s: Any) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:420] + ("…" if len(s) > 420 else "")


def quotes_for(hid: str, key: str) -> tuple[list[dict[str, Any]], int | None]:
    res = nuitee_get(f"/v3.0/data/reviews?hotelId={urllib.parse.quote(hid)}&limit=200&timeout=20", key) or {}
    rows = res.get("data") or []
    out = []
    for r in rows:
        pros, cons, head = clean(r.get("pros")), clean(r.get("cons")), clean(r.get("headline"))
        if len(pros) + len(cons) + len(head) < 40:
            continue
        sc = r.get("averageScore")
        out.append({
            "date": str(r.get("date") or "")[:10],
            "source": SOURCE_NAMES.get(str(r.get("source") or "").lower(), str(r.get("source") or "Guest review").title()),
            "score": float(sc) if isinstance(sc, (int, float)) and 0 < float(sc) <= 10 else None,
            "travellerType": str(r.get("type") or "").replace("_", " "),
            "headline": head,
            "liked": pros,
            "disliked": cons,
            "language": str(r.get("language") or "").lower()[:2],
        })
    out.sort(key=lambda q: q["date"], reverse=True)
    seen, uniq = set(), []
    for q in out:  # the feed sometimes holds the same review twice (e.g. once per booking channel)
        sig = (q["date"], q["liked"][:60].lower(), q["disliked"][:60].lower(), q["headline"][:40].lower())
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(q)
    eng = [q for q in uniq if q["language"] == "en"]
    pick = (eng if len(eng) >= 2 else uniq)[:4]
    total = res.get("total") if isinstance(res.get("total"), int) else None
    return pick, total


def main() -> int:
    key = os.environ["NUITEE_API_KEY"]
    pol = json.loads((ROOT / "data" / "live-rate-coverage.json").read_text(encoding="utf-8"))
    blocked = set((pol.get("blockLiveRates") or {}).keys())
    props = [p for p in sb_all("properties", "id,name,nuitee_hotel_id") if p.get("nuitee_hotel_id")]
    todo = [p for p in props if p["id"] not in blocked and p["nuitee_hotel_id"] not in blocked]
    print(f"Guest quotes: {len(todo)} hotels with a verified LiteAPI id ({len(props) - len(todo)} skipped as unverified)")
    today = datetime.now(timezone.utc).date().isoformat()
    # Reuse what we already saved: each hotel is asked again at most every REFRESH_DAYS.
    try:
        saved = json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        saved = {}
    REFRESH_DAYS = 30
    cutoff = (datetime.now(timezone.utc).date().toordinal()) - REFRESH_DAYS
    todo_ids = {p["id"] for p in todo}
    result: dict[str, Any] = {
        k: v for k, v in saved.items()
        if k in todo_ids and datetime.fromisoformat(str(v.get("fetched", "1970-01-01"))).date().toordinal() >= cutoff
    }
    todo = [p for p in todo if p["id"] not in result]
    print(f"Guest quotes: {len(result)} reused from the saved copy, {len(todo)} to fetch")

    def work(p: dict[str, Any]) -> None:
        try:
            q, total = quotes_for(p["nuitee_hotel_id"], key)
        except Exception as e:  # noqa: BLE001
            print(f"  error {p['id']}: {e}")
            return
        if q:
            result[p["id"]] = {"fetched": today, "provider": "LiteAPI (Nuitée)", "reviewsInFeed": total, "quotes": q}

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(work, todo))
    OUT.write_text(json.dumps(dict(sorted(result.items())), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    nq = sum(len(v["quotes"]) for v in result.values())
    print(f"Guest quotes: {nq} real guest comments for {len(result)} hotels -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
