"""Proves del bloc 4 (1a part): reacció davant d'anomalies i preguntes de clarificació.

Cobreix cada situació que el gestor del diàleg distingeix: resposta no entesa (amb ajuda
progressiva), resposta buida, ambigüitat, error tipogràfic, confirmació implícita,
valors fora de rang o poc plausibles, diversos números, pressupost amb tipus 'any'
i confirmació de sortida.

Execució:  python -m recomanador.tests.test_bloc4
"""

from recomanador.numeric import Range
from recomanador.tests.common import answers_for, run_case, run_suite

CASES = [
    ("tipus 'any': '300k' és de compra i es demana el lloguer",
     answers_for(type="both", price="300k", location="Barcelona", then={"price": ["1.200"]}),
     [17, 18, 19, 23, 24, 25, 26, 28, 32, 34, 35, 36, 43, 45, 46]),
    ("tipus 'any': '800' es pregunta si és lloguer o compra",
     answers_for(type="any", price="800", location="Les Corts", then={"price": ["buy", "any"]}), [27, 28]),
    ("fora de rang mantingut: no hi ha resultats", answers_for(type="sale", price="50k", then={"price": ["no", "no"]}), []),
]


def text_of(answers):
    return run_case(answers)[2].text()


def missing(text, expected):
    return [f"falta: {e!r}" for e in expected if e not in text]


def check_not_understood():
    text = text_of(answers_for(type="rent", retries={"type": ["maybe", "", "perhaps"]}))
    return missing(text, [
        "Sorry, I didn't quite get that. I'm expecting 'buy' or 'rent'.",       # 1r error: què s'espera
        "It looks like you didn't type anything. I'm expecting 'buy' or 'rent'.",  # resposta buida
        "Let me explain again how to answer this question:",                    # 3r: ajuda completa...
        "If you'd rather not answer, type 'any' and we'll move on.",            # ...i opció de saltar-la
    ])


def check_ambiguity_and_typos():
    errors = []
    _, state, io = run_case(answers_for(type="rent", retries={"type": ["buy or rent"]}))
    errors += missing(io.text(), ["Sorry, do you mean renting or buying?"])
    if state.preferences["type"] != "rent":
        errors.append(f"l'aclariment no resol el tipus: {state.preferences['type']}")

    _, state, io = run_case(answers_for(location="Gràcia", retries={"location": ["Eixampel", "no"]}))
    errors += missing(io.text(), ["Did you mean Eixample? (Yes / No)", "No problem, let's try again:"])
    if state.preferences["location"] != ["Gràcia"]:
        errors.append("en dir 'no' a 'Did you mean...?' no es torna a preguntar")

    _, state, io = run_case(answers_for(location="Eixampel", then={"location": ["maybe", "yes"]}))
    errors += missing(io.text(), ["Please answer yes or no."])
    if state.preferences["location"] != ["Eixample"]:
        errors.append("una confirmació no entesa no es torna a demanar")
    return errors


def check_implicit_confirmation():
    text = text_of(answers_for(type="sale", price="between 200k and 300k", location="near the beach",
                               property_type="flat", bedrooms="3", floor="2"))
    errors = missing(text, ["Got it: between 200,000 and 300,000 euros.", "Got it: Ciutat Vella and Sant Martí.",
                            "Got it: at least 3 bedrooms.", "Got it: floor 2 or higher."])
    if "Got it: flat" in text:
        errors.append("es repeteix una opció escrita literalment ('flat')")
    errors += missing(text_of(answers_for(location="BCN")), ["Got it: all of Barcelona."])
    return errors


def check_numeric_anomalies():
    errors = []
    _, state, io = run_case(answers_for(bedrooms="3", retries={"bedrooms": ["10", "yes"]}))
    errors += missing(io.text(), ["None of our homes matches at least 10 bedrooms: ours have between 1 and 5 bedrooms."])
    if state.preferences["bedrooms"] != Range(3, None):
        errors.append("en voler canviar un valor fora de rang no es torna a preguntar")

    _, state, io = run_case(answers_for(type="sale", price="50k", then={"price": ["no", "no"]}))
    errors += missing(io.text(), ["OK, I'll keep up to 50,000 euros."])

    _, state, io = run_case(answers_for(type="rent", price="1200", retries={"price": ["300k", "no"]}))
    errors += missing(io.text(), ["Up to 300,000 euros a month looks more like a purchase price than a monthly rent."])
    if state.preferences["price"] != Range(None, 1200):
        errors.append("el lloguer poc plausible no es corregeix")

    text = text_of(answers_for(type="rent", price="1200", retries={"price": ["1200 1500"]}))
    errors += missing(text, ["I found several numbers (1,200, 1,500). Please give just one, or a range such as "
                             "'between 1,200 and 1,500'."])
    return errors


def check_budget_with_any_type():
    _, state, io = run_case(answers_for(type="any", price="800", then={"price": ["buy", "1.200"]}))
    errors = missing(io.text(), ["Is that a monthly rent or a purchase price? (rent / buy)",
                                 "Got it: up to 800,000 euros (buying).",
                                 "And if you rented, what would be your maximum monthly rent?",
                                 "Got it: up to 1,200 euros a month."])
    if state.preferences["price"] != {"sale": Range(None, 800000), "rent": Range(None, 1200)}:
        errors.append(f"pressupost amb tipus 'any' mal desat: {state.preferences['price']}")
    return errors


def check_exit_confirmation():
    errors = []
    _, state, io = run_case(answers_for(type="rent", retries={"type": ["quit", "no"]}))
    errors += missing(io.text(), ["Are you sure you want to leave?", "OK, let's continue."])
    if state.exited or state.preferences.get("type") != "rent":
        errors.append("en dir 'no' a la sortida la conversa no continua")
    _, state, _ = run_case(["rent", "quit", "quit"])  # "quit" a la confirmació = sí
    if not state.exited:
        errors.append("'quit' a la confirmació de sortida no surt")
    _, state, _ = run_case(["rent", "q", "yes"])
    if not state.exited:
        errors.append("'q' + 'yes' no surt")
    return errors


CHECKS = [
    ("no entès: què s'espera, resposta buida, ajuda completa i opció de saltar", check_not_understood),
    ("ambigüitat ('buy or rent') i errors tipogràfics ('Did you mean...?')", check_ambiguity_and_typos),
    ("confirmació implícita ('Got it: ...') només quan cal", check_implicit_confirmation),
    ("números: fora de rang, lloguer poc plausible, diversos números", check_numeric_anomalies),
    ("pressupost amb tipus 'any' (lloguer o compra + segon pressupost)", check_budget_with_any_type),
    ("confirmació de sortida", check_exit_confirmation),
]


def main():
    return run_suite("Bloc 4 (reacció davant d'anomalies)", CASES, CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
