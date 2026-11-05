"""Proves de la iteració 3 (primera tanda): confirmació de sumes sense desglossament, comanda 'show me',
oferta d'anar al resum quan una resposta deixa 0 vivendes i resultats ordenats.

Execució:  python -m recomanador.tests.test_iter3
"""

from recomanador import run
from recomanador.data_loader import load_data
from recomanador.io_adapter import ScriptedIO
from recomanador.recommender import to_number
from recomanador.tests.common import answers_for, conversation, run_case, run_suite
from recomanador import nlg
from recomanador.numeric import Range

STEPS = dict(type="rent", price="1.200", location="Gràcia", property_type="flat", shared="No")  # -> només la 18


def ordered_run(answers):
    """Com run_case, però conservant l'ordre de presentació dels resultats."""
    io = ScriptedIO(list(answers) + ["quit"])  # 'quit' per sortir del menú de resultats
    state, houses = run(io=io, picker=nlg.first_choice)
    return houses, state, io


def check_sum_confirmation():
    text = run_case(answers_for(bedrooms="1 big bedroom and 1 small one", then={"bedrooms": ["yes"]}))[2].text()
    errors = []
    if "So that's 2 bedrooms in total, is that right? (Yes / No)" not in text:
        errors.append("no surt la nova confirmació de la suma")
    if "(1 + 1)" in text:
        errors.append("encara surt el desglossament '(1 + 1)'")
    return errors


def check_show_me():
    errors = []
    # a la 3a pregunta: resultats amb el que hi ha (lloguer <= 1.200), sense confirmació ni més preguntes
    ids, state, io = run_case(["rent", "1.200", "show me"])
    text = io.text()
    if not state.stopped_early or state.exited:
        errors.append("'show me' no atura el qüestionari com a petició de resultats")
    if "[4/" in text:
        errors.append("després de 'show me' es continua preguntant")
    if "Are you sure" in text:
        errors.append("'show me' demana confirmació (només ho ha de fer 'quit')")
    for sentence in ["Sure! Let's look at what we have so far.",
                     "Here's what I've noted so far: you're looking for a home to rent, up to 1,200 euros a month.",
                     "Good news! I found 13 homes for you:"]:
        if sentence not in text:
            errors.append(f"falta: {sentence!r}")
    if len(ids) != 13:
        errors.append(f"'show me' a la 3a pregunta hauria de donar 13 vivendes, en dona {len(ids)}")
    # al principi: totes les vivendes i cap resum
    ids, state, io = run_case(["Show me!"])
    if len(ids) != 50 or "noted so far" in io.text():
        errors.append("'show me' a la 1a pregunta: s'esperaven les 50 vivendes sense resum")
    # dins d'una confirmació ("Did you mean...?")
    _, state, _ = run_case(["any", "any", "Eixampel", "resultados"])
    if not state.stopped_early:
        errors.append("'resultados' no funciona dins d'una confirmació")
    # una frase que conté "show me" no és la comanda
    _, state, _ = run_case(answers_for(location="show me something in Gràcia"))
    if state.stopped_early:
        errors.append("una resposta que només conté 'show me' s'ha pres com a comanda")
    if "Type 'show me' at any time" not in run_case(["quit", "yes"])[2].text():
        errors.append("la benvinguda no explica 'show me'")
    return errors


def check_offer_summary():
    errors = []
    # manté "2 bedrooms" (0 vivendes) i accepta anar al resum
    ids, state, io = run_case(answers_for(**STEPS, bedrooms="2", then={"bedrooms": ["no", "yes"]}))
    text = io.text()
    if "Since no home matches right now, would you like me to stop here and show you a summary?" not in text:
        errors.append("no s'ofereix el resum en mantenir una resposta sense vivendes")
    if not state.stopped_early or ids or "[7/" in text:
        errors.append("en acceptar l'oferta no s'atura amb 0 resultats")
    if "with at least 2 bedrooms" not in text.split("<clear>")[1]:
        errors.append("el resum no inclou la resposta que s'ha mantingut")
    # la rebutja: continua
    _, state, io = run_case(answers_for(**STEPS, bedrooms="2", then={"bedrooms": ["no", "no"]}))
    if state.stopped_early or "OK, let's continue." not in io.text() or "[7/" not in io.text():
        errors.append("en rebutjar l'oferta la conversa no continua")
    return errors


