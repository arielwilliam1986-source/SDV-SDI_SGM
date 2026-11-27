# AUDITORÍA DE RESOLUBILIDAD DE UNKNOWN — R6-R4

**Fase:** auditoría técnica, documental y de solo lectura.
**Fecha:** 2026-11-25 (UTC).
**Alcance:** los nueve resultados `UNKNOWN` de D18-R2-R6-R4.

> Este documento **no modifica** la batería, **no ejecuta** pruebas, **no altera** veredictos y **no adjudica** nada por interpretación. Las categorías que propone son conclusiones de auditoría, no veredictos nuevos.

---

## 1. Identificación del material auditado

| Elemento | Valor verificado |
|---|---|
| Repositorio | `https://github.com/arielwilliam1986-source/SDV-SDI_SGM` |
| Rama de referencia | `arena/a2d9ac2e-sdv-sdi-sgm` |
| HEAD auditado | `0ae2c10c472e2e9941320fa1dd2727f1a044701c` |
| Commit funcional R6-R4 | `bbc1aab50ab1487f81c03697a7f10390088302e5` |
| Padre del commit funcional | `c80f7f11651e08267a4929527b3035ae40c39e13` (R6-R3) |
| Cadena anterior | `8487d9cdd54c9f5e584cec5b1a788c891f00aed5` (R6-R1) → `779485acf4b9116a2f1e055f320382beb2c51799` (R6) → `ac82b6c3cc46f6f5202c1a14c4aa70c7a67c87e2` (R5) |
| Arnés auditado | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` — 3171 líneas, 150218 bytes, **sha256 `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18`** |
| Informe de evidencia | `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` — **sha256 `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db`** |
| Arnés histórico D18-R1 (fuente cruzada) | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_mmap_6g1.py` — **sha256 `1744aa521ed79a0622f484b188afec7194ba6e96e61e89f0b9132ff3dc148acc`** |
| Informe histórico D18-R1 | `INFORME_FEASIBILITY_D18_MMAP_6G1.md` |

Los dos `sha256` del arnés y del informe coinciden exactamente con los blobs del commit `0ae2c10` (`git show 0ae2c10:<ruta>`), es decir, lo auditado es lo publicado.

### 1.1 Ubicación exacta de las implementaciones (verificada por AST, `python -B`, sin ejecutar el arnés)

| Símbolo | Línea | Líneas |
|---|---|---|
| `parse_maps()` | 317 | 38 |
| `_is_procfs_fd_dir()` | 378 | 6 |
| `_fdinfo_probe()` | 386 | 27 |
| `_classify_fd_error()` | 415 | 46 |
| `_supports_anchored_scandir()` | 498 | 9 |
| `fds_with_identity()` | 509 | 150 |
| `test_b6()` (R2-B6) | 1031 | 29 |
| `test_d1()` (R2-D1) | 1194 | 25 |
| `test_d2()` (R2-D2) | 1221 | 25 |
| `test_r2c_disappeared()` (R2-C2) | 1338 | 105 |
| `test_r2c_inaccessible()` (R2-C3) | 1445 | 35 |
| `test_r2c_procfs_inspect_error()` (R2-C5) | 1512 | 60 |
| `test_r1a_unparseable()` (R1-A3) | 2775 | 22 |
| `test_r1a_unreadable()` (R1-A4) | 2799 | 14 |
| `test_r1b_incomplete()` (R1-B2) | 2836 | 27 |

### 1.2 Estado de evidencia primaria

El arnés escribe su evidencia en `EVIDENCE_DIR = "/tmp/feas_d18_r2_evidence"` (línea 227) como `evidence_d18_r2.json`, y **no** versiona ese archivo. En esta sesión ese directorio **no existe** (`/tmp` no persiste entre sandboxes).

Consecuencia para la auditoría: la evidencia primaria disponible es **el registro textual del informe §6** (tablas de resultados con los campos `observed`) y el **código fuente** que produjo esos campos. No hay JSON crudo versionado de R6-R3/R6-R4, ni de R6-R1, ni de R2/R3/R4/R5. Esto se registra como limitación, no se compensa con inferencias.

---

## 2. Hallazgo transversal previo al análisis (importante)

**La evidencia auxiliar "Probe T1/T2 independiente: 3/3 PASS" no existe en el repositorio.**

Búsquedas realizadas sobre el árbol completo, en todos los formatos (`*.md`, `*.py`, `*.json`, `*.txt`, `*.csv`):

| Búsqueda | Resultado |
|---|---|
| `grep -rn "[Pp]robe" INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md INFORME_FEASIBILITY_D18_MMAP_6G1.md` | 0 coincidencias |
| `grep -rn "\bT1\b" \|\| "\bT2\b" --include="*.md" .` | Solo coincidencias en `INFORME_CORRECCIONES_AUDITORIA_6G1.md`, `INFORME_H2_6G1.md`, `INFORME_H2_R_6G1.md`, `INFORME_PARA_CHATGPT_ETAPA_6G1.md` |
| `grep -rn "3/3 PASS" --include="*.md" .` | 0 coincidencias |
| `grep -rn "vivo=" --include="*.md" --include="*.json" --include="*.txt" .` | 0 coincidencias |

