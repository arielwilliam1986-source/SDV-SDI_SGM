# INFORME DE CORRECIONES — AudioInput ETAPA 2 **v0.2.4 (última corrección técnica)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Versión de partida:** v0.2.3 (commit [`21fd0e6`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/21fd0e6))
**Versión entregada:** v0.2.4
**Auditor independiente:** Cris (ChatGPT) | **Implementación:** Arena
**Fecha:** 2026-11-21
**Condición:** entrega publicada; **no equivale a aprobación técnica**. Requiere la
última auditoría independiente de Cris (Código, pruebas y diff) antes de la
congelación de la versión.

---

## 1. Objetivo y principio de corrección

Última corrección técnica, **estrictamente delimitada**, sobre los defectos
residuales identificados en la auditoría independiente de v0.2.3. Tres áreas:

- **C1:** publicación segura del informe JSON.
- **C4:** propiedad e identidad de los descriptores y conservación de errores de cierre.
- **C5:** propagación completa de interrupciones y registro de pruebas no ejecutadas.

No se reescribió el instrumento, no se amplió funcionalidad ni se introdujo nueva
arquitectura. **No se amplió el alcance y no se reconstruyó el instrumento.**

**Restricciones respetadas:** no se ejecutó Android/Termux; no se usó root; no se
accedió a muestras reales del proyecto; no se modificaron motores ni código DSP; no
se tocó el branch `main`; no se fusionaron ramas; no se eliminó archivo alguno
automáticamente; los apartados congelados (T11–T16, `sha256_pread_v2()`,
clasificaciones SHA-256, `SoundFile(fd, closefd=False)`, `os.pread()`, formatos y
subtipos WAV, señales sintéticas, criterios PASS/FAIL — salvo la clasificación de
interrupciones — y metadatos) no se modificaron.

---

## 2. Commits y enlaces

| Commit | Padre | Contenido |
|---|---|---|
| [`a3dcb88`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/a3dcb88) | [`21fd0e6`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/21fd0e6) (v0.2.3) | `.py` v0.2.4 + [diff v0.2.3→v0.2.4](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/etapa2/DIFF_v0_2_3_A_v0_2_4.patch) + [pruebas unitarias](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/etapa2/pruebas_unitarias_v0_2_4.py) |
| (este informe) | `a3dcb88` | `INFORME_CORRECCIONES_v0_2_4.md` |

- Instrumento v0.2.4: [blob](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py)
- Instrumento v0.2.3 (base): [blob en commit 21fd0e6](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/21fd0e6/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py)
- Rama autorizada: `arena/audioinput-diag-etapa2` (base `b64f15a` de `main`)

---

## 3. Identificación del objeto y recovery point

Antes de modificar se confirmó la identidad del archivo:

- **SHA-256 de entrada (v0.2.3):** `4ce798095baf1c8e6b7008a9d9a17c44d553e7240d57bcbe44be7505336d3e08`
- **Tamaño / líneas de entrada:** 102951 bytes / 2248 líneas
- **Recovery point verificable:** `/tmp/diag_v023_recovery.py` — SHA-256 idéntico al de entrada

---

## 4. Funciones modificadas y justificación

### C1 — Publicación segura del informe JSON

| Función | Modificación | Justificación (defecto residual) |
|---|---|---|
| **`write_report_json_robust(report_path, report_dict)`** | **Publicación atómica anclada:** la publicación se realiza con `os.link(tmp_name, report_path.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)` — **nombres relativos** a los descriptores del directorio, operación **atómica** que falla con `EEXIST` si el destino existe, sin sobrescribirlo. **Eliminado** el `os.path.exists()` + `os.rename()` (carrera TOCTOU). **Eliminado** el `os.link()` con rutas completas. Si el mecanismo anclado no está disponible (`NotImplementedError` u otro `OSError`), **se conserva el provisional y se reporta explícitamente** "informe no publicado" con el motivo. El `unlink` del provisional se realiza **solo tras la publicación exitosa** y **solo sobre el provisional creado por este proceso** (origen acreditado); un fallo del unlink se conserva para trazabilidad pero no invalida la publicación. | Defecto: `os.link()` con rutas completas y fallback `os.path.exists()`+`os.rename()` con carrera TOCTOU que podía sobrescribir un destino creado concurrentemente. La creación del provisional por `dir_fd` se mantiene (ítem 1 de la corrección requerida). |

### C4 — Propiedad e identidad de descriptores

