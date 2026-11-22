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

import html
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SITE_URL = "https://live.uncharteditinerary.com"


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
    url = f"{sb_url}/rest/v1/{table}?select={urllib.parse.quote(select)}&limit=1000"
    req = urllib.request.Request(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def esc(val: Any) -> str:
    return html.escape(str(val or ""), quote=True)


def compute_stayodds_py(h: dict[str, Any]) -> dict[str, Any]:
    first_hand = bool(h.get("visitedByUs") and h.get("overall") is not None and h.get("scores"))
    visited = bool(h.get("visitedByUs"))
    personal_score_25 = None
    if first_hand and h.get("scores"):
        s = h["scores"]
        try:
            personal_score_25 = sum(int(s[k]) for k in ("value", "rooms", "grounds", "food", "service"))
        except Exception:
            personal_score_25 = None
    ours100 = (
        int(round(personal_score_25 * 4))
        if personal_score_25 is not None
        else (int(round(float(h["overall"]) * 20)) if first_hand else None)
    )

    editorial = [e for e in (h.get("editorialRatings") or []) if str(e.get("sourceUrl", "")).startswith("http")]
    awards = [a for a in (h.get("officialAwards") or []) if str(a.get("sourceUrl", "")).startswith("http")]
    yt_reviews = [y for y in (h.get("youtubeReviews") or []) if str(y.get("sourceUrl", "")).startswith("http")]

    # STRICT RULE: Numeric critic score ONLY comes from published numeric critic reviews (e.g. 9/10, 18/20).
    # Official awards (MICHELIN Keys, Forbes Five-Star, World's 50 Best) are NEVER turned into fake /100 numbers —
    # they are displayed by exact award name with a direct official link.
    critic_scores = [int(e["normalized100"]) for e in editorial if e.get("normalized100") is not None]
    critic100 = int(round(sum(critic_scores) / len(critic_scores))) if critic_scores else None
    primary_critic = editorial[0] if editorial else None

    vg = (h.get("verifiedGuest") or {}).get("licensed")
    guest100 = int(vg["normalized100"]) if vg and vg.get("normalized100") else None

    weights = {"firstHand": 0, "critics": 0, "guests": 0}
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

    if first_hand and ours100 is not None:
        if critic100 is not None and guest100 is not None:
            weights = {"firstHand": 40, "critics": 30, "guests": 30}
            overall_idx = int(round(ours100 * 0.4 + critic100 * 0.3 + guest100 * 0.3))
            formula = "40% My Stay • 30% Published Critics • 30% Verified Guests"
        elif guest100 is not None:
            weights = {"firstHand": 55, "critics": 0, "guests": 45}
            overall_idx = int(round(ours100 * 0.55 + guest100 * 0.45))
            formula = "55% My Stay • 45% Verified Guests"
        elif critic100 is not None:
            weights = {"firstHand": 55, "critics": 45, "guests": 0}
            overall_idx = int(round(ours100 * 0.55 + critic100 * 0.45))
            formula = "55% My Stay • 45% Published Critics"
        else:
            weights = {"firstHand": 100, "critics": 0, "guests": 0}
            overall_idx = ours100
            odds = ours100
            status_badge = "First-Hand Verified"
            status_tone = "accent"
            formula = "100% My First-Hand Stay — live Google reviews check on this page."
    else:
        if critic100 is not None and guest100 is not None:
            weights = {"firstHand": 0, "critics": 35, "guests": 65}
            overall_idx = int(round(critic100 * 0.35 + guest100 * 0.65))
            formula = "35% Published Critics • 65% Verified Guests"
        elif guest100 is not None:
            weights = {"firstHand": 0, "critics": 0, "guests": 100}
            overall_idx = guest100
            odds = guest100
            status_badge = "Verified Guest Score"
            status_tone = "teal"
            formula = "100% Verified Guest Ratings"
        elif critic100 is not None:
            weights = {"firstHand": 0, "critics": 100, "guests": 0}
            overall_idx = critic100
            odds = critic100
            status_badge = "Critic Reviewed"
            status_tone = "slate"
            formula = "100% Published Critic Reviews — live Google reviews check on this page."

    odds = overall_idx
    if src_cnt >= 2 and overall_idx is not None:
        is_consensus = True
        spread100 = max(active) - min(active)
        if spread100 <= 6:
            status_badge, status_tone = "Strong Agreement", "accent"
        elif spread100 <= 12:
            status_badge, status_tone = "Mostly Aligned", "teal"
        else:
            status_badge, status_tone = "Opinions Differ", "amber"

    left100 = ours100 if first_hand else critic100
    right100 = guest100
    delta100 = (left100 - right100) if (left100 is not None and right100 is not None) else None

    if delta100 is not None:
        critic_name = (
            primary_critic["sourceName"]
            if len(editorial) == 1 and primary_critic
            else f"{len(editorial)} published critics"
        )
        if abs(delta100) <= 5:
            gap_head = (
                f"Tight agreement ({'+' if delta100 >= 0 else ''}{delta100} pts) — my stay matched real guest reviews."
                if first_hand
                else f"Tight agreement ({'+' if delta100 >= 0 else ''}{delta100} pts) — {critic_name} and real guests agree."
            )
        elif delta100 > 5:
            gap_head = (
                f"I rated this +{delta100} pts higher than real guests — see what I loved below."
                if first_hand
                else f"{critic_name} rated this +{delta100} pts higher than real guests."
            )
        else:
            gap_head = (
                f"I rated this {delta100} pts stricter than real guests — see what stood out & what held it back."
                if first_hand
                else f"Real guests rated this +{abs(delta100)} pts higher than {critic_name}."
            )
    else:
        if first_hand:
            gap_head = "My first-hand stay notes below — compare directly with real guest reviews."
        elif awards:
            gap_head = f"Recognised with {' • '.join(a['label'] for a in awards)} — compare with real guest reviews below."
        else:
            gap_head = "Real guest ratings, official awards, and linked reviews compared side-by-side."

    return {
        "firstHand": first_hand,
        "visited": visited,
        "tierLabel": "First-Hand Verified" if first_hand else ("Short Tour Preview" if visited else "Global Directory"),
        "personalScore25": personal_score_25,
        "ours100": ours100,
        "critic100": critic100,
        "primaryCritic": primary_critic,
        "guest100": guest100,
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


def render_seo_page(h: dict[str, Any], o: dict[str, Any], related: list[dict[str, Any]]) -> str:
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
        img_src = f"../../{raw_thumb}"
        img_abs = f"{SITE_URL}/{raw_thumb}"
    elif raw_thumb.startswith("http"):
        img_src = raw_thumb
        img_abs = raw_thumb
    else:
        img_src = "../../assets/logo.jpg"
        img_abs = f"{SITE_URL}/assets/logo.jpg"

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
        ld["review"] = {
            "@type": "Review",
            "author": {"@type": "Organization", "name": "The Uncharted Itinerary"},
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": o["personalScore25"],
                "bestRating": 25,
                "worstRating": 5,
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
        f'<span class="tag tag-caution">⚠ {esc(rf)}</span>' for rf in (h.get("redFlags") or [])
    )

    # First-hand 5-axis bars matching exact YouTube video categories (/25 total)
    scores_html = ""
    if o["firstHand"] and h.get("scores"):
        s = h["scores"]
        for lbl, key in [
            ("Value", "value"),
            ("Room Quality", "rooms"),
            ("Vibe", "grounds"),
            ("Food", "food"),
            ("Service", "service"),
        ]:
            val = int(s.get(key, 4))
            pct = int(round((val / 5) * 100))
            scores_html += (
                f'<div class="detail-bar-row"><div class="detail-bar-top"><span>{lbl}</span>'
                f'<strong>{val} / 5</strong></div><div class="detail-bar-track">'
                f'<div class="detail-bar-fill" style="width:{pct}%"></div></div></div>'
            )

    review_href = ""
    if h.get("videoId"):
        if h.get("coverageType") == "Short Tour":
            review_href = f"https://www.youtube.com/shorts/{urllib.parse.quote(h['videoId'])}"
        else:
            review_href = f"https://www.youtube.com/watch?v={urllib.parse.quote(h['videoId'])}"

    scored_ed = [e for e in o["editorial"] if e.get("normalized100") is not None]
    pc = scored_ed[0] if scored_ed else None
    left_label = (
        "My First-Hand Stay"
        if o["firstHand"]
        else (pc["sourceName"] if (len(scored_ed) == 1 and pc) else "Published Critics")
    )
    if o["firstHand"] and o.get("personalScore25") is not None:
        left_display = f"{o['personalScore25']} / 25 ({o['ours100']}/100)"
    elif o["firstHand"]:
        left_display = f"{h['overall']} / 5 ({o['ours100']}/100)"
    elif len(scored_ed) == 1 and pc:
        raw_sc = pc.get("rawScore") or f"{o['critic100']}/100"
        left_display = f"{raw_sc} ({o['critic100']}/100)"
    elif o["critic100"] is not None:
        left_display = f"{o['critic100']} / 100 ({len(scored_ed)} critics)"
    else:
        left_display = "No numeric critic review yet"

    right_display = (
        f"{vg['rating']} / {vg.get('scale', 10)} ({o['guest100']}/100)"
        if vg and vg.get("rating")
        else "Checking Google Reviews…"
    )
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
        f'<a class="tag tag-accent" href="{esc(a["sourceUrl"])}" target="_blank" rel="noopener noreferrer" style="text-decoration:none;">🏆 {esc(a["label"])} ↗</a>'
        for a in o["awards"]
    )

    awards_html = "".join(
        f'<article class="channel-row"><div class="channel-row-head"><div>'
        f'<span class="tag tag-accent">{esc(a.get("awardBody") or "Official Award")}</span>'
        f'<h4><a href="{esc(a["sourceUrl"])}" target="_blank" rel="noopener noreferrer">🏆 {esc(a["label"])} ↗</a></h4>'
        f'</div><div class="channel-row-score"><strong>{esc(a.get("year") or "Official")}</strong>'
        f'<span>Official Honour</span></div></div></article>'
        for a in o["awards"]
    )
    editorial_parts = []
    for e in o["editorial"]:
        tk = f'<p class="channel-takeaway">{esc(e.get("takeaway"))}</p>' if e.get("takeaway") else ""
        if e.get("normalized100") is not None:
            sc_html = f'<strong>{esc(e.get("rawScore") or "")}</strong><span>{esc(e["normalized100"])}/100</span>'
        else:
            sc_html = '<strong>Review</strong><span>Read Article ↗</span>'
        editorial_parts.append(
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'<span class="tag">Editorial</span>'
            f'<h4><a href="{esc(e["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{esc(e["sourceName"])} ↗</a></h4>'
            f'</div><div class="channel-row-score">{sc_html}</div></div>{tk}</article>'
        )
    editorial_html = "".join(editorial_parts)

    yt_html = ""
    if review_href:
        fh_score_lbl = f"{o['personalScore25']} / 25" if (o["firstHand"] and o.get("personalScore25") is not None) else "Short"
        yt_html += (
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'<span class="tag tag-accent">Founding Contributor</span>'
            f'<h4><a href="{esc(review_href)}" target="_blank" rel="noopener noreferrer">The Uncharted Itinerary — {esc(h.get("coverageType"))} ↗</a></h4>'
            f'</div><div class="channel-row-score"><strong>{fh_score_lbl}</strong></div></div>'
            f'<p class="channel-takeaway">{esc(h.get("verdict") or "")}</p></article>'
        )
    for y in o["ytReviews"]:
        tk = f'<p class="channel-takeaway">{esc(y.get("takeaway"))}</p>' if y.get("takeaway") else ""
        yt_html += (
            f'<article class="channel-row"><div class="channel-row-head"><div>'
            f'<span class="tag">{esc(y.get("sentiment") or "Review")}</span>'
            f'<h4><a href="{esc(y["sourceUrl"])}" target="_blank" rel="noopener noreferrer">{esc(y["creatorName"])} ↗</a></h4>'
            f'</div></div>{tk}</article>'
        )

    related_html = ""
    for r in related:
        ro = compute_stayodds_py(r)
        r_odds = f"{ro['greatStayOdds']}% StayOdds" if ro["greatStayOdds"] is not None else ro["tierLabel"]
        r_thumb = r.get("thumbnail") or ""
        r_img = f"../../{r_thumb}" if r_thumb.startswith("assets/") else (r_thumb if r_thumb.startswith("http") else "../../assets/logo.jpg")
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

    if o["critic100"] is not None:
        critic_kpi_val = f'{o["critic100"]}<span>/100</span>'
        critic_kpi_lbl = (
            pc["sourceName"]
            if (len(scored_ed) == 1 and pc)
            else f"Published Critics ({len(scored_ed)})"
        )
    elif len(o["editorial"]) > 0:
        cnt_ed = len(o["editorial"])
        critic_kpi_val = f'{cnt_ed}<span> {"Review" if cnt_ed == 1 else "Reviews"}</span>'
        critic_kpi_lbl = "Editorial (No Score)"
    else:
        critic_kpi_val = "—"
        critic_kpi_lbl = "Published Critics"

    eq_parts = []
    if o["weights"]["firstHand"] > 0 and o["ours100"] is not None:
        raw_fh = f"{o['personalScore25']}/25 → " if o.get("personalScore25") is not None else ""
        eq_parts.append(f"{o['weights']['firstHand']}% My Stay ({raw_fh}{o['ours100']}%)")
    if o["weights"]["critics"] > 0 and o["critic100"] is not None:
        eq_parts.append(f"{o['weights']['critics']}% Published Critics ({o['critic100']}%)")
    if o["weights"]["guests"] > 0 and o["guest100"] is not None:
        g_raw = f"{vg['rating']}/{int(vg.get('scale', 10))} → " if vg and vg.get("rating") else ""
        eq_parts.append(f"{o['weights']['guests']}% Verified Guests ({g_raw}{o['guest100']}%)")

    if eq_parts and o["greatStayOdds"] is not None:
        equation_text = " + ".join(eq_parts) + f" = {o['greatStayOdds']}% StayOdds"
        if o["guest100"] is None and google_place_id:
            equation_text += " (updating with live Google rating…)"
    else:
        equation_text = "Waiting for live Google guest rating — StayOdds blends whichever verified numeric scores exist."

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light only" />
  <link rel="icon" type="image/png" href="../../assets/stayodds-logo.png" />
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
  <link rel="stylesheet" href="../../assets/styles.css?v=22" />
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
<body>
  <header class="site-header stayodds-site-header">
    <div class="container header-inner">
      <a class="brand" href="../../compare/" rel="noopener">
        <span class="stayodds-brand-stack">
          <span class="stayodds-wordmark-lg">StayOdds<span class="stayodds-dot">.</span></span>
          <span class="stayodds-brand-by">by The Uncharted Itinerary</span>
        </span>
      </a>
      <nav class="nav-links" aria-label="Main site navigation">
        <a href="https://www.uncharteditinerary.com/home">Home</a>
        <a href="../../compare/">StayOdds Directory</a>
        <a href="../../hotels/">Hotel Map</a>
        <a href="../../">Videos</a>
        <a href="../../links/">Deals &amp; Gear</a>
      </nav>
      <div class="header-actions">
        <a class="btn btn-primary" href="../../compare/?a={esc(slug)}">Compare VS</a>
      </div>
    </div>
  </header>

  <div class="hub-tabs-bar">
    <div class="container hub-tabs-inner">
      <a class="hub-embed-brand" href="../../compare/" aria-label="StayOdds Home">
        <span class="stayodds-wordmark">StayOdds<span class="stayodds-dot">.</span></span>
      </a>
      <nav class="hub-tabs" aria-label="Switch hub sections">
        <a class="hub-tab" href="../../">Latest Videos</a>
        <a class="hub-tab" id="hubTabMap" href="../../hotels/">Hotel Map &amp; Scores</a>
        <a class="hub-tab active" id="hubTabStayOdds" href="../../compare/" aria-current="page">StayOdds<span class="stayodds-dot">.</span></a>
        <a class="hub-tab" href="../../cameras/">Camera Reviews</a>
        <a class="hub-tab" href="../../links/">Deals &amp; Gear</a>
      </nav>
      <a class="hub-back-link" href="../../compare/">&larr; All 300 StayOdds Hotels</a>
    </div>
  </div>

  <main>
    <div class="container">
      <div class="detail-breadcrumb">
        <a id="crumbAllLink" href="../../compare/">&larr; All StayOdds Hotels</a>
        <span>/</span>
        <a id="crumbRegionLink" href="../../compare/?region={region_q}">{esc(h['region'])}</a>
        <span>/</span>
        <strong>{esc(h['name'])}</strong>
        <a id="crumbAltViewLink" href="../../hotels/?region={region_q}" style="margin-left:auto;font-size:12.5px;font-weight:600;color:var(--accent);white-space:nowrap;">&#x1F4CD; {esc(h['region'])} Map &rarr;</a>
      </div>

      <section class="detail-hero">
        <div class="detail-hero-media">
          <img src="{esc(img_src)}" alt="{esc(h['name'])}" fetchpriority="high" decoding="async" />
          <div class="detail-hero-badges">
            <span class="tag {'tag-accent' if o['firstHand'] else 'tag-slate'}">{esc(o['tierLabel'])}</span>
            <span class="tag {tag_class}" id="heroStatusBadge">{esc(o['statusBadge'])}</span>
          </div>
        </div>
        <div class="detail-hero-body">
          <div class="meta-line">
            <span>{esc(h['location'])}, {esc(h['country'])}</span>
            {f"<span>&bull;</span><span>{esc(h['brand'])}</span>" if h.get('brand') else ""}
            {f"<span>&bull;</span><span>{esc(h['priceRange'])}</span>" if h.get('priceRange') else ""}
          </div>
          {f'<div class="meta-line" style="margin-top:8px;gap:6px;">{hero_awards_html}</div>' if hero_awards_html else ''}
          <h1 class="detail-title">{esc(h['name'])}</h1>
          <p class="detail-verdict">{esc(h.get('verdict') or h.get('standout') or f"Personally curated StayOdds luxury hotel profile for {h['name']} in {h['location']}, {h['country']}.")}</p>

          <div class="detail-kpi-row">
            <div class="detail-kpi is-primary {'is-caution' if o['statusTone'] == 'amber' else ''}" id="kpiOddsCard">
              <strong id="kpiOdds">{f"{o['greatStayOdds']}%" if o['greatStayOdds'] is not None else ("Award" if o['awards'] else "Live…")}</strong>
              <span id="kpiOddsLbl">{'StayOdds' if o['greatStayOdds'] is not None else o['statusBadge']}</span>
            </div>
            <div class="detail-kpi">
              <strong>{f"{o['personalScore25']}<span>/25</span>" if (o['firstHand'] and o.get('personalScore25') is not None) else ("Short" if o['visited'] else "Not Stayed")}</strong>
              <span>{'My Stay Score' if o['firstHand'] else ('Short Tour' if o['visited'] else 'My Stay Score')}</span>
            </div>
            <div class="detail-kpi">
              <strong>{critic_kpi_val}</strong>
              <span>{esc(critic_kpi_lbl)}</span>
            </div>
            <div class="detail-kpi">
              <strong id="kpiGuestVal">{f"{vg['rating']}<span>/{int(vg.get('scale', 10))}</span>" if vg and vg.get('rating') else "Live…"}</strong>
              <span id="kpiGuestLbl">{f"Verified Guests ({vg['reviewCount']:,})" if vg and vg.get('reviewCount') else "Google Guests"}</span>
            </div>
          </div>

          <details class="stayodds-explainer">
            <summary>
              <span>How is this StayOdds % calculated?</span>
              <span class="stayodds-explainer-caret" aria-hidden="true">&#9662;</span>
            </summary>
            <div class="stayodds-explainer-body">
              <div class="stayodds-explainer-eq" id="stayOddsEquation">{esc(equation_text)}</div>
              <ul class="stayodds-explainer-list">
                <li><strong>One headline percentage, zero double-counting:</strong> StayOdds % is simply the weighted average of whichever independent numeric scores exist above — never inflated or tweaked by hidden bonuses.</li>
                <li><strong>My Stay Score (/25):</strong> Our personal 5-category score (Value, Room Quality, Vibe, Food, Service — each out of 5, multiplied by 4 to convert to a 100% scale).</li>
                <li><strong>Published Critics (/100):</strong> Average of critics that publish an explicit numeric score (e.g. 9/10, 18/20). Comments-only reviews (like The Points Guy) and official awards (MICHELIN Keys, Forbes Five-Star) are linked separately and never turned into invented numbers.</li>
                <li><strong>Google Guests (/5★):</strong> Live guest rating from Google (stars &times; 20 = 100% scale).</li>
                <li><strong>Weighting rules:</strong> 40% My Stay / 30% Critics / 30% Guests when all three exist &bull; 55% My Stay / 45% other source when two exist &bull; 35% Critics / 65% Guests when we haven&rsquo;t stayed yet &bull; 100% when only one numeric source exists.</li>
              </ul>
            </div>
          </details>

          <div class="detail-actions">
            <a class="btn btn-primary" href="{esc(h['bookingUrl'])}" target="_blank" rel="sponsored noopener noreferrer">Check Live Rates on Booking.com &nearr;</a>
            {f'<a class="btn btn-outline" href="{esc(review_href)}" target="_blank" rel="noopener noreferrer">Watch Our {"Short" if h.get("coverageType") == "Short Tour" else "Full Review"} &nearr;</a>' if review_href else ""}
            <a class="btn btn-outline" href="../../compare/?a={esc(slug)}">Compare Head-to-Head</a>
            <a class="tripadvisor-link" href="{esc(tripadvisor_url)}" target="_blank" rel="noopener noreferrer">TripAdvisor &nearr;</a>
          </div>
          <div class="vip-perks-note">
            <strong>Luxury Advisor VIP Perks Slot:</strong> Coming soon — book eligible 5-star stays with complimentary breakfast, resort credit &amp; room upgrades.
          </div>
        </div>
      </section>

      <!-- Dual-Mode Comparison & Opinion Gap Module -->
      <section class="detail-section">
        <div class="opinion-gap-card {delta_tone}">
          <div class="opinion-gap-head">
            <div>
              <span class="tag {tag_class}" id="gapStatusBadge">{esc(o['statusBadge'])}</span>
              <h2>{'My Score vs. Real Guest Score' if o['firstHand'] else 'Published Critics vs. Real Guest Score'}</h2>
              <p class="opinion-gap-headline" id="gapHeadline">{esc(o['gapHeadline'])}</p>
            </div>
            <div class="opinion-gap-delta" id="gapDeltaPill">
              <strong>{esc(delta_badge)}</strong>
              <span>Opinion Gap</span>
            </div>
          </div>

          <div class="opinion-gap-bars">
            <div class="gap-side">
              <div class="gap-side-top"><span>{esc(left_label)}</span><strong>{esc(left_display)}</strong></div>
              <div class="detail-bar-track"><div class="detail-bar-fill" style="width:{o['left100'] or 0}%"></div></div>
            </div>
            {f'''<div class="gap-side">
              <div class="gap-side-top"><span>Published Critic{'' if len(scored_ed) == 1 else 's'} ({esc(', '.join(e['sourceName'] for e in scored_ed))})</span><strong>{o['critic100']} / 100</strong></div>
              <div class="detail-bar-track"><div class="detail-bar-fill" style="width:{o['critic100']}%;background:#d97706;"></div></div>
            </div>''' if (o['firstHand'] and o['critic100'] is not None) else ''}
            <div class="gap-side">
              <div class="gap-side-top"><span>Real Guest Score</span><strong id="gapGuestDisplay">{esc(right_display)}</strong></div>
              <div class="detail-bar-track"><div class="detail-bar-fill is-secondary" id="gapGuestBar" style="width:{o['right100'] or 0}%"></div></div>
            </div>
          </div>

          {f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-top:12px;"><strong style="font-size:13px;color:#334155;">Official Awards (Listed by Name, Never Scored):</strong> {hero_awards_html}</div>' if hero_awards_html else ''}
          <div class="live-google-bar" id="liveGoogleStrip" style="display:none;"></div>
          {f'<p class="opinion-gap-narrative"><strong>What I Liked &amp; Where My Take Differs:</strong> {esc(h.get("whereWeDiffer") or h.get("verdict"))}</p>' if o['firstHand'] and (h.get('whereWeDiffer') or h.get('verdict')) else ''}
        </div>
      </section>

      <!-- Structured Middle Key Facts Panel (Strictly Verified Specs) -->
      <section class="detail-section">
        <div class="key-facts-panel">
          <div class="detail-panel-head" style="margin-bottom:14px;">
            <div>
              <h2 class="section-title" style="font-size:20px;">Key Hotel Facts &amp; Decision Details</h2>
              <p class="section-subtitle">Strictly verified property specs, standout highlights, and honest watch-outs — blank fields are omitted rather than guessed.</p>
            </div>
          </div>
          {f'<div class="key-facts-grid">{facts_html}</div>' if facts_html else ''}
          {f'<div class="key-facts-flags">{red_flags_html}</div>' if red_flags_html else ''}
          <div class="verdict-trio" style="margin-top:16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));">
            {f'<div class="verdict-card"><span class="tag tag-accent">Standout Strengths</span><h3>What Stands Out</h3><p>{esc(h.get("standout"))}</p></div>' if h.get("standout") else ''}
            {f'<div class="verdict-card is-warn"><span class="tag tag-caution">Watch-Outs</span><h3>Know Before Booking</h3><p>{esc(h.get("watchOut"))}</p></div>' if h.get("watchOut") else ''}
          </div>
        </div>
      </section>

      <!-- Formula Transparency & First-Hand Scorecard -->
      <section class="detail-section">
        <div class="detail-two-col">
          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>StayOdds Weighting</h3>
              <span class="tag">{esc(o['tierLabel'])}</span>
            </div>
            <p class="detail-panel-sub" id="weightFormulaSub">{esc(o['formula'])}</p>
            <div class="formula-grid" style="margin-top:14px; grid-template-columns: repeat(3, 1fr);">
              <div class="formula-step"><span class="formula-weight" id="weightFirstHandPct">{o['weights']['firstHand']}%</span><strong>{f"{o['personalScore25']}/25 → {o['ours100']}%" if (o['ours100'] is not None and o.get('personalScore25') is not None) else (f"{o['ours100']}%" if o['ours100'] is not None else "—")}</strong><small>My Stay</small></div>
              <div class="formula-step"><span class="formula-weight" id="weightCriticsPct">{o['weights']['critics']}%</span><strong>{f"{o['critic100']}%" if o['critic100'] is not None else "—"}</strong><small>Published Critics</small></div>
              <div class="formula-step"><span class="formula-weight" id="weightGuestsPct">{o['weights']['guests']}%</span><strong id="weightGuestVal">{f"{o['guest100']}%" if o['guest100'] is not None else "Live…"}</strong><small>Google Guests</small></div>
            </div>
          </div>

          <div class="detail-panel">
            <div class="detail-panel-head">
              <h3>My 5-Category Scorecard (/25)</h3>
              <span class="tag {'tag-accent' if o['firstHand'] else 'tag-slate'}">{f"{o['personalScore25']} / 25 Total" if (o['firstHand'] and o.get('personalScore25') is not None) else o['tierLabel']}</span>
            </div>
            {f'<div class="detail-bars" style="margin-top:12px;">{scores_html}</div>' if scores_html else '<p class="detail-panel-sub" style="margin-top:12px;">We have not scored a full personal stay here yet. Once we stay and film a review, our 5-axis scorecard will be added to our First-Hand Verified tier.</p>'}
          </div>
        </div>
      </section>

      <!-- Curated Awards, Critics & YouTube Reviews -->
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

      <section class="detail-section" style="margin-bottom:56px;">
        <div class="section-header" style="margin-bottom:18px;flex-wrap:wrap;gap:12px;">
          <div>
            <h2 class="section-title">Compare Nearby Luxury Stays</h2>
            <p class="section-subtitle">Explore other personally curated properties in {esc(h['region'])}.</p>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <a class="btn btn-outline" id="nearbyMapLink" href="../../hotels/?region={region_q}">&#x1F4CD; All {esc(h['region'])} on Map &rarr;</a>
            <a class="btn btn-outline" id="nearbyListLink" href="../../compare/?region={region_q}">All {esc(h['region'])} in StayOdds &rarr;</a>
          </div>
        </div>
        <div class="related-grid">{related_html}</div>
      </section>
    </div>
  </main>

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
        </div>
      </div>
      <div class="footer-bottom">
        <span>&copy; {datetime.now().year} StayOdds &amp; The Uncharted Itinerary</span>
        <span>Disclosure: Booking links may earn an affiliate commission at no extra cost to you.</span>
      </div>
    </div>
  </footer>

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

    const placeId = {json.dumps(google_place_id)};
    const firstHand = {json.dumps(bool(o['firstHand']))};
    const ours100 = {json.dumps(o['ours100'])};
    const personal25 = {json.dumps(o.get('personalScore25'))};
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

    if (placeId) {{
      fetch("https://yfupehkygkkccybefuam.supabase.co/functions/v1/live-google-rating?place_id=" + encodeURIComponent(placeId))
        .then((r) => (r.ok ? r.json() : null))
        .then((g) => {{
          if (!g || g.status !== "ok" || typeof g.rating !== "number") {{
            showMapsFallback((g && g.googleMapsUri) || mapsFallbackUrl);
            return;
          }}
          const g100 = typeof g.normalized100 === "number" ? g.normalized100 : Math.round(g.rating * 20);
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

          // Recalculate StayOdds % live when no static licensed guest score was already baked in
          if (staticGuest100 == null) {{
            let wFH = 0, wCr = 0, wGu = 0, odds = null, formula = "";
            if (firstHand && ours100 != null) {{
              if (critic100 != null) {{
                wFH = 40; wCr = 30; wGu = 30;
                odds = Math.round(ours100 * 0.4 + critic100 * 0.3 + g100 * 0.3);
                formula = "40% My Stay • 30% Published Critics • 30% Google Guests";
              }} else {{
                wFH = 55; wCr = 0; wGu = 45;
                odds = Math.round(ours100 * 0.55 + g100 * 0.45);
                formula = "55% My Stay • 45% Google Guests";
              }}
            }} else if (critic100 != null) {{
              wFH = 0; wCr = 35; wGu = 65;
              odds = Math.round(critic100 * 0.35 + g100 * 0.65);
              formula = "35% Published Critics • 65% Google Guests";
            }} else {{
              wFH = 0; wCr = 0; wGu = 100;
              odds = g100;
              formula = "100% Google Guest Rating";
            }}

            const active = [firstHand ? ours100 : null, critic100, g100].filter((v) => v != null);
            let badgeText = active.length === 1 ? "Google Guest Rating" : "Mostly Aligned";
            let badgeClass = "tag-teal";
            if (active.length >= 2) {{
              const spread = Math.max(...active) - Math.min(...active);
              if (spread <= 6) {{ badgeText = "Strong Agreement"; badgeClass = "tag-accent"; }}
              else if (spread <= 12) {{ badgeText = "Mostly Aligned"; badgeClass = "tag-teal"; }}
              else {{ badgeText = "Opinions Differ"; badgeClass = "tag-caution"; }}
            }}

            const kpiOdds = document.getElementById("kpiOdds");
            const kpiOddsLbl = document.getElementById("kpiOddsLbl");
            const kpiOddsCard = document.getElementById("kpiOddsCard");
            if (kpiOdds && odds != null) kpiOdds.textContent = `${{odds}}%`;
            if (kpiOddsLbl) kpiOddsLbl.textContent = "StayOdds";
            if (kpiOddsCard) kpiOddsCard.classList.toggle("is-caution", badgeClass === "tag-caution");

            const heroBadge = document.getElementById("heroStatusBadge");
            const gapBadge = document.getElementById("gapStatusBadge");
            [heroBadge, gapBadge].forEach((el) => {{
              if (!el) return;
              el.textContent = badgeText;
              el.className = `tag ${{badgeClass}}`;
            }});

            if (left100 != null) {{
              const d = left100 - g100;
              if (pill) pill.innerHTML = `<strong>${{d > 0 ? "+" + d : d}} pts</strong><span>Opinion Gap</span>`;
              const gapHead = document.getElementById("gapHeadline");
              if (gapHead) {{
                if (Math.abs(d) <= 5) {{
                  gapHead.textContent = firstHand
                    ? `Tight agreement (${{d >= 0 ? "+" + d : d}} pts) — my stay matched real guest reviews.`
                    : `Tight agreement (${{d >= 0 ? "+" + d : d}} pts) — ${{criticLabel}} and real guests agree.`;
                }} else if (d > 5) {{
                  gapHead.textContent = firstHand
                    ? `I rated this +${{d}} pts higher than real guests — see what I loved below.`
                    : `${{criticLabel}} rated this +${{d}} pts higher than real guests.`;
                }} else {{
                  gapHead.textContent = firstHand
                    ? `I rated this ${{d}} pts stricter than real guests — see what stood out & what held it back.`
                    : `Real guests rated this +${{Math.abs(d)}} pts higher than ${{criticLabel}}.`;
                }}
              }}
            }}

            const eqParts = [];
            if (wFH > 0 && ours100 != null) {{
              const rawFh = personal25 != null ? `${{personal25}}/25 → ` : "";
              eqParts.push(`${{wFH}}% My Stay (${{rawFh}}${{ours100}}%)`);
            }}
            if (wCr > 0 && critic100 != null) {{
              eqParts.push(`${{wCr}}% Published Critics (${{critic100}}%)`);
            }}
            if (wGu > 0) {{
              eqParts.push(`${{wGu}}% Google Guests (${{g.rating.toFixed(1)}}★ → ${{g100}}%)`);
            }}
            const eqEl = document.getElementById("stayOddsEquation");
            if (eqEl && eqParts.length && odds != null) {{
              eqEl.textContent = `${{eqParts.join(" + ")}} = ${{odds}}% StayOdds`;
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
          }}
        }})
        .catch(() => showMapsFallback(mapsFallbackUrl));
    }} else {{
      showMapsFallback("");
    }}
  </script>
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
        raw_hero = p.get("hero_image_url") or ""
        if local_thumb.exists() and local_thumb.stat().st_size > 1500:
            resolved_thumb = f"assets/thumbs/{pid}.webp"
        elif any(bad in raw_hero for bad in ("www.fourseasons.com", "www.lungarnocollection.com")):
            resolved_thumb = ""
        else:
            resolved_thumb = raw_hero

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
            "tier": p["tier"],
            "visitedByUs": bool(p.get("visited_by_founder")),
            "coverageType": fh["coverage_type"] if fh else "Global Directory",
            "googlePlaceId": p.get("google_place_id"),
            "nuiteeHotelId": p.get("nuitee_hotel_id"),
            "thumbnail": resolved_thumb,
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
            "redFlags": f.get("red_flag_tags") or [],
            "bookingUrl": web_booking,
            "bookingLinks": bks,
            "verifiedGuest": {
                "licensed": {
                    "sourceName": "Verified Guests",
                    "rating": float(gs["rating"]),
                    "scale": float(gs.get("scale") or 10.0),
                    "normalized100": int(gs["normalized_100"]),
                    "reviewCount": gs.get("review_count"),
                    "attribution": gs.get("attribution", "Verified Guest Score"),
                    "verifiedAt": gs.get("verified_at"),
                }
            }
            if gs
            else None,
            "editorialRatings": ed_map.get(pid) or [],
            "youtubeReviews": yt_map.get(pid) or [],
            "officialAwards": awards_map.get(pid) or [],
        }
        directory.append(rec)

    # Sort: First-Hand Verified first, then Short Tours, then Global Directory by licensed score desc
    def sort_key(r: dict[str, Any]) -> tuple[int, int, str]:
        tier_rank = 0 if r["tier"] == "first_hand_verified" else (1 if r["tier"] == "short_preview" else 2)
        g_score = -int(((r.get("verifiedGuest") or {}).get("licensed") or {}).get("normalized100") or 0)
        return (tier_rank, g_score, r["name"])

    directory.sort(key=sort_key)

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
            "bookingUrl": r["bookingUrl"],
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

    # Generate static SEO HTML pages at /stayodds/<slug>/index.html
    stayodds_dir = ROOT / "stayodds"
    stayodds_dir.mkdir(exist_ok=True)
    for h in directory:
        o = compute_stayodds_py(h)
        same_reg = [r for r in directory if r["id"] != h["id"] and r["region"] == h["region"]][:3]
        if len(same_reg) < 3:
            same_reg += [r for r in directory if r["id"] != h["id"] and r not in same_reg][: 3 - len(same_reg)]
        pdir = stayodds_dir / h["id"]
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "index.html").write_text(render_seo_page(h, o, same_reg), encoding="utf-8")

    # Build sitemap.xml covering all hub pages + all 300 /stayodds/<slug>/ pages
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        (f"{SITE_URL}/", "1.0", "daily"),
        (f"{SITE_URL}/compare/", "1.0", "daily"),
        (f"{SITE_URL}/hotels/", "0.9", "weekly"),
        (f"{SITE_URL}/cameras/", "0.8", "weekly"),
        (f"{SITE_URL}/links/", "0.8", "daily"),
    ]
    for h in directory:
        prio = "0.9" if h["tier"] == "first_hand_verified" else "0.8"
        urls.append((f"{SITE_URL}/stayodds/{h['id']}/", prio, "weekly"))

    sm_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, prio, freq in urls:
        sm_lines.append(
            f"  <url><loc>{esc(loc)}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        )
    sm_lines.append("</urlset>\n")
    (ROOT / "sitemap.xml").write_text("\n".join(sm_lines), encoding="utf-8")

    print(
        f"BUILT STAYODDS SITE!\n"
        f"  Directory JSON: {len(directory)} verified properties -> data/stayodds-directory.json ({out_json.stat().st_size/1024:.1f} KB)\n"
        f"  Lean Index JSON: {len(lean_hotels)} verified properties -> data/stayodds-index.json ({lean_json.stat().st_size/1024:.1f} KB)\n"
        f"  Static SEO Pages: {len(directory)} pages -> stayodds/<slug>/index.html\n"
        f"  Sitemap URLs: {len(urls)} URLs -> sitemap.xml"
    )


if __name__ == "__main__":
    main()
