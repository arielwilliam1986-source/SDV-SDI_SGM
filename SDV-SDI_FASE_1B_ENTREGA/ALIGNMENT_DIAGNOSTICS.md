# ALIGNMENT_DIAGNOSTICS.md — Bloque B

**Fase sintética 1B · diagnóstico del verificador de alineación**
Fuente auditada: `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` (copia inmutable, SHA‑256 verificado)
y `MOTOR_SEP_SDV-SDI_EVO.py` como contraste.

> **Revisión 2.** Los datos experimentales no han cambiado: no se ha vuelto a ejecutar el motor,
> no se ha modificado ninguna fuente y no se ha aplicado ninguna corrección de DSP. Solo se han
> corregido la documentación y los agregados derivados. Cambios respecto a la revisión 1:
> **(1)** el control de identidad son 30/30 **por motor** y 60/60 global (§7);
> **(2)** el barrido de confianza informa ahora la clasificación **completa** antes y después,
> no solo los aciertos (§9.1); **(3)** θ = 0,35 queda marcado como **umbral exploratorio**, no
> validado ni incorporado al motor (§9.1); **(4)** se documenta el **alcance** de la restricción
> de solape ≥ 90 % por duración (§9.2); **(5)** se corrige la descripción del caso estéreo (§8);
> **(6)** la explicación de los 224 samples queda como **hipótesis** respaldada, sin generalizar
> a voces reales ni a música (§6, pieza 2).

Etiquetas usadas en todo el documento, sin excepciones:

- `DOCUMENTED_FACT` — está escrito en el código o en la documentación del proyecto.
- `EXPERIMENTAL_RESULT` — medido en este laboratorio, reproducible con los comandos de §11.
- `THEORETICAL_DEDUCTION` — se deduce de un hecho documentado + aritmética, sin medición nueva.
- `HYPOTHESIS` — explicación propuesta, no demostrada.
- `UNKNOWN` — no se midió o no se puede decidir con la evidencia disponible.

---

## 1. La pregunta que este bloque responde

En la Fase 1 el verificador declaró `MISALIGNED` en archivos cuyo retardo real era **0 ms**.
No supe explicar por qué y lo dejé abierto. Este bloque existe para cerrarlo: reproducir el
fallo, medirlo y decir **qué pieza concreta del verificador lo produce**, sin tocar el motor.

Restricciones respetadas (§2.8 de la especificación): **no se usó `--correct-alignment`**,
**no se parcheó el verificador**, **no se normalizó ni se cambió ganancia, polaridad, fase,
frecuencia de muestreo, canales ni duración** de ninguna señal. El motor se cargó en modo
solo lectura con `importlib` y se llamaron sus propias funciones.

---

## 2. Tolerancia declarada ANTES de ejecutar

Esto se fijó antes de ver un solo resultado y no se ajustó después:

| Concepto | Regla |
|---|---|
| Acierto de estimación | `|lag_est − lag_real| ≤ 1 muestra` (44 100 Hz) |
| Falso positivo (FP) | retardo real `= 0` y clase `MISALIGNED` |
| FP severo | retardo real `= 0` y `|lag_est| > 10 ms` |
| Falso negativo (FN) | `|retardo real| > 10 ms` y clase `ALIGNED` |
| Error | `(lag_est − lag_real_esperado)` en ms |

Los umbrales 1 muestra y 10 ms **no son inventados**: son `ALIGNED_TOL_SAMPLES = 1` (l.145)
y `MISALIGNED_TOL_MS = 10.0` (l.146) del propio motor. Es decir, se juzga al verificador
con su propia vara.

---

## 3. Convención de signo (una trampa que conviene documentar)

`DOCUMENTED_FACT`. El motor devuelve el **índice de correlación**, no el retardo compensatorio.
La correlación se calcula como `corr[k] = Σ env_mix[t] · env_guide[t−k]` (`_ncc_fft_coarse`,
l.459–489) y `_aligned_pair` alinea con `guide[t−lag]` (l.497–501). Consecuencia:

> una guía **retardada** `d` muestras produce su máximo en `k = −d`.

Por eso en todo este bloque el valor esperado es `−d` y el error se calcula como `lag_est + d`.
Un operador que lea `Offset = +25.0 ms` en el log debe entender que la guía va **adelantada**
25 ms, no retardada. `EXPERIMENTAL_RESULT`: verificado en 780 casos; en los aciertos
`lag_est` coincide con `−d` dentro de 1 muestra.

Esto no es un defecto del motor. Es una fuente de confusión al leer los informes, y por eso
se documenta aquí.

---

## 4. Método: cómo se mide sin modificar el verificador

1. Se carga el módulo con `importlib` (tiene guarda `if __name__ == "__main__"`, no ejecuta nada).
2. Se usan **sus** funciones: `mono_downmix`, `_moving_rms`, `_decimate_block_mean`,
   `_ncc_fft_coarse`, `_refine_alignment`, y **sus** constantes `ALIGN_*`.
3. Para ver *toda* la curva —y no solo el argmax que devuelve el motor— se replica su bucle
   de normalización (`src/bloque_b.py:curva_ncc`), vectorizado.
4. **La réplica se verifica en cada caso**: si su argmax no coincide con el que devuelve
   `_ncc_fft_coarse`, el caso se marca y no se usa. `EXPERIMENTAL_RESULT`: **780/780
   coincidencias, 0 discrepancias**. La curva que se analiza es la del motor.

Batería: 6 contenidos × 5 duraciones (4, 10, 15, 20, 30 s) × 13 retardos
(0, ±1, ±5, ±10, ±25, ±50, ±100 ms) × 2 motores = **780 casos**.
Señales: `voz_armonica`, `percusivo`, `percusivo_aperiodico`, `aire_reverb`, `estereo`,
`silencio_inicial_final` (20 % inicial y final en silencio). Semilla 20261117.

Los retardos se aplican **desplazando la guía**, con relleno de ceros (`y[t] = x[t−d]`).
Eso es el experimento; la mezcla no se toca.

---

## 5. Resultado global

`EXPERIMENTAL_RESULT` — 780 casos:

| Métrica | Valor |
|---|---|
| Réplica fiel al motor | 780/780 |
| Aciertos de estimación (≤ 1 muestra) | **554/780 (71,0 %)** |
| Falsos positivos (retardo 0 → `MISALIGNED`) | **10** (5 configuraciones × 2 motores) |
| Falsos negativos (retardo > 10 ms → `ALIGNED`) | **0** |
| Casos con retardo real 0 | 60: 38 `ALIGNED`, 12 `WARNING`, 10 `MISALIGNED` |
| hardened vs EVO | **0 diferencias** en 390 pares (error y clase) |

Lectura inmediata: el verificador **no deja pasar** desalineaciones reales (0 FN), pero
**inventa** desalineaciones donde no las hay (10 FP) y su estimación fina solo es exacta
en 7 de cada 10 casos. La igualdad hardened ≡ EVO reproduce lo ya visto en Fase 1 (X5):
en esta ruta, EVO no cambia nada.

### 5.1 Por contenido

| Contenido | Aciertos ≤1 muestra | FP | FN |
|---|---|---|---|
| `estereo` | 130/130 | 0 | 0 |
| `silencio_inicial_final` | 130/130 | 0 | 0 |
| `aire_reverb` | 112/130 | 2 | 0 |
| `voz_armonica` | 62/130 | 2 | 0 |
| `percusivo` | 62/130 | 2 | 0 |
| `percusivo_aperiodico` | 58/130 | 4 | 0 |

(130 = 2 motores × 5 duraciones × 13 retardos.)

### 5.2 Por magnitud del retardo

