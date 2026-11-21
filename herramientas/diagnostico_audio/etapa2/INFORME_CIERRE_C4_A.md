# INFORME DE CIERRE C4-A — AudioInput ETAPA 2 **v0.2.7 (provisional)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Base obligatoria:** commit [`b91622bee7a81f7850e9612a53d5ffb04a24e975`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b91622bee7a81f7850e9612a53d5ffb04a24e975) (v0.2.6)
**Versión entregada:** v0.2.7 (provisional)
**Etapa:** CIERRE CONTROLADO C4-A — contrato estricto de propiedad de descriptores
**Auditor independiente:** Cris (ChatGPT) | **Implementación:** Arena | **Decisor:** Will
**Fecha:** 2026-11-21
**Rama de trabajo:** `arena/441a4bf8-sdv-sdi-sgm`
**Condición:** entrega publicada; **C4-A NO queda aprobado**. La aprobación
corresponde exclusivamente a Cris tras revisión independiente. **No se inicia
C4-B ni C5.**

---

## 1. Punto de partida y estado del entorno

| Verificación | Resultado |
|---|---|
| Rama de sesión en la base obligatoria | **OK** — tras resincronización (ver incidente abajo): HEAD local = HEAD remoto = `b91622b…` |
| Blob del instrumento en la base | `1a9854471fedd79e2b687df05e7749162f850c9b` (SHA-256 `a0d2ad29…63a2`, v0.2.6) |
| SHA del diff v0.2.5→v0.2.6 publicado | `1d8ace3466ff8811df813c65a3f6388658a01e0e302f0d66d6fb247b4bd26c49` |
| Árbol de trabajo limpio | **OK** (solo `__pycache__/` sin seguimiento, residuo de pruebas, no commiteado, no eliminado por restricción) |
| Referencia inmutable conservada | **OK** — commits `5e38e0f`/`b91622b` en el historial; recovery point `/tmp/diag_v026_recovery.py` (SHA-256 idéntico); el diff v0.2.6→v0.2.7 es reversible y reconstruye v0.2.6 byte a byte |

**Incidente de entorno documentado (resuelto sin pérdida):** al iniciar esta
etapa, el clon local había perdido los commits locales (HEAD local quedó en el
commit base `50bae98` de la sesión y los artefactos aparecían como
modificados/sin seguimiento) — restauración del sandbox. Se verificó, **archivo
por archivo contra los blobs del remoto**, que los 15 archivos de
`herramientas/diagnostico_audio/etapa2` en disco eran byte a byte idénticos a
lo publicado en `b91622b`, y que el historial remoto estaba íntegro
(`50bae98 → fb2a96c → b947c05 → 5e38e0f → b91622b`). Se resincronizó el clon
local con `git reset --hard` hacia el estado publicado exacto: **cero pérdida
de datos**, verificado por hashes. El trabajo ya publicado en GitHub nunca
estuvo en riesgo.

---

## 2. HECHOS COMPROBADOS — implementación de la decisión técnica vinculante

**Decisión adoptada:** contrato estricto de propiedad de descriptores dentro
del instrumento. Cada descriptor registrado tiene un único propietario
(`OwnedFdResource`); solo ese propietario puede iniciar su cierre, una única
vez. **No se exige ni se declara** la detección portable de un cierre externo
arbitrario seguido de reutilización del mismo número para abrir el mismo
archivo (Python y `fstat()` no ofrecen identidad portable del
open-file-description). Esa limitación queda documentada expresamente (sección
9) y **no se presenta como una protección conseguida**.

Cambios implementados sobre v0.2.6:

