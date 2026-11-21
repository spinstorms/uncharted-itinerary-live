#!/usr/bin/env python3
"""
Sync engine for The Uncharted Itinerary Live Hub.
Zero external dependencies (Python 3.10+ stdlib only).

What it does:
1. Fetches latest long-form videos (UULF) and Shorts (UUSH) from YouTube RSS (no API key needed).
2. Preserves historical archive in data/videos.json so older videos are never lost.
3. Parses chapter timestamps, locations, categories, and affiliate links from descriptions.
4. Generates editorial AI summaries via Gemini API (GEMINI_API_KEY) or OpenAI API (OPENAI_API_KEY),
   with a clean structured fallback if no key is configured yet.
5. Merges curated affiliate links from a published Google Sheet CSV (AFFILIATE_SHEET_CSV_URL or config.json)
   with auto-extracted YouTube description links into data/affiliates.json.
"""

from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DATA_DIR = ROOT / "data"
VIDEOS_PATH = DATA_DIR / "videos.json"
AFFILIATES_PATH = DATA_DIR / "affiliates.json"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}

SOCIAL_IGNORE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "tiktok.com",
    "www.tiktok.com",
    "twitter.com",
    "x.com",
    "uncharteditinerary.com",
    "www.uncharteditinerary.com",
}

