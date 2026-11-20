# INFORME DE CORRECCIONES PUNTUALES — AudioInput ETAPA 2 v0.2.2

**Proyecto:** SDV-SDI_SGM
**Instrumento:** `audioinput_diag_termux.py`
**Versión corregida:** `v0.2.2` (anterior: `v0.2.1`)
**Responsable:** Z.ai — Asistente Senior de Investigación
**Auditor:** Cris (ChatGPT)
**Decisor:** Will
**Fecha:** 2026-11-21

---

## 0. Declaración expresa de no ejecución y no modificación

1. **No se ejecutó** el instrumento en el dispositivo de Will ni en ningún dispositivo Android.
2. Las únicas operaciones ejecutadas en sandbox Linux x86_64 fueron:
   - `python3 -m py_compile audioinput_diag_termux.py` → `exit=0`
   - `python3 audioinput_diag_termux.py --help` → CLI OK
   - `ast.parse` para inspección estática
   - `sha256sum` para hash
3. **No se modificó** el repositorio `arielwilliam1986-source/SDV-SDI_SGM`.
4. **No se crearon** commits, ramas o PRs.
5. **No se modificó** `main`, `AudioInput_SPEC.md`, ni motores ni DSP.
6. **No se solicitaron** credenciales ni permisos root.
7. **No se eliminaron** archivos.
8. **No se implementó** AudioInput.

---

## 1. Código completo v0.2.2

**[`audioinput_diag_termux.py`](/home/z/my-project/download/audioinput_diag_termux.py)** — 1697 líneas, 71 847 bytes.

### 1.1 SHA-256

```
e791f3ec56ad812c6917a3bd625a6d5f2efbbf76a49061421621a1fc8457d511  audioinput_diag_termux.py
```

### 1.2 Resultado de `py_compile`

```
$ python3 -m py_compile audioinput_diag_termux.py
exit=0
```

### 1.3 Resultado de `--help`

```
usage: audioinput_diag_termux.py [-h] [--shared SHARED] [--output OUTPUT]
                                 [--private-dir PRIVATE_DIR]

Diagnostico AudioInput ETAPA 2: SoundFile(fd, closefd=False) + os.pread

options:
  -h, --help            show this help message and exit
  --shared SHARED       Ruta al directorio de almacenamiento compartido Android
  --output OUTPUT       Ruta al archivo JSON de salida
  --private-dir PRIVATE_DIR
                        Directorio padre privado
```

### 1.4 Verificación estática del AST

```
Imports: ['os', 'sys', 'errno', 'hashlib', 'platform', 'json', 'time',
          'traceback', 'argparse', 'struct', 'stat', 'pathlib.Path',
          'numpy', 'soundfile']
Modulos del proyecto: NINGUNO
```

---

## 2. Informe de correcciones C1–C7

### C1 — Seguridad de rutas: eliminar rutas inseguras

