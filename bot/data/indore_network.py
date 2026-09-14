"""Authored Indore bus network.

The BRTS corridor is real: 11.57 km, 22 stations, Rajiv Gandhi Square ↔
Niranjanpur along AB Road, operational since 2013.
See https://en.wikipedia.org/wiki/Indore_Bus_Rapid_Transit_System

Coordinates are approximate (to ~100 m) and exist for map display and rough
sanity checks, not for navigation. Cumulative distances are road km along the
corridor, authored to match the published corridor length.

Each route is authored in ONE direction; the seeder derives the return
direction automatically, so distances have a single source of truth.
"""

# name: (code, latitude, longitude, [aliases])
STOPS = {
    # --- BRTS AB Road corridor ---
    "Rajiv Gandhi Square":      ("RGS", 22.6797, 75.8577, ["Rajiv Gandhi Chauraha", "RGS"]),
    "Aditya Nagar":             ("ADN", 22.6858, 75.8615, []),
    "Indrapuri":                ("IDP", 22.6912, 75.8648, ["Indrapuri Colony"]),
    "Holkar College":           ("HKC", 22.6968, 75.8672, ["Holkar Science College"]),
    "Indore Zoo":               ("ZOO", 22.7018, 75.8698, ["Kamla Nehru Zoo", "Prani Sangrahalaya"]),
    "Navlakha":                 ("NVL", 22.7062, 75.8721, ["Navlakha Square"]),
    "GPO":                      ("GPO", 22.7108, 75.8698, ["General Post Office", "Head Post Office"]),
    "MY Hospital":              ("MYH", 22.7141, 75.8662, ["Maharaja Yeshwantrao Hospital", "MY"]),
    "Geeta Bhawan":             ("GTB", 22.7181, 75.8742, ["Geeta Bhawan Square"]),
    "Palasia":                  ("PLS", 22.7238, 75.8812, ["Palasia Square", "Palasia Thana", "56 Dukan"]),
    "Industry House":           ("IDH", 22.7278, 75.8848, []),
    "LIG Square":               ("LIG", 22.7318, 75.8878, ["LIG Colony", "LIG Chauraha"]),
    "Press Complex":            ("PRC", 22.7358, 75.8905, ["Press Complex Square"]),
    "Shalimar Residency":       ("SHR", 22.7398, 75.8928, []),
    "Vijay Nagar":              ("VJN", 22.7452, 75.8952, ["Vijay Nagar Square", "Vijay Nagar Chauraha"]),
    "Satya Sai Square":         ("SSQ", 22.7502, 75.8968, ["Satya Sai", "Sai Square"]),
    "Orbit Mall":               ("ORB", 22.7548, 75.8982, []),
    "Scheme 74":                ("S74", 22.7592, 75.8995, ["Scheme No 74"]),
    "Shalimar Township":        ("SHT", 22.7638, 75.9008, []),
    "Scheme 78":                ("S78", 22.7678, 75.9018, ["Scheme No 78"]),
    "Lasudiya Mori":            ("LSM", 22.7712, 75.9028, ["Lasudia Mori"]),
    "Niranjanpur":              ("NJP", 22.7748, 75.9038, ["Niranjanpur Square"]),

    # --- City network ---
    "Rajwada":                  ("RJW", 22.7177, 75.8545, ["Rajwada Palace", "Raj Wada"]),
    "Sarwate Bus Stand":        ("SRW", 22.7148, 75.8698, ["Sarwate", "Sarvate Bus Stand"]),
    "Indore Junction":          ("IJN", 22.7185, 75.8672, ["Railway Station", "Indore Railway Station"]),
    "Gangwal Bus Stand":        ("GNW", 22.7085, 75.8365, ["Gangwal"]),
    "Bhawarkuan":               ("BWK", 22.6884, 75.8571, ["Bhanwarkuan", "Bhawarkuan Square"]),
    "Annapurna":                ("ANP", 22.6935, 75.8412, ["Annapurna Temple", "Annapurna Road"]),
    "Chhoti Gwaltoli":          ("CGT", 22.7215, 75.8712, []),
    "Regal Square":             ("RGL", 22.7202, 75.8628, ["Regal", "Regal Chauraha"]),
    "Madhumilan Square":        ("MDM", 22.7168, 75.8608, ["Madhumilan"]),
    "Khajrana":                 ("KJR", 22.7365, 75.9082, ["Khajrana Square", "Khajrana Ganesh"]),
    "Bengali Square":           ("BNG", 22.7288, 75.9192, ["Bengali Chauraha", "Bengali"]),
    "Musakhedi":                ("MSK", 22.7015, 75.8905, ["Musakhedi Square"]),
    "Airport":                  ("ARP", 22.7218, 75.8011, ["Devi Ahilya Bai Holkar Airport", "Indore Airport"]),
    "Sukhliya":                 ("SKL", 22.7565, 75.8865, []),
    "Malwa Mill":               ("MLM", 22.7245, 75.8752, ["Malwa Mill Square"]),
    "Patnipura":                ("PTN", 22.7412, 75.8802, ["Patnipura Square"]),
    "Bapat Square":             ("BPT", 22.7522, 75.8778, ["Bapat Chauraha"]),
    "Nanda Nagar":              ("NND", 22.7358, 75.8698, []),
    "Rau":                      ("RAU", 22.6415, 75.8158, ["Rau Circle"]),
}


