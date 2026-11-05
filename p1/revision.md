# Revisión del código — Práctica 1 (para la entrevista)

Leyenda de cada función: **[No tocar]** = lógica central o probada por el oráculo; cambiarla rompe tests o el
comportamiento. **[Modificable]** = punto previsto para ajustes, con *cómo* hacerlo. Las funciones que empiezan
por `_` son auxiliares internas: se agrupan y casi nunca hay que tocarlas.

Regla general en ambos sistemas: **los textos y datos se cambian en el JSON / `lexicon.py` / `prompts.py` /
`config.py`, no en la lógica.** Después de cualquier cambio: `python -m recomanador.tests.run_all` y
`python -m recomanador_llm.tests.run_all` (no necesitan GPU).

---

## 1. Sistema 1: recomendador basado en reglas (`recomanador/`)

### Cómo funciona (conceptual)

- **Diálogo dirigido por el sistema**: hace las preguntas del JSON en orden (operación → precio → zona → resto),
  saltando las que no aplican (`ask_if`: habitaciones no en oficinas, jardín solo en casa/chalet…).
- **Comprensión por reglas (gramática semántica)**: normaliza el texto y busca sinónimos EN/ES/CA por pregunta;
  negación (3 palabras antes), exclusiones ("todo menos X"), erratas (similitud ≥ 0,83), ambigüedad → pregunta.
- **Números**: "1,5k", "dos mil quinientos", rangos, mínimo/máximo/aprox.; sin modificador, precio = máximo y
  resto = mínimo; en compra "250" = 250.000 €; sumas de habitaciones con confirmación.
- **Reacción según confianza** (Tabla 2 del informe): aceptar, confirmar implícita/explícitamente, aclarar, avisar
  de valores poco plausibles, explicar + ayuda y, al 3.er fallo, ofrecer saltar.
- **Contador**: tras cada respuesta recalcula cuántas viviendas quedan; si una respuesta dejaría 0, avisa antes.
- **Iniciativa del usuario**: `show me` (resultados ya), `help`, `quit` (con confirmación) y correcciones
  ("change the budget to 900", "actually, Gràcia", "back").
- **Iteración 4**: bajo cada pregunta, opciones o rango que aún encajan con el resto de respuestas.
- **Resultados**: alquiler y luego venta, de barato a caro; si no hay ninguno, "casi coincidencias" (≤ 2 criterios
  fallados, nunca se relaja alquiler/compra); exploración (`all`, `next`, `prev`, número) y ficha en lenguaje natural.

### Arquitectura modular y coordinación

```
Notebook → run() [dialogue_manager]
            ├─ data_loader → JSON (preguntas, textos, viviendas)
            ├─ por cada pregunta: nlg.print_question + print_availability
            │     → ask() lee la respuesta (io_adapter) → corrections.detect (¿es una corrección?)
            │     → nlu.analyse / numeric.parse (comprensión) → reacción (nlg) → check_matches (recommender)
            │     → se guarda en DialogueState (state.py) → contador (recommender.count_matches)
            └─ show_results → recommender.find_suitable_houses / near_misses / rank_houses → nlg → explore_results
```

- **DM** (`dialogue_manager.py`) es el único que decide; NLU/numeric solo interpretan, NLG solo redacta,
  recommender solo filtra.
- El flujo se controla con **excepciones**: `ExitConversation` (salir), `ShowResults` (ir a resultados) y
  `Correction` (volver a una pregunta). Por eso el bucle siempre pide "la siguiente pregunta aplicable sin
  responder".
- **IO inyectable**: `ConsoleIO` (consola real) o `ScriptedIO` (tests con respuestas predefinidas).

### `__init__.py`
- Exporta `run`. **[No tocar]**.

### `config.py` — parámetros (todo **[Modificable]**, es su función)
- `DATA_PATH`: JSON de datos. `EXIT_COMMANDS`, `HELP_COMMANDS`, `RESULTS_COMMANDS`: palabras de cada orden.
- `FUZZY_CUTOFF` (0,83) y `FUZZY_MIN_LENGTH`: tolerancia a erratas (subir = más estricto). `NEGATION_WINDOW` (3).
- `DEFAULT_NUMERIC_MODE` (precio = max, resto = min), `APPROX_MARGINS` (margen de "around"), `INTEGER_KEYS`,
  `ROOM_SUM_KEYS`, `SALE_THOUSANDS_BELOW` / `PURCHASE_SCALE_FROM` ("250" en compra = 250.000).
