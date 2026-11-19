# Qué cambió en la decisión de cada motor

**Unidad:** rol/canal cotejado con la composición. Los originales emiten un **escalar de rol**, no dos retardos: se compara ese mismo escalar con cada marca por separado. «Coincidencia original» cuenta números iguales, no valida la confianza antigua. No se atribuyen diferencias de cobertura a cambios en máscaras. [Matriz primaria de comparación](MATRIZ_RESULTADOS_6D.csv) · [desglose por partición](evidence/desglose.json) · [trazabilidad histórica 6C](../ETAPA_6C_CORRECCION_EXPERIMENTAL/TRAZABILIDAD_DEFECTOS.md).

### Testigos históricos reejecutados, no una segunda evaluación de los 200 casos de 6B

**EXPERIMENTAL_RESULT · CONFIRMADO.** 13 casos × 4 rol/canales por motor: 44 marcas únicas y 8 sin reloj publicable (4 periódicos, 4 constantes). Se reejecutaron originales y copias; 78 retornos originales de rol coinciden íntegros con 6B. En todos los ensayos 6D del detector se conservaron entradas, preflight, errores capturados y retornos; cero excepciones escapadas de la llamada y cero warnings Python en esos seis lotes. Un `ERROR` **devuelto** sigue siendo un error técnico.

| Motor | Coincidencias numéricas originales / 44 | Exactas 6C / 44 | Mejoras / pérdidas numéricas en los mismos canales | Abstenciones con marca | Sin reloj: rechazos correctos / 8 |
|---|---:|---:|---:|---:|---:|
| B · Hardened | 24 | 38 | +14 / −0 | 6 | 8 |
| C · EVO | 28 (8 por identidad) | 37 | +12 / −3 | 7 | 8 |
| D · MQR | 24 | 38 | +14 / −0 | 6 | 8 |

### Reserva nueva: no se suman DEV ni las dos réplicas de 6C

**EXPERIMENTAL_RESULT · CONFIRMADO.** Para **cada** motor hay 100 observaciones (25 casos, V/I y L/R): 50 marcas ALIGNED, 6 WARNING, 23 MISALIGNED; aparte 7 insuficientes, 13 ambiguas y 1 error técnico. No son 100 canciones ni réplicas estadísticas independientes. Los dos DEV por separado: 8 marcas de control, las 8 exactas por copia.

| Motor | Original: escalar coincide con marca / 79 | Copia: marca exacta | Sin señal o ERROR: estado correcto / 8 | AMBIGUOUS correcto / 13 | Publicaciones indebidas entre las ambiguas |
|---|---:|---:|---:|---:|---:|
| B | 10 | 79/79 | 8 | 4 | 9 |
| C | 50 (42 por identidad) | 79/79 | 8 | 6 | 7 |
| D | 10 | 79/79 | 8 | 4 | 9 |

Las 4 abstenciones comunes corresponden a `circular` (período 257; V/I × L/R). Las siete ambigüedades **simultáneas** no detectadas son las dos columnas de `rep_igual`, `rep_035`, `rep_165` y sólo R de `rival_R`. En los dos canales de `dos_tramos` hay además dos relojes **sucesivos**: B/D eligen uno, C rehúsa el escalar. Los errores están localizados, no diluidos en una «exactitud global». En los casos de marca única no se observó un lag falso; tal resultado no ampara las publicaciones sin origen único.

## B · Hardened

- **EXPERIMENTAL_RESULT · CONFIRMADO.** En `C_tonos_marcas_4s` I, el k de rol original era +24100; ahora I/L da 0 y R declara AMBIGUOUS. En `D_lateral_exacto_4s` V y `E_invertida_1103_4s` V recupera d=+1103; antes devolvía un extremo (−176404 en k) en el Mid cancelado o d=1116 en la inversión. En el S7 periódico no transforma confianza cero en un extremo. En DC no inventa origen. El veto por `ERROR` y el rechazo del pedido de shift se comprobaron en el consumidor.
- **EXPERIMENTAL_RESULT · PARCIALMENTE CONFIRMADO.** El máximo de todo el archivo funciona en los retardos opuestos, pero en `dos_tramos` el mejor d=−1213 recibe ρ=.3450/.2207, márgenes .04382/.01399; hay otras marcas +953 probadas por bytes. Dice MISALIGNED como si el retardo fuera único. En S5 marcado a cero, V e I de ambos canales se abstienen. Elimina una afirmación falsa, no recupera ese cero.
- **EXPERIMENTAL_RESULT · CONFIRMADO.** `duplicate_id` permite dos pares llamados P01, con entrada repetida, tanto antes como después; no hay validación global estilo MQR en B. Es un límite de inventario, no prueba de corrupción de PCM en esta medición. [CLI](AUDITORIA_CLI.md).

