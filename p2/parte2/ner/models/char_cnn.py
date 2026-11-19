"""Representació de paraula a partir dels caràcters amb CNN i max-pooling (Ma & Hovy, 2016).

És el lloc natural del pooling en NER: la convolució detecta n-grames de caràcters (sufixos, dígits,
apòstrofs) i el max-pooling sobre els caràcters de cada paraula en treu un vector de mida fixa,
independent de la longitud de la paraula. Com que es construeix des dels caràcters, també dona una
representació útil a paraules que no són al vocabulari, com números de vol o hores que no surten a train.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from ..data import PAD_IDX
from .tagger import register_char_encoder

NEG_INF = -1e4


@register_char_encoder("char_cnn")
class CharCNN(nn.Module):
    """Embedding de caràcters → Conv1d → max-pooling sobre la paraula; retorna (B, L, filters)."""

    def __init__(self, n_chars: int, char_dim: int = 30, filters: int = 30, kernel_size: int = 3):
        super().__init__()
        self.embedding = nn.Embedding(n_chars, char_dim, padding_idx=PAD_IDX)
        self.conv = nn.Conv1d(char_dim, filters, kernel_size, padding=kernel_size // 2)
        self.output_dim = filters

    def forward(self, chars: torch.Tensor) -> torch.Tensor:
        batch, seq_len, word_len = chars.shape
        flat = chars.reshape(batch * seq_len, word_len)
        char_mask = (flat != PAD_IDX).unsqueeze(1)                     # (B·L, 1, W)
        h = self.conv(self.embedding(flat).transpose(1, 2))           # (B·L, F, W)
        h = h.masked_fill(~char_mask, NEG_INF).max(dim=2).values      # max només sobre caràcters reals
        # Les posicions de padding de l'oració no tenen cap caràcter: el seu vector es deixa a zero.
        h = h * char_mask.any(dim=2).float()
        return h.reshape(batch, seq_len, -1)
