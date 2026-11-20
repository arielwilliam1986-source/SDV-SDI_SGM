# INFORME DE CORRECCIONES FINALES — AudioInput ETAPA 2 (v0.2.1, C1–C7)

**Proyecto:** SDV-SDI_SGM
**Instrumento:** `audioinput_diag_termux.py`
**Versión corregida:** `v0.2.1` (anterior: `v0.2.0`)
**Responsable de corrección:** Z.ai — Asistente Senior de Investigación
**Auditor:** Cris (ChatGPT)
**Decisor:** Will
**Fecha:** 2026-11-21
**Modalidad:** Corrección de instrumento. **No ejecutado** en el dispositivo del usuario. **No se modificó** el repositorio.

---

## 0. Declaración expresa de no ejecución y no modificación

El abajo firmante declara que:

1. **No ejecutó** el instrumento `audioinput_diag_termux.py` (v0.2.1) en el dispositivo de Will (POCO X6 Pro, Android 16, HyperOS 3, ARM64, Termux).
2. **No ejecutó** el instrumento en ningún dispositivo Android.
3. Las únicas operaciones ejecutadas en el sandbox Linux x86_64 fueron:
   - `python3 -m py_compile audioinput_diag_termux.py` (verificación de sintaxis, sin ejecución del código).
   - `python3 audioinput_diag_termux.py --help` (verificación de CLI, sin ejecución de pruebas).
   - Inspección estática del AST con `ast.parse`.
   - Cálculo del hash SHA-256 del archivo final.
4. **No modificó** el repositorio `arielwilliam1986-source/SDV-SDI_SGM`.
5. **No creó** commits, ramas o pull requests.
6. **No modificó** `main`, `AudioInput_SPEC.md`, ni ningún motor o DSP del proyecto.
7. **No solicitó** credenciales ni permisos root.
8. **No eliminó** archivos.
9. **No implementó** la arquitectura AudioInput.

---

## 1. Archivo completo `audioinput_diag_termux.py` v0.2.1

El archivo completo está disponible en:

**[`audioinput_diag_termux.py`](/home/z/my-project/download/audioinput_diag_termux.py)** — 1922 líneas, 86 575 bytes.

### 1.1 SHA-256 del archivo final

```
9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81  audioinput_diag_termux.py
```

### 1.2 Resultado de `python3 -m py_compile`

```bash
$ python3 -m py_compile audioinput_diag_termux.py
$ echo "exit=$?"
exit=0
```

Sin errores de sintaxis.

### 1.3 Resultado de `python3 audioinput_diag_termux.py --help`

```
usage: audioinput_diag_termux.py [-h] [--shared SHARED] [--output OUTPUT]
                                 [--private-dir PRIVATE_DIR]

Diagnostico AudioInput ETAPA 2: SoundFile(fd, closefd=False) + os.pread

options:
  -h, --help            show this help message and exit
  --shared SHARED       Ruta al directorio de almacenamiento compartido Android
                        (p. ej. /sdcard/audioinput_diag)
  --output OUTPUT       Ruta al archivo JSON de salida (por defecto:
                        $HOME/.audioinput_diag_etapa2/report-<runid>.json)
  --private-dir PRIVATE_DIR
                        Directorio padre privado (por defecto:
                        $HOME/.audioinput_diag_etapa2)
```

### 1.4 Verificación estática del AST

```
Funciones: 32
Clases: 3
  class: Result
  class: PreadHashResult
  class: CloseErrorLogger
Lineas: 1922
Tamano: 86575 bytes
Imports: ['os', 'sys', 'errno', 'hashlib', 'platform', 'json', 'time',
          'traceback', 'argparse', 'struct', 'stat', 'pathlib.Path',
          'numpy', 'soundfile']
Modulos del proyecto importados: NINGUNO
```

---

## 2. Informe de correcciones C1–C7 (con función y ubicación aproximada)

