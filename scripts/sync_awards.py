#!/usr/bin/env python3
"""Upsert all verified official awards (strict HTTP source_url) for existing Supabase properties."""

import json
import os
import urllib.request
from datetime import datetime, timezone
from catalog_250 import VERIFIED_AWARDS_BY_SLUG
from sync_250_hotels import load_env_local, supabase_upsert

load_env_local()
sb_url = os.environ["SUPABASE_URL"].rstrip("/")
sb_secret = os.environ["SUPABASE_SECRET_KEY"]
now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

req = urllib.request.Request(
    f"{sb_url}/rest/v1/properties?select=id&limit=1000",
    headers={"apikey": sb_secret, "Authorization": f"Bearer {sb_secret}"},
)
valid_ids = {r["id"] for r in json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))}

rows = []
for pid, items in VERIFIED_AWARDS_BY_SLUG.items():
    if pid not in valid_ids:
        continue
    for body, label, year, norm100, src_url in items:
        rows.append(
            {
                "property_id": pid,
                "award_body": body,
                "label": label,
                "award_year": year,
                "normalized_100": norm100,
                "source_url": src_url,
                "verified_at": now_iso,
            }
        )

supabase_upsert(sb_url, sb_secret, "official_awards", rows, "property_id,award_body,label")
print(f"Upserted {len(rows)} verified official awards across {len(valid_ids)} Supabase properties!")