Las `T1/T2` que sí existen en el repositorio pertenecen a la **etapa 6G.1 de MixHandle/`lectura_segura_6g1.py`** (inyector `scripts/inyeccion_6g1/sitecustomize.py`, "T1 validado→FIFO", "T2 gemelo byte a byte con distinto inodo"). Son **ajenas** a D18-R2: no abren `np.memmap`, no cuentan mappings en `/proc/self/maps` y no tienen relación con retención de referencias.

**Conclusión:** no puede usarse el "Probe T1/T2" como evidencia de soporte para el Grupo A en esta auditoría. Tratarlo como evidencia existente sería una afirmación no verificable. El Grupo A se audita **exclusivamente** con el código y con las tablas del informe.

Las tres afirmaciones que el encargo atribuye a ese probe sí tienen respaldo verificable, pero por **otra vía** (ver §3.3): A2/A3/A5/A6 y B2 prueban retención con referencias vivas y liberación tras soltarlas, sin cierre forzado.

---

## 3. Grupo A — Retención de memoria

### 3.1 Criterios originales (leídos del código, no inferidos)

Las tres pruebas comparten la misma estructura de adjudicación:

```python
verdict = "UNKNOWN" if not reads_complete else ("UNKNOWN" if ok_release else "FAIL")
```

| ID | `ok_release` | Lectura del criterio |
|---|---|---|
| R2-B6 | `kept_maps == 1` | Tras `del arr; gc.collect()` con referencia externa viva, se exige que **siga existiendo el mapping**. |
| R2-D1 | `kept_maps == 1` | Tras `del arr; gc.collect()` con vista retenida, se exige que **siga existiendo el mapping**. |
| R2-D2 | `kept_maps == 1` | Tras `del arr; gc.collect()` con referencia retenida, se exige que **siga existiendo el mapping**. |

Es decir: en los tres casos, la condición evaluada (`kept_maps == 1`, el mapping **persiste**) es exactamente el comportamiento **esperado y correcto** del escenario. El veredicto se fija en `UNKNOWN` **por construcción**, tanto si se cumple como si no.

Esto no es un defecto: es deliberado y está documentado en el campo `rationale` de cada registro — "no se acredita la liberación", "el resultado no puede ser PASS ni autorizar EXIT_OK", "el escenario termina en UNKNOWN/fallo cerrado, no en PASS".

### 3.2 Verificación por AST de que no hay cierre forzado

Se inspeccionó el AST de `test_b6`, `test_d1`, `test_d2` buscando llamadas reales a `.close()`:

```
Llamadas .close() dentro de B6/D1/D2 (código, no texto): NINGUNA
test_b6: menciones a "_mmap.close" en literales de cadena = 1 (documentan la prohibición)
test_d1: menciones a "_mmap.close" en literales de cadena = 1 (documentan la prohibición)
test_d2: menciones a "_mmap.close" en literales de cadena = 1 (documentan la prohibición)
```

Las tres únicas apariciones de `_mmap.close` en esas funciones son **cadenas de texto** que declaran la prohibición de usarlo. No hay invocación.

### 3.3 ¿La evidencia disponible responde a la misma pregunta?

| Afirmación necesaria | Evidencia existente | ¿Responde a la misma pregunta? |
|---|---|---|
| "Cada mapa permanece mientras existe una referencia viva" | `R2-A2` (raíz + slice: `1→1→0`), `R2-A3` (vistas encadenadas: `1→1→1→0`), `R2-A4`, `R2-A5`, `R2-A6` — todos **PASS** | **Sí, parcialmente.** Demuestran que el mapping sigue mientras hay referencias y desaparece al soltarlas. Pero A2/A3/A5 son escenarios donde la referencia se libera *dentro* de la prueba; no acreditan el caso "referencia que sobrevive al final de la prueba". |
| "Cada mapa desaparece naturalmente tras liberar la última referencia" | `R2-B1`, `R2-B2`, `R2-B3`, `R2-B4` — **PASS** (`maps 1→0`, `fds complete=True`, `residuales []`) | **Sí, directamente.** Es el escenario complementario exacto: sin referencias vivas, el mapping desaparece sin `_mmap.close()`. |
| "No se utilizó cierre forzado" | Verificado por AST (§3.2) sobre el código actual de B6/D1/D2 | **Sí, para el código publicado en HEAD.** No es verificable para ejecuciones históricas cuyo código ya no está en el árbol. |
| "3/3 PASS" del probe T1/T2 | **No existe en el repositorio** (§2) | **No.** No es evidencia disponible. |

