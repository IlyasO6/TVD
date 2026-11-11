"""Cel·les de l'Exercici 7 del notebook P2_2 i eina per inserir-les.

Les cel·les es defineixen aquí perquè sigui fàcil revisar-les i regenerar-les. `python tools/ex7_cells.py
insert` les posa al notebook just després de l'enunciat de l'Exercici 7 (substituint les que s'hi hagin
inserit abans, marcades amb l'etiqueta `ex7`), i `python tools/ex7_cells.py script <sortida.py>` en fa un
script pla amb QUICK = True per comprovar en local que tot el flux s'executa.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[2] / "P2_2_alumnes.ipynb"
TAG = "ex7"
PENDING = "**Anàlisi dels resultats:** *pendent d'executar les graelles a Colab.*"

CELLS: list[tuple[str, str]] = [
    ("markdown", """---

## Exercici 7: metodologia

Tot el codi de l'Exercici 7 és al paquet `parte2/ner/`: configuracions (`config.py`), dades (`data.py`), models
compostos per blocs (`models/`), un únic bucle d'entrenament (`train.py`), mètriques (`metrics.py`) i una
graella per apartat (`experiments/`). Totes les variants comparteixen preprocessament, entrenament i avaluació,
així que les diferències entre resultats només poden venir del factor que es canvia.

