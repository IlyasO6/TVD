"""Proves d'integració del sistema complet (estat al final de la iteració 2).

1. Consistència estàtica: dades, guió, lèxic i plantilles (cap variant aleatòria pot fallar en formatar-se).
2. Extrem a extrem amb un oracle independent: converses aleatòries (respostes escrites de maneres
   variades i formulacions del sistema a l'atzar); els resultats es comparen amb un filtre de referència
   escrit des de l'especificació, i es comproven invariants de cada transcripció.
3. Fuzzing d'anomalies: respostes estranyes a qualsevol punt (també a les confirmacions): cap excepció,
   cap bucle i la conversa sempre acaba amb el comiat.
4. Rendiment: una resposta llarga no reconeguda es processa en un temps raonable.

Totes les parts usen llavors fixes: els resultats són reproduïbles.
Execució:  python -m recomanador.tests.test_integracio
"""

import random
import re
import string
import time
import traceback
import unicodedata

from recomanador import lexicon, nlg, nlu
from recomanador.config import EXIT_COMMANDS, RESULTS_COMMANDS
from recomanador.data_loader import load_data
from recomanador.io_adapter import ScriptedIO
from recomanador.recommender import initialize_available_options, to_number
from recomanador.tests.common import run_case, run_suite

DATA = load_data()
HOUSES = DATA["houses"]
OPTIONS = {}
initialize_available_options(DATA, OPTIONS)
BCN = {h["location"] for h in HOUSES if h["city"] == "Barcelona"}
TOWNS = {h["location"] for h in HOUSES if h["city"] != "Barcelona"}
LOCATIONS = sorted(BCN | TOWNS)
YES_NO_KEYS = ["shared", "terrace", "elevator", "garden", "parking", "furnished", "pets", "commercial_use"]


# --- 1. Consistència estàtica ---------------------------------------------------------------

def _fields(template):
    return {f for _, f, _, _ in string.Formatter().parse(template) if f}


def check_static():
    errors = []
    # dades
    if [h["id"] for h in HOUSES] != list(range(1, len(HOUSES) + 1)):
        errors.append("ids no consecutius")
    for h in HOUSES:
        if h["type"] == "sale" and not h["price"].endswith("k"):
            errors.append(f"casa {h['id']}: preu de venda sense 'k'")
        if h["shared"] == "Yes" and h["type"] != "rent":
            errors.append(f"casa {h['id']}: compartida però no de lloguer")
        for key in YES_NO_KEYS:
            if h[key] not in ("Yes", "No"):
                errors.append(f"casa {h['id']}: {key}={h[key]!r}")
    # guió: condicions sobre valors existents i preguntes anteriors
    keys = [q["answer_key"] for q in DATA["questions"]]
    for q in DATA["questions"]:
        for key, allowed in q.get("ask_if", {}).items():
            if keys.index(key) > keys.index(q["answer_key"]) or not set(allowed) <= OPTIONS[key]:
                errors.append(f"ask_if incorrecte a {q['answer_key']}")
    # plantilles: els camps de cada variant han de ser els mateixos que els de la primera
    # (el codi passa sempre els de la situació; una variant amb un camp de més fallaria a l'atzar)
    groups = {f"reactions.{k}": v for k, v in DATA["reactions"].items() if isinstance(v, list)}
    groups.update({f"summary.{k}": DATA["summary"][k] for k in ("intro", "intro_early")})
    groups.update({f"results.{k}": DATA["results"][k] for k in ("found", "none")})
    groups.update({f"question.{q['answer_key']}": q["question"] for q in DATA["questions"]})
    allowed_extra = {"reactions.count_update": {"removed"}}  # el codi sempre passa 'removed'
    for name, variants in groups.items():
        base = _fields(variants[0]) | allowed_extra.get(name, set())
        for variant in variants:
            if not _fields(variant) <= base:
                errors.append(f"{name}: la variant {variant!r} usa camps que no té la primera")
    # lèxic coherent amb les dades i sense formes ambigües
    for key, synonyms in lexicon.SYNONYMS.items():
        if not set(synonyms) <= OPTIONS[key]:
            errors.append(f"sinònims de valors inexistents a {key}")
    if set(lexicon.LOCATIONS) != OPTIONS["location"]:
        errors.append("LOCATIONS no cobreix exactament els llocs de les dades")
    special = ({nlu.normalize(p) for p in lexicon.ANY_PHRASES} | {nlu.normalize(c) for c in EXIT_COMMANDS}
               | {nlu.normalize(c) for c in RESULTS_COMMANDS} | {nlu.normalize(c) for c in lexicon.BACK_COMMANDS})
    for key in ["type", "property_type", "condition", "location"]:
        vocabulary = nlu.build_vocabulary(key, sorted(OPTIONS[key]), HOUSES)
        if key != "location" and any(len(v) > 1 for v in vocabulary.values()):
            errors.append(f"{key}: una forma apunta a dos valors")
        if special & set(vocabulary):
            errors.append(f"{key}: formes que també són 'any' o sortida: {special & set(vocabulary)}")
    for key, comments in DATA["comments"].items():
        if not set(comments) <= OPTIONS[key]:
            errors.append(f"comentaris de valors inexistents a {key}")
    return errors


