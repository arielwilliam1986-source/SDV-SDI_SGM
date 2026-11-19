# Etapa 6G.1 — Corrección de lectura segura del Mix y validación de evidencias

**Informe de implementación**

| Dato | Valor |
|---|---|
| Etapa | 6G.1 (corrección sobre 6G) |
| Base | `ee19fe208449249a20e194b09c9452b782c7de70` (cierre de 6G) |
| Rama | `arena/89d5c189-sdv-sdi-sgm` |
| Alcance | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/` exclusivamente |
| Canciones reales | ninguna |
| Integración con el piloto | ninguna |
| Cambios de parámetros históricos o por defecto | ninguno |

---

## 1. Motivo de la corrección

La entrega 6G quedó publicada y verificada, pero su diseño de lectura del Mix
tenía tres huecos:

1. **Reapertura por ruta.** Tras validar el Mix, los tres motores volvían a
   abrirlo con `sf.SoundFile(mix_info.path)`. Entre la validación y esa
   apertura la ruta puede apuntar a otro archivo; el DSP leería entonces un
   objeto no validado.
2. **Cierre previo a los chequeos posteriores.** El `hmix` se cerraba antes de
   las rutinas de identidad `post_wav_identity` y antes de la confirmación
   final, de modo que la comparación final se hacía por ruta (`_check_unchanged_6g`)
   y no sobre el descriptor efectivamente leído.
3. **Evidencia de la matriz.** La comparación WAV/FLAC de 6G declaraba
   equivalencia comparando diccionarios de PCM que podían estar **vacíos** y
   comparando `None == None` en informes ausentes. Eso no es una prueba de
   igualdad de PCM.

Además, la propia validación de 6G.1 descubrió un **defecto de evidencia de la
6G**: en todo archivo FLAC, `check_unchanged()` devolvía
`unchanged: false, reason: "identidad fstat distinta"` aunque nada hubiera
cambiado, porque `wav_integridad_6f._identity()` y
`audio_integridad_6g._identity()` describen la identidad con campos distintos
(`mode` sólo en la segunda). Se corrigió como parte de "integridad y validación
de evidencias".

---

## 2. Qué se implementó

### 2.1 Módulo nuevo `motores/lectura_segura_6g1.py` (192 líneas)

`MixHandle` mantiene **un único descriptor** del Mix durante toda la corrida:

* `os.open(path, O_RDONLY)` + `os.fstat` → identidad del objeto
  (`device`, `inode`, `size`, `mtime_ns`, `mode`).
* SHA-256 calculado **sobre el descriptor** (`os.fdopen(os.dup(fd))`), no sobre
  la ruta, y contrastado con el `sha256` del sondeo (`mix_info.sha256`).
  Si difieren: `MixCambiado("SHA-256 del Mix distinto del sondeo: sustitución
  antes del DSP")`.
* Lector `soundfile.SoundFile('/proc/self/fd/N')`: el decodificador lee **el
  mismo inodo** que se validó. Se delega el resto de la interfaz con
  `__getattr__`, de modo que el bucle DSP no cambia ni una línea.
* `verificar()`: relee el descriptor y compara `fstat` + SHA-256 con los de la
  apertura.
* `ruta_apunta_al_mismo_objeto()`: compara la identidad del objeto al que
  apunta hoy la **ruta** con la identidad del descriptor.
* `ruta_lectura()`: devuelve `/proc/self/fd/N` para las funciones que exigen un
  nombre de archivo (p. ej. `post_wav_identity`); no reabre la ruta del usuario.
* `close()` idempotente.
* `abortar_6g1(run_dir, motivo, detalle)`: invalida **sólo** las salidas de la
  corrida actual y escribe `ABORT_6G1.json`, anotando también `analysis.json`
  si existe. Regla de borrado conservadora: `<base> SDV.wav`,
  `<base> SDI.wav`, `SDV.wav`, `SDI.wav`, cualquier `*.wav` dentro de
  `candidates/`, y `*.png` cuyo nombre contenga `SDV`/`SDI`. Todo lo demás se
  **conserva** y se lista en `conservados` (archivos ajenos o preexistentes).

### 2.2 Motores (copias 6G.1, mismas funciones DSP)

| Motor | Cambios aplicados | Diff |
|---|---|---|
| `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | apertura única, cierre diferido, `post_wav_identity` sobre el descriptor, guarda final ampliada, `analyze_guide_scale` sobre el descriptor | +29 / −9 |
| `MOTOR_SEP_SDV-SDI_EVO.py` | idéntico | +29 / −9 |
| `sdv_sdi_mqr_engine.py` | idéntico + handle publicado en `ctx` (el bucle vive en `_run_core`) + `stream_level_stats` de la escala sobre el descriptor | +33 / −10 |

Patrón aplicado en los tres (indentación conservada del sitio original):

```python
try:
    hmix = _abrir_mix_6g1(mix_info.path, mix_info.sha256)
except _MixCambiado_6g1 as _exc6g1:
    _abortar_6g1(run_dir, "MIX_SUSTITUIDO_ANTES_DEL_DSP", str(_exc6g1))
    log("[FATAL] Mix sustituido antes del DSP: %s" % _exc6g1)
    close_tee()
    return EXIT_PROCESSING, None
```

y, al final del pipeline (tras `os.rename` al directorio definitivo y antes de
`input_integrity_6g.json`):

```python
ctx["container_6g"]["after"] = hmix.verificar()
ctx["container_6g"]["ruta_actual"] = hmix.ruta_apunta_al_mismo_objeto()
hmix.close()
...
if not (after.unchanged and ruta_actual.unchanged):
    _abortar_6g1(run_dir_final, "MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO", ...)
    return EXIT_PROCESSING, None
```

En MQR el `hmix` vive en `_run_core` y la guarda en `run_experiment`; el handle
se publica en `ctx["_mix_handle_6g1"]`, sin reordenar el pipeline.

`post_wav_identity(mix_path, ...)` conserva su firma y su lógica; lo único que
cambia es el argumento: recibe `hmix.ruta_lectura()`, es decir el mismo inodo ya
abierto y vigilado.

### 2.3 Corrección de evidencia de identidad (FLAC)

* `wav_integridad_6f.check_unchanged`: compara la identidad por
  `CLAVES_IDENTIDAD_6G1 = ('device', 'inode', 'size', 'mtime_ns')`; `mode`
  sigue en la evidencia (`before`/`after`) pero no en la comparación. Se añade
  `identidad_comparada_6g1` para auditoría.
* `audio_integridad_6g.check_file_unchanged`: misma normalización.
* Efecto: los FLAC dejan de producir un falso negativo `unchanged: false` en
  `alignment_analysis[*].integrity.mix_after`. Diff: +25 / −3 y +13 / −2.

La verificación WAV no se relaja: los cuatro campos comparados son los mismos
que ya usaba 6F para WAV.

### 2.4 Lo que **no** se tocó

* STFT/ISTFT, `n_fft`, `hop`, ventanas, ventaneo y OLA.
* Máscaras, fórmulas, consenso, `power`, `beta`, `epsilon`, suavizado.
* Reconstrucción, ganancias, polaridad, offsets de alineación.
* Parámetros DSP y valores por defecto de cualquier modo.
* Validación WAV de 6F (`verify_wave`), sin relajación alguna.
* Contenedores admitidos, conversión, remuestreo, downmix, normalización,
  ganancia, dither: nada de eso se añade ni se ejecuta.

Prueba 10 (huella DSP idéntica y PCM idéntico byte a byte frente a 6G en WAV y
FLAC) confirma lo anterior.

---

## 3. Hashes de fuentes

| Archivo | SHA-256 en 6G | SHA-256 en 6G.1 |
|---|---|---|
| `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | `29b30593d97733eb…` | `99ef34b9e2ef69f7…` |
| `MOTOR_SEP_SDV-SDI_EVO.py` | `87bf83651f8f237a…` | `8d9ed7804b6c82ef…` |
| `sdv_sdi_mqr_engine.py` | `f014cc0c71a00120…` | `a2767cbc90fe79db…` |
| `wav_integridad_6f.py` | `243ba66381f1e949…` | `3e03930e083fccbd…` |
| `audio_integridad_6g.py` | `cd5dd521de03cb40…` | `65bcc902a04b95b4…` |
| `atribucion_6f.py` | `dcc251e35d3c2222…` | `dcc251e35d3c2222…` (sin cambios) |
| `lectura_segura_6g1.py` | — (nuevo) | `a70a4782d953bb5e…` |

Las copias se tomaron byte a byte de `ETAPA_6G_SOPORTE_FLAC_MIX/motores/` y se
verificaron con SHA-256 antes de cualquier edición (script
`scripts/aplicar_cambios_6g1.py`). La carpeta 6G no se modificó: no aparece en
`git status` y sus 46 hashes siguen verificando.

---

## 4. Trazabilidad y reproducibilidad

* `scripts/preparar_fixtures_6g1.py` — fixtures sintéticos (Mix = suma de guía
  vocal + instrumental; WAV y FLAC con PCM idéntico; sustitutos válidos con otro
  PCM).
* `scripts/aplicar_cambios_6g1.py` — aplicación idempotente de los parches a las
  copias (documenta cada sitio y su indentación).
* `scripts/comun_6g1.py` — ejecución de motores, hashes PCM reales, vigía de
  sustitución (`patron` o `retraso`), siembra de archivos ajenos.
* `scripts/validar_contenedores_6g1.py` — pruebas 1, 2, 3, 8, 9.
* `scripts/sustituciones_6g1.py` — pruebas 4, 5, 6, 7 (incluye guarda unitaria
  determinista).
* `scripts/no_regresion_dsp_6g1.py` — prueba 10.
* `scripts/consolidar_6g1.py` — matriz global, `resumen_6g1.json`,
  `SHA256SUMS.txt` y `MANIFEST_6G1.json`.

Todo lo anterior vive dentro de `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`.

---

## 5. Limitaciones declaradas

1. **Ventana de carrera en la prueba 4b.** La sustitución se dispara al leer el
   log de la corrida; en las tres implementaciones el intervalo entre la última
   línea previa y la apertura del descriptor es de milisegundos, de modo que la
   sustitución puede aterrizar **después** de la apertura. Cuando ocurre así, el
   motor aborta igualmente por la guarda final (misma consecuencia: sin salidas)
   y la guarda previa queda demostrada por la prueba unitaria determinista
   (`abrir_mix` con `sha` validado y archivo sustituido → `MixCambiado`) y por la
   prueba 4c (sustitución durante la alineación → rechazo con `exit=1`).
2. **`Hardened` en `analysis_only`** aborta por un defecto **preexistente**
   (también en la copia 6G y en 6F): `write_reports` usa
   `ctx["post_wav_validation"]` nulo cuando `full_mode` es `False`. No se corrigió
   porque excede el alcance (no es lectura, ni integridad, ni aborto). Los casos
   afectados se marcan `NOT_EXECUTED`.
3. **Limpieza del aborto.** `abortar_6g1` borra sólo nombres que el motor escribe
   en esa corrida. Un archivo ajeno con exactamente el mismo nombre
   (`SDV.wav`) dentro del directorio de una corrida sería tratado como salida
   propia; el directorio de corrida lo crea el motor, vacío, en cada ejecución.
4. Los tiempos y el consumo de memoria del informe de validación son los
   observados en este entorno, no una promesa de rendimiento.
5. No se ejecutó ninguna canción real, ni el piloto, ni comparación de calidad
   subjetiva: fuera de alcance por instrucción.
