# AUDITORÍA ESTÁTICA DE CORRESPONDENCIA — MOTOR HARDENED ↔ PLAN v2.3 (6G.1) — v1

- **Destinatario:** Cris (ChatGPT), responsable técnica y adjudicadora. **Ejecutor de inspección:** Arena.
- **Naturaleza:** PREINTEGRACIÓN — **INSPECCIÓN ESTÁTICA EXCLUSIVAMENTE**. Implementación **NO autorizada** y NO realizada. Este informe NO constituye integración: todo lo relativo a P-01..P-09 se etiqueta **PROPOSED**.
- **Etiquetas de cada afirmación:** **DOCUMENTED_FACT** = comprobable en el código inspeccionado hoy (con archivo y línea); **PROPOSED** = previsto en el plan v2.3, todavía no implementado; **UNKNOWN** = no resuelto o no verificable estáticamente.
- **Advertencia metodológica [DOCUMENTED_FACT]:** ninguna función del motor queda «integrada» por la existencia de un auxiliar con nombre parecido. `crear_y_acreditar_dir_6g1`, `publicar_dir_6g1`, `registrar_propio_6g1` y el ciclo de aborto **existen y se usan** (LS L367/L803/L515/L900; importados en H L334-349), pero **NO satisfacen** P-01/P-06/P-07/P-02 en su forma vigente (brechas específicas en §3 y §8).

---

## 1. Identidades Git y archivos inspeccionados

- **Padre directo obligatorio verificado ANTES de trabajar:** `ef90a45ceeeaa02be0c1d1a9f647a9490219e0cf` — local = origin = `gh api` = `ef90a45…` CONFORME; árbol limpio; sin cambios concurrentes. Rama `arena/f1c5739f-sdv-sdi-sgm`, repo `arielwilliam1986-source/SDV-SDI_SGM`.
- **Archivos inspeccionados (sólo lectura; SHA256 al momento de la inspección):**

| Archivo | Líneas | SHA256 |
|---|---|---|
| `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (v2.3) | 374 | `39632eae6246a6103f7cc7d71b6c934ceb1cdc41cca54ff0e060ac41863f7af4` |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | 2312 | `a4c157e7607f52a229cb35506ca9c5a57b86d30a6da179fec59ad7df445c416a` |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py` | 1422 | `b6f7d7eb2646c37fac0a912b777a83369d9e31d8e50d756f36db213a93690caf` |

- **Método [DOCUMENTED_FACT]:** lectura con `grep`/`awk` línea a línea sobre los archivos; cero ejecución de motores; cero importación de módulos de producción; cero arneses, pruebas o fixtures; cero audio. Las líneas citadas corresponden a los SHA256 de arriba (los números de línea citados por el plan §2/§6 difieren en ±3 en tres puntos — ver nota de desvío en §2).
- Abreviaturas: **H** = motor Hardened; **LS** = `lectura_segura_6g1.py`.

## 2. Mapa de funciones actuales con archivo y líneas

### 2.1 Motor Hardened (H) — funciones con relevancia 6G.1

