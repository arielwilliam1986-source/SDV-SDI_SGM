# INFORME H1-R2-R2 — RECTIFICACIÓN 6G.1 (APERTURA SEGURA FRENTE A FIFO)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD obligatorio**: `cda43639df114450424eb4b466a57e99c30259ec` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente la apertura de `_sha_via_descriptor_6g1()` y su prueba determinista. Sin cambios DSP; motores (los tres y los originales de 6G), carpeta de referencia, `main` y otras ramas intactos; A1/A2/A3/B1, H1, C-R1 y H1-R2-R1 sin alterar; baterías históricas 34/26/17/12 no repetidas.

> **Estado**: ENTREGADA, **NO CERRADA**. No se declaran H1 ni 6G.1 cerradas: la aprobación final corresponde a Cris y depende de auditoría independiente.

---

## 1. Hallazgo y corrección

La apertura de `_sha_via_descriptor_6g1()` usaba `os.O_RDONLY | os.O_NOFOLLOW`: existía una **ventana entre el `lstat()` previo y `os.open()`** — si una entrada regular era sustituida por una **FIFO**, la apertura de sólo lectura podía **bloquearse** (esperando un escritor) antes de que el `fstat()` comprobara el tipo de archivo.

**Corrección** (únicamente la apertura, +9/−3): se incorpora **`os.O_NONBLOCK`** manteniendo `O_NOFOLLOW`, `dir_fd`, el descriptor anclado, la comprobación `fstat()` de archivo regular, la comparación de identidad contra el `lstat` previo, el SHA-256 incremental, el segundo `fstat()` y la verificación de estabilidad (H1-R2-R1). Comportamiento **fail-closed** intacto: objeto no regular o identidad distinta → SHA **no acreditable** (`no_es_archivo_regular (H1-R2-R1)`), sin leer el objeto no regular y sin rutas alternativas. Con `O_NONBLOCK`, la apertura de la FIFO devuelve el descriptor al instante y el `fstat` posterior la clasifica como no regular — la ventana ya no puede bloquear la llamada. Compatible con Python 3.8.

## 2. Prueba determinista — 1/1 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_h1_r2_r2_6g1.csv` · detalle: `evidence/pruebas_h1_r2_r2_6g1.json`. Sustitución inyectada **en el punto exacto** entre la identificación inicial (lstat relativo al directorio anclado) y la apertura interna (envoltorio de `_sha_via_descriptor_6g1` que sustituye justo antes de delegar en la función original — no una FIFO preexistente al lstat):

1. Crea el archivo regular y su vecino ajeno; obtiene el `lstat` relativo (`S_ISREG` verificado).
2. Sustituye la entrada por una FIFO (`unlink` + `mkfifo` con `dir_fd`) tras la identificación y antes de la apertura.
3. Ejecuta la función bajo vigía temporal (`setitimer` 8 s, fail-safe anti-bloqueo).
4-7. Comprueba sobre el estado real en disco: **termina sin bloquearse** (sin vigía disparado, tiempo ≪ 5 s), **no devuelve SHA válido** (`sha is None`), el **motivo identifica el objeto como no regular** (`no_es_archivo_regular (H1-R2-R1)`), la entrada **sigue siendo FIFO sin contenido escrito por nadie** (lectura no bloqueante → vacía), el **vecino ajeno permanece byte a byte intacto** (sin eliminaciones) y el directorio queda sin entradas inesperadas (`['ajeno_vecino.txt', 'salida.wav']`).

**Regresiones autorizadas (sólo éstas)**: batería **H1-R2** (A1/A2/A3/B1 intactos): **4/4 PASS** · batería **H1**: **10/10 PASS** · batería **C-R1**: **13/13 PASS** (evidencias regeneradas). Baterías históricas 34/26/17/12: no ejecutadas. Sin cambios DSP (sanidad ×3 con PCM idéntico a la campaña auditada, incluida en la regresión H1).

## 3. SHA-256, DIFF y commits

- `SHA256SUMS_H1_R2_R2.txt` (**10 ficheros** — módulo, prueba focalizada y las 8 evidencias JSON/CSV de la batería nueva y sus regresiones — con SHA previo en comentario; verificado con `sha256sum -c`: **10/10 OK**). [Rectificación documental H1-R2-R2-R]: la versión anterior de esta línea indicaba «5 ficheros / 5/5» por un error de conteo en la redacción; el manifiesto publicado siempre contuvo las 10 entradas correctas y fue verificado 10/10 al generarlo y al rectificar este informe.
- `DIFF_6G1_H1_R2_R2.patch`: diff incremental **reversible** respecto de `cda43639df114450424eb4b466a57e99c30259ec` (`patch -R -p1` → árbol base byte a byte; forward dry-run exit 0).
- **Padre directo**: `cda43639df114450424eb4b466a57e99c30259ec` · **Nuevo commit**: hijo directo (SHA completo en el informe de ejecución).

## 4. Límites respetados

Sin modificaciones en motores ni parámetros DSP (la corrección es interna al módulo compartido, en la única apertura señalada); motores originales de 6G y carpeta de referencia intactos; `main` intacto; sin canciones reales ni Elis/Tristania; sin Android/Termux; sin fusionar, integrar ni abrir PR; A1/A2/A3/B1, H1, C-R1 y H1-R2-R1 sin alterar (la prueba nueva es un arnés independiente). **No se declaran H1 ni 6G.1 cerradas.**

## 5. Enlaces (URLs completas)

Informe H1-R2-R2 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H1_R2_R2_6G1.md

Diff incremental vs cda4363 (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H1_R2_R2.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H1_R2_R2.txt

Matriz H1-R2-R2:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h1_r2_r2_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h1_r2_r2_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
