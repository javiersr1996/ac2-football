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
  40,3 %**. Consecuencia: la 12 la matiza (corrección abajo): lo extrapolado es más suave que lo
  detectado y su mediana está en el suelo de redondeo, pero no es una recta.
- Cadencia (m7, exploratoria): el hueco entre quiebros de detectados es 1 frame en el 57,6 a
  59,8 % y decae sin pico; el umbral cae dentro del ruido de redondeo de 1 cm. Lo cierra la 13.
- **Corrección de la tarea 12 (2026-10-18; todas las cifras de este bloque salen de
  `reports/layer2.json`, 10 de calibración, por partido: `matches`, `summary` y `inventory`).**
  - *m3 a m6 y m9 se reproducen en lo comparable.* Los 22 rangos de 20 partidos contienen los
    valores de los 10 de calibración (22 de 22; sus medianas son de otro conjunto y no se
    comparan). Un valor, los rivales detectados a 20 m (0,8765 en un partido), queda 0,0005 bajo
    el 87,7 % del plan: doble redondeo del plan (la sonda imprimía 0,8765), no un dato distinto.
    Tramos extrapolados (m6): los 10 suman 48.798, mediana 47, p90 181, p99 592 frente a 98.487, 47,
    175 y 587 de los 20: mismo orden, no comparables uno a uno.
  - *m11 se reproduce en 85 de 100 celdas por partido y en los pooled de ≤ 1 s y > 20 s; las
    demás difieren por la sonda, no por el código.* Iguales a tres decimales: paso detectado a
    detectado (mediana y p90), mediana del salto en ≤ 1 s y > 20 s, p90 del salto en > 20 s, y el
    número de huecos > 20 s (10 de 10 partidos); pooled de ≤ 1 s (2.601 huecos) y > 20 s (4.058)
    enteros (n, mediana, p90, p99, paso interior). Difieren la fracción de posiciones por banda (15
    de 40 celdas, hasta 0,012) y el número de huecos de 1 a 5 s y de 5 a 20 s del pooled (+17 y +5
    de 23.091 y 18.844; medianas y percentiles iguales). Causa: m11 etiquetaba cada tramo con
    `any_value(det)`, que no es determinista cuando un tramo mezcla clases (ver abajo); con la
    clase de la última fila salen los huecos largos de los 10 partidos, no las fracciones. Valen
    las bandas de `reacquisition` del artefacto: fracción de posiciones por hueco, por partido, ≤ 1
    s 0,3 a 0,6 %; 1 a 5 s 15,9 a 19,5; 5 a 20 s 40,6 a 46,6; > 20 s 35,1 a 39,7 %.
  - *Un "tramo" de m6 y m11 une trozos separados por frames que el proveedor no lista.* Por
    partido hay 1.068 a 1.553 trozos sin filas dentro de un periodo (mediana de 126 a 209 frames;
    1.048 a 1.553 de más de 50) y en 1.054 a 1.553 de ellos hay frames extrapolados a ambos lados
    (`unlisted`): el jugador desaparece de la lista entre dos extrapolaciones. Las sondas los
    pegaban. Con el tramo cortado en el frame sin fila (`runs`, por defecto en `ac2fb`) salen 5.335
    a 7.057 tramos extrapolados por partido (m11: 3.801 a 5.715); de los de ≤ 1 s, con detección a
    ambos lados solo 148 a 352 de 1.078 a 1.346 (el resto son reentradas), y de los 281 a 496 de
    más de 20 s lo son 138 a 309. Solo esos huecos cerrados dicen cuánto cuesta un hueco: salto
    mediano por banda, ≤ 1 s 0,179 a 0,258 m; 1 a 5 s 0,165 a 0,219; 5 a 20 s 0,150 a 0,207; > 20 s
    0,205 a 0,257 (paso detectado a detectado 0,184 a 0,214). **El salto no crece con el hueco como
    lo haría un predictor, pero en los huecos largos cerrados es algo mayor (mediana entre partidos
    0,217 m frente a 0,198 detectado)**: "interpolado con el futuro visto" aguanta, sin "casi
    exacto". Fracción de posiciones extrapoladas en huecos > 20 s: 28,9 a 35,5 % (no 34,9 a 40,3).
  - *La hipótesis "residuo cero por construcción" se confirma a medias.* Segunda diferencia (m por
    frame²): extrapolados p50 0,010, p90 0,022, p99 0,041; detectados p50 0,014, p90 0,032, p99
    0,051; una recta a velocidad constante redondeada a 1 cm da p50 0,010, p90 0,014 y p99 0,014
    (simulada, semilla fija). Mediana de lo extrapolado en el suelo de redondeo (también por banda
    de hueco, salvo ≤ 1 s con 0,014), pero colas de 1,6 y 2,9 veces el suelo: lo extrapolado es más
    suave que lo detectado, no una recta. Una métrica de reacción no lee cero exacto en esos
    jugadores: se trata con V1 y V2, no por supuesto.
  - *Definiciones que la 12 fija.* `gap_len` mide números de frame hasta la detección más cercana
    del mismo periodo (nulo si el jugador no tiene ninguna). El silver no trae el rol: el portero
    de la línea es un proxy (el jugador cuya posición media está más cerca de su portería, por
    periodo y equipo) que coincide con el portero del reparto en los 40 pares (periodo, equipo) de
    los 10 partidos (test `realdata`). La puerta sirve silver, no bronce: las sondas se re-derivan
    de los eventos del silver (`native_family`), sin `frame_physical_start`.

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
  estratos de dirección, presionado menos libre: hacia atrás −0,34 a +0,42 (8 de 10 positivos),
  hacia delante −0,65 a +0,14 (8 de 10 negativos, agregado −0,27 m, 0,14 sd), lateral −0,47 a
  +0,38. Queda un residuo del tamaño de 0,1 a 0,15 sd que D3 tiene que juzgar.
- La etiqueta del proveedor es monótona con la geometría (rivales a 5 m; distancia al más cercano):
  `no_pressure` 0,00 y 11,6 m; `low` 0,20 y 6,9; `medium` 0,69 y 4,6; `high` 1,35 y 2,6;
  `very_high` 1,72 y 1,3. **La visibilidad va con la causa**: con presión se ven 2,51 de los 4 de
  la línea (los 4 en el 43,9 %), sin presión 1,78 (28,6 %): "línea vista" selecciona recepciones
  presionadas y cercanas al balón, y toda variante restringida declara ese sesgo.
- **Re-derivado en código por la tarea 15** (`reports/probe_s2.json`, `m10_inventory`, con las
  definiciones de m10): 314 de 340 cifras impresas por m10 iguales a sus decimales; las otras 26
  difieren en 0,0061 o menos por empates de profundidad a 1 cm entre el cuarto y el quinto
  defensor, que m10 rompía sin orden fijo. Todas las cifras de este bloque se reproducen a su
  precisión salvo una: hacia atrás eran 8 de 10 positivos, no 7 (corregido arriba).

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

- [x] 11. `opus` Split y guard: `protocol/split.json` con la decisión 1, commiteado antes de
  cualquier código de desenlace. Una sola puerta a los datos: toda lectura del silver de la base
  pasa por `protocol.data`, que rehúsa los ids del reservado salvo con protocolo `frozen` en `HEAD`,
  `code_tree_sha` de `defence/` y `reliability/` igual al congelado (desde la revisión 18, de todo
  `src`, `pyproject.toml`, `uv.lock` y `.python-version`) y árbol limpio; tras la lectura,
  `stage: "read"` con su commit, y entonces reproduce. Aceptación: test de comportamiento sobre
  toda ruta pública (cada comando del CLI y cada función exportada, enumerados por el test);
  mutaciones anotadas: guard que solo mira `stage`, guard sin comparar el sha, lectura que
  esquiva `protocol.data`; las tres tienen que hacer fallar un test.
  Medido (2026-10-18): **commit del split `7747bed`**, solo `protocol/split.json` (los 20 ids de la
  decisión 1, comprobados contra `tracklab/tasks/todo.md:4767-4771` y contra los 20 de silver por nombre
  de fichero) y `protocol/protocol.json` (`stage: "design"`, `code_tree_sha: null`), empujado antes de
  cualquier código (CI verde 39129954707). Código en `dad335a`, empujado: CI verde
  https://github.com/javiersr1996/ac2-football/actions/runs/39132358688 (95 pasan, 2 deseleccionados, 3,9 s).
  Datos: `FTBASE_DATA_ROOT=C:/Users/javie/Desktop/proyectos/ac2-football/data` (`data/` en `.gitignore:1`),
  `ftbase ingest --from-existing` contra tracklab: `downloaded=0 verified=85 failed=0`, 10 s; `bronze` 297 s
  (295,5 según ftbase); `silver` 76 s (73,5; `checks: 64/64 passed`); 383 s en total; tracklab sin cambios
  (`git status` vacío). Puerta `ac2fb.protocol.data` (`read_frames`, `read_events`, `read_dim`,
  `load_split`, `guard_status`, `code_tree_sha`, `data_dir`): split y `stage` se leen de `HEAD` con
  `git show`, nunca del árbol; un id del reservado se rehúsa con `HeldOutLocked` antes de abrir ningún
  fichero salvo `stage` `frozen` o `read` en `HEAD`, `code_tree_sha` igual al registrado y árbol limpio
  (`git status --porcelain --untracked-files=all` vacío y ningún fichero `assume-unchanged` o
  `skip-worktree`); un id fuera del split, `ValueError`. `code_tree_sha` es el sha256 de `git ls-tree HEAD
  -- src/ac2fb/defence src/ac2fb/reliability` (en `dad335a`: `51a755a8...8911d`); `data_dir()` es
  `$FTBASE_DATA_ROOT` o `data/` en la raíz del checkout. `ac2fb status` imprime el estado (solo git).
  Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 95 pasan, eran 7; 0
  saltados; 2 deseleccionados); `pytest -m realdata`: 2 de 2 (sirve los 10 de calibración por frames,
  events y `dim_match`; rehúsa los 10 del reservado por los tres lectores, sin abrir nada suyo). Tests
  sobre el sintético de la base escrito dos veces, con ids 1874553 y 1899585, y construido por su CLI;
  control positivo: ese reservado se lee directo con `ftbase.silver`. **Rutas públicas enumeradas por
  el test** (`__all__` de cada módulo, que debe listar todo nombre público, y subcomandos del CLI): 9
  funciones (`cli.build_parser`, `cli.main` y las 7 de la puerta) y 1 comando (`status`). Las 3 que
  toman partido, en 10 llamadas (frames normal, `attacking` y con columnas; events; `read_dim` en las 6
  dimensiones), rehúsan el reservado y sirven calibración con los Parquet del reservado envenenados, y
  sirven el reservado con el protocolo congelado; las 6 funciones sin partido y `status` corren sobre los
  envenenados sin fallar. Test AST: fuera de la puerta, ningún import de `ftbase`, `duckdb` ni
  `pyarrow.dataset`, ningún lector de Parquet por nombre, ningún privado de la puerta y ninguna cadena
  con `ftbase|duckdb|silver` fuera de docstrings; el comprobador se prueba con 23 fragmentos que debe
  rechazar y 7 que debe dejar pasar. **Mutaciones (18, todas matan algún test; script en el
  scratchpad, todo restaurado):** guard que solo mira `stage` (8 tests); guard sin comparar el sha (2);
  `reliability/leak.py` que importa `ftbase.silver` y exporta un lector (2: AST y tabla de rutas), sin
  `__all__` (5) y con `duckdb` sobre un glob de silver (1); sin árbol limpio (5); sin
  `assume-unchanged`/`skip-worktree` (2); split del árbol (1); `stage` del árbol (1, por el mensaje: el
  árbol sucio también cierra); `read_dim` sin recorte (6); `dim_team` sin recorte (1); ids fuera del
  split admitidos (1); sha de una sola carpeta (10); `design` abre (3); `read_frames` sin guard (24);
  sin comprobar la raíz del checkout (1); lector exportado en la puerta sin guard (1); petición mixta
  que mira solo el primer id (1). Fallo de la base (no arreglado): `ftbase bronze` y `ftbase silver`
  imprimen recuentos por partido (filas, frames, eventos, MB) de los 20, reservado incluido, y el bloque
  completo del README también; de los logs (scratchpad) se borraron sin mirarlas las 70 líneas con ids
  del reservado. Desviaciones: `protocol.json` entra en el commit del split (la 19 lo rellena) y el
  split lleva un campo `about`; la puerta prohíbe a los demás módulos todo `ftbase`, no solo
  `ftbase.silver` (`pyarrow.parquet.write_table` sigue permitido para la 12); `read_dim` pide ids y lee
  entero el fichero de cada dimensión, pero solo devuelve las filas de esos partidos (`dim_team`, sus
  equipos; `dim_sport`, entera); `read` abre como `frozen` (reproducir) con las mismas condiciones, y la
  puerta no escribe `stage: "read"` ni exige el commit de la lectura (J4 y la 24); no detecta una
  recongelación (un commit que cambie código y `code_tree_sha` a la vez: lo cubre el `git diff` de la
  23) y su propio código (`src/ac2fb/protocol/`) no entra en el sha; ids fuera del split rehusados
  (el sintético con su id por defecto no pasa); solo sirve desde su checkout git, fuera da
  `RuntimeError`; `pyarrow>=26.0.0` como dependencia directa (misma versión del lock), override de mypy
  y `addopts = -m 'not realdata'` como en la base; `ac2fb status` nuevo (da el sha que pedirá la 23).
- [x] 12. `sonnet` Núcleo de la capa 2 (`reliability/`): `gap_len` (frames hasta la detección
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
  Medido (2026-10-18): commit `7d08dfa` (código, tests y `reports/layer2.json`, empujado). **CI en
  verde: https://github.com/javiersr1996/ac2-football/actions/runs/39135819850, 36 s.** Gate local en
  verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 267 pasan, eran 95; 0 saltados; 6
  deseleccionados, eran 2); `pytest -m realdata`: 6 de 6 (2 de la 11 y 4 nuevos: `gap_len` en un
  partido real, m11 del primero, informe confirmado byte a byte contra el recalculado, portero).
  Módulos de `reliability/`: `long` (`gap_len` y el Parquet largo de la decisión 4 en
  `data/layer2/frames_long/<id>.parquet`: `match_id` (`fb:<id>`), `period`, `frame`, `player_id` y
  `team_id` (nulos en el balón), `x`, `y`, `is_detected`, `gap_len`), `match`, `runs`,
  `visibility`, `sensitivity`, `inventory`, `report`; comando `ac2fb layer2 [--match ID]
  [--reports-dir D]` (sin `--match`, la calibración; un id del reservado sale con 2 y el motivo en
  stderr). Dependencia nueva: numpy 2.5.4. Tiempos: `ac2fb layer2` sobre los 10 de calibración, 37 a
  46 s (lectura de unos 2 s por partido); 10 Parquet de 5,0 a 6,4 MB; gate local 182 s (las rutas
  públicas pasan de 4 s a unos 2 min porque cada ruta carga el sintético por la puerta); CI 36 s.
  Sintéticos (5 semillas, 1 a 5, de la base con 12 tramos plantados: los 7 de la base más 5 de
  longitudes 1, 3, 8, 12 y 15, uno en el primer frame de un periodo): `gap_len` esperado por fuerza
  bruta desde las `PlantedRun` (nunca de la salida) en las 720 filas de jugador; tramos recuperados
  = plantados (jugador, inicio, longitud); salto contra las filas leídas aparte; V0 (10 unidades), V1
  (4) y estratos de V2, fracción extrapolada y `gap_len` (mediana, p90, máximo) contra la verdad, y
  medias contra las filas; `gap_len` contra fuerza bruta en series aleatorias con frames sin listar
  (5 semillas); partidos hechos a mano (aceleración con 5 semillas, pasos, tramos y trozos sin fila,
  jugador comprometido, recepción, línea con portero). **Mutaciones (11, todas matan algún test,
  restauradas; script en el scratchpad):** `sensitivity` que ignora `is_detected` (V1 = V0: falla el
  recuento de V1, 4 frente a 10); que no cuenta los frames extrapolados; `gap_len` +1; `gap_len` que
  cruza la frontera de serie; `gap_len` solo hacia atrás; tramos que unen frames sin fila por
  defecto; salto leído en el frame equivocado; aceleración que ignora la clase del frame; portero
  dentro de la línea (sobrevivía a la primera versión del test, con el portero visto: se rehízo con
  el portero no visto); línea con los más adelantados; rivales que incluyen al propio equipo. Control
  permanente de la pedida: con `is_detected` forzado a verdadero V1 = V0 y la fracción extrapolada es
  0, con las banderas reales no. **Cifras: 22 de 22 rangos de m3 a m6 y m9 contienen los 10 de
  calibración; m11, 85 de 100 celdas por partido y 2 de 4 pooled iguales a tres decimales; el resto
  difiere por la sonda y se corrige en el inventario ("Corrección de la tarea 12").** Desviaciones:
  la puerta sirve silver y no bronce, así que m3 a m9 se re-derivan de eventos del silver y sin
  `frame_physical_start`; el portero es un proxy (40 de 40 pares igual al reparto, test `realdata` que
  lee `match_players` de los 10 de calibración con duckdb dentro del test, nada en `src`);
  `sensitivity(metric, frames, windows=None)` toma la tabla larga y ventanas opcionales (sin ellas,
  cada frame es una unidad: lento en un partido real); la definición de tramo de m6 y m11 queda
  como `bridge_holes=True` para reproducir y la de `ac2fb` corta en el frame sin fila; los Parquet
  largos se escriben pero no se releen en `src` (la puerta prohíbe lectores de Parquet fuera de ella:
  el análisis recalcula desde `protocol.data`); `reports/layer2.json` es un solo informe con la
  sección `inventory` (comparación con el plan) en vez de un JSON por sonda; la aceleración por banda
  usa como referencia los detectados en conjunto y por longitud de su propio tramo; el suelo de
  redondeo es una simulación (`linear_rounding_floor`, semilla 0), no una medida. Nadie leyó el
  reservado: ningún comando ni test tocó un partido suyo.
- [x] 13. `sonnet` Cadencia en fútbol: segundas diferencias de jugadores detectados con un umbral
  por encima del ruido de redondeo de la rejilla de 1 cm (justificado en la tarea), hueco entre
  quiebros en los 10 de calibración. Aceptación: `reports/probe_cadence.json`; decide la ventana
  más corta admisible (W mínimo) y lo escribe; sintético con cadencia plantada de 5 frames que
  el estimador tiene que recuperar, varias semillas; mutación anotada.
  Medido (2026-10-18; todas las cifras salen de `reports/probe_cadence.json`, 10 de calibración,
  por partido): código `2f6f53c`, empujado, **CI en verde** (run 39136726588, 38 s). Gate local en
  verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 347 pasan, eran 267; 7
  deseleccionados; `pytest -m realdata`: 7 de 7, eran 6, con el informe confirmado byte a byte).
  Nuevo: `reliability/cadence.py`, comando `ac2fb cadence [--match ID] [--reports-dir D]` y
  `runs.second_differences` (la segunda diferencia que `acceleration_summary` calculaba dentro, sin
  duplicarla: `layer2.json` sale igual byte a byte). Rutas públicas nuevas cubiertas por el test de
  la 11 (7 funciones y el comando `cadence`).
  **Umbral.** Una recta redondeada a 1 cm se desvía como mucho 0,005 por coordenada, la segunda
  diferencia 0,005 x (1 + 2 + 1) = 0,02 y la de dos dimensiones 0,02 x raíz de 2 = 0,0283 m por
  frame al cuadrado (`threshold.rounding_bound`). Umbral de quiebro: **0,03**, por encima de ese
  máximo exacto, así que el redondeo solo nunca da un quiebro (un test lo comprueba con 100.000
  rectas). El artefacto imprime también el suelo simulado de la 12 (`simulated_floor`: p50 0,010,
  p90 y p99 0,0141).
  **Regla de W mínimo, escrita en el docstring de `cadence.py` antes de leer los datos:** cadencia
  de un partido = el hueco más frecuente entre quiebros (el menor en un empate); cadencia del
  conjunto = la mayor de los 10; G = el mayor de los 10 del percentil 90 del hueco; **W mínimo =
  máx(2 x cadencia, G) frames**. Razón: un desenlace "desplazamiento en `[t, t + W]` menos lo que
  predecía la velocidad en `t`" vale cero para un camino que no gira, así que la ventana tiene que
  poder contener un giro en la mayoría de los casos (G) y al menos tres actualizaciones reales
  (2 x cadencia). Es un suelo: la 19 puede elegir una ventana mayor, nunca menor.
  **Resultado: cadencia 1 frame en 10 de 10 partidos (no hay cadencia oculta), G = 13, W mínimo = 13
  frames = 1,3 s** (`decision`). Por partido: el hueco p50 es 1 a 2 frames; p90 9 a 13; el hueco de 1
  frame es el 49,9 a 55,1 % de los huecos y el de 2 el 21,2 a 22,7 %; quiebros en el 11,1 a 14,4 %
  de los centros detectados (58.036 a 74.302 huecos por partido); el histograma cae sin pico (la
  primera subida respecto al hueco anterior, `first_rise`, está entre el hueco 9 y el 23, en colas
  de menos de 1 %). Sin umbral, el 96,9 a 97,3 % de los centros son quiebros (cadencia 1); con el
  p99 del suelo, 37,0 a 42,0 % (cadencia 1, p90 de 4 a 5): el umbral cae dentro del ruido de redondeo
  y de movimiento real, como adelantó m7 (57,6 a 59,8 % de huecos de 1 frame con otro umbral y
  otra definición de hueco: no son comparables). Los huecos solo se cuentan dentro de tramos
  detectados sin interrupción, así que los largos están infrarrepresentados (censura por la
  derecha); los de más de 30 frames son el 3,3 a 4,9 % (`histogram.gap_gt_30`).
  **Sintético** (`tests/test_cadence.py`): caminos con un vértice cada `c` frames (cambio de
  velocidad de al menos 0,1 m por frame, redondeo a 1 cm), 8 jugadores x 600 frames, **5 semillas
  (1 a 5) x c = 3, 5 y 8**: el estimador recupera `c` en las 15; con c = 5 todos los huecos son
  múltiplos de 5, más del 90 % valen 5, el informe da cadencia 5, G 5 y W mínimo 10 frames; la
  primera subida del histograma cae en `c`; un camino recto no da ningún quiebro con 0,03 y miles
  con 0. Los huecos se contrastan con una referencia de fuerza bruta sobre diccionarios, con
  frames sin listar y tramos extrapolados, 5 semillas x 3 umbrales. **Mutaciones (7, restauradas;
  script en el scratchpad), tests que fallan de 60:** sin umbral 42; umbral dentro del ruido (p50
  del suelo, 0,010) 32; hueco que cruza interrupciones 56; ventana sin G 1; ventana sin 2 x
  cadencia 6; cadencia = hueco mayor 11; umbral en el p99 del suelo (0,0142) **solo 1**: el test de
  la cota (0,0141 < 0,0283 < 0,03), porque con un 1 % de falsos quiebros la moda sigue en 5.
  Desviaciones: G como percentil 90 y el factor 2 son una convención (la regla las declara; no
  salen de un artefacto); sin pico no se prueba que el proveedor interpole a 10 Hz, solo que ninguna
  cadencia mayor de 1 aparece con este umbral; el informe es un JSON propio y no una sección de
  `layer2.json`; la 19 toma W >= 13 frames. Nadie leyó el reservado.
- [x] 14. `sonnet` Sonda S1 (C1): índice de presión en la recepción; contraste de dirección
  forzada (mediana del índice creciente en los 5 niveles de `overall_pressure_start` en al menos
  9 de 10 partidos); fracción del índice que sostienen rivales extrapolados; estratos de balón
  entrante por partido (recuentos, nunca el avance posterior). Muere C1 en sonda si el contraste
  falla. Mutación: un índice sin peso por distancia debe romper el contraste en el sintético.
  Medido (2026-10-18; todas las cifras salen de `reports/probe_s1.json`, 10 de calibración, por
  partido): **código y regla en `e279ccf`, empujado antes de calcular el índice en ningún partido
  real** (CI en verde, run 39137889374); el informe y este registro, en el commit siguiente. Gate
  local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 422 pasan, eran 347; 9
  deseleccionados, eran 7; `pytest -m realdata`: 9 de 9, con el informe confirmado byte a byte).
  Nuevo: `defence/pressure.py` (índice, estratos), `defence/probe_s1.py` (regla, carga, informe),
  comando `ac2fb s1 [--match ID] [--reports-dir D]` (32 s para los 10) y `protocol.data.read_bronze_events`
  (ver desviaciones). Rutas públicas nuevas (16 funciones y el comando `s1`) cubiertas por el test de
  la 11. **Índice y regla, escritos en los docstrings antes de leer los datos.** Cada rival del otro
  equipo listado en `t` (el portero incluido) a distancia `d` del poseedor suma `(1 - d/10) * (1 +
  cos(theta)) / 2` si `d <= 10`, con `theta` el ángulo en el poseedor entre el rival y el punto de
  portería que ataca `(signo * 52,5; 0)`; el índice es la suma. Recepción `t` = `frame_start` de
  `player_possession`; el índice usa solo el frame `t`. Contraste: por partido, la mediana del índice
  por nivel (1 a 5, `overall_pressure_start_id`) estrictamente creciente (cada una por encima de la
  anterior en más de 1e-9) y al menos 10 recepciones en cada nivel; **C1 sobrevive si pasan al menos
  9 de los 10; si no, muere en la sonda**. El veredicto es sobre V0; el contraste en V1 (rivales
  cercanos todos vistos) se imprime al lado y no decide.
  **Veredicto: C1 sobrevive a la sonda (`verdict.c1_survives_probe` = true, 10 de 10).** Mediana del
  índice por nivel, rango entre partidos: `no_pressure` 0,000 en los 10 (la mediana es 0: al menos la
  mitad de esas recepciones tiene índice 0, sin rival a 10 m); `low` 0,241 a 0,302; `medium` 0,468 a 0,553; `high`
  0,707 a 0,853; `very_high` 0,816 a 1,027. Recepciones por nivel y partido: `no` 110 a 317, `low` 109 a
  210, `medium` 179 a 288, `high` 130 a 213, `very_high` 28 a 42 (el mínimo exigido, 10, se cumple en
  todos). Saltos entre niveles contiguos, por partido: no a low 0,241 a 0,302; low a medium 0,169 a
  0,288; medium a high 0,219 a 0,330; **high a very_high 0,036 a 0,274**: el escalón estrecho es el
  último. En V1 también crece en los 10 (n de 612 a 909 por partido; `very_high` desde 23). Entran
  todas las recepciones con etiqueta (653 a 936 por partido; sin etiqueta 80 a 130 de 757 a 1.054
  `player_possession`) y ninguna se descarta después (`left_out` 0). Poseedor detectado en `t`: 0,976
  a 0,999. Índice medio en V0, 0,381 a 0,559; en V1, 0,370 a 0,550.
  **Fracción del índice que sostienen rivales extrapolados** (`extrapolated_share`): global 0,008 a
  0,050 por partido; por nivel, `no` 0,000 a 0,045, `low` 0,001 a 0,038, `medium` 0,009 a 0,036, `high`
  0,005 a 0,054, `very_high` 0,000 a 0,115; recepciones con algún rival cercano extrapolado, 0,019 a
  0,093 (de 558 a 756 con algún rival a 10 m). Por la capa 2 (`sensitivity`, ventanas de un frame): fracción
  de los jugador-frame cercanos extrapolada 0,008 a 0,046; V0 n 653 a 936 y V1 n de 612 a 909;
  `gap_len` mediano de esos extrapolados 5,0 a 10,0 frames (p90 18,4 a 206,4; `sensitivity.gap_len`).
  La capa 2 muerde poco en C1, como adelantaba el plan; el máximo por nivel está en `very_high`.
  **Estratos de balón entrante** (`incoming_ball`): dirección del avance del balón en `[t - 13, t]`
  (retrocede más de 2 m, avanza más de 2 m, lateral) por tercio del poseedor (propio, medio, final;
  cortes a 17,5 m del centro) por longitud (recta menor o mayor de 10 m): 18 celdas, todas presentes
  en los 10 partidos, cada una con su reparto por nivel (`strata.<celda>.by_level`); sin balón en
  `t - 13` o `t` (`undefined`), 0 a 3 por partido. Son recuentos de lo previo; ninguna cifra de
  después de `t` (un test cambia todo lo posterior a `t` y el índice y el estrato no se mueven).
  Los recuentos por celda y nivel están en el JSON; son lo que usa la 17 para la potencia dentro
  de estrato.
  **Mutaciones** (script en el scratchpad, todo restaurado, `git status` limpio): la pedida, índice sin
  peso por distancia (`distance_weight` constante, dentro del test): 0 de 10 partidos crecen y el
  veredicto pasa a `false` (`test_an_index_without_distance_weight_breaks_the_contrast`); en el código
  fuente: sin peso por distancia, sin peso hacia portería, contraste sin mínimo por nivel, regla de 8
  de 10, índice que lee `t + 1`, balón leído en `[t, t + 13]`, ventana de 12 frames, radio de 12 m,
  fracción extrapolada que cuenta los vistos, métrica de la capa 2 que ignora el poseedor, rivales
  que son el propio equipo, y empate numérico (`TIE` a -1, que deja pasar el ruido de coma flotante
  como subida): 12 de 12 matan algún test. Guarda: `read_bronze_events` sin `_admit` hace fallar el
  barrido de rutas (1 test).
  **Desviaciones.** (1) La puerta no tenía lector de bronce y silver no guarda la etiqueta:
  `read_bronze_events(match_ids, columns)` (guardado con `_admit`, abre solo los ficheros de los ids
  admitidos) se une a silver por `native_event_id` = `event_id`; en los 10 de calibración los dos
  conjuntos de ids coinciden y cada `overall_pressure_start_id` va con su etiqueta; la carga falla si
  no, o si dos recepciones caen en el mismo frame. (2) Los parámetros del índice (peso lineal a 10
  m, `(1 + cos) / 2`, punto de portería a 52,5 m, portero incluido, mínimo 10 por nivel, empate 1e-9,
  cortes de los estratos de 2 m, 17,5 m y 10 m) son convenciones mías, escritas antes de los datos;
  ninguna salió de un artefacto, y la 19 puede redefinir el índice (el contraste de la sonda no lo
  congela). (3) Con `no_pressure` en mediana 0,000, la primera subida (a 0,241 o más) se debe sobre todo
  a que muchas recepciones sin presión no tienen rival a 10 m; el contraste no prueba que el índice
  distinga dentro de un nivel. (4) La sonda no mide la correlación del índice con el desenlace
  ni con el avance posterior, a propósito. (5) `W` = 13 (suelo de la 13) para los estratos; un test
  lo ata a `reports/probe_cadence.json`. Nadie leyó el reservado.
