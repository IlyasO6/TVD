# %% [markdown] [Cel·la nova abans del codi de l'Exercici 6]
# Entrenem amb Adam i CrossEntropy ignorant l'índex de padding. En lloc de fixar un nombre d'èpoques a cegues,
# a cada època mesurem la F1 d'entitats a validació i ens quedem amb els pesos de la millor (early stopping
# amb paciència). Fem servir la F1 d'entitats com a criteri perquè és la mètrica estàndard en NER
# (conlleval/seqeval): una entitat només compta com a encertada si el tipus i els límits coincideixen
# exactament. L'accuracy per token enganya en aquest dataset, ja que gairebé dos terços dels tokens són `O`
# i un model que només predigués `O` ja tindria un 64% d'accuracy. Per complir l'enunciat també mostrem el
# report token per token, però les conclusions es basen sobretot en la F1 d'entitats.

# %% [Cel·la 31: Exercici 6, funcions d'entrenament i avaluació]
TRAIN_CONFIG = {
    "batch_size": 32,
    "lr": 1e-3,
    "max_epochs": 30,
    "patience": 5,      # èpoques sense millorar la F1 de validació abans d'aturar
    "grad_clip": 1.0,   # evita salts bruscos de gradient, habituals a les RNN
}
SEQEVAL_SCHEME = BILOU if LABEL_SCHEME == "BILOU" else IOB2


def make_loader(dataset: Dataset, shuffle: bool = False) -> DataLoader:
    """Crea un DataLoader amb un generador propi perquè l'ordre de barreja sigui reproduïble."""
    generator = torch.Generator().manual_seed(SEED)
    return DataLoader(dataset, batch_size=TRAIN_CONFIG["batch_size"], shuffle=shuffle, generator=generator)


def run_epoch(model: nn.Module, loader: DataLoader, criterion: nn.Module,
              optimizer: optim.Optimizer | None = None) -> float:
    """Fa una passada pel loader; si hi ha optimitzador entrena, si no només calcula la loss mitjana."""
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    with torch.set_grad_enabled(training):
        for x, y, lengths in loader:
            x, y = x.to(device), y.to(device)
            logits = model(x, lengths)
            loss = criterion(logits.reshape(-1, logits.size(-1)), y.reshape(-1))
            if training:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), TRAIN_CONFIG["grad_clip"])
                optimizer.step()
            total_loss += loss.item()
    return total_loss / len(loader)


@torch.no_grad()
def predict(model: nn.Module, loader: DataLoader) -> list[list[str]]:
    """Retorna les etiquetes predites de cada oració, ja sense el padding."""
    model.eval()
    predictions = []
    for x, _, lengths in loader:
        logits = model(x.to(device), lengths)
        # La classe de padding mai és una resposta vàlida, així que l'excloem de l'argmax.
        logits[..., PAD_LABEL_IDX] = float("-inf")
        preds = logits.argmax(dim=-1).cpu().numpy()
        predictions += [[idx2label[i] for i in p[:n]] for p, n in zip(preds, lengths.tolist())]
    return predictions


def entity_f1(gold: list[list[str]], pred: list[list[str]]) -> float:
    """F1 micro a nivell d'entitat en mode estricte (tipus i límits exactes)."""
    return entity_f1_score(gold, pred, mode="strict", scheme=SEQEVAL_SCHEME)


def train_model(model: nn.Module, train_loader: DataLoader, val_loader: DataLoader,
                val_gold: list[list[str]], criterion: nn.Module, verbose: bool = True) -> dict[str, list[float]]:
    """Entrena amb early stopping sobre la F1 d'entitats de validació i deixa carregats els millors pesos."""
    optimizer = optim.Adam(model.parameters(), lr=TRAIN_CONFIG["lr"])
    history = {"train_loss": [], "val_loss": [], "val_f1": []}
    best_f1, best_state, epochs_without_improvement = -1.0, None, 0
    for epoch in range(1, TRAIN_CONFIG["max_epochs"] + 1):
        train_loss = run_epoch(model, train_loader, criterion, optimizer)
        val_loss = run_epoch(model, val_loader, criterion)
        val_f1 = entity_f1(val_gold, predict(model, val_loader))
        for key, value in zip(history, (train_loss, val_loss, val_f1)):
            history[key].append(value)
        if verbose:
            print(f"Epoch {epoch:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val F1: {val_f1:.4f}")
        if val_f1 > best_f1:
            best_f1, best_state, epochs_without_improvement = val_f1, copy.deepcopy(model.state_dict()), 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= TRAIN_CONFIG["patience"]:
                break
    model.load_state_dict(best_state)
    history["best_epoch"] = int(np.argmax(history["val_f1"])) + 1
    if verbose:
        print(f"Millor època: {history['best_epoch']} (Val F1 = {best_f1:.4f})")
    return history


