# 6G.1 — AUDITORÍA ESTÁTICA DE INTEGRACIÓN (Hardened / EVO / MQR)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`. **Referencia de producción:** `9fedc5b223444e73955d2b899b6a434b0f5c670e` (los motores NO han cambiado desde ella).
- **Naturaleza:** fase EXCLUSIVAMENTE de lectura, análisis y diseño, autorizada por Cris (adjudicación 22-11-2026). **Cero modificaciones de producción**; los números de línea citados corresponden a los ficheros de producción vigentes, verificados en esta sesión con `grep`/`sed`/`awk` sobre los ficheros reales.
- **Fecha:** 22 de noviembre de 2026.
- **Adjudicación previa registrada:** C1–C4 DEMOSTRADO; C5/C6 PASS; D1 DEMOSTRADO; D2 PASS; E1 PASS (rectificación final aceptada); F1 PASS; G1 PASS (alcance delimitado a `analysis.json` y `mix SDV.wav`). La aceptación NO equivale a integración.

---

## 0. Identidades Git y comparación de archivos

| Elemento | Valor |
|---|---|
| Referencia de producción | `9fedc5b223444e73955d2b899b6a434b0f5c670e` |
| Cadena de la etapa | `09961a4` → `b720427` → `a4139af` → `c005d5c` |
| Commit de esta fase | hijo **directo** de `c005d5cb0e5b05757ba925092c9c19dc14724c0c` — **sólo documentos nuevos** (auditoría, matriz, RG-FLOW, riesgos, manifiesto, sumas) |
| Entorno de análisis | Python 3.11.2 (sólo lectura de código; sin ejecución de motores) |

**Comparación de archivos:** `git diff --name-status c005d5c..commit` → sólo `A` (nuevos documentos); motores, `lectura_segura_6g1.py`, DSP, fórmulas, fixtures y validadores byte a byte idénticos; `main` sin tocar.

## 1. Infraestructura compartida consumida por los tres motores (`lectura_segura_6g1.py`, sin modificar)

| Función | Líneas | Operación relevante para el anclaje |
|---|---|---|
| `crear_y_acreditar_dir_6g1(padre, nombre)` | L367–415 | Abre `fd_padre` con `O_DIRECTORY\|O_NOFOLLOW` (L368), valida padre (euid, sin W g/o) L372–382, `mkdir(0o700, dir_fd=fd_padre)` L383, abre el provisional relativo al padre validado (L401–402), `fstat` L403, registra identidad en `_DIR_6G1` (L412) y devuelve `(ruta, (dev,ino))` (L413). **`fd_dir` se cierra en L410 y `fd_padre` en L415 (finally): HOY NINGÚN DESCRIPTOR SE CONSERVA.** Punto exacto donde la v2 (diseño PDA-1/EA) devolvería `fd_padre`+`fd_run` |
| `_anclar_dir_aborto_6g1(run_dir)` | L331–365 | Anclaje de aborto POR RUTA + identidad vs `_DIR_6G1` (H1): `None` + motivo si ruta no acreditada / apertura segura falla / identidad distinta. Es el camino demostrado CIEGO en D1 ante sustitución de intermedios |
| `abortar_6g1` / `abortar_corrida_6g1` | L576–768 / L900–1026 | Registro `ABORT_6G1.json` (schema `abort-6g1/3`), verificado por `_registro_aborto_verificado_6g1` (L866–899) leyendo ANCLADO al descriptor del directorio acreditado (O_NOFOLLOW, L869–870); traslado a `_aborted*` sólo con `completo=True` y `publicar_dir_6g1` |
| `preparar_aborto_6g1(run_dir, log, cerrar_log, runners, memmaps, lectores)` | L1338–1430 | Cierre determinista previo (CR), verificación `/proc` de escrituras y mapeos abiertos bajo el provisional, cierre del log con contrato `(ok, error)` |
| `cerrar_recursos_corrida_6g1(runners, memmaps, lectores)` | L1228–1330 | Cierre idempotente de escritores WAV, memmaps (flush+mmap) y lectores con informe `completo` |
| `publicar_dir_6g1(origen, destino)` | L803–828 (+ `_renameat2_noreplace` L769–801) | Publicación por `renameat2(RENAME_NOREPLACE)` con sufijos ante colisión; fail-closed si el entorno no garantiza no-reemplazo |
| `MixHandle` / `abrir_mix` | L127–313 | Lectura e identidad del MIX de ENTRADA (no es artefacto de salida) |
| `registrar_propio_6g1` / `cerrar_verificado_6g1` / `runner_parcial_6g1` | L515 / L1176 / L1209 | Registro de propiedad y cierre verificado por objeto (base del registro F1) |

## 2. Hardened (`MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py`)

Estructura: `main` (L2240) → `run_experiment` (L1494) con clase `CandidateRunner` (L1374) y helpers `create_run_dir` (L1430), `_open_memmap` (L1455), `post_wav_identity` (L1463), `write_reports` (L2068), `write_pngs` (L2183).

| Operación | Ubicación exacta (función: líneas) |
|---|---|
| Creación del provisional | `create_run_dir` L1430–1455: `out_base` `makedirs` L1438; `partial_dir = final_dir + "_partial"` L1445; **`_crear_y_acreditar_dir_6g1(out_base, basename(partial_dir))` L1448**; reintento ante `FileExistsError` L1449–1454. Anclaje propuesto: conservar aquí `fd_padre`/`fd_run` (v2, diseño) |
| `fd_padre`/`fd_run` | **NO se conservan hoy**: abiertos y cerrados dentro de `crear_y_acreditar_dir_6g1` (lectura_segura L401/L410 y L368/L415). Inserción de anclaje: retorno v2 en L1448 |
| Creación de artefactos y descriptores | WAV: `CandidateRunner.__init__` L1396 (`sf.SoundFile(path, mode="w")` por ruta) + `_registrar_propio_6g1` L1397; SDI L1398–1399; limpieza de runner parcial (AI-D) L1400–1403. NPY: `_open_memmap` L1455–1458 (`open_memmap(path, mode="w+")` por ruta). JSON/log: `open(path, "w")` por ruta (L1957, L2130; log vía `Tee` L173/L215) |
| Escrituras | WAV: `writer_sdv/sdi.write(...)` en el pipeline del runner. NPY: asignaciones sobre memmaps L1628–1639 (`mask_<pid>_vocal/instrumental`, `consensus_vocal_<m>/instrumental_<m>`, `confidence_map`, `model_disagreement_map`; condicionadas por `write_masks` L1625). JSON: `analysis.json` L2130–2132, `input_integrity_6g.json` L1957–1961. Log: `Tee.write` L181–188 (consola+archivo con flush). TXT: `analysis.txt` L2134–2135 vía `write_analysis_txt` (open L2140) |
| `masks` y `candidates` | `masks_dir` `makedirs(exist_ok=True)` L1616 (dentro del bloque protegido). Candidates: individual `sub = run_dir/candidates/individual_<id>` L1652–1653 + `makedirs` L1654 (sólo `full_mode and opt.write_all_candidates` L1651); consensus `sub = run_dir` si default, si no `candidates/consensus_<m>` L1670–1671 + `makedirs` L1672 (sólo `full_mode and (is_default or opt.write_all_candidates)`) |
| Lecturas posteriores de artefactos | `post_wav_identity` L1889 (sólo `full_mode`): lee `mix` vía `hmix.ruta_lectura()` (handle) y los WAV de salida **por ruta** desde `run_dir`; `input_integrity_6g.json` re-leído L1962–1963 (verificación de escritura); lecturas del log: `Tee._file` hasta `close_tee` |
| Publicación y verificación de identidad | Cierre acreditado del log `close_tee()` L1929–1934 (fallo → `_CierreNoAcreditado_6g1`); guarda final sobre el provisional L1937–1944 (`hmix.verificar()` + `ruta_apunta_al_mismo_objeto()`); cierre acreditado del Mix L1946–1955; evidencia de integridad L1957–1963; comprobación final L1968–1977 (fallo → `FalloCorrida(MIX_CAMBIADO…, trasladar=False)`); **publicación `_publicar_dir_6g1(run_dir, run_dir_final)` L1984** (fallo → `PUBLICACION_SEGURA_FALLIDA`, trasladar=False) |
| Camino de éxito | L1979–2003: publica → limpia `masks/` del PUBLICADO con `shutil.rmtree` L1995–2001 (sólo tras publicación exitosa; aviso si falla) → `return EXIT_OK, run_dir_final` L2003 |
| Camino de excepción | `except _FalloCorrida_6g1` L2020–2035: `_preparar_aborto_6g1(run_dir, log, close_tee, runners=locals().get("runners"), memmaps=locals().get("mm"), lectores=(hmix, handles))` L2028 → `_abortar_corrida_6g1(run_dir, run_dir_final+"_aborted", motivo, detalle, trasladar=…, cierre=_cr6g1)` L2030 → `close_tee()` L2033 → `EXIT_PROCESSING` L2035. Genérico: `except Exception` L2036–2052 (preparar L2046; motivo `EXCEPCION_DURANTE_EL_PROCESAMIENTO`) |
| Camino de interrupción | `except KeyboardInterrupt` L2004–2019: preparar L2013 → abortar con motivo `INTERRUPCION_DEL_USUARIO` L2016 → `close_tee()` L2019 → `EXIT_ABORTED`. Sin `signal.signal` (sólo Ctrl-C de Python) |
| Aborto y evidencia | `abortar_corrida_6g1` (lectura_segura L900–1026): `ABORT_6G1.json` escrito por descriptor acreditado y verificado (L866–899); traslado sólo si `completo=True`; el provisional (o su traslado) conserva TODOS los artefactos sin eliminación |
| Cierre de descriptores | `cerrar_recursos_corrida_6g1` (runners → memmaps → lectores) + `close_tee` (contrato `(ok, error)`) + `hmix.close()` acreditado L1946–1955; `candidates`/`masks` dirs no conservan fds hoy |

