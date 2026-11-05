"""Comprensió de les respostes d'opcions de l'usuari (NLU). Els números van a `numeric.py`.

Iteració 0: tokenització amb NLTK i extracció del primer token numèric.
Bloc 3: preprocessament robust (majúscules, accents, símbols, contraccions),
sinònims, zones geogràfiques, negació, exclusions ("except", "but", "menos")
i tolerància a errors tipogràfics.

Flux per a preguntes d'opcions:
  1. normalize(): text -> tokens en minúscules, sense accents ni símbols.
  2. build_vocabulary(): per a la pregunta, forma normalitzada -> conjunt de valors canònics
     (opcions del JSON + sinònims + ciutats + zones, de lexicon.py).
  3. interpret(): busca les formes dins la resposta (coincidència exacta per paraules,
     la més llarga guanya, es descarten les negades); si no n'hi ha cap, prova
     coincidència aproximada. Un sol valor -> resposta; diversos -> ambigu (None),
     excepte a les preguntes de selecció múltiple, on s'uneixen.
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import NamedTuple

from . import lexicon
from .config import (EXIT_COMMANDS, FUZZY_CUTOFF, FUZZY_MIN_LENGTH, HELP_COMMANDS, MIN_CONTAINED_LENGTH,
                     NEGATION_WINDOW, RESULTS_COMMANDS)

CLAUSE_SEP = "|"
_QUOTES = str.maketrans({"’": "'", "‘": "'", "´": "'", "`": "'", "·": ""})


def fold(text):
    """Minúscules, apòstrofs unificats, contraccions desplegades i sense accents (m² -> m2)."""
    text = str(text).casefold().translate(_QUOTES)
    text = text.replace("n't", " not")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize(text):
    """fold() + símbols eliminats.

    Les comes i signes de puntuació forts es conserven com a '|' (límit de clàusula),
    perquè una negació no afecti la clàusula següent ("no, rent" != "not rent").
    """
    text = fold(text)
    text = re.sub(r"[,;!?]", f" {CLAUSE_SEP} ", text)
    text = re.sub(r"[^a-z0-9|]+", " ", text)
    tokens = []
    for token in text.split():
        if token == CLAUSE_SEP and (not tokens or tokens[-1] == CLAUSE_SEP):
            continue
        tokens.append(token)
    while tokens and tokens[-1] == CLAUSE_SEP:
        tokens.pop()
    return " ".join(tokens)


# --- Comandes especials ---

_EXIT = {normalize(c) for c in EXIT_COMMANDS}
_ANY = {normalize(p) for p in lexicon.ANY_PHRASES}
_ANY_MULTIWORD = [p.split() for p in _ANY if len(p.split()) > 1]
_NEGATIONS = {normalize(w) for w in lexicon.NEGATIONS}
_EXCLUSIONS = sorted((normalize(p).split() for p in lexicon.EXCLUSION_MARKERS), key=len, reverse=True)


def is_exit(answer):
    return normalize(answer) in _EXIT


_HELP = {normalize(c) for c in HELP_COMMANDS} - {""}
_RESULTS = {normalize(c) for c in RESULTS_COMMANDS}


def is_help(answer):
    return answer.strip() == "?" or normalize(answer) in _HELP


def is_show_results(answer):
    return normalize(answer) in _RESULTS


def is_any(answer):
    text = normalize(answer)
    if text in _ANY:
        return True
    tokens = text.split()
    return any(_find(tokens, phrase) for phrase in _ANY_MULTIWORD)


def _exclusion_split(tokens):
    """(tokens abans, tokens després) del primer marcador d'exclusió, o None si no n'hi ha."""
    for start in range(len(tokens)):
        for marker in _EXCLUSIONS:
            if tokens[start:start + len(marker)] == marker:
                return tokens[:start], tokens[start + len(marker):]
    return None


def has_exclusion(answer):
    return _exclusion_split(normalize(answer).split()) is not None


# --- Vocabulari per pregunta ---

def _zone_members(members, houses):
    if isinstance(members, dict) and "city" in members:
        return {h['location'] for h in houses if h['city'] == members["city"]}
    if isinstance(members, dict) and "not_city" in members:
        return {h['location'] for h in houses if h['city'] != members["not_city"]}
    present = {h['location'] for h in houses}
    return set(members) & present


def build_vocabulary(key, options, houses):
    """Diccionari forma normalitzada -> conjunt de valors canònics per a la pregunta `key`."""
    vocabulary = {}

    def add(phrase, values):
        if values:
            vocabulary.setdefault(normalize(phrase), set()).update(values)

    if key == 'location':
        by_city = {}
        for house in houses:
            by_city.setdefault(house['city'], set()).add(house['location'])
        for location in {h['location'] for h in houses}:
            add(location, {location})
            for phrase in lexicon.LOCATIONS.get(location, []):
                add(phrase, {location})
        for city, locations in by_city.items():
            if locations != {city}:
                add(city, locations)
                for phrase in lexicon.CITIES.get(city, []):
                    add(phrase, locations)
        for zone in lexicon.ZONES.values():
            members = _zone_members(zone["members"], houses)
            for phrase in zone["phrases"]:
                add(phrase, members)
        return vocabulary

    for option in options:
        add(option, {option})
    synonyms = lexicon.YES_NO if set(options) == {"Yes", "No"} else lexicon.SYNONYMS.get(key, {})
    for canonical, phrases in synonyms.items():
        if canonical in options:
            for phrase in phrases:
                add(phrase, {canonical})
    return vocabulary


# --- Interpretació ---

def _find(tokens, phrase_tokens):
    """Posicions d'inici on `phrase_tokens` apareix seguit dins `tokens`."""
    n = len(phrase_tokens)
    return [i for i in range(len(tokens) - n + 1) if tokens[i:i + n] == phrase_tokens]