# --- 2. Extrem a extrem amb oracle ------------------------------------------------------------

class AutoConfirmIO(ScriptedIO):
    """Respon les respostes previstes i 'no' (mantenir) a qualsevol pregunta '(Yes / No)' del sistema."""

    def __init__(self, answers, limit=400):
        super().__init__(answers)
        self.limit, self.calls = limit, 0

    def ask(self, prompt):
        self.calls += 1
        if self.calls > self.limit:
            raise RuntimeError("massa torns (possible bucle)")
        if self.transcript and "(Yes / No)" in self.transcript[-1]:
            self.transcript.append(prompt + "no")
            return "no"
        return super().ask(prompt)


def _applicable(question, given):
    for key, allowed in question.get("ask_if", {}).items():
        value = given.get(key, "any")
        values = value if isinstance(value, (list, set)) else [value]
        if value != "any" and not any(v in allowed for v in values):
            return False
    return True


def _plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def generate(rng):
    """Una intenció d'usuari aleatòria: (respostes escrites, restriccions canòniques)."""
    answers, constraints, given = [], {}, {}
    for question in DATA["questions"]:
        if not _applicable(question, given):
            continue
        key, text, value, r = question["answer_key"], "any", "any", rng.random()
        if key == "type":
            value = rng.choice(["rent", "sale", "any"])
            text = rng.choice({"rent": ["rent", "RENT", "I want to rent", "alquiler", "lloguer"],
                               "sale": ["buy", "Sale", "comprar", "I'd like to buy"],
                               "any": ["any", "both", "doesn't matter", "me da igual"]}[value])
        elif key == "price" and given.get("type") in ("rent", "sale") and r < 0.6:
            sale = given["type"] == "sale"
            if r < 0.35:
                x = rng.randrange(100, 700, 10) * 1000 if sale else rng.randrange(400, 3500, 50)
                value = (None, x)
                text = rng.choice([f"{x // 1000}k", f"{x:,}".replace(",", "."), f"{x // 1000} mil", f"max {x // 1000}k"]
                                  if sale else [str(x), f"{x:,}".replace(",", "."), f"{x} euros", f"up to {x}"])
            else:
                a = rng.randrange(100, 500, 10) * 1000 if sale else rng.randrange(400, 2000, 50)
                b = a + (rng.randrange(50, 300, 10) * 1000 if sale else rng.randrange(100, 1500, 50))
                value = (a, b)
                text = f"between {a // 1000}k and {b // 1000}k" if sale else rng.choice([f"between {a} and {b}",
                                                                                           f"{a}-{b}", f"from {a} to {b}"])
        elif key == "location" and r < 0.75:
            kind = rng.random()
            if kind < 0.35:
                loc = rng.choice(LOCATIONS)
                value, text = {loc}, rng.choice([loc, loc.upper(), _plain(loc)])
            elif kind < 0.5:
                value, text = set(BCN), rng.choice(["Barcelona", "BCN"])
            elif kind < 0.6:
                value, text = {"Ciutat Vella", "Sant Martí"}, rng.choice(["near the beach", "cerca de la playa"])
            elif kind < 0.7:
                value, text = {"Ciutat Vella", "Eixample"}, rng.choice(["city centre", "centro"])
            elif kind < 0.8:
                value, text = set(TOWNS), rng.choice(["outskirts", "alrededores de barcelona"])
            elif kind < 0.9:
                a, b = rng.sample(LOCATIONS, 2)
                value, text = {a, b}, f"{a} or {b}"
            else:
                x = rng.choice(sorted(BCN))
                value, text = BCN - {x}, f"Barcelona except {x}"
        elif key == "property_type" and r < 0.7:
            synonyms = {"flat": ["flat", "apartment", "piso"], "house": ["house", "casa"], "chalet": ["chalet", "villa"],
                        "duplex": ["duplex", "dúplex"], "office": ["office", "oficina"],
                        "premises": ["premises", "local comercial", "shop"]}
            if r < 0.55:
                t = rng.choice(sorted(synonyms))
                value, text = {t}, rng.choice(synonyms[t])
            else:
                a, b = rng.sample(sorted(synonyms), 2)
                value, text = {a, b}, f"{synonyms[a][0]} or {synonyms[b][0]}"
        elif key in ("bedrooms", "bathrooms") and r < 0.6:
            n, m = rng.randint(1, 5 if key == "bedrooms" else 3), rng.random()
            if m < 0.5:
                value, text = (n, None), rng.choice([str(n), f"{n} {key}", f"at least {n}", f"{n} or more"])
            elif m < 0.7:
                value, text = (n, n), f"exactly {n}"
            elif m < 0.85:
                value, text = (max(0, n - 1), n + 1), f"around {n}"
            else:
                value, text = (n, n + 1), f"between {n} and {n + 1}"
        elif key == "square_meters" and r < 0.5:
            n = rng.randrange(40, 180, 5)
            value, text = ((n, None), rng.choice([str(n), f"{n} m2", f"at least {n}"])) if r < 0.35 \
                else ((n, n + 40), f"between {n} and {n + 40}")
        elif key == "floor" and r < 0.5:
            n = rng.randint(0, 6)
            value = (n, None)
            text = rng.choice([str(n), f"{n} or higher"]) if n else rng.choice(["0", "ground floor", "planta baja"])
        elif key == "condition" and r < 0.5:
            conditions = sorted(OPTIONS["condition"])
            if r < 0.4:
                t = rng.choice(conditions)
                value, text = {t}, t
            else:
                a, b = rng.sample(conditions, 2)
                value, text = {a, b}, f"{a} or {b}"
        elif key in YES_NO_KEYS and r < 0.75:
            value = rng.choice(["Yes", "No"])
            text = rng.choice({"Yes": ["yes", "Yes", "sí", "of course"], "No": ["no", "nope", "not really"]}[value])
        answers.append(text)
        constraints[key] = value
        given[key] = sorted(value) if isinstance(value, set) else value
    return answers, constraints


