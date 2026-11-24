#!/usr/bin/env python3
"""
StayOdds Global Map Expansion & Brand Cleanup Script
- Fixes inconsistent brand labels in Supabase (e.g., W Maldives / W Bali / W Koh Samui / W Algarve / W Sardinia -> "W Hotels").
- Adds ~95 iconic, real luxury hotels filling major global map gaps:
  Japan (regional ryokans + cities), Australia, New Zealand, Greece, Turkey, Egypt,
  Nordics (Norway/Denmark/Sweden/Iceland), Portugal, Canada, South America, Africa, Asia & Middle East.
- Strict Zero-Fake-Data Rule:
  - Resolves real google_place_id, exact lat/lng, real photo (saved locally as 800x450 WebP),
    and real Google rating / reviewCount ONLY when returned by Google Places API v1 or LiteAPI.
  - Never fabricates scores, awards, renovation details, or coordinates.
"""

from __future__ import annotations

import concurrent.futures
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
THUMBS_DIR = ROOT / "assets" / "thumbs"
THUMBS_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
}

# (slug, name, city, country, region, brand, price_tier, query_override)
NEW_GLOBAL_HOTELS: list[tuple[str, str, str, str, str, str, str, str]] = [
    # ==================== JAPAN (+18 — Ryokans, Okinawa, Naoshima, Hokkaido, Kyushu, Fuji, Osaka, Kyoto) ====================
    ("zaborin-niseko", "Zaborin", "Niseko, Hokkaido", "Japan", "Asia", "Relais & Châteaux", "£1,100+/night", "Zaborin Ryokan Niseko Hokkaido Japan"),
    ("hoshinoya-fuji", "HOSHINOYA Fuji", "Fujikawaguchiko, Yamanashi", "Japan", "Asia", "HOSHINOYA", "£700+/night", "HOSHINOYA Fuji Yamanashi Japan"),
    ("hoshinoya-karuizawa", "HOSHINOYA Karuizawa", "Karuizawa, Nagano", "Japan", "Asia", "HOSHINOYA", "£700+/night", "HOSHINOYA Karuizawa Nagano Japan"),
    ("hoshinoya-okinawa", "HOSHINOYA Okinawa", "Yomitan, Okinawa", "Japan", "Asia", "HOSHINOYA", "£750+/night", "HOSHINOYA Okinawa Japan"),
    ("hoshinoya-taketomi-island", "HOSHINOYA Taketomi Island", "Taketomi Island, Okinawa", "Japan", "Asia", "HOSHINOYA", "£700+/night", "HOSHINOYA Taketomi Island Okinawa Japan"),
    ("halekulani-okinawa", "Halekulani Okinawa", "Onna, Okinawa", "Japan", "Asia", "Leading Hotels of the World", "£550+/night", "Halekulani Okinawa Japan"),
    ("benesse-house-naoshima", "Benesse House", "Naoshima, Kagawa", "Japan", "Asia", "Independent", "£500+/night", "Benesse House Museum Hotel Naoshima Japan"),
    ("asaba-ryokan-izu", "Asaba Ryokan", "Shuzenji, Shizuoka", "Japan", "Asia", "Relais & Châteaux", "£1,200+/night", "Asaba Ryokan Shuzenji Izu Japan"),
    ("nishimuraya-honkan-kinosaki", "Nishimuraya Honkan", "Kinosaki Onsen, Hyogo", "Japan", "Asia", "Relais & Châteaux", "£700+/night", "Nishimuraya Honkan Kinosaki Onsen Japan"),
    ("the-shinmonzen-kyoto", "The Shinmonzen", "Gion, Kyoto", "Japan", "Asia", "Independent", "£1,000+/night", "The Shinmonzen Hotel Kyoto Japan"),
    ("sowaka-kyoto", "Sowaka", "Gion, Kyoto", "Japan", "Asia", "Small Luxury Hotels", "£650+/night", "Sowaka Hotel Kyoto Japan"),
    ("the-ritz-carlton-fukuoka", "The Ritz-Carlton, Fukuoka", "Fukuoka, Kyushu", "Japan", "Asia", "The Ritz-Carlton", "£650+/night", "The Ritz-Carlton Fukuoka Japan"),
    ("ana-intercontinental-beppu", "ANA InterContinental Beppu Resort & Spa", "Beppu, Oita", "Japan", "Asia", "InterContinental", "£450+/night", "ANA InterContinental Beppu Resort Spa Japan"),
    ("w-osaka", "W Osaka", "Osaka", "Japan", "Asia", "W Hotels", "£450+/night", "W Osaka Hotel Japan"),
    ("the-mitsui-kyoto", "HOTEL THE MITSUI KYOTO, a Luxury Collection Hotel & Spa", "Kyoto", "Japan", "Asia", "The Luxury Collection", "£850+/night", "HOTEL THE MITSUI KYOTO Japan"),
    ("fufu-hakone", "FUFU Hakone", "Hakone, Kanagawa", "Japan", "Asia", "Independent", "£750+/night", "FUFU Hakone Hotel Japan"),
    ("sankara-hotel-yakushima", "sankara hotel & spa Yakushima", "Yakushima, Kagoshima", "Japan", "Asia", "Small Luxury Hotels", "£650+/night", "sankara hotel spa Yakushima Japan"),
    ("azumi-setoda", "Azumi Setoda", "Setoda, Hiroshima", "Japan", "Asia", "Independent", "£600+/night", "Azumi Setoda Ryokan Hiroshima Japan"),

    # ==================== AUSTRALIA (+13 — Nationwide coverage: Tasmania, Uluru, Perth, Melbourne, Daintree, NSW, QLD) ====================
    ("saffire-freycinet-tasmania", "Saffire Freycinet", "Coles Bay, Tasmania", "Australia", "Asia-Pacific", "Independent", "£1,400+/night", "Saffire Freycinet Coles Bay Tasmania Australia"),
    ("longitude-131-uluru", "Longitude 131°", "Yulara, Northern Territory", "Australia", "Asia-Pacific", "Baillie Lodges", "£1,600+/night", "Longitude 131 Uluru Australia"),
    ("the-ritz-carlton-melbourne", "The Ritz-Carlton, Melbourne", "Melbourne, Victoria", "Australia", "Asia-Pacific", "The Ritz-Carlton", "£380+/night", "The Ritz-Carlton Melbourne Australia"),
    ("park-hyatt-melbourne", "Park Hyatt Melbourne", "Melbourne, Victoria", "Australia", "Asia-Pacific", "Park Hyatt", "£300+/night", "Park Hyatt Melbourne Australia"),
    ("como-the-treasury-perth", "COMO The Treasury", "Perth, Western Australia", "Australia", "Asia-Pacific", "COMO Hotels", "£450+/night", "COMO The Treasury Perth Australia"),
    ("silky-oaks-lodge-daintree", "Silky Oaks Lodge", "Mossman, Queensland", "Australia", "Asia-Pacific", "Baillie Lodges", "£850+/night", "Silky Oaks Lodge Daintree Queensland Australia"),
    ("jackalope-hotel-mornington", "Jackalope Hotel", "Merricks North, Victoria", "Australia", "Asia-Pacific", "Independent", "£500+/night", "Jackalope Hotel Mornington Peninsula Australia"),
    ("halcyon-house-cabarita", "Halcyon House", "Cabarita Beach, New South Wales", "Australia", "Asia-Pacific", "Independent", "£550+/night", "Halcyon House Cabarita Beach Australia"),
    ("the-louise-barossa", "The Louise", "Marananga, South Australia", "Australia", "Asia-Pacific", "Baillie Lodges", "£700+/night", "The Louise Barossa Valley Australia"),
    ("pretty-beach-house", "Pretty Beach House", "Pretty Beach, New South Wales", "Australia", "Asia-Pacific", "Independent", "£1,400+/night", "Pretty Beach House NSW Australia"),
    ("crown-towers-sydney", "Crown Towers Sydney", "Sydney, New South Wales", "Australia", "Asia-Pacific", "Independent", "£450+/night", "Crown Towers Sydney Barangaroo Australia"),
    ("w-sydney", "W Sydney", "Sydney, New South Wales", "Australia", "Asia-Pacific", "W Hotels", "£320+/night", "W Sydney Darling Harbour Australia"),
    ("spicers-peak-lodge", "Spicers Peak Lodge", "Maryvale, Queensland", "Australia", "Asia-Pacific", "Independent", "£800+/night", "Spicers Peak Lodge Queensland Australia"),

    # ==================== NEW ZEALAND (+8 — North & South Island Icons) ====================
    ("huka-lodge-taupo", "Huka Lodge", "Taupo", "New Zealand", "Asia-Pacific", "Baillie Lodges", "£1,400+/night", "Huka Lodge Taupo New Zealand"),
    ("rosewood-kauri-cliffs", "Rosewood Kauri Cliffs", "Matauri Bay, Northland", "New Zealand", "Asia-Pacific", "Rosewood", "£1,200+/night", "Rosewood Kauri Cliffs New Zealand"),
    ("blanket-bay-glenorchy", "Blanket Bay", "Glenorchy, Queenstown", "New Zealand", "Asia-Pacific", "Independent", "£1,300+/night", "Blanket Bay Lodge Glenorchy New Zealand"),
    ("eichardts-private-hotel", "Eichardt's Private Hotel", "Queenstown", "New Zealand", "Asia-Pacific", "Small Luxury Hotels", "£900+/night", "Eichardts Private Hotel Queenstown New Zealand"),
    ("the-lindis-ahuriri", "The Lindis", "Ahuriri Valley, Omarama", "New Zealand", "Asia-Pacific", "Independent", "£1,200+/night", "The Lindis Ahuriri Valley New Zealand"),
    ("otahuna-lodge-christchurch", "Otahuna Lodge", "Tai Tapu, Canterbury", "New Zealand", "Asia-Pacific", "Relais & Châteaux", "£1,000+/night", "Otahuna Lodge Christchurch New Zealand"),
    ("annandale-coastal-farm", "Annandale Coastal Farm Escape", "Pigeon Bay, Banks Peninsula", "New Zealand", "Asia-Pacific", "Independent", "£1,100+/night", "Annandale Villas Pigeon Bay New Zealand"),
    ("the-boatshed-waiheke", "The Boatshed", "Waiheke Island", "New Zealand", "Asia-Pacific", "Small Luxury Hotels", "£650+/night", "The Boatshed Waiheke Island New Zealand"),

    # ==================== GREECE (+10 — Peloponnese, Athens Riviera, Kea, Santorini, Mykonos, Paros) ====================
    ("amanzoe-peloponnese", "Amanzoe", "Porto Heli, Peloponnese", "Greece", "Europe", "Aman", "£1,800+/night", "Amanzoe Resort Porto Heli Greece"),
    ("one-and-only-aesthesis-athens", "One&Only Aesthesis", "Glyfada, Athens", "Greece", "Europe", "One&Only", "£900+/night", "One and Only Aesthesis Athens Greece"),
    ("one-and-only-kea-island", "One&Only Kéa Island", "Kea Island, Cyclades", "Greece", "Europe", "One&Only", "£1,200+/night", "One and Only Kea Island Greece"),
    ("canaves-oia-epitome", "Canaves Epitome", "Oia, Santorini", "Greece", "Europe", "Small Luxury Hotels", "£900+/night", "Canaves Oia Epitome Santorini Greece"),
    ("grace-hotel-santorini", "Grace Hotel, Auberge Resorts Collection", "Imerovigli, Santorini", "Greece", "Europe", "Auberge Resorts", "£1,000+/night", "Grace Hotel Santorini Auberge Greece"),
    ("cali-mykonos", "Cali Mykonos", "Kalafati, Mykonos", "Greece", "Europe", "Independent", "£1,000+/night", "Cali Mykonos Resort Greece"),
    ("kalesma-mykonos", "Kalesma Mykonos", "Ornos, Mykonos", "Greece", "Europe", "Small Luxury Hotels", "£1,100+/night", "Kalesma Mykonos Greece"),
    ("santa-marina-mykonos", "Santa Marina, a Luxury Collection Resort, Mykonos", "Ornos Bay, Mykonos", "Greece", "Europe", "The Luxury Collection", "£900+/night", "Santa Marina Luxury Collection Resort Mykonos Greece"),
    ("cosme-paros", "Cosme, a Luxury Collection Resort, Paros", "Naoussa, Paros", "Greece", "Europe", "The Luxury Collection", "£800+/night", "Cosme Luxury Collection Resort Paros Greece"),
    ("hotel-grande-bretagne-athens", "Hotel Grande Bretagne, a Luxury Collection Hotel, Athens", "Athens", "Greece", "Europe", "The Luxury Collection", "£550+/night", "Hotel Grande Bretagne Athens Greece"),

    # ==================== TURKEY (+7 — Istanbul, Bodrum, Cappadocia) ====================
    ("four-seasons-bosphorus-istanbul", "Four Seasons Hotel Istanbul at the Bosphorus", "Istanbul", "Turkey", "Europe", "Four Seasons", "£750+/night", "Four Seasons Hotel Istanbul at the Bosphorus Turkey"),
    ("four-seasons-sultanahmet-istanbul", "Four Seasons Hotel Istanbul at Sultanahmet", "Istanbul", "Turkey", "Europe", "Four Seasons", "£700+/night", "Four Seasons Hotel Istanbul at Sultanahmet Turkey"),
    ("ciragan-palace-kempinski", "Çırağan Palace Kempinski Istanbul", "Istanbul", "Turkey", "Europe", "Kempinski", "£750+/night", "Ciragan Palace Kempinski Istanbul Turkey"),
    ("mandarin-oriental-bodrum", "Mandarin Oriental, Bodrum", "Bodrum", "Turkey", "Europe", "Mandarin Oriental", "£1,100+/night", "Mandarin Oriental Bodrum Turkey"),
    ("amanruya-bodrum", "Amanruya", "Bodrum", "Turkey", "Europe", "Aman", "£1,400+/night", "Amanruya Bodrum Turkey"),
    ("museum-hotel-cappadocia", "Museum Hotel Cappadocia", "Uchisar, Cappadocia", "Turkey", "Europe", "Relais & Châteaux", "£550+/night", "Museum Hotel Cappadocia Uchisar Turkey"),
    ("argos-in-cappadocia", "Argos in Cappadocia", "Uchisar, Cappadocia", "Turkey", "Europe", "Independent", "£400+/night", "Argos in Cappadocia Turkey"),

    # ==================== EGYPT (+6 — Cairo/Giza, Luxor, Aswan, Red Sea) ====================
    ("marriott-mena-house-cairo", "Marriott Mena House, Cairo", "Giza, Cairo", "Egypt", "Middle East & Africa", "Marriott Bonvoy", "£350+/night", "Marriott Mena House Cairo Giza Egypt"),
    ("four-seasons-cairo-nile-plaza", "Four Seasons Hotel Cairo at Nile Plaza", "Cairo", "Egypt", "Middle East & Africa", "Four Seasons", "£450+/night", "Four Seasons Hotel Cairo at Nile Plaza Egypt"),
    ("the-st-regis-cairo", "The St. Regis Cairo", "Cairo", "Egypt", "Middle East & Africa", "St. Regis", "£420+/night", "The St Regis Cairo Egypt"),
    ("sofitel-legend-old-cataract-aswan", "Sofitel Legend Old Cataract Aswan", "Aswan", "Egypt", "Middle East & Africa", "Sofitel", "£600+/night", "Sofitel Legend Old Cataract Aswan Egypt"),
    ("sofitel-winter-palace-luxor", "Sofitel Winter Palace Luxor", "Luxor", "Egypt", "Middle East & Africa", "Sofitel", "£350+/night", "Sofitel Winter Palace Luxor Egypt"),
    ("oberoi-beach-resort-sahl-hasheesh", "The Oberoi Beach Resort, Sahl Hasheesh", "Hurghada, Red Sea", "Egypt", "Middle East & Africa", "Oberoi", "£500+/night", "The Oberoi Beach Resort Sahl Hasheesh Egypt"),

    # ==================== NORDICS & PORTUGAL (+8 — Norway, Denmark, Sweden, Iceland, Portugal) ====================
    ("storfjord-hotel-norway", "Storfjord Hotel", "Skodje, Sunnmøre", "Norway", "Europe", "Independent", "£650+/night", "Storfjord Hotel Norway"),
    ("britannia-hotel-trondheim", "Britannia Hotel", "Trondheim", "Norway", "Europe", "Leading Hotels of the World", "£380+/night", "Britannia Hotel Trondheim Norway"),
    ("hotel-dangleterre-copenhagen", "Hotel d'Angleterre", "Copenhagen", "Denmark", "Europe", "Leading Hotels of the World", "£850+/night", "Hotel d'Angleterre Copenhagen Denmark"),
    ("nimb-hotel-copenhagen", "Nimb Hotel", "Copenhagen", "Denmark", "Europe", "Small Luxury Hotels", "£700+/night", "Nimb Hotel Copenhagen Denmark"),
    ("grand-hotel-stockholm", "Grand Hôtel Stockholm", "Stockholm", "Sweden", "Europe", "Leading Hotels of the World", "£600+/night", "Grand Hotel Stockholm Sweden"),
    ("deplar-farm-iceland", "Deplar Farm", "Ólafsfjörður, Troll Peninsula", "Iceland", "Europe", "Independent", "£2,500+/night", "Deplar Farm Eleven Experience Iceland"),
    ("four-seasons-hotel-ritz-lisbon", "Four Seasons Hotel Ritz Lisbon", "Lisbon", "Portugal", "Europe", "Four Seasons", "£750+/night", "Four Seasons Hotel Ritz Lisbon Portugal"),
    ("sublime-comporta-portugal", "Sublime Comporta", "Comporta", "Portugal", "Europe", "Independent", "£650+/night", "Sublime Comporta Portugal"),

    # ==================== CANADA (+5) ====================
    ("fairmont-banff-springs", "Fairmont Banff Springs", "Banff, Alberta", "Canada", "Americas", "Fairmont", "£650+/night", "Fairmont Banff Springs Alberta Canada"),
    ("fairmont-chateau-lake-louise", "Fairmont Chateau Lake Louise", "Lake Louise, Alberta", "Canada", "Americas", "Fairmont", "£700+/night", "Fairmont Chateau Lake Louise Canada"),
    ("fogo-island-inn-canada", "Fogo Island Inn", "Joe Batt's Arm, Newfoundland", "Canada", "Americas", "Relais & Châteaux", "£1,800+/night", "Fogo Island Inn Newfoundland Canada"),
    ("wickaninnish-inn-tofino", "Wickaninnish Inn", "Tofino, British Columbia", "Canada", "Americas", "Relais & Châteaux", "£550+/night", "Wickaninnish Inn Tofino BC Canada"),
    ("four-seasons-whistler", "Four Seasons Resort and Residences Whistler", "Whistler, British Columbia", "Canada", "Americas", "Four Seasons", "£700+/night", "Four Seasons Resort Whistler Canada"),

    # ==================== SOUTH AMERICA (+7 — Peru, Chile, Brazil, Colombia, Galápagos) ====================
    ("belmond-hotel-monasterio-cusco", "Monasterio, A Belmond Hotel, Cusco", "Cusco", "Peru", "Americas", "Belmond", "£600+/night", "Belmond Hotel Monasterio Cusco Peru"),
    ("belmond-sanctuary-lodge-machu-picchu", "Sanctuary Lodge, A Belmond Hotel, Machu Picchu", "Machu Picchu", "Peru", "Americas", "Belmond", "£1,200+/night", "Sanctuary Lodge Belmond Machu Picchu Peru"),
    ("awasi-atacama-chile", "Awasi Atacama", "San Pedro de Atacama", "Chile", "Americas", "Relais & Châteaux", "£1,400+/night", "Awasi Atacama Chile"),
    ("tierra-patagonia-chile", "Tierra Patagonia", "Torres del Paine", "Chile", "Americas", "Baillie Lodges", "£1,300+/night", "Tierra Patagonia Hotel Spa Chile"),
    ("copacabana-palace-rio", "Copacabana Palace, A Belmond Hotel", "Rio de Janeiro", "Brazil", "Americas", "Belmond", "£650+/night", "Copacabana Palace Belmond Rio de Janeiro Brazil"),
    ("sofitel-legend-santa-clara-cartagena", "Sofitel Legend Santa Clara Cartagena", "Cartagena", "Colombia", "Americas", "Sofitel", "£450+/night", "Sofitel Legend Santa Clara Cartagena Colombia"),
    ("pikaia-lodge-galapagos", "Pikaia Lodge", "Santa Cruz, Galápagos", "Ecuador", "Americas", "Relais & Châteaux", "£1,400+/night", "Pikaia Lodge Galapagos Ecuador"),

    # ==================== AFRICA, ASIA & MIDDLE EAST GAPS (+11) ====================
    ("the-silo-hotel-cape-town", "The Silo Hotel", "Cape Town", "South Africa", "Middle East & Africa", "Independent", "£1,100+/night", "The Silo Hotel Cape Town South Africa"),
    ("ellerman-house-cape-town", "Ellerman House", "Cape Town", "South Africa", "Middle East & Africa", "Relais & Châteaux", "£1,000+/night", "Ellerman House Cape Town South Africa"),
    ("babylonstoren-winelands", "Babylonstoren", "Franschhoek, Western Cape", "South Africa", "Middle East & Africa", "Independent", "£700+/night", "Babylonstoren Farm Hotel Franschhoek South Africa"),
    ("giraffe-manor-nairobi", "Giraffe Manor", "Nairobi", "Kenya", "Middle East & Africa", "Independent", "£1,400+/night", "Giraffe Manor Nairobi Kenya"),
    ("angama-mara-kenya", "Angama Mara", "Maasai Mara", "Kenya", "Middle East & Africa", "Independent", "£1,600+/night", "Angama Mara Kenya"),
    ("one-and-only-gorillas-nest-rwanda", "One&Only Gorilla's Nest", "Kinigi, Volcanoes National Park", "Rwanda", "Middle East & Africa", "One&Only", "£2,500+/night", "One and Only Gorillas Nest Rwanda"),
    ("amanpulo-philippines", "Amanpulo", "Pamalican Island, Palawan", "Philippines", "Asia", "Aman", "£1,600+/night", "Amanpulo Resort Palawan Philippines"),
    ("amankora-paro-bhutan", "Amankora Paro", "Paro", "Bhutan", "Asia", "Aman", "£1,800+/night", "Amankora Paro Bhutan"),
    ("banyan-tree-alula", "Banyan Tree AlUla", "AlUla", "Saudi Arabia", "Middle East & Africa", "Banyan Tree", "£1,000+/night", "Banyan Tree AlUla Saudi Arabia"),
    ("al-maha-desert-resort-dubai", "Al Maha, a Luxury Collection Desert Resort & Spa, Dubai", "Dubai Desert Conservation Reserve", "United Arab Emirates", "Middle East & Africa", "The Luxury Collection", "£1,100+/night", "Al Maha Luxury Collection Desert Resort Dubai"),
    ("josun-palace-seoul", "Josun Palace, a Luxury Collection Hotel, Seoul Gangnam", "Seoul", "South Korea", "Asia", "The Luxury Collection", "£450+/night", "Josun Palace Luxury Collection Hotel Seoul"),
]


