"""Drinking water in the room: classify guest review sentences as 'free' or 'paid' (strict; anything unclear is ignored)."""
from __future__ import annotations

import re
from typing import Any

WATER_CTX = re.compile(r"\b(bottles? of water|bottled water|water bottles?|drinking water|mineral water|still water|sparkling water|free water|complimentary water|water refill|refill station|water station|bottle of water)\b", re.I)
NEG = re.compile(r"\b(not|no|never|without|n't|didn't|wasn't|weren't|isn't|aren't|lack|lacking|ran out|run out)\b", re.I)
FREE = re.compile(
    r"\b((free|complimentary|unlimited) (bottled |drinking |mineral |still |filtered |fresh )?(bottles? of )?water"
    r"|water (bottles? )?(was|is|were|are) (free|complimentary|included|replenished|refilled|provided)"
    r"|(bottles? of water|bottled water|water bottles?) (were|was|are|is)? ?(provided|replenished|refilled|included|free|complimentary|topped up)"
    r"|complimentary (bottles?|water)|(water )?refill station|water station|plenty of (bottled )?water)\b", re.I)
PAID = re.compile(r"\b(charg\w*|pay|paid|paying|cost\w*|overpriced|expensive)\b|[$€£]\s?\d|\b\d+\s?(usd|eur|euros?|dollars?|gbp|aed|thb|idr)\b", re.I)
NOT_FREE = re.compile(r"\b(no|not|isn't|wasn't|aren't|weren't) (free|complimentary)\b|\bno (free|complimentary) (bottled )?water\b", re.I)


def classify(sentence: str) -> str | None:
    s = sentence.strip()
    if not WATER_CTX.search(s) or len(s) > 260:
        return None
    if NOT_FREE.search(s) or (PAID.search(s) and not FREE.search(s)):
        return "paid"
    if FREE.search(s) and not NEG.search(s):
        return "free"
    return None


def summarise(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    reports = []
    for c in candidates or []:
        v = classify(c.get("text", ""))
        if v:
            reports.append({**c, "verdict": v})
    if not reports:
        return None
    reports.sort(key=lambda x: x.get("date", ""), reverse=True)
    free = sum(1 for r in reports if r["verdict"] == "free")
    return {"free": free, "paid": len(reports) - free, "latest": reports[0].get("date", ""), "reports": reports[:3]}
