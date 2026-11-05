"""Gestor del diàleg (DM): política i bucle principal.

Iteració 0: diàleg lineal d'iniciativa del sistema, en l'ordre de les
preguntes del JSON, com a l'Ex. 6.
Bloc 1: l'ordre (tipus -> preu -> zona -> resta) el marca house_data_v2.json,
sense pregunta d'ingressos; cada pregunta mostra progrés i ajuda de format,
i una resposta no vàlida torna a mostrar l'ajuda.
Bloc 2: preguntes condicionals (`ask_if` al JSON, p.ex. jardí només per a
cases/xalets) i comiat sempre després dels resultats.
Bloc 3: les respostes d'opcions s'interpreten amb l'NLU (sinònims, zones, errors,
exclusions) i les numèriques amb `numeric` (diners, rangs, modificadors); les preguntes
de selecció múltiple es desen com a llista, les numèriques com a Range, i una suma
d'habitacions es confirma abans d'acceptar-la.
Bloc 4: reacció davant d'anomalies, segons la confiança en el que s'ha entès:
  - entès literalment -> s'accepta;
  - entès però interpretat (sinònim, zona, número amb sentit mínim/màxim) -> confirmació
    implícita ("Got it: at least 3 bedrooms.");
  - entès per aproximació (error tipogràfic) -> confirmació explícita ("Did you mean Eixample?");
  - ambigu ("buy or rent", "1200 1500") -> pregunta de clarificació;
  - plausible però estrany (fora del rang de les dades, lloguer de "300k", suma d'habitacions)
    -> confirmació explícita amb opció de canviar-ho;
  - no entès -> missatge que explica què s'espera, amb ajuda progressiva i, al final,
    l'opció de saltar la pregunta;
  - sortida -> es confirma abans de sortir.
Bloc 4 (naturalitat): cada resposta acceptada rep una reacció (`accept`), i abans dels
resultats es fa un resum de la cerca. L'ajuda de cada pregunta només surt si l'usuari falla o
escriu 'help'.
Bloc 5: comptador de coincidències. Després de cada resposta es recompten les vivendes que
compleixen tot el que s'ha dit fins ara; si el nombre baixa es diu ("That rules out 8 homes,
so 12 homes still match."), i si una resposta les deixaria a 0 s'avisa abans d'acceptar-la.
Iteració 3: 'show me' porta als resultats en qualsevol moment; si l'usuari manté una resposta que
deixa 0 vivendes, s'ofereix anar directament al resum; els resultats surten ordenats. L'usuari pot
corregir respostes anteriors ("change the budget", "actually, Gràcia", "back"): per això el bucle
pregunta sempre "la següent pregunta aplicable sense resposta". Si no hi ha resultats, es mostren
les "casi coincidències".
"""

import re

from . import corrections, lexicon, nlg, nlu, numeric
from .corrections import Correction
from .config import ANY, DATA_PATH, FEW_MATCHES, MULTI_SELECT_KEYS, OFFER_SKIP_AFTER, PURCHASE_SCALE_FROM
from .data_loader import load_data
from .io_adapter import ConsoleIO
from .recommender import (count_matches, find_suitable_houses, initialize_available_options, near_misses,
                          rank_houses, to_number)
from .state import DialogueState

_YES_NO = nlu.build_vocabulary("confirmation", ["No", "Yes"], [])
_OPERATIONS = nlu.build_vocabulary("type", ["rent", "sale"], [])

# Conversa en curs (estat i vocabularis de cada pregunta), per detectar correccions des de `ask`.
# El fixa `run` a l'inici de cada conversa.
_SESSION = {}

# Respostes després dels resultats per explorar ('all', 'next', 'prev'). Per acabar: comandes de sortida.
_RESULTS_ALL = {nlu.normalize(p) for p in lexicon.RESULTS_ALL}
_RESULTS_NEXT = {nlu.normalize(p) for p in lexicon.RESULTS_NEXT}
_RESULTS_PREV = {nlu.normalize(p) for p in lexicon.RESULTS_PREV}


class ExitConversation(Exception):
    """L'usuari ha confirmat que vol sortir."""


class ShowResults(Exception):
    """L'usuari vol veure els resultats ja ("show me"), o ha acceptat el resum amb 0 coincidències."""


