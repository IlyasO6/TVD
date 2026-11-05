"""Comprensió de respostes numèriques (bloc 3): diners, rangs, modificadors i sumes.

Flux de `parse(answer, key, house_type)`:
  1. _tokens(): text plegat (minúscules, sense accents) conservant separadors de milers/decimals
     ("1.300", "10,000", "1,5"), símbols útils (+ < > ~ -) i límits de clàusula ('|').
  2. _quantities(): extreu quantitats -> xifres ("10.000", "1.5k"), paraules ("thirteen hundred",
     "dos mil quinientos", "vint-i-cinc"), escales ("k", "mil", "thousand", "million") i, segons la
     pregunta, ordinals/planta baixa (planta) o articles ("a big bedroom") (habitacions).
  3. Es decideix el significat, per ordre:
     a) rang explícit: "between 2 and 3", "2-3", "de 2 a 3", "2 or 3", "200 to 300k";
     b) un mínim i un màxim: "at least 2 and at most 4";
     c) habitacions/banys: suma de quantitats coordinades ("1 big and 1 small bedroom" -> 2),
        que el gestor del diàleg haurà de confirmar;
     d) una sola quantitat amb el seu modificador (mínim, màxim, aproximat, exacte) o, si no en té,
        el sentit per defecte de la pregunta (pressupost = màxim; la resta = mínim).
  Retorna NumericAnswer(range=Range(min, max), parts=quantitats sumades), NumericAnswer(None,
  candidates=...) si hi ha diversos números sense relació, o None si no s'entén.
"""

import re
from typing import NamedTuple, Optional

from . import lexicon
from .config import (APPROX_MARGINS, DEFAULT_NUMERIC_MODE, INTEGER_KEYS, PURCHASE_SCALE_FROM, ROOM_SUM_KEYS,
                     SALE_THOUSANDS_BELOW)
from .nlu import CLAUSE_SEP, fold, normalize


class Range(NamedTuple):
    min: Optional[float] = None
    max: Optional[float] = None

    def __contains__(self, number):
        return (self.min is None or number >= self.min) and (self.max is None or number <= self.max)


class NumericAnswer(NamedTuple):
    range: Optional[Range]
    parts: tuple = ()       # quantitats sumades (habitacions/banys); buit si no n'hi ha hagut suma
    candidates: tuple = ()  # diversos números sense relació clara (range = None): cal aclarir-ho


class Quantity(NamedTuple):
    value: float
    start: int
    end: int
    scale: float  # escala escrita explícitament ("k", "mil"...), 1 si no n'hi ha


# --- Tokenització ---

def _tokens(text):
    text = fold(text)
    text = re.sub(r"(?<=\d)\.(?=\d)", "§", text)          # protegeix separadors dins de xifres
    text = re.sub(r"(?<=\d),(?=\d)", "¶", text)
    text = re.sub(r"(?<=[\dkm])\s*-\s*(?=\d)", " - ", text)  # "2-3", "200k-300k" -> rang
    text = re.sub(r"(?<=\d)(?=[a-z])", " ", text)           # "250k" -> "250 k", "3rd" -> "3 rd"
    text = re.sub(r"[,;!?]", f" {CLAUSE_SEP} ", text)
    text = re.sub(r"([+<>~])", r" \1 ", text)
    text = re.sub(r"(?<! )-|-(?! )", " ", text)             # guions dins de paraules ("vint-i-cinc")
    text = re.sub(r"[^a-z0-9§¶|+<>~ -]+", " ", text)
    text = text.replace("§", ".").replace("¶", ",")
    tokens = []
    for token in text.split():
        if token in {".", ","} or (token == CLAUSE_SEP and (not tokens or tokens[-1] == CLAUSE_SEP)):
            continue
        tokens.append(token)
    while tokens and tokens[-1] == CLAUSE_SEP:
        tokens.pop()
    return tokens


def _phrases(items):
    """Formes del lèxic tokenitzades igual que l'entrada, de més llarga a més curta.

    Un símbol sol ('-') es perdria en tokenitzar-lo fora de context: es conserva tal qual.
    """
    return sorted({tuple(_tokens(item) or [item]) for item in items}, key=len, reverse=True)


def _words(items):
    return {token for item in items for token in _tokens(item)}


