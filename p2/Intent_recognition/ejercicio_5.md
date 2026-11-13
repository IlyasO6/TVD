# Exercici 5: notebook acadèmic autocontingut

Executarem `P2_1_alumnes.ipynb` amb **Restart & Run All**. Definirem les funcions comunes abans d'utilitzar-les i executarem automàticament els apartats 5.1–5.9, sense activar interruptors ni triar manualment hiperparàmetres. Només necessitarem els datasets originals i les biblioteques de Python importades al notebook.

## Protocol experimental

Mantindrem 4078 exemples de train, 900 de validació i 888 de test després de les exclusions originals. Aprendrem el vocabulari i els pesos exclusivament amb train. Seleccionarem hiperparàmetres i checkpoints amb validació i consultarem test una sola vegada al final.

Conservarem la partició original: documentarem el solapament de 93 textos diferents entre train i validació, que afecta 104 files de validació, i 10 textos entre train i test. No afirmarem independència textual completa.

Utilitzarem PAD=0, UNK=1, padding post, longituds reals i màscares apropiades per a cada arquitectura. Calcularem els pesos de classe només amb train. Seleccionarem sempre el checkpoint amb menor validation loss sense pesos, també quan ponderem la loss d'entrenament.

Exclourem exactament day_name (2 exemples), airfare+flight (1), flight+airline (1) i flight_no+airline (1), absents de train. Interpretarem el resultat com una avaluació de classes conegudes sobre els 888 exemples retinguts; no l'estendrem als 893 originals ni al reconeixement d'intencions desconegudes.

Tindrem present que flight representa el 74,13 % de train, mentre que quatre classes tenen un exemple i dues en tenen dos. Amb pesos inversos obtenim 185,36 per a una classe d'un exemple, 92,68 per a una de dos i 0,0613 per a flight. Considerarem que una observació molt rara pot dominar la contribució relativa a un batch: la ponderació no afegeix dades i pot amplificar memorització, ambigüitats o variabilitat. No afirmarem un benefici fiable per a totes les minoritàries, sobretot si no tenen suport a validació.

Interpretem les tres llavors com variabilitat d'entrenament, no com una correcció del biaix de la partició. Mantindrem el protocol fix ara que test ja ha estat consultat i no repetirem la cerca a partir del seu resultat.

## Seqüència dels experiments

1. **5.1. Preparació:** definirem dades, preprocessing, models, entrenador, mètriques i funcions de presentació. Iniciarem una sessió buida, sense recuperar fitxers externs.
2. **5.2. Preprocessament:** compararem vocabulari 250/500/1000/2000, lowercase i Snowball anglès, amb un únic factor variable en cada contrast.
3. **5.3. Embeddings:** compararem 32/64/128 i provarem explícitament una combinació addicional de valors seleccionats, sense assumir que les millores se sumen.
4. **5.4. CNN:** compararem kernels 2/3/5, pooling max/average amb el kernel seleccionat i una/dues convolucions.
5. **5.5. Recurrents:** compararem LSTM, BiLSTM, GRU, BiGRU, LSTM+attention i BiLSTM+attention; després compararem hidden 64/128 en el recurrent seleccionat.
6. **5.6. Dropout:** compararem 0/0.2/0.4 en una CNN i un recurrent seleccionats amb validació.
7. **5.7. Balanceig:** compararem el model escollit amb i sense pesos N/(C*count), mostrant accuracy, macro-F1 i recall.
8. **5.8. Comparació global:** repetirem un candidat per família amb llavors 42/123/2026; seleccionarem la família mitjançant les mitjanes de validació i avaluarem sobre test el seu checkpoint de llavor 42, fixada prèviament.
9. **5.9. Conclusions:** resumirem exclusivament mètriques realment calculades i discutirem les limitacions.

Mantindrem Adam, learning rate 0.001, batch 32, màxim 25 èpoques i patience 4 com a referència comuna. Controlarem les llavors i restaurarem els millors pesos abans d'obtenir les mètriques finals de cada experiment. No farem una cerca cartesiana; reutilitzarem durant la mateixa execució configuracions idèntiques o amb tensors equivalents, identificant-ho a la taula.

Llegirem les interpretacions específiques i les comparacions breus de 5.2–5.8, juntament amb les taules detallades i els gràfics. A 5.9 sintetitzarem l'execució guardada amb noms descriptius de models, distingint els efectes observats de les explicacions possibles. No considerarem les diferències d'una sola llavor una prova de superioritat universal.

## Resultats dins del notebook

Consultarem `resultats_experiments`, les taules de cada apartat i `historials_entrenament`. Mantindrem els millors estats a `models_entrenats` i el model final a `millor_model`. Totes aquestes dades viuran en memòria durant l'execució.

Mostrarem les taules amb `display()` i les figures amb Matplotlib, després de calcular resultats reals. Conservarem els outputs dins del `.ipynb` en desar-lo, per revisar-los sense repetir l'entrenament. No crearem carpetes de resultats, JSON, CSV, PNG, mòduls Python ni checkpoints externs. No necessitarem els resultats de proves guardats amb anterioritat.

Mantindrem el lliurable original després de 5.9. Seleccionarem les taules i figures pertinents per explicar els contrastos sense superar les deu pàgines de l'informe.
