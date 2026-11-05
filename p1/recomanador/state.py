"""Estat del diàleg.

A l'Ex. 6 l'estat era només el diccionari global `user_preferences`.
Aquí s'encapsula en un objecte nou per a cada execució.
"""

from dataclasses import dataclass, field


@dataclass
class DialogueState:
    preferences: dict = field(default_factory=dict)  # slot -> valor (string, 'any' o '0')
    exited: bool = False                              # l'usuari ha sortit amb una comanda d'EXIT
    stopped_early: bool = False                       # ha demanat els resultats abans d'acabar ("show me")
    match_history: list = field(default_factory=list)  # (pregunta, vivendes abans, vivendes després)
    answer_order: list = field(default_factory=list)   # preguntes respostes, en ordre (per a 'back')
    show_me_hinted: bool = False                       # ja s'ha suggerit 'show me' (només un cop)
    reached: set = field(default_factory=set)          # preguntes que s'han arribat a fer
