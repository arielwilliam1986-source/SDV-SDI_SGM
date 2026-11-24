# DISEÑO TÉCNICO COMPLEMENTARIO PREINTEGRACIÓN — HARDENED 6G.1 — v1

- **Destinatario:** Cris (ChatGPT), responsable técnica y adjudicadora. **Ejecutor:** Arena.
- **Naturaleza:** documento de **diseño y documentación exclusivamente**. No modifica el motor, `lectura_segura_6g1.py`, el plan v2.3 ni ningún archivo; no ejecuta ni importa producción; no ejecuta pruebas, arneses ni fixtures; cero audio. **No implementa nada**: todo mecanismo futuro queda **PROPOSED** hasta su adjudicación.
- **Informe base:** `INFORME_AUDITORIA_ESTATICA_CORRESPONDENCIA_MOTOR_PLAN_6G1.md` (`2438559…`) y `COMPLEMENTO_ADJUDICACION_AUDITORIA_MOTOR_PLAN_6G1.md` (`1b9f5be…`). Este documento RESUELVE decisiones de diseño pendientes señaladas en el §8 de la auditoría, sin reescribirlos.
- **Etiquetas (esquema de 4, vigente desde el complemento):** **DOCUMENTED_FACT** (código vigente, con líneas) · **ADJUDICACIÓN** (decisión expresa de Cris) · **PROPOSED** (diseño futuro, no implementado) · **UNKNOWN** (sin evidencia).
- **Contexto aceptado:** plan v2.3 consolidado; FEASIBILITY-1-R2 aceptada (entorno Linux documentado); auditoría estática aceptada; complemento de adjudicación aceptado; alcance P-01..P-09 y FLOW-1..4 = `full_processing` exclusivamente; `single_pair` fuera con comportamiento preservado; SR-EI-1 adjudicado, PROPOSED y no implementado.

## A. SR-EI-1 — Continuidad de identidad de guías (diseño completo)

### A.1 Secuencia actual (DOCUMENTED_FACT, motor H sin modificar)

1. `probe_file(path, role)` — H L372: apertura ÚNICA `os.open(O_RDONLY|O_NONBLOCK)`; L378 `fstat` inicial; L379-382 exigencia de regular (fail-closed); **L383 `info.device, info.inode = st0.st_dev, st0.st_ino`** (la identidad queda conservada en `FileInfo`); L404 SHA estable por descriptor; L411-418 estabilidad fstat final; L420 `os.close(fd)` — el fd del probe es TRANSITORIO.
2. Guías: H L1522-1523 `p.vocal = validate_guide(probe_file(p.vocal_path, "vocal_guide"))` / `p.instrumental = validate_guide(probe_file(p.instrumental_path, "instrumental_guide"))`; `validate_guide` (L442-452) valida extensión/sample-rate/canales y no toca la identidad; `PairMeta.vocal/.instrumental` son `FileInfo` (L468-469).
3. Reapertura para el DSP: H L1697-1698 `sf.SoundFile(p.vocal.path)` / `sf.SoundFile(p.instrumental.path)` — **libsndfile abre SU PROPIO fd resolviendo la ruta nominal**; consumo en L1720-1721 vía `read_span` (L841-857: `handle.seek/read` sobre la API SoundFile); cierre L1878.
4. **Brecha (DOCUMENTED_FACT):** entre (2) y (3) no hay comparación `(st_dev, st_ino)` contra `FileInfo` — la reapertura no acredita el objeto validado. El patrón correcto existe para el Mix: `abrir_mix(..., identidad_esperada=(mix_info.device, mix_info.inode))` H L1687 → `MixHandle` LS L142/L152-158/L177 (fd propio + fstat + rechazo si identidad distinta) — pero NO se aplica a las guías.

### A.2 Secuencia propuesta S1..S8 (PROPOSED)

