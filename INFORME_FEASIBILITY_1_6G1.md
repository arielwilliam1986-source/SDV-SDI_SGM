# FEASIBILITY-1 (6G.1) — VALIDACIÓN EMPÍRICA AISLADA — v2 (RECTIFICACIÓN FEASIBILITY-1-R1)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena.
- **Naturaleza:** validación empírica **aislada** de los mecanismos del plan v2.3. **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción; cero ejecución de motores; cero audio real; cero Android/Termux; cero FLOW-5..8; cero EVO/MQR; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Historial:** v1 de este informe + arnés publicados en `a94f50793dfa97bb7074bb3e20fe2d42c3306596` (hijo de `2274862…`). **v2 = rectificación FEASIBILITY-1-R1** (hijo directo de `a94f507…`): sólo los dos archivos autorizados (`scripts/arnes_feasibility_1_6g1.py` y este informe). Los resultados de la ejecución anterior **se conservan íntegros en §10** (sin borrar ni ocultar).
- **Corrida final R1:** ts `2026-11-23T23:18:18Z` (run A) + corrida de reproducibilidad `23:18:31Z` aprox (run B, `--raiz /tmp/feas1_6g1_b`).

---

## 1. Commit padre exacto

- **FEASIBILITY-1 (v1):** `22748622830d1579d7814c51b1f048c58b121110` (verificado local = origin = `gh api`).
- **FEASIBILITY-1-R1 (esta fase):** `a94f50793dfa97bb7074bb3e20fe2d42c3306596` — verificado ANTES de trabajar: local = origin = `gh api` = `a94f507…` CONFORME, árbol limpio.

## 2. Commit final y archivos modificados

- **Commit de esta rectificación:** hijo directo de `a94f507…`; SHA completo en el informe de entrega (verificable vía `git`/`gh api`).
- **Archivos (exactamente los 2 autorizados):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py` (M) — arnés rectificado R1..R6.
  - `INFORME_FEASIBILITY_1_6G1.md` (M) — este informe.
- Evidencia JSON cruda: `/tmp/feas1_6g1/evidence/feas1r1_f{1..6}.json` + `consolidado_feasibility_1_r1.json` (run A) y `/tmp/feas1_6g1_b/evidence/…` (run B, reproducibilidad). El arnés regenera todo.

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
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_6g1
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_6g1_b   # reproducibilidad
```

## 5. Fixtures sintéticos (sin cambios de fondo; una corrección metodológica en F3)

- WAV: ruido blanco PRNG (`20261122` F3; `19480720` F6), 0.30, estéreo, PCM_16, 44100/8000 Hz. **F3 v2:** la señal se recorta a `[-0.999, 0.999]` ANTES de escribir (justificación: libsndfile **recorta** muestras float >1.0 al convertir a PCM_16 — observado en la rectificación, §9.2); el esperado de la comparación es la señal recortada.
- NPY float32 `(1024,2048)` / `(256,512)` con valores sembrados; payloads ASCII. Cero audio real.

## 6. Correcciones R1..R6 aplicadas al arnés