| Líneas | Función/clase | Rol (DOCUMENTED_FACT) | Relevancia |
|---|---|---|---|
| L159-162 | exit codes | `EXIT_OK=0, EXIT_VALIDATION=1, EXIT_PROCESSING=2, EXIT_ABORTED=130` | MEDIA |
| L173-209 | `Tee` | log duplicado a consola+archivo; **abre por ruta** `open(path,"w")` L176; cierre verificable con `error_cierre_6g1` L177/L193-209 | ALTA (P-03/P-04d) |
| L215-220 / L222-244 | `init_tee` / `close_tee` | redirige `sys.stdout/stderr` L219-220; `close_tee()` devuelve `(ok, error)` y conserva el fallo L230-244 | ALTA |
| L303-322 | `FileInfo` | metadatos de probe | BAJA |
| L355-422 | `probe_file` | validación de ENTRADA **anclada a descriptor**: `os.open(O_RDONLY\|O_NONBLOCK)` único L372, `fstat` st0 L378, regular fail-closed L379-382, metadatos y `_verify_audio_6g` vía `/proc/self/fd/N` L386-389, SHA por `_sha_fd_estable_6g1(fd)` L404, estabilidad fstat st1 L411-418, `os.close` L420 | ALTA (ya fd; P-04 no la cambia) |
| L424-457 | `validate_mix` / `validate_guide` | reglas de validación (DSP-adyacente) | BAJA |
| L483-511 | `load_manifest` | lee manifiesto **por ruta** L484 y resuelve rutas de guías L493 | MEDIA |
| L826-857 | `FramePlan` / `read_span` | lectura por bloques desde un `sf.SoundFile` ya abierto | MEDIA |
| L867-936 | `OlaStream` | streaming OLA; recibe `writer: sf.SoundFile` L868/871 y escribe vía su API | MEDIA (P-03 no la cambia) |
| L1374-1424 | `CandidateRunner` | `__init__` crea escritores WAV **por ruta**: `sf.SoundFile(os.path.join(run_dir, sdv_name), mode="w")` L1396/L1398; registra por ruta L1397/L1399 (`estable=False`); runner parcial en fallo L1400-1402; `close()` verificable L1408-1424 (`cerrar_verificado_6g1` → `CierreNoAcreditado6G1`) | ALTA (P-03) |
| L1430-1454 | `create_run_dir` | provisional exclusivo: `_reiniciar_registro_6g1()` L1437, `os.makedirs(out_base)` L1438, `_crear_y_acreditar_dir_6g1(out_base, basename(partial))` L1448 — **el retorno (ruta, identidad) se DESCARTA**; devuelve sólo `(partial_dir, final_dir)` (rutas) L1449 | ALTA (P-01/P-07) |
| L1456-1459 | `_open_memmap` | `np.lib.format.open_memmap(path, mode="w+")` **por ruta** L1457 + registro por ruta L1458 | ALTA (P-03/R-29) |
| L1461-1492 | `post_wav_identity` | re-lectura de mix+SDV+SDI **por ruta** con `sf.SoundFile(...)` L1464 (mix llega como `ruta_lectura()` = magic-link, H L1889) | ALTA (P-04c) |
| L1494-2057 | `run_experiment` | orquestador (detalle en §5) | ALTA |
| L1603-1608 | creación provisional | fallo de creación/acreditación ⇒ `EXIT_PROCESSING` sin corrida | MEDIA |
| L1614 | `init_tee(...)` | engine_log **por ruta** `os.path.join(run_dir, "engine_log.txt")` | ALTA |
| L1615-1616 | `masks/` | `os.makedirs(masks_dir, exist_ok=True)` **por ruta** (siempre se crea) | ALTA (P-01 [R-C]) |
| L1625/1628-1639 | memmaps masks | `write_masks = opt.png or keep_masks`; 6+ memmaps **por ruta** vía `_open_memmap` | ALTA |
| L1649 | `track_base` | `basename(mix) sin extensión` — nombres WAV dinámicos | MEDIA |
| L1651-1681 | runners + `candidates/` | subdirectorios **por ruta** `os.makedirs(sub, exist_ok=True)` L1654/L1672 (dos niveles con `--write-all-candidates`); default escribe WAV raíz en `run_dir` L1671 | ALTA (P-09) |
| L1687 | `abrir_mix` | `hmix = _abrir_mix_6g1(mix_info.path, mix_info.sha256, identidad_esperada)` — contenedor anclado por descriptor | ALTA |
| L1695-1698 | handles de guías | `sf.SoundFile(p.vocal.path)` / `(p.instrumental.path)` **por ruta**, abiertos durante todo el DSP | MEDIA (brecha no asignada a P-xx — §8.9) |
| L1871-1875 | flush final + cierre runners | `runner.ola_*.flush()` + `runner.close()` — cierre ACREDITADO de writers vía `cerrar_verificado_6g1`, ANTES de post_wav/reports | ALTA (P-08 paso 2 positionalmente compatible) |
| L1877-1878 | cierre de guías | `for h in handles.values(): h.close()` (comentario: «el descriptor sigue abierto durante todo el DSP») | MEDIA |
| L1879-1882 | fin memmaps | `flush()` L1880 + soltar referencias (`arr=None`, `del mm`) — **sin cierre explícito del mmap ni del fd** (queda a recolección) | ALTA (P-08) |
| L1886-1890 | post_wav | llamada **por rutas** L1889 | ALTA (P-04c) |
| L1918/1919-1920 | reports/pngs | `write_reports(ctx, run_dir, opt)`; `write_pngs` si `opt.png and MATPLOTLIB_OK` | MEDIA |
| L1927-1930 | cierre log acreditado | `close_tee()`; fallo ⇒ `CierreNoAcreditado6G1` (sin publicación) | ALTA (R-32) |
| L1937-1954 | guarda final (mix) | `hmix.verificar()` L1938 + `ruta_apunta_al_mismo_objeto()` L1939 + `hmix.close()` acreditado L1950 | ALTA |
| L1957-1971 | `input_integrity_6g.json` | escritura **por ruta** `open(...,"w")` L1957-58, registro L1961-62, **re-lectura por ruta** `open(...,"r")+json.load` L1963-65 | ALTA (P-03/P-04a) |
| L1972-1977 | compuerta integridad | fail-closed ⇒ `_FalloCorrida_6g1("MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO")` | ALTA |
| L1984-1990 | publicación | `run_dir_final = _publicar_dir_6g1(run_dir, run_dir_final)` **por rutas**; fallo ⇒ aborto sin traslado | ALTA (P-06) |
| L1994-2000 | limpieza masks/ | **por ruta**: `os.path.exists` L1995 + `shutil.rmtree` L1997; fallo ⇒ **WARN** L2000 | ALTA (5bis/R-28) |
| L2001-2002 | EXIT_OK | `return EXIT_OK, run_dir_final` tras publicación+limpieza | ALTA (P-08 paso 8) |
| L2004-2057 | handlers aborto | 3 handlers (`KeyboardInterrupt` L2004, `_FalloCorrida_6g1` L2023, `Exception` L2040) → `_preparar_aborto_6g1(run_dir, log, close_tee, runners/memmaps/lectores de locals())` → `_abortar_corrida_6g1(run_dir, run_dir_final+"_aborted", ...)` — **todo por rutas** | ALTA (P-02) |
| L2068-2135 | `write_reports` | hashes forenses **por ruta** (`get_sha256` L2075-2080, `engine_sha` L2082); `analysis.json` **por ruta** `open(...,"w")` L2130 + registro L2132; `analysis.txt` L2134-2135 | ALTA (P-03) |
| L2137-2181 | `write_analysis_txt` | compila texto y **escribe por ruta** `open(path,"w")` L2180 | ALTA (P-04e) |
| L2183-2210 | `write_pngs` | `png/` **por ruta** L2184-2185; lee npy por ruta L2191; `fig.savefig(os.path.join(png_dir,...))` L2204 (exactamente 2 PNG) | MEDIA (R-12 OPC) |
| L2212-2312 | parser + `main` | `REQUIRED_MODES` L140 (4 modos); `run_experiment` L2296; exit L2304-2312 | BAJA |
| L332-349 | imports LS | 15 símbolos de `lectura_segura_6g1` (MixCambiado, abrir_mix, abortar_6g1, registrar/reiniciar, crear_y_acreditar, publicar_dir, FalloCorrida, abortar_corrida, cerrar_recursos, resumen_aborto, preparar_aborto, cerrar_verificado, runner_parcial, CierreNoAcreditado, sha_fd_estable) | ALTA |
| L351-353 | imports 6f | `atribucion_6f` — **fuera del alcance 6G.1** | FUERA |
| resto | DSP (STFT/máscaras/acumuladores L543-1360, L938-1360) | cálculo; toca arrays en memoria y los writers/memmaps ya listados | FUERA (intocable) |

**Nota de desvío de líneas [DOCUMENTED_FACT]:** el plan v2.3 §2/§6 cita H L1399/1401 (writers; observado hoy **L1396/L1398**), H L1988-1997 (limpieza masks; observado **L1994-2000**) y H L1652/1671 (candidates; observado **L1653-1654/L1671-1672**). Este informe usa las líneas OBSERVADAS en `ef90a45`; la deriva es de ±3 y no altera ninguna conclusión.

### 2.2 Protocolo auxiliar (LS) — funciones con relevancia 6G.1

