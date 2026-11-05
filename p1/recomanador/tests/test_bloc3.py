"""Proves del bloc 3 (primera part): preprocessament, sinònims i zones geogràfiques.

Execució:  python -m recomanador.tests.test_bloc3
"""

from recomanador import nlu, numeric
from recomanador.data_loader import load_data
from recomanador.recommender import initialize_available_options
from recomanador.tests.common import answers_for, run_case, run_suite

BCN = ["Ciutat Vella", "Eixample", "Gràcia", "Horta-Guinardó", "Les Corts", "Nou Barris", "Sant Andreu",
       "Sant Martí", "Sants-Montjuïc", "Sarrià-Sant Gervasi"]
TOWNS = ["Esplugues de Llobregat", "L'Hospitalet de Llobregat", "Santa Coloma de Gramenet"]

NORMALIZE = [
    ("  ÀLQUILER!! ", "alquiler"),
    ("L’Hospitalet", "l hospitalet"),
    ("Sants-Montjuïc", "sants montjuic"),
    ("I don't care, really", "i do not care | really"),
    ("Sta. Coloma", "sta coloma"),
    ("Col·legi", "collegi"),
]

# (pregunta, resposta, valor esperat; None = no s'entén o és ambigu)
INTERPRET = [
    # majúscules, accents, símbols
    ("type", "BUY", "sale"), ("type", "  Rent!!! ", "rent"), ("location", "L’HOSPITALET", [TOWNS[1]]),
    ("location", "Gracia", ["Gràcia"]), ("location", "sants montjuic", ["Sants-Montjuïc"]),
    # sinònims (anglès, castellà, català) i frases
    ("type", "I want to rent", "rent"), ("type", "Alquiler", "rent"), ("type", "comprar", "sale"),
    ("type", "lloguer", "rent"), ("type", "to let", "rent"),
    ("property_type", "Apartment", "flat"), ("property_type", "PISO", "flat"), ("property_type", "a villa", "chalet"),
    ("property_type", "detached house", "chalet"), ("property_type", "local comercial", "premises"),
    ("property_type", "Ático dúplex", "duplex"), ("property_type", "shop", "premises"),
    ("condition", "Like new", "very good"), ("condition", "reformado", "renovated"),
    ("condition", "needs work", "needs renovation"), ("condition", "Brand-new", "new"),
    ("terrace", "YES", "Yes"), ("terrace", "sí", "Yes"), ("terrace", "Si, claro", "Yes"), ("terrace", "y", "Yes"),
    ("terrace", "of course", "Yes"), ("terrace", "no problem", "Yes"), ("terrace", "nope", "No"),
    ("terrace", "I don't need it", "No"), ("terrace", "not really", "No"), ("terrace", "no, thanks", "No"),
    # negació i ambigüitat
    ("type", "I don't want to buy, I want to rent", "rent"), ("type", "No, rent please", "rent"),
    ("type", "buy or rent", None), ("property_type", "I don't want a flat, a house", "house"),
    ("condition", "not renovated", None), ("terrace", "yes no", None), ("terrace", "no, I need it", None),
    # (des de la 2a part del bloc 3, "anywhere except X" és una exclusió: vegeu test_bloc3b)
    ("location", "not nou barris", None),
    # errors tipogràfics
    ("property_type", "apartmnet", "flat"), ("condition", "renovatd", "renovated"),
    ("location", "Barcleona", BCN), ("location", "Eixampel", ["Eixample"]), ("location", "Santacoloma", [TOWNS[2]]),
    ("property_type", "horse", None), ("type", "maybe", None), ("location", "Madrid", None),
    # llocs: formes alternatives, barris, ciutat i zones
    ("location", "BCN", BCN), ("location", "barcelona", BCN), ("location", "Poblenou", ["Sant Martí"]),
    ("location", "Hospitalet", [TOWNS[1]]), ("location", "Pedralbes", ["Les Corts"]),
    ("location", "gràcia o eixample", ["Eixample", "Gràcia"]),
    ("location", "Eixample, Barcelona", ["Eixample"]),
    ("location", "near the beach", ["Ciutat Vella", "Sant Martí"]),
    ("location", "near the beach in Sant Martí", ["Sant Martí"]),
    ("location", "city centre", ["Ciutat Vella", "Eixample"]), ("location", "centro", ["Ciutat Vella", "Eixample"]),
    ("location", "zona alta", ["Les Corts", "Sarrià-Sant Gervasi"]),
    ("location", "in the north", ["Horta-Guinardó", "Nou Barris", "Sant Andreu"]),
    ("location", "outskirts of Barcelona", TOWNS), ("location", "alrededores de barcelona", TOWNS),
    ("location", "west of Barcelona", [TOWNS[0], TOWNS[1]]),
    ("location", "Besòs", ["Nou Barris", "Sant Andreu", "Sant Martí", TOWNS[2]]),
]

