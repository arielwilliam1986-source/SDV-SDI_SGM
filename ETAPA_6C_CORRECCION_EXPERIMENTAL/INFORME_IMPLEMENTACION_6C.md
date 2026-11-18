# SDV-SDI / SGM · Informe de implementación experimental 6C

**Decisión para Cris y Will: detenerse en 6C.** Las copias de Hardened, EVO y MQR miden ahora el reloj por canal, sin convertir la falta de evidencia en cero ni alimentar shifts. En las señales de 6B, **cada copia recuperó exactamente 252 de 263 retardos no nulos con marca**. Las once restantes fueron abstenciones, no coincidencias. En la reserva aparecieron tres decisiones injustificadas por motor cuando una fuente estaba presente dos veces en el Mix. El diagnóstico no está validado para autorizar una corrección de audio. **EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.**

## Qué se tocó y cómo se midió

**DOCUMENTED_FACT · CONFIRMADO.** Se recuperaron los cuatro blobs completos en `7092c6cee764861d4bd8230eccb700f1d4d0556c`. Coincidieron bytes y SHA con checkout, 1B, S5, auditoría independiente, E6 y 6B. A/v3 quedó como referencia sin copia experimental ni nueva ejecución. Sólo se cambiaron **tres copias**, en esta carpeta. La versión nominal de B y C sigue siendo la misma; no usarla como identificador.

| Motor | SHA-256 original → SHA-256 experimental (prefijos; hashes completos en los manifiestos) | Cambio que se somete a prueba |
|---|---|---|
| Hardened (B) | `5141fb500565` → `48b423c4a976` | La envolvente propone, no decide. Se verifican alternativas de onda, cero, signo, solape y competencia antes de emitir lag. Ningún lag va a la lectura desplazada. |
| EVO (C) | `003e698e187b` → `27e478751920` | Búsqueda local trasladada al origen correcto, selección de ventanas por canal hasta EOF, eliminación de identidad forzada ante duda o error. |
| MQR (D) | `5990ebe41177` → `9962d4993723` | Ausencia de candidato explícita, sin −2; validación conserva estados críticos, errores y permisos separados. Máscara compartida y cresta nativas intactas. |

[Fuentes](source_hashes.json) · [cierre de las copias antes de la reserva](experimental_hashes.json) · [parches y reproducción](README.md) · [criterios de decisión](TAXONOMIA_ESTADOS.md) · [caso, línea nativa, cambio y efecto para **cada** defecto](TRAZABILIDAD_DEFECTOS.md).

**EXPERIMENTAL_RESULT · CONFIRMADO.** Para cada motor se llamó a su `analyze_alignment` completo dos veces (V e I) por caso: **200 casos físicos de 6B + 1 fallo de lectura separado + 13 casos reservados**. En total 642 contextos, 1284 llamadas, 2568 contrastes de canal. Se verificaron los 338 WAV únicos de 6B y los 51 nuevos de la reserva; ningún hash WAV compartido entre particiones. Los retardos verdaderos proceden del oráculo, no del máximo del detector. No se relanzó el banco de originales: las columnas históricas provienen de los registros sellados de 6B. La separación se probó después en un experimento distinto, con la CLI nativa de cada original y su copia.

## Resultado pareado en los 200 casos físicos de 6B

**EXPERIMENTAL_RESULT · CONFIRMADO.** Unidad: *rol × columna × caso*; 800 filas por motor. De ellas 690 tienen retardo único por marca (427 cero, 263 no cero); 68 admiten varios orígenes y 42 carecen de señal útil. X y reserva **no entran** en estos denominadores. En «antes → después» el valor anterior era común al rol: cotejarlo con dos columnas no lo convierte en dos mediciones originales.

