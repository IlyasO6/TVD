"""Entrada/sortida injectable.

El gestor del diàleg mai crida directament input()/print(): ho fa a través
d'un objecte IO. Així el mateix codi funciona a la consola, a Colab i en
diàlegs simulats per a les proves (fase "Proves" del mètode).

Iteració 3 (interfície): cada sortida porta un `kind` (la seva funció: pregunta, avís, error,
ajuda, resultats...). Només ConsoleIO li dona format (colors, negreta, separadors), sempre igual
per a cada funció; ScriptedIO l'ignora i les proves veuen el text pla. Els colors es desactiven
amb la variable d'entorn NO_COLOR (convenció estàndard) o amb config.USE_COLORS = False.
"""

import os
import textwrap

from .config import USE_COLORS

RESET = "\033[0m"
BOLD, DIM = "\033[1m", "\033[2m"
RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN = (f"\033[{n}m" for n in (91, 92, 93, 94, 95, 96))

# Format de cada funció de la sortida. Només caràcters que existeixen a la consola de Windows (cp1252).
STYLES = {
    'title': BOLD + CYAN,       # benvinguda
    'info': "",                 # instruccions
    'question': BOLD,           # pregunta (el número [3/17] va en cian)
    'help': DIM,                # ajuda de format
    'system': GREEN,            # reaccions a les respostes, confirmacions de canvis
    'count': MAGENTA,           # comptador de vivendes
    'warning': BOLD + YELLOW,   # avisos i confirmacions (Yes / No)
    'error': RED,               # no s'ha entès la resposta
    'hint': CYAN,               # suggeriments i menús
    'recap': BOLD,              # resum de la cerca
    'results': BOLD + GREEN,    # capçaleres dels resultats
    'item': "",                 # una línia per vivenda (el número en negreta)
    'house_header': BOLD + CYAN,
    'goodbye': BOLD + CYAN,
}
WIDTH = 78  # amplada de línia de la consola
RULE = "=" * 64
SECTION = "-" * 64


class ConsoleIO:
    """IO real: input() i print(), amb format segons la funció de cada línia.
    clear() esborra la sortida només a Colab."""

    def __init__(self, colors=None):
        self.colors = USE_COLORS and "NO_COLOR" not in os.environ if colors is None else colors
        if self.colors and os.name == "nt":
            os.system("")  # activa les seqüències ANSI a la consola clàssica de Windows

    def _paint(self, text, style):
        return f"{style}{text}{RESET}" if self.colors and style else text

    def _format(self, text, kind, args):
        if kind == 'question' and text.startswith("[") and "] " in text:
            number, question = text.split("] ", 1)
            return f"{self._paint(number + ']', CYAN)} {self._paint(question, BOLD)}"
        if kind == 'item' and " · " in text:  # "  #32 · flat in Gràcia · 575 euros/month"
            number, rest = text.split(" · ", 1)
            return f"{self._paint(number, BOLD + YELLOW)} · {rest}"
        return self._paint(text, STYLES.get(kind, ""))

    def ask(self, prompt):
        # El text de la pregunta s'escriu amb print i després input() sense text: els codis de color
        # dins de l'indicador d'input() no es mostren bé a tots els entorns (p.ex. notebooks).
        print(self._paint(f"> {prompt}", BOLD + CYAN), end="", flush=True)
        return input()

    def say(self, *args, kind=None):
        text = " ".join(str(a) for a in args)
        blank_lines = len(text) - len(text.lstrip("\n"))
        text = text.lstrip("\n")
        if kind in ('title', 'goodbye'):  # marc de la benvinguda i del comiat
            print("\n" * blank_lines + self._paint(RULE, CYAN))
            print(self._format(text, kind, args))
            print(self._paint(RULE, CYAN))
            return
        if kind == 'recap':  # separador abans del resum i dels resultats
            print("\n" * blank_lines + self._paint(SECTION, DIM))
            print(self._format(text, kind, args))
            return
        print("\n" * blank_lines, end="")
        if kind in ('question', 'item', 'house_header') or len(text) <= WIDTH:
            print(self._format(text, kind, args))
            return
        # Textos llargs (fitxes, menús, avisos): es parteixen a l'amplada de la consola mantenint el sagnat.
        indent = text[:len(text) - len(text.lstrip())]
        for line in textwrap.wrap(text, WIDTH, subsequent_indent=indent):
            print(self._format(line, kind, (line,)))

    def clear(self):
        try:
            from google.colab import output
            output.clear()
        except ImportError:
            pass


class ScriptedIO:
    """IO simulat: llegeix les respostes d'una llista i guarda tot el que es mostra (sense format)."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.transcript = []

    def ask(self, prompt):
        if not self.answers:
            raise RuntimeError(f"El guió s'ha quedat sense respostes al prompt: {prompt!r}")
        answer = self.answers.pop(0)
        self.transcript.append(f"{prompt}{answer}")
        return answer

    def say(self, *args, kind=None):
        self.transcript.append(" ".join(str(a) for a in args))

    def clear(self):
        self.transcript.append("<clear>")

    def text(self):
        return "\n".join(self.transcript)
