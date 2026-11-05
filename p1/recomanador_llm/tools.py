"""Tools que el model pot cridar: les funcions, el seu esquema JSON i l'execució segura.

Entregable (proposta A). Dues tools, no més (la teoria: poques tools, menys confusió):
- search_homes: els 17 criteris del sistema 1, amb el seu mateix filtre (recomanador.recommender) i la
  seva NLU (recomanador.nlu) per interpretar ubicacions i tipus: 'Barcelona' = tots els districtes, zones
  ('near the beach'), sinònims ('apartment', 'buy'), noms sense accents o amb errors petits. Així els dos
  sistemes cerquen exactament igual i la comparació de l'informe és justa.
- get_home_details: la fitxa completa d'una vivenda, en llenguatge natural (la del sistema 1).

La sortida és compacta: el que s'ha cercat, quantes n'hi ha i 5 línies ja redactades que el model només
ha de copiar (abans: totes les fitxes en JSON, fins a ~15.000 tokens). Menys dades per llegir vol dir
menys context, menys latència i menys ocasions d'inventar. Sense resultats, es donen les "casi
coincidències" i què no compleixen, perquè el consell de relaxar un criteri es basi en dades.

Validació (execution guardrail): abans d'executar es comproven els noms, tipus i valors dels arguments
(enumeracions, nombres no negatius, mínim <= màxim...). Els errors es retornen al model en text, amb
el que ha de corregir; mai s'atura el xat. La ruta de les dades no és un argument (permisos mínims).
"""

import json
import re
from functools import lru_cache

from recomanador import nlg, nlu
from recomanador.data_loader import load_data
from recomanador.lexicon import ZONES
from recomanador.numeric import Range
from recomanador.recommender import find_suitable_houses, near_misses, rank_houses, to_number

from . import guardrails, prompts
from .config import DATA_PATH, RESULTS_PER_PAGE


@lru_cache(maxsize=None)
def load_dataset(path=DATA_PATH):
    return load_data(path)


def load_houses():
    return load_dataset()["houses"]


@lru_cache(maxsize=None)
def _vocabulary(key):
    """Vocabulari de l'NLU del sistema 1 per a un camp (ubicació, operació, tipus d'immoble, estat)."""
    houses = load_houses()
    return nlu.build_vocabulary(key, sorted({h[key] for h in houses}), houses)


def _values(key):
    return sorted({h[key] for h in load_houses()})


# --- Esquema dels arguments ---

# Rangs numèrics: camp de les dades -> (argument del mínim, argument del màxim).
NUMERIC = {"price": ("min_price", "max_price"), "bedrooms": ("min_bedrooms", "max_bedrooms"),
           "bathrooms": ("min_bathrooms", None), "square_meters": ("min_square_meters", "max_square_meters"),
           "floor": ("min_floor", "max_floor")}
# Característiques que es poden exigir -> camp de les dades ("No" no filtra: vol dir que no cal).
FEATURES = {"elevator": "elevator", "terrace": "terrace", "garden": "garden", "parking": "parking",
            "furnished": "furnished", "pets_allowed": "pets", "commercial_use": "commercial_use"}


def _integer(description):
    return {"type": "integer", "description": description}


