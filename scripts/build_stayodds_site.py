#!/usr/bin/env python3
"""
StayOdds Static SEO & Directory Builder (250+ Verified Luxury Hotels from Supabase)
- Reads the single source of truth from Supabase Postgres (zero AI-estimated data).
- Generates:
    1) data/stayodds-directory.json  (verified directory snapshot for fast initial paint)
    2) stayodds/<slug>/index.html    (250 real indexable SEO pages with JSON-LD Hotel/Review schema,
                                      Consensus Badge, Dual-Mode Opinion Gap, Middle Key Facts,
                                      Travelpayouts Drive monetization, and live Google Places hydration)
    3) sitemap.xml                   (256+ clean indexable URLs)
"""

from __future__ import annotations

from brand_logo_map import logo_for_hotel
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_rate_policy import apply_live_rate_policy  # noqa: E402
from stayodds_chrome import (  # noqa: E402
    ICO_ALERT,
    ICO_BED,
    ICO_CAM,
    ICO_LINK,
    ICO_PIN,
    ICO_SPARK,
    ICO_TROPHY,
    header as chrome_header,
    DETAIL_OTA_STRIP,
    partner_strip as chrome_partner_strip,
    yt_overlay,
    yt_watch_btn,
    YT_GLYPH as YT_GLYPH_INLINE,
)

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://uncharteditinerary.com"



MIN_GUEST_REVIEWS = 20


# --- Marriott direct booking through Partnerize (Nov 2026) ---------------------------------
# data/partnerize-campaigns.json is written by scripts/partnerize_campaigns.py (keys stay in repo
# secrets). Until a Marriott campaign is approved there is no camref and nothing changes.
MARRIOTT_BRAND_RE = re.compile(
    r"marriott|ritz-carlton|st\.? regis|\bw hotels?\b|\bjw\b|edition|luxury collection|bulgari|westin|sheraton|"
    r"le m[eé]ridien|autograph collection|design hotels|courtyard|element by westin|renaissance|aloft|tribute portfolio|gaylord",
    re.I,
)
MARRIOTT_NAME_RE = re.compile(r"ritz-carlton|st\.? regis|jw marriott|marriott|luxury collection|\bedition\b|bulgari|bvlgari", re.I)


def _marriott_camref() -> str:
    try:
        data = json.loads((ROOT / "data" / "partnerize-campaigns.json").read_text(encoding="utf-8"))
    except Exception:
        return ""
    for pub in data.get("publishers") or []:
        for c in pub.get("campaigns") or []:
            title = f"{c.get('title') or ''} {c.get('name') or ''}"
            if "marriott" in title.lower() and c.get("camref"):
                return str(c["camref"])
    return ""


MARRIOTT_CAMREF = _marriott_camref()


def marriott_affiliate_link(pid: str, name: str, city: str, brand: str) -> str:
    """Partnerize tracking link to the hotel on marriott.com, or "" when not Marriott / not approved yet."""
    if not MARRIOTT_CAMREF:
        return ""
    if not (MARRIOTT_BRAND_RE.search(brand) or MARRIOTT_NAME_RE.search(name)):
        return ""
    from urllib.parse import quote, urlencode
    dest = "https://www.marriott.com/search/findHotels.mi?" + urlencode(
        {"destinationAddress.destination": f"{name}, {city}".strip(", "), "roomCount": "1", "numAdultsPerRoom": "2"}
    )
    return f"https://prf.hn/click/camref:{MARRIOTT_CAMREF}/pubref:{pid}/destination:{quote(dest, safe='')}"

def _load_json(name: str) -> dict[str, Any]:
    try:
        return json.loads((Path(__file__).resolve().parent.parent / "data" / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


GUEST_RANKS: dict[str, dict[str, Any]] = {}  # filled in render_static_pages_from_directory()
NEARBY: dict[str, list[dict[str, Any]]] = {}  # closest scored hotels (build_insights.nearby_compare)
ALTERNATIVES: dict[str, list[dict[str, Any]]] = {}  # better-rated hotels nearby (build_insights.better_alternatives)
from water_rules import summarise as water_summary  # noqa: E402
ITWF = _load_json("isthewaterfree.json")  # water policy, critic lists (isthewaterfree.com, shared by its owner)
DINING = _load_json("hotel-dining.json")  # restaurants at the hotel, MICHELIN Guide (scripts/michelin_dining.py)
GUEST_QUOTES = _load_json("guest-quotes.json")  # real guest comments (scripts/fetch_guest_quotes.py)
COMMUNITY = _load_json("community-mentions.json").get("hotels", {})  # forum threads, blogs, press links
_NO_PLACE = {k for k, v in (_load_json("property-corrections.json").get("properties") or {}).items()
             if "google_place_id" in v and not v["google_place_id"]}  # Google listing was a different place: ignore it
GOOGLE_RATINGS = {k: v for k, v in _load_json("google-ratings.json").get("hotels", {}).items()
                  if (v.get("reviewCount") or 0) >= MIN_GUEST_REVIEWS and k not in _NO_PLACE}  # saved Google Maps ratings (fetch_google_ratings.py)


def _ta_ok(pid: str, t: dict[str, Any]) -> bool:
    return (t.get("reviewCount") or 0) >= MIN_GUEST_REVIEWS


TRIPADVISOR = ({k: v for k, v in _load_json("tripadvisor.json").get("hotels", {}).items() if _ta_ok(k, v)}
               if _load_json("tripadvisor-settings.json").get("enabled", True) else {})  # one switch removes it all  # a guest score needs at least this many verified reviews to be shown

def load_env_local() -> None:
    env_path = ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def sb_get_all(sb_url: str, key: str, table: str, select: str = "*") -> list[dict[str, Any]]:
    page_size = 1000
    all_rows: list[dict[str, Any]] = []
    for offset in range(0, 10000, page_size):
        url = f"{sb_url}/rest/v1/{table}?select={urllib.parse.quote(select)}&limit={page_size}&offset={offset}"
        req = urllib.request.Request(
            url,
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            page = json.loads(resp.read().decode("utf-8"))
        all_rows.extend(page)
        if len(page) < page_size:
            break
    return all_rows


def esc(val: Any) -> str:
    return html.escape(str(val or ""), quote=True)


_FALLBACK_HOTEL_PARTNERS = ("Trip.com", "Agoda", "Expedia", "Hotels.com")


def _hotel_partner_links() -> list[tuple[str, str]]:
    """(label, href) for the hotel booking partners already listed in DETAIL_OTA_STRIP (single source)."""
    found = {
        label.strip(): href
        for href, label in re.findall(r'href="([^"]+)"[^>]*>([^<]*?)\s*&nearr;', DETAIL_OTA_STRIP)
    }
    return [(name, found[name]) for name in _FALLBACK_HOTEL_PARTNERS if name in found]


def _photo_credit(src: Any, thumb: str) -> dict[str, str] | None:
    """Credit line for openly licensed (Wikimedia Commons) photos: 'wikimedia|<license>|<artist>|<file page url>'."""
    if not isinstance(src, str) or not src.startswith("wikimedia|"):
        return None
    parts = (src.split("|") + ["", "", ""])[:4]
    _, lic, artist, page = parts
    text = f"Photo: {artist.strip() or 'Wikimedia Commons'}" + (f", {lic.strip()}" if lic.strip() else "") + " via Wikimedia Commons"
    return {"text": text, "url": page.strip()}


def live_rate_unavailable_html(h: dict[str, Any]) -> str:
    """Message shown when someone asks for live pricing on a hotel we can't price reliably."""
    name = esc(h.get("name"))
    site = h.get("officialSite")
    if site:
        return (
            f'<span class="live-rate-note"><strong>Live pricing isn&rsquo;t available</strong> for {name}. '
            f"Check current rates and availability on the official site: "
            f'<a href="{esc(site["url"])}" target="_blank" rel="noopener noreferrer">{esc(site["partner"])} &nearr;</a></span>'
        )
    links: list[str] = []
    if h.get("bookingUrl"):
        links.append(
            f'<a href="{esc(h["bookingUrl"])}" target="_blank" rel="sponsored noopener noreferrer">Booking.com &nearr;</a>'
        )
    links += [
        f'<a href="{esc(href)}" target="_blank" rel="sponsored noopener noreferrer">{esc(label)} &nearr;</a>'
        for label, href in _hotel_partner_links()
    ]
    return (
        f'<span class="live-rate-note"><strong>Live pricing isn&rsquo;t available</strong> for {name} right now. '
        f"Compare current rates on: {' &bull; '.join(links)}</span>"
    )


def fmt_score_num(v: float | int | None) -> str:
    if v is None:
        return ""
    f = float(v)
    if f.is_integer():
        return str(int(f))
    return f"{f:.2f}".rstrip("0").rstrip(".")


def is_score_unverified(e: dict[str, Any]) -> bool:
    if not isinstance(e, dict):
        return False
    if e.get("scoreUnverified") is True:
        return True
    txt = f"{e.get('rawScore') or ''} {e.get('takeaway') or ''}".lower()
    return "unable to verify" in txt or "unverified" in txt


def evidence_label(review_count: Any, has_guest: bool, critics: int) -> str:
    """'4,438 reviews + 2 critics' - what a StayOdds score is based on."""
    parts = []
    if has_guest:
        try:
            rc = int(review_count or 0)
        except (TypeError, ValueError):
            rc = 0
        parts.append(f"{rc:,} review{'' if rc == 1 else 's'}" if rc > 0 else "guest reviews")
    if critics:
        parts.append(f"{critics} critic{'' if critics == 1 else 's'}")
    return " + ".join(parts) if parts else "no scores yet"


def _round_half_up(x: float) -> int:
    """Same rounding as the site's JavaScript (Math.round): 92.5 -> 93, so page and live scores always match."""
    import math
    return int(math.floor(float(x) + 0.5))


def compute_stayodds_py(h: dict[str, Any]) -> dict[str, Any]:
    first_hand = bool(h.get("visitedByUs") and h.get("overall") is not None and h.get("scores"))
    visited = bool(h.get("visitedByUs"))
    personal_score_25 = None
    personal_score_max = 25
    personal_score_label = None
    if first_hand and h.get("scores"):
        s = h["scores"]
        vals = [float(s[k]) for k in ("value", "rooms", "grounds", "food", "service") if s.get(k) is not None]
        if vals:
            personal_score_25 = round(sum(vals), 2)
            personal_score_max = len(vals) * 5
            personal_score_label = f"{fmt_score_num(personal_score_25)} / {personal_score_max}"
    ours100 = (
        _round_half_up(((personal_score_25 / personal_score_max) * 100))
        if personal_score_25 is not None
        else (_round_half_up((float(h["overall"]) * 20)) if first_hand else None)
    )

    editorial = [e for e in (h.get("editorialRatings") or []) if str(e.get("sourceUrl", "")).startswith("http")]
    awards = [a for a in (h.get("officialAwards") or []) if str(a.get("sourceUrl", "")).startswith("http")]
    yt_reviews = [y for y in (h.get("youtubeReviews") or []) if str(y.get("sourceUrl", "")).startswith("http")]

    # STRICT RULE: Numeric critic score ONLY comes from published, verified numeric critic reviews (e.g. 9/10, 18/20, 88/100).
    # Any score_unverified entry ("Score/points awarded — unable to verify exact figure"), non-scored editorial article,
    # or official award is strictly excluded from numeric math and displayed transparently with its direct source link.
    scored_editorial = [
        e for e in editorial if e.get("normalized100") is not None and not is_score_unverified(e)
    ]
    unverified_editorial = [e for e in editorial if is_score_unverified(e)]
    critic_scores = [int(e["normalized100"]) for e in scored_editorial]
    critic100 = _round_half_up((sum(critic_scores) / len(critic_scores))) if critic_scores else None
    primary_critic = scored_editorial[0] if scored_editorial else None

    vg = (h.get("verifiedGuest") or {}).get("licensed")
    raw_guest100 = int(vg["normalized100"]) if vg and vg.get("normalized100") else None
    guest_rc = vg.get("reviewCount") if vg else None
    if raw_guest100 is not None and guest_rc is not None and 0 < int(guest_rc) < 40:
        guest100 = _round_half_up(((raw_guest100 * int(guest_rc) + 90 * 8) / (int(guest_rc) + 8)))
        guest_dampened = True
    else:
        guest100 = raw_guest100
        guest_dampened = False

    # LAYER 1: Universal External Consensus Baseline
    market_odds = None
    market_src_cnt = 0
    source_basis_short = "Live Google"
    if critic100 is not None and guest100 is not None:
        market_odds = _round_half_up((critic100 * 0.35 + guest100 * 0.65))
        market_src_cnt = 2
        source_basis_short = "2 sources • Critics + Guests"
    elif guest100 is not None:
        market_odds = guest100
        market_src_cnt = 1
        source_basis_short = "1 source • Guest Reviews"
    elif critic100 is not None:
        market_odds = critic100
        market_src_cnt = 1
        source_basis_short = "1 source • Critics"

    # LAYER 2: Two-Track Score ("Uncharted Verified" vs "StayOdds")
    score_track = "verified" if (first_hand and ours100 is not None) else "market"
    if score_track == "verified":
        score_track_label = "Uncharted Verified"
    elif market_src_cnt >= 1:
        # show what the score rests on: number of guest reviews and published critics
        score_track_label = "StayOdds • " + evidence_label(
            guest_rc if guest100 is not None else None, guest100 is not None, len(critic_scores) if critic100 is not None else 0
        )
    else:
        score_track_label = "StayOdds"
    founder_vs_market_delta = (ours100 - market_odds) if (first_hand and ours100 is not None and market_odds is not None) else None

    weights = {"firstHand": 0, "market": 0, "critics": 0, "guests": 0}
    overall_idx = None
    odds = None
    spread100 = None
    status_badge = "Award-Winning" if awards else "Global Directory"
    status_tone = "teal" if awards else "slate"
    is_consensus = False
    formula = (
        f"Awarded {' • '.join(a['label'] for a in awards)} — live Google reviews check on this page."
        if awards
        else "Live Google guest reviews check on this page."
    )

    active = [v for v in [ours100, critic100, guest100] if v is not None]
    src_cnt = len(active)

    if score_track == "verified" and ours100 is not None:
        if market_odds is not None:
            overall_idx = _round_half_up((ours100 * 0.70 + market_odds * 0.30))
            weights = {
                "firstHand": 70,
                "market": 30,
                "critics": 11 if (critic100 is not None and guest100 is not None) else (30 if critic100 is not None else 0),
                "guests": 19 if (critic100 is not None and guest100 is not None) else (30 if guest100 is not None else 0),
            }
            formula = f"70% Uncharted Stay ({personal_score_label or f'{ours100}%'}) • 30% Consensus ({market_odds}%)"
            source_basis_short = f"Uncharted Stay + {market_src_cnt} source{'s' if market_src_cnt != 1 else ''}"
        else:
            overall_idx = ours100
            weights = {"firstHand": 100, "market": 0, "critics": 0, "guests": 0}
            status_badge = "Uncharted Verified"
            status_tone = "accent"
            formula = f"100% Uncharted Video Stay ({personal_score_label or f'{ours100}%'})"
            source_basis_short = "1 source • Uncharted Stay"
    else:
        overall_idx = market_odds
        if critic100 is not None and guest100 is not None:
            weights = {"firstHand": 0, "market": 100, "critics": 35, "guests": 65}
            formula = "Based on 2 sources: Published Critics (35%) + Guest Reviews (65%)"
        elif guest100 is not None:
            weights = {"firstHand": 0, "market": 100, "critics": 0, "guests": 100}
            status_badge = "1 Data Source"
            status_tone = "teal"
            formula = "Based on 1 source (Guest Reviews" + (", small-sample adjusted)" if guest_dampened else ")")
        elif critic100 is not None:
            weights = {"firstHand": 0, "market": 100, "critics": 100, "guests": 0}
            status_badge = "1 Data Source"
            status_tone = "slate"
            formula = "Based on 1 source (Published Critics)"

    odds = overall_idx
    if src_cnt >= 2 and overall_idx is not None:
        is_consensus = True
        spread100 = abs(founder_vs_market_delta) if (score_track == "verified" and founder_vs_market_delta is not None) else (max(active) - min(active))
        if spread100 <= 6:
            status_badge, status_tone = "Strong Agreement", "accent"
        elif spread100 <= 12:
            status_badge, status_tone = "Mostly Aligned", "teal"
        else:
            status_badge, status_tone = "Opinions Differ", "amber"

    left100 = ours100 if first_hand else critic100
    right100 = market_odds if first_hand else guest100
    delta100 = (left100 - right100) if (left100 is not None and right100 is not None) else None

    if delta100 is not None:
        critic_name = (
            primary_critic["sourceName"]
            if len(scored_editorial) == 1 and primary_critic
            else f"{len(scored_editorial)} published critics"
        )
        if abs(delta100) <= 5:
            gap_head = (
                f"Tight agreement ({'+' if delta100 >= 0 else ''}{delta100} pts) — The Uncharted Itinerary stay matched the wider consensus."
                if first_hand
                else f"Tight agreement ({'+' if delta100 >= 0 else ''}{delta100} pts) — {critic_name} and real guests agree."
            )
        elif delta100 > 5:
            gap_head = (
                f"The Uncharted Itinerary rated this +{delta100} pts higher than the wider consensus — see what stood out below."
                if first_hand
                else f"{critic_name} rated this +{delta100} pts higher than real guests."
            )
        else:
            gap_head = (
                f"The Uncharted Itinerary rated this {delta100} pts stricter than the wider consensus — see what held it back below."
                if first_hand
                else f"Real guests rated this +{abs(delta100)} pts higher than {critic_name}."
            )
    else:
        if first_hand:
            gap_head = "The Uncharted Itinerary's filmed stay leads here — live Google reviews check on this page."
        elif unverified_editorial and not scored_editorial:
            names = ", ".join(u["sourceName"] for u in unverified_editorial)
            gap_head = f"{names} awards a score (unverified figure — excluded from numeric math)."
        elif awards:
            gap_head = f"Recognised with {' • '.join(a['label'] for a in awards)} — compare with real guest reviews below."
        else:
            gap_head = f"{formula}."

    is_full_unscored = visited and not first_hand and h.get("coverageType") != "Short Tour"
    return {
        "firstHand": first_hand,
        "visited": visited,
        "scoreTrack": score_track,
        "scoreTrackLabel": score_track_label,
        "sourceBasisShort": source_basis_short,
        "tierLabel": (
            "Uncharted Verified"
            if first_hand
            else ("Uncharted Video" if is_full_unscored else ("Uncharted Short" if visited else "Global Directory"))
        ),
        "personalScore25": personal_score_25,
        "personalScoreMax": personal_score_max,
        "personalScoreLabel": personal_score_label,
        "ours100": ours100,
        "critic100": critic100,
        "primaryCritic": primary_critic,
        "scoredEditorial": scored_editorial,
        "unverifiedEditorial": unverified_editorial,
        "guest100": guest100,
        "marketOdds": market_odds,
        "marketSourceCount": market_src_cnt,
        "founderVsMarketDelta": founder_vs_market_delta,
        "overallIndex": overall_idx,
        "greatStayOdds": odds,
        "spread100": spread100,
        "sourceCount": src_cnt,
        "isConsensus": is_consensus,
        "statusBadge": status_badge,
        "statusTone": status_tone,
        "weights": weights,
        "formula": formula,
        "left100": left100,
        "right100": right100,
        "delta100": delta100,
        "gapHeadline": gap_head,
        "editorial": editorial,
        "awards": awards,
        "ytReviews": yt_reviews,
        "vg": vg,
    }


CLIMATE_RULES_PY: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"maldives|baa atoll|noonu|raa atoll|ari atoll|mal[eé]|lhaviyani|gaafu|laamu|dhaalu", re.I), "Nov–Apr", "Dry NE monsoon, calmest lagoons & clearest house-reef visibility"),
    (re.compile(r"bali|lombok|gili|labuan bajo|flores|sumba|ubud|seminyak|canggu|nusa dua|uluwatu|jimbaran|indonesia|penida|bintan|jakarta", re.I), "May–Oct", "Dry season with sunny skies, lower humidity & calm seas"),
    (re.compile(r"koh samui|samui|koh phangan", re.I), "Jan–Aug", "Gulf of Thailand dry window (avoids Oct–Dec NE monsoon)"),
    (re.compile(r"krabi|phuket|yao noi|bangkok|chiang mai|chiang rai|khao lak|koh kood|thailand", re.I), "Nov–Apr", "Cool dry season & calm Andaman Sea conditions"),
    (re.compile(r"seychelles|mah[eé]|praslin|f[eé]licit[eé]|platte|desroches|north island", re.I), "Apr–May & Oct–Mar", "Calmest seas & best diving in Apr–May and Oct–Nov transition windows"),
    (re.compile(r"mauritius", re.I), "May–Nov", "Cool, dry winter & spring avoiding Jan–Mar cyclone season"),
    (re.compile(r"bora bora|tahiti|tetiaroa|moorea|french polynesia", re.I), "May–Oct", "Dry winter season with lower humidity and clear turquoise lagoons"),
    (re.compile(r"fiji|laucala|vomo|kokomo|malolo", re.I), "May–Oct", "Dry trade-wind season outside Nov–Apr cyclone window"),
    (re.compile(r"riviera maya|cancun|canc[uú]n|costa mujeres|playa mujeres|tulum|mayakoba|caribbean|st\.?\s*barts|st\.?\s*lucia|anguilla|turks|caicos|antigua|barbados|jamaica|bahamas|grenada|aruba|cura[cç]ao|st\.?\s*kitts|dominican|punta cana|cap cana|la romana|puerto rico|bermuda|cayman|st\.?\s*vincent|canouan|nevis|british virgin|virgin gorda", re.I), "Dec–Apr", "Dry season with lower hurricane & summer sargassum seaweed risk"),
    (re.compile(r"cabo|punta mita|punta de mita|nayarit|riviera nayarit|zihuatanejo|careyes|mexico city|san miguel|oaxaca|mexico", re.I), "Nov–May", "Dry Pacific season with sunny skies and whale-watching in winter"),
    (re.compile(r"costa rica|papagayo|belize|panama|nicaragua", re.I), "Dec–Apr", "Dry season with clearest coastal water & trail access"),
    (re.compile(r"st\.?\s*moritz|gstaad|courchevel|meg[eè]ve|andermatt|zermatt|verbier|bürgenstock|burgenstock|alps|dolomites|aspen|vail|jackson hole|deer valley|park city|whistler|niseko|estes park|banff|chamonix|lech|kitzb", re.I), "Dec–Mar (Ski) & Jun–Sep", "Prime snowpack in winter; crisp alpine hiking & lakes in summer"),
    (re.compile(r"dubai|abu dhabi|oman|muscat|zighy|doha|qatar|red sea|alula|saudi|jordan|marrakech|morocco|egypt", re.I), "Nov–Apr", "Pleasant 22–30°C sunshine avoiding extreme summer heat"),
    (re.compile(r"udaipur|jaipur|jodhpur|mumbai|new delhi|delhi|hyderabad|bengaluru|chennai|rajasthan|ranthambore|jawai|india", re.I), "Oct–Mar", "Cool dry season outside summer heat and Jun–Sep monsoon"),
    (re.compile(r"sri lanka|yala|galle|tangalle|weligama|colombo", re.I), "Dec–Apr", "Dry south & west coast season with calm seas"),
    (re.compile(r"tokyo|kyoto|osaka|hakone|amanemu|naoshima|okinawa|japan", re.I), "Mar–May & Oct–Nov", "Cherry blossom spring & crisp autumn foliage seasons"),
    (re.compile(r"singapore|langkawi|kuala lumpur|malaysia|hong kong|seoul|korea|vietnam|hanoi|ph[uú] qu[oố]c|ninh van|bai san ho|cambodia|song saa|phnom penh|siem reap|shanghai|beijing|china|taipei", re.I), "Nov–Apr", "Drier, less humid months across East & Southeast Asia"),
    (re.compile(r"serengeti|masai mara|kenya|tanzania|botswana|okavango|kruger|sabi|singita|rwanda|zambia|zimbabwe|namibia|safari", re.I), "Jun–Oct & Jan–Feb", "Dry safari game-viewing season with sparse bush & wildlife concentrations"),
    (re.compile(r"cape town|winelands|franschhoek|hermanus|south africa", re.I), "Nov–Apr", "Warm, dry austral summer ideal for beaches & wine country"),
    (re.compile(r"sydney|melbourne|brisbane|kangaroo island|southern ocean|qualia|hayman|australia|queenstown|auckland|new zealand", re.I), "Nov–Apr", "Warm Southern Hemisphere spring, summer & early autumn"),
    (re.compile(r"tenerife|lanzarote|gran canaria|fuerteventura|la gomera|la palma|costa adeje|maspalomas|meloneras|playa blanca|corralejo|canary", re.I), "Year-Round (Oct–May Winter Sun)", "Europe's warm year-round subtropical islands — sunny 21–27°C beaches even in winter"),
    (re.compile(r"amalfi|positano|capri|como|portofino|tuscany|florence|rome|milan|venice|sardinia|sicily|taormina|puglia|italy|greece|santorini|mykonos|athens|paros|crete|mallorca|ibiza|marbella|barcelona|madrid|spain|algarve|lisbon|douro|comporta|portugal|bodrum|istanbul|turkey|antibes|cannes|st\.?\s*tropez|riviera|provence|monaco|croatia|dubrovnik|montenegro", re.I), "May–Oct", "Warm Mediterranean sunshine & full seasonal beach-club openings"),
    (re.compile(r"london|cotswolds|castle combe|wiltshire|somerset|scotland|uk|united kingdom|ireland|paris|france|zurich|geneva|switzerland|vienna|austria|amsterdam|netherlands|germany|munich|berlin|stockholm|copenhagen|norway|iceland|blue lagoon", re.I), "May–Sep", "Long daylight hours, mild temperatures & peak garden/terrace season"),
    (re.compile(r"hawaii|maui|lanai|lānaʻi|kauai|oahu|big island|kona", re.I), "Year-Round (Apr–Oct driest)", "Warm year-round; Apr–Oct driest, Dec–Mar peak whale-watching"),
    (re.compile(r"mendoza|buenos aires|patagonia|argentina|rio|s[aã]o paulo|brazil|peru|cusco|chile|atacama|colombia|cartagena", re.I), "Oct–Apr", "Warm spring/summer weather & wine harvest months in South America"),
    (re.compile(r"florida|miami|palm beach|keys|scottsdale|arizona|sedona|amangiri|utah|desert", re.I), "Nov–Apr", "Comfortable sunny winter/spring escaping summer heat & humidity"),
    (re.compile(r"california|napa|big sur|santa monica|beverly hills|los angeles|malibu|montecito|new york|manhattan|vermont|new england|georgia|sea island|charleston|washington|chicago|boston|usa|united states|canada|toronto|vancouver", re.I), "Apr–Oct", "Pleasant spring, summer & crisp autumn travel seasons"),
]

