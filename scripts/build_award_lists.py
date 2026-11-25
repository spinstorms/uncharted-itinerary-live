#!/usr/bin/env python3
"""Static, ordered award list pages for stayodds.com.

  /lists/                              index
  /lists/worlds-50-best-hotels-2026/   ranks 1-100 in official order
  /lists/michelin-3-keys-2026/         every 3-Key hotel in the directory
  /lists/michelin-2-keys-2026/         every 2-Key hotel in the directory

Built only from data/stayodds-directory.json (officialAwards, verifiedGuest, editorialRatings, youtubeReviews), so a
hotel appears here exactly when it carries the award, and the page says how many of the official list are present.
"""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://stayodds.com"
W50B_URL = "https://www.the50.com/hotels/best-in-the-world/"
MICHELIN_URL = "https://guide.michelin.com/en/article/travel/all-the-key-hotels-in-the-world-michelin-guide"

LISTS = [
    {
        "slug": "worlds-50-best-hotels-2026",
        "title": "The World's 50 Best Hotels 2026 — Full Top 100 Ranked",
        "h1": "The World's 50 Best Hotels 2026",
        "sub": "The complete 1–100 ranking, in order, with guest scores, critic scores and video reviews for each hotel.",
        "short": "World's 50 Best 2026 (1–100)",
        "source": W50B_URL,
        "source_name": "The World's 50 Best Hotels",
        "official_total": 100,
    },
    {
        "slug": "michelin-3-keys-2026",
        "title": "2026 MICHELIN 3 Keys Hotels — Every Three-Key Hotel Ranked by Guest Score",
        "h1": "2026 MICHELIN Guide: 3 Keys",
        "sub": "The highest MICHELIN Keys distinction. Ordered by StayOdds verified guest score, then name.",
        "short": "MICHELIN 3 Keys 2026",
        "source": MICHELIN_URL,
        "source_name": "MICHELIN Guide",
        "official_total": 155,
    },
    {
        "slug": "michelin-2-keys-2026",
        "title": "2026 MICHELIN 2 Keys Hotels — Ranked by Guest Score",
        "h1": "2026 MICHELIN Guide: 2 Keys",
        "sub": "Two-Key hotels in the StayOdds directory, ordered by verified guest score, then name.",
        "short": "MICHELIN 2 Keys 2026",
        "source": MICHELIN_URL,
        "source_name": "MICHELIN Guide",
        "official_total": 657,
    },
    {
        "slug": "michelin-1-key-2026",
        "title": "2026 MICHELIN 1 Key Hotels on StayOdds — Ranked by Guest Score",
        "h1": "2026 MICHELIN Guide: 1 Key",
        "sub": "One-Key hotels in the StayOdds directory, ordered by verified guest score, then name.",
        "short": "MICHELIN 1 Key 2026",
        "source": MICHELIN_URL,
        "source_name": "MICHELIN Guide",
        "official_total": 2020,
    },
]
MAP_SCOPE = {
    "worlds-50-best-hotels-2026": "w50",
    "michelin-3-keys-2026": "michelin3",
    "michelin-2-keys-2026": "michelin2",
    "michelin-1-key-2026": "michelin1",
}
MICHELIN_ABOUT = (
    "<h2>What is a MICHELIN Key?</h2>"
    "<p>The Key is the MICHELIN Guide's distinction for hotels, its equivalent of the Star for restaurants. "
    "Keys are awarded by MICHELIN inspectors after anonymous stays or visits, and recognise a unique hospitality concept, "
    "distinctive character, a warm welcome and a very high level of service.</p>"
    "<ul><li><strong>One Key</strong>: &ldquo;a very special stay&rdquo;</li>"
    "<li><strong>Two Keys</strong>: &ldquo;an exceptional stay&rdquo;</li>"
    "<li><strong>Three Keys</strong>: &ldquo;an extraordinary stay&rdquo;</li></ul>"
    "<p>The 2026 selection has 155 Three-Key, 657 Two-Key and 2,020 One-Key hotels worldwide. "
    'Sources: <a href="https://guide.michelin.com/us/en/article/travel/one-two-three-michelin-keys-hotels-have-own-distinction-michelin-guide" target="_blank" rel="noopener">MICHELIN Guide: what the Keys mean</a>, '
    f'<a href="{MICHELIN_URL}" target="_blank" rel="noopener">MICHELIN Guide 2026 selection</a>.</p>'
)
W50_ABOUT = (
    "<h2>How the World&rsquo;s 50 Best Hotels is ranked</h2>"
    "<p>The list is voted by The World&rsquo;s 50 Best Hotels Academy: travel experts in 13 regions, each panel split "
    "equally between travel journalists, hoteliers and seasoned luxury travellers, with a 50/50 gender balance. "
    "Each member votes for seven hotels in order of preference, must have stayed at every hotel they vote for in the last "
    "three years and upload proof of the stay, and cannot vote for hotels they own or have a financial interest in. "
    "Voting is confidential and independently adjudicated by Deloitte. Ranks 51&ndash;100 are published as the extended list.</p>"
    '<p>Source: <a href="https://www.the50.com/hotels/best-in-the-world/how-the-voting-works.html" target="_blank" rel="noopener">The World&rsquo;s 50 Best Hotels: how the voting works</a>.</p>'
)


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _awards(h: dict[str, Any]) -> list[dict[str, Any]]:
    return h.get("officialAwards") or []