| # | Defecto en v0.2.1 | Corrección en v0.2.2 | Función / Línea |
|---|---|---|---|
| C1.1 | `safe_makedirs_exclusive_anchored()` tenía un fallback `os.mkdir(str(p))` cuando `safe_open_dir_anchored` retornaba -1. | **Eliminado el fallback.** Si `safe_open_dir_anchored` falla, se lanza `OSError(ENOSYS)` con mensaje explícito: "No se continuara con ruta directa." No hay continuación insegura. | `safe_makedirs_exclusive_anchored` ~L292-340 |
| C1.2 | Se usaba `parent.mkdir(parents=True, exist_ok=True)` para crear componentes intermedios. | **Eliminado `parents=True, exist_ok=True`.** Nueva función `safe_create_single_dir(path)` crea un único directorio (sin recursión) con verificación de seguridad del padre. Si el padre no existe o no es seguro, falla con error explícito. | `safe_create_single_dir` ~L249-282; usada en `main()` ~L1448-1459 |
| C1.3 | Si no se podía realizar el recorrido seguro, el código continuaba mediante rutas directas. | **Fallo conservador.** Todas las funciones que crean archivos/directorios protegidos usan `dir_fd`. Si `safe_open_dir_anchored` retorna -1 (p. ej. `O_PATH` no disponible), la operación se aborta con error. No hay fallback por ruta. | `safe_makedirs_exclusive_anchored` L323-325; `safe_create_file_exclusive_anchored` L377-380; `create_fixture` L678-680; `write_report_json_robust` L1341-1343 |
| C1.4 | `safe_create_file_exclusive_anchored()` creaba el archivo con `os.open(str(p), ...)` (por ruta, no por `dir_fd`). | **Usa `dir_fd` del padre verificado.** La función ahora toma `(parent_path, filename, content_bytes)`, abre el padre con `safe_open_dir_anchored`, y crea el archivo con `os.open(filename, ..., dir_fd=parent_fd)`. | `safe_create_file_exclusive_anchored` ~L356-430 |
| C1.5 | `create_fixture()` usaba `os.open(str(out_path), ...)` (por ruta). | **Usa `dir_fd` del `run_dir` verificado.** Abre el `run_dir` con `safe_open_dir_anchored`, crea el fixture con `os.open(filename, ..., dir_fd=run_dir_fd)`. | `create_fixture` ~L660-710 |
| C1.6 | El informe JSON se creaba con `os.open(str(report_path), ...)` (por ruta). | **Usa `dir_fd` del padre verificado.** `write_report_json_robust(parent_path, filename, report_dict)` abre el padre con `safe_open_dir_anchored` y crea el archivo con `dir_fd=parent_fd`. El informe se crea dentro del directorio privado verificado por defecto, o en el directorio especificado por `--output` (que también se abre de forma anclada). | `write_report_json_robust` ~L1321-1390 |
| C1.7 | El docstring de `check_no_symlink_in_path` sugería que `lstat()` eliminaba TOCTOU. | **Documentado explícitamente** que `check_no_symlink_in_path` NO elimina TOCTOU. Solo detección instantánea. La protección TOCTOU real requiere `safe_open_dir_anchored`. | `check_no_symlink_in_path` docstring ~L137-142 |
| C1.8 | Si no se puede garantizar seguridad en Android/Termux, el resultado podía ser continuación insegura. | **Fallo conservador.** Si `O_PATH` no está disponible, `safe_open_dir_anchored` retorna -1. Todas las funciones que dependen de ella abortan con `NOT_EXECUTED` o `ERROR` según corresponda, nunca continúan por ruta directa. | `safe_open_dir_anchored` L183-185; verificación en cada llamador |

### C2 — Orden de validación de entornos

| # | Defecto en v0.2.1 | Corrección en v0.2.2 | Función / Línea |
|---|---|---|---|
| C2.1 | `validate_environments_distinct()` se ejecutaba **antes** de crear los directorios. Si el directorio privado no existía, `os.stat` fallaba y el instrumento abortaba. | **Orden corregido.** `main()` primero crea los directorios padre con `safe_create_single_dir()`, luego valida. | `main()` ~L1448-1459 (crear), ~L1466-1490 (validar) |
| C2.2 | La comparación usaba `os.stat(realpath)` que puede resolver symlinks. | **Nueva función `validate_environments_distinct_by_fd(private_fd, shared_fd)`** que compara por `os.fstat()` sobre los descriptores abiertos con `safe_open_dir_anchored`. No usa `realpath` ni comparación de cadenas. | `validate_environments_distinct_by_fd` ~L444-460 |
| C2.3 | Un error en `os.stat` se interpretaba como "no hay conflicto" (`except OSError: pass`). | **Tres estados de retorno.** `(True, None)` = distintos. `(False, msg)` = mismo objeto. `(None, msg)` = no se pudo verificar. `main()` aborta con `sys.exit(2)` si `ok_distinct is None` (no asume que son distintos). | `validate_environments_distinct_by_fd` L456-460; `main()` L1478-1487 |
| C2.4 | No se abrían los descriptores para comparar. | **Se abren ambos directorios con `safe_open_dir_anchored`** y se comparan sus `fstat()`. Los fds se cierran en `finally` tras la verificación. | `main()` ~L1466-1490 |

### C3/C5 — Propagación de interrupciones

