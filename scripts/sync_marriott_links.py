#!/usr/bin/env python3
"""Put the Partnerize Marriott.com link first for every Marriott-family hotel in the app's database.

Does nothing until data/partnerize-campaigns.json holds an approved Marriott campaign (camref).
Live pricing is untouched (the LiteAPI id stays). Env: SUPABASE_URL, SUPABASE_SECRET_KEY.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import sb  # noqa: E402
from build_stayodds_site import MARRIOTT_CAMREF, marriott_affiliate_link  # noqa: E402
from add_award_hotels import sb_all  # noqa: E402


def main() -> int:
    if not MARRIOTT_CAMREF:
        print("Marriott: no approved Partnerize campaign yet, nothing changed")
        return 0
    rows = []
    for p in sb_all("properties", "id,name,city,brand"):
        url = marriott_affiliate_link(p["id"], p.get("name") or "", p.get("city") or "", p.get("brand") or "")
        if url:
            rows.append({"property_id": p["id"], "channel_type": "direct_brand", "partner_name": "Marriott.com",
                         "url": url, "mobile_allowed": True, "priority": 0,
                         "perks_summary": "Book direct: Marriott Bonvoy points and member rates"})
    for i in range(0, len(rows), 200):
        sb("POST", "/rest/v1/booking_links?on_conflict=property_id,channel_type,partner_name", rows[i:i + 200],
           {"Prefer": "resolution=merge-duplicates,return=minimal"})
    print(f"Marriott: {len(rows)} hotels now book through Marriott.com (Partnerize)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