| # | Paso | Mecanismo | Clasificación |
|---|---|---|---|
| S1 | Conservar identidad inicial | ya existe: `FileInfo.device/.inode` (H L383); `validate_guide` no la altera | DOCUMENTED_FACT (base) / PROPOSED (uso) |
| S2 | Apertura controlada en el punto actual de las guías (posición H L1695-1698, tras `abrir_mix`) | `fd = os.open(p.vocal_path, os.O_RDONLY \| os.O_NONBLOCK)` — misma política H2-B del Mix (una FIFO no bloquea; el `fstat` siguiente clasifica). Sin `O_NOFOLLOW` para IGUALAR la política vigente de entradas de usuario (el probe también sigue enlaces legítimos, H L368-369: el anclaje es por identidad, no por no-follow) | PROPOSED |
| S3 | fstat del descriptor utilizado | `st = os.fstat(fd)`; exigir regular (`stat.S_ISREG`), fail-closed si no | PROPOSED |
| S4 | Comparación obligatoria con FileInfo | `(st.st_dev, st.st_ino) == (p.vocal.device, p.vocal.inode)` — identidad esperada conservada en S1 | PROPOSED (ADJUDICACIÓN B.3 del complemento) |
| S5 | Rechazo fail-closed | desigualdad, objeto no regular, o apertura fallida ⇒ aborto por protocolo único (A.5) | PROPOSED (ADJUDICACIÓN B.4) |
| S6 | Entrega del MISMO descriptor a soundfile | `rd = sf.SoundFile(fd, mode="r", closefd=False)` — el int fd va por `sf_open_fd`; sin re-resolver ruta alguna (A.3) | PROPOSED (ADJUDICACIÓN B.5) |
| S7 | Consumo DSP sin cambios | los handles pasan a exponer la misma API SoundFile (`seek/read/channels/frames`) que `read_span` ya usa (L841-857) — el punto de entrega único es la construcción del handle en S6 | PROPOSED |
| S8 | Cierre con propiedad definida | `rd.close()` (libsndfile finaliza; NO cierra nuestro fd con `closefd=False`) + `os.close(fd)` por el propietario (motor), en la posición actual de cierre de guías (H L1878) y en el camino de aborto vía `preparar_aborto` (A.4/A.6) | PROPOSED |

Contenedor propuesto: **`GuiaHandle`** que replica el contrato ya vigente de `MixHandle` (LS L127-288): `fd` propio + lector soundfile + `__getattr__` delegando la API + `close()` verificable idempotente con `_cierre_fallido_6g1` persistente (el primer fallo nunca se convierte en estado «cerrado»). Alternativa mínima: conservar el dict `handles` y añadir los fds a un registro paralelo de la corrida — rechazada en el diseño por dispersar la propiedad (riesgo de fuga en aborto). La forma EXACTA de `GuiaHandle` (firma, campos, mensajes) queda para la fase de implementación autorizada.

### A.3 Semántica REAL del mecanismo de entrega en soundfile 0.13.1 (DOCUMENTED_FACT por fuentes + arnés; explicación exigida)

soundfile 0.13.1 tiene **tres rutas de entrega** en `_open` (fuente `soundfile.py` L1240-1258, inspeccionada en fases previas; comportamiento observado además en el arnés FEASIBILITY-1 F3, espacio AISLADO):

1. **`str` (ruta):** `sf_open(ruta)` — libsndfile abre y cierra SU PROPIO fd resolviendo la ruta nominal. **Es la ruta vigente de las guías (H L1697-1698): ninguna garantía de identidad entre probe y lectura.**
2. **`int` (fd):** `sf_open_fd(file, mode, info, closefd)` — libsndfile **opera sobre ESE fd**: no duplica, no re-resuelve nada (no hay ruta en juego), y el binding kernel fd→objeto no puede re-dirigirse. Con `closefd=False`, `sf.close()` NO cierra el fd (el motor conserva la propiedad y el control del cierre). Con `closefd=True`, `sf.close()` CIERRA el fd propio (observado en arnés F3: EBADF en `fstat` posterior). **Es la única ruta donde el descriptor cuyo `fstat` se compara contra `FileInfo` (S3/S4) es literalmente el descriptor que libsndfile lee.**
3. **file object:** `sf_open_virtual` — callbacks read/seek/write/tell (VIO) sobre el objeto Python. libsndfile **nunca ve un fd**; la cadena de identidad sería callbacks→objeto→(si es `fdopen`) fd→inodo: más fuerte que una ruta, pero con capa de indirección Python y sin que «el mismo descriptor» sea literal. **Advertencia exigida por la adjudicación [DOCUMENTED_FACT lógico]:** pasar un objeto file-like NO demostraría por sí mismo que soundfile usa el mismo descriptor — con VIO la identidad depende de lo que el objeto encapsule, no de un fd entregado. Por eso el diseño elige la ruta **int fd** (ruta 2) como mecanismo primario: es la única que satisface literalmente «entrega del mismo descriptor» (ADJUDICACIÓN B.5).