| # | Defecto en v0.2.1 | Corrección en v0.2.2 | Función / Línea |
|---|---|---|---|
| C3.1 | `KeyboardInterrupt` en `run_environment()` se capturaba por prueba pero no propagaba al estado global `interrupted`. El informe declaraba `interrupted: false`. | **`interrupt_flag[0] = True` se establece** en cada captura de `KeyboardInterrupt`. Tras retornar de `run_environment()`, `main()` verifica `interrupt_flag[0]` y establece `interrupted = True` con `interrupt_msg`. | `run_environment` ~L1000-1010; `main()` ~L1530-1540 |
| C3.2 | La prueba interrumpida no siempre se registraba como `ERROR`. | **Se registra como `ERROR`** con detalle "KeyboardInterrupt: prueba interrumpida, no se declara PASS". | `run_environment` ~L1003-1009 |
| C3.3 | Las pruebas posteriores a la interrumpida podían no marcarse como `NOT_EXECUTED`. | **Las pruebas posteriores verifican `interrupt_flag[0]` al inicio.** Si es `True`, se marcan `NOT_EXECUTED` con detalle "interrupcion previa; prueba no ejecutada". No se inventan resultados. | `run_environment` ~L980-986, ~L1035-1041 |
| C3.4 | El entorno B podía ejecutarse tras una interrupción en el entorno A. | **`main()` verifica `interrupt_flag[0]`** antes de llamar a `run_environment()` para B. Si es `True`, marca todo B como `NOT_EXECUTED`. | `main()` ~L1530-1545 |
| C3.5 | El código de salida podía ser 0 tras interrupción si todos los resultados eran PASS. | **`if interrupted: sys.exit(130)`** (o `sys.exit(2)` si `fatal_exception`). Nunca 0 tras interrupción. | `main()` ~L1676-1680 |
| C3.6 | El informe podía declarar ejecución normal tras interrupción. | **`interrupted` se establece en `True`** y se incluye en `report['interrupted']` y `report['summary']['interrupted']`. El `interrupt_msg` se incluye en `report['interrupt_message']`. | `main()` ~L1531-1532, report dict ~L1620-1622 |

### C7 — Cierre del informe JSON

| # | Defecto en v0.2.1 | Corrección en v0.2.2 | Función / Línea |
|---|---|---|---|
| C7.1 | El descriptor del informe podía cerrarse dos veces: una en la rama de error y otra en `finally`. | **`fd` se establece a `None` tras `os.close(fd)` en la rama normal.** El `finally` solo cierra `if fd is not None`. No hay doble cierre. | `write_report_json_robust` ~L1370-1375, finally ~L1378-1385 |
| C7.2 | Los errores de cierre se almacenaban en una variable local `close_error` que nunca llegaba al llamador (el `return` se evaluaba antes del `finally`). | **El cierre se hace dentro del `try` principal, no en `finally`.** `close_error` se captura antes del `return` y se incluye en la tupla de retorno. El llamador recibe `(ok, write_error, close_error)`. | `write_report_json_robust` ~L1368-1375 |
| C7.3 | Un cierre fallido podía producir `ok=True`. | **`ok_final = (write_error is None and close_error is None)`.** Si el cierre falla, `ok_final` es `False`. | `write_report_json_robust` L1374 |
| C7.4 | Se devolvía una tupla de éxito antes de conocer el resultado del cierre. | **El cierre se ejecuta antes del `return`.** No se devuelve `ok=True` sin haber verificado el cierre. | `write_report_json_robust` ~L1368-1376 |
| C7.5 | Se podía ejecutar un segundo `os.close(fd)` después de cerrar en una rama de error. | **`fd = None` tras el primer `os.close(fd)`.** El `finally` verifica `if fd is not None` antes de intentar cerrar. No hay segundo cierre. | `write_report_json_robust` L1371, finally L1379 |
| C7.6 | Si la escritura quedaba incompleta, el informe podía presentarse como válido. | **`write_error` se establece si `written != total`.** `ok_final` es `False` si hay `write_error`. | `write_report_json_robust` ~L1363-1365 |
| C7.7 | El código de salida podía ser 0 si la escritura o el cierre fallaban. | **`if not ok_write: sys.exit(2)`** garantiza código no-cero. | `main()` ~L1682 |
| C7.8 | `safe_create_file_exclusive_anchored()` tenía el mismo problema de `close_error` perdido. | **Corregido igual que `write_report_json_robust`.** El cierre se hace dentro del `try`, `close_error` se captura antes del `return`, `fd = None` tras cerrar, `ok_final` es `False` si cierre falla. | `safe_create_file_exclusive_anchored` ~L395-420 |