def is_applicable(question, preferences):
    """Una pregunta amb `ask_if` només es fa si les respostes prèvies ho permeten.

    Si la condició encara no s'ha respost o s'ha respost 'any', es pregunta. Amb una
    resposta múltiple (p.ex. ['flat', 'house']) n'hi ha prou que un valor ho permeti.
    """
    for key, allowed in question.get('ask_if', {}).items():
        value = preferences.get(key, ANY)
        values = value if isinstance(value, list) else [value]
        if value != ANY and not any(v in allowed for v in values):
            return False
    return True


# --- Torns bàsics: preguntar, confirmar, no entès ---

def ask(io, data, prompt, help_lines=None, question=None):
    """Demana una resposta. Una comanda de sortida es confirma abans de sortir; 'help' mostra l'ajuda;
    'show me' porta directament als resultats (sense confirmació: és una petició explícita, no un error).
    A les preguntes principals (`question`), una correcció d'una resposta anterior llença Correction."""
    while True:
        answer = io.ask(prompt)
        if help_lines and nlu.is_help(answer):
            nlg.react(io, data, 'help')
            nlg.print_help(io, help_lines)
            continue
        if nlu.is_show_results(answer):
            nlg.react(io, data, 'show_results')
            raise ShowResults
        if question is not None and _SESSION:
            state = _SESSION['state']
            correction = corrections.detect(data, state.preferences, state.answer_order, question, answer,
                                            _SESSION['vocabularies'])
            if correction:
                raise correction
        if not nlu.is_exit(answer):
            return answer
        if confirm(io, data, nlg.reaction(data, 'confirm_exit'), prompt, exiting=True):
            raise ExitConversation
        nlg.react(io, data, 'continue')


def confirm(io, data, message, prompt, exiting=False):
    """Pregunta de sí/no. Si la resposta no s'entén es torna a demanar un cop; després compta com a No."""
    io.say(message, kind='warning')
    for attempt in range(2):
        reply = io.ask(prompt) if exiting else ask(io, data, prompt)
        if exiting and nlu.is_exit(reply):  # "quit" a "Are you sure you want to leave?" = sí
            return True
        if exiting and nlu.is_show_results(reply):  # la confirmació de sortida recorda 'show me'
            nlg.react(io, data, 'show_results')
            raise ShowResults
        value = nlu.interpret(_YES_NO, reply)
        if value is not None:
            return value == "Yes"
        if attempt == 0:
            nlg.react(io, data, 'yes_no_expected')
    return False


def not_understood(io, data, question, help_lines, failures, answer):
    """Resposta no entesa: què s'espera i l'ajuda de la pregunta (que només surt aquí o amb 'help');
    si falla diverses vegades, s'ofereix saltar-la."""
    if not answer.strip():
        nlg.react(io, data, 'empty', expected=question['expects'])
    elif failures == 1:
        nlg.react(io, data, 'not_understood', expected=question['expects'])
    else:
        nlg.react(io, data, 'explain_again')
    nlg.print_help(io, help_lines)
    if failures >= OFFER_SKIP_AFTER:
        nlg.react(io, data, 'offer_skip')


# --- Preguntes d'opcions ---

def clarify_choice(io, data, question, vocabulary, candidates):
    """'buy or rent' -> 'Sorry, do you mean buying or renting?'. Retorna el valor triat o None."""
    nlg.react(io, data, 'which_one', options=nlg.describe_options(data, candidates))
    answer = ask(io, data, question['prompt'])
    if nlu.is_any(answer):
        return ANY
    return nlu.interpret(nlu.restrict(vocabulary, candidates), answer)


