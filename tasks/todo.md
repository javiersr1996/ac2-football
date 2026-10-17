# ac2-football: entrada de fútbol a la Analytics Cup 2.0 (planificado el 2026-10-17)

Carpeta y paquete con nombre provisional (`ac2-football`, `ac2fb`) hasta que Javier elija (J2).
**Las cifras que no vienen del inventario son hipótesis** y van marcadas así hasta que una tarea
las imprima. Lo que no se pudo medir dice PENDIENTE DE CONFIRMAR.

## La entrada en tres capas

- **Capa 1, base (trabajo previo, declarado).** Ingesta verificada por sha256 contra manifiesto,
  bronze, frames y eventos conformados, copiados de tracklab (repo privado del autor, MIT). No se
  enlaza; se nombra como origen.
- **Capa 2, fiabilidad (nuevo, la columna vertebral, no puede morir).** Cuánto cambia cada métrica
  defensiva al quitar lo extrapolado (`is_detected` false), partido a partido. tracklab midió la
  PROPORCIÓN detectada; lo nuevo es la SENSIBILIDAD de las métricas a ella.
- **Capa 3, aplicación (nuevo, con permiso para morir).** Una pregunta de presión o posición
  defensiva con la incertidumbre del tracking dentro. La pregunta NO está elegida: la elige Javier
  en CP1 con las cifras de las sondas delante.

## Bases oficiales (leídas en la fuente el 2026-10-17, citadas tal cual)

- Entrega **18 Dec 2026** (62 días desde hoy, 8,9 semanas). Finalistas 8 Jan 2027. Final Europa
  17 Feb 2027 en París, presencial, viaje no pagado, 500 EUR por finalista. Ganador regional:
  grant de 1.500 EUR para convertirlo en paquete Python o PR.
- "The submission must contain substantial new work created specifically for the Analytics Cup.
  Pre-existing libraries, frameworks, open-source projects and general-purpose code may be used,
  provided they are appropriately licensed and disclosed. Previously completed projects may not
  simply be resubmitted or lightly adapted."
- "The project must use only the SkillCorner dataset provided for this event, and/or prior
  Analytics Cups. The use of additional data (e.g. video, or additional matches...) will lead to
  immediate disqualification." Fútbol: A-League 2024/25, agregados físicos de 175 partidos, 20
  partidos de tracking XY, Dynamic Events, 2 partidos de Body Pose (github.com/SkillCorner/opendata).
- Sin software propietario. Entregables: vídeo de YouTube de **máximo 1 minuto** con la voz del
  autor; repo público con todo salvo los datos, licencia abierta, **fichero LICENSE.md**, "should
  work out of the box"; **README.md de hasta 1000 palabras con un máximo de dos figuras o tablas
  en total**, con instrucciones para reproducir en entorno limpio. Descalifica: no ejecutar out of
  the box, entregar tarde, usar datos adicionales.
- Criterios, 20 % cada uno: Relevance, Methodology, Originality, Communication, Open-source
  potential ("Can others reproduce, reuse or develop the work further?").
- Recursos sugeridos: kloppy, databallpy, floodlight, mplsoccer, skillcornerviz, unravelsports.

## Lo que ya existe, medido (inventario del 2026-10-17, tracklab en `686508a`)

