# INFORME C-R1 — RECTIFICACIÓN 6G.1 (ABORTO SIN ELIMINACIÓN DE ARCHIVOS)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**Commit anterior (base obligatoria)**: `71cfe4cf8b939ce5180dbdb3123c1694a0291312` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente la seguridad de limpieza de `abortar_6g1()`. Sin cambios DSP; sin tocar motores de 6G, `main` ni la rama de referencia; sin repetir baterías históricas.

> **Estado**: ENTREGADA, **NO CERRADA**. La aprobación final corresponde a Cris tras la auditoría independiente.

---

## 1. Hallazgo confirmado

En `abortar_6g1()` la comprobación (`os.lstat` + dictamen de propiedad) y la eliminación (`os.unlink`) eran **operaciones separadas**: un proceso concurrente podía sustituir el archivo entre ambas y el `unlink` habría borrado el sustituto ajeno. Las baterías previas probaban sustituciones *anteriores* al aborto, no esa ventana.

## 2. Solución aplicada (la preferida por la instrucción)

**El aborto ya no elimina ningún archivo.** En `motores/lectura_segura_6g1.py` (+43/−18):

1. Eliminada la rama `os.unlink` (única llamada de borrado del módulo; verificación estática: 0 `os.unlink`/`os.remove`/`os.rmdir` en código).
2. Las salidas propias **registradas** por la corrida quedan **invalidadas y conservadas** en el provisional (motivo `salida_parcial_invalidada_y_conservada (sin eliminación; C-R1)`); el dictamen de propiedad se usa **sólo para clasificar y registrar**, nunca como decisión de borrado → la ventana TOCTOU del hallazgo deja de existir **por construcción**.
3. `ABORT_6G1.json` registra qué resultados quedan invalidados; creación **exclusiva y no-follow** mantenida (`O_CREAT|O_EXCL|O_NOFOLLOW` + `dir_fd`); `analysis.json` permanece intacto (E-R2 se mantiene).
4. **Distinción clara de resultados**: schema versionado a **`abort-6g1/3`** con `estado_salidas_invalidadas: 'conservadas en el provisional; sin eliminación (C-R1)'` y `resultados_validos: []` (siempre vacío en un aborto). Un directorio con `ABORT_6G1.json` nunca es una corrida exitosa: la publicación sólo ocurre por `publicar_dir_6g1` en la ruta de éxito tras la guarda, y los traslados de aborto usan nombres `_aborted*` (G/G-R1) — verificado estática y dinámicamente (e2e: exit 2, 0 directorios definitivos).
5. **Sin patrones de nombre** para decidir borrados (no hay borrados; verificación estática: sin `fnmatch`).
6. Clasificación por identidad del registro: una salida propia **sustituida** durante la corrida se clasifica `identidad_distinta` y queda en `conservados` (su contenido real —el ajeno— permanece intacto); la propia no sustituida queda en `salidas_invalidadas`.

### Versionado del esquema y consumidores

El significado de `salidas_invalidadas` cambió (de «eliminados» a «conservadas-invalidadas») → **`abort-6g1/3`**. Consumidores actualizados en **compatibilidad de lectura** (`in ('abort-6g1/2', 'abort-6g1/3')`, con comentario `[6G.1-R/C-R1]`): `pruebas_correccion_6g1.py` (2 sitios) y `pruebas_e_r2_6g1.py` (3 sitios). Esos arneses son **evidencia histórica cerrada** (de las baterías 34 y 12): **no se re-ejecutaron** y sus aserciones semánticas (p. ej. eliminación esperada en UC4 de la batería 34) corresponden a la semántica `/2` que probaron en sus bases; **no deben utilizarse como pruebas de aceptación de `abort-6g1/3` sin actualización** — sus registros históricos permanecen válidos para sus commits. [Señal reforzada en la rectificación C-R1-R.] El resto de arneses (26/17) y el código de producción no consumen el literal del schema. Documentación: docstrings del módulo (`propiedad_de_6g1` y `abortar_6g1`) y este informe.

