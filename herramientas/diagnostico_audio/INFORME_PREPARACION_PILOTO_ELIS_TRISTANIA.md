# INFORME DE PREPARACIÓN — PILOTO MUSICAL ELIS / TRISTANIA

> **RECTIFICADO 2026-11-21**: leer junto con `INFORME_RECTIFICACION_PILOTO_ELIS_TRISTANIA.md` (mismo directorio). Correcciones principales: (1) la Etapa 6G.1 **sí existe** en la rama `arena/89d5c189-sdv-sdi-sgm`; (2) C5-A/C5-C **aceptados por Cris** — C5 concluida, C1/C4-A/C4-B cerrados y congelados, pendiente solo la validación Android/Termux; (3) S5 sintético ya ejecutado y auditado; la batería `per_channel` (P1–P6) pendiente usa fixtures sintéticos y **no requiere las canciones**; (4) material designado oficialmente: Elis — Die Stadt y Tristania — Lethean River (rutas en §4 de la rectificación, **sin hash ni inspección**); (5) matriz de los 10 defectos de Fase 1B clasificada por defecto. Las secciones de este documento que contradigan la rectificación quedan sustituidas por ella.

**Modalidad**: inspección estática y diagnóstico de solo lectura. **No se ejecutó DSP, no se procesaron canciones, no se abrieron ni copiaron muestras musicales (no existen muestras de audio en el repositorio), no se modificó código.**

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm` — HEAD de referencia: `9b3608d` (`9b3608d5a09a80e313d320552ffa9f8b4a3149fe`, verificado local = remoto)
- **Responsable técnico**: Cris · **Decisor final**: Will
- **Estado**: PROVISIONAL — pendiente de auditoría de Cris y decisión de Will
- **Clasificación de evidencia**: se usa la taxonomía del propio proyecto (DOCUMENTED_FACT / EXPERIMENTAL_RESULT / THEORETICAL_DEDUCTION / HYPOTHESIS / UNKNOWN). Una inspección de código no equivale a una prueba dinámica.

---

## 1. Estado real de cada requisito de la instrucción

### A. Estado de la "Etapa 6G.1" y sus hallazgos pendientes

**DOCUMENTED_FACT**: el término "6G.1" (y cualquier variante "6G") **no aparece en ninguno de los 124 archivos seguidos por git** en esta rama (`git grep -i "6G"` → 0 resultados). No existe en el repositorio ningún documento, informe o registro con esa denominación.

**UNKNOWN (requiere confirmación de Cris/Will)**: la numeración "6G.1" corresponde presumiblemente a la contabilidad interna de las conversaciones externas (ChatGPT) que no fue volcada al repositorio. Lo más cercano estructuralmente en el repositorio es:

- El **documento de transferencia técnica** (`Proyecto SDV-SDI_SGM — Estado y continuidad.txt`, fecha de referencia 2026-11-18), que contiene el inventario de hallazgos pendientes del proyecto: **10 defectos enumerados**, la tabla de estado de pruebas críticas y las 7 prioridades ordenadas (§6 y §8 del documento).
- El **informe de la Fase sintética 1B** (`SDV-SDI_FASE_1B_ENTREGA/REPORT.md`), con los resultados medidos de consensos, alineación, `mix_delta`/SDI_F2 y orquestador.

**Acción solicitada**: confirmar el mapeo entre "Etapa 6G.1" y los hallazgos del documento de transferencia (o aportar el documento 6G.1 original) antes de que el piloto dependa de él. Mientras ese mapeo no exista, este informe toma como lista autoritativa de hallazgos pendientes la del documento de transferencia.

### B. Estado actual de AudioInput v0.2.12 y limitaciones conocidas

Identidad (DOCUMENTED_FACT, commit `7afdff3` — corrección documental final):

| Item | Valor |
|---|---|
| Instrumento | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| Versión | `SCRIPT_VERSION = "0.2.12"` |
| Blob / SHA-256 | `9abecd18770236e7e5c269ba0e4336f98bdafc27` / `de69863bafb2a7cb17540b15c59bc41d3165730246983ceeb22fd0a2987060b6` |
| Tamaño / líneas | 155.558 B / 3.181 L |
| HEAD de la rama | `9b3608d` (informe documental) |

Estado de las subfases (DOCUMENTED_FACT, informes en el repositorio):

| Subfase | Estado |
|---|---|
| C1, C2, C3, C4-A (hasta cierre v0.2.7) | Auditadas y cerradas (INFORME_CIERRE_C4_A, `edc10b0`) |
| C4-A v0.2.8, C4-B v0.2.9/v0.2.10, C5 v0.2.11/v0.2.12 | **Entregadas y provisionales — pendientes de auditoría independiente de Cris** |
| Zonas congeladas vigentes | C1, C4-A (`OwnedFdResource`, `_ResourceSnapshot`, tokens), C4-B (acumulador persistente), C5 (interrupciones), `sha256_pread_v2`, SoundFile `closefd=False`, T11–T16 |

Limitaciones conocidas y documentadas (resumen de los informes v0.2.9–v0.2.12; lista completa en §10 del INFORME_CORRECCION_C5_v0_2_12):

1. **Alcance de lectura**: el instrumento **solo abre fixtures sintéticos que él mismo crea** en su directorio de ejecución exclusivo (`run-<run_id>`). **No tiene ningún modo para abrir o verificar archivos de música existentes del usuario.** Sus notas JSON lo documentan: "Crea exclusivamente fixtures sintéticos en directorios de ejecución exclusivos", "NO modifica archivos originales del usuario".
2. `EXPECTED_LIMITATION` documentada (no es protección): la reutilización del mismo número de fd para el mismo archivo tras un cierre externo no es detectable por `(st_dev, st_ino)`.
3. Errores de cierre posteriores a la publicación del informe: visibles en salida de diagnóstico y acumulador, no insertados en el JSON ya publicado.
4. `_close_err_id` es identificador por ejecución (no global).
5. C5-C: estado de publicación `INDETERMINADO` cuando el provisional desapareció sin evidencia de identidad (comportamiento correcto pero conservador).
6. Una sola ruta de reconstrucción del informe por ejecución (v0.2.5, congelado); KI durante la reconstrucción ⇒ limitación explícita + exit 130.
7. Propósito de diseño: diagnóstico de lectura de almacenamiento (Android/Termux) con `SoundFile(fd, closefd=False)` + `os.pread` + SHA-256 — **no es un procesador musical ni alimenta a los motores**.

### C. Condiciones que deben cumplirse antes de permitir que AudioInput intervenga en la lectura de material musical real

| # | Condición | Estado | Tipo |
|---|---|---|---|
| C-1 | **Autorización de una extensión "verificación de archivo existente"** (modo de solo lectura que aplique `sha256_pread_v2` + `SoundFile(fd, closefd=False)` + metadatos a archivos reales aportados, sin crear fixtures ni modificar nada) | **No existe**; requiere nueva subfase autorizada y diseño que respete las zonas congeladas | Bloqueante para cualquier uso directo |
| C-2 | Cierre de las auditorías provisionales v0.2.8–v0.2.12 por Cris | **Pendiente** | Bloqueante (gobernanza) |
| C-3 | Autorización expresa para ejecutar en Android/Termux si el objetivo es validar el almacenamiento destino (hoy prohibido en las instrucciones de sesión) | **Pendiente** | Bloqueante para ese entorno; no lo es para verificación en escritorio |
| C-4 | Material conforme: WAV/FLAC 44.1 kHz sin pérdida (preferencia documentada del proyecto), pistas seleccionadas, hasheadas y declaradas inmutables; trabajo **sobre copias** en directorios de ejecución exclusivos (nunca sobre originales) | **Pendiente** (las pistas del piloto no están en el repo ni hasheadas) | Bloqueante para el piloto |
| C-5 | Confirmación de que la lectura real no altera la cadena congelada (C1/C4-A/C4-B/C5): la extensión C-1 debe reutilizar los patrones existentes, no reescribirlos | Verificable en diseño futuro | Condición de diseño |
| C-6 | Guías MVSEP disponibles (Fase 3 externa) para que los motores tengan pares vocal/instrumental | **Pendiente** (servicio externo; límite gratuito 100 MB) | Bloqueante para los motores, no para la verificación de lectura |

**Conclusión parcial**: con el instrumento tal como está, AudioInput **no puede intervenir** en la lectura de las canciones reales; su rol preparatorio hoy es (a) implementación de referencia de los patrones de lectura segura (C1 + C4-A + `sha256_pread_v2`) y (b) candidato a extensión autorizada como verificador pre-vuelo (Fase 0 del protocolo, §5).

### D. Documentación S5 y escenarios sintéticos pendientes de investigación

**DOCUMENTED_FACT**: la documentación S5 existente en el repositorio es **mínima**: el término aparece únicamente en el documento de transferencia (3 menciones). No hay informe dedicado de S5 en el repo.

Definición recuperada (DOCUMENTED_FACT, citas del documento de transferencia):

- "La prueba **S5** de comportamiento **"per_channel"** en motores reales no ha sido completada." (defecto pendiente #10)
- Tabla de estado: "**S5: per_channel real | Pendiente**"
- "**Prioridad 2**: ejecutar S5 con motores reales y canales L/R diferenciados."

Es decir, S5 verifica si los motores reales procesan los canales L/R de forma independiente (requisito directo de la filosofía SGM: "No mezclar canales L/R durante el procesamiento", "No convertir silenciosamente audio estéreo a mono"). **Sigue pendiente** y es el único escenario sintético pendiente con identificador propio.

Escenarios sintéticos adicionales pendientes de investigación (DOCUMENTED_FACT del documento de transferencia + EXPERIMENTAL_RESULT del REPORT.md de Fase 1B):

| Escenario pendiente | Evidencia actual |
|---|---|
| **S5 per_channel real** (L/R diferenciados) | Pendiente (Prioridad 2 del proyecto) |
| **Alineación v3** con retardos independientes L/R | Pendiente; el verificador actual acierta 554/780 (71.0 %) con 10 falsos positivos; dos propuestas **medidas y no aplicadas**, pendientes de validación externa |
| **Consenso predeterminado `magnitudes_first` no-op** en hardened y EVO (max\|Δ\| = 0.0 exacto) | Medido en sintético; investigación de causa pendiente |
| **`mix_delta` / SDI_F2** | **UNKNOWN** según el propio informe |
| **Detección de inversión de polaridad** (los procedimientos actuales no la detectan en algunos casos) | Identificado, sin resolución |
| **Complementariedad algebraica trivial** (no demuestra separación musical) | Documentado; método de evaluación musical pendiente |
| **Compatibilidad de manifiestos** (orquestador ↔ v3) | Inspección realizada; transformación no probada |
| **Inspección completa de registros** (logs) | Pendiente |

### E. Motores y configuraciones candidatos (sin declaración de ganador)

Inventario DOCUMENTED_FACT (cabeceras y CLIs inspeccionadas estáticamente; **sin ejecución**):

| Motor / módulo | Líneas | Rol declarado | Estado documentado |
|---|---|---|---|
| `sdv_sdi_mqr_engine.py` | 3.505 | MQR Engine v1.0.0 — consenso multi-modelo/multi-variante de máscaras TF (spec "Prompt Mask MVSEP.json" v1.3.0, `experimental_calibration`). **Pista de calibración de referencia designada: "Elis - Die Stadt"** (constante interna + `primary_test_track_reference` en el metadato de salida). CLI: `--manifest`, `--mix`, `--mode`, `--out`, `--n-fft`, `--hop`, `--power`, `--epsilon`, `--chunk-frames`, `--consensus`, `--smoothing`. Depende de numpy/scipy/soundfile | Experimental_calibration |
| `MOTOR_SEP_SDV-SDI.py` | 1.939 | Motor Maestro v3.1.0 (rama base) | Auditado sintéticamente |
| `MOTOR_SEP_SDV-SDI_v3.py` | 2.278 | Motor de consenso v3.0.0 "Consensus-Complete": SDV/SDI a partir de mix + K pares de guías por residuo, consenso en dominio complejo | Con defecto de alineación (downmix mono) pendiente |
| `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | 1.951 | Variante hardened de v3.1.0 | Consenso predeterminado no-op en sintético |
| `MOTOR_SEP_SDV-SDI_EVO.py` | 2.114 | Variante EVO | Consenso predeterminado no-op en sintético |
| `orquestador_maestro.py` | 75 | Orquestador "Fórmula Will": resuelve archivos de la carpeta de la canción (`--dir`, `--mix`) | Con incompatibilidad de manifiesto pendiente |
| `mix_delta.py` | 402 | Inyección del Delta Vocal al SDV (rama normal; interpretación corregida AUDIT_014 v2) | SDI_F2 = UNKNOWN |
| `preflight_audit.py` | 108 | Pre-vuelo: carga, detección de guías duplicadas (< −90 dB) | Utilitario de apoyo |
| `orchestrator_spec/` (FASE_1B) | — | Arquitectura experimental del orquestador (perfil, inventario, validador) | Experimental |

