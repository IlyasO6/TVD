"""Bloc convolucional a nivell de paraula per a l'apartat 7.2.

Cada capa aplica convolucions 1D sobre la seqüència amb padding `same`, de manera que es manté una sortida
per token (imprescindible en NER). Amb diverses mides de kernel en paral·lel, cada token rep alhora
informació de finestres de 3, 5... paraules, que és la mida típica de les entitats d'ATIS ("san francisco",
"838 am", "first class"). El camp receptiu creix amb la profunditat: L capes de kernel k veuen
L·(k−1)+1 paraules.

Un global pooling clàssic redueix tota l'oració a un sol vector i per tant elimina la resolució per token
que necessita l'etiquetatge. Per això aquí el pooling es fa servir de dues maneres compatibles amb NER: un
max-pooling local amb stride 1 (que suavitza les activacions sense reduir la longitud) i un vector global
de l'oració que es concatena a cada token com a context (si l'oració parla d'arribada o de sortida, etc.).
"""

from __future__ import annotations

import torch
import torch.nn as nn

from .tagger import register_block

NEG_INF = -1e4  # prou negatiu per als max-pooling sense provocar NaN en half precision


@register_block("cnn")
class CNNBlock(nn.Module):
    """Pila de capes Conv1d multi-kernel amb ReLU i pooling opcional (local i/o context global)."""

    def __init__(self, input_dim: int, kernel_sizes: tuple[int, ...] | list[int] = (3,), filters: int = 128,
                 num_layers: int = 1, local_pool: int | None = None, global_context: bool = False):
        super().__init__()
        assert all(k % 2 == 1 for k in kernel_sizes), "Kernels senars perquè el padding 'same' sigui simètric"
        self.layers = nn.ModuleList()
        dim = input_dim
        for _ in range(num_layers):
            self.layers.append(nn.ModuleList(nn.Conv1d(dim, filters, k, padding=k // 2) for k in kernel_sizes))
            dim = filters * len(kernel_sizes)
        self.local_pool = nn.MaxPool1d(local_pool, stride=1, padding=local_pool // 2) if local_pool else None
        self.global_context = global_context
        self.output_dim = dim * (2 if global_context else 1)

    def forward(self, x: torch.Tensor, mask: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        keep = mask.unsqueeze(1)                     # (B, 1, L), per treballar en format canal-primer
        h = x.transpose(1, 2)
        for convs in self.layers:
            # Es torna a posar a zero el padding a cada capa: el biaix i la ReLU el farien no nul i
            # les posicions reals de la vora el veurien a la capa següent com si fos contingut.
            h = torch.relu(torch.cat([conv(h) for conv in convs], dim=1)) * keep
        if self.local_pool is not None:
            h = self.local_pool(h.masked_fill(~keep, NEG_INF)) * keep
        if self.global_context:
            sentence = h.masked_fill(~keep, NEG_INF).max(dim=2, keepdim=True).values
            h = torch.cat([h, sentence.expand_as(h) * keep], dim=1)
        return h.transpose(1, 2)
