# Lecciones de ac2-football

Máximo 30 líneas. Heredadas de tracklab el 2026-10-17 y adaptadas; al llegar al tope, se
consolida o se archiva en `lessons-archive.md`.

- **Reportar el número por partido y reservar el veredicto.** Nunca el agregado donde cabe la
  tabla de 10 filas por mitad: un bundle que parece homogéneo esconde particiones.
- **Ninguna cifra en prosa sin un artefacto que la imprima** (README, guion, figura, plan). Las
  cifras de un plan son hipótesis hasta medirlas, también las del sintético.
- **Un test que pasa por construcción no protege nada** (INNER JOIN que descarta, fichero
  comparado consigo mismo, margen de sintético que es ruido, sintético que no distingue la clave,
  aleatorio que nunca cae en un corte: cada umbral, su caso plantado). Mutar y ver fallar; varias
  semillas; anotar la mutación; mutar desde una copia (`git checkout` borra lo no commiteado).
- **Un guard sobre una función no guarda los datos.** Una sola lectura del reservado, guardada;
  una sola puerta a los datos; test de comportamiento sobre toda ruta pública; lo que leerá el
  reservado, escrito y congelado antes.
- **El revisor adversarial antes de cada checkpoint y antes de congelar**, y otra vez sobre sus
  arreglos, hasta que no salga nada alto ni medio. El arreglo va al bloque canónico del plan.
- **Un solo agente escribiendo en el árbol** (en tracklab dos en paralelo borraron 2,8 GB de
  datos). Paralelo solo para leer o en worktrees separados. Nadie escribe en tracklab.
- **Todo escritor de texto fija LF**: un CSV con CRLF, invisible en Windows, ensucia el árbol en
  el clon limpio de Linux.
- **Que pase en local no dice que quepa en CI**, y un skip silencioso esconde fallos. Todo
  `--check` sobre fixtures dice cuánto verificó.
- **El instante que da el proveedor puede no ser el causal, y el balón es la causa común** (P5:
  `frame_start` con el corredor ya a 4 m/s; C2: presionado tras balón hacia delante, la línea ya
  seguía al balón, 10 de 10). Medir la cinemática previa y estratificar por el balón entrante
  antes de fijar la causa.
- **Tras editar `todo.md`, comprobar la forma** (`wc -l`, encabezados, `git diff --stat`): un Edit
  puede duplicar bloques enteros.
