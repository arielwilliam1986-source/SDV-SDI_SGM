# INFORME DE CORRECCIÓN C4-B — v0.2.10

**Registro único por evento de cierre fallido en la escritura del informe e informe de errores de cierre ante interrupción durante la publicación**

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm`
- **Estado**: PROVISIONAL — pendiente de auditoría de Cris. **Ningún resultado de este informe constituye una aprobación.**

---

## 1. Identificación de la corrección

| Campo | Valor |
|---|---|
| Sub-fase | **C4-B** — cierre de dos defectos residuales (C4-B-1 y C4-B-2) |
| Versión base | **v0.2.9** (`SCRIPT_VERSION = "0.2.9"`) |
| Versión objetivo | **v0.2.10** (`SCRIPT_VERSION = "0.2.10"`) |
| Commit base (entrega v0.2.9, informe) | `0cc9dea` — `0cc9deac7d28a5bb881d3b6e32fbd74a36fb601d` |
| Commit de la versión v0.2.9 del instrumento | `2456195` — `245619504a1c8c1bb5e6ad35d84c62fb5fd25bdc` |
| Blob SHA-1 del instrumento v0.2.9 (base) | `6d1cdadc64a0ebe4085dd79a94d6ccd4a7191b11` |
| SHA-256 del instrumento v0.2.9 (base) | `666e2cae5e866dbcae962effb7efd6f50d7aeea84adfa7ae2a62556311e1ac4b` |
| Commit final (código v0.2.10) | `045af46` — `045af464bc9bd28381d1e73455c7b061b54c9544` |
| Blob SHA-1 del instrumento v0.2.10 | `27b844b2aa2d3be074e76cbc4420fe046913129d` |
| SHA-256 del instrumento v0.2.10 | `54b7bf03af194043f48eb8f3cc27377840dffd1f674e453e99b5da2d22291253` |
| Tamaño exacto (bytes) | **138.962** |
| Número de líneas | **2.872** |
| Diferencia vs v0.2.9 | +25 / −7 líneas efectivas (diff de 72 líneas; v0.2.9: 137.672 B, 2.854 L) |

Archivo: `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`

Entregables acompañantes (mismo commit `045af46`):

| Archivo | Blob SHA-1 | SHA-256 | Tamaño | Líneas |
|---|---|---|---|---|
| `pruebas_unitarias_C4_B_v0_2_10.py` | `d02da9bfb5bb256cce325ba8e357507b6dbf1ed2` | `6aab855e7b775ae1ca5c07f58a97694adc5d40939327fd0ac7e3893f6ac7afaa` | 32.136 B | 766 |
| `DIFF_v0_2_9_A_v0_2_10.patch` | `6ef1bbce72cd006f481eb171d7dd8c8b1c08479e` | `5013375892dd28240d234e232a4fafa3081c8d7e17eadc1ead9c4164237c38f3` | 4.265 B | 72 |

---

## 2. Verificación del punto de partida (antes de modificar)

Condiciones exigidas, verificadas el 2026-11-21 antes de tocar el instrumento:

1. El contenido del instrumento en disco correspondía **exactamente** al commit `2456195`: SHA-256 `666e2cae…` = blob `6d1cdadc…` — **verificado**.
2. Blob SHA-1 `6d1cdadc…` — **verificado** en remoto y, tras recuperación, en local.
3. Árbol de trabajo limpio — **verificado tras recuperación** (ver incidencia abajo).
4. No se reconstruyó el instrumento desde otra versión: el contenido de disco se comparó bit a bit contra los blobs remotos antes de cualquier operación.
5. No se copiaron archivos de otras ramas.

**Incidencia del entorno (transparencia)**: la sandbox fue restaurada entre la entrega v0.2.9 y esta tarea; el clon local perdió los commits (HEAD local quedó en `50bae98`, base antigua) mientras el remoto permaneció intacto en `0cc9dea`. Se aplicó el procedimiento de recuperación ya establecido en la sesión (caso v0.2.7): **comparación bit a bit de los 15 artefactos del disco contra los blobs del árbol remoto `0cc9dea` (todos `OK`, incluido el instrumento = `6d1cdadc`) y posteriormente `git reset --hard origin/arena/441a4bf8-sdv-sdi-sgm`**. Tras la recuperación, las 5 condiciones del punto de partida se verificaron nuevamente y todas coincidieron. Ninguna discrepancia de contenido; únicamente el estado del clon local.

---

## 3. Diagnóstico previo (evidencia empírica sobre v0.2.9, sin modificar el instrumento)

### C4-B-1 — Registro duplicado de errores en `write_report_json_robust()`

Mecanismo confirmado en código: `CloseErrorLogger.close_fd()` registra el error del cierre fallido vía `_append_error()` → `_record_close_error()` (propietario), y `_close_fd_tracked()` lo registra directamente. Las llamadas adicionales a `_record_close_error()` volvían a registrar **el mismo evento** (con **otro** `_close_err_id`, pues cada registro asigna un id nuevo).

Evidencia empírica (llamadas aisladas a `write_report_json_robust` con mocks sobre `os.close`; directorio fresco por escenario; instrumento v0.2.9 sin modificar):

| Escenario (1 evento real c/u) | Disparos del mock | Entradas en el acumulador | IDs |
|---|---|---|---|
| Solo cierre del temporal | 1 | **2** (`report_tmp_fd` ×2) | `[1, 2]` |
| Solo cierre del directorio padre | 1 | **2** (`report_parent_fd` ×2) | `[1, 2]` |
| Ambos descriptores (2 eventos reales) | 1 y 1 | **4** (2+2) | `[1, 2, 3, 4]` |

En los tres escenarios el detalle del error **sí** llegaba al retorno (`close_err = closer.summary()` y/o `parent_close_err`), es decir, el defecto era de duplicación en el acumulador, no de pérdida. También se verificó que un evento único quedaba con **dos ids distintos** (confirmación de doble registro con nueva identidad).

### C4-B-2 — KeyboardInterrupt durante la publicación

El `except KeyboardInterrupt` de `main()` alrededor de `write_report_json_robust()` ejecutaba `sys.exit(130)` **antes** del drenaje final de errores (que está tras el bloque de impresión del resultado de escritura). Evidencia empírica (flujo `main()` completo con capa simulada; KI inyectada en la primera escritura del contenido JSON + fallo de cierre del temporal inyectado):

- rc = **130**; `'[INTERRUMPIDO] KeyboardInterrupt durante la publicacion…'` presente en la salida;
- acumulador con el error registrado (`report_tmp_fd`) — el registro del propietario sí ocurrió;
- ocurrencias de `'[cierre pendiente]'` en la salida de diagnóstico: **0** — **el error no llegaba a la salida**;
- informe no publicado; provisional conservado en disco (semántica C1/C5 correcta).

Ambos defectos confirmados **exactamente como fueron descritos en la autorización**.

---

## 4. Corrección implementada (v0.2.10)

Cambios mínimos, 5 hunks (ver §5):

1. **C4-B-1.A (temporal)**: eliminada la llamada `_record_close_error()` redundante tras `closer.close_fd(tmp_fd, 'report_tmp_fd', token=tmp_token)`. El propietario ya registra el evento. El detalle se conserva en el retorno vía `close_err = closer.summary()` y en el acumulador persistente. **No se eliminó el registro original del propietario.**
2. **C4-B-1.B (directorio padre)**: eliminada la llamada `_record_close_error()` redundante tras `_close_fd_tracked(parent_fd, 'report_parent_fd')`. Se conserva íntegro el bloque que construye `parent_close_err` y lo agrega al tercer elemento del retorno (detalle no perdido). **No se eliminó el registro original (`_close_fd_tracked` registra y retorna la excepción).**
3. **C4-B-2 (KI durante publicación)**: en el `except KeyboardInterrupt` de `main()`, **antes** de `sys.exit(130)` se agrega el drenaje e informe de los errores pendientes con el mismo formato del drenaje final (`[cierre pendiente] {label}: {strerror}`). No hay segunda publicación, no se borra el provisional, no hay nuevos fallbacks de escritura, el código de salida 130 se conserva (C5 intacto).
4. **Nota JSON**: nuevo elemento en `notes` (nivel superior del informe) documentando la corrección v0.2.10.
5. `SCRIPT_VERSION = "0.2.10"` (el banner se anuncia automáticamente desde la constante).

Otras rutas de cierre de la función revisadas (mandato "revisar si existen otras duplicaciones equivalentes"):
- `report_tmp_unlink` (`os.unlink` tras publicación exitosa): registra **una vez**, no es un cierre y no tiene registro redundante — sin cambio.
- La apertura del temporal (`os.open` O_EXCL) y sus retornos tempranos: no registran cierres — sin cambio.
- `safe_open_dir_anchored`: retorna el fd del directorio; su cierre único es el del `finally` externo — sin cambio.
- No existen otros sitios de `os.close` en la función fuera de `closer.close_fd` (temporal) y `_close_fd_tracked` (padre) — verificado por `grep` (los únicos `os.close(` del instrumento están en `_close_fd_tracked` y `close_fd`).

**Funciones modificadas**: `write_report_json_robust()` (2 sitios), `main()` (manejador KI de publicación + nota JSON), constante `SCRIPT_VERSION`. **Ninguna otra función o clase fue modificada.**

---

## 5. Alcance exacto del cambio (hunks del diff)

| Hunk (línea v0.2.10) | Zona | Contenido | +/− |
|---|---|---|---|
| @83 | Cabecera | `SCRIPT_VERSION "0.2.9" → "0.2.10"` | 1/1 |
| @2346–2358 | `write_report_json_robust` (finally del temporal) | registro único C4-B-1.A | 5/2 |
| @2404–2413 | `write_report_json_robust` (bloque del padre) | registro único C4-B-1.B | 4/1 |
| @2745–2749 | `main` → `notes` del JSON | nota v0.2.10 | 5/0 |
| @2814–2822 | `main` → manejador KI de publicación | drenaje + informe antes de `exit(130)` | 9/0 |

Total: 25+/7− (72 líneas de diff). **Todos los hunks dentro del alcance C4-B autorizado.**

---

## 6. Zonas congeladas — confirmación de integridad

| Zona congelada | ¿Tocada? | Evidencia |
|---|---|---|
| **C1** (apertura/creación anclada, publicación atómica sin sobrescritura, tmp) | **No** | Ningún hunk toca `safe_open_dir_anchored`, `safe_makedirs_exclusive_anchored`, `_ensure_parents_anchored`, `os.link`, `os.unlink`, política O_EXCL. El diff de 5 hunks no incluye esas líneas |
| **C4-A** (`OwnedFdResource`, `_ResourceSnapshot`, tokens, propiedad, estados) | **No** | `close_fd` y `close_soundfile` intactos; solo se eliminó un registro redundante EXTERNO al propietario |
| **C4-B** (acumulador persistente, ids, atribución — v0.2.9) | **No** (salvo lo autorizado) | `_close_error_ledger`, `_close_error_seq`, `_attributed_close_error_ids`, `_record_close_error`, `_drain_close_error_sink`, `_mark_close_errors_attributed`, `_close_errors_unattributed`, `_reset_close_error_accounting`: **sin cambios**; el drenaje en el manejador KI reutiliza `_drain_close_error_sink()` tal cual |
| **C5** (interrupciones, clasificación, segundo entorno, exit codes) | **No** | El manejador KI conserva su condición, su mensaje y su `sys.exit(130)`; solo se inserta el drenaje informativo ANTES del exit. Regresiones C5 16/16 y 10/11-pin |
| `sha256_pread_v2()` y clasificaciones, `os.pread` | **No** | Sin hunks |
| SoundFile `closefd=False`, formatos WAV, señales sintéticas | **No** | Sin hunks |
| T11–T16 funcionales, metadata, motores DSP, procesamiento de audio | **No** | Sin hunks |

---

## 7. Batería C4-B v0.2.10 — resultados reales de ejecución

Comando: `python3 pruebas_unitarias_C4_B_v0_2_10.py` (en `herramientas/diagnostico_audio/etapa2/`). Ejecución final:

```
TOTAL 10 | PASS 10 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0
```

**Casos NOT_EXECUTED: ninguno.** Regla de clasificación: NOT_EXECUTED solo ante ImportError/ModuleNotFoundError; FAIL ante AssertionError; ERROR ante cualquier otra excepción. Ningún caso fue contado como PASS sin ejecución real.

### C4-B-1 (llamadas aisladas a `write_report_json_robust`)

| Caso | Inyección | Resultado | Evidencia observada |
|---|---|---|---|
| **C4B10_01** registro único — cierre del temporal | `os.close` del fd temporal falla (EIO); mock confirma 1 disparo | **PASS** | 1 evento → **1 entrada** `report_tmp_fd` en el acumulador (antes eran 2); errno=EIO; id único; detalle `'report_tmp_fd (Input/output error)'` presente en el retorno |
| **C4B10_02** registro único — cierre del padre | cierre del fd del directorio padre falla (EIO); mock confirma 1 disparo | **PASS** | 1 evento → **1 entrada** `report_parent_fd`; errno=EIO; id único; detalle `'parent_fd close errno=5: Input/output error'` en el retorno |
| **C4B10_03** ambos descriptores | ambos cierres fallan (2 eventos reales) | **PASS** | **2 entradas** (1+1), ids **distintos** (1 y 2), cada evento exactamente una vez; el retorno contiene AMBOS detalles |
| **C4B10_04** ids únicos, sin ocurrencia duplicada | 4 escenarios: limpio / temporal / padre / ambos | **PASS** | entradas 0/1/1/2 (esperadas); `_close_err_id` único y presente en todas; ninguna tupla (label, errno, strerror) repetida en un mismo acumulador |
| **C4B10_05** retorno conserva los errores | ambos fallos; escritura primaria intacta | **PASS** | `err is None` (primario no afectado); `close_err = "report_tmp_fd (Input/output error) | parent_fd close errno=5: Input/output error"`; acumulador consistente con el retorno (1+1) |

### C4-B-2 (flujo `main()` real con capa simulada)

| Caso | Inyección | Resultado | Evidencia observada |
|---|---|---|---|
| **C4B10_06** KI en escritura, sin fallos de cierre | KI en la 1ª escritura del JSON (mock confirma 1 disparo) | **PASS** | rc=130; mensaje `[INTERRUMPIDO]…publicacion` presente; **sin publicación**; provisional conservado en disco; acumulador vacío (sin anunciar errores inexistentes: 0 líneas `[cierre pendiente]`) |
| **C4B10_07** KI en escritura + cierre del temporal | KI (1 disparo) + EIO en cierre del temporal (1 disparo) | **PASS** | rc=130; `'[cierre pendiente] report_tmp_fd'` aparece **exactamente 1 vez** en la salida; **1 entrada** en el acumulador (registro único también bajo KI); sin publicación; provisional conservado |
| **C4B10_08** KI en publicación + cierre del padre | KI en `os.link` del informe (1 disparo — **ruta alcanzada**) + EIO en el cierre del padre (1 disparo) | **PASS** | rc=130; `'[cierre pendiente] report_parent_fd'` **1 vez**; **1 entrada**; sin publicación (el link nunca se completó); provisional conservado (el unlink solo ocurre tras link exitoso) |
| **C4B10_09** cada evento 1 vez en la salida | KI + fallo temporal + fallo padre (3 disparos confirmados) | **PASS** | rc=130; **2 líneas** `[cierre pendiente]` (temporal ×1, padre ×1); acumulador 1+1 sin duplicados; ids únicos |
| **C4B10_10** rc=130, sin publicación, provisional conservado | 4 escenarios KI (escritura; escritura+temporal; link+padre; escritura+ambos) | **PASS** | en los 4: rc=130; `find_report` sin resultado (no publicado); `.json.tmp` presente en disco (sin limpieza automática); mensaje explícito de no publicación |

### Confirmación de que las inyecciones realmente ocurrieron

Cada caso verifica los contadores de disparo del mock **antes** de evaluar el comportamiento (`fired_ki_write`, `fired_ki_link`, `fired_tmp`, `fired_parent`); un escenario cuya inyección no se hubiera disparado quedaría FAIL (o ERROR), nunca PASS. En C4B10_08 la ruta "KI en `os.link` + cierre del padre" resultó **alcanzable**: durante la propagación de la KI se ejecutan el `finally` interno (cierre del temporal) y el `finally` externo (cierre del padre), por lo que el fallo inyectado del padre se produce dentro de la ventana de interrupción, exactamente el escenario descrito en la autorización.

### Historial de depuración del harness (transparencia)

El instrumento no fue modificado durante la depuración del harness (SHA-256 constante `54b7bf03…` desde el empalme). Dos correcciones, ambas de mi harness: (1) el `write_file` duplicó los caracteres de continuación de línea (33 líneas) — corrección mecánica; (2) el monkeypatch de `CloseErrorLogger.register_fd` no reenviaba `self` (TypeError en los 5 casos aislados) — corrección de una línea. El script de diagnóstico previo también tuvo 2 defectos míos (falta de `pathlib.Path` — lección ya conocida de C4AC_13; e impresión del ledger de **otra instancia** del módulo: el harness crea su propia instancia del instrumento, por lo que el diagnóstico definitivo usa una única instancia).

---

## 8. Evidencia de ausencia de duplicación

- Aislado (por escenario): 1 evento → 1 entrada; 2 eventos → 2 entradas; ids distintos entre eventos y únicos dentro del acumulador; ninguna tupla (label, errno, strerror) repetida (C4B10_01..04).
- Flujo completo bajo interrupción: los errores de cierre producidos durante la escritura/publicación interrumpida aparecen **exactamente una vez** en la salida de diagnóstico y **una vez** en el acumulador (C4B10_07/08/09).
- Regresión directa del defecto original: el escenario "solo temporal" que en v0.2.9 producía 2 entradas (ids `[1, 2]`) produce ahora **1 entrada** (id `[1]`); "ambos" pasaba de 4 entradas a **2**.

## 9. Evidencia de conservación de errores durante KeyboardInterrupt

- La KI en `os.write` se propaga por los `finally` de `write_report_json_robust`: el cierre del temporal y del padre se ejecutan durante el desenredo; sus errores quedan registrados por el propietario (propietario intacto).
- El manejador KI de `main()` ahora drena e imprime **antes** de `sys.exit(130)`: los errores llegan a la salida de diagnóstico (0 → 1 línea por evento; verificado en 3 escenarios con fallos y 1 sin fallos).
- El acumulador persistente (C4-B v0.2.9) conserva las entradas: nada se pierde, nada se duplica.
- No se publica el informe y el provisional no se borra en ningún escenario de KI (C4B10_06/07/08/10).

---

## 10. Regresiones ejecutadas (harness congelados, sin modificaciones)

| Harness (congelado) | Sobre v0.2.10 | Referencia sobre v0.2.9 | Δ |
|---|---|---|---|
| `pruebas_unitarias_C4_B_v0_2_9.py` | **15/15 PASS** | 15/15 | ninguno (sus aserciones de C4B_13 son de presencia y siguen cumpliéndose con registro único) |
| `pruebas_unitarias_v0_2_4.py` (C5) | **16/16 PASS** | 16/16 | ninguno |
| `pruebas_unitarias_v0_2_5.py` (C5 flujo real) | **10/11** — único FAIL: "el banner no anuncia v0.2.5" (pin de versión esperado; el banner ahora anuncia v0.2.10) | 10/11 (mismo pin) | ninguno |
| `pruebas_unitarias_C4_A_v0_2_8.py` | **15 PASS + 1 EXPECTED_LIMITATION (`C4A8_16`) + 0 FAIL / 0 ERROR** | igual | ninguno |
| `pruebas_unitarias_C4_A_v0_2_6.py` | 4 PASS / 7 FAIL / 2 ERROR | **idéntico caso a caso** | **ninguno** (artefactos documentados de semántica snapshot en harness congelados) |
| `pruebas_unitarias_C4_A_CIERRE.py` | 5 PASS / 9 FAIL / 1 EXPECTED_LIMITATION | **idéntico caso a caso** | **ninguno** |

**Suplemento de flujo real** (`main()` completo, capa simulada): rc=0; banner `v0.2.10`; 36 resultados, 36 PASS; `interrupted=false`; `environment_close_errors` vacío; `close_errors` vacío en los 36 resultados; `metadata.script_version="0.2.10"`; nota v0.2.10 presente en `notes` (nivel superior del informe).

Método de comparación para v0.2.6/CIERRE: baseline v0.2.9 regenerada desde git (`git show 2456195:…`, SHA-256 verificado `666e2cae…`) en directorio aislado; ambos harnesses ejecutados sobre v0.2.9 y sobre v0.2.10; `diff` de las líneas de clasificación: **idéntico en ambos**.

---

## 11. Reversibilidad del diff

`DIFF_v0_2_9_A_v0_2_10.patch` (72 líneas, 25+/7−) generado con `git diff 2456195 -- <instrumento>`. Verificación de reversibilidad ejecutada: aplicación inversa (`patch -R`) sobre el instrumento v0.2.10 →

```
sha256 = 666e2cae5e866dbcae962effb7efd6f50d7aeea84adfa7ae2a62556311e1ac4b
```

que es **exactamente** el SHA-256 del instrumento v0.2.9 (blob `6d1cdadc…`, 137.672 B). El diff es reversible bit a bit.

---

## 12. Limitaciones restantes

- El registro único aplica a los errores de cierre de la escritura del informe; cualquier **otro** componente que en el futuro llame a `_record_close_error` dos veces para el mismo evento seguiría duplicando (no hay deduplicación por (label, evento) en el acumulador; la unicidad es por diseño de registro, no por detección).
- En el escenario "cierre del temporal falla tras escritura completa", el informe **sí se publica** (semántica v0.2.3+ sin cambios, fuera del alcance de esta corrección): el contenido está completo y verificado antes del cierre; el error del cierre queda conservado y reportado como secundario en `close_err`.
- En el flujo interrumpido, los errores drenados en el manejador KI se muestran en la salida de diagnóstico y quedan en el acumulador persistente; no se insertan en un JSON (no se publica nada y no se intenta segunda publicación).
- `_close_err_id` sigue siendo un identificador por ejecución (clave de unicidad dentro de un informe, no global).
- **Este informe es provisional. La aprobación corresponde exclusivamente a Cris.**

---

## 13. Confirmaciones de alcance y ejecución

- **No hubo ejecución en Android/Termux**: toda la ejecución se realizó en el entorno de trabajo (Linux sandbox), con capa simulada `numpy`/`soundfile` y fallos inyectados exclusivamente por mocks (`os.close`, `os.write`, `os.link`, registro de fds). Ningún fallo espontáneo del OS, sin audio real, sin muestras del proyecto, sin ejecución de motores DSP.
- Sin root; sin merges; sin PR; sin publicación en `main`; sin eliminación de archivos ni limpiezas automáticas; sin reescritura del instrumento (5 hunks quirúrgicos).
- Técnicas permitidas utilizadas: inspección estática, pruebas unitarias aisladas con mocks, `py_compile`, `--help` (rc=0), pruebas de las rutas indicadas.
- Zonas congeladas intactas (§6); C4-A y C1 no reabiertos; C5 sin regresiones (§10).

---

## 14. Cadena de commits de la sesión (rama `arena/441a4bf8-sdv-sdi-sgm`)

```
50bae98  (base)      v0.2.4
fb2a96c  → b947c05   v0.2.5 (código + informe)
5e38e0f  → b91622b   v0.2.6 (código + informe)
3f850b6  → edc10b0   v0.2.7 (código + informe CIERRE)
ba77e6d  → 25e1302   v0.2.8 (código + informe)
2456195  → 0cc9dea   v0.2.9 (código + informe) ← BASE de v0.2.10
045af46              v0.2.10 (código: instrumento + harness C4-B v0.2.10 + DIFF) ← este informe
```

Todos los artefactos previos permanecen intactos (blobs verificados tras el commit: informes v0.2.1–v0.2.9, harnesses v0.2.3–v0.2.9, DIFFs v0.2.3–v0.2.9 con sus SHA-1 sin cambios).
