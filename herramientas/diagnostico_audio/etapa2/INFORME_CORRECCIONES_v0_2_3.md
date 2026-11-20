# INFORME DE CORRECIONES — AudioInput ETAPA 2 **v0.2.3 (provisional, no aprobada)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Base:** v0.2.1 (publicado en `arena/audioinput-diag-etapa2`, commit `ae1aa24`; SHA-256 `9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81`)
**Auditoría aplicada:** `AUDITORIA_ESTATICA_CIERRE_ETAPA2_V021.md` (commit `4d2eb42`)
**Decisor:** Will | **Auditor:** Cris | **Ejecutor:** Arena
**Fecha:** 2026-11-20

---

## 1. Alcance y principio de corrección

Corrección **controlada, mínima, trazable y conservadora**: se corrigen **exclusivamente**
los defectos **C1, C4 y C5** identificados en la auditoría estática de cierre v0.2.1.
No se reconstruye ni se sustituye el instrumento; no se elimina funcionalidad aceptada;
no se tocan los apartados congelados (T11–T16, `sha256_pread_v2()`, clasificaciones
SHA-256, `SoundFile(fd, closefd=False)` + `os.pread()`, formatos/subtypes WAV, señales
sintéticas, condiciones PASS/FAIL — salvo la clasificación de interrupción exigida por
C5 — ni metadatos). No se ejecutó Android/Termux, no se procesó audio, no se usaron
muestras reales ni motores/archivos originales. No se tocó el branch `main`, no se
fusionaron ramas, no se eliminó ningún archivo preexistente ni se hizo limpieza
automática.

**Estado:** v0.2.3 **provisional**. **No aprobada por Cris.** Requiere revisión y
aprobación explícita antes de cualquier uso o publicación adicional.

---

## 2. Commits y enlaces

| Commit | Padre | Contenido |
|---|---|---|
| [`dc07259`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/dc07259) | [`4d2eb42`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/4d2eb42) | `.py` corregido v0.2.3 + harness de pruebas unitarias |
| (este informe) | `dc07259` | `INFORME_CORRECCIONES_v0_2_3.md` |

- Instrumento corregido: [blob v0.2.3](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py)
- Informe de auditoría de base: [AUDITORIA_ESTATICA_CIERRE_ETAPA2_V021.md](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/AUDITORIA_ESTATICA_CIERRE_ETAPA2_V021.md)
- Instrumento v0.2.1 (base): [blob](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/audioinput-diag-etapa2/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py) (commit `ae1aa24`)
- Rama: `arena/audioinput-diag-etapa2` (base `b64f15a` de `main`)

---

## 3. Identificación del objeto y recovery point

Antes de modificar se confirmó la identidad del archivo:

- **SHA-256 de entrada (v0.2.1):** `9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81`
- **Tamaño / líneas de entrada:** 86575 bytes / 1922 líneas
- **Recovery point verificable:** `/tmp/diag_v021_recovery.py` — SHA-256 idéntico al de entrada

---

## 4. Funciones modificadas y justificación

### C1 — Creación segura de directorios y archivos (no hay fallbacks por ruta)

