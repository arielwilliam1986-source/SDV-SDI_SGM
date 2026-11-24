# FEASIBILITY-D18-R2 (6G.1) — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena.
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Relación con D-18 / R1:** D-18 permanece **FAIL**. El hallazgo **C5** (SIGSEGV al cerrar `arr._mmap` con el array vivo, reproducible 3/3) es de FEASIBILITY-D18-R1 y se **conserva como histórico e independiente**; R2 **no lo re-ejecuta ni lo oculta**. R2 investiga si existe una alternativa SEGURA de liberación que evite ese camino peligroso.
- **Veredicto global R2:** **UNKNOWN** (precedencia FAIL > UNKNOWN > PASS). 16 PASS · 0 FAIL · 3 UNKNOWN. El camino seguro **funciona** cuando se liberan TODAS las referencias + `gc.collect()`, pero **no puede garantizarse incondicionalmente** (una referencia retenida impide acreditar la liberación → UNKNOWN/fallo cerrado).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R2):** `b4eee7d5bd6620d58643a6e6627943a24687c037` (FEASIBILITY-D18-R1).
- Verificado ANTES de trabajar: local = origin = `gh api` = `b4eee7d…` CONFORME, rama `arena/f1c5739f-sdv-sdi-sgm`, árbol limpio salvo los dos archivos nuevos aún sin commit.

## 2. Commit final y archivos modificados

