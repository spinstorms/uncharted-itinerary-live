#!/usr/bin/env python3
"""Check every stored LiteAPI id points at OUR hotel: compare LiteAPI's name/town with ours, word by word.

Flags ids where LiteAPI's name has meaningful words ours doesn't (e.g. 'The Lodge at Ashford Castle' for Ashford
Castle) or misses words ours has. Output: data/liteapi-id-audit.json (for review; nothing is changed). Env: NUITEE_API_KEY.
"""
import json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
K = os.environ["NUITEE_API_KEY"]
H = {"X-API-Key": K, "Accept": "application/json"}
SOFT = set("the a an and at of by de du des la le les il el los las di del da do & hotel hotels hôtel resort resorts spa "
           "and luxury collection small world members leading autograph tribute portfolio relais chateaux châteaux "
           "all inclusive adults only couples caters to with club benefits ihg marriott hilton hyatt accor by "
           "wellness retreat beach boutique 5 star one five sea view golf country estate oetker best year 2026 die besten 101 "
           "a an".split())


def toks(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("bvlgari", "bulgari")
    return [t for t in re.findall(r"[a-z0-9]+", s)]


def info(hid):
    for _ in range(3):
        try:
            u = "https://api.liteapi.travel/v3.0/data/hotel?" + urllib.parse.urlencode({"hotelId": hid})
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                d = json.loads(r.read().decode()).get("data") or {}
            return d.get("name") or "", d.get("city") or "", d.get("country") or "", d.get("starRating")
        except Exception:
            time.sleep(2)
    return None


def main():
    hotels = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]
    rows = [h for h in hotels if h.get("nuiteeHotelId")]
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(lambda h: info(h["nuiteeHotelId"]), rows))
    flags = []
    for h, r in zip(rows, res):
        if not r:
            continue
        lname, lcity, lcountry, stars = r
        ours = set(toks(h["name"])); place = set(toks(h.get("location"))) | set(toks(lcity)) | set(toks(h.get("country")))
        theirs = set(toks(lname))
        extra = sorted(t for t in theirs - ours - place - SOFT if not t.isdigit())
        missing = sorted(t for t in ours - theirs - place - SOFT if not t.isdigit())
        if extra or missing:
            flags.append({"id": h["id"], "ours": h["name"], "liteapi": lname, "city": lcity, "stars": stars,
                          "extra": extra, "missing": missing, "nuitee": h["nuiteeHotelId"]})
    (ROOT / "data" / "liteapi-id-audit.json").write_text(json.dumps({"checked": len(rows), "flagged": flags}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"LiteAPI id audit: {len(rows)} checked, {len(flags)} flagged for review")
    for f in flags:
        print(f"  {f['id']}: ours '{f['ours']}' | LiteAPI '{f['liteapi']}' ({f['city']}, {f['stars']}*) extra={f['extra']} missing={f['missing']}")


if __name__ == "__main__":
    main()
