"""Model final, ablació i significança.

El model final es construeix automàticament amb els resultats de validació de cada apartat, sense mirar mai
el test. De cada apartat s'agafa la configuració guanyadora i només s'incorpora al model final si millora la
seva referència per més d'una desviació estàndard entre llavors; si no, la diferència no es distingeix del
soroll i el component no s'hi afegeix. Cada component és una funció que modifica la configuració, de manera
que l'ablació consisteix a reconstruir el model final ometent-ne un cada vegada.

Que cada component ajudi per separat no garanteix que ajudi en combinació (per exemple, el dropout i els
pesos de classe regularitzen tots dos), i per això l'ablació es fa amb 5 llavors: si treure un component
millora el model final, l'ablació ho mostra i es reporta tal qual.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .. import plots
from ..config import BlockConfig, ExperimentConfig, baseline
from ..data import prepare_data
from ..metrics import paired_bootstrap
from ..runner import summarize

SECTION = "final"
FINAL = "model final"
BASELINE = "baseline"
FINAL_SEEDS = (0, 1, 2, 3, 4)
Component = Callable[[ExperimentConfig], ExperimentConfig]


def _summary(results: list[dict[str, Any]]) -> pd.DataFrame:
    return summarize(results, metrics=["val_entity_f1", "test_entity_f1"], extra=[])


def _winner(results: list[dict[str, Any]], reference: str, candidates: list[str] | None = None
            ) -> tuple[str | None, float]:
    """Millor configuració per validació i el seu guany; None si no supera la referència més enllà del soroll."""
    s = _summary(results)
    pool = s.loc[[c for c in (candidates or s.index) if c in s.index and c != reference]]
    best = pool["val_entity_f1_mean"].idxmax()
    gain = pool.loc[best, "val_entity_f1_mean"] - s.loc[reference, "val_entity_f1_mean"]
    noise = s.loc[reference, "val_entity_f1_std"]
    noise = 0.0 if np.isnan(noise) else noise
    return (best if gain > noise else None), float(gain)


def _config_of(results: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(r["config"] for r in results if r["name"] == name)


def _copy_fields(source: dict[str, Any], paths: list[str]) -> Component:
    """Component que copia uns camps concrets de la configuració guanyadora d'un apartat."""
    def get(path: str) -> Any:
        value = source
        for part in path.split("."):
            value = value[part]
        return value

    def apply(cfg: ExperimentConfig) -> ExperimentConfig:
        overrides = {}
        for path in paths:
            value = get(path)
            if path == "model.blocks":
                value = [BlockConfig(**b) for b in value]
            elif path == "model.char_encoder" and value is not None:
                value = BlockConfig(**value)
            overrides[path] = copy.deepcopy(value)
        return cfg.with_(**overrides)
    return apply


def _dropout(source: dict[str, Any]) -> Component:
    """Component de dropout: reaplica les probabilitats guanyadores a les posicions que tingui el model final."""
    blocks = source["model"]["blocks"]
    p_between = next((b["params"].get("dropout", 0.0) for b in blocks if b["kind"] == "rnn"), 0.0)
    p_intern = next((b["params"].get("dropout", 0.0) for b in blocks if b["kind"] == "transformer"), 0.0)

    def apply(cfg: ExperimentConfig) -> ExperimentConfig:
        cfg = cfg.with_(**{"model.embedding_dropout": source["model"]["embedding_dropout"],
                           "model.classifier_dropout": source["model"]["classifier_dropout"]})
        for block in cfg.model.blocks:
            if block.kind == "rnn" and block.params.get("num_layers", 1) > 1 and p_between:
                block.params["dropout"] = p_between
            if block.kind == "transformer" and p_intern:
                block.params["dropout"] = p_intern
        return cfg
    return apply


def _strip_dropout(blocks: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(b["kind"], {k: v for k, v in b["params"].items() if k != "dropout"}) for b in blocks]