Observaciones empíricas del arnés que sustentan S6 (FEASIBILITY-1, espacio AISLADO — NO es evidencia sobre el motor): lectura por fd con auto-detección funciona (no se pasa `format` — pasar `format` en lectura por fd eleva TypeError, observado); `closefd=False` conserva la identidad `(dev,ino)` tras `sf.close()`; el contenido se verifica con redondeo PCM_16. **Lo NO ejercitado en el arnés: lectura por fd de FLAC** (`ALLOWED_EXTENSIONS` admite .flac, H L113; el arnés sólo probó WAV) — UNKNOWN hasta prueba autorizada. En el motor vigente las guías se abren sin `format` (auto-detección, L1697), por lo que la migración a fd no cambia la política de detección (DOCUMENTED_FACT).

### A.4 Propiedad y cierre del descriptor (PROPOSED)

| Momento | Propietario del fd | Operación |
|---|---|---|
| S2 apertura | motor (corrida) | `os.open` + `fstat` + comparación — el fd nace YA siendo del motor |
| S6 entrega | soundfile OPERA sobre él; la propiedad sigue del motor (`closefd=False`) | `sf.SoundFile(fd, mode="r", closefd=False)` |
| DSP (L1720-1721) | motor | `read_span(handle, ...)` — lectura vía API del lector |
| Cierre éxito (posición H L1878) | motor | `rd.close()` (finaliza libsndfile; fd sobrevive) **y después** `os.close(fd)` — cierre ACREDITADO (registro verificable; un fallo ⇒ `CierreNoAcreditado6G1` camino vigente) |
| Aborto | motor vía `preparar_aborto_6g1` | `GuiaHandle.close()` verificable (incluido en `lectores=` junto a `hmix` y `handles`, como hoy H L2016-2017/L2029-2032/L2046-2050); el fallo marca `completo=False` ⇒ sin traslado |
| Fallo S2-S5 | motor | cierre determinista del fd antes de re-elevar (nunca llega al llamador abierto — patrón MixHandle L178-183) |

Punto de diseño conservado: las guías son ENTRADAS — su fd NO forma parte de las anclas de compuertas (no se retiene hasta gate-1/gate-2 ni hasta el paso 7 de P-08); su vida es exactamente el DSP. Esto delimita SR-EI-1 respecto de P-08/P-09 (los writers/memmaps/anclas SÍ permanecen).

### A.5 Errores y rechazo fail-closed (PROPOSED)

| Fallo | Detección | Consecuencia |
|---|---|---|
| `os.open` falla (ENOENT/EACCES/…) | S2 | `_FalloCorrida_6g1("GUIA_NO_ABIERTA_ANTES_DEL_DSP", detalle, trasladar=False)` — mismo patrón que `MIX_NO_ABIERTO_ANTES_DEL_DSP` (H L1691-1694): protocolo único, registro en el provisional, sin traslado, rc≠0 |
| Objeto no regular (p. ej. FIFO) | S3 fstat | mismo manejo (motivo específico en `detalle`) |
| Identidad `(dev,ino)` ≠ `FileInfo` | S4 | `_FalloCorrida_6g1("GUIA_SUSTITUIDA_ANTES_DEL_DSP", detalle, trasladar=False)` — análogo a `MIX_SUSTITUIDO_ANTES_DEL_DSP` (H L1688-1690) |
| Cierre no acreditado (éxito o aborto) | S8 / A.6 | `CierreNoAcreditado6G1` — sin publicación (camino vigente, H L1408-1424/L1927-1930) |