def process_choice(io, data, question, options, help_lines):
    key = question['answer_key']
    multiple = key in MULTI_SELECT_KEYS
    yes_no = set(options) == {"Yes", "No"}
    vocabulary = nlu.build_vocabulary(key, options, data['houses'])
    failures = 0
    while True:
        answer = ask(io, data, question['prompt'], help_lines, question)
        # "anywhere except Nou Barris" conté "anywhere", però és una exclusió, no un 'any'.
        if nlu.is_any(answer) and not (multiple and nlu.has_exclusion(answer)):
            return accept(io, data, question, ANY)
        result = nlu.analyse(vocabulary, answer, multiple)
        if result.candidates:
            value = clarify_choice(io, data, question, vocabulary, result.candidates)
            if value is not None:
                return accept(io, data, question, value)
        elif result.value is not None and result.approximate:
            described = nlg.describe_value(data, result.value)
            if confirm(io, data, nlg.reaction(data, 'did_you_mean', value=described), question['prompt']):
                return accept(io, data, question, result.value)
            nlg.react(io, data, 'try_again')
            continue
        elif result.value is not None:
            # Només es repeteix el que s'ha interpretat (sinònim, zona...), no el que s'ha escrit tal qual.
            described = None if result.literal or yes_no else nlg.describe_value(data, result.value)
            return accept(io, data, question, result.value, described)
        failures += 1
        not_understood(io, data, question, help_lines, failures, answer)


def accept(io, data, question, value, described=None):
    """Reacciona a la resposta acceptada (comentari, confirmació implícita o acusament) i la retorna.

    En una correcció amb el valor ja dit ("actually, I want to buy") l'IO és silenciós (`quiet`):
    no es reacciona aquí perquè la correcció es confirma amb una sola línia ("Sure, I've updated...")."""
    if not getattr(io, 'quiet', False):
        nlg.react_to_answer(io, data, question, value, described)
    return value


# --- Preguntes numèriques ---

def available_range(data, key, operation):
    """(mínim, màxim) dels valors de `key` a les dades (preu: només del tipus d'operació)."""
    houses = [h for h in data['houses'] if key != 'price' or operation in (None, h['type'])]
    values = [to_number(h[key]) for h in houses]
    return numeric.Range(min(values), max(values))


def check_anomalies(io, data, question, value_range, operation, with_label):
    """Avisa si el valor és poc plausible. Retorna 'ok', 'keep' (l'usuari el manté) o 'change'.

    (Els valors fora del rang de les dades es detecten després, amb el comptador: vegeu check_matches.)
    """
    key = question['answer_key']
    described = nlg.describe_range(data, question, value_range, operation, with_label)
    bounds = [b for b in value_range if b is not None]
    if key == 'price' and operation == 'rent' and any(b >= PURCHASE_SCALE_FROM for b in bounds):
        if not confirm(io, data, nlg.reaction(data, 'implausible_rent', value=described), question['prompt']):
            return 'change'
        nlg.react(io, data, 'keep_answer', value=described)
        return 'keep'
    return 'ok'


def choose_operation(io, data, question):
    """Pressupost ambigu amb tipus 'any' ("800"): 'Is that a monthly rent or a purchase price?'"""
    nlg.react(io, data, 'rent_or_buy')
    return nlu.interpret(_OPERATIONS, ask(io, data, question['prompt']))


def ask_number(io, data, question, help_lines, operation, infer_operation=False):
    """Bucle d'una resposta numèrica. Retorna (Range o ANY, operació a què es refereix)."""
    key = question['answer_key']
    failures = 0
    while True:
        answer = ask(io, data, question['prompt'], help_lines, question)
        if nlu.is_any(answer):
            return accept(io, data, question, ANY), operation
        result = numeric.parse(answer, key, operation)
        if result is not None and result.candidates:
            failures += 1
            values = [nlg.format_number(v) for v in result.candidates]
            nlg.react(io, data, 'several_numbers', numbers=", ".join(values), low=values[0], high=values[1])
            continue
        if result is None:
            failures += 1
            not_understood(io, data, question, help_lines, failures, answer)
            continue
        chosen = operation
        if infer_operation:
            chosen = numeric.operation_for(result.range) or choose_operation(io, data, question)
            if chosen is None:
                failures += 1
                not_understood(io, data, question, help_lines, failures, answer)
                continue
            result = numeric.parse(answer, key, chosen)  # aplica la regla de compra ("250" -> 250.000)
        if result.parts and not confirm(io, data, nlg.sum_confirmation(question, result), question['prompt']):
            nlg.react(io, data, 'try_again')
            continue
        status = check_anomalies(io, data, question, result.range, chosen, infer_operation)
        if status == 'change':
            nlg.react(io, data, 'try_again')
            continue
        if status == 'ok':
            # Un número sempre s'interpreta (mínim/màxim...): es confirma implícitament, tret que
            # l'usuari acabi de confirmar una suma, on n'hi ha prou amb un acusament.
            described = None if result.parts else \
                nlg.describe_range(data, question, result.range, chosen, infer_operation)
            accept(io, data, question, result.range, described)
        return result.range, chosen


