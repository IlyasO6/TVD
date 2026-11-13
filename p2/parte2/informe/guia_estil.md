# Guía de estilo: qué hace que un texto parezca escrito por una IA

Documento de trabajo para revisar el informe. No es una lista de palabras prohibidas: un texto suena a IA
cuando acumula varios de estos rasgos a la vez, sobre todo los estructurales. Cada apartado explica el rasgo,
por qué delata, y cómo se ve en catalán (el idioma del informe).

## 1. Estructura del discurso

**Paralelismo mecánico.** Todos los párrafos siguen el mismo molde: afirmación, cifras entre paréntesis,
interpretación y frase de cierre que resume. Una persona escribe con más irregularidad: unos párrafos sólo dan
datos, otros sólo razonan, alguno empieza por la duda.

**Cierres con moraleja.** Cada sección termina con una frase que "eleva" el resultado ("La conclusió és que...",
"Això demostra que...", "...que és justament el que esperàvem"). Si la frase final se puede quitar sin perder
información, sobra.

**Tríadas.** Enumeraciones de tres elementos por costumbre ("vectors externs, ortografia i regularització";
"més ràpid, més estable i més precís"). Una o dos por página pasan; en cada párrafo, delatan.

**Contraste "no X, sinó Y".** La construcción "el guany no ve de A sinó de B" o "no és un detall, és part del
disseny" es uno de los tics más reconocibles. Se puede decir lo mismo afirmando directamente B.

**Revelaciones con dos puntos.** "L'efecte depèn del model: ...", "La raó és senzilla: ...". Los dos puntos como
golpe de efecto, repetidos, suenan a guion. Mejor una frase normal o un punto.

**Anuncios y metadiscurso.** "Hi ha dues sorpreses", "Val la pena destacar", "Cal remarcar", "A continuació
veurem". Se anuncia lo que se va a decir en lugar de decirlo.

**Simetría artificial de pros y contras.** Cada afirmación compensada con un "tot i que" o "en canvi" para
parecer equilibrado, aunque los datos no lo pidan.

## 2. Léxico

**Intensificadores y adjetivos valorativos:** clarament, de lluny, sens dubte, notable, crucial, clau,
fonamental, robust, sòlid, imprescindible, evident, especialment. Un informe técnico se apoya en cifras, no en
adjetivos. "Significatiu" se reserva para la significancia estadística.

**Muletillas de conexión en cadena:** a més, per tant, així doncs, en definitiva, en resum, tanmateix, és a dir.
Encadenar tres en un párrafo es típico; los humanos usan menos conectores y más yuxtaposición.

**Calcos del inglés en catalán:** "jugar un paper", "fer sentit", "en termes de", "a nivell de", "basat en" como
muleta, "abordar", "aprofundir", "posar de manifest" repetido. Delatan traducción mental del inglés, que es como
"piensan" la mayoría de modelos.

**Personificación excesiva del modelo:** "el model aprèn que...", "el model sap...", "el model decideix...".
Aceptable alguna vez en ML, pero no como recurso narrativo en cada párrafo.

## 3. Forma

**Ritmo uniforme.** Frases de longitud parecida, todas bien formadas, sin ninguna corta ni ninguna larga y
enrevesada. La variedad natural incluye alguna frase de cuatro palabras.

**Exceso de paréntesis con cifras.** Meter tres números entre paréntesis en cada frase. Mejor dejar las cifras
en las tablas y citar en el texto sólo las que sostienen el argumento.

**Formato decorativo:** negritas en medio del texto, listas con viñetas para ideas que son un razonamiento,
rayas largas (—), títulos con dos puntos ("Conclusions: el que hem après"). En un informe universitario, prosa
continua.

**Perfección sin rastro del proceso.** Ningún error, ninguna decisión que se tomó y luego se revisó, ninguna
duda. Un trabajo real tiene historia: algo falló, algo se rehízo, alguna decisión fue discutible. Contarlo con
naturalidad (por ejemplo, que el criterio de parada resultó demasiado estricto y cómo lo comprobamos) es lo que
más humaniza un texto, y además es honesto.

## 4. Contenido

**Repetición entre secciones.** La introducción anuncia, el cuerpo explica y la conclusión repite las mismas
frases con otras palabras. La conclusión debe sintetizar, no resumir sección por sección.

**Generalidades sin anclaje.** Frases que valdrían para cualquier trabajo ("els resultats mostren la importància
d'escollir bé l'arquitectura"). Cada afirmación debe poder rastrearse a una tabla, figura o celda del notebook.

**Trabajo futuro genérico.** "Seria interessant explorar models més grans". Si se propone algo, que salga de un
resultado concreto del trabajo.

**Sobreinterpretación.** Explicar con seguridad causas que no se han medido. Cuando es una hipótesis, decirlo
("probablement", "creiem que"), pero sin envolver cada frase en cautelas.

## 5. Lista de comprobación para la revisión

Para cada párrafo del informe:

1. ¿Se puede quitar la última frase sin perder información? Si sí, quitarla.
2. ¿Hay un "no X, sinó Y", una revelación con dos puntos o un anuncio ("cal remarcar", "hi ha dues...")?
   Reescribir.
3. ¿Hay más de un intensificador (clarament, de lluny, robust...)? Dejar como mucho uno, y mejor ninguno.
4. ¿Hay una tríada que no responde a tres cosas reales? Romperla.
5. ¿Más de dos cifras entre paréntesis en la misma frase? Mover a tabla o elegir la que importa.
6. ¿Todos los párrafos de la sección tienen la misma forma? Variar.
7. ¿Hay calcos ("a nivell de", "en termes de", "jugar un paper")? Sustituir.
8. ¿Cada afirmación tiene respaldo en el notebook? Si no, quitarla o marcarla como hipótesis.
9. ¿Se nota que lo escribió el grupo que hizo el trabajo (decisiones, problemas, comprobaciones)? Si no, añadir
   el detalle del proceso donde sea relevante.