# code: (name, kind, [(stop_name, cumulative_km, offset_minutes), ...])
ROUTES = {
    "BRTS-01": (
        "iBus AB Road Corridor",
        "BRTS",
        [
            ("Rajiv Gandhi Square", 0.00, 0),
            ("Aditya Nagar", 0.70, 2),
            ("Indrapuri", 1.30, 4),
            ("Holkar College", 1.90, 6),
            ("Indore Zoo", 2.50, 8),
            ("Navlakha", 3.10, 10),
            ("GPO", 3.80, 13),
            ("MY Hospital", 4.30, 15),
            ("Geeta Bhawan", 5.00, 17),
            ("Palasia", 5.70, 20),
            ("Industry House", 6.30, 22),
            ("LIG Square", 6.90, 24),
            ("Press Complex", 7.40, 26),
            ("Shalimar Residency", 7.90, 28),
            ("Vijay Nagar", 8.50, 30),
            ("Satya Sai Square", 9.00, 32),
            ("Orbit Mall", 9.50, 34),
            ("Scheme 74", 10.00, 36),
            ("Shalimar Township", 10.50, 38),
            ("Scheme 78", 10.90, 40),
            ("Lasudiya Mori", 11.20, 42),
            ("Niranjanpur", 11.57, 44),
        ],
    ),
    "CITY-02": (
        "Indore Junction – Airport",
        "CITY",
        [
            ("Indore Junction", 0.00, 0),
            ("Sarwate Bus Stand", 0.60, 2),
            ("Madhumilan Square", 1.20, 5),
            ("Regal Square", 1.80, 8),
            ("Rajwada", 2.60, 12),
            ("Gangwal Bus Stand", 4.40, 18),
            ("Airport", 8.20, 30),
        ],
    ),
    "CITY-03": (
        "Rajwada – Niranjanpur",
        "CITY",
        [
            ("Rajwada", 0.00, 0),
            ("Regal Square", 0.80, 3),
            ("Chhoti Gwaltoli", 1.60, 6),
            ("Malwa Mill", 2.40, 9),
            ("Palasia", 3.50, 13),
            ("Patnipura", 5.20, 18),
            ("Nanda Nagar", 6.30, 22),
            ("Sukhliya", 7.80, 27),
            ("Bapat Square", 9.10, 31),
            ("Niranjanpur", 11.00, 38),
        ],
    ),
    "CITY-04": (
        "Bhawarkuan – Bengali Square",
        "CITY",
        [
            ("Bhawarkuan", 0.00, 0),
            ("Musakhedi", 1.90, 6),
            ("Geeta Bhawan", 3.40, 11),
            ("Palasia", 4.60, 15),
            ("Malwa Mill", 5.50, 18),
            ("Khajrana", 7.90, 26),
            ("Bengali Square", 9.60, 32),
        ],
    ),
    "CITY-05": (
        "Rau – Indore Junction",
        "CITY",
        [
            ("Rau", 0.00, 0),
            ("Annapurna", 6.20, 20),
            ("Bhawarkuan", 8.10, 26),
            ("Holkar College", 9.60, 31),
            ("Madhumilan Square", 11.40, 37),
            ("Indore Junction", 12.30, 41),
        ],
    ),
    "CITY-06": (
        "Gangwal – Vijay Nagar",
        "CITY",
        [
            ("Gangwal Bus Stand", 0.00, 0),
            ("Annapurna", 1.70, 6),
            ("Rajwada", 3.30, 12),
            ("Chhoti Gwaltoli", 4.60, 16),
            ("Geeta Bhawan", 6.10, 21),
            ("Palasia", 7.20, 25),
            ("LIG Square", 8.60, 30),
            ("Vijay Nagar", 10.40, 36),
        ],
    ),
}


# (min_km, max_km or None, price)
FARE_SLABS = [
    (0, 3, 5),
    (3, 6, 10),
    (6, 10, 15),
    (10, 15, 20),
    (15, None, 25),
]


# code, kind, seats
BUSES = [
    ("MP09 FA 1201", "BRTS", 40),
    ("MP09 FA 1202", "BRTS", 40),
    ("MP09 FA 1203", "BRTS", 40),
    ("MP09 FA 1204", "BRTS", 40),
    ("MP09 GB 2101", "CITY", 32),
    ("MP09 GB 2102", "CITY", 32),
    ("MP09 GB 2103", "CITY", 32),
    ("MP09 GB 2104", "CITY", 32),
    ("MP09 GB 2105", "CITY", 32),
    ("MP09 GB 2106", "CITY", 32),
]


# Departures per route direction: (first_hour, last_hour, headway_minutes)
SERVICE_PATTERN = {
    "BRTS": (6, 22, 20),
    "CITY": (6, 21, 45),
}