def process_number(io, data, question, preferences, help_lines):
    operation = preferences.get('type', ANY)
    if question['answer_key'] != 'price' or operation != ANY:
        return ask_number(io, data, question, help_lines, None if operation == ANY else operation)[0]
    # Tipus 'any': el pressupost pot ser de lloguer o de compra. S'esbrina a quina operació
    # es refereix (o es pregunta) i es demana també el de l'altra.
    first, operation = ask_number(io, data, question, help_lines, None, infer_operation=True)
    if first == ANY:
        return ANY
    other = 'rent' if operation == 'sale' else 'sale'
    other_help = nlg.question_help(question, data, {'type': other}, [])
    io.say(data['reactions']['other_budget'][other], kind='question')
    second, _ = ask_number(io, data, question, other_help, other, infer_operation=False)
    return {operation: first, other: second}


def current_matches_for_question(data, question, preferences):
    """
    Returns the homes that match all preferences already given,
    excluding the answer to the question currently being asked.

    Excluding the current key is important when a user goes back
    and changes a previous answer.
    """
    key = question['answer_key']

    other_preferences = {
        pref_key: value
        for pref_key, value in preferences.items()
        if pref_key != key
    }

    return find_suitable_houses(data, other_preferences)


def print_availability(io, data, question, preferences):
    """Sota la pregunta, les opcions o el rang que encara encaixen amb la resta de respostes (iteració 4):
    les zones amb vivendes a la pregunta de la zona i els valors disponibles a la resta."""
    houses = current_matches_for_question(data, question, preferences)
    if question['answer_key'] == 'location':
        nlg.print_available_zones(io, data, houses)
    else:
        nlg.print_available_values(io, question, houses, preferences)


def process_question(io, data, question, state, options):
    help_lines = nlg.question_help(question, data, state.preferences, options)
    if question['type'] == 'numerical':
        return process_number(io, data, question, state.preferences, help_lines)
    return process_choice(io, data, question, options, help_lines)


# --- Comptador de coincidències (bloc 5) ---

def out_of_range_message(data, question, value, preferences):
    """Si el valor tot sol ja no el compleix cap vivenda ("10 bedrooms"), s'explica per què."""
    key = question['answer_key']
    operation = preferences.get('type') if preferences.get('type') in ('rent', 'sale') else None
    if not isinstance(value, numeric.Range) or count_matches(data, {'type': operation or ANY, key: value}):
        return None
    described = nlg.describe_range(data, question, value, operation)
    low, high = available_range(data, key, operation)
    if (value.min is not None and value.min > high) or (value.max is not None and value.max < low):
        available = nlg.describe_range(data, question, numeric.Range(low, high), operation)
        return nlg.reaction(data, 'out_of_range', value=described, available=available), described
    # Dins del rang de les dades però en un buit (p.ex. entre 155 i 195 m2): no s'ha de dir "ours have 45-277".
    return nlg.reaction(data, 'no_value_matches', value=described), described


def valid_answer(data, question, preferences, text):
    """`text` (sense marcador de correcció) és una resposta vàlida per a `question`? La retorna, o None."""
    text = corrections.strip_marker(text)
    key = question['answer_key']
    if question['type'] == 'numerical':
        operation = preferences.get('type') if preferences.get('type') in ('rent', 'sale') else None
        result = numeric.parse(text, key, operation)
        return text if result is not None and result.range is not None else None
    vocabulary = _SESSION.get('vocabularies', {}).get(key)
    if vocabulary is None:
        return None
    result = nlu.analyse(vocabulary, text, key in MULTI_SELECT_KEYS)
    return text if result.value is not None or result.candidates else None


