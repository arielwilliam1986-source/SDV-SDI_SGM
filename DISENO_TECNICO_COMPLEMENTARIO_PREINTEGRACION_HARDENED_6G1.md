# DISEÑO TÉCNICO COMPLEMENTARIO PREINTEGRACIÓN — HARDENED 6G.1 — v5 (RECTIFICACIÓN DOCUMENTAL)

- **Destinatario:** Cris, auditor y adjudicador técnico. **Ejecutor:** Arena.
- **Historial:** **v1** publicada en `981c29c29367b2f4ec3928f9d3fadd930edb5eb0` (hijo de `1b9f5be…`). **v2 = rectificación documental** (hijo directo de `981c29c…`): incorpora la adjudicación **D-13** (SR-EI-1 en ambos modos), separa los invariantes de `single_pair` (ordinarios vs adversariales), añade B.7 (recursos transitorios) y A.4.1 (contrato de cierre de `GuiaHandle`). **v3 = rectificación documental** (hijo directo de `30b2b0aebdd46480aee30a3f5e6e86cac1447052`): actualiza el contexto, precisa los LÍMITES de las anclas transitorias (B.7.0), separa las tres alternativas de construcción de memmaps con propiedad y orden de cierre (B.7.1), rectifica las dependencias P-03/P-09 (C.1.1) y retira del contrato de `GuiaHandle` la afirmación de reintento seguro del lector (A.4.1). **v4 = rectificación documental** (hijo directo de `f7450b9d0220a947692154507d02e6ccc986cb9d`): Rectificación A — alcance exacto de `O_NOFOLLOW` y del recorrido de ruta (B.7.0, puntos 5-9); Rectificación B — cierre EFECTIVO del mapeo como condición VERIFICABLE (B.7.2). **v5 = rectificación documental** (hijo directo de `4feccd86806202eb723461287fa60da3a71f3654`; único archivo modificado: este documento): **(1)** acreditación de `/proc/self/maps` POR IDENTIDAD `(dev,ino)` de todas las entradas del objeto, no por ruta textual (B.7.2.2-b; ruta textual desaparecida ≠ mapeo desaparecido; imposible acreditar ⇒ UNKNOWN, nunca PASS); evidencias complementarias objeto/proceso; **(2)** propiedad y recursos restantes por alternativa en el fallo de cierre (B sin `fd_mm` propio: no se le atribuyen garantías de A/C); **(3)** bloqueo de publicación POR MODO (`full_processing`: compuertas; `single_pair`: circuito propio sin P-05). Límites intactos: D-13 adjudicada; P-01..P-09 y FLOW-1..4 sólo `full_processing`; D-16 PENDIENTE; D-18 UNKNOWN; D-19 PROPOSED; FEASIBILITY-1-R2 = evidencia aislada de mecanismos, NO validación de integración. El historial v1..v4 queda íntegro en Git; las secciones no afectadas no se reescriben.
- **Naturaleza:** documento de **diseño y documentación exclusivamente**. No modifica el motor, `lectura_segura_6g1.py`, el plan v2.3 ni ningún archivo; no ejecuta ni importa producción; no ejecuta pruebas, arneses ni fixtures; cero audio. **No implementa nada**: todo mecanismo futuro queda **PROPOSED** hasta su adjudicación. **D-16 continúa PENDIENTE DE AUTORIZACIÓN**: no se ejecutan regresiones ni pruebas.
- **Informe base:** `INFORME_AUDITORIA_ESTATICA_CORRESPONDENCIA_MOTOR_PLAN_6G1.md` (`2438559…`) y `COMPLEMENTO_ADJUDICACION_AUDITORIA_MOTOR_PLAN_6G1.md` (`1b9f5be…`). Este documento RESUELVE decisiones de diseño pendientes señaladas en el §8 de la auditoría, sin reescribirlos.
- **Etiquetas (esquema de 4, vigente desde el complemento):** **DOCUMENTED_FACT** (código vigente, con líneas) · **ADJUDICACIÓN** (decisión expresa de Cris) · **PROPOSED** (diseño futuro, no implementado) · **UNKNOWN** (sin evidencia).
- **Contexto aceptado (actualizado v3):** plan v2.3 consolidado; FEASIBILITY-1-R2 aceptada (entorno Linux documentado); auditoría estática aceptada; complemento de adjudicación aceptado. **D-13 está ADJUDICADA**: SR-EI-1 aplica a `full_processing` y a `single_pair`. `single_pair` está FUERA de P-01..P-09 y FLOW-1..4, pero **NO fuera de SR-EI-1**; la preservación de su comportamiento se refiere a los **escenarios ordinarios**, con la **excepción adversarial adjudicada** (sustitución de guía ⇒ rechazo fail-closed en ambos modos, B.4.2). **SR-EI-1 está adjudicado como REQUISITO y todavía NO está implementado** (PROPOSED).

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

**Aplicabilidad a ambos modos (ADJUDICACIÓN D-13, incorporada en esta rectificación):** la secuencia S1-S8 se ejecuta en la **región compartida ANTES de la bifurcación de modos** (posición vigente H L1695-1698, posterior a `abrir_mix` L1687 y anterior al DSP y a la bifurcación final de §B.1) ⇒ **SR-EI-1 aplica tanto a `full_processing` como a `single_pair`**. La verificación de identidad de las guías **ocurre antes del DSP y es independiente de las compuertas P-05**: no desciende de ningún dirfd de compuerta, no consulta la matriz §8ter y no depende de anclas retenidas. **Una sustitución detectada produce rechazo fail-closed en AMBOS modos** (A.5); la rama `else` de publicación de `single_pair` conserva su comportamiento vigente pero **no puede eludir SR-EI-1**.

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

### A.4.1 Contrato de cierre de `GuiaHandle` (precisado en la rectificación v2)

**PROPOSED** — el patrón equivalente SÍ es vigente para `MixHandle` (DOCUMENTED_FACT, LS L199-245), pero `GuiaHandle` NO existe y este contrato **NO está probado en el motor**:

1. **Intentar finalizar el lector SoundFile** (`rd.close()` — libsndfile finaliza el archivo lógico). **Si el cierre del lector falla:** el fallo se registra de forma persistente (punto 3), la referencia se conserva mientras el objeto no conste cerrado físicamente, y los REINTENTOS posteriores ocurren sólo dentro del circuito vigente de cierre verificado (`cerrar_verificado_6g1` vuelve a invocar `close()` únicamente si el objeto no consta cerrado físicamente — LS L1185-1189). **NO se afirma que un segundo `rd.close()` sea necesariamente seguro tras un fallo del primero, salvo evidencia técnica específica** que la fase de implementación deberá acreditar para el caso `GuiaHandle`/guías (hasta entonces: UNKNOWN). [Nota de trazabilidad: el docstring de `MixHandle` SÍ declara «idempotente y seguro de reintentar» para SU lector (LS L200-206 — DOCUMENTED_FACT como contrato vigente de MixHandle). Ese contrato de MixHandle NO se modifica aquí y NO se traslada automáticamente a `GuiaHandle`.]
2. **Intentar SIEMPRE cerrar el descriptor propio, incluso si el cierre del lector falla.** Antes del primer intento de `os.close(fd)`, el campo pasa a `None` (nunca se reintenta `os.close` sobre el mismo número: en Linux el descriptor queda liberado aunque close() falle y el número puede haberse reasignado — mismo argumento de MixHandle, LS L206-212).
3. **Registrar de forma persistente cualquier fallo:** el PRIMER fallo (del lector o del fd) queda en `_cierre_fallido_6g1` y no se sobrescribe (LS L234-235); un recurso con fallo de cierre nunca se acredita como cerrado, aunque sus referencias queden en None.
4. **No declarar el recurso completamente cerrado si el cierre no puede acreditarse:** estado físico = (lector `closed` True **Y** campo `fd` es None) — análogo a `_estado_fisico_6g1` para MixHandle (LS L1157-1159); el dictamen OK exige estado físico acreditado Y ningún fallo persistente (patrón `_cerrado_6g1`, LS L1164-1173).
5. **Integración con el mecanismo vigente:** el cierre en ruta de éxito se acredita con `cerrar_verificado_6g1` (LS L1176-1201) — `GuiaHandle` debe exponer el estado físico que esa función sabe leer (delegación `.closed` + lógica fd, detalle de implementación); en aborto, `GuiaHandle` entra en `lectores=` de `preparar_aborto_6g1` junto a `hmix` y `handles` (H L2016-2017/L2029-2032/L2046-2050); un fallo de cierre marca `completo=False` ⇒ aborto registrado SIN traslado.

**Estado (DOCUMENTED_FACT / PROPOSED):** lo vigente es el patrón MixHandle y el circuito `cerrar_verificado_6g1`/`preparar_aborto`; lo PROPOSED es `GuiaHandle` y la aplicación de ese contrato a las guías. **No se afirma que este comportamiento esté probado en el motor** — su verificación pertenece a una fase de implementación autorizada (y a la regresión B.6 si se adjudica D-16).

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
4. **Pendiente de prueba o decisión (UNKNOWN):** lectura de FLAC por fd; ejecución de la invariancia en el motor real; texto final de motivos de `FalloCorrida6G1`; forma exacta de `GuiaHandle`. [v2: el alcance de SR-EI-1 a ambos modos ya está ADJUDICADO (D-13) — ya no es una incertidumbre.]

## B. Aislamiento de `full_processing` y `single_pair`

### B.1 Punto de separación de modos (DOCUMENTED_FACT base / PROPOSED diseño)

- Base: `full_mode = (mode == MODE_FULL_PROCESSING or mode == MODE_SINGLE_PAIR)` (H L1622) — hoy AMBOS modos recorren la misma ruta de escritura/publicación.
- Diseño propuesto: **UN ÚNICO punto de bifurcación** al final de `run_experiment`, delimitando los pasos NUEVOS de P-08/P-05: `if mode == MODE_FULL_PROCESSING: <secuencia P-08 con gate-1/5bis/gate-2/EXIT_OK condicionado>` `else: <secuencia vigente intacta (publicación por rutas L1984, rmtree masks con WARN L1994-2000, EXIT_OK incondicionado L2002)>`. El resto del flujo (creación, escrituras, DSP, guarda del mix, input_integrity) permanece compartido con adaptación mecánica (B.2).
- Justificación: minimizar la superficie de bifurcación (un solo `if` de modo en la secuencia final) y hacer verificable por diff que la rama `else` conserva las líneas vigentes.
- **Límite de la rama `else` (ADJUDICACIÓN D-13, v2):** la rama `else` de publicación de `single_pair` **puede conservar su comportamiento vigente** (publicación por rutas, rmtree con WARN, EXIT_OK incondicionado) **pero NO puede eludir SR-EI-1**: la verificación de identidad de guías ocurre en la región compartida ANTERIOR a la bifurcación (§A.2 Aplicabilidad), por lo que es anterior a cualquier decisión de publicación y es **independiente de las compuertas P-05** (no consulta §8ter ni dirfds de compuerta).

### B.2 Clasificación de funciones compartidas (PROPOSED)

| Función (líneas vigentes) | Tratamiento propuesto | `single_pair` |
|---|---|---|
| `create_run_dir` (H L1430) | adaptación mecánica compartida (P-01: anclas retenidas vía parámetro opcional `retener_anclas=False` por defecto); `full_processing` pasa `True` | comportamiento observable idéntico (mismos nombres/_partial/_final; anclas no retenidas por defecto → P-01 NO se extiende) |
| `CandidateRunner.__init__` (L1396-1399), `_open_memmap` (L1456), `Tee`/`init_tee` (L173/L215), JSON/TXT (L2130/L2180/L1957) | adaptación mecánica compartida (P-03/P-04: fd-passthrough) — cambia el CÓMO interno, no el QUÉ observable | mismos artefactos, nombres, contenido y `rc`; verificado por B.6 |
| `post_wav_identity` (L1461/L1889) | compartida con P-04c; `single_pair` ejecuta full_mode ⇒ misma lectura por descriptor ( cambio transparente) | ídem |
| Compuertas P-05 (gate-1/gate-2), hash G1, matriz §8ter (`L_acept`), paso 5bis | **RAMIFICADO**: sólo en la rama `full_processing`; `L_acept` NO se deriva para `single_pair` (la derivación queda detrás del `if`) | NO hereda §8ter ni P-05 |
| Publicación P-06 (`_v2` por anclas + `fstat(fd_pub)==I_run`) | **RAMIFICADO**: rama `full_processing`; `single_pair` conserva `publicar_dir_6g1` vigente por rutas (L1984) | NO hereda P-06 |
| Aborto P-02 (`abortar_corrida_6g1_v2(fd_dir, fd_padre)`) | **RAMIFICADO**: handlers pasan anclas sólo si existen (rama `full_processing`); si `single_pair` no retiene anclas (B.2 primera fila), los handlers usan el protocolo VIGENTE por rutas | NO hereda P-02 |
| SR-EI-1 (guías) | **ADJUDICADO (D-13, v2): aplica a AMBOS modos** — región compartida antes del DSP, independiente de P-05; sustitución ⇒ rechazo fail-closed en ambos modos | aplicar (fallo fail-closed si hubo sustitución — cambio de seguridad deliberado, no regresión) |

