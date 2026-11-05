"""Flux de la conversa (entregable, punt C): com comença i com acaba.

Decisions:
- l'inici, l'ajuda i el tancament són textos del codi, no del model: són instantanis, no poden al·lucinar i
  diuen exactament què hi ha a les dades (nombre d'anuncis, zones);
- la benvinguda presenta el rol, què pot fer i què NO (reservar, negociar, assessorar): fixar expectatives
  des del principi és la lliçó del cas Air Canada de la teoria; dona un exemple de petició i com acabar;
- la benvinguda no s'afegeix a l'historial del model: canviaria totes les entrades del model i les
  avaluacions deixarien de ser comparables (primer es mesura un canvi i després un altre);
- el tancament reconeix comiats naturals ("adiós", "thanks, that's all, bye"), no només 'exit'/'quit', però
  només en missatges curts, sense pregunta i sense criteris de cerca ("thanks, and #19?" no és un comiat);
- el resum final dona els #id vists a la sessió (vàlids en qualsevol idioma) per poder-hi tornar.
"""

import re

from recomanador.nlu import fold

from . import guardrails, prompts
from .config import EXIT_COMMANDS

_FAREWELL = re.compile(
    r"\b(bye|goodbye|see you|that'?s all|that is all|i'?m done|nothing else|no more questions|"
    r"adios|hasta luego|hasta pronto|eso es todo|nada mas|ya esta|me voy|chao|chau|"
    r"adeu|fins aviat|fins despres|aixo es tot|res mes|ja esta|me'n vaig)\b")
_HELP = {"help", "ayuda", "ajuda", "?", "menu", "help me", "ayudame", "ajuda'm"}
MAX_FAREWELL_WORDS = 10


def welcome_lines(houses=None):
    """Benvinguda amb les dades reals (com el system prompt): primera línia, títol; la resta, informació."""
    if houses is None:
        from .tools import load_houses
        houses = load_houses()
    towns = sorted({h["city"] for h in houses if h["city"] != "Barcelona"})
    text = prompts.WELCOME.format(
        n_houses=len(houses), n_rent=sum(h["type"] == "rent" for h in houses),
        n_sale=sum(h["type"] == "sale" for h in houses), towns=", ".join(towns[:-1]) + " and " + towns[-1])
    return text.split("\n")


def _words(text):
    return re.findall(r"[a-z0-9']+", fold(text))


def is_exit(text):
    return fold(text).strip(" .!") in EXIT_COMMANDS


def is_help(text):
    return fold(text).strip(" .!") in _HELP


def is_farewell(text):
    """Comiat natural: curt, sense pregunta i sense criteris de cerca."""
    if "?" in text or len(_words(text)) > MAX_FAREWELL_WORDS:
        return False
    return bool(_FAREWELL.search(fold(text))) and not guardrails._has_criteria(text)


def help_lines(language):
    return prompts.HELP[language].split("\n")


def session_summary(history):
    """(#id consultats en detall, #id de l'última cerca) a partir de l'historial."""
    details, shown = [], []
    for message in history:
        if message["role"] != "tool":
            continue
        content = str(message.get("content") or "")
        if message.get("name") == "get_home_details" and content.startswith("#"):
            details.append(int(re.match(r"#(\d+)", content).group(1)))
        elif message.get("name") == "search_homes" and not content.startswith("Error"):
            shown = [int(m.group(1)) for m in guardrails.HOME_LINE.finditer(content)]
    return list(dict.fromkeys(details)), shown


def _ids(numbers):
    return ", ".join(f"#{n}" for n in numbers)  # comes: vàlid en els tres idiomes


def closing_lines(history, language):
    """Comiat amb el resum de la sessió, en l'idioma del client."""
    words = prompts.CLOSING[language]
    details, shown = session_summary(history)
    lines = [words["thanks"]]
    if details:
        lines.append(words["details"].format(ids=_ids(details)))
    if shown:
        lines.append(words["shown"].format(ids=_ids(shown)))
    lines.append(words["back"] if details or shown else words["back_empty"])
    return lines