**Punto clave:** B2 demuestra liberación natural cuando no quedan referencias vivas. B6/D1/D2 demuestran **lo contrario por diseño**: que con una referencia viva la liberación **no** se puede acreditar. Son las dos caras del mismo mecanismo, y ambas son coherentes entre sí.

### 3.4 Causas posibles, sin presentarlas como hechos

| Hipótesis | Evaluación |
|---|---|
| (a) El `UNKNOWN` se debe a una referencia viva legítima y deliberada | **Compatible con el código y con la tabla del informe** (`maps persiste`). Es la explicación declarada y no contradicha por ninguna evidencia del repositorio. |
| (b) El `UNKNOWN` oculta un fallo de liberación | **Descartable con la evidencia disponible**: B1/B2/B3/B4 acreditan liberación real (`1→0`) en el mismo binario, mismo entorno y misma sesión. Un fallo del mecanismo de liberación habría hecho fallar también esos casos. |
| (c) El `UNKNOWN` refleja una limitación de `gc` no universal | **Parcialmente aplicable, pero no es la causa del veredicto.** El veredicto no depende de `gc`: está codificado en la rama `"UNKNOWN" if ok_release else "FAIL"`, que se activa con independencia del resultado de `gc`. |

### 3.5 ¿Existe vía de adjudicación documental sin alterar el veredicto?

**Sí, pero solo como clasificación, no como cambio de veredicto.** El `UNKNOWN` es correcto y no debe cambiarse: los tres casos miden una situación en la que la acreditación de cierre es **imposible por definición del escenario**. Lo que sí puede documentarse es que el `UNKNOWN` **no es una incertidumbre epistémica sobre el código**, sino el resultado previsto cuando se viola la precondición de seguridad ("liberar todas las referencias").

### 3.6 Categorías propuestas

| ID | Categoría | Fundamento |
|---|---|---|
| R2-B6 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | El criterio es determinista y el resultado (`maps persiste` con referencia viva) está registrado en la tabla R2-B. La categoría se refiere a que **el caso es resoluble documentalmente como "UNKNOWN correcto por diseño"**, no a que pueda convertirse en PASS. |
| R2-D1 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Ídem, tabla R2-D (`maps persiste`). |
| R2-D2 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Ídem, tabla R2-D (`maps persiste`). |

**Salvedad obligatoria:** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` aquí significa **"la condición que produce el UNKNOWN está identificada y documentada sin ambigüedad"**, no "puede promoverse a PASS". **No se propone ni se autoriza el cambio de los tres UNKNOWN a PASS.** Un intento de promoverlos sería exactamente el tipo de conversión por interpretación que el encargo prohíbe.

**Evidencia que falta, si se quisiera ir más allá del UNKNOWN:** un escenario nuevo que (i) mantenga una referencia viva y (ii) demuestre que el mapeo desaparece *de forma certificada* tras eliminar esa referencia **dentro de la misma observación**, sin cierre forzado. Eso sería una prueba nueva, no una lectura documental. No es necesaria para el objetivo de la fase.

---

## 4. Grupo B — Descriptores y clasificación

### 4.1 R2-C2 — Entrada que desaparece durante el recorrido (Caso B)

**Criterio original (líneas 1338-1442).** Dos subcasos; el veredicto es `"UNKNOWN" if ok else "FAIL"` donde `ok = ok_fs and ok_proc`:

- **B1** (FS regular): `complete=False`, exactamente 1 error, `classification == DESCRIPTOR_DESAPARECIDO`, `errno == ENOENT`, `name == "5"`, `exception_type == "FileNotFoundError"`.
- **B2** (`/proc/self/fd` real): `closed_victim` verdadero, `complete=False`, exactamente 1 error sobre `victim_fd`, `ENOENT`, `UNKNOWN_CAUSE`.

**Resultado observado (informe, tabla R2-C2):** `B1_fs_ok=True`, con `DESCRIPTOR_DESAPARECIDO`, `errno=2`, `complete=False`; `B2_proc_real_ok=True`, con `closed_victim=True`, único error `'5'`, `ENOENT`, `UNKNOWN_CAUSE`, `complete=False`. Veredicto: **UNKNOWN**.

**¿La clasificación es coherente con la evidencia?** **Sí, y verifica dos reglas distintas del clasificador** (`_classify_fd_error`, línea 415):

| Rama del código | Regla | Caso que la ejercita |
|---|---|---|
| `if not _is_procfs_fd_dir(fd_dir): return CLASS_DISAPPEARED` | En FS regular, "estaba en el listado y ya no se puede inspeccionar" ⇒ DESAPARECIDO | B1 |
| `if _fdinfo_probe(...) is True: DISAPPEARED else: UNKNOWN_CAUSE` | En procfs, la ausencia de `fdinfo` **no** prueba que fuera un artefacto de procfs; también ocurre si el descriptor real se cerró | B2 |

**Lo que el UNKNOWN significa aquí:** no es ignorancia sobre si el evento ocurrió — ocurrió y está demostrado (`closed_victim=True`, un único error, sobre `victim_fd`). El UNKNOWN es la consecuencia **correcta** de `complete=False` bajo R1-B: desde un inventario incompleto no se puede acreditar un cierre. Es decir, el veredicto `UNKNOWN` es **el resultado esperado** de una prueba diseñada para producir un inventario incompleto controlado.

**Análisis crítico relevante:** la prueba tiene un nombre ("entrada que desaparece") que sugiere evaluar la *detección*, pero su veredicto evalúa la *acreditación de cierre*. Son dos preguntas distintas. La detección (detección real, sin ocultar ENOENT, clasificación correcta) **está demostrada y aprobada** dentro de `ok_fs`/`ok_proc`; la acreditación de cierre es imposible por construcción. Esto es un desajuste **semántico** entre título y veredicto, no un defecto de implementación.

**Causa indeterminada residual:** en B2, `UNKNOWN_CAUSE` deja abiertas dos causas (artefacto de procfs vs. descriptor real cerrado). La prueba **sí distingue** cuál fue (cierra `victim_fd` a propósito), pero el **clasificador** no puede distinguirlo y por eso se queda en `UNKNOWN_CAUSE`. Esa es la decisión conservadora correcta según R3-D.

**Categoría:** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` — con la misma salvedad que en el Grupo A: se puede documentar con certeza **por qué** es UNKNOWN y **que la clasificación es correcta**, pero el veredicto permanece UNKNOWN.

