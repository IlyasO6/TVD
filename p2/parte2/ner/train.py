"""Bucle d'entrenament i avaluació comú a tots els experiments.

Fa servir el mateix procediment que l'Exercici 6 (Adam, gradient clipping, early stopping per F1
d'entitats a validació) perquè les comparacions entre variants siguin justes. Per anar més ràpid, les
particions es pugen senceres al dispositiu i cada batch es retalla a la longitud màxima que conté, cosa
que no canvia el resultat però evita processar desenes de posicions de padding.
"""

from __future__ import annotations

import copy
import random
import time
from typing import Any

import numpy as np
import torch

from .config import ExperimentConfig
from .data import PAD_LABEL_IDX, PreparedData, Split, prepare_data
from .metrics import all_scores, entity_f1
from .models import PRETRAINED, NERTagger


def set_seed(seed: int) -> None:
    """Fixa totes les fonts d'aleatorietat; cudnn determinista fa que dues execucions coincideixin a GPU."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def load_data_and_model(cfg: ExperimentConfig, device: torch.device) -> tuple[PreparedData, NERTagger]:
    """Prepara les dades que demana la configuració i construeix el model ja inicialitzat amb la llavor."""
    extra_words, vectors_fn = frozenset(), None
    if cfg.model.pretrained:
        vocab_fn, vectors_fn = PRETRAINED[cfg.model.pretrained]
        extra_words = vocab_fn()
    data = prepare_data(cfg.data, with_chars=cfg.model.char_encoder is not None, extra_words=extra_words)
    set_seed(cfg.seed)
    vectors = vectors_fn(data.word2idx) if vectors_fn else None
    model = NERTagger(cfg.model, len(data.word2idx), data.num_classes, len(data.char2idx), vectors)
    return data, model.to(device)


def class_weights(cfg: ExperimentConfig, data: PreparedData, device: torch.device) -> torch.Tensor | None:
    """Pesos de la cross-entropy segons la freqüència de cada etiqueta a train.

    Es normalitzen perquè el pes mitjà per token de train sigui 1 (el criteri "balanced" de scikit-learn).
    La cross-entropy de PyTorch amb pesos ja és una mitjana ponderada i no depèn de l'escala global, així
    que la normalització només serveix perquè el límit (`weight_clip`) i `o_weight` tinguin un significat
    clar: un pes de 10 vol dir que aquell token compta deu vegades més que el token mitjà.
    """
    t = cfg.train
    if t.class_weighting is None and t.o_weight is None:
        return None
    counts = np.array([data.label_counts.get(data.idx2label[i], 1) for i in range(data.num_classes)], dtype=float)
    if t.class_weighting == "effective":
        # El nombre efectiu de mostres creix cada cop menys amb la freqüència, perquè exemples nous d'una classe
        # ja molt vista aporten poca informació; així el pes de les classes freqüents no cau tant com amb la inversa.
        weights = (1 - t.effective_beta) / (1 - t.effective_beta ** counts)
    else:
        power = {None: 0.0, "inverse": 1.0, "inverse_sqrt": 0.5}[t.class_weighting]
        weights = (counts.sum() / counts) ** power
    weights[PAD_LABEL_IDX] = 0.0
    real = np.arange(data.num_classes) != PAD_LABEL_IDX
    weights[real] *= counts[real].sum() / (counts[real] * weights[real]).sum()
    if t.weight_clip is not None:
        weights[real] = np.minimum(weights[real], t.weight_clip)
    if t.o_weight is not None:
        weights[data.label2idx["O"]] = t.o_weight
    return torch.tensor(weights, dtype=torch.float, device=device)


def _batches(split: dict[str, torch.Tensor], batch_size: int, generator: torch.Generator | None = None):
    """Itera per batches retallats a la longitud màxima real; amb generador, en ordre aleatori reproduïble."""
    n = len(split["lengths"])
    order = torch.randperm(n, generator=generator) if generator is not None else torch.arange(n)
    for start in range(0, n, batch_size):
        idx = order[start:start + batch_size]
        lengths = split["lengths"][idx]
        max_len = int(lengths.max())
        batch = {k: v[idx.to(v.device)][:, :max_len] for k, v in split.items() if k != "lengths" and v is not None}
        yield batch, lengths


def _to_device(split: Split, device: torch.device) -> dict[str, torch.Tensor]:
    # Les longituds es queden a CPU perquè pack_padded_sequence les hi demana.
    return {"words": split.words.to(device), "labels": split.labels.to(device), "lengths": split.lengths,
            "chars": split.chars.to(device) if split.chars is not None else None}


def evaluate(model: NERTagger, split: dict[str, torch.Tensor], data: PreparedData, batch_size: int,
             weights: torch.Tensor | None = None) -> tuple[float, list[list[str]]]:
    """Loss mitjana i etiquetes predites en una sola passada sobre la partició."""
    model.eval()
    total_loss, n_batches, preds = 0.0, 0, []
    with torch.no_grad():
        for batch, lengths in _batches(split, batch_size):
            words, labels, chars = batch["words"], batch["labels"], batch.get("chars")
            feats, mask = model.features(words, lengths, chars)
            total_loss += model.decoder.loss(feats, labels, mask, weights).item()
            n_batches += 1
            decoded = model.decoder.decode(feats, mask).cpu().numpy()
            preds += [[data.idx2label[i] for i in row[:n]] for row, n in zip(decoded, lengths.tolist())]
    return total_loss / n_batches, preds


def train_and_evaluate(cfg: ExperimentConfig, device: torch.device | str = "cpu", verbose: bool = False) -> dict[str, Any]:
    """Entrena una configuració amb early stopping i retorna mètriques, historial i prediccions."""
    device = torch.device(device)
    data, model = load_data_and_model(cfg, device)
    t = cfg.train
    splits = {k: _to_device(s, device) for k, s in data.splits.items()}
    weights = class_weights(cfg, data, device)
    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.Adam(params, lr=t.lr, weight_decay=t.weight_decay)
    steps_per_epoch = -(-len(data.splits["train"].lengths) // t.batch_size)
    warmup_steps = max(1, int(t.warmup_epochs * steps_per_epoch))
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda step: min(1.0, (step + 1) / warmup_steps))
    generator = torch.Generator().manual_seed(cfg.seed)

    history = {"train_loss": [], "val_loss": [], "val_f1": []}
    best = {"f1": -1.0, "state": None, "epoch": 0}
    epoch_times = []
    for epoch in range(1, t.max_epochs + 1):
        start = time.perf_counter()
        model.train()
        total = 0.0
        for batch, lengths in _batches(splits["train"], t.batch_size, generator):
            loss = model.loss(batch["words"], batch["labels"], lengths, batch.get("chars"), weights)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, t.grad_clip)
            optimizer.step()
            scheduler.step()
            total += loss.item()
        epoch_times.append(time.perf_counter() - start)

        val_loss, val_pred = evaluate(model, splits["val"], data, t.batch_size, weights)
        val_f1 = entity_f1(data.splits["val"].gold, val_pred, cfg.data.scheme)
        for key, value in zip(("train_loss", "val_loss", "val_f1"), (total / steps_per_epoch, val_loss, val_f1)):
            history[key].append(value)
        if verbose:
            print(f"Epoch {epoch:02d} | train {history['train_loss'][-1]:.4f} | val {val_loss:.4f} | F1 {val_f1:.4f}")
        # Només es considera millora si supera min_delta, per no allargar l'entrenament per soroll.
        if val_f1 > best["f1"] + t.min_delta or best["state"] is None:
            best = {"f1": val_f1, "state": copy.deepcopy(model.state_dict()), "epoch": epoch}
        elif epoch - best["epoch"] >= t.patience:
            break

    model.load_state_dict(best["state"])
    _, val_pred = evaluate(model, splits["val"], data, t.batch_size, weights)
    _, test_pred = evaluate(model, splits["test"], data, t.batch_size, weights)
    return {
        "name": cfg.name,
        "section": cfg.section,
        "seed": cfg.seed,
        "key": cfg.key(),
        "config": cfg.to_dict(),
        "history": history,
        "best_epoch": best["epoch"],
        "epochs_run": len(history["val_f1"]),
        "n_params": sum(p.numel() for p in params),
        "sec_per_epoch": float(np.mean(epoch_times)),
        "device": str(device),
        "val": all_scores(data.splits["val"].gold, val_pred, cfg.data.scheme, data.label_counts),
        "test": all_scores(data.splits["test"].gold, test_pred, cfg.data.scheme, data.label_counts),
        "val_pred": [" ".join(p) for p in val_pred],
        "test_pred": [" ".join(p) for p in test_pred],
    }
