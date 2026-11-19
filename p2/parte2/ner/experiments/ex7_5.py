"""Apartat 7.5: regularització amb dropout.

Apliquem dropout a tres models amb graus de sobreajust diferents: el baseline (BiLSTM 1×128), un model gran
(BiLSTM 2×256, uns 2,5 milions de paràmetres per a 4k oracions) i el millor model amb atenció de l'apartat
7.4. Les posicions tenen motivacions diferents. Sobre l'embedding, el dropout obliga el model a no
dependre d'una sola paraula o dimensió i simula paraules parcialment desconegudes, cosa útil quan la
majoria del vocabulari apareix poques vegades. Entre capes recurrents (Zaremba et al., 2014) regularitza la
representació intermèdia sense tocar les connexions temporals, que és on el dropout perjudicaria la
memòria de la LSTM; amb una sola capa no té efecte, per això només es prova al model gran. Abans del
classificador evita que la capa lineal s'especialitzi en poques unitats de la BiLSTM. Al Transformer el
dropout intern (atenció i feed-forward) és part de la recepta estàndard (0.1 a Vaswani et al., 2017).

Primer es prova cada posició per separat amb p = 0.3 i després totes juntes amb p = 0.1, 0.3 i 0.5.

Hipòtesis. Al model gran el dropout hauria de tenir l'efecte més clar: menys distància entre la loss de
train i la de validació, més èpoques abans de l'early stopping i millor F1. Al baseline l'efecte hauria de
ser petit però positiu, perquè ja al ej. 6 la loss de validació tocava mínim cap a l'època 17 mentre la de
train seguia baixant. p = 0.5 hauria de ser massa per a un dataset tan petit (infraajust), i el valor
òptim hauria d'estar entre 0.1 i 0.3. L'embedding hauria de ser la posició que més aporta, per la gran
proporció de paraules rares.
"""

from __future__ import annotations

import copy
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import plots
from ..config import BlockConfig, ExperimentConfig, baseline
from ..runner import summarize

SECTION = "7.5"
BASELINE = "BiLSTM 1×128 sense dropout"
POSITIONS = ("embedding", "entre capes", "classificador", "intern")
P_SINGLE = 0.3
P_ALL = (0.1, 0.3, 0.5)
DEFAULT_ATTENTION = ("BiLSTM + atenció 1 capa",
                     [BlockConfig("rnn", baseline().model.blocks[0].params),
                      BlockConfig("transformer", {"d_model": 256, "nhead": 4, "num_layers": 1,
                                                  "dim_feedforward": 512, "positional": "none"})])
MODELS: dict[str, str] = {}   # nom de configuració → model al qual pertany


def _with_dropout(cfg: ExperimentConfig, positions: tuple[str, ...], p: float) -> ExperimentConfig:
    """Aplica dropout p a les posicions indicades; les que el model no té simplement s'ignoren."""
    cfg = copy.deepcopy(cfg)
    if "embedding" in positions:
        cfg.model.embedding_dropout = p
    if "classificador" in positions:
        cfg.model.classifier_dropout = p
    for block in cfg.model.blocks:
        if block.kind == "rnn" and "entre capes" in positions and block.params.get("num_layers", 1) > 1:
            block.params["dropout"] = p
        if block.kind == "transformer" and "intern" in positions:
            block.params["dropout"] = p
    return cfg


def _applicable(cfg: ExperimentConfig) -> tuple[str, ...]:
    """Posicions on té sentit posar dropout en aquest model."""
    kinds = {b.kind for b in cfg.model.blocks}
    deep_rnn = any(b.kind == "rnn" and b.params.get("num_layers", 1) > 1 for b in cfg.model.blocks)
    return tuple(p for p, ok in zip(POSITIONS, (True, deep_rnn, True, "transformer" in kinds)) if ok)


