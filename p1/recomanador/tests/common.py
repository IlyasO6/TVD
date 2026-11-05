"""Utilitats compartides per les proves de cada iteració."""

from recomanador import nlg, nlu, run
from recomanador.config import ANY, MULTI_SELECT_KEYS
from recomanador.data_loader import load_data
from recomanador.dialogue_manager import is_applicable
from recomanador.io_adapter import ScriptedIO
from recomanador.recommender import initialize_available_options


def run_case(answers, picker=nlg.first_choice, finish=True):
    """Executa un diàleg simulat. Retorna (ids recomanats, estat, io).

    `finish`: s'afegeix un "quit" al final per sortir del menú de resultats (iteració 3; "no" ja no
    hi serveix); si la conversa acaba abans, simplement no es fa servir.

    Per defecte les formulacions són deterministes (sempre la primera de cada llista).
    Els ids es retornen ordenats: aquí es comprova QUINES vivendes surten; l'ordre de presentació
    (iteració 3, per preu) es comprova a part, a test_iter3.
    """
    io = ScriptedIO(list(answers) + (["quit"] if finish else []))
    state, houses = run(io=io, picker=picker)
    return sorted(h["id"] for h in houses), state, io


def conversation(text):
    """Part de la transcripció anterior als resultats (preguntes, ajudes i reaccions)."""
    return text.split("<clear>")[0]


def _canonical(question, answer, data, available_options):
    """Valor que el sistema entendrà (per saber quines preguntes condicionals es faran)."""
    if nlu.is_any(answer):
        return ANY
    if question["type"] == "numerical":
        return answer
    key = question["answer_key"]
    vocabulary = nlu.build_vocabulary(key, sorted(available_options.get(key, [])), data["houses"])
    return nlu.interpret(vocabulary, answer, multiple=key in MULTI_SELECT_KEYS)


def answers_for(retries=None, then=None, **prefs):
    """Llista de respostes en l'ordre actual de preguntes; 'any' per a les no indicades.

    Els valors poden ser formes lliures ('ALQUILER', 'near the beach'): la condició de les
    preguntes condicionals s'avalua sobre el valor interpretat, com fa el sistema.
    `retries` = {clau: [respostes]} s'insereixen abans de la resposta final (invàlides o rebutjades);
    `then` = {clau: [respostes]} s'afegeixen després (p.ex. el 'yes' d'una confirmació).
    Fa que els casos de prova no depenguin de l'ordre ni del nombre de preguntes.
    """
    retries = retries or {}
    then = then or {}
    data = load_data()
    available_options = {}
    initialize_available_options(data, available_options)
    answers, given = [], {}
    for question in data["questions"]:
        if not is_applicable(question, given):
            continue
        key = question["answer_key"]
        value = prefs.get(key, ANY)
        given[key] = _canonical(question, value, data, available_options)
        answers.extend(retries.get(key, []))
        answers.append(value)
        answers.extend(then.get(key, []))
    return answers


def run_suite(title, cases, checks):
    """cases: [(nom, respostes, ids esperats)]; checks: [(nom, funció -> llista d'errors)]."""
    print(f"== {title} ==")
    failures = 0
    for name, answers, expected in cases:
        got, _, _ = run_case(answers)
        ok = got == expected
        failures += not ok
        print(f"[{'OK' if ok else 'FAIL'}] {name}" + ("" if ok else f"\n    esperat {expected}\n    obtingut {got}"))
    for name, check in checks:
        errors = check()
        failures += len(errors)
        print(f"[{'OK' if not errors else 'FAIL'}] {name}" + "".join(f"\n    {e}" for e in errors))
    print("Tot correcte\n" if not failures else f"{failures} error(s)\n")
    return failures