def oracle(constraints):
    """Filtre de referència, escrit des de l'especificació (no reutilitza el recomanador)."""
    number = lambda s: float(s[:-1]) * 1000 if s.endswith("k") else float(s)
    ids = []
    for h in HOUSES:
        ok = True
        for key, value in constraints.items():
            if value == "any":
                continue
            if key == "type":
                ok = h["type"] == value
            elif isinstance(value, set):
                ok = h[key] in value
            elif isinstance(value, tuple):
                low, high = value
                ok = (low is None or number(h[key]) >= low) and (high is None or number(h[key]) <= high)
            elif key == "shared":
                ok = value == "Yes" or h["shared"] == "No"
            else:
                ok = value == "No" or h[key] == "Yes"
            if not ok:
                break
        if ok:
            ids.append(h["id"])
    return ids


def transcript_errors(text, state, ids):
    errors = []
    if re.search(r"\{\w*\}", text) or re.search(r"\bNone\b(?! of)", text):
        errors.append("marcador o 'None' sense substituir")
    conversation_lines = text.split("<clear>")[0].splitlines()
    progress = [tuple(map(int, m)) for m in re.findall(r"^\[(\d+)/(\d+)\]", "\n".join(conversation_lines), re.M)]
    if [p[0] for p in progress] != list(range(1, len(progress) + 1)) or progress[-1][0] != progress[-1][1]:
        errors.append(f"numeració de preguntes {progress}")
    if any(b[1] > a[1] for a, b in zip(progress, progress[1:])):
        errors.append("el total de preguntes augmenta")
    for i, line in enumerate(conversation_lines):
        if line.startswith("Your answer:") and (i + 1 >= len(conversation_lines) or not conversation_lines[i + 1].strip()):
            errors.append(f"sense reacció: {line!r}")
    if any(after > before for _, before, after in state.match_history):
        errors.append("el comptador augmenta")
    if state.match_history and state.match_history[-1][2] != len(ids):
        errors.append("el comptador no coincideix amb els resultats")
    if text.rstrip().splitlines()[-1] not in DATA["end_message"]:
        errors.append("no acaba amb el comiat")
    return errors


