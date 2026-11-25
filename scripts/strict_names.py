"""Strict "is this the same hotel?" name check for outside listings (Tripadvisor, Forbes, ...).

Looser checks matched e.g. "Halekulani" to "Halepuna Waikiki by Halekulani" (its sister hotel) and
"La Mirande" to "Glamping La Mirande". Rule: compare the MAIN part of each name (before " - ", " – ", ", ", " | ",
" by "); every word of our main name must be in theirs, and their main name may only add generic words
(hotel, resort, spa, Relais & Châteaux...) or the hotel's own town/country words.
"""
from __future__ import annotations

import re
import unicodedata

GENERIC = {
    "the", "a", "an", "and", "at", "of", "by", "de", "du", "des", "la", "le", "les", "il", "el", "los", "las", "di", "del",
    "hotel", "hotels", "hôtel", "resort", "resorts", "spa", "and", "residences", "villas", "collection", "luxury",
    "relais", "chateaux", "restaurant", "maison", "boutique", "suites", "retreat", "lodge", "estate", "palace",
    "beach", "island", "s", "golf", "wellness", "5", "star", "en", "grand", "private", "a",
}
SPLIT = re.compile(r"\s[-–—|]\s|,\s|\s\(|\sby\s", re.I)


def toks(s: str) -> list[str]:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().replace("bvlgari", "bulgari")
    return re.findall(r"[a-z0-9]+", s)


def main_part(name: str) -> str:
    return SPLIT.split(name or "", maxsplit=1)[0]


def same_hotel(ours: str, theirs: str, city: str = "", country: str = "") -> bool:
    place = set(toks(city)) | set(toks(country))

    def check(a: str, b: str) -> bool:
        mine = set(toks(a)) - GENERIC
        other = set(toks(b)) - GENERIC
        return bool(mine) and mine <= set(toks(theirs)) and not (other - mine - place)

    # main parts (before " - ", ", ", " by "...) or the whole names, compared both ways round
    return check(main_part(ours), main_part(theirs)) or check(ours, theirs)