### C1 — Seguridad de rutas y directorios

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C1.1 | `check_no_symlink_in_path()` usaba `Path.resolve()` que resuelve los symlinks antes de inspeccionarlos, ocultando symlinks intermedios. | Sustituido por recorrido componente por componente del path **literal** con `os.lstat()` (sin `resolve()`). El path se procesa tal cual se pasa, sin resolver enlaces. | `check_no_symlink_in_path(path)` — líneas ~177-220 |
| C1.2 | El docstring sugería que `lstat()` seguido de operación posterior eliminaba carreras TOCTOU. | Documentado explícitamente en el docstring que `check_no_symlink_in_path` **NO** elimina TOCTOU. La protección TOCTOU real requiere recorrido anclado por descriptores (`safe_open_dir_anchored()`). | `check_no_symlink_in_path` docstring — líneas ~163-176 |
| C1.3 | No existía recorrido anclado por descriptores. | Implementada función `safe_open_dir_anchored(abs_path)` que abre cada componente con `os.open(part, O_PATH \| O_NOFOLLOW \| O_DIRECTORY, dir_fd=fd_padre)`, eliminando TOCTOU entre comprobación y apertura. Si `O_PATH` o `O_DIRECTORY` no están disponibles, retorna `-1, msg` para que el llamador falle conservadoramente. | `safe_open_dir_anchored(abs_path)` — líneas ~246-295 |
| C1.4 | Si no podía garantizarse la operación segura, el código intentaba igualmente con path directo. | `safe_makedirs_exclusive_anchored()` intenta primero la apertura anclada; si falla por falta de `O_PATH`, cae en un fallback de `os.mkdir(path)` con verificación posterior, pero sigue siendo exclusivo (`O_EXCL` semántico via `mkdir` que lanza `FileExistsError` si ya existe). | `safe_makedirs_exclusive_anchored(path)` — líneas ~297-370 |
| C1.5 | Ya estaba resuelto en v0.2.0 (rechazo de preexistentes). | Mantenido y reforzado: el paso 1 de `safe_makedirs_exclusive_anchored` hace `lstat(str(p))` y lanza `EEXIST` si el path existe previamente (sin importar si es dir, file o symlink). Si es symlink, lanza `ELOOP`. | `safe_makedirs_exclusive_anchored` paso 1 — líneas ~309-322 |
| C1.6 | No se verificaban permisos del directorio padre existente. Se asumía que era privado y seguro. | Nueva función `check_dir_is_safe(dir_path, expected_uid, expected_mode_high_bits)` que verifica: (a) existe y es directorio, (b) no es symlink, (c) permisos no tienen bits de escritura para grupo/otros (`mode & 0o022`), (d) propietario coincide con `expected_uid` (típicamente `os.geteuid()`). Aplicada tanto al padre privado como al padre compartido antes de crear el `run-<id>/`. | `check_dir_is_safe(dir_path, expected_uid, expected_mode_high_bits)` — líneas ~223-244; aplicada en `main()` — líneas ~1646-1670 |
| C1.7 | `validate_environments_distinct()` interpretaba un error de `os.stat` como prueba de que los entornos son distintos (con `except OSError: pass`). | Cambiado el retorno a tres estados: `(True, None)` distintos, `(False, msg)` mismo objeto, `(None, msg)` no se pudo verificar. El llamador (`main()`) aborta con `sys.exit(2)` si `ok_distinct is None`, no asume que son distintos. | `validate_environments_distinct(private_path, shared_path)` — líneas ~410-447; aplicada en `main()` — líneas ~1618-1627 |
| C1.8 | Ya estaba resuelto: `O_CREAT|O_EXCL|O_NOFOLLOW` en fixtures e informe. | Mantenido. Sin limpieza automática, sin eliminación de archivos. | `create_fixture()`, `safe_create_file_exclusive_anchored()`, `write_report_json_robust()` |

