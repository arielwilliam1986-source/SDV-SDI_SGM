# INFORME DE CORRECCIONES — AudioInput ETAPA 2 **v0.2.5 (C4/C5)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Versión de partida:** v0.2.4 (commit [`50bae98`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/50bae98eddd1b2f2b65c255e94d517003234a8e1); blob del script `72920aa077e3a660d6333c618e300f192b87bfd1`)
**Versión entregada:** v0.2.5
**Auditor independiente:** Cris (ChatGPT) | **Implementación:** Arena
**Fecha:** 2026-11-21
**Rama de trabajo:** `arena/441a4bf8-sdv-sdi-sgm` (rama de sesión autorizada
excepcionalmente por el responsable; idéntica en contenido a
`arena/audioinput-diag-etapa2` @ `50bae98` al inicio de la sesión)
**Condición:** entrega publicada; **no equivale a aprobación técnica**. Cris
realizará la auditoría independiente, limitada a C4, C5, trazabilidad y
preservación de los sectores congelados. La integración posterior hacia
`arena/audioinput-diag-etapa2` queda reservada a decisión del responsable.

---

## 1. Objetivo y principio de corrección

Corrección **estrictamente delimitada** a los dos ítems autorizados para v0.2.5:

- **C4:** registro, propiedad y cierre correcto de descriptores.
- **C5:** propagación de interrupciones y **prueba del flujo real de `main()`**.

No se reescribió el instrumento, no se amplió funcionalidad ni se introdujo
nueva arquitectura. **No se amplió el alcance y no se reconstruyó el instrumento.**

Nota de contexto: el texto íntegro de las instrucciones técnicas v0.2.5 de Cris
circuló en la sesión anterior de Arena, no disponible en esta sesión. Esta
implementación cubre el alcance tal como fue re-declarado expresamente en la
autorización del responsable (C4: registro/propiedad/cierre; C5: propagación de
interrupciones + prueba del flujo real de `main()`), a partir de una auditoría
dirigida del script v0.2.4 cuyos hallazgos se documentan en la sección 2. Si las
instrucciones originales de Cris contemplan algún punto adicional dentro de ese
alcance, queda pendiente de la auditoría de Cris.

**Restricciones respetadas:** no se ejecutó Android/Termux; no se usó root; no se
ejecutó audio real ni libsndfile real; no se usaron muestras reales del proyecto;
no se modificaron motores DSP ni archivos de la rama `main`; no se fusionaron
ramas; no se abrió ni integró PR; no se publicó en `main`; no se eliminó archivo
alguno ni se realizaron limpiezas automáticas; los sectores congelados (sección
6) no se modificaron.

---

## 2. Defectos residuales identificados (evidencia de origen)

Hallazgos de la auditoría dirigida sobre el script v0.2.4, dentro del alcance
autorizado. Cada corrección de este informe corresponde a uno de estos ítems.

### C4-R1 — Los cierres de T11–T16 no cierran nada (fuga silenciosa de descriptores)

**Evidencia de origen:** en v0.2.4, la clase `CloseErrorLogger` exige el modelo
de propiedad por apertura (`register_fd()` → token; `close_fd(..., token=...)`).
Las pruebas T11–T16 abren descriptores con `os.open()` **sin registrarlos** y
cierran con `closer.close_fd(fd, 'fd')` **sin token**. En ese estado,
`close_fd()` emite el aviso *"no hay apertura registrada como abierta para este
fd; no se cierra"* y **no cierra nada**. El aviso va a `closer.warnings`, que no
se reporta en el resultado de la prueba (solo se reporta `closer.errors`), por
lo que la fuga es invisible en el informe.

Verificación empírica (réplica del patrón exacto de T11–T16 v0.2.4):

```
resultado close_fd sin registro: None
warnings: [{'label': 'fd', 'errno': None, 'strerror': 'no hay apertura
registrada como abierta para este fd; no se cierra (doble cierre o numero
reutilizado)'}]
errors: []
fd sigue abierto tras close_fd (fuga): True
```