| Retardo | Aciertos | Error máx. | Clases |
|---|---|---|---|
| 0 | 38/60 | 7147 ms | 38 ALIGNED, 12 WARNING, 10 MISALIGNED |
| ±1 ms | 76/120 | 7147 ms | 100 WARNING, 20 MISALIGNED |
| ±5 ms | 82/120 | 7147 ms | 90 WARNING, 28 MISALIGNED, 2 ALIGNED |
| ±10 ms | 88/120 | 7147 ms | 94 WARNING, 26 MISALIGNED |
| ±25 ms | 88/120 | 7147 ms | 120 MISALIGNED |
| ±50 ms | 90/120 | 7147 ms | 120 MISALIGNED |
| ±100 ms | 92/120 | 7147 ms | 120 MISALIGNED |

El error máximo de ~7 s aparece porque en algunos casos el ganador se va al extremo del
rango de búsqueda (30 s). No es un error de escala: es el mismo fallo de §6 llevado al límite.

---

## 6. Por qué el verificador dijo `MISALIGNED` con retardo real 0

Esta es la respuesta a la pregunta abierta de la Fase 1. El fallo se compone de **cuatro
piezas** que se suman; las cuatro están medidas, aunque la segunda tiene rango de `HYPOTHESIS`.

### Pieza 1 — La superficie de correlación está casi empatada

`EXPERIMENTAL_RESULT`. En **752 de 780 casos** el máximo global vale más del 99,9 % del valor
que la curva tiene en el retardo verdadero (y en los aciertos, `ratio real/máx ∈ [0,999992,
1,000000]`). El número de picos locales dentro del 1 % del máximo va de **1 a 96**, con 3–4
en las señales de 4 s y 50–70 en las de 20–30 s: la superficie no tiene un pico dominante,
tiene una cordillera.

Ejemplo exacto (percusivo, 30 s, guía idéntica salvo retardo 0):

```
ncc(lag = 0)  = 0.9911148
ncc(lag = 28) = 0.9911151      ← gana este
diferencia    = 3·10⁻⁷
```

**Un solo lag de 330 749** supera al lag correcto, y lo supera por tres diezmillonésimas
(0,0000003 en valor absoluto, sobre una escala de 0 a 1).
`np.argmax` (l.488) no tiene margen de significancia ni regla de desempate: toma el primero
que encuentra. El veredicto depende de ruido numérico.

### Pieza 2 — El desempate cae a un período de la envolvente  ·  `HYPOTHESIS`

> **Estado de esta pieza: `HYPOTHESIS`, respaldada por un experimento. No es un hecho
> documentado ni una deducción cerrada, y no se generaliza a voces reales ni a música.**

Los datos que la respaldan:

- `EXPERIMENTAL_RESULT`. En los 60 casos con retardo real 0, la clase se reparte así:
  **38 `ALIGNED` con estimación 0,000 ms exacto**, **12 `WARNING` con estimaciones entre
  5,044 y 5,077 ms**, y **10 `MISALIGNED`** con valores lejanos (§6 pieza 3).
- La F0 de la voz sintética de este laboratorio es **196 Hz**; a 44 100 Hz son **225 muestras**,
  y con la decimación de 8 (`ALIGN_COARSE_DECIMATION`) son **28,125 unidades de envolvente**.
- El desplazamiento recurrente mide **28 unidades = 224 muestras = 5,079 ms**.

La explicación propuesta: la envolvente de una señal periódica es periódica, así que la
correlación de envolventes tiene picos casi idénticos separados un período, y el detector
elige el período vecino (224 en vez de 225 probablemente porque el refinamiento de ±12
muestras arrastra el resultado). La coincidencia entre 225 y 224 es de **una muestra**, y el
rango de valores observado (5,044–5,077 ms) corresponde a 222–224 muestras.

Lo que **no** está demostrado y queda `UNKNOWN`:

- que un período de la envolvente sea la causa exclusiva de esos 12 casos (hay 12 casos y una
  diferencia de 3·10⁻⁷ en otros tantos; ambas cosas pueden convivir);
