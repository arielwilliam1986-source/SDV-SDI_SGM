# FEASIBILITY-D18-R2 + R1 + R2 + R3 — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP (rectificación final de verificación)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena (sesión `arena/9a32cda8-sdv-sdi-sgm`).
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Alcance de ESTA entrega (adjudicación de Cris, D18-R2-R3):** **rectificación final de verificación** del arnés R2+R1+R2 (R3-A propagación correcta, R3-B verificación de clasificación, R3-C evidencia de procfs, R3-D clasificación conservadora de ENOENT, R3-E propagación en escenarios reales, R3-F reejecución e informe). No se amplía el alcance a referencias retenidas ni a nuevas estrategias de liberación.
- **Relación con D-18 / R1 / R2:** D-18 permanece **FAIL**. El hallazgo **C5** (SIGSEGV al cerrar `arr._mmap` con el array vivo, reproducible 3/3) es de FEASIBILITY-D18-R1 y se **conserva como histórico e independiente**; R2/R1/R2-R2/R2-R3 **no lo re-ejecutan ni lo ocultan**.
- **Veredicto global R2+R1+R2+R3:** **UNKNOWN** (precedencia FAIL > UNKNOWN > PASS). 18 PASS · 0 FAIL · 17 UNKNOWN (35 subpruebas). El camino seguro **funciona** cuando se liberan TODAS las referencias + `gc.collect()`, pero **no puede garantizarse incondicionalmente** (una referencia retenida, o un inventario de `/proc` incompleto, impiden acreditar la liberación → UNKNOWN/fallo cerrado).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R2-R3):** `66978202fb6f9211d71b6114614ae38254adac6a` (FEASIBILITY-D18-R2-R2).
- Verificado ANTES de trabajar: HEAD = `6697820...` (local = padre exigido), rama `arena/9a32cda8-sdv-sdi-sgm`, árbol limpio (`git status --porcelain` vacío). **TODO CONFORME**. Sin recuperación, fetch, reset, force, cherry-pick ni rebase necesarios en esta fase.
- **Nuevo commit:** hijo directo de `6697820...`; **exactamente 2 archivos modificados** (los dos autorizados). SHA completo en el mensaje de commit (verificable vía `git`/`gh api`).

## 2. Archivos modificados (exactamente los 2 autorizados, ambos existentes)

| Archivo | Rol | Cambio |
|---|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` | Arnés R2+R1+R2+R3 (35 subpruebas: 19 R2 + 10 R2-C controladas + 6 R1 controladas) | R3-A/B/C/D/E correcciones; sin nuevos archivos |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` | Este informe | Actualiza método, recuentos, evidencias, clasificación conservadora, hallazgo del fd fantasma, procedimientos y limitaciones (R3-F) |

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

### R1 / R2 (fases previas, conservadas íntegramente)
- **R1-A/B/C/D** — lectura de `/proc/self/maps` con estados complete/incomplete/unreadable; errores de `stat` en inventario de fds registrados; propagación de UNKNOWN; C5 como FAIL histórico; sin `_mmap.close()` forzado ni garantías universales de `gc.collect()`.
- **R2-A** — `fds_with_identity()` captura **también** los errores de `os.listdir(fd_dir)`: imposibilidad de abrir/enumerar → inventario **INCOMPLETO** con error+contexto registrado; **no propaga** la excepción (evita FAIL artificial del controlador); incompletitud → UNKNOWN; nunca PASS ni cero descriptores desde incompleto. Enumeración por descriptor de directorio mantenido abierto, demostrado por pruebas (R2-C9) y NO asumido como solución del artefacto fantasma.
- **R2-B** — clasificación expresa de errores con errno, tipo de excepción, nombre de entrada y contexto conservados.

### R3-A — R2-C7: propagación correcta (dos propiedades independientes)
- **Antes:** la prueba asignaba PASS al controlador simulado cuando la función no propagaba, aunque el inventario estuviera incompleto.
- **Ahora** verifica dos propiedades **independientes**:
  - **P1:** el error de enumeración **no escapa** de `fds_with_identity()` (no se propaga).
  - **P2:** el controlador recibe `complete=False` y asigna **UNKNOWN**, nunca PASS ni FAIL artificial.
- **La prueba solo da PASS si ambas propiedades se verifican.**

### R3-B — R2-C2 y R2-C3: verificación de clasificación
- **Antes:** el veredicto dependía exclusivamente de `not inv.complete`.
- **Ahora:**
  - Clasificación **correcta** + `complete=False` → **UNKNOWN**.
  - Clasificación **incorrecta** → **FAIL**.
  - **No** se asigna UNKNOWN automáticamente por el simple hecho de que el inventario sea incompleto cuando la prueba verifica una clasificación específica.
- Verificados: R2-C2 → `DESCRIPTOR_DESAPARECIDO` (errno=2, FileNotFoundError, entrada '5'); R2-C3 → `DESCRIPTOR_INACCESIBLE` (errno=13, PermissionError, entrada '9').

### R3-C — R2-C5: evidencia de procfs
- La prueba exige la **presencia real** de un error de inspección clasificado **ERROR_PROCFS** con **errno compatible** (EIO/EINVAL/ENOTDIR/ENOSYS/EOPNOTSUPP/EBUSY/EREMOTEIO) y **contexto de procfs**. No vale cualquier error genérico.
- Si el entorno no proporciona evidencia suficiente → **UNKNOWN, no PASS**.
- **Resultado en este entorno: UNKNOWN.** La mecánica del clasificador se verifica unitariamente y es correcta (ENOENT+fdinfo ausente en procfs → UNKNOWN_CAUSE; ENOENT en FS regular → DESAPARECIDO; EACCES → INACCESIBLE; EIO en procfs → ERROR_PROCFS), pero el inventario real de `/proc/self/fd` **no contiene** un error de inspección ERROR_PROCFS con errno compatible (el único error es el fantasma ENOENT, clasificado UNKNOWN_CAUSE por R3-D). Por R3-C, la prueba declara **UNKNOWN**.

### R3-D — Clasificación conservadora de ENOENT
- **Corrección de criterio:** la ausencia de `fdinfo` después de un ENOENT **no demuestra por sí sola** que la entrada sea un artefacto de procfs: también puede corresponder a un **descriptor real cerrado** entre la enumeración y la inspección.
- **Regla corregida** en `_fdinfo_probe()`/`_classify_fd_error()`:
  - **ENOENT en FS regular** (no procfs): entrada previamente listada que ya no se inspecciona → `DESCRIPTOR_DESAPARECIDO` (no existe concepto de artefacto de procfs en un FS regular).
  - **ENOENT en procfs:**
    - `fdinfo` **PRESENTE** (evidencia de descriptor real) → `DESCRIPTOR_DESAPARECIDO` (se cerró entre enumeración e inspección).
    - `fdinfo` **AUSENTE** → **UNKNOWN_CAUSE** (no se puede distinguir artefacto de procfs de descriptor real cerrado; no se inventa).
  - **ERROR_PROCFS** se mantiene solo con **evidencia suficiente**: errores de enumeración en directorio de procfs, o errores de inspección con errno típico de procfs/fs virtual (EIO, EINVAL, ENOTDIR, ENOSYS, EOPNOTSUPP, EBUSY, EREMOTEIO).
  - **EACCES/EPERM** → `DESCRIPTOR_INACCESIBLE`; cualquier otra causa sin evidencia → `UNKNOWN_CAUSE`.
- **Qué puede y qué no puede distinguir el mecanismo** (documentado):
  - **Puede distinguir:** permisos/acceso (EACCES); desapariciones en FS regular (ENOENT tras listado); descriptores reales en procfs (fdinfo presente); fallos de enumeración en procfs; errores de inspección con errno típico de procfs.
  - **NO puede distinguir (con este mecanismo):** si un ENOENT+fdinfo ausente en `/proc/self/fd` es un artefacto de procfs o un descriptor real cerrado entre enumeración e inspección → se registra **UNKNOWN_CAUSE** y no se inventa una causa root para el descriptor fantasma.

### R3-E — Propagación en escenarios reales
- **Nueva prueba R2-C10**: no basta una función simplificada que reproduce la regla aislada. Se ejecutan **escenarios REALES** del arnés (`test_a1`, `test_b1`, `test_b5`, `test_c_b`: np.memmap real, `count_maps` real, lógica de veredicto real) con el inventario de fds controlado en dos condiciones:
  - **Inventario INCOMPLETO** (`complete=False`): los escenarios asignan **UNKNOWN** (verificados A1, B1, B5, C-B).
  - **Inventario COMPLETO** (`complete=True`): A1, B1 y C-B asignan **PASS**, demostrando que el UNKNOWN del caso incompleto depende de la regla y **no es UNKNOWN hardcodeado**.
