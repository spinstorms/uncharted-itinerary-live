#!/usr/bin/env python3
"""Builds the StayOdds social media kit (PNG artwork + short MP4s) from live directory numbers.

    python3 marketing/build_social_kit.py [outdir]

Needs Playwright + Chromium + ffmpeg. Every number printed on the artwork is counted from
data/stayodds-directory.json at build time, so re-run it whenever the directory grows.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "marketing" / "social-kit"
LOGO = "data:image/png;base64," + base64.b64encode((ROOT / "assets" / "stayodds-logo.png").read_bytes()).decode()


def stats() -> dict[str, int]:
    hs = json.loads((ROOT / "data" / "stayodds-directory.json").read_text(encoding="utf-8"))["hotels"]

    def keys(h):
        for a in h.get("officialAwards") or []:
            m = re.search(r"([123])\s*MICHELIN Key", a.get("label", ""))
            if m:
                return int(m.group(1))

    def rank(h):
        for a in h.get("officialAwards") or []:
            m = re.search(r"No\. (\d+) in the World", a.get("label", ""))
            if m:
                return int(m.group(1))

    return {
        "hotels": len(hs),
        "countries": len({h["country"] for h in hs if h.get("country")}),
        "w50": sum(1 for h in hs if rank(h)),
        "k3": sum(1 for h in hs if keys(h) == 3),
        "k2": sum(1 for h in hs if keys(h) == 2),
        "guest": sum(1 for h in hs if ((h.get("verifiedGuest") or {}).get("licensed") or {}).get("normalized100") is not None),
        "firsthand": sum(1 for h in hs if h.get("tier") == "first_hand_verified"),
        "videos": sum(len(h.get("youtubeReviews") or []) for h in hs),
    }


S = stats()
CSS = """
*{box-sizing:border-box;margin:0}
body{font-family:'Poppins',sans-serif;color:#fff;background:#071323;overflow:hidden}
.c{position:relative;width:100vw;height:100vh;padding:7%;display:flex;flex-direction:column;justify-content:space-between;
background:radial-gradient(120% 90% at 100% 0%,#1d3a5f 0%,#0b2540 45%,#071323 100%)}
.c:before{content:"";position:absolute;right:-12%;top:-10%;width:60%;aspect-ratio:1;border-radius:50%;
background:radial-gradient(circle,rgba(255,93,34,.45),rgba(255,93,34,0) 65%)}
.brand{display:flex;align-items:center;gap:14px;font-weight:800;font-size:2.6vmin;letter-spacing:.01em;z-index:1}
.brand img{height:5.4vmin;border-radius:1.2vmin}.brand i{color:#ff5d22;font-style:normal}
.eyebrow{font-weight:700;font-size:2.1vmin;letter-spacing:.16em;text-transform:uppercase;color:#ffb48f;z-index:1}
h1{font-weight:800;line-height:1.04;font-size:var(--h,8.6vmin);letter-spacing:-.02em;z-index:1;margin:1.4vmin 0 2.2vmin}
h1 em{font-style:normal;color:#ff5d22}
p{font-size:var(--p,3vmin);line-height:1.4;color:#d5deea;z-index:1;max-width:30em}
.row{display:flex;gap:2vmin;flex-wrap:wrap;z-index:1}
.stat{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.18);border-radius:2vmin;padding:2vmin 2.6vmin;min-width:19vmin}
.stat b{display:block;font-size:5.6vmin;font-weight:800;line-height:1}
.stat span{font-size:1.9vmin;color:#c3cfdf}
.cta{z-index:1;display:flex;justify-content:space-between;align-items:center;font-size:2.4vmin;font-weight:700}
.pill{background:#ff5d22;color:#fff;border-radius:99px;padding:1.5vmin 3vmin}
.list{z-index:1;display:grid;gap:1.4vmin}
.li{display:flex;gap:2vmin;align-items:center;background:rgba(255,255,255,.07);border-radius:1.8vmin;padding:1.6vmin 2.4vmin;font-size:2.7vmin;font-weight:600}
.li b{width:7vmin;color:#ff5d22;font-size:3.2vmin;font-weight:800}
.li small{margin-left:auto;color:#9fb1c8;font-weight:500;font-size:2vmin}
.vs{display:grid;grid-template-columns:1fr 1fr;gap:2vmin;z-index:1}
.vs div{background:rgba(255,255,255,.08);border-radius:2vmin;padding:3vmin}
.vs b{font-size:2vmin;letter-spacing:.12em;text-transform:uppercase;color:#ffb48f}
.vs span{display:block;font-size:3vmin;font-weight:700;margin-top:1vmin}
"""

BRAND = f'<div class="brand"><img src="{LOGO}"/>StayOdds<i>.</i></div>'
CTA = '<div class="cta"><span>stayodds.com</span><span class="pill">Compare hotels free</span></div>'


def page(inner: str, h: str | None = None, p: str | None = None) -> str:
    var = (f"--h:{h};" if h else "") + (f"--p:{p};" if p else "")
    return f'<html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="c" style="{var}">{inner}</div></body></html>'


def stat(n, label) -> str:
    return f'<div class="stat"><b>{n:,}</b><span>{label}</span></div>'


def slides() -> dict[str, str]:
    return {
        "01-critics-vs-guests": page(
            f'<div>{BRAND}</div><div><div class="eyebrow">Luxury hotel scores</div>'
            "<h1>Critics say 5 stars.<br><em>Guests say?</em></h1>"
            "<p>StayOdds puts published critic scores, verified guest ratings and first-hand video stays side by side.</p></div>"
            f'<div class="row">{stat(S["hotels"], "luxury hotels")}{stat(S["countries"], "countries")}</div>{CTA}'
        ),
        "02-top-100": page(
            f'<div>{BRAND}</div><div><div class="eyebrow">World\'s 50 Best Hotels 2026</div>'
            "<h1>The full <em>Top 100</em>, in order.</h1>"
            "<p>Every ranked hotel with guest scores, critic scores and video reviews. No paywall.</p></div>"
            '<div class="list"><div class="li"><b>1</b>Rosewood Hong Kong<small>Hong Kong</small></div>'
            '<div class="li"><b>2</b>Capella Bangkok<small>Bangkok</small></div>'
            '<div class="li"><b>3</b>Four Seasons Bangkok<small>Bangkok</small></div></div>' + CTA
        ),
        "03-michelin-keys": page(
            f'<div>{BRAND}</div><div><div class="eyebrow">MICHELIN Keys 2026</div>'
            "<h1>Every <em>3 Key</em> hotel, ranked by real guests.</h1>"
            "<p>Michelin's top hotel distinction, checked against verified guest scores.</p></div>"
            f'<div class="row">{stat(S["k3"], "3-Key hotels")}{stat(S["k2"], "2-Key hotels")}{stat(S["w50"], "Top-100 ranked")}</div>' + CTA
        ),
        "04-one-place": page(
            f'<div>{BRAND}</div><div><div class="eyebrow">One scorecard per hotel</div>'
            "<h1>Stop opening <em>12 tabs</em>.</h1></div>"
            '<div class="vs"><div><b>Critics</b><span>Published scores, linked to source</span></div>'
            '<div><b>Guests</b><span>Verified guest ratings</span></div>'
            '<div><b>Awards</b><span>50 Best, MICHELIN Keys</span></div>'
            '<div><b>Video</b><span>Real reviews, verified links</span></div></div>' + CTA
        ),
    }


SIZES = {
    "instagram-square-1080x1080": (1080, 1080),
    "instagram-portrait-1080x1350": (1080, 1350),
    "story-reel-cover-1080x1920": (1080, 1920),
    "x-post-1600x900": (1600, 900),
    "facebook-post-1200x630": (1200, 630),
}


def video_html() -> str:
    lines = [
        ("1", "Rosewood Hong Kong"), ("2", "Capella Bangkok"), ("3", "Four Seasons Bangkok"),
        ("4", "Atlantis The Royal"), ("5", "Passalacqua"),
    ]
    items = "".join(f'<div class="li v" style="animation-delay:{6.4 + i * .55}s"><b>{n}</b>{t}</div>' for i, (n, t) in enumerate(lines))
    return f"""<html><head><meta charset="utf-8"><style>{CSS}
.v,.s{{opacity:0;transform:translateY(40px);animation:in .7s forwards}}
@keyframes in{{to{{opacity:1;transform:none}}}}
.sc{{position:absolute;inset:0;padding:7%;display:flex;flex-direction:column;justify-content:center;opacity:0;animation:sc 3.2s forwards}}
@keyframes sc{{0%{{opacity:0;transform:scale(.97)}}12%{{opacity:1;transform:none}}88%{{opacity:1}}100%{{opacity:0}}}}
.big{{font-size:12vmin;font-weight:800;line-height:1.02;letter-spacing:-.03em}}
.big em{{font-style:normal;color:#ff5d22}}
</style></head><body><div class="c" style="--h:9vmin">
<div style="z-index:2">{BRAND}</div>
<div class="sc" style="animation-delay:0s"><div class="eyebrow">Luxury hotel scores</div><div class="big">Critics say<br><em>5 stars.</em></div></div>
<div class="sc" style="animation-delay:3s"><div class="big">Guests say<br><em>something else?</em></div></div>
<div class="sc" style="animation-delay:6s;justify-content:flex-start;padding-top:28%"><div class="eyebrow">World's 50 Best Hotels 2026</div><h1>The full <em>Top 100</em>,<br>in order.</h1><div class="list" style="margin-top:3vmin">{items}</div></div>
<div class="sc" style="animation-delay:10.4s;animation-duration:3.6s;animation-fill-mode:both"><div class="eyebrow">{S["hotels"]:,} hotels · {S["countries"]} countries</div><div class="big">Compare<br><em>before you book.</em></div><div class="cta" style="margin-top:6vmin"><span class="pill">stayodds.com</span></div></div>
</div></body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("stats:", S)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for name, html in slides().items():
            for label, (w, h) in SIZES.items():
                pg = br.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
                pg.set_content(html)
                pg.wait_for_timeout(250)
                pg.screenshot(path=str(OUT / f"{name}__{label}.png"))
                pg.close()
        # profile / header images
        pg = br.new_page(viewport={"width": 1500, "height": 500})
        pg.set_content(page(f'<div style="display:flex;justify-content:space-between;align-items:center;height:100%;z-index:1">{BRAND}<div style="text-align:right"><div class="eyebrow">Critics vs real guests</div><h1 style="--h:6vmin;margin:0">Luxury hotel scores,<br><em>side by side.</em></h1></div></div>'))
        pg.wait_for_timeout(250)
        pg.screenshot(path=str(OUT / "x-header-1500x500.png"))
        pg.close()
        pg = br.new_page(viewport={"width": 1640, "height": 624})
        pg.set_content(page(f'<div style="display:flex;justify-content:space-between;align-items:center;height:100%;z-index:1">{BRAND}<div style="text-align:right"><h1 style="--h:6.4vmin;margin:0">Compare luxury hotels<br><em>before you book.</em></h1></div></div>'))
        pg.wait_for_timeout(250)
        pg.screenshot(path=str(OUT / "facebook-cover-1640x624.png"))
        pg.close()
        # animated vertical video (record, then convert)
        tmp = OUT / "_rec"
        shutil.rmtree(tmp, ignore_errors=True)
        ctx = br.new_context(viewport={"width": 1080, "height": 1920}, record_video_dir=str(tmp), record_video_size={"width": 1080, "height": 1920})
        pg = ctx.new_page()
        pg.set_content(video_html())
        pg.wait_for_timeout(14500)
        ctx.close()
        br.close()
    webm = next(tmp.glob("*.webm"))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(webm), "-ss", "0.4", "-t", "14", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "20", str(OUT / "reel-tiktok-shorts-1080x1920.mp4")], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print("done ->", OUT)


if __name__ == "__main__":
    main()