def check_ordering():
    errors = []
    houses, _, io = ordered_run(answers_for(type="both", location="Les Corts"))  # 27 (lloguer) + 28, 29 (vendes)
    if [h["id"] for h in houses] != [27, 28, 29]:
        errors.append(f"ordre amb tipus 'any': {[h['id'] for h in houses]} (esperat [27, 28, 29])")
    text = io.text()
    for sentence in ["Homes to rent come first, then homes to buy, each from the cheapest to the most expensive.",
                     "Homes to rent:", "Homes to buy:"]:
        if sentence not in text:
            errors.append(f"falta: {sentence!r}")
    if not (text.find("Homes to rent:") < text.find("#27 ·") < text.find("Homes to buy:") < text.find("#28 ·")):
        errors.append("les capçaleres de grup no van abans de les seves vivendes")

    houses, _, io = ordered_run(answers_for(type="sale", location="Barcelona", property_type="flat"))
    prices = [to_number(h["price"]) for h in houses]
    if prices != sorted(prices):
        errors.append(f"vendes no ordenades per preu: {prices}")
    if "I've sorted them from the cheapest to the most expensive." not in io.text() or "Homes to buy:" in io.text():
        errors.append("amb un sol tipus: cal la frase d'ordenació i no cal capçalera de grup")

    _, _, io = ordered_run(answers_for(location="Les Corts", property_type="chalet"))  # una sola vivenda
    if "sorted" in io.text():
        errors.append("amb una sola vivenda no cal explicar l'ordre")
    return errors


def check_bedrooms_question_and_layout():
    errors = []
    text = run_case(answers_for(type="rent", shared="Yes", bedrooms="any"))[2].text()
    if "How many bedrooms should the whole home have (counting your own room if you share)?" not in text:
        errors.append("si accepta compartir, la pregunta d'habitacions no s'aclareix")
    text = run_case(answers_for(type="rent", shared="No"))[2].text()
    if "How many bedrooms do you need?" not in text or "whole home" in text:
        errors.append("si no comparteix, la pregunta d'habitacions ha de ser la normal")
    lines = run_case(answers_for(property_type="chalet") + ["all"])[2].text().splitlines()
    # cada fitxa: línia en blanc, "Home i of n:" i la fitxa
    blocks = [i for i, l in enumerate(lines) if l.startswith("Home ") and " · #" in l]
    if not blocks or any(lines[i - 1] != "" or not lines[i + 1].startswith("  ") for i in blocks):
        errors.append("les vivendes no estan separades per una línia en blanc")
    return errors


def check_show_me_hint():
    text = conversation(run_case(answers_for(**STEPS))[2].text())  # passa a 2 i després a 1 vivenda
    hint = "Type 'show me' if you'd like to see them now."
    errors = [] if text.count(hint) == 1 else [f"la pista de 'show me' surt {text.count(hint)} cops (ha de ser 1)"]
    if text.find(hint) < text.find("Only 2 homes left"):
        errors.append("la pista no surt just quan queden poques vivendes")
    return errors


def check_near_misses():
    errors = []
    # lloguer <= 1.200 a l'Eixample: cap. Es manté i es va al resum.
    houses, state, io = ordered_run(answers_for(type="rent", price="1.200", location="Eixample",
                                                then={"location": ["no", "yes"]}))
    text = io.text()
    if houses or "No home matches everything, but these come close:" not in text:
        errors.append("sense resultats no es mostren les casi coincidències")
    reasons = text.count("· everything except the area")  # una línia per casi coincidència al resum
    if reasons != 5:
        errors.append(f"s'esperaven 5 casi coincidències que només fallen la zona, n'hi ha {reasons}")
    shown = [int(l.split("#")[1].split(" ")[0]) for l in text.split("<clear>")[1].splitlines()
             if l.startswith("  #")]
    by_id = {h["id"]: h for h in load_data()["houses"]}
    prices = [to_number(by_id[i]["price"]) for i in shown]
    if prices != sorted(prices) or any(by_id[i]["type"] != "rent" for i in shown):
        errors.append(f"casi coincidències mal ordenades o d'un altre tipus d'operació: {shown}")
    return errors


