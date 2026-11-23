# PLAN DE INTEGRACIÓN — HARDENED FLOW-1..4 / 6G.1 (SÓLO DISEÑO — v2 RECTIFICADO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **exclusivamente DISEÑO**. No se implementó nada. Cero modificaciones de producción; cero ejecución del motor; cero pruebas adicionales; cero audio real.
- **Historial:** v1 publicada en `cea6652893b3f790b3c47aaab430ef99554c9d00` (hijo de `292274b`). **v2 = rectificación A–D** (adjudicación de Cris que acepta el plan como base de diseño sin autorizar implementación); publicada en un **commit hijo directo de `cea6652`**, acompañada del informe `RECTIFICACION_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md`.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`. Verificación previa: local = origin = `gh api` = `cea6652…` CONFORME.
- **Regla de lectura:** cada afirmación clasificada como **DEMOSTRADO** (evidencia experimental publicada), **DOCUMENTED_FACT** (fuente de código vigente inspeccionada, archivo:línea citado), **PROPUESTO** (este diseño, pendiente de adjudicación/implementación) o **DESCONOCIDO** (§11).

---

## §1 Línea base adjudicada (no se repite ni se re-ejecuta)

| Flujo | Veredicto adjudicado | Evidencia |
|---|---|---|
| FLOW-1 | PASS | `evidencia_rgflow_hardened_14/flow1_hardened.json` |
| FLOW-2 | PASS | `flow2_hardened.json` |
| FLOW-3 | PASS | `flow3_hardened.json` |
| FLOW-4 | UNKNOWN (caracterización) — **D1** y **C** observados | `flow4_hardened.json` |

Hallazgos que este plan debe resolver:

- **D1** — Aborto sobre directorio sustituido: FLOW-4 a1 produjo rc=2 **sin `ABORT_6G1.json` en ningún árbol**.
- **C** — Entrada final sustituida: FLOW-4 b produjo **EXIT_OK con `analysis.json` publicado como symlink atacante** (conjunto publicado mixto: 5 regulares reales + 1 symlink).

## §2 Mapa vigente del código real (DEMOSTRADO — inspección estática sobre `292274b`/`cea6652`, sin modificación)

Motor: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` (2312 líneas). Protocolo: `motores/lectura_segura_6g1.py` (1422 líneas).

| Elemento | Ubicación | Qué hace hoy (vigente) | Apertura de salida |
|---|---|---|---|
| Códigos de salida | H L159–162 | EXIT_OK=0, EXIT_VALIDATION=1, EXIT_PROCESSING=2, EXIT_ABORTED=130 | — |
| `Tee.__init__` | H L173–178 | `open(path, "w")` **por ruta**; cierre verificable AI-C (`error_cierre_6g1`) | por ruta |
| `init_tee` / `close_tee` | H L215–221 / L222–245 | log global de corrida (`engine_log.txt`); contrato de reintentos (R-17) | por ruta |
| `probe_file` | H L355 (os.open L372) | apertura única `O_RDONLY\|O_NONBLOCK` del mix de entrada (H2-R-A) | entrada |
| `create_run_dir` | H L1430–1454 | `_reiniciar_registro_6g1()` + `_crear_y_acreditar_dir_6g1(out_base, nombre)`; devuelve **rutas**, no descriptores | mkdir(dir_fd) |
| `crear_y_acreditar_dir_6g1` | LS L367–415 | padre validado (O_DIRECTORY\|O_NOFOLLOW, euid propietario, sin W grupo/otros) → `mkdir(0o700, dir_fd)` → fstat → registra `(dev,ino)` en `_DIR_6G1[ruta]`; **cierra ambos fds** | dir_fd |
| `_open_memmap` | H L1456–1460 | `np.lib.format.open_memmap(path, "w+")` **por ruta** + registrar propio (estable=False) | por ruta |
| `CandidateRunner.__init__` | H L1374–1407 | escritores WAV: `sf.SoundFile(join(run_dir,nombre), "w")` **por ruta** (L1399, L1401) + registrar propio; fallo → `_runner_parcial_6g1` + re-eleva | por ruta |
| `CandidateRunner.close` | H L1408–1428 | cierre verificable `_cerrar_verificado_6g1` de `writer_sdv`/`writer_sdi`; fallo → `CierreNoAcreditado6G1` | — |
| `post_wav_identity` | H L1461–1492 | **re-abre los 3 WAV por ruta** para SNR de identidad | por ruta (lectura) |
| masks | H L1615–1616, L1628–1639 | `os.makedirs(masks_dir)` **por ruta**; 6 memmaps (`mask_gp01_vocal/instrumental`, `consensus_vocal/instrumental_<method>`, `confidence_map`, `model_disagreement_map`) | por ruta (multi-componente) |
| lectores de guías | H L1695–1698, L1878 | `sf.SoundFile(p.vocal.path)` por ruta (entradas; cerrados en L1878) | entrada |
| `hmix` | H L1687 | `_abrir_mix_6g1` → `MixHandle` (fd de lectura retenido + verificación identidad/SHA) | fd retenido |
| `input_integrity_6g.json` | H L1957–1966 | escritura 'w' **por ruta** + registrar (estable=True) + **re-lectura 'r' por ruta** + `json.load` | por ruta |
| `write_reports` | H L2068–2133 | `analysis.json` con `open(..., "w")` **por ruta** (L2130); SHA de entradas (`engine_sha256`, `manifest_sha256`) por ruta | por ruta |
| `write_analysis_txt` | H L2134, L2137–2182 | `analysis.txt` por ruta | por ruta |
| `write_pngs` | H L2183–2211 | matplotlib por rutas ancladas no probado (**R-12**; artefacto OPCIONAL `--png`) | por ruta |
| guarda final (CV) | H L1937–1982 | cubre el MIX de **entrada** (`hmix.verificar()` + `ruta_apunta_al_mismo_objeto`, ~L1937; raise ~L1968) — **no cubre artefactos de salida** (**R-16**) | — |
| publicación | H L1984 → LS L803–827 (`publicar_dir_6g1`) → L769–802 (`_renameat2_noreplace`) | `renameat2(AT_FDCWD, origen_abs, destino_abs, RENAME_NOREPLACE)` **por rutas absolutas**; sin inspección de contenido del conjunto; sufijos `_r%03d` ante colisión; fail-closed si renameat2 indisponible | rutas absolutas |
| limpieza masks | H L1988–1997 | `shutil.rmtree(published/masks)` **por ruta** tras publicar (WARN si falla) | por ruta |
| EXIT_OK | H L1999–2000 | `return EXIT_OK, run_dir_final` tras publicación exitosa | — |
| KeyboardInterrupt | H L2004–2018 | `_preparar_aborto_6g1(...)` → `_abortar_corrida_6g1(..., "INTERRUPCION_DEL_USUARIO")` → `return EXIT_ABORTED, None` | — |
| `FalloCorrida6G1` | H L2019–2035 | aborto clasificado (mix cambiado, publicación fallida, …) → `EXIT_PROCESSING` | — |
| Exception genérica | H L2036–2055 | `EXCEPCION_DURANTE_EL_PROCESAMIENTO` → `EXIT_PROCESSING` | — |
| `main` / top-level | H L2240 / L2309–2312 | `sys.exit(main())`; KeyboardInterrupt de nivel superior → EXIT_ABORTED | — |
| señales | todo el motor | **sin `signal.signal`** (**R-11**; SIGTERM/SIGKILL fuera de alcance en esta fase) | — |
| `_anclar_dir_aborto_6g1` | LS L331–365 | **re-abre el provisional POR RUTA** (`O_DIRECTORY\|O_NOFOLLOW`) y compara `fstat` contra `_DIR_6G1[ruta]`; fail-closed si identidad distinta | por ruta |
| `abortar_6g1` | LS L576–768 | ancla → inventario por descriptor (listdir(fd)+lstat(dir_fd), descenso O_NOFOLLOW) → `ABORT_6G1.json` `O_CREAT\|O_EXCL\|O_NOFOLLOW`+`dir_fd` en el MISMO fd validado; sin eliminación (C-R1); analysis.json intacto (E-R2) | dir_fd (tras ancla por ruta) |
| `_sha_via_descriptor_6g1` | LS L416–470 | SHA-256 de una entrada relativa a un dirfd ya validado | dir_fd |
| registro propio | LS L508–575 | `registrar_propio_6g1(path, estable)` por RUTA (clave: ruta) | — |
| `_registro_aborto_verificado_6g1` | LS L866–899 | verifica la existencia del registro de aborto vía fd | dir_fd |
| `abortar_corrida_6g1` | LS L900–1026 | protocolo: cierre → ABORT → traslado opcional a `_aborted*` (vía `publicar_dir_6g1`) | mixto |
| barridos procfs | LS L1058–1129 | `descriptores_bajo_dir_6g1` / `mapeos_bajo_dir_6g1` / `escritura_abierta_bajo_dir_6g1` (R-15) | — |