Consecuencia: cada ejecución de cada prueba T11–T16 filtraba su descriptor
(hasta 4 aperturas simultáneas por fixture × 6 pruebas). El defecto no fue
detectado en v0.2.4 porque T11–T16 nunca se ejecutaron en esa entrega
(numpy/soundfile ausentes; rutas ejercitadas solo por simulación con funciones
sustituidas). La **prueba del flujo real de `main()`** introducida en v0.2.5 es
la que expone el defecto.

### C4-R2 — `safe_create_file_exclusive_anchored()` cierra sin registro de propiedad

**Evidencia de origen:** la función (sin llamadores actuales, pero parte del
contrato documentado del instrumento: retorna `(ok, error, close_error)`) usaba
`try: os.close(fd) except OSError` directos: conservaba el error en el valor de
retorno, pero sin registro por token (`register_fd`), sin sink y sin el modelo
de propiedad adoptado en v0.2.4 para todos los demás puntos de cierre.

### C5-R1 — KI en la fase de resumen/construcción del informe pierde todos los resultados

**Evidencia de origen:** en v0.2.4, el `try/except KeyboardInterrupt` de
`main()` cubría solo las llamadas a `run_environment()`. Una KI que llegara
después del último entorno (durante el resumen, el detalle por entorno o la
construcción del dict del informe) no era capturada: propagaba al handler de
`__main__`, salía con rc 130 y **el informe JSON nunca se publicaba** — todos
los resultados ya obtenidos se perdían (solo quedaban los mensajes de stdout).
Contradice el criterio C5 de que la interrupción se refleje en el informe con
`interrupted=true` y de conservar los resultados obtenidos.

### C5-R2 — KI durante la creación del directorio de ejecución registra 0 entradas

**Evidencia de origen:** en `run_environment()`, la ruta `OSError` de
`safe_makedirs_exclusive_anchored()` registra las 18 pruebas del entorno como
`NOT_EXECUTED`; la KI (BaseException, no capturada entonces) propagaba a
`main()` sin registrar **ninguna** entrada del entorno — comportamiento
inconsistente con la filosofía C5 ("las pruebas no ejecutadas quedan como
NOT_EXECUTED") y con la ruta OSError del mismo bloque.

### C5-R3 — KI durante la publicación del informe salía sin mensaje dedicado

**Evidencia de origen:** una KI durante `write_report_json_robust()` se
propagaba (correctamente, sin publicar; el provisional queda en disco por el
diseño C1 de v0.2.4) hasta el handler genérico de `__main__`
(*"[Interrumpido por usuario fuera del flujo principal]"*), sin mensaje
específico de que la publicación fue interrumpida ni trazabilidad del
provisional.

---

## 3. Commits y enlaces

| Commit | Padre | Contenido |
|---|---|---|
| [`fb2a96c`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/fb2a96c7073d51dd6d16505e1616d3abc5fabe28) | [`50bae98`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/50bae98eddd1b2f2b65c255e94d517003234a8e1) (v0.2.4) | `.py` v0.2.5 + [diff v0.2.4→v0.2.5](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/DIFF_v0_2_4_A_v0_2_5.patch) + [pruebas unitarias v0.2.5](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/pruebas_unitarias_v0_2_5.py) |
| (este informe) | `fb2a96c` | `INFORME_CORRECCIONES_v0_2_5.md` |

- Instrumento v0.2.5: [blob](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py)
- Instrumento v0.2.4 (base): [blob en commit 50bae98](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/50bae98eddd1b2f2b65c255e94d517003234a8e1/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py)
- Rama de publicación: `arena/441a4bf8-sdv-sdi-sgm` (rama de sesión; sin PR,
  sin fusión, sin publicación en `main`)

---

## 4. Identificación del objeto y recovery point

Antes de modificar se confirmó la identidad del archivo:

- **SHA-256 de entrada (v0.2.4):** `8cf68c25f9e2da72c3e7c36a40386f742b1cd91254e8c40da1d5704cb6fe98d3`
- **Blob de entrada:** `72920aa077e3a660d6333c618e300f192b87bfd1` (idéntico al de
  `a3dcb88` y al documentado como referencia por el responsable)
- **Tamaño / líneas de entrada:** 111488 bytes / 2387 líneas
- **Recovery point verificable:** `/tmp/diag_v024_recovery.py` — SHA-256
  idéntico al de entrada. Además, el diff entregado es reversible: aplicar
  `DIFF_v0_2_4_A_v0_2_5.patch` en sentido inverso sobre v0.2.5 reconstruye
  v0.2.4 **byte a byte** (SHA-256 verificado idéntico al de entrada).

---

## 5. Funciones modificadas y justificación

### C4 — Registro, propiedad y cierre correcto de descriptores

| Función | Modificación | Justificación (defecto residual) |
|---|---|---|
| **`test_t11_soundfile_fd_closefd_false()`** | La apertura del fd se registra (`fd_token = closer.register_fd(fd, 'fd')`) y **todos** los cierres de la prueba (retornos anticipados, cierre del propietario y `finally`) se asocian al token; el token se invalida (`fd_token = None`) tras cada cierre. | C4-R1: cierre sin registro = no-op silencioso + fuga. |
| **`test_t12_pread_works()`** | Ídem (registro + cierres con token + `finally` con token). | C4-R1. |
| **`test_t13_pread_hash_matches_canonical()`** | Ídem. | C4-R1. |
| **`test_t14_pread_coexists_with_soundfile()`** | Ídem (la comprobación `11_fd_close` se asocia al token de la apertura registrada en el paso `01_open_fd`). | C4-R1. |
| **`test_t15_libsndfile_error_raised()`** | Ídem para `dir_fd` (todas las ramas: éxito inesperado, `LibsndfileError`, `OSError`, `Exception`, `finally`). | C4-R1. |
| **`test_t16_fd_survives_closefd_false_failure()`** | Ídem. | C4-R1. |
| **`safe_create_file_exclusive_anchored()`** | El fd del archivo se registra con token (`closer.register_fd(fd, 'create_file_fd')`) y se cierra asociado al token; el `parent_fd` se cierra con `_close_fd_tracked()` (conservado y reportado). **El contrato de retorno `(ok, error, close_error)` no cambia** y los mensajes de error de cierre conservan su formato. | C4-R2: propiedad por apertura uniforme en todo el instrumento. |
| **`SCRIPT_VERSION`** | `"0.2.4"` → `"0.2.5"`. Notas del informe JSON actualizadas (C4/C5 v0.2.5). | Identificación de versión. |

**Alcance de la modificación de T11–T16:** solo la **propiedad y cierre** de los
descriptores (C4). Los **criterios funcionales PASS/FAIL de T11–T16 no se
modifican**: ni las condiciones de verificación, ni los mensajes de estado, ni
los valores de retorno. Verificado por la regresión completa del harness v0.2.4
(16/16 PASS) y porque los criterios de PASS siguen siendo idénticos línea a
línea en el diff.

### C5 — Propagación de interrupciones y prueba del flujo real de `main()`

| Función | Modificación | Justificación (defecto residual) |
|---|---|---|
| **`run_environment()` — creación del directorio** | Nueva rama `except KeyboardInterrupt` alrededor de `safe_makedirs_exclusive_anchored()`: setea `interrupt_flag[0] = True`, registra **las 18 pruebas del entorno** como `NOT_EXECUTED` (coherente con la ruta `OSError`; nunca PASS), drena el sink de errores de cierre en la primera entrada y retorna `None`. | C5-R2: la KI en `makedirs` no registraba ninguna entrada. |
| **`main()` — nueva función local `_finalize_report()`** | La construcción del informe (drenaje del sink, `finished_at`, conteos, dict del informe) se aísla en una función local para poder **reconstruirlo de forma consistente** si una KI cae en la fase de resumen. El contenido del informe definido en v0.2.4 no se modifica (solo se añaden las notas C4/C5 v0.2.5). | C5-R1: sin esto, la reconstrucción tras KI duplicaría el dict o perdería el esquema. |
| **`main()` — fase de resumen e informe** | El bloque (llamada a `_finalize_report` + impresión de resumen + detalle por entorno) queda dentro de `try/except KeyboardInterrupt`: ante una KI se setea `interrupt_flag[0] = True`, se reconcilia con `_reconcile_interrupted()`, se añade el mensaje *"…resultados conservados"* y se reconstruye el informe con `interrupted=true`; la ejecución continúa hacia la publicación con rc no nulo. | C5-R1: la KI en esta ventana no pierde los resultados obtenidos ni deja el estado global incoherente. |
| **`main()` — publicación del informe** | La llamada a `write_report_json_robust()` queda dentro de `try/except KeyboardInterrupt`: ante una KI durante la publicación se imprime mensaje explícito ("no se publica; el provisional queda en disco") y se sale con rc 130. **El mecanismo de publicación C1 de v0.2.4 (link anclado atómico, provisional conservado, sin sobrescritura) no se altera.** | C5-R3: mensaje dedicado + trazabilidad, sin tocar el sector congelado C1. |
| **`pruebas_unitarias_v0_2_5.py` (nuevo)** | Harness que ejecuta el **flujo real de `main()`** (argparse, validación de entornos, directorios anclados, metadatos, `run_environment` completo con fixtures, T11–T16, informe y códigos de salida) con numpy/soundfile **simulados** inyectados en `sys.modules`, e inyección de KI en puntos controlados. | C5: la v0.2.4 solo simuló fragmentos (fixtures vacíos y funciones sustituidas); el flujo real nunca fue ejercitado — y al ejercitarlo se descubrió C4-R1. |

---

## 6. Sectores congelados — preservación verificada

- **C1 y publicación segura del JSON:** `write_report_json_robust()`,
  `safe_open_dir_anchored()`, `_ensure_parents_anchored()`,
  `safe_makedirs_exclusive_anchored()`, `check_no_symlink_in_path()`,
  `check_dir_is_safe()`, `validate_environments_distinct()` — **sin cambios de
  lógica** (el diff no toca sus cuerpos, salvo ninguna línea). El único cambio
  relacionado es **externo** a la publicación: el llamador en `main()` captura
  KI alrededor de la llamada (mismo resultado: no se publica, provisional
  conservado).
- **`sha256_pread_v2()`** — sin cambios.
- **Clasificación SHA-256 y `sha256_canonical()`** — sin cambios.
- **Contrato SoundFile con `closefd=False`** — sin cambios (todas las llamadas
  conservan `closefd=False`; el contrato se verifica en el harness).
- **Lectura mediante `pread()`** — sin cambios.
- **Generación de señales sintéticas** (`generate_audio_array`, constantes) —
  sin cambios.
- **Formatos WAV y subtipos** (`FIXTURE_SPECS`, `SAMPLE_RATE`, etc.) — sin
  cambios.
- **Criterios funcionales PASS/FAIL de T11–T16** — sin cambios (solo
  propiedad/cierre de descriptores, C4).
- **Motores DSP y archivos de `main` (branch)** — sin cambios; ningún archivo
  fuera de `herramientas/diagnostico_audio/etapa2/` fue tocado.
- **Nota cosmética (preexistente):** la línea de título del docstring dice
  "v0.2.1"; quedó intacta, como en v0.2.3/v0.2.4. La versión autoritativa es
  `SCRIPT_VERSION = "0.2.5"` (línea 86) y `metadata.script_version` del informe.

---

## 7. Verificaciones exigidas (resultados reales)

Entorno de verificación: contenedor Linux (no Android), Python 3.11.2, sin
numpy/soundfile/libsndfile instalados, sin ejecución de audio.

| # | Verificación | Resultado |
|---|---|---|
| 1 | `py_compile` del script v0.2.5 | **PASS** — OK |
| 2 | `--help` (interfaz del instrumento) | **PASS** — interfaz correcta |
| 3 | Prueba de humo de `main()` sin dependencias (entorno no Android) | **PASS** — banner v0.2.5, rc=2 (dependencias ausentes, no 0) |
| 4 | Harness v0.2.5 completo (11 pruebas) | **PASS** — `TOTAL 11 \| PASS 11 \| FAIL 0 \| ERROR 0 \| NOT_EXECUTED 0` |
| 5 | Regresión: harness v0.2.4 completo (16 pruebas) sobre el script v0.2.5 | **PASS** — `TOTAL 16 \| PASS 16 \| FAIL 0 \| ERROR 0 \| NOT_EXECUTED 0` |
| 6 | T11–T14 sobre fixture real: PASS, `close_errors == []` y **sin fuga de descriptores** (conteo `/proc/self/fd` antes/después) | **PASS** — `C4_v05_T11_T14_sin_fuga_descriptores` |
| 7 | T15–T16 con fd de directorio: PASS y sin fuga | **PASS** — `C4_v05_T15_T16_sin_fuga_descriptores` |
| 8 | Flujo real de `main()` completo (2 entornos): rc=0, 36 PASS, informe publicado, `interrupted=false`, `close_errors` vacíos | **PASS** — `C5_v05_flujo_real_main_completo` |
| 9 | KI durante T11 (flujo real): ERROR + cascada NOT_EXECUTED + segundo entorno no iniciado + rc=130 + informe con `interrupted=true` | **PASS** — `C5_v05_flujo_real_main_ki_prueba` |
| 10 | KI durante `create_fixture()` (flujo real): ERROR + cascada NOT_EXECUTED + rc=130 | **PASS** — `C5_v05_flujo_real_main_ki_create_fixture` |
| 11 | KI durante `makedirs` (flujo real): 18 entradas NOT_EXECUTED del entorno (corrección C5-R2) + rc=130 | **PASS** — `C5_v05_flujo_real_main_ki_makedirs` |
| 12 | KI en la fase de resumen/informe (flujo real): resultados conservados (36 PASS), informe publicado con `interrupted=true`, rc=130 (corrección C5-R1) | **PASS** — `C5_v05_flujo_real_main_ki_preparacion_informe` |
| 13 | KI durante la publicación (flujo real): sin publicación, provisional conservado en disco, mensaje explícito, rc=130 (corrección C5-R3) | **PASS** — `C5_v05_flujo_real_main_ki_publicacion` |
| 14 | Token de apertura: registrar → cerrar con token cierra; token obsoleto no cierra nada | **PASS** — `C4_v05_patron_token_cierre_y_obsoleto` |
| 15 | `safe_create_file_exclusive_anchored`: token interno, contrato `(ok, err, close_error)` intacto, EEXIST sin sobrescritura, sin fuga | **PASS** — `C4_v05_safe_create_file_token_contrato` |
| 16 | Estático: sin patrón de cierre sin registro en el script; `register_fd` presente en todas las aperturas (≥ 8 sitios) | **PASS** — `C4_v05_sin_patron_cierre_sin_token` |
| 17 | Diff verificable: patch inverso reconstruye v0.2.4 byte a byte | **PASS** — SHA-256 reconstruido = `8cf68c25…98d3` |

**Nota de honestidad sobre la verificación 6:** las T11–T14 del flujo real se
ejecutan con la **capa soundfile simulada** (escritura/lectura de bytes
deterministas sobre descriptores reales, `LibsndfileError` simulada para fd de
directorio, `close()` que respeta `closefd=False`). Verifican la lógica de
flujo, registro, cierre y propagación — **no** la compatibilidad con libsndfile
real (NOT_EXECUTED, sección 8).

---

## 8. Pruebas no ejecutadas (NOT_EXECUTED, con explicación, nunca PASS inventado)

- **T11–T16 con numpy/soundfile/libsndfile reales y fixtures WAV decodificados
  por libsndfile:** **NOT_EXECUTED**. Explicación: el entorno de trabajo no
  tiene `numpy` ni `soundfile` instalados y el alcance prohíbe instalar
  dependencias y ejecutar audio. Se ejercen los mismos caminos con la capa
  simulada documentada (sección 7, nota de la verificación 6).
- **Android/Termux:** **no ejecutado** (prohibido por el alcance). No se declara
  compatibilidad Android/Termux.
- **Audio real, motores DSP, muestras reales del proyecto:** no ejecutados
  (prohibidos por el alcance).

---

## 9. Resultados individuales de las pruebas unitarias

**Harness:** `herramientas/diagnostico_audio/etapa2/pruebas_unitarias_v0_2_5.py`
(artefacto de entrega, commit `fb2a96c`).

**Método:** importar el módulo por ruta; para el flujo real, ejecutar
`mod.main()` con numpy/soundfile simulados en `sys.modules`, `--private-dir` y
`--shared` en directorios temporales, captura de stdout y `SystemExit`; KI
inyectada en puntos controlados (constructor simulado nº N, `makedirs`,
`time.strftime` de `finished_at`, `os.write` del contenido JSON). **No**
Android/Termux, **no** audio, **no** libsndfile, **no** muestras reales.

**Resultado:** `TOTAL 11 | PASS 11 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0`

```
PASS C4_v05_patron_token_cierre_y_obsoleto
PASS C4_v05_T11_T14_sin_fuga_descriptores
PASS C4_v05_T15_T16_sin_fuga_descriptores
PASS C4_v05_safe_create_file_token_contrato
PASS C4_v05_sin_patron_cierre_sin_token
PASS C5_v05_flujo_real_main_completo
PASS C5_v05_flujo_real_main_ki_prueba
PASS C5_v05_flujo_real_main_ki_create_fixture
PASS C5_v05_flujo_real_main_ki_makedirs
PASS C5_v05_flujo_real_main_ki_preparacion_informe
PASS C5_v05_flujo_real_main_ki_publicacion
```

**Regresión (harness v0.2.4 sobre el script v0.2.5):**
`TOTAL 16 | PASS 16 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0`

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

## 10. Datos de la entrega

| Artefacto | Valor |
|---|---|
| Archivo corregido | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **SHA-256 final (v0.2.5)** | `8a2ad0e4c191ea945a6918dd7b50fbc6bffbf3bc8b8e68ccd3438a36aa98b902` |
| **Blob final (v0.2.5)** | `a41d7b954e6182e75c59706b329317f386edd69d` |
| Tamaño final | 119728 bytes |
| Líneas finales | 2512 |
| **Diff** | `DIFF_v0_2_4_A_v0_2_5.patch` — SHA-256 `4b090a2aaad33bb35abdfd2d21451732adb0487b32454f569def0bfea6663a69`, blob `cde8e03b8709f7b747adc3f842ebd201c58072dc`, 646 líneas de patch (32364 bytes); reversible (reconstruye v0.2.4 byte a byte) |
| **Harness v0.2.5** | `pruebas_unitarias_v0_2_5.py` — SHA-256 `340b10d46fdceb9ca2cb267fc0b1a9154fda4064c2aec659f6a4bb11f884a44a`, blob `5abbd509510ca08846a29243a00bcca9514f266f`, 705 líneas (29897 bytes) |
| Harness v0.2.4 (regresión, sin cambios) | blob `2646deae04001976e5ef6b67bf8a29b8b6f3137c` |
| Commit de partida | [`50bae98`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/50bae98eddd1b2f2b65c255e94d517003234a8e1) (v0.2.4) |
| Commit de entrega (código) | [`fb2a96c`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/fb2a96c7073d51dd6d16505e1616d3abc5fabe28) (padre `50bae98`) |
| Commit del informe | (este commit, hijo de `fb2a96c`) |
| Rama de publicación | `arena/441a4bf8-sdv-sdi-sgm` (rama de sesión autorizada) |
| `py_compile` | OK |
| `--help` | OK |
| Prueba de humo `main()` sin dependencias | OK (rc=2) |

---

## 11. Riesgos residuales

1. **Aprobación pendiente:** la entrega no equivale a aprobación técnica. Cris
   debe auditar C4, C5, trazabilidad y preservación de sectores congelados.
2. **Capa simulada:** los PASS de T11–T16 en el flujo real provienen de la capa
   numpy/soundfile simulada. La compatibilidad con libsndfile real, con
   Android/Termux y con almacenamiento compartido real queda **NOT_EXECUTED**
   y no se declara.
3. **Instrucciones originales de Cris no disponibles en esta sesión:** la
   implementación cubre el alcance re-declarado en la autorización (C4 y C5).
   Si las instrucciones originales v0.2.5 incluyen puntos adicionales dentro de
   ese alcance, quedarán para la auditoría/iteración siguiente.
4. **`register_fd` con descriptor inválido:** si `register_fd()` no puede
   registrar (fd ya inválido), `close_fd(..., token=None)` emite aviso y no
   cierra — el descriptor ya era inoperante; sin fuga operativa. Los puntos de
   uso internos registran la apertura inmediatamente después de `os.open()`.
5. **KI residual residual:** una KI que caiga exactamente dentro del segundo
   `_finalize_report()` del handler de excepción o dentro de `sys.exit()` es
   teóricamente posible (ventana de pocas instrucciones, sin syscalls
   relevantes); el comportamiento resultante sería el handler de `__main__`
   (rc 130) — mismo que v0.2.4 en ese microscópico intervalo.
6. **Publicación por enlace duro anclado:** sin cambios respecto a v0.2.4
   (mecanismo C1 congelado): si el sistema no admite `os.link` con `dir_fd`, el
   provisional se conserva y se reporta explícitamente.
7. **Residuo de provisional:** tras una publicación fallida o interrumpida, el
   provisional `report-*.json.tmp` queda en disco **sin limpieza automática**
   (por diseño; no se eliminan archivos cuyo origen no esté acreditado).
8. **No se declara compatibilidad Android/Termux** basada en esta entrega.

---

## 12. Confirmaciones explícitas

- **No hubo ejecución Android/Termux**, ni audio real, ni libsndfile real, ni
  acceso a muestras reales del proyecto, ni uso de root.
- **No se modificó la rama `main` ni los motores DSP**, no se fusionaron ramas,
  no se abrió ni integró PR, no se eliminó archivo alguno, no se realizaron
  limpiezas automáticas.
- **No se reconstruyó el instrumento:** corrección delimitada sobre v0.2.4.
- **Solo se modificó el archivo autorizado** `audioinput_diag_termux.py`,
  además de los **artefactos de entrega**: `INFORME_CORRECCIONES_v0_2_5.md`,
  `DIFF_v0_2_4_A_v0_2_5.patch` y `pruebas_unitarias_v0_2_5.py` (nuevo).
  `pruebas_unitarias_v0_2_4.py` y `DIFF_v0_2_3_A_v0_2_4.patch` quedaron
  intactos (blobs idénticos a v0.2.4).
- **Los sectores congelados no se modificaron** (sección 6).
- **No se declaró ninguna prueba como ejecutada que no se haya realizado**; las
  ejecuciones reales están listadas en las secciones 7 y 9 con su entorno.