### B.3 Evitar herencia inadvertida de §8ter/P-05 (PROPOSED)

- La derivación de `L_acept` desde la matriz §8ter se codifica DENTRO de la rama `mode == MODE_FULL_PROCESSING` (no como función importable de alcance global); ninguna constante de §8ter se consulta fuera de esa rama.
- El paso 5bis y la condición de EXIT_OK quedan dentro de la misma rama; la rama `else` mantiene literalmente el código vigente (L1984-L2002).
- `preparar_aborto_6g1`/`abortar_corrida_6g1` reciben anclas SÓLO si el modo las retuvo (los `locals().get(...)` vigentes ya toleran ausencia); la variante `_v2` de P-02 se invoca sólo con anclas presentes.

### B.4 Comportamiento de `single_pair` a preservar (RECTIFICADO v2 — separación expresamente exigida)

**1. Escenarios ORDINARIOS** (entradas válidas y sin sustitución) — invariantes de equivalencia, PROPOSED:

1. Mismos artefactos y nombres (`<track_base> SDV/SDI.wav` en raíz, `candidates/…` con `--write-all-candidates`, `analysis.json/.txt`, `engine_log.txt`, `input_integrity_6g.json`, `masks/` según `--png/--keep-masks`, `png/` condicionado, publicación con sufijos `_r%03d`, `masks/` eliminada del publicado con WARN si falla).
2. Mismo `rc` en cada escenario ordinario (éxito/validación/procesamiento/aborto) y misma semántica de `ABORT_6G1.json` (schema abort-6g1/3).
3. Mismo contenido científico (`analysis.json` campo a campo).
4. Cambios PERMITIDOS (no observables): mecanismo interno de fds (P-03/P-04), registro por identidad, orden interno de cierre con acreditación, anclas transitorias (B.7) — mientras los invariantes 1-3 se mantengan.

**2. Escenarios ADVERSARIALES de sustitución de guía** — NO son regresión de equivalencia:

- El rechazo fail-closed de SR-EI-1 (`GUIA_SUSTITUIDA_ANTES_DEL_DSP`, rc≠0, sin publicación) es un **CAMBIO DE SEGURIDAD DELIBERADO adjudicado** (D-13): hoy el motor vigente lee el sustituto SILENCIOSAMENTE (H L1697-1698 sin verificación); después de la integración, ese mismo escenario produce aborto en **AMBOS modos**.
- **NO se afirma que los códigos de retorno deban permanecer idénticos ante una sustitución de entrada**: en los escenarios de sustitución, la comparación correcta es contra el comportamiento NUEVO esperado (fail-closed), no contra el vigente (B.6).

### B.5 Riesgos de bifurcar funciones o duplicar rutas (PROPOSED; mitigación)

| Riesgo | Mitigación |
|---|---|
| Deriva entre la rama `else` (vigente) y la rama nueva → dos semánticas de publicación/limpieza que divergen silenciosamente | un solo punto de bifurcación (B.1); verificación por diff de que la rama `else` es idéntica a las líneas vigentes; la rama nueva se construye sobre la misma `GuiaHandle`/anclas (sin duplicar helpers) |
| Duplicación de helpers (dos implementaciones de publicación/limpieza) | P-06 `_v2` y 5bis son funciones NUEVAS llamadas sólo desde la rama nueva; las vigentes (`publicar_dir_6g1`, `shutil.rmtree`) permanecen para `single_pair` sin modificar |
| Parámetro `retener_anclas` mal propagado → `single_pair` retiene anclas sin usarlas (fuga) o `full_processing` no las retiene (P-01 roto) | valor por defecto `False` (comportamiento vigente); el paso de `True` ocurre en un único punto (`run_experiment`); verificación de residuos de fds en la regresión B.6 |
| `full_mode` compartido oculta diferencias futuras | documentar en la propia rama el motivo del `if` (referencia a la ADJUDICACIÓN A del complemento) |
| SR-EI-1 cambia `single_pair` en el escenario de sustitución (antes silencioso, ahora aborto) | **COMPORTAMIENTO DELIBERADO ADJUDICADO (D-13, v2)**: cambio de seguridad, no regresión; el protocolo B.6 verifica los escenarios de sustitución contra el comportamiento NUEVO esperado |

### B.6 Verificación comparativa pre/post para `single_pair` (PROPOSED — **PENDIENTE DE AUTORIZACIÓN; NO EJECUTADA**)

Protocolo propuesto (sólo diseño): (1) ejecutar el motor vigente en `--mode single_pair` con fixture sintético fijo (sin audio real) y capturar: `rc`, árbol de artefactos, `analysis.json`, `engine_log.txt`, `input_integrity_6g.json`, hashes de WAV, presencia/ausencia de `masks/` publicado, formato de `ABORT_6G1.json` en un escenario de aborto; (2) repetir idéntico tras la integración; (3) comparar campo a campo (los campos temporales/`(dev,ino)`/timestamps varían por diseño).

