#!/usr/bin/env python3
"""Save our own YouTube video thumbnails locally (assets/video-thumbs/<id>.jpg), once each.

Our videos, our thumbnails: used for the promo kit and so pages don't need to call YouTube for images.
"""
import json, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "video-thumbs"
OUT.mkdir(parents=True, exist_ok=True)
d = json.loads((ROOT / "data" / "videos.json").read_text(encoding="utf-8"))
n = 0
for v in d["videos"] + d["shorts"]:
    f = OUT / f"{v['id']}.jpg"
    if f.exists():
        continue
    for q in ("maxresdefault", "sddefault", "hqdefault"):
        try:
            with urllib.request.urlopen(f"https://i.ytimg.com/vi/{v['id']}/{q}.jpg", timeout=20) as r:
                data = r.read()
            if len(data) > 5000:
                f.write_bytes(data); n += 1; break
        except Exception:
            continue
print(f"Video thumbnails: {n} new saved")