def confirm_change(io, data, question, preferences, message):
    """'Do you want to change it?'. Retorna (canviar?, resposta nova o None).

    Iteració 3: si en lloc de sí/no l'usuari dona directament un valor nou ("actually, Gràcia"),
    s'entén com a sí i el valor es fa servir com a nova resposta (passa per la validació normal).
    """
    io.say(message, kind='warning')
    for attempt in range(2):
        reply = ask(io, data, question['prompt'])
        value = nlu.interpret(_YES_NO, reply)
        if value is not None:
            return value == "Yes", None
        new_answer = valid_answer(data, question, preferences, reply)
        if new_answer:
            return True, new_answer
        if attempt == 0:
            nlg.react(io, data, 'yes_no_expected')
    return False, None


def check_matches(io, data, question, state, value, before, old=None, offer_summary=True):
    """Si la resposta deixa 0 vivendes (i abans n'hi havia), s'avisa i es pot canviar.

    Retorna (veredicte, resposta nova): 'ok' (acceptada), 'change' (l'usuari la vol canviar; si ja ha
    dit el valor nou, ve a la resposta nova) o 'stop' (la manté i, com que ja no queda cap vivenda,
    accepta l'oferta d'anar directament al resum; iteració 3).
    El recompte es fa sobre les preferències tal com quedaran (sense respostes obsoletes: en canviar
    lloguer per compra, el pressupost de lloguer ja no compta). `before` és el punt de referència: en una
    correcció, les vivendes que hi havia amb el valor antic (si ja eren 0, no hi ha res a avisar).
    `offer_summary`: després dels resultats no s'ofereix "anar al resum" (es tornen a mostrar igualment).
    """
    after = count_matches(data, with_answer(data, state.preferences, question['answer_key'], value, old))
    if after or not before:
        return 'ok', None
    alone = out_of_range_message(data, question, value, state.preferences)
    message = alone[0] if alone else nlg.reaction(data, 'no_matches', before=nlg.count_text(data, before))
    change, new_answer = confirm_change(io, data, question, state.preferences, message)
    if change:
        if new_answer is None:
            nlg.react(io, data, 'try_again')
            # És quan més útil és saber què encara encaixa (la resposta anterior deixava 0 vivendes).
            print_availability(io, data, question, state.preferences)
        return 'change', new_answer
    if alone:
        nlg.react(io, data, 'keep_answer', value=alone[1])
    else:
        nlg.react(io, data, 'keep_no_matches')
    if offer_summary and confirm(io, data, nlg.reaction(data, 'offer_summary'), question['prompt']):
        return 'stop', None
    nlg.react(io, data, 'continue')
    return 'ok', None


# --- Desar respostes i correccions (iteració 3) ---

class PrefilledIO:
    """IO que dona `first` com a primera resposta sense preguntar-la ("change the area to Gràcia":
    'Gràcia' passa per tota la validació normal, com si l'usuari l'hagués escrit a la pregunta).

    `quiet`: no es reacciona a la resposta (vegeu `accept`); s'hereta si l'IO de dins ja ho és."""

    def __init__(self, io, first, quiet=False):
        self.io, self.first = io, first
        self.quiet = quiet or getattr(io, 'quiet', False)

    def ask(self, prompt):
        if self.first is not None:
            answer, self.first = self.first, None
            return answer
        return self.io.ask(prompt)

    def say(self, *args, kind=None):
        self.io.say(*args, kind=kind)

    def clear(self):
        self.io.clear()


def with_answer(data, preferences, key, value, old):
    """Preferències tal com quedaran en desar `key` = `value`: sense les respostes que ja no s'apliquen
    (p.ex. el jardí si ara és un pis) i, si el valor ha canviat, sense les que en depenen (`depends_on`:
    el pressupost si canvia lloguer/compra). Les preguntes esborrades es tornaran a fer si s'apliquen."""
    result = {**preferences, key: value}
    changed = old is not None and old != value
    for question in data['questions']:
        other = question['answer_key']
        if other != key and other in result and (
                (changed and key in question.get('depends_on', [])) or not is_applicable(question, result)):
            del result[other]
    return result


