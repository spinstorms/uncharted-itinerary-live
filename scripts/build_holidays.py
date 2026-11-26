#!/usr/bin/env python3
"""/holidays/ — pick a holiday (Christmas, New Year, Easter...) and every hotel link opens with those dates set.

Hotels shown: the stays we filmed, then the hotels guests rate highest (verified guest score, 300+ reviews).
Each link goes to the hotel page with ?when=<key>, which selects the dates and checks the live price there.
Nothing here is estimated: guest scores are licensed scores, prices are the indicative 'from' price we show elsewhere.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from build_award_lists import PAGE_CSS, _shell, michelin_keys, w50_rank

SITE = "https://stayodds.com"


def esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _g(h: dict[str, Any]) -> tuple[int | None, int]:
    lic = ((h.get("verifiedGuest") or {}).get("licensed") or {})
    g = lic.get("normalized100")
    return (int(g) if g is not None else None), int(lic.get("reviewCount") or 0)


def _stars(h: dict[str, Any]) -> int:
    best = 0
    for d in h.get("dining") or []:
        m = re.match(r"([123]) MICHELIN Star", d.get("distinction") or "")
        if m:
            best = max(best, int(m.group(1)))
    return best


def _tags(h: dict[str, Any]) -> list[str]:
    g, rc = _g(h)
    t = []
    if (g or 0) >= 93 and rc >= 300:
        t.append("top")
    if w50_rank(h):
        t.append("w50")
    if michelin_keys(h):
        t.append("keys")
    if _stars(h):
        t.append("stars")
    return t


def _row(h: dict[str, Any]) -> str:
    g, rc = _g(h)
    price = (h.get("priceSnapshot") or {}).get("nightlyGbp")
    thumb = h.get("thumbnail") or ""
    img = f'<img src="/{esc(thumb)}" alt="" loading="lazy" width="96" height="72">' if thumb else '<span class="hd-noimg"></span>'
    badges = []
    if h.get("visitedByUs"):
        badges.append('<span class="al-badge hd-film">&#9654; We filmed it</span>')
    w, k, st = w50_rank(h), michelin_keys(h), _stars(h)
    if w:
        badges.append(f'<span class="al-badge">No. {w} World\'s 50 Best</span>')
    if k:
        badges.append(f'<span class="al-badge">{k} MICHELIN Key{"s" if k > 1 else ""}</span>')
    if st:
        badges.append(f'<span class="al-badge">{st}-star restaurant</span>')
    score = f"<strong>{g}</strong>guest score" if g is not None else "<strong>—</strong>no guest score yet"
    from_txt = f'<span class="hd-from">from £{int(price):,}/nt</span>' if price else ""
    return (
        f'<li class="hd-row" data-region="{esc(h.get("region"))}" data-tags="{" ".join(_tags(h))}">{img}'
        f'<div><a class="al-name" href="/stayodds/{esc(h["id"])}/">{esc(h["name"])}</a>'
        f'<div class="al-meta">{esc(h.get("location"))}, {esc(h.get("country"))}</div>'
        f'<div class="al-badges">{"".join(badges)}</div></div>'
        f'<div class="hd-side"><div class="al-score">{score}</div>{from_txt}'
        f'<a class="hd-cta" data-hotel="{esc(h["id"])}" href="/stayodds/{esc(h["id"])}/?when=christmas">Check <span class="hd-occ">Christmas</span> prices &rarr;</a></div></li>'
    )


CSS = """
<style>
.hd-quick{display:flex;gap:8px;overflow-x:auto;padding:2px 0 8px;margin:0 0 14px}
.hd-q{flex:none;display:flex;flex-direction:column;align-items:flex-start;gap:1px;background:#fff;border:1px solid #D1D5DB;border-radius:12px;padding:9px 14px;cursor:pointer;font:inherit;color:#0F172A;min-height:44px}
.hd-q b{font-size:14px}.hd-q span{font-size:12px;color:#64748B}
.hd-q[aria-pressed="true"]{background:#16A34A;border-color:#16A34A;color:#fff}.hd-q[aria-pressed="true"] span{color:#DCFCE7}
.hd-filters{display:flex;gap:8px;overflow-x:auto;padding:2px 0 6px;margin:0 0 10px}
.hd-filters button{flex:none;font:inherit;font-size:13.5px;font-weight:700;padding:9px 14px;border-radius:999px;border:1px solid #FDBA74;background:#FFF7ED;color:#9A3412;cursor:pointer;min-height:40px}
.hd-filters button[aria-pressed="true"]{background:#FF5D22;border-color:#FF5D22;color:#fff}
.hd-more{display:block;margin:16px auto 0;font:inherit;font-weight:700;padding:10px 18px;border-radius:999px;border:1px solid rgba(100,110,130,.4);background:transparent;color:inherit;cursor:pointer}
.hd-regions{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 16px}
.hd-regions button{font:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:999px;border:1px solid rgba(100,110,130,.35);background:transparent;color:inherit;cursor:pointer}
.hd-regions button[aria-pressed="true"]{background:#0b2540;color:#fff;border-color:#0b2540}
.hd-wrap h2{font-size:21px;margin:26px 0 4px}.hd-wrap h2+p{margin:0 0 10px;color:var(--muted,#5b6472);font-size:14px}
.hd-list{list-style:none;margin:0;padding:0;border-top:1px solid rgba(100,110,130,.25)}
.hd-row{display:grid;grid-template-columns:96px 1fr auto;gap:14px;align-items:center;padding:12px 2px;border-bottom:1px solid rgba(100,110,130,.25)}
.hd-row img,.hd-noimg{width:96px;height:72px;object-fit:cover;border-radius:10px;background:#E5E7EB;display:block}
.hd-side{display:flex;flex-direction:column;align-items:flex-end;gap:4px;text-align:right}
.hd-from{font-size:12px;color:var(--muted,#5b6472)}
.hd-cta{display:inline-block;background:#16A34A;color:#fff!important;font-weight:700;font-size:13.5px;padding:9px 14px;border-radius:10px;text-decoration:none;white-space:nowrap}
.hd-cta:hover{background:#15803D}
.hd-film{background:#FFE4D6!important;color:#9A3412}
.hd-picked{font-weight:700;color:#15803D;font-size:14px;margin:-6px 0 12px}
@media (max-width:620px){.hd-row{grid-template-columns:72px 1fr}.hd-row img,.hd-noimg{width:72px;height:56px}.hd-side{grid-column:1/-1;flex-direction:row;flex-wrap:wrap;align-items:center;justify-content:space-between;text-align:left}.hd-side .al-score strong{display:inline;margin-right:4px}.hd-cta{flex-basis:100%;text-align:center}}
</style>
"""

JS = r"""
<script>
(function(){
  const fmt=(d)=>d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0");
  const add=(d,n)=>new Date(d.getFullYear(),d.getMonth(),d.getDate()+n);
  const today=new Date();today.setHours(0,0,0,0);
  function easter(y){const a=y%19,b=Math.floor(y/100),c=y%100,d=Math.floor(b/4),e=b%4,f=Math.floor((b+8)/25),g=Math.floor((b-f+1)/3),h=(19*a+b-d-g+15)%30,i=Math.floor(c/4),k=c%4,l=(32+2*e+2*i-h-k)%7,m=Math.floor((a+11*h+22*l)/451),mo=Math.floor((h+l-7*m+114)/31);return new Date(y,mo-1,((h+l-7*m+114)%31)+1);}
  function nextOf(fn){const y=today.getFullYear();let r=fn(y);if(r[0]<=today)r=fn(y+1);return r;}
  const fri=add(today,((5-today.getDay()+7)%7)||7);
  const Q=[
    {key:"christmas",label:"Christmas",range:nextOf(y=>[new Date(y,11,23),new Date(y,11,27)])},
    {key:"newyear",label:"New Year",range:nextOf(y=>[new Date(y,11,30),new Date(y+1,0,2)])},
    {key:"valentines",label:"Valentine's",range:nextOf(y=>[new Date(y,1,13),new Date(y,1,15)])},
    {key:"easter",label:"Easter",range:nextOf(y=>{const e=easter(y);return [add(e,-2),add(e,2)];})},
    {key:"summer",label:"Summer week",range:nextOf(y=>[new Date(y,7,1),new Date(y,7,8)])},
    {key:"weekend",label:(fri-today)<=5*86400000?"This weekend":"Next weekend",range:[fri,add(fri,2)]},
  ];
  const sd=(d)=>d.toLocaleDateString("en-GB",{day:"numeric",month:"short"});
  const wrap=document.getElementById("hdQuick"),picked=document.getElementById("hdPicked");
  let cur=new URLSearchParams(location.search).get("when");if(!Q.some(q=>q.key===cur))cur="christmas";
  function apply(){
    const q=Q.find(x=>x.key===cur);
    wrap.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b.dataset.key===cur)));
    const n=Math.round((q.range[1]-q.range[0])/86400000);
    picked.textContent=sd(q.range[0])+" – "+sd(q.range[1])+" · "+n+" night"+(n===1?"":"s")+". Every link below opens with these dates and checks the live price.";
    document.querySelectorAll(".hd-cta").forEach(a=>{a.href="/stayodds/"+a.dataset.hotel+"/?when="+cur;a.querySelector(".hd-occ").textContent=q.label;});
    try{localStorage.setItem("so_dates",JSON.stringify({ci:fmt(q.range[0]),co:fmt(q.range[1]),ad:"2"}));}catch(_){}
    const u=new URL(location.href);u.searchParams.set("when",cur);history.replaceState(null,"",u);
  }
  Q.forEach(q=>{const b=document.createElement("button");b.type="button";b.className="hd-q";b.dataset.key=q.key;
    b.innerHTML="<b>"+q.label+"</b><span>"+sd(q.range[0])+" – "+sd(q.range[1])+"</span>";
    b.addEventListener("click",()=>{cur=q.key;apply();});wrap.appendChild(b);});
  apply();
  const rw=document.getElementById("hdRegions"),fw=document.getElementById("hdFilters"),moreBtn=document.getElementById("hdMoreBtn");
  const TITLES={top:"Guests' top rated",w50:"World's 50 Best hotels",keys:"MICHELIN Key hotels",stars:"Hotels with a Michelin-star restaurant","":"All hotels"};
  let f="top",reg="",limit=40;
  function filter(){
    document.querySelectorAll("#hdFilmed,#hdMore").forEach(sec=>{
      let shown=0,match=0;const paged=sec.id==="hdMore";
      sec.querySelectorAll(".hd-row").forEach(li=>{
        const ok=(!f||(" "+li.dataset.tags+" ").includes(" "+f+" "))&&(!reg||li.dataset.region===reg);
        if(ok)match++;const vis=ok&&(!paged||match<=limit);li.hidden=!vis;if(vis)shown++;});
      sec.hidden=match===0;sec.querySelector(".hd-n").textContent=match;
      if(paged){moreBtn.hidden=match<=limit;moreBtn.textContent="Show more ("+(match-limit)+" more)";}
    });
    document.getElementById("hdMoreTitle").textContent=TITLES[f];
  }
  function press(wrap,b){wrap.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));}
  fw.addEventListener("click",(e)=>{const b=e.target.closest("button");if(!b)return;press(fw,b);f=b.dataset.f;limit=40;filter();});
  rw.addEventListener("click",(e)=>{const b=e.target.closest("button");if(!b)return;press(rw,b);reg=b.dataset.region;limit=40;filter();});
  moreBtn.addEventListener("click",()=>{limit+=40;filter();});
  filter();
})();
</script>
"""


def write_holidays(dist: Path, hotels: list[dict[str, Any]], template: str) -> list[str]:
    head, foot = _shell(template)
    head, foot = head.replace('"../../', '"/').replace("'../../", "'/"), foot.replace('"../../', '"/').replace("'../../", "'/")
    live = [h for h in hotels if (h.get("propertyStatus") or "open") not in ("closed", "Closed")]
    filmed = sorted([h for h in live if h.get("visitedByUs")], key=lambda h: (-(_g(h)[0] or 0), h["name"].lower()))
    fav = sorted(
        [h for h in live if not h.get("visitedByUs") and _tags(h)],
        key=lambda h: (-(_g(h)[0] or 0), -_g(h)[1], h["name"].lower()),
    )
    regions = sorted({h.get("region") for h in filmed + fav if h.get("region")})
    reg_btns = '<button type="button" data-region="" aria-pressed="true">All</button>' + "".join(
        f'<button type="button" data-region="{esc(r)}" aria-pressed="false">{esc(r)}</button>' for r in regions
    )
    title = "Christmas, New Year & holiday hotel dates"
    desc = "Pick Christmas, New Year, Easter or another holiday and check live prices at top-rated luxury hotels with those dates already set."
    url = f"{SITE}/holidays/"
    head = re.sub(r"<title>.*?</title>", f"<title>{esc(title)} | StayOdds</title>", head, flags=re.S)
    for prop, val in (("description", desc),):
        head = re.sub(r'(<meta name="description" content=")[^"]*(")', lambda m: m.group(1) + esc(val) + m.group(2), head)
    head = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), head)
    head = re.sub(r'(<meta property="og:title" content=")[^"]*(")', lambda m: m.group(1) + esc(title) + m.group(2), head)
    head = re.sub(r'(<meta property="og:description" content=")[^"]*(")', lambda m: m.group(1) + esc(desc) + m.group(2), head)
    head = re.sub(r'(<meta property="og:url" content=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), head)
    body = (
        '<main><div class="al-wrap hd-wrap"><div class="al-eyebrow">Holiday dates</div>'
        "<h1>Where to stay this Christmas, New Year or Easter</h1>"
        '<p class="al-sub">Pick your holiday. Every hotel below then opens with those dates already chosen, '
        "and the live price for them is checked for you.</p>"
        '<div class="hd-quick" id="hdQuick" role="group" aria-label="Holiday dates"></div>'
        '<p class="hd-picked" id="hdPicked"></p>'
        '<div class="hd-filters" id="hdFilters" role="group" aria-label="Show">'
        '<button type="button" data-f="top" aria-pressed="true">&#9733; Guests\' top rated</button>'
        '<button type="button" data-f="w50" aria-pressed="false">World\'s 50 Best</button>'
        '<button type="button" data-f="keys" aria-pressed="false">MICHELIN Keys</button>'
        '<button type="button" data-f="stars" aria-pressed="false">Michelin-star dining</button>'
        '<button type="button" data-f="" aria-pressed="false">All</button></div>'
        f'<div class="hd-regions" id="hdRegions" role="group" aria-label="Region">{reg_btns}</div>'
        "<section id=\"hdFilmed\"><h2>Stays we've filmed</h2><p><span class=\"hd-n\"></span> hotels we checked into ourselves, best guest score first.</p>"
        f'<ol class="hd-list">{"".join(_row(h) for h in filmed)}</ol></section>'
        '<section id="hdMore"><h2 id="hdMoreTitle">Guests\' favourites</h2><p><span class="hd-n"></span> hotels, best guest score first.</p>'
        f'<ol class="hd-list">{"".join(_row(h) for h in fav)}</ol>'
        '<button type="button" class="hd-more" id="hdMoreBtn" hidden>Show more hotels</button></section>'
        '<p class="al-note" style="margin-top:22px">Guest scores are verified licensed guest ratings. '
        "“From” prices are indicative (middle of three sample dates); your holiday dates usually cost more, "
        "so the live price on each hotel page is the one to go by.</p>"
        "</div></main>"
    )
    page = head.replace("</head>", PAGE_CSS + CSS + "</head>", 1) + body + foot + JS + "</body>\n</html>\n"
    out = dist / "holidays"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    return ["/holidays/"]