- **Commit de esta fase:** hijo directo de `b4eee7d…`; **exactamente 2 archivos NUEVOS** (sin modificar los archivos históricos D18 ni D18-R1, ni ningún otro); SHA completo en el mensaje de entrega (verificable vía `git`/`gh api`).
- **Archivos (exactamente los 2 autorizados, ambos nuevos):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (A) — arnés R2, **19 subpruebas** R2-A1–A6 / B1–B6 / C-A / C-B / C-C / D1–D4.
  - `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (A) — este informe.
- Evidencia JSON cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera; el arnés la regenera).

## 3. Entorno y versiones exactas

| Componente | Valor |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (`/tmp/venv_i1/bin/python`) |
| numpy | `1.26.4` |
| glibc | 2.36 |

Veredictos válidos para ESTE entorno y condiciones; **sin extrapolación** a Android/Termux ni a otras versiones de Python/NumPy. Lo aquí observado es **comportamiento en CPython 3.11.2 / NumPy 1.26.4**, no una garantía documentada de las bibliotecas (ver §9).

## 4. Comando reproducible

```
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
```

El arnés crea un directorio aislado efímero (`/tmp/feas_d18_r2_*`), registra entorno, ejecuta las 19 subpruebas y vuelca `evidence_d18_r2.json` con todos los veredictos individuales y el global.

## 5. Fixtures sintéticos

- Archivos binarios de 16384 bytes (`\x00`) con nombre único por subprueba; variantes con byte sembrado (`0x07`, `0x09`, `0x0B`) para las alternativas A/B/C. Cero audio real; cero red; cero archivos del proyecto.

## 6. Método (helpers del arnés)

- `parse_maps()`: lee `/proc/self/maps`, separa `addr/perms/offset/dev(dev:ino)/ino/pathname`; descarta y reporta líneas no interpretables.
- `identity_of(st)`: `(os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)` — **nunca usa la ruta**.
- `entries_for_identity(entries, st)`: TODAS las entradas con esa identidad (no sólo la primera).
- `count_maps(st)` / `fds_with_identity(st)`: recuento de entradas por identidad y lista de `/proc/self/fd/N` con esa identidad (distingue fd del llamante del fd duplicado interno de `mmap.mmap`).
- `OpenRecorder`: reemplaza `builtins.open` para registrar la(s) ruta(s) que NumPy abre a nivel Python (magic-link en C-A, ruta real en C-B, nada en C-C). No captura `os.open` ni el `dup()` interno de `mmap.mmap`.
- **Liberación segura:** en R2 **no se invoca `arr._mmap.close()`**. La secuencia es `del <referencias>; gc.collect()`, dejando que el **finalizador del `mmap`** cierre su fd duplicado y desmapee. Esto es lo que evita el SIGSEGV de C5.

## 7. Resultados individuales por sección

### R2-A — Liberación de referencias

| ID | Título | Procedimiento | Observado | Veredicto |
|---|---|---|---|---|
| A1 | Raíz sin vistas | `del arr; gc` | vivo maps=1 fds=[dup]; tras liberar maps=0 fds=[] | PASS |
| A2 | Raíz + slice | liberar raíz (slice vivo) → maps persiste; luego slice | vivo=1; del raíz=1; del slice=0 | PASS |
| A3 | Vistas encadenadas | arr→v1→v2; liberar en cadena | vivo=1; del raíz=1; del v1=1; del v2=0 | PASS |
| A4 | Contenedores | array+vista en lista; vaciar lista | vivo=1; del var=1; del cont=0 | PASS |
| A5 | Referencia exportada | ref a lista de módulo; liberar luego | vivo=1; del local=1; del export=0 | PASS |
| A6 | Liberación progresiva | raíz+vista+contenedor, una a una | secuencia [(inicial,1),(del raíz,1),(del vista,1),(del cont,0)] | PASS |

**Conclusión A:** la liberación por referencias + `gc.collect()` desmapea correctamente y cierra el fd duplicado del mmap; el mapeo desaparece exactamente cuando la **última** referencia viva se libera.

### R2-B — Cierre seguro (sin `_mmap.close()`)

| ID | Título | Procedimiento | Observado | Veredicto |
|---|---|---|---|---|
| B1 | Secuencia segura, raíz | soltar ref + gc; verificar maps y fds | vivo maps=1 fds=[dup]; tras maps=0 fds=[] | PASS |
| B2 | Con vistas | soltar vistas+raíz + gc | vivo=1; tras maps=0 fds=[] | PASS |
| B3 | Recolección controlada | doble `gc.collect()` | vivo=1; tras=0 | PASS |
| B4 | Todas las entradas por (dev,ino) | `entries_for_identity` antes/después | antes=1 después=0 | PASS |
| B5 | Fds residuales y propiedad (ruta) | tras liberar, `fds_with_identity` | vivos=[dup]; residuales=[] | PASS |
| B6 | Referencia externa viva | motor libera lo suyo; ref externa queda | vivo=1; tras liberar motor=1 (no desaparece) | **UNKNOWN** |

**Conclusión B:** la secuencia segura (referencias + `gc`) libera el mapeo y cierra el fd duplicado del mmap sin SIGSEGV (evita C5). **Pero** si una referencia externa permanece viva, el mapeo NO desaparece y la liberación no puede acreditse → UNKNOWN/fallo cerrado (B6).

### R2-C — Alternativas A/B/C (cierre seguro, diferenciando fds)

| ID | Título | Observado (fds) | Veredicto |
|---|---|---|---|
| C-A | fd motor + magic-link | NumPy abrió `['/proc/self/fd/3']`; vivos=[3,6]; tras liberar maps=0 fds=[3] (fd motor 3 abierto); fd duplicado 6 cerrado | PASS |
| C-B | NumPy por ruta | NumPy abrió `['…/cb.bin']`; vivos=[5] (dup); tras liberar maps=0 residuales=[] | PASS |
| C-C | fileobj entregado | NumPy abrió `[]`; vivos=[3,5] (fileobj 3 + dup 5); tras liberar maps=0 fds=[3] (fileobj abierto) | PASS |

**Conclusión C — diferenciación de descriptores (observado, no inferido):**
- **A:** fd del motor = 3 (lo abre y debe cerrar el motor); NumPy abre el magic-link vía `builtins.open`; `mmap.mmap` crea un fd duplicado = 6. Tras liberar el array + `gc`, maps=0 y el dup 6 se cierra; el fd 3 del motor **sigue abierto** (NumPy no lo toca).
- **B:** el único fd con la identidad es el dup (5) de NumPy; tras liberar, maps=0 y residuales=[] (el motor no tiene fd_mm que cerrar).
- **C:** fd del fileobj = 3 (del motor) + dup 5; tras liberar, maps=0, dup 5 cerrado, fileobj 3 abierto (del motor). NumPy no abrió nada (`nullcontext`).
- En las tres, el **único** recurso que cierra el camino seguro es el fd duplicado interno del objeto `mmap`, vía su finalizador. **No se atribuye al motor ningún fd que pertenezca a NumPy.**

### R2-D — Fallos y excepciones

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| D1 | Liberación incompleta (vista retenida) | vivo=1; tras liberar solo raíz=1 (vista viva) | **UNKNOWN** |
| D2 | Referencia retenida impide acreditar | vivo=1; tras secuencia segura (retenida viva)=1 | **UNKNOWN** |
| D3 | Flush no bloquea la liberación | flush normal persiste; liberación por ref+gc sin flush → maps=0 | PASS |
| D4 | Cierre seguro sin errores | `del arr; gc` → sin excepción, maps=0; `_mmap.close()` forzado NO usado | PASS |

**Conclusión D:** las variantes de fallo (vista/contenedor/referencia retenida) **no usan `_mmap.close()` forzado** para superar la referencia activa; el mapeo simplemente permanece vivo y la liberación termina en UNKNOWN/fallo cerrado. El flush no es prerrequisito del unmapping y un error de flush (ValueError «mmap closed or invalid» sobre mapping ya cerrado, observado en sonda previa) no bloquea la liberación por `gc`. El camino seguro (finalizador) no lanza excepción.

## 8. Conteos y veredicto global

```
Conteos: PASS=16 FAIL=0 UNKNOWN=3   (19 subpruebas)
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
```

La precedencia es **FAIL > UNKNOWN > PASS**. No hay FAIL en R2 (el camino peligroso `_mmap.close()` está explícitamente excluido y no se ejecuta). Hay 3 UNKNOWN (B6, D1, D2): escenarios donde una referencia retenida impide acreditar la desaparición del mapeo. Por tanto el veredicto global es **UNKNOWN**: el ciclo de vida seguro **es viable condicionalmente** (cuando se liberan TODAS las referencias), pero **no incondicionalmente garantizable** en esta validación aislada.

## 9. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4):** soltar el array raíz, todas las vistas/slices, contenedores y referencias exportadas, y luego `gc.collect()`, finaliza el `mmap` (su `__del__`/`__dealloc__` cierra el fd duplicado y desmapea). Evita el SIGSEGV de C5. Esto es **observación de comportamiento**, coherente con la semántica de que el `ndarray` mantiene al `mmap` como `base`; NO es una garantía documentada de NumPy que cubra todos los modos/versiones.

2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** en A/B/C el único fd que cierra el camino seguro es el dup interno del objeto `mmap`. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor. B no tiene fd_mm. Esto afina B.7.1/B.7.2 del diseño v5: la «liberación del mapeo NumPy» = liberar referencias + `gc`, y el cierre del fd del motor queda fuera de esa responsabilidad de NumPy.

3. **Condición de seguridad: liberar TODAS las referencias (hipótesis de diseño, no demons. incondicional):** cualquier referencia olvidada (vista en contenedor, variable exportada, referencia externa) mantiene el mapeo vivo. La liberación **no puede acreditse** en ese caso → UNKNOWN/fallo cerrado. Por tanto R2 **no autoriza por sí mismo EXIT_OK** ni un «cierre efectivo garantizado»: exige que el motor rastree y libere CADA referencia. Esto es una **hipótesis de diseño** pendiente de mecanismo de seguimiento de referencias en el motor.

4. **C5 se conserva (histórico):** el cierre por `arr._mmap.close()` con array vivo ⇒ SIGSEGV (3/3) sigue siendo el fallo de FEASIBILITY-D18-R1; R2 demuestra la alternativa segura pero **no cambia** ese resultado.

## 10. Limitaciones y escenarios no reproducidos

- **Entorno único:** Linux 6.1.158+ x86_64, glibc 2.36, Python 3.11.2, NumPy 1.26.4, euid 1001. **No extrapolable** a Android/Termux, a otros kernels/versiones ni a `mmap.ACCESS_COPY`/`MAP_PRIVATE` con page-cache distinto.
- **Fallo de I/O de flush no forzado:** en tmpfs no se pudo provocar un fallo real de `flush` (la escritura siempre succeed); se documenta el camino de error (ValueError sobre mapping ya cerrado, de sonda previa) y que es independiente de la liberación por `gc`. No se afirma un fallo de flush que no ocurrió.
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** validación de mecanismos, no de integración. Las conclusiones son sobre `mmap`/`numpy`/procfs en CPython, no sobre el código de producción.
- **Seguimiento de referencias en el motor no implementado:** R2 valida que el camino seguro funciona *si* se liberan todas las referencias; no valida que el motor las rastree todas (eso es responsabilidad de diseño/implementación futura, fuera de fase preintegración).
- **Hashes:** los sha256 de los dos archivos nuevos se calculan realmente y se entregan en el mensaje de entrega (no se afirman aquí valores no calculados).

## 11. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (C5 histórico). R2 añade: **existe un ciclo de vida SEGURO** (referencias + `gc.collect()`) que evita el SIGSEGV, **pero condicionado** a liberar todas las referencias; con referencia retenida la liberación no se acredita (UNKNOWN). Veredicto global R2: **UNKNOWN**.
- La decisión sobre D-18 / el mecanismo de cierre seguro de NumPy corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris.

## 12. Trazabilidad

- Padre: `b4eee7d5bd6620d58643a6e6627943a24687c037` (FEASIBILITY-D18-R1).
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` (nuevo).
- Informe: `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (nuevo, este archivo).
- Evidencia cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera).
- Archivos históricos D18 / D18-R1: **no modificados** en esta fase.
- Commit hijo directo de `b4eee7d…`: SHA en mensaje de entrega; verificable vía `gh api`.