def ask_and_store(io, data, question, state, options, previous=None, old=None, on_stored=None, at_end=False):
    """Fa la pregunta, comprova les coincidències, desa la resposta i actualitza el comptador.

    `previous`: vivendes que hi havia abans (en una correcció, amb el valor antic) per dir si n'hi ha
    més o menys; `old`: valor antic (per saber si ha canviat); `on_stored(value)`: es crida en desar-la,
    abans del comptador (per confirmar una correcció abans de dir quantes vivendes queden).
    """
    key = question['answer_key']
    before = count_matches(data, state.preferences)
    # Referència per a l'avís de 0 vivendes: el que l'usuari té ara mateix. En una correcció és el recompte
    # amb el valor antic (`previous`), no el recompte sense aquesta pregunta: si l'usuari ja havia acceptat
    # quedar-se sense vivendes, tornar-li a avisar "until now we had 5" seria fals i repetitiu.
    baseline = before if previous is None else previous
    value = process_question(io, data, question, state, options)
    verdict, new_answer = check_matches(io, data, question, state, value, baseline, old, not at_end)
    while verdict == 'change':
        retry_io = PrefilledIO(io, new_answer) if new_answer else io
        value = process_question(retry_io, data, question, state, options)
        verdict, new_answer = check_matches(io, data, question, state, value, baseline, old, not at_end)
    updated = with_answer(data, state.preferences, key, value, old)
    state.answer_order = [k for k in state.answer_order if k in updated] + [key]
    state.preferences.clear()
    state.preferences.update(updated)
    state.reached.add(key)  # respost (no només mostrat: "show me" a la pregunta no compta)
    if on_stored:
        on_stored(value)
    # Comptador: quantes vivendes queden després d'aquesta resposta (i quantes s'han descartat).
    remaining = count_matches(data, state.preferences)
    state.match_history.append((key, before, remaining))
    previous = before if previous is None else previous
    if 0 < remaining < previous:
        nlg.print_count_update(io, data, previous, remaining)
        if remaining <= FEW_MATCHES and not state.show_me_hinted:  # pista de 'show me', un sol cop
            nlg.react(io, data, 'show_me_hint')
            state.show_me_hinted = True
    elif remaining > previous:
        nlg.react(io, data, 'count_more', count=nlg.count_text(data, remaining))
    if verdict == 'stop':  # la resposta ja és desada: el resum la inclou
        raise ShowResults


def handle_correction(io, data, state, correction, questions, options, at_end=False):
    """Aplica una correcció.

    - Si l'usuari ja ha dit el valor nou ("actually, I want to buy", "change the budget to 900"), no es
      torna a fer la pregunta en veu alta: el valor passa per la validació normal i el canvi es confirma
      amb una sola línia ("Sure, I've updated buying or renting: buying.").
    - Si no ("change the budget", "back"), es torna a fer la pregunta.
    - `at_end` (després dels resultats): es pot afegir una pregunta que no s'havia arribat a fer.
    """
    key = correction.key
    if correction.kind == 'unclear':
        nlg.react(io, data, 'correction_unclear')
        return
    if correction.kind == 'nothing_back':
        nlg.react(io, data, 'correction_nothing_back')
        return
    if correction.kind == 'not_yet' and not (at_end and is_applicable(questions[key], state.preferences)):
        nlg.react(io, data, 'correction_not_yet', slot=nlg.slot_name(data, key))
        return
    question = questions[key]
    quiet = correction.value_text is not None
    if not quiet:
        nlg.react(
            io,
            data,
            'correction_ack',
            slot=nlg.slot_name(data, key)
        )

        io.say(
            f"\n{nlg.question_text(question, state.preferences)}",
            kind='question'
        )
        print_availability(io, data, question, state.preferences)
    previous = count_matches(data, state.preferences)
    old = state.preferences.pop(key, None)
    if key in state.answer_order:
        state.answer_order.remove(key)
    sub_io = PrefilledIO(io, correction.value_text, quiet=True) if quiet else io

    def confirm_update(value):
        # "Done, I've changed the area to Gràcia." amb valors d'opció; amb rangs, Sí/No o 'any' quedaria
        # forçat ("changed the budget to up to 900 euros"): "Done, I've updated the budget: up to 900 euros."
        option = value != ANY and not isinstance(value, (tuple, dict)) and value not in ("Yes", "No")
        nlg.react(io, data, 'correction_done' if option else 'correction_done_value', slot=nlg.slot_name(data, key),
                  value=nlg.describe_answer(data, question, value, state.preferences))

    try:
        ask_and_store(sub_io, data, question, state, options[key], previous, old,
                      on_stored=confirm_update if quiet else None, at_end=at_end)
    except (Correction, ExitConversation, ShowResults):
        if key not in state.preferences and old is not None:  # no s'ha respost: es manté el valor antic
            state.preferences[key] = old
            state.answer_order.append(key)
        raise


