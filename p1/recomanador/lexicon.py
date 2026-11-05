"""Recursos lingüístics de l'NLU (bloc 3): sinònims, zones i paraules funcionals.

Totes les formes s'escriuen en forma natural (amb accents, majúscules, apòstrofs):
`nlu` les normalitza amb la mateixa funció que l'entrada de l'usuari, de manera que
'L'Hospitalet', 'l’hospitalet' i 'L HOSPITALET' coincideixen per construcció.

El sistema parla anglès, però els usuaris són de l'àrea de Barcelona: s'accepten
també les formes castellanes i catalanes més habituals.
"""

# --- Respostes "m'és igual" -------------------------------------------------
# Formes d'una paraula: només si són tota la resposta ("any"), per no confondre
# "I don't have any pets" amb "any". Formes de 2+ paraules: també dins d'una frase.
ANY_PHRASES = [
    "any", "anything", "anywhere", "whatever", "either", "both", "all", "skip",
    "indifferent", "igual", "cualquiera", "indiferente", "qualsevol", "indiferent",
    "doesn't matter", "it doesn't matter", "don't mind", "i don't mind", "don't care", "i don't care",
    "no preference", "no preferences", "not important", "not bothered", "not fussed",
    "either is fine", "either one", "any of them", "anything is fine", "whatever you have",
    "me da igual", "da igual", "me es igual", "no me importa", "no importa", "lo que sea",
    "sin preferencia", "m'és igual", "tant me fa", "em és igual",
    "everything", "everywhere", "todo", "tot", "no limit", "sin límite", "sense límit",
]

# --- Negació -----------------------------------------------------------------
# Una coincidència precedida (dins la mateixa clàusula) per una d'aquestes paraules
# es descarta: "I don't want to buy" no és "buy". ("don't" es normalitza a "do not".)
NEGATIONS = {"not", "no", "never", "without", "sin", "ni", "nunca", "sense", "mai"}

# --- Exclusió (preguntes de selecció múltiple) ---------------------------------
# "anywhere except Nou Barris", "Barcelona but not Nou Barris", "todo menos un piso":
# el que va abans del marcador s'inclou (o tot, si és buit o 'any') i el que va després s'exclou.
EXCLUSION_MARKERS = ["except", "except for", "but", "but not", "apart from", "other than", "excluding",
                     "excepto", "menos", "salvo", "excepte", "menys", "llevat de"]

# --- Sí / No -----------------------------------------------------------------
YES_NO = {
    "Yes": [
        "yes", "y", "yeah", "yea", "yep", "yup", "sure", "of course", "definitely", "absolutely",
        "certainly", "please", "yes please", "i do", "i want", "i want it", "want it", "i need it",
        "need it", "i would", "i would like", "would like", "must", "a must", "it's a must", "must have",
        "required", "essential", "important", "true", "ok", "okay", "no problem", "why not",
        "sí", "si", "sip", "claro", "vale", "por supuesto", "imprescindible", "obligatorio", "necesario",
        "és clar", "i tant", "d'acord",
    ],
    "No": [
        "no", "n", "nope", "nah", "not", "no thanks", "no thank you", "not needed", "not necessary",
        "no need", "i don't", "don't", "dont", "i don't need it", "i don't want it", "without", "never",
        "false", "not really", "no gracias", "para nada", "no hace falta", "no es necesario",
        "tampoco", "no cal", "gens", "de cap manera",
    ],
}

