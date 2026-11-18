# SOURCE_AUDIT.md — Fase sintética 1B

**Auditoría de las 10 fuentes entregadas.** Ninguna se ha modificado: cero bytes cambiados
en esta fase. Todos los cambios viven en `src/` del laboratorio.

Etiquetas: `DOCUMENTED_FACT` · `EXPERIMENTAL_RESULT` · `THEORETICAL_DEDUCTION` ·
`HYPOTHESIS` · `UNKNOWN`.

---

## 1. Integridad

Fuente: `Proyecto SDV-SDI_SGM.zip` — 158 768 B —
SHA‑256 `47b7dc8ef1d24847000b60f426c9b7965301e2836c97ad865bff856a875af95f`, idéntico al
esperado en `INTEGRIDAD_FUENTES.json`.

Re-verificación al empaquetar (`src/empaquetar.py`): **10/10 coinciden**
(`hashes/FUENTES_SHA256.txt`, `manifests/MANIFEST_ENTREGABLES.json`).

| # | Fichero | Líneas | SHA‑256 (16) | Papel |
|---|---|---|---|---|
| 1 | `MOTOR_SEP_SDV-SDI.py` | 1939 | `896d3b32446ad8a8` | Motor base (R‑24 aplicado en Fase 1 sobre una **copia**, no aquí) |
| 2 | `MOTOR_SEP_SDV-SDI_EVO.py` | 2114 | `003e698e187b6d62` | Variante evolucionada; añade `hybrid_asymmetric` |
| 3 | `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | 1951 | `5141fb5005656db1` | Variante endurecida; 3 métodos reales |
| 4 | `MOTOR_SEP_SDV-SDI_v3.py` | 2278 | `a0550a01cefb1095` | Variante con taxonomía propia de 4 métodos |
| 5 | `sdv_sdi_mqr_engine.py` | 3505 | `5990ebe41177b62c` | Motor grande; CLI con `--mode` obligatorio |
| 6 | `mix_delta.py` | 402 | `e373c8354b13cb86` | Delta/híbrido y guardas de compatibilidad |
| 7 | `orquestador_maestro.py` | 75 | `ea16344ae64eea4e` | Orquestación por árboles de stems |
| 8 | `preflight_audit.py` | 108 | `e17591fb22133312` | Comprobaciones previas |
| 9 | `MANIFEST_SEP_SDV-SDI.json` | 59 | `23f9982fe93ae4d7` | Manifiesto de pares/guías |
| 10 | `manifest_genio.json` | 48 | `ed83dac7d848c7d5` | Manifiesto real de una canción |

---

## 2. Defectos y hechos confirmados en esta fase, por fichero

Cada entrada indica el bloque que la estableció y la evidencia.

### 2.1 `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` · Bloque A

| Ref | Línea | Hecho |
|---|---|---|
| A‑01 | 123 | `CONSENSUS_ORDER_DEFAULT = "magnitudes_first"` |
| A‑02 | 124‑127 | `METHODS` (3), `DEFAULT = "confidence_weighted_mean"`, `ORDERS` |
| A‑03 | 131‑132 | `BETA = 1.0`, `FLOOR = 1e-6` |
| A‑04 | 819 | `confidence_and_disagreement`: `dis = std(ddof=0)`, `conf = clip(1 − 2·dis, 0, 1)` |
| A‑05 | 837 | `consensus_from_masks` |
| A‑06 | **1520‑1546** | **Colapso:** con `magnitudes_first` los tres métodos reciben el mismo array |
| A‑07 | **1556‑1558** | Solo se escriben las salidas del método predeterminado |
| A‑08 | 1865, 1869 | CLI `--consensus-method`, `--consensus-order` |
| A‑09 | — | `c_k = 1 − media|m_k − m_j|` **sin clip**; medido: nunca negativo, pero **mínimo 0,0000 exacto** en las 36 combinaciones por el piso `1e‑6` |

`EXPERIMENTAL_RESULT` (Bloque A, e2e): `magnitudes_first` produce **1 método distinto de 3**
y **max|Δ| de audio = 0,0 exacto**; `masks_first` produce 3/3 y 2,283·10⁻³. Es decir, la
opción de orden **sí llega a operación**… pero por la rama `masks_first`, mientras que la
predeterminada no cambia ni una muestra.

### 2.2 `MOTOR_SEP_SDV-SDI_EVO.py` · Bloque A

| Ref | Línea | Hecho |
|---|---|---|
| A‑10 | 127 | Añade `hybrid_asymmetric` a los métodos |
| A‑11 | 872 | `consensus_from_masks` |
| A‑12 | 1659‑1692 | Bloque de consenso híbrido asimétrico |
| A‑13 | **1389‑1395** | `[FATAL]` con `--use-residuals` + `per_channel` (`EXIT_VALIDATION`) |
| A‑14 | 2011, 2015 | CLI de consenso |

`EXPERIMENTAL_RESULT`: EVO ≡ hardened también en `masks_first` (huellas de audio
`1cfced96`/`26d82eaf`/`0d32fc24`). `hybrid_asymmetric` sí produce 3/3 métodos distintos
(2,072·10⁻³).

### 2.3 `MOTOR_SEP_SDV-SDI_v3.py` · Bloque A

| Ref | Línea | Hecho |
|---|---|---|
| A‑15 | 175 | `CONSENSUS_METHODS = ("magnitudes_first", "mean", "median", "median_ri")` — **taxonomía distinta** |
| A‑16 | 643 | `magnitudes_first` = mediana de magnitudes **con la fase del promedio** |
| A‑17 | 666 | Toma la fase del promedio (por eso ≡ `mean` en fase **por construcción**) |
| A‑18 | 1851 | CLI de consenso; **no hay `--consensus-order`** |

`EXPERIMENTAL_RESULT`: 4/4 métodos distintos, max|Δ| 9,651·10⁻² (el mayor de los cuatro
motores). Error de fase a K=7 (media, grados): independiente 26,22 / mediana 38,25 /
`median_ri` 29,96.

### 2.4 `sdv_sdi_mqr_engine.py` · Bloque A

| Ref | Línea | Hecho |
|---|---|---|
| A‑19 | 1382 | `consensus_from_masks` |
| A‑20 | — | **No** existe `--consensus-order` |
| A‑21 | 3371 | CLI: elige **qué se escribe**, no qué se calcula: los tres se calculan siempre |
| A‑22 | — | `--mode` es obligatorio; sin él abre un menú interactivo y **se cuelga** (rc=130) |

`EXPERIMENTAL_RESULT`: 3 corridas con `--mode full_processing` → 3 audios distintos
(2,316·10⁻³) porque cada corrida escribe candidatos distintos.

### 2.5 Verificador de alineación · Bloque B

| Ref | Línea | Hecho |
|---|---|---|
| B‑01 | 566‑568 | La clasificación final **ignora `alignment_confidence`** |
| B‑02 | — | Superficie NCC casi empatada: **752/780** casos con `ratio_real_vs_max > 0,999`; gana por ~3·10⁻⁷ |
| B‑03 | — | Desempate de **28 muestras de envolvente = 5,079 ms** (`HYPOTHESIS`) |

`EXPERIMENTAL_RESULT` (780 casos): 554 aciertos, 10 falsos positivos, 0 falsos negativos;
con retardo 0 → 38 `ALIGNED` / 12 `WARNING` / 10 `MISALIGNED`. **Sigue sin parchear.**

### 2.6 `mix_delta.py` · Bloque C

| Ref | Línea | Hecho |
|---|---|---|
| C‑01 | 85 | `COMPLEMENTARY_SNR_MIN_DB = 100` |
| C‑02 | 116 | FATAL si hay 0 candidatos **o más de 1** (sin primer match) |
| C‑03 | 154 | `check_compatibility`: SR, canales y largos |
| C‑04 | 170 | Largos distintos ⇒ FATAL salvo `--allow-crop` |
| C‑05 | 183 | `estimate_lag_ms` |
| C‑06 | 285 | Aviso si el desfase supera 2 ms |
| C‑07 | 297 | `Delta = SDI_id − SDI_norm` |
| C‑08 | 301 | `SDV_hib = SDV_norm + gain·Delta` |
| C‑09 | 315 | `e_norm = mix − SDV_norm − SDI_norm` |
| C‑10 | **266‑275** | Los opcionales (`mix`, `SDV_id`) **nunca se recortan** y se comparan contra el tamaño **original** ⇒ `--allow-crop` es inoperante si existe `SDV_id` |
| C‑11 | — | **La polaridad invertida no se detecta ni se avisa** aunque el script calcule el residuo que la delata |

Detalle completo en `FORMULA_AUDIT.md`.

### 2.7 `orquestador_maestro.py` · Bloque D

16 afirmaciones verificadas línea a línea (D‑01…D‑16) y 8 demos ejecutando el original.
Resumen: nombres de modelo cableados, `[B]`/`[E]` ausentes, primer-gana por `listdir`,
`min_len` silencioso, SR del Mix impuesto a todos, sin comprobación de canales, sin hashes,
escribe dentro del árbol de entrada. Detalle en `ORCHESTRATOR_SPEC.md` §2.

**Hallazgo propio de este bloque:** la nomenclatura real del manifiesto entregado
(`par1_roformer_instrum_only.wav`) **no casa** con el glob del orquestador
(`*_instrum.wav`): ejecutado sobre esos nombres produce **0 pares**.

### 2.8 `MANIFEST_SEP_SDV-SDI.json` y `manifest_genio.json`

`DOCUMENTED_FACT`. Son la única fuente de nombres reales. Aportan:

- modelos reales: `roformer`, `mdxb`, `sucial`, `anvuew` (el orquestador solo conoce dos);
- patrón `parN_<modelo>_vocals_full.wav` / `_instrum_only.wav`;
- salidas reales del estilo `Genio_Atrapado_DeReverb_mt_6_SDV_B1.wav`;
- **ninguna** etiqueta `[A]`/`[B]`/`[C]`/`[D]`/`[E]` (0 coincidencias en ambos).

### 2.9 `preflight_audit.py`

`DOCUMENTED_FACT`: 108 líneas de comprobaciones previas; no interviene en los cuatro
motores ni en el orquestador. **No auditado en profundidad en esta fase** (`UNKNOWN` su
cobertura real).

---

## 3. Relación con la Fase 1

La Fase 1 detectó y documentó H‑12, H‑13, H‑14, H‑15, H‑25 y H‑26, y aplicó **R‑24** sobre
una **copia** del motor base (`/home/user/fase1/parcheados/MOTOR_SEP_SDV-SDI_R24.py`,
`317eba5d…`, con su `R-24.diff`). Esa copia **no forma parte de las fuentes** y no se ha
usado en esta fase: la Fase 1B trabaja siempre contra los 10 ficheros originales.

En la Fase 1 se estableció además que R‑24 ≡ hardened ≡ EVO en el comportamiento medido; la
Fase 1B no contradice ese resultado.

---

## 4. Lo que este documento NO afirma

- **`UNKNOWN`**: el motivo histórico de cada ausencia (por qué no hay `[B]`/`[E]` en el
  orquestador, por qué `c_k` no lleva clip, por qué el verificador no usa
  `alignment_confidence`). El código no lo dice.
- **`UNKNOWN`**: si `--allow-crop` se usa en flujos reales (depende de si las corridas normal
  e identidad suelen compartir longitud).
- **`UNKNOWN`**: la convención de nombres real de los componentes de Reverb Removal: no hay
  ni un ejemplo en el material entregado.
- NO VERIFICADO: `preflight_audit.py` más allá de su función declarada.
- No se ha evaluado calidad perceptual ni idoneidad musical de ninguna salida.