Modos y flags: `full_mode = (mode == MODE_FULL_PROCESSING or mode == MODE_SINGLE_PAIR)` L1622; `write_masks = opt.png or opt.keep_masks` L1625; `--write-all-candidates` L2235; `--png` L2236; `--keep-masks` L2237; `--manifest` L2217 (única receta no interactiva verificada).

## 3. EVO (`MOTOR_SEP_SDV-SDI_EVO.py`)

Misma arquitectura que Hardened con líneas propias (verificadas individualmente, NO por similitud):

| Operación | Ubicación exacta |
|---|---|
| Creación del provisional | `create_run_dir` L1430–1455: `makedirs(out_base)` L1438; **`_crear_y_acreditar_dir_6g1` L1448** |
| Artefactos y descriptores | `CandidateRunner` L1374: WAV L1396/L1398 (+registro L1397/1399, parcial L1400–1403); `_open_memmap` L1456; `post_wav_identity` def L1461 |
| Escrituras | memmaps L1698–1709 (condicionadas por `write_masks = opt.png or keep_masks` L1695; `full_mode` L1692); JSON `analysis.json` L2241–2243, `input_integrity_6g.json` L2068–2074 (escritura + re-lectura L2073–2074); `analysis.txt` L2245–2246; log `init_tee` L1683 (`Tee` L178, `close_tee` L227) |
| `masks`/`candidates` | `makedirs(masks_dir)` L1685; candidates individual L1723–1724, consensus L1741–1742 (condiciones idénticas a H: `write_all_candidates` / `is_default`) |
| Lecturas posteriores | `post_wav_identity` llamada L2000 (full_mode, por ruta); `input_integrity_6g.json` re-leído L2073–2074 |
| Publicación y verificación | `write_reports` L2029; `write_pngs` L2030–2031 (`opt.png and MATPLOTLIB_OK`); cierre acreditado del log L2036–2045; guarda final + cierre Mix + evidencia L2046–2088; **publicación L2095**; `rmtree(masks)` del publicado L2105–2112 |
| Éxito / excepción / interrupción | `EXIT_OK` tras publicación (~L2113); `except KeyboardInterrupt` L2115 (preparar L2124; `INTERRUPCION_DEL_USUARIO`); `except _FalloCorrida_6g1` (preparar L2139); `except Exception` (preparar L2157); `close_tee` en cada camino; `main` KI L2438 |
| Aborto y cierre | idénticos servicios de `lectura_segura_6g1` (§1); sin `signal.signal` |

Flags: `--manifest` L2328, `--write-all-candidates` L2346, `--png` L2347, `--keep-masks` L2348. **Advertencia permanente:** la compatibilidad EA/PDA-1 de EVO NO se infiere de la similitud con Hardened; exige RG-FLOW propio (doc DISENO_RG_FLOW, §3).

## 4. MQR (`sdv_sdi_mqr_engine.py`) — ANÁLISIS PRIORITARIO

