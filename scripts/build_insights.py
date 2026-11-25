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
MIN_GROUP = 10  # for the insights charts
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


COUNTRY_ALIAS = {"UAE": "United Arab Emirates", "USA": "United States", "Virgin Islands (US)": "US Virgin Islands"}


def _country(h: dict[str, Any]) -> str:
    c = str(h.get("country") or "").strip()
    return COUNTRY_ALIAS.get(c, c)


def _city(h: dict[str, Any]) -> str:
    loc = str(h.get("location") or "").strip()
    c = loc.split(",")[-1].strip() if loc else ""
    return CITY_ALIAS.get(c, c)


CITY_ALIAS = {"New York City": "New York", "NYC": "New York", "Manhattan": "New York"}
AREA_MIN = 6  # smallest group worth ranking in


PRICE_BANDS = ((0, 300, "under £300"), (300, 600, "£300–£600"), (600, 1000, "£600–£1,000"), (1000, 10**9, "£1,000+"))


def _price_band(h: dict[str, Any]) -> str | None:
    gbp = (h.get("priceSnapshot") or {}).get("nightlyGbp")
    if not gbp:
        return None
    for lo, hi, label in PRICE_BANDS:
        if lo <= gbp < hi:
            return label
    return None


def _rank_rows(rows: list, label: str) -> dict[str, dict[str, Any]]:
    ordered = sorted(rows, key=lambda r: (-r[1], -r[2], r[0]["name"]))
    return {h["id"]: {"rank": i, "of": len(ordered), "group": label, "top": ordered[0][0]["name"],
                      "topScore": ordered[0][1], "low": ordered[-1][1]}
            for i, (h, g, rc) in enumerate(ordered, 1)}


