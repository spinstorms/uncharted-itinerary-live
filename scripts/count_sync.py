"""Keep every "N hotels" style number in StayOdds page text equal to the real directory size.

Used by build_stayodds_domain.py (stayodds.com) and build_stayodds_site.py (hub), so the headline counts
follow data/stayodds-directory.json on every build instead of being hand-edited.
"""
from __future__ import annotations

import re

_WORDS = r"(?:Verified|verified|Luxury|luxury|Mapped|mapped|StayOdds|Hotels|hotels|Properties|properties|Property|property|on\s+World\s+Map)"
_AFTER = re.compile(r"(?<![£$€\d.,])\b(?!(?:19|20)\d{2}\b)([3-9]\d{2}|[1-9]\d{3})(\+?(?:\s|-|&nbsp;)" + _WORDS + r")")
_BEFORE = re.compile(r"((?:\bAll|\ball|\bacross|\bAcross)\s+)(?!(?:19|20)\d{2}\b)([3-9]\d{2}|[1-9]\d{3})\b(?![.,]\d)")
_VISITED = re.compile(r"\b(\d{1,3})(\s+(?:Uncharted YouTube Stays|First-Hand stays|First-Hand Stays|Uncharted Verified))")


def sync_counts(text: str, total: int, visited: int | None = None) -> str:
    text = _AFTER.sub(lambda m: f"{total}{m.group(2)}", text)
    text = _BEFORE.sub(lambda m: f"{m.group(1)}{total}", text)
    if visited is not None:
        text = _VISITED.sub(lambda m: f"{visited}{m.group(2)}", text)
    return text