def check_corrections():
    errors = []
    # canvi amb valor nou, des d'una pregunta posterior
    _, state, io = run_case(answers_for(**STEPS, bedrooms="1", retries={"bedrooms": ["change the budget to 900"]}))
    if state.preferences["price"] != Range(None, 900) or state.preferences["bedrooms"] != Range(1, None):
        errors.append("'change the budget to 900' no canvia el pressupost o no torna a la pregunta actual")
    # canvi sense valor: es torna a preguntar
    _, state, _ = run_case(["rent", "1.200", "Gràcia", "change the area", "Sant Martí"] + ["any"] * 20)
    if state.preferences["location"] != ["Sant Martí"]:
        errors.append("'change the area' no torna a preguntar la zona")
    # correcció natural
    _, state, _ = run_case(["rent", "any", "Eixample", "actually, Gràcia"] + ["any"] * 20)
    if state.preferences["location"] != ["Gràcia"] or state.preferences.get("property_type") != "any":
        errors.append("'actually, Gràcia' no corregeix la zona des de la pregunta següent")
    # 'back' = pregunta anterior en l'ordre del qüestionari
    _, state, io = run_case(["rent", "1.200", "back", "800"] + ["any"] * 20)
    if state.preferences["price"] != Range(None, 800):
        errors.append("'back' no torna a la pregunta anterior")
    text = run_case(["back", "rent", "quit", "yes"])[2].text()
    if "We're at the very first question" not in text:
        errors.append("'back' a la primera pregunta no s'explica")
    # sense dir què, o una cosa encara no preguntada
    text = run_case(["rent", "change", "change the garden", "quit", "yes"])[2].text()
    if "Tell me what you'd like to change" not in text or "I haven't asked you about the garden" not in text:
        errors.append("no s'expliquen les correccions incompletes o d'una pregunta no feta")
    # una resposta normal amb 'actually' a la pregunta actual no és una correcció
    _, state, _ = run_case(["rent", "any", "actually, Gràcia"] + ["any"] * 20)
    if state.preferences["location"] != ["Gràcia"] or "change" in state.preferences:
        errors.append("'actually, Gràcia' a la pregunta de la zona s'ha de prendre com a resposta")
    return errors


def check_correction_consistency():
    errors = []
    # lloguer -> compra: el pressupost (depèn del tipus) i compartir (només lloguer) s'esborren i es repregunten
    _, state, io = run_case(["rent", "1.200", "any", "flat", "no", "change buy or rent", "buy", "400k"] + ["any"] * 20)
    text = io.text()
    if state.preferences["type"] != "sale" or state.preferences["price"] != Range(None, 400000):
        errors.append("en canviar a compra no es torna a preguntar el pressupost")
    if "shared" in state.preferences:
        errors.append("en canviar a compra es manté la resposta de compartir (només lloguer)")
    if "no home would match" in text:
        errors.append("en canviar el tipus s'avisa de 0 vivendes amb el pressupost antic")
    # pis -> casa: el jardí passa a aplicar-se i es pregunta
    _, state, io = run_case(["sale", "any", "any", "flat", "any", "actually, a house"] + ["any"] * 20)
    if state.preferences["property_type"] != ["house"] or "garden" not in state.preferences:
        errors.append("en canviar a casa no es pregunta pel jardí")
    # en l'avís de 0 vivendes, respondre amb el valor nou = canviar-lo
    _, state, _ = run_case(answers_for(type="rent", price="1.200", location="Eixample",
                                       then={"location": ["actually, Gràcia"]}))
    if state.preferences["location"] != ["Gràcia"]:
        errors.append("a 'Do you want to change it?', un valor nou no s'accepta com a canvi")
    # 'show me' a mig corregir: es manté el valor antic
    _, state, _ = run_case(["rent", "1.200", "Gràcia", "change the area", "show me"])
    if state.preferences.get("location") != ["Gràcia"] or not state.stopped_early:
        errors.append("si es demanen els resultats a mig corregir, es perd el valor antic")
    return errors


def check_silent_correction():
    """Bug reportat: "actually i want to buy" imprimia tot el procés del canvi (pregunta, reacció, 'continue')."""
    _, state, io = run_case(["rent", "actually i want to buy", "400k", "show me"])
    text = conversation(io.text())
    after = text.split("Your answer: actually i want to buy")[1].split("\n[")[0]
    errors = []
    if after.strip() != "Done, I've changed the operation to buying.":
        errors.append(f"la correcció amb valor ha de ser una sola línia; surt: {after.strip()!r}")
    if state.preferences.get("type") != "sale" or state.preferences.get("price") != Range(None, 400000):
        errors.append("la correcció no canvia el tipus o no es torna a preguntar el pressupost")
    return errors


