"""Importa tots els mòduls del paquet perquè cada bloc quedi registrat sense haver-lo d'afegir a mà."""

import importlib
import pkgutil

from .tagger import BLOCKS, CHAR_ENCODERS, DECODERS, PRETRAINED, NERTagger

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")

__all__ = ["BLOCKS", "CHAR_ENCODERS", "DECODERS", "PRETRAINED", "NERTagger"]
