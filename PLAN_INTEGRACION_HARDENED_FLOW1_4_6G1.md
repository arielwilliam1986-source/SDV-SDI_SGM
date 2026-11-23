# PLAN DE INTEGRACIÓN — HARDENED FLOW-1..4 / 6G.1 (SÓLO DISEÑO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **exclusivamente DISEÑO**. Autorización vigente: «La autorización actual es exclusivamente de diseño». **No se implementó nada.** Cero modificaciones de producción; cero ejecución del motor en esta fase; cero pruebas de línea base repetidas.
- **Fecha:** 23-11-2026 (post adjudicación de la línea base RG-FLOW-1..4).
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`. **Commit padre:** `292274b28dd4bef4b68055d5f0d1869c0aa0a02f` (verificado local = origin = `gh api` ANTES de trabajar). Este documento se publica en un **commit hijo directo** de `292274b`.
- **Regla de lectura:** cada afirmación de este plan está clasificada como **DEMOSTRADO** (evidencia experimental publicada), **PROPUESTO** (este diseño, pendiente de adjudicación/implementación) o **DESCONOCIDO** (§11).

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

## §2 Mapa vigente del código real (DEMOSTRADO — inspección estática sobre `292274b`, sin modificación)

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
| masks | H L1615–1616, L1628–1639 | `os.makedirs(masks_dir)` **por ruta**; 6 memmaps (`mask_gp01_vocal/instrumental`, `consensus_vocal/instrumental_<method>`, `confidence_map`, `model_disagreement_map`) | por ruta |
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
| **PDA-1** (`DISENO_PUBLICACION_ANCLADA_6G1.md`) | ancla **(fd_padre, nombre_relativo, identidad)**; `crear_y_acreditar_dir_6g1_v2` que NO cierra el descriptor del padre; `renameat2` **relativo a descriptores** (`src_dir_fd=fd_padre, dst_dir_fd=fd_padre`); cierre acreditado del ancla en el protocolo de recursos | prototipo adjudicado; **NO integrado en producción** |
| **EA** (ciclo de vida anclado, `INFORME_PDA1_PROTECCION_CICLO_6G1.md` / `CICLO_VIDA_6G1.md`) | el provisional vive como **objeto designado por descriptor** desde la creación hasta el cierre/publicación | prototipo adjudicado; no integrado |
| **C/D** (protección de archivos y protocolo de aborto por descriptores) | ABORT exclusivo/no-follow **vía dirfd** (ya vigente en LS L660+: `O_CREAT\|O_EXCL\|O_NOFOLLOW`+dir_fd tras el ancla); extensión propuesta: ancla directa por descriptor retenido (sin re-apertura de ruta) | vigente parcialmente (tras ancla por ruta) + propuesta |
| **E1** (`INFORME_RECTIFICACION_FINAL_E1_6G1.md`) | obligatoriedad + identidad por artefacto: identidad vs fd, sin PASS por defecto ante fd ausente (E1-A/E1-B) | prototipo adjudicado; no integrado |
| **F1** (`CIERRE_RECURSOS_6G1.md` / `CORRECCION_F_6G1.md`) | ciclo de vida y cierre determinista verificable (`preparar_aborto_6g1`, `cerrar_recursos_corrida_6g1`) | vigente en producción |
| **G1** (alcance delimitado) | comparación SHA-256 **sólo** `['analysis.json', 'mix SDV.wav']` — en Hardened: `analysis.json` y `mix_sintetico SDV.wav`; **sin ampliación** | demostrado delimitado; no integrado |

**Advertencia explícita:** PDA-1/EA/E1 son **prototipos adjudicados** (evidencia experimental sobre arneses). Este plan los **propone** como base de integración; **no declara** que la integración esté conseguida. La producción permanece en el estado de `292274b`.

## §5 [ENTREGABLE 1] Plan de integración — decisiones de diseño (todas PROPUESTO)

Decisiones P-01..P-09. Cada una indica: qué cambia (función real + línea vigente), por qué, y qué ventana residual queda.

- **P-01 — Ancla retenida desde la creación (EA/PDA-1).** Nueva variante en `lectura_segura_6g1.py`: `crear_y_acreditar_dir_6g1_v2(padre, nombre)` → misma secuencia fail-closed que L367–415 pero **sin cerrar** `fd_dir` ni `fd_padre`; devuelve `(ruta, (dev,ino), fd_dir, fd_padre)`. El registro deja de ser por ruta: nuevo `_CORRIDA_6G1` claveado por **identidad** (token de corrida), no por ruta absoluta (elimina la dependencia de la cadena de rutas en TODO el protocolo). Motor: `create_run_dir` (H L1430) devuelve además el ancla; `run_experiment` la conserva en locales hasta el cierre acreditado final.
- **P-02 — Aborto por descriptor retenido, sin re-apertura de ruta (resuelve D1).** Nueva variante `abortar_corrida_6g1_v2(..., fd_dir, fd_padre)`: la verificación de anclaje es `os.fstat(fd_dir)` contra la identidad registrada **del descriptor** (no contra la ruta). Si coincide → `ABORT_6G1.json` se escribe con `os.open("ABORT_6G1.json", O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=fd_dir)` y el inventario desciende desde `fd_dir` (reutiliza el patrón vigente LS L612–767). Si el descriptor está muerto (directorio vaciado y `rmdir` por el atacante) o la identidad no coincide → `directorio_acreditado=False`, `abort_registrado=False`, **sin escritura en ningún árbol**, registro en consola/log y rc≠0 obligatorio. `_anclar_dir_aborto_6g1` (por ruta) queda sólo para arneses de prueba.
- **P-03 — Creación exclusiva de cada archivo de salida.** En `CandidateRunner.__init__` (H L1399/1401), `_open_memmap` (H L1456), `init_tee` (H L176), `write_reports`/`write_analysis_txt`/`input_integrity` (H L2130, L2134, L1957): pre-creación `os.open(nombre, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=fd_dir)` → `fstat` → cierre → apertura por la biblioteca → **re-verificación de identidad** (`os.stat(nombre, dir_fd=fd_dir)` == ino pre-creado). Ventana pre-creación→apertura: **TOCTOU ACOTADA**, no eliminable con libsndfile/memmap (P-07); la re-verificación la detecta salvo sustitución en la micro-ventana posterior a la verificación (documentada en R-26).
- **P-04 — Escritura y re-lectura mediante descriptores retenidos.** (a) `input_integrity_6g.json`: escribir en fd retenido (`os.fdopen`) y re-leer con `os.pread` **sobre el mismo fd** tras `flush` (elimina la re-apertura por ruta L1963). (b) `analysis.json`/`analysis.txt`: fd retenido; el SHA-256 de G1 se calcula con `_sha_via_descriptor_6g1(nombre, fd_dir, st)` (LS L416 — ya vigente). (c) `post_wav_identity` (H L1461–1492, llamada L1889): re-lectura de los 3 WAV vía `openat(fd_dir)` + `sf.SoundFile(fileobj=...)` (lecturas por fileobj: factibilidad alta, documentada por soundfile; **PROPUESTO**, a validar en la fase de implementación); alternativa de repliegue (opción B): mantener lectura por ruta con `lstat` inmediatamente previo de identidad (ventana ACOTADA declarada). (d) `engine_log.txt`: `Tee` conservando contrato R-17; acepta descriptor pre-creado (P-03) y escribe por el mismo fd.
- **P-05 — Compuerta de conjunto completo antes de publicar (resuelve C; E1 aplicado al conjunto).** Nueva función `verificar_conjunto_publicable_6g1(fd_dir, modo, opts)` en `lectura_segura_6g1.py`: inventario `os.listdir(fd_dir)` + `os.lstat(nombre, dir_fd=fd_dir)` (sin recorrer rutas); para `full_processing` exige EXACTAMENTE: regulares `{analysis.json, analysis.txt, engine_log.txt, input_integrity_6g.json, "mix_sintetico SDV.wav", "mix_sintetico SDI.wav"}` (no vacíos) + directorio `masks/` con los 6 npy esperados (o `candidates/` con prefijos cuando `--write-all-candidates`; PNG sólo si `--png`, OPCIONAL); **RECHAZA** symlinks y cualquier tipo inesperado; **RECHAZA entradas inesperadas** (fail-closed); verifica continuidad de identidad de cada obligatorio contra el registro propio (clave identidad+nombre, P-07); calcula SHA-256 vía descriptor **sólo** para el alcance G1 (`analysis.json`, `mix_sintetico SDV.wav` — sin ampliación). Fallo → `_FalloCorrida_6g1("CONJUNTO_PUBLICABLE_NO_VALIDO", detalle, trasladar=False)` → protocolo de aborto (P-02). **Sin EXIT_OK si falla.**
- **P-06 — Publicación por ancla + verificación post-rename (PDA-1 adjudicado, aplicado).** `publicar_dir_6g1_v2(fd_padre, nombre_prov, nombre_final, ...)` con `renameat2(src_dir_fd=fd_padre, dst_dir_fd=fd_padre, RENAME_NOREPLACE)` vía ctypes (variantes dirfd; fail-closed si indisponible — igual que L769–802 hoy). Tras el rename: `fd_pub = os.open(nombre_final, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_padre)`; `fstat(fd_pub)` == `(dev,ino)` del provisional (identidad≠ruta). Segunda pasada de P-05 sobre `fd_pub` (ventana compuerta→rename, R-24). Si falla: `ABORT_6G1.json` dentro del publicado vía `fd_pub` (O_EXCL|O_NOFOLLOW) + rc≠0 (regla vigente ya documentada: «un directorio con ABORT_6G1.json nunca es una corrida exitosa»).
- **P-07 — Registro propio claveado por identidad.** `registrar_propio_6g1_v2(fd_dir, nombre, estable)`: registra `(identidad_dir, nombre) → (dev,ino,estable)`; `propiedad_de_6g1_v2` consulta por descriptor. Permite a la compuerta P-05 comparar identidad sin depender de rutas (elimina la clase de confusiones ruta/objeto).
- **P-08 — Invariante de EXIT_OK (condición necesaria y suficiente).** `EXIT_OK ⇔ (guarda de entrada CV superada) ∧ (conjunto_publicable_valido en fd_dir y en fd_pub) ∧ (publicación por ancla exitosa) ∧ (fstat(fd_pub) == identidad provisional) ∧ (sin ABORT_6G1.json en el publicado) ∧ (cierre acreditado sin errores: `CierreNoAcreditado6G1` ausente) ∧ (`abort_registrado` no requerido)`. Cualquier incumplimiento → protocolo de aborto con rc∈{1,2,130}. **Nunca EXIT_OK con verificación obligatoria fallida.**
- **P-09 — Cierre acreditado extendido.** `preparar_aborto_6g1` (LS L1338) y el cierre normal incorporan los anclas: `anchores=(fd_run, fd_padre)` con cierre verificable (`cerrar_verificado_6g1`); en éxito, los anclas se cierran **sólo después** de la verificación post-rename (P-06).

## §6 [ENTREGABLE 2] Matriz de integración por flujo (funciones reales)

Leyenda: **OB** = archivo obligatorio; **OP** = opcional; Δ = cambio propuesto; «fds retenidos» = los que DEBEN permanecer abiertos en cada fase.

### FLOW-1 — éxito normal (creación, escritura, verificación, publicación, cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | `create_run_dir` H L1430 (ΔP-01/P-07); `CandidateRunner.__init__` H L1399/1401 (ΔP-03); `_open_memmap` H L1456 (ΔP-03); `init_tee`/`Tee` H L215/L173 (ΔP-03/P-04d, R-17); `os.makedirs(masks_dir)` H L1615–1616 → `os.mkdir(dir_fd=fd_run)` (ΔP-03); `write_reports` H L2130 + `write_analysis_txt` H L2134 (ΔP-03/P-04b); bloque `input_integrity` H L1957–1966 (ΔP-04a); `post_wav_identity` H L1461/L1889 (ΔP-04c); **nueva** llamada a compuerta P-05 antes de H L1984; `publicar` H L1984 → ΔP-06; limpieza masks H L1988–1997 (Δ residual R-28); salida EXIT_OK H L1999–2000 (ΔP-08) |
| Recursos y propietario | provisional + anclas: `run_experiment`; escritores WAV: `CandidateRunner`; memmaps: `run_experiment` (dict `mm`); `engine_log`: `Tee` global; `hmix`: `run_experiment`; lectores de guías: `run_experiment` |
| Fds que deben permanecer abiertos | `fd_run`, `fd_padre` (toda la vida de la corrida; cierre acreditado al final — P-09); fds internos de libsndfile (2 escritores); 6 fds de memmaps; fd `engine_log`; fd `hmix`; fds transitorios de analysis/analysis.txt/input_integrity |
| Obligatorios / opcionales | OB: `analysis.json`, `analysis.txt`, `engine_log.txt`, `input_integrity_6g.json`, `mix_sintetico SDV.wav`, `mix_sintetico SDI.wav`. OP: `masks/` (se elimina tras publicar), PNGs (`--png`, R-12), `candidates/` WAVs (`--write-all-candidates`) |
| Lecturas post-escritura | `input_integrity` re-read (→ pread, P-04a); `post_wav_identity` sobre los 3 WAV (→ openat/fileobj, P-04c); SHA G1 vía descriptor (P-05); compila `analysis.txt` desde el dict en memoria (sin re-lectura) |
| Excepciones/interrupciones | excepción → protocolo CV (cierre determinista → aborto → traslado); sin `signal.signal` (R-11) |
| EXIT_OK exacto | invariante P-08 completa |
| ABORT exacto | fallo de compuerta (CONJUNTO_PUBLICABLE_NO_VALIDO), fallo de publicación (PUBLICACION_SEGURA_FALLIDA), mix cambiado (MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO), excepción genérica, cierre no acreditado — todos con rc≠0 y ABORT vía descriptor |
| Riesgos residuales | R-26 (micro-ventana pre-creación→apertura), R-24 (ventana compuerta→rename; mitigada con 2ª pasada), R-28 (limpieza masks post-publicación por ruta; cosmético), R-15 (coste openat adicional no medido) |

### FLOW-2 — excepción tras varios recursos (invalidación, aborto, cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | H L2036–2055 (`except Exception`): pasa `fd_dir`/`fd_padre` a `abortar_corrida_6g1_v2` (ΔP-02); `preparar_aborto_6g1` LS L1338 (ΔP-09, anclas); resto del cierre vigente (F1) **sin cambios funcionales** |
| Recursos y propietario | idénticos a FLOW-1 hasta el punto de inyección (2º `sf.SoundFile` "w", H L1399–1401) |
| Fds retenidos al abortar | los que existan en el punto de la excepción; el cierre determinista vigente los acredita (escritores/memmaps/lectores) y DESPUÉS se registra el aborto (orden vigente ya verificado empíricamente: `escritores=1 memmaps=6 lectores=0 completo=True errores=0`) |
| Obligatorios / opcionales | ninguno: `resultados_validos=[]` siempre (vigente); 7 salidas invalidadas y conservadas (C-R1) |
| Lecturas post-escritura | el inventario del aborto desciende desde `fd_dir` (sin rutas) |
| Excepciones | la propia inyección de excepción ES el escenario; orden cierre→ABORT→(traslado)→close_tee vigente (H L2036–2055) |
| EXIT_OK | **imposible** por construcción (rama de excepción nunca publica) |
| ABORT | `abort-6g1/3`→`abort-6g1/4` (PROPUESTO: añade `abort_registrado`, `anclaje`, `directorio_acreditado`, hashes G1 del provisional) en el provisional REAL vía `fd_dir`; traslado a `_aborted*` por ancla |
| Riesgos residuales | R-23 (fd muerto: abort sin registro en disco, rc≠0, fail-closed) |

### FLOW-3 — SIGINT (aborto y cierre)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | H L2004–2018 (`except KeyboardInterrupt`): idéntico a FLOW-2 con `fd_dir`/`fd_padre` (ΔP-02/P-09); nada más |
| Señales | **sólo SIGINT** (KeyboardInterrupt; sin `signal.signal`, R-11). SIGTERM/SIGKILL siguen FUERA DE ALCANCE. PEP 475: syscalls reintentadas tras EINTR — el disparo durante escrituras libsndfile ya demostrado seguro empíricamente (FLOW-3 PASS) |
| Fds retenidos | idénticos a FLOW-2; cierre observado `escritores=2 memmaps=6 lectores=3 completo=True errores=0` |
| Obligatorios / opcionales | masks conservadas en el provisional (C-R1, sin borrado — vigente); 8 salidas invalidadas |
| EXIT_OK | imposible (misma razón) |
| ABORT | `INTERRUPCION_DEL_USUARIO` vía descriptor; masks listadas como «invalidada y conservada» |
| Riesgos residuales | R-11 (no-Ctrl-C), R-23 |

### FLOW-4 — sustitución de entrada (intermedia, final, publicación, aborto)

| Aspecto | Contenido |
|---|---|
| Funciones que cambian | TODAS las que hoy operan por ruta y pasan a operar por ancla: writers/memmaps/Tee (P-03), post_wav (P-04c), compuerta (P-05), publicación (P-06), aborto (P-02). Efecto: **ninguna operación de salida re-resuelve la ruta nominal** después de la apertura inicial |
| Sustitución INTERMEDIA (caso a1/a2) | con anclas: los escritores ya abiertos escriben en los inodos reales (libsndfile retiene su fd); `post_wav_identity` lee vía `fd_dir` (P-04c) → **ya no falla por ruta secuestrada**; la compuerta P-05 inspecciona el REAL vía `fd_dir`; la publicación renombra el REAL vía `fd_padre` (P-06). El árbol del atacante queda como señuelo sin artefactos de motor. Aborto si algo falla: ABORT en el REAL vía `fd_dir` (D1 cerrado) |
| Sustitución FINAL (caso b) | symlink en `analysis.json` → P-05 rechaza (S_ISLNK vía lstat(dir_fd)) → `CONJUNTO_PUBLICABLE_NO_VALIDO` → aborto por descriptor → **sin EXIT_OK** (C cerrado). Sustitución en la ventana compuerta→rename → 2ª pasada P-05 sobre `fd_pub` → ABORT dentro del publicado + rc≠0 (P-06/R-24) |
| Obligatorios / opcionales | idénticos a FLOW-1; el conjunto publicado MIXTO (symlink atacante + regulares) queda **imposible** bajo P-05 |
| Lecturas post-escritura | idénticas a FLOW-1, todas por ancla |
| EXIT_OK exacto | P-08 (incluye identidad publicada == provisional) |
| ABORT exacto | cualquier detección → ABORT en el árbol REAL (identificado por identidad, no por ruta); «ABORT en algún árbol» deja de ser la métrica: la métrica es «ABORT en el árbol acreditado por descriptor» |
| Riesgos residuales | R-23, R-24, R-26, R-27 (fallback padre: por defecto DESACTIVADO), y limitaciones del modelo: atacante mismo-uid post-publicación (post-return) y DoS (llenado de disco, renombrados masivos) siguen fuera del alcance de integridad |

## §7 [ENTREGABLE 3] Diagrama del ciclo de vida de descriptores

```
                    ┌────────────────────────────────────────────────────────────┐
                    │ run_experiment (propietario)                                │
                    └────────────────────────────────────────────────────────────┘

 crear_run_dir (P-01)
   fd_padre ──► open(padre, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)   [validado: euid, sin W grupo/otros]
   fd_run   ──► mkdir(nombre, 0o700, dir_fd=fd_padre)
                open(nombre, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_padre)
                fstat(fd_run) ──► IDENTIDAD I_run=(dev,ino) registrada por identidad (P-07)
   ANCLA = (fd_padre, fd_run, nombre_relativo, I_run)   ...no se cierran hasta el final (P-09)

   fd_log ──► openat(fd_run,"engine_log.txt",O_CREAT|O_EXCL|O_NOFOLLOW) → Tee (P-03/P-04d)
   fd_Wav ──► openat(fd_run,"<Track> SDV.wav",O_CREAT|O_EXCL|O_NOFOLLOW) → fstat
              → sf.SoundFile(ruta,"w") → os.stat(ruta)==ino pre-creado (P-03)   [x2 SDV/SDI]
   fd_mm  ──► openat(fd_run,"masks/*.npy",...) → open_memmap(ruta,"w+") → verif ino (P-03)  [x6]
   fd_ai  ──► openat(fd_run,"input_integrity_6g.json",...) → write + pread re-read (P-04a)
   fd_an  ──► openat(fd_run,"analysis.json"/"analysis.txt",...) → write (P-04b)
   hmix   ──► MixHandle (entrada; fd de lectura retenido, verificación vigente)

 ÉXITO (P-05/P-06/P-08):
   verificar_conjunto_publicable_6g1(fd_run)  ──FAIL──► aborto (abajo)
   renameat2(fd_padre, nombre_prov, fd_padre, nombre_final, RENAME_NOREPLACE)
   fd_pub ──► openat(fd_padre, nombre_final, O_DIRECTORY|O_NOFOLLOW) → fstat(fd_pub)==I_run
   verificar_conjunto_publicable_6g1(fd_pub)  [2ª pasada, ventana compuerta→rename]
   ──OK──► cerrar acreditado: escritores→memmaps→lectores→fd_log→fd_ai/fd_an→fd_run→fd_padre
           EXIT_OK (sólo si P-08 completa)

 ABORTO (D1 cerrado, P-02):
   fstat(fd_run) == I_run ? ──NO──► abort_registrado=False; sin escritura en NINGÚN árbol; rc≠0
        │ sí
   os.open("ABORT_6G1.json", O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, dir_fd=fd_run)
   inventario desciende desde fd_run (sin rutas); sin eliminación (C-R1); analysis.json intacto (E-R2)
   traslado opcional: renameat2(fd_padre, nombre_prov, fd_padre, nombre_aborted, NOREPLACE)
   cerrar acreditado (incluye anclas) → rc ∈ {2,130}
