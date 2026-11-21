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
4. **Informe.** Se compara `analysis.json` de 6G y 6G.1. **[6G.1-R, corrección
   D]** La afirmación original de esta sección («descartando sólo metadatos
   volátiles») resultó imprecisa: los informes normalizados **NO son iguales**
   y esa desigualdad es correcta y esperada. Los campos que difieren
   (`campos_diferentes_estricto` en `evidence/no_regresion_dsp_6g1.json`) son
   exclusivamente los de integridad que 6G.1 corrige por diseño: el campo
   nuevo `identidad_comparada_6g1` (comparación por claves de objeto en
   `wav_integridad_6f`/`audio_integridad_6g`) y el detalle de
   `mix_after` en FLAC (6G.1 corrige el falso negativo FLAC de 6G). La
   igualdad de informes no se fabrica: se documentan los campos exactos que
   difieren (§6). La huella DSP excluye de sus literales los valores del
   argumento `indent` de serialización JSON (parámetro de formato, no DSP);
   el conteo excluido queda registrado por definición.

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
| `analysis.json` normalizado | difieren sólo en los campos de integridad corregidos por 6G.1 (ver §6) | difieren sólo en los campos de integridad corregidos por 6G.1 (ver §6) |

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

---

## 6. Rectificación de la comparación de informes [6G.1-R, corrección D]

**Motivo real de la discrepancia**: la tabla de §3 declaraba «`analysis.json`
normalizado | igual» y, sin embargo, `no_regresion_dsp_6g1.json` registraba
`informe_igual: false` en los seis casos (3 motores × WAV/FLAC). El diagnóstico
registrado en la evidencia (`campos_diferentes_estricto`) muestra que los
informes difieren **exclusivamente** en campos del bloque `integrity` de la
alineación, y por una razón documentada de la propia etapa: 6G.1 corrige la
comparación de identidad por claves de objeto (`wav_integridad_6f`, +25/−3;
`audio_integridad_6g`, +13/−2 según el índice de auditoría de la entrega), lo
que añade el campo `identidad_comparada_6g1` (ausente en 6G) y cambia el
contenido de `mix_after` en FLAC (6G.1 ya no publica el falso negativo FLAC de
6G). No hay diferencia alguna en campos de cálculo DSP.

**Resolución**: la igualdad de informes normalizados **no se fabrica**.
- `informe_igual` (6G vs 6G.1) es y debe ser **False**; el procedimiento
  actualizado registra campo por campo lo que difiere
  (`campos_diferentes_estricto`, `campos_diferentes_normalizado`) y el conjunto
  de exclusión aplicado (`volatiles`, `volatiles_adicionales`; este último
  quedó vacío: ningún campo se excluyó más allá del conjunto histórico).
- La tabla de §3 se corrige en consecuencia.
- La huella DSP excluye los literales del argumento `indent` de
  `json.dump`/serialización (formato, no DSP); el conteo excluido por
  definición queda en `huellas[*].indent_excluidos_6g/6g1` (2 por motor tras la
  rectificación: la evidencia de integridad se reubicó al directorio
  provisional junto con su `indent=2`). Sin esa exclusión, el traslado del
  `indent=2` entre funciones marcaba la huella como cambiada sin cambio DSP
  alguno (falso positivo documentado en el informe de correcciones).
- Resultado tras la rectificación: 3 motores `ACCEPTED`, huella DSP idéntica,
  PCM WAV y FLAC idénticos frente a 6G.
