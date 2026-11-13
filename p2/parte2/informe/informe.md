# Pràctica 2, part 2: reconeixement d'entitats anomenades a ATIS

**Tractament de la Veu i el Diàleg** · Laia Beyloc i Ilyas Ouacham

> Esborrany revisat de l'informe. La versió que s'entrega és la de `latex/`; aquest fitxer en conserva el mateix
> text per poder-lo revisar còmodament. Totes les xifres surten del notebook `P2_2_alumnes.ipynb` i dels
> resultats desats a `parte2/results/`.

---

## 1. Introducció

Un sistema de diàleg orientat a tasques necessita dues coses de cada frase de l'usuari: què vol fer (la
intenció, que treballem a la primera part de la pràctica) i amb quins valors (les entitats). Si algú escriu "i
want to fly from boston to denver on thursday", el sistema ha de saber que `boston` és l'origen, `denver` la
destinació i `thursday` el dia de sortida. Aquesta part tracta el reconeixement d'entitats (NER) com un problema
d'etiquetatge de seqüències sobre ATIS, un corpus de consultes de reserves de vols: cada paraula rep una etiqueta
que indica si forma part d'una entitat, de quin tipus és i en quina posició hi cau.

Hem entrenat els models amb xarxes neuronals, sense LLM, i hem estudiat com canvia el rendiment segons la
representació de les paraules, el tipus d'encoder, la regularització i el tractament del desequilibri entre
classes. L'informe segueix els exercicis: preparació de dades (1-4), model base (5-6) i estudi experimental (7),
que acabem amb un model final, una ablació i una anàlisi d'errors.

## 2. Experiments i resultats

### 2.1 Dades i preprocessament (exercicis 1-4)

El corpus té 4.978 frases d'entrenament, de les quals reservem les 900 últimes per a validació, i 893 de test
(taula 1). En carregar els CSV vam trobar dos problemes. Els camps estan separats per `", "` i entre cometes, i
pandas, si no se li indica `skipinitialspace=True`, deixa les cometes dins del text, de manera que apareixen
etiquetes inexistents com `"O`. L'altre és que el fitxer fa servir l'esquema BIO, tot i que l'enunciat parla de BILOU.
Vam decidir convertir-lo a BILOU (una `B` aïllada passa a ser `U` i l'última `I` d'una entitat passa a ser `L`),
perquè la conversió es pot desfer i dona al model un senyal explícit del final de cada entitat. L'esquema ha
quedat com a paràmetre, i a l'apartat 2.10 comparem tots dos.

Les frases ja venen tokenitzades i en minúscules, així que separem per espais i mantenim l'alineació d'una
etiqueta per paraula. El vocabulari es construeix només amb train, i les paraules que hi surten un sol cop van a
`<unk>`; si totes hi entressin, el vector de `<unk>` no s'entrenaria mai. El padding té un índex propi que la loss
ignora. Les poques etiquetes de validació i test que no surten mai a train també es codifiquen amb aquest índex,
però l'avaluació es fa contra les etiquetes originals en text, i per tant aquests tokens compten com a errors.

**Taula 1.** Estadístiques del dataset.

| | Valor |
|---|---|
| Frases train / validació / test | 4.078 / 900 / 893 |
| Longitud mitjana (màxima) de les frases | 11,4 (46) paraules |
| Etiquetes BILOU (BIO) | 178 (119) |
| Proporció de tokens `O` | 63,7% |
| Etiquetes amb un sol exemple a train | 25 |
| Tokens amb etiqueta no vista a train (val / test) | 7 / 10 |
| Vocabulari (`min_freq = 2`) i tokens `<unk>` a test | 589 paraules, 1,44% |

### 2.2 Model base (exercicis 5-6)

El model base té un embedding de 128 dimensions, una LSTM bidireccional de 128 unitats i una capa lineal que
classifica cada token. Abans de la LSTM empaquetem les seqüències amb la seva longitud real; sense aquest pas, la
direcció cap enrere començaria cada frase llegint desenes de posicions de padding. Entrenem amb Adam (LR 10⁻³) i
fem *early stopping* sobre la F1 d'entitats de validació.

Aquesta F1, calculada en mode estricte amb seqeval (equivalent a conlleval), és la mètrica principal de tot el
treball. Una entitat només compta com a encertada si coincideixen el tipus i els límits. L'accuracy per token
gairebé no informa, perquè un model que predigués sempre `O` ja tindria una accuracy de més del 60%.