El protocol és el mateix a tots els apartats. Es canvia un factor cada vegada respecte al baseline de
l'Exercici 6, cada configuració s'entrena amb 3 llavors i es reporta la mitjana ± la desviació, i totes les
decisions es prenen amb la F1 de validació (el test només s'observa). La mètrica principal és la F1 d'entitats
en mode estricte (seqeval, equivalent a conlleval); també es mostren la F1 macro, que reflecteix les classes
rares, el nombre de paràmetres i el temps per època. El baseline es reentrena amb early stopping més robust
(`min_delta = 0.001` i fins a 40 èpoques), perquè a l'Exercici 6 la F1 encara pujava mil·lèsimes a l'època 30.

Cada execució es desa en un JSON a `parte2/results/` en acabar, de manera que si l'entorn es desconnecta, en
tornar a executar la cel·la només s'entrena el que falta."""),
    ("code", """# Configuració de l'Exercici 7. A Colab, PARTE2_DIR ha d'apuntar a la carpeta parte2 (millor a Google Drive,
# així els resultats sobreviuen a les desconnexions).
import os
import sys
from pathlib import Path

try:
    from IPython.display import display
except ImportError:
    display = print

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    from google.colab import drive
    drive.mount("/content/drive")
    PARTE2_DIR = Path("/content/drive/MyDrive/TVD/p2/parte2")  # ajusta la ruta a on tinguis la carpeta
else:
    PARTE2_DIR = Path("parte2").resolve()

os.environ["NER_RESULTS_DIR"] = str(PARTE2_DIR / "results")
sys.path.insert(0, str(PARTE2_DIR))

from ner import run_grid
from ner.experiments import ex7_1, ex7_2, ex7_3, ex7_4, ex7_5, ex7_6, extras, final

# QUICK = True entrena 1 època amb 1 llavor: només serveix per comprovar que tot s'executa.
# El codi de ner/ s'ha de congelar abans de llançar les graelles de debò: la cache identifica cada execució
# per la seva configuració, no per la versió del codi.
QUICK = False
N_WORKERS = 2            # execucions simultànies a la GPU; es pot ajustar amb el benchmark de la cel·la següent
SEEDS = (0,) if QUICK else (0, 1, 2)
FINAL_SEEDS = (0,) if QUICK else final.FINAL_SEEDS


def run(configs, seeds=SEEDS):
    \"\"\"Llança una graella amb cache; en mode QUICK redueix cada configuració a una sola època.\"\"\"
    if QUICK:
        configs = [c.with_(**{"train.max_epochs": 1}) for c in configs]
    return run_grid(configs, seeds=seeds, n_workers=N_WORKERS)


def fig_name(name):
    \"\"\"En mode QUICK no es desen figures, per no sobreescriure les bones amb resultats d'una època.\"\"\"
    return None if QUICK else name"""),
    ("code", """# Benchmark opcional: quantes execucions simultànies aprofiten millor la GPU. Entrena 4 models curts per a cada
# valor en una carpeta temporal, sense tocar la cache de resultats.
import tempfile
import time

from ner import baseline

if not QUICK:
    results_dir = os.environ["NER_RESULTS_DIR"]
    for workers in (1, 2, 4):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["NER_RESULTS_DIR"] = tmp
            start = time.perf_counter()
            run_grid([baseline().with_(**{"train.max_epochs": 3})], seeds=(10, 11, 12, 13), n_workers=workers)
            print(f"n_workers = {workers}: {time.perf_counter() - start:.0f} s")
    os.environ["NER_RESULTS_DIR"] = results_dir"""),

    ("markdown", """### 7.1 Mida dels embeddings i embeddings preentrenats

Es proven embeddings aleatoris de 16 a 512 dimensions i GloVe (50, 100, 200 i 300) congelat i amb fine-tuning.
Hipòtesi: amb un vocabulari d'unes 600 paraules la F1 hauria de saturar cap a 50-100 dimensions i empitjorar
lleugerament per sobre de 256 per sobreajust. GloVe hauria d'ajudar sobretot amb paraules rares o no vistes
(Jurafsky & Martin, cap. 6). Com que el vocabulari amb GloVe també inclou les paraules que surten un sol cop a
train, el control `aleatori-100 min_freq=1` separa l'efecte del vocabulari del dels vectors preentrenats."""),
    ("code", """display(ex7_1.vocab_stats().round(4))
r71 = run(ex7_1.configs())
s71, fig71 = ex7_1.report(r71, save_as=fig_name("ex7_1_embeddings"))
display(s71.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### 7.2 Xarxes convolucionals i pooling

Tres usos de la convolució: una CNN de paraula davant de la BiLSTM, una CNN sola i una char-CNN amb max-pooling
sobre els caràcters de cada paraula (Ma & Hovy, 2016). Un global pooling sol no serveix en NER perquè elimina la
sortida per token; aquí el pooling es fa servir com a max-pooling local amb stride 1, com a vector de context
global concatenat a cada token i dins de la char-CNN. Hipòtesi: la CNN davant de la BiLSTM aporta poc perquè la
BiLSTM ja captura el context local; la CNN sola falla en etiquetes que depenen de paraules llunyanes
(`arrive_time` vs `depart_time`); la char-CNN millora les paraules fora de vocabulari."""),
    ("code", """r72 = run(ex7_2.configs())
s72, fig72 = ex7_2.report(r72, save_as=fig_name("ex7_2_cnn"))
display(s72.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### 7.3 Xarxes recurrents

Primer es canvia un factor cada vegada (tipus de cel·la, direcció, capes i mida de l'estat) i després es creuen
automàticament els guanyadors de cada factor amb el valor del baseline. La LSTM unidireccional de 256 unitats té
la mateixa mida de sortida que la BiLSTM de 128 i separa l'efecte de la direcció del de la capacitat. Hipòtesi:
LSTM i GRU queden a prop (oracions curtes), la bidireccionalitat és el factor més important i més capes sense
dropout sobreajusten."""),
    ("code", """r73 = run(ex7_3.configs())
r73 += run(ex7_3.cross_configs(r73))
s73, fig73 = ex7_3.report(r73, save_as=fig_name("ex7_3_rnn"))
display(s73.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### 7.4 Transformer

Un encoder Transformer sol (amb posició sinusoidal, apresa o sense posició) i un híbrid amb capes d'atenció
sobre la BiLSTM. La primera fase compara la recepta d'optimització del baseline amb LR 5e-4 i warmup; la segona
fa servir la recepta guanyadora a totes les variants. Hipòtesi: entrenat des de zero amb 4k oracions, el
Transformer sol queda per sota de la BiLSTM perquè no té biaix de seqüencialitat; sense posició falla en
distincions d'ordre com `fromloc`/`toloc`; l'híbrid iguala o millora lleugerament el baseline."""),
    ("code", """r74 = run(ex7_4.configs())
r74 += run(ex7_4.variant_configs(r74))
s74, fig74 = ex7_4.report(r74, save_as=fig_name("ex7_4_transformer"))
display(s74.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### 7.5 Regularització amb dropout

Dropout sobre l'embedding, entre capes recurrents, abans del classificador i dins del Transformer, en tres
models: el baseline, una BiLSTM 2×256 i el millor model amb atenció de l'apartat anterior. Cada posició es prova
sola (p = 0.3) i després totes juntes (p = 0.1, 0.3, 0.5). Hipòtesi: l'efecte més clar és al model gran (menys
distància entre la loss de train i la de validació i millor F1); p = 0.5 és massa per a un dataset tan petit."""),
    ("code", """r75 = run(ex7_5.configs(r74))
s75, fig75, curves75 = ex7_5.report(r75, save_as=fig_name("ex7_5_dropout"))
display(s75.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### 7.6 Balanceig de les classes

Pesos a la cross-entropy segons la freqüència de cada etiqueta a train: inversa (amb i sense límit), inversa de
l'arrel, nombre efectiu de mostres (Cui et al., 2019) i reduir només el pes de `O`. Hipòtesi: els pesos pugen el
recall i la F1 de les classes rares a canvi de precisió; la inversa pura és massa agressiva i el límit o l'arrel
donen el millor compromís."""),
    ("code", """display(ex7_6.weights_table().round(3))
r76 = run(ex7_6.configs())
s76, fig76 = ex7_6.report(r76, save_as=fig_name("ex7_6_balanceig"))
display(s76.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### Experiments addicionals: CRF, esquema d'etiquetes i vocabulari

Disseny 2×2 entre esquema (BIO, BILOU) i decodificador (softmax, CRF implementat a mà amb forward i Viterbi), i
`min_freq = 1`. Hipòtesi: amb softmax, BILOU produeix més seqüències impossibles que BIO, i el CRF, que aprèn
quines transicions són vàlides, les redueix gairebé a zero."""),
    ("code", """rx = run(extras.configs())
sx, figx = extras.report(rx, save_as=fig_name("extra_crf_esquema"))
display(sx.round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### Model final, ablació i significança

El model final es construeix automàticament amb els resultats de validació: de cada apartat s'agafa la
configuració guanyadora i només s'hi afegeix si millora la seva referència per més d'una desviació estàndard.
Després, l'ablació treu un component cada vegada (5 llavors) i un bootstrap pareat sobre les oracions de test
diu si la millora respecte al baseline és significativa."""),
    ("code", """section_results = {"7.1": r71, "7.2": r72, "7.3": r73, "7.4": r74, "7.5": r75, "7.6": r76, "extra": rx}
components, log = final.build_final(section_results)
print("\\n".join(log))
final_cfg = final.compose(components)
print("\\nModel final:", {k: v for k, v in final_cfg.to_dict().items() if k in ("data", "model")})
print("Entrenament:", final_cfg.to_dict()["train"])

rf = run(final.ablation_configs(components), seeds=FINAL_SEEDS)
sf, figf = final.report(rf, save_as=fig_name("final_ablacio"))
display(sf.round(4))
display(final.significance(rf).round(4))"""),
    ("code", """s_all, fig_all = final.overview_figure(section_results, rf, save_as=fig_name("resum_global"))
display(s_all[["test_entity_f1_mean", "test_entity_f1_std", "test_entity_f1_macro_mean", "n_params"]].round(4))"""),
    ("markdown", PENDING),

    ("markdown", """### Anàlisi d'errors

Es fa servir l'execució amb F1 de validació mediana de cada model, per no triar la llavor més afortunada. Cada
error d'entitat es classifica com a tipus equivocat, límits equivocats, no detectada o inventada."""),
    ("code", """from ner import analysis
from ner.config import ExperimentConfig
from ner.data import prepare_data
from ner.metrics import entity_report

categories = {}
for name in (final.BASELINE, final.FINAL):
    run_result = analysis.median_seed_result(rf, name)
    cfg = ExperimentConfig.from_dict(run_result["config"])
    test = prepare_data(cfg.data).splits["test"]
    pred = [p.split() for p in run_result["test_pred"]]
    cat, conf = analysis.error_summary(test.gold, pred)
    categories[name] = cat
    print(f"\\n=== {name}: confusions de tipus més freqüents ===")
    display(conf)
display(pd.DataFrame(categories).round(3))

report_final = entity_report(test.gold, pred, cfg.data.scheme)
print("Entitats amb pitjor F1 al model final (amb suport mínim de 5):")
display(report_final[report_final["support"] >= 5].head(10).round(3))
for example in analysis.error_examples(test.sentences, test.gold, pred, n=4):
    print(example, end="\\n\\n")"""),
    ("markdown", PENDING),
]


def _cell(kind: str, source: str) -> dict:
    lines = source.splitlines(keepends=True)
    cell = {"cell_type": kind, "metadata": {"tags": [TAG]}, "source": lines}
    if kind == "code":
        cell.update({"execution_count": None, "outputs": []})
    return cell


def insert() -> None:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cells = [c for c in nb["cells"] if TAG not in c.get("metadata", {}).get("tags", [])]
    anchor = next(i for i, c in enumerate(cells) if c["cell_type"] == "markdown" and "name=\"ex-seven\"" in "".join(c["source"]))
    nb["cells"] = cells[:anchor + 1] + [_cell(k, s) for k, s in CELLS] + cells[anchor + 1:]
    NOTEBOOK.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(CELLS)} cel·les inserides després de la cel·la {anchor}")


def script(path: Path) -> None:
    code = [s for k, s in CELLS if k == "code"]
    text = "import pandas as pd\n" + "\n\n".join(code).replace("QUICK = False", "QUICK = True")
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    if sys.argv[1] == "insert":
        insert()
    else:
        script(Path(sys.argv[2]))
