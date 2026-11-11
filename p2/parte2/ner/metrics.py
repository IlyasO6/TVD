"""Mètriques d'avaluació del NER.

La mètrica principal és la F1 d'entitats en mode estricte (seqeval), equivalent a conlleval: una entitat
compta com a encert només si coincideixen tipus i límits. Les mètriques per token s'afegeixen perquè són
les que demana l'enunciat i perquè la F1 macro sense "O" és la que millor reflecteix les classes rares.
"""

from __future__ import annotations

from collections import Counter

import numpy as np
import pandas as pd
from seqeval.metrics import classification_report as seqeval_report
from seqeval.metrics import f1_score as seqeval_f1
from seqeval.metrics import precision_score, recall_score
from seqeval.scheme import BILOU, IOB2
from sklearn.metrics import accuracy_score, f1_score

Tags = list[list[str]]
SCHEMES = {"BILOU": BILOU, "BIO": IOB2}


def entity_scores(gold: Tags, pred: Tags, scheme: str) -> dict[str, float]:
    """Precisió, recall i F1 d'entitats (micro) i F1 macro per tipus d'entitat."""
    kw = {"mode": "strict", "scheme": SCHEMES[scheme], "zero_division": 0}
    return {
        "entity_p": precision_score(gold, pred, **kw),
        "entity_r": recall_score(gold, pred, **kw),
        "entity_f1": seqeval_f1(gold, pred, **kw),
        "entity_f1_macro": seqeval_f1(gold, pred, average="macro", **kw),
    }


def entity_f1(gold: Tags, pred: Tags, scheme: str) -> float:
    return seqeval_f1(gold, pred, mode="strict", scheme=SCHEMES[scheme], zero_division=0)


def token_scores(gold: Tags, pred: Tags) -> dict[str, float]:
    """Accuracy per token i F1 macro/ponderada sense "O", que dominaria la mitjana si s'hi inclogués."""
    flat_gold = [t for s in gold for t in s]
    flat_pred = [t for s in pred for t in s]
    tags = sorted(set(flat_gold) - {"O"})
    return {
        "token_acc": accuracy_score(flat_gold, flat_pred),
        "token_f1_macro": f1_score(flat_gold, flat_pred, labels=tags, average="macro", zero_division=0),
        "token_f1_weighted": f1_score(flat_gold, flat_pred, labels=tags, average="weighted", zero_division=0),
    }


def f1_by_frequency(gold: Tags, pred: Tags, train_counts: Counter, bins: tuple[int, int] = (10, 100)) -> dict[str, float]:
    """F1 macro per token agrupant les etiquetes segons quants cops surten a train (rares, mitjanes, freqüents)."""
    flat_gold = [t for s in gold for t in s]
    flat_pred = [t for s in pred for t in s]
    low, high = bins
    groups = {"rare": [], "mid": [], "frequent": []}
    for tag in set(flat_gold) - {"O"}:
        count = train_counts.get(tag, 0)
        groups["rare" if count < low else "frequent" if count > high else "mid"].append(tag)
    return {
        f"f1_{name}": f1_score(flat_gold, flat_pred, labels=sorted(tags), average="macro", zero_division=0)
        if tags else float("nan")
        for name, tags in groups.items()
    }


def _is_valid(prev: str, tag: str, scheme: str) -> bool:
    """Transició permesa entre dues etiquetes consecutives segons l'esquema."""
    p_pre, p_ent = (prev.split("-", 1) + [""])[:2] if prev != "O" else ("O", "")
    t_pre, t_ent = (tag.split("-", 1) + [""])[:2] if tag != "O" else ("O", "")
    if scheme == "BIO":
        return t_pre != "I" or (p_pre in {"B", "I"} and p_ent == t_ent)
    inside = p_pre in {"B", "I"}           # l'entitat anterior encara és oberta
    if inside:
        return t_pre in {"I", "L"} and t_ent == p_ent
    return t_pre in {"O", "B", "U"}


def invalid_sequences(pred: Tags, scheme: str) -> int:
    """Nombre d'oracions predites amb almenys una transició impossible (p. ex. una I sense B, o B sense L)."""
    invalid = 0
    for tags in pred:
        seq = ["O"] + tags + ["O"]
        if any(not _is_valid(a, b, scheme) for a, b in zip(seq[:-1], seq[1:])):
            invalid += 1
    return invalid


def entity_report(gold: Tags, pred: Tags, scheme: str) -> pd.DataFrame:
    """Taula per tipus d'entitat (precisió, recall, F1, suport), útil per a l'anàlisi d'errors."""
    report = seqeval_report(gold, pred, mode="strict", scheme=SCHEMES[scheme], zero_division=0, output_dict=True)
    df = pd.DataFrame(report).T
    return df.drop(index=[i for i in df.index if "avg" in i]).sort_values("f1-score")


def all_scores(gold: Tags, pred: Tags, scheme: str, train_counts: Counter) -> dict[str, float]:
    """Totes les mètriques escalars d'una partició, en un sol diccionari per guardar al JSON de resultats."""
    return {
        **entity_scores(gold, pred, scheme),
        **token_scores(gold, pred),
        **f1_by_frequency(gold, pred, train_counts),
        "invalid_sequences": invalid_sequences(pred, scheme),
    }


def paired_bootstrap(gold: Tags, pred_a: Tags, pred_b: Tags, scheme: str, n_samples: int = 1000, seed: int = 0,
                     gold_b: Tags | None = None, scheme_b: str | None = None) -> dict[str, float]:
    """Bootstrap pareat sobre oracions: proporció de remostrejos en què B no supera A (p-valor unilateral).

    Si els dos models fan servir esquemes diferents (BIO i BILOU), cadascun s'avalua amb el seu gold; les
    entitats de referència són les mateixes, així que remostrejar les mateixes oracions continua sent pareat.
    """
    gold_b, scheme_b = gold_b or gold, scheme_b or scheme
    rng = np.random.default_rng(seed)
    n = len(gold)
    deltas = np.empty(n_samples)
    for i in range(n_samples):
        idx = rng.integers(0, n, n)
        f1_b = entity_f1([gold_b[j] for j in idx], [pred_b[j] for j in idx], scheme_b)
        deltas[i] = f1_b - entity_f1([gold[j] for j in idx], [pred_a[j] for j in idx], scheme)
    return {
        "delta": float(entity_f1(gold_b, pred_b, scheme_b) - entity_f1(gold, pred_a, scheme)),
        "ci_low": float(np.percentile(deltas, 2.5)),
        "ci_high": float(np.percentile(deltas, 97.5)),
        "p_value": float((deltas <= 0).mean()),
    }