**Alcance rectificado (v2, consecuencia de D-13):** la comparación de equivalencia campo a campo del punto (3) aplica a los **escenarios ORDINARIOS** (B.4.1). Los **escenarios adversariales de sustitución de guía** se comparan contra el comportamiento NUEVO esperado (rechazo fail-closed con motivo específico y rc≠0 — B.4.2), NO contra el vigente. **Este protocolo NO se ejecutó aquí y NO se autoriza por este documento** — D-16 continúa PENDIENTE DE AUTORIZACIÓN — requiere adjudicación expresa de Cris (fixtures, entorno, momento). Hasta entonces, la preservación de `single_pair` en escenarios ordinarios es un requisito de diseño (PROPOSED) con verificación UNKNOWN.

### B.7 Recursos transitorios de `single_pair` — P-03/P-04 sin anclas retenidas de P-01 (añadido v2)

**Problema:** en `single_pair` NO se retienen anclas (D-10: `retener_anclas=False` por defecto). Las adaptaciones mecánicas de P-03/P-04 necesitan dirfds acreditados para crear archivos componente a componente. **Restricción de diseño (exigida): NO se introducen rutas nominales como solución implícita al anclaje.**

**Mecanismo propuesto — ANCLA TRANSITORIA (PROPOSED):** patrón «abrir → fstat contra identidad registrada → usar → cerrar inmediatamente». La identidad del provisional es CONOCIDA sin fd retenido: `crear_y_acreditar_dir_6g1` la registra en `_DIR_6G1` (LS L410, clave por ruta — registro vigente) y `create_run_dir` conoce la ruta. La reapertura se hace con `os.open(ruta, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)` + `fstat` comparado contra la identidad registrada — el mismo patrón H1 vigente de `_anclar_dir_aborto_6g1` (LS L331-364). Esto es **re-acreditación por identidad en cada uso**, no resolución nominal de un objeto no acreditado; los ficheros se crean y abren SIEMPRE por `openat` relativo al dirfd re-acreditado (P-03, prohibición de rutas multi-componente mantenida).

**B.7.0 Límites exactos del ancla transitoria (precisado v3):**
1. **La identidad `(st_dev, st_ino)` se verifica en CADA apertura transitoria** (fstat tras cada `os.open`, comparado contra la identidad registrada). La verificación vale para ESE descriptor durante ESE uso: mientras el descriptor permanece abierto, el kernel garantiza que designa el MISMO objeto de directorio (un fd no puede re-dirigirse).
2. **La verificación NO garantiza inmutabilidad del contenido** de los archivos internos ni protege contra TODAS las acciones de un proceso con el mismo UID (p. ej. modificar archivos dentro del directorio por sus propias rutas, o actuar sobre objetos vía procfs): acredita la IDENTIDAD del objeto directorio, no la integridad de su contenido.
3. **La identidad registrada en `_DIR_6G1` NO debe describirse como prueba de integridad de los archivos internos** del provisional: es la identidad del OBJETO directorio observado al crearlo/acreditarlo (H1, LS L385-411). Lo que ocurra DENTRO del directorio durante la ventana queda fuera de esa garantía.
4. **Si la ruta o el objeto no permiten revalidar la identidad esperada** (ruta ausente, symlink en la ruta, fstat distinto, objeto no directorio), **la operación debe fallar CERRADA**: sin uso del dirfd dudoso, sin creación de archivos sobre él, y el recurso pasa al protocolo vigente (registro/aborto). Patrón fail-closed de `_anclar_dir_aborto_6g1` (LS L331-364), SIN ampliar sus garantías más allá de lo documentado.

**Precisión v4 sobre `O_NOFOLLOW` y el recorrido de la ruta (Rectificación A):**

5. **`O_NOFOLLOW` protege únicamente el componente FINAL de la ruta**: si el componente final es un symlink, la apertura falla (ELOOP); los componentes INTERMEDIOS se siguen con normalidad (DOCUMENTED_FACT — coherente con la restricción técnica ya registrada del plan: «O_NOFOLLOW sólo protege el componente final», P-01 [R-C]).
6. **La comparación `(st_dev, st_ino)` por `fstat` acredita la identidad del DIRECTORIO FINAL abierto** frente a la identidad registrada (ADJUDICACIÓN: identidad final exigida — sin cambio respecto de B.7.0.1).
7. **Esa comparación NO demuestra que el recorrido completo de la ruta haya estado libre de enlaces simbólicos**: la acreditación es de IDENTIDAD FINAL del objeto abierto, no de PUREZA DEL RECORRIDO (un recorrido con componentes intermedios symlink que conduzca al objeto con la identidad registrada pasaría la comparación).
8. **Si se pretende exigir ausencia de symlinks en TODOS los componentes**, se identifica como REQUISITO ADICIONAL que necesita apertura COMPONENTE A COMPONENTE mediante dirfds (cada componente con `O_NOFOLLOW|O_DIRECTORY` relativo al descriptor acreditado del nivel anterior, con `fstat` por nivel) — **PROPOSED, NO implementado y NO presentado como implementado; NO es una garantía ya proporcionada por H1**.
9. **No se amplían las garantías de `_anclar_dir_aborto_6g1` más allá de lo que acredita el código vigente** (DOCUMENTED_FACT, LS L331-364): ese código acredita la apertura de la ruta con `O_NOFOLLOW` (sólo componente final) + `fstat` contra la identidad registrada del provisional — y NADA más (ni pureza del recorrido ni integridad del contenido).

**Clasificación (v4):** DOCUMENTED_FACT = puntos 5 y 9 (comportamiento real de `O_NOFOLLOW` y de H1); ADJUDICACIÓN = punto 6 (identidad final exigida, sin cambio); PROPOSED = punto 8 (recorrido componente a componente, eventual); UNKNOWN = cualquier garantía que no pueda demostrarse (p. ej. la pureza del recorrido histórico de una ruta ya abierta).

**Aplicación por recurso (todo PROPOSED):**