| Medida | Hardened | EVO | MQR |
|---|---:|---:|---:|
| Entero exacto entre las 690 marcas | 571 → **666** | 580 → **642** | 571 → **666** |
| Ceros publicados exactos / 427 (incluye identidades antiguas) | 371 → 414 | 418 → 390 | 371 → 414 |
| No ceros exactos / 263 | 200 → **252** | 162 → **252** | 200 → **252** |
| Falsa alarma: marca cero → `MISALIGNED` / 427 | 47 → **0** | 6 → **0** | 47 → **0** |
| Marca cero → `WARNING` / 427 | 9 → 0 | 3 → 0 | 9 → 0 |
| Severo (>441) aprobado `ALIGNED`/identidad / 209 | 9 → **0** | 72 → **0** | 9 → **0** |
| Severo sin `MISALIGNED`, **incluye abstenciones** / 209 | 12 → **11** | 77 → **11** | 12 → **11** |
| Marcas sin estimación / 690 | 0 → **24** | 0 → **48** | 0 → **24** |

**EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** En los retardos identificables donde las copias dieron un número, el error máximo fue 0 muestras. **No** es «error cero en todo el banco»: faltan las marcas de la última fila. Hubo ganancias y pérdidas reales de cobertura. En B/D, 107 contrastes que no eran exactos pasaron a exactos y **12 que antes daban el número exacto** quedaron sin decisión; en C fueron 101 y **39**. El número anterior podía ser identidad no sustentada. En la guía vocal severa de B/D *aumentaron* los casos sin alarma firme (6 → 11 de 203), aun eliminando todas las aprobaciones severas erróneas. Los 12 no ceros que ahora reciben `ALIGNED` en cada motor son los **±1 medidos correctamente**, dentro de la política nativa; ninguno se sustituyó por cero. [Detalle por rol y lista de fallos](RESULTADOS_REGRESION.json).

**EXPERIMENTAL_RESULT · CONFIRMADO.** En V del grupo A, se recuperaron **100/100** contrastes no nulos de barrido y fronteras por motor; los signos + y − se ensayaron realmente. Para |d|=1, 221, 441, 1103 y 22050 hubo 12 contrastes por magnitud (tres duraciones, dos signos, dos canales); para 442 hubo cuatro en 4 s. ±441 dio `WARNING`, ±442 `MISALIGNED`. V=Mix: 6/6 ceros medidos; no se infirió que una guía parcial tuviera que ser idéntica al Mix. En el banco completo se recuperaron **164/175 positivos y 88/88 negativos**; la distribución del banco no es simétrica. En F, 60/60 contrastes V exactos incluyendo interior, cola y material posterior a 60 s. En V débil a 10⁻⁷, aperiódica, lateral exacta y casi lateral: 6/6 por familia y motor. Atenuación de una señal limpia no es ruido añadido.

## Qué demuestran los testigos, y qué no

- **EXPERIMENTAL_RESULT · CONFIRMADO.** En `F_interior_-22050_30s`, EVO conserva `tG=661500`, `tM=595350`, `h=66150`. Ahora solicita `q∈[0,132300]`, encuentra `q=88200`, traduce a `k=+22050` y comunica `d=−22050` en los dos canales. En 6B el q necesario quedaba fuera y acababa en identidad. El espejo +22050 y la cola de 70 s también se midieron.
- **EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** En `C_tonos_marcas_4s` I/L, B recupera cero cuando la propuesta principal de envolvente sigue en +23984 muestras. En `C_archivo_S2_4s` I, la antigua cifra −1212 deja paso a `AMBIGUOUS`. En `C_archivo_S5_4s` I, retirar el antiguo −6436 no basta para identificar el cero verdadero: hay competidores de onda casi iguales. Las tres copias distinguieron los **68/68 ambiguos** del oráculo 6B y los **42/42 sin señal**, no todos los materiales *con* marcas.
- **EXPERIMENTAL_RESULT · CONFIRMADO.** `B_solo_L_4s` y su swap dan (1103,0) y (0,1103); el d común es nulo y `dR−dL` cambia de signo. En los **27 roles físicos** con dos marcas distintas, B/D midieron 27 diferencias exactas; C midió 26 y se abstuvo en un canal del restante. Ningún motor publicó un lag común para esos 27. Antifase exacta no es silencio L/R; en inversión global `E_invertida_1103_4s`, L/R dan +1103 con Pearson negativo, no 0/ID. [Informes estéreo](RESULTADOS_ESTEREO.json).
- **EXPERIMENTAL_RESULT · CONFIRMADO.** En X la lectura de V da `ERROR` en las tres copias e I puede medirse aparte; no se llama «completo» al contexto. En D, de los 201 resúmenes aislados de 6B (X incluido), 34 son `pass`, 18 `pass_with_warnings` y 149 `fail`; **ningún veto dio `pass`**. No confundir estas cifras con separación ni con 149 falsas alarmas. El T6 mono de D conservó ambos signos: k=−1500/+800.

