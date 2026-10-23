# Lecciones de ac2-football

Máximo 30 líneas (heredadas de tracklab el 2026-10-17); al tope, consolidar o archivar.

- **Reportar el número por partido y reservar el veredicto.** Nunca el agregado donde cabe la
  tabla de 10 filas por mitad: un bundle que parece homogéneo esconde particiones.
- **Ninguna cifra en prosa sin un artefacto que la imprima** (README, guion, figura, plan), y el
  artefacto en el repo: un log del scratchpad muere con la sesión (los recuentos de la 26 ya no se
  reproducen). Las cifras de un plan son hipótesis hasta medirlas, también las del sintético.
- **Un test que pasa por construcción no protege nada** (INNER JOIN que descarta, fichero
  comparado consigo mismo, margen de sintético que es ruido, sintético que no distingue la clave,
  aleatorio que nunca cae en un corte: cada umbral, su caso plantado). Mutar y ver fallar; varias
  semillas; anotar la mutación; mutar desde una copia (`git checkout` borra lo no commiteado).
- **Un guard sobre una función no guarda los datos.** Una sola lectura del reservado, guardada;
  una sola puerta a los datos; test de comportamiento sobre toda ruta pública; lo que leerá el
  reservado, escrito y congelado antes. Si el guard lee git: lo ya hecho se busca en todas las
  refs y padres (`--all --full-history`), el estado se ancla en la historia simple de `HEAD`.
- **El revisor adversarial antes de cada checkpoint y antes de congelar**, y otra vez sobre sus
  arreglos, hasta que no salga nada alto ni medio. El arreglo va al bloque canónico del plan, y
  con el test del camino legítimo que debe seguir abierto (23c: dos endurecimientos rompían uno).
- **Un solo agente escribiendo en el árbol** (en tracklab dos en paralelo borraron 2,8 GB de
  datos). Paralelo solo para leer o en worktrees separados. Nadie escribe en tracklab.
- **Todo escritor de texto fija LF**: un CRLF, invisible en Windows, ensucia el clon de Linux.
- **Que pase en local no dice que quepa en CI**, y un skip silencioso esconde fallos. Todo
  `--check` sobre fixtures dice cuánto verificó.
- **El instante que da el proveedor puede no ser el causal, y el balón es la causa común** (P5:
  `frame_start` con el corredor ya a 4 m/s; C2: presionado tras balón hacia delante, la línea ya
  seguía al balón, 10 de 10). Medir la cinemática previa y estratificar por el balón entrante
  antes de fijar la causa.
- **Tras editar `todo.md`, comprobar la forma** (`wc -l`, encabezados, `git diff --stat`).
