# Etapa 6F · Tomo 1 · Informes

Documento autogenerado por `scripts/empaquetar_auditoria_6f.py`.
Fuente: `arielwilliam1986-source/SDV-SDI_SGM`, rama
`arena/89d5c189-sdv-sdi-sgm`, base `b72ce49ae787c72a1148bbec95db35dba460d279`,
congelamiento `5d344e1`. Cualquier cifra de este tomo proviene de los informes y
la evidencia versionada; el tomo no añade afirmaciones nuevas.

Dictamen de la etapa: **APROBADO CON LIMITACIONES** (ver §Limitaciones).

---

## Índice

# 6F · Índice para auditoría externa

Punto de entrada único para revisión independiente de la etapa 6F.

## Lectura en dos enlaces (todo el texto, sin navegar el repositorio)

| Tomo | Contenido | URL raw |
|---|---|---|
| 1 | los nueve informes, este índice y el informe de entrega | `https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/89d5c189-sdv-sdi-sgm/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_6F_TOMO_1_INFORMES.md` |
| 2 | hashes, matrices completas (atribución, CLI, WAV) | `https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/89d5c189-sdv-sdi-sgm/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_6F_TOMO_2_EVIDENCIA.md` |

Ambos tomos se regeneran con `scripts/empaquetar_auditoria_6f.py`. Este índice
solo no contiene los informes: es un mapa con resumen y advertencias.

| Dato | Valor |
|---|---|
| Repositorio | `arielwilliam1986-source/SDV-SDI_SGM` (público) |
| Rama | `arena/89d5c189-sdv-sdi-sgm` |
| Commit base exigido | `b72ce49ae787c72a1148bbec95db35dba460d279` |
| Congelamiento de implementación | `5d344e1` |
| Cierre 6F (este árbol) | ver el commit que contiene este índice |
| Dictamen | **APROBADO CON LIMITACIONES** |
| Informe de entrega (16 puntos + confirmaciones) | `ENTREGA_6F.md` |

## Informes

| Documento | Ruta |
|---|---|
| Implementación | `INFORME_IMPLEMENTACION_6F.md` |
| Validación con reserva independiente | `INFORME_VALIDACION_INDEPENDIENTE_6F.md` |
| Auditoría CLI y bloqueos | `AUDITORIA_CLI_6F.md` |
| Auditoría de integridad WAV | `AUDITORIA_WAV_6F.md` |
| Diagnóstico MQR S7 | `DIAGNOSTICO_MQR_S7_6F.md` |
| Estéreo L/R | `ANALISIS_ESTEREO_LR_6F.md` |
| No regresión DSP | `NO_REGRESION_DSP_6F.md` |
| Recursos y duraciones | `RECURSOS_Y_DURACIONES_6F.md` |
| Limitaciones y casos fuera de capacidad | `LIMITACIONES_Y_CASOS_UNKNOWN_6F.md` |

## Evidencia y matrices

| Artefacto | Ruta |
|---|---|
| Manifiesto (hashes, entorno, estímulos, resultados) | `MANIFEST_6F.json` |
| Hashes verificables (`sha256sum -c`) | `SHA256SUMS.txt` |
| Matriz de atribución (177 filas, desarrollo + reserva) | `MATRIZ_RESULTADOS_6F.csv` |
| Matriz de CLI | `MATRIZ_CLI_6F.csv` |
| Matriz de WAV | `MATRIZ_WAV_6F.csv` |
| Evidencia JSON | `evidence/*.json`, `evidence/matriz_*.csv` |
| Motores 6F | `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py`, `motores/MOTOR_SEP_SDV-SDI_EVO.py`, `motores/sdv_sdi_mqr_engine.py` |
| Módulos nuevos | `motores/atribucion_6f.py`, `motores/wav_integridad_6f.py` |
| Reproducción | `README.md`, `requirements.txt`, `scripts/*.py` |

## Resumen numérico

* Atribución: 31/31 por motor en desarrollo (93 filas) y 28/28 por motor en
  reserva (84 filas).
* CLI: 57/57 (desarrollo) y 30/30 (reserva); bloqueo con exit 1, 0 WAV y sin
  informe; permiso registrado sin shift ni cambio de polaridad.
* WAV: 39/39 y 10/10; perfil admitido PCM 8/16/24/32, float 32/64 y
  `WAVE_FORMAT_EXTENSIBLE` con GUID PCM/FLOAT.
* MQR S7: 6C aborta (`ZeroDivisionError`, exit 2); 6E y 6F publican `null`
  explícito; 6F bloquea sin permiso por guía periódica no identificable.
* DSP: PCM idéntico a 6E en 24/24 y a 6C en 23/24 (1 no comparable).

## Advertencias para el auditor

1. Los tres motores comparten `atribucion_6f.measure`: sus coincidencias no son
   validaciones independientes.
2. La reserva se definió después del congelamiento y no se usó para ajustar,
   pero fue construida por el mismo autor y comparte portadora de ruido.
3. No se usaron canciones reales; no se probó Termux ARM64 ni archivos largos.
4. `UNIQUE` significa «no se detectó réplica por encima del piso publicado», no
   unicidad matemática.
5. La detección TOCTOU no previene escrituras concurrentes.

---

## Informe de implementación

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

---

## Informe de validación con reserva independiente

# Etapa 6F · Validación con reserva independiente

Independiente respecto del ajuste: la reserva se definió **después** del commit
de congelamiento `5d344e1`, con semilla y construcciones nuevas, y no se cambió
ni el código ni ningún umbral después de ver sus resultados. No equivale a una
validación por un tercero.

## 1. Separación de conjuntos

| Conjunto | Definición | Uso | Casos |
|---|---|---|---|
| Desarrollo | `scripts/estimulos_6f.py`, semillas 609174223 y 20261119 | ajuste del detector | 24 de 1 s + 7 de 4 s |
| Reserva | `scripts/reserva_6f.py`, semilla 770315 | sólo evaluación | 28 (1 s y 2 s) |

La reserva incluye: casos positivos (sin réplica, con retardo, con polaridad
invertida, con Mid nulo), negativos (guía no relacionada), ambiguos (réplicas
de 0,125 / 0,25 / 0,5 exclusivas de L y de R, dos orígenes, cambios por tramos,
señal periódica), insuficientes, asimetría de ganancia L/R, retardos de ambos
signos (±1 901), retardo de borde (+4 000), guía parcial, nivel bajo, guía
débil, amplitud variable, WAV válidos e inválidos y CLI con y sin autorización.

## 2. Atribución

**Desarrollo: 31/31 por motor (93/93). Reserva: 28/28 por motor (84/84).**
Matriz cruda completa en `MATRIZ_RESULTADOS_6F.csv`, `evidence/matriz_dev.csv`
y `evidence/matriz_reserva.csv`; detalle por canal, cubierta, piso y rivales en
`evidence/atribucion_dev.json` y `evidence/reserva_atribucion.json`.

Subconjunto representativo de la reserva (los tres motores coinciden porque
comparten el estimador):

