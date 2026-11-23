# FEASIBILITY-1 (6G.1) — VALIDACIÓN EMPÍRICA AISLADA — v3 (RECTIFICACIÓN FINAL FEASIBILITY-1-R2)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena.
- **Naturaleza:** validación empírica **aislada** de los mecanismos del plan v2.3. **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción; cero ejecución de motores; cero audio real; cero Android/Termux; cero FLOW-5..8; cero EVO/MQR; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Historial:** v1 publicada en `a94f50793dfa97bb7074bb3e20fe2d42c3306596` (hijo de `2274862…`). **v2 = rectificación FEASIBILITY-1-R1**, publicada en `71d928bbf3a7ee9ebed92a94da005d120ed42de7` (hijo directo de `a94f507…`). **v3 = rectificación final FEASIBILITY-1-R2** (hijo directo de `71d928b…`): sólo los dos archivos autorizados (`scripts/arnes_feasibility_1_6g1.py` y este informe). Los resultados de las ejecuciones anteriores **se conservan íntegros en §10** (sin borrar ni ocultar).
- **Corrida final R2:** ts `2026-11-23T23:33:35Z` (run A, `--raiz /tmp/feas1_r2`) + corrida de reproducibilidad ts `2026-11-23T23:34:04Z` (run B, `--raiz /tmp/feas1_r2_b`). Ambas: **6/6 PASS · 48/48 subpasos obligatorios OK · 60 descriptores registrados · 0 residuos**.

---

## 1. Commit padre exacto

- **FEASIBILITY-1-R1 (padre de esta fase):** `71d928bbf3a7ee9ebed92a94da005d120ed42de7` — verificado ANTES de trabajar: local = origin = `gh api` = `71d928b…` CONFORME, árbol limpio, SHA256 de partida registrados: arnés `e2e57cfef5a43cf9e59bc9559646c23e94077bc2df8a9ec5ea3b2bb18fa19021`, informe `16120904fcf2c1f909d87c3c42340609a300de4ee20756dceb34b671abc25c26`.

## 2. Commit final y archivos modificados

