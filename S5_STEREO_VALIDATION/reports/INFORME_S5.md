# S5 · ¿Decide cada canal su propia máscara?

**En las condiciones medidas, v3 `identity`, Hardened y EVO sí lo hacen en `per_channel`. En `mono` los tres comparten la máscara; MQR también la comparte y no ofrece ese selector.** Compartir una máscara no convierte el Mix en mono: las dos STFT de salida conservan los dos canales del Mix. Lo que se pierde es la posibilidad de tomar dos decisiones distintas en una misma celda tiempo–frecuencia.

**Balance experimental:** 48 de 49 corridas principales completadas; 7 de 7 controles unilaterales y 3 de 3 controles EVO completados. **58 de 59 en total.** MQR en S7 (antifase) abortó después de escribir audio; no se cuenta como ejecución satisfactoria. No se eligió un ganador.

## Qué se midió

- **DOCUMENTED_FACT** — Fuentes de `main` fijadas a `b64f15ae8b28e46eef3c024dc62c85fe27c69494`; las cuatro [copias](../source_hashes.json) son idénticas a los blobs y a los hashes de Fase 1B. No se cambiaron los motores. Python 3.11.2, NumPy 1.26.4, SciPy 1.13.1, SoundFile 0.13.1, libsndfile 1.2.2; [memoria y entorno](../environment.json). El [preflight inicial](../logs/preflight_inicial.log) no pasó por falta de dependencias; se autorizó un venv aislado, no una instalación de sistema.
- **DOCUMENTED_FACT** — Cada fixture tiene Mix y guías **estéreo, WAV FLOAT, 44 100 Hz, 176 400 frames, 4 s**. El [manifiesto de señales](../signals/manifest.json) define muestra por muestra cada par. En la matriz principal hay un único par sintético; «V» e «I» denotan roles conocidos, no estimaciones de voz real. FFT 4096, hop 1024, ventana Hann del motor, sin suavizado. Sin normalización, limitador, EQ, remuestreo del audio, compensación temporal ni MVSEP. Los ajustes `p` y `ε` se fijaron por motor, **no cambiaron entre modos del mismo motor**.
- **EXPERIMENTAL_RESULT** — Se observaron los arrays reales del candidato escrito **antes de la OLA**, no una máscara estimada dividiendo WAV ni un mapa diagnóstico promediado. La [sonda](../scripts/observador.py) lee locales mediante el profiler de CPython; nunca reemplaza una función ni escribe en un frame. En cada corrida hubo 175 tramas TF: tres chunks de 64, 64 y 47. Para cada chunk se registraron dimensiones de guías, Mix, máscara, SDV y SDI. En todos los chunks capturados, incluso en el aborto, los máximos de `|Yv−X·M|` y `|Yi−X·(1−M)|` fueron **0**.
- **EXPERIMENTAL_RESULT** — Las medidas de audio se calcularon sobre **cada canal del WAV releído**. El [CSV](../measurements/resultados.csv) incluye RMS, pico de muestra, pico interpolado 4× (estimación FIR polifásica Kaiser, no medidor certificado), correlación L/R (`vacío` si es indefinida), no finitos y hashes del contenedor y del PCM. El pico 4× es sólo una medición. En los 58 pares completados, el máximo de `|SDV+SDI−Mix|` sobre muestras y canales fue `1.141×10⁻⁸` FS (redondeado). Esto mide reconstrucción, no acierto en la atribución de una fuente.

## Prueba que distingue independencia de simple simetría

**EXPERIMENTAL_RESULT** — S2 hace coincidir 441 Hz con V en L y con I en R. S6 permuta **todo** S2 (Mix y guías). Tras deshacer la permutación, la diferencia máxima fue 0 para ambas salidas y la máscara efectiva en **las siete configuraciones**, incluida MQR. Un algoritmo de máscara compartida también puede superar S6.

Por eso se añadió un control unilateral (`Ronly`): **mismo archivo Mix**, guías L idénticas a S2, roles V/I permutados **sólo en la guía R**. Una decisión compartida puede cambiar el WAV L aunque no cambien ni el Mix L ni sus guías. Resultados respecto de S2 (RMS de diferencias de muestras, en FS, sin nivelar):

