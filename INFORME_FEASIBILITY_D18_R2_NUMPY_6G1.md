# FEASIBILITY-D18-R2 + R1 + R2 + R3 + R4 + R5 — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP (registro del fallo de cierre final de dirfd)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena (sesión `arena/9a32cda8-sdv-sdi-sgm`).
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Alcance de ESTA entrega (autorización D18-R2-R5):** **registro del fallo de cierre final de dirfd** (R5-A cierre final registrado, R5-B prueba controlada, R5-C regresión). No se amplía el alcance a referencias retenidas ni a nuevas estrategias de liberación.
- **Relación con D-18 / R1 / R2 / R3 / R4:** D-18 permanece **FAIL**. El hallazgo **C5** (SIGSEGV al cerrar `arr._mmap` con el array vivo, reproducible 3/3) es de FEASIBILITY-D18-R1 y se **conserva como histórico e independiente**; R2/R1/R2-R2/R2-R3/R2-R4/R2-R5 **no lo re-ejecutan ni lo ocultan**.
- **Veredicto global R2+R1+R2+R3+R4+R5:** **UNKNOWN** (precedencia FAIL > UNKNOWN > PASS). 21 PASS · 0 FAIL · 17 UNKNOWN (38 subpruebas). El camino seguro **funciona** cuando se liberan TODAS las referencias + `gc.collect()`, pero **no puede garantizarse incondicionalmente** (una referencia retenida, o un inventario de `/proc` incompleto, impiden acreditar la liberación → UNKNOWN/fallo cerrado).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R2-R5):** `e412d561b50cf358d21609d76646fc4a361cd0fb` (FEASIBILITY-D18-R2-R4).
- Verificado ANTES de trabajar: HEAD = `e412d56...` (local = padre exigido), rama `arena/9a32cda8-sdv-sdi-sgm`, árbol limpio (`git status --porcelain` vacío). **TODO CONFORME**.
- **Nuevo commit:** hijo directo de `e412d56...`; **exactamente 2 archivos modificados** (los dos autorizados). SHA completo en el mensaje de commit (verificable vía `git`/`gh api`).

## 2. Archivos modificados (exactamente los 2 autorizados, ambos existentes)

| Archivo | Rol | Cambio |
|---|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` | Arnés R2+R1+R2+R3+R4+R5 (38 subpruebas: 19 R2 + 13 R2-C controladas + 6 R1 controladas) | R5-A/B/C correcciones; sin nuevos archivos |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` | Este informe | Actualiza método, recuentos, evidencias de cierre final, procedimientos y limitaciones (R5-C) |

Evidencia JSON cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera; el arnés la regenera). SHA-256 de los dos archivos en el mensaje de commit y en la entrega a Cris (no autocalculados dentro del propio informe para evitar autorreferencia).

## 3. Entorno y versiones exactas

| Componente | Valor |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (venv efímero `/tmp/feas_d18_venv` con NumPy 1.26.4) |
| numpy | `1.26.4` |
| glibc | 2.36 |

Veredictos válidos para ESTE entorno y condiciones; **sin extrapolación** a Android/Termux ni a otras versiones de Python/NumPy. Lo aquí observado es **comportamiento en CPython 3.11.2 / NumPy 1.26.4**, no una garantía documentada de las bibliotecas.

## 4. Correcciones metodológicas

### R1 / R2 / R3 / R4 (fases previas, conservadas íntegramente)
- **R1-A/B/C/D** — lectura de `/proc/self/maps` con estados complete/incomplete/unreadable; errores de `stat` en inventario de fds registrados; propagación de UNKNOWN; C5 como FAIL histórico; sin `_mmap.close()` forzado ni garantías universales de `gc.collect()`.
- **R2-A/B** — `fds_with_identity()` captura errores de `os.listdir(fd_dir)` y de `stat`; inventario INCOMPLETO con error+contexto; no propaga; clasificación expresa (errno, tipo, nombre, contexto).
- **R3-A..F** — R2-C7 con dos propiedades independientes; R2-C2/C3 con veredicto dependiente de la clasificación; R2-C5 con exigencia de evidencia real de ERROR_PROCFS; clasificación **conservadora de ENOENT** (fdinfo ausente → UNKNOWN_CAUSE); R2-C10 con propagación verificada sobre escenarios reales A/B/C.
- **R4-A/B/C** — cierre del dirfd ante fallo de `os.listdir(dirfd)` (sin fugas, nota de cierre registrada); inspección **relativa** al descriptor (`os.stat(name, dir_fd=dirfd)`) sin resolver de nuevo la ruta nominal; modo `path` documentado como no anclado.

