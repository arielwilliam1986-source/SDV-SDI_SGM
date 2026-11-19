# Etapa 6G · Informe de validación

Todo lo siguiente se **ejecutó** en esta sesión. Lo no ejecutado se marca al
final como `NOT_EXECUTED`. Evidencia en `evidence/`.

Corpus sintético: `fixtures/` (16 archivos, 1 s, 44 100 Hz, estéreo, PCM_16 y
PCM_24, más variantes inválidas), generado por `scripts/preparar_fixtures_6g.py`
a partir de las **mismas muestras** para WAV y FLAC.

## 1. Contenedores: 52/52

`scripts/validar_contenedores_6g.py` — 15.5 s, RSS 41 348 KiB.
Matriz: `evidence/matriz_contenedores_6g.csv`; JSON: `contenedores_6g.json`.

| Caso | Esperado módulo | Esperado motor | Módulo | 3 motores |
|---|---|---|---|---|
| WAV válido (PCM_16) | ACEPTA | ACEPTA | ✔ | ✔ |
| FLAC válido (PCM_16) | ACEPTA | ACEPTA | ✔ | ✔ |
| WAV PCM_24 | ACEPTA | ACEPTA | ✔ | ✔ |
| FLAC PCM_24 | ACEPTA | ACEPTA | ✔ | ✔ |
| WAV renombrado `.flac` | RECHAZA | RECHAZA | ✔ | ✔ |
| FLAC renombrado `.wav` | RECHAZA | RECHAZA | ✔ | ✔ |
| FLAC truncado | RECHAZA | RECHAZA | ✔ | ✔ |
| FLAC con frames alterados | RECHAZA | RECHAZA | ✔ | ✔ |
| FLAC sólo metadatos | RECHAZA | RECHAZA | ✔ | ✔ |
| FLAC 48 kHz | ACEPTA | RECHAZA | ✔ | ✔ |
| FLAC 3 canales | ACEPTA | RECHAZA | ✔ | ✔ |
| WAV float con NaN | RECHAZA | RECHAZA | ✔ | ✔ |
| Contenedor OGG con extensión `.flac` | RECHAZA | RECHAZA | ✔ | ✔ |

**Módulo 13/13, Hardened 13/13, EVO 13/13, MQR 13/13.**

Nota metodológica: 48 kHz y 3 canales se aceptan en la capa de contenedor porque
el archivo FLAC es válido; el rechazo corresponde a la política del motor
(tasa 44 100 Hz y 1–2 canales). Por eso las expectativas se registran por capa.
En todas las filas de rechazo se comprobó además **0 WAV y 0 informes**.

## 2. Motores: 12/12 combinaciones idénticas

`scripts/validar_motores_6g.py` — 17.8 s, RSS 41 216 KiB.
Matriz: `evidence/matriz_motores_6g.csv`; JSON: `motores_6g.json`.

3 motores × 4 modos (`dry_run`, `analysis_only`, modo de un solo par
—`single_pair`/`single_file`—, `full_processing`) × 2 contenedores.

Para cada combinación motor×modo se comparó WAV vs FLAC:

| Comprobación | Resultado |
|---|---|
| PCM de salida SDV y SDI (SHA-256 de float64) | idéntico en 12/12 |
| Geometría de salida (frames, canales, tasa) | idéntica en 12/12 |
| Código de salida y número de WAV | idéntico en 12/12 |
| Atribución y retardo estimado | idéntico en 12/12 |
| Informe completo (sin metadatos volátiles) | idéntico en 12/12 |

Normalización aplicada al informe: se descartan `document_meta`,
`mix_original`, inventarios de guías e `input_integrity`, y el bloque
`alignment.integrity` se reduce a `same_descriptor_read` + banderas
`unchanged`, porque contiene inodo, tamaño, SHA-256 y campos de formato que
**deben** diferir entre un WAV y un FLAC. Ninguna sección DSP se descartó.

Condiciones de entrada verificadas:
* `numpy.array_equal` entre las muestras decodificadas de `mix.wav` y
  `mix.flac`: **True**, misma tasa.
* SHA-256 de todos los fixtures antes y después de la matriz: **sin cambios**
  (el motor no modifica el archivo original).

## 3. Sustitución entre validación y lectura (TOCTOU)

`scripts/toctou_6g.py` — 0.38 s. Evidencia: `evidence/toctou_6g.json`.

| Prueba | Resultado |
|---|---|
| `open_audio` y luego reemplazo de la ruta | las muestras leídas siguen siendo las validadas; `check_file_unchanged` detecta el cambio (`identidad fstat distinta`) |
| Hardened con el Mix sustituido justo después del sondeo | exit 1, **0 WAV, 0 informes** |
| EVO, idem | exit 1, 0 WAV, 0 informes |
| MQR, idem | exit 1, 0 WAV, 0 informes |

En los tres motores la sustitución se detectó en la etapa de alineación
(SHA-256 del descriptor distinto del sondeo, `READ_OR_FORMAT_ERROR`) y no por la
guarda final, que es la segunda línea de defensa. Se documenta tal cual: el
aborto ocurrió antes de llegar a la comprobación de cierre.

## 4. Muestras no finitas

* WAV `FLOAT` con NaN: rechazado por el validador (`Muestras no finitas en el
  payload float`) y por los tres motores.
* FLAC: **no aplicable**; FLAC almacena enteros y no puede representar NaN. No
  se inventó un caso artificial.

## 5. Recursos

| Prueba | Duración | RSS máx. |
|---|---|---|
| Contenedores (52 filas) | 15.5 s | 41 348 KiB |
| Motores (24 corridas) | 17.8 s | 41 216 KiB |
| TOCTOU (4 pruebas) | 0.38 s | — |

Entorno: Linux x86_64, 2 vCPU, Python 3.11.2, numpy 1.26.4, scipy 1.13.1,
soundfile 0.13.1, libsndfile 1.2.2, hilos BLAS/OpenMP = 1. Mediciones de Arena;
no se extrapolan a Termux ARM64.

## 6. No ejecutado

* `NOT_EXECUTED`: procesamiento de canciones reales o del piloto (prohibido).
* `NOT_EXECUTED`: archivos > 2 GB, FLAC 32 bits, FLAC sin MD5, más de 2 canales
  en procesamiento real.
* `NOT_EXECUTED`: sustitución *durante* la decodificación de un archivo enorme
  (la ventana de lectura sería mayor); sólo se probó sustitución entre sondeo y
  lectura.
* `NOT_EXECUTED`: modos y flags no listados (residuales, `--mask-mode
  per_channel`, presets alternativos).
* `UNKNOWN`: comportamiento con `/proc` no disponible (el código falla con error
  explícito, pero no se probó en ese entorno).
