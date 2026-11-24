# FEASIBILITY-D18-R2 + R1 — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP (corrección metodológica del arnés)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena (sesión `arena/91ec2615-sdv-sdi-sgm`).
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Alcance de ESTA entrega (adjudicación de Cris, P1–P3):** **corrección metodológica del arnés R2** únicamente (R1-A `count_maps`, R1-B `fds_with_identity`, R1-C propagación de UNKNOWN, R1-D informe). No se amplía el alcance a referencias retenidas ni a nuevas estrategias de liberación.
- **Relación con D-18 / R1:** D-18 permanece **FAIL**. El hallazgo **C5** (SIGSEGV al cerrar `arr._mmap` con el array vivo, reproducible 3/3) es de FEASIBILITY-D18-R1 y se **conserva como histórico e independiente**; R2/R1 **no lo re-ejecutan ni lo ocultan**. R1 investiga si el arnés mide lo que dice medir.
- **Veredicto global R2+R1:** **UNKNOWN** (precedencia FAIL > UNKNOWN > PASS). 12 PASS · 0 FAIL · 13 UNKNOWN (25 subpruebas). El camino seguro **funciona** cuando se liberan TODAS las referencias + `gc.collect()`, pero **no puede garantizarse incondicionalmente** (una referencia retenida, o —novedad R1— un inventario de `/proc` incompleto, impiden acreditar la liberación → UNKNOWN/fallo cerrado).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R2 + R1):** `f206980f9279e5793756496b2ceb563d92859b30` (FEASIBILITY-D18-R2, hijo directo de `b4eee7d…`).
- Verificado ANTES de trabajar: local = origin = `gh api` = `f206980…` CONFORME, rama `arena/91ec2615-sdv-sdi-sgm` (hija de `arena/f1c5739f-sdv-sdi-sgm`, situada en el padre obligatorio), árbol limpio salvo los dos archivos nuevos aún sin commit.
- **Nuevo commit:** hijo directo de `f206980…`; **exactamente 2 archivos modificados** (los dos autorizados). SHA completo en el mensaje de commit (verificable vía `git`/`gh api`).
- `arena/f1c5739f-sdv-sdi-sgm` **permanece intacta** (no force push, no reconstrucción, no cherry-pick, no traslado).

## 2. Archivos modificados (exactamente los 2 autorizados, ambos existentes)

| Archivo | Rol | Cambio |
|---|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` | Arnés R2 + R1 (25 subpruebas: 19 R2 + 6 R1 controladas) | Corrección metodológica R1-A/B/C; sin nuevos archivos |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` | Este informe | Actualiza método, recuentos, evidencias, procedimientos y limitaciones (R1-D) |

Evidencia JSON cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera; el arnés la regenera). SHA-256 de los dos archivos en el mensaje de commit y en la entrega a Cris (no autocalculados dentro del propio informe para evitar autorreferencia).

## 3. Entorno y versiones exactas

| Componente | Valor |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (venv efímero con NumPy 1.26.4) |
| numpy | `1.26.4` |
| glibc | 2.36 |

Veredictos válidos para ESTE entorno y condiciones; **sin extrapolación** a Android/Termux ni a otras versiones de Python/NumPy. Lo aquí observado es **comportamiento en CPython 3.11.2 / NumPy 1.26.4**, no una garantía documentada de las bibliotecas.

## 4. Corrección metodológica R1 (lo que cambió y por qué)

El arnés R2 original **ocultaba dos fuentes de incertidumbre** y aun así declaraba PASS. R1 las hace visibles y las convierte en UNKNOWN, nunca en PASS silencioso.

### R1-A — `count_maps()` / `parse_maps()` (lectura de `/proc/self/maps`)
- **Antes:** las líneas no interpretables se descartaban (`unparseable.append; continue`) y el recuento se devolvía igualmente, como si la lectura fuera total.
- **Ahora:** `parse_maps()` devuelve un `MapsRead` con `status` de tres estados:
  - `complete` — se leyó todo y **todas** las líneas se interpretaron.
  - `incomplete` — se leyó pero hubo líneas no interpretables (no se descartan: se registran).
  - `unreadable` — no se pudo abrir/leer el origen (error de E/S).
