# FEASIBILITY-D18-R2 + R1 + R2 — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP (rectificación final del inventario procfs)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena (sesión `arena/9a32cda8-sdv-sdi-sgm`).
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Alcance de ESTA entrega (adjudicación de Cris, D18-R2-R2):** **rectificación final del inventario procfs** del arnés R2+R1 (R2-A captura de errores de enumeración, R2-B clasificación de errores, R2-C pruebas controladas, R2-D reejecución e informe). No se amplía el alcance a referencias retenidas ni a nuevas estrategias de liberación.
- **Relación con D-18 / R1:** D-18 permanece **FAIL**. El hallazgo **C5** (SIGSEGV al cerrar `arr._mmap` con el array vivo, reproducible 3/3) es de FEASIBILITY-D18-R1 y se **conserva como histórico e independiente**; R2/R1/R2-R2 **no lo re-ejecutan ni lo ocultan**.
- **Veredicto global R2+R1+R2:** **UNKNOWN** (precedencia FAIL > UNKNOWN > PASS). 18 PASS · 0 FAIL · 16 UNKNOWN (34 subpruebas). El camino seguro **funciona** cuando se liberan TODAS las referencias + `gc.collect()`, pero **no puede garantizarse incondicionalmente** (una referencia retenida, o un inventario de `/proc` incompleto, impiden acreditar la liberación → UNKNOWN/fallo cerrado).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R2-R2):** `709991589255239208340d0db6907d1cbb91609e` (FEASIBILITY-D18-R2-R1: corrección metodológica del arnés).
- **Verificación de identidad ANTES de trabajar:** recuperación mediante `git fetch origin 7099915...`; `git cat-file -t` → `commit`; padre directo del commit recuperado = `f206980f9279e5793756496b2ceb563d92859b30`; `f206980` verificado como antecesor; advance exclusivo por **fast-forward** (`git merge --ff-only`); sin reset, force, cherry-pick ni rebase. Tras la preparación: rama `arena/9a32cda8-sdv-sdi-sgm`, HEAD exactamente `7099915...`, árbol limpio. **TODO CONFORME**.
- **Nuevo commit:** hijo directo de `7099915...`; **exactamente 2 archivos modificados** (los dos autorizados). SHA completo en el mensaje de commit (verificable vía `git`/`gh api`).

## 2. Archivos modificados (exactamente los 2 autorizados, ambos existentes)

| Archivo | Rol | Cambio |
|---|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` | Arnés R2+R1+R2 (34 subpruebas: 19 R2 + 9 R2-C controladas + 6 R1 controladas) | R2-A captura de errores de enumeración; R2-B clasificación; R2-C pruebas controladas; sin nuevos archivos |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` | Este informe | Actualiza método, recuentos, evidencias, hallazgo del fd fantasma, procedimientos y limitaciones (R2-D) |

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

## 4. Correcciones metodológicas (lo que cambió y por qué)

### R1 (fase previa, conservada íntegramente)
- **R1-A — `count_maps()` / `parse_maps()`:** líneas no interpretables de `/proc/self/maps` no se descartan; `status` de tres estados (`complete`/`incomplete`/`unreadable`); incompletitud o ilegibilidad → UNKNOWN; cero mappings solo tras lectura `complete`; FAIL solo si una lectura `complete` contradice lo esperado.
- **R1-B — `fds_with_identity()`:** errores de `stat` sobre entradas individuales se registran y fuerzan `complete=False`.
- **R1-C — Propagación:** ningún escenario A/B/C declara PASS si su acreditación depende de una lectura/inventario incompleto.
- **R1-D — Informe:** C5 conservado como FAIL histórico; sin `_mmap.close()` forzado; sin garantías universales atribuidas a `gc.collect()`.

