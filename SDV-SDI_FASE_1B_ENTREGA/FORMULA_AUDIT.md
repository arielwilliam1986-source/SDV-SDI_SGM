# FORMULA_AUDIT.md — Bloque C

**Fase sintética 1B · auditoría de fórmulas: `mix_delta.py` y SDI_F2**
Fuente: copia inmutable `/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM` (10/10 SHA‑256
verificados). `mix_delta.py` se ha ejecutado como proceso; **no se ha modificado ni un byte**
ni del script ni de ningún motor.

Etiquetas: `DOCUMENTED_FACT` · `EXPERIMENTAL_RESULT` · `THEORETICAL_DEDUCTION` ·
`HYPOTHESIS` · `UNKNOWN`.

---

## 1. Declaración sobre SDI_F2 — `NOT_IMPLEMENTED`

**`SDI_F2` no existe en el paquete entregado.** No es una inferencia: se buscó la cadena en
los 10 ficheros `.py` y en todos los `.json`, `.md` y `.txt` de la fuente inmutable
(`src/bloque_c.py:auditoria()`), y el recuento es **cero coincidencias**.

| Búsqueda | Resultado |
|---|---|
| `SDI_F2` en las 10 fuentes y manifiestos | **0 apariciones** |
| `SDI_F` | 0 apariciones |
| `F2` (suelto) | 0 apariciones |

**Estado: `UNKNOWN` / `NOT_IMPLEMENTED`.** No se reconstruye, no se infiere de otras
fórmulas y no se propone una definición. Si SDI_F2 designa una magnitud del proyecto, no está
en este código y este laboratorio no puede decir nada sobre ella.

Lo único que sí existe, y que se audita aquí, es `SDI_x = mix − V_hat_x` para ramas
complementarias, que **no es** SDI_F2 ni se presenta como sustituto.

---

## 2. Fórmulas exactas  ·  `DOCUMENTED_FACT`

Transcritas del docstring de cabecera (l.3‑75) y **verificadas contra el código ejecutable**;
las líneas se comprobaron releyendo el fichero, y `results/mix_delta_auditoria.json` guarda la
correspondencia.

| Magnitud | Fórmula | Dónde |
|---|---|---|
| Residuo instrumental | `SDI_x = mix − V_hat_x` | docstring l.8‑10 |
| Complementariedad | `e_norm := mix − SDV_norm − SDI_norm` | cálculo: **l.315** |
| Delta indirecta | `Delta = SDI_identity − SDI_normal` | cálculo: **l.297** |
| Identidad declarada | `Delta_indirecta = (SDV_norm − SDV_id) + e_norm` | docstring l.20‑24 |
| Híbrido | `SDV_hibrido = SDV_norm + gain·Delta` | cálculo: **l.301** |
| Híbrido desarrollado | `= SDV_norm + gain·(SDV_norm − SDV_id) + gain·e_norm` | docstring l.32‑36 |
| Umbral de complementariedad | `COMPLEMENTARY_SNR_MIN_DB = 100.0` | **l.85** |
| Compatibilidad de entradas | `check_compatibility()` | **l.154** |
| Medición de desfase | `estimate_lag_ms()` | **l.183** |
| Aviso por desfase > 2 ms | — | **l.283‑285** |

El fichero **ya documenta con precisión** que `Delta_indirecta = Delta_directa` solo vale si
`e_norm = 0`, y que con el camino por defecto `normal + magnitudes_first` eso **no** se
cumple. Es decir: la trampa que el encargo pedía evitar («no confundir complementariedad con
separación») ya está identificada en el propio código. Este bloque no la descubre; la
**verifica** y añade la condición exacta que faltaba (§3).

---

## 3. La identidad, con su condición exacta  ·  `THEORETICAL_DEDUCTION` + `EXPERIMENTAL_RESULT`

El docstring afirma la identidad. Desarrollándola se obtiene **cuándo** se cumple, y no estaba
escrito:

```
residuo := Delta_indirecta − (Delta_directa + e_norm)
        = (SDI_id − SDI_norm) − [(SDV_norm − SDV_id) + (mix − SDV_norm − SDI_norm)]
        = SDV_id + SDI_id − mix
        =: e_id
```

> **La identidad se cumple si y solo si la corrida identity es complementaria
> (`SDV_id + SDI_id = mix`).** El residuo no es ruido: es exactamente `e_id`.

Verificado numéricamente en tres escenarios (`results/delta_identidad_residuo.json`):

| Caso | `max|residuo|` | `max|residuo − e_id|` | ¿identidad con `e_id`? |
|---|---|---|---|
| entradas compatibles | 0,000e+00 | **0,000e+00** | **sí (exacta)** |
| desfase de 5 ms en el Delta | 4,450e-01 | **0,000e+00** | **sí (exacta)** |
| polaridad invertida | 8,393e-01 | **0,000e+00** | **sí (exacta)** |

(Se comprobó también el signo contrario: con `residuo + e_id` el resultado es el **doble** del
residuo y no se anula. El signo positivo es el correcto.)

Y en el caso real con motor (v3 `normal` vs `identity`, 176 400 muestras):

| Medición | Valor |
|---|---|
| `max|Delta_ind − (Delta_dir + e_norm)|` | 2,98·10⁻⁸ |
| error relativo | 2,96·10⁻⁷ |
| `max|SDV_hib − (SDV_norm + 0,5·Delta)|` | 2,98·10⁻⁸ |

Es decir: en el caso real la identidad se cumple **dentro del redondeo de coma flotante**
(3·10⁻⁷ relativo, coherente con `e_norm` ≈ 4·10⁻⁸ medido en §5), y el híbrido escrito coincide
con la fórmula. La identidad **no es una aproximación**: es exacta salvo redondeo.

---

## 4. Complementariedad ≠ separación  ·  `EXPERIMENTAL_RESULT`

Este es el punto que el encargo pedía no confundir, y se demuestra con un control trivial
(`results/complementariedad_trivial.json`):

| Caso | SNR de `e = M − SDV − SDI` | ¿complementaria? | Separación real |
|---|---|---|---|
| **`SDV = mix`, `SDI = 0`** | **336,87 dB** | **sí** | **nula** |
| `SDV = 0`, `SDI = mix` | 336,87 dB | sí | nula |
| `SDV = V_true`, `SDI = I_true` | 325,83 dB | sí | ground truth exacta |

**La separación nula da MÁS complementariedad que la separación perfecta** (336,87 frente a
325,83 dB). `e = 0` solo dice que las dos salidas suman la entrada; no dice absolutamente nada
sobre si el vocal está en el vocal. Cualquier lectura de `e ≈ 0` como «separación correcta»
queda refutada por la primera fila.

Precisión de medida: en los dos casos triviales `e` es **exactamente 0**, y los 336,87 dB son
un valor **finito artificialmente** por el piso numérico de `snr_db` (un SNR infinito se
reporta como 336,87). En el caso correcto `e = 5,55·10⁻¹⁷` (redondeo), de ahí sus 325,83 dB.
Ambas cifras están muy por encima de cualquier umbral: la conclusión no depende de la
diferencia entre ellas.

---

## 5. Complementariedad medida, por rama y con guías degradadas

### 5.1 Con guías exactas, las tres ramas de v3 son complementarias

`EXPERIMENTAL_RESULT` (v3, 4 s, guías = `V_true` e `I_true`):

| Rama | SNR de `e` | `rms(e)` | `max|e|` | ¿≥ 100 dB? |
|---|---|---|---|---|
| `normal` | 149,02 dB | 5,57·10⁻⁹ | 4,47·10⁻⁸ | sí |
| `ratio` | 152,28 dB | 3,83·10⁻⁹ | 2,24·10⁻⁸ | sí |
| `identity` | 152,30 dB | 3,82·10⁻⁹ | 2,98·10⁻⁸ | sí |

