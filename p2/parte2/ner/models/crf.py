"""Decodificador CRF lineal (Lafferty et al., 2001) sobre les sortides de l'encoder.

Amb softmax cada token es classifica per separat i res impedeix predir seqüències impossibles com una `L-x`
sense `B-x` davant. El CRF afegeix una matriu de transicions entre etiquetes i puntua la seqüència sencera:
l'entrenament maximitza la probabilitat de la seqüència correcta (l'algorisme forward calcula la funció de
partició) i la predicció busca la seqüència de puntuació màxima amb Viterbi (Jurafsky & Martin, cap. 17;
Lample et al., 2016). Amb BILOU hi ha moltes més transicions prohibides que amb BIO, així que és on el
CRF hauria d'aportar més.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from ..data import PAD_LABEL_IDX
from .tagger import register_decoder

NEG_INF = -1e4


@register_decoder("crf")
class CRFDecoder(nn.Module):
    """Capa lineal d'emissions i transicions apreses, amb puntuacions d'inici i final de seqüència."""

    def __init__(self, input_dim: int, num_classes: int):
        super().__init__()
        self.fc = nn.Linear(input_dim, num_classes)
        self.transitions = nn.Parameter(torch.zeros(num_classes, num_classes))  # [anterior, actual]
        self.start = nn.Parameter(torch.zeros(num_classes))
        self.end = nn.Parameter(torch.zeros(num_classes))

    def _emissions(self, features: torch.Tensor, exclude_pad: bool) -> torch.Tensor:
        emissions = self.fc(features)
        if exclude_pad:
            # En predir, la classe de padding no és una etiqueta real i es descarta de qualsevol camí.
            emissions[..., PAD_LABEL_IDX] = NEG_INF
        return emissions

    def _gold_score(self, emissions: torch.Tensor, tags: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Puntuació no normalitzada de la seqüència d'etiquetes correcta de cada oració."""
        batch = torch.arange(tags.size(0), device=tags.device)
        score = self.start[tags[:, 0]] + emissions[batch, 0, tags[:, 0]]
        for t in range(1, tags.size(1)):
            step = self.transitions[tags[:, t - 1], tags[:, t]] + emissions[batch, t, tags[:, t]]
            score = score + step * mask[:, t]
        last = tags[batch, mask.sum(dim=1) - 1]
        return score + self.end[last]

    def _log_partition(self, emissions: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Algorisme forward: log de la suma de puntuacions de totes les seqüències possibles."""
        alpha = self.start + emissions[:, 0]                                   # (B, C)
        for t in range(1, emissions.size(1)):
            nxt = torch.logsumexp(alpha.unsqueeze(2) + self.transitions + emissions[:, t].unsqueeze(1), dim=1)
            # A les posicions de padding l'estat no avança, així cada oració acaba a la seva longitud real.
            alpha = torch.where(mask[:, t].unsqueeze(1), nxt, alpha)
        return torch.logsumexp(alpha + self.end, dim=1)

    def loss(self, features: torch.Tensor, labels: torch.Tensor, mask: torch.Tensor,
             class_weights: torch.Tensor | None = None) -> torch.Tensor:
        """Log-versemblança negativa de la seqüència correcta, dividida pel nombre de tokens.

        Dividir per tokens i no per oracions deixa la loss en la mateixa escala que la cross-entropy del
        softmax, de manera que el learning rate i el gradient clipping del baseline continuen sent adequats.
        """
        if class_weights is not None:
            raise ValueError("El CRF no admet pesos de classe: la loss és sobre seqüències, no sobre tokens")
        # A la loss no s'exclou la classe de padding: a validació les etiquetes no vistes a train hi estan
        # codificades, i excloure-la donaria a aquelles oracions una loss enorme que desfiguraria les corbes.
        emissions = self._emissions(features, exclude_pad=False)
        nll = self._log_partition(emissions, mask) - self._gold_score(emissions, labels, mask)
        return nll.sum() / mask.sum()

    def decode(self, features: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        """Viterbi: seqüència d'etiquetes de màxima puntuació per a cada oració."""
        emissions = self._emissions(features, exclude_pad=True)
        score = self.start + emissions[:, 0]
        backpointers = []
        for t in range(1, emissions.size(1)):
            best, idx = (score.unsqueeze(2) + self.transitions).max(dim=1)
            backpointers.append(idx)
            score = torch.where(mask[:, t].unsqueeze(1), best + emissions[:, t], score)
        # El recorregut enrere és seqüencial i amb índexs escalars: es fa a CPU per no sincronitzar la GPU a cada pas.
        last = (score + self.end).argmax(dim=1).cpu().tolist()
        pointers = torch.stack(backpointers).cpu().numpy() if backpointers else None
        lengths = mask.sum(dim=1).cpu().tolist()
        paths = torch.zeros(mask.shape, dtype=torch.long)
        for b, (length, tag) in enumerate(zip(lengths, last)):
            paths[b, length - 1] = tag
            for t in range(length - 1, 0, -1):
                tag = int(pointers[t - 1, b, tag])
                paths[b, t - 1] = tag
        return paths.to(mask.device)