| Función | Modificación | Justificación (defecto auditado) |
|---|---|---|
| **Nueva: `_ensure_parents_anchored(path)`** | Recorrido componente a componente abriendo cada directorio con `O_PATH\|O_NOFOLLOW\|O_DIRECTORY` relativo al `dir_fd` del padre; los componentes ausentes se crean con `os.mkdir(name, mode=0o700, dir_fd=...)`. Si `O_PATH`/`O_DIRECTORY` no están disponibles, lanza `OSError(EOPNOTSUPP)`: **falla conservador, sin recurrir a ruta**. | C1: la auditoría confirmó el fallback `os.mkdir(str(p))` por ruta completa (audito 2.1). El nuevo mecanismo ancla la creación de padres a descriptores. |
| **`safe_makedirs_exclusive_anchored(path)`** | Eliminado el fallback `os.mkdir(str(p))` por ruta. La creación del componente final se realiza **siempre** con `os.mkdir(name, mode=0o700, dir_fd=parent_fd)`; verificación final del creado por descriptor (`fstat` del `O_PATH` anclado) en vez de `lstat` por ruta. Los padres se aseguran con `_ensure_parents_anchored`. Si la apertura anclada del padre falla, **falla conservador** con `OSError`. | C1 / hallazgo 2.1: el fallback por ruta permitía crear directorios sin el mecanismo anclado. Ahora no hay operación de creación por ruta; `O_NOFOLLOW` se aplica al componente final; no se usa comprobación previa de symlinks como sustituto del mecanismo anclado; no se borran dirs/archivos preexistentes (EEXIST/ELOOP se conservan). |
| **`safe_create_file_exclusive_anchored(path, content_bytes)`** | Eliminada la creación `os.open(str(p), ...)` por ruta completa (audito 2.2). Ahora: apertura anclada del padre (`safe_open_dir_anchored`), `os.open(name, ..., dir_fd=parent_fd)` con `O_WRONLY\|O_CREAT\|O_EXCL\|O_NOFOLLOW`, escritura en bucle (C7), cierre del fd y del `parent_fd` con conservación de errores. **Nuevo retorno `(ok, error, close_error)`**: los errores de cierre se conservan también en las rutas de escritura fallida. | C1 / hallazgo 2.2: creación de archivos por ruta completa. La comprobación previa de symlinks del padre se mantiene como rechazo anticipado, no como sustituto del mecanismo anclado. El cierre del `parent_fd` se garantiza en `finally`. |
| **`create_fixture(np, sf, dir_path, fixture_name, subtype, closer)`** | Creación del fixture **anclada** (`os.open(name, ..., dir_fd=parent_fd)`), eliminando `os.open(str(out_path), ...)` (audito 2.3). Se añade la verificación de symlinks del directorio fixture y se documenta explícitamente que un WAV parcial queda en disco (sin limpieza automática). | C1 / hallazgos 2.2 y 2.3: creación por ruta completa y falta de documentación del residuo. El cierre del `parent_fd` se garantiza en `finally`. |
| **`main()`** | Creación de los directorios padres privado/compartido: se sustituye `Path.mkdir(parents=True, ...)` por **`_ensure_parents_anchored(...)`** (creación anclada), con manejo conservador de `OSError` y `sys.exit(2)`. | C1: la instrucción autoriza explícitamente corregir la **función** `main()` (el branch `main` queda prohibido y no se tocó). |
| **`write_report_json_robust(report_path, report_dict)`** | Eliminada la creación `os.open(str(report_path), ...)` por ruta (audito 2.2). El informe se crea como **provisional exclusivo y anclado** (`os.open(name.tmp, ..., dir_fd=parent_fd)`), se escribe en bucle (C7), se `fsync` + verifica el tamaño por `fstat`, se verifica el cierre del descriptor (C4, identidad registrada), y se **publica** con `os.link` (enlace duro **atómico y sin sobrescritura**): si el informe final ya existe, `os.link` falla con `EEXIST` y **no se sobrescribe**; el provisional queda en disco (sin limpieza). Fallback documentado de rename con comprobación previa solo para sistemas sin enlaces duros. | C1 / hallazgo 2.2 + C5: creaciones por ruta completa en la escritura del informe. C5 exige: creación provisional exclusivo+anclado, bucle de escritura parcial, verificación de escritura/cierre, renombrado seguro sin sobrescritura, estado explícito del informe (publicado o provisional/incompleto/no publicado) y no sobrescribir informes anteriores. |

### C4 — Gestión de propiedad y cierre de descriptores