ROOM_TIP_KEYWORDS_PY = re.compile(
    r"\b(villa|suite|main\s+building|overwater|beach\s+villa|pool\s+villa|pavilion|cottage|room|book\s+direct|upgrade|lagoon|sunset|sunrise|cliff|2-bedroom|bunk|pod|bungalow|ground[- ]floor)\b",
    re.I,
)


def get_best_months_py(h: dict[str, Any]) -> tuple[str, str]:
    hay = f"{h.get('name', '')} {h.get('location', '')} {h.get('country', '')} {h.get('region', '')}"
    for pat, label, reason in CLIMATE_RULES_PY:
        if pat.search(hay):
            return label, reason
    return "Spring & Autumn", "Mild shoulder-season conditions"


VERIFIED_FIRST_HAND_ROOM_TIPS_PY: dict[str, str] = {
    "st-regis-bali": "Skip the older 2008 main-building suites — book a private villa instead for fresher finishes and more space.",
    "ritz-carlton-bali": "Book a Pavilion Pool Villa for newer interiors, direct lagoon-style privacy, and strong value vs. nearby Nusa Dua rivals.",
    "the-sira-lombok": "Book a Beachfront Pool Villa for a brand-new layout, private pool, butler care, and direct sand access.",
    "w-bali-seminyak": "Book a One-Bedroom Oasis Pool Villa (~£400/night) — one of the best-value private-pool villa categories in Seminyak.",
    "radisson-blu-maldives": "Every villa category includes a private infinity pool and overwater hammock — even entry villas deliver the full Maldives setup.",
    "four-seasons-jimbaran": "Ask for a renovated villa — older 30-year-old villa interiors felt noticeably bare on our stay (3/5 Rooms score).",
    "w-maldives": "Book a refurbished overwater villa with direct reef access so you can snorkel straight off your deck.",
    "bask-gili-meno": "Book a Beachfront Pool Villa for large private pools with turtle snorkeling steps from your sun lounger.",
    "phulay-bay-krabi": "Book a Pool Villa — the cavernous 20ft-ceiling layouts are the centerpiece (and a standout 80k Bonvoy points sweet spot).",
    "w-koh-samui": "All 75 villas come with a private pool — just note 2010 villa finishes feel slightly older than newer Samui rivals.",
    "como-uma-canggu": "Modern rooms feature outdoor showers and real soundproofing from busy Canggu — a sharp ~£200/night luxury base.",
    "regent-bali-canggu": "Book a 1-Bedroom Suite — flawlessly designed, spacious room hardware is a standout highlight right on Canggu beach.",
    "taaktana-labuan-bajo": "Pick between the brand-new Private Pool Villas or Overwater Villas — both include dedicated 24/7 butler service.",
    "finolhu-baa-atoll": "Book an Ocean Water Villa for spacious overwater living with easy access to the 1.8km sandbank.",
    "st-regis-bora-bora": "Overwater Villas start at a massive 1,550+ sq ft — classic styling with one of Bora Bora's largest room footprints.",
    "westin-bora-bora": "Fresh modern Polynesian bungalows & villas — newer and more comfortable inside than St. Regis next door.",
    "four-seasons-koh-samui": "Hillside Pool Villas deliver iconic palm-framed ocean views, though classic interiors feel slightly dated for the price.",
    "le-meridien-maldives": "Stylish modern beach and overwater villas — one of the smartest Marriott Bonvoy points redemptions in the Maldives.",
    "w-algarve": "Watch for elite suite upgrades (the Supreme Two-Bedroom Suite is standout) — note a few suite layouts have quirky details.",
    "rayavadee-krabi": "Two-story jungle Pavilions tucked beneath limestone cliffs offer real privacy across the boat-only peninsula.",
    "cocana-gili-t": "Book a Private Pool Villa for true modern 5-star resort comfort on Gili Trawangan.",
    "manor-house-castle-combe": "Choose between historic 14th-century manor rooms or picturesque garden cottages beside Castle Combe village.",
    "heights-melasti-bali": "The modern 2-Bedroom Private Pool Villa is strong Uluwatu value (pack mosquito repellent for open-air bathrooms).",
    "the-pod-singapore": "Book a single 'bookshelf' capsule with privacy blind for 1–2 night solo stopovers (expect shared-room noise).",
    "the-edge-bali": "Book an ultra-private Cliffside Villa — includes privileged quiet access outside busy dayclub hours.",
    "sebali-nusa-penida": "Book a Pool-Access Room for rare beachfront resort polish on Nusa Penida.",
    "hiliwatu-ubud": "Modern rainforest-valley balcony suites deliver dramatic jungle views at a fraction of Mandapa's nightly rate.",
    "four-seasons-bangkok": "Standard riverside rooms already outclass many resort suites — spacious Jean-Michel Gathy design throughout.",
    "the-ungasan-bali": "Private multi-bedroom clifftop villas are grouped into intimate neighborhoods sharing huge infinity pools.",
    "kin-house-wiltshire": "Primarily booked as an exclusive-use Georgian house for private groups and weddings rather than individual rooms.",
}

SPECIFIC_ROOM_CATEGORY_PY = re.compile(
    r"\b(\d+[- ]?(?:bedroom|room|suite|villa|casita|bungalow|pavilion|tented\s+(?:suite|villa))s?|"
    r"all[- ](?:suite|villa|casita|pool[- ]villa)|"
    r"overwater\s+(?:pool\s+)?villas?|beachfront\s+(?:pool\s+)?villas?|beach\s+(?:pool\s+)?villas?|"
    r"private[- ]pool\s+(?:villas?|suites?)|swim[- ]up\s+(?:rooms?|suites?)|"
    r"ocean[- ]view\s+(?:rooms?|suites?|villas?)|cliffside\s+(?:pool\s+)?villas?|"
    r"hillside\s+(?:pool\s+)?(?:villas?|casitas?)|lagoon\s+(?:pool\s+)?villas?|"
    r"tented\s+(?:suites?|villas?|camps?)|treehouses?|penthouse\s+suites?|"
    r"junior\s+suites?|garden\s+(?:pool\s+)?villas?|bungalows?|casitas?)\b",
    re.I,
)


def _extract_strict_room_clause_py(raw_text: str | None) -> str | None:
    txt = str(raw_text or "").strip()
    if not txt:
        return None
    parts = [s.strip() for s in re.split(r"(?:(?<=[.!?])\s+|\s+[—–]\s+|;\s+)", txt) if s.strip()]
    for part in parts:
        if not SPECIFIC_ROOM_CATEGORY_PY.search(part):
            continue
        sub_parts = re.split(r",\s+", part)
        room_segs = [seg for seg in sub_parts if SPECIFIC_ROOM_CATEGORY_PY.search(seg)]
        if room_segs:
            clean = ", ".join(room_segs[:2])
            clean = re.sub(r"^(?:featuring|with|and|plus)\s+", "", clean, flags=re.I).strip().rstrip(".;, ")
            if 16 <= len(clean) <= 180:
                return clean[0].upper() + clean[1:] + "."
    return None


def get_verified_room_tip_py(h: dict[str, Any]) -> dict[str, Any] | None:
    hid = str(h.get("id") or "").strip()
    if hid in VERIFIED_FIRST_HAND_ROOM_TIPS_PY:
        return {
            "text": VERIFIED_FIRST_HAND_ROOM_TIPS_PY[hid],
            "is_uncharted": True,
            "label": "Rooms to Book (Uncharted Note)",
        }
    for cand in (h.get("standout"), h.get("verdict")):
        clause = _extract_strict_room_clause_py(cand)
        if clause:
            return {
                "text": clause,
                "is_uncharted": False,
                "label": "Room & Villa Setup",
            }
    return None


def compute_price_medians(directory: list[dict[str, Any]]) -> dict[str, dict[str, tuple[int, int]]]:
    """Compute real GBP nightly medians per country and region (only when >=3 priced properties exist)."""
    import statistics

    by_country: dict[str, list[float]] = {}
    by_region: dict[str, list[float]] = {}
    for h in directory:
        snap = h.get("priceSnapshot") or {}
        gbp = snap.get("nightlyGbp")
        if isinstance(gbp, (int, float)) and gbp > 0:
            if h.get("country"):
                by_country.setdefault(h["country"], []).append(float(gbp))
            if h.get("region"):
                by_region.setdefault(h["region"], []).append(float(gbp))
    return {
        "country": {k: (int(round(statistics.median(v))), len(v)) for k, v in by_country.items() if len(v) >= 3},
        "region": {k: (int(round(statistics.median(v))), len(v)) for k, v in by_region.items() if len(v) >= 3},
    }


_CITY_TOKENS_RE = re.compile(
    r"\b(tokyo|kyoto|osaka|london|paris|rome|milan|venice|florence|new york|manhattan|miami|beverly hills|los angeles|san francisco|chicago|boston|bangkok|singapore|hong kong|seoul|sydney|melbourne|dubai|abu dhabi|doha|cairo|istanbul|barcelona|madrid|lisbon|zurich|geneva|vienna|amsterdam|munich|berlin|stockholm|copenhagen|mumbai|new delhi|delhi|kuala lumpur|taipei|shanghai|beijing|mexico city|buenos aires|s[aã]o paulo|rio de janeiro|cape town|auckland)\b",
    re.I,
)
_SAFARI_LODGE_RE = re.compile(
    r"\b(safari|serengeti|masai mara|okavango|kruger|sabi|singita|tented camp|game reserve|bush|wilderness|gorilla|nyungwe|jawai|ranthambore|uluru|outback|kangaroo island|fiordland)\b",
    re.I,
)
_SKI_ALPINE_RE = re.compile(
    r"\b(ski|courchevel|st\.?\s*moritz|gstaad|zermatt|verbier|meg[eè]ve|andermatt|alps|dolomites|aspen|vail|jackson hole|deer valley|park city|whistler|niseko|chamonix|lech|kitzb|mountain lodge)\b",
    re.I,
)
_BEACH_ISLAND_RE = re.compile(
    r"\b(maldives|atoll|island|beach|overwater|lagoon|reef|bali|lombok|gili|samui|phuket|krabi|bora bora|tahiti|fiji|seychelles|mauritius|santorini|mykonos|paros|crete|amalfi|capri|sardinia|mallorca|ibiza|bodrum|riviera maya|canc[uú]n|tulum|cabo|punta mita|anguilla|st\.?\s*barth|turks|caicos|antigua|barbados|jamaica|bahamas|st\.?\s*lucia|hawaii|maui|lanai|kauai|okinawa|zanzibar|red sea|alula)\b",
    re.I,
)
_COUNTRYSIDE_RE = re.compile(
    r"\b(cotswolds|somerset|wiltshire|countryside|estate|manor|ch[aâ]teau|tuscany|umbria|provence|winelands|franschhoek|napa|sonoma|hudson valley|vermont|farm|ryokan|hakone|karuizawa|yakushima|naoshima|kyushu|highlands|scotland|ireland)\b",
    re.I,
)
_ALL_INCLUSIVE_RE = re.compile(r"\ball[- ]inclusive\b", re.I)


def _extract_nightly_gbp(h: dict[str, Any]) -> float | None:
    snap = h.get("priceSnapshot") or {}
    gbp = snap.get("nightlyGbp")
    if isinstance(gbp, (int, float)) and gbp > 0:
        return float(gbp)
    pr = str(h.get("priceRange") or "")
    m = re.search(r"([\d,]{3,6})", pr)
    if m:
        try:
            v = float(m.group(1).replace(",", ""))
            if v > 0:
                return v
        except ValueError:
            pass
    return None


def _classify_setting(h: dict[str, Any]) -> str:
    hay = f"{h.get('name', '')} {h.get('location', '')} {h.get('standout', '')} {(h.get('keyFacts') or {}).get('beachOrReef', '')}"
    if _SAFARI_LODGE_RE.search(hay):
        return "safari"
    if _SKI_ALPINE_RE.search(hay):
        return "alpine"
    # Urban city check before beach so "Four Seasons Bangkok" or "Claridge's Mayfair, London" stays city
    loc_name = f"{h.get('name', '')} {h.get('location', '')}"
    if _CITY_TOKENS_RE.search(loc_name) and not re.search(r"\b(beach resort|overwater|island resort|atoll)\b", loc_name, re.I):
        return "city"
    if _BEACH_ISLAND_RE.search(hay):
        return "beach"
    if _COUNTRYSIDE_RE.search(hay):
        return "countryside"
    return "resort"


def _locality_tokens(h: dict[str, Any]) -> set[str]:
    raw = f"{h.get('location', '')}"
    stop = {"the", "of", "and", "at", "in", "by", "bay", "beach", "island", "resort", "city", "north", "south", "east", "west", "new"}
    parts = [p.strip().lower() for p in re.split(r"[,/&–—\-]+", raw) if p.strip()]
    tokens: set[str] = set()
    for p in parts:
        if len(p) >= 3 and p not in stop:
            tokens.add(p)
        for w in p.split():
            if len(w) >= 4 and w not in stop:
                tokens.add(w)
    return tokens


def _rival_similarity_score(
    base: dict[str, Any],
    cand: dict[str, Any],
    odds_map: dict[str, dict[str, Any]],
) -> float:
    score = 0.0
    base_loc = _locality_tokens(base)
    cand_loc = _locality_tokens(cand)
    same_country = base.get("country") == cand.get("country")
    same_region = base.get("region") == cand.get("region")

    if same_country and base_loc and cand_loc and (base_loc & cand_loc):
        score += 48.0
    elif same_country:
        score += 18.0
    elif same_region:
        score += 5.0
    else:
        return -999.0

    set_a = _classify_setting(base)
    set_b = _classify_setting(cand)
    if set_a == set_b:
        score += 24.0
    elif (set_a == "city" and set_b in ("beach", "safari", "countryside", "alpine")) or (
        set_b == "city" and set_a in ("beach", "safari", "countryside", "alpine")
    ):
        score -= 22.0
    elif (set_a == "safari" and set_b == "beach") or (set_b == "safari" and set_a == "beach"):
        score -= 16.0

    ai_a = bool(_ALL_INCLUSIVE_RE.search(f"{base.get('priceRange', '')} {base.get('name', '')}"))
    ai_b = bool(_ALL_INCLUSIVE_RE.search(f"{cand.get('priceRange', '')} {cand.get('name', '')}"))
    if ai_a != ai_b:
        score -= 12.0

    p_a = _extract_nightly_gbp(base)
    p_b = _extract_nightly_gbp(cand)
    if p_a and p_b:
        ratio = max(p_a, p_b) / min(p_a, p_b)
        if ratio <= 1.45:
            score += 22.0
        elif ratio <= 1.95:
            score += 12.0
        elif ratio <= 2.6:
            score += 2.0
        else:
            score -= 20.0

    oa = odds_map[base["id"]]
    ob = odds_map[cand["id"]]
    sa, sb = oa.get("greatStayOdds"), ob.get("greatStayOdds")
    if sa is not None and sb is not None:
        diff = abs(sa - sb)
        if diff <= 6:
            score += 8.0
        elif diff <= 12:
            score += 4.0
        score += 4.0
    elif sb is not None or ob.get("awards"):
        score += 3.0

    # Gentle preference for first-hand verified stays ONLY as a relevance boost, never overriding locality/price fit
    if ob.get("firstHand"):
        score += 7.0
    elif ob.get("visited"):
        score += 3.0

    # Tie-breaker toward stronger peer StayOdds %
    score += ((sb or 80) / 1000.0)
    return score


def pick_comparable_rivals(
    hotel: dict[str, Any],
    directory: list[dict[str, Any]],
    odds_map: dict[str, dict[str, Any]],
    limit: int = 3,
) -> list[dict[str, Any]]:
    pool = [r for r in directory if r["id"] != hotel["id"] and r["country"] == hotel["country"]]
    if len(pool) < limit:
        seen = {r["id"] for r in pool}
        pool += [r for r in directory if r["id"] != hotel["id"] and r["id"] not in seen and r["region"] == hotel["region"]]
    if len(pool) < limit:
        seen = {r["id"] for r in pool}
        pool += [r for r in directory if r["id"] != hotel["id"] and r["id"] not in seen]

    scored = sorted(
        pool,
        key=lambda r: (-_rival_similarity_score(hotel, r, odds_map), r["name"]),
    )
    return scored[:limit]


