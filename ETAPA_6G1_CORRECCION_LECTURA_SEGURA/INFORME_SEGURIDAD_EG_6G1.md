# INFORME DE SEGURIDAD E–G — RECTIFICACIÓN 6G.1 (CORRECCIÓN PUNTUAL FINAL)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**Base de esta entrega**: `64b3c2d5052355cdcba411149bf9b8f8da1e3fdd` (corrección de auditoría A–D de 6G.1)
**Base técnica auditada**: `015e2f8e2b215c1d4dc5b9360988b42063e28533`
**Alcance**: exclusivamente los tres hallazgos nuevos (E, F, G) y las pruebas nuevas E1–E7. Las correcciones A–D no se rehicieron; ningún cambio ajeno a los hallazgos.

> **Estado**: ENTREGADA, **NO CERRADA**. La aprobación final corresponde a Cris tras revisar el código y las evidencias.

---

## 0. Publicación y entregables

- **Rama**: `arena/441a4bf8-sdv-sdi-sgm` (rama de sesión autorizada; la rama de referencia `arena/89d5c189-sdv-sdi-sgm` no fue tocada; sin `main`, sin merges, sin PR).
- **Diff incremental vs `64b3c2d`**: `DIFF_6G1_SEGURIDAD_EG.patch` (1.598 líneas; **reversible verificado**: `patch -R -p1` devuelve el árbol de `64b3c2d` byte a byte — `diff -r` sin diferencias; forward dry-run exit 0).
- **SHA-256 de modificados**: `SHA256SUMS_SEGURIDAD.txt` (8 ficheros, con el SHA previo en comentario; verificado con `sha256sum -c`: 8/8 OK).
- **Pruebas y resultados individuales**: `evidence/pruebas_seguridad_6g1.json` (detalle por check) y `evidence/matriz_seguridad_6g1.csv` (26 filas).
- Limpieza: sin `__pycache__` en el árbol ni en el commit.

**Nota de entorno**: durante esta tarea el sandbox fue restaurado por la plataforma (HEAD local revertido a `50bae98`, `.venv` y `/tmp` eliminados). El remoto permaneció intacto en `64b3c2d`; se aplicó el protocolo de recuperación (verificación remota → `reset --hard` → reconstrucción del entorno con las versiones exactas numpy 1.26.4 / scipy 1.13.1 / soundfile 0.13.1 / libsndfile 1.2.2). Ningún trabajo se perdió.

---

## 1. Hallazgo E — Protección de archivos internos frente a enlaces simbólicos (`lectura_segura_6g1.py`)

**Problema (confirmado por inspección y por prueba)**: `_es_registro_interno()` identificaba por nombre y la escritura de `ABORT_6G1.json` y la lectura/actualización de `analysis.json` usaban `Path.write_text()`/`Path.read_text()`, que **siguen enlaces simbólicos**: un `analysis.json` o `ABORT_6G1.json` simbólico apuntando a un archivo externo habría sido sobrescrito por el procedimiento de aborto.

**Corrección implementada** (todas las exigencias del hallazgo):

1. **No escribir a través de enlaces simbólicos** — todas las operaciones de E/S del aborto usan ahora descriptores:
   - `ABORT_6G1.json`: `os.open('ABORT_6G1.json', O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=<dirfd>)` — creación **exclusiva, no-follow y anclada al descriptor del directorio** (punto 4 y 6 del hallazgo); el contenido se escribe por `os.fdopen(fd)`.
   - `analysis.json`: lectura con `O_RDONLY|O_NOFOLLOW, dir_fd=...` y reescritura con `O_WRONLY|O_TRUNC|O_NOFOLLOW, dir_fd=...`; ambos con `os.fstat(fd)` sobre el descriptor abierto.