| Función | Modificación | Justificación (defecto auditado) |
|---|---|---|
| **Nueva: `_close_error_sink` / `_record_close_error` / `_drain_close_error_sink`** | Sink global que acumula errores de cierre producidos mientras una prueba se developa por una excepcion/interrupcion (los closers son locales a las pruebas y no accesibles desde el llamador). Se drena en los handlers de excepcion/interrupcion y en `run_environment`/`main`. | C4: conservación de errores de cierre que, sin esto, se perdían (audito 2.5). |
| **`CloseErrorLogger`** | Se elimina el uso del **número de fd como identidad**. Cada descriptor se registra (`register_fd`) con su **identidad actual `(st_dev, st_ino)`**, su propietario (label), estado (`open`/`closed`) y resultado de cierre. `close_fd` ahora: (a) un fd reutilizado por otro recurso (identidad distinta) **no se cierra** — aviso, no error; (b) un cierre duplicado del mismo recurso — aviso, no error; (c) fd inválido — error conservado y devuelto. `close_soundfile` evita dobles cierres por reutilización de `id()`. Se añade `warnings` distinto de `errors`. | C4 / hallazgo 2.4: `(fd, dev, ino)` no basta solo; el número de fd se reutiliza (cierre erróneo + fuga; skip registrado como error). Ahora la identidad es explícita y el propietario se registra. |
| **`run_environment(np, sf, ...)`** | El descriptor del ambiente se **registra** (`closer.register_fd`) y se **cierra siempre** en `finally` (todos los caminos, incluidos retornos anticipados, excepciones e interrupciones), registrando fallos al sink. Los handlers `KeyboardInterrupt` y de excepciones genéricas **ya no devolviendo `close_errors: []` fijo**: drena el sink y conserva los errores. Los errores de cierre de la creación de fixtures se reenvían al sink para que no se pierdan. | C4 / hallazgos 2.4 y 2.5: `close_errors: []` hardcodeado en handlers (L1413-1429, L1454-1461). |
| **`main()`** | Se drena el sink de errores de cierre a nivel de entorno y se incluye en el informe como campo **`environment_close_errors`** (aditivo, no altera resultados ni apartados congelados). | C4: conservación de errores de cierre a nivel de ejecución en el informe final. |
| **`write_report_json_robust(...)`** | El cierre del descriptor del provisional usa `CloseErrorLogger` (identidad registrada); fallos de cierre se conservan (sink + tercer valor de retorno). | C4: gestión de propiedad y conservación de errores de cierre en la escritura del informe. |

### C5 — Propagación y registro de interrupciones; escritura e integridad del informe

| Función | Modificación | Justificación (defecto auditado) |
|---|---|---|
| **`run_environment(...)`** | Interrupción absorbida a nivel de prueba: `KeyboardInterrupt` se registra como **ERROR** (nunca PASS), se setea `interrupt_flag[0] = True` y las pruebas posteriores se marcan **NOT_EXECUTED** (sin inventar resultados). Los resultados previos se conservan. | C5 / hallazgo 2.6 (parcial): `interrupted` no reflejaba interrupciones absorbidas. |
| **`main()`** | **Reconciliación explícita:** tras la ejecución, si `interrupt_flag[0]` está seteado y `interrupted` aún es `False`, se fija `interrupted = True` y se registra el motivo. El resumen y el informe JSON (`interrupted`, `summary.interrupted`) reflejan el **estado real**. El código de salida ya era ≠ 0 (130/2) en interrupción y se mantiene. | C5: `interrupt_flag` debe coincidir con `interrupted` global e `interrupted: true` en informe. |
| **`write_report_json_robust(...)`**** | Verificación `fsync` + tamaño antes del cierre; publicación sin sobrescritura; errores explícitos: **"informe incompleto, no publicado; provisional queda en disco"**, **"informe preexistente; no se sobrescribe"**, **"informe no publicado"**. | C5 / hallazgo 2.6: escritura incompleta no debe publicar informe válido; informes preexistentes no se sobrescriben; no se afirma durabilidad sin verificada (verificación fsync+tamaño). |
| **`SCRIPT_VERSION`** | `"0.2.1"` → `"0.2.3"`. Notas del informe JSON actualizadas para describir las correcciones C1/C4/C5 (v0.2.3). | Identificación de versión de la entrega. |

---

## 5. Verificaciones exigidas (resultados reales)