> **Cautela importante.** Este resultado es en parte **artefacto de mis señales**: las guías
> sintéticas son exactamente `V_true` e `I_true`, y por construcción `V_true + I_true = M`.
> Si las guías suman el mix, cualquier rama que devuelva una partición de ellas lo reconstruye.
> **No demuestra** que la rama `normal` sea complementaria en uso real.

### 5.2 Con guías inexactas, `e_norm` deja de ser cero

`EXPERIMENTAL_RESULT` (v3, rama `normal`, guías degradadas a propósito):

| Guías | SNR de `e` | `max|e|` | ¿≥ 100 dB? |
|---|---|---|---|
| exactas | 149,02 dB | 4,47·10⁻⁸ | sí |
| atenuadas ×0,8 | **13,98 dB** | 1,49·10⁻¹ | **no** |
| atenuadas ×0,8 + ruido | **11,41 dB** | 2,31·10⁻¹ | **no** |

Confirmado (`EXPERIMENTAL_RESULT`): la complementariedad **depende de la exactitud de las
guías**, no de la rama. Con guías reales, `e_norm ≠ 0` y la equivalencia
`Delta_indirecta ≈ Delta_directa` deja de sostenerse, tal como el propio `mix_delta.py`
advierte cuando se ejecuta sin `--mix`.

`DOCUMENTED_FACT` no reproducido: el docstring cita «~49 dB» para el camino por defecto
`normal + magnitudes_first`. Aquí se midieron 149 / 13,98 / 11,41 dB con las guías indicadas;
**no se reprodujo el valor de 49 dB** porque ese caso requiere guías reales, que esta batería
sintética no tiene.

---

## 6. Casos límite: qué detecta y qué no  ·  `EXPERIMENTAL_RESULT`

Once pruebas contra el CLI real (`results/mix_delta_guardas.json`):

| Caso | `rc` | Salida escrita | Veredicto |
|---|---|---|---|
| base compatible | 0 | sí | correcto |
| **SR distinto** (48 kHz vs 44,1 kHz) | 1 | no | `FATAL` ✓ |
| **canales distintos** (mono vs estéreo) | 1 | no | `FATAL` ✓ |
| **longitudes distintas** sin `--allow-crop` | 1 | no | `FATAL`, sin truncar ✓ |
| longitudes distintas **con** `--allow-crop` | **1** | no | **`FATAL` por otra regla — ver §6.1** |
| **desfase 5 ms** | 0 | sí | **medido y avisado** (`−4,989 ms`, aviso >2 ms) ✓ |
| **polaridad invertida** | 0 | sí | **NO detectada, sin aviso** ✗ |
| **2 candidatos `SDI`** | 2 | no | `FATAL` listando ambos ✓ |
| **0 candidatos** | 1 | no | `FATAL` ✓ |
| `--mix` con longitud distinta | 1 | no | `FATAL` ✓ |
| `--allow-crop` **sin** `SDV_id` | **0** | **sí** | ✓ (aísla la causa de §6.1) |

### 6.1 Defecto: `--allow-crop` es inutilizable si existe `SDV_id`

`EXPERIMENTAL_RESULT`. Con la corrida identity más corta (87 200 muestras frente a 88 200), el
script recorta correctamente los tres insumos principales y lo reporta:

```
[!] --allow-crop: recorte EXPLICITO a 87200 muestras (originales: {...88200...87200})
```

…y a continuación **aborta**:

```
[FATAL] sdv_id: frames/sr/ch (87200/44100/2) != SDV normal (88200/44100/2).
        Posible mezcla de ejecuciones distintas: se aborta.
```

La causa (`DOCUMENTED_FACT`, l.266‑275): los insumos opcionales (`mix`, `SDV_id`) **nunca se
recortan** y se comparan contra el tamaño **original** de `sdv_norm`, no contra el ya
recortado. Resultado: cuando las corridas difieren de longitud **y** existe `SDV_id`, la
bandera de recorte explícito no puede funcionar nunca. Aislado el 4c: quitando `SDV_id` del
directorio, la misma operación termina con `rc = 0` y escribe la salida.

No se corrige (prohibido). Queda documentado con las líneas y la reproducción.