Los `motivo` exactos son PROPOSED y quedan sujetos a la convención de `FalloCorrida6G1` vigente; su texto final se fija en la fase de implementación autorizada.

### A.6 Integración con el protocolo de aborto y cierre de recursos (PROPOSED, sobre mecanismos vigentes)

- Fallos S2-S5 ocurren DESPUÉS de `create_run_dir` y `abrir_mix` (posición L1695-1698) ⇒ caen en el bloque protegido: cierre determinista (`preparar_aborto_6g1` → `cerrar_recursos_corrida_6g1` con runners/memmaps/lectores) → `abortar_corrida_6g1` con registro en el provisional y sin traslado — idéntico flujo a los fallos del Mix de hoy.
- `GuiaHandle` debe ser cerrable por `cerrar_recursos_6g1` (tiene `close()`; LS L847-863) y verificable por `cerrar_verificado_6g1` (estado físico + `_cierre_fallido_6g1`; LS L1155-1201). Hoy `handles` son `sf.SoundFile` y `_estado_fisico_6g1` usa `.closed` — `GuiaHandle` expondrá un estado físico equivalente (delegación + fd propio), detalle de implementación pendiente.
- En el aborto los fds de guías se cierran como lectores (no hay mapeos ni escritura) — no bloquean el traslado salvo fallo de cierre acreditado.

### A.7 Invariancia de muestras, canales, formatos, DSP y comportamiento acústico (PROPOSED como INVARIANTE de diseño)

- `read_span` (L841-857) no cambia: sigue recibiendo un objeto con API SoundFile y leyendo `float64` por bloques con seek — mismos bytes del mismo inodo, mismas muestras, mismos canales, mismos formatos.
- El DSP (STFT/máscaras/OLA/TruePeak/análisis) no se toca: SR-EI-1 sólo cambia CÓMO se obtiene el lector, no QUÉ se lee.
- Verificación de la invariancia: estática (diff de `read_span` y consumidor = vacío) + la regresión comparativa de B.6 (cuando se autorice). Hasta entonces: UNKNOWN como hecho ejecutado.

### A.8 Diferenciación epistémica exigida (4 niveles)

1. **Demostrado en FEASIBILITY-1 (espacio AISLADO, commits `a94f507`/`71d928b`/`ef90a45`):** lectura y escritura por fd int con `sf_open_fd` y `closefd=False` (identidad conservada); exigencia `format='WAV'` en escritura por fd; auto-detección en lectura por fd (TypeError con `format`); `closefd=True` cierra el fd propio (EBADF); contenido PCM_16 verificado con cota 1 LSB. **NO demostrado ahí:** FLAC por fd; comportamiento con `single_pair`; nada sobre el motor real.
2. **Observado en el motor actual (DOCUMENTED_FACT):** probe por descriptor con identidad conservada (L372/L383); reapertura de guías por ruta sin verificación (L1697-1698); patrón Mix/`MixHandle` con identidad exigida (L1687; LS L152-158); consumo vía `read_span` (L841-857/L1720-1721); cierre L1878; aborto con lectores (H L2016-2017).
3. **Propuesta de integración (PROPOSED):** secuencia S1-S8, `GuiaHandle`, ruta int fd + `closefd=False`, taxonomía de fallos A.5, propiedad A.4.
4. **Pendiente de prueba o decisión (UNKNOWN):** lectura de FLAC por fd; ejecución de la invariancia en el motor real; texto final de motivos de `FalloCorrida6G1`; forma exacta de `GuiaHandle`; si SR-EI-1 aplica también a `single_pair` (D, decisión P-2).

## B. Aislamiento de `full_processing` y `single_pair`

### B.1 Punto de separación de modos (DOCUMENTED_FACT base / PROPOSED diseño)