| Recurso | Secuencia con ancla transitoria en `single_pair` | Descriptor que sobrevive |
|---|---|---|
| `candidates/` y grupos (con flag) | `fd_run_t` (re-acreditado) → `mkdir("candidates", dir_fd=fd_run_t)` → `fd_cand_t = openat` + fstat → `mkdir(grupo, dir_fd=fd_cand_t)` → `fd_grupo_t = openat` + fstat → `openat(WAV, O_CREAT\|O_EXCL\|O_NOFOLLOW, dir_fd=fd_grupo_t)` → **fd del WAV entregado a `sf.SoundFile(fd, 'w', closefd=False)`** (P-03) → cierre INMEDIATO de `fd_run_t`, `fd_cand_t`, `fd_grupo_t` | fd del WAV (propiedad del motor hasta su cierre acreditado) |
| `masks/` y memmaps | `fd_run_t` (re-acreditado) → `mkdir("masks", dir_fd=fd_run_t)` → `fd_masks_t = openat` + fstat → `openat(npy, O_CREAT\|O_EXCL\|O_NOFOLLOW, dir_fd=fd_masks_t)` → **fd_mm del motor** + construcción del mapeo por UNA de las alternativas B.7.1 (A/B/C) → cierre de `fd_run_t` y `fd_masks_t` tras crear los npy | según alternativa B.7.1: `fd_mm` del motor (A y C) o ningún fd propio retenido (B) — cierre verificable al final del DSP |
| Tee / engine_log, `analysis.json/.txt`, `input_integrity_6g.json` | `fd_run_t` (re-acreditado) → `openat(O_CREAT\|O_EXCL\|O_NOFOLLOW)` → `os.fdopen(fd)` (P-03/P-04) → cierre de `fd_run_t` tras la creación | fd propio del recurso (cerrado por fdopen según contrato R-17) |
| `post_wav` (P-04c) | ancla transitoria re-acreditada del run dir → `openat(nombre, O_RDONLY\|O_NOFOLLOW, dir_fd=fd_run_t)` + fstat → `sf.SoundFile(fd, closefd=False)` → lectura → cierres | ninguno (transitorios por lectura) |
| SR-EI-1 (guías) | NO usa ancla de run: se abre el archivo de guía directamente (S2) y se compara contra `FileInfo` (S4) — independiente de P-01/P-05 | fd del lector durante el DSP |

**B.7.1 Memmaps: alternativas de construcción, propiedad de descriptores y orden de cierre (separado v3):**

| | **A — fd del motor + magic-link** (`/proc/self/fd/<fd_mm>`) | **B — `open_memmap` por ruta (vigente del motor, SIN anclaje)** | **C — sin procfs** (cabecera manual + `np.memmap(file object)`) |
|---|---|---|---|
| Quién abre el descriptor EFECTIVO | el motor abre `fd_mm` (`openat`); ADEMÁS numpy abre SUS PROPIOS fds resolviendo el magic-link (cabecera `open(path,'w+b')` y mapeo `open(path,'r+b')` — DOCUMENTED_FACT fuente numpy 1.26.4, plan §8bis) | numpy abre TODOS los fds por ruta nominal (el motor no abre ninguno para esto) | el motor abre `fd_mm` (`openat`); numpy NO abre fd nuevo: `np.memmap(file object)` invoca `mmap.mmap(fid.fileno())` sobre el fd DEL OBJETO ENTREGADO (DOCUMENTED_FACT fuente numpy 1.26.4) |
| Quién posee cada descriptor | `fd_mm`: el motor. fds internos de numpy: numpy (transitorios; los cierra numpy) | sólo numpy | `fd_mm` y el file object (`os.fdopen(fd_mm, 'r+b', closefd=False)`): el motor; el `mmap` referencia el fd vía `fileno()` |
| ¿El mapeo usa literalmente el fd del motor? | **NO** — por magic-link numpy abre OTROS fds sobre el mismo OBJETO designado por `fd_mm`; NO se afirma que numpy use el mismo fd del motor (afirmación retirada en v3) | NO | **SÍ, efectivamente**: el mapeo se crea sobre el fd del motor (mismo número, mismo objeto) — la identidad es atribuible al fd retenido |
| Qué mantiene vivo el mapeo | el objeto `mmap` (`mm._mmap`); semántica POSIX/Linux: el mapeo permanece mientras el objeto mmap viva — el orden adoptado es conservador: cerrar el mapeo ANTES que los fds | ídem | ídem |
| Orden exacto (P-09, conservador) | `mm.flush()` → cierre del mmap (`mm._mmap.close()` / soltar `mm`) → **entonces** `os.close(fd_mm)` (los fds internos de numpy se cerraron al construir el mapeo) | `mm.flush()` → cierre del mmap (no hay `fd_mm` propio que cerrar) | `mm.flush()` → cierre del mmap → cierre del file object (`closefd=False`: NO cierra `fd_mm`) → **entonces** `os.close(fd_mm)` |
| Si falla un paso | `flush` falla ⇒ excepción → protocolo de aborto (el npy puede quedar inconsistente ⇒ provisional no publicable); fallo de `os.close` ⇒ `_cierre_fallido_6g1` persistente ⇒ `CierreNoAcreditado6G1` ⇒ sin publicación | ídem (sin fd propio que acreditar) | ídem; el fallo al cerrar el file object sigue el contrato que se fije en implementación |
| Estado | mecanismo OBSERVADO en arnés F3 (espacio AISLADO: open_memmap vía magic-link con fd retenido — identidad y valor verificados); integración en `single_pair`: PROPOSED; verificación exhaustiva: UNKNOWN (D-16) | es el comportamiento VIGENTE del motor (por ruta, sin anclaje); el diseño lo SUSTITUYE; si se conservara para `single_pair` exigiría decisión expresa (no se propone) | mecanismo OBSERVADO en arnés F2 (espacio AISLADO: cabecera manual + `np.memmap(file object)`, guardián sin procfs, 0 consultas); integración: PROPOSED; verificación: UNKNOWN (D-16) |

**Declaración exigida (v3):** FEASIBILITY-1 NO valida la integración de anclas transitorias en `single_pair` — probó los MECANISMOS de biblioteca en espacio AISLADO y con arnés propio. La integración B.7 en su conjunto es PROPOSED; su verificación requiere la fase autorizada (D-16). Si algún elemento no pudiera determinarse con evidencia, queda UNKNOWN con la alternativa pendiente — sin presentar propuestas como implementaciones.

**B.7.2 Cierre efectivo del mapeo — condición VERIFICABLE, no liberación de referencias (Rectificación B, v4):**