def build_final(results: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Component], list[str]]:
    """Tria els components del model final a partir dels resultats de cada apartat (claus "7.1"... "extra")."""
    from . import ex7_1, ex7_2, ex7_3, ex7_4, ex7_6, extras

    components: dict[str, Component] = {}
    gains: dict[str, float] = {}
    log: list[str] = []

    def consider(label: str, section: str, reference: str, make: Callable[[dict[str, Any]], Component],
                 candidates: list[str] | None = None, res: list[dict[str, Any]] | None = None) -> str | None:
        res = res if res is not None else results[section]
        best, gain = _winner(res, reference, candidates)
        verdict = f"s'afegeix '{best}'" if best else "no millora més enllà del soroll"
        log.append(f"{label} ({section}): {verdict} (guany de validació {gain:+.4f})")
        if best:
            components[label] = make(_config_of(res, best))
            gains[label] = gain
        return best

    consider("embedding", "7.1", ex7_1._random(128),
             lambda c: _copy_fields(c, ["model.embedding_dim", "model.pretrained", "model.freeze_embeddings", "data.min_freq"]))
    char_names = [n for n, (fam, _, _) in ex7_2.GRID.items() if fam == "Char-CNN"]
    consider("char-CNN", "7.2", ex7_2.BASELINE, lambda c: _copy_fields(c, ["model.char_encoder"]), candidates=char_names)

    # Arquitectura de l'encoder: la millor entre totes les variants sense char-CNN de 7.2, 7.3 i 7.4.
    # El baseline surt a cada apartat amb un nom diferent: s'unifica i es treuen duplicats (mateixa clau i llavor).
    base_names = {ex7_2.BASELINE, ex7_3.BASELINE, ex7_4.BASELINE}
    arch_results, seen = [], set()
    for r in (r for s in ("7.2", "7.3", "7.4") for r in results[s] if r["config"]["model"]["char_encoder"] is None):
        if r["key"] in seen:
            continue
        seen.add(r["key"])
        arch_results.append({**r, "name": BASELINE} if r["name"] in base_names else r)
    arch = consider("encoder", "7.2-7.4", BASELINE,
                    lambda c: _copy_fields(c, ["model.blocks", "train.lr", "train.warmup_epochs"]), res=arch_results)

    # El dropout es pren del model de 7.5 que més s'assembla a l'encoder triat.
    final_blocks = _strip_dropout(_config_of(arch_results, arch)["model"]["blocks"]) if arch else _strip_dropout(
        [{"kind": b.kind, "params": b.params} for b in baseline().model.blocks])
    suffix = " sense dropout"
    models = list(dict.fromkeys(r["name"][:-len(suffix)] for r in results["7.5"] if r["name"].endswith(suffix)))
    match = next((m for m in models if _strip_dropout(_config_of(results["7.5"], f"{m} sense dropout")["model"]["blocks"])
                  == final_blocks), None)
    if match is None:
        has_transformer = any(kind == "transformer" for kind, _ in final_blocks)
        deep = any(kind == "rnn" and p.get("num_layers", 1) > 1 for kind, p in final_blocks)
        match = models[2] if has_transformer else models[1] if deep else models[0]
    log.append(f"dropout: es fa servir el model de 7.5 '{match}'")
    consider("dropout", "7.5", f"{match} sense dropout", _dropout,
             candidates=[n for n in _summary(results["7.5"]).index if n.startswith(match)])

    consider("pesos de classe", "7.6", ex7_6.BASELINE,
             lambda c: _copy_fields(c, ["train.class_weighting", "train.weight_clip", "train.o_weight", "train.effective_beta"]))
    extra_pairs = ["BILOU + CRF", "BIO + softmax", "BIO + CRF"]
    best_extra = consider("esquema i decodificador", "extra", extras.BASELINE,
                          lambda c: _copy_fields(c, ["data.scheme", "model.decoder"]), candidates=extra_pairs)

    # El CRF no admet pesos de classe: si tots dos han guanyat, es queda el que millorava més la seva referència.
    if best_extra and "CRF" in best_extra and "pesos de classe" in components:
        drop = "pesos de classe" if gains["esquema i decodificador"] >= gains["pesos de classe"] else "esquema i decodificador"
        components.pop(drop)
        log.append(f"conflicte CRF / pesos de classe: es descarta '{drop}' (menor guany a la seva secció)")
    return components, log