- Base: `full_mode = (mode == MODE_FULL_PROCESSING or mode == MODE_SINGLE_PAIR)` (H L1622) — hoy AMBOS modos recorren la misma ruta de escritura/publicación.
- Diseño propuesto: **UN ÚNICO punto de bifurcación** al final de `run_experiment`, delimitando los pasos NUEVOS de P-08/P-05: `if mode == MODE_FULL_PROCESSING: <secuencia P-08 con gate-1/5bis/gate-2/EXIT_OK condicionado>` `else: <secuencia vigente intacta (publicación por rutas L1984, rmtree masks con WARN L1994-2000, EXIT_OK incondicionado L2002)>`. El resto del flujo (creación, escrituras, DSP, guarda del mix, input_integrity) permanece compartido con adaptación mecánica (B.2).
- Justificación: minimizar la superficie de bifurcación (un solo `if` de modo en la secuencia final) y hacer verificable por diff que la rama `else` conserva las líneas vigentes.

### B.2 Clasificación de funciones compartidas (PROPOSED)

| Función (líneas vigentes) | Tratamiento propuesto | `single_pair` |
|---|---|---|
| `create_run_dir` (H L1430) | adaptación mecánica compartida (P-01: anclas retenidas vía parámetro opcional `retener_anclas=False` por defecto); `full_processing` pasa `True` | comportamiento observable idéntico (mismos nombres/_partial/_final; anclas no retenidas por defecto → P-01 NO se extiende) |
| `CandidateRunner.__init__` (L1396-1399), `_open_memmap` (L1456), `Tee`/`init_tee` (L173/L215), JSON/TXT (L2130/L2180/L1957) | adaptación mecánica compartida (P-03/P-04: fd-passthrough) — cambia el CÓMO interno, no el QUÉ observable | mismos artefactos, nombres, contenido y `rc`; verificado por B.6 |
| `post_wav_identity` (L1461/L1889) | compartida con P-04c; `single_pair` ejecuta full_mode ⇒ misma lectura por descriptor ( cambio transparente) | ídem |
| Compuertas P-05 (gate-1/gate-2), hash G1, matriz §8ter (`L_acept`), paso 5bis | **RAMIFICADO**: sólo en la rama `full_processing`; `L_acept` NO se deriva para `single_pair` (la derivación queda detrás del `if`) | NO hereda §8ter ni P-05 |
| Publicación P-06 (`_v2` por anclas + `fstat(fd_pub)==I_run`) | **RAMIFICADO**: rama `full_processing`; `single_pair` conserva `publicar_dir_6g1` vigente por rutas (L1984) | NO hereda P-06 |
| Aborto P-02 (`abortar_corrida_6g1_v2(fd_dir, fd_padre)`) | **RAMIFICADO**: handlers pasan anclas sólo si existen (rama `full_processing`); si `single_pair` no retiene anclas (B.2 primera fila), los handlers usan el protocolo VIGENTE por rutas | NO hereda P-02 |
| SR-EI-1 (guías) | compartido POR DEFECTO (requisito de integridad de entradas, no es compuerta) — **decisión pendiente** D/P-2 | propuesta: aplicar (fallo fail-closed sólo si hubo sustitución); pendiente adjudicación |

### B.3 Evitar herencia inadvertida de §8ter/P-05 (PROPOSED)

- La derivación de `L_acept` desde la matriz §8ter se codifica DENTRO de la rama `mode == MODE_FULL_PROCESSING` (no como función importable de alcance global); ninguna constante de §8ter se consulta fuera de esa rama.
- El paso 5bis y la condición de EXIT_OK quedan dentro de la misma rama; la rama `else` mantiene literalmente el código vigente (L1984-L2002).
- `preparar_aborto_6g1`/`abortar_corrida_6g1` reciben anclas SÓLO si el modo las retuvo (los `locals().get(...)` vigentes ya toleran ausencia); la variante `_v2` de P-02 se invoca sólo con anclas presentes.

### B.4 Comportamiento de `single_pair` a preservar (invariantes observables, PROPOSED)

