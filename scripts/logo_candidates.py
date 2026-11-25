#!/usr/bin/env python3
"""Read-only: find candidate brand logo files on Wikimedia Commons and save small PNG previews for review.

Usage: logo_candidates.py OUT_DIR "Brand one" "Brand two" ...
Writes OUT_DIR/<n>-<k>.png and OUT_DIR/index.json with each file's Commons title, page URL and licence.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "StayOddsBot/1.0 (https://stayodds.com; brand logo lookup)"}


def api(**q) -> dict:
    q.update(format="json", formatversion="2")
    with urllib.request.urlopen(urllib.request.Request(API + "?" + urllib.parse.urlencode(q), headers=UA), timeout=30) as r:
        return json.loads(r.read())


def main() -> int:
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    index = {}
    for n, brand in enumerate(sys.argv[2:]):
        res = api(action="query", list="search", srnamespace=6, srlimit=6, srsearch=f'intitle:logo "{brand}"')
        titles = [s["title"] for s in res.get("query", {}).get("search", [])]
        if not titles:
            res = api(action="query", list="search", srnamespace=6, srlimit=6, srsearch=f"{brand} logo")
            titles = [s["title"] for s in res.get("query", {}).get("search", [])]
        items = []
        if titles:
            info = api(action="query", titles="|".join(titles), prop="imageinfo", iiprop="url|extmetadata|mime", iiurlwidth=360)
            for k, pg in enumerate(info.get("query", {}).get("pages", [])):
                ii = (pg.get("imageinfo") or [{}])[0]
                meta = ii.get("extmetadata") or {}
                lic = re.sub("<[^>]+>", "", (meta.get("LicenseShortName") or {}).get("value", ""))
                item = {"title": pg["title"], "page": ii.get("descriptionurl"), "url": ii.get("url"), "thumb": ii.get("thumburl"),
                        "mime": ii.get("mime"), "licence": lic}
                try:
                    raw = urllib.request.urlopen(urllib.request.Request(item["thumb"], headers=UA), timeout=30).read()
                    f = f"{n:02d}-{k}.png"
                    (out / f).write_bytes(raw)
                    item["file"] = f
                except Exception as e:  # noqa: BLE001
                    item["error"] = str(e)
                items.append(item)
        index[brand] = items
        print(brand, len(items))
    (out / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
