#!/usr/bin/env python3
"""
StayOdds — Repeatable Brand & Loyalty Affiliation Audit & Cleanup Script.

Enforces strict zero-fake-data integrity on brand, parent group, and loyalty tags:
- Flags/blocks legacy placeholder brands ("Luxury Collection & Boutique") that
  previously caused independent hotels (e.g., The Library Koh Samui) to inherit
  Marriott Bonvoy / Marriott STARS tags.
- Checks for known regex false positives (Virgin Limited Edition -> EDITION,
  Peninsula Papagayo -> The Peninsula, Lago di Como -> COMO Hotels,
  Capella Lodge -> Capella Hotels, Bulgari -> Marriott Bonvoy points,
  blanket Small Luxury Hotels -> Hilton Honors).
- Can run in `--check` mode (used by build_stayodds_site.py before every deploy)
  or `--fix-supabase` mode to clean Supabase `properties.brand` rows directly.
"""
import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Explicit, verified brand corrections for Supabase `properties.brand`
# Strictly derived from official hotel names / verified brand memberships — zero guesses.
VERIFIED_BRAND_CORRECTIONS = {
    # 40 legacy 'Luxury Collection & Boutique' rows:
    "the-library-samui": "Independent",
    "garrya-tongsai-bay-samui": "Independent",
    "the-sanchaya": "Independent",
    "napasai-samui-residence": "Independent",
    "lalya-ninh-van-bay": "Independent",
    "mia-resort-nha-trang": "Independent",
    "sala-samui-chaweng-beach-resort": "Independent",
    "alvear-icon-hotel": "Independent",
    "hotel-proverbs-taipei": "Independent",
    "hotel-unique": "Independent",
    "sala-phuket-mai-khao-beach-resort": "Independent",
    "the-ruma-hotel-and-residences": "Independent",
    "amiana-resort-nha-trang": "Independent",
    "mango-bay-resort": "Independent",
    "saii-koh-samui-villas-adult-only": "Independent",
    "almanac-barcelona": "Independent",
    "cordis-auckland": "Independent",
    "ana-mandara-cam-ranh": "Independent",
    "arlo-midtown-building-skydb": "Independent",
    "citizenm-tower-of-london": "Independent",
    "twa-hotel": "Independent",
    "an-lam-retreats-ninh-van-bay": "Independent",
    "gorgeous-george-hotel": "Independent",
    "grand-fiesta-americana-coral-beach-cancun": "Independent",
    "heritage-le-telfair-golf-and-wellness": "Independent",
    "lux-grand-gaube": "Independent",
    "lux-marijani-zanzibar": "Independent",
    "maia-resort-quy-nhon": "Independent",
    "majestic-hotel-and-spa-barcelona": "Independent",
    "shinta-mani-angkor-and-bensley-collection": "Independent",
    "sunscape-cancun-resort-and-spa": "Independent",
    "the-slate-phuket": "Independent",
    # Verified brand names right in official property titles:
    "sindhorn-kempinski-hotel-bangkok": "Kempinski",
    "fiji-marriott-resort-momi-bay": "Marriott",
    "the-westin-langkawi-resort-and-spa": "Westin",
    "the-bernic-hotel-new-york-city": "Tapestry Collection by Hilton",
    "canopy-by-hilton-paris-eiffel-tower": "Canopy by Hilton",
    "emiliano-rio-an-slh-hotel": "Small Luxury Hotels",
    "rambagh-palace-jaipur": "Taj Hotels",
    "umaid-bhawan-palace-jodhpur": "Taj Hotels",
    # Non-Bonvoy / over-broad / ambiguous raw brand cleanup:
    "bulgari-resort-bali": "Bulgari Hotels",
    "bulgari-resort-dubai": "Bulgari Hotels",
    "bulgari-hotel-roma": "Bulgari Hotels",
    "bulgari-hotel-tokyo": "Bulgari Hotels",
    "andaz-peninsula-papagayo": "Andaz",
    "alila-villas-uluwatu": "Alila",
    "waldorf-astoria-maldives": "Waldorf Astoria",
    "conrad-bora-bora-nui": "Conrad",
    "element-by-westin-ubud": "Element by Westin",
    "domes-noruz-chania-autograph-collection": "Autograph Collection",
    "canaves-oia-epitome": "Small Luxury Hotels",
    "grand-hotel-tremezzo-como": "Preferred Hotels",
}


