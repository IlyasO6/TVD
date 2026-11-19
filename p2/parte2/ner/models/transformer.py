"""Bloc Transformer encoder (Vaswani et al., 2017) per a l'apartat 7.4.

L'autoatenció no té cap noció d'ordre, així que la posició s'ha d'afegir explícitament: amb una codificació
sinusoidal fixa, amb embeddings de posició apresos, o gens (útil com a control, o quan el bloc va després
d'una BiLSTM que ja codifica l'ordre). La màscara de padding impedeix que els tokens reals atenguin a
posicions de farciment. Fem servir la variant pre-LN (normalització abans de cada subcapa), que és més
estable quan s'entrena des de zero i depèn menys del warmup que la post-LN original (Xiong et al., 2020).
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

from .tagger import register_block


class SinusoidalPositions(nn.Module):
    """Codificació posicional fixa de l'article original; no afegeix paràmetres."""

    def __init__(self, d_model: int, max_len: int):
        super().__init__()
        position = torch.arange(max_len).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div)
        pe[:, 1::2] = torch.cos(position * div[: d_model // 2])
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[: x.size(1)]


class LearnedPositions(nn.Module):
    """Un vector après per posició; més flexible però s'ha d'aprendre amb les poques oracions disponibles."""

    def __init__(self, d_model: int, max_len: int):
        super().__init__()
        self.pe = nn.Embedding(max_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe(torch.arange(x.size(1), device=x.device))


@register_block("transformer")
class TransformerBlock(nn.Module):
    """Projecció opcional a d_model, posició i una pila de capes TransformerEncoder amb màscara de padding."""

    def __init__(self, input_dim: int, d_model: int = 128, nhead: int = 4, num_layers: int = 2,
                 dim_feedforward: int = 256, positional: str = "sinusoidal", dropout: float = 0.0,
                 max_len: int = 128):
        super().__init__()
        self.proj = nn.Linear(input_dim, d_model) if input_dim != d_model else nn.Identity()
        self.positions = {
            "sinusoidal": lambda: SinusoidalPositions(d_model, max_len),
            "learned": lambda: LearnedPositions(d_model, max_len),
            "none": nn.Identity,
        }[positional]()
        layer = nn.TransformerEncoderLayer(d_model, nhead, dim_feedforward, dropout=dropout,
                                           batch_first=True, norm_first=True)
        # Amb pre-LN cal una normalització final; el camí ràpid de tensors niats no és compatible amb norm_first.
        self.encoder = nn.TransformerEncoder(layer, num_layers, norm=nn.LayerNorm(d_model), enable_nested_tensor=False)
        self.output_dim = d_model

    def forward(self, x: torch.Tensor, mask: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        h = self.positions(self.proj(x))
        h = self.encoder(h, src_key_padding_mask=~mask)
        return h * mask.unsqueeze(-1)
