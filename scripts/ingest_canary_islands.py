#!/usr/bin/env python3
"""
StayOdds Canary Islands Comprehensive Real-Data Ingestion
=========================================================
Adds verified Canary Islands hotels across Tenerife, Lanzarote, Gran Canaria,
Fuerteventura, La Gomera, and La Palma — spanning luxury flagships, major loyalty
chains (Marriott Bonvoy, Hyatt Inclusive Collection, IHG/Iberostar, Meliá/Paradisus,
Barceló/Royal Hideaway, Radisson), family-friendly resorts, adults-only retreats,
and great-value all-inclusive hotels.

Strict Zero-Fake-Data Guarantees:
1. Matches each candidate live against FREE Nuitée Connect (LiteAPI) metadata
   endpoints (/v3.0/data/hotels & /v3.0/data/hotel) in Spain (ES).
2. Enforces Canary Islands geographic bounding box (27.4 <= lat <= 29.5,
   -18.3 <= lng <= -13.3) so mainland Spain hotels can never false-match.
3. ONLY inserts properties that have a REAL verified guest rating (> 0) and
   verified coordinates from Nuitée Connect — zero fabricated scores or reviews.
4. Extracts standout/watch_out/facilities strictly from Nuitée Connect data.
"""
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# (slug, name, location_label, brand, search_hint)
CANARY_CANDIDATES: list[tuple[str, str, str, str, str]] = [
    # --- TENERIFE ---
    ("ritz-carlton-abama-tenerife", "The Ritz-Carlton, Abama", "Guía de Isora, Tenerife", "Ritz-Carlton", "Ritz-Carlton Abama"),
    ("bahia-del-duque-tenerife", "Bahía del Duque", "Costa Adeje, Tenerife", "Independent", "Bahia del Duque"),
    ("royal-hideaway-corales-beach-tenerife", "Royal Hideaway Corales Beach - Adults Only", "Costa Adeje, Tenerife", "Royal Hideaway", "Royal Hideaway Corales Beach"),
    ("royal-hideaway-corales-suites-tenerife", "Royal Hideaway Corales Suites", "Costa Adeje, Tenerife", "Royal Hideaway", "Royal Hideaway Corales Suites"),
    ("royal-river-luxury-hotel-tenerife", "Royal River Luxury Hotel - Adults Only", "Costa Adeje, Tenerife", "Independent", "Royal River Luxury"),
    ("iberostar-selection-anthelia-tenerife", "Iberostar Selection Anthelia", "Costa Adeje, Tenerife", "Iberostar", "Iberostar Selection Anthelia"),
    ("iberostar-grand-el-mirador-tenerife", "JOIA El Mirador by Iberostar - Adults Only", "Costa Adeje, Tenerife", "Iberostar", "El Mirador Iberostar"),
    ("iberostar-selection-sabila-tenerife", "Iberostar Selection Sábila - Adults Only", "Costa Adeje, Tenerife", "Iberostar", "Iberostar Selection Sabila"),
    ("iberostar-heritage-grand-mencey-tenerife", "Iberostar Heritage Grand Mencey", "Santa Cruz de Tenerife, Tenerife", "Iberostar", "Iberostar Heritage Grand Mencey"),
    ("gran-melia-palacio-de-isora-tenerife", "Gran Meliá Palacio de Isora", "Alcalá, Tenerife", "Gran Meliá", "Gran Melia Palacio de Isora"),
    ("tivoli-la-caleta-tenerife", "Tivoli La Caleta Tenerife Resort", "Costa Adeje, Tenerife", "Tivoli", "Tivoli La Caleta"),
    ("hard-rock-hotel-tenerife", "Hard Rock Hotel Tenerife", "Playa Paraíso, Tenerife", "Hard Rock", "Hard Rock Hotel Tenerife"),
    ("dreams-jardin-tropical-tenerife", "Dreams Jardín Tropical Resort & Spa", "Costa Adeje, Tenerife", "Dreams Resorts", "Dreams Jardin Tropical"),
    ("hotel-botanico-tenerife", "Hotel Botánico & The Oriental Spa Garden", "Puerto de la Cruz, Tenerife", "Independent", "Hotel Botanico Oriental Spa"),
    ("hotel-suite-villa-maria-tenerife", "Hotel Suite Villa María", "Costa Adeje, Tenerife", "Independent", "Hotel Suite Villa Maria"),
    ("vincci-seleccion-la-plantacion-del-sur-tenerife", "Vincci Selección La Plantación del Sur", "Costa Adeje, Tenerife", "Vincci Hoteles", "Vincci Seleccion La Plantacion"),
    ("jardines-de-nivaria-tenerife", "Adrián Hoteles Jardines de Nivaria", "Costa Adeje, Tenerife", "Adrián Hoteles", "Jardines de Nivaria"),
    ("roca-nivaria-gh-tenerife", "Adrián Hoteles Roca Nivaria GH", "Playa Paraíso, Tenerife", "Adrián Hoteles", "Roca Nivaria"),
    ("colon-guanahani-tenerife", "Adrián Hoteles Colón Guanahaní - Adults Only", "Costa Adeje, Tenerife", "Adrián Hoteles", "Colon Guanahani"),
    ("gf-victoria-tenerife", "GF Victoria", "Costa Adeje, Tenerife", "GF Hoteles", "GF Victoria"),
    ("gf-gran-costa-adeje-tenerife", "GF Gran Costa Adeje", "Costa Adeje, Tenerife", "GF Hoteles", "GF Gran Costa Adeje"),
    ("gf-fanabe-tenerife", "GF Fañabé", "Costa Adeje, Tenerife", "GF Hoteles", "GF Fanabe"),
    ("h10-costa-adeje-palace-tenerife", "H10 Costa Adeje Palace", "Costa Adeje, Tenerife", "H10 Hotels", "H10 Costa Adeje Palace"),
    ("h10-atlantic-sunset-tenerife", "H10 Atlantic Sunset Horizons Collection", "Playa Paraíso, Tenerife", "H10 Hotels", "H10 Atlantic Sunset"),
    ("h10-conquistador-tenerife", "H10 Conquistador", "Playa de las Américas, Tenerife", "H10 Hotels", "H10 Conquistador"),
    ("riu-palace-tenerife", "Hotel Riu Palace Tenerife", "Costa Adeje, Tenerife", "RIU Hotels", "Riu Palace Tenerife"),
    ("riu-arecas-tenerife", "Hotel Riu Arecas - Adults Only", "Costa Adeje, Tenerife", "RIU Hotels", "Riu Arecas"),
    ("barcelo-tenerife", "Barceló Tenerife", "San Miguel de Abona, Tenerife", "Barceló", "Barcelo Tenerife"),
    ("barcelo-santiago-tenerife", "Barceló Santiago - Adults Only", "Puerto de Santiago, Tenerife", "Barceló", "Barcelo Santiago"),
    ("spring-hotel-bitacora-tenerife", "Spring Hotel Bitácora", "Playa de las Américas, Tenerife", "Spring Hotels", "Spring Hotel Bitacora"),
    ("landmar-costa-los-gigantes-tenerife", "Landmar Costa Los Gigantes Family Resort", "Puerto de Santiago, Tenerife", "Landmar Hotels", "Landmar Costa Los Gigantes"),
    ("landmar-playa-la-arena-tenerife", "Landmar Playa La Arena", "Puerto de Santiago, Tenerife", "Landmar Hotels", "Landmar Playa La Arena"),
    ("sandos-san-blas-tenerife", "Sandos San Blas Eco Resort", "San Miguel de Abona, Tenerife", "Sandos", "Sandos San Blas"),
    ("bahia-principe-fantasia-tenerife", "Bahia Principe Fantasia Tenerife", "San Miguel de Abona, Tenerife", "Bahia Principe", "Bahia Principe Fantasia Tenerife"),
    ("bahia-principe-sunlight-costa-adeje-tenerife", "Bahia Principe Sunlight Costa Adeje", "Costa Adeje, Tenerife", "Bahia Principe", "Bahia Principe Sunlight Costa Adeje"),
    ("alua-atlantico-golf-tenerife", "Alua Atlántico Golf Resort", "San Miguel de Abona, Tenerife", "Alua Hotels", "Alua Atlantico Golf"),
    ("melia-jardines-del-teide-tenerife", "Meliá Jardines del Teide - Adults Only", "Costa Adeje, Tenerife", "Meliá", "Melia Jardines del Teide"),
    # --- LANZAROTE ---
    ("princesa-yaiza-lanzarote", "Princesa Yaiza Suite Hotel Resort", "Playa Blanca, Lanzarote", "Independent", "Princesa Yaiza"),
    ("lanis-suites-de-luxe-lanzarote", "Lani's Suites de Luxe - Adults Only", "Puerto del Carmen, Lanzarote", "Independent", "Lanis Suites de Luxe"),
    ("hotel-fariones-lanzarote", "Hotel Fariones", "Puerto del Carmen, Lanzarote", "Independent", "Hotel Fariones"),
    ("secrets-lanzarote-resort-and-spa", "Secrets Lanzarote Resort & Spa - Adults Only", "Puerto Calero, Lanzarote", "Secrets Resorts", "Secrets Lanzarote"),
    ("dreams-lanzarote-playa-dorada", "Dreams Lanzarote Playa Dorada Resort & Spa", "Playa Blanca, Lanzarote", "Dreams Resorts", "Dreams Lanzarote Playa Dorada"),
    ("paradisus-salinas-lanzarote", "Paradisus by Meliá Salinas Lanzarote - Adults Only", "Costa Teguise, Lanzarote", "Paradisus by Meliá", "Paradisus Salinas Lanzarote"),
    ("hotel-lava-beach-lanzarote", "Hotel Lava Beach", "Puerto del Carmen, Lanzarote", "Independent", "Hotel Lava Beach"),
    ("hotel-volcan-lanzarote", "Hotel Volcán Lanzarote", "Playa Blanca, Lanzarote", "Independent", "Hotel Volcan Lanzarote"),
    ("arrecife-gran-hotel-lanzarote", "Arrecife Gran Hotel & Spa", "Arrecife, Lanzarote", "Independent", "Arrecife Gran Hotel"),
    ("iberostar-selection-lanzarote-park", "Iberostar Selection Lanzarote Park", "Playa Blanca, Lanzarote", "Iberostar", "Iberostar Selection Lanzarote Park"),
    ("h10-rubicon-palace-lanzarote", "H10 Rubicón Horizons Collection", "Playa Blanca, Lanzarote", "H10 Hotels", "H10 Rubicon"),
    ("h10-timanfaya-palace-lanzarote", "H10 Timanfaya Palace - Adults Only", "Playa Blanca, Lanzarote", "H10 Hotels", "H10 Timanfaya Palace"),
    ("h10-lanzarote-princess", "H10 Lanzarote Princess", "Playa Blanca, Lanzarote", "H10 Hotels", "H10 Lanzarote Princess"),
    ("barcelo-playa-blanca-lanzarote", "Barceló Playa Blanca", "Playa Blanca, Lanzarote", "Barceló", "Barcelo Playa Blanca"),
    ("barcelo-teguise-beach-lanzarote", "Barceló Teguise Beach - Adults Only", "Costa Teguise, Lanzarote", "Barceló", "Barcelo Teguise Beach"),
    ("sandos-papagayo-lanzarote", "Sandos Papagayo", "Playa Blanca, Lanzarote", "Sandos", "Sandos Papagayo"),
    ("hipotels-natura-palace-lanzarote", "Hipotels Natura Palace - Adults Only", "Playa Blanca, Lanzarote", "Hipotels", "Hipotels Natura Palace"),
    ("elba-lanzarote-royal-village", "Elba Lanzarote Royal Village Resort", "Playa Blanca, Lanzarote", "Elba Hotels", "Elba Lanzarote Royal Village"),
    ("riu-paraiso-lanzarote", "Hotel Riu Paraiso Lanzarote", "Puerto del Carmen, Lanzarote", "RIU Hotels", "Riu Paraiso Lanzarote"),
    # --- GRAN CANARIA ---
    ("seaside-grand-hotel-residencia-gran-canaria", "Seaside Grand Hotel Residencia", "Maspalomas, Gran Canaria", "Seaside Collection", "Seaside Grand Hotel Residencia"),
    ("seaside-palm-beach-gran-canaria", "Seaside Palm Beach", "Maspalomas, Gran Canaria", "Seaside Collection", "Seaside Palm Beach"),
    ("santa-catalina-royal-hideaway-gran-canaria", "Santa Catalina, a Royal Hideaway Hotel", "Las Palmas, Gran Canaria", "Royal Hideaway", "Santa Catalina Royal Hideaway"),
    ("lopesan-villa-del-conde-gran-canaria", "Lopesan Villa del Conde Resort & Thalasso", "Meloneras, Gran Canaria", "Lopesan", "Lopesan Villa del Conde"),
    ("lopesan-baobab-resort-gran-canaria", "Lopesan Baobab Resort", "Meloneras, Gran Canaria", "Lopesan", "Lopesan Baobab"),
    ("lopesan-costa-meloneras-gran-canaria", "Lopesan Costa Meloneras Resort & Spa", "Meloneras, Gran Canaria", "Lopesan", "Lopesan Costa Meloneras"),
    ("salobre-hotel-resort-gran-canaria", "Salobre Hotel Resort & Serenity", "Maspalomas, Gran Canaria", "Independent", "Salobre Hotel Resort"),
    ("radisson-blu-resort-gran-canaria", "Radisson Blu Resort, Gran Canaria", "Arguineguín, Gran Canaria", "Radisson Blu", "Radisson Blu Resort Gran Canaria"),
    ("radisson-blu-mogan-gran-canaria", "Radisson Blu Resort & Spa, Gran Canaria Mogán", "Puerto de Mogán, Gran Canaria", "Radisson Blu", "Radisson Blu Mogan"),
    ("paradisus-gran-canaria", "Paradisus by Meliá Gran Canaria", "San Agustín, Gran Canaria", "Paradisus by Meliá", "Paradisus Gran Canaria"),
    ("riu-palace-meloneras-gran-canaria", "Hotel Riu Palace Meloneras", "Meloneras, Gran Canaria", "RIU Hotels", "Riu Palace Meloneras"),
    ("riu-palace-maspalomas-gran-canaria", "Hotel Riu Palace Maspalomas - Adults Only", "Maspalomas, Gran Canaria", "RIU Hotels", "Riu Palace Maspalomas"),
    ("riu-gran-canaria", "Hotel Riu Gran Canaria", "Meloneras, Gran Canaria", "RIU Hotels", "Riu Gran Canaria"),
    ("h10-playa-meloneras-palace-gran-canaria", "H10 Playa Meloneras Horizons Collection", "Meloneras, Gran Canaria", "H10 Hotels", "H10 Playa Meloneras"),
    ("cordial-mogan-playa-gran-canaria", "Hotel Cordial Mogán Playa", "Puerto de Mogán, Gran Canaria", "Be Cordial", "Cordial Mogan Playa"),
    ("gloria-palace-royal-gran-canaria", "Gloria Palace Royal Hotel & Spa", "Amadores, Gran Canaria", "Gloria Thalasso", "Gloria Palace Royal"),
    ("gloria-palace-amadores-gran-canaria", "Gloria Palace Amadores Thalasso & Hotel", "Amadores, Gran Canaria", "Gloria Thalasso", "Gloria Palace Amadores"),
    ("bohemia-suites-and-spa-gran-canaria", "Bohemia Suites & Spa - Adults Only", "Playa del Inglés, Gran Canaria", "Independent", "Bohemia Suites Spa"),
    ("taurito-princess-gran-canaria", "Taurito Princess", "Taurito, Gran Canaria", "Princess Hotels", "Taurito Princess"),
    # --- FUERTEVENTURA ---
    ("secrets-bahia-real-fuerteventura", "Secrets Bahía Real Resort & Spa - Adults Only", "Corralejo, Fuerteventura", "Secrets Resorts", "Secrets Bahia Real"),
    ("iberostar-selection-fuerteventura-palace", "Iberostar Selection Fuerteventura Palace", "Jandía, Fuerteventura", "Iberostar", "Iberostar Selection Fuerteventura Palace"),
    ("iberostar-playa-gaviotas-park-fuerteventura", "Iberostar Waves Gaviotas Park", "Jandía, Fuerteventura", "Iberostar", "Iberostar Gaviotas Park"),
    ("riu-palace-tres-islas-fuerteventura", "Hotel Riu Palace Tres Islas", "Corralejo, Fuerteventura", "RIU Hotels", "Riu Palace Tres Islas"),
    ("riu-palace-jandia-fuerteventura", "Hotel Riu Palace Jandia", "Morro Jable, Fuerteventura", "RIU Hotels", "Riu Palace Jandia"),
    ("barcelo-fuerteventura-mar", "Barceló Fuerteventura Mar", "Caleta de Fuste, Fuerteventura", "Barceló", "Barcelo Fuerteventura Mar"),
    ("barcelo-corralejo-bay-fuerteventura", "Barceló Corralejo Bay - Adults Only", "Corralejo, Fuerteventura", "Barceló", "Barcelo Corralejo Bay"),
    ("elba-palace-golf-fuerteventura", "Elba Palace Golf Boutique Hotel - Adults Only", "Caleta de Fuste, Fuerteventura", "Elba Hotels", "Elba Palace Golf"),
    ("fuerteventura-princess", "Fuerteventura Princess", "Esquinzo, Fuerteventura", "Princess Hotels", "Fuerteventura Princess"),
    ("h10-ocean-suites-fuerteventura", "H10 Ocean Suites", "Corralejo, Fuerteventura", "H10 Hotels", "H10 Ocean Suites"),
    ("melia-fuerteventura", "Meliá Fuerteventura", "Costa Calma, Fuerteventura", "Meliá", "Melia Fuerteventura"),
    ("sheraton-fuerteventura", "Sheraton Fuerteventura Beach, Golf & Spa Resort", "Caleta de Fuste, Fuerteventura", "Sheraton", "Sheraton Fuerteventura"),
    # --- LA GOMERA & LA PALMA ---
    ("hotel-jardin-tecina-la-gomera", "Hotel Jardín Tecina", "Playa de Santiago, La Gomera", "Independent", "Hotel Jardin Tecina"),
    ("parador-de-la-gomera", "Parador de La Gomera", "San Sebastián, La Gomera", "Paradores", "Parador de La Gomera"),
    ("hotel-hacienda-de-abajo-la-palma", "Hotel Hacienda de Abajo - Adults Only", "Tazacorte, La Palma", "Independent", "Hacienda de Abajo"),
    ("la-palma-princess", "La Palma Princess", "Fuencaliente, La Palma", "Princess Hotels", "La Palma Princess"),
]


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


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_tokens(text: str) -> set[str]:
    stop = {"the", "a", "an", "hotel", "hotels", "resort", "resorts", "spa", "and", "de", "del", "la", "las", "el", "by", "adults", "only", "collection", "selection"}
    clean = strip_accents(text).lower().replace("&", " ")
    toks = set(re.findall(r"[a-z0-9]+", clean))
    filtered = toks - stop
    return filtered if filtered else toks