### R5-A — Cierre final registrado
Corrección del `finally` de `fds_with_identity()`:
- **No se descartan silenciosamente** los errores de `os.close(dirfd)`.
- Si el cierre **falla**, se registra: **fase** (`"cierre"`), **descriptor**, **tipo de excepción**, **errno** y **contexto**.
- El inventario queda **`complete=False`**: ningún escenario dependiente puede convertirlo en PASS — **propagación UNKNOWN**, salvo que exista un **FAIL independiente demostrado**.
- **No se afirma** que el descriptor quedó cerrado cuando el cierre falló (la nota del registro lo explicita).
- **No se realizan reintentos ciegos** de `close()` que puedan cerrar un descriptor distinto por reutilización del número: se registra y se termina.

### R5-B — Prueba controlada R2-C13
Fuerza un error de **cierre** en el `finally` **después** de una enumeración e inspección correctas (`os.close` forzado a `OSError(EBADF)`), y verifica **independientemente**:
1. La inspección se ejecutó en **modo `dirfd`** (spy de `os.stat`: `dir_fd` establecido).
2. El **cierre fue intentado** (spy de `os.close`: llamada registrada para el dirfd).
3. El **error quedó registrado con su contexto** (`phase="cierre"`, `name`/`entry` = descriptor, `exception_type`, `errno=9`).
4. El **inventario resultó incompleto** (`complete=False`).
5. El **controlador dependiente asignó UNKNOWN** (nunca PASS).
6. **No se declara PASS ni cierre efectivo** cuando el descriptor no pudo acreditarse como cerrado (la nota no afirma el cierre).
- **Diferenciación con R2-C11**: en R2-C11 el fallo es de `listdir(dirfd)` (`phase=enumeracion`, sin inspección ejecutada); en R2-C13 la enumeración e inspección **succeen** (`matched=[5]`) y el fallo es de fase `"cierre"`. **Resultado: PASS** (las seis propiedades y la diferenciación verificadas).

### R5-C — Regresión
- Se reejecutan **R2-C11, R2-C12, R3-A..E** y el **conjunto completo D18-R2** (38 subpruebas).
- Se mantienen: precedencia **FAIL > UNKNOWN > PASS**; **C5 como FAIL histórico** (sin repetir el cierre de `_mmap` con referencias vivas); **ENOENT + fdinfo ausente → UNKNOWN_CAUSE**; **modo `dirfd` anclado** y **modo `path` no anclado**; ausencia de garantías universales de `gc.collect()`.
- Se comprobó que los errores de enumeración **no producen fugas** (R2-C11), que las inspecciones en modo `dirfd` **no resuelven la ruta nominal** (R2-C12) y que el **cierre final registra su fallo** sin reintentos (R2-C13).

## 5. Resultados individuales (38 subpruebas)

### R2-A — Liberación de referencias

| ID | Título | maps vivo→muerto | Veredicto |
|---|---|---|---|
| A1 | Raíz sin vistas | 1→0 (maps); fd vivo→[] | **UNKNOWN** (inventario fd incompleto) |
| A2 | Raíz + slice | 1→1→0 | PASS (solo maps, complete) |
| A3 | Vistas encadenadas | 1→1→1→0 | PASS (solo maps, complete) |
| A4 | Contenedores | 1→1→0 | PASS (solo maps, complete) |
| A5 | Referencia exportada | 1→1→0 | PASS (solo maps, complete) |
| A6 | Liberación progresiva | 1→1→1→0 | PASS (solo maps, complete) |

**Conclusión A (maps):** la liberación por referencias + `gc.collect()` desmapea correctamente y cierra el fd duplicado del mmap; el mapeo desaparece exactamente cuando la **última** referencia viva se libera.

### R2-B — Cierre seguro (sin `_mmap.close()`)

