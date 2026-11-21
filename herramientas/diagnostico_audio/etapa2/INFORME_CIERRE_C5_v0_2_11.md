# INFORME DE CIERRE C5 — v0.2.11

**Coherencia de interrupciones, finalización y construcción/publicación del informe**

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm`
- **Estado**: PROVISIONAL — pendiente de auditoría independiente de Cris y decisión de Will. **La entrega de Arena no constituye aprobación.**

---

## 1. Identificación de la corrección

| Campo | Valor |
|---|---|
| Sub-fase | **C5** — interrupciones, finalización y coherencia del informe (autorizada) |
| Versión base | **v0.2.10** (`SCRIPT_VERSION = "0.2.10"`) |
| Versión objetivo | **v0.2.11** (`SCRIPT_VERSION = "0.2.11"`) |
| Commit base (entrega v0.2.10, informe) | `2a134f2` — `2a134f2f2d374b205d981c458191b7848894e4b9` |
| Commit de código v0.2.10 | `045af46` — `045af464bc9bd28381d1e73455c7b061b54c9544` |
| Blob SHA-1 del instrumento v0.2.10 (base) | `27b844b2aa2d3be074e76cbc4420fe046913129d` |
| SHA-256 del instrumento v0.2.10 (base) | `54b7bf03af194043f48eb8f3cc27377840dffd1f674e453e99b5da2d22291253` |
| Commit final (código v0.2.11) | `392c485` — `392c4854beb4639b577461feaf678ce9bd115c68` |
| Blob SHA-1 del instrumento v0.2.11 | `5a5a052a9d0ea062afd25f690fcdb6d222bff240` |
| SHA-256 del instrumento v0.2.11 | `172a17fbd15620e82af25a07cda952cef9b034b61945e4c14cef9f5d094b4938` |
| Tamaño exacto (bytes) | **150.510** |
| Número de líneas | **3.101** |
| Diferencia vs v0.2.10 | +238 / −24 líneas efectivas (diff de 376 líneas; v0.2.10: 138.962 B, 2.872 L) |

Archivo: `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`

Entregables acompañantes (mismo commit `392c485`):

| Archivo | Blob SHA-1 | SHA-256 | Tamaño | Líneas |
|---|---|---|---|---|
| `pruebas_unitarias_C5_v0_2_11.py` | `ae7b94a95c692b68db650ceeae0998ffa6218c63` | `7c207bc4b56affcb07200c70ff9db0bde4fe19d733370d4553c72beffbf35357` | 50.925 B | 1.250 |
| `DIFF_v0_2_10_A_v0_2_11.patch` | `8056114c154efcc50c22345c25a16307db8e1982` | `c481a4e1c59eeeb63bb6d86ee02f51fb256aac8ed4db8a61ca883f6e5da3d02a` | 19.258 B | 376 |

---

## 2. Verificación del punto de partida (antes de modificar)

Verificado el 2026-11-21 antes de tocar el instrumento:

1. Rama `arena/441a4bf8-sdv-sdi-sgm` — HEAD local = remoto = **`2a134f2f2d374b205d981c458191b7848894e4b9`** (referencia exacta) ✓
2. Commit de código v0.2.10 `045af464…` presente en la historia ✓
3. Blob del instrumento en HEAD = **`27b844b2aa2d3be074e76cbc4420fe046913129d`** (referencia exacta) ✓
4. Contenido en disco = SHA-256 `54b7bf03…` (138.962 B, 2.872 L) = v0.2.10 exacto ✓
5. Árbol de trabajo limpio (único elemento: `__pycache__/` preexistente y sin tocar) ✓
6. `SCRIPT_VERSION = "0.2.10"` ✓

**Todas las condiciones se cumplieron; no fue necesaria detención ni recuperación.**

---

## 3. Diagnóstico previo (evidencia empírica sobre v0.2.10, sin modificar el instrumento)

Cuatro gaps confirmados con mocks aislados y flujo real `main()`:

### C5-A — KI durante el cierre de recursos (secuencia SoundFile → FD)
`create_fixture()` y T11/T14 cierran secuencialmente `close_soundfile(...)` y `close_fd(..., token=...)` en sus `finally` (y T15/T16 en sus rutas "inesperadas"), sin protección: una KI durante el cierre de SoundFile impide el intento de cierre del descriptor. Evidencia (KI inyectada en `close_soundfile` del `finally` de T11): intentos de `os.close` sobre el ino del fixture pcm16 = **1** (solo la creación); el cierre del FD de T11 **nunca se intentó** (0); T11=ERROR, rc=130.

### C5-B — Pruebas pendientes sin registro
Una KI **fuera** de los bloques `try/except KeyboardInterrupt` de `run_environment()` (p. ej. en la presentación del fixture creado: `fpath.stat()` en el `print`) escapa a `main()`; los resultados parciales se conservan pero **todas las pruebas planificadas restantes quedan sin registro** (omisión silenciosa). Evidencia (KI en `os.stat` del fixture pcm16): informe con **total=0** para `A_private` (0/18 registradas), rc=130, interrupted=true.

### C5-C — Publicación reconocida incorrectamente tras KI
Una KI puede llegar **después de que `os.link()` completó la publicación** (antes del `unlink` o del retorno): el programa anunciaba "no se publica" con el archivo final ya existente. Evidencia (enlace real + KI inyectada después): informe EN disco=True y salida con "no se publica"=True → **afirmación falsa confirmada**.

### C5-D — KI durante la reconstrucción del informe
Si la KI cae dentro de la `_finalize_report()` de recuperación (p. ej. en `strftime`), escapa del manejador hacia el nivel de módulo: **sin informe, sin registro explícito de la limitación**. Evidencia (KI en `strftime` llamadas 2 y 3 del formato de fecha): rc=130 (no nulo) pero sin informe publicado y sin mensaje de limitación.

---

## 4. Corrección implementada (v0.2.11)

**Tres funciones nuevas a nivel de módulo** (hunk @863; fuera de toda zona congelada):

1. **`_close_pair_conserving_interrupt(closer, sfile, sfile_label, fd, fd_label, fd_token)`** (C5-A): intenta cerrar el SoundFile (si aplica) y DESPUÉS el descriptor propietario (si aplica); absorbe una KI en cualquiera de los dos y retorna True para que el llamador la propague tras completar los intentos. No reintenta cierres de resultado incierto; no cierra duplicados (el estado C4-A —CLOSING/CLOSED/UNCERTAIN— lo impide por diseño); conserva los errores secundarios vía `_append_error`/`_record_close_error` (C4-B intacto). No modifica `OwnedFdResource`, `_ResourceSnapshot`, tokens ni estados.
2. **`_reconcile_pending_tests(results, env_names, detail)`** (C5-B): registra `NOT_EXECUTED` para toda prueba planificada (T11–T14 por fixture y T15/T16) sin registro, por entorno. **Idempotente**: calcula las claves existentes `(env, test, fixture)` y solo añade faltantes; una segunda llamada añade 0 y no altera resultados anteriores.
3. **`_publication_state_after_interrupt(report_path)`** (C5-C): verificación de **solo lectura** del estado real de publicación comparando identidad `(st_dev, st_ino)` del informe final con el provisional de esta ejecución (el enlace duro de C1 comparte inode; un archivo ajeno preexistente no). Retorna `PUBLICADO` / `NO_PUBLICADO` / `INDETERMINADO` con detalle. Sin segunda publicación, sin sobrescritura, sin limpieza.

**Sitios modificados:**

- `create_fixture()` finally, `test_t11_...` finally, `test_t14_...` finally, rutas inesperadas de T15/T16 → usan `_close_pair_conserving_interrupt` y propagan la KI absorbida tras la limpieza (C5-A).
- Camino normal de T11 y T14: si la KI cae en el cierre del SoundFile, `sfile=None` (resultado incierto, sin reintento en el `finally`) y re-lanza (C5-A, "no reintentar cierres inciertos").
- `main()` — fase de entornos: tras `_reconcile_interrupted`, llamada única e incondicional a `_reconcile_pending_tests` (cubre KI escapada, excepción fatal y cualquier omisión; en flujo normal añade 0) con aviso `[Reconciliacion C5: N ...]` (C5-B).
- `main()` — recuperación del informe: la `_finalize_report()` de recuperación queda envuelta; ante KI registra **explícitamente** `[LIMITACION] ...` y sale con `sys.exit(130)` (C5-D).
- `main()` — manejador KI de publicación: consulta `_publication_state_after_interrupt` y anuncia `[ESTADO DE PUBLICACION: PUBLICADO|NO_PUBLICADO|INDETERMINADO]` con detalle; conserva el drenaje C4-B (v0.2.10) y `sys.exit(130)` (C5-C).
- Nota C5 en `notes` del JSON + `SCRIPT_VERSION = "0.2.11"`.

**Funciones modificadas**: `create_fixture()`, `test_t11_soundfile_fd_closefd_false()`, `test_t14_pread_coexists_with_soundfile()`, `test_t15_libsndfile_error_raised()`, `test_t16_fd_survives_closefd_false_failure()`, `main()` (3 bloques C5 + nota), constante `SCRIPT_VERSION`. **Funciones nuevas**: las 3 listadas. **Ninguna función o clase congelada fue modificada.**

**Interpretación del alcance** (transparencia): la prohibición genérica de "modificar main" se interpretó, como en entregas previas, como limitación a los bloques que los hallazgos autorizados nombran explícitamente (manejador KI de publicación, recuperación del informe, guardia del segundo entorno/reconciliación); "fuentes originales" = muestras/audio del usuario.

---

## 5. Alcance exacto del cambio (hunks del diff)

| Hunk (línea v0.2.11) | Zona | Contenido |
|---|---|---|
| @83 | Cabecera | `SCRIPT_VERSION "0.2.10" → "0.2.11"` |
| @863–1008 | Entre `_close_errors_unattributed` (C4-B, intacta) y `_reconcile_interrupted` | 3 funciones nuevas C5 (151 líneas) |
| @1544 | `create_fixture` finally | helper C5-A + propagación KI |
| @1607 y @1645 | T11 (camino normal y finally) | sfile=None ante KI + helper C5-A |
| @1938 y @1992 | T14 (camino normal paso 9 y finally) | ídem |
| @2028 y @2088 | T15/T16 rutas inesperadas | helper C5-A + propagación |
| @2818 | `main` tras `_reconcile_interrupted` | reconciliación idempotente C5-B |
| @2949 | `main` recuperación del informe | envoltura C5-D con LIMITACION + exit 130 |
| @3010 | `main` manejador KI publicación | estado real PUBLICADO/NO_PUBLICADO/INDETERMINADO (C5-C) |
| @3033 | `main` → `notes` | nota C5 v0.2.11 |

Total: **238+/24−** (376 líneas). Todos los hunks dentro del alcance C5 autorizado.

---

## 6. Zonas congeladas — confirmación de integridad

| Zona congelada | Símbolos (línea en v0.2.11) | ¿Tocada? |
|---|---|---|
| **C1** | `safe_open_dir_anchored` (246), `_ensure_parents_anchored` (315), `safe_makedirs_exclusive_anchored` (375), `os.link` (2557), `write_report_json_robust` (2246, **sin hunks**) | **No** — el mecanismo de publicación es idéntico; la verificación C5-C es de solo lectura (stat), sin rename, sin comprobación previa de existencia, sin segunda publicación |
| **C4-A** | `_close_fd_tracked` (1030), `OwnedFdResource` (1053), `_ResourceSnapshot` (1135), `get_resource` (1273), `register_fd` (1291), `close_fd` (1316), `close_soundfile` (1441) | **No** — los cierres se solicitan por el canal del propietario; el helper solo ORQUESTA llamadas existentes |
| **C4-B** | `_reset_close_error_accounting` (805), `_record_close_error` (815), `_drain_close_error_sink` (829), `_mark_close_errors_attributed` (841), `_close_errors_unattributed` (851) y atribuciones en `run_environment` | **No** — sin cambios; el drenaje del manejador KI reutiliza `_drain_close_error_sink()` tal cual |
| `sha256_pread_v2` (664) y `os.pread` | — | **No** |
| SoundFile `closefd=False`, subtipos WAV, señales sintéticas | — | **No** |
| Criterios funcionales T11–T16 | cuerpos intactos salvo los `finally`/limpiezas autorizados por C5-A | No se altera ningún criterio funcional |
| Metadatos y alcance general | — | **No** (solo nota JSON y versión) |

---

## 7. Batería C5 obligatoria — resultados reales de ejecución

Comando: `python3 pruebas_unitarias_C5_v0_2_11.py`. Ejecución final:

```
TOTAL 18 | PASS 18 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0 | EXPECTED_LIMITATION 0
```

**Casos NOT_EXECUTED: ninguno. EXPECTED_LIMITATION: ninguno.** Todas las pruebas ejecutan el flujo real de `main()` con dependencias simuladas; cada caso verifica los contadores de disparo de sus mocks antes de evaluar el comportamiento (una inyección que no ocurre ⇒ FAIL, nunca PASS). Los casos de cierre verifican **explícitamente el número de intentos por identidad del archivo (st_ino)**.

| ID | Escenario (inyección) | Resultado | Evidencia observada |
|---|---|---|---|
| **C5-01** | KI durante creación de fixture (escritura simulada) | **PASS** | T11 pcm16=ERROR (nunca PASS); intentos de cierre del FD del fixture: **exactamente 1**; rc=130; interrupted=true |
| **C5-02** | KI durante cierre de SoundFile (cuerpo y finally de T11) | **PASS** | T11=ERROR; intentos de cierre del FD: **2** (creación + T11, el intento independiente ocurre); el cierre incierto del SoundFile **no se reintenta** (`sfile_finally` nunca invocado); rc=130 |
| **C5-03** | KI durante el cierre del FD (2º intento por ino) | **PASS** | T11=ERROR; intentos sobre el ino: **exactamente 2** (creación + único intento de T11): el cierre incierto (estado CLOSING) NO se reintenta; rc=130 |
| **C5-04** | KI durante prueba T11–T14 (pread de T12) | **PASS** | T12 pcm16=ERROR con detalle KI; rc=130; interrupted=true |
| **C5-05** | Pruebas posteriores a la interrupción | **PASS** | 36 registros únicos: 1 PASS conservado (T11 pcm16, **terminada antes de la KI**: su resultado no se altera) + 1 ERROR (T12) + 34 NOT_EXECUTED; rc=130 |
| **C5-06** | KI durante T15 (apertura de directorio) | **PASS** | T15=ERROR; T16=NOT_EXECUTED; rc=130 |
| **C5-07** | KI en preparación intermedia (`os.stat` del fixture creado, fuera de bloques protegidos) | **PASS** | **36 registros** (18 de A_private reconciliados NOT_EXECUTED con aviso `[Reconciliacion C5: 18 ...]`); sin duplicados; rc=130 |
| **C5-08** | KI en entorno privado con `--shared` configurado | **PASS** | `shared_run_dir=None` (el entorno B **no se inicia**); 18 NOT_EXECUTED en B_shared con el motivo; rc=130 |
| **C5-09** | KI en `time.strftime` de finalización (1ª construcción) | **PASS** | informe **reconstruido** y publicado con `interrupted=true`; 36 PASS conservados; rc=130 |
| **C5-10** | KI durante la presentación del resumen (`print '=== RESUMEN ==='`) | **PASS** | informe reconstruido con resultados anteriores íntegros (36 PASS); rc=130 |
| **C5-11** | KI antes de ejecutar `os.link` | **PASS** | `[ESTADO DE PUBLICACION: NO_PUBLICADO]` anunciado; provisional conservado; sin publicación; rc=130 |
| **C5-12** | `os.link` REAL completa y luego KI | **PASS** | `[ESTADO DE PUBLICACION: PUBLICADO]` — la publicación se **reconoce** por identidad (st_dev, st_ino) compartida con el provisional; el informe EXISTE en disco; sin afirmación falsa; provisional conservado; rc=130 |
| **C5-13** | KI tras publicación durante la eliminación del provisional: (a) en `os.unlink`; (b) en el cierre del padre tras unlink completado | **PASS** | (a) PUBLICADO + provisional conservado; (b) PUBLICADO con provisional ausente (única ruta que lo elimina es la post-enlace); sin segunda publicación; rc=130 en ambos |
| **C5-14** | KI durante escritura JSON | **PASS** | rc=130; NO_PUBLICADO; provisional parcial conservado |
| **C5-15** | KI + error de cierre del temporal | **PASS** | `[cierre pendiente] report_tmp_fd` **exactamente 1 vez** en la salida; **1 entrada** en el acumulador (sin duplicación); NO_PUBLICADO; rc=130 |
| **C5-16** | Reconstrucción repetida del informe | **PASS** | 2 construcciones en una ejecución (1ª interrumpida por KI en finished_at + reconstrucción completa): 36 PASS únicos, `environment_close_errors` vacío, acumulador vacío; **idempotencia verificada directamente**: `_reconcile_pending_tests` 1ª llamada añade 17, 2ª añade **0** y no altera resultados anteriores; rc=130 |
| **C5-17** | Excepción fatal durante la fase de entornos (`RuntimeError`) | **PASS** | `fatal_exception` reflejado en el informe; 36 registros (pendientes reconciliados NOT_EXECUTED); `[ERROR FATAL]` en salida; **rc=2** (no nulo) |
| **C5-18** | Ejecución normal sin interrupciones | **PASS** | rc=0; banner v0.2.11; 36 PASS; `environment_close_errors` vacío; **sin reconciliación** (0 añadidos); sin `[ESTADO DE PUBLICACION]`; nota v0.2.11 en JSON |

### Historial de depuración del harness (transparencia)

El instrumento **no fue modificado** durante la depuración del harness (SHA-256 constante `172a17fb…` desde el empalme; los ajustes posteriores del instrumento se documentan en §4/§10 y fueron re-verificados). Tres correcciones, todas del harness:
1. `StrftimeKI` contaba **todas** las llamadas a `strftime` (incluida la de `make_run_id`, con formato distinto) desplazando el índice → corregido para contar solo el formato de fecha del informe (1=started_at; 2=finished_at de la 1ª construcción; 3+=reconstrucciones).
2. C5-05: error aritmético — T11 pcm16 terminó **antes** de la KI y su PASS se conserva legítimamente (1 PASS + 1 ERROR + 34 NOT_EXECUTED = 36).
3. C5-16: una segunda reconstrucción **completa** dentro de una misma ejecución no existe por diseño (una sola ruta de recuperación, v0.2.5 congelado; KI durante la reconstrucción ⇒ LIMITACION + 130, nunca una tercera construcción). El caso verifica las 2 construcciones reales (interrumpida + recuperación) más la idempotencia directa de `_reconcile_pending_tests` (mandato explícito C5-B).

---

## 8. Evidencia de conservación y coherencia

- **La interrupción no impide la limpieza**: C5-02 (2 intentos de cierre), C5-01 (1 intento), C5-03 (sin reintento del incierto, exactamente 2). Conteo explícito por `st_ino`.
- **Resultados conservados**: C5-05 (PASS de prueba terminada intacto), C5-09/C5-10/C5-16 (36 resultados íntegros tras reconstrucción).
- **Clasificación correcta**: interrumpido ⇒ ERROR nunca PASS (C5-01/02/03/04/06); pendientes ⇒ NOT_EXECUTED (C5-05/07/08); nunca se inventan resultados.
- **Reconciliación idempotente**: C5-16 (17 + 0; sin alteración de registros previos); C5-18 (0 añadidos en flujo normal); C5-07 (36/36 tras KI escapada).
- **Estado de publicación veraz**: C5-11 (NO_PUBLICADO real), C5-12/C5-13 (PUBLICADO reconocido — antes se anunciaba falsamente "no se publica"), C5-14 (NO_PUBLICADO), INDETERMINADO definido para estados no verificables. La frase "no se publica" aparece **solo** en la rama NO_PUBLICADO (verdad; el defecto era afirmarla cuando SÍ se publicó).
- **Errores C4-B conservados**: C5-15 (1 entrada + 1 línea en salida); acumulador y atribución intactos.

---

## 9. Regresiones ejecutadas (harness congelados, sin modificaciones)

| Harness (congelado) | Sobre v0.2.11 | Referencia v0.2.10 | Δ |
|---|---|---|---|
| `pruebas_unitarias_C5_v0_2_11.py` (nuevo) | **18/18 PASS** | — | — |
| `pruebas_unitarias_C4_B_v0_2_9.py` | **15/15 PASS** | 15/15 | ninguno |
| `pruebas_unitarias_C4_B_v0_2_10.py` | **10/10 PASS** | 10/10 | ninguno |
| `pruebas_unitarias_v0_2_4.py` (C5) | **16/16 PASS** | 16/16 | ninguno |
| `pruebas_unitarias_v0_2_5.py` (C5 flujo real) | **10/11** — único FAIL: pin de banner ("no anuncia v0.2.5") | 10/11 (mismo pin) | ninguno |
| `pruebas_unitarias_C4_A_v0_2_8.py` | **15 PASS + 1 EXPECTED_LIMITATION (`C4A8_16`) + 0F/0E** | igual | ninguno |
| `pruebas_unitarias_C4_A_v0_2_6.py` | 4 PASS / 7 FAIL / 2 ERROR | **idéntico caso a caso** (comparación directa sobre copia v0.2.10 regenerada desde git `045af46`, SHA-256 verificado) | un detalle informativo cambia (ver abajo); clasificación idéntica |
| `pruebas_unitarias_C4_A_CIERRE.py` | 5 PASS / 9 FAIL / 1 EXPECTED_LIMITATION | **idéntico caso a caso** | ninguno |

**Delta informativo explicado**: `C4A_11_estatico_contrato_en_t11_a_t16` (PASS en ambas versiones) informa "cierres con token" 24 → **20**. Causa: los 5 cierres por token inline convertidos al helper C5-A (create_fixture finally, T11 finally, T14 finally, rutas inesperadas T15 y T16) se cuentan ahora en el helper (1 llamada única `closer.close_fd(fd, fd_label, token=fd_token)`) en vez de inline: −5 +1 = −4. El umbral del harness es `>= 20` (cumplido) y la auditoría de "cierre sin token" sigue en 0: **todos los cierres siguen asociados a token por el canal del propietario**.

**Suplemento de flujo real** (`main()` completo, capa simulada, con `--shared`): rc=0; banner v0.2.11; 36 resultados, 36 PASS; `interrupted=false`; `environment_close_errors` vacío; `close_errors` vacío en los 36; `metadata.script_version="0.2.11"`; nota v0.2.11 en `notes`.

**Nota histórica**: durante la iteración, el harness v0.2.5 llegó a mostrar un segundo FAIL (`ki_publicacion`: exige `'no se publica' in out`) porque el mensaje nuevo no incluía esa frase; se resolvió incluyendo la frase **solo en los detalles NO_PUBLICADO** (veraz en esa rama; la rama PUBLICADO jamás la contiene), con lo que el harness congelado vuelve a 10/11 (solo pin de banner). No se modificó el harness congelado.

---

## 10. Reversibilidad del diff

`DIFF_v0_2_10_A_v0_2_11.patch` (376 líneas, 238+/24−) generado con `git diff 045af46 -- <instrumento>`. Verificación ejecutada: aplicación inversa (`patch -R`) sobre el instrumento v0.2.11 →

```
sha256 = 54b7bf03af194043f48eb8f3cc27377840dffd1f674e453e99b5da2d22291253
```

que es **exactamente** el SHA-256 del instrumento v0.2.10 (blob `27b844b2…`, 138.962 B). El diff es reversible bit a bit.

---

## 11. Limitaciones pendientes

- **Identidad por (st_dev, st_ino)**: la verificación C5-C distingue nuestra publicación de un archivo ajeno por compartir inode con el provisional (enlace duro). Si el provisional ya fue eliminado (unlink exitoso), el estado PUBLICADO se infiere de la invariante del flujo (solo la eliminación post-enlace lo quita) y de la unicidad del `run_id` (marca de tiempo UTC + PID + 8 hex aleatorios); una colisión de nombre con un archivo ajeno en ese escenario se considera practic imposible pero no verificable por identidad — se documenta, no se oculta.
- **Cierre de SoundFile incierto**: tras una KI durante `sfile.close()`, el estado del SoundFile no queda registrado en ninguna estructura de estado (el libro de `_closed_sfiles` solo marca cierres completados); el diseño NO reintenta y la KI se propaga — el recurso subyacente se resuelve al terminar el proceso. Limitación del contrato actual, no modificada (C4-A congelado).
- **Una sola ruta de reconstrucción por ejecución** (v0.2.5 congelado): máximo 2 construcciones de informe por ejecución; KI durante la reconstrucción ⇒ limitación explícita + 130 (sin tercera construcción). Los resultados quedan en memoria pero sin informe en ese caso extremo.
- **Errores post-publicación**: los errores de cierre posteriores al informe publicado se muestran en la salida de diagnóstico (`[cierre pendiente]`) y en el acumulador; no se insertan en el JSON ya publicado (evitaría reescritura no atómica; C1).
- **Este informe es provisional. La aprobación corresponde exclusivamente a Cris (auditoría independiente) y la decisión a Will.**

---

## 12. Confirmaciones de alcance y ejecución

- **No se ejecutó en Android/Termux ni con audio real**: toda la ejecución se realizó en el entorno de trabajo (Linux sandbox) con capa simulada `numpy`/`soundfile` y KI/fallos **inyectados exclusivamente por mocks** (`os.close`, `os.open`, `os.write`, `os.stat`, `os.pread`, `os.link`, `os.unlink`, `time.strftime`, `builtins.print`, cierre simulado de SoundFile). Ningún fallo espontáneo del OS; sin muestras del proyecto; sin ejecución de motores DSP; sin root.
- Sin merges, sin PR, sin publicación en otra rama; sin borrado de archivos ni limpieza automática; sin reescritura del instrumento (13+2 reemplazos quirúrgicos por empalme con verificación de conteo exacto).
- Técnicas permitidas: inspección estática, pruebas unitarias aisladas con mocks, inyección controlada de KI, `py_compile` (OK), `--help` (rc=0), pruebas simuladas del flujo completo de `main()`.
- **Ninguna prueba fue declarada como ejecutada sin haberse ejecutado**: los 18 casos C5 y todas las regresiones listadas corresponden a ejecuciones reales con salida capturada.
- C1, C4-A y C4-B sin modificación alguna (§6); C5-A/C5-B/C5-C/C5-D implementados dentro del alcance autorizado; sin defectos conocidos pendientes en el alcance de esta subfase.

---

## 13. Cadena de commits de la sesión (rama `arena/441a4bf8-sdv-sdi-sgm`)

```
50bae98  (base)      v0.2.4
fb2a96c  → b947c05   v0.2.5 (código + informe)
5e38e0f  → b91622b   v0.2.6 (código + informe)
3f850b6  → edc10b0   v0.2.7 (código + informe CIERRE)
ba77e6d  → 25e1302   v0.2.8 (código + informe)
2456195  → 0cc9dea   v0.2.9 (código + informe)
045af46  → 2a134f2   v0.2.10 (código + informe) ← BASE de C5
392c485              v0.2.11 (código: instrumento + harness C5 + DIFF) ← este informe
```

Todos los artefactos previos permanecen intactos (blobs verificados tras el commit: informes y harnesses v0.2.1–v0.2.10, DIFFs v0.2.3–v0.2.10 con sus SHA-1 sin cambios).
