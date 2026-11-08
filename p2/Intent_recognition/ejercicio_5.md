# Ejercicio 5: implementación, protocolo y comprobaciones

Fecha: 8 de noviembre de 2026.

Versión de implementación: `1.0-32992c0f36e6`. El sufijo identifica el código incorporado; resultados de versiones diferentes no se mezclan ni se sobrescriben.

## Alcance y archivos

Se ha trabajado en [P2_1_alumnes.ipynb](P2_1_alumnes.ipynb), el único notebook coincidente existente. El nombre P2_1_alumnes_pytorch.ipynb indicado en la petición no existe en este directorio; no se ha inventado una segunda copia. El código final está contenido en el notebook, organizado en funciones y clases reutilizables, sin depender de un módulo Python nuevo.

Antes de programar se inspeccionaron las celdas reales de carga, tokenizer, padding, etiquetas, ejercicios 2–4 y enunciado del 5, así como los CSV que utiliza la práctica. Se respetaron PyTorch, pandas, NumPy y scikit-learn. SnowballStemmer de nltk y Matplotlib están instalados; Snowball no ha requerido descargar corpus.

Archivos entregados/modificados: el notebook, este documento y los artefactos reales de auditoría y smoke en results/ex5/. Los scripts de construcción y las copias de revisión son temporales y no forman parte de la entrega. No se han modificado los CSV ni otros enunciados.

## Cambios anteriores al ejercicio 5, limitados y señalizados

La numeración original cuenta todas las celdas desde 1, antes de esta implementación:

- Celda original 45, entrenamiento/evaluación del ejercicio 4: el bucle de evaluación utiliza val_loader en lugar de test_loader y la salida se identifica como Validation accuracy. La arquitectura y el entrenamiento se conservan.
- Celda original 47, visualización de errores: se cambian únicamente el loader, frases y etiquetas de test por los de validación.
- Cada sustitución conserva la línea original comentada y utiliza delimitadores #______________ antes y después. Una nota Markdown separada en catalán bajo la celda de entrenamiento explica por qué era imprescindible: ejecutar todo el notebook no debe consultar test antes de la selección final del 5.
- El resto de fuentes de los ejercicios 1–4 y todo el Markdown original se conserva. Las salidas se regeneraron en la comprobación completa; los contadores de ejecución reflejan esa ejecución.

Se añaden 11 celdas de código para el 5, sus títulos, una introducción, la nota anterior y una metodología final. Las posiciones actuales son:

| Celda actual | Contenido |
|---:|---|
| 52 | Tickets 1-2: protocol, configuration and preprocessing |
| 54 | Ticket 3: interchangeable neural architectures |
| 56 | Ticket 4: common training and evaluation |
| 58 | Ticket 5: persistent records, equivalence detection and exact resume |
| 60 | Tickets 6-10: declarative, sequential one-factor comparisons |
| 62 | Tickets 11-12: evidence-based tables and figures |
| 64 | Ticket 11: sealed, explicit and single final test evaluation |
| 66 | Ticket 13: genuine small smoke tests, isolated from actual test |
| 68 | Execute only smoke checks (small subsets, at most two epochs) |
| 70 | Explicit FULL launch: disabled during implementation |
| 72 | Separate, one-time final test: disabled until selection has been frozen |

## Estado de los tickets