def check_quit_and_near_layout():
    errors = []
    ids, state, io = run_case(["rent", "1.200", "quit", "yes"])
    text = io.text()
    if ids or " · #" in text or "noted so far" in text or "Let me recap" in text:
        errors.append("'quit' no ha de mostrar resum ni vivendes")
    if "If you'd like to see the homes first, type 'show me'" not in text:
        errors.append("la confirmació de sortida no recorda 'show me'")
    ids, state, _ = run_case(["rent", "1.200", "quit", "show me"])
    if len(ids) != 13 or state.exited:
        errors.append("'show me' a la confirmació de sortida no mostra els resultats")
    # lloguer <= 1.200 a l'Eixample -> 0; es manté ('no') i s'accepta el resum ('yes'); després 'all'
    lines = run_case(["rent", "1.200", "Eixample", "no", "yes", "all"])[2].text().splitlines()
    fiches = [l for l in lines if l.startswith("Home ") and " · #" in l]
    if not fiches or any("· It matches everything except" not in l for l in fiches):
        errors.append("en les casi coincidències, el motiu ha d'anar just abans de la fitxa")
    return errors


def check_change_after_results():
    errors = []
    goodbye = load_data()["end_message"][0]
    # només les comandes de sortida acaben ("no" ja no: "change pets to no" la tancava)
    for reply in ["quit", "exit"]:
        text = run_case(["rent", "show me", reply], finish=False)[2].text()
        if "What would you like to do?" not in text or not text.rstrip().endswith(goodbye):
            errors.append(f"'{reply}' a 'Would you like to change anything?' no acaba la conversa")
    # 'yes' -> què? -> 'the budget' -> es torna a preguntar -> resultats nous
    ids, state, io = run_case(answers_for(**STEPS) + ["yes", "the budget", "900", "quit"], finish=False)
    text = io.text()
    if "Sure, what would you like to change?" not in text or state.preferences["price"] != Range(None, 900):
        errors.append("'yes' + 'the budget' + '900' no canvia el pressupost")
    if text.count("<clear>") != 2:
        errors.append("després d'un canvi no es tornen a mostrar el resum i els resultats")
    # després de 'show me', una correcció no reprèn el qüestionari
    ids, state, io = run_case(["rent", "1.200", "Gràcia", "show me", "actually, Sant Martí", "quit"], finish=False)
    if ids != [35] or "[4/" in io.text().split("What would you like to do?")[1]:
        errors.append("després de 'show me', corregir la zona ha de donar la 35 sense reprendre preguntes")
    # al final es pot afegir una pregunta que no s'havia fet (després de 'show me')
    _, state, _ = run_case(["sale", "show me", "change the floor", "3", "quit"], finish=False)
    if state.preferences.get("floor") != Range(3, None):
        errors.append("al final no es pot afegir una pregunta no feta ('change the floor')")
    # dues respostes no enteses seguides tanquen la conversa
    text = run_case(["rent", "show me", "blah", "blah"], finish=False)[2].text()
    if not text.rstrip().endswith(goodbye):
        errors.append("dues respostes no enteses a la pregunta final no acaben la conversa")
    return errors


def explore(commands, base=("rent", "1.200", "Gràcia", "show me")):
    """Conversa fins als resultats (per defecte: lloguer <= 1.200 a Gràcia -> #32, #18) + `commands`."""
    return run_case(list(base) + list(commands), finish=False)[2].text().split("<clear>")[-1]


def headers(text):
    """Capçaleres de fitxa, sense el número de la vivenda: "Home 1 of 2"."""
    return [l.split(" · ")[0] for l in text.splitlines() if l.startswith("Home ") and " of " in l]


