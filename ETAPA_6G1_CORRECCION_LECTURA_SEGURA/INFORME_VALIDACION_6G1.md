# Etapa 6G.1 — Informe de validación

Todas las cifras de este informe provienen de ejecuciones reales registradas en
`evidence/`. Nada está proyectado ni estimado. Lo que no se ejecutó figura como
`NOT_EXECUTED` con su motivo.

* Base: `ee19fe208449249a20e194b09c9452b782c7de70`.
* Entorno: Python 3.11, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1,
  libsndfile 1.2.2, Linux x86_64.
* Fixtures: sintéticos, generados por `scripts/preparar_fixtures_6g1.py`
  (11 archivos, hashes en `fixtures/fixtures_manifest.json`).

---

## 1. Reglas de veredicto (corrección del defecto de la matriz 6G)

La matriz 6G podía declarar equivalencia comparando diccionarios de PCM vacíos
o `None == None` en informes ausentes. Aquí se aplica un enum explícito y una
condición material:

| Veredicto | Significado |
|---|---|
| `ACCEPTED` | La prueba se ejecutó y su condición se cumplió. |
| `REJECTED` | La prueba se ejecutó y su condición falló. |
| `PCM_IDENTICAL` | Existen archivos PCM **reales** (leídos, finitos, con `frames > 0`, `bytes > 0`), con hash calculado, y sus hashes coinciden. |
| `PCM_DIFFERENT` | Existen archivos PCM reales y sus hashes no coinciden. |
| `NOT_APPLICABLE` | El modo no produce la magnitud medida (p. ej. `dry_run` no escribe PCM). No se usa como sinónimo de éxito. |
| `NOT_EXECUTED` | No se pudo ejecutar; se documenta el motivo. |

`_pcm_real()` exige que **todos** los archivos de la lista tengan
`pcm_sha256`, `finite is True`, `frames > 0` y `bytes > 0`; una lista vacía
nunca produce `PCM_IDENTICAL`.

Separación de niveles, tal como se pidió:

* **Validación** → `dry_run` (validación de entradas y plan).
* **Análisis** → `analysis_only` (alineación, máscaras, informes).
* **Procesamiento efectivo** → `full_processing` (WAV SDV/SDI reales).

---

## 2. Resumen global

64 filas en `evidence/matriz_global_6g1.csv`.

| Veredicto | Filas |
|---|---|
| `ACCEPTED` | 46 |
| `PCM_IDENTICAL` | 6 |
| `NOT_APPLICABLE` | 8 |
| `NOT_EXECUTED` | 4 |
| `REJECTED` | 0 |

| Prueba | Resultado |
|---|---|
| 1 — WAV válido aceptado | 8 `ACCEPTED`, 1 `NOT_EXECUTED` |
| 2 — FLAC válido aceptado | 8 `ACCEPTED`, 1 `NOT_EXECUTED` |
| 3 — WAV/FLAC equivalentes (PCM) | 3 `PCM_IDENTICAL`, 5 `NOT_APPLICABLE`, 1 `NOT_EXECUTED` |
| 4 — sustitución antes del DSP | 7 `ACCEPTED` |
| 5 — sustitución durante el DSP | 3 `ACCEPTED` |
| 6 — sustitución después del DSP | 3 `ACCEPTED` |
| 7 — sin salidas válidas tras abortar | 6 `ACCEPTED` |
| 8 — hashes de PCM reales | 6 `ACCEPTED` |
| 9 — WAV/FLAC: alineación, máscaras, SDV, SDI | 3 `PCM_IDENTICAL`, 2 `ACCEPTED`, 3 `NOT_APPLICABLE`, 1 `NOT_EXECUTED` |
| 10 — no regresión DSP | 3 `ACCEPTED` |

---

## 3. Pruebas 1 y 2 — validez de contenedores

Motores × contendores × modos (18 combinaciones). Se acepta sólo si
`exit == 0`, sin `ABORT_6G1.json` y, en modos con informe, con
`input_integrity_6g.json` que declare `after.unchanged = true` **y**
`ruta_actual.unchanged = true`.

| Motor | Modo | WAV | FLAC | Integridad |
|---|---|---|---|---|
| Hardened | `dry_run` | ACCEPTED | ACCEPTED | validación y plan OK (sin PCM por diseño) |
| Hardened | `analysis_only` | NOT_EXECUTED | NOT_EXECUTED | defecto preexistente (ver §7) |
| Hardened | `full_processing` | ACCEPTED | ACCEPTED | `after`/`ruta_actual` = true |
| EVO | `dry_run` | ACCEPTED | ACCEPTED | ídem |
| EVO | `analysis_only` | ACCEPTED | ACCEPTED | `after`/`ruta_actual` = true |
| EVO | `full_processing` | ACCEPTED | ACCEPTED | `after`/`ruta_actual` = true |
| MQR | `dry_run` | ACCEPTED | ACCEPTED | ídem |
| MQR | `analysis_only` | ACCEPTED | ACCEPTED | `after`/`ruta_actual` = true |
| MQR | `full_processing` | ACCEPTED | ACCEPTED | `after`/`ruta_actual` = true |

