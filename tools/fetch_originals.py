import urllib.request, pathlib
OUT = pathlib.Path("photo-candidates/originals"); OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "StayOdds photo review (stayodds.com)"}
URLS = {
 "maldives": "https://upload.wikimedia.org/wikipedia/commons/5/51/Kuredo_Resort_Malediven_%2828800496576%29.jpg",
 "bora-bora": "https://upload.wikimedia.org/wikipedia/commons/7/78/Bora_Bora_%2816542797633%29.jpg",
 "seychelles": "https://upload.wikimedia.org/wikipedia/commons/7/73/Anse_Source_d%27Argent_-_La_Digue_-_Seychelles_-_06.jpg",
 "bali": "https://upload.wikimedia.org/wikipedia/commons/f/f8/Rice_terraces%2C_Ubud%2C_Bali.jpg",
}
import time
def thumb(u, w=3840):
    base, name = u.rsplit("/", 1)
    a, b = base.rsplit("/commons/", 1)
    return f"{a}/commons/thumb/{b}/{name}/{w}px-{name}"
for k, u in URLS.items():
    for attempt in range(6):
        try:
            req = urllib.request.Request(thumb(u), headers=UA)
            (OUT / f"{k}.jpg").write_bytes(urllib.request.urlopen(req, timeout=60).read())
            print(k, (OUT / f"{k}.jpg").stat().st_size); break
        except Exception as e:
            print(k, "retry", e); time.sleep(15)
    time.sleep(8)