| Ticket | Implementación | Validación o ejecución |
|---:|---|---|
| 1 | Auditoría, IDs originales, distribuciones, clases ausentes y política de exclusión. | Datos reales comprobados; limitación de textos repetidos documentada. |
| 2 | Preprocessing configurable, PAD/UNK, longitudes, vacíos y caché. | Smoke de OOV, stemming, números, stopwords, cuatro presupuestos de vocabulario y límites. |
| 3 | Feedforward, CNN y recurrentes con interfaz IDs/longitudes → logits. | 14 variantes forward/backward en CPU, máscaras y dimensiones verificadas. |
| 4 | Entrenador único, métricas, pérdida correcta, early stopping y restauración. | Entrenamientos pequeños reales, restauración y evaluación sin modificar parámetros. |
| 5 | Identidad estable, JSON/CSV/checkpoints, equivalencias y reanudación. | Guardado/carga real; reanudación y equivalencias sin reentrenar comprobadas. |
| 6 | Vocabulario, lowercase, stemming y embedding con un factor cada vez. | Configuraciones declaradas; batería definitiva pendiente. |
| 7 | Kernels CNN 2/3/5, max/average y segunda convolución opcional. | Forward/backward y padding probados; comparación definitiva pendiente. |
| 8 | Seis recurrentes iniciales y comparación posterior hidden 64/128. | Seis variantes probadas; selección definitiva pendiente. |
| 9 | Dropout 0/0.2/0.4 en CNN y recurrente seleccionados por validation. | Configuraciones y exportación de curvas preparadas; comparación pendiente. |
| 10 | Pesos N/(C*count), recall, soporte por clase y comparación controlada. | Pesos/orden verificados, entrenamiento ponderado pequeño y gráficos reales smoke. |
| 11 | Selección por validation, tres semillas y test final bloqueado. | Guards y carga del checkpoint probados; repeticiones definitivas/test no ejecutados. |
| 12 | Tablas, gráficos y material Markdown para informe. | PNG/CSV smoke reales exportados; gráficos definitivos se generarán con full. |
| 13 | Smoke de arquitectura, entrenamiento, determinismo, guardado y no acceso a test. | Passed; ejecución del notebook en orden sin errores. |

«Implementado» describe el código disponible; no implica que se hayan ejecutado los experimentos definitivos. No se ha ejecutado full ni se han inventado resultados de comparación.

## Ticket 1: datos y evaluación

train.csv contiene 4978 filas. La práctica utiliza las primeras 4078 para train y las últimas 900 para validation; test.csv contiene 893. Se conservan las columnas originales 0 (texto) y 2 (intención), comprobadas antes de crear los nombres internos text, label y source_id.

Los IDs originales incluyen el nombre del CSV y su índice de fila. Train y validation son disjuntos en IDs; test tiene su propio espacio de IDs. Las etiquetas se limpian exactamente como en la práctica, conservando cada cadena compuesta como una clase única. No se reordenan componentes ni se inventan etiquetas. LabelEncoder y el número de clases se verifican frente a las 22 clases de train.

La política original excluye day_name, airfare+flight, flight+airline y flight_no+airline en validation/test. En los datos actuales no se elimina ninguna fila de validation y se excluyen cinco de test: day_name (2) y una de cada una de las otras tres etiquetas. Son clases que no aparecen en train. Todo filtrado actúa sobre filas completas y conserva sus IDs: textos y etiquetas nunca se filtran de forma independiente.

Tamaños utilizados: `{'train': 4078, 'val': 900, 'test': 888}`. La evaluación final de test corresponderá a 888 ejemplos de clases conocidas, no a los 893 originales. Los mismos IDs se mantienen en todos los experimentos del protocolo elegido.

Distribuciones reales antes de la exclusión:

| Etiqueta | Train | Validation | Test original |
|---|---:|---:|---:|
| abbreviation | 120 | 27 | 33 |
| aircraft | 68 | 13 | 9 |
| aircraft+flight+flight_no | 1 | 0 | 0 |
| airfare | 333 | 90 | 48 |
| airfare+flight | 0 | 0 | 1 |
| airfare+flight_time | 1 | 0 | 0 |
| airline | 125 | 32 | 38 |
| airline+flight_no | 2 | 0 | 0 |
| airport | 14 | 6 | 18 |
| capacity | 13 | 3 | 21 |
| cheapest | 1 | 0 | 0 |
| city | 16 | 3 | 6 |
| day_name | 0 | 0 | 2 |
| distance | 15 | 5 | 10 |
| flight | 3023 | 643 | 632 |
| flight+airfare | 15 | 6 | 12 |
| flight+airline | 0 | 0 | 1 |
| flight_no | 11 | 1 | 8 |
| flight_no+airline | 0 | 0 | 1 |
| flight_time | 46 | 8 | 1 |
| ground_fare | 15 | 3 | 7 |
| ground_service | 203 | 52 | 36 |
| ground_service+ground_fare | 1 | 0 | 0 |
| meal | 3 | 3 | 6 |
| quantity | 50 | 1 | 3 |
| restriction | 2 | 4 | 0 |