| Caso | Esperado | Observado | k | Piso L / R |
|---|---|---|---|---|
| `res_clean_1s` | UNIQUE, k=0 | UNIQUE | 0 | 0,0888 / 0,0877 |
| `res_clean_2s` | UNIQUE, k=0 | UNIQUE | 0 | 0,0767 / 0,0706 |
| `res_delay_pos_1901` | UNIQUE, k=+1901 | UNIQUE | +1901 | 0,0767 / 0,0706 |
| `res_delay_neg_1901` | UNIQUE, k=−1901 | UNIQUE | −1901 | 0,0767 / 0,0706 |
| `res_shift_pad_567` | UNIQUE, k=−567 | UNIQUE | −567 | 0,0767 / 0,0706 |
| `res_right_replica_.125_777` | AMBIGUOUS | AMBIGUOUS | — | L medido, R ambiguo |
| `res_left_replica_.125_777` | AMBIGUOUS | AMBIGUOUS | — | L ambiguo, R medido |
| `res_right_replica_.25_-450` | AMBIGUOUS | AMBIGUOUS | — | idem |
| `res_left_replica_.5_1901` | AMBIGUOUS | AMBIGUOUS | — | idem |
| `res_dos_origenes` | AMBIGUOUS | AMBIGUOUS | — | — |
| `res_por_tramos` | AMBIGUOUS | AMBIGUOUS | — | — |
| `res_periodica_64` | AMBIGUOUS | AMBIGUOUS | — | — |
| `res_lr_distintos_58` | AMBIGUOUS | AMBIGUOUS (`L=0`, `R=58`) | — | — |
| `res_marcas_unicas` | UNIQUE, k=0 | UNIQUE | 0 | 0,0877 / 0,0785 |
| `res_no_relacionada` | INSUFFICIENT_SIGNAL | INSUFFICIENT_SIGNAL | — | — |
| `res_silencio` / `res_dc` | NON_INFORMATIVE | NON_INFORMATIVE | — | — |
| `res_nan` | ERROR | ERROR | — | — |
| `res_retardo_borde_4000` | UNIQUE, k=+4000 | UNIQUE | +4000 | 0,0767 / 0,0706 |
| `res_guia_parcial` (75 %) | UNIQUE, k=0 | UNIQUE | 0 | — |
| `res_mid_nulo` (L=−R) | UNIQUE, k=0 | UNIQUE | 0 | 0,0767 / 0,0767 |
| `res_amplitud_variable` | UNIQUE, k=0 | UNIQUE | 0 | — |
| `res_replica_bajo_piso` | UNIQUE **o** AMBIGUOUS | UNIQUE (0,03 < piso) | 0 | 0,0767 / 0,0707 |

Casos relevantes del conjunto de desarrollo: `right_rival_.125` → AMBIGUOUS
(defecto prioritario heredado), `different_lr` → AMBIGUOUS con canales 0 y 33,
`shift_567` → UNIQUE k=−567 (defecto C), `dual_173` / `dominant_.25` /
`piecewise_53` / `periodic_32` → AMBIGUOUS, `unique_marks` → UNIQUE 0,
`delay_boundary_+3000` → UNIQUE +3000.

## 3. Capacidad de detección declarada

El piso (`replica_detection_floor`) es la mínima amplitud relativa al Mix que
el caso habría podido detectar con el estadístico usado, peor caso entre los
retardos examinados:

| Duración | Piso observado |
|---|---|
| 1 s | 0,088 – 0,089 |
| 2 s | 0,071 – 0,077 |
| 4 s | 0,049 – 0,058 |

Consecuencia honesta: una réplica de 0,125 sí se detecta; una de 0,03 no se
detecta en 2 s y el caso se declara `UNIQUE` con el piso publicado. No se
presenta como unicidad absoluta.

## 4. CLI

**Desarrollo: 57/57 filas. Reserva: 30/30 filas.** Cada fila verifica código de
salida, número de WAV, existencia de informe, diagnóstico publicado, registro
del permiso y finitud del PCM. `MATRIZ_CLI_6F.csv`.

* Bloqueados sin permiso: `dual_173`, `right_rival_.125`, `different_lr`,
  `silent`, `shift_567` (por retardo), `res_dos_origenes`,
  `res_right_replica_.125_777`, `res_por_tramos` → exit 1, 0 WAV, sin informe.
* Con permiso: exit 0, 2 WAV, informe con `permission=cli_allow_misaligned` y
  `verdict=ALLOWED_EXPLICIT`.
* Invalidados incondicionalmente incluso con permiso: guía truncada, muestras
  NaN, WAV con `data` inconsistente → exit 1, 0 WAV.
* El permiso no cambia el PCM ni el diagnóstico: las repeticiones son
  deterministas (mismos hashes) y `action.applied_shift_samples = 0`,
  `polarity_changed = false`.

## 5. Integridad WAV

**Desarrollo: 39/39 (13 válidos, 26 inválidos). Reserva: 10/10 (3 válidos,
7 inválidos).** `MATRIZ_WAV_6F.csv`, `evidence/wav_auditoria.json`,
`evidence/reserva_wav.json`. Se aceptan PCM 8/16/24/32, float 32/64 y
`WAVE_FORMAT_EXTENSIBLE` con GUID PCM/FLOAT, incluido `valid_bits` 24 en
contenedor de 32. Se rechazan truncamientos, sobrepasos de `data`, `RIFF` con
tamaño incoherente, padding ausente, GUID comprimido, `cbSize` corto,
`valid_bits` imposible, máscara incoherente, alineación o `byte_rate` erróneos,
`data` duplicado, `fmt` posterior a `data`, `data` vacío, RF64, RIFX, A-law,
profundidades no admitidas, NaN y `fact` inconsistente.

TOCTOU: reemplazo tras abrir → detectado (las muestras siguen siendo las del
objeto validado); modificación en sitio → detectada por identidad y SHA-256;
sustitución entre sondeo y lectura → `ERROR` y bloqueo.

## 6. S7 y no regresión

S7: 6C aborta con `ZeroDivisionError` (exit 2, 2 WAV parciales, sin informe);
6E y 6F terminan (exit 0 con permiso), publican informe y crestas `null`
explícitas. 6F sin permiso bloquea porque la guía periódica es no
identificable.

DSP: 23/24 comparaciones idénticas a 6C (la restante no es comparable porque 6C
aborta en `MQR/side`) y 24/24 idénticas a 6E, con formas y crestas iguales. El
AST muestra que sólo cambian `_combine`, `analyze_alignment`, `run_experiment`
(compuerta), `write_reports` (campo nuevo), y en MQR `build_validation_status`
y `CandidateMetrics` heredado de 6E; ninguna función de STFT, máscaras, consenso
o reconstrucción cambia, y ninguna constante de nivel superior cambia.

## 7. Límite de esta validación

Los tres motores comparten `atribucion_6f.measure` y `combine_channels`: sus
resultados coincidentes **no** son tres validaciones independientes del mismo
algoritmo, sino tres integraciones del mismo estimador. La reserva comparte
portadora de ruido entre casos y no es una muestra estadísticamente
independiente. No se probaron canciones reales.

---

## Auditoría de CLI y bloqueos

# Etapa 6F · Auditoría de CLI y bloqueos

Ejecutado realmente (subprocess, no inspección estática):
`scripts/auditoria_cli_6f.py` (57 filas, desarrollo) y el bloque CLI de
`scripts/validar_reserva_6f.py` (30 filas, reserva). Evidencia:
`evidence/cli_6f.json`, `evidence/reserva_cli.json`, `MATRIZ_CLI_6F.csv`.

## 1. Regla aplicada

`alignment_gate(records, blocking, allow, log)` decide antes de crear el
directorio de corrida:

| Estado del diagnóstico | Sin permiso | Con `--allow-misaligned` |
|---|---|---|
| `ALIGNED` / `WARNING` (UNIQUE) | procesa | procesa (permiso no aplica) |
| `MISALIGNED` (UNIQUE con k) | bloquea | procesa, sin shift |
| `AMBIGUOUS` | bloquea | procesa, sin shift |
| `INSUFFICIENT_SIGNAL` | bloquea | procesa, sin shift |
| `NON_INFORMATIVE` | bloquea | procesa, sin shift |
| `ERROR` (incluye NaN y contenedor inválido) | bloquea | **bloquea** |

