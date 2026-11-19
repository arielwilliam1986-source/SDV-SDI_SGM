# Etapa 6G · Informe de implementación

**Objetivo:** que los tres motores experimentales derivados de 6F acepten el Mix
original en **WAV o FLAC**, leído directamente y sin conversión intermedia, sin
tocar el DSP.

## 1. Base, rama y aislamiento

| Elemento | Valor |
|---|---|
| Repositorio | `arielwilliam1986-source/SDV-SDI_SGM` |
| Commit base exigido | `663fb5f8b4d53c8445d482ecec4df6a0208c59f0` (cierre 6F) |
| Rama | `arena/89d5c189-sdv-sdi-sgm` |
| HEAD al iniciar | `663fb5f8b4d53c8445d482ecec4df6a0208c59f0` (verificado; base es ancestro) |
| Árbol al iniciar | limpio (0 cambios) |
| `main` | no tocada (`b64f15ae…`, intacta) |

Desviación declarada: el encargo pedía una rama nueva `arena/etapa-6g-soporte-flac-mix`.
Arena no permite crear ni cambiar de rama en esta sesión; el usuario **autorizó
expresamente** ejecutar 6G en la rama activa, partiendo del commit base exigido.
Todo el trabajo vive en `ETAPA_6G_SOPORTE_FLAC_MIX/`; ningún archivo de 6C, 6D,
6E, 6F, del motor v3 ni de `main` fue modificado.

## 2. El problema, en las dos capas

1. **Validación.** `probe_file()` de Hardened y EVO llamaba a `verify_wave()`
   para cualquier entrada; MQR hacía lo mismo. `wav_integridad_6f` exige
   RIFF/WAVE, de modo que un FLAC válido se rechazaba antes de leer nada.
2. **Extensiones.** MQR declaraba `MIX_ALLOWED_EXTENSIONS = (".wav",)`.
3. **Lectura de alineación.** `atribucion_6f.analyze_files` abría Mix y guía con
   `open_validated` (sólo WAV), así que incluso aceptando el archivo, el
   análisis de alineación habría fallado.

Cambiar sólo la extensión no habría bastado: el rechazo venía de tres sitios.

## 3. Qué se implementó

### 3.1 Módulo nuevo `motores/audio_integridad_6g.py`

Capa de compatibilidad de contenedores, sin DSP:

* **Detección por cabecera real** (`RIFF/WAVE`, `fLaC`, `RF64`, `RIFX`, `OggS`,
  `ID3`), nunca por extensión. Si el contenedor no coincide con la extensión, se
  rechaza con mensaje explícito.
* **WAV:** delega íntegramente en `wav_integridad_6f` (copia byte a byte, hash
  idéntico). No se relajó ninguna comprobación: chunks, geometría, `fmt`,
  bits válidos, máscara, tamaños y padding se validan igual que en 6F.
* **FLAC:**
  1. recorre los bloques de metadatos y exige STREAMINFO primero, longitud 34 y
     sin desbordes;
  2. contrasta STREAMINFO (rate, canales, profundidad, frames, MD5) con lo que
     reporta libsndfile;
  3. exige subtipo `PCM_S8/PCM_16/PCM_24` y decodifica **por bloques de 65 536
     frames**, comprobando finitud y recuento de frames (sin retener el audio en
     memoria durante la validación);
  4. verifica el **MD5 de PCM de STREAMINFO** recorriendo el archivo otra vez en
     streaming, lo que detecta corrupción que el decodificador tolera;
  5. calcula SHA-256 y compara identidad `fstat` antes/después.
* **Misma lectura que la validada:** el decodificador abre `/proc/self/fd/<fd>`,
  es decir, **el mismo inodo** que se validó, no la ruta. Una sustitución de la
  ruta después de abrir no cambia las muestras leídas.
* **Lectura para análisis:** `open_audio()` despacha WAV→6F y FLAC→validador
  nuevo, devolviendo la misma interfaz (`spec`, `samples`, `digest`, `identity`).

### 3.2 Cambios en las copias de los motores

| Motor | Líneas | Qué cambia |
|---|---|---|
| Hardened 6G | +26 / −1 | import del módulo, `probe_file` usa `verify_audio`, traza de contenedor, guarda final |
| EVO 6G | +26 / −1 | idem |
| MQR 6G | +27 / −2 | idem + `MIX_ALLOWED_EXTENSIONS = (".wav", ".flac")` |
| `atribucion_6f.py` | +2 / −2 | `open_validated` → `open_audio` (despacho por contenedor) |
| `wav_integridad_6f.py` | 0 | copia idéntica (hash verificado) |

* **Trazabilidad:** en `run_experiment` se registra `ctx["container_6g"]` (ruta,
  contenedor real, formato, subtipo, SHA-256 del sondeo) y al terminar se
  revalida el SHA-256. Si cambió, se aborta con `EXIT_PROCESSING`. El resultado
  se escribe en `input_integrity_6g.json` dentro del directorio de la corrida.
* **Puerta de alineación intacta:** el bloqueo por `AMBIGUOUS`,
  `INSUFFICIENT_SIGNAL`, `NON_INFORMATIVE` y `ERROR` sigue siendo el de 6F.

### 3.3 Invariantes del audio

No hay conversión FLAC→WAV, ni archivo WAV intermedio, ni remuestreo, downmix,
cambio de canales, normalización, ganancia, polaridad, desplazamiento,
cuantización adicional ni dither. El FLAC se decodifica a `float64` y alimenta
el mismo procesamiento que el WAV. Las muestras decodificadas de WAV y FLAC
equivalentes son **idénticas** (verificado: `np.array_equal`).

## 4. Lo que NO se hizo

* No se procesó ninguna canción real ni material del piloto.
* No se integró nada al orquestador, no se eligió motor ganador.
* No se cambiaron parámetros, defaults ni umbrales históricos.
* No se creó copia WAV del Mix original.
* No se tocó STFT/ISTFT, ventanas, FFT/hop, máscaras, fórmulas, consenso,
  potencias/epsilon, suavizado, reconstrucción, chunking, alineación ni
  atribución (ver `NO_REGRESION_DSP_6G.md`).

## 5. Limitaciones conocidas

* La lectura desde el mismo descriptor usa `/proc/self/fd`; fuera de Linux (o
  con `/proc` no montado) el FLAC se rechaza con error explícito en lugar de
  leer por ruta.
* Sólo se admiten FLAC `PCM_S8/PCM_16/PCM_24`; no FLAC de 32 bits ni FLAC con
  metadatos de streaming sin MD5 (en ese caso `md5_checked = false` y se
  documenta que la verificación criptográfica de STREAMINFO no se aplicó).
* La detección de corrupción combina errores del decodificador, recuento de
  frames y MD5 de PCM; no se implementó verificación CRC-16 frame a frame.
* MQR mantiene su limitación histórica: las máscaras se derivan por downmix
  mono de las guías; **no** equivale al modo L/R independiente de Hardened/EVO.
* No se probaron archivos > 2 GB, tasas distintas de 44 100 Hz ni más de 2
  canales (se rechazan por política del motor, no por el validador).