Clases de train ausentes en cada partición retenida:

- train: ninguna.
- val: aircraft+flight+flight_no, airfare+flight_time, airline+flight_no, cheapest, ground_service+ground_fare.
- test: aircraft+flight+flight_no, airfare+flight_time, airline+flight_no, cheapest, ground_service+ground_fare, restriction.

El idioma se confirmó por inspección de las oraciones reales: inglés. Los tres conjuntos no contienen oraciones con mayúsculas ni textos vacíos en esta versión. El pipeline, no obstante, contempla ambos casos.

### Solapamiento textual: limitación relevante

Hay **93 textos distintos compartidos entre train y validation**, que afectan a **104 filas de validation**, pese a que las filas originales son disjuntas. Train y test comparten **10 textos distintos**.

Por decisión explícita del usuario, se conserva la partición original de la práctica y se documenta el solapamiento textual como limitación. El protocolo queda fijado con EX5_DEDUPLICATE_VALIDATION=False para todos los experimentos; no se excluyen las 104 filas de validation que comparten texto con train. Se mantienen 4078 ejemplos de entrenamiento, 900 de validación y 888 de test tras la exclusión original de etiquetas desconocidas. La opción de deduplicación disponible en el código no se utilizará en esta batería ni se mezclarán resultados de protocolos diferentes.

No hay ajuste del tokenizer con validation/test, gradientes de validation ni selección por test. Sin embargo, **no puede afirmarse independencia textual completa ni ausencia absoluta de contaminación del corpus si se conserva la partición original**. El solapamiento de test se documenta sin utilizar sus textos para modificar train ni seleccionar modelos. Además, el test ya había sido observado históricamente en los ejercicios anteriores; esta implementación evita nuevos accesos durante la búsqueda, pero no puede deshacer ese antecedente.

Los registros de auditoría en results/ex5/audit/ guardan distribuciones, exclusiones y los IDs exactos retenidos. Su identidad incluye datos y versión de implementación, evitando sustituir auditorías previas.

## Ticket 2: preprocessing y baseline

Ex5Preprocessing permite vocab_size, lowercase, stemming y max_sequence_length. El presupuesto vocab_size incluye PAD=0 y UNK=1; las palabras empiezan en 2 y la matriz embedding usa el máximo ID real más uno. El vocabulario se aprende solo con train y se ordena por frecuencia con desempate por primera aparición.

Se conserva el patrón de tokenización por palabras de la práctica. Los desconocidos se convierten en 1 y no se descartan. No se eliminan stopwords ni números. Snowball para inglés no se combina con lematización; Snowball normaliza internamente palabras y el contraste de stemming mantiene lowercase=True.

La longitud máxima por defecto se aprende solo con train. Se trunca por el final y se añade padding post. Se guardan raw_lengths antes del truncamiento/padding y lengths efectivas; una entrada vacía mantiene raw_length=0 y recibe un UNK de longitud efectiva 1. Los modelos también aceptan casos sintéticos de longitud cero sin logits infinitos.

El tokenizador original de los ejercicios previos descarta OOV y ya convierte a minúsculas; se conserva allí. El nuevo baseline feedforward del ejercicio 5 aplica una política OOV correcta común a todos los modelos. Por tanto, la diferencia respecto al ejercicio 4 no debe atribuirse a un único hiperparámetro.

Los datos reales ya están en minúsculas. Una configuración sin lowercase que produce los mismos tensores y dimensiones se registra como equivalencia, con source_experiment_id, sin afirmar un entrenamiento nuevo. Se reutilizan los pesos, pero al cargar una configuración equivalente se reconstruye su propio preprocessing exclusivamente con train: no se sustituye silenciosamente por el del experimento fuente.

La caché incorpora dataset/protocolo, configuración, modo y tamaños smoke. Solo prepara train/validation durante la búsqueda. El test del pipeline 5 se transforma por primera vez en la función final, con el vocabulario del checkpoint seleccionado.

## Tickets 3–4: modelos y entrenamiento

