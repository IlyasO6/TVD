"""Bloc recurrent (LSTM o GRU), el mateix de l'Exercici 6."""

from __future__ import annotations

import torch
import torch.nn as nn

from .tagger import register_block


@register_block("rnn")
class RNNBlock(nn.Module):
    """RNN (bi)direccional sobre seqüències empaquetades perquè el padding no contamini l'estat."""

    def __init__(self, input_dim: int, rnn_type: str = "lstm", hidden_dim: int = 128, num_layers: int = 1,
                 bidirectional: bool = True, dropout: float = 0.0):
        super().__init__()
        rnn_cls = {"lstm": nn.LSTM, "gru": nn.GRU}[rnn_type]
        # El dropout intern de PyTorch només s'aplica entre capes, per això amb una sola capa no té efecte.
        self.rnn = rnn_cls(input_dim, hidden_dim, num_layers=num_layers, batch_first=True,
                           bidirectional=bidirectional, dropout=dropout if num_layers > 1 else 0.0)
        self.output_dim = hidden_dim * (2 if bidirectional else 1)

    def forward(self, x: torch.Tensor, mask: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = nn.utils.rnn.pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        out, _ = self.rnn(packed)
        out, _ = nn.utils.rnn.pad_packed_sequence(out, batch_first=True, total_length=x.size(1))
        return out
