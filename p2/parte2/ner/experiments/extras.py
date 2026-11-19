"""Experiments addicionals: decodificador CRF, esquema d'etiquetes (BIO vs BILOU) i mida del vocabulari.

Esquema i decodificador es creuen en un disseny 2×2 perquè interactuen: BILOU dona al model més informació
sobre els límits de les entitats però multiplica les classes (178 enfront de 119) i les transicions
prohibides, i el CRF és justament el mecanisme que aprèn quines transicions són vàlides. La F1 d'entitats
és comparable entre esquemes perquè la conversió BIO→BILOU no perd informació: el conjunt d'entitats de
referència és exactament el mateix i només canvia com s'etiqueten per dins.

Hipòtesis. Amb softmax, BILOU hauria de produir més seqüències invàlides que BIO (hi ha més maneres
d'equivocar-se) i el CRF les hauria de reduir gairebé a zero, amb una millora petita de F1 que vindria
sobretot dels límits de les entitats llargues (Lample et al., 2016). Ratinov & Roth (2009) troben que
BILOU supera BIO en NER; amb un corpus petit l'avantatge podria quedar compensat per tenir més classes amb
menys exemples cadascuna. Pel que fa al vocabulari, amb `min_freq = 1` el model coneix 243 paraules més,
però cadascuna amb un sol exemple, i l'embedding de `<unk>` gairebé no s'entrena; esperem una diferència
petita, possiblement a favor de `min_freq = 2` a test, on hi ha més paraules desconegudes.
"""

from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from .. import plots
from ..config import ExperimentConfig, baseline
from ..runner import summarize, to_frame

SECTION = "extra"
BASELINE = "BILOU + softmax (baseline)"
GRID: dict[str, tuple[str, dict[str, Any]]] = {
    BASELINE: ("Referència", {}),
    "BILOU + CRF": ("Decodificador", {"model.decoder": "crf"}),
    "BIO + softmax": ("Esquema", {"data.scheme": "BIO"}),
    "BIO + CRF": ("Esquema", {"data.scheme": "BIO", "model.decoder": "crf"}),
    "min_freq = 1": ("Vocabulari", {"data.min_freq": 1}),
}


def configs() -> list[ExperimentConfig]:
    return [baseline().with_(name, SECTION, **overrides) for name, (_, overrides) in GRID.items()]


def invalid_table(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Mitjana d'oracions amb alguna transició impossible a validació i a test, per configuració."""
    df = to_frame(results)
    out = df.groupby("name", sort=False)[["val_invalid_sequences", "test_invalid_sequences"]].mean()
    return out.rename(columns={"val_invalid_sequences": "invàlides val (de 900)",
                               "test_invalid_sequences": "invàlides test (de 893)"})


def report(results: list[dict[str, Any]], save_as: str | None = "extra_crf_esquema") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula amb F1, cost i seqüències invàlides, i figura comparativa."""
    summary = summarize(results).join(invalid_table(results))
    summary.insert(0, "family", [GRID[name][0] for name in summary.index])
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=summary["family"], with_cost=True)
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