- que el mecanismo se comporte igual con F0 variable, vibrato amplio, voz cantada o polifonía;
- cualquier extrapolación a música real. La F0 de esta batería es fija por construcción.

Consecuencia práctica dentro de esta batería: en vez de 0 ms el verificador reporta ~5,08 ms,
que cae en la banda `WARNING` (entre 1 muestra y 10 ms) y no en `ALIGNED`.

### Pieza 3 — Cuando gana un lag lejano, gana con solape parcial

`EXPERIMENTAL_RESULT`. La normalización es **por ventana de solape**: las energías se calculan
solo sobre la parte que se solapa (l.481–483), con el único filtro `min_overlap =
max(64, 0.5·min(A,B))` (l.475). Eso permite que un lag con la mitad de la señal disponible
puntúe más alto que el lag correcto, que compara la señal completa.

Los 5 falsos positivos, con su solape:

| Contenido | Dur. | Ganador | Solape del ganador | Pearson resultante |
|---|---|---|---|---|
| `voz_armonica` | 4 s | **+1439,8 ms** | 14 113 / 22 050 (64 %) | 0,0670 |
| `percusivo` | 10 s | **−4291,7 ms** | 31 467 / 55 125 (57 %) | 0,0228 |
| `percusivo_aperiodico` | 4 s | **+1449,8 ms** | 14 058 / 22 050 (64 %) | 0,0535 |
| `percusivo_aperiodico` | 15 s | **+7147,3 ms** | 43 287 / 82 687 (52 %) | 0,0097 |
| `aire_reverb` | 4 s | **+1394,3 ms** | 14 364 / 22 050 (65 %) | 0,0262 |

En los cinco, el ganador usa entre la mitad y dos tercios de la señal. El retardo verdadero
era **cero**.

### Pieza 4 (la que hace daño) — El veredicto ignora su propia confianza

`DOCUMENTED_FACT`. Esto es lo más importante del bloque. Después del refinamiento el motor
calcula el Pearson del par propuesto y lo guarda:

```python
556   best_lag, peak_val, sub = _refine_alignment(...)
562   rec["alignment_confidence"] = max(0.0, min(1.0, peak_val))
...
566   if abs_off <= ALIGNED_TOL_SAMPLES: rec["classification"] = "ALIGNED"
567   elif abs_off <= tol_warn:           rec["classification"] = "WARNING"
568   else:                               rec["classification"] = "MISALIGNED"
```

La clasificación (l.566–568) depende **solo de `abs_off`**. `alignment_confidence` se escribe,
se imprime en el log (l.1337: `Offset=… ms | NCC=… -> …`) y **nunca se usa para decidir**.

Y esa confianza separa el problema con una nitidez que no deja margen a dudas:

| Grupo | Pearson del par propuesto |
|---|---|
| Los 10 falsos positivos | **0,0097 – 0,0670** |
| Los 554 aciertos | **0,6603 – 0,8454** |

Entre 0,067 y 0,660 **no hay un solo caso**. Con retardo 0 y un ganador a 1,4 s de distancia,
el motor está proponiendo un par de señales que no se parecen en nada (Pearson ≈ 0,01–0,07)
y aun así concluye `MISALIGNED` en lugar de «no lo sé».

Véase `results/fig_b_pearson.svg`: las tres nubes de puntos y el hueco vacío en medio.

---

## 7. Control de identidad: lo que el verificador **sí** hace bien

Para descartar que el estimador tuviera un sesgo interno, se le pasó **la misma señal como
mezcla y como guía** (retardo verdadero 0 *por construcción*, no por elección).

Diseño y conteo, sin ambigüedad: son **6 contenidos × 5 duraciones = 30 casos por motor**, y
**2 motores**, es decir **60 casos en total**.

`EXPERIMENTAL_RESULT`:

| Ámbito | Casos | Con lag = 0 y offset = 0,000 ms | Pearson | Clase |
|---|---|---|---|---|
| `hardened_3.1.1` | 30 | **30/30** | 1,0000 en los 30 | `ALIGNED` en los 30 |
| `evo_3.1.1` | 30 | **30/30** | 1,0000 en los 30 | `ALIGNED` en los 30 |
| **Global** | **60** | **60/60** | 1,0000 en los 60 | `ALIGNED` en los 60 |

Conclusión: el estimador no tiene desfase propio. Los ~5,08 ms de §6 aparecen **al introducir
el acompañamiento**, no antes. Esto descarta la explicación fácil («la envolvente va corrida»)
y deja el diagnóstico donde corresponde: en la superficie de correlación entre dos señales
distintas y en la falta de control de confianza.

Véase `results/alineacion_identidad.json` (`n_casos` = 30 por motor; `n_exactos` = 30).

---

## 8. Caso L/R asimétrico: +10 ms en L, −10 ms en R

`EXPERIMENTAL_RESULT` (20 s, contenido `estereo`).

El motor compara **mono contra mono**: `mono_downmix` (l.260) promedia los dos canales antes de
estimar. Con un desfase **opuesto** en cada canal, ese promedio produce **una sola estimación**
que no representa a ninguno de los dos desplazamientos reales: es el resultado de la mezcla,
no la alineación del par estéreo.

| Medición | Resultado |
|---|---|
| Veredicto sobre el downmix | −55 env = **−9,98 ms**, `WARNING` |
| Canal L aislado | −55 env = −9,98 ms (verdad −10 ms) → **correcto** |
| Canal R aislado | +83 env = +15,06 ms (verdad +10 ms) → **error de 5,06 ms** |

Lectura en lenguaje llano: cuando los canales están desplazados en sentidos opuestos, el
promedio mono **no los representa** —los suma y devuelve un valor intermedio—, de modo que
un `WARNING` o incluso un `ALIGNED` sobre el downmix **no certifica que el par estéreo esté
alineado**. La evaluación mono solo habla de la señal promediada.

Los resultados por canal se conservan porque son los informativos: el canal L acierta y el R
se desvía 5,06 ms (otra vez, aproximadamente un período de la envolvente, §6 pieza 2).

Alcance de lo medido: un único caso, una sola duración (20 s). `UNKNOWN`: el comportamiento
con desfases opuestos de otras magnitudes, con desfases distintos por canal no simétricos, o
con desfase más contenido de fase entre canales. No se generaliza.

Esto es una limitación de diseño (`DOCUMENTED_FACT`: la comparación es mono), no un fallo
aleatorio. No se propone ni se aplica ninguna corrección.

Véase `results/alineacion_lr_asimetrico.json`.

---

## 9. Dos correcciones posibles — **medidas pero NO aplicadas**

El encargo prohíbe parchear el verificador. Por eso estas dos ideas se evalúan **fuera del
motor**, sobre los datos ya calculados, y se presentan como propuestas declaradas.

Ninguna se ha implementado en ningún `.py` de la fuente, ninguna se ha incorporado al motor y
ninguna se recomienda sobre la otra. **Las dos quedan pendientes de validación externa**: lo
que sigue son resultados de laboratorio sobre una batería sintética acotada, no un parámetro
listo para producción.

### 9.1 Puerta por confianza

Regla propuesta: si `alignment_confidence < θ`, la clase pasa a `AMBIGUOUS` en vez de
`MISALIGNED`.

> **Sobre θ = 0,35.** Es un **umbral exploratorio**, elegido dentro del hueco de separación que
> muestra esta batería sintética. **No es un valor validado**, no procede de música real, no se
> ha contrastado con ninguna grabación del proyecto y **no debe leerse como definitivo ni
> llevarse al motor tal cual.** El barrido de la tabla siguiente existe precisamente para que se
> vea que el resultado no depende de ese valor concreto, sino de un intervalo amplio.

