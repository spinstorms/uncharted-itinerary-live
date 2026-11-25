"""Strict "is this the same hotel?" name check for outside listings (Tripadvisor, Forbes, ...).

Looser checks matched e.g. "Halekulani" to "Halepuna Waikiki by Halekulani" (its sister hotel) and
"La Mirande" to "Glamping La Mirande". Rule: every word of our name must be in theirs, and the main part of
their name (before " - ", " – ", ", ", " | ", " by ") may only add generic words (hotel, resort, spa, Relais &
Châteaux...) or the hotel's own town/country words.
"""
from __future__ import annotations

import re
import unicodedata

GENERIC = {
    "the", "a", "an", "and", "at", "of", "by", "de", "du", "des", "la", "le", "les", "il", "el", "los", "las", "di", "del",
    "hotel", "hotels", "hôtel", "resort", "resorts", "spa", "and", "residences", "villas", "collection", "luxury",
    "relais", "chateaux", "restaurant", "maison", "boutique", "suites", "lodge",
    "s", "golf", "wellness", "5", "star", "en", "grand", "private",
}
SPLIT = re.compile(r"\s[-–—|]\s|,\s|\s\(|\sby\s", re.I)


def toks(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("bvlgari", "bulgari")
    return re.findall(r"[a-z0-9]+", s)


def main_part(name: str) -> str:
    return SPLIT.split(name or "", maxsplit=1)[0]


def same_hotel(ours: str, theirs: str, city: str = "", country: str = "") -> bool:
    """Every word of our name must appear in theirs, and the main part of theirs (before " - ", ", ", " by "...)
    may add nothing but generic words or the hotel's own town/country words."""
    place = set(toks(city)) | set(toks(country))
    mine = set(toks(ours)) - GENERIC
    if not mine or not mine <= set(toks(theirs)):
        return False
    extra = set(toks(main_part(theirs))) - GENERIC - mine - place
    return not extra