def load_env():
    env_path = ROOT / ".env.local"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def audit_hotels(hotels):
    """Returns (errors, warnings) lists."""
    errors = []
    warnings = []
    for h in hotels:
        hid = h.get("id", "")
        name = (h.get("name") or "").strip()
        brand = (h.get("brand") or "").strip()
        bl = brand.lower()
        nl = name.lower()

        # 1. Block forbidden legacy placeholder strings
        if bl == "luxury collection & boutique":
            errors.append(f"{hid}: forbidden legacy brand placeholder 'Luxury Collection & Boutique'")

        # 2. Block Bulgari tagged with Marriott in raw brand
        if ("bulgari" in bl or "bvlgari" in bl) and "marriott" in bl:
            errors.append(f"{hid}: Bulgari Hotels does not participate in Marriott Bonvoy (raw={brand!r})")

        # 3. Block SLH explicitly tagged with Hilton in raw brand unless separately verified
        if ("slh" in bl or "small luxury" in bl) and "hilton" in bl:
            warnings.append(f"{hid}: SLH property has Hilton in raw brand ({brand!r}) — verify individual participation")

        # 4. Catch Virgin Limited Edition accidentally carrying EDITION
        if "virgin" in nl and bl == "edition":
            errors.append(f"{hid}: Virgin Limited Edition misclassified as Marriott EDITION")

        # 5. Catch generic parent brand when explicit sub-brand is in name
        if bl in ("hilton honors", "world of hyatt", "hyatt") and any(
            sub in nl for sub in ("waldorf", "conrad", "andaz", "alila", "park hyatt")
        ):
            warnings.append(f"{hid}: generic parent brand {brand!r} used despite specific sub-brand in {name!r}")

        # 6. Catch Element by Westin tagged simply as Westin (would mis-trigger Luminous)
        if "element by westin" in nl and bl == "westin":
            errors.append(f"{hid}: Element by Westin tagged as 'Westin' (would falsely trigger Marriott Luminous)")

        # 7. Catch Design Hotels (note: Cap Karoso IS verified Bonvoy, warn on any new Design Hotels)
        if "design hotels" in bl and hid != "cap-karoso-sumba":
            warnings.append(f"{hid}: Design Hotels member ({brand!r}) — manually verify Marriott Bonvoy participation")

        # 8. Catch accidental Peninsula Papagayo -> The Peninsula or Capella Lodge -> Capella Hotels in raw brand
        if "papagayo" in nl and bl == "the peninsula":
            errors.append(f"{hid}: Andaz Peninsula Papagayo misclassified as 'The Peninsula'")
        if "capella lodge" in nl and bl in ("capella", "capella hotels"):
            errors.append(f"{hid}: Capella Lodge (Lord Howe Island) misclassified as Capella Hotels")

    return errors, warnings


def summarize_brand_hygiene(hotels):
    """Build a transparent, read-only hygiene report without stripping any legitimate properties."""
    indep_all = []
    indep_with_facts = []
    slh_ids = []
    bulgari_ids = []
    design_bonvoy_ids = []
    banyan_ids = []
    regional_brands = {}

    REGIONAL_OR_BOUTIQUE = {
        "Aman", "Soneva", "Singita", "Hoshinoya", "Capella", "Capella Hotels",
        "Taj Hotels", "Oberoi", "COMO Hotels", "Virgin Limited Edition",
        "Auberge Resorts", "One&Only", "Six Senses", "Belmond", "Rosewood",
    }

    for h in hotels:
        hid = h.get("id", "")
        brand = (h.get("brand") or "").strip()
        bl = brand.lower()
        has_verified_facts = bool(
            (h.get("verifiedGuest") or {}).get("licensed")
            or h.get("officialAwards")
            or h.get("editorialRatings")
            or h.get("visitedByUs")
            or h.get("standout")
            or any((h.get("keyFacts") or {}).values())
        )
        if not brand or bl in ("independent", "independent & boutique"):
            indep_all.append(hid)
            if has_verified_facts:
                indep_with_facts.append(hid)
        if "small luxury" in bl or bl == "slh":
            slh_ids.append(hid)
        if "bulgari" in bl or "bvlgari" in bl:
            bulgari_ids.append(hid)
        if "design hotels" in bl:
            design_bonvoy_ids.append(hid)
        if "banyan tree" in bl:
            banyan_ids.append(hid)
        if brand in REGIONAL_OR_BOUTIQUE:
            regional_brands[brand] = regional_brands.get(brand, 0) + 1

    return {
        "totalProperties": len(hotels),
        "independentCount": len(indep_all),
        "independentWithVerifiedFacts": len(indep_with_facts),
        "regionalBoutiqueLuxuryCount": sum(regional_brands.values()),
        "slhNoBlanketHilton": sorted(slh_ids),
        "bulgariNoBonvoyPoints": sorted(bulgari_ids),
        "designHotelsVerifiedBonvoy": sorted(design_bonvoy_ids),
        "banyanTreeAccorReview": sorted(banyan_ids),
    }


