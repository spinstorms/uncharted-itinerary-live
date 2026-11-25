#!/usr/bin/env python3
"""Look up our Partnerize publisher id and approved campaigns (camrefs) and save them.

Keys come only from the environment (repo secrets PARTNERIZE_APP_KEY / PARTNERIZE_USER_KEY);
nothing secret is written. A camref is public: it appears in every prf.hn tracking link.
Output: data/partnerize-campaigns.json
"""
import base64, json, os, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP, USER = os.environ.get("PARTNERIZE_APP_KEY", ""), os.environ.get("PARTNERIZE_USER_KEY", "")
if not (APP and USER):
    sys.exit("Partnerize keys missing")
AUTH = "Basic " + base64.b64encode(f"{APP}:{USER}".encode()).decode()


def get(url):
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:300]}


def shape(o, d=0):
    if d > 3: return "…"
    if isinstance(o, dict): return {k: shape(v, d + 1) for k, v in list(o.items())[:25]}
    if isinstance(o, list): return [shape(o[0], d + 1)] if o else []
    return type(o).__name__


st, pubs = get("https://api.partnerize.com/user/publisher")
print("publisher lookup:", st, json.dumps(shape(pubs))[:800])
ids = []
def walk(o):
    if isinstance(o, dict):
        if "publisher_id" in o: ids.append(str(o["publisher_id"]))
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)
walk(pubs)
for extra in ("https://api.partnerize.com/user", "https://api.partnerize.com/user/account", "https://api.partnerize.com/user/publisher?limit=100&offset=0", "https://api.partnerize.com/v3/partner/publishers", "https://api.partnerize.com/user/brand"):
    st2, d2 = get(extra)
    print("probe", extra.split(".com")[1], st2, json.dumps(shape(d2))[:700])
    walk(d2)
ids = sorted(set(ids))
print("publisher ids:", ids)
out = {"publishers": []}
for pid in ids:
    entry = {"publisher_id": pid, "campaigns": []}
    for url in (f"https://api.partnerize.com/user/publisher/{pid}/campaign/a",
                f"https://api.partnerize.com/user/publisher/{pid}/campaign"):
        st, data = get(url)
        print(url.split('/publisher/')[1], st, json.dumps(shape(data))[:600])
        camps = []
        def grab(o):
            if isinstance(o, dict):
                if "campaign_id" in o and ("title" in o or "name" in o or "camref" in o):
                    camps.append({k: o.get(k) for k in ("campaign_id", "title", "name", "camref", "status", "destination_url", "default_url") if k in o})
                for v in o.values(): grab(v)
            elif isinstance(o, list):
                for v in o: grab(v)
        grab(data)
        if camps:
            entry["campaigns"] = camps
            break
    out["publishers"].append(entry)
for p in out["publishers"]:
    for c in p["campaigns"]:
        print("CAMPAIGN", json.dumps(c))
(ROOT / "data" / "partnerize-campaigns.json").write_text(json.dumps(out, indent=2) + "\n")