| Motor / modo | max. cambio de la máscara L | RMS ΔSDV L | RMS ΔSDV R |
|---|---:|---:|---:|
| v3 identity · per_channel | 0 | 0 | 0.150314 |
| v3 identity · mono | 0.500000 | 0.078234 | 0.075157 |
| Hardened · per_channel | 0 | 0 | 0.150311 |
| Hardened · mono | 1.000000 | 0.049481 | 0.119482 |
| EVO · per_channel | 0 | 0 | 0.150311 |
| EVO · mono | 1.000000 | 0.049481 | 0.119482 |
| MQR · compartida | 1.000000 | 0.047971 | 0.119111 |

Valores redondeados; `1.000000` no afirma saturación exacta. En los tres `per_channel` tampoco cambió **ninguna muestra de SDI L**, mientras sí cambió R. Máscaras completas, sus dos estadísticas de canal cuando existen y contrastes de SDI y SDV sin redondear: claves `runs[].observation` y `contrasts` en cada JSON.

## S5-A · v3, exclusivamente `identity`

**DOCUMENTED_FACT** — [`apply_mask`](../sources/MOTOR_SEP_SDV-SDI_v3.py#L672-L715) calcula por canal `m_c=|V_c|^p/(|V_c|^p+|I_c|^p+ε)` sobre el consenso complejo. En `mono` **promedia esas dos máscaras ya calculadas**, no las formas de onda. `normal` devuelve los espectros de consenso y `ratio` tiene otra construcción: ninguna de esas ramas se ejecutó. Se llamó a `run_processing` con `p=1.95`, `ε=10⁻¹²`, `write_wavs=True`, sin shifts, gains, LOO ni referencias. No se llamó a `main`, que ejecutaría la auditoría de alineación excluida de S5.

**EXPERIMENTAL_RESULT** — Máscara completa `(2,2049,175)` en `per_channel`; `(1,2049,175)` en `mono`. La comprobación del promedio antes de la aplicación dio error máximo 0. En S2, cambiar de modo dio RMS ΔSDV **0.078365 L / 0.067364 R** y ΔSDI **0.078365 / 0.067364**. En S7 las magnitudes son iguales en ambos canales aunque sus signos sean opuestos: ambos modos dieron las mismas muestras y RMS SDV **0.146911** por canal. No ocurrió el colapso por downmix observado en otros motores. [Datos A](../results/s5_a_v3.json) · [WAV y máscaras A](../evidence/S5-A.tar.xz).

## S5-B · Hardened 3.1.1

**DOCUMENTED_FACT** — `full_processing`, `magnitudes_first`, `confidence_weighted_mean`, `p=1.8`, `ε=10⁻¹²`, `use_physical_residuals=False`, sin corrección de alineación. La [ruta de guías](../sources/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py#L1463-L1501) distingue STFT de `v_span/i_span` estéreo y STFT de sus downmix. Una media L/R para estadísticas o mapas 2D no implica que se haya aplicado esa media al Mix ([aplicación](../sources/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py#L1574-L1595)).

**EXPERIMENTAL_RESULT** — El guardián no rechazó las combinaciones. En el primer chunk las guías pasaron de `(68608,2)` a espectros `(2,2049,64)` en `per_channel`; en `mono` se suministró `(68608,1)` igual a `(L+R)/2` y se obtuvo `(1,2049,64)`. El Mix y los dos espectros de salida siguieron siendo `(2,2049,64)` **en ambos modos**. Las máscaras aplicadas completas fueron `(2,2049,175)` y `(2049,175)`. En S2, ΔSDV y ΔSDI entre modos dieron **0.049486 L / 0.060501 R** RMS. En S7, `per_channel` dio RMS SDV **0.144226** por canal; en `mono` el downmix de las guías, la máscara vocal y el WAV SDV fueron cero, pese a un Mix no silencioso. [Datos B](../results/s5_b_hardened.json) · [WAV y máscaras B](../evidence/S5-B.tar.xz).

## S5-C · EVO

**DOCUMENTED_FACT** — Misma configuración principal que B, con residual físico desactivado. EVO [estima un signo LS por par y rol](../sources/MOTOR_SEP_SDV-SDI_EVO.py#L627-L674) usando el downmix y [lo aplica al span estéreo](../sources/MOTOR_SEP_SDV-SDI_EVO.py#L1561-L1608) antes de elegir las guías de la STFT. Esto no es una corrección independiente de polaridad por canal.

**EXPERIMENTAL_RESULT** — Se observaron máscaras `(2,2049,175)` en `per_channel` y `(2049,175)` en `mono`. S2: RMS ΔSDV y ΔSDI **0.049486 L / 0.060501 R**. S7: RMS SDV por canal **0.144226** en `per_channel` y **0** en `mono`. El cambio sólo a R dejó L intacto únicamente en `per_channel`.

**Controles separados de la matriz principal.** Con dos pares distintos (`Ppos`, `Pneg`), se invirtió sólo la guía V del segundo par. Su LS pasó de **+1.791158 a −1.791158**; sólo ese rol recibió signo −1. En cada chunk la comparación entre el span realmente enviado a STFT y `signo × lectura cruda` dio máximo 0. Los WAV y máscaras de ambos controles tuvieron diferencia muestral máxima 0. La igualdad de WAV sola **no** probaría la corrección: estas máscaras usan magnitudes.

En otra corrida, `Ppos`, dos pares, `per_channel`, mismo `p`, `ε`, `β=1`, sin residual ni suavizado: se varió sólo el orden a `hybrid_asymmetric`. La [fórmula híbrida](../sources/MOTOR_SEP_SDV-SDI_EVO.py#L1657-L1691) combina el consenso de máscaras vocales con una máscara instrumental de magnitudes y renormaliza. Se observó RMS ΔSDV **0.003453 L / 0.003712 R** frente al **control de dos pares**, no frente a S2 de un par. Es un cambio de resultado, no una mejora. [Datos C](../results/s5_c_evo.json) · [WAV y máscaras C](../evidence/S5-C.tar.xz).

## S5-D · MQR

**DOCUMENTED_FACT** — No se pasó ni existe `--mask-mode`. `full_processing`, consenso `confidence_weighted_mean`, `p=2`, `ε=10⁻⁹`, suavizado apagado. El motor [promedia las guías antes de la STFT](../sources/sdv_sdi_mqr_engine.py#L2322-L2336); [difunde el mismo mapa 2D](../sources/sdv_sdi_mqr_engine.py#L2408-L2420) sobre los dos canales del Mix.

**EXPERIMENTAL_RESULT** — En los spans observados, la entrada real a la STFT de cada guía coincidió exactamente con `(L+R)/2`. Una máscara `(2049,175)` actuó sobre ambos espectros. En S3 la razón RMS R/L **0.25** se conservó en las dos salidas, y S6 pasó el intercambio exactamente. Ninguno de esos resultados implica decisiones L/R independientes: el control unilateral cambió SDV L en **0.047971** RMS. En S4 apareció energía de R en el destino SDV aunque el V sintético de R era cero.

**Fallo reproducible S7:** el downmix de ambas guías fue cero, la máscara vocal observada fue cero en las 175 tramas y hubo dos WAV en el directorio `aborted`. La relectura dio RMS L/R de SDV **0/0**, de SDI **0.191964/0.191964**. `CandidateMetrics.finalize` intentó calcular `crest_factor_sdv` con denominador cero y terminó con **`ZeroDivisionError`, exit 2** ([traceback](../logs/aborto_D_S7_shared.log), [fuente](../sources/sdv_sdi_mqr_engine.py#L1949-L1954)). Es evidencia del recorrido y del fallo, **no un resultado final válido de MQR**. Sin reintento modificado ni datos imputados. [Datos D](../results/s5_d_mqr.json) · [evidencias D, incluido el aborto](../evidence/S5-D.tar.xz).

## Qué diagnostica cada señal

| Señal | Observación sobre muestras, no valoración musical |
|---|---|
| S1 · identidad L=R | SDV L=R y SDI L=R en todas las configuraciones; `per_channel` y `mono` dieron lo mismo donde existen ambos. No significa que SDV deba ser igual al Mix. |
| S2 · bandas asimétricas | La misma banda cumple roles opuestos. En `per_channel`, la RMS de `M_L−M_R` ponderada por energía del Mix fue 0.950968 (v3), 0.946571 (Hardened), 0.946571 (EVO). En máscara compartida la diferencia **efectiva** es cero por difusión, no por disponer de dos estimadores idénticos. |
| S3 · nivel R=L/4 | Error RMS `R−L/4` en ambos stems ≤7.61×10⁻¹⁰ FS; cero en los modos compartidos. Preservar esta proporción no demuestra independencia. |
| S4 · eventos exclusivos | En la ventana del evento V exclusivo L (0.5–1 s), RMS SDV **R** fue 0 en los tres `per_channel`; **0.028284** (v3 mono), **0.031361** (Hardened/EVO mono), **0.032037** (MQR). En el evento I exclusivo R (2–2.5 s), RMS SDI **L** fue ≤7.48×10⁻¹⁰ en `per_channel`, frente a 0.028284, 0.029400 y 0.029978 respectivamente en los compartidos. Es asignación al stem de contenido local ya presente en ese canal del Mix; no es transferencia de muestras L→R. |
| S5 · retardos | El Mix R es exactamente L retardado 2205 muestras en la región común. RMS `SDV_R[n]−SDV_L[n−2205]` ≈2.16×10⁻⁵ FS en v3 per_channel y 2.08×10⁻⁵ en Hardened/EVO per_channel; 0.008695, 0.008965 y 0.009309 en los modos compartidos de v3, Hardened/EVO y MQR. Son errores contra un retardo *conocido*, no una estimación de alineación. |
| S6 · canales intercambiados | Error máximo 0 al intercambiar de vuelta los dos stems y la máscara efectiva en las siete configuraciones. |
| S7 · antifase | El Mix lateral tiene RMS 0.191964 por canal. Promediar formas de onda antes de construir la máscara cancela las guías; promediar máscaras después de las magnitudes no las cancela. En MQR falló además el cierre de métricas. |

## Alcance y siguiente revisión

- **THEORETICAL_DEDUCTION** — Una sola ganancia TF no puede, en la misma celda, retener todo en L y rechazar todo en R. Puede preservar simultáneamente la fase propia de cada canal, una relación de niveles y la simetría bajo intercambio. Las diferencias de WAV, por sí solas, no identificarían en qué punto se compartió información.
- **HYPOTHESIS** — El pequeño residuo de traslación de S5 aun en `per_channel` puede depender de la posición del evento en la rejilla STFT: 2205 no es múltiplo del hop de 1024. No se aisló causalmente ese efecto aquí.
- **UNKNOWN** — Calidad perceptual, separación de música, comportamiento con otros pares, kernels y FFT, y robustez de la detección de polaridad cuando sólo un canal de una guía se invierte. No se evaluaron las ramas `normal`/`ratio` de v3, su alineación, ni los residuales físicos. Para MQR S7 no hay informe final nativo exitoso. No se extrapolan fallos a señales no ensayadas.
- **Después, sólo con revisión de Cris y autorización de Will:** contrastar retardos múltiplos/no múltiplos de hop y perturbaciones de signo de un solo canal; replicar con más pares sintéticos no equivalentes; acotar el caso de métricas de energía nula en MQR sin alterar esta evidencia. No se aplicó ni se propone como resultado un parche.

**Reproducción y custodia:** [instrucciones](../README.md), [construcción matemática y hashes de entrada](../signals/manifest.json), [consola de las 59 corridas](../logs/ejecucion_completa.log), [índice de paquetes sin pérdida](../evidence/index.json), [hashes de cada miembro](../hashes/MIEMBROS_SHA256.txt), [control de calidad](../results/control_calidad.json).