| ID | Corrección | Implementación |
|---|---|---|
| **R1** | Agregación real de veredictos | cada subpaso lleva `obligatorio=True/False` + booleano; `_agregar_veredicto` calcula el veredicto global: PASS ⇔ 0 obligatorios fallidos; excepción inesperada ⇒ FAIL (capturada con traceback); UNKNOWN sólo con condición explícita (F2 procfs ausente; F5 renameat2 indisponible). `obligatorios_fallidos` queda registrado en cada JSON. |
| **R2** | Cierre y contabilización | clase `Ledger`: TODOS los `os.open` pasan por `led.abrir(etiqueta, fd, tipo)` — tipos `propio` / `duplicado` / `fdopen_cierra` / `biblioteca_cierra`; cierres por `led.cerrar` o `led.marcar_cerrado`; verificación final por `os.stat('/proc/self/fd/N')` directo (sin fd de listado) de CADA descriptor registrado; paso obligatorio `cierre_y_verificacion_de_todos_los_fds` en F2..F6 y `cierre_ordenado_y_sin_fugas` en F1. |
| **R3** | F2 separado | Parte A (procfs: 3 subpasos obligatorios) sólo si `/proc/self/fd` está montado; si no, condición UNKNOWN explícita. Parte B (variante sin procfs) se ejecuta SIEMPRE bajo **guardián runtime**: `os.open/os.stat/os.listdir` parcheados para rechazar cualquier ruta `/proc/self/fd`; subpaso obligatorio `B_variante_sin_consultar_procfs_guardian` registra si el guardián disparó. Escenario «procfs realmente ausente» registrado como NO reproducible (subpaso no obligatorio, ok=False, declarado en evidencia). |
| **R4** | F3 contenido | comparación muestra a muestra contra la señal esperada (recortada) con tolerancia **1 LSB PCM_16 = 1/32768** (justificada: redondeo ≤ medio LSB = 1/65536; cota conservadora); `max_abs_diff` registrado; se mantienen `closefd=False` (identidad antes/después) y el comportamiento observado de `closefd=True` (EBADF). |
| **R5** | F4 en escenarios | **A: limpieza nominal v2.3** (masks con 3 entradas → `unlinkat` vía `fd_masks` → `rmdir` vía descriptor del PADRE acreditado — `fd_dir` asume el rol de `fd_pub`, declarado en la evidencia); **B: sustitución por symlink** (el nombre `masks2` → symlink a directorio AJENO: rmdir sobre el nombre falla seguro y el ajeno queda intacto; apertura O_NOFOLLOW rechaza; el real retenido por `fd_masks2` no se redirige; eliminación por fd del real; unlinkat del enlace elimina EL ENLACE, no el destino); **C: errores** (ENOTEMPTY, ENOENT). Ya no se presenta `masks_real` como equivalente de la secuencia nominal. |
| **R6** | Coherencia F1/F5 | F1: el descenso valida identidades (`identidades_validadas` obligatorio) y las entradas inesperadas se clasifican contra el conjunto exacto esperado. F5: los 4 controles (publicación, colisión, sustitución, fuera-del-padre) + disponibilidad + cierre son obligatorios. R-31 conservado como observación («la detección es POST-rename; NO es garantía de publicación atómica»). |

## 7. Resultados R1 — subpasos individuales y veredictos globales calculados

**Run A (ts `2026-11-23T23:18:18Z`): 45/45 subpasos obligatorios OK · 60 descriptores registrados · 0 residuales · 6/6 PASS. Run B: idéntico 6/6 PASS (reproducibilidad confirmada).** `obligatorios_fallidos=[]` en las 6 pruebas.

**F1 — R-13 → PASS** (9 pasos; 9 obligatorios; 9 fds registrados; 0 residuos): base acreditada → candidates creado/acreditado → 2 grupos dos niveles (identidad fstat) → descenso sin rutas + **identidades validadas** → symlink rechazado (ENOTDIR observado) → inesperados clasificados (`['evil','suelto.txt']`) → sustitución detectada por identidad (fd≠nombre) → cierre ordenado sin fugas.

**F2 — R-29 → PASS** (8 pasos; 6 obligatorios; 6 fds; 0 residuos): procfs disponible (no obligatorio) → A: magic-link designa el objeto / vivo tras unlink / desaparece al cerrar (ENOENT) → B: guardián sin disparos (0 consultas procfs) / alternativa con contenido e identidad verificados → `escenario_procfs_realemente_ausente`: **NO reproducible** (no obligatorio; declarado). Veredicto global PASS con procfs presente; si procfs no estuviera montado, la parte A produciría UNKNOWN (condición explícita) y la parte B se ejecutaría igualmente.

**F3 — R-34 → PASS** (6 pasos; 6 obligatorios; 7 fds; 0 residuos): escritor por fd `closefd=False` con identidad conservada (`format='WAV'` exigido por fd) → lector por fd (forma 44100×2) → **contenido: `max_abs_diff=3.0514e-05 ≤ 3.0518e-05` (1 LSB PCM_16, cota conservadora)** → `closefd=True` cierra el fd propio (EBADF observado, marcado `biblioteca_cierra`) → open_memmap vía procfs (identidad + valor 3.25) → ledger completo.

**F4 — P-08/R-28 → PASS** (11 pasos; 11 obligatorios; 11 fds; 0 residuos): A nominal (unlinkat vía `fd_masks` + rmdir vía padre acreditado + verificación de eliminación) → B: rmdir sobre nombre-symlink **falla seguro** (errno 20 observado) y ajeno intacto / apertura O_NOFOLLOW rechaza / real no redirigido / eliminación por fd del real / symlink presente y no seguido / unlinkat del enlace NO del destino / ajeno intacto → C: ENOTEMPTY + ENOENT → ledger.

