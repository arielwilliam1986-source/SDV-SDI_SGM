# INFORME DE CORRECCIONES DE AUDITORÍA — ETAPA 6G.1

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**Commit auditado**: `015e2f8e2b215c1d4dc5b9360988b42063e28533` (tip de `arena/89d5c189-sdv-sdi-sgm`, «Etapa 6G.1: lectura del Mix desde un único descriptor vigilado y aborto seguro»)
**Alcance**: exclusivamente los cuatro hallazgos de la auditoría estática independiente de 6G.1 (correcciones A, B, C y D). No se rehizo la etapa ni se introdujo mejora alguna ajena a ellos.

> **Estado**: la corrección está ENTREGADA, **no cerrada**. La aprobación final corresponde a Cris después de revisar el código y las evidencias.

---

## 0. Dónde está publicado y por qué

La corrección se publica en la **rama de sesión autorizada** `arena/441a4bf8-sdv-sdi-sgm`, como copia íntegra del contenido del commit auditado con las correcciones aplicadas (carpeta `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`, mismo nombre de ruta). Alternativa de la instrucción («rama hija basada exactamente en el commit auditado») **no disponible en este entorno**: la plataforma de sesión no permite crear ramas ni pushear a ramas ajenas. Se entregan además:

- `DIFF_6G1_AUDITADO_A_CORRECCION.patch` (incluye este informe; la longitud exacta es la del propio archivo): diff completo `015e2f8 → corrección`, **reversible verificado** — `patch -R -p1` sobre el árbol corregido devuelve el árbol del commit auditado **byte a byte** (`diff -r` sin diferencias). Este parche permite aplicar la corrección sobre la rama de referencia con `git apply`/`patch` si Cris lo prefiere.
- `SHA256SUMS_CORRECCION.txt`: SHA-256 nuevo de cada archivo modificado/añadido, con el SHA-256 auditado previo en comentario.

**La rama de referencia `arena/89d5c189-sdv-sdi-sgm` NO fue tocada** (sólo lectura). Tampoco `main`, 6G, ni los motores originales. Sin merges, sin PR.

**Limpieza**: los `__pycache__` generados por compilación de verificación fueron eliminados de la carpeta antes de publicar.

---

## 1. Corrección A — Guarda final fail-closed (los tres motores)

**Hallazgo corregido**: la guarda final se ejecutaba **después de publicar** (`os.rename(run_dir, run_dir_final)` primero) y, ante cualquier excepción de `hmix.verificar()` o de la comprobación de ruta, caía a un **fallback** que reabría el Mix por su ruta (`_check_unchanged_6g(mix_path, ...)`) y además asignaba manualmente `ctx["container_6g"]["ruta_actual"] = dict(unchanged=True)` — aprobación fabricada sin evidencia de ruta. El cierre del descriptor quedaba dentro del `try` (una excepción en la ruta lo saltaba).

**Cambios** (regiones exactas):
- `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` y `MOTOR_SEP_SDV-SDI_EVO.py`: bloque de guarda reubicado **antes** de la publicación, reescrito fail-closed:
  - `verificar()` + `ruta_apunta_al_mismo_objeto()` en `try`; cualquier excepción registra `unchanged=False` con el motivo de la excepción en **ambos** componentes;
  - `hmix.close()` en `finally` (cierre garantizado incluso con verificación fallida);
  - **eliminado por completo** el fallback `_check_unchanged_6g` (también del `import` de `audio_integridad_6g`: 0 usos restantes en los tres motores);
  - **ninguna** asignación manual de `unchanged=True`;
  - en el camino de aborto se cierran además los lectores de guías (`handles`) antes de retornar `EXIT_PROCESSING`.
- `sdv_sdi_mqr_engine.py`: la guarda vivía en `main` **después** de que `_run_core` ya había publicado por renombrado. Se movió a `_run_core`, inmediatamente **antes** de la transacción de publicación, con la misma estructura fail-closed; `main` ya no contiene ninguna verificación ni fallback (sólo registra el éxito), y un nuevo `except _VerifFallida_6g1` retorna `EXIT_PROCESSING` **sin renombrar ni publicar**.

**Regla aplicada**: `VERIFICACIÓN INCIERTA = ABORTO` (excepción o veredicto no satisfactorio → aborto sobre el directorio provisional, sin publicación).

## 2. Corrección B — Orden de publicación (los tres motores)

**Hallazgo corregido**: podía existir un directorio definitivo con resultados que no habían superado la guarda final (la guarda corría sobre `run_dir_final` y el aborto limpiaba sobre lo ya publicado).