### R2-A — Captura de errores de enumeración (rectificación final)
- **Antes:** `os.listdir(fd_dir)` se ejecutaba FUERA de cualquier manejo de errores; si la apertura/enumeración del directorio fallaba, la excepción **propagaba** y el controlador general la convertía **artificialmente en FAIL**.
- **Ahora:** `fds_with_identity()` captura **también** los errores de `os.listdir(fd_dir)`:
  - Si no se puede abrir o enumerar el directorio, devuelve un inventario **INCOMPLETO**.
  - Se registra el error con su contexto (`phase=enumeracion`, `fd_dir`, errno, tipo de excepción).
  - **La función NO propaga la excepción**: el controlador general no puede convertirla en FAIL artificial (ver R2-C7).
  - La imposibilidad de completar el inventario produce **UNKNOWN** en los escenarios dependientes.
  - **Nunca** se declara PASS ni cero descriptores a partir de un inventario incompleto.
- **Enumeración por descriptor de directorio mantenido abierto:** se investiga la estrategia de abrir el directorio con `O_DIRECTORY` y enumerar vía el descriptor, manteniéndolo **abierto durante la inspección**, para que el descriptor propio de la enumeración sea estable e identificable y no se confunda con una desaparición externa. El modo usado se registra en el inventario (`enum_mode`, `enum_dirfd`).
  - **Se DEMUESTRA por pruebas (R2-C9)** lo que la estrategia logra: descriptor estable/identificable, y diferenciación de desapariciones externas.
  - **Se NO asume que elimine el problema**: R2-C8 demuestra que el artefacto fd fantasma del entorno **persiste** con esta estrategia (es un artefacto de listado de procfs, no un descriptor real), como se detalla en §7.

### R2-B — Clasificación de errores
Cada error del inventario lleva `classification`, `errno`, `exception_type`, `name`, `phase` y `context`:

| Clasificación | Criterio (evidencia, no invención) |
|---|---|
| `DESCRIPTOR_DESAPARECIDO` | Entrada que desaparece durante el recorrido: aparecía en la enumeración y la inspección (`stat`) falla con `ENOENT` **sin** evidencia de que el fallo sea del propio procfs. |
| `DESCRIPTOR_INACCESIBLE` | Error de permisos o acceso (`EACCES`/`EPERM`). |
| `ERROR_PROCFS` | Fallo de apertura, enumeración o inspección **atribuible al propio procfs**; en `/proc/self/fd`, `ENOENT` con `fdinfo` ausente (la entrada no es un descriptor real abierto); o error no clasificable de procfs/fs virtual (`EIO`, `EINVAL`, `ENOTDIR`, `ENOSYS`, …). |
| `UNKNOWN_CAUSE` | La causa **no puede determinarse con seguridad**: p.ej. fallo de enumeración en un directorio que no es de procfs, sin evidencia suficiente para atribuirlo. **No se inventa una clasificación.** |

Ningún error se oculta: todos quedan registrados en `inv.errors` (con clasificación) y fuerzan `complete=False`.

### R2-C — Pruebas controladas obligatorias
Añadidas las nueve pruebas R2-C1..R2-C9 (§5). Cubren: inventario completo, desaparición durante el recorrido, inaccesibilidad, error de enumeración, error de procfs en inspección, propagación de UNKNOWN, ausencia de FAIL artificial, origen del fd fantasma y demostración del descriptor de directorio mantenido.

### R2-D — Reejecución e informe
- Reejecución del conjunto completo de FEASIBILITY-D18-R2 con las correcciones (34 subpruebas).
- Se mantiene: precedencia **FAIL > UNKNOWN > PASS**; **C5 como FAIL histórico de D18-R1**; prohibición de `_mmap.close()` forzado con referencias vivas; ausencia de garantías universales atribuidas a `gc.collect()`.
- Resultados actualizados; hechos, hipótesis y UNKNOWN separados explícitamente (§8).

## 5. Resultados individuales (34 subpruebas)

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

**Conclusión C (observado, no inferido):** en A/B/C el **único** recurso que cierra el camino seguro es el fd duplicado interno del objeto `mmap`, vía su finalizador. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor; B no tiene fd_mm. La *lógica* de diferenciación sigue siendo válida; lo que impide acreditarla como PASS en este entorno es la incompletitud del inventario de fds.

### R2-D — Fallos y excepciones

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| D1 | Liberación incompleta (vista retenida) | maps persiste | **UNKNOWN** |
| D2 | Referencia retenida impide acreditar | maps persiste | **UNKNOWN** |
| D3 | Flush no bloquea la liberación | flush persiste; sin flush→maps=0 | PASS |
| D4 | Cierre seguro sin errores | `del arr; gc` → sin excepción, maps=0 | PASS |

