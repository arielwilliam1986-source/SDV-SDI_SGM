# INFORME DE CORRECCIÓN C4-B — v0.2.9

**Propagación completa de errores de cierre: conservación, atribución sin duplicación y reconstrucción sin pérdida**

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm`
- **Estado**: PROVISIONAL — pendiente de auditoría de Cris. **Ningún resultado de este informe constituye una aprobación.**

---

## 1. Identificación de la corrección

| Campo | Valor |
|---|---|
| Sub-fase | **C4-B** (autorizada; sub-objetivos C4-B1..C4-B5) |
| Versión resultante | **v0.2.9** (`SCRIPT_VERSION = "0.2.9"`) |
| Commit base (entrega v0.2.8) | `25e1302` — `25e1302e01c9a6492335186738d31c7ab2ec3c6ab` |
| Commit final (código v0.2.9) | `2456195` — `245619504a1c8c1bb5e6ad35d84c62fb5fd25bdc` |
| Blob SHA-1 del instrumento | `6d1cdadc64a0ebe4085dd79a94d6ccd4a7191b11` |
| SHA-256 del instrumento | `666e2cae5e866dbcae962effb7efd6f50d7aeea84adfa7ae2a62556311e1ac4b` |
| Tamaño exacto (bytes) | **137.672** |
| Número de líneas | **2.854** |
| Diferencia vs v0.2.8 | +106 / −10 líneas efectivas (diff de 252 líneas; v0.2.8: 131.709 B, 2.746 L) |

Archivo: `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`

Entregables acompañantes (mismo commit `2456195`):

| Archivo | Blob SHA-1 | SHA-256 | Tamaño | Líneas |
|---|---|---|---|---|
| `pruebas_unitarias_C4_B_v0_2_9.py` | `5bfc7aac09c0ab98d21b3ab07e9421eecfd2f9d8` | `7cfa985fff64d5084b8e70063677f65c36ee61deb5c7f50b4ad583000e61dad8` | 37.035 B | 891 |
| `DIFF_v0_2_8_A_v0_2_9.patch` | `a3ea06d068ab1fb2b0d277b7b08f807140d868e5` | `867996515f1268cbd6e6b4d43e674c2a24657d3ce11386b5ce92dd3cbda76bc7` | 13.770 B | 252 |

---

## 2. Diagnóstico previo (evidencia empírica sobre v0.2.8)

Tres defectos confirmados experimentalmente sobre v0.2.8 con mocks aislados (importación de solo lectura, sin modificar el instrumento):

- **Defecto A — drenaje destructivo**: `_finalize_report()` consumía `_drain_close_error_sink()` (vacía la cola). En la **segunda construcción del informe** (reconstrucción tras interrupción), la cola ya estaba vacía: los errores recogidos por la primera construcción **se perdían** para la reconstrucción.
- **Defecto B — duplicación prueba→entorno**: un error de cierre de una prueba quedaba en `close_errors` del resultado Y, si además era re-registrado (p. ej. el re-registro v0.2.3 en el éxito de creación de fixture, o el drenaje a nivel entorno), aparecía también en `environment_close_errors`: **la misma entrada dos veces** en el informe.
- **Defecto C — errores sin destino**: errores de cierre registrados **después** del drenaje de `_finalize_report` (p. ej. durante la escritura/cierre del tmp del informe) quedaban en la cola sin ningún destino visible ni persistente, y una aserción de publicación habría sido falsa si la cola se asumiera vacía.

---

## 3. Diseño implementado (v0.2.9)

Estructura de acumulación **persistente por ejecución** (permitida por la autorización C4-B; **no** cambia la propiedad ni el ciclo de vida de recursos de C4-A):

1. **`_close_error_ledger`** (lista global por ejecución): cada error de cierre se incorpora **en el momento del registro** (`_record_close_error`), antes de cualquier drenaje. Ningún drenaje puede provocar pérdida irreversible.
2. **Identificador único**: `_close_error_seq[0]` asigna `_close_err_id` incremental a cada entrada al registrarse. Es la clave de unicidad en el informe y la base de la atribución.
3. **`_attributed_close_error_ids`** (conjunto): identificadores ya incorporados a una estructura persistente concreta (resultado de prueba u operación). Evita duplicación prueba→entorno→informe.
4. **`_record_close_error(entry)`**: asigna ID (si es dict y no lo tiene) y añade a la cola pendiente **y** al ledger (incorporación en registro). Contrato previo intacto.
5. **`_drain_close_error_sink()`**: contrato v0.2.3+ intacto (extrae y vacía la cola); ya no puede provocar pérdida porque el ledger conserva todo.
6. **`_mark_close_errors_attributed(errors)`**: marca IDs como atribuidos. No reclasifica nada (C4-B5).
7. **`_close_errors_unattributed()`**: lectura **NO destructiva**: primero incorpora cualquier pendiente de la cola (no asume cola vacía — C4-B2) y retorna las entradas del ledger **sin atribución**. Llamadas sucesivas no pierden ni duplican.
8. **`_reset_close_error_accounting()`**: invocado en `main()` justo después de `run_id = make_run_id()`; reinicia cola, ledger, atribuciones y contador por ejecución (aislamiento entre ejecuciones).
9. **Atribución en `run_environment()`**: cada resultado que incorpora `close_errors` (NOT_EXECUTED por dependencia, KI en creación de fixture, fallo de creación de fixture, KI en prueba T11–T14, resultado ordinario de prueba, KI en T15/T16, resultado ordinario T15/T16) marca sus errores como atribuidos → no se repiten en `environment_close_errors`.
10. **Eliminado el re-registro duplicado v0.2.3** en el éxito de creación de fixture (los errores del closer ya están en el ledger por incorporación en registro; re-registrarlos duplicaba entradas).
11. **`_finalize_report()`** (clausura dentro de `main()`):
    - `env_close_errors_local = _close_errors_unattributed()` (no destructivo → la reconstrucción conserva lo ya recogido).
    - **Guardia de fecha**: `try: time.strftime(...) except Exception → "DESCONOCIDO (TipoExc: msg)"`. **`except Exception` NO captura `KeyboardInterrupt`** — la KI sigue propagando exactamente como antes (C5 congelado).
12. **Drenaje final post-escritura** en `main()`: los errores registrados durante escritura/cierre/publicación del informe se imprimen como `[cierre pendiente] {label}: {strerror}` — llegan a la salida de diagnóstico aunque el informe no se haya publicado (nunca se afirma publicación si no ocurrió).

---

## 4. Alcance exacto del cambio (hunks del diff)

| Hunk (línea v0.2.9) | Zona | Contenido |
|---|---|---|
| @83 | Cabecera | `SCRIPT_VERSION "0.2.8" → "0.2.9"` |
| @791–868 | Bloque nuevo tras `sha256_pread_v2` | globals `_close_error_ledger`, `_close_error_seq`, `_attributed_close_error_ids`; funciones `_reset_close_error_accounting`, `_record_close_error` (modificada), `_drain_close_error_sink` (docstring), `_mark_close_errors_attributed`, `_close_errors_unattributed` |
| @2006–2009 | `run_environment` | marca de atribución en resultado NOT_EXECUTED por dependencia |
| @2048–2049 | `run_environment` | comentario (KI en creación de fixture; el drenaje no pierde) |
| @2058 | `run_environment` | marca tras resultado KI de creación de fixture |
| @2078–2091 | `run_environment` | marca tras resultado de fallo de creación de fixture; **eliminado** re-registro duplicado en éxito (v0.2.3) |
| @2112–2126 | `run_environment` (T11–T14) | KI: drenaje a variable local + marca (semántica C5 intacta) |
| @2135 | `run_environment` (T11–T14) | marca tras resultado ordinario |
| @2159–2172 | `run_environment` (T15/T16) | KI: drenaje a variable + marca |
| @2179 | `run_environment` (T15/T16) | marca tras resultado ordinario |
| @2445–2448 | `main` | llamada a `_reset_close_error_accounting()` tras `run_id` |
| @2639–2652 | `main` → `_finalize_report` | lectura no destructiva + guardia `except Exception` en `strftime` |
| @2734–2740 | `main` | nota C4-B en `notes` del JSON |
| @2813–2820 | `main` | drenaje final post-escritura con impresión `[cierre pendiente]` |

**Funciones/clases modificadas**: `SCRIPT_VERSION` (constante), `_record_close_error()`, `_drain_close_error_sink()` (solo docstring), `run_environment()`, `main()` (incl. `_finalize_report()` interna). **Funciones nuevas**: las 4 listadas en el hunk @791. **Ningún otro símbolo fue modificado.**

---

## 5. Zonas congeladas — confirmación de integridad

Posiciones en v0.2.9 (verificadas por `grep -n`) frente a rangos de hunks: **ninguna intersección**.

| Zona congelada | Símbolos (línea en v0.2.9) | ¿Tocada por algún hunk? |
|---|---|---|
| **C1** (anclaje, publicación atómica) | `safe_open_dir_anchored` (246), `_ensure_parents_anchored` (315), `safe_makedirs_exclusive_anchored` (375), publicación `os.link`+`dir_fd`, gestión tmp | **No** |
| **C4-A** (propiedad/encapsulación) | `_close_fd_tracked` (885), `OwnedFdResource` (908), `_ResourceSnapshot` (990), `get_resource` (1128), `register_fd` (1146), `close_fd` (1171), `close_soundfile` (1296) | **No** |
| **C5** (interrupciones) | `interrupt_flag` (2570), flujo KI de `run_environment`/`main`, clasificación de interrumpidas, exit codes | **No** (los hunks KI solo cambian el destino del drenaje a variable local + marca; la semántica de C5 — ERROR nunca PASS, `interrupt_flag[0]=True`, NOT_EXECUTED posteriores, exit code, reconstrucción — es idéntica) |
| SHA | `sha256_pread_v2` (664), `pread` | **No** (solo contexto de cabecera de hunk) |
| Contrato SoundFile / subtipos WAV / señales sintéticas / T11–T16 funcionales / motores DSP | cuerpos de pruebas | **No** |
| `write_report_json_robust` (2246) | escritura robusta del informe | **No** |

El guardia de `_finalize_report` usa `except Exception` (no `BaseException`): `KeyboardInterrupt` **no** es capturado ahí y mantiene su propagación original a la gestión C5. Verificado por C4B_08 (KI+limpieza) y por la regresión del harness C5 v0.2.5.

---

## 6. Batería C4-B obligatoria — resultados reales de ejecución

Comando: `python3 pruebas_unitarias_C4_B_v0_2_9.py` (en `herramientas/diagnostico_audio/etapa2/`). Ejecución final:

```
TOTAL 15 | PASS 15 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0
```

**Casos NOT_EXECUTED: ninguno.** Todos los 15 casos obligatorios se ejecutaron y se clasificaron. Regla de clasificación del harness: NOT_EXECUTED solo ante ImportError/ModuleNotFoundError (dependencia no disponible); FAIL ante AssertionError; ERROR ante cualquier otra excepción.

| Caso | Errores simulados (primario / secundario) | Resultado | Evidencia observada |
|---|---|---|---|
| **C4B_01** cierre correcto sin secundarios | Ninguno (flujo íntegro limpio) | **PASS** | rc=0; 36 PASS; sin entradas de cierre en ningún nivel |
| **C4B_02** error de cierre de FD en resultado | Secundario: `CloseFailure` sobre `os.close` del FD del fixture en T11 (errno EIO) | **PASS** | T11=FAIL con `close_errors` (id único); `environment_close_errors` vacío; 1 ocurrencia en el JSON |
| **C4B_03** error de cierre de SoundFile en resultado | Secundario: cierre del `sf.SoundFile` de T11 falla (errno EIO) | **PASS** | error conservado en `close_errors` (label=`sfile`) y en el acumulador; tratado como error real, no advertencia |
| **C4B_04** primario + secundario | Primario: `LibsndfileError` en T11; Secundario: cierre de `dir_fd` del entorno falla | **PASS** | ambos presentes: primario en `detail`, secundario en `close_errors`; el primario NO reemplaza al secundario |
| **C4B_05** varios secundarios misma operación | 2 cierres fallidos consecutivos en la limpieza de T11 | **PASS** | ambos secundarios conservados en `close_errors` del resultado, IDs distintos |
| **C4B_06** retorno anticipado tras error de cierre | Error de cierre que dispara retorno anticipado en la prueba | **PASS** | retorno anticipado con primario + secundario conservados en el resultado |
| **C4B_07** excepción ordinaria + cierre en limpieza | Primario: excepción ordinaria inyectada; Secundario: cierre falla en la limpieza | **PASS** | clasificación correcta sin pérdida del secundario |
| **C4B_08** KeyboardInterrupt + cierre en limpieza | Primario: KI inyectada; Secundario: cierre falla en limpieza | **PASS** | clasificación ERROR/interrumpida C5; secundario conservado; rc según flujo C5 |
| **C4B_09** drenaje sin pérdida | 3 registros directos + drenajes | **PASS** | "3 registrados → drenados 3 → acumulador persistente 3 → no atribuidos 3" |
| **C4B_10** segundo drenaje sin duplicación | 2 drenajes + atribución de 2 | **PASS** | "2º drenaje vacío; atribución excluye 2; sin duplicados por id" |
| **C4B_11** reconstrucción del informe sin pérdida | Secundario de nivel entorno: cierre del FD del fixture **durante su creación** (1er cierre por-inode, errno EIO) + KI inyectada en `strftime` del resumen (2ª llamada) | **PASS** | rc=130; informe reconstruido con `interrupted=true`; error de entorno (`fixture_fd_pcm16`) conservado **1 vez** (unicidad por `_close_err_id`); 36 resultados conservados |
| **C4B_12** fallo equivalente a strftime sin pérdida | `OSError` en `strftime` de `finished_at` (no KI) | **PASS** | informe publicado con `finished_at="DESCONOCIDO (…)"`; errores de cierre intactos; KI no afectada (guardia `except Exception`) |
| **C4B_13** conservación en fallo de escritura/cierre del informe | Cierre del FD del tmp del informe falla (errno EIO) | **PASS** | rc=2; **sin publicación** (no se afirma publicada); provisional en disco; error `report_tmp_fd` en salida de diagnóstico y en el acumulador |
| **C4B_14** sin duplicación prueba→entorno→informe | Secundario: 2º cierre por-inode del fixture (= cierre de T11, la primera prueba que lo abre) falla | **PASS** | error en `close_errors` de T11; `environment_close_errors` vacío; exactamente 1 ocurrencia en el JSON por `_close_err_id` |
| **C4B_15** C4-A sigue funcionando | — (contrato C4-A: sin token no cierra; token desconocido no-op; snapshot inmutable; cierre por token exactamente 1 vez) | **PASS** | contrato de propiedad íntegro tras el cambio |

### Historial de depuración del harness (transparencia)

El instrumento **no fue modificado** durante la depuración (todas las iteraciones fueron del harness; el SHA-256 del instrumento se mantuvo `666e2cae…` desde el empalme). Tres correcciones, todas de mi harness:

1. **C4B_11 (inyección)**: registraba el error ANTES de `run_main`, pero `main()` reinicia legítimamente la contabilidad por ejecución (`_reset_close_error_accounting`) → la entrada se borraba. Corrección: inyectar **durante** el flujo (mock que falla el 1er cierre por-inode de un archivo regular >1000 B = cierre de creación del fixture → error de nivel entorno no atribuido a prueba).
2. **C4B_11/C4B_14 (verificación)**: las aserciones contaban el texto arbitrario del mensaje simulado en el JSON, pero el esquema de entrada del instrumento (vigente desde v0.2.1) normaliza `strerror` a `os.strerror(errno)` → el texto arbitrario nunca aparece. Corrección: unicidad por `_close_err_id` (clave diseñada para esto).
3. **Patrón de conteo**: `json.dumps` sin `indent` produce JSON compacto (el ID va seguido de `}`, no de `\n`) → conteo siempre 0. Corrección: regex con frontera `"_close_err_id":\s*{id}(?=[,}\s])`.

---

## 7. Evidencia de no pérdida y no duplicación

- **No pérdida en reconstrucción (Defecto A corregido)**: C4B_11 — con KI en el resumen, el informe reconstruido contiene el error de cierre de nivel entorno registrado durante el flujo (antes de la primera construcción), con exactamente 1 ocurrencia por ID.
- **No duplicación prueba→entorno→informe (Defecto B corregido)**: C4B_02 y C4B_14 — el error del resultado de T11 aparece 1 vez en el informe; `environment_close_errors` vacío; `raw.count` por regex de frontera sobre `_close_err_id` = 1. C4B_10 — atribución excluye los IDs ya incorporados; segundo drenaje vacío sin duplicar.
- **Sin errores sin destino (Defecto C corregido)**: C4B_13 — el error de cierre del tmp del informe (registrado tras la construcción del informe) aparece en la salida de diagnóstico (`report_tmp_fd`) y en el acumulador; rc=2; sin afirmación de publicación.
- **Cola nunca asumida vacía**: `_close_errors_unattributed()` incorpora cualquier pendiente antes de leer el ledger (C4B_09/C4B_10).
- **Sin reclasificaciones (C4-B5)**: las marcas de atribución solo añaden IDs a un conjunto; no convierten cierres correctos en errores, ni omisiones legítimas en fallos, ni advertencias de tokens obsoletos/desconocidos en errores reales (C4B_15; regresiones C4-A).

---

## 8. Regresiones ejecutadas (harness congelados, sin modificaciones)

| Harness (congelado) | Sobre v0.2.9 | Referencia sobre v0.2.8 | Δ |
|---|---|---|---|
| `pruebas_unitarias_v0_2_4.py` (C5) | **16/16 PASS** | 16/16 | ninguno |
| `pruebas_unitarias_v0_2_5.py` (C5 flujo real) | **10/11** — único FAIL: "el banner no anuncia v0.2.5" (pin de versión esperado) | 10/11 (mismo pin) | ninguno |
| `pruebas_unitarias_C4_A_v0_2_6.py` | 4 PASS / 7 FAIL / 2 ERROR | **idéntico caso a caso** (comparación directa ejecutando el mismo harness sobre copia v0.2.8: misma lista de NO PASS) | **ninguno** (artefactos documentados de semántica snapshot en harness congelados; el instrumento es correcto según el harness vigente v0.2.8: 15 PASS + 1 EXPECTED_LIMITATION + 0 FAIL/0 ERROR) |
| `pruebas_unitarias_C4_A_CIERRE.py` | 5 PASS / 9 FAIL / 1 EXPECTED_LIMITATION | **idéntico caso a caso** (misma comparación directa) | **ninguno** |
| `pruebas_unitarias_C4_A_v0_2_8.py` | **15 PASS + 1 EXPECTED_LIMITATION (`C4A8_16`, límite documentado) + 0 FAIL / 0 ERROR** | igual | ninguno |

**Suplemento de flujo real** (`main()` completo con capa simulada numpy/soundfile): rc=0; banner `v0.2.9`; 36 resultados, 36 PASS; `interrupted=false`; `environment_close_errors` vacío; `close_errors` vacío en los 36 resultados; `metadata.script_version="0.2.9"`.

Método de comparación para los harness v0.2.6/CIERRE: se ejecutó cada harness congelado dos veces (sobre copia v0.2.8 y sobre v0.2.9) y se comparó la clasificación caso a caso (`diff` de las líneas PASS/FAIL/ERROR/EXPECTED_LIMITATION): **idéntico en ambos** → v0.2.9 no introduce ninguna variación de comportamiento en esos contratos.

---

## 9. Reversibilidad del diff

`DIFF_v0_2_8_A_v0_2_9.patch` (252 líneas, 106+/10−) generado con `git diff ba77e6d -- <instrumento>`. Verificación de reversibilidad ejecutada: aplicación inversa (`patch -R`) sobre el instrumento v0.2.9 →

```
sha256 = 89efd402c3f42c4322d71e203c7e425b64ede12253fbe26517793501b308d148
```

que es **exactamente** el SHA-256 del instrumento v0.2.8 (`blob e9bb5ab2407bc6f0e360f6ca301cc292b7935f35`, 131.709 B). El diff es reversible bit a bit.

---

## 10. Confirmaciones de alcance

- **Sin Android/Termux**: toda la ejecución se realizó en el entorno de trabajo (Linux sandbox), con capa simulada `numpy`/`soundfile` (módulos falsos) y fallos **inyectados por mocks** (ningún fallo espontáneo del OS, sin audio real, sin DSP real, sin muestras del proyecto).
- **Sin root**; sin ejecución en dispositivo.
- **Sin `except Exception: pass` ni `except OSError: pass` nuevos**: el único `except Exception` añadido (guardia de `strftime`) **sustituye** el valor y conserva el error en el informe (`"DESCONOCIDO (…)"`); no silencia nada. Los cierres siguen sin tragar errores (C4-B4).
- **Retornos anticipados seguros (C4-B4)**: los retornos anticipados de `create_fixture()`, `run_environment()`, `close_fd()/close_soundfile()`, `_close_fd_tracked()`, directorios auxiliares y escritura del informe conservan los errores — verificado por C4B_06, C4B_07, C4B_08, C4B_13 y por los harnesses C4-A (rutas de cierre auditadas: `C4AC_13` runtime sin aperturas vivas fuera del propietario, idéntico a v0.2.8).
- **Publicación atómica y C1 intactos**: ningún hunk toca la publicación `os.link`+`dir_fd`, `safe_*_anchored`, ni la política de no sobreescritura.
- **C5 intacto**: la KI del guardia de fecha sigue propagando (`except Exception`); el flujo KI de pruebas solo cambió el destino del drenaje (variable local + marca), con idéntica clasificación, `interrupt_flag`, NOT_EXECUTED posteriores, omitida segunda envolvente y exit codes (regresión C5 16/16 y 10/11-pin).

---

## 11. Criterios de cierre (los 7)

1. **Errores de cierre conservados en todos los puntos de retorno** — ✅ C4B_02/03/05/06/07/08/09/13; ledger persistente con incorporación en registro.
2. **Errores primarios no reemplazados por secundarios** — ✅ C4B_02/04/07/08 (primario en `detail`/estado, secundario en `close_errors`, coexisten).
3. **Errores secundarios no descartados** — ✅ C4B_04/05/06/08 (múltiples secundarios conservados; drenajes no destructivos en la vía de reconstrucción).
4. **Retornos anticipados y limpiezas sin pérdida** — ✅ C4B_06/07/08/13; `create_fixture`, `run_environment`, closers, directorio auxiliar, tmp del informe.
5. **Reconstrucción del informe sin pérdida ni duplicación** — ✅ C4B_11 (sin pérdida, 1 ocurrencia por ID) y C4B_10/14 (sin duplicación prueba→entorno→informe).
6. **Las 15 pruebas obligatorias ejecutadas y clasificadas correctamente** — ✅ 15/15 PASS, 0 FAIL, 0 ERROR, 0 NOT_EXECUTED; fallos inyectados por mocks; clasificación real (ningún no-ejecutado contado como PASS).
7. **Zonas congeladas intactas (C1, C4-A, C5, sha256/pread, SoundFile, WAV, señales, T11–T16 funcionales, metadata, DSP)** — ✅ verificación por posiciones de símbolos vs hunks (sin intersección), por diff revisado línea a línea, y por regresiones con harnesses congelados idénticos caso a caso a v0.2.8.

---

## 12. Limitaciones y notas para la auditoría

- La corrección **no** pretende detectar fallos de cierre que el OS no reporta; solo conserva y propaga los que el OS reporta (mismo alcance que v0.2.3+, ahora sin pérdida ni duplicación).
- `_close_err_id` es un identificador **por ejecución** (se reinicia en `main()`); es clave de unicidad dentro de un informe, no un identificador global.
- El drenaje final post-escritura imprime a la salida de diagnóstico; los errores post-publicación no se insertan en el JSON ya escrito (evitaría reescritura no atómica; C1). Están disponibles en salida y acumulador.
- La atribución de errores de creación de fixture exitosa al nivel de entorno (no a una prueba) es el comportamiento de v0.2.3+, conservado; lo nuevo es que ya no se duplica.
- **Este informe es provisional. La aprobación corresponde exclusivamente a Cris.**

---

## 13. Cadena de commits de la sesión (rama `arena/441a4bf8-sdv-sdi-sgm`)

```
50bae98  (base)      v0.2.4
fb2a96c  → b947c05   v0.2.5 (código + informe)
5e38e0f  → b91622b   v0.2.6 (código + informe)
3f850b6  → edc10b0   v0.2.7 (código + informe CIERRE)
ba77e6d  → 25e1302   v0.2.8 (código + informe) ← BASE de C4-B
2456195              v0.2.9 (código: instrumento + harness C4-B + DIFF) ← este informe
```

Todos los artefactos previos permanecen intactos (blobs verificados tras el commit: informes v0.2.1–v0.2.8, harnesses v0.2.3–v0.2.8, DIFFs v0.2.3–v0.2.8 con sus SHA-1 sin cambios).
