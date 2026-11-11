"""Apartat 7.3: xarxes recurrents (tipus de cel·la, direcció, profunditat i mida de l'estat).

L'experiment es fa en dues fases. A la primera es canvia un sol factor respecte al baseline (BiLSTM d'una
capa i 128 unitats), de manera que cada diferència s'explica per aquell factor. A la segona es creuen els
guanyadors de cada factor amb el valor del baseline, perquè els factors poden interactuar (per exemple, una
GRU pot treure més profit de dues capes que una LSTM). Els guanyadors es trien automàticament per
validació, mai mirant el test.

Hipòtesis. LSTM i GRU haurien de quedar molt a prop: amb oracions de 11 paraules de mitjana no hi ha
dependències prou llargues perquè el mecanisme extra de la LSTM marqui diferència, i la GRU té un 25% menys
de paràmetres (Chung et al., 2014). La bidireccionalitat hauria de ser el factor més important: en NER
l'etiqueta d'una paraula depèn també del que ve després ("boston" a "boston to denver" és sortida), i una
RNN unidireccional només veu el passat (Jurafsky & Martin, cap. 8 i 17). Per separar aquest efecte del de
la capacitat, comparem també una LSTM unidireccional de 256 unitats, que té la mateixa mida de sortida que
la BiLSTM de 128. Més capes donen representacions més abstractes, però sense dropout entre capes i amb
només 4k oracions esperem poc guany a 2 capes i sobreajust a 3; aquest efecte es revisa a l'apartat 7.5.
Amb la mida de l'estat esperem saturació a partir de 128.
"""

from __future__ import annotations

from itertools import product
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .. import plots
from ..config import BlockConfig, ExperimentConfig, baseline
from ..runner import summarize

SECTION = "7.3"
BASELINE = "BiLSTM 1×128 (baseline)"
DEFAULT = {"rnn_type": "lstm", "bidirectional": True, "num_layers": 1, "hidden_dim": 128}


def _name(rnn_type: str, bidirectional: bool, num_layers: int, hidden_dim: int) -> str:
    if (rnn_type, bidirectional, num_layers, hidden_dim) == tuple(DEFAULT.values()):
        return BASELINE
    return f"{'Bi' if bidirectional else ''}{rnn_type.upper()} {num_layers}×{hidden_dim}"


def _config(family: str, **rnn: Any) -> ExperimentConfig:
    params = {**DEFAULT, **rnn}
    cfg = baseline().with_(_name(**params), SECTION, **{"model.blocks": [BlockConfig("rnn", params)]})
    FAMILIES[cfg.name] = family
    return cfg


FAMILIES: dict[str, str] = {}

# Fase 1: un factor cada vegada respecte al baseline.
STAGE1: dict[str, list[dict[str, Any]]] = {
    "Referència": [{}],
    "Tipus de cel·la": [{"rnn_type": "gru"}],
    "Direcció": [{"bidirectional": False}, {"bidirectional": False, "hidden_dim": 256}],
    "Capes": [{"num_layers": 2}, {"num_layers": 3}],
    "Mida de l'estat": [{"hidden_dim": 64}, {"hidden_dim": 256}],
}


def configs() -> list[ExperimentConfig]:
    """Configuracions de la primera fase."""
    return [_config(family, **change) for family, changes in STAGE1.items() for change in changes]


def _winner(summary: pd.DataFrame, candidates: dict[Any, dict[str, Any]]) -> Any:
    """Valor del factor amb millor F1 de validació entre el baseline i les variants de la fase 1."""
    scores = {value: summary.loc[_name(**{**DEFAULT, **change}), "val_entity_f1_mean"]
              for value, change in candidates.items()}
    return max(scores, key=scores.get)


def cross_configs(stage1_results: list[dict[str, Any]]) -> list[ExperimentConfig]:
    """Fase 2: creuament complet entre el valor del baseline i el guanyador de cada factor."""
    summary = summarize(stage1_results)
    winners = {
        "rnn_type": _winner(summary, {"lstm": {}, "gru": {"rnn_type": "gru"}}),
        "bidirectional": _winner(summary, {True: {}, False: {"bidirectional": False}}),
        "num_layers": _winner(summary, {1: {}, 2: {"num_layers": 2}, 3: {"num_layers": 3}}),
        "hidden_dim": _winner(summary, {128: {}, 64: {"hidden_dim": 64}, 256: {"hidden_dim": 256}}),
    }
    print("Guanyadors de la fase 1 per validació:", winners)
    grid = [sorted({DEFAULT[k], v}, key=str) for k, v in winners.items()]
    stage1_names = {cfg.name for cfg in configs()}
    out = []
    for rnn_type, bidirectional, num_layers, hidden_dim in product(*grid):
        params = {"rnn_type": rnn_type, "bidirectional": bidirectional, "num_layers": num_layers, "hidden_dim": hidden_dim}
        if _name(**params) not in stage1_names:
            out.append(_config("Creuament", **params))
    return out


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_3_rnn") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula resum (amb família, paràmetres i temps per època) i figura de F1 amb el cost de cada variant."""
    summary = summarize(results)
    summary.insert(0, "family", [FAMILIES.get(name, "Creuament") for name in summary.index])
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=summary["family"], with_cost=True)
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