def guest_ranks(hotels: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """{hotel_id: {"area": rank, "price": rank or absent}} for every hotel with a guest score (20+ reviews).

    area: the smallest of town/island, country, wider region that has AREA_MIN+ rated hotels.
    price: rank among rated hotels in the same price band (from the latest indicative nightly price check)."""
    scored = [(h, *_guest(h)) for h in hotels]
    scored = [(h, g, rc) for h, g, rc in scored if g is not None]
    groups: dict[tuple, list] = defaultdict(list)
    for row in scored:
        h = row[0]
        if _city(h):
            groups[("city", _country(h), _city(h))].append(row)
        if _country(h):
            groups[("country", _country(h))].append(row)
        if h.get("region"):
            groups[("region", h["region"])].append(row)
        band = _price_band(h)
        if band:
            groups[("price", band)].append(row)
    ranked = {k: _rank_rows(v, k[-1]) for k, v in groups.items() if len(v) >= AREA_MIN or k[0] == "region"}
    out: dict[str, dict[str, Any]] = {}
    for h, g, rc in scored:
        hid = h["id"]
        for key in (("city", _country(h), _city(h)), ("country", _country(h)), ("region", h.get("region") or "")):
            if key in ranked and hid in ranked[key] and key[-1]:
                out[hid] = {"area": ranked[key][hid]}
                break
        band = _price_band(h)
        if band and ("price", band) in ranked and hid in out:
            out[hid]["price"] = {**ranked[("price", band)][hid], "group": band}
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
        by_country[_country(r["h"])].append(r)
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
    try:  # official logos (Wikimedia Commons), only where the file has been downloaded
        logos = json.loads((ROOT / "data" / "brand-logos.json").read_text(encoding="utf-8"))["brands"]
    except Exception:
        logos = {}
    for b in brands:
        lg = logos.get(b["brand"]) or {}
        if lg.get("file") and (ROOT / lg["file"]).exists():
            b["logo"] = "/" + lg["file"]

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

    def _spread(vals: list[int]) -> dict[str, Any]:
        q = st.quantiles(sorted(vals), n=4)
        return {"n": len(vals), "median": st.median(vals), "q1": round(q[0], 1), "q3": round(q[2], 1),
                "min": min(vals), "max": max(vals)}

    # guest score by price level (latest indicative nightly price check), with the best-rated hotels in each band
    by_band: dict[str, list] = defaultdict(list)
    for r in guests:
        b = _price_band(r["h"])
        if b:
            by_band[b].append(r)
    price = []
    for lo, hi, label in PRICE_BANDS:
        rs = by_band.get(label) or []
        if len(rs) < 8:
            continue
        top = sorted(rs, key=lambda r: (-r["g"], -r["rc"]))[:3]
        price.append({"band": label, **_spread([r["g"] for r in rs]),
                      "top": [{"name": r["h"]["name"], "g": r["g"], "rc": r["rc"]} for r in top]})

    # guest score by destination (town or island with 8+ rated hotels)
    by_area: dict[tuple[str, str], list] = defaultdict(list)
    for r in guests:
        if _city(r["h"]):
            by_area[(_country(r["h"]), _city(r["h"]))].append(r)
    areas = []
    for (country, area), rs in by_area.items():
        if len(rs) < 8:
            continue
        best = max(rs, key=lambda r: (r["g"], r["rc"]))
        label = area if area == country or area in ("Hong Kong", "Singapore", "Macau") else f"{area}, {country}"
        areas.append({"area": label, **_spread([r["g"] for r in rs]), "best": best["h"]["name"]})
    have_city = {a["area"].split(", ")[-1] for a in areas}
    by_cty: dict[str, list] = defaultdict(list)
    for r in guests:
        by_cty[_country(r["h"])].append(r)
    for country, rs in by_cty.items():  # whole countries (e.g. the Maldives) where no single town or island has 8+
        if country and len(rs) >= 8 and country not in have_city:
            best = max(rs, key=lambda r: (r["g"], r["rc"]))
            areas.append({"area": country, **_spread([r["g"] for r in rs]), "best": best["h"]["name"]})
    areas.sort(key=lambda x: (-x["median"], -x["n"]))

    # guests' favourites: highest guest score, from 500+ reviews so a small sample can't top the list
    fav = sorted((r for r in guests if r["rc"] >= 500), key=lambda r: (-r["g"], -r["rc"]))[:15]
    favourites = [{"name": r["h"]["name"], "where": _city(r["h"]) or _country(r["h"]), "g": r["g"], "rc": r["rc"]} for r in fav]
    return {"disappoint": low[:6], "brands": brands, "tiers": tier_stats, "scatter": scatter, "n": len(guests),
            "price": price, "areas": areas, "favourites": favourites}


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
    pr = d["price"]
    price_note = ""
    if len(pr) >= 2:
        price_note = (f"Typical guest score {'rises' if pr[-1]['median'] > pr[0]['median'] else 'goes'} from {pr[0]['median']:g} ({pr[0]['band']}) to {pr[-1]['median']:g} ({pr[-1]['band']}), "
                      "but every price level has hotels guests rate 98 or more, so a higher price is no guarantee.") if all(b["max"] >= 98 for b in pr) else (
                      f"Typical guest score: {pr[0]['median']:g} at {pr[0]['band']}, {pr[-1]['median']:g} at {pr[-1]['band']}.")
    data = {k: d[k] for k in ("disappoint", "brands", "tiers", "scatter", "price", "areas", "favourites")}
    page = (page.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
            .replace("__DATE__", datetime.now(timezone.utc).strftime("%-d %B %Y"))
            .replace("__NHOTELS__", f"{d['n']:,}")
            .replace("__NSCATTER__", f"{len(d['scatter']):,}")
            .replace("__BRAND_NOTE__", brand_note)
            .replace("__TIER_NOTE__", tier_note)
            .replace("__PRICE_NOTE__", price_note))
    site = "https://stayodds.com"
    h2 = re.sub(r"<title>.*?</title>", "<title>Guest Insights | StayOdds</title>", head, flags=re.S)
    h2 = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + f"{site}/insights/" + m.group(2), h2)
    h2 = re.sub(r'(<meta name="description" content=")[^"]*(")',
                lambda m: m.group(1) + "How guests rate luxury hotels: rankings by destination, brand and price, critics versus guests, and guests' favourites." + m.group(2), h2)
    out = dist / "insights"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(
        h2 + '<main><div style="max-width:960px;margin:0 auto;padding:28px 16px 56px">' + page + "</div></main>" + foot + "</body>\n</html>\n",
        encoding="utf-8",
    )
    return ["/insights/"]