def check_end_to_end(n=200):
    errors = []
    rng = random.Random(2026)
    for i in range(n):
        answers, constraints = generate(rng)
        io = AutoConfirmIO(answers + ["quit"])  # 'quit' = sortir del menú de resultats
        try:
            from recomanador import run
            state, houses = run(io=io, picker=nlg.VariedPicker(random.Random(i)))
        except Exception:
            errors.append(f"#{i} excepció amb {answers}: {traceback.format_exc(limit=1).splitlines()[-1]}")
            continue
        ids = [h["id"] for h in houses]
        problems = transcript_errors(io.text(), state, ids)
        if sorted(ids) != oracle(constraints):
            problems.append(f"resultats {sorted(ids)} != oracle {oracle(constraints)}")
        # Iteració 3: ordre de presentació = lloguers abans que vendes i, dins de cada grup, preu creixent.
        order = [({"rent": 0, "sale": 1}[h["type"]], to_number(h["price"])) for h in houses]
        if order != sorted(order):
            problems.append(f"resultats mal ordenats: {ids}")
        if io.answers:
            problems.append("respostes sense consumir")
        if problems:
            errors.append(f"#{i} {answers}: {problems}")
    return errors[:10]


# Iteració 3: correccions aleatòries. Només de preguntes que no canvien quines altres s'apliquen
# (el tipus i el tipus d'immoble sí que en canvien, i llavors el guió de respostes no seria previsible).
SLOT_WORDS = {"price": "budget", "location": "area", "bedrooms": "bedrooms", "bathrooms": "bathrooms",
              "square_meters": "size", "floor": "floor", "condition": "condition", "terrace": "terrace",
              "elevator": "elevator", "garden": "garden", "parking": "parking", "furnished": "furniture",
              "pets": "pets", "commercial_use": "business", "shared": "sharing"}


def correction_for(rng, key, constraints):
    """(text del valor nou, restricció nova) per corregir `key`, o None."""
    if key == "price":
        operation = constraints.get("type")
        if operation not in ("rent", "sale"):
            return None
        x = rng.randrange(150, 700, 10) * 1000 if operation == "sale" else rng.randrange(500, 3000, 50)
        return (f"{x // 1000}k" if operation == "sale" else str(x)), (None, x)
    if key == "location":
        loc = rng.choice(LOCATIONS)
        return (loc, {loc}) if rng.random() < 0.7 else ("near the beach", {"Ciutat Vella", "Sant Martí"})
    if key in ("bedrooms", "bathrooms"):
        n = rng.randint(1, 3)
        return f"at least {n}", (n, None)
    if key == "square_meters":
        n = rng.randrange(40, 150, 10)
        return f"{n} m2", (n, None)
    if key == "floor":
        n = rng.randint(0, 5)
        return str(n), (n, None)
    if key == "condition":
        t = rng.choice(sorted(OPTIONS["condition"]))
        return t, {t}
    if key in YES_NO_KEYS:
        v = rng.choice(["Yes", "No"])
        return v.lower(), v
    return None


def check_corrections_end_to_end(n=150):
    """Converses aleatòries amb una correcció ("change the area to Gràcia") a una pregunta posterior:
    els resultats han de coincidir amb l'oracle aplicant el valor nou."""
    from recomanador import run
    errors = []
    rng = random.Random(77)
    done = 0
    while done < n:
        answers, constraints = generate(rng)
        keys = list(constraints)
        choices = [(i, k) for i, k in enumerate(keys[:-1]) if k in SLOT_WORDS]
        if not choices:
            continue
        i, key = rng.choice(choices)
        new = correction_for(rng, key, constraints)
        if new is None:
            continue
        text, value = new
        j = rng.randrange(i + 1, len(answers))
        script = answers[:j] + [f"change the {SLOT_WORDS[key]} to {text}"] + answers[j:]
        constraints[key] = value
        io = AutoConfirmIO(script + ["quit"])
        try:
            state, houses = run(io=io, picker=nlg.VariedPicker(random.Random(done)))
        except Exception:
            errors.append(f"#{done} excepció amb {script}: {traceback.format_exc(limit=1).splitlines()[-1]}")
            done += 1
            continue
        problems = []
        if sorted(h["id"] for h in houses) != oracle(constraints):
            problems.append(f"resultats {sorted(h['id'] for h in houses)} != oracle {oracle(constraints)}")
        if io.answers:
            problems.append(f"respostes sense consumir {io.answers}")
        # amb el valor ja dit, la correcció es confirma amb una línia ("Sure, I've updated the area: ...")
        templates = DATA["reactions"]["correction_done"] + DATA["reactions"]["correction_done_value"]
        if not any(v.split("{")[0] in io.text() for v in templates):
            problems.append("la correcció no s'ha reconegut")  # (formulacions aleatòries: qualsevol variant)
        if problems:
            errors.append(f"#{done} {script}: {problems}")
        done += 1
    return errors[:10]


