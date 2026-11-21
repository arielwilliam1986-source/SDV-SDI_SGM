# INFORME DE CORRECCIÓN PUNTUAL C5 — v0.2.12

**Garantía del segundo cierre ante interrupción (C5-A) e identidad real de publicación (C5-C)**

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm`
- **Estado**: PROVISIONAL — pendiente de auditoría independiente limitada de Cris. **La entrega no constituye aprobación.**

---

## 1. Identificación de la corrección

| Campo | Valor |
|---|---|
| Sub-fase | **C5** — corrección puntual autorizada (solo C5-A y C5-C) |
| Versión base | **v0.2.11** (`SCRIPT_VERSION = "0.2.11"`) |
| Versión objetivo | **v0.2.12** (`SCRIPT_VERSION = "0.2.12"`) |
| Commit base (código v0.2.11) | `392c485` — `392c4854beb4639b577461feaf678ce9bd115c68` |
| Commit base (informe v0.2.11) | `656d3c0` — `656d3c046a7c00722373383dc88970b0dbe2c714` |
| Blob SHA-1 del instrumento v0.2.11 (base) | `5a5a052a9d0ea062afd25f690fcdb6d222bff240` |
| SHA-256 del instrumento v0.2.11 (base) | `172a17fbd15620e82af25a07cda952cef9b034b61945e4c14cef9f5d094b4938` |
| Commit final (código v0.2.12) | `acd1d26` — `acd1d26c528b4c21d065e8fcfadfec82040c20be` |
| Commit de corrección documental (instrumento) | `7afdff3` — `7afdff3d80eee51a1ce55c6ea5739960add4d7cc` |
| Blob SHA-1 del instrumento v0.2.12 (revisión documental) | `9abecd18770236e7e5c269ba0e4336f98bdafc27` |
| SHA-256 del instrumento v0.2.12 (revisión documental) | `de69863bafb2a7cb17540b15c59bc41d3165730246983ceeb22fd0a2987060b6` |
| Tamaño exacto (bytes) | **155.558** |
| Número de líneas | **3.181** |
| Diferencia del instrumento vs v0.2.11 | **+155 / −75** (230 líneas cambiadas; numstat real `656d3c0 → d2efc30`), además de **2+/2−** documentales (`d2efc30 → 7afdff3`, nota JSON). El archivo `DIFF_v0_2_11_A_v0_2_12.patch` tiene **284 líneas** (estadística del patch, no del instrumento). v0.2.11: 150.510 B, 3.101 L |

> **Nota estadística (corrección documental)**: la primera edición de este informe declaraba "+154/−75" — conteo propio con el patrón `grep -c "^+[^+]"`, que **no cuenta las líneas añadidas vacías** (una línea añadida vacía se renderiza como `+` suelto y no casa con el patrón). El `numstat` real de git y GitHub registran **+155/−75** para el instrumento entre `656d3c0` y `d2efc30`.

Archivo: `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`

Entregables acompañantes (mismo commit `acd1d26`):

| Archivo | Blob SHA-1 | SHA-256 | Tamaño | Líneas |
|---|---|---|---|---|
| `pruebas_unitarias_C5_v0_2_12.py` | `5a9b9701d2f557912e1e6dba9d6612092f9853a0` | `e3ad942c28f5fa5876561106c197336a71568064b6b101a1d34abd997813c886` | 37.842 B | 930 |
| `DIFF_v0_2_11_A_v0_2_12.patch` | `648e515dd766f8f680586b7fefcf80ea37d8f98a` | `200da613fa2ef1cac452b1fd08d471c416a151bef7688b0b303b484f7901a78a` | 14.965 B | 284 |

---

## 2. Verificación de la base obligatoria (antes de modificar)

Verificado el 2026-11-21 antes de editar:

1. HEAD local = remoto = **`656d3c046a7c00722373383dc88970b0dbe2c714`** (informe v0.2.11) ✓
2. Commit de código v0.2.11 `392c4854…` presente ✓; commit del informe `656d3c04…` presente ✓
3. Blob del instrumento en HEAD = **`5a5a052a9d0ea062afd25f690fcdb6d222bff240`** (referencia exacta) ✓
4. Contenido en disco = SHA-256 `172a17fb…` = **150.510 B, 3.101 L** (v0.2.11 exacto) ✓
5. Árbol de trabajo limpio (único elemento: `__pycache__/` preexistente y sin tocar) ✓
6. `SCRIPT_VERSION = "0.2.11"` ✓

**Todas las condiciones se cumplieron; no fue necesaria detención ni recuperación.**

---

## 3. Diagnóstico previo (evidencia empírica sobre v0.2.11, sin modificar el instrumento)

### C5-A — La KI en el límite impide el intento de cierre del descriptor

Mecanismo confirmado: el helper v0.2.11 invoca `closer.close_fd(...)` con **acceso a atributo** en el punto secuencial posterior a `close_soundfile`. Una KI entregada en ese límite (tras completarse `close_soundfile` y antes de que el cierre del descriptor comience) es capturada por el propio `except KeyboardInterrupt` del bloque del descriptor **sin que el cierre llegara a invocarse**.

Evidencia (closer scriptado sobre un `CloseErrorLogger` real con fd y token reales; la KI se entrega al ACCEDER al método `close_fd`, es decir, después de que `close_soundfile` retornó normalmente):

- `close_soundfile` invocado: **1** (completado);
- `close_fd` invocado: **0** — **el intento de cierre nunca ocurrió**;
- el descriptor **sigue abierto**;
- el helper **retornó `True`** (afirmando haber absorbido la interrupción) — el intento se omitió silenciosamente.

Es decir: el defecto es incluso más sutil que "el cierre no se intenta": el helper **absorbe la KI del límite y reporta haber limpiado**, sin intentar el cierre del descriptor.

### C5-C — `PUBLICADO` por inferencia y siguiendo enlaces simbólicos

Dos manifestaciones confirmadas con escenarios fabricados sobre la función v0.2.11:

| Escenario | Estado retornado v0.2.11 | Correcto |
|---|---|---|
| Final regular **preexistente ajeno** (no de esta ejecución), provisional ausente | **`PUBLICADO`** (inferencia: "el provisional fue eliminado tras un enlace exitoso") | `INDETERMINADO` — sin evidencia de identidad, otro proceso pudo eliminar el provisional |
| Final que es un **enlace simbólico** a un archivo regular, provisional ausente | **`PUBLICADO`** (`os.stat` sigue el enlace) | `NO_PUBLICADO` — la publicación C1 es siempre un enlace duro (archivo regular); nunca declarar `PUBLICADO` siguiendo el enlace |

---

## 4. Corrección implementada (v0.2.12)

### C5-A — `_close_pair_conserving_interrupt()` (solo cuerpo interno; firma y contrato de retorno intactos)

1. **`finally` que abarca el cierre de SoundFile**: el intento de cierre del descriptor propietario queda dentro de un `finally`, garantizado tanto si el cierre de SoundFile retorna normalmente, como si genera `KeyboardInterrupt` (absorbida), como si genera una excepción ordinaria, o si la interrupción llega en el límite entre ambas operaciones.
2. **Pre-vinculación de los métodos del propietario** (`close_sf_fn = closer.close_soundfile`, `close_fd_fn = closer.close_fd`) **antes del primer intento**: elimina la ventana de acceso a atributos entre ambas operaciones (el seam exacto donde el diagnóstico demostró la omisión). Tras la pre-vinculación no queda ningún acceso a atributos entre los dos cierres.
3. **KI dentro del cierre del descriptor**: capturada, `ki_absorbida = True`, **sin reintento** (estado CLOSING — contrato C4-A).
4. **Propagación después de los intentos posibles**: el retorno `True` hace que el llamador re-lance la KI tras la limpieza (contrato v0.2.11 intacto; los 5 sitios llamadores no requieren cambios).
5. **Casos límite documentados en la docstring**: una KI entregada **antes del primer intento** (durante la pre-vinculación) se propaga sin intentos — la limpieza aún no había comenzado y no había intentos posibles. Los errores secundarios siguen registrándose vía `_append_error`/`_record_close_error` (C4-B). No se declara éxito con resultado incierto (el helper no emite declaraciones de éxito; el estado C4-A gobierna).

### C5-C — `_publication_state_after_interrupt()` (solo cuerpo interno; firma y ternario de estados intactos)

1. **Verificación por directorio anclado (C1) y `lstat` relativo al descriptor**: `safe_open_dir_anchored(str(report_path.parent))` + `os.lstat(nombre, dir_fd=parent_fd)` — **sin seguir enlaces simbólicos** y sin comprobaciones de ruta vulnerables a cambios concurrentes. El ancla se cierra en un `finally` con `_close_fd_tracked` (errores de cierre conservados, C4-B).
2. **`PUBLICADO` solo con evidencia**: final y provisional existen, **ambos son archivos regulares** (`S_ISREG` sobre `lstat`) y comparten `(st_dev, st_ino)`.
3. **Identidad distinta o entrada no regular** (p. ej. enlace simbólico — la publicación C1 es siempre un enlace duro regular) → **`NO_PUBLICADO`**; nunca se declara `PUBLICADO` siguiendo el enlace.
4. **Provisional ausente + final regular** → **`INDETERMINADO`**: sin evidencia independiente de identidad, el final no se atribuye a esta ejecución (otro proceso pudo eliminar el provisional). Se elimina la inferencia v0.2.11.
5. **Errores de acceso** (apertura anclada imposible, `lstat` con error distinto de inexistencia) → **`INDETERMINADO`**.
6. **Solo lectura**: ninguna escritura, ningún reintento de publicación, ninguna sobrescritura, ningún borrado. La frase "el informe no se publica" aparece **solo** en los detalles `NO_PUBLICADO` (verdad en esa rama; la rama `PUBLICADO` jamás la contiene — compatibilidad con el harness congelado v0.2.5 mantenida).
7. **Cierre best-effort del ancla de verificación** (ajuste v0.2.12b, descubierto por la prueba obligatoria 7): si una KI llega durante el cierre del descriptor del ancla (el ancla es del mismo directorio que el informe y puede ser alcanzada por la misma condición inyectada), se absorbe **sin reintento** para no perder el anuncio del estado ni el `exit 130` del manejador de la KI original; el resultado del cierre queda incierto; los errores `OSError` siguen registrándose en el acumulador (C4-B).

### Otros

- `SCRIPT_VERSION = "0.2.12"` (banner automático).
- **Nota C5 v0.2.12** añadida a la lista `notes` del informe JSON — ubicada en la región fuente de `_finalize_report()` (congelada). Transparencia: es exclusivamente **documentación de versión** (una cadena en `notes`, sin ningún cambio de lógica), exactamente como se hizo en v0.2.9, v0.2.10 y v0.2.11 con el mismo criterio; ninguna línea de lógica de `_finalize_report` fue tocada (verificado por diff: el único cambio en esa región es la cadena de la nota).

**Funciones modificadas**: `_close_pair_conserving_interrupt()` (cuerpo), `_publication_state_after_interrupt()` (cuerpo), constante `SCRIPT_VERSION`, nota JSON. **Ninguna otra función fue modificada** (`main` sin cambios; `write_report_json_robust` sin cambios; `_reconcile_pending_tests` sin cambios — aparece solo como contexto del diff).

---

## 5. Alcance exacto del cambio (hunks del diff)

| Hunk (línea v0.2.12) | Zona | Contenido |
|---|---|---|
| @83 | Cabecera | `SCRIPT_VERSION "0.2.11" → "0.2.12"` |
| @869–884 | `_close_pair_conserving_interrupt` | docstring + cuerpo: pre-vinculación + `finally` garantizado (C5-A) |
| @944–968 | `_publication_state_after_interrupt` | reemplazo completo del cuerpo: anclaje C1 + lstat + regularidad + INDETERMINADO (C5-C) |
| @3027 | `notes` del informe JSON | nota C5 v0.2.12 (documentación) |

Total: **+155/−75** (230 líneas cambiadas del instrumento; el archivo patch `DIFF_v0_2_11_A_v0_2_12.patch` tiene 284 líneas — estadística del patch, no del instrumento). Todos los hunks dentro del alcance autorizado (C5-A y C5-C) más la nota de versión.

---

## 6. Zonas congeladas — confirmación de integridad

Posiciones en v0.2.12 (verificadas por `grep -n`) frente a los hunks (@83, @869–884, @944–968, @3027): **ninguna intersección con símbolos congelados**.

| Zona congelada | Símbolos (línea en v0.2.12) | ¿Tocada? |
|---|---|---|
| **C1** | `safe_open_dir_anchored` (246), `_ensure_parents_anchored` (315), `safe_makedirs_exclusive_anchored` (375), `os.link` (2627), `write_report_json_robust` (2316 aprox., **sin hunks**) | **No** — el anclaje y la publicación son idénticos; C5-C **utiliza** `safe_open_dir_anchored` (uso permitido, no modificación) |
| **C4-A** | `_close_fd_tracked` (1100), `OwnedFdResource` (1123), `_ResourceSnapshot` (1205), `get_resource` (1343), `register_fd` (1361), `close_fd` (1386), `close_soundfile` (1511) | **No** — los cierres se solicitan por el canal del propietario; sin cambios en estados, tokens ni propiedad |
| **C4-B** | `_reset_close_error_accounting` (805), `_record_close_error` (815), `_drain_close_error_sink` (829), `_mark_close_errors_attributed` (841), `_close_errors_unattributed` (851) | **No** — sin cambios |
| `_reconcile_pending_tests()` | 934 | **No** — aparece únicamente como contexto del diff |
| `_finalize_report()` y reconciliación C5-B/C5-D | cuerpo sin hunks de lógica | **No** (salvo la cadena de documentación en `notes` — ver §4) |
| `sha256_pread_v2()` (664), `os.pread`, SoundFile `closefd=False`, WAV, señales, T11–T16 | — | **No** |

---

## 7. Batería de pruebas obligatorias — resultados reales de ejecución

Comando: `python3 pruebas_unitarias_C5_v0_2_12.py`. Ejecución final:

```
TOTAL 15 | PASS 15 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0 | EXPECTED_LIMITATION 0
```

**NOT_EXECUTED: ninguno. EXPECTED_LIMITATION: ninguno.** Todos los casos ejecutan pruebas reales con inyección; los conteos de intentos se verifican explícitamente con contadores de llamadas sobre closers scriptados que envuelven un `CloseErrorLogger` REAL con fd y token reales (propiedad C4-A intacta).

### C5-A (7 pruebas obligatorias)

| ID | Inyección | Resultado | Evidencia observada |
|---|---|---|---|
| **C5A12_01** | KI **dentro** de `close_soundfile` (antes del efecto del cierre) | **PASS** | retorno `True`; `close_soundfile`=1 (sin reintento); **intento del FD = exactamente 1**; fd cerrado por el intento |
| **C5A12_02** | KI **en el límite**: (a) el cierre de SoundFile se COMPLETA y el KI llega justo al terminar; (b) KI **asíncrona real** (SIGALRM armada al completarse `close_soundfile`; punto de entrega dependiente del planificador — eso es una interrupción asíncrona; la aserción es invariante al punto de entrega) | **PASS** | (a) intento del FD = 1; fd cerrado; `close_soundfile`=1; (b) intento del FD = 1; sin reintentos |
| **C5A12_03** | KI **dentro** de `close_fd` (antes del efecto del cierre) | **PASS** | retorno `True`; `close_fd` invocado **exactamente 1 vez** (cierre incierto NO reintentado); fd en estado incierto (abierto); SoundFile cerrado |
| **C5A12_04** | **Excepción ordinaria** (`RuntimeError`) de SoundFile | **PASS** | la excepción **se propaga** (no se absorbe); el intento del FD = 1 (**el `finally` garantiza el intento**); fd cerrado |
| **C5A12_05** | Cierre **normal** de ambos | **PASS** | `sf`=1 llamada, `fd`=1 llamada; retorno `False`; ambos cerrados |
| **C5A12_06** | Verificación agregada: exactamente **un intento** del FD en los 5 escenarios obligatorios (recursos frescos por escenario) | **PASS** | 5 escenarios: intento del FD = 1 exactamente en cada uno |
| **C5A12_07** | **Sin reintento** de recursos inciertos | **PASS** | KI dentro de `close_fd` → `close_fd`=1; KI dentro de `close_soundfile` → `close_soundfile`=1 y `close_fd`=1 |

### C5-C (8 pruebas obligatorias)

| ID | Escenario | Resultado | Evidencia observada |
|---|---|---|---|
| **C5C12_01** | Final + provisional con la **misma identidad** (enlace duro real) | **PASS** | `PUBLICADO`; el detalle menciona la identidad `(st_dev, st_ino)` y la regularidad de ambos |
| **C5C12_02** | Final **preexistente ajeno** + provisional propio | **PASS** | `NO_PUBLICADO` (identidades distintas) |
| **C5C12_03** | Provisional **ausente** + final regular | **PASS** | `INDETERMINADO` (sin evidencia de identidad; detalle explica que otro proceso pudo eliminar el provisional) — **nunca `PUBLICADO` por inferencia** |
| **C5C12_04** | Final **simbólico** (sin provisional; y con provisional) | **PASS** | `NO_PUBLICADO` en ambos casos (`lstat` no sigue el enlace; nunca `PUBLICADO`) |
| **C5C12_05** | **Error de acceso** (directorio sin permisos → apertura anclada imposible) | **PASS** | `INDETERMINADO` |
| **C5C12_06** | **Flujo real**: publicación real + KI antes de eliminar el provisional (`os.link` real + KI) | **PASS** | `[ESTADO DE PUBLICACION: PUBLICADO]` anunciado (identidad verificable: provisional presente); provisional conservado; rc=130; **1 solo anuncio** |
| **C5C12_07** | **Flujo real**: publicación real, eliminación del provisional completada y KI posterior (cierre del padre) | **PASS** | **NO se afirma `PUBLICADO` sin evidencia**; se anuncia `[ESTADO DE PUBLICACION: INDETERMINADO]`; rc=130; sin limpieza extra |
| **C5C12_08** | **Ninguna segunda publicación o sobrescritura** | **PASS** | (a) 5 escenarios unitarios: la instantánea del directorio `(nombre, dev, ino)` es **idéntica** antes y después de la verificación (solo lectura); (b) flujo: 1 solo anuncio de estado, 1 único informe, sin archivos extra |

### Historial de depuración (transparencia)

El instrumento no fue modificado durante la depuración del harness salvo por el ajuste **v0.2.12b** documentado en §4.7, motivado directamente por la prueba obligatoria C5-C-7: con la inyección en el cierre del padre, la **verificación del estado** abría y cerraba su propio ancla en el mismo directorio (con el informe ya presente) y la misma condición inyectada alcanzaba ese cierre, perdiéndose el anuncio del estado (la KI escapaba del manejador; rc=None vía módulo, evidenciado con trazas de eventos). La corrección (absorción best-effort de la KI **solo** en el cierre del ancla de la verificación) preserva el anuncio y el exit 130. En el harness, la aserción de disparo pasó de `== 1` a `>= 1` (la verificación del ancla también es víctima de la misma condición inyectada; el foco del caso es el anuncio y el rc). Una corrección menor de empalme (ancla de la nota JSON no coincidente) abortó de forma segura **antes** de escribir el archivo y se corrigió sin efectos residuales.

---

## 8. Regresiones ejecutadas (harnesses congelados, sin modificaciones)

| Harness (congelado) | Sobre v0.2.12 | Referencia v0.2.11 | Δ |
|---|---|---|---|
| `pruebas_unitarias_C5_v0_2_12.py` (nuevo) | **15/15 PASS** | — | — |
| `pruebas_unitarias_C5_v0_2_11.py` | **16 PASS + 2 FAIL** | 18/18 | **2 FAIL documentados como pins congelados de comportamiento corregido**: (1) `C5_13_ki_durante_eliminacion_provisional` — su parte (b) exige `fired == 1` y anuncia `PUBLICADO` en el escenario "provisional eliminado + KI posterior", que en v0.2.12 es **INDETERMINADO** (la corrección C5-C elimina la inferencia) y la verificación del ancla añade un segundo disparo absorbido; (2) `C5_18_ejecucion_normal` — "banner v0.2.11 ausente" (pin de versión, análogo al pin de v0.2.5). Las partes (a) de C5_13 (PUBLICADO con provisional presente) y todos los demás casos siguen PASS |
| `pruebas_unitarias_C4_B_v0_2_9.py` | **15/15 PASS** | 15/15 | ninguno |
| `pruebas_unitarias_C4_B_v0_2_10.py` | **10/10 PASS** | 10/10 | ninguno (la semántica del helper C5-A para KI dentro de los cierres se conserva) |
| `pruebas_unitarias_v0_2_4.py` (C5) | **16/16 PASS** | 16/16 | ninguno |
| `pruebas_unitarias_v0_2_5.py` (C5 flujo real) | **10/11** — único FAIL: pin de banner ("no anuncia v0.2.5") | 10/11 (mismo pin) | ninguno |
| `pruebas_unitarias_C4_A_v0_2_8.py` | **15 PASS + 1 EXPECTED_LIMITATION (`C4A8_16`) + 0F/0E** | igual | ninguno |
| `pruebas_unitarias_C4_A_v0_2_6.py` | 4 PASS / 7 FAIL / 2 ERROR | **idéntico caso a caso** (baseline v0.2.11 regenerada desde git `392c485`, SHA-256 verificado `172a17fb…`) | ninguno |
| `pruebas_unitarias_C4_A_CIERRE.py` | 5 PASS / 9 FAIL / 1 EXPECTED_LIMITATION | **idéntico caso a caso** | ninguno |

**Suplemento de flujo real** (`main()` completo con `--shared`): rc=0; banner v0.2.12; 36 resultados, 36 PASS; `interrupted=false`; `environment_close_errors` vacío; `close_errors` vacío en los 36; `metadata.script_version="0.2.12"`; nota v0.2.12 en `notes`.

---

## 9. Reversibilidad del diff

`DIFF_v0_2_11_A_v0_2_12.patch` (284 líneas; estadísticas reales del instrumento entre `392c485` y `d2efc30`: **+155/−75**) generado con `git diff 392c485 -- <instrumento>`. Verificación ejecutada: aplicación inversa (`patch -R`) sobre el instrumento v0.2.12 (revisión `acd1d26`) →

```
sha256 = 172a17fbd15620e82af25a07cda952cef9b034b61945e4c14cef9f5d094b4938
```

que es **exactamente** el SHA-256 del instrumento v0.2.11 (blob `5a5a052a…`, 150.510 B). El diff es reversible bit a bit.

---

## 10. Limitaciones pendientes

- **KI antes del primer intento**: una KI entregada durante la pre-vinculación de los métodos del propietario (antes de cualquier intento de limpieza) se propaga sin intentos — la limpieza aún no había comenzado y no había intentos posibles (documentado en la docstring del helper).
- **Cierre del ancla de verificación**: si una KI llega durante ese cierre, se absorbe best-effort (sin reintento, resultado incierto, sin pérdida de errores `OSError` — C4-B) para preservar el anuncio del estado y el exit 130; una KI entregada en cualquier otro punto de la verificación (p. ej. durante `lstat`) abortaría el manejador hacia el nivel de módulo con rc=130 pero sin anuncio (ventana inherentemente no eliminable ante interrupciones asíncronas en cada bytecode).
- **`INDETERMINADO` en "provisional eliminado"**: el escenario de flujo "publicación + unlink completado + KI posterior" ahora anuncia INDETERMINADO (v0.2.11 anunciaba PUBLICADO por inferencia). El informe en disco es real y correcto; lo que ya no se afirma es su atribución a esta ejecución sin evidencia. El harness congelado v0.2.11 pins el comportamiento anterior (§8).
- **Final simbólico → NO_PUBLICADO** (no INDETERMINADO): rationale — la publicación C1 produce siempre un enlace duro regular; una entrada simbólica con ese nombre no puede ser la publicación de esta ejecución.
- **Este informe es provisional. La aprobación corresponde exclusivamente a Cris** (auditoría independiente limitada a los dos defectos descritos y verificación de sectores congelados).

---

## 11. Confirmaciones de alcance y ejecución

- **No hubo ejecución en Android/Termux ni con audio real**: toda la ejecución se realizó en el entorno de trabajo (Linux sandbox) con capa simulada `numpy`/`soundfile`, fd/tokens reales sobre archivos temporales propios, y KI/fallos **inyectados exclusivamente por mocks** (closers scriptados, `os.link`/`os.close`/`os.unlink` envueltos, SIGALRM para la KI asíncrona real, `chmod` para el error de acceso). Ningún fallo espontáneo del OS; sin muestras del proyecto; sin motores DSP; sin root.
- Sin merges, sin PR, sin publicación en otra rama; sin borrado de archivos ni limpieza automática (los temporales de prueba se eliminan por el propio harness en sus directorios exclusivos `tempfile`, no son archivos del usuario ni del instrumento); sin reescritura del instrumento (2 funciones reemplazadas por extracción de límites exactos con verificación de unicidad + versión + nota).
- Técnicas permitidas: inspección estática, pruebas unitarias aisladas, inyección de interrupciones (incluida SIGALRM asíncrona real), `py_compile` (OK), `--help` (rc=0), ejecución simulada de `main()`.
- **Ninguna prueba fue declarada PASS sin haberse ejecutado**: los 15 casos y todas las regresiones corresponden a ejecuciones reales con salida capturada.
- **`main` sin cambios**; `_reconcile_pending_tests`, `_finalize_report` (lógica), C1, C4-A y C4-B intactos (§6); el diff es reversible bit a bit (§9).

---

## 12. Corrección documental final (2026-11-21)

Autorizada y limitada a dos puntos documentales; **sin ninguna modificación funcional**:

1. **Estadísticas reales del instrumento**: el informe declaraba "+154/−75" (conteo propio defectuoso; el patrón `grep -c "^+[^+]"` omite las líneas añadidas vacías). Estadísticas reales (`git diff --numstat` entre `656d3c0` y `d2efc30`, coincidentes con GitHub): **+155/−75** (230 líneas cambiadas del instrumento). Actualizado en §1 y §5; la cifra "284 líneas" se mantiene como estadística **del archivo patch** (no del instrumento). Causa de la discrepancia documentada para el auditor.
2. **Frase restaurada en la nota C5 v0.2.11 de `notes` (JSON del instrumento)**: la primera edición del empalme v0.2.12 corrigió el *ancla* del patrón de inserción de la nota v0.2.12 pero no el *texto de reemplazo*, que eliminó el fragmento `limitacion explicitamente y sale con codigo ` y dejó la cadena concatenada incoherente: "...una KI durante la reconstruccion del informe registra la no nulo.". Corrección aplicada **únicamente a la cadena documental** (diff completo: **2+/2−**, hunk único dentro de `notes`):

```
-                'falsa); una KI durante la reconstruccion del informe registra la '
-                'no nulo.',
+                'falsa); una KI durante la reconstruccion del informe se '
+                'documenta explicitamente y produce un codigo de salida no nulo.',
```

   Significado restaurado (equivalente al original): una interrupción durante la reconstrucción del informe **se documenta explícitamente y produce un código de salida no nulo**. El flujo, las condiciones, los bloques `try/except/finally` y toda la lógica de `_finalize_report()` quedan **intactos** (verificado por el diff: el único cambio está dentro de la lista `notes`).

**Verificación final (puntual, sin repetir la batería completa según la autorización)**:
- `py_compile` OK; `--help` rc=0.
- Diff completo del cambio: solo las 2 líneas documentales indicadas (evidencia de no-funcionalidad).
- Re-verificación **puntual** del comportamiento C5-A y C5-C ya auditado: `pruebas_unitarias_C5_v0_2_12.py` → **15/15 PASS** (no se repitieron el resto de harnesses).
- C1, C4-A, C4-B, `_reconcile_pending_tests()` y la lógica de `_finalize_report()` sin modificación alguna.
- `main()` (función) intacta; sin PR, sin merge, sin publicación en la rama `main`; sin Android/Termux ni audio real.

**Identidad del instrumento tras la corrección documental**: blob `9abecd18770236e7e5c269ba0e4336f98bdafc27` · SHA-256 `de69863bafb2a7cb17540b15c59bc41d3165730246983ceeb22fd0a2987060b6` · **155.558 B** · **3.181 L** (antes: blob `d8006f69…`, SHA-256 `e8e93a17…`, 155.512 B — mismo número de líneas: el cambio solo afecta el contenido de 2 líneas de la cadena). El archivo `DIFF_v0_2_11_A_v0_2_12.patch` (blob `648e515d…`) **no se regeneró**: permanece como el registro fiel de la corrección de código en el commit `acd1d26`; la corrección documental (commit `7afdff3`) es posterior y puramente de cadena.

---

## 13. Cadena de commits de la sesión (rama `arena/441a4bf8-sdv-sdi-sgm`)

```
50bae98  (base)      v0.2.4
fb2a96c  → b947c05   v0.2.5 (código + informe)
5e38e0f  → b91622b   v0.2.6 (código + informe)
3f850b6  → edc10b0   v0.2.7 (código + informe CIERRE)
ba77e6d  → 25e1302   v0.2.8 (código + informe)
2456195  → 0cc9dea   v0.2.9 (código + informe)
045af46  → 2a134f2   v0.2.10 (código + informe)
392c485  → 656d3c0   v0.2.11 (código + informe) ← BASE de v0.2.12
acd1d26              v0.2.12 (código: instrumento + harness C5 v0.2.12 + DIFF)
d2efc30              informe de corrección puntual C5 (v0.2.12)
7afdff3              corrección documental final: nota C5 v0.2.11 restaurada en notes (2+/2−, sin cambios funcionales) ← este informe
```

Todos los artefactos previos permanecen intactos (blobs verificados tras el commit: informes y harnesses v0.2.1–v0.2.11, DIFFs v0.2.3–v0.2.11 con sus SHA-1 sin cambios).