**Secuencia implementada** (idéntica en los tres motores):
1. Procesamiento y escritura en el directorio provisional (`*_partial`, creado vacío por `create_run_dir`; nombres definitivos `motorA_run_<stamp>` / `mqr_run_<stamp>`);
2. Verificación final del descriptor y de la ruta (corrección A);
3. Escritura **y comprobación** de la evidencia de integridad: `input_integrity_6g.json` se escribe en el provisional, se relee y se valida sintácticamente; si la escritura o la comprobación fallan, la verificación se considera no superada (fail-closed);
4. Publicación mediante renombrado al directorio definitivo, **sólo tras guarda superada** (con el sufijo anti-colisión horario ya existente);
5. Registro de éxito en el log.

Si la verificación falla: `abortar_6g1` sobre el provisional, `ABORT_6G1.json` dentro de él, **ningún directorio definitivo creado** (verificado por T4/T5).

## 3. Corrección C — Propiedad de archivos durante el aborto (`lectura_segura_6g1.py`)

**Hallazgo corregido**: `abortar_6g1` borraba por **patrón de nombre/ubicación** (`_es_salida_de_la_corrida`: sufijos ` SDV.wav`/` SDI.wav`, cualquier WAV en `candidates/`, PNG con SDV/SDI) — el propio `INFORME_IMPLEMENTACION_6G1.md` documentaba la limitación (un ajeno llamado `SDV.wav` dentro del directorio de corrida sería tratado como propio).