| # | Verificación | Resultado |
|---|---|---|
| 1 | No quedan fallbacks inseguros por ruta en C1 | **PASS** — prueba estática por AST: `os.mkdir(str(...))` ausente; `os.open(str(...))` con `O_CREAT` ausente. Las `os.open(str(...))` remanentes son **lecturas** de fixtures en T11–T16 (apartado congelado, no creación). |
| 2 | Creaciones ancladas correctas | **PASS** — `mkdir`/`open` con `dir_fd` presentes (≥2 y ≥3 respectivamente); pruebas funcionales `C1_ensure_parents_anchored`, `C1_safe_makedirs_exclusive_anchored`, `C1_safe_create_file_exclusive_anchored` PASS. |
| 3 | Gestión de propiedad FD y dobles cierres | **PASS** — `C4_close_error_logger_identity`, `C4_close_error_logger_fd_reuse` PASS (reutilización de número: aviso, no se cierra ajeno; doble cierre: aviso, no error). |
| 4 | Errores de cierre sobreviven a excepciones/interrupciones | **PASS** — `C4_close_error_logger_sink_conservation`, `C4_close_error_logger_close_soundfile`, `C5_run_environment_close_errors_conserved`, `C5_write_report_close_error_conserved` PASS. |
| 5 | `interrupted` coincide con el estado real | **PASS** — `C5_run_environment_interruption` (KI → ERROR, posteriores NOT_EXECUTED, flag seteado) y `C5_main_interrupted_coherence_static` (reconciliación en `main`) PASS. |
| 6 | Escritura incompleta no publica informe válido | **PASS** — `C5_write_report_json_robust`: provisional queda en disco, se informa explícitamente, no se publica. |
| 7 | Informes preexistentes no se sobrescriben | **PASS** — `C5_write_report_json_robust`: segundo intento contra camino existente falla con mensaje explícito y el contenido preexistente se conserva. |
| 8 | `py_compile` + `--help` | **PASS** — `python3 -m py_compile` OK; `--help` muestra la interfaz del instrumento. |
| 9 | Pruebas unitarias aisladas | **PASS** — 13/13 PASS (ver sección 6). |

### Prueba de humo del flujo `main()` (entorno no Android)

Ejecución con `--private-dir /tmp/v023_smoke/priv --output /tmp/v023_smoke/report.json`:

- Banner correcto: `Script: audioinput_diag_termux.py v0.2.3`
- Directorio privado creado con **modo 0700** (`drwx------`), creación anclada por `_ensure_parents_anchored`
- Sin numpy/soundfile: **falla conservadoramente** con `[FATAL] Dependencias no disponibles` y **código de salida 2** (no 0)
- No se creó informe JSON (el informe solo se escribe tras superar la verificación de dependencias)

---

## 6. Pruebas unitarias aisladas — resultados

**Harness:** `herramientas/diagnostico_audio/etapa2/pruebas_unitarias_v0_2_3.py` (artefacto de entrega, commit `dc07259`)

**Método:** importar el módulo por ruta (`importlib.util.spec_from_file_location`) y ejercer las funciones corregidas sobre directorios temporales. **No** se ejecuta Android/Termux, no se procesa audio, no se usan muestras reales.

**Resultado:** `TOTAL 13 | PASS 13 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0`

```
PASS C1_safe_makedirs_exclusive_anchored
PASS C1_ensure_parents_anchored
PASS C1_safe_create_file_exclusive_anchored
PASS C1_no_path_fallback_static
PASS C4_close_error_logger_identity
PASS C4_close_error_logger_fd_reuse
PASS C4_close_error_logger_sink_conservation
PASS C4_close_error_logger_close_soundfile
PASS C5_run_environment_interruption
PASS C5_run_environment_close_errors_conserved
PASS C5_main_interrupted_coherence_static
PASS C5_write_report_json_robust
PASS C5_write_report_close_error_conserved
```

**Pruebas no ejecutadas (NOT_EXECUTED, con explicación, nunca PASS inventado):**

- Pruebas **T11–T16 del instrumento** y la ruta completa de `run_environment`/`create_fixture`
  con fixtures reales: **NOT_EXECUTED**. Explicación: el entorno de trabajo **no tiene
  `numpy` ni `soundfile`** instalados, y la restricción prohíbe instalar dependencias o
  ejecutar audio/DSP. El flujo completo requiere estos módulos. Lo no ejecutable se
  reporta como NOT_EXECUTED, nunca PASS.
