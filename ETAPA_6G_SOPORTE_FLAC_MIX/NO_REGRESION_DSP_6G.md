# Etapa 6G · No regresión DSP

Evidencia: `evidence/no_regresion_6g.json`, `evidence/matriz_no_regresion_6g.csv`,
`evidence/diffs_6g.md`. Script: `scripts/no_regresion_dsp_6g.py` (5.1 s,
RSS 53 944 KiB).

## 1. Estructura (AST)

Comparación definición por definición y constante por constante entre cada
fuente 6F y su copia 6G:

| Motor | Definiciones cambiadas | Añadidas | Quitadas | Constantes cambiadas | Defs idénticas |
|---|---|---|---|---|---|
| Hardened | `probe_file`, `run_experiment` | — | — | — | 61 |
| EVO | `probe_file`, `run_experiment` | — | — | — | 64 |
| MQR | `probe_file`, `run_experiment` | — | — | `MIX_ALLOWED_EXTENSIONS` | — |
| `atribucion_6f.py` | ninguna definición | — | — | — | todas |

* `probe_file` cambia en una línea: `verify_wave(...)` → `verify_audio(...)`
  (validación de contenedor).
* `run_experiment` cambia por dos inserciones: el bloque `ctx["container_6g"]`
  tras la validación de entradas y la guarda de cierre antes del retorno. No se
  alteró ninguna línea de procesamiento.
* `MIX_ALLOWED_EXTENSIONS` es política de contenedor, no parámetro DSP.

Ninguna función de STFT/ISTFT, ventanas, FFT/hop, máscaras, consenso, potencia,
epsilon, suavizado, reconstrucción, chunking, alineación ni atribución aparece
entre las cambiadas. `wav_integridad_6f.py` es copia byte a byte (SHA-256
idéntico al de 6F).

## 2. Muestras

Mismo Mix WAV procesado por la fuente 6F y por la copia 6G, en cada motor,
`full_processing`:

| Motor | PCM 6F vs 6G | Geometría | Informe |
|---|---|---|---|
| Hardened | **idéntico** | idéntica | idéntico |
| EVO | **idéntico** | idéntica | idéntico |
| MQR | **idéntico** | idéntica | idéntico |

Comparación por SHA-256 de las muestras decodificadas a float64 y por forma de
cada WAV de salida (SDV y SDI). "Informe idéntico" se evalúa tras descartar
`document_meta`, `mix_original`, inventarios de guías, `input_integrity` y las
secciones de integridad que contienen rutas o hashes.

## 3. Diff reproducible

`evidence/diffs_6g.md` contiene el diff unificado completo:

| Archivo | Líneas |
|---|---|
| Hardened | +26 / −1 |
| EVO | +26 / −1 |
| MQR | +27 / −2 |
| `atribucion_6f.py` | +2 / −2 |

Se puede regenerar con `python -B scripts/consolidar_6g.py`.

## 4. Límites de esta prueba

* Las comparaciones usan un fixture sintético de 1 s en `full_processing`; no se
  recorrió la matriz completa de flags ni audio largo.
* La igualdad de PCM es de extremo a extremo; no se instrumentaron tensores
  intermedios de la STFT ni máscaras.
* El informe se compara tras normalizar metadatos volátiles; la lista exacta de
  claves descartadas está en el script y en el JSON de evidencia.
* No se comparó contra el motor v3 original ni contra 6C/6E en esta etapa (el
  trabajo previo de 6F ya cubrió esa cadena).
