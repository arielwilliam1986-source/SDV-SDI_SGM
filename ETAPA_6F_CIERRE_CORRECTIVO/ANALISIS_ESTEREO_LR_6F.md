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