_NUMBERS = {_tokens(word)[0]: value for word, value in lexicon.NUMBER_WORDS.items()}
_ORDINALS = {_tokens(word)[0]: value for word, value in lexicon.ORDINALS.items()}
_GROUND = _phrases(lexicon.GROUND_FLOOR)
_HUNDRED = _words(lexicon.HUNDRED_WORDS)
_THOUSAND = _words(lexicon.THOUSAND_WORDS)
_MILLION = _words(lexicon.MILLION_WORDS)
_CONNECT = _words(lexicon.NUMBER_CONNECTORS)
_MODIFIERS = sorted(((p, mode) for mode, items in lexicon.NUMERIC_MODIFIERS.items() for p in _phrases(items)),
                    key=lambda item: len(item[0]), reverse=True)
_RANGE_PREFIXES = _words(lexicon.RANGE_PREFIXES)
_RANGE_AND = set(_phrases(lexicon.RANGE_AND))
_RANGE_CONNECTORS = set(_phrases(lexicon.RANGE_CONNECTORS))
_SUM_CONNECTORS = _words(lexicon.SUM_CONNECTORS) | {CLAUSE_SEP}
_ROOM_ARTICLES = _words(lexicon.ROOM_ARTICLES)
_ROOM_NOUNS = {key: _phrases(items) for key, items in lexicon.ROOM_NOUNS.items()}
_OTHER_NOUNS = _phrases(lexicon.OTHER_NOUNS)
_SKIP = _words(lexicon.UNIT_WORDS) | {t for phrases in _ROOM_NOUNS.values() for p in phrases for t in p}
_NEGATIONS = {normalize(w) for w in lexicon.NEGATIONS}
_KEY_UNITS = {
    "price": _phrases(["euro", "euros", "eur", "e", "month", "mes"]),
    "square_meters": _phrases(["m2", "m", "meter", "meters", "metre", "metres", "square", "sq", "sqm"]),
    "floor": _phrases(["floor", "floors", "planta", "plantas"]),
}


# --- Quantitats ---

_GROUPED = re.compile(r"(\d{1,3}(?:([.,])\d{3})(?:\2\d{3})*)(?:([.,])(\d{1,2}))?")


def _parse_digits(token):
    """'10.000' / '10,000' -> 10000; '1.300,50' -> 1300.5; '1.5' / '1,5' -> 1.5; '250' -> 250."""
    match = _GROUPED.fullmatch(token)
    if match and (match.group(3) is None or match.group(3) != match.group(2)):
        value = float(re.sub(r"[.,]", "", match.group(1)))
        return value + (float("0." + match.group(4)) if match.group(4) else 0)
    if re.fullmatch(r"\d+(?:[.,]\d+)?", token):
        return float(token.replace(",", "."))
    return None


def _fits(current, value):
    """Una paraula-número es pot afegir a l'anterior? ('twenty' + 'five' sí; 'two' + 'three' no)."""
    if value >= 100:
        return current % 1000 == 0
    if value >= 10:
        return current % 100 == 0
    return current % 10 == 0


def _parse_words(tokens, i):
    """Paraules-número a partir de `i`: 'thirteen hundred', 'a thousand three hundred', 'dos mil'."""
    total = current = 0
    seen = False
    j = i
    while j < len(tokens):
        token = tokens[j]
        following = tokens[j + 1] if j + 1 < len(tokens) else None
        if token in _NUMBERS and (not seen or _fits(current, _NUMBERS[token])):
            current += _NUMBERS[token]
            seen = True
        elif not seen and token in {"a", "an"} and following in _HUNDRED | _THOUSAND | _MILLION:
            current, seen = 1, True
        elif not seen and token == "mil":
            total, seen = 1000, True
        elif seen and token in _HUNDRED:
            current = (current or 1) * 100
        elif seen and token in _THOUSAND:
            total, current = total + (current or 1) * 1000, 0
        elif seen and token in _MILLION:
            total, current = total + (current or 1) * 1_000_000, 0
        elif (seen and token in _CONNECT and following in _NUMBERS
              and _fits(current, _NUMBERS[following])):
            pass
        else:
            break
        j += 1
    return (total + current, j) if seen else (None, i)


def _match_at(tokens, position, phrases):
    for phrase in phrases:
        if tuple(tokens[position:position + len(phrase)]) == phrase:
            return phrase
    return None


def _is_noun(tokens, position):
    return any(_match_at(tokens, position, phrases) for phrases in [*_ROOM_NOUNS.values(), _OTHER_NOUNS])


