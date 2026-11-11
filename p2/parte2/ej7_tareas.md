# Ejercicio 7: plan de tareas

Cada tarea se hace en orden, sobre la infraestructura de la Tarea 0. Las rejillas completas se lanzan en
Colab T4; en local solo smoke tests (`env -u PYTHONPATH .../envs/tvd/python.exe -s ...`, 1 semilla, 2 épocas).

## Reglas comunes

- Las tareas 7.x solo crean su bloque en `ner/models/` y su rejilla en `ner/experiments/`. Si necesitan
  un campo nuevo en `config.py`, se añade con valor por defecto (la clave de caché solo usa los campos que
  difieren del valor por defecto, así que añadir campos no invalida resultados ya calculados).
- Nunca se cambian los valores por defecto de `config.py`: definen el baseline del ej. 6.
- Selección por validación, test solo para reportar. 3 semillas en exploración, 5 en modelo final y ablación.
- Cada `experiments/ex7_x.py` expone `configs()` y `report(results)`. El informe de cada tarea incluye la
  rejilla justificada, la hipótesis con su base teórica y qué gráfico/tabla genera.
- Estilo: comentarios y docstrings en catalán, breves, explicando qué y por qué; type hints; nada hardcodeado.

## Tarea 0: infraestructura común (`ner/`)

`config.py` (dataclasses con clave de caché), `data.py` (mismo preprocesado que ej. 1-4, BIO/BILOU,
MIN_FREQ, caracteres), `models/tagger.py` (embedder → bloques registrados → decodificador), `models/rnn.py`
(bloque base), `train.py` (bucle único, early stopping con `min_delta`, pesos de clase, warmup opcional),
`metrics.py` (F1 entidad, F1 macro token sin O, F1 por grupo de frecuencia, secuencias inválidas,
bootstrap pareado), `runner.py` (caché JSON en `results/`, varios procesos en la GPU), `plots.py`.

## Tarea 7.1: embeddings + GloVe

Dimensión con embeddings aleatorios: 16, 32, 64, 128, 256, 512. GloVe 50/100/200/300
(gensim `glove-wiki-gigaword-*`) congelado y fine-tuned; el vocabulario incluye las palabras de train con
vector aunque salgan una vez. Vectores del vocabulario guardados en `ner/assets/*.npy` (sin descargas en
el notebook). Gráfico: F1 val vs dimensión (log, barras de error), líneas aleatorio / GloVe congelado /
GloVe fine-tuned.

## Tarea 7.2: CNN + pooling

Conv1d de palabra antes de la BiLSTM (kernels 3, 5, 7 y multi-kernel 3+5; 64/128/256 filtros; 1-2 capas;
padding `same`). Modelo solo CNN. Pooling: max-pool local stride 1, vector global de frase concatenado a
cada token y char-CNN con max-pooling sobre caracteres (Ma & Hovy 2016; dim 25/50, kernel 3). Justificar
por qué un global pooling solo no sirve en NER.

## Tarea 7.3: recurrentes

LSTM vs GRU, uni vs bi, 1/2/3 capas, hidden 64/128/256. Un factor cada vez y cruce reducido con los
ganadores. Reportar parámetros y tiempo por época.

## Tarea 7.4: Transformer

`nn.TransformerEncoder` con máscara de padding, posicional sinusoidal vs aprendido. Solo Transformer
(d_model 128; 1/2/4 capas; 2/4/8 cabezas; FF 256/512) y BiLSTM + Transformer encima. Si necesita LR menor o
warmup, como opción de config, indicado como confusor.

## Tarea 7.5: dropout

Posiciones: embedding, entre capas RNN, antes del clasificador. Valores 0.1/0.3/0.5. Sobre el baseline y un
modelo grande (2 capas, hidden 256). Curvas train/val loss sin y con el mejor dropout y gap final.

## Tarea 7.6: balanceo

Pesos: ninguno, inversa de frecuencia, inversa de la raíz, con recorte, y bajar solo el peso de O. F1 micro
vs macro, F1 por grupo de frecuencia (raras < 10, medias, frecuentes > 100), precisión vs recall.

## Extras

CRF sobre la BiLSTM implementado a mano (forward + Viterbi) con conteo de secuencias inválidas
softmax vs CRF. BIO vs BILOU. MIN_FREQ 1 vs 2.

## Tarea final

Modelo final elegido automáticamente por validación combinando lo mejor de cada apartado, ablación quitando
cada componente (5 semillas), bootstrap pareado baseline vs final, análisis de errores (peores entidades,
confusiones fromloc/toloc y depart/arrive, ejemplos) y dot plot resumen. Celdas del notebook del ej. 7.
