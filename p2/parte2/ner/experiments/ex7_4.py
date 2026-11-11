"""Apartat 7.4: blocs Transformer.

Provem dues maneres d'afegir Transformer. La primera substitueix la BiLSTM per un encoder Transformer
entrenat des de zero (embedding 128 → d_model 128). La segona manté la BiLSTM i hi posa capes d'atenció
al damunt: la BiLSTM aporta l'ordre i el context local, i l'atenció permet que cada token consulti
directament qualsevol altre de l'oració. En aquest cas no afegim codificació posicional, perquè la sortida
de la BiLSTM ja depèn de la posició.

Hipòtesis. Un Transformer sol des de zero hauria de quedar per sota de la BiLSTM: no té el biaix inductiu de
seqüencialitat i ha d'aprendre de les dades tant el significat com l'ordre, i amb 4k oracions n'hi ha
poques (els Transformers brillen amb preentrenament massiu; Jurafsky & Martin, cap. 9 i 11). Sense
codificació posicional el model veu l'oració com una bossa de paraules i hauria de fallar en distincions
que depenen de l'ordre com `fromloc`/`toloc`; aquest control mostra fins a quin punt la posició és
imprescindible. Sinusoidal i apresa haurien de quedar a prop, amb lleuger avantatge per a la sinusoidal
perquè no s'ha d'aprendre. Més capes o caps afegeixen capacitat que amb poques dades es tradueix sobretot
en sobreajust. L'híbrid BiLSTM + atenció hauria d'igualar o millorar lleugerament el baseline.

Els Transformers solen necessitar un LR més baix i warmup. Per no barrejar aquest efecte amb l'arquitectura,
la fase 1 compara la recepta del baseline amb LR 5e-4 i 2 èpoques de warmup sobre el Transformer de
referència, i la fase 2 fa servir la recepta guanyadora (per validació) en totes les variants. Si guanya la
recepta nova, la comparació amb el baseline queda afectada per aquest canvi d'optimització, i així s'indica.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .. import plots
from ..config import BlockConfig, ExperimentConfig, baseline
from ..runner import summarize

SECTION = "7.4"
BASELINE = "BiLSTM (baseline)"
REFERENCE = {"d_model": 128, "nhead": 4, "num_layers": 2, "dim_feedforward": 256, "positional": "sinusoidal"}
RECIPES = {
    "recepta baseline": {},
    "LR 5e-4 + warmup": {"train.lr": 5e-4, "train.warmup_epochs": 2.0},
}
RNN = baseline().model.blocks[0]
FAMILIES: dict[str, str] = {BASELINE: "Referència"}

# Fase 2: variacions d'un sol factor sobre el Transformer de referència.
VARIANTS: dict[str, tuple[str, dict[str, Any]]] = {
    "Transformer 1 capa": ("Profunditat", {"num_layers": 1}),
    "Transformer 4 capes": ("Profunditat", {"num_layers": 4}),
    "Transformer 2 caps": ("Caps d'atenció", {"nhead": 2}),
    "Transformer 8 caps": ("Caps d'atenció", {"nhead": 8}),
    "Transformer FF 512": ("Feed-forward", {"dim_feedforward": 512}),
    "Transformer pos. apresa": ("Posició", {"positional": "learned"}),
    "Transformer sense posició": ("Posició", {"positional": "none"}),
}
HYBRIDS: dict[str, dict[str, Any]] = {
    "BiLSTM + atenció 1 capa": {"d_model": 256, "nhead": 4, "num_layers": 1, "dim_feedforward": 512, "positional": "none"},
    "BiLSTM + atenció 2 capes": {"d_model": 256, "nhead": 4, "num_layers": 2, "dim_feedforward": 512, "positional": "none"},
}


def _transformer(name: str, family: str, params: dict[str, Any], recipe: dict[str, Any],
                 with_rnn: bool = False) -> ExperimentConfig:
    blocks = ([RNN] if with_rnn else []) + [BlockConfig("transformer", params)]
    FAMILIES[name] = family
    return baseline().with_(name, SECTION, **{"model.blocks": blocks, **recipe})


def configs() -> list[ExperimentConfig]:
    """Fase 1: el baseline i el Transformer de referència amb cadascuna de les dues receptes."""
    out = [baseline().with_(BASELINE, SECTION)]
    out += [_transformer(f"Transformer ref. ({name})", "Recepta", REFERENCE, recipe) for name, recipe in RECIPES.items()]
    return out


def best_recipe(stage1_results: list[dict[str, Any]]) -> str:
    summary = summarize(stage1_results)
    scores = {name: summary.loc[f"Transformer ref. ({name})", "val_entity_f1_mean"] for name in RECIPES}
    winner = max(scores, key=scores.get)
    print("Recepta guanyadora per validació:", winner)
    return winner


def variant_configs(stage1_results: list[dict[str, Any]]) -> list[ExperimentConfig]:
    """Fase 2: variacions del Transformer i híbrids BiLSTM + atenció, tots amb la recepta guanyadora."""
    recipe = RECIPES[best_recipe(stage1_results)]
    out = [_transformer(name, family, {**REFERENCE, **change}, recipe) for name, (family, change) in VARIANTS.items()]
    out += [_transformer(name, "Híbrid", params, recipe, with_rnn=True) for name, params in HYBRIDS.items()]
    return out


def report(results: list[dict[str, Any]], save_as: str | None = "ex7_4_transformer") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula resum i figura de F1 i cost de totes les variants de Transformer davant del baseline."""
    summary = summarize(results)
    summary.insert(0, "family", [FAMILIES.get(name, "Altres") for name in summary.index])
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=summary["family"], with_cost=True)
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
