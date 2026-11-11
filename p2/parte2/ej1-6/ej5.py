# %% [markdown] [Cel·la nova abans del codi de l'Exercici 5]
# El model segueix l'estructura que demana l'enunciat: embedding, una LSTM bidireccional i una capa lineal
# que classifica cada token. La bidireccionalitat és important en NER perquè el tipus d'una entitat sovint
# depèn del context de la dreta i de l'esquerra (a "from boston" és la preposició anterior la que decideix
# `fromloc`). Abans de la LSTM empaquetem les seqüències amb les seves longituds reals: sense fer-ho, la
# direcció cap enrere començaria llegint desenes de tokens de padding i el seu estat inicial per a l'última
# paraula real estaria contaminat. Aquest model és la base; les variants (CNN, Transformer, dropout...)
# es fan a l'Exercici 7.

# %% [Cel·la 29: Exercici 5]
class NERModel(nn.Module):
    """Etiquetador de seqüències: embedding → RNN (bi)direccional → capa lineal per token."""

    def __init__(self, vocab_size: int, embedding_dim: int, hidden_dim: int, num_classes: int,
                 num_layers: int = 1, bidirectional: bool = True, rnn_type: str = "lstm"):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        rnn_cls = nn.LSTM if rnn_type == "lstm" else nn.GRU
        self.rnn = rnn_cls(embedding_dim, hidden_dim, num_layers=num_layers,
                           batch_first=True, bidirectional=bidirectional)
        self.fc = nn.Linear(hidden_dim * (2 if bidirectional else 1), num_classes)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """Retorna logits de forma (batch, seq_len, num_classes); les posicions de padding queden a zero."""
        embeds = self.embedding(x)
        # pack_padded_sequence demana les longituds a CPU; total_length recupera la mida original del batch.
        packed = nn.utils.rnn.pack_padded_sequence(embeds, lengths.cpu(), batch_first=True,
                                                   enforce_sorted=False)
        rnn_out, _ = self.rnn(packed)
        rnn_out, _ = nn.utils.rnn.pad_packed_sequence(rnn_out, batch_first=True, total_length=x.size(1))
        return self.fc(rnn_out)


MODEL_CONFIG = {
    "embedding_dim": 128,
    "hidden_dim": 128,
    "num_layers": 1,
    "bidirectional": True,
    "rnn_type": "lstm",
}

set_seed()
model = NERModel(vocab_size=len(word2idx), num_classes=num_classes, **MODEL_CONFIG).to(device)
print(model)
print("Paràmetres entrenables:", sum(p.numel() for p in model.parameters() if p.requires_grad))