**Afirmación retirada / prohibida:** NO se acredita el cierre del `mmap` por el mero hecho de ejecutar `del mm`, eliminar una referencia de Python o llamar a `close()` sin comprobar el resultado. El cierre es una CONDICIÓN VERIFICABLE del ciclo de vida, exigible antes de declarar el recurso cerrado y antes de cualquier publicación.

1. **Referencias que deben dejar de usar el mapeo ANTES de cerrarlo:** el propio objeto `memmap` (`mm`), TODAS las vistas (slices) obtenidas del mapeo, arrays derivados que compartan su buffer, y las referencias retenidas por el motor (en el motor vigente, la variable de bucle `arr` — H L1880-1881, DOCUMENTED_FACT). Con vistas/buffers activos, el cierre puede no liberar el mapeo (punto 4). Inventariar y soltar es parte del paso de cierre (PROPOSED).
2. **Acreditación del cierre efectivo del `mmap` subyacente (PROPOSED sobre mecanismos vigentes; rectificado v5)** — DOS evidencias COMPLEMENTARIAS (no intercambiables):
   - **(a) Estado del OBJETO `mmap` (evidencia del objeto):** tras `close()`, el objeto queda cerrado y cualquier acceso posterior eleva `ValueError` (comportamiento DOCUMENTED_FACT de CPython). Una llamada a `close()` SIN excepción NO acredita por sí sola la liberación del mapeo en el proceso.
   - **(b) Estado de los MAPEOS DEL PROCESO (evidencia del proceso)** vía `/proc/self/maps`, con las exigencias v5:
     * **Identificación por IDENTIDAD, no por nombre:** la comprobación debe identificar el objeto mapeado por los campos de DISPOSITIVO e INODO que expone `/proc/self/maps` (columnas `dev`/`inode` de cada línea), comparándolos con la identidad `(st_dev, st_ino)` conocida del archivo; NO exclusivamente por el nombre o ruta textual.
     * **TODAS las entradas correspondientes a ese objeto**, no sólo una coincidencia de ruta (cada mapeo del objeto es una entrada).
     * **La desaparición de una ruta textual NO acredita que el mapeo haya desaparecido**: un archivo ELIMINADO o RENOMBRADO puede continuar mapeado; la comprobación debe atender a su IDENTIDAD, no sólo al nombre (la línea de maps muestra el pathname con sufijo `(deleted)` o vacío — DOCUMENTED_FACT del formato; el barrido vigente `mapeos_bajo_dir_6g1`, LS L1094-1112, casa por NOMBRE y elimina el sufijo `(deleted)`: INSUFICIENTE para la acreditación exigida aquí).
     * **Si `/proc/self/maps` no está disponible o no permite acreditar la identidad** (procfs ausente, formato inesperado, campos no legibles), el resultado es **UNKNOWN — nunca PASS por ausencia de coincidencia textual**.
   - **(c) Complementariamente**, el fd propio del motor se acredita por `/proc/self/fd/N` (patrón vigente H1 / arnés F6) — sólo en las alternativas donde el motor posee fd (A y C).
   **UNKNOWN (D-18):** esta comprobación por identidad NO fue ejercitada para el caso exacto del motor (ni en el arnés: F6 verificó fds por stat, no maps por identidad).
3. **Si `mm.flush()` falla:** excepción ⇒ el contenido del `.npy` puede quedar inconsistente ⇒ provisional NO publicable ⇒ protocolo de aborto (provisional conservado); el mapeo NO se declara cerrado; el fallo se registra persistentemente (punto 6).
4. **Si el cierre del mmap falla o no libera** (referencias/buffers aún activos): el mapeo puede PERMANECER vivo. El fallo de `flush`, la imposibilidad de cerrar el mmap o la falta de acreditación de cierre DEBEN impedir la publicación en AMBOS modos — por los circuitos DISTINTOS del punto 6 (v5). El comportamiento EXACTO de `mmap.close()` de CPython con memoria exportada activa (cuándo se produce el unmap real) es UNKNOWN hasta prueba autorizada — no se ejecuta nada aquí.
5. **Qué permanece abierto si el cierre falla — sólo recursos de propiedad y permanencia DEMOSTRADAS, por alternativa (rectificado v5):**
   - **A:** el motor CONSERVA `fd_mm` y NO lo cierra hasta resolver el estado del mapeo; los fds internos de numpy (abiertos por numpy al resolver el magic-link) son propiedad de numpy y quedaron cerrados al construir el mapeo.
   - **B:** NO existe `fd_mm` propio del motor — numpy abre los descriptores necesarios por la ruta nominal y administra su cierre. Si el mmap no puede cerrarse, puede permanecer vivo EL MAPEO; **NO se afirma que el motor conserve un descriptor propio inexistente**; sólo se documentan los recursos cuya propiedad y permanencia estén demostradas (el propio mapeo).
   - **C:** el motor conserva `fd_mm` Y el file object (`closefd=False`); ambos permanecen bajo propiedad del motor y NO se cierran hasta resolver el estado del mapeo.
   **No se trasladan a B las garantías de propiedad de A o C.**
6. **Registro persistente, bloqueo de publicación y circuitos POR MODO (v5):** el PRIMER fallo queda registrado en el propio recurso (patrón `_cierre_fallido_6g1`, LS L1145-1152) y el dictamen de `cerrar_verificado_6g1` (LS L1176-1201) resulta no-acreditado ⇒ `CierreNoAcreditado6G1`. **P-05 es una COMPUERTA EXCLUSIVA de `full_processing`** (ADJUDICACIÓN A del complemento; §B.3):
   - **`full_processing`:** circuito de cierre, compuertas y aborto correspondiente — el dictamen no acreditado y/o la condición procfs de la compuerta (cero descriptores de escritura Y cero mapeos bajo el provisional, por identidad) impiden EXIT_OK ⇒ aborto (P-02).
   - **`single_pair`:** SIN compuertas P-05 — el error persistente del recurso y el aborto por el CIRCUITO PROPIO del modo impiden la publicación: dictamen no acreditado ⇒ `CierreNoAcreditado6G1` ⇒ protocolo vigente de aborto (`preparar_aborto_6g1` / `abortar_corrida_6g1`; su barrido procfs LS L1362/L1404 opera en el camino de aborto) ⇒ provisional conservado, sin publicación. **NO se invocan ni atribuyen a `single_pair` compuertas P-05 que no tiene; NO se declara que el barrido de P-05 proteja `single_pair`.**
   - **UNKNOWN / requisito de implementación:** si el circuito vigente no permite acreditar alguna de estas condiciones (p. ej. la acreditación del mapeo por identidad B.7.2.2-(b) no existe hoy como paso del ciclo de cierre de ningún modo), queda UNKNOWN y como REQUISITO de implementación — sin inventar un mecanismo actual.