| Líneas | Función/clase | Rol (DOCUMENTED_FACT) | Relevancia |
|---|---|---|---|
| L69/L73 | `MixCambiado` / `VerificacionFallida6G1` | excepciones | BAJA |
| L79-81 | `_identity` | identidad (dev,ino,size,mtime,mode) | MEDIA |
| L84-116 | `_sha_fd_estable` / `sha_fd_estable_6g1` | SHA-256 **por descriptor** con estabilidad fstat antes/después (dup+fdopen con seek(0) L94-96) | ALTA (P-05 ya tiene base) |
| L119-124 | `_sha_archivo` | SHA **por ruta** (usado en registro estable L532 y propiedad L565) | MEDIA (P-07 v2 lo sustituiría) |
| L127-288 | `MixHandle` | fd propio `O_RDONLY\|O_NONBLOCK` L142 + identidad exigida L152-158 + SHA estable L167 + lector `sf.SoundFile('/proc/self/fd/N')` L174-177; cierre verificable L199-245; `verificar()` re-lee por fd L248-271; `ruta_lectura()`=magic L273-277; `ruta_apunta_al_mismo_objeto()` compara la RUTA nominal L279-288 | ALTA |
| L305/L311 | `_PROPIOS_6G1` / `_DIR_6G1` | registros de propiedad y anclaje **claveados por ruta absoluta** | ALTA (P-01/P-07) |
| L314-328 | `acreditar_dir_6g1` | acreditación **por ruta** (lstat) — uso en arneses | MEDIA |
| L331-364 | `_anclar_dir_aborto_6g1` | re-APERTURA **por ruta** con `O_DIRECTORY\|O_NOFOLLOW` L348 + fstat contra registro; devuelve `(fd, motivo)` fail-closed | ALTA (P-02 la sustituye) |
| L367-413 | `crear_y_acreditar_dir_6g1` | padre seguro L388 + euid/permisos L394-399 + `mkdir(dir_fd)` L400 + apertura relativa L401-402 + fstat L404; **CIERRA fd_dir (L408) y fd_padre (L413)**; devuelve `(ruta, (dev,ino))` — los fds **NO se retienen** | ALTA (P-01 exige la variante) |
| L416-468 | `_sha_via_descriptor_6g1` | SHA por `openat(O_NOFOLLOW\|O_NONBLOCK, dir_fd)` + doble fstat — mecanismo G1 ya existente para el aborto | ALTA (P-05) |
| L471-505 | `_clasificar_entrada_6g1` | propiedad por identidad+ sello, sólo para registrar | MEDIA |
| L508-567 | registro propio | `registrar_propio_6g1(path, estable)` **por ruta** (os.stat L527; sha por ruta L532); `propiedad_de_6g1` por ruta+identidad L537-567 | ALTA (P-07 v2) |
| L576-767 | `abortar_6g1` | aborto sin eliminación (C-R1); anclaje fail-closed L626-644; inventario descendiendo por descriptor L652+; `ABORT_6G1.json` `O_CREAT\|O_EXCL\|O_NOFOLLOW, dir_fd` (docstring L596-598); `analysis.json` intacto (E-R2) | ALTA (P-02) |
| L769-800 | `_renameat2_noreplace` | ctypes glibc/syscall; **siempre `_AT_FDCWD`** (sin dir_fd) L782-783/L789-790; EEXIST L797-798; fail-closed si indisponible L792-794 | ALTA (P-06) |
| L803-822 | `publicar_dir_6g1` | **por rutas** L811-812; sufijos `_r%03d` L815; **sin acreditación post-rename por fd** (devuelve sólo la ruta L818) | ALTA (P-06) |
| L829-863 | `FalloCorrida6G1` / `cerrar_recursos_6g1` | cierre silencioso recursivo para aborto | MEDIA |
| L866-897 | `_registro_aborto_verificado_6g1` | relectura de `ABORT_6G1.json` **anclada al fd del directorio** L872-879 + verificación de schema/motivo L893-896 | ALTA |
| L900-1024 | `abortar_corrida_6g1` | protocolo único: barrido de escritura abierta L939, registro L952, re-anclaje **por ruta** L971, verificación L978, bloqueo de traslado si cierre incompleto L943-950, fstat fd_dir vs lstat(origen) L994-1005, traslado vía `publicar_dir_6g1` L1007, verificación post-traslado por lstat L1016-1021 | ALTA (P-02) |
| L1058-1127 | barridos procfs | `descriptores_bajo_dir_6g1` (listdir `/proc/self/fd` L1069 + readlink L1075 + flags fdinfo L1082-1086), `mapeos_bajo_dir_6g1` (`/proc/self/maps`), `escritura_abierta_bajo_dir_6g1` L1115 | ALTA (P-05 condición; R-15/R-29) |
| L1130-1226 | cierre acreditado | `cerrar_verificado_6g1` L1176-1201 (estado físico + fallo persistente), `runner_parcial_6g1` L1209 | ALTA (P-08 paso 2) |
| L1228-1336 | `cerrar_recursos_corrida_6g1` | cierre ordenado runners→memmaps→lectores con pasos registrados | ALTA (P-08/P-09) |
| L1338-1422 | `preparar_aborto_6g1` | cierre obligatorio pre-aborto; `completo` exige (a) recursos cerrados, (b) log cerrado verificado en /proc, (c) cero escritura/mapeos bajo el provisional | ALTA (P-02/P-09) |

## 3. Matriz de correspondencia P-01 a P-09

Todas las celdas «Adaptación» son **PROPOSED** (plan v2.3 §5). «Estado actual» es **DOCUMENTED_FACT**. Nada está implementado.