**F5 — R-D → PASS** (6 pasos; 6 obligatorios; 18 fds; 0 residuos): renameat2 disponible → publicación con `fstat(fd_pub)==identidad` → colisión EEXIST con destino intacto → sustitución origen: impostor publicado, **detectado post-rename** (R-31: «NO es garantía de publicación atómica») y real localizable por fd → real fuera del padre: ENOENT con fd sobreviviente → ledger.

**F6 — cierre → PASS** (7 pasos; 7 obligatorios; 9 fds: 2 anclas, 1 log, 2 writers, 2 memmaps, 2 lectores; 0 residuos): apertura en orden registrada → anclas conservadas → etapas de cierre (writers→memmaps→lectores→log→anclas inversas) verificando **por fd conocido** (stat directo) que cada cierre desaparece y que los demás PERMANECEN.

## 8. Descriptores abiertos, cerrados y residuos (R2)

| Prueba | Registrados (tipos) | Cerrados explícitos | Cerrados por biblioteca/fdopen | Residuos |
|---|---|---|---|---|
| F1 | 9 (propios) | 9 | 0 | 0 |
| F2 | 6 (propios + 1 duplicado) | 4 + fd_dir | 1 (dup→fdopen) | 0 |
| F3 | 7 (propios + 1 duplicado) | 5 | 1 (dup→fdopen) + 1 (`closefd=True` de libsndfile) | 0 |
| F4 | 11 (propios) | 11 | 0 | 0 |
| F5 | 18 (propios) | 18 | 0 | 0 |
| F6 | 9 (propios; log vía fdopen) | 8 + log | 1 (fdopen) | 0 |
| **Total** | **60** | — | — | **0** |

En modo fd, libsndfile opera sobre NUESTRO descriptor (no se observaron fds internos adicionales de biblioteca; la verificación por etapas de F6 lo muestra: cada etapa elimina exactamente sus fds). No se declaran «sin fugas» más allá de los descriptores contabilizados; el ledger de cada prueba exige 0 residuos registrados y su verificación es un subpaso obligatorio.

## 9. Excepciones observadas y diferencias documento↔probado

**9.1 Excepciones observadas en la corrida final** (todas esperadas y documentadas): ENOTDIR(20) open/rmdir sobre symlink-nombre con O_DIRECTORY/O_NOFOLLOW; ENOENT(2) magic-link tras close, real fuera del padre, unlink inexistente, lstat tras rmdir; EEXIST(17) colisión; EBADF(9) fstat tras `sf.close()` con `closefd=True`; ENOTEMPTY(39) rmdir con contenido.

**9.2 Fallos del PROPIO arnés detectados por la agregación R1 durante la rectificación** (evidencia de que la metodología corregida funciona; NO son hallazgos sobre producción): (a) F1 v1 registraba `symlink_rechazado ok=False` sin afectar el veredicto (PASS injustificado) — corregido; (b) dup con offset compartido → EOF de `read_array` — corregido con `lseek(0)`; (c) **libsndfile recorta muestras >1.0 en PCM_16** (max_abs_diff 0.416 con fixture sin acotar) — fixture acotado a ±0.999 y comparación contra la señal recortada; (d) doble cierre / fstat tras cerrar (EBADF) por orden de evaluación — corregido; (e) `fd_padre` (F5), `fd_base` (F3/F4) y writers/memmaps/lectores (F6) sin contabilizar/cerrar — corregidos con ledger.

**9.3 Diferencias documento↔probado (precisiones para la próxima adjudicación; el plan v2.3 NO se modifica aquí):**
1. Escritura por fd exige `format='WAV'` (P-03 no lo explicitaba); lectura por fd NO acepta format/samplerate/channels (auto-detección).
2. `closefd=True` cierra el fd propio (EBADF): el diseño fija `closefd=False` — ahora con evidencia.
3. `np.memmap(file object)` exige fd **O_RDWR** (EACCES con O_WRONLY); `open_memmap('/proc/self/fd/N')` no lo exige sobre el fd retenido (numpy abre su propio fd por magic-link).
4. El errno de rechazo de symlink es **ENOTDIR (20)** en este kernel (no ELOOP); el rechazo fail-closed se mantiene.
5. **libsndfile recorta a ±1.0 en PCM_16**: para la fase de implementación, los fixtures/validaciones de contenido deben acotar el rango.
6. Un `os.dup` comparte offset con el original: cualquier relectura por duplicado debe rebobinar (o usar `pread`).
7. La detección de fugas por listado de `/proc/self/fd` produce falsos positivos (fd transitorio del listado): el ledger usa `os.stat` por fd conocido.
8. Confirmaciones sin diferencia: identidad (dev,ino) conservada en todas las operaciones por descriptor; magic-link designa el objeto; RENAME_NOREPLACE atómico (EEXIST); detección post-rename (R-31); orden de cierre verificable por etapas.