- **Commit de esta rectificación:** hijo directo de `71d928b…`; SHA completo en el informe de entrega (verificable vía `git`/`gh api`).
- **Archivos (exactamente los 2 autorizados):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py` (M) — arnés rectificado R2-A/R2-B/R2-C sobre R1..R6.
  - `INFORME_FEASIBILITY_1_6G1.md` (M) — este informe.
- Evidencia JSON cruda: `/tmp/feas1_r2/evidence/feas1r2_f{1..6}.json` + `consolidado_feasibility_1_r2.json` (run A) y `/tmp/feas1_r2_b/evidence/…` (run B, reproducibilidad). El arnés regenera todo.

## 3. Entorno y versiones exactas

| Componente | Valor |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (`/tmp/venv_i1/bin/python`) |
| numpy | `1.26.4` |
| soundfile | `0.13.1` (libsndfile `1.2.2`) |
| glibc | 2.36 (símbolo `renameat2` disponible) |

Veredictos válidos para ESTE entorno y condiciones; sin extrapolación a Android/Termux ni a otros entornos.

## 4. Comando reproducible

```
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_r2
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_r2_b   # reproducibilidad
```

## 5. Fixtures sintéticos (sin cambios respecto de R1)

- WAV: ruido blanco PRNG (`20261122` F3; `19480720` F6), 0.30, estéreo, PCM_16, 44100/8000 Hz; señal recortada a `[-0.999, 0.999]` antes de escribir (libsndfile recorta muestras float >1.0 en PCM_16 — observado en R1); el esperado de la comparación es la señal recortada.
- NPY float32 `(1024,2048)` / `(256,512)` con valores sembrados; payloads ASCII. Cero audio real.

## 6. Correcciones R2-A/R2-B/R2-C aplicadas al arnés (esta fase)

| ID | Corrección | Implementación |
|---|---|---|
| **R2-A** | Prioridad inequívoca de veredictos | `_agregar_veredicto` reordenado: **(1)** uno o más subpasos obligatorios fallidos ⇒ **FAIL** (si además hay condición no disponible, se añade al detalle como «NO oculta el fallo»); **(2)** sin fallos obligatorios pero condición de evaluación no disponible ⇒ **UNKNOWN**; **(3)** todos los obligatorios satisfechos y ninguna condición pendiente ⇒ **PASS**. Un UNKNOWN NUNCA oculta un subpaso obligatorio fallido. La regla se **aplica y comprueba en F2 y F5**: subpaso obligatorio `R2A_prioridad_fail_sobre_unknown_comprobada` con tres casos sintéticos deterministas (todos-ok+condición⇒UNKNOWN; fallo-obligatorio+condición⇒FAIL; todo-ok⇒PASS) — `conforme=true` en ambas pruebas y en ambas corridas. `condiciones_pendientes` queda registrado en cada JSON. |
| **R2-B** | Aperturas negativas y Ledger | Auditoría de **TODAS** las `os.open()` del arnés (27 llamadas registradas en `led.abrir` / `_crear_archivo_rel` con retorno registrado + 3 negativas). Nuevo helper `_abrir_negativo(pasos, led, etiqueta, paso, abrir, errno_esperado)`: si la apertura falla, registra la excepción y la **valida contra el errno esperado** (`errno_conforme`); si tiene éxito cuando debía fallar, **registra el descriptor en el Ledger inmediatamente**, lo **cierra de forma explícita y verificable** (`cerrado_explicitamente`, `existe_tras_cierre`) y marca el subpaso **FALLIDO**. Aplicado a F1 `evil` (esperado ENOTDIR/ELOOP), F2 magic-link tras close (esperado ENOENT), F4 nombre sustituido por symlink (esperado ENOTDIR/ELOOP). Ningún descriptor abierto con éxito puede quedar fuera del Ledger; un fallo de control no se oculta por una fuga ni por una excepción posterior. |
| **R2-C** | Indisponibilidad de renameat2 | F5 clasifica la sonda en tres ramas: syscall **ejecutada** (errno ENOENT/EEXIST con origen inexistente) ⇒ disponible; **ENOSYS / arquitectura sin soporte** ⇒ no disponible; **cualquier otro errno** ⇒ sonda inconclusa. En las dos últimas: NO se continúa con los 4 escenarios dependientes de renameat2 (registrados con `ejecutado=False`, `obligatorio=False`, «no se presenta como probado»), se **cierran y verifican todos los descriptores abiertos**, y el veredicto es **UNKNOWN salvo fallo obligatorio independiente** (que prevalece como FAIL por R2-A). Como el entorno real SÍ dispone de renameat2, la rama de indisponibilidad se **ejercita mediante PRUEBA CONTROLADA AISLADA**: parche ENOSYS sobre `_renameat2` + ejecución de `f5()` en un raíz separado (`f5_ctrl_enosys`), verificando veredicto UNKNOWN, 0 fallos obligatorios, escenarios no ejecutados y no-obligatorios, sonda no-obligatoria (`clasificacion=no_soportada`), 0 residuos y ausencia de publicación simulada (dir vacío). La evidencia DECLARA el parcheo. La rama real no se declara validada — no ocurrió en este entorno. |

Las correcciones R1..R6 de la fase anterior permanecen en el arnés sin cambios de fondo (agregación de veredictos, Ledger con tipos, F2 con guardián procfs, F3 contenido PCM_16, F4 en escenarios, F1/F5 identidades + R-31 como observación).

## 7. Resultados R2 — subpasos individuales y veredictos globales calculados

**Run A (ts `2026-11-23T23:33:35Z`): 48/48 subpasos obligatorios OK · 60 descriptores registrados · 0 residuales · 6/6 PASS. Run B (ts `23:34:04Z`): idéntico — 6/6 PASS, 48/48, 60 fds, 0 residuos.** `obligatorios_fallidos=[]` y `condiciones_pendientes=[]` en las 6 pruebas (ambas corridas).

**F1 — R-13 → PASS** (9 pasos; 9 obligatorios; 9 fds propios; 0 residuos): base acreditada → candidates creado/acreditado → 2 grupos dos niveles (identidad fstat) → descenso sin rutas + **identidades validadas** → symlink rechazado **con errno validado** (ENOTDIR=20 ∈ esperado {20,40}, `errno_conforme=true`, R2-B) → inesperados clasificados (`['evil','suelto.txt']`) → sustitución detectada por identidad (fd≠nombre) → cierre ordenado sin fugas.

**F2 — R-29 → PASS** (9 pasos; 7 obligatorios; 6 fds [5 propios + 1 duplicado]; 0 residuos): procfs disponible (no obligatorio) → A: magic-link designa el objeto / vivo tras unlink / **desaparece al cerrar (ENOENT=2, errno esperado conforme, R2-B)** → B: guardián **0 disparos** / alternativa con contenido e identidad verificados → `escenario_procfs_realemente_ausente`: NO reproducible (no obligatorio, declarado) → **R2A_prioridad_fail_sobre_unknown_comprobada** (3 casos sintéticos conforme) → ledger. Si procfs no estuviera montado: parte A ⇒ UNKNOWN explícito (condición registrada) sin ocultar ningún fallo obligatorio (R2-A).

**F3 — R-34 → PASS** (6 pasos; 6 obligatorios; 7 fds [6 propios + 1 duplicado]; 0 residuos): escritor por fd `closefd=False` con identidad conservada (`format='WAV'` exigido por fd) → lector por fd (forma 44100×2) → **contenido: `max_abs_diff=3.0513852834701538e-05 ≤ tolerancia 3.0517578125e-05` (1 LSB PCM_16, cota conservadora)** → `closefd=True` cierra el fd propio (EBADF observado, marcado `biblioteca_cierra`) → open_memmap vía procfs (identidad + valor 3.25) → ledger.

**F4 — P-08/R-28 → PASS** (11 pasos; 11 obligatorios; 11 fds propios; 0 residuos): A nominal (unlinkat vía `fd_masks` + rmdir vía padre acreditado + verificación) → B: rmdir sobre nombre-symlink **falla seguro** y ajeno intacto / **apertura O_NOFOLLOW rechazada con errno validado (ENOTDIR=20 ∈ {20,40}, R2-B)** / real no redirigido / eliminación por fd del real / symlink presente y no seguido / unlinkat del enlace NO del destino / ajeno intacto → C: ENOTEMPTY + ENOENT → ledger.

**F5 — R-D → PASS** (8 pasos; 8 obligatorios; 18 fds propios; 0 residuos): sonda **disponible** (syscall ejecutada, errno 2 con origen inexistente) → publicación con `fstat(fd_pub)==identidad` → colisión EEXIST con destino intacto → sustitución origen: impostor publicado, **detectado post-rename** (R-31: «NO es garantía de publicación atómica») y real localizable por fd → real fuera del padre: ENOENT con fd sobreviviente → ledger → **R2A_prioridad_fail_sobre_unknown_comprobada** (conforme) → **R2C_rama_indisponibilidad_ejercida_prueba_controlada_aislada** (conforme: UNKNOWN obtenido/esperado; 4 escenarios `ejecutado=false, obligatorio=false`; sonda `obligatorio=false, clasificacion=no_soportada`; 0 residuos; dir vacío — sin publicación simulada).

**F6 — cierre → PASS** (7 pasos; 7 obligatorios; 9 fds: 2 anclas, 1 log, 2 writers, 2 memmaps, 2 lectores; 0 residuos): apertura en orden registrada → anclas conservadas → etapas de cierre (writers→memmaps→lectores→log→anclas inversas) verificando **por fd conocido** (stat directo) que cada cierre desaparece y que los demás PERMANECEN.

## 8. Descriptores abiertos, cerrados y residuos (R2/R2-B)

| Prueba | Registrados (tipos) | Cerrados explícitos | Cerrados por biblioteca/fdopen | Residuos |
|---|---|---|---|---|
| F1 | 9 (propios) | 9 | 0 | 0 |
| F2 | 6 (5 propios + 1 duplicado) | 4 + fd_dir | 1 (dup→fdopen) | 0 |
| F3 | 7 (6 propios + 1 duplicado) | 5 | 1 (dup→fdopen) + 1 (`closefd=True` de libsndfile) | 0 |
| F4 | 11 (propios) | 11 | 0 | 0 |
| F5 | 18 (propios) | 18 | 0 | 0 |
| F6 | 9 (propios; log vía fdopen) | 8 + log | 1 (fdopen) | 0 |
| **Total** | **60** | — | — | **0** |

**Efecto R2-B sobre el recuento:** en esta corrida las 3 aperturas negativas fallaron como se esperaba (no se crearon descriptores), por lo que el total registrado no cambia respecto de R1 (60). La diferencia es **estructural**: ahora toda apertura negativa que tuviera éxito inesperadamente quedaría registrada en el Ledger, cerrada de forma explícita y verificable, y su subpaso quedaría FALLIDO — sin excepciones ni fugas que la oculten. En modo fd, libsndfile opera sobre NUESTRO descriptor (no se observaron fds internos adicionales de biblioteca). No se declaran «sin fugas» más allá de los descriptores contabilizados; el ledger de cada prueba exige 0 residuos registrados y su verificación es un subpaso obligatorio.

## 9. Evidencia específica R2, excepciones observadas y diferencias documento↔probado

**9.1 Evidencia específica exigida por la adjudicación (presente en los JSON de las dos corridas):**
- **Prioridad FAIL frente a UNKNOWN:** subpasos `R2A_prioridad_fail_sobre_unknown_comprobada` en F2 y F5 — caso (a) todo-ok + condición ⇒ UNKNOWN; caso (b) fallo obligatorio + condición ⇒ **FAIL** con `obligatorios_fallidos=['sintetico_obligatorio_fallido']` y nota «la condición de evaluación no disponible (NO oculta el fallo)»; caso (c) todo-ok sin condición ⇒ PASS. `conforme=true` en F2 y F5, en ambas corridas.
- **Aperturas negativas inesperadamente exitosas:** regla implementada en `_abrir_negativo` (§6 R2-B). En esta corrida **ninguna** de las 3 aperturas negativas (F1 `evil`, F2 magic tras close, F4 `masks2`) tuvo éxito — sus descriptores fantasma no existen y así consta: `exito_inesperado=null` en las tres, con errno observado y validado (20, 2, 20).
- **Cierre y verificación de esos descriptores:** si se diera el caso, el helper registra `cerrado_explicitamente` + `existe_tras_cierre` y el cierre quedará además bajo la verificación final del Ledger (subpaso obligatorio). Esa ruta no se ejecutó aquí (no hubo éxito inesperado) — se declara implementada y estructuralmente forzada, no ejecutada por ausencia del suceso.
- **Rama de indisponibilidad de renameat2:** ejercida en **prueba controlada aislada** (§6 R2-C y §7 F5) — veredicto UNKNOWN, escenarios no ejecutados y marcados no-obligatorios, sonda no-obligatoria, 0 residuos, sin publicación simulada, parcheo declarado. La **rama real** (entorno sin renameat2) no ocurrió y **no se declara validada**.

**9.2 Excepciones observadas en la corrida final** (todas esperadas y documentadas): ENOTDIR(20) open/rmdir sobre symlink-nombre con O_DIRECTORY/O_NOFOLLOW; ENOENT(2) magic-link tras close, sonda renameat2, real fuera del padre, unlink inexistente; EEXIST(17) colisión; EBADF(9) fstat tras `sf.close()` con `closefd=True`; ENOTEMPTY(39) rmdir con contenido.

**9.3 Fallos del PROPIO arnés detectados durante esta rectificación** (evidencia de que la metodología funciona; NO son hallazgos sobre producción): (a) en la primera implementación de R2-C la sonda clasificó ENOENT (resultado esperado con origen inexistente) como «inconclusa» y F5 devolvió **UNKNOWN** con renameat2 disponible — detectado por la propia corrida (el UNKNOWN no pasó inadvertido), corregido con la clasificación de tres ramas (§6) y ambas corridas re-ejecutadas; (b) `global _renameat2` mal posicionado (SyntaxError de Python: uso previo a la declaración) — corregido. Ambos errores quedaron confinados al arnés; ninguna prueba se publicó con ellos.

**9.4 Diferencias documento↔probado** (precisiones conservadas de R1, §9.3 de la v2; el plan v2.3 NO se modifica aquí):
1. Escritura por fd exige `format='WAV'`; lectura por fd NO acepta format/samplerate/channels (auto-detección).
2. `closefd=True` cierra el fd propio (EBADF): el diseño fija `closefd=False` — con evidencia.
3. `np.memmap(file object)` exige fd **O_RDWR**; `open_memmap('/proc/self/fd/N')` no lo exige sobre el fd retenido.
4. El errno de rechazo de symlink es **ENOTDIR (20)** en este kernel (no ELOOP); el rechazo fail-closed se mantiene.
5. **libsndfile recorta a ±1.0 en PCM_16**: los fixtures de implementación deben acotar el rango.
6. Un `os.dup` comparte offset con el original: rebobinar (o `pread`) antes de re-leer.
7. La detección de fugas por listado de `/proc/self/fd` produce falsos positivos: el ledger usa `os.stat` por fd conocido.
8. Confirmaciones sin diferencia: identidad (dev,ino) conservada; magic-link designa el objeto; RENAME_NOREPLACE atómico (EEXIST); detección post-rename (R-31); orden de cierre verificable por etapas.

**9.5 Separación evidencia observada vs deducción:** lo OBSERVADO son los subpasos de §7 con sus valores (identidades `(dev,ino)`, errno con validación, max_abs_diff, disparos del guardián, etapas de cierre, casos sintéticos de prioridad, ejercicio controlado ENOSYS). Son DEDUCCIÓN (etiquetadas como tales): la generalización a entornos no probados, la ausencia de fugas «en general», la conducta de las ramas FAIL-sobre-UNKNOWN y ENOSYS en entornos reales distintos, y cualquier afirmación del plan no ejercitada aquí (hashes G1, compuertas del motor real, R-13 con motor).

## 10. Trazabilidad de las ejecuciones anteriores — conservada

**v1 (commit `a94f507…`, ts `2026-11-23T23:01:31Z`): 6/6 PASS** con la metodología v1: F1 (9 pasos) · F2 (5) · F3 (5) · F4 (7) · F5 (5) · F6 (8). Sus resultados no se retiran: la rectificación R1 identificó estas deficiencias metodológicas (corregidas en v2): veredictos no agregados sobre todos los subpasos obligatorios (p. ej. F1 `symlink_rechazado ok=False` no impedía PASS); ledger incompleto (`fd_base` en F3/F4, `fd_padre` en F5; writers/memmaps/lectores en F6); F2 dependía de procfs sin guardián; F3 verificaba sólo forma, no contenido; F4 presentaba `masks_real` como equivalente nominal. La evidencia v1 fue regenerada por la corrida R1 (los JSON v1 no se conservan en disco; sus resultados quedan registrados en este informe y en el commit `a94f507…`).

**v2 / FEASIBILITY-1-R1 (commit `71d928b…`, run A ts `2026-11-23T23:18:18Z` + run B `23:18:31Z` aprox): 6/6 PASS · 45/45 subpasos obligatorios OK · 60 descriptores · 0 residuos** — F1 PASS (9/9) · F2 PASS (6/6; procfs-ausente NO reproducible, declarado) · F3 PASS (6/6; max_abs_diff 3.0514e-05) · F4 PASS (11/11; escenarios A/B/C) · F5 PASS (6/6) · F6 PASS (7/7). Sus resultados no se retiran: la presente rectificación R2 identifica estas deficiencias metodológicas de v2 (corregidas en v3): la prioridad UNKNOWN>fallos en `_agregar_veredicto` podía ocultar un subpaso obligatorio fallido bajo una condición no disponible; las aperturas negativas no registraban un éxito inesperado en el Ledger (fuga de un fd que debía rechazarse + fallo oculto); F5 continuaba ejecutando los escenarios aunque la sonda determinara indisponibilidad y no ejercitaba la rama ENOSYS. La evidencia v2 fue regenerada por las corridas R2 (los JSON v2 no se conservan en disco; sus resultados quedan registrados en este informe y en el commit `71d928b…`).

## 11. Limitaciones y escenarios no reproducidos

1. **Escenario «procfs realmente ausente»: NO reproducible en este sandbox** (procfs montado). Lo probado es el mecanismo B SIN CONSULTAR procfs (guardián runtime, 0 disparos), que **NO equivale** a ejecutar con procfs ausente. Queda UNKNOWN/declarado, no PASS.
2. **Rama REAL de indisponibilidad de renameat2: no ocurrió en este entorno** (glibc 2.36 con `renameat2` disponible). Lo probado es el ejercicio controlado con ENOSYS simulado en raíz aislado (§6/§7); el comportamiento en un entorno realmente sin la syscall queda como deducción, no como observación.
3. **Ruta «éxito inesperado en apertura negativa»: no ocurrió** en esta corrida. La regla R2-B está implementada y forzada estructuralmente (helper con Ledger), pero su ejecución efectiva no se observó — se declara como ruta no ejecutada por ausencia del suceso.
4. Entorno único (Linux 6.1.158+/x86_64/glibc 2.36); no Android/Termux, no kernels sin `renameat2`, no euid≠1001, no sonda bajo seccomp (la rama «sonda inconclusa» es code-path, no observación).
5. Atacante same-uid simulado en ventanas controladas; no root, no post-return sobre publicados, no DoS, no señales.
6. R-13: el MECANISMO por descriptores pasa en el arnés; la observación con motor real (`candidates/<grupo>/`) sigue pendiente de fase autorizada. Rendimiento no medido (R-15). Hashes G1 no ejercitados aquí — no se declara verificación de hashes.
7. F4 asimilación declarada: `fd_dir` de la prueba juega el rol de `fd_pub` del plan (no hay publicación real en F4).

## 12. Declaración expresa

**No se modificó ni ejecutó producción.** El arnés no importa ningún módulo de producción; `gh api` del commit acredita 0 archivos bajo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/` y que sólo los 2 archivos autorizados cambiaron; `lectura_segura_6g1.py` intacto; ningún motor ejecutado; cero audio real, Android/Termux, FLOW-5..8, EVO/MQR, `main`, merge/cherry-pick; PR #2 intacto; el plan v2.3 y los documentos de adjudicación anteriores sin cambios. **No se declara verificación de hashes G1** (no formó parte de F1..F6); las identidades comparadas son `(st_dev, st_ino)` por `fstat` y contenidos por re-lectura exacta. No se declara validada ninguna rama que no se haya ejecutado (§11.2–11.4).

— Fin del informe FEASIBILITY-1-R2. Parada obligatoria: publicado y detenido a la espera de la adjudicación final de Cris. Esta fase valida mecanismos aislados; NO autoriza implementación, integración ni ejecución de motores.
