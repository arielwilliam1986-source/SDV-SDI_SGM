# Qué cambiar en cada detector y qué dejar intacto

**Estado del documento:** diseño para revisión. Toda regla o ventaja propuesta en este documento es `HYPOTHESIS · NO CONFIRMADO` hasta pasar los controles reservados; ninguna se incorporó al código. Las premisas comprobadas se marcan aparte. Aquí «corrección» significa corregir **el diagnóstico**, no el tiempo de un archivo.

## Contrato mínimo común, sin imponer un estimador común

**DOCUMENTED_FACT · CONFIRMADO.** Hay consumidores distintos: B/C pueden desplazar lecturas, D no puede ni debe, y A usa la convención de signo opuesta. Un único campo `offset=0` no distingue sincronía, candidato descartado, falta de señal, excepción y no actuación. Véanse H2, C1/C2, D1/D3 y A2 del [expediente](DEFECTOS_REPRODUCIBLES.json).

**Propuesta.** Emitir evidencia por `archivo Mix / archivo guía / par / rol / canal / ventana`. Identificar bytes, tasa, bases temporales y versión del detector. Un registro de rol puede agregar los registros L/R, no sustituirlos. Si la entrada es realmente mono y la interfaz la admite, identificar qué observación es posible; no duplicar ese dato para afirmar que se midieron dos relojes. Una incompatibilidad con la política de entrada sigue siendo un rechazo de validación, no una señal «alineada».

| Campo de revisión | Semántica propuesta |
|---|---|
| `lag_native`, `convencion`, `guide_delay_samples` | Conservar el signo nativo y ofrecer `d>0 = guía tardía`. Dar entero, fracción opcional, tasa y ms; no reusar el signo para definir el índice de lectura. |
| `candidates[]`, `estimate`, `applied_shift_samples` | Lista de candidatos con ventana de origen, lag local y global, incluido cero como hipótesis. Estimación aceptada `null` al abstenerse; no forzar candidato si ningún lag es válido. En esta propuesta de diagnóstico, acción siempre 0, independiente de `estimate`. |
| `support`, `quality`, `polarity_evidence` | Intervalo de Mix/guía en muestras, solape real sin padding, soporte activo, energías/varianzas por canal, score de envolvente, Pearson firmado, pico alternativo y su distancia, autocorrelación y acuerdo entre ventanas. El signo es evidencia separada, no una orden de inversión. |
| `confidence`, `state`, `reason`, `coverage` | No llamar probabilidad a `clip(ρ)`. Antes de calibrar, exponer componentes o nivel ordinal definido; probabilidad `null`. Explicar empate, borde de rango, ventana ciega, ruido, conflicto de canales o excepción. Registrar cobertura temporal y canales que realmente sustentan la decisión. |
| `authorization`, `run_status`, `legacy` | Registrar por separado permiso explícito (CLI/interactivo), política aplicada, si se inició/completó procesamiento y por qué. Versionar schema; conservar el registro histórico como tal. Nunca degradar un nuevo estado desconocido a `ALIGNED` para un lector antiguo. |

### Taxonomía recomendada para B/C/D

**Propuesta.** Se justifican seis estados porque separan problemas con respuestas operativas distintas. Los límites de **severidad** existentes en B/C/D no deben tomar el lugar de una prueba de **evidencia**. Evaluar calidad antes de aplicar estos límites; no modificar las clases históricas de v3.