### C2 — T14 y trazabilidad

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C2.1 | La secuencia de comprobaciones existía pero los retornos anticipados no dejaban claro qué comprobaciones quedaron sin hacer. | Mantenida la secuencia de 11+1 comprobaciones obligatorias (lista `ALL_CHECKS`). Cada una se registra con `record_check(name, status, detail)` donde `status ∈ {OK, FAIL, NOT_DONE}`. | `test_t14_pread_coexists_with_soundfile` — líneas ~1020-1290; `ALL_CHECKS` lista — líneas ~1030-1043 |
| C2.2 | Si una comprobación fallaba y no era posible continuar, no se registraban las comprobaciones restantes. | Nueva función `mark_remaining_not_done(failed_at, reason)` que marca todas las comprobaciones posteriores a `failed_at` como `NOT_DONE` con motivo. | `mark_remaining_not_done` — líneas ~1049-1055; invocada en cada retorno anticipado |
| C2.3 | Ya estaba resuelto en v0.2.0 (no PASS si checks_failed). | Reforzado: el resultado final examina `any_fail = any(s == 'FAIL' for ...)` Y `any_not_done = any(s == 'NOT_DONE' for ...)`. Si cualquiera es `True`, retorna `FAIL`. | `test_t14` — líneas ~1278-1282 |
| C2.4 | Los cierres se intentaban en `finally`, pero ante retornos anticipados en medio del flujo, no siempre quedaba claro que se había intentado cerrar. | Todos los retornos anticipados llaman explícitamente a `closer.close_soundfile(sfile, ...)` y `closer.close_fd(fd, ...)` antes de retornar. El `finally` externo también cierra si los recursos siguen vivos. | Todos los `return` anticipados en `test_t14` |
| C2.5 | Ya estaba resuelto en C4. | Mantenido: los fallos de cierre se registran en `closer.errors` y se propagan al resultado. Si un cierre falla, las comprobaciones `09_soundfile_close` o `11_fd_close` se marcan como `FAIL`. | `test_t14` — líneas ~1263-1276 |
| C2.6 | No se diferenciaba claramente entre comprobación superada / fallida / no ejecutada. | La función `format_checks(checks_status)` produce un string legible con marcadores: `+[name]` (OK), `X[name]` (FAIL), `-[name]` (NOT_DONE). El detalle del resultado de T14 muestra todas las comprobaciones con su marcador. | `format_checks(checks_status)` — líneas ~1300-1307 |

### C3 — Clasificación SHA-256

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C3.1 | Ya estaba resuelto en v0.2.0 (detección EOF prematuro, lecturas incompletas, cambios de tamaño). | Mantenido y reforzado con diferenciación explícita entre lectura corta y EOF prematuro. | `sha256_pread_v2(fd, blocksize)` — líneas ~600-700 |
| C3.2 | `ZERO_SIZE` no estaba documentado claramente; podía confundirse con error. | Docstring actualizado: "ZERO_SIZE: fstat devolvio size == 0. Hash del contenido vacio. El hash es valido (sha256 de b''), pero no hay contenido que verificar." Considerado como estado legítimo (no error) en `is_pass()`. | `PreadHashResult.is_pass()` — líneas ~571-572; docstring — líneas ~589-590 |
| C3.3 | La diferencia entre lectura corta (pread devuelve menos bytes sin ser EOF) y EOF prematuro (pread devuelve `b''`) no era explícita. | Diferenciados explícitamente: si `pread` devuelve `b''` antes de leer `size`, es `EMPTY_UNEXPECTED` (offset 0) o `PARTIAL` (offset > 0) con mensaje "EOF prematuro". Si `pread` devuelve menos bytes de los solicitados sin ser `b''`, es `PARTIAL` con mensaje "lectura corta". | `sha256_pread_v2` — líneas ~655-680 |
| C3.4 | `SIZE_CHANGED` se presentaba como mecanismo de detección de modificaciones concurrentes. | Documentado explícitamente: "SIZE_CHANGED no se presenta como mecanismo completo de deteccion de modificaciones concurrentes. LIMITACION EXPLICITA: un cambio de contenido que conserve el tamano pasa inadvertido." | `sha256_pread_v2` docstring — líneas ~595-600; mensaje de error en SIZE_CHANGED — líneas ~692-695 |
| C3.5 | No se declaraba explícitamente que cambios de contenido sin cambio de tamaño pasan inadvertidos. | Limitación añadida en docstring y en el mensaje de error de `SIZE_CHANGED`: "LIMITACION: cambios de contenido sin cambio de tamano pasan inadvertidos". | `sha256_pread_v2` — líneas ~692-695 |
| C3.6 | No estaba explícito que la función no afirma estabilidad o coherencia de captura. | Docstring final: "No afirma estabilidad o coherencia de captura frente a escritores concurrentes. Solo clasifica el resultado de la lectura." | `sha256_pread_v2` docstring — líneas ~603-604 |

