# Comparación pareada con v3 · mismo WAV, distinta pregunta

**EXPERIMENTAL_RESULT · CONFIRMADO.** Aquí sí se ejecutó `audit_alignment`. La referencia no es el resultado `identity` de separación de S5. Cada comparación usa el **mismo hash de Mix y de guía** para los cuatro motores. En la tabla, los números son muestras, **ya convertidas a d positivo = guía tardía**. Se muestra el valor publicado/efectivo, no el candidato descartado salvo indicación. AL = `ALIGNED`, MIS = `MISALIGNED`, ID = `ALIGNED_BY_IDENTITY`, G = `PERIODIC_PEAK_IGNORED`.

| Caso, V salvo indicación | Verdad L/R | v3 | Hardened | EVO | MQR |
|---|---|---|---|---|---|
| `A_d+0_4s`, guía parcial | 0/0, identificable | 0 AL | 0 AL | 0 AL | 0 AL |
| `A_d+1_4s` | +1/+1 | +1 AL | +1 AL | +1 AL | +1 AL |
| `A_d-221_4s` | −221/−221 | −221 AL | −221 WARNING | −221 WARNING | −221 WARNING |
| `A_d-485_4s` | −485/−485 | −485 MIS | −485 MIS | −485 MIS | −485 MIS |
| `C_tono+1200_4s` | +1200 plantado, indistinguible de 0 | 0 AL | 0 AL | 0 AL | 0 AL |
| `C_alta_AC_4s` | +1200/+1200, marcas únicas | +1200 candidato → **0 G** | +1200 MIS | +1200 MIS | +1200 MIS |
| `B_solo_R_4s` | **0/+1103** | 0 AL | +564 MIS | 0 ID | +564 MIS |
| `E_invertida_1103_4s` | +1103/+1103; ambos signos de V invertidos | +1103 MIS | +1116 MIS | 0 ID | +1116 MIS |
| `C_archivo_S5_4s`, **I** | 0/0, marcas únicas | +6900 candidato → **0 G** | +6436 MIS | 0 ID | +6436 MIS |

**Qué demuestra el primer bloque — EXPERIMENTAL_RESULT · CONFIRMADO.** La diferencia en ±5/10 ms puede ser sólo de **política**, no de estimación: uno admite hasta 10 ms y los otros advierten a partir de 2 muestras. En cambio, un ID con retardo sustituido por 0 no es «la misma estimación pero otra etiqueta». La resolución nativa es un entero en v3 (1/44100 s ≈ 0.02268 ms); en B/C/D el grueso avanza en bloques de 8 (≈0.1814 ms), se refina a paso de 1 y se interpola para ms antes de redondear las muestras. Una fracción impresa no demuestra precisión submuestral.

**Qué aporta la guarda — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** En el I de la última fila v3 retuvo un candidato falso sin declararlo como desplazamiento accionable. En la fila de AC alta retiró uno verdadero. En los tonos sin marca no avisó de ambigüedad al seleccionar cero. «Ignorar un pico», «medir cero» y «audio sincronizado» son tres afirmaciones diferentes. Conservar candidato y decisión separados es útil; trasladar la guarda como certificado de alineación queda contradicho por los controles.

**Qué aporta el recorrido de todo el archivo — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Los eventos que comienzan después de 60 s están fuera de la observación de v3; no están necesariamente fuera del material leído por B o D. La ventana móvil de C permite alcanzar parte de esa región, no toda la cola. La longitud por sí sola no es una explicación: v3 sí recuperó los retardos del barrido A de 70 s cuando las marcas estaban dentro del prefijo. Ver las ventanas por índice (`tM`, `tG`, `frames_M/G`) en las filas F de la matriz.

**Información estéreo — EXPERIMENTAL_RESULT · CONFIRMADO.** En B/`solo_L` frente a `solo_R` se permutaron los tres WAV por columnas; como la referencia es dual, el Mix no cambió. Los relojes sí intercambiaron su lado. Ningún motor cambió el escalar de V. En `B_distintos_4s` la verdad es (−1103,+4410), y los cuatro dan **el mismo resultado respectivo** después del swap: v3 +4410; B/C/D −1103. Que cada método escoja una de las dos cifras no identifica cuál es el canal retrasado; el oráculo sí cambia de columna. Esto no prueba nada nuevo sobre independencia de **máscaras**: aquí no se calcularon.

**Contrastes de composición — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** En V, 4 s, misma verdad (0,+1103): al reducir conjuntamente R/L a 1/4 (`B_nivel_1_4_4s`), v3 publicó d=0 y B/C/D **+60**; al cambiar el espectro de R respecto al control dual (`B_espectros_4s`), B/D publicaron **+572**, C identidad 0 y v3 0. Con sólo la **guía** R muy atenuada (`D_debil_R_4s`), los cuatro publicaron 0 aunque la marca de R seguía +1103. Cuando sólo un canal contiene el rol (`B_evento_L_4s`/`B_evento_R_4s`), el escalar +1103 coincide con el activo; en el otro no hay un reloj V que se pueda acreditar.

**Marcas más portadora — EXPERIMENTAL_RESULT · CONFIRMADO.** Al añadir portadoras a las marcas de `A_d+1103_4s`, manteniendo d=+1103 (`C_tonos_marcas_4s`), v3 retira su candidato, B/D publican **+86703** y C **+1203**. Es un caso identificable por la marca externa; que las tres últimas salidas digan `MISALIGNED` no valida ninguna de esas magnitudes. En las ráfagas aperiódicas `C_aperiodico_4s`, en cambio, los cuatro recuperan −1103. No se extrapola esta pareja de ejemplos a toda señal con ataques.

**HYPOTHESIS · NO CONFIRMADO como corrección.** Tomar de A la separación entre candidato, incertidumbre y actuación, no copiar su prefijo, su signo de lag ni su umbral de AC. No se demostró que un mismo estimador, estado global o calibración sirva para los cuatro motores. V3 permanece intacto.
