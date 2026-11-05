"""Generació de llenguatge: microplanificació i realització superficial.

Iteració 0: textos de l'Ex. 6. Les funcions reben l'objecte IO en lloc de
fer print() directament.
Bloc 1: instruccions inicials, indicador de progrés i ajuda de format per a
cada pregunta (amb els rangs reals de les dades).
Bloc 3: les opcions ja no cal escriure-les exactament; s'hi afegeixen les zones.
Bloc 4: reaccions (llistes de formulacions per situació al JSON) i descripció del que
s'ha entès ("at least 3 bedrooms", "all of Barcelona") per a les confirmacions.
Bloc 4 (naturalitat): les formulacions es trien a l'atzar sense repetir la darrera de cada
situació; preguntes amb variants; reacció a cada resposta (comentari propi del valor,
confirmació implícita o acusament de recepció); resum final de la cerca (microplanificació:
agregació de les preferències en una sola frase) i presentació dels resultats.
"""

import random

from .config import ANY, FEW_MATCHES, ZONES_EXCEPT_MAX
from .lexicon import ZONES
from .recommender import to_number, value_range

OPTIONS_LABEL = "Options:"
TYPE_LABELS = {"rent": "If renting", "sale": "If buying"}


# --- Tria de formulacions ---

class VariedPicker:
    """Tria una formulació a l'atzar evitant repetir l'última de la mateixa situació."""

    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.last = {}

    def __call__(self, options, key):
        candidates = [o for o in options if o != self.last.get(key)] or options
        choice = self.rng.choice(candidates)
        self.last[key] = choice
        return choice


def first_choice(options, key):
    """Tria determinista (la primera formulació): per a les proves."""
    return options[0]


_picker = VariedPicker()


def configure(picker=None):
    """Cada conversa comença amb un selector nou (per defecte, aleatori)."""
    global _picker
    _picker = picker or VariedPicker()


def pick(options, key):
    return options if isinstance(options, str) else _picker(options, key)


def print_welcome(io, data):
    io.say(pick(data['start_message'], 'start_message'), kind='title')
    n = len(data['questions'])
    for line in data['instructions']:
        io.say(line.format(n=n), kind='info')


def print_goodbye(io, data):
    io.say("\n" + pick(data['end_message'], 'end_message'), kind='goodbye')


def _format_help(template, houses, key):
    low, high = value_range(houses, key)
    return template.format(min=low, max=high)


def question_help(question, data, preferences, options):
    """Línies d'ajuda que expliquen com respondre `question`.

    Els rangs {min}/{max} es calculen sobre les dades. Si la pregunta té
    variants per tipus (preu), es tria la del tipus ja respost; amb 'any'
    es mostren totes dues.
    """
    key = question['answer_key']
    lines = []
    if 'help_by_type' in question:
        chosen = preferences.get('type', ANY)
        for house_type, template in question['help_by_type'].items():
            if chosen not in (house_type, ANY):
                continue
            houses = [h for h in data['houses'] if h['type'] == house_type]
            text = _format_help(template, houses, key)
            lines.append(text if chosen == house_type else f"{TYPE_LABELS[house_type]}: {text}")
    elif question['type'] == 'numerical':
        lines.append(_format_help(question['help'], data['houses'], key))
    else:
        lines.append(question['help'])
    if key == 'location':
        lines.extend(location_option_lines(data['houses']))
    elif options:
        lines.append(f"{OPTIONS_LABEL} {' / '.join(options)}")
    return lines


def location_option_lines(houses):
    """Opcions d'ubicació agrupades: ciutats amb districtes i, a part, la resta de municipis."""
    by_city = {}
    for house in houses:
        by_city.setdefault(house['city'], set()).add(house['location'])
    lines = [OPTIONS_LABEL]
    towns = []
    for city, locations in sorted(by_city.items()):
        if locations == {city}:
            towns.append(city)
        else:
            lines.append(f"  - {city} (whole city), or one of its districts: {' / '.join(sorted(locations))}")
    if towns:
        lines.append(f"  - Nearby towns: {' / '.join(towns)}")
    lines.append(f"  - Areas: {' / '.join(ZONES)}")
    return lines


def print_available_zones(io, data, houses):
    """Iteració 3: amb la pregunta de la zona, una frase discreta (format d'ajuda) amb les zones on hi ha
    vivendes que encaixen amb la resta de respostes. Microplanificació: agrupació per ciutat
    ("Barcelona (Eixample and Gràcia)") i agregació si hi són tots els districtes ("every district of
    Barcelona") o gairebé tots ("every district of Barcelona except Les Corts", més curt que la llista);
    primer les ciutats amb districtes i després els municipis; la frase amb "except" sempre al final, perquè
    els noms que la seguissin semblarien part de l'excepció. Sense vivendes, no es diu res."""
    if not houses:
        return
    every, found = {}, {}
    for house in data['houses']:
        every.setdefault(house['city'], set()).add(house['location'])
    for house in houses:
        found.setdefault(house['city'], set()).add(house['location'])
    names = []  # (va al final?, és un municipi?, text)
    for city, locations in found.items():
        missing = sorted(every[city] - locations)
        if every[city] == {city}:
            names.append((False, True, city))
        elif not missing:
            names.append((False, False, pick(data['reactions']['zones_whole_city'], 'zones_whole_city').format(
                city=city)))
        elif len(missing) <= ZONES_EXCEPT_MAX and len(missing) < len(locations):
            names.append((True, False, pick(data['reactions']['zones_city_except'], 'zones_city_except').format(
                city=city, missing=_join(missing))))
        elif len(locations) == 1:
            names.append((False, False, f"{next(iter(locations))} ({city})"))
        else:
            names.append((False, False, f"{city} ({_join(sorted(locations))})"))
    single = sum(len(locations) for locations in found.values()) == 1
    react(io, data, 'zones_single' if single else 'zones_available', zones=_join(text for *_, text in sorted(names)))

def print_available_values(io, question, houses, preferences):
    """
    Shows the values currently available among the homes that still match
    the user's previous answers.

    Printed as a secondary/help-style line below the question.
    """
    if not houses:
        return

    key = question['answer_key']

    if key == 'property_type':
        values = sorted({house['property_type'] for house in houses})

        io.say(
            f"Currently available: {' / '.join(values)}.",
            kind='help'
        )

    elif key == 'condition':
        values = sorted({house['condition'] for house in houses})

        io.say(
            f"Currently available: {' / '.join(values)}.",
            kind='help'
        )

    elif key == 'square_meters':
        low, high = value_range(houses, 'square_meters')

        io.say(
            f"Your current matches range from {low} m2 to {high} m2.",
            kind='help'
        )

    elif key == 'price':
        low, high = value_range(houses, 'price')

        operation = preferences.get('type')

        if operation == 'rent':
            text = (
                f"Your current matches range from "
                f"{low} to {high} euros/month."
            )
        elif operation == 'sale':
            text = (
                f"Your current matches range from "
                f"{low} to {high} euros."
            )
        else:
            text = (
                f"Your current matches range from "
                f"{low} to {high} euros."
            )

        io.say(text, kind='help')

def format_location(house):
    if house['location'] == house['city']:
        return house['location']
    return f"{house['location']} ({house['city']})"


def question_text(question, preferences):
    """Formulació de la pregunta. `question_if` (iteració 3) en canvia les variants segons una resposta
    anterior: p.ex. si l'usuari accepta compartir, s'aclareix que les habitacions són de tota la vivenda."""
    variants = question['question']
    for key, by_value in question.get('question_if', {}).items():
        if preferences.get(key) in by_value:
            variants = by_value[preferences[key]]
    return pick(variants, question['answer_key'])


def print_question(io, index, total, question, preferences):
    """Només la pregunta: l'ajuda es mostra si l'usuari falla o escriu 'help'."""
    io.say(f"\n[{index}/{total}] {question_text(question, preferences)}", kind='question')


def slot_name(data, key):
    """Nom amb què el sistema es refereix a una pregunta: 'the budget', 'the area'..."""
    return data['reactions']['slots'][key]


# --- Comptador de coincidències (bloc 5) ---

def count_text(data, n):
    words = data['reactions']['count']
    return words['one'] if n == 1 else words['many'].format(n=n)


def print_count_start(io, data, count):
    react(io, data, 'count_start', count=count_text(data, count))


def print_count_update(io, data, before, after):
    """Després d'una resposta que filtra: 'That rules out 8 homes, so 12 homes still match.'"""
    if after == 1:
        react(io, data, 'count_one')
    elif after <= FEW_MATCHES:
        react(io, data, 'count_few', count=count_text(data, after))
    else:
        react(io, data, 'count_update', count=count_text(data, after), removed=count_text(data, before - after))


def format_number(value):
    """300000 -> '300,000'; 2.0 -> '2'; 1300.5 -> '1,300.5'."""
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}".rstrip("0")


def sum_confirmation(question, result):
    """'So that's 2 bedrooms in total, is that right?' (iteració 3: sense el desglossament "(1 + 1)")."""
    return pick(question['confirm_sum'], f"confirm_sum:{question['answer_key']}").format(
        total=format_number(sum(result.parts)))


def print_help(io, help_lines):
    for line in help_lines:
        io.say(f"   {line}", kind='help')


# --- Reaccions (bloc 4): cada situació té una llista de formulacions al JSON ---

# Funció de cada reacció a la interfície (io_adapter li dona el format); per defecte, 'system'.
REACTION_KINDS = {
    **dict.fromkeys(['no_matches', 'out_of_range', 'no_value_matches', 'implausible_rent', 'confirm_exit',
                     'offer_summary', 'did_you_mean', 'which_one', 'rent_or_buy'], 'warning'),
    **dict.fromkeys(['not_understood', 'empty', 'explain_again', 'several_numbers', 'yes_no_expected',
                     'explore_unclear', 'correction_unclear', 'explore_no_id'], 'error'),
    **dict.fromkeys(['offer_skip', 'show_me_hint', 'help', 'explore_menu', 'explore_again', 'nothing_to_explore',
                     'which_change', 'explore_last', 'explore_first', 'correction_not_yet',
                     'correction_nothing_back'], 'hint'),
    **dict.fromkeys(['count_start', 'count_update', 'count_few', 'count_one', 'count_more'], 'count'),
    **dict.fromkeys(['zones_available', 'zones_single'], 'help'),  # discret: disponible però sense destacar
}

def reaction(data, case, **fields):
    text = pick(data['reactions'][case], case).format(**fields)
    return text[:1].upper() + text[1:]  # "{value} looks like..." pot començar en minúscula


def react(io, data, case, **fields):
    io.say(reaction(data, case, **fields), kind=REACTION_KINDS.get(case, 'system'))


def react_to_answer(io, data, question, value, described=None):
    """Reacció a una resposta acceptada, com faria un agent:

    - 'any' -> "No problem, I won't filter by that."
    - valor amb comentari propi al JSON -> "Gràcia, lovely choice: ..." (ja nomena el valor);
    - valor interpretat (`described`) -> confirmació implícita "Got it: at least 3 bedrooms.";
    - si no -> acusament breu ("Perfect.").
    """
    if value == ANY:
        react(io, data, 'acknowledge_any')
        return
    single = value[0] if isinstance(value, list) and len(value) == 1 else value
    comments = data['comments'].get(question['answer_key'], {})
    if isinstance(single, str) and single in comments:
        io.say(pick(comments[single], f"{question['answer_key']}:{single}"), kind='system')
    elif described:
        react(io, data, 'understood', value=described)
    else:
        react(io, data, 'acknowledge')


def describe_range(data, question, value_range, operation=None, with_label=False):
    """Range -> 'at least 3 bedrooms', 'between 200,000 and 300,000 euros', 'floor 2 or higher'."""
    templates = question.get('describe') or data['reactions']['range']
    unit = question.get('unit') or question.get('unit_by_type', {}).get(operation, "euros")
    low, high = value_range
    if low is not None and high is not None:
        case = 'exact' if low == high else 'between'
    else:
        case = 'min' if low is not None else 'max'
    if case != 'between' and (low if low is not None else high) == 1:
        unit = question.get('unit_one', unit)  # "at least 1 bedroom"
    fields = {"min": format_number(low) if low is not None else "",
              "max": format_number(high) if high is not None else "", "unit": unit}
    text = templates[case].format(**fields).strip()
    if with_label and operation:
        text += f" ({data['reactions']['labels'][operation]})"
    return text


def describe_value(data, value):
    """Valor d'opcions -> text: 'buying', 'Ciutat Vella and Sant Martí', 'flat or duplex'."""
    labels = data['reactions']['labels']
    if isinstance(value, list):
        names = _compress_cities(data['houses'], value) if value[0] in {h['location'] for h in data['houses']} \
            else [labels.get(v, v) for v in value]
        return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"
    return labels.get(value, value)


def _compress_cities(houses, locations):
    """Si hi són tots els districtes d'una ciutat, 'all of Barcelona' en lloc dels 10 noms."""
    by_city = {}
    for house in houses:
        by_city.setdefault(house['city'], set()).add(house['location'])
    names, pending = [], list(locations)
    for city, districts in sorted(by_city.items()):
        if len(districts) > 1 and districts <= set(pending):
            names.append(f"all of {city}")
            pending = [p for p in pending if p not in districts]
    return names + pending


def describe_options(data, values):
    """Candidats d'una resposta ambigua -> 'buying or renting'."""
    labels = data['reactions']['labels']
    names = [labels.get(v, v) for v in values]
    return f"{', '.join(names[:-1])} or {names[-1]}"


def _join(items, conjunction="and"):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {conjunction} {items[-1]}"


def summarize(data, preferences):
    """Microplanificació del resum: agrega totes les preferències en una sola descripció.

    "a flat to rent in Gràcia, up to 1,200 euros a month, on floor 2 or higher,
     in good condition, with at least 2 bedrooms, a terrace and an elevator"
    Retorna None si no hi ha cap preferència.
    """
    words = data['summary']
    questions = {q['answer_key']: q for q in data['questions']}
    given = {k: v for k, v in preferences.items() if v != ANY}
    if not given:
        return None

    types = given.get('property_type', [ANY])
    head = [_join((words['property'][t] for t in types), "or")]
    if given.get('type') in words['operation']:
        head.append(words['operation'][given['type']])
    if 'location' in given:
        head.append(f"in {describe_value(data, given['location'])}")

    clauses = []
    price = given.get('price')
    if isinstance(price, dict):
        parts = [describe_range(data, questions['price'], r, op, with_label=True)
                 for op, r in price.items() if r != ANY]
        if parts:
            clauses.append(_join(parts, "or"))
    elif price is not None:
        clauses.append(describe_range(data, questions['price'], price, given.get('type')))
    if 'floor' in given:
        clauses.append(f"on {describe_range(data, questions['floor'], given['floor'])}")
    if 'condition' in given:
        clauses.append(_join((words['condition'][c] for c in given['condition']), "or"))
    if given.get('shared') == 'No':
        clauses.append(words['not_shared'])

    extras = [describe_range(data, questions[k], given[k]) for k in ('bedrooms', 'bathrooms', 'square_meters')
              if k in given]
    extras += [phrase for key, phrase in words['features'].items() if given.get(key) == 'Yes']
    if extras:
        clauses.append(f"with {_join(extras)}")
    return ", ".join([" ".join(head)] + clauses)


def print_recap(io, data, preferences, case='intro'):
    """case: 'intro' (conversa completa) o 'intro_early' ("show me"). En sortir amb 'quit' no hi ha resum."""
    summary = summarize(data, preferences)
    if summary:
        io.say("\n" + pick(data['summary'][case], f"summary:{case}").format(summary=summary), kind='recap')


def describe_answer(data, question, value, preferences):
    """Valor desat d'una pregunta, en text: 'buying', 'Gràcia', 'up to 900 euros a month', 'no preference'."""
    if value == ANY:
        return data['reactions']['labels']['any']
    if isinstance(value, dict):  # pressupost amb tipus 'any'
        parts = [describe_range(data, question, r, op, with_label=True) for op, r in value.items() if r != ANY]
        return _join(parts, "or") or data['reactions']['labels']['any']
    if isinstance(value, tuple):  # Range
        operation = preferences.get('type') if preferences.get('type') in ('rent', 'sale') else None
        return describe_range(data, question, value, operation)
    return describe_value(data, value)


def _ordinal(n):
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 11 -> '11th'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _count(words, n):
    return words['one'] if n == 1 else words['many'].format(n=n)


def describe_house(data, house):
    """Fitxa en llenguatge natural (iteració 3). Microplanificació: les 17 dades s'agrupen en frases
    per temes en un ordre fix: què és, on i quant costa; distribució i estat; extres; condicions.
    Res no es perd: els extres absents queden implícits en enumerar els presents (i, si no n'hi ha
    cap, es diu explícitament quins falten)."""
    words = data['house']
    kind = words['kinds'][house['property_type']]
    amount = format_number(to_number(house['price']))
    price = words['price_rent' if house['type'] == 'rent' else 'price_sale'].format(amount=amount)
    location = format_location(house)
    if house['shared'] == 'Yes':
        title = words['title_shared'].format(kind=kind, location=location, price=price)
    else:
        title = words['title'].format(kind=kind, operation=words['operation'][house['type']],
                                      location=location, price=price)
    sentences = [title[:1].upper() + title[1:]]

    working = house['property_type'] in ('office', 'premises')  # oficines i locals: "rooms", no "bedrooms"
    rooms = _count(words['rooms_work' if working else 'rooms'], int(to_number(house['bedrooms'])))
    baths = _count(words['baths'], int(to_number(house['bathrooms'])))
    floor = int(to_number(house['floor']))
    if house['property_type'] in ('house', 'chalet'):
        floor_text = ""  # la planta d'una casa no aporta res
    else:
        floor_text = words['ground_floor'] if floor == 0 else words['floor'].format(ordinal=_ordinal(floor))
    sentences.append(words['layout'].format(rooms=rooms, baths=baths, size=house['square_meters'],
                                            floor=floor_text,
                                            condition=data['summary']['condition'][house['condition']]))

    features = data['summary']['features']
    extras = [key for key in ('elevator', 'terrace', 'garden', 'parking', 'furnished') if house[key] == 'Yes']
    if extras:
        sentences.append(words['with'].format(features=_join(features[k] for k in extras)))
    else:
        missing = ['elevator', 'terrace', 'parking'] + (['garden'] if house['property_type'] in ('house', 'chalet')
                                                        else [])
        sentences.append(words['without'].format(features=_join((features[k] for k in missing), "or")))

    if house['type'] == 'rent':  # en una compra, les mascotes són decisió del propietari
        sentences.append(words['pets_yes' if house['pets'] == 'Yes' else 'pets_no'])
    if house['commercial_use'] == 'Yes':
        sentences.append(words['commercial'])
    return sentences


def print_house(io, data, house, header=None):
    """Fitxa d'una vivenda en llenguatge natural, precedida d'una línia en blanc que la separa de
    l'anterior. `header`: línia just abans (posició i número, i què falla en una casi coincidència)."""
    io.say("")
    if header:
        io.say(header, kind='house_header')
    io.say("  " + " ".join(describe_house(data, house)), kind='info')  # la consola l'ajusta a l'amplada