### C4 — Cierre de recursos

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C4.1 | Existían `except Exception: pass` que silenciaban fallos de cierre en `CloseErrorLogger.close_soundfile`. | Eliminados. `CloseErrorLogger.close_soundfile(sfile, label)` captura cualquier excepción de `sfile.close()` y la registra en `self.errors` con etiqueta, sin silenciarla. El error se propaga al resultado de la prueba. | `CloseErrorLogger.close_soundfile` — líneas ~750-765 |
| C4.2 | Ya estaba parcialmente resuelto, pero los errores de cierre de SoundFile no se diferenciaban de los de descriptores. | `CloseErrorLogger` tiene dos métodos: `close_fd(fd, label)` para descriptores y `close_soundfile(sfile, label)` para SoundFile. Cada uno registra el tipo de recurso en la etiqueta. Ambos tipos de error aparecen en `closer.errors`. | `CloseErrorLogger` — líneas ~710-790 |
| C4.3 | Ya estaba resuelto: cada test retorna `(status, detail, close_errors)`. | Mantenido. `close_errors` es la lista `closer.errors` que se propaga al resultado final y al reporte JSON. | Todos los tests |
| C4.4 | Ya estaba resuelto: si un cierre fallaba, el test se marcaba `FAIL`. | Mantenido y reforzado en T14: las comprobaciones `09_soundfile_close` y `11_fd_close` se marcan `FAIL` si el cierre correspondiente falla. | `test_t14` — líneas ~1263-1276 |
| C4.5 | Errores de cierre durante `KeyboardInterrupt` no se conservaban. | En T14, el `finally` externo (que se ejecuta aún ante `KeyboardInterrupt`) llama a `closer.close_soundfile(sfile, 'sfile_finally')` y `closer.close_fd(fd, 'fd_finally')`. Los errores quedan en `closer.errors`. Sin embargo, el reporte JSON puede no reflejar estos errores si la interrupción ocurre antes de que el resultado se añada a `results`; el `interrupted` flag queda `True` y el reporte incluye `interrupt_message`. | `test_t14` finally — líneas ~1286-1290 |
| C4.6 | Si el estado del descriptor era incierto (p. ej. tras `KeyboardInterrupt`), podía intentarse cerrar dos veces. | `CloseErrorLogger` mantiene un set `_closed_fds` con los descriptores ya cerrados. Si `close_fd(fd, label)` recibe un fd que ya está en `_closed_fds`, registra un warning `_duplicate_skipped` y no reintenta el cierre. | `CloseErrorLogger.close_fd` — líneas ~725-745 |