| # | Cambio | Detalle |
|---|---|---|
| 1 | **`close_fd()` sin token ya no cierra nada** | Eliminada la rama de resolución automática por número de fd (`open_tokens`). Con `token=None` (o sin token): aviso *"cierre sin token rechazado por el contrato de propiedad…"* y retorno inmediato — **ni siquiera cierra un descriptor registrado como OPEN**. El cierre solo puede iniciarlo el propietario con el token de su apertura concreta. |
| 2 | **`get_resource(token)` retorna vista de solo lectura** | Nueva clase `_ReadOnlyResourceView`: permite consultar estado (`state`, `close_result`, `fd`, `dev`, `ino`, `label`, `token`; acceso tipo dict de compatibilidad) pero **cualquier intento de asignación lanza `AttributeError`**. El estado y la propiedad solo se modifican dentro del logger propietario (transiciones de la máquina de estados). |
| 3 | **Estados conservados** | `OPEN` / `CLOSING` / `CLOSED` / `CLOSE_FAILED_UNCERTAIN` (terminal), mismas transiciones que v0.2.6. Un token cerrado, desconocido o incierto nunca inicia otro cierre. |
| 4 | **Escenario 09c reclasificado** | El escenario (cierre externo + reutilización del mismo número para el mismo archivo) viola el contrato y **no es detectable de forma portable**: en el nuevo harness se registra como **`EXPECTED_LIMITATION`** (categoría separada de PASS; NO es una aprobación de seguridad). Se conserva/añade la prueba **exigible** del caso inverso (sección 4, prueba `C4AC_04`). |
| 5 | **`SoundFile(fd, closefd=False)` sin cambios** | SoundFile no asume propiedad del descriptor; el propietario conserva la responsabilidad del cierre (verificado en `C4AC_10`). |
| 6 | **Auditoría de llamadas directas a `os.close()`** | Estática (AST): `os.close` solo existe dentro de `close_fd` (propietario) y `_close_fd_tracked` (descriptores internos **no registrados**). Runtime: durante un flujo completo, **0 cierres de números de recursos registrados aún abiertos fuera del propietario** (`C4AC_13`). |
| 7 | `SCRIPT_VERSION` | `"0.2.6"` → `"0.2.7"`. Nota de documentación del informe JSON actualizada (única línea en zona C5, documentación, sin sentencias — declarado para auditoría). |

Tabla de semántica (v0.2.6 → v0.2.7):

| Situación | v0.2.6 | v0.2.7 |
|---|---|---|
| `close_fd(fd, label)` sin token, fd registrado OPEN | Buscaba un recurso OPEN por número y lo cerraba | **No cierra nada** (aviso; estado permanece OPEN; el propietario aún puede cerrar con su token) |
| `close_fd(fd, label)` sin token, fd no registrado | Aviso "no hay apertura registrada…" | Aviso "cierre sin token rechazado…" (mismo resultado: no cierra) |
| `get_resource(token)` | Retornaba el recurso mutable | Retorna **vista de solo lectura** (mutación → `AttributeError`) |
| Reutilización tras cierre **correcto** del propietario | Token obsoleto → aviso, no cierra | Igual, **verificada expresamente** con reutilización del mismo número y mismo archivo (`C4AC_04`: la nueva apertura permanece utilizable) |
| Reutilización tras **cierre externo** (contrato violado), mismo archivo | El cierre procedía (comparación como identidad) | **`EXPECTED_LIMITATION`**: comportamiento documentado, no detección; categoría separada de PASS |

---

## 3. RESULTADOS DE PRUEBAS

Entorno: contenedor Linux (no Android), Python 3.11.2, sin numpy/soundfile/libsndfile.

### 3.1 Harness de cierre — `pruebas_unitarias_C4_A_CIERRE.py`

`TOTAL 15 | PASS 14 | EXPECTED_LIMITATION 1 | NOT_EXECUTED 0 | FAIL 0 | ERROR 0` — exit 0

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
| 1 | `C4AC_01_cierre_normal_propietario` | **PASS** | `OPEN → CLOSED`; 1 `os.close` (contador); sin errores |
| 2 | `C4AC_02_dos_aperturas_cada_token` | **PASS** | Tokens distintos; cada cierre con su propio token; sin efectos cruzados |
| 3 | `C4AC_03_doble_cierre` | **PASS** | Aviso; contador `os.close` = 0 en el reintento |
| 4 | `C4AC_04_token_antiguo_reutilizacion` | **PASS** | Caso exigible (instrucción §3): propietario cierra correctamente → el sistema reutiliza el mismo número para el MISMO archivo → token antiguo invocado → **no cierra la nueva apertura** (recurso `CLOSED`), la nueva apertura permanece utilizable y es cerrable con token propio |
| 5 | `C4AC_05_token_desconocido` | **PASS** | Aviso; sin `os.close`; fd vivo |
| 6 | `C4AC_06_descriptor_no_registrado` | **PASS** | Sin token → no cierra; token desconocido → no cierra |
| 7 | `C4AC_07_cierre_sin_token_nunca_cierra` | **PASS** | **Decisión vinculante**: descriptor registrado OPEN + `close_fd` sin token (2 formas) → no se cierra, estado intacto, aviso explícito; el propietario luego cierra con su token |
| 8 | `C4AC_08_error_simulado_os_close` | **PASS** | `OSError(EIO)` devuelta; conservada en `errors` y sink; estado `CLOSE_FAILED_UNCERTAIN` |
| 9 | `C4AC_09_incierto_sin_segundo_intento` | **PASS** | Tras estado incierto, reintento → aviso; contador `os.close` = 0 |
| 10 | `C4AC_10_soundfile_closefd_false` | **PASS** | SoundFile simulado con `closefd=False` no cierra el fd; el propietario cierra después por token |
| 11 | `C4AC_11_vista_solo_lectura` | **PASS** | Consulta OK (atributos y clave); mutación por atributo → `AttributeError`; por clave → `TypeError`; estado real intacto; el cierre por token se refleja en la vista |
| 12 | `C4AC_12_auditoria_estatica_rutas_cierre` | **PASS** | AST: `os.close` solo en `{_close_fd_tracked, close_fd}`; resolución automática por fd eliminada (`open_tokens` ausente); rechazo sin token presente y precede al camino de cierre; 25 llamadores internos del logger, **todos con token** |
| 13 | `C4AC_13_auditoria_runtime_rutas_cierre` | **PASS** | Flujo completo (fixture + T11–T14 + T15/T16 + `safe_create_file` + publicación de informe): 0 cierres de números de recursos registrados aún abiertos fuera del propietario; los números liberados por cierre confirmado pueden reasignarse (modelado en la auditoría) |
| 14 | `C4AC_14_violacion_mismo_archivo_limite` | **EXPECTED_LIMITATION** | Escenario de violación del contrato (cierre externo + mismo número + mismo archivo): no detectable portable; comportamiento documentado verificado (el cierre procede y afecta a la apertura ajena — consecuencia declarada, no oculta). **NO es una aprobación de seguridad** |
| 15 | `C4AC_15_estado_closing_guardia_reentrada` | **PASS** | Reentrada real durante el cierre (sin mutar estado desde fuera): aviso "ya iniciado"; 1 `os.close`; `CLOSED` final |