- build_model(config, vocab_size, num_classes) construye feedforward, CNN o recurrente; todos aceptan ids y lengths y producen logits (batch, num_classes), sin Softmax final.
- Feedforward: embedding con padding_idx=0, max sobre posiciones no PAD, Linear/ReLU, dropout opcional y Linear final. El caso solo PAD produce una representación agregada cero.
- CNN: Conv1d recibe (batch, embedding, length). Kernels 2/3/5, 64 filtros por defecto y una o dos capas. Solo se permiten ventanas completas; las parciales que cruzan padding/bordes se excluyen. Si no cabe una ventana completa se devuelve representación cero. El max aplica máscara sin máximos artificiales; AdaptiveAvgPool1d(1) promedia valores finitos enmascarados a cero y se renormaliza por el número de ventanas válidas.
- LSTM/GRU: pack_padded_sequence con longitudes reales. Sin atención se utiliza h_n; en bidireccional se concatenan los estados finales de ambas direcciones de la última capa. La atención escalar aplica máscara antes de Softmax y suma ponderada de estados válidos. No se introduce Transformer ni multi-head attention.
- Dropout explícito después de la representación agregada y antes del clasificador; no se confía en el argumento dropout de un RNN de una sola capa.

Defaults de entrenamiento: Adam, lr=0.001, batch_size=32, máximo 25 épocas, patience=4 y seed=42. Todo es configurable. Se fija Python/NumPy/PyTorch, cuDNN y algoritmos deterministas. Los loaders usan num_workers=0 y un generador de barajado con semilla; CPU/GPU se selecciona explícitamente o con auto.

train_model recibe solo train_loader y val_loader. Registra train loss/accuracy y validation loss/accuracy/macro-F1. La loss se acumula por numeradores y denominadores: CE ponderada divide por la suma de los pesos de los targets, reproduciendo la reducción de PyTorch, y CE no ponderada por el número de ejemplos.

La selección del checkpoint utiliza siempre **validation CE sin pesos**, incluso si train utiliza pesos. Así el criterio es idéntico entre configuraciones. Se guardan los mejores pesos en CPU y se restauran antes de la evaluación final de validation. Se libera el modelo entre experimentos y se limpia la caché CUDA cuando existe GPU.

Macro-F1, recall y matrices usan el conjunto fijo de 22 clases de train con zero_division=0. Las clases ausentes de validation contribuyen cero; su recall no permite concluir mejoras o perjuicios. Los análisis de minoritarias excluyen clases sin soporte de validación.

## Ticket 5: registros y reanudación

Cada configuración tiene un ID estable derivado de configuración completa, semilla, modo, versión de código, identidad de train/validation y entorno. Las identidades y resultados JSON son inmutables: se reutiliza contenido idéntico y se rechaza sustituir contenido diferente. Los reintentos incompletos usan un nuevo attempt-UUID sin sobrescribir intentos previos. Si se modifican las funciones del pipeline, debe actualizarse EX5_VERSION antes de reutilizar resultados; cambiar una configuración declarativa ya cambia su identidad automáticamente.

Estructura:

```text
results/ex5/
  audit/                         # IDs, tamaños y distribuciones reales
  smoke/experiments/<id>/       # Pruebas pequeñas, separadas de full
  full/experiments/<id>/
    config.json                  # Configuración, datos, versión y entorno
    result.json                  # Métricas del mejor checkpoint
    attempt-<id>/best.pt          # Solo el mejor checkpoint, no cada época
    attempt-<id>/history.csv
    attempt-<id>/summary.csv
  <modo>/tables/                # Comparaciones, finalistas y material Markdown
  <modo>/figures/               # PNG calculados, con ID de contenido
  full/selections/              # Decisión congelada usando validation
  full/final_test_once.json     # Bloqueo y resultado de la evaluación única
  full/final_test/              # Métricas, predicciones y matriz finales
```

Al repetir la misma configuración completada se leen los resultados, sin entrenar ni modificar el checkpoint. Las equivalencias se identifican por tensores efectivos y configuración de modelo/entrenamiento; mantienen el tiempo original de entrenamiento y muestran incremental_training_seconds=0. No se cuentan como nuevos entrenamientos. Cada configuración conserva su propio JSON y la referencia al origen de los pesos.

## Tickets 6–10: plan controlado preparado