def _grid(label: str, cfg: ExperimentConfig, p_all: tuple[float, ...] = P_ALL) -> list[ExperimentConfig]:
    """Sense dropout, cada posició aplicable sola amb p = 0.3 i totes juntes amb cada valor de p_all."""
    positions = _applicable(cfg)
    variants = [(f"{label} sense dropout", (), 0.0)]
    variants += [(f"{label} + {pos} {P_SINGLE}", (pos,), P_SINGLE) for pos in positions]
    variants += [(f"{label} + tot {p}", positions, p) for p in p_all]
    out = []
    for name, pos, p in variants:
        MODELS[name] = label
        out.append(_with_dropout(cfg, pos, p).with_(name, SECTION))
    return out


def attention_model(results_7_4: list[dict[str, Any]] | None = None) -> tuple[str, list[BlockConfig]]:
    """Millor model de l'apartat 7.4 per validació; sense resultats, l'híbrid BiLSTM + atenció d'una capa."""
    if not results_7_4:
        return DEFAULT_ATTENTION
    # Només compten els models que tenen algun bloc d'atenció (el baseline BiLSTM també és a la llista).
    with_attention = [r for r in results_7_4 if any(b["kind"] == "transformer" for b in r["config"]["model"]["blocks"])]
    best = summarize(with_attention, metrics=["val_entity_f1"], extra=[])["val_entity_f1_mean"].idxmax()
    cfg = next(r["config"] for r in results_7_4 if r["name"] == best)
    print("Model d'atenció escollit de l'apartat 7.4:", best)
    blocks = [BlockConfig(**b) for b in cfg["model"]["blocks"]]
    return best, blocks


def configs(results_7_4: list[dict[str, Any]] | None = None) -> list[ExperimentConfig]:
    base = baseline()
    big = base.with_(**{"model.blocks": [BlockConfig("rnn", {"rnn_type": "lstm", "hidden_dim": 256,
                                                            "num_layers": 2, "bidirectional": True})]})
    att_name, att_blocks = attention_model(results_7_4)
    att = base.with_(**{"model.blocks": att_blocks})
    # Si la recepta guanyadora del 7.4 era una altra, s'hereta perquè el model sigui el mateix.
    if results_7_4:
        train = next(r["config"]["train"] for r in results_7_4 if r["name"] == att_name)
        att = att.with_(**{f"train.{k}": train[k] for k in ("lr", "warmup_epochs")})
    return (_grid("BiLSTM 1×128", base) + _grid("BiLSTM 2×256", big)
            + _grid(att_name, att, p_all=(0.1, 0.3)))


def _gap(result: dict[str, Any]) -> float:
    """Distància entre la loss de validació i la de train a la millor època: mesura directa del sobreajust."""
    i = result["best_epoch"] - 1
    return result["history"]["val_loss"][i] - result["history"]["train_loss"][i]


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_5_dropout"
           ) -> tuple[pd.DataFrame, plt.Figure, plt.Figure]:
    """Taula amb F1, gap i millor època; figura comparativa i corbes d'aprenentatge sense i amb el millor dropout."""
    summary = summarize(results)
    summary.insert(0, "model", [MODELS.get(n, "?") for n in summary.index])
    gaps = pd.Series({n: np.mean([_gap(r) for r in results if r["name"] == n]) for n in summary.index})
    summary["loss_gap"] = gaps
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=summary["model"])

    models = list(dict.fromkeys(summary["model"]))
    curves, axes = plt.subplots(1, len(models), figsize=(5.2 * len(models), 3.6))
    for ax, model in zip(np.atleast_1d(axes), models):
        # Es compara sempre sense dropout amb la millor variant que en té, encara que no superi la primera.
        none = f"{model} sense dropout"
        rows = summary[(summary["model"] == model) & (summary.index != none)]
        best = rows["val_entity_f1_mean"].idxmax()
        labels = ["sense dropout", best.removeprefix(model).strip(" +")]
        plots.learning_curves(results, [none, best], ax=ax, title=model, labels=labels)
    curves.tight_layout()
    if save_as:
        plots.save(fig, save_as)
        plots.save(curves, f"{save_as}_curves")
    return summary, fig, curves
