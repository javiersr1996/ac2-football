# Lecciones de ac2-football

Máximo 30 líneas (heredadas de tracklab el 2026-10-17); al tope, consolidar o archivar.

- **Reportar el número por partido y reservar el veredicto.** Nunca el agregado donde cabe la
  tabla de 10 filas por mitad: un bundle que parece homogéneo esconde particiones.
- **Ninguna cifra en prosa sin un artefacto del repo que la imprima** (README, guion, figura,
  plan); un log del scratchpad muere con la sesión, y la cifra de un plan es hipótesis.
- **Un test que pasa por construcción no protege nada** (INNER JOIN que descarta, fichero
  comparado consigo mismo, margen de sintético que es ruido, sintético que no distingue la clave,
  aleatorio que nunca cae en un corte: cada umbral, su caso plantado). Mutar y ver fallar; varias
  semillas; anotar la mutación; mutar desde una copia (`git checkout` borra lo no commiteado).
- **Un guard sobre una función no guarda los datos.** Una sola lectura del reservado, guardada;
  una sola puerta a los datos; test de comportamiento sobre toda ruta pública; lo que leerá el
  reservado, escrito y congelado antes. Si el guard lee git: lo ya hecho se busca en todas las
  refs y padres (`--all --full-history`), el estado se ancla en la historia simple de `HEAD`.
- **El revisor adversarial antes de cada checkpoint y antes de congelar**, y otra vez sobre sus
  arreglos hasta que no salga nada alto ni medio; cada propuesta suya (o del jurado) se contrasta
  con el artefacto antes de aplicarla, y el arreglo lleva el test del camino legítimo (23c).
- **Un solo agente escribe en el árbol** (en tracklab dos borraron 2,8 GB; nadie escribe en
  tracklab); paralelo solo para leer. Un subagente no despierta con sus procesos de fondo: que los
  sondee él; si queda inactivo sin informe, su último texto está en `subagents/agent-*.jsonl`.
- **Todo escritor de texto fija LF** (un CRLF ensucia el clon de Linux); tras editar `todo.md`,
  comprobar la forma (`wc -l`, encabezados, `git diff --stat`).
- **Que pase en local no dice que quepa en CI ni en otro sistema**; un skip silencioso esconde
  fallos y todo `--check` dice cuánto verificó. `np.hypot` (libm) no redondea igual en Windows y
  glibc (`scripts/hypot_platform_probe.log`; `sqrt` sí): un valor en el borde de un bin cambia de
  banda. Código nuevo, `sqrt`; el congelado, diferencia fijada exacta (28).
- **El instante del proveedor puede no ser el causal, y el balón es la causa común** (P5, C2):
  medir la cinemática previa y estratificar por el balón entrante antes de fijar la causa.
