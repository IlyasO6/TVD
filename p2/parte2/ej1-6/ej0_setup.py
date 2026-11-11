# %% [Cel·la 5: afegir seqeval a la instal·lació; la resta de la cel·la es manté igual]
# !pip install gdown seqeval

# %% [Cel·la 3: substitueix la cel·la d'imports original]
import copy
import random
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import accuracy_score, classification_report, f1_score
from seqeval.metrics import classification_report as entity_report
from seqeval.metrics import f1_score as entity_f1_score
from seqeval.scheme import BILOU, IOB2

# %% [Cel·la nova just després dels imports: configuració i reproductibilitat]
# Tots els paràmetres que es toquen entre execucions viuen aquí perquè el notebook sigui fàcil de reproduir.
DATA_DIR = Path("data")
VAL_SIZE = 900          # l'enunciat demana les 900 últimes línies de train com a validació
LABEL_SCHEME = "BILOU"  # "BILOU" (el que demana l'enunciat) o "BIO" (el format original del CSV)
MIN_FREQ = 2            # les paraules que surten menys cops a train es tracten com a <unk>
PAD_TOKEN, UNK_TOKEN = "<pad>", "<unk>"
SEED = 42


def set_seed(seed: int = SEED) -> None:
    """Fixa totes les fonts d'aleatorietat perquè dues execucions donin els mateixos resultats."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


set_seed()
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", device)
