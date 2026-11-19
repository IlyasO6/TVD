"""Embeddings preentrenats GloVe (Pennington et al., 2014) per a l'apartat 7.1.

Els vectors venen de `ner/assets/glove-{dim}.npz`, generats un sol cop amb `tools/build_glove_assets.py`,
així el notebook no ha de descarregar res. Les paraules del vocabulari sense vector a GloVe s'inicialitzen
aleatòriament amb la mateixa escala que els vectors de GloVe, perquè no quedin desproporcionades.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

from ..data import PAD_IDX
from .tagger import register_pretrained

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
GLOVE_DIMS = (50, 100, 200, 300)


@lru_cache(maxsize=None)
def load_glove(dim: int) -> dict[str, np.ndarray]:
    """Diccionari paraula → vector per a la dimensió demanada."""
    path = ASSETS_DIR / f"glove-{dim}.npz"
    if not path.exists():
        raise FileNotFoundError(f"Falta {path}; genera'l amb tools/build_glove_assets.py")
    data = np.load(path)
    return dict(zip(data["words"].tolist(), data["vectors"]))


def glove_matrix(word2idx: dict[str, int], dim: int, seed: int = 0) -> np.ndarray:
    """Matriu d'embedding alineada amb el vocabulari; el padding queda a zero."""
    glove = load_glove(dim)
    scale = np.std(np.stack(list(glove.values())))
    rng = np.random.default_rng(seed)
    matrix = rng.normal(0.0, scale, size=(len(word2idx), dim)).astype(np.float32)
    for word, idx in word2idx.items():
        if word in glove:
            matrix[idx] = glove[word]
    matrix[PAD_IDX] = 0.0
    return matrix


def coverage(word2idx: dict[str, int], dim: int = 100) -> float:
    """Proporció del vocabulari (sense <pad> ni <unk>) que té vector a GloVe."""
    glove = load_glove(dim)
    words = [w for w, i in word2idx.items() if i > 1]
    return sum(w in glove for w in words) / len(words)


for _dim in GLOVE_DIMS:
    register_pretrained(
        f"glove-{_dim}",
        vocab_fn=lambda d=_dim: frozenset(load_glove(d)),
        vectors_fn=lambda word2idx, d=_dim: glove_matrix(word2idx, d),
    )
