# %% [markdown] [Cel·la nova abans del codi de l'Exercici 1]
# Els CSV separen els camps amb `", "` i cada camp va entre cometes. Com que després de la coma hi ha un
# espai, pandas no reconeix l'inici del camp entrecomillat i deixa les cometes dins del text, de manera
# que apareixerien etiquetes falses com `"O` o `B-arrive_time.period_of_day"`. Amb `skipinitialspace=True`
# el parser salta aquest espai i llegeix els camps correctament. També comprovem que cada oració té
# tantes etiquetes com paraules, perquè tot el que ve després assumeix aquesta alineació 1 a 1.

# %% [Cel·la 9: Exercici 1]
COLUMNS = ["sentence", "labels", "intent"]


def load_split(path: Path) -> pd.DataFrame:
    """Llegeix un CSV d'ATIS (sense capçalera) i valida que frases i etiquetes estan alineades."""
    df = pd.read_csv(path, header=None, names=COLUMNS, skipinitialspace=True)
    df = df.apply(lambda col: col.str.strip())
    misaligned = df["sentence"].str.split().str.len() != df["labels"].str.split().str.len()
    assert not misaligned.any(), f"{misaligned.sum()} oracions amb diferent nombre de paraules i etiquetes"
    return df


train_df = load_split(DATA_DIR / "train.csv")
test_data = load_split(DATA_DIR / "test.csv")

# La validació són les últimes files de train; reset_index evita arrossegar índexs desplaçats.
train_data = train_df.iloc[:-VAL_SIZE].reset_index(drop=True)
val_data = train_df.iloc[-VAL_SIZE:].reset_index(drop=True)

print("Training size:", len(train_data))
print("Validation dataset size:", len(val_data))
print("Test dataset size:", len(test_data))