def check_explore_results():
    errors = []
    text = explore(["quit"])
    for line in ["  #32 · room in a shared flat in Gràcia · 575 euros/month", "  #18 · flat in Gràcia · 850 euros/month",
                 "or a home's number (e.g. 32) to see it"]:
        if line not in text:
            errors.append(f"resum: falta {line!r}")
    if " · #" in text:
        errors.append("el resum no ha de mostrar fitxes fins que es demanen")
    # next / prev, límits i 'back' com a vivenda anterior
    text = explore(["next", "next", "next", "prev", "back", "back", "quit"])
    if headers(text) != ["Home 1 of 2", "Home 2 of 2", "Home 1 of 2"]:
        errors.append(f"navegació next/prev: {headers(text)}")
    if "That was the last one." not in text or "That's the first one." not in text:
        errors.append("no s'avisa en arribar al final o al principi")
    if "Sure, let's change" in text:
        errors.append("'back' als resultats ha de ser la vivenda anterior, no una correcció")
    # per número (i després 'next' segueix l'ordre)
    text = explore(["#18", "prev", "house 18", "7", "quit"])
    if headers(text) != ["Home 2 of 2", "Home 1 of 2", "Home 2 of 2"] or "Home 2 of 2 · #18" not in text:
        errors.append(f"vivenda per número: {headers(text)}")
    if "Home #7 isn't among these results. The available ones are: #32, #18." not in text:
        errors.append("un número que no és als resultats no s'explica")
    # all
    text = explore(["all", "quit"])
    if headers(text) != ["Home 1 of 2", "Home 2 of 2"] or "Anything else?" not in text:
        errors.append("'all' no mostra totes les fitxes")
    # un canvi des de l'exploració torna a fer el resum; 'show me' també
    ids, state, io = run_case(["rent", "1.200", "Gràcia", "show me", "next", "change the budget to 700", "quit"],
                              finish=False)
    if ids != [32] or io.text().count("<clear>") != 2:
        errors.append("un canvi des de l'exploració no actualitza els resultats")
    if explore(["show me", "quit"]).count("#32 ·") != 1:
        errors.append("'show me' als resultats no torna a mostrar el resum")
    # casi coincidències: també s'exploren, amb el motiu
    text = explore(["next", "quit"], base=("rent", "1.200", "Eixample", "no", "yes"))
    if "Home 1 of 5 · #17 · It matches everything except the area." not in text:
        errors.append("les casi coincidències no s'exploren amb el seu motiu")
    # dues respostes no enteses seguides acaben
    if not explore(["blah", "blah"]).rstrip().endswith(load_data()["end_message"][0]):
        errors.append("dues respostes no enteses als resultats no acaben la conversa")
    return errors


def check_correction_messages():
    errors = []
    text = run_case(["rent", "any", "Eixample", "actually, Gràcia", "change the budget to 900", "quit", "yes"])[2].text()
    for line in ["Done, I've changed the area to Gràcia.", "Done, I've updated the budget: up to 900 euros a month."]:
        if line not in text:
            errors.append(f"falta: {line!r}")
    return errors


# lloguer <= 1.200, Gràcia, pis, no compartit -> només la 18 (que no admet mascotes)
PETS_BASE = ["rent", "1.200", "Gràcia", "flat", "no"] + ["any"] * 9


def check_results_menu_fixes():
    errors = []
    # "change pets to no" als resultats és un canvi, no un "no" que tanca la conversa (cas reportat)
    _, state, io = run_case(PETS_BASE + ["yes", "no", "yes", "change pets to no"])
    if state.preferences.get("pets") != "No" or io.text().count("<clear>") != 2:
        errors.append("'change pets to no' als resultats no s'aplica")
    # "no" sol ja no acaba: només les comandes de sortida
    text = explore(["no", "quit"])
    if "Sorry, I didn't get that." not in text or "'quit' to finish" not in text:
        errors.append("'no' als resultats no s'ha de prendre com a sortida")
    # després d'una fitxa es torna a mostrar la llista
    text = explore(["18", "quit"])
    if "Your results:\n  #32 · room in a shared flat in Gràcia · 575 euros/month\n  #18 · flat in Gràcia · 850 euros/month" not in text:
        errors.append("després de mostrar una fitxa no es torna a mostrar la llista de resultats")
    # una sola vivenda: la fitxa surt directament
    text = explore(["quit"], base=("rent", "1.200", "Gràcia", "flat", "no", "show me"))
    if "Home 1 of 1 · #18" not in text or "Flat for rent in Gràcia (Barcelona)" not in text:
        errors.append("amb una sola vivenda, la fitxa no surt directament")
    return errors