| Función | Modificación | Justificación (defecto residual) |
|---|---|---|
| **Nueva: `_reconcile_interrupted(interrupt_flag, interrupted, interrupt_msg)`** | Helper de reconciliación del estado global de interrupción (C5, testable). | C5: toda interrupción debe reflejarse en `interrupted`. |
| **Nueva: `_close_fd_tracked(fd, label)`** | Cierre que **conserva** el error en el sink y lo devuelve; sustituye los `except OSError: pass`. | C4: persistían rutas de cierre que ignoraban errores mediante `except OSError: pass`. |
| **`CloseErrorLogger`** | **Modelo explícito de propiedad por apertura:** `register_fd()` asigna un **token único de apertura** por apertura concreta. `close_fd(fd, label, token=None)`: con token, se cierra **solo** la apertura identificada (token obsoleto/desconocido no cierra nada); sin token, solo se cierra si hay una apertura registrada como `'open'` para el fd. Se verifica la identidad `(st_dev, st_ino)` contra la registrada antes de cerrar. **`(fd, st_dev, st_ino)` no se considera identidad suficiente por sí sola**: dos aperturas del mismo archivo tienen tokens distintos, y un número de fd reutilizado no se cierra a través de un registro antiguo. **No se reintenta `os.close()`** tras un error ambiguo: el error se registra y se devuelve. Los avisos (token obsoleto, fd no registrado, identidad distinta) se guardan en `warnings`, los fallos reales en `errors`. | Defecto: `(fd, dev, ino)` no distingue dos aperturas independientes del mismo archivo; persistían cierres con `except OSError: pass`. |
| **`safe_open_dir_anchored()`** | Los dos `except OSError: pass` de los cierres de cadena se sustituyen por `_close_fd_tracked()`. | C4: revisar cierres; sin silencio de errores. |
| **`_ensure_parents_anchored()`** | Los dos `except OSError: pass` de los cierres de cadena se sustituyen por `_close_fd_tracked()`. | C4: revisar cierres. |
| **`safe_makedirs_exclusive_anchored()`** | Cierres del descriptor de verificación y del `parent_fd`: `except OSError: pass` → `_close_fd_tracked()`. | C4: revisar cierres. |
| **`create_fixture()`** | El descriptor del fixture se **registra con token** (`closer.register_fd`) y se cierra asociado al token; el `parent_fd` se cierra con `_close_fd_tracked()`. | C4: propiedad registrada por apertura; sin silencio de errores. |
| **`write_report_json_robust()`** | El `tmp_fd` se registra con token y se cierra asociado al token; el **cierre del `parent_fd` se conserva y se reporta** en el resultado (`close_err`), combinado con los errores del cierre del provisional. | C4 + C1: conservar y reportar los errores de cierre del descriptor del directorio. |
| **`main()`** | El `env_close_errors` (sink) se drena y se incluye en el informe (mantenido de v0.2.3). | C4: conservación de errores de cierre a nivel de entorno. |

**Error primario vs secundario de cierre:** en todos los resultados, el error
primario de ejecución queda en `status`/`detail` y los errores secundarios de
cierre en `close_errors` (resultados de prueba) o en el tercer valor de retorno
(`close_err` de `write_report_json_robust`). Son campos distintos y ambos
conservados.

### C5 — Interrupciones y resultados incompletos

| Función | Modificación | Justificación (defecto residual) |
|---|---|---|
| **`run_environment()` — bucle de fixtures** | **KI durante `create_fixture()`:** se captura `KeyboardInterrupt`, se **setea `interrupt_flag[0] = True`** (estado global), se registra **ERROR** para la T11 del fixture interrumpido (nunca PASS), **NOT_EXECUTED** para T12–T14 del mismo fixture y para las T11–T14 de los fixtures posteriores, se **conservan los errores de cierre** (sink drenado hacia `close_errors`) y se rompe el bucle. **Interrupción previa** en el bucle: los fixtures restantes se registran como **NOT_EXECUTED** sin crearlos. | C5: la interrupción durante la creación de fixtures no quedaba cubierta. |
| **`main()`** | Los handlers de `KeyboardInterrupt` y de excepciones genéricas **setean `interrupt_flag[0] = True`** (coherencia del estado global). La reconciliación `interrupted` se delega en `_reconcile_interrupted()`. El segundo entorno se decide con `not interrupt_flag[0]`, por lo que **no se inicia tras una interrupción del primero**. El código de salida en interrupción es 130 (KI) o 2 (excepción fatal) — siempre no nulo. | C5: toda interrupción debe reflejarse en `interrupted`; rc no nulo; segundo entorno no iniciado. |
| **`write_report_json_robust()`** | La escritura del JSON se realiza en provisional; **una KI durante la escritura se propaga** y el `finally` cierra los descriptores conservando errores: **no se publica** un informe incompleto; el provisional queda en disco y se informa. | C5: la interrupción durante la escritura del JSON debe impedir publicar un informe incompleto. |
| **`SCRIPT_VERSION`** | `"0.2.3"` → `"0.2.4"`. Notas del informe JSON actualizadas (C1/C4/C5 v0.2.4). | Identificación de versión. |