- Reglas de acreditación (R1-A):
  - **Líneas no interpretables, errores o lectura ilegible → UNKNOWN.**
  - **Solo se declara cero mappings después de una lectura `complete`.**
  - **FAIL únicamente cuando una lectura `complete` contradice lo esperado por el escenario.**
- En este entorno `/proc/self/maps` es totalmente interpretable, así que `status == complete` y los recuentos por identidad son fiables (los escenarios que solo dependen de maps siguen siendo PASS/UNKNOWN como en R2).

### R1-B — `fds_with_identity()` (inventario de `/proc/self/fd`)
- **Antes:** `except OSError: continue` — los errores de `stat` sobre entradas individuales se **ignoraban silenciosamente**, y el recuento se devolvía como si el inventario fuera completo.
- **Ahora:** `fds_with_identity()` devuelve un `FdInventory` con `matched`, `errors` y `complete`:
  - Cualquier `OSError` al estatizar una entrada (descriptor que **desapareció durante el recorrido**, **inaccesible**, o **error de procfs**) se **registra** y fuerza `complete = False`.
  - **Inventario incompleto → UNKNOWN.**
  - **Nunca se declara PASS a partir de un inventario incompleto.**
- **Hallazgo empírico (este entorno):** `/proc/self/fd` contiene al menos una entrada —`fd 3`— que lanza `FileNotFoundError` al `os.stat` (symlink fantasma; `readlink` también falla). Por tanto el inventario de fds es **genuinamente incompleto** aquí y los escenarios que dependen de él (A1, B1, B2, B5, C-A, C-B, C-C) pasan a **UNKNOWN**. El arnés R2 original ocultaba exactamente este error y declaraba PASS; R1-B lo expone. En un entorno donde `/proc/self/fd` sea totalmente estadizable, esos mismos escenarios recuperarían su veredicto de cierre (la **lógica de acreditación no cambió**, solo el tratamiento del error).

### R1-C — Propagación
- Todo escenario A/B/C cuyo acreditamiento dependa de una lectura `incomplete`/`unreadable` o de un inventario `complete = False` pasa a **UNKNOWN**.
- **Ningún escenario declara PASS si su acreditación depende de una lectura incompleta.**

### R1-D — Informe y límites
- C5 se conserva como **FAIL histórico** (no se re-ejecuta).
- **No** se invoca `_mmap.close()` forzado con referencias vivas en ningún punto.
- **No** se afirma que `gc.collect()` sea una garantía universal (ver §9).
- Hechos observados, hipótesis y UNKNOWN se separan explícitamente (§8).

## 5. Resultados individuales (25 subpruebas)

### R2-A — Liberación de referencias

| ID | Título | maps vivo→muerto | Veredicto R1 |
|---|---|---|---|
| A1 | Raíz sin vistas | 1→0 (maps); fd vivo→[] | **UNKNOWN** (inventario fd incompleto, R1-B) |
| A2 | Raíz + slice | 1→1→0 | PASS (solo maps, complete) |
| A3 | Vistas encadenadas | 1→1→1→0 | PASS (solo maps, complete) |
| A4 | Contenedores | 1→1→0 | PASS (solo maps, complete) |
| A5 | Referencia exportada | 1→1→0 | PASS (solo maps, complete) |
| A6 | Liberación progresiva | 1→1→1→0 | PASS (solo maps, complete) |

**Conclusión A (maps):** la liberación por referencias + `gc.collect()` desmapea correctamente y cierra el fd duplicado del mmap; el mapeo desaparece exactamente cuando la **última** referencia viva se libera. (Inalterado respecto a R2; la única novedad es A1, que ahora es UNKNOWN por el inventario fd, no por maps.)

### R2-B — Cierre seguro (sin `_mmap.close()`)

