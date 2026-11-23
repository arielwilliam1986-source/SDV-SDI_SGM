# RECTIFICACIÓN TÉCNICA DEL PLAN DE INTEGRACIÓN HARDENED FLOW-1..4 — 6G.1 (SÓLO DISEÑO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **exclusivamente diseño y documentación**. No autoriza implementación. Cero modificaciones de producción; cero ejecución de motores; cero pruebas adicionales; cero audio real.
- **Fecha:** 23-11-2026. **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Commit padre obligatorio:** `cea6652893b3f790b3c47aaab430ef99554c9d00` — verificado ANTES de trabajar: local = origin = `gh api` = `cea6652…` CONFORME. Este informe se publica en un **commit hijo directo de `cea6652`**.
- **Documento rectificado:** `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (v1 en `cea6652` → **v2** en este commit). Este informe registra qué cambió, por qué, y las fuentes.

---

## §0 Adjudicación que se atiende

Cris **acepta el plan v1 como base de diseño** y **no autoriza implementación**. La rectificación exige cuatro precisiones: **A** orden de cierre y verificación; **B** identidad real del descriptor de escritura; **C** anclaje de subdirectorios; **D** publicación y modelo de amenazas. Todas las afirmaciones de este informe están clasificadas (DEMOSTRADO / DOCUMENTED_FACT / PROPUESTO / DESCONOCIDO).

## §1 RECTIFICACIÓN A — Orden de cierre y verificación (afecta P-08 y el diagrama §7)

**Secuencia inequívoca (PROPUESTO, P-08 v2):**

1. **Finalizar todas las escrituras** de datos: streaming OLA completamente volcado a los escritores WAV; últimas escrituras de los 6 memmaps; `analysis.json`/`analysis.txt`/`input_integrity_6g.json` escritos (buffers Python vaciados con `flush` → syscall `write`).
2. **Cerrar y acreditar** los recursos de escritura, en este orden: escritores WAV (`SoundFile.close()` → `flush()` + `sf_close`, que escribe la cabecera WAV final — DOCUMENTED_FACT soundfile.py L1230–1236) y a continuación su fd propio (entregado con `closefd=False`, P-03 [R-B]); memmaps (`mm.flush()` → `msync` del mapeo, cierre del mmap, y **después** el fd retenido); lectores (mix/guías); `Tee.close()` con contrato R-17 (`error_cierre_6g1`, reintentos); fds propios de JSON/TXT/log. **Cualquier error de cierre eleva `CierreNoAcreditado6G1` → protocolo de aborto (P-02): la corrida jamás alcanza la compuerta ni publica.** Estado vigente ya demostrado: cierre con `errores=0` en FLOW-2/FLOW-3.
3. **`fd_run` y `fd_padre` (y `fd_masks`) permanecen abiertos** — son el ancla para los pasos 4–7.
4. **Primera compuerta de integridad** (P-05, sólo lectura): tipos, rechazo de symlinks/inesperados, obligatorios no vacíos, identidad vs registro propio, SHA G1 delimitado, y condición **«cero descriptores de escritura abiertos hacia el provisional»** (`escritura_abierta_bajo_dir_6g1`, LS L1115 — acredita que el conjunto inspeccionado está estático).
5. **Publicar** (P-06: `renameat2` relativo a `fd_padre` + acreditación post-rename `fstat(fd_pub)==I_run`).
6. **Segunda compuerta** sobre `fd_pub` (ventana compuerta→rename, R-24).
7. **Cierre del anclaje** (acreditado): `fd_pub` → `fd_masks` → `fd_run` → `fd_padre`.
8. **Sólo entonces `EXIT_OK`** (condición completa en P-08: paso 2 sin errores ∧ paso 4 válido ∧ paso 5 con identidad verificada ∧ paso 6 válido ∧ sin `ABORT_6G1.json` en el publicado).

**Justificación del tratamiento de flush y cierres de bibliotecas:**
- **Flush** (vaciar buffers de proceso → kernel) es obligatorio en el paso 1; el paso 2 añade la finalización **estructural** de cada formato (cabecera WAV en `sf_close`; `msync` del mapeo). Un recurso sin acreditación de cierre bloquea la corrida (fail-closed, vigente).
- **Cierre de bibliotecas**: `sf_close` (libsndfile) es la ÚNICA operación que completa las cabeceras WAV; por eso el paso 1 «finaliza escrituras de datos» y el paso 2 «cierra bibliotecas» — la compuerta exige los artefactos ya finalizados (por eso va DESPUÉS del paso 2, nunca antes).
- **fsync**: PROPUESTO opcional por artefacto (durabilidad ante crash del SO; no aporta integridad frente a mismo-uid y no es precondición de la compuerta) — R-33.
- **Errores de cierre**: ya hoy elevan `CierreNoAcreditado6G1` (H L1408–1428, L1950–1956); en la secuencia v2 ese error interrumpe ANTES del paso 4 → aborto por descriptor → rc≠0. Ninguna ruta convierte un fallo de cierre en éxito.

**Prohibición de escrituras posteriores a la compuerta final (paso 6):** tras el paso 6 no existe ninguna escritura de contenido; la única excepción es `ABORT_6G1.json` vía `fd_pub` (y vía `fd_run` si el real ≠ publicado) **si el paso 6 falla** — registro de aborto, no de resultado — con rc≠0. Consecuencia (límite aceptado, **R-32**): el `engine_log` termina en el paso 2, por lo que el veredicto de las compuertas vive en la salida estándar directa y en el ABORT (si falla), no en el log. El diagrama §7 v2 del plan incorpora la secuencia numerada (1)–(8) con esta prohibición explícita.

## §2 RECTIFICACIÓN B — Identidad real del descriptor de escritura (afecta P-03)

**Crítica aceptada:** el patrón v1 «crear con `O_EXCL`, **cerrar** y reabrir por ruta» **no** acredita el descriptor que la biblioteca usa internamente: la re-apertura por ruta re-resuelve la cadena y puede designar otro objeto (exactamente la clase de fallo de C). El patrón queda **sustituido** por **fd-passthrough** (P-03 v2): crear con `openat(O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=acreditado)` → `fstat(fd)` (identidad del fd devuelto: garantía del kernel, sin ventana) → **entregar ESE fd a la biblioteca** → toda la escritura ocurre sobre él → `fstat` de acreditación tras el ciclo si procede. La «verificación posterior de la ruta» **deja de invocarse como prueba**.

**Análisis individual (DOCUMENTED_FACT — fuente vigente del venv, citada por archivo:línea; sin ejecución):**

| Caso | ¿Acepta fd/file object? | ¿`/proc/self/fd/N` viable? | ¿Exige ruta? | ¿Duplica/conserva/cierra? | TOCTOU residual | Acreditación del descriptor interno |
|---|---|---|---|---|---|---|
| **soundfile/libsndfile — escritores WAV** | SÍ: fd int → `sf_open_fd(fd, mode, info, closefd)` (soundfile.py L1255–1256); file object → `sf_open_virtual` (callbacks read/seek/write/tell sobre el objeto, sin tocar fds) | innecesario | NO (con fd) | **conserva** el fd entregado; NO duplica; con `closefd=False` libsndfile NO lo cierra en `sf_close` (closefd se pasa íntegro L1256; default True → **el diseño fija `closefd=False`** para retener y acreditar el fd) | **ninguna** (un fd no puede re-dirigirse) | `fstat(fd)` previo == identidad del `openat O_EXCL`; el fd entregado ES el descriptor interno de libsndfile → **COMPLETA** |
| **soundfile — lectores (post_wav)** | SÍ (mismo mecanismo, modo `r`) | innecesario | NO | conserva/no cierra con `closefd=False` | ninguna | idem → **COMPLETA** |
| **numpy `open_memmap`** (masks) | **NO**: exige ruta — escribe la cabecera `.npy` con `open(filename,'w+b')` y luego `np.memmap(filename,…)` (numpy/lib/format.py) | **SÍ**: `/proc/self/fd/<fd_retenido>` — el magic-link resuelve al **objeto designado por el fd retenido** (no a la cadena nominal); los `open()` internos de numpy caen en el inodo correcto; el `mmap` queda anclado al inodo | SÍ (intrínseco a open_memmap) | numpy abre/cierra SUS file objects sobre la ruta procfs; el fd retenido es del motor y numpy no lo toca; el mapeo mantiene referencia propia al inodo | **ninguna** respecto de la ruta nominal; **dependencia de procfs** (R-29; fail-closed si no hay `/proc`) | `fstat(fd_retenido)` acreditado al crear + el mapeo nace del magic-link de ESE fd → **ACOTADA-COMPLETA** |
| **numpy `np.memmap` directo** (alternativa sin procfs) | SÍ: file object (`nullcontext` — NO lo cierra, memmap.py L227–231) + `mmap.mmap(fid.fileno(),…)` (L268) | innecesario | NO | conserva el objeto; motor lo cierra acreditado | ninguna | cabecera `.npy` previa con `np.lib.format.write_array_header_1_0` sobre `fdopen(fd)` + `fstat` → **COMPLETA** |
| **Tee / engine_log** | SÍ: `os.fdopen(fd, "w", encoding="utf-8")` | innecesario | NO | fdopen **toma posesión** del fd y lo cierra al `close()` (contrato R-17 preservado) | ninguna | `fstat(fd)` previo → **COMPLETA** |
| **JSON y archivos de texto** (`analysis.json`, `analysis.txt`, `input_integrity_6g.json` + re-lectura) | SÍ: `fdopen` para escribir; re-lectura con `os.pread(fd,…)` sobre el mismo fd (elimina la re-apertura por ruta H L1963) | innecesario | NO | idem fdopen | ninguna | `fstat(fd)` previo; pread no re-resuelve nada → **COMPLETA** |
| **matplotlib PNG** (`savefig`) | la API acepta file object pero **no probado** | — | hoy por ruta (H L2204) | — | por ruta | ninguna hoy → **LIMITACIÓN/UNKNOWN** (R-12; artefacto OPCIONAL fuera del conjunto obligatorio) |

**No se presenta ninguna verificación posterior de ruta como prueba del descriptor interno.** Donde no existe garantía completa (único caso obligatorio: `open_memmap` exige ruta), queda clasificado expresamente como **limitación con alternativa compatible**: (i) fd retenido + `/proc/self/fd/N` (dependencia procfs declarada, R-29) o (ii) reconstrucción manual de la cabecera `.npy` + `np.memmap(file object)` (sin procfs). La elección entre (i) y (ii) se toma en la fase de implementación; ambas fallan cerradas. Dependencia por versión de las bibliotecas: **R-34** (re-verificación documental en upgrades).

## §3 RECTIFICACIÓN C — Anclaje de subdirectorios (afecta P-01/P-03/P-05/P-09)

**Alcance en Hardened FLOW-1..4:** el único subdirectorio real es **`masks/`** (H L1615–1616; 6 memmaps L1628–1639). **`candidates/` NO existe en Hardened** (los WAV de candidatos van al raíz con prefijo «Track», H L1387–1401; R-13 — subdirectorios de dos niveles con nombres fijos — aplica a MQR). El patrón se define genéricamente para que cualquier subdirectorio futuro (o `candidates/` bajo MQR) lo reutilice.

**Diseño [R-C] (PROPUESTO):**
1. **Creación exclusiva relativa a `fd_run`**: `os.mkdir("masks", 0o700, dir_fd=fd_run)` — un solo componente, exclusivo; colisión → fail (nunca reutilizar).
2. **Apertura** `fd_masks = os.open("masks", O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_run)` — el componente final protegido por O_NOFOLLOW; **no hay componentes intermedios** porque la apertura es relativa a un descriptor ya acreditado.
3. **Acreditación**: `fstat(fd_masks)` → `I_masks` registrada por identidad (P-07).
4. **Retención**: `fd_masks` permanece abierto desde la creación hasta el cierre determinista (se integra al ancla; P-09).
5. **Archivos relativos al subdirectorio**: los 6 memmaps se crean con `openat(nombre, O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=fd_masks)` + fd retenido (P-03 [R-B]).
6. **Rechazo de sustituciones por symlink**: `O_NOFOLLOW` en la apertura del subdirectorio y de cada entrada; la compuerta (P-05) desciende **por `fd_masks`** (listdir(fd)+lstat(dir_fd)) y rechaza symlinks/tipos inesperados dentro.
7. **Cierre determinista y orden**: memmaps (flush+mmap close) → fd_mm retenidos → `fd_masks` → (tras publicación y verificación) `fd_pub` → `fd_run` → `fd_padre` (P-09). En aborto, `fd_masks` acompaña al ancla en `preparar_aborto_6g1`.

**Regla de cadena acreditada [R-C] (exigida por la adjudicación):** `O_NOFOLLOW` protege **sólo el componente final** de una ruta; los componentes intermedios de una cadena absoluta o multi-componente NO están protegidos. Por tanto: **prohibido abrir rutas multi-componente** (`os.path.join(run_dir, "masks", "x.npy")` — patrón vigente H L1628) y **obligatorio** abrir componente a componente, cada uno relativo a un descriptor acreditado (`fd_padre → fd_run → fd_masks → archivo`). Ningún componente intermedio queda «no acreditado»: la cadena completa vive en descriptores.

## §4 RECTIFICACIÓN D — Publicación y modelo de amenazas (afecta P-06)

**Crítica aceptada:** el origen de `renameat2` sigue siendo un **nombre relativo** aunque se use `fd_padre`. El kernel resuelve `nombre_prov` **dentro del directorio designado por `fd_padre` en el instante de la llamada**; si la entrada fue sustituida antes, el objeto movido es el sustituto. **No se afirma que renameat2 relativo a dirfd constituya una publicación atómica por identidad del descriptor origen.** Lo que el diseño garantiza es el par **«RENAME_NOREPLACE del destino + acreditación de identidad POST-RENAME»** (`fstat(fd_pub)` contra `I_run` — identidad≠ruta).

**Análisis expresamente exigido (tabla completa en §8 del plan v2):**
1. **Sustitución del nombre provisional antes de renameat2** → el impostor es renombrado al nombre final; el paso 3 (`fstat(fd_pub) != I_run`) lo detecta → **sin EXIT_OK**; ABORT vía `fd_pub` dentro de lo publicado (queda marcado «nunca corrida exitosa») + ABORT vía `fd_run` en el REAL (el descriptor designa el inodo real esté donde esté) + rc≠0 (**R-31**).
2. **Renombrado del directorio real fuera del padre** → `renameat2` falla con **ENOENT** (el nombre ya no está en el padre) → sin EXIT_OK; ABORT vía `fd_run` en el real (sobrevive al movimiento); rc≠0.
3. **Recreación del nombre provisional con otro objeto** → idéntico al caso 1 (el rename mueve el objeto nuevo; la acreditación post-rename falla).
4. **Verificación posterior `fd_pub` vs `I_run`** → es la acreditación que habilita los pasos 6–8; se ejecuta sobre el objeto **publicado** (apertura con `O_DIRECTORY|O_NOFOLLOW` relativa a `fd_padre`), nunca sobre una re-resolución de cadena.
5. **El objeto real puede permanecer fuera del destino publicado** (casos 1–3) → el motor **NO reintenta** moverlo al destino (otro rename sería igualmente susceptible y podría reemplazar objetos). Garantizado: nunca EXIT_OK; ABORT en el real vía `fd_run`; ABORT en lo publicado vía `fd_pub`; rc≠0. Limitación declarada (**R-31**): ante same-uid puede quedar basura con el nombre final — el motor jamás la avala; recomendación operativa: el consumidor debe exigir ausencia de `ABORT_6G1.json` y verificar identidad externamente.
6. **Fail-closed en cada caso** → tabla §8 v2 (caso 6: renameat2 indisponible/EIO/agotamiento → `PUBLICACION_SEGURA_FALLIDA` → aborto por descriptor, provisional conservado, rc≠0).

**Qué garantiza realmente el diseño y qué exige limitar el modelo de amenazas:**
- **Garantiza (PROPUESTO):** toda escritura ocurre sobre fds acreditados (no re-dirigibles); el aborto se registra en el objeto real por descriptor (D1); ningún conjunto no verificado se publica con éxito (C); el objeto publicado fue el acreditado **en el instante de la verificación** (pasos 3 y 6); tras el paso 6 no hay escrituras; todo fallo produce rc≠0 con ABORT en los objetos reales alcanzables por descriptor.
- **NO garantiza (límites declarados):** que el nombre final siga designando el objeto verificado después del paso 6 (**R-30**, post-return/post-verificación); que no quede basura nominal ante same-uid (**R-31**); protección ante root, DoS, SIGTERM/SIGKILL (R-11), kernels sin `renameat2`-dirfd (fail-closed).
- **Aislamiento adicional** (mount namespaces, permisos del árbol de salida gestionados por el entorno, consumidor externo con atestación) **queda fuera del alcance 6G.1 actual** y se menciona sólo como frontera del modelo de amenazas, no como parte del diseño.

## §5 Cambios v1 → v2 (trazabilidad)

| Decisión | v1 | v2 (rectificada) |
|---|---|---|
| P-01 | ancla (fd_padre, fd_run, I_run) retenida | + subancla `fd_masks` + **regla de cadena acreditada componente a componente** [R-C] |
| P-02 | aborto por descriptor retenido | sin cambio funcional (integra subanclas) |
| P-03 | pre-creación O_EXCL → cerrar → reabrir por ruta → re-verificación | **REESCRIPTO [R-B]**: fd-passthrough (`openat O_EXCL` → `fstat(fd)` → entregar el fd a la biblioteca); por biblioteca: `sf_open_fd(closefd=False)`, `fdopen`, pread; memmaps vía `/proc/self/fd/N` (R-29) o cabecera manual; sin verificación por ruta como prueba |
| P-04 | lecturas post-escritura por ancla | precisado: post_wav con `sf_open_fd` lectura; pread en input_integrity |
| P-05 | compuerta de conjunto | + descenso por `fd_masks`; + condición «cero fds de escritura abiertos» (procfs) |
| P-06 | publicación por ancla + verificación post-rename | **REESCRIPTO [R-D]**: afirmación honesta (NO atomicidad por identidad del origen); tabla fail-closed de 6 casos; ABORT doble (fd_pub + fd_run) |
| P-07 | registro propio por identidad | sin cambio |
| P-08 | invariante EXIT_OK | **REESCRIPTO [R-A]**: secuencia obligatoria (1)–(8); prohibición de escrituras posteriores a la compuerta final; R-32 |
| P-09 | cierre acreditado extendido | + subanclas; orden completo incl. fd propio tras mmap close |

Matriz FLOW-1..4: actualizada en §6 del plan (puntos de aplicación con líneas reales; `candidates/` inexistente en Hardened declarado). Diagrama §7 v2: secuencia numerada (1)–(8) + subanclas + prohibición. Riesgos: R-26 rectificado (ventana eliminada por fd-passthrough) y **nuevos R-29..R-34**. Regresión: **nuevos casos** REG-D1-d, REG-D1-e, REG-C-d, REG-C-e, REG-B-a (total 11).

## §6 Clasificación epistémica de la rectificación

- **DEMOSTRADO:** línea base y mecanismos D1/C (ya publicados).
- **DOCUMENTED_FACT (nuevo):** comportamiento de soundfile 0.13.1 (`sf_open_fd` L1255–1256 con `closefd`; `sf_open_virtual` con callbacks; `close()` = `flush()`+`sf_close` L1230–1236), numpy 1.26.4 (`np.memmap` file object vía `nullcontext` sin cerrar L227–231 y `mmap.mmap(fid.fileno())` L268; `open_memmap` exige ruta), `/proc/self/fd/N` como re-apertura del objeto designado por un fd (kernel Linux) — citado por archivo:línea en §2 y en §8bis del plan.
- **PROPUESTO:** toda la secuencia R-A, el fd-passthrough, las subanclas, la tabla fail-closed, schema `abort-6g1/4`, regresión ampliada y riesgos R-23..R-34.
- **DESCONOCIDO:** entornos sin procfs en producción (R-29), coste (R-15), upgrades de dependencias (R-34), EVO/MQR, señales no-Ctrl-C (R-11), atacantes fuera de las ventanas diseñadas.

## §7 Parada

Commit hijo directo de `cea6652893b3f790b3c47aaab430ef99554c9d00` con: este informe, el plan v2 rectificado, manifiesto y SHA-256 actualizados. **No se implementa nada. Parada obligatoria** a la espera de la adjudicación de Cris.