1. Vocabulario 250/500/1000/2000 con feedforward, embedding 64 y demás variables fijas.
2. Lowercase True/False con referencia vocabulario 500 y embedding 64; los no-op se identifican como tales.
3. Stemming False/True con el mismo resto de parámetros.
4. Embedding 32/64/128 con referencia vocabulario 500.
5. Selección de una configuración realmente observada por validation. La combinación de ganadores individuales solo se prueba si include_combination=True, etiquetada como experimento adicional; no se supone que sume mejoras.
6. Con preprocessing/embedding comunes, CNN k=2/3/5 con 64 filtros y max. Después se prueba el mejor kernel con average; la segunda convolución solo si include_second_convolution=True.
7. Con ese mismo preprocessing/embedding, LSTM, BiLSTM, GRU, BiGRU, LSTM+atención y BiLSTM+atención; hidden=128, una capa y dropout=0. No se añade inicialmente GRU+atención. Después se compara hidden=64/128 en el recurrente elegido.
8. CNN y recurrente prometedores: dropout 0.0/0.2/0.4 con todo lo demás fijo y curvas por configuración.
9. Mejor configuración observada: sin/con pesos de clase, conservando las demás variables.

Los pesos se calculan exclusivamente con train: N/(C*count). Se verifica count>0 para las 22 clases y se usa exactamente el orden de LabelEncoder. La tabla mostrada incluye class_id, etiqueta, frecuencia absoluta/relativa y peso. En smoke se usan estos pesos de train para probar la rama ponderada; sus resultados no constituyen una comparación definitiva.

El análisis automático de pesos guarda recall por clase y su diferencia ponderado menos no ponderado. Define minoritarias como count<=mediana de train y frecuentes como count>=percentil 75, siempre con soporte de validación. No afirma beneficio si los deltas reales no lo apoyan; si no hay soporte, registra null, no una mejora ficticia.

## Tickets 11–12: selección, test y gráficos

La tabla DataFrame se puede ordenar por cualquier columna mediante ex5_sort_table(table, by=..., ascending=...). Incluye ID, familia/arquitectura, preprocessing, vocabulario presupuestado/real, embedding, hidden, kernel, pooling, bidireccionalidad, atención, dropout, pesos, validation accuracy/macro-F1/loss, mejor época, parámetros, tiempo, semilla, modo y equivalencias.

Se selecciona por validation accuracy; macro-F1 es secundario y validation loss sirve de desempatador posterior. Cada entrenamiento ya restauró el checkpoint de menor validation loss. Se elige como máximo un candidato por familia y se repite con 42/123/2026. Se guardan media y desviación estándar muestral de accuracy y macro-F1. La familia final se decide por esas medias de validación; dentro de ella se utiliza seed=42, fijada de antemano, sin seleccionar retrospectivamente la mejor semilla con test.

La selección se guarda con el ID de experimento y SHA-256 del checkpoint. evaluate_final_test exige confirm=True, una selección previamente congelada y el checkpoint full de semilla 42. Un bloqueo exclusivo impide evaluar otra selección después de observar test. Si la misma evaluación ya terminó, se devuelve su registro sin volver a inferir. Si quedó interrumpida, se exige inspeccionar el registro; no se borra automáticamente para repetirla.

La función final guardará test accuracy/macro-F1/recall, predicciones con source_id, matriz CSV y PNG con ejes de clases. Actualmente no se ha ejecutado.

Las funciones de material exportan comparaciones de vocabulario/embedding, CNN/recurrentes, dropout, pesos, recall por clase, curvas train/validation, tabla de mejores modelos y observaciones Markdown derivadas exclusivamente de resultados reales. No se dibujan datos faltantes. Los PNG utilizan FigureCanvasAgg: la primera prueba detectó que Tk/Tcl no funcionaba en este entorno y se eliminó esa dependencia de interfaz gráfica.

La metodología al final del notebook explica los gráficos, las limitaciones y una distribución sugerida de 10 páginas para el PDF. No se ha generado un informe con conclusiones sobre modelos aún no entrenados.

## Cómo ejecutar