El permiso queda registrado en el informe como
`alignment_gate.permission = "cli_allow_misaligned"`,
`verdict = "ALLOWED_EXPLICIT"`, con la lista de estados permitidos y
`does_not_bypass = ["validacion_fisica_wav", "datos_no_finitos",
"integridad_identidad_archivo"]`. En MQR el mismo permiso se registra como
ítem `misalignment_user_authorized` de `validation_status`.

## 2. Qué se comprobó en cada modalidad

| Comprobación | Resultado |
|---|---|
| Código de salida por caso y motor | 57/57 y 30/30 coinciden con la expectativa |
| WAV generados cuando el caso se bloquea | 0 en todas las filas bloqueadas |
| Informe generado cuando el caso se bloquea | ausente en todas |
| Informe y 2 WAV cuando se permite | presente en todas las filas permitidas |
| PCM finito en las corridas permitidas | sí en las 30 filas |
| `action.applied_shift_samples` | 0 en todas |
| `action.polarity_changed` | `false` en todas |
| Determinismo con permiso (3 casos × 3 motores) | PCM, exit y diagnóstico idénticos |
| PCM 6F con permiso vs 6E con permiso | idéntico (12/12 pares) |
| Permiso no altera el diagnóstico | igual atribución y mismo k |

Casos bloqueados por defecto en la matriz: `dual_173`, `right_rival_.125`,
`different_lr`, `silent`, `shift_567` (retardo real, política heredada de
bloqueo), `res_dos_origenes`, `res_right_replica_.125_777`, `res_por_tramos`.
Invalidados incluso con permiso: `nonfinite`, `truncated`, `nan_samples`.

## 3. Límites

* No se ejecutaron pruebas de carrera de sustitución de archivo durante una
  corrida completa de CLI; la detección TOCTOU se probó a nivel del módulo de
  integridad (ver `AUDITORIA_WAV_6F.md`).
* No se recorrió toda la matriz de modos (`dry_run`, `analysis_only`,
  `single_file`, `self_test`) ni sus permisos heredados; sólo el modo usado,
  `full_processing`.
* Un código de salida correcto no se considera prueba de seguridad: por eso
  cada fila conserva artefactos, diagnóstico, permiso y PCM.
* El bloqueo depende del diagnóstico: si el estimador declarase `UNIQUE`
  erróneamente, la CLI no lo vetaría. 6F reduce ese riesgo con la prueba de
  réplica y el piso declarado, pero no lo elimina.

---

## Auditoría de integridad WAV

# Etapa 6F · Auditoría de integridad WAV

Ejecutado: `scripts/auditoria_wav_6f.py` (39 casos construidos byte a byte) y
el bloque WAV de `scripts/validar_reserva_6f.py` (10 casos nuevos). Evidencia:
`evidence/wav_auditoria.json`, `evidence/reserva_wav.json`,
`MATRIZ_WAV_6F.csv`.

## 1. Perfil admitido

| Aceptado | Condición |
|---|---|
| RIFF/WAVE little-endian clásico | tamaño RIFF = tamaño físico − 8, sin bytes extra |
| PCM entero 8/16/24/32 | `block_align = canales·ancho`, `byte_rate = rate·align` |
| IEEE float 32/64 | `fact`, si existe, igual a frames |
| `WAVE_FORMAT_EXTENSIBLE` | `cbSize ≥ 22`, GUID PCM (`01…`) o FLOAT (`03…`), `valid_bits ≤ bits`, máscara coherente |
| `valid_bits` < contenedor | se escala por bits válidos (p. ej. 24 en 32) |
| Chunks adicionales (`LIST`, `fact`, …) | tamaño y padding dentro del RIFF |

| Rechazado | Motivo |
|---|---|
| RF64, RIFX | fuera de perfil |
| Formatos comprimidos (A-law, µ-law, ADPCM…) | sólo PCM/float |
| GUID de subformato distinto de PCM/FLOAT y alias `00000000-…` | no verificable |
| PCM 64 bits, float de 16 bits, profundidades no admitidas | fuera de perfil |
| `data` antes de `fmt`, `fmt` o `data` duplicados, falta de alguno | estructura inválida |
| `data` de tamaño 0 | sin muestras |
| `data` no múltiplo de `block_align` | geometría incoherente |
| Chunk que desborda el RIFF, sin byte de padding, tamaño > 2³¹−1 | límites físicos |
| `RIFF` declarado distinto del tamaño físico, bytes extra al final | truncamiento o relleno |
| `valid_bits > bits`, `cbSize < 22`, máscara con popcount ≠ canales o bits fuera de las 18 posiciones estándar | cabecera incoherente |
| `block_align` o `byte_rate` erróneos | geometría incoherente |
| `fact` distinto de frames | metadato incoherente |
| Muestras float no finitas | datos inválidos |
| Geometría distinta de la que reporta libsndfile, o subtipo distinto del `fmt` | desacuerdo cabecera/decodificador |

## 2. Resultados

* Desarrollo: **39/39** expectativas (13 válidos aceptados, 26 inválidos
  rechazados).
* Reserva: **10/10** (3 válidos, 7 inválidos).
* Todos los rechazos informan el motivo concreto; ninguno se aceptó por el
  simple hecho de que el decodificador pudiera abrir el archivo.
* Los archivos válidos decodifican con la misma forma y finitud que
  libsndfile, y el PCM se obtiene del mismo descriptor validado.

## 3. TOCTOU

`open_validated` abre el archivo una vez, hace `fstat`, valida el contenedor,
hashea los bytes y decodifica el payload **desde ese mismo descriptor**.
Después:

| Escenario | Resultado observado | Alcance |
|---|---|---|
| Reemplazo de la ruta tras abrir | las muestras leídas siguen siendo las del objeto validado; `check_unchanged` detecta identidad y SHA distintos | detecta, no previene |
| Modificación en sitio tras abrir | `check_unchanged` detecta identidad (mtime) y SHA distintos | detecta, no previene |
| Sustitución entre `probe_file` y `analyze_alignment` | `sha256` del sondeo ≠ `sha256` leído → `ERROR` → CLI bloquea | detecta y bloquea |

**No se afirma** que la validación elimine cualquier manipulación concurrente:
no hay bloqueo de archivo, ni copia inmutable, ni autenticación criptográfica del
contenido. Una escritura concurrente *durante* la lectura puede producir un
error de lectura (que se rechaza) o un contenido mixto que sólo se detectaría
por la comparación de SHA al final de la alineación.

## 4. Límites

* No se probaron todos los chunks posibles ni combinaciones de `LIST`/`bext`.
* No se probaron archivos > 2 GB ni RF64 (rechazado por perfil).
* No se validó la coherencia de `channel mask` contra convenciones de orden de
  canales más allá del popcount y el conjunto estándar.
* La decodificación carga el payload completo en memoria; el pico de memoria
  crece con la duración del archivo y no se midió a escala larga.

---

## Diagnóstico MQR S7

# Etapa 6F · MQR S7: división indefinida al finalizar

Ejecutado: `scripts/mqr_s7_6f.py`. Evidencia: `evidence/mqr_s7.json`.
Estímulo reconstruido desde la receta publicada de S5
(`S5_STEREO_VALIDATION/signals/manifest.json`):