**Taula 2.** Resultats del model base (exercici 6, una llavor).

| | F1 entitats | Accuracy token | F1 macro token (sense `O`) |
|---|---|---|---|
| Validació | 0,975 | 0,989 | 0,820 |
| Test | 0,953 | 0,977 | 0,707 |

A test, la F1 micro d'entitats és 0,95 i la macro, 0,73. Les entitats freqüents, com `fromloc.city_name`, surten
gairebé perfectes, mentre que moltes de les rares tenen F1 baixa o zero. La loss de validació arriba al mínim cap
a l'època 17 i a partir d'aquí puja lleugerament, tot i que la de train continua baixant.

### 2.3 Metodologia de l'exercici 7

Per comparar variants de manera justa vam escriure un paquet (`parte2/ner/`) on totes comparteixen el
preprocessament, el bucle d'entrenament i l'avaluació, i cada arquitectura és un bloc intercanviable. En cada
apartat canviem un sol factor respecte al baseline i entrenem cada configuració amb 3 llavors. A les taules donem
la mitjana i la desviació. Les decisions les prenem sempre amb validació, i el test només el mirem. A més de la F1
d'entitats, seguim la F1 macro, el nombre de paràmetres entrenables i el temps per època. En total hem fet 278
entrenaments, unes 3,3 hores en una GPU T4.

Per a l'exercici 7 vam afegir a l'*early stopping* un `min_delta = 0,001`, pensant que estalviaria èpoques de
millores minúscules. Va resultar massa estricte, i per això el baseline de l'exercici 7 (0,946 de test amb cinc llavors) queda per sota del de l'exercici 6 (0,953). Com que tots els experiments comparteixen el criteri, les comparacions continuen sent
vàlides. A l'apartat 2.11 comprovem que les conclusions es mantenen sense `min_delta`.

### 2.4 Mida dels embeddings i embeddings preentrenats (7.1)

Hem provat embeddings aleatoris de 16 a 512 dimensions i vectors GloVe (Pennington et al., 2014) de 50, 100, 200 i
300 dimensions, congelats o amb *fine-tuning* (figura 1). Dels fitxers de GloVe només hem guardat els vectors de
les paraules que apareixen a ATIS. Això dona exactament les mateixes prediccions que fer servir GloVe sencer,
perquè una paraula que no apareix mai no es consulta, i no fa servir cap etiqueta de validació ni de test.

> **Figura 1** — `ex7_1_embeddings.pdf`

Amb embeddings aleatoris, la F1 de validació puja de 0,960 a 16 dimensions a 0,975 a 100, i a partir d'aquí
s'estanca. Esperàvem que per sobre de 256 dimensions el model sobreajustés i empitjorés, i no passa. El que veiem
és que els embeddings grans convergeixen abans (la millor època baixa de 25 a 10) i suposem que l'*early stopping* els atura abans que l'excés de capacitat arribi a fer mal. La F1 macro sí que baixa una mica a 300 i 512 dimensions.

GloVe millora tant la F1 micro com la macro. Congelat i amb 300 dimensions arriba a 0,980 de validació, 0,4 punts
per sobre del millor embedding aleatori. A test, tots els GloVe de 100 dimensions o més superen tots els
aleatoris, i la F1 macro passa de 0,717 (baseline) a valors entre 0,750 i 0,774, que és on es veu l'efecte sobre les paraules rares. Com que el
vocabulari amb GloVe també inclou les paraules que surten una sola vegada, vam afegir un control: vocabulari
complet (`min_freq = 1`) amb vectors aleatoris. Aquest control no millora (0,971), així que el guany ve dels
vectors. Entre congelar i fer *fine-tuning* no trobem una diferència
consistent, i congelar estalvia entrenar uns 280.000 paràmetres.

### 2.5 Xarxes convolucionals i pooling (7.2)

Hem fet servir la convolució de tres maneres (figura 2): una CNN de paraula davant de la BiLSTM, una CNN sola i
una char-CNN que construeix la representació de cada paraula a partir dels seus caràcters (Ma i Hovy, 2016). El
pooling necessitava una adaptació. Un *global pooling* redueix la frase a un sol vector, i en NER cal una sortida
per paraula. L'hem aplicat com a max-pooling local amb stride 1, com a vector global concatenat a cada posició i
sobre els caràcters de cada paraula dins de la char-CNN.

> **Figura 2** — `ex7_2_cnn.pdf`