| ID | Título | maps | Veredicto |
|---|---|---|---|
| B1 | Secuencia segura, raíz | 1→0 | **UNKNOWN** (fd inventario incompleto) |
| B2 | Con vistas | 1→0 | **UNKNOWN** (fd inventario incompleto) |
| B3 | Recolección controlada | 1→0 | PASS (solo maps) |
| B4 | Todas las entradas por (dev,ino) | 1→0 | PASS (solo maps) |
| B5 | Fds residuales y propiedad (ruta) | fd vivo→[] | **UNKNOWN** (fd inventario incompleto) |
| B6 | Referencia externa viva | maps persiste | **UNKNOWN** (referencia retenida, por diseño) |

**Conclusión B:** la secuencia segura libera el mapeo y cierra el fd duplicado sin SIGSEGV (evita C5). Pero si el inventario de fds es incompleto —por una referencia externa retenida (B6) o por una entrada de `/proc/self/fd` no estadizable en este entorno (B1/B2/B5)— la liberación **no puede acreditse** → UNKNOWN/fallo cerrado.

### R2-C — Alternativas A/B/C (cierre seguro, diferenciando fds)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| C-A | fd motor + magic-link | fd motor abierto; dup cerrado | **UNKNOWN** (fd inventario incompleto) |
| C-B | NumPy por ruta | solo dup de NumPy | **UNKNOWN** (fd inventario incompleto) |
| C-C | fileobj entregado | fd fileobj abierto; dup cerrado | **UNKNOWN** (fd inventario incompleto) |

**Conclusión C (observado, no inferido):** en A/B/C el **único** recurso que cierra el camino seguro es el fd duplicado interno del objeto `mmap`, vía su finalizador. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor; B no tiene fd_mm.

### R2-D — Fallos y excepciones

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| D1 | Liberación incompleta (vista retenida) | maps persiste | **UNKNOWN** |
| D2 | Referencia retenida impide acreditar | maps persiste | **UNKNOWN** |
| D3 | Flush no bloquea la liberación | flush persiste; sin flush→maps=0 | PASS |
| D4 | Cierre seguro sin errores | `del arr; gc` → sin excepción, maps=0 | PASS |

**Conclusión D:** las variantes de fallo no usan `_mmap.close()` forzado; el mapeo permanece vivo y la liberación termina en UNKNOWN/fallo cerrado. El camino seguro (finalizador) no lanza excepción.

### R2-C controladas (obligatorias)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R2-C1 | Inventario COMPLETO de fds | complete=True; matched=[3]; errors=[]; enum por dirfd | PASS |
| R2-C2 | Entrada que desaparece durante el recorrido | complete=False; error `DESCRIPTOR_DESAPARECIDO`, errno=2, FileNotFoundError, entrada '5' (R3-B) | **UNKNOWN** |
| R2-C3 | Entrada inaccesible (permisos) | complete=False; error `DESCRIPTOR_INACCESIBLE`, errno=13, PermissionError, entrada '9' (R3-B) | **UNKNOWN** |
| R2-C4 | Error de enumeración del directorio | no propaga; complete=False; phase=enumeración; /proc → `ERROR_PROCFS`, no-procfs → `UNKNOWN_CAUSE` | PASS |
| R2-C5 | Error de procfs durante la inspección (R3-C) | mecánica correcta; **sin evidencia real** de ERROR_PROCFS con errno/contexto compatibles | **UNKNOWN** |
| R2-C6 | Propagación de UNKNOWN a escenarios dependientes | inventario forzado incompleto → A/B/C = UNKNOWN | PASS |
| R2-C7 | Sin FAIL artificial (R3-A) | P1 no propaga = OK; P2 controlador → UNKNOWN = OK | PASS |
| R2-C8 | Origen del descriptor fantasma fd (diagnóstico) | evidencia recopilada; clasificación **UNKNOWN_CAUSE** (R3-D); causa root: UNKNOWN (§7) | **UNKNOWN** |
| R2-C9 | Descriptor de directorio mantenido abierto | dirfd estable/identificable; tras borrado externo, ruta falla y el dirfd no; modo registrado | PASS |
| R2-C10 | Propagación en escenarios REALES A/B/C (R3-E) | incompleto → UNKNOWN en A1/B1/B5/C-B; completo → A1/B1/C-B = PASS | PASS |
| R2-C11 | Cierre de dirfd ante error de enumeración (R4-A) | no hay fuga (descriptor cerrado, EBADF al fstat); inventario INCOMPLETO; nota de cierre fallido registrada | PASS |
| R2-C12 | Inspección relativa al dirfd vs recorrido por ruta (R4-B) | modo dirfd: inspecciones relativas (dir_fd, nombre sin resolver), descriptor cerrado; modo path: no anclado | PASS |
| R2-C13 | Registro del fallo de cierre final de dirfd (R5-B) | inspección en modo dirfd; cierre intentado; error fase "cierre" registrado (errno=9); inventario INCOMPLETO; controlador → UNKNOWN | PASS |