```
n = 0..176399 (4 s, 44 100 Hz)
s_f[n] = sin(2π((f·n) mod 44100)/44100);  a=s441, b=s882, c=s1323
v = 0.16a + 0.08b;  i = 0.07a + 0.12c
V = (v, −v);  I = (i, −i);  Mix = V + I
```

**Reproducción verificada:** `mix_mid_rms = 0,0`, `mix_lr_peak = 0,3303473`.
El pico coincide con el `peak_mix = 0.330347` registrado por la auditoría 6D
para S7, así que el fixture es el mismo caso histórico y no una aproximación.

## 1. Condición matemática

La métrica heredada calcula

```
crest_factor = pico L/R ÷ RMS de Mid        (Mid = (L+R)/2)
```

y acumula `sum_*2` sobre la **media de canales** y `peak_*` sobre el máximo
absoluto multichannel. Para S7, Mid es idénticamente cero (L = −R) aunque L y R
sean no nulos. El cociente no está definido para cualquier pico finito, no sólo
cuando el pico es cero. La guarda de 6C protegía `n_samples`, no el denominador.

## 2. Resultado exacto por versión

| Versión | Exit | Aborto | Informe | WAV | `crest_factor_sdv` / `_mix` | `validation_status.overall` |
|---|---|---|---|---|---|---|
| 6C (MQR) | **2** | `ZeroDivisionError: float division by zero` en `crest_factor_sdv` | no | 2 parciales en `_aborted` | no publicadas | no calculado |
| 6E (MQR) | 0 | no | sí | 2 | `null` explícito | `fail` |
| 6F (MQR) | 0 | no | sí | 2 | `null` explícito | `fail` |

`crest_factor_basis` declara literalmente `"LR peak / Mid RMS; null if
undefined"`. **No se introdujo epsilon** ni se sustituyó Mid por otra referencia:
si el cociente no está definido, se publica `null` y el informe sigue adelante.

`overall = fail` en 6E y 6F no es un aborto: refleja que la validación de
alineación queda en `AMBIGUOUS` (ítems `alignment_P1/vocal` y
`alignment_P1/instrumental`) aun con permiso registrado. El procesamiento
termina, escribe WAV e informe, y el permiso consta como `recorded`.

## 3. Comportamiento de 6F con el mismo estímulo

* **Sin permiso:** exit 1, sin WAV y sin informe. La guía es una suma de tonos
  exactamente periódicos (periodo base 441 muestras): cualquier retardo
  múltiplo del periodo produce la misma guía, por lo que el reloj es
  genuinamente no identificable. 6F se abstiene (`AMBIGUOUS`), a diferencia del
  `MISALIGNED −3999,8 ms` histórico, que era una afirmación sin fundamento.
* **Con permiso:** exit 0, 2 WAV, informe completo y crestas `null`. Idéntico
  comportamiento observable que 6E en este caso, con el canal y el motivo
  publicados por canal (`channel_states` L/R = `AMBIGUOUS`).

Hardened y EVO reproducen el mismo patrón (6C/6E con permiso: exit 0,
`AMBIGUOUS`; 6F sin permiso: exit 1). No hay aborto por la métrica en ninguno
de los tres candidatos 6F.

## 4. Estabilidad y consecuencias

* La ejecución completa con S7 dura ~1,3 s por motor y no aborta; el RSS máximo
  del arnés fue 51 740 KiB y el de los hijos 250 044 KiB.
* Un `null` explícito permite distinguir «no medible» de «medido y cero», que es
  la diferencia que 6C perdía al abortar.
* El límite permanece: cualquier métrica basada en Mid es degenerada para
  material lateral puro. 6F no propone un indicador alternativo; sólo evita que
  el informe se pierda y que el valor se falsifique.
* No se probaron otras entradas degeneradas (Mid casi nulo) más allá de los
  controles de 6D; el comportamiento cerca del cero no se caracterizó aquí.

---

## Análisis estéreo L/R

# Etapa 6F · Análisis estéreo L/R

## 1. Regla

Cada canal se mide por separado con la guía de su mismo canal. Nunca se
construye Mid, Side ni mono para inferir el reloj, y no se aplica ningún shift
ni corrección de polaridad (`action.shift_authorized=false`,
`applied_shift_samples=0`, `polarity_changed=false`).

El agregado `combine_channels` distingue cinco desenlaces:

| Agregado | Condición | Retardo publicado |
|---|---|---|
| `MEASURED_AGREEMENT` | todos los canales medidos, mismo k y mismo signo de ρ | sí (el del canal más débil) |
| `CHANNEL_DISAGREEMENT` | canales medidos con k distinto | **no**; se publican `channel_lags` por canal |
| `CHANNEL_POLARITY_CONFLICT` | mismo k, signos de ρ opuestos | no |
| `INCOMPLETE_CHANNEL_EVIDENCE` | un solo canal medido | no; `partial.measured` / `partial.not_measured` |
| `MEMBER_AMBIGUITY_OR_CONFLICT` | algún canal ambiguo | no; se conserva qué canal pudo medirse |

Un canal insuficiente nunca se rellena con el otro; una ambigüedad de un canal
no se resuelve por el acuerdo del otro.

## 2. Casos verificados

| Caso | L | R | Agregado |
|---|---|---|---|
| `side` (L=−R) | UNIQUE 0 | UNIQUE 0 | UNIQUE 0 |
| `side_output` (Mix lateral, guía no lateral) | medido 0 | insuficiente | INSUFFICIENT_SIGNAL |
| `different_lr` (L intacto, R desplazado 33) | UNIQUE 0 | UNIQUE 33 | **AMBIGUOUS** (`channel_lags`) |
| `res_lr_distintos_58` (reserva) | UNIQUE 0 | UNIQUE 58 | **AMBIGUOUS** (`channel_lags`) |
| `right_rival_.125` | UNIQUE 0 | AMBIGUOUS | **AMBIGUOUS** |
| `left_rival_.125` | AMBIGUOUS | UNIQUE 0 | **AMBIGUOUS** |
| `res_right_replica_.125_777` | UNIQUE 0 | AMBIGUOUS | **AMBIGUOUS** |
| `res_asimetria_ganancia` (R a 0,3) | UNIQUE 0 | UNIQUE 0 | UNIQUE 0 |
| `res_mid_nulo` (L=−R, ruido) | UNIQUE 0 | UNIQUE 0 | UNIQUE 0 |

## 3. Qué cambió respecto de 6E

* 6E convertía `different_lr` en `INSUFFICIENT_SIGNAL`: el cuarto bloque de R no
  producía retardo y la regla `states != {'UNIQUE'}` anulaba el canal completo,
  de modo que el desacuerdo real (0 vs 33) nunca se publicaba. 6F mide ambos
  canales y declara el desacuerdo.
* 6E agregaba con `lags` anónimos (lista), sin nombres de canal. 6F agrega con
  diccionario por canal, de modo que el informe dice **qué** canal mide qué.
* Se conserva la regla conservadora de 6E: no se promedia ni se elige el canal
  «bueno».

## 4. Límites

* Un desacuerdo sólo se detecta si ambos canales son medibles; si uno es
  insuficiente, el resultado es abstención con información parcial, no una
  afirmación de desacuerdo.
* El agregado no distingue «desacuerdo de reloj» de «desacuerdo de contenido»;
  ambos aparecen como `CHANNEL_DISAGREEMENT`.
* No se probaron más de dos canales (el motor sólo acepta mono/estéreo) ni
  geometrías multicanal, ni `WAVE_FORMAT_EXTENSIBLE` con máscaras distintas de
  FL/FR.