### 4.2 R2-C3 — Entrada inaccesible (permisos)

**Criterio original (líneas 1445-1479).** `ok = (not inv.complete and classification == DESCRIPTOR_INACCESIBLE and errno == EACCES and exception_type == "PermissionError")`; veredicto `"UNKNOWN" if ok else "FAIL"`.

**Resultado observado:** `complete=False`; `DESCRIPTOR_INACCESIBLE`, `errno=13`, `PermissionError`, entrada `'9'`. Veredicto **UNKNOWN**.

**¿Coherente?** **Sí.** La rama del clasificador es `if err in (errno.EACCES, errno.EPERM): return CLASS_INACCESSIBLE` (línea ~443). La cadena causal completa está verificada en el registro: `EACCES` (13) → `PermissionError` → `DESCRIPTOR_INACCESIBLE` → `complete=False` → `UNKNOWN`.

**Riesgo metodológico documentado (no es un fallo):** la prueba depende de que el proceso **no** sea `root`. Si `euid == 0`, `chmod(0o000)` no bloquea el acceso y la prueba fallaría por una razón ambiental, no por un defecto. En este entorno auditado `euid = 1001` (`user`), por lo que la precondición se cumple; pero es una **condición de entorno no verificada dentro de la prueba**. `test_r2c_inaccessible` no comprueba `os.geteuid()` en ningún punto. Se registra como fragilidad de portabilidad: en un Termux con usuario root la prueba podría no reproducir el escenario.

**Causa indeterminada residual:** **ninguna.** Es el caso mejor determinado de los nueve: no hay ambigüedad de causa.