| Estado | Condición propuesta por canal/rol | Acción del diagnóstico |
|---|---|---|
| `ERROR` | Falló lectura, contrato de formato, cálculo o apareció un valor no finito. | Conservar etapa y causa; bloquear la aceptación. Nada de confianza inventada. |
| `INSUFFICIENT_SIGNAL` | No hay suficiente señal/varianza o solape con información temporal común; faltó observar un tramo necesario. | Sin estimación válida. Distinguir canal inactivo, silencio/DC, zona no leída y candidato sin soporte. |
| `AMBIGUOUS` | Hay señal, pero picos rivales, periodicidad, desacuerdo entre ventanas, conflicto de reloj o un máximo truncado impiden elegir. | Conservar alternativas y por qué no se discriminaron. No votar por cero para resolver el empate. |
| `ALIGNED` | Únicamente tras identificar el lag y localizarlo dentro de ±1 muestra. | Informar evidencia positiva y resolución. |
| `WARNING` | Lag identificado de 2 a 441 muestras en módulo a 44.1 kHz. | Advertencia temporal **medida**; no usar esta etiqueta para «no sé». |
| `MISALIGNED` | Lag identificado de más de 441 muestras en módulo a 44.1 kHz. | Conservar dirección y soporte. Mostrar advertencia y decisión de política; no desplazar. |

**Agregación propuesta.** Para una guía estéreo, remitir siempre ambos resultados. Sólo emitir `common_delay` si los canales activos tienen estimaciones compatibles y la cobertura requerida está completa; nunca promediar −25/+25 ms a 0. Para evitar que un veto esconda otro: error técnico → estado global `ERROR` conservando toda alarma medida; si no hay error y algún canal tiene un `MISALIGNED` sustentado → global `MISALIGNED`, incluso si el otro está indeterminado, con `common_delay=null` si corresponde. Si no hay tal alarma y faltan canales requeridos → `INSUFFICIENT_SIGNAL` o `AMBIGUOUS` con razón específica. Si los intervalos de estimación por canal no se solapan, consignar `L_R_DISAGREE`, sin lag único ni acción. En ausencia de `MISALIGNED` o `ERROR`, clasificar ese conflicto como `AMBIGUOUS`; con cobertura completa y estimaciones compatibles, conservar `WARNING` si algún canal lo tiene. Congelar la tolerancia de compatibilidad antes de abrir la reserva. Sólo declarar un rol estéreo `ALIGNED` con soporte válido en ambos. Si la incertidumbre cruza un límite de clase, guardar el intervalo y marcar la decisión dudosa, no redondear la incertidumbre fuera del informe.

**Política propuesta, separada de las clases.** El diagnóstico aislado siempre entrega los registros aunque no se pueda continuar. Para una eventual integración, proponer veto por defecto ante `ERROR` y no dar luz verde automática con señal insuficiente o ambigua en canales requeridos. Conservar el aviso de un `MISALIGNED` fiable, incluso si se permite explícitamente continuar. Cualquier excepción operativa requiere reglas y registro propios; no cambiar el sentido de las banderas actuales ni callar advertencias en esta etapa.

### Cómo distinguir tiempo, amplitud y signo

**Propuesta.** En cálculos auxiliares de sólo lectura, evaluar cada canal contra **su misma columna de Mix**, por rol. Una transformación de características para medir (p.ej., RMS, centrado estadístico o detección de ataques) no cambia los archivos ni la entrada de separación. La energía del mid puede ser un dato explicativo sobre cancelación, nunca el sustituto silencioso de L/R.

1. Seleccionar ventanas con soporte compartido y contenido variable; incluir principio, interior y fin cuando existan. Rastrear las ventanas sin información, no contarlas como votos a cero. Evitar que mucha energía estacionaria desplace las pocas marcas temporales útiles. Fijar un presupuesto de lectura por rol y registrar zonas excluidas: no declarar alineada toda una pieza sólo por un prefijo.
2. Usar la envolvente para **proponer** varios máximos distintos y el candidato cero, no para resolver la pregunta final. Descartar índices inválidos mediante una máscara de validez, no con un 0 competitivo. Contrastar también candidatos derivados de ataques o correlación de onda cuando la envolvente no distingue; evaluar por lag con numerador y denominador en el **mismo solape**, comparar soporte y evitar correlaciones altas de colas diminutas. Si hay varianza cero, el coeficiente es indefinido. No sustituir el coseno positivo por una receta global copiada de A: centrar la envolvente puede mejorar su contraste o dejarla sin varianza.
3. Refinar candidatos competidores en onda centrada; puntuar coincidencia temporal de ambos signos y retener la polaridad de cada ajuste. Comparar frente a cero y frente al mejor **pico separado**, no frente al bin contiguo de la misma loma. Comprobar autocorrelación de guía y Mix en el *espaciado entre picos*, incluyendo antipicos si se usa módulo. Exigir coincidencia de índices de ataques o acuerdo en ventanas no redundantes. Si dos desplazamientos producen la misma observación, el resultado correcto es no decidir. Si hay una parábola válida, guardar su fracción sin presentarla como precisión garantizada.
4. Calibrar soporte, contraste, separación de máximos y consistencia en el banco de desarrollo; fijarlos antes de la reserva. Preferir consistencia temporal sobre «pico grande». No convertir el 0.15 de C, la AC 0.50 de A, el umbral exploratorio 0.35 de 1B ni un solape fijo del 90 % en valores universales. Por ejemplo, con archivos iguales de 4 s y retardo de 500 ms el solape máximo a ese lag es **87.5 %**: exigir 90 % descartaría la solución cierta. Un umbral que reduzca avisos pero reduzca también la cobertura debe quedar visible.

