"""Proves del bloc 3 (2a part): diners, rangs i modificadors, sumes d'habitacions amb confirmació,
exclusions ("except", "but", "menos") i selecció múltiple en tipus d'immoble i estat.

Execució:  python -m recomanador.tests.test_bloc3b
"""

from recomanador import nlu, numeric
from recomanador.data_loader import load_data
from recomanador.numeric import Range
from recomanador.recommender import initialize_available_options
from recomanador.tests.common import answers_for, run_case, run_suite

N = None
# (pregunta, tipus d'operació, resposta, rang esperat, quantitats sumades)
NUMERIC = [
    # diners: formats
    ("price", "rent", "10k", Range(N, 10000), ()), ("price", "rent", "10.000", Range(N, 10000), ()),
    ("price", "rent", "10000", Range(N, 10000), ()), ("price", "rent", "1.300", Range(N, 1300), ()),
    ("price", "rent", "1,300", Range(N, 1300), ()), ("price", "rent", "1.5k", Range(N, 1500), ()),
    ("price", "rent", "1,5k", Range(N, 1500), ()), ("price", "rent", "1300€", Range(N, 1300), ()),
    ("price", "rent", "€1.300", Range(N, 1300), ()), ("price", "rent", "1.300,50", Range(N, 1300.5), ()),
    ("price", "rent", "1.200 euros al mes", Range(N, 1200), ()),
    ("price", "rent", "thirteen hundred", Range(N, 1300), ()),
    ("price", "rent", "one thousand three hundred", Range(N, 1300), ()),
    ("price", "rent", "a thousand three hundred", Range(N, 1300), ()),
    ("price", "rent", "dos mil quinientos", Range(N, 2500), ()), ("price", "rent", "mil", Range(N, 1000), ()),
    ("price", "sale", "250", Range(N, 250000), ()), ("price", "sale", "250k", Range(N, 250000), ()),
    ("price", "sale", "250.000", Range(N, 250000), ()), ("price", "sale", "250 thousand", Range(N, 250000), ()),
    ("price", "sale", "250 mil", Range(N, 250000), ()), ("price", "sale", "1.2m", Range(N, 1200000), ()),
    ("price", "sale", "un millón", Range(N, 1000000), ()), ("price", "sale", "1,2 millones", Range(N, 1200000), ()),
    ("price", "sale", "un presupuesto de 300 mil", Range(N, 300000), ()),
    ("price", "sale", "I can pay up to 280.000 euros", Range(N, 280000), ()),
    # rangs i modificadors
    ("price", "sale", "between 200k and 300k", Range(200000, 300000), ()),
    ("price", "sale", "between 200 and 300k", Range(200000, 300000), ()),
    ("price", "sale", "200k-300k", Range(200000, 300000), ()),
    ("price", "sale", "from 200 to 300k", Range(200000, 300000), ()),
    ("price", "sale", "around 250k", Range(225000, 275000), ()),
    ("price", "sale", "at least 200k", Range(200000, N), ()),
    ("price", "sale", "300k max", Range(N, 300000), ()),
    ("bedrooms", N, "3", Range(3, N), ()), ("bedrooms", N, "three", Range(3, N), ()),
    ("bedrooms", N, "tres", Range(3, N), ()), ("bedrooms", N, "more than 2", Range(3, N), ()),
    ("bedrooms", N, "less than 3", Range(N, 2), ()), ("bedrooms", N, "between 2 and 3", Range(2, 3), ()),
    ("bedrooms", N, "2-3", Range(2, 3), ()), ("bedrooms", N, "2 or 3", Range(2, 3), ()),
    ("bedrooms", N, "de 2 a 3", Range(2, 3), ()), ("bedrooms", N, "around 3", Range(2, 4), ()),
    ("bedrooms", N, "exactly 2", Range(2, 2), ()), ("bedrooms", N, "3+", Range(3, N), ()),
    ("bedrooms", N, "3 or more", Range(3, N), ()), ("bedrooms", N, "at least 2 and at most 4", Range(2, 4), ()),
    ("square_meters", N, "80m2", Range(80, N), ()), ("square_meters", N, "80 m²", Range(80, N), ()),
    ("square_meters", N, "around 80", Range(68, 92), ()),
    ("square_meters", N, "eighty square meters", Range(80, N), ()),
    ("floor", N, "ground floor", Range(0, N), ()), ("floor", N, "planta baja", Range(0, N), ()),
    ("floor", N, "3rd", Range(3, N), ()), ("floor", N, "segundo", Range(2, N), ()),
    ("floor", N, "third floor or higher", Range(3, N), ()), ("floor", N, "not the ground floor", Range(1, N), ()),
    # sumes d'habitacions i banys (cal confirmar-les)
    ("bedrooms", N, "1 habitación grande y 1 mediana", Range(2, N), (1, 1)),
    ("bedrooms", N, "1 big bedroom and 1 small one", Range(2, N), (1, 1)),
    ("bedrooms", N, "a big bedroom and a small one", Range(2, N), (1, 1)),
    ("bedrooms", N, "1 big and 1 small bedroom", Range(2, N), (1, 1)),
    ("bedrooms", N, "2 doubles and 1 single", Range(3, N), (2, 1)),
    ("bedrooms", N, "dos dobles y una individual", Range(3, N), (2, 1)),
    ("bedrooms", N, "un dormitorio grande y uno pequeño", Range(2, N), (1, 1)),
    ("bedrooms", N, "I need a big one and another small one", Range(2, N), (1, 1)),
    ("bedrooms", N, "2+1", Range(3, N), (2, 1)),
    ("bathrooms", N, "1 full bathroom and 1 toilet", Range(2, N), (1, 1)),
    ("bathrooms", N, "un baño y un aseo", Range(2, N), (1, 1)),
    # quantitats que no compten
    ("bedrooms", N, "a house with 3 bedrooms", Range(3, N), ()),
    ("bedrooms", N, "3 bedrooms and 2 bathrooms", Range(3, N), ()),
    ("bathrooms", N, "3 bedrooms and 2 bathrooms", Range(2, N), ()),
    ("bedrooms", N, "not 3", N, ()), ("bedrooms", N, "hello", N, ()),
]