# --- Sinònims per pregunta (valor canònic del JSON -> formes alternatives) ----
SYNONYMS = {
    "type": {
        "sale": ["sale", "for sale", "buy", "buying", "to buy", "purchase", "purchasing", "to purchase",
                 "own", "to own", "comprar", "compra", "compro", "venta", "en venta", "a la venta"],
        "rent": ["rent", "rental", "renting", "to rent", "for rent", "lease", "leasing", "to let",
                 "alquiler", "alquilar", "alquilo", "de alquiler", "en alquiler", "lloguer", "llogar",
                 "de lloguer"],
    },
    "property_type": {
        "flat": ["flat", "apartment", "apt", "appartment", "studio", "loft", "penthouse", "piso", "pis",
                 "apartamento", "apartament", "estudio", "estudi", "ático", "àtic"],
        "house": ["house", "casa", "townhouse", "town house", "terraced house", "semi-detached",
                  "semi-detached house", "family house", "single-family home", "cottage", "adosado",
                  "casa adosada", "unifamiliar", "casa unifamiliar"],
        "chalet": ["chalet", "villa", "detached house", "detached", "mansion", "xalet", "torre",
                   "casa independiente", "chalet independiente"],
        "duplex": ["duplex", "dúplex", "maisonette", "triplex", "two-storey", "two-story", "two floors",
                   "ático dúplex", "àtic dúplex"],
        "office": ["office", "offices", "oficina", "oficinas", "despacho", "despatx", "workspace", "coworking"],
        "premises": ["premises", "commercial premises", "local", "local comercial", "shop", "store",
                     "retail", "retail space", "storefront", "shopfront", "commercial space", "tienda",
                     "botiga", "bajo comercial"],
    },
    "condition": {
        "new": ["new", "brand new", "new build", "newly built", "new construction", "obra nueva",
                "nuevo", "nueva", "a estrenar", "nou", "nova", "obra nova"],
        "very good": ["very good", "excellent", "great", "perfect", "perfect condition", "like new",
                      "as new", "immaculate", "pristine", "muy bien", "muy bueno", "muy buen estado",
                      "excelente", "impecable", "molt bo", "molt bon estat", "com nou"],
        "good": ["good", "good condition", "fine", "decent", "correct", "acceptable", "normal", "bien",
                 "bueno", "buen estado", "correcto", "bon estat"],
        "renovated": ["renovated", "refurbished", "reformed", "remodeled", "remodelled", "restored",
                      "updated", "reformado", "reformada", "renovado", "rehabilitado", "reformat"],
        "needs renovation": ["needs renovation", "needs work", "needs refurbishment", "needs refurbishing",
                             "to renovate", "to refurbish", "to reform", "for renovation", "fixer-upper",
                             "renovation needed", "a reformar", "para reformar", "por reformar",
                             "per reformar", "a rehabilitar"],
    },
}

# --- Llocs: formes alternatives (barris inclosos) -------------------------------
LOCATIONS = {
    "Ciutat Vella": ["ciudad vieja", "old town", "old city", "gothic quarter", "barri gòtic", "barrio gótico",
                     "gòtic", "el raval", "raval", "el born", "born", "barceloneta", "la barceloneta",
                     "casco antiguo"],
    "Eixample": ["ensanche", "l'eixample", "el eixample", "sagrada família", "sant antoni",
                 "dreta de l'eixample", "esquerra de l'eixample", "passeig de gràcia", "fort pienc"],
    "Sants-Montjuïc": ["sants", "montjuïc", "poble sec", "poble-sec", "hostafrancs", "la bordeta",
                       "zona franca", "plaza españa", "plaça espanya"],
    "Les Corts": ["las corts", "corts", "pedralbes", "camp nou"],
    "Sarrià-Sant Gervasi": ["sarrià", "sant gervasi", "san gervasio", "sarrià sant gervasi",
                            "sarrià-san gervasio", "bonanova", "la bonanova", "putxet", "vallvidrera", "galvany"],
    "Gràcia": ["vila de gràcia", "villa de gracia", "vallcarca", "park güell", "camp d'en grassot"],
    "Horta-Guinardó": ["horta", "guinardó", "horta guinardó", "el carmel", "carmel", "vall d'hebron",
                       "la teixonera"],
    "Nou Barris": ["nueve barrios", "9 barris", "trinitat nova", "roquetes", "prosperitat",
                   "turó de la peira", "porta", "vilapicina"],
    "Sant Andreu": ["san andrés", "sant andreu de palomar", "la sagrera", "sagrera", "navas",
                    "trinitat vella", "bon pastor"],
    "Sant Martí": ["san martín", "poblenou", "poble nou", "el poblenou", "diagonal mar", "el clot", "clot",
                   "vila olímpica", "villa olímpica", "22@", "la verneda", "provençals"],
    "L'Hospitalet de Llobregat": ["hospitalet", "l'hospitalet", "hospitalet de llobregat", "la hospitalet",
                                  "l'h", "lh", "bellvitge", "la florida", "collblanc", "santa eulàlia"],
    "Santa Coloma de Gramenet": ["santa coloma", "sta coloma", "sta. coloma", "gramenet"],
    "Esplugues de Llobregat": ["esplugues", "esplugas", "esplugas de llobregat"],
}