**R2-C1..R2-C13 demuestran** el mecanismo R2-A/R2-B/R3/R4/R5: enumeración e inspección capturadas; ciclo de vida completo del descriptor (cierre ante error de enumeración, inspección anclada, registro del fallo de cierre final); inventarios completos permiten acreditar; cualquier incompletitud fuerza UNKNOWN; nunca PASS ni FAIL artificial; clasificación conservadora sin inventar causas.

### R1 controladas (conservadas)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R1-A1 | Lectura COMPLETA con coincidencia | status=complete; recuento=1 | PASS |
| R1-A2 | Lectura COMPLETA sin coincidencia | status=complete; recuento=0 | PASS |
| R1-A3 | Coincidencia + líneas no interpretables | status=incomplete | **UNKNOWN** |
| R1-A4 | `/proc/self/maps` no disponible/ilegible | status=unreadable | **UNKNOWN** |
| R1-B1 | Inventario COMPLETO de /proc/self/fd | complete=True; matched=[3]; errors=[] | PASS |
| R1-B2 | Inventario INCOMPLETO (/proc/self/fd con error) | complete=False; error registrado | **UNKNOWN** |

## 6. Conteos y veredicto global

```
Subpruebas: 38 (19 R2 + 13 R2-C controladas + 6 R1 controladas)
Conteos:    PASS=21 FAIL=0 UNKNOWN=17
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
```

Desglose de PASS (21): A2,A3,A4,A5,A6 · B3,B4 · D3,D4 · R2-C1,R2-C4,R2-C6,R2-C7,R2-C9,R2-C10,R2-C11,R2-C12,R2-C13 · R1-A1,R1-A2 · R1-B1.
Desglose de UNKNOWN (17): A1,B1,B2,B5,B6 · C-A,C-B,C-C · D1,D2 · R2-C2,R2-C3,R2-C5,R2-C8 · R1-A3,R1-A4 · R1-B2.

**Evolución respecto a R2+R1+R2+R3+R4 (20 PASS · 17 UNKNOWN):** los 37 escenarios previos conservan **exactamente** sus veredictos (regresión R2-C11/C12 y R3-A..E intacta). R5 añade **R2-C13** (PASS): verificación del registro del fallo de cierre final. Ningún resultado anterior fue alterado.

## 7. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4):** soltar el array raíz, todas las vistas/slices, contenedores y referencias exportadas, y luego `gc.collect()`, finaliza el `mmap` (su `__del__`/`__dealloc__` cierra el fd duplicado y desmapea). Evita el SIGSEGV de C5. **Observación de comportamiento**, coherente con la semántica de que el `ndarray` mantiene al `mmap` como `base`; **NO es una garantía documentada de NumPy**.
2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** en A/B/C el único fd que cierra el camino seguro es el dup interno del objeto `mmap`. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor. B no tiene fd_mm.
3. **Condición de seguridad: liberar TODAS las referencias (hipótesis de diseño, no dem. incondicional):** cualquier referencia olvidada mantiene el mapeo vivo → UNKNOWN/fallo cerrado. R5 **no autoriza por sí mismo EXIT_OK** ni un «cierre efectivo garantizado» en producción.
4. **Hallazgo del descriptor fantasma de `/proc/self/fd` (hechos observados, R2-C8):** en este entorno, `/proc/self/fd` lista **exactamente una entrada** que `stat`/`readlink` no pueden resolver (`ENOENT`) y que **carece de `fdinfo`**. Hechos observados: no es un descriptor real abierto (fdinfo ausente); no es el descriptor transitorio de la propia enumeración (ese es estable, identificable y real); su número es **variable** entre llamadas (observado `3`, `5`, `6`); cuando el número lo ocupa un descriptor real abierto, `stat` **succee**. **Clasificación conservadora (R3-D):** ENOENT + fdinfo ausente → **UNKNOWN_CAUSE**; **causa root: UNKNOWN** (no inventada). **HIPÓTESIS (no afirmada como hecho):** artefacto propio de la emulación de procfs del sandbox (entorno `e2b`). **Implicación:** la acreditación por fds es **inherentemente incompleta** en este entorno; es un límite de la *medición por `/proc`*, no del mecanismo de cierre.
5. **Ciclo de vida del descriptor de enumeración (observado, R4-A):** ante un fallo de `os.listdir(dirfd)` **tras** una apertura exitosa, el descriptor se cierra antes de propagar: no hay fuga (verificado por `fstat` → EBADF y ausencia en `/proc/self/fd`); un fallo de `os.close` se registra en el error (no se oculta) y el inventario no se declara acreditado.
6. **Anclaje de la inspección (observado, R4-B):** en modo `dirfd` las inspecciones son **relativas** al descriptor (`os.stat(name, dir_fd=dirfd)`), **no** resuelven de nuevo la ruta nominal; el descriptor se mantiene abierto durante la enumeración e inspección y se cierra al finalizar (éxito y error). El modo `path` (caída alternativa) es un recorrido **no anclado** y no se le atribuyen las garantías del modo `dirfd`.
7. **Registro del fallo de cierre final (observado, R5-A/R5-B):** si el `os.close(dirfd)` del `finally` falla **tras** una enumeración e inspección correctas, el error se **registra** con fase `"cierre"`, descriptor, tipo, errno y contexto; el inventario queda `complete=False`; el controlador dependiente asigna **UNKNOWN**; **no se afirma** que el descriptor quedó cerrado y **no se realizan reintentos** ciegos de `close()`.
8. **C5 se conserva (histórico):** el cierre por `arr._mmap.close()` con array vivo ⇒ SIGSEGV (3/3) sigue siendo el fallo de FEASIBILITY-D18-R1; R5 **no lo cambia**.