**Categoría:** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` (la clasificación está cerrada; el UNKNOWN proviene de `complete=False`, que es el resultado buscado).

### 4.3 R2-C5 — Error de procfs durante la inspección

**Criterio original (líneas 1512-1568).** Tres ramas:
- `if not mechanics_ok: FAIL`
- `elif env_evidence: PASS`
- `else: UNKNOWN`

donde `mechanics_ok` = las 4 reglas unitarias del clasificador, y `env_evidence` = existencia **real** en `/proc/self/fd` de un error de fase `inspeccion` clasificado `ERROR_PROCFS` con `errno` en `{EIO, EINVAL, ENOTDIR, ENOSYS, EOPNOTSUPP, EBUSY, EREMOTEIO}` y contexto procfs.

**Resultado observado:** mecánica 4/4 correcta; inventario real `complete=True`, `errors=0`; lista `ERROR_PROCFS_inspeccion_con_errno_compatible` vacía. Veredicto **UNKNOWN**.

**¿La ausencia de un evento real impide adjudicar?** **Sí, y es exactamente lo que R3-C prescribe.** La prueba tiene dos mitades con objeto distinto:

| Mitad | Qué mide | Resultado | ¿Resoluble? |
|---|---|---|---|
| Mecánica (unitaria) | El clasificador mapea correctamente errno→clase | 4/4 correcta | **Sí, adjudicada dentro de la prueba** |
| Entorno (real) | Que el entorno haya producido alguna vez un fallo de procfs en inspección | No ocurrió | **No adjudicable sin provocar el evento** |

**Punto crítico:** `complete=True, errors=0` no es un fallo de la prueba; es la **ausencia del fenómeno**. No se puede acreditar un comportamiento que no se ha observado, y **provocarlo artificialmente** (inyectar un error en `/proc`) sería falsear el escenario, cosa que R3-C prohíbe expresamente ("No vale cualquier error genérico"). La prohibición del encargo de "no provocar nuevos errores de permisos ni carreras" refuerza lo mismo.

**¿Hay evidencia histórica suficiente para distinguir fallo de clasificación / evento no observado / causa indeterminada?**

| Alternativa | Veredicto de la auditoría |
|---|---|
| Fallo de clasificación | **Descartado.** La mecánica es 4/4 y está cubierta además por `R2-C4` (procfs → `ERROR_PROCFS` en enumeración, PASS) y por `R2-C2` B2 (`UNKNOWN_CAUSE` en inspección, correcto). |
| Evento no observado | **Confirmado.** Es la causa exacta: `errors=0` en el inventario real. |
| Causa indeterminada | **No aplica.** No hay ambigüedad: se sabe *por qué* no hay evidencia. |

**Categoría:** `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE`.

**Evidencia que falta:** un `ERROR_PROCFS` real de fase `inspeccion` en un `/proc` real. No es obtenible de forma no destructiva en un entorno sano. **No debe buscarse provocándolo.**

---

## 5. Grupo C — `/proc/self/maps`

### 5.1 R1-A3 — Parser con mapas sintéticos (coincidencia + no interpretables)

**Criterio original (líneas 2775-2796).** `verdict = "UNKNOWN" if m.status != READ_COMPLETE else ("PASS" if n == 1 else "FAIL")`, sobre un maps sintético generado por `_synthetic_maps_lines(..., match=True, unparseable=True)`, que inserta **1 línea válida coincidente + 2 líneas válidas sin coincidencia + 3 líneas no interpretables**:
```
"xyz"                                                     # <5 campos
"solo tres campos aqui"                                   # <5 campos
"aaaa-bbbb r-xp notadev 1 /ruta/invalida"                 # dev no hexadecimal
```

`MapsRead.status` (línea 255) devuelve `READ_UNCOMPLETE` en cuanto `self.unparseable` no está vacío.

**Resultado observado:** `status=incomplete`. Veredicto **UNKNOWN**.

**¿Evalúa el parser, la integridad del inventario o ambos?**

**Ambos, y en ese orden.** La prueba es una **cadena de dos eslabones**:

1. **Eslabón del parser** — mide que las 3 líneas malformadas se detecten y se **registren** en `unparseable` en lugar de descartarse silenciosamente (requisito R1-A).
2. **Eslabón de la integridad** — mide que, con `unparseable` no vacío, el recuento **no se use** para adjudicar y el escenario vaya a UNKNOWN.

La prueba original no desglosa ambos eslabones en campos separados del registro: el campo `observed` publica `status`, `recuento_sin_garantia`, `no_interpretables` y `error` en una sola cadena. **Esto es una carencia de instrumentación, no de lógica**: el veredicto depende del eslabón 2, pero no se registra por separado el resultado del eslabón 1 (que las 3 líneas concretas, con sus números de línea, quedaron en `unparseable`), ni se comprueba `len(m.unparseable) == 3`.

**Verificación cruzada disponible:** `D18-E7` del arnés histórico (`arnes_feasibility_d18_mmap_6g1.py`, línea 985) **sí** comprueba explícitamente `len(entries) == 1 and len(unp) >= 1`, y salió **PASS**. Es decir, el eslabón del parser **está demostrado**, pero en la batería de D18-R1, no en la de D18-R2. `R1-A3` de R2 depende de él sin repetirlo.

**¿Puede explicarse documentalmente sin repetir pruebas?** **Sí.** La explicación no requiere ejecutar nada: `status=incomplete` solo puede alcanzarse si `unparseable` no está vacío (§5.3 de este informe cita la propiedad), y eso solo ocurre si el parser detectó las líneas malformadas. La lógica del parser está verificada por lectura directa (línea 317-355) y su comportamiento coincide con el documentado.

**Categoría:** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE`.

**Recomendación (no implementada):** en una fase futura, desglosar el registro de `R1-A3` en dos campos explícitos (`parser_detecto_no_interpretables`, `integirdad_no_acreditada`). Sería una mejora de trazabilidad, no un cambio de veredicto.

### 5.2 R1-A4 — Ruta de maps inexistente

**Criterio original (líneas 2799-2813).** `m = parse_maps(os.path.join(WORKDIR, "no_existe_maps_xyz"))`; `verdict = "UNKNOWN" if m.status != READ_COMPLETE else "FAIL"`.

**Resultado observado:** `status=unreadable`, `FileNotFoundError` registrado, 0 entradas. Veredicto **UNKNOWN**.

**¿Escenario no disponible en el entorno o fallo de implementación?**

**Escenario no disponible en el entorno (correctamente documentado).** El código de `parse_maps` (línea 317) tiene `except OSError as e: error = f"{type(e).__name__}: {e}"` sin re-lanzar, y fija `readable = False`. `MapsRead.status` devuelve `READ_UNREADABLE` cuando `self.error is not None or not self.readable`. La cadena es determinista y verificable por lectura.