**Conclusión D:** las variantes de fallo no usan `_mmap.close()` forzado; el mapeo permanece vivo y la liberación termina en UNKNOWN/fallo cerrado. El flush no es prerrequisito del unmapping y un error de flush no bloquea la liberación por `gc`. El camino seguro (finalizador) no lanza excepción.

### R2-C controladas (obligatorias, R2-A/R2-B)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R2-C1 | Inventario COMPLETO de fds | complete=True; matched=[3]; errors=[]; enum por dirfd | PASS |
| R2-C2 | Entrada que desaparece durante el recorrido | complete=False; error `DESCRIPTOR_DESAPARECIDO`, errno=2, FileNotFoundError, entrada '5' | **UNKNOWN** |
| R2-C3 | Entrada inaccesible (permisos) | complete=False; error `DESCRIPTOR_INACCESIBLE`, errno=13, PermissionError, entrada '9' | **UNKNOWN** |
| R2-C4 | Error de enumeración del directorio | no propaga; complete=False; phase=enumeración; /proc → `ERROR_PROCFS`, no-procfs → `UNKNOWN_CAUSE` | PASS |
| R2-C5 | Error de procfs durante la inspección | ENOENT+fdinfo ausente → `ERROR_PROCFS`; EACCES → `DESCRIPTOR_INACCESIBLE`; ENOENT no-procfs → `DESCRIPTOR_DESAPARECIDO` | PASS |
| R2-C6 | Propagación de UNKNOWN a escenarios dependientes | inventario forzado incompleto → verdictos A/B/C = UNKNOWN (nunca PASS) | PASS |
| R2-C7 | Sin FAIL artificial por error de enumeración | `OSError(EIO)` en listdir: no propaga, inventario incompleto, controlador general NO genera FAIL | PASS |
| R2-C8 | Origen del descriptor fantasma fd 3 (diagnóstico) | evidencia recopilada; clasificación `ERROR_PROCFS`; **causa root: UNKNOWN** (§7) | **UNKNOWN** |
| R2-C9 | Descriptor de directorio mantenido abierto | dirfd estable/identificable; tras borrado externo, ruta falla y el dirfd no; modo registrado | PASS |