Esta evaluación sí es **exacta respecto al pipeline**: la puerta solo reclasifica usando el
`alignment_confidence` y la clase que el motor ya produjo; no interviene en el cálculo.

#### Clasificación completa, antes y después de θ = 0,35 (780 casos)

| Clase | Antes | Después | Diferencia |
|---|---|---|---|
| `ALIGNED` | 40 | 40 | 0 |
| `WARNING` | 296 | 296 | 0 |
| `MISALIGNED` | 444 | 344 | **−100** |
| `AMBIGUOUS` | 0 | **100** | **+100** |
| **Falsos positivos** | **10** | **0** | **−10** |
| **Falsos negativos** | **0** | **0** | 0 |

#### Por motor (390 casos cada uno; idénticos, como cabía esperar de hardened ≡ EVO)

| Clase | `hardened_3.1.1` antes | después | `evo_3.1.1` antes | después |
|---|---|---|---|---|
| `ALIGNED` | 20 | 20 | 20 | 20 |
| `WARNING` | 148 | 148 | 148 | 148 |
| `MISALIGNED` | 222 | 172 | 222 | 172 |
| `AMBIGUOUS` | 0 | 50 | 0 | 50 |
| Falsos positivos | 5 | 0 | 5 | 0 |
| Falsos negativos | 0 | 0 | 0 | 0 |

#### Qué ocurre con los 226 casos que no son acierto

De los 780 casos, 554 son acierto de estimación (≤ 1 muestra) y **226 no**. La puerta los trata
así:

| Grupo | Casos | Pasan a `AMBIGUOUS` | Se quedan como estaban |
|---|---|---|---|
| Aciertos (≤ 1 muestra) | 554 | **0** | 554 |
| No aciertos | 226 | **100** | 126 |

Detalle de las transiciones de esos 226, caso por caso:

| Transición | Casos |
|---|---|
| `MISALIGNED` → `AMBIGUOUS` | **100** |
| `MISALIGNED` → `MISALIGNED` (confianza ≥ 0,35) | 74 |
| `WARNING` → `WARNING` | 50 |
| `ALIGNED` → `ALIGNED` | 2 |

Dos consecuencias que conviene dejar explícitas:

1. **La puerta solo toca la clase `MISALIGNED`.** Ningún `WARNING` y ningún `ALIGNED` se
   convierten en `AMBIGUOUS`, porque todos ellos tienen confianza ≥ 0,35. La intervención es
   quirúrgica: no degrada avisos legítimos.
2. **No arregla la exactitud de la estimación.** Siguen quedando **74 casos `MISALIGNED` con
   confianza alta** y estimación equivocada. La puerta separa «no lo sé» de «está desalineado»;
   no mejora el valor numérico del retardo. Esa parte sigue siendo un problema abierto.

#### Barrido de θ

| θ | FP retirados | Aciertos perdidos |
|---|---|---|
| 0,10 – 0,60 | **10/10** | **0/554** |
| 0,70 | 10/10 | 84/554 |
| 0,80 | 10/10 | 248/554 |

Cualquier θ en el intervalo **(0,067; 0,660)** elimina los 10 falsos positivos **sin sacrificar
un solo acierto**. Esa es la afirmación robusta; 0,35 es solo un punto cómodo dentro del
intervalo, no un descubrimiento.

### 9.2 Restringir la búsqueda a solape alto

Regla propuesta: excluir del `argmax` los lags cuyo solape sea < 90 % del máximo.

#### Alcance: qué desplazamientos puede buscar esta restricción

Con señales de igual longitud (`A = B = N` en unidades de envolvente), el solape vale `N − |k|`
y su máximo es `N` (en `k = 0`). Exigir solape ≥ 0,9 · máximo equivale a **`|k| ≤ 0,1 · N`**, es
decir, un desplazamiento máximo del **10 % de la duración de la señal**:

| Duración | N (muestras) | N (env) | `|k|` máx. (env) | `|k|` máx. (muestras) | Desplazamiento máx. buscable |
|---|---|---|---|---|---|
| 4 s | 176 400 | 22 050 | 2 205 | 17 640 | **± 400,0 ms** |
| 10 s | 441 000 | 55 125 | 5 512 | 44 096 | **± 999,9 ms** |
| 15 s | 661 500 | 82 687 | 8 269 | 66 152 | **± 1 500,0 ms** |
| 20 s | 882 000 | 110 250 | 11 025 | 88 200 | **± 2 000,0 ms** |
| 30 s | 1 323 000 | 165 375 | 16 537 | 132 296 | **± 2 999,9 ms** |

#### ¿Excluye alguno de los retardos reales de la batería?

No. `EXPERIMENTAL_RESULT` sobre los 780 casos:

- casos cuyo retardo verdadero queda **fuera** del alcance: **0 de 780**;
- caso más exigente: 4 s con 100 ms de retardo, que usa **el 25,0 %** del alcance disponible;
- **holgura mínima restante: 75,0 %**.

Es decir, la restricción deja de buscar por encima de ±400 ms en la señal más corta, y el
retardo más grande del experimento es de 100 ms.

#### Efecto medido sobre la etapa gruesa

Se compara la posición del `argmax` libre con la del restringido, en los mismos 780 casos, y se
cuenta si queda **al alcance del refinamiento** (|error| ≤ 12 muestras = `ALIGN_REFINE_HALFSPAN`):

| Ámbito | Libre | Restringido |
|---|---|---|
| Global (780) | 554 | **602** |
| Retardo real 0 (60) | 38 | **44** |
| Retardo real ≠ 0 (720) | 516 | **558** |
| Casos que **empeoran** | — | **0** |
| Casos que **mejoran** | — | **48** |

(La coincidencia numérica de 554 libres con los 554 aciertos finales es casualidad: son dos
métricas distintas, una sobre la etapa gruesa y otra sobre el resultado tras refinar.)

#### Efecto sobre los falsos positivos

Los 5 falsos positivos (× 2 motores) pasan a:

| Contenido | Dur. | Ganador libre | Ganador con solape alto |
|---|---|---|---|
| `voz_armonica` | 4 s | +1439,8 ms | **+4,90 ms** |
| `percusivo` | 10 s | −4291,7 ms | **0,00 ms** |
| `percusivo_aperiodico` | 4 s | +1449,8 ms | **+5,08 ms** |
| `percusivo_aperiodico` | 15 s | +7147,3 ms | **0,00 ms** |
| `aire_reverb` | 4 s | +1394,3 ms | **+0,18 ms** |

**0 de 10 falsos positivos seguirían siendo `MISALIGNED`**: los 60 casos de retardo real 0
quedan con `|ganador| ≤ 441 muestras` (es decir, dentro de la banda `WARNING` o `ALIGNED`).

> **Cautela sobre 9.2.** A diferencia de 9.1, estas cifras son **cotas sobre la etapa gruesa**,
> no el resultado de un pipeline completo. Se evalúa la posición del `argmax` restringido, con
> resolución de 8 muestras (≈ 0,18 ms), **sin simular el refinamiento posterior**: hacerlo
> exigiría ejecutar una variante del motor, y este laboratorio no modifica el motor. Por tanto,
> las clases proyectadas son aproximadas y la estimación fina que daría la variante es `UNKNOWN`.

### 9.3 Estado de ambas propuestas

Las dos atacan piezas distintas (Pieza 4 y Pieza 3) y ambas funcionan por separado, lo que
confirma que el fallo tiene más de una causa. **No se combinan aquí, no se cuantifica su efecto
conjunto y no se elige una sobre otra**: eso corresponde a quien gobierne el motor. Quedan
como propuestas declaradas, **pendientes de validación externa sobre música real**, que esta
batería sintética no puede aportar.

## 10. Límites de lo medido, y lo que queda `UNKNOWN`

- Todo lo anterior es sobre **señales sintéticas**. `UNKNOWN`: cómo se comporta esto con
  grabaciones reales. No se extrapola.