* No se modela polaridad inversa como causa física: se informa el conflicto y
  se abstiene, sin corregirla.

---

## No regresión DSP

# Etapa 6F · No regresión DSP

Ejecutado: `scripts/no_regresion_dsp_6f.py`. Evidencia:
`evidence/dsp_no_regresion.json`.

## 1. Comparación de PCM

8 configuraciones × 3 motores = 24 comparaciones, con `--allow-misaligned` en
las tres versiones (6C, 6E, 6F) y el mismo manifiesto por caso. Se comparan
hashes SHA-256 de las muestras decodificadas float64, forma, tasa, finitud, pico
y crestas de MQR.

| Comparación | Resultado |
|---|---|
| 6F vs 6E | **24/24 idénticas** (SDV y SDI) |
| 6F vs 6C | **23/24 idénticas**; 1 no comparable (`MQR/side`, 6C aborta por la división indefinida de cresta) |
| Formas | iguales en todas las comparaciones |
| Crestas MQR | iguales en todas |
| Finitud | todas las salidas finitas |

Casos: `clean`, `side`, `dual_173`, `shift_567`, `right_rival_.125`,
`different_lr`, `4s_clean`, `4s_shift_1000`.

## 2. Auditoría AST

Se comparan todas las definiciones de nivel superior y todas las constantes en
mayúsculas (valores) entre 6F y 6C / 6E.

| Motor vs | Definiciones cambiadas | Constantes cambiadas | Definiciones DSP cambiadas |
|---|---|---|---|
| Hardened / 6E | `_combine`, `analyze_alignment`, `run_experiment`, `write_reports` | ninguna | **ninguna** |
| EVO / 6E | idem | ninguna | **ninguna** |
| MQR / 6E | `_combine`, `analyze_alignment`, `build_validation_status`, `run_experiment` | ninguna | **ninguna** |
| Hardened / 6C | las anteriores + `probe_file`, `build_arg_parser` (heredadas de 6E) + `_attribution_state` añadida | ninguna | **ninguna** |
| EVO / 6C | idem | ninguna | **ninguna** |
| MQR / 6C | idem + `CandidateMetrics`, `stream_level_stats` (corrección de cresta de 6E) | ninguna | **ninguna** |

Ninguna de las definiciones que tocan muestras cambia: `mono_downmix`,
`read_span`, `stft_span_frames`, `OlaStream`, `apply_sfumato_smoothing`,
`TruePeakStream`, `build_band_masks`, `compute_vocal_mask`,
`confidence_and_disagreement`, `consensus_from_masks`, `FramePlan`,
`PairwiseAccum`, `GlobalMaskAccum`, `PearsonAccum`, `mask_stats_stream_*`.

`run_experiment` cambia **sólo** por la compuerta de continuación (antes del
directorio de corrida); `write_reports` sólo añade el campo `alignment_gate`.
`analyze_alignment` y `_combine` son diagnóstico puro.

## 3. Diff reproducible

`scripts/construir_motores_6f.py` regenera las copias desde 6E y reporta
89 (Hardened), 89 (EVO) y 102 (MQR) líneas de diff, correspondientes a cinco
regiones: importación del módulo, `_combine`, `analyze_alignment`, compuerta CLI
y campo de informe (más, en MQR, el ítem de `validation_status`).
`--check` verifica que las copias publicadas coinciden exactamente con lo que
produce el constructor.

## 4. Límites

* Las comparaciones usan `float64` decodificado, no los bytes WAV: dos archivos
  con distinto subtipo pero idénticas muestras aparecerían como iguales (las
  formas y el subtipo se registran aparte).
* No se instrumentaron tensores intermedios de la STFT ni máscaras; la prueba es
  de extremo a extremo sobre las muestras y de estructura sobre el AST.
* No se comparó con el motor v3 original (protegido, no ejecutado en 6F) ni se
  cubrieron todos los modos, parámetros, residual o combinaciones de consenso.
* Los casos son sintéticos de 1 s y 4 s; no se probaron canciones reales.

---

## Recursos y duraciones

# Etapa 6F · Recursos, tiempos y errores

Todas las mediciones son del entorno **Arena** (no de Termux ARM64). Se
obtuvieron con el arnés en subprocess y `resource.getrusage`; no se impusieron
límites de RAM teóricos.

## 1. Entorno

| Elemento | Valor |
|---|---|
| SO / arquitectura | Linux x86_64 (contenedor Arena) |
| CPU | 2 vCPU; hilos OpenMP/OpenBLAS/MKL fijados a 1 |
| Memoria del sistema | 3 939 MB |
| Python | 3.11.2 (`/tmp/sdv6f-env`, `-B`, sin `__pycache__`) |
| numpy / scipy / soundfile / cffi / pycparser | 1.26.4 / 1.13.1 / 0.13.1 / 2.1.1 / 3.12 |
| libsndfile | 1.2.2 |
| Fecha de ejecución | 2026-11-19 |

## 2. Duración y pico de memoria

| Prueba | Duración | RSS del arnés | RSS de hijos |
|---|---|---|---|
| Atribución desarrollo (93 filas) | 14,5 s | 153 544 KiB | — |
| Atribución reserva (84 filas) | 37,1 s | 144 464 KiB | — |
| CLI desarrollo (57 filas) | 41,0 s | 57 472 KiB | 139 980 KiB |
| CLI reserva (30 filas) | incluida en reserva | — | — |
| Integridad WAV (49 casos) | 0,21 s | 90 600 KiB | — |
| MQR S7 (13 corridas) | 12,9 s | 51 740 KiB | 250 044 KiB |
| No regresión DSP (24 comparaciones) | 66,8 s | 86 876 KiB | 253 372 KiB |

## 3. Tamaños de archivo

| Estímulo | Frames | Canales | Formato | Tamaño |
|---|---|---|---|---|
| Caso de 1 s | 44 100 | 2 | float32 WAV | ≈353 KiB |
| Caso de 2 s (reserva) | 88 200 | 2 | float32 WAV | ≈706 KiB |
| Caso de 4 s | 176 400 | 2 | float32 WAV | ≈1,4 MiB |
| S7 | 176 400 | 2 | float32 WAV | ≈1,4 MiB |
| WAV válidos de auditoría | 16–1 024 frames | 1–2 | PCM/float | 44 B–4,1 KiB |

Los WAV de trabajo se generan en directorios temporales; el repositorio sólo
contiene código y evidencia JSON/CSV.

## 4. Errores y excepciones observados

| Dónde | Error | Tratamiento |
|---|---|---|
| 6C, MQR, S7 | `ZeroDivisionError` en `crest_factor_sdv` | reproducido, no corregido en 6C (protegido) |
| 6F, S7 sin permiso | bloqueo por `AMBIGUOUS` | comportamiento esperado |
| Arneses | `AttributeError` con `Cronometro.seconds` antes de salir del `with` | corregido en el arnés |
| Arneses | `ModuleNotFoundError: medidas` al importar el generador de S5 | fixture S7 reescrito autónomo |
| Arneses | `StopIteration` al elegir casos inexistentes en CLI/DSP | corregido en el arnés |
| WAV inválidos | `WaveError` con motivo concreto | esperado |

Ninguna excepción no controlada en los motores 6F durante las 138 corridas de
CLI ni en las 177 filas de atribución.

## 5. Extrapolación

No se extrapolan tiempos ni memoria a Termux ARM64. Los archivos largos
(audio completo) cargan el payload en memoria y no se midieron; el coste de
`correlate` es O(n log n) por ventana y por canal.