## C · EVO

- **EXPERIMENTAL_RESULT · CONFIRMADO.** Ya no hay retorno `ALIGNED_BY_IDENTITY` en las copias. En `F_interior_-22050_30s` V, el original publicaba 0/identidad. Ahora tG=661500, tM=595350: q=88200 da k=+22050 y d=−22050 dentro de q solicitado [0,132300]. El espejo a +22050 también es exacto. En `F_tail_+22050_70s`, tG=2425500 (55 s), sí recupera el evento final. Son pruebas del cambio de origen y de alcance del escaneo, no de búsqueda ilimitada.
- **EXPERIMENTAL_RESULT · CONFIRMADO.** En `dos_tramos` ve dos ventanas de guía desde 0 y 926100 (21 s), cada una internamente convincente, d=+953 y −1213. Conserva ambos candidatos y el estado por canal es AMBIGUOUS sin k. En réplicas *simultáneas* comete los mismos siete fallos nuevos que B/D. La selección de hasta dos ventanas disjuntas y el radio global ±66150 muestras siguen siendo límites documentados; no se reensayó toda la barrida histórica fuera de radio.
- **EXPERIMENTAL_RESULT · REGRESIÓN (cobertura numérica, no DSP).** `A_d+0_70s` I/R: con el original de rol d=0 ALIGNED, la marca coincide. La copia ve cero en la primera ventana, luego rivales de d=0 y +16, margen .001742: ya no publica cero. En `C_archivo_S5_4s` I/L y R también pierde dos coincidencias antiguas, **éstas sí por identidad**, no dos antiguas mediciones independientes. El mejor d=6900 compite con +6950 de signo contrario, margen ~.00000378. La abstención es más defendible, pero sigue costando cobertura. No hubo esa pérdida en las 79 marcas nuevas. La inversión LS del DSP preexistente no se atribuye a la correlación negativa del detector.

## D · MQR

- **EXPERIMENTAL_RESULT · CONFIRMADO.** `D_archivo_S7_4s`: original k=−176392 con «correlación» −2 en ambos roles; copia AMBIGUOUS sin número, no −2. El nuevo agregador preserva severidad: en S3, S4, Ppos e `invL` las corridas originales permitidas con MISALIGNED acababan en `overall=pass`; las copias permitidas producen `fail`, no un certificado. Se conservaron los estados por canal y se registró el permiso real.
- **EXPERIMENTAL_RESULT · PARCIALMENTE CONFIRMADO.** El agregador no puede corregir la entrada convincente pero mal atribuida: en las tres falsas admisiones de la reserva, devuelve `pass`. En controles aislados también tolera la ausencia de R dentro de un rol aparentemente ALIGNED. En `dos_tramos` su estimador de archivo completo presenta el mismo problema que B. [CLI y contrapruebas](AUDITORIA_CLI.md).
- **EXPERIMENTAL_RESULT · CONFIRMADO (defecto preexistente).** En S7, el veto por ambigüedad y el aborto posterior de métrica son dos decisiones diferentes. Incluso sin override, la sonda side con V e I correctamente alineadas aborta después del DSP. [Diagnóstico de la cresta](MQR_S7_DIAGNOSTICO.md).

**EXPERIMENTAL_RESULT · REGRESIÓN (recursos).** Para los tres motores se midió mayor asignación temporal del detector 6C que del original emparejado en los tres tamaños ensayados. Esto no es un OOM ni predice rendimiento en Android. [Medidas](RECURSOS_Y_DURACIONES.md). **DOCUMENTED_FACT · CONFIRMADO:** v3 sólo se comparó por bytes y SHA. No recibió ninguna de las decisiones, mediciones de DSP ni correcciones de las copias.