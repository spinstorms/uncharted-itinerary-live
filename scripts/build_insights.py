"""StayOdds Insights page (/insights/) and the per-hotel guest rank line.

Everything is computed from the directory at build time:
  * guest_ranks(): each hotel's rank by guest score among StayOdds hotels in its city (10+ hotels) or else its
    country (10+ hotels). Only guest scores from 20 or more reviews take part.
  * write_insights(): award winners guests rank lowest, guest scores by brand, critics vs guests, awards vs guests.
"""
from __future__ import annotations

import json
import re
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "insights_template.html"
MIN_GROUP = 10
MIN_REVIEWS = 20

BRAND_NORMALISE = {
    "Leading Hotels": "Leading Hotels of the World", "Auberge Resorts": "Auberge Resorts Collection",
    "IHG / Six Senses": "Six Senses", "Accor / Raffles": "Raffles", "The Ritz-Carlton": "Ritz-Carlton",
    "Ritz-Carlton Reserve": "Ritz-Carlton",
}
NOT_A_BRAND = {"Independent", "Boutique", "Leading Hotels of the World", "Small Luxury Hotels", "Relais & Châteaux", ""}


def _guest(h: dict[str, Any]) -> tuple[int | None, int | None]:
    lic = (h.get("verifiedGuest") or {}).get("licensed") or {}
    n100, rc = lic.get("normalized100"), lic.get("reviewCount")
    if n100 is None or (rc or 0) < MIN_REVIEWS:
        return None, None
    return int(n100), int(rc)


def _city(h: dict[str, Any]) -> str:
    loc = str(h.get("location") or "").strip()
    return loc.split(",")[-1].strip() if loc else ""