### Prueba reservada: dónde falla la generalización

**EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** De las 52 filas por motor, 35 tienen marca única: B y D midieron **35/35**, C **33/35**. C se abstuvo en +72011/−72011, fuera del dominio nativo; no publicó cero. Las nueve filas sin soporte tuvieron el rechazo esperado. De ocho filas que exigían ambigüedad, **cinco se reconocieron y tres no** en cada motor. En `R_dos_origenes` V/L se aceptó cero pese a un segundo origen; en `R_replica_dominante` V/L y V/R se aceptó −3217. Son fallos de atribución temporal en una composición deliberadamente multiorigen, no FP medidos sobre una marca única de cero. Las cuatro columnas del caso circular de período 719 sí fueron ambiguas. Resultado total conforme al criterio predefinido: **49/52 B, 47/52 C, 49/52 D**. No hubo reajuste posterior. [Recetas y oráculo](evidence/reserva_manifest.json) · [límites y contraejemplos](LIMITACIONES_UNKNOWN.md).

## No regresión **medida** en separación sintética

**EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Se comparó cada original contra **su propia copia**, mismos WAV custodiados S5, manifiesto, flags y partición por chunks. Sin `--correct-alignment`, con `--allow-misaligned` explícito para que un veto diagnóstico no impidiera medir el camino de audio. De 15 pares de ejecuciones, **14 completaron ambos lados** (B: 5; C: 6; D: 3). D/S7 abortó en ambos; no se computó como «idéntico». La sonda CPython leyó arrays reales en `stft_span_frames`, `CandidateMetrics.update_freq` y `read_span`; no sustituyó ninguna función.

| Observación | Resultado en las 14 comparaciones completas |
|---|---|
| Máscaras V/I **aplicadas**, consensos y espectros de candidatos | 840 contrastes de tensor con forma, dtype y SHA; 564 de ellos además comparados elemento a elemento (entradas STFT, máscaras, consensos), máximo absoluto **0**. No se confundió el `.npy` promediado de disco con la máscara aplicada. |
| Fórmulas y residuales | Error observado **0** para `Mv+Mi=1`, `SDV=X·Mv` y `SDI=X·Mi`. B y C ejecutaron además `mono + --use-residuals`: por par de runs, 12 entradas de guía residual por versión y motor, mismas ganancias y spans y mismo resultado. D no tiene ese flag. |
| PCM, relación L/R y polaridad | **28 comparaciones de WAV** (14 SDV, 14 SDI): 0 muestras distintas en L o R, 176400 frames, 4 s, 44100 Hz, estéreo FLOAT. Sin recorte, reordenar canales, desplazar ni invertir en la comparación. En S3 se conserva R/L≈0.25. En `C/Pneg/hybrid_asymmetric` se observan signos nativos −1 y +1 en ambas versiones; error `span−signo·lectura=0`. |
| Suma releída y acción | Diferencia del residual `Mix−SDV−SDI` entre versiones = **0** en los dos canales; el residual frente a Mix no es exactamente cero en todos los archivos (máximo observado ≈7.45e−9). Todas las lecturas comparadas tuvieron shift 0. |
| Diferencias que **sí** existen | En los WAV FLOAT cambió el timestamp que libsndfile escribe en el chunk RIFF `PEAK`: hash de ese chunk **sin los 4 bytes de fecha** idéntico; `fmt `, `fact` y `data` idénticos. En los `analysis.json`, cambian los registros de alineación, `validation_status` de D y metadatos de ejecución (`engine_sha256`, UTC, duración o descripción D5 según motor). Las rutas JSON exactas se enumeran por par; no se atribuye igualdad binaria a los informes. |

