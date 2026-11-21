# INFORME DE CORRECCIÓN ENCAPSULACIÓN C4-A — AudioInput ETAPA 2 **v0.2.8 (provisional)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Commit base:** [`edc10b0e28033194247583c4c4789346e59df48f`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/edc10b0e28033194247583c4c4789346e59df48f) (entrega v0.2.7 y su informe; blob del instrumento en la base `f1c0e6f79b8f73af885dfe9eb8c80e5e0f8ce6c2`, SHA-256 `b5be0b8b8b75d53ddd8f9f6d09ad71a80407a07924562128c32261442920c944`, 130529 bytes, 2726 líneas)
**Versión entregada:** v0.2.8 (provisional)
**Alcance:** exclusivamente el defecto de encapsulación detectado en `_ReadOnlyResourceView`
**Auditor independiente:** Cris (ChatGPT) | **Implementación:** Arena
**Fecha:** 2026-11-21
**Rama:** `arena/441a4bf8-sdv-sdi-sgm`
**Condición:** entrega publicada; **C4-A NO queda aprobado**. La aprobación
corresponde exclusivamente a Cris tras auditoría independiente. **No se inicia
C4-B ni C5** hasta recibir nueva autorización.

---

## 1. Diagnóstico confirmado y corrección aplicada

**Diagnóstico (confirmado):** en v0.2.7, `_ReadOnlyResourceView` conservaba una
referencia directa al recurso mutable mediante `self._res`. Aunque la
asignación ordinaria `vista.state = ...` estaba bloqueada, cualquier consumidor
podía acceder a `vista._res.state` o `vista._res.fd` y modificar el objeto
original: la vista no cumplía plenamente el requisito de solo lectura.

**Corrección aplicada (solución preferida de la instrucción):**
`get_resource(token)` retorna ahora una **instantánea inmutable**
(`_ResourceSnapshot`) con exactamente los campos de consulta necesarios:
`token`, `fd`, `label`, `dev`, `ino`, `state`, `close_result`.

Propiedades verificadas de la instantánea:

1. **No expone ni conserva referencia al objeto interno:** no existe `_res` ni
   ningún atributo de reenvío (sin `__dict__`; `vars()` lanza `TypeError`; la
   clase está restringida a `__slots__ = _FIELDS`). Verificado en
   `C4A8_02_sin_referencia_al_recurso_interno`.
2. **Compatibilidad de lectura por atributo y por clave** conservada (los 7
   campos; `'x' in snap`; clave desconocida → `KeyError`).
   Verificado en `C4A8_01`.
3. **La asignación por atributo o clave es rechazada** (`AttributeError` /
   `TypeError`), y — sin limitarse a la excepción — **incluso una mutación
   hostil del objeto retornado (vía `object.__setattr__`, fuera del alcance
   exigido) no altera el recurso interno**, porque la instantánea es una
   **copia** puntual. Verificado en `C4A8_03` (estado y fd internos intactos
   por nueva consulta, después de un bypass hostil).
4. **Cada nueva llamada a `get_resource(token)` refleja el estado actual** del
   recurso en ese momento (semántica de fotografía: una instantánea obtenida
   antes de una transición no se actualiza retroactivamente — cambio
   documentado respecto a la vista viva de v0.2.7). Verificado en `C4A8_04`.
5. **Máquina de estados y lógica de cierre sin cambios:** `OwnedFdResource` y
   `close_fd()` (contrato estricto de token obligatorio) permanecen intactos.

No se exige protección contra introspección deliberadamente hostil mediante
`object.__setattr__` (conforme a la instrucción); se exige — y se cumple —
encapsulación real en la interfaz normal del instrumento, sin exponer el
objeto interno.

---

## 2. Entregables e identificación