def _negated(tokens, start, phrase_tokens):
    if phrase_tokens[0] in _NEGATIONS:  # la forma ja és negativa ("not needed", "no thanks")
        return False
    for token in reversed(tokens[max(0, start - NEGATION_WINDOW):start]):
        if token == CLAUSE_SEP:
            return False
        if token in _NEGATIONS:
            return True
    return False


def _drop_contained(matches):
    """Si una coincidència queda dins d'una altra de més llarga, guanya la llarga."""
    return [m for m in matches
            if not any(o[0] <= m[0] and m[1] <= o[1] and (o[1] - o[0]) > (m[1] - m[0]) for o in matches)]


def _exact_matches(vocabulary, tokens):
    matches = []
    for phrase, values in vocabulary.items():
        phrase_tokens = phrase.split()
        if not phrase_tokens:
            continue
        if len(phrase) < MIN_CONTAINED_LENGTH:
            if tokens == phrase_tokens:
                matches.append((0, len(tokens), values))
            continue
        for start in _find(tokens, phrase_tokens):
            if not _negated(tokens, start, phrase_tokens):
                matches.append((start, start + len(phrase_tokens), values))
    return _drop_contained(matches)


def _fuzzy_matches(vocabulary, tokens):
    """Coincidència aproximada per errors tipogràfics ('Barcleona', 'Eixampel', 'santacoloma')."""
    best = {}  # (inici, final) -> (similitud, valors)
    for phrase, values in vocabulary.items():
        compact = phrase.replace(" ", "")
        if len(compact) < FUZZY_MIN_LENGTH:
            continue
        phrase_tokens = phrase.split()
        negative_phrase = phrase_tokens[0] in _NEGATIONS
        k = len(phrase_tokens)
        matcher = SequenceMatcher(None, "", compact)  # la forma es preprocessa un sol cop
        for n in {max(1, k - 1), k, k + 1}:
            for start in range(len(tokens) - n + 1):
                gram = tokens[start:start + n]
                # Un tros que comença amb negació només pot aproximar una forma negativa,
                # i una forma positiva negada abans es descarta ("not renovatd").
                if (CLAUSE_SEP in gram or (gram[0] in _NEGATIONS) != negative_phrase
                        or _negated(tokens, start, phrase_tokens)):
                    continue
                matcher.set_seq1("".join(gram))
                # real_quick_ratio() i quick_ratio() són cotes superiors barates de ratio():
                # si ja no arriben al llindar, ratio() tampoc (mateix resultat, molt més ràpid).
                if matcher.real_quick_ratio() < FUZZY_CUTOFF or matcher.quick_ratio() < FUZZY_CUTOFF:
                    continue
                ratio = matcher.ratio()
                if ratio < FUZZY_CUTOFF:
                    continue
                span = (start, start + n)
                if span not in best or ratio > best[span][0]:
                    best[span] = (ratio, set(values))
                elif ratio == best[span][0]:
                    best[span][1].update(values)
    return _drop_contained([(s, e, values) for (s, e), (_, values) in best.items()])