| P-xx | Exigencia esencial (plan) | Código actual implicado | Brecha / adaptación necesaria |
|---|---|---|---|
| **P-01** (L88) | Ancla retenida desde la creación + cadena de directorios acreditada; `crear_y_acreditar_dir_6g1_v2` **sin cerrar** `fd_dir`/`fd_padre`, devuelve `(ruta,(dev,ino),fd_dir,fd_padre)`; registro por identidad/token; aperturas componente a componente; prohibido abrir rutas multi-componente | H L1448 descarta el retorno; LS L408/L413 cierran ambos fds; LS L410/L530 registros claveados por ruta; H L1616/L1654/L1672 `makedirs` por ruta | Variante `_v2` que retenga fds; motor conserva `fd_run`/`fd_padre` hasta paso 7; `masks/` con `mkdir(dir_fd=fd_run)` + subancla `fd_masks`; sustituir `os.makedirs`/`os.path.join` para abrir |
| **P-02** (L89) | Aborto por descriptor retenido; anclaje = `fstat(fd_dir)` contra identidad del descriptor; descriptor muerto ⇒ `directorio_acreditado=False`, `abort_registrado=False`, sin escritura, rc≠0; `_anclar_dir_aborto_6g1` queda para arneses | H L2013-2055 pasa `run_dir` (ruta); LS L626/L971 re-abren **por ruta**; LS L348 apertura por ruta; sin propagación de fd muerto como estado explícito | `abortar_corrida_6g1_v2(..., fd_dir, fd_padre)`; handlers H pasan anclas; inventario L652+ ya desciende por descriptor (reutilizable); añadir rama fd-muerto |
| **P-03** (L90) | fd-passthrough en TODA salida: `openat(O_EXCL\|O_NOFOLLOW, dir_fd)` → `fstat` → **el mismo fd a la biblioteca** → cierre acreditado. WAV: `sf.SoundFile(fd, mode="w", closefd=False)`; Tee/JSON/TXT: `os.fdopen`; memmaps: magic-link sobre fd retenido o cabecera manual (R-29); PNG fuera del obligatorio (R-12) | H L1396/L1398 writers por ruta; H L1457 `open_memmap(path)`; H L176/L1614 Tee por ruta; H L2130/L2180 JSON/TXT por ruta | Cambiar `CandidateRunner.__init__`, `_open_memmap`, `Tee.__init__`/`init_tee`, `write_reports`/`write_analysis_txt` a creación openat + entrega del fd; verificación por `fstat(fd)` antes/después (la verificación posterior por ruta DEJA de invocarse como prueba) |
| **P-04** (L91) | Lecturas post-escritura por descriptor: (a) pread `input_integrity`; (b) SHA G1 por `_sha_via_descriptor_6g1`; (c) `post_wav_identity` con `openat(dir_fd=fd_run)`+`sf.SoundFile(fd, closefd=False)` (Mix sin cambios); (d) engine_log con fdopen preservando contrato R-17; (e) analysis.txt desde memoria | H L1963-65 re-lectura por ruta; H L1889/L1464 post_wav por rutas (mix ya por magic-link); H L2134/L2180 TXT por archivo; H L2075-2080 hashes forenses por ruta | (a) pread sobre fd propio; (c) re-firmar `post_wav_identity` para recibir fds/dirfd; (d) `Tee` acepta file object fdopen; (e) compilar TXT sin re-lectura; los hashes forenses internos de `write_reports` quedan como trazabilidad (no son compuerta) |
| **P-05** (L92-94) | Compuerta de conjunto (gate-1 y gate-2) sólo lectura: `listdir(fd_dir)`+`lstat(dir_fd)`; lista de aceptación determinista §8ter; rechazo symlinks/inesperados; continuidad de identidad vs registro (P-07); condición «cero descriptores de escritura» vía `escritura_abierta_bajo_dir_6g1`; hash G1 por descriptor (reapertura `O_NOFOLLOW` dirfd + fstat vs registro + lectura sólo de `fd_h` + close inmediato; SIN comparación entre compuertas) | NO EXISTE compuerta de conjunto; la guarda vigente es sólo de integridad del MIX (H L1937-1977); el mecanismo de hash por descriptor existe para el aborto (LS L416-468); `escritura_abierta_bajo_dir_6g1` existe (LS L1115) | Función NUEVA `verificar_conjunto_publicable_6g1` + derivación L_acept de §8ter + integración en pasos 4 y 6 de P-08; fases gate-1 (`fd_run`+`fd_masks`+subanclas) y gate-2 (`fd_pub`+subanclas) |
| **P-06** (L95) | `publicar_dir_6g1_v2(fd_padre, nombre_prov, nombre_final)` con `renameat2(src_dir_fd=fd_padre, dst_dir_fd=fd_padre, RENAME_NOREPLACE)`; afirmación honesta R-D (el origen es nombre relativo); post-rename: `fd_pub=openat(nombre_final, dir_fd=fd_padre)` + `fstat(fd_pub)==I_run` fail-closed; 2ª pasada de compuerta sobre `fd_pub`; ABORT vía `fd_pub`/`fd_run` si difieren | H L1984 por rutas; LS L811-812 abspath; LS L782-783/L789-790 `_AT_FDCWD` (sin dir_fd); **sin `fd_pub` ni fstat post-rename** | Variante `_v2` con dirfds + acreditación `fstat(fd_pub)==I_run` + conexión con compuerta-2 y 5bis |
| **P-07** (L96) | Registro propio claveado por identidad: `registrar_propio_6g1_v2(fd_dir, nombre, estable)` → `(identidad_dir, nombre) → (dev,ino,estable)`; consulta por descriptor | LS L305/L515-534/L537-567 claveados por ruta absoluta; sha de sello por ruta L532/L565 | Variante `_v2` por `(identidad_dir, nombre)`; `_clasificar_entrada_6g1` (LS L471) ya compara por identidad — base reutilizable |
| **P-08** (L97) | Secuencia única de cierre/compuertas: (1) fin de escrituras; (2) cerrar y acreditar writers/memmaps/lectores/Tee/fds; (3) `fd_run`,`fd_padre`,`fd_masks`, subanclas PERMANECEN; (4) gate-1; (5) publicar; (5bis) eliminar masks/ por descriptores (`unlinkat` vía `fd_masks` + `rmdir(dir_fd=fd_pub)`) sólo si `fstat(fd_pub)==I_run`, luego cerrar `fd_masks`; (6) gate-2; (7) cerrar subanclas→`fd_candidates`→`fd_pub`→`fd_run`→`fd_padre`; (8) EXIT_OK. Prohibida toda mutación tras compuerta final (excepción ABORT con rc≠0); veredictos fuera del engine_log (R-32) | Secuencia vigente distinta: cierre acreditado de writers L1871-1875 → post_wav L1889 → reports L1918 → pngs L1920 → close_tee L1927 → guarda mix L1937-1954 → input_integrity L1957-1965 → publicación L1984 → rmtree masks L1994-2000 (WARN) → EXIT_OK L2002; memmaps sin cierre explícito L1879-1882 | Reordenar el final de `run_experiment`: insertar gate-1 tras el cierre (paso 4), convertir rmtree en 5bis por descriptores, añadir gate-2 y EXIT_OK sólo tras paso 8; añadir cierre explícito del mmap y retención de fd_mm (§5) |
| **P-09** (L98) | `candidates/` componente a componente con subanclas `fd_candidates`/`fd_cand_<grupo>` retenidas en ambas compuertas; orden de cierre (writers→memmaps (fd_mm retenido mientras vive el mapeo)→lectores→Tee→fds propios); subanclas se cierran en 5bis (`fd_masks`) y paso 7 (candidates); re-apertura de emergencia componente único; `preparar_aborto` incorpora anclas vivas | H L1653-1654/L1671-1672 `makedirs` por ruta (dos niveles DOCUMENTED_FACT); sin `fd_candidates`/`fd_cand_<grupo>`; memmaps sin fd retenido (el objeto `open_memmap` abre SUS propios fds por la ruta) | Creación openat + subanclas; los WAV de grupo con P-03 sobre `fd_cand_<grupo>`; extender `preparar_aborto_6g1` (LS L1338) con anclas/subanclas |