- `MULTI_SELECT_KEYS` (preguntas con varias opciones), `YES_ONLY_FILTERS` (sí/no que solo filtran con "sí"),
  `OPT_IN_FILTERS` (compartir).
- `OFFER_SKIP_AFTER` (fallos antes de ofrecer saltar), `FEW_MATCHES` (pista de `show me`),
  `NEAR_MISS_MAX_FAILURES` / `NEAR_MISS_LIMIT` / `NON_RELAXABLE`, `ZONES_EXCEPT_MAX`, `USE_COLORS`.
- Cómo: cambiar el valor y pasar los tests (algunos comprueban valores concretos, p. ej. el umbral de erratas).

### `state.py` — estado de la conversación
- `DialogueState`: `preferences` (respuestas), `answer_order` (para `back`), `match_history` (contador),
  `reached`, `stopped_early`, `exited`, `show_me_hinted`. **[No tocar]** salvo para añadir un campo nuevo.

### `data_loader.py`
- `load_data(path)`: lee el JSON. **[No tocar]**.

### `io_adapter.py` — entrada/salida
- `ConsoleIO`: `ask` (input), `say(text, kind)` (print con formato según la función de la línia), `clear`
  (borra solo en Colab), `_paint`/`_format`. **[Modificable]**: colores y estilos en `STYLES`, ancho en `WIDTH`.
- `ScriptedIO`: `ask` devuelve respuestas de una lista, `say` guarda el texto, `text()` lo devuelve. Para tests.
  **[No tocar]**.

### `lexicon.py` — recursos lingüísticos (todo **[Modificable]**, es donde se amplía el lenguaje)
- `SYNONYMS` (por pregunta y valor), `LOCATIONS`/`CITIES`/`ZONES` (barrios, ciudades, 7 áreas), `YES_NO`,
  `ANY_PHRASES`, `NEGATIONS`, `EXCLUSION_MARKERS`, palabras numéricas (`NUMBER_WORDS`, `HUNDRED_WORDS`…),
  modificadores y rangos (`NUMERIC_MODIFIERS`, `RANGE_*`), sumas (`SUM_CONNECTORS`, `ROOM_*`), correcciones
  (`CHANGE_MARKERS`, `CORRECTION_MARKERS`, `BACK_COMMANDS`, `SLOT_NAMES`), resultados (`RESULTS_ALL/NEXT/PREV`).
- Cómo: añadir la forma a la lista que toca (en minúsculas o con acentos, se normaliza sola). Ej.: nuevo
  sinónimo de "piso" → `SYNONYMS["property_type"]["flat"]`. Pasar tests (comprueban que no hay cruces).

### `nlu.py` — comprensión de opciones
- `fold(text)` / `normalize(text)`: minúsculas, sin acentos, contracciones; `|` como límite de cláusula. **[No tocar]**
  (el léxico se normaliza igual; si cambia, dejan de coincidir).
- `is_exit`, `is_help`, `is_show_results`, `is_any`, `has_exclusion`: detectan órdenes. **[Modificable]** vía
  `config`/`lexicon`, no aquí.
- `build_vocabulary(key, options, houses)`: forma normalizada → valores canónicos de una pregunta. **[No tocar]**.
- `analyse(vocabulary, answer, multiple)`: devuelve `Interpretation` (valor, candidatos si ambiguo, aproximado,
  literal). Núcleo. **[No tocar]**.
- `interpret(...)`: solo el valor (o None). `restrict(vocabulary, values)`: vocabulario reducido para aclarar.
  **[No tocar]**.
- Auxiliares `_find`, `_negated`, `_drop_contained` (gana la coincidencia más larga), `_exact_matches`,
  `_fuzzy_matches` (erratas), `_match`, `_matched_values`, `_with_exclusion`, `_exclusion_split`, `_zone_members`.
  **[No tocar]**; los umbrales están en `config`.