**Punto crítico de interpretación:** la prueba **no** lee `/proc/self/maps` real. Usa una ruta sintética inexistente dentro de `WORKDIR`. Por tanto:

- **Mide** que `parse_maps` maneja un origen ilegible sin lanzar y sin inventar un recuento.
- **No mide** que `/proc/self/maps` no sea accesible en el entorno real. De hecho, `/proc/self/maps` **sí** es accesible (A1-A6, B1-B6, D1-D4 lo leen constantemente y obtienen lecturas `complete`).

Es la contraparte exacta de `D18-E1` ("maps inexistente — SIMULACIÓN controlada"), que también fue **UNKNOWN** por la misma razón: el UNKNOWN reconoce que la *ausencia real de procfs* no se ha reproducido. La prueba es honesta al no declararlo PASS.

**Categoría:** `LIMITACION_DEL_ENTORNO_DOCUMENTADA`.

**Evidencia que falta:** una ejecución en un entorno donde `/proc/self/maps` **realmente** no exista o no sea legible (p. ej. contenedor con `/proc` desmontado, o política SELinux en Android que lo oculte). Esa condición no se puede crear de forma no destructiva y el encargo prohíbe fabricar un archivo `/proc` o alterar el entorno.

### 5.3 Nota de coherencia adicional (no solicitada, relevante para la adjudicación)

`D18-E2` de la batería histórica simula `EACCES` con `chmod(0o000)` sobre un archivo de maps y también quedó en **UNKNOWN**, describiéndose a sí mismo como "SIMULACIÓN de EACCES; ausencia real no reproducida". `R1-A4` de R2 tiene el mismo estatus metodológico que E1/E2 y su UNKNOWN es **consistente con la política ya aplicada** en D18-R1. No hay contradicción entre baterías.

---

## 6. Grupo D — Symlink roto (R1-B2)

**Criterio original (líneas 2836-2861).**

```python
broken = os.path.join(d, "4")
try:
    os.symlink(os.path.join(d, "no_existe_xyz"), broken)
except OSError:
    pass
inv = fds_with_identity(st, fd_dir=d)
verdict = "UNKNOWN" if (not inv.complete) else "FAIL"
```

Un directorio sintético con **1 entrada válida** (`"3"`) + **1 symlink roto** (`"4"`). Ver `fds_with_identity` en modo `dirfd` (`os.stat("4", dir_fd=dirfd)` → `ENOENT`) o `path` (`os.stat(os.path.join(d, "4"))` → `ENOENT`). Como `d` no está bajo `/proc/`, `_is_procfs_fd_dir(d)` es `False`.

**Resultado observado:** `complete=False`; `ENOENT`; clasificación `DESCRIPTOR_DESAPARECIDO`. Veredicto **UNKNOWN**.

**¿La clasificación corresponde al evento observado?** **Sí.** La rama aplicable es la primera de la sección ENOENT:
```python
if err == errno.ENOENT:
    if not _is_procfs_fd_dir(fd_dir):
        return CLASS_DISAPPEARED, ctx   # FS regular: listado previo + ENOENT = desaparición
```
El evento es exactamente "entrada presente en el listado, `stat` posterior devuelve ENOENT". En un FS regular **no existe** el concepto de artefacto de procfs, de modo que la clasificación es la única compatible con la semántica de R3-D. **No hay ambigüedad causal**: la causa es el symlink roto.

**¿La semántica de ENOENT permite identificar inequívocamente la causa?**

**Aquí está el matiz importante y hay que ser preciso.** `ENOENT` **por sí solo no identifica la causa**. En un FS regular, `os.stat(name, dir_fd=dirfd)` puede devolver `ENOENT` por al menos dos motivos distintos:

1. La entrada fue **eliminada** entre la enumeración y la inspección.
2. La entrada **existe** pero es un **symlink cuyo destino no existe** (exactamente este caso).

La clasificación `DESCRIPTOR_DESAPARECIDO` **no distingue** entre (1) y (2): ambos producen el mismo errno y la misma rama de código. La prueba llama al escenario "symlink roto", pero el clasificador no lo sabe y no lo puede saber con la información que recibe.

**Consecuencia:** el veredicto `UNKNOWN` es correcto por dos motivos independientes y acumulativos:
- (i) `complete=False` fuerza UNKNOWN bajo R1-B;
- (ii) la clasificación es `DESCRIPTOR_DESAPARECIDO`, que en sentido estricto **no es exacta** para un symlink roto (la entrada *no* desapareció: sigue en el directorio). Es una clasificación **conservadora y no errónea**, pero es semánticamente más estrecha que el evento.

Esto es un hallazgo de **precisión semántica**, no de corrección lógica: `DESCRIPTOR_DESAPARECIDO` describe el efecto observable ("ya no puedo inspeccionar esta entrada"), no la causa física.

