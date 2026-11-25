#!/usr/bin/env python3
"""Add hand-checked links (forum threads, blog reviews) to data/community-mentions.json.

Usage: add_mentions.py <hotel_id> "<site>|<title>|<url>" ...   (existing URLs are not duplicated)
"""
import json
import sys
from pathlib import Path

P = Path(__file__).resolve().parent.parent / "data" / "community-mentions.json"
d = json.loads(P.read_text(encoding="utf-8")) if P.exists() else {"note": "Links found by search and checked by hand: forum threads and independent reviews. Titles as published.", "hotels": {}}
pid = sys.argv[1]
cur = d["hotels"].setdefault(pid, [])
have = {m["url"] for m in cur}
for arg in sys.argv[2:]:
    site, title, url = arg.split("|", 2)
    if url not in have:
        cur.append({"site": site, "title": title, "url": url})
        have.add(url)
d["hotels"] = dict(sorted(d["hotels"].items()))
P.write_text(json.dumps(d, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(pid, len(cur))