# (pregunta, resposta, valor esperat)
INTERPRET = [
    ("location", "Barcelona but not Nou Barris",
     ["Ciutat Vella", "Eixample", "Gràcia", "Horta-Guinardó", "Les Corts", "Sant Andreu", "Sant Martí",
      "Sants-Montjuïc", "Sarrià-Sant Gervasi"]),
    ("location", "city centre except Ciutat Vella", ["Eixample"]),
    ("location", "outskirts except Hospitalet", ["Esplugues de Llobregat", "Santa Coloma de Gramenet"]),
    ("location", "Gràcia, but cheap", ["Gràcia"]),
    ("location", "Gràcia except Gràcia", None),
    ("property_type", "anything but a flat", ["chalet", "duplex", "house", "office", "premises"]),
    ("property_type", "flat or duplex", ["duplex", "flat"]),
    ("property_type", "piso o dúplex", ["duplex", "flat"]),
    ("condition", "new or very good", ["new", "very good"]),
    ("condition", "anything except needs renovation", ["good", "new", "renovated", "very good"]),
    ("type", "buy or rent", None),
]

ALL_BUT_NOU_BARRIS = sorted({h["location"] for h in load_data()["houses"]} - {"Nou Barris"})

CASES = [
    ("compra: pis a Barcelona entre 200k i 300k",
     answers_for(type="sale", price="between 200k and 300k", location="Barcelona", property_type="flat"),
     [23, 24, 26, 28, 36, 46]),
    ("compra: pressupost '250' s'entén en milers", answers_for(type="sale", price="250", location="Santa Coloma"),
     [2, 4, 6]),
    ("lloguer: màxim '1.200' a Gràcia o l'Eixample",
     answers_for(type="rent", price="1.200", location="Gràcia o Eixample"), [18, 32]),
    ("lloguer: 'around 800' (marge del 10%)", answers_for(type="rent", price="around 800"), [3, 18]),
    ("lloguer: menys de 1000 i exactament 2 banys a BCN",
     answers_for(type="rent", price="less than 1000", location="BCN", bathrooms="exactly 2"), [32, 43, 45]),
    ("compra: m2 entre 70 i 90 a Barcelona",
     answers_for(type="sale", location="Barcelona", square_meters="between 70 and 90 m2"), [20, 26, 36]),
    ("planta: 'second floor or higher' a Sants", answers_for(location="Sants", floor="second floor or higher"),
     [25, 46]),
    ("suma d'habitacions confirmada", answers_for(type="sale", location="Sant Martí",
                                                  bedrooms="1 big bedroom and 1 small one", then={"bedrooms": ["yes"]}),
     [20, 36]),
    ("suma d'habitacions rebutjada i resposta nova",
     answers_for(location="Les Corts", bedrooms="4", retries={"bedrooms": ["2 doubles and 1 single", "no"]}),
     [29]),
    ("exclusió: Barcelona però no Nou Barris, casa",
     answers_for(location="Barcelona but not Nou Barris", property_type="house"), [41]),
    ("selecció múltiple: pis o dúplex a Gràcia", answers_for(location="Gràcia", property_type="flat or duplex"),
     [18, 32, 33]),
    ("exclusió en l'estat: Santa Coloma sense 'a reformar'",
     answers_for(location="Santa Coloma", condition="anything except needs renovation"), [1, 2, 3, 5, 7]),
]