**Compuertas P-05 — cableado exacto (todo PROPOSED, plan L92-94, L97, §8ter L273-303):** gate-1 = compuerta sobre el provisional (`fd_run`+`fd_masks`+subanclas) tras el paso 2, con lista gate-1 (masks/ OB; npy OB-C según `--png ∨ --keep-masks`; png/ OB-C según `--png ∧ MATPLOTLIB_OK`; 6 WAV/JSON/logs OB) + hash G1 de `analysis.json` y `<track_base> SDV.wav` por `fd_h` efímero; publicación (P-06) + acreditación `fstat(fd_pub)==I_run`; 5bis = eliminación de `masks/` del publicado por descriptores y cierre de `fd_masks` (fallo ⇒ masks/ presente en gate-2 ⇒ RECHAZO — cambio semántico respecto del WARN vigente H L2000, ya registrado en §8ter nota 1 como decisión PROPUESTA); gate-2 = segunda compuerta sobre `fd_pub`+subanclas con lista gate-2 (masks/ PROH) + segundo hash G1 independiente (**sin comparación entre compuertas** — huellas registradas; veredictos a salida directa porque engine_log está cerrado desde el paso 2, R-32); aceptación ⇒ paso 7 (cierres) ⇒ EXIT_OK; rechazo en cualquier punto ⇒ `_FalloCorrida_6g1("CONJUNTO_PUBLICABLE_NO_VALIDO")` ⇒ aborto (P-02) ⇒ sin EXIT_OK. Alcance G1 sin ampliación: sólo `analysis.json` + `<track_base> SDV.wav`.

## 4. Dependencias entre funciones y recursos

[DOCUMENTED_FACT] Grafo mínimo (creador → consumidor → destino):

1. `create_run_dir` (H L1430) → `crear_y_acreditar_dir_6g1` (LS L367) → `_DIR_6G1` (LS L410) → usado por `_anclar_dir_aborto_6g1` (LS L343-346) en todo el ciclo de aborto. El fd del provisional **muere** en LS L408.
2. `run_experiment` (H L1494) → `init_tee` (H L1614) → `Tee` (H L176) → `engine_log.txt`; `close_tee` (H L1927, L2021, L2038, L2056) también en `preparar_aborto_6g1` vía callback `cerrar_log` (LS L1388).
3. `CandidateRunner.__init__` (H L1396-1399) → `sf.SoundFile` (escritores) → `OlaStream` (H L1404-1405) → DSP escribe; `CandidateRunner.close` (H L1408) → `cerrar_verificado_6g1` (LS L1176).
4. `_open_memmap` (H L1456) → `np.lib.format.open_memmap` → memmap; `flush` en H L1880; registro por ruta (H L1458).
5. `abrir_mix` (H L1687) → `MixHandle` (LS L127) → fd propio + lector procfs; consumido por DSP (`read_span`), guarda final (H L1938-1939) y `post_wav_identity` (H L1889 vía `ruta_lectura()`).
6. handles de guías (H L1697-1698) → `read_span` durante DSP → cerrados H L1878.
7. `write_reports`/`write_analysis_txt` (H L1918, L2134) → `analysis.json`/`analysis.txt` por ruta; `input_integrity` (H L1957-1965) por ruta (escritura + relectura).
8. `_publicar_dir_6g1` (H L1984) → `publicar_dir_6g1` (LS L803) → `_renameat2_noreplace` (LS L769).
9. handlers (H L2004-2057) → `preparar_aborto_6g1` (LS L1338) → `cerrar_recursos_corrida_6g1` (LS L1228) + barridos procfs (LS L1115) → `abortar_corrida_6g1` (LS L900) → `abortar_6g1` (LS L576) + `publicar_dir_6g1` (LS L1007).
10. `registrar_propio_6g1` (H L1397/1399/1458/1961/2132/2135) → `_PROPIOS_6G1` (LS L530) → clasificación de propiedad del aborto (LS L481-505).

Bajo P-01..P-09 [PROPOSED]: las aristas 1-4 y 7-9 pasarían a transportar descriptores (`fd_padre`/`fd_run`/`fd_masks`/`fd_candidates`/`fd_cand_<grupo>`/`fd_pub`/fds de biblioteca), y las aristas 2/7 pasarían a entregar file objects sobre fds propios; la arista 6 (guías) no está asignada a ningún P-xx (§8.9).

## 5. Secuencia actual frente a secuencia propuesta

