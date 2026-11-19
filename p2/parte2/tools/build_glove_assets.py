"""Extreu de GloVe només els vectors de les paraules que apareixen a ATIS i els desa a ner/assets/.

Els fitxers de GloVe (glove-wiki-gigaword, 6B tokens, 400k paraules) ocupen uns 800 MB; per a l'experiment
només calen les ~900 paraules del corpus, així que els fitxers resultants pesen pocs MB i viatgen dins del
zip. Restringir-se a les paraules del corpus no canvia cap predicció respecte a fer servir GloVe sencer,
ja que una paraula que no apareix mai al corpus mai no es consulta. S'executa un sol cop en local:
`python tools/build_glove_assets.py <carpeta amb glove-{50,100,200,300}.gz>`.
"""

from __future__ import annotations

import gzip
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ner.data import find_data_dir, load_split  # noqa: E402
from ner.models.embeddings import ASSETS_DIR, GLOVE_DIMS  # noqa: E402


def corpus_words() -> set[str]:
    """Totes les paraules de train, validació i test (només el text, mai les etiquetes)."""
    data_dir = find_data_dir()
    words = set()
    for name in ("train.csv", "test.csv"):
        for sentence in load_split(data_dir / name)["sentence"]:
            words.update(sentence.split())
    return words


def extract(path: Path, words: set[str]) -> tuple[list[str], np.ndarray]:
    """Llegeix el format word2vec en text (capçalera amb mida i dimensió) i es queda amb `words`."""
    found, vectors = [], []
    with gzip.open(path, "rt", encoding="utf-8") as f:
        next(f)
        for line in f:
            word, rest = line.split(" ", 1)
            if word in words:
                found.append(word)
                vectors.append(np.array(rest.split(), dtype=np.float32))
    return found, np.stack(vectors)


def main(source_dir: Path) -> None:
    words = corpus_words()
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for dim in GLOVE_DIMS:
        found, vectors = extract(source_dir / f"glove-{dim}.gz", words)
        np.savez_compressed(ASSETS_DIR / f"glove-{dim}.npz", words=np.array(found), vectors=vectors)
        print(f"glove-{dim}: {len(found)}/{len(words)} paraules del corpus amb vector")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
