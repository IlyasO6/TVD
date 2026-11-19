"""Estil comú i gràfics reutilitzables per a l'Exercici 7 i l'informe.

Tots els gràfics comparteixen paleta, mida de lletra i forma de mostrar la variància entre llavors (mitjana
± desviació), perquè les figures de l'informe es llegeixin com un conjunt. Els colors segueixen un ordre
fix i validat per a daltonisme; la identitat de cada sèrie també es dona amb etiquetes, mai només amb color.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import PACKAGE_ROOT

PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dd"
FIGURES_DIR = PACKAGE_ROOT.parent / "figures"


def setup_style() -> None:
    """Estil sobri: eixos i graella discrets perquè l'atenció vagi a les dades."""
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.labelsize": 10,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "axes.titlecolor": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.prop_cycle": plt.cycler(color=PALETTE),
        "lines.linewidth": 2, "lines.markersize": 6,
        "legend.frameon": False,
    })


def save(fig: plt.Figure, name: str) -> Path:
    """Desa la figura en PDF (vectorial, per a l'informe) i PNG a la carpeta figures/."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIGURES_DIR / f"{name}.{ext}")
    return FIGURES_DIR / f"{name}.pdf"


def line_with_errors(ax: plt.Axes, x: Sequence[float], summary: pd.DataFrame, names: Sequence[str],
                     metric: str, label: str | None = None, color: str | None = None) -> None:
    """Línia de la mitjana amb barres d'error (desviació entre llavors) per a les configuracions `names`."""
    mean = summary.loc[list(names), f"{metric}_mean"].to_numpy()
    std = summary.loc[list(names), f"{metric}_std"].fillna(0).to_numpy()
    ax.errorbar(x, mean, yerr=std, marker="o", capsize=3, label=label, color=color)


def dot_plot(summary: pd.DataFrame, metric: str, baseline: str | None = None, title: str = "",
             xlabel: str = "F1 d'entitats", ax: plt.Axes | None = None, order: Sequence[str] | None = None,
             groups: pd.Series | None = None) -> plt.Axes:
    """Punts horitzontals amb mitjana ± desviació i una línia vertical al valor del baseline.

    Per defecte s'ordena per la mètrica; amb `order` es pot fixar el mateix ordre a diversos panells perquè
    es puguin comparar fila a fila. Amb `groups` cada família té un color (el baseline sempre en negre).
    """
    data = summary.loc[list(order)[::-1]] if order is not None else summary.sort_values(f"{metric}_mean")
    mean, std = data[f"{metric}_mean"], data[f"{metric}_std"].fillna(0)
    ax = ax or plt.subplots(figsize=(7, 0.38 * len(data) + 1))[1]
    y = np.arange(len(data))
    if groups is not None:
        # La família del baseline només es descarta si no té cap altre membre que s'hagi de pintar.
        members = groups.loc[summary.index]
        only_baseline = {g for g in members.unique() if set(members[members == g].index) <= {baseline}}
        families = [g for g in dict.fromkeys(members) if g not in only_baseline]
        family_color = dict(zip(families, PALETTE))
        colors = [INK if name == baseline else family_color[groups[name]] for name in data.index]
        for family, color in family_color.items():
            ax.scatter([], [], color=color, s=48, label=family)
    else:
        colors = [INK if name == baseline else PALETTE[0] for name in data.index]
    ax.errorbar(mean, y, xerr=std, fmt="none", ecolor=MUTED, capsize=3, linewidth=1.2)
    ax.scatter(mean, y, color=colors, s=48, zorder=3)
    # L'etiqueta va després de la barra d'error perquè no s'hi solapi.
    for yi, m, s in zip(y, mean, std):
        ax.annotate(f"{m:.3f}", (m + s, yi), xytext=(6, 0), textcoords="offset points", va="center", fontsize=8, color=MUTED)
    if baseline is not None and baseline in summary.index:
        ax.axvline(summary.loc[baseline, f"{metric}_mean"], color=INK, linestyle="--", linewidth=1, zorder=1)
    ax.set_yticks(y, data.index)
    ax.grid(axis="y", visible=False)
    ax.set(xlabel=xlabel, title=title)
    return ax