| ID | Título | maps | Veredicto R1 |
|---|---|---|---|
| B1 | Secuencia segura, raíz | 1→0 | **UNKNOWN** (fd inventario incompleto) |
| B2 | Con vistas | 1→0 | **UNKNOWN** (fd inventario incompleto) |
| B3 | Recolección controlada | 1→0 | PASS (solo maps) |
| B4 | Todas las entradas por (dev,ino) | 1→0 | PASS (solo maps) |
| B5 | Fds residuales y propiedad (ruta) | fd vivo→[] | **UNKNOWN** (fd inventario incompleto) |
| B6 | Referencia externa viva | maps persiste | **UNKNOWN** (referencia retenida, por diseño) |

**Conclusión B:** la secuencia segura (referencias + `gc`) libera el mapeo y cierra el fd duplicado del mmap sin SIGSEGV (evita C5). **Pero** si el inventario de fds es incompleto —bien por una referencia externa retenida (B6), bien por una entrada de `/proc/self/fd` no estadizable en este entorno (B1/B2/B5)— la liberación **no puede acreditse** → UNKNOWN/fallo cerrado.

### R2-C — Alternativas A/B/C (cierre seguro, diferenciando fds)

| ID | Título | Observado | Veredicto R1 |
|---|---|---|---|
| C-A | fd motor + magic-link | fd motor abierto; dup cerrado | **UNKNOWN** (fd inventario incompleto) |
| C-B | NumPy por ruta | solo dup de NumPy | **UNKNOWN** (fd inventario incompleto) |
| C-C | fileobj entregado | fd fileobj abierto; dup cerrado | **UNKNOWN** (fd inventario incompleto) |

**Conclusión C (observado, no inferido):** en A/B/C el **único** recurso que cierra el camino seguro es el fd duplicado interno del objeto `mmap`, vía su finalizador. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor; B no tiene fd_mm. **Novedad R1:** estas tres diferenciaciones ya no pueden acreditse como PASS en este entorno porque el inventario de `/proc/self/fd` es incompleto (fd 3 fantasma). La *lógica* de diferenciación sigue siendo válida; lo que cambia es la **acreditación** del inventario de fds.

### R2-D — Fallos y excepciones

| ID | Título | Observado | Veredicto R1 |
|---|---|---|---|
| D1 | Liberación incompleta (vista retenida) | maps persiste | **UNKNOWN** |
| D2 | Referencia retenida impide acreditar | maps persiste | **UNKNOWN** |
| D3 | Flush no bloquea la liberación | flush persiste; sin flush→maps=0 | PASS |
| D4 | Cierre seguro sin errores | `del arr; gc` → sin excepción, maps=0 | PASS |

**Conclusión D:** las variantes de fallo (vista/contenedor/referencia retenida) **no usan `_mmap.close()` forzado** para superar la referencia activa; el mapeo permanece vivo y la liberación termina en UNKNOWN/fallo cerrado. El flush no es prerrequisito del unmapping y un error de flush (ValueError «mmap closed or invalid» sobre mapping ya cerrado, observado en sonda previa) no bloquea la liberación por `gc`. El camino seguro (finalizador) no lanza excepción.

### R1 controladas (obligatorias, R1-A/R1-B)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R1-A1 | Lectura COMPLETA con coincidencia | status=complete; recuento=1 | PASS |
| R1-A2 | Lectura COMPLETA sin coincidencia | status=complete; recuento=0 (declarado tras lectura completa) | PASS |
| R1-A3 | Coincidencia + líneas no interpretables | status=incomplete (3 no interpretables) | **UNKNOWN** |
| R1-A4 | `/proc/self/maps` no disponible/ilegible | status=unreadable (OSError) | **UNKNOWN** |
| R1-B1 | Inventario COMPLETO de /proc/self/fd | complete=True; matched=[3]; errors=[] | PASS |
| R1-B2 | Inventario INCOMPLETO (/proc/self/fd con error) | complete=False; symlink roto → error registrado | **UNKNOWN** |

