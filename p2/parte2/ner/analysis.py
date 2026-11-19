"""Anàlisi d'errors a nivell d'entitat.

La F1 diu quant s'equivoca el model però no com. Aquí cada error es classifica en una de quatre categories:
tipus equivocat (el tram és correcte però l'etiqueta no, per exemple `fromloc` en lloc de `toloc`), límits
equivocats (es detecta l'entitat amb el tipus correcte però amb el tram més llarg o més curt), entitat no
detectada i entitat inventada. Les confusions de tipus més freqüents mostren quines distincions semàntiques
costen més al model.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

Span = tuple[int, int, str]   # (inici, final exclusiu, tipus)


def spans(tags: list[str]) -> set[Span]:
    """Extreu les entitats d'una seqüència BIO o BILOU (U i L es tracten com B i I tancant l'entitat)."""
    out, start, kind = set(), None, None
    for i, tag in enumerate(tags + ["O"]):
        prefix, _, entity = tag.partition("-")
        continues = prefix in {"I", "L"} and entity == kind
        if start is not None and not continues:
            out.add((start, i, kind))
            start, kind = None, None
        if prefix in {"B", "U"} or (prefix in {"I", "L"} and start is None):
            start, kind = i, entity
        if prefix in {"L", "U"} and start is not None:
            out.add((start, i + 1, kind))
            start, kind = None, None
    return out


def _overlap(a: Span, b: Span) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def classify_errors(gold: list[list[str]], pred: list[list[str]]) -> tuple[Counter, Counter]:
    """Recompte de categories d'error i de confusions de tipus (tipus real → tipus predit) en mateix tram."""
    categories, confusions = Counter(), Counter()
    for g_tags, p_tags in zip(gold, pred):
        g, p = spans(g_tags), spans(p_tags)
        missing, extra = g - p, p - g
        used = set()
        for gs in missing:
            same_span = [ps for ps in extra if ps[:2] == gs[:2]]
            same_type = [ps for ps in extra if ps[2] == gs[2] and _overlap(ps, gs)]
            if same_span:
                categories["tipus equivocat"] += 1
                confusions[(gs[2], same_span[0][2])] += 1
                used.add(same_span[0])
            elif same_type:
                categories["límits equivocats"] += 1
                used.add(same_type[0])
            else:
                categories["no detectada"] += 1
        categories["inventada"] += len(extra - used)
    return categories, confusions


def error_summary(gold: list[list[str]], pred: list[list[str]], top: int = 10) -> tuple[pd.Series, pd.DataFrame]:
    """Categories d'error en proporció i taula de les confusions de tipus més freqüents."""
    categories, confusions = classify_errors(gold, pred)
    total = sum(categories.values())
    cat = pd.Series({k: v / total for k, v in categories.most_common()}, name="proporció d'errors")
    conf = pd.DataFrame([{"real": a, "predit": b, "vegades": n} for (a, b), n in confusions.most_common(top)])
    return cat, conf


def error_examples(sentences: list[list[str]], gold: list[list[str]], pred: list[list[str]],
                   n: int = 5, kinds: tuple[str, ...] = ("fromloc", "toloc", "depart", "arrive")) -> list[str]:
    """Oracions curtes amb errors que impliquen els tipus indicats, amb les etiquetes reals i predites alineades."""
    examples, seen = [], set()
    for words, g, p in sorted(zip(sentences, gold, pred), key=lambda x: len(x[0])):
        wrong = [i for i, (a, b) in enumerate(zip(g, p)) if a != b]
        # ATIS repeteix algunes oracions idèntiques; cada una es mostra un sol cop.
        if not wrong or " ".join(words) in seen or not any(k in g[i] + p[i] for i in wrong for k in kinds):
            continue
        seen.add(" ".join(words))
        rows = [f"{w:<14} {a:<32} {b}{'  ✗' if a != b else ''}" for w, a, b in zip(words, g, p)]
        examples.append("\n".join([f"{'paraula':<14} {'real':<32} predit", *rows]))
        if len(examples) == n:
            break
    return examples


def median_seed_result(results: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """Execució amb la F1 de validació mediana: representa el model sense triar la millor llavor."""
    runs = sorted((r for r in results if r["name"] == name), key=lambda r: r["val"]["entity_f1"])
    return runs[len(runs) // 2]