**¿Qué evidencia adicional sería necesaria?**

| Para distinguir (1) de (2) | Requeriría | ¿Permitido? |
|---|---|---|
| Comprobar si la entrada sigue en el directorio | Un `os.lstat(name, dir_fd=dirfd)` adicional tras el fallo | Sería una **modificación del código** — fuera de alcance |
| Verificar el tipo de entrada antes del `stat` | `entry.is_symlink()` desde el `DirEntry` de `scandir` | **Ya disponible** en el bucle (`entry` es un `DirEntry`) pero **no se usa** en `fds_with_identity()` |
| Una categoría nueva | `DESCRIPTOR_NO_RESOLUBLE` o similar | Cambiaría la taxonomía R3-D — fuera de alcance |

**Observación técnica de valor:** el bucle `for entry in it:` (línea ~583) ya dispone del objeto `entry` (`os.DirEntry`), que expone `entry.is_symlink()` **sin coste de syscall adicional** en la mayoría de plataformas y **sin abandonar el anclaje `dirfd`**. Esa información permitiría refinar la clasificación a futuro sin romper R3-D ni R4-B. **Se documenta como recomendación, no se implementa.**

**Categoría:** `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA`.

**Evidencia que falta:** la distinción entre "entrada eliminada" y "symlink no resoluble" requeriría una comprobación adicional no destructiva (`entry.is_symlink()` o `lstat` con `dir_fd`). No se ejecuta en esta fase ni se propone como corrección inmediata.

---

## 7. Tabla consolidada de los nueve casos

| # | ID | Título | Criterio que produce el UNKNOWN | Categoría propuesta | Falta |
|---|---|---|---|---|---|
| 1 | R2-B6 | Referencia externa viva impide la liberación | `kept_maps == 1` ⇒ rama UNKNOWN por diseño (mapping **debe** persistir) | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Nada para clasificar; no promovible a PASS |
| 2 | R2-D1 | Liberación incompleta (vista retenida) | Ídem | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Ídem |
| 3 | R2-D2 | Referencia retenida impide acreditar cierre | Ídem | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Ídem |
| 4 | R2-C2 | Entrada que desaparece durante el recorrido (Caso B) | `complete=False` + clasificación correcta (B1 `DESAPARECIDO`, B2 `UNKNOWN_CAUSE`) | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Nada; desajuste título/veredicto documentado |
| 5 | R2-C3 | Entrada inaccesible (permisos) | `complete=False` + `EACCES`→`DESCRIPTOR_INACCESIBLE` correcta | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Nada; frágil si `euid==0` |
| 6 | R2-C5 | Error de procfs durante la inspección | `mechanics_ok` y **no** `env_evidence` (no hubo `ERROR_PROCFS` real) | `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` | `ERROR_PROCFS` real en `inspeccion` |
| 7 | R1-A3 | Coincidencia + líneas no interpretables | `status == incomplete` ⇒ lectura no acreditable | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | Nada; mejorar desglose del registro |
| 8 | R1-A4 | `/proc/self/maps` no disponible o ilegible | `status == unreadable` en ruta sintética (no `/proc` real) | `LIMITACION_DEL_ENTORNO_DOCUMENTADA` | Entorno con `/proc/self/maps` realmente ilegible |
| 9 | R1-B2 | Inventario incompleto (symlink roto) | `complete=False`; `DESAPARECIDO` no distingue symlink roto de borrado | `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` | Distinción symlink/borrado (`entry.is_symlink()`) |

**Distribución:** 5 `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` · 1 `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` · 1 `LIMITACION_DEL_ENTORNO_DOCUMENTADA` · 1 `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` · 0 `NO_DETERMINABLE`.

