"""Executa els fitxers d'exercicis en ordre i en un mateix espai de noms, igual que ho faria el notebook.

Serveix per provar en local el codi que després es copia al notebook. Les cel·les del notebook que no
són nostres (els print de les cel·les 13, 15 i 18) també es reprodueixen aquí perquè formen part del flux.
Ús: `python run_cells.py [ultim_exercici]`, per exemple `python run_cells.py 3`.
"""

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Cel·les originals del notebook que no hem de modificar però que depenen del nostre codi.
ORIGINAL_CELLS = {
    2: '''
print(train_sentences[0]); print(train_labels[0])
print(train_sentences[1]); print(train_labels[1])

def count_unique_entities(list_of_label_sentences):
  flat_labels = []
  for labels in list_of_label_sentences:
    flat_labels += labels.split()
  c = Counter(flat_labels)
  return len(c), list(c.keys())

num_unique_entities, unique_entities = count_unique_entities(train_labels)
print("Number of different entities:", num_unique_entities)
''',
}


def run(last_exercise: int) -> dict:
    """Executa ej0_setup.py i ej1..ejN dins del directori parte2/, on hi ha la carpeta data/."""
    os.chdir(HERE.parent)
    namespace: dict = {"__name__": "__main__"}
    files = [HERE / "ej0_setup.py"] + [HERE / f"ej{i}.py" for i in range(1, last_exercise + 1)]
    for i, path in enumerate(files):
        print(f"\n===== {path.name} =====")
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), namespace)
        if i in ORIGINAL_CELLS:
            print("----- cel·les originals -----")
            exec(ORIGINAL_CELLS[i], namespace)
    return namespace


if __name__ == "__main__":
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