### 3.2 Regresiones (harness congelados sobre el script v0.2.7)

| Harness | Resultado | Divergencias |
|---|---|---|
| v0.2.4 (16 pruebas) | **16/16 PASS** (exit 0) | Ninguna |
| v0.2.5 (11 pruebas) | 10/11 PASS; 1 FAIL | `C5_v05_flujo_real_main_completo`: aserción de pin de versión (`'v0.2.5'` en banner) — esperado desde v0.2.6, no es regresión de lógica |
| C4-A v0.2.6 (13 pruebas) | 11 PASS; 1 FAIL; 1 ERROR | **Ambas derivadas de las decisiones vinculantes de este cierre, sin pérdida de comportamiento exigible:** (a) `C4A_06_cierre_no_registrado` falla su aserción de **texto de aviso** (esperaba el texto antiguo "no hay apertura registrada…"; ahora el aviso es "cierre sin token rechazado…"); el comportamiento exigible (no cerrar, fd vivo, sin errores) está re-verificado en `C4AC_06` y `C4AC_07`. (b) `C4A_10_estado_closing_no_duplica` lanza `AttributeError` porque **mutaba el estado desde fuera** (`res.state = …`), exactamente lo que la vista de solo lectura ahora impide por decisión vinculante; la misma guardia de reentrada está re-verificada sin mutación externa en `C4AC_15`. Ambos harness son artefactos congelados y no se modificaron |

### 3.3 Suplementos y controles

| Verificación | Resultado |
|---|---|
| Flujo real de `main()` (utilidades del harness v0.2.5, sin modificarlo) | **OK** — rc=0, banner v0.2.7, `script_version=0.2.7`, 36 resultados, 36 PASS, `interrupted=false`, `close_errors` vacíos, informe publicado, run_dir privado y compartido creados |
| `py_compile` v0.2.7 | **PASS** |
| `--help` | **PASS** (rc 0) |

---

## 4. Escenarios EXPECTED_LIMITATION y NOT_EXECUTED (separados de PASS)

**EXPECTED_LIMITATION (1):**
- `C4AC_14_violacion_mismo_archivo_limite`: cierre externo + reutilización del
  MISMO número para el MISMO archivo. **Por qué no es detectable de forma
  portable:** la identidad de la apertura no es observable — `fstat()` retorna
  `(st_dev, st_ino)` del archivo, que coincide para ambas aperturas; ni Python
  ni Linux exponen portátilmente el open-file-description; alternativas
  evaluadas y rechazadas: `kcmp(KCMP_FILE)` (no portable, requiere
  `CONFIG_CHECKPOINT_RESTORE` y syscalls crudas; la instrucción además lo
  excluye expresamente) y posición del OFD (no fiable). El escenario **no se
  contabiliza como PASS de seguridad**: se verifica y documenta el
  comportamiento del límite, incluida su consecuencia (el cierre del
  propietario afecta a la apertura ajena).