def in_canary_bbox(lat: Any, lng: Any) -> bool:
    try:
        la = float(lat)
        lo = float(lng)
    except (TypeError, ValueError):
        return False
    return 27.4 <= la <= 29.5 and -18.4 <= lo <= -13.2


def nuitee_get(path: str, api_key: str) -> dict[str, Any] | None:
    url = f"https://api.liteapi.travel{path}"
    req = urllib.request.Request(
        url,
        headers={"X-API-Key": api_key, "Accept": "application/json", "User-Agent": "StayOddsCanary/1.0"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=16) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                time.sleep(1.2 * (attempt + 1))
                continue
            return None
        except Exception:
            if attempt < 2:
                time.sleep(0.4)
                continue
            return None
    return None


def find_canary_nuitee(name: str, hint: str, api_key: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    queries = []
    for q in [hint, strip_accents(name), re.split(r"[,—–-]", strip_accents(name))[0].strip()]:
        if q and len(q) >= 4 and q not in queries:
            queries.append(q)

    target_toks = norm_tokens(hint) | norm_tokens(name)
    for q in queries[:3]:
        qs = urllib.parse.urlencode({"countryCode": "ES", "hotelName": q, "limit": 10})
        res = nuitee_get(f"/v3.0/data/hotels?{qs}", api_key)
        items = (res or {}).get("data") or []
        best = None
        best_score = 0.0
        for item in items:
            lat = item.get("latitude")
            lng = item.get("longitude")
            if not in_canary_bbox(lat, lng):
                continue
            cand_toks = norm_tokens(str(item.get("name") or ""))
            if not cand_toks:
                continue
            hint_toks = norm_tokens(hint)
            overlap_h = len(hint_toks & cand_toks) / max(1, len(hint_toks))
            overlap_c = len(target_toks & cand_toks) / max(1, len(cand_toks))
            if overlap_h < 0.55 and overlap_c < 0.65:
                continue
            score = overlap_h * 0.65 + overlap_c * 0.35 + (0.08 if (item.get("rating") or 0) > 0 else 0.0)
            if score > best_score:
                best_score = score
                best = item
        if best and best.get("id"):
            det_res = nuitee_get(f"/v3.0/data/hotel?hotelId={urllib.parse.quote(str(best['id']))}", api_key)
            detail = (det_res or {}).get("data")
            return best, detail
    return None, None


def extract_facts(detail: dict[str, Any], name: str) -> dict[str, Any]:
    facilities = [str(f).strip() for f in (detail.get("hotelFacilities") or []) if f]
    fac_low = [f.lower() for f in facilities]
    desc = strip_accents(str(detail.get("hotelDescription") or "")).lower()
    blob = " ".join(fac_low) + " " + desc + " " + name.lower()

    pool_heating = ""
    if any("heated pool" in f for f in fac_low) or "heated pool" in desc:
        pool_heating = "Heated pool confirmed"
    elif any("indoor pool" in f for f in fac_low) and any("outdoor pool" in f for f in fac_low):
        pool_heating = "Indoor & outdoor pools"
    elif any("infinity pool" in f for f in fac_low):
        pool_heating = "Infinity pool on property"
    elif any("swimming pool" in f or "outdoor pool" in f for f in fac_low):
        pool_heating = "Outdoor pool listed"

    beach_or_reef = ""
    if any("private beach" in f for f in fac_low):
        beach_or_reef = "Private beach area"
    elif any("beachfront" in f or "on the beach" in f or "beach access" in f for f in fac_low) or "beachfront" in desc:
        beach_or_reef = "Direct beachfront access"

    airport = str(detail.get("airportCode") or "").strip().upper()
    has_shuttle = any("airport shuttle" in f or "airport transfer" in f for f in fac_low)
    transfer = ""
    if airport and has_shuttle:
        transfer = f"Airport transfers available (nearest code: {airport})"
    elif airport:
        transfer = f"Nearest airport code: {airport}"
    elif has_shuttle:
        transfer = "Airport shuttle / transfer service listed"

    tags: list[str] = []
    if "all-inclusive" in blob or "all inclusive" in blob:
        tags.append("All-Inclusive Available")
    if "adults only" in blob or "adults-only" in blob or "adult only" in blob:
        tags.append("Adults-Only")
    if any(k in blob for k in ("kids club", "kids' club", "children's club", "water park", "waterpark", "playground", "family rooms")):
        tags.append("Family & Kids-Friendly")

    sa = detail.get("sentiment_analysis") or {}
    pros = [str(p).strip() for p in (sa.get("pros") or []) if p]
    cons = [str(c).strip() for c in (sa.get("cons") or []) if c]

    standout = " • ".join(pros[:2]) if pros else (" • ".join(tags[:2]) if tags else "")
    watch_out = " • ".join(cons[:2]) if cons else ""

    red_flags: list[str] = []
    cons_blob = " ".join(cons).lower()
    if any(k in cons_blob for k in ["expensive", "overpriced", "high price", "costly"]):
        red_flags.append("High On-Property Pricing")
    if any(k in cons_blob for k in ["dated", "aged", "maintenance", "worn", "old"]):
        red_flags.append("Aging Finish Noted")
    if any(k in cons_blob for k in ["noisy", "noise", "crowded", "busy", "sunbed"]):
        red_flags.append("Noise / Crowds Noted")

    # Preserve verified profile cues in source_note so guest-profile & style classifiers detect them accurately
    src_bits = ["Nuitée Connect verified facilities & guest themes"]
    if tags:
        src_bits.append("Verified profile: " + ", ".join(tags))

    return {
        "pool_heating": pool_heating,
        "beach_or_reef": beach_or_reef,
        "transfer_logistics": transfer,
        "standout": standout,
        "watch_out": watch_out,
        "red_flag_tags": red_flags[:4],
        "source_note": " | ".join(src_bits),
    }


def sb_upsert(url: str, secret_key: str, table: str, rows: list[dict[str, Any]], on_conflict: str) -> None:
    if not rows:
        return
    for i in range(0, len(rows), 80):
        batch = rows[i : i + 80]
        endpoint = f"{url}/rest/v1/{table}?on_conflict={urllib.parse.quote(on_conflict)}"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(batch).encode("utf-8"),
            headers={
                "apikey": secret_key,
                "Authorization": f"Bearer {secret_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201, 204):
                raise RuntimeError(f"Upsert {table} failed with HTTP {resp.status}")


def main() -> None:
    load_env_local()
    sb_url = os.environ["SUPABASE_URL"].rstrip("/")
    sb_secret = os.environ["SUPABASE_SECRET_KEY"]
    nuitee_key = os.environ["NUITEE_API_KEY"].strip()

    print(f"Matching {len(CANARY_CANDIDATES)} Canary Islands hotels against FREE Nuitée Connect (strict bbox + real rating > 0)...", flush=True)

    def worker(entry: tuple[str, str, str, str, str]) -> dict[str, Any]:
        slug, name, loc, brand, hint = entry
        match, detail = find_canary_nuitee(name, hint, nuitee_key)
        return {"slug": slug, "name": name, "loc": loc, "brand": brand, "match": match, "detail": detail}

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(worker, c) for c in CANARY_CANDIDATES]
        done = 0
        for fut in as_completed(futs):
            results.append(fut.result())
            done += 1
            if done % 20 == 0 or done == len(CANARY_CANDIDATES):
                print(f"  Checked {done}/{len(CANARY_CANDIDATES)}...", flush=True)

    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    prop_rows: list[dict[str, Any]] = []
    fact_rows: list[dict[str, Any]] = []
    guest_rows: list[dict[str, Any]] = []
    booking_rows: list[dict[str, Any]] = []
    seen_nuitee_ids: set[str] = set()
    skipped: list[tuple[str, str]] = []

    for r in results:
        match = r["match"] or {}
        detail = r["detail"] or {}
        nid = str(detail.get("id") or match.get("id") or "").strip()
        if not nid:
            skipped.append((r["slug"], "no_nuitee_match"))
            continue
        if nid in seen_nuitee_ids:
            skipped.append((r["slug"], f"duplicate_nuitee_{nid}"))
            continue

        # Strict REAL rating > 0 requirement (no unrated shells!)
        raw_rating = detail.get("rating") if detail.get("rating") is not None else match.get("rating")
        raw_reviews = detail.get("reviewCount") if detail.get("reviewCount") is not None else match.get("reviewCount")
        try:
            r_num = float(raw_rating) if raw_rating not in (None, "", 0, "0") else 0.0
        except (TypeError, ValueError):
            r_num = 0.0
        if r_num <= 0:
            skipped.append((r["slug"], "no_verified_rating"))
            continue

        lat = (detail.get("location") or {}).get("latitude") or match.get("latitude")
        lng = (detail.get("location") or {}).get("longitude") or match.get("longitude")
        if not in_canary_bbox(lat, lng):
            skipped.append((r["slug"], f"outside_canary_bbox_{lat}_{lng}"))
            continue

        seen_nuitee_ids.add(nid)
        pid = r["slug"]

        hero = str(detail.get("main_photo") or match.get("main_photo") or "").strip()
        if not hero:
            imgs = detail.get("hotelImages") or []
            if imgs and isinstance(imgs[0], dict):
                hero = str(imgs[0].get("url") or "").strip()

        prop_rows.append(
            {
                "id": pid,
                "name": r["name"],
                "brand": r["brand"],
                "city": r["loc"],
                "country": "Spain",
                "region": "Europe",
                "lat": float(lat),
                "lng": float(lng),
                "tier": "global_directory",
                "visited_by_founder": False,
                "nuitee_hotel_id": nid,
                "price_tier": "",
                "hero_image_url": hero,
                "image_license_source": "nuitee_connect" if hero else "editorial",
                "updated_at": now_iso,
            }
        )

        kf = extract_facts(detail, r["name"])
        fact_rows.append(
            {
                "property_id": pid,
                "standout": kf["standout"],
                "watch_out": kf["watch_out"],
                "pool_heating": kf["pool_heating"],
                "beach_or_reef": kf["beach_or_reef"],
                "transfer_logistics": kf["transfer_logistics"],
                "red_flag_tags": kf["red_flag_tags"],
                "source_note": kf["source_note"],
                "verified_at": now_iso,
            }
        )

        scale = 10.0 if r_num > 5.0 else 5.0
        norm100 = max(1, min(100, int(round((r_num / scale) * 100))))
        try:
            rev_cnt = int(raw_reviews) if raw_reviews not in (None, "") else None
        except (TypeError, ValueError):
            rev_cnt = None
        guest_rows.append(
            {
                "property_id": pid,
                "partner_source": "nuitee_connect",
                "rating": round(r_num, 2),
                "scale": scale,
                "normalized_100": norm100,
                "review_count": rev_cnt,
                "attribution": "Verified Guest Score",
                "verified_at": now_iso,
            }
        )

        b_url = f"https://www.booking.com/searchresults.html?ss={urllib.parse.quote_plus(r['name'] + ' ' + r['loc'])}"
        booking_rows.append(
            {
                "property_id": pid,
                "channel_type": "ota_affiliate",
                "partner_name": "Booking.com",
                "url": b_url,
                "mobile_allowed": False,
                "perks_summary": "",
                "priority": 1,
                "updated_at": now_iso,
            }
        )
        booking_rows.append(
            {
                "property_id": pid,
                "channel_type": "direct_brand",
                "partner_name": "StayOdds Web Rates",
                "url": f"https://stayodds.com/stayodds/{pid}/",
                "mobile_allowed": True,
                "perks_summary": "Compare live rates & verified reviews on StayOdds.com",
                "priority": 2,
                "updated_at": now_iso,
            }
        )

    sb_upsert(sb_url, sb_secret, "properties", prop_rows, "id")
    sb_upsert(sb_url, sb_secret, "property_facts", fact_rows, "property_id")
    sb_upsert(sb_url, sb_secret, "licensed_guest_scores", guest_rows, "property_id,partner_source")
    sb_upsert(sb_url, sb_secret, "booking_links", booking_rows, "property_id,channel_type,partner_name")

    by_island: dict[str, int] = {}
    for p in prop_rows:
        isl = p["city"].split(",")[-1].strip()
        by_island[isl] = by_island.get(isl, 0) + 1

    print(
        f"\nCANARY ISLANDS INGESTION COMPLETE:\n"
        f"  Verified rated Canary Islands hotels added: {len(prop_rows)} / {len(CANARY_CANDIDATES)}\n"
        f"  By island: {by_island}\n"
        f"  Skipped ({len(skipped)}): {skipped[:15]}"
    )


if __name__ == "__main__":
    main()