def check_zero_baseline_on_correction():
    """Cas reportat: després d'acceptar 0 vivendes (mascotes), tornar a corregir la mateixa resposta
    tornava a avisar "until now we had one home" i a oferir el resum, com si l'estat actual no fos 0."""
    errors = []
    _, state, io = run_case(PETS_BASE + ["yes", "no", "yes", "change pets to yes"])
    after_results = io.text().split("<clear>", 1)[1]
    if "no home would match" in after_results or "stop here and show you a summary" in after_results:
        errors.append("es torna a avisar de 0 vivendes quan ja n'hi havia 0")
    # de >0 a 0 després dels resultats: avís amb el recompte real d'abans i sense oferir el resum
    # (500: hi ha lloguers d'aquest preu, però no a Gràcia; amb 300 sortiria l'avís de "fora de rang")
    _, state, io = run_case(["rent", "1.200", "Gràcia", "show me", "change the budget to 500", "no"])
    after_results = io.text().split("<clear>", 1)[1]
    if "(until now we had 2 homes)" not in after_results:
        errors.append("una correcció que deixa 0 vivendes no avisa amb el recompte d'abans")
    if "stop here and show you a summary" in after_results:
        errors.append("després dels resultats no s'ha d'oferir 'anar al resum'")
    if state.preferences.get("price") != Range(None, 500):
        errors.append("en mantenir la correcció ('no' a canviar-la) no es desa")
    return errors


def check_natural_house_description():
    """Fitxa en llenguatge natural: totes les dades agrupades en frases (casos variats)."""
    from recomanador import nlg
    data = load_data()
    by_id = {h["id"]: h for h in data["houses"]}
    expected = {
        18: "Flat for rent in Gràcia (Barcelona), 850 euros a month. It has 1 bedroom and 1 bathroom, 50 m2 on the "
            "4th floor, and it is newly built. It comes with an elevator, a terrace and furniture. Pets are not allowed.",
        32: "Room in a shared flat for rent in Gràcia (Barcelona), 575 euros a month per room.",
        15: "It has 2 rooms and 1 bathroom, 75 m2 on the ground floor",           # local: 'rooms'
        2: "It has 4 bedrooms and 2 bathrooms, 120 m2, and it is in good condition.",  # casa: sense planta
        4: "It doesn't have an elevator, a terrace or a parking space.",          # sense extres: es diu
        29: "Chalet for sale in Les Corts (Barcelona), 1,298,000 euros.",
    }
    errors = []
    for house_id, fragment in expected.items():
        text = " ".join(nlg.describe_house(data, by_id[house_id]))
        if fragment not in text:
            errors.append(f"#{house_id}: falta {fragment!r} a {text!r}")
    if "Pets" in " ".join(nlg.describe_house(data, by_id[29])):
        errors.append("en una compra no s'han d'esmentar les mascotes")
    return errors


def zones_said(data, sentence):
    """Oracle independent: quines zones diu la frase de zones disponibles (desfent 'every district' i 'except')."""
    districts = {h["location"] for h in data["houses"] if h["city"] == "Barcelona" and h["location"] != "Barcelona"}
    head, _, missing = sentence.partition(" except ")
    said = {loc for loc in {h["location"] for h in data["houses"]} if loc in head}
    if "every district of Barcelona" in head:
        said |= {d for d in districts if d not in missing}
    return said


