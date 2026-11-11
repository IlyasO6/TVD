"""Apartat 7.6: balanceig de classes amb pesos a la cross-entropy.

El 64% dels tokens són `O` i, entre les 178 etiquetes, n'hi ha que surten centenars de cops i altres un sol
cop. Amb la loss estàndard cada token pesa igual, de manera que el model optimitza sobretot les classes
freqüents. Donar més pes a les classes rares compensa aquest desequilibri. Comparem diversos esquemes, de
més a menys agressius: la inversa de la freqüència (amb i sense límit superior), la inversa de l'arrel,
el nombre efectiu de mostres (Cui et al., 2019) i, com a alternativa mínima, reduir només el pes de `O`.
Els pesos es normalitzen perquè el token mitjà de train pesi 1; així el límit superior es llegeix
directament (un límit de 10 vol dir que cap token compta més de deu vegades el token mitjà).

Hipòtesis. Els pesos haurien de pujar el recall de les classes rares i, per tant, la F1 macro i la F1 del
grup de classes rares, a canvi de més falsos positius (menys precisió) en aquestes classes. La F1 micro,
dominada per les classes freqüents, pot baixar lleugerament. La inversa pura hauria de ser massa agressiva:
una etiqueta vista un sol cop rep un pes centenars de vegades superior al de `O`, i el model acaba
sobreajustant aquells pocs exemples; el límit superior i l'arrel haurien de donar el millor compromís.
Reduir només el pes de `O` hauria de moure el llindar entre "entitat" i "no entitat" i guanyar recall
general sense afavorir específicament les classes rares.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import torch

from .. import plots
from ..config import ExperimentConfig, baseline
from ..data import PAD_LABEL_IDX, prepare_data
from ..runner import summarize
from ..train import class_weights

SECTION = "7.6"
BASELINE = "sense pesos"
SCHEMES: dict[str, dict[str, Any]] = {
    BASELINE: {},
    "inversa": {"train.class_weighting": "inverse"},
    "inversa, límit 10": {"train.class_weighting": "inverse", "train.weight_clip": 10.0},
    "inversa de l'arrel": {"train.class_weighting": "inverse_sqrt"},
    "inversa de l'arrel, límit 10": {"train.class_weighting": "inverse_sqrt", "train.weight_clip": 10.0},
    "nombre efectiu (β=0.999)": {"train.class_weighting": "effective"},
    "només O × 0.5": {"train.o_weight": 0.5},
    "només O × 0.25": {"train.o_weight": 0.25},
}
METRICS = ("val_entity_f1", "test_entity_f1", "test_entity_f1_macro", "test_token_f1_macro", "test_entity_p",
           "test_entity_r", "test_f1_rare", "test_f1_mid", "test_f1_frequent")


def configs() -> list[ExperimentConfig]:
    return [baseline().with_(name, SECTION, **overrides) for name, overrides in SCHEMES.items()]


def weights_table() -> pd.DataFrame:
    """Pes de `O`, mínim, mediana i màxim de cada esquema, per veure com d'agressiu és cadascun."""
    data = prepare_data(baseline().data)
    rows = {}
    for cfg in configs():
        w = class_weights(cfg, data, torch.device("cpu"))
        w = torch.ones(data.num_classes) if w is None else w
        real = torch.cat([w[:PAD_LABEL_IDX], w[PAD_LABEL_IDX + 1:]])
        rows[cfg.name] = {"pes O": w[data.label2idx["O"]].item(), "mínim": real.min().item(),
                          "mediana": real.median().item(), "màxim": real.max().item()}
    return pd.DataFrame(rows).T


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_6_balanceig") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula de mètriques i figura amb F1 per grup de freqüència i precisió/recall de cada esquema."""
    summary = summarize(results, metrics=METRICS)
    plots.setup_style()
    fig, (ax_freq, ax_pr) = plt.subplots(1, 2, figsize=(14, 4.2))
    plots.grouped_bars(summary, ["test_f1_rare", "test_f1_mid", "test_f1_frequent"],
                       ["rares (<10)", "mitjanes", "freqüents (>100)"], ax=ax_freq,
                       title="F1 per token segons la freqüència de l'etiqueta a train (test)", ylabel="F1 macro")
    plots.grouped_bars(summary, ["test_entity_p", "test_entity_r", "test_entity_f1", "test_entity_f1_macro"],
                       ["precisió", "recall", "F1 micro", "F1 macro"], ax=ax_pr,
                       title="Mètriques d'entitat (test)", ylabel="")
    for ax in (ax_freq, ax_pr):
        values = [summary[c] for c in summary.columns if c.endswith("_mean") and c.startswith("test_")]
        ax.set_ylim(max(0.0, min(v.min() for v in values) - 0.1), 1.15)  # marge per a la llegenda
    fig.tight_layout()
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