1. Mismos artefactos y nombres (`<track_base> SDV/SDI.wav` en raíz, `candidates/…` con `--write-all-candidates`, `analysis.json/.txt`, `engine_log.txt`, `input_integrity_6g.json`, `masks/` según `--png/--keep-masks`, `png/` condicionado, publicación con sufijos `_r%03d`, `masks/` eliminada del publicado con WARN si falla).
2. Mismo `rc` en cada escenario (éxito/validación/procesamiento/aborto) y misma semántica de `ABORT_6G1.json` (schema abort-6g1/3).
3. Mismo contenido científico (`analysis.json` campo a campo).
4. Cambios PERMITIDOS (no observables): mecanismo interno de fds (P-03/P-04), registro por identidad, orden interno de cierre con acreditación — mientras los invariantes 1-3 se mantengan.

### B.5 Riesgos de bifurcar funciones o duplicar rutas (PROPOSED; mitigación)

| Riesgo | Mitigación |
|---|---|
| Deriva entre la rama `else` (vigente) y la rama nueva → dos semánticas de publicación/limpieza que divergen silenciosamente | un solo punto de bifurcación (B.1); verificación por diff de que la rama `else` es idéntica a las líneas vigentes; la rama nueva se construye sobre la misma `GuiaHandle`/anclas (sin duplicar helpers) |
| Duplicación de helpers (dos implementaciones de publicación/limpieza) | P-06 `_v2` y 5bis son funciones NUEVAS llamadas sólo desde la rama nueva; las vigentes (`publicar_dir_6g1`, `shutil.rmtree`) permanecen para `single_pair` sin modificar |
| Parámetro `retener_anclas` mal propagado → `single_pair` retiene anclas sin usarlas (fuga) o `full_processing` no las retiene (P-01 roto) | valor por defecto `False` (comportamiento vigente); el paso de `True` ocurre en un único punto (`run_experiment`); verificación de residuos de fds en la regresión B.6 |
| `full_mode` compartido oculta diferencias futuras | documentar en la propia rama el motivo del `if` (referencia a la ADJUDICACIÓN A del complemento) |
| SR-EI-1 cambia `single_pair` en el escenario de sustitución (antes silencioso, ahora aborto) | decisión explícita requerida (D/P-2) — no se introduce por defecto sin adjudicación |

### B.6 Verificación comparativa pre/post para `single_pair` (PROPOSED — **PENDIENTE DE AUTORIZACIÓN; NO EJECUTADA**)

Protocolo propuesto (sólo diseño): (1) ejecutar el motor vigente en `--mode single_pair` con fixture sintético fijo (sin audio real) y capturar: `rc`, árbol de artefactos, `analysis.json`, `engine_log.txt`, `input_integrity_6g.json`, hashes de WAV, presencia/ausencia de `masks/` publicado, formato de `ABORT_6G1.json` en un escenario de aborto; (2) repetir idéntico tras la integración; (3) comparar campo a campo (los campos temporales/`(dev,ino)`/timestamps varían por diseño). **Este protocolo NO se ejecutó aquí y NO se autoriza por este documento** — requiere adjudicación expresa de Cris (fixtures, entorno, momento). Hasta entonces, la preservación de `single_pair` es un requisito de diseño (PROPOSED) con verificación UNKNOWN.

## C. Integración con P-01..P-09 (secuencia coherente)

### C.1 Orden de dependencias actualizado (PROPOSED; sustituye/refina el §9 de la auditoría)

1. **P-01 + P-07** (anclas retenidas + registro por identidad) — fundación.
2. **P-03** (fd-passthrough a bibliotecas: writers, memmaps, Tee, JSON/TXT).
3. **P-04** (lecturas post-escritura por descriptor: pread, post_wav, TXT desde memoria).
4. **SR-EI-1** (S1-S8 de §A: entradas con identidad continua) — usa el mecanismo de P-03 para ENTRADAS; no depende de compuertas; se integra con el cierre/aborto vigente (A.6).
5. **P-09** (subanclas `candidates/` + órdenes de cierre; extiende `preparar_aborto`).
6. **P-06** (publicación por anclas + `fd_pub` + `fstat(fd_pub)==I_run`).
7. **P-08 + P-05** (reordenación y compuertas gate-1/5bis/gate-2 + hashes G1; un solo paso; rama exclusiva `full_processing`).
8. **P-02** (aborto por descriptor retenido; último, consume anclas de P-01 y la secuencia de P-08/P-09).

