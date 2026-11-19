# A · Un máximo localiza una copia; no identifica al dueño del reloj

**EXPERIMENTAL_RESULT · CONFIRMADO.** Los tres fallos declarados por 6C son **tres decisiones de canal vocal sobre dos composiciones**, reproducidas en cada copia. No son tres WAV distintos ni nueve causas independientes. La instrumental del mismo caso sirve de control positivo. No se modificaron las composiciones para producir este resultado.

## Verdad sin consultar los motores

[Manifiesto de origen](../ETAPA_6C_CORRECCION_EXPERIMENTAL/evidence/reserva_manifest.json) · [reconstrucción independiente y SHA de cada entrada](evidence/verdad_doble_origen.json) · [código](scripts/origenes.py). Se recuperaron y verificaron los contenedores, PCM, L y R contra los archivos sellados. Cada caso tiene 330 750 frames a 44 100 Hz. Con la receta archivada se regeneraron la vocal `V` y un fondo `B` de código distinto. Se buscó la traslación de `V` en `I−B` y se ajustaron **dos columnas**, `V[t]` y `V[t−r]`, a `Mix−B`. Esta regresión no usa `analyze_alignment`, sus semillas de envolvente ni su candidato ganador.

En **cada** columna L/R, `r=+3217` (72.95 ms). Los ajustes de rango 2 dan coeficientes (1,1) en `R_dos_origenes` y (1,1.8) en `R_replica_dominante`, salvo redondeo FLOAT; números de condición 1.0000–1.0032. Con las amplitudes nominales se recrean **bit a bit** `I = B + a·V[t−3217]` y `Mix = V + I`, respetando los redondeos de construcción. La guía V está intacta; no se desplazó el archivo. Para V hay dos explicaciones de su coincidencia con el Mix: **d=0 y d=−3217**. Para la guía I completa, que incluye el fondo independiente, existe el reloj identificado **d=0**. «La guía no se desplazó al exportarla» no implica «el detector puede atribuir a una sola aparición del Mix el patrón que observa».

## Lo que decidió cada copia

**EXPERIMENTAL_RESULT · CONFIRMADO.** Las cifras de las dos hipótesis y las decisiones coinciden en B/Hardened, C/EVO y D/MQR; se midieron los tres, no se imputó la respuesta de uno a los demás. `d` positivo = guía tardía; el motor almacena `k=−d`. En estas ventanas `tM=tG=0`, por lo que `q=k`. `ρ` es Pearson **con signo** en el solape real. El margen es `1−strength₂/strength₁` entre *máximos de onda*; la confianza emitida es `|ρ directo|·margen`, **no** una probabilidad. `—` significa nulo, no cero.

| Caso / V | ρ en d=0 (330 750 frames) | ρ en d=−3217 (327 533 frames) | margen | confianza publicada | d y clase de canal | juicio frente a la composición |
|---|---:|---:|---:|---:|---|---|
| Dos orígenes / L | +0.5700423 | +0.5655469 | .0078862 | .0044955 | 0, ALIGNED | **Fallo 1**: la diferencia de fuerza ~.00450 basta al criterio nativo, no a identificar origen. Debe ser AMBIGUOUS. |
| Dos orígenes / R | +0.5809167 | +0.5815261 | .0010478 | — | —, AMBIGUOUS | Abstención justificada: hay un candidato a −3217, **no** un d publicado. |
| Réplica dominante / L | +0.4366508 | +0.7895169 | .4469391 | .3528660 | −3217, MISALIGNED | **Fallo 2**: la réplica más potente gana ampliamente; el término a cero sigue presente. Debe ser AMBIGUOUS. |
| Réplica dominante / R | +0.4382837 | +0.7890170 | .4445193 | .3507333 | −3217, MISALIGNED | **Fallo 3**: la misma sobreafirmación en R. Debe ser AMBIGUOUS. |

Control I, dos orígenes: L/R `ρ(0)=.823158/.812197` frente al rival `ρ(d=+3217)=.394483/.417630`; confianzas `.428675/.394567`. Control I, réplica dominante: `.899596/.898837` frente a `.385296/.383482`; confianzas `.514300/.515355`. I publica cero, ALIGNED, en los cuatro canales de caso. Un segundo máximo en I no recrea su **fondo independiente**: el argumento de no unicidad es específico del rol, no «si hay dos picos, siempre es ambiguo».