def w50_rank(h: dict[str, Any]) -> int | None:
    for a in _awards(h):
        m = re.search(r"No\.\s*(\d+)\s+in the World", a.get("label", ""))
        if m and "50 Best" in a.get("awardBody", ""):
            return int(m.group(1))
    return None


def michelin_keys(h: dict[str, Any]) -> int | None:
    for a in _awards(h):
        if "MICHELIN" in a.get("awardBody", "").upper():
            m = re.search(r"([123])\s*MICHELIN\s*Key", a.get("label", ""), re.I)
            if m:
                return int(m.group(1))
    return None


def guest100(h: dict[str, Any]) -> int | None:
    g = ((h.get("verifiedGuest") or {}).get("licensed") or {}).get("normalized100")
    return int(g) if g is not None else None


def critic_summary(h: dict[str, Any]) -> str:
    parts = [f"{e.get('sourceName')} {e.get('rawScore')}" for e in (h.get("editorialRatings") or []) if e.get("rawScore")]
    return " · ".join(parts[:2])


def select(lst: dict[str, Any], hotels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slug = lst["slug"]
    if slug.startswith("worlds"):
        rows = [(w50_rank(h), h) for h in hotels]
        return [h for r, h in sorted((r for r in rows if r[0] is not None), key=lambda r: r[0])]
    want = 3 if "3-keys" in slug else 2 if "2-keys" in slug else 1
    rows = [h for h in hotels if michelin_keys(h) == want]
    return sorted(rows, key=lambda h: (-(guest100(h) or -1), h["name"].lower()))


def _shell(src_template: str) -> tuple[str, str]:
    """Header (up to <main>) and footer (from <footer>) of the StayOdds hotels page, re-pointed for depth 2."""
    head, _, rest = src_template.partition("<main>")
    foot = rest[rest.index('<footer class="site-footer">') : rest.index("<script src=\"https://unpkg.com/leaflet")]
    for part in (head, foot):
        pass
    fix = lambda s: re.sub(r'((?:href|src)=["\'])\.\./', r"\1../../", s)  # noqa: E731
    head, foot = fix(head), fix(foot)
    foot = foot.replace('href="./"', 'href="../../hotels/"')
    head = head.replace('href="./"', 'href="../../hotels/"')
    head = head.replace('<a href="../../hotels/" class="active">', '<a href="../../hotels/">')
    return head, foot


PAGE_CSS = """
<style>
.al-wrap{max-width:1040px;margin:0 auto;padding:28px 16px 56px}
.al-eyebrow{font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent,#0f766e)}
.al-wrap h1{font-size:clamp(26px,5vw,40px);line-height:1.15;margin:6px 0 10px}
.al-sub{color:var(--muted,#5b6472);max-width:70ch;margin:0 0 14px}
.al-note{font-size:13.5px;background:rgba(15,118,110,.08);border:1px solid rgba(15,118,110,.25);border-radius:12px;padding:10px 14px;margin:0 0 18px}
.al-tabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.al-tabs a{padding:7px 14px;border-radius:999px;border:1px solid rgba(100,110,130,.35);font-size:13px;font-weight:600;text-decoration:none;color:inherit}
.al-tabs a.on{background:#0b2540;color:#fff;border-color:#0b2540}
.al-list{list-style:none;margin:0;padding:0;border-top:1px solid rgba(100,110,130,.25)}
.al-row{display:grid;grid-template-columns:54px 1fr auto;gap:12px;align-items:center;padding:12px 4px;border-bottom:1px solid rgba(100,110,130,.25)}
.al-rank{font-weight:800;font-size:20px;text-align:center;font-variant-numeric:tabular-nums}
.al-name{font-weight:700;font-size:16px;text-decoration:none;color:inherit}
.al-name:hover{text-decoration:underline}
.al-meta{font-size:12.5px;color:var(--muted,#5b6472);margin-top:2px}
.al-badges{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}
.al-badge{font-size:11.5px;font-weight:600;padding:2px 8px;border-radius:999px;background:rgba(100,110,130,.14)}
.al-score{text-align:right;font-size:12px;color:var(--muted,#5b6472);white-space:nowrap}
.al-score strong{display:block;font-size:20px;color:inherit}
.al-missing{margin-top:22px;font-size:13.5px}
.al-actions{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 18px}
.al-btn{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;border-radius:999px;background:#ff5d22;color:#fff;font-weight:700;font-size:14px;text-decoration:none}
.al-btn:hover{background:#e44b12}
.al-btn.ghost{background:transparent;color:inherit;border:1px solid rgba(100,110,130,.4)}
.al-about{margin:30px 0 0;padding:18px 20px;border-radius:14px;background:rgba(100,110,130,.08);font-size:14.5px;line-height:1.6}
.al-about h2{font-size:19px;margin:0 0 8px}.al-about h2+p{margin-top:0}.al-about ul{margin:6px 0 10px 18px;padding:0}
.al-about + .al-about{margin-top:14px}
@media (max-width:560px){.al-row{grid-template-columns:40px 1fr}.al-score{grid-column:2;text-align:left}}
</style>
"""


def _row(rank_label: str, h: dict[str, Any]) -> str:
    g = guest100(h)
    yt = len(h.get("youtubeReviews") or [])
    critics = critic_summary(h)
    badges = []
    for a in _awards(h)[:3]:
        badges.append(f'<span class="al-badge">{esc(a.get("label"))}</span>')
    if yt:
        badges.append(f'<span class="al-badge">{yt} video review{"s" if yt != 1 else ""}</span>')
    if critics:
        badges.append(f'<span class="al-badge">{esc(critics)}</span>')
    score = f'<strong>{g}</strong>guest score' if g is not None else "<strong>—</strong>no guest score yet"
    return (
        f'<li class="al-row"><div class="al-rank">{esc(rank_label)}</div>'
        f'<div><a class="al-name" href="../../stayodds/{esc(h["id"])}/">{esc(h["name"])}</a>'
        f'<div class="al-meta">{esc(h.get("location"))}, {esc(h.get("country"))}</div>'
        f'<div class="al-badges">{"".join(badges)}</div></div>'
        f'<div class="al-score">{score}</div></li>'
    )


def render(lst: dict[str, Any], hotels: list[dict[str, Any]], head: str, foot: str) -> str:
    rows = select(lst, hotels)
    is_rank = lst["slug"].startswith("worlds")
    items = []
    for i, h in enumerate(rows, 1):
        items.append(_row(str(w50_rank(h)) if is_rank else str(i), h))
    present = len(rows)
    total = lst["official_total"]
    if is_rank:
        have = {w50_rank(h) for h in rows}
        gaps = [str(n) for n in range(1, 101) if n not in have]
        note = (
            f"All {present} of {total} ranked hotels are listed."
            if not gaps
            else f"{present} of {total} ranked hotels are listed so far; still to add: No. {', '.join(gaps)}."
        )
    elif total == 657:
        note = (
            f"{present} two-Key hotels are listed so far out of {total} in the 2026 selection. "
            "We are adding the rest in stages; one-Key hotels are not part of this list."
        )
    elif total == 2020:
        note = (
            f"{present} one-Key hotels from the StayOdds directory. The full 2026 selection has {total:,} one-Key hotels; "
            "this list shows the ones we already cover."
        )
    else:
        note = f"{present} of {total} three-Key hotels are listed."
    tabs = "".join(
        f'<a href="/lists/{x["slug"]}/"{" class=on" if x["slug"] == lst["slug"] else ""}>{esc(x["short"])}</a>' for x in LISTS
    )
    url = f"{SITE}/lists/{lst['slug']}/"
    desc = f"{lst['sub']} {note}"[:300]
    head = re.sub(r"<title>.*?</title>", f"<title>{esc(lst['title'])} | StayOdds</title>", head, flags=re.S)
    head = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + esc(desc) + m.group(2), head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*(")', lambda m: m.group(1) + esc(lst["title"]) + m.group(2), head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + esc(desc) + m.group(2), head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), head)
    head = re.sub(r'<script type="application/ld\+json">.*?</script>', "", head, count=1, flags=re.S)
    ld = (
        '<script type="application/ld+json">{"@context":"https://schema.org","@type":"ItemList","name":%s,"url":%s,'
        '"numberOfItems":%d,"itemListElement":[%s]}</script>'
        % (
            _js(lst["h1"]),
            _js(url),
            present,
            ",".join(
                '{"@type":"ListItem","position":%d,"name":%s,"url":%s}'
                % (i, _js(h["name"]), _js(f"{SITE}/stayodds/{h['id']}/"))
                for i, h in enumerate(rows, 1)
            ),
        )
    )
    body = (
        f'<main><div class="al-wrap"><div class="al-eyebrow">Award lists</div><h1>{esc(lst["h1"])}</h1>'
        f'<p class="al-sub">{esc(lst["sub"])}</p>'
        f'<p class="al-note">{esc(note)} Source: <a href="{esc(lst["source"])}" target="_blank" rel="noopener">{esc(lst["source_name"])}</a>. '
        "Guest scores are verified licensed guest ratings; nothing on this page is estimated.</p>"
        f'<nav class="al-tabs" aria-label="Award lists">{tabs}</nav>'
        f'<div class="al-actions"><a class="al-btn" href="/hotels/?scope={MAP_SCOPE[lst["slug"]]}">View these hotels on the map &rarr;</a></div>'
        f'<ol class="al-list">{"".join(items)}</ol>'
        f'<section class="al-about">{W50_ABOUT if is_rank else MICHELIN_ABOUT}</section></div></main>'
    )
    return head.replace("</head>", PAGE_CSS + ld + "\n</head>", 1) + body + foot + "</body>\n</html>\n"


def _js(s: str) -> str:
    import json

    return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")


def write_award_lists(dist: Path, hotels: list[dict[str, Any]], template: str) -> list[str]:
    """Write /lists/** into dist. Returns the site paths written (for the sitemap)."""
    head, foot = _shell(template)
    paths = []
    for lst in LISTS:
        out = dist / "lists" / lst["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(render(lst, hotels, head, foot), encoding="utf-8")
        paths.append(f"/lists/{lst['slug']}/")
    # index page
    idx = dist / "lists"
    cards = "".join(
        f'<li class="al-row"><div class="al-rank">★</div><div><a class="al-name" href="/lists/{x["slug"]}/">{esc(x["h1"])}</a>'
        f'<div class="al-meta">{esc(x["sub"])}</div>'
        f'<div class="al-badges"><a class="al-badge" href="/lists/{x["slug"]}/">See the list</a>'
        f'<a class="al-badge" href="/hotels/?scope={MAP_SCOPE[x["slug"]]}">Show on map</a></div></div>'
        f'<div class="al-score"><strong>{len(select(x, hotels))}</strong>hotels</div></li>'
        for x in LISTS
    )
    h2 = re.sub(r"<title>.*?</title>", "<title>Hotel Award Lists | StayOdds</title>", head, flags=re.S)
    h2 = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + f"{SITE}/lists/" + m.group(2), h2)
    page = (
        h2.replace("</head>", PAGE_CSS + "</head>", 1)
        + '<main><div class="al-wrap"><div class="al-eyebrow">Award lists</div><h1>Hotel award lists</h1>'
        '<p class="al-sub">The World\'s 50 Best Hotels and the MICHELIN Keys, ordered and linked to full StayOdds scorecards.</p>'
        f'<ol class="al-list">{cards}</ol><section class="al-about">{MICHELIN_ABOUT}</section>'
        f'<section class="al-about">{W50_ABOUT}</section></div></main>' + foot + "</body>\n</html>\n"
    )
    (idx / "index.html").write_text(page, encoding="utf-8")
    return ["/lists/"] + paths