El aislamiento de modos (§B) es transversal: se define ANTES del paso 1 como decisión de diseño y se materializa en el paso 7 (bifurcación única).

### C.2 Ciclo de vida completo de descriptores (PROPOSED; consolidación)

| Descriptor | Creación | Uso | Cierre |
|---|---|---|---|
| `fd_padre` | P-01 (`_v2`, retenido) | creación/validación del provisional; P-06 (dirfds del rename); inventario P-02 | paso 7 (último) |
| `fd_run` | P-01 | ancla del provisional: writers/masks/candidates/log/JSON por openat; P-04c; gate-1; P-06 | paso 7 (tras `fd_pub`) |
| `fd_masks` | P-01 (subancla) | memmaps componente a componente; 5bis (`unlinkat`) | tras 5bis (su última operación) |
| `fd_candidates` + `fd_cand_<grupo>` | P-09 (si flag) | WAV de grupo por P-03; descensos de compuertas | paso 7 (grupo → `fd_candidates`) |
| fds de writers WAV (×2 por runner) | P-03 (`openat O_EXCL` → `sf.SoundFile(fd, 'w', closefd=False)`) | DSP vía `OlaStream` | paso 2 (sf_close + cierre acreditado del fd) |
| `fd_mm` de memmaps (×6) | P-03 (magic-link sobre fd retenido o cabecera manual) | DSP (mapeo) | paso 2 (flush + cierre del mmap; entonces el fd) |
| fd de engine_log (Tee) | P-03 (`fdopen`, contrato R-17) | log de la corrida | paso 2 (`close_tee` acreditado, R-32) |
| fds JSON/TXT | P-03/P-04 (`fdopen`; pread) | reports/integridad | cierre inmediato tras cada uso |
| `fd_h` (hash G1) | dentro de cada compuerta | leer bytes del alcance G1 | dentro de la compuerta, uno por archivo |
| `fd_pub` | P-06 (post-rename) | 5bis/gate-2/ABORT-en-publicado | paso 7 |
| fd de guías (SR-EI-1) | S2 (posición L1695-1698) | DSP vía `read_span` (L1720-1721) | posición L1878 (éxito) / aborto vía `lectores` (A.4) |
| fd del mix (`hmix.fd`) | vigente (LS L142) | DSP + guarda final | vigente (acreditado, L1950) — sin cambios |
| handles de guías vigentes → `GuiaHandle` | S6 | `read_span` | S8 |

### C.3 Relación SR-EI-1 ↔ P-03/P-04 (sin confusión)

| Aspecto | P-03 | P-04 | SR-EI-1 |
|---|---|---|---|
| Objeto | SALIDAS del motor (creación exclusiva + entrega del fd a la biblioteca que escribe) | LECTURAS POST-ESCRITURA de salidas propias (pread/post_wav/TXT) | ENTRADAS del DSP (guías): continuidad validación→lector |
| Mecanismo compartido | fd-passthrough (`sf_open_fd`, `fdopen`, magic-link) | reapertura por `openat(dir_fd)` + `sf.SoundFile(fd, closefd=False)` | apertura controlada + fstat + comparación + entrega del MISMO fd (ruta int, A.3) |
| Verificación de identidad | `fstat(fd)` contra el objeto recién creado (sin ventana) | `fstat(fd_h)` contra registro propio (P-07) en compuertas G1 | `fstat(fd)` contra `FileInfo` del probe (S4) |
| Momento | creación de recursos | después del cierre de writers (paso 2) | antes del DSP (S2-S6) |
| Fallo ⇒ | aborto (sin EXIT_OK) | rechazo en compuerta (P-05) | aborto fail-closed (A.5) |

SR-EI-1 usa el mismo MECANISMO de entrega que P-03 pero para entradas y con comparación contra `FileInfo` — es un requisito de integridad de ENTRADAS, no una lectura post-escritura ni una compuerta.

## D. Matriz de decisiones