DEFAULT_CURATED_AFFILIATES = [
    {
        "id": "curated-amex-gold-uk",
        "source": "curated",
        "featured": True,
        "category": "Points & Cards",
        "title": "American Express Preferred Rewards Gold (UK)",
        "badge": "Bonus Points",
        "description": "Earn bonus Membership Rewards points toward luxury hotel stays and business class flights when applying via our referral link.",
        "promoCode": "",
        "url": "https://americanexpress.com/en-gb/referral/gold-credit?ref=oLIVEK1B4w",
        "buttonLabel": "Claim Referral Bonus",
        "sortOrder": 1,
    },
    {
        "id": "curated-marriott-currensea",
        "source": "curated",
        "featured": True,
        "category": "Points & Cards",
        "title": "Marriott Bonvoy Currensea Debit Card",
        "badge": "Up to 2,000 Bonus Pts",
        "description": "Earn Marriott Bonvoy points on everyday spending with low foreign transaction fees—our go-to card for luxury hotel stays.",
        "promoCode": "OKM2ZH",
        "url": "https://marriottbonvoy.currensea.co.uk/refer-a-friend?utm_source=refer-a-friend&friend-referral-code=OKM2ZH",
        "buttonLabel": "Get Card & Bonus",
        "sortOrder": 2,
    },
    {
        "id": "curated-insta360-standard",
        "source": "curated",
        "featured": True,
        "category": "Camera & Travel Gear",
        "title": "Insta360 Luna Ultra — Standard Kit",
        "badge": "Filming Setup",
        "description": "Our compact main travel camera used to film resort walkthroughs, room tours, and island adventures.",
        "promoCode": "",
        "url": "https://link.amazon/B0fpiIMTi",
        "buttonLabel": "Shop on Amazon",
        "sortOrder": 3,
    },
    {
        "id": "curated-insta360-creator-black",
        "source": "curated",
        "featured": False,
        "category": "Camera & Travel Gear",
        "title": "Insta360 Luna Ultra — Creator Kit (Black)",
        "badge": "Filming Setup",
        "description": "Complete Creator Kit in Matte Black with extra accessories for travel vlogging.",
        "promoCode": "",
        "url": "https://link.amazon/B03YstgcC",
        "buttonLabel": "Shop on Amazon",
        "sortOrder": 4,
    },
    {
        "id": "curated-insta360-creator-white",
        "source": "curated",
        "featured": False,
        "category": "Camera & Travel Gear",
        "title": "Insta360 Luna Ultra — Creator Kit (White)",
        "badge": "Filming Setup",
        "description": "Complete Creator Kit in Arctic White—lightweight and easy to pack for long-haul trips.",
        "promoCode": "",
        "url": "https://link.amazon/B09TARLyD",
        "buttonLabel": "Shop on Amazon",
        "sortOrder": 5,
    },
    {
        "id": "curated-insta360-wide-lens",
        "source": "curated",
        "featured": False,
        "category": "Camera & Travel Gear",
        "title": "Insta360 Luna Ultra Wide Angle Lens",
        "badge": "Gear Essential",
        "description": "Essential ultra-wide attachment for capturing full hotel suites, villas, and ocean views in tight spaces.",
        "promoCode": "",
        "url": "https://link.amazon/B00hjVInJ",
        "buttonLabel": "Shop on Amazon",
        "sortOrder": 6,
    },
    {
        "id": "curated-insta360-battery",
        "source": "curated",
        "featured": False,
        "category": "Camera & Travel Gear",
        "title": "Insta360 Luna Ultra Battery Handle",
        "badge": "Gear Essential",
        "description": "All-day battery grip for shooting full-property resort tours without running out of charge.",
        "promoCode": "",
        "url": "https://link.amazon/B0cxr0rKz",
        "buttonLabel": "Shop on Amazon",
        "sortOrder": 7,
    },
    {
        "id": "curated-epidemic-sound",
        "source": "curated",
        "featured": False,
        "category": "Creator Tools",
        "title": "Epidemic Sound — Royalty-Free Travel Music",
        "badge": "Creator Referral",
        "description": "The music library behind our cinematic resort tours and travel guides. Start a free trial via our link.",
        "promoCode": "",
        "url": "https://www.epidemicsound.com/referral/vo2tr9/",
        "buttonLabel": "Try Epidemic Sound",
        "sortOrder": 8,
    },
    {
        "id": "curated-tubebuddy",
        "source": "curated",
        "featured": False,
        "category": "Creator Tools",
        "title": "TubeBuddy — YouTube SEO & Growth",
        "badge": "Creator Tool",
        "description": "What we use to research keywords, optimize video tags, and grow The Uncharted Itinerary channel.",
        "promoCode": "",
        "url": "https://www.tubebuddy.com/Techinthecar",
        "buttonLabel": "Explore TubeBuddy",
        "sortOrder": 9,
    },
    {
        "id": "curated-octopus-energy",
        "source": "curated",
        "featured": False,
        "category": "Everyday Perks",
        "title": "Octopus Energy (UK)",
        "badge": "£50 Credit",
        "description": "Switch to Octopus Energy with our referral link and we both receive £50 credit toward your energy bill.",
        "promoCode": "",
        "url": "https://share.octopus.energy/jolly-skunk-453",
        "buttonLabel": "Claim £50 Credit",
        "sortOrder": 10,
    },
    {
        "id": "curated-freetrade",
        "source": "curated",
        "featured": False,
        "category": "Everyday Perks",
        "title": "Freetrade — Commission-Free Investing",
        "badge": "Free Share £3–£200",
        "description": "Join Freetrade via our link to get a free share worth between £3 and £200 when you fund your account.",
        "promoCode": "",
        "url": "https://magic.freetrade.io/join/oliver/238af2d9",
        "buttonLabel": "Get Free Share",
        "sortOrder": 11,
    },
]


def http_get_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; UnchartedItinerarySync/1.0)",
            "Accept": "application/xml,text/csv,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def normalize_url(raw: str) -> str:
    cleaned = html.unescape(raw).strip()
    cleaned = cleaned.rstrip(".,;:!?)>]}")
    return cleaned


def url_dedupe_key(url: str) -> str:
    parsed = urllib.parse.urlsplit(normalize_url(url))
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    query = parsed.query
    return f"{host}{path}?{query}".rstrip("?")


