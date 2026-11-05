"""Proves del bloc 2: noves característiques de l'immoble
(tipus de propietat, estat, pis compartit, moblat, aparcament, jardí, mascotes),
ubicació per districtes de Barcelona i les 24 vivendes noves (ids 27-50).

Inclou també el comiat després dels resultats (proposta acceptada).

Execució:  python -m recomanador.tests.test_bloc2
"""

import re

from recomanador.data_loader import load_data
from recomanador.tests.common import answers_for, conversation, run_case, run_suite

NEW_FIELDS = ["property_type", "condition", "shared", "furnished", "parking", "garden", "pets", "city"]
RENT_IDS = [1, 3, 5, 7, 9, 11, 14, 17, 18, 19, 22, 27, 30, 32, 34, 35, 37, 38, 39, 41, 43, 44, 45, 47, 50]
SHARED_IDS = [32, 35, 43, 45]

CASES = [
    ("tipus de propietat: oficina", answers_for(property_type="office"), [5, 10, 25]),
    ("tipus de propietat: xalet", answers_for(property_type="chalet"), [22, 29, 39, 42]),
    ("estat: nou i compra", answers_for(type="sale", condition="new"), [8, 12, 21, 42, 46, 49]),
    ("compartir: No exclou les habitacions", answers_for(type="rent", shared="No"),
     [i for i in RENT_IDS if i not in SHARED_IDS]),
    ("compartir: Yes no filtra", answers_for(type="rent", shared="Yes"), RENT_IDS),
    ("aparcament obligatori en lloguer", answers_for(type="rent", parking="Yes"), [3, 7, 22, 34, 39, 41]),
    ("moblat obligatori en compra", answers_for(type="sale", furnished="Yes"), [24, 29, 40]),
    ("mascotes en lloguer", answers_for(type="rent", pets="Yes"), [1, 7, 9, 14, 19, 22, 27, 38, 41, 47]),
    ("jardí amb tipus 'any'", answers_for(garden="Yes"), [22, 29, 31, 39, 41, 42, 49]),
    ("jardí amb tipus 'house'", answers_for(property_type="house", garden="Yes"), [31, 41, 49]),
    ("districte: Les Corts", answers_for(location="Les Corts"), [27, 28, 29]),
    ("districte amb accent: Gràcia en lloguer", answers_for(type="rent", location="Gràcia"), [18, 32]),
    ("ciutat sencera: Barcelona + xalet", answers_for(location="Barcelona", property_type="chalet"),
     [22, 29, 39, 42]),
]


def check_data():
    errors = []
    houses = load_data()["houses"]
    if [h["id"] for h in houses] != list(range(1, 51)):
        errors.append("els ids no són 1..50")
    for house in houses:
        missing = [f for f in NEW_FIELDS if f not in house]
        if missing:
            errors.append(f"habitatge {house['id']} sense {missing}")
        if house["condition"] == "shared":
            errors.append(f"habitatge {house['id']} encara té 'shared' com a estat")
        if house["shared"] == "Yes" and house["type"] != "rent":
            errors.append(f"habitatge {house['id']} compartit però no és de lloguer")
    districts = {h["location"] for h in houses if h["city"] == "Barcelona"}
    if len(districts) != 10:
        errors.append(f"Barcelona hauria de tenir 10 districtes, en té {len(districts)}")
    return errors


def asked(text):
    """Text de la conversa abans dels resultats (només preguntes, ajudes i reaccions)."""
    return conversation(text)


def last_progress(text):
    return re.findall(r"\[(\d+)/(\d+)\]", text)[-1]


def check_questions():
    errors = []
    # (preferències, total de preguntes, es pregunta compartir?, mascotes?, jardí?, habitacions?, planta?)
    # Habitacions no s'esmenten per a oficines/locals ni la planta per a cases/xalets (propostes acceptades).
    expectations = [
        ({}, 17, True, True, True, True, True),
        ({"type": "rent", "property_type": "flat"}, 16, True, True, False, True, True),
        ({"type": "sale", "property_type": "flat"}, 14, False, False, False, True, True),
        ({"type": "rent", "property_type": "office"}, 14, False, True, False, False, True),
        ({"type": "sale", "property_type": "premises"}, 13, False, False, False, False, True),
        ({"type": "sale", "property_type": "house"}, 14, False, False, True, True, False),
        ({"type": "rent", "property_type": "chalet"}, 16, True, True, True, True, False),
    ]
    for prefs, total, shared, pets, garden, bedrooms, floor in expectations:
        text = asked(run_case(answers_for(**prefs))[2].text())
        if last_progress(text) != (str(total), str(total)):
            errors.append(f"{prefs}: s'esperaven {total} preguntes, progrés final {last_progress(text)}")
        for label, expected, question in [("compartir", shared, "sharing the home"),
                                          ("mascotes", pets, "live with pets"),
                                          ("jardí", garden, "want a garden"),
                                          ("habitacions", bedrooms, "How many bedrooms"),
                                          ("planta", floor, "lowest floor")]:
            if (question in text) != expected:
                errors.append(f"{prefs}: pregunta de {label} {'absent' if expected else 'present'}")
    for q in ["kind of property", "condition", "furnished", "parking space"]:
        if q not in text:
            errors.append(f"no es pregunta '{q}'")
    return errors


def check_location_options():
    errors = []
    text = run_case(["any", "any", "help", "quit", "yes"])[2].text()
    if "Barcelona (whole city), or one of its districts:" not in text or "Nearby towns:" not in text:
        errors.append("les opcions d'ubicació no s'agrupen per ciutat/districtes")
    _, _, io = run_case(answers_for(location="Les Corts", property_type="chalet") + ["all"])  # fitxes: 'all'
    if "in Les Corts (Barcelona)" not in io.text():  # fitxa en llenguatge natural (iteració 3)
        errors.append("els resultats no mostren 'districte (ciutat)'")
    return errors


def check_results_and_goodbye():
    errors = []
    _, _, io = run_case(answers_for(location="Sarrià-Sant Gervasi", property_type="chalet") + ["all"])
    text = io.text()
    # fitxa en llenguatge natural (iteració 3): tipus, estat, no compartit, jardí, aparcament, moblat, mascotes
    for label in ["Chalet for rent in Sarrià-Sant Gervasi (Barcelona)", "in very good condition",
                  "It comes with a garden, a parking space and furniture.", "Pets are welcome."]:
        if label not in text:
            errors.append(f"els resultats no mostren '{label}'")
    goodbye = load_data()["end_message"][0]  # proves deterministes: primera formulació
    if not text.rstrip().endswith(goodbye):
        errors.append("el comiat no surt al final en una conversa completa")

    _, _, io = run_case(["rent", "quit", "yes"])
    text = io.text()
    # iteració 3: 'quit' s'acomiada sense mostrar vivendes
    if not text.rstrip().endswith(goodbye) or " · #" in text:
        errors.append("amb 'quit' s'ha d'acomiadar sense mostrar vivendes")
    return errors


CHECKS = [
    ("dades: 50 vivendes, camps nous, 'shared' fora de l'estat, 10 districtes", check_data),
    ("preguntes noves i condicionals (compartir, mascotes, jardí, habitacions, planta)", check_questions),
    ("opcions d'ubicació agrupades i 'districte (ciutat)' als resultats", check_location_options),
    ("resultats amb camps nous i comiat al final", check_results_and_goodbye),
]


def main():
    return run_suite("Bloc 2", CASES, CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