**NOT_EXECUTED (0 en esta ejecución):**
- La vía `NOT_EXECUTED` está implementada para `C4AC_04` y `C4AC_14` cuando el
  entorno no reutilice el número de fd (clase `NotReproducible` →
  `NOT_EXECUTED`, nunca PASS inventado). En esta ejecución la reutilización sí
  fue reproducible.
- Android/Termux, audio real, libsndfile real, muestras del proyecto: **no
  ejecutados** (prohibidos por el alcance).

---

## 5. Auditoría de todas las rutas de cierre de descriptores

| Ruta | Mecanismo | Descriptor registrado | Verificación |
|---|---|---|---|
| T11–T14 (`test_t11…` a `test_t14…`) | `closer.close_fd(fd, …, token=fd_token)` (todos los cierres, incluido `finally`) | Sí, registrado en la apertura | `C4AC_12` (25 llamadores, todos con token) + `C4AC_13` (runtime) |
| T15–T16 | `closer.close_fd(dir_fd, …, token=dir_fd_token)` | Sí | Ídem |
| `create_fixture()` | fixture fd: token; `parent_fd`: `_close_fd_tracked` | fd sí; parent **no registrado** | Ídem |
| `safe_create_file_exclusive_anchored()` | fd: token; `parent_fd`: `_close_fd_tracked` | fd sí; parent no registrado | `C4AC_13` |
| `write_report_json_robust()` | `tmp_fd`: token; `parent_fd`: `_close_fd_tracked` | tmp sí; parent no registrado | `C4AC_13` |
| `safe_open_dir_anchored()`, `_ensure_parents_anchored()`, `safe_makedirs_exclusive_anchored()` | `_close_fd_tracked` (cadena anclada, verify_fd, parent_fd) | **No registrados** (descriptores internos de vida mínima) | `C4AC_12` (os.close solo en esas 2 funciones) + `C4AC_13` |
| `close_fd()` sin token | **Rechazado** (no cierra nada) | — | `C4AC_07` |
| `CloseErrorLogger.close_soundfile()` | `sfile.close()`; SoundFile opera con `closefd=False` y no cierra el fd | No aplica | `C4AC_10` |
| `sha256_canonical()` | `with open(...)` (cierre por contexto, no `os.close`) | No registrado | Estático (`C4AC_12`: os.close solo en 2 funciones) |

**Conclusión de la auditoría:** todo descriptor registrado se cierra
exclusivamente mediante su recurso propietario (token, una única vez); las
demás rutas de cierre (`_close_fd_tracked`) atienden únicamente descriptores
internos que nunca se registran; ninguna ruta interna cierra directamente un
descriptor registrado.

---

## 6. Funciones modificadas (lista exacta)

| Función / clase | Naturaleza | Contenido |
|---|---|---|
| `_ReadOnlyResourceView` | **NUEVA clase** | Vista de solo lectura de un recurso; mutación → `AttributeError` |
| `CloseErrorLogger.get_resource()` | **Modificada** | Retorna la vista de solo lectura (o None) |
| `CloseErrorLogger.close_fd()` | **Modificada** | Contrato estricto: sin token → aviso y sin cierre (eliminada la rama `open_tokens`); token → guardias de estado (`OPEN`/`CLOSING`/`CLOSED`/`CLOSE_FAILED_UNCERTAIN`) y cierre único sobre `resource.fd`; docstring actualizado |
| `CloseErrorLogger` (docstring de clase) | **Documentación** | Reglas v0.2.7 (contrato estricto, vista, límite `EXPECTED_LIMITATION`) |
| `SCRIPT_VERSION` | Constante | `"0.2.6"` → `"0.2.7"` |
| Notas del informe JSON (dentro de `_finalize_report`, `main()`) | **Documentación** (1 entrada, sin sentencias modificadas — declarado para auditoría) | Declara el contrato estricto y el límite |
| `OwnedFdResource`, `register_fd`, `_identity`, `_append_error`, `close_soundfile`, `summary`, T11–T16, `create_fixture`, `safe_create_file_exclusive_anchored`, `write_report_json_robust`, C1, C5, `sha256_pread_v2`, señales sintéticas, WAV/subtipos, criterios PASS/FAIL | **SIN cambios** | Sectores congelados y funciones no alcanzadas por el alcance |

---

## 7. Entregables e identificación