### 6.2 Polaridad: no hay guarda y no hay aviso

`EXPERIMENTAL_RESULT`. Con `SDI_id` invertido en polaridad, el script termina con `rc = 0`,
escribe el híbrido y **no emite ningún aviso de polaridad**. Sí imprime la línea de
consistencia, que delata el problema si alguien la lee:

```
Consistencia Delta_ind = Delta_dir + e_norm: max|residuo| = 8.393e-01
```

pero ese número no dispara ninguna alarma. Por §3, ese residuo **es exactamente `e_id`**:
la corrida identity no era complementaria. El código tiene el dato y no lo interpreta.

Comparación con el desfase: para el desfase **sí** hay umbral declarado (2 ms) y aviso
explícito; para la polaridad no hay ninguno. `UNKNOWN`: si la ausencia de guarda es una
decisión de diseño o un olvido — el motivo histórico no está en el código.

---

## 7. Lo que queda `UNKNOWN`

- **`SDI_F2`: `UNKNOWN`** por ausencia total en el código (§1). No se reconstruye.
- `UNKNOWN`: por qué el docstring cita ~49 dB para `normal + magnitudes_first`. No se
  reprodujo; haría falta una corrida con guías reales.
- `UNKNOWN`: el comportamiento con `gain` distinto de 0,5. Solo se probó el valor por defecto.
- `UNKNOWN`: si el defecto de §6.1 afecta a flujos reales del proyecto (depende de si las
  corridas normal e identity suelen tener la misma longitud).
- NO VERIFICADO: el `sidecar` de procedencia se generó y se leyó (claves `complementarity`,
  `delta_math`, `lag_sdi_norm_vs_id_ms`, `inputs` con SHA‑256), pero no se validó su
  contenido campo por campo.
- Todo lo medido usa **señales sintéticas de 2–4 s**. No se extrapola a música real.

---

## 8. Reproducción

```bash
cd /home/user/fase1b/FASE_1B_RESULTADOS
python3 -u src/bloque_c.py                > results/logs/bloque_c_stdout.log 2>&1   # ~13 s
python3 -u src/bloque_c.py --saltar-e2e   # solo auditoría estática
```

| Artefacto | Contenido |
|---|---|
| `results/mix_delta_auditoria.json` | fórmulas, líneas verificadas y búsqueda de SDI_F2 |
| `results/complementariedad.json` | `e` por rama de v3, con guías exactas |
| `results/complementariedad_guias_degradadas.json` | `e` con guías inexactas (§5.2) |
| `results/complementariedad_trivial.json` | control `e = 0` con separación nula (§4) |
| `results/delta_identidad.json` | identidad y híbrido en caso real + procedencia |
| `results/delta_identidad_residuo.json` | residuo = `e_id` exacto (§3) |
| `results/mix_delta_guardas.json` | las 11 pruebas de §6 con stdout/stderr completos |
| `results/allow_crop_sin_sdv_id.json` | aislamiento del defecto (§6.1) |

---

## 9. Resumen

1. **`SDI_F2` no está en el código**: cero apariciones. `UNKNOWN`, sin reconstruir.
2. Las fórmulas del fichero son las que su documentación dice, y el híbrido escrito coincide
   con la fórmula a 3·10⁻⁸.
3. La identidad `Delta_indirecta = Delta_directa + e_norm` se cumple **si y solo si la corrida
   identity es complementaria**, y el residuo es **exactamente `e_id`** — verificado con
   anulación exacta en tres escenarios.
4. **`e = 0` no prueba separación**: `SDV = mix, SDI = 0` da 325 dB de complementariedad y
   separación nula.
5. Las guardas de SR, canales, longitudes y ambigüedad funcionan y **no truncan en silencio**;
   el desfase se mide y se avisa por encima de 2 ms.
6. Dos huecos: **`--allow-crop` es inoperante si existe `SDV_id`** (la comparación usa el
   tamaño original) y **la polaridad invertida no se detecta ni se avisa**, aunque el propio
   script calcula el residuo que la delataría.