- La F0 sintética es fija (196 Hz). `UNKNOWN`: si el salto de período de §6 pieza 2 se
  atenúa o empeora con F0 variable, voz cantada, o señales con envolvente no periódica. Esa
  pieza está declarada como `HYPOTHESIS` y no se generaliza.
- Se probaron 13 retardos. `UNKNOWN`: el comportamiento entre 10 y 25 ms está poco muestreado.
- `UNKNOWN`: por qué el desempate cae sistemáticamente en **+28** y no en **−28** (en el caso
  L/R el canal R se va a **+**28). Se constata la asimetría; no se ha demostrado su causa.
- El caso estéreo (§8) es **un único caso con una sola duración**. `UNKNOWN`: desfases
  opuestos de otras magnitudes, desfases no simétricos por canal, o diferencia de fase entre
  canales. La evaluación mono no certifica alineación estéreo en ningún caso.
- **θ = 0,35 es exploratorio** (§9.1): no validado, no incorporado al motor, no extrapolable.
  El resultado robusto es el intervalo (0,067; 0,660), no el valor concreto.
- Las cifras de solape ≥ 90 % (§9.2) son **cotas sobre la etapa gruesa**, sin simular el
  refinamiento. El efecto exacto sobre el pipeline completo es `UNKNOWN`.
- NO VERIFICADO: el efecto de estas dos propuestas sobre archivos reales del proyecto.
- NO VERIFICADO: el efecto conjunto de aplicar las dos propuestas a la vez (no se combinaron).
- El motor `sdv_sdi_mqr_engine` no se usa en la ruta de alineación, así que no se prueba aquí.

---

## 11. Reproducción

```bash
cd /home/user/fase1b/FASE_1B_RESULTADOS

# batería completa: 780 casos (~6 min, < 1,5 GB de RAM; una señal viva por vez)
python3 -u src/bloque_b.py            > results/logs/bloque_b_stdout.log 2>&1

# control de identidad: 60 casos (~3 min)
python3 -u src/bloque_b_control.py    > results/logs/bloque_b_control_stdout.log 2>&1

# agregados, contrafactuales y figuras (~2 s)
python3 -u src/analisis_b.py          > results/logs/analisis_b_stdout.log 2>&1

# humo rápido (24 casos, ~30 s)
python3 src/bloque_b.py --rapido
```

Ningún comando escribe en `/home/user/fase1b/fuentes/`. Todos los artefactos van a `results/`.

| Artefacto | Contenido |
|---|---|
| `results/alineacion_casos.csv` | 780 filas, todas las columnas medidas |
| `results/alineacion_matriz.csv` | agregado por motor × contenido × retardo |
| `results/alineacion_curvas.json` | 24 curvas NCC completas (d = 0, 4 s y 30 s) |
| `results/alineacion_identidad.json` | control de identidad (§7) |
| `results/alineacion_lr_asimetrico.json` | caso L/R (§8) |
| `results/alineacion_resumen.json` | agregados, control de identidad, barrido de θ y alcance del solape (§5, §7, §9) |
| `results/b_raw.jsonl` | 780 registros en el esquema común del proyecto |
| `results/fig_b_*.svg` | figuras (§6, §9) |
| `results/logs/bloque_b_*.log` | stdout/stderr completos |

---

## 12. Resumen en una frase

**El verificador no falla por el retardo: falla porque la superficie de correlación de
envolventes está casi empatada (diferencias de 10⁻⁷), porque el desempate cae a veces un
período de la señal más allá, y sobre todo porque la confianza que el propio motor calcula
—y que separa limpiamente el 0,01 del 0,66— no participa en el veredicto.**

Se pidió además un diagnóstico de la Curva NCC, FP/FN, tolerancia previa y barrido de
retardos y duraciones. Está en §2, §5, §6 y §11, con las cifras exactas y los artefactos
que las respaldan.