`ruta_actual` es nuevo en 6G.1: además de que el contenido del descriptor no
cambió, se comprueba que la **ruta** sigue apuntando al mismo inodo que el
descriptor vigilado.

---

## 4. Pruebas 3, 8 y 9 — equivalencia WAV/FLAC con PCM real

### 4.1 Prueba 3 — igualdad de PCM de salida

| Motor | Modo | Veredicto | Evidencia |
|---|---|---|---|
| Hardened | `dry_run` | NOT_APPLICABLE | el modo no escribe PCM |
| Hardened | `analysis_only` | NOT_EXECUTED | defecto preexistente |
| Hardened | `full_processing` | **PCM_IDENTICAL** | `mix SDV.wav`, `mix SDI.wav` reales en ambos contenedores |
| EVO | `dry_run` | NOT_APPLICABLE | ídem |
| EVO | `analysis_only` | NOT_APPLICABLE | ídem |
| EVO | `full_processing` | **PCM_IDENTICAL** | `mix SDV.wav`, `mix SDI.wav` |
| MQR | `dry_run` | NOT_APPLICABLE | ídem |
| MQR | `analysis_only` | NOT_APPLICABLE | ídem |
| MQR | `full_processing` | **PCM_IDENTICAL** | `SDV.wav`, `SDI.wav` |

El hash es SHA-256 sobre el PCM decodificado en `float64` little-endian
(`x.astype('<f8').tobytes()`), previa lectura con `soundfile`. No se comparan
nombres ni tamaños: se compara contenido.

### 4.2 Prueba 8 — verificación de hashes sobre archivos reales

Seis casos (`3 motores × 2 contenedores`, `full_processing`): **6/6
`ACCEPTED`**. Para cada salida se calculó SHA-256 del archivo dos veces
(recomputación independiente) y coincidió; el PCM se verificó finito, con
`frames > 0` y `bytes > 0`. Los hashes por salida están en
`evidence/contenedores_6g1.json` (`casos[*].pcm`).

> **[6G.1-R, corrección D — precisión sobre la "estabilidad"]**: dos hashes
> consecutivos del mismo archivo acreditan la **consistencia de la lectura y
> escritura en ese instante**, no estabilidad frente a modificaciones
> concurrentes posteriores. La estabilidad del **Mix durante el procesamiento
> principal** se acredita por la guarda final sobre el **descriptor vigilado**
> (`verificar()` + `ruta_apunta_al_mismo_objeto()`), que revalida contenido e
> identidad al término del DSP. Las **lecturas auxiliares de análisis** (p. ej.
> `post_wav_identity` sobre las salidas ya escritas) abren sus **propios
> lectores** sobre archivos del directorio de corrida; no reabren el Mix por su
> ruta.

### 4.3 Prueba 9 — alineación, máscaras, SDV y SDI

Comparación del informe completo (`analysis.json`) entre la corrida WAV y la
corrida FLAC del mismo motor y modo, descartando sólo metadatos volátiles por
archivo (`document_meta`, `mix_original`, inventarios de guías, `input_integrity`,
`post_wav_validation`, `container_6g`) y reduciendo `integrity` a sus banderas
`unchanged`/`reason`.

| Motor | Modo | Veredicto | Detalle |
|---|---|---|---|
| Hardened | `full_processing` | **PCM_IDENTICAL** | informe idéntico + SDV/SDI idénticos |
| EVO | `full_processing` | **PCM_IDENTICAL** | informe idéntico + SDV/SDI idénticos |
| MQR | `full_processing` | **PCM_IDENTICAL** | informe idéntico + SDV/SDI idénticos |
| EVO | `analysis_only` | ACCEPTED | informe idéntico; sin PCM por diseño |
| MQR | `analysis_only` | ACCEPTED | informe idéntico; sin PCM por diseño |
| los tres | `dry_run` | NOT_APPLICABLE | `dry_run` no emite informe de análisis |
| Hardened | `analysis_only` | NOT_EXECUTED | defecto preexistente |

---

## 5. Pruebas 4, 5 y 6 — sustitución del Mix

Sustituto: `fixtures/mix_otro.flac`, FLAC **válido** con otro PCM (mismo
contenedor que el Mix), para que el rechazo no pueda atribuirse a un formato
ajeno. Sustitución por `os.replace` de un archivo pre-copiado (rename atómico).

