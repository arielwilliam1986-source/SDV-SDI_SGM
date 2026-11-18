# CONSENSUS_VALIDATION.md — Bloque A

**Fase sintética 1B · validación de consenso**
Fuente: copia inmutable `/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM` (10/10 SHA‑256
verificados). Motores ejecutados como proceso, **sin modificar ni un byte**.

> **Regla de este bloque: no se elige método ganador.** Aquí se mide *si las opciones llegan
> a producir audio distinto* y *cuánto se desvía el resultado respecto de la verdad
> sintética*. No se ordena, no se puntúa y no se recomienda ningún método. Las tablas de
> error se publican completas precisamente para que nadie tenga que fiarse de un resumen
> jerarquizado.

Etiquetas: `DOCUMENTED_FACT` (leído en el código) · `EXPERIMENTAL_RESULT` (medido aquí) ·
`THEORETICAL_DEDUCTION` · `HYPOTHESIS` · `UNKNOWN`.

---

## 1. La pregunta

> «¿Qué opción de método de consenso llega **realmente** a una operación distinta?»

En la Fase 1 se detectó (H‑12) que `--consensus` parecía ignorarse en el orden
`magnitudes_first`. Este bloque no se apoya en aquella lectura: la vuelve a verificar de forma
independiente, la extiende a **las cuatro versiones** del motor y añade el comportamiento del
consenso con **K = 2, 3, 5, 7** guías con errores de tipos distintos.

---

## 2. Método, en cuatro partes

| Parte | Qué hace | Por qué |
|---|---|---|
| 1. Inventario estático | Relee cada fuente y **verifica** línea por línea las opciones, la función de consenso y el bloque donde se asignan los métodos | Evita citar de memoria |
| 2. Extremo a extremo | Ejecuta el motor real con cada `--consensus` y compara el **audio decodificado** | Es lo único que demuestra si la opción «llega a operación» |
| 3. Consenso enmascarado | Llama a `consensus_from_masks` (solo lectura) con K máscaras de error conocido | Permite barrer 9 modelos × 4 valores de K |
| 4. Consenso complejo | Llama a `consensus()` de v3 con STFT complejas | Único dominio donde existe **error de fase arbitrario** |

### 2.1 Corrección metodológica: el SHA‑256 del fichero no sirve

Se empezó comparando `sha256sum` de los WAV y aparecieron **diferencias donde el audio era
idéntico**. La causa, verificada y registrada en `results/consenso_e2e_metodo.json`:

`EXPERIMENTAL_RESULT`. Tres corridas del mismo audio, mismo motor, misma entrada:
**1 solo byte distinto en todo el fichero**, en el offset 60, que cae dentro del **chunk
`PEAK`** que escribe libsndfile y que contiene una **marca de fecha**. `data` empieza en el
offset 80; no hay ni un byte distinto después. Diferencia máxima de audio decodificado:
**0,0 exacto**.

> Consecuencia para todo el proyecto: **comparar `sha256` de WAV entre corridas produce
> falsos positivos de «diferencia»**. La comparación válida es sobre el audio decodificado
> (`results/consenso_e2e_metodo.json` deja el offset y el chunk identificados).

Por eso el veredicto de §4 se basa en `sha256` del **array float32 decodificado**, no del
fichero.

---

## 3. Inventario por versión  ·  `DOCUMENTED_FACT`

Todas las cifras de línea fueron verificadas releyendo la fuente en este bloque
(`results/consenso_inventario.json` incluye el SHA‑256 de cada fichero auditado).