Configuraciones relevantes para el piloto (DOCUMENTED_FACT):

- `configs/perfiles_orquestador.json` (schema `orchestrator_profile/1`): extensiones `[".wav"]`; patrones de mix `^Mix(_|\.)` / `^Mix$`; resolución con `empate_prioridad: AMBIGUOUS`, `primer_match: false`, `no_truncar: true`, `no_resamplear: true` (coherente con las restricciones del proyecto); perfil `mvsep_simple` con roles INSTRUMENTAL/VOCALS por regex (`parN_<modelo>_vocals_full.wav` / `parN_<modelo>_instrum_only.wav`, convención de `MANIFEST_SEP_SDV-SDI.json`).
- `MANIFEST_SEP_SDV-SDI.json`: `guide_pairs` estructurados (`pair_id`, `family`, `variant`, `configuration`, `vocal_guide`, `instrumental_guide`, `source_service: MVSEP`) — el formato de entrada de guías que el piloto debe producir en Fase 3.

**No se declara ganador ni preferencia.** La selección de motor ganador está explícitamente prohibida sin pruebas con material musical real y evaluación auditiva (restricción #9 del proyecto).

---

## 2. Defectos pendientes que bloquean el piloto

De los 10 defectos del documento de transferencia, estos **bloquean o comprometen directamente** el piloto Elis/Tristania (orden de gravedad para el piloto):

| # | Defecto | Impacto en el piloto |
|---|---|---|
| 10 | **S5 per_channel real pendiente** | El comportamiento L/R de los motores con señales reales es UNKNOWN: cualquier resultado estéreo del piloto sería incomparable entre motores y posiblemente inválido |
| 7 | **Alineación v3 con downmix mono** (sin retardos L/R independientes) | Un piloto con música real mediría alineación con un verificador que acierta el 71 % y oculta diferencias L/R — directamente contrario al objetivo de integridad estéreo |
| 4 | **Inversión de polaridad no detectada** por algunos procedimientos | Daño silencioso potencialmente no detectado por las verificaciones del piloto |
| 1 | **`estricto_subtype` no propagado** en determinadas rutas | Las canciones reales pueden ser FLAC/WAV con subtipos variados; riesgo de manejo de formato incorrecto silencioso |
| 2 | **Archivos C corruptos → excepciones no controladas** | Una guía corrupta abortaría la corrida sin diagnóstico controlado |
| 3 | **Residuos pueden fallar con audio mono** | Stems de MVSEP ocasionalmente mono (p. ej. canales centrales) romperían el procesamiento de residuos |
| 4b | **`out_dir=None`** produce errores | Riesgo operativo de configuración |
| 5 | **No verificado impedir guardar resultados dentro del árbol de entrada** | Riesgo de contaminar el directorio de la canción (efectivamente "modificar originales") |
| 6 | **Estado global ACCEPT con grupos SIN_PERFIL** | El piloto podría aceptar resultados generados con perfil ausente (inválidos presentados como válidos) |
| 8 | **Manifiesto orquestador ≠ esquema v3** | Impide encadenar orquestador → v3 sin pegamento manual; transformación no probada |

Bloqueos adicionales fuera de esa lista: auditorías provisionales v0.2.8–v0.2.12 sin cerrar (gobernanza), extensión de AudioInput para archivos reales sin autorizar (C-1), pistas no seleccionadas/hasheadas (C-4), guías MVSEP no producidas (C-6), pista de Tristania sin designar (solo Elis - Die Stadt aparece designada como referencia de calibración en el motor MQR).

---

## 3. Requisitos ya cerrados que NO deben reabrirse

1. **C1** (apertura/creación anclada, publicación atómica sin sobrescritura, no-overwrite) — cerrado y congelado desde v0.2.4; verificado íntegro en v0.2.9–v0.2.12.
2. **C4-A** (`OwnedFdResource`, `_ResourceSnapshot`, tokens, propiedad, estados, `closefd=False`) — cerrado en v0.2.7 (INFORME_CIERRE_C4_A) + encapsulación v0.2.8; congelado.
3. **C4-B** (propagación completa de errores de cierre: acumulador persistente, ids, atribución) — cerrado v0.2.9/v0.2.10; congelado.
4. **C5** (interrupciones: clasificación ERROR/NOT_EXECUTED, segundo entorno, reconciliación idempotente, estado de publicación por identidad, código 130) — cerrado v0.2.11/v0.2.12; congelado salvo las correcciones ya autorizadas y aplicadas.
5. **`sha256_pread_v2()`** y sus clasificaciones — congelado.
6. **Criterios funcionales T11–T16** del AudioInput — congelados.
7. **Definiciones matemáticas SDV/SDI y de Reverb Removal** (documento de transferencia §3) — acordadas; no reabrir sin evidencia.
8. **Restricciones técnicas y filosofía** (§4 del documento de transferencia, 12 reglas) — vigentes; el piloto debe cumplirlas, no renegociarlas.
9. **Campañas sintéticas ya ejecutadas** (Fase 1B: consensos K=2/K=3, alineación medida, complementariedad, coherencia) — NO repetir; sus resultados son la línea base.
10. **Auditoría estática de cierre de AudioInput v0.2.1** — completada; es el punto de partida histórico, no requiere reejecución.

---

## 4. Riesgos de procesar las dos canciones en el estado actual

1. **Resultados estéreo no comparables** (S5 pendiente + defecto de alineación L/R): cualquier diferencial entre motores en "integridad espacial" sería atribuible al verificador tanto como a los motores. Riesgo de conclusión espuria — el tipo exacto de error que el piloto quiere evitar ("sin confundir resultados sintéticos con resultados perceptuales").
2. **Daño silencioso no detectado**: polaridad no verificable de forma fiable + consenso predeterminado que no cambia ni una muestra (hardened/EVO) → un motor podría "procesar" y devolver copias sin cambios o alteradas sin que las verificaciones actuales lo distingan.
3. **Riesgo a los originales**: sin el cierre del defecto 5 (resultados dentro del árbol de entrada) y con `out_dir=None` defectuoso, una corrida mal configurada podría escribir en el directorio de la canción. Mitigación obligatoria: copias + directorios de salida explícitos + hashes antes/después de los originales.
4. **Formatos reales no ejercitados**: los escenarios sintéticos usaron WAV; las canciones reales (y sus stems de MVSEP) traen subtipos y tasas variadas → defecto 1 (`estricto_subtype`) y 3 (mono) tienen probabilidad real de dispararse.
5. **Cadena de guías externa**: MVSEP (servicio externo, límite 100 MB gratuito) es un paso no automatizado y no reproducible dentro del repo; la procedencia de cada guía debe registrarse (hash + parámetros) o el piloto no será reproducible.
6. **Gobernanza**: ejecutar el piloto antes de cerrar las auditorías pendientes (Fase 1B y AudioInput v0.2.8–v0.2.12) violaría el propio protocolo del proyecto ("No modificar los motores originales antes de completar la auditoría"; las correcciones que el piloto revelaría quedarían congeladas).
7. **Sesgo perceptual**: sin protocolo de escucha ciega y rúbrica (naturalidad tímbrica, dinámica, integridad estéreo, intimidad vocal), la evaluación auditiva de Will sería informal y no comparable entre pistas.
8. **Sin ganador conocido**: el piloto es exploratorio/descriptivo; cualquier ranking sería HYPOTHESIS, no DOCUMENTED_FACT.

---

## 5. Propuesta de protocolo para el piloto Elis/Tristania

**Principio**: el piloto solo se ejecuta cuando los bloqueos de §2 estén cerrados o excluidos explícitamente por decisión de Will/Cris. Cada fase produce evidencia hasheada y clasificada.

**F0 — Fijación de material (sin DSP)**
1. Will designa las dos pistas: la de **Elis** (el propio motor MQR designa "Elis - Die Stadt" como pista de calibración de referencia — candidato natural) y la de **Tristania** (sin candidata documentada; decisión de Will).
2. Formato: WAV o FLAC 44.1 kHz (sin pérdida); se registran SHA-256, tamaño, duración, canales, subtype; los originales se declaran **inmutables** y se trabaja sobre copias en un directorio exclusivo del piloto.

**F1 — Verificación de lectura (solo lectura)**
1. Pre-vuelo con `preflight_audit.py` (duplicados de guías < −90 dB) y verificación de metadatos con soundfile (canales = 2, sr, subtype).
2. **Opcional recomendado**: extensión autorizada de AudioInput (condición C-1) para verificar cada archivo con `sha256_pread_v2` + `SoundFile(fd, closefd=False)` — el patrón de lectura del proyecto — sin ejecutar en Android/Termux salvo autorización expresa.

**F2 — Guías (Fase 3 externa, fuera de este repo)**
1. Generar los stems con los modelos MVSEP acordados (BS-Roformer, Mel-Band Roformer, y candidatos experimentales si Will lo decide); límite 100 MB.
2. Empaquetar como `guide_pairs` conforme a `MANIFEST_SEP_SDV-SDI.json` (`parN_<modelo>_vocals_full.wav` / `parN_<modelo>_instrum_only.wav`); registrar hashes y proveniencia de cada par.

**F3 — Ejecución por motor (aislada, sin correcciones)**
1. Un directorio de ejecución exclusivo por motor × pista; configuraciones fijadas por escrito antes de correr (CLI del MQR: mode/consensus/n-fft/hop/power/epsilon/chunk-frames/smoothing; perfiles del orquestador con resolución AMBIGUOUS/no_truncar/no_resamplear).
2. Mismas entradas (mix + guías idénticas) para todos los motores; capturar stdout, manifiestos de salida y SHA-256 de cada SDV/SDI producido.
3. Regla dura: **ningún defecto se corrige durante el piloto**; se registra en la matriz de defectos (identificador, evidencia, gravedad).

**F4 — Verificación objetiva (antes de cualquier escucha)**
1. Identidad de tasa/duración/canales de cada salida vs mix; ausencia de downmix mono (comparación L/R estructural); niveles vs guías (sin ganancia impuesta); verificación de polaridad con el método más robusto disponible (reconociendo su debilidad documentada).
2. Residuo algebraico SDV+SDI−Mix (etiquetado: **no demuestra separación musical**; solo integridad del procesamiento).
3. Todo resultado etiquetado EXPERIMENTAL_RESULT con hashes.

**F5 — Evaluación auditiva (Will)**
1. Escucha ciega por motor/pista con rúbrica SGM: naturalidad tímbrica, dinámica original, integridad estéreo, información espacial, intimidad vocal, ausencia de degradación.
2. Resultados perceptuales etiquetados como evaluación auditiva (no como métrica objetiva).

**F6 — Informe del piloto**
1. Matriz motor × pista × verificación × escucha; clasificación por evidencia; **sin declaración de ganador** (solo hipótesis para el siguiente piloto); actualización de la matriz de defectos; recomendación de siguiente paso.

---

## 6. Motores y configuraciones candidatos (repetido como lista operativa, sin selección)

- **Candidatos a consenso SDV/SDI (Motor 1)**: `MOTOR_SEP_SDV-SDI_v3.py` (Consensus-Complete, 4 métodos propios), `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py`, `MOTOR_SEP_SDV-SDI_EVO.py`, `MOTOR_SEP_SDV-SDI.py` (v3.1.0 base), `sdv_sdi_mqr_engine.py` (experimental_calibration; consenso multi-modelo TF; pista de calibración Elis - Die Stadt).
- **Configuraciones a fijar por escrito**: para el MQR: `--mode` (de `REQUIRED_MODES`), `--consensus` (de `CONSENSUS_METHODS` — documentado que `magnitudes_first` es no-op en hardened/EVO, por lo que el piloto debe usar métodos que lleguen a operación: `masks_first`, `hybrid_asymmetric`, o los de v3), `--n-fft`, `--hop`, `--power`, `--epsilon`, `--chunk-frames`, `--smoothing`.
- **Apoyo**: `orquestador_maestro.py` + `perfiles_orquestador.json` (resolución de archivos, AMBIGUOUS sin primer-match), `preflight_audit.py` (pre-vuelo), `mix_delta.py` (post-proceso del delta vocal, con SDI_F2 en UNKNOWN).
- **Excluidos del piloto por estado**: PolarFormer y SCNet XL IHF son candidatos de MVSEP (Fase 3), no motores locales.

La elección de qué motores entran en la primera tanda corresponde a Will; este informe no recomienda ninguno.

---

## 7. Evidencias y enlaces GitHub (rama `arena/441a4bf8-sdv-sdi-sgm`)

- Documento de transferencia (hallazgos, S5, prioridades, restricciones): [Proyecto SDV-SDI_SGM — Estado y continuidad.txt](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM%20%E2%80%94%20Estado%20y%20continuidad.txt)
- Informe Fase sintética 1B: [SDV-SDI_FASE_1B_ENTREGA/REPORT.md](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/SDV-SDI_FASE_1B_ENTREGA/REPORT.md)
- Perfiles del orquestador: [configs/perfiles_orquestador.json](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/SDV-SDI_FASE_1B_ENTREGA/configs/perfiles_orquestador.json)
- Motor MQR (referencia de calibración Elis - Die Stadt): [sdv_sdi_mqr_engine.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/sdv_sdi_mqr_engine.py)
- Manifiesto de pares de guías: [MANIFEST_SEP_SDV-SDI.json](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/MANIFEST_SEP_SDV-SDI.json)
- Motores: [MOTOR_SEP_SDV-SDI.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/MOTOR_SEP_SDV-SDI.py) · [v3](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/MOTOR_SEP_SDV-SDI_v3.py) · [v3.1.1 Hardened](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py) · [EVO](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/MOTOR_SEP_SDV-SDI_EVO.py) · [orquestador_maestro.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/orquestador_maestro.py) · [mix_delta.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/mix_delta.py) · [preflight_audit.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/preflight_audit.py)
- AudioInput v0.2.12 y sus limitaciones: [audioinput_diag_termux.py](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py) · [INFORME_CORRECCION_C5_v0_2_12.md (§10 limitaciones, §12 corrección documental)](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/INFORME_CORRECCION_C5_v0_2_12.md) · [INFORME_CIERRE_C5_v0_2_11.md](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/INFORME_CIERRE_C5_v0_2_11.md) · [INFORME_CIERRE_C4_A.md](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/etapa2/INFORME_CIERRE_C4_A.md)
- Auditoría estática de cierre v0.2.1: [AUDITORIA_ESTATICA_CIERRE_ETAPA2_V021.md](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/AUDITORIA_ESTATICA_CIERRE_ETAPA2_V021.md)
- HEAD de la rama: [commit `9b3608d`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/9b3608d5a09a80e313d320552ffa9f8b4a3149fe)

---

## 8. Recomendación final

## **NO LISTO** (en el estado actual) para preparar/ejecutar el piloto Elis/Tristania.

Fundamento (en el orden de prioridades que el propio proyecto estableció):

1. **S5 (per_channel real, Prioridad 2 del proyecto) sigue pendiente** — y es exactamente la propiedad (L/R independiente) que el piloto pretende evaluar con música real. Ejecutar el piloto antes convierte sus conclusiones estéreo en no atribuibles.
2. **La batería de alineación v3 (Prioridad 3) está pendiente** — el verificador actual tiene 71 % de acierto y oculta diferencias L/R.
3. **La Fase 1B no está cerrada** (10 defectos pendientes; inspección de módulos/registros incompleta; compatibilidad de manifiestos sin probar) y las reglas del proyecto prohíben corregir motores antes de completar la auditoría.
4. **Las auditorías provisionales de AudioInput v0.2.8–v0.2.12 no están cerradas** y el instrumento no puede leer archivos reales existentes sin una extensión autorizada que aún no existe.
5. **El material del piloto no está fijado** (pista de Tristania sin designar; pistas sin hash; guías MVSEP no producidas).

**Condiciones objetivas para re-evaluación a "LISTO PARA PREPARAR PILOTO"**:

- [ ] S5 ejecutada con motores reales y canales L/R diferenciados (Prioridad 2) y resultados documentados.
- [ ] Batería de alineación v3 ejecutada (Prioridad 3) y verificador con estimación L/R independiente aplicado o descartado con evidencia.
- [ ] Compatibilidad de manifiestos probada (Prioridad 4) y defectos reproducidos dinámicamente (Prioridad 5) con matriz de gravedad (Prioridad 7).
- [ ] Auditorías provisionales de AudioInput v0.2.8–v0.2.12 cerradas por Cris.
- [ ] Autorización explícita para (a) la extensión de verificación de archivos existentes de AudioInput y/o (b) la ejecución del piloto, y en su caso (c) Android/Termux.
- [ ] Pistas designadas por Will, hasheadas, inmutables; guías MVSEP producidas y hasheadas.

Lo que **sí puede hacerse ya sin violar ningún límite** (y que este informe deja preparado): aprobación del protocolo §5, designación de la pista de Tristania, confirmación del mapeo "Etapa 6G.1" ↔ hallazgos del documento de transferencia, y la decisión sobre la extensión de verificación de AudioInput como siguiente subfase autorizable.

---

*Este informe es de preparación: no implementa nada, no procesa audio y no declara ganadores. La aprobación técnica corresponde a Cris; la decisión final a Will.*