```

Regla del diagrama: **después de la creación, ninguna operación de salida del motor resuelve la ruta nominal**; todas las operaciones se ejecutan relativas a `fd_run`/`fd_padre` o sobre descriptores ya abiertos.

## §8 [ENTREGABLE 4] Diseño de publicación y aborto (resumen operativo)

**Publicación (`publicar_dir_6g1_v2`, P-05+P-06+P-08):**
1. Compuerta de conjunto sobre `fd_run` (tipos, symlinks NO, entradas inesperadas NO, obligatorios presentes y no vacíos, identidad continua vs registro, SHA G1 por descriptor).
2. `renameat2` relativo a `fd_padre` con `RENAME_NOREPLACE` (colisión → sufijo `_r%03d`, cada intento relativo y re-verificado; fail-closed si renameat2 indisponible).
3. Verificación de identidad post-rename: `fstat(fd_pub) == I_run`.
4. Segunda pasada de compuerta sobre `fd_pub`.
5. Éxito total → cierre acreditado de anclas → `EXIT_OK`. Cualquier fallo en 1–4 → aborto (abajo); si el fallo ocurrió tras el rename, `ABORT_6G1.json` se escribe DENTRO del publicado vía `fd_pub` y rc≠0.

**Aborto (`abortar_corrida_6g1_v2`, P-02+P-09):**
1. Orden vigente conservado: cierre determinista (escritores→memmaps→lectores) → cierre de log → registro del aborto.
2. Anclaje: `fstat(fd_run)` vs `I_run` **del descriptor** (sin ruta). Coincide → ABORT exclusivo/no-follow vía `dir_fd=fd_run` + inventario por descriptor (sin eliminación, C-R1; analysis.json intacto, E-R2).
3. Descriptor muerto/identidad distinta → `abort_registrado=False`, `directorio_acreditado=False`, sin escritura en ningún árbol; la corrida **nunca** termina en EXIT_OK; el resumen en consola conserva la evidencia.
4. Traslado a `_aborted*` sólo por `renameat2` relativo a `fd_padre` con verificación post-rename.
5. Campos nuevos del schema (PROPUESTO `abort-6g1/4`): `abort_registrado`, `anclaje` (`descriptor_retenido|descriptor_no_valido`), `identidad_dir`, `hashes_g1` (alcance delimitado), `fd_vivo`.

## §9 [ENTREGABLE 5] Diseño de pruebas de regresión específicas D1 y C (PROPUESTO — NO EJECUTADO en esta fase)

Arnés nuevo y aislado `scripts/arnes_regresion_d1_c_6g1.py` (fixtures sintéticos idénticos a la línea base: ruido PRNG semillas 20261122/19480720, `--allow-misaligned`; árboles de trabajo en `/tmp`; hooks de inyección en memoria como en FLOW-4 b — el motor **con los cambios propuestos**, no el vigente). Cada caso con veredicto definido a priori:

| Caso | Estímulo | Veredicto esperado (post-integración) | Métricas |
|---|---|---|---|
| **REG-D1-a** | swap de misma uid durante el procesamiento (renombrar provisional real + recrear nombre) | la corrida **continúa sobre los inodos reales**; publica el árbol REAL o aborta con ABORT en el REAL; el árbol señuelo queda sin artefactos de motor | rc; ABORT presente SOLO en el árbol de identidad acreditada; identidad publicada == I_run; artefactos en señuelo = 0; EXIT_OK sólo si P-08 |
| **REG-D1-b** | hook que vacía y hace `rmdir` del provisional real en la ventana entre cierre de escritores y aborto (fd muerto) | `abort_registrado=False`, `anclaje=descriptor_no_valido`, sin ABORT en ningún árbol, **rc≠0**, sin publicación | rc≠0; flags del schema; EXIT_OK imposible |
| **REG-C-a** | hook en frontera de compuerta: `analysis.json` → symlink al impostor | `CONJUNTO_PUBLICABLE_NO_VALIDO` → aborto por descriptor; **sin EXIT_OK**; sin publicación; impostor intacto | rc∈{2}; ABORT en árbol REAL; symlink publicado = False |
| **REG-C-b** | hook entre compuerta y `renameat2`: sustituir archivo dentro del provisional real | 2ª pasada sobre `fd_pub` lo detecta → ABORT dentro del publicado vía `fd_pub` + rc≠0 | rc≠0; ABORT en publicado; EXIT_OK imposible |
| **REG-C-c** | archivo inesperado adicional en el provisional antes de la compuerta | compuerta falla (entrada inesperada) → aborto, sin EXIT_OK | rc≠0; lista `inesperados` en evidencia |
| **REG-D1-c** | ruta del provisional convertida en symlink (ELOOP) antes del aborto | el aborto **por descriptor** no depende de la ruta: ABORT presente en el árbol real | ABERT en árbol acreditado; sin seguir el symlink |

Clasificación: todos los casos son **PROPUESTO** (diseño); su ejecución requiere nueva autorización. Los 6 casos NO sustituyen la línea base adjudicada (no se re-ejecuta).

## §10 [ENTREGABLE 6] Registro de riesgos y limitaciones (extensión PROPUESTA del `REGISTRO_RIESGOS_6G1.md`; IDs nuevos desde R-23, sin tocar el registro vigente)

| ID propuesto | Estado | Riesgo / limitación | Plan |
|---|---|---|---|
| R-23 | PROPUESTO | Descriptor del provisional muerto (atacante mismo-uid vacía el dir y lo elimina entre cierre y aborto): ABORT no puede escribirse en disco | fail-closed `abort_registrado=False` + rc≠0; evidencia en consola; sin EXIT_OK |
| R-24 | PROPUESTO | Ventana compuerta→rename y post-rename: sustituciones misma-uid en ese intervalo | 2ª pasada de compuerta sobre `fd_pub` (P-06); residual post-rename = limitación post-return documentada |
| R-25 | PROPUESTO | Escrituras WAV por `fileobj` (libsndfile): factibilidad de cabeceras/reposicionamiento sin validar | P-03 mantiene ruta con pre-creación O_EXCL + verificación; fileobj sólo en LECTURAS (P-04c); validar en fase de implementación (extensión de R-18) |
| R-26 | PROPUESTO | Micro-ventana TOCTOU entre pre-creación O_EXCL y apertura por biblioteca (ACOTADA, no eliminable) | re-verificación de identidad post-apertura; sustitución posterior mientras libsndfile escribe cae en el inodo real (escritor retiene fd) y se detecta en compuerta |
| R-27 | PROPUESTO | Fallback de ABORT en el padre validado (si se habilitara) podría ser eliminado por mismo-uid | por defecto **DESACTIVADO** (sólo fail-closed); decisión pendiente de Cris |
| R-28 | PROPUESTO | Limpieza `masks/` post-publicación por ruta (`shutil.rmtree`, H L1992) | ventana post-publicación; impacto cosmético/DoS, no de integridad (artefactos ya verificados); migración opcional a unlinkat por descriptor |
| R-11, R-12, R-15, R-18 | vigentes | sin cambios; R-15 se re-evaluará con el coste de los openat adicionales (P-03/P-05) | fuera de esta fase |

**Limitaciones del modelo de amenazas (declaración expresa):** el modelo cubre un atacante **same-uid con control de rutas** durante la corrida. No cubre: root; modificaciones post-return sobre artefactos publicados; DoS (disco, renombrados masivos, fd exhaustion); kernels sin `renameat2` con dirfd (fail-closed); SIGTERM/SIGKILL (R-11). El hash G1 cubre **sólo** `analysis.json` + `mix_sintetico SDV.wav` (sin ampliación): para el resto de obligatorios la protección es de **identidad/obligatoriedad**, no de contenido («LECTURA ANCLADA», nunca «contenido íntegro» — T7).

## §11 Distinción epistémica

**DEMOSTRADO (evidencia publicada en `292274b`):** FLOW-1/2/3 PASS; D1 (aborto ciego ante sustitución: anclaje por re-apertura de ruta falla con identidad distinta); frontera temporal de FLOW-4 (swap post-publicación → EXIT_OK limpio); C (EXIT_OK con analysis.json symlink publicado; conjunto mixto); el mapa vigente de §2 (inspección estática).

**PROPUESTO (este plan, pendiente de adjudicación):** P-01..P-09; schema `abort-6g1/4`; compuerta de conjunto; publicación por ancla con doble pasada; registro propio por identidad; invariante EXIT_OK; arnés de regresión y sus 6 casos; riesgos R-23..R-28.

**DESCONOCIDO:** transferencia a EVO/MQR; factibilidad fileobj-escritura (R-25/R-18); coste de rendimiento de la compuerta y los openat (R-15); disponibilidad de `renameat2` con dirfd en entornos objetivo (fail-closed si ausente); comportamiento ante señales no-Ctrl-C (R-11); todo comportamiento de atacantes fuera de las ventanas ensayadas/diseñadas.

## §12 [ENTREGABLE 7] Manifiesto y SHA-256

`MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` + `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` (generados al cierre; publicados en el mismo commit hijo de `292274b`).

## §13 Restricciones y parada

1. CERO modificaciones de producción (motores, `lectura_segura_6g1.py`, DSP, fórmulas, parámetros); cero ejecución del motor; cero audio real; cero Android/Termux; cero FLOW-5..8; cero EVO/MQR; cero merge/cherry-pick/main; PR #2 intacto.
2. Este commit contiene **sólo** documentación de diseño (archivos añadidos; nada de producción).
3. **No se implementa nada. Parada obligatoria** a la espera de la adjudicación de Cris.

— Fin del plan.