**Nuevo mecanismo** (el patrón de nombre fue **eliminado**; no hay decisión de borrado por nombre ni por ubicación):
- **Registro de propiedad**: `registrar_propio_6g1(path, estable)` — el motor registra cada archivo que crea:
  - `estable=True` (archivos finalizados: `analysis.json`, `analysis.txt`, `input_integrity_6g.json`): sello de dispositivo/inodo/tamaño/mtime_ns/**SHA-256**;
  - `estable=False` (archivos en curso: writers WAV de SDV/SDI —incluidos los de `candidates/`— y memmaps de máscaras vía `_open_memmap`): identidad por dispositivo/**inodo** (el contenido crece legítimamente mientras el motor escribe).
  - Si el archivo no puede observarse al registrar, **no** se registra (y por tanto se conservará): fail-closed sin interrumpir al motor.
- **Dictamen de propiedad** (`propiedad_de_6g1`): `ajeno_no_registrado` → conserva; inodo distinto del registrado (sustituido tras su creación, p. ej. por `os.replace`) → conserva (`identidad_distinta`); archivo sellado con tamaño/mtime/SHA-256 distintos → conserva (`modificado`); identidad acreditada → elimina.
- **`abortar_6g1`** (schema `abort-6g1/2`): sólo elimina con propiedad acreditada; conserva y lista todo lo demás con motivo (`motivos_propiedad`); los archivos de registro forense (`ABORT_6G1.json`, `engine_log.txt`, `analysis.json`, `input_integrity_6g.json`) se conservan siempre; el embedding del aborto en `analysis.json` se mantiene.
- Puntos de registro añadidos en los tres motores: creación de writers SDV/SDI (Hardened/EVO/MQR, incluidos subdirectorios `candidates/`), `_open_memmap` (máscaras), `write_reports` (analysis.json + analysis.txt), escritura de `input_integrity_6g.json`.

**Limitación documentada** (fail-closed honesto): para archivos **en curso** la propiedad se acredita por ruta registrada + continuidad de inodo; una modificación *in situ* del mismo inodo mientras el motor escribe no es detectable sin sello de contenido (el sello SHA-256 existe sólo para archivos finalizados). Los casos de la instrucción quedan cubiertos: el ajeno no registrado se conserva (UC1–UC3) y el propio sustituido por inodo distinto se conserva (UC5, T6).

## 4. Corrección D — Evidencia y documentación

**4.1 Discrepancia `informe_igual: false` vs «igual|igual»** — resuelta por diagnóstico empírico (nuevo procedimiento en `scripts/no_regresion_dsp_6g1.py` que registra campo por campo lo que difiere, `campos_diferentes_estricto`):
- **Motivo real**: los informes normalizados de 6G y 6G.1 difieren **exclusivamente** en campos del bloque `integrity` de la alineación: el campo nuevo `identidad_comparada_6g1` (6G.1 corrige la comparación por claves de objeto en `wav_integridad_6f`/`audio_integridad_6g`, índice de auditoría: +25/−3 y +13/−2) y el detalle de `mix_after` en FLAC (6G.1 elimina el falso negativo FLAC de 6G). **Ningún campo de cálculo DSP difiere.**
- **Resolución**: la igualdad **no se fabrica**. `informe_igual` (6G vs 6G.1) queda False por diseño correcto; la tabla §3 de `NO_REGRESION_DSP_6G1.md` («`analysis.json` normalizado | igual | igual») fue **rectificada** (§1.4 y §6 nuevas, con marcador `[6G.1-R]`); `VOLATILES_ADICIONALES` quedó **vacío** (no se excluyó campo alguno más allá del conjunto histórico); el JSON registra `volatiles`, `volatiles_adicionales`, `informe_igual_estricto` y las rutas exactas que difieren, para los seis casos.
- **Falso positivo de la huella DSP corregido**: al reubicar la evidencia de integridad, el literal `indent=2` del `json.dump` se movió entre funciones y la huella marcaba `numeros_iguales: false` sin cambio DSP alguno (detectado en la primera corrida: `run_experiment` [1.0, 2.0]→[1.0] y `_run_core` +2.0 — únicamente el `2.0` de formato). El procedimiento excluye ahora, de forma **simétrica para 6G y 6G.1**, los valores del argumento `indent` de serialización JSON (parámetro de formato, no DSP), con el conteo excluido registrado (`huellas[*].indent_excluidos_6g/6g1` = 2 por motor). Ninguna otra numeración cambió (verificado por conjuntos: único delta = 2.0).

**4.2 Afirmación de estabilidad de la prueba 8** — precisada en `INFORME_VALIDACION_6G1.md` §4.2 (`[6G.1-R]`): dos hashes consecutivos acreditan la consistencia de lectura/escritura **en ese instante**, no estabilidad frente a modificaciones concurrentes; la estabilidad del Mix durante el procesamiento principal la acredita la **guarda final sobre el descriptor vigilado**; las lecturas auxiliares de análisis (p. ej. `post_wav_identity` sobre salidas ya escritas) abren sus **propios lectores** sobre archivos del directorio de corrida y no reabren el Mix por su ruta.

**4.3 Salvedad de limpieza (§3 de `INFORME_IMPLEMENTACION_6G1.md`)** — el documento señalaba la limitación como abierta; se añadió nota `[6G.1-R]`: **resuelta** por la corrección C, con referencia a este informe.

## 5. Pruebas obligatorias y resultados individuales

Entorno de ejecución (reproducibilidad): **CPython 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64, 2 CPU** — idéntico al entorno registrado de la campaña auditada. Fixtures: los del commit auditado, **intactos** (12/12 SHA-256 idénticos al commit; nunca se regeneraron ni modificaron). Los Mix sustituibles se copian a `/tmp`; el repositorio nunca se tocó. Variables de un solo hilo (`OMP/OPENBLAS/MKL_NUM_THREADS=1`, del harness existente).

**Resultados: 34/34 PASS, 0 FAIL, 0 NOT_EXECUTED** (`evidence/matriz_correccion_6g1.csv`, detalle completo por check en `evidence/pruebas_correccion_6g1.json`):

| Grupo | Pruebas | Resultado |
|---|---|---|
| Unidad de propiedad y limpieza (corrección C) | UC1 ajeno en `candidates/`; UC2 ajeno `SDV.wav`; UC3 ajeno con nombre exacto de salida; UC4 propio acreditado eliminado; UC5 propio sustituido tras creación → conservado (`identidad_distinta`); UC6 propio en curso (inodo continuo) eliminado; UC7 propio sellado modificado in situ → conservado | 7/7 PASS |
| Hardened | T1 excepción `verificar()`; T2 excepción de ruta; T3 sustitución del Mix durante el DSP (`chunk 10/`, `--chunk-frames 48`, sustituto FLAC válido `mix_otro.flac`, guías 12 s — mismas técnicas de la campaña auditada); T4 verificación fallida sin excepción; T5 ausencia de directorio definitivo tras T1–T4; T6 colisiones (ajeno `SDV.wav`, `candidates/ajeno_cand.wav`, suelto; **reemplazo por `os.replace` de la salida propia ya cerrada** → conservado); T7 eliminación de propias acreditadas con motivos; T8 WAV + FLAC | 9/9 PASS |
| EVO | ídem Hardened | 9/9 PASS |
| MQR | ídem | 9/9 PASS |

Cada prueba de aborto verifica **más que el código de salida** (como exige la instrucción): exit=2, `ABORT_6G1.json` presente con `schema=abort-6g1/2` y motivo `MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO`, salidas propias eliminadas y acreditadas en `salidas_invalidadas`, ajenos conservados con `motivos_propiedad=ajeno_no_registrado`, salida propia reemplazada conservada con `identidad_distinta`, **ningún directorio definitivo** creado, y `input_integrity_6g.json` en el provisional con los componentes negativos esperados (T3: `after=True` legítimo —el descriptor retiene el contenido original— y `ruta=False`; T4: `after=False` con `ruta=True` legítima).

**No repetido**: ninguna campaña histórica cerrada (S5, 6B–6G) fue re-ejecutada; las pruebas 1–10 originales de 6G.1 no se volvieron a correr (sus evidencias de `evidence/` permanecen intactas, salvo `no_regresion_dsp_6g1.{json,csv}` regeneradas por el procedimiento corregido D — el diff registra exactamente qué cambió).

**Casos `NOT_EXECUTED` preservados**: los cuatro casos de Hardened `analysis_only` (defecto preexistente de 6F/6G: `AttributeError` en `write_reports`) **no fueron tocados ni convertidos en aprobados**; siguen documentados en `INFORME_VALIDACION_6G1.md` §7.1 y ninguna prueba de esta corrección los altera.

## 6. No-regresión DSP tras la corrección (confirmación expresa de DSP intacto)

Tres evidencias independientes:

1. **Huella AST + PCM vs 6G** (procedimiento corregido, corrida completa en entorno con la carpeta 6G del commit auditado): **3 motores `ACCEPTED`** — definiciones cambiadas sólo en las regiones de lectura/guarda/registro; sin constantes cambiadas; huella DSP idéntica (numerales y llamadas DSP, excluido `indent` registrado); **PCM WAV y FLAC idénticos byte a byte frente a las copias 6G**.
2. **PCM idéntico a la campaña auditada**: las corridas T8 de esta corrección reproducen los `pcm_sha256` almacenados en `evidence/contenedores_6g1.json` del commit auditado, por motor y contenedor (p. ej. Hardened WAV: `mix SDV.wav` = `a347838da989c364…`, `mix SDI.wav` = `368d3ecbc3a07d05…`; equivalencia WAV=FLAC también en EVO y MQR). Mismo PCM ⇒ DSP intacto.
3. **Afirmación expresa**: **el DSP permanece intacto.** No se modificó STFT, ISTFT, FFT, hop, chunking, máscaras, fórmulas, consenso, ganancias, polaridad ni parámetro DSP alguno; los cambios se limitan a lectura/guarda, orden de publicación, registro de propiedad/aborto, procedimiento de comparación de evidencia y documentación. Los archivos modificados y sus identidades están en `SHA256SUMS_CORRECCION.txt` (con SHA auditado previo).

## 7. Superficie de cambio (numstat vs commit auditado)

| Archivo | Cambio |
|---|---|
| `motores/lectura_segura_6g1.py` | +109/−29 (registro de propiedad, dictamen, aborto acreditado; `MixHandle` intacto) |
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | +50/−19 |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | +50/−19 |
| `motores/sdv_sdi_mqr_engine.py` | +66/−31 |
| `scripts/no_regresion_dsp_6g1.py` | +76/−3 (procedimiento D) |
| `scripts/pruebas_correccion_6g1.py` | NUEVO (568 L; batería obligatoria) |
| `scripts/inyeccion_6g1/sitecustomize.py` | NUEVO (37 L; inyector T1/T2/T4, sólo por variable de entorno) |
| `evidence/no_regresion_dsp_6g1.{json,csv}` | regenerados por el procedimiento corregido (+301/−22 y +4/−4) |
| `evidence/pruebas_correccion_6g1.json`, `evidence/matriz_correccion_6g1.csv` | NUEVOS (resultados individuales y matriz) |
| `NO_REGRESION_DSP_6G1.md`, `INFORME_VALIDACION_6G1.md`, `INFORME_IMPLEMENTACION_6G1.md` | +47/−3, +11/0, +10/0 (rectificaciones `[6G.1-R]`) |
| `DIFF_6G1_AUDITADO_A_CORRECCION.patch`, `SHA256SUMS_CORRECCION.txt`, este informe | NUEVOS (entregables) |
| **Total (sin este informe ni los dos entregables auto-referentes)** | **+2.848/−130** |

Fixtures: 12/12 idénticos al commit auditado (nunca tocados). `evidence/` histórico (matriz_global, contenedores, sustituciones, resumen, MANIFEST, SHA256SUMS) intacto.

## 8. Límites respetados

Solo los hallazgos auditados; sin mejoras ajenas. Sin tocar STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP (verificado por huella). Motores originales intactos; 6G intacto; `main` intacto; sin fusionar ramas ni abrir PR; sin ejecutar Elis/Tristania ni audio real; sin Android/Termux; campañas históricas cerradas no repetidas; los cuatro `NOT_EXECUTED` de Hardened `analysis_only` siguen identificados. **No se declara 6G.1 cerrada**: la aprobación final corresponde a Cris tras revisar el código y las evidencias.