| # | Secuencia ACTUAL de éxito (DOCUMENTED_FACT, H) | Secuencia PROPUESTA (PROPOSED, P-08 L97) |
|---|---|---|
| 1 | `create_run_dir` L1604 (fds descartados); `init_tee` L1614; `makedirs masks/` L1616; memmaps L1628-1639; runners+candidates L1651-1681; `abrir_mix` L1687; handles de guías L1697 | P-01: anclas `fd_padre`→`fd_run`→`fd_masks`(+candidates) retenidas; P-03: writers/memmaps/log/JSON por fd; P-09: candidates componente a componente |
| 2 | DSP streaming (escrituras a writers/memmaps) | (sin cambios funcionales en DSP; los recursos de escritura siguen abiertos) |
| 3 | flush OLA + `runner.close()` (cierre acreditado writers) L1871-1875; cierre handles de guías L1877-1878; memmaps: `flush` + soltar refs L1879-1882 (sin cierre explícito del mmap ni del fd) | paso 1-2: fin de escrituras; cierre ACREDITADO de writers (sf_close), memmaps (flush+cierre mmap+fd_mm retenido), lectores, Tee, fds propios — los writers ya se cierran en posición equivalente; la diferencia es el cierre explícito del mmap y la retención del fd_mm |
| 4 | `metrics.finalize` L1884; `post_wav_identity` por rutas L1889 | paso 3: anclas permanecen; post_wav por descriptor (P-04c) |
| 5 | `write_reports` L1918; `write_pngs` L1919-1920 | (orden propuesto: reports/TXT desde memoria y PNG antes del paso 2 — decisión de ubicación PROPOSED; R-32 obliga a que los veredictos de compuerta no vayan al log) |
| 6 | `close_tee` acreditado L1927-1930 | paso 2 (Tee se cierra aquí en ambas secuencias — compatible) |
| 7 | guarda final del mix L1937-1954 | (se conserva; sin cambio funcional) |
| 8 | `input_integrity_6g.json` escrita+releída por ruta L1957-1965; guarda L1972-1977 | pread sobre fd propio (P-04a); + **paso 4: gate-1** (compuerta de conjunto + hash G1) — NO EXISTE hoy |
| 9 | publicación por rutas L1984 | paso 5: P-06 por anclas + `fstat(fd_pub)==I_run` |
| 10 | `rmtree masks/` por ruta L1994-2000 (fallo ⇒ WARN) | paso 5bis: eliminación por descriptores vía `fd_masks`+`rmdir(dir_fd=fd_pub)`; fallo ⇒ RECHAZO en gate-2 |
| 11 | — | paso 6: gate-2 sobre `fd_pub` + segundo hash G1 independiente |
| 12 | `return EXIT_OK, run_dir_final` L2002 | paso 7: cierre subanclas→`fd_candidates`→`fd_pub`→`fd_run`→`fd_padre`; paso 8: EXIT_OK |
| aborto | 3 handlers L2004-2057 por rutas | P-02: `_abortar_corrida_6g1_v2(fd_dir, fd_padre, ...)`; anclas vivas; fd muerto ⇒ sin escritura + rc≠0 |

## 6. Inventario de descriptores a crear, conservar y cerrar

| Descriptor | Hoy (DOCUMENTED_FACT) | Bajo P-01..P-09 (PROPOSED) |
|---|---|---|
| `fd_padre` | abierto y CERRADO dentro de `crear_y_acreditar_dir_6g1` (LS L388/L413); el motor nunca lo ve | creado por `_v2` y RETENIDO por el motor hasta el paso 7 (último cierre) |
| `fd_run` | abierto y CERRADO dentro de LS L401-408; identidad sólo en `_DIR_6G1[ruta]` | RETENIDO toda la corrida; usado por P-04/P-05/P-06/P-09; cerrado en paso 7 |
| `fd_masks` | no existe (masks/ por ruta H L1616) | subancla: `mkdir(dir_fd=fd_run)`+openat; usado por memmaps (componente único) y 5bis (`unlinkat`); cerrado tras 5bis |
| `fd_candidates` + `fd_cand_<grupo>` | no existen (makedirs por ruta H L1654/L1672) | subanclas por P-09 cuando `--write-all-candidates`; retenidas hasta paso 7 |
| writers WAV (×2 por runner) | `sf.SoundFile(ruta)`; libsndfile abre SU fd interno por ruta (H L1396/1398); cierre acreditado en ruta de éxito L1871-1875 y en aborto vía `cerrar_recursos_corrida_6g1` | fd propio `openat O_EXCL` entregado a `sf.SoundFile(fd, closefd=False)`; cierre acreditado en paso 2 |
| fds de memmaps (×6) | `open_memmap(ruta)` abre SUS file objects por ruta y los cierra; el motor no retiene fd (H L1457; flush+soltar refs L1879-1882) | fd propio retenido (`fd_mm`) mientras vive el mapeo; creación por magic-link sobre el fd o cabecera manual (R-29); cierre explícito paso 2 |
| engine_log (Tee) | `open(ruta,"w")` dentro de Tee (H L176); fdopen implícito de CPython sobre ese fd | fd pre-creado con P-03 + `os.fdopen` en Tee (contrato R-17 preservado); cierre paso 2 |
| `analysis.json`/`analysis.txt`/`input_integrity` | `open(ruta,"w"/"r")` transitorios (H L2130/L2180/L1957/L1963) | fds transitorios por `fdopen`/`pread` sobre fd propio; cierre inmediato |
| `fd_h` (hash G1) | — (hoy: hashes forenses por ruta H L2075-2080, NO son compuerta) | efímeros DENTRO de la compuerta: openat→fstat→leer→close por cada archivo G1 (ninguno sobrevive) |
| `fd_pub` | no existe (publicación por rutas; sin acreditación post-rename) | tras el rename (P-06): `openat(nombre_final, dir_fd=fd_padre)` + `fstat==I_run`; usado por 5bis/gate-2/ABORT-en-publicado; cerrado paso 7 |
| fd del aborto | `_anclar_dir_aborto_6g1` lo abre por ruta y lo cierra (LS L348/L626/L971/L1024) | sustituido por `fd_dir` retenido; fd muerto ⇒ sin escritura + rc≠0 |
| fd del mix (`hmix.fd`) | retenido todo el DSP; lector procfs encima (LS L142/L177); cierre acreditado (LS L238) | sin cambios (P-04c: «ya opera sobre fd retenido») |
| handles de guías | `sf.SoundFile(ruta)` internos de libsndfile (H L1697-1698) | NO cubierto por P-01..P-09 — decisión requerida (§8.9) |

## 7. Bibliotecas implicadas y mecanismo de entrega de descriptores

[DOCUMENTED_FACT — plan §8bis L256-271, fuentes de soundfile 0.13.1/numpy 1.26.4 inspeccionadas en fases anteriores; y DOCUMENTED_FACT empírico del arnés FEASIBILITY-1 (espacio AISLADO, no producción), efímero en /tmp, publicado en `a94f507`/`71d928b`/`ef90a45`]:

| Biblioteca / punto | Mecanismo vigente | Mecanismo propuesto | Soporte empírico (arnés aislado) |
|---|---|---|---|
| soundfile escritores WAV (H L1396/1398) | `sf_open(ruta)` — fd interno de libsndfile por ruta | `sf.SoundFile(fd, mode="w", closefd=False)` → `sf_open_fd` | **OBSERVADO**: escritura por fd exige `format='WAV'`; `closefd=False` conserva identidad (dev,ino) tras `sf.close()`; `closefd=True` CIERRA el fd propio (EBADF). Nota: subtype vigente del motor es `OUTPUT_SUBTYPE="FLOAT"` (H L150) — el recorte ±1.0 observado aplica a PCM_16, no al FLOAT vigente |
| soundfile lectores post_wav (H L1464) | `sf_open(ruta)` | `sf.SoundFile(fd, closefd=False)` | **OBSERVADO**: lectura por fd NO acepta `format` (auto-detección) |
| numpy open_memmap (H L1457) | por ruta | magic-link `/proc/self/fd/<fd_retenido>` (R-29) o cabecera manual + `np.memmap(fileobj, r+, offset)` | **OBSERVADO**: open_memmap vía magic-link con fd retenido conserva identidad y contenido; `np.memmap(fileobj)` exige O_RDWR y NO cierra el objeto (nullcontext); variante sin procfs viable (guardián, 0 consultas); escenario procfs-ausente NO reproducible (UNKNOWN) |
| Tee/io Python (H L176) | `open(ruta)` | `os.fdopen(fd)` — toma posesión (cierra al cerrar; R-17) | contrato R-17 ya documentado en LS; refactor del Tee PROPOSED, sin prueba |
| JSON/TXT (H L2130/L2180/L1957) | `open(ruta)` | `os.fdopen(fd)` escribir + `os.pread(fd)` relectura | mecanismo estándar; sin riesgos conocidos |
| matplotlib savefig (H L2204) | por ruta | fuera del conjunto obligatorio (R-12, OPC) | **UNKNOWN**: savefig por file object «aceptado por la API, no probado» (§8bis L267) |
| renameat2 (LS L769) | `_AT_FDCWD` por rutas | `renameat2(src_dir_fd=fd_padre, dst_dir_fd=fd_padre)` | **OBSERVADO** (arnés): RENAME_NOREPLACE atómico (EEXIST, destino intacto); sustitución del origen ⇒ se mueve el impostor, detección SOLO post-rename `fstat(fd_pub)` (R-31, observación — NO garantía de atomicidad por identidad); ENOENT con fd sobreviviente |
| procfs | usado por MixHandle/probes/barridos | magic-link para memmaps + condición «cero escritores» de la compuerta | dependencia R-29 declarada; barridos devuelven «no observable» si no hay procfs (LS L1069-1071) — en `preparar_aborto` eso fuerza `completo=False` (fail-closed, LS L1404-1411) |

## 8. Riesgos de incompatibilidad y puntos que todavía requieren decisión

1. **[DOCUMENTED_FACT] P-01 rompe el contrato vigente de `crear_y_acreditar_dir_6g1`:** hoy CIERRA ambos fds (LS L408/L413) y `create_run_dir` además descarta el retorno (H L1448). La variante `_v2` cambia la firma y la propiedad de los fds; todo llamador (motor y arneses que la usen) requiere adaptación. Decisión: nueva función vs modificación (plan dice «variante» — PROPOSED).
2. **[DOCUMENTED_FACT] Registros claveados por ruta:** `_DIR_6G1`/`_PROPIOS_6G1` (LS L410/L530) y `_anclar_dir_aborto_6g1` (LS L342-348) dependen de `os.path.abspath`; P-01/P-07 los sustituyen por identidad/token. Riesgo de incoherencia si conviven registro por ruta (aborto vigente) y por identidad (compuertas) durante una migración parcial — orden de implementación debe evitar estados mixtos (§9).
3. **[DOCUMENTED_FACT] Memmaps sin fd retenido ni cierre explícito:** el flush + `del mm` (H L1879-1882) deja el cierre del mmap y del fd a la recolección; P-08 exige flush+cierre del mmap y fd_mm retenido hasta entonces. La creación vía `open_memmap` hace que el objeto retenga SUS file objects — tras migrar a magic-link, el fd_mm propio y los fds internos del objeto memmap coexisten y el orden de cierre importa (P-09: «nunca cerrar un fd del que depende otro recurso vivo»).
4. **[PROPOSED→decisión] Cambio semántico de la limpieza de masks/:** hoy WARN (H L2000); con §8ter/P-08, fallo de 5bis ⇒ RECHAZO ⇒ sin EXIT_OK (§8ter nota 1 lo registra expresamente como decisión para adjudicación).
5. **[DOCUMENTED_FACT] El cierre acreditado de writers YA existe en la ruta de éxito** (H L1871-1875: `runner.close()` → `cerrar_verificado_6g1`), en posición anterior a `post_wav_identity` (L1889) y a los informes (L1918): la exigencia P-08 de writers cerrados ANTES de gate-1/hash G1 es positionalmente compatible con la secuencia vigente. Los puntos de reordenación reales son: (i) memmaps sin cierre explícito del mmap ni fd_mm retenido (L1879-1882); (ii) inserción de gate-1 entre el cierre y la publicación; (iii) 5bis por descriptores en lugar del rmtree; (iv) gate-2 y EXIT_OK condicionado. El hash G1 de `<track_base> SDV.wav` leería un WAV con cabecera ya finalizada por sf_close (L1875) — requisito satisfecho por la secuencia vigente.
6. **[DOCUMENTED_FACT→decisión] Veredictos de compuerta fuera del engine_log (R-32):** el log se cierra en el paso 2 (H L1927 ya lo hace antes de la guarda) — consistente; los veredictos deben ir a salida directa y a `ABORT_6G1.json` en caso de fallo. Decisión de formato de registro no especificada en el plan (UNKNOWN).
7. **[DOCUMENTED_FACT] Barridos procfs como condición de compuerta:** `escritura_abierta_bajo_dir_6g1` (LS L1115) depende de procfs; sin procfs devuelve «no observable» y `preparar_aborto` fuerza `completo=False`. Para P-05 la misma dependencia aplica (R-15 coste; R-29 disponibilidad). Decisión: aceptar fail-closed sin procfs (plan lo asume) o alternativa por fd propio del arnés (fuera de alcance).
8. **[DOCUMENTED_FACT] `_renameat2_noreplace` sin dirfd:** la variante vigente usa `_AT_FDCWD` (LS L782-789); P-06 exige dirfds. Firmas y tests cambian; el manejo EEXIST/sufijos `_r%03d` (LS L815) se conserva.
9. **[DOCUMENTED_FACT→decisión] Handles de guías re-abiertos por ruta (H L1697-1698):** los archivos de guía se validan por descriptor en `probe_file`, pero el DSP los re-abre por ruta SIN re-verificación de identidad. **Ningún P-01..P-09 cubre explícitamente esta apertura** (el plan P-04c sólo menciona el Mix). Registro como punto que requiere decisión de Cris (no se amplía el alcance por iniciativa propia): asignarlo a P-04 (openat + fstat vs identidad del probe) o dejarlo como riesgo documentado.
10. **[UNKNOWN] R-13:** el descenso de DOS niveles por descriptores (`fd_run→fd_candidates→fd_cand_<grupo>`) está definido (P-09) pero no validado empíricamente con el motor; el arnés FEASIBILITY-1 F1 validó el MECANISMO aislado (dos niveles, identidades, symlink), no la observación en el motor.
11. **[UNKNOWN] R-12 (matplotlib), R-15 (coste procfs/compuertas), comportamiento en entornos sin procfs real, Android/Termux, kernels sin renameat2** (la rama ENOSYS sólo se ejercitó por parche controlado en el arnés — `ef90a45`).
12. **[DOCUMENTED_FACT] Excepción de aborto tras compuerta final:** P-08 permite `ABORT_6G1.json` vía `fd_pub`/`fd_run` con rc≠0; hoy el handler de `_FalloCorrida` usa `run_dir_final+"_aborted"` por ruta (H L2033). La combinación «compuerta falló después del rename» (ABORT en publicado + ABORT en real si difieren) no existe en el código vigente.

