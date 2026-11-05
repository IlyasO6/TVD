"""Detecció de correccions de respostes anteriors (iteració 3).

Tres maneres de corregir, sempre explícites (sense marcador no hi ha correcció, perquè una resposta
normal no s'ha de confondre mai amb un canvi):
  - "back" / "go back"  -> tornar a la pregunta anterior;
  - marcador de canvi + nom de la pregunta (+ valor nou opcional):
        "change the budget", "change the area to Gràcia", "cambiar la zona";
  - marcador de correcció + valor: "actually, Gràcia", "I meant a house". El valor s'atribueix a la
    pregunta ja resposta a la qual correspon, si n'hi ha exactament una (no s'intenta amb números ni
    amb Sí/No, que serien ambigus: "actually 3" pot ser habitacions o banys).
Aquest mòdul només detecta; el gestor del diàleg aplica la correcció.
"""

from . import lexicon, nlu
from .config import MULTI_SELECT_KEYS


class Correction(Exception):
    """kind: 'back', 'change', 'value', 'unclear' (vol canviar però no diu què), 'not_yet' (encara no
    preguntat) o 'nothing_back' ("back" a la primera pregunta)."""

    def __init__(self, kind, key=None, value_text=None):
        super().__init__(kind)
        self.kind, self.key, self.value_text = kind, key, value_text


def _tokens(text):
    return nlu.normalize(text).split()


def _longest_first(phrases):
    return sorted({tuple(_tokens(p)) for p in phrases if _tokens(p)}, key=len, reverse=True)


_SLOTS = sorted({(tuple(_tokens(p)), key) for key, names in lexicon.SLOT_NAMES.items() for p in names},
                key=lambda item: len(item[0]), reverse=True)
_CHANGE = _longest_first(lexicon.CHANGE_MARKERS)
_CORRECT = _longest_first(lexicon.CORRECTION_MARKERS)
_BACK = {nlu.normalize(c) for c in lexicon.BACK_COMMANDS}
_FILLERS = {t for f in lexicon.VALUE_FILLERS for t in _tokens(f)} | {nlu.CLAUSE_SEP}


def _after_marker(tokens, markers):
    for marker in markers:
        if tuple(tokens[:len(marker)]) == marker:
            rest = tokens[len(marker):]
            return rest[1:] if rest[:1] == [nlu.CLAUSE_SEP] else rest
    return None


def _find_slot(tokens):
    """Primera menció d'una pregunta: (clau, inici, final) o None."""
    for start in range(len(tokens)):
        for phrase, key in _SLOTS:
            if tuple(tokens[start:start + len(phrase)]) == phrase:
                return key, start, start + len(phrase)
    return None


def _strip_fillers(tokens):
    while tokens and tokens[0] in _FILLERS:
        tokens = tokens[1:]
    while tokens and tokens[-1] in _FILLERS:
        tokens = tokens[:-1]
    return tokens


def strip_marker(answer):
    """'actually, Gràcia' -> 'gracia'; sense marcador, la resposta tal qual."""
    tokens = _tokens(answer)
    rest = _after_marker(tokens, _CHANGE)
    if rest is None:
        rest = _after_marker(tokens, _CORRECT)
    return " ".join(rest) if rest is not None else answer


def detect(data, preferences, answer_order, question, answer, vocabularies):
    """Correction si `answer` (resposta a `question`) corregeix una resposta anterior; si no, None.

    `question` és None després dels resultats ("Would you like to change anything?")."""
    tokens = _tokens(answer)
    current = question['answer_key'] if question else None
    if not tokens:
        return None
    if " ".join(tokens) in _BACK:
        # La pregunta anterior en l'ordre del qüestionari (no la darrera modificada); al final, la darrera.
        order = [q['answer_key'] for q in data['questions']]
        before = order[:order.index(current)] if current else order
        previous = [key for key in before if key in preferences]
        return Correction('back', previous[-1]) if previous else Correction('nothing_back')

    rest = _after_marker(tokens, _CHANGE)
    explicit = rest is not None
    if not explicit:
        rest = _after_marker(tokens, _CORRECT)
        if rest is None:
            return None

    slot = _find_slot(rest)
    if slot:
        key, _, end = slot
        if key == current:
            return None  # "I mean, a budget of 900" a la pregunta del pressupost: és la resposta
        if key not in preferences:
            return Correction('not_yet', key)
        value = _strip_fillers(rest[end:])
        return Correction('change', key, " ".join(value) or None)
    if explicit:
        return Correction('unclear')

    # "actually, Gràcia": si respon la pregunta actual, és una resposta normal; si no, es busca a quina
    # pregunta anterior (d'opcions, no Sí/No) correspon el valor, i ha de ser-ne exactament una.
    text = " ".join(_strip_fillers(rest))
    if not text:
        return None
    if current in vocabularies and nlu.analyse(vocabularies[current], text, current in MULTI_SELECT_KEYS).value:
        return None
    matches = []
    for key in answer_order:
        if key == current or key not in vocabularies or set().union(*vocabularies[key].values()) <= {"Yes", "No"}:
            continue
        result = nlu.analyse(vocabularies[key], text, key in MULTI_SELECT_KEYS)
        if result.value is not None and not result.approximate:
            matches.append(key)
    return Correction('value', matches[0], text) if len(matches) == 1 else None
