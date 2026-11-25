#!/usr/bin/env python3
"""Replace a hotel's card photo with a hand-picked overview photo (data/card-photo-overrides.json).

Each entry: {"url": ..., "source": "liteapi" | "youtube", "note": ...}. Downloads the photo, saves an 800x450 WebP to
assets/card-photos/<id>.webp, and (unless --no-db) sets properties.hero_image_url so the app shows the same photo.
Env: SUPABASE_URL, SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import io
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    cfg = json.loads((ROOT / "data" / "card-photo-overrides.json").read_text(encoding="utf-8"))["hotels"]
    done = 0
    for pid, o in cfg.items():
        out = ROOT / "assets" / "card-photos" / f"{pid}.webp"
        try:
            req = urllib.request.Request(o["url"], headers={"User-Agent": "Mozilla/5.0 StayOdds/1.0"})
            raw = urllib.request.urlopen(req, timeout=30).read()
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
            if im.width < 600:
                print(f"  {pid}: photo too small ({im.width}px), skipped")
                continue
            ImageOps.fit(im, (800, 450), method=Image.Resampling.LANCZOS).save(out, "WEBP", quality=80, method=6)
            done += 1
            print(f"  {pid}: saved ({o.get('source')})")
        except Exception as e:  # noqa: BLE001
            print(f"  {pid}: failed ({e})")
            continue
        if "--no-db" not in sys.argv and o.get("source") == "liteapi":
            try:
                from add_award_hotels import sb
                sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(pid)}",
                   {"hero_image_url": o["url"], "image_license_source": "nuitee_connect"}, {"Prefer": "return=minimal"})
            except Exception as e:  # noqa: BLE001
                print(f"  {pid}: database not updated ({e})")
    print(f"Card photos: {done} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