## §3 Mecanismo exacto de los hallazgos (por qué ocurren hoy)

**D1 (DEMOSTRADO, flow4_hardened.json sub-caso a1):** `create_run_dir` acredita `(dev,ino)` pero **no retiene ningún descriptor** (LS L405–409 cierran `fd_dir` y `fd_padre`). En el aborto, `_anclar_dir_aborto_6g1(run_dir)` resuelve la **ruta** y compara identidad: si el atacante renombró el provisional real a otro árbol y recreó el nombre, la ruta ya NO designa el objeto acreditado → `identidad_distinta` → **fail-closed sin escritura en ninguna parte**, aunque el objeto real siga vivo y alcanzable por descriptor. Resultado observado: rc=2, `LibsndfileError` en la ruta nominal del árbol real (post_wav_identity reabrió por ruta), provisional real conservado, **ABORT_6G1.json ausente en los dos árboles**.

**C (DEMOSTRADO, sub-caso b):** la publicación renombra el directorio completo **sin ninguna compuerta de contenido**: sin rechazo de enlaces simbólicos, sin verificación de obligatoriedad/identidad del conjunto, sin atestación de hashes. El hook en frontera de publicación sustituyó `analysis.json` por un symlink y el conjunto MIXTO se publicó con EXIT_OK (rc=0). R-16 ya declaraba que la guarda vigente cubre sólo la entrada.

## §4 Arquitectura de referencia adjudicada (se reutiliza; NO es integración conseguida)

| Diseño adjudicado | Qué aporta a este plan | Estado |
|---|---|---|
| **PDA-1** (`DISENO_PUBLICACION_ANCLADA_6G1.md`) | ancla **(fd_padre, nombre_relativo, identidad)**; `crear_y_acreditar_dir_6g1_v2` que NO cierra el descriptor del padre; `renameat2` **relativo a descriptores**; cierre acreditado del ancla en el protocolo de recursos | prototipo adjudicado; **NO integrado en producción** |
| **EA** (ciclo de vida anclado) | el provisional vive como **objeto designado por descriptor** desde la creación hasta el cierre/publicación | prototipo adjudicado; no integrado |
| **C/D** (protección de archivos y protocolo de aborto por descriptores) | ABORT exclusivo/no-follow **vía dirfd** (vigente tras el ancla); extensión propuesta: ancla directa por descriptor retenido (sin re-apertura de ruta) | vigente parcialmente + propuesta |
| **E1** (`INFORME_RECTIFICACION_FINAL_E1_6G1.md`) | obligatoriedad + identidad por artefacto: identidad vs fd, sin PASS por defecto ante fd ausente (E1-A/E1-B) | prototipo adjudicado; no integrado |
| **F1** (`CIERRE_RECURSOS_6G1.md` / `CORRECCION_F_6G1.md`) | ciclo de vida y cierre determinista verificable (`preparar_aborto_6g1`, `cerrar_recursos_corrida_6g1`) | vigente en producción |
| **G1** (alcance delimitado) | comparación SHA-256 **sólo** `analysis.json` y `mix_sintetico SDV.wav`; **sin ampliación** | demostrado delimitado; no integrado |

**Advertencia explícita:** PDA-1/EA/E1 son **prototipos adjudicados**. Este plan los **propone** como base de integración; **no declara** que la integración esté conseguida. La producción permanece en el estado de `cea6652` (= `292274b` en producción: los commits de diseño no tocan código).

## §5 [ENTREGABLE 1] Plan de integración — decisiones de diseño v2 (todas PROPUESTO)

Decisiones P-01..P-09 rectificadas. Marcas: **[R-A]** secuencia de cierre/verificación, **[R-B]** identidad real del descriptor de escritura, **[R-C]** anclaje de subdirectorios, **[R-D]** publicación y modelo de amenazas.