def guest_ranks(hotels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{hotel_id: {"rank", "of", "group", "top", "topScore", "low"}} for hotels with a guest score."""
    scored = [(h, *_guest(h)) for h in hotels]
    scored = [(h, g, rc) for h, g, rc in scored if g is not None]
    by_city: dict[tuple[str, str], list] = defaultdict(list)
    by_country: dict[str, list] = defaultdict(list)
    for row in scored:
        h = row[0]
        if _city(h):
            by_city[(h.get("country") or "", _city(h))].append(row)
        by_country[h.get("country") or ""].append(row)
    out: dict[str, dict[str, Any]] = {}
    for groups, label_of in ((by_country, lambda k: k), (by_city, lambda k: k[1])):
        for key, rows in groups.items():
            if len(rows) < MIN_GROUP or not key:
                continue
            ordered = sorted(rows, key=lambda r: (-r[1], -r[2], r[0]["name"]))
            for i, (h, g, rc) in enumerate(ordered, 1):
                # city groups are written second, so they replace the country rank where both exist
                out[h["id"]] = {
                    "rank": i, "of": len(ordered), "group": label_of(key),
                    "top": ordered[0][0]["name"], "topScore": ordered[0][1], "low": ordered[-1][1],
                }
    return out


def _awards(h: dict[str, Any]) -> list[str]:
    return [str(a.get("label") or "") for a in h.get("officialAwards") or []]


def _data(hotels: list[dict[str, Any]], compute) -> dict[str, Any]:
    rows = []
    for h in hotels:
        g, rc = _guest(h)
        o = compute(h)
        rows.append({"h": h, "g": g, "rc": rc, "c": o.get("critic100"), "awards": _awards(h),
                     "brand": BRAND_NORMALISE.get(h.get("brand") or "", h.get("brand") or "")})
    guests = [r for r in rows if r["g"] is not None]

    # award winners guests rank lowest in their country (10+ hotels)
    by_country: dict[str, list] = defaultdict(list)
    for r in guests:
        by_country[r["h"].get("country") or ""].append(r)
    low = []
    for country, rs in by_country.items():
        if len(rs) < MIN_GROUP:
            continue
        ordered = sorted(rs, key=lambda r: (-r["g"], -r["rc"]))
        for i, r in enumerate(ordered, 1):
            big = [a for a in r["awards"] if re.search(r"in the World|3 MICHELIN Keys|Forbes Five-Star", a)]
            if any(re.search(r"in the World|3 MICHELIN Keys", a) for a in big):
                low.append({"name": r["h"]["name"], "guest": r["g"], "reviews": r["rc"], "rank": i, "of": len(ordered),
                            "group": country, "awards": big[:2], "pct": i / len(ordered)})
    low.sort(key=lambda x: (-x["pct"], x["guest"]))
    for x in low:
        x.pop("pct")

    # brands with 8+ rated hotels
    by_brand: dict[str, list] = defaultdict(list)
    for r in guests:
        if r["brand"] not in NOT_A_BRAND:
            by_brand[r["brand"]].append(r)
    brands = []
    for b, rs in by_brand.items():
        if len(rs) < 8:
            continue
        gs = sorted(r["g"] for r in rs)
        q = st.quantiles(gs, n=4)
        best = max(rs, key=lambda r: (r["g"], r["rc"]))
        worst = min(rs, key=lambda r: (r["g"], -r["rc"]))
        brands.append({"brand": b, "n": len(rs), "median": st.median(gs), "q1": round(q[0], 1), "q3": round(q[2], 1),
                       "min": gs[0], "max": gs[-1], "best": best["h"]["name"], "worst": worst["h"]["name"]})
    brands.sort(key=lambda x: (-x["median"], -x["n"]))

    # award tiers
    tiers: dict[str, list] = defaultdict(list)
    for r in guests:
        a = r["awards"]
        if any(re.search(r"in the World", x) for x in a):
            tiers["World's 50 Best Top 100"].append(r["g"])
        for k in ("3 MICHELIN Keys", "2 MICHELIN Keys", "1 MICHELIN Key", "Forbes Five-Star"):
            if k in a:
                tiers[k].append(r["g"])
        if not a:
            tiers["No major award"].append(r["g"])
    tier_stats = {k: {"n": len(v), "median": st.median(v), "q1": st.quantiles(v, n=4)[0], "q3": st.quantiles(v, n=4)[2]}
                  for k, v in tiers.items() if len(v) >= 8}

    scatter = [{"n": r["h"]["name"], "c": r["c"], "g": r["g"]} for r in guests if r["c"] is not None]
    return {"disappoint": low[:6], "brands": brands, "tiers": tier_stats, "scatter": scatter, "n": len(guests)}


def write_insights(dist: Path, hotels: list[dict[str, Any]], template: str, compute) -> list[str]:
    from build_award_lists import _shell  # same header and footer as the award list pages

    head, foot = _shell(template)
    d = _data(hotels, compute)
    page = TEMPLATE.read_text(encoding="utf-8")
    b = d["brands"]
    if b:
        steady = min(b, key=lambda x: (x["max"] - x["min"], -x["n"]))
        wide = max(b, key=lambda x: (x["max"] - x["min"], x["n"]))
        brand_note = (f"Most consistent: {steady['brand']}, where every rated hotel scores between {steady['min']} and "
                      f"{steady['max']}. Widest spread: {wide['brand']}, from {wide['min']} to {wide['max']}.")
    else:
        brand_note = ""
    t = d["tiers"]
    award_meds = [v["median"] for k, v in t.items() if k != "No major award"]
    tier_note = ""
    if award_meds and "No major award" in t:
        tier_note = (f"Award-winning hotels have a typical guest score of {min(award_meds):g} to {max(award_meds):g}, "
                     f"against {t['No major award']['median']:g} for hotels with no major award. Awards point to good "
                     "hotels, but guests separate them far less than the lists do.")
    data = {k: d[k] for k in ("disappoint", "brands", "tiers", "scatter")}
    page = (page.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
            .replace("__DATE__", datetime.now(timezone.utc).strftime("%-d %B %Y"))
            .replace("__NHOTELS__", f"{d['n']:,}")
            .replace("__NSCATTER__", f"{len(d['scatter']):,}")
            .replace("__BRAND_NOTE__", brand_note)
            .replace("__TIER_NOTE__", tier_note))
    site = "https://stayodds.com"
    h2 = re.sub(r"<title>.*?</title>", "<title>Guest Insights | StayOdds</title>", head, flags=re.S)
    h2 = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + f"{site}/insights/" + m.group(2), h2)
    h2 = re.sub(r'(<meta name="description" content=")[^"]*(")',
                lambda m: m.group(1) + "How guests rate award-winning luxury hotels: rankings, brands, critics versus guests." + m.group(2), h2)
    out = dist / "insights"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(
        h2 + '<main><div style="max-width:960px;margin:0 auto;padding:28px 16px 56px">' + page + "</div></main>" + foot + "</body>\n</html>\n",
        encoding="utf-8",
    )
    return ["/insights/"]