7. **Momento exacto de los cierres de descriptores propios y file objects — DESPUÉS de acreditar el cierre del mapeo:**

| Alternativa (B.7.1) | Orden exacto tras el DSP |
|---|---|
| **A** (fd del motor + magic-link) | flush → soltar vistas/referencias → cerrar mmap → **ACREDITAR** (maps por identidad + estado del objeto) → `os.close(fd_mm)` — los fds internos de numpy (abiertos por numpy vía magic-link) ya fueron cerrados por numpy al construir el mapeo |
| **B** (`open_memmap` por ruta — vigente sin anclaje) | flush → soltar vistas/referencias → cerrar mmap → **ACREDITAR** (maps por identidad) — no hay fd del motor que cerrar; sólo los fds internos de numpy, abiertos y cerrados por numpy por la ruta nominal |
| **C** (sin procfs: file object) | flush → soltar vistas/referencias → cerrar mmap → **ACREDITAR** (maps por identidad + estado del objeto) → cerrar el file object (`closefd=False`: NO cierra `fd_mm` y NO transfiere su propiedad al file object) → `os.close(fd_mm)` |

**Propiedad (invariante mantenido de v3):** A — descriptor del motor (`fd_mm`) + descriptores internos de numpy abiertos a través del magic-link; **NO se afirma que numpy utilice literalmente el descriptor del motor** (acreditable por identidad del OBJETO, no por el número de fd). B — descriptores abiertos por numpy mediante la ruta nominal; alternativa VIGENTE sin anclaje, no aceptada como solución futura sin decisión expresa. C — descriptor del motor entregado mediante file object y mapeo construido sobre `fid.fileno()`; `closefd=False` NO transfiere la propiedad del descriptor. **Si alguna garantía depende de prueba futura (D-16), queda UNKNOWN y pendiente — no se inventa evidencia ni se ejecutan pruebas en esta rectificación.**

**Cierre verificable y ausencia de fugas (PROPOSED):** cada apertura transitoria tiene su cierre EMPAREJADO en el mismo bloque (patrón ledger validado en el arnés FEASIBILITY-1, F1-F6: toda apertura registrada, todo cierre verificado); los dirfds transitorios se cierran antes de continuar; los barridos procfs vigentes de `preparar_aborto_6g1` (LS L1115/L1362/L1404) detectarían cualquier escritura abierta bajo el provisional. **UNKNOWN:** la prueba exhaustiva de ausencia de fugas en `single_pair` requiere la regresión B.6 (D-16, pendiente); el barrido procfs presupone procfs montado (R-29).

**Diferenciación expresamente exigida (v2):**

| | `single_pair` | `full_processing` |
|---|---|---|
| Anclas (`fd_run`/`fd_padre`/`fd_masks`/`fd_candidates`/grupos) | **TRANSITORIAS**: abrir→fstat→usar→cerrar; ninguna sobrevive a su bloque | **RETENIDAS** toda la corrida (P-01); cierre ordenado paso 5bis/paso 7 |
| Compuertas P-05 / matriz §8ter / hashes G1 | **NO** (no se derivan; detrás de la bifurcación) | **SÍ** (gate-1/5bis/gate-2 exclusivos) |
| Publicación | vigente por rutas (rama `else`) | P-06 `_v2` por anclas + `fstat(fd_pub)==I_run` |
| P-03/P-04 | sí, con anclas transitorias (B.7) | sí, con anclas retenidas |
| SR-EI-1 | **SÍ** (D-13) | **SÍ** (D-13) |
| Aborto | protocolo vigente por rutas (P-02 NO retenido) | P-02 `_v2` con anclas retenidas |

**Estado:** todo el mecanismo de ancla transitoria es PROPOSED y NO ha sido ejercitado ni en arnés ni en el motor (la re-acreditación por ruta+identidad SÍ es vigente en el aborto H1, DOCUMENTED_FACT). Si en la fase de implementación alguna operación resultara no garantizable con anclas transitorias (p. ej. un descenso reiterado con coste R-15), se clasificaría UNKNOWN y se propondría el mecanismo pendiente — sin recurrir a rutas nominales.

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

**C.1.1 Dependencias reales P-03 ↔ P-09 (rectificado v3 — diferenciación exigida):**

| Componente | Contenido | Depende de | Notas |
|---|---|---|---|
| **P-03 — infraestructura GENERAL de fd-passthrough** | patrón único crear/acreditar/entregar/cerrar: `openat(O_CREAT\|O_EXCL\|O_NOFOLLOW, dir_fd)` + `fstat` + entrega del fd a la biblioteca (`sf_open_fd`, `fdopen`, magic-link o cabecera manual) + cierre acreditado | de una FUENTE DE DIRFD acreditado — que puede ser un ancla RETENIDA (P-01) o un ANCLA TRANSITORIA (B.7); NO depende de P-09 | aplica a writers/memmaps/Tee/JSON/TXT en AMBOS modos |
| **P-09 — subanclas de `candidates/` y sus grupos** | creación y gestión de DOS niveles (`mkdir("candidates", dir_fd=…)` → `fd_candidates` → `mkdir(grupo, dir_fd=fd_candidates)` → `fd_cand_<grupo>`), retención hasta el paso 7, orden de cierre y descensos de compuertas | CONSUME el mecanismo de P-03 para cada componente y para los WAV de grupo; requiere P-01 (anclas retenidas) en `full_processing` | sólo relevante con `--write-all-candidates`; en `single_pair` sus aperturas serían transitorias (B.7) — sin retención ni compuertas |
| **Dependencia real** | P-09 CONSUME la infraestructura de P-03; P-03 NO consume P-09. SR-EI-1 (entradas) es INDEPENDIENTE de ambos (fd directo + `FileInfo`, §A). P-05 requiere las subanclas de P-09 SÓLO cuando la compuerta debe descender por `candidates/` (flag activo) | | la secuencia 1-8 NO está implementada (PROPOSED); el alcance del plan v2.3 NO se altera |

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