Estas seis pruebas **demuestran** el mecanismo R1-A/R1-B: lectura/inventario completos permiten acreditar (PASS/recuento 0 legítimo); cualquier incompletitud fuerza UNKNOWN y jamás PASS.

## 6. Conteos y veredicto global

```
Subpruebas: 25 (19 R2 + 6 R1 controladas)
Conteos:    PASS=12 FAIL=0 UNKNOWN=13
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
```

Desglose de PASS (12): A2,A3,A4,A5,A6 · B3,B4 · D3,D4 · R1-A1,R1-A2 · R1-B1.
Desglose de UNKNOWN (13): A1,B1,B2,B5,B6 · C-A,C-B,C-C · D1,D2 · R1-A3,R1-A4 · R1-B2.

**Por qué cambió el global respecto a R2 (16 PASS → 12 PASS):** la lógica de ciclo de vida es idéntica; los 7 escenarios que pasaron de PASS→UNKNOWN (A1,B1,B2,B5,C-A,C-B,C-C) lo hicieron **exclusivamente** por la incompletitud del inventario de `/proc/self/fd` en este entorno (fd 3 fantasma). El arnés R2 original enmascaraba ese error con `except OSError: continue` y declaraba PASS; R1-B lo expone como UNKNOWN. Esto es, precisamente, la corrección metodológica solicitada.

## 7. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4):** soltar el array raíz, todas las vistas/slices, contenedores y referencias exportadas, y luego `gc.collect()`, finaliza el `mmap` (su `__del__`/`__dealloc__` cierra el fd duplicado y desmapea). Evita el SIGSEGV de C5. **Observación de comportamiento**, coherente con la semántica de que el `ndarray` mantiene al `mmap` como `base`; **NO es una garantía documentada de NumPy** que cubra todos los modos/versiones.
2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** en A/B/C el único fd que cierra el camino seguro es el dup interno del objeto `mmap`. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor. B no tiene fd_mm. Esto afina B.7.1/B.7.2 del diseño v5.
3. **Condición de seguridad: liberar TODAS las referencias (hipótesis de diseño, no dem. incondicional):** cualquier referencia olvidada mantiene el mapeo vivo → UNKNOWN/fallo cerrado. R1 **no autoriza por sí mismo EXIT_OK** ni un «cierre efectivo garantizado» en producción: exige que el motor rastree y libere CADA referencia.
4. **Novedad R1 — el inventario de `/proc` puede ser incompleto (hecho observado):** en este entorno `/proc/self/fd/3` lanza `FileNotFoundError` al `stat`. Por tanto la acreditación basada en enumerar fds es **inherentemente incompleta** aquí; los escenarios que la usan son UNKNOWN. Esto NO invalida la conclusión de que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; simplemente impide **acreditarlo** en entornos con fds no estadizables. Es un límite de la *medición por `/proc`*, no del mecanismo de cierre.
5. **C5 se conserva (histórico):** el cierre por `arr._mmap.close()` con array vivo ⇒ SIGSEGV (3/3) sigue siendo el fallo de FEASIBILITY-D18-R1; R1 demuestra la alternativa segura pero **no cambia** ese resultado.

## 8. Hechos observados · hipótesis · UNKNOWN

- **HECHO OBSERVADO:** con todas las referencias liberadas + `gc.collect()`, el mmap se desmapea y su fd duplicado se cierra, sin SIGSEGV, en CPython 3.11.2 / NumPy 1.26.4 (A2–A6, B3, B4, D3, D4, R1-A1, R1-A2, R1-B1). El fd propio del motor no lo cierra NumPy (C-A/C-C). `/proc/self/fd/3` es no estadizable en este entorno (diagnóstico directo).
- **HIPÓTESIS DE DISEÑO:** para que el cierre sea efectivo en producción, el motor debe rastrear y liberar CADA referencia al mmap, y contar con un inventario de fds completo; de lo contrario la liberación no es acreditable. Pendiente de mecanismo de seguimiento de referencias en el motor (fuera de fase preintegración).
- **UNKNOWN:** (a) si queda una referencia retenida, la liberación no se acredita (B6, D1, D2); (b) si el inventario de `/proc/self/fd` es incompleto (entrada no estadizable, p.ej. fd 3 en este entorno), la acreditación por fds no es posible (A1, B1, B2, B5, C-A, C-B, C-C); (c) lectura de maps con líneas no interpretables o ilegible (R1-A3, R1-A4); (d) inventario de fds con error (R1-B2).