2. **Regulares con identidad de archivo interno legítimo** — tras abrir por descriptor se exige `S_ISREG` (enlaces → error de apertura con `ELOOP` → sin tocar); la identidad del descriptor (`st_dev`, `st_ino`) y el sello (`size`, `mtime_ns`, **SHA-256 del contenido leído**) se cotejan contra el **registro de propiedad de la corrida** (entrada estable sellada por `registrar_propio_6g1` en `write_reports`). Nueva función `_propiedad_fd_acreditada()` (fail-closed).
3. **`analysis.json` sólo si propiedad e identidad acreditadas** — si el archivo no está registrado, no coincide con el sello, es un enlace, o cualquier paso falla: se conserva sin modificar y se registra el motivo (`analysis.json (actualizacion): actualizacion omitida: propiedad no acreditada (…)` / `apertura segura fallo (…)`). Las claves de motivo del inventario y de la actualización están separadas para trazabilidad completa.
4. **`ABORT_6G1.json` exclusivo y seguro** — con `O_CREAT|O_EXCL|O_NOFOLLOW`, un preexistente (regular o simbólico) **nunca** se sobrescribe: se conserva y se registra `colision: ABORT_6G1.json preexistente (o enlace); sin sobrescribir`; el motivo sobrevive en el valor de retorno y, cuando `analysis.json` acredita propiedad, embebido en su campo `abort_6g1`.
5. **Colisión o propiedad indemostrable → conservar con motivo** — también en el pase de inventario, ahora con `os.lstat`: los enlaces se conservan siempre (`enlace_simbolico_conservado (sin seguir)`) y nunca se eliminan; `propiedad_de_6g1()` pasó de `os.stat` a `os.lstat` (un enlace jamás puede acreditar la identidad de un regular registrado; motivo nuevo `enlace_simbolico_no_propio`).
6. **Operaciones ancladas a descriptores de directorio** (`dir_fd`) y **no-follow** (`O_NOFOLLOW`) en toda la E/S interna; ante imposibilidad de verificar, fallo seguro (sin escritura).

**Alcance del cambio**: sólo `lectura_segura_6g1.py` (+183/−25). Los motores no requieren cambios para E (llaman a `abortar_6g1` sin cambio de firma).

## 2. Hallazgo F — Directorios provisionales exclusivos (los tres motores)

**Problema**: `os.makedirs(partial_dir, exist_ok=True)` reutilizaba un `_partial` preexistente; los writers abren en modo `w` y podrían truncar archivos ajenos **antes** de registrar propiedad.

**Corrección** en `create_run_dir()` de Hardened, EVO y MQR (texto equivalente en los tres):

1. **`os.mkdir(partial_dir)` sin `exist_ok`** — creación exclusiva (atómica).
2. **Nunca reutilizar** un `_partial` preexistente: ante `FileExistsError` se genera **otro identificador** (sufijo `_NNN` incremental, hasta 999 intentos) **sin tocar el contenido existente**; agotados los intentos → `RuntimeError` (aborta sin destruir nada).
3. `os.makedirs(out_base, exist_ok=True)` sólo garantiza la raíz de salida (como hacía la creación original de forma implícita).
4. **Registro de propiedad aislado por corrida**: `create_run_dir()` llama a `reiniciar_registro_6g1()` (nueva importación en los tres motores); además cada motor es un proceso independiente, de modo que el registro es doblemente aislado. Verificado dinámicamente en E4/E5 (`registro_vacio` tras cada llamada).
5. **Archivos preexistentes ≠ propios por ubicación**: ya garantizado por el mecanismo C (acreditación por registro), y reforzado porque el provisional siempre es nuevo y vacío.

## 3. Hallazgo G — Publicación sin sobrescritura (los tres motores)

**Problema**: `os.path.exists(run_dir_final)` + `os.rename(...)` tiene ventana de carrera y `os.rename` puede reemplazar un directorio de destino vacío.

**Corrección** (nueva función `publicar_dir_6g1()` en `lectura_segura_6g1.py`, usada por los tres motores):

