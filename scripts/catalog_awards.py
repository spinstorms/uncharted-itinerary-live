"""Hotels from the official 2026 award lists that were missing from the StayOdds directory.

Identity fields only (slug, name, city, country, iso2, region, brand). Every rating, review, video and photo is
pulled from a real source by the sync scripts - nothing here is a score or a claim.

Source for ranks: The World's 50 Best Hotels 2026
  https://www.the50.com/hotels/best-in-the-world/list/1-50
  https://www.the50.com/stories/News/the-50-best-hotels-2026-the-51-100-list.html
"""

# (slug, name, city, country, iso2, region, brand)
AWARD_HOTEL_ADDITIONS = [
    ("casa-maria-luigia-modena", "Casa Maria Luigia", "Modena", "Italy", "IT", "Europe", "Independent"),
    ("desa-potato-head-bali", "Desa Potato Head", "Seminyak, Bali", "Indonesia", "ID", "Asia", "Potato Head"),
    ("patina-osaka", "Patina Osaka", "Osaka", "Japan", "JP", "Asia", "Patina"),
    ("hotel-de-paris-monte-carlo", "Hôtel de Paris Monte-Carlo", "Monte-Carlo", "Monaco", "MC", "Europe", "Monte-Carlo SBM"),
    ("la-reserve-paris", "La Réserve Paris", "Paris", "France", "FR", "Europe", "La Réserve"),
    ("palacio-nazarenas-cusco", "Palacio Nazarenas, A Belmond Hotel", "Cusco", "Peru", "PE", "Americas", "Belmond"),
    ("sofitel-legend-casco-viejo-panama", "Sofitel Legend Casco Viejo", "Panama City", "Panama", "PA", "Americas", "Accor / Sofitel Legend"),
    ("orient-express-la-minerva-rome", "Orient Express La Minerva", "Rome", "Italy", "IT", "Europe", "Orient Express"),
    ("forestis-dolomites", "Forestis Dolomites", "Brixen, South Tyrol", "Italy", "IT", "Europe", "Independent"),
    ("macakizi-bodrum", "Maçakızı", "Bodrum", "Turkey", "TR", "Europe", "Independent"),
    ("hotel-das-cataratas-belmond", "Hotel das Cataratas, A Belmond Hotel", "Iguassu Falls", "Brazil", "BR", "Americas", "Belmond"),
    ("the-fifth-avenue-hotel-new-york", "The Fifth Avenue Hotel", "New York", "United States", "US", "Americas", "Independent"),
    ("carlton-cannes-regent", "Carlton Cannes, a Regent Hotel", "Cannes", "France", "FR", "Europe", "IHG / Regent"),
    ("capella-hanoi", "Capella Hanoi", "Hanoi", "Vietnam", "VN", "Asia", "Capella"),
    ("waldorf-astoria-osaka", "Waldorf Astoria Osaka", "Osaka", "Japan", "JP", "Asia", "Hilton / Waldorf Astoria"),
    ("mandarin-oriental-shenzhen", "Mandarin Oriental, Shenzhen", "Shenzhen", "China", "CN", "Asia", "Mandarin Oriental"),
    ("villa-treville-positano", "Villa Treville", "Positano", "Italy", "IT", "Europe", "Independent"),
    ("the-greenwich-hotel-new-york", "The Greenwich Hotel", "New York", "United States", "US", "Americas", "Independent"),
    ("the-maybourne-riviera", "The Maybourne Riviera", "Roquebrune-Cap-Martin", "France", "FR", "Europe", "Maybourne"),
    ("the-johri-jaipur", "The Johri", "Jaipur", "India", "IN", "Asia", "Independent"),
    ("wynn-palace-macau", "Wynn Palace", "Cotai, Macau", "Macau", "MO", "Asia", "Wynn"),
    ("the-peninsula-shanghai", "The Peninsula Shanghai", "Shanghai", "China", "CN", "Asia", "The Peninsula"),
    ("maroma-belmond-riviera-maya", "Maroma, A Belmond Hotel", "Punta Maroma, Riviera Maya", "Mexico", "MX", "Caribbean & Mexico", "Belmond"),
]

# Hotels already in the directory whose 2026 World's 50 Best rank tag was missing: slug -> rank
W50B_2026_MISSING_TAGS = {
    "rosewood-sao-paulo": 6,
    "mandarin-oriental-qianmen-beijing": 7,
    "jumeirah-marsa-al-arab-dubai": 15,
    "san-ysidro-ranch-montecito": 22,
    "copacabana-palace-belmond-rio": 29,
    "the-taj-mahal-palace-mumbai": 30,
    "the-peninsula-istanbul": 31,
    "mount-nelson-belmond-cape-town": 34,
    "hotel-du-couvent-nice": 38,
    "estelle-manor-oxfordshire": 43,
    "splendido-belmond-portofino": 60,
    "rosewood-castiglion-del-bosco": 62,
    "the-okura-tokyo": 69,
    "rosewood-bangkok": 70,
    "amangalla-sri-lanka": 71,
    "four-seasons-tamarindo": 74,
    "the-mitsui-kyoto": 79,
    "huka-lodge-taupo": 82,
    "the-calile-hotel-brisbane": 83,
    "borgo-santandrea-amalfi": 84,
    "castello-di-reschio-umbria": 95,
    "oberoi-udaivilas": 98,
}

# Rank for every newly added hotel above
W50B_2026_NEW = {
    "casa-maria-luigia-modena": 18,
    "desa-potato-head-bali": 21,
    "patina-osaka": 33,
    "hotel-de-paris-monte-carlo": 40,
    "maroma-belmond-riviera-maya": 47,
    "la-reserve-paris": 51,
    "palacio-nazarenas-cusco": 54,
    "sofitel-legend-casco-viejo-panama": 63,
    "orient-express-la-minerva-rome": 66,
    "forestis-dolomites": 68,
    "macakizi-bodrum": 76,
    "hotel-das-cataratas-belmond": 77,
    "the-fifth-avenue-hotel-new-york": 78,
    "carlton-cannes-regent": 80,
    "capella-hanoi": 81,
    "waldorf-astoria-osaka": 89,
    "mandarin-oriental-shenzhen": 90,
    "villa-treville-positano": 91,
    "the-greenwich-hotel-new-york": 92,
    "the-maybourne-riviera": 93,
    "the-johri-jaipur": 94,
    "wynn-palace-macau": 96,
    "the-peninsula-shanghai": 99,
}