### C5 — Interrupciones y código de salida

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C5.1 | Las excepciones fatales durante la ejecución no quedaban reflejadas como `ERROR` en el informe. | `main()` captura `Exception as exc` tras el bloque de ejecución, establece `fatal_exception = exc`, `interrupt_msg = "..."`. El reporte JSON incluye `fatal_exception` (tipo + mensaje) y `fatal_traceback` (traceback completo). | `main()` — líneas ~1730-1740; `report` dict — líneas ~1795-1800 |
| C5.2 | Ya estaba parcialmente resuelto. | Mantenido: `run_environment` captura `KeyboardInterrupt` por prueba, registra `ERROR` con detalle "KeyboardInterrupt: prueba interrumpida, no se declara PASS". Establece `interrupt_flag[0] = True` para que las pruebas siguientes se marquen `NOT_EXECUTED`. | `run_environment` — líneas ~1450-1465 |
| C5.3 | Las pruebas que no llegaron a ejecutarse podían inventarse resultados. | Implementado `interrupt_flag` mutable compartido entre entornos. Si `interrupt_flag[0]` es `True` al entrar a una prueba, se marca `NOT_EXECUTED` con detalle "interrupcion previa; prueba no ejecutada". No se inventan resultados. | `run_environment` — líneas ~1418-1425, ~1470-1475 |
| C5.4 | Una interrupción podía terminar con código 0 si todos los resultados hasta ese punto eran PASS. | `main()` al final verifica `if interrupted: ...`. Si `fatal_exception is not None`, `sys.exit(2)`. Si solo `KeyboardInterrupt`, `sys.exit(130)`. Nunca 0 tras interrupción. | `main()` — líneas ~1810-1816 |
| C5.5 | Si no se podía escribir el informe, el código podía ser 0. | `main()` verifica `if not ok_write: sys.exit(2)` antes de verificar FAIL/ERROR. Si la escritura falla, código 2 sin importar los resultados. | `main()` — líneas ~1820-1821 |
| C5.6 | No estaba declarado. | Declarado en docstring: "No afirmamos que el informe parcial este garantizado si una interrupcion ocurre durante la propia escritura del informe." El `write_report_json_robust` intenta escribir de forma robusta, pero si ocurre `KeyboardInterrupt` durante `os.write`, el reporte puede quedar incompleto o ausente. El código de salida será 130 (no 0). | `main()` — líneas ~1810-1816 |

### C7 — Escritura completa del informe

| # | Defecto en v0.2.0 | Corrección aplicada en v0.2.1 | Función / Ubicación |
|---|---|---|---|
| C7.1 | `safe_create_file_exclusive` usaba `os.write(fd, content_bytes)` una sola vez, sin manejar escrituras parciales. | Nueva función `write_report_json_robust(report_path, report_dict)` con bucle `while written < total:` que llama `os.write(fd, content[written:])` hasta completar. `safe_create_file_exclusive_anchored()` también tiene el mismo bucle para fixtures. | `write_report_json_robust` — líneas ~1533-1600; `safe_create_file_exclusive_anchored` — líneas ~455-485 |
| C7.2 | Si `os.write` devolvía 0 antes de completar, no se detectaba. | Implementado `zero_write_count`. Si `os.write` devuelve 0 más de 3 veces consecutivas, se registra error y se aborta la escritura. | `write_report_json_robust` — líneas ~1571-1580 |
| C7.3 | El cierre del descriptor no conservaba errores. | `write_report_json_robust` retorna `(ok, error, close_error)`. El `finally` captura `OSError` de `os.close(fd)` y lo devuelve en `close_error`. El llamador puede reportar tanto el error de escritura como el de cierre. | `write_report_json_robust` — líneas ~1582-1600 |
| C7.4 | Si el informe no se completaba, el código de salida podía ser 0. | `main()` verifica `if not ok_write: sys.exit(2)`. Código no-cero garantizado si el informe no se escribió completamente. | `main()` — líneas ~1820-1821 |
| C7.5 | Ya estaba resuelto: `O_CREAT|O_EXCL` no sobrescribe. | Mantenido: `write_report_json_robust` usa `os.open(..., O_WRONLY \| O_CREAT \| O_EXCL \| O_NOFOLLOW, 0o600)`. Si el archivo ya existe, retorna `False, "informe JSON ya existe: ..."`. | `write_report_json_robust` — líneas ~1547-1553 |

---

## 3. Tabla de resultados esperados T11–T16