| Escenario | Hardened | EVO | MQR |
|---|---|---|---|
| 4a guarda unitaria (`abrir_mix` con `sha` validado, archivo sustituido) | ACCEPTED | ACCEPTED | ACCEPTED |
| 4c sustitución durante la alineación (antes del DSP) | ACCEPTED (`exit=1`, sin salidas) | ACCEPTED (`exit=1`) | ACCEPTED (`exit=1`) |
| 4b sustitución tras la validación | ACCEPTED (ver nota) | ACCEPTED (ver nota) | ACCEPTED (ver nota) |
| 5 sustitución durante la lectura del DSP | ACCEPTED | ACCEPTED | ACCEPTED |
| 6 sustitución tras el DSP, antes de la confirmación final | ACCEPTED | ACCEPTED | ACCEPTED |

* Casos 5 y 6: `exit=2`, `ABORT_6G1.json` con motivo
  `MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO`; las salidas ya escritas se invalidan
  (`salidas_invalidadas = ['mix SDV.wav', 'mix SDI.wav']` en Hardened/EVO,
  `['SDV.wav', 'SDI.wav']` en MQR).
* Caso 4c: el motor detecta la sustitución al releer el Mix durante la
  alineación y termina con `exit=1` (`EXIT_VALIDATION`) antes de crear salidas.
* **Nota (4b):** la sustitución se disparó leyendo el log; en las tres
  implementaciones aterrizó después de abrir el descriptor. El motor abortó
  igualmente por la guarda final, sin salidas. La guarda previa a la apertura
  queda demostrada de forma determinista por 4a y 4c. Se declara así para no
  presentar como resultado una carrera que no se ganó.

---

## 6. Prueba 7 — higiene del aborto

En cada corrida con aborto se sembraron archivos ajenos en el directorio de la
corrida (`ajeno.txt`, `ajeno.wav`, `notas_preexistentes.json`) en el mismo
instante de la sustitución.

Resultado: **6/6 `ACCEPTED`**.

* No queda ninguna salida del motor (`*.wav` con nombres SDV/SDI) en el
  directorio.
* `ABORT_6G1.json` presente con `motivo`, `salidas_invalidadas` y
  `conservados`.
* Los tres archivos sembrados se conservan y se listan en `conservados`.
* `engine_log.txt` se conserva para trazabilidad forense.

---

## 7. Casos `NOT_EXECUTED` y `NOT_APPLICABLE`

### 7.1 `NOT_EXECUTED` (4 filas)

`Hardened` en `analysis_only` aborta con `AttributeError` en `write_reports`
(`ctx["post_wav_validation"]` es `None` cuando `full_mode` es `False`). Se
reprodujo **idénticamente** con la copia 6G, de modo que es un defecto
preexistente de 6F/6G y **no una regresión de 6G.1**. No se corrigió: queda
fuera del alcance autorizado (no es lectura, integridad ni aborto). Filas
afectadas: pruebas 1, 2, 3 y 9 con `escenario = analysis_only`.

### 7.2 `NOT_APPLICABLE` (8 filas)

`dry_run` no escribe PCM y no emite `analysis.json`; `analysis_only` no escribe
WAV. Esas ausencias se marcan `NOT_APPLICABLE`, nunca como éxito.

---

## 8. Reproducción

```bash
cd ETAPA_6G1_CORRECCION_LECTURA_SEGURA
python -B scripts/preparar_fixtures_6g1.py
python -B scripts/validar_contenedores_6g1.py
python -B scripts/sustituciones_6g1.py
python -B scripts/no_regresion_dsp_6g1.py
python -B scripts/consolidar_6g1.py
cd .. && sha256sum -c ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS.txt
```

Tiempos observados en este entorno (una ejecución, `resource.getrusage`):

| Script | s | máx. RSS hijo (KiB) |
|---|---|---|
| `preparar_fixtures_6g1.py` | 0,3 | 87 184 |
| `validar_contenedores_6g1.py` | 14,3 | 87 184 (acumulado) |
| `sustituciones_6g1.py` | 76,5 | 377 240 (acumulado) |
| `no_regresion_dsp_6g1.py` | 14,7 | 377 240 (acumulado) |
| `consolidar_6g1.py` | 0,2 | — |

Los RSS son el máximo acumulado de procesos hijos que informa `getrusage`; no
son la memoria de cada script por separado.

---

## 9. Artefactos de evidencia

* `evidence/matriz_global_6g1.csv` — 64 filas de las pruebas 1–10.
* `evidence/matriz_contenedores_6g1.csv` — pruebas 1, 2, 3, 8, 9.
* `evidence/matriz_sustituciones_6g1.csv` — pruebas 4, 5, 6, 7.
* `evidence/no_regresion_dsp_6g1.csv/.json` — prueba 10.
* `evidence/contenedores_6g1.json` — hashes PCM por salida, informes normalizados, integridad.
* `evidence/sustituciones_6g1.json` — intentos, motivos de aborto, archivos conservados.
* `evidence/resumen_6g1.json` — conteos, no ejecutadas, bloqueos conocidos.
* `MANIFEST_6G1.json` y `SHA256SUMS.txt` — hashes de todo lo entregado.