### `numeric.py` — comprensión de números
- `Range` (min/max, `in`), `NumericAnswer`, `Quantity`: estructuras. **[No tocar]**.
- `parse(answer, key, house_type)`: texto → rango (con modo, sumas, confirmación necesaria). Núcleo. **[No tocar]**.
- `operation_for(range)`: con operación "any", deduce compra/alquiler por la escala. **[Modificable]** vía
  `PURCHASE_SCALE_FROM`.
- Auxiliares: `_parse_digits` ("10.000", "1,5"), `_parse_words` ("dos mil"), `_quantities`, `_prefix_mode` /
  `_postfix_mode` (mínimo, máximo, aprox.), `_bound`, `_explicit_range` ("entre x y z"), `_chains` (sumas),
  `_negated`, `_attachment`, `_for_sale`, etc. **[No tocar]**; palabras nuevas → `lexicon.py`.

### `corrections.py` — correcciones
- `Correction(kind, …)`: tipos `back`, `change`, `value`, `unclear`, `not_yet`, `nothing_back`. **[No tocar]**.
- `detect(data, preferences, answer_order, question, answer, vocabularies)`: ¿la respuesta corrige otra anterior?
  Requiere marcador explícito ("change", "actually", "back"). **[No tocar]**; marcadores en `lexicon`.
- `strip_marker(answer)`: "actually, Gràcia" → "gracia". Auxiliares `_tokens`, `_find_slot`, `_after_marker`,
  `_strip_fillers`. **[No tocar]**.

### `recommender.py` — filtrado (backend)
- `satisfies(house, key, value)`: ¿cumple un criterio? **[Modificable]** solo si se añade un tipo de criterio nuevo.
- `find_suitable_houses`, `count_matches`, `failed_criteria`: filtrar / contar / qué falla. **[No tocar]** (el
  oráculo de los tests compara contra ellas).
- `near_misses(data, prefs)`: casi coincidencias. **[Modificable]** vía `NEAR_MISS_*` y `NON_RELAXABLE`.
- `rank_houses(houses)`: orden (alquiler → venta, barato → caro). **[Modificable]**: cambiar la clave de
  ordenación (tests de iteración 3 la comprueban).
- `value_range`, `to_number`, `initialize_available_options`: utilidades. **[No tocar]**.

### `nlg.py` — generación (plantillas, microplanificación y realización)
- Selección de frases: `VariedPicker` (al azar sin repetir la última), `first_choice` (tests), `configure`, `pick`.
  **[No tocar]**.
- Bienvenida/despedida/ayuda: `print_welcome`, `print_goodbye`, `question_help`, `print_help`, `_format_help`.
  **[Modificable]**: los textos están en el JSON (`start_message`, `instructions`, `help`…).
- Preguntas: `question_text` (variantes y `question_if`), `print_question`, `slot_name`. **[Modificable]** en el JSON.
- Iteración 4: `print_available_zones` (microplanificación de zonas: agrupar por ciudad, "except…"),
  `print_available_values` (opciones/rango bajo la pregunta), `location_option_lines`. **[Modificable]**: textos
  `zones_*` en el JSON; para mostrar opciones en otra pregunta, añadir un `elif key == ...` en
  `print_available_values`.
- Contador: `count_text`, `print_count_start`, `print_count_update`. Textos en JSON (`reactions.count_*`).
- Reacciones: `reaction`, `react`, `react_to_answer` (comentario del valor, confirmación implícita o acuse),
  `REACTION_KINDS` (estilo de cada reacción). **[Modificable]**: frases en `reactions`/`comments` del JSON.
- Descripciones: `describe_range` ("at least 3 bedrooms"), `describe_value`, `describe_options`,
  `describe_answer`, `format_number`, `sum_confirmation`, `_join`, `_compress_cities`. **[No tocar]**.
- Microplanificación: `summarize` (todas las preferencias en una frase), `print_recap`. **[No tocar]** la lógica;
  plantillas en JSON (`summary`).
- Realización: `describe_house` (ficha en párrafo de 4 frases), `print_house`, `price_text`, `house_line`,
  `_failed_text`, `_ordinal`, `_count`. **[Modificable]** con cuidado: el orden de las frases está aquí.
- Resultados: `print_results_overview`, `_print_lines`, `print_results_list`, `print_result`, `print_all_results`.
  Textos en JSON (`results`).