**R2-C1..R2-C9 demuestran** el mecanismo R2-A/R2-B: la enumeración y la inspección se capturing metodológicamente; los inventarios completos permiten acreditar; cualquier incompletitud fuerza UNKNOWN y jamás PASS ni FAIL artificial.

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
Subpruebas: 34 (19 R2 + 9 R2-C controladas + 6 R1 controladas)
Conteos:    PASS=18 FAIL=0 UNKNOWN=16
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
```

Desglose de PASS (18): A2,A3,A4,A5,A6 · B3,B4 · D3,D4 · R2-C1,R2-C4,R2-C5,R2-C6,R2-C7,R2-C9 · R1-A1,R1-A2 · R1-B1.
Desglose de UNKNOWN (16): A1,B1,B2,B5,B6 · C-A,C-B,C-C · D1,D2 · R2-C2,R2-C3,R2-C8 · R1-A3,R1-A4 · R1-B2.

**Evolución de los veredictos:** respecto al arnés R2+R1 original (12 PASS · 13 UNKNOWN), los 19 escenarios A/B/C/D/R1 conservan **exactamente** sus veredictos; los 9 nuevos R2-C añaden 6 PASS (verificaciones mecánicas del mecanismo) y 3 UNKNOWN (R2-C2, R2-C3: escenarios de incompletitud que, por diseño metodológico, no pueden acreditar PASS; R2-C8: causa root del fantasma no determinada con certeza). La corrección R2-A/B **no revierte** ningún veredicto previo; fija el tratamiento de los errores de enumeración (antes: FAIL artificial; ahora: UNKNOWN registrado).

## 7. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4):** soltar el array raíz, todas las vistas/slices, contenedores y referencias exportadas, y luego `gc.collect()`, finaliza el `mmap` (su `__del__`/`__dealloc__` cierra el fd duplicado y desmapea). Evita el SIGSEGV de C5. **Observación de comportamiento**, coherente con la semántica de que el `ndarray` mantiene al `mmap` como `base`; **NO es una garantía documentada de NumPy**.
2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** en A/B/C el único fd que cierra el camino seguro es el dup interno del objeto `mmap`. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor. B no tiene fd_mm.
3. **Condición de seguridad: liberar TODAS las referencias (hipótesis de diseño, no dem. incondicional):** cualquier referencia olvidada mantiene el mapeo vivo → UNKNOWN/fallo cerrado. R2 **no autoriza por sí mismo EXIT_OK** ni un «cierre efectivo garantizado» en producción.
4. **Hallazgo del descriptor fantasma de `/proc/self/fd` (hechos observados, R2-C8):** en este entorno, `/proc/self/fd` lista **exactamente una entrada** que `stat`/`readlink` no pueden resolver (`ENOENT`) y que **carece de `fdinfo`**. Hechos observados:
   - **No es un descriptor real abierto** de este proceso: carece de `fdinfo` (inspección directa, 3 pasadas).
   - **No es el descriptor transitorio de la propia enumeración:** el descriptor propio de la enumeración es estable, identificable y real (R2-C9); el fantasma está presente en pasadas de listado independientes, incluso antes de cualquier enumeración nuestra.
   - **Su número es VARIABLE entre llamadas** del mismo proceso (observado `3` y `5`/`6` en distintas ejecuciones/pasadas).
   - **Cuando el número lo ocupa un descriptor real abierto**, `stat` **succee** (observado en R2-C-A, donde el motor abrió un fd real que coincidió con el número 3; y en diagnóstico directo): el fantasma ocupa un hueco del listado que cede ante un descriptor real.
   - **Clasificación por evidencia:** el fallo de inspección se clasifica `ERROR_PROCFS` (atribuible al propio procfs; fdinfo ausente). **CAUSA ROOT: UNKNOWN** — no determinada con certeza desde userspace.
   - **HIPÓTESIS (no afirmada como hecho):** el artefacto es propio de la emulación de procfs del sandbox (entorno `e2b`, kernel reportado `6.1.158+`); se desconoce el mecanismo interno que produce la entrada fantasma en el listado.
   - **Implicación:** la acreditación basada en enumerar fds es **inherentemente incompleta** en este entorno; los escenarios que la usan son UNKNOWN. Esto **NO invalida** la conclusión de que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; impide solo **acreditarlo** aquí. Es un límite de la *medición por `/proc`*, no del mecanismo de cierre.
5. **La enumeración por descriptor de directorio mantenido (R2-A)** hace explícito y estable el descriptor propio de la enumeración y permite diferenciar desapariciones externas (R2-C9), **pero NO elimina** el fantasma (R2-C8): la alternativa se demostró, no se asumió, y sus límites se documentaron.
6. **C5 se conserva (histórico):** el cierre por `arr._mmap.close()` con array vivo ⇒ SIGSEGV (3/3) sigue siendo el fallo de FEASIBILITY-D18-R1; R2/R2-R2 **no lo cambian**.

## 8. Hechos observados · hipótesis · UNKNOWN

- **HECHOS OBSERVADOS:**
  - Con todas las referencias liberadas + `gc.collect()`, el mmap se desmapea y su fd duplicado se cierra, sin SIGSEGV, en CPython 3.11.2 / NumPy 1.26.4 (A2–A6, B3, B4, D3, D4, R1-A1, R1-A2, R1-B1).
  - El fd propio del motor no lo cierra NumPy (C-A/C-C).
  - `fds_with_identity()` captura errores de enumeración (R2-C4/R2-C7: no propaga; inventario incompleto; controlador general no genera FAIL) y clasifica por evidencia (R2-C2, R2-C3, R2-C5).
  - `/proc/self/fd` tiene exactamente una entrada no stat-able, sin `fdinfo`, de número variable, que cede ante un descriptor real abierto (R2-C8).
- **HIPÓTESIS DE DISEÑO (no afirmadas como hechos):**
  - Para que el cierre sea efectivo en producción, el motor debe rastrear y liberar CADA referencia al mmap, y contar con un inventario de fds completo; de lo contrario la liberación no es acreditable.
  - El artefacto fantasma es propio de la emulación de procfs del sandbox (§7.4).
- **UNKNOWN:**
  - (a) si queda una referencia retenida, la liberación no se acredita (B6, D1, D2);
  - (b) si el inventario de `/proc/self/fd` es incompleto (entrada no estadizable, p.ej. el fantasma en este entorno), la acreditación por fds no es posible (A1, B1, B2, B5, C-A, C-B, C-C, R1-B2);
  - (c) lectura de maps con líneas no interpretables o ilegible (R1-A3, R1-A4);
  - (d) **causa root del descriptor fantasma de `/proc/self/fd`** (R2-C8: se clasifica el error, pero no se determina con certeza el origen del artefacto);
  - (e) escenarios R2-C2/R2-C3: la incompletitud impide acreditar PASS por diseño metodológico.

## 9. Límites y lo que NO se afirma

- **`gc.collect()` NO es una garantía universal.** Es observación de CPython 3.11.2 / NumPy 1.26.4 en este entorno. No se extrapola a otras versiones, a Android/Termux, ni a `mmap.ACCESS_COPY`/`MAP_PRIVATE` con page-cache distinto.
- **Entorno único:** Linux 6.1.158+ x86_64, glibc 2.36, Python 3.11.2, NumPy 1.26.4, euid 1001, sandbox e2b.
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** validación de mecanismos, no de integración.
- **Seguimiento de referencias en el motor no implementado:** R2 valida que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; no valida que el motor las rastree todas.
- **La acreditación por `/proc` es frágil:** depende de que `/proc/self/maps` sea totalmente interpretable y `/proc/self/fd` totalmente estadizable. R2-A/R2-B lo reconocen explícitamente y convierten cualquier incompletitud en UNKNOWN, y fijan que un fallo de enumeración nunca se convierta en FAIL artificial.
- **Hashes:** los sha256 de los dos archivos modificados se calculan realmente y se entregan en el mensaje de commit y en la entrega a Cris (no se afirman aquí valores no calculados).

## 10. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2 **con rectificación final R2 del inventario procfs**. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (C5 histórico). R2+R1+R2 añaden: existe un ciclo de vida SEGURO (referencias + `gc.collect()`) que evita el SIGSEGV, **pero condicionado** a (i) liberar todas las referencias y (ii) disponer de un inventario de `/proc` completo; con referencia retenida o inventario incompleto la liberación no se acredita (UNKNOWN). Veredicto global: **UNKNOWN**.
- La decisión sobre D-18 / el mecanismo de cierre seguro de NumPy corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris. **Esta autorización no adjudica D18 como PASS ni autoriza integración en producción.**

## 11. Trazabilidad

- Padre: `709991589255239208340d0db6907d1cbb91609e` (FEASIBILITY-D18-R2-R1), hijo directo de `f206980f9279e5793756496b2ceb563d92859b30`.
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (modificado: R2-A/B/C/D).
- Informe: `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (modificado: R2-D).
- Evidencia cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera).
- Archivos históricos D18 / D18-R1 / D18-R2 previos: **no modificados** (se actualiza el mismo informe D18-R2 con la rectificación R2).
- Commit hijo directo de `7099915...`: SHA en mensaje de commit; verificable vía `gh api`.
- SHA-256 de los dos archivos modificados: en el mensaje de commit y en la entrega a Cris.

## 12. Enlaces de GitHub (para auditoría de Cris)

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama de esta sesión (`arena/9a32cda8-sdv-sdi-sgm`, HEAD = padre obligatorio `7099915`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/9a32cda8-sdv-sdi-sgm
- Commit padre obligatorio `7099915`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/709991589255239208340d0db6907d1cbb91609e
- Commit antecesor `f206980`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/f206980f9279e5793756496b2ceb563d92859b30
- `main` intacta (`b64f15ae`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b64f15ae8b28e46eef3c024dc62c85fe27c69494
- Arnés R2+R1+R2 (raw): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe R2+R1+R2 (raw, este archivo): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
