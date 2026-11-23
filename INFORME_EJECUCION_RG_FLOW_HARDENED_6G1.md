# INFORME DE EJECUCIÓN — RG-FLOW-1..4 SOBRE HARDENED SIN ADAPTACIÓN (ETAPA 6G.1)

**Dirigido a:** ChatGPT / Cris (adjudicador de la autorización controlada).
**Fecha de ejecución:** 2026-11-23 (corrida final integral 20:54:46Z–20:55:51Z).
**Rama:** `arena/f1c5739f-sdv-sdi-sgm` — **compromiso hijo de `92b7c08`**.
**Autorización:** EXCLUSIVA de Cris (22-11-2026): FLOW-1..4 sobre Hardened SIN ADAPTACIÓN, fixtures sintéticos + arnés + ejecución controlada. NO autoriza PDA-1/EA/E1/F1/G1, NO FLOW-5..8, NO pruebas EVO/MQR, NO adaptación alguna.

---

## §0 Nota metodológica (léase antes de comparar corridas)

1. Los JSON de evidencia (`evidencia_rgflow_hardened_14/*.json`) contienen marcas de tiempo y pares `(dev,ino)` **reales del filesystem**; por diseño, **varían entre corridas**. Dos corridas correctas del mismo flujo producen JSON distintos en esos campos y idénticos en los campos semánticos (rc, motivo, validaciones booleanas). La evidencia comprometida corresponde EXCLUSIVAMENTE a la corrida final integral única (una sola invocación del arnés con `--flujos 1,2,3,4`).
2. El arnés (`scripts/arnes_rgflow_hardened_6g1.py`) **evolucionó durante la fase** (no el motor): (i) fixtures cambiados de tonos/chirps a ruido blanco PRNG tras dos fallos de la compuerta NCC; (ii) FLOW-2 convertido a ejecución en memoria; (iii) FLOW-4 reescrito (v2) con atacante temporizado y luego (v3) con sub-caso (b) determinista por inyección en memoria. Todas las ejecuciones del MOTOR usaron el mismo motor sin modificar.
3. Ningún archivo de producción fue leído para modificarlo ni modificado. Los árboles de trabajo quedan en `/tmp/rgflow_h1/` (fuera del repo, efímeros por diseño).

## §1 Identidades exactas

