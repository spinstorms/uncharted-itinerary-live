"""Find photo candidates (hero destinations from Unsplash and Wikimedia Commons; exterior
shots for hotels whose card photo is an interior) and save small previews plus credits."""
import json, os, sys, urllib.parse, urllib.request, pathlib, time
OUT = pathlib.Path("photo-candidates"); OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "StayOdds photo review (stayodds.com; contact via site)"}
def get(url, raw=False):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        b = r.read()
    return b if raw else json.loads(b)
def save(url, path):
    try:
        path.write_bytes(get(url, raw=True)); return True
    except Exception as e:
        print("fail", url, e); return False
meta = {}
HERO = {"maldives": "maldives aerial", "bora-bora": "bora bora", "seychelles": "seychelles beach", "bali": "bali rice terraces"}
for key, q in HERO.items():
    items = []
    try:
        d = get("https://unsplash.com/napi/search/photos?per_page=8&orientation=landscape&query=" + urllib.parse.quote(q))
        for i, p in enumerate(d.get("results", [])[:8]):
            u = p["urls"]["raw"]; name = f"hero-{key}-u{i}.jpg"
            if save(u + "&w=900&q=70&fm=jpg", OUT / name):
                items.append({"file": name, "source": "unsplash", "id": p["id"], "raw": u, "w": p["width"], "h": p["height"],
                              "credit": p["user"]["name"], "page": p["links"]["html"]})
    except Exception as e:
        print("unsplash fail", key, e)
    meta[f"hero-{key}"] = items
def commons(query, n):
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=%d"
           "&gsrsearch=%s&prop=imageinfo&iiprop=url|size|extmetadata|mime&iiurlwidth=700") % (n, urllib.parse.quote(query))
    d = get(api); res = []
    for p in (d.get("query", {}).get("pages", {}) or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]
        if ii.get("mime") not in ("image/jpeg", "image/png"): continue
        em = ii.get("extmetadata", {})
        res.append({"title": p["title"], "thumb": ii.get("thumburl"), "url": ii.get("url"), "w": ii.get("width"), "h": ii.get("height"),
                    "license": em.get("LicenseShortName", {}).get("value"), "artist": em.get("Artist", {}).get("value", "")[:200],
                    "page": ii.get("descriptionurl")})
    return res
hotels = json.loads(pathlib.Path("tools/flagged.json").read_text())
for hid, name in hotels.items():
    items = []
    try:
        for j, r in enumerate(commons(name, 8)[:6]):
            fn = f"{hid}-c{j}.jpg"
            if r["thumb"] and save(r["thumb"], OUT / fn):
                r["file"] = fn; items.append(r)
    except Exception as e:
        print("commons fail", hid, e)
    meta[hid] = items
    time.sleep(0.5)
(OUT / "meta.json").write_text(json.dumps(meta, indent=1))
print({k: len(v) for k, v in meta.items()})