class Interpretation(NamedTuple):
    """Resultat de l'NLU amb la informació que el gestor del diàleg necessita per reaccionar."""
    value: object = None        # valor canònic (o llista, si és múltiple); None si no s'entén o és ambigu
    candidates: tuple = ()      # selecció única ambigua: valors possibles ("buy or rent")
    approximate: bool = False   # només s'ha trobat per similitud (error tipogràfic) -> "Did you mean...?"
    literal: bool = False       # l'usuari ha escrit exactament l'opció -> no cal repetir-la


def _match(vocabulary, tokens, multiple):
    """(conjunt de valors, aproximat?) reconeguts a `tokens`."""
    exact = _exact_matches(vocabulary, tokens)
    matches = exact or _fuzzy_matches(vocabulary, tokens)
    sets = [values for _, _, values in matches]
    if not sets:
        return set(), False
    if multiple:
        # "Eixample, Barcelona" -> Eixample: si un conjunt conté un altre, es queda el més concret.
        sets = [s for s in sets if not any(other < s for other in sets)]
    return set().union(*sets), not exact


def _matched_values(vocabulary, tokens, multiple):
    """Conjunt de valors reconeguts a `tokens` (buit si no n'hi ha o, en selecció única, si és ambigu)."""
    values, _ = _match(vocabulary, tokens, multiple)
    return values if multiple or len(values) == 1 else set()


def _with_exclusion(vocabulary, tokens):
    """Selecció múltiple amb "except/but/menos...": (inclosos - exclosos), o None si no s'aplica."""
    split = _exclusion_split(tokens)
    if split is None:
        return None
    before, after = split
    excluded = _matched_values(vocabulary, [t for t in after if t not in _NEGATIONS], multiple=True)
    if not excluded:  # "Gràcia, but cheap": després del marcador no hi ha cap lloc -> no és una exclusió
        return None
    if not before or is_any(" ".join(before)):
        included = set().union(*vocabulary.values())
    else:
        included = _matched_values(vocabulary, before, multiple=True)
    return included - excluded


def analyse(vocabulary, answer, multiple=False):
    """Interpretation de `answer`: valor, candidats si és ambigu, si és aproximat i si és literal."""
    tokens = normalize(answer).split()
    if multiple:
        excluded = _with_exclusion(vocabulary, tokens)
        if excluded is not None:
            return Interpretation(sorted(excluded) or None)
    values, approximate = _match(vocabulary, tokens, multiple)
    if not values:
        return Interpretation()
    if not multiple and len(values) > 1:
        return Interpretation(candidates=tuple(sorted(values)), approximate=approximate)
    literal = len(values) == 1 and " ".join(tokens) == normalize(next(iter(values)))
    value = sorted(values) if multiple else next(iter(values))
    return Interpretation(value, approximate=approximate, literal=literal)


def interpret(vocabulary, answer, multiple=False):
    """Valor canònic de `answer` (o llista ordenada si `multiple`), o None si no s'entén o és ambigu."""
    return analyse(vocabulary, answer, multiple).value


def restrict(vocabulary, values):
    """Vocabulari limitat a `values` (per resoldre una pregunta de clarificació)."""
    restricted = {phrase: found & set(values) for phrase, found in vocabulary.items()}
    return {phrase: found for phrase, found in restricted.items() if found}