| Versión | Fichero | `--consensus` | `--consensus-order` | Métodos declarados | Órdenes declarados | Función de consenso |
|---|---|---|---|---|---|---|
| **v3** | `MOTOR_SEP_SDV-SDI_v3.py` | l.1851 | **no existe** | l.175: `magnitudes_first`, `mean`, `median`, `median_ri` | no aplica | `consensus(Vs, method)` l.643 |
| **hardened 3.1.1** | `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | l.1869 | l.1865 | l.124: `weighted_mean`, `median`, `confidence_weighted_mean` | l.127: `magnitudes_first`, `masks_first` | `consensus_from_masks` l.837 |
| **EVO 3.1.1** | `MOTOR_SEP_SDV-SDI_EVO.py` | l.2015 | l.2011 | l.124: los tres | l.127: `magnitudes_first`, `masks_first`, **`hybrid_asymmetric`** | `consensus_from_masks` l.872 |
| **mqr 1.3.0** | `sdv_sdi_mqr_engine.py` | l.3371 | **no existe** | l.244: los tres | no aplica | `consensus_from_masks` l.1382 |

Valores por defecto (`DOCUMENTED_FACT`): en hardened y EVO, `CONSENSUS_ORDER_DEFAULT =
"magnitudes_first"` (l.123) y `CONSENSUS_DEFAULT = "confidence_weighted_mean"` (l.125). En v3
el defecto de `--consensus` es `magnitudes_first` (l.1851).

### 3.1 El bloque que anula la elección (hardened y EVO)

`DOCUMENTED_FACT` + verificación automática. En el orden `magnitudes_first`, los tres métodos
**apuntan al mismo objeto**:

```python
hardened l.1540-1544              EVO l.1650-1654
consensus = {                     consensus = {
    "weighted_mean": Mv_consensus,    "weighted_mean": Mv_consensus,
    "median": Mv_consensus,           "median": Mv_consensus,
    "confidence_weighted_mean":       "confidence_weighted_mean":
        Mv_consensus                      Mv_consensus
}                                 }
```

Además, el bucle de escritura salta los métodos no predeterminados
(`and method != opt.consensus_default`: hardened l.1556‑1558, EVO l.1667‑1669). Dos
mecanismos independientes que apuntan al mismo resultado.

### 3.2 Tres taxonomías distintas bajo nombres parecidos

Esto es una trampa real de lectura, y conviene dejarla escrita:

- **`magnitudes_first` en v3** (l.643) significa *mediana de magnitudes + fase del promedio
  complejo* — es un **método** de combinación compleja.
- **`magnitudes_first` en hardened/EVO** (l.127) significa *un **orden**: primero promediar
  magnitudes y luego derivar la máscara* — no es un método, es una etapa.

El mismo identificador designa cosas distintas según la versión. Cualquier comparación entre
versiones hecha por nombre de opción sería incorrecta.

---

## 4. ¿La opción llega a operación?  ·  `EXPERIMENTAL_RESULT`

Corridas reales (4 s, K=3 guías con error independiente, misma entrada para todos los
métodos, `--allow-misaligned` por el defecto del Bloque B, `mask_mode=mono`).

| Versión | Orden | Salidas distintas | Diferencia máx. de audio entre métodos | ¿Llega a operación? |
|---|---|---|---|---|
| hardened | `magnitudes_first` | **1 / 3** | **0,0 exacto** | **NO** |
| hardened | `masks_first` | 3 / 3 | 2,283·10⁻³ | **SÍ** |
| EVO | `magnitudes_first` | **1 / 3** | **0,0 exacto** | **NO** |
| EVO | `masks_first` | 3 / 3 | 2,283·10⁻³ | **SÍ** |
| EVO | `hybrid_asymmetric` | 3 / 3 | 2,072·10⁻³ | **SÍ** |
| v3 | — (no tiene órdenes) | 4 / 4 | 9,651·10⁻² | **SÍ** |
| mqr | — (no tiene órdenes) | 3 / 3 | 2,316·10⁻³ | **SÍ** |

Lectura:

1. **En el orden por defecto de hardened y EVO, `--consensus` no cambia ni una muestra.**
   No es que el efecto sea pequeño: es **exactamente cero**. La opción existe en el CLI, se
   valida, se registra... y no toca el audio. Coincide con H‑12 de la Fase 1 y lo confirma
   con una igualdad numérica dura.
2. **En `masks_first` la opción sí opera** (diferencias del orden de 2,3·10⁻³ en amplitud).
3. **`hybrid_asymmetric` es exclusivo de EVO** y no está en hardened.
4. **v3 y mqr no siguen este esquema**: no tienen `--consensus-order`, y todas sus opciones
   producen audio distinto.

### 4.1 Hallazgo colateral: hardened ≡ EVO también en `masks_first`

`EXPERIMENTAL_RESULT`. Las huellas de audio decodificado son **idénticas entre hardened y
EVO** en `masks_first` para los tres métodos:

| Método | huella de audio (hardened = EVO) |
|---|---|
| `weighted_mean` | `1cfced96b587…` |
| `median` | `26d82eafa64b…` |
| `confidence_weighted_mean` | `0d32fc24ba3e…` |

La Fase 1 había establecido la equivalencia hardened ≡ EVO en la ruta por defecto (X5). Aquí
se extiende a `masks_first`: **la única diferencia de comportamiento entre hardened y EVO en
materia de consenso es la existencia de la tercera rama**, no las ramas compartidas.

### 4.2 Dos versiones, dos actitudes ante la misma bandera

`EXPERIMENTAL_RESULT` + `DOCUMENTED_FACT`. Con `mask_mode: per_channel` y residuos activos:

- **EVO aborta** con `EXIT_VALIDATION` y un mensaje explícito (l.1391‑1395):
  *«`--use-residuals` actualmente calcula las guías en mono. Combinarlo con
  `--mask-mode per_channel` produciría un estéreo falso. Abortando para proteger la
  integridad del SDV/SDI.»*
- **hardened no aborta**: ejecuta y registra `mask_mode=mono` en su log aunque el manifiesto
  pedía `per_channel` (es el H‑25 de la Fase 1, reproducido aquí).

Mismo riesgo, dos políticas opuestas: una se niega, la otra continúa en silencio.

### 4.3 mqr: la opción elige qué se escribe, no qué se calcula

`DOCUMENTED_FACT` (texto de ayuda, l.3371 y siguientes): *«candidato escrito como
SDV.wav/SDI.wav (los 3 métodos se calculan siempre)»*. `EXPERIMENTAL_RESULT`: las tres
corridas producen audio distinto porque cada una escribe un candidato distinto; los tres se
calculan siempre. No es un fallo: es una semántica diferente de la misma bandera.

---

## 5. Consenso enmascarado con K = 2, 3, 5, 7  ·  `EXPERIMENTAL_RESULT`

Llamada directa a `confidence_and_disagreement` y `consensus_from_masks` del motor hardened
(l.819 y l.837), sobre máscaras sintéticas de 256 × 64 con error conocido. 4 valores de K ×
9 modelos = 36 configuraciones.

Fórmulas exactas del motor (`DOCUMENTED_FACT`, l.819‑846):

```
dis  = std(máscaras, eje K)                      # desacuerdo
conf = clip(1 − 2·dis, 0, 1)                     # confianza agregada
c_k  = 1 − media_{j≠k} |m_k − m_j|               # acuerdo leave-one-out, POR ELEMENTO
weighted_mean            = media(máscaras)
median                   = mediana(máscaras)
confidence_weighted_mean = Σ w_k·m_k ,  w_k = clip(c_k, 1e‑6)^β / Σ_j clip(c_j, 1e‑6)^β
```

### 5.1 Aviso previo: con K = 2 los tres métodos no pueden distinguirse

`THEORETICAL_DEDUCTION`. Para dos valores, `mediana = media` **por identidad algebraica**. Y
el promedio ponderado por confianza también colapsa al mismo valor cuando los dos pesos son
iguales. Resultado medido: **9 de 9 modelos dan los tres métodos idénticos** con K = 2.

Esto **no es un defecto del motor**: es una propiedad matemática. Cualquier afirmación del
tipo «con dos guías el método importa» sería falsa. Se registra para que nadie lo confunda
con un hallazgo.

### 5.2 Diferencia entre métodos (`max|Δ|` en unidades de máscara, wm vs cwm)

| Modelo de error | K=2 | K=3 | K=5 | K=7 |
|---|---|---|---|---|
| independiente | 0,0000 | 0,0222 | 0,0207 | 0,0140 |
| ρ = 0 | 0,0000 | 0,0185 | 0,0145 | 0,0141 |
| ρ = 0,6 | 0,0000 | 0,0210 | 0,0151 | 0,0116 |
| ρ = 0,95 | 0,0000 | 0,0235 | 0,0139 | 0,0135 |
| 1 outlier | 0,0000 | **0,3333** | 0,1993 | 0,1429 |
| 2 outliers | 0,0000 | **0,3333** | 0,2000 | 0,1565 |
| mayoría degradada | 0,0000 | **0,3333** | 0,2000 | 0,1727 |
| escalas distintas | 0,0000 | 0,0744 | 0,0503 | 0,0349 |
| polaridad invertida | 0,0000 | **0,3333** | 0,2000 | 0,1429 |

Observaciones, sin jerarquía:

- Con **errores independientes o correlacionados**, la elección de método mueve la máscara
  muy poco (≈0,02) y **la correlación ρ apenas cambia ese número**: de 0,0185 (ρ=0) a 0,0235
  (ρ=0,95) en K=3.
- Con **outliers, mayoría degradada o polaridad invertida**, la diferencia entre métodos
  llega a 0,3333: es ahí donde la elección del método sí cambia el resultado de forma
  apreciable.
- Las diferencias **decrecen al crecer K** (0,3333 → 0,1429 de K=3 a K=7): más guías, menos
  peso relativo de cada una.

### 5.3 El piso de peso se alcanza de verdad

`EXPERIMENTAL_RESULT`. En ninguna de las 36 configuraciones `c_k` fue negativo (0,0 % de
elementos), pero **`c_k` mínimo = 0,0000 exacto** en todas. Con el piso
`CONFIDENCE_WEIGHT_FLOOR = 1e‑6`, esos elementos quedan con peso ≈ 0: la guía que no concuerda
con ninguna otra **es anulada**, no promediada. `c_k` media sube con K (0,810 en K=2 → 0,886
en K=7).

### 5.4 Error respecto de la verdad (MAE), publicado sin ordenar

`results/consenso_mallas.csv` contiene `mae_wm`, `mae_med` y `mae_cwm` para las 36
configuraciones. Se publican completas. **Este laboratorio no las ordena ni deduce de ellas
un método preferible**: para hacerlo harían falta señales reales y criterios de escucha que
esta batería sintética no puede aportar.

---

## 6. Consenso complejo de v3: aquí sí existe error de fase  ·  `EXPERIMENTAL_RESULT`

`consensus(Vs, method)` de v3 (l.643) opera sobre STFT complejas, así que admite errores de
fase arbitrarios. 4 valores de K × 11 modelos = 44 configuraciones.

`magnitudes_first` de v3 = *mediana de magnitudes + fase del promedio complejo* (l.664‑667).

Resultados destacables:

- **43 de 44 configuraciones** dan diferencias reales entre métodos. La única excepción es
  K=2 con `escalas`, donde la diferencia máxima es **1,76·10⁻¹⁶**: numéricamente indistinguible
  (ruido de coma flotante, no una diferencia de comportamiento). Es coherente con §5.1: con
  K=2 la media y la mediana coinciden por construcción, también aquí.
- Error de fase resultante (media del |ángulo| en grados, ponderado), K = 7:

| Modelo | `mean` | `median` | `magnitudes_first` | `median_ri` |
|---|---|---|---|---|
| independiente | 26,22 | 38,25 | 26,22 | 29,96 |
| ρ = 0,95 | 26,11 | 38,94 | 26,11 | 29,84 |
| 1 outlier | 40,26 | 39,77 | 40,26 | 32,35 |
| mayoría degradada | 50,03 | 47,44 | 50,03 | 41,81 |
| fase +45° en una guía | 6,02 | 0,00 | 6,02 | 0,00 |

- `THEORETICAL_DEDUCTION`: `magnitudes_first` y `mean` coinciden siempre en el error de fase
  porque **el primero toma la fase del segundo** por construcción (l.666). La igualdad de sus
  columnas no es un hallazgo empírico: es estructural.
- Con `escalas` en K = 2 los métodos coinciden (1,8·10⁻¹⁶) por la misma razón algebraica que
  en §5.1. En una primera versión del experimento las escalas de K=2 y K=3 eran simétricas
  (mediana = media exacta) y la fila salía 0,0000; se sustituyeron por escalas asimétricas y
  desde K=3 ya difieren. Se deja anotado para que la tabla no se lea mal.

**Sin ordenación ni recomendación**, igual que en §5.4.

---

## 7. Lo que queda `UNKNOWN`

- `UNKNOWN`: si estas diferencias son audibles o relevantes musicalmente. No se han hecho
  pruebas perceptuales, y el encargo prohíbe deducirlas de señales sintéticas.
- `UNKNOWN`: el comportamiento con guías reales (extraídas de grabaciones). Toda la parte 3
  usa máscaras sintéticas y toda la parte 2, señales sintéticas de 4 s.
- `UNKNOWN`: por qué v3 produce la diferencia más grande entre métodos (9,7·10⁻² frente a
  2,3·10⁻³). Se mide, no se explica.
- `UNKNOWN`: el motivo histórico de que `magnitudes_first` sea el orden por defecto pese a
  anular la elección de método.
- NO VERIFICADO: el efecto de `--beta` y `--smoothing` sobre estas conclusiones; no se
  barrieron en este bloque.
- El experimento extremo a extremo usa **K=3 y un solo modelo de error** (independiente). No
  se repitió con los otros ocho modelos por coste; la parte 3 cubre esos modelos en el
  dominio de máscaras.

---

## 8. Reproducción

```bash
cd /home/user/fase1b/FASE_1B_RESULTADOS
python3 -u src/bloque_a.py            > results/logs/bloque_a_stdout.log 2>&1   # ~62 s
python3 -u src/bloque_a.py --saltar-e2e --saltar-runtime   # solo inventario
```

| Artefacto | Contenido |
|---|---|
| `results/consenso_inventario.json` | inventario verificado + SHA‑256 de cada fuente |
| `results/consenso_e2e.csv` | 22 corridas con rutas, rc, huellas de audio |
| `results/consenso_e2e_veredicto.json` | veredicto por (motor, orden) + detalle muestra a muestra |
| `results/consenso_e2e_metodo.json` | prueba de que el SHA de fichero no sirve (chunk `PEAK`) |
| `results/consenso_mallas.csv` | 36 configuraciones K × modelo con MAE de los 3 métodos |
| `results/consenso_complejo.csv` | 44 configuraciones de v3 con MAE y error de fase |
| `results/logs/bloque_a_stdout.log` | salida completa |

---

## 9. Resumen

**La opción `--consensus` existe en las cuatro versiones, pero solo en dos de las siete
combinaciones (orden × versión) con orden explícito no hace absolutamente nada, y son
precisamente las dos que vienen activas por defecto.** En `magnitudes_first`, hardened y EVO
producen audio **bit a bit idéntico** con cualquiera de los tres métodos: diferencia 0,0. En
`masks_first` sí operan. v3 y mqr no tienen ese problema porque no tienen orden, pero usan
taxonomías de nombres incompatibles con las otras dos, hasta el punto de que
`magnitudes_first` significa una cosa en v3 y otra en hardened/EVO.

Con K guías, el método solo marca diferencias apreciables cuando hay outliers, mayoría
degradada o polaridad invertida (hasta 0,3333 en máscara), y esas diferencias se diluyen al
crecer K. Con K = 2 los tres métodos son indistinguibles por construcción algebraica, no por
defecto.

Y un aviso transversal: **comparar `sha256` de WAV entre corridas no prueba igualdad**, porque
libsndfile estampa la hora en un chunk `PEAK`. La comparación válida es sobre el audio
decodificado.