def compose(components: dict[str, Component], skip: str | None = None) -> ExperimentConfig:
    cfg = baseline()
    for name, component in components.items():
        if name != skip:
            cfg = component(cfg)
    return cfg


def ablation_configs(components: dict[str, Component]) -> list[ExperimentConfig]:
    """Baseline, model final i model final sense cada component; es llancen amb FINAL_SEEDS."""
    out = [baseline().with_(BASELINE, SECTION), compose(components).with_(FINAL, SECTION)]
    out += [compose(components, skip=name).with_(f"final − {name}", SECTION) for name in components]
    return out


def significance(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Bootstrap pareat sobre les oracions de test entre baseline i model final, llavor a llavor."""
    data = prepare_data(baseline().data)
    gold = data.splits["test"].gold
    rows = {}
    for seed in sorted({r["seed"] for r in results}):
        base = next((r for r in results if r["name"] == BASELINE and r["seed"] == seed), None)
        final = next((r for r in results if r["name"] == FINAL and r["seed"] == seed), None)
        if base is None or final is None:
            continue
        # El gold es construeix amb l'esquema de cada model; les entitats són les mateixes en tots dos.
        final_gold = prepare_data(ExperimentConfig.from_dict(final["config"]).data).splits["test"].gold
        assert len(final_gold) == len(gold)
        rows[seed] = paired_bootstrap(gold, [p.split() for p in base["test_pred"]], [p.split() for p in final["test_pred"]],
                                      "BILOU", gold_b=final_gold, scheme_b=final["config"]["data"]["scheme"])
    return pd.DataFrame(rows).T


def report(results: list[dict[str, Any]], save_as: str | None = "final_ablacio") -> tuple[pd.DataFrame, plt.Figure]:
    """Taula i figura de l'ablació: quant perd el model final quan se li treu cada component."""
    summary = summarize(results)
    groups = pd.Series({n: "Model final" if n == FINAL else "Ablació" if n.startswith("final −") else "Baseline"
                        for n in summary.index})
    plots.setup_style()
    fig = plots.comparison_figure(summary, BASELINE, groups=groups, with_cost=True)
    if save_as:
        plots.save(fig, save_as)
    return summary, fig


def overview_figure(section_results: dict[str, list[dict[str, Any]]], final_results: list[dict[str, Any]],
                    save_as: str | None = "resum_global") -> tuple[pd.DataFrame, plt.Figure]:
    """Dot plot resum: millor configuració de cada apartat (per validació), baseline i model final, a test."""
    rows = []
    for section, res in section_results.items():
        s = summarize(res)
        best = s["val_entity_f1_mean"].idxmax()
        rows.append(s.loc[[best]].rename(index={best: f"{section}: {best}"}))
    final_summary = summarize(final_results)
    rows.append(final_summary.loc[[BASELINE, FINAL]])
    summary = pd.concat(rows)
    groups = pd.Series({n: "Model final" if n == FINAL else "Baseline" if n == BASELINE else "Millor de l'apartat"
                        for n in summary.index})
    plots.setup_style()
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(summary) + 1.6))
    plots.dot_plot(summary, "test_entity_f1", baseline=BASELINE, groups=groups, ax=ax,
                   title="F1 d'entitats a test (mitjana ± desviació entre llavors)")
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    if save_as:
        plots.save(fig, save_as)
    return summary, fig