def _quantities(tokens, key):
    rooms = key in ROOM_SUM_KEYS
    found = []
    i = 0
    while i < len(tokens):
        token = tokens[i]
        following = tokens[i + 1] if i + 1 < len(tokens) else None
        value, end = None, i
        if (digits := _parse_digits(token)) is not None:
            value, end = digits, i + 1
        elif key == "floor" and (ground := _match_at(tokens, i, _GROUND)):
            value, end = 0, i + len(ground)
        elif key == "floor" and token in _ORDINALS:
            value, end = _ORDINALS[token], i + 1
        elif rooms and token == "ones":
            pass
        elif rooms and token == "one" and found and _is_pronoun(tokens, found[-1].end, i):
            pass  # "a small one": 'one' substitueix el nom, no és una quantitat
        elif rooms and token in _ROOM_ARTICLES and following is not None and following not in _NUMBERS \
                and _parse_digits(following) is None and following not in _SUM_CONNECTORS:
            value, end = 1, i + 1
        elif token in {"un", "una"} and not rooms and following not in _THOUSAND | _MILLION and len(tokens) > 1:
            pass  # "un presupuesto de 300 mil": aquí 'un' és un article
        elif token in _NUMBERS or token in {"a", "an", "mil"}:
            value, end = _parse_words(tokens, i)
        if value is None:
            i += 1
            continue
        scale = 1
        if end < len(tokens):
            if tokens[end] in _THOUSAND:
                scale = 1000
            elif tokens[end] in _MILLION or (key == "price" and tokens[end] in lexicon.PRICE_ONLY_SCALES):
                scale = 1_000_000
            if scale > 1:
                end += 1
        found.append(Quantity(value * scale, i, end, scale))
        i = end
    return found


def _negated(tokens, quantity, lower):
    """'not the ground floor', 'no 3': negació com a molt 2 paraules abans, dins la clàusula."""
    for token in reversed(tokens[max(lower, quantity.start - 2):quantity.start]):
        if token == CLAUSE_SEP:
            return False
        if token in _NEGATIONS:
            return True
    return False


def _is_pronoun(tokens, previous_end, position):
    between = tokens[previous_end:position]
    return len(between) <= 2 and not any(
        t in _SUM_CONNECTORS or _is_noun(tokens, previous_end + k) for k, t in enumerate(between))


# --- Modificadors ---

def _prefix_mode(tokens, quantity, lower):
    """Modificador just abans de la quantitat (com a molt 2 paraules entremig, mateixa clàusula)."""
    for end in range(quantity.start, max(lower, quantity.start - 3) - 1, -1):
        if CLAUSE_SEP in tokens[end:quantity.start]:
            return None
        for phrase, mode in _MODIFIERS:
            start = end - len(phrase)
            if start >= lower and tuple(tokens[start:end]) == phrase:
                return mode
    return None


def _postfix_mode(tokens, quantity, upper):
    """Modificador just després de la quantitat, saltant unitats ('200k euros max', '3 bedrooms or more')."""
    position = quantity.end
    skipped = 0
    while position < upper and tokens[position] in _SKIP and skipped < 2:
        position, skipped = position + 1, skipped + 1
    for phrase, mode in _MODIFIERS:
        if position + len(phrase) <= upper and tuple(tokens[position:position + len(phrase)]) == phrase:
            return mode
    return None


def _bound(value, mode, key):
    integer = key in INTEGER_KEYS and float(value).is_integer()
    if mode == "min":
        return Range(value, None)
    if mode == "min_strict":
        return Range(value + 1 if integer else value, None)
    if mode == "max":
        return Range(None, value)
    if mode == "max_strict":
        return Range(None, value - 1 if integer else value)
    if mode == "exact":
        return Range(value, value)
    kind, below, above = APPROX_MARGINS[key]
    if kind == "abs":
        return Range(max(0, value - below), value + above)
    return Range(value * (1 - below), value * (1 + above))


# --- Interpretació ---

def _attachment(tokens, quantity, upper, key):
    """'right' si el nom que segueix la quantitat és el de la pregunta, 'other' si és un altre, o None."""
    right = _ROOM_NOUNS[key] if key in ROOM_SUM_KEYS else _KEY_UNITS.get(key, [])
    other = [p for p in _OTHER_NOUNS + [p for k, ps in _ROOM_NOUNS.items() if k != key for p in ps]
             if p not in right]
    for position in range(quantity.end, upper):
        if tokens[position] == CLAUSE_SEP:
            return None
        found = _match_at(tokens, position, sorted(right + other, key=len, reverse=True))
        if found:
            return "right" if found in right else "other"
        if tokens[position] in _SUM_CONNECTORS:
            return None
    return None