| Artefacto | Valor |
|---|---|
| Instrumento v0.2.8 | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **Commit base** | `edc10b0e28033194247583c4c4789346e59df48f` |
| **Commit de entrega (código)** | `ba77e6dd8fec0884bf96ba06fdbfb95cf3b9c5f8` (padre `edc10b0…`) |
| **Blob del instrumento** | `e9bb5ab2407bc6f0e360f6ca301cc292b7935f35` |
| **SHA-256 del instrumento** | `89efd402c3f42c4322d71e203c7e425b64ede12253fbe26517793501b308d148` |
| **Tamaño / líneas** | **131709 bytes / 2746 líneas** |
| **Diff v0.2.7→v0.2.8** | `DIFF_v0_2_7_A_v0_2_8.patch` — SHA-256 `563b4e517e1ca77902735bbf25503be509df73b7983556e6abfd8042686536df`, blob `d3fc00718e5de0fa72d2e57cb654841f73eab369`, 136 líneas (6745 bytes); **reversible**: el patch inverso sobre v0.2.8 reconstruye v0.2.7 byte a byte (SHA-256 verificado idéntico a la base) |
| **Harness v0.2.8** | `pruebas_unitarias_C4_A_v0_2_8.py` — SHA-256 `c06c07f4c56a41ad0f0a8b5eb45bffbfefdf32873f4f974cda7b19644c362947`, blob `55ee63339f6c3f1c71d23d16f93f2227ea4b53f5`, 783 líneas (30925 bytes) |
| Commit del informe | (este commit, hijo de `ba77e6d`) |
| Rama | `arena/441a4bf8-sdv-sdi-sgm` (sin PR, sin fusión, sin `main`) |
| Recovery point | `/tmp/diag_v027_recovery.py` (SHA-256 idéntico a la base) |

**Alcance del diff (hunks):** línea 83 (`SCRIPT_VERSION`), bloque de la clase
de consulta (`_ReadOnlyResourceView` → `_ResourceSnapshot`) y `get_resource()`,
y la nota de documentación del informe JSON. Ningún otro hunk.

---

## 3. Funciones y clases modificadas (lista exacta)

| Clase / función | Naturaleza | Contenido |
|---|---|---|
| `_ReadOnlyResourceView` | **ELIMINADA** | Era el defecto: conservaba `self._res` (referencia al interno) |
| `_ResourceSnapshot` | **NUEVA clase** | Instantánea inmutable de los 7 campos de consulta; sin referencia al interno (`__slots__ = _FIELDS`); asignación por atributo rechazada; lectura por atributo y clave; copia puntual |
| `CloseErrorLogger.get_resource()` | **Modificada** | Retorna `_ResourceSnapshot(resource)` (copia fresca en cada llamada; `None` si token desconocido); docstring actualizado |
| `SCRIPT_VERSION` | Constante | `"0.2.7"` → `"0.2.8"` |
| Notas del informe JSON (dentro de `_finalize_report`, `main()`) | **Documentación** (1 entrada actualizada, sin sentencias modificadas — declarado para auditoría) | Declara la instantánea inmutable sin referencia al interno |
| `OwnedFdResource`, `CloseErrorLogger.close_fd()`, `register_fd()`, `_identity()`, `close_soundfile()`, T11–T16, `create_fixture`, `safe_create_file_exclusive_anchored`, `write_report_json_robust`, C1, C4-B (no iniciado), C5, `sha256_pread_v2`, clasificación SHA, SoundFile `closefd=False`, `pread`, subtipos WAV, señales sintéticas, criterios PASS/FAIL | **SIN cambios** | Sectores congelados preservados |

---

## 4. RESULTADOS REALES DE CADA PRUEBA

Entorno: contenedor Linux (no Android), Python 3.11.2, sin numpy/soundfile/libsndfile.

### 4.1 Harness v0.2.8 — `pruebas_unitarias_C4_A_v0_2_8.py`