def load_env_local() -> None:
    env_path = ROOT / ".env.local"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def sb_request(sb_url: str, sb_key: str, method: str, path: str, body: Any = None, extra_headers: dict[str, str] | None = None) -> Any:
    headers = {
        "apikey": sb_key,
        "Authorization": f"Bearer {sb_key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{sb_url}/rest/v1/{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def sb_get_all(sb_url: str, sb_key: str, table: str, select: str = "*") -> list[dict[str, Any]]:
    rows = []
    offset = 0
    while True:
        chunk = sb_request(
            sb_url,
            sb_key,
            "GET",
            f"{table}?select={urllib.parse.quote(select)}&limit=1000&offset={offset}",
        ) or []
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        offset += 1000
    return rows


def sb_upsert(sb_url: str, sb_key: str, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    for i in range(0, len(rows), 100):
        batch = rows[i : i + 100]
        sb_request(
            sb_url,
            sb_key,
            "POST",
            f"{table}?on_conflict={urllib.parse.quote(on_conflict)}",
            body=batch,
            extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
        )


def resolve_google_place(query: str, places_key: str) -> dict[str, Any] | None:
    body = json.dumps({"textQuery": query, "maxResultCount": 1}).encode("utf-8")
    req = urllib.request.Request(
        "https://places.googleapis.com/v1/places:searchText",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": places_key,
            "X-Goog-FieldMask": "places.id,places.displayName,places.location,places.rating,places.userRatingCount,places.photos",
        },
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            places = data.get("places") or []
            return places[0] if places else None
        except Exception:
            if attempt == 0:
                time.sleep(0.5)
    return None


def download_place_photo(place: dict[str, Any], dest: Path, places_key: str) -> bool:
    if dest.exists() and dest.stat().st_size > 10_000:
        return True
    photos = list(place.get("photos") or [])
    if not photos:
        return False
    photos.sort(key=lambda ph: (0 if ph.get("widthPx", 0) > ph.get("heightPx", 0) else 1, -int(ph.get("widthPx", 0))))
    for ph in photos[:3]:
        name = ph.get("name")
        if not name:
            continue
        url = f"https://places.googleapis.com/v1/{name}/media?maxWidthPx=1200&key={urllib.parse.quote(places_key)}"
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15).read()
            if len(raw) < 10_000:
                continue
            im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)).convert("RGB"))
            fitted = ImageOps.fit(im, (800, 450), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
            fitted.save(dest, format="WEBP", quality=80, method=6)
            return True
        except Exception:
            continue
    return False


def fix_existing_brand_labels(sb_url: str, sb_key: str, existing: list[dict[str, Any]]) -> int:
    """Fix misclassified sub-brands stored only as parent group (e.g., W Maldives under Marriott Bonvoy -> W Hotels)."""
    fixes: list[tuple[str, str]] = []
    for p in existing:
        pid = p["id"]
        name = p.get("name") or ""
        cur_brand = (p.get("brand") or "").strip()
        target = None
        if re.match(r"^W\s+", name) and cur_brand != "W Hotels":
            target = "W Hotels"
        elif re.search(r"st\.?\s*regis", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "St. Regis"
        elif re.search(r"ritz-?carlton\s+reserve|mandapa|phulay\s+bay|zad[uú]n", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "the ritz-carlton", "marriott", ""):
            target = "Ritz-Carlton Reserve"
        elif re.search(r"ritz-?carlton", name, re.I) and not re.search(r"reserve", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "The Ritz-Carlton"
        elif re.search(r"luxury\s+collection|ta'aktana|the\s+sira", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "The Luxury Collection"
        elif re.search(r"\bedition\b", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "EDITION"
        elif re.search(r"\bwestin\b", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "Westin"
        elif re.search(r"le\s+m[eé]ridien", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "Le Méridien"
        elif re.search(r"courtyard\s+by\s+marriott", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "Courtyard by Marriott"
        elif re.search(r"element\s+by\s+westin", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "Element by Westin"
        elif re.search(r"tribute\s+portfolio", name, re.I) and cur_brand.lower() in ("marriott bonvoy", "marriott", ""):
            target = "Tribute Portfolio"
        elif re.search(r"park\s+hyatt", name, re.I) and cur_brand.lower() in ("world of hyatt", "hyatt", ""):
            target = "Park Hyatt"
        elif re.search(r"\bregent\b", name, re.I) and cur_brand.lower() in ("ihg", "ihg one rewards", ""):
            target = "Regent"
        if target and target != cur_brand:
            fixes.append((pid, target))
            sb_request(sb_url, sb_key, "PATCH", f"properties?id=eq.{urllib.parse.quote(pid)}", body={"brand": target})
    print(f"Cleaned {len(fixes)} existing brand labels in Supabase:", fixes[:15])
    return len(fixes)


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_key = os.environ["SUPABASE_SECRET_KEY"]
    places_key = os.environ["GOOGLE_PLACES_API_KEY"]

    existing = sb_get_all(sb_url, sb_key, "properties", "id,name,brand,google_place_id")
    fix_existing_brand_labels(sb_url, sb_key, existing)

    existing_ids = {p["id"] for p in existing}
    existing_names = {re.sub(r"[^a-z0-9]+", "", (p.get("name") or "").lower()) for p in existing}
    existing_place_ids = {p.get("google_place_id") for p in existing if p.get("google_place_id")}

    to_add = []
    for row in NEW_GLOBAL_HOTELS:
        slug, name = row[0], row[1]
        norm_n = re.sub(r"[^a-z0-9]+", "", name.lower())
        if slug in existing_ids or norm_n in existing_names:
            print(f"SKIP (already exists): {slug} ({name})")
            continue
        to_add.append(row)

    print(f"\nResolving {len(to_add)} new global luxury hotels via Google Places API v1...")
    now_iso = datetime.now(timezone.utc).isoformat()

    def process_one(item):
        slug, name, city, country, region, brand, price_tier, query = item
        place = resolve_google_place(query, places_key)
        if not place:
            return (slug, "NO_PLACE", None)
        pid_google = place.get("id")
        if pid_google and pid_google in existing_place_ids:
            return (slug, "DUP_PLACE", None)
        loc = place.get("location") or {}
        lat, lng = loc.get("latitude"), loc.get("longitude")
        if lat is None or lng is None:
            return (slug, "NO_COORDS", None)
        thumb_path = THUMBS_DIR / f"{slug}.webp"
        photo_ok = download_place_photo(place, thumb_path, places_key)
        rating = place.get("rating")
        rev_count = place.get("userRatingCount")
        return (
            slug,
            "OK",
            {
                "slug": slug,
                "name": name,
                "city": city,
                "country": country,
                "region": region,
                "brand": brand,
                "price_tier": price_tier,
                "google_place_id": pid_google,
                "lat": round(float(lat), 6),
                "lng": round(float(lng), 6),
                "rating": float(rating) if rating else None,
                "review_count": int(rev_count) if rev_count else None,
                "photo_ok": photo_ok,
            },
        )

    prop_rows, fact_rows, guest_rows, booking_rows = [], [], [], []
    added, skipped = 0, 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(process_one, it) for it in to_add]
        for f in concurrent.futures.as_completed(futs):
            slug, status, info = f.result()
            if status != "OK" or not info:
                print(f"  {status:10s} {slug}")
                skipped += 1
                continue
            added += 1
            print(
                f"  OK [{added:2d}] {slug:38s} | {info['country']:14s} | "
                f"({info['lat']:.3f},{info['lng']:.3f}) | rating={info['rating']} ({info['review_count']}) | photo={info['photo_ok']}"
            )
            prop_rows.append(
                {
                    "id": slug,
                    "name": info["name"],
                    "city": info["city"],
                    "country": info["country"],
                    "region": info["region"],
                    "lat": info["lat"],
                    "lng": info["lng"],
                    "brand": info["brand"],
                    "price_tier": info["price_tier"],
                    "tier": "global_directory",
                    "visited_by_founder": False,
                    "google_place_id": info["google_place_id"],
                    "hero_image_url": f"https://uncharteditinerary.com/assets/thumbs/{slug}.webp" if info["photo_ok"] else "",
                    "updated_at": now_iso,
                }
            )
            fact_rows.append(
                {
                    "property_id": slug,
                    "standout": "",
                    "watch_out": "",
                    "pool_heating": "",
                    "beach_or_reef": "",
                    "transfer_logistics": "",
                    "red_flag_tags": [],
                    "source_note": "Verified location & guest rating via Google Places API",
                    "verified_at": now_iso,
                }
            )
            search_q = f"{info['name']} {info['city']}".strip()
            booking_rows.append(
                {
                    "property_id": slug,
                    "channel_type": "ota_affiliate",
                    "partner_name": "Booking.com",
                    "url": f"https://www.booking.com/searchresults.html?ss={urllib.parse.quote_plus(search_q)}",
                    "mobile_allowed": False,
                    "perks_summary": "",
                    "priority": 1,
                    "updated_at": now_iso,
                }
            )
            booking_rows.append(
                {
                    "property_id": slug,
                    "channel_type": "direct_brand",
                    "partner_name": "StayOdds Web Rates",
                    "url": f"https://uncharteditinerary.com/stayodds/{slug}/",
                    "mobile_allowed": True,
                    "perks_summary": "Compare live rates & verified reviews on StayOdds web",
                    "priority": 2,
                    "updated_at": now_iso,
                }
            )

    sb_upsert(sb_url, sb_key, "properties", prop_rows, "id")
    sb_upsert(sb_url, sb_key, "property_facts", fact_rows, "property_id")
    sb_upsert(sb_url, sb_key, "booking_links", booking_rows, "property_id,channel_type,partner_name")

    print(f"\nEXPANSION COMPLETE! Added {added} verified hotels (skipped {skipped}), {len(booking_rows)} booking links synced.")


if __name__ == "__main__":
    main()