def fetch_rss_entries(feed_url: str, is_short: bool) -> list[dict[str, Any]]:
    xml_text = http_get_text(feed_url)
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []

    for entry in root.findall("atom:entry", NS):
        vid_el = entry.find("yt:videoId", NS)
        title_el = entry.find("atom:title", NS)
        pub_el = entry.find("atom:published", NS)
        link_el = entry.find("atom:link", NS)
        desc_el = entry.find("media:group/media:description", NS)
        thumb_el = entry.find("media:group/media:thumbnail", NS)
        stats_el = entry.find("media:group/media:community/media:statistics", NS)

        if vid_el is None or not vid_el.text:
            continue

        vid = vid_el.text.strip()
        title = (title_el.text or "").strip() if title_el is not None else ""
        published = (pub_el.text or "").strip() if pub_el is not None else ""
        link = link_el.attrib.get("href", f"https://www.youtube.com/watch?v={vid}") if link_el is not None else f"https://www.youtube.com/watch?v={vid}"
        desc = (desc_el.text or "").strip() if desc_el is not None else ""
        views = int(stats_el.attrib.get("views", "0")) if stats_el is not None else 0
        thumbnail = (
            f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            if is_short
            else f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg"
        )
        fallback_thumb = thumb_el.attrib.get("url", f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg") if thumb_el is not None else f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"

        entries.append(
            {
                "id": vid,
                "title": title,
                "url": link,
                "publishedAt": published,
                "publishedDate": published[:10] if len(published) >= 10 else "",
                "isShort": is_short or ("/shorts/" in link),
                "thumbnail": thumbnail,
                "fallbackThumbnail": fallback_thumb,
                "views": views,
                "description": desc,
            }
        )
    return entries


def parse_chapters(description: str) -> list[dict[str, Any]]:
    chapters: list[dict[str, Any]] = []
    pattern = re.compile(r"^\s*(?:[-•*]\s*)?(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s*[-–—:|]?\s*(.+?)\s*$")
    for line in description.splitlines():
        m = pattern.match(line)
        if not m:
            continue
        hours = int(m.group(1) or 0)
        mins = int(m.group(2))
        secs = int(m.group(3))
        label = m.group(4).strip()
        if not label or len(label) < 2:
            continue
        total_sec = hours * 3600 + mins * 60 + secs
        ts = f"{hours}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"
        chapters.append({"time": ts, "seconds": total_sec, "label": label})
    return chapters[:20]


def infer_category(title: str, description: str, is_short: bool) -> str:
    blob = f"{title} {description[:500]}".lower()
    if any(k in blob for k in ["pocket 4", "osmo", "insta360", "luna ultra", "camera", "mic", "gimbal", "travel setup"]):
        return "Travel Gear"
    if any(k in blob for k in ["flight", "airline", "business class", "economy", "airport", "staff travel", "id90"]):
        return "Flights"
    if any(k in blob for k in ["bali", "uluwatu", "canggu", "seminyak", "ubud", "jimbaran", "nusa dua", "nusa penida", "lembongan", "gili", "komodo", "labuan bajo", "lombok"]):
        if any(k in blob for k in ["resort", "hotel", "villa", "st. regis", "ritz-carlton", "four seasons", "regent", "ungasan", "cocana", "ta'aktana", "w bali", "hiliwatu", "element"]):
            return "Hotel Reviews"
        return "Bali & Indonesia"
    if any(k in blob for k in ["maldives", "finolhu", "park hyatt maldives", "radisson blu maldives", "w maldives", "le meridien maldives"]):
        return "Maldives"
    if any(k in blob for k in ["resort", "hotel", "suite", "villa", "review", "w sardinia", "w algarve", "rayavadee", "westin", "phulay bay"]):
        return "Hotel Reviews"
    return "Shorts" if is_short else "Travel Guides"


def infer_location(title: str, description: str) -> str:
    # Check explicit "Resort Featured:" or "Location:" lines first
    m = re.search(r"(?:Resort Featured|Location|Destination)\s*:\s*\n?([^\n]+)", description, re.I)
    if m:
        loc_line = m.group(1).strip()
        paren = re.search(r"\(([^)]+)\)", loc_line)
        if paren:
            return paren.group(1).strip()
        if len(loc_line) < 60:
            return loc_line

    blob = f"{title} {description[:700]}".lower()
    places = [
        ("uluwatu", "Uluwatu, Bali"),
        ("canggu", "Canggu, Bali"),
        ("seminyak", "Seminyak, Bali"),
        ("jimbaran", "Jimbaran, Bali"),
        ("nusa dua", "Nusa Dua, Bali"),
        ("ubud", "Ubud, Bali"),
        ("nusa penida", "Nusa Penida, Indonesia"),
        ("nusa lembongan", "Nusa Lembongan, Bali"),
        ("gili t", "Gili Trawangan, Indonesia"),
        ("gili meno", "Gili Meno, Indonesia"),
        ("labuan bajo", "Labuan Bajo, Indonesia"),
        ("komodo", "Komodo National Park, Indonesia"),
        ("lombok", "Lombok, Indonesia"),
        ("maldives", "Maldives"),
        ("sardinia", "Costa Smeralda, Sardinia"),
        ("algarve", "Algarve, Portugal"),
        ("koh samui", "Koh Samui, Thailand"),
        ("krabi", "Krabi, Thailand"),
        ("bora bora", "Bora Bora, French Polynesia"),
        ("singapore", "Singapore"),
        ("bali", "Bali, Indonesia"),
    ]
    for needle, label in places:
        if needle in blob:
            return label
    return "Global Travel"


def classify_link(url: str, context_line: str) -> dict[str, str]:
    low_url = url.lower()
    low_ctx = context_line.lower()

    if "americanexpress.com" in low_url:
        return {
            "title": "American Express Preferred Rewards Gold (UK)",
            "category": "Points & Cards",
            "badge": "Bonus Points",
            "buttonLabel": "Claim Referral Bonus",
        }
    if "currensea" in low_url or "marriottbonvoy" in low_url:
        return {
            "title": "Marriott Bonvoy Currensea Debit Card",
            "category": "Points & Cards",
            "badge": "Up to 2,000 Bonus Pts",
            "buttonLabel": "Get Card & Bonus",
        }
    if "octopus.energy" in low_url:
        return {
            "title": "Octopus Energy (UK)",
            "category": "Everyday Perks",
            "badge": "£50 Credit",
            "buttonLabel": "Claim £50 Credit",
        }
    if "freetrade" in low_url:
        return {
            "title": "Freetrade Commission-Free Investing",
            "category": "Everyday Perks",
            "badge": "Free Share £3–£200",
            "buttonLabel": "Get Free Share",
        }
    if "epidemicsound" in low_url:
        return {
            "title": "Epidemic Sound — Royalty-Free Music",
            "category": "Creator Tools",
            "badge": "Creator Referral",
            "buttonLabel": "Try Epidemic Sound",
        }
    if "tubebuddy" in low_url:
        return {
            "title": "TubeBuddy — YouTube Growth Tool",
            "category": "Creator Tools",
            "badge": "Creator Tool",
            "buttonLabel": "Explore TubeBuddy",
        }
    if "amazon" in low_url or "amzn.to" in low_url:
        label = re.sub(r"https?://\S+", "", context_line).strip(" :-–—•")
        if label.lower() in {"black", "white"}:
            label = f"Insta360 Luna Ultra Creator Kit ({label.title()})"
        elif not label or len(label) < 4:
            label = "Featured Travel Gear (Amazon)"
        return {
            "title": label,
            "category": "Camera & Travel Gear",
            "badge": "Filming Gear",
            "buttonLabel": "Shop on Amazon",
        }
    if any(d in low_url for d in ["booking.com", "expedia", "hotels.com", "trip.com", "agoda", "marriott.com", "hilton.com"]):
        label = re.sub(r"https?://\S+", "", context_line).strip(" :-–—•") or "Book Featured Hotel"
        return {
            "title": label[:80],
            "category": "Hotels & Booking",
            "badge": "Hotel Partner",
            "buttonLabel": "Check Rates",
        }

    # Generic fallback from surrounding context
    label = re.sub(r"https?://\S+", "", context_line).strip(" :-–—•")
    host = urllib.parse.urlsplit(url).netloc.removeprefix("www.")
    title = label[:72] if len(label) >= 4 else host
    category = "Hotels & Booking" if any(k in low_ctx for k in ["book", "hotel", "resort", "stay", "villa"]) else "Travel & Perks"
    return {
        "title": title,
        "category": category,
        "badge": "From Video",
        "buttonLabel": "Open Link",
    }


def extract_affiliate_links(description: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    lines = description.splitlines()

    for idx, line in enumerate(lines):
        found = re.findall(r"https?://[^\s<>\"'\)\]]+", line)
        for raw_url in found:
            url = normalize_url(raw_url)
            host = urllib.parse.urlsplit(url).netloc.lower()
            if not host or host in SOCIAL_IGNORE_HOSTS:
                continue
            key = url_dedupe_key(url)
            if key in seen:
                continue
            seen.add(key)

            # Build context from current line or previous non-empty line
            line_without_url = re.sub(r"https?://\S+", "", line).strip(" :-–—•")
            prev_line = lines[idx - 1].strip() if idx > 0 else ""
            context = line_without_url if len(line_without_url) >= 4 else prev_line

            # Detect promo code if mentioned near the link
            promo_match = re.search(r"\bcode\s+([A-Z0-9]{4,16})\b", f"{prev_line} {line}")
            promo_code = promo_match.group(1) if promo_match else ""

            meta = classify_link(url, context)
            links.append(
                {
                    "title": meta["title"],
                    "category": meta["category"],
                    "badge": meta["badge"],
                    "buttonLabel": meta["buttonLabel"],
                    "promoCode": promo_code,
                    "url": url,
                    "dedupeKey": key,
                }
            )
    return links


def clean_description_intro(description: str) -> str:
    """Strip boilerplate affiliate/footer sections to keep the clean editorial body."""
    stop_markers = [
        "equipment used in this video",
        "amazon links",
        "want bonus points",
        "get £50 credit",
        "these links are affiliate",
        "we love feedback",
        "if you enjoyed this review",
        "don't forget to like",
        "⏱️ chapter",
        "chapter timestamps",
    ]
    kept_lines: list[str] = []
    for line in description.splitlines():
        low = line.strip().lower()
        if any(marker in low for marker in stop_markers):
            break
        if re.match(r"^\s*(?:(\d{1,2}):)?\d{1,2}:\d{2}\s+", line):
            break
        kept_lines.append(line.strip())
    text = "\n".join(kept_lines).strip()
    return text


def build_fallback_summary(title: str, description: str, chapters: list[dict[str, Any]], location: str, is_short: bool) -> dict[str, Any]:
    intro = clean_description_intro(description)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", intro) if p.strip() and not p.strip().startswith("#")]

    # Build clean 2-sentence TLDR
    tldr_source = " ".join(paragraphs[:2]) if paragraphs else title
    tldr_source = re.sub(r"https?://\S+", "", tldr_source)
    tldr_source = re.sub(r"\s+", " ", tldr_source).strip()
    sentences = re.split(r"(?<=[.!?])\s+", tldr_source)
    tldr = " ".join(sentences[:3]).strip()
    if len(tldr) > 290:
        tldr = tldr[:287].rsplit(" ", 1)[0] + "…"
    if not tldr:
        tldr = f"Quick travel highlight from {location}: {title}."

    # Extract bullet highlights from description bullets or chapter labels
    highlights: list[str] = []
    for line in intro.splitlines():
        s = line.strip()
        if s.startswith(("-", "•", "*")) and len(s) > 12:
            highlights.append(s.lstrip("-•* ").strip())
        elif re.match(r"^(Full |An honest |Pro Tip:|A taste |Comparison |The truth )", s):
            highlights.append(s)

    if len(highlights) < 3 and chapters:
        skip_labels = {"intro", "welcome", "outro", "final thoughts"}
        for ch in chapters:
            if ch["label"].lower() not in skip_labels and not ch["label"].lower().startswith("welcome to"):
                highlights.append(f"{ch['time']} — {ch['label']}")
            if len(highlights) >= 4:
                break

    if not highlights:
        highlights = [
            f"Destination focus: {location}",
            "First-hand walkthrough and honest impressions from The Uncharted Itinerary",
        ]

    best_for = (
        f"Quick visual preview from {location}"
        if is_short
        else f"Travelers researching stays and itineraries in {location}"
    )

    return {
        "tldr": tldr,
        "highlights": highlights[:4],
        "bestFor": best_for,
        "aiGenerated": False,
        "model": "auto-extracted",
    }


def call_gemini_summary(title: str, description: str, chapters: list[dict[str, Any]], api_key: str) -> dict[str, Any] | None:
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={urllib.parse.quote(api_key)}"
    intro = clean_description_intro(description)[:2200]
    chapter_text = "\n".join(f"{c['time']} - {c['label']}" for c in chapters[:15])

    prompt = (
        "You are an editorial travel writer for 'The Uncharted Itinerary' (luxury hotels, resorts, flights, and travel gear).\n"
        "Summarize this YouTube video strictly from the provided title, description, and chapters. Do not invent facts or prices not stated.\n"
        "Return ONLY valid JSON with keys:\n"
        '{"tldr": "2-3 crisp editorial sentences", "highlights": ["3 to 4 concise bullet takeaways"], '
        '"bestFor": "short 6-12 word audience fit", "location": "City/Region, Country", '
        '"category": "one of: Hotel Reviews, Bali & Indonesia, Maldives, Flights, Travel Gear, Travel Guides"}\n\n'
        f"TITLE: {title}\n"
        f"DESCRIPTION:\n{intro}\n"
        f"CHAPTERS:\n{chapter_text}\n"
    )

    payload = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        if isinstance(parsed.get("tldr"), str) and isinstance(parsed.get("highlights"), list):
            return {
                "tldr": parsed["tldr"].strip(),
                "highlights": [str(h).strip() for h in parsed["highlights"][:4] if str(h).strip()],
                "bestFor": str(parsed.get("bestFor", "")).strip(),
                "location": str(parsed.get("location", "")).strip(),
                "category": str(parsed.get("category", "")).strip(),
                "aiGenerated": True,
                "model": model,
            }
    except Exception as exc:
        print(f"[warn] Gemini summary failed for '{title}': {exc}", file=sys.stderr)
    return None


def call_openai_summary(title: str, description: str, chapters: list[dict[str, Any]], api_key: str) -> dict[str, Any] | None:
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    intro = clean_description_intro(description)[:2200]
    chapter_text = "\n".join(f"{c['time']} - {c['label']}" for c in chapters[:15])

    prompt = (
        "Summarize this luxury travel YouTube video strictly from the provided title, description, and chapters.\n"
        "Return ONLY valid JSON with keys: tldr (2-3 crisp sentences), highlights (3-4 concise bullets), "
        "bestFor (6-12 words), location (Region, Country), category (Hotel Reviews|Bali & Indonesia|Maldives|Flights|Travel Gear|Travel Guides).\n\n"
        f"TITLE: {title}\nDESCRIPTION:\n{intro}\nCHAPTERS:\n{chapter_text}\n"
    )
    payload = json.dumps(
        {
            "model": model,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        parsed = json.loads(data["choices"][0]["message"]["content"])
        if isinstance(parsed.get("tldr"), str) and isinstance(parsed.get("highlights"), list):
            return {
                "tldr": parsed["tldr"].strip(),
                "highlights": [str(h).strip() for h in parsed["highlights"][:4] if str(h).strip()],
                "bestFor": str(parsed.get("bestFor", "")).strip(),
                "location": str(parsed.get("location", "")).strip(),
                "category": str(parsed.get("category", "")).strip(),
                "aiGenerated": True,
                "model": model,
            }
    except Exception as exc:
        print(f"[warn] OpenAI summary failed for '{title}': {exc}", file=sys.stderr)
    return None


def fetch_curated_affiliates_from_sheet(csv_url: str) -> list[dict[str, Any]] | None:
    if not csv_url:
        return None
    try:
        raw = http_get_text(csv_url, timeout=20)
        reader = csv.DictReader(io.StringIO(raw))
        items: list[dict[str, Any]] = []
        for idx, row in enumerate(reader, start=1):
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            active = norm.get("active", "true").lower() not in {"false", "0", "no", "off"}
            url = normalize_url(norm.get("url", ""))
            title = norm.get("title", "")
            if not active or not url or not title:
                continue
            try:
                sort_order = int(norm.get("sort order") or norm.get("sort") or idx)
            except ValueError:
                sort_order = idx
            items.append(
                {
                    "id": f"sheet-{idx}",
                    "source": "curated",
                    "featured": norm.get("featured", "false").lower() in {"true", "1", "yes"},
                    "category": norm.get("category") or "Travel & Perks",
                    "title": title,
                    "badge": norm.get("offer badge") or norm.get("badge") or "",
                    "description": norm.get("description") or "",
                    "promoCode": norm.get("promo code") or norm.get("code") or "",
                    "url": url,
                    "buttonLabel": norm.get("button label") or "Explore Deal",
                    "sortOrder": sort_order,
                }
            )
        items.sort(key=lambda x: (not x["featured"], x["sortOrder"], x["title"]))
        return items
    except Exception as exc:
        print(f"[warn] Failed to fetch Google Sheet CSV: {exc}", file=sys.stderr)
        return None


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing videos archive to preserve past AI summaries & historical videos
    existing_by_id: dict[str, dict[str, Any]] = {}
    if VIDEOS_PATH.exists():
        old_data = json.loads(VIDEOS_PATH.read_text(encoding="utf-8"))
        for item in old_data.get("videos", []) + old_data.get("shorts", []):
            existing_by_id[item["id"]] = item

    yt_cfg = config["youtube"]
    long_url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={yt_cfg['longFormPlaylistId']}"
    shorts_url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={yt_cfg['shortsPlaylistId']}"

    print(f"Fetching long-form feed: {long_url}")
    long_entries = fetch_rss_entries(long_url, is_short=False)
    print(f"Fetching Shorts feed: {shorts_url}")
    short_entries = fetch_rss_entries(shorts_url, is_short=True)

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()

    merged: dict[str, dict[str, Any]] = dict(existing_by_id)

    for raw in long_entries + short_entries:
        vid = raw["id"]
        prev = existing_by_id.get(vid, {})
        chapters = parse_chapters(raw["description"])
        links = extract_affiliate_links(raw["description"])
        location = prev.get("location") or infer_location(raw["title"], raw["description"])
        category = prev.get("category") or infer_category(raw["title"], raw["description"], raw["isShort"])

        # Keep existing high-quality AI summary if already generated
        prev_summary = prev.get("summary")
        if prev_summary and prev_summary.get("aiGenerated"):
            summary = prev_summary
        else:
            ai_res = None
            if not raw["isShort"]:
                if gemini_key:
                    ai_res = call_gemini_summary(raw["title"], raw["description"], chapters, gemini_key)
                elif openai_key:
                    ai_res = call_openai_summary(raw["title"], raw["description"], chapters, openai_key)

            if ai_res:
                summary = {
                    "tldr": ai_res["tldr"],
                    "highlights": ai_res["highlights"],
                    "bestFor": ai_res["bestFor"],
                    "aiGenerated": True,
                    "model": ai_res["model"],
                }
                if ai_res.get("location"):
                    location = ai_res["location"]
                if ai_res.get("category"):
                    category = ai_res["category"]
            elif prev_summary:
                summary = prev_summary
            else:
                summary = build_fallback_summary(raw["title"], raw["description"], chapters, location, raw["isShort"])

        merged[vid] = {
            "id": vid,
            "title": raw["title"],
            "url": raw["url"],
            "publishedAt": raw["publishedAt"],
            "publishedDate": raw["publishedDate"],
            "isShort": raw["isShort"],
            "thumbnail": raw["thumbnail"],
            "fallbackThumbnail": raw["fallbackThumbnail"],
            "views": raw["views"],
            "category": category,
            "location": location,
            "chapters": chapters,
            "summary": summary,
            "affiliateLinks": [
                {k: v for k, v in lnk.items() if k != "dedupeKey"} for lnk in links
            ],
        }

    all_items = list(merged.values())
    all_items.sort(key=lambda v: v.get("publishedAt", ""), reverse=True)

    videos = [v for v in all_items if not v.get("isShort")]
    shorts = [v for v in all_items if v.get("isShort")]

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    videos_payload = {
        "updatedAt": now_iso,
        "channel": yt_cfg,
        "totalVideos": len(videos),
        "totalShorts": len(shorts),
        "videos": videos,
        "shorts": shorts[:18],
    }
    VIDEOS_PATH.write_text(json.dumps(videos_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(videos)} videos and {len(shorts[:18])} shorts to {VIDEOS_PATH}")

    # Build live affiliates payload (Google Sheet curated + YouTube auto-extracted)
    sheet_csv_url = (
        os.environ.get("AFFILIATE_SHEET_CSV_URL", "").strip()
        or config.get("affiliates", {}).get("googleSheetCsvUrl", "").strip()
    )
    sheet_items = fetch_curated_affiliates_from_sheet(sheet_csv_url)
    curated = sheet_items if sheet_items is not None else DEFAULT_CURATED_AFFILIATES
    curated_keys = {url_dedupe_key(item["url"]) for item in curated}

    # Aggregate unique affiliate links found across videos
    video_link_map: dict[str, dict[str, Any]] = {}
    for v in videos + shorts:
        for lnk in v.get("affiliateLinks", []):
            key = url_dedupe_key(lnk["url"])
            if key not in video_link_map:
                video_link_map[key] = {
                    "id": f"yt-{abs(hash(key)) % 10000000}",
                    "source": "youtube",
                    "featured": False,
                    "category": lnk.get("category", "From Recent Videos"),
                    "title": lnk["title"],
                    "badge": lnk.get("badge", "From Video"),
                    "description": f"Featured in \"{v['title']}\"",
                    "promoCode": lnk.get("promoCode", ""),
                    "url": lnk["url"],
                    "buttonLabel": lnk.get("buttonLabel", "Open Link"),
                    "inCurated": key in curated_keys,
                    "mentionedIn": [{"id": v["id"], "title": v["title"], "date": v["publishedDate"]}],
                }
            else:
                mentions = video_link_map[key]["mentionedIn"]
                if len(mentions) < 5 and not any(m["id"] == v["id"] for m in mentions):
                    mentions.append({"id": v["id"], "title": v["title"], "date": v["publishedDate"]})

    # Attach mention counts to curated items too
    for c in curated:
        key = url_dedupe_key(c["url"])
        if key in video_link_map:
            c["mentionedIn"] = video_link_map[key]["mentionedIn"]

    extra_from_videos = [
        item for item in video_link_map.values() if not item["inCurated"]
    ]

    affiliates_payload = {
        "updatedAt": now_iso,
        "sheetConnected": bool(sheet_csv_url and sheet_items is not None),
        "googleSheetCsvUrl": sheet_csv_url,
        "disclosure": config.get("affiliates", {}).get("disclosure", ""),
        "curated": curated,
        "fromVideos": extra_from_videos,
    }
    AFFILIATES_PATH.write_text(json.dumps(affiliates_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(curated)} curated + {len(extra_from_videos)} video-discovered affiliate links to {AFFILIATES_PATH}")


if __name__ == "__main__":
    main()