- **Limitación declarada:** en la condición COMPLETA con stub, B5 asigna FAIL porque el stub informa `matched=[]` y B5 exige `bool(alive_fds)`; la verificación que se atribuye a B5 es **incompleto → UNKNOWN**, no la contraste completa. El contraste completo se atribuye solo a A1/B1/C-B.
- **Limitación adicional declarada:** la condición COMPLETA con stub controla `complete` pero no reproduce el contenido real de `matched`; la verificación de la regla de propagación es lo que cubre esta prueba, no la corrección de los valores de `matched`.

### R3-F — Reejecución y consistencia
- Reejecución del **conjunto completo D18-R2**, incluyendo pruebas R1 y R2-C (35 subpruebas).
- Se mantienen: precedencia **FAIL > UNKNOWN > PASS**; **C5 como FAIL histórico** (no re-ejecutado); prohibición de `_mmap.close()` con referencias vivas; ausencia de garantías universales atribuidas a `gc.collect()`; separación de hechos, hipótesis y UNKNOWN.

## 5. Resultados individuales (35 subpruebas)

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

### R2-C controladas (obligatorias, R2-A/R2-B + R3-A..E)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R2-C1 | Inventario COMPLETO de fds | complete=True; matched=[3]; errors=[]; enum por dirfd | PASS |
| R2-C2 | Entrada que desaparece durante el recorrido | complete=False; error `DESCRIPTOR_DESAPARECIDO`, errno=2, FileNotFoundError, entrada '5' (R3-B: UNKNOWN solo si clasificación correcta) | **UNKNOWN** |
| R2-C3 | Entrada inaccesible (permisos) | complete=False; error `DESCRIPTOR_INACCESIBLE`, errno=13, PermissionError, entrada '9' (R3-B) | **UNKNOWN** |
| R2-C4 | Error de enumeración del directorio | no propaga; complete=False; phase=enumeración; /proc → `ERROR_PROCFS`, no-procfs → `UNKNOWN_CAUSE` | PASS |
| R2-C5 | Error de procfs durante la inspección (R3-C) | mecánica correcta; **sin evidencia real** de ERROR_PROCFS con errno/contexto compatibles en /proc/self/fd | **UNKNOWN** |
| R2-C6 | Propagación de UNKNOWN a escenarios dependientes | inventario forzado incompleto → A/B/C = UNKNOWN | PASS |
| R2-C7 | Sin FAIL artificial (R3-A) | P1 no propaga = OK; P2 controlador → UNKNOWN = OK | PASS |
| R2-C8 | Origen del descriptor fantasma fd (diagnóstico) | evidencia recopilada; clasificación **UNKNOWN_CAUSE** (R3-D); causa root: UNKNOWN (§7) | **UNKNOWN** |
| R2-C9 | Descriptor de directorio mantenido abierto | dirfd estable/identificable; tras borrado externo, ruta falla y el dirfd no; modo registrado | PASS |
| R2-C10 | Propagación en escenarios REALES A/B/C (R3-E) | incompleto → UNKNOWN en A1/B1/B5/C-B; completo → A1/B1/C-B = PASS | PASS |