- **P-01 [R-C ampliado] — Ancla retenida desde la creación + cadena de directorios acreditada.** `crear_y_acreditar_dir_6g1_v2(padre, nombre)` (LS L367–415 → variante): misma secuencia fail-closed pero **sin cerrar** `fd_dir` ni `fd_padre`; devuelve `(ruta, (dev,ino), fd_dir, fd_padre)`. Registro propio y de anclaje claveados por **identidad/token de corrida**, no por ruta absoluta (elimina la dependencia de la cadena de rutas en todo el protocolo). **REGLA DE CADENA ACREDITADA [R-C]:** toda apertura de archivo o subdirectorio se hace **componente a componente**, cada componente relativo a un descriptor ya acreditado (`fd_padre → fd_run → fd_masks → archivo`); **prohibido** abrir rutas multi-componente (`os.path.join(...)` para abrir), porque `O_NOFOLLOW` sólo protege el componente final. Motor: `create_run_dir` (H L1430) devuelve además el ancla; `run_experiment` la conserva hasta el cierre acreditado final.
- **P-02 [R-A] — Aborto por descriptor retenido, sin re-apertura de ruta (resuelve D1).** `abortar_corrida_6g1_v2(..., fd_dir, fd_padre)`: anclaje = `os.fstat(fd_dir)` contra la identidad **del descriptor** (no de la ruta). Coincide → `ABORT_6G1.json` con `os.open("ABORT_6G1.json", O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=fd_dir)` e inventario descendiendo desde `fd_dir` (patrón vigente LS L612–767). Descriptor muerto o identidad distinta → `directorio_acreditado=False`, `abort_registrado=False`, **sin escritura en ningún árbol**, rc≠0 obligatorio. `_anclar_dir_aborto_6g1` (por ruta) queda sólo para arneses de prueba.
- **P-03 [R-B RECTIFICADO] — Creación exclusiva + ENTREGA DEL DESCRIPTOR a la biblioteca (fd-passthrough).** El patrón v1 «crear con O_EXCL, **cerrar** y reabrir por ruta» **no** acredita el descriptor interno de la biblioteca y queda **sustituido**. Nuevo patrón obligatorio para TODO archivo de salida: (1) `os.open(nombre, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=<fd acreditado>)` — creación exclusiva atómica respecto del directorio acreditado; el fd devuelto designa **incondicionalmente** el objeto creado (garantía del kernel, sin ventana); (2) `os.fstat(fd)` == identidad esperada del nuevo objeto; (3) **el mismo fd se entrega a la biblioteca** y toda la escritura ocurre sobre él; (4) cierre acreditado posterior del recurso. Tratamiento por biblioteca (detalle y fuentes en §8bis): **soundfile WAV** → `sf.SoundFile(fd, mode="w", ..., closefd=False)` → `sf_open_fd` (DOCUMENTED_FACT: `soundfile.py` L1255–1256); **Tee/engine_log y JSON/texto** → `os.fdopen(fd, "w", encoding="utf-8")` (el file object opera sobre el fd propio; lo cierra al cerrar); **re-lectura de `input_integrity_6g.json`** → `os.pread(fd, …)` sobre el mismo fd (elimina la re-apertura por ruta H L1963); **masks/memmaps** → `np.lib.format.open_memmap` **exige ruta** (DOCUMENTED_FACT: `format.py`, `open_memmap` → `open(filename, "w+b")` para la cabecera + `np.memmap(filename)`); alternativa compatible: pasar como ruta **`/proc/self/fd/<fd_propio_retenido>`** — el magic-link de procfs resuelve **al objeto designado por el fd retenido**, no a la cadena de rutas nominal (sin ventana TOCTOU nominal; dependencia procfs declarada **R-29**, fail-closed si no hay procfs; alternativa sin procfs: escribir la cabecera `.npy` con `np.lib.format.write_array_header_1_0` sobre `os.fdopen(fd)` y mapear con `np.memmap(file_object, mode="r+", offset=…)` — DOCUMENTED_FACT: `memmap.py` L227–231 acepta file object y **no lo cierra** (`nullcontext`)); **matplotlib PNG** → fuera del conjunto obligatorio (R-12: `savefig` por ruta no probado; LIMITACIÓN declarada, OPC). La «verificación posterior de la ruta» **deja de invocarse como prueba** del descriptor interno: la acreditación es el `fstat` del fd entregado antes/después del ciclo de escritura (el fd no puede cambiar de identidad). 
- **P-04 [R-B] — Lecturas post-escritura por descriptores.** (a) `input_integrity_6g.json`: pread sobre el fd propio (P-03). (b) SHA-256 G1: `_sha_via_descriptor_6g1(nombre, fd_dir, st)` (LS L416 — vigente). (c) `post_wav_identity` (H L1461–1492, llamada L1889): re-lectura de los 3 WAV con `os.open(nombre, O_RDONLY|O_NOFOLLOW, dir_fd=fd_run)` + `sf.SoundFile(fd, closefd=False)` (mismo patrón fd-passthrough en lectura); el `MixHandle` ya opera sobre fd retenido (sin cambios). (d) `engine_log.txt`: fd pre-creado con P-03 + `os.fdopen` dentro de `Tee` preservando el contrato R-17 (`error_cierre_6g1`, reintentos, estado de referencia). (e) compila `analysis.txt` desde el dict en memoria (sin re-lectura).
- **P-05 [R-A/R-C] — Compuerta de conjunto completo antes de publicar (resuelve C; E1 aplicado al conjunto).** `verificar_conjunto_publicable_6g1(fd_dir, fd_masks, modo, opts)` (sólo lectura): inventario `os.listdir(fd_dir)` + `os.lstat(nombre, dir_fd=fd_dir)`; para `full_processing` exige EXACTAMENTE: regulares no vacíos `{analysis.json, analysis.txt, engine_log.txt, input_integrity_6g.json, "mix_sintetico SDV.wav", "mix_sintetico SDI.wav"}` + `masks/` acreditado (P-08v2 subancla) con sus 6 npy (o `candidates/` cuando aplique; PNG sólo si `--png`, OPCIONAL); **RECHAZA symlinks y tipos inesperados**; **RECHAZA entradas inesperadas** (fail-closed); continuidad de identidad de cada obligatorio vs registro propio por identidad (P-07); SHA-256 vía descriptor **sólo** alcance G1 (`analysis.json`, `mix_sintetico SDV.wav` — sin ampliación); **condición «cero descriptores de escritura abiertos hacia el provisional»** vía `escritura_abierta_bajo_dir_6g1` (LS L1115, procfs; coste R-15) — acredita que el conjunto inspeccionado está estático. Fallo → `_FalloCorrida_6g1("CONJUNTO_PUBLICABLE_NO_VALIDO", detalle, trasladar=False)` → aborto (P-02). **Sin EXIT_OK si falla.**
- **P-06 [R-D RECTIFICADO] — Publicación por ancla + verificación post-rename; Afirmación honesta.** `publicar_dir_6g1_v2(fd_padre, nombre_prov, nombre_final, ...)` con `renameat2(src_dir_fd=fd_padre, dst_dir_fd=fd_padre, RENAME_NOREPLACE)` (fail-closed si indisponible). **Afirmación exacta [R-D]:** el renameat2 relativo a dirfd **NO** es una «publicación atómica por identidad del descriptor origen»: el origen es un **nombre relativo** que el kernel resuelve **dentro del directorio designado por `fd_padre` en el instante de la llamada**; si la entrada fue sustituida antes de la llamada, el objeto movido es el sustituto. Lo que el diseño garantiza es el par **«no-reemplazo del destino + acreditación de identidad POST-RENAME»**: tras el rename, `fd_pub = os.open(nombre_final, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_padre)`; `fstat(fd_pub) == (dev,ino)` del provisional (identidad≠ruta). Si no coincide → fail-closed (tabla completa en §8v2). Segunda pasada de P-05 sobre `fd_pub` (ventana compuerta→rename, R-24). Si falla tras el rename: `ABORT_6G1.json` dentro del publicado vía `fd_pub` (O_EXCL|O_NOFOLLOW) + ABORT en el real vía `fd_run` si difieren + rc≠0.
- **P-07 — Registro propio claveado por identidad.** `registrar_propio_6g1_v2(fd_dir, nombre, estable)`: registra `(identidad_dir, nombre) → (dev,ino,estable)`; `propiedad_de_6g1_v2` consulta por descriptor. La compuerta P-05 compara identidad sin depender de rutas.
- **P-08 [R-A RECTIFICADO] — Secuencia inequívoca de cierre/verificación y condición de EXIT_OK.** Secuencia OBLIGATORIA (ver §7v2 y justificación completa en el informe de rectificación §1): **(1)** finalizar todas las escrituras de datos; **(2)** cerrar y acreditar escritores WAV (`sf_close` finaliza cabeceras), memmaps (`flush` + cierre del mmap + verificación), lectores, Tee y fds propios — un error aquí eleva `CierreNoAcreditado6G1` → aborto, **nunca** compuerta; **(3)** `fd_run` y `fd_padre` PERMANECEN abiertos; **(4)** primera compuerta (P-05, sólo lectura); **(5)** publicar (P-06); **(6)** segunda compuerta sobre `fd_pub`; **(7)** cierre acreditado del anclaje (`fd_pub`, `fd_run`, `fd_padre`); **(8)** sólo entonces `EXIT_OK`. **Prohibición: ninguna escritura posterior a la compuerta final (6)** — única excepción: `ABORT_6G1.json` vía `fd_pub`/`fd_run` si la compuerta final falla (registro de aborto, no de resultado), con rc≠0. El veredicto de las compuertas NO va al `engine_log` (cerrado en el paso 2; decisión y límite en R-32): queda en la salida estándar directa y, si falla, en el ABORT. `fsync(fd)` por artefacto: **PROPUESTO opcional** (durabilidad; no aporta integridad frente a mismo-uid, no es precondición de la compuerta).
- **P-09 [R-A/R-C] — Cierre acreditado extendido y orden de recursos.** Orden de cierre (éxito y aborto): escritores WAV (sf_close) → memmaps (flush+mmap close; **después** el fd propio retenido) → lectores → `Tee` (R-17) → fds propios de JSON/TXT (si no cerrados por fdopen) → **subanclas** (`fd_masks`; `fd_candidates` si existiera) → tras la verificación post-rename: `fd_pub` → `fd_run` → `fd_padre`. `preparar_aborto_6g1` (LS L1338) incorpora anclas y subanclas con cierre verificable. Nunca cerrar un fd del que depende otro recurso vivo (procfs-magic y mmap requieren su fd retenido hasta el cierre del mapeo).

