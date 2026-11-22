# INFORME H1-R2 — RECTIFICACIÓN 6G.1 (CIERRE DE DOS BRECHAS DE ANCLAJE)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD obligatorio de partida**: `f54ceb532b4e6a38410cfedfe35dfd2bb5c4ff1d` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente los dos hallazgos (H1-R2-A, H1-R2-B) y sus pruebas. Sin cambios DSP; motores originales de 6G, `main` y rama de referencia intactos; baterías históricas 34/26/17/12 no repetidas.

> **Estado**: ENTREGADA, **NO CERRADA**. No se declara H1 cerrada ni 6G.1 aprobada: la aprobación requiere una nueva auditoría independiente de Cris.

---

## 1. H1-R2-A — Acreditación segura desde la creación

**Brecha**: `create_run_dir()` ejecutaba `os.mkdir(partial_dir)` y luego `_acreditar_dir_6g1(partial_dir)` (identidad por `os.lstat` de la ruta): entre ambas, una sustitución de la ruta podía registrar la identidad de un impostor.

**Solución** (nueva función pública `crear_y_acreditar_dir_6g1(padre, nombre)`; aplicada en **Hardened, EVO y MQR**):

1. **Padre evaluado y asegurado**: se abre de forma segura (`O_DIRECTORY | O_NOFOLLOW` — un enlace en la ruta del padre no se sigue) y se verifica la condición de privacidad: **propiedad del euid** y **sin permisos de escritura para grupo/otros** («privado y no modificable por terceros»). Si no se cumple, **no se crea nada y se eleva `RuntimeError`** (fail-closed: los motores abortan sin crear corrida).
2. **Creación por descriptor**: `os.mkdir(nombre, 0o700, dir_fd=fd_padre)` — exclusiva respecto del padre **validado** y modo privado para el provisional.
3. **Acreditación por descriptor**: apertura del provisional **relativa al padre validado** (`O_NOFOLLOW`, `dir_fd`) e identidad por **`fstat`** — la identidad registrada es la del objeto creado dentro del padre validado, no la de una re-consulta por ruta. La ventana POSIX residual entre `mkdir` y la apertura (sólo alcanzable por procesos de la misma uid) queda cubierta por la condición del padre verificada en el paso 2 (modelo de amenaza documentado en el docstring).
4. La identidad `(st_dev, st_ino)` queda **vinculada a la corrida** (`_DIR_6G1`, limpiada por `reiniciar_registro_6g1()`); `_anclar_dir_aborto_6g1` (H1) la verifica al abortar. `acreditar_dir_6g1()` (por ruta) queda documentado como mecanismo de arneses de pruebas; la producción usa el nuevo.
5. Los motores llaman al nuevo mecanismo dentro de su bucle anti-colisión (F intacto: `FileExistsError` → sufijo; la denegación por padre no conforme propaga y aborta sin crear nada).

## 2. H1-R2-B — Inventario exclusivamente mediante descriptores

**Brecha**: el recorrido usaba `fd_base`, pero la clasificación re-consultaba la ruta absoluta (`propiedad_de_6g1(os.path.join(str(run_dir), rel))`), que además volvía a hacer `lstat` por ruta: contradecía el anclaje y abría una consulta post-acreditación por ruta.

**Solución** (nuevas `_clasificar_entrada_6g1(nombre, st, fd_dir, ruta_esperada)` y `_sha_via_descriptor_6g1(nombre, fd_dir, st)`):

- La clasificación se hace **por identidad del descriptor**: `(st_dev, st_ino)` del `lstat` relativo (`os.lstat(nombre, dir_fd=fd_base)`) cotejado contra el registro de la corrida; **sin seguir enlaces**.
- El **SHA-256** se calcula abriendo el archivo con `dir_fd` + `O_NOFOLLOW`, verificando por `fstat` la misma identidad y re-verificando tamaño/mtime tras la lectura (sin rutas).
- `ruta_esperada` se usa **sólo como clave de comparación del registro** (para distinguir un *sustituido* de un *ajeno* y conservar los motivos C-R1: `identidad_distinta`, `ajeno_no_registrado`) — **nunca para re-consultar el sistema de archivos** (verificado estáticamente: 0 `propiedad_de_6g1(os…` en el módulo).
- **Registro dinámico del motor** (`estable=False`, salidas en escritura): la propiedad se acredita **por identidad**, igual que la semántica C-R1 de `propiedad_de_6g1` (el sello sólo se exige en `estable=True`); detectado y corregido durante la regresión e2e (primera ejecución: salidas → conservadas por «registro no sellado»; corrección aplicada y re-regresión verde).
- **Garantías C-R1 intactas**: nada se elimina; las propias se invalidan y conservan; los motivos se mantienen; `propiedad_de_6g1()` permanece como API de dictamen por ruta (arneses históricos de prueba).