## 9. Límites y lo que NO se afirma

- **`gc.collect()` NO es una garantía universal.** Es observación de CPython 3.11.2 / NumPy 1.26.4 en este entorno. No se extrapola a otras versiones, a Android/Termux, ni a `mmap.ACCESS_COPY`/`MAP_PRIVATE` con page-cache distinto.
- **Entorno único:** Linux 6.1.158+ x86_64, glibc 2.36, Python 3.11.2, NumPy 1.26.4, euid 1001.
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** validación de mecanismos, no de integración. Las conclusiones son sobre `mmap`/`numpy`/procfs en CPython, no sobre el código de producción.
- **Seguimiento de referencias en el motor no implementado:** R1 valida que el camino seguro funciona *si* se liberan todas las referencias y *si* el inventario de fds es completo; no valida que el motor las rastree todas (responsabilidad de diseño/implementación futura, fuera de fase preintegración).
- **La acreditación por `/proc` es frágil:** depende de que `/proc/self/maps` sea totalmente interpretable y `/proc/self/fd` totalmente estadizable. R1-B lo reconoce explícitamente y convierte cualquier incompletitud en UNKNOWN en lugar de PASS silencioso.
- **Hashes:** los sha256 de los dos archivos modificados se calculan realmente y se entregan en el mensaje de commit y en la entrega a Cris (no se afirman aquí valores no calculados).

## 10. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2 **corregida metodológicamente (R1)**. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (C5 histórico). R2+R1 añaden: existe un ciclo de vida SEGURO (referencias + `gc.collect()`) que evita el SIGSEGV, **pero condicionado** a (i) liberar todas las referencias y (ii) disponer de un inventario de `/proc` completo; con referencia retenida o inventario incompleto la liberación no se acredita (UNKNOWN). Veredicto global R2+R1: **UNKNOWN**.
- La decisión sobre D-18 / el mecanismo de cierre seguro de NumPy corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris. **La aceptación de esta autorización no implica que D18-R2 esté adjudicado como PASS: el veredicto sigue siendo UNKNOWN hasta la auditoría independiente de Cris.**

## 11. Trazabilidad

- Padre: `f206980f9279e5793756496b2ceb563d92859b30` (FEASIBILITY-D18-R2).
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (modificado: R1-A/B/C).
- Informe: `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (modificado: R1-D).
- Evidencia cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera).
- Archivos históricos D18 / D18-R1 / D18-R2 previo: **no modificados** en esta fase (se actualiza el mismo informe D18-R2 con la corrección R1).
- Commit hijo directo de `f206980…`: SHA en mensaje de commit; verificable vía `gh api`.
- SHA-256 de los dos archivos modificados: en el mensaje de commit y en la entrega a Cris.

## 12. Enlaces de GitHub (para auditoría de Cris)

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama de esta sesión (`arena/91ec2615-sdv-sdi-sgm`, HEAD = padre obligatorio `f206980`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/91ec2615-sdv-sdi-sgm
- Rama padre de referencia intacta (`arena/f1c5739f-sdv-sdi-sgm`, HEAD `f206980`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/f1c5739f-sdv-sdi-sgm
- Commit padre obligatorio `f206980`: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/f206980f9279e5793756496b2ceb563d92859b30
- `main` intacta (`b64f15ae`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b64f15ae8b28e46eef3c024dc62c85fe27c69494
- Arnés R2+R1 (raw): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/91ec2615-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe R2+R1 (raw, este archivo): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/91ec2615-sdv-sdi-sgm/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