### `dialogue_manager.py` — gestor del diálogo (decide todo)
- `run(data_path, io, picker)`: conversación completa (bienvenida → preguntas → resultados → despedida).
  Punto de entrada. **[No tocar]**.
- `question_loop(...)`: bucle "siguiente pregunta aplicable", aplica correcciones. `next_question`,
  `is_applicable` (`ask_if`). **[No tocar]**; el orden y las condiciones se cambian en el JSON.
- `ask(io, data, prompt, …)`: lee respuesta y gestiona órdenes (`quit` con confirmación, `help`, `show me`,
  correcciones). `confirm` (sí/no). **[No tocar]**.
- `ask_and_store(...)`: preguntar → comprobar 0 viviendas → guardar → contador. `with_answer` (borra respuestas
  que dejan de aplicar). **[No tocar]**.
- Opciones: `process_choice`, `clarify_choice` (ambigüedad), `accept`, `not_understood` (ayuda progresiva).
  **[No tocar]**; textos en JSON, `OFFER_SKIP_AFTER` en config.
- Números: `process_number`, `ask_number`, `choose_operation` (presupuesto con operación "any"),
  `check_anomalies` (poco plausible), `available_range`. **[No tocar]**.
- Contador y 0 viviendas: `check_matches`, `out_of_range_message`, `confirm_change`, `valid_answer`. **[No tocar]**.
- Iteración 4: `current_matches_for_question` (viviendas que encajan sin la pregunta actual),
  `print_availability` (las muestra; también tras "let's try again"). **[Modificable]**: dónde se llama.
- Correcciones: `handle_correction`, `PrefilledIO` (inyecta el valor dicho en la corrección), `interpret_change`.
  **[No tocar]**.
- Resultados: `show_results`, `explore_results` (`all`/`next`/`prev`/número/cambios), `_house_id`. **[No tocar]**.
- `process_question`: despacha a opción o número. **[No tocar]**.

### Datos: `house_data_v2.json` y `tools/generate_houses.py`
- JSON: `questions` (texto, `answer_key`, `type`, `ask_if`, `depends_on`, `expects`, ayudas), textos
  (`start_message`, `reactions`, `comments`, `summary`, `results`, `end_message`) y `houses`. **[Modificable]**:
  es donde se cambian preguntas, orden y frases sin tocar código.
- `generate_houses.py`: genera las viviendas 27–50 (semilla 7, cuotas, log-normal, Bernoulli). **[Modificable]**
  (`SLOTS`, `ZONES` con €/m²); reejecutar cambia los datos y los resultados de la batería del sistema 2.

---

## 2. Sistema 2: chatbot con LLM y tools (`recomanador_llm/`)

### Cómo funciona (conceptual)

- **El LLM conversa; las reglas garantizan**: Qwen2.5-Coder-3B interpreta la petición y redacta; todos los datos
  salen de dos tools que reutilizan el sistema 1.
- **Turno**: mensaje → guardrail de entrada → modelo (puede pedir tools) → validación/anclaje de argumentos →
  tool → modelo redacta → guardrail de salida (reglas + juez LLM + idioma) → correcciones finales → respuesta.
- **Flujo**: bienvenida fija con datos reales; `help`; despedidas naturales y `exit` con resumen de la sesión.
  Si el cliente da criterios y el modelo no consulta la tool, se le obliga una vez.
- **Idioma**: detectado por turno (EN/ES/CA) y añadido al final del system prompt; las líneas de viviendas se
  traducen en el código.
- **Ante un problema**: una reformulación guiada; si persiste, respuesta fija según el caso, en el idioma del
  cliente.
- **Decodificación**: greedy para decidir llamadas; muestreo (T = 0,6, semilla del contenido) solo al redactar.

### Arquitectura modular y coordinación

```
chat() [chat.py]  ── bienvenida/ayuda/cierre [flow.py] ── registro JSONL
   └─ respond() [agent.py]  (un turno; máx. 5 llamadas al modelo)
        ├─ guardrails.check_input            (entrada)
        ├─ QwenModel(...)        [model.py]  (generar; score() para el juez)
        ├─ parse_tool_call → guardrails.ground_search_arguments / check_tool_call / ground_details_id
        ├─ tools.run_tool → search_homes / get_home_details   (usan recomanador: nlu, recommender, nlg)
        ├─ guardrails.expected_tool          (flujo: forzar consulta)
        ├─ guardrails.check_output → judge_scope → check_language   (salida)
        └─ guardrails.finalize / fallback_reply                      (correcciones / respuesta fija)
prompts.py: todos los textos · config.py: límites · version.py: huella del código
battery.py + evaluation.py: experimentos (sección 3)
```