def next_question(questions, preferences, allowed=None):
    """La primera pregunta aplicable sense resposta (després d'una correcció pot ser una d'anterior).
    `allowed`: si es dona, només es consideren aquestes preguntes."""
    for question in questions:
        key = question['answer_key']
        if is_applicable(question, preferences) and key not in preferences and (allowed is None or key in allowed):
            return question
    return None


def question_loop(io, data, state, questions, by_key, options,
                  pending=None, only_reached=False, at_end=False):

    """Fa les preguntes pendents (i aplica les correccions) fins que no en queda cap.

    `only_reached`: després de 'show me', una correcció no reprèn tot el qüestionari;
    només es tornen a fer les preguntes que ja s'havien arribat a fer
    (p.ex. el pressupost, si es canvia lloguer/compra).
    """

    while True:
        try:
            if pending:
                correction, pending = pending, None
                handle_correction(
                    io, data, state, correction,
                    by_key, options, at_end
                )
                continue

            question = next_question(
                questions,
                state.preferences,
                state.reached if only_reached else None
            )

            if question is None:
                return

            applicable = [
                q for q in questions
                if is_applicable(q, state.preferences)
            ]

            index = 1 + sum(
                q['answer_key'] in state.preferences
                for q in applicable
            )

            # Main question
            nlg.print_question(
                io,
                index,
                len(applicable),
                question,
                state.preferences
            )

            # Secondary grey availability information
            print_availability(io, data, question, state.preferences)

            # Actually ask, validate and store the answer
            ask_and_store(
                io,
                data,
                question,
                state,
                options[question['answer_key']],
                at_end=at_end
            )

        except Correction as correction:
            pending = correction

def interpret_change(data, state, reply):
    """Després dels resultats, una resposta que demana un canvi: Correction, 'which' (vol canviar però no
    diu què: "yes", "change") o None. Aquí no cal marcador: "the budget" o "Gràcia" ja diuen què canviar."""
    vocabularies = _SESSION['vocabularies']
    correction = corrections.detect(data, state.preferences, state.answer_order, None, reply, vocabularies)
    if correction and correction.kind != 'unclear':
        return correction
    if correction or nlu.interpret(_YES_NO, reply) == 'Yes':
        return 'which'
    correction = corrections.detect(data, state.preferences, state.answer_order, None,
                                    f"actually {reply}", vocabularies)
    return correction if correction and correction.kind != 'unclear' else None


def _house_id(reply):
    """'18', '#18', 'house 18', 'home 18' -> 18; si no, None."""
    match = re.fullmatch(r"(?:#|house|home|id|number|casa|piso|pis)?\s*#?\s*(\d+)", reply.strip().lower())
    return int(match.group(1)) if match else None


