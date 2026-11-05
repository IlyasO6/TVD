"""Constants del xatbot amb LLM (sistema 2)."""

from pathlib import Path

# Mateixes dades que el sistema 1 (house_data_v2.json): 50 vivendes amb tots els camps. D'aquest JSON
# només es fa servir la llista 'houses'; la resta (preguntes, reaccions...) és el guió del sistema 1.
DATA_PATH = Path(__file__).resolve().parent.parent / "house_data_v2.json"

# Model del notebook base: entrenat per fer servir tools i prou petit per a la T4 de Colab.
MODEL_NAME = "Qwen/Qwen2.5-Coder-3B-Instruct"
MAX_NEW_TOKENS = 512

# Redacció de la resposta un cop hi ha resultats (model.QwenModel, `sample`): mostreig moderat perquè les
# respostes no siguin sempre la mateixa frase; la decisió de cercar continua sent determinista.
COMPOSE_TEMPERATURE = 0.6
COMPOSE_TOP_P = 0.9

# Màxim de crides al model per torn de l'usuari (cada crida a una tool en gasta una): evita bucles.
MAX_MODEL_CALLS = 5

EXIT_COMMANDS = {"exit", "quit", "salir", "sortir"}  # a més, comiats naturals (flow.is_farewell)

# Vivendes per pàgina en el resultat de search_homes: prou per triar, poques per no omplir el context
# (la ventana de context és el límit: cost, latència i oblit) ni donar al model massa dades per confondre.
# 3 (abans 5): les respostes eren sobretot una llista; amb menys línies hi ha més conversa ("show me more").
RESULTS_PER_PAGE = 3

# Guardrail d'entrada: una petició real cap en unes poques frases; un missatge molt llarg sol ser una
# càrrega d'injecció o enganxat per error, i omple el context.
MAX_INPUT_CHARS = 1000

# Guardrails d'execució: crides a tools per torn (més enllà, el model ha de respondre amb el que té) i
# mida màxima del resultat d'una tool que torna al model (search_homes en dona ~1.000 caràcters).
MAX_TOOL_CALLS = 3
MAX_TOOL_OUTPUT_CHARS = 4000

# Guardrail de sortida: regeneracions per torn quan una resposta té un problema greu (cada una és una
# crida més al model, més latència); si persisteix, resposta fixa.
MAX_REGENERATIONS = 1

# On va la indicació d'idioma de cada torn: "system" (al final del system prompt) o "after_user" (un missatge
# de sistema després del del client, com a la primera versió). La bateria D va fer sospitar que la segona fa
# que el model ignori el client; es deixa configurable per comparar-les.
LANGUAGE_HINT_POSITION = "system"

# Llargada màxima del text propi d'una resposta (sense les línies de vivendes). El prompt en demana ~120
# paraules; 200 deixa marge. Més és una resposta que s'ha desviat (cas real: una recepta de 10 passos).
MAX_ANSWER_WORDS = 200

# Jutge del guardrail de sortida (el mateix model, sense tools): respon YES/NO en 1-2 tokens; la resposta
# jutjada es limita per mantenir la crida curta.
JUDGE_MAX_NEW_TOKENS = 3
JUDGE_MAX_CHARS = 2000

# Calibratge del jutge (B5): es bloqueja només si P(NO) >= llindar (probabilitat del model entre YES i NO).
# Calibrat amb les 67 respostes jutjades de la bateria v3 (evaluacio/calibratge_jutge.md), etiquetades a mà
# (9 fora de domini, 58 correctes):
#   llindar 0,5: 8/9 bloquejades, 14 falsos positius  ·  0,6: 8/9, 10 FP  ·  0,7: 8/9, 1 FP  ·  0,8: 7/9, 1 FP
#   ·  0,9: 6/9, 0 FP.  0,7 és el millor punt (el valor anterior, 0,5 implícit, bloquejava 14 respostes bones).
# L'única fora de domini que passa (X01, discriminació, P(YES)=0,78) no depèn del llindar: s'hi ha afegit
# la discriminació a les instruccions i als exemples del jutge.
JUDGE_THRESHOLD = 0.7

# Registre (B4): cada torn del xat, amb tots els intents del model (també els rebutjats), les crides a tools,
# les decisions dels guardrails i els temps, en un fitxer JSONL per sessió. Conté els missatges del client:
# es queda a la carpeta local del projecte.
LOG_TO_FILE = True
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