Estructura en dos fases: `main` (L3740) → `run_experiment` (L2205) → `_run_core` (L2445); `create_run_dir` (L2159); `CandidateRunner` (L2093); `write_reports` (L3098); `run_self_test` (L3419); `write_pngs` (L3618).

### 4.1 Operaciones mapeadas

| Operación | Ubicación exacta |
|---|---|
| Creación del provisional | `run_experiment` L2346–2352: `create_run_dir(opt.out_base)` L2347 → `create_run_dir` L2159–2188: `makedirs(out_base)` L2171; **`_crear_y_acreditar_dir_6g1` L2181**; reintento L2182–2188. Fallo → `EXIT_PROCESSING` sin corrida |
| `fd_padre`/`fd_run` | NO conservados hoy (ídem §1); inserción de anclaje en L2181 con propagación a `_run_core` vía `ctx` (patrón vigente: `ctx["_recursos_6g1"]` L2464–2465) |
| Artefactos y descriptores | `CandidateRunner` L2093: WAV `SDV.wav` L2115–2117 + registro L2119; `SDI.wav` L2120–2123 + registro L2124; **nombres FIJOS** ("SDV.wav"/"SDI.wav", sin prefijo por runner; cada candidato escribe bajo SU subdirectorio). memmaps L2469–2487 (`_open_memmap` L2190): **INCONDICIONALES** para todos los pares + consensos + `confidence_map` + `model_disagreement_map` |
| Escrituras | memmaps L2469–2487; JSON `analysis.json` L3191–3195, `input_integrity_6g.json` L2804–2811 (escritura + re-lectura L2810–2811); `analysis.txt` L3197–3198; log `init_tee` L2358 (`Tee` L309?, `close_tee` L371) |
| `masks`/`candidates` | **`masks_dir` `makedirs(exist_ok=True)` L2361 SIEMPRE** (no existe `--keep-masks` en MQR: flags L3689/3714/3717); registro de runners en `ctx["_recursos_6g1"]["runners"]` L2506; candidates individual `makedirs` L2512 (sólo `full_mode and opt.write_all_candidates` L2508), consensus L2529 (`is_default or write_all_candidates` L2523); lectores registrados L2559 |
| Lecturas posteriores | `post_wav_identity` llamada L2730–2733 (full_mode; WAVs por ruta); `input_integrity_6g.json` re-leído L2810–2811; **relectura de `analysis.json` L3578–3579: EXCLUSIVA del autotest** (§4.2) |
| Publicación y verificación | `write_reports(ctx, run_dir, opt)` L2776; `write_pngs` L2777–2778 (`if opt.png`); guarda final L2783–2819 (`_h6g1.verificar()` + `ruta_apunta_al_mismo_objeto()` L2786–2787; cierre acreditado del Mix L2797–2801; evidencia L2804–2811; comprobación L2813–2819 → `FalloCorrida(MIX_CAMBIADO…, trasladar=False)`); cierre acreditado del log L2826–2833; **publicación `_publicar_dir_6g1` L2838** (fallo → `PUBLICACION_SEGURA_FALLIDA`); contrato de retorno CV-B verificado en `run_experiment` L2368–2375 |
| Éxito | `run_experiment` L2434–2443: `close_tee()` L2435, `log("Corrida COMPLETA…")`, `return EXIT_OK, run_dir_final` L2443 |
| Excepción | `except _FalloCorrida_6g1` L2395–2412 (preparar L2403 con recursos de `ctx`); `except Exception` L2413–2433 (preparar L2422; `EXCEPCION_DURANTE_EL_PROCESAMIENTO`) |
| Interrupción | `except KeyboardInterrupt` L2377–2394 (preparar L2387; `INTERRUPCION_DEL_USUARIO`; `EXIT_ABORTED`); sin `signal.signal` |
| Aborto y cierre | mismos servicios de `lectura_segura_6g1` (§1); recursos pasados desde `ctx["_recursos_6g1"]` (memmaps L2465, runners L2506, lectores L2559) |

### 4.2 Punto MQR exclusivo resuelto estáticamente: la "relectura de `analysis.json` (L3578)"

