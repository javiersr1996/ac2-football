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
- [ ] 22. `opus` (subagente `revisor-adversarial`) Revisión del protocolo, el estimador y la
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
    `review22_p5/alt/test_mixed_alt.py`). **Lo decide Javier.**
  - *El requisito de `make_metric` solo estaba en la 22:* diferirlo es aceptable (no alimenta D1
    a D5 y sus dos mutaciones tumban `test_realdata_s1`, `real_metric_s1.log`), pero pasa a la
    aceptación de la 25.
- [ ] 23. `sonnet` Congelación en un commit propio: `stage: "frozen"`, `code_tree_sha`, semilla,
  umbrales. Aceptación: desde ese commit hasta la lectura, `git diff <congelación> -- src
  pyproject.toml uv.lock .python-version protocol/` vacío (revisión 18: el sha cubre ya todo
  `src`, la puerta y el CLI incluidos, y los pines de la base, las librerías y el intérprete);
  test contra `HEAD` que el reservado sigue cerrado con un cambio de código posterior.
  **Requisito de la revisión 18, una sola lectura por código y no solo por procedimiento:** hoy
  la puerta abre en `frozen` tantas veces como se pida (`OPEN_STAGES`). La 23 escribe `ac2fb
  heldout read` (el comando que lanza J4) y hace que, en `frozen`, el reservado solo se abra
  dentro de ese comando, que registra la lectura (commit con `stage: "read"`, el sha de la
  congelación y los ids leídos) antes de dar ninguna cifra; y que en `read` solo se reproduzca
  con el mismo `code_tree_sha`. El sha congela `uv.lock`, no el entorno instalado: `ac2fb heldout
  read` compara las versiones instaladas (`importlib.metadata`) con las de `uv.lock` antes de
  abrir y se niega si alguna difiere. Aceptación: test de que una segunda apertura en `frozen`
  fuera del comando falla, test de que una versión instalada distinta de la del lock cierra la
  lectura, y mutaciones anotadas (la puerta que abre en `frozen` sin registrar la lectura; la
  lectura que no compara las versiones).
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
  coinciden con las de la 12; mutación anotada. Antes de abrir el reservado (revisión 22,
  pasadas 2, 4 y 5): test de `pressure.make_metric` y de toda métrica nueva que lea
  `attack_sign`, con portadores de los dos equipos en los dos periodos y moviendo también la
  tabla larga; y decidida la tolerancia de `index >= PRESSED_INDEX` y de `weights > 0`.
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
