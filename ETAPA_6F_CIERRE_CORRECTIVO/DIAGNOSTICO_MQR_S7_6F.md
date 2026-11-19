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
