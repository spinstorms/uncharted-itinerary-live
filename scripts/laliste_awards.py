#!/usr/bin/env python3
"""LaListe Top 1000 Hotels 2026: tag our hotels with their published LaListe score (shown as an award with a link).

Reads the public list pages https://www.laliste.com/hotels/top-1000/<n>, matches names with the same strict rule as the
Forbes and MICHELIN tags (name words + town/country), skips ambiguous matches. Never turned into StayOdds points.
Env: SUPABASE_URL, SUPABASE_SECRET_KEY.  --dry-run to only print.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import http_get, now_iso, sb_all, upsert  # noqa: E402
from forbes_awards import place_ok  # noqa: E402
from strict_names import same_hotel  # noqa: E402

BASE = "https://www.laliste.com"
CARD = re.compile(r'<a[^>]+href="(?P<href>/places/hotel-[^"]+)"[^>]*>(?P<body>.*?)</a>', re.S)


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(page: str) -> list[dict]:
    out = []
    for m in CARD.finditer(page):
        body = m.group("body")
        sc = re.search(r"/>\s*(\d{2}(?:\.\d)?)\s*</span>", body)
        name = re.search(r'line-clamp-2[^"]*">(.*?)</span>', body, re.S)
        loc = re.search(r'truncate[^"]*">(.*?)</span>', body, re.S)
        if sc and name:
            out.append({"score": float(sc.group(1)), "name": text(name.group(1)), "dest": text(loc.group(1)) if loc else "",
                        "url": BASE + m.group("href")})
    return out


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    entries, seen = [], set()
    for n in range(1, 21):
        code, page = http_get(f"{BASE}/hotels/top-1000/{n}" if n > 1 else f"{BASE}/hotels/top-1000",
                              headers={"User-Agent": "StayOddsBot/1.0 (+https://stayodds.com; award listings with source links)"})
        got = [e for e in parse(page) if e["url"] not in seen] if code == 200 else []
        if not got:
            break
        for e in got:
            seen.add(e["url"])
        entries += got
    print(f"LaListe: {len(entries)} hotels on the published Top 1000 pages")
    if not entries:
        return 0
    props = sb_all("properties", "id,name,city,country")
    claims: dict[str, list] = {}
    for e in entries:
        hits = [p for p in props if same_hotel(p["name"], e["name"], p.get("city") or "", p.get("country") or "") and place_ok(p, e["dest"])]
        if len(hits) == 1:
            claims.setdefault(hits[0]["id"], []).append(e)
    rows = []
    for pid, es in claims.items():
        if len(es) != 1:
            print(f"  ambiguous, skipped: {pid} matches {len(es)} LaListe entries")
            continue
        e = es[0]
        rows.append({"property_id": pid, "award_body": "LaListe", "label": f"LaListe Top 1000 2026: {e['score']:g}/100",
                     "award_year": "2026", "normalized_100": round(e["score"]),  # shown as an award, not used in any score
                     "source_url": e["url"], "verified_at": now_iso()})
        print(f"  {pid}: {e['score']:g} ({e['name']}, {e['dest']})")
    print(f"LaListe: tagging {len(rows)} of our hotels")
    if not dry and rows:
        upsert("official_awards", rows, "property_id,award_body,label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