**Nota v2 (alcance de la tabla):** el ciclo de vida descrito corresponde a `full_processing` (anclas retenidas). En `single_pair`, las filas de anclas (`fd_padre`/`fd_run`/`fd_masks`/`fd_candidates`/grupos) se sustituyen por el patrón de **ancla transitoria** de B.7 (abrir→fstat→usar→cerrar; sin compuertas ni 5bis ni `fd_pub`); las filas de writers/memmaps/Tee/JSON/guías/mix son iguales en ambos modos (P-03/P-04/SR-EI-1, ADJUDICACIÓN D-13).

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
| D-9 | Bifurcación única al final de `run_experiment`; `L_acept`/5bis/P-06/P-02 sólo en rama `full_processing`; `else` = código vigente **sin poder eludir SR-EI-1** (D-13) | PROPOSED (B.1-B.3) |
| D-10 | `retener_anclas=False` por defecto en `create_run_dir` (P-01 no se extiende a `single_pair`) | PROPOSED (B.2) |
| D-11 | Adaptación mecánica compartida de writers/memmaps/Tee/JSON (P-03/P-04) con invariantes observables preservados | PROPOSED (B.2/B.4) |
| D-12 | Protocolo de verificación comparativa `single_pair` pre/post | PROPOSED y **PENDIENTE DE AUTORIZACIÓN** — NO ejecutado (B.6) |
| D-13 | **SR-EI-1 aplica tanto a `full_processing` como a `single_pair`**: verificación de identidad antes del DSP, independiente de las compuertas P-05; sustitución detectada ⇒ rechazo fail-closed en AMBOS modos; la rama `else` de publicación de `single_pair` conserva su comportamiento vigente pero NO puede eludir SR-EI-1; el aborto por sustitución es cambio de seguridad deliberado, NO regresión de equivalencia | **ADJUDICACIÓN** (adjudicada por Cris; incorporada en esta rectificación v2 — §A.2 Aplicabilidad, B.1, B.2, B.4, B.5, B.6) |
| D-14 | **Forma exacta de `GuiaHandle`** (firma/campos/mensajes) | PENDIENTE — fase de implementación autorizada |
| D-15 | **Textos finales de motivos de `FalloCorrida6G1`** para guías | PENDIENTE — fase de implementación autorizada |
| D-16 | **Autorización para ejecutar la regresión B.6 y/o pruebas con motor** | PENDIENTE — adjudicación expresa |
| D-17 | Todo el contenido de P-01..P-09 (secuencia C) | PROPOSED (plan v2.3; nada implementado) |
| D-18 | Acreditación del cierre efectivo del mapeo (`/proc/self/maps` POR IDENTIDAD `(dev,ino)` de todas las entradas del objeto + estado del objeto mmap — evidencias complementarias, no intercambiables) para el caso exacto del motor/`single_pair` | UNKNOWN hasta fase autorizada (B.7.2.2; D-16) |
| D-19 | Recorrido componente a componente para exigir ausencia de symlinks en TODOS los componentes de la ruta del ancla transitoria | PROPOSED — requisito adicional, NO garantía ya proporcionada por H1 (B.7.0.8) |

**Decisiones que todavía requieren adjudicación de Cris (explícitas, v5):** D-16 (autorización de la regresión comparativa/pruebas — continúa PENDIENTE), y tras la auditoría de este documento: la aceptación del diseño D-3/D-4/D-9/B.7/B.7.1/B.7.2 y del requisito adicional D-19 como base para la futura fase de implementación. **Resueltas:** D-13 (ADJUDICACIÓN — SR-EI-1 en ambos modos, v2). No se cierra ninguna incertidumbre por suposición: D-7/D-8/D-18 (incluida la acreditación por identidad de B.7.2.2-(b), que el circuito vigente no ejerce hoy — requisito de implementación), la verificación del mecanismo de ancla transitoria B.7 (incluida la seguridad de reintento del lector de `GuiaHandle`, A.4.1.1), la integración de las alternativas de memmaps B.7.1 y la acreditación del cierre de mapeo B.7.2 quedan UNKNOWN hasta evidencia. D-19 continúa PROPOSED: la apertura componente a componente NO se convierte en requisito obligatorio ni garantía implementada sin adjudicación expresa.

## Declaración expresa y parada

Documento de diseño y documentación exclusivamente: esta rectificación v5 modifica ÚNICAMENTE este documento (M) — no modifica `motores/`, `lectura_segura_6g1.py`, el plan v2.3 ni ningún otro archivo; no ejecuta ni importa producción; no ejecuta pruebas, arneses ni fixtures; cero audio real y cero Android/Termux; no toca DSP, fórmulas, parámetros, máscaras ni reconstrucción; no integra FLOW-1..4 ni P-01..P-09 ni SR-EI-1; no interviene EVO/MQR, FLOW-5..8, `main` ni PR #2; sin merge ni cherry-pick. D-16 continúa PENDIENTE DE AUTORIZACIÓN: no se ejecutaron regresiones ni pruebas; no se inventó evidencia ni mecanismo actual inexistente. Límites intactos: D-13 adjudicada (SR-EI-1 en ambos modos); P-01..P-09 y FLOW-1..4 limitados a `full_processing`; D-18 UNKNOWN (acreditación por identidad no ejercida hoy — requisito de implementación); D-19 PROPOSED sin convertir en obligatorio. FEASIBILITY-1-R2 sigue siendo evidencia aislada de mecanismos de biblioteca, no validación de integración en el motor ni de las anclas transitorias de `single_pair`. Las propuestas siguen siendo propuestas. El historial de v1 a v4 queda íntegro en Git. Las líneas citadas corresponden a los SHA256 de la auditoría (§1 de `2438559…`) sobre el padre `4feccd8…`.

— Fin del documento. Parada obligatoria: publicado y detenido — se espera la auditoría y adjudicación de Cris. No se implementa nada.
