# Etapa 6F · Informe de implementación

**Resultado:** corrección acotada de diagnóstico, integridad de archivos y
controles de CLI, con reserva independiente superada. No se modificó ningún
paso de procesamiento de audio y no se declara producción ni aptitud
definitiva.

## 1. Base, rama y trazabilidad

| Elemento | Valor |
|---|---|
| Repositorio | `arielwilliam1986-source/SDV-SDI_SGM` |
| Commit base exigido y verificado | `b72ce49ae787c72a1148bbec95db35dba460d279` |
| Rama de trabajo | `arena/89d5c189-sdv-sdi-sgm` |
| Commit de congelamiento (implementación) | `5d344e1` |
| Archivos de 6E | presentes e íntegros (24 archivos, `MANIFEST_6E.json` con SHA-256 coincidente) |

**Desviación declarada (no técnico):** el encargo pedía crear la rama
`arena/etapa-6f-cierre-correctivo` partiendo del commit base. Esta sesión está
fijada por la plataforma a una única rama (`arena/89d5c189-sdv-sdi-sgm`) y no
permite crear ni cambiar de rama. Se informó la restricción, se detuvo la
ejecución y, con autorización explícita del usuario, se ejecutó 6F en la rama
de sesión, que parte exactamente del commit base exigido. No se sustituyó la
rama por una carpeta de otra rama: el árbol de trabajo es el de 6F y el
aislamiento se comprueba con los commits y los hashes del manifiesto.

## 2. Qué se corrigió (y qué no)

### A. Atribución y candidatos rivales

**Causa demostrada del falso `UNIQUE` de `right_rival` en 6E.** El umbral
rival se calculaba con un tamaño efectivo derivado de la autocorrelación de la
guía. Con ruido blanco de 5 512 muestras ese estimador devolvía ≈2 834 muestras
en lugar de 5 512 (sesgo ≈1,95×), y el umbral quedaba en **0,1124**; la réplica
real de amplitud 0,125 producía puntuaciones de **0,103 / 0,099 / 0,090** en
las mitades de R y nunca se confirmaba. La normalización además dividía por la
energía total del residual, que incluye la guía instrumental.

**Corrección 6F** (`motores/atribucion_6f.py`):

1. **Ventanas solapadas** (6 ventanas de `n/4` con 50 % de solape en lugar de
   bloques contiguos) y mitades degeneradas (silencio/constante) descartadas
   sin invalidar la ventana: recupera retardos cuyo borde contiene relleno.
2. **Prueba de hipótesis de réplica**: para cada pico candidato se ajusta
   `mix ≈ a + b0·g[t−k0] + b1·g[t−k1]` por mínimos cuadrados y se evalúa
   `t = b1/se(b1)`; si los soportes no se solapan se usa el ajuste simple en el
   soporte propio del candidato. La multiplicidad se cuenta sobre el **barrido
   completo** (`z = Φ⁻¹(1 − 10⁻³/(2M))`, M = posiciones examinadas) y no sobre
   los picos retenidos.
3. **Calibración empírica del nulo**: `σ_ρ = 1,4826·MAD(ρ)` de la propia curva;
   se exige simultáneamente `|t| ≥ z` y `|ρ| ≥ σ_ρ·z`. Esto evita confundir
   ruido con réplica en señales dispersas o correlacionadas.
4. **Ambigüedad estructural**: si la autocorrelación de la guía en el retardo
   candidato es ≥ 0,5 y el candidato está igual de soportado que el dominante,
   el caso es `AMBIGUOUS` (señal periódica). Un hombro del lóbulo principal no
   se trata como réplica.
5. **Corroboración**: una réplica debe confirmarse en dos mitades con el mismo
   retardo (±1 muestra). Un único testimonio se registra como
   `RIVAL_NOT_CORROBORATED` y la ventana no cuenta como medida (no se convierte
   en `UNIQUE` ni en `AMBIGUOUS` probado).
6. **Capacidad de detección publicada**: cada canal informa
   `replica_detection_floor = z·se·σ_guía/σ_mix` (amplitud relativa al Mix). Si
   el piso supera 0,35 el canal se abstiene con
   `INSUFFICIENT_DETECTION_CAPABILITY` en lugar de declarar `UNIQUE`.

Pisos medidos: **0,088–0,089** con 1 s, **0,071–0,077** con 2 s y
**0,049–0,058** con 4 s de ruido sintético. Una réplica de amplitud 0,125 se
detecta desde 1 s; una de 0,03 queda por debajo del piso y se documenta como
límite declarado (caso `res_replica_bajo_piso`, con dos resultados admisibles).

### B. Diagnóstico estéreo L/R

Cada canal se mide por separado; nunca se usa Mid, Side ni mono. El agregado
(`combine_channels`) distingue:

* `MEASURED_AGREEMENT`: todos los canales medidos y con el mismo retardo y
  signo.
* `CHANNEL_DISAGREEMENT` / `CHANNEL_POLARITY_CONFLICT`: canales medidos con
  retardos distintos o polaridad opuesta; **no se emite un retardo común**.
* `INCOMPLETE_CHANNEL_EVIDENCE`: un solo canal medido; se publica
  `partial.measured` y `partial.not_measured` y no se infiere reloj.

`different_lr` (L alineado, R desplazado 33 muestras) pasa de
`INSUFFICIENT_SIGNAL` en 6E a `AMBIGUOUS` con `channel_lags={"L":0,"R":33}`.

### C. Retardo uniforme

El caso 567 de la reserva 6E devolvía `INSUFFICIENT_SIGNAL` porque el primer
bloque contenía 567 ceros y una de sus mitades no aportaba ningún retardo, lo
que invalidaba el bloque completo. Con ventanas solapadas y mitades
degeneradas descartadas el resultado es `k=-567` en L y R, con cobertura 1,0.
Se probaron además retardos ±1 901 y +4 000 (borde de cobertura sobre 2 s) y
±1 000 / +3 000 sobre otras longitudes, todos con el retardo exacto.

### D. Integridad WAV

`motores/wav_integridad_6f.py` sustituye el analizador de 6E:

* RIFF/WAVE clásico little-endian; se rechazan explícitamente RF64 y RIFX.
* `fmt` único y anterior a `data`; `data` único; tamaños y padding de todos los
  chunks dentro del límite físico; el recorrido debe cerrar exactamente en el
  tamaño declarado.
* `WAVE_FORMAT_EXTENSIBLE`: `cbSize ≥ 22`, GUID de subformato PCM o IEEE float
  (se rechazan GUID comprimidos y el alias `00000000-…`), `valid_bits ≤ bits`,
  channel mask dentro de las 18 posiciones estándar y con tantos bits como
  canales, `block_align = canales·⌈bits/8⌉`, `byte_rate = rate·block_align`,
  `data` múltiplo de `block_align`, `fact` coincidente con los frames.
* Perfil admitido: PCM entero 8/16/24/32 y float 32/64 (incluido
  `valid_bits` en contenedor mayor). Se rechazan profundidades no admitidas,
  formatos comprimidos y PCM de 64 bits.
* Contraste con la metadata de libsndfile (canales, tasa, frames y subtipo).
* **Mismo descriptor**: `open_validated` valida, hashea y decodifica el payload
  desde el mismo descriptor abierto; el PCM usado para el diagnóstico es el
  PCM inspeccionado. `check_unchanged` revalida identidad `fstat` y SHA-256 al
  terminar.
* **TOCTOU**: se detecta (a) reemplazo de la ruta después de abrir —las muestras
  siguen siendo las del objeto validado—, (b) modificación en sitio y
  (c) sustitución entre el sondeo y la lectura, que produce `ERROR` y bloquea.
  No se afirma inmunidad: no hay prevención de escrituras concurrentes ni
  autenticación del contenido.

### E. CLI y bloqueos

`alignment_gate` (módulo compartido) sustituye el veto ad-hoc de cada motor:

* `ERROR` es incondicional.
* `AMBIGUOUS`, `INSUFFICIENT_SIGNAL` y `NON_INFORMATIVE` bloquean por defecto
  (sin WAV, sin informe, exit 1).