---

## Limitaciones y casos fuera de capacidad

# Etapa 6F · Limitaciones y casos fuera de capacidad

Registro de lo que 6F **no** puede sostener. No hay garantía de unicidad
absoluta: se documenta lo detectado y lo que queda fuera de capacidad.

## 1. Ambigüedades fuera de capacidad

| Situación | Comportamiento 6F | Fundamento |
|---|---|---|
| Réplica por debajo del piso (≈0,05–0,09 según duración) | `UNIQUE` con `replica_detection_floor` publicado, o abstención si el piso > 0,35 | el estadístico no puede separarla del nulo |
| Guía periódica o de banda estrecha (tonos, bucles) | `AMBIGUOUS` siempre | la autocorrelación de la guía es ≈1 en el retardo candidato |
| Réplica que sólo aparece en una mitad del archivo | `RIVAL_NOT_CORROBORATED`; la ventana no cuenta como medida | no se acepta un único testimonio |
| Retardo mayor que la ventana de búsqueda (±30 s) o que el solape disponible | no examinado; cobertura < 1 publicada | límite de plantilla |
| Diferencia L/R con un canal insuficiente | abstención parcial (`partial.measured`) | no se infiere del otro canal |
| Contenido no estacionario con guía que cambia de carácter | puede declararse `AMBIGUOUS` pese a existir un retardo dominante por tramo | se publica `piecewise` cuando aplica |
| Silencio, DC o constante | `NON_INFORMATIVE` | no hay información de reloj |
| Muestras no finitas | `ERROR`, bloqueo incondicional | no se procesa |

## 2. Afirmaciones que 6F **no** hace

* No afirma que la validación WAV elimine la manipulación concurrente: sólo la
  detecta cuando el objeto cambia (identidad, SHA-256, tamaño).
* No afirma que `UNIQUE` signifique «no existe réplica»: significa «no se
  detectó réplica por encima del piso publicado».
* No afirma aptitud de producción, ni elige motor ganador, ni integra nada en el
  orquestador.
* No afirma que 6F sea estable en archivos largos ni en Termux ARM64.
* No afirma que las tres coincidencias de motores sean tres validaciones
  independientes: comparten `atribucion_6f.measure`.

## 3. Cobertura no realizada

* Canciones reales: prohibidas en esta etapa.
* Modos de CLI distintos de `full_processing` (`dry_run`, `analysis_only`,
  `single_file`, `self_test`) no se auditaron en 6F.
* Archivos > 2 GB, RF64, multicanal > 2, WAV con `channel mask` no FL/FR.
* Carreras TOCTOU durante una corrida CLI completa (sólo a nivel de módulo).
* Barrido fino de `σ_ρ`, del umbral `z`, del solape 50 % y del criterio de
  corroboración: se fijaron con el conjunto de desarrollo y no se optimizaron.
* Cerca de Mid ≈ 0 (no exactamente 0) en MQR: no caracterizado.
* El ajuste de escala de guías (`g_vocal`, `g_instr`) queda como estaba en 6E.

## 4. Riesgos residuales

1. **Falso `UNIQUE` por réplica bajo el piso**: mitigado con el piso publicado,
   no eliminado. El caso `res_replica_bajo_piso` admite ambos resultados para no
   ocultar el límite.
2. **Falso `AMBIGUOUS` en material periódico**: se prefiere abstención a una
   afirmación errónea; el coste es que material musical con bucles nunca se
   procesará sin permiso explícito.
3. **Carga en memoria** proporcional a la duración; no medida a escala real.
4. **Acoplamiento** de los tres motores al mismo estimador compartido.

---

## Informe de entrega para auditoría independiente

# Etapa 6F · Informe de entrega para auditoría independiente

**Fecha de emisión:** 2026-11-19
**Estado del expediente:** congelado y publicado en GitHub. Este documento **no modifica** el árbol auditado.
**Dictamen registrado:** APROBADO CON LIMITACIONES (sujeto a la auditoría independiente).

Todos los enlaces de auditoría están fijados al commit del árbol auditado
(`d914d179bac682c6830bfe481ddf5ae2e045726e`), no a la rama genérica. Este informe
se publica en un commit posterior, dentro de la misma carpeta; el árbol auditado
permanece inmutable y sus enlaces siguen siendo válidos.

---

## 1. Repositorio GitHub

https://github.com/arielwilliam1986-source/SDV-SDI_SGM

Repositorio **público**: legible sin credenciales ni token.

## 2. Rama exclusiva de la Etapa 6F

- **Nombre:** `arena/89d5c189-sdv-sdi-sgm`
- **Enlace:** https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/89d5c189-sdv-sdi-sgm
- **Puntero remoto:** `git ls-remote refs/heads/arena/89d5c189-sdv-sdi-sgm` coincide con el commit
  de publicación de este informe (el SHA que muestra la cabecera del archivo en GitHub).

## 3. Commit base

```
b72ce49ae787c72a1148bbec95db35dba460d279
```

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b72ce49ae787c72a1148bbec95db35dba460d279

## 4. Commit final del árbol auditado (6F)

```
d914d179bac682c6830bfe481ddf5ae2e045726e
```

- Enlace: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/d914d179bac682c6830bfe481ddf5ae2e045726e
- Fecha: 2026-11-19 12:23:30 +0000

Cadena completa desde la base (todos presentes en la rama):

| Commit | Asunto |
|---|---|
| `5d344e1f7eda9291c47b08b1f0accd0f17644ea0` | Congela implementación 6F |
| `f92f5755c502b1e664d5b89aed0052d67b0dc9fa` | Reserva independiente, matrices, manifiesto e informes |
| `41c525f3921ce0f4c96d226e913334372c0f639c` | Índice de auditoría externa |
| `d914d179bac682c6830bfe481ddf5ae2e045726e` | Tomos de auditoría en texto |

Los commits posteriores a `d914d17` sólo añaden documentación de entrega; no tocan
motores, evidencia ni umbrales.

## 5. Carpeta completa de la Etapa 6F

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO

## 6. Informe de implementación

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/INFORME_IMPLEMENTACION_6F.md

## 7. Informe de validación independiente

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/INFORME_VALIDACION_INDEPENDIENTE_6F.md

## 8. Auditoría CLI

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_CLI_6F.md

## 9. Auditoría de integridad WAV

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_WAV_6F.md

## 10. Diagnóstico MQR S7

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/DIAGNOSTICO_MQR_S7_6F.md

## 11. Análisis estéreo L/R

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/ANALISIS_ESTEREO_LR_6F.md

## 12. Informe de no regresión DSP

https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/NO_REGRESION_DSP_6F.md

**Documentos adicionales de la misma carpeta** (mismo commit):

| Documento | Enlace |
|---|---|
| Recursos y duraciones | `…/RECURSOS_Y_DURACIONES_6F.md` |
| Limitaciones y casos fuera de capacidad | `…/LIMITACIONES_Y_CASOS_UNKNOWN_6F.md` |
| README de reproducción | `…/README.md` |
| Índice de auditoría | `…/INDICE_PARA_AUDITORIA.md` |
| Tomo 1 (todos los informes juntos) | `…/AUDITORIA_6F_TOMO_1_INFORMES.md` |
| Tomo 2 (hashes y matrices) | `…/AUDITORIA_6F_TOMO_2_EVIDENCIA.md` |

Prefijo para todos: `https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/`

## 13. Matriz CSV de resultados

