"""Proves del bloc 5: comptador de coincidències a cada pas del filtre, avís quan una resposta
deixaria 0 vivendes, i ajuda només a demanda (decisió presa en tancar el bloc 4).

Execució:  python -m recomanador.tests.test_bloc5
"""

from recomanador.numeric import Range
from recomanador.tests.common import answers_for, conversation, run_case, run_suite

# lloguer -> 25; <= 1.200 -> 13; Gràcia -> 2 (18 i 32); pis -> 2; no compartit -> 1 (la 18)
STEPS = dict(type="rent", price="1.200", location="Gràcia", property_type="flat", shared="No")


def check_counter():
    errors = []
    _, state, io = run_case(answers_for(**STEPS))
    history = [(key, before, after) for key, before, after in state.match_history if after != before]
    expected = [("type", 50, 25), ("price", 25, 13), ("location", 13, 2), ("shared", 2, 1)]
    if history != expected:
        errors.append(f"historial del comptador {history}, esperat {expected}")
    text = conversation(io.text())
    for sentence in ["Right now we have 50 homes available. Let's narrow them down!", "That leaves 25 homes.",
                     "That leaves 13 homes.", "Only 2 homes left, we're getting close!",
                     "Only one home left that fits everything!"]:
        if sentence not in text:
            errors.append(f"falta: {sentence!r}")
    after_flat = text.split("Your answer: flat")[1].split("\n[")[0]
    if "home" in after_flat:
        errors.append("es parla del comptador tot i que la resposta no ha descartat cap vivenda")
    return errors


def check_counter_matches_results():
    ids, state, _ = run_case(answers_for(type="sale", location="Barcelona", bedrooms="3"))
    final = state.match_history[-1][2]
    return [] if final == len(ids) else [f"el comptador acaba a {final} però hi ha {len(ids)} resultats"]


def check_zero_matches():
    errors = []
    # "2 bedrooms" deixaria 0 vivendes (la 18 en té 1): avís -> sí, canviar -> "1"
    _, state, io = run_case(answers_for(**STEPS, bedrooms="1", retries={"bedrooms": ["2", "yes"]}))
    if "With that answer, no home would match everything you've told me so far (until now we had one home)." \
            not in io.text():
        errors.append("no s'avisa quan una resposta deixa 0 vivendes")
    if state.preferences["bedrooms"] != Range(1, None):
        errors.append("en voler canviar-la no es torna a preguntar")

    # mantenir-la: cap avís més i cap resultat
    ids, state, io = run_case(answers_for(**STEPS, bedrooms="2", floor="5", then={"bedrooms": ["no", "no"]}))
    text = io.text()
    if "OK, I'll keep it, although for now no home matches." not in text or ids:
        errors.append("en mantenir una resposta sense coincidències no es manté")
    if text.count("no home would match") != 1:
        errors.append("s'avisa més d'un cop després d'haver-se quedat sense coincidències")
    return errors


def check_help_on_demand():
    errors = []
    text = conversation(run_case(answers_for(type="rent", retries={"price": ["help"], "location": ["?"]}))[2].text())
    first_question = text.split("[1/")[1].split("Your answer")[0]
    if "Type" in first_question:
        errors.append("l'ajuda surt sense demanar-la")
    if "Of course, here's how you can answer:\n   Type your maximum monthly rent" not in text:
        errors.append("'help' no mostra l'ajuda del pressupost")
    if "Barcelona (whole city), or one of its districts" not in text:
        errors.append("'?' no mostra les opcions d'ubicació")
    if "didn't quite get that" in text:
        errors.append("'help' es compta com una resposta no entesa")
    return errors


CHECKS = [
    ("comptador: inici, descartades a cada pas, pocs, un, sense canvis", check_counter),
    ("el comptador final coincideix amb els resultats", check_counter_matches_results),
    ("avís quan una resposta deixaria 0 vivendes (canviar o mantenir)", check_zero_matches),
    ("ajuda només amb 'help'/'?' o en fallar", check_help_on_demand),
]


def main():
    return run_suite("Bloc 5 (comptador de coincidències)", [], CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