* `--allow-misaligned` permite continuar sólo en esos estados, deja
  `verdict=ALLOWED_EXPLICIT`, `permission=cli_allow_misaligned`,
  `scope=procesar_sin_corregir_alineacion` y el listado de estados que se
  permitieron.
* El permiso no altera offsets, muestras ni polaridad: `action` permanece en
  `shift_authorized=false`, `applied_shift_samples=0`,
  `polarity_changed=false`; el PCM es idéntico y el diagnóstico no cambia.
* El permiso no salta la validación física ni la comprobación de datos no
  finitos: ambas se ejecutan antes y `ERROR` nunca se permite.
* La compuerta queda en el informe (`alignment_gate` en Hardened/EVO,
  `alignment_gate` como ítem de `validation_status` en MQR).

### F. MQR S7

Se reconstruyó el estímulo histórico S7 desde la receta publicada de S5
(`V=(v,−v)`, `I=(i,−i)`, 176 400 frames). Reproducción exacta:

| Versión | Exit | Aborto | Informe | WAV | Cresta SDV/Mix |
|---|---|---|---|---|---|
| 6C | 2 | `ZeroDivisionError` en `crest_factor_sdv` | no | 2 parciales | no publicada |
| 6E | 0 (con permiso) | no | sí | 2 | `null` explícito |
| 6F | 0 (con permiso) | no | sí | 2 | `null` explícito |

`mix_mid_rms = 0.0` y `mix_lr_peak = 0.3303473`, idéntico al pico `0.330347`
registrado en 6D: la reproducción es fiel. No se introdujo epsilon: el cociente
indefinido se representa como `null` y `crest_factor_basis` lo declara. En 6F
la validación técnica global sigue siendo `fail` (alineación ambigüedad
registrada), que no equivale a aborto: la corrida termina y publica informe.
Sin `--allow-misaligned`, 6F bloquea S7 porque la guía es una suma de tonos
periódicos y el retardo es genuinamente no identificable (abstención honesta,
no regresión).

## 3. Archivos nuevos y modificados

Dentro de `ETAPA_6F_CIERRE_CORRECTIVO/` (nada fuera de esta carpeta):

| Archivo | Origen | SHA-256 |
|---|---|---|
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | copia 6E + 5 bloques de diagnóstico | ver `MANIFEST_6F.json` |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | copia 6E + 5 bloques | idem |
| `motores/sdv_sdi_mqr_engine.py` | copia 6E + 5 bloques | idem |
| `motores/atribucion_6f.py` | nuevo | idem |
| `motores/wav_integridad_6f.py` | nuevo | idem |
| `scripts/*.py` | nuevos | idem |

El constructor `scripts/construir_motores_6f.py` regenera las tres copias y
aplica exactamente 89 / 89 / 102 líneas de diff respecto de 6E: importación,
`_combine`, `analyze_alignment`, compuerta CLI y campo de informe. No hay
cambios en STFT, máscaras, fórmulas SDV/SDI, ganancias, polaridad, shifts,
normalización, parámetros de separación ni procesamiento de muestras (ver
`NO_REGRESION_DSP_6F.md`).

## 4. Defectos que permanecen

* Réplicas por debajo del piso publicado (≈0,05–0,09 según duración) no son
  detectables; el caso se declara `UNIQUE` con piso explícito. No hay garantía
  matemática de unicidad.
* Guías periódicas o de banda estrecha son no identificables: 6F se abstiene
  siempre (`AMBIGUOUS`), incluso si el retardo real es cero. Es una abstención
  deliberada y documentada.
* La ventana de búsqueda (±30 s) y el requisito de solape completo de la
  plantilla limitan los retardos examinados en archivos cortos.
* La detección TOCTOU no previene escrituras concurrentes; sólo las detecta.
* Los tres motores comparten el estimador: sus coincidencias no son tres
  validaciones independientes.
* No se probaron canciones reales, ni Termux ARM64, ni archivos largos.
* El ajuste de escala de guías (`g_vocal`, `g_instr`) no se revisó en 6F.