1. Reiniciar el kernel y ejecutar en orden. Los defaults ejecutan únicamente smoke en el ejercicio 5.
2. Para los experimentos definitivos, fijar el protocolo de particiones; poner EX5_MODE="full" para omitir smoke y RUN_FULL_EX5=True en su celda explícita. Ejecutarla cuando corresponda. No hace falta modificar el entrenador para añadir configuraciones.
3. Esperar la batería, revisar tablas, gráficos, medias de semillas y selección congelada. No consultar test para ajustar decisiones.
4. Solo entonces activar RUN_FINAL_TEST=True en la celda separada. La evaluación queda registrada y no se vuelve a utilizar para modificar el modelo.
5. Dejar los interruptores en False al compartir una copia que no deba lanzar entrenamientos automáticamente.

## Comprobaciones realmente ejecutadas

Se ejecutaron las **28 celdas de código del notebook en orden desde una sesión IPython nueva**, incluida la preparación y el ejercicio 4 ahora sobre validation. No hay excepciones ni salidas stderr en el notebook guardado. El modo full y el test final permanecieron desactivados.

Entorno: Python 3.13.0, CPU. Versiones: {'torch': '2.12.1', 'numpy': '2.2.4', 'pandas': '2.3.3', 'scikit-learn': '1.7.2', 'nltk': '3.9.2'}. No se ha probado GPU.

Smoke persistido: **4 entrenamientos pequeños** — feedforward, CNN, BiLSTM con atención y feedforward ponderado — con **96 ejemplos de train y 48 de validation**, máximo dos épocas. Hay además entrenamientos auxiliares pequeños en memoria para restauración/reproducibilidad y un registro de equivalencia sin entrenamiento adicional. Son pruebas de funcionamiento, no resultados finales de la práctica.

1. 14 architectures: finite forward/backward, correct logits, PAD gradient zero and padding invariance.
2. Negative embeddings cannot be replaced by artificial padding maxima.
3. Empty input, UNK=1, PAD=0, reserved indices and real lengths checked.
4. Weighted CE numerators/denominators and class-index ordering checked.
5. Early stopping restores epoch-1 weights in a controlled real run; evaluation leaves parameters unchanged.
6. Two independent CPU trainings with seed 42 produce identical histories and checkpoints.
7. Real smoke runs saved/reloaded/resumed, no-op configuration reused without retraining, checkpoint loaded, real plots exported, actual test sealed throughout.

También se comprobó Snowball inglés, conservación de números/stopwords, límites 250/500/1000/2000 y que transformar datos no modifica el vocabulario. El test real se sustituyó temporalmente por un objeto que lanza excepción si se accede durante los smoke de búsqueda: no se produjo ningún acceso. No se ha creado un directorio full/experiments ni un registro final de test.

Artefactos de los cuatro smoke de esta versión:

- [Experimento dffdf900814c64f9b571](results/ex5/smoke/experiments/dffdf900814c64f9b571/result.json).
- [Experimento 886305fc93b45367d13d](results/ex5/smoke/experiments/886305fc93b45367d13d/result.json).
- [Experimento dbfb74b0c81981982747](results/ex5/smoke/experiments/dbfb74b0c81981982747/result.json).
- [Experimento a2c9c36810ebfad227b9](results/ex5/smoke/experiments/a2c9c36810ebfad227b9/result.json).

Tabla smoke: [comparison_7a5c235fcafe3872.csv](results/ex5/smoke/tables/comparison_7a5c235fcafe3872.csv).

Gráfico smoke real: [comprobación de ejecución](results/ex5/smoke/figures/execution_check_b22ebc6d06b8abf8.png).

Los registros de versiones preliminares, si están presentes, se conservan; ex5_all_results filtra por identidad de datos, versión y entorno. No deben mezclarse con la versión final ni con modo full.

## Pendiente de ejecución real

- Toda la batería definitiva de preprocessing, embeddings, CNN, recurrentes, hidden, dropout y pesos.
- Repeticiones de candidatos con las tres semillas y selección final sobre validation.
- Única evaluación final de test y su matriz de confusión.
- Conclusiones académicas y gráficos definitivos basados en esos experimentos.
- Validación en GPU, si se dispone de ella. El código ofrece soporte; no se afirma haberlo probado.

La implementación satisface la separación de entrenamiento, validación y evaluación final del nuevo proceso. La independencia textual completa del corpus original sigue siendo una limitación explícita; no se presenta como un requisito ya resuelto.
