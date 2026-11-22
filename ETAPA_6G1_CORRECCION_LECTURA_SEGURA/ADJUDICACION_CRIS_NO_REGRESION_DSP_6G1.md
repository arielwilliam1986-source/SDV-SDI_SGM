# Adjudicación de Cris — No regresión DSP 6G.1

**Proyecto:** SDV-SDI_SGM
**Rama:** `arena/c7719286-sdv-sdi-sgm`
**Commit auditado (evidencia):** `bd768316d9234d365ee2a32f81558f26ac7a8d50`
(hijo directo de `b362c56e724811feab2570618c44b082e0d79d3d`)
**Commits comparados por la prueba:**

| Lado | Commit | Carpeta |
|---|---|---|
| 6G (referencia publicada) | `ee19fe208449249a20e194b09c9452b782c7de70` | `ETAPA_6G_SOPORTE_FLAC_MIX/motores/` |
| 6G.1 (código H2/H2-R) | `b362c56e724811feab2570618c44b082e0d79d3d` | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/` |

Este documento solo registra la decisión del auditor. No cambia el script de
prueba, los resultados JSON/CSV, los motores ni el código DSP. Las pruebas
**no** se volvieron a ejecutar.

---

## 0. Conclusión

| Concepto | Estado |
|---|---|
| **Resultado del detector** | **REJECTED** en Hardened, EVO y MQR (`dsp_ok = False`). Se mantiene tal como se registró. |
| **Decisión del auditor (Cris)** | **Equivalencia DSP aceptada con alcance limitado** para Hardened, EVO y MQR frente a 6G (alcance en §6). |
| **Estado general de 6G.1** | **NO CERRADA.** Esta adjudicación no la cierra ni la declara lista para integración. |

---

## 1. Rechazo mecánico original del detector

`scripts/no_regresion_dsp_6g1.py` (schema `no-regresion-dsp-6g1/2`) se ejecutó
una sola vez en `bd76831` y dio:

| Motor | `dsp_ok` | Motivo | PCM WAV | PCM FLAC | Veredicto del detector |
|---|---|---|---|---|---|
| Hardened | False | literales numéricos distintos en `FileInfo` y `create_run_dir` | IDÉNTICO | IDÉNTICO | **REJECTED** |
| EVO | False | literales numéricos distintos en `FileInfo` y `create_run_dir` | IDÉNTICO | IDÉNTICO | **REJECTED** |
| MQR | False | literales numéricos distintos en `FileInfo` y `create_run_dir` | IDÉNTICO | IDÉNTICO | **REJECTED** |

El rechazo es **mecánico**. El criterio de literales exige el mismo conjunto de
literales numéricos en *toda* definición cambiada, haga o no procesamiento de
señal. Se aplicó tal cual: no se modificó `dsp_ok` ni se añadió ninguna
exclusión a esa comprobación.

En los tres motores:

- no hay definiciones añadidas ni eliminadas;
- no hay constantes en mayúsculas cambiadas, añadidas ni eliminadas.

Evidencia conservada sin cambios (SHA-256 según `SHA256SUMS_NOREG_DSP_FINAL.txt`):

| Archivo | SHA-256 |
|---|---|
| `scripts/no_regresion_dsp_6g1.py` | `1fd4defb75f82e8712bdf018b71651c93e980ca9586a537ea1b4f562e9f5994a` |
| `evidence/no_regresion_dsp_6g1.json` | `9a499e813c7f2499989b5fcb2779cd298f73671415943fedb57e4c4a262b7dca` |
| `evidence/no_regresion_dsp_6g1.csv` | `af607dd61370dc4b2d006dbf3f5fdd53da49aa17793db44fe62945777f3b8260` |
| `NO_REGRESION_DSP_6G1.md` | `09afeebdde3e049c106a8aca586addc2c3d484b02c1539cd5d3f7d0e97ce569a` |

---

## 2. Las dos diferencias numéricas encontradas

Las diferencias son las mismas en los tres motores.

| Definición | Literales añadidos en 6G.1 | Código que los origina | Commit de origen |
|---|---|---|---|
| `FileInfo` | `0`, `0`, `0`, `0` | valores por defecto de los campos de identidad `device: int = 0`, `inode: int = 0`, `mtime_ns: int = 0`, `ctime_ns: int = 0` | H2 `af804244…` |
| `create_run_dir` | `0`, `0`, `1`, `999` | `intento = 0`, `intento == 0`, `intento += 1`, `intento > 999` (creación exclusiva del directorio provisional y tope de reintentos) | Seguridad E–G `2248e2e` |

No falta ningún literal respecto de 6G: solo hay literales añadidos.

---

## 3. Por qué ninguna de las dos diferencias es DSP

**`FileInfo`**

- Es un `dataclass` de metadatos del archivo de entrada: ruta, rol, formato,
  tamaño, SHA y validez.
- Los cuatro campos nuevos guardan la identidad del objeto validado en el
  sistema de archivos (dispositivo, inodo y marcas de tiempo), que se usa para
  anclar la apertura segura del Mix (H2/H2-R).
- No contiene muestras de audio, no hace ninguna llamada a función salvo
  `field(default_factory=list)` en los campos de lista, y su valor `0` es solo
  el estado inicial antes de rellenarse con `os.fstat`.
- Ningún parámetro de señal (STFT, `n_fft`, `hop`, ventanas, máscaras,
  consenso, `power`/`beta`/`epsilon`, ganancias) se lee de estos campos.

**`create_run_dir`**

- Crea el directorio provisional de la corrida.
- Los literales `0`/`1`/`999` son un contador de reintentos: si el nombre ya
  existe, prueba con otro sufijo y se detiene con error al pasar de 999
  intentos.
- Las únicas llamadas que hace son de gestión de archivos y del registro de
  propiedad: `datetime.now().strftime`, `os.path.join`, `os.path.basename`,
  `os.makedirs`, `_reiniciar_registro_6g1`, `_crear_y_acreditar_dir_6g1` y
  `RuntimeError`.
- No lee ni escribe audio.

La inspección de ambas definiciones confirma que ninguna procesa señal. Las dos
diferencias quedan **clasificadas como gestión de archivos y seguridad**, no
como modificaciones DSP.

---

## 4. Llamadas DSP idénticas

En cada definición cambiada, el detector comparó el multiconjunto de llamadas a
primitivas DSP (`fft`, `rfft`, `hann`, `sqrt`, `exp`, `abs`, `power`,
`maximum`, `where`, `sum`, `mean`, `convolve`, `einsum`, `percentile`, …) entre
6G y 6G.1. Según `evidence/no_regresion_dsp_6g1.json` (`huellas[*].llamadas_dsp_iguales`),
coinciden en **todas** las definiciones cambiadas de los tres motores:

| Motor | Definición | Llamadas DSP 6G / 6G.1 | Iguales |
|---|---|---|---|
| Hardened | `analyze_guide_scale` | 8 / 8 | sí |
| Hardened | `run_experiment` | 14 / 14 | sí |
| Hardened | `CandidateRunner`, `FileInfo`, `_open_memmap`, `create_run_dir`, `probe_file`, `write_reports` | 0 / 0 | sí |
| EVO | `analyze_guide_scale` | 9 / 9 | sí |
| EVO | `run_experiment` | 23 / 23 | sí |
| EVO | `CandidateRunner`, `FileInfo`, `_open_memmap`, `create_run_dir`, `probe_file`, `write_reports` | 0 / 0 | sí |
| MQR | `_run_core` | 5 / 5 | sí |
| MQR | `analyze_guide_scale` | 1 / 1 | sí |
| MQR | `CandidateRunner`, `FileInfo`, `_open_memmap`, `create_run_dir`, `probe_file`, `run_experiment`, `write_reports` | 0 / 0 | sí |

`FileInfo` y `create_run_dir` tienen **cero** llamadas DSP tanto en 6G como en
6G.1. Fuera de esas dos definiciones, los literales numéricos también son
iguales en todas las demás definiciones cambiadas.

---

## 5. Resultados PCM y geometría registrados

Condiciones de la ejecución registrada:

- modo `full_processing`;
- fixtures sintéticos `mix.wav` / `mix.flac` + `vocal_mix.wav` / `instrumental_mix.wav`, verificados 4/4 contra `fixtures_manifest.json`;
- Python 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2.

Resultado en los 3 motores y ambos contenedores: código de salida 0/0, 2
salidas reales en disco en cada versión, geometría igual y hash PCM igual entre
6G y 6G.1.

| Motor | Salida | Geometría (frames, canales, sr) | SHA-256 PCM decodificado `float64` (6G = 6G.1, WAV = FLAC) |
|---|---|---|---|
| Hardened | `mix SDI.wav` | 88200, 2, 44100 | `368d3ecbc3a07d053a67e2fb1157a66eb290d8f0a7a31087a5a3060a81574f85` |
| Hardened | `mix SDV.wav` | 88200, 2, 44100 | `a347838da989c3645115f9d08dd296a9902a2b8ac0372fde5002e40f1d420bc0` |
| EVO | `mix SDI.wav` | 88200, 2, 44100 | `368d3ecbc3a07d053a67e2fb1157a66eb290d8f0a7a31087a5a3060a81574f85` |
| EVO | `mix SDV.wav` | 88200, 2, 44100 | `a347838da989c3645115f9d08dd296a9902a2b8ac0372fde5002e40f1d420bc0` |
| MQR | `SDI.wav` | 88200, 2, 44100 | `565bc8b6adbf2e489723a2dd11471f05a181608359163d0dbf44b509083754d3` |
| MQR | `SDV.wav` | 88200, 2, 44100 | `8fb3578a2b56b062d6bcb9b9d72b2657106efcd1aa838cc5de8f8a42fe6f9af8` |

---

## 6. Alcance exacto de la aceptación

Cris acepta la **equivalencia DSP** de Hardened, EVO y MQR (6G.1 en `b362c56`)
frente a 6G (`ee19fe2`) **solo** en estos términos:

1. Las diferencias de literales en `FileInfo` (`0` ×4) y `create_run_dir`
   (`0`, `0`, `1`, `999`) se aceptan como diferencias **no DSP** de gestión de
   archivos y seguridad.
2. La aceptación cubre únicamente los tres motores comparados, en las versiones
   identificadas por los SHA-256 registrados en la evidencia:
   - Hardened `8c1fca98…1f571`
   - EVO `7b99ab80…e19d8`
   - MQR `00734713…9372d`
3. Se apoya en la evidencia registrada en `bd76831`:
   - sin definiciones añadidas ni eliminadas;
   - sin constantes cambiadas;
   - llamadas DSP idénticas;
   - PCM WAV/FLAC idéntico y geometría igual con los fixtures sintéticos publicados.
4. Cualquier cambio posterior en esos motores, o en las definiciones citadas,
   deja sin efecto esta aceptación y requiere una nueva evaluación.

## 7. Limitaciones de la conclusión

- **No sustituye al detector:** el resultado mecánico sigue siendo `REJECTED`.
  No se modificó `dsp_ok`, no se añadieron exclusiones a la comprobación de
  literales y no se regeneró la evidencia.
- **Cobertura de señal limitada:**
  - solo fixtures sintéticos cortos (2 s, 44,1 kHz, estéreo, PCM_16);
  - solo el modo `full_processing`;
  - un único entorno (Python 3.11.2 / numpy 1.26.4 / scipy 1.13.1 / libsndfile 1.2.2, linux x86_64);
  - no se procesó audio real (Elis, Tristania) ni se ejecutó en Android/Termux.
- **Solo los tres motores:** la prueba compara Hardened, EVO y MQR.
  `lectura_segura_6g1.py`, `audio_integridad_6g.py`, `wav_integridad_6f.py` y
  `atribucion_6f.py` no forman parte de la comparación AST de esta prueba.
- **Análisis estático por definición:** el AST y la comprobación de literales
  comparan definiciones de nivel superior. La equivalencia de comportamiento se
  apoya además en el PCM idéntico, que se limita a los casos ejecutados.
- **Evidencia agregada sin actualizar:**
  - `consolidar_6g1.py` no se ejecutó;
  - `evidence/matriz_global_6g1.csv` y `evidence/resumen_6g1.json` siguen sin reflejar el resultado de `bd76831`;
  - `SHA256SUMS.txt` y `MANIFEST_6G1.json` de la etapa siguen desfasados para los archivos de la prueba 10.

  Esta adjudicación no los modifica.
- **6G.1 sigue NO CERRADA.** Esta decisión resuelve solo el control de
  equivalencia DSP. No hace merge, no integra y no autoriza otra subfase.
