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
    man_path = ROOT / "assets" / "card-photos" / "sources.json"  # id -> source url already saved (download once only)
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    done = 0
    for pid, o in cfg.items():
        out = ROOT / "assets" / "card-photos" / f"{pid}.webp"
        if manifest.get(pid) == o["url"] and out.exists():
            continue
        try:
            req = urllib.request.Request(o["url"], headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", **({"Referer": o["site"]} if o.get("site") else {})})
            raw = urllib.request.urlopen(req, timeout=30).read()
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
            if im.width < 600:
                print(f"  {pid}: photo too small ({im.width}px), skipped")
                continue
            ImageOps.fit(im, (800, 450), method=Image.Resampling.LANCZOS).save(out, "WEBP", quality=80, method=6)
            done += 1
            manifest[pid] = o["url"]
            print(f"  {pid}: saved ({o.get('source')})")
        except Exception as e:  # noqa: BLE001
            print(f"  {pid}: failed ({e})")
            continue
        if "--no-db" not in sys.argv and o.get("source") in ("liteapi", "official", "commons"):
            try:
                from add_award_hotels import sb
                sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(pid)}",
                   {"hero_image_url": o["url"], "image_license_source": o.get("license_source") or ("nuitee_connect" if o.get("source") == "liteapi" else "hotel_official_site")}, {"Prefer": "return=minimal"})
            except Exception as e:  # noqa: BLE001
                print(f"  {pid}: database not updated ({e})")
    man_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n", encoding="utf-8")
    print(f"Card photos: {done} replaced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