def _search_schema():
    houses = load_houses()
    districts = sorted({h["location"] for h in houses if h["city"] == "Barcelona"})
    towns = sorted({h["city"] for h in houses if h["city"] != "Barcelona"})
    properties = {
        "type": {"type": "string", "enum": ["rent", "sale"],
                 "description": "'rent' or 'sale' (buy). Omit it if the client has not said."},
        "locations": {"type": "array", "items": {"type": "string"},
                      "description": "Where the client wants to live. Each item is a Barcelona district "
                                     f"({', '.join(districts)}), 'Barcelona' for the whole city, a nearby town "
                                     f"({', '.join(towns)}) or an area ({', '.join(ZONES)}). Omit it for anywhere."},
        "min_price": _integer("Minimum price in euros."),
        "max_price": _integer("Maximum price in euros: per month for rent, total price for sale "
                              "('400k' = 400000)."),
        "property_types": {"type": "array", "items": {"type": "string", "enum": _values("property_type")},
                           "description": "Accepted types of property."},
        "conditions": {"type": "array", "items": {"type": "string", "enum": _values("condition")},
                       "description": "Accepted conditions of the property."},
        "min_bedrooms": _integer("Minimum number of bedrooms (rooms, for offices and premises)."),
        "max_bedrooms": _integer("Maximum number of bedrooms."),
        "min_bathrooms": _integer("Minimum number of bathrooms."),
        "min_square_meters": _integer("Minimum size in square metres."),
        "max_square_meters": _integer("Maximum size in square metres."),
        "min_floor": _integer("Lowest acceptable floor (0 = ground floor)."),
        "max_floor": _integer("Highest acceptable floor (0 = ground floor)."),
        "required_features": {"type": "array", "items": {"type": "string", "enum": list(FEATURES)},
                              "description": "Only the features the client says they need."},
        "include_shared_rooms": {"type": "boolean",
                                 "description": "true only if the client accepts renting a room in a shared "
                                                "flat. By default, rooms in shared flats are not included."},
        "page": _integer(f"Page of results ({RESULTS_PER_PAGE} homes per page). Use 2, 3... only when the "
                         "client wants to see more homes from the same search."),
    }
    return {"type": "function", "function": {
        "name": "search_homes",
        "description": "Searches the agency's listings. Pass only the criteria the client has stated; every "
                       "argument is optional. Returns the search applied, how many homes match and up to "
                       f"{RESULTS_PER_PAGE} of them (rent before sale, cheapest first), one line per home. If "
                       "none matches, returns the closest homes and what they miss.",
        "parameters": {"type": "object", "properties": properties, "required": []}}}


DETAILS_SCHEMA = {"type": "function", "function": {
    "name": "get_home_details",
    "description": "Returns the full description of one home: size, floor, condition, every feature and "
                   "its conditions. Use it when the client asks about a specific home.",
    "parameters": {"type": "object", "required": ["id"],
                   "properties": {"id": _integer("The id of the home (the number after #).")}}}}


# --- Validació i conversió dels arguments ---

class ArgumentError(ValueError):
    """Argument invàlid: el missatge explica al model què ha de corregir."""


def _number(name, value):
    """Enter no negatiu: 1200, 1200.0, '1200', '1,200', '1.200', '400k', '850 €'."""
    if isinstance(value, bool):
        raise ArgumentError(f"{name} must be a number, not {value!r}.")
    if isinstance(value, str):
        text = value.lower().replace("€", "").replace("euros", "").replace(" ", "").strip()
        if re.fullmatch(r"\d{1,3}([.,]\d{3})+", text):  # separador de milers
            text = re.sub(r"[.,]", "", text)
        try:
            value = float(text[:-1]) * 1000 if text.endswith("k") else float(text)
        except ValueError:
            raise ArgumentError(f"{name} must be a number, not {value!r}.") from None
    if not isinstance(value, (int, float)):
        raise ArgumentError(f"{name} must be a number, not {value!r}.")
    if value < 0:
        raise ArgumentError(f"{name} cannot be negative.")
    return value


def _as_list(name, value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ArgumentError(f"{name} must be a list of strings.")


def _resolve(name, key, items, multiple=True, hint=None):
    """Interpreta cada valor amb l'NLU del sistema 1; els que no s'entenen fan un error amb les opcions."""
    found, unknown = set(), []
    for item in items:
        value = nlu.interpret(_vocabulary(key), item, multiple=multiple)
        if value:
            found.update(value if multiple else [value])
        else:
            unknown.append(item)
    if unknown:
        raise ArgumentError(f"Unknown {name}: {', '.join(map(repr, unknown))}. {hint or ''}".strip())
    return sorted(found)


def search_criteria(arguments):
    """Arguments de search_homes -> (preferències en el format del sistema 1, pàgina)."""
    prefs = {}
    if arguments.get("type") is not None:
        prefs["type"] = _resolve("type", "type", [str(arguments["type"])], multiple=False,
                                 hint="Use 'rent' or 'sale'.")[0]
    if arguments.get("locations") is not None:
        places = [p for p in _as_list("locations", arguments["locations"]) if not nlu.is_any(p)]  # 'anywhere'
        if places:
            prefs["location"] = _resolve(
                "locations", "location", places,
                hint="Use a Barcelona district, 'Barcelona', a nearby town or an area such as 'city centre', "
                     "or omit locations for anywhere.")
    for name, key in (("property_types", "property_type"), ("conditions", "condition")):
        if arguments.get(name) is not None:
            prefs[key] = _resolve(name, key, _as_list(name, arguments[name]),
                                  hint=f"Valid values: {', '.join(_values(key))}.")
    for key, (low_name, high_name) in NUMERIC.items():
        low = _number(low_name, arguments[low_name]) if arguments.get(low_name) is not None else None
        high = _number(high_name, arguments[high_name]) if high_name and arguments.get(high_name) is not None \
            else None
        if low is not None and high is not None and low > high:
            raise ArgumentError(f"{low_name} ({low:g}) is greater than {high_name} ({high:g}).")
        if low is not None or high is not None:
            prefs[key] = Range(low, high)
    for feature in _as_list("required_features", arguments.get("required_features") or []):
        if feature.strip().lower() not in FEATURES and feature.strip().lower() not in FEATURES.values():
            raise ArgumentError(f"Unknown feature {feature!r}. Valid values: {', '.join(FEATURES)}.")
        prefs[FEATURES.get(feature.strip().lower(), feature.strip().lower())] = "Yes"
    shared = arguments.get("include_shared_rooms")
    if prefs.get("type") != "sale" and not (shared is True or str(shared).strip().lower() in ("true", "yes")):
        prefs["shared"] = "No"  # opt-in, com al sistema 1: una habitació no és el que demana qui vol un pis
    page = int(_number("page", arguments["page"])) if arguments.get("page") is not None else 1
    if page < 1:
        raise ArgumentError("page must be 1 or greater.")
    return prefs, page


# --- Realització de la sortida ---

_EXTRAS = {"elevator": "elevator", "terrace": "terrace", "garden": "garden", "parking": "parking",
           "furnished": "furnished"}


def home_line(house, missing=None, language="en"):
    """'#18 · flat for rent in Gràcia (Barcelona) · 1 bedroom · 50 m2 · 850 €/month — elevator, terrace', en
    l'idioma demanat (prompts.LINE_WORDS): el model rep les línies en anglès i el client les veu en el seu idioma."""
    words = prompts.LINE_WORDS[language]
    kind = words["kinds"][house["property_type"]]
    working = house["property_type"] in ("office", "premises")
    rooms = int(to_number(house["bedrooms"]))
    shared = house["shared"] == "Yes"
    # Una habitació en un pis compartit: les habitacions són del pis ("room in a shared 4-bedroom flat").
    what = words["shared"].format(rooms=rooms, kind=kind) if shared else f"{kind} {words['operation'][house['type']]}"
    parts = [f"#{house['id']}", f"{what} {words['in']} {nlg.format_location(house)}"]
    if rooms and not shared:
        one, many = words["rooms_work" if working else "rooms"]
        parts.append(f"{rooms} {one if rooms == 1 else many}")
    parts.append(f"{house['square_meters']} m2")
    price = nlg.format_number(to_number(house["price"])).replace(",", words["thousands"])
    per = words["per_room"] if shared else ""
    parts.append(f"{price} {words['month']}{per}" if house["type"] == "rent" else f"{price} €")
    line = " · ".join(parts)
    extras = [words["extras"][key] for key in _EXTRAS if house[key] == "Yes"]
    if house["type"] == "rent" and house["pets"] == "Yes":
        extras.append(words["extras"]["pets"])
    if extras:
        line += " — " + ", ".join(extras)
    if missing:
        line += f" ({words['misses'].format(slots=', '.join(words['slots'][key] for key in missing))})"
    return line


_ENGLISH_SLOTS = {name: key for key, name in prompts.LINE_WORDS["en"]["slots"].items()}


def localize_line(line, language):
    """Una línia de vivenda en anglès (tal com la dona search_homes) en l'idioma del client."""
    if language == "en":
        return line
    match = re.match(r"#(\d+) · ", line)
    house = next((h for h in load_houses() if match and h["id"] == int(match.group(1))), None)
    if house is None:
        return line
    missing = re.search(r"\(misses: ([^)]*)\)", line)
    keys = [_ENGLISH_SLOTS[name] for name in missing.group(1).split(", ") if name in _ENGLISH_SLOTS] if missing else None
    return home_line(house, keys, language)


def _notes(prefs, shown, total):
    """Notes per al model (no per copiar): dades reals perquè pugui comentar les opcions i fer una pregunta útil
    sense inventar (converses manuals v5: les respostes eren només "aquests són els pisos" + la llista)."""
    notes = []
    if len(shown) > 1:
        cheapest = min(shown, key=lambda h: to_number(h["price"]))
        largest = max(shown, key=lambda h: to_number(h["square_meters"]))
        notes.append(f"cheapest shown: #{cheapest['id']} ({home_line(cheapest).split(' · ')[-1].split(' — ')[0]})")
        if largest["id"] != cheapest["id"]:
            notes.append(f"largest shown: #{largest['id']} ({largest['square_meters']} m2)")
        common = [text for key, text in _EXTRAS.items() if all(h[key] == "Yes" for h in shown)]
        if common:
            notes.append("all of them have: " + ", ".join(common))
    unspecified = [label for key, label in (("type", "rent or buy"), ("price", "budget"), ("location", "area"),
                                            ("property_type", "type of home")) if key not in prefs]
    if unspecified:
        notes.append("the client has not said yet: " + ", ".join(unspecified))
    return f"Notes for your answer (facts to comment on; do not copy them as a list): {'; '.join(notes)}." if notes else ""


def search_homes(**arguments):
    prefs, page = search_criteria(arguments)
    data = load_dataset()
    summary = nlg.summarize(data, prefs) or "any home"
    homes = rank_houses(find_suitable_houses(data, prefs))
    lines = [f"Search: {summary}."]
    if homes:
        start = (page - 1) * RESULTS_PER_PAGE
        shown = homes[start:start + RESULTS_PER_PAGE]
        if not shown:
            return lines[0] + f"\nOnly {len(homes)} homes match: page {page} is empty."
        count = "1 home matches" if len(homes) == 1 else f"{len(homes)} homes match"
        remaining = len(homes) - start - len(shown)
        if start == 0 and not remaining:
            lines.append(f"{count}:" if len(homes) == 1 else f"{count} (rent before sale, cheapest first):")
        else:
            lines.append(f"{count}. Showing {start + 1}-{start + len(shown)} (rent before sale, cheapest first):")
        lines += [home_line(house) for house in shown]
        if remaining:
            lines.append(f"{remaining} more: call again with page={page + 1} to see them, or narrow the search.")
        notes = _notes(prefs, shown, len(homes))
        return "\n".join(lines + ([notes] if notes else []))
    near = near_misses(data, prefs)
    if not near:
        lines.append("No home matches, and none is close: several criteria would have to change.")
        return "\n".join(lines)
    lines.append("No home matches all the criteria. The closest ones (in brackets, what they miss):")
    lines += [home_line(house, failed) for house, failed in near]
    return "\n".join(lines)


def get_home_details(id):
    number = _number("id", str(id).lstrip("#") if isinstance(id, str) else id)  # '#18' -> 18
    houses = {h["id"]: h for h in load_houses()}
    if number != int(number) or int(number) not in houses:
        raise ArgumentError(f"There is no home with id {id}. Ids go from {min(houses)} to {max(houses)}.")
    house = houses[int(number)]
    return f"#{house['id']}: " + " ".join(nlg.describe_house(load_dataset(), house))


TOOLS = [_search_schema(), DETAILS_SCHEMA]
AVAILABLE_TOOLS = {"search_homes": search_homes, "get_home_details": get_home_details}


def run_tool(name, arguments):
    """Executa la tool que demana el model i en retorna el resultat com a text per al model.

    Mai llança excepcions: els errors es retornen al model ("Error: ...") perquè pugui corregir la crida
    o explicar-ho al client. Guardrail d'execució (guardrails.py): abans, la crida es valida contra la
    llista de tools i el seu esquema; després, el resultat es neteja. Els null es tracten com a no indicats.
    """
    error = guardrails.check_tool_call(name, arguments, TOOLS)
    if error:
        return error
    arguments = {k: v for k, v in arguments.items() if v is not None}
    try:
        output = AVAILABLE_TOOLS[name](**arguments)
    except ArgumentError as e:
        return f"Error: {e}"
    except Exception as e:  # noqa: BLE001  (un error inesperat no ha d'aturar el xat)
        return f"Error: the search failed ({type(e).__name__}). Try again with simpler criteria."
    return guardrails.sanitize_tool_output(output)