# --- 3. Fuzzing ---------------------------------------------------------------------------

POOL = ["", " ", "?", "help", "quit", "q", "e", "yes", "no", "y", "maybe", "asdf", "1", "0", "-1", "2.5",
        "999999999", "1e6", "€€€", "🏠", "ñ", "x" * 500, "between and", "between 3 and", "3-", "-", "k", "mil",
        "a", "not", "except", "but", "Barcelona except", "or", "one two three", "1.2.3", "1,,2", "nan", "None",
        "{value}", "%s", "both", "any", "anything but", "Gràcia but not Gràcia", "'; DROP TABLE houses;--",
        "300k", "rent", "buy or rent", "Eixampel", "2 doubles and 1 single", "10 bedrooms", "300k a month",
        "1200 1500", "between 5 and 2", "around 0", "less than 0", "flat but not flat", "planta baja",
        "no, yes", "sí sí", "I don't know", "whatever, but cheap", "everything except everything",
        "show me", "show me flats in Gràcia", "resultados", "back", "go back", "change", "change the budget",
        "change the area to Gràcia", "actually, Gràcia", "actually, a house", "change the garden",
        "change buy or rent", "I meant a flat", "change the bedrooms to 2 doubles and 1 single"]


class FuzzIO(ScriptedIO):
    def __init__(self, rng, garbage, limit=600):
        super().__init__([])
        self.rng, self.garbage, self.limit, self.calls = rng, garbage, limit, 0

    def ask(self, prompt):
        self.calls += 1
        if self.calls > self.limit:
            raise RuntimeError("massa torns (possible bucle)")
        answer = self.rng.choice(POOL) if self.calls <= self.garbage else "any"
        self.transcript.append(prompt + answer)
        return answer


def check_fuzzing(n=80):
    from recomanador import run
    errors = []
    for i in range(n):
        rng = random.Random(i)
        io = FuzzIO(rng, garbage=rng.randint(5, 60))
        try:
            run(io=io, picker=nlg.VariedPicker(random.Random(i)))
        except Exception:
            errors.append(f"#{i}: {traceback.format_exc(limit=1).splitlines()[-1]} després de {io.transcript[-3:]}")
            continue
        if io.text().rstrip().splitlines()[-1] not in DATA["end_message"]:
            errors.append(f"#{i}: no acaba amb el comiat")
    return errors[:10]


# --- 4. Rendiment i casos concrets trobats a l'auditoria -------------------------------------

def check_performance():
    vocabulary = nlu.build_vocabulary("location", sorted(OPTIONS["location"]), HOUSES)
    answer = "I am not really sure what area I prefer to be honest, somewhere quiet with good transport " * 2
    start = time.perf_counter()
    nlu.analyse(vocabulary, answer, multiple=True)
    elapsed = time.perf_counter() - start
    return [] if elapsed < 1.0 else [f"una resposta de {len(answer.split())} paraules triga {elapsed:.2f} s"]


def check_gap_message():
    """Un valor dins del rang de les dades però sense cap vivenda no s'ha d'explicar com a 'fora de rang'."""
    # 8a pregunta (m2) amb tot 'any' abans; 'no' = mantenir-la; la resta, 'any'
    text = run_case(["any"] * 7 + ["between 155 and 195", "no", "no"] + ["any"] * 9)[2].text()
    errors = []
    if "None of our homes matches between 155 and 195 m2." not in text:
        errors.append("no surt el missatge de 'cap vivenda' per a un buit de les dades")
    if "ours have between 45 and 277 m2" in text:
        errors.append("es diu que el valor és fora de rang quan no ho és")
    # 6a pregunta (habitacions): '10', 'yes' = canviar-la, 'any'; la resta, 'any'
    text = run_case(["any"] * 5 + ["10", "yes", "any"] + ["any"] * 11)[2].text()
    if "ours have between 1 and 5 bedrooms" not in text:
        errors.append("un valor realment fora de rang no s'explica")
    return errors


CHECKS = [
    ("consistència estàtica: dades, guió, lèxic, plantilles", check_static),
    ("extrem a extrem: 200 converses aleatòries vs. oracle independent + invariants", check_end_to_end),
    ("correccions: 150 converses amb una correcció aleatòria vs. oracle", check_corrections_end_to_end),
    ("fuzzing: 80 converses amb respostes estranyes (cap excepció ni bucle)", check_fuzzing),
    ("rendiment: resposta llarga no reconeguda < 1 s", check_performance),
    ("missatge correcte per a un valor sense vivendes dins del rang", check_gap_message),
]


def main():
    return run_suite("Integració (sistema complet)", [], CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