---

## 5. Verificaciones exigidas (resultados reales)

| # | Verificación | Resultado |
|---|---|---|
| C1 | Destino creado concurrentemente entre preparación y publicación → destino intacto, publicación falla sin sobrescribirlo | **PASS** — `C1_publicacion_concurrente_destino` |
| C1 | Comportamiento cuando el mecanismo seguro no está disponible | **PASS** — `C1_mecanismo_no_disponible` (provisional conservado, mensaje explícito "no publicado") |
| C1 | Creación del provisional por `dir_fd` (mantenida) | **PASS** — `C1_regressions` + `C1_publicacion_exitosa` |
| C4 | Dos aperturas independientes del mismo archivo | **PASS** — `C4_dos_aperturas_mismo_archivo` (tokens distintos; cierre de una no afecta a la otra) |
| C4 | Reutilización del número FD tras cerrar el primer recurso | **PASS** — `C4_reutilizacion_numero_fd` (token obsoleto/registro ausente → no se cierra el recurso reutilizado) |
| C4 | Intento de cierre repetido | **PASS** — `C4_cierre_repetido` (aviso, no error) |
| C4 | Error de cierre simulado | **PASS** — `C4_error_cierre_simulado` (registrado y devuelto) |
| C4 | Error de cierre durante una excepción | **PASS** — `C4_error_cierre_durante_excepcion` (primario y secundario conservados) |
| C4 | Error de cierre durante `KeyboardInterrupt` | **PASS** — `C4_error_cierre_durante_keyboardinterrupt` |
| C4 | Sin silencio de errores de cierre (`except OSError: pass`) | **PASS** — `C4_no_silencio_cierres_revisados` (solo permanece la consulta `_identity`, no un cierre) |
| C5 | `KeyboardInterrupt` durante prueba T11–T16 | **PASS** — `C5_ki_durante_prueba` (ERROR, posteriores NOT_EXECUTED, flag seteado) |
| C5 | `KeyboardInterrupt` durante `create_fixture()` | **PASS** — `C5_ki_durante_create_fixture` (flag, ERROR, NOT_EXECUTED, close_errors conservados) |
| C5 | `KeyboardInterrupt` durante la escritura del JSON | **PASS** — `C5_ki_durante_escritura_json` (KI propagada, sin publicación, provisional conservado) |
| C5 | Informe no declara ejecución completa | **PASS** — `C5_informe_no_declara_completo` (`interrupted: true` en informe y resumen) |
| C5 | Pruebas posteriores NOT_EXECUTED | **PASS** — `C5_ki_durante_prueba`, `C5_ki_durante_create_fixture` |
| C5 | Estado global de interrupción verdadero | **PASS** — `C5_informe_no_declara_completo` (reconciliación) |
| C5 | Segundo entorno no iniciado | **PASS** — `C5_segundo_entorno_no_iniciado` (la flag gatea la decisión de main) |
| — | `py_compile` | **PASS** — OK |
| — | `--help` | **PASS** — interfaz del instrumento correcta |
| — | Prueba de humo de `main()` (entorno no Android) | **PASS** — banner v0.2.4, dir privado creado 0700, rc=2 por dependencias ausentes (no 0) |

### Pruebas no ejecutadas (NOT_EXECUTED, con explicación, nunca PASS inventado)

- **Pruebas T11–T16 del instrumento con fixtures reales y la ruta completa de
  `run_environment`/`create_fixture` con numpy/soundfile reales:** **NOT_EXECUTED**.
  Explicación: el entorno de trabajo **no tiene `numpy` ni `soundfile`** instalados
  y el alcance prohíbe instalar dependencias o ejecutar audio/DSP. Se ejercen
  estos caminos mediante simulación controlada (harness con FIXTURE_SPECS vacío y
  funciones de prueba/fixture sustituidas), que cubre la lógica de propagación y
 registración; la ejecución real con señales sintéticas queda NOT_EXECUTED.
- **Android/Termux:** **no ejecutado** (prohibido por el alcance). No se declara
  compatibilidad Android/Termux.

---

## 6. Resultados individuales de las pruebas unitarias

**Harness:** `herramientas/diagnostico_audio/etapa2/pruebas_unitarias_v0_2_4.py`
(artefacto de entrega, commit `a3dcb88`).

**Método:** importar el módulo por ruta y ejercer las funciones corregidas sobre
directorios temporales. **No** Android/Termux, **no** audio, **no** muestras reales.