# Ciutats amb districtes: el nom (i aquestes formes) equival a tots els seus districtes.
CITIES = {
    "Barcelona": ["bcn", "barna", "barcelona city", "city of barcelona", "ciudad de barcelona",
                  "ciutat de barcelona", "barcelona ciudad", "barcelona capital", "all of barcelona",
                  "anywhere in barcelona", "the whole city", "whole city"],
}

# --- Zones (etiqueta que es mostra a l'usuari -> membres i formes) --------------
# members: llista de llocs, o {"city": X} (districtes de X) o {"not_city": X} (municipis de fora de X).
ZONES = {
    "city centre": {
        "members": ["Ciutat Vella", "Eixample"],
        "phrases": ["centre", "center", "city centre", "city center", "downtown", "central",
                    "central barcelona", "barcelona centre", "barcelona center", "centre of barcelona",
                    "center of barcelona", "centro", "el centro", "centro de barcelona", "barcelona centro",
                    "céntrico", "el centre", "centre de barcelona"],
    },
    "uptown": {
        "members": ["Sarrià-Sant Gervasi", "Les Corts"],
        "phrases": ["uptown", "upper barcelona", "upper part of barcelona", "upper area", "upscale area",
                    "zona alta", "la zona alta", "parte alta", "part alta", "zona alta de barcelona"],
    },
    "seaside": {
        "members": ["Ciutat Vella", "Sant Martí"],
        "phrases": ["seaside", "sea", "by the sea", "near the sea", "beach", "the beach", "near the beach",
                    "close to the beach", "coast", "waterfront", "seafront", "playa", "cerca de la playa",
                    "cerca del mar", "mar", "costa", "platja", "a prop del mar", "a prop de la platja"],
    },
    "north Barcelona": {
        "members": ["Nou Barris", "Sant Andreu", "Horta-Guinardó"],
        "phrases": ["north", "north barcelona", "northern barcelona", "north of barcelona", "barcelona north",
                    "nord", "barcelona nord", "zona nord", "norte", "zona norte", "norte de barcelona"],
    },
    "outskirts": {
        "members": {"not_city": "Barcelona"},
        "phrases": ["outskirts", "outskirts of barcelona", "suburbs", "suburbs of barcelona", "surroundings",
                    "surroundings of barcelona", "around barcelona", "near barcelona", "close to barcelona",
                    "outside barcelona", "outside the city", "metropolitan area", "metro area",
                    "área metropolitana", "área metropolitana de barcelona", "alrededores",
                    "alrededores de barcelona", "afueras", "afueras de barcelona", "extrarradio",
                    "cerca de barcelona", "fuera de barcelona", "rodalies", "voltants", "voltants de barcelona",
                    "àrea metropolitana"],
    },
    "Llobregat side": {
        "members": ["L'Hospitalet de Llobregat", "Esplugues de Llobregat"],
        "phrases": ["llobregat", "llobregat side", "llobregat area", "zona llobregat", "west of barcelona",
                    "west barcelona", "oeste de barcelona", "zona oeste"],
    },
    "Besòs side": {
        "members": ["Santa Coloma de Gramenet", "Sant Andreu", 
        "Sant Martí", "Nou Barris"],
        "phrases": ["besòs", "besos side", "besòs area", "zona besòs", "east of barcelona", "east barcelona",
                    "este de barcelona", "zona este"],
    },
}

