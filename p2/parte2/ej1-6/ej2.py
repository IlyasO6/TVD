# %% [markdown] [Cel·la nova abans del codi de l'Exercici 2]
# Tot i que l'enunciat parla de BILOU, el CSV només conté prefixos `B-`, `I-` i `O` (esquema BIO). Per
# seguir l'enunciat convertim les etiquetes a BILOU: una `B` que no continua passa a ser `U` i l'última `I`
# d'una entitat passa a ser `L`. La conversió no perd informació (es pot desfer) i dona al model senyal
# explícit de quan acaba una entitat, cosa que amb BIO només pot deduir mirant el token següent. Deixem
# l'esquema com a paràmetre (`LABEL_SCHEME`) per poder comparar BIO i BILOU a l'Exercici 7. Per això
# les sortides de les cel·les següents mostren `U-` i `L-` en lloc del `B-`/`I-` dels exemples de l'enunciat.

# %% [Cel·la 11: Exercici 2]
def bio_to_bilou(tags: list[str]) -> list[str]:
    """Converteix una seqüència BIO ben formada a BILOU mirant si el token següent continua l'entitat."""
    bilou = []
    for i, tag in enumerate(tags):
        if tag == "O":
            bilou.append(tag)
            continue
        prefix, entity = tag.split("-", maxsplit=1)
        next_tag = tags[i + 1] if i + 1 < len(tags) else "O"
        continues = next_tag == f"I-{entity}"
        if prefix == "B":
            bilou.append(f"{'B' if continues else 'U'}-{entity}")
        else:
            bilou.append(f"{'I' if continues else 'L'}-{entity}")
    return bilou


def get_labels(df: pd.DataFrame, scheme: str = LABEL_SCHEME) -> list[str]:
    """Retorna les etiquetes de cada oració com a string separat per espais, en l'esquema demanat."""
    if scheme == "BIO":
        return df["labels"].tolist()
    return [" ".join(bio_to_bilou(labels.split())) for labels in df["labels"]]


train_sentences, train_labels = train_data["sentence"].tolist(), get_labels(train_data)
val_sentences, val_labels = val_data["sentence"].tolist(), get_labels(val_data)
test_sentences, test_labels = test_data["sentence"].tolist(), get_labels(test_data)

# %% [Cel·la nova després de la cel·la 18: anàlisi addicional del dataset]
# Aquestes xifres justifiquen decisions posteriors: la longitud màxima fixa el padding, el desbalanceig
# motiva l'apartat de pesos de classe i les etiquetes no vistes expliquen errors inevitables al test.
sentence_lengths = pd.Series([len(s.split()) for s in train_sentences])
print("Longitud de les oracions de train:")
print(sentence_lengths.describe().round(2).to_string(), "\n")

label_counts = Counter(tag for labels in train_labels for tag in labels.split())
total_tags = sum(label_counts.values())
print(f"Proporció de tokens 'O': {label_counts['O'] / total_tags:.1%}")
print("Etiquetes més freqüents (sense 'O'):", [l for l, _ in label_counts.most_common(6)[1:]])
print("Etiquetes que surten un sol cop a train:", sum(c == 1 for c in label_counts.values()), "\n")

for name, labels in [("validació", val_labels), ("test", test_labels)]:
    unseen = Counter(t for ls in labels for t in ls.split() if t not in label_counts)
    print(f"Etiquetes de {name} que no apareixen a train ({sum(unseen.values())} tokens):", sorted(unseen))
