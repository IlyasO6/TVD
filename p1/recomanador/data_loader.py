"""Càrrega de les dades (missatges, preguntes i habitatges) des del JSON."""

import json

from .config import DATA_PATH


def load_data(path=DATA_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