- **Operación atómica de no-reemplazo**: `renameat2(..., RENAME_NOREPLACE)` vía símbolo `renameat2` de la libc y, si no existe, vía `syscall` con número por arquitectura (x86_64 316, aarch64 276, etc.). Sonda del entorno: disponible y correcta (`EEXIST` sin reemplazo) en tmpfs y workspace.
- **Nunca sustituye un destino ajeno**: `EEXIST` → reintento con sufijo `_rNNN` (el destino existente no se toca jamás); agotados los intentos → no publica.
- **Abortar si no puede garantizarse**: si `renameat2` no está disponible en el entorno (plataforma/FS sin soporte), la función eleva `OSError` y el motor **NO publica** (fail-closed, sin degradación silenciosa): Hardened/EVO retornan `EXIT_PROCESSING` conservando el provisional; MQR eleva `VerificacionFallida6G1` (capturado en `main` sin renombrar).
- Los bloques `exists()`+`os.rename` fueron **eliminados** de los tres motores (verificación estática E6: 0 apariciones de `os.rename(run_dir, run_dir_final)`).
- La lógica anti-colisión que antes precedía al rename vive ahora dentro del publicador seguro (mismo efecto observable: sufijo ante colisión).

## 4. Pruebas nuevas obligatorias (E1–E7) y resultados individuales

**Resultado: 26/26 PASS, 0 FAIL, 0 NOT_EXECUTED** (`evidence/matriz_seguridad_6g1.csv`; detalle por check en `evidence/pruebas_seguridad_6g1.json`). Entorno: CPython 3.11.2 + numpy 1.26.4 / scipy 1.13.1 / soundfile 0.13.1 / libsndfile 1.2.2 (idéntico al auditado). Fixtures intactos; sin repetir la batería de 34; sin audio real; sin Elis/Tristania; sin Android/Termux.

| Prueba | Alcance | Qué comprueba (contenido/hash/identidad/estado) | Resultado |
|---|---|---|---|
| E1 unidad | módulo compartido | `analysis.json` simbólico → externo: SHA-256 byte a byte intacto; el enlace se conserva; `ABORT_6G1.json` creado regular; propio acreditado eliminado | PASS |
| E1 Hardened/EVO/MQR | end-to-end | plantado determinista del enlace en el instante de la guarda (inyector, sin tocar código del motor): externo intacto, enlace conservado, `ABORT_6G1.json` regular, exit 2, sin directorio definitivo, salidas propias eliminadas | 3× PASS |
| E2 unidad | módulo compartido | `ABORT_6G1.json` simbólico → externo intacto; sin sobrescribir; motivo de colisión registrado | PASS |
| E2 Hardened/EVO/MQR | end-to-end | plantado del enlace; externo intacto; `ABORT_6G1.json` sigue siendo enlace; motivo de colisión registrado en `analysis.json` actualizado; exit 2; sin definitivo | 3× PASS |
| E3 unidad | módulo compartido | `analysis.json` ajeno ordinario: bytes intactos, sin campo `abort_6g1`, motivo `propiedad no acreditada` | PASS |
| E3 Hardened/EVO/MQR | end-to-end | reemplazo por ajeno ordinario: contenido byte a byte intacto y sin actualizar; exit 2; `ABORT_6G1.json` regular; sin definitivo | 3× PASS |
| E4 Hardened/EVO/MQR | dos procesos, marca temporal forzada (reloj congelado `20991231_235959`) | el segundo `create_run_dir` NO reutiliza el `_partial` del primero; centinelas del primero intactos (hash); el nuevo provisional queda vacío (sólo el marcador del propio arnés); registro de propiedad vacío tras cada corrida | 3× PASS |
| E5 Hardened/EVO/MQR | un proceso, reloj congelado | dos solicitudes con el mismo identificador → directorios distintos; marcador de la primera intacto; ambas existen | 3× PASS |
| E6 unidad + estático | `publicar_dir_6g1` | destino preexistente con centinela: no reemplazado (hash intacto) y origen publicado con sufijo; destino **vacío** tampoco reemplazado; los tres motores publican por la vía segura y sin `os.rename(run_dir, run_dir_final)` | 1× PASS + 3× PASS |
| E7 unidad | registro | aislamiento entre corridas consecutivas: lo registrado en la corrida 1 no está acreditado en la corrida 2 (`ajeno_no_registrado`), se conserva y permanece byte a byte; lo de la corrida 2 se elimina por su propia corrida | PASS |
| sanidad ×3 | corrida feliz | tras E–G: exit 0, publicación única, `after`/`ruta` True, **PCM idéntico a la campaña auditada** (contenedores_6g1.json) | 3× PASS |

