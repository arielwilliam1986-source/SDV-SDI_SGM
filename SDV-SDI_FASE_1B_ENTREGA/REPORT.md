# REPORT.md — Fase sintética 1B

**Consensos, alineación, `mix_delta`/SDI_F2 y orquestador · resultados sobre señales
sintéticas deterministas.**

Fecha: 2026-11-15 · Fuente: `Proyecto SDV-SDI_SGM.zip` (10/10 SHA‑256 verificados,
**0 bytes modificados**) · Python 3.13, NumPy/SciPy/SoundFile+libsndfile (versiones en
`manifests/MANIFEST_ENTREGABLES.json` y en el log de cada corrida).

Este informe **no elige ganador**, no declara mejor motor y no extrae conclusiones
perceptuales: solo mide propiedades matemáticas, de implementación y de integridad sobre
señales sintéticas con ground truth.

---

## 0. Las cuatro respuestas en una pantalla

| Bloque | Pregunta | Respuesta medida |
|---|---|---|
| **A** Consensos | ¿Qué opción de método llega a operación distinta? | Solo `masks_first`, `hybrid_asymmetric` y los 4 métodos de v3. La opción **predeterminada `magnitudes_first` no cambia ni una muestra** (max\|Δ\| = 0,0 exacto) en hardened y EVO |
| **B** Alineación | ¿Acierta el verificador? | **554/780** (71,0 %), 10 falsos positivos, 0 falsos negativos. Dos propuestas medidas y **no aplicadas**, pendientes de validación externa |
| **C** Fórmulas | ¿Existe `SDI_F2`? | **No existe**: 0 apariciones en las 10 fuentes y manifiestos. **`UNKNOWN`**, no reconstruido |
| **D** Orquestador | ¿Es seguro? | **No**: 16 defectos verificados y 8 demos ejecutando el original. Prototipo por perfiles: **27/27 fixtures**, 10 tests internos y 21 en `tests/` |

---

## 1. Bloque A — Consensos

### 1.1 Inventario (`DOCUMENTED_FACT`)

Cuatro implementaciones **distintas** de consenso, no una:

| Motor | Métodos | Órdenes | Escribe |
|---|---|---|---|
| hardened 3.1.1 | 3 (incl. `confidence_weighted_mean`) | `magnitudes_first` / `masks_first` | solo el predeterminado (l.1556‑1558) |
| EVO | 4 (añade `hybrid_asymmetric`) | ídem | ídem |
| v3 | **4 con taxonomía propia** (`mean`, `median`, `median_ri`) | **no existe el concepto** | — |
| `sdv_sdi_mqr_engine` | 3 | **no existe** | elige qué escribe, no qué calcula |

### 1.2 Qué llega realmente a operación (`EXPERIMENTAL_RESULT`, K=3 independiente)

| Motor / orden | Métodos distintos | max\|Δ\| de audio | ¿Cambia la salida? |
|---|---|---|---|
| hardened / `magnitudes_first` | 1/3 | **0,0** | **NO** |
| hardened / `masks_first` | 3/3 | 2,283·10⁻³ | SÍ |
| EVO / `magnitudes_first` | 1/3 | **0,0** | **NO** |
| EVO / `masks_first` | 3/3 | 2,283·10⁻³ | SÍ |
| EVO / `hybrid_asymmetric` | 3/3 | 2,072·10⁻³ | SÍ |
| v3 (sin orden) | 4/4 | 9,651·10⁻² | SÍ |
| mqr (sin orden) | 3/3 | 2,316·10⁻³ | SÍ |

**hardened ≡ EVO** también en `masks_first` (huellas de audio idénticas). La opción
predeterminada existe, está documentada y **no tiene ningún efecto sobre el audio**.

### 1.3 Guías degradadas (K × 9 modelos)

- **K=2 → los 3 métodos de máscara son idénticos 9/9 por álgebra** (mediana de 2 ≡ media de
  2). No es un defecto: no se presenta como hallazgo.
- **K≥3 → 0/9 idénticos.**
- Distancia `d(weighted_mean, confidence_weighted_mean)` a K=3: independiente 0,0222 ·
  ρ=0,95 0,0235 · **escalas 0,0744** · **outliers / mayoría degradada / polaridad 0,3333**.
  Decrece con K (a K=7, outlier 0,1429).
- `c_k` **nunca negativo** (0,0 %) pero con **mínimo exactamente 0,0000** en las 36
  combinaciones: el piso `FLOOR = 1e-6` anula la confianza de un método.
- Configuración compleja de v3: **43/44** con diferencia real; la única excepción es K=2 con
  escalas = 1,76·10⁻¹⁶ (ruido de coma flotante).

