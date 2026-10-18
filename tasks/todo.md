# ac2-football: entrada de fútbol a la Analytics Cup 2.0 (planificado y revisado el 2026-10-17)

Dos repos con nombre provisional hasta J2 (decisión 7): la entrada (`ac2-football`, paquete `ac2fb`)
y la base (`football-tracking-base`, paquete `ftbase`, carpeta hermana en `proyectos\`).
**Las cifras que no vienen del inventario son hipótesis** y van marcadas así hasta que una tarea
las imprima. Lo que no se pudo medir dice PENDIENTE DE CONFIRMAR.

## La entrada en tres capas

- **Capa 1, base (trabajo previo, publicado aparte y declarado).** Ingesta verificada por sha256
  contra manifiesto, bronze, frames y eventos conformados, extraídos de tracklab (privado, MIT) a
  un repo público propio (`ftbase`, decisión 7) que la entrada fija como dependencia.
- **Capa 2, fiabilidad (nuevo, la columna vertebral, no puede morir).** Cuánto cambia cada métrica
  de posicionamiento defensivo al separar lo visto de lo extrapolado (`is_detected`), por partido
  y por longitud del hueco, con una referencia medida por amputación. tracklab midió la PROPORCIÓN
  detectada; lo nuevo es la SENSIBILIDAD y el hallazgo de que lo "extrapolado" es interpolado (m11).
- **Capa 3, aplicación (nuevo, con permiso para morir).** Una pregunta de presión o posición
  defensiva con la incertidumbre del tracking dentro. La pregunta NO está elegida: la elige Javier
  en CP1 con las cifras de las sondas delante. Está diseñada para que las dos salidas se publiquen:
  si el efecto vive solo en lo extrapolado, ese es el hallazgo de la capa 2.

## Bases oficiales (leídas en la fuente el 2026-10-17, citadas tal cual)

- Entrega **18 Dec 2026** (62 días desde hoy). Finalistas 8 Jan 2027. Final Europa 17 Feb 2027 en
  París, presencial, viaje no pagado, 500 EUR por finalista; ganador regional, grant de 1.500 EUR.
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

Fuente: sondas de solo lectura de esta sesión (`m1.py` a `m11.py` y sus `.out` en
`C:\Users\javie\AppData\Local\Temp\claude\C--Users-javie-Desktop-proyectos-tracklab\32ca1c69-cc35-4afa-8188-48fc580d005f\scratchpad\ac2\`),
DuckDB en memoria sobre `tracklab/pipeline/data` (silver `frames`, bronze `dynamic_events`,
`phases_of_play`, `match_players`, `dim_team_period`); ninguna escribe en tracklab. m1 a m9 miran
los 20 partidos; **m10 y m11 solo los 10 de calibración del split A**. **La tarea 12 re-deriva en
código las cifras de capa 2 y tiene que dar las mismas**; si no, se corrige este plan. "Por
partido" = mínimo a máximo (mediana entre paréntesis).

**Fuente y peso.**
- `SkillCorner/opendata`: HEAD de `master` el 2026-10-17 es `4340d274572876239c154c90bc507a9b3250a656`
  (`git ls-remote`), el mismo commit que fija `tracklab/pipeline/manifest/sources.json`.
- Fuente de fútbol del manifiesto: 85 ficheros, 1.919.842.163 B; los 20 de tracking van por LFS
  (1.823.448.331 B, unos 91 MB por partido: derivado, no medido por fichero). El manifiesto trae
  además baloncesto (35) y body pose (2): no se copian.
- Silver `frames` de fútbol: 20.213.849 filas (19.334.986 de jugador, 878.863 de balón), igual
  que `tracklab/web/public/data/stats.json`. Jugador detectado 56,8 % de las filas, balón 80,2 %.
  Clon limpio de tracklab con descarga real de los dos bundles: 670 s (`tracklab/tasks/todo.md:3420`).

**Eventos (`dynamic_events`, bronze: 94.361 filas, 325 columnas; el CSV trae 322).**
- Por tipo: `passing_option` 48.308, `player_possession` 18.710, `on_ball_engagement` 17.445,
  `off_ball_run` 9.898, los cuatro en los 20 partidos.
- `on_ball_engagement` por partido 754 a 1.025 (874); subtipos `pressure` 4.636, `recovery_press`
  4.084, `pressing` 3.847, `other` 3.251, `counter_press` 1.627, todos con `frame_physical_start`,
  que adelanta a `frame_start` en el 36,3 % (nunca después; p90 15 frames). Duración mediana 12
  frames (p90 32).
- `overall_pressure_start` solo en `player_possession`: 16.604 de 18.710 (84,2 a 92,6 % por
  partido, 653 a 1.056): `no_pressure` 4.683, `medium` 4.390, `low` 3.442, `high` 3.384,
  `very_high` 705, nulo 2.106. `fully_extrapolated` (bandera del proveedor) solo en
  `passing_option` (7.398 de 48.308) y `player_possession` (276 de 18.710; 0,4 a 3,9 % por partido).
- `last_defensive_line_x_start` en 18.697 de 18.710 posesiones. `phases_of_play`: 8.834 fases,
  `team_out_of_possession_width/length_start` en 8.494. **tracklab nunca usó** columnas de
  presión ni de `on_ball_engagement` (grep en `src`, `reports`, `tasks`: solo recuentos).

**Detección alrededor de la presión (m3, m4, m5, m9; 20 partidos).**
- Defensor que presiona (`player_id` del `on_ball_engagement`) detectado en `frame_start`: 92,5 a
  96,8 % por partido; entero en `[frame_start - 1 s, frame_end + 1 s]`, 76,7 a 91,1 % (86,2).
- En la recepción (`frame_start` de `player_possession`): poseedor detectado 93,6 a 98,2 % (96,8).
  Rivales a 5 m o menos del poseedor detectados 93,1 a 98,6 % (97,0); a 20 m 87,7 a 96,2; más
  allá de 20 m 33,0 a 62,1 (46,9). Posesiones sin rival a 5 m: 42,3 a 68,4 %. De las 8.066 con
  algún rival a 5 m, con al menos uno extrapolado: 1,8 a 8,5 % (3,6).
- **Línea defensiva en la recepción** (4 jugadores de campo más retrasados del rival, sin portero,
  18.657 posesiones): fracción detectada 37,4 a 69,7 % (51,7); los 4 a la vez en el 19,6 a 56,1 %
  de las posesiones (34,3); el más retrasado, 28,6 a 60,1 % (43,3).
- **Bloque al inicio de fase** (los 11 sin balón, 8.461 fases): detectados 51,1 a 69,2 % (58,2);
  fases con los 11 detectados 0,5 a 5,9 % (2,8).
- Detección de jugadores por distancia al balón (1 de cada 10 frames): 0 a 5 m 82,5 a 91,4 %
  (86,3); 5 a 10 m 78,9 a 89,3 (83,8); 10 a 20 m 70,9 a 84,1 (77,4); 20 a 30 m 43,9 a 70,8
  (57,7); 30 a 40 m 26,0 a 51,8 (36,4); más de 40 m 11,6 a 26,9 (16,1).
- **Lo local es casi todo visto; lo global, la mitad modelo.** La capa 2 lo convierte en mapa.

**Cómo es lo extrapolado (m6, m7 en 20 partidos; m11 en los 10 de calibración).**
- Paso por 0,1 s, mediana por partido: detectado a detectado 0,200 m (0,184 a 0,218),
  extrapolado a extrapolado 0,129 (0,112 a 0,140), extrapolado a detectado 0,171 (0,136 a 0,200).
- Tramos extrapolados: 98.487, mediana 47 frames (4,7 s), p90 175 (17,5 s), p99 587 (58,7 s).
- **Lo "extrapolado" es interpolado (m11).** Salto al readquirir la detección por longitud del
  hueco, mediana: ≤ 1 s 0,212 m; 1 a 5 s 0,156; 5 a 20 s 0,175; **más de 20 s 0,202** (p90 0,438,
  p99 0,664), frente a 0,184 a 0,214 del paso detectado a detectado (p90 0,424 a 0,474); por
  partido, en huecos de más de 20 s (318 a 539), 0,174 a 0,231 m. Un predictor acumularía error con
  el hueco; aquí la posición aterriza en la readquirida: **el proveedor interpola con el futuro
  visto** (paso dentro de huecos largos 0,137 m, más suave). Posiciones extrapoladas por hueco, por
  partido: ≤ 1 s 0,3 a 0,6 %; 1 a 5 s 15,8 a 19,5; 5 a 20 s 40,6 a 46,8; **más de 20 s 34,9 a
  40,3 %**. Consecuencia (hipótesis hasta la 12): una trayectoria interpolada casi sin aceleración
  da residuo sobre velocidad cero por construcción: toda métrica de REACCIÓN defensiva lee cero en
  los jugadores extrapolados.
- Cadencia (m7, exploratoria): el hueco entre quiebros de detectados es 1 frame en el 57,6 a
  59,8 % y decae sin pico; el umbral cae dentro del ruido de redondeo de 1 cm. Lo cierra la 13.

**La recepción y la línea, solo calibración (m10; 9.178 posesiones, 8.959 con línea de 4,
presión y balón en `t` y `t - 1 s`). Signo: + es la línea retrocediendo hacia su portería.**
- `frame_start` de `player_possession` es la recepción: balón a 1,18 a 1,37 m del poseedor
  (mediana), a 2 m o menos en el 76,4 a 86,6 %, a 1 m o menos solo en el 28,6 a 38,1 %.
- **La línea sigue al balón.** En el segundo previo a la recepción, tras un balón que retrocedió
  más de 2 m la línea sube 0,80 a 1,21 m; tras uno que avanzó más de 2 m baja 0,78 a 1,16 m;
  lateral, −0,18 a +0,16 (sd por estrato 1,14 a 2,10 m). 10 de 10 partidos, los dos signos.
- **El confundidor de C2.** Presionado (rival a 5 m o menos, 38,5 a 58,7 % de las recepciones)
  frente a libre, desplazamiento previo de la línea en 1 s: +0,00 a +0,50 m (en 2 s, +0,03 a
  +1,04; sd 1,67 a 1,96 y 3,20 a 3,75), 10 de 10 no negativos, porque el presionado recibe tras un
  balón hacia delante (+0,55 a +1,79 m) y el libre tras uno hacia atrás (−0,53 a −1,56). **Sin
  estratificar por el balón entrante, "presión, línea arriba" sale solo de esto.** Dentro de
  estratos de dirección, presionado menos libre: hacia atrás −0,34 a +0,42 (7 de 10 positivos),
  hacia delante −0,65 a +0,14 (8 de 10 negativos, agregado −0,27 m, 0,14 sd), lateral −0,47 a
  +0,38. Queda un residuo del tamaño de 0,1 a 0,15 sd que D3 tiene que juzgar.
- La etiqueta del proveedor es monótona con la geometría (rivales a 5 m; distancia al más cercano):
  `no_pressure` 0,00 y 11,6 m; `low` 0,20 y 6,9; `medium` 0,69 y 4,6; `high` 1,35 y 2,6;
  `very_high` 1,72 y 1,3. **La visibilidad va con la causa**: con presión se ven 2,51 de los 4 de
  la línea (los 4 en el 43,9 %), sin presión 1,78 (28,6 %): "línea vista" selecciona recepciones
  presionadas y cercanas al balón, y toda variante restringida declara ese sesgo.

**kloppy.** kloppy 3.19.1 (última en PyPI hoy): el deserializador `skillcorner` lee `player_data`
sin `is_detected` (grep del paquete instalado en esta sesión). Lo vuelve a comprobar la tarea 10.

**Código a copiar al repo base (lectura de un subagente sobre tracklab `pipeline/`).**
- Casi tal cual: `ingest/{fetch,lfs,verify,manifest,local}.py` (sin HuggingFace, `freeze` ni
  baloncesto), `bronze/common.py`, `bronze/football/{tracking,events,meta}.py`,
  `formats/csvschema.py`, dos esquemas JSON, `quality/{common,detection}.py`, `paths.py`.
- Se reescribe: silver sin dbt (`frames.sql` 163 líneas, `events.sql` 287 y dims, DuckDB plano sin
  `ref()/source()` ni baloncesto); la orientación de fútbol (unas 250 de las 1.839 de
  `silver/orientation.py`); el CLI (unas 80); los 6 tests dbt de fútbol como SQL de 0 filas. No se
  copian `formats/football.py`, `runs/` (P5), `build.py`, Dagster, dbt, pose ni publish.
  Estimación (hipótesis): **unas 2.250 líneas copiadas y 460 reescritas**; dependencias `duckdb`,
  `pyarrow`, `httpx`; Python >= 3.13. Tiempo y RAM del build: PENDIENTE DE CONFIRMAR (tarea 9).
  `gap_len` no existe en tracklab (grep, 0 ocurrencias): es capa 2 y va en la entrada.

**Contaminación declarada.** m1 a m9 calcularon en los 20 partidos solo recuentos, nulos,
vocabularios, detección y pasos. m10 y m11, solo en los 10 de calibración: m11 pasos y huecos; m10
**el desplazamiento de la línea rival ANTES de la recepción** (`[t - 2 s, t]`) por presión y por
dirección del balón entrante. No es el desenlace de C2 (`[t, t + W]`), pero sí su pre-tendencia y
el contraste "la línea sigue al balón": en calibración solo valen como instrumento (D1) y
diagnóstico (D3), nunca como hallazgo; en el reservado nadie los ha mirado. **Ningún desenlace de
C1, C2 ni C3 en ningún partido**: no se miró `stop_possession_danger`, `force_backward`,
`beaten_by_*`, `possession_danger`, `end_type` contra presión, `last_defensive_line_*_end` ni
ningún movimiento posterior a una recepción. tracklab: P5 miró carreras en los 10 de calibración
del split A y nunca abrió su reservado; P6 leyó pose de 1925299 y 1996435 (calibración).

## Preguntas candidatas de la capa 3 (se elige una en CP1)

Las tres miden presión con el tracking en la recepción (`t` = `frame_start` de
`player_possession`, confirmado como recepción en m10), porque ahí el poseedor y sus rivales
cercanos están vistos (97,0 %). Difieren en dónde vive el desenlace, y por tanto en cuánto muerde
la capa 2. **Las tres comparten el confundidor medido en m10: el movimiento del balón en
`[t - W, t]` decide a la vez la presión y lo que la defensa hace, así que la causa se compara
siempre dentro de estratos de dirección y longitud del balón entrante y de tercio, y D3 mide lo
que queda.**

**C1. "Pressure the camera sees": presión en la recepción y progreso inmediato del balón.**
- Pregunta: ¿la presión sobre el poseedor en la recepción reduce el avance del balón hacia la
  portería en `[t, t + W]`, dentro del mismo estrato, y sobrevive a quitar los rivales
  extrapolados?
- Instrumento: índice de presión geométrico (rivales a 10 m o menos con peso por distancia y por
  estar entre poseedor y portería); debe crecer con los 5 niveles de `overall_pressure_start`
  (la etiqueta contrasta, nunca es desenlace; m10 ya ve monótonos los rivales a 5 m). Desenlace:
  avance del balón en el marco de ataque en `[t, t + W]`, del tracking.
- Capa 2: muerde poco (3,6 % de posesiones con un rival extrapolado a 5 m); el balón está
  detectado en el 75,45 a 85,38 % de los frames con balón (`docs/formats/football.md`).
- Riesgo de morir: **medio** (el receptor decide, no la defensa). Encaje: Relevance alta,
  Methodology media-alta, **Originality baja** (presión muy modelada y ya etiquetada por el
  proveedor), Communication alta, Open-source media.

**C2. "Ball pressured, line steps up": respuesta de la última línea a la presión sobre el balón.**
- Pregunta: dentro del mismo estrato de balón entrante y tercio, cuando el poseedor recibe
  presionado, ¿la última línea rival sube en `[t, t + W]` más que cuando recibe libre, más allá de
  lo que su velocidad en `t` predecía, y lo hace también la línea que la cámara vio? Es el
  principio "balón presionado, línea arriba" como definición geométrica, sin leer intención.
- Instrumento: altura de la línea (media de los 4 jugadores de campo más retrasados, sin portero,
  los mismos jugadores seguidos en el tiempo, nunca re-rankeados dentro de la ventana), contrastada
  contra `last_defensive_line_x_start` del proveedor (18.697 posesiones), y el contraste de
  dirección forzada ya visto en calibración: la línea sigue al balón entrante (D1). Causa: presión
  geométrica en `t` (umbral fijado en el protocolo desde S2). Desenlace: desplazamiento de la
  línea en `[t, t + W]` menos el que predecía su velocidad en `t`; pre-tendencia la misma
  estadística en `[t - W, t]`, por estrato, que tiene que quedar por debajo de la mitad del efecto.
- Capa 2: **muerde en el desenlace y en la selección**: línea detectada al 51,7 %, entera en el
  34,3 %, más vista con presión (43,9 frente a 28,6 %). Si lo extrapolado es interpolado casi
  lineal, su residuo es cero por construcción: V0 diluye el efecto y V1 (línea vista) lo muestra;
  si V1 no lo muestra, el efecto era modelo. Las dos salidas se publican.
- Riesgo de morir: **medio-alto** (pre-tendencia dentro de estrato ya en 0,1 a 0,15 sd; potencia
  en V1). Encaje: Relevance muy alta (presión, forma, "defensive decision-making"), Methodology
  alta, **Originality alta**, Communication alta (la línea con los extrapolados en hueco),
  Open-source alta.

**C3. "The block the camera does not see": compacidad del bloque y fase de juego.**
- Pregunta: ¿las diferencias de compacidad del bloque sin balón (anchura, longitud, área) entre
  tipos de fase sobreviven cuando se mide solo lo visto, o las fabrica lo extrapolado?
- Instrumento: anchura y longitud propias al inicio de fase contra
  `team_out_of_possession_width/length_start` del proveedor (8.494 fases). Capa 2: muerde todo
  (bloque detectado al 58,2 %, entero en el 2,8 %): solo da una banda, no un valor verdadero.
- Riesgo de morir: **bajo como medida, alto como hallazgo** (lo probable es "no identificable con
  retransmisión": negativo útil, poca aplicación). Encaje: Relevance muy alta, Methodology media,
  Originality media-alta, Communication alta, Open-source alta.

**Descartada: el efecto de un `on_ball_engagement` sobre el poseedor o la línea.** Es el diseño de
P5 (evento con inicio del proveedor): el arranque de la presión lo dispara el mismo pase que mueve
a la línea (mismo confundidor que C2) y el instante es dudoso (`frame_physical_start` adelanta en
el 36,3 %). Sus cifras quedan para la capa 2.

**Recomendación provisional: C2 con el diseño estratificado**, si S2 da un instrumento de línea
que concuerda con el proveedor, una pre-tendencia dentro de estrato por debajo de 0,15 sd en al
menos 8 de 10 partidos y MDE80 ≤ 0,3 sd en V1; si no, C1; C3 solo como respaldo descriptivo. Lo
decide CP1, no este plan.

## Reglas

- **Regla de oro.** Ninguna cifra en README, vídeo, figuras ni plan sin un artefacto de `reports/`
  que la imprima. **Por partido, siempre**, veredicto reservado, un negativo junto a cada positivo.
- **El desenlace es geometría del tracking**; las etiquetas del proveedor (`overall_pressure_*`,
  `last_defensive_line_*`, anchura de fase) solo contrastan el instrumento. **La causa, en un
  instante que el efecto no pudo causar**, validada antes con cinemática (P5) y **comparada dentro
  de estratos del movimiento previo del balón** (m10: el balón es la causa común); pre-tendencia
  por debajo de la mitad del efecto, en valor absoluto.
- **Toda variante restringida a lo visto declara su selección** (qué recepciones entran, a qué
  distancia del balón, con qué presión), porque la visibilidad va con la causa (m10).
- **Intención no reclamable**: "decision-making" solo como definición geométrica medida.
- **El protocolo es código y se congela antes del reservado**; un umbral que falla no se mueve. La
  capa 2 corre solo en calibración hasta la lectura. Tests que pueden fallar (mutación anotada).
- **Un agente por repo; nadie escribe en tracklab; nada de análisis en la base.** LF siempre. 0 €.
- **Fuera de alcance:** EPV propio, rankings de jugador o equipo, predicción de resultados, vídeo,
  body pose, baloncesto, cualquier dato fuera del commit fijado de `SkillCorner/opendata`.

## Decisiones, con su porqué (1 a 6 aprobadas en J3; la 7 la aprueba Javier en J2)

1. **Split A de P5, declarado hoy, antes de calcular ningún desenlace.** Calibración 1874553,
   1886347, 1925299, 1959846, 1996435, 1996436, 2007448, 2010085, 2011166, 2015213; reservado
   1899585, 1927964, 1953632, 1986691, 2006229, 2006363, 2007721, 2013725, 2016236, 2017461.
   Queda 5 y 5 por precisión de coordenadas de eventos y 2 y 3 por metraje fuera de periodo
   (`tracklab/tasks/todo.md:4767-4774`), y ese reservado nunca se abrió.
2. **Base en DuckDB + Python, sin dbt ni Dagster.** Out of the box ligero; se pierden lineage y
   docs de dbt, no los tests. Python 3.13 fijado con uv, como tracklab (uv instala Python).
3. **Fixtures sintéticos en formato SkillCorner, no un corte real**: el repo va "con todo salvo
   los datos", CI por push no tira de la cuota LFS ni redistribuye dato del proveedor; datos
   reales solo en `full-build` (manual, caché por huella del manifiesto). Ninguna cifra sale de
   los sintéticos: el README lo dice y `readme_check` lo impone.
4. **Lector propio, kloppy no es dependencia** (3.19.1 pierde `is_detected`). Salida en Parquet
   largo documentado (`match_id, period, frame, player_id, team_id, x, y, is_detected, gap_len`);
   un issue o PR a kloppy es el "develop further" natural, y el uso del grant.
5. **`--from-existing <dir>` se conserva y hay camino rápido `--match <id>`**: si se agota la
   cuota LFS de SkillCorner, un clon local de `opendata` se verifica en sitio; y un juez puede
   reproducir un partido (unos 91 MB, hipótesis) antes de bajar 1,82 GB.
6. **Variantes de capa 2 fijadas para toda métrica de equipo**: V0 todo; V1 unidades con los
   jugadores de la métrica detectados en toda la ventana (selección declarada); V2 el efecto por
   número de jugadores detectados (0 a 4 en la línea), monótono si lo extrapolado atenúa; más la
   referencia por amputación (26). Sustituye a "sin extrapolados", que para una línea es otra línea.
7. **Dos repos: la base en un repo público propio, la entrada la fija como dependencia.** Con
   tracklab privado, una base copiada dentro de la entrada no encajaba al pie de la letra en
   "pre-existing ... open-source projects ... appropriately licensed and disclosed" (bases, arriba).
   `ftbase` (tarea 2: MIT, CI, tests de contrato, procedencia desde tracklab `686508a`) es open
   source por sí mismo; la entrada lo fija en `pyproject.toml` y todo su `git log` es trabajo de la
   Cup. Frontera: en la base solo lo que ya existía en tracklab para fútbol más dos añadidos sin
   análisis que necesita para funcionar y probarse sola (`--match`, generador sintético),
   etiquetados `nuevo`; en la entrada todo lo demás, `gap_len` incluido. Coste: dos gates y dos CI;
   un arreglo en la base pide tag nuevo y re-fijar (nunca análisis); el clon limpio depende de
   GitHub; el repo base nace en octubre de 2026 con código anterior, y los dos README lo dicen.

## Fases y fechas

| Fase | Fechas | Contenido | Horas (hipótesis) |
|---|---|---|---|
| 0 | sáb 17 oct a dom 25 oct | Repo base público (copia, CI, procedencia, `v0.1.0`); entrada con la base fijada, clon limpio, kloppy | 14 a 20 (+2 a 4 por el segundo repo) |
| 1 | lun 26 oct a dom 1 nov | Split y guard, núcleo de capa 2, sondas, potencia | 12 a 16 |
| CP1 | lun 2 nov | **Javier elige la pregunta** | 1 |
| 2 | lun 2 nov a dom 15 nov | Protocolo, sintéticos, calibración, congelación | 14 a 18 |
| CP2 | lun 16 nov | Javier aprueba la congelación | 1 |
| 3 | lun 16 nov a dom 29 nov | Lectura única del reservado, capa 2 completa, amputación | 8 a 12 |
| 4 | lun 30 nov a dom 6 dic | Figuras, `--check`, API, CI Linux completo | 8 a 10 |
| 5 | lun 7 dic a vie 18 dic | README, vídeo, clon limpio, entrega (objetivo mar 15 dic) | 8 a 12 |

Holgura real: la fase 1 es el cuello (8 tareas en 7 días); si CP1 se retrasa, se come la semana
libre de la fase 3 (la lectura del reservado dura un día). Rama B: la fase 3 entera es capa 2.

## Plan B: si la capa 3 muere (en sonda, calibración o reservado)

Se publica como cae, con el negativo bien medido. La entrada cuenta: (1) la base, declarada; (2)
**la capa 2 como contribución principal**: qué métricas defensivas aguantan la retransmisión y
cuáles son sobre todo modelo, por partido y por longitud de hueco, con el sesgo de visibilidad y
la referencia por amputación; (3) dónde murió la pregunta, con las cifras por partido de esa sonda
y lo que no se abrió. La figura 2 enseña la muerte. Si en CP1 mueren las tres, rama B ese día.

## Fase 0: repo base `[base]` y entrada `[entrada]` (sáb 17 oct a dom 25 oct)

- [x] J1. **[Javier]** Registrarse en la Cup (región Europa) y confirmar que puede asistir a París
  el 17 Feb 2027 (las bases lo piden antes de entregar). Antes del dom 25 oct; si no, replantear.
  **Cerrado el 2026-10-18: registro hecho y asistencia a París registrada (Javier).**
- [x] J2. **[Javier]** Aprobar la decisión 7 y elegir nombres: base (`football-tracking-base`,
  `ftbase`, carpeta hermana en `C:\Users\javie\Desktop\proyectos\`; sin "ac2" ni "tracklab", que
  se lea como proyecto propio) y entrada (`ac2-football`, `ac2fb`). **Hecho el 2026-10-17:
  decisión 7 y nombres aprobados; falta cuándo se publica la base y quién crea los repos (`gh`
  tiene sesión en `javiersr1996`; crearlos es de Javier o con su sí explícito).** Crear
  los dos repos en GitHub y **hacer público el repo base**: recomendado ya; límite antes de la 8,
  cuya CI lo instala sin token, como un juez. Publicar es irreversible hacia fuera: lo copiado de
  tracklab para fútbol queda a la vista y clonable aunque luego se vuelva privado. Antes del mar 20
  oct (recomendado); límite jue 22 oct: más tarde, 8 a 10 pasan a la semana siguiente y la fase 1
  pierde dos días, lo mínimo que se mueve.
  **Cerrado el 2026-10-18:** Javier eligió "yo, pública al tag": Claude creó los dos repos
  privados con `gh` (`javiersr1996/football-tracking-base`, `javiersr1996/ac2-football`) y hace
  pública la base al cerrar la 7 (`v0.1.0`), antes de la 8, avisando al hacerlo.
- [x] J3. **[Javier]** Aprobar este plan y las decisiones 1 a 6. Aprobado el 2026-10-17 (revisión
  de Fable, `ca5712a`); ejecución en modo mixto según las etiquetas.
- [x] 1. `sonnet` Esqueleto: `pyproject.toml` (uv, hatchling, `ruff` línea 100 y reglas
  `E,F,I,UP,B`, `mypy --strict`, `pytest`), `.python-version`, `.gitattributes` con `* text=auto
  eol=lf`, `.gitignore` con `data/`, `LICENSE.md` (MIT, Javier Sánchez Rueda, 2026). Paquete
  `src/ac2fb/` con `base/` (copiado), `reliability/` (capa 2), `defence/` (capa 3), `protocol/`
  (split, guard, congelación), `cli.py`. Aceptación: `uv sync --locked` y el gate (V) en verde con
  un test trivial que se rompe al mutar.
  Medido: gate en verde con 3 tests; mutar `prog` en `cli.py` rompe 2 de 3; todo `i/lf`.
- [x] 2. `sonnet` `[base]` Repo base con `git init` nuevo (sin historia de tracklab, para no
  filtrar el resto del repo privado). **Primer commit, solo la copia literal** de los ficheros de
  tracklab `686508a` listados en `docs/provenance.md` (fichero, ruta en tracklab, estado
  `copiado`), mensaje "Import football base from tracklab@686508a (author's prior work, MIT)".
  Segundo commit, el esqueleto con las herramientas de la tarea 1 (`name = "ftbase"`, `py.typed`
  para el mypy estricto de la entrada, `.python-version`, `.gitattributes` LF, `.gitignore` con
  `data/`, `LICENSE.md` MIT) y un README corto en inglés (qué es, instalar, los tres comandos, datos
  y LFS, procedencia, licencia). Aceptación: `git show --stat <import>` lista solo ficheros de la
  tabla; gate (V) en verde desde el segundo commit con un test trivial que se rompe al mutar.
  Medido: commits `a3ae656` (importación) y `13b6aa8` (esqueleto) en `football-tracking-base`; 49 ficheros
  importados con blobs idénticos a tracklab `686508a` (49 de 49 por hash) y `docs/provenance.md` con las 49 filas;
  gate en verde con 3 tests (`sync --locked`, ruff, format, mypy, pytest); mutar `prog` en `cli.py` rompe 2 de 3;
  todo `i/lf`. Desviaciones: git no tiene `user.name` global (solo el correo), el autor es `Javier Sánchez Rueda`
  fijado en local como en los commits de tracklab; no se importó `cli.py` ni `tests/conftest.py`; `test_ingest.py`
  y `test_frozen_schemas.py` mezclan baloncesto y se importaron enteros (recorte en las tareas 3 y 4); la primera
  importación (43) dejó fuera semillas, `silver/schema.yml`, `sources/{football,common}.yml` y la macro
  `test_unique_combination`, que silver usa: se rehízo el commit, sin publicar, con los 6 (`quality/` no). `pipeline/` va excluido del gate (ruff
  `extend-exclude`) hasta cerrar la tarea 5: quitar esa exclusión entonces (también anotado en el README de la base).
- [x] 3. `sonnet` `[base]` Ingesta: manifiesto recortado a `opendata-football` (85 ficheros,
  commit `4340d27`), `fetch` sin HuggingFace ni `freeze`, `verify`, `lfs`, `manifest`, `local`
  (`--from-existing`) y `--match <id>` (los 4 ficheros de un partido más `matches.json`; nuevo,
  etiquetado así). Cabecera en cada fichero copiado: origen en tracklab, commit, cambios; renombrar
  `TRACKLAB_DATA_ROOT`, `User-Agent` y metadatos `tracklab.*`. Aceptación: `ftbase ingest` verifica
  los 85 (`failed: 0`); `--match 1874553` verifica 5 y dice `PARTIAL 5/85`; tests copiados de
  `test_ingest.py` sin baloncesto; mutación anotada (un sha256 cambiado tiene que fallar).
  Medido: commits en `football-tracking-base` `4662782` (solo mueve con `git mv`, 0 cambios de contenido), `ad7ecfe`
  (manifiesto recortado a 85 ficheros, 322 líneas borradas y ninguna añadida, commit `4340d27`), `6de90a8` (adaptación) y
  `c3b1a49` (tests, procedencia, README); `uv add httpx` (0.28.1), sin más dependencias. `ftbase ingest --from-existing`
  contra `tracklab/pipeline/data/raw/opendata-football` (lectura: `ingest_local` solo hashea; el recibo va a `data/` de
  la base; el `_receipt.json` de tracklab conserva su fecha del 15 oct): `downloaded=0 verified=85 failed=0`, exit 0, 3,7 s.
  `ftbase ingest --match 1874553` con descarga real a un `data-dir` en el scratchpad: `downloaded=5 verified=5 failed=0
  PARTIAL 5/85`, 95.624.493 B (tracking 90.729.279), 5,0 s. Mutación: un sha256 del manifiesto cambiado (el primer
  agregado) da `verified=84 failed=1`, exit 1; restaurado, 85 y exit 0. Mutaciones de código (cada una rompe un test):
  `verify_file` sin comparar hash, `select_match` sin `matches.json`, descarga sin comprobar hash, `ingest_local` que da
  todo por bueno, sin `PARTIAL`. Gate en verde (`sync --locked`, ruff, format, `mypy --strict src`, `pytest -q`: 21
  tests, 0 saltados); `git ls-files --eol` todo `i/lf`. Procedencia: 46 `copiado`, 4 `reescrito` (`fetch.py`, `local.py`,
  `test_ingest.py`, `cli.py`), 1 `nuevo` (`select.py`). Desviaciones: sin argumento `source_id` en `ftbase ingest` (una
  sola fuente); `--match` toca `fetch.py` y `local.py` (de ahí `reescrito`) y el recibo gana `match_id` y `manifest_files`;
  manifiesto empaquetado en `src/ftbase/manifest/sources.json` (entra en el wheel, comprobado) en vez de `pipeline/manifest`;
  JSON sin cabecera, su origen consta en `docs/provenance.md`; añadidas filas de `select.py` y `cli.py` a la tabla;
  `lfs.py` conserva `parse_pointer` aunque `src` ya no lo llama (solo los tests); `test_ingest.py` mantiene sus tests de
  descarga y añade 8 de `--match` y `--from-existing`; el intermedio `4662782` no pasa ruff ni mypy (imports aún de
  tracklab); `pipeline/` sigue excluido del gate hasta la tarea 5; los metadatos `tracklab.*` viven en bronze (tarea 4).
- [x] 4. `sonnet` `[base]` Bronze: `common`, `tracking`, `events`, `meta`, `csvschema` y los dos
  esquemas JSON. Aceptación: `ftbase bronze` produce las tablas de fútbol con los mismos recuentos
  que tracklab (94.361 filas de eventos; tracking por partido igual) y las cabeceras congeladas
  (`header_sha256`); tests de contrato copiados y recortados; mutación anotada.
  Medido: commits en `football-tracking-base` `3b926ed` (solo `git mv`, 17 renombres, 0 cambios de contenido), `19324fc`
  (fuente: `ftbase.*`, metadatos Parquet `ftbase.*`, `ftbase bronze`, `uv add duckdb pyarrow` = 1.5.6 y 26.0.0, override de
  mypy para pyarrow), `3c307bf` (tests) y `ad627e9` (procedencia y README), empujados. `ftbase ingest --from-existing` contra
  `tracklab/pipeline/data/raw/opendata-football` (`verified=85 failed=0`) y `ftbase bronze` con `FTBASE_DATA_ROOT` en el
  scratchpad: 72,0 s. Comparación de solo lectura (`compare_bronze.py` en el scratchpad, DuckDB en memoria sobre Parquet de
  ambos) contra el bronze de tracklab, por partido y tabla: filas, esquema Arrow y `EXCEPT ALL` en los dos sentidos. Las 7
  tablas por partido coinciden en los 20 de 20 (0 diferencias): `dynamic_events` 94.361 (4.142 a 5.656 por partido),
  `phases_of_play` 8.834, `tracking_frames` 1.244.814, `tracking_objects` 19.334.986, `match` 20, `match_periods` 40,
  `match_players` 719; `matches` (fichero de temporada) 20 filas idénticas. Solo difieren los metadatos de pie de Parquet
  (`ftbase.*` en vez de `tracklab.*`), que la comparación excluye a propósito. Gate en verde (`sync --locked`, ruff, format,
  `mypy --strict src`, `pytest -q`: 59 pasan, 0 saltados, 17 deseleccionados); con datos reales `pytest -m realdata`: 17 de 17.
  Mutación: un byte de la cabecera de un CSV de eventos (`frame_start` a `frame_stars`, copia en el scratchpad) da exit 1 con
  `header does not match frozen dynamic_events`; una letra en una celda numérica da exit 1; restaurado, exit 0. Un dígito del
  `header_sha256` de un esquema JSON rompe `test_header_sha256_is_the_hash_of_the_frozen_column_names`, y renombrar una columna
  del esquema rompe el mismo test; recortar una fila del Parquet de un partido rompe 3 tests de contrato reales. Procedencia: 44
  `copiado`, 6 `reescrito` (`fetch.py`, `local.py`, `test_ingest.py`, `cli.py`, `test_frozen_schemas.py`,
  `test_football_events_bronze.py`), 2 `nuevo` (`select.py`, `manifest_helper.py`). Desviaciones: los tests de contrato leen el
  bundle real y no pueden correr en el gate sin datos, así que llevan el marcador `realdata` y `addopts = -m 'not realdata'`
  (deseleccionados, no saltados); `ftbase bronze` no lleva argumento de deporte y acepta `--tables tracking,meta,events`;
  `save_manifest` (quitado en la 3) se sustituye en los tests por `tests/unit/manifest_helper.py`; `common.py` conserva
  `build_season_csv_table` y las líneas de temporada (sin llamador hasta que haya agregados); quedan dos menciones históricas a
  `bronze/basketball/*` en los docstrings de `meta.py` y `tracking.py`; no se construyen `aggregates_*` ni `bodypose_*` de
  tracklab (fuera de la 4); `test_frozen_schemas.py` pasa de 28 esquemas a los 2 de fútbol; `pipeline/` solo conserva `dbt/` y
  `src/tracklab/__init__.py`, y sigue excluido del gate hasta la 5.
- [x] 5. `opus` `[base]` Silver sin dbt: orientación de fútbol desde `match.home_team_side`
  (reescrita, unas 250 líneas), dims, `frames` (**sin `gap_len`**: es capa 2, tarea 12), `events` y
  la vista `frames_attacking`, desde Python en orden; los 6 tests dbt de fútbol como aserciones SQL
  de 0 filas; lector de silver exportado (para la 11). Aceptación: 20.213.849 filas de `frames` y
  mismos recuentos por partido y `is_detected` que tracklab, comparados con un script de solo
  lectura contra `tracklab/pipeline/data`; signos de ataque opuestos por periodo en los 20;
  mutación: invertir un signo hace fallar la aserción.
  Medido: commits en `football-tracking-base` `ad38e3a` (solo `git mv`, 22 renombres, 0 cambios de contenido), `8c5942c`
  (SQL sin dbt ni baloncesto, `orientation.py`, `checks.py`, `build.py`, `read.py`, `ftbase silver`), `3f06892` (tests),
  `75cb933` (fuera `pipeline/` y su `extend-exclude`, README y procedencia) y `c4ffe15` (fixture de dos partidos), empujados.
  `ftbase silver` con `FTBASE_DATA_ROOT` en el scratchpad: 26,4 s (38,1 s la primera vez), pico de memoria del proceso
  1.796.546.560 B (working set, `GetProcessMemoryInfo` en `run_silver.py`), 101.974.624 B en disco (`frames` 99.162.422,
  `events` 2.787.526, zstd); 62 de 62 comprobaciones. Comparación de solo lectura (`compare_silver.py` en el scratchpad;
  `tracklab.duckdb` con `read_only=True`, sha256 y mtime iguales antes y después, `git status` de tracklab limpio): `frames`
  20.213.849 filas en los dos (la cifra del plan se confirma), 897.345 a 1.116.466 por partido, `is_detected` 11.683.552
  vistos y 8.530.297 extrapolados en los dos, `EXCEPT ALL` vacío en los dos sentidos por partido en las 14 columnas (todas
  comunes); `events` 107.204 (4.507 a 6.264), `EXCEPT ALL` vacío; `frames_attacking` 15.284.167 (664.217 a 867.629); dims
  con `EXCEPT ALL` vacío: `dim_sport` 1, `dim_period` 40, `dim_team` 13, `dim_match` 20, `dim_team_period` 80 (evidencia
  incluida), `dim_entity` 739. **20 de 20 partidos coinciden en todo; ninguna diferencia.** Signos: 40 periodos con dos
  equipos de signo opuesto en los 20 partidos, `assert_attack_signs_opposite` 0 filas, fases de acuerdo al 100 % en las 80
  filas. Gate desde la raíz ya sin exclusión (`sync --locked`, ruff, format, `mypy --strict src`, `pytest -q`: 88 pasan, 0
  saltados, 22 deseleccionados); `pytest -m realdata`: 22 de 22 (17 de bronze, 5 de silver). `schema.yml`: de sus 111 tests
  de fútbol (modelos y semilla), 56 de integridad portados a `checks.py` (unicidad de clave, `not_null` de columnas de clave o clave
  ajena, relaciones); 55 descartados: 13 `accepted_values` y 42 `not_null` de columnas que no son clave (entre ellos
  `frames.is_detected`, `x_m`, `y_m`, `period` y `attack_sign` en `dim_team_period` y `frames_attacking`), más los 4 de la
  semilla `surface_spec` (baloncesto). Mutaciones: invertir el signo del visitante en `orientation.py` da exit 1 con
  `assert_attack_signs_opposite` en 40 filas (y la comprobación de fases falla en los 20); invertirlo solo en
  `dim_team_period.sql` (`abs`) da 61 de 62, la misma aserción con 40 filas; en el gate, cada una de las 6 aserciones y cada
  tipo de comprobación genérica fallan sobre su violación plantada (9 tests permanentes); de código, cada una rompe al menos
  un test: lector que abre todos los partidos (6), `unique` que pide 3 copias (2), relaciones invertidas, `not_null` que
  nunca salta (1), fallos de orientación ignorados (1); todo restaurado. Procedencia: 55 filas, 31 `copiado`, 18
  `reescrito`, 6 `nuevo`. Desviaciones: entra también la vista `frame_possession`, que `frames_attacking` necesita; las 6
  aserciones viven en el paquete (`src/ftbase/silver/assertions/`) y las ejecutan `ftbase silver` tras cada build (como
  `dbt build`) y pytest, no `tests/`; la orientación (176 líneas, no unas 250) no trae la sonda de marco de eventos, los CSV
  ni los docs de tracklab (medición, no build), no escribe `bronze/common/orientation` y una fase en desacuerdo hace fallar
  el build (exit 1) tras escribir; silver en un Parquet por partido (`silver/{frames,events}/<id>.parquet`, como bronze)
  en vez de particiones hive, con la columna `sport` conservada para que el esquema sea el de tracklab; `dim_sport` queda
  con una fila; `event_type_map.csv` con sus 3 filas de fútbol y una nota que ya no cita un informe de tracklab; el commit
  fijado entra desde Python (`manifest_sources`), no leyendo el JSON en SQL; lectores `read_frames`, `read_events` y
  `read_dim` (solo abren los ficheros de los partidos pedidos, contrato en el docstring); `read.py`, `__init__.py` y dos
  ficheros de test son `nuevo` (el plan contaba los fixtures como único `nuevo`, algo que ya rompieron la 3 y la 4); los
  tests unitarios construyen un bronze mínimo de dos partidos con solo las columnas que lee silver (no son los fixtures de
  la 6); `src/ftbase/py.typed` y `tests/test_cli.py` (de la tarea 2) siguen sin fila en la procedencia: los caza el test
  de la 7; un fichero de bronze que falte a mitad de build sale como error de DuckDB sin mensaje propio.
- [x] 6. `sonnet` `[base]` Fixtures sintéticos (decisión 3): `ftbase.fixtures`, partido corto
  determinista en formato SkillCorner (JSONL, `match.json`, CSV de eventos y fases con las cabeceras
  congeladas) con tramos extrapolados plantados de longitudes conocidas; único fichero `nuevo` de la
  base. CI `ci.yml` de la base en `ubuntu-latest` (ruff, format, mypy, pytest sobre fixtures, sin
  LFS). Aceptación: CI en verde en GitHub; un skip cuenta como fallo; mutación anotada.
  Medido: commits en `football-tracking-base` `68ab86a` (`ftbase.fixtures`, `ftbase fixtures --out`, dos `not_null` en
  silver, test de extremo a extremo), `d40629d` (CI, `conftest.py` que convierte un skip en fallo, README y procedencia) y
  `ded3a56` (la CI imprime cuántos `realdata` se deseleccionan), empujados. Gate local en verde: `sync --locked`, ruff, format,
  `mypy --strict src`, `pytest -q` con 109 pasan, 0 saltados, 22 deseleccionados (eran 88: +16 de fixtures, +2 de las
  comprobaciones nuevas, +3 del hook de skips). **CI en verde: https://github.com/javiersr1996/football-tracking-base/actions/runs/39120613764,
  26 s** (la primera verde, `39120497745`, 26 s con el job `gate` en 22 s); `ubuntu-latest`, checkout `v7.0.1` sin LFS,
  `astral-sh/setup-uv@v10.3.0` con uv 0.10.4, Python 3.13.12 de `.python-version`; el log imprime `22 realdata tests are deselected`.
  **Un skip pone la CI en rojo:** PR de prueba nº 1 desde `ci-skip-probe` (un push a una rama no dispara la CI, que corre en push a
  `main`, PR y manual), ejecución `39120566513` en rojo (`109 passed, 1 skipped`, `FAILED: 1 skipped test(s) count as failures`, exit 1);
  PR cerrado sin fusionar y rama borrada en local y remoto (`git ls-remote --heads` solo `main`). Fixture: un partido, 130 frames a
  10 Hz, periodos 0-59 y 70-129 (60-69 sin periodo), 3+3 jugadores, un suplente que no juega y el balón; siete rachas plantadas
  de 4, 7, 3, 10, 6, 5 y 2 frames (dos del mismo jugador y periodo, dos que tocan el fin de un periodo, dos que empiezan con el
  segundo); lados `[left_to_right, right_to_left]`. El generador escribe los 5 ficheros crudos más un `manifest.json` con sus sha256
  reales, así que **el ingest real corre y no se salta** (`ingest --from-existing` verifica 5 de 5, `failed=0`), luego bronze y silver
  (64 de 64 comprobaciones: 62 más las 2 nuevas). La verdad sale de `SyntheticMatch.runs`, no de silver; las longitudes están
  además escritas a mano en el test. Comprueba: frames (120 en periodo x 7 entidades) y jugadores, rachas por jugador y periodo
  idénticas a las plantadas (y ninguna otra extrapolada, balón incluido), signos `{(1,7):+1,(1,8):-1,(2,7):-1,(2,8):+1}`, las 6
  aserciones y todas las comprobaciones a 0 filas, y un byte cambiado en el crudo hace fallar el ingest. Mutaciones (cada una
  rompe un test, todo restaurado, `git status` limpio): longitud plantada 4 a 5 en `fixtures.py` rompe el test de longitudes a
  mano; el escritor planta un frame menos del que declara rompe `test_the_runs_silver_recovers_are_the_planted_ones`; bronze que
  fuerza `is_detected` a true rompe 2 tests de fixtures y el de bronze; `frames.sql` que ignora `is_detected` rompe el mismo;
  invertir `left_to_right` en `orientation.py` hace salir a silver con 1 (fases en desacuerdo) y rompe 5 tests de fixtures; quitar
  `not_null frames.is_detected` de `SCHEMA_CHECKS` y un `not_null` que nunca salta rompen su test de violación plantada; sin el
  efecto del hook, 2 de los 3 tests de skips fallan. Desviaciones: `frames` no tiene `attack_sign`, vive en la vista
  `frames_attacking` (y en `dim_team_period`), el `not_null` va sobre `frames_attacking.attack_sign`; los `nuevo` son 5 filas
  más (fixtures, 3 ficheros de test y `conftest.py`), no un solo fichero; el generador escribe un partido por llamada (`match_id`
  y `seed` por argumento, la semilla solo mueve coordenadas, nunca las rachas); el bronze de dos partidos de `c4ffe15` se conserva
  (prueba los lectores con dos partidos y solo las columnas de silver; los fixtures son crudos de uno); el hook de skips vale
  también en local; `ci.yml` no está en la tabla de procedencia (va en la prosa); aviso de GitHub: `ubuntu-latest` pasa a Ubuntu 26
  desde el 19 oct 2026. Para la 8 y la 12: `write_synthetic_match(dir)` da `bundle/` y `manifest.json`, con `PlantedRun(player_id,
  period, start_frame, length)` como verdad de `gap_len`.
- [x] 7. `haiku` `[base]` Procedencia y tag: completar `docs/provenance.md` (fichero, ruta y commit
  en tracklab, estado `copiado`/`reescrito`/`nuevo`, líneas copiadas, líneas cambiadas) y `ftbase
  provenance` que imprime y escribe `reports/provenance.json` (líneas por estado). Tag `v0.1.0`
  en el commit que pasa el gate. Aceptación: el recuento del JSON coincide con `wc -l`; test que
  falla si un fichero de `src/ftbase/` no está en la tabla; `--check` compara con el JSON escrito.
  Medido: commit `4c08ba0` en `football-tracking-base` (sobre `ded3a56`, empujado a `main`; sin tag, tag pendiente de la
  revisión adversarial). Gate local en verde (`uv sync --locked`, ruff, format, `mypy src`, `pytest -q`: 114 pasan, 0
  saltados, 22 deseleccionados; eran 109) y `ftbase provenance --check` exit 0. **CI en verde:
  https://github.com/javiersr1996/football-tracking-base/actions/runs/39121055070** (último paso: `ftbase provenance --check`).
  Alcance: 63 ficheros de `src/ftbase/` y `tests/` (`__pycache__` fuera), todos con fila. Recuento contra tracklab
  `686508a`: copiado 31 ficheros, 5.661 líneas, 5.424 copiadas, 237 cambiadas; reescrito 18, 2.431 líneas, 1.354 copiadas,
  1.077 cambiadas; nuevo 14, 1.986 líneas, todas cambiadas. Total 10.078 líneas, 6.778 copiadas, 3.300 cambiadas. La suma
  de líneas del JSON es igual a `wc -l` sobre los 63. Mutaciones (cada una restaurada y comprobada): borrar la fila de
  `paths.py` (test de cobertura falla y `--check` sale 1); `lines_total` +1 en el JSON (test de `wc -l` falla, `--check`
  sale 1); editar `paths.py` sin regenerar (`--check` sale 1 con JSON y tabla); una cifra de la tabla +1 a mano (`--check`
  sale 1); `count_copied` que devuelve 0 (2 tests fallan). Desviaciones: `py.typed` y `tests/test_cli.py` no tenían fila
  (`nuevo`: tracklab `686508a` no los tiene), se añadieron con `provenance.py` y `test_provenance.py`; `ftbase provenance`
  sin `--check` exige `--tracklab` cuando hay filas `copiado` o `reescrito`; el conjunto de ficheros sale del sistema de
  ficheros, no de `git ls-files`; los dos originales de `checks.py` y `build.py` se concatenan en el orden de la tabla;
  `--check` sin tracklab compara las copiadas con el JSON pero no las recuenta (lo hace `--check --tracklab`); `ci.yml`
  queda fuera del alcance; el README no lista el nuevo subcomando.
  Revisión adversarial 1 (2026-10-18): nueve hallazgos, todos arreglados en `football-tracking-base` (`4c08ba0` a `920b943`,
  empujados; sin tag). (1) README y comentarios sin afirmaciones analíticas: solo "conserva `is_detected` del proveedor", con
  "extrapolated" como palabra suya (`4629e57`). (2) `ingest --match` seguido de `bronze` reventaba: `bronze` aplica `select_match`
  con el `match_id` del recibo (`789b31a`); test de extremo a extremo con dos partidos en el manifiesto, el segundo borrado del
  disco; mutación (quitar `select_match`) rompe el test; con datos reales, partido 1874553: `ingest --from-existing --match`
  0,6 s, `bronze` 5,7 s, `silver` 2,1 s (64 de 64 comprobaciones), exit 0 los tres. (3) `ftbase provenance` sin `--tracklab`
  funciona para `nuevo`, para sha256 sin cambios (reutiliza el JSON) y para `copiado`/`reescrito` editados (recuenta contra el
  commit de importación del propio repo, localizado por mensaje) con error claro si no está (clon superficial o `cli.py`,
  `orientation.py`, `test_silver_orientation.py`, cuyo origen no está en la importación); 4 mutaciones rompen sus tests
  (`7197bf1`, documentado en `docs/provenance.md`). (4) README sin "not tagged yet" ni "where the code was first written", con
  los cinco subcomandos y remisión a la procedencia (`920b943`, `9634b04`). (5) Cabeceras y tabla de acuerdo, con test nuevo
  (mutación: una cabecera cambiada lo rompe); `manifest_helper.py` pasa a `copiado` con su origen; la tabla dice qué orígenes no
  están en la importación y que `surface_spec.csv` quedó fuera; JSON regenerado (`920b943`). (6) 29 referencias a tareas o
  decisiones y 8 a `docs/formats/football.md` fuera (`4629e57`). (7) "about 91 MB" fuera: `ingest --match` imprime ficheros y
  bytes (95.624.493 B para 1874553, test con suma independiente; `9634b04`). (8) `source_path` absoluto y en POSIX, test
  (`5cf445d`). (9) Test de lectores con ficheros del otro partido corruptos: un lector que abre todos y filtra falla (mutación
  comprobada; el test anterior no la veía; `0a5d2f7`). Gate local y clon limpio en verde (122 pasan, 22 `realdata` pasan con
  datos reales). CI en verde: https://github.com/javiersr1996/football-tracking-base/actions/runs/39123326191
  Revisión adversarial 2 (2026-10-18): hallazgo alto, el historial: lo resuelve la reescritura, no un arreglo en HEAD.
  Medios y bajos arreglados en `football-tracking-base` (`22d403b` a `f963684`, empujados; sin tag). (1) `checks.py` da una razón
  de integridad del dato (`22d403b`). (2) `provenance` solo reutiliza el recuento guardado si coinciden sha256, orígenes, commit y
  estado, y recuenta siempre contra el commit de importación cuando este tiene los orígenes; test del caso de cambiar el origen
  en la tabla, test del recuento editado a mano en JSON y tabla; mutación (reutilizar por sha256 solo) rompe ambos
  (`22a00b3`; docs en `dbf3fa0`). (3) `silver` respeta el `match_id` del recibo como `bronze`: build completo, luego
  `--match` de uno, silver con un solo partido; mutación (ignorar el recibo) rompe el test (`36b1f36`); sin recibo, build completo
  (`f963684`, lo cazó la suite). (4) Cifras de tamaño de `select.py` fuera (`926a1d4`). (5) Nota del plan interno fuera de
  `frame_possession.sql` (`b07511e`). (6) Cifras medidas en tracklab fuera de comentarios y docstrings de `src/`, solo queda la
  explicación cualitativa (`94d7ce7`). (7) `provenance.json` y tabla regenerados con `--tracklab` (`dbf3fa0`, `f963684`). Gate
  local en verde (125 pasan, 22 `realdata` pasan). CI en verde: https://github.com/javiersr1996/football-tracking-base/actions/runs/39125630235
  Historia reescrita (2026-10-18, decisiones de Javier: copia literal con baloncesto, cifra previa
  retirada, correo noreply): `git-filter-repo` con autor y committer a noreply, la frase del README a
  "extrapolated", dos mensajes neutros y, en la importación, retirados los comentarios con mediciones
  de tracklab de `frames.sql` (6 líneas por 2) y una frase de `schema.yml`: 47 de 49 ficheros idénticos
  por hash, declarado en `docs/provenance.md`. El repo viejo (con `refs/pull/1/head`, que no se borra)
  quedó privado como `football-tracking-base-old`; **los shas de la base citados de la tarea 2 a la
  revisión 2 son de esa historia vieja.** Mapa: importación `a3ae656` → `ed43731`, esqueleto `13b6aa8` →
  `0f74d2e`, arreglos de la revisión 2 → `c1f44ca..c8a398a`. `ac2-football` también a noreply (push
  forzado al repo privado, árbol idéntico). Revisión adversarial 3: nada alto ni medio; dos bajos
  arreglados (`fetch-depth: 0` para que la CI recuente la procedencia; texto de la regla de
  reutilización), uno aceptado (9 menciones a tareas del plan en commits viejos, sin la Cup ni la entrada).
  **Tag `v0.1.0` en `53080bc`, CI verde
  (https://github.com/javiersr1996/football-tracking-base/actions/runs/39127612460) y base pública desde
  el 2026-10-18; clon anónimo comprobado.** Procedencia en el tag: 63 ficheros, 10.562 líneas (6.730
  copiadas, 3.832 cambiadas).
- [x] 8. `sonnet` `[entrada]` Dependencia fijada: `git rm -r src/ac2fb/base/`; `ftbase` en
  `dependencies` con `[tool.uv.sources] ftbase = { git = "<URL pública>", tag = "v0.1.0" }`; nunca
  una fuente `path`: para probar cambios de la base sin tag, `uv run --with-editable
  ../football-tracking-base ...`, que no toca el lock. CI `ci.yml` de la entrada en `ubuntu-latest`
  (ruff, format, mypy, pytest) instalando la base desde GitHub sin token; test de humo que construye
  el sintético de `ftbase`. Aceptación: CI en verde en GitHub con el clon de la base en el log;
  `uv.lock` lleva URL y sha; test que falla si `[tool.uv.sources]` lleva `path`; mutación: cambiar
  el sha en `uv.lock` hace fallar `uv sync --locked`. Base privada: CI roja, no saltada, hasta J2.
  Medido: commit `6bcb068` en `ac2-football` (sobre `77b0deb`), empujado. `git rm -r src/ac2fb/base/` (solo tenía un
  `__init__.py` de esqueleto; nada lo referenciaba). `[tool.uv.sources] ftbase = { git = "https://github.com/javiersr1996/football-tracking-base",
  tag = "v0.1.0" }`; `uv.lock` fija `ftbase` a `...football-tracking-base?tag=v0.1.0#53080bcc3ca1cbf7eb4fcbc8133094411a7c0d9d`
  (el sha de `53080bc`); el venv instalado lo confirma en `direct_url.json` (`commit_id` igual). Tests nuevos (7 en total, 0
  saltados): `tests/test_base_dependency.py` (3: sin `path` ni `editable` en `[tool.uv.sources]`, `ftbase` declarado, lock a git
  más sha de 40 hex y tag coincidente), `tests/test_base_smoke.py` (1: sintético de `ftbase` en `tmp_path`, `ingest
  --from-existing`, bronze y silver por el CLI de la base, y las parejas (jugador, frame) con `is_detected` falso que lee
  `read_frames` son exactamente las de `PLANTED_RUNS`, ninguna del balón) y `tests/conftest.py` (un skip hace fallar la sesión).
  CI `.github/workflows/ci.yml`: `ubuntu-latest`, checkout v7.0.1 sin LFS, `setup-uv` v10.3.0 con uv 0.10.4 (como la base), Python de
  `.python-version`, `uv sync --locked -v` sin secretos ni `GITHUB_TOKEN`, `uv pip show ftbase` y el `direct_url.json`, ruff,
  format, `mypy src`, `pytest -q`. **CI en verde: https://github.com/javiersr1996/ac2-football/actions/runs/39127916951, 18 s**;
  el log muestra `Updating https://github.com/javiersr1996/football-tracking-base (v0.1.0)` y el clon en
  `53080bcc3ca1cbf7eb4fcbc8133094411a7c0d9d`. Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 7
  pasan); todo `i/lf`. Mutaciones (todas restauradas): sha de `ftbase` en `uv.lock` a 40 ceros: `uv sync --locked` sale con
  exit 1 (`not our ref`); `path = "../football-tracking-base"` en la fuente: 2 de los 3 tests de dependencia fallan; fuente del
  lock cambiada a registro: el test del lock falla (y `uv run` no instala); un `pytest.skip` añadido: `7 passed, 1 skipped`,
  `FAILED: 1 skipped test(s) count as failures`, exit 1; quitar la última `PlantedRun` de la comparación del humo: falla.
  Fallos de la base: ninguno. Desviaciones: el aviso de GitHub sobre `ubuntu-latest` migrando a Ubuntu 26 el 19 oct no
  afecta; `README.md` provisional creado (no existía) con la instalación y `uv run --with-editable ../football-tracking-base`;
  la mutación del `path` se hizo sin tocar el lock (`--frozen`), no se probó `--with-editable` en ejecución.
- [x] 9. `sonnet` `[entrada]` Build completo de los 20 partidos con el CLI de la base y
  `scripts/clean_clone_check.sh` con dos bloques (el rápido de un partido y el completo), cada uno
  el bloque literal de un README provisional, 5 comandos como máximo (la base se instala desde
  GitHub: el clon no ve la carpeta hermana), en un `mktemp -d`, recibo sin fallos, árbol sin
  cambios. Aceptación: `CLEAN CLONE OK in N s` para los dos en local; tiempo, bytes y RAM anotados.
  Medido: commit `655bb06` en `ac2-football` (README con los dos bloques entre marcadores `clean-clone:<modo>:start/end` y
  `scripts/clean_clone_check.sh <quick|full>`), CI en verde (run 39128404085). El script extrae el bloque del README, lo
  ejecuta en un `mktemp -d` (respeta `TMPDIR`), comprueba recibo (`failed: []`, `verified` 5 con `match_id` y 85 de manifiesto,
  o 85 sin `match_id`), un Parquet de silver por partido (1 o 20) y `git status --porcelain` vacío, e imprime `CLEAN CLONE OK in N s`.
  Mientras el repo sea privado, `AC2_REPO=<ruta local>` sustituye solo la URL del `git clone` (clona el estado confirmado, así
  que hay que hacer commit antes) y lo dice en la salida. Local, con descarga real y una vez cada uno: **`CLEAN CLONE OK in 29 s`**
  (rápido: `downloaded=5 verified=5 failed=0 PARTIAL 5/85`, 95.624.493 B, 64 de 64 comprobaciones de silver) y **`CLEAN CLONE OK
  in 335 s`** (completo: `downloaded=85 verified=85 failed=0`, 1.919.842.163 B sumando los 85 `downloaded:` del log; bronze
  166,2 s, silver 53,4 s, 64 de 64). RAM: pico por muestreo cada 0,2 s con `psutil` de los procesos python/uv/ftbase bajo el
  directorio temporal (script en el scratchpad, no en el repo): rápido 447.004.672 B de suma y 405.614.592 B de un proceso;
  completo 1.844.088.832 B de suma y 1.802.645.504 B de un proceso (silver ya midió 1,8 GB en la 5).
  Los temporales se borran al salir (`trap`); no quedó nada en el directorio temporal. Mutaciones: id de partido inexistente
  (9999999) en una copia del README: `ftbase: unknown match 9999999`, exit 1, sin `OK`; un `echo junk > stray.txt` añadido al
  bloque: `FAIL: the clone is not clean: ?? stray.txt`, exit 1, sin `OK`. Gate local en verde (`sync --locked`, ruff, format,
  `mypy src`, `pytest -q`: 7 pasan); `README.md` y el script `i/lf`. Fallos de la base: ninguno. Desviaciones: el `TMPDIR` del
  scratchpad (266 caracteres en el peor fichero) supera el MAX_PATH de 260 de Windows y silver falla con `ftbase: 2`
  (`FileNotFoundError` sobre `assert_football_possessions_do_not_overlap.sql`, que existe), así que se usó
  `C:\Users\javie\AppData\Local\Temp\cc`; no es un fallo de la base, pero un juez en Windows con una ruta larga lo vería (para
  el README final); el rápido bajó 95,6 MB cuatro veces (un intento con el `TMPDIR` largo, uno bueno, dos mutaciones) y el
  completo una; los bloques usan `uv run ftbase ...` con el `--data-dir` por defecto (`data/` del clon, ignorado); los bytes
  salen de la línea `match ...: 5 files, N bytes` (rápido) y del log (completo), el recibo no los guarda.
- [x] 10. `haiku` `[entrada]` kloppy: con la versión fijada, cargar el sintético de la base y ver si
  `is_detected` sobrevive; si no, borrador de un issue (no se publica: es de Javier).
  Medido (2026-10-18, fuera del repo y luego copiado): kloppy 3.19.1 (última en PyPI ese día);
  `ftbase` instalado desde git como un tercero (`v0.1.0` → `53080bc`) sin problemas. `is_detected` se
  pierde: `kloppy/infra/serializers/tracking/skillcorner.py:224-233` crea `PlayerData(coordinates=...)`
  sin leerlo, `:215` igual con el balón, `:185` y `:241` dejan `other_data={}`; `grep -rn is_detected`
  sobre el paquete (sin `tests/files`) vacío. Las 37 filas jugador-frame plantadas con `is_detected`
  falso siguen en el dataset de kloppy con coordenadas y sin ningún indicador. Borrador del issue en
  `docs/kloppy_issue_draft.md` (reproducción sintética de dos frames, sin datos reales; no publicado: J5).

## Fase 1: capa 2 y sondas (lun 26 oct a dom 1 nov)

Todas las sondas corren **solo en los 10 partidos de calibración** y ninguna calcula el desenlace
de ninguna candidata (`[t, t + W]`). Cada una escribe `reports/probe_<n>.json` por partido y trae
su test sintético con el fallo plantado (una sonda que no puede fallar no protege nada).

- [ ] 11. `opus` Split y guard: `protocol/split.json` con la decisión 1, commiteado antes de
  cualquier código de desenlace. Una sola puerta a los datos: toda lectura del silver de la base
  pasa por `protocol.data`, que rehúsa los ids del reservado salvo con protocolo `frozen` en `HEAD`,
  `code_tree_sha` de `defence/` y `reliability/` igual al congelado y árbol limpio; tras la lectura,
  `stage: "read"` con su commit, y entonces reproduce. Aceptación: test de comportamiento sobre
  toda ruta pública (cada comando del CLI y cada función exportada, enumerados por el test);
  mutaciones anotadas: guard que solo mira `stage`, guard sin comparar el sha, lectura que
  esquiva `protocol.data`; las tres tienen que hacer fallar un test.
- [ ] 12. `sonnet` Núcleo de la capa 2 (`reliability/`): `gap_len` (frames hasta la detección
  más cercana, 0 si detectado) calculado sobre el silver de la base y escrito en el Parquet largo
  de la decisión 4, nunca en la base; detección por partido, por distancia al balón, de la línea
  y del bloque; tramos extrapolados con su longitud y salto al readquirir por
  banda de hueco (m11); **aceleración (segunda diferencia) de extrapolados frente a detectados por
  banda** (decide la hipótesis "residuo cero por construcción"); `sensitivity(metric, frames)`
  devuelve, por partido, la métrica en V0, V1 y V2 (decisión 6), la fracción extrapolada que la
  sostiene y el `gap_len` de esos jugadores. Aceptación: re-deriva las cifras de m3 a m6, m9 y m11
  en los 10 de calibración (iguales o este plan se corrige); sintético con extrapolación plantada,
  5 semillas; mutación: una `sensitivity` que ignora `is_detected` da V0 = V1 y el test falla;
  `gap_len` plantado en un sintético con huecos de longitud conocida.
- [ ] 13. `sonnet` Cadencia en fútbol: segundas diferencias de jugadores detectados con un umbral
  por encima del ruido de redondeo de la rejilla de 1 cm (justificado en la tarea), hueco entre
  quiebros en los 10 de calibración. Aceptación: `reports/probe_cadence.json`; decide la ventana
  más corta admisible (W mínimo) y lo escribe; sintético con cadencia plantada de 5 frames que
  el estimador tiene que recuperar.
- [ ] 14. `sonnet` Sonda S1 (C1): índice de presión en la recepción; contraste de dirección
  forzada (mediana del índice creciente en los 5 niveles de `overall_pressure_start` en al menos
  9 de 10 partidos); fracción del índice que sostienen rivales extrapolados; estratos de balón
  entrante por partido (recuentos, nunca el avance posterior). Muere C1 en sonda si el contraste
  falla. Mutación: un índice sin peso por distancia debe romper el contraste en el sintético.
- [ ] 15. `opus` Sonda S2 (C2): (a) altura de línea propia contra `last_defensive_line_x_start`
  en la recepción (concordancia por partido; umbral fijado antes de correr, en el commit de la
  sonda); (b) contraste forzado: la línea sigue al balón entrante en `[t - W, t]` (m10, re-derivado
  en código); (c) **pre-tendencia dentro de estrato** (dirección por longitud del balón entrante
  por tercio) presionado menos libre, en sd del estrato, por partido; (d) velocidad de la línea en
  `t` por grupo; (e) recepciones por partido con la línea entera vista en `[t - W, t + W]` y por
  número de detectados, por estrato y distancia al balón (la selección de V1); (f) fracción con el
  balón extrapolado en `[t - W, t]`. Muere C2 en sonda si el instrumento no concuerda en al menos
  9 de 10, si la pre-tendencia dentro de estrato pasa de 0,15 sd en más de 2 partidos, o si quedan
  menos de 100 recepciones por partido con la línea vista (hipótesis, se revisa con la 17).
  Mutación: con los estratos barajados el sintético con confundidor plantado devuelve la
  pre-tendencia cruda de m10 (+0,0 a +0,5 m) y el test falla.
- [ ] 16. `sonnet` Sonda S3 (C3): anchura y longitud propias contra las del proveedor al inicio
  de fase (y la definición que usa el proveedor: con o sin portero, extremos o percentiles);
  fracción extrapolada de los jugadores que fijan cada extremo; correlación de rango entre
  fracción detectada y la propia métrica (sesgo de visibilidad). Muere C3 en sonda si no se
  reproduce la métrica del proveedor. Mutación: incluir al portero rompe la reproducción.
- [ ] 17. `opus` Potencia por candidata con los tamaños medidos en 14 a 16, en sd: simula el bar
  exacto (mismo signo en al menos 8 de 10 y p de permutación agrupado ≤ 0,00135, 2.500 réplicas)
  con n por estrato y partido y la correlación dentro de la posesión de equipo medida con la
  estadística PREVIA (`[t - W, t]`, nunca el desenlace), para V0 y V1. Aceptación:
  `reports/power.json`; tabla de CP1; test que contrasta la aproximación con la permutación
  completa en un conjunto pequeño (diferencia < 0,025).
- [ ] 18. `opus` (subagente `revisor-adversarial`) Revisión de 11 a 17 antes de CP1, repetida
  sobre los arreglos hasta que no salga nada alto ni medio.
- [ ] CP1. **[Javier] lun 2 nov.** Elige UNA pregunta con la tabla delante (por candidata:
  instrumento pasa o no, pre-tendencia dentro de estrato, fracción extrapolada que la sostiene,
  n por partido en V0 y V1, MDE80, riesgo y encaje con los 5 criterios). Va recomendada primero
  la que salga de la regla: C2 si S2 pasa y su MDE80 en V1 es ≤ 0,3 sd; si no, C1; C3 solo como
  respaldo; ninguna viva, rama B.

## Fase 2: protocolo y calibración (lun 2 nov a dom 15 nov)

- [ ] 19. `fable` Protocolo en `stage: "design"` (`protocol/protocol.json`), escrito antes de
  calcular un solo desenlace (fable: el protocolo se congela y el reservado se lee una vez, un
  error aquí no tiene reintento). Contenido: instante de la causa (de la sonda), ventana W (de la
  13), desenlace exacto, estratos (dirección por longitud del balón entrante por tercio, cortes
  escritos), nulo por permutación de la etiqueta de causa dentro de partido y estrato (2.000,
  semilla fija; bloque la posesión de equipo si la correlación medida en la 17 pasa de 0,1),
  variantes V0, V1, V2 (decisión 6), familia de Holm {V0, V1}, bar de calibración (mismo signo en
  al menos 8 de 10 y p ≤ 0,00135) y de reservado (8 de 10 y p ≤ 0,01 con Holm). **Criterios de
  muerte, inamovibles:** D1 el instrumento falla su contraste; D2 MDE80 > 0,3 sd en alguna mitad
  para V0 (en V1 solo etiqueta "no comprobable en lo visto"); D3 |pre-tendencia| ≥ 50 % de
  |efecto| en V0, agregado por estrato; D4 en V1 el efecto cambia de signo o cae por debajo de la
  mitad de V0 (el efecto era modelo: muere como hallazgo táctico y se publica como hallazgo de la
  capa 2); D5 nada pasa en calibración, el reservado no se abre; D6 el reservado no pasa, se
  publica así. Aceptación: `--check` del protocolo; test de que ningún campo numérico del
  protocolo se lee de un fichero de resultados.
- [ ] 20. `sonnet` Estimador validado con sintéticos antes de tocar datos reales: efecto plantado
  que se recupera; pre-tendencia plantada que sale por D3; confundidor plantado (presión con pase
  hacia delante y línea que sigue al balón, como m10) que el estrato anula; jugadores interpolados
  linealmente en hueco que dan residuo cero y disparan la monotonía de V2; 5 semillas cada uno.
  Mutación: la causa en `t + 1 s` deja pasar la pre-tendencia; sin estrato pasa el confundidor.
- [ ] 21. `opus` Calibración: efecto por partido en los 10, las tres variantes, pre-tendencia y
  veredicto mecánico D1 a D5 en `reports/calibration.json`. Nada de este paso mueve un umbral.
- [ ] 22. `opus` (subagente `revisor-adversarial`) Revisión del protocolo, el estimador y la
  calibración antes de congelar, hasta que no salga nada alto ni medio.
- [ ] 23. `sonnet` Congelación en un commit propio: `stage: "frozen"`, `code_tree_sha`, semilla,
  umbrales. Aceptación: desde ese commit hasta la lectura, `git diff <congelación> --
  src/ac2fb/defence src/ac2fb/reliability protocol/` vacío; test contra `HEAD` que el reservado
  sigue cerrado con un cambio de código posterior.
- [ ] CP2. **[Javier] lun 16 nov.** Aprueba la congelación y queda avisado de que la lectura del
  reservado es irreversible. Si D5 ya mató la pregunta, aprueba la rama B: la capa 2 se queda en
  los 10 de calibración, salvo que Javier decida abrir el reservado solo para ella (irreversible).

## Fase 3: reservado y capa 2 completa (lun 16 nov a dom 29 nov)

- [ ] J4. **[Javier]** Lectura única del reservado: autoriza y lanza `ac2fb heldout read` (o lo
  autoriza por escrito a quien lo lance). Paso irreversible.
- [ ] 24. `opus` Veredicto mecánico del reservado (D6) por partido en `reports/heldout.json`, con
  el commit de la lectura; `stage: "read"`. Se publica como cae.
- [ ] 25. `sonnet` Capa 2 en los 20 partidos (ya permitido): mapa de fiabilidad por métrica y
  partido (presión local, distancia al rival más cercano, altura de línea, anchura, longitud, área
  del bloque, y la reacción de la línea al balón entrante) en V0, V1 y V2, con la fracción
  extrapolada y su `gap_len`, en `reports/reliability.csv`. Aceptación: las cifras de calibración
  coinciden con las de la 12; mutación anotada.
- [ ] 26. `sonnet` Referencia por amputación (`reliability/amputate.py`): en tramos con los
  jugadores de la métrica detectados se enmascaran huecos muestreados de la distribución real de
  `gap_len` y de la detección por distancia al balón, se rellenan por interpolación lineal entre
  extremos (lo que m11 dice que hace el proveedor; declarado como cota, no como su modelo) y se
  mide el error de cada métrica por banda de hueco y partido en `reports/amputation.csv`.
  Aceptación: hueco 0 da error 0; sintético con trayectoria conocida recupera el error analítico;
  mutación: rellenar con la última posición cambia el error y un test lo detecta. Sesgo
  declarado: los tramos enteramente vistos están cerca del balón.

## Fase 4: empaquetado (lun 30 nov a dom 6 dic)

- [ ] 27. `sonnet` Las dos figuras (máximo de las bases), generadas por `ac2fb figures` desde
  `reports/`: figura 1, detección por distancia al balón, fracción del modelo por banda de hueco y
  sensibilidad por métrica (V0 frente a V1, error por amputación), por partido; figura 2, el efecto
  de la capa 3 por partido en V0, V1 y V2, calibración y reservado (o la muerte, rama B).
  Aceptación: test que regenera y compara; cada número de una etiqueta sale de un artefacto.
- [ ] 28. `sonnet` `--check` en cada comando que escribe un artefacto (recalcula y compara; con
  fixtures dice cuánto verificó, `PARTIAL n/20`). Aceptación: mutar un valor de un JSON hace
  fallar su `--check`.
- [ ] 29. `sonnet` API pública mínima y documentada (`reliability.sensitivity`,
  `reliability.amputate`, `protocol.data` como lector guardado del silver de la base, esquema del
  Parquet largo con `gap_len`) y un
  `examples/sensitivity.py` que corre sobre el sintético. Aceptación: el ejemplo corre en CI.
- [ ] 30. `sonnet` `full-build.yml`: `workflow_dispatch`, caché de `data/raw` por huella del
  manifiesto, build completo, todos los `--check` y los dos bloques de `clean_clone_check.sh` en
  `ubuntu-latest`. Aceptación: una ejecución en verde con su enlace; el árbol queda limpio.
- [ ] 31. `sonnet` `scripts/readme_check.py` y su test: palabras del README (todo el texto, bloques
  de código incluidos, sin comentarios HTML) ≤ 1000, figuras más tablas ≤ 2, cada número del README
  presente en algún artefacto de `reports/`, y la frase literal de que los fixtures sintéticos no
  producen cifra alguna. Mutaciones: 1001 palabras, tercera tabla, número inventado, frase borrada.
- [ ] 32. `sonnet` Clip de 10 s para el vídeo: una recepción con los defensores detectados en
  relleno y los extrapolados en hueco con su `gap_len`, desde silver por `ac2fb clip` (matplotlib).
- [ ] J5. **[Javier, opcional]** Abrir el issue en kloppy con el texto de la 10.

## Fase 5: entrega (lun 7 dic a vie 18 dic)

- [ ] 33. `sonnet` README en inglés: qué es, procedencia (abajo), capa 2 (con "extrapolated is
  interpolated" y la cifra de huecos largos), capa 3, método en corto, reproducir (bloque rápido
  de un partido y bloque completo, con tiempos medidos), fixtures sintéticos solo para tests,
  reutilizar, licencia y datos. Aceptación: la 31 en verde; lectura de Javier.
- [ ] 34. `sonnet` Guion del vídeo (≤ 60 s, unas 140 palabras, voz de Javier) con plano por frase
  (figura 1, figura 2, clip de la 32); cada cifra con su artefacto.
- [ ] J6. **[Javier]** `ac2-football` público (si no lo era; la base lo es desde J2); `full-build`
  en verde del commit entregado y el tag de la base que fija `uv.lock` presente en el repo público.
- [ ] J7. **[Javier]** Grabar el vídeo con su voz (máximo 1 minuto) y subirlo a YouTube
  (visibilidad admitida: PENDIENTE DE CONFIRMAR en las bases).
- [ ] J8. **[Javier]** Enviar en submissions.analytics-cup.org. Objetivo mar 15 dic; límite vie 18.

## Cómo se declara la base (cumplir "disclosed" sin parecer "lightly adapted")

- Dependencia declarada, no árbol copiado (decisión 7): `ac2-football` no tiene `base/` ni commit
  de importación; `pyproject.toml` fija `ftbase` (URL git pública más tag, commit en `uv.lock`) y
  todo su `git log` es trabajo de la Cup.
- La procedencia vive en el repo base: primer commit con la copia literal de tracklab `686508a`,
  `docs/provenance.md` (fichero, origen, estado, líneas; tarea 7), `ftbase provenance` en
  `reports/provenance.json`, y su README dice que se extrajo de tracklab en octubre de 2026.
- La cifra "líneas nuevas frente a copiadas" sale del README de la entrada: allí todo es nuevo por
  construcción; basta el puntero a la base (tag, commit) y su tabla; `readme_check` (31) no la pide.
- Lo previo que se reutiliza como dato (la proporción detectada por partido que midió tracklab) se
  dice como previo; lo nuevo es la sensibilidad, la interpolación medida y la pregunta. P5 no se
  reutiliza; su protocolo (split, nulo, criterios de muerte) se cita como método, no resultado.
- Borrador de la sección del README de la entrada (unas 60 palabras, en inglés):

  > **Provenance.** Ingestion, bronze and conformed frames and events come from [`ftbase`](<URL>),
  > the author's open-source pipeline for SkillCorner open data (MIT), pinned at tag `<tag>` (commit
  > `<sha>`), extracted in October 2026 from his private repository *tracklab* (`docs/provenance.md`
  > lists every file and what changed). Everything here was written for the Analytics Cup: the
  > reliability layer, the defensive question, its protocol and held-out reading, figures and tests.

## Choques con las bases detectados al planificar

1. **Cuota LFS de SkillCorner.** Out of the box depende de bajar 1.823.448.331 B por
   `media.githubusercontent.com`; si la cuota de SkillCorner se agota durante la Cup, la descarga
   falla. Mitigación: decisión 5 (`--from-existing`, `--match`), error que los nombra, tiempos medidos.
2. **kloppy (recurso sugerido) pierde `is_detected`** en 3.19.1: la capa 2 no se puede construir
   encima. Mitigación: decisión 4; el hallazgo entra en el README.
3. **"Lightly adapted" y "pre-existing open-source projects".** Cerrado en lo esencial por la
   decisión 7: la base es un "open-source project" propio (repo público MIT), "appropriately
   licensed and disclosed" (dependencia declarada, procedencia en su repo), y la entrada no contiene
   nada previo que adaptar; la capa 2 vale sola (rama B). Residual, reducido: "pre-existing" en el
   tiempo (el repo base nace en octubre de 2026 con código anterior); los dos README lo dicen.
4. **"Solo los datos de SkillCorner" y los fixtures sintéticos.** Un lector estricto podría leer
   el sintético como dato adicional. Mitigación: solo alimentan tests y CI, ninguna cifra sale de
   ellos, el README lo dice con una frase literal y `readme_check` la exige (31). **París**: J1.
5. **1000 palabras y 2 figuras o tablas**: reproducción y procedencia comen unas 200 (hipótesis);
   resultados en prosa con cifras y las dos figuras, sin tablas.

## Verificación

- [ ] V. Verificación. Gate en los dos repos, cada uno desde su raíz, en este orden (en la base,
  sin las dos últimas líneas y con `uv run ftbase provenance --check` al final):
  ```
  uv sync --locked
  uv run ruff check .
  uv run ruff format --check .
  uv run mypy src
  uv run pytest -q
  uv run python scripts/readme_check.py
  bash scripts/clean_clone_check.sh
  ```
  Criterio de aceptación agregado: todo lo anterior en verde en local en los dos repos; `ci.yml` de
  la base en verde en `ubuntu-latest` sobre el commit del tag fijado y `full-build` de la entrada en
  verde en `ubuntu-latest` sobre el commit que se entrega (enlaces a las dos ejecuciones); `uv.lock`
  fija `ftbase` a URL git pública más sha, sin fuente `path`, el commit que cita el README; el clon
  limpio de `ac2-football` en Linux instala la base desde GitHub sin token en los dos bloques, con
  el tiempo impreso; `src/ac2fb/base/` no existe; README ≤ 1000 palabras contadas por script y ≤ 2
  figuras o tablas; `LICENSE.md` en los dos repos; ningún número del README, del guion ni de las
  figuras sin un artefacto de `reports/` que lo imprima; `protocol.json` en `read` (o en
  `design`/`frozen` con D5 documentado, rama B) y su historia en git; ninguna ruta pública lee el
  reservado fuera del guard; cada test nuevo con su mutación anotada; las cifras de m10 y m11
  re-derivadas por la 12 y la 15 o este plan corregido. Revisión adversarial (`revisor-adversarial`)
  de todo `ac2-football` (sin commit de importación: todo es nuevo) y del diff de la base desde su
  importación (`git diff <import>..HEAD` en `ftbase`), repetida sobre los arreglos hasta que no
  salga nada alto ni medio.