## §6 [ENTREGABLE 2] Matriz de integración por flujo (funciones reales, v2)

### FLOW-1 — éxito normal (creación, escritura, verificación, publicación, cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | `create_run_dir` H L1430 (ΔP-01/P-07); `CandidateRunner.__init__` H L1399/1401 → fd-passthrough `sf_open_fd` (ΔP-03 [R-B]); `_open_memmap` H L1456 → procfs-magic sobre fd retenido o header manual (ΔP-03 [R-B], R-29); `Tee` H L173–178 → fdopen (ΔP-03, R-17); `os.makedirs(masks_dir)` H L1615–1616 → `os.mkdir("masks", 0o700, dir_fd=fd_run)` + subancla `fd_masks` (ΔP-01 [R-C]); memmaps relativos a `fd_masks` (componente único, Δ[R-C]); `write_reports` H L2130 + `write_analysis_txt` H L2134 → fdopen (ΔP-03); bloque `input_integrity` H L1957–1966 → fdopen + pread (ΔP-04a); `post_wav_identity` H L1461/L1889 → sf_open_fd lectura (ΔP-04c); **nueva** secuencia P-08 (paso 4) compuerta antes de H L1984; publicación H L1984 → ΔP-06 [R-D]; limpieza masks H L1988–1997 (residual R-28); EXIT_OK H L1999–2000 → sólo paso 8 de P-08 |
| Recursos y propietario | anclas+subanclas: `run_experiment`; escritores WAV: `CandidateRunner`; memmaps: `run_experiment` (dict `mm`); `engine_log`: `Tee` global; `hmix`: `run_experiment`; lectores de guías: `run_experiment` |
| Fds que deben permanecer abiertos | `fd_run`, `fd_padre` (toda la vida; paso 7 de P-08); `fd_masks` hasta el cierre de los memmaps; fds internos de libsndfile (2 escritores, entregados por P-03); 6 mapeos mm + sus fds retenidos; fd `engine_log`; fd `hmix`; fds transitorios de analysis/analysis.txt/input_integrity |
| Obligatorios / opcionales | OB: `analysis.json`, `analysis.txt`, `engine_log.txt`, `input_integrity_6g.json`, `mix_sintetico SDV.wav`, `mix_sintetico SDI.wav`. OP: `masks/` (subdirectorio acreditado; se elimina tras publicar), PNGs (`--png`, R-12), WAVs de candidatos con prefijo en el raíz (`--write-all-candidates`; **`candidates/` NO existe en Hardened** — R-13 aplica a MQR) |
| Lecturas post-escritura | input_integrity re-read (pread, P-04a); post_wav sobre los 3 WAV (sf_open_fd, P-04c); SHA G1 vía descriptor (P-05); analysis.txt desde memoria |
| Excepciones/interrupciones | excepción → protocolo CV con secuencia P-08 adaptada (cierre → aborto); sin `signal.signal` (R-11) |
| EXIT_OK exacto | paso 8: (2 sin errores) ∧ (4 válido) ∧ (5 con `fstat(fd_pub)==I_run`) ∧ (6 válido) ∧ (sin ABORT en publicado) |
| ABORT exacto | CONJUNTO_PUBLICABLE_NO_VALIDO, PUBLICACION_SEGURA_FALLIDA, MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO, excepción genérica, cierre no acreditado — rc≠0, ABORT vía descriptor |
| Riesgos residuales | R-24 (compuerta→rename y post-verificación), R-28 (limpieza post-publicación cosmética), R-29 (procfs para memmaps), R-15 (coste openat/procfs) |

### FLOW-2 — excepción tras varios recursos (invalidación, aborto, cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | H L2036–2055 (`except Exception`): pasa `fd_dir`/`fd_padre`/`fd_masks` a `abortar_corrida_6g1_v2` (ΔP-02/P-09); cierre vigente (F1) sin cambios funcionales |
| Recursos y propietario | idénticos a FLOW-1 hasta la inyección (2º `sf.SoundFile` "w", H L1399–1401) |
| Fds retenidos al abortar | los existentes en el punto de la excepción; cierre determinista vigente acredita escritores/memmaps/lectores; DESPUÉS se registra el aborto (orden verificado empíricamente: `escritores=1 memmaps=6 lectores=0 completo=True errores=0`) |
| Obligatorios / opcionales | ninguno: `resultados_validos=[]` (vigente); 7 salidas invalidadas y conservadas (C-R1) |
| Lecturas post-escritura | inventario del aborto desciende desde `fd_dir` (sin rutas) |
| EXIT_OK | **imposible** por construcción (rama de excepción nunca publica) |
| ABORT | `abort-6g1/3`→`abort-6g1/4` (PROPUESTO: `abort_registrado`, `anclaje`, `identidad_dir`, `hashes_g1`, `fd_vivo`) en el provisional REAL vía `fd_dir`; traslado por ancla |
| Riesgos residuales | R-23 (fd muerto: abort sin registro en disco, rc≠0, fail-closed) |