## B · Hardened: impedir que un máximo no válido gobierne la lectura

**Premisa — EXPERIMENTAL_RESULT · CONFIRMADO.** En S7 se publica un offset más largo que el archivo; en S2/I un único grueso excluye cero aun cuando la onda lo favorece. El `ERROR` del detector no entra en la lista `misaligned` del consumidor (esto último: `DOCUMENTED_FACT · CONFIRMADO`).

**Diseño B.** Mantener como generador inicial de candidatos el barrido de envolvente sobre el archivo, con solape local, haciendo explícitos validez, competencia y cobertura. Reutilizar el hecho de que B lee el archivo completo para escoger ventanas activas en ambos canales y contrastar eventos distantes, sin exigir que Mix y una guía de un solo rol tengan idéntica envolvente. Un fino sin candidatos válidos termina como insuficiente, no como primer 0. Un pico fino en el borde de ±12 sin contraste exterior no demuestra convergencia. El diagnóstico puede compartir resultados de lectura del Mix por ventana, no decisiones entre L y R.

Separar en `run_experiment` clasificación, autorización y construcción de `guide_shifts`. En un prototipo de **sólo medición** no alimentar ese diccionario. Un rechazo técnico no debe pasar por `rec.get(...,0)` como un acierto. Mantener sin cambio `read_span(start+shift)`, LS, guardián residual, STFT por modo y escritura de WAV. Si algún día Will autoriza estudiar la actuación, requerir otra especificación de signo, compatibilidad de canales y soporte; no habilitarla incidentalmente con el cambio del detector.

**Alternativa descartada como solución suficiente:** cambiar el 10 ms a 30 ms ocultaría −1212 muestras pero seguiría dejando al motor con el signo/lag de un pico ajeno. Validar B con V00/V01/V03/V05/V11 y el aislamiento de V12.

## C · EVO: corregir el dominio temporal de búsqueda y dejar de aprobar la duda

**Premisas — DOCUMENTED_FACT · CONFIRMADO.** `peak_val<0.15` fuerza identidad y un error de lectura puede obtener la misma etiqueta. El margen local no equivale a un margen global cuando los segmentos no parten de la misma muestra (C:549–625; demostración C3 en el informe).

**Diseño C.** Conservar la ventaja de seleccionar actividad, pero no una única ventana de máxima energía en mid. Escoger por canal varias ventanas útiles dentro del presupuesto, incluyendo una ventana corta válida en archivos <15 s y una que termine en EOF para no perder la cola. Anotar coordenadas de ambos segmentos y el intervalo global físicamente buscado. Para cada `k_global` permitido, la evidencia debe calcularse en `q_local=k_global+tG−tM`. Intersecar con el solape realmente disponible y marcar extremos truncados. No basta con restar `tG−tM` *después* de recortar simétricamente el lag local. V10 es la condición de aceptación específica de esta adaptación.