def check_numeric():
    errors = []
    for key, house_type, answer, expected_range, expected_parts in NUMERIC:
        result = numeric.parse(answer, key, house_type)
        got = None if result is None else (result.range, tuple(result.parts))
        expected = None if expected_range is None else (expected_range, expected_parts)
        if got != expected:
            errors.append(f"[{key}] {answer!r} -> {got}, esperat {expected}")
    return errors


def check_interpret():
    data = load_data()
    options = {}
    initialize_available_options(data, options)
    errors = []
    for key, answer, expected in INTERPRET:
        vocabulary = nlu.build_vocabulary(key, sorted(options[key]), data["houses"])
        got = nlu.interpret(vocabulary, answer, multiple=key != "type")
        if got != expected:
            errors.append(f"[{key}] {answer!r} -> {got}, esperat {expected}")
    return errors


def check_dialogue():
    errors = []
    _, state, io = run_case(answers_for(location="anywhere except Nou Barris"))
    if state.preferences.get("location") != ALL_BUT_NOU_BARRIS:
        errors.append(f"'anywhere except Nou Barris' -> {state.preferences.get('location')} (no s'ha pres com a exclusió)")

    _, _, io = run_case(answers_for(bedrooms="1 habitación grande y 1 mediana", then={"bedrooms": ["sí"]}))
    if "So that's 2 bedrooms in total, is that right?" not in io.text():
        errors.append("no es demana confirmació de la suma d'habitacions")

    _, _, io = run_case(answers_for(bedrooms="3", retries={"bedrooms": ["2 doubles and 1 single", "no"]}))
    text = io.text()
    if "let's try again" not in text or "So that's 3 bedrooms in total" not in text:
        errors.append("en rebutjar la suma no es torna a preguntar")

    _, _, io = run_case(answers_for(type="rent", bedrooms="3"))
    if "in total" in io.text():
        errors.append("es demana confirmació sense que hi hagi suma")

    _, state, _ = run_case(answers_for(type="sale", price="around 250k", floor="ground floor"))
    if state.preferences["price"] != Range(225000, 275000) or state.preferences["floor"] != Range(0, None):
        errors.append(f"preferències numèriques mal desades: {state.preferences}")
    return errors


def check_prompts():
    text = run_case(answers_for(type="sale", retries={k: ["help"] for k in
                                                     ("price", "bedrooms", "square_meters", "floor")}))[2].text()
    expected = ["Type your maximum budget", "Type the minimum number of bedrooms", "'2 doubles and 1 single'",
                "Type the minimum size in square metres", "'2nd' or 'second'"]
    return [f"falta a l'ajuda: {e!r}" for e in expected if e not in text]


CHECKS = [
    (f"números: {len(NUMERIC)} respostes (formats, rangs, modificadors, sumes)", check_numeric),
    (f"exclusions i selecció múltiple: {len(INTERPRET)} respostes", check_interpret),
    ("diàleg: exclusió amb 'any', confirmació de sumes, rangs desats", check_dialogue),
    ("textos d'ajuda numèrics actualitzats", check_prompts),
]


def main():
    return run_suite("Bloc 3b (diners, rangs, sumes, exclusions, selecció múltiple)", CASES, CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