def pick_destination_matchups(
    dest_hotels: list[dict[str, Any]],
    odds_map: dict[str, dict[str, Any]],
    limit: int = 3,
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    """Pick up to 3 diverse, genuinely comparable local matchups + a cohesive 3-hotel trio for a destination guide."""
    if len(dest_hotels) < 2:
        return [], dest_hotels[:3]

    # Rank anchor candidates: iconic / first-hand / high-StayOdds + priced/awarded stays first
    def anchor_rank(h: dict[str, Any]) -> tuple[int, int, int, str]:
        o = odds_map[h["id"]]
        fh = 1 if o.get("firstHand") else 0
        has_awards = 1 if o.get("awards") else 0
        sc = o.get("greatStayOdds") or 0
        return (-fh, -has_awards, -sc, h["name"])

    anchors = sorted(dest_hotels, key=anchor_rank)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    seen_pairs: set[tuple[str, str]] = set()
    used_anchors: set[str] = set()

    for a in anchors:
        if len(pairs) >= limit:
            break
        if a["id"] in used_anchors and len(anchors) >= 6:
            continue
        best_b = None
        best_sim = -999.0
        for b in dest_hotels:
            if b["id"] == a["id"]:
                continue
            key = tuple(sorted((a["id"], b["id"])))
            if key in seen_pairs:
                continue
            sim = _rival_similarity_score(a, b, odds_map)
            # Small bonus for unused B so the 3 matchups showcase varied local rivalries
            if b["id"] not in used_anchors:
                sim += 4.0
            if sim > best_sim:
                best_sim = sim
                best_b = b
        if best_b is not None:
            pairs.append((a, best_b))
            seen_pairs.add(tuple(sorted((a["id"], best_b["id"]))))
            used_anchors.add(a["id"])
            used_anchors.add(best_b["id"])

    # Cohesive 3-hotel trio anchored on the top matchup's hotel A + its top 2 comparable rivals in dest_hotels
    trio: list[dict[str, Any]] = []
    if len(dest_hotels) >= 3 and pairs:
        lead = pairs[0][0]
        rivals = sorted(
            [h for h in dest_hotels if h["id"] != lead["id"]],
            key=lambda r: (-_rival_similarity_score(lead, r, odds_map), r["name"]),
        )
        trio = [lead, rivals[0], rivals[1]]
    else:
        trio = dest_hotels[:3]
    return pairs, trio


LANG_NAMES = {"fr": "French", "de": "German", "es": "Spanish", "it": "Italian", "nl": "Dutch", "pt": "Portuguese", "ja": "Japanese",
              "zh": "Chinese", "ko": "Korean", "ru": "Russian", "ar": "Arabic", "he": "Hebrew", "pl": "Polish", "sv": "Swedish",
              "da": "Danish", "no": "Norwegian", "fi": "Finnish", "tr": "Turkish", "th": "Thai", "id": "Indonesian", "cs": "Czech",
              "el": "Greek", "hu": "Hungarian", "ro": "Romanian", "uk": "Ukrainian", "vi": "Vietnamese"}


def combined_guest_score(gs: dict[str, Any] | None, ta: dict[str, Any] | None,
                         gg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """One guest score from every real guest rating we hold, weighted by how many reviews each is based on.

    Booking-platform guest ratings are out of 10, Tripadvisor and Google ratings out of 5; both become a % of the maximum
    (9.2/10 -> 92, 4.5/5 -> 90) and are averaged by review count, so 4,000 Tripadvisor reviews count for more than
    40 booking reviews. Each part keeps its own source, rating and review count for display.
    """
    parts = []
    if gs and gs.get("normalized_100") is not None:
        parts.append({
            "name": "Verified booking guests", "rating": float(gs["rating"]), "scale": float(gs.get("scale") or 10.0),
            "normalized100": int(gs["normalized_100"]), "reviewCount": gs.get("review_count"),
            "checked": gs.get("verified_at"),
        })
    if ta and ta.get("rating") is not None and (ta.get("reviewCount") or 0) >= MIN_GUEST_REVIEWS:
        parts.append({
            "name": "Tripadvisor", "rating": float(ta["rating"]), "scale": 5.0,
            "normalized100": int(round(float(ta["rating"]) * 20)), "reviewCount": int(ta["reviewCount"]),
            "checked": ta.get("fetched"), "url": ta.get("url"),
        })
    if gg and gg.get("rating") is not None and (gg.get("reviewCount") or 0) >= MIN_GUEST_REVIEWS:
        parts.append({
            "name": "Google", "rating": float(gg["rating"]), "scale": 5.0,
            "normalized100": int(round(float(gg["rating"]) * 20)), "reviewCount": int(gg["reviewCount"]),
            "checked": gg.get("fetched"),
        })
    if not parts:
        return None
    counts = [int(p["reviewCount"] or 0) for p in parts]
    if sum(counts) > 0:
        n100 = int(round(sum(p["normalized100"] * c for p, c in zip(parts, counts)) / sum(counts)))
    else:
        n100 = int(round(sum(p["normalized100"] for p in parts) / len(parts)))
    total = sum(counts) or None
    return {
        "licensed": {
            "sourceName": "Guest Reviews" if len(parts) > 1 else parts[0]["name"],
            "rating": round(n100 / 10, 1),
            "scale": 10.0,
            "normalized100": n100,
            "reviewCount": total,
            "attribution": " + ".join(p["name"] for p in parts),
            "verifiedAt": max((str(p.get("checked") or "") for p in parts), default=None),
            "sources": parts,
        }
    }


def nice_date(iso: str) -> str:
    """2026-11-25 -> 25 November 2026 (anything else is returned unchanged)."""
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d")
        return f"{d.day} {d.strftime('%B %Y')}"
    except Exception:
        return str(iso or "")


def voices_section_html(h: dict[str, Any]) -> str:
    """Real guest comments (dated, sourced, unedited) and links to traveller discussions and reviews. No scores made up."""
    # read the data files directly too, so a publish-only run picks up newly added links and ratings
    quotes = h.get("guestQuotes") or GUEST_QUOTES.get(h.get("id", "")) or {}
    qs = quotes.get("quotes") or []
    mentions = COMMUNITY.get(h.get("id", "")) or h.get("communityMentions") or []
    ta = h.get("tripadvisor") or TRIPADVISOR.get(h.get("id", "")) or {}
    if not qs and not mentions and not ta.get("rating"):
        return ""
    ta_html = ""
    if ta.get("rating") is not None:
        bits = [f'<strong>Tripadvisor: {float(ta["rating"]):.1f} / 5</strong>'
                + (f' from {int(ta["reviewCount"]):,} reviews' if ta.get("reviewCount") else "")]
        if ta.get("ranking"):
            bits.append(esc(ta["ranking"]))
        for a in ta.get("awards") or []:
            bits.append(esc(f'{a.get("name")} {a.get("year") or ""}'.strip()))
        link = f' <a href="{esc(ta["url"])}" target="_blank" rel="noopener noreferrer">Read the reviews on Tripadvisor &#8599;</a>' if ta.get("url") else ""
        ta_html = (f'<div class="channel-row" style="display:block;">{"<br>".join(bits)}{link}'
                   f'<small class="detail-panel-sub" style="display:block;margin-top:6px;">Source: Tripadvisor · last updated {esc(nice_date(ta.get("fetched", "")))}</small></div>')
    q_html = ""
    for q in qs:
        parts = []
        if q.get("headline"):
            parts.append(f'<strong>{esc(q["headline"])}</strong>')
        if q.get("liked"):
            parts.append(f'<span><b>Liked:</b> {esc(q["liked"])}</span>')
        if q.get("disliked"):
            parts.append(f'<span><b>Disliked:</b> {esc(q["disliked"])}</span>')
        meta = " · ".join(x for x in (
            f"{q['score']:g}/10" if isinstance(q.get("score"), (int, float)) else "",
            q.get("travellerType", "").title(),
            nice_date(q.get("date", "")),
            f"{'Verified booking guest' if q.get('source') in ('LiteAPI guest', 'Verified guest') else q.get('source', '')} review",
            f"written in {LANG_NAMES.get(q.get('language', ''), q.get('language', '').upper())}" if q.get("language") not in ("", "en", None) else "",
        ) if x)
        q_html += (f'<div class="channel-row" style="display:block;"><div style="display:flex;flex-direction:column;gap:4px;">'
                   f'{"".join(parts)}</div><small class="detail-panel-sub" style="display:block;margin-top:6px;">{esc(meta)}</small></div>')
    m_html = ""
    for m in mentions:
        quote = f'<span>&ldquo;{esc(m["quote"])}&rdquo;</span>' if m.get("quote") else ""
        meta = " · ".join(x for x in (m.get("site", ""), m.get("author", ""), m.get("date", "")) if x)
        m_html += (f'<div class="channel-row" style="display:block;"><a href="{esc(m["url"])}" target="_blank" rel="noopener noreferrer">'
                   f'<strong>{esc(m.get("title") or m["url"])}</strong> &#8599;</a>{"<br>" + quote if quote else ""}'
                   f'<small class="detail-panel-sub" style="display:block;margin-top:6px;">{esc(meta)}</small></div>')
    left = (f'''<div class="detail-panel"><div class="detail-panel-head"><h3>Recent Guest Comments</h3><span class="tag">{len(qs)} real review{"" if len(qs) == 1 else "s"}</span></div>
      <p class="detail-panel-sub">The most recent reviews written by guests who stayed here, shown word for word, whether positive or negative. Each one shows the guest's score, their type of trip, the date and the source of the review. Last updated {esc(nice_date(quotes.get("fetched", "")))}.</p>
      <div class="channel-breakdown-list" style="margin-top:12px;">{q_html}</div></div>''') if qs else ""
    right = (f'''<div class="detail-panel"><div class="detail-panel-head"><h3>Travellers &amp; Reviewers Elsewhere</h3><span class="tag">{len(mentions) + (1 if ta_html else 0)} linked</span></div>
      <p class="detail-panel-sub">This hotel's rating on Tripadvisor, plus forum discussions and independent reviews by travel writers. Each link opens the original page.</p>
      <div class="channel-breakdown-list" style="margin-top:12px;">{ta_html}{m_html}</div></div>''') if (mentions or ta_html) else ""
    return f'''<section class="detail-section"><h2 class="section-title" style="margin-bottom:14px;">What Guests &amp; Travellers Say</h2>
      <div class="detail-two-col">{left}{right}</div></section>'''


def render_seo_page(
    h: dict[str, Any],
    o: dict[str, Any],
    related: list[dict[str, Any]],
    total_props: int = 500,
    price_medians: dict[str, dict[str, tuple[int, int]]] | None = None,
    rivals: list[dict[str, Any]] | None = None,
) -> str:
    slug = h["id"]
    canonical = f"{SITE_URL}/stayodds/{slug}/"
    vg = o["vg"]
    tag_class = {
        "amber": "tag-caution",
        "accent": "tag-accent",
        "teal": "tag-teal",
    }.get(o["statusTone"], "tag-slate")

    odds_str = f"{o['greatStayOdds']}%" if o["greatStayOdds"] is not None else "Live"
    title_text = f"{h['name']} — StayOdds Score ({odds_str}) & Honest Review | Worth It?"
    meta_desc = (
        f"Is {h['name']} in {h['location']}, {h['country']} worth it? Compare verified guest ratings, "
        f"official awards, key hotel facts, and {'first-hand stay scores' if o['firstHand'] else 'hype vs. reality opinion gap'} on StayOdds."
    )
    raw_thumb = h.get("thumbnail") or ""
    if raw_thumb.startswith("assets/"):
        img_src = f"../../{raw_thumb}?v=169"
        img_abs = f"{SITE_URL}/{raw_thumb}"
    elif raw_thumb.startswith("http"):
        img_src = raw_thumb
        img_abs = raw_thumb
    else:
        img_src = "../../assets/placeholders/default-stayodds.webp?v=169"
        img_abs = f"{SITE_URL}/assets/placeholders/default-stayodds.webp"

    # Build JSON-LD structured data (Hotel + Review if First-Hand Verified)
    ld: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Hotel",
        "name": h["name"],
        "url": canonical,
        "image": img_abs,
        "address": {
            "@type": "PostalAddress",
            "addressLocality": h["location"],
            "addressCountry": h["country"],
        },
    }
    if h.get("lat") and h.get("lng"):
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": h["lat"], "longitude": h["lng"]}
    if vg and vg.get("rating"):
        ld["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": vg["rating"],
            "bestRating": vg.get("scale", 10),
            "reviewCount": vg.get("reviewCount") or 1,
        }
    if o["firstHand"] and o.get("personalScore25") is not None:
        max_pts = o.get("personalScoreMax") or 25
        ld["review"] = {
            "@type": "Review",
            "author": {"@type": "Organization", "name": "The Uncharted Itinerary"},
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": o["personalScore25"],
                "bestRating": max_pts,
                "worstRating": max(1, max_pts // 5),
            },
            "reviewBody": h.get("whereWeDiffer") or h.get("verdict") or "",
        }

    # Build Middle Key Facts tiles (strictly non-blank verified fields only!)
    kf = h.get("keyFacts") or {}
    fact_tiles = []
    if kf.get("poolHeating"):
        fact_tiles.append(("Pool & Heating", kf["poolHeating"]))
    if kf.get("beachOrReef"):
        fact_tiles.append(("Beach & Reef", kf["beachOrReef"]))
    if kf.get("renovationYear"):
        fact_tiles.append(("Opened / Renovated", str(kf["renovationYear"])))
    if kf.get("transferLogistics"):
        fact_tiles.append(("Transfer Logistics", kf["transferLogistics"]))
    if h.get("priceRange"):
        fact_tiles.append(("Price Tier", h["priceRange"]))
    if h.get("brand"):
        fact_tiles.append(("Brand / Collection", h["brand"]))

    facts_html = "".join(
        f'<div class="key-fact-tile"><small>{esc(lbl)}</small><strong>{esc(val)}</strong></div>'
        for lbl, val in fact_tiles
    )
    red_flags_html = "".join(
        f'<span class="tag tag-caution">{ICO_ALERT} {esc(rf)}</span>' for rf in (h.get("redFlags") or [])
    )

    # First-hand 5-axis bars matching exact YouTube video categories (/25 total)
    scores_html = ""
    if o["firstHand"] and h.get("scores"):
        s = h["scores"]
        for lbl, key in [
            ("Value", "value"),
            ("Room Quality", "rooms"),
            ("Vibe / Layout", "grounds"),
            ("Food", "food"),
            ("Service", "service"),
        ]:
            raw = s.get(key)
            if raw is None:
                continue
            val = float(raw)
            pct = int(round((val / 5.0) * 100))
            scores_html += (
                f'<div class="detail-bar-row"><div class="detail-bar-top"><span>{lbl}</span>'
                f'<strong>{fmt_score_num(val)} / 5</strong></div><div class="detail-bar-track">'
                f'<div class="detail-bar-fill" style="width:{pct}%"></div></div></div>'
            )

    review_href = ""
    if h.get("videoId"):
        if h.get("coverageType") == "Short Tour":
            review_href = f"https://www.youtube.com/shorts/{urllib.parse.quote(h['videoId'])}"
        else:
            review_href = f"https://www.youtube.com/watch?v={urllib.parse.quote(h['videoId'])}"

    scored_ed = o.get("scoredEditorial") or [e for e in o["editorial"] if e.get("normalized100") is not None and not is_score_unverified(e)]
    unverified_ed = o.get("unverifiedEditorial") or [e for e in o["editorial"] if is_score_unverified(e)]
    pc = scored_ed[0] if scored_ed else None
    left_label = (
        "My First-Hand Stay"
        if o["firstHand"]
        else (
            pc["sourceName"]
            if (len(scored_ed) == 1 and pc)
            else (
                unverified_ed[0]["sourceName"]
                if (not scored_ed and len(unverified_ed) == 1)
                else "Published Critics"
            )
        )
    )
    if o["firstHand"] and o.get("personalScoreLabel"):
        left_display = f"{o['personalScoreLabel']} ({o['ours100']}/100)"
    elif o["firstHand"]:
        left_display = f"{fmt_score_num(h['overall'])} / 5 ({o['ours100']}/100)"
    elif len(scored_ed) == 1 and pc:
        raw_sc = pc.get("rawScore") or f"{o['critic100']}/100"
        left_display = f"{raw_sc} ({o['critic100']}/100)"
    elif o["critic100"] is not None:
        left_display = f"{o['critic100']} / 100 ({len(scored_ed)} critics)"
    elif unverified_ed:
        left_display = "Score/points awarded — unable to verify exact figure"
    else:
        left_display = "No numeric critic review yet"

    right_display = (
        (f"{o['guest100']} / 100 ({int(vg['reviewCount']):,} reviews)" if vg.get("reviewCount") else f"{o['guest100']} / 100")
        if vg and vg.get("rating")
        else "Checking Google Reviews…"
    )
    guest_parts = (vg or {}).get("sources") or []
    guest_breakdown_html = (
        '<small class="detail-panel-sub" style="display:block;margin-top:6px;">'
        + " · ".join(
            f"{esc(p['name'])} {p['rating']:g}/{int(p['scale'])}"
            + (f" ({int(p['reviewCount']):,})" if p.get("reviewCount") else "")
            for p in guest_parts
        )
        + (" — combined by number of reviews" if len(guest_parts) > 1 else "")
        + "</small>"
    ) if guest_parts else ""
    gr = GUEST_RANKS.get(h.get("id", "")) or {}
    rank_html = ""
    if gr and vg:
        def _ord(n: int) -> str:
            return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"

        def _scale(r: dict[str, Any], title: str) -> str:
            pos = 0 if r["of"] <= 1 else round((r["rank"] - 1) / (r["of"] - 1) * 100)
            return (
                f'<div style="margin-top:12px;font-size:13.5px;font-weight:600">{title}</div>'
                f'<div style="position:relative;height:8px;border-radius:99px;background:rgba(100,110,130,.18);margin:8px 0 4px" aria-hidden="true">'
                f'<div style="position:absolute;top:50%;left:{pos}%;width:14px;height:14px;margin:-7px 0 0 -7px;border-radius:50%;'
                f'background:#ff5d22;box-shadow:0 0 0 3px #fff"></div></div>'
                f'<div style="display:flex;justify-content:space-between;gap:8px;font-size:11px;opacity:.7"><span>Top: {esc(r["top"])} ({r["topScore"]})</span>'
                f'<span>Lowest: {r["low"]}</span></div>'
            )

        a = gr.get("area")
        if a:
            rank_html += _scale(
                a, f'Guests rank it <span style="color:#ff5d22">{_ord(a["rank"])} of {a["of"]}</span> {esc(a["group"])} hotels on StayOdds')
        pr = gr.get("price")
        if pr:
            rank_html += _scale(
                pr, f'Against hotels at a similar price ({esc(pr["group"])} a night{(" in " + esc(pr["where"])) if pr.get("where") else ", worldwide"}): <span style="color:#ff5d22">{_ord(pr["rank"])} of {pr["of"]}</span>')
        rank_html += ('<div style="font-size:11px;opacity:.7;margin-top:6px">Ranked by guest score (20+ reviews). Price level from our latest nightly price check. '
                                 '<a href="/insights/" style="color:inherit">More guest insights</a></div>')
        alts = ALTERNATIVES.get(h.get("id", "")) or []
        near = NEARBY.get(h.get("id", "")) or []
        my_g = (vg or {}).get("normalized100")
        if near and my_g is not None:
            rows = sorted([{"id": h["id"], "name": h["name"], "g": int(my_g), "rc": int((vg or {}).get("reviewCount") or 0), "km": 0, "gbp": int((h.get("priceSnapshot") or {}).get("nightlyGbp") or 0) or None, "me": True}]
                          + near, key=lambda r: (-r["g"], -r["rc"]))
            lo = min(r["g"] for r in rows) - 2
            span = max(1, 100 - lo)

            def _row(r: dict[str, Any]) -> str:
                w = max(4, round((r["g"] - lo) / span * 100))
                name = (f'<b>{esc(r["name"])}</b> <span style="font-size:11px;color:#C2410C">(this hotel)</span>' if r.get("me")
                        else f'<a href="../../stayodds/{esc(r["id"])}/" style="font-weight:600">{esc(r["name"])}</a>')
                meta = (f'{r["rc"]:,} reviews' + (f' · {r["km"]:g} km away' if not r.get("me") else "")
                        + (f' · from £{r["gbp"]:,}' if r.get("gbp") else ""))
                return (f'<div class="so2-near-row{" is-me" if r.get("me") else ""}">'
                        f'<div class="so2-near-top"><span>{name}</span><b>{r["g"]}</b></div>'
                        f'<div class="so2-near-bar"><i style="width:{w}%"></i></div>'
                        f'<div class="so2-near-meta">{meta}</div></div>')

            rank_html += ('<div class="so2-near"><div class="so2-near-head">How guests compare nearby</div>'
                          + "".join(_row(r) for r in rows)
                          + f'<div style="font-size:11px;opacity:.7;margin-top:6px">Guest scores out of 100 for the closest StayOdds hotels (within 15 km). '
                          + (f'<a href="../../compare/?a={esc(h["id"])}&amp;b={esc(rows[0]["id"] if not rows[0].get("me") else rows[1]["id"])}" style="color:inherit">Compare side by side &rarr;</a>' if len(rows) > 1 else '')
                          + '</div></div>')
        elif alts:
            rank_html += (
                '<div style="margin-top:14px;padding:12px 14px;border:1px solid rgba(100,110,130,.22);border-radius:12px">'
                '<div style="font-size:13.5px;font-weight:700;margin-bottom:6px">Guests rate these higher nearby'
                + (' (same price level or less)' if gr.get("price") else '') + '</div>'
                + "".join(
                    f'<div style="display:flex;justify-content:space-between;gap:10px;font-size:13px;padding:4px 0">'
                    f'<a href="../../stayodds/{esc(a["id"])}/" style="font-weight:600">{esc(a["name"])}</a>'
                    f'<span style="white-space:nowrap;opacity:.85"><b style="color:#ff5d22">{a["g"]}</b>/100 · {a["rc"]:,} reviews'
                    + (f' · {esc(a["band"])}' if a["band"] else '') + '</span></div>'
                    for a in alts
                )
                + f'<div style="font-size:11px;opacity:.7;margin-top:4px">Guest scores 2+ points higher than this hotel\'s {(vg or {}).get("normalized100", "")}, in the same area. '
                f'<a href="../../compare/?a={esc(h.get("id", ""))}&amp;b={esc(alts[0]["id"])}" style="color:inherit">Compare with {esc(alts[0]["name"])} &rarr;</a></div></div>'
            )
        elif gr.get("area", {}).get("rank") == 1:
            rank_html += (f'<div style="margin-top:12px;font-size:13px;font-weight:600">Guests\' top-rated hotel in '
                                     f'{esc(gr["area"]["group"])} on StayOdds.</div>')
    delta_badge = (
        f"{'+' if o['delta100'] > 0 else ''}{o['delta100']} pts"
        if o["delta100"] is not None
        else "—"
    )
    delta_tone = (
        "is-caution"
        if (o["delta100"] is not None and abs(o["delta100"]) > 12)
        else ("is-aligned" if o["delta100"] is not None else "")
    )

    hero_awards_html = "".join(
        f'<a class="tag tag-accent" href="{esc(a["sourceUrl"])}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">{ICO_TROPHY} {esc(a["label"])} ↗</a>'
        for a in o["awards"]
    )

    awards_html = "".join(
        f'<article class="channel-row"><div class="channel-row-head"><div>'
        f'<span class="tag tag-accent">{esc(a.get("awardBody") or "Official Award")}</span>'
        f'<h4><a href="{esc(a["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{ICO_TROPHY} {esc(a["label"])} ↗</a></h4>'
        f'</div><div class="channel-row-score"><strong>{esc(a.get("year") or "Official")}</strong>'
        f'<span>Official Honour</span></div></div></article>'
        for a in o["awards"]
    )
    editorial_parts = []
    for e in o["editorial"]:
        tk = f'<p class="channel-takeaway">{esc(e.get("takeaway"))}</p>' if e.get("takeaway") else ""
        if is_score_unverified(e):
            tag_html = '<span class="tag tag-caution">Score Awarded — Unverified</span>'
            sc_html = (
                '<strong style="font-size:12px;color:#b45309;">Score/points awarded — unable to verify exact figure</strong>'
                '<span>Excluded from numeric math</span>'
            )
        elif e.get("normalized100") is not None:
            tag_html = '<span class="tag tag-teal">Verified Score</span>'
            sc_html = f'<strong>{esc(e.get("rawScore") or "")}</strong><span>{esc(e["normalized100"])}/100</span>'
        else:
            tag_html = '<span class="tag">Editorial</span>'
            sc_html = '<strong>Review</strong><span>Read Article ↗</span>'
        editorial_parts.append(
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'{tag_html}'
            f'<h4><a href="{esc(e["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{esc(e["sourceName"])} ↗</a></h4>'
            f'</div><div class="channel-row-score">{sc_html}</div></div>{tk}</article>'
        )
    editorial_html = "".join(editorial_parts)

    yt_html = ""
    if review_href:
        fh_score_lbl = (
            o["personalScoreLabel"]
            if (o["firstHand"] and o.get("personalScoreLabel"))
            else ("Short" if h.get("coverageType") == "Short Tour" else "Filmed Review")
        )
        yt_html += (
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'<span class="tag tag-accent">Founding Contributor</span>'
            f'<h4><a href="{esc(review_href)}" target="_blank" rel="noopener noreferrer" data-yt-id="{esc(h.get("videoId"))}" data-yt-short="{1 if h.get("coverageType") == "Short Tour" else 0}" data-yt-title="{esc(h.get("name"))} - The Uncharted Itinerary">{YT_GLYPH_INLINE} The Uncharted Itinerary — {esc(h.get("coverageType"))}</a></h4>'
            f'</div><div class="channel-row-score"><strong>{fh_score_lbl}</strong></div></div>'
            f'<p class="channel-takeaway">{esc(h.get("verdict") or "")}</p></article>'
        )
    for y in o["ytReviews"]:
        raw_tk = y.get("takeaway") or ""
        tk = f'<p class="channel-takeaway">{esc(raw_tk)}</p>' if raw_tk else ""
        if "unable to verify" in raw_tk.lower():
            yt_tag = '<span class="tag tag-caution">Score Awarded — Unverified</span>'
            yt_score_box = (
                '<div class="channel-row-score">'
                '<strong style="font-size:12px;color:#b45309;">Score/points awarded — unable to verify exact figure</strong>'
                '<span>Excluded from numeric math</span></div>'
            )
        elif "/100" in raw_tk and "verified" in raw_tk.lower():
            m_sc = re.search(r"(\d{1,3}/100)", raw_tk)
            sc_str = m_sc.group(1) if m_sc else "Verified"
            yt_tag = '<span class="tag tag-teal">Verified Video Score</span>'
            yt_score_box = f'<div class="channel-row-score"><strong>{esc(sc_str)}</strong><span>Included in Critic Math</span></div>'
        else:
            yt_tag = f'<span class="tag">{esc(y.get("sentiment") or "Review")}</span>'
            yt_score_box = ""
        yt_html += (
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'{yt_tag}'
            f'<h4><a href="{esc(y["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{esc(y["creatorName"])} ↗</a></h4>'
            f'</div>{yt_score_box}</div>{tk}</article>'
        )

    related_html = ""
    for r in related:
        ro = compute_stayodds_py(r)
        r_odds = f"{ro['greatStayOdds']}% StayOdds" if ro["greatStayOdds"] is not None else ro["tierLabel"]
        r_thumb = r.get("thumbnail") or ""
        r_img = f"../../{r_thumb}?v=169" if r_thumb.startswith("assets/") else (r_thumb if r_thumb.startswith("http") else "../../assets/placeholders/default-stayodds.webp?v=169")
        related_html += f"""
          <article class="related-card">
            <img src="{esc(r_img)}" alt="{esc(r['name'])}" loading="lazy" decoding="async" />
            <div class="related-card-body">
              <div class="meta-line">
                <span class="tag {'tag-accent' if ro['firstHand'] else 'tag-slate'}">{esc(r_odds)}</span>
                <span>{esc(ro['statusBadge'])}</span>
              </div>
              <h4>{esc(r['name'])}</h4>
              <p>{esc(r['location'])}, {esc(r['country'])}</p>
              <div class="related-card-actions">
                <a class="btn btn-primary" href="../{esc(r['id'])}/">Full Breakdown</a>
                <a class="btn btn-outline" href="../../compare/?a={esc(slug)}&amp;b={esc(r['id'])}">Compare VS</a>
              </div>
            </div>
          </article>"""

    google_place_id = h.get("googlePlaceId") or ""
    region_q = urllib.parse.quote(h["region"])
    ta_query = f"{h['name']} {h.get('location') or h.get('country') or ''}".strip()
    tripadvisor_url = f"https://www.tripadvisor.com/Search?q={urllib.parse.quote(ta_query)}&ssrc=h"

    # Live-rate coverage: hotels without a trusted LiteAPI match (or sold via the official site only)
    # never show a live/indicative price. Clicking "Check Live Rate" explains that and offers alternatives.
    official_site = h.get("officialSite") or {}
    live_btn_cls = "btn btn-outline date-rate-check-btn" + ("" if h.get("nuiteeHotelId") else " is-unavailable")
    primary_book_label = (
        f"Check Rates on {esc(official_site.get('partner'))}" if official_site else "Check Live Rates on Booking.com"
    ) + " &nearr;"
    primary_book_rel = "noopener noreferrer" if official_site else "sponsored noopener noreferrer"
    date_hint = (
        f"Official rates are on {esc(official_site.get('partner'))} &mdash; choose your dates there."
        if official_site
        else "Select trip dates to pass them straight into Booking.com."
    )
    live_unavailable_js = json.dumps(live_rate_unavailable_html(h)).replace("</", "<\\/")

    if o["critic100"] is not None:
        critic_kpi_val = f'{o["critic100"]}<span>/100</span>'
        critic_kpi_lbl = (
            pc["sourceName"]
            if (len(scored_ed) == 1 and pc)
            else f"Published Critics ({len(scored_ed)})"
        )
    elif unverified_ed:
        critic_kpi_val = '<span style="font-size:15px;">Unverified</span>'
        critic_kpi_lbl = f"{unverified_ed[0]['sourceName']} (Score Awarded)"
    elif len(o["editorial"]) > 0:
        cnt_ed = len(o["editorial"])
        critic_kpi_val = f'{cnt_ed}<span> {"Review" if cnt_ed == 1 else "Reviews"}</span>'
        critic_kpi_lbl = "Editorial (No Score)"
    else:
        critic_kpi_val = "—"
        critic_kpi_lbl = "Published Critics"

    unverified_transparency_html = ""
    if unverified_ed:
        uv_names = ", ".join(u["sourceName"] for u in unverified_ed)
        unverified_transparency_html = (
            f'<div style="margin-top:12px;padding:10px 12px;border-radius:10px;background:#fffbeb;border:1px solid #fde68a;font-size:12.5px;color:#92400e;">'
            f'<strong>Score Verification Transparency:</strong> {esc(uv_names)} awards a points/rating score in their linked review, '
            f'but the exact figure could not be verified from published text or captions — marked '
            f'<strong>&ldquo;Score/points awarded — unable to verify exact figure&rdquo;</strong> and excluded from numeric StayOdds calculations.'
            f'</div>'
        )

    eq_parts = []
    if o["weights"]["firstHand"] > 0 and o["ours100"] is not None:
        raw_fh = f"{o['personalScoreLabel'].replace(' ', '')} → " if o.get("personalScoreLabel") else ""
        eq_parts.append(f"{o['weights']['firstHand']}% My Stay ({raw_fh}{o['ours100']}%)")
    if o["weights"]["critics"] > 0 and o["critic100"] is not None:
        eq_parts.append(f"{o['weights']['critics']}% Published Critics ({o['critic100']}%)")
    if o["weights"]["guests"] > 0 and o["guest100"] is not None:
        g_raw = f"{vg['rating']}/{int(vg.get('scale', 10))} → " if vg and vg.get("rating") else ""
        eq_parts.append(f"{o['weights']['guests']}% Guest Reviews ({g_raw}{o['guest100']}%)")

    if eq_parts and o["greatStayOdds"] is not None:
        equation_text = " + ".join(eq_parts) + f" = {o['greatStayOdds']}% StayOdds"
        if o["guest100"] is None and google_place_id:
            equation_text += " (updating with live Google rating…)"
    else:
        equation_text = "Waiting for live Google guest rating — StayOdds blends whichever verified numeric scores exist."

    ps = h.get("propertyStatus") or {}
    ps_op = (ps.get("operatingStatus") or "").strip()
    ps_reno = (ps.get("renovationsExtensions") or "").strip()
    ps_nearby = (ps.get("nearbyConstruction") or "").strip()
    ps_src_url = (ps.get("sourceUrl") or "").strip()
    ps_src_note = (ps.get("sourceNote") or "").strip()
    ps_verified = (ps.get("verifiedAt") or "").strip()[:10]
    ps_has = bool(ps_op or ps_reno or ps_nearby)
    ps_lower = ps_op.lower()
    if "closed" in ps_lower:
        ps_box_cls, ps_tag_cls, ps_badge_lbl = "is-danger", "tag-danger", ps_op
    elif "rebrand" in ps_lower or "transition" in ps_lower or ps_nearby:
        ps_box_cls, ps_tag_cls, ps_badge_lbl = "is-warn", "tag-caution", ps_op or "Status Notice"
    elif ps_op == "Open":
        ps_box_cls, ps_tag_cls, ps_badge_lbl = "is-open", "tag-teal", "Open · Confirmed Works" if ps_reno else "Open"
    else:
        ps_box_cls, ps_tag_cls, ps_badge_lbl = "", "tag-slate", "No Confirmed Works Listed"

    if ps_has:
        ps_items = []
        if ps_op:
            ps_items.append(
                f'<div class="property-status-item"><small>Operating / Closure Status</small><p><strong>{esc(ps_op)}</strong></p></div>'
            )
        if ps_reno:
            ps_items.append(
                f'<div class="property-status-item"><small>Renovations &amp; Extensions</small><p>{esc(ps_reno)}</p></div>'
            )
        if ps_nearby:
            ps_items.append(
                f'<div class="property-status-item"><small>Nearby / Neighboring Construction</small><p>{esc(ps_nearby)}</p></div>'
            )
        else:
            ps_items.append(
                '<div class="property-status-item"><small>Nearby / Neighboring Construction</small><p>No confirmed nearby construction listed.</p></div>'
            )
        ps_src_parts = []
        if ps_src_note:
            ps_src_parts.append(f"<span><strong>Source:</strong> {esc(ps_src_note)}</span>")
        if ps_src_url:
            ps_src_parts.append(f'<a href="{esc(ps_src_url)}" target="_blank" rel="noopener noreferrer">View verified report &nearr;</a>')
        if ps_verified:
            ps_src_parts.append(f"<span>Checked: {esc(ps_verified)}</span>")
        ps_source_html = f'<div class="property-status-source">{" &bull; ".join(ps_src_parts)}</div>' if ps_src_parts else ""
        ps_body_html = f'<div class="property-status-grid">{"".join(ps_items)}</div>{ps_source_html}'
    else:
        ps_body_html = '<p class="property-status-neutral">No confirmed renovations, closures, or nearby works listed. StayOdds never guesses or invents renovation dates or construction notices.</p>'

    property_status_html = f"""
          <div class="property-status-box {ps_box_cls}" id="propertyStatusBlock">
            <div class="property-status-head">
              <span class="property-status-title">Property Status &amp; Works</span>
              <span class="tag {ps_tag_cls}">{esc(ps_badge_lbl)}</span>
            </div>
            {ps_body_html}
          </div>"""

    # Trip Planning & Price-to-Score Context Strip (strictly zero invented data)
    best_months_lbl, best_months_reason = get_best_months_py(h)
    verified_room_tip = get_verified_room_tip_py(h)
    trip_tiles: list[str] = []

    snap = h.get("priceSnapshot") or {}
    gbp_val = snap.get("nightlyGbp")
    if isinstance(gbp_val, (int, float)) and gbp_val > 0:
        med_info = None
        med_scope = ""
        if price_medians:
            if h.get("country") in price_medians.get("country", {}):
                med_info = price_medians["country"][h["country"]]
                med_scope = h["country"]
            elif h.get("region") in price_medians.get("region", {}):
                med_info = price_medians["region"][h["region"]]
                med_scope = h["region"]
        if med_info:
            med_gbp, med_cnt = med_info
            pct_diff = int(round(((float(gbp_val) - med_gbp) / med_gbp) * 100))
            if abs(pct_diff) <= 5:
                rel_note = f"Right around the {med_scope} luxury median (£{med_gbp:,}/nt across {med_cnt} priced stays)."
            elif pct_diff < 0:
                rel_note = f"{abs(pct_diff)}% below the {med_scope} luxury median (£{med_gbp:,}/nt across {med_cnt} priced stays)."
            else:
                rel_note = f"{pct_diff}% above the {med_scope} luxury median (£{med_gbp:,}/nt across {med_cnt} priced stays)."
        else:
            rel_note = f"Indicative nightly benchmark (checked {snap.get('checkedAt') or 'recently'}) — click Booking.com for exact dates."
        trip_tiles.append(
            f'<div class="detail-trip-tile">'
            f'<span class="detail-trip-kicker">Indicative Nightly Rate</span>'
            f'<strong class="detail-trip-val">{esc(snap.get("label") or f"From £{int(round(gbp_val)):,}/nt")}</strong>'
            f'<span class="detail-trip-sub">{esc(rel_note)}</span>'
            f'</div>'
        )
    elif h.get("priceRange"):
        trip_tiles.append(
            f'<div class="detail-trip-tile">'
            f'<span class="detail-trip-kicker">Price Tier</span>'
            f'<strong class="detail-trip-val">{esc(h["priceRange"])}</strong>'
            f'<span class="detail-trip-sub">Select dates above to check live partner rates on Booking.com.</span>'
            f'</div>'
        )

    trip_tiles.append(
        f'<div class="detail-trip-tile">'
        f'<span class="detail-trip-kicker">☀ Best Dry Months</span>'
        f'<strong class="detail-trip-val">{esc(best_months_lbl)}</strong>'
        f'<span class="detail-trip-sub">{esc(best_months_reason)}</span>'
        f'</div>'
    )

    if ps_has:
        ps_short_sub = ps_reno or ps_nearby or "Confirmed operating status — full details in Property Status below."
        if len(ps_short_sub) > 130:
            ps_short_sub = ps_short_sub[:127].rsplit(" ", 1)[0] + "…"
        trip_tiles.append(
            f'<div class="detail-trip-tile {"is-alert" if ps_box_cls in ("is-danger", "is-warn") else ""}">'
            f'<span class="detail-trip-kicker">Property Status &amp; Works</span>'
            f'<strong class="detail-trip-val">{esc(ps_badge_lbl)}</strong>'
            f'<span class="detail-trip-sub">{esc(ps_short_sub)}</span>'
            f'</div>'
        )
    else:
        trip_tiles.append(
            '<div class="detail-trip-tile">'
            '<span class="detail-trip-kicker">Property Status &amp; Works</span>'
            '<strong class="detail-trip-val">No Confirmed Works Listed</strong>'
            '<span class="detail-trip-sub">No active closures, renovations, or nearby works flagged.</span>'
            '</div>'
        )

    if h.get("dining"):
        _d = h["dining"]
        trip_tiles.append(
            '<div class="detail-trip-tile">'
            '<span class="detail-trip-kicker">Dine at the hotel</span>'
            f'<strong class="detail-trip-val">{esc(_d[0]["name"])}: {esc(_d[0]["distinction"])}</strong>'
            '<span class="detail-trip-sub">' + " · ".join(f'<a href="{esc(r["url"])}" target="_blank" rel="noopener noreferrer">{esc(r["name"])}</a> ({esc(r["distinction"])})' for r in _d)
            + ('. Source: MICHELIN Guide, via isthewaterfree.com.' if 'isthewaterfree' in _d[0].get("url", "") else '. Source: MICHELIN Guide.') + '</span></div>'
        )

    # Drinking water: isthewaterfree.com's checked policy first, else what guests say in our reviews feed
    _iw = h.get("itwf") or {}
    _w = h.get("water") or {}
    if _iw.get("status"):
        _st = _iw["status"]
        _bad = bool(re.search(r"charg|rationed|paid|not free|cost", _st + " " + (_iw.get("summary") or ""), re.I))
        _extra = " · ".join(f"{k}: {v}" for k, v in (("Pool", _iw.get("pool")), ("Gym", _iw.get("gym"))) if v and "not checked" not in v.lower())
        trip_tiles.append(
            f'<div class="detail-trip-tile {"is-alert" if _bad else ""}">'
            f'<span class="detail-trip-kicker">Drinking water</span>'
            f'<strong class="detail-trip-val">{esc(_st)}{(" · " + esc(_iw["label"])) if _iw.get("label") else ""}</strong>'
            f'<span class="detail-trip-sub">{esc(_iw.get("summary") or "")}{(" " + esc(_extra) + ".") if _extra else ""} '
            f'Source: <a href="{esc(_iw["url"])}" target="_blank" rel="noopener">isthewaterfree.com</a>.</span>'
            f'</div>'
        )
    elif _w.get("reports"):
        _free, _paid = int(_w.get("free") or 0), int(_w.get("paid") or 0)
        if _paid and not _free:
            _wv, _wcls = "Guests say water isn't free", "is-alert"
        elif _free and not _paid:
            _wv, _wcls = "Guests report free water", ""
        else:
            _wv, _wcls = "Mixed reports on water", ""
        _rep = _w["reports"][0]
        _ym = _rep.get("date", "")[:7]
        _alt = ""
        if _paid > _free:
            for _r in (rivals or []):
                _rw = _r.get("water") or {}
                if int(_rw.get("free") or 0) > int(_rw.get("paid") or 0):
                    _alt = f' Guests report free water at <a href="../{esc(_r["id"])}/">{esc(_r["name"])}</a>.'
                    break
        _n = _free + _paid
        trip_tiles.append(
            f'<div class="detail-trip-tile {_wcls}">'
            f'<span class="detail-trip-kicker">Drinking water</span>'
            f'<strong class="detail-trip-val">{_wv}</strong>'
            f'<span class="detail-trip-sub">{_n} guest report{"s" if _n != 1 else ""} · latest {esc(_ym)}: '
            f'&ldquo;{esc(_rep.get("text", ""))}&rdquo; ({esc(_rep.get("source", ""))}).{_alt}</span>'
            f'</div>'
        )

    if verified_room_tip:
        trip_tiles.append(
            f'<div class="detail-trip-tile is-tip">'
            f'<span class="detail-trip-kicker">{ICO_BED} {esc(verified_room_tip["label"])}</span>'
            f'<strong class="detail-trip-val">{esc(verified_room_tip["text"])}</strong>'
            f'</div>'
        )

    trip_context_html = f'<div class="detail-trip-context-strip">{"".join(trip_tiles)}</div>'

    # Plain-English Quick Summary placed RIGHT AT THE TOP (before KPIs & detailed boxes)
    price_summary_str = (snap.get("label") if isinstance(snap, dict) else "") or h.get("priceRange") or ""
    awards_summary_str = " • ".join(a["label"] for a in o["awards"][:2]) if o["awards"] else ""
    if o["scoreTrack"] == "verified" and o["greatStayOdds"] is not None:
        my_bit = f" ({o['personalScoreLabel']} from our filmed stay)" if o.get("personalScoreLabel") else " (filmed on The Uncharted Itinerary)"
        score_summary_line = f"<strong>{o['greatStayOdds']}% StayOdds</strong> — Uncharted Verified{esc(my_bit)}"
        if o.get("founderVsMarketDelta") is not None:
            fd = o["founderVsMarketDelta"]
            score_summary_line += f" • The Uncharted Itinerary is {'+' if fd > 0 else ''}{fd} pts vs. wider consensus"
    elif o["greatStayOdds"] is not None:
        tone_word = "Standout" if o["greatStayOdds"] >= 92 else ("Strong" if o["greatStayOdds"] >= 86 else ("Solid" if o["greatStayOdds"] >= 78 else "Mixed"))
        score_summary_line = f"<strong>{tone_word} {o['greatStayOdds']}% StayOdds</strong> — {esc(o['formula'])}"
    else:
        score_summary_line = f"<strong>Live Google Check</strong> — {esc(o['formula'])}"
    if awards_summary_str:
        score_summary_line += f" • <strong>{esc(awards_summary_str)}</strong>"

    standout_summary = (h.get("standout") or h.get("verdict") or "").strip()
    if len(standout_summary) > 195:
        standout_summary = standout_summary[:192].rsplit(" ", 1)[0] + "…"
    watchout_summary = (h.get("watchOut") or "").strip()
    if len(watchout_summary) > 185:
        watchout_summary = watchout_summary[:182].rsplit(" ", 1)[0] + "…"

    weather_reason_lc = best_months_reason[:1].lower() + best_months_reason[1:] if best_months_reason else ""
    quick_bullets: list[str] = [
        f'<li class="qs-row"><span class="qs-label">Consensus:</span> <span id="glanceScoreBasis">{score_summary_line}</span></li>',
    ]
    if standout_summary:
        quick_bullets.append(
            f'<li class="qs-row is-pro"><span class="qs-label">Why Guests Love It:</span> {esc(standout_summary)}</li>'
        )
    quick_bullets.append(
        f'<li class="qs-row"><span class="qs-label">Best Weather:</span> <strong>{esc(best_months_lbl)}</strong> — {esc(weather_reason_lc)}{f" • Indicative rate: <strong>{esc(price_summary_str)}</strong>" if price_summary_str else ""}.</li>'
    )
    if watchout_summary:
        quick_bullets.append(
            f'<li class="qs-row is-con"><span class="qs-label">Heads-Up:</span> {esc(watchout_summary)}</li>'
        )
    room_summary_html = (
        f'<div class="qs-room-callout">'
        f'<span class="qs-room-kicker">{ICO_BED} {esc(verified_room_tip["label"])}</span>'
        f'<p>{esc(verified_room_tip["text"])}</p>'
        f'</div>'
        if verified_room_tip
        else ""
    )

    top_quick_summary_html = f"""
          <div class="top-quick-summary {'is-uncharted' if o['scoreTrack'] == 'verified' else ''}" aria-label="Quick hotel summary">
            <div class="top-quick-summary-head">
              <span class="top-quick-summary-eyebrow">{ICO_SPARK} Quick Summary &bull; The Bottom Line</span>
              <span class="top-quick-summary-jumps">
                <a href="#opinion-gap">Score Gap &darr;</a>
                <a href="#key-facts">Specs &amp; Facts &darr;</a>
                <a href="#score-sources">Sources &darr;</a>
              </span>
            </div>
            <ul class="top-quick-summary-list">
              {''.join(quick_bullets)}
            </ul>
            {room_summary_html}
          </div>"""

    # Pre-loaded Head-to-Head Rival Matchups (same country / region peers)
    rival_list = rivals if rivals is not None else related
    rival_cards: list[str] = []
    for rv in (rival_list or [])[:3]:
        rvo = compute_stayodds_py(rv)
        rv_odds = f"{rvo['greatStayOdds']}%" if rvo["greatStayOdds"] is not None else rvo["tierLabel"]
        rv_price = (rv.get("priceSnapshot") or {}).get("label") or rv.get("priceRange") or ""
        rv_meta = f"{rv['name']}: {rv_odds}" + (f" · {rv_price}" if rv_price else "")
        rival_cards.append(
            f'<a class="rival-matchup-card" href="../../compare/?a={esc(slug)}&amp;b={esc(rv["id"])}">'
            f'<div class="rival-matchup-vs">{esc(h["name"])} <span style="color:var(--accent);">vs</span> {esc(rv["name"])}</div>'
            f'<div class="rival-matchup-meta"><span>{esc(rv_meta)}</span><span class="rival-matchup-cta">Compare &rarr;</span></div>'
            f'</a>'
        )
    three_hotel_link = ""
    if len(rival_list or []) >= 2:
        three_hotel_link = (
            f'<a class="btn btn-outline" style="font-size:12.5px;padding:7px 12px;" '
            f'href="../../compare/?a={esc(slug)}&amp;b={esc(rival_list[0]["id"])}&amp;c={esc(rival_list[1]["id"])}">'
            f'Compare All 3 Side-by-Side &rarr;</a>'
        )
    rival_matchups_html = (
        f'<div class="rival-matchups-box">'
        f'<div class="rival-matchups-head"><h3>Pre-Loaded Head-to-Head Matchups</h3>{three_hotel_link}</div>'
        f'<div class="rival-matchups-grid">{"".join(rival_cards)}</div>'
        f'</div>'
        if rival_cards
        else ""
    )

    share_card_payload = {
        "hotel": {
            "id": h["id"],
            "name": h["name"],
            "location": h["location"],
            "country": h["country"],
            "brand": h.get("brand", ""),
            "priceRange": h.get("priceRange", ""),
            "standout": h.get("standout", ""),
            "watchOut": h.get("watchOut", ""),
            "keyFacts": h.get("keyFacts") or {},
            "thumbnail": h.get("thumbnail", ""),
        "cardPhoto": f"assets/card-photos/{h['id']}.webp" if (ROOT / "assets" / "card-photos" / f"{h['id']}.webp").exists() else "",
        "videoId": h.get("videoId", ""),
        "coverageType": h.get("coverageType", ""),
            "propertyStatus": h.get("propertyStatus") or None,
        },
        "odds": {
            "greatStayOdds": o["greatStayOdds"],
            "statusBadge": o["statusBadge"],
            "tierLabel": o["tierLabel"],
            "firstHand": o["firstHand"],
            "visited": o["visited"],
            "personalScoreLabel": o.get("personalScoreLabel"),
            "critic100": o["critic100"],
            "scoredEditorial": [
                {"sourceName": e["sourceName"], "rawScore": e.get("rawScore", ""), "normalized100": e["normalized100"]}
                for e in scored_ed
            ],
            "unverifiedEditorial": [
                {"sourceName": e["sourceName"], "rawScore": e.get("rawScore", "")}
                for e in (o.get("unverifiedEditorial") or [])
            ],
            "editorialCount": len(o.get("editorial") or []),
            "youtubeCount": len(o.get("ytReviews") or []),
            "verifiedGuest": {"rating": vg["rating"], "scale": int(vg.get("scale", 10))} if (vg and vg.get("rating")) else None,
            "officialAwards": [{"label": a["label"]} for a in o["awards"]],
            "opinionGap": {
                "title": "Uncharted Stay vs. Consensus" if o["firstHand"] else "Critics & Awards vs. Real Guest Score",
                "headline": o["gapHeadline"],
                "deltaLabel": delta_badge,
            },
        },
    }


    # ---------- Redesign (Nov 2026): score story first ----------
    so_odds = o["greatStayOdds"]
    so_left, so_right, so_d = o.get("left100"), o.get("right100"), o.get("delta100")
    so_alts = ALTERNATIVES.get(h.get("id", "")) or []
    so_area = (GUEST_RANKS.get(h.get("id", "")) or {}).get("area") or {}
    if so_odds is None:
        so_band = ""
    elif so_odds >= 90:
        so_band = "A great stay"
    elif so_odds >= 82:
        so_band = "A very good stay"
    elif so_odds >= 74:
        so_band = "A good stay, with caveats"
    else:
        so_band = "Mixed reviews"
    so_n_reviews = int((vg or {}).get("reviewCount") or 0)
    if o["firstHand"] and so_left is not None and so_right is not None:
        if abs(so_d) <= 5:
            so_verdict = f"{so_band}, and guests agree with us."
        elif so_d < 0:
            so_verdict = f"{so_band}, and guests like it even more than we did."
        else:
            so_verdict = f"{so_band}: we rated it higher than guests do."
        so_sub = f"Built from our filmed stay ({o['weights']['firstHand']}%)" + (
            (f" and {so_n_reviews:,} guest reviews" + (f" plus {len(scored_ed)} critic{'s' if len(scored_ed) != 1 else ''}" if o["critic100"] is not None else "")
             + f" ({100 - o['weights']['firstHand']}%).") if so_n_reviews else ".")
        so_gap_title, so_left_lbl, so_right_lbl = "Our score vs guests", "Us", ("Guests" if o["critic100"] is None else "Guests & critics")
    elif so_left is not None and so_right is not None:
        if abs(so_d) <= 5:
            so_verdict = f"{so_band}: critics and guests agree."
        elif so_d < 0:
            so_verdict = f"{so_band}: guests rate it higher than the critics."
        else:
            so_verdict = f"{so_band}: critics rate it higher than guests do."
        so_sub = f"Built from {so_n_reviews:,} guest reviews ({o['weights']['guests']}%) and {len(scored_ed)} published critic{'s' if len(scored_ed) != 1 else ''} ({o['weights']['critics']}%)."
        so_gap_title, so_left_lbl, so_right_lbl = "Critics vs guests", "Critics", "Guests"
    elif so_odds is not None:
        so_verdict = f"{so_band}, rated {o['guest100']}/100 by guests." if o.get("guest100") is not None else so_band + "."
        so_sub = (f"Built from {so_n_reviews:,} guest reviews." if so_n_reviews else "Built from 1 source.") + " No published critic score yet."
        so_gap_title = ""
        so_left_lbl = so_right_lbl = ""
    else:
        so_verdict = "Not enough reviews for a StayOdds score yet."
        so_sub = "We only show a score when there are 20+ guest reviews or a published critic score."
        so_gap_title = ""
        so_left_lbl = so_right_lbl = ""
    if so_alts and so_area.get("group"):
        so_verdict = so_verdict.rstrip(".") + f", but {so_area['group']} has better-rated options at this price."
    elif so_area.get("rank") == 1 and so_area.get("group"):
        so_verdict = so_verdict.rstrip(".") + f". Guests' top-rated hotel in {so_area['group']}."
    if not o["firstHand"] and not o["visited"]:
        so_sub += " We haven't stayed yet."

    def _so_pos(v):  # place a 0-100 score on a 60-100 scale
        return max(0, min(100, round((float(v) - 60) / 40 * 100)))

    if so_gap_title:
        so_gap_txt = (f"{'+' if so_d > 0 else ''}{so_d} pts" if o["firstHand"] else
                      ("Level" if so_d == 0 else (f"Guests +{abs(so_d)} pts" if so_d < 0 else f"Critics +{so_d} pts")))
        lp, rp = _so_pos(so_left), _so_pos(so_right)
        why = ""
        if o["firstHand"] and h.get("scores"):
            low = [lbl for lbl, k in (("rooms", "rooms"), ("grounds", "grounds"), ("food", "food"), ("service", "service"), ("value", "value"))
                   if h["scores"].get(k) is not None and float(h["scores"][k]) < 4.5]
            if low and so_d < -5:
                why = f"We marked {', '.join(low[:-1]) + ' and ' + low[-1] if len(low) > 1 else low[0]} down a little. "
        if vg and vg.get("rating"):
            why += f"Guests rate it {vg['rating']}/{int(vg.get('scale', 10))} from {so_n_reviews:,} reviews."
        if not o["firstHand"] and pc:
            why = f"{pc.get('sourceName')} scored it {pc.get('rawScore') or str(o['critic100']) + '/100'}. " + why
        so_gap_html = (
            f'<div class="so2-gap"><div class="so2-gap-head"><span>{esc(so_gap_title)}</span><b>{esc(so_gap_txt)}</b></div>'
            f'<div class="so2-gap-track">'
            f'<i class="so2-dot is-a" style="left:{lp}%"></i><em class="so2-lbl is-a" style="left:{lp}%">{esc(so_left_lbl)} {so_left}</em>'
            f'<i class="so2-dot is-b" style="left:{rp}%"></i><em class="so2-lbl is-b" style="left:{rp}%">{esc(so_right_lbl)} {so_right}</em>'
            f'</div><div class="so2-gap-scale"><span>60</span><span>100</span></div>'
            f'<p>{esc(why.strip())}</p></div>'
        )
    else:
        so_gap_html = ""

    so_ring = (
        f'<div class="so2-ring" style="background:conic-gradient(#FF5D22 0 {so_odds}%,#F1E7E0 {so_odds}% 100%)">'
        f'<div><b>{so_odds}%</b><span>StayOdds</span></div></div>' if so_odds is not None else
        '<div class="so2-ring"><div><b>—</b><span>StayOdds</span></div></div>'
    )
    price_bits = ""
    if (h.get("priceSnapshot") or {}).get("nightlyGbp"):
        price_bits = f" · from £{int(h['priceSnapshot']['nightlyGbp']):,}"
    so_hero_html = f"""
          <div class="so2-score">{so_ring}<div class="so2-verdict"><strong>{esc(so_verdict)}</strong><span>{esc(so_sub)}</span></div></div>
          {so_gap_html}
          <div class="so2-actions">
            <a class="so2-btn-price" id="detailPrimaryBookingBtn" data-base-url="{esc(h['bookingUrl'])}" href="{esc(h['bookingUrl'])}" target="_blank" rel="{primary_book_rel}">Check prices{price_bits} &nearr;</a>
            {yt_watch_btn(h, "Watch our " + ("Short" if h.get("coverageType") == "Short Tour" else "review"), "btn btn-outline btn-yt-hero") if review_href else ""}
            <a class="btn btn-outline" href="../../compare/?a={esc(slug)}">Compare</a>
            <button type="button" class="btn btn-outline shortlist-btn" data-shortlist-id="{esc(slug)}" data-resort-name="{esc(h['name'])}" aria-pressed="false">&#9825; Save</button>
            <button type="button" class="btn btn-outline" id="shareHotelCardBtn">{ICO_CAM} Share</button>
          </div>
          <a class="so2-details-jump" href="#full-details">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M8 12l4 4 4-4M12 8v8"/></svg>
            <span><strong>Full StayOdds details below</strong><small>What guests and critics say, best months, room tips and rivals</small></span>
          </a>
          <section class="so2-dates" aria-label="Choose your dates">
            <div class="so2-dates-head"><strong>When are you going?</strong><span id="soDatesPicked"></span></div>
            <div class="so2-quick" id="soQuickDates" role="group" aria-label="Quick dates"></div>
            <a class="so2-hol-link" href="../../holidays/">See our top hotels for Christmas &amp; holidays &rarr;</a>
            <div class="date-rate-bar" id="detailDateRateBar">
              <div class="date-rate-inputs">
                <label><span>Check-in</span><input type="date" id="detailCheckin" /></label>
                <label><span>Check-out</span><input type="date" id="detailCheckout" /></label>
                <label><span>Guests</span>
                  <select id="detailAdults"><option value="1">1 Adult</option><option value="2" selected>2 Adults</option><option value="3">3 Adults</option><option value="4">4 Adults</option></select>
                </label>
                <button type="button" class="{live_btn_cls}" id="detailLiveRateBtn" data-nuitee-id="{esc(h.get("nuiteeHotelId") or "")}">Check Live Rate</button>
              </div>
              <div class="date-rate-status" id="detailLiveRateStatus">
                {f"Indicative: <strong>{esc(h['priceSnapshot']['label'])}</strong> (updated {esc(h['priceSnapshot'].get('checkedAt', ''))})" if h.get("priceSnapshot") else date_hint}
              </div>
            </div>
          </section>
{DETAIL_OTA_STRIP}"""

    # Highlights strip (Nov 2026): videos and awards visible up top, details stay in the tab
    _chips = []
    if o["ytReviews"]:
        _n = len(o["ytReviews"])
        _chips.append(f'<a class="so2-chip is-video" href="#more-reviews" data-open-tab="reviews">&#9654; {_n} more video review{"s" if _n != 1 else ""}</a>')
    for _r in (h.get("dining") or [])[:2]:
        _chips.append(f'<a class="so2-chip is-award" href="{esc(_r["url"])}" target="_blank" rel="noopener noreferrer">{esc(_r["name"])} · {esc(_r["distinction"])}</a>')
    for _a in o["awards"][:3]:
        _chips.append(f'<a class="so2-chip is-award" href="{esc(_a["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{ICO_TROPHY} {esc(_a["label"])}</a>')
    _known = " ".join(a["label"] for a in o["awards"]).lower()
    _itwf_crit = [c for c in ((h.get("itwf") or {}).get("critics") or [])
                  if re.search(r"cond[eé] nast|travel \+ leisure|gault|la liste", c, re.I)
                  and not (re.search(r"la liste", c, re.I) and "laliste" in _known)]
    for _c in _itwf_crit[:2]:
        _chips.append(f'<a class="so2-chip is-award" href="{esc(h["itwf"]["url"])}" target="_blank" rel="noopener">{ICO_TROPHY} {esc(_c)}</a>')
    _rest = max(0, len(o["awards"]) - 3) + len(o["editorial"])
    if _rest:
        _chips.append(f'<a class="so2-chip" href="#more-reviews" data-open-tab="reviews">+{_rest} more award{"s" if _rest != 1 else ""} &amp; critic review{"s" if _rest != 1 else ""}</a>')
    so_highlights_html = (
        '<section class="so2-highlights" aria-label="Videos and awards"><span class="so2-hl-label">Watch &amp; awards</span>'
        + "".join(_chips) + "</section>"
    ) if _chips else ""
    _rev_count = (1 if review_href else 0) + len(o["ytReviews"]) + len(o["awards"]) + len(o["editorial"])

    # three voices
    if o["firstHand"] and o.get("personalScore25") is not None:
        ours_body = (f'<div class="so2-big">{fmt_score_num(o["personalScore25"])}<small>/{o["personalScoreMax"]}</small></div>'
                     f'<div class="detail-bars">{scores_html}</div>')
    elif o["visited"]:
        ours_body = ('<div class="so2-mid">We filmed it</div><p class="so2-muted">We reviewed this stay on video without a numeric '
                     'scorecard. We never add numbers afterwards.</p>')
    else:
        ours_body = ('<div class="so2-mid">Not stayed yet</div><p class="so2-muted">When we stay and publish a scored review, '
                     'our score appears here and counts for 70% of StayOdds.</p>')
    if vg and vg.get("rating"):
        src_rows = "".join(
            f'<div class="so2-row"><span>{esc(sp["name"])}</span><b>{sp["rating"]:g}/{int(sp["scale"])} '
            f'<small>({int(sp["reviewCount"]):,})</small></b></div>' if sp.get("reviewCount") else
            f'<div class="so2-row"><span>{esc(sp["name"])}</span><b>{sp["rating"]:g}/{int(sp["scale"])}</b></div>'
            for sp in (vg.get("sources") or [])
        )
        guests_body = (f'<div class="so2-big">{vg["rating"]}<small>/{int(vg.get("scale", 10))}</small></div>'
                       f'<p class="so2-muted">from {so_n_reviews:,} reviews{", combined by number of reviews" if len(vg.get("sources") or []) > 1 else ""}</p>{src_rows}')
    else:
        guests_body = '<div class="so2-mid">Not enough reviews</div><p class="so2-muted">We show a guest score only from 20+ reviews.</p>'
    critic_rows = "".join(
        f'<div class="so2-row"><a href="{esc(e.get("sourceUrl") or "#")}" target="_blank" rel="noopener">{esc(e["sourceName"])} &nearr;</a>'
        f'<b>{esc(e.get("rawScore") or str(e["normalized100"]) + "/100")}</b></div>'
        for e in scored_ed
    )
    critics_body = (critic_rows or '<div class="so2-mid">No published critic score yet</div>') + (
        f'<div class="so2-chips">{hero_awards_html}</div>' if hero_awards_html else
        '<p class="so2-muted">Awards (MICHELIN Keys, Forbes, 50 Best) are listed by name and never turned into points.</p>')
    so_voices_html = f"""
      <section class="so2-three">
        <div class="so2-card"><div class="so2-kicker is-accent">Our stay</div>{ours_body}</div>
        <div class="so2-card"><div class="so2-kicker">Guests</div>{guests_body}</div>
        <div class="so2-card"><div class="so2-kicker">Critics &amp; awards</div>{critics_body}</div>
      </section>"""

    so_love_html = ""
    if h.get("standout") or h.get("watchOut"):
        so_love_html = '<section class="so2-two">' + (
            f'<div class="so2-card is-love"><h3>Why guests love it</h3><p>{esc(h.get("standout"))}</p></div>' if h.get("standout") else "") + (
            f'<div class="so2-card is-know"><h3>Know before you book</h3><p>{esc(h.get("watchOut"))}</p></div>' if h.get("watchOut") else "") + "</section>"
    so_more_facts = ""
    if facts_html or red_flags_html or ps_has:
        so_more_facts = (f'<details class="so2-more"><summary>Hotel facts &amp; property status</summary>'
                         f'{f"<div class=\'key-facts-grid\'>{facts_html}</div>" if facts_html else ""}'
                         f'{f"<div class=\'key-facts-flags\'>{red_flags_html}</div>" if red_flags_html else ""}'
                         f'{property_status_html if ps_has else ""}</details>')

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light only" />
  <link rel="icon" type="image/svg+xml" href="../../assets/stayodds-favicon.svg?v=3" />
  <link rel="icon" type="image/png" sizes="32x32" href="../../assets/stayodds-favicon-32.png?v=3" />
  <link rel="shortcut icon" href="../../favicon.ico?v=3" />
  <link rel="apple-touch-icon" sizes="180x180" href="../../assets/stayodds-apple-touch-icon.png?v=3" />
  <meta name="google-adsense-account" content="ca-pub-4618281487216833" />
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4618281487216833" crossorigin="anonymous"></script>
  <title>{esc(title_text)}</title>
  <meta name="description" content="{esc(meta_desc)}" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:type" content="article" />
  <meta property="og:title" content="{esc(title_text)}" />
  <meta property="og:description" content="{esc(meta_desc)}" />
  <meta property="og:image" content="{esc(img_abs)}" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" media="print" onload="this.media='all'" />
  <noscript><link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" /></noscript>
  <script>if(window.self!==window.top||location.search.includes("embed=1"))document.documentElement.classList.add("is-embedded");</script>
  <style>.site-header{{background:#071323!important;}}html.is-embedded .site-header,html.is-embedded .site-footer,html.is-embedded .hub-back-link{{display:none!important;}}</style>
  <link rel="stylesheet" href="../../assets/styles.min.css?v=47" />
  <link rel="stylesheet" href="../../assets/stayodds-hotel.css?v=6" />
  <script data-goatcounter="https://stayodds.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <script type="text/javascript">
      (function(c,l,a,r,i,t,y){{
          c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
      }})(window, document, "clarity", "script", "zhmuw1amoy");
  </script>
  <script nowprocket data-noptimize="1" data-cfasync="false" data-wpfc-render="false" seraph-accel-crit="1" data-no-defer="1" data-cmp-ab="2">
    (function () {{
        var script = document.createElement("script");
        script.async = 1;
        script.setAttribute("data-cmp-ab","2");
        script.src = 'https://emrld.ltd/NjA0NzQ3.js?t=604747';
        document.head.appendChild(script);
    }})();
  </script>
</head>
<body class="stayodds-warm-canvas">
{chrome_header("../../")}

  <main class="has-top-band">
    <div class="detail-top-band" aria-hidden="true"></div>
    <div class="container">
      <div class="detail-breadcrumb">
        <a id="crumbAllLink" href="../../compare/">&larr; All StayOdds Hotels</a>
        <span>/</span>
        <a id="crumbRegionLink" href="../../compare/?region={region_q}">{esc(h['region'])}</a>
        <span>/</span>
        <strong>{esc(h['name'])}</strong>
        <a id="crumbAltViewLink" href="../../hotels/?region={region_q}" style="margin-left:auto;font-size:12.5px;font-weight:600;color:var(--accent);white-space:nowrap;">{ICO_PIN} {esc(h['region'])} Map &rarr;</a>
      </div>

      <section class="detail-hero">
        <div class="detail-hero-media">
          <div class="yt-stage"{' data-yt-host' if h.get('videoId') else ''}>
            <img src="{esc(img_src)}" alt="{esc(h['name'])}" fetchpriority="high" decoding="async" />
            {yt_overlay(h, inline=True)}
          </div>
          {(f'<p class="photo-credit" style="font-size:11.5px;color:var(--ink-muted,#76736c);margin:6px 2px 0;"><a href="{esc(h["photoCredit"]["url"])}" target="_blank" rel="noopener" style="color:inherit;">{esc(h["photoCredit"]["text"])}</a></p>') if h.get("photoCredit") else ""}
          <div class="detail-hero-badges">
            <span class="tag {'tag-accent' if o['firstHand'] else 'tag-slate'}">{esc(o['tierLabel'])}</span>
            <span class="tag {tag_class}" id="heroStatusBadge">{esc(o['statusBadge'])}</span>
            {f'<span class="tag {ps_tag_cls}">{esc(ps_badge_lbl)}</span>' if ps_box_cls in ('is-danger', 'is-warn') else ''}
          </div>
        </div>
        <div class="detail-hero-body">
          <div class="meta-line">
            <span>{esc(h['location'])}, {esc(h['country'])}</span>
            {f"<span>&bull;</span><span>{esc(h['brand'])}</span>" if h.get('brand') else ""}
            {f"<span>&bull;</span><span><strong>{esc((h.get('priceSnapshot') or {}).get('label') or h.get('priceRange'))}</strong></span>" if ((h.get('priceSnapshot') or {}).get('label') or h.get('priceRange')) else ""}
          </div>
          {f'<div class="meta-line" style="margin-top:8px;gap:6px;">{hero_awards_html}</div>' if hero_awards_html else ''}
          {(lambda lg: f'<img class="so2-brand-logo" src="../..{esc(lg[0])}" alt="{esc(lg[1])}" title="{esc(lg[1])}" />' if lg else '')(logo_for_hotel(h.get("brand")))}
          <h1 class="detail-title">{esc(h['name'])}</h1>

          {so_hero_html}
          {so_highlights_html}
        </div>
      </section>
      <div id="full-details" style="scroll-margin-top:84px"></div>

      {f'''<section class="detail-section" id="guest-rank">
        <div class="key-facts-panel">
          <h2 class="section-title" style="font-size:20px;margin:0 0 4px">How Guests Rank It</h2>
          <p class="section-subtitle" style="margin:0">Where this hotel's guest score sits against other StayOdds hotels nearby, and against hotels charging a similar price: are guests getting what they pay for? Left is the best-rated hotel, right the lowest.</p>
          {rank_html}
        </div>
      </section>''' if rank_html else ''}

      {so_voices_html}

      <section class="so2-section"><h2 class="so2-h2">Before you book</h2>{trip_context_html}{so_more_facts}</section>
      {so_love_html}

      <section class="so2-tabs" data-so2-tabs id="more-reviews">
        <div class="so2-tablist" role="tablist">
          <button type="button" role="tab" aria-selected="true" data-tab="comments">Guest comments</button>
          <button type="button" role="tab" aria-selected="false" data-tab="reviews">Reviews, awards &amp; videos{f' <span class="so2-count">{_rev_count}</span>' if _rev_count else ''}</button>
          <button type="button" role="tab" aria-selected="false" data-tab="nearby">Compare nearby</button>
          <button type="button" role="tab" aria-selected="false" data-tab="score">How the score works</button>
        </div>
      <div class="so2-panel" data-panel="score" hidden>
      <details class="stayodds-explainer" open><summary><span>How is this StayOdds % calculated?</span></summary><div class="stayodds-explainer-body"><div class="stayodds-explainer-eq" id="stayOddsEquation">{esc(equation_text)}</div><ul class="stayodds-explainer-list"><li><strong>Hotels we stayed at:</strong> 70% our filmed stay + 30% guest &amp; critic consensus.</li><li><strong>Other hotels:</strong> 35% published critics + 65% guest reviews when both exist, otherwise the one source.</li><li><strong>No made-up numbers:</strong> awards and comment-only reviews are linked, never converted into points.</li></ul></div></details>
      <section class="detail-section" id="score-sources">
        <div class="detail-two-col">
          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>StayOdds Weighting</h3>
              <span class="tag">{esc(o['scoreTrackLabel'])}</span>
            </div>
            <p class="detail-panel-sub" id="weightFormulaSub">{esc(o['formula'])}</p>
            <div class="formula-grid" style="margin-top:14px; grid-template-columns: repeat(3, 1fr);">
              <div class="formula-step"><span class="formula-weight" id="weightFirstHandPct">{o['weights']['firstHand']}%</span><strong>{f"{o['personalScoreLabel'].replace(' ', '')} → {o['ours100']}%" if (o['ours100'] is not None and o.get('personalScoreLabel')) else (f"{o['ours100']}%" if o['ours100'] is not None else "—")}</strong><small>Uncharted Stay</small></div>
              <div class="formula-step"><span class="formula-weight" id="weightCriticsPct">{o['weights']['critics']}%</span><strong>{f"{o['critic100']}%" if o['critic100'] is not None else ("Unverified" if unverified_ed else "—")}</strong><small>Published Critics</small></div>
              <div class="formula-step"><span class="formula-weight" id="weightGuestsPct">{o['weights']['guests']}%</span><strong id="weightGuestVal">{f"{o['guest100']}%" if o['guest100'] is not None else "Live…"}</strong><small>Guest Reviews</small></div>
            </div>
            {unverified_transparency_html}
          </div>

          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>My Uncharted Scorecard</h3>
              <span class="tag {'tag-accent' if o['firstHand'] else 'tag-slate'}">{f"{o['personalScoreLabel']} Total" if (o['firstHand'] and o.get('personalScoreLabel')) else o['tierLabel']}</span>
            </div>
            {f'<div class="detail-bars" style="margin-top:12px;">{scores_html}</div>' if scores_html else ('<p class="detail-panel-sub" style="margin-top:12px;">We filmed and reviewed this stay qualitatively in our video without assigning a numeric scorecard — we never invent numbers after the fact. Watch our full video review above for our honest take.</p>' if o['visited'] else '<p class="detail-panel-sub" style="margin-top:12px;">We have not scored a personal stay here yet. Once we stay and publish a scored review, our Uncharted Scorecard will appear here.</p>')}
          </div>
        </div>
      </section>

      </div>
      <div class="so2-panel" data-panel="reviews" hidden>
      <section class="detail-section">
        <div class="detail-two-col">
          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>Official Awards &amp; Editorial Ratings</h3>
              <span class="tag">{len(o['awards']) + len(o['editorial'])} sourced</span>
            </div>
            <div class="channel-breakdown-list" style="margin-top:12px;">
              {awards_html + editorial_html if (awards_html or editorial_html) else '<p class="detail-panel-sub">No editorial reviews added yet — we only include awards and critic scores with a direct link to the published review.</p>'}
            </div>
          </div>
          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>Linked YouTube Video Reviews</h3>
              <span class="tag">{(1 if review_href else 0) + len(o['ytReviews'])} linked</span>
            </div>
            <div class="channel-breakdown-list" style="margin-top:12px;">
              {yt_html if yt_html else '<p class="detail-panel-sub">No video tours linked yet — we only feature full hotel walkthroughs we have personally checked.</p>'}
            </div>
          </div>
        </div>
      </section>

      </div>
      <div class="so2-panel" data-panel="comments">{voices_section_html(h)}</div>
      <div class="so2-panel" data-panel="nearby" hidden>
      <section class="detail-section" style="margin-bottom:24px;">
        <div class="section-header" style="margin-bottom:18px;flex-wrap:wrap;gap:12px;">
          <div>
            <h2 class="section-title">Compare Nearby Luxury Stays</h2>
            <p class="section-subtitle">Explore other personally curated properties in {esc(h['region'])}.</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <a class="btn btn-outline" id="nearbyMapLink" href="../../hotels/?region={region_q}">{ICO_PIN} All {esc(h['region'])} on Map &rarr;</a>
            <a class="btn btn-outline" id="nearbyListLink" href="../../compare/?region={region_q}">All {esc(h['region'])} in StayOdds &rarr;</a>
            <button type="button" class="so-request-btn" data-open-resort-request>+ Request a Resort</button>
          </div>
        </div>
        {rival_matchups_html}
        <div class="related-grid">{related_html}</div>
      </section>
      </div>
      </section>
    </div>
{chrome_partner_strip("../../")}  </main>

  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div>
          <div class="footer-brand"><span class="stayodds-wordmark">StayOdds<span class="stayodds-dot">.</span></span> &bull; by The Uncharted Itinerary</div>
          <p class="footer-muted">Critics vs Real Guest Reviews — personally curated luxury hotel comparisons with verified sources.</p>
        </div>
        <div class="footer-links">
          <a href="../../compare/">StayOdds Directory</a>
          <a href="../../hotels/">Hotel Map</a>
          <a href="../../">Videos</a>
          <a href="../../links/">Deals &amp; Gear</a>
          <a href="../../about/">About</a>
          <a href="../../faq/">FAQ</a>
          <a href="../../contact/">Contact</a>
          <a href="../../privacy/">Privacy Policy</a>
          <button type="button" class="so-request-footer-link" data-open-resort-request>+ Request a Resort</button>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; {datetime.now().year} StayOdds &amp; The Uncharted Itinerary</span>
        <span>Disclosure: Booking &amp; gear links may earn an affiliate commission at no extra cost to you (<a href="../../privacy/" style="color:inherit;text-decoration:underline;">Privacy &amp; Ad Disclosure</a>).</span>
      </div>
    </div>
  </footer>

  <script src="../../assets/stayodds-feedback.js?v=4" defer></script>
  <script src="../../assets/stayodds-video.js?v=2" defer></script>
  <script>
    document.querySelectorAll("[data-open-tab]").forEach(function (a) {{
      a.addEventListener("click", function (e) {{
        var t = document.querySelector('[data-so2-tabs] [data-tab="' + a.getAttribute("data-open-tab") + '"]');
        if (!t) return; e.preventDefault(); t.click();
        document.getElementById("more-reviews").scrollIntoView({{ behavior: "smooth", block: "start" }});
      }});
    }});
    document.querySelectorAll("[data-so2-tabs]").forEach(function (box) {{
      box.addEventListener("click", function (e) {{
        var b = e.target.closest("[data-tab]"); if (!b) return;
        box.querySelectorAll("[data-tab]").forEach(function (x) {{ x.setAttribute("aria-selected", x === b ? "true" : "false"); }});
        box.querySelectorAll("[data-panel]").forEach(function (p) {{ p.hidden = p.getAttribute("data-panel") !== b.getAttribute("data-tab"); }});
      }});
    }});
  </script>
  <script type="module">
    const pageRegion = {json.dumps(h['region'])};
    const qsParams = new URLSearchParams(window.location.search);
    const isEmbed = qsParams.get("embed") === "1";
    const fromMap = qsParams.get("from") === "map" || (document.referrer || "").includes("/hotels");
    const regionQ = encodeURIComponent(pageRegion);
    const embedSuffix = isEmbed ? "&embed=1" : "";
    const embedOnly = isEmbed ? "?embed=1" : "";

    const crumbAll = document.getElementById("crumbAllLink");
    const crumbRegion = document.getElementById("crumbRegionLink");
    const crumbAlt = document.getElementById("crumbAltViewLink");
    const nearbyMap = document.getElementById("nearbyMapLink");
    const nearbyList = document.getElementById("nearbyListLink");

    if (fromMap) {{
      if (crumbAll) {{
        crumbAll.href = "../../hotels/" + embedOnly;
        crumbAll.textContent = "← World Hotel Map";
      }}
      if (crumbRegion) {{
        crumbRegion.href = "../../hotels/?region=" + regionQ + embedSuffix;
      }}
      if (crumbAlt) {{
        crumbAlt.href = "../../compare/?region=" + regionQ + embedSuffix;
        crumbAlt.textContent = pageRegion + " in StayOdds →";
      }}
      document.getElementById("hubTabStayOdds")?.classList.remove("active");
      document.getElementById("hubTabStayOdds")?.removeAttribute("aria-current");
      document.getElementById("hubTabMap")?.classList.add("active");
      document.getElementById("hubTabMap")?.setAttribute("aria-current", "page");
      document.querySelectorAll('.related-grid a[href^="../"]').forEach((a) => {{
        const href = a.getAttribute("href") || "";
        if (!href.includes("?")) a.setAttribute("href", href + "?from=map" + embedSuffix);
      }});
    }} else if (isEmbed) {{
      if (crumbAll) crumbAll.href = "../../compare/?embed=1";
      if (crumbRegion) crumbRegion.href = "../../compare/?region=" + regionQ + "&embed=1";
      if (crumbAlt) crumbAlt.href = "../../hotels/?region=" + regionQ + "&embed=1";
    }}
    if (isEmbed) {{
      if (nearbyMap) nearbyMap.href = "../../hotels/?region=" + regionQ + "&embed=1";
      if (nearbyList) nearbyList.href = "../../compare/?region=" + regionQ + "&embed=1";
    }}

    // Date-aware outbound booking links + explicit on-demand live rate check
    const ciEl = document.getElementById("detailCheckin");
    const coEl = document.getElementById("detailCheckout");
    const adEl = document.getElementById("detailAdults");
    const bookBtn = document.getElementById("detailPrimaryBookingBtn");
    const rateBtn = document.getElementById("detailLiveRateBtn");
    const rateStatus = document.getElementById("detailLiveRateStatus");

    const fmtDate = (d) => d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    const addDays = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
    const today = new Date(); today.setHours(0, 0, 0, 0);
    // Quick dates: the next upcoming occurrence of each, worked out from today
    function easterSunday(y) {{
      const a = y % 19, b = Math.floor(y / 100), c = y % 100, d = Math.floor(b / 4), e = b % 4, f = Math.floor((b + 8) / 25),
        g = Math.floor((b - f + 1) / 3), h = (19 * a + b - d - g + 15) % 30, i = Math.floor(c / 4), k = c % 4,
        l = (32 + 2 * e + 2 * i - h - k) % 7, m = Math.floor((a + 11 * h + 22 * l) / 451), mo = Math.floor((h + l - 7 * m + 114) / 31);
      return new Date(y, mo - 1, ((h + l - 7 * m + 114) % 31) + 1);
    }}
    function nextOf(fn) {{ const y = today.getFullYear(); let r = fn(y); if (r[0] <= today) r = fn(y + 1); return r; }}
    const fri = addDays(today, ((5 - today.getDay() + 7) % 7) || 7);
    const QUICK = [
      {{ key: "weekend", label: (fri - today) <= 5 * 86400000 ? "This weekend" : "Next weekend", range: [fri, addDays(fri, 2)] }},
      {{ key: "christmas", label: "Christmas", range: nextOf((y) => [new Date(y, 11, 23), new Date(y, 11, 27)]) }},
      {{ key: "newyear", label: "New Year", range: nextOf((y) => [new Date(y, 11, 30), new Date(y + 1, 0, 2)]) }},
      {{ key: "valentines", label: "Valentine's", range: nextOf((y) => [new Date(y, 1, 13), new Date(y, 1, 15)]) }},
      {{ key: "easter", label: "Easter", range: nextOf((y) => {{ const e = easterSunday(y); return [addDays(e, -2), addDays(e, 2)]; }}) }},
      {{ key: "summer", label: "Summer week", range: nextOf((y) => [new Date(y, 7, 1), new Date(y, 7, 8)]) }},
    ];
    const shortD = (d) => d.toLocaleDateString("en-GB", {{ day: "numeric", month: "short" }});
    const quickWrap = document.getElementById("soQuickDates");
    const pickedEl = document.getElementById("soDatesPicked");
    const nights = (a, b) => Math.round((new Date(b) - new Date(a)) / 86400000);
    function markPicked() {{
      const ci = ciEl?.value, co = coEl?.value;
      quickWrap?.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.ci === ci && b.dataset.co === co)));
      if (pickedEl) pickedEl.textContent = ci && co && co > ci ? `${{shortD(new Date(ci + "T12:00"))}} – ${{shortD(new Date(co + "T12:00"))}} · ${{nights(ci, co)}} night${{nights(ci, co) === 1 ? "" : "s"}}` : "";
      if (bookBtn && ci && co && co > ci) {{
        const priceTxt = bookBtn.dataset.label || (bookBtn.dataset.label = bookBtn.textContent.replace(/\s*↗\s*$/, ""));
        bookBtn.textContent = `Check prices · ${{shortD(new Date(ci + "T12:00"))}}–${{shortD(new Date(co + "T12:00"))}} ↗`;
        bookBtn.title = priceTxt;
      }}
      try {{ localStorage.setItem("so_dates", JSON.stringify({{ ci, co, ad: adEl?.value || "2" }})); }} catch (_) {{}}
    }}
    QUICK.forEach((q) => {{
      if (!quickWrap) return;
      const b = document.createElement("button");
      b.type = "button"; b.className = "so2-qd";
      b.dataset.ci = fmtDate(q.range[0]); b.dataset.co = fmtDate(q.range[1]); b.dataset.key = q.key;
      b.innerHTML = `<b>${{q.label}}</b><span>${{shortD(q.range[0])}} – ${{shortD(q.range[1])}}</span>`;
      b.addEventListener("click", () => {{
        ciEl.value = b.dataset.ci; coEl.value = b.dataset.co;
        updateDatedBookingLink(); markPicked();
        if (rateBtn && rateBtn.getAttribute("data-nuitee-id")) rateBtn.click();
      }});
      quickWrap.appendChild(b);
    }});
    let saved = null;
    try {{ saved = JSON.parse(localStorage.getItem("so_dates") || "null"); }} catch (_) {{}}
    if (saved && !(saved.ci > fmtDate(today))) saved = null;
    const whenQ = QUICK.find((q) => q.key === qsParams.get("when"));
    const defCi = addDays(today, 45), defCo = addDays(today, 47);
    if (ciEl && !ciEl.value) ciEl.value = qsParams.get("checkin") || (whenQ && fmtDate(whenQ.range[0])) || saved?.ci || fmtDate(defCi);
    if (coEl && !coEl.value) coEl.value = qsParams.get("checkout") || (whenQ && fmtDate(whenQ.range[1])) || saved?.co || fmtDate(defCo);
    if (adEl && (qsParams.get("adults") || saved?.ad)) adEl.value = qsParams.get("adults") || saved.ad;

    function updateDatedBookingLink() {{
      if (!bookBtn) return;
      const baseUrl = bookBtn.getAttribute("data-base-url") || bookBtn.href;
      const ci = ciEl?.value || "";
      const co = coEl?.value || "";
      const ad = adEl?.value || "2";
      try {{
        const u = new URL(baseUrl);
        if (/prf\\.hn$/i.test(u.hostname) && ci && co && co > ci) {{
          const m = baseUrl.match(/destination:(.+)$/);
          if (m) {{
            const d = new URL(decodeURIComponent(m[1]));
            const us = (x) => x.slice(5, 7) + "/" + x.slice(8, 10) + "/" + x.slice(0, 4);
            d.searchParams.set("fromDate", us(ci));
            d.searchParams.set("toDate", us(co));
            d.searchParams.set("numAdultsPerRoom", ad);
            bookBtn.href = baseUrl.slice(0, m.index) + "destination:" + encodeURIComponent(d.toString());
          }}
        }}
        if (/booking\\.com/i.test(u.hostname) && ci && co && co > ci) {{
          u.searchParams.set("checkin", ci);
          u.searchParams.set("checkout", co);
          u.searchParams.set("group_adults", ad);
          u.searchParams.set("no_rooms", "1");
          bookBtn.href = u.toString();
        }}
      }} catch (_) {{}}
    }}
    [ciEl, coEl, adEl].forEach((el) => el?.addEventListener("change", () => {{ updateDatedBookingLink(); markPicked(); }}));
    updateDatedBookingLink();
    markPicked();
    if (whenQ && rateBtn && rateBtn.getAttribute("data-nuitee-id")) rateBtn.click();

    rateBtn?.addEventListener("click", async () => {{
      const nid = rateBtn.getAttribute("data-nuitee-id");
      const ci = ciEl?.value || "";
      const co = coEl?.value || "";
      const ad = adEl?.value || "2";
      if (!nid) {{
        // Not covered by live pricing: say so and point to where rates can be checked.
        if (rateStatus) rateStatus.innerHTML = {live_unavailable_js};
        return;
      }}
      if (!ci || !co || co <= ci) {{
        if (rateStatus) rateStatus.textContent = "Please select a valid check-in and check-out date.";
        return;
      }}
      rateBtn.disabled = true;
      rateBtn.textContent = "Checking…";
      if (rateStatus) rateStatus.textContent = "Checking live nightly rate for your selected dates…";
      try {{
        const url = `https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-hotel-rates?hotel_ids=${{encodeURIComponent(nid)}}&checkin=${{encodeURIComponent(ci)}}&checkout=${{encodeURIComponent(co)}}&adults=${{encodeURIComponent(ad)}}&currency=GBP`;
        const res = await fetch(url, {{ headers: {{ Accept: "application/json" }} }});
        const data = await res.json();
        const r = data?.rates?.[nid];
        if (r && r.perNight) {{
          if (rateStatus) {{
            rateStatus.innerHTML = `<strong style="color:#0f766e;">Live Rate (${{ci}} → ${{co}}): £${{Number(r.perNight).toLocaleString("en-GB")}}/nt</strong> (£${{Number(r.total).toLocaleString("en-GB")}} total for ${{r.nights}} nt${{r.refundable ? " • Refundable" : ""}})`;
          }}
        }} else if (data?.status === "cap_reached") {{
          if (rateStatus) rateStatus.textContent = "Daily live-rate quota reached — click Check Live Rates on Booking.com above (your dates are already pre-filled).";
        }} else {{
          if (rateStatus) rateStatus.textContent = "No instant partner rooms returned for those exact dates — click Check Live Rates on Booking.com above (dates pre-filled).";
        }}
      }} catch (_) {{
        if (rateStatus) rateStatus.textContent = "Unable to check live rate right now — click Booking.com above with your dates pre-filled.";
      }} finally {{
        rateBtn.disabled = false;
        rateBtn.textContent = "Check Live Rate";
      }}
    }});

    const placeId = {json.dumps(google_place_id)};
    const firstHand = {json.dumps(bool(o['firstHand']))};
    const ours100 = {json.dumps(o['ours100'])};
    const personalLabel = {json.dumps(o['personalScoreLabel'].replace(' ', '') if o.get('personalScoreLabel') else None)};
    const critic100 = {json.dumps(o['critic100'])};
    const staticGuest100 = {json.dumps(o['guest100'])};
    const left100 = {json.dumps(o['left100'])};
    const criticLabel = {json.dumps(pc["sourceName"] if (len(scored_ed) == 1 and pc) else f"{len(scored_ed)} published critics")};
    const mapsFallbackUrl = placeId
      ? "https://www.google.com/maps/place/?q=place_id:" + encodeURIComponent(placeId)
      : "";

    function showMapsFallback(mapsUrl) {{
      const strip = document.getElementById("liveGoogleStrip");
      const gDisp = document.getElementById("gapGuestDisplay");
      const kpiVal = document.getElementById("kpiGuestVal");
      const kpiOdds = document.getElementById("kpiOdds");
      const wGuestVal = document.getElementById("weightGuestVal");
      if (gDisp && gDisp.textContent.includes("Checking")) {{
        gDisp.textContent = "Google Maps ↗";
      }}
      if (kpiVal && kpiVal.textContent.includes("Live")) {{
        kpiVal.innerHTML = mapsUrl
          ? `<a href="${{mapsUrl}}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none;">Maps ↗</a>`
          : "—";
      }}
      if (kpiOdds && kpiOdds.textContent.includes("Live")) {{
        kpiOdds.textContent = "—";
      }}
      if (wGuestVal && wGuestVal.textContent.includes("Live")) {{
        wGuestVal.textContent = "—";
      }}
      if (strip && mapsUrl) {{
        strip.style.display = "flex";
        strip.innerHTML = `<span><a href="${{mapsUrl}}" target="_blank" rel="noopener noreferrer">Check live reviews on Google Maps ↗</a></span><span class="powered-google">Google Maps</span>`;
      }}
    }}

    if (placeId && !document.getElementById("kpiOdds")) {{ showMapsFallback(mapsFallbackUrl); }}
    if (false && placeId) {{
      const grCacheKey = "stayodds_gr_v1_" + placeId;
      const GR_TTL_MS = 24 * 60 * 60 * 1000;
      let cachedGr = null;
      try {{
        const raw = localStorage.getItem(grCacheKey);
        if (raw) {{
          const parsed = JSON.parse(raw);
          if (parsed && parsed.ts && (Date.now() - parsed.ts) < GR_TTL_MS && parsed.data) {{
            cachedGr = parsed.data;
          }}
        }}
      }} catch (_) {{}}

      const grPromise = cachedGr
        ? Promise.resolve(cachedGr)
        : fetch("https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-google-rating?place_id=" + encodeURIComponent(placeId))
            .then((r) => (r.ok ? r.json() : null))
            .then((g) => {{
              if (g && g.status === "ok" && typeof g.rating === "number") {{
                try {{ localStorage.setItem(grCacheKey, JSON.stringify({{ ts: Date.now(), data: g }})); }} catch (_) {{}}
              }}
              return g;
            }});

      grPromise
        .then((g) => {{
          if (!g || g.status !== "ok" || typeof g.rating !== "number") {{
            showMapsFallback((g && g.googleMapsUri) || mapsFallbackUrl);
            return;
          }}
          const rawG100 = typeof g.normalized100 === "number" ? g.normalized100 : Math.round(g.rating * 20);
          const rc = typeof g.reviewCount === "number" ? g.reviewCount : null;
          const g100 = rc && rc > 0 && rc < 40 ? Math.round((rawG100 * rc + 90 * 8) / (rc + 8)) : rawG100;
          const strip = document.getElementById("liveGoogleStrip");
          const mapsUrl = g.googleMapsUri || mapsFallbackUrl;
          if (strip) {{
            strip.style.display = "flex";
            const revText = g.reviewCount ? ` (${{g.reviewCount.toLocaleString("en-GB")}} reviews)` : "";
            const link = mapsUrl ? ` · <a href="${{mapsUrl}}" target="_blank" rel="noopener noreferrer">View on Google Maps ↗</a>` : "";
            const notice = g.policyNotice || "Reviews are not verified by Google.";
            strip.innerHTML = `<span><strong>Live Google Rating:</strong> ${{g.rating.toFixed(1)}} ★${{revText}}${{link}}<br><small style="color:#64748b;font-weight:400;">${{notice}}</small></span><span class="powered-google">Powered by Google</span>`;
          }}

          const gBar = document.getElementById("gapGuestBar");
          const gDisp = document.getElementById("gapGuestDisplay");
          const pill = document.getElementById("gapDeltaPill");
          const kpiVal = document.getElementById("kpiGuestVal");
          const kpiLbl = document.getElementById("kpiGuestLbl");

          if (kpiVal && kpiVal.textContent.includes("Live")) {{
            kpiVal.innerHTML = `${{g.rating.toFixed(1)}}<span>/5★</span>`;
            if (kpiLbl) kpiLbl.textContent = g.reviewCount ? `Google (${{g.reviewCount.toLocaleString("en-GB")}})` : "Google Guests";
          }}
          if (gDisp && gDisp.textContent.includes("Checking")) {{
            gDisp.textContent = `${{g.rating.toFixed(1)}} ★ (${{g100}}/100)`;
            if (gBar) gBar.style.width = `${{g100}}%`;
          }}

          // Recalculate Two-Track StayOdds % live when no static licensed guest score was already baked in
          if (staticGuest100 == null) {{
            const mkt = critic100 != null ? Math.round(critic100 * 0.35 + g100 * 0.65) : g100;
            let wFH = 0, wCr = 0, wGu = 0, odds = null, formula = "";
            if (firstHand && ours100 != null) {{
              wFH = 70;
              wCr = critic100 != null ? 11 : 0;
              wGu = critic100 != null ? 19 : 30;
              odds = Math.round(ours100 * 0.70 + mkt * 0.30);
              formula = `70% Uncharted Stay • 30% Consensus (${{mkt}}%)`;
            }} else if (critic100 != null) {{
              wFH = 0; wCr = 35; wGu = 65;
              odds = mkt;
              formula = "Based on 2 sources: Published Critics (35%) + Google Reviews (65%)";
            }} else {{
              wFH = 0; wCr = 0; wGu = 100;
              odds = mkt;
              formula = "Based on 1 source (Google Reviews)";
            }}

            const active = [firstHand ? ours100 : null, critic100, g100].filter((v) => v != null);
            let badgeText = active.length === 1 ? "1 Data Source" : "Mostly Aligned";
            let badgeClass = "tag-teal";
            if (active.length >= 2) {{
              const spread = firstHand && ours100 != null ? Math.abs(ours100 - mkt) : Math.max(...active) - Math.min(...active);
              if (spread <= 6) {{ badgeText = "Strong Agreement"; badgeClass = "tag-accent"; }}
              else if (spread <= 12) {{ badgeText = "Mostly Aligned"; badgeClass = "tag-teal"; }}
              else {{ badgeText = "Opinions Differ"; badgeClass = "tag-caution"; }}
            }}

            const kpiOdds = document.getElementById("kpiOdds");
            const kpiOddsLbl = document.getElementById("kpiOddsLbl");
            const kpiOddsCard = document.getElementById("kpiOddsCard");
            if (kpiOdds && odds != null) kpiOdds.textContent = `${{odds}}%`;
            if (kpiOddsLbl) {{
              kpiOddsLbl.textContent = firstHand
                ? "Uncharted Verified"
                : active.length >= 2
                ? `StayOdds • ${{active.length}} Sources`
                : "StayOdds • 1 Source (Google)";
            }}
            if (kpiOddsCard) kpiOddsCard.classList.toggle("is-caution", badgeClass === "tag-caution");

            const glanceScoreEl = document.getElementById("glanceScoreBasis");
            if (glanceScoreEl && odds != null) {{
              glanceScoreEl.innerHTML = `<strong>${{odds}}% StayOdds</strong> — ${{formula}}`;
            }}

            const heroBadge = document.getElementById("heroStatusBadge");
            const gapBadge = document.getElementById("gapStatusBadge");
            [heroBadge, gapBadge].forEach((el) => {{
              if (!el) return;
              el.textContent = badgeText;
              el.className = `tag ${{badgeClass}}`;
            }});

            const rhs = firstHand ? mkt : g100;
            if (left100 != null && rhs != null) {{
              const d = left100 - rhs;
              if (pill) pill.innerHTML = `<strong>${{d > 0 ? "+" + d : d}} pts</strong><span>${{firstHand ? "Uncharted vs Consensus" : "Opinion Gap"}}</span>`;
              const gapHead = document.getElementById("gapHeadline");
              if (gapHead) {{
                if (Math.abs(d) <= 5) {{
                  gapHead.textContent = firstHand
                    ? `Tight agreement (${{d >= 0 ? "+" + d : d}} pts) — The Uncharted Itinerary stay matched the wider consensus.`
                    : `Tight agreement (${{d >= 0 ? "+" + d : d}} pts) — ${{criticLabel}} and real guests agree.`;
                }} else if (d > 5) {{
                  gapHead.textContent = firstHand
                    ? `The Uncharted Itinerary rated this +${{d}} pts higher than the wider consensus — see what stood out.`
                    : `${{criticLabel}} rated this +${{d}} pts higher than real guests.`;
                }} else {{
                  gapHead.textContent = firstHand
                    ? `The Uncharted Itinerary rated this ${{d}} pts stricter than the wider consensus — see what held it back.`
                    : `Real guests rated this +${{Math.abs(d)}} pts higher than ${{criticLabel}}.`;
                }}
              }}
            }}

            const eqEl = document.getElementById("stayOddsEquation");
            if (eqEl && odds != null) {{
              eqEl.textContent = firstHand && ours100 != null
                ? `70% Uncharted Stay (${{personalLabel ? personalLabel + " → " : ""}}${{ours100}}%) + 30% Consensus (${{mkt}}%) = ${{odds}}% StayOdds`
                : `${{formula}} = ${{odds}}% StayOdds`;
            }}

            const wSub = document.getElementById("weightFormulaSub");
            const wFhEl = document.getElementById("weightFirstHandPct");
            const wCrEl = document.getElementById("weightCriticsPct");
            const wGuEl = document.getElementById("weightGuestsPct");
            const wGuVal = document.getElementById("weightGuestVal");
            if (wSub) wSub.textContent = formula;
            if (wFhEl) wFhEl.textContent = `${{wFH}}%`;
            if (wCrEl) wCrEl.textContent = `${{wCr}}%`;
            if (wGuEl) wGuEl.textContent = `${{wGu}}%`;
            if (wGuVal) wGuVal.textContent = `${{g.rating.toFixed(1)}}★ → ${{g100}}%`;

            if (shareCardState && shareCardState.odds) {{
              shareCardState.odds.greatStayOdds = odds;
              shareCardState.odds.statusBadge = badgeText;
              shareCardState.odds.verifiedGuest = {{ rating: g.rating, scale: 5 }};
            }}
          }}
        }})
        .catch(() => showMapsFallback(mapsFallbackUrl));
    }} else {{
      showMapsFallback("");
    }}

    const shareCardState = {json.dumps(share_card_payload, ensure_ascii=False)};
    document.getElementById("shareHotelCardBtn")?.addEventListener("click", async () => {{
      const mod = await import("../../assets/stayodds-share-card.js?v=11");
      mod.openSingleHotelShareModal(shareCardState.hotel, shareCardState.odds);
      if (typeof window.trackEvent === "function") {{
        window.trackEvent("open_share_card", "single_hotel", shareCardState.hotel.name);
      }}
    }});
  </script>
