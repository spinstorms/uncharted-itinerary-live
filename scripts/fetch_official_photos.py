#!/usr/bin/env python3
"""Save the official hotel photos listed in data/gallery-manual.json ("photos") as assets/card-photos/<id>.webp (1600px)."""
import io
import json
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
photos = json.loads((ROOT / "data" / "gallery-manual.json").read_text(encoding="utf-8")).get("photos") or {}
for hid, url in photos.items():
    out = ROOT / "assets" / "card-photos" / f"{hid}.webp"
    if out.exists():
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (StayOdds hotel directory)"})
        with urllib.request.urlopen(req, timeout=40) as r:
            im = Image.open(io.BytesIO(r.read())).convert("RGB")
        im.thumbnail((1600, 1600))
        if im.width < 600:
            print(f"[skip] {hid}: too small ({im.width}px)")
            continue
        im.save(out, "WEBP", quality=82)
        print(f"[ok] {hid} {im.size}")
    except Exception as e:  # noqa: BLE001
        print(f"[fail] {hid}: {e}")
