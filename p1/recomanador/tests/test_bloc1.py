"""Proves del bloc 1: estructura i flux (sense ingressos, ordre, claredat de les instruccions).

Inclou també els camins feliços i casos límite heretats de la iteració 0 (Ex. 6).
Els casos "límit" documenten el comportament actual, no el desitjat.

Execució:  python -m recomanador.tests.test_bloc1
"""

from recomanador.tests.common import answers_for, run_case, run_suite

# Des del bloc 3 (2a part) un número sol és un mínim (habitacions, banys, m2, planta) o un màxim
# (pressupost): per això aquí hi ha vivendes que abans quedaven fora per la igualtat exacta.
CASES = [
    ("happy path lloguer",
     answers_for(type="rent", location="Santa Coloma de Gramenet", bedrooms="3", bathrooms="2", floor="0"),
     [1, 7]),
    ("compra sense restriccions",
     answers_for(type="sale"),
     [2, 4, 6, 8, 10, 12, 13, 15, 16, 20, 21, 23, 24, 25, 26, 28, 29, 31, 33, 36, 40, 42, 46, 48, 49]),
    ("lloguer amb pressupost, planta i terrassa",
     answers_for(type="rent", price="700", floor="2", terrace="Yes"),
     [9, 43]),
    ("tipus any amb ús comercial",
     answers_for(location="Barcelona", commercial_use="Yes"),
     [19, 21, 22, 25, 38]),
    ("pressupost '250k' (abans igualtat exacta, ara màxim)",
     answers_for(type="sale", price="250k", location="Santa Coloma de Gramenet", bedrooms="4",
                 bathrooms="2", square_meters="120"),
     [2]),
    # Fins al bloc 2 les respostes 'buy', 'barcelona', 'yes' eren invàlides; des del bloc 3 s'entenen,
    # així que el cas fa servir respostes que continuen sent incomprensibles.
    ("límit: entrades invàlides es tornen a demanar",
     answers_for(type="rent", price="1k", location="Barcelona", terrace="Yes", elevator="No",
                 commercial_use="No",
                 retries={"type": ["maybe"], "price": ["lots"], "location": ["Madrid"], "terrace": ["perhaps"]}),
     [18, 19, 43]),
    # des del bloc 4 la sortida es confirma; des de la iteració 3 'quit' ja no mostra vivendes
    ("'quit' a mitja conversa s'acomiada sense resultats",
     ["rent", "quit", "yes"],
     []),
]


def check_flow_and_clarity():
    errors = []
    # Des del bloc 5 l'ajuda només surt amb 'help' o en fallar.
    _, state, io = run_case(answers_for(type="rent", retries={"price": ["help"]}))
    text = io.text()
    if "income" in state.preferences or "income" in text.lower():
        errors.append("encara es pregunta pels ingressos")
    # cada text es busca a partir de l'anterior (la benvinguda també diu "budget" des de la iteració 3)
    positions, start = [], 0
    for q in ["[1/", "buy or to rent", "[2/", "budget", "[3/", "area"]:
        start = text.find(q, max(start, 0))
        positions.append(start)
    if -1 in positions or positions != sorted(positions):
        errors.append(f"les tres primeres preguntes no són tipus -> preu -> zona: {positions}")
    if "type 'any'" not in text or "type 'quit'" not in text:
        errors.append("les instruccions inicials no expliquen 'any'/'quit'")
    if "euros/month" not in text or "If buying" in text or "thousands of euros" in text:
        errors.append("l'ajuda del preu no s'adapta al lloguer")

    _, _, io = run_case(["any", "help", "quit", "yes"])
    if "If renting" not in io.text() or "If buying" not in io.text():
        errors.append("amb tipus 'any' l'ajuda del preu no mostra les dues variants")

    _, _, io = run_case(["maybe", "quit", "yes"])
    if "didn't quite get that" not in io.text():
        errors.append("una resposta invàlida no mostra cap missatge")
    return errors


CHECKS = [("income, ordre, progrés, instruccions, ajuda, reprompt", check_flow_and_clarity)]


def main():
    return run_suite("Bloc 1", CASES, CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