## 8. Hechos observados · hipótesis · UNKNOWN

- **HECHOS OBSERVADOS:**
  - Con todas las referencias liberadas + `gc.collect()`, el mmap se desmapea y su fd duplicado se cierra, sin SIGSEGV, en CPython 3.11.2 / NumPy 1.26.4 (A2–A6, B3, B4, D3, D4, R1-A1, R1-A2, R1-B1).
  - El fd propio del motor no lo cierra NumPy (C-A/C-C).
  - `fds_with_identity()` captura errores de enumeración e inspección (R2-C4/R2-C7: no propaga; inventario incompleto; controlador general no genera FAIL) y clasifica por evidencia con criterio conservador (R2-C2, R2-C3, R3-D).
  - Los escenarios A/B/C reales asignan UNKNOWN ante inventario incompleto y PASS ante inventario completo (R2-C10).
  - Ante fallo de `os.listdir(dirfd)` tras apertura OK, el dirfd se cierra (no hay fuga) y los fallos de cierre se registran (R2-C11).
  - En modo dirfd, las inspecciones son relativas al descriptor y el descriptor se cierra al finalizar; el modo path es no anclado (R2-C12).
  - Un fallo de `os.close(dirfd)` en el `finally` tras enumeración e inspección correctas se registra (fase "cierre", descriptor, errno), el inventario queda incompleto y el controlador asigna UNKNOWN (R2-C13).
  - `/proc/self/fd` tiene exactamente una entrada no stat-able, sin `fdinfo`, de número variable, que cede ante un descriptor real abierto (R2-C8).
- **HIPÓTESIS DE DISEÑO (no afirmadas como hechos):**
  - Para que el cierre sea efectivo en producción, el motor debe rastrear y liberar CADA referencia al mmap, y contar con un inventario de fds completo; de lo contrario la liberación no es acreditable.
  - El artefacto fantasma es propio de la emulación de procfs del sandbox (§7.4).
- **UNKNOWN:**
  - (a) si queda una referencia retenida, la liberación no se acredita (B6, D1, D2);
  - (b) si el inventario de `/proc/self/fd` es incompleto (entrada no estadizable, p.ej. el fantasma en este entorno), la acreditación por fds no es posible (A1, B1, B2, B5, C-A, C-B, C-C, R1-B2);
  - (c) lectura de maps con líneas no interpretables o ilegible (R1-A3, R1-A4);
  - (d) **causa root del descriptor fantasma** (R2-C8: error clasificado UNKNOWN_CAUSE; origen no determinado con certeza);
  - (e) **evidencia de procfs durante la inspección** (R2-C5: el entorno no proporciona un error ERROR_PROCFS con errno/contexto compatibles; la mecánica del clasificador sí está verificada);
  - (f) escenarios R2-C2/R2-C3: incompletitud con clasificación verificada → UNKNOWN por diseño metodológico.