**R2-C1..R2-C10 demuestran** el mecanismo R2-A/R2-B/R3: enumeración e inspección capturadas; inventarios completos permiten acreditar; cualquier incompletitud fuerza UNKNOWN; nunca PASS ni FAIL artificial; clasificación conservadora sin inventar causas.

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
Subpruebas: 35 (19 R2 + 10 R2-C controladas + 6 R1 controladas)
Conteos:    PASS=18 FAIL=0 UNKNOWN=17
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
```

Desglose de PASS (18): A2,A3,A4,A5,A6 · B3,B4 · D3,D4 · R2-C1,R2-C4,R2-C6,R2-C7,R2-C9,R2-C10 · R1-A1,R1-A2 · R1-B1.
Desglose de UNKNOWN (17): A1,B1,B2,B5,B6 · C-A,C-B,C-C · D1,D2 · R2-C2,R2-C3,R2-C5,R2-C8 · R1-A3,R1-A4 · R1-B2.

**Evolución respecto a R2+R1+R2 (18 PASS · 16 UNKNOWN):** los 25 escenarios A/B/C/D/R1-B conservan sus veredictos; los cambios en R3 son metodológicos:
- **R2-C5 pasa PASS→UNKNOWN**: la versión R2 asumía ERROR_PROCFS para el fantasma ENOENT; R3-D demuestra que esa evidencia **no basta** (fdinfo ausente no descarta descriptor real cerrado) y R3-C exige evidencia real de un error ERROR_PROCFS con errno compatible, que este entorno **no proporciona** → UNKNOWN honesto.
- **R2-C2/R2-C3 mantienen UNKNOWN**, pero ahora el veredicto **verifica la clasificación** (R3-B): UNKNOWN solo si la clasificación es correcta; incorrecta → FAIL.
- **R2-C7 mantiene PASS**, con las dos propiedades independientes verificadas explícitamente (R3-A).
- **R2-C10 añadida** (R3-E): PASS, verificando la regla sobre escenarios reales.
- **R2-C8 mantiene UNKNOWN**, con clasificación corregida a UNKNOWN_CAUSE (R3-D) y causa root sin inventar.

## 7. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4):** soltar el array raíz, todas las vistas/slices, contenedores y referencias exportadas, y luego `gc.collect()`, finaliza el `mmap` (su `__del__`/`__dealloc__` cierra el fd duplicado y desmapea). Evita el SIGSEGV de C5. **Observación de comportamiento**, coherente con la semántica de que el `ndarray` mantiene al `mmap` como `base`; **NO es una garantía documentada de NumPy**.
2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** en A/B/C el único fd que cierra el camino seguro es el dup interno del objeto `mmap`. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor. B no tiene fd_mm.
3. **Condición de seguridad: liberar TODAS las referencias (hipótesis de diseño, no dem. incondicional):** cualquier referencia olvidada mantiene el mapeo vivo → UNKNOWN/fallo cerrado. R3 **no autoriza por sí mismo EXIT_OK** ni un «cierre efectivo garantizado» en producción.
4. **Hallazgo del descriptor fantasma de `/proc/self/fd` (hechos observados, R2-C8):** en este entorno, `/proc/self/fd` lista **exactamente una entrada** que `stat`/`readlink` no pueden resolver (`ENOENT`) y que **carece de `fdinfo`**. Hechos observados:
   - **No es un descriptor real abierto** de este proceso: carece de `fdinfo` (inspección directa, 3 pasadas).
   - **No es el descriptor transitorio de la propia enumeración:** el descriptor propio de la enumeración es estable, identificable y real (R2-C9); el fantasma está presente en pasadas de listado independientes, incluso antes de cualquier enumeración nuestra.
   - **Su número es VARIABLE entre llamadas** del mismo proceso (observado `3`, `5` y `6` en distintas ejecuciones/pasadas).
   - **Cuando el número lo ocupa un descriptor real abierto**, `stat` **succee** (observado en R2-C-A, donde el motor abrió un fd real que coincidió con el número 3; y en diagnóstico directo): el fantasma ocupa un hueco del listado que cede ante un descriptor real.
   - **Clasificación corregida (R3-D):** ENOENT + fdinfo ausente **NO se atribuye automáticamente a procfs** → **UNKNOWN_CAUSE** (no se puede distinguir artefacto de procfs de descriptor real cerrado entre enumeración e inspección). **No se inventa causa root.**
   - **HIPÓTESIS (no afirmada como hecho):** el artefacto es propio de la emulación de procfs del sandbox (entorno `e2b`, kernel reportado `6.1.158+`); se desconoce el mecanismo interno que produce la entrada fantasma en el listado.
   - **Implicación:** la acreditación basada en enumerar fds es **inherentemente incompleta** en este entorno; los escenarios que la usan son UNKNOWN. Esto **NO invalida** la conclusión de que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; impide solo **acreditarlo** aquí. Es un límite de la *medición por `/proc`*, no del mecanismo de cierre.
5. **La enumeración por descriptor de directorio mantenido (R2-A)** hace explícito y estable el descriptor propio de la enumeración y permite diferenciar desapariciones externas (R2-C9), **pero NO elimina** el fantasma (R2-C8): la alternativa se demostró, no se asumió, y sus límites se documentaron.
6. **C5 se conserva (histórico):** el cierre por `arr._mmap.close()` con array vivo ⇒ SIGSEGV (3/3) sigue siendo el fallo de FEASIBILITY-D18-R1; R3 **no lo cambia**.

## 8. Hechos observados · hipótesis · UNKNOWN

- **HECHOS OBSERVADOS:**
  - Con todas las referencias liberadas + `gc.collect()`, el mmap se desmapea y su fd duplicado se cierra, sin SIGSEGV, en CPython 3.11.2 / NumPy 1.26.4 (A2–A6, B3, B4, D3, D4, R1-A1, R1-A2, R1-B1).
  - El fd propio del motor no lo cierra NumPy (C-A/C-C).
  - `fds_with_identity()` captura errores de enumeración (R2-C4/R2-C7: no propaga; inventario incompleto; controlador general no genera FAIL) y clasifica por evidencia con criterio conservador (R2-C2, R2-C3, R3-D).
  - Los escenarios A/B/C reales asignan UNKNOWN ante inventario incompleto y PASS ante inventario completo (R2-C10, contraste verificado).
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
- **Seguimiento de referencias en el motor no implementado:** R3 valida que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; no valida que el motor las rastree todas.
- **La acreditación por `/proc` es frágil:** depende de que `/proc/self/maps` sea totalmente interpretable y `/proc/self/fd` totalmente estadizable. R3-D lo reconoce explícitamente y convierte la ambigüedad en UNKNOWN_CAUSE en lugar de atribuir ERROR_PROCFS sin evidencia.
- **Mecanismo de clasificación (R3-D) — límites documentados:** puede distinguir permisos, desapariciones en FS regular, descriptores reales en procfs (fdinfo presente) y fallos de enumeración/inspección con errno típico; **no puede distinguir** entre artefacto de procfs y descriptor real cerrado para ENOENT+fdinfo ausente, que se registra como UNKNOWN_CAUSE.
- **Hashes:** los sha256 de los dos archivos modificados se calculan realmente y se entregan en el mensaje de commit y en la entrega a Cris (no se afirman aquí valores no calculados).

## 10. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2 **con rectificación final R2 y rectificación final de verificación R3**. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (C5 histórico). R2+R1+R2+R3 añaden: existe un ciclo de vida SEGURO (referencias + `gc.collect()`) que evita el SIGSEGV, **pero condicionado** a (i) liberar todas las referencias y (ii) disponer de un inventario de `/proc` completo; con referencia retenida o inventario incompleto la liberación no se acredita (UNKNOWN). Veredicto global: **UNKNOWN**.
- La decisión sobre D-18 / el mecanismo de cierre seguro de NumPy corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris. **Esta autorización no adjudica D18 como PASS ni autoriza integración en producción.**

## 11. Trazabilidad

- Padre: `66978202fb6f9211d71b6114614ae38254adac6a` (FEASIBILITY-D18-R2-R2), hijo directo de `709991589255239208340d0db6907d1cbb91609e`.
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (modificado: R3-A/B/C/D/E/F).
- Informe: `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (modificado: R3-F).
- Evidencia cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera).
- Archivos históricos D18 / D18-R1 / D18-R2 / D18-R2-R2 previos: **no modificados** (se actualiza el mismo informe D18-R2 con la rectificación R3).
- Commit hijo directo de `6697820...`: SHA en mensaje de commit; verificable vía `gh api`.
- SHA-256 de los dos archivos modificados: en el mensaje de commit y en la entrega a Cris.

## 12. Enlaces de GitHub (para auditoría de Cris)

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama de esta sesión (`arena/9a32cda8-sdv-sdi-sgm`, HEAD = padre obligatorio `6697820`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/9a32cda8-sdv-sdi-sgm
- Commit padre obligatorio `6697820`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/66978202fb6f9211d71b6114614ae38254adac6a
- Commit antecesor `7099915`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/709991589255239208340d0db6907d1cbb91609e
- `main` intacta (`b64f15ae`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b64f15ae8b28e46eef3c024dc62c85fe27c69494
- Arnés R2+R1+R2+R3 (raw): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe R2+R1+R2+R3 (raw, este archivo): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/9a32cda8-sdv-sdi-sgm/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
