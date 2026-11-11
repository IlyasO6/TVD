# %% [markdown] [Cel·la nova abans del codi de l'Exercici 3]
# Les oracions ja venen en minúscules i tokenitzades, i cada paraula separada per espais té exactament una
# etiqueta. Per això tokenitzem amb un simple `split()`: qualsevol tokenitzador més elaborat (separar `'s`,
# signes, etc.) trencaria l'alineació amb les etiquetes. El vocabulari es construeix només amb train, per
# no filtrar informació de validació ni de test. Les paraules que surten un sol cop a train les enviem a
# `<unk>` (`MIN_FREQ = 2`); si totes entressin al vocabulari, l'embedding de `<unk>` no s'entrenaria mai i
# a test les paraules desconegudes rebrien un vector aleatori. Així el model aprèn una representació útil
# per a paraules rares, que a ATIS solen ser números de vol, hores o noms propis poc freqüents.

# %% [Cel·la 22: Exercici 3]
def tokenize(sentence: str) -> list[str]:
    """Separa per espais per mantenir l'alineació 1 a 1 amb les etiquetes del dataset."""
    return sentence.split()


def build_vocab(sentences: list[str], min_freq: int = MIN_FREQ) -> dict[str, int]:
    """Crea el diccionari paraula→índex amb les paraules de train prou freqüents, ordenades per freqüència."""
    counts = Counter(word for s in sentences for word in tokenize(s))
    word2idx = {PAD_TOKEN: 0, UNK_TOKEN: 1}
    for word, count in counts.most_common():
        if count >= min_freq:
            word2idx[word] = len(word2idx)
    return word2idx


def encode_sentences(sentences: list[str], word2idx: dict[str, int]) -> list[list[int]]:
    """Passa cada oració a la seqüència d'índexs, fent servir <unk> per a les paraules fora del vocabulari."""
    unk_idx = word2idx[UNK_TOKEN]
    return [[word2idx.get(word, unk_idx) for word in tokenize(s)] for s in sentences]


def pad_sequences(sequences: list[list[int]], max_len: int, pad_value: int = 0) -> np.ndarray:
    """Afegeix padding al final (o trunca) perquè totes les seqüències tinguin longitud max_len."""
    padded = np.full((len(sequences), max_len), pad_value, dtype=np.int64)
    for i, seq in enumerate(sequences):
        trunc = seq[:max_len]
        padded[i, :len(trunc)] = trunc
    return padded


word2idx = build_vocab(train_sentences)
idx2word = {i: w for w, i in word2idx.items()}
max_sequence_length = max(len(tokenize(s)) for s in train_sentences)

train_sequences = encode_sentences(train_sentences, word2idx)
val_sequences = encode_sentences(val_sentences, word2idx)
test_sequences = encode_sentences(test_sentences, word2idx)

# Les longituds reals permeten ignorar el padding tant a l'LSTM (empaquetant) com a l'avaluació.
len_train_sequences = np.array([len(s) for s in train_sequences])
len_val_sequences = np.array([len(s) for s in val_sequences])
len_test_sequences = np.array([len(s) for s in test_sequences])

train_pad_sequences = pad_sequences(train_sequences, max_sequence_length)
val_pad_sequences = pad_sequences(val_sequences, max_sequence_length)
test_pad_sequences = pad_sequences(test_sequences, max_sequence_length)

print("Vocabulary size:", len(word2idx))
print("Max sequence length:", max_sequence_length)
for name, seqs in [("train", train_sequences), ("val", val_sequences), ("test", test_sequences)]:
    flat = [idx for s in seqs for idx in s]
    print(f"Tokens <unk> a {name}: {flat.count(word2idx[UNK_TOKEN]) / len(flat):.2%}")