# =============================================================================
# Números (bloc 3, segona part): diners, rangs, modificadors i sumes d'habitacions
# =============================================================================

# Paraules-número (anglès, castellà, català). "set" (7 en català) s'omet: xoca amb l'anglès.
NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "cero": 0, "uno": 1, "una": 1, "un": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14,
    "quince": 15, "dieciséis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
    "veintiuno": 21, "veintiún": 21, "veintiuna": 21, "veintidós": 22, "veintitrés": 23,
    "veinticuatro": 24, "veinticinco": 25, "veintiséis": 26, "veintisiete": 27, "veintiocho": 28,
    "veintinueve": 29, "treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
    "ochenta": 80, "noventa": 90, "cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
    "trescientos": 300, "trescientas": 300, "cuatrocientos": 400, "cuatrocientas": 400,
    "quinientos": 500, "quinientas": 500, "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
    "setecientas": 700, "ochocientos": 800, "ochocientas": 800, "novecientos": 900, "novecientas": 900,
    "dues": 2, "quatre": 4, "cinc": 5, "sis": 6, "vuit": 8, "nou": 9, "deu": 10, "onze": 11, "dotze": 12,
    "tretze": 13, "catorze": 14, "quinze": 15, "setze": 16, "disset": 17, "divuit": 18, "dinou": 19,
    "vint": 20, "trenta": 30, "quaranta": 40, "cinquanta": 50, "seixanta": 60, "setanta": 70,
    "vuitanta": 80, "noranta": 90, "cent": 100,
}
HUNDRED_WORDS = ["hundred", "hundreds", "cents"]                   # "thirteen hundred", "dos-cents"
THOUSAND_WORDS = ["thousand", "thousands", "k", "mil", "miles"]    # també sufix: "250k", "250 mil"
MILLION_WORDS = ["million", "millions", "millón", "millones", "milió", "milions", "mill"]
PRICE_ONLY_SCALES = {"m": 1_000_000}                                # "1.2m" (en m2 'm' és la unitat)
NUMBER_CONNECTORS = ["and", "y", "i"]                               # "one hundred and twenty", "vint-i-cinc"

# Planta: "ground floor", "planta baja"... = 0; ordinals.
GROUND_FLOOR = ["ground", "ground floor", "planta baja", "bajo", "bajos", "baja", "planta baixa",
                "baixos", "baixa", "pb"]
ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
    "ninth": 9, "tenth": 10,
    "primero": 1, "primer": 1, "primera": 1, "segundo": 2, "segunda": 2, "tercero": 3, "tercer": 3,
    "tercera": 3, "cuarto": 4, "cuarta": 4, "quinto": 5, "quinta": 5, "sexto": 6, "sexta": 6,
    "séptimo": 7, "octavo": 8, "noveno": 9, "décimo": 10,
    "segon": 2, "segona": 2, "quart": 4, "quarta": 4, "cinquè": 5, "cinquena": 5, "sisè": 6, "sisena": 6,
    "setè": 7, "setena": 7, "vuitè": 8, "vuitena": 8, "novè": 9, "novena": 9, "desè": 10, "desena": 10,
}

