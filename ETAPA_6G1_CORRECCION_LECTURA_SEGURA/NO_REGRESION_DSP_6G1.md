# Etapa 6G.1 — No regresión DSP frente a 6G

**Objeto:** demostrar que la corrección de lectura segura no altera el DSP.
**Fuentes comparadas:** `ETAPA_6G_SOPORTE_FLAC_MIX/motores/` (6G, publicada) y
`ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/` (6G.1).
**Evidencia:** `evidence/no_regresion_dsp_6g1.csv`, `evidence/no_regresion_dsp_6g1.json`
y las filas de prueba `10` en `evidence/matriz_global_6g1.csv`.

---

## 1. Método

1. **AST.** Se comparan las definiciones de nivel superior y las constantes en
   mayúsculas de cada archivo.
2. **Huella DSP de las definiciones que cambian.** Para cada definición distinta
   se comparan dos conjuntos independientes de la indentación y del texto:
   * literales numéricos (multiconjunto, con signo aplicado para `-x`);
   * llamadas a primitivas DSP (`fft`, `rfft`, `hann`, `sqrt`, `exp`, `abs`,
     `power`, `maximum`, `minimum`, `where`, `sum`, `mean`, `convolve`,
     `einsum`, `percentile`, …). `log(...)` sin punto se excluye a propósito:
     es el registro del motor, no `np.log`.
3. **PCM.** El mismo Mix se procesa con la copia 6G y con la 6G.1, en `WAV` y en
   `FLAC`, en modo `full_processing`, y se comparan los hashes del PCM
   decodificado (`float64`) por nombre de salida. Se exige que existan archivos
   reales en ambas corridas.
4. **Informe.** Se compara `analysis.json` de 6G y 6G.1 descartando sólo
   metadatos volátiles por archivo.

---

## 2. Resultado por motor

| Motor | Definiciones cambiadas | Añadidas | Eliminadas | Constantes cambiadas | Huella DSP | PCM WAV | PCM FLAC | Veredicto |
|---|---|---|---|---|---|---|---|---|
| Hardened | `analyze_guide_scale`, `run_experiment` | — | — | — | idéntica | IDÉNTICO | IDÉNTICO | ACCEPTED |
| EVO | `analyze_guide_scale`, `run_experiment` | — | — | — | idéntica | IDÉNTICO | IDÉNTICO | ACCEPTED |
| MQR | `_run_core`, `analyze_guide_scale`, `run_experiment` | — | — | — | idéntica | IDÉNTICO | IDÉNTICO | ACCEPTED |

* No hay definiciones añadidas ni eliminadas en los motores.
* No hay ninguna constante en mayúsculas modificada (ni `CONSENSUS_METHODS`, ni
  `CHUNK_FRAMES_DEFAULT`, ni umbrales, ni `*_ALLOWED_EXTENSIONS`).
* Las tres definiciones que cambian son las que contienen la apertura vigilada,
  la guarda final o la lectura del Mix para la escala de guías.

## 3. Verificación de compatibilidad DSP y su equivalencia con 6G

| Vector | 6G | 6G.1 |
|---|---|---|
| Mix WAV → SDV/SDI (Hardened) | hashes | idénticos |
| Mix WAV → SDV/SDI (EVO) | hashes | idénticos |
| Mix WAV → SDV/SDI (MQR) | hashes | idénticos |
| Mix FLAC → SDV/SDI (Hardened) | hashes | idénticos |
| Mix FLAC → SDV/SDI (EVO) | hashes | idénticos |
| Mix FLAC → SDV/SDI (MQR) | hashes | idénticos |
| `analysis.json` normalizado | igual | igual |

Los hashes concretos están en `evidence/no_regresion_dsp_6g1.json`
(`motores[*].pcm[WAV|FLAC].pcm_6g` y `pcm_6g1`).

---

## 4. Superficie de cambio declarada

Cambios permitidos y efectivamente realizados (ver `INFORME_IMPLEMENTACION_6G1.md`):

* lectura: apertura única y lectura desde `/proc/self/fd/N`;
* gestión de archivos: cierre diferido del descriptor;
* integridad: `verificar()` + `ruta_apunta_al_mismo_objeto()` en la guarda final,
  y comparación por claves de objeto en `wav_integridad_6f` y `audio_integridad_6g`;
* aborto seguro: `abortar_6g1`, invalida sólo salidas propias de la corrida;
* evidencia: `post_wav_identity` recibe el descriptor ya validado.

Cambios **no** realizados (verificados por AST y por huella): STFT/ISTFT,
`n_fft`/`hop`, ventanas, ventaneo y OLA, máscaras, fórmulas, consenso,
`power`/`beta`/`epsilon`, suavizado, reconstrucción, ganancias, polaridad,
parámetros DSP, verificación WAV de 6F.

---

## 5. Verificación de la 6G publicada

* `ETAPA_6G_SOPORTE_FLAC_MIX/` no figura en `git status` durante 6G.1.
* Los 46 hashes de `ETAPA_6G_SOPORTE_FLAC_MIX/SHA256SUMS.txt` siguen
  verificando con `sha256sum -c` después de la corrección.
* La firma de `post_wav_identity` no cambió en 6G.1: sólo cambió el valor del
  argumento que reciben los motores.
