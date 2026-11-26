#!/usr/bin/env python3
"""Re-check prices for the 'best value' insight, carefully.

For every hotel guests rate 95+ (300+ reviews) that has a LiteAPI id:
  1. confirm the LiteAPI id really is our hotel (name + town from /data/hotel, strict name rule), else skip it;
  2. price 2 nights for 2 adults on three dates (about 1, 2 and 4 months out) and keep the cheapest room each time;
  3. the value price = the middle of the three (so one odd cheap date can't make a hotel look like a bargain).
Saved to data/value-check.json with the dates, room names and the LiteAPI name, so every figure can be checked.
Env: NUITEE_API_KEY.
"""
from __future__ import annotations

import json
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_insights import _guest  # noqa: E402
from strict_names import same_hotel  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KEY = os.environ.get("NUITEE_API_KEY", "")
H = {"X-API-Key": KEY, "Accept": "application/json", "Content-Type": "application/json"}


def call(url: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers=H, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        print(f"  warn {url.split('?')[0][-30:]}: {e}")
        return {}


def rates(ids: list[str], ci: date) -> dict[str, tuple[float, str]]:
    d = call("https://api.liteapi.travel/v3.0/hotels/rates", {
        "hotelIds": ids, "checkin": ci.isoformat(), "checkout": (ci + timedelta(days=2)).isoformat(),
        "currency": "GBP", "guestNationality": "GB", "occupancies": [{"adults": 2}]})
    out = {}
    for row in d.get("data") or []:
        best = None
        for rt in row.get("roomTypes") or []:
            amt = (rt.get("offerRetailRate") or {}).get("amount")
            name = ((rt.get("rates") or [{}])[0].get("name") or "")
            if amt and float(amt) > 40 and (best is None or float(amt) < best[0]):
                best = (float(amt), name)
        if best:
            out[str(row.get("hotelId"))] = (round(best[0] / 2), best[1])
    return out


def main() -> int:
    if not KEY:
        sys.exit("NUITEE_API_KEY missing")
    hotels = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]
    cands = []
    for h in hotels:
        g, rc = _guest(h)
        if g is not None and g >= 95 and (rc or 0) >= 300 and h.get("nuiteeHotelId"):
            cands.append((h, g, rc))
    print(f"Value check: {len(cands)} hotels with guest score 95+ from 300+ reviews")
    ok = []
    for h, g, rc in cands:
        info = (call("https://api.liteapi.travel/v3.0/data/hotel?" + urllib.parse.urlencode({"hotelId": h["nuiteeHotelId"]})).get("data") or {})
        lname, lcity = info.get("name") or "", info.get("city") or ""
        good = bool(lname) and same_hotel(h["name"], lname, f"{h.get('location') or ''} {lcity}", h.get("country") or "")
        ok.append((h, g, rc, lname, good))
        time.sleep(0.15)
    matched = [x for x in ok if x[4]]
    print(f"Value check: LiteAPI id confirmed for {len(matched)}; {len(ok) - len(matched)} skipped (name mismatch)")
    for h, g, rc, lname, good in ok:
        if not good:
            print(f"  skip {h['id']}: LiteAPI says '{lname}'")
    today = date.today()
    windows = [today + timedelta(days=d) for d in (30, 60, 120)]
    ids = [x[0]["nuiteeHotelId"] for x in matched]
    per = {w: {} for w in windows}
    for w in windows:
        for i in range(0, len(ids), 35):
            per[w].update(rates(ids[i:i + 35], w))
            time.sleep(0.3)
    out = {}
    for h, g, rc, lname, _ in matched:
        nid = h["nuiteeHotelId"]
        got = [(w.isoformat(), *per[w][nid]) for w in windows if nid in per[w]]
        if len(got) < 2:
            continue
        mid = int(st.median([p for _, p, _ in got]))
        out[h["id"]] = {"name": h["name"], "liteapiName": lname, "g": g, "rc": rc, "nightlyGbp": mid,
                        "dates": [{"checkin": d, "nightlyGbp": p, "room": r} for d, p, r in got]}
    data = {"checked": today.isoformat(), "method": "2 nights, 2 adults, cheapest room on 3 dates (about 1, 2 and 4 months out); value price = middle of the three",
            "hotels": dict(sorted(out.items(), key=lambda kv: kv[1]["nightlyGbp"]))}
    (ROOT / "data" / "value-check.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in list(data["hotels"].items())[:15]:
        print(f"  £{v['nightlyGbp']}: {v['name']} ({v['g']}) · " + ", ".join(f"{x['checkin']} £{x['nightlyGbp']}" for x in v["dates"]))
    print(f"Value check: priced {len(out)} hotels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
