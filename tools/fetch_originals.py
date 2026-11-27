import urllib.request, pathlib
OUT = pathlib.Path("photo-candidates/originals"); OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "StayOdds photo review (stayodds.com)"}
URLS_DIRECT = {
 "aman-tokyo": "https://www.aman.com/sites/default/files/styles/central_carousel_extra_large_2x/public/2023-11/aman_tokyo_japan_-_interior_-_swimming_pool_1.webp?itok=KuSdyGI3",
 "amanfayun": "https://www.aman.com/sites/default/files/styles/central_carousel_large_2x/public/2021-02/Aman_Amanfayun_Gallery_8.webp?itok=c0kkHt6Q",
 "bulgari-hotel-shanghai": "https://www.bulgarihotels.com/mgnl/.imaging/mte/theme/landscape/dam/Shangai/Hotel/Destination/Hero-shot-view-final-template-landascape.jpg/jcr:content/Hero-shot-view-final-template-landascape.jpg",
 "bulgari-hotel-tokyo": "https://www.bulgarihotels.com/mgnl/.imaging/mte/theme/landscape/dam/Tokyo/Landing/FACADE-NIGHT-1_landscape.jpg/jcr:content/FACADE-NIGHT-1_landscape.jpg",
 "casa-chameleon-las-catalinas": "https://www.casachameleonhotels.com/wp-content/uploads/2026/11/Two-MICHELIN-Keys-2026-Casa-Chameleon-Las-Catalinas-Costa-Rica.jpg",
 "estancia-cristina": "https://estanciacristina.com/wp-content/uploads/2025/05/5-Lodge-Panoramica-STAY.jpg",
 "four-seasons-hotel-nashville": "https://www.fourseasons.com/alt/img-opt/~65.1920.0,0000-167,5008-3000,0000-1687,5000/publish/content/dam/fourseasons/images/web/NSH/NSH_146_original.jpg",
 "four-seasons-hotel-ritz-lisbon": "https://www.fourseasons.com/alt/img-opt/~65.1920.0,0000-39,4388-3000,0000-1687,5000/publish/content/dam/fourseasons/images/web/LIS/LIS_1946_original.jpg",
 "four-seasons-hotel-san-francisco-at-embarcadero": "https://www.fourseasons.com/alt/img-opt/~65.1920.0,0000-212,7161-3000,0000-1687,5000/publish/content/dam/fourseasons/images/web/EMB/EMB_154_original.jpg",
 "rosewood-hong-kong": "https://picasso.rosewoodhotelgroup.com/transform/c55f3d95-f8f4-4ae5-ac6f-10f18634a625/RWHKG_3-0_Brand-com_Assets_Destination_Landscape-Exterior",
 "royal-mansour-marrakech": "https://www.royalmansour.com/wp-content/uploads/2023/05/RM-Marrakech-3.jpg",
 "mandarin-oriental-downtown-dubai": "https://media.ffycdn.net/eu/mandarin-oriental-hotel-group/k2F76A6VmSheq6GzDDcc.jpg"
}
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
for k, u in ({} if (OUT / "bali.jpg").exists() else URLS).items():
    for attempt in range(6):
        try:
            req = urllib.request.Request(thumb(u), headers=UA)
            (OUT / f"{k}.jpg").write_bytes(urllib.request.urlopen(req, timeout=60).read())
            print(k, (OUT / f"{k}.jpg").stat().st_size); break
        except Exception as e:
            print(k, "retry", e); time.sleep(15)
    time.sleep(8)

for k, u in URLS_DIRECT.items():
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36", "Accept": "image/avif,image/webp,image/jpeg,*/*"})
        (OUT / f"{k}.img").write_bytes(urllib.request.urlopen(req, timeout=60).read())
        print(k, (OUT / f"{k}.img").stat().st_size)
    except Exception as e:
        print(k, "FAILED", e)