`TOTAL 16 | PASS 15 | EXPECTED_LIMITATION 1 | NOT_EXECUTED 0 | FAIL 0 | ERROR 0` — exit 0

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
| 1 | `C4A8_01_consulta_atributos_y_claves` | **PASS** | Los 7 campos accesibles por atributo y clave con valores correctos; clave desconocida → `KeyError` |
| 2 | `C4A8_02_sin_referencia_al_recurso_interno` | **PASS** | `_res`/`resource`/`_resource`/`_entry`/`res`/`_entries`/`_internal`/`__dict__` ausentes (sentinel); `vars()` → `TypeError`; solo los 7 campos en `dir()` |
| 3 | `C4A8_03_mutacion_rechazada_e_interno_intacto` | **PASS** | `snap.state=`, `snap.fd=` → `AttributeError`; `snap['state']=` → `TypeError`; bypass hostil (`object.__setattr__`) solo altera la copia; **el interno queda intacto** (nueva consulta: estado OPEN, fd idéntico; descriptor real vivo con su `(dev,ino)`) |
| 4 | `C4A8_04_cierre_reflejado_en_nueva_consulta` | **PASS** | Tras el cierre por token, la nueva consulta retorna `CLOSED`/`ok`; la instantánea previa no se muta retroactivamente (fotografía) |
| 5 | `C4A8_05_token_obsoleto_sin_segundo_close` | **PASS** | Segundo cierre con el mismo token → aviso; contador `os.close` = 0 |
| 6 | `C4A8_06_caso_exigible_reutilizacion` | **PASS** | Propietario cierra correctamente → reutilización del mismo número para el MISMO archivo → token antiguo invocado → no cierra la nueva apertura (recurso `CLOSED`); la nueva apertura permanece utilizable y es cerrable con token propio |
| 7 | `C4A8_07_cierre_sin_token_nunca_cierra` | **PASS** | Contrato estricto intacto: sin token → no cierra (aviso), estado OPEN en nueva consulta |
| 8 | `C4A8_08_doble_cierre` | **PASS** | Aviso; 1 `os.close` total |
| 9 | `C4A8_09_token_desconocido_y_no_registrado` | **PASS** | Nunca se cierra; sin errores |
| 10 | `C4A8_10_dos_aperturas_mismo_archivo` | **PASS** | Tokens distintos; cierres independientes |
| 11 | `C4A8_11_error_simulado_e_incierto_sin_reintento` | **PASS** | `OSError(EIO)` conservada; **nueva consulta** → `CLOSE_FAILED_UNCERTAIN`; reintento sin `os.close` |
| 12 | `C4A8_12_soundfile_closefd_false` | **PASS** | SoundFile no cierra el fd; el propietario cierra luego por token |
| 13 | `C4A8_13_reentrada_closing` | **PASS** | Reentrada real: aviso "ya iniciado"; 1 `os.close`; nueva consulta → `CLOSED` |
| 14 | `C4A8_14_auditoria_estatica` | **PASS** | `os.close` solo en `{_close_fd_tracked, close_fd}`; sin `open_tokens`; **sin `_ReadOnlyResourceView`**; `get_resource` retorna `_ResourceSnapshot`; `__slots__ = _FIELDS`; 25 llamadores del logger, todos con token |
| 15 | `C4A8_15_auditoria_runtime` | **PASS** | Flujo completo (fixture + T11–T14 + T15/T16 + `safe_create_file` + informe): 0 cierres de números de recursos registrados vivos fuera del propietario |
| 16 | `C4A8_16_violacion_mismo_archivo_limite` | **EXPECTED_LIMITATION** | Clasificación conservada: no detectable portable; comportamiento documentado verificado; NO es una aprobación de seguridad |

### 4.2 Regresiones (harness congelados, sin modificar)

| Harness | Resultado | Análisis de divergencias |
|---|---|---|
| v0.2.4 (16 pruebas) | **16/16 PASS** (exit 0) | Ninguna divergencia |
| v0.2.5 (11 pruebas) | 10/11; 1 FAIL | Únicamente el pin de versión (`'v0.2.5'` en banner) — documentado desde v0.2.6 |
| C4-A v0.2.6 (13 pruebas) | 5 PASS; 6 FAIL; 2 ERROR | **Divergencias de semántica vista viva → instantánea** (decisión de esta instrucción): los tests capturaban `res = get_resource(tok)` **antes** de la acción y afirmaban el estado **después**; con instantáneas, la referencia previa no se actualiza (el estado real del instrumento es correcto, verificado por consultas frescas). Además: `C4A_10` mutaba el estado desde fuera (`res.state = CLOSING`) — exactamente lo que la instantánea impide; `C4A_09b` aborta por la aserción de instantánea y su **propia limpieza** (`close_quietly(fd3)` con `fd3=None`) lanza TypeError — quirk latente del harness congelado, no del instrumento (reproducción directa del flujo 09b: comportamiento correcto en todos los pasos, verificado con traceback y con consultas frescas). Los comportamientos exigibles de todos estos casos están re-verificados con la interfaz actual en el harness v0.2.8 (`C4A8_02/03/04/10/11/13/16`) |
| C4-A CIERRE v0.2.7 (15 pruebas) | 7 PASS + 1 EXPECTED_LIMITATION; 7 FAIL; 0 ERROR | Mismo origen: patrones de captura previa a la acción (`C4AC_02/03/07/08/09/15`), reflejo en vista viva (`C4AC_11`), y auditoría estática que exigía la presencia de la vista eliminada (`C4AC_12`). Todos los comportamientos exigibles re-verificados en el harness v0.2.8 |

