#!/usr/bin/env python3
"""Read-only: candidate hotel photos from Wikimedia Commons (openly licensed), as review sheets.

Usage: commons_photos.py OUT_DIR id1 id2 ...
"""
from __future__ import annotations

import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; hotel photos with credit)"}


def api(**q) -> dict:
    q.update(format="json", formatversion="2")
    return json.loads(urllib.request.urlopen(urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=UA), timeout=30).read())


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    hs = {h["id"]: h for h in json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]}
    index, rows = {}, []
    for pid in sys.argv[2:]:
        h = hs.get(pid) or {}
        name = re.sub(r"\s*[-–(,].*$", "", h.get("name", pid)).strip()
        picks = []
        try:
            res = api(action="query", generator="search", gsrnamespace=6, gsrlimit=12, gsrsearch=f'"{name}" filetype:bitmap',
                      prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=500)
            for pg in sorted(res.get("query", {}).get("pages", []), key=lambda p: p.get("index", 99)):
                ii = (pg.get("imageinfo") or [{}])[0]
                if ii.get("width", 0) < 1000 or ii.get("width", 0) <= ii.get("height", 0):
                    continue
                meta = ii.get("extmetadata") or {}
                lic = re.sub("<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", ""))
                artist = re.sub("<[^>]+>", "", (meta.get("Artist") or {}).get("value", "")).strip()
                try:
                    im = Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(ii["thumburl"], headers=UA), timeout=30).read())).convert("RGB")
                except Exception:  # noqa: BLE001
                    continue
                picks.append({"title": pg["title"], "page": ii.get("descriptionurl"), "url": ii.get("url"), "licence": lic,
                              "artist": artist[:80], "im": im})
                if len(picks) >= 4:
                    break
        except Exception as e:  # noqa: BLE001
            print(pid, e)
        index[pid] = [{k: v for k, v in p.items() if k != "im"} for p in picks]
        rows.append((pid, picks))
        print(pid, name, len(picks))
    W, H, per = 300, 170, 12
    for s in range(0, len(rows), per):
        chunk = rows[s:s + per]
        sheet = Image.new("RGB", (260 + 4 * W, len(chunk) * (H + 6)), "white")
        dr = ImageDraw.Draw(sheet)
        for r, (pid, picks) in enumerate(chunk):
            y = r * (H + 6)
            dr.text((4, y + 60), f"{s + r} {pid[:34]}", fill="black")
            for k, p in enumerate(picks):
                im = p["im"].copy(); im.thumbnail((W - 6, H))
                sheet.paste(im, (260 + k * W, y))
                dr.text((262 + k * W, y + 2), str(k), fill="yellow")
        sheet.save(out / f"commons-{s // per:02d}.jpg", quality=70)
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