| Matriz | Filas | Enlace |
|---|---|---|
| Atribución (desarrollo + reserva) | 177 | `…/MATRIZ_RESULTADOS_6F.csv` |
| CLI | 87 | `…/MATRIZ_CLI_6F.csv` |
| WAV | 49 | `…/MATRIZ_WAV_6F.csv` |

Enlace directo de la principal:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/MATRIZ_RESULTADOS_6F.csv

## 14. Evidencias JSON principales

Prefijo: `https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/evidence/`

| Archivo | Contenido |
|---|---|
| `atribucion_dev.json` | 31 casos × 3 motores, detalle por canal |
| `matriz_dev.csv` | matriz cruda de desarrollo |
| `reserva_atribucion.json` | 28 casos × 3 motores (post-congelamiento) |
| `matriz_reserva.csv` | matriz cruda de la reserva |
| `wav_auditoria.json` | 39 casos + escenarios TOCTOU |
| `reserva_wav.json` | 10 casos de reserva |
| `cli_6f.json` | 57 filas, determinismo y PCM vs 6E |
| `reserva_cli.json` | 30 filas |
| `mqr_s7.json` | 13 corridas S7, matemática y crestas |
| `dsp_no_regresion.json` | 24 comparaciones PCM + auditoría AST |

Ejemplo directo: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/evidence/mqr_s7.json

## 15. Manifiesto SHA-256

- **Manifiesto:** https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/MANIFEST_6F.json
  Contiene: commit base, rama, hashes de los tres motores 6F, módulos nuevos, scripts, fuentes protegidas (original, 6C, 6E), hashes de los 59 estímulos (desarrollo y reserva), entorno y resumen de resultados.
- **Lista verificable:** https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/d914d179bac682c6830bfe481ddf5ae2e045726e/ETAPA_6F_CIERRE_CORRECTIVO/SHA256SUMS.txt
  Verificación: `cd ETAPA_6F_CIERRE_CORRECTIVO && sha256sum -c SHA256SUMS.txt` → 46/46 OK.

## 16. Archivos añadidos o modificados

`git diff --diff-filter=MD b72ce49…d914d17` → **0** archivos modificados o eliminados: nada
preexistente fue tocado. Todos los archivos de la etapa son adiciones dentro de
`ETAPA_6F_CIERRE_CORRECTIVO/`.

Total en esta publicación: **47 archivos** (46 listados en `SHA256SUMS.txt` + el propio
`SHA256SUMS.txt`).

**Lista autorizada de hashes:** `SHA256SUMS.txt` de este mismo commit. Se verifica con
`cd ETAPA_6F_CIERRE_CORRECTIVO && sha256sum -c SHA256SUMS.txt`.

En la tabla siguiente se dan los hashes exactos de los archivos estables. Los seis
artefactos que se regeneran en cada publicación (este informe, el índice, los dos tomos,
el manifiesto y el propio listado) se remiten a `SHA256SUMS.txt`, porque un archivo no
puede contener su propio hash final.

| Ruta (dentro de `ETAPA_6F_CIERRE_CORRECTIVO/`) | SHA-256 |
|---|---|
| `ANALISIS_ESTEREO_LR_6F.md` | `9359b5ba9ae28b62e0accff7abad27fa7fe08d98cb07969aed8a77f6dc151523` |
| `AUDITORIA_6F_TOMO_1_INFORMES.md` | ver `SHA256SUMS.txt` |
| `AUDITORIA_6F_TOMO_2_EVIDENCIA.md` | ver `SHA256SUMS.txt` |
| `AUDITORIA_CLI_6F.md` | `c8f5d2af61d530a7e3c4a40f0a07f0be4ae967f0e052abd0cb7bf671ac4201c6` |
| `AUDITORIA_WAV_6F.md` | `0ec7db71b040d67f39516c35c4d6e1580180bd51651eb65c93e1369307952e4d` |
| `DIAGNOSTICO_MQR_S7_6F.md` | `736942fe3d9cdabcd66e45c4f949029d56eff858f0d2069a5c3fdbc1f98f0ea2` |
| `ENTREGA_6F.md` | ver `SHA256SUMS.txt` |
| `INDICE_PARA_AUDITORIA.md` | ver `SHA256SUMS.txt` |
| `INFORME_IMPLEMENTACION_6F.md` | `1b8351d0c94490fdaf279a6d096fed72c2f8de1b4f408c9c5a1d6ffb50d8e6e5` |
| `INFORME_VALIDACION_INDEPENDIENTE_6F.md` | `2a7a9ce6eb856e183a78628a2b96933a86ae4b27be4eb53aa7aa886c09a1bbcf` |
| `LIMITACIONES_Y_CASOS_UNKNOWN_6F.md` | `45e88c7bf5afa30dbc24d17e05c33809184779676b8f13fb95fa3b574a2f6571` |
| `MANIFEST_6F.json` | ver `SHA256SUMS.txt` |
| `MATRIZ_CLI_6F.csv` | `9ff196b2deea7902a9652ada4923215b0ddbc94efd8869b83749a4301d1c66d3` |
| `MATRIZ_RESULTADOS_6F.csv` | `cdf120a8e5e5fef56caabec849aefb96395fcbc130195593029406b4689de7cf` |
| `MATRIZ_WAV_6F.csv` | `e4fbd79fe97b5054920c233577135aaf2d7486ba6089d2174256757cfb21e42a` |
| `NO_REGRESION_DSP_6F.md` | `d8dd4ae37c03104747e94f0b339918a4ef2aa21232ffeca9fa2b21fa59cd68d5` |
| `README.md` | `9db73e26672cb3b68236a080e496080087780ef05da67fdae2ab770c7ec858c4` |
| `RECURSOS_Y_DURACIONES_6F.md` | `61b54bb4e28f941a75f9e1387213209a63367ea56253f9ab6b1cb092716210b0` |
| `SHA256SUMS.txt` | ver `SHA256SUMS.txt` |
| `evidence/atribucion_dev.json` | `8b453ecc6ad597e4ec13bae4eebf1046e9b6d49c3b0330f8a8bcac52dd36da31` |
| `evidence/cli_6f.json` | `3ed3f3e0dd44d344404d3d131e0d3aebbcb4cd65874708b1a005513f518e01c3` |
| `evidence/dsp_no_regresion.json` | `009cb407af6bb931e7beaa881d83682251500d6803edb492e4c6a9e20f165fcb` |
| `evidence/matriz_dev.csv` | `3c34868150a47f4d63d2d35ea4cba34125d24bd07a592e7208361018111a4dee` |
| `evidence/matriz_reserva.csv` | `29439dfa6265664d23f017a6b95a5507886d614137a5a2f4f570ad2e3f0a465d` |
| `evidence/mqr_s7.json` | `e688c8b7ce0ccbe00218b15e7e2bc267d03cdc0c58bd0d20516851fb81d4be8b` |
| `evidence/reserva_atribucion.json` | `e9a6a737cec2697cc03466bc7c5e0f512579e5a8a55047669e096287f6df07c4` |
| `evidence/reserva_cli.json` | `f862dc07f7e6f23898b17e118c2954519fd336132ac274531243c35cb5b0e9c8` |
| `evidence/reserva_wav.json` | `0758da36df5078f451649c9648e733490b67f3110aba4bf87c26b93f4d69be71` |
| `evidence/wav_auditoria.json` | `5ef794b44b236e60a3839b4c732b1cf0748b281dced95d1d067b8ecb8c74b56a` |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | `6084c68fdd88c9ba1b77663f4ec217de0800b1ffeb2e322c2fbe8ffcc019beae` |
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | `8b74211dda8f34f7b563a7426fb68a837d424016ca03a4f9aead3bdfb0b09d12` |
| `motores/atribucion_6f.py` | `6628cd82cba3f2324ab2a114918f93ef6e9a777ca2d8fbcb4712cd273b8487ec` |
| `motores/sdv_sdi_mqr_engine.py` | `0867768e2e7116f0b3210a839aad31adf37092279b91ae4eb4f7931141e0224f` |
| `motores/wav_integridad_6f.py` | `243ba66381f1e949b624bb353e5b23ce65cef6e538b41fb2d48ab932415ec048` |
| `requirements.txt` | `ac62a9ac6bdf158f58548373bf65817072c145588f579a44666611acbd744b21` |
| `scripts/auditoria_cli_6f.py` | `a3a7160fd33b7e0438a015189de02345582cd306b006359ccb4a2c9c75106a25` |
| `scripts/auditoria_wav_6f.py` | `14c63534bceaba32e699d357a2a291bd4f018f6ba16009f9b5fcc277b874bedb` |
| `scripts/comun_6f.py` | `d36e2246644ae000f406a5a7670af375319a8c2c19c83222540f21d2f0e67efb` |
| `scripts/consolidar_6f.py` | `6c66e9b4f12ba0c6df6a47b0b3e8db8b3942278dcc1d67fd27878c61e60c7f50` |
| `scripts/construir_motores_6f.py` | `aca2c25211ad09f3788a9d169559eddfbfdd34bbd5e090a4fcc0fd01545add33` |
| `scripts/empaquetar_auditoria_6f.py` | `2c883be00de4a8cecce05ee64c6ce7ffadd78706506e346687911883f077221d` |
| `scripts/estimulos_6f.py` | `300b03d1e26dd60d21d08c883d8e38dced063eb9b01829bf4d29b3e2b69ab946` |
| `scripts/mqr_s7_6f.py` | `bab553784737bd5d3fa449b8259db59788c23db3e42589df5d1991aa02bb9885` |
| `scripts/no_regresion_dsp_6f.py` | `48d2193f8db7ea8cb525067e0bfcbda62bf804795a482a60afa7b6f1b90bba36` |
| `scripts/reserva_6f.py` | `ac13963e51a0b37f41d3e577d70300f1917817594b06a6aa60fb655461ff38c9` |
| `scripts/validar_dev_6f.py` | `fc8740b2d1a12487ff7dfe9ee5d47fc4afccd35d9ba98f07cfc00392c756f6eb` |
| `scripts/validar_reserva_6f.py` | `962ebf618c171e3002dc1bf09009fe141b6f94a9258ed6a900b6a2d7dbf0f73d` |

