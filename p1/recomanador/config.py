"""Constants i paràmetres configurables del sistema.

Punt únic on aniran els paràmetres de les iteracions futures
(sinònims, marges dels rangs, llistes de zones, llistes de frases...).
"""

from pathlib import Path

# Ruta per defecte del JSON: carpeta que conté el paquet (p1/ en local, /content/ a Colab).
# L'Ex. 7 fa servir house_data_v2.json; house_data.json queda intacte per als Ex. 1-6.
DATA_PATH = Path(__file__).resolve().parent.parent / "house_data_v2.json"

# Comandes de sortida (Ex. 3), copiades literalment de l'Ex. 6.
EXIT_COMMANDS = {
    "q",
    "quit",
    "exit",
    "e",
    ":q",
    "salir",
    "fin",
    "end",
    "stop",
    "cancel",
    "sleep"
}

# Interfície (iteració 3): colors i format a la consola. També es desactiven amb la variable NO_COLOR.
USE_COLORS = True

# Comodí "m'és igual" (Ex. 5).
ANY = "any"

# Característiques booleanes que només filtren si la resposta és "Yes" (Ex. 6.4-6.6 i bloc 2).
YES_ONLY_FILTERS = ["terrace", "elevator", "commercial_use", "garden", "parking", "furnished", "pets"]

# Característiques que només es mostren si l'usuari les accepta: "No" les exclou, "Yes" no filtra.
OPT_IN_FILTERS = ["shared"]

# --- NLU (bloc 3) ---
# Preguntes on l'usuari pot triar diversos valors alhora (p.ex. "Gràcia o Eixample", "flat or duplex")
# i excloure'n ("anywhere except Nou Barris").
MULTI_SELECT_KEYS = ["location", "property_type", "condition"]

# Formes més curtes que això ('y', 'n') només compten si són tota la resposta.
MIN_CONTAINED_LENGTH = 2

# Nombre de paraules prèvies (dins la mateixa clàusula) on es busca una negació.
NEGATION_WINDOW = 3

# Coincidència aproximada (errors tipogràfics): només si no hi ha cap coincidència exacta,
# per a formes d'almenys FUZZY_MIN_LENGTH lletres i amb similitud >= FUZZY_CUTOFF (0-1).
# 0.83: accepta una lletra de més/menys/transposada en paraules de 6+ lletres ('gracie', 'eixampel'),
# però no una lletra canviada en paraules de 5 ('horse' -> 'house' = 0.80).
FUZZY_MIN_LENGTH = 5
FUZZY_CUTOFF = 0.83

# --- NLU numèrica (bloc 3) ---
# Què vol dir un número sense modificador: el pressupost és un màxim; la resta, un mínim
# ("3 bedrooms" = 3 o més, com als portals immobiliaris).
DEFAULT_NUMERIC_MODE = {"price": "max", "bedrooms": "min", "bathrooms": "min",
                        "square_meters": "min", "floor": "min"}

# Marge de "around X" per pregunta: ("abs", per sota, per sobre) en unitats o ("rel", ...) en proporció.
APPROX_MARGINS = {
    "bedrooms": ("abs", 1, 1),
    "bathrooms": ("abs", 1, 1),
    "floor": ("abs", 1, 1),
    "square_meters": ("rel", 0.15, 0.15),
    "price": ("rel", 0.10, 0.10),
}

# Preguntes de nombres enters: "more than 2" -> mínim 3; "less than 3" -> màxim 2.
INTEGER_KEYS = ["bedrooms", "bathrooms", "floor"]

# Preguntes on se sumen quantitats ("1 big bedroom and 1 small one" -> 2) i es demana confirmació.
ROOM_SUM_KEYS = ["bedrooms", "bathrooms"]

# Compra: un pressupost per sota d'aquest valor s'entén en milers ("250" -> 250.000 euros).
SALE_THOUSANDS_BELOW = 1000

# --- Reacció davant d'anomalies (bloc 4) ---
# Imports a partir d'aquest valor semblen preus de compra, no lloguers mensuals:
# serveix per endevinar l'operació quan el tipus és 'any' i per avisar d'un lloguer de "300k".
PURCHASE_SCALE_FROM = 10000

# Respostes no enteses seguides abans d'oferir saltar la pregunta amb 'any'.
OFFER_SKIP_AFTER = 3

# L'ajuda de cada pregunta només es mostra si l'usuari falla o la demana amb una d'aquestes paraules.
HELP_COMMANDS = {"help", "?", "options", "ayuda", "opciones", "ajuda", "opcions"}

# Iteració 3: anar als resultats sense acabar el qüestionari. Només compten si són tota la resposta
# (així "show me flats in Gràcia" no talla la conversa).
RESULTS_COMMANDS = {"show me", "show results", "show me the results", "results", "see results",
                    "show me what you have", "show me what you've got", "that's enough", "enough",
                    "skip to results", "resultados", "ver resultados", "muéstramelos", "enséñamelos",
                    "resultats", "veure resultats", "ensenya-me'ls"}

# Iteració 3: "casi coincidències" quan no hi ha resultats. Es mostren les vivendes que fallen menys
# criteris (com a molt aquest nombre), fins a NEAR_MISS_LIMIT. NON_RELAXABLE: criteris que mai es relaxen.
NEAR_MISS_MAX_FAILURES = 2
NEAR_MISS_LIMIT = 5
NON_RELAXABLE = ["type"]

# --- Comptador de coincidències (bloc 5) ---
# Per sota d'aquest nombre de vivendes es diu "Only 2 left, we're getting close!".
FEW_MATCHES = 3

# Iteració 3: zones disponibles amb la pregunta de la zona. Si d'una ciutat en falten com a molt aquests
# districtes, es diu "every district of Barcelona except Les Corts" en lloc de llistar-los tots.
ZONES_EXCEPT_MAX = 3