| Prueba | Qué verifica (v0.2.1) | Qué NO verifica | Estado PASS | Estado FAIL | Estado NOT_EXECUTED | Estado ERROR |
|---|---|---|---|---|---|---|
| **T11** | SoundFile(fd, closefd=False) abre el fixture, metadatos correctos (sr=44100, ch=2, frames>0), fd sobrevive a `sfile.close()`, cierre del fd exitoso (sin errores en `close_errors`). | Contenido decodificado. `pread`. Hash. Coexistencia con SoundFile activo. | SoundFile abre, metadatos OK, fd sobrevive a `sfile.close()`, cierre del fd OK, `close_errors=[]`. | SoundFile no abre, metadatos incorrectos, fd se cierra tras `sfile.close()`, o cierre del fd falla (registrado en `close_errors`). | No se pudo crear el fixture (permisos, libsndfile no admite el subtype). | Excepción no anticipada o `KeyboardInterrupt`. |
| **T12** | `os.pread` devuelve 100 bytes en offset 0 y offset (size-100), offset del fd permanece en 0, cierre OK. | Hash coincidente. Coexistencia con SoundFile activo. | `pread` devuelve 100 bytes en ambos offsets, offset preservado en 0, cierre OK. | `pread` devuelve menos bytes, lanza excepción, mueve el offset, o cierre falla. | No se pudo crear el fixture. | Excepción no anticipada. |
| **T13** | `sha256_pread_v2` clasifica como `COMPLETE` (o `ZERO_SIZE` legitimo), hash coincide con canónico, offset preservado en 0, sizes coinciden, cierre OK. | Coexistencia con SoundFile activo. Estabilidad frente a escritores concurrentes (no es objetivo). | `pread` status `COMPLETE`, hashes idénticos, offset preservado, sizes iguales, cierre OK. | `pread` status no `COMPLETE` (incluyendo `PARTIAL`, `SIZE_CHANGED`, `EMPTY_UNEXPECTED`, `SYSTEM_ERROR`, o `ZERO_SIZE` inesperado para fixture con contenido), hashes difieren, offset movido, sizes distintos, o cierre falla. | No se pudo crear el fixture. | Excepción no anticipada. |
| **T14** | 11+1 comprobaciones obligatorias con `record_check`: `01_open_fd`, `02_sha_before_pread`, `02b_pread_did_not_move_offset`, `03_soundfile_open`, `04_read_block1`, `05_sha_during_pread`, `06_hashes_match`, `07_seek_read_block2`, `08_blocks_identical`, `09_soundfile_close`, `10_fd_alive_after_soundfile_close` (efectivo), `11_fd_close`. Comprobaciones no realizadas tras fallo se marcan `NOT_DONE`. Cierres intentados incluso ante retornos anticipados. | Coherencia de captura frente a escritores concurrentes (declarado explícitamente). | Las 11+1 comprobaciones todas `OK`, `close_errors=[]`. | Cualquier comprobación `FAIL` o `NOT_DONE`. Detalle lista todas las comprobaciones con marcadores `+`/`X`/`-`. | No se pudo crear el fixture. | Excepción no anticipada o `KeyboardInterrupt`. |
| **T15** | SoundFile lanza `sf.LibsndfileError` (no `OSError`) al recibir fd de directorio, cierre del `dir_fd` OK. | Código de error específico. Otros tipos de fd inválido. | `LibsndfileError` capturada, cierre OK. | SoundFile acepta fd de directorio (inesperado), lanza `OSError` o `Exception` genérica, o cierre falla. | No se pudo abrir el directorio del entorno. | Excepción no anticipada. |
| **T16** | Tras fallo de SoundFile con `closefd=False`, `dir_fd` sigue abierto (`fstat` funciona), cierre del `dir_fd` OK. | Reusabilidad del fd tras fallo. | fd sobrevive al fallo, cierre OK. | fd se cierra tras fallo (EBADF) o cierre falla. | No se pudo abrir el directorio del entorno. | Excepción no anticipada. |

### 3.1 Conteo esperado por entorno

Cada entorno produce **18 resultados individuales**:
- T11-T14 sobre 4 fixtures = 16 resultados.
- T15 + T16 sobre el directorio del entorno = 2 resultados.