## 9. Orden técnico recomendado para una futura implementación (todo PROPOSED)

Con dependencias justificadas (ninguna ejecución autorizada):

1. **P-01 + P-07 (fundación):** variante `crear_y_acreditar_dir_6g1_v2` (fds retenidos) + registro por `(identidad_dir, nombre)`. Todo lo demás consume anclas y registro por identidad. Verificación estática sugerida: ninguna apertura multi-componente en el código tocado.
2. **P-03 (entrega de fds a bibliotecas):** writers WAV (closefd=False), memmaps (magic-link sobre fd retenido; alternativa sin procfs mantenida como respaldo R-29), Tee por fdopen, JSON/TXT por fdopen. Punto crítico: cambio de `CandidateRunner.__init__` y `_open_memmap` sin tocar `OlaStream` (su API ya recibe el writer como objeto).
3. **P-04 (lecturas por descriptor):** pread `input_integrity`, `post_wav_identity` por openat+fd, `analysis.txt` desde memoria, Tee con file object. (Decisión pendiente §8.9 sobre guías.)
4. **P-09 (subanclas candidates + órdenes de cierre):** creación componente a componente, subanclas retenidas, `preparar_aborto` con anclas vivas.
5. **P-06 (publicación v2):** renameat2 con dirfds + `fd_pub` + `fstat(fd_pub)==I_run`.
6. **P-08 + P-05 (reordenación y compuertas, en un solo paso):** secuencia 1-8 con gate-1/5bis/gate-2 y hashes G1; incluye el cambio semántico de la limpieza de masks/ (WARN→RECHAZO) y la salida de veredictos fuera del log (R-32).
7. **P-02 (aborto por descriptor retenido):** handlers pasan `fd_dir`/`fd_padre`; rama fd-muerto; se hace AL FINAL porque consume anclas producidas por P-01 y reordenaciones de P-08/P-09.

Mapa de aceptación sugerido (PROPOSED, §6 del plan): FLOW-1 (éxito normal) tras pasos 1-6; FLOW-2 (excepción con recursos) y FLOW-3 (SIGINT) tras paso 7; FLOW-4 (sustituciones intermedia/final) tras compuertas.

## 10. Lista explícita de aspectos NO demostrados o desconocidos

- **[PROPOSED] TODO P-01..P-09:** ninguna parte está implementada ni integrada; las funciones vigentes con nombres afines NO satisfacen las exigencias (brechas por fila en §3). La validación FEASIBILITY-1 (commits `a94f507`/`71d928b`/`ef90a45`) probó mecanismos en espacio AISLADO, no en el motor; NO constituye autorización ni evidencia de integración.
- **[UNKNOWN] Comportamiento del motor real** tras cualquier cambio: cero ejecuciones (esta fase es estática).
- **[UNKNOWN] R-12:** `savefig` por file object; hoy PNG por ruta (H L2204), fuera del conjunto obligatorio.
- **[UNKNOWN] R-13:** descenso de dos niveles observado en el motor (sólo mecanismo validado en arnés).
- **[UNKNOWN] R-15:** coste de compuertas/barridos procfs en corridas reales.
- **[UNKNOWN] Entornos:** procfs realmente ausente (no reproducible ni en arnés), kernels sin renameat2 (sólo rama ENOSYS por parche), Android/Termux, euid distinto, seccomp (rama «sonda inconclusa» es code-path).
- **[UNKNOWN] Formato de registro de veredictos de compuerta** (salida directa + detalle de `CONJUNTO_PUBLICABLE_NO_VALIDO`): no especificado en el plan.
- **[UNKNOWN] Asignación de los handles de guías** (H L1697-1698) a un P-xx (§8.9) — requiere decisión.
- **[UNKNOWN] Interacción de señales (SIGTERM/SIGHUP) y handlers** con anclas retenidas: hoy sólo `KeyboardInterrupt` tiene handler propio (H L2004); el resto cae en `Exception`.
- **[UNKNOWN] Durabilidad:** fsync por artefacto es PROPUESTO opcional (P-08), no decidido.
- **[DOCUMENTED_FACT de alcance] Lo que SÍ está demostrado estáticamente:** las brechas de rutas nominales (§3/§5/§8), el mapa de funciones (§2), la matriz de correspondencia (§3), el inventario de descriptores (§6) y los mecanismos de biblioteca con soporte del plan §8bis más evidencia de arnés aislado citada.

## 11. Declaración expresa y parada

**Inspección estática exclusivamente.** No se modificó ningún archivo de producción ni de ningún otro tipo en esta fase salvo este informe; no se ejecutaron motores ni se importaron módulos de producción; no se ejecutaron pruebas, arneses ni fixtures; cero audio; cero Android/Termux; cero DSP/máscaras/fórmulas tocados; cero integración P-01..P-09; cero FLOW-5..8; cero EVO/MQR; cero `main`; sin merge ni cherry-pick; PR #2 intacto; plan v2.3, motores y `lectura_segura_6g1.py` intactos (verificables por `gh api` del commit: exactamente 1 archivo nuevo). Las líneas citadas corresponden a los SHA256 de §1 en el padre `ef90a45…`.

— Fin del informe. Parada obligatoria: publicado y detenido a la espera de la adjudicación de Cris. Esta autorización permite únicamente inspección estática y documentación; NO concede implementación, integración ni ejecución.