Posar una CNN davant de la BiLSTM no ajuda. La millor variant (kernel 3) obté 0,975, dins de la variabilitat del
baseline (0,974 ± 0,003), i els kernels grans o les dues capes empitjoren. Entenem que la BiLSTM ja recull el
context local i que la convolució només hi afegeix paràmetres.

Sense recurrència, la CNN queda per sota (entre 0,92 i 0,95 de validació) i millora a mesura que creix el camp
receptiu: 0,922 amb una capa de kernel 3, 0,944 amb dues i 0,954 combinant kernels de 3 i 5. Etiquetes com
`arrive_time` i `depart_time` depenen de paraules allunyades, i una finestra petita no les veu. Per la mateixa
raó, el vector de context global és el que més ajuda a la CNN sola (dos punts de F1 de validació i cinc de F1 macro a test), mentre
que sobre la BiLSTM no aporta res. El max-pooling local empitjora la CNN (0,935), segurament perquè barreja
activacions de paraules veïnes i difumina on comença i on acaba cada entitat.

La char-CNN és l'única variant que supera el baseline més enllà de la variabilitat entre llavors, amb 0,978 de validació, 0,951 de test i 3-4 punts més de
F1 macro. Pensàvem que l'efecte vindria sobretot de les paraules desconegudes, però sobre els 76 tokens de test
que no surten a train l'accuracy només passa de 0,55 a 0,57-0,60. Creiem que la millora ve més aviat de
representar bé paraules rares que sí que són al vocabulari, com números de vol o codis d'aeroport.

### 2.6 Xarxes recurrents (7.3)

Hem variat el tipus de cel·la, la direcció, el nombre de capes i la mida de l'estat d'un en un, i després hem
creuat automàticament els valors guanyadors (taula 3). Per separar l'efecte de la direcció del de la capacitat,
hem inclòs una LSTM unidireccional de 256 unitats, que té la mateixa mida de sortida que la BiLSTM de 128.

**Taula 3.** Variants recurrents (3 llavors; la desviació de validació és ≤ 0,003 en totes).

| Configuració | Val F1 | Test F1 | F1 macro test | Paràmetres |
|---|---|---|---|---|
| BiLSTM 1×128 (baseline) | 0,9737 | 0,9450 | 0,717 | 386k |
| BiGRU 1×128 | 0,9736 | 0,9494 | 0,724 | 320k |
| LSTM 1×128 (unidireccional) | 0,9475 | 0,9200 | 0,669 | 231k |
| LSTM 1×256 (unidireccional) | 0,9471 | 0,9229 | 0,697 | 517k |
| BiLSTM 2×128 | 0,9738 | 0,9493 | 0,742 | 781k |
| BiLSTM 3×128 | 0,9721 | 0,9428 | 0,710 | 1.176k |
| BiLSTM 1×64 | 0,9747 | 0,9453 | 0,685 | 198k |
| BiLSTM 1×256 | 0,9748 | 0,9494 | 0,738 | 958k |
| BiLSTM 2×256 (creuament) | 0,9765 | 0,9508 | 0,746 | 2.535k |

Treure el context dret costa 2,6 punts, i la LSTM unidireccional de 256 unitats no en recupera cap, de manera que
la pèrdua ve del context que falta. És el factor més gran de tot l'apartat. LSTM i GRU queden
empatades, tot i que la GRU té un 17% menys de paràmetres, i el nombre de capes o la mida de l'estat pràcticament
no canvien res. El creuament (BiLSTM 2×256) obté la F1 més alta, però el guany és de 0,28 punts, igual que la
desviació del baseline, i necessita 6,5 vegades més paràmetres. Amb frases de 11 paraules de mitjana i 4.000
exemples, una BiLSTM d'una capa ja té capacitat de sobres.

### 2.7 Transformer (7.4)

Hem substituït la BiLSTM per un encoder Transformer (Vaswani et al., 2017) i n'hem variat les capes, els caps
d'atenció, la capa *feed-forward* i la codificació posicional (sinusoidal, apresa o cap). També hem provat un
híbrid amb capes d'atenció sobre la BiLSTM (figura 3). Com que els Transformers solen necessitar un learning rate
més baix i *warmup*, una primera fase va comparar la recepta del baseline amb LR 5·10⁻⁴ i dues èpoques de *warmup*.
Va guanyar la recepta del baseline, i és la que hem fet servir en totes les variants.

