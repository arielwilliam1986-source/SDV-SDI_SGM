# Etapa 6B · Validación experimental de los cuatro detectores de alineación

**Dictamen — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Con marcas inequívocas y un reloj común, los cuatro reconocieron la sincronía exacta. Con retrasos reales de ambos signos, v3, Hardened y MQR recuperaron **42/42** retardos no nulos del barrido temporal principal; EVO, **30/42**. Las doce diferencias se concentraron en **guías adelantadas y ventanas interiores**. Esto no establece un ganador: los tres que pasan ese barrido también emiten desfases sin soporte, y ninguno devuelve dos relojes L/R.

## Qué se ejecutó y qué cuenta como resultado

**EXPERIMENTAL_RESULT · CONFIRMADO.** Se completaron las **800 ejecuciones físicas caso–motor** previstas (200 casos × 4 originales). Cada una solicitó el resultado del par P1, roles V e I. Se añadieron cuatro ejecuciones técnicas X con una lectura fallida deliberada; **las cuatro constan como fallos, no como aprobaciones**. En total: 804 contextos, 1407 llamadas al detector completo (v3 devuelve dos roles por llamada; B/C/D se invocan por rol) y 3216 filas de contraste L/R, incluidas las de X sin estimación. No hubo fallo técnico imprevisto en los archivos físicos ni intento de separación, shift o corrección de polaridad. Un retorno íntegro no implica un diagnóstico acertado.

**EXPERIMENTAL_RESULT · CONFIRMADO.** En X, v3 propagó `LibsndfileError` al abrir V y nunca intentó I; B y D devolvieron `ERROR` en V; C devolvió cero/`ALIGNED_BY_IDENTITY` **con error explícito**. B/C/D sí devolvieron `ALIGNED` en la I válida. Nada de esto convierte el caso completo en éxito. Por separado, la comprobación previa de guías de v3 rechazó **15 roles físicos en 12 casos** por silencio o RMS insuficiente; las respuestas de `audit_alignment` constan como mediciones directas, no como aprobación de la CLI.

| Diseño físico | 4 s | 30 s | 70 s | Pregunta |
|---|---:|---:|---:|---|
| A · tiempo | 24 | 16 | 16 | Cero, ±1 muestra, ±5/10/11/25/100/500 ms, copia exacta y controles de frontera. |
| B · estéreo | 11 | 11 | 11 | Un canal, dos relojes, asimetría de amplitud/espectro, eventos exclusivos y swap. |
| C · estructura | 12 | 10 | 10 | Repetición indistinguible frente a repetición con marca, transitorios y ruido aperiódico marcado. |
| D · energía | 9 | 8 | 8 | Silencio, DC, atenuación, guía muda, casi cancelación y lateral exacto. |
| E · polaridad | 8 | 8 | 8 | Cuatro patrones de signo, con y sin un retardo real de +1103 muestras. |
| F · ventanas | 9 | 9 | 12 | Principio, interior, cola y dos regiones distintas después de 60 s. |
| **Total** | **73** | **62** | **65** | Los controles técnicos X quedan fuera. |

**EXPERIMENTAL_RESULT · CONFIRMADO.** En los tres paquetes se reabrieron y verificaron **338 WAV distintos** (4 033 934 804 bytes sin comprimir): FLOAT, dos canales, 44100 Hz, 176400/1323000/3087000 frames, sin muestras no finitas. En una segunda generación, **1000 referencias a WAV** de las recetas dieron exactamente los mismos 338 SHA. El oráculo, sin consultar ninguna estimación, clasificó las 800 combinaciones físicas caso–rol–canal en **427 ceros y 263 retardos no nulos con marca**, 68 tiempos ambiguos y 42 sin información suficiente. Comprobó los dos canales de las entradas, no un WAV mono paralelo. [Oráculo y pares de bytes iguales](evidence/oraculo.json) · [verificación desde los resultados originales](evidence/control_calidad.json).

## Cuándo comparar estimación, aviso y fiabilidad

**EXPERIMENTAL_RESULT · CONFIRMADO.** Barrido A principal: misma mezcla por duración, sólo se altera el tiempo de V, idéntico en L y R. Cada caso se cuenta **una vez**, no dos. En cada duración hay siete retardos positivos y siete negativos, además de cero. La tabla usa el **retardo publicado en muestras**, no sólo la etiqueta.

| Motor | Exactos no nulos a 4 s (+ / −) | A 30 s (+ / −) | A 70 s (+ / −) | Ceros parciales correctos | Desfases >10 ms etiquetados MIS en este barrido |
|---|---|---|---|---:|---:|
| v3 | 7/7 · 7/7 | 7/7 · 7/7 | 7/7 · 7/7 | 3/3 | 24/24 |
| Hardened | 7/7 · 7/7 | 7/7 · 7/7 | 7/7 · 7/7 | 3/3 | 24/24 |
| EVO | 7/7 · 7/7 | 7/7 · **1/7** | 7/7 · **1/7** | 3/3 | **16/24** |
| MQR | 7/7 · 7/7 | 7/7 · 7/7 | 7/7 · 7/7 | 3/3 | 24/24 |

**EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Al ampliar a **todo el banco físico, rol V**, la comparación es por **canal de verdad** contra el único escalar que publica cada motor. Hay 85 ceros y 257 no ceros con marca; 203 de estos últimos superan 441 muestras. No son observaciones independientes. «Cero compatible» exige, además de coincidencia numérica, señal en lo observado por el motor, decisión no censurada y ausencia de conflicto de reloj entre columnas (regla completa en el [README](README.md)).

| Motor | Publicó 0 / 85 ceros | Cero compatible / 85 | FP: cero → MIS / 85 | Cero → WARNING / 85 | No cero → AL o identidad / 257 | FN severo: → AL o identidad / 203 | No ceros numéricamente exactos / 257 |
|---|---:|---:|---:|---:|---:|---:|---:|
| v3 | 69 | 52 | 16 | 0 | 69 | 15 | 189 |
| Hardened | 53 | 50 | 23 | 9 | 21 | 3 | 200 |
| EVO | **80** | **48** | **2** | 3 | 94 | **68** | 162 |
| MQR | 53 | 50 | 23 | 9 | 21 | 3 | 200 |

**Interpretación — EXPERIMENTAL_RESULT · CONFIRMADO.** De los 80 ceros publicados por EVO sobre ceros reales, **29** proceden de `ALIGNED_BY_IDENTITY`. La columna «no cero → AL o identidad» incluye desplazamientos pequeños que la política original **tolera conscientemente**, incluso si los estima con exactitud. No es lo mismo que perder el retardo en la estimación. Entre los 203 severos, v3 retiró además 18 candidatos por periodicidad: no son 18 aprobaciones `ALIGNED`, pero tampoco 18 alertas `MISALIGNED`. El rol I no debe diluir la comparación: casi siempre se dejó intacto. Entre sus **342 ceros con marca**, los FP severos fueron 18/24/4/24 para v3/B/C/D. En las seis comparaciones I con retardos opuestos, v3 no aprobó ninguna, pero falló el signo en tres. Una clase severa correcta no rescata un reloj erróneo.

**EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Error en muestras del **valor efectivo publicado**, rol V. El máximo y el error medio incluyen los extremos espurios cuando el mid falla a pesar de haber marcas por canal. La mediana del error absoluto fue **0 para los cuatro** y, por ello, no distingue estos riesgos. La MAE de magnitud usa `abs(abs(d_publicado)−abs(d_real))`; los errores de signo requieren dos valores no nulos de signos opuestos. Un no cero sustituido por 0 se cuenta aparte.

| Motor | MAE de magnitud, 342 comparaciones | Máximo error absoluto en muestras | Signo opuesto / 257 no ceros | No cero publicado como 0 / 257 |
|---|---:|---:|---:|---:|
| v3 | 213644.82 | 2668049 | 31 | 33 |
| Hardened | 83105.64 | 1323012 | 6 | 9 |
| EVO | 1334.96 | 22050 | 6 | 82 |
| MQR | 83104.94 | 1323012 | 6 | 9 |

Los 1132 estratos de [DESGLOSE_METRICAS.csv](DESGLOSE_METRICAS.csv) separan **grupo, duración, magnitud, signo, canal y rol**, incluido el cruce conjunto. [MATRIZ_RESULTADOS.csv](MATRIZ_RESULTADOS.csv) conserva el valor individual, error, score, estado original y externo; [RESULTADOS_DETECTORES.json](RESULTADOS_DETECTORES.json) resuelve la línea primaria y su SHA. No se impone una tolerancia de producción ni se interpreta una menor MAE por sustitución de candidatos como mayor fiabilidad.

## Punto de control para Cris y el usuario

