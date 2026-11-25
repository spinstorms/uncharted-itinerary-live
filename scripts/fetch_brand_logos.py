#!/usr/bin/env python3
"""Download the brand logos listed in data/brand-logos.json (Wikimedia Commons) into assets/brand-logos/ as small PNGs."""
from __future__ import annotations

import io
import json
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; brand logos with Commons attribution)"}


def main() -> int:
    cfg = json.loads((ROOT / "data" / "brand-logos.json").read_text(encoding="utf-8"))["brands"]
    (ROOT / "assets" / "brand-logos").mkdir(parents=True, exist_ok=True)
    n = 0
    for brand, o in cfg.items():
        out = ROOT / o["file"]
        try:
            raw = urllib.request.urlopen(urllib.request.Request(o["source"], headers=UA), timeout=30).read()
            im = Image.open(io.BytesIO(raw)).convert("RGBA")
            corner = im.getpixel((0, 0))
            if corner[3] == 255 and sum(corner[:3]) < 735:  # flat coloured backdrop (e.g. a JPG): make it transparent
                px = im.load()
                for yy in range(im.height):
                    for xx in range(im.width):
                        c = px[xx, yy]
                        if sum(abs(c[k] - corner[k]) for k in range(3)) < 40:
                            px[xx, yy] = (255, 255, 255, 0)
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            flat = Image.alpha_composite(bg, im).convert("RGB")
            box = im.getchannel("A").getbbox() if corner[3] == 255 and sum(corner[:3]) < 735 else \
                ImageChops.difference(flat, Image.new("RGB", flat.size, (255, 255, 255))).getbbox()
            if box:
                im = im.crop(box)
            im.thumbnail((240, 72), Image.Resampling.LANCZOS)
            im.save(out, "PNG", optimize=True)
            n += 1
            print(f"  {brand}: {im.size}")
        except Exception as e:  # noqa: BLE001
            print(f"  {brand}: failed ({e})")
    print(f"Brand logos: {n} saved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
