# INFORME E-R1 / G-R1 — RECTIFICACIÓN 6G.1 (CORRECCIÓN PUNTUAL II)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**Base obligatoria respetada**: `2248e2e21e44b279d57f9d0163f3f11b474a75e2` (padre directo del commit de esta entrega)
**Alcance**: exclusivamente los dos hallazgos (E-R1, G-R1). A–D y F no se reabrieron ni rediseñaron; sin cambios DSP.

> **Estado**: ENTREGADA, **NO CERRADA**. La aprobación final corresponde a Cris.

---

## 1. E-R1 — Eliminación de la ventana TOCTOU al actualizar `analysis.json`

**Cambio** (`motores/lectura_segura_6g1.py`, bloque `analysis.json` de `abortar_6g1`, +36/−12):

- **Antes** (ventana): apertura de lectura (`O_RDONLY|O_NOFOLLOW`) → fstat/lectura/acreditación → **cierre** → **reapertura por nombre** (`O_WRONLY|O_TRUNC|O_NOFOLLOW`) → escritura. Entre el cierre y la reapertura, otro proceso podía sustituir el nombre por otro archivo regular (`O_NOFOLLOW` no impide esa sustitución) y el segundo `open()` truncaba un objeto nunca verificado.
- **Después** (sin ventana): el archivo se abre **una sola vez** con `os.O_RDWR|os.O_NOFOLLOW` anclado al `dirfd`; `fstat(fd)` verifica que es regular; la lectura, la acreditación (identidad, tamaño, `mtime_ns` y SHA-256 del contenido leído contra el registro sellado de la corrida, vía `_propiedad_fd_acreditada`) y la actualización (`os.ftruncate(fd,0)` + `os.lseek` + `os.write` + `os.fsync`) ocurren **sobre el mismo descriptor ya verificado**. No hay cierre ni reapertura por nombre entre verificación y escritura: una sustitución del nombre durante la operación no puede recibir la escritura — ésta sólo alcanza al objeto cuyo descriptor fue acreditado.
- **Fail-closed mantenido**: apertura fallida (ENOENT → nada que hacer; ELOOP/enlace, EACCES u otro → omitida con motivo), acreditación fallida → archivo conservado sin modificar con motivo (`propiedad no acreditada (…)`); cualquier excepción → motivo de fallo seguro. Claves de motivo separadas (inventario vs actualización), como en la entrega anterior.

## 2. G-R1 — No reemplazo también en el traslado de aborto (los tres motores)

**Cambio** (6 sitios: 2 por motor — `except KeyboardInterrupt` y `except Exception` en Hardened/EVO; los mismos dos en MQR `main`; +22/−4 por motor H/E, +18/−4 MQR):

- **Antes**: `os.rename(run_dir, aborted)` con fallback `except OSError: aborted = run_dir` — `os.rename` puede reemplazar un destino preexistente **vacío** y el fallback ocultaba el fallo.
- **Después**: el traslado usa `_publicar_dir_6g1(run_dir, aborted)` — la **misma operación atómica de no-reemplazo** (`renameat2 RENAME_NOREPLACE`) de la corrección G:
  - destino `_aborted` preexistente (con archivos, vacío o enlace simbólico) → `EEXIST` → se elige un **sufijo libre** (`_rNNN`, misma política segura) sin tocar jamás el destino;
  - si el entorno no garantiza el no-reemplazo → **no se traslada**: el provisional queda conservado en su ubicación original (`aborted = run_dir`) con log explícito; **sin degradación a `os.rename()`**;
  - el mensaje de log original de cada sitio se conserva (trazabilidad).
- Verificación estática: **0 apariciones** de `os.rename(run_dir` en los tres motores; los 6 traslados pasan por `_publicar_dir_6g1`.

## 3. Pruebas y resultados individuales (17/17 PASS, 0 FAIL, 0 NOT_EXECUTED)

`evidence/matriz_e_r1_g_r1_6g1.csv` · detalle por check: `evidence/pruebas_e_r1_g_r1_6g1.json`. No se repitieron las baterías de 34 ni de 26; sólo sanidad mínima por motor.

