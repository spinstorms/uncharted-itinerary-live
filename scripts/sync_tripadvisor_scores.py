#!/usr/bin/env python3
"""Copy the saved Tripadvisor ratings (data/tripadvisor.json, 20+ reviews) into Supabase licensed_guest_scores
(partner_source 'tripadvisor') so the app can combine them with the booking-guest score, exactly like the website.
Removes Tripadvisor rows that are no longer in the file, or all of them when Tripadvisor is switched off.

Env: SUPABASE_URL, SUPABASE_SECRET_KEY
"""
import json
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from add_award_hotels import now_iso, sb, sb_all, upsert  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    on = json.loads((ROOT / "data" / "tripadvisor-settings.json").read_text()).get("enabled", True)
    data = json.loads((ROOT / "data" / "tripadvisor.json").read_text(encoding="utf-8")).get("hotels", {}) if on else {}
    props = {p["id"] for p in sb_all("properties", "id")}
    rows = [{
        "property_id": pid, "partner_source": "tripadvisor", "rating": float(t["rating"]), "scale": 5.0,
        "normalized_100": int(round(float(t["rating"]) * 20)), "review_count": int(t["reviewCount"]),
        "attribution": "Tripadvisor", "verified_at": (t.get("fetched") or now_iso()[:10]) + "T00:00:00+00:00",
    } for pid, t in data.items() if pid in props and t.get("rating") is not None and (t.get("reviewCount") or 0) >= 20]
    if rows:
        upsert("licensed_guest_scores", rows, "property_id,partner_source")
    keep = {r["property_id"] for r in rows}
    stale = [r["property_id"] for r in sb_all("licensed_guest_scores", "property_id,partner_source")
             if r.get("partner_source") == "tripadvisor" and r["property_id"] not in keep]
    for pid in stale:
        sb("DELETE", f"/rest/v1/licensed_guest_scores?property_id=eq.{urllib.parse.quote(pid)}&partner_source=eq.tripadvisor",
           None, {"Prefer": "return=minimal"})
    print(f"Tripadvisor -> Supabase: {len(rows)} ratings saved, {len(stale)} removed")
    # Google Maps ratings, saved the same way for the app
    gdata = json.loads((ROOT / "data" / "google-ratings.json").read_text(encoding="utf-8")).get("hotels", {}) \
        if (ROOT / "data" / "google-ratings.json").exists() else {}
    grows = [{
        "property_id": pid, "partner_source": "google", "rating": float(t["rating"]), "scale": 5.0,
        "normalized_100": int(round(float(t["rating"]) * 20)), "review_count": int(t["reviewCount"]),
        "attribution": "Google", "verified_at": t["fetched"] + "T00:00:00+00:00",
    } for pid, t in gdata.items() if pid in props and (t.get("reviewCount") or 0) >= 20]
    if grows:
        upsert("licensed_guest_scores", grows, "property_id,partner_source")
    keep = {r["property_id"] for r in grows}
    gstale = [r["property_id"] for r in sb_all("licensed_guest_scores", "property_id,partner_source")
              if r["partner_source"] == "google" and r["property_id"] not in keep]
    for pid in gstale:  # e.g. a hotel whose Google listing turned out to be a different place
        sb("DELETE", f"/rest/v1/licensed_guest_scores?property_id=eq.{urllib.parse.quote(pid)}&partner_source=eq.google",
           None, {"Prefer": "return=minimal"})
    print(f"Google -> Supabase: {len(grows)} ratings saved, {len(gstale)} removed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
