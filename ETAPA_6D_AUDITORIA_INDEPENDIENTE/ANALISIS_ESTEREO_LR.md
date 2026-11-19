# C · Independencia L/R del reloj, no de la separación

**EXPERIMENTAL_RESULT · CONFIRMADO en las entradas ensayadas.** Cambiar sólo R del WAV guía de `Z` (incluido un NaN en R) dejó **idéntico el registro completo de L**: ventanas, candidatos, signos, solapes, confianza y decisión. R pasó a ERROR y el rol a ERROR sin k. Al intercambiar físicamente ambos canales en `distintos↔swap` y `soloL↔soloR`, las decisiones **y las ventanas enteras** se intercambiaron. Los originales en cambio publicaban el mismo escalar de rol al intercambiar columnas. Esto prueba más que dos campos L/R rellenos desde un único pico Mid. [Contraprueba](evidence/extra_raw.json.gz) · [aserciones](tests/test_expediente.py).

Los valores son `d` en muestras a 44.1 kHz; Δ es **dR−dL**, no kR−kL. Acordar un estado severo no implica acordar un reloj común. Las tres copias dieron la misma respuesta en esta tabla de controles:

| Caso, rol | dL | dR | Δ | Clase de rol, k publicado | Qué discrimina |
|---|---:|---:|---:|---|---|
| `distintos`, V | +1361 | −587 | −1948 | MISALIGNED, — | Relojes independientes, no el promedio. |
| `distintos`, I | −811 | +331 | +1142 | MISALIGNED, — | La alarma de L no oculta el WARNING de R en el desglose. |
| `swap`, V / I | −587 / +331 | +1361 / −811 | +1948 / −1142 | MISALIGNED, — en ambos roles | Cambia el signo de Δ; los dos roles son diferentes. |
| `corta`, V | +821 | −903 | −1724 | MISALIGNED, — | Guía **válida** 11 983 frames más corta que Mix, no un contenedor truncado. |
| `interior_vacio`, V | −18013 | +18103 | +36116 | MISALIGNED, — | 36 s con paquetes tempranos/tardíos, silencio interior y en bordes. |
| `larga`, V | −825 | −825 | 0 | MISALIGNED, +825 | Guía válida 7231 frames más larga: diferencia de duración no es el retardo. |
| `soloL` / `soloR`, V | 0 / — | — / 0 | — | INSUFFICIENT_SIGNAL, — | Una columna no puede suplir a la muda. |
| `alarma_mudo`, V | +937 | — | — | MISALIGNED, — | Se conserva alarma L **y** R insuficiente en JSON/consola. |
| `invalida_L`, V | — (ERROR) | 0 | — | ERROR, — | Se retiene la medición de R pero no autoriza el rol. |
| Control `opposite_warnings`, V | +219 | −219 | −438 | AMBIGUOUS, — | Dos WARNING incompatibles no se convierten en un cero ALIGNED. Veto real sin permiso. |
| `lateral`, V | −1933 | −1933 | 0 | MISALIGNED, +1933 | L=−R, Mid exactamente nulo, ambos canales sí son informativos. |
| `invL`, V | −827 | −827 | 0 | MISALIGNED, +827 | ρL=−.772778, ρR=+.611186; aceptan el mismo **tiempo**, ρ común nulo. No se aplicó shift. |

**EXPERIMENTAL_RESULT · CONFIRMADO.** En el banco reservado hay seis roles con marcas L/R numéricas desiguales por copia; en los seis, Δ es exacto y el k común es nulo. En `C_tonos_marcas_4s` V histórico hay un L severo y un R AMBIGUOUS, no una estimación común. En los registros nativos de toda la prueba, un k común requirió kL y kR enteros presentes e iguales; los no medidos no publicaron ni ρ ni confianza de decisión. El CSV conserva por separado `k_mejor_por_ventana`, `k_publicado` de canal y `k_comun` de rol. [Matriz](MATRIZ_RESULTADOS_6D.csv).

**EXPERIMENTAL_RESULT · PARCIALMENTE CONFIRMADO (evidencia física).** En `rival_R` la segunda copia existe **sólo en R** (amplitud .38). Para L el cero está identificado. En R los rivales dan ρ(0)=.63366 y ρ(−2849)=.24039. El detector de R acepta el primero, ambos canales anuncian cero y sale ALIGNED. No se impuso un valor de L al cálculo de R: **R clasificó mal su propia evidencia**. El resultado global oculta la ambigüedad física aunque conserve perfectamente los registros nativos. En un registro manipulado fuera del flujo normal el agregador D tampoco garantiza presencia de ambos canales; [véase el alcance exacto](AUDITORIA_CLI.md).

**EXPERIMENTAL_RESULT · CONFIRMADO, no una curva de sensibilidad universal.** `debil` atenúa la guía V a 3×10⁻⁷ (misma forma): d=+763 en L/R. `ruido8` y `ruido_menos6` añaden **ruido al Mix** a +8 y −6 dB respecto a la vocal: d=−1541 y +367 respectivamente; a −6 dB ρ≈.424/.402. `sin_relacion` (otro código) y `dc` no producen número vocal. La verdad procede de los componentes archivados y las marcas, no de que ρ supere un corte. No se dedujo un SNR límite.

**DOCUMENTED_FACT · CONFIRMADO.** La inspección e intercambio de columnas conciernen al *detector*. MQR sigue teniendo máscara compartida; en B/C `mask_mode` y la inversión LS preexistente de EVO pertenecen al DSP. Ni una discrepancia de reloj es una regresión de máscara, ni la igualdad de máscaras prueba que la atribución sea correcta. [Comparación física](NO_REGRESION_6D.md).