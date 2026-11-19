"""Càrrega i preprocessament d'ATIS per a l'Exercici 7.

Repeteix el preprocessament dels exercicis 1-4 del notebook perquè el paquet sigui independent de l'estat
del notebook i pugui variar l'esquema d'etiquetes o el MIN_FREQ per experiment.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from .config import DataConfig

PAD_TOKEN, UNK_TOKEN = "<pad>", "<unk>"
PAD_IDX, UNK_IDX = 0, 1
PAD_LABEL = "<pad>"
PAD_LABEL_IDX = 0
COLUMNS = ["sentence", "labels", "intent"]
PACKAGE_ROOT = Path(__file__).resolve().parent


def find_data_dir() -> Path:
    """Busca la carpeta data/ a NER_DATA_DIR, al directori actual o al costat del paquet (local i Colab)."""
    candidates = [os.environ.get("NER_DATA_DIR"), Path.cwd() / "data", PACKAGE_ROOT.parent / "data"]
    for candidate in candidates:
        if candidate and (Path(candidate) / "train.csv").exists():
            return Path(candidate)
    raise FileNotFoundError("No trobo data/train.csv; defineix NER_DATA_DIR o executa la cel·la de descàrrega.")


def load_split(path: Path) -> pd.DataFrame:
    """Llegeix un CSV d'ATIS; skipinitialspace evita que les cometes quedin dins dels camps."""
    df = pd.read_csv(path, header=None, names=COLUMNS, skipinitialspace=True)
    df = df.apply(lambda col: col.str.strip())
    misaligned = df["sentence"].str.split().str.len() != df["labels"].str.split().str.len()
    assert not misaligned.any(), "Hi ha oracions amb diferent nombre de paraules i etiquetes"
    return df


def bio_to_bilou(tags: list[str]) -> list[str]:
    """Converteix una seqüència BIO ben formada a BILOU mirant si el token següent continua l'entitat."""
    bilou = []
    for i, tag in enumerate(tags):
        if tag == "O":
            bilou.append(tag)
            continue
        prefix, entity = tag.split("-", maxsplit=1)
        next_tag = tags[i + 1] if i + 1 < len(tags) else "O"
        continues = next_tag == f"I-{entity}"
        if prefix == "B":
            bilou.append(f"{'B' if continues else 'U'}-{entity}")
        else:
            bilou.append(f"{'I' if continues else 'L'}-{entity}")
    return bilou


@dataclass
class Split:
    """Una partició ja codificada; `gold` conserva les etiquetes en text per avaluar sense amagar res."""

    sentences: list[list[str]]
    gold: list[list[str]]
    words: torch.Tensor          # (N, L) índexs de paraula amb padding
    labels: torch.Tensor         # (N, L) índexs d'etiqueta; padding i etiquetes no vistes = PAD_LABEL_IDX
    lengths: torch.Tensor        # (N,) longituds reals
    chars: torch.Tensor | None   # (N, L, W) índexs de caràcter, només si algun model els necessita


@dataclass
class PreparedData:
    word2idx: dict[str, int]
    label2idx: dict[str, int]
    idx2label: dict[int, str]
    char2idx: dict[str, int]
    label_counts: Counter        # freqüència de cada etiqueta a train, per als pesos de classe i l'anàlisi
    splits: dict[str, Split]

    @property
    def num_classes(self) -> int:
        return len(self.label2idx)


def build_vocab(sentences: list[list[str]], min_freq: int, extra_words: frozenset[str] = frozenset()) -> dict[str, int]:
    """Vocabulari de train ordenat per freqüència, ampliat amb `extra_words` (paraules amb vector preentrenat).

    Les paraules preentrenades hi entren encara que siguin rares o no surtin a train: el seu vector ja aporta
    significat sense haver-lo d'aprendre, que és justament el que pot ajudar amb les paraules no vistes.
    """
    counts = Counter(w for s in sentences for w in s)
    word2idx = {PAD_TOKEN: PAD_IDX, UNK_TOKEN: UNK_IDX}
    for word, count in counts.most_common():
        if count >= min_freq or word in extra_words:
            word2idx[word] = len(word2idx)
    for word in sorted(extra_words - word2idx.keys()):
        word2idx[word] = len(word2idx)
    return word2idx


