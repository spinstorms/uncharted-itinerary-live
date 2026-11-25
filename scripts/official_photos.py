#!/usr/bin/env python3
"""Read-only: candidate photos from each hotel's own official website, saved as review sheets.

For each id: the official site (directory officialSite, else the website on the hotel's Google listing), then the
page's share image (og:image / twitter:image) and its first large images. Up to 4 candidates per hotel.
Usage: official_photos.py OUT_DIR id1 id2 ...   Env: GOOGLE_PLACES_API_KEY
"""
from __future__ import annotations

import html
import io
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
      "Accept-Language": "en-GB,en;q=0.9", "Accept": "text/html,application/xhtml+xml,image/avif,image/webp,*/*;q=0.8"}


def get(url: str, headers: dict | None = None, timeout: int = 25) -> tuple[bytes, str]:
    r = urllib.request.urlopen(urllib.request.Request(url, headers=headers or UA), timeout=timeout)
    return r.read(), r.geturl()


def website(h: dict, key: str) -> str:
    if h.get("officialSite"):
        return h["officialSite"]
    if not (h.get("googlePlaceId") and key):
        return ""
    raw, _ = get(f"https://places.googleapis.com/v1/places/{urllib.parse.quote(h['googlePlaceId'])}",
                 {"X-Goog-Api-Key": key, "X-Goog-FieldMask": "websiteUri"})
    return json.loads(raw).get("websiteUri") or ""


def candidates(page: str, base: str) -> list[str]:
    out = []
    for pat in (r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image)["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']'):
        out += re.findall(pat, page, re.I)
    for m in re.finditer(r'<img[^>]+(?:data-src|src)=["\']([^"\']+\.(?:jpe?g|webp|png)(?:\?[^"\']*)?)["\']', page, re.I):
        out.append(m.group(1))
    seen, res = set(), []
    for u in out:
        u = urllib.parse.urljoin(base, html.unescape(u.strip()))
        if u.startswith("http") and u not in seen and not re.search(r"logo|icon|sprite|favicon|badge|award", u, re.I):
            seen.add(u)
            res.append(u)
    return res[:12]


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    ids, forced = [], {}
    for a in sys.argv[2:]:
        if "=" in a:
            k, u = a.split("=", 1)
            forced[k] = u
            ids.append(k)
        else:
            ids.append(a)
    key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    hs = {h["id"]: h for h in json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]}
    index, rows = {}, []
    for pid in ids:
        h = hs.get(pid) or {}
        site, picks = "", []
        try:
            site = forced.get(pid) or website(h, key)
            if site:
                raw, final = get(site)
                for u in candidates(raw.decode("utf-8", "ignore"), final):
                    if len(picks) >= 4:
                        break
                    try:
                        b, _ = get(u, {**UA, "Referer": final})
                        im = Image.open(io.BytesIO(b)).convert("RGB")
                        if im.width >= 800 and im.width > im.height:
                            picks.append({"url": u, "w": im.width, "im": im})
                    except Exception:  # noqa: BLE001
                        continue
        except Exception as e:  # noqa: BLE001
            print(pid, "error", e)
        index[pid] = {"site": site, "photos": [{k: v for k, v in p.items() if k != "im"} for p in picks]}
        rows.append((pid, picks))
        print(pid, site, len(picks))
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
        sheet.save(out / f"official-{s // per:02d}.jpg", quality=70)
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