1. **¿Quién reconoce mejor la sincronía exacta? — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Empate en los controles limpios: 3/3 con V parcial en tiempo y 3/3 con V=Mix para cada motor. En el banco amplio, v3, B, C y D sustentaron respectivamente 52, 50, 48 y 50 de los 85 ceros de V con el criterio externo. Contar sólo ceros publicados invertiría la lectura sobre EVO. No hay base para elegir un motor general.
2. **¿Y los retardos reales? — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** v3/B/D recuperaron los 42/42 del barrido simétrico, EVO 30/42. En material marcado con AC alta, B/C/D pudieron acertar un desplazamiento que v3 había estimado bien y luego retiró. Con dos relojes ninguno puede devolver ambos. Véase la [comparación pareada](COMPARACION_CON_V3.md), que distingue tiempo, signo y clase.
3. **¿Quién confunde periodicidad con sincronía o desfase? — EXPERIMENTAL_RESULT · CONFIRMADO.** Los cuatro. En los 68 contrastes físicos de canal/rol cuyo origen es indistinguible, **ninguno** emitió un estado original de ambigüedad ni la guarda de v3. En los tres `C_tono` de 4 s (0, +1200 y −1200) son exactamente los mismos tres WAV: todos dan V=0 `ALIGNED`. En otros controles periódicos hubo `MISALIGNED` o `WARNING`. Por separado, la guarda de v3 sí se activó en señales con marcas; no es un test general de unicidad.
4. **¿Ventana interior? — EXPERIMENTAL_RESULT · CONFIRMADO.** EVO acepta ambos signos al principio de 30 s, pero en `F_interior_-22050_30s` el retardo adelantado cae fuera del rango local elegido y termina en identidad. El espejo +22050 sí se recupera. En 70 s se distinguen dos puntos ciegos: v3 no observa nada de lo que empieza después de 60 s; EVO puede ver 62–66 s pero no una guía activa sólo tras 67.5 s.
5. **¿Quién pierde L/R? — EXPERIMENTAL_RESULT · CONFIRMADO.** Todos los detectores devuelven un escalar por rol. Con retardo sólo en L y sólo en R, pese a las dos verdades opuestas bajo intercambio, cada motor conserva su misma respuesta. No se deduce de esto cómo operan sus máscaras: no se probó separación.
6. **¿Antifase, silencio y baja energía? — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** En el lateral exacto de 4 s, V tiene d=+1103 en ambos canales; con mid nulo, los k nativos fueron v3 −176399, B −176404, C 0 por identidad y D −176392 con NCC −2. Ninguno rechazó explícitamente las **42** columnas/roles sin información como señal insuficiente. La casi cancelación y la atenuación sin ruido no equivalen al silencio: `D_casi_lateral_4s` y `D_guia_debil_4s` sí permitieron recuperar +1103 a los cuatro detectores directos.
7. **¿Qué defectos se reprodujeron? — EXPERIMENTAL_RESULT · CONFIRMADO.** Pico de envolvente que excluye el tiempo real; retorno extremo sin soporte; censura de Pearson bajo/negativo y excepción como identidad en EVO; asimetría de ventana; ceguera del prefijo de v3; pérdida de lateralidad. D emitió **−2 en 22 registros de par/rol: 15 V y 7 I**. No son 44 resultados independientes L/R. De sus 200 resúmenes físicos aislados, **129 dijeron `pass` pese a tener algún ítem `MISALIGNED`**. Esto prueba una discrepancia entre resumen e ítems, no que las 129 alarmas fueran falsas. El control técnico con V en `ERROR` también dio `pass`. Las rutas y causas están en el [análisis por motor](ANALISIS_POR_MOTOR.md).
8. **¿Qué correcciones están justificadas? — THEORETICAL_DEDUCTION · CONFIRMADO CON LIMITACIONES** como requisitos, **HYPOTHESIS · NO CONFIRMADO** como implementación. B: impedir que un candidato sin evidencia llegue a una decisión firme y comparar hipótesis temporales competidoras. C: buscar en coordenadas globales, cubrir la cola y nunca traducir incertidumbre o excepción a identidad. D: distinguir «ningún candidato» de una correlación y propagar los ítems al resumen, sin añadir corrección de audio. Los tres necesitan evidencia L/R si pretenden certificar L/R. No hay prueba de que baste subir un umbral o copiar la guarda de v3.
9. **¿Qué riesgo permanece? — THEORETICAL_DEDUCTION · CONFIRMADO CON LIMITACIONES.** Un escalar incorrecto por rol podría actuar sobre las dos columnas si se lo conecta a una lectura desplazada. Reducir FP a costa de identidades forzadas puede ocultar retardos reales. Un buen retorno de proceso o un `pass` no acredita temporalidad. No se midió ni se autorizó ninguna actuación.
10. **¿Qué falta? — UNKNOWN · UNKNOWN.** Umbrales calibrados en otros estímulos, ruido frente a simple atenuación, deriva y retardos fraccionarios, polaridad parcial por bandas, más pares y cobertura de ventanas. Un eventual prototipo deberá volver a medirse con reserva independiente y comprobar no regresión de máscaras, signos y PCM. [Límites y pruebas no realizadas](LIMITACIONES_Y_CASOS_UNKNOWN.md).

**Punto de parada:** evidencia para decidir, no reparación. Los cuatro originales, las entregas anteriores y `main` quedan intactos. No iniciar cambios ni pruebas musicales sin revisión y autorización expresas de Cris y del usuario.
