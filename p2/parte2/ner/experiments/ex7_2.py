"""Apartat 7.2: xarxes convolucionals i pooling.

Provem la convolució de tres maneres amb motivacions diferents. Primer, una CNN de paraula davant de la
BiLSTM: la CNN extreu patrons locals d'n-grames i la BiLSTM els combina amb el context llarg. Esperem un
guany petit o nul, perquè la BiLSTM ja captura bé el context local; els kernels de 3 haurien de bastar, ja
que gairebé totes les entitats d'ATIS tenen entre una i tres paraules, i kernels més grans o més filtres
només afegeixen paràmetres. Segon, una CNN sola sense recurrència: la paraula clau que decideix moltes
etiquetes és just al costat ("from boston" o "to boston"), així que pot funcionar raonablement, però
etiquetes com `arrive_time` vs `depart_time` depenen de paraules llunyanes ("arrive in denver at 1110") i
amb un camp receptiu limitat haurien de fallar més. Esperem que millori amb la profunditat i quedi per
sota de la BiLSTM.

Pel que fa al pooling, un global pooling sol no serveix en NER perquè destrueix la sortida per token. El
fem servir com a vector de context global concatenat a cada token, que hauria d'ajudar sobretot a la CNN
sola (li dona informació de tota l'oració que el seu camp receptiu no arriba a veure). El max-pooling local
amb stride 1 suavitza activacions veïnes; esperem que sigui neutre o fins i tot negatiu, perquè difumina
els límits de les entitats, que són justament el que BILOU intenta marcar.

Finalment, la char-CNN amb max-pooling sobre caràcters (Ma & Hovy, 2016; Lample et al., 2016) aporta
informació morfològica i ortogràfica: dígits en hores i números de vol, sufixos, apòstrofs. Esperem guany
sobretot en paraules fora de vocabulari i en classes rares. El guany hauria de ser menor que en corpus com
CoNLL perquè ATIS està en minúscules i es perd la pista de les majúscules.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .. import plots
from ..config import BlockConfig, ExperimentConfig, baseline
from ..data import prepare_data
from ..runner import summarize

SECTION = "7.2"
BASELINE = "baseline (BiLSTM)"
RNN = baseline().model.blocks[0]


def _cnn(kernels: list[int] = [3], filters: int = 128, layers: int = 1, **extra: Any) -> BlockConfig:
    return BlockConfig("cnn", {"kernel_sizes": kernels, "filters": filters, "num_layers": layers, **extra})


def _char(char_dim: int, filters: int, kernel: int) -> BlockConfig:
    return BlockConfig("char_cnn", {"char_dim": char_dim, "filters": filters, "kernel_size": kernel})


# nom → (família, blocs de l'encoder, encoder de caràcters)
GRID: dict[str, tuple[str, list[BlockConfig], BlockConfig | None]] = {
    BASELINE: ("Referència", [RNN], None),
    # CNN de paraula davant de la BiLSTM: kernel, nombre de filtres i profunditat, un factor cada vegada.
    "CNN k3 → BiLSTM": ("CNN → BiLSTM", [_cnn([3]), RNN], None),
    "CNN k5 → BiLSTM": ("CNN → BiLSTM", [_cnn([5]), RNN], None),
    "CNN k7 → BiLSTM": ("CNN → BiLSTM", [_cnn([7]), RNN], None),
    "CNN k3+5 → BiLSTM": ("CNN → BiLSTM", [_cnn([3, 5], filters=64), RNN], None),
    "CNN k3 f64 → BiLSTM": ("CNN → BiLSTM", [_cnn([3], filters=64), RNN], None),
    "CNN k3 f256 → BiLSTM": ("CNN → BiLSTM", [_cnn([3], filters=256), RNN], None),
    "CNN k3 ×2 → BiLSTM": ("CNN → BiLSTM", [_cnn([3], layers=2), RNN], None),
    # CNN sola: el camp receptiu creix amb les capes (1 capa k3 = 3 paraules, 2 = 5, 3 = 7).
    "CNN k3 ×1": ("Només CNN", [_cnn([3])], None),
    "CNN k3 ×2": ("Només CNN", [_cnn([3], layers=2)], None),
    "CNN k3 ×3": ("Només CNN", [_cnn([3], layers=3)], None),
    "CNN k3+5 ×2": ("Només CNN", [_cnn([3, 5], filters=64, layers=2)], None),
    # Pooling compatible amb NER, sobre la CNN de 2 capes i sobre la CNN → BiLSTM.
    "CNN k3 ×2 + max-pool local": ("Pooling", [_cnn([3], layers=2, local_pool=3)], None),
    "CNN k3 ×2 + context global": ("Pooling", [_cnn([3], layers=2, global_context=True)], None),
    "CNN k3 + context global → BiLSTM": ("Pooling", [_cnn([3], global_context=True), RNN], None),
    # Char-CNN concatenada a l'embedding de paraula (Ma & Hovy fan servir 30 dimensions i 30 filtres).
    "char-CNN 25/25 k3 + BiLSTM": ("Char-CNN", [RNN], _char(25, 25, 3)),
    "char-CNN 50/50 k3 + BiLSTM": ("Char-CNN", [RNN], _char(50, 50, 3)),
    "char-CNN 50/50 k5 + BiLSTM": ("Char-CNN", [RNN], _char(50, 50, 5)),
}


def configs() -> list[ExperimentConfig]:
    base = baseline()
    return [base.with_(name, SECTION, **{"model.blocks": blocks, "model.char_encoder": char})
            for name, (_, blocks, char) in GRID.items()]


def oov_accuracy(results: list[dict[str, Any]]) -> pd.Series:
    """Accuracy a test sobre els tokens la paraula dels quals no surt mai a train, mitjana sobre llavors."""
    data = prepare_data(baseline().data)
    train_words = {w for s in data.splits["train"].sentences for w in s}
    test = data.splits["test"]
    positions = [(i, j) for i, sent in enumerate(test.sentences) for j, w in enumerate(sent) if w not in train_words]
    acc = {}
    for r in results:
        preds = [p.split() for p in r["test_pred"]]
        hits = sum(preds[i][j] == test.gold[i][j] for i, j in positions)
        acc.setdefault(r["name"], []).append(hits / len(positions))
    print(f"Tokens de test amb paraula no vista a train: {len(positions)}")
    return pd.Series({k: sum(v) / len(v) for k, v in acc.items()}, name="oov_token_acc")


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_2_cnn") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula resum (amb família, accuracy en OOV i cost) i dot plot de F1 de validació i test."""
    summary = summarize(results)
    summary.insert(0, "family", [GRID[name][0] for name in summary.index])
    summary = summary.join(oov_accuracy(results))
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=summary["family"], with_cost=True)
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