[Comparaciones y diferencias por ejecución](RESULTADOS_NO_REGRESION.json) · [datos primarios de la sonda y consola](evidence/no_regresion.jsonl.gz). **No** se evaluó calidad perceptual. Las copias no cambian STFT/iSTFT, máscaras, polaridad de procesamiento, política de residual ni `mask_mode`. La medición sólo alcanza las rutas ejercitadas: `per_channel` y `mono` de B/C, `magnitudes_first`, `masks_first`, híbrido de C, y cálculo compartido de D.

## Diez respuestas de cierre

1. **Corregidos realmente — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Salida extrema o identidad sin soporte, −2 de MQR, rango asimétrico y omisión de cola de EVO, pérdida de relojes L/R, confusión de signo de onda con tiempo y aprobación por omisión de MQR. Se quitó el monopolio del pico de envolvente; no se resolvió la atribución universal de fuente.
2. **Persisten — EXPERIMENTAL_RESULT · CONFIRMADO.** Abstenciones sobre marcas periódicas/compuestas, veto de segunda ventana de C y cresta posterior D/S7. A1/A2 de v3 quedan fuera, sin parche.
3. **Nuevos fallos — EXPERIMENTAL_RESULT · CONFIRMADO.** Tres decisiones injustificadas de ocho exigencias de ambigüedad por copia en reserva; dos retardos adicionales sin resolver en C por límite de rango. También se informan las marcas de 6B antes numéricamente exactas que ahora se pierden.
4. **Recuperación — EXPERIMENTAL_RESULT · CONFIRMADO.** 252/263 retardos no nulos por copia en 6B; 100/100 del barrido y fronteras V. En reserva: 20/20 no ceros B/D, 18/20 C.
5. **FP — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** 0/427 ceros marcados → MIS en cada copia, frente a 47/6/47 B/C/D. No extrapolar ese cero a mezclas de dos orígenes.
6. **FN — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Ninguno de 209 severos se aprobó como alineado; 11/209 no produjeron la alarma firme esperada por canal (abstenciones). Medir sólo aprobaciones ocultaría esos once.
7. **L/R — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Se estiman por separado y se conserva su diferencia cuando ambas son medibles. No hay lag común si discrepan o falta una. Un signo de polaridad contrario no anula por sí solo un reloj válido.
8. **Máscaras y fórmulas — DOCUMENTED_FACT · CONFIRMADO; contraste físico: EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** Sin cambios de fórmula ni de parámetros; sin diferencias de arrays en los caminos comparados.
9. **Alcance de no regresión — EXPERIMENTAL_RESULT · CONFIRMADO CON LIMITACIONES.** 14 pares sintéticos completos y sin shift, no toda combinación CLI, no el par D/S7 incompleto y no música real. No se deduce conservación futura en otros datos o versiones.
10. **Antes de 6D — UNKNOWN · UNKNOWN fuera del banco.** Hace falta revisión independiente de ChatGPT (Cris): aplicar los tres diffs sobre las fuentes selladas, reproducir cifras y contraejemplos, revisar cobertura vs falsas decisiones y verificar DSP/PCM. Will debe autorizar expresamente cualquier nueva etapa. **No iniciar 6D, no seleccionar ganador, no integrar en `main`.**

**QA — EXPERIMENTAL_RESULT · CONFIRMADO.** Diffs reaplicados byte a byte; compilación; seis pruebas automatizadas y siete pruebas del self-test MQR pasaron. En detección: 0 excursiones a DSP/downmix, 0 excepciones no controladas, 0 avisos Python, 3 errores de lectura provocados y conservados. En un directorio nuevo se regeneraron el paquete reservado y su manifiesto idénticos, y se reprodujeron byte a byte la matriz, los dos índices de regresión/estéreo, el log de incidencias y el control de calidad a partir de los registros primarios. [Control de calidad](evidence/control_calidad.json) · [errores/avisos](ERRORES_Y_EXCEPCIONES.log) · [SHA256SUMS](SHA256SUMS.txt).