- [x] 15. `opus` Sonda S2 (C2): (a) altura de línea propia contra `last_defensive_line_x_start`
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
  Medido (2026-10-18; todas las cifras salen de `reports/probe_s2.json`, 10 de calibración, por
  partido): **código y regla en `5a435ed`, empujado antes de calcular la línea en ningún partido
  real** (CI en verde, run 39141308101); el informe y este registro, en el commit siguiente. Gate
  local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 490 pasan, eran 422; 10
  deseleccionados, eran 9; `pytest -m realdata`: 10 de 10, con el informe confirmado byte a
  byte). Nuevo: `defence/line.py` (línea, unidades, visibilidad, concordancia, pre-tendencia
  dentro de estrato), `defence/probe_s2.py` (regla, carga, informe), `defence/m10.py` (m10
  re-derivado y sus tablas impresas) y el comando `ac2fb s2 [--match ID] [--reports-dir D]`.
  Rutas públicas nuevas (17 funciones y el comando `s2`) cubiertas por el test de la 11.
  Reutiliza `pressure.incoming_ball` (estratos, W = 13), `visibility.goalkeepers`,
  `match.locate_rows` y `players_at`, `report.render_report` y `protocol.data.read_bronze_events`.
  **Definiciones y regla, escritas en los docstrings antes de leer los datos.** Recepción `t` =
  `frame_start` de toda `player_possession` con jugador y equipo, con etiqueta o sin ella. Línea:
  los 4 jugadores de campo más profundos del rival en `t` (x por el signo de ataque del
  poseedor; portero fuera por el proxy de la 12), elegidos en `t` y seguidos sin re-rankear; `L`
  su profundidad media, + es la línea retrocediendo. Presionado: un rival a 5 m o menos en `t`
  (el proxy de m10). V0: línea listada en `t`, `t - 5`, `t - 13` y `t - 18` y estrato definido.
  Pre-tendencia bruta `P = L(t) - L(t - 13)`; residual `R = P - 13 v(t - 13)`, con `v` medida en
  5 frames (el desenlace de C2 movido W hacia atrás). Criterios: (1) instrumento por partido = r
  de Pearson de `L(t)` con `last_defensive_line_x_start` de al menos 0,9 (30 pares o más) y `P`
  medio negativo tras balón hacia atrás y positivo tras balón hacia delante (30 o más cada uno);
  muere si pasan menos de 9 de 10. (2) Pre-tendencia dentro de estrato (18 celdas; presionado
  menos libre en sd de la celda, media ponderada por `n_p n_f / (n_p + n_f)`, fuera las celdas
  con menos de 5 en un grupo): un partido está por encima si `P` o `R` pasa de 0,15 sd en valor
  absoluto; muere si hay más de 2. (3) Muere si algún partido tiene menos de 100 recepciones en
  V1 (los 4 detectados en todo `[t - 13, t + 13]`).
  **Veredicto: C2 muere en la sonda (`verdict.c2_survives_probe` = false), por el criterio 2.**
  - (1) Instrumento: pasa en 10 de 10. (a) r 0,990 a 0,993 (CCC 0,964 a 0,979) sobre 754 a
    1.050 pares por partido; la media de 4 queda 1,57 a 2,59 m menos profunda que el proveedor
    (mediana de la diferencia). **El proveedor da el defensor más retrasado, no la media de 4**:
    con el más profundo solo, r 0,997 a 1,000 y diferencia mediana −0,09 a +0,02 m (absoluta
    0,00 a 0,17). (b) La línea sigue al balón en los 10: tras balón hacia atrás `P` medio −1,52
    a −0,93 m (n 296 a 448), tras balón hacia delante +0,87 a +1,43 (n 281 a 415), lateral
    −0,36 a +0,29.
  - (2) Pre-tendencia: **por encima de 0,15 sd en 7 de 10** (1874553, 1886347, 1925299,
    1959846, 2010085, 2011166, 2015213); por debajo 1996435, 1996436 y 2007448. Bruta dentro de
    estrato −0,272 a +0,002 sd (−0,57 a +0,01 m; negativa en 9 de 10, por encima en 3); residual
    −0,305 a −0,106 sd (negativa en 10 de 10, por encima en 5): con cualquiera de las dos sola,
    C2 muere igual. La cruda (sin estratos) es la de m10, bruta +0,008 a +0,660 m (+0,003 a
    +0,279 sd); dentro de estrato cambia de signo: **el presionado ya retrocede menos que el
    libre antes de `t`**, sobre todo tras balón hacia delante (celdas `forward/*` de
    `pretrend.raw.within_strata.by_stratum`), en la dirección del efecto que C2 buscaría
    ("presión, línea arriba"). Entran 13 a 16 de las 18 celdas por partido (40 a 86 recepciones
    fuera por celdas finas).
  - (3) Visibilidad: V1 138 a 477 recepciones por partido (V0 733 a 1.037), 100 o más en los 10.
    Por número de detectados en toda la ventana: 0, 226 a 454; 1, 93 a 167; 2, 68 a 122; 3, 77
    a 126; 4, 138 a 477. La selección va con la causa: en V1 quedan 86 a 223 presionadas y 45 a
    254 libres (`visibility.by_group`), y cae con la distancia de la línea al balón
    (`visibility.by_ball_distance`); las 18 celdas por grupo, en V0 y V1, están en
    `visibility.by_stratum` para la 17.
  - (d) Velocidad de la línea en `t` (m/s, + retrocede): presionado −0,05 a +0,33, libre −0,46 a
    +0,11 (presionado por encima en 9 de 10); dentro de estrato −0,295 a −0,035 sd (negativa en
    10 de 10). Informa, no decide.
  - (f) Balón extrapolado o sin fila en algún frame de `[t - 13, t]`: 3,4 a 6,2 % de V0
    (presionado 3,5 a 6,5 %, libre 2,3 a 6,6 %); en 9 de 10 es igual a la fracción con el
    balón extrapolado en un extremo de la ventana (`ball.extrapolated_at_ends`; 1925299, 6,1
    frente a 6,2 %).
  **m10 re-derivado** (`m10_inventory`, definiciones de m10: ventanas de 10 y 20 frames, todas
  las posesiones): 314 de 340 cifras impresas iguales a sus decimales; las 26 restantes (1925299:
  1, 1959846: 2, 1996436: 8, 2010085: 8, 2015213: 3, agregadas: 4) difieren en 0,0061 o menos.
  Causa: empates de profundidad a 1 cm entre el cuarto y el quinto defensor en `t`, que m10
  rompía con `row_number()` sin orden fijo; rompiéndolos al revés (diagnóstico de solo lectura
  en el scratchpad), 1925299, 1959846, 1996436 y 2010085 reproducen entero y 1996435 pasa a
  diferir; los porteros del reparto no entran en ninguna línea. Las cifras en prosa del bloque m10
  del inventario se reproducen a su precisión salvo el "7 de 10 positivos" hacia atrás, que son 8
  (corregido en el bloque).
  **Mutaciones** (31 sobre el código, script en el scratchpad, todo restaurado, `git status`
  limpio; tests que fallan, de 32): la pedida, estratos ignorados (4) o barajados (4): la
  pre-tendencia vuelve a la cruda de +0,4 m del sintético y
  `test_the_strata_absorb_the_planted_confounder` falla; profundidad sin signo (1), ranking sin
  signo (1), línea re-rankeada en cada desfase (1), portero en la línea (10), lectura en `t + lag`
  (16), presión con 2 rivales (6), visto con solo fila (4), pre-tendencia sin dividir por la sd (2)
  o con pesos 1 (1), mínimo de celda solo en un grupo (1 y 1), ventana del balón que no ve una
  fila ausente (1) o que empieza tarde (1), visibilidad que acaba en `t` (4), residual sin
  velocidad (2), velocidad por frame (1), veredicto solo con la bruta (1), sin celdas que agregar
  no cuenta (1), concordancia sin mínimo de pares (1), contraste sin el lado hacia atrás (1), sin
  el lado hacia delante (1) o sin mínimo (1), regla de 8 de 10 (2), de 3 partidos por encima (2),
  un partido corto admitido en V1 (1), instrumento sin concordancia (1), corte de m10 con `>=`
  (1), tolerancia de m10 por 10 (1), sd de m10 con ddof 0 (1). La primera pasada dejó viva la de
  la fila de balón ausente: se añadió ese caso al test.
  **Desviaciones.** (1) Concordancia por r de Pearson (la CCC se imprime y no decide): el plan no
  fijaba la medida. (2) La pre-tendencia decide con dos estadísticas, la bruta (la de m10) y la
  residual ("la misma estadística" del desenlace en `[t - W, t]`), y basta una por encima: lo más
  conservador; el veredicto no cambia con una sola. (3) El criterio 3 se aplica en cada partido
  (lectura estricta de "por partido"); el plan marca el 100 como hipótesis de la 17. (4) `K` = 5
  frames, los mínimos de 30 y de 5, el radio de 5 m de m10 como presión y los cortes de distancia
  de la capa 2 son convenciones mías, escritas antes de los datos. (5) (e) no pasa por
  `reliability.sensitivity`, cuya métrica recibe las posiciones de toda la ventana, también
  después de `t`: `seen_through` cuenta la misma selección (V1, V2) leyendo solo banderas. (6)
  El proxy del portero usa la posición media del periodo entero, también después de `t`: un rol,
  no un movimiento (declarado en el docstring). (7) Entran todas las `player_possession` con
  jugador y equipo, como en m10, no solo las etiquetadas de S1. Nadie leyó el reservado; nada
  medido en `(t, t + W]` salvo las banderas de detección de (e).
- [x] 16. `sonnet` Sonda S3 (C3): anchura y longitud propias contra las del proveedor al inicio
  de fase (y la definición que usa el proveedor: con o sin portero, extremos o percentiles);
  fracción extrapolada de los jugadores que fijan cada extremo; correlación de rango entre
  fracción detectada y la propia métrica (sesgo de visibilidad). Muere C3 en sonda si no se
  reproduce la métrica del proveedor. Mutación: incluir al portero rompe la reproducción.
  Medido (2026-10-18; todas las cifras salen de `reports/probe_s3.json`, 10 de calibración, por
  partido; rangos entre partidos): **código y regla en `c8e2d49`, empujado antes de calcular nada
  en ningún partido real** (CI en verde, run 39144469545); el informe y este registro, en el
  commit siguiente. Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`:
  589 pasan, eran 490; 11 deseleccionados, eran 10; `pytest -m realdata`: 11 de 11, con el informe
  confirmado byte a byte). Nuevo: `defence/block.py` (las 8 definiciones, `measure`, Spearman),
  `defence/probe_s3.py` (regla, carga, informe), `protocol.data.read_bronze_phases` (ver
  desviaciones) y el comando `ac2fb s3 [--match ID] [--reports-dir D]` (60 s para los 10). Rutas
  públicas nuevas (14 funciones y el comando `s3`) cubiertas por el test de la 11.
  **Definiciones y regla, escritas en los docstrings antes de leer los datos.** Ocho definiciones
  del bloque del equipo sin balón al `frame_start` de la fase (producto de tres elecciones): con o
  sin portero (el proxy de la 12), extremos (máximo menos mínimo) o percentiles 5 y 95, y todos los
  jugadores listados o solo los detectados; anchura = extensión de `y`, longitud = de `x`. Una
  definición **reproduce** en un partido si, en anchura y en longitud, hay al menos 100 fases con
  ambos números, r de Pearson de al menos 0,95 y diferencia absoluta mediana de 1 m o menos. Se
  elige la que reproduce en más partidos; empate por la menor media (entre partidos) de la suma de
  las dos diferencias medianas (no calculable cuenta infinito); nuevo empate, la anterior en la
  lista. **C3 muere en la sonda si la elegida reproduce en menos de 9 de los 10.**
  **Veredicto: C3 sobrevive a la sonda (`verdict.c3_survives_probe` = true, 10 de 10).**
  - *Definición del proveedor: `with_gk_extremes_listed`*, es decir, los 11 jugadores listados en
    el `frame_start`, **portero incluido**, de extremo a extremo (el bloque es "el equipo sin
    balón entero"). Anchura: r 0,9847 a 1,0000, diferencia absoluta mediana 0,00 a 0,30 m
    (con signo −0,03 a +0,11); longitud: r 0,9938 a 1,0000, 0,00 a 0,345 m (−0,15 a +0,115);
    374 a 473 fases por partido de 383 a 490 (se quedan fuera las sin jugadores listados en ese
    frame y las sin número del proveedor). Exacta (ambas medianas 0) en 5 de 10 (1874553, 1959846,
    1996436, 2007448, 2010085); en los otros 5, diferencias de 0,18 a 0,35 m que no se
    investigaron. Las otras siete reproducen en 0 de 10: `with_gk_p5_p95_listed` (anchura r 0,931
    a 0,950, 3,4 a 4,8 m; longitud 12,7 a 14,3 m), `outfield_extremes_listed` (ver mutación) y las
    cuatro de solo detectados, las peores (suma media 29,7 a 38,7 m).
  - *Fracción extrapolada de los jugadores que fijan cada extremo* (capa 2, `sensitivity` con una
    ventana de un frame; `matches.<id>.chosen.fixers`, fracción de jugador-frame extrapolada):
    `x_low` 0,520 a 0,637, `x_high` 0,527 a 0,630, `y_low` 0,250 a 0,529, `y_high` 0,288 a 0,447;
    anchura (sus dos extremos) 0,271 a 0,455 y longitud 0,524 a 0,633. Fases con todos los
    fijadores detectados (V1): anchura 137 a 249 de 374 a 473 (32,9 a 58,9 %); **longitud 15 a 43
    (3,9 a 9,5 %)**. La longitud media en V1 es 17,8 a 30,1 m frente a 50,5 a 53,3 m en V0 (V1
    menos V0, −34,5 a −21,8 m); la anchura, −2,65 a +0,71 m. `gap_len` mediano de lo extrapolado en
    los extremos de `x`, 55 a 118 frames (p90 322 a 1.431); en los de `y`, 11 a 26 (p90 52 a 135).
    No se midió qué jugador fija cada extremo: que el más retrasado sea el portero es lo esperable
    con esta definición, no un dato.
  - *Sesgo de visibilidad* (Spearman por partido, `chosen.visibility_bias`; fracción detectada del
    bloque 0,526 a 0,692): con nuestra anchura −0,280 a −0,096 y con nuestra longitud −0,566 a
    −0,308, **negativas en 10 de 10**; con los números del proveedor salen iguales a menos de 0,01.
    Con la fracción detectada de los fijadores: anchura −0,194 a +0,126 (6 de 10 negativas),
    longitud −0,270 a −0,010 (10 de 10 negativas). Cuanto más del bloque se ve, más corto y algo
    más estrecho: los bloques que la cámara enseña son los compactos. Es el sesgo de selección de
    m10 en el bloque, y la métrica del proveedor lo trae igual.
  - **Lo que esto dice para C3.** Existe un instrumento (el proveedor es reproducible casi al
    metro), pero su longitud es del portero al jugador más adelantado: un contraste de compacidad
    del bloque sin portero es otra medida (la longitud sin portero difiere de la del proveedor en
    20,1 a 23,8 m de mediana). La capa 2 muerde aquí más que en C1 y C2 (longitud vista entera en
    menos del 10 % de las fases). Sobrevivir a la sonda no la elige: lo decide CP1.
  **Mutación** (la pedida y su inversa). La definición ganadora incluye al portero, así que la
  mutación pedida es la inversa: dejarlo fuera. En datos reales, `outfield_extremes_listed`
  reproduce en 0 de 10: la anchura no se mueve (r 0,979 a 1,000, 0,00 a 0,32 m) y la longitud sí
  (r 0,737 a 0,868, 20,1 a 23,8 m). En el sintético, `test_each_planted_definition_is_the_one_chosen`
  planta cada una de las 8 con 5 semillas (40 casos, con el proveedor calculado por una referencia
  independiente de bucles) y exige que la sonda devuelva esa, y
  `test_the_other_goalkeeper_choice_breaks_the_reproduction` exige, para las 8, que la elección
  contraria del portero no reproduzca (longitud a más de 1 m) en las 5 semillas. **Mutaciones de
  código (26, script en el scratchpad, todo restaurado): portero invertido o nunca fuera,
  percentil medido como extremo y al revés, población ignorada, anchura y longitud cambiadas,
  percentil bajo en 10, Spearman sin empates y con el signo cambiado, selección sin la diferencia,
  con la posición antes de la diferencia, con no calculable como cero y con menos partidos
  primero, regla de 8 y de 10 de 10, r mínimo 0,5, límite de 5 m, mínimo de 50 pares, veredicto
  solo con la anchura, equipo equivocado (el que tiene el balón), fase leída un frame tarde,
  fijadores de un solo extremo, fracción de sesgo que cuenta al portero aunque se deje fuera, fases sin equipo
  admitidas, números del proveedor cruzados y `read_bronze_phases` sin guarda: 26 de 26 matan algún
  test.** La primera pasada dejó viva la de 50 pares: el test usaba la constante del código
  (`MIN_PAIRS - 1`), que es tautológico; ahora usa 99 y 100 literales. Otros controles: un
  proveedor de ruido no lo reproduce ninguna definición; unos pocos errores grandes (30 % de las
  longitudes a 10 m) rompen la r con mediana cero y, al revés, un desplazamiento de 1,5 m rompe la
  mediana con r 1; con filas absurdas tras el `frame_start` el informe es idéntico; el bloque que
  se ve más ancho cuanto más se ve da Spearman 1 en el sintético.
  **Desviaciones.** (1) El conjunto de 8 definiciones, el 5 y 95 de los percentiles, el mínimo de 5
  jugadores, el `frame_start` exacto, anchura = `y` y longitud = `x`, y los umbrales (r 0,95, 1 m,
  100 pares, 9 de 10) son convenciones mías escritas antes de los datos; ninguna salió de un
  artefacto. (2) La mutación pedida (incluir al portero) es la inversa porque la definición ganadora
  lo incluye. (3) El silver no guarda la anchura ni la longitud de las fases: `read_bronze_phases`
  (guardado con `_admit`, cubierto por el test de rutas con 2 llamadas) las lee de bronce, y las
  fases salen de bronce, no de los eventos del silver. (4) El portero es el proxy de la 12
  (posición media del periodo), no el rol; reproduce al proveedor, pero el proveedor puede usar el
  rol real. (5) Reproducir es por partido y conjunto en anchura y longitud, no solo una; la sonda no
  investiga el residuo de 0,2 a 0,35 m de 5 partidos. (6) El `gap_len` del informe de fijadores
  lee banderas de detección de otros frames (capa 2, declarado desde la 14); ninguna posición
  posterior al `frame_start`. (7) No se calcula nada del desenlace de C3 (diferencias de
  compacidad entre tipos de fase). Nadie leyó el reservado.
- [x] 17. `opus` Potencia por candidata con los tamaños medidos en 14 a 16, en sd: simula el bar
  exacto (mismo signo en al menos 8 de 10 y p de permutación agrupado ≤ 0,00135, 2.500 réplicas)
  con n por estrato y partido y la correlación dentro de la posesión de equipo medida con la
  estadística PREVIA (`[t - W, t]`, nunca el desenlace), para V0 y V1. Aceptación:
  `reports/power.json`; tabla de CP1; test que contrasta la aproximación con la permutación
  completa en un conjunto pequeño (diferencia < 0,025).
  Medido (2026-10-18; las cifras salen de `reports/power.json` salvo las que citan otra sonda; 10
  de calibración, por partido, rangos entre partidos): **código en `68731fa`, empujado antes de
  calcular ninguna potencia en un partido real** (CI en verde, run 39147956002); el informe y este
  registro, en el commit siguiente. Antes del código se miró en el scratchpad la correlación dentro
  de la posesión de la estadística previa (solo `[t - W, t]`) para saber si el bloqueo hacía falta;
  no movió ningún umbral. Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest
  -q`: 679 pasan, eran 589; 13 deseleccionados, eran 11; `pytest -m realdata`: 13 de 13, con el
  informe confirmado byte a byte y las unidades atadas a las de S1 y S3). Nuevo: `defence/bar.py`
  (el bar, sus dos nulos, la aproximación, la simulación, el MDE80 y la correlación por pares),
  `defence/power.py` (unidades de C1 y C3, lectores previos, informe y regla de CP1) y el comando
  `ac2fb power [--match ID] [--reports-dir D]` (44 s para los 10). Rutas públicas nuevas (25
  funciones y el comando `power`) cubiertas por el test de la 11.
  **Diseño, escrito en los docstrings antes de calcular.** *Estadístico:* en cada celda (partido,
  estrato) con al menos 5 unidades de cada grupo, `z` = media de la causa menos la del resto sobre
  la sd de la celda; por partido y agregado, media de `z` ponderada por `n_p n_f / (n_p + n_f)` (la
  de `within_strata`). *Bar:* el agregado tiene el signo de al menos 8 de los 10 partidos (uno sin
  celda nunca cuenta) y el p bilateral de 2.000 nulos, `(1 + cuenta) / 2.001`, es ≤ 0,00135: a lo
  sumo 1 nulo tan extremo (`bar_count_at_most`). "Agrupado" se lee como un solo estadístico
  agregado sobre los 10 partidos. *Nulo:* sin bloquear, la etiqueta de causa permutada dentro de
  partido y celda; bloqueado, el signo de la contribución de cada posesión entera invertido al azar
  (el nulo por bloques de P5). *Aproximación:* varianza exacta del nulo (`1 / suma w` sin bloquear,
  `suma S_k²` bloqueado), la cuenta como Binomial(2.000, 2 Φ(−|Z|)) y la probabilidad de que sea
  ≤ 1; potencia = media de esa probabilidad por la condición de signo en 2.500 réplicas, ruido
  común a todos los efectos, semilla 20261018 con una corriente por candidata, desenlace, estratos
  y variante. *Ruido:* varianza 1, una parte compartida por posesión con la correlación `rho` del
  partido; efecto en sd del ruido. *MDE80:* el menor efecto con tasa ≥ 0,8, rejilla de 0,05 hasta 2
  sd refinada a 0,01; "no alcanzable" es más de 2 sd o imposible por diseño. *Correlación:* por
  pares de unidades de una posesión, de la estadística previa estandarizada dentro de cada estrato,
  por partido y variante; el ruido lleva la mayor de 0, la de V0 y la de V1 si se apoya en 30 pares
  o más; se bloquea si la de V0 agregada (media por pares) pasa de 0,1, como pide la 19. *C1:* las
  recepciones de S1 con estrato definido; causa, un rival a 5 m o menos en `t` (proxy de m10 y
  S2); los 18 estratos de S1; posesión, el `possession_id` de la base; estadística previa, el
  avance del balón en `[t − 13, t]`; V1, la de S1. *C3:* las fases de S3 medidas con
  `with_gk_extremes_listed`; contraste `low_block` (causa) frente a `high_block`
  (`team_out_of_possession_phase_type`); dos desenlaces, anchura y longitud, con su V1 (los
  fijadores de sus dos extremos vistos en `t`); estratos del balón entrante con el balón en lugar
  del poseedor y, como cota, sin estratos; posesión, una racha de fases del mismo equipo en un
  periodo; estadística previa, el mismo bloque en `t − 13`; sin pre-tendencia (el desenlace es un
  nivel en `t`, y en `t − 13` sería casi el desenlace).
  **C1** (`candidates.C1`): V0 650 a 934 recepciones por partido (presionadas 311 a 385, libres
  279 a 586; 551 a 864 en 12 a 16 celdas usadas; 149 a 201 posesiones), V1 610 a 907. Correlación
  dentro de la posesión en V0 −0,027 a +0,015 (2.007 a 6.026 pares), agregada −0,005: **nulo sin
  bloquear**; en V1 −0,035 a +0,016. **MDE80 0,12 sd en V0 y en V1** (tasa 0,887 y 0,873 en 0,12;
  0,797 y 0,782 en 0,11); tasa sin efecto 0,00005 y 0,0013. **Pre-tendencia dentro de estrato**
  (nueva: S1 no la medía), presionada menos libre del avance del balón en `[t − 13, t]` en sd de la
  celda: V0 +0,081 a +0,371, positiva en 10 de 10 y por encima de 0,15 en 9; V1 +0,081 a +0,348. La
  presionada recibe tras más avance del balón que la libre dentro de la misma celda: el confundidor
  de m10 que los estratos de S1 no absorben del todo. La regla de S1 no la tenía, así que no mata a
  C1 en sonda; es la cifra que D3 juzgará contra el efecto.
  **C3** (`candidates.C3`): fases medidas 374 a 473 por partido (V1 de anchura 137 a 249, de
  longitud 15 a 43: las de S3). En el contraste, sin estratos, V0 110 a 162 (bajo 60 a 96, alto 34
  a 74). **Con los estratos del plan, bajo/alto: 0 celdas por construcción** en los 10 partidos
  (bajo y alto no comparten tercio del balón): MDE80 no alcanzable en V0 ni V1, anchura ni
  longitud, para ese contraste; no es que C3 no sea medible dentro de estrato (los contrastes
  contiguos, en la revisión 18, más abajo). Sin
  estratos (cota inferior): **anchura 0,24 en V0 y 0,41 en V1** (V1: bajo 28 a 68, alto 7 a 28);
  **longitud 0,25 en V0 y no alcanzable en V1** (V1 2 a 18, ninguna de bloque alto: sus dos
  fijadores de `x` nunca se ven a la vez). Correlación agregada de V0: anchura 0,126 con estratos y
  0,129 sin ellos, longitud 0,208 y 0,383: **nulo bloqueado** en las cuatro; por partido, sin
  estratos, anchura 0,064 a 0,229 y longitud 0,245 a 0,536. Tasa sin efecto 0,0008 en la anchura y
  0,0018 en la longitud (sin estratos), esta por encima de 0,00135.
  **C2**: muerta en S2 por la pre-tendencia (`probe_s2.json`, `verdict.criteria.pretrend` false);
  no se simula.
  **Tabla de CP1** (rangos por partido; riesgo y encaje, del bloque de candidatas de este plan):

  | | C1 | C2 | C3 |
  |---|---|---|---|
  | Instrumento | pasa S1, 10 de 10 (`probe_s1.json`) | pasa, 10 de 10 (`probe_s2.json`) | pasa S3, 10 de 10 (`probe_s3.json`) |
  | Pre-tendencia dentro de estrato (sd) | V0 +0,081 a +0,371; > 0,15 en 9 de 10 (`power.json`) | bruta −0,272 a +0,002, residual −0,305 a −0,106; > 0,15 en 7 de 10: **muerta en S2** | no aplica (nivel) |
  | Pre-tendencia agregada (sd) y efecto mínimo para pasar D3 (V0) | V0 +0,224, V1 +0,216 (informativa: D3 se aplica solo en V0); D3 pide \|efecto\| > 0,447 en V0, 3,7 veces el MDE80 (`pretrend`) | no aplica (muerta) | no aplica (nivel) |
  | Fracción que lo extrapolado sostiene | 0,008 a 0,050 del índice (`probe_s1.json`) | línea detectada en `t` 0,444 a 0,697 (`layer2.json`); el resto, extrapolada | fijadores de la anchura 0,271 a 0,455, de la longitud 0,524 a 0,633 (`probe_s3.json`) |
  | n por partido, V0 / V1 | 650 a 934 / 610 a 907 | 733 a 1.037 / 138 a 477 (`probe_s2.json`) | bajo y alto 110 a 162 / anchura 44 a 90, longitud 2 a 18; bajo/medio en el tercio medio 96 a 142 / anchura 32 a 87, longitud 0 a 14; medio/alto en el propio 74 a 141 / anchura 15 a 53, longitud 0 |
  | MDE80 (sd), V0 / V1 | 0,12 / 0,12 | no simulada | dentro de estrato: bajo/alto, 0 celdas por construcción; bajo/medio en el tercio medio, anchura 0,41 / no alcanzable, longitud 0,41 / no alcanzable; medio/alto en el propio, anchura 0,85 / no alcanzable, longitud 0,83 / no alcanzable. Sin estratos (cota, bajo/alto, que incumple la regla de estratos y no tiene D3): anchura 0,24 / 0,41, longitud 0,25 / no alcanzable; tasa sin efecto de su nulo 0,0008 en la anchura y 0,0018 en la longitud (esta pasa de 0,00135) |
  | Riesgo | medio; D3 por la pre-tendencia | murió | bajo como medida, alto como hallazgo; **ningún contraste cumple las reglas del plan** (ver abajo) |
  | Encaje (R, M, O, C, OS) | alta, media-alta, **baja**, alta, media | muy alta, alta, alta, alta, alta | muy alta, media, media-alta, alta, alta |

  **Lo que sale de la regla de CP1 (recomienda; decide Javier).** C2 murió en S2, así que la regla
  da **C1 primero** y C3 como respaldo descriptivo (`cp1_rule`: `recommended_first` C1, `backup`
  C3; `testable_v0` C1 sí y ninguno de los seis diseños de C3 dentro de estrato, revisión 18). El
  MDE80 de C1, 0,12 sd en V0 y en V1, queda muy por debajo del
  0,3 de D2 en la mitad de calibración: la potencia no es razón para la rama B. El riesgo de C1
  está en D3: con una pre-tendencia por partido de +0,08 a +0,37 sd, positiva en 10 de 10 (de signo
  contrario al efecto que C1 busca: la presión reduciría el avance), D3 pide un efecto de más
  del doble de la pre-tendencia agregada en V0 (+0,224 sd: |efecto| > 0,447 sd, 3,7 veces el
  MDE80; revisión 18); y su originalidad es baja. **C3 no tiene ningún diseño que cumpla las
  reglas del plan.** Dentro de estrato (la regla: la causa se compara siempre dentro de estratos),
  bajo frente a alto no tiene celdas por construcción y los contrastes contiguos dan 0,41 a 0,85
  sd en V0 (`testable_v0` falso en los seis diseños, así que D2 los mataría) y no alcanzan en V1.
  Bajo frente a alto sin estratos pasa D2 (0,24 anchura y 0,25 longitud en V0) pero incumple la
  regla de estratos, su nulo de longitud da 0,0018 de tasa sin efecto (por encima de 0,00135) y D3
  no está definida para un nivel (queda en "no aplica"). Sin estratos, en V1 C3 solo mide la
  anchura (MDE80 0,41) y la longitud no llega en V1 en ningún diseño. Elegir C3 obliga a CP1 a
  cambiar por escrito la regla de estratos o D2, y a definir D3 para un nivel, antes de la 19; y
  como lo haría después de ver la cifra, choca con "un umbral que falla no se mueve" y con los
  criterios inamovibles, la misma objeción que la nota 1 hace a C1. Sospechoso, sin
  confirmar (la definición no está en `docs/`): el grupo de C3 es
  `team_out_of_possession_phase_type`, una etiqueta de toda la fase que el proveedor podría fijar
  con lo posterior a `frame_start`, es decir, una lectura parcial del desenlace.
  **Notas de la revisión 18 a la tabla** (cifras de `power.json`). (1) Con la vara de S2 (más de
  2 partidos con la pre-tendencia por encima de 0,15 sd en valor absoluto), C1 también moriría:
  9 de 10 en V0 y en V1 (`pretrend.s2_bar`). El plan, a la letra, solo la somete a D3 (la regla
  de S1 no tenía pre-tendencia); aplicarle la vara de S2 sería mover un umbral después de ver la
  cifra, y no se hace aquí: lo decide CP1 con las dos lecturas delante. (2) Una pre-tendencia
  positiva con reversión a la media puede producir sola un efecto negativo: la presionada recibe
  tras más avance del balón en `[t − 13, t]` que la libre de su celda; si ese avance revierte en
  `[t, t + W]`, el avance posterior de la presionada cae sin que la presión cause nada, y ese es
  justo el signo que C1 busca. D3 compara magnitudes y no lo separa: la 19 lo tiene que tratar
  con la estadística previa como covariable dentro de la celda (ajuste por lo previo dentro de
  estrato). El desenlace como cambio respecto a lo previo no sirve: con E[después | antes, G] =
  α + β·antes + τ·G (G la causa), el desenlace estima τ + β·pre, el cambio τ + (β − 1)·pre y la
  covariable τ; con pre positiva (+0,224 sd) el cambio añade −(1 − β)·pre, del signo que busca C1,
  para todo β < 1, y con β = 0 un nulo sale como −pre.
  (3) La 19 fija si D3 se mide en sd o en metros (aquí, sd de la celda). (4) La elección de qué
  contraste usaría C3 no tiene respuesta dentro de las reglas (ni bajo/alto sin estratos ni uno
  contiguo dentro de estrato las cumplen, véase arriba): la hará CP1, cambiando por escrito la
  regla de estratos o D2 y definiendo D3 para un nivel.
  **Mutaciones** (22 sobre el código, script en el scratchpad, todo restaurado; todas matan algún
  test, entre paréntesis cuántos): las pedidas, ruido que ignora la correlación dentro de la
  posesión, que infla la potencia (2: `test_ignoring_the_possession_correlation_inflates_the_power`
  y `test_the_noise_carries_the_planted_correlation`), y leer el desenlace en vez de la estadística
  previa, imposible por construcción porque `ball_advance` y `block_before` rehúsan un retardo
  negativo (`test_the_readers_refuse_a_lag_after_t`), con el avance leído después de `t` (5), el
  bloque leído después de `t` (1; el test de "nada después de `t`" ponía a todos los jugadores en
  un punto, la anchura salía 0 con los dos valores y no lo veía: ahora se reparten y lo mata con 4)
  y el retardo negativo admitido (1). Además: aproximación sin la raíz (4), bloqueada con la
  varianza sin bloquear (4), q unilateral (7), parte compartida por unidad y no por posesión (3),
  regla de 7 de 10 (4), partido sin celda que cuenta (1), celdas bajo el mínimo (2), correlación
  sin estandarizar (5) o con cada unidad emparejada consigo misma (7), cota de 2 nulos (2), nulo
  completo fuera de la celda (4), causa a 10 m (2), V1 de C1 sin los rivales (1), grupos de C3
  cambiados (1), V1 de la longitud con los fijadores de la anchura (1), rachas que no cortan por
  equipo (2), nulo que nunca bloquea (1) o que bloquea con cualquier correlación (1). El contraste
  de la aproximación (`test_the_approximation_matches_the_full_permutation`: 10 partidos x 2
  estratos x 24 unidades, 3.000 réplicas, 3 semillas, sin bloquear y bloqueado con `rho` 0,3 y
  grupos por posesión, efectos 0, 0,3, 0,45 y 0,6) exige menos de 0,025 con la permutación completa
  sobre los mismos conjuntos.
  **Desviaciones.** (1) La causa de C1 es el proxy de 5 m, no un corte del índice: el plan no lo
  fija; si la 19 lo cambia, se rehace la potencia. (2) El contraste de C3 (bajo frente a alto), sus
  estratos con el balón en lugar del poseedor y la versión sin estratos son convenciones mías. (3)
  El nulo bloqueado invierte el signo por posesión (P5), no permuta etiquetas por bloques (no
  definido cuando una posesión tiene los dos grupos); la 19 tiene que escribir el mismo o rehacer
  la potencia. (4) Se bloquea con la correlación agregada de V0 y no con el máximo por partido: el
  máximo de 20 estimaciones con correlación 0 pasaba de 0,1 en el sintético; en estos datos la
  decisión es la misma con las dos reglas (C1 no pasa de 0,016 en ningún partido ni variante; C3
  pasa de 0,1 en algún partido en las cuatro combinaciones). (5) La pre-tendencia de C1 se mide aquí y la de C3 no. (6) La
  correlación de C3 se mide en todas las fases medidas, no solo bajo y alto. (7) Es la potencia de
  la mitad de calibración: la del reservado (D2, "en alguna mitad") no se puede medir sin abrirlo.
  (8) La tasa sin efecto del nulo bloqueado en la longitud de C3 (0,0018) pasa de 0,00135: la 19
  lo tiene que mirar si se elige C3. (9) El mínimo de 100 recepciones de V1 de S2 no se revisa: C2
  murió por otro criterio. Nadie leyó el reservado; ninguna cifra de `(t, t + W]` de ninguna
  candidata.