| Elemento | Valor |
|---|---|
| Rama | `arena/f1c5739f-sdv-sdi-sgm` |
| Compromiso base (padre de este trabajo) | `92b7c0829978945a90fc082c8b0db43f8a8e534f` |
| Padre de `92b7c08` | `504e2b9` |
| Verificación previa a ejecutar | local `HEAD` = `origin/arena/f1c5739f-sdv-sdi-sgm` = `gh api` = `92b7c08…` — **CONFORME** (re-verificado también inmediatamente antes de la corrida integral) |
| Compromiso hijo (este informe) | hijo directo de `92b7c08`, creado al cierre de esta fase |
| Motor Hardened ejecutado | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` — **SIN MODIFICAR** (0 cambios en `motores/` acreditados por `git status` y por el commit) |

## §2 Alcance ejecutado y fuera de alcance

- **Ejecutado:** FLOW-1 (éxito normal), FLOW-2 (excepción tras varios recursos), FLOW-3 (SIGINT), FLOW-4 (sustitución de entrada, caracterización expresa de D1 y C).
- **Fuera de alcance (no ejecutado, no simulado):** SIGTERM/SIGKILL, FLOW-5..8, EVO/MQR, corrección de defectos observados, cualquier mecanismo nuevo.

## §3 Fixtures sintéticos: inventario + SHA-256

Receta (idéntica para todos los flujos; `MANIFEST_RGFLOW.json` hash `3b69d7b011c40e14e4639141e431af728f45cae4c911967b60e77699b68ac7ae` en **todos** los casos, incluido F3):

- Ruido blanco PRNG determinista (semillas: vocal `20261122`, instrumental `19480720`), amplitud 0.30, `mix = 0.5·(vocal + instrumental)`, estéreo PCM_16, 44100 Hz.
- Duración: **30 s** para F1, F2, F4(a1,a2,b); **90 s** para F3 (ventana de disparo SIGINT; por eso los WAV de F3 difieren de los demás).

| Archivo | Casos 30 s — SHA-256 | Caso F3 90 s — SHA-256 |
|---|---|---|
| `vocal.wav` | `f1863bbab24c02507159e4e4e5aa0b5ec66202094e291111ab80423be9546daf` | `f8a424bf46ecf2e4a981b229575aebfba788d811ff3624544328c5a287b4c29f` |
| `instrumental.wav` | `9691c8b275c29d03a86e97355f6ad47517a2fc844f62dc4c16ad4d88d4b1e831` | `bc15fb2b2a21a75c09395717092ffeb81fcd5f9c2edfa51b5a728de322f5e67d` |
| `mix_sintetico.wav` | `bdf839ddc53b4d8c43215b23ad6670186defafae8c7c3fba24f319ed32b0d8bb` | `43d416e7593ba3d7ea789773861be48fb50cab8748d41c970faae5a78973bdef` |

Copias auditables comprometidas: `evidencia_rgflow_hardened_14/MANIFEST_RGFLOW_F1_F2_F4.json` y `MANIFEST_RGFLOW_F3.json`.

## §4 Comandos y configuración exactos (incluye `--allow-misaligned` y su justificación)

Motor subproceso (F1, F3, F4a1, F4a2), forma exacta (`$PY` = `/tmp/venv_i1/bin/python -B`; `$MOTOR` = ruta absoluta al motor Hardened):

```
$PY -B $MOTOR --manifest <fixtures>/MANIFEST_RGFLOW.json --mode full_processing --out <raíz>/out --allow-misaligned
```

F2 y F4b: misma cmdline pasada a `M.main(argv)` **en memoria** (importlib del archivo del motor, sin copia ni edición; `sys.path` apunta al dir de motores para dependencias internas).

F3 añadió `--keep-masks` (invariante del escenario: masks presentes al interrumpir); F2 también (`--keep-masks`).

**Justificación de `--allow-misaligned` (configuración CLI documentada, NO adaptación):** la compuerta de alineación (`atribucion_6f.py`, inspeccionado sin modificar) exige ≥2 ventanas con lag UNIQUE, cobertura ≥0.5 y MDR ≤0.35. Con ruido blanco PRNG, `measure` devuelve NCC=null con clasificación AMBIGUOUS/INSUFFICIENT_SIGNAL (ventanas de varianza cero): los fixtures sintéticos **no pueden** validar NCC por construcción (dos intentos previos con tonos+envolvente y chirps fallaron igual). `--allow-misaligned` produce veredicto `ALLOWED_EXPLICIT` (permiso `cli_allow_misaligned`, alcance `procesar_sin_corregir_alineacion`): **no altera offsets, muestras ni polaridad** y no bypasea validación física/no-finitos/integridad. Es configuración CLI del motor, no modificación de código ni de comportamiento por defecto.

## §5 FLOW-1 — éxito normal → **PASS**

- **rc = 0**, duración 10.56 s, ts `2026-11-23T20:54:46Z`.
- Identidad `(dev,ino)` del directorio **conservada parcial→publicado** (ino `534881` = `534881`; dir `motorA_run_20261123_205443_partial` → `motorA_run_20261123_205443`).
- 6/6 artefactos obligatorios **regulares** en el publicado: `analysis.json` (71285 B), `analysis.txt` (2313), `engine_log.txt` (420), `input_integrity_6g.json` (1295), `mix_sintetico SDV.wav` y `mix_sintetico SDI.wav` (10584088 c/u).
- `abort_en_publicado=False`, `masks_en_publicado=False` (eliminación post-publicación = comportamiento vigente).

## §6 FLOW-2 — excepción tras varios recursos → **PASS**

- Ejecución **en memoria** (`M.main(argv)`); inyección del arnés en el 2º `sf.SoundFile` modo `'w'` (punto RG-FLOW L1398). Motor sin modificar.
- **rc in-process = 2**; escrituras sf vistas = `mix_sintetico SDV.wav` + `mix_sintetico SDI.wav` en `_partial`; duración 6.32 s.
- Cierre de recursos `[6G.1-R/CR]`: `escritores=1 memmaps=6 lectores=0 completo=True errores=0` + «se cierra engine_log.txt; a continuación se registra el aborto».
- `ABORT_6G1.json` (2158 B) en `motorA_run_20261123_205453_aborted`: schema `abort-6g1/3`, motivo `EXCEPCION_DURANTE_EL_PROCESAMIENTO`, `resultados_validos=[]`, `directorio_acreditado=True`, 7 salidas invalidadas (6 masks + mix SDV), traslado a `_aborted`.
- Sin publicación indebida (`publicacion_indebida=[]`); **fds residuales = []** (snapshot post-corrida del proceso arnés; `fds_antes=[]`).

## §7 FLOW-3 — SIGINT → **PASS**

- Duración de fixtures 90 s; disparo SIGINT **tras masks/*.npy y WAV del runner** (ts `2026-11-23T20:55:20Z`); señal única SIGINT (SIGTERM/SIGKILL fuera de alcance).
- **rc = 130**; dir `motorA_run_20261123_205519_aborted`.
- `ABORT_6G1.json`: schema `abort-6g1/3`, motivo `INTERRUPCION_DEL_USUARIO`, 8 salidas invalidadas con estado «conservadas en el provisional; sin eliminación (C-R1)», `resultados_validos=[]`, conservados: `engine_log.txt`.
- **Masks conservadas = True** (invariante AI-E: sin borrado en aborto).
- Cierre `[6G.1-R/CR]`: `escritores=2 memmaps=6 lectores=3 completo=True errores=0` (ts 26.81–26.82 s).

## §8 FLOW-4 — sustitución de entrada (caracterización; D1 y C documentados expresamente) → **OBSERVADO (caracterización)**

Registro fiel del comportamiento VIGENTE; **no es un veredicto de seguridad ni presupone detección**.

| Sub-caso | Mecanismo | Momento del swap | rc | Resultado observado |
|---|---|---|---|---|
| **a1_intermedio_inmediato** | proceso atacante mismo-uid (subreaddir `partial` + recrear en árbol propio) | +0.05 s tras observar `*_partial` (≈ +6,6 s: tras toda la validación, en procesamiento) | **2** | `LibsndfileError` (System error) al abrir `mix_sintetico SDV.wav` en la **ruta nominal** del árbol REAL; cierre de recursos completo (escritores=2, completo=True); **motor aborta SIN escribir `ABORT_6G1.json` en NINGÚN árbol** (anclaje H1 ciego: identidad≠ruta); provisional real conservado; sin fail-open a publicación (`publicado_en=None`); árbol del atacante sin artefactos de motor. **D1 observado.** |
| **a2_intermedio_procesamiento** | ídem | +4.0 s tras observar `*_partial` (≈ +10,6 s: **post-publicación**, EXIT_OK ≈ +6,5 s) | **0** | Motor publicó normalmente en su árbol (`user.orig`, dir final regular, `analysis.json` regular) y terminó EXIT_OK; el `_partial` recreado por el atacante quedó en el árbol del atacante; sin ABORT en ningún árbol. Frontera temporal caracterizada: el swap sólo es efectivo entre apertura de escritores y post_wav. |
| **b_entrada_final** | **inyección EN MEMORIA del arnés** en la frontera de `publicar_dir_6g1` (mismo uid; motor sin modificar; determinista) | pre-publicación: `unlink`+`symlink` de `analysis.json` del provisional → `objetivo/impostor.json` | **0** | **El `analysis.json` PUBLICADO es un symlink al impostor** (`apunta_al_impostor=True`; impostor intacto `{"impostor": true}`); conjunto publicado MIXTO: 5 artefactos regulares reales + 1 symlink atacante; EXIT_OK. **C demostrado de forma determinista: la entrada final publicada puede quedar bajo control de un mismo-uid sin que el motor lo impida.** |

Clasificación de los tres sub-casos: `EXPERIMENTAL_RESULT (caracterización)`. En la taxonomía PASS/FAIL/UNKNOWN/NO EJECUTADO: **UNKNOWN como veredicto de seguridad** (caracterización completa; el diseño no presupone detección y esta corrida no la afirma).

## §9 Inventario de artefactos creados / modificados / ausentes

- **Creados (repo, commit hijo — todo añadido, nada de producción):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_rgflow_hardened_6g1.py` (arnés; NUEVO)
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidencia_rgflow_hardened_14/` (5 JSON + 2 copias de manifiesto de fixtures)
  - `INFORME_EJECUCION_RG_FLOW_HARDENED_6G1.md`, `MANIFEST_EJECUCION_RG_FLOW_HARDENED_6G1.json`, `SHA256SUMS_EJECUCION_RG_FLOW_HARDENED_6G1.txt`
- **Modificados:** NINGUNO (0 ficheros de producción; `motores/` intacto; `git status` previo al commit acreditado).
- **Ausentes (no generados, fuera de alcance):** FLOW-5..8, EVO/MQR, SIGTERM/SIGKILL, correcciones de defectos.
- **Fuera del repo (efímeros, no comprometidos):** árboles de trabajo `/tmp/rgflow_h1/f{1,2,3}, f4_*/` con fixtures, consola, stderr, atacante.json y árboles de corrida.

## §10 Registro de fds

- F2: snapshot del proceso arnés — `fds_antes=[]`, `fds_residuales=[]` (sin fugas tras in-process).
- F2 cierre en log: `escritores=1 memmaps=6 lectores=0 completo=True errores=0`.
- F3 cierre en log: `escritores=2 memmaps=6 lectores=3 completo=True errores=0`.
- F1: sin aborto → no hay líneas de cierre extraordinario ni instrumentación de fds en su JSON (registro honesto: no instrumentado en esta corrida).
- F4a1 cierre en log del árbol real: `escritores=2 memmaps=0 lectores=3 completo=True errores=0`.

## §11 Veredictos (taxonomía exigida PASS/FAIL/UNKNOWN/NO EJECUTADO)

| Flujo | Veredicto | Observación |
|---|---|---|
| FLOW-1 | **PASS** | criterio: EXIT_OK + 6/6 obligatorios regulares + identidad (dev,ino) conservada + sin ABORT + masks eliminadas post-publicación |
| FLOW-2 | **PASS** | criterio: excepción → cierre completo → ABORT acreditado → sin publicación indebida → sin fds residuales |
| FLOW-3 | **PASS** | criterio: SIGINT → rc=130 → ABORT INTERRUPCION_DEL_USUARIO → masks conservadas → cierre completo |
| FLOW-4 | **UNKNOWN (caracterización OBSERVADO)** | sin veredicto de seguridad; D1 y C registrados fielmente; NO se afirma detección ni integridad |

## §12 Clasificación epistémica

- `EXPERIMENTAL_RESULT`: todo lo ejecutado en §5–§8 (corridas reales, mediciones).
- `DOCUMENTED_FACT`: existencia y semántica del flag `--allow-misaligned` y del gate `alignment_gate` (código vigente inspeccionado).
- `THEORETICAL_DEDUCTION`: la generalización «un mismo-uid puede hacer X en cualquier análogo» a partir de los sub-casos observados (sólo lo observado es Experimental).
- `UNKNOWN`: cualquier propiedad no demostrada aquí (p. ej. comportamiento con atacantes fuera de las tres ventanas ensayadas, EVO/MQR, FLOW-5..8).
- Recordatorio T7: **identidad ≠ integridad**; sin hash atestiguado → «LECTURA ANCLADA», nunca «contenido íntegro». Esta corrida no atribuye integridad de contenido a ningún artefacto publicado.

## §13 Manifiesto + SHA-256

- `MANIFEST_EJECUCION_RG_FLOW_HARDENED_6G1.json` — hashes SHA-256 de: informe, arnés, 9 archivos de evidencia y `SHA256SUMS_EJECUCION_RG_FLOW_HARDENED_6G1.txt`.
- `SHA256SUMS_EJECUCION_RG_FLOW_HARDENED_6G1.txt` — sumas de los anteriores (excluye el manifiesto mismo).

## §14 Declaraciones exigidas por la adjudicación

1. **No hubo modificaciones de producción** ni de motores H-EVO-MQR/DSP/FFT/STFT/ISTFT/máscaras/fórmulas/parámetros/reconstrucción.
2. Sin normalización/resampling/downmix/alineación/ganancias introducidas por el arnés; `--allow-misaligned` es configuración CLI documentada (§4) y no altera offsets/muestras/polaridad.
3. Sin audio real; fixtures 100 % sintéticos y aislados de archivos de producción.
4. Sin merge/cherry-pick/main; PR #2 sin tocar; sin Android/Termux.
5. **Esta ejecución NO es autorización de integración ni cierre de 6G.1.** La rama queda **DETENIDA** a la espera de adjudicación.
6. URLs: informe y compromiso hijo publicados en `origin/arena/f1c5739f-sdv-sdi-sgm` (hijo directo de `92b7c08`).

— Fin del informe. Parada obligatoria tras publicación.