| Prueba | Alcance | Qué comprueba | Resultado |
|---|---|---|---|
| **E-R1a** | unidad, determinista | Sustitución de `analysis.json` por **otro archivo regular** exactamente entre la acreditación y la escritura (inyectada por un gancho sobre `_propiedad_fd_acreditada`, sin tocar el código del módulo): el sustituto conserva sus bytes y SHA-256 byte a byte; **no se escribe sobre él**; el motivo registra «mismo descriptor verificado, sin reapertura por nombre»; `ABORT_6G1.json` regular creado; propio acreditado eliminado | PASS |
| **E-R1b** | unidad | Acreditación imposible (sellado modificado in situ): archivo conservado byte a byte, sin truncar, motivo `propiedad no acreditada`, fail-closed | PASS |
| **G-R1a** ×3 motores | end-to-end (SIGINT con reloj real) | Destino `_aborted` preexistente **con archivos y centinelas**: centinelas intactos (SHA-256), destino sin artefactos del motor, provisional conservado en `*_partial` o trasladado a `_aborted_rNNN` con su `engine_log.txt`, exit 130 | 3× PASS |
| **G-R1b** ×3 motores | end-to-end | Destino `_aborted` preexistente **como directorio vacío** (el caso que `os.rename` habría reemplazado): el destino sigue existiendo y **sigue vacío**; provisional conservado o trasladado a sufijo | 3× PASS |
| **G-R1c** ×3 motores | end-to-end | Destino `_aborted` preexistente **como enlace simbólico**: el enlace se conserva (nunca seguido ni reemplazado) y el archivo externo apuntado permanece byte a byte | 3× PASS |
| G-R1-estático ×3 | código | `os.rename(run_dir` ausente; traslado vía `_publicar_dir_6g1(run_dir, aborted)` | 3× PASS |
| sanidad ×3 | corrida feliz | exit 0, publicación única, integridad True, **PCM idéntico a la campaña auditada** (sin cambio DSP) | 3× PASS |

**Método de interrupción**: SIGINT dirigido al proceso del motor con anclas de log **dentro del `try`** (antes de cualquier publicación): Hardened/EVO en `Chunk 10/17` (mix de 12 s con `--chunk-frames 32`; el motor sólo registra cada 10 chunks y el último) y MQR en `Escribiendo analysis.json` (MQR no registra chunks; la línea está dentro de `main`, antes de guarda/publicación). Si el KI aterrizara fuera de la ventana, la prueba lo registra como fallo del disparo, no como éxito. Plantado del destino `_aborted` al aparecer el `*_partial` (siempre antes del disparo). El sustituto de E-R1a se planta por copia+`os.replace` conservando su propia ruta (la verificación de bytes compara el original).

## 4. SHA-256 de los archivos modificados

`SHA256SUMS_ER1_GR1.txt` (7 ficheros, con el SHA previo en comentario; verificado con `sha256sum -c`: 7/7 OK). Diff incremental exclusivo respecto de `2248e2e`: `DIFF_6G1_ER1_GR1.patch` (1.012 líneas; **reversible verificado** — `patch -R -p1` devuelve el árbol de `2248e2e` byte a byte, `diff -r` sin diferencias; forward dry-run exit 0). Superficie de trabajo: **+831/−20** (+18/−4 MQR, +22/−4 Hardened, +22/−4 EVO, +36/−12 módulo, batería nueva 473 L, evidencia 309 L).

## 5. Confirmaciones exigidas

1. **Sin cambios DSP**: las modificaciones se limitan a la actualización interna de `analysis.json` en el aborto (E-R1) y al traslado del provisional en rutas de excepción/interrupción (G-R1); sanidad ×3 con PCM (`pcm_sha256`) idéntico a los hash de la campaña auditada.
2. **HEAD remoto y padre del commit**: el commit de esta entrega tiene como **padre directo** `2248e2e21e44b279d57f9d0163f3f11b474a75e2` y el HEAD remoto de `arena/441a4bf8-sdv-sdi-sgm` fue verificado igual al local tras el push (valores exactos al final de este documento y en el informe de ejecución).
3. Límites: base exacta `2248e2e`; sin tocar STFT/…/parámetros DSP; motores originales y carpeta 6G de referencia intactos; `main` y `arena/89d5c189-sdv-sdi-sgm` intactos; sin Elis/Tristania; sin Android/Termux; baterías anteriores no repetidas; A–D y F intactos salvo lo estrictamente necesario para E-R1/G-R1 (bloque de actualización del aborto y traslados de excepción). **No se declara 6G.1 cerrada.**

## 6. Enlaces (URLs completas)

Informe E-R1/G-R1 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_ER1_GR1_6G1.md

Diff incremental vs 2248e2e (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_ER1_GR1.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_ER1_GR1.txt

Matriz E-R1/G-R1:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_e_r1_g_r1_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_e_r1_g_r1_6g1.json

Módulo corregido (E-R1):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