def _explicit_range(tokens, quantities):
    for a, b in zip(quantities, quantities[1:]):
        between = tuple(t for t in tokens[a.end:b.start] if t not in _SKIP)
        prefixed = any(t in _RANGE_PREFIXES for t in tokens[max(0, a.start - 2):a.start])
        if between in _RANGE_CONNECTORS or (between in _RANGE_AND and prefixed):
            low = a.value * b.scale if b.scale > 1 and a.scale == 1 and a.value * b.scale <= b.value else a.value
            return Range(min(low, b.value), max(low, b.value))
    return None


def _chains(tokens, quantities):
    """Agrupa quantitats consecutives unides per un connector de suma ('and', 'y', '+', ',')."""
    chains = []
    for quantity in quantities:
        if chains and any(t in _SUM_CONNECTORS for t in tokens[chains[-1][-1].end:quantity.start]):
            chains[-1].append(quantity)
        else:
            chains.append([quantity])
    return chains


def operation_for(value_range):
    """Amb tipus 'any': un pressupost de "300k" és de compra i un de "1.200", de lloguer.

    None si no es pot saber ("800": 800 euros al mes o 800.000 per comprar?).
    """
    bounds = [b for b in value_range if b is not None]
    if all(b >= PURCHASE_SCALE_FROM for b in bounds):
        return "sale"
    if all(SALE_THOUSANDS_BELOW <= b < PURCHASE_SCALE_FROM for b in bounds):
        return "rent"
    return None


def _for_sale(value_range, house_type, key):
    """Compra: "250" vol dir 250.000 euros (ningú compra un habitatge per 250 euros)."""
    if key != "price" or house_type != "sale":
        return value_range
    scale = lambda b: b * 1000 if b is not None and b < SALE_THOUSANDS_BELOW else b
    return Range(scale(value_range.min), scale(value_range.max))


def parse(answer, key, house_type=None):
    tokens = _tokens(answer)
    quantities = _quantities(tokens, key)
    if not quantities:
        return None

    explicit = _explicit_range(tokens, quantities)
    if explicit:
        return NumericAnswer(_for_sale(explicit, house_type, key))

    bounds = {}
    candidates = []
    for n, quantity in enumerate(quantities):
        lower = quantities[n - 1].end if n else 0
        upper = quantities[n + 1].start if n + 1 < len(quantities) else len(tokens)
        attached = _attachment(tokens, quantity, upper, key)
        if attached == "other":
            continue
        if _negated(tokens, quantity, lower):
            if key == "floor" and quantity.value == 0:  # "not the ground floor" -> des de la 1a
                return NumericAnswer(Range(1, None))
            continue
        mode = _prefix_mode(tokens, quantity, lower) or _postfix_mode(tokens, quantity, upper)
        bounds[quantity] = (mode, attached)
        candidates.append(quantity)
    if not candidates:
        return None

    minima = [q for q in candidates if bounds[q][0] in ("min", "min_strict")]
    maxima = [q for q in candidates if bounds[q][0] in ("max", "max_strict")]
    if len(minima) == 1 and len(maxima) == 1:
        low = _bound(minima[0].value, bounds[minima[0]][0], key).min
        high = _bound(maxima[0].value, bounds[maxima[0]][0], key).max
        return NumericAnswer(_for_sale(Range(low, high), house_type, key))

    if key in ROOM_SUM_KEYS and len(candidates) > 1:
        chains = _chains(tokens, candidates)
        with_noun = [c for c in chains if any(bounds[q][1] == "right" for q in c)]
        counted = [q for c in with_noun for q in c] if with_noun else max(chains, key=len)
        if len(counted) > 1:
            total = sum(q.value for q in counted)
            mode = bounds[counted[0]][0] or DEFAULT_NUMERIC_MODE[key]
            return NumericAnswer(_bound(total, mode, key), tuple(q.value for q in counted))
        candidates = counted

    if len({q.value for q in candidates}) > 1:  # diverses quantitats sense relació clara: ambigu
        return NumericAnswer(None, candidates=tuple(dict.fromkeys(q.value for q in candidates)))
    quantity = candidates[0]
    mode = bounds[quantity][0] or DEFAULT_NUMERIC_MODE[key]
    return NumericAnswer(_for_sale(_bound(quantity.value, mode, key), house_type, key))
