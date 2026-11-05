"""Xatbot d'assessorament d'habitatges amb LLM i tools (sistema 2, entregable del notebook
P1_LLM_House_Advice_Chatbot_with_Tools.ipynb).

Mòduls:
    config   constants (model, dades, límits)
    prompts  system prompt i textos de la sessió
    tools    search_homes i get_home_details (filtre i NLU del sistema 1), esquemes i validació
    guardrails  guardrails d'entrada, de flux, d'execució (ancoratge d'arguments) i de sortida (regles i jutge)
    battery  bateria d'avaluació (riscos de la teoria i casos funcionals)
    evaluation  execució de la bateria, resums, comparació i calibratge del jutge
    model    accés al LLM (l'única part que necessita GPU)
    agent    un torn: model -> crides a tools -> resposta
    chat     sessió de diversos torns

Ús:  python -m recomanador_llm [--verbose]      (terminal, amb GPU)
     chat(QwenModel(model, tokenizer))           (notebook, reutilitzant el model ja carregat)
"""

from . import version  # primer: l'empremta del codi que es carrega ara (vegeu version.py)
from .agent import respond
from .chat import chat, new_history
from .model import QwenModel

__all__ = ["QwenModel", "chat", "new_history", "respond"]