def check_available_zones():
    """Amb la pregunta de la zona, les zones on hi ha vivendes que encaixen amb la resta de respostes."""
    from recomanador.recommender import find_suitable_houses
    data = load_data()
    errors = []
    # 1) A la conversa: just després de la pregunta (i abans de respondre), i només amb la de la zona.
    text = run_case(["rent", "900", "Gràcia", "quit", "yes"], finish=False)[2].text()
    expected = ("Which area would you like to live in?\nSo far, there are homes for you in Barcelona (Ciutat Vella, "
                "Gràcia, Nou Barris, Sant Andreu, Sant Martí and Sants-Montjuïc), Esplugues de Llobregat and Santa "
                "Coloma de Gramenet.\nYour answer: Gràcia")
    if expected not in text:
        errors.append("la frase de zones no surt (o no és la prevista) just després de la pregunta")
    if text.count("there are homes for you in") != 1:
        errors.append("la frase de zones surt amb altres preguntes")
    # 2) Contingut, amb un oracle independent: exactament les zones amb vivendes que compleixen la resta.
    for operation, budgets in (("rent", range(400, 2600, 50)), ("sale", range(100000, 1500000, 25000))):
        for budget in budgets:
            for kind in (None, "flat", "house"):
                prefs = {"type": operation, "price": Range(None, budget)}
                if kind:
                    prefs["property_type"] = [kind]
                houses = find_suitable_houses(data, prefs)
                io = ScriptedIO([])
                nlg.print_available_zones(io, data, houses)
                said = zones_said(data, io.text())
                real = {h["location"] for h in houses}
                if said != real:
                    errors.append(f"{prefs}: diu {sorted(said)}, n'hi ha a {sorted(real)}")
                if len(real) == 1 and "the only area" not in io.text():
                    errors.append(f"{prefs}: una sola zona sense la formulació de zona única")
    io = ScriptedIO([])
    nlg.print_available_zones(io, data, [])
    if io.text():
        errors.append("sense vivendes no s'ha de dir res")
    # 3) Correccions: sense valor es torna a preguntar (amb la frase); amb valor, una sola línia (sense frase).
    base = ["rent", "900", "Gràcia"]
    again = run_case(base + ["change the area", "Eixample", "quit", "yes"], finish=False)[2].text()
    silent = run_case(base + ["change the area to Eixample", "quit", "yes"], finish=False)[2].text()
    lines = [line for line in again.split("\n") if "there are homes for you in" in line]
    if len(lines) != 2:
        errors.append("en tornar a preguntar la zona (correcció sense valor) no surt la frase")
    elif lines[0] != lines[1]:  # la zona antiga (Gràcia) no ha de filtrar les zones disponibles
        errors.append(f"en la correcció, la frase depèn del valor antic: {lines[1]!r}")
    if silent.count("there are homes for you in") != 1:
        errors.append("una correcció amb valor no ha de tornar a mostrar la frase")
    # 4) Zona sense vivendes -> "la vols canviar?" -> sí: es torna a dir on n'hi ha.
    retry = run_case(["rent", "600", "Les Corts", "yes", "Gràcia", "quit", "yes"], finish=False)[2].text()
    after_retry = retry.split("let's try again:")[-1].split("Your answer:")[0]
    if "there are homes for you in Barcelona (Gràcia" not in after_retry:
        errors.append("en tornar a demanar la zona després de l'avís de 0 vivendes no surt la frase")
    return errors


CHECKS = [
    ("confirmació de sumes sense '(1 + 1)'", check_sum_confirmation),
    ("'show me': en qualsevol moment, sense confirmació, amb resum parcial", check_show_me),
    ("oferta d'anar al resum quan una resposta mantinguda deixa 0 vivendes", check_offer_summary),
    ("resultats ordenats per preu i agrupats per operació", check_ordering),
    ("pregunta d'habitacions si es comparteix i separació entre vivendes", check_bedrooms_question_and_layout),
    ("pista de 'show me' (un sol cop) quan queden poques vivendes", check_show_me_hint),
    ("casi coincidències quan no hi ha resultats", check_near_misses),
    ("correccions: canvi amb/sense valor, 'actually', 'back', incompletes", check_corrections),
    ("correccions: dependències, preguntes que passen a aplicar-se, avís, 'show me'", check_correction_consistency),
    ("correcció amb valor: una sola línia (bug reportat)", check_silent_correction),
    ("'quit' sense resultats; motiu abans de la fitxa a les casi coincidències", check_quit_and_near_layout),
    ("canvis després dels resultats (acabar, 'yes', 'the budget', després de 'show me')", check_change_after_results),
    ("exploració dels resultats: resum, next/prev, número, all, canvis, casi coincidències", check_explore_results),
    ("missatges de correcció: 'changed X to Y' (opcions) i 'updated X: Y' (rangs)", check_correction_messages),
    ("menú de resultats: 'change pets to no', 'no' no surt, llista després de la fitxa, 1 vivenda",
     check_results_menu_fixes),
    ("correccions: l'avís de 0 vivendes es compara amb l'estat actual (cas reportat)",
     check_zero_baseline_on_correction),
    ("fitxa de la vivenda en llenguatge natural", check_natural_house_description),
    ("zones disponibles amb la pregunta de la zona (conversa, oracle, correccions, avís)", check_available_zones),
]


def main():
    return run_suite("Iteració 3 (show me, resum, ordenació, correccions, casi coincidències)", [], CHECKS)


if __name__ == "__main__":
    raise SystemExit(main())
