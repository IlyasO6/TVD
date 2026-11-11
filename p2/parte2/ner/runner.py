"""Execució de graelles d'experiments amb cache a disc i diversos processos en paral·lel.

Cada execució (configuració + llavor) es guarda en un JSON propi tan bon punt acaba. Si Colab es desconnecta,
en tornar a llançar la mateixa graella només s'entrenen les que falten. Com que aquests models són molt
petits i una sola execució aprofita una fracció mínima de la GPU, en llançar-ne diverses alhora el temps
total baixa sense canviar cap resultat (cada procés té la seva llavor i el seu propi model).
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import torch

from .config import ExperimentConfig
from .data import PACKAGE_ROOT

DEFAULT_SEEDS = (0, 1, 2)
SUMMARY_METRICS = ("val_entity_f1", "test_entity_f1", "test_entity_f1_macro", "test_token_f1_macro")


def results_dir() -> Path:
    """Carpeta de resultats; a Colab convé apuntar NER_RESULTS_DIR a Google Drive perquè sobrevisqui."""
    path = Path(os.environ.get("NER_RESULTS_DIR", PACKAGE_ROOT.parent / "results"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _result_path(cfg: ExperimentConfig) -> Path:
    return results_dir() / f"{cfg.key()}.json"


def run_one(cfg_dict: dict[str, Any], device: str | None = None, threads: int | None = None) -> dict[str, Any]:
    """Entrena una configuració si no és a la cache; rep un dict perquè sigui fàcil d'enviar a un altre procés."""
    from .train import train_and_evaluate  # import tardà: els processos fills només carreguen torch aquí

    cfg = ExperimentConfig.from_dict(cfg_dict)
    path = _result_path(cfg)
    if path.exists():
        result = json.loads(path.read_text(encoding="utf-8"))
    else:
        if threads:
            torch.set_num_threads(threads)
        device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        result = train_and_evaluate(cfg, device)
        # Escriptura atòmica: un fitxer a mitges per una desconnexió no s'ha de llegir com a resultat vàlid.
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result), encoding="utf-8")
        tmp.replace(path)
    # El nom i l'apartat són etiquetes de presentació: es prenen de la petició actual, no del fitxer.
    result["name"], result["section"] = cfg.name, cfg.section
    return result


def expand_seeds(configs: Iterable[ExperimentConfig], seeds: Iterable[int] = DEFAULT_SEEDS) -> list[ExperimentConfig]:
    return [cfg.with_(seed=s) for cfg in configs for s in seeds]


def run_grid(configs: Iterable[ExperimentConfig], seeds: Iterable[int] = DEFAULT_SEEDS, n_workers: int = 1,
             device: str | None = None) -> list[dict[str, Any]]:
    """Executa totes les configuracions amb totes les llavors i retorna els resultats en l'ordre d'entrada."""
    runs = expand_seeds(configs, seeds)
    pending = [i for i, cfg in enumerate(runs) if not _result_path(cfg).exists()]
    print(f"{len(runs)} execucions, {len(runs) - len(pending)} ja a la cache, {len(pending)} per entrenar")
    results: list[dict[str, Any] | None] = [None] * len(runs)
    start = time.perf_counter()

    def log(done: int, res: dict[str, Any]) -> None:
        elapsed = time.perf_counter() - start
        print(f"[{done}/{len(pending)}] {res['name']} (seed {res['seed']}): val F1 {res['val']['entity_f1']:.4f}, "
              f"{res['epochs_run']} èpoques, {elapsed / 60:.1f} min")

    if n_workers <= 1 or len(pending) <= 1:
        for done, i in enumerate(pending, 1):
            results[i] = run_one(runs[i].to_dict(), device)
            log(done, results[i])
    else:
        threads = max(1, (os.cpu_count() or 2) // n_workers)
        # spawn és obligatori amb CUDA: un fork heretaria el context de la GPU del procés pare.
        with ProcessPoolExecutor(n_workers, mp_context=mp.get_context("spawn")) as pool:
            futures = {pool.submit(run_one, runs[i].to_dict(), device, threads): i for i in pending}
            for done, future in enumerate(as_completed(futures), 1):
                results[futures[future]] = future.result()
                log(done, results[futures[future]])

    for i, cfg in enumerate(runs):
        if results[i] is None:
            results[i] = run_one(cfg.to_dict())
    return results


def to_frame(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Una fila per execució amb les mètriques de validació i test aplanades (prefixos val_ i test_)."""
    rows = []
    for r in results:
        row = {k: r[k] for k in ("name", "section", "seed", "key", "best_epoch", "epochs_run", "n_params", "sec_per_epoch")}
        row.update({f"val_{k}": v for k, v in r["val"].items()})
        row.update({f"test_{k}": v for k, v in r["test"].items()})
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(results: list[dict[str, Any]], metrics: Iterable[str] = SUMMARY_METRICS,
              extra: Iterable[str] = ("n_params", "best_epoch", "sec_per_epoch")) -> pd.DataFrame:
    """Mitjana i desviació per configuració, mantenint l'ordre en què s'han definit a la graella."""
    df = to_frame(results)
    order = list(dict.fromkeys(df["name"]))
    metrics, extra = list(metrics), list(extra)
    grouped = df.groupby("name", sort=False)
    out = pd.concat({"mean": grouped[metrics].mean(), "std": grouped[metrics].std(ddof=1)}, axis=1)
    out.columns = [f"{m}_{stat}" for stat, m in out.columns]
    out = out[[f"{m}_{s}" for m in metrics for s in ("mean", "std")]]
    out = out.join(grouped[extra].mean())
    out["n_seeds"] = grouped.size()
    return out.loc[order]


def best_by_val(results: list[dict[str, Any]], metric: str = "val_entity_f1") -> str:
    """Nom de la configuració amb millor mitjana de validació; mai es tria mirant el test."""
    return summarize(results, metrics=[metric], extra=[])[f"{metric}_mean"].idxmax()