| # | Decisión/punto | Estado |
|---|---|---|
| D-1 | Reapertura de guías por ruta sin verificación (brecha) | DOCUMENTED_FACT (H L1697-1698; complemento §4.1) |
| D-2 | SR-EI-1 exigido (reapertura controlada + fstat + comparación + fail-closed + mismo descriptor) | ADJUDICACIÓN (complemento §4.2) |
| D-3 | Mecanismo primario: ruta **int fd** (`sf_open_fd`, `closefd=False`) — única que satisface literalmente «mismo descriptor» | PROPOSED (este documento, A.3) — sujeto a aceptación en la auditoría de Cris |
| D-4 | `GuiaHandle` con contrato MixHandle (fd propio + lector + cierre verificable) | PROPOSED (A.2/A.4) |
| D-5 | Posición de apertura (L1695-1698) y de cierre (L1878) conservadas | PROPOSED (A.2/A.4) |
| D-6 | Taxonomía de fallos (`GUIA_NO_ABIERTA/SUSTITUIDA_ANTES_DEL_DSP`, `trasladar=False`) | PROPOSED (A.5); texto final de motivos pendiente de implementación |
| D-7 | Invariancia DSP/acústica (mismo inodo, misma API, `read_span` sin cambios) | PROPOSED como invariante; UNKNOWN como hecho ejecutado |
| D-8 | FLAC por fd | UNKNOWN (no ejercitado ni en arnés ni en motor) |
| D-9 | Bifurcación única al final de `run_experiment`; `L_acept`/5bis/P-06/P-02 sólo en rama `full_processing`; `else` = código vigente | PROPOSED (B.1-B.3) |
| D-10 | `retener_anclas=False` por defecto en `create_run_dir` (P-01 no se extiende a `single_pair`) | PROPOSED (B.2) |
| D-11 | Adaptación mecánica compartida de writers/memmaps/Tee/JSON (P-03/P-04) con invariantes observables preservados | PROPOSED (B.2/B.4) |
| D-12 | Protocolo de verificación comparativa `single_pair` pre/post | PROPOSED y **PENDIENTE DE AUTORIZACIÓN** — NO ejecutado (B.6) |
| D-13 | **¿SR-EI-1 aplica también a `single_pair`?** (recomendación de diseño: sí, por ser integridad de entradas y no compuerta; cambiaría el escenario de sustitución de silencioso a aborto) | **DESCISIÓN ABIERTA — requiere adjudicación de Cris** |
| D-14 | **Forma exacta de `GuiaHandle`** (firma/campos/mensajes) | PENDIENTE — fase de implementación autorizada |
| D-15 | **Textos finales de motivos de `FalloCorrida6G1`** para guías | PENDIENTE — fase de implementación autorizada |
| D-16 | **Autorización para ejecutar la regresión B.6 y/o pruebas con motor** | PENDIENTE — adjudicación expresa |
| D-17 | Todo el contenido de P-01..P-09 (secuencia C) | PROPOSED (plan v2.3; nada implementado) |

**Decisiones que todavía requieren adjudicación de Cris (explícitas):** D-13 (alcance de SR-EI-1 a `single_pair`), D-16 (autorización de regresión/pruebas), y tras la auditoría de este documento: la aceptación del diseño D-3/D-4/D-9 como base para la futura fase de implementación. No se cierra ninguna incertidumbre por suposición: D-7/D-8 quedan UNKNOWN hasta evidencia.

## Declaración expresa y parada

Documento de diseño y documentación exclusivamente: no modifica `motores/`, `lectura_segura_6g1.py`, el plan v2.3 ni ningún archivo existente; no ejecuta ni importa producción; no ejecuta pruebas, arneses ni fixtures; cero audio real y cero Android/Termux; no toca DSP, fórmulas, parámetros, máscaras ni reconstrucción; no integra FLOW-1..4 ni P-01..P-09 ni SR-EI-1; no interviene EVO/MQR, FLOW-5..8, `main` ni PR #2; sin merge ni cherry-pick. El único archivo de este commit es este documento. Las líneas citadas corresponden a los SHA256 de la auditoría (§1 de `2438559…`) sobre el padre `1b9f5be…`.

— Fin del documento. Parada obligatoria: publicado y detenido — se espera la auditoría y adjudicación de Cris. No se implementa nada.