**Confirmación:** ningún harness congelado fue modificado; las divergencias
están íntegramente explicadas por el cambio de interfaz de consulta ordenado
por la instrucción (vista viva → instantánea) y por el quirk de limpieza del
harness v0.2.6 documentado arriba.

### 4.3 Suplementos y controles

| Verificación | Resultado |
|---|---|
| Flujo real de `main()` (utilidades del harness v0.2.5, sin modificarlo) | **OK** — rc=0, banner v0.2.8, `script_version=0.2.8`, 36 resultados, 36 PASS, `interrupted=false`, `close_errors` vacíos, informe publicado |
| `py_compile` v0.2.8 | **PASS** |
| `--help` | **PASS** (rc 0) |

---

## 5. Casos no ejecutados

- **Ningún caso de la batería v0.2.8 quedó NOT_EXECUTED en esta ejecución**
  (la reutilización del número de fd fue reproducible; la vía
  `NOT_EXECUTED`/`NotReproducible` está implementada para `C4A8_06` y
  `C4A8_16` en entornos donde no ocurra — nunca PASS inventado).
- **Android/Termux, audio real, libsndfile real, muestras del proyecto:** no
  ejecutados (prohibidos por el alcance).

---

## 6. Confirmaciones explícitas

- **C1 (creación y publicación segura) permanece intacto:** ningún cambio en
  `write_report_json_robust`, `safe_open_dir_anchored`,
  `_ensure_parents_anchored`, `safe_makedirs_exclusive_anchored` ni helpers C1
  (hunks del diff limitados a la clase de consulta, `get_resource`,
  `SCRIPT_VERSION` y la nota de documentación).
- **C4-B (propagación completa de errores de cierre e interrupciones)
  permanece intacto y NO fue iniciado.**
- **C5 (gestión de interrupciones) permanece intacto:** la única línea en zona
  C5 del diff es la nota de documentación del informe JSON (sin sentencias).
- **`sha256_pread_v2()` y clasificación SHA, SoundFile `closefd=False`,
  `pread`, subtipos WAV, señales sintéticas, T11–T16 y sus criterios
  funcionales, metadatos y alcance general: intactos.**
- **La clasificación `EXPECTED_LIMITATION` se conserva** (`C4A8_16`).
- **No se ejecutó Android/Termux**, ni se usó root, ni se ejecutó audio real,
  ni se usaron muestras del proyecto, ni se modificaron motores DSP ni
  archivos de `main` (branch).
- No se fusionaron ramas; no se abrió ni integró PR; no se publicó en `main`;
  no se eliminó archivo alguno; no se realizó limpieza automática; no se
  reescribió el instrumento (diff de 136 líneas).
- Solo se modificó el archivo autorizado `audioinput_diag_termux.py`, además
  de los artefactos de entrega: `INFORME_CORRECCION_ENCAPSULACION_C4_A_v0_2_8.md`,
  `DIFF_v0_2_7_A_v0_2_8.patch` y `pruebas_unitarias_C4_A_v0_2_8.py` (nuevo).
  Los artefactos anteriores (v0.2.4 a v0.2.7) quedaron intactos.

---

## 7. Riesgos residuales

1. **Aprobación pendiente:** C4-A no está aprobado; corresponde a Cris.
2. **Semántica de fotografía:** una instantánea obtenida antes de una
   transición no se actualiza; los consumidores deben solicitar una consulta
   nueva para ver el estado actual (documentado y verificado en `C4A8_04`).
3. **Compatibilidad de harness congelado:** las divergencias documentadas en
   la sección 4.2 derivan del cambio de interfaz ordenado por la instrucción;
   los harness congelados permanecen intactos como referencia histórica.
4. **`fd` expuesto en la instantánea:** es un valor de consulta (el número en
   el momento de la copia); no otorga propiedad ni permite cerrar: el único
   camino de cierre sigue siendo el token vía `close_fd`.

---

**No se declara C4-A aprobado. No se inicia C4-B ni C5.** Se espera la
evaluación de Cris.