def format_audit_summary(hotels, errors, warnings, verbose=False):
    rep = summarize_brand_hygiene(hotels)
    lines = [
        f"Brand & Loyalty Audit ({rep['totalProperties']} properties): {len(errors)} errors, {len(warnings)} warnings",
        f"  Preserved: {rep['independentCount']} Independent ({rep['independentWithVerifiedFacts']} with verified facts/scores) • {rep['regionalBoutiqueLuxuryCount']} boutique/regional luxury properties",
        f"  Loyalty Hygiene: {len(rep['slhNoBlanketHilton'])} SLH (SLH Invited only, no blanket Hilton) • {len(rep['bulgariNoBonvoyPoints'])} Bulgari (STARS only, no Bonvoy pts) • {len(rep['designHotelsVerifiedBonvoy'])} verified Bonvoy Design Hotel • {len(rep['banyanTreeAccorReview'])} Banyan Tree (Accor ALL/STEP)",
    ]
    if verbose:
        lines.append(f"  [INFO] SLH properties (verify Hilton per property): {', '.join(rep['slhNoBlanketHilton'])}")
        lines.append(f"  [INFO] Bulgari (non-Bonvoy points): {', '.join(rep['bulgariNoBonvoyPoints'])}")
        lines.append(f"  [INFO] Banyan Tree (Accor partnership): {', '.join(rep['banyanTreeAccorReview'])}")
    for w in warnings:
        lines.append(f"  [WARN] {w}")
    for e in errors:
        lines.append(f"  [ERROR] {e}")
    return "\n".join(lines)


def apply_supabase_fixes():
    load_env()
    sb_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    sb_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not sb_url or not sb_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_SECRET_KEY in .env.local")

    # Group property IDs by target brand for fast batched PATCH calls
    by_brand = {}
    for pid, new_brand in VERIFIED_BRAND_CORRECTIONS.items():
        by_brand.setdefault(new_brand, []).append(pid)

    updated_total = 0
    for new_brand, ids in by_brand.items():
        for i in range(0, len(ids), 40):
            chunk = ids[i : i + 40]
            in_filter = "(" + ",".join(chunk) + ")"
            url = f"{sb_url}/rest/v1/properties?id=in.{urllib.parse.quote(in_filter, safe='(),')}"
            body = json.dumps({"brand": new_brand}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method="PATCH",
                headers={
                    "apikey": sb_key,
                    "Authorization": f"Bearer {sb_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                rows = json.loads(resp.read().decode("utf-8"))
                updated_total += len(rows)
                print(f"  PATCH brand={new_brand!r:30s} -> updated {len(rows)} row(s)")
    print(f"Total Supabase rows updated: {updated_total}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix-supabase", action="store_true", help="Apply verified brand corrections to Supabase")
    ap.add_argument("--check", action="store_true", help="Audit data/stayodds-directory.json and fail on errors")
    ap.add_argument("--report", action="store_true", help="Print verbose brand & loyalty hygiene report")
    args = ap.parse_args()

    if args.fix_supabase:
        apply_supabase_fixes()
        return

    dir_path = ROOT / "data" / "stayodds-directory.json"
    if not dir_path.exists():
        print("data/stayodds-directory.json not found", file=sys.stderr)
        sys.exit(1)
    hotels = json.loads(dir_path.read_text(encoding="utf-8")).get("hotels", [])
    errors, warnings = audit_hotels(hotels)
    print(format_audit_summary(hotels, errors, warnings, verbose=args.report))
    if args.check and errors:
        sys.exit(1)


if __name__ == "__main__":
    main()