**9.4 Separación evidencia observada vs deducción:** lo OBSERVADO son los subpasos de §7 con sus valores (identidades `(dev,ino)`, errno, max_abs_diff, disparos del guardián, etapas de cierre). Son DEDUCCIÓN (y se etiquetan como tales): la generalización a entornos no probados, la ausencia de fugas «en general», y cualquier afirmación del plan no ejercitada aquí (hashes G1, compuertas del motor real, R-13 con motor).

## 10. Trazabilidad de la ejecución anterior (a94f507) — conservada

La corrida v1 (ts `2026-11-23T23:01:31Z`, commit `a94f507`) produjo **6/6 PASS** con la metodología v1: F1 (9 pasos) · F2 (5) · F3 (5) · F4 (7) · F5 (5) · F6 (8). Sus resultados **no se retiran**: se reevalúan bajo la metodología R1, que identificó estas deficiencias metodológicas (corregidas en v2): veredictos no agregados sobre todos los subpasos obligatorios (p. ej. F1 `symlink_rechazado ok=False` no impedía PASS); ledger de descriptores incompleto (fds auxiliares sin registrar: `fd_base` en F3/F4, `fd_padre` en F5; writers/memmaps/lectores cerrados sin actualizar el ledger en F6); F2 dependía de procfs para ejecutar la variante alternativa sin guardián; F3 verificaba sólo forma, no contenido; F4 presentaba `masks_real` como equivalente de la secuencia nominal. La evidencia v1 (`/tmp/feas1_6g1/evidence/feas1_f*.json`) fue regenerada por la corrida R1 en el mismo arnés (los JSON v1 no se conservan en disco; sus resultados quedan registrados en este informe y en el commit a94f507).

## 11. Limitaciones y escenarios no reproducidos

1. **Escenario «procfs realmente ausente»: NO reproducible en este sandbox** (procfs montado). Lo probado es el mecanismo B SIN CONSULTAR procfs (guardián runtime), que **NO equivale** a ejecutar con procfs ausente (R3). Este escenario queda UNKNOWN/declarado, no PASS.
2. Entorno único (Linux 6.1.158+/x86_64/glibc 2.36); no Android/Termux, no kernels sin `renameat2`, no euid≠1001.
3. Atacante same-uid simulado en ventanas controladas; no root, no post-return sobre publicados, no DoS, no señales.
4. R-13: el MECANISMO por descriptores pasa en el arnés; la observación con motor real (`candidates/<grupo>/`) sigue pendiente de fase autorizada.
5. Rendimiento no medido (R-15). Hashes G1 no ejercitados aquí (mecanismo de P-05, fuera de F1..F6) — no se declara verificación de hashes.
6. F4 asimilación declarada: `fd_dir` de la prueba juega el rol de `fd_pub` del plan (no hay publicación real en F4).

## 12. Declaración expresa

**No se modificó ni ejecutó producción.** El arnés no importa ningún módulo de producción; `gh api` del commit acredita 0 archivos bajo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/` y que sólo los 2 archivos autorizados cambiaron; `lectura_segura_6g1.py` intacto; ningún motor ejecutado; cero audio real, Android/Termux, FLOW-5..8, EVO/MQR, `main`, merge/cherry-pick; PR #2 intacto; el plan v2.3 y los documentos de adjudicación anteriores sin cambios. **No se declara verificación de hashes G1** (no formó parte de F1..F6); las identidades comparadas son `(st_dev, st_ino)` por `fstat` y contenidos por re-lectura exacta.

— Fin del informe FEASIBILITY-1-R1. Parada obligatoria: publicado y detenido a la espera de la adjudicación de Cris. Esta fase valida mecanismos aislados; NO autoriza implementación, integración ni ejecución de motores.