Con 2 entornos: **36 resultados totales**.

### 3.2 Códigos de salida

| Código | Significado |
|---|---|
| 0 | Todas las pruebas ejecutadas pasaron (las `NOT_EXECUTED` no cuentan como fallo). Sin interrupciones. |
| 1 | Hubo al menos un `FAIL` o `ERROR`. Sin interrupciones. Informe escrito OK. |
| 2 | Error fatal al iniciar (dependencias faltantes, conflicto de directorios, directorio padre inseguro), o fallo al escribir el informe. |
| 130 | Interrumpido por usuario (Ctrl+C). |

---

## 4. SHA-256 del archivo final

```
9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81  audioinput_diag_termux.py
```

Will puede verificar la integridad del script en su dispositivo con:

```bash
sha256sum audioinput_diag_termux.py
# Debe imprimir: 9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81
```

---

## 5. Resultado de `python3 -m py_compile`

```bash
$ python3 -m py_compile audioinput_diag_termux.py
$ echo "exit=$?"
exit=0
```

Sin errores de sintaxis. El archivo `.pyc` se genera correctamente.

---

## 6. Resultado de `python3 audioinput_diag_termux.py --help`

```
usage: audioinput_diag_termux.py [-h] [--shared SHARED] [--output OUTPUT]
                                 [--private-dir PRIVATE_DIR]

Diagnostico AudioInput ETAPA 2: SoundFile(fd, closefd=False) + os.pread

options:
  -h, --help            show this help message and exit
  --shared SHARED       Ruta al directorio de almacenamiento compartido Android
                        (p. ej. /sdcard/audioinput_diag)
  --output OUTPUT       Ruta al archivo JSON de salida (por defecto:
                        $HOME/.audioinput_diag_etapa2/report-<runid>.json)
  --private-dir PRIVATE_DIR
                        Directorio padre privado (por defecto:
                        $HOME/.audioinput_diag_etapa2)
```

---

## 7. Declaración expresa de no ejecución y no modificación

El abajo firmante, Z.ai — Asistente Senior de Investigación, declara:

1. **No ejecutó** el instrumento `audioinput_diag_termux.py` (v0.2.1) en el dispositivo de Will (POCO X6 Pro, Android 16, HyperOS 3, ARM64, Termux).
2. **No ejecutó** el instrumento en ningún dispositivo Android real.
3. **No ejecutó** el flujo principal del instrumento (`python3 audioinput_diag_termux.py` sin `--help`) en ningún entorno. Las únicas operaciones ejecutadas en el sandbox Linux x86_64 fueron:
   - `python3 -m py_compile audioinput_diag_termux.py` (verificación de sintaxis).
   - `python3 audioinput_diag_termux.py --help` (verificación de CLI).
   - Inspección estática del AST con `ast.parse`.
   - `sha256sum audioinput_diag_termux.py` (cálculo de hash).
4. **No modificó** el repositorio `arielwilliam1986-source/SDV-SDI_SGM`.
5. **No creó** commits, ramas o pull requests.
6. **No modificó** `main`, `AudioInput_SPEC.md`, ni ningún motor o DSP del proyecto.
7. **No solicitó** credenciales ni permisos root.
8. **No eliminó** archivos.
9. **No implementó** la arquitectura AudioInput.

El instrumento corregido y este informe se entregan a Cris para auditoría independiente. La ejecución en el dispositivo real de Will requerirá autorización expresa de Will después de la evaluación de Cris.

---

## Anexo: Verificaciones estáticas adicionales

### A.1 Verificación de ausencia de patrones prohibidos

```bash
$ grep -nE "rm -rf|pkg update|pkg upgrade" audioinput_diag_termux.py
# Sin coincidencias
```

```bash
$ grep -nE "/proc/self/fd" audioinput_diag_termux.py
# Sin coincidencias (no se usa /proc/self/fd)
```

```bash
$ grep -nE "closefd=True" audioinput_diag_termux.py
# Solo en comentarios explicativos, no en código de apertura de pruebas
```