| V global | Original B/D, k (escalar) | Original C, k (escalar) | Copia B/C/D | CLI experimental por defecto / permiso explícito |
|---|---|---|---|---|
| Dos orígenes | −56, WARNING | 0, ALIGNED_BY_IDENTITY | AMBIGUOUS, k nulo (L aceptado, R no) | exit 1 sin DSP / exit 0 con DSP, D `overall=fail` |
| Réplica dominante | +3217, MISALIGNED | +3217, MISALIGNED | MISALIGNED, k=+3217 (L y R coinciden en la misma réplica) | exit 1 sin DSP / exit 0 con DSP, D `overall=fail` |

El veto en ambas filas no subsana el **motivo equivocado** de la segunda. Los 30 retornos de rol por copia reensayados en las dos composiciones y los 13 testigos 6B coincidieron íntegramente con los retornos 6C archivados. No se confundió esta repetición con reserva nueva.

## Todas las hipótesis inspeccionables, no sólo las dos de la tabla

- [174 propuestas de onda y 72 semillas de envolvente](evidence/candidatos_A.csv): motor, caso, rol, canal, lag local/global, refinamiento, origen, ρ, fuerza, diferencias respecto al mejor, intersección física, decisión. Para las semillas, el ρ corresponde a **envolvente decimada**; el solape en frames describe el lag equivalente de onda, no el denominador de ese ρ. Las propuestas refinadas pueden ser vecinas de un máximo y no participan necesariamente en la brecha 1–2. No existe confianza nativa separada para cada candidato: se conserva la confianza de **decisión**, sin inventar una para los rivales.
- [Curvas completas](evidence/curvas/) e índices en `evidence/det_{B,C,D}_6C.json.gz`: 16 curvas por motor (2 casos × 2 roles × 2 canales × onda/envolvente). B y D: por ventana onda q=−165 375…+165 375 y envolvente −20 671…+20 671 **bins**; C: onda ±66 150 muestras y envolvente ±8268 bins. Onda exige ≥165 375 frames reales. Total onda+envolvente por motor: 2 976 752 / 1 190 704 / 2 976 752 posiciones inspeccionadas. Cada intervalo compartido entre archivos se revalidó por SHA de los tres arrays. Envolvente: paso 8 muestras.
- Contraste de todas las posiciones por convolución separada: 0 discrepancias de validez, máximo absoluto de diferencia en ρ o fuerza `1.12e−15` como cota redondeada. Pearson directo en los intervalos PCM de **todas** las 174 propuestas de onda: diferencia <`4.3e−14`. No es un oráculo de atribución: verifica que los números sí corresponden a esas coincidencias.

Para exportar todos los lags, incluso los no propuestos, desde la raíz (con el Python del [README](README.md)):

```sh
N=ETAPA_6D_AUDITORIA_INDEPENDIENTE
python -B "$N/scripts/curvas_a.py" C R_dos_origenes vocal L wave > /tmp/todos_C_L.csv
python -B "$N/scripts/curvas_a.py" D R_replica_dominante vocal R env --picos > /tmp/maximos_D_R.csv
```

**THEORETICAL_DEDUCTION · CONFIRMADO.** La regla de brecha `.002` separa alturas, no procedencias. La prueba de periodicidad busca una guía repetida consigo misma; aquí el patrón es aperiódico y la segunda copia **está en el Mix**. El ruido del fondo, el distinto solape y las amplitudes cambian el orden de los picos sin resolver la atribución. Tampoco el acuerdo estéreo constituye dos pruebas independientes de un solo origen.

**HYPOTHESIS · PARCIALMENTE CONFIRMADO.** Una pista aislada previa a la réplica, una marca exclusiva de fuente conocida, un reloj de captura verificable o una descomposición conjunta con componentes identificables permitirían contrastar las dos hipótesis. Aquí la disponibilidad del fondo y la receta sí permite probar la duplicación; que esa información exista en otra entrada es **UNKNOWN**. Sin ella corresponde conservar alternativas y abstenerse. No se eligió umbral nuevo ni se propuso desplazar audio.