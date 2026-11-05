"""Lògica de filtratge (backend).

Iteració 0: `find_suitable_houses` de l'Ex. 6.
Bloc 1: s'elimina el filtre d'ingressos (ja no es pregunta) i s'afegeix
`value_range` per mostrar a l'usuari els valors disponibles.
Bloc 2: filtres de mascotes i pis compartit; la ubicació accepta districte o ciutat.
Bloc 3: les respostes de selecció múltiple són llistes de valors acceptats (ubicació,
tipus d'immoble, estat) i les numèriques són rangs (mínim/màxim).
Bloc 5: `count_matches` per al comptador de coincidències de cada pas del diàleg.
Iteració 3: `rank_houses` ordena els resultats per operació i preu; `near_misses` dona les
"casi coincidències" quan no hi ha cap resultat.
"""

from .config import (ANY, NEAR_MISS_LIMIT, NEAR_MISS_MAX_FAILURES, NON_RELAXABLE, OPT_IN_FILTERS,
                     YES_ONLY_FILTERS)
from .numeric import Range


def initialize_available_options(house_data, available_options):
    for house in house_data['houses']:
        for key, value in house.items():
            available_options.setdefault(key, set()).add(value)


def to_number(value):
    """Converteix '2000' o '2k' en número."""
    value = str(value).lower()
    if value.endswith('k'):
        return float(value[:-1]) * 1000
    return float(value)


def value_range(houses, key):
    """Valors mínim i màxim de `key` entre `houses`, en el format original del JSON (p.ex. '100k')."""
    values = sorted((house[key] for house in houses), key=to_number)
    return values[0], values[-1]


def rank_houses(houses):
    """Iteració 3: ordre de presentació. Primer els lloguers i després les vendes (escales de preu
    diferents) i, dins de cada grup, del més barat al més car; a igual preu, per id."""
    order = {'rent': 0, 'sale': 1}
    return sorted(houses, key=lambda h: (order[h['type']], to_number(h['price']), h['id']))


def count_matches(data, user_preferences):
    """Comptador del bloc 5: quantes vivendes compleixen les preferències donades fins ara."""
    return len(find_suitable_houses(data, user_preferences))


def satisfies(house, key, value):
    """La vivenda compleix la preferència `key` = `value`? (Iteració 3: extret de find_suitable_houses
    per poder comptar quins criteris falla cada vivenda.)"""
    if isinstance(value, dict):
        # Pressupost amb tipus 'any': un rang per a lloguer i un altre per a compra.
        value = value.get(house['type'], ANY)
    if value == ANY:
        return True
    if isinstance(value, Range):
        # Pressupost, habitacions, banys, m2, planta: mínim i/o màxim.
        return to_number(house[key]) in value
    if isinstance(value, list):
        # Valors acceptats (ja expandits per l'NLU: ciutat, zones, exclusions...).
        return house[key] in value
    if key in OPT_IN_FILTERS:
        return not (value == 'No' and house[key] == 'Yes')
    if key in YES_ONLY_FILTERS:
        return value != 'Yes' or house[key] == value
    return house[key] == value


def failed_criteria(house, user_preferences):
    return [key for key, value in user_preferences.items() if not satisfies(house, key, value)]


def find_suitable_houses(data, user_preferences):
    return [house for house in data['houses'] if not failed_criteria(house, user_preferences)]


def near_misses(data, user_preferences):
    """Iteració 3: si no hi ha cap coincidència, les vivendes que fallen menys criteris (com a molt
    NEAR_MISS_MAX_FAILURES), amb els criteris que fallen. Els de NON_RELAXABLE no es relaxen mai
    (a qui vol llogar no li serveix una vivenda en venda). Ordenades per criteris fallats i després
    com els resultats normals; com a molt NEAR_MISS_LIMIT."""
    candidates = []
    for house in data['houses']:
        failed = failed_criteria(house, user_preferences)
        if failed and len(failed) <= NEAR_MISS_MAX_FAILURES and not set(failed) & set(NON_RELAXABLE):
            candidates.append((house, failed))
    if not candidates:
        return []
    fewest = min(len(failed) for _, failed in candidates)
    closest = [c for c in candidates if len(c[1]) == fewest]
    ranked = {house['id']: n for n, house in enumerate(rank_houses([house for house, _ in closest]))}
    return sorted(closest, key=lambda c: ranked[c[0]['id']])[:NEAR_MISS_LIMIT]