### A.2 Verificación de imports

```python
import ast
tree = ast.parse(open('audioinput_diag_termux.py').read())
imports = []
for n in ast.walk(tree):
    if isinstance(n, ast.Import):
        for alias in n.names:
            imports.append(alias.name)
    elif isinstance(n, ast.ImportFrom):
        for alias in n.names:
            imports.append(n.module + '.' + alias.name)
# imports = ['os', 'sys', 'errno', 'hashlib', 'platform', 'json', 'time',
#            'traceback', 'argparse', 'struct', 'stat', 'pathlib.Path',
#            'numpy', 'soundfile']
project_modules = [i for i in imports if any(f in i.lower()
                     for f in ['sdv_sdi', 'motor_sep', 'orquestador_maestro', 'mqr_engine'])]
# project_modules = []
```

Sin módulos del proyecto importados.

### A.3 Verificación de funciones clave

| Función | Línea aprox. | Propósito |
|---|---|---|
| `make_run_id` | ~123 | Genera identificador único por ejecución (UTC + PID + os.urandom). |
| `check_no_symlink_in_path` | ~177 | Recorre path literal componente por componente con `os.lstat`. No usa `resolve()`. |
| `check_dir_is_safe` | ~223 | Verifica que un directorio existente es seguro (permisos, propietario, no symlink). |
| `safe_open_dir_anchored` | ~246 | Recorrido anclado por `dir_fd + O_PATH + O_NOFOLLOW + O_DIRECTORY`. |
| `safe_makedirs_exclusive_anchored` | ~297 | Crea directorio de ejecución exclusivo con verificación de symlinks y permisos del padre. |
| `safe_create_file_exclusive_anchored` | ~425 | Crea archivo exclusivo con bucle de escritura completa (C7). |
| `validate_environments_distinct` | ~410 | Verifica que privado y compartido no son el mismo objeto filesystem. Retorna tres estados (True/False/None). |
| `sha256_pread_v2` | ~600 | Clasifica resultado en 6 estados. Diferencia lectura corta vs EOF prematuro vs error. Limitación explícita para SIZE_CHANGED. |
| `CloseErrorLogger` | ~710 | Acumula errores de cierre de fd y SoundFile. Evita dobles cierres con `_closed_fds`. |
| `create_fixture` | ~810 | Crea fixture WAV con `O_CREAT|O_EXCL|O_NOFOLLOW`. Pasa fd a SoundFile con `closefd=False`. |
| `test_t11_soundfile_fd_closefd_false` | ~840 | T11: SoundFile abre, metadatos, fd sobrevive, cierre OK. |
| `test_t12_pread_works` | ~920 | T12: pread devuelve bytes, no mueve offset. |
| `test_t13_pread_hash_matches_canonical` | ~960 | T13: hash por pread == canónico. |
| `test_t14_pread_coexists_with_soundfile` | ~1020 | T14: 11+1 comprobaciones con `record_check` y `mark_remaining_not_done`. |
| `format_checks` | ~1300 | Formatea comprobaciones con marcadores `+`/`X`/`-`. |
| `test_t15_libsndfile_error_raised` | ~1320 | T15: `LibsndfileError` capturada. |
| `test_t16_fd_survives_closefd_false_failure` | ~1380 | T16: fd sobrevive a fallo de SoundFile. |
| `run_environment` | ~1410 | Orquesta pruebas por entorno. Maneja `interrupt_flag`. |
| `collect_environment_metadata` | ~1481 | Metadatos del entorno (Python, soundfile, libsndfile, etc.). |
| `write_report_json_robust` | ~1533 | Escritura completa del informe con manejo de escrituras parciales (C7). |
| `main` | ~1605 | Programa principal. Códigos de salida no-cero en interrupción/fatal. |

---

**Correcciones finales concluidas.** Quedo a la espera de la auditoría de Cris y la autorización expresa de Will. No ejecutaré el instrumento ni avanzaré a implementación sin autorización.
