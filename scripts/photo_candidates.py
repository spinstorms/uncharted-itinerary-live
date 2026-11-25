#!/usr/bin/env python3
"""Read-only: save candidate hotel photos (LiteAPI images with captions, then Google Places photos) for review.

Usage: photo_candidates.py OUT_DIR id1 id2 ...   (ids from data/stayodds-directory.json)
Writes OUT_DIR/<id>/NN.jpg (small previews) and OUT_DIR/index.json with each photo's source, caption, url and credit.
Env: NUITEE_API_KEY, GOOGLE_PLACES_API_KEY
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OVERVIEW = ("aerial", "exterior", "facade", "property grounds", "view from property", "beach", "pool", "outdoor", "garden",
            "building", "overview", "lobby", "terrace", "island")


def get(url: str, headers: dict[str, str], timeout: int = 25) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return r.read()


def small(raw: bytes) -> bytes:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.thumbnail((480, 320))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=72)
    return b.getvalue()


def main() -> int:
    out = Path(sys.argv[1])
    ids = [a for a in sys.argv[2:] if not a.startswith("--")]
    hs = {h["id"]: h for h in json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]}
    lk, gk = os.environ.get("NUITEE_API_KEY", ""), os.environ.get("GOOGLE_PLACES_API_KEY", "")
    index: dict[str, list] = {}
    if "--current" in sys.argv:  # review sheets of every hotel whose card photo is a remote URL
        from PIL import ImageDraw
        rem = [h for h in hs.values() if str(h.get("thumbnail") or "").startswith("http")]
        out.mkdir(parents=True, exist_ok=True)
        W, H, cols, per = 170, 96, 10, 80
        order = []
        for sidx in range(0, len(rem), per):
            chunk = rem[sidx:sidx + per]
            rows = (len(chunk) + cols - 1) // cols
            sheet = Image.new("RGB", (cols * W, rows * (H + 12)), "white")
            dr = ImageDraw.Draw(sheet)
            for i, h in enumerate(chunk):
                n = sidx + i
                order.append([n, h["id"]])
                try:
                    im = Image.open(io.BytesIO(get(h["thumbnail"], {"User-Agent": "Mozilla/5.0"}))).convert("RGB").resize((W - 4, H))
                    sheet.paste(im, ((i % cols) * W, (i // cols) * (H + 12)))
                except Exception:  # noqa: BLE001
                    pass
                dr.text(((i % cols) * W + 2, (i // cols) * (H + 12) + H), str(n), fill="black")
            sheet.save(out / f"cur-{sidx // per:02d}.jpg", quality=60)
        (out / "index.json").write_text(json.dumps(order), encoding="utf-8")
        return 0
    if "--best" in sys.argv:  # top 3 overview-looking LiteAPI photos per hotel, as review sheets
        from PIL import ImageDraw
        GOOD = ("aerial", "exterior", "building", "facade", "view from property", "beach", "property grounds", "garden",
                "landmark", "overview", "pool", "balance & terrace", "terrace", "island", "outdoor")
        BAD = ("bath", "room", "bed", "restaurant", "food", "bar", "spa", "fitness", "gym", "meeting", "lounge", "lobby",
               "recepcion", "kitchen", "suite", "dining", "interior", "breakfast", "toilet", "shower", "sauna")
        def rank(i):
            c = str(i.get("caption") or "").lower()
            return (0 if any(k in c for k in GOOD) else (2 if any(k in c for k in BAD) else 1), i.get("order") or 0)
        rows = []
        for pid in ids:
            h = hs.get(pid) or {}
            if not h.get("nuiteeHotelId"):
                continue
            try:
                d = json.loads(get(f"https://api.liteapi.travel/v3.0/data/hotel?hotelId={urllib.parse.quote(h['nuiteeHotelId'])}",
                                   {"X-API-Key": lk, "Accept": "application/json"}))["data"]
            except Exception as e:  # noqa: BLE001
                print(pid, e); continue
            imgs = sorted([i for i in d.get("hotelImages") or [] if isinstance(i, dict)], key=rank)
            picks = []
            for i in imgs:
                if len(picks) >= 3:
                    break
                u = i.get("urlHd") or i.get("url")
                try:
                    raw = get(u, {"User-Agent": "Mozilla/5.0"})
                    im = Image.open(io.BytesIO(raw)).convert("RGB")
                    if im.width < 700:
                        continue
                    picks.append({"url": u, "caption": i.get("caption") or "", "w": im.width, "im": im})
                except Exception:  # noqa: BLE001
                    continue
            index[pid] = [{k: v for k, v in pk.items() if k != "im"} for pk in picks]
            rows.append((pid, picks))
        out.mkdir(parents=True, exist_ok=True)
        W, H, per = 300, 170, 12
        for sidx in range(0, len(rows), per):
            chunk = rows[sidx:sidx + per]
            sheet = Image.new("RGB", (260 + 3 * W, len(chunk) * (H + 6)), "white")
            dr = ImageDraw.Draw(sheet)
            for r, (pid, picks) in enumerate(chunk):
                y = r * (H + 6)
                dr.text((4, y + 60), f"{sidx + r} {pid[:34]}", fill="black")
                for k, pk in enumerate(picks):
                    im = pk["im"].copy(); im.thumbnail((W - 6, H))
                    sheet.paste(im, (260 + k * W, y))
                    dr.text((262 + k * W, y + H - 12), f"{k} {pk['caption'][:22]}", fill="yellow")
            sheet.save(out / f"best-{sidx // per:02d}.jpg", quality=70)
        (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
        return 0
    if "--names" in sys.argv:  # just print what each stored id points at
        for pid in ids:
            h = hs.get(pid) or {}
            ln = gn = ""
            try:
                if h.get("nuiteeHotelId"):
                    d = json.loads(get(f"https://api.liteapi.travel/v3.0/data/hotel?hotelId={urllib.parse.quote(h['nuiteeHotelId'])}",
                                       {"X-API-Key": lk, "Accept": "application/json"}))["data"]
                    ln = f"{d.get('name')} | {d.get('address')} | {d.get('city')}"
                if h.get("googlePlaceId"):
                    d = json.loads(get(f"https://places.googleapis.com/v1/places/{urllib.parse.quote(h['googlePlaceId'])}",
                                       {"X-Goog-Api-Key": gk, "X-Goog-FieldMask": "displayName,formattedAddress"}))
                    gn = f"{(d.get('displayName') or {}).get('text')} | {d.get('formattedAddress')}"
            except Exception as e:  # noqa: BLE001
                ln += f" error {e}"
            print(f"NAMES {pid} [{h.get('name')}] liteapi={h.get('nuiteeHotelId')}: {ln} || google: {gn}")
            index[pid] = [{"liteapi": ln, "google": gn}]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
        return 0
    for pid in ids:
        h = hs.get(pid) or {}
        cands: list[dict] = []
        if h.get("nuiteeHotelId") and lk:
            try:
                d = json.loads(get(f"https://api.liteapi.travel/v3.0/data/hotel?hotelId={urllib.parse.quote(h['nuiteeHotelId'])}",
                                   {"X-API-Key": lk, "Accept": "application/json"}))["data"]
                imgs = [i for i in d.get("hotelImages") or [] if isinstance(i, dict)]
                imgs.sort(key=lambda i: (not any(k in str(i.get("caption") or "").lower() for k in OVERVIEW), i.get("order") or 0))
                for i in imgs[:10]:
                    cands.append({"source": "liteapi", "caption": i.get("caption") or "", "url": i.get("urlHd") or i.get("url")})
            except Exception as e:  # noqa: BLE001
                print(pid, "liteapi", e)
        if h.get("googlePlaceId") and gk:
            try:
                d = json.loads(get(f"https://places.googleapis.com/v1/places/{urllib.parse.quote(h['googlePlaceId'])}",
                                   {"X-Goog-Api-Key": gk, "X-Goog-FieldMask": "photos"}))
                for ph in (d.get("photos") or [])[:8]:
                    credit = ", ".join(a.get("displayName", "") for a in ph.get("authorAttributions") or [])
                    cands.append({"source": "google", "caption": "", "credit": credit, "name": ph["name"],
                                  "url": f"https://places.googleapis.com/v1/{ph['name']}/media?maxWidthPx=1600"})
            except Exception as e:  # noqa: BLE001
                print(pid, "google", e)
        if h.get("videoId"):  # our own review video: its cover and YouTube's three automatic frames
            v = h["videoId"]
            for nm in ("maxresdefault", "maxres1", "maxres2", "maxres3", "hq1", "hq2", "hq3"):
                cands.append({"source": "youtube", "caption": nm, "url": f"https://i.ytimg.com/vi/{v}/{nm}.jpg"})
        if "--no-google" in sys.argv:
            cands = [c for c in cands if c["source"] != "google"]
        (out / pid).mkdir(parents=True, exist_ok=True)
        kept = []
        for n, c in enumerate(cands):
            try:
                url = c["url"] + (f"&key={gk}" if c["source"] == "google" else "")
                (out / pid / f"{n:02d}.jpg").write_bytes(small(get(url, {"User-Agent": "Mozilla/5.0"})))
                kept.append({**c, "file": f"{pid}/{n:02d}.jpg"})
            except Exception as e:  # noqa: BLE001
                print(pid, n, e)
        index[pid] = kept
        print(pid, len(kept), "photos")
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