**Advertencia sobre la lectura de esta tabla:** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` **no** significa "el UNKNOWN es incorrecto" ni "puede convertirse en PASS". Significa que **la razón del UNKNOWN está completamente determinada y documentada** y no requiere nueva evidencia para ser explicada. Los nueve UNKNOWN siguen siendo UNKNOWN.

---

## 8. Recomendación técnica para la siguiente fase

Ordenadas por relación coste/valor. Ninguna se ejecuta en esta fase.

1. **No promover ningún UNKNOWN.** Los nueve son correctos con la evidencia actual. Cualquier promoción sería una conversión por interpretación, prohibida expresamente.

2. **Prioridad alta — desglose de instrumentación en R1-A3 y R2-C2.** Añadir campos separados en el registro (`parser_detecto_3_no_interpretables`, `deteccion_real_ok` / `acreditacion_ok`) permitiría separar el eslabón demostrado del eslabón imposible, sin cambiar el veredicto. Es una mejora de trazabilidad de bajo riesgo.

3. **Prioridad media — precisión semántica del clasificador (R1-B2).** `DESCRIPTOR_DESAPARECIDO` se aplica a un symlink roto que no desapareció. `entry.is_symlink()` está disponible en el bucle sin syscall adicional. Una categoría nueva o un campo `entry_kind` en el contexto del error eliminaría la ambigüedad. **Requiere autorización expresa y su propio ciclo R6-R5**; no debe hacerse dentro de una fase de auditoría.

4. **Prioridad media — precondición de `R2-C3`.** Añadir `os.geteuid() != 0` como precondición explícita del escenario, para que en un entorno root el resultado se degrade a UNKNOWN con motivo declarado en lugar de producir un FAIL engañoso.

5. **Prioridad baja — `R2-C5`.** No buscar `ERROR_PROCFS` provocándolo. Su UNKNOWN es honesto y no bloquea nada. Si se quiere resolver, la vía correcta es un entorno donde el fallo ocurra de forma natural (p. ej. procfs restringido en Android con SELinux), no una inyección.

6. **Prioridad baja — `R1-A4`.** Mantener como limitación de entorno. Documentar en el informe que la prueba usa ruta sintética y no `/proc/self/maps` real, para evitar lecturas erróneas futuras.

7. **Valoración global de la fase:** la integridad de los resultados históricos es correcta. **Los nueve UNKNOWN son defendibles y no hay evidencia en el repositorio que permita resolver ninguno de ellos sin nueva evidencia o cambio de código.** El único problema real detectado no está en los veredictos, sino en la **trazabilidad**: el JSON de evidencia no se versiona (`/tmp`), y el "Probe T1/T2" citado en el encargo **no existe** en el repositorio.

---

## 9. Confirmaciones obligatorias

### 9.1 No se modificó código ni evidencia original

| Verificación | Resultado |
|---|---|
| `git status --porcelain` antes de crear este informe | vacío (árbol limpio en `0ae2c10`) |
| `sha256` del arnés antes y después de la auditoría | `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18` sin cambios |
| `sha256` del informe de evidencia antes y después | `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db` sin cambios |
| Ejecución del arnés | **Ninguna.** No se importó, no se invocó `main()`, no se ejecutó `run_controller()` |
| Uso de `python -B` | Sí, exclusivamente para `ast.parse()` y `hashlib` (lectura estática). Sin `__pycache__` |
| Creación de archivos `/proc` falsos | **Ninguna** |
| Alteración de symlinks del sistema | **Ninguna** |
| Pruebas destructivas o concurrentes | **Ninguna** |
| Cierre forzado `_mmap.close()` | **Ninguno** (verificado por AST que el código tampoco lo hace) |
| D18-R1 C5 histórico | **No ejecutado** |
| `numpy` | **No instalado, no requerido** en esta fase (auditoría estática) |

### 9.2 No se alteraron veredictos históricos

- Los 9 `UNKNOWN` siguen siendo `UNKNOWN`.
- Los `30 PASS` / `0 FAIL` de R6-R3 Linux siguen intactos.
- El `1 FAIL` de R6-R3 Android/Termux (`R2-C9`) sigue intacto y **no** se presenta como PASS.
- `C5 = FAIL` histórico de D18-R1 sigue intacto.
- `D18` sigue `FAIL`. **No se declara D18-R2 global PASS.**
- El veredicto global de D18-R2 en Linux sigue siendo `UNKNOWN` (30/0/9); en Android/Termux `FAIL` (29/1/9).
- R6-R4 (`R2-C9` por identidad `fstat`) no se toca.
- PR #3 y PR #4 no se modifican ni se fusionan.

### 9.3 Limitación de esta auditoría

No hay JSON de evidencia crudo versionado. Toda la evidencia primaria citada proviene del **registro textual del informe** (`INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md`, §6, tablas R2-A/B/C/D y R1-A/B) y del **código fuente publicado**. Cuando una afirmación del encargo no ha podido verificarse contra el repositorio, se ha declarado explícitamente en §2 en lugar de aceptarla por defecto.

---

## 10. Enlaces de GitHub para auditoría

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama y HEAD auditados (`0ae2c10`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit R6-R4 (funcional, `bbc1aab`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/bbc1aab50ab1487f81c03697a7f10390088302e5
- Commit R6-R3 (`c80f7f1`, padre): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/c80f7f11651e08267a4929527b3035ae40c39e13
- Arnés auditado en HEAD: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe de evidencia en HEAD: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- Arnés histórico D18-R1: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_mmap_6g1.py
- Informe histórico D18-R1: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_MMAP_6G1.md
- Diff completo R6-R3 → R6-R4: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/compare/c80f7f11651e08267a4929527b3035ae40c39e13...0ae2c10c472e2e9941320fa1dd2727f1a044701c
- PR #4 (R6-R4, abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4
- PR #3 (R6/R6-R1/R6-R3, abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3

---

**Fin del informe de auditoría. No se implementaron correcciones. No se ejecutaron pruebas. No se fusionó ningún PR. La adjudicación final corresponde exclusivamente a Cris / ChatGPT.**
