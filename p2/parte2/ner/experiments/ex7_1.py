"""Apartat 7.1: mida dels embeddings i embeddings preentrenats (GloVe).

Hipòtesi sobre la mida: amb un vocabulari d'unes 600 paraules i només 4k oracions, la F1 hauria de pujar
ràpidament fins a 50-100 dimensions i després estancar-se. Més dimensions donen capacitat per separar
paraules, però el nombre de paraules a separar és petit i cada dimensió extra són paràmetres que s'han
d'aprendre amb pocs exemples, així que per sobre de 256 esperem un lleuger empitjorament per sobreajust.

Hipòtesi sobre GloVe: els vectors preentrenats aporten coneixement que el corpus no conté, sobretot per a
paraules rares o no vistes (noms de ciutats, aerolínies, dies), que és on falla un embedding après des de
zero (Jurafsky & Martin, cap. 6; Lample et al., 2016). Esperem millora sobretot en la F1 macro i en test.
Amb fine-tuning el model adapta els vectors a la tasca, però les paraules que no surten a train es queden
amb el vector original mentre la resta es desplacen; congelats, tot l'espai queda coherent però no
s'adapta. Quina de les dues opcions guanya és justament una de les preguntes de l'experiment.

El control `aleatori-100 min_freq=1` separa els dos efectes de GloVe: el vocabulari amb GloVe inclou les
paraules que surten un sol cop a train (que al baseline van a <unk>), i amb aquest control veiem quina part
de la millora ve només d'aquest vocabulari més gran i quina dels vectors preentrenats.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .. import plots
from ..config import ExperimentConfig, baseline
from ..data import UNK_IDX, prepare_data
from ..models import PRETRAINED
from ..models.embeddings import GLOVE_DIMS, coverage
from ..runner import summarize

SECTION = "7.1"
RANDOM_DIMS = (16, 32, 50, 64, 100, 128, 200, 256, 300, 512)
CONTROL = "aleatori-100 min_freq=1"


def _random(dim: int) -> str:
    return f"aleatori-{dim}"


def _glove(dim: int, freeze: bool) -> str:
    return f"glove-{dim} {'congelat' if freeze else 'fine-tuned'}"


def configs() -> list[ExperimentConfig]:
    """Embeddings aleatoris de diverses mides, GloVe congelat i fine-tuned, i el control de vocabulari."""
    base = baseline()
    out = [base.with_(_random(d), SECTION, **{"model.embedding_dim": d}) for d in RANDOM_DIMS]
    for freeze in (True, False):
        out += [base.with_(_glove(d, freeze), SECTION, **{"model.embedding_dim": d, "model.pretrained": f"glove-{d}",
                                                          "model.freeze_embeddings": freeze}) for d in GLOVE_DIMS]
    out.append(base.with_(CONTROL, SECTION, **{"model.embedding_dim": 100, "data.min_freq": 1}))
    return out


def vocab_stats() -> pd.DataFrame:
    """Mida del vocabulari i proporció de tokens <unk> segons el vocabulari (baseline, min_freq=1, GloVe)."""
    base = baseline()
    variants = {
        "baseline (min_freq=2)": prepare_data(base.data),
        "min_freq=1": prepare_data(base.data.__class__(min_freq=1)),
        "GloVe": prepare_data(base.data, extra_words=PRETRAINED["glove-100"][0]()),
    }
    rows = {}
    for name, data in variants.items():
        row = {"vocab": len(data.word2idx)}
        for split in ("val", "test"):
            words = data.splits[split].words
            real = words[words != 0]
            row[f"unk_{split}"] = (real == UNK_IDX).float().mean().item()
        rows[name] = row
    df = pd.DataFrame(rows).T
    df["vocab"] = df["vocab"].astype(int)
    print(f"Cobertura de GloVe sobre el vocabulari del baseline: {coverage(variants['baseline (min_freq=2)'].word2idx):.1%}")
    return df


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_1_embeddings") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula resum i figura de F1 (validació i test) en funció de la dimensió per a cada tipus d'embedding."""
    summary = summarize(results)
    plots.setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=False)
    series = [
        ("Aleatori", RANDOM_DIMS, [_random(d) for d in RANDOM_DIMS]),
        ("GloVe congelat", GLOVE_DIMS, [_glove(d, True) for d in GLOVE_DIMS]),
        ("GloVe fine-tuned", GLOVE_DIMS, [_glove(d, False) for d in GLOVE_DIMS]),
    ]
    for ax, metric, title in zip(axes, ("val_entity_f1", "test_entity_f1"), ("Validació", "Test")):
        for color, (label, dims, names) in zip(plots.PALETTE, series):
            plots.line_with_errors(ax, dims, summary, names, metric, label=label, color=color)
        ctrl = summary.loc[CONTROL]
        ax.errorbar([100], [ctrl[f"{metric}_mean"]], yerr=[ctrl[f"{metric}_std"]], fmt="D", color=plots.PALETTE[3],
                    capsize=3, label="Aleatori, min_freq=1 (control)")
        ax.set_xscale("log", base=2)
        ax.set_xticks(RANDOM_DIMS, [str(d) for d in RANDOM_DIMS], rotation=45)
        ax.minorticks_off()
        ax.set(xlabel="Dimensió de l'embedding", ylabel="F1 d'entitats", title=title)
    axes[0].legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