- `agent.respond` es el orquestador; `guardrails` no llama al modelo salvo el juez; `tools` no conoce el modelo.
- Las indicaciones internas al modelo (`NUDGE_*`) van a una copia de trabajo y **no** se guardan en el historial.

### `__init__.py` / `__main__.py`
- `__init__`: exporta `QwenModel`, `chat`, `new_history`, `respond`; calcula la huella al importar. **[No tocar]**.
- `__main__.main()`: `python -m recomanador_llm [--verbose] [--model]`. **[Modificable]**: argumentos de terminal.

### `config.py` — límites (todo **[Modificable]**)
- `MODEL_NAME`, `MAX_NEW_TOKENS` (512), `COMPOSE_TEMPERATURE`/`COMPOSE_TOP_P` (0,6/0,9), `MAX_MODEL_CALLS` (5),
  `MAX_TOOL_CALLS` (3), `MAX_REGENERATIONS` (1), `RESULTS_PER_PAGE` (3), `MAX_INPUT_CHARS` (1000),
  `MAX_TOOL_OUTPUT_CHARS`, `MAX_ANSWER_WORDS` (200), `JUDGE_THRESHOLD` (0,7, calibrado), `JUDGE_MAX_*`,
  `LANGUAGE_HINT_POSITION` ("system"; "after_user" = ablación), `LOG_TO_FILE`/`LOG_DIR`, `EXIT_COMMANDS`.
- Ojo: cambiar `JUDGE_THRESHOLD` o `RESULTS_PER_PAGE` cambia los resultados de la batería; repetirla.

### `model.py`
- `QwenModel(model, tokenizer)` o `QwenModel(name=...)`: reutiliza el modelo cargado en el notebook.
- `__call__(messages, tools, max_new_tokens, sample)`: genera con la plantilla de Qwen; `last_finish` indica si
  se cortó por longitud. **[No tocar]** (parámetros en `config`).
- `score(messages, options)`: probabilidad de "YES"/"NO" como primer token (juez). **[No tocar]**.

### `prompts.py` — todos los textos (todo **[Modificable]**, con cuidado)
- `SYSTEM_PROMPT_TEMPLATE` (7 secciones) + `build_system_prompt(houses)` (rellena nº de anuncios y zonas);
  `BASE_SYSTEM_PROMPT` = el del notebook (para comparar, **[No tocar]**).
- `WELCOME`, `HELP`, `CLOSING`, `GIVE_UP`, `LINE_WORDS` (traducción de las líneas), `GUARD_REPLIES` (respuestas
  fijas por caso e idioma), `NUDGE_*` (indicaciones internas de reformulación), `LANGUAGE_HINT`,
  `JUDGE_SYSTEM`/`JUDGE_EXAMPLES`/`JUDGE_REPLY` (juez few-shot).
- Cómo: editar el texto. Si se toca el system prompt o los ejemplos del juez, **repetir la batería**: el
  comportamiento del modelo cambia (pasó con L03). La detección de fugas compara contra la plantilla.

### `tools.py` — las tools
- `TOOLS` (esquemas JSON), `_search_schema()`, `DETAILS_SCHEMA`: lo que ve el modelo. **[Modificable]**:
  descripciones de los argumentos.
- `search_homes(**args)`: busca con el sistema 1; devuelve resumen "Search: …", nº, 3 líneas, cuántas quedan y
  notas; si no hay, casi coincidencias. **[No tocar]** la lógica.
- `get_home_details(id)`: ficha del sistema 1 (`nlg.describe_house`). **[No tocar]**.
- `run_tool(name, arguments)`: valida (`check_tool_call`), ejecuta y sanea; nunca lanza excepciones.
  **[No tocar]**.
- `search_criteria(arguments)`: argumentos → preferencias del sistema 1. `_resolve` (valores con la NLU del
  sistema 1), `_number` ("400k", "1.200"), `_as_list`, `ArgumentError`. **[No tocar]**.