Fuente: sondas de solo lectura de esta sesión (`m1.py` a `m9.py` en
`C:\Users\javie\AppData\Local\Temp\claude\C--Users-javie-Desktop-proyectos-tracklab\32ca1c69-cc35-4afa-8188-48fc580d005f\scratchpad\ac2\`),
DuckDB en memoria sobre `tracklab/pipeline/data` (silver `frames`, bronze `dynamic_events`,
`phases_of_play`, `match_players`, `dim_team_period`); ninguna escribe en tracklab. **La tarea 9
re-deriva en código las de capa 2 y tiene que dar las mismas cifras**; si no, se corrige este
plan. "Por partido" = mínimo a máximo sobre los 20 (mediana entre paréntesis).

**Fuente y peso.**
- `SkillCorner/opendata`: HEAD de `master` el 2026-10-17 es `4340d274572876239c154c90bc507a9b3250a656`
  (`git ls-remote`), el mismo commit que fija `tracklab/pipeline/manifest/sources.json`.
- Fuente de fútbol del manifiesto: 85 ficheros, 1.919.842.163 B; los 20 de tracking van por LFS
  (1.823.448.331 B). El manifiesto trae además baloncesto (35) y body pose (2): no se copian.
- Silver `frames` de fútbol: 20.213.849 filas (19.334.986 de jugador, 878.863 de balón), igual
  que `tracklab/web/public/data/stats.json`. Jugador detectado 56,8 % de las filas, balón 80,2 %.
- Clon limpio de tracklab con descarga real de los dos bundles: 670 s (`tracklab/tasks/todo.md:3420`).

**Eventos (`dynamic_events`, bronze: 94.361 filas, 325 columnas; el CSV trae 322).**
- Por tipo: `passing_option` 48.308, `player_possession` 18.710, `on_ball_engagement` 17.445,
  `off_ball_run` 9.898, los cuatro en los 20 partidos.
- `on_ball_engagement` por partido 754 a 1.025 (874). Subtipos (total, por partido): `pressure`
  4.636 (169 a 281), `recovery_press` 4.084 (141 a 249), `pressing` 3.847 (117 a 268), `other`
  3.251 (112 a 199), `counter_press` 1.627 (62 a 102). Todos traen `frame_physical_start`,
  `interplayer_distance_start/min`, `pressing_chain` (5.962 true), `goal_side_start`.
- `frame_physical_start` cae antes de `frame_start` en el 36,3 % de los `on_ball_engagement`
  (nunca después; p90 del adelanto 15 frames, 1,5 s). Duración mediana 12 frames (p90 32).
- `overall_pressure_start` solo en `player_possession`: 16.604 de 18.710 (84,2 a 92,6 % por
  partido, 653 a 1.056): `no_pressure` 4.683, `medium` 4.390, `low` 3.442, `high` 3.384,
  `very_high` 705, nulo 2.106.
- `fully_extrapolated` (bandera del proveedor) solo en `passing_option` (7.398 de 48.308) y
  `player_possession` (276 de 18.710; 0,4 a 3,9 % por partido; 234 de ellas sin presión).
- `last_defensive_line_x_start` en 18.697 de 18.710 posesiones. `phases_of_play`: 8.834 fases,
  `team_out_of_possession_width/length_start` en 8.494. **tracklab nunca usó** columnas de
  presión ni de `on_ball_engagement` (grep en `src`, `reports`, `tasks`: solo recuentos).

**Detección alrededor de la presión (lo que la capa 2 necesita saber antes de elegir).**
- Defensor que presiona (`player_id` del `on_ball_engagement`) detectado en `frame_start`: 95,1 %
  global, 92,5 a 96,8 % por partido (por subtipo, de 93,3 % `other` a 95,9 % `recovery_press`);
  en `frame_physical_start` anterior, 85,3 a 95,1 % (91,9); entero en `[frame_start - 1 s,
  frame_end + 1 s]`, 76,7 a 91,1 % (86,2). Defensor y poseedor a la vez: 90,4 a 95,9 % (94,1).
- En la recepción (`frame_start` de `player_possession`): poseedor detectado 93,6 a 98,2 % (96,8).
  Rivales a 5 m o menos del poseedor detectados 93,1 a 98,6 % (97,0); a 10 m 93,0 a 98,4; a 20 m
  87,7 a 96,2; más allá de 20 m 33,0 a 62,1 (46,9). Posesiones sin rival a 5 m: 42,3 a 68,4 %.
  De las 8.066 con algún rival a 5 m, con al menos uno extrapolado: 1,8 a 8,5 % (3,6).
- **Línea defensiva en la recepción** (4 jugadores de campo más retrasados del rival, sin portero,
  18.657 posesiones): fracción detectada 37,4 a 69,7 % (51,7); los 4 detectados a la vez en el
  19,6 a 56,1 % de las posesiones (34,3); el más retrasado, 28,6 a 60,1 % (43,3).
- **Bloque al inicio de fase** (los 11 sin balón, 8.461 fases): detectados 51,1 a 69,2 % (58,2);
  fases con los 11 detectados 0,5 a 5,9 % (2,8).
- Detección de jugadores por distancia al balón (1 de cada 10 frames): 0 a 5 m 82,5 a 91,4 %
  (86,3); 5 a 10 m 78,9 a 89,3 (83,8); 10 a 20 m 70,9 a 84,1 (77,4); 20 a 30 m 43,9 a 70,8
  (57,7); 30 a 40 m 26,0 a 51,8 (36,4); más de 40 m 11,6 a 26,9 (16,1).
- **Lo local es casi todo visto; lo global, la mitad modelo.** Es la hipótesis que la capa 2
  convierte en mapa por métrica.

**Cómo es lo extrapolado.**
- Paso por 0,1 s, mediana por partido: detectado a detectado 0,200 m (0,184 a 0,218),
  extrapolado a extrapolado 0,129 (0,112 a 0,140), extrapolado a detectado 0,171 (0,136 a 0,200).
  **No hay salto al recuperar la detección**: el salto no sirve para medir el error extrapolado.
- Tramos extrapolados: 98.487, mediana 47 frames (4,7 s), p90 175 (17,5 s), p99 587 (58,7 s).
- Cadencia (exploratoria, 1874553, 1925299, 2010085): el hueco entre quiebros (|segunda
  diferencia| > 1,5 cm) de detectados es 1 frame en el 57,6 a 59,8 % y decae sin pico en 5; el
  umbral cae dentro del ruido de redondeo de la rejilla de 1 cm. Lo cierra la tarea 10.

**kloppy.** kloppy 3.19.1 (última en PyPI hoy): el deserializador `skillcorner` lee `player_data`
sin `is_detected` (grep del paquete instalado en esta sesión). Quien cargue estos datos con kloppy
no distingue lo detectado de lo extrapolado. Lo vuelve a comprobar la tarea 15.

**Código a copiar (lectura de un subagente sobre tracklab `pipeline/`).**
- Casi tal cual: `ingest/{fetch,lfs,verify,manifest,local}.py` (sin HuggingFace, `freeze` ni
  baloncesto), `bronze/common.py`, `bronze/football/{tracking,events,meta}.py`,
  `formats/csvschema.py`, dos esquemas JSON, `quality/{common,detection}.py`, `paths.py`.
- Se reescribe: silver sin dbt (`frames.sql` 163 líneas, `events.sql` 287 y dims son DuckDB plano
  tras quitar `ref()/source()` y baloncesto); la orientación de fútbol (unas 250 de las 1.839 de
  `silver/orientation.py`); el CLI (unas 80); los 6 tests dbt de fútbol, como SQL de 0 filas. No
  se copian `formats/football.py`, `runs/` (P5), `build.py`, Dagster, dbt, pose ni publish.
- Estimación (hipótesis): **unas 2.250 líneas copiadas y 460 reescritas**; dependencias `duckdb`,
  `pyarrow`, `httpx`; Python >= 3.13. Tiempo y RAM del build: PENDIENTE DE CONFIRMAR (tarea 7).

**Contaminación declarada.** Esta sesión calculó en los 20 partidos solo recuentos, nulos,
vocabularios, detección y pasos. **Ningún desenlace de C1, C2 ni C3**: no se miró
`stop_possession_danger`, `force_backward`, `beaten_by_*`, `possession_danger`, `end_type` contra
presión, `last_defensive_line_*_end` ni ningún movimiento posterior a una recepción. tracklab: P5
miró carreras en los 10 partidos de calibración del split A y **nunca abrió su reservado**; P6 leyó
pose de 1925299 y 1996435 (los dos en calibración).

## Preguntas candidatas de la capa 3 (se elige una en CP1)

Las tres miden presión con el tracking en la recepción (`frame_start` de `player_possession`),
porque ahí el poseedor y sus rivales cercanos están vistos (97,0 %). Difieren en dónde vive el
desenlace, y por tanto en cuánto muerde la capa 2.

**C1. "Pressure the camera sees": presión en la recepción y progreso inmediato del balón.**
- Pregunta: ¿la presión sobre el poseedor en la recepción reduce el avance del balón hacia la
  portería en los 2 s siguientes, dentro de la misma zona y tipo de fase, y sobrevive a quitar los
  defensores extrapolados?
- Instrumento: índice de presión geométrico (rivales a 10 m o menos con peso por distancia y por
  estar entre poseedor y portería). Contraste de dirección forzada: debe crecer con los 5 niveles
  de `overall_pressure_start` (la etiqueta contrasta, nunca es desenlace). Desenlace: avance del
  balón en el marco de ataque en `[t, t + W]`, del tracking.
- Capa 2: muerde poco (3,6 % de posesiones con un rival extrapolado a 5 m), pero el balón está
  detectado solo en el 75,45 a 85,38 % de frames con balón (`tracklab/docs/formats/football.md`).
- Riesgo de morir: **medio** (confusión con zona y fase, se estratifica; `frame_start` puede no
  ser la recepción, lección P5). Encaje: Relevance alta, Methodology media-alta, **Originality
  baja** (hay muchos modelos de presión y el proveedor ya la etiqueta), Communication alta,
  Open-source media.

**C2. "Ball pressured, line steps up": respuesta de la última línea a la presión sobre el balón.**
- Pregunta: cuando el poseedor recibe presionado, ¿la última línea rival sube (y cuando recibe
  libre, cae) en los segundos siguientes, más de lo que su velocidad en `t` predecía, y sobrevive
  con la línea detectada? Es el principio "balón presionado, línea arriba" como definición
  geométrica, sin leer intención.
- Instrumento: altura de la línea (media de los 4 jugadores de campo más retrasados, sin portero),
  contrastada contra `last_defensive_line_x_start` del proveedor (18.697 posesiones). Causa:
  presión de C1 en `t`. Desenlace: desplazamiento de la línea en `[t, t + W]` menos el que predecía
  su velocidad en `t`; pre-tendencia en `[t - W, t]` que tiene que salir plana.
- Capa 2: **muerde en el desenlace**: la línea está detectada al 51,7 % y entera en el 34,3 % de
  las posesiones (19,6 a 56,1 % por partido). El sesgo de visibilidad es el riesgo y el hallazgo:
  la línea se ve entera cuando está cerca del balón.
- Riesgo de morir: **medio-alto** (lo extrapolado se mueve más suave, paso mediano 0,129 frente a
  0,200 m por frame, y puede aplanar la respuesta; reacción al pase; potencia tras restringir).
  Encaje: Relevance muy alta (presión, forma y "defensive decision-making"), Methodology alta,
  **Originality alta**, Communication alta (la línea con los extrapolados en hueco), Open-source
  alta (la sensibilidad sirve para cualquier métrica de línea).

**C3. "The block the camera does not see": compacidad del bloque y fase de juego.**
- Pregunta: ¿las diferencias de compacidad del bloque sin balón (anchura, longitud, área) entre
  tipos de fase sobreviven cuando se mide solo lo visto, o las fabrica lo extrapolado?
- Instrumento: anchura y longitud propias al inicio de fase contra
  `team_out_of_possession_width/length_start` del proveedor (8.494 fases).
- Capa 2: muerde todo (bloque detectado al 58,2 %, entero en el 2,8 % de las fases): solo puede
  dar una banda (todo, sin extrapolados, fases más vistas), no un valor verdadero.
- Riesgo de morir: **bajo como medida, alto como hallazgo** (lo probable es "no identificable con
  retransmisión": negativo útil, poca aplicación). Encaje: Relevance muy alta, Methodology media,
  Originality media-alta, Communication alta, Open-source alta.

**Descartada ahora: el efecto de un `on_ball_engagement` sobre el poseedor.** Es el diseño de P5
(placebo, instante del proveedor) y el instante es dudoso: `frame_physical_start` adelanta a
`frame_start` en el 36,3 %. Sus cifras de detección quedan en el inventario para la capa 2.

**Recomendación provisional: C2**, si la sonda 12 da un instrumento de línea que concuerda con el
proveedor y una potencia útil tras restringir; si no, C1; C3 solo como respaldo descriptivo. Lo
decide CP1, no este plan.

## Reglas

- **Regla de oro.** Ninguna cifra en README, vídeo, figuras ni plan sin un artefacto de `reports/`
  que la imprima. **Por partido, siempre**, veredicto reservado, un negativo junto a cada positivo.
- **El desenlace es geometría del tracking**; las etiquetas del proveedor (`overall_pressure_*`,
  `last_defensive_line_*`, anchura de fase) solo contrastan el instrumento. **La causa, en un
  instante que el efecto no pudo causar**, validado antes con cinemática (P5), pre-tendencia plana.
- **Intención no reclamable**: "decision-making" solo como definición geométrica medida.
- **El protocolo es código y se congela antes del reservado**; un umbral que falla no se mueve. La
  capa 2 corre solo en calibración hasta la lectura. Tests que pueden fallar (mutación anotada).
- **Un solo agente escribe en este árbol; nadie escribe en tracklab.** LF en todo escritor. 0 €.
- **Fuera de alcance:** EPV propio, rankings de jugador o equipo, predicción de resultados, vídeo,
  body pose, baloncesto, cualquier dato fuera del commit fijado de `SkillCorner/opendata`.

## Decisiones, con su porqué (las aprueba Javier en J3)

1. **Split A de P5, declarado hoy, antes de calcular ningún desenlace.** Calibración 1874553,
   1886347, 1925299, 1959846, 1996435, 1996436, 2007448, 2010085, 2011166, 2015213; reservado
   1899585, 1927964, 1953632, 1986691, 2006229, 2006363, 2007721, 2013725, 2016236, 2017461.
   Queda 5 y 5 por precisión de coordenadas de eventos y 2 y 3 por metraje fuera de periodo
   (`tracklab/tasks/todo.md:4767-4774`), y ese reservado nunca se abrió.
2. **Base en DuckDB + Python, sin dbt ni Dagster.** Out of the box ligero; se pierden lineage y
   docs de dbt, no los tests. Python 3.13 fijado con uv, como tracklab (uv instala Python).
3. **Fixtures sintéticos en formato SkillCorner, no un corte real**: el repo va "con todo salvo
   los datos" y CI por push no tira de la cuota LFS de SkillCorner; datos reales solo en
   `full-build` (manual, caché por huella del manifiesto). Alternativa: el corte de 1874553 de
   tracklab (MIT, PENDIENTE DE CONFIRMAR su peso); si Javier la prefiere, cambia la tarea 5.
4. **Lector propio, kloppy no es dependencia** (3.19.1 pierde `is_detected`). Salida en Parquet
   largo documentado (`match_id, period, frame, player_id, team_id, x, y, is_detected`); un issue
   o PR a kloppy es el "develop further" natural, y el uso del grant.
5. **`--from-existing <dir>` se conserva**: si se agota la cuota LFS de SkillCorner, un clon local
   de `opendata` se verifica en sitio y el repo sigue funcionando.

## Fases y fechas

| Fase | Fechas | Contenido | Horas (hipótesis) |
|---|---|---|---|
| 0 | sáb 17 oct a dom 25 oct | Repo, base copiada, CI con fixtures | 12 a 16 |
| 1 | lun 26 oct a dom 1 nov | Split y guard, núcleo de capa 2, sondas, potencia | 10 a 14 |
| CP1 | lun 2 nov | **Javier elige la pregunta** | 1 |
| 2 | lun 2 nov a dom 15 nov | Protocolo, sintéticos, calibración, congelación | 14 a 18 |
| CP2 | lun 16 nov | Javier aprueba la congelación | 1 |
| 3 | lun 16 nov a dom 29 nov | Lectura única del reservado, capa 2 completa | 6 a 10 |
| 4 | lun 30 nov a dom 6 dic | Figuras, `--check`, API, CI Linux completo | 8 a 10 |
| 5 | lun 7 dic a vie 18 dic | README, vídeo, clon limpio, entrega (objetivo mar 15 dic) | 8 a 12 |

Holgura: la fase 3 tiene una semana libre si la calibración mata la pregunta (rama B).

## Plan B: si la capa 3 muere (en sonda, calibración o reservado)

Se publica como cae, con el negativo bien medido. La entrada cuenta: (1) la base, declarada; (2)
**la capa 2 como contribución principal**: qué métricas defensivas aguantan la retransmisión y
cuáles son sobre todo modelo, por partido, con el sesgo de visibilidad medido; (3) dónde murió la
pregunta, con las cifras por partido de esa sonda y lo que no se abrió. La figura 2 enseña la
muerte. Si en CP1 mueren las tres, rama B ese día y las dos semanas libres amplían la capa 2.

## Fase 0: base (sáb 17 oct a dom 25 oct)

- [ ] J1. **[Javier]** Registrarse en la Cup (región Europa) y confirmar que puede asistir a París
  el 17 Feb 2027 (las bases piden poder asistir antes de entregar). Antes del dom 25 oct. Si no
  puede: parar y replantear.
- [ ] J2. **[Javier]** Elegir nombre del repo y del paquete, y crear el repo en GitHub (privado
  hasta J6 o público ya, a su elección) para que corra CI. Antes del dom 25 oct.
- [ ] J3. **[Javier]** Aprobar este plan y las decisiones 1 a 5.
- [ ] 1. `sonnet` Esqueleto: `pyproject.toml` (uv, hatchling, `ruff` línea 100 y reglas
  `E,F,I,UP,B`, `mypy --strict`, `pytest`), `.python-version`, `.gitattributes` con `* text=auto
  eol=lf`, `.gitignore` con `data/`, `LICENSE.md` (MIT, Javier Sánchez Rueda, 2026). Paquete
  `src/ac2fb/` con `base/` (copiado), `reliability/` (capa 2), `defence/` (capa 3), `protocol/`
  (split, guard, congelación), `cli.py`. Aceptación: `uv sync --locked` y el gate (V) en verde con
  un test trivial que se rompe al mutar.
- [ ] 2. `sonnet` Ingesta copiada: manifiesto recortado a `opendata-football` (85 ficheros, commit
  `4340d27`), `fetch` sin HuggingFace ni `freeze`, `verify`, `lfs`, `manifest`, `local`
  (`--from-existing`). Cabecera en cada fichero copiado: origen en tracklab, commit, cambios.
  Renombrar `TRACKLAB_DATA_ROOT`, `User-Agent` y metadatos `tracklab.*`. Aceptación: `ac2fb
  ingest` descarga y verifica los 85 (recibo con `failed: 0`); tests copiados de `test_ingest.py`
  sin la parte de baloncesto; mutación anotada (un sha256 cambiado tiene que fallar).
- [ ] 3. `sonnet` Bronze copiado: `common`, `tracking`, `events`, `meta`, `csvschema` y los dos
  esquemas JSON. Aceptación: `ac2fb bronze` produce las tablas de fútbol con los mismos recuentos
  que tracklab (94.361 filas de eventos; tracking por partido igual) y las cabeceras congeladas
  (`header_sha256`); tests de contrato copiados y recortados; mutación anotada.
- [ ] 4. `opus` Silver sin dbt: orientación de fútbol desde `match.home_team_side` (reescrita,
  unas 250 líneas), dims, `frames`, `events` y la vista `frames_attacking`, ejecutados desde Python
  en orden; los 6 tests dbt de fútbol como aserciones SQL de 0 filas. Aceptación: 20.213.849
  filas de `frames` y mismos recuentos por partido y `is_detected` que tracklab, comparados con un
  script de solo lectura contra `tracklab/pipeline/data`; signos de ataque opuestos por periodo en
  los 20; mutación: invertir un signo hace fallar la aserción.
- [ ] 5. `sonnet` Fixtures sintéticos (decisión 3): generador determinista de un partido corto en
  formato SkillCorner (JSONL, `match.json`, CSV de eventos y fases con las cabeceras congeladas),
  con tramos extrapolados plantados. CI `ci.yml` en `ubuntu-latest`: ruff, format, mypy, pytest
  sobre fixtures. Aceptación: CI en verde en GitHub; un skip cuenta como fallo (sin skips
  silenciosos); mutación anotada en el generador.
- [ ] 6. `haiku` Procedencia: `docs/provenance.md` (fichero copiado, ruta y commit en tracklab,
  líneas copiadas, líneas cambiadas) y `ac2fb provenance` que imprime y escribe
  `reports/provenance.json` (líneas en `base/` frente al resto). Primer commit del repo: solo la
  base importada, mensaje "Import base from tracklab@<sha> (author's prior work, MIT)".
  Aceptación: el recuento del JSON coincide con `wc -l`; test que falla si un fichero de `base/`
  no está en la tabla.
- [ ] 7. `sonnet` Build completo de los 20 partidos y `scripts/clean_clone_check.sh` adaptado (el
  bloque de un README provisional, 5 comandos como máximo, en un `mktemp -d`, recibo sin fallos,
  árbol sin cambios). Aceptación: `CLEAN CLONE OK in N s` en local; tiempo y pico de RAM del build
  anotados (resuelve el PENDIENTE del inventario).

## Fase 1: capa 2 y sondas (lun 26 oct a dom 1 nov)

Todas las sondas corren **solo en los 10 partidos de calibración** y ninguna calcula el desenlace
de ninguna candidata. Cada una escribe su `reports/probe_<n>.json` por partido.

- [ ] 8. `opus` Split y guard: `protocol/split.json` con la decisión 1, commiteado antes de
  cualquier código de desenlace. Una sola puerta a los datos: toda lectura de silver pasa por
  `protocol.data`, que rehúsa los ids del reservado salvo con protocolo `frozen` en `HEAD`,
  `code_tree_sha` de `defence/` y `reliability/` igual al congelado y árbol limpio; tras la lectura,
  `stage: "read"` con su commit, y entonces reproduce. Aceptación: test de comportamiento sobre
  toda ruta pública (cada comando del CLI y cada función exportada, enumerados por el test);
  mutaciones anotadas: guard que solo mira `stage`, guard sin comparar el sha, lectura que
  esquiva `protocol.data`; las tres tienen que hacer fallar un test.
- [ ] 9. `sonnet` Núcleo de la capa 2 (`reliability/`): detección por partido, por distancia al
  balón, de la línea y del bloque, tramos extrapolados y pasos por transición; una función genérica
  `sensitivity(metric, frames)` que devuelve, por partido, la métrica con todo, sin extrapolados y
  restringida a unidades enteras vistas, más la fracción extrapolada que la sostiene. Aceptación:
  re-deriva las cifras de capa 2 del inventario en los 10 de calibración (iguales o este plan se
  corrige); sintético con extrapolación plantada que la función tiene que detectar, 5 semillas.
- [ ] 10. `sonnet` Cadencia en fútbol: segundas diferencias de jugadores detectados con un umbral
  por encima del ruido de redondeo de la rejilla de 1 cm (justificado en la tarea), hueco entre
  quiebros en los 10 de calibración. Aceptación: `reports/probe_cadence.json`; decide la ventana
  más corta admisible (W mínimo) y lo escribe.
- [ ] 11. `sonnet` Sonda S1 (C1): índice de presión en la recepción; contraste de dirección
  forzada (mediana del índice creciente en los 5 niveles de `overall_pressure_start` en al menos
  9 de 10 partidos); instante: distancia balón a poseedor en `frame_start` y frames hasta el
  contacto; fracción del índice que sostienen rivales extrapolados; recuentos por partido.
  Muere C1 en sonda si el contraste falla.
- [ ] 12. `opus` Sonda S2 (C2): altura de línea propia contra `last_defensive_line_x_start` en la
  recepción (concordancia por partido; umbral fijado antes de correr, en el propio commit de la
  sonda); detección de la línea en `[t - W, t + W]`; recuento por partido de posesiones con la
  línea entera vista, por tercio del balón (sesgo de visibilidad). Muere C2 en sonda si el
  instrumento no concuerda en al menos 9 de 10 o si quedan menos de 100 posesiones por partido
  con la línea vista (hipótesis, se revisa con la potencia de la 14).
- [ ] 13. `sonnet` Sonda S3 (C3): anchura y longitud propias contra las del proveedor al inicio
  de fase (y la definición que usa el proveedor: con o sin portero, extremos o percentiles);
  fracción extrapolada de los jugadores que fijan cada extremo; correlación de rango entre
  fracción detectada y la propia métrica (sesgo de visibilidad). Muere C3 en sonda si no se
  reproduce la métrica del proveedor.
- [ ] 14. `opus` Potencia por candidata con los tamaños medidos en 11 a 13: MDE80 en sd con el bar
  de la regla (mismo signo en al menos 8 de 10 y p de permutación agrupado ≤ 0,00135), para la
  variante con todo y la restringida a lo visto. Aceptación: `reports/power.json`; tabla de CP1.
- [ ] 15. `haiku` kloppy: con la versión fijada, cargar el partido sintético y comprobar si
  `is_detected` sobrevive; si no, borrador del texto de un issue (no se publica: es de Javier).
- [ ] 16. `opus` (subagente `revisor-adversarial`) Revisión de 8 a 15 antes de CP1, repetida
  sobre los arreglos hasta que no salga nada alto ni medio.
- [ ] CP1. **[Javier] lun 2 nov.** Elige UNA pregunta con la tabla delante (por candidata:
  instrumento pasa o no, fracción extrapolada que la sostiene, n por partido, MDE80, riesgo y
  encaje con los 5 criterios). Va recomendada primero la que salga de la regla: C2 si S2 pasa y
  su MDE80 restringido es ≤ 0,3 sd; si no, C1; C3 solo como respaldo; ninguna viva, rama B.

## Fase 2: protocolo y calibración (lun 2 nov a dom 15 nov)

- [ ] 17. `opus` Protocolo en `stage: "design"` (`protocol/protocol.json`), escrito antes de
  calcular un solo desenlace: instante de la causa (de la sonda), ventana W (de la 10), desenlace
  exacto, estratos (tercio del balón por tipo de fase), nulo por permutación de la causa dentro de
  partido y estrato (2.000, semilla fija), variantes de capa 2 (V0 todo, V1 solo unidades vistas
  enteras, V2 métrica sin extrapolados), bar de calibración y de reservado (mismo signo en al menos
  8 de 10 y p ≤ 0,01 con Holm). **Criterios de muerte:** D1 el instrumento falla su contraste; D2
  MDE80 > 0,3 sd en alguna mitad; D3 la pre-tendencia llega al 50 % del efecto; D4 en V1 o V2 el
  efecto cambia de signo o cae por debajo de la mitad (extrapolación); D5 nada pasa en
  calibración, el reservado no se abre; D6 el reservado no pasa, se publica así.
- [ ] 18. `sonnet` Estimador validado con sintéticos antes de tocar datos reales: efecto plantado
  que se recupera, pre-tendencia plantada que sale por D3, artefacto de extrapolación plantado que
  sale por D4; 5 semillas cada uno. Mutación: medir la causa en `t + 1 s` deja pasar la
  pre-tendencia y el test falla.
- [ ] 19. `opus` Calibración: efecto por partido en los 10, las tres variantes, pre-tendencia y
  veredicto mecánico D1 a D5 en `reports/calibration.json`. Nada de este paso mueve un umbral.
- [ ] 20. `opus` (subagente `revisor-adversarial`) Revisión del protocolo, el estimador y la
  calibración antes de congelar, hasta que no salga nada alto ni medio.
- [ ] 21. `sonnet` Congelación en un commit propio: `stage: "frozen"`, `code_tree_sha`, semilla,
  umbrales. Aceptación: desde ese commit hasta la lectura, `git diff <congelación> --
  src/ac2fb/defence src/ac2fb/reliability protocol/` vacío; test contra `HEAD` que el reservado
  sigue cerrado con un cambio de código posterior.
- [ ] CP2. **[Javier] lun 16 nov.** Aprueba la congelación y queda avisado de que la lectura del
  reservado es irreversible. Si D5 ya mató la pregunta, aprueba la rama B: la capa 2 se queda en
  los 10 de calibración, salvo que Javier decida abrir el reservado solo para ella (irreversible).

## Fase 3: reservado y capa 2 completa (lun 16 nov a dom 29 nov)

- [ ] J4. **[Javier]** Lectura única del reservado: autoriza y lanza `ac2fb heldout read` (o lo
  autoriza por escrito a quien lo lance). Paso irreversible.
- [ ] 22. `opus` Veredicto mecánico del reservado (D6) por partido en `reports/heldout.json`, con
  el commit de la lectura; `stage: "read"`. Se publica como cae.
- [ ] 23. `sonnet` Capa 2 en los 20 partidos (ya permitido): mapa de fiabilidad por métrica y
  partido (presión local, distancia al rival más cercano, altura de línea, anchura, longitud, área
  del bloque) en `reports/reliability.csv`. Aceptación: las cifras de calibración coinciden con
  las de la 9; mutación anotada.

## Fase 4: empaquetado (lun 30 nov a dom 6 dic)

- [ ] 24. `sonnet` Las dos figuras (máximo de las bases), generadas por `ac2fb figures` desde
  `reports/`: figura 1, detección por distancia al balón y sensibilidad por métrica, por partido;
  figura 2, el efecto de la capa 3 por partido en V0, V1 y V2, calibración y reservado (o la
  muerte, en la rama B). Aceptación: test que regenera y compara; cada número de una etiqueta sale
  de un artefacto.
- [ ] 25. `sonnet` `--check` en cada comando que escribe un artefacto (recalcula y compara; con
  fixtures dice cuánto verificó, `PARTIAL n/20`). Aceptación: mutar un valor de un JSON hace
  fallar su `--check`.
- [ ] 26. `sonnet` API pública mínima y documentada (`reliability.sensitivity`, lector de silver,
  esquema del Parquet largo) y un `examples/sensitivity.py` que corre sobre el sintético.
  Aceptación: el ejemplo corre en CI.
- [ ] 27. `sonnet` `full-build.yml`: `workflow_dispatch`, caché de `data/raw` por huella del
  manifiesto, build completo, todos los `--check` y `clean_clone_check.sh` en `ubuntu-latest`.
  Aceptación: una ejecución en verde con su enlace; el árbol queda limpio.
- [ ] 28. `sonnet` `scripts/readme_check.py` y su test: cuenta palabras del README (todo el texto,
  bloques de código incluidos, sin comentarios HTML) ≤ 1000, figuras más tablas ≤ 2, y cada
  número del README presente en algún artefacto de `reports/`. Mutaciones: README de 1001
  palabras, tercera tabla, número inventado; las tres fallan.
- [ ] 29. `sonnet` Clip de 10 s para el vídeo: una recepción con los defensores detectados en
  relleno y los extrapolados en hueco, renderizado desde silver por `ac2fb clip` (matplotlib).
- [ ] J5. **[Javier, opcional]** Abrir el issue en kloppy con el texto de la 15.

## Fase 5: entrega (lun 7 dic a vie 18 dic)

- [ ] 30. `sonnet` README en inglés: qué es, procedencia (abajo), capa 2, capa 3, método en
  corto, reproducir (bloque de clon limpio), reutilizar, licencia y datos. Aceptación: la 28 en
  verde; lectura de Javier.
- [ ] 31. `sonnet` Guion del vídeo (≤ 60 s, unas 140 palabras, voz de Javier) con plano por frase
  (figura 1, figura 2, clip de la 29); cada cifra con su artefacto.
- [ ] J6. **[Javier]** Repo público (si no lo era) y comprobar que la `full-build` en verde es del
  commit que se entrega.
- [ ] J7. **[Javier]** Grabar el vídeo con su voz (máximo 1 minuto) y subirlo a YouTube
  (visibilidad admitida: PENDIENTE DE CONFIRMAR en las bases).
- [ ] J8. **[Javier]** Enviar en submissions.analytics-cup.org. Objetivo mar 15 dic; límite vie 18.

## Cómo se declara la base (cumplir "disclosed" sin parecer "lightly adapted")

- Árbol separado: `src/ac2fb/base/` es lo copiado; todo lo demás es nuevo. Cada fichero de
  `base/` abre con su origen (`tracklab`, ruta, commit) y sus cambios.
- Historia de git: el primer commit importa solo la base; `git diff <import>..HEAD --stat` es el
  trabajo nuevo. `reports/provenance.json` imprime líneas de `base/` frente al resto y el README
  cita esa cifra, no una estimación.
- Lo previo que se reutiliza como dato (la proporción detectada por partido que midió tracklab) se
  dice como previo; lo nuevo es la sensibilidad y la pregunta. P5 (carreras) no se reutiliza.
- Borrador de la sección del README (unas 70 palabras, en inglés):

  > **Provenance.** `src/ac2fb/base/` (ingest verified against a pinned manifest, bronze, conformed
  > frames and events) is the author's prior work, copied under MIT from his private repository
  > *tracklab* at commit `<sha>`; [`docs/provenance.md`](docs/provenance.md) lists every file and
  > what changed. Everything else was written for the Analytics Cup: the reliability layer, the
  > defensive question, its protocol and held-out reading, figures and tests (`<n>` of `<m>` lines,
  > `reports/provenance.json`).

## Choques con las bases detectados al planificar

1. **Cuota LFS de SkillCorner.** Out of the box depende de bajar 1.823.448.331 B por
   `media.githubusercontent.com`; si la cuota del repo de SkillCorner se agota durante la Cup, la
   descarga falla. Mitigación: decisión 5 y mensaje de error que nombra `--from-existing`.
2. **kloppy (recurso sugerido) pierde `is_detected`** en 3.19.1: la capa 2 no se puede construir
   encima. Mitigación: decisión 4; el hallazgo entra en el README.
3. **"Lightly adapted".** Unas 2.250 líneas copiadas: el trabajo nuevo tiene que superarlas y el
   README lo cuenta con la cifra de `provenance.json`; la capa 2 tiene que valer sola (rama B).
4. **"Todo salvo los datos"**: decisión 3 (fixtures sintéticos). **París**: J1 antes de seguir.
5. **1000 palabras y 2 figuras o tablas**: reproducción y procedencia comen unas 200 (hipótesis);
   resultados en prosa con cifras y las dos figuras, sin tablas.

## Verificación

- [ ] V. Verificación. Gate, desde la raíz del repo, en este orden:
  ```
  uv sync --locked
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy src
  uv run pytest -q
  uv run python scripts/readme_check.py
  bash scripts/clean_clone_check.sh
  ```
  Criterio de aceptación agregado: todo lo anterior en verde en local y la `full-build` de GitHub
  Actions en verde en `ubuntu-latest` sobre el commit que se entrega (enlace a la ejecución);
  README ≤ 1000 palabras contadas por script y ≤ 2 figuras o tablas; `LICENSE.md` presente; clon
  limpio OK en Linux con el tiempo impreso; ningún número del README, del guion ni de las figuras
  sin un artefacto de `reports/` que lo imprima; `protocol.json` en `read` (o en `design`/`frozen`
  con D5 documentado, rama B) y su historia en git; ninguna ruta pública lee el reservado fuera
  del guard; cada test nuevo con su mutación anotada. Revisión adversarial del diff completo
  (`git diff <import>..HEAD`) con el subagente `revisor-adversarial`, repetida sobre los arreglos
  hasta que no salga nada alto ni medio.