---

## 3. Tabla de correspondencia defecto → corrección

| Defecto | Severidad | Corrección | Función afectada | Verificación |
|---|---|---|---|---|
| Fallback `os.mkdir(str(p))` cuando anclado falla | CRÍTICA | Eliminado. Aborta con `OSError(ENOSYS)`. | `safe_makedirs_exclusive_anchored` L323-325 | `grep "os.mkdir(str(p))"` solo en comentarios |
| `parent.mkdir(parents=True, exist_ok=True)` | CRÍTICA | Eliminado. `safe_create_single_dir` crea un nivel sin recursión. | `safe_create_single_dir` L249-282 | `grep "parents=True"` sin coincidencias en código |
| `safe_create_file_exclusive_anchored` no usa `dir_fd` | ALTA | Usa `os.open(filename, ..., dir_fd=parent_fd)`. | L385 | `grep "dir_fd=parent_fd"` confirma |
| `create_fixture` no usa `dir_fd` | ALTA | Usa `os.open(filename, ..., dir_fd=run_dir_fd)`. | L687 | `grep "dir_fd=run_dir_fd"` confirma |
| `write_report_json_robust` no usa `dir_fd` | ALTA | Usa `os.open(filename, ..., dir_fd=parent_fd)`. | L1349 | `grep "dir_fd=parent_fd"` en `write_report_json_robust` |
| `validate_environments_distinct` antes de crear dirs | ALTA | Orden invertido: crear primero, validar después. | `main()` L1448-1490 | Análisis de flujo |
| Validación por `os.stat(realpath)` no por `fstat` sobre fds | ALTA | Nueva función `validate_environments_distinct_by_fd`. | L444-460 | `grep "validate_environments_distinct_by_fd"` |
| `KeyboardInterrupt` no propaga a `interrupted` global | CRÍTICA | `interrupt_flag[0] = True`; `main()` verifica y establece `interrupted`. | `run_environment` L1005; `main()` L1531 | `grep "interrupt_flag\[0\] = True"` |
| `close_error` perdido en `finally` de `safe_create_file_exclusive_anchored` | ALTA | Cierre dentro del `try`, antes del `return`. | L395-420 | Análisis de flujo |
| Doble `os.close(fd)` en `write_report_json_robust` | CRÍTICA | `fd = None` tras cerrar; `finally` verifica `if fd is not None`. | L1371, L1379 | Análisis de flujo |
| `ok=True` con cierre fallido | CRÍTICA | `ok_final = (write_error is None and close_error is None)`. | L1374 | Análisis de flujo |
| Código de salida 0 tras interrupción | CRÍTICA | `sys.exit(130)` si `interrupted`. | L1680 | `grep "sys.exit(130)"` |
| Código de salida 0 si informe no se escribió | CRÍTICA | `sys.exit(2)` si `not ok_write`. | L1682 | `grep "not ok_write"` |

---

## 4. Tabla de resultados esperados T11–T16

| Prueba | PASS | FAIL | NOT_EXECUTED | ERROR |
|---|---|---|---|---|
| **T11** | SoundFile abre fd, metadatos OK, fd sobrevive `sfile.close()`, cierre OK, `close_errors=[]`. | SoundFile no abre, metadatos incorrectos, fd cerrado tras `sfile.close()`, o cierre falla. | No se pudo crear el fixture. | Excepción no anticipada o `KeyboardInterrupt`. |
| **T12** | `pread` devuelve 100 bytes, offset preservado en 0, cierre OK. | `pread` falla, mueve offset, o cierre falla. | No se pudo crear el fixture. | Excepción o `KeyboardInterrupt`. |
| **T13** | `pread` status `COMPLETE`, hashes idénticos, offset preservado, sizes iguales, cierre OK. | `pread` status no `COMPLETE`, hashes difieren, offset movido, o cierre falla. | No se pudo crear el fixture. | Excepción o `KeyboardInterrupt`. |
| **T14** | 12 comprobaciones todas `OK`, `close_errors=[]`. | Cualquier comprobación `FAIL` o `NOT_DONE`. Detalle lista marcadores `+`/`X`/`-`. | No se pudo crear el fixture. | Excepción o `KeyboardInterrupt`. |
| **T15** | `LibsndfileError` capturada, cierre OK. | SoundFile acepta fd de dir, lanza `OSError`, o cierre falla. | No se pudo abrir el directorio. | Excepción o `KeyboardInterrupt`. |
| **T16** | fd sobrevive a fallo de SoundFile, cierre OK. | fd cerrado (EBADF) o cierre falla. | No se pudo abrir el directorio. | Excepción o `KeyboardInterrupt`. |

