"""Genera les 24 vivendes noves (ids 27-50) de house_data_v2.json.

Model:
  * Variables categòriques principals (zona, tipus d'operació, tipus d'immoble,
    habitatge compartit) -> mostreig estratificat per quotes fixes (SLOTS), perquè
    amb n=24 un sorteig aleatori podria deixar districtes o tipus buits.
  * Superfície i preu -> distribució log-normal (asimètrica a la dreta, positiva:
    és el model habitual per a preus i mides d'habitatge). El preu surt de
    m2 x preu/m2 del districte x multiplicadors (estat, tipus) x soroll log-normal.
  * Estat i planta -> distribució categòrica amb pesos.
  * Característiques Sí/No -> Bernoulli amb probabilitat condicionada al tipus
    d'immoble, a l'operació, a la planta o a la zona.

Els preus/m2 de referència són aproximacions de l'ordre de magnitud del mercat
2023-2024 (no dades oficials).

Execució (des de p1/):  python tools/generate_houses.py
És idempotent: substitueix els ids > 26 i deixa intactes els 26 originals.
"""

import json
import math
import random
from pathlib import Path

SEED = 7
DATA = Path(__file__).resolve().parent.parent / "house_data_v2.json"
FIRST_NEW_ID = 27

# zona -> (municipi, preu venda EUR/m2, lloguer EUR/m2/mes)
ZONES = {
    "Ciutat Vella":              ("Barcelona", 4400, 22),
    "Eixample":                  ("Barcelona", 5200, 23),
    "Sants-Montjuïc":            ("Barcelona", 3900, 19),
    "Les Corts":                 ("Barcelona", 5500, 22),
    "Sarrià-Sant Gervasi":       ("Barcelona", 6000, 22),
    "Gràcia":                    ("Barcelona", 4900, 21),
    "Horta-Guinardó":            ("Barcelona", 3600, 17),
    "Nou Barris":                ("Barcelona", 2800, 15),
    "Sant Andreu":               ("Barcelona", 3700, 18),
    "Sant Martí":                ("Barcelona", 4700, 22),
    "L'Hospitalet de Llobregat": ("L'Hospitalet de Llobregat", 2700, 16),
    "Santa Coloma de Gramenet":  ("Santa Coloma de Gramenet", 2300, 14),
    "Esplugues de Llobregat":    ("Esplugues de Llobregat", 3600, 17),
}
CENTRAL = {"Ciutat Vella", "Eixample", "Gràcia"}

# Quotes: (zona, tipus d'immoble, operació, compartit)
SLOTS = [
    ("Les Corts", "flat", "rent", False),
    ("Les Corts", "flat", "sale", False),
    ("Les Corts", "chalet", "sale", False),
    ("Nou Barris", "flat", "rent", False),
    ("Nou Barris", "house", "sale", False),
    ("Gràcia", "flat", "rent", True),
    ("Gràcia", "duplex", "sale", False),
    ("Sant Andreu", "flat", "rent", False),
    ("Sant Martí", "flat", "rent", True),
    ("Sant Martí", "flat", "sale", False),
    ("Eixample", "flat", "rent", False),
    ("Eixample", "premises", "rent", False),
    ("Sarrià-Sant Gervasi", "chalet", "rent", False),
    ("Sarrià-Sant Gervasi", "flat", "sale", False),
    ("Horta-Guinardó", "house", "rent", False),
    ("Horta-Guinardó", "chalet", "sale", False),
    ("Ciutat Vella", "flat", "rent", True),
    ("Ciutat Vella", "flat", "rent", False),
    ("Sants-Montjuïc", "flat", "rent", True),
    ("Sants-Montjuïc", "flat", "sale", False),
    ("L'Hospitalet de Llobregat", "flat", "rent", False),
    ("L'Hospitalet de Llobregat", "flat", "sale", False),
    ("L'Hospitalet de Llobregat", "house", "sale", False),
    ("L'Hospitalet de Llobregat", "flat", "rent", False),
]

# Superfície: log-normal amb mediana (m2) i sigma per tipus d'immoble
SIZE = {"flat": (75, 0.30), "duplex": (130, 0.20), "house": (150, 0.25),
        "chalet": (220, 0.25), "premises": (90, 0.35)}
SHARED_SIZE = (95, 0.15)

CONDITIONS = (["new", "very good", "good", "renovated", "needs renovation"],
              [0.10, 0.20, 0.40, 0.15, 0.15])
CONDITION_FACTOR = {"new": 1.15, "very good": 1.08, "good": 1.0, "renovated": 1.05, "needs renovation": 0.80}
TYPE_FACTOR = {"flat": 1.0, "duplex": 1.05, "house": 0.85, "chalet": 0.90, "premises": 0.80}
PRICE_SIGMA = 0.10
ROOM_PRICE = (525, 0.12)  # habitació en pis compartit: mediana EUR/mes a un districte de 20 EUR/m2

