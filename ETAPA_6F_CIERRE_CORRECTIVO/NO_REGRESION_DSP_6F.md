# Etapa 6F · No regresión DSP

Ejecutado: `scripts/no_regresion_dsp_6f.py`. Evidencia:
`evidence/dsp_no_regresion.json`.

## 1. Comparación de PCM

8 configuraciones × 3 motores = 24 comparaciones, con `--allow-misaligned` en
las tres versiones (6C, 6E, 6F) y el mismo manifiesto por caso. Se comparan
hashes SHA-256 de las muestras decodificadas float64, forma, tasa, finitud, pico
y crestas de MQR.

| Comparación | Resultado |
|---|---|
| 6F vs 6E | **24/24 idénticas** (SDV y SDI) |
| 6F vs 6C | **23/24 idénticas**; 1 no comparable (`MQR/side`, 6C aborta por la división indefinida de cresta) |
| Formas | iguales en todas las comparaciones |
| Crestas MQR | iguales en todas |
| Finitud | todas las salidas finitas |

Casos: `clean`, `side`, `dual_173`, `shift_567`, `right_rival_.125`,
`different_lr`, `4s_clean`, `4s_shift_1000`.

## 2. Auditoría AST

Se comparan todas las definiciones de nivel superior y todas las constantes en
mayúsculas (valores) entre 6F y 6C / 6E.

| Motor vs | Definiciones cambiadas | Constantes cambiadas | Definiciones DSP cambiadas |
|---|---|---|---|
| Hardened / 6E | `_combine`, `analyze_alignment`, `run_experiment`, `write_reports` | ninguna | **ninguna** |
| EVO / 6E | idem | ninguna | **ninguna** |
| MQR / 6E | `_combine`, `analyze_alignment`, `build_validation_status`, `run_experiment` | ninguna | **ninguna** |
| Hardened / 6C | las anteriores + `probe_file`, `build_arg_parser` (heredadas de 6E) + `_attribution_state` añadida | ninguna | **ninguna** |
| EVO / 6C | idem | ninguna | **ninguna** |
| MQR / 6C | idem + `CandidateMetrics`, `stream_level_stats` (corrección de cresta de 6E) | ninguna | **ninguna** |

Ninguna de las definiciones que tocan muestras cambia: `mono_downmix`,
`read_span`, `stft_span_frames`, `OlaStream`, `apply_sfumato_smoothing`,
`TruePeakStream`, `build_band_masks`, `compute_vocal_mask`,
`confidence_and_disagreement`, `consensus_from_masks`, `FramePlan`,
`PairwiseAccum`, `GlobalMaskAccum`, `PearsonAccum`, `mask_stats_stream_*`.

`run_experiment` cambia **sólo** por la compuerta de continuación (antes del
directorio de corrida); `write_reports` sólo añade el campo `alignment_gate`.
`analyze_alignment` y `_combine` son diagnóstico puro.

## 3. Diff reproducible

`scripts/construir_motores_6f.py` regenera las copias desde 6E y reporta
89 (Hardened), 89 (EVO) y 102 (MQR) líneas de diff, correspondientes a cinco
regiones: importación del módulo, `_combine`, `analyze_alignment`, compuerta CLI
y campo de informe (más, en MQR, el ítem de `validation_status`).
`--check` verifica que las copias publicadas coinciden exactamente con lo que
produce el constructor.

## 4. Límites

* Las comparaciones usan `float64` decodificado, no los bytes WAV: dos archivos
  con distinto subtipo pero idénticas muestras aparecerían como iguales (las
  formas y el subtipo se registran aparte).
* No se instrumentaron tensores intermedios de la STFT ni máscaras; la prueba es
  de extremo a extremo sobre las muestras y de estructura sobre el AST.
* No se comparó con el motor v3 original (protegido, no ejecutado en 6F) ni se
  cubrieron todos los modos, parámetros, residual o combinaciones de consenso.
* Los casos son sintéticos de 1 s y 4 s; no se probaron canciones reales.