- **Android/Termux:** **no ejecutado** (prohibido por el alcance). La corrección se
  verifica en un entorno no Android; no se declara compatibilidad Android/Termux.

---

## 7. Datos de la entrega

| Artefacto | Valor |
|---|---|
| Archivo corregido | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **SHA-256 final** | `4ce798095baf1c8e6b7008a9d9a17c44d553e7240d57bcbe44be7505336d3e08` |
| Tamaño final | 102951 bytes |
| Líneas finales | 2248 |
| SHA-256 del harness de pruebas | `18ac9c1cc10541732dff7e17db06aa835ade5fa8b1cdd3de936513e7ff49ca67` |
| Diff vs v0.2.1 | 704 líneas cambiadas (515 añadidas) |
| `py_compile` | OK |
| `--help` | OK |
| Commit código | [`dc07259`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/dc07259) (padre `4d2eb42`) |
| Rama | `arena/audioinput-diag-etapa2` (base `b64f15a` de `main`) |

---

## 8. Limitaciones y riesgos residuales

1. **Aprobación pendiente:** v0.2.3 es **provisional**. Requiere revisión y aprobación
   explícita de Cris antes de cualquier uso o publicación adicional.
2. **Ejecución restringida:** no se ejecutó Android/Termux, ni audio/DSP, ni las pruebas
   T11–T16 con fixtures reales (dependencias numpy/soundfile ausentes en el entorno de
   trabajo). La corrección se verifica por inspección estática, pruebas unitarias aisladas
   de las funciones corregidas, `py_compile` y `--help` en entorno no Android.
3. **`O_NOFOLLOW` solo protege el componente final:** las protecciones ancladas cubren
   el componente creado/abierto en cada paso; los componentes intermedios se opening
   con `O_NOFOLLOW`, pero en sistemas sin `O_PATH`/`O_DIRECTORY` la función **falla
   conservador** (no hay fallback inseguro).
4. **Publicación del informe por enlace duro:** `os.link` es atómico y no sobrescribe;
   el fallback de rename solo aplica en sistemas sin enlaces duros y comprueva
   existencia previa (equivalente seguro en este contexto). En sistemas sin enlaces
   duros, existe una ventana de condición de carrera entre la comprobación y el rename
   (documentada, no aprovechable para sobrescribir informes preexistentes en la práctica
   del flujo usado).
5. **Residuo de provisional:** tras un intento fallido de publicación, el informe
   provisional (`report-*.json.tmp`) queda en disco **sin limpieza automática** (por
   diseño, no se eliminan archivos preexistentes ni se hace limpieza).
6. **No se declara compatibilidad Android/Termux** basada en esta entrega.
7. **Cambio de contrato de retorno:** `safe_create_file_exclusive_anchored` ahora
   retorna `(ok, error, close_error)` (3 valores) en vez de `(ok, error)` (2). No hay
   llamadores internos en el instrumento; es un cambio de API interno documentado.

---

## 9. Confirmaciones explícitas

- **No se ejecutó en Android/Termux** (prohibido por el alcance; no se declara
  compatibilidad Android/Termux).
- **No se ejecutó audio/DSP ni se usaron muestras reales** (prohibido).
- **No se tocó el branch `main`**, ni se fusionaron ramas, ni se eliminaron archivos
  preexistentes ni se hizo limpieza automática.
- **No se reconstruyó ni se sustituyó el instrumento:** corrección mínima sobre v0.2.1.
- **Solo se modificó el archivo autorizado** `audioinput_diag_termux.py`, además de
  los **artefactos de entrega** (`INFORME_CORRECCIONES_v0_2_3.md` y el harness de
  pruebas `pruebas_unitarias_v0_2_3.py`).
- **No se modificó** `audioinput_diag.py` (instrumento de rondas anteriores),
  `AGENTS.md`, motores/módulos DSP, fórmulas SDV/SDI, ni los apartados congelados
  T11–T16 y `sha256_pread_v2()`.