# Modificadors. min/max "_strict" = estricte ("more than 2" bedrooms -> 3 o més).
# Es busquen just abans del número o just després (saltant unitats: "200k max", "3 or more").
NUMERIC_MODIFIERS = {
    "min": ["at least", "minimum", "min", "no less than", "not less than", "or more", "or above", "and up",
            "and above", "or bigger", "or larger", "or higher", "+", "from", "starting at", "starting from",
            "al menos", "por lo menos", "como mínimo", "mínimo", "o más", "a partir de", "desde",
            "almenys", "com a mínim", "mínim", "o més"],
    "min_strict": ["more than", "over", "above", "greater than", "bigger than", "larger than", "higher than",
                   ">", "más de", "més de", "superior a", "por encima de"],
    "max": ["at most", "maximum", "max", "up to", "no more than", "not more than", "or less", "or fewer",
            "or under", "or below", "or lower", "tops", "as much as", "hasta", "como máximo", "máximo",
            "como mucho", "no más de", "o menos", "fins a", "com a màxim", "màxim", "o menys"],
    "max_strict": ["less than", "under", "below", "fewer than", "cheaper than", "smaller than", "lower than",
                   "<", "menos de", "menys de", "por debajo de", "inferior a"],
    "approx": ["around", "about", "approximately", "approx", "roughly", "more or less", "circa", "ish", "~",
               "aprox", "aproximadamente", "alrededor de", "unos", "unas", "sobre", "más o menos",
               "cerca de", "uns", "unes", "més o menys", "aproximadament", "entorn de", "al voltant de"],
    "exact": ["exactly", "just", "precisely", "exacto", "exactamente", "justo", "exactament", "justament"],
}

# Rangs: "between 2 and 3" (cal 'between'/'entre'); "2 to 3", "2-3", "de 2 a 3", "2 or 3" (no cal).
RANGE_PREFIXES = ["between", "entre"]
RANGE_AND = ["and", "y", "i"]
RANGE_CONNECTORS = ["to", "-", "a", "hasta", "until", "till", "fins", "fins a", "or", "o"]

# Sumes d'habitacions: "1 big bedroom and 1 small one", "dos dobles y una individual".
SUM_CONNECTORS = ["and", "y", "i", "plus", "+", "más", "més", "|", "with", "con", "amb"]
ROOM_ARTICLES = ["a", "an", "another", "otro", "otra", "altre", "altra"]   # valen 1 davant d'una paraula
ROOM_NOUNS = {
    "bedrooms": ["bedroom", "bedrooms", "room", "rooms", "habitación", "habitaciones", "dormitorio",
                 "dormitorios", "cuarto", "cuartos", "habitació", "habitacions", "dormitori", "dormitoris",
                 "suite", "suites", "double", "doubles", "single", "singles", "doble", "dobles",
                 "individual", "individuales", "individuals"],
    "bathrooms": ["bathroom", "bathrooms", "bath", "baths", "toilet", "toilets", "wc", "washroom",
                  "shower room", "shower rooms", "en suite", "ensuite", "baño", "baños", "cuarto de baño",
                  "cuartos de baño", "aseo", "aseos", "lavabo", "lavabos", "bany", "banys"],
}
# Paraules que, si segueixen un número, indiquen que NO compta habitacions ("a house with 3 bedrooms").
OTHER_NOUNS = ["euro", "euros", "eur", "m2", "meter", "meters", "metre", "metres", "square", "floor", "floors",
               "planta", "plantas", "year", "years", "año", "años", "any", "anys", "people", "person",
               "persons", "adult", "adults", "kid", "kids", "child", "children", "persona", "personas",
               "niño", "niños", "hijo", "hijos", "fill", "fills", "nen", "nens", "house", "flat", "apartment",
               "home", "piso", "casa", "pis", "car", "cars", "coche", "coches", "cotxe", "cotxes", "pet", "pets",
               "dog", "dogs", "cat", "cats", "perro", "perros", "gato", "gatos", "gos", "gossos", "gat", "gats"]
# Unitats que es poden saltar entre un número i el seu modificador ("200k euros max").
UNIT_WORDS = ["euro", "euros", "eur", "e", "m2", "m", "meter", "meters", "metre", "metres", "square", "sq",
              "sqm", "floor", "planta", "per", "month", "mes", "al", "the", "st", "nd", "rd", "th"]

# =============================================================================
# Correccions (iteració 3)
# =============================================================================