- `home_line(house, missing, language)`, `localize_line(line, language)`: línea "#18 · flat for rent…" y su
  traducción. **[Modificable]**: palabras en `prompts.LINE_WORDS`.
- `_notes(prefs, shown, total)`: notas para redactar (más barata, más grande, en común, qué falta).
  **[Modificable]**: qué hechos se dan al modelo.
- `NUMERIC`, `FEATURES`, `_EXTRAS`: mapa argumento ↔ campo de datos. **[Modificable]** para añadir criterios.
- `load_dataset`, `load_houses`, `_vocabulary`, `_values`, `_integer`. **[No tocar]**.

### `agent.py` — un turno
- `respond(model, history, user_text, log, events)`: orquesta todo el turno (ver diagrama). **[No tocar]**; los
  límites están en `config`.
- `parse_tool_call(text)`: reconoce `<tool_call>`, ```json o JSON a mitad del texto → `none`/`call`/`invalid`.
  **[No tocar]**.
- `_working_copy(history, language)`: historial + indicación de idioma (no se guarda). **[No tocar]**.
- `_Trace`: registra cada evento (intentos, capas, tiempos) para logs y evaluación. **[No tocar]**.

### `guardrails.py` — protecciones (el más grande)
- **Idioma**: `detect_language`, `turn_language`, `LANGUAGE_NAMES`. **[Modificable]**: palabras en `_LANGUAGE_WORDS`.
- **Entrada**: `check_input` (tokens de control, inyección/rol EN/ES/CA, discriminación, longitud) → `InputCheck`;
  `blocked_reply`. **[Modificable]**: patrones en `INJECTION_PATTERNS`, `DISCRIMINATION`, `CONTROL_TOKENS`
  (añadir una regex y un test con el caso).
- **Flujo**: `expected_tool` (¿debía consultar?), `_has_criteria`, `_wants_more`, `_asks_about_shown`,
  `_location_vocabulary`, `_vocabulary_for`. **[No tocar]**; palabras débiles en `_WEAK_WORDS`.
- **Ejecución**: `ground_search_arguments` ("validar, no sustituir": quita lo nunca dicho o negado, añade solo
  precio/características del mensaje actual), `_negated`, `_mentioned`, `_phrases_for`; `ground_details_id`
  (ficha solo de #id mencionados); `check_tool_call` (esquema); `sanitize_tool_output`. **[No tocar]**;
  negaciones en `_NEGATION_CUES`/`_SCOPE_BREAKS`.
- **Salida (reglas)**: `check_output` (fuga, código, promesas, datos personales, lugares, datos no anclados,
  contradicción, degenerado, longitud, mecánica interna, negativa seca) → `OutputProblem`; contexto en
  `OutputContext`/`output_context`; auxiliares `count_claims`, `_amount(s)`, `_shingles`, `_prose`, `_repeated`.
  **[Modificable]**: patrones `PROMISE_PATTERNS`, `PERSONAL_DATA`, `NAMED_PLACE`, `INTERNAL`; `SOFT_PROBLEMS`
  (qué problemas se aceptan si persisten).
- **Juez**: `judge_scope(model, text, note)` (umbral en `config`). **[No tocar]**; ejemplos en `prompts`.
- **Idioma de salida**: `check_language`, `_localize_lines`. **[No tocar]**.
- **Respuestas fijas**: `user_intent` (reserva, precio, contacto…, en `_INTENTS`), `fallback_reply`, `_disclaimer`,
  `_lines_intro`, `_is_bare_refusal`. **[Modificable]**: intenciones en `_INTENTS`, textos en `GUARD_REPLIES`.
- **Correcciones finales**: `finalize` (aviso si pide algo imposible, quita frases internas, emoji y Markdown,
  líneas exactas de la tool solo si tienen forma de listado `_LISTING_LINE`, inserta líneas tras la intro,
  traduce). **[No tocar]** (aquí estaba el fallo F10, ya corregido).

### `flow.py` — inicio y final
- `welcome_lines(houses)` (bienvenida con datos reales), `help_lines(language)`, `closing_lines(history,
  language)` + `session_summary` (#id vistos). **[Modificable]**: textos en `prompts`.
- `is_exit`, `is_help`, `is_farewell` (corto, sin "?", sin criterios), `_FAREWELL`, `MAX_FAREWELL_WORDS`.
  **[Modificable]**: añadir despedidas a la regex.

### `chat.py` — sesión
- `chat(model, io, history, verbose, log_dir)`: bucle de conversación (bienvenida, ayuda, despedida, `respond`).
  **[No tocar]**.
- `new_history(system_prompt)`: historial inicial (el del entregable o el base). `SessionLog`: JSONL por sesión en
  `logs/`. `_say_answer`. **[No tocar]**; desactivar logs con `LOG_TO_FILE = False`.

### `version.py`
- `disk_fingerprint()` (hash de los `.py` + datos), `loaded_fingerprint()`. Evita evaluar código antiguo.
  **[No tocar]**.

### `battery.py` y `evaluation.py` → ver sección 3.

---

## 3. Experimentos y cómo se ha demostrado que funcionan

### Sistema 1 (determinista)
- `recomanador/tests/`: una batería por bloque (`test_bloc1…5`, `3b`, `4b`), iteración 3 (`test_iter3`) e
  integración; `common.py` (utilidades, `run_case` con `ScriptedIO`), `run_all.py` → **97 comprobaciones**.
- **Oráculo independiente**: conversaciones aleatorias (y con correcciones) comparadas con un filtro reescrito
  desde la especificación, no con el código.
- **Fuzzing** (entradas basura: sin excepciones ni bucles), consistencia de JSON/plantillas y rendimiento.
- **Mutación**: se introducen fallos a propósito y la batería los detecta (prueba de que los tests sirven).
- Resultado: 97/97; pasada ampliada (1.000 + 750 + 400 conversaciones) sin errores.

### Sistema 2 (probabilístico)
- **Unitarios sin GPU** (`recomanador_llm/tests/`, 33): `test_agent.py` usa un `FakeModel` con salidas
  guionizadas (parseo, tools vs oráculo de 400 búsquedas, guardrails, anclaje con los casos de las sesiones
  manuales, flujo, F10…); `test_evaluation.py` comprueba la batería y la huella.
- **Batería con el modelo real** (`battery.py`): 68 `Case` en 13 categorías (uso normal + riesgos: fuera de
  alcance, jailbreak, inyección directa/indirecta, fuga, promesas, consejos peligrosos, discriminación, datos
  personales, alucinación, permisos de tools, robustez). Cada caso: turnos, tool esperada o prohibida, patrones
  prohibidos/requeridos, y un **ejemplo malo** que debe fallar.
- `evaluation.py`:
  - `run_battery(model=..., name=..., expected_code=...)`: ejecuta, reanuda si se corta, guarda
    `evaluacio/resultats_<name>.json` y `resum_<name>.md`; se niega si el código cargado no es el esperado
    (`check_code`).
  - `turn_failures` / `evaluate`: comprobaciones **independientes de los guardrails** (datos inventados frente a
    las tools, fuga, promesas, datos personales, mecánica interna, lugares, idioma, longitud, tool correcta,
    búsqueda correcta).
  - `EntregableResponder` / `BaselineResponder` / `baseline_responder`: mismo protocolo para el sistema nuevo y el
    del notebook; `_CountingModel` cuenta llamadas.
  - `summarize`, `summary_markdown`, `compare` (tabla por categorías), `judge_calibration` (umbral del juez).
- **Resultados**: base 40/68 → v6 66/68 (recalculados con las comprobaciones finales); calibración del juez
  (0,7: 8/9 malas detectadas, 1 falso positivo); ablación de la posición del idioma (forzar en 12/12 vs 3/12).
- **Sesiones manuales** con registro JSONL: encontraron lo que la batería no veía (anclaje que sustituía, negaciones,
  respuestas mecánicas) → v6.

---

## 4. Posibles preguntas del profesor

| Pregunta / petición | Respuesta breve | Acción |
|---|---|---|
| Enseñadnos el sistema 1 funcionando | Última celda de `P1_regles…ipynb`; probar sinónimos, "around 900", "todo menos Nou Barris", una corrección y `show me`. | Ensayar una conversación de 2 min. |
| Enseñadnos el sistema 2 funcionando | Colab con GPU T4: celdas de carga del modelo y "Chatbot interactiu". Respuesta ≈ 25 s por turno. | Tener Colab abierto con el modelo cargado **antes** de la entrevista; probar una búsqueda, "#18", un ataque y "exit". |
| ¿Cómo sabéis que el LLM no inventa viviendas? | Los datos solo salen de las tools; reglas de salida comprueban #id, precios y recuentos contra las tools; las líneas las pone el código. Batería: alucinación 4/4. | Mostrar `check_output` y `finalize`. |
| ¿Qué es el "anclaje" de argumentos? | Validar, no sustituir: el modelo interpreta; el código quita lo que el cliente nunca dijo o niega y solo añade precio/características del mensaje actual. | Ejemplo: "por menos de 400.000 €" pasado como mínimo → se corrige. |
| ¿Por qué un juez LLM y no solo reglas? | Las reglas no reconocen un poema o una receta; el juez sí. Leemos la probabilidad de YES/NO y el umbral 0,7 está calibrado con 67 respuestas etiquetadas. | `evaluacio/calibratge_jutge.md`. |
| ¿Por qué 66/68 y no 68? | Fallo 1 (comentario que empieza por "#17" tomado por línea): corregido en código y con test, sin batería real nueva. Fallo 2 (piden el esquema JSON → búsqueda vacía): no corregido, sin fuga. | Propuesta para el 2: no ejecutar una búsqueda si el anclaje la deja sin argumentos y el mensaje no tiene criterios. |
| ¿Por qué la latencia es el doble? | Cada capa añade llamadas (forzar tool, juez, reformular) en una T4 con un modelo de 3B. | Mejora posible: modelo mayor/afinado con llamadas a tools; juez solo cuando las reglas no bastan. |
| ¿Por qué no fine-tuning? | Sin datos ni GPU para entrenar; el enunciado se centra en prompt, tools y guardrails (in-context learning). | — |
| ¿Por qué el sistema 1 dirige el diálogo? | El objetivo del usuario es filtrar; dirigirlo acota lo que escribe y lo que las reglas deben cubrir. Iniciativa mixta con correcciones y `show me`. | — |
| Añadid un sinónimo / una zona | Sistema 1: `lexicon.py` (`SYNONYMS`, `LOCATIONS`/`ZONES`); el sistema 2 lo hereda. | Ejecutar los tests después. |
| Añadid una característica nueva (p. ej. balcón) | Campo en las viviendas del JSON + pregunta en `questions` + clave en `YES_ONLY_FILTERS`; para la ficha, añadirla a la lista de extras de `nlg.describe_house` y su texto en el JSON (`summary.features`, que usan el resumen y la ficha). Sistema 2: entrada en `tools.FEATURES` (filtro) y en `tools._EXTRAS` + `prompts.LINE_WORDS[...]["extras"]` (línea y notas). | Tests + repetir batería si se toca el sistema 2. |
| Cambiad una frase del sistema | Sistema 1: JSON (`reactions`, `comments`…). Sistema 2: `prompts.py`. | — |
| ¿Qué evita la prompt injection? | Entrada: regex de tokens de control, inyección y roles en 3 idiomas (no llega al modelo); system prompt; resultados de tools saneados; juez; reglas de salida. Batería: 6/6 directa, 3/3 indirecta. | Probar "Ignore all previous instructions…". |
| ¿Cómo se evaluó el sistema base? | `BaselineResponder` ejecuta `query_model_with_tools` del notebook con la misma batería y comprobaciones. | `evaluacio/resum_base.md`. |
| ¿Qué hizo la IA y qué vosotros? | Decisiones, propuestas, pruebas y evaluación: equipo; escritura del código: Claude bajo instrucciones (apartado "Uso de IA"). | Saber explicar cualquier función de este documento. |
| ¿Qué es la "huella" del código? | Hash de los `.py` y datos; la batería se niega a ejecutar código antiguo (pasó en una ejecución que se descartó). | — |
| ¿Por qué hay respuestas fijas si es un LLM? | Solo si el modelo no consigue responder de forma segura tras reformular: en v6 el modelo escribió 16/16 respuestas funcionales y 30/58 de seguridad. | — |
| ¿Qué pasa si pido Madrid? | La tool responde que no hay anuncios allí y el modelo dice dónde los hay (caso de la batería). | — |