- [x] 18. `opus` (subagente `revisor-adversarial`) Revisión de 11 a 17 antes de CP1, repetida
  sobre los arreglos hasta que no salga nada alto ni medio.
  Revisión 18, pasada 1 (2026-10-18): seis hallazgos (3 medios, 3 bajos, ningún alto), todos
  arreglados; falta la re-revisión. Las cifras salen de `reports/power.json`.
  - *Medio 1, la tabla de CP1 no mostraba la cifra que decide C1.* `power.json` imprime por
    variante `pretrend`: la pre-tendencia agregada sobre todas las celdas (partido, estrato) con
    los pesos del bar, el efecto que D3 deja pasar en valor absoluto (|pre-tendencia| / 0,5), su
    razón con el MDE80 y la vara de S2 (`s2_bar`). C1: V0 +0,224 sd, |efecto| > 0,447 (3,7 veces
    el MDE80); V1 +0,216, > 0,433 (3,6); por encima de 0,15 sd en 9 de 10 en las dos, así que con
    la vara de S2 moriría. Fila nueva y notas 1 a 3 en la tabla de CP1; requisito (a) en la 19.
  - *Medio 2, "C3 no medible" era bajo/alto por construcción.* `phase_types_by_third` cuenta
    todas las fases de S3 por tipo y tercio del balón (total de los 10, propio/medio/final:
    `high_block` 569/2/1, `low_block` 0/349/462, `medium_block` 532/762/25). Contrastes contiguos
    dentro de estrato (`candidates.C3.contiguous`) con el mismo bar y la misma correlación previa
    (agregada de V0, 0,126 en la anchura y 0,208 en la longitud: nulo bloqueado), V0 y V1:
    bajo/medio en el tercio medio, MDE80 0,41 en anchura y en longitud (con alguna celda en 10 de
    10 partidos); medio/alto en el propio, 0,85 y 0,83 (en 8 de 10: los otros 2 nunca cuentan
    para el signo); en V1, no alcanzable en los cuatro; tasa sin efecto 0,0002 a 0,0009. Corregidos
    la tabla y el "Medido" de la 17; `testable_v0` lista cada diseño (ninguno de C3 llega a 0,3);
    la elección del contraste de C3 queda para CP1 (nota 4).
  - *Medio 3, la congelación no cubría todo lo que llega al código congelado.* `code_tree_sha` es
    el sha256 de `git ls-tree HEAD -- .python-version pyproject.toml src uv.lock`, y un checkout
    sin alguno de ellos no se puede congelar; test que cambia cada fichero (`.python-version`,
    `pyproject.toml`, `uv.lock`, `cli.py`, la puerta, `defence/` y `reliability/`) y un módulo
    nuevo bajo `src`, y ve cerrarse el reservado. Diff de la 23 ampliado. Lectura única: la fase 3
    la deja a J4 y a la 24 (`ac2fb heldout read` no existe), así que va como requisito explícito
    de la 23 y no se implementa ahora.
  - *Bajo 4, solape de ventanas.* `candidates.C1.window_overlap`, sobre las unidades de C1 en
    V0: hueco con la anterior del mismo periodo de W o menos, 8,9 a 14,0 % (del mismo equipo, 7,3
    a 11,2 %); de 2W o menos, 37,7 a 46,2 % (31,7 a 40,1 %). Requisito (b) en la 19.
  - *Bajo 5, agujeros del chequeo estático.* `tests/test_single_door.py` rechaza además pandas,
    polars y fastparquet; todo pyarrow salvo `pyarrow`, `compute` y `parquet`; privados y módulos
    de entrada de pyarrow por alias; lectores de fichero por nombre (Parquet, CSV, JSON, IPC,
    NumPy, mapas de memoria, flujos); abrir o listar ficheros (`open`, `read_text`, `read_bytes`,
    `glob`, `listdir` y similares) salvo la lectura de informes de `power`; la raíz de datos
    fuera de `cli` y `reliability.long`; y cadenas con `bronze`, `jsonl`, `_parquet`, `pandas` o
    `polars` (55 fragmentos que rechazar, eran 23; 10 que dejar pasar, eran 7; las excepciones
    son por módulo). Puerta: `read_bronze_players` (guardada, en la tabla de rutas); el test
    `realdata` del portero lee la plantilla por ella y no con duckdb; el `realdata` de la puerta
    sirve y rehúsa con los tres lectores de bronce (en el reservado solo comprueba que rehúsa).
  - *Bajo 6, test tautológico.* Literales 4 y 5 en
    `test_measure_needs_enough_players_and_finite_coordinates`.
  **Mutaciones (30, scripts en el scratchpad `review18_fix`, todo restaurado; entre paréntesis,
  tests que fallan):** `MIN_PLAYERS` de 5 a 3 (1) y a 4 (1); sha de `defence` y `reliability`
  solo (10), sin `uv.lock` (8), sin `pyproject.toml` (8), sin `.python-version` (8), que acepta
  un checkout sin un pin (3); chequeo que admite submódulos de pyarrow (6), pandas y polars (2),
  sin la regla de abrir ficheros (7), con la excepción por nombre y no por módulo (2), sin
  excepción (2: `power` no podría leer sus informes), con la raíz de datos en todas partes (4),
  sin la regla de privados de pyarrow por alias (2), sin `OSFile` (1), sin `ParquetReader` (1),
  sin `memory_map` (1), sin las cadenas nuevas (3); `read_bronze_players` sin guarda (1); suelo de
  D3 sin valor absoluto (1) o con la razón al revés (1); pre-tendencia agregada con las celdas de
  dos partidos juntas (1) o como media sin pesos (1); vara de S2 que muere con 2 (1); contraste
  contiguo que ignora su tercio (1) o leído como bajo/alto (1); tipos por la longitud del balón y
  no por el tercio (1); solape con `<` (1), entre periodos (1) y ciego al equipo (1). La primera
  pasada dejó viva la de `OSFile`: se añadieron fragmentos literales.
  **Gate local en verde** (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 736 pasan,
  eran 679; 15 deseleccionados, eran 13; `pytest -m realdata`: 15 de 15, con `power.json`
  confirmado byte a byte); todas las cifras anteriores de `power.json`, iguales (cambian solo el
  texto de la regla y `testable_v0`). Commits: `68bd574` (bajo 6), `cb5f39c` (medio 3),
  `58aa3a5` (bajo 5) y `b86ed70` (medios 1 y 2, bajo 4 e informe), empujados; **CI en verde:
  https://github.com/javiersr1996/ac2-football/actions/runs/39153216333** (736 pasan, 99 s). Los
  dos commits intermedios, probados aparte en worktrees (ruff, `mypy src` y sus tests de puerta,
  chequeo, rutas y bloque: 408 y 447 pasan).
  **Desviaciones.** (1) `.python-version` entra en el sha (no se pedía: fija el intérprete). (2)
  El solape se mide sobre las unidades de C1 y con W o menos (el instante cae en la ventana de
  desenlace), no sobre todas las recepciones con `< 13`. (3) Lector nuevo `read_bronze_players`
  en la puerta. (4) Las excepciones del chequeo (la lectura de informes de `power`; la raíz de
  datos en `cli` y `reliability.long`) son por módulo y explícitas; el chequeo no ve un
  subprocess ni una ruta escrita a trozos. (5) A C1 no se le aplica la vara de S2: se imprime y
  decide CP1. (6) Los contrastes contiguos usan la correlación previa de todas las fases, como
  bajo/alto. Nadie leyó el reservado; ninguna cifra de `(t, t + W]` de ninguna candidata.
  Revisión 18, pasada 2 (2026-10-18): cinco hallazgos (2 medios, 3 bajos), arreglados en `e574fa4`;
  falta la re-revisión. (Medio 1) La nota 2 y el requisito (a) ofrecían el desenlace como cambio
  respecto a lo previo, que añade −(1 − β)·pre del signo de C1: se quita y queda la covariable
  dentro de celda. (Medio 2) La tabla, la recomendación, la nota 4 y el requisito (c) dicen que C3
  no tiene diseño que cumpla las reglas (dentro de estrato D2 los mata; sin estratos incumple la
  regla de estratos, su nulo de longitud da 0,0018 y D3 no aplica); tasa añadida a la tabla;
  `team_out_of_possession_phase_type` anotado como sospechoso, sin confirmar. (Bajo 3) La
  excepción del chequeo estático es por sitio (módulo, función, llamada y receptor); `power` ya
  no lee ficheros (el CLI lee los tres informes y le pasa los veredictos); el chequeo rechaza
  además cualquier mención de `open`, `read_text` y similares sin llamada, `FileIO`, `open_code`,
  `linecache`, `fileinput` y `copyfile`. (Bajo 4) Quitado el "8,1 a 12,5 %" sin artefacto; la fila
  de D3 de la tabla da 0,447 solo para V0 (V1 informativa). (Bajo 5) La 23 exige que `ac2fb heldout
  read` compare las versiones instaladas con `uv.lock` antes de abrir. **Mutaciones (10, script en
  el scratchpad `review18b`, todo restaurado; cada una hace fallar el test del chequeo):**
  `Path(...).read_text()` en `power` y en otro módulo, `io.FileIO`, `io.open_code`, `linecache`,
  `fileinput`, `shutil.copyfile`, `f = open; f(p)`, lectura fuera de la función permitida del CLI
  y la función permitida copiada a `power`. Gate local en verde (751 pasan, 15 de 15 `realdata`);
  **CI en verde:
  https://github.com/javiersr1996/ac2-football/actions/runs/39156486410**. Sin desviaciones
  de fondo: `probe_verdicts` recibe los informes ya leídos y vive aún en `power`. Nadie leyó el
  reservado; ninguna cifra del desenlace.
  Revisión 18, pasada 3 (2026-10-18): sin altos ni medios; tres bajos arreglados en `f56024e`: (1) la
  exención `status.open` del chequeo estático solo vale si no se llama (`status = Path(p);
  status.open()` e `import io as status` ya fallan); (2) `from io import open as o` y
  `from os import listdir as ls` se rechazan y el docstring cita `ALLOWED_FILE_SITES`; (3) la
  recomendación y el requisito (c) dicen que elegir C3 cambia la regla de estratos o D2 después de
  ver su cifra (choca con "un umbral que falla no se mueve"), con el nulo de longitud sin estratos
  (0,0018 > 0,00135) y que en V1 solo mide la anchura (MDE80 0,41). Cifras de `power.json`.
  Mutaciones: sin los arreglos fallan 4 snippets de `REJECTED`. Cerrada.
- [x] CP1. **[Javier] lun 2 nov.** Elige UNA pregunta con la tabla delante (por candidata:
  instrumento pasa o no, pre-tendencia dentro de estrato, fracción extrapolada que la sostiene,
  n por partido en V0 y V1, MDE80, riesgo y encaje con los 5 criterios). Va recomendada primero
  la que salga de la regla: C2 si S2 pasa y su MDE80 en V1 es ≤ 0,3 sd; si no, C1; C3 solo como
  respaldo; ninguna viva, rama B.
  **Cerrado el 2026-10-18 (adelantado): Javier eligió C1**, la recomendada por la regla, con la
  tabla revisada en tres pasadas delante y avisado de su riesgo: D3 en el reservado le exige
  |efecto| > 0,447 sd en V0 (pre-tendencia agregada +0,224 sd, `power.json`), y con la vara de
  S2 también moriría. Si cae, rama B con el negativo medido. C2 muerta en sonda; C3 descartada.

## Fase 2: protocolo y calibración (lun 2 nov a dom 15 nov)

- [x] 19. `fable` Protocolo en `stage: "design"` (`protocol/protocol.json`), escrito antes de
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
  protocolo se lee de un fichero de resultados. **Requisitos de la revisión 18:** (a) fija si D3
  se mide en sd (de la celda, como en la 17) o en metros, y cómo trata la reversión a la media de
  una pre-tendencia positiva (nota 2 de la tabla de CP1): con lo previo como covariable dentro de
  celda, no con el desenlace como cambio respecto a lo previo, que añade −(1 − β)·pre; (b) excluye o bloquea las unidades cuyo
  instante cae en la ventana de desenlace de la unidad anterior del mismo periodo: en C1, 8,9 a
  14,0 % de las unidades de V0 con un hueco de W o menos (7,3 a 11,2 % del mismo equipo), y 37,7
  a 46,2 % con 2W o menos, cuya ventana previa toca esa ventana de desenlace (31,7 a 40,1 % del
  mismo equipo; `power.json`, `candidates.C1.window_overlap`); si la 19 cambia W o las unidades,
  la cifra se rehace; (c) C3 no tiene diseño que cumpla las reglas del plan (tabla de CP1): sin estratos su nulo de longitud da 0,0018 de tasa sin efecto, por encima de 0,00135 (`power.json`), y en V1 solo mide la anchura (MDE80 0,41); si CP1 la elige, antes de la 19 cambia por escrito la regla de estratos o D2 (después de ver su cifra, lo que choca con "un umbral que falla no se mueve" y con los criterios inamovibles, como la nota 1 con C1) y define D3 para un nivel, y la 19 escribe el contraste resultante.
  Medido (2026-10-19; las cifras salen de `reports/design.json`, 10 de calibración, por partido;
  rangos entre partidos, calculados por script desde el informe): **protocolo y código en
  `8ede609`, commiteado a las 11:48:16 y antes de calcular el diseño en ningún partido real (el
  informe se escribió a las 11:48:41); empujado después, a las 11:50:54** (CI en verde, run
  39233113080). A diferencia de la 14 a la 17, la marca pública del push es posterior al cálculo;
  el diseño solo lee hasta `t` y no se ha calculado ningún desenlace. Antes, `6f209f3` arregla
  `power._pretrend` y `_pretrend_pooled`, que no dejaban fuera las unidades sin estadística previa
  (`_correlation` sí lo hacía); ninguna unidad de la 17 la tenía vacía (habría fallado), así que
  `power.json` no cambia, y el test de la pre-tendencia a mano fallaba sin el arreglo. Gate local
  en verde (ruff, format, `mypy src`, `pytest -q`: 864 pasan, 19 deseleccionados; `pytest -m
  realdata`: 19 de 19; `ac2fb protocol --check`: 89 campos de esquema, 24 reglas de coherencia, 23
  constantes contra el código, 26 campos numéricos, todos justificados). Nuevo: `defence/design.py`,
  `protocol/check.py`, `pressure.PRESSED_INDEX` (0,5) y los comandos `ac2fb design [--match ID]
  [--reports-dir D]` (20 s para los 10) y `ac2fb protocol [--check]`; sus rutas públicas, cubiertas
  por el test de la 11. Requisitos de la revisión 18: (a) D3 en sd de la celda
  (`death_criteria.D3.why_sd`) y el efecto como coeficiente del grupo ajustado por lo previo dentro
  de celda (`statistic.why_adjusted`); (b) se excluye la unidad posterior (`units.exclusion`); (c)
  no aplica, CP1 eligió C1.
  - *Unidades.* Etiquetadas 653 a 936; de diseño 650 a 934; excluidas por solape 73 a 125 (8,9 a
    14,0 %, la cifra de la revisión 18 sobre las mismas unidades); quedan 577 a 851 (7.229 en
    total), sin ningún instante en la ventana de desenlace de otra (`within_w` 0 en 10 de 10); con
    la ventana previa tocando la de desenlace anterior (2W), 26,5 a 32,9 %, contadas y no
    excluidas. Sin estadística previa: 0 en 10 de 10.
  - *Causa.* Presionadas (índice ≥ 0,5) 239 a 284 (30,8 a 48,2 %); el proxy de 5 m coincide con el
    índice en el 84,7 a 89,6 %. V1 (portador y rivales cercanos detectados en `t`): 534 a 817 (91,7
    a 98,6 %), 200 a 268 presionadas. V2: clase 1, 11 a 47 unidades; 2 o más, 0 a 11 (pocas celdas,
    como avisaba el protocolo). Balón extrapolado en `t`: 0,1 a 0,9 %.
  - *Bloqueo.* Correlación agregada de la estadística previa en V0: −0,004, por debajo de 0,1. El
    nulo no se bloquea, como fija `null.blocked`.
  - *D2 en calibración.* MDE80 0,13 sd en V0 y en V1, por debajo de 0,3 (tasa sin efecto 0,0009 en
    V0 y 0,0006 en V1, las dos ≤ 0,00135). La 21 lo reimprime.
  - *D3, el riesgo de C1.* Pre-tendencia agregada con la causa del protocolo: V0 +0,181 sd (+0,59
    m), así que la 21 exige |efecto| > 0,363 sd en V0 (2,8 veces el MDE80; 1,18 m); V1 +0,190
    sd, umbral 0,379. Por partido en V0, +0,054 a +0,397: positiva en 10 de 10 (la presionada recibe tras
    más balón hacia delante). Con el proxy de 5 m sobre las mismas unidades: V0 +0,221 sd, > 0,441,
    casi la de la 17 (+0,224, > 0,447). Con la vara de S2 (más de 0,15 sd en más de 2 partidos)
    moriría: 5 de 10 en V0, 7 de 10 en V1. Esa vara no es criterio de C1 y no decide nada.
- [x] 20. `sonnet` Estimador validado con sintéticos antes de tocar datos reales: efecto plantado
  que se recupera; pre-tendencia plantada que sale por D3; confundidor plantado (presión con pase
  hacia delante y línea que sigue al balón, como m10) que el estrato anula; jugadores interpolados
  linealmente en hueco que dan residuo cero y disparan la monotonía de V2; 5 semillas cada uno.
  Mutación: la causa en `t + 1 s` deja pasar la pre-tendencia; sin estrato pasa el confundidor.
  Hecho (2026-10-19): **código en `26f97cf`, empujado a las 13:40 antes de calcular ningún
  desenlace en un partido real** (CI en verde, run 39246359431). Lo escribió un subagente `sonnet` con
  prohibición de tocar datos reales, `reports/`, el protocolo y git. Revisión posterior: diff leído
  entero y contraste independiente en el scratchpad (mínimos cuadrados celda a celda y la
  permutación reconstruida desde la corriente documentada), que da el mismo T, E_m, P y los 300
  primeros nulos con diferencias de orden 1e-16, y S_k que suma T. Gate local en verde (`sync
  --locked`, ruff, format, `mypy src`, `pytest -q`: 983 pasan, eran 864; 19 deseleccionados; `ac2fb
  protocol --check`: 26 constantes contra el código, eran 23, y 0 números solo del protocolo).
  Nuevo: `defence/effect.py` (el lector del desenlace, único que lee después de `t`; el
  estadístico ajustado por lo previo, la pre-tendencia, el nulo por permutación dentro de celda y
  su versión bloqueada por posesión, las barras de calibración y de reservado con Holm, D3, D4 y
  V2), `tests/effect_helpers.py` y `tests/test_effect.py` (93 tests, unos 19 s); `null.seed`,
  `bars.heldout.alpha` y `death_criteria.D4.ratio` pasan de `PROTOCOL_ONLY` a `CODE_CHECKS`. Sin
  comando ni informe: los añade la 21.
  - *Sintéticos, semillas 0 a 4* (umbrales de `tests/test_effect.py`). (a) Efecto plantado de
    −0,5 sd recuperado con error menor de 0,08 y barra superada con al menos 9 de 10 partidos; sin
    efecto, p > 0,05 y la barra no pasa. (b) Pre-tendencia sin efecto (la presionada recibe 0,8 m
    más de balón hacia delante y el desenlace conserva 0,6): D3 mata en las 5; la diferencia simple
    supera 0,3 sd y el coeficiente ajustado queda por debajo de un cuarto de ella. (c) Confundidor
    por el pipeline real (`score_receptions`, `design_units`): con estratos, |T| < 0,1 y la barra
    no pasa; con un solo estrato, T > 0,12 y la barra pasa. (d) Rivales interpolados en línea recta
    dentro del hueco: residuo de la capa 2 (`runs.second_differences`) < 1e-9 en más de 1.000
    filas extrapoladas y > 0,1 en las detectadas; |T| de la clase 0 mayor que 2 veces la de la 1,
    y esta mayor que 4 veces la de 2 o más; |T_V0| < 0,8 |T_V1|. (e) Causalidad inversa (los
    defensores cierran después de que el balón no avance): con la causa en `t`, |T| < 0,15 y la
    barra no pasa; con el índice a `t + 10` frames, T < −1, la barra pasa en 10 de 10 y D3 no lo ve.
  - *Mutaciones* (todas revertidas, `pressure.py` sin cambios). Causa en `t + 1 s`: falla
    `test_a_cause_read_at_t_finds_no_effect_in_reverse_causation` (|T| de 1,60 contra < 0,15;
    repetida aparte en la revisión). Sin estratos: falla `test_the_strata_cancel_the_confounder`.
    Además tumban al menos un test cada una: sin covariable, ddof 0, permutar entre celdas, T = 0
    como acuerdo, corriente sin la mitad, p sin el +1, Holm como Bonferroni, D3 estricto, pesos n,
    contribuciones bloqueadas sin x, unidades sin ordenar, V1 con un extrapolado, pre-tendencia sin
    estandarizar y desenlace sin signo.
  - *Decisiones que el protocolo no fijaba* (en el docstring de `effect.py`): la celda con x
    colineal con G queda fuera y se cuenta (`collinear_cell`); las unidades se ordenan por
    (partido, estrato, periodo, frame) antes de sortear; empate a 1e-9; un criterio no evaluable
    (sin celda) mata.
  - *Para la revisión 22.* (1) Permutar G con x fija ignora la correlación entre G y x: con
    pre-tendencia, la varianza real del coeficiente es mayor por un factor 1/(1 − r²_Gx), así que
    el p sale algo optimista justo cuando P no es pequeño (la nota de D2 ya cita ese factor para la
    potencia); cuantificarlo con la calibración o pasar a permutar residuos (Freedman-Lane) antes
    de congelar. (2) `read_outcome` no comprueba el periodo de la fila de balón en `t + W` (las
    filas de balón no lo llevan) y se apoya en que fuera de periodo no hay fila de balón (el bronze
    de la base documenta esos frames con `ball_data` nulo). (3) `P` deja fuera las celdas con x
    constante y `T` no: "las mismas celdas" de D3 solo es exacto con x continua. (4) "p ≤ 0,00135"
    y "a lo sumo 1 nulo" coinciden solo con 2.000 nulos. (5) Con T_V0 = 0, D4 mata si T_V1 ≠ 0
    (cambio de signo) y no mata si T_V1 también es 0; la barra de V0 falla igual (corregido en la
    revisión 22: decía que D4 no mataba).
