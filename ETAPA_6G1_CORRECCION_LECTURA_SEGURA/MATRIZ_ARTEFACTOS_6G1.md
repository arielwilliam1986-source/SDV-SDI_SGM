# 6G.1 — MATRIZ REAL DE ARTEFACTOS POR MOTOR Y MODO (base futura de la guarda E y de la auditoría SHA-256)

- **Destinatario:** Cris. **Naturaleza:** documento de diseño derivado de la auditoría estática (lectura exclusiva). **No amplía G1** (instrucción §4).
- **Referencias de línea:** ver INFORME_AUDITORIA_ESTATICA_INTEGRACION_6G1.md (mismo commit). "H/EVO" indica líneas de Hardened y EVO respectivamente cuando difieren.
- Leyenda: **OB** = obligatorio; **COND** = condicional por modo; **OPC** = opcional. "Descriptor (diseño)" = descriptor que la guarda E exigiría tras la adaptación (hoy la creación es por ruta y NO se conservan descriptores).

## 1. Hardened — modos: `full_processing` / `single_pair` (L1622); flags: `--write-all-candidates` L2235, `--png` L2236, `--keep-masks` L2237

| Artefacto | Condición (modo real) | Obl. | Tipo esperado | Método de creación (líneas) | Descriptor (diseño) | Lectores posteriores (líneas) | Publicación | Aborto |
|---|---|---|---|---|---|---|---|---|
| `engine_log.txt` | siempre (init_tee L1614) | OB | regular | `Tee(path)` L173/L215, `open(path,"w")` por ruta | `fd_log` (O_EXCL\|NOFOLLOW + `TeeAnclado` fileobj sobre dup) | `Tee._file` hasta `close_tee()` L1929–1934 | presente antes del cierre acreditado; NO se elimina (PATCH 6) | conservado; su cierre forma parte de `preparar_aborto_6g1` (contrato `(ok,error)`) |
| `analysis.json` | siempre (write_reports L2130) | OB | regular | `open(path,"w")` L2130 + `_registrar_propio_6g1` L2132 | `fd_json` (O_EXCL\|NOFOLLOW) | NINGUNA en pipeline; autotests externos | antes de `close_tee` L1929 | conservado; invalidado en `ABORT_6G1.json` |
| `analysis.txt` | siempre (L2134–2135) | OB | regular | `open(path,"w")` L2140 (`write_analysis_txt` L2137) | `fd_txt` | ninguna | antes de `close_tee` | conservado; invalidado |
| `input_integrity_6g.json` | siempre (L1957–1961) | OB | regular | `open(path,"w")` L1957–1958 + registro L1960 | `fd_integ` | **re-lectura de verificación L1962–1963** (misma uid, por ruta) | antes de `close_tee` | conservado; invalidado |
| `mix SDV.wav` / `mix SDI.wav` | `full_mode` (default consensus runner, `sub=run_dir` L1670–1671) | OB en full/single | regular | `sf.SoundFile(path, mode="w")` L1396/L1398 (por ruta) | `fd_wav` (O_EXCL\|NOFOLLOW; escritura fileobj-dup) | **`post_wav_identity` L1889** (full_mode, por ruta) | antes de `close_tee` | conservados; invalidados |
| `candidates/individual_<id>/…` WAVs | `full_mode AND --write-all-candidates` (L1651–1654) | COND | directorio real + regulares | `makedirs(exist_ok)` L1654; WAVs L1396/L1398 con `run_dir=sub` | `fd_candidates` (subdir) + `fd_wav` por WAV | post_wav sólo para default | antes de `close_tee` | conservados; invalidados |
| `candidates/consensus_<m>/…` WAVs | `full_mode AND (no default) AND (default OR --write-all-candidates)` (L1670–1672) | COND | ídem | `makedirs` L1672; WAVs L1396/L1398 | ídem | ídem | ídem | ídem |
| `masks/*.npy` (mask_<pid>_v/instr, consensus_*, confidence_map, model_disagreement_map) | `write_masks = --png OR --keep-masks` (L1625); creaciones L1628–1639 | COND (OB si el modo activó masks) | directorio real + regulares | `open_memmap(path, mode="w+")` L1456 (por ruta) | `fd_masks` (subdir) + `fd_npy` O_RDWR por npy | escrituras continuas hasta cierre CR | **NO condiciona EXIT_OK hoy**; `rmtree` del PUBLICADO tras éxito L1995–2001 | conservados SIEMPRE en aborto (AI-E: sin limpieza pre-publicación) |
| `png/*.png` | `--png AND MATPLOTLIB_OK` (L1919–1920); creaciones `write_pngs` L2183–2204 | OPC | directorio + regulares | matplotlib `savefig` L2204 (por ruta) | (diseño: por ruta + checklist de tipo/no-symlink; procfs NO probado) | ninguna | antes de `close_tee` | conservados |
| `ABORT_6G1.json` | sólo camino de aborto (lectura_segura L866–899, L900–1026) | OB en aborto | regular | por descriptor acreditado (O_NOFOLLOW, dir_fd) | ya anclado hoy (L869–870) | re-lectura verificada L874–890 | traslado a `_aborted*` sólo si `completo=True` | — (es la evidencia) |

## 2. EVO — misma matriz que Hardened con líneas propias