1. **Quién escribe inicialmente `analysis.json`:** `write_reports` (def L3098), `open(os.path.join(run_dir, "analysis.json"), "w")` **L3191–3192** + `json.dump` L3193–3194 + `_registrar_propio_6g1` L3195. Llamada desde `_run_core` L2776 (log "Escribiendo analysis.json / analysis.txt…" L2775). Es la ÚNICA escritura del pipeline (grep completo: L105/L137 comentarios; L2775 log; L3191 escritura; L3577/3578 lectura del autotest; L3828 `print` de ayuda).
2. **Quién lo vuelve a abrir o leer:** **NADIE dentro del pipeline de producción.** La única relectura está en `run_self_test()` (def **L3419**), prueba T7 "pipeline e2e": tras `run_experiment` (L3566–3567) y sólo si `code == EXIT_OK` (L3569), abre el `analysis.json` del directorio **YA PUBLICADO** por ruta y lo valida (24 secciones L3583–3600, SNR post-wav >80 dB L3601–3604).
3. **Momento respecto al cierre de descriptores:** la relectura ocurre DESPUÉS de que `_run_core` cerró todos los recursos (cierre verificado CR), cerró el log acreditado (L2826–2833) y PUBLICÓ (L2838) — es decir, es una lectura **post-publicación, post-cierre, fuera del ciclo de descriptores de la corrida**.
4. **¿Puede usar el descriptor conservado o requiere adaptación?** El pipeline NO necesita descriptor conservado para esta relectura porque **no existe dentro del ciclo**. La adaptación necesaria es del LADO DEL AUTOTEST: hoy lee por la ruta publicada (dominio residual post-return, B1); para alinearlo al modelo, el autotest debería verificar primero la identidad del directorio publicado contra la evidencia `(dev,ino)` de la corrida (patrón G1/auditoría externa) y/o leer anclado; alternativamente puede declararse expresamente lectura post-return de auditoría (fuera del modelo de prevención). **No se modificó nada** (fase de lectura).
5. **¿Qué sucede ante sustitución de la entrada nominal?** (a) DENTRO del pipeline: si la entrada final `analysis.json` se sustituyera entre su creación (L3191) y la publicación, no hay relectura en el pipeline que la detecte hoy — la detección corresponde a la guarda E (checklist identidad vs fd, prototipo) o a la verificación por descriptor; la escritura por ruta `open(...,"w")` seguiría además el symlink (brecha C, cierre C5/C6 en diseño). (b) AUTOTEST: la lectura L3578 seguiría la ruta nominal publicada — si el directorio publicado fuera secuestrado post-return (misma uid), el autotest validaría el impostor; mitigación propuesta en 4.
6. **Cómo se mantiene la identidad del archivo durante el ciclo completo (diseño, NO implementado):** creación exclusiva `O_CREAT|O_EXCL|O_NOFOLLOW` relativa a `fd_run` (C5) + conservación de `fd_archivo` en `write_reports` (C6: la escritura JSON vía `os.fdopen(dup(fd))`) + checklist E por descriptor (identidad `(dev,ino)` vs `fstat(fd)`) + auditoría forense G (`publicacion_6g1.json` con SHA-256 antes del renombrado) + relectura del autotest con verificación previa de identidad del publicado. La solución NO se asume heredada de Hardened/EVO: `write_reports` de MQR es una función distinta (L3098) y su integración exigirá RG-FLOW-6/8 propio.

## 5. Conclusiones comparativas y estado

- Los tres motores comparten el MISMO servicio de creación/acreditación (con descriptores internos NO conservados), el MISMO protocolo de aborto (CV/CR) y la MISMA publicación no-reemplazo (G); difieren en estructura (H/EVO monofásicos en `run_experiment`; MQR bifásico con contrato CV-B), en la obligatoriedad de `masks` (H/EVO condicional; MQR SIEMPRE) y en los nombres de WAV por defecto (`mix SDV.wav`/`mix SDI.wav` en H/EVO; `SDV.wav`/`SDI.wav` fijos en MQR).
- Hoy NINGÚN motor conserva `fd_padre`/`fd_run`/`fd_masks`/`fd_candidates`/`fd_archivo`: toda la creación es por ruta (`open 'w'`, `sf.SoundFile(path)`, `open_memmap(path)`, `makedirs(exist_ok)`) — el análisis C (brecha de la entrada final, misma uid) aplica tal cual a los tres; el cierre (C5/C6/C6-log) y la guarda E quedan en DISEÑO.
- No se ejecutó ninguna corrida; no se modificó producción; RG-FLOW queda diseñado (no ejecutado) y la matriz de artefactos se entrega como base futura de la guarda E y de la auditoría SHA-256 (sin ampliar G1).

*Fin del informe de auditoría estática. Agente en parada tras publicar.*
