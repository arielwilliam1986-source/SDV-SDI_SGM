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