**Resultado:** `TOTAL 16 | PASS 16 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0`

```
PASS C1_publicacion_concurrente_destino
PASS C1_mecanismo_no_disponible
PASS C1_publicacion_exitosa
PASS C1_regressions
PASS C4_dos_aperturas_mismo_archivo
PASS C4_reutilizacion_numero_fd
PASS C4_cierre_repetido
PASS C4_error_cierre_simulado
PASS C4_error_cierre_durante_excepcion
PASS C4_error_cierre_durante_keyboardinterrupt
PASS C4_no_silencio_cierres_revisados
PASS C5_ki_durante_prueba
PASS C5_ki_durante_create_fixture
PASS C5_ki_durante_escritura_json
PASS C5_informe_no_declara_completo
PASS C5_segundo_entorno_no_iniciado
```

---

## 7. Datos de la entrega

| Artefacto | Valor |
|---|---|
| Archivo corregido | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **SHA-256 final (v0.2.4)** | `8cf68c25f9e2da72c3e7c36a40386f742b1cd91254e8c40da1d5704cb6fe98d3` |
| Tamaño final | 111488 bytes |
| Líneas finales | 2387 |
| SHA-256 del diff | generado con `diff -u` v0.2.3 → v0.2.4 (688 líneas de patch) |
| SHA-256 del harness | ver blob en commit `a3dcb88` |
| Commit de partida | [`21fd0e6`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/21fd0e6) (v0.2.3) |
| Commit de entrega (código) | [`a3dcb88`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/a3dcb88) (padre `21fd0e6`) |
| Rama | `arena/audioinput-diag-etapa2` (base `b64f15a` de `main`) |
| `py_compile` | OK |
| `--help` | OK |

---

## 8. Riesgos residuales

1. **Aprobación pendiente:** la entrega no equivale a aprobación técnica. Cris
   debe realizar la última auditoría independiente (código, pruebas, diff) antes
   de congelar la versión.
2. **Ejecución restringida:** no se ejecutó Android/Termux ni audio/DSP. Las
   pruebas T11–T16 con fixtures reales quedan NOT_EXECUTED (dependencias
   numpy/soundfile ausentes en el entorno de trabajo). Las lógicas de
   propagación/registro se verifican por simulación controlada en el harness.
3. **Publicación por enlace duro anclado:** `os.link` con `src_dir_fd`/`dst_dir_fd`
   es atómico y no sobrescribe. Si el sistema no lo admite, la función **conserva
   el provisional y reporta explícitamente** que el informe no pudo publicarse;
   no hay operación insegura de respaldo.
4. **Residuo de provisional:** tras un intento fallido de publicación (destino
   preexistente, mecanismo no disponible, escritura interrumpida), el informe
   provisional (`report-*.json.tmp`) queda en disco **sin limpieza automática**
   (por diseño: no se eliminan archivos cuyo origen no esté acreditado).
5. **Token de apertura:** el modelo de propiedad por token requiere que cada
   apertura se registre antes de cerrar. Los cierres sin registro se **evitan**
   (aviso) en vez de cerrar por número de fd; los puntos de uso internos están
   todos registrados.
6. **No se declara compatibilidad Android/Termux** basada en esta entrega.
7. **Cambio de contrato de retorno:** `safe_create_file_exclusive_anchored`
   retorna `(ok, error, close_error)` (3 valores, mantenido de v0.2.3);
   `close_fd` acepta el parámetro opcional `token` (mantenido como opcional para
   compatibilidad con llamados sin token).

---

## 9. Confirmaciones explícitas

- **No hubo ejecución Android/Termux** (prohibido por el alcance; no se declara
  compatibilidad Android/Termux).
- **No se usó root, no se accedió a muestras reales del proyecto, no se
  procesó audio ni DSP.**
- **No se modificó `main` (branch) ni los motores DSP**, ni se fusionaron ramas,
  ni se eliminó archivo alguno automáticamente.
- **No se reconstruyó el instrumento:** corrección delimitada sobre v0.2.3.
- **Solo se modificó el archivo autorizado** `audioinput_diag_termux.py`,
  además de los **artefactos de entrega**: `INFORME_CORRECCIONES_v0_2_4.md`,
  `DIFF_v0_2_3_A_v0_2_4.patch` y `pruebas_unitarias_v0_2_4.py`.
- **Los apartados congelados no se modificaron** (T11–T16 y objetivos
  funcionales, `sha256_pread_v2()`, clasificaciones SHA-256,
  `SoundFile(fd, closefd=False)`, `os.pread()`, formatos/subtipos WAV, señales
  sintéticas, criterios PASS/FAIL, metadatos).