# Noms amb què l'usuari es pot referir a cada pregunta ("change the budget", "cambiar la zona").
SLOT_NAMES = {
    "type": ["buy or rent", "rent or buy", "operation", "renting or buying", "buying or renting",
             "comprar o alquilar", "alquilar o comprar", "comprar o llogar"],
    "price": ["budget", "price", "money", "presupuesto", "precio", "pressupost", "preu"],
    "location": ["area", "location", "zone", "place", "district", "neighbourhood", "neighborhood", "city",
                 "zona", "barrio", "ubicación", "lugar", "sitio", "barri", "lloc", "ubicació"],
    "property_type": ["property type", "type of property", "kind of property", "type of home", "kind of home",
                      "tipo de inmueble", "tipo de vivienda", "tipus d'immoble", "tipus d'habitatge"],
    "shared": ["sharing", "shared", "compartir", "compartido", "compartit"],
    "bedrooms": ["bedrooms", "bedroom", "rooms", "habitaciones", "dormitorios", "habitacions", "dormitoris"],
    "bathrooms": ["bathrooms", "bathroom", "baños", "baño", "banys", "bany"],
    "square_meters": ["size", "square metres", "square meters", "m2", "metros", "superficie", "tamaño",
                      "metres", "mida"],
    "condition": ["condition", "estado", "estat"],
    "floor": ["floor", "planta"],
    "terrace": ["terrace", "terraza", "terrassa"],
    "elevator": ["elevator", "lift", "ascensor"],
    "garden": ["garden", "jardín", "jardí"],
    "parking": ["parking", "parking space", "garage", "aparcamiento", "garaje", "pàrquing", "garatge"],
    "furnished": ["furnished", "furniture", "amueblado", "muebles", "moblat", "mobles"],
    "pets": ["pets", "pet", "mascotas", "mascota", "mascotes"],
    "commercial_use": ["business", "commercial use", "uso comercial", "negocio", "negoci", "ús comercial"],
}
# Marcadors explícits de canvi: el que segueix ha de dir QUÈ es canvia.
CHANGE_MARKERS = ["change", "change the", "i want to change", "i'd like to change", "can i change", "let me change",
                  "modify", "edit", "go back to", "cambiar", "cambia", "quiero cambiar", "modificar", "canviar",
                  "canvia", "vull canviar", "tornar a"]
# Marcadors de correcció natural: "actually, Gràcia" (el valor es busca entre les respostes anteriors).
CORRECTION_MARKERS = ["actually", "i meant", "i mean", "wait", "correction", "en realidad", "quiero decir",
                      "perdón", "perdona", "de hecho", "en realitat", "vull dir", "perdó"]
# Tornar a la pregunta anterior (només si és tota la resposta).
BACK_COMMANDS = ["back", "go back", "previous", "previous question", "atrás", "volver", "pregunta anterior",
                 "enrere", "tornar"]
# Paraules buides entre el nom de la pregunta i el valor nou ("change the area TO Gràcia").
VALUE_FILLERS = ["to", "into", "for", "is", "be", "the", "a", "an", "por", "per", "a", "el", "la", "de", "en",
                 "al", "que", "sea", "sigui", "it", "please", "por favor", "si us plau"]
# Exploració dels resultats (iteració 3). Només compten si són tota la resposta.
# ("back"/"previous" aquí volen dir la vivenda anterior, no la pregunta anterior.)
RESULTS_ALL = ["all", "show all", "see all", "all of them", "show them all", "everything", "every home",
               "todas", "todos", "ver todas", "totes", "tots", "veure-les totes"]
RESULTS_NEXT = ["next", "next one", "next home", "following", "more", "siguiente", "la siguiente", "otra",
                "següent", "la següent", "una altra"]
RESULTS_PREV = ["prev", "previous", "previous one", "back", "go back", "anterior", "la anterior", "atrás",
                "l'anterior", "enrere"]