Detalle completo y tablas: `CONSENSUS_VALIDATION.md` (9 secciones).

---

## 2. Bloque B — Alineación (cerrado como diagnóstico)

780 casos: 6 contenidos × 2 duraciones × 5 retardos × 13 combinaciones de motor.

| Métrica | Valor |
|---|---|
| Aciertos (tolerancia ±1 muestra) | **554 / 780** (71,0 %) |
| Falsos positivos | **10** |
| Falsos negativos | **0** |
| Retardo real 0 | 38 `ALIGNED` / 12 `WARNING` (5,044–5,077 ms) / 10 `MISALIGNED` |
| Aciertos por contenido | estéreo 130, silencio 130, aire/reverb 112, voz armónica 62, percusivo 62, aperiódico 58 |
| hardened ≡ EVO | **390/390 idénticos** |

**Mecanismo** (`EXPERIMENTAL_RESULT`): la superficie NCC está casi empatada — **752/780**
casos con `ratio_real_vs_max > 0,999`, y gana por ~3·10⁻⁷. El desempate efectivo es de
**28 muestras de envolvente = 5,079 ms** (`HYPOTHESIS`), y la clasificación final
(l.566‑568) **ignora `alignment_confidence`**. Discriminante medido: 0,0670 (fallos) frente a
0,6603 (aciertos).

**Dos propuestas, medidas y NO aplicadas** (requieren validación externa):
1. umbral θ = 0,35 → 444 → 344 `MISALIGNED`, `AMBIGUOUS` 0 → 100, falsos positivos 10 → 0;
2. exigir solape ≥ 90 % → |k| ≤ 10 % de la duración; **554 → 602** aciertos, 0/780 fuera.

Además: la evaluación en mono **no certifica** la alineación estéreo. Downmix −9,98 ms,
canal L −9,98 ms, canal R **+15,06 ms**: un único retardo no representa desplazamientos
opuestos. La periodicidad se conserva como **hipótesis**, sin generalizar.

Detalle: `ALIGNMENT_DIAGNOSTICS.md` (540 líneas, 12 secciones).

---

## 3. Bloque C — `mix_delta.py` y SDI_F2

- **`SDI_F2` no existe** → `UNKNOWN`, sin reconstruir (`FORMULA_AUDIT.md` §1).
- Fórmulas verificadas contra el código: `e_norm = M − SDV − SDI` (l.315),
  `Delta = SDI_id − SDI_norm` (l.297), `SDV_hib = SDV_norm + gain·Delta` (l.301), umbral de
  complementariedad 100 dB (l.85).
- **Resultado nuevo** (`THEORETICAL_DEDUCTION` + `EXPERIMENTAL_RESULT`): el residuo de la
  identidad `Delta_indirecta = Delta_directa + e_norm` es **exactamente**
  `e_id = SDV_id + SDI_id − mix`. Verificado con anulación exacta (**0,000e+00**) en tres
  escenarios. La identidad se cumple **si y solo si la corrida identidad es complementaria**.
- **`e = 0` no prueba separación**: con `SDV = mix` y `SDI = 0` la complementariedad es de
  **336,87 dB** y la separación es **nula**, mientras que la separación perfecta
  (`SDV = V_true`, `SDI = I_true`) da **325,83 dB**. La separación nula obtiene **más**
  complementariedad que la perfecta: el número no mide separación.
- Complementariedad con guías exactas: 149–152 dB en las tres ramas de v3; con guías
  atenuadas ×0,8 cae a **13,98 dB** y con ruido a **11,41 dB**. Es decir, **depende de las
  guías, no de la rama**; el caso «todo complementario» es artefacto de mis señales.
- Guardas: SR, canales, largos y ambigüedad funcionan y **no truncan en silencio**; el
  desfase >2 ms se mide y se avisa.
- **Dos huecos**: `--allow-crop` es **inoperante si existe `SDV_id`** (compara contra el
  tamaño original, §6.1) y la **polaridad invertida no se detecta ni se avisa** (§6.2).

---

## 4. Bloque D — Orquestador

16 defectos verificados línea a línea y 8 demos **ejecutando el original**. Los cuatro más
graves, medidos:

1. **La nomenclatura real no casa.** Con los nombres del manifiesto entregado
   (`par1_roformer_instrum_only.wav`) el orquestador produce **0 pares**, `rc=0`, sin aviso.
2. **SR distinta**: un `[C]` a 48 kHz se descarta parcialmente (**7 800 muestras, 0,1625 s**)
   y se reinterpreta a 44,1 kHz (**8,13 % más grave**), `rc=0`, sin aviso.