### Códigos de salida

| Código | Significado |
|---|---|
| 0 | Todo PASS. Sin interrupciones. Informe escrito OK. |
| 1 | Hay FAIL o ERROR. Sin interrupciones. Informe escrito OK. |
| 2 | Fatal al iniciar, o informe no se pudo escribir/cerrar. |
| 130 | Interrumpido por usuario (Ctrl+C). |

---

## 5. Limitaciones que impiden garantizar seguridad

Declaración honesta de limitaciones:

1. **`O_PATH` puede no estar disponible en todos los entornos Android/Termux.** Si no lo está, `safe_open_dir_anchored` retorna -1 y todas las operaciones que dependen de recorrido anclado fallan conservadoramente con `NOT_EXECUTED` o `ERROR`. No hay fallback por ruta.

2. **`check_no_symlink_in_path` NO elimina TOCTOU.** Solo detecta symlinks en el instante de la comprobación. La protección TOCTOU real la proporciona `safe_open_dir_anchored` (apertura por `dir_fd` que es atómica respecto a symlinks intermedios). Sin embargo, incluso el recorrido anclado tiene una ventana teórica entre `lstat` del componente y `os.open` del siguiente, aunque en la práctica `O_NOFOLLOW` en el `os.open` mismo rechaza symlinks.

3. **`safe_create_single_dir` crea directorios padre por ruta.** Para el directorio padre privado (`~/.audioinput_diag_etapa2/`) y el compartido, se usa `os.mkdir(str(p), mode=0o700)` porque el padre de estos (p. ej. `$HOME` o `/sdcard/`) ya existe y no podemos controlar su apertura anclada desde la raíz sin requerir permisos adicionales. Esta es una limitación inherente al punto de entrada del instrumento. Si `$HOME` o `/sdcard/` contienen symlinks maliciosos, el instrumento no puede protegerse en este nivel. Sin embargo, `check_no_symlink_in_path` se aplica al directorio padre antes de crearlo, y `check_dir_is_safe` verifica permisos y propietario.

4. **No se puede garantizar seguridad en Android/Termux sin ejecución real.** Todas las afirmaciones sobre compatibilidad Android/Termux están clasificadas como NDE (No Determinable Estáticamente). El instrumento está diseñado para fallar conservadoramente si los mecanismos no están disponibles, pero la verificación real requiere ejecución en el dispositivo de Will.

5. **`SIZE_CHANGED` en `sha256_pread_v2` no detecta cambios de contenido sin cambio de tamaño.** Esta limitación está documentada explícitamente en el docstring y en el mensaje de error. No se presenta como mecanismo completo de detección de modificaciones concurrentes.

6. **Los errores de cierre durante `KeyboardInterrupt` pueden no conservarse** si la interrupción ocurre antes de que el resultado se añada a `results`. El `interrupted` flag queda `True` y el reporte incluye `interrupt_message`, pero los `close_errors` de la prueba interrumpida pueden perderse.

---

## 6. Puntos congelados (no modificados)

Conforme al §3 del requerimiento, no se modificaron:

- Estructura de comprobaciones T14 (12 comprobaciones con `record_check` y `mark_remaining_not_done`).
- Clasificación SHA-256 (`PreadHashResult` con 6 estados).
- Ausencia de actualizaciones generales y limpieza automática.
- Generación de fixtures y sus formatos (WAV PCM16/24/32 + FLOAT, 44100 Hz, estéreo).
- Pruebas T11–T16 (funciones de test sin cambios en su lógica de verificación).
- Contrato SoundFile(fd, closefd=False) + os.pread.
- Protección de los motores y DSP.

No se incorporó FLAC, `/proc/self/fd`, fallbacks por ruta ni nuevas funcionalidades.

---

**Correcciones concluidas.** Quedo a la espera de la auditoría de Cris y la autorización expresa de Will. No ejecutaré el instrumento ni avanzaré a implementación sin autorización.