</body>
</html>
"""


DESTINATION_GUIDES: list[dict[str, str]] = [
    {
        "slug": "maldives",
        "title": "Maldives",
        "headline": "Best Luxury Resorts in the Maldives — StayOdds Guide",
        "lead": "Compare Maldives overwater & beachfront luxury resorts side-by-side with our first-hand stays, sourced editorial critics, official MICHELIN Key & Forbes Five-Star awards, and verified guest scores.",
        "filterType": "country",
        "filterValue": "Maldives",
        "banner": "maldives.jpg",
        "compareRegion": "Maldives & Indian Ocean",
    },
    {
        "slug": "bali-indonesia",
        "title": "Bali & Indonesia",
        "headline": "Best Luxury Resorts in Bali & Indonesia — StayOdds Guide",
        "lead": "Explore personally curated luxury resorts across Uluwatu, Nusa Dua, Canggu, Ubud, Sumba, and Labuan Bajo — combining first-hand stays, sourced press reviews, and official awards.",
        "filterType": "country",
        "filterValue": "Indonesia",
        "banner": "bali.jpg",
        "compareRegion": "Asia",
    },
    {
        "slug": "europe",
        "title": "Europe",
        "headline": "Best Luxury Hotels in Europe — StayOdds Guide",
        "lead": "Compare Europe's most acclaimed grand dames, coastal resorts, and countryside estates — with transparent first-hand stays, linked newspaper & magazine reviews, and official awards.",
        "filterType": "region",
        "filterValue": "Europe",
        "banner": "seychelles.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "mexico",
        "title": "Mexico",
        "headline": "Best Luxury Resorts in Mexico — StayOdds Guide",
        "lead": "Compare Riviera Maya, Los Cabos, Punta Mita, Costalegre, San Miguel de Allende, and Mexico City luxury resorts side-by-side — including swimmable beaches, sargassum notes, all-inclusive vs. à la carte differences, and verified editorial links.",
        "filterType": "country",
        "filterValue": "Mexico",
        "banner": "bora-bora.jpg",
        "compareRegion": "Caribbean & Mexico",
    },
    {
        "slug": "caribbean",
        "title": "Caribbean",
        "headline": "Best Luxury Resorts in the Caribbean — StayOdds Guide",
        "lead": "Compare flagship luxury resorts across every Caribbean island & territory — from Anguilla, St. Barths, Turks & Caicos, and St. Lucia to Barbados, Jamaica, Cayman Islands, Aruba, Curaçao, Dominica, Grenada, and private BVI cays.",
        "filterType": "region_except_country",
        "filterValue": "Caribbean & Mexico|Mexico",
        "banner": "seychelles.jpg",
        "compareRegion": "Caribbean & Mexico",
    },
    {
        "slug": "americas",
        "title": "Americas",
        "headline": "Best Luxury Hotels in the Americas — StayOdds Guide",
        "lead": "From California, Hawaii, and New York icons to Costa Rica, Belize, Panama, Canada, and South American sanctuaries — every StayOdds profile links directly to verified editorial reviews and official awards.",
        "filterType": "region",
        "filterValue": "Americas",
        "banner": "bora-bora.jpg",
        "compareRegion": "Americas",
    },
    {
        "slug": "asia",
        "title": "Asia",
        "headline": "Best Luxury Hotels in Asia — StayOdds Guide",
        "lead": "Compare flagship urban sanctuaries and island escapes across Japan, Indonesia, Thailand, Singapore, Hong Kong, Vietnam, India, and beyond with verified StayOdds data.",
        "filterType": "region",
        "filterValue": "Asia",
        "banner": "bali.jpg",
        "compareRegion": "Asia",
    },
    {
        "slug": "middle-east",
        "title": "Middle East",
        "headline": "Best Luxury Hotels in the Middle East — StayOdds Guide",
        "lead": "Compare Dubai, Abu Dhabi, Doha, Oman, and Red Sea luxury resorts with verified awards, linked press reviews, and transparent StayOdds ratings.",
        "filterType": "region",
        "filterValue": "Middle East",
        "banner": "maldives.jpg",
        "compareRegion": "Middle East",
    },
    {
        "slug": "thailand",
        "title": "Thailand",
        "headline": "Best Luxury Resorts in Thailand — StayOdds Guide",
        "lead": "Explore curated luxury resorts across Krabi, Phuket, Koh Samui, Bangkok, and Chiang Mai — including first-hand filmed reviews and verified critic links.",
        "filterType": "country",
        "filterValue": "Thailand",
        "banner": "bali.jpg",
        "compareRegion": "Asia",
    },
    {
        "slug": "indian-ocean-africa",
        "title": "Indian Ocean & Africa",
        "headline": "Best Luxury Resorts in the Indian Ocean & Africa — StayOdds Guide",
        "lead": "Compare luxury island sanctuaries in Maldives, Seychelles, and Mauritius alongside iconic African safari lodges and city hotels — every source linked and verified.",
        "filterType": "regions",
        "filterValue": "Maldives & Indian Ocean|Africa",
        "banner": "seychelles.jpg",
        "compareRegion": "Africa",
    },
    {
        "slug": "bora-bora",
        "title": "Bora Bora",
        "headline": "Best Luxury Resorts in Bora Bora — StayOdds Guide",
        "lead": "Compare Bora Bora's iconic overwater lagoon resorts side-by-side with sourced press reviews, official awards, and direct rate links.",
        "filterType": "country",
        "filterValue": "French Polynesia",
        "banner": "bora-bora.jpg",
        "compareRegion": "Australia & Pacific",
    },
    {
        "slug": "italy",
        "title": "Italy",
        "headline": "Best Luxury Hotels in Italy — StayOdds Guide",
        "lead": "Compare Italy's celebrated luxury stays across Rome, Sardinia, Lake Como, Amalfi, Florence, Puglia, and Venice — combining first-hand stays, linked press reviews, and official awards.",
        "filterType": "country",
        "filterValue": "Italy",
        "banner": "seychelles.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "japan",
        "title": "Japan",
        "headline": "Best Luxury Hotels in Japan — StayOdds Guide",
        "lead": "Compare Japan's finest luxury hotels and independent ryokans across Tokyo, Kyoto, Osaka, Hokkaido, Hakone, Mount Fuji, Karuizawa, Naoshima, Kyushu, and Okinawa with verified awards and guest scores.",
        "filterType": "country",
        "filterValue": "Japan",
        "banner": "bali.jpg",
        "compareRegion": "Asia",
    },
    {
        "slug": "united-kingdom",
        "title": "United Kingdom",
        "headline": "Best Luxury Hotels in the United Kingdom — StayOdds Guide",
        "lead": "Compare London grand dames and British countryside retreats — including first-hand reviews, verified newspaper critiques, and MICHELIN Key honorees.",
        "filterType": "country",
        "filterValue": "United Kingdom",
        "banner": "seychelles.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "france",
        "title": "France",
        "headline": "Best Luxury Hotels in France — StayOdds Guide",
        "lead": "Compare Palace-distinction Parisian icons and Riviera retreats with verified official awards and linked editorial critiques.",
        "filterType": "country",
        "filterValue": "France",
        "banner": "bora-bora.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "australia-new-zealand",
        "title": "Australia & New Zealand",
        "headline": "Best Luxury Hotels & Lodges in Australia & New Zealand — StayOdds Guide",
        "lead": "Compare flagship luxury lodges and city icons across Sydney, Melbourne, Tasmania, Uluru, Kangaroo Island, the Great Barrier Reef, Queenstown, Bay of Islands, and Fiordland.",
        "filterType": "countries",
        "filterValue": "Australia|New Zealand",
        "banner": "seychelles.jpg",
        "compareRegion": "Australia & Pacific",
    },
    {
        "slug": "greece",
        "title": "Greece",
        "headline": "Best Luxury Resorts in Greece — StayOdds Guide",
        "lead": "Compare iconic Greek luxury resorts across Santorini, Mykonos, Athens Riviera, Peloponnese, Crete, Paros, and Milos with transparent StayOdds ratings and official awards.",
        "filterType": "country",
        "filterValue": "Greece",
        "banner": "maldives.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "turkey",
        "title": "Turkey",
        "headline": "Best Luxury Hotels in Turkey — StayOdds Guide",
        "lead": "Compare Istanbul Bosphorus palaces, Bodrum peninsula resorts, and Cappadocia cave sanctuaries with verified StayOdds guest scores and awards.",
        "filterType": "country",
        "filterValue": "Turkey",
        "banner": "bora-bora.jpg",
        "compareRegion": "Europe",
    },
    {
        "slug": "egypt",
        "title": "Egypt",
        "headline": "Best Luxury Hotels in Egypt — StayOdds Guide",
        "lead": "Compare Cairo Nile icons, Giza pyramid-view landmarks, historic Luxor and Aswan grand hotels, and Red Sea luxury escapes with verified StayOdds data.",
        "filterType": "country",
        "filterValue": "Egypt",
        "banner": "maldives.jpg",
        "compareRegion": "Africa",
    },
    {
        "slug": "canary-islands",
        "title": "Canary Islands",
        "headline": "Best Hotels & Resorts in the Canary Islands — StayOdds Guide",
        "lead": "Compare verified hotels across Tenerife, Lanzarote, Gran Canaria, Fuerteventura, La Gomera, and La Palma — from 5-star luxury and loyalty chains to top-rated family-friendly, adults-only, and great-value all-inclusive resorts.",
        "filterType": "location_regex",
        "filterValue": "tenerife|lanzarote|gran canaria|fuerteventura|la gomera|la palma",
        "banner": "seychelles.jpg",
        "compareRegion": "Europe",
    },
]


def render_destination_page(
    guide: dict[str, str],
    dest_hotels: list[dict[str, Any]],
    all_guides: list[dict[str, str]],
) -> str:
    slug = guide["slug"]
    title = guide["title"]
    canonical = f"{SITE_URL}/destinations/{slug}/"
    page_title = f"{guide['headline']} | StayOdds by The Uncharted Itinerary"
    meta_desc = f"Compare {len(dest_hotels)} curated luxury hotels in {title} on StayOdds — first-hand verified stays, official awards, linked newspaper & magazine reviews, and transparent ratings."
    banner_file = guide["banner"]
    banner_abs = f"{SITE_URL}/assets/banners/{banner_file}"
    compare_q = urllib.parse.quote(guide["compareRegion"])

    fh_count = sum(1 for h in dest_hotels if h.get("tier") == "first_hand_verified")
    award_count = sum(1 for h in dest_hotels if h.get("officialAwards"))
    press_count = sum(len(h.get("editorialRatings") or []) for h in dest_hotels)

    # ItemList structured data strictly using real curated properties
    item_list_ld = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": guide["headline"],
        "description": meta_desc,
        "url": canonical,
        "numberOfItems": len(dest_hotels),
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": idx + 1,
                "name": h["name"],
                "url": f"{SITE_URL}/stayodds/{h['id']}/",
            }
            for idx, h in enumerate(dest_hotels)
        ],
    }

    dest_nav_pills = "".join(
        f'<a class="dest-nav-pill {"is-active" if g["slug"] == slug else ""}" href="../{esc(g["slug"])}/">{esc(g["title"])}</a>'
        for g in all_guides
    )

    cards_parts: list[str] = []
    for idx, h in enumerate(dest_hotels):
        o = compute_stayodds_py(h)
        raw_thumb = h.get("thumbnail") or "assets/placeholders/default-stayodds.webp"
        thumb_src = raw_thumb if raw_thumb.startswith(("http://", "https://")) else f"../../{raw_thumb.lstrip('/')}?v=169"
        odds_val = f"{o['greatStayOdds']}%" if o["greatStayOdds"] is not None else ("Award" if o["awards"] else "Open")
        odds_lbl = "StayOdds" if o["greatStayOdds"] is not None else ("Official Award" if o["awards"] else "Breakdown")

        award_badges = "".join(
            f'<a class="source-chip" href="{esc(a["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{ICO_TROPHY} {esc(a["label"])} &nearr;</a>'
            for a in o["awards"][:2]
        )
        press_badges = "".join(
            f'<a class="source-chip" href="{esc(e["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{ICO_LINK} {esc(e["sourceName"])} &nearr;</a>'
            for e in o["editorial"][:2]
        )
        blurb = h.get("standout") or h.get("verdict") or ""
        if len(blurb) > 190:
            blurb = blurb[:187].rsplit(" ", 1)[0] + "…"

        cards_parts.append(
            f"""
        <article class="dest-card" data-resort-name="{esc(h['name'])}">
          <div class="dest-card-media-wrap">
            <a class="dest-card-media" href="../../stayodds/{esc(h['id'])}/">
              <img src="{esc(thumb_src)}" alt="{esc(h['name'])}" loading="lazy" decoding="async" />
              <span class="dest-card-rank">#{idx + 1}</span>
              <span class="dest-card-odds"><strong>{esc(odds_val)}</strong><small>{esc(odds_lbl)}</small></span>
            </a>
            {yt_overlay(h)}
            <button type="button" class="card-heart-fab shortlist-btn" data-shortlist-id="{esc(h['id'])}" data-shortlist-icon-only="1" data-resort-name="{esc(h['name'])}" aria-label="Save {esc(h['name'])} to shortlist" aria-pressed="false" title="Save to shortlist">&#9825;</button>
          </div>
          <div class="dest-card-body">
            <div class="meta-line">
              <span class="tag {'tag-accent' if o['firstHand'] else 'tag-slate'}">{esc(o['scoreTrackLabel'])}</span>
              {f'<span class="tag">{esc(h["brand"])}</span>' if h.get("brand") else ""}
            </div>
            <h3><a href="../../stayodds/{esc(h['id'])}/">{esc(h['name'])}</a></h3>
            <div class="dest-card-loc">{esc(h['location'])}, {esc(h['country'])}{f" &bull; {esc(h['priceRange'])}" if h.get("priceRange") else ""}</div>
            {f'<p class="dest-card-blurb">{esc(blurb)}</p>' if blurb else ""}
            {f'<div class="dest-card-sources">{award_badges}{press_badges}</div>' if (award_badges or press_badges) else ""}
            <div class="dest-card-actions">
              <a class="btn btn-primary" href="../../stayodds/{esc(h['id'])}/">Full Breakdown &rarr;</a>
              <a class="btn btn-outline" href="../../compare/?a={esc(h['id'])}">Compare VS</a>
              <button type="button" class="btn btn-outline shortlist-btn" data-shortlist-id="{esc(h['id'])}" data-shortlist-compact="1" data-resort-name="{esc(h['name'])}" aria-pressed="false">&#9825; Save</button>
              <a class="btn btn-primary check-prices-btn" style="background:#16a34a;border-color:#16a34a;color:#fff;font-weight:700" href="{esc(h['bookingUrl'])}" target="_blank" rel="sponsored noopener noreferrer">Check prices{(" · from £" + format(int((h.get("priceSnapshot") or {}).get("nightlyGbp")), ",")) if (h.get("priceSnapshot") or {}).get("nightlyGbp") else ""} &nearr;</a>
            </div>
          </div>
        </article>"""
        )

    cards_html = "\n".join(cards_parts)

    # Build up to 3 genuinely comparable Head-to-Head Rival Matchups + cohesive 3-hotel trio
    dest_odds_map = {h["id"]: compute_stayodds_py(h) for h in dest_hotels}
    matched_pairs, trio = pick_destination_matchups(dest_hotels, dest_odds_map, limit=3)
    dest_matchup_cards: list[str] = []
    for ha, hb in matched_pairs:
        oa, ob = dest_odds_map[ha["id"]], dest_odds_map[hb["id"]]
        sa = f"{oa['greatStayOdds']}%" if oa["greatStayOdds"] is not None else oa["tierLabel"]
        sb = f"{ob['greatStayOdds']}%" if ob["greatStayOdds"] is not None else ob["tierLabel"]
        dest_matchup_cards.append(
            f'<a class="rival-matchup-card" href="../../compare/?a={esc(ha["id"])}&amp;b={esc(hb["id"])}">'
            f'<div class="rival-matchup-vs">{esc(ha["name"])} <span style="color:var(--accent);">vs</span> {esc(hb["name"])}</div>'
            f'<div class="rival-matchup-meta"><span>{esc(sa)} vs {esc(sb)}</span><span class="rival-matchup-cta">Compare &rarr;</span></div>'
            f'</a>'
        )
    dest_three_link = ""
    if len(trio) >= 3:
        dest_three_link = (
            f'<a class="btn btn-outline" style="font-size:12.5px;padding:7px 12px;" '
            f'href="../../compare/?a={esc(trio[0]["id"])}&amp;b={esc(trio[1]["id"])}&amp;c={esc(trio[2]["id"])}">'
            f'Compare Top 3 Side-by-Side &rarr;</a>'
        )
    dest_matchups_html = (
        f'<div class="rival-matchups-box">'
        f'<div class="rival-matchups-head"><h3>Popular Head-to-Head Rival Matchups in {esc(title)}</h3>{dest_three_link}</div>'
        f'<div class="rival-matchups-grid">{"".join(dest_matchup_cards)}</div>'
        f'</div>'
        if dest_matchup_cards
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light only" />
  <link rel="icon" type="image/svg+xml" href="../../assets/stayodds-favicon.svg?v=3" />
  <link rel="icon" type="image/png" sizes="32x32" href="../../assets/stayodds-favicon-32.png?v=3" />
  <link rel="shortcut icon" href="../../favicon.ico?v=3" />
  <link rel="apple-touch-icon" sizes="180x180" href="../../assets/stayodds-apple-touch-icon.png?v=3" />
  <meta name="google-adsense-account" content="ca-pub-4618281487216833" />
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-4618281487216833" crossorigin="anonymous"></script>
  <title>{esc(page_title)}</title>
  <meta name="description" content="{esc(meta_desc)}" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:type" content="website" />
  <meta property="og:title" content="{esc(page_title)}" />
  <meta property="og:description" content="{esc(meta_desc)}" />
  <meta property="og:image" content="{esc(banner_abs)}" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{esc(page_title)}" />
  <meta name="twitter:description" content="{esc(meta_desc)}" />
  <meta name="twitter:image" content="{esc(banner_abs)}" />
  <script type="application/ld+json">{json.dumps(item_list_ld, ensure_ascii=False)}</script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" media="print" onload="this.media='all'" />
  <noscript><link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet" /></noscript>
  <script>if(window.self!==window.top||location.search.includes("embed=1"))document.documentElement.classList.add("is-embedded");</script>
  <style>.site-header{{background:#071323!important;}}html.is-embedded .site-header,html.is-embedded .site-footer,html.is-embedded .hub-back-link{{display:none!important;}}</style>
  <link rel="stylesheet" href="../../assets/styles.min.css?v=47" />
  <script data-goatcounter="https://stayodds.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <script type="text/javascript">
      (function(c,l,a,r,i,t,y){{
          c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments)}};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
      }})(window, document, "clarity", "script", "zhmuw1amoy");
  </script>
  <script nowprocket data-noptimize="1" data-cfasync="false" data-wpfc-render="false" seraph-accel-crit="1" data-no-defer="1" data-cmp-ab="2">
    (function () {{
        var script = document.createElement("script");
        script.async = 1;
        script.setAttribute("data-cmp-ab","2");
        script.src = 'https://emrld.ltd/NjA0NzQ3.js?t=604747';
        document.head.appendChild(script);
    }})();
  </script>
</head>
<body class="stayodds-warm-canvas">
{chrome_header("../../")}

  <main class="has-top-band">
    <div class="detail-top-band" aria-hidden="true"></div>
    <section class="page-intro">
      <div class="container">
        <div class="detail-breadcrumb" style="margin-bottom:14px;">
          <a href="../../compare/">&larr; All StayOdds Hotels</a>
          <span>/</span>
          <span>Destinations</span>
          <span>/</span>
          <strong>{esc(title)}</strong>
        </div>

        <div class="hero-banner-card" style="--hero-bg: url('../../assets/banners/{esc(banner_file)}');">
          <div class="intro-row">
            <div class="hero-title-group">
              <img class="hero-emblem" src="../../assets/stayodds-logo.png?v=3" alt="StayOdds." width="60" height="60" style="border-radius:14px;" />
              <div>
                <h1 class="page-title">{esc(guide['headline'])}</h1>
                <p class="page-lead">{esc(guide['lead'])}</p>
              </div>
            </div>
            <div class="sync-meta">
              <span>{len(dest_hotels)} Curated Properties</span>
              <strong>{fh_count} First-Hand Verified &bull; {award_count} Awarded</strong>
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">
                <a class="btn btn-outline" href="../../compare/?region={compare_q}" style="background:#fff;color:#111;border-color:#fff;font-size:12.5px;padding:6px 12px;">Interactive Compare &rarr;</a>
                <a class="btn btn-outline" href="../../hotels/?region={compare_q}" style="background:rgba(255,255,255,0.14);color:#fff;border-color:rgba(255,255,255,0.35);font-size:12.5px;padding:6px 12px;">View on Map &rarr;</a>
              </div>
            </div>
          </div>
        </div>

        <div class="dest-stats-row">
          <div class="dest-stat-pill"><strong>{len(dest_hotels)}</strong><span>Curated Luxury Stays</span></div>
          <div class="dest-stat-pill"><strong>{fh_count}</strong><span>First-Hand Verified</span></div>
          <div class="dest-stat-pill"><strong>{award_count}</strong><span>Official Award Honorees</span></div>
          <div class="dest-stat-pill"><strong>{press_count}</strong><span>Linked Press &amp; Critic Reviews</span></div>
        </div>

        <nav class="dest-pills-bar" aria-label="Browse StayOdds Destination Guides">
          {dest_nav_pills}
        </nav>
      </div>
    </section>

    <section class="dest-list-section">
      <div class="container">
        <div class="section-header" style="margin-bottom:18px;flex-wrap:wrap;gap:12px;">
          <div>
            <h2 class="section-title">{esc(title)} Luxury Hotel Directory ({len(dest_hotels)})</h2>
            <p class="section-subtitle">Ordered with First-Hand Verified stays first, followed by highest verified guest scores. Save favourites to your zero-login Shortlist or jump into Head-to-Head Compare.</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
            <a class="btn btn-outline" href="../../compare/?scope=saved">&#9829; Open My Shortlist</a>
            <button type="button" class="so-request-btn" data-open-resort-request>+ Request a Resort</button>
          </div>
        </div>

        {dest_matchups_html}

        <div class="dest-grid">
          {cards_html}
        </div>
      </div>
    </section>
{chrome_partner_strip("../../")}  </main>

  <footer class="site-footer">
    <div class="container">
      <div class="footer-grid">
        <div>
          <div class="footer-brand"><span class="stayodds-wordmark">StayOdds<span class="stayodds-dot">.</span></span> &bull; by The Uncharted Itinerary</div>
          <p class="footer-muted">Critics vs Real Guest Reviews — personally curated luxury hotel comparisons with verified sources.</p>
        </div>
        <div class="footer-links">
          <a href="../../compare/">StayOdds Directory</a>
          <a href="../../hotels/">Hotel Map</a>
          <a href="../../">Videos</a>
          <a href="../../links/">Deals &amp; Gear</a>
          <a href="../../about/">About</a>
          <a href="../../faq/">FAQ</a>
          <a href="../../contact/">Contact</a>
          <a href="../../privacy/">Privacy Policy</a>
          <button type="button" class="so-request-footer-link" data-open-resort-request>+ Request a Resort</button>
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; {datetime.now().year} StayOdds &amp; The Uncharted Itinerary</span>
        <span>Disclosure: Booking &amp; gear links may earn an affiliate commission at no extra cost to you (<a href="../../privacy/" style="color:inherit;text-decoration:underline;">Privacy &amp; Ad Disclosure</a>).</span>
      </div>
    </div>
  </footer>

  <script src="../../assets/stayodds-feedback.js?v=4" defer></script>
  <script src="../../assets/stayodds-video.js?v=2" defer></script>
</body>
</html>
"""


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_key = os.environ["SUPABASE_SECRET_KEY"]

    props = sb_get_all(sb_url, sb_key, "properties")
    facts = {r["property_id"]: r for r in sb_get_all(sb_url, sb_key, "property_facts")}
    fh_map = {r["property_id"]: r for r in sb_get_all(sb_url, sb_key, "first_hand_reviews")}
    guest_map: dict[str, dict[str, Any]] = {}
    for r in sb_get_all(sb_url, sb_key, "licensed_guest_scores"):
        if r.get("partner_source") in ("tripadvisor", "google"):
            continue  # added from the saved data files in combined_guest_score()
        n = r.get("review_count")
        if (n is not None and int(n) < MIN_GUEST_REVIEWS) or (n is None and r.get("partner_source") == "nuitee_connect"):
            continue  # too few reviews to be a reliable guest score: leave it off
        guest_map[r["property_id"]] = r

    awards_map: dict[str, list[dict[str, Any]]] = {}
    for r in sb_get_all(sb_url, sb_key, "official_awards"):
        awards_map.setdefault(r["property_id"], []).append(
            {
                "awardBody": r.get("award_body", ""),
                "label": r["label"],
                "year": r.get("award_year", ""),
                "normalized100": r.get("normalized_100"),
                "sourceUrl": r["source_url"],
            }
        )

    ed_map: dict[str, list[dict[str, Any]]] = {}
    for r in sb_get_all(sb_url, sb_key, "editorial_ratings"):
        ed_map.setdefault(r["property_id"], []).append(
            {
                "sourceName": r["source_name"],
                "sourceUrl": r["source_url"],
                "rawScore": r.get("raw_score", ""),
                "normalized100": r["normalized_100"],
                "takeaway": r.get("takeaway", ""),
            }
        )

    yt_map: dict[str, list[dict[str, Any]]] = {}
    for r in sb_get_all(sb_url, sb_key, "youtube_reviews"):
        yt_map.setdefault(r["property_id"], []).append(
            {
                "creatorName": r["creator_name"],
                "sourceUrl": r["source_url"],
                "sentiment": r.get("sentiment", "Review"),
                "takeaway": r.get("takeaway", ""),
            }
        )

    bk_map: dict[str, list[dict[str, Any]]] = {}
    for r in sb_get_all(sb_url, sb_key, "booking_links"):
        bk_map.setdefault(r["property_id"], []).append(
            {
                "channelType": r["channel_type"],
                "partnerName": r["partner_name"],
                "url": r["url"],
                "mobileAllowed": bool(r.get("mobile_allowed", True)),
                "perksSummary": r.get("perks_summary", ""),
                "priority": r.get("priority", 1),
            }
        )

    # hand corrections (data/property-corrections.json) win over the database, so a fix shows even before it is written back
    corr = _load_json("property-corrections.json") or {}
    visited_src = {h["id"]: h for h in (_load_json("hotels.json") or {}).get("hotels", [])}

    def _corr(table: str, row: dict[str, Any] | None, pid: str) -> dict[str, Any] | None:
        fields = (corr.get(table) or {}).get(pid)
        if not fields or row is None:
            return row
        return {**row, **{k: (visited_src.get(pid, {}).get(k) if v == "from data/hotels.json" else v) for k, v in fields.items()}}

    # a LiteAPI id set to null here was another hotel's: drop everything that came from it until a correct id is found
    wrong_lite = {k for k, v in (corr.get("properties") or {}).items() if "nuitee_hotel_id" in v and not v["nuitee_hotel_id"]}
    guest_map = {k: v for k, v in guest_map.items() if not (k in wrong_lite and v.get("partner_source") == "nuitee_connect")}
    props = [_corr("properties", p, p["id"]) for p in props]
    facts = {k: _corr("property_facts", v, k) for k, v in facts.items()}
    fh_map = {k: _corr("first_hand_reviews", v, k) for k, v in fh_map.items()}

    directory: list[dict[str, Any]] = []
    for p in props:
        pid = p["id"]
        f = facts.get(pid) or {}
        fh = fh_map.get(pid)
        gs = guest_map.get(pid)
        bks = sorted(bk_map.get(pid) or [], key=lambda x: x.get("priority", 1))
        web_booking = next((b["url"] for b in bks if b["channelType"] == "ota_affiliate"), "") or (
            bks[0]["url"] if bks else ""
        )
        _mlink = marriott_affiliate_link(pid, p.get("name") or "", p.get("city") or p.get("location") or "", p.get("brand") or p.get("brand_name") or "")
        if _mlink:
            web_booking = _mlink
            bks = [{"channelType": "direct_brand", "partnerName": "Marriott.com", "url": _mlink, "mobileAllowed": True,
                    "perksSummary": "Book direct: Marriott Bonvoy points and member rates", "priority": 0}] + [
                b for b in bks if b.get("partnerName") != "Marriott.com"]

        rated = bool(fh and fh.get("overall_score") is not None)
        scores = (
            {
                "rooms": fh["rooms_score"],
                "grounds": fh["grounds_score"],
                "food": fh["food_score"],
                "service": fh["service_score"],
                "value": fh["value_score"],
            }
            if rated
            else None
        )

        local_thumb = ROOT / "assets" / "thumbs" / f"{pid}.webp"
        local_ph = ROOT / "assets" / "placeholders" / f"{pid}.webp"
        raw_hero = (p.get("hero_image_url") or "").strip()
        is_blocked = any(bad in raw_hero for bad in ("www.fourseasons.com", "www.lungarnocollection.com"))
        is_self_hosted_ph = f"/assets/placeholders/{pid}.webp" in raw_hero
        card_photo = ROOT / "assets" / "card-photos" / f"{pid}.webp"
        if card_photo.exists() and card_photo.stat().st_size > 1500:
            # Clean hotel photo (no YouTube thumbnail text/faces). Video is flagged with a badge + in-page player.
            resolved_thumb = f"assets/card-photos/{pid}.webp"
        elif local_thumb.exists() and local_thumb.stat().st_size > 1500:
            resolved_thumb = f"assets/thumbs/{pid}.webp"
        elif (not raw_hero or is_blocked or is_self_hosted_ph) and local_ph.exists() and local_ph.stat().st_size > 1500:
            resolved_thumb = f"assets/placeholders/{pid}.webp"
        elif raw_hero and not is_blocked:
            resolved_thumb = raw_hero
        else:
            resolved_thumb = "assets/placeholders/default-stayodds.webp"

        price_snap_path = ROOT / "data" / "price-snapshots.json"
        if "_price_snaps_loaded" not in globals():
            globals()["_price_snaps_loaded"] = (
                json.loads(price_snap_path.read_text(encoding="utf-8")).get("prices", {})
                if price_snap_path.exists()
                else {}
            )
        price_snap = None if pid in wrong_lite else globals()["_price_snaps_loaded"].get(pid)

        rec = {
            "id": pid,
            "name": p["name"],
            "location": p["city"],
            "country": p["country"],
            "region": p["region"],
            "lat": p.get("lat"),
            "lng": p.get("lng"),
            "brand": p.get("brand", ""),
            "priceRange": p.get("price_tier", ""),
            "priceSnapshot": price_snap,
            "tier": p["tier"],
            "visitedByUs": bool(p.get("visited_by_founder")),
            "coverageType": fh["coverage_type"] if fh else "Global Directory",
            "googlePlaceId": p.get("google_place_id"),
            "nuiteeHotelId": p.get("nuitee_hotel_id"),
            "thumbnail": resolved_thumb,
            "photoCredit": _photo_credit(p.get("image_license_source"), resolved_thumb),
            "videoId": fh.get("youtube_video_id", "") if fh else "",
            "inLiveFeed": bool(fh.get("in_live_feed")) if fh else False,
            "reviewedDate": fh.get("reviewed_date") if fh else None,
            "scores": scores,
            "overall": fh.get("overall_score") if rated else None,
            "verdict": fh.get("verdict", "") if fh else "",
            "whereWeDiffer": fh.get("where_we_differ", "") if fh else "",
            "shorts": fh.get("shorts", []) if fh else [],
            "standout": f.get("standout", ""),
            "watchOut": f.get("watch_out", ""),
            "keyFacts": {
                "poolHeating": f.get("pool_heating", ""),
                "beachOrReef": f.get("beach_or_reef", ""),
                "renovationYear": f.get("renovation_year"),
                "transferLogistics": f.get("transfer_logistics", ""),
            },
            "propertyStatus": (
                {
                    "operatingStatus": f.get("operating_status") or "",
                    "renovationsExtensions": f.get("renovations_extensions") or "",
                    "nearbyConstruction": f.get("nearby_construction") or "",
                    "sourceUrl": f.get("status_source_url") or "",
                    "sourceNote": f.get("status_source_note") or "",
                    "verifiedAt": f.get("status_verified_at") or "",
                }
                if (
                    f.get("operating_status")
                    or f.get("renovations_extensions")
                    or f.get("nearby_construction")
                )
                else None
            ),
            "redFlags": f.get("red_flag_tags") or [],
            "bookingUrl": web_booking,
            "bookingLinks": bks,
            "verifiedGuest": combined_guest_score(gs, TRIPADVISOR.get(pid), GOOGLE_RATINGS.get(pid)),
            "editorialRatings": ed_map.get(pid) or [],
            "youtubeReviews": yt_map.get(pid) or [],
            "officialAwards": awards_map.get(pid) or [],
            "guestQuotes": None if pid in wrong_lite else GUEST_QUOTES.get(pid),
            "water": None if pid in wrong_lite else water_summary((GUEST_QUOTES.get(pid) or {}).get("waterMentions")),
            "itwf": ITWF.get(pid),
            "dining": ([r for r in ((DINING.get(pid) or {}).get("restaurants") or []) if r.get("distinction") != "MICHELIN Guide selected"][:3]
                       or [{"name": m.group(1).strip(), "distinction": f"{m.group(2)} MICHELIN Star{'s' if m.group(2) != '1' else ''}", "url": (ITWF.get(pid) or {}).get("url", "")}
                           for a in ((ITWF.get(pid) or {}).get("award") or []) for m in [re.match(r"(.+?):\s*(\d) Michelin Stars?", a)] if m][:3] or None),
            "communityMentions": COMMUNITY.get(pid) or [],
            "tripadvisor": TRIPADVISOR.get(pid),
        }
        directory.append(rec)

    # Sort: First-Hand Scored first, then Filmed Full Reviews, then Short Tours, then Global Directory by score desc
    def sort_key(r: dict[str, Any]) -> tuple[int, int, str]:
        if r.get("scores") and r.get("overall") is not None:
            tier_rank = 0
        elif r.get("visitedByUs") and r.get("coverageType") != "Short Tour":
            tier_rank = 1
        elif r.get("visitedByUs"):
            tier_rank = 2
        else:
            tier_rank = 3
        g_score = -int(((r.get("verifiedGuest") or {}).get("licensed") or {}).get("normalized100") or 0)
        return (tier_rank, g_score, r["name"])

    directory.sort(key=sort_key)

    # Hide live/indicative prices we can't trust (lookalike LiteAPI matches, duplicate ids, hotels not sold
    # through Booking.com). Rules live in scripts/live_rate_policy.py + data/live-rate-coverage.json.
    live_decisions = apply_live_rate_policy(directory)
    print(f"Live-rate policy: {len(live_decisions)} hotels without live pricing {dict(Counter(live_decisions.values()))}")

    # Pre-build Brand & Loyalty Validation Gate (blocks fake/placeholder brand regressions)
    import sys as _sys

    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    from audit_brands_and_loyalty import audit_hotels, format_audit_summary

    # duplicates (same hotel twice in the database): fold the duplicate's awards, critic scores and videos into the
    # record we keep, then drop it. The dropped page redirects to the kept one (build_stayodds_domain.write_redirects).
    merges = (corr.get("merge") or {})
    if merges:
        by_id = {h["id"]: h for h in directory}
        for dup, keep in merges.items():
            a, b = by_id.get(dup), by_id.get(keep)
            if not a or not b:
                continue
            for field, key in (("officialAwards", "label"), ("editorialRatings", "sourceName"), ("youtubeReviews", "videoId")):
                have = {str(x.get(key)) for x in b.get(field) or []}
                b[field] = (b.get(field) or []) + [x for x in a.get(field) or [] if str(x.get(key)) not in have]
        directory = [h for h in directory if h["id"] not in merges]

    brand_errors, brand_warnings = audit_hotels(directory)
    print(format_audit_summary(directory, brand_errors, brand_warnings))
    if brand_errors:
        raise RuntimeError(f"Brand & Loyalty Audit failed with {len(brand_errors)} error(s). Fix Supabase before building.")

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    out_json = ROOT / "data" / "stayodds-directory.json"
    out_json.write_text(
        json.dumps(
            {
                "updatedAt": now_iso,
                "brand": "StayOdds",
                "totalProperties": len(directory),
                "hotels": directory,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Guest ranks + better-rated alternatives for the app (same numbers as the hotel pages)
    from build_insights import better_alternatives, guest_ranks as _gr
    (ROOT / "data" / "guest-ranks.json").write_text(
        json.dumps({"updatedAt": now_iso,
                    "ranks": {k: {t: {f: r[f] for f in ("rank", "of", "group", "top", "topScore", "low", "where") if f in r}
                                  for t, r in v.items()} for k, v in _gr(directory).items()},
                    "nearby": {k: [{f: a[f] for f in ("id", "name", "g", "rc", "km")} for a in v] for k, v in NEARBY.items()},
                    "alternatives": {k: [{f: a[f] for f in ("id", "name", "g", "rc", "band")} for a in v]
                                     for k, v in better_alternatives(directory).items()},
                    "extras": {h["id"]: {k: v for k, v in {
                        "water": ({"free": h["water"]["free"], "paid": h["water"]["paid"], "latest": h["water"]["latest"],
                                   "text": h["water"]["reports"][0]["text"], "source": h["water"]["reports"][0]["source"]}
                                  if h.get("water") else None),
                        "dining": [{f: r[f] for f in ("name", "distinction", "url")} for r in (h.get("dining") or [])] or None,
                        "waterPolicy": ({"status": h["itwf"]["status"], "summary": h["itwf"].get("summary", ""), "url": h["itwf"]["url"]}
                                        if (h.get("itwf") or {}).get("status") else None),
                    }.items() if v} for h in directory if h.get("water") or h.get("dining") or (h.get("itwf") or {}).get("status")}},
                   separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )

    # Build lean index JSON specifically for fast /hotels/ map & /compare/ directory initial load
    lean_hotels = []
    for r in directory:
        vg_lic = (r.get("verifiedGuest") or {}).get("licensed")
        lean_kf = {k: v for k, v in (r.get("keyFacts") or {}).items() if v}
        item: dict[str, Any] = {
            "id": r["id"],
            "name": r["name"],
            "location": r["location"],
            "country": r["country"],
            "region": r["region"],
            "lat": r["lat"],
            "lng": r["lng"],
            "brand": r["brand"],
            "priceRange": r["priceRange"],
            "visitedByUs": r["visitedByUs"],
            "coverageType": r["coverageType"],
            "thumbnail": r["thumbnail"],
            **({"cardPhoto": f"assets/card-photos/{r['id']}.webp"} if (ROOT / "assets" / "card-photos" / f"{r['id']}.webp").exists() else {}),
            "bookingUrl": r["bookingUrl"],
        }
        if r.get("googlePlaceId"):
            item["googlePlaceId"] = r["googlePlaceId"]
        if r.get("nuiteeHotelId"):
            item["nuiteeHotelId"] = r["nuiteeHotelId"]
        if r.get("officialSite"):
            item["officialSite"] = r["officialSite"]
        if r.get("liveRateUnavailable"):
            item["liveRateUnavailable"] = r["liveRateUnavailable"]
        if r.get("priceSnapshot"):
            item["priceSnapshot"] = {
                "nightlyGbp": r["priceSnapshot"]["nightlyGbp"],
                "label": r["priceSnapshot"]["label"],
                "checkedAt": r["priceSnapshot"].get("checkedAt", ""),
            }
        if r["videoId"]:
            item["videoId"] = r["videoId"]
            item["inLiveFeed"] = r["inLiveFeed"]
        if r["scores"]:
            item["scores"] = r["scores"]
            item["overall"] = r["overall"]
        if r["verdict"]:
            item["verdict"] = r["verdict"]
        if r["whereWeDiffer"]:
            item["whereWeDiffer"] = r["whereWeDiffer"]
        if r["standout"]:
            item["standout"] = r["standout"]
        if r["watchOut"]:
            item["watchOut"] = r["watchOut"]
        if lean_kf:
            item["keyFacts"] = lean_kf
        if r.get("propertyStatus"):
            item["propertyStatus"] = {k: v for k, v in r["propertyStatus"].items() if v}
        if r["redFlags"]:
            item["redFlags"] = r["redFlags"]
        if r["shorts"]:
            item["shorts"] = r["shorts"]
        if vg_lic:
            item["verifiedGuest"] = {
                "licensed": {
                    "rating": vg_lic["rating"],
                    "scale": vg_lic["scale"],
                    "normalized100": vg_lic["normalized100"],
                    "reviewCount": vg_lic.get("reviewCount"),
                }
            }
        if r["officialAwards"]:
            item["officialAwards"] = [
                {
                    "awardBody": a.get("awardBody", ""),
                    "label": a["label"],
                    "sourceUrl": a["sourceUrl"],
                }
                for a in r["officialAwards"]
            ]
        if r["editorialRatings"]:
            item["editorialRatings"] = [
                {
                    "sourceName": e["sourceName"],
                    "rawScore": e.get("rawScore", ""),
                    "normalized100": e["normalized100"],
                    "sourceUrl": e["sourceUrl"],
                }
                for e in r["editorialRatings"]
            ]
        if r["youtubeReviews"]:
            item["youtubeReviews"] = [
                {
                    "creatorName": y["creatorName"],
                    "sourceUrl": y["sourceUrl"],
                }
                for y in r["youtubeReviews"]
            ]
        if r.get("dining"):
            item["dining"] = [{"name": x["name"], "distinction": x["distinction"]} for x in r["dining"]]
        lean_hotels.append(item)

    lean_json = ROOT / "data" / "stayodds-index.json"
    lean_json.write_text(
        json.dumps(
            {
                "updatedAt": now_iso,
                "brand": "StayOdds",
                "totalProperties": len(lean_hotels),
                "hotels": lean_hotels,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    visited_hotels = [h for h in lean_hotels if h.get("videoId")]
    visited_json = ROOT / "data" / "stayodds-visited.json"
    visited_json.write_text(
        json.dumps(
            {
                "updatedAt": now_iso,
                "brand": "StayOdds",
                "totalProperties": len(visited_hotels),
                "hotels": visited_hotels,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Generate static SEO HTML pages at <out_dir>/stayodds/<slug>/index.html & destinations/<slug>/index.html
    args = sys.argv[1:]
    data_only = "--data-only" in args
    out_dir = ROOT
    if "--out-dir" in args:
        idx = args.index("--out-dir")
        if idx + 1 < len(args):
            out_dir = Path(args[idx + 1]).resolve()
            out_dir.mkdir(parents=True, exist_ok=True)

    # Build minified assets/styles.min.css from assets/styles.css (safe comment & whitespace stripping)
    css_src = ROOT / "assets" / "styles.css"
    css_min = ROOT / "assets" / "styles.min.css"
    if css_src.exists():
        raw_css = css_src.read_text(encoding="utf-8")
        min_css = re.sub(r"/\*[\s\S]*?\*/", "", raw_css)
        min_css = re.sub(r"\s+", " ", min_css)
        min_css = re.sub(r"\s*([{};,>~])\s*", r"\1", min_css)
        min_css = re.sub(r":\s+", ":", min_css)
        min_css = min_css.replace(";}", "}").strip()
        css_min.write_text(min_css + "\n", encoding="utf-8")

    if data_only:
        print(
            f"BUILT STAYODDS DATA (--data-only)!\n"
            f"  Directory JSON: {len(directory)} verified properties -> data/stayodds-directory.json ({out_json.stat().st_size/1024:.1f} KB)\n"
            f"  Lean Index JSON: {len(lean_hotels)} verified properties -> data/stayodds-index.json ({lean_json.stat().st_size/1024:.1f} KB)\n"
            f"  Minified CSS: assets/styles.css ({css_src.stat().st_size/1024:.1f} KB) -> assets/styles.min.css ({css_min.stat().st_size/1024:.1f} KB)"
        )
        return

    render_static_pages_from_directory(directory, out_dir, write_root_sitemap=(out_dir == ROOT))


def render_static_pages_from_directory(
    directory: list[dict[str, Any]],
    out_dir: Path,
    write_root_sitemap: bool = False,
) -> tuple[int, list[str]]:
    apply_live_rate_policy(directory)  # idempotent; keeps pages safe even if the data files are stale
    visited_hotels = [h for h in directory if h.get("videoId")]
    total_props = len(directory)
    world_props = total_props - len(visited_hotels)
    price_medians = compute_price_medians(directory)
    odds_map = {h["id"]: compute_stayodds_py(h) for h in directory}
    from build_insights import better_alternatives, guest_ranks

    GUEST_RANKS.clear()
    GUEST_RANKS.update(guest_ranks(directory))
    ALTERNATIVES.clear()
    ALTERNATIVES.update(better_alternatives(directory))
    from build_insights import nearby_compare
    NEARBY.update(nearby_compare(directory))

    stayodds_dir = out_dir / "stayodds"
    stayodds_dir.mkdir(parents=True, exist_ok=True)
    for h in directory:
        o = odds_map[h["id"]]
        rivals = pick_comparable_rivals(h, directory, odds_map, limit=3)
        pdir = stayodds_dir / h["id"]
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "index.html").write_text(
            render_seo_page(h, o, rivals, total_props, price_medians=price_medians, rivals=rivals),
            encoding="utf-8",
        )

    # Sync recalculated total_props and world_props counts in templates when building to ROOT
    if out_dir == ROOT:
        for rel_html in ["stayodds-src/compare/index.html", "stayodds-src/hotels/index.html", "about/index.html", "faq/index.html"]:
            hp = ROOT / rel_html
            if hp.exists():
                txt = hp.read_text(encoding="utf-8")
                from count_sync import sync_counts

                visited_n = sum(1 for r in directory if r.get("tier") in ("first_hand_verified", "short_preview"))
                txt = sync_counts(txt, total_props, visited_n)
                txt = re.sub(r"(Global\s+Directory\s*\()\d{3,4}(\))", f"\\g<1>{world_props}\\2", txt)
                hp.write_text(txt, encoding="utf-8")

    # Generate static SEO destination landing pages at <out_dir>/destinations/<slug>/index.html
    dest_root = out_dir / "destinations"
    dest_root.mkdir(parents=True, exist_ok=True)
    generated_dests: list[str] = []
    for guide in DESTINATION_GUIDES:
        ft = guide["filterType"]
        if ft == "region":
            matched = [r for r in directory if r["region"] == guide["filterValue"]]
        elif ft == "regions":
            allowed_r = {x.strip() for x in guide["filterValue"].split("|") if x.strip()}
            matched = [r for r in directory if r["region"] in allowed_r]
        elif ft == "region_except_country":
            reg_val, excl_c = [x.strip() for x in guide["filterValue"].split("|", 1)]
            matched = [r for r in directory if r["region"] == reg_val and r["country"] != excl_c]
        elif ft == "countries":
            allowed = {c.strip() for c in guide["filterValue"].split("|") if c.strip()}
            matched = [r for r in directory if r["country"] in allowed]
        elif ft == "location_regex":
            loc_re = re.compile(guide["filterValue"], re.I)
            matched = [r for r in directory if loc_re.search(f"{r.get('location', '')} {r.get('name', '')}")]
        else:
            matched = [r for r in directory if r["country"] == guide["filterValue"]]
        if not matched:
            continue
        ddir = dest_root / guide["slug"]
        ddir.mkdir(parents=True, exist_ok=True)
        (ddir / "index.html").write_text(
            render_destination_page(guide, matched, DESTINATION_GUIDES),
            encoding="utf-8",
        )
        generated_dests.append(guide["slug"])

    if write_root_sitemap:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        urls = [
            (f"{SITE_URL}/", "1.0", "daily"),
            (f"{SITE_URL}/cameras/", "0.85", "monthly"),
            (f"{SITE_URL}/links/", "0.85", "weekly"),
            (f"{SITE_URL}/about/", "0.85", "monthly"),
            (f"{SITE_URL}/faq/", "0.85", "monthly"),
            (f"{SITE_URL}/contact/", "0.80", "monthly"),
            (f"{SITE_URL}/privacy/", "0.60", "monthly"),
        ]
        sm_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for loc, prio, freq in urls:
            sm_lines.append(
                f"  <url><loc>{esc(loc)}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
            )
        sm_lines.append("</urlset>\n")
        (ROOT / "sitemap.xml").write_text("\n".join(sm_lines), encoding="utf-8")

    print(
        f"RENDERED STAYODDS STATIC PAGES -> {out_dir}\n"
        f"  Static SEO Pages: {len(directory)} pages -> {stayodds_dir}\n"
        f"  Destination Guides: {len(generated_dests)} pages -> {dest_root}"
    )
    return len(directory), generated_dests


if __name__ == "__main__":
    if "--from-local-json" in sys.argv[1:]:
        out_dir = ROOT
        if "--out-dir" in sys.argv[1:]:
            idx = sys.argv.index("--out-dir")
            if idx + 1 < len(sys.argv):
                out_dir = Path(sys.argv[idx + 1]).resolve()
                out_dir.mkdir(parents=True, exist_ok=True)
        local_dir = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8")).get("hotels", [])
        render_static_pages_from_directory(local_dir, out_dir, write_root_sitemap=False)
    else:
        main()
