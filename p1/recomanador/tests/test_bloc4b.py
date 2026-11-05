"""Proves del bloc 4 (2a part): naturalitat i fluïdesa.

Variació aleatòria de formulacions (reproduïble amb llavor, sense repetir la darrera),
reacció a cada resposta, comentaris propis de l'agent, resum final i presentació dels resultats.

Execució:  python -m recomanador.tests.test_bloc4b
"""

import random

from recomanador import nlg
from recomanador.data_loader import load_data
from recomanador.tests.common import answers_for, conversation, run_case, run_suite

ALL_ANY = answers_for()  # totes les preguntes amb 'any'
# Una cerca que acaba amb resultats (la 18): així cap resposta dispara l'avís de 0 coincidències (bloc 5).
FULL = answers_for(type="rent", price="1.200", location="Gràcia", property_type="flat", shared="No",
                   bedrooms="1", floor="2", terrace="Yes", furnished="Yes")


def seeded(seed):
    return nlg.VariedPicker(random.Random(seed))


def check_randomness():
    errors = []
    a = run_case(FULL, picker=seeded(1))[2].text()
    b = run_case(FULL, picker=seeded(2))[2].text()
    c = run_case(FULL, picker=seeded(1))[2].text()
    if a == b:
        errors.append("dues llavors diferents donen exactament la mateixa conversa")
    if a != c:
        errors.append("la mateixa llavor no reprodueix la conversa")
    questions = {line for seed in range(10) for line in run_case(["quit", "yes"], picker=seeded(seed))[2].text().splitlines()
                 if line.startswith("[1/")}
    if len(questions) < 2:
        errors.append("la primera pregunta no varia mai")
    return errors


def check_no_immediate_repetition():
    """Amb moltes respostes 'any' seguides, dues reaccions consecutives no són mai iguals."""
    errors = []
    for seed in range(5):
        lines = conversation(run_case(ALL_ANY, picker=seeded(seed))[2].text()).splitlines()
        reactions = [lines[i + 1] for i, line in enumerate(lines[:-1]) if line == "Your answer: any"]
        repeated = [r for r, s in zip(reactions, reactions[1:]) if r == s]
        if repeated:
            errors.append(f"llavor {seed}: reacció repetida seguida: {repeated[0]!r}")
    return errors


def check_every_answer_gets_a_reaction():
    errors = []
    for answers in (FULL, ALL_ANY):
        lines = conversation(run_case(answers)[2].text()).splitlines()
        for i, line in enumerate(lines):
            if line.startswith("Your answer:") and (i + 1 >= len(lines) or not lines[i + 1].strip()):
                errors.append(f"sense reacció després de {line!r}")
    return errors


def check_comments():
    text = run_case(FULL)[2].text()
    expected = ["Renting, perfect: it gives you a lot of flexibility.",
                "Gràcia, lovely choice: lively squares and a real neighbourhood feel.",
                "A flat, the most popular choice in the city.",
                "A terrace, great: with Barcelona's weather you'll make good use of it.",
                "Furnished, perfect: you'll be able to move in with just your suitcase.",
                "Got it: at least 1 bedroom.", "No problem, I won't filter by that.", "Perfect."]
    return [f"falta: {e!r}" for e in expected if e not in text]


def check_recap():
    errors = []
    cases = [
        (FULL, "Let me recap: you're looking for a flat to rent in Gràcia, up to 1,200 euros a month, "
               "on floor 2 or higher, not shared, with at least 1 bedroom, a terrace and furniture."),
        (answers_for(property_type="flat or duplex", location="near the beach", condition="new or very good",
                     terrace="Yes", parking="Yes"),
         "Let me recap: you're looking for a duplex or a flat in Ciutat Vella and Sant Martí, newly built or "
         "in very good condition, with a terrace and a parking space."),
        (answers_for(type="any", price="300k", then={"price": ["1.200"]}),
         "Let me recap: you're looking for a home, up to 300,000 euros (buying) or up to 1,200 euros a month (renting)."),
    ]
    for answers, expected in cases:
        text = run_case(answers)[2].text()
        if expected not in text:
            recap = [l for l in text.splitlines() if "looking for" in l]
            errors.append(f"resum esperat {expected!r}, obtingut {recap}")
    if "noted so far" in run_case(["show me"])[2].text():
        errors.append("es fa un resum sense cap preferència")
    if "looking for a home to rent" in run_case(["rent", "quit", "yes"])[2].text():
        errors.append("en sortir amb 'quit' es fa un resum (iteració 3: no)")
    return errors


def check_results_text():
    errors = []
    data = load_data()
    expected = [(answers_for(property_type="chalet"), "Good news! I found 4 homes for you:"),
                (answers_for(location="Les Corts", property_type="chalet"), "Good news! I found one home for you:"),
                # des de la iteració 3, si no hi ha res però algunes vivendes s'hi acosten, es mostren aquestes:
                # aquí cap vivenda falla menys de 3 criteris, així que es diu que no n'hi ha cap
                (answers_for(type="sale", price="50k", location="Gràcia", property_type="office",
                             condition="needs renovation", then={"price": ["no", "no"]}),
                 data["results"]["none"][0])]
    for answers, sentence in expected:
        if sentence not in run_case(answers)[2].text():
            errors.append(f"falta: {sentence!r}")
    return errors


CHECKS = [
    ("variació aleatòria reproduïble (llavor) i preguntes amb variants", check_randomness),
    ("no es repeteix seguida la mateixa formulació", check_no_immediate_repetition),
    ("cada resposta rep una reacció", check_every_answer_gets_a_reaction),
    ("comentaris d'agent, confirmacions implícites i acusaments", check_comments),
    ("resum final (complet, múltiple, tipus 'any', parcial en sortir)", check_recap),
    ("presentació del nombre de resultats", check_results_text),
]


def main():
    return run_suite("Bloc 4b (naturalitat i fluïdesa)", [], CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