def explore_results(io, data, state, houses, near, prompt):
    """Després del resum dels resultats: l'usuari explora ('all', 'next'/'prev', el número d'una vivenda),
    canvia alguna resposta o acaba amb una comanda de sortida ('quit', 'exit'...).

    Iteració 3: "no" ja no acaba (en "change pets to no" es prenia per un "no" i es tancava la conversa);
    per això també es mira primer si és un canvi. Després de cada fitxa es torna a mostrar la llista de
    resultats, perquè l'usuari tingui sempre a mà els números. Si només hi ha una vivenda, es mostra ja.

    Retorna la Correction a aplicar, 'show' (tornar a mostrar el resum) o None (acabar). Dues respostes
    no enteses seguides tanquen la conversa (no es pregunta indefinidament).
    """
    items = houses or [house for house, _ in near]
    failures = {house['id']: failed for house, failed in near}
    ids = [house['id'] for house in items]
    cursor = -1
    if len(items) == 1:  # una sola vivenda: no cal demanar-la
        cursor = 0
        nlg.print_result(io, data, items, 0, failures.get(ids[0]))
    nlg.react(io, data, 'explore_menu', example=ids[0]) if items else nlg.react(io, data, 'nothing_to_explore')
    unclear = 0
    while unclear < 2:
        reply = io.ask(prompt)
        text = nlu.normalize(reply)
        if nlu.is_exit(reply):
            return None
        if nlu.is_show_results(reply):
            return 'show'
        if items and (text in _RESULTS_ALL or text in _RESULTS_NEXT or text in _RESULTS_PREV
                      or _house_id(reply) is not None):
            unclear = 0
            if text in _RESULTS_ALL:
                nlg.print_all_results(io, data, items, failures)
            elif text in _RESULTS_NEXT or text in _RESULTS_PREV:
                step = 1 if text in _RESULTS_NEXT else -1
                if not 0 <= cursor + step < len(items):
                    nlg.react(io, data, 'explore_last' if step == 1 else 'explore_first')
                    continue
                cursor += step
                nlg.print_result(io, data, items, cursor, failures.get(items[cursor]['id']))
            elif _house_id(reply) in ids:
                cursor = ids.index(_house_id(reply))
                nlg.print_result(io, data, items, cursor, failures.get(items[cursor]['id']))
            else:
                nlg.react(io, data, 'explore_no_id', id=_house_id(reply), ids=", ".join(f"#{i}" for i in ids))
                continue
            nlg.print_results_list(io, data, houses, near)  # la llista, sempre a mà
            nlg.react(io, data, 'explore_again')
            continue
        change = interpret_change(data, state, reply)
        if change == 'which':
            nlg.react(io, data, 'which_change')
            continue
        if change:
            return change
        unclear += 1
        nlg.react(io, data, 'explore_unclear' if items else 'correction_unclear')
    return None


def show_results(io, data, state):
    """Resum de la cerca i dels resultats (una línia per vivenda). Retorna (resultats, casi coincidències)."""
    io.clear()
    nlg.print_recap(io, data, state.preferences, 'intro_early' if state.stopped_early else 'intro')
    suitable_houses = rank_houses(find_suitable_houses(data, state.preferences))
    near = near_misses(data, state.preferences) if not suitable_houses else []
    nlg.print_results_overview(io, data, suitable_houses, near)
    return suitable_houses, near


def run(data_path=DATA_PATH, io=None, picker=None):
    """Executa una conversa completa. Retorna (state, suitable_houses).

    `picker` tria les formulacions; per defecte a l'atzar (nlg.first_choice per a proves deterministes).
    """
    io = io or ConsoleIO()
    nlg.configure(picker)
    data = load_data(data_path)
    state = DialogueState()
    available_options = {}
    initialize_available_options(data, available_options)
    questions = data['questions']
    by_key = {q['answer_key']: q for q in questions}
    options = {q['answer_key']: sorted(available_options.get(q['answer_key'], []))
               if q['type'] == 'multichoice' else [] for q in questions}
    vocabularies = {key: nlu.build_vocabulary(key, opts, data['houses']) for key, opts in options.items() if opts}
    _SESSION.clear()
    _SESSION.update(state=state, vocabularies=vocabularies)

    nlg.print_welcome(io, data)
    nlg.print_count_start(io, data, count_matches(data, state.preferences))

    suitable_houses = []
    try:
        try:
            question_loop(io, data, state, questions, by_key, options)
        except ShowResults:
            state.stopped_early = True
        # Resultats i exploració ('all', 'next', un número, un canvi...) fins que l'usuari acaba.
        while True:
            suitable_houses, near = show_results(io, data, state)
            change = explore_results(io, data, state, suitable_houses, near, questions[0]['prompt'])
            if change is None:
                break
            if change == 'show':
                continue
            try:
                question_loop(io, data, state, questions, by_key, options, pending=change,
                              only_reached=state.stopped_early, at_end=True)
            except ShowResults:
                state.stopped_early = True
    except ExitConversation:
        # 'quit' (confirmat) només s'acomiada: per veure les vivendes hi ha 'show me'.
        state.exited = True
        suitable_houses = []
    finally:
        _SESSION.clear()

    nlg.print_goodbye(io, data)
    return state, suitable_houses