## 3. Batería focalizada — 13/13 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_c_r1_6g1.csv` · detalle por check: `evidence/pruebas_c_r1_6g1.json`. Verificación sobre **archivos reales en disco** (bytes, SHA-256, existencia), no sólo códigos de salida.

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| CR1a | Salidas propias parciales **conservadas** tras el aborto (bytes intactos); `salidas_invalidadas` las registra; `estado_sin_eliminacion`; `resultados_validos == []`; schema /3 | PASS |
| CR1b | Ajenos byte a byte intactos —incluidos nombres tipo salida y `candidates_*`—; en `conservados` con `ajeno_no_registrado`; fuera de `salidas_invalidadas` | PASS |
| **CR1c** | **La ventana histórica exacta del hallazgo** [C-R1-R]: se intercepta `propiedad_de_6g1()`; se ejecuta la función original y se obtiene su dictamen; **inmediatamente después de un dictamen positivo** se sustituye el archivo por otro regular (`os.replace()`) y se devuelve el dictamen **original** al llamador — demostrando que la sustitución ocurrió **después del dictamen y antes de que el llamador continuara** (con el código anterior a C-R1, el `unlink` posterior habría borrado al sustituto ajeno): el sustituto queda byte a byte intacto; nada se elimina; la clasificación del archivo en `ABORT_6G1.json` se basa en el dictamen obtenido **antes** de la sustitución (el motivo registrado no afirma la identidad posterior) | PASS |
| CR1d | Enlaces simbólicos conservados, nunca seguidos; objetivo externo intacto | PASS |
| CR1e | `ABORT_6G1.json` registra las invalidadas; exclusividad mantenida (colisión conservada, info /3 completa en el retorno) | PASS |
| CR1f | `analysis.json` byte a byte y `mtime` intacto (E-R2 se mantiene) | PASS |
| CR1-estático | 0 `os.unlink`/`os.remove`/`os.rmdir` en el módulo (sólo la mención documental del hallazgo); schema `/3` en código; `estado_salidas_invalidadas` y `resultados_validos` presentes; sin `fnmatch` | PASS |
| CR1-e2e ×3 | Aborto real (guarda final, plantado determinista en los tres motores): exit 2; **0 directorios definitivos** (item 6); salidas propias **conservadas en disco**; la salida reemplazada por el ajeno plantado conserva el contenido ajeno byte a byte (item 3) y queda en `conservados` con `identidad_distinta`; la salida propia no reemplazada queda en `salidas_invalidadas`; enlace plantado conservado con objetivo intacto; `ABORT_6G1.json` /3 con `estado_sin_eliminacion` y `resultados_validos == []`; `analysis.json` parseable, sin `abort_6g1`, sin truncar (fail-closed mantenido, item 8) | 3× PASS |
| sanidad ×3 | Corrida feliz: exit 0, publicación única, integridad True, **PCM idéntico a la campaña auditada** (DSP intacto) | 3× PASS |

**Registro de iteración**: primera ejecución 10/13 — las 3 fallas eran de aserción del arnés (esperaba la salida *reemplazada* en `salidas_invalidadas`; el diseño correcto la clasifica en `conservados` con `identidad_distinta` porque su inodo ya no coincide con el registro). Asértion corregida; ejecución 13/13. Ningún cambio de código del módulo tras la primera ejecución.

**Rectificación de evidencia [C-R1-R] (a petición de Cris)**: el mecanismo de inyección de CR1c fue sustituido por el de la ventana histórica exacta (intercepción de `propiedad_de_6g1()`, sustitución por `os.replace()` tras el dictamen positivo y antes de devolverlo al llamador; sin modificar el módulo de producción). Re-ejecutada exclusivamente la batería C-R1 focalizada: **13/13 PASS** con el nuevo mecanismo; JSON/CSV de evidencia regenerados. Detalle en `INFORME_RECTIFICACION_CR1C_6G1.md`.

## 4. SHA-256 de los archivos modificados

`SHA256SUMS_C_R1.txt` (6 ficheros, con SHA previo en comentario; verificado con `sha256sum -c`: 6/6 OK). Diff incremental respecto de `71cfe4cf…`: `DIFF_6G1_C_R1.patch` (1.007 líneas; **reversible verificado**: `patch -R -p1` devuelve el árbol base byte a byte — `diff -r` sin diferencias; forward dry-run exit 0). Superficie de trabajo (sin entregables auto-referentes): **+885/−23** (módulo +43/−18; compatibilidad consumidores +7/−5; batería nueva 538 L; evidencia 295 L).

## 5. Limitaciones y límites respetados

- Los archivos parciales conservados ocupan espacio en disco (antes se eliminaban); el provisional/`_aborted` conserva ahora todo el trabajo de la corrida abortada — decisión de seguridad asumida por la instrucción.
- Los arneses históricos 34 y 12 quedan atados semánticamente a `/2` (registro histórico; sólo su lectura de versión es compatible `/3`).
- Sin cambios en STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP (sanidad ×3 con PCM idéntico a la campaña auditada); motores originales de 6G, `main` y `arena/89d5c189-sdv-sdi-sgm` intactos; sin canciones reales ni Elis/Tristania; sin Android/Termux; baterías históricas no repetidas; sin fusionar ramas ni abrir PR; rama de sesión autorizada únicamente.
- **No se declara 6G.1 cerrada.**

## 6. Identificación exacta de commits

- **Commit anterior (base)**: `71cfe4cf8b939ce5180dbdb3123c1694a0291312`
- **Nuevo commit (esta entrega)**: ver sección 8 y el informe de ejecución (padre directo verificado)

## 7. Enlaces (URLs completas)

Informe C-R1 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_C_R1_6G1.md

Diff incremental vs 71cfe4c (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_C_R1.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_C_R1.txt

Matriz C-R1:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_c_r1_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_c_r1_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
