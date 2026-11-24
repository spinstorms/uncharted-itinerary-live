"""Shared StayOdds page chrome (single clean header, bespoke SVG icons, partner perks strip).

Used by build_stayodds_site.py and synced into stayodds-src/*/index.html so Discover, Compare,
World Map, Brands, Hotel Detail pages, and Destination Guides share identical luxury-editorial
navigation and verified Travelpayouts + direct affiliate partner displays.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_JS = (ROOT / "assets" / "stayodds-icons.js").read_text(encoding="utf-8")
_PATHS = {
    m.group(1): m.group(2)
    for m in re.finditer(r"^\s{2}(\w+):\s*\n?\s*'([^']*)'", _JS, re.M)
}


def ico(name: str, size: int = 14) -> str:
    inner = _PATHS.get(name) or _PATHS["compass"]
    return (
        f'<svg class="so-ico" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.85" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{inner}</svg>'
    )


ICO_BED = ico("bed")
ICO_CAM = ico("camera")
ICO_PIN = ico("mapPin")
ICO_SPARK = ico("sparkles")
ICO_TROPHY = ico("trophy", 12)
ICO_LINK = ico("link", 12)
ICO_ALERT = ico("alert", 12)


def header(p: str, active: str = "") -> str:
    """Single clean dark header. p = relative prefix to site root ('../', '../../')."""

    def a(key, href, label, icon):
        cls = ' class="active"' if key == active else ""
        return f'        <a href="{href}"{cls}>\n          {ico(icon, 15)}\n          {label}\n        </a>\n'

    def m(key, href, label):
        cls = ' class="active"' if key == active else ""
        return f'      <a href="{href}"{cls}>{label}</a>\n'

    nav = (
        a("discover", f"{p}compare/", "Discover", "search")
        + a("compare", f"{p}compare/?mode=compare", "Compare", "compare")
        + a("map", f"{p}hotels/", "World Map", "mapPin")
        + a("brands", f"{p}brands/", "Brands", "award")
        + f'        <a href="{p}" class="nav-uncharted-pill">Uncharted Videos &nearr;</a>\n'
    )
    mob = (
        m("discover", f"{p}compare/", "Discover Hotels")
        + m("compare", f"{p}compare/?mode=compare", "Compare VS &amp; Directory")
        + m("map", f"{p}hotels/", "Interactive World Map")
        + m("brands", f"{p}brands/", "Brand Leaderboard")
        + f'      <a href="{p}links/">Travel Deals &amp; Codes</a>\n      <a href="{p}">Uncharted Videos &nearr;</a>\n'
        + f'      <a href="{p}about/">About</a>\n      <a href="{p}faq/">FAQ</a>\n      <a href="{p}contact/">Contact</a>\n'
    )
    return f'''  <header class="site-header stayodds-site-header">
    <div class="container header-inner">
      <div class="brand stayodds-brand-group">
        <a href="{p}compare/" class="stayodds-brand-emblem-link" aria-label="StayOdds Home">
          <img src="{p}assets/stayodds-logo.png?v=2" alt="SO." width="36" height="36" class="stayodds-header-emblem" />
        </a>
        <span class="stayodds-brand-stack">
          <a class="stayodds-wordmark-lg" href="{p}compare/" rel="noopener">StayOdds<span class="stayodds-dot">.</span></a>
          <a class="stayodds-brand-by" href="https://uncharteditinerary.com/" rel="noopener">by The Uncharted Itinerary &nearr;</a>
        </span>
      </div>

      <nav class="nav-links stayodds-clean-nav" aria-label="Main site navigation">
{nav}      </nav>

      <div class="header-actions">
        <a class="btn btn-outline nav-deals-btn" href="{p}links/">Deals &amp; Codes</a>
        <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Toggle menu" aria-expanded="false">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
      </div>
    </div>

    <nav class="mobile-nav" id="mobileNav" aria-label="Mobile navigation">
{mob}    </nav>
  </header>
'''


DETAIL_OTA_STRIP = '''          <div class="detail-ota-strip" aria-label="Compare booking platforms and trip extras">
            <span class="detail-ota-label">Compare partners:</span>
            <a href="https://expedia.tpx.lu/9LHschol" target="_blank" rel="sponsored noopener noreferrer">Expedia &nearr;</a>
            <a href="https://hotels.tpx.lu/2JsCNIZh" target="_blank" rel="sponsored noopener noreferrer">Hotels.com &nearr;</a>
            <a href="https://agoda.tpx.lu/p5JSiiU0" target="_blank" rel="sponsored noopener noreferrer">Agoda &nearr;</a>
            <a href="https://trip.tpx.lu/BbtDtE5w" target="_blank" rel="sponsored noopener noreferrer">Trip.com &nearr;</a>
            <span class="detail-ota-sep" aria-hidden="true">&bull;</span>
            <a href="https://kiwi.tpx.lu/fDgPG9Ew" target="_blank" rel="sponsored noopener noreferrer">Kiwi Flights &nearr;</a>
            <a href="https://getyourguide.tpx.lu/q0UlPSkz" target="_blank" rel="sponsored noopener noreferrer">GetYourGuide &nearr;</a>
            <a href="https://viator.tpx.lu/ByHwSqC5" target="_blank" rel="sponsored noopener noreferrer">Viator &nearr;</a>
          </div>'''


def partner_strip(p: str) -> str:
    """Tasteful verified affiliate & Travelpayouts partner hub (strictly verified links from data/affiliates.json)."""
    return f'''    <section class="partner-deals-section" id="partnerDealsStrip" aria-label="Travel perks and booking partners">
      <div class="container">
        <div class="partner-deals-card">
          <div class="partner-deals-head">
            <div>
              <span class="partner-deals-eyebrow">Trip Essentials &amp; Verified Booking Partners</span>
              <h2>Compare Rates, Flights, Tours &amp; Travel Perks</h2>
              <p>Trusted booking platforms, eSIM discount codes, and hotel points cards we use on trips filmed for The Uncharted Itinerary.</p>
            </div>
            <a class="btn btn-outline" href="{p}links/" style="font-size:13px;padding:8px 14px;">All Deals &amp; Gear &nearr;</a>
          </div>

          <div class="partner-deals-grid">
            <a class="partner-deal-tile" href="https://holafly.sjv.io/Tripready" target="_blank" rel="sponsored noopener noreferrer">
              <div class="partner-deal-top"><span class="partner-deal-kicker">Unlimited Travel eSIM</span><span class="partner-deal-code">Code: TRIPREADY</span></div>
              <h3>Holafly Unlimited Data eSIM</h3>
              <p>Instant data on arrival across 200+ destinations &mdash; 5% off with code <strong>TRIPREADY</strong>.</p>
              <span class="partner-deal-cta">Claim 5% Discount &nearr;</span>
            </a>
            <a class="partner-deal-tile" href="https://marriottbonvoy.currensea.co.uk/refer-a-friend?utm_source=refer-a-friend&amp;friend-referral-code=OKM2ZH" target="_blank" rel="sponsored noopener noreferrer">
              <div class="partner-deal-top"><span class="partner-deal-kicker">Hotel Points Card</span><span class="partner-deal-code">Code: OKM2ZH</span></div>
              <h3>Marriott Bonvoy Currensea Card</h3>
              <p>Earn Marriott Bonvoy points on everyday &amp; overseas spending (up to 2,000 bonus pts via referral).</p>
              <span class="partner-deal-cta">See Referral Offer &nearr;</span>
            </a>
            <a class="partner-deal-tile" href="https://americanexpress.com/en-gb/referral/gold-credit?ref=oLIVEK1B4w" target="_blank" rel="sponsored noopener noreferrer">
              <div class="partner-deal-top"><span class="partner-deal-kicker">Rewards Card (UK)</span><span class="partner-deal-code">Bonus Offer</span></div>
              <h3>Amex Preferred Rewards Gold</h3>
              <p>Convert Membership Rewards into airline Avios or hotel points with our UK referral bonus.</p>
              <span class="partner-deal-cta">View UK Referral &nearr;</span>
            </a>
          </div>

          <div class="partner-platforms-bar">
            <div class="partner-platform-group">
              <span class="partner-platform-label">Hotel Rates:</span>
              <a class="partner-platform-pill" href="https://booking.tpx.lu/dddKFSMf" target="_blank" rel="sponsored noopener noreferrer">Booking.com &nearr;</a>
              <a class="partner-platform-pill" href="https://expedia.tpx.lu/9LHschol" target="_blank" rel="sponsored noopener noreferrer">Expedia &nearr;</a>
              <a class="partner-platform-pill" href="https://hotels.tpx.lu/2JsCNIZh" target="_blank" rel="sponsored noopener noreferrer">Hotels.com &nearr;</a>
              <a class="partner-platform-pill" href="https://agoda.tpx.lu/p5JSiiU0" target="_blank" rel="sponsored noopener noreferrer">Agoda &nearr;</a>
              <a class="partner-platform-pill" href="https://trip.tpx.lu/BbtDtE5w" target="_blank" rel="sponsored noopener noreferrer">Trip.com &nearr;</a>
            </div>
            <div class="partner-platform-group">
              <span class="partner-platform-label">Flights &amp; Tours:</span>
              <a class="partner-platform-pill" href="https://kiwi.tpx.lu/fDgPG9Ew" target="_blank" rel="sponsored noopener noreferrer">Kiwi.com Flights &nearr;</a>
              <a class="partner-platform-pill" href="https://getyourguide.tpx.lu/q0UlPSkz" target="_blank" rel="sponsored noopener noreferrer">GetYourGuide &nearr;</a>
              <a class="partner-platform-pill" href="https://viator.tpx.lu/ByHwSqC5" target="_blank" rel="sponsored noopener noreferrer">Viator &nearr;</a>
              <a class="partner-platform-pill" href="https://klook.tpx.lu/TsCmTC1L" target="_blank" rel="sponsored noopener noreferrer">Klook Transfers &nearr;</a>
            </div>
            <div class="partner-platform-group">
              <span class="partner-platform-label">eSIMs &amp; FX:</span>
              <a class="partner-platform-pill" href="https://airalo.tpx.lu/WSdkjcJz" target="_blank" rel="sponsored noopener noreferrer">Airalo eSIM &nearr;</a>
              <a class="partner-platform-pill" href="https://saily.tpx.lu/bIVFTBvq" target="_blank" rel="sponsored noopener noreferrer">Saily eSIM &nearr;</a>
              <a class="partner-platform-pill" href="https://wise.com/invite/dic/oliverarrashk" target="_blank" rel="sponsored noopener noreferrer">Wise Travel Card &nearr;</a>
            </div>
          </div>

          <p class="partner-deals-disclosure">Affiliate disclosure: Partner links may earn a small commission at zero extra cost to you and never influence StayOdds scores or rankings.</p>
        </div>
      </div>
    </section>
'''


# ---------- Video review badge (mirrors ytOverlay / ytWatchBtn in assets/stayodds-icons.js) ----------
YT_GLYPH = (
    '<svg class="yt-glyph" viewBox="0 0 28 20" width="22" height="16" aria-hidden="true">'
    '<rect width="28" height="20" rx="5.5" fill="#ff0033"/><path d="M11.2 5.6v8.8l7.6-4.4z" fill="#fff"/></svg>'
)
_PLAY_SVG = '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M8 5.5v13l11-6.5z" fill="currentColor"/></svg>'


def _yt_attrs(h: dict, inline: bool = False) -> str:
    import html as _html

    esc = lambda v: _html.escape(str(v or ""), quote=True)  # noqa: E731
    short = 1 if h.get("coverageType") == "Short Tour" else 0
    return (
        f'data-yt-id="{esc(h.get("videoId"))}" data-yt-short="{short}" '
        f'data-yt-title="{esc(h.get("name"))} - The Uncharted Itinerary"' + (" data-yt-inline" if inline else "")
    )


def yt_overlay(h: dict, inline: bool = False) -> str:
    """Play button + 'YouTube + Uncharted Itinerary' pill over a hotel photo (empty if no video)."""
    if not h.get("videoId"):
        return ""
    import html as _html

    label = _html.escape(f"Play The Uncharted Itinerary video review of {h.get('name', '')}", quote=True)
    text = "Video tour" if h.get("coverageType") == "Short Tour" else "Video review"
    a = _yt_attrs(h, inline)
    return (
        f'<span class="yt-overlay"><button type="button" class="yt-play" {a} aria-label="{label}" '
        f'title="Watch our video review">{_PLAY_SVG}</button>'
        f'<button type="button" class="yt-badge" {a} tabindex="-1" aria-hidden="true">'
        f'<span class="yt-badge-logo"></span>{YT_GLYPH}<span class="yt-badge-text">{text}</span></button></span>'
    )


def yt_watch_btn(h: dict, label: str, cls: str = "btn btn-outline") -> str:
    if not h.get("videoId"):
        return ""
    return f'<button type="button" class="{cls} yt-watch-btn" {_yt_attrs(h)}>{YT_GLYPH}<span>{label}</span></button>'
