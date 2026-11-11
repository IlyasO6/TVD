# %% [markdown] [Cel·la nova abans del codi de l'Exercici 4]
# Cada etiqueta BILOU (`B-x`, `I-x`, `L-x`, `U-x` i `O`) és una classe independent. El padding té un índex
# propi (0) que la loss ignora, de manera que les posicions de farciment no aporten gradient ni compten a
# les mètriques. Les poques etiquetes de validació i test que no surten mai a train (una quinzena de tokens)
# també es codifiquen amb aquest índex: el model no les pot predir i no té sentit que distorsionin la loss
# de validació. Això no amaga els errors, perquè l'avaluació final es fa comparant amb les etiquetes
# originals en text, i allà aquests tokens compten com a fallades.

# %% [Cel·la 26: Exercici 4]
PAD_LABEL = "<pad>"
PAD_LABEL_IDX = 0


def build_label_vocab(label_sentences: list[str]) -> dict[str, int]:
    """Assigna un índex a cada etiqueta de train, reservant el 0 per al padding."""
    label2idx = {PAD_LABEL: PAD_LABEL_IDX}
    for labels in label_sentences:
        for tag in labels.split():
            label2idx.setdefault(tag, len(label2idx))
    return label2idx


def encode_labels(label_sentences: list[str], label2idx: dict[str, int], max_len: int) -> np.ndarray:
    """Codifica i fa padding de les etiquetes; les no vistes a train van a l'índex ignorat."""
    encoded = [[label2idx.get(tag, PAD_LABEL_IDX) for tag in labels.split()] for labels in label_sentences]
    return pad_sequences(encoded, max_len, pad_value=PAD_LABEL_IDX)


label2idx = build_label_vocab(train_labels)
idx2label = {i: l for l, i in label2idx.items()}
num_classes = len(label2idx)

train_pad_labels = encode_labels(train_labels, label2idx, max_sequence_length)
val_pad_labels = encode_labels(val_labels, label2idx, max_sequence_length)
test_pad_labels = encode_labels(test_labels, label2idx, max_sequence_length)

print("Number of different entities (sense padding):", num_classes - 1)
print("Exemple codificat:", train_pad_labels[0][:len_train_sequences[0]])


class NERDataset(Dataset):
    """Agrupa seqüències, etiquetes i longituds reals; la longitud cal per empaquetar la RNN."""

    def __init__(self, sequences: np.ndarray, labels: np.ndarray, lengths: np.ndarray):
        self.sequences = torch.as_tensor(sequences, dtype=torch.long)
        self.labels = torch.as_tensor(labels, dtype=torch.long)
        self.lengths = torch.as_tensor(lengths, dtype=torch.long)

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        return self.sequences[idx], self.labels[idx], self.lengths[idx]


train_dataset = NERDataset(train_pad_sequences, train_pad_labels, len_train_sequences)
val_dataset = NERDataset(val_pad_sequences, val_pad_labels, len_val_sequences)
test_dataset = NERDataset(test_pad_sequences, test_pad_labels, len_test_sequences)