def comparison_figure(summary: pd.DataFrame, baseline: str, groups: pd.Series | None = None,
                      with_cost: bool = False) -> plt.Figure:
    """Figura estàndard d'un apartat: F1 de validació i de test i, opcionalment, el cost de cada configuració.

    Tots els panells comparteixen l'ordre de validació perquè una fila es llegeixi de cap a cap; el test
    només s'observa i no decideix l'ordre. El panell de cost mostra els paràmetres entrenables amb el temps
    per època anotat, per poder parlar de quant costa cada punt de F1.
    """
    order = summary["val_entity_f1_mean"].sort_values(ascending=False).index
    n_panels = 3 if with_cost else 2
    widths = [1, 1, 0.6][:n_panels]
    fig, axes = plt.subplots(1, n_panels, figsize=(4.6 * sum(widths) + 3, 0.34 * len(summary) + 1.8),
                             sharey=True, gridspec_kw={"width_ratios": widths})
    for ax, metric, title in zip(axes, ("val_entity_f1", "test_entity_f1"), ("Validació", "Test")):
        dot_plot(summary, metric, baseline=baseline, title=title, ax=ax, order=order, groups=groups)
    if with_cost:
        data = summary.loc[list(order)[::-1]]
        y = np.arange(len(data))
        ax = axes[2]
        ax.barh(y, data["n_params"] / 1e3, height=0.55, color=GRID, edgecolor=MUTED, linewidth=0.6)
        for yi, (params, secs) in enumerate(zip(data["n_params"] / 1e3, data["sec_per_epoch"])):
            ax.annotate(f"{secs:.1f} s/ep", (params, yi), xytext=(4, 0), textcoords="offset points",
                        va="center", fontsize=8, color=MUTED)
        ax.grid(axis="y", visible=False)
        ax.set(xlabel="Paràmetres (milers)", title="Cost")
        ax.set_xlim(0, (data["n_params"] / 1e3).max() * 1.45)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.tight_layout(rect=(0, 0.05 if handles else 0, 1, 1))
    if handles:
        # La llegenda va a sota, fora dels eixos, perquè no tapi cap punt sigui quin sigui el resultat.
        fig.legend(handles, labels, loc="lower center", ncols=len(labels), fontsize=9)
    return fig


def learning_curves(results: list[dict[str, Any]], names: Iterable[str], ax: plt.Axes | None = None,
                    title: str = "Loss d'entrenament i validació", labels: Iterable[str] | None = None) -> plt.Axes:
    """Loss mitjana per època (sobre llavors) de train (discontínua) i validació (contínua) per configuració."""
    ax = ax or plt.subplots(figsize=(6.5, 3.5))[1]
    names = list(names)
    for color, name, label in zip(PALETTE, names, labels or names):
        runs = [r for r in results if r["name"] == name]
        for key, style in (("train_loss", "--"), ("val_loss", "-")):
            curves = [r["history"][key] for r in runs]
            n = min(map(len, curves))  # l'early stopping fa que cada llavor s'aturi en una època diferent
            ax.plot(range(1, n + 1), np.mean([c[:n] for c in curves], axis=0), style, color=color,
                    label=f"{label} ({'train' if key == 'train_loss' else 'val'})")
    ax.set(xlabel="Època", ylabel="Loss", title=title, yscale="log")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.legend(fontsize=8)
    return ax


def grouped_bars(summary: pd.DataFrame, metrics: Sequence[str], metric_labels: Sequence[str],
                 ax: plt.Axes | None = None, title: str = "", ylabel: str = "F1") -> plt.Axes:
    """Barres agrupades per configuració (una barra per mètrica) amb barres d'error."""
    ax = ax or plt.subplots(figsize=(7, 3.5))[1]
    x = np.arange(len(summary))
    width = 0.8 / len(metrics)
    for i, (metric, label) in enumerate(zip(metrics, metric_labels)):
        ax.bar(x + (i - (len(metrics) - 1) / 2) * width, summary[f"{metric}_mean"], width * 0.92,
               yerr=summary[f"{metric}_std"].fillna(0), capsize=2, label=label, color=PALETTE[i],
               error_kw={"ecolor": MUTED, "linewidth": 1})
    ax.set_xticks(x, summary.index, rotation=20, ha="right")
    ax.grid(axis="x", visible=False)
    ax.set(ylabel=ylabel, title=title)
    ax.legend(fontsize=8, ncols=len(metrics))
    return ax