### FLOW-3 — SIGINT (aborto y cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | H L2004–2018 (`except KeyboardInterrupt`): idéntico a FLOW-2 con anclas (ΔP-02/P-09); nada más |
| Señales | **sólo SIGINT** (sin `signal.signal`, R-11). SIGTERM/SIGKILL FUERA DE ALCANCE. PEP 475: syscalls reintentadas tras EINTR (FLOW-3 PASS empírico) |
| Fds retenidos | idénticos a FLOW-2; cierre observado `escritores=2 memmaps=6 lectores=3 completo=True errores=0` |
| Obligatorios / opcionales | masks conservadas en el provisional (C-R1); 8 invalidadas |
| EXIT_OK | imposible |
| ABORT | `INTERRUPCION_DEL_USUARIO` vía descriptor; masks «invalidada y conservada» |
| Riesgos residuales | R-11, R-23 |

### FLOW-4 — sustitución de entrada (intermedia, final, publicación, aborto)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | todas las que hoy operan por ruta pasan a operar por ancla/fd (P-03/P-04/P-05/P-06/P-02). Efecto: **ninguna operación de salida re-resuelve la ruta nominal** después de la apertura inicial |
| Sustitución INTERMEDIA | los escritores ya abiertos escriben en los inodos reales (fd entregado); post_wav lee vía `fd_dir`; compuerta inspecciona el REAL; publicación renombra el REAL vía `fd_padre`; aborto → ABORT en el REAL vía `fd_dir` (D1 cerrado) |
| Sustitución FINAL (caso b) | symlink en `analysis.json` → P-05 rechaza → aborto → **sin EXIT_OK** (C cerrado). Sustitución antes del renameat2 → verificación post-rename falla → fail-closed (tabla §8v2, R-31). Sustitución compuerta→rename → 2ª pasada sobre `fd_pub` → ABORT + rc≠0 (R-24) |
| Obligatorios / opcionales | idénticos a FLOW-1; conjunto MIXTO imposible bajo P-05 |
| EXIT_OK exacto | P-08 paso 8 completo |
| ABORT exacto | ABORT en el árbol acreditado por descriptor (métrica correcta: «ABORT en el árbol de identidad acreditada», no «en algún árbol») |
| Riesgos residuales | R-23, R-24, R-29, R-31, R-27 (fallback padre DESACTIVADO por defecto); límites: same-uid post-verificación (post-return) y DoS fuera del alcance de integridad |

## §7 [ENTREGABLE 3] Diagrama del ciclo de vida de descriptores v2 (secuencia R-A numerada)

```
              ┌────────────────────── run_experiment (propietario) ──────────────────────┐

 CREACIÓN (P-01, cadena acreditada: componente a componente)
   fd_padre ──► open(padre, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)  [euid propietario, sin W grupo/otros]
   fd_run   ──► mkdir(nombre, 0o700, dir_fd=fd_padre)
                open(nombre, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_padre) → fstat → I_run
   fd_masks ──► mkdir("masks", 0o700, dir_fd=fd_run)
                open("masks", O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_run) → fstat → I_masks
   ANCLA = (fd_padre, fd_run, fd_masks, nombres_relativos, I_run, I_masks)   [no se cierran aún]

 ESCRITURA (P-03 fd-passthrough [R-B]; cada fd entregado a su biblioteca)
   fd_log  ──► openat(fd_run,"engine_log.txt",O_CREAT|O_EXCL|O_NOFOLLOW) → fstat → os.fdopen → Tee
   fd_Wav  ──► openat(fd_run,"<Track> SDV.wav",O_CREAT|O_EXCL|O_NOFOLLOW) → fstat
               → sf.SoundFile(fd, mode="w", closefd=False) → sf_open_fd(fd)              [x2 SDV/SDI]
   fd_mm   ──► openat(fd_masks,"mask_*.npy",O_CREAT|O_EXCL|O_NOFOLLOW) → fstat → fd retenido
               → open_memmap("/proc/self/fd/<fd_mm>","w+")   [magic link → objeto del fd; R-29]
               (alt. sin procfs: write_array_header_1_0 + np.memmap(fileobj, "r+", offset))   [x6]
   fd_ai   ──► openat(fd_run,"input_integrity_6g.json",O_EXCL...) → fdopen → write → pread re-read
   fd_an   ──► openat(fd_run,"analysis.json"/"analysis.txt",O_EXCL...) → fdopen → write
   hmix    ──► MixHandle (entrada; fd retenido; vigente)

 SECUENCIA DE CIERRE Y VERIFICACIÓN [R-A] (P-08)
   (1) finalizar TODAS las escrituras de datos (OLA flush; memmap writes; JSON/TXT write)
   (2) CERRAR Y ACREDITAR: sf_close escritores WAV (cabecera final) + cerrar fd propio [closefd=False]
       → memmaps mm.flush() + mm._mmap.close() → cerrar fd_mm retenido → lectores
       → Tee.close() (contrato R-17; error ⇒ CierreNoAcreditado6G1 → ABORTO, nunca computa)
       → fds propios fd_an/fd_ai/fd_log
       ⇒ fd_run, fd_padre, fd_masks PERMANECEN ABIERTOS            ← (3)
   (4) PRIMERA COMPUERTA (sólo lectura): P-05 sobre (fd_run, fd_masks)
       — tipos, symlinks NO, inesperados NO, obligatorios no vacíos,
         identidad vs registro propio, SHA G1 (analysis.json + mix_sintetico SDV.wav),
         cero fds de escritura abiertos hacia el provisional (procfs)
   (5) PUBLICAR (P-06 [R-D]): renameat2(fd_padre, nombre_prov, fd_padre, nombre_final, NOREPLACE)
       → fd_pub = openat(fd_padre, nombre_final, O_DIRECTORY|O_NOFOLLOW) → fstat(fd_pub)==I_run
   (6) SEGUNDA COMPUERTA sobre fd_pub
   (7) CERRAR EL ANCLAJE (acreditado): fd_pub → fd_masks → fd_run → fd_padre
   (8) EXIT_OK — SÓLO si (2) sin errores ∧ (4) válido ∧ (5) identidad verificada
       ∧ (6) válido ∧ (sin ABORT_6G1.json en el publicado)
   PROHIBICIÓN [R-A]: ninguna escritura después de (6). Única excepción:
       ABORT_6G1.json vía fd_pub (y vía fd_run si el real ≠ publicado) si (6) falla + rc≠0

 ABORTO (P-02; D1 cerrado)
   fstat(fd_run) == I_run ? ──NO (fd muerto/identidad distinta)──► abort_registrado=False
        │ sí                                          sin escritura en NINGÚN árbol; rc≠0
   os.open("ABORT_6G1.json", O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=fd_run)
   inventario desde fd_run/fd_masks (sin rutas); sin eliminación (C-R1); analysis.json intacto (E-R2)
   traslado opcional: renameat2(fd_padre, nombre_prov, fd_padre, nombre_aborted, NOREPLACE)
   cierre acreditado (incluye anclas y subanclas) → rc ∈ {2,130}
```