No volver a escribir 0 al perder fiabilidad. Conservar el cero histórico como dato *legacy*, sin presentarlo como candidato medido. En registros nuevos guardar el candidato previo a la decisión y el motivo del rechazo; la nueva clase debe distinguir falta de soporte, pico de signo contrario pero coherente en tiempo, alternativa periódica y excepción técnica. Evaluar ambos signos para el tiempo y registrar su evidencia antes de consultar la polaridad LS. No usar el LS global como reloj ni el signo de un solo canal como orden para ambas columnas. **El LS, su aplicación actual y `hybrid_asymmetric` quedan fuera del cambio**. Tampoco se adapta `guide_shifts` a dos valores: la nueva observación por canal no autoriza reescribir el procesamiento. No considerar victoria que C emita más advertencias honestas si simultáneamente pierde detección de retardos verdaderos; comprobar ambas cosas.

**Alternativa descartada:** cambiar sólo `<0.15` por `abs(ρ)<0.15`. Seguiría sin resolver el origen local, los alias y la excepción que da identidad. Validar con V02/V06/V08/V09/V10/V11.

## D · MQR: preservar la política de sólo detección y corregir qué se comunica

**Premisas — EXPERIMENTAL_RESULT · CONFIRMADO.** Dos coeficientes −2 en consola D/S7; en el JSON D/S5 dos `MISALIGNED` conviven con `validation_status.overall=pass`.

**Diseño D.** Reemplazar conceptualmente el centinela competitivo por «sin candidato válido» y un recuento explícito de solapes evaluables. El rango nominal de búsqueda, `coarse_lag_samples` y la diferencia de duración ya se registran; conservarlos y añadir cuánto solape dio evidencia para el lag. No confundirlo con la cobertura usada después por la máscara. Implementar en un futuro diagnóstico la comparación real con otros máximos/ventanas, no un comentario de prominencia. Si no hay un coeficiente, escribir `null` y la causa, nunca una cifra fuera de [−1,1]. Un cálculo por canal aquí es sólo del **reloj**; no convierte en estéreo las guías de cálculo de máscara ni añade un selector `mask_mode`.

Separar los estados de los ítems, la decisión explícita de continuar, la integridad del proceso y su resumen. Definir una tabla de severidad que abarque errores, ambigüedad y señal insuficiente además de advertencias medidas; `overall=pass` no debe parecer un certificado si hay ítems vetados. En CLI e interacción, registrar origen del permiso, no reemplazar la clase. Mantener **`detect_only_no_correction` incluso si se encuentra un desplazamiento inequívoco**. No tocar `CandidateMetrics.finalize`, las guías mid de separación, el consenso de máscaras ni los parciales conservados. La división por cero de S7 requiere otro encargo; no esconderla declarando que el detector o un veto nuevo la «reparó».

**Alternativa descartada:** limitar −2 a −1 o a 0 dejaría un offset extremo sin fundamento y lo haría más verosímil. Validar con V01/V03/V05/V11/V12; retener los dos signos del control T6 como casos auxiliares, no como batería completa.

## Transferencia desde A y decisión solicitada

**THEORETICAL_DEDUCTION · CONFIRMADO CON LIMITACIONES.** Es compatible transferir el principio de **conservar candidato y motivo de no actuación**, puntuar onda con signo visible y preguntar por periodicidad. No es directamente compatible copiar operandos FFT y signo de `shift`, conversión a mid, prefijo de 60 s, estados o límites de A. La AC alta puede corresponder tanto a un alias como a un desfase real. La polaridad de ensamble de A presupone más de una guía por rol; no constituye una referencia disponible en todas las corridas. Ninguna de estas transferencias exige modificar v3.

**Punto de revisión:** aprobar o rechazar por separado el contrato de evidencia, la selección de ventanas/rangos de cada motor y los criterios ciegos de validación. Si se autorizara un prototipo posterior: comenzar en modo de diagnóstico paralelo que no alimente el DSP; comparar con los originales; sólo discutir integración con un informe de resultados. **No hay autorización implícita para implementar, corregir audio o pasar a música.**