Diferencias verificadas (todo lo demás idéntico en semántica): `run_experiment` L1559; `init_tee` L1683; `masks` makedirs L1685; `full_mode` L1692; `write_masks` L1695; memmaps L1698–1709; candidates L1723–1724 / L1741–1742; `post_wav_identity` def L1461, llamada L2000; `write_reports` L2029; `write_pngs` L2030–2031; cierre acreditado del log L2036–2045; `input_integrity_6g.json` L2068–2074 (re-lectura L2073–2074); publicación L2095; `rmtree(masks)` L2105–2112; handlers L2115–2175 (preparar L2124/2139/2157); `analysis.json` L2241–2243; `analysis.txt` L2245–2246; `write_pngs` def L2294 (`savefig` L2315); flags L2328/2346/2347/2348. Nombres de WAV default: `f"{track_base} SDV.wav"` (L2000).

**La compatibilidad de EVO con el diseño NO se asume por similitud:** esta matriz es su referencia y su validación exige RG-FLOW propio (FLOW-1..8 EVO) antes de cualquier declaración.

## 3. MQR — modo `full_processing` (L2457); flags: `--write-all-candidates` L3714, `--png` L3717 (**NO existe `--keep-masks`**)

| Artefacto | Condición (modo real) | Obl. | Tipo esperado | Método de creación (líneas) | Descriptor (diseño) | Lectores posteriores (líneas) | Publicación | Aborto |
|---|---|---|---|---|---|---|---|---|
| `engine_log.txt` | siempre (init_tee L2358) | OB | regular | `Tee(path)` por ruta | `fd_log` + `TeeAnclado` | `Tee._file` hasta `close_tee()` L2826–2833 (en `_run_core`) | antes del cierre acreditado | conservado; cierre en `preparar_aborto_6g1` |
| `analysis.json` | siempre (L3191–3195) | OB | regular | `open(path,"w")` L3191 + registro L3195 | `fd_json` | **NINGUNA en pipeline** (relectura L3578 = autotest T7, post-publicación: ver informe §4.2) | antes de `close_tee` L2826 | conservado; invalidado |
| `analysis.txt` | siempre (L3197–3198) | OB | regular | `write_analysis_txt` (open "w") | `fd_txt` | ninguna | ídem | conservado; invalidado |
| `input_integrity_6g.json` | siempre (L2804–2811) | OB | regular | `open(path,"w")` L2805 + registro L2810 | `fd_integ` | **re-lectura de verificación L2810–2811** (por ruta) | antes de `close_tee` | conservado; invalidado |
| `SDV.wav` / `SDI.wav` | default consensus con `write_audio` (nombres FIJOS L2115/L2120) | OB en full | regular | `sf.SoundFile(path, mode="w")` L2115–2117/L2120–2123 | `fd_wav` | **`post_wav_identity` L2730–2733** (por ruta) | antes de `close_tee` | conservados; invalidados |
| `candidates/individual_<id>/SDV.wav`+`SDI.wav` | `full_mode AND --write-all-candidates` (L2508–2512) | COND | directorio real + regulares (dos niveles: `candidates/<grupo>/`) | `makedirs` L2512; WAVs L2115/L2120 con `run_dir=sub` | `fd_candidates` + `fd_wav` | post_wav sólo default | antes de `close_tee` | conservados; invalidados |
| `candidates/consensus_<m>/…` | `full_mode AND (no default) AND (default OR --write-all-candidates)` (L2523–2529) | COND | ídem | `makedirs` L2529 | ídem | ídem | ídem | ídem |
| `masks/*.npy` (todos los pares + consensos + confidence_map + model_disagreement_map) | **SIEMPRE** (L2469–2487 incondicionales; `masks_dir` L2361) | **OB SIEMPRE** (diferencia clave vs H/EVO) | directorio real + regulares | `open_memmap(path, mode="w+")` L2190/L2469–2487 | **`fd_masks` OBLIGATORIO en MQR** + `fd_npy` O_RDWR | escrituras hasta cierre CR | **NO se elimina nunca** (sin `rmtree` en MQR) | conservados SIEMPRE |
| `png/*.png` | `--png` (L2777–2778; `write_pngs` L3618: makedirs L3626, savefig L3656/L3670) | OPC | directorio + regulares | matplotlib (por ruta) | (ídem H: checklist tipo/no-symlink) | ninguna | antes de `close_tee` | conservados |
| `ABORT_6G1.json` | sólo aborto | OB en aborto | regular | por descriptor acreditado (L866–899) | ya anclado hoy | re-lectura verificada | traslado condicionado | — |

## 4. Cruce con la guarda E (checklist) — propuesta de consolidación

- `SPEC_COMUN` (prototipo): `engine_log.txt`, `analysis.json`, `analysis.txt`, `input_integrity_6g.json`, `mix SDV.wav`, `mix SDI.wav` — **coincide con H/EVO**; para MQR los WAV obligatorios se llaman `SDV.wav`/`SDI.wav` (matriz §3) y `masks/` pasa a **obligatorio SIEMPRE** (con identidad vs `fd_masks`, E1-B).
- Todo artefacto OB exige: existe + tipo esperado + no-symlink + **descriptor presente** + identidad `(dev,ino)` vs fd (E1-A/E1-B rectificadas).
- Los COND se activan por los flags reales de cada motor (tabla); los OPC (png) se verifican por tipo/no-symlink si presentes.
- **Auditoría SHA-256 futura (G):** la columna "Lectores posteriores" delimita qué ficheros tendrían hashes en `publicacion_6g1.json` por motor/modo; **NO se amplía G1 en esta fase** (instrucción §4).

*Fin de la matriz. Agente en parada tras publicar.*