Regla del diagrama: **después de la creación, ninguna operación de salida re-resuelve la ruta nominal**; todo se ejecuta componente a componente relativo a descriptores acreditados, y los fds de escritura son los entregados a las bibliotecas.

## §8 [ENTREGABLE 4] Diseño de publicación y aborto v2

**Publicación (`publicar_dir_6g1_v2`, pasos 4–6 de P-08):**
1. Compuerta de conjunto sobre `fd_run`+`fd_masks` (sólo lectura; condición «cero escritores abiertos»).
2. `renameat2` relativo a `fd_padre`, `RENAME_NOREPLACE`; colisión → sufijo `_r%03d` (cada intento relativo y re-verificado); fail-closed si renameat2 indisponible.
3. Acreditación post-rename: `fstat(fd_pub) == I_run`. **NO se afirma atomicidad por identidad del origen** — la acreditación es post-hoc (§5 P-06 [R-D]).
4. Segunda compuerta sobre `fd_pub`.
5. Paso 7 (cierre de anclas) → paso 8 → `EXIT_OK`. Fallo en 1–4 → aborto; si el fallo ocurrió tras el rename: `ABORT_6G1.json` vía `fd_pub` DENTRO del publicado (y vía `fd_run` en el real si difieren) + rc≠0.

**Tabla fail-closed [R-D] — los 6 casos exigidos:**

| # | Caso (antes de / en renameat2) | Qué ocurre | Detección | Comportamiento fail-closed |
|---|---|---|---|---|
| 1 | Sustitución de la **entrada nominal** del provisional (impostor/symlink en `nombre_prov`) antes del renameat2 | rename mueve el **sustituto** al nombre final; el REAL queda fuera | paso 3: `fstat(fd_pub) != I_run` | **sin EXIT_OK**; ABORT vía `fd_pub` en el objeto publicado (queda marcado «nunca corrida exitosa») + ABORT vía `fd_run` en el REAL (donde esté) + rc≠0 (R-31) |
| 2 | **Renombrado del directorio real fuera del padre** (nombre vacante) | renameat2 → **ENOENT** | excepción del rename | sin EXIT_OK; ABORT vía `fd_run` en el REAL (el descriptor sobrevive al movimiento) + rc≠0 |
| 3 | **Recreación del nombre con otro objeto** tras mover el real | rename mueve el objeto nuevo | paso 3 falla | idéntico a caso 1 |
| 4 | Verificación post-rename `fd_pub` vs `I_run` | — | `fstat` sobre el objeto **publicado** (identidad≠ruta) | es la acreditación que habilita/bloquea los pasos 6–8 |
| 5 | El objeto real queda **fuera del destino publicado** (casos 1–3) | el motor NO reintenta mover el real al destino (otro rename sería igualmente susceptible y podría reemplazar objetos) | — | garantizado: (a) nunca EXIT_OK; (b) ABORT en el REAL vía `fd_run`; (c) ABORT en lo publicado vía `fd_pub`; (d) rc≠0 (R-31: basura marcada con el nombre final es posible ante same-uid; el motor no la avala) |
| 6 | Cualquier fallo no anticipado (renameat2 indisponible, EIO, agotamiento de intentos) | — | excepción → `PUBLICACION_SEGURA_FALLIDA` | aborto por descriptor, provisional conservado, rc≠0 |

**Aborto (`abortar_corrida_6g1_v2`, P-02):** como en §7 (anclaje por fstat del descriptor → ABORT exclusivo/no-follow vía dir_fd → inventario por descriptor → traslado opcional por ancla). Campos nuevos del schema PROPUESTO `abort-6g1/4`: `abort_registrado`, `anclaje` (`descriptor_retenido|descriptor_no_valido`), `identidad_dir`, `hashes_g1` (alcance delimitado), `fd_vivo`.

## §8bis [ENTREGABLE 4-bis] Matriz de compatibilidad de bibliotecas [R-B]

Fuentes inspeccionadas (DOCUMENTED_FACT, versión vigente en el venv; sin ejecución): `soundfile.py` 0.13.1 (`_open` L1240–1258: str→`sf_open` ruta; int→`sf_open_fd(file, mode, info, closefd)`; file object→`sf_open_virtual` con callbacks; `close()` L1230–1236: `flush()+sf_close`), `numpy/core/memmap.py` 1.26.4 (L227–231: file object→`nullcontext` **sin cerrarlo**; path→`open(path, mode+'b')`; L268: `mmap.mmap(fid.fileno(), …)`), `numpy/lib/format.py` (`open_memmap`: escribe cabecera con `open(filename,'w+b')` y luego `np.memmap(filename, …)` — **exige ruta**).