FLOOR_WEIGHTS = [0.05, 0.17, 0.17, 0.15, 0.13, 0.11, 0.09, 0.07, 0.06]  # plantes 0..8 (pisos)

P_TERRACE = {"flat": 0.30, "duplex": 0.85, "house": 0.50, "chalet": 0.70, "premises": 0.0}
P_GARDEN = {"house": 0.50, "chalet": 0.90}
P_COMMERCIAL = {"flat": 0.08, "duplex": 0.10, "house": 0.05, "chalet": 0.0, "premises": 1.0}


def lognormal(rng, median, sigma):
    return rng.lognormvariate(math.log(median), sigma)


def yes(rng, p):
    return "Yes" if rng.random() < p else "No"


def make_house(rng, house_id, zone, ptype, operation, shared):
    city, sale_m2, rent_m2 = ZONES[zone]
    m2 = round(lognormal(rng, *(SHARED_SIZE if shared else SIZE[ptype])))
    m2 = max(35, min(m2, 400))
    condition = rng.choices(*CONDITIONS)[0]

    if ptype == "premises":
        bedrooms, bathrooms = 1, 1
    elif ptype in ("house", "chalet"):
        bedrooms = max(2, min(5, round(m2 / 40 + rng.gauss(0, 0.5))))
        bathrooms = 1 if m2 < 85 else 2 if m2 < 160 else 3
    else:
        bedrooms = max(1, min(5, round(m2 / 27 + rng.gauss(0, 0.4))))
        bathrooms = 1 if m2 < 85 else 2 if m2 < 160 else 3
    if shared:
        bedrooms = max(bedrooms, 3)

    factor = CONDITION_FACTOR[condition] * TYPE_FACTOR[ptype] * lognormal(rng, 1, PRICE_SIGMA)
    if operation == "sale":
        price = f"{round(m2 * sale_m2 * factor / 1000)}k"
    elif shared:
        price = str(round(lognormal(rng, ROOM_PRICE[0] * rent_m2 / 20, ROOM_PRICE[1]) / 25) * 25)
    else:
        price = str(round(m2 * rent_m2 * factor / 25) * 25)

    if ptype == "flat":
        floor = rng.choices(range(9), FLOOR_WEIGHTS)[0]
    elif ptype == "duplex":
        floor = rng.randint(3, 7)
    else:
        floor = 0
    has_lift_building = ptype in ("flat", "duplex")
    elevator = yes(rng, 0.9 if floor >= 3 else 0.5) if has_lift_building and floor > 0 else "No"

    if ptype in ("house", "chalet"):
        p_parking = 0.75
    elif ptype == "premises":
        p_parking = 0.0
    else:
        p_parking = 0.10 if zone in CENTRAL else 0.30

    if ptype == "premises":
        furnished = "No"
    elif shared:
        furnished = "Yes"
    else:
        furnished = yes(rng, 0.65 if operation == "rent" else 0.15)

    if operation == "sale":
        pets = "Yes"
    else:
        pets = yes(rng, 0.20 if shared else 0.45)

    return {
        "id": house_id,
        "type": operation,
        "property_type": ptype,
        "condition": condition,
        "shared": "Yes" if shared else "No",
        "bedrooms": str(bedrooms),
        "bathrooms": str(bathrooms),
        "price": price,
        "square_meters": str(m2),
        "floor": str(floor),
        "elevator": elevator,
        "terrace": yes(rng, P_TERRACE[ptype]),
        "garden": yes(rng, P_GARDEN.get(ptype, 0.0)),
        "parking": yes(rng, p_parking),
        "furnished": furnished,
        "pets": pets,
        "commercial_use": yes(rng, 0.0 if shared else P_COMMERCIAL[ptype]),  # una habitació no té ús comercial
        "location": zone,
        "city": city,
    }


def main():
    rng = random.Random(SEED)
    data = json.loads(DATA.read_text(encoding="utf-8"))
    original = [h for h in data["houses"] if h["id"] < FIRST_NEW_ID]
    new = [make_house(rng, FIRST_NEW_ID + i, *slot) for i, slot in enumerate(SLOTS)]
    data["houses"] = original + new
    DATA.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for h in new:
        print(h["id"], h["type"], h["property_type"], h["condition"], h["shared"], h["bedrooms"], h["bathrooms"],
              h["price"], h["square_meters"], h["floor"], h["elevator"], h["terrace"], h["garden"], h["parking"],
              h["furnished"], h["pets"], h["commercial_use"], h["location"], sep=" | ")


if __name__ == "__main__":
    main()