def token_metrics(gold: list[list[str]], pred: list[list[str]]) -> dict[str, float]:
    """Mètriques per token: accuracy global i F1 macro i ponderada calculades sense la classe 'O'."""
    flat_gold = [t for s in gold for t in s]
    flat_pred = [t for s in pred for t in s]
    entity_tags = sorted(set(flat_gold) - {"O"})
    return {
        "token_acc": accuracy_score(flat_gold, flat_pred),
        "token_f1_macro": f1_score(flat_gold, flat_pred, labels=entity_tags, average="macro", zero_division=0),
        "token_f1_weighted": f1_score(flat_gold, flat_pred, labels=entity_tags, average="weighted", zero_division=0),
    }


# %% [Cel·la nova: Exercici 6, entrenament]
# El gold de validació i test són les etiquetes originals en text, incloses les que el model no pot predir.
val_gold = [labels.split() for labels in val_labels]
test_gold = [labels.split() for labels in test_labels]

train_loader = make_loader(train_dataset, shuffle=True)
val_loader = make_loader(val_dataset)
test_loader = make_loader(test_dataset)

set_seed()
model = NERModel(vocab_size=len(word2idx), num_classes=num_classes, **MODEL_CONFIG).to(device)
criterion = nn.CrossEntropyLoss(ignore_index=PAD_LABEL_IDX)
history = train_model(model, train_loader, val_loader, val_gold, criterion)

# %% [Cel·la nova: Exercici 6, corbes d'aprenentatge]
fig, (ax_loss, ax_f1) = plt.subplots(1, 2, figsize=(11, 3.5))
epochs_range = range(1, len(history["train_loss"]) + 1)
ax_loss.plot(epochs_range, history["train_loss"], label="train")
ax_loss.plot(epochs_range, history["val_loss"], label="validació")
ax_loss.set(xlabel="Època", ylabel="Loss", title="Loss")
ax_loss.legend()
ax_f1.plot(epochs_range, history["val_f1"], color="tab:green")
ax_f1.axvline(history["best_epoch"], linestyle="--", color="grey", label="millor època")
ax_f1.set(xlabel="Època", ylabel="F1 d'entitats", title="F1 d'entitats (validació)")
ax_f1.legend()
plt.tight_layout()
plt.show()

# %% [Cel·la nova: Exercici 6, avaluació a validació i test]
val_pred = predict(model, val_loader)
test_pred = predict(model, test_loader)

summary = pd.DataFrame({
    name: {"entity_f1": entity_f1(gold, pred), **token_metrics(gold, pred)}
    for name, gold, pred in [("validació", val_gold, val_pred), ("test", test_gold, test_pred)]
}).T
print(summary.round(4), "\n")

print("Test: report a nivell d'entitat (seqeval, mode estricte)")
print(entity_report(test_gold, test_pred, mode="strict", scheme=SEQEVAL_SCHEME, zero_division=0))

# %% [Cel·la nova: Exercici 6, report token per token]
# Report que demana l'enunciat. Només inclou les etiquetes presents al gold de test per no omplir la
# taula de classes amb suport zero.
flat_test_gold = [t for s in test_gold for t in s]
flat_test_pred = [t for s in test_pred for t in s]
print("Test: report token per token")
print(classification_report(flat_test_gold, flat_test_pred, labels=sorted(set(flat_test_gold)), zero_division=0))
