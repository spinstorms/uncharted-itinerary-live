#!/usr/bin/env python3
"""Point every hotel's photo in the database at the copy saved on our own site (assets/card-photos or assets/thumbs),
so the app and site load one cached file from us instead of hotlinking hotel or booking-site servers.
Env: SUPABASE_URL, SUPABASE_SECRET_KEY
"""
from __future__ import annotations

import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb, sb_all  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    n = 0
    for p in sb_all("properties", "id,hero_image_url,visited_by_founder"):
        hero = (p.get("hero_image_url") or "").strip()
        if not hero:
            continue  # no genuine photo: keep the placeholder
        pid = p["id"]
        want = ""
        if (ROOT / "assets" / "card-photos" / f"{pid}.webp").exists():
            want = f"assets/card-photos/{pid}.webp"
        elif (ROOT / "assets" / "thumbs" / f"{pid}.webp").exists() and hero.startswith("http"):
            want = f"assets/thumbs/{pid}.webp"
        if want and want != hero:
            sb("PATCH", f"/rest/v1/properties?id=eq.{urllib.parse.quote(pid)}", {"hero_image_url": want}, {"Prefer": "return=minimal"})
            n += 1
    print(f"Photos: {n} hotels now use the copy saved on our site")
    return 0


if __name__ == "__main__":
    sys.exit(main())