| Artefacto | Valor |
|---|---|
| Instrumento v0.2.7 | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **Commit de partida** | `b91622bee7a81f7850e9612a53d5ffb04a24e975` (v0.2.6) |
| **Commit de código final** | `3f850b6c27383638ea68fea73ce8b815cdf6c3f6` (padre `b91622b…`) |
| **Blob del instrumento** | `f1c0e6f79b8f73af885dfe9eb8c80e5e0f8ce6c2` |
| **SHA-256 del instrumento** | `b5be0b8b8b75d53ddd8f9f6d09ad71a80407a07924562128c32261442920c944` |
| Tamaño / líneas | 130529 bytes / 2726 líneas |
| **Diff v0.2.6→v0.2.7** | `DIFF_v0_2_6_A_v0_2_7.patch` — SHA-256 `5d948057da66eb2840d2dfc0192a009a01c9446b7792478ff1c8029a3a3fb216`, blob `65ddadd05cfeb0ff450296d5758ae76c8d70b79c`, 253 líneas (12540 bytes); **reversible** (patch inverso reconstruye v0.2.6 byte a byte, verificado) |
| **Harness de cierre** | `pruebas_unitarias_C4_A_CIERRE.py` — SHA-256 `21987eeec268220c13526775d6ac32d014faeae44c1447015391a30aa4ef1955`, blob `907af5e96952e343c33b39cf622f07d345e4bd3d`, 799 líneas (32455 bytes) |
| Commit del informe | (este commit, hijo de `3f850b6`) |
| Rama | `arena/441a4bf8-sdv-sdi-sgm` (sin PR, sin fusión, sin `main`) |

**Alcance del diff (hunks):** línea 83 (`SCRIPT_VERSION`), bloque
`OwnedFdResource`/`CloseErrorLogger` (vista + `get_resource` + reglas +
`close_fd`), y la nota de documentación en `_finalize_report`. **Sin cambios de
lógica en C1 ni C5.**

---

## 8. Limitaciones que permanecen

1. **Identidad del open-file-description:** no existe mecanismo portable para
   reconocer un cierre externo seguido de reutilización del mismo número para
   el mismo archivo. El diseño depende del **contrato de propiedad**, no de
   detección. Documentado y clasificado `EXPECTED_LIMITATION`.
2. **Detección pasiva de cierres externos:** no existe; la violación solo se
   observa en la guardia previa del cierre del propietario (EBADF) o por
   identidad distinta (reutilización por otro archivo).
3. **Compatibilidad de harness congelado:** dos divergencias documentadas
   (sección 3.2) derivadas de las decisiones vinculantes; los comportamientos
   exigibles están re-verificados en el harness de cierre.
4. **La propagación completa de errores de cierre ante interrupciones
   corresponde a C4-B** (fuera de esta etapa); los errores se conservan en
   `errors` y en el sink.
5. **No se declara compatibilidad Android/Termux** basada en esta entrega.

---

## 9. Riesgos residuales

1. **Aprobación pendiente:** C4-A no está aprobado; corresponde a Cris.
2. **Llamadas externas al logger:** si un componente ajeno al instrumento
   invocara `close_fd` sin token esperando el comportamiento antiguo
   (cierre por número), ahora obtiene un no-op con aviso — cambio de contrato
   deliberado y documentado.
3. **`_by_fd` conservado con fines de registro** (ya no se usa para resolver
   cierres); su presencia es inofensiva y verificada estáticamente.

---

## 10. Confirmaciones explícitas

- **Android/Termux NO fue ejecutado.** Tampoco se usó root, ni se ejecutó
  audio real, ni libsndfile real, ni se usaron muestras del proyecto, ni se
  modificaron motores DSP ni archivos de `main` (branch).
- No se fusionaron ramas; no se abrió ni integró PR; no se publicó en `main`;
  no se eliminó archivo alguno; no se realizó limpieza automática; no se
  reescribió el instrumento (diff de 253 líneas sobre la base obligatoria).
- Solo se modificó el archivo autorizado `audioinput_diag_termux.py`, además
  de los artefactos de entrega: `INFORME_CIERRE_C4_A.md`,
  `DIFF_v0_2_6_A_v0_2_7.patch` y `pruebas_unitarias_C4_A_CIERRE.py` (nuevo).
  Los artefactos anteriores (v0.2.4, v0.2.5, v0.2.6) quedaron intactos.
- Sectores congelados sin cambios: C1, C4-B (no iniciado), C5,
  `sha256_pread_v2()`, clasificación SHA, SoundFile `closefd=False`, `pread`,
  subtipos WAV, señales sintéticas, criterios funcionales PASS/FAIL de
  T11–T16, metadatos y alcance general.
- **C4-A NO se declara aprobado.** **No se inicia C4-B ni C5**; se espera la
  evaluación de Cris.
