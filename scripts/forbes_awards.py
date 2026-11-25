#!/usr/bin/env python3
"""Forbes Travel Guide 2026 Star Awards (Five-Star and Four-Star hotels) from the official winners page.

Reads https://www.forbestravelguide.com/award-winners (one public page), keeps hotel entries only, and tags our hotels
when the name matches (same strict rule as everywhere else) and the destination matches the hotel's country or town.
Official awards are shown with their source link and are never turned into a score.
Writes official_awards rows; prints conflicts (e.g. we show Five-Star, Forbes now lists Four-Star) instead of changing them.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY.  --dry-run to only print.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import urllib.parse  # noqa: E402

from add_award_hotels import http_get, norm_words, now_iso, sb, sb_all, upsert  # noqa: E402
from strict_names import same_hotel  # noqa: E402

URL = "https://www.forbestravelguide.com/award-winners"
TOKEN = re.compile(
    r"<h3[^>]*>(?P<h3>.*?)</h3>|<h4[^>]*>(?P<h4>.*?)</h4>|"
    r"<a[^>]+href=\"(?P<href>(?:https://www\.forbestravelguide\.com)?/(?P<kind>hotels|restaurants|spas|cruises)/[^\"]+)\"[^>]*>(?P<name>.*?)</a>",
    re.S | re.I,
)
US = {"united states", "usa", "us", "united states of america"}


def text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse(page: str) -> list[dict[str, str]]:
    dest = rating = ""
    out = []
    for m in TOKEN.finditer(page):
        if m.group("h3") is not None:
            dest = text(m.group("h3"))
        elif m.group("h4") is not None:
            rating = text(m.group("h4"))
        elif m.group("kind").lower() == "hotels" and rating in ("Five-Star", "Four-Star"):
            href = m.group("href")
            out.append({"name": text(m.group("name")), "dest": dest, "rating": rating,
                        "url": href if href.startswith("http") else "https://www.forbestravelguide.com" + href})
    seen, uniq = set(), []
    for r in out:
        if r["url"] not in seen:
            seen.add(r["url"])
            uniq.append(r)
    return uniq


def place_ok(p: dict[str, Any], dest: str) -> bool:
    d = dest.lower()
    country = str(p.get("country") or "").lower()
    if country and country in d:
        return True
    return bool(set(norm_words(p.get("city") or "")) & set(norm_words(dest)))


def main(argv: list[str]) -> int:
    dry = "--dry-run" in argv
    code, page = http_get(URL, headers={"User-Agent": "StayOddsBot/1.0 (+https://stayodds.com; award listings with source links)"})
    if code != 200 or "Five-Star" not in page:
        print(f"Forbes: page not available (HTTP {code})")
        return 0
    entries = parse(page)
    print(f"Forbes: {sum(e['rating'] == 'Five-Star' for e in entries)} Five-Star and "
          f"{sum(e['rating'] == 'Four-Star' for e in entries)} Four-Star hotels on the official list")
    props = sb_all("properties", "id,name,city,country")
    by_id = {p["id"]: p for p in props}
    by_url = {e["url"]: e for e in entries}
    # repair: remove any Forbes tag whose Forbes page is a different hotel (an earlier, looser match)
    removed = 0
    for r in sb_all("official_awards", "property_id,award_body,label,source_url"):
        if r["award_body"] != "Forbes Travel Guide":
            continue
        e = by_url.get(r.get("source_url") or "")
        p = by_id.get(r["property_id"])
        if e and p and not same_hotel(p["name"], e["name"], p.get("city") or "", p.get("country") or ""):
            print(f"  REMOVE wrong tag {r['property_id']} ({p['name']}): Forbes page is {e['name']} - {r['label']}")
            removed += 1
            if not dry:
                sb("DELETE", f"/rest/v1/official_awards?property_id=eq.{urllib.parse.quote(r['property_id'])}"
                             f"&award_body=eq.{urllib.parse.quote('Forbes Travel Guide')}&label=eq.{urllib.parse.quote(r['label'])}",
                   None, {"Prefer": "return=minimal"})
    print(f"Forbes: removed {removed} tags that pointed at a different hotel")
    have: dict[str, set[str]] = {}
    for r in sb_all("official_awards", "property_id,award_body,label"):
        if r["award_body"] == "Forbes Travel Guide":
            have.setdefault(r["property_id"], set()).add(r["label"])
    rows, unmatched_five = [], []
    # a hotel matched by more than one Forbes entry (e.g. two wings of one resort) is ambiguous: skip it
    claims: dict[str, int] = {}
    for e in entries:
        for p in props:
            if same_hotel(p["name"], e["name"], p.get("city") or "", p.get("country") or "") and place_ok(p, e["dest"]):
                claims[p["id"]] = claims.get(p["id"], 0) + 1
    for e in entries:
        hits = [p for p in props if same_hotel(p["name"], e["name"], p.get("city") or "", p.get("country") or "") and place_ok(p, e["dest"])]
        if len(hits) != 1:
            if e["rating"] == "Five-Star" and not hits:
                unmatched_five.append(f"{e['name']} ({e['dest']})")
            if len(hits) > 1:
                print(f"  ambiguous, skipped: {e['name']} -> {[h['id'] for h in hits]}")
            continue
        p = hits[0]
        if claims.get(p["id"], 0) > 1:
            print(f"  ambiguous, skipped: {p['id']} matches {claims[p['id']]} Forbes entries")
            continue
        label = f"Forbes {e['rating']}"
        cur = have.get(p["id"], set())
        if cur and label not in cur:
            print(f"  CONFLICT {p['id']}: we show {sorted(cur)}, Forbes 2026 lists {label} - left for review")
            continue
        rows.append({"property_id": p["id"], "award_body": "Forbes Travel Guide", "label": label, "award_year": "2026",
                     "normalized_100": 95 if e["rating"] == "Five-Star" else 90,  # not used in any score (awards are excluded from the maths)
                     "source_url": e["url"], "verified_at": now_iso()})
        print(f"  {p['id']}: {label} ({e['name']}, {e['dest']})")
    print(f"Forbes: tagging {len(rows)} hotels; {len(unmatched_five)} Five-Star hotels on the list are not in StayOdds")
    seen_keys: set[tuple[str, str]] = set()
    rows = [r for r in rows if (r["property_id"], r["label"]) not in seen_keys and not seen_keys.add((r["property_id"], r["label"]))]
    if not dry and rows:
        upsert("official_awards", rows, "property_id,award_body,label")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
