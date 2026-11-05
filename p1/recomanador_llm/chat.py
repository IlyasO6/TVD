"""Sessió de xat de diversos torns (equivalent a `start_chat_session` del notebook base).

L'entrada/sortida és la del sistema 1 (`recomanador.io_adapter`): ConsoleIO a la consola i ScriptedIO a
les proves. Així els dos sistemes es presenten igual a la terminal.

Registre (B4): cada torn s'afegeix com una línia JSON a logs/sessio_<data-hora>.jsonl (missatge, resposta i
tots els esdeveniments del torn: intents del model, tools, guardrails, jutge, temps).
"""

import json
from datetime import datetime
from pathlib import Path

from recomanador.io_adapter import ConsoleIO

from . import flow, guardrails, prompts
from .agent import respond
from .config import LOG_DIR, LOG_TO_FILE

_DEFAULT = object()


def new_history(system_prompt=None):
    """Historial nou amb el system prompt (per defecte, el de l'entregable generat amb les dades;
    `new_history(prompts.BASE_SYSTEM_PROMPT)` reprodueix el del notebook base per comparar)."""
    return [{"role": "system", "content": system_prompt or prompts.build_system_prompt()}]


class SessionLog:
    """Fitxer JSONL d'una sessió: una línia per torn. Si no es pot escriure, el xat continua igualment."""

    def __init__(self, log_dir):
        self.session = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = Path(log_dir) / f"sessio_{self.session}.jsonl" if log_dir else None
        self.turn = 0

    def write(self, user_text, answer, events):
        self.turn += 1
        if not self.path:
            return
        record = {"session": self.session, "turn": self.turn, "time": datetime.now().isoformat(timespec="seconds"),
                  "user": user_text, "answer": answer, "events": events}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except (OSError, ValueError):  # p.ex. carpeta sense permisos o ruta invàlida
            self.path = None  # sense registre, però sense aturar la conversa


def chat(model, io=None, history=None, verbose=False, log_dir=_DEFAULT):
    """Conversa fins que l'usuari escriu 'exit'/'quit' (o tanca l'entrada). Retorna l'historial.
    `log_dir`: carpeta del registre (per defecte, config.LOG_DIR si LOG_TO_FILE; None, sense registre)."""
    io = io or ConsoleIO()
    history = new_history() if history is None else history
    log = (lambda text: io.say(text, kind='help')) if verbose else None
    session = SessionLog((LOG_DIR if LOG_TO_FILE else None) if log_dir is _DEFAULT else log_dir)
    welcome = flow.welcome_lines()
    io.say(welcome[0], kind='title')
    for line in welcome[1:]:
        io.say(line, kind='info')
    language = "en"
    while True:
        try:
            user_input = io.ask("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            break
        if not user_input:
            continue
        language = guardrails.turn_language(user_input, history)
        # Flux (punt C): ajuda, sortida i comiats es resolen al codi, sense cridar el model.
        if flow.is_exit(user_input) or flow.is_farewell(user_input):
            session.write(user_input, "", [{"t": 0, "kind": "flow", "action": "farewell"}])
            break
        if flow.is_help(user_input):
            lines = flow.help_lines(language)
            session.write(user_input, "\n".join(lines), [{"t": 0, "kind": "flow", "action": "help"}])
            _say_answer(io, lines)
            continue
        events = []
        answer = respond(model, history, user_input, log, events)
        session.write(user_input, answer, events)
        _say_answer(io, answer.split("\n"))
    closing = flow.closing_lines(history, language)
    io.say("")
    for line in closing[:-1]:
        io.say(line, kind='system')
    io.say(closing[-1], kind='goodbye')
    return history


def _say_answer(io, lines):
    io.say("")
    # Línia a línia: la consola ajusta l'amplada de cada línia sense ajuntar les llistes del model.
    for i, line in enumerate(lines):
        io.say(f"Assistant: {line}" if i == 0 else line, kind='system')