- [x] 21. `opus` Calibración: efecto por partido en los 10, las tres variantes, pre-tendencia y
  veredicto mecánico D1 a D5 en `reports/calibration.json`. Nada de este paso mueve un umbral.
  **Decisión previa, tomada el 2026-10-19 antes de calcular ningún desenlace (Javier): el nulo
  se queda como dice el protocolo** (permutar G dentro de celda con x fija), sin Freedman-Lane.
  Punto (1) de la 20: con pre-tendencia, ese nulo subestima la varianza del coeficiente por
  1/(1 − r²_Gx). Se midió en el scratchpad solo con G y x del diseño (nada después de `t`, las
  mismas 133 celdas de V0 y 130 de V1 que `design.json`): varianza ×1,054 en V0 y ×1,058 en V1
  (media ponderada por celda), así que la tasa real de la barra sería 0,0018 y no 0,00135. No
  decide nada en C1: con `sum w` = 1.241 en V0, un efecto en el umbral de D3 (0,363 sd) tiene z de
  12,5 ya corregido, y el p solo pesaría hacia z = 3,2 (unos 0,09 sd), donde D3 ya mata; en el
  reservado el sesgo y el umbral de D3 nacen de la misma correlación entre G y x. **Requisito de
  la 21:** `calibration.json` imprime ese factor por variante (media ponderada, mediana y máximo
  por celda) como diagnóstico que no decide nada, y estas cifras se confirman con él.
  Hecho (2026-10-19; las cifras salen de `reports/calibration.json`, 10 de calibración, por
  partido; rangos entre partidos, calculados por script desde el informe): **código en
  `ee2e2c3`, commiteado a las 14:25:24 y empujado a las 14:25:26 antes de calcular ningún
  desenlace en un partido real; el informe se escribió a las 14:25:55** (CI en verde, run
  39251937842). Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 1.020
  pasan, eran 983; 19 deseleccionados; `pytest -m realdata`: 26 de 26, eran 19; `ac2fb protocol
  --check`: OK, sin números nuevos). Nuevo: `defence/calibration.py` (el orden de lectura del
  protocolo: diseño, desenlaces, efectos con su nulo y la barra, criterios), el comando `ac2fb
  calibration [--match ID] [--reports-dir D]` (19 s para los 10), `tests/test_calibration.py`
  (24 tests sobre medios sintéticos por el pipeline real, 5 semillas en el efecto plantado y en
  el nulo, 3 en D1, D3 y D4) y `tests/test_realdata_calibration.py` (7); `design._LABEL` pasa a
  `design.POWER_LABEL` para que la 21 reimprima el MDE80 con el mismo flujo. D1 se recalcula con
  el código de la sonda S1 (no se lee `probe_s1.json`) y el realdata comprueba que coincide.
  Contraste independiente en el scratchpad (desenlace leído de los arrays del balón con un
  diccionario, cada celda ajustada con `np.linalg.lstsq` sobre `[1, x, G]`, factor con
  `np.corrcoef`): T, P, E_m, celdas, acuerdo de signo y factor iguales con diferencias < 5e-7
  (el redondeo del informe).
  - *Veredicto mecánico: D3 mata; D5 mata; el reservado no se abre (rama B).* V0: T = −0,193 sd
    (signo esperado, 1,48 veces el MDE80), p = 0,0005 (0 de 2.000 nulos tan extremos), mismo
    signo en 8 de 10: **pasa la barra de calibración**. Pero la pre-tendencia agregada es
    +0,181 sd (+0,589 m): |P| es el 94 % de |T|, por encima del 50 % de D3; el efecto tendría que
    pasar de 0,363 sd (el umbral que ya fijaba la 19 sobre las mismas 133 celdas). D1 no mata (10
    de 10 crecientes, como la sonda S1), D2 no mata (MDE80 0,13 sd en V0 y en V1, el de
    `design.json`), D4 no mata (T_V1 −0,200 sd, mismo signo y más que la mitad de V0).
  - *Por partido.* E_m en V0 de −0,364 a +0,093; negativo en 8 de 10; positivo en 2015213
    (+0,093) y en 2010085 (+0,000477; si fuera negativo serían 9 de 10). El 8 de 10 cuelga de
    cada uno de los 8 negativos, el más débil 1959846 (−0,109), y no decide nada porque D3 mata
    igual (corregido en la revisión 22: decía que colgaba de 2010085). P por partido de +0,054 a +0,397 sd (+0,255 a +1,533 m), positiva en
    10 de 10; |P| ≥ 50 % de |E_m| en 7 de 10 (lectura por partido, no es criterio). V1: E_m de
    −0,373 a +0,056, negativo en 8 de 10, P +0,190 sd, |P| el 95 % de |T|. Entre 11 y 14 celdas
    por partido; fuera por celda pequeña 166 presionadas y 896 libres en V0 (6.167 de 7.229
    unidades usadas).
  - *Desenlaces.* Ninguno indefinido (7.229 de 7.229). Balón extrapolado en `t` o `t + W`: 1,4 a
    5,3 % de las presionadas y 1,7 a 3,7 % de las libres. Con el balón detectado en los dos
    extremos (al lado, no decide): T −0,212 sd, 5.887 unidades usadas, 8 de 10.
  - *V2.* Las clases 1 (280 unidades) y 2 o más (38) no llenan ninguna celda: solo existe la 0
    (V1), `shrinks` nulo. Lo avisaba el protocolo.
  - *Factor de varianza, diagnóstico.* V0: media ponderada 1,0537, mediana 1,028, máximo 1,570
    (133 celdas); V1: 1,0575, 1,024 y 1,713 (130 celdas). Confirma el ×1,054 y ×1,058 medidos
    antes de la 21 sobre las mismas celdas (ningún desenlace indefinido, así que las celdas del
    efecto son las del diseño). No decide nada.
  - *Lo que sigue según el protocolo* (D5: "the protocol is not frozen for a reading, the
    held-out stays shut, and the entry publishes the negative with its figures per match"):
    la 23 no congela para una lectura y J4 no se lanza; la 22 sigue siendo la revisión adversarial
    antes de dar el veredicto por bueno; CP2 decide la rama B (y si se abre el reservado solo para
    la capa 2, irreversible). Esto lo decide Javier, no este registro.
- [x] 22. `opus` (subagente `revisor-adversarial`) Revisión del protocolo, el estimador y la
  calibración antes de congelar, hasta que no salga nada alto ni medio.
  **Decisión de Javier (2026-10-19), antes de la revisión: seguir la recomendación.** Primero la
  22; en CP2, rama B; el reservado se abre solo para la capa 2, después de la 22, por código y
  con registro (un commit público que diga que D5 mató la capa 3 antes de leer nada), y con una
  confirmación suya justo antes de abrirlo, porque es irreversible.
  Revisión 22, pasada 1 (2026-10-19), en dos frentes paralelos de solo lectura sobre `git diff
  aeefafc..HEAD` (A: el diseño contra el protocolo; B: el estimador, la calibración y el
  veredicto). **Ningún alto; el veredicto se sostiene: D3 mata, D5 mata.** Re-derivaciones
  independientes: A rehízo las 8.131 unidades de diseño de los 10 partidos sin `design_units`
  ni sus ayudantes (0 campos distintos; índice a 4,4e-16, x exacta) y el signo de ataque de los
  40 pares (periodo, equipo) por tres fuentes; B rehízo T, P, E_m y las 133 y 130 celdas sin
  `effect.py` (diferencias ≤ 5e-7, el redondeo del informe) y los 250 primeros nulos (1e-16).
  D3 con ocho lecturas de la escala: las seis que son D3 matan, la más favorable a C1 en 0,602
  (P en sd de y; 0,604 con el `calibration.json` vigente, por script); las dos que quedan por debajo miden el sesgo que explicaría el modelo lineal y
  no son D3 (adoptarlas ahora sería cambiar el criterio después de ver el desenlace).
  Arreglado en `c0eefa9` (scripts de mutación en el scratchpad, `fix22/mutate22.py`):
  - *Medio, A y B: ventanas que cruzan el descanso.* En 5 de los 10 (1886347, 1925299, 1959846,
    1996435, 2010085) el descanso deja 10 frames sin filas, menos que W: una recepción en los 3
    últimos frames del periodo 1 leía el desenlace del 2 (`read_outcome`) y una en los 3 primeros
    del 2 leía x y estrato del 1 (`ball_advance`, `incoming_ball`); el protocolo lo declara
    indefinido ("the period ends before t + W"). `MatchData` guarda `ball_period` y los tres
    lectores rechazan la ventana que lo cruza. Ninguna unidad afectada (la recepción más cercana
    al borde queda a 30 frames del inicio del periodo 2 y a 60 del final del 1): con este arreglo
    solo, los seis informes salen idénticos byte a byte. La nota (2) de la 20 queda resuelta.
  - *Medio, A: empate en un corte decidido por el float.* Partido 1874553, t = 20513: el balón
    de x 3,15 a 5,15 con signo −1 da −2,0000000000000004 y caía en `backward`; el protocolo dice
    "backward below −cut_m; lateral otherwise". Los tres cortes de estrato usan ahora
    `pressure.TIE` (1e-9). Esa unidad pasa a `lateral` y se regeneran `probe_s1`, `probe_s2`,
    `power`, `design` y `calibration` (`probe_s3` igual), sin ningún veredicto cambiado.
    Cifras nuevas, de los informes: calibración V0 T −0,192680 (era −0,192952), P +0,182152
    (+0,181267), |P|/|T| 0,945 (0,939), umbral de D3 0,364304 (0,362535); V1 T −0,199717, P
    +0,190513; E_m de 1874553 −0,131169 (−0,133453); acuerdo 8 de 10, p 0,0005; con el balón
    detectado en los dos extremos, T −0,211289. Diseño: ρ −0,004831 (−0,00416), MDE80 0,13 en
    V0 y V1. `power.json` (C1, proxy de 5 m): pre-tendencia +0,22438 (+0,223511), umbral 0,44876
    (0,447023). En S1 solo cambian las cuentas de dos estratos de 1874553 (una recepción pasa
    de `backward/middle/short` a `lateral/middle/short`); S2 sigue muerta (7 de 10).
    Las cifras de los registros de la 14 a la 21 quedan como se midieron entonces; las vigentes
    son las de los informes.
  - *Medio, A: el signo de ataque sin test sintético.* La mutación "x sin signo" pasaba los
    1.020 tests y solo la tumbaban los `realdata` de regresión (con ella P bajaba a +0,037 y D3
    no mataba; +0,036 con el código vigente, según la pasada 2). Test nuevo: el campo espejado (x y signos invertidos) en el periodo 2 da las
    mismas unidades.
  - *Bajos.* Nulo de V1 sobre las unidades de V0 y "nunca bloquear" sobrevivían: tests nuevos
    (el nulo de V1 sobre todas las unidades es el de las de V1; un medio con x correlacionada
    dentro de la posesión bloquea el nulo). La exclusión contra cualquier recepción etiquetada
    era equivalente en los datos: test con una recepción sin estrato seguida de una unidad. El
    test de causalidad inversa pasaba en vacío sin celdas: exige al menos 10. `protocol --check`
    no comparaba `design.EXCLUSION_GAP`: ahora sí (27 constantes contra el código, eran 26).
    Dos frases falsas de los registros de la 20 y la 21, corregidas en su sitio.
  **Mutaciones (11, todas tumban su test; ficheros restaurados, huella del diff igual antes y
  después):** desenlace, x y estrato sin el periodo del balón; corte de dirección y de longitud
  sin la tolerancia; x sin el signo; el signo del periodo 1 siempre; exclusión contra toda
  recepción etiquetada; nunca bloquear; nulo de V1 sobre V0; `EXCLUSION_GAP` a 12 en el código.
  Gate local en verde: ruff, format, `mypy src`, `pytest -q` (1.028 pasan, eran 1.020; 26
  deseleccionados), `pytest -m realdata` (26 de 26), `ac2fb protocol --check` OK.
  *Para contar el negativo* (de `reports/calibration.json`, V0, por dirección del balón
  entrante): hacia delante, 56 celdas y el 50 % del peso, T −0,466 y P +0,269; hacia atrás, 52
  celdas y el 38 %, T +0,124 (de signo contrario) y P +0,115; lateral, 25 celdas y el 12 %, T
  −0,052 y P +0,030. El efecto agregado sale de las recepciones con el balón llegando hacia
  delante, que es también donde la pre-tendencia es mayor. No es criterio; no decide nada.
  Revisión 22, pasada 2 (2026-10-19), de solo lectura sobre `git diff a0a3b68..e140984`.
  **Ningún alto; un medio, que no cambia ningún veredicto.** Los arreglos del periodo y del
  empate están completos en la ruta de C1; los seis informes, regenerados en la carpeta del
  revisor, salen idénticos byte a byte, y con solo el arreglo del periodo los cinco que cambiaron
  salen iguales a los de `a0a3b68` (la descomposición de la pasada 1 es cierta). Arreglado:
  - *Medio: el signo con el que se lee el desenlace, sin test sintético.* `effect_units` lee
    `attack_sign[(periodo, equipo)]` y el test espejado de la pasada 1 solo pasaba por
    `design_units`. Con el signo del periodo 1 siempre, o sin signo, pasaban todos los de `pytest
    -q` (en `realdata`, la regresión de `calibration.json` tumba la del periodo 1: 1 falla y 25
    pasan, según la pasada 3); en
    la calibración real la primera llevaba T de −0,193 a −0,064, el acuerdo de 8 a 7 y p de
    0,0005 a 0,024, sin cambiar el veredicto (cifras del revisor). Test nuevo: el mismo espejo en
    el periodo 2, por `effect_units`, da los mismos desenlaces (+7,5 y −4,0). Cada una de las dos
    mutaciones tumba ese test y solo ese (1 falla, 1.028 pasan).
  - *Bajos.* La tolerancia del corte de tercio no se alcanza (la profundidad es una x listada por
    1 o −1, exacta) y no tenía test: se quita, y la frase "los tres cortes" de la pasada 1 vale
    ahora para dirección y longitud. El protocolo no decía la condición de periodo que el código
    ya aplica: `units.requirements`, `units.outcome_undefined`, `outcome.period_end` y
    `strata.undefined` la dicen ahora; es una aclaración del texto que no mueve ninguna unidad
    (0 de las 8.142 recepciones etiquetadas tienen t − W o t + W en otro periodo, según el
    revisor). Los docstrings de `pressure`, `effect` y `DesignUnit.pre`, con la misma condición.
    Dos cifras de la pasada 1 eran de antes del arreglo del empate (0,602 y +0,037): anotadas en
    su sitio con las vigentes.
  - *Sospechoso, sin arreglo:* el corte del índice (`index >= PRESSED_INDEX`) y el de los rivales
    cercanos (`weights > 0`, que decide V1 y V2) no llevan tolerancia. En calibración no deciden
    nada (ningún índice a menos de 1e-6 de 0,5, ningún rival a menos de 1e-6 de 10 m ni de 5 m,
    ningún peso positivo bajo 1e-9). Si la capa 2 del reservado incluye el índice
    (`pressure.make_metric` usa los rivales cercanos), pesa allí: se decide al escribir ese
    código, antes de abrir.
  Gate local en verde: ruff, format, `mypy src`, `pytest -q` (1.029 pasan, eran 1.028; 26
  deseleccionados), `pytest -m realdata` (26 de 26), `ac2fb protocol --check` OK.
  Revisión 22, pasada 3 (2026-10-20), de solo lectura sobre `git diff e140984..c2d8e25`.
  **Ningún alto; un medio, en los tests y no en el código, que no cambia ningún veredicto.** Los
  seis informes, regenerados con `299dcac` en la carpeta del revisor, salen idénticos byte a
  byte, y las cifras del registro de la pasada 2 son las vigentes. Arreglado en `10b2820`:
  - *Medio: el equipo del signo, sin test sintético.* Todas las recepciones sintéticas son del
    equipo 1, así que los dos tests espejados solo fijaban el periodo de `attack_sign[(periodo,
    equipo)]`, no el equipo. Con el signo de un mismo equipo para todo portador pasaban todos los
    sintéticos en los tres lectores (`effect_units`, `design_units`, `score_receptions`) y solo
    caían las regresiones de `realdata`. En la calibración real (cifras del revisor), en el
    desenlace: T de −0,193 a +0,044, acuerdo de 8 a 6, p 0,115, D5 sigue matando; en la x del
    pre: P de +0,182 a −0,048 con T −0,176, 8 de 10 y p 0,0005, **D3 y D5 dejarían pasar la
    calibración**; en el índice y el estrato: T −0,076 y P +0,526, D5 mata. Los dos tests
    espejados se parametrizan sobre (periodo, equipo) = (2, 1), (1, 2) y (2, 2) con un ayudante
    común, `effect_helpers.moved` (el equipo del portador con otra etiqueta y el campo espejado
    donde ataca hacia −x; los signos del periodo 1 siguen en `attack_sign`, así que un lector
    con el periodo o el equipo equivocado lee un signo falso, no uno ausente; falso para las
    unidades del periodo 1, en un partido que no listaba el 2: lo arregla la pasada 4). Pasan a
    llamarse `test_the_carriers_period_and_team_do_not_move_an_outcome` y `..._a_unit`.
  - *Bajos.* El borde del tercio final en +17,5 no tenía test (`depth >= THIRD_CUT` pasaba los
    43 de estratos): caso nuevo en `test_the_stratum_of_the_incoming_ball`. En calibración
    ninguna profundidad de S1 ni de S2 cae en el corte y una de C3 sí (el revisor). Dos frases
    del protocolo seguían sin la condición de periodo (`outcome.ball_out_of_play` y la última
    convención): dicen ahora "in the period of t", sin mover ninguna unidad (0 de 8.142
    recepciones con t + W en otro periodo). La frase "pasaban todos los tests" de la pasada 2,
    acotada en su sitio.
  - *El sospechoso de la pasada 2, sin efecto en calibración (el revisor):* ningún índice a
    menos de 2,4e-4 de 0,5, ningún rival a menos de 1,3e-4 de 10 m ni de 5,7e-4 de 5 m; mover
    cada corte ±1e-9 no cambia ningún grupo. Para la capa 2: el peso positivo mínimo, 1,1156e-9,
    es geometría y no ruido (un rival detectado a 4,5 m casi justo detrás); con `> 1e-8`
    cambiarían 3 conjuntos de rivales cercanos y con `> 1e-6`, 15, sin mover V1 (todos están
    detectados). Se decide al escribir ese código, antes de abrir.
  **Mutaciones (11 tumban su test; en memoria, con el plugin del revisor, sin tocar `src`):** con
  el signo de un mismo equipo para todo portador, en el desenlace caen los casos (1, 2) y (2, 2)
  del test del desenlace; en la x del pre y en el índice y el estrato caen además los mismos dos
  del test de diseño. En la suite completa, solo esos: 2 fallan y 1.032 pasan; 4 y 1.030; 4 y
  1.030. Signo del periodo 1, +1, del otro equipo, negado, negado solo en
  el periodo 2: caen en el test del desenlace. x del pre sin signo: caen (2, 1) y (1, 2) de los
  dos tests. Tercio con `>=` o con `<=`: cae su caso de 17,5. Dos equivalentes al código, sin
  test posible: el signo con el periodo de la fila de t + W (`read_outcome` rechaza la ventana
  que cruza el periodo; 0 de 7.229 desenlaces cambian) y la tolerancia del tercio devuelta (0
  estratos cambian en S1, S2 y C3).
  Gate local en verde: ruff, format, `mypy src`, `pytest -q` (1.034 pasan, eran 1.029: los dos
  tests espejados pasan a seis casos y hay uno de estrato más; 26 deseleccionados), `pytest -m
  realdata` (26 de 26), `ac2fb protocol --check` OK.
  Revisión 22, pasada 4 (2026-10-20), de solo lectura sobre `git diff 299dcac..bbb3f4a`.
  **Ningún alto; un medio, otra vez en los tests, que no cambia ningún veredicto.** El arreglo
  de la pasada 3 cierra el equipo en los tres lectores; la calibración regenerada en `bbb3f4a`
  sale idéntica byte a byte y el diff no toca `src` ni los pines (mismo `code_tree_sha`).
  Arreglado en `8a25f87`:
  - *Medio: el periodo del signo, fijado en un solo sentido.* Con `period=1`, `moved` no listaba
    los signos del periodo 2, y los mundos base son de un periodo: un ayudante que ignora el
    periodo y se queda con el último listado pasaba los 1.034 tests en los tres lectores. En los
    10 partidos el periodo 2 se lista el último, así que daría su signo a las 4.286 recepciones
    del periodo 1 (de 8.142). En la calibración real (cifras del revisor), en la x del pre: T
    −0,184, P −0,034, 8 de 10, p 0,0005, **D3 y D5 dejarían pasar la calibración**; en el
    desenlace: T +0,064, acuerdo 7, la barra no pasa; en el índice y el estrato: T −0,070, P
    +0,541, D5 mata. `moved` lista ahora los signos de los dos periodos, ordenados por periodo y
    equipo, y admite la etiqueta 7, que no es un número de periodo: los casos pasan a ser (1, 1),
    (2, 1), (1, 2), (2, 2), (1, 7) y (2, 7) (`effect_helpers.MOVES`). La propuesta del revisor
    dejaba vivo un ayudante que ignora el equipo y se queda con el primero del periodo, porque
    listaba siempre primero el del portador; con el orden por equipo cae. El texto de `moved`, de
    los docstrings de mutaciones y del registro de la pasada 3, corregido.
  - *Bajo: dos lectores fuera de los tres, con el mismo hueco del equipo.* `power.c1_units` (que
    da `power.json`): test nuevo `test_the_carriers_period_and_team_do_not_move_a_c1_unit` con
    los mismos casos. `pressure.make_metric` (la sensibilidad de S1 y, si la capa 2 del
    reservado usa el índice, también esa) lee además la tabla larga, que `moved` no mueve: su
    test con un portador del equipo 2 y del periodo 2 va con el código de la capa 2, antes de
    abrir (con la tolerancia de la pasada 2). Ninguno de los dos toca D3 ni D5.
  - *Bajo: trazabilidad.* La pasada 3 solo guardó el log de 3 de sus 11 mutaciones y no el de
    ruff, format ni `protocol --check`; el revisor los re-derivó todos y son ciertos. Los de esta
    pasada se guardan todos (`fix22p4/sweep.log`, `mut_full.log`, `gate.log`,
    `lint_protocol.log` en el scratchpad de la sesión).
  - *Sin arreglo, bajos rebuscados que sobreviven:* el signo con el periodo de la última fila
    del balón, y con el equipo de la primera fila listada en t (en datos reales esa fila solo es
    del equipo del portador en 4.281 de 8.142). El revisor los tumba con un partido sintético de
    dos periodos (`review22_p4/alt/test_two_periods_alt.py`); no se adopta: ningún lector lee
    así el signo y el coste es un `MatchData` construido a mano.
  **Mutaciones (32 en memoria, con `mutplug4.py` del revisor, sobre los cuatro tests; el log
  tiene 33 bloques porque el primero es la línea base, según la pasada 5):** 26 tumban su test;
  las seis vivas son las cuatro equivalentes (signo con el periodo de t + W,
  tolerancia del tercio devuelta, equipo leído de la fila del portador, signo negado del rival
  más cercano) y los dos bajos de arriba. Lo que tumba cada una, en `fix22p4/sweep.log`. Con el
  ayudante que se queda con el último periodo caen los casos del periodo 1; con el signo de un
  mismo equipo, los del equipo 2 y 7; con la clave al revés, los del equipo 7. En la suite
  completa, solo esos: con el último periodo en el desenlace, en la x del pre y en el índice,
  3, 6 y 9 fallan (1.043, 1.040 y 1.037 pasan); con el equipo más bajo en `c1_units`, 4 (1.042).
  Gate local en verde: ruff, format, `mypy src`, `pytest -q` (1.046 pasan, eran 1.034: tres
  casos más en cada test espejado y los seis del de `c1_units`; 26 deseleccionados), `pytest -m
  realdata` (26 de 26), `ac2fb protocol --check` OK.
  Revisión 22, pasada 5 (2026-10-20), de solo lectura sobre `git diff bbb3f4a..c6096cf`.
  **Ningún alto ni medio: la 22 cumple su criterio.** El veredicto se sostiene (D3 mata, D5
  mata): `calibration.json` regenerado en `c6096cf` sale idéntico byte a byte, el diff solo toca
  tests y `todo.md` y el `code_tree_sha` es el de `bbb3f4a`. `moved` es equivalente para un
  lector correcto en los seis casos y ninguno pasa por construcción; ningún lector de `src`
  depende de las etiquetas {1, 2}. De 72 mutaciones (`review22_p5/logs/sweep5.log`) caen 51.
  Tres bajos:
  - *El recuento de la pasada 4* (33 y 27 por 32 y 26), corregido en su sitio.
  - *Los lectores que toman el signo de otra unidad, de otra fila o de una caché* sobreviven a
    los cuatro tests, porque cada mundo base es de un periodo y un equipo: 10 mutaciones (el
    periodo de la primera fila de jugadores, el signo de la primera unidad, una caché por equipo
    y una caché por periodo que olvida el equipo). En la calibración real, con el pre leído así
    (cifras del revisor, `calmut5.log`): con la caché por periodo T −0,190, P −0,007, 8 de 10, p
    0,0005; con el periodo de la primera fila T −0,184, P +0,047, 8 de 10, p 0,0005: **D3 y D5
    dejarían pasar la calibración**. En el desenlace y en el índice, D5 sigue matando. Solo las
    tumban las regresiones de `realdata`. El revisor lo deja en bajo porque ningún lector del
    proyecto tiene esa forma y los actuales están re-derivados (pasada 1) y fijados por
    `realdata`; sería medio si se ve plausible "un signo por periodo sacado de los datos". Un
    partido mixto, con los dos equipos en los dos periodos y un solo `attack_sign`, las tumba
    todas, y también los dos bajos de la pasada 4 (borrador de unas 60 líneas en
    `review22_p5/alt/test_mixed_alt.py`). **Lo decide Javier: adoptarlo (abajo).**
  - *El requisito de `make_metric` solo estaba en la 22:* diferirlo es aceptable (no alimenta D1
    a D5 y sus dos mutaciones tumban `test_realdata_s1`, `real_metric_s1.log`), pero pasa a la
    aceptación de la 25.
  **Decisión de Javier (2026-10-20): adoptar el partido mixto.** Arreglado en `8b02f78`, solo
  tests (el sha no cambia): `effect_helpers.mixed`, los cuatro cuadrantes (periodo, equipo) en
  un partido con un solo `attack_sign` y el portador del segundo equipo listado después de los
  rivales, y `unshifted`, que devuelve cada unidad a su mundo base; un test por lector
  (`test_both_teams_in_both_periods_give_the_same_outcomes`, `..._units` y `..._c1_units`), con
  el segundo equipo 2 o 7. **Mutaciones (las 72 de `mutplug5.py` del revisor, sobre los siete
  tests, `fix22p5/sweep.log`):** caen 63, entre ellas las 10 de esta familia y los dos bajos de
  la pasada 4; viven las 7 equivalentes (signo con el periodo de t + W, tolerancia del tercio
  devuelta, equipo de la fila del portador, signo negado del rival más cercano, signo del
  equipo listado primero en el desenlace y en el diseño, signo por volteo de periodo) y las 2
  de `make_metric`, que van con la 25. En la suite completa, las dos que en la calibración real
  dejarían pasar D3 y D5 (la caché por periodo y el periodo de la primera fila, en la x del pre)
  tumban solo los casos mixtos de diseño y desenlace: 4 fallan y 1.048 pasan cada una.
  Gate local en verde: ruff, format, `mypy src`, `pytest -q` (1.052 pasan, eran 1.046: los
  seis casos nuevos; 26 deseleccionados), `pytest -m realdata` (26 de 26), `ac2fb protocol
  --check` OK.
  Revisión 22, pasada 6 (2026-10-20), corta y de solo lectura sobre `git diff 4ca6618..c59acd4`.
  **Ningún alto ni medio: la 22 queda cerrada.** D3 mata y D5 mata (`reports/calibration.json`
  sin cambios; su regresión de `realdata` pasa en `c59acd4`). `mixed` es equivalente para un
  lector correcto: el revisor comprobó por script `key`, `frame_order`, el orden del balón, el
  portador 50 detrás de los rivales y al menos 9.774 frames entre cuadrantes frente a W = 13;
  ninguno de los tres lectores lee `gap`, el periodo de las filas de jugadores ni la tabla
  larga. Los tres tests son el borrador de la pasada 5, con las mismas aserciones. El barrido
  cuadra (72, 63, 9) y otras 9 mutaciones del revisor, que los docstrings dicen cubrir, caen
  solo en los casos mixtos. Dos notas sin severidad: los logs de `fix22p5` no llevan el HEAD
  (se escribieron antes del commit; repetidos en HEAD salen iguales), y
  `outcome_sign_other_period_neg` cae por un `KeyError` en el mundo base, un lector correcto
  rechazado con un error visible y no un hueco.
- [x] 23. Rama B: registro de D5, puerta de la capa 2, revisión y congelación. **Decisiones de
  Javier (2026-10-20), antes de escribir nada de esto:** (1) dos protocolos: `protocol.json`
  (capa 3) no se congela nunca para una lectura, como dice D5 ("the protocol is not frozen for a
  reading"), y pasa a `stage: "dead"`; la única lectura del reservado, solo para la capa 2, lleva
  su propio `protocol/layer2.json`; (2) antes de esa lectura se escriben, se corren en
  calibración y se congelan la 25, la 26 y el `--check` de sus dos comandos (las figuras leen
  solo `reports/` y van después). Como la puerta solo reproduce con el mismo `code_tree_sha`,
  todo cambio de `src` posterior a la lectura cierra el reservado en `HEAD`: sus artefactos se
  reproducen desde el commit de la lectura (un `git worktree` en ese commit). Orden: 23a, 23b,
  25, 30, 26, 23c, 23d, CP2, J4, 24 (la 30 se adelanta por decisión de Javier del 2026-10-22: no
  funcionar out of the box es lo único que descalifica; el borrador del README, adelantado de la
  33, entra antes que ella porque `clean_clone_check.sh` lee sus bloques).
  - [x] 23a. `sonnet` Registro público de D5, ya. `protocol.json` pasa a `stage: "dead"` con un
    bloque `verdict` (D5, `killed_by` y `v0_bar_passed` del informe, `reports/calibration.json`
    con su sha256, el commit y el `code_tree_sha` con los que se reproduce byte a byte, rama B,
    `heldout_read_for_layer3: false`); `code_tree_sha` sigue nulo (nunca se congeló). `protocol
    --check` admite `dead` y exige el bloque solo ahí (sin abrir `reports/`, como hasta ahora);
    un test contrasta el bloque con el informe; la puerta no abre en `dead`. Commit y push: es el
    registro de que la capa 3 murió antes de leer nada del reservado. Aceptación: tests de
    `check` y de la puerta; mutaciones anotadas (la puerta que abre en `dead`; un `killed_by` que
    no es el del informe).
    Hecho (2026-10-20). Antes de escribir el registro, `ac2fb calibration` regenerado en el
    scratchpad en `ccaafe5` sale idéntico byte a byte a `reports/calibration.json` (sha256
    `7ec16e6b…4814`, `code_tree_sha` `39a23a99…11da`, 37 s): son el commit y el sha que el bloque
    `verdict` registra. Cambian solo `stage` y ese bloque (`killed_by: ["D3"]`, `v0_bar_passed:
    true`, rama B, `heldout_read_for_layer3: false`); el resto del protocolo queda como se
    escribió antes de ningún desenlace. `check.py`: stage `dead` (con `design`, sin sha), esquema
    `VERDICT` de 10 campos exigido en `dead` y solo ahí, y 8 reglas nuevas (el bloque existe solo
    en `dead`; criterio D5; `killed_by` sin repetidos y dentro de D1 a D4, vacío solo si V0 no pasó
    su barra; rama B; reservado no leído; el informe; formatos de sha y commit). `protocol --check`
    sigue sin abrir `reports/`; el contraste con el informe (sha256 de los bytes, `killing`,
    `v0_bar_passed`, `calibration_passes`) es un test. La puerta no cambia: `dead` no está en
    `OPEN_STAGES`, y el test de los stages que no abren lo incluye. **Mutaciones (9, todas tumban
    su test; copias en memoria, diff igual antes y después; `d5/mutate23a.py` y su log en el
    scratchpad):** la puerta que abre en `dead`; `killed_by` D4; el sha256 del informe cambiado;
    sin la regla de "solo en `dead`"; `killed_by` vacío con la barra pasada; `killed_by` con D5;
    `dead` con sha obligatorio; el esquema de `dead` sin `VERDICT`; el reservado leído sin
    comprobar. Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 1.067
    pasan, eran 1.052; 26 deseleccionados; `pytest -m realdata`: 26 de 26; `ac2fb protocol
    --check`: 99 campos de esquema, eran 89; 32 reglas de coherencia, eran 24; 27 constantes
    contra el código; 26 campos numéricos, todos justificados). Commit `ed729c4`, empujado; CI en
    verde (run 39444922954).
  - [x] 23b. `opus` Puerta de la capa 2 y `ac2fb heldout read` (los requisitos de la revisión 18,
    adaptados). `protocol/layer2.json` (`design`, `frozen`, `read`): qué comandos lee y qué
    artefactos escribe (los de la 25 y la 26), `code_tree_sha`, y que no calcula nada de la capa
    3. La puerta abre el reservado solo con `protocol.json` en `dead`, `layer2.json` en `read`, su
    `code_tree_sha` igual al de `HEAD` y el árbol limpio; en `frozen` no abre nunca. `ac2fb
    heldout read` compara las versiones instaladas con las de `uv.lock` (`importlib.metadata`, y
    el commit de `ftbase` por su `direct_url.json`) y se niega si alguna difiere; commitea
    `layer2.json` en `read` (commit de la congelación, ids leídos, fecha) antes de calcular
    ninguna cifra, y después corre la 25 y la 26 sobre los 20. En `read`, solo reproduce con el
    mismo sha. Aceptación: tests de que `frozen` no abre fuera del comando, de que una versión
    instalada distinta cierra la lectura, de que la lectura no llama a ningún lector de la capa 3
    (`effect`, `design`, `calibration`, `power`) con un id del reservado y de que un cambio de
    código posterior la cierra; mutaciones anotadas (la puerta que abre en `frozen`; la lectura
    que no compara versiones; la lectura que commitea después de calcular).
    Hecho (2026-10-20). **Más estricto que lo escrito arriba:** el reservado se sirve solo
    *dentro* de `data.read_heldout` (un `ContextVar` que solo esa función activa), y fuera de
    ella toda ruta lo rechaza en todos los stages, también después de la lectura. Con la puerta
    abierta en `read` para cualquier lector, `reliability.match.load_match` serviría el reservado
    y una función pura de `defence/` podría calcular la capa 3 sobre él: el registro de D5 dice
    que eso no ocurre nunca. La condición de la puerta: `protocol.json` en `dead`, `layer2.json`
    en `read`, su `code_tree_sha` igual al de `HEAD` y el árbol limpio (`_guard`); en `frozen` no
    abre ni dentro de la lectura. `read_heldout(commands, reports_dir)`: con la puerta en
    `frozen` o `read`, los `reads` de `layer2.json` iguales a los comandos del código, el bloque
    `reading` presente solo en `read` y `lock.lock_mismatches` vacío, commitea `layer2.json` en
    `read` (`READ_MESSAGE`; commit de la congelación, ids, fecha UTC) y solo después corre los
    comandos; en `read` reproduce sin commit nuevo. Los comandos escriben en un directorio
    temporal fuera del checkout y sus artefactos se copian a `reports_dir` al final: **fallo
    hallado al revisar el diff**, un comando que escribía en `reports/heldout` ensuciaba el
    árbol y la puerta rechazaba al siguiente (test nuevo, que caía antes del arreglo con ese
    error). `protocol/lock.py`: todo lo instalado está en `uv.lock` con su versión, y `ftbase`
    con su commit (`Distribution.origin`, sin abrir ficheros); el cierre de dependencias de
    `ac2fb` sin marcadores está instalado (`colorama` y el grupo dev pueden faltar). En este
    entorno, 0 diferencias en 24 paquetes. CLI: `ac2fb heldout read [--reports-dir D]`
    (`reports/heldout/` por defecto; sale con 2 y los motivos si rehúsa) y `ac2fb status` con los
    dos stages. `protocol/layer2.json` en `design`, escrito a mano, con `reads: ["layer2"]`: el
    comando de la 12 (detección por distancia al balón, tramos y salto por banda de hueco), que
    la figura 1 necesita en los 20; la 25 y la 26 añaden los suyos, y el `--check` de `layer2`
    entra con ellos antes de 23c. Tests: `test_heldout.py` (16: la lectura commitea antes de
    calcular, solo `layer2.json`, con el registro; reproduce sin commit y un cambio de código la
    cierra; dos comandos que escriben dentro del checkout; 10 rechazos sin commit, sin llamar a
    ningún comando y sin escribir nada; el CLI no ejecuta ninguna función de `defence/`, medido
    con `sys.setprofile`; el `layer2.json` commiteado), `test_lock.py` (16), la puerta reescrita
    por stages (`test_data_gate.py`) y en `test_public_routes.py` dos barridos: en `read`, fuera
    de la lectura, toda ruta que toma partido rechaza el reservado; dentro, lo sirve.
    `test_realdata_gate` deja de exigir la puerta cerrada: los rechazos valen en todo stage.
    **Mutaciones (13, todas tumban su test; copias en memoria, árbol igual antes y después;
    `d5/mutate23b.py` y su log en el scratchpad):** la puerta que abre en `frozen`; la que sirve
    fuera de la lectura; capa 3 viva admitida; la lectura sin comparar versiones; la lectura que
    commitea después de calcular (con `frozen` abierto, que es lo único que la deja correr);
    `reads` sin comparar; una reproducción tomada por primera lectura; el registro sin el commit
    de la congelación; el lock sin el commit de git, sin el cierre de dependencias, siguiendo
    los marcadores y admitiendo un paquete que no lista; la lectura que ejecuta código de
    `defence/`. Gate local en verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`:
    1.193 pasan, eran 1.067; 26 deseleccionados; `pytest -m realdata`: 26 de 26; `ac2fb protocol
    --check` OK). Nadie leyó el reservado. Commit `913d8d9`, empujado; CI en verde (run
    39450823910).
  - [x] 23c. `opus` (subagente `revisor-adversarial`) Revisión de 23b, 25 y 26 antes de congelar,
    como la 22, **con un máximo de 3 pasadas** (decisión de Javier, 2026-10-22: la 22 necesitó 6).
    Un alto se arregla siempre; los medios que sigan vivos tras la tercera pasada van a Javier,
    que decide si se arreglan o se aceptan por escrito. Dos notas de la 26 esperan a Javier
    (2026-10-22): el docstring de `metrics.py` (línea 29) aún dice "Javier to confirm" sobre el
    área, confirmada en la 25, y como toca `src` va antes de la 23d; y el bloque completo del
    README no corre `ac2fb amputation` (su `--check` sí corre en full-build).
    **Pasada 1 (2026-10-23)**, en dos frentes paralelos de solo lectura sobre `git diff
    ed729c4..5dbee58` (A: la puerta y la lectura; B: las métricas de la 25 y la amputación de la
    26). Antes, el docstring de `metrics.py` dice ya que el área está confirmada (`5dbee58`).
    Arreglado en dos worktrees separados, uno por frente, y juntado en `main`:
    - *Alto, A: tras la lectura, editar `layer2.json` la reabría.* Con el sha del código nuevo en
      `code_tree_sha` (stage y registro intactos) la puerta servía el reservado a otro código; de
      vuelta a `frozen`, salía una segunda "primera lectura". La puerta lee ahora la historia
      (`_freeze`): en `frozen`, ningún commit anterior dejó `layer2.json` en `read`; en `read`, el
      último commit que lo tocó es la lectura (`READ_MESSAGE`, el único en `read`), el anterior es
      la congelación que el registro nombra; y desde la congelación nada del código ni de
      `protocol/` cambió, salvo `layer2.json` en `read`.
    - *Alto, A: `read_heldout` ejecutaba cualquier función.* Ya no recibe comandos: los toma de
      `ac2fb.reliability.reading.LAYER2_READS`.
    - *Medio, A: el registro guardaba `HEAD`, no la congelación, y un `split.json` cambiado
      después se leía.* Ahora guarda el commit de la congelación y `protocol/` entra en el diff.
    - *Medio, A: el lock comparaba metadatos, no lo que se importa.* Reglas nuevas en `lock.py`:
      cada módulo de primer nivel del cierre se importa desde su distribución (un `ftbase` en
      `PYTHONPATH` cierra la lectura), los ficheros de un paquete fijado por git (la base) siguen
      con los hashes de su `RECORD` (leído tal cual: en 3.13 `Distribution.files` oculta los
      borrados), y el intérprete es el de `.python-version`. Los hashes de numpy y pyarrow no se
      comprueban: tardan más de 2 min en Windows (la base, 55 ficheros, 0,2 s).
    - *Medio, A: cinco comprobaciones sin test.* Casos nuevos para todas.
    - *Bajos, A:* el comando `layer2` de la lectura ya no escribe el Parquet largo bajo `data/`
      (nada lo lee y se mezclaría con calibración); un fallo del CLI sale con 1 y `failed:`, no
      como rechazo; los pasos del README de full-build van con `shell: bash` (pipefail: con `| tee`
      un bloque roto no tumbaba el paso); el bloque completo del README corre también `ac2fb
      amputation` (la segunda nota de la 26: el clon debe quedar limpio, así que el CSV debe salir
      igual byte a byte).
    - *Alto condicionado, B: la reacción de la línea leía del periodo anterior.* En los 3 primeros
      frames del periodo 2, con un descanso de 10 frames (5 de los 10), `t - 13` cae en el periodo
      1; 0 casos en calibración, pero el reservado no se ha mirado. Ahora exige el mismo periodo
      en los dos extremos; `defence/` no se toca (la capa 3 está muerta) y el docstring anota la
      diferencia. Con el arreglo, las 10.425 celdas de calibración no cambian.
    - *Medio, B: cuatro mutaciones sobrevivían* (banda contada sin el `- 1`, relleno solo del
      último frame de la ventana, distancia al balón en `t - 13`, área con solo los jugadores de
      la anchura); cuatro casos plantados, cada uno tumba la suya.
    - *Medio, B: V2 mezclaba tamaños.* En la presión, n va de 0 a 11 jugadores y V2_0 eran sobre
      todo recepciones sin rivales cerca (en 2010085, de 0,01 a 2,26 por construcción). **Decisión
      de Javier (2026-10-23): V2 por "k de n"**, `V2_{k}of{n}`, ordenado por n y después k, con una
      agrupación aparte (`sensitivity_by_size`) para no cambiar `sensitivity()` ni los informes de
      la capa 3. n por métrica: 4 en línea y reacción, 2 en anchura y longitud, 1 en el rival más
      cercano, de 0 a 11 en la presión y 2, 3 o 4 en el área. `reliability.csv` pasa de 695 a 854
      filas (de 10.425 a 12.810 celdas): las 220 de V0 y V1, idénticas; de las 475 de V2, 330 solo
      cambian de etiqueta y el resto se parten.
    **Mutaciones: 18 en A (`mutate23c_a.py` y su log en el scratchpad de la sesión) y 5 en B,
    todas caen, cada una en su test.** Commits `3ffb031`, `e6a4c9d`, `be1a03b`, `65e9944`,
    `e43e241`, `eff9dda`.
    Gate local en `main` tras juntar los dos frentes: `sync --locked`, ruff, format, `mypy src`;
    `pytest -q` pasa 1.460 con 66 deseleccionados (el único rojo, `test_single_door`, señalaba la
    lectura del `RECORD` en `lock._edited`: dos sitios permitidos más, sin datos); `pytest -m
    realdata`, 66 de 66; `protocol --check` OK; `reliability --check`, 854 filas y 12.810 celdas;
    `layer2 --check`, 3.558 valores; `amputation --check`, 420 filas y 4.200 celdas.
    **Pasada 2, frente B (2026-10-23), sobre `be1a03b..eff9dda`: ningún alto ni medio.** Rehízo
    V2 sin el código de `reliability/` en los 10 (834 filas iguales a 6 decimales; en los 110
    grupos, V2 suma V0 y `V2_nofn` suma V1) y 13 de 14 mutaciones caen; la que sobrevive (n como
    jugadores con fila en la ventana) es equivalente en las siete métricas. Un bajo arreglado: el
    README decía "V2 grouped by how many are extrapolated".
    **Pasada 2, frente A (2026-10-23), sobre `5dbee58..be1a03b`: un alto y un medio.**
    - *Alto: la lectura única se eludía con git.* Una rama desde la congelación, un `merge -s
      ours` que descarta la lectura o un clon superficial volvían a leer: la puerta miraba solo
      la historia simplificada de `HEAD`. Ahora `--full-history` sigue los dos padres de un merge;
      en `frozen`, una lectura en cualquier ref (`--all`) la cierra; en `read` cuenta solo la
      historia de `HEAD`, para que un worktree en el commit de la lectura la reproduzca aunque
      `main` cambie `src` y `layer2.json` (el `--all` que proponía el revisor lo rompía: test
      nuevo); y un clon superficial se rechaza.
    - *Medio: un `ftbase` sombra con su propio dist-info (`pip install --target`) pasaba la
      regla 3*, porque se hasheaba contra su propio `RECORD`. Ahora cada paquete del cierre está
      instalado una sola vez, sus módulos se importan desde el site-packages del entorno
      (`sysconfig`) y se hashea el `RECORD` de todos, no solo el de la base: 0,8 s en total (los
      más de 2 min medidos antes eran carga de la máquina, no el hash).
    - *Bajo, aceptado:* un rebase de la congelación después de la lectura cierra la
      reproducción ("does not name its freeze"); y `reset --hard` más force-push o `git replace`
      reescriben la historia, fuera del alcance de una puerta local. Mitigación en J4: la
      congelación se empuja antes de leer, y el commit de la lectura justo después.
    **Mutaciones: 23 en A tras la pasada 2 (16 de la pasada 1 vigentes y 7 nuevas,
    `mutate23c_a2.py`; log `mutate23c_p2.log`), todas caen, cada una en su test**, incluida la que
    mete `--all` en `read` (cae el test del worktree). Commit `706a3be`.
    **Pasada 3, la última (2026-10-23), sobre `6548f03..706a3be`, en un clon (las mutaciones
    corrían en el árbol): un alto, dos medios, un bajo.**
    - *Alto: en `read`, una lectura a mano en una rama desde la congelación pasaba por
      reproducción* (en `read` solo contaba la historia de `HEAD`). Ahora una lectura es un commit
      con `READ_MESSAGE` que deja `layer2.json` en `read`, buscado en todas las refs y por los dos
      padres de un merge; en `frozen` no hay ninguna, en `read` hay una y es el último cambio de
      `HEAD`. Una edición posterior en otra rama no es una lectura: el worktree en la lectura sigue
      reproduciendo.
    - *Medio, regresión de la pasada 2: `--full-history` en la historia de `HEAD`* tomaba un merge
      posterior a la congelación por la congelación (un split cambiado en una rama anterior,
      juntado después, se leía). La historia de `HEAD` vuelve a ser la simplificada; solo la
      búsqueda de lecturas sigue todos los padres.
    - *Medio: las lecturas que el clon no ha traído no se ven* (un clon anterior a la lectura sin
      `fetch`, o de una sola rama). **Decisión de Javier (2026-10-23): se acepta por escrito.** J4
      se lanza solo desde su checkout, con `git fetch` justo antes, y la lectura se empuja en el
      acto; nadie más tiene clones del repo.
    - *Bajo: con `--all`, una rama de trabajo con `layer2.json` roto, borrado o en `read` a mano
      bloqueaba la primera lectura.* Ahora solo cuenta una lectura de verdad, y un `layer2.json`
      ilegible en otra ref es un stage nulo.
    - *Sospechoso arreglado: en Fedora (`lib64 -> lib`) cada paquete se ve dos veces* y la regla 3
      rechazaría el entorno de un juez; un sitio visto dos veces es una copia.
    - Para la 23d: el test contra `HEAD` necesita la historia entera en CI (`fetch-depth: 0`).
    **Mutaciones finales de la puerta: 26, cada una contra su test con nombre, todas caen**
    (`mutate23c_final.py` y su log en el scratchpad de la sesión; las 16 de la pasada 1 que
    siguen vigentes, las 7 de la 2 y 3 nuevas). Commit `a3bc9a4`. **Cierre de la 23c:** tres
    pasadas, como decidió Javier; los altos de las tres arreglados, los medios arreglados salvo
    el aceptado por escrito, y en la capa 2 nada abierto. Los arreglos de la tercera no tienen
    una cuarta pasada: los cubren sus tests, las 26 mutaciones y el test de la 23d sobre la
    historia real.
  - [x] 23d. `sonnet` Congelación de `layer2.json` en un commit propio: `stage: "frozen"`,
    `code_tree_sha`. Aceptación: desde ese commit hasta la lectura, `git diff <congelación> --
    src pyproject.toml uv.lock .python-version protocol/` vacío; test contra `HEAD` de que el
    reservado sigue cerrado con un cambio de código posterior. Antes, **[Javier]** confirma que
    `reads` incluye `layer2` (el comando de la 12, que la figura 1 necesita en los 20): va más
    allá de "25 + 26" tal como lo eligió; si no, se quita, y con él su `--check`. Pendiente desde
    23b; mejor antes de escribir ese `--check`. **Resuelto (2026-10-22): `layer2` se queda.**
    Javier delegó la decisión; la lectura es irreversible y sin `layer2` la figura 1 quedaría
    para siempre en los 10 de calibración, y es capa 2 pura (nada de la capa 3). Consecuencia:
    `ac2fb layer2 --check` se escribe antes de la 23c, con la 26.
    Hecho (2026-10-23). **Congelación `38cbd60`**, `code_tree_sha`
    `899a013cee5b8dca8ab66bcdacf1e8a8543a250e58ef05769d137b4a910b8695` (el mismo con `git ls-tree
    HEAD -- .python-version pyproject.toml src uv.lock | sha256sum`). Dos tests la sostienen hasta
    la lectura: `layer2.json` commiteado nombra el código de `HEAD`, y un clon completo del repo
    real admite la lectura (congelación `38cbd60`, ninguna lectura en ninguna ref) y la cierra con
    un commit más en `src`. CI con `fetch-depth: 0` (la puerta lee la historia). En el repo real:
    `ac2fb status`, reservado cerrado (`frozen` no abre fuera de la lectura); la puerta de la
    lectura, abierta; el lock, 0 diferencias en las reglas 1 a 4. Gate local en verde (`pytest
    -q`, 1.474 con 66 deseleccionados; `realdata`, 66 de 66; los cuatro `--check` como en la 23c);
    CI en verde (run 40021739416). Desde aquí, todo cambio de `src`, `pyproject.toml`, `uv.lock`,
    `.python-version` o `protocol/` antes de la lectura obliga a congelar otra vez (y a CP2).
- [x] CP2. **[Javier]** Aprueba la congelación de `layer2.json` y queda avisado de que la lectura
  del reservado es irreversible. La rama B ya está decidida (2026-10-19) y D5 registrado (23a).
  **Aprobado por Javier (2026-10-23)** sobre la congelación `38cbd60`, avisado de que la lectura
  es irreversible; en la misma respuesta **autoriza por escrito que Claude lance J4** ahora.

## Fase 3: reservado y capa 2 completa (lun 16 nov a dom 29 nov)

- [x] J4. **[Javier]** Lectura única del reservado, solo capa 2: confirma justo antes y lanza
  `ac2fb heldout read` (o lo autoriza por escrito a quien lo lance). Paso irreversible. La
  congelación ya empujada a `origin` antes de leer, y el commit de la lectura empujado justo
  después (un rebase posterior de cualquiera de los dos cierra la reproducción; 23c, pasada 2).
  **Hecho (2026-10-23, 21:18 UTC), lanzada por Claude con la autorización escrita de Javier
  (CP2).** Antes: `git fetch`, `HEAD` igual a `origin/main` (`85c69f5`), la congelación `38cbd60`
  empujada, sin otras ramas ni worktrees, árbol limpio. Commit de la lectura **`4cb9351`**,
  hecho antes de calcular nada y empujado en el acto; su registro: `frozen_commit` `38cbd60`,
  los 10 ids de la decisión 1 y la fecha. 2 min 33 s. Artefactos en `reports/heldout/`
  (`layer2.json`, `reliability.csv`, `amputation.csv`, LF), commit `8c3ef91`. Reproducida con el
  mismo código en un directorio aparte: idéntica byte a byte en los tres, sin commit nuevo.
  CI en rojo en `4cb9351` (run 40025760773) y en `8c3ef91` (run 40026089602): dos tests de la 23d
  seguían exigiendo `frozen`; `2c4e4e7` los arregló (revisión V, pasada 1).
- [x] 24. `opus` Registro de la lectura de la capa 2: cifras por partido de los 20 en
  `reliability.csv` y `amputation.csv`, con el commit de la lectura (`layer2.json` en `read`). Se
  publica como cae. Sin D6: la capa 3 no se lee en el reservado (rama B).
  Hecho (2026-10-23). Cifras por partido de los 10 del reservado, impresas por
  `scripts/layer2_summary.py reports/heldout` (el mismo script sobre `reports` da las de
  calibración); las de cada celda están en los CSV. **Se publican como caen; veredicto
  reservado** a las figuras (27) y al README (33).
  V1 menos V0 (estrato `all`, media de V1 menos media de V0):

  | match | press | rival | line | react | width | length | area |
  |---|---|---|---|---|---|---|---|
  | 1899585 | -0.015 | -0.123 | +12.375 | +0.993 | -1.063 | -37.304 | -1554.062 |
  | 1927964 | -0.004 | -0.072 | +8.847 | +0.979 | -1.140 | -18.055 | -811.148 |
  | 1953632 | -0.020 | +0.006 | +7.280 | +0.789 | +0.660 | -23.749 | -1002.797 |
  | 1986691 | -0.007 | -0.050 | +12.035 | +0.846 | -0.895 | -23.337 | -1014.382 |
  | 2006229 | -0.017 | -0.009 | +7.193 | +0.810 | -0.077 | -17.073 | -724.359 |
  | 2006363 | -0.010 | -0.054 | +9.556 | +1.751 | -1.874 | -26.307 | -1206.273 |
  | 2007721 | -0.013 | -0.087 | +8.031 | +0.932 | +0.005 | -27.945 | -1252.244 |
  | 2013725 | -0.034 | -0.006 | +9.987 | +1.339 | -0.308 | -23.904 | -913.213 |
  | 2016236 | -0.018 | -0.049 | +13.200 | +1.908 | -0.519 | -27.141 | -1254.792 |
  | 2017461 | -0.029 | -0.157 | +9.583 | +1.718 | -1.286 | -23.624 | -975.189 |

  Error absoluto medio de la amputación (banda `all`):

  | match | press | rival | line | react | width | length | area |
  |---|---|---|---|---|---|---|---|
  | 1899585 | 0.039 | 0.357 | 0.945 | 0.425 | 2.435 | 2.121 | 143.492 |
  | 1927964 | 0.027 | 0.274 | 1.173 | 0.398 | 2.455 | 1.681 | 178.964 |
  | 1953632 | 0.036 | 0.426 | 1.037 | 0.455 | 2.285 | 1.091 | 94.898 |
  | 1986691 | 0.037 | 0.291 | 0.899 | 0.364 | 2.131 | 1.735 | 118.026 |
  | 2006229 | 0.034 | 0.413 | 0.979 | 0.407 | 2.075 | 1.477 | 164.726 |
  | 2006363 | 0.033 | 0.287 | 0.943 | 0.343 | 2.360 | 5.952 | 185.084 |
  | 2007721 | 0.038 | 0.333 | 0.964 | 0.438 | 2.284 | 0.079 | 28.590 |
  | 2013725 | 0.042 | 0.512 | 1.203 | 0.486 | 2.894 | 4.580 | 179.263 |
  | 2016236 | 0.035 | 0.268 | 1.017 | 0.406 | 2.901 | 1.646 | 117.149 |
  | 2017461 | 0.046 | 0.342 | 1.091 | 0.374 | 2.796 | 2.798 | 106.562 |

  **Contra calibración (mínimo, mediana y máximo de los 10; mismo script).** V1 - V0: altura
  de línea +7,19 / +9,57 / +13,20 m (calibración +8,654 / +11,091 / +13,885), positiva en 10 de 10
  en las dos mitades; reacción +0,79 / +0,99 / +1,91 m (+0,625 / +1,361 / +1,457), 10 de 10, y V1
  por encima de V0 en los tres estratos del balón entrante en 10 de 10 (como en calibración);
  longitud del bloque −37,3 / −23,8 / −17,1 m (−34,5 / −28,7 / −21,8) y área −1.554 / −1.009 /
  −724 m² (−1.364 / −1.189 / −807), negativas en 10 de 10; presión −0,034 / −0,016 / −0,004
  (−0,041 / −0,014 / −0,006), negativa en 10 de 10; rival más cercano negativo en 9 de 10 en las
  dos; anchura mixta (positiva en 2 de 10; en calibración, 3). Fracción extrapolada de
  jugador-frame, mediana: línea 0,469 (0,500), longitud 0,580 (0,581), presión 0,040 (0,030).
  Amputación, error absoluto medio de `all`: presión 0,027 / 0,037 / 0,046 (0,019 / 0,033 /
  0,049); rival 0,27 / 0,34 / 0,51 m (0,20 / 0,32 / 0,50); línea 0,90 / 1,00 / 1,20 m (0,79 /
  0,89 / 1,39); reacción 0,34 / 0,41 / 0,49 m (0,34 / 0,40 / 0,46); anchura 2,075 / 2,398 / 2,901 m
  (1,87 / 2,34 / 3,32); longitud 0,08 / 1,71 / 5,95 m (1,17 / 2,72 / 5,06); área 29 / 131 / 185
  m² (43 / 133 / 246). Error estrictamente creciente de banda en banda (bandas con unidades, de
  `le_1s` a `gt_20s`), partidos: presión 8, rival 10, línea 10, reacción 10, anchura 10,
  longitud 8, área 7 (calibración: 5, 9, 10, 10, 9, 7, 9).
  **Nota sobre la 26:** sus recuentos de calibración (10 en línea, reacción y área; 9 en rival y
  anchura; 8 en longitud; 5 en presión) venían de `summary26.log`, en el scratchpad de otra
  sesión; ninguna definición probada aquí los reproduce desde `amputation.csv` (estricta o no,
  con o sin `le_1s`, error medio o p90, mínimo de unidades 1, 2, 5 o 10). Valen los de este
  script, que está en el repo. Sin D6.
- [x] 25. `sonnet` Capa 2 (rama B: código y `--check` antes de 23c, corrido en calibración; los
  20 partidos solo en la lectura de J4): mapa de fiabilidad por métrica y
  partido (presión local, distancia al rival más cercano, altura de línea, anchura, longitud, área
  del bloque, y la reacción de la línea al balón entrante) en V0, V1 y V2, con la fracción
  extrapolada y su `gap_len`, en `reports/reliability.csv`. Aceptación: las cifras de calibración
  coinciden con las de la 12; mutación anotada. Antes de abrir el reservado (revisión 22,
  pasadas 2, 4 y 5): test de `pressure.make_metric` y de toda métrica nueva que lea
  `attack_sign`, con portadores de los dos equipos en los dos periodos y moviendo también la
  tabla larga; y decidida la tolerancia de `index >= PRESSED_INDEX` y de `weights > 0`.
  Hecho (2026-10-22). **Dónde vive, contra lo escrito arriba:** el código está en `reliability/` y
  no reutiliza las funciones de `defence/`. La lectura de J4 no puede ejecutar ninguna función de
  `defence/` (la 23b lo mide con `sys.setprofile` en
  `test_the_command_runs_the_layer2_commands_and_no_layer3_code`) y la 25 va en `LAYER2_READS`.
  Las definiciones se reescriben en `reliability/metrics.py` y se igualan a las originales: en
  mundos aleatorios (5 semillas, `test_reliability_metrics.py`) y en los 10 partidos reales
  (`realdata`, la `Sensitivity` entera igual, no aproximada). Cuesta unas 60 líneas repetidas
  (pesos del índice, línea, extremos del bloque); mover `pressure`, `line` y `block` a
  `reliability/` tocaría código de la capa 3 ya auditado. Confirmado por Javier (2026-10-22): la
  copia con igualdad comprobada.
  **Construido** (commit `de8919f`, empujado; CI en verde, run 39775012607, 1 min 50 s):
  `reliability/metrics.py` (siete métricas), `reliability/table.py` (filas, CSV, `check`),
  `match.load_with_long`, el comando `ac2fb reliability [--match ID] [--reports-dir D]
  [--check]` y `LAYER2_READS["reliability"]`; `protocol/layer2.json` lista `layer2` y
  `reliability` en `reads` (el `stage` sigue en `design`; `protocol.json` no se toca; `layer2`
  sigue donde estaba). `reports/reliability.csv`: 465 filas, 14 columnas, 10 partidos de
  calibración, LF; `ac2fb reliability` tarda 2 min 53 s en los 10. Las unidades salen de los
  eventos del partido: una posesión es un `player_possession` con equipo y jugador (t = su
  `frame_start`; 755 a 1.050 por partido, 9.153 en total, 25 sin medir) y una fase un
  `phases_of_play` con equipo (374 a 473 por partido, 4.250 en total, 169 sin medir). Columnas:
  `match_id, metric, variant, n, mean` (V0, V1 y `V2_k` con k jugadores detectados en toda la
  ventana) y, repetidas en cada fila del par, `n_units, n_skipped, player_frames,
  extrapolated_fraction, absent_fraction, gap_len_n, gap_len_median, gap_len_p90, gap_len_max`.
  **Métricas y definiciones mínimas, confirmadas por Javier (2026-10-22) salvo `line_reaction_m`,
  que gana el estrato del balón en la 26:** `pressure_index`
  (el índice de S1 en t; jugadores: los rivales con peso mayor que `NEAR_WEIGHT`);
  `nearest_rival_m` (distancia del portador al rival más cercano en t; jugador: ese rival; el
  portador no cuenta, como en S1); `line_height_m` (profundidad media de los 4 rivales de campo
  más profundos en t, la de S2, portero fuera por el proxy); `line_reaction_m` (altura de la línea
  elegida en t menos su altura en t - 13, positiva si se retira; ventana [t - 13, t]; sin estrato
  del balón: es el `P` de S2 sobre todas las posesiones); `block_width_m`, `block_length_m`
  (definición `with_gk_extremes_listed`, la de `power.C3_DEFINITION`, que S3 eligió) y
  `block_area_m2` (**rectángulo envolvente, ancho por largo, no casco convexo**; jugadores: los
  cuatro que fijan los extremos). Toda V1 es una selección declarada (unidades con sus jugadores
  detectados en toda la ventana). Sin cubrir: la visibilidad del balón (la causa común) no está en
  el CSV; sigue en `probe_s2.json` (`ball`).
  **Tolerancias (confirmadas por Javier, 2026-10-22), medidas en las 8.142 recepciones puntuadas de calibración
  (`measure_cuts.log`):** el mínimo de |índice - 0,5| es 2,4e-4; el de |d - 10| m, 1,3e-4, y el de
  |d - 5| m, 5,7e-4; de 14.669 pesos positivos, el menor es 1,1e-9, ninguno por debajo de 1e-9,
  15 por debajo de 1e-6, 384 por debajo de 1e-3. El ruido de coma flotante es de otro orden: un
  rival exactamente detrás del portador, sobre la recta al gol, pesa 1,15e-17 en vez de 0 (caso del
  test). Decidido: `weights > NEAR_WEIGHT` con `NEAR_WEIGHT = 1e-12` (tres órdenes por encima del
  ruido y tres por debajo del peso real menor), en `pressure.score_receptions`,
  `pressure.make_metric` y la copia de `metrics`; cambia 0 decisiones en calibración (los informes
  de S1, diseño, calibración y potencia salen idénticos byte a byte en `realdata`).
  `index >= PRESSED_INDEX` queda sin tolerancia: solo lo lee `design.py` (capa 3, muerta) y la
  capa 2 no lo usa (la métrica es el índice, sin corte); si algún día se leyera, la holgura sería
  `TIE` (1e-9) y la distancia mínima medida es 2,4e-4.
  **Cifras de calibración** (`summary25.log`; mínimo - mediana - máximo de los 10 partidos): V1
  sobre V0 y fracción extrapolada: presión 0,904-0,961-0,977 y 0,016-0,030-0,070; rival más
  cercano 0,943-0,972-0,980 y 0,020-0,028-0,057; altura de línea 0,255-0,326-0,561 y
  0,303-0,500-0,556; reacción 0,183-0,257-0,506 y 0,307-0,502-0,555; anchura 0,329-0,399-0,589 y
  0,271-0,408-0,455; longitud 0,039-0,053-0,095 y 0,524-0,581-0,633; área 0,035-0,046-0,086 y
  0,404-0,497-0,542. `gap_len` máximo: 446 (presión) a 3.109 frames (longitud y área);
  `absent_fraction` 0 en todas las filas. La longitud del bloque casi no se ve entera: sus
  extremos los fijan jugadores que la cámara pierde.
  **Coinciden con la 12 donde se solapan** (`test_realdata_reliability.py`, 10 de 10 partidos):
  los estratos V2 de la altura de línea son `line.detected_count` de `layer2.json`; sus unidades,
  `line_at_t` de `probe_s2.json`; las unidades del bloque, `block.phases`; V0 menos V1 de la
  presión, las recepciones con un rival extrapolado a menos de 10 m de `reception`; anchura y
  longitud, el `fixers` de `probe_s3.json` (n, medias, fracción extrapolada, `gap_len`) a seis
  decimales. El `check` del CSV real recalcula los 10 partidos (110 s en el test): 465 filas,
  6.510 celdas, sin diferencias. La presión de S1 usa las 8.142 recepciones etiquetadas y esta
  tabla las 9.153 posesiones: no se solapan en cifras, y sí en definición (`pressure.make_metric`
  igual).
  **`--check`:** recalcula y compara celda a celda con el CSV, dice cuánto verificó (`verified: N
  rows, M cells, K matches`) y sale con 1 y la celda (partido, métrica, variante, columna) si
  difiere; no escribe. La lectura del CSV la hace `cli._committed_table` (sitio nuevo en
  `ALLOWED_FILE_SITES` de `test_single_door.py`, una sola llamada, un solo receptor: leer un
  informe, no un dato); `table.check` recibe los bytes y no abre nada. **Hallazgo:**
  `effect_helpers.mixed` reutiliza los ids de jugador en los dos equipos, y la tabla larga da a
  cada jugador el equipo de su primera fila; el test renumera (`+ 1000 k` por cuadrante) para
  poder mover también la tabla larga.
  **Revisión 22:** `pressure.make_metric` y las tres métricas nuevas que leen `attack_sign`
  (índice, altura y reacción) pasan por el partido mixto con los dos equipos en los dos periodos
  (`other` 2 y 7) y la tabla larga rehecha desde los arrays movidos. **Mutaciones (38, todas
  caen; `mutate25.py` y sus logs `mutate25_pass1.log` y `mutate25_final.log` en
  `scratchpad/t25/`; copia del árbol, el árbol real no se toca):** para `make_metric`, el signo
  del periodo 1 siempre, sin signo y el signo del equipo 1 siempre (las dos de la 22 y una más), y
  las mismas tres en cada lector nuevo (9 en total con las de `make_metric`); `sensitivity` que
  ignora `is_detected` (V1 = V0); tres métricas que no declaran sus jugadores; `weights > 0` en
  `score_receptions`, `make_metric` y `pressure_index`; una tolerancia de 1e-9; línea con el
  portero, sin signo, con los cuatro menos profundos, reacción sin exigir la línea en t - 13 y sin
  signo; bloque de 4, por percentiles, área como suma, extremos con otro desempate; rival más
  cercano el más lejano; peso sin la mitad; `check` sin comparar celdas, con solo 4 columnas, solo
  la primera fila, sin ver una fila que falta, sin ver un CR y sin contar celdas; escritor con CRLF
  y con NaN; comando que no imprime cuánto verificó y que sale 0 con el `check` fallido. En la
  primera pasada sobrevivieron 2: `weights > 0` en `score_receptions` (sin test; añadido
  `test_the_scored_receptions_cut_the_near_rivals_the_same_way`) y el escritor con NaN
  (equivalente al original, que escribía `nan`; ahora una celda vacía, con test). Gate local en
  verde (`sync --locked`, ruff, format, `mypy src`, `pytest -q`: 1.314 pasan, eran 1.193; 41
  deseleccionados; `pytest -m realdata`: 41 de 41, eran 26; `ac2fb protocol --check` OK). Nadie
  leyó el reservado: los tests de la puerta (`test_public_routes`, `test_data_gate`,
  `test_single_door`, `test_heldout`) no se debilitan (los únicos cambios: entradas nuevas en las
  tablas de rutas, la lista de `reads` del helper y un sitio de lectura de un informe). Pendiente
  de la 25: nada; faltan la 26, 23c y 23d.
- [x] 26. `sonnet` (rama B: como la 25, antes de 23c) Referencia por amputación
  (`reliability/amputate.py`), con su comando y su `--check`: en tramos con los
  jugadores de la métrica detectados se enmascaran huecos muestreados de la distribución real de
  `gap_len` y de la detección por distancia al balón, se rellenan por interpolación lineal entre
  extremos (lo que m11 dice que hace el proveedor; declarado como cota, no como su modelo) y se
  mide el error de cada métrica por banda de hueco y partido en `reports/amputation.csv`.
  Aceptación: hueco 0 da error 0; sintético con trayectoria conocida recupera el error analítico;
  mutación: rellenar con la última posición cambia el error y un test lo detecta. Sesgo
  declarado: los tramos enteramente vistos están cerca del balón.
  Entran también en la 26, antes de la 23c: (a) **decisión de Javier (2026-10-22):**
  `line_reaction_m` se parte por el estrato del movimiento previo del balón (el de S2, copiado en
  `reliability/` como el resto) con una columna `ball_stratum` en `reliability.csv`, y V0 frente a
  V1 se compara dentro de cada estrato (m10: V1 se queda con lo que está cerca del balón); se
  rehacen el CSV, su `--check` y las mutaciones afectadas; (b) `ac2fb layer2 --check` (23d:
  `layer2` se queda en `reads`), que `full-build.yml` corre en cuanto exista.
  **Decisiones de Javier (2026-10-22), antes de escribir código:** (1) el estrato de (a) es la
  dirección del balón en `[t - 13, t]` con el corte de 2 m de S2 (`backward`, `forward`,
  `lateral`, `undefined`), no las 18 celdas; las filas de las otras métricas, y las de la
  reacción sin partir, llevan `ball_stratum = all`. (2) Amputación con frames reales: unidades V1
  de cada métrica; cada jugador de la métrica se oculta con la probabilidad de no detección de su
  banda de distancia al balón en `t` (la de `layer2.json`); si cae, copia de un frame extrapolado
  real de esa banda (mismo partido, con detección a los dos lados en el periodo) los frames hasta
  la detección anterior y la siguiente, y los pone alrededor de `t`; los extremos se mueven a la
  detección más cercana del jugador; relleno lineal entre ellos. Error = valor rellenado menos
  valor visto, por banda del hueco efectivo más largo (`runs.BANDS`), más `none` (nadie oculto) y
  `all`. Semilla fija, una corriente por partido y métrica.
  Hecho (2026-10-22). **Construido:** `reliability/amputate.py` con el comando `ac2fb amputation
  [--match ID] [--reports-dir D] [--check]` y `LAYER2_READS["amputation"]`; `protocol/layer2.json`
  lista `layer2`, `reliability` y `amputation` en `reads` (sigue en `design`). Apoyos:
  `sensitivity.window_frames` (extraído de `_one_match` sin cambiar nada: la amputación construye
  las ventanas y decide V1 igual que la tabla de la 25), `metrics.incoming_direction` y
  `reaction_strata` (la dirección de `pressure.incoming_ball`, copiada como el resto),
  `table.check_csv` y `render_csv` (un solo check de CSV para las dos tablas), `report.check` y
  `ac2fb layer2 --check` (cada valor de `layer2.json` por su ruta, después los bytes tal como los
  escribe el código; no escribe nada, ni el Parquet largo) y `cli._committed` en lugar de
  `_committed_table` (un solo sitio de lectura de informes para los tres checks, en
  `ALLOWED_FILE_SITES`). `full-build.yml` corre `layer2 --check` y `amputation --check` después
  del de `reliability`. README: el `PENDING(task 26)` apunta ahora a `reports/amputation.csv`, con
  el resumen PENDING(task 27). Del bloque completo del README no se ha tocado nada: el workflow
  verifica `amputation.csv` con su `--check`.
  **`reliability.csv`:** columna `ball_stratum` detrás de `metric` (clave: partido, métrica,
  estrato y variante); 695 filas, eran 465. Las 465 de `all` son iguales celda a celda a las de
  `HEAD` (comprobado contra `git show`); hay 230 nuevas de `line_reaction_m` por dirección. El
  estrato `undefined` está vacío en los 10 partidos. Cifras (`summary26.log`; mínimo, mediana y
  máximo de los 10 partidos), con n y la media de V0 frente a V1: hacia atrás n 296-394-449,
  −1,518/−1,327/−0,932 frente a n 55-86,5-194, −0,951/−0,625/−0,021; hacia delante 284-356-417,
  +0,870/+1,198/+1,437 frente a 73-109,5-218, +2,106/+2,669/+3,107; lateral 134-154-208,
  −0,356/−0,149/+0,286 frente a 30-47-86, +0,116/+0,604/+1,066. **V1 queda por encima de V0 en
  los tres estratos y en los 10 de 10 partidos:** estratificar por el balón no borra la diferencia
  V0-V1 de la reacción (sin estratos, mediana −0,095 frente a +1,064).
  **`amputation.csv`:** 420 filas (10 partidos, 7 métricas y 6 bandas: `none`, `le_1s`, `1_5s`,
  `5_20s`, `gt_20s` y `all`), 10 columnas (`n`, error medio, error absoluto medio, su p90 y su
  máximo, `n_units` y `n_skipped`), LF. Tiempos en local: `ac2fb amputation` 52 s en los 10,
  `ac2fb reliability` 71 s y `ac2fb layer2 --check` 16 s (3.558 valores verificados). Las
  unidades son las V1 de `reliability.csv` (test `realdata`). Se saltan de 0 a 11 por partido y
  métrica. La banda `le_1s` casi no tiene unidades (0 a 6): un frame extrapolado rara vez vive en
  un hueco de 1 s o menos, y el muestreo pondera por frame. Error absoluto medio de `all`
  (mínimo, mediana y máximo): presión 0,019-0,033-0,050; rival más cercano 0,20-0,32-0,50 m;
  altura de línea 0,79-0,89-1,39 m; reacción 0,34-0,40-0,46 m; anchura 1,87-2,34-3,32 m;
  longitud 1,17-2,72-5,06 m (14 a 42 unidades); área 43-133-246 m². En huecos de más de 20 s:
  presión 0,15-0,18-0,21; rival 2,12-2,73-3,75 m, con error medio siempre positivo (+1,22 a
  +3,19: el rival rellenado queda más lejos); línea 1,31-1,46-1,94 m; reacción 0,54-0,62-0,67 m;
  anchura 3,80-4,57-5,40 m. En la mediana entre partidos, el error crece con la banda en las
  siete métricas; partido a partido crece de banda en banda en 10 de 10 (línea, reacción, área),
  9 de 10 (rival, anchura), 8 de 10 (longitud) y 5 de 10 (presión, donde 5-20 s y más de 20 s
  quedan parecidos).
  **Tests:** `test_amputate.py` (33: hueco nulo, recta exacta, error analítico `c a b` de una
  parábola en tres huecos, extremos que se desplazan y no cruzan periodos, saltos sin balón o
  sin detección, banda del hueco más largo, ocultación igual a `detection_by_ball_distance`,
  unidades V1 en 5 mundos, semillas fijas e independientes, tabla y check), `test_layer2_check.py`
  (5), dirección contra el original (5 semillas y un caso plantado en el corte con ruido de coma
  flotante), estratos en la tabla plantada y, en `realdata`, `test_realdata_amputation.py` (14:
  el CSV es el del código, una mutación de 1e-6 la ve, unidades = V1, bandas que reparten, la
  ocultación igual a `layer2.json` en los 10) y en `test_realdata_reliability.py` (estratos que
  reparten las unidades; la dirección igual a la de S2, posesión a posesión, en los 10).
  **Mutaciones (28, todas caen; `t26/mutate26.py` y sus logs `mutate26.log` y
  `mutate26_tolerance.log` en el scratchpad de la sesión; copia del árbol, el real no se toca):**
  relleno con la última posición; huecos que siguen marcados como detectados; error con el signo
  cambiado; extremos que no se mueven o que cruzan periodos; probabilidad igual a la fracción
  detectada; bolsa con huecos abiertos o con todos los frames muestreados; ocultar con el sorteo
  invertido; banda del hueco más corto; amputar todas las unidades V0; no saltar sin balón; una
  corriente para todos los partidos o para todas las métricas; dirección sin signo, sin
  tolerancia o cruzando el descanso; cada estrato con todas las unidades; `check_csv` con una
  columna menos o sin ver una fila que falta; escritor con CRLF; comando de amputación que sale
  con 0 aunque el check falle; check de `layer2` solo con números, sin ver un valor que falta, un
  CR u otro formato; `layer2 --check` que escribe el Parquet o que no dice cuánto verificó. En la
  primera pasada sobrevivió una, la dirección sin tolerancia: en la rejilla de 10 cm del test
  aleatorio ninguna diferencia pasaba de 2 m por ruido. Se añadió el caso plantado (−17,6 a
  −15,6 m), y ahí cae.
  Gate local en verde: `sync --locked`, ruff, format, `mypy src`; `pytest -q` pasa 1.416 (eran
  1.314) con 66 deseleccionados; `pytest -m realdata`, 66 de 66 (eran 41); `ac2fb protocol
  --check` OK. Commit `925b902`, empujado. CI en verde (run 39798271669, 2 min 18 s). Full build
  en verde con la caché caliente (https://github.com/javiersr1996/ac2-football/actions/runs/39798302910;
  `downloaded=0`; rápido en 10 s, completo en 164 s). En Linux, `reliability` verificó 695 filas y
  10.425 celdas; `layer2`, 3.558 valores; `amputation`, 420 filas y 4.200 celdas. Los tres salen
  idénticos a los calculados en Windows. Nadie leyó el reservado: la puerta y sus tests no se
  tocan, salvo entradas nuevas en las tablas de rutas, `READS` del helper y el sitio de lectura
  renombrado. Pendiente de la 26: nada. Siguen la 23c (revisión de 23b, 25 y 26, con un máximo de
  3 pasadas) y la 23d.

## Fase 4: empaquetado (lun 30 nov a dom 6 dic)

- [x] 27. `sonnet` Las dos figuras (máximo de las bases), generadas por `ac2fb figures` desde
  `reports/`: figura 1, detección por distancia al balón, fracción del modelo por banda de hueco y
  sensibilidad por métrica (V0 frente a V1, error por amputación), por partido; figura 2, el efecto
  de la capa 3 por partido en V0, V1 y V2, calibración y reservado (o la muerte, rama B).
  Aceptación: test que regenera y compara; cada número de una etiqueta sale de un artefacto.
  Hecho (2026-10-24), commit `16446a4` (código, tests y figuras) y el de este registro. **Qué
  hay:** `src/ac2fb/figures.py` (puro: recibe los bytes de `reports/` y devuelve cuatro ficheros,
  no abre nada, la puerta única sigue única), `ac2fb figures [--reports-dir] [--out-dir] [--check]`,
  `tests/test_figures.py` (30 hoy), matplotlib 3.11.2 con `uv add` (lock al día; `test_lock` espera
  ahora `matplotlib` entre lo que necesita el paquete) y dos rutas nuevas en `test_public_routes`.
  Salida en `reports/figures/`: `fig1_layer2.svg|json`, `fig2_layer3.svg|json`. Lee solo
  `layer2.json`, `reliability.csv`, `amputation.csv`, `calibration.json` y los tres de
  `reports/heldout/`; no toca `data/`, `protocol/*.json` ni el reservado.
  **Figura 1** (20 partidos; calibración en azul con círculo, reservado en naranja con cuadrado;
  línea fina por partido, gruesa la mediana de la mitad): (a) fracción de jugador-frames
  detectados por distancia al balón; (b) fracción de los frames rellenados por banda de hueco
  (`reacquisition.by_band.*.frame_share`); (c) por métrica y partido, V1 menos V0 (estrato `all`);
  (d) error absoluto medio de la amputación (banda `all`). Las siete métricas van en su unidad,
  sin normalizar (la reacción cruza el cero y una razón explotaría).
  **Figura 2** (rama B, solo calibración, 10 partidos): (a) efecto E_m por partido en V0, V1 y V2
  sin extrapolados, con el T conjunto y el suelo de D3 en gris; (b) la diferencia previa a la
  recepción por partido; debajo, la muerte dicha con cifras de `calibration.json` (D3, V0 pasó su
  barra, V2 con extrapolados sin unidades útiles) y que no hay lectura del reservado para la capa 3.
  **Determinismo:** `svg.fonttype none`, `svg.hashsalt` fijo, metadatos sin fecha ni versión, ejes
  en posiciones fijas (sin `tight_layout` ni leyendas automáticas), LF. Cada figura lleva un
  sidecar JSON con cada valor trazado y cada número de etiqueta, su fórmula y las celdas de
  origen, más el sha256 de los informes leídos. Comprobado en Linux (contenedor
  `ghcr.io/astral-sh/uv:python3.13-bookworm`, `uv sync --locked`, `figures --check` y `cmp`): los
  cuatro ficheros idénticos a los de Windows. En la primera pasada el SVG de la figura 1 difería:
  el marcador de rombo escribe `-0` en Linux y `0` en Windows; se cambió por un cuadrado y
  `test_no_signed_zero_in_the_svg...` lo vigila. CI de Ubuntu: en verde, run 40085566961 del push `18c9313`
  (https://github.com/javiersr1996/ac2-football/actions/runs/40085566961).
  **`--check`:** redibuja y compara byte a byte; imprime `verified: 4 files, 594 plotted values
  and 7 labels, each from its artefact cell, 7 reports read`; sale 1 si algo difiere o falta, 2
  si falta un informe; no escribe.
  **Mutaciones.** En los tests, sobre copia de `reports` (cada una falla): un efecto de
  `calibration.json`; el error de amputación de un partido del reservado (mueve un solo valor
  trazado); fichero commiteado editado o ausente; número cambiado solo en el SVG; informe ausente
  (salida 2); resolutor con valor, referencia, marca de mediana, número de etiqueta, redondeo y
  número tecleado cambiados; cobertura con un partido, una variante o un punto quitados; recorrido
  del SVG con un número tecleado y con una etiqueta quitada. Sobre el código, en copia del árbol
  redibujando las figuras con el código mutado (18; `mutate27.py` y `mutate27.log` en el
  scratchpad de la sesión, cabo para pasarlos a `scripts/mutations/` con los de la 28): caen 16
  (número de etiqueta desplazado, redondeo, etiqueta fuera del sidecar, 10 tecleado, columna
  equivocada en (b) y (d), mediana sustituida por la media, V1 leída de V0, reservado leído del
  fichero de calibración, sidecar en CRLF, `--check` que ignora el SVG, que sale 0, que escribe o
  que no dice cuánto verificó, un partido menos, sal del hash por el reloj); una no llega a dibujar
  (estrato `backward` en (c): `KeyError`); una sobrevive en Windows, el rombo, y solo la ve Linux.
  **Desviaciones:** "fracción del modelo por banda de hueco" se leyó como `frame_share` de los
  runs extrapolados; el reservado de `layer2.json` no trae `runs` ni `steps`, solo `reacquisition`;
  el enlace SVG a sidecar es por construcción (el SVG se dibuja de las series del sidecar) y lo
  guarda el `--check` byte a byte; se arrancó Docker Desktop para la prueba en Linux. Gate local
  en verde: ruff, format, `mypy src`, `pytest -q` 1.502 pasan (66 deseleccionados).
- [x] 28. `sonnet` `--check` en cada comando que escribe un artefacto (recalcula y compara; con
  fixtures dice cuánto verificó, `PARTIAL n/20`). Aceptación: mutar un valor de un JSON hace
  fallar su `--check`. Rama B: el de la 25 y la 26 ya existe (23); en `HEAD`, tras la lectura,
  verifica solo la calibración y lo dice (`PARTIAL 10/20`); el reservado, desde el commit de la
  lectura.
  Cabo suelto de la 23c (2026-10-23): los scripts de mutación que citan los registros
  (`mutate23c_final.py` y los de 23a, 23b, 25 y 26) viven en scratchpads de sesión; pasarlos
  a `scripts/mutations/` para que su registro tenga artefacto en el repo (lecciones).
  Hecho (2026-10-24), commits `68e9b78` (los `--check` y sus tests), `ef40bc4` (workflow y
  script de comparación del reservado) y `82d232c` (scripts de mutación); el de este registro.
  **Qué hay:** `--check` en `cadence`, `s1`, `s2`, `s3`, `power`, `design` y `calibration`
  (además de los de `layer2`, `reliability`, `amputation`, `protocol` y `figures`). Cada uno
  recalcula su informe por la puerta guardada, compara valor a valor con el fichero (nombra la
  ruta que difiere, el valor que falta o sobra, el CR y el formato) y no escribe. La comparación
  es una sola, `report.check_json` (la de `layer2` ahora la usa, mismos tests); cada módulo trae
  su `check`. Salida: `verified: N values, M matches`, los problemas, una línea `PARTIAL n/20` y
  `<comando>: OK|FAILED`; sale 1 si algo difiere o falta, 2 si pide un partido del reservado.
  `PARTIAL` sale en los diez (también en `layer2`, `reliability` y `amputation`): en `HEAD` el
  reservado no abre, así que se verifican 10 de 20 y la línea dice por qué (en los de capa 2: el
  reservado reproduce solo desde el commit de la lectura, en un worktree; en los de capa 3: no
  tiene mitad reservada, la capa murió antes de leer).
  **En datos reales (salida de cada uno, `HEAD` con los 10 de calibración):** `cadence` 493
  values; `s1` 1903 values; `s2` 5275 values; `s3` 2401 values; `design` 1801 values; `power` 3458
  values; `calibration` 7701 values; `layer2` 3558 values; `reliability` 854 rows, 12810 cells;
  `amputation` 420 rows, 4200 cells. Los diez, `10 matches`,
  `PARTIAL 10/20 matches: ...` y `OK`, sin discrepancia con los ficheros commiteados de
  `reports/` (ninguno que tocar). Nota: el primer lanzamiento dejó una cadena huérfana que
  escribía en los mismos logs; se mataron y se relanzó todo, de ahí los dos `exit 0` sueltos en
  `layer2.log` y `calibration.log`; los resultados son los de la segunda pasada.
  **Reservado (rama B):** el código de `HEAD` no puede abrirlo (la guarda lo cierra: el código
  cambió desde el congelado), ni debe haber ruta nueva. `full-build.yml` hace lo que pedía la
  30: un worktree en el commit de la lectura (se busca por su asunto y debe ser uno solo; hoy
  `4cb9351`), `uv sync --locked` allí, `ac2fb heldout read --reports-dir` (reproduce, no
  commitea) y `scripts/compare_heldout_reading.sh` compara byte a byte los tres ficheros con
  `reports/heldout/`. También añade al workflow los siete `--check` nuevos y `figures --check`,
  y `fetch-depth: 0` al checkout (la guarda lee toda la historia). **No probado de punta a punta
  en local**: no se corre `heldout read`; queda para el primer dispatch. El script de comparación
  sí se probó con 8 casos sobre copias de `reports/heldout/`: idéntico pasa; un número de
  `layer2.json`, una celda de `reliability.csv` y el salto de línea final cambiados, un fichero
  no reproducido, uno no commiteado, uno de más y nada que comparar fallan (salida 1).
  **Mutaciones.** En datos reales, sobre copia de `reports/` (`ac2fb <cmd> --check
  --reports-dir copia`), un número cambiado por JSON, los siete caen con salida 1 y nombran el
  valor: `cadence` `decision.cadence_frames` 1 a 2; `s1` `constants.goal_x`; `s2`
  `constants.frame_seconds`; `s3` `constants.max_median_diff_m`; `design` `constants.d3_ratio`;
  `power` `candidates.C1.outcomes.ball_advance.incoming_ball.rho_v0_pooled`; `calibration`
  `beside.V0_ball_detected.agreeing` 8 a 9. En los tests (`tests/test_report_checks.py`, 47 hoy):
  por cada uno de los siete, el primer número, el último y un texto cambiados, un valor de más,
  el fichero ausente, un partido del reservado (salida 2), que no escribe, y `power` contra un
  veredicto de sonda editado junto al fichero. Sobre el código, 25 (copia del árbol con su
  propio git; `scripts/mutations/mutate28.py` y `mutate28.log`; línea base 51 verdes, **las 25
  caen**, cada una en su test): comparación que no compara, que no ve un valor cambiado, de más
  o que falta, que acepta CR, otro formato o un fichero ausente; sin contar valores; salida 0
  al fallar; sin `OK/FAILED`, sin lista de problemas, sin `PARTIAL`; total de `PARTIAL` mal;
  `layer2` diciendo que no tiene reservado; `cadence` leyendo el fichero de `s1`; `s2`
  recalculando el informe de `s1`; `design` leyendo el de `calibration`; `power` con las sondas
  de `reports/` en vez de las del lado del fichero; `calibration` y `s3` que reescriben antes de
  comprobar; `s1` que no rechaza el reservado; `s1` que verifica un partido menos; `cadence`
  recomputando otro redondeo; `layer2` que cuenta cero. La primera pasada abortó por un
  artefacto del script (la copia no era un repositorio y un test lee `split.json` de `HEAD`);
  se le dio su `git init`. Rutas públicas: 8 funciones nuevas y 7 comandos con `--check` en las
  tablas de `test_public_routes` (cada una rechaza el reservado y sirve calibración).
  **Scripts de mutación pasados a `scripts/mutations/`** (cabecera con el registro que los cita
  y cómo correrlos; los logs al lado; LF; excluidos de ruff con `extend-exclude`, no los recoge
  pytest): `mutate22`, `mutate23a`, `mutate23b`, `mutate23c_a`, `mutate23c_a2`,
  `mutate23c_final`, `mutate25`, `mutate26`, `mutate27` y `mutate28`. Todos los citados se
  encontraron. Dudas: `mutate22.py` estaba en el scratchpad del proyecto
  football-tracking-base; el registro de la 23c dice "5 en B" sin nombrar el script, y se
  archivaron `mutate23c_b.py` y `mutate23c_b2.py` (de `r23c/B/scripts`, con `mutate_B.log` y
  `mutate_C.log`) por su ubicación, no por el registro. Los de la 23c restauran con
  `git checkout`, tal como se escribieron. Quedan en los scratchpads, sin copiar, los scripts de
  análisis de la 23c (`rd1` a `rd3`, `straddle`, etc.), que ningún registro cita.
  **Desviaciones:** `PARTIAL` también en los de capa 3 (la tarea lo pedía para los de fixtures);
  el `--check` de `power` lee las sondas de `--reports-dir`, el de escritura las de `reports/`;
  `extend-exclude` en `pyproject.toml` (está en `GUARDED_CODE`, que ya no coincide con el
  congelado, así que no afecta a la lectura hecha); el reservado se verifica por reproducción y
  `cmp`, no con un `--check` propio, porque el código del commit de la lectura es el congelado.
  Gate local en verde: ruff, format, `mypy src` y `pytest -q` (1.577 pasan, 66 deseleccionados).
  Revisión 27-28, pasada 1 (2026-10-24), sobre `git diff 9971807..b1ca9c2`: ocho hallazgos, sin
  tocar el paso del reservado de `full-build.yml`, `protocol/*.json`, `reports/heldout/` ni
  `data/`. Cada mutación se plantó sobre una copia del fichero, que se restauró después.
  (1) MEDIO, etiquetas de eje de los paneles a y b tecleadas: `4b3205f` las deriva de
  `BALL_DISTANCE_EDGES` y de los cortes de `runs.BANDS`; el test nuevo comprueba, sobre lo que el
  código dibuja ahora, que los números de cada etiqueta son los de la clave de su celda.
  Mutaciones: `5-10` a `5-15` y `up to 1 s` a `up to 2 s` en el código, ambas caen (antes, con
  los ficheros regenerados, 25 de 25 verdes). (2) MEDIO, `matplotlibrc` del usuario: `99d4f52`
  dibuja dentro de `style.context("default")`; dos tests (un `MATPLOTLIBRC` hostil en un
  subproceso y `rcParams` hostiles en curso). Mutación: quitar `style.context`, los dos caen.
  (3) y (4) BAJOS, `f7a31fd`: sin `except KeyError` (un partido que falta en V2 es ahora un
  error) y las frases "passed/failed", "the kill is ..." y las dos clases de V2 salen de
  `variants/V0/bar/passed`, `criteria/D5/killing` y `classes/1/used` y `classes/2_or_more/used`;
  se regeneraron `fig2_layer3.svg` y `.json` (cambió la frase de la clase vacía, un número más
  en el sidecar). Mutaciones: la frase tecleada de nuevo y el `except KeyError` repuesto, los
  dos tests nuevos caen. (5) BAJOS: `1de5d17`, `check_json` recibe la recomputación como
  llamada que solo corre si hay fichero (los ocho `--check` pasan la suya; los docstrings de
  `test_public_routes` vuelven a ser ciertos); mutación: recomputar antes de mirar si hay
  fichero, cae el test nuevo. `7e8ea4f`: `figures --check` dice "N of 4 files found"; mutación:
  contar siempre 4, caen dos casos. (6) `0588425`: `power --check` sin las sondas en
  `--reports-dir` sale con 2 y nombra lo que falta; mutación: quitar la guarda, cae el test.
  (7) `215f01e`: el script de comparación resuelve las dos rutas a absolutas, usa `ls -A`
  y tiene `tests/test_compare_heldout_script.py` (7 casos: idéntico, relativa, un valor, falta
  uno, uno de más, uno oculto, vacío); mutación: el script anterior falla la ruta relativa y el
  fichero oculto. (8) Este registro: 25 mutaciones de código (no 26) y sin tiempos de pared.
  Reabierto por la revisión 27-28 (ALTO 1, 2026-10-24): la mitad del reservado no se había
  probado de punta a punta. Los runs de `full-build` 40098167554 y 40099424687 (ubuntu) fallaron
  en el paso del reservado con las mismas líneas: `reliability.csv` y `amputation.csv` idénticos
  byte a byte, y en `layer2.json`, partido 2007721, un player-frame cruza el borde de 10 m de las
  bandas de distancia al balón: `ball_distance.05_10.detected` 0,847193 a 0,847209 y `.n` 9620 a
  9621; `ball_distance.10_20.detected` 0,793839 a 0,793831 y `.n` 25126 a 25125 (commiteado en
  Windows, reproducido en Linux). **Causa:** `np.hypot` (`visibility.py:57`, agrupado con
  `searchsorted` sobre `BALL_DISTANCE_EDGES`) pasa por la libm de la plataforma, no correctamente
  redondeada, y glibc y la CRT de Windows no coinciden. **Evidencia** (`scripts/hypot_platform_probe.py`,
  4.000.000 pares con semilla, rango de 120 m, numpy 2.5.4 de `uv.lock`; Windows nativo contra
  Docker `python:3.13`, glibc 2.41; salida completa en
  `scripts/hypot_platform_probe.log`, que repite estas dos cifras): `hypot: 681117 of 4000000 results differ in bits`;
  `sqrt: 0 of 4000000 results differ in bits` para `np.sqrt(dx*dx + dy*dy)`. Es la causa
  probable, no demostrada sobre el reservado (no se abre): la sonda muestra que `hypot` difiere
  entre plataformas y que `sqrt` no, y el cruce de un borde es lo que produce una diferencia así.
  El código del commit de la lectura está congelado, así que no se puede cambiar.
  **Decisión de Javier (2026-10-24):** pinear la diferencia, frente a un runner de Windows o una
  tolerancia. **Qué cambió** (`c01969a`, `3e48f8a`): `scripts/compare_heldout_reading.sh` acepta
  `--expect-diff FICHERO`; el `diff` de cada fichero distinto, bajo una cabecera `== nombre`, debe
  igualar FICHERO byte a byte; sin la opción, igual que antes. El fichero fijado es
  `scripts/heldout_linux_diff.txt` (LF; generado aplicando los cuatro cambios a una copia de
  `layer2.json` y corriendo el mismo `diff`; vive junto al script que lo lee y fuera de
  `reports/heldout/`, que el script lista). `full-build.yml` lo pasa. Tests en
  `tests/test_compare_heldout_script.py` (13): la diferencia fijada pasa con la opción; con un
  valor más, con otro cambio de las mismas líneas, con otra diferencia en otro fichero, sin
  diferencia alguna, y sin la opción, falla. Mutaciones sobre el script, restauradas: ignorar el
  fichero esperado (4 tests caen), comparar solo su primera línea (2) y no fallar ante una
  diferencia sin la opción (2). Gate local en verde (1.597 pasan, 66 deseleccionados).
  Run verde de `full-build`: https://github.com/javiersr1996/ac2-football/actions/runs/40109287550
  (`heldout: OK`, "the differences are exactly those pinned"); CI del push, run 40109287863, en verde.
  Revisión 27-28, pasada 2 (2026-10-24, Fable): sin altos ni medios; cuatro bajos. (1) `full-build`
  corría en `ubuntu-latest` y la diferencia fijada solo se produjo y verificó en la imagen
  `ubuntu-26.04` (runs 40098167554, 40099424687 y 40109287550 lo imprimen); `a797db3` fija
  `runs-on: ubuntu-26.04` (`ci.yml` sigue en `ubuntu-latest`) y el paso del reservado imprime
  `ldd --version | head -1`. La versión de glibc de esa imagen la imprime el run 40110756564 (el
  primero en `ubuntu-26.04` fijado, en verde: `ldd (Ubuntu GLIBC 2.43-2ubuntu2.4) 2.43` y
  `heldout: OK` con la diferencia fijada); la sonda de Docker corrió sobre otra glibc (2.41-12 de
  Debian), así que la diferencia del reservado se verificó con 2.43. No va en
  `heldout_linux_diff.txt` porque el script lo
  compara byte a byte. (4) En el mismo commit, el comentario de `full-build.yml` ya no dice
  "byte for byte" sin más: nombra la diferencia fijada. (2) `323b881` añade
  `scripts/hypot_platform_probe.log` (Windows nativo, Docker `python:3.13` con glibc 2.41-12 y
  numpy 2.5.4, y `compare`), repetido hoy: 681117 y 0 de 4000000, igual que el registro. (3)
  Cifras al día en este fichero: `test_figures.py` 30, `test_report_checks.py` 47 (recontados con
  `pytest --collect-only`), CI de Ubuntu de la tarea 27 y run verde de `full-build` citados. Gate
  local: ruff, format, `mypy src` y `pytest` de `test_compare_heldout_script.py` y
  `test_figures.py`; la suite completa tarda más de 30 min aquí y la corre CI al hacer push.
- [x] 29. `sonnet` API pública mínima y documentada (`reliability.sensitivity`,
  `reliability.amputate`, `protocol.data` como lector guardado del silver de la base, esquema del
  Parquet largo con `gap_len`) y un
  `examples/sensitivity.py` que corre sobre el sintético. Aceptación: el ejemplo corre en CI.
  Hecho (2026-10-24), commit `0a2a509` (sin push). **Superficie pública, sin código nuevo en
  `src/`:** los nombres de la tarea ya existían, con comportamiento y entrada en
  `FUNCTION_ROUTES` (`tests/test_public_routes.py`), así que no hay rutas nuevas y la tabla no
  cambia. Mapa: `reliability.sensitivity` es `ac2fb.reliability.sensitivity.sensitivity` (y
  `sensitivity_by_size`, `Window`, `WindowFrames`, `Reading`); `reliability.amputate` es
  `ac2fb.reliability.amputate.amputate` más `hiding`; `protocol.data` es el lector guardado
  (`read_frames`, `read_events`, `read_dim`), que sigue siendo la única puerta (el ejemplo no la
  usa, y `test_single_door.py` sigue en verde); el esquema largo es `long.LONG_SCHEMA`.
  **Dónde está documentado:** docstring de `ac2fb/reliability/__init__.py` (cuatro pasos, cada
  nombre resuelto por `test_every_documented_name_resolves_and_is_exported` contra el `__all__`
  de su módulo, sin reexportar nada para no duplicar rutas); el esquema del Parquet largo se
  escribe una vez, en `LONG_SCHEMA`, y `test_the_long_schema_is_one_thing_in_code_and_in_its_docstring`
  ata `LONG_COLUMNS`, el esquema y el docstring de `long.py` (nombre y tipo de cada columna,
  `gap_len` int32).
  **Ejemplo:** `examples/sensitivity.py` construye en memoria un partido sintético con forma de
  silver (11 contra 11, 2.000 fotogramas, huecos sembrados) y recorre `long_table`,
  `metric_units`, `sensitivity` y `amputate`; no lee ficheros ni `data/`. Salida (artefacto:
  `uv run python examples/sensitivity.py`): `line_height_m: V0 n=45 mean=8.86 m, V1 n=31
  mean=8.90 m, extrapolated=0.139, amputation n=31 mean_abs_error=0.078 m (synthetic numbers, not
  findings)`. **Corre en CI de dos formas:** `tests/test_public_api.py` lo lanza como subproceso
  con `FTBASE_DATA_ROOT` inexistente y directorio vacío, y comprueba la línea entera y que
  0 < n(V1) < n(V0); y un paso nuevo de `ci.yml` lo corre y falla si falta el aviso. Ninguno
  puede saltarse (el conftest cuenta los skips como fallo; el paso es de `run`, sin condición).
  **Mutaciones** (sobre copias del árbol en `scratchpad/mut29`, script `mutate29.sh`, ninguna en el
  árbol de trabajo): (a) un nombre no exportado en el docstring de `reliability`: cae
  `test_every_documented_name_...`; (b) una columna `extra` añadida a `LONG_SCHEMA` y
  `LONG_COLUMNS` y no al docstring: cae `test_the_long_schema_...` (y de paso el ejemplo, porque
  `long_table` ya no arma el esquema); (c) el ejemplo sin el aviso: cae
  `test_the_example_runs_...`; (d) el ejemplo con `open("data/x")`: caen
  `test_the_example_reads_no_file` y el de ejecución. **Gate local:** ruff, format, `mypy src`
  y `pytest` (674 pasan, 18 min) de `test_public_api.py`, `test_public_routes.py`, `test_single_door.py` y
  `test_figures.py`; la suite completa tarda más de 30 min aquí y la corre CI al hacer push.
  Cambiar `src/` mueve `code_tree_sha` (solo un docstring, sin cambio de comportamiento ni de
  bytes de ningún comando).
- [x] 30. `sonnet` `full-build.yml`: `workflow_dispatch`, caché de `data/raw` por huella del
  manifiesto, build completo, todos los `--check` y los dos bloques de `clean_clone_check.sh` en
  `ubuntu-latest`. Aceptación: una ejecución en verde con su enlace; el árbol queda limpio. Rama
  B: los `--check` del reservado corren en un `git worktree` en el commit de la lectura.
  Hecho (2026-10-22), commits `3e9cbcc`, `e8d0891` y `09915b8` (README). **Qué hay:**
  `.github/workflows/full-build.yml` (`workflow_dispatch`, `ubuntu-latest`, solo las acciones de
  `ci.yml` más `actions/cache/restore` y `save` en `v6.1.0`). Clave de la caché: sha256 del
  `sources.json` de la base (`047f8b36...`). Caché fría: el bloque rápido baja sus 5 ficheros, el
  completo baja los 85 una vez y, si salen en verde, se guardan; caché caliente: cada bloque recibe
  una copia de `raw` en su propio `FTBASE_DATA_ROOT` (el rápido solo los 5 ficheros de su partido,
  elegidos con `select_match`, para que bronze y silver se queden en 1 partido) y `ftbase ingest`
  salta todo lo presente y verificado. Los bloques del README no cambian por la caché; el script
  tampoco. Después, `ac2fb protocol --check` y `ac2fb reliability --check` (los únicos `--check` de
  `ac2fb`; `ftbase provenance --check` no aplica: este repo no tiene `reports/provenance.json`) sobre
  el silver que construyó el bloque completo. **Dos ejecuciones, las dos en verde:** fría
  https://github.com/javiersr1996/ac2-football/actions/runs/39782141426 (rápido `CLEAN CLONE OK in
  9 s`, `downloaded=5`, 95.624.493 B; completo `CLEAN CLONE OK in 174 s`, `downloaded=85`,
  1.919.842.163 B, de ellos 1.823.448.331 B en los 20 ficheros LFS; recibo `verified=85 failed=0`;
  `protocol: OK` con 99 campos, 32 reglas, 27 constantes; `reliability`: 465 filas, 6.510 celdas,
  10 partidos) y caliente https://github.com/javiersr1996/ac2-football/actions/runs/39783298818
  (`downloaded=0` en los dos bloques, 9 s y 150 s, mismos `--check`). Cuota LFS gastada: una
  descarga completa más el partido rápido; `cache-hit` lo imprime el resumen del run.
  **Riesgo conocido, materializado y arreglado:** el bloque rápido reescribía `reports/layer2.json`
  con un solo partido (comprobado en local: difiere del commiteado) y el script habría fallado con
  "the clone is not clean". Cambio mínimo en el bloque rápido del README:
  `ac2fb layer2 --match 1874553 --reports-dir ../reports-quick` (fuera del árbol; el script no se
  toca). `layer2`, `calibration` y `reliability` completos reproducen byte a byte los ficheros de
  `reports/` (comprobado en local con `--reports-dir` aparte y con `cmp`). README: rellenados los
  `PENDING(task 30)` con 95,6 MB y 9 s (rápido), 1,9 GB (1,8 GB LFS) y unos 3 min (completo), cada
  cifra con su `<!-- src: -->` al run. No se tocó `src/`, `protocol/*.json` ni el reservado.
  **Pendiente tras J4:** la rama B ("los `--check` del reservado en un `git worktree` en el commit
  de la lectura"): la lectura no existe aún, así que ese paso no está en el workflow.
  Desviaciones: el medido local de `layer2` + `calibration` + `reliability` fue 38 min por
  contención de la máquina (el run de CI, 150 s el bloque entero); el primer intento de dispatch
  falló al parsear el YAML (`runner` no existe en el `env` del job), sin descargar nada.
- [x] 31. `sonnet` `scripts/readme_check.py` y su test: palabras del README (todo el texto, bloques
  de código incluidos, sin comentarios HTML) ≤ 1000, figuras más tablas ≤ 2, cada número del README
  presente en algún artefacto de `reports/`, y la frase literal de que los fixtures sintéticos no
  producen cifra alguna. Mutaciones: 1001 palabras, tercera tabla, número inventado, frase borrada.
  **Hecho (2026-10-24)**, commit `361eeac` (script y `tests/test_readme_check.py`, 27 tests). Comando
  de la puerta V: `uv run python scripts/readme_check.py` (sale 0/1; imprime palabras, figuras +
  tablas, números comprobados y cada fallo). No está en `ci.yml` (fallaría hasta la 33); los tests
  sí corren en CI con pytest, sobre READMEs sintéticos en directorios temporales.
  **Reglas** (más estrictas que el texto de la tarea, según la propuesta de la 33): palabras = trozos
  separados por espacio de todo el texto, código incluido, sin ningún comentario HTML; figuras
  (`![](...)`, `<img`) más tablas Markdown, fuera de bloques de código; la frase literal
  `Synthetic fixtures are used only for tests and produce no figure in this README.` (la del README
  actual; la fijé yo, el texto de la tarea no da las palabras); ningún `PENDING(`, ni en comentarios;
  cada número con `<!-- src: -->` debe igualar el valor citado al redondeo escrito (mitad hacia
  arriba), `%` contra valor × 100, sin signo = magnitud, con `+`/`-` = signo; un número sin `src`
  falla salvo lista permitida. Un comentario `src` cubre los números escritos desde el comentario o
  fin de frase/párrafo anterior. Sintaxis aceptada (la del README): `fichero.json|toml:clave.con.puntos`
  (la clave más larga que exista gana, porque `summary` de `layer2.json` tiene claves con punto),
  `*` con `(min)`, `(max)` o `(count below zero)` (y se acepta el número de elementos, "8 de 10"),
  varias claves con coma (se acepta su suma: 10 + 10 = 20 partidos), cociente `a / b`, lista = su
  longitud, duraciones en la clave (`gt_20s`, `1_5s`) = "más de 20 s"; otro fichero (`docs/*.md`,
  `uv.lock`, `scripts/*.log`): `fichero:frase`, la frase debe estar en una línea y el número en esa
  misma línea; ejecución de CI (`Full build run <id>`, `same run`, URL `actions/runs/<id>`): **solo
  se comprueba que la cita exista, no el valor** (sin red); se imprime aparte.
  **Lista permitida** (`ALLOWED` en el script): `Analytics Cup 2.0`, años y temporadas (`20dd`,
  `20dd/dd`), `Figure N`, `Layer 2|3`, y `--match <id>` (este además debe aparecer en algún
  artefacto de `reports/`). No se comprueban unidades salvo `%` (m, s, MB) ni cuentan los números en
  palabras ("four", "eleven").
  **Mutaciones** (cada una es un test que falla, con el límite a ambos lados): 1000 palabras pasan y
  1001 fallan; las palabras de un comentario no cuentan; el código sí cuenta; 1 figura + 1 tabla
  pasan y una segunda tabla, una segunda imagen o un `<img>` fallan; una tabla en un bloque de
  código, en un comentario o una regla `---` no son tabla; número inventado (215 por 214) y sin
  `src` (42, en prosa y en código); frase borrada o cambiada en una palabra (partida en dos líneas
  sí vale); redondeo desfasado un paso (56.1, 56.3), mitad hacia arriba (0.5625 = 56.3 %), signo;
  clave inexistente, fichero inexistente, frase inexistente, fichero fuera del repo; `PENDING(` en
  texto y en comentario; `src` sin número; `*` sin modificador; CI con `same run` sin ejecución
  previa. Para validar los tests, 21 mutaciones plantadas en el propio script (umbrales, `>=`,
  redondeo, `%`, signo, `PENDING`, comentarios, fences, `src` sin número, lista permitida, etc.):
  20 matadas (más el redondeo mitad hacia abajo, aparte), 1 equivalente superviviente (`not sep or not rest.strip()`: otro error salta igual).
  **Resultado sobre el README actual** (no se tocó): 928 palabras, 2 figuras + 0 tablas, 60 números
  (39 iguales a su `src`, 7 solo con cita de CI, 14 permitidos, 0 fallidos). Falla en 3 cosas, todas
  `PENDING(`: `held-out reading` y dos `task 27`. Ninguna clave citada deja de resolver. Los 7
  números de CI (95.6 MB, 5 y 85 ficheros, 1.9 GB, 1.8 GB, 9 s, 3 min) quedan sin comprobar su valor
  por diseño, y el 1.9 GB sigue sin redondear desde el manifiesto (1.823.448.331 B, ver la 33).
  Decisiones por si Javier quiere cambiarlas: la frase exacta; que un número sin signo valga por su
  magnitud (el efecto está en el JSON como -0.19268 y el README dice 0.19); que `8 of 10` acepte el
  total de elementos; que las palabras cuenten por separación de espacios (los fences y `##` suman).
- [x] 32. `sonnet` Clip de 10 s para el vídeo: una recepción con los defensores detectados en
  relleno y los extrapolados en hueco con su `gap_len`, desde silver por `ac2fb clip` (matplotlib).
  **Hecho (2026-10-24)**, commits `1591ce4` (comando, tests, workflows) y el de este registro con
  `reports/clip/` y la corrección de dos tests (sin push). **Comando:** `ac2fb clip [--match ID]
  [--out-dir DIR] [--check]`; partido por defecto 1874553 (el del bloque rápido del README; un test
  exige que el defecto sea de calibración). Lee por `load_match`, es decir por `protocol.data`:
  un reservado sale con exit 2 y no escribe nada. Módulo `src/ac2fb/clip.py` (puro: devuelve bytes;
  `ffmpeg` solo en `encode_mp4`); el cuerpo de la CLI lee y escribe, como `figures`.
  **La regla (en código, `Rule` y `describe`; el sidecar la repite):** candidatas son los eventos
  `player_possession` con equipo y jugador (el receptor) cuyo receptor y balón están detectados en
  el primer fotograma del evento y con al menos 4 rivales detectados ahí (para que el clip muestre
  los dos tipos). Orden: más rivales extrapolados en ese fotograma, después el mayor `gap_len` entre
  ellos, después periodo y fotograma (el más temprano). Gana la primera con ventana completa: 100
  fotogramas (10 s a 10 Hz) desde 30 antes de la recepción, dentro de un periodo, con receptor,
  balón y cada rival presentes y con `gap_len` en todos. Defensores = rivales del receptor,
  portero incluido. **Recepción elegida** (artefacto: `reports/clip/clip.json`): partido 1874553,
  periodo 1, fotograma 14562, pase del jugador 50968 (equipo 866); en ese fotograma 7 de 11
  defensores extrapolados y 4 vistos, el mayor `gap_len` 1214 fotogramas (121,4 s, jugador 50999);
  a lo largo de la ventana pasan de 7 a 4 extrapolados.
  **Qué muestra:** campo 105 x 68 girado para que el equipo del receptor ataque a la derecha;
  defensores detectados con marcador lleno bermellón, extrapolados con marcador hueco y su `gap_len`
  en segundos (`gap_len` / 10, un decimal) encima; receptor con anillo negro; balón negro;
  compañeros como puntos azules pequeños (huecos si extrapolados, sin etiqueta); a la derecha un
  contador vivo ("7 of 11 defenders filled in by the model") y una leyenda de letra 20 pt; abajo el
  reloj relativo a la recepción ("+0.0 s RECEPTION"). 1280 x 720, 10 fps en tiempo real, sin
  voz ni música. Fuentes de 16 a 54 pt para que se lea en un móvil.
  **Ficheros** (en `reports/clip/`): `clip.mp4` 153.234 B (H.264, yuv420p, 100 fotogramas, 10,0 s;
  muy por debajo de los 3 MB), `clip_still.png` 97.806 B (fotograma de la recepción, para la
  miniatura o el README), `clip.json` 27.041 B (LF, claves ordenadas, sin fecha). El sidecar guarda,
  por fotograma, `detected` y `gap_len` de cada defensor, del receptor y del balón, los números
  del contador y el hash de los píxeles de todos los fotogramas. Generar: 36 s; `--check`: 10 s.
  **`--check`:** vuelve a dibujar los 100 fotogramas y compara el sidecar byte a byte (contiene el
  hash sha256 de los píxeles RGB de todos los fotogramas y del de la recepción), el PNG por sus
  píxeles decodificados (no por sus bytes, que dependen de zlib) y el MP4 por el hash que lleva en
  su comentario (`ac2fb clip frames_sha256=...`, escrito por `encode_mp4`); los bytes del MP4 no se
  comparan porque dependen del codificador, así que el vídeo queda atado a un dibujo pero no a su
  contenido decodificado. No necesita ffmpeg. Estabilidad (reglas de la 27: `style.context("default")`,
  `rc_context` fijo, sin metadatos con fecha): el hash de píxeles sale igual en Windows (matplotlib
  3.11.2, numpy 2.5.4, pillow 13.0.0) y en Linux x86-64 (`python:3.13-slim` en Docker con esas
  mismas versiones, ejecutando el mismo dibujo sobre la escena guardada: `3ec84354...5840` en
  ambos). No lo he podido comprobar en el runner de GitHub: `clip --check` entra en `full-build.yml`
  (tras `figures --check`, con el silver completo) y sin dispatch; si el runner difiere, ese paso
  fallará y bastará bajar el `--check` del vídeo a sidecar y PNG.
  **Rutas y puerta única:** entradas nuevas en `FUNCTION_ROUTES` (`clip.build`, `check`, `choose`,
  `describe`, `encode_mp4`, `ffmpeg`) y `("clip",)` en `CLI_ROUTES` (el comando con una regla corta,
  porque los periodos sintéticos tienen 60 fotogramas, y su `--check`); un reservado se rechaza y
  uno de calibración se sirve; `test_single_door.py` en verde. **ffmpeg en CI:** los tests del
  vídeo y las rutas de `encode_mp4` y `clip` lo necesitan y fallan sin él (no hay skip); `ci.yml`
  gana un paso que lo instala si falta (`apt-get`). Cambia `ci.yml` aunque la tarea solo pedía
  `full-build.yml`.
  **Tests** (`tests/test_clip.py`, 28; `tests/test_realdata_clip.py`, 2, deseleccionados por
  defecto): la regla con detección y `gap_len` sembrados en copias del partido sintético, cada
  número dibujado contra la tabla larga leída aparte por la puerta, las etiquetas del pintor, el
  color del centro de un marcador lleno y de uno hueco, el sidecar canónico, el check ante cada
  fichero ausente o cambiado, el MP4 real (H.264, 1280x720, número de fotogramas) y la CLI.
  **Mutaciones** (20, en un `git worktree` aparte con un script, ninguna en el árbol de trabajo;
  las 20 matadas): orden por hueco antes que por cuenta, hueco fuera de la clave, fotograma
  descendente, sin comprobar ventana completa, receptor no comprobado, balón no comprobado,
  `<` por `<=` en `min_seen`, signo de ataque sin aplicar, etiqueta en fotogramas, llenos y huecos
  intercambiados, `gap_len` desplazado uno en la escena, fecha en el sidecar, PNG comparado por
  bytes, MP4 que solo debe existir, check que ignora el sidecar, partido por defecto reservado,
  ficheros escritos antes de buscar ffmpeg, check que exige ffmpeg, rechazo del reservado
  tragado (exit 1). **Desviación honesta:** 3 mutaciones sobrevivieron a la primera versión de los
  tests (ventana con hueco, receptor y balón no comprobados) porque los casos sembrados caían
  fuera por otra regla (`min_seen`, o rivales del propio equipo); se corrigieron los casos y las
  tres mueren. **Gate local:** `ruff check`, `ruff format --check`, `mypy src` limpios; `pytest`
  de `test_public_routes.py`, `test_single_door.py`, `test_clip.py` y `test_cli.py`: 693 pasan (15
  min); tras corregir los dos tests y renombrar un campo, `test_clip.py` (28), las rutas de `clip`
  (23) y `test_single_door.py` (86) en verde otra vez, y los 2 de `-m realdata`; la suite
  completa tarda más de 30 min aquí y la corre CI al hacer push. Cambiar `src/` mueve
  `code_tree_sha` (sin efecto: el reservado sigue en diseño y `layer2.json` no está congelado).
  **Decisiones por si Javier quiere cambiarlas:** el clip va en tiempo real a 10 fps (el dato es de
  10 Hz; no interpolo entre fotogramas para no inventar posiciones), apto para 16:9; la elegida
  tiene un defensor con 121 s de hueco, real pero llamativo ("121.4 s"); los defensores incluyen al
  portero; el texto del clip está en inglés.
  En el runner (2026-10-24): `full-build` run 40117288163, `ubuntu-26.04`, en verde, con
  `clip: OK` (100 fotogramas redibujados y con hash, sidecar byte a byte, still por píxeles, vídeo
  por el hash de su comentario); CI del push con ffmpeg, runs 40117288550 y 40117322501, en verde.
- [ ] J5. **[Javier, opcional]** Abrir el issue en kloppy con el texto de la 10.

## Fase 5: entrega (lun 7 dic a vie 18 dic)

- [ ] 33. `sonnet` README en inglés: qué es, procedencia (abajo), capa 2 (con "extrapolated is
  interpolated" y la cifra de huecos largos), capa 3, método en corto, reproducir (bloque rápido
  de un partido y bloque completo, con tiempos medidos), fixtures sintéticos solo para tests,
  reutilizar, licencia y datos. Aceptación: la 31 en verde; lectura de Javier.
  El README debe decir que el reservado se reproduce byte a byte en Windows y que en Linux
  difiere en ese único player-frame, fijado en CI (`scripts/heldout_linux_diff.txt`, tarea 28).
  Borrador adelantado (2026-10-22), en `README.md`: cada cifra lleva al lado
  `<!-- src: fichero:clave -->` y lo que falta dice `PENDING(...)`. Propuesta para la 31: comprobar
  cada cifra contra la clave que cita, con su redondeo, en vez de buscarla literal en `reports/`
  (así cubre también tamaños y versiones, que no viven en `reports/`). Los tamaños de descarga
  (95.6 MB, 1.9 GB) vienen del README anterior y los re-mide la 30: el manifiesto suma
  1.823.448.331 B (choque 1), que no redondea a 1.9 GB.
  **Borrador final (2026-10-24)**, commits `1928453` (README) y `e4c7141` (`readme_check` como
  paso de `ci.yml`, tras `mypy`); sin push. `uv run python scripts/readme_check.py`: `words: 994
  (max 1000)`, `figures + tables: 2 + 0 = 2`, `numbers: 79 checked, 59 equal to their src, 7
  covered by a CI citation only (presence, not value), 13 allow-listed, 0 failed`, `readme_check:
  OK`. **Qué cambió frente al borrador:** (1) la entrada da las dos mitades (56,2 % y 57,0 % de
  jugador-frames detectados, mediana por partido) y el veredicto de la capa 2 por partido, con
  rangos del sidecar `reports/figures/fig1_layer2.json` (`series.N.points.0.of.*(min|max|count
  below zero)`, las listas `of` de las medianas por métrica y mitad): altura de línea V1 − V0 de
  +7,2 a +13,2 m en el reservado (+8,7 a +13,9 en calibración), positiva en 10 de 10; longitud
  −37,3 a −17,1 m (−34,5 a −21,8), negativa en 10 de 10; área, reacción y presión 10 de 10; rival
  9 de 10 en las dos mitades; anchura mixta (estrecha en 8 y 7 de 10); leído como selección (la
  cámara sigue al balón), no como ruido. (2) "Extrapolated is interpolated" con las claves
  `reacquisition` de `layer2.json` (las de la figura 1b) en vez de `runs`: salto al reaparecer
  tras más de 20 s 0,203 m frente a 0,198 m de paso visto (calibración), 0,190 frente a 0,201
  (reservado); pasos dentro del hueco 0,130 y 0,125 m; los huecos de más de 20 s tienen el 38,7 %
  y el 36,0 % de los frames rellenados. (3) Amputación por partido del reservado (línea 0,90 a
  1,20 m, anchura 2,1 a 2,9, longitud 0,1 a 6,0), de la figura 1d. (4) Capa 3 contada como
  resultado, efectos con signo (−0,19 sd, −0,20 sd), "That is the result". (5) "Method in short"
  reducido a la puerta, el `--check` y la reproducción: byte a byte en Windows; en Linux
  (`ubuntu-26.04`, citado de `full-build.yml:runs-on`) un player-frame cruza un borde de banda,
  fijado en `scripts/heldout_linux_diff.txt`. (6) Rutas de las figuras corregidas a
  `reports/figures/*.svg` (el borrador apuntaba a `figures/*.png`, inexistentes). (7) El tiempo
  del bloque completo cita el run 40117288163 (202 s, caché caliente; el comentario nombra el frío
  39782141426, 174 s antes de que `amputation` entrara en el bloque); tamaños, del run frío. Los
  7 números de CI siguen sin comprobar valor (diseño de la 31). (8) Procedencia en primera persona.
  Bloques de código idénticos a `HEAD` (diff vacío); imágenes resuelven; LF; sin `PENDING(`.
  **Sin artefacto, fuera del README:** el crecimiento del error de amputación banda a banda por
  partido (8, 10, 10, 10, 10, 8, 7 en el reservado) y la fracción extrapolada por métrica, que
  solo imprime `scripts/layer2_summary.py` (se dice "growing with gap length" sin cifra); la
  glibc 2.43 del runner (solo en este plan y en el log del run). **Mutaciones** (11, sobre copia
  del README, `mutate_readme.py` en el scratchpad de la sesión; todas caen y nombran el número):
  salto 0,203→0,204; mínimo +7,2→+7,3; máximo −17,1→−17,2 y su signo; recuento 8→9; signo del
  efecto; cociente 95→94; porcentaje 38,7→38,6; reservado 57,0→56,9; `ubuntu-24.04`; kloppy
  3.19.2. Gate local en verde: `readme_check`, ruff, format, `mypy src`, `pytest
  tests/test_readme_check.py` (27). **Pendiente para `[x]`:** simulación del jurado (Fable) y
  lectura de Javier. Decisiones a juzgar: `reacquisition` y no `runs` para el salto (la figura 1b
  usa `reacquisition`; con `runs` el borrador decía 0,217 frente a 0,198); citas por índice de
  serie (`series.63`), frágiles si `figures.py` reordena, pero `readme_check` corre en CI; "Method
  in short" ya no repite V0/V1; "10 of 10" lo valida el número de elementos de la lista, no el
  recuento del signo (tolerancia de la 31).
  **Revisión tras la simulación del jurado (2026-10-24; 7,4/10, comunicación 5/10)**, commits
  `e10d0d2` (pie de la figura 2), `538c7b8` (citas al sidecar y texto nuevo) y `ee57178` (recorte
  a 949); sin push. **Recuento doble:** `readme_check` 949 palabras y `wc -w README.md` 949 (el
  fichero crudo es el texto contado: las citas ya no viven en el README). Línea de la puerta:
  `words: 949 (max 1000)`, `figures + tables: 2 + 0 = 2`, `numbers: 77 checked, 56 equal to their
  src, 7 covered by a CI citation only (presence, not value), 14 allow-listed, 0 failed`,
  `readme_check: OK`. **Mecanismo nuevo (punto 8):** `README.src.json` lista cada número no
  permitido en orden de aparición (`number` tal como está escrito, `src` con la sintaxis de la 31,
  `note` libre); `scripts/readme_check.py` empareja uno a uno (un número sin entrada, una entrada
  sin número o un desorden fallan y nombran los dos lados), cuenta las palabras del fichero crudo
  (comentarios incluidos: los marcadores `clean-clone` suman 12) y admite `Layer 1`.
  `tests/test_readme_check.py` reescrito sobre el sidecar (30 tests: las tres mutaciones de la 33
  más sidecar ausente o malformado, y las de la 31 adaptadas). Sobre el README real, 7 mutaciones
  en copia (`mutate_sidecar.py`, scratchpad): número cambiado solo en el README, entrada borrada,
  dos entradas permutadas, valor erróneo en los dos lados, signo invertido, suelo D3 0,37, número
  suelto al final; las 7 caen. **Texto (puntos 1 a 7):** título real; frase para analistas;
  capas, unidad y partición definidas antes de la figura 1, con "amputation error" definido;
  V1 − V0 presentado como selección y no como error de relleno, con la cifra del relleno (0,90 a
  1,20 m en la altura de línea) frente a +7 a +14 m de selección; capa 3 con la regla de muerte
  en la primera frase; pie de la figura 2 con el suelo D3 (0,36 sd, el doble de la pretendencia);
  colas p90 y p99 del salto tras huecos de más de 20 s frente a los pasos entre detectados, en las
  dos mitades; kloppy en frase propia; "every metric moves the same way" fuera; un solo "n = 10
  matches per half"; "byte for byte on my Windows machine" y "GitHub runner" dichos así; línea del
  reservado (`git worktree add ../reading 4cb9351`, `uv sync --locked`, `heldout read
  --reports-dir ../heldout-check`, `compare_heldout_reading.sh`), **corrida aquí tal cual está
  escrita: `heldout: OK`, 3 ficheros byte a byte, 174 s** (worktree y directorio borrados después);
  macOS sin probar. **Figura 2 (punto 4):** el pie de V2 decía "0 usable units"; el artefacto
  registra 280 unidades con un jugador extrapolado en la recepción y 38 con dos o más
  (`beside.V2.classes.*.units`), ninguna usable, y la clase sin extrapolados igual a V1 partido a
  partido; la frase propuesta ("no unit had an extrapolated player") era falsa y se escribió desde
  esos campos: "Units with an extrapolated player at the reception, 280 with one and 38 with two
  or more, fill no cell: V2 is V1, no estimate for them", solo cuando `used` es 0 en las dos
  clases y V2 iguala V1 en todos los partidos (si no, cae a los recuentos). `fig2_layer3.svg|json`
  regenerados; `figures --check` OK; `test_figures.py` (30) planta las dos ramas. **No aplicado o
  recortado por palabras:** "Method in short" se funde en Reproduce; los errores de amputación de
  anchura y longitud y "inside gaps the steps are smaller" salen del texto (siguen en la figura 1d
  y en `layer2.json`); la lista de nombres de la API en Reuse se reduce a la referencia al
  docstring. Gate local en verde: ruff, format, `mypy src`, `figures --check`, `pytest
  tests/test_figures.py tests/test_readme_check.py` (60). Bloques de código idénticos a `HEAD`;
  imágenes resuelven; LF; sin `PENDING(`.
  **Jurado 2 (2026-10-25, Fable; lector sin historia: solo las bases y el repo, sin `tasks/`)**:
  7,2/10 (relevancia 7, metodología 8, originalidad 8, comunicación 5, potencial open source 8).
  Riesgo nuevo: el guion, a 149 palabras, solo cabía en 60 s a 150 palabras por minuto sin pausas.
  Arreglos de un agente Fable en worktree, cada propuesta contrastada con el artefacto antes de
  aplicarla; commits `919539d` a `7735b3b` (10) y `803896d`. (1) Guion a 134 palabras (54 s): la
  frase 1 dice los 7 rellenados (lo que enseña el contador de `clip_still.png`) y la 2 los 4
  vistos; la 12 sin los 9 s. (2) V0, V1 y V2 definidos en llano ("computed three ways"); la receta
  del reservado pasa a `docs/heldout.md` con los comandos idénticos (ningún test ni flujo leía esa
  línea del README; `full-build.yml` corre los suyos). (3) Tesis reescrita, "on the units the
  camera saw whole" (V1 conserva unidades enteras, no jugadores sueltos, al revés de lo que
  proponía el jurado). (4) Cifra nueva: todos vistos, mediana por partido, en el 2,4 % de las
  fases del bloque (3,3 % en el reservado) y el 33 % de las recepciones de la línea de cuatro
  (36 %) (`layer2.json:summary.{block,line}.all_detected.median`, `visibility.py:155` y `:193`).
  (5) D3: la pretendencia es el avance del balón en [t − W, t]; el efecto ya está ajustado por
  ella (`effect.py`, coeficiente de G en y = a + b x + tau G; `protocol.json:pretrend.role`, "both
  apply", comprobado también en la sesión principal) y su suelo, 0,36 sd, se conocía antes de
  cualquier resultado (`design.json`; `b66e7d7` antes de `a0a3b68`). (6) Reuse: `--match` sirve los
  10 partidos de calibración (`data.py:343-345`). (9) Advertencia de la amputación, sin cifra: la
  referencia son las unidades vistas enteras, pocas y compactas en el bloque, y el error crece con
  el hueco (`amputation.csv`: `gt_20s` por encima del total en 70 de 70 pares métrica-partido; las
  cifras del jurado, 17 a 32 unidades y 2,7 a 6,3 m, eran falsas y no se escriben). (10)
  Etiquetas de las tiras de la figura 1 a 9,5 px (`figures --check` OK, sidecar idéntico). (8)
  `macos.yml`, solo `workflow_dispatch`. No aplicado: (7) publicar el issue de kloppy (J5, de
  Javier) y sacar el texto de la figura 2. Retoque propio en `803896d`: "the ones near the ball"
  y "byte for byte on my Windows machine" (el jurado 1 pidió decir que es una máquina), con dos
  palabras recortadas. Puertas: `readme_check: OK` (998 palabras, `wc -w` 998; 82 números, 61
  iguales, 7 solo CI, 14 permitidos, 0 fallos); `video_script_check: OK` (134 palabras, 54 s, 11
  números, 0 fallos); ruff, format, `mypy src`; pytest de los dos checkers (44) y
  `test_figures.py`; CI run 40189342879 en verde sobre `803896d`. Margen: 2 palabras, así que la
  próxima edición del README empieza recortando. **Pendiente para `[x]`:** lectura de Javier.
- [x] 34. `sonnet` Guion del vídeo (≤ 60 s, unas 140 palabras, voz de Javier) con plano por frase
  (figura 1, figura 2, clip de la 32); cada cifra con su artefacto.
  **Hecho (2026-10-24)**, commits `7098de7` (`docs/video_script.md`), `ab3d2d3`
  (`scripts/video_script_check.py` y `tests/test_video_script_check.py`), `d8f9544` (paso en
  `ci.yml`) y el de este registro; sin push. **Guion:** `docs/video_script.md`, en inglés, tabla
  con una fila por frase: ventana de tiempo a 150 palabras por minuto, plano, frase tal como se
  dice y, por cada cifra, su artefacto y clave con la sintaxis `src` de `README.src.json`, una
  cita entre acentos graves por cifra y en orden. **146 palabras habladas, 58 s a 150 palabras
  por minuto** (12 filas; la línea del recuento vive en el fichero y la comprueba el gate).
  Estructura: gancho con el clip (la cámara vio 4 de 11 defensores en la recepción, el modelo
  rellenó los otros 7, cada uno etiquetado con los segundos a su detección más cercana); hallazgo
  de la capa 2 con el rango por partido (20 partidos, cerca de la mitad de los jugador-frames
  vistos; solo con lo visto la línea sube de 7 a 14 m y el bloque se acorta de 17 a 37 m en todos
  los partidos); implicación para el analista (longitud y área son sobre todo lo que la cámara
  eligió enseñar, presión y rival más cercano sobreviven; etiquetar cada métrica con cuántos
  jugadores se vieron); capa 3 muerta por su regla prerregistrada (efecto −0,19 sd, diferencia
  previa 0,18 sd, "that is the published result"); y el código en GitHub (un partido en unos 9 s,
  cita de CI). **Planos:** clip de 0 a 3 s y congelado en la recepción (`clip_still.png`,
  contador "7 of 11"), clip de 3 a 10 s, figura 1a, figura 1c (tiras de altura de línea, longitud
  del bloque, presión y rival), Javier a cámara, figura 2a (efecto conjunto frente al suelo D3),
  figura 2b, Javier a cámara, README en pantalla (sección Reproduce). Cifras citadas: `clip.json`
  (`key.defenders_seen`, `n_defenders`, `key.defenders_extrapolated`), `protocol/split.json`
  (10 + 10), `fig1_layer2.json` (`series.63|61|87.points.0.of.*(min|max)`, las mismas claves que
  el README), `calibration.json` (`criteria.D3.values.effect|pretrend`), run 39782141426 para los
  9 s (solo presencia, como en el README); "Layer 3" va en la lista permitida; "about half" es
  palabra, no numeral (el README dice lo mismo y lo respalda con 56,2 % y 57,0 %). Palabras
  pensadas para la voz de Javier: sin "extrapolated", "interpolated" ni "amputation"; `-0.19` se
  lee "minus zero point one nine".
  **Gate:** `scripts/video_script_check.py`, hermano de `readme_check.py` (reutiliza su resolutor,
  su comparación con redondeo y signo, su lista permitida y su sintaxis de citas): una tabla con
  columnas `Sentence` y `Sources`; solo la columna `Sentence` se cuenta y se comprueba (≤ 150
  palabras); la línea "N spoken words, S s at 150 words per minute" del fichero tiene que
  coincidir con el recuento; cada cifra se empareja con la siguiente cita de su fila (más cifras
  que citas, o al revés, falla y nombra la frase); las citas las resuelve `readme_check.resolve`.
  Salida: `rows: 12`, `words: 146 (max 150), 58 s at 150 words per minute`, `numbers: 12 checked,
  10 equal to their src, 1 covered by a CI citation only (presence, not value), 1 allow-listed, 0
  failed`, `video_script_check: OK`. Paso nuevo en `ci.yml` tras el gate del README.
  **Tests** (`tests/test_video_script_check.py`, 14): línea base, cifra cambiada (y un paso de
  redondeo en un rango), cifra sin cita, cita sin cifra, 150 palabras pasan y 151 fallan, columnas
  de plano y tiempo ni habladas ni comprobadas, signo escrito que debe coincidir, cita que no
  resuelve (clave, fichero, run sin id, `same run` sin run anterior), recuento o duración
  declarados falsos o ausentes, tabla sin columnas o fila corta, lista permitida y sus vecinos,
  CRLF, el comando y su salida, y el guion real contra los artefactos reales. **Mutaciones sobre
  el guion real** (12, en copia en el scratchpad de la sesión, `mutate34.py` y `mutate34.log`;
  las 12 caen y nombran la fila): 4→5, 7→8, 37→38, 0,18→0,19, signo −0,19→+0,19, cita del 11
  borrada, cita equivocada para el 7, clave mal escrita, 151 palabras, recuento 146→140, duración
  58→55, cifra añadida sin cita. Desviación honesta: el primer borrador declaraba 145 palabras y
  el gate lo corrigió a 146. Gate local en verde: `ruff check`, `ruff format --check`, `mypy src`,
  `pytest tests/test_video_script_check.py tests/test_readme_check.py` (44), `readme_check.py` OK
  y `video_script_check.py` OK (lo que corre el paso nuevo de CI). **Para Javier:** leer el guion
  en voz alta y cronometrar; si pasa de 60 s, recortar la fila 6 o la 11 (el gate avisa si cambia
  el recuento).
  Corrección (2026-10-24), commit `f006d07`: la frase 12 decía "one match builds in about 9
  seconds" sin decir dónde (el jurado señaló lo mismo en el README); ahora "Code and protocol are
  on GitHub, whose runners build one match in about 9 seconds". 148 palabras habladas, 59 s;
  gate (`words: 148 (max 150), 59 s`, `video_script_check: OK`, ruff, format, `mypy src`, los 44
  tests, `readme_check` OK) en verde.
- [ ] J6. **[Javier]** `ac2-football` público (si no lo era; la base lo es desde J2); `full-build`
  en verde del commit entregado y el tag de la base que fija `uv.lock` presente en el repo público.
- [ ] J7. **[Javier]** Grabar el vídeo con su voz (máximo 1 minuto) y subirlo a YouTube
  (visibilidad: las bases no la fijan; leídas el 2026-10-25 en el bundle de
  pysport.org/analytics-cup, "Submission Requirements": "A YouTube video of at most one minute
  summarising and elevator-pitching your project, presented and voiced by you or your teammate";
  público o no listado lo ve quien tenga el enlace, privado no). La misma fuente da la final el
  "17 or 24 February", no solo el 17.
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

- [x] V. Verificación. Gate en los dos repos, cada uno desde su raíz, en este orden (en la base,
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
  figuras sin un artefacto de `reports/` que lo imprima; `protocol.json` en `dead` con D5
  registrado (rama B) y `layer2.json` en `read`, con su historia en git; ninguna ruta pública lee el
  reservado fuera del guard; cada test nuevo con su mutación anotada; las cifras de m10 y m11
  re-derivadas por la 12 y la 15 o este plan corregido. Revisión adversarial (`revisor-adversarial`)
  de todo `ac2-football` (sin commit de importación: todo es nuevo) y del diff de la base desde su
  importación (`git diff <import>..HEAD` en `ftbase`), repetida sobre los arreglos hasta que no
  salga nada alto ni medio.
  **Decisión de Javier (2026-10-24): Fable** (`model: fable`) en la revisión adversarial de V y
  en sus pasadas, en una simulación del jurado (un lector con solo las bases y el repo puntúa la
  entrada) antes de cerrar el README, y en la 33 y la 34; Sonnet en lo mecánico.
  Para la revisión de V, tolerancias de `readme_check` (31) que conviene juzgar: un número sin
  signo casa con la magnitud (el README dice 0.19 y el efecto es -0.19268), "8 of 10" acepta dos
  recuentos, se aceptan sumas de claves (10 + 10 = 20), y la frase de los fixtures sintéticos es
  la del borrador actual. Y del clip (32): `ci.yml` instala ffmpeg (los tests del vídeo lo
  necesitan, sin skip), la etiqueta "121.4 s" es real pero llamativa, texto en inglés y
  "defenders" incluye al portero.
  **Revisión V, pasada 1 (2026-10-24, Fable)**, tres frentes, ningún alto. Arreglos, commits
  `1440af3`, `379c672`, `63e135e`, `10b42de`, `3877644` y el de este registro; sin push.
  Medios: (1) la línea del reservado del README lleva `--expect-diff
  scripts/heldout_linux_diff.txt` (en Windows, sin la opción). (2) Los "9 s" del README y de la
  frase 12 del guion se dicen con el entorno ya instalado; el guion queda en 150 palabras y 60 s
  (dos palabras recortadas en las frases 2 y 6; la línea declarada y el tiempo de la 12 al día).
  (3) El error de relleno de la altura de línea va sobre las dos mitades, 0,79 a 1,39 m (los dos
  extremos están en calibración, `series.65`; el reservado, `series.67`, queda dentro: 0,90 a
  1,20 m; el `note` del sidecar lo dice), como el "+7 to +14 m" de la misma frase. (4) Las tiras
  de la figura 1 se anclan en 0 en los dos paneles (`_strip_xlim`, un solo sitio): regenerada
  `fig1_layer2.svg` (el sidecar no cambia, `figures --check` OK); test nuevo del ancla, y la
  mutación de quitarla cae (`mutate_anchor.py`, scratchpad: límite inferior 0,764 > 0); las frases
  del README ("filling costs little") y del guion (frase 6, "both near zero") siguen siendo
  ciertas y ahora se ven. (5) `verdict.about` de `protocol.json` nombra `aa1edf9` y `10b2820`
  (seis textos con "in the period of t" tras `calibration.json`, `a0a3b68`, regenerado en
  `c0eefa9`); un recorrido del JSON entre `a0a3b68` y `10b2820` da 6 hojas distintas, 0 numéricas:
  ningún umbral ni constante cambió. Ningún test fijaba la frase; `protocol --check` OK (99
  campos, 32 reglas, 27 constantes) y `test_protocol.py` en verde. Bajos: (6) frase en el
  registro de J4 sobre los runs rojos 40025760773 y 40026089602 y el arreglo `2c4e4e7`. (7) README:
  ffmpeg para `ac2fb clip` y los tests; la base citada con su commit `53080bc`; "about 3 min"
  dicho con los datos en caché; "any match but the held-out, which stays closed". La frase de los
  fixtures sintéticos frente a `examples/sensitivity.py`: sin contradicción (el ejemplo construye
  su partido en memoria, no es un fixture de tests, y etiqueta sus cifras "not findings"; la frase
  habla de figuras del README), así que no se toca. (8) El patrón de años de `readme_check`
  admite solo temporadas (`2024/25`) o un año tras un mes (`October 2026`); un `2026` suelto o
  `2024/2025` necesitan fuente; test ampliado. No hecho, aceptado por escrito: el enmascaramiento
  por `.gitignore` del código congelado (manipulación local deliberada, fuera del alcance de la
  puerta). Recuento doble del README: `readme_check` 950 palabras y `wc -w README.md` 950.
  Puertas: ruff, format, `mypy src`; `readme_check: OK` (77 números, 56 iguales, 7 solo CI, 14
  permitidos, 0 fallos); `video_script_check: OK` (12 filas, 150 palabras, 60 s, 12 números, 0
  fallos); `figures --check` OK (594 valores, 7 etiquetas); `protocol --check` OK; pytest de
  `test_figures.py` (31), `test_readme_check.py`, `test_video_script_check.py` y
  `test_protocol.py` (136). Bloques de código del README idénticos a `HEAD`; LF en los cuatro
  ficheros editados.
  **Revisión V, pasada 2 (2026-10-25, Fable)**: ningún alto, un medio, tres bajos. Commits
  `ef17f9d` (README y sidecar), `b2e7839` (`readme_check` y su test), `3b882a5` (guion, su gate y
  su test) y el de este registro; sin push. Medio: la pasada 1 había borrado la única frase del
  README que apuntaba a `protocol/` (y su registro no lo decía); la regla de muerte nombra ahora
  `protocol/protocol.json`, "committed before any outcome". Bajos: el bloque completo dice "about
  3.5 min" (202 s en el run 40117288163 y 207 s en el 40136059795, los dos con caché; la entrada
  del sidecar cita ambos); los "9 s" del README y de la frase 12 del guion se dicen "with the
  packages cached" (el bloque cronometrado incluye `uv sync --locked` y la descarga; lo que el
  runner tiene es uv, Python y la caché de ruedas); el guion queda en 149 palabras y 60 s;
  `readme_check` exime un número solo si la coincidencia permitida cubre todo su tramo
  (`2026/10/24` ya no pasa como temporada; caso añadido al test), y el mismo arreglo, con su caso,
  en `video_script_check.py`, que tenía la misma comprobación de solo el inicio. Recuento doble
  del README: 955 y 955. Puertas: ruff, format, `mypy src`; `readme_check: OK` (77 números, 0
  fallos); `video_script_check: OK` (149 palabras, 60 s, 12 números, 0 fallos); pytest de
  `test_readme_check.py` y `test_video_script_check.py` (44).
  **Pasada 3 (2026-10-25)**, en la sesión principal y sin subagente, por tamaño: el diff de los
  arreglos de la pasada 2 (`ef17f9d^..3b882a5`, 15 líneas añadidas y 12 quitadas); nada alto ni
  medio. **Puerta local completa (2026-10-25)**, los dos repos desde su raíz (`gate.sh` en el
  scratchpad): base en `53080bc` (= `v0.1.0`), `uv sync --locked`, ruff, format, `mypy src`,
  pytest (35 s) y `ftbase provenance --check`, todo con salida 0; entrada en `239f305`, lo mismo
  más `readme_check` OK, `video_script_check` OK, `clean_clone_check.sh quick` con `AC2_REPO`
  local (53 s) y pytest `1696 passed, 68 deselected in 2287.67s`. Estáticos: `uv.lock` fija
  `ftbase` a `git+...?tag=v0.1.0#53080bcc...`, sin `path`; `src/ac2fb/base/` no existe;
  `LICENSE.md` en los dos repos; `protocol/protocol.json` en `dead` con `verdict.criterion` D5 y
  rama B; `protocol/layer2.json` en `read`. CI de la base en verde sobre `53080bc` (run
  39127612460). Tras los arreglos del jurado 2 (tarea 33), sobre `803896d`: CI run 40189342879 en
  verde; `full-build` run 40189351880 en verde (bloque rápido 9 s, completo 202 s, `heldout: OK`
  con exactamente la diferencia fijada); macOS run 40189349695 en verde (`macos-26-arm64`, `1696
  passed, 68 deselected in 441.63s`, bloque rápido `CLEAN CLONE OK in 8 s`, 95.624.493 B), así
  que el README dice ahora "GitHub's Linux and macOS runners" (997 palabras). El reservado en
  macOS no se ha reproducido (el flujo no lo corre). El error de
  `tests/test_clip.py::test_the_rule_ranks_by_the_number_of_extrapolated_rivals_before_their_gap`
  en el worktree del agente (pasa solo; había dos suites a la vez en la máquina, con poca memoria)
  no se repite en la CI de Linux ni en la de macOS. Sin revisión adversarial de los arreglos del
  jurado 2, a sabiendas: son texto, una etiqueta de figura y un flujo manual; cada propuesta se
  contrastó con su artefacto (el D3, también en la sesión principal) y los checkers los cubren.
  **Cerrada para el estado actual.** El commit que se entregue vuelve a pedir `full-build` en
  verde (J6).