> **Figura 3** — `ex7_4_transformer.pdf`

El Transformer de referència treu 0,948 de validació i 0,915 de test, tres punts per sota de la BiLSTM, i perd
deu punts de F1 macro. Sense recurrència, el model ha d'aprendre de les dades l'ordre de les paraules a més del
seu significat, i amb 4.000 frases les classes rares no tenen prou exemples per fer-ho (Jurafsky i Martin,
cap. 9). Si li traiem la codificació posicional, la F1 cau a 0,797, perquè no pot distingir "from boston to
denver" de "from denver to boston". La posició apresa queda una mica per sota de la sinusoidal.

Esperàvem que més capes portessin a sobreajust, però amb quatre capes el Transformer millora fins a 0,956, el
seu millor resultat. L'híbrid, que segons la nostra hipòtesi havia d'igualar el baseline, es queda en 0,966. La distància entre la loss de train i la de validació de l'híbrid (0,077) és la més gran de tots els models amb BiLSTM que hem entrenat (la del baseline és 0,047), i apunta a sobreajust de les capes d'atenció. L'apartat següent ho confirma.

### 2.8 Regularització amb dropout (7.5)

Hem posat dropout a l'embedding, entre capes recurrents (Zaremba et al., 2014), abans del classificador i dins del
Transformer, en tres models: el baseline, una BiLSTM 2×256 i l'híbrid amb atenció. Primer hem provat cada posició
sola amb p = 0,3 i després totes juntes amb p = 0,1, 0,3 i 0,5 (a l'híbrid, només 0,1 i 0,3) (figura 4).

> **Figura 4** — `ex7_5_dropout_curves.pdf`

Al baseline, dropout de 0,3 a l'embedding i al classificador millora 0,3 punts de validació, 0,6 de test i tres de
F1 macro, i a test gairebé tota la millora ve del dropout de l'embedding. Té sentit en un vocabulari on moltes paraules surten poques vegades. Amb p = 0,5 la distància entre la loss de train i la de validació gairebé
desapareix, però la F1 torna a baixar.

A l'híbrid amb atenció, el dropout fa passar la F1 de 0,966 a 0,974 de validació i de 0,935 a 0,948 de test, i la
distància de loss es redueix a la meitat. Amb dropout, l'híbrid arriba al nivell del baseline però no el supera.

La BiLSTM 2×256 contradiu la hipòtesi. Era el model amb més paràmetres dels tres, i el dropout no li canvia la F1. La distància de loss sí que es redueix, de 0,055 a 0,025 amb p = 0,5. La nostra interpretació és que
l'*early stopping* ja atura la BiLSTM abans que el sobreajust afecti les prediccions, mentre que les capes
d'atenció sobreajusten tan de pressa que l'aturada no arriba a temps.

### 2.9 Balanceig de les classes (7.6)

Hem ponderat la cross-entropy segons la freqüència de cada etiqueta amb cinc esquemes: inversa de la freqüència
(amb i sense límit), inversa de l'arrel (amb i sense límit) i nombre efectiu de mostres (Cui et al., 2019). També
hem provat de reduir només el pes de `O` (figura 5). Normalitzem els pesos perquè el token mitjà pesi 1. Amb la
inversa pura, una etiqueta vista un sol cop pesa 260 vegades més que el token mitjà, i `O` gairebé no compta.

> **Figura 5** — `ex7_6_balanceig.pdf`

En el grup de classes rares (menys de 10 exemples a train), la F1 per token passa de 0,31 a 0,39-0,41 amb
qualsevol esquema basat en la freqüència, i la F1 macro per token puja entre un i tres punts. A canvi es perd una mica de
precisió. La F1 micro d'entitats no millora amb cap esquema. La inversa pura l'empitjora mig punt, tot i que les
seves tres llavors arriben al límit de 40 èpoques i per tant el seu resultat és una cota inferior. La inversa de
l'arrel amb límit 10 manté la F1 micro i guanya tres punts de F1 macro per token. Reduir només el pes de `O` no
té cap efecte.

Com que el model final es tria per F1 micro, els pesos no hi entren. Si el sistema hagués de prioritzar les
entitats poc freqüents, la inversa de l'arrel amb límit seria l'opció a triar.

### 2.10 Experiments addicionals: CRF, esquema d'etiquetes i vocabulari

Hem implementat un CRF lineal (Lafferty et al., 2001) amb els algorismes forward i Viterbi, i n'hem comprovat el
càlcul enumerant totes les seqüències possibles en un cas petit. L'hem creuat amb l'esquema d'etiquetes en un
disseny 2×2 (taula 4). La F1 d'entitats és comparable entre BIO i BILOU perquè la conversió no perd informació i
les entitats de referència són les mateixes.

**Taula 4.** Esquema i decodificador (3 llavors). Invàlides: frases de test amb alguna transició impossible, com
una `L-x` sense `B-x` al davant.

| Configuració | Val F1 | Test F1 | F1 macro test | Invàlides (test) | s/època |
|---|---|---|---|---|---|
| BILOU + softmax (baseline) | 0,9737 | 0,9450 | 0,717 | 44 | 1,9 |
| BILOU + CRF | 0,9742 | 0,9462 | 0,729 | 26 | 7,8 |
| BIO + softmax | 0,9740 | 0,9446 | 0,727 | 23 | 2,0 |
| BIO + CRF | 0,9741 | 0,9460 | 0,737 | 15 | 7,8 |
| `min_freq = 1` | 0,9739 | 0,9475 | 0,721 | 41 | 2,0 |

La nostra hipòtesi era que el CRF eliminaria gairebé totes les seqüències invàlides, i les redueix entre un 35 i un 40%. El CRF aprèn les
transicions a partir de les dades, sense cap restricció imposada, i les transicions entre etiquetes rares queden
mal estimades. Prohibir explícitament les transicions impossibles a Viterbi les eliminaria del tot. En F1 micro
el CRF no canvia res, millora un punt la F1 macro i multiplica per quatre el temps per època.

Entre BIO i BILOU no hi ha diferència de F1. BILOU produeix el doble de seqüències invàlides amb softmax, i
l'avantatge d'indicar explícitament el final de cada entitat no compensa passar de 119 a 178 classes. Amb
`min_freq = 1` tampoc no canvia res.

### 2.11 Model final, ablació i significança

El model final es construeix automàticament a partir dels resultats de validació. De cada apartat s'agafa la
millor variant, i només s'incorpora si supera la seva referència per més d'una desviació estàndard. Hi han entrat
GloVe-300 congelat, la char-CNN i el dropout de 0,3, tot sobre la BiLSTM d'una capa del baseline. L'encoder, els
pesos de classe i el CRF s'han quedat fora perquè els seus guanys (+0,27, +0,02 i +0,04 punts) no superen la
desviació entre llavors. Per a l'ablació hem reentrenat el model final traient cada component, ara amb cinc
llavors (taula 5).

**Taula 5.** Model final, ablació i control sense `min_delta` (5 llavors). Paràm.: paràmetres entrenables (els
vectors GloVe congelats no hi compten).

| Configuració | Val F1 | Test F1 | F1 macro test | Paràm. |
|---|---|---|---|---|
| Baseline | 0,9738 ± 0,0021 | 0,9463 ± 0,0035 | 0,727 | 386k |
| **Model final** | **0,9789 ± 0,0016** | **0,9552 ± 0,0021** | **0,777** | 547k |
| final − GloVe | 0,9792 | 0,9539 | 0,763 | 446k |
| final − char-CNN | 0,9778 | 0,9527 | 0,771 | 486k |
| final − dropout | 0,9783 | 0,9544 | 0,778 | 547k |
| Baseline, sense `min_delta` | 0,9760 ± 0,0026 | 0,9498 ± 0,0035 | 0,736 | 386k |
| Model final, sense `min_delta` | 0,9816 ± 0,0020 | 0,9568 ± 0,0015 | 0,791 | 547k |

> **Figura 6** — `resum_global.pdf`

El model final millora el baseline en 0,9 punts de F1 a test i en cinc de F1 macro (figura 6). Per saber si la
diferència és real, hem fet un bootstrap pareat sobre les frases de test, llavor a llavor. La millora és
significativa en les cinc llavors, amb un p-valor unilateral de com a màxim 0,026.

L'ablació indica que els tres components se solapen. El que més pesa és la char-CNN, sense la qual el model
perd 0,25 punts de test. Sense GloVe la validació gairebé no canvia, però el test baixa 0,13 punts i la F1 macro 1,4.
Treure el dropout queda dins del soroll. Per separat, cadascun millorava el test entre 0,56 i 0,71 punts, i junts n'aporten 0,9, menys de la meitat de la suma. Totes tres peces milloren la representació de les paraules poc freqüents, i és raonable que, en part, corregeixin els mateixos errors.

Faltava comprovar que el guany no fos un efecte del `min_delta`. El model final convergeix més a poc a poc que el
baseline (millor època 16,8 enfront de 12,6), i un criteri d'aturada estricte podia estar tallant el baseline
massa aviat. Hem reentrenat tots dos models sense `min_delta`, amb paciència 10 i fins a 60 èpoques. Tots dos
milloren, i la diferència baixa de 0,89 a 0,70 punts. Continua sent significativa en quatre de les cinc llavors,
la F1 macro hi guanya 5,4 punts i la desviació del model final queda en menys de la meitat de la del baseline.

### 2.12 Anàlisi d'errors

Hem classificat cada error d'entitat del test en quatre tipus: tipus equivocat (el tram és correcte però
l'etiqueta no), límits equivocats, entitat no detectada i entitat inventada (taula 6). Per no triar la llavor
més afortunada, fem servir l'execució amb la F1 de validació mediana.

**Taula 6.** Distribució dels errors a test.

| Categoria | Baseline | Model final |
|---|---|---|
| Tipus equivocat | 52% | 63% |
| Inventada | 20% | 16% |
| No detectada | 16% | 8% |
| Límits equivocats | 12% | 14% |

El model final deixa escapar menys entitats, i el que li queda són sobretot errors de tipus. La confusió més
freqüent, en tots dos models, és predir `toloc.city_name` on l'etiqueta correcta és `city_name`. Mirant els
exemples se n'entén el motiu. A ATIS, les ciutats i els estats sense rol apareixen en preguntes que no parlen
d'un trajecte, com "list california airports" o "which airport is closest to ontario california", mentre que a train només el 2,4% de les ciutats no tenen rol i `state_name` hi surt una sola vegada (al test, nou). Per això `state_name` té F1 zero al test i `city_name` té un recall de 0,54. Per encertar aquests casos cal saber què demana la frase, que és justament la
tasca de la primera part de la pràctica.

## 3. Conclusions

Cap dels encoders que hem provat (CNN, GRU, BiLSTM més profundes, Transformer o híbrids) supera la BiLSTM
d'una capa del baseline més enllà de la variabilitat entre llavors. Amb frases curtes i 4.000 exemples d'entrenament, aquesta xarxa ja té més
capacitat de la que poden aprofitar les dades. Les millores han vingut de la representació d'entrada: els
vectors GloVe, la char-CNN i el dropout a l'embedding. Combinats, porten la F1 de test de 0,946 a 0,955 i la F1
macro de 0,727 a 0,777, i la millora es manté quan es deixa entrenar els dos models sense `min_delta`.

Una part dels resultats ha contradit les nostres hipòtesis. El Transformer millora amb més capes, el dropout no fa
res a la BiLSTM gran i el CRF, sense restriccions explícites, no elimina les seqüències impossibles. També hem
vist que el `min_delta` que vam afegir era massa estricte. Als dos models on ho hem comprovat ens costava entre
0,2 i 0,4 punts, i si tornéssim a fer l'estudi no el faríem servir. Els pesos de classe són un bon exemple de com
la mètrica de selecció condiciona el resultat. Milloren les classes rares, però amb la F1 micro com a criteri no
entren al model final.

L'anàlisi d'errors indica per on continuar. La majoria d'errors que queden són confusions de rol que depenen de
la intenció de la frase, i un model que aprengués alhora la intenció (primera part) i les entitats tindria aquesta
informació. També provaríem la decodificació restringida al CRF.

## Referències

- D. Jurafsky i J. H. Martin. *Speech and Language Processing*, 3a ed. (esborrany), caps. 6, 8, 9 i 17.
- J. Pennington, R. Socher i C. D. Manning. GloVe: Global Vectors for Word Representation. EMNLP, 2014.
- X. Ma i E. Hovy. End-to-end Sequence Labeling via Bi-directional LSTM-CNNs-CRF. ACL, 2016.
- A. Vaswani et al. Attention Is All You Need. NeurIPS, 2017.
- J. Lafferty, A. McCallum i F. Pereira. Conditional Random Fields: Probabilistic Models for Segmenting and
  Labeling Sequence Data. ICML, 2001.
- W. Zaremba, I. Sutskever i O. Vinyals. Recurrent Neural Network Regularization. arXiv:1409.2329, 2014.
- Y. Cui et al. Class-Balanced Loss Based on Effective Number of Samples. CVPR, 2019.