## 3. Invariantes preservadas

C-R1 (cero eliminaciones) · E-R2 (`analysis.json` intacto) · parciales conservados · `resultados_validos: []` en abortos · `ABORT_6G1.json` con creación exclusiva + `O_NOFOLLOW` + `dir_fd` · schema **`abort-6g1/3`** sin cambios incompatibles · DSP original de los tres motores sin alteración.

## 4. Pruebas focalizadas y resultados

**Batería H1-R2 (nueva, `scripts/pruebas_h1_r2_6g1.py`): 4/4 PASS, 0 FAIL, 0 NOT_EXECUTED** (`evidence/matriz_h1_r2_6g1.csv`; detalle: `evidence/pruebas_h1_r2_6g1.json`):

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| **A1** | Creación+acreditación por descriptores: provisional creado (modo 0o700) dentro del padre validado; identidad acreditada == identidad de una apertura independiente `O_NOFOLLOW`; vinculada a la corrida (anclaje OK) | PASS |
| **A2** | Sustituto en la ruta tras la acreditación (impostor con señuelo): **nunca acreditado como provisional legítimo** — aborto por esa ruta fail-closed (`identidad_distinta`), **sin ABORT en el impostor**, señuelo byte a byte intacto, nada eliminado, sin salidas válidas; el provisional acreditado (vivo, movido aparte) sigue vinculado | PASS |
| **A3** | Padre **no conforme** (g+w, modificable por terceros): el mecanismo **se niega** (RuntimeError «modificable por terceros»), **sin crear y sin acreditar nada** | PASS |
| **B1** | Sustitución de la ruta **después de abrir y validar el descriptor y antes de clasificar** (impostor con señuelo de contenido distinto): el ABORT aterriza en el **original vía descriptor** (en donde quedó el objeto abierto), `directorio_acreditado=True`, la clasificación corresponde al original (`salida.wav` invalidada aunque la ruta ya apuntaba al impostor), **sin consulta del árbol externo** (señuelo byte a byte, sin ABORT en el impostor), ajeno del original intacto, nada eliminado | PASS |

**Regresiones focalizadas (ejecutadas tras los cambios)**: batería **H1** (H1a/H1b/H1c + **los tres flujos de aborto** e2e + sanidad ×3): **10/10 PASS**; batería **C-R1** (con el gancho de la ventana histórica actualizado al mecanismo por descriptor — dictamen original → `os.replace` → devolución): **13/13 PASS**. Evidencia regenerada (`pruebas_h1_6g1.json/csv`, `pruebas_c_r1_6g1.json/csv`). Baterías históricas 34/26/17/12: no ejecutadas.

**Registro de iteraciones** (ninguna de diseño tras la corrección de la primera): (1) A2 usaba `shutil.move` sobre una ruta ya renombrada → el impostor se crea directamente en la ruta; (2) A2 trataba la ruta del helper (`str`) como `Path` → `Path(ruta)`; (3) primera regresión e2e: salidas del motor → conservadas por «registro no sellado» → clasificación corregida al semántico C-R1 (identidad para registros dinámicos). Ejecución final: 4/4 + 10/10 + 13/13.

## 5. SHA-256, DIFF y commits

- `SHA256SUMS_H1_R2.txt` (12 ficheros con SHA previo en comentario; verificado con `sha256sum -c`: 12/12 OK).
- `DIFF_6G1_H1_R2.patch`: diff incremental **reversible** respecto de `f54ceb532b4e6a38410cfedfe35dfd2bb5c4ff1d` (`patch -R -p1` → árbol base byte a byte; forward dry-run exit 0).
- **Padre directo**: `f54ceb532b4e6a38410cfedfe35dfd2bb5c4ff1d` · **Nuevo commit**: hijo directo (SHA completo en el informe de ejecución y en §6 de este documento).

## 6. Identificación exacta de commits

- **Commit anterior (base obligatoria)**: `f54ceb532b4e6a38410cfedfe35dfd2bb5c4ff1d`
- **Nuevo commit (esta entrega)**: ver sección 8 y el informe de ejecución (padre directo verificado).

## 7. Límites respetados

Sin STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP (sanidad ×3 con PCM idéntico a la campaña auditada); motores originales de 6G y carpeta 6G de referencia intactos; `main` y otras ramas intactos; sin canciones reales ni Elis/Tristania; sin Android/Termux; baterías históricas 34/26/17/12 no repetidas; sin fusionar ramas ni abrir PR. **No se declara H1 cerrada ni 6G.1 aprobada.**

## 8. Enlaces (URLs completas)

Informe H1-R2 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H1_R2_6G1.md

Diff incremental vs f54ceb5 (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H1_R2.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H1_R2.txt

Matriz H1-R2:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h1_r2_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h1_r2_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