# --- Resultats (iteració 3): resum amb una línia per vivenda + exploració ('all', 'next', un número) ---

def price_text(data, house):
    amount = format_number(to_number(house['price']))
    return f"{amount} {data['results']['per_month']}" if house['type'] == 'rent' else f"{amount} euros"


def _failed_text(data, failed):
    return _join((slot_name(data, key) for key in failed), "and")


def house_line(data, house, failed=None):
    """'#32 · flat in Gràcia · 575 euros/month' (i, en una casi coincidència, què falla)."""
    kind = data['house']['kinds'][house['property_type']]
    if house['shared'] == 'Yes':
        kind = f"room in a shared {kind}"
    line = f"  #{house['id']} · {kind} in {house['location']} · {price_text(data, house)}"
    if failed:
        line += " · " + data['results']['near_short'].format(slots=_failed_text(data, failed))
    return line


def print_results_overview(io, data, suitable_houses, near=()):
    """Resum dels resultats (ja ordenats per recommender.rank_houses), una línia per vivenda; si n'hi
    ha de lloguer i de compra, s'agrupen. Sense resultats: les casi coincidències (`near`: parelles
    (vivenda, criteris fallats)) o, si no n'hi ha, que no s'ha trobat res. Les fitxes es veuen a demanda."""
    results = data['results']
    if suitable_houses:
        n = len(suitable_houses)
        count = results['one'] if n == 1 else results['many'].format(n=n)
        io.say("\n" + pick(results['found'], 'results:found').format(count=count), kind='results')
        if n > 1:
            mixed = len({h['type'] for h in suitable_houses}) > 1
            io.say(pick(results['sorted_mixed' if mixed else 'sorted'], 'results:sorted'), kind='help')
    elif near:
        io.say("\n" + pick(results['near_intro'], 'results:near_intro'), kind='warning')
    else:
        io.say("\n" + pick(results['none'], 'results:none'), kind='warning')
        return
    _print_lines(io, data, suitable_houses, near)


def _print_lines(io, data, suitable_houses, near):
    """Una línia per vivenda ('#32 · flat in Gràcia · 575 euros/month'), amb capçaleres de grup si hi ha
    lloguer i compra; en les casi coincidències, què falla."""
    if suitable_houses:
        mixed = len({h['type'] for h in suitable_houses}) > 1
        group = None
        for house in suitable_houses:
            if mixed and house['type'] != group:
                group = house['type']
                io.say(data['results']['group'][group], kind='results')
            io.say(house_line(data, house), kind='item')
    else:
        for house, failed in near:
            io.say(house_line(data, house, failed), kind='item')


def print_results_list(io, data, suitable_houses, near=()):
    """Després de mostrar una fitxa: la llista de resultats de nou, per tenir els números a mà."""
    io.say("\n" + data['results']['list_again'], kind='results')
    _print_lines(io, data, suitable_houses, near)


def print_result(io, data, items, index, failed=None):
    """Fitxa d'un resultat amb la seva posició ('Home 2 of 13:') i, si és casi coincidència, què falla."""
    header = data['results']['position'].format(position=index + 1, total=len(items), id=items[index]['id'])
    if failed:
        header += " · " + pick(data['results']['near_reason'], 'results:near_reason').format(
            slots=_failed_text(data, failed))
    print_house(io, data, items[index], header=header)


def print_all_results(io, data, items, failures):
    """'all': totes les fitxes, amb capçaleres de grup si hi ha lloguer i compra."""
    mixed = len({h['type'] for h in items}) > 1
    group = None
    for index, house in enumerate(items):
        if mixed and house['type'] != group:
            group = house['type']
            io.say(f"\n{data['results']['group'][group]}", kind='results')
        print_result(io, data, items, index, failures.get(house['id']))