**Nota de método**: los plantados end-to-end se realizan dentro del proceso del motor en el instante exacto de la guarda (extensión del inyector de pruebas `sitecustomize.py`, activada sólo por variables de entorno) — sin ellos, sembrar vía log tenía una carrera frente al aborto; así son deterministas. No se modificó el código del motor para ensayar.

**Registro honesto de iteraciones**: la primera ejecución de la batería dio 17/26; las desviaciones fueron del arnés de pruebas (motivos con clave colisionada en el inventario vs actualización — corregido en el módulo con claves separadas; una aserción de E7 mal dirigida; plantado por log con carrera — sustituido por plantado determinista; errata `h` en E4; aserción de E4 sobre el marcador del arnés). Ejecución final: 26/26.

## 5. Confirmación de que el DSP no se modificó

- Los cambios se limitan a: seguridad de E/S del aborto (E), creación de directorio de corrida (F), publicación (G) y arnés de pruebas.
- **Sanidad empírica**: corrida feliz por motor tras E–G con PCM (`pcm_sha256` del WAV releído) **idéntico** a los hash almacenados de la campaña auditada (`evidence/contenedores_6g1.json` del commit `64b3c2d`).
- Sin cambios en STFT, ISTFT, FFT, hop, chunking, máscaras, fórmulas, consenso, ganancias, polaridad ni parámetros DSP; motores originales y carpeta 6G intactos; `main` intacto.

## 6. Superficie de cambio (numstat vs `64b3c2d`, sin los dos entregables auto-referentes)

| Archivo | Cambio |
|---|---|
| `motores/lectura_segura_6g1.py` | +183/−25 (E + G) |
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | +36/−11 (F + G) |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | +36/−11 (F + G) |
| `motores/sdv_sdi_mqr_engine.py` | +37/−12 (F + G) |
| `scripts/inyeccion_6g1/sitecustomize.py` | +33/0 (plantado determinista de pruebas) |
| `scripts/pruebas_seguridad_6g1.py` | NUEVO (606 L; batería E1–E7) |
| `evidence/pruebas_seguridad_6g1.json`, `evidence/matriz_seguridad_6g1.csv` | NUEVOS (resultados individuales y matriz) |
| **Total superficie de trabajo** | **+1.372/−59** |

## 7. Límites respetados

No se tocaron STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP; ni los motores originales ni la carpeta 6G ni `main` ni la rama de referencia; sin fusionar ni abrir PR; sin Elis/Tristania; sin audio real; sin Android/Termux; la batería de 34 no se repitió (sólo sanidad mínima de publicación); A–D no se rehicieron (la única intervención sobre zonas A–D es la indispensable para E–G: claves de motivo en `abortar_6g1`, importación y llamada de reinicio/publicación en los motores). **No se declara 6G.1 cerrada**: la aprobación final corresponde a Cris.

## 8. Enlaces (URLs completas)

Informe de seguridad E–G (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_SEGURIDAD_EG_6G1.md

Diff incremental vs 64b3c2d (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_SEGURIDAD_EG.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_SEGURIDAD.txt

Matriz E1–E7:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_seguridad_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_seguridad_6g1.json

Módulo corregido (E + G):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py

Informe previo de correcciones A–D (antecedente):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_CORRECCIONES_AUDITORIA_6G1.md