---

# Confirmaciones expresas

## a) La rama parte del commit base autorizado

`git rev-parse 5d344e1^` = `b72ce49ae787c72a1148bbec95db35dba460d279`.
`git merge-base --is-ancestor b72ce49… d914d17…` = verdadero.
El primer commit de la etapa tiene a la base como padre directo, sin commits ajenos intermedios.

## b) Etapas anteriores y fuentes originales intactas

`git diff --name-only b72ce49..d914d17`, filtrado fuera de `ETAPA_6F_CIERRE_CORRECTIVO/` → **cero archivos**.
No se tocó `Proyecto SDV-SDI_SGM/`, `ETAPA_6C_…`, `ETAPA_6D_…`, `ETAPA_6E_…` ni `S5_STEREO_VALIDATION/`. El manifiesto 6F registra además el SHA-256 de esas fuentes protegidas.

## c) No se modificó el DSP

- Las tres copias 6F se generan desde 6E con `construir_motores_6f.py`: 89 / 89 / 102 líneas de diff, sólo importación, `_combine`, `analyze_alignment`, compuerta CLI y campo de informe.
- Auditoría AST: ninguna definición DSP ni constante de nivel superior cambia.
- PCM: idéntico a 6E en 24/24 comparaciones; a 6C en 23/24 (la restante no es comparable porque 6C aborta en `MQR/side`).

## d) La reserva se ejecutó después de congelar

- Congelamiento de implementación: `5d344e1`.
- Reserva definida y validada: `f92f575`, posterior; ejecutada después (37,1 s, semilla 770315, 28 casos).
- Ningún umbral ni línea del detector se cambió después de ver sus resultados.

## e) Fallos, casos no resueltos y limitaciones

**Fallos encontrados y corregidos**

1. Falso `UNIQUE` en `right_rival`: umbral rival 0,1124 frente a puntuaciones reales 0,103 / 0,099 / 0,090, por tamaño efectivo sesgado ≈1,95×.
2. Pérdida de información L/R en `different_lr`: 6E devolvía `INSUFFICIENT_SIGNAL` y nunca publicaba el desacuerdo 0 vs 33.
3. Retardo uniforme de 567 no recuperado por la reserva 6E.
4. TOCTOU entre validación y lectura de WAV.
5. MQR S7 abortando por `ZeroDivisionError` en `crest_factor_sdv`.

**No resueltos / fuera de capacidad**

- Réplicas por debajo del piso 0,049–0,089 según duración (se publica el piso; `UNIQUE` no implica unicidad matemática).
- Material periódico: siempre `AMBIGUOUS` (abstención deliberada).
- Retardos fuera de ±30 s o sin solape suficiente; ventana de búsqueda limitada.
- Diferencia L/R cuando un canal no es medible: abstención parcial, sin inferencia.
- Mid ≈ 0 (no exactamente 0) en MQR: no caracterizado.
- `g_vocal` / `g_instr`: sin revisar en 6F.
- TOCTOU: se detecta, no se previene.

**Limitaciones de la evidencia**

- Los tres motores comparten `atribucion_6f.measure`: sus coincidencias no son tres validaciones independientes.
- La reserva la construyó el mismo autor y comparte portadora de ruido.
- Sin canciones reales, sin Termux ARM64, sin archivos largos.
- Un código de salida correcto no se considera prueba de seguridad.

## f) Desviaciones respecto de las instrucciones originales

1. **Nombre de rama.** El encargo pedía `arena/etapa-6f-cierre-correctivo`. La sesión está fijada por la plataforma a `arena/89d5c189-sdv-sdi-sgm`. Se detuvo la ejecución al comprobarlo y se continuó con autorización explícita del usuario, sobre una rama que parte del commit base exigido. No se sustituyó por una carpeta dentro de otra rama.
2. **Ajuste del arnés tras el congelamiento.** En la primera ejecución de la reserva, MQR informaba `permission = null` porque el extractor miraba sólo `alignment_gate` (Hardened/EVO) y no el ítem `misalignment_user_authorized` de `validation_status`. Se corrigió **sólo la extracción de evidencia del validador**; ni detector, ni umbrales, ni motores cambiaron. Resultado: 25/30 → 30/30.
3. **Documentación añadida después del cierre** (`INDICE_PARA_AUDITORIA.md`, dos tomos, `empaquetar_auditoria_6f.py`) para facilitar la lectura externa. No añade afirmaciones: reensambla los informes ya publicados.

**Transparencia adicional:** durante la publicación de los tomos, el puntero local de la rama se revirtió accidentalmente al commit base; se restauró desde el remoto y se reaplicaron sólo los cambios nuevos. La historia en GitHub nunca fue reescrita y no se usó `push --force`.

---

## Entregables que no existen

Ninguno de los solicitados falta. Se indica expresamente lo que **no** se produjo: no hay evidencia de canciones reales, ni de Termux ARM64, ni de archivos largos, ni de los modos de CLI `dry_run`, `analysis_only`, `single_file` y `self_test`.