SPECIAL = [  # (resposta, és 'any'?, és sortida?)
    ("ANY", True, False), ("Doesn't matter", True, False), ("I don't care", True, False),
    ("whatever", True, False), ("me da igual", True, False), ("no preference", True, False),
    ("I don't have any pets", False, False),
    ("QUIT", False, True), (" Quit. ", False, True), ("Exit!", False, True), ("quite", False, False),
]

CASES = [
    ("compra a prop de la platja", answers_for(type="Buy", location="near the beach"), [20, 24, 36]),
    ("lloguer de pis als voltants", answers_for(type="ALQUILER", location="outskirts of Barcelona",
                                                property_type="apartment"), [1, 3, 9, 11, 14, 47, 50]),
    ("pis a Gràcia o l'Eixample", answers_for(location="Gracia o Eixample", property_type="PISO"),
     [18, 21, 32, 37]),
    ("xalet a la zona alta", answers_for(location="zona alta", property_type="villa"), [22, 29, 39]),
    ("lloguer a BCN, sense compartir, amb mascotes",
     answers_for(type="rent", location="BCN", shared="no thanks", pets="sí"), [19, 22, 27, 38, 41]),
    ("compra en molt bon estat", answers_for(type="for sale", condition="Like new"), [13, 20, 31, 33, 40, 48]),
    # des del bloc 4 un error tipogràfic es confirma ("Did you mean Eixample?")
    ("districte amb error tipogràfic", answers_for(location="Eixampel", then={"location": ["yes"]}), [21, 37, 38]),
    ("negació: no vull pis, una casa", answers_for(property_type="I don't want a flat, a house"),
     [2, 31, 41, 49]),
    ("resposta ambigua: es demana aclariment", answers_for(type="rent", location="Les Corts",
                                                        retries={"type": ["buy or rent"]}), [27]),
]


def vocabularies():
    data = load_data()
    options = {}
    initialize_available_options(data, options)
    return {key: nlu.build_vocabulary(key, sorted(options[key]), data["houses"])
            for key in ["type", "property_type", "condition", "terrace", "location"]}


def check_normalize():
    return [f"normalize({text!r}) = {nlu.normalize(text)!r}, esperat {expected!r}"
            for text, expected in NORMALIZE if nlu.normalize(text) != expected]


def check_interpret():
    errors = []
    vocab = vocabularies()
    for key, answer, expected in INTERPRET:
        got = nlu.interpret(vocab[key], answer, multiple=(key == "location"))
        if got != expected:
            errors.append(f"[{key}] {answer!r} -> {got}, esperat {expected}")
    return errors


def check_special():
    errors = []
    for answer, is_any, is_exit in SPECIAL:
        if nlu.is_any(answer) != is_any or nlu.is_exit(answer) != is_exit:
            errors.append(f"{answer!r}: any={nlu.is_any(answer)} exit={nlu.is_exit(answer)}")
    if numeric.parse("250K", "price", "sale").range != numeric.Range(None, 250000):
        errors.append("'250K' no s'entén com a 250.000")
    return errors


def check_prompts():
    errors = []
    text = run_case(["any", "any", "help", "quit", "yes"])[2].text()
    if "type exactly as written" in text:
        errors.append("encara es demana escriure les opcions exactament")
    if "own words" not in text:
        errors.append("les instruccions no diuen que es pot respondre amb paraules pròpies")
    if "Areas: city centre / uptown / seaside" not in text:
        errors.append("la pregunta d'ubicació no mostra les zones")
    return errors


CHECKS = [
    ("normalització del text", check_normalize),
    (f"interpretació: {len(INTERPRET)} respostes (sinònims, negació, errors, zones)", check_interpret),
    ("'any', sortida i majúscules en números", check_special),
    ("textos: sense 'exactly as written', paraules pròpies, zones", check_prompts),
]


def main():
    return run_suite("Bloc 3 (preprocessament, sinònims, zones)", CASES, CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
