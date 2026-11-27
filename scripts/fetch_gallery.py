#!/usr/bin/env python3
"""Save a small photo gallery per hotel from LiteAPI (Nuitée) hotel details: free metadata endpoint, licensed photos.

Writes data/hotel-gallery.json: {"updatedAt", "hotels": {id: {"src": "liteapi", "liteapiId", "photos": [{"u", "c"}]}}}.
Hotels without a LiteAPI id are looked up by name + country, and only kept when the name matches closely;
those are listed under "matchedByName" so they can be checked by hand.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_250_hotels import COUNTRY_TO_ISO2, load_env_local, norm_tokens, nuitee_get  # noqa: E402
import urllib.parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "hotel-gallery.json"
MAX_PHOTOS = 8


def photos_from(detail: dict) -> list[dict]:
    imgs = detail.get("hotelImages") or []
    out, seen = [], set()
    imgs = sorted(imgs, key=lambda i: (not i.get("defaultImage"), i.get("order") or 999))
    for im in imgs:
        u = str(im.get("urlHd") or im.get("url") or "").strip()
        if not u.startswith("http") or u in seen:
            continue
        seen.add(u)
        out.append({"u": u, "c": str(im.get("caption") or "").strip()[:80]})
        if len(out) >= MAX_PHOTOS:
            break
    return out


def find_by_name(name: str, country: str, key: str) -> dict | None:
    iso2 = COUNTRY_TO_ISO2.get(country.lower())
    if not iso2:
        return None
    target = norm_tokens(name)
    qs = urllib.parse.urlencode({"countryCode": iso2, "hotelName": name, "limit": 8})
    items = ((nuitee_get(f"/v3.0/data/hotels?{qs}", key) or {}).get("data")) or []
    best, best_score = None, 0.0
    for it in items:
        cand = norm_tokens(str(it.get("name") or ""))
        if not cand:
            continue
        # exact name only: near-matches were other places ("Maçakızı yatch", "The Barn at Moor Hall")
        if cand == target:
            return it
    return None


def search(queries: list[str], key: str) -> None:
    """Print LiteAPI candidates for 'Name|CC' queries, so a hotel can be pinned by hand in data/gallery-manual.json."""
    for q in queries:
        name, cc = (q.split("|") + [""])[:2]
        qs = urllib.parse.urlencode({"countryCode": cc.strip(), "hotelName": name.strip(), "limit": 10})
        items = ((nuitee_get(f"/v3.0/data/hotels?{qs}", key) or {}).get("data")) or []
        print(f"## {q}")
        for it in items:
            print(f"   {it.get('id')} | {it.get('name')} | {it.get('city')} | {it.get('address')} | stars {it.get('stars')}")


def main() -> None:
    load_env_local()
    key = os.environ["NUITEE_API_KEY"].strip()
    if os.environ.get("GALLERY_SEARCH"):
        search([q for q in os.environ["GALLERY_SEARCH"].split(";") if q.strip()], key)
        return
    manual = {}
    mf = ROOT / "data" / "gallery-manual.json"
    if mf.exists():
        manual = json.loads(mf.read_text(encoding="utf-8")).get("liteapiIds") or {}
    hotels = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"hotels": {}}
    only = set(a for a in sys.argv[1:] if not a.startswith("--"))
    refresh = "--refresh" in sys.argv

    def work(h: dict):
        hid = h["id"]
        if only and hid not in only:
            return hid, old["hotels"].get(hid), None
        if not refresh and not only and old["hotels"].get(hid, {}).get("photos"):
            return hid, old["hotels"][hid], None
        lid = manual.get(hid) or h.get("nuiteeHotelId")
        by_name = None
        if not lid:
            m = find_by_name(h["name"], h.get("country") or "", key)
            if m:
                lid, by_name = m.get("id"), m.get("name")
        if not lid:
            return hid, None, None
        det = (nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(str(lid))}", key) or {}).get("data") or {}
        ph = photos_from(det)
        if not ph:
            return hid, None, None
        rec = {"src": "liteapi", "liteapiId": str(lid), "liteapiName": det.get("name") or by_name, "photos": ph}
        return hid, rec, (by_name and {"id": hid, "name": h["name"], "liteapiName": by_name, "liteapiId": lid})

    res, by_name = {}, []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for hid, rec, bn in ex.map(work, hotels):
            if rec:
                res[hid] = rec
            if bn:
                by_name.append(bn)
    OUT.write_text(json.dumps({"updatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "note": "LiteAPI (Nuitee) hotel photos, licensed for display with bookings. Max 8 per hotel.",
                               "matchedByName": sorted(by_name, key=lambda x: x["id"]),
                               "hotels": dict(sorted(res.items()))}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Galleries: {len(res)} hotels; matched by name: {len(by_name)}")


if __name__ == "__main__":
    main()