| Biblioteca / uso | ¿Acepta fd o file object? | ¿Viable vía `/proc/self/fd/N`? | ¿Exige ruta? | ¿Duplica/conserva/cierra el fd? | TOCTOU residual | Comprobación que acredita el descriptor de escritura | Garantía |
|---|---|---|---|---|---|---|---|
| **soundfile — escritores WAV** (`sf.SoundFile(fd, mode="w", closefd=False)`) | SÍ: fd int directo (`sf_open_fd`, L1255–1256) | innecesario | NO (con fd) | **conserva** el fd entregado; NO lo duplica; con `closefd=False` NO lo cierra (`sf_close` no cierra el fd) | **ninguna** (un fd no puede redirigirse) | `fstat(fd)` previo == identidad del `openat O_EXCL`; el fd entregado ES el descriptor interno de libsndfile | **COMPLETA** |
| **soundfile — lectores post_wav** (`sf.SoundFile(fd, mode="r", closefd=False)`) | SÍ (mismo mecanismo) | innecesario | NO | conserva; no cierra (closefd=False) | ninguna | fstat(fd) previo + openat O_NOFOLLOW relativo a fd_run | **COMPLETA** |
| **soundfile — file object** (`sf_open_virtual`, callbacks read/seek/write/tell sobre el objeto) | SÍ: file object con attrs VIO | innecesario | NO | el objeto es del motor (`os.fdopen`); soundfile no toca fds | ninguna (callbacks → fd propio) | el objeto fdopen encapsula el fd acreditado; `f.fileno()` verificable | **COMPLETA** (alternativa equivalente) |
| **numpy `open_memmap`** (cabecera `.npy` + memmap) | NO: **exige ruta** (abre por ruta 2 veces) | SÍ: `/proc/self/fd/<fd_retenido>` — el magic-link resuelve al **objeto designado por el fd retenido**, no a la cadena nominal | SÍ (intrínseco) | abre SUS PROPIOS file objects sobre la ruta procfs y los cierra; el mapeo `mmap` queda anclado al inodo (referencia propia); el **fd retenido** es del motor y NO lo toca | ninguna respecto de la ruta nominal (el magic-link fija el objeto); dependencia de procfs (**R-29**) | `fstat(fd_retenido)` acreditado al crear; el mapeo nace de `open()` sobre el magic-link de ESE fd; identidad verificable con `mm.filename`/fstat pre-cierre | **ACOTADA-COMPLETA** (inodo garantizado por kernel; requisito procfs declarado) |
| **numpy `np.memmap` directo** (alternativa sin procfs) | SÍ: file object (`nullcontext`, NO lo cierra) o fd | innecesario | NO (con file object) | conserva el objeto; `mmap.mmap(fileno)` ancla el mapeo; motor cierra el objeto acreditado | ninguna | fstat del fd del file object; cabecera `.npy` escrita antes con `write_array_header_1_0` sobre `fdopen(fd)` | **COMPLETA** |
| **Tee / engine_log** (Python io) | SÍ: `os.fdopen(fd, "w", encoding="utf-8")` | innecesario | NO | fdopen **toma posesión**: conserva el fd y lo cierra al `close()` (contrato R-17 preservado) | ninguna | fstat(fd) previo; el objeto Python opera sobre el fd entregado | **COMPLETA** |
| **JSON / texto** (`analysis.json`, `analysis.txt`, `input_integrity_6g.json` y su re-lectura) | SÍ: `os.fdopen(fd,…)` para escribir; re-lectura con `os.pread(fd,…)` sobre el mismo fd | innecesario | NO | idem fdopen | ninguna | fstat(fd) previo; pread no re-resuelve nada | **COMPLETA** |
| **matplotlib PNG** (`savefig`) | acepta file object en la API, **no probado** | — | hoy por ruta (H L2204) | — | por ruta (no anclada) | ninguna hoy | **LIMITACIÓN/UNKNOWN** (R-12; OPC — fuera del conjunto obligatorio) |
| **libsndfile por ruta** (`sf_open` — usado hoy en writers L1399/1401 y en lectores vigentes) | — | SÍ (procfs) pero innecesario con fd | SÍ (vigente) | libsndfile abre/cierra su propio fd por ruta | **ventana por ruta** (resuelta al migrar a fd) | hoy: ninguna (por eso C fue posible) | vigente = **DÉBIL** → sustituido por fd en este plan |
| **procfs `/proc/self/fd/N`** (soporte del entorno) | — | — | — | — | — | — | dependencia declarada (**R-29**): si `/proc` no está montado → fail-closed a la alternativa sin procfs o aborto; DOCUMENTED_FACT del entorno vigente |

**Conclusión [R-B]:** la única biblioteca del conjunto obligatorio que **exige ruta** es `open_memmap`; se resuelve con fd retenido + magic-link (o reconstrucción manual de cabecera sin procfs). Con el patrón fd-passthrough, la afirmación «el descriptor utilizado para escribir corresponde al objeto esperado» queda acreditada por `fstat` del fd entregado (garantía del kernel: un fd designa un inodo y no puede ser re-dirigido), **sin** apelar a verificaciones posteriores por ruta.

## §9 [ENTREGABLE 5] Diseño de pruebas de regresión D1/C ampliado (PROPUESTO — NO EJECUTADO)

Arnés aislado `scripts/arnes_regresion_d1_c_6g1.py` sobre el motor **con los cambios propuestos** (fixtures sintéticos de la línea base; árboles en `/tmp`; hooks en memoria; motor sin ejecutar en esta fase).

| Caso | Estímulo | Veredicto esperado (post-integración) |
|---|---|---|
| REG-D1-a | swap durante el procesamiento (renombrar provisional real + recrear nombre) | la corrida continúa sobre los inodos reales; publica el REAL o aborta con ABORT en el REAL; señuelo sin artefactos; EXIT_OK sólo si P-08 completo |
| REG-D1-b | vaciar + `rmdir` del provisional real entre cierre y aborto (fd muerto) | `abort_registrado=False`, `anclaje=descriptor_no_valido`, sin ABORT en ningún árbol, rc≠0 |
| REG-D1-c | ruta del provisional convertida en symlink (ELOOP) antes del aborto | ABORT presente en el árbol real vía descriptor (la ruta es irrelevante) |
| **REG-D1-d [R-D caso 1/3]** | sustituir la entrada `nombre_prov` por un impostor ANTES del renameat2 | paso 3 detecta `fstat(fd_pub) != I_run` → **sin EXIT_OK**; ABORT vía `fd_pub` en lo publicado + ABORT vía `fd_run` en el real; rc≠0 |
| **REG-D1-e [R-D caso 2]** | renombrar el provisional real FUERA del padre antes del renameat2 | renameat2 ENOENT → sin EXIT_OK; ABORT vía `fd_run` en el real (donde esté); rc≠0 |
| REG-C-a | hook en la compuerta: `analysis.json` → symlink al impostor | `CONJUNTO_PUBLICABLE_NO_VALIDO` → aborto por descriptor; sin EXIT_OK; impostor intacto |
| REG-C-b | hook entre compuerta 1 y renameat2: sustituir archivo del provisional | 2ª compuerta sobre `fd_pub` detecta → ABORT dentro del publicado vía `fd_pub` + rc≠0 |
| REG-C-c | archivo inesperado en el provisional antes de la compuerta | compuerta falla (entrada inesperada) → aborto, sin EXIT_OK |
| **REG-C-d [R-C]** | sustituir `masks/` por un symlink ANTES de abrir memmaps | `openat(O_NOFOLLOW, dir_fd=fd_run)` falla (ELOOP/EEXIST) → aborto; sin escritura fuera del acreditado |
| **REG-C-e [R-C]** | archivo inesperado o symlink DENTRO de `masks/` | la compuerta desciende por `fd_masks` y rechaza (tipo inesperado) → aborto |
| **REG-B-a [R-B]** | auditoría de descriptores durante la escritura (procfs del proceso arnés/motor): `/proc/PID/fd` de cada escritor | cada fd de escritura apunta a inodos acreditados; tras el cierre, los inodos contienen el contenido esperado (validación del fd-passthrough; el arnés no modifica el motor) |

Clasificación: **PROPUESTO** (diseño); su ejecución requiere nueva autorización. No sustituye la línea base adjudicada.

## §10 [ENTREGABLE 6] Registro de riesgos y limitaciones (extensión PROPUESTA; IDs nuevos desde R-23)