3. **Duplicados**: dos `[C]` ⇒ gana el **último del `listdir`** (identificado comparando
   salidas: residuo 5,6·10⁻⁸ frente a 1,95·10⁻¹), sin diagnóstico.
4. **Omisiones silenciosas**: modelo no listado o componente ausente ⇒ 0 pares, sin aviso.

El prototipo `src/orchestrator_spec/` resuelve esto con **perfiles en datos**: el código de
cálculo no conoce ningún nombre de modelo. Resultados: **27/27 fixtures**, **10/10 tests** internos y **21/21** en `tests/`,
C agregado y dividido **nunca sumados**, sin primer match, sin truncar, sin resamplear.

Prueba de fidelidad L/R: `SDV1` y `SDI1` contra ground truth dan **6,06·10⁻⁸** y **5,62·10⁻⁸**
de error máximo; si los canales se intercambiaran, el error sería **0,350**.

Detalle: `ORCHESTRATOR_SPEC.md`.

---

## 5. Las ocho preguntas del encargo (4.11)

| # | Pregunta | Respuesta |
|---|---|---|
| 1 | Qué es funcional y qué peligroso | Funcional: la resta y la escritura FLOAT. Peligroso: recorte silencioso, SR impuesto, elección por `listdir`, omisiones sin aviso (`ORCHESTRATOR_SPEC.md` §2) |
| 2 | Cómo no depender de nombres de modelo | Perfiles JSON; el código solo conoce roles (§3.1) |
| 3 | C agregado vs dividido sin doble conteo | Estrategia declarada + patrones anclados con `excluye`; ambos a la vez ⇒ `AMBIGUOUS` (§3.2, §5.2) |
| 4 | Cuándo es válido `C_total` | Agregado solo **o** Reverb+Others exactamente, con geometría idéntica (§5.2) |
| 5 | Política ante ausentes/duplicados/corridas mezcladas | `INCOMPLETE` / `AMBIGUOUS` / separación por `(perfil, run, carpeta)` (§4) |
| 6 | Qué residuales por subconjunto | Tabla §5.3 |
| 7 | Qué prueba que no mezcla L/R ni altera duración/SR | §7: error 6·10⁻⁸ frente a 0,350 si se intercambiaran |
| 8 | Qué cambios debe recibir el futuro orquestador | §8: 10 cambios concretos |

---

## 6. Cambios respecto a la Fase 1

- La Fase 1 cerró con R‑24 aplicado sobre una **copia** del motor base. La Fase 1B **no usa
  esa copia**: trabaja contra los 10 ficheros originales.
- **Ninguna fuente se ha modificado en esta fase** (0 bytes). El orquestador original solo se
  ha **ejecutado** en directorios de trabajo desechables.
- El **verificador de alineación sigue sin parchear**, tal como se pidió.

---

## 7. Límites de conclusión

- Todo se midió sobre **señales sintéticas** (2–30 s). **No se extrapola a música real.**
- No se valida calidad perceptual, ni MVSEP en línea, ni Android/Termux, ni la idoneidad de
  ningún candidato para una canción.
- **`UNKNOWN`**: SDI_F2; el motivo histórico de cada ausencia; la convención real de nombres
  de Reverb Removal; si `--allow-crop` se usa en flujos reales.
- NO VERIFICADO: `preflight_audit.py` en profundidad; el contenido campo por campo de los
  sidecars de procedencia de `mix_delta.py`.
- Las dos propuestas del Bloque B **no están aplicadas**: son medidas, a la espera de
  validación externa.

---

## 8. Entregables

| Documento | Contenido |
|---|---|
| `README.md` | Cómo reproducir todo, en orden |
| `SOURCE_AUDIT.md` | Las 10 fuentes, hashes y defectos por fichero |
| `CONSENSUS_VALIDATION.md` | Bloque A completo (9 secciones) |
| `ALIGNMENT_DIAGNOSTICS.md` | Bloque B completo (12 secciones) |
| `FORMULA_AUDIT.md` | Bloque C completo |
| `ORCHESTRATOR_SPEC.md` | Bloque D completo |
| `src/` | Código del laboratorio y prototipo `orchestrator_spec/` |
| `tests/` | 21 tests del prototipo |
| `configs/` | Registro de perfiles semánticos |
| `fixtures/` | Especificación de los 27 fixtures (deterministas) |
| `results/` | `results.csv`, `results.json`, `raw.jsonl`, logs y artefactos crudos |
| `manifests/`, `hashes/` | Inventario con SHA‑256 y verificación de fuentes |