def _pad(rows: list[list[int]], max_len: int) -> torch.Tensor:
    out = np.zeros((len(rows), max_len), dtype=np.int64)
    for i, row in enumerate(rows):
        out[i, :min(len(row), max_len)] = row[:max_len]
    return torch.from_numpy(out)


def _encode_chars(sentences: list[list[str]], char2idx: dict[str, int], max_len: int, max_word: int) -> torch.Tensor:
    out = np.zeros((len(sentences), max_len, max_word), dtype=np.int64)
    for i, sent in enumerate(sentences):
        for j, word in enumerate(sent[:max_len]):
            ids = [char2idx.get(c, UNK_IDX) for c in word[:max_word]]
            out[i, j, :len(ids)] = ids
    return torch.from_numpy(out)


@lru_cache(maxsize=8)
def _prepare_cached(config_json: str, with_chars: bool, extra_words: frozenset[str]) -> PreparedData:
    cfg = DataConfig(**json.loads(config_json))
    data_dir = find_data_dir()
    full_train = load_split(data_dir / "train.csv")
    frames = {
        "train": full_train.iloc[:-cfg.val_size],
        "val": full_train.iloc[-cfg.val_size:],
        "test": load_split(data_dir / "test.csv"),
    }
    sentences = {k: [s.split() for s in df["sentence"]] for k, df in frames.items()}
    gold = {k: [t.split() for t in df["labels"]] for k, df in frames.items()}
    if cfg.scheme == "BILOU":
        gold = {k: [bio_to_bilou(t) for t in tags] for k, tags in gold.items()}
    elif cfg.scheme != "BIO":
        raise ValueError(f"Esquema desconegut: {cfg.scheme}")

    word2idx = build_vocab(sentences["train"], cfg.min_freq, extra_words)
    label_counts = Counter(t for tags in gold["train"] for t in tags)
    label2idx = {PAD_LABEL: PAD_LABEL_IDX}
    for tag in label_counts:
        label2idx.setdefault(tag, len(label2idx))
    # Els caràcters es construeixen igual que el vocabulari: només amb train, i 0/1 per a padding i desconeguts.
    chars = sorted({c for s in sentences["train"] for w in s for c in w})
    char2idx = {PAD_TOKEN: PAD_IDX, UNK_TOKEN: UNK_IDX, **{c: i + 2 for i, c in enumerate(chars)}}

    max_len = max(len(s) for s in sentences["train"])
    max_word = max(len(w) for s in sentences["train"] for w in s)
    splits = {}
    for k in frames:
        splits[k] = Split(
            sentences=sentences[k],
            gold=gold[k],
            words=_pad([[word2idx.get(w, UNK_IDX) for w in s] for s in sentences[k]], max_len),
            labels=_pad([[label2idx.get(t, PAD_LABEL_IDX) for t in tags] for tags in gold[k]], max_len),
            lengths=torch.tensor([min(len(s), max_len) for s in sentences[k]]),
            chars=_encode_chars(sentences[k], char2idx, max_len, max_word) if with_chars else None,
        )
    return PreparedData(word2idx, label2idx, {i: l for l, i in label2idx.items()}, char2idx, label_counts, splits)


def prepare_data(cfg: DataConfig, with_chars: bool = False, extra_words: frozenset[str] = frozenset()) -> PreparedData:
    """Prepara les tres particions; es memoritza perquè una graella no repeteixi el preprocessament."""
    return _prepare_cached(json.dumps(asdict(cfg), sort_keys=True), with_chars, extra_words)
