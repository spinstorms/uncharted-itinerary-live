#!/usr/bin/env python3
"""Print LiteAPI hotel name and every room/rate for given hotel ids (read-only check). Usage: probe_rates.py ID [ID...]"""
import json, os, sys, urllib.request, urllib.parse
from datetime import date, timedelta
K = os.environ["NUITEE_API_KEY"]
H = {"X-API-Key": K, "Accept": "application/json", "Content-Type": "application/json"}
def call(u, b=None):
    r = urllib.request.Request(u, data=json.dumps(b).encode() if b else None, headers=H, method="POST" if b else "GET")
    with urllib.request.urlopen(r, timeout=40) as x:
        return json.loads(x.read().decode())
for hid in sys.argv[1:]:
    info = call("https://api.liteapi.travel/v3.0/data/hotel?" + urllib.parse.urlencode({"hotelId": hid})).get("data") or {}
    print(f"== {hid}: {info.get('name')} | {info.get('address')} {info.get('city')} {info.get('country')} | stars {info.get('starRating')}")
    ci = date.today() + timedelta(days=60)
    d = call("https://api.liteapi.travel/v3.0/hotels/rates", {"hotelIds": [hid], "checkin": ci.isoformat(), "checkout": (ci + timedelta(days=2)).isoformat(), "currency": "GBP", "guestNationality": "GB", "occupancies": [{"adults": 2}]})
    for row in d.get("data") or []:
        for rt in (row.get("roomTypes") or [])[:12]:
            r0 = (rt.get("rates") or [{}])[0]
            print(f"   {(rt.get('offerRetailRate') or {}).get('amount')} {(rt.get('offerRetailRate') or {}).get('currency')} | {r0.get('name')} | board {r0.get('boardName')} | {r0.get('retailRate', {}).get('total', [{}])[0].get('amount') if isinstance(r0.get('retailRate'), dict) else ''}")
