"""Model d'etiquetatge compost per blocs: embedding → blocs d'encoder → decodificador.

Cada variant de l'Exercici 7 (CNN, Transformer, CRF, char-CNN...) es registra en un dels registres
d'aquest mòdul amb un nom, i la configuració només ha d'indicar aquests noms i els seus paràmetres. Així
totes les variants comparteixen el mateix embedding, el mateix bucle d'entrenament i la mateixa avaluació,
i les diferències entre resultats només poden venir del bloc que canvia.

Contracte dels blocs d'encoder: `__init__(input_dim, **params)`, atribut `output_dim` i
`forward(x, mask, lengths)`, on `x` és (B, L, D), `mask` és (B, L) amb True a les posicions reals i
`lengths` són les longituds reals a CPU. Els encoders de caràcters reben `(n_chars, **params)` i
`forward(chars)` amb `chars` de forma (B, L, W). Els decodificadors exposen `loss` i `decode`.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from ..config import ModelConfig
from ..data import PAD_IDX, PAD_LABEL_IDX

BLOCKS: dict[str, type[nn.Module]] = {}
CHAR_ENCODERS: dict[str, type[nn.Module]] = {}
DECODERS: dict[str, type[nn.Module]] = {}
# nom → (funció que retorna les paraules amb vector, funció que retorna la matriu alineada amb word2idx)
PRETRAINED: dict[str, tuple[Callable[[], frozenset[str]], Callable[[dict[str, int]], np.ndarray]]] = {}


def _register(registry: dict, name: str) -> Callable[[type], type]:
    def decorator(cls: type) -> type:
        if name in registry:
            raise ValueError(f"'{name}' ja està registrat")
        registry[name] = cls
        return cls
    return decorator


def register_block(name: str) -> Callable[[type], type]:
    return _register(BLOCKS, name)


def register_char_encoder(name: str) -> Callable[[type], type]:
    return _register(CHAR_ENCODERS, name)


def register_decoder(name: str) -> Callable[[type], type]:
    return _register(DECODERS, name)


def register_pretrained(name: str, vocab_fn: Callable[[], frozenset[str]],
                        vectors_fn: Callable[[dict[str, int]], np.ndarray]) -> None:
    PRETRAINED[name] = (vocab_fn, vectors_fn)


@register_decoder("softmax")
class SoftmaxDecoder(nn.Module):
    """Classificació independent de cada token amb una capa lineal i cross-entropy."""

    def __init__(self, input_dim: int, num_classes: int):
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)

    def loss(self, features: torch.Tensor, labels: torch.Tensor, mask: torch.Tensor,
             class_weights: torch.Tensor | None = None) -> torch.Tensor:
        logits = self.fc(features)
        # El padding i les etiquetes no vistes a train comparteixen l'índex ignorat, així que no aporten gradient.
        return F.cross_entropy(logits.reshape(-1, logits.size(-1)), labels.reshape(-1),
                               weight=class_weights, ignore_index=PAD_LABEL_IDX)

    def decode(self, features: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        logits = self.fc(features)
        logits[..., PAD_LABEL_IDX] = float("-inf")  # la classe de padding mai és una predicció vàlida
        return logits.argmax(dim=-1)


class NERTagger(nn.Module):
    """Etiquetador genèric definit per una ModelConfig."""

    def __init__(self, cfg: ModelConfig, vocab_size: int, num_classes: int, n_chars: int,
                 pretrained_vectors: np.ndarray | None = None):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, cfg.embedding_dim, padding_idx=PAD_IDX)
        if pretrained_vectors is not None:
            assert pretrained_vectors.shape == (vocab_size, cfg.embedding_dim), "Vectors preentrenats mal alineats"
            self.embedding.weight.data.copy_(torch.as_tensor(pretrained_vectors))
            self.embedding.weight.requires_grad = not cfg.freeze_embeddings
        input_dim = cfg.embedding_dim

        self.char_encoder = None
        if cfg.char_encoder is not None:
            self.char_encoder = CHAR_ENCODERS[cfg.char_encoder.kind](n_chars, **cfg.char_encoder.params)
            input_dim += self.char_encoder.output_dim
        self.embedding_dropout = nn.Dropout(cfg.embedding_dropout)

        self.blocks = nn.ModuleList()
        for block_cfg in cfg.blocks:
            block = BLOCKS[block_cfg.kind](input_dim, **block_cfg.params)
            self.blocks.append(block)
            input_dim = block.output_dim

        self.classifier_dropout = nn.Dropout(cfg.classifier_dropout)
        self.decoder = DECODERS[cfg.decoder](input_dim, num_classes)

    def features(self, words: torch.Tensor, lengths: torch.Tensor, chars: torch.Tensor | None = None
                 ) -> tuple[torch.Tensor, torch.Tensor]:
        """Representació contextual de cada token, abans del decodificador, i la màscara de posicions reals."""
        mask = torch.arange(words.size(1), device=words.device)[None, :] < lengths.to(words.device)[:, None]
        x = self.embedding(words)
        if self.char_encoder is not None:
            x = torch.cat([x, self.char_encoder(chars)], dim=-1)
        x = self.embedding_dropout(x)
        for block in self.blocks:
            x = block(x, mask, lengths)
        return self.classifier_dropout(x), mask

    def loss(self, words: torch.Tensor, labels: torch.Tensor, lengths: torch.Tensor,
             chars: torch.Tensor | None = None, class_weights: torch.Tensor | None = None) -> torch.Tensor:
        feats, mask = self.features(words, lengths, chars)
        return self.decoder.loss(feats, labels, mask, class_weights)

    @torch.no_grad()
    def predict(self, words: torch.Tensor, lengths: torch.Tensor, chars: torch.Tensor | None = None) -> torch.Tensor:
        feats, mask = self.features(words, lengths, chars)
        return self.decoder.decode(feats, mask)