## 9. Límites y lo que NO se afirma

- **`gc.collect()` NO es una garantía universal.** Es observación de CPython 3.11.2 / NumPy 1.26.4 en este entorno. No se extrapola a otras versiones, a Android/Termux, ni a `mmap.ACCESS_COPY`/`MAP_PRIVATE` con page-cache distinto.
- **Entorno único:** Linux 6.1.158+ x86_64, glibc 2.36, Python 3.11.2, NumPy 1.26.4, euid 1001, sandbox e2b.
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** validación de mecanismos, no de integración.
- **Seguimiento de referencias en el motor no implementado:** R5 valida que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; no valida que el motor las rastree todas.
- **La acreditación por `/proc` es frágil:** depende de que `/proc/self/maps` sea totalmente interpretable y `/proc/self/fd` totalmente estadizable. R3-D lo reconoce explícitamente y convierte la ambigüedad en UNKNOWN_CAUSE en lugar de atribuir ERROR_PROCFS sin evidencia.
- **Mecanismo de clasificación (R3-D) — límites documentados:** puede distinguir permisos, desapariciones en FS regular, descriptores reales en procfs (fdinfo presente) y fallos de enumeración/inspección con errno típico; **no puede distinguir** entre artefacto de procfs y descriptor real cerrado para ENOENT+fdinfo ausente, que se registra como UNKNOWN_CAUSE.
- **Modo "path" del enumerador:** recorrido no anclado (caída cuando O_DIRECTORY no está disponible); no se le atribuyen las garantías del modo dirfd.
- **Cierre final (R5-A):** el registro del fallo de cierre garantiza que el inventario no se declare acreditado; **NO garantiza** que el descriptor quede cerrado cuando el cierre falla (no se afirma); no se realizan reintentos por reutilización de número.
- **Hashes:** los sha256 de los dos archivos modificados se calculan realmente y se entregan en el mensaje de commit y en la entrega a Cris (no se afirman aquí valores no calculados).

## 10. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2 **con correcciones R1, R2, R3, R4 y R5**. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (C5 histórico). R2+R1+R2+R3+R4+R5 añaden: existe un ciclo de vida SEGURO (referencias + `gc.collect()`) que evita el SIGSEGV, **pero condicionado** a (i) liberar todas las referencias y (ii) disponer de un inventario de `/proc` completo; con referencia retenida o inventario incompleto la liberación no se acredita (UNKNOWN). Veredicto global: **UNKNOWN**.
- La decisión sobre D-18 / el mecanismo de cierre seguro de NumPy corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris. **Esta autorización no adjudica D18 como PASS ni autoriza integración en producción.**

## 11. Trazabilidad

- Padre: `e412d561b50cf358d21609d76646fc4a361cd0fb` (FEASIBILITY-D18-R2-R4), hijo directo de `03422d6b69b83b590cead24e6aaba9c9c46c1e23`.
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (modificado: R5-A/B/C).
- Informe: `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (modificado: R5-C).
- Evidencia cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera).
- Archivos históricos D18 / D18-R1 / D18-R2 / D18-R2-R2 / D18-R2-R3 / D18-R2-R4 previos: **no modificados** (se actualiza el mismo informe D18-R2 con la corrección R5).
- Commit hijo directo de `e412d56...`: SHA en mensaje de commit; verificable vía `gh api`.
- SHA-256 de los dos archivos modificados: en el mensaje de commit y en la entrega a Cris.

## 12. Enlaces de GitHub (para auditoría de Cris)

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama de esta sesión (`arena/9a32cda8-sdv-sdi-sgm`, HEAD = padre obligatorio `e412d56`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/9a32cda8-sdv-sdi-sgm
- Commit padre obligatorio `e412d56`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/e412d561b50cf358d21609d76646fc4a361cd0fb
- Commit antecesor `03422d6`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/03422d6b69b83b590cead24e6aaba9c9c46c1e23
- `main` intacta (`b64f15ae`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b64f15ae8b28e46eef3c024dc62c85fe27c69494
- Arnés R2+R1+R2+R3+R4+R5 (raw): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe R2+R1+R2+R3+R4+R5 (raw, este archivo): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