| ID propuesto | Estado | Riesgo / limitación | Plan |
|---|---|---|---|
| R-23 | PROPUESTO | Descriptor del provisional muerto (mismo-uid vacía y elimina el dir entre cierre y aborto): ABORT no puede escribirse en disco | fail-closed `abort_registrado=False` + rc≠0; evidencia en consola; sin EXIT_OK |
| R-24 | PROPUESTO (ajustado en v2) | Ventanas: compuerta→rename y post-verificación post-rename; sustituciones same-uid en esos intervalos | 2ª compuerta sobre `fd_pub`; residual post-verificación = límite post-return documentado |
| R-25 | PROPUESTO | Escrituras WAV por `fileobj`: no necesarias tras la rectificación (fd directo `sf_open_fd` DOCUMENTED_FACT); se conserva como repliegue | re-evaluar sólo si cambia la versión de soundfile (R-34) |
| R-26 | PROPUESTO (**RECTIFICADO en v2**) | v1 declaraba micro-ventana «pre-creación→reapertura por ruta»; **el fd-passthrough la elimina** (el fd del `openat O_EXCL` se entrega directamente; no hay re-apertura). Residual: la variante memmap depende de procfs | ver R-29 |
| R-27 | PROPUESTO | Fallback de ABORT en el padre validado (si se habilitara) podría ser eliminado por mismo-uid | por defecto **DESACTIVADO** (sólo fail-closed); decisión pendiente de Cris |
| R-28 | PROPUESTO | Limpieza `masks/` post-publicación por ruta (`shutil.rmtree`, H L1992) | ventana post-publicación; impacto cosmético/DoS, no de integridad; migración opcional a `unlinkat` por descriptor |
| **R-29 [R-B]** | PROPUESTO | **Dependencia procfs** de la variante `open_memmap("/proc/self/fd/N")`: entornos sin `/proc` montado no soportan el magic-link | fail-closed → alternativa sin procfs (cabecera manual + `np.memmap(fileobj)`) o aborto; elección en implementación |
| **R-30 [R-D]** | PROPUESTO | **Post-verificación**: tras el paso 6, un same-uid puede seguir sustituyendo el nombre final; el motor ya no verifica (no hay escritura ni re-inspección posterior — prohibición R-A) | límite del modelo de amenazas (post-return); aislamiento adicional (monturas privadas/namespace) fuera del alcance 6G.1 |
| **R-31 [R-D]** | PROPUESTO | En los casos D-1/D-3, el impostor renombrado queda con el **nombre final** (marcado con ABORT vía `fd_pub`) y el real fuera: basura nominal posible ante same-uid | el motor jamás lo avala (rc≠0 + ABORT); recomendación operativa documental: el consumidor debe exigir ausencia de `ABORT_6G1.json` + verificar identidad externamente |
| **R-32 [R-A]** | PROPUESTO | El `engine_log` termina en el paso 2: el veredicto de las compuertas queda fuera del log (sólo consola directa + ABORT si falla) | aceptado a cambio del orden exigido; alternativa futura: artefacto de evidencia `verificacion_conjunto_6g1.json` si Cris lo aprueba |
| **R-33 [R-A]** | PROPUESTO | `fsync` opcional: sin él, la durabilidad ante crash del SO no está garantizada (no afecta a la integridad frente a mismo-uid) | PROPUESTO opcional/configurable |
| **R-34 [R-B]** | PROPUESTO | El fd-passthrough se apoya en el comportamiento vigente de python-soundfile 0.13.1 (`sf_open_fd`, `closefd`) y numpy 1.26.4 (`nullcontext`/`open_memmap` por ruta) — DOCUMENTED_FACT **por versión** | re-verificación documental en cualquier upgrade de dependencias antes de conservar la garantía |
| R-11, R-12, R-15, R-18 | vigentes | sin cambios; R-15 se re-evaluará con el coste de openat/compuertas/procfs | fuera de esta fase |

**Limitaciones del modelo de amenazas (declaración expresa [R-D]):** el modelo cubre un atacante **same-uid con control de rutas** durante la corrida, en un FS POSIX/Linux sin aislamiento adicional. El diseño **NO** puede garantizar (y no afirma): que el nombre final del FS siga designando el objeto verificado después del paso 6 (R-30); que un impostor no quede renombrado al nombre final en casos D-1/D-3 (R-31, sólo queda marcado y rc≠0); protección ante root, post-return sobre publicados, DoS (disco/renames/fd exhaustion), kernels sin `renameat2`-dirfd (fail-closed), SIGTERM/SIGKILL (R-11). Mitigación completa de same-uid requeriría aislamiento (mount namespace/permisos del árbol de salida gestionados por el entorno), **fuera del alcance 6G.1 actual**. El hash G1 cubre sólo `analysis.json` + `mix_sintetico SDV.wav` (sin ampliación): para el resto, la protección es de identidad/obligatoriedad, no de contenido («LECTURA ANCLADA», nunca «contenido íntegro» — T7).

## §11 Distinción epistémica

**DEMOSTRADO (evidencia publicada en `292274b`):** FLOW-1/2/3 PASS; D1 y frontera temporal de FLOW-4; C (EXIT_OK con analysis.json symlink); mapa vigente de §2 (inspección estática).

**DOCUMENTED_FACT (nuevo en v2):** comportamiento de las bibliotecas vigentes citado con archivo:línea (§8bis): `sf_open_fd` + `closefd` + `sf_open_virtual` (soundfile 0.13.1); `np.memmap` file object con `nullcontext` y `open_memmap` por ruta (numpy 1.26.4); `/proc/self/fd/N` como re-apertura del objeto designado por un fd (kernel Linux).

**PROPUESTO (este plan v2, pendiente de adjudicación):** P-01..P-09 rectificados; secuencia R-A de 8 pasos; fd-passthrough; subanclas de subdirectorios y regla de cadena acreditada; tabla fail-closed de publicación; schema `abort-6g1/4`; arnés de regresión ampliado (11 casos); riesgos R-23..R-34.

**DESCONOCIDO:** transferencia a EVO/MQR; entorno sin procfs (R-29) en producción real; coste de rendimiento (R-15); disponibilidad renameat2-dirfd en entornos objetivo; señales no-Ctrl-C (R-11); atacantes fuera de las ventanas diseñadas; comportamiento de versiones futuras de las bibliotecas (R-34).

## §12 [ENTREGABLE 7] Manifiesto y SHA-256

`MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` + `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` (regenerados para v2; incluyen el plan rectificado y el informe de rectificación).

## §13 Restricciones y parada

1. CERO modificaciones de producción (motores, `lectura_segura_6g1.py`, DSP, fórmulas, parámetros); CERO ejecución del motor; CERO pruebas adicionales; CERO audio real; CERO Android/Termux; CERO FLOW-5..8; CERO EVO/MQR; CERO merge/cherry-pick/main; PR #2 intacto.
2. Este commit contiene **sólo** documentación de diseño (archivos añadidos/modificados de documentos; nada de producción).
3. **No se implementa nada. Parada obligatoria** a la espera de la adjudicación de Cris.

— Fin del plan v2.
