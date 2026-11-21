# RECTIFICACIÓN DEL INFORME DE PREPARACIÓN — PILOTO MUSICAL ELIS / TRISTANIA

**Modalidad**: solo lectura y documentación. **No se modificó código, motores, DSP ni archivos del usuario; no se ejecutó Android/Termux; no se procesó audio; no se tocaron canciones.** La única operación sobre Git fue una lectura (`fetch`) de la rama `arena/89d5c189-sdv-sdi-sgm` para inspección; ningún push a ramas ajenas, ningún merge.

- **Fecha**: 2026-11-21
- **Rama de trabajo**: `arena/441a4bf8-sdv-sdi-sgm` — base del informe original: `152957a` (`152957a46f5c676afb9e7703231539dfda352d89`)
- **Informe rectificado**: `herramientas/diagnostico_audio/INFORME_PREPARACION_PILOTO_ELIS_TRISTANIA.md`
- **Responsable técnico**: Cris · **Decisor final**: Will
- **Estado**: PROVISIONAL — pendiente de auditoría de Cris y decisión de Will
- **Fuente de la rectificación**: instrucción documental de Will/Cris recibida el 2026-11-21 (aceptaciones de C5, existencia de 6G.1 en otra rama, designación de material). Los hechos comunicados en esa instrucción se marcan como `COMUNICADO (instrucción)`; todo lo demás lleva evidencia de repositorio.

**Propósito**: corregir las imprecisiones del informe de preparación **sin reabrir código ni modificar motores**. El informe original queda en el historial como quedó; este documento lo rectifica punto por punto y una nota de cabecera en el original enlaza aquí.

---

## 0. Tabla de rectificaciones (afirmación original → afirmación corregida)

| # | Afirmación en el informe original (`152957a`) | Rectificación |
|---|---|---|
| R1 | «La Etapa 6G.1 no existe en el repositorio» (0 resultados en `git grep` sobre la rama de trabajo) | **Existe** en la rama `arena/89d5c189-sdv-sdi-sgm`, carpeta `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`, commit `015e2f8` (2026-11-19). La inspección anterior se limitó a una sola rama; la ausencia de la denominación en esta rama no prueba la inexistencia de la etapa. |
| R2 | «v0.2.8–v0.2.12 pendientes de auditoría de Cris» | **C5-A y C5-C fueron aceptados por Cris** (`COMUNICADO (instrucción)`). C1, C4-A y C4-B permanecen **cerrados y congelados**; la fase de correcciones C5 está **concluida**. Lo único pendiente de AudioInput es la **validación real Android/Termux**. C5 no se presenta como pendiente de auditoría. |
| R3 | «S5 = prueba per_channel en motores reales — Pendiente, Prioridad 2» (sin desglose) | Dos niveles distintos: (i) el **estudio sintético S5 ya se ejecutó y fue auditado** (bloques A–D, `S5_STEREO_VALIDATION/` en `arena/89d5c189-sdv-sdi-sgm`); (ii) la **batería `per_channel` pendiente** (propuestas P1–P6) usa **fixtures sintéticos controlados** y **no necesita las canciones Elis ni Tristania**. |
| R4 | «Tristania sin candidata designada» | **Designada oficialmente**: Tristania — Lethean River, con ruta explícita (§4). |
| R5 | «Matriz de defectos: lista de defectos pendientes que bloquean el piloto» (tratamiento genérico) | Los 10 defectos del documento de transferencia **no están todos abiertos**: 1 reproducido con corrección solo en copias experimentales, 3 pendientes de prueba con diseño documentado, 6 sin evidencia en repositorio (Desconocidos). Matriz clasificada en §5. |
| R6 | «Material sin fijar» | Material **designado oficialmente** (ambas rutas registradas en §4), **pero sin hash, sin inspección y sin verificación** — no está listo para procesamiento. |

**No se rectifica** (permanece válido): la recomendación de modalidad (inspección estática), la restricción de no declarar ganador, el protocolo F0–F6 como propuesta, la inexistencia de muestras de audio en el repositorio de esta rama.

---

## 1. Estado actualizado de AudioInput

### 1.1 Estado de las correcciones (rectifica R2)

| Ítem | Estado | Procedencia |
|---|---|---|
| C5-A (cierre conservando interrupción, helper con `finally` + pre-vinculación) | **ACEPTADO por Cris** | `COMUNICADO (instrucción)` — no consta dictamen en el repositorio |
| C5-C (publicación tras interrupción, anclaje de directorio + `lstat`) | **ACEPTADO por Cris** | `COMUNICADO (instrucción)` |
| C1 (`os.link`), C4-A (`OwnedFdResource`/estados), C4-B (acumulador/atribución) | **CERRADOS Y CONGELADOS** (no reabrir) | `COMUNICADO (instrucción)` + informe de cierre v0.2.11 |
| Fase de correcciones C5 (v0.2.11 + v0.2.12) | **CONCLUIDA** | `COMUNICADO (instrucción)` |
| Validación real Android/Termux | **PENDIENTE** — única puerta abierta de AudioInput | `COMUNICADO (instrucción)`; el instrumento se ejecuta hoy sólo en el sandbox Linux, nunca se validó en el entorno Termux destino |

Identidad del instrumento entregado (v0.2.12, `etapa2/audioinput_diag_termux.py`): blob Git `9abecd18770236e7e5c269ba0e4336f98bdafc27`, SHA-256 `de69863bafb2a7cb17540b15c59bc41d3165730246983ceeb22fd0a2987060b6`, 155.558 B / 3.181 L. Commits: código `acd1d26`, informe `d2efc30`, corrección documental `7afdff3` + `9b3608d`.

### 1.2 Limitación vigente (sin cambios respecto del informe original, confirmada)

- El instrumento actual **no ofrece una modalidad para verificar directamente archivos musicales existentes**: sólo abre fixtures sintéticos que él mismo crea. La extensión «verificación de archivo existente» (condición C-1 del informe original) **no fue iniciada**.
- **Instrucción vigente**: no iniciar otra ronda de correcciones de AudioInput. La extensión C-1 queda registrada como **subfase futura autorizable aparte**; no se implementa en esta tarea.

---

## 2. Estado correcto de la Etapa 6G.1 (rectifica R1)

### 2.1 Localización e identidad

- **Rama**: `arena/89d5c189-sdv-sdi-sgm` (tip `015e2f8`, fechado 2026-11-19 20:59 UTC). La inspección anterior no la consultó; el error metodológico fue concluir inexistencia desde una sola rama.
- **Cadena de etapas visible en esa rama**: ETAPA_6 (diagnóstico alineación) → 6B (validación alineación) → 6C (corrección experimental con trazabilidad por defecto) → 6D (auditoría independiente) → 6E (corrección atribución/integridad) → 6F (cierre correctivo, dictamen **APROBADO CON LIMITACIONES**) → 6G (soporte nativo WAV/FLAC del Mix en los tres motores, `ee19fe2`) → **6G.1 (lectura del Mix desde un único descriptor vigilado y aborto seguro, `015e2f8`)**.
- Verificado por `git show --name-only`: los commits `ee19fe2` y `015e2f8` **sólo tocan sus propias carpetas** (`ETAPA_6G_SOPORTE_FLAC_MIX/`, `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`); el README de 6G.1 declara la carpeta autónoma («no modifica 6G ni etapas anteriores»). Los motores originales (`Proyecto SDV-SDI_SGM/`) quedan intactos; las correcciones viven en **copias** dentro de la carpeta de la etapa.
- El documento de transferencia (`Proyecto SDV-SDI_SGM — Estado y continuidad.txt`, blob `c24493ed1ce941498033ef0d70f8f1319ca54895`) es **idéntico en ambas ramas** y es anterior (2026-11-18) a 6G/6G.1 (2026-11-19): por eso no los menciona.

### 2.2 Contenido declarado de 6G.1 (lectura de sus documentos)

1. El Mix se valida **una vez** y se lee siempre desde **el mismo descriptor** (`/proc/self/fd/N`) durante todo el DSP; ningún componente reabre por ruta.
2. Si el archivo o la ruta cambian, el motor **aborta**, invalida las salidas de audio de esa corrida, registra `ABORT_6G1.json` y **no borra** archivos preexistentes ni ajenos (prueba 7: 6/6 ACCEPTED, archivos sembrados conservados y listados).
3. Matriz con enum de veredictos explícito (`ACCEPTED`, `REJECTED`, `PCM_IDENTICAL`, `PCM_DIFFERENT`, `NOT_APPLICABLE`, `NOT_EXECUTED`) y condición material de PCM real (corrige el defecto de la matriz 6G que podía comparar diccionarios vacíos).
4. DSP sin cambios: verificado por AST, huella de literales/llamadas y **PCM idéntico byte a byte frente a 6G** en WAV y FLAC.

### 2.3 Separación histórico-cerrado vs abierto

**Histórico (cerrado, no reabrir):**
- Pruebas 1–10 ejecutadas sobre fixtures sintéticos: **64 filas** — 46 `ACCEPTED`, 6 `PCM_IDENTICAL`, 8 `NOT_APPLICABLE`, 4 `NOT_EXECUTED`, **0 `REJECTED`** (`INFORME_VALIDACION_6G1.md` §2, `evidence/matriz_global_6g1.csv`).
- Equivalencia WAV↔FLAC de PCM de salida en `full_processing` para los tres motores copia (Hardened, EVO, MQR) — 3× `PCM_IDENTICAL` en pruebas 3 y 9.
- Sustitución del Mix abortada antes/durante/después del DSP (pruebas 4–6, 13 casos ACCEPTED; caso 4b documentado con su limitación: la carrera no se ganó por tiempo, la guarda final abortó igualmente; la guarda previa queda demostrada de forma determinista por 4a y 4c).
- Corrección del falso negativo FLAC en `wav_integridad_6f`/`audio_integridad_6g` (comparación por claves de objeto).

**Abierto:**
- **(i) Auditoría de 6G.1**: el `INDICE_PARA_AUDITORIA_6G1.md` está **preparado para auditoría**; no consta dictamen de auditoría de 6G.1 en el repositorio. Estado real: **entregado, auditoría pendiente** (revisión de Cris).
- **(ii) Defecto preexistente de Hardened en `analysis_only`**: aborta con `AttributeError` en `write_reports` (`ctx["post_wav_validation"]` es `None` cuando `full_mode` es `False`). Reproducido **idénticamente** en la copia 6G → defecto preexistente de 6F/6G, **no regresión de 6G.1**; se dejó sin corregir por estar fuera del alcance autorizado. Son las 4 filas `NOT_EXECUTED`. Sigue abierto.
- **(iii) Alcance de la etapa**: 6G.1 cubre contenedores, lectura segura y aborto del **Mix**; no cubre alineación, máscaras ni calidad perceptual (los UNKNOWN de S5 siguen siendo los que son).

---

## 3. Estado de S5 (rectifica R3)

### 3.1 Pruebas sintéticas de integridad estéreo — YA EJECUTADAS (histórico, no repetir)

- **Qué es**: estudio sintético de independencia estéreo de los **cuatro motores reales** (A·v3, B·Hardened, C·EVO, D·MQR) con señales L/R diferenciadas por diseño (S1–S7), ejecutado el 2026-11-18 en la rama `arena/20d905c7-sdv-sdi-sgm` y archivado en `S5_STEREO_VALIDATION/` de `arena/89d5c189-sdv-sdi-sgm` (commits `c1ce9e2` estudio, `9fc5fc9` auditoría independiente).
- **Evidencia**: 26 WAV de entrada, 116 corridas completadas + 2 del aborto (144 WAV conservados), 59 máscaras en NPY, 5 paquetes `tar.xz` sin pérdida (55.911.452 B), hashes por miembro (`hashes/MIEMBROS_SHA256.txt`).
- **Dictamen de la auditoría independiente**: «Integridad: CONFIRMADO. Conclusión sobre independencia estéreo: **CONFIRMADO CON LIMITACIONES**» — cambiar sólo las guías derechas no cambió máscara ni salidas izquierdas en los tres `per_channel` ensayados; sí en las cuatro configuraciones compartidas. No certifica todos los modos, ni la alineación, ni calidad musical.
- **Hallazgo documentado de MQR**: en S7 (antifase) `CandidateMetrics.finalize` calcula `crest_factor_sdv` con denominador cero → `ZeroDivisionError`, exit 2, aborto documentado (no es resultado válido de MQR). El dictamen lo convierte en requisito: condición de parada explícita antes de lotes no supervisados (propuesta P1). Sin corrección en los originales.
- **Esta campaña está cerrada**: sus salidas son **referencia de solo lectura**. No repetir ni regenerar.

### 3.2 Prueba `per_channel` — PENDIENTE (con fixtures sintéticos, sin canciones)

- La batería profunda `per_channel` existe como **propuestas documentadas P1–P6** (`S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/PRUEBAS_PENDIENTES.md`), con configuración exacta por caso, señal, mediciones y predicciones; resultado declarado `UNKNOWN` («Propuestas, no ejecuciones ni autorización»).
- **Base común ya definida**: dos canales WAV FLOAT 44.100 Hz, 4 s, FFT 4096, hop 1024, chunks de 64, sin suavizado/normalización/resampleo/corrección de alineación; versión y hash de motor, Mix y manifiesto fijados por condición. `--allow-misaligned` sólo para observar avisos en señales de temporización conocida, **no** política para admitir música.
- **No requiere Elis ni Tristania.** Las canciones quedan explícitamente fuera de esta fase.
- Continúa siendo **Prioridad 2** del documento de transferencia. Ejecutarla requiere revisión de Cris y autorización de Will; no se ha ejecutado ni autorizado.

---

## 4. Designación oficial del material musical (rectifica R4/R6)

Designadas oficialmente, según la instrucción de esta rectificación:

| Canción | Ruta designada (dispositivo del usuario, fuera del repositorio) |
|---|---|
| **Elis — Die Stadt** | `/storage/emulated/0/Download/SGM Music/Proyecto MVSEP/Proyecto renovado Nov/Elis - Die Stadt/Carpeta_Maestra` |
| **Tristania — Lethean River** | `/storage/emulated/0/Download/SGM Music/Proyecto MVSEP/Proyecto renovado Nov/Tristania - Lethean River/Carpeta_Maestra` |

**Estado real del material** (sin suposiciones):
- **No** se ha inspeccionado: se desconoce contenido, formatos, duraciones, canales y número de archivos de cada `Carpeta_Maestra`.
- **No** está hasheado ni verificado: **no afirmar** que está listo para procesamiento.
- No existe ninguna muestra de audio en el repositorio de esta rama; las rutas anteriores pertenecen al almacenamiento del dispositivo del usuario y no pueden inspeccionarse desde aquí.
- Nota histórica vigente: el motor MQR original (rama de trabajo, `sdv_sdi_mqr_engine.py`, l. 10 y @2608) menciona «Elis - Die Stadt» como pista de calibración designada; esa mención es de código, no una validación del archivo real.

---

## 5. Matriz actualizada de los diez defectos de Fase 1B (rectifica R5)

Clasificación solicitada: **Cerrado con evidencia / Pendiente de prueba / Defecto reproducido / No aplicable al piloto / Desconocido**. Los resultados históricos de Fase 1B (consenso `magnitudes_first` no-op con max|Δ| = 0.0; equivalencia algebraica de tres métodos de máscara con K=2; alineación 554/780 = 71,0 % con 10 FP; `SDI_F2` UNKNOWN; polaridad no detectada por algunas verificaciones) **se conservan como históricos y no se repiten aquí**.

| # | Defecto (documento de transferencia) | Clasificación | Evidencia y detalle |
|---|---|---|---|
| 1 | «estricto_subtype» no se propaga en determinadas rutas | **Desconocido** | 0 menciones en `REPORT.md` de Fase 1B y 0 en los documentos de las etapas 6A–6G.1 de `arena/89d5c189`. No hay reproducción, prueba ni corrección documentada. Requiere mapeo (quién lo identificó y en qué archivo). |
| 2 | Archivos «C» corruptos pueden provocar excepciones no controladas | **Desconocido** | El término «archivos C» no está mapeado a un artefacto del repositorio (¿archivos corruptos genéricos, componente C, bloque C de S5?). Evidencia adyacente: en las **copias** 6G, contenedores corruptos del Mix (FLAC truncado, corrupto, sin audio, renombrados) son **RECHAZA** en la matriz de validación 6G — alcance limitado al contenedor del Mix; no cubre el defecto como fue enunciado. |
| 3 | Procesamiento de residuos puede fallar con audio mono | **Pendiente de prueba** | Existe diseño de prueba exacto sin ejecutar: **P6** de `PRUEBAS_PENDIENTES.md` (guardas de residuales: `dry_run --mask-mode per_channel` con/ sin `--use-residuals`, y aplicación `mono`; se espera `EXIT_VALIDATION=1` en la combinación incompatible). S5 declara los residuales físicos como no evaluados. Fixtures sintéticos; no requiere canciones. |
| 4 | «out_dir=None» puede provocar errores al generar resultados | **Desconocido** | 0 evidencia en repositorio (ni reproducción ni prueba). Mitigación operativa para el piloto con independencia del defecto: protocolo F1 con directorios de salida dedicados, nunca el árbol de entrada. |
| 5 | No se ha verificado que se impida guardar resultados dentro del árbol de entrada | **Desconocido** | No hay prueba documentada. Adyacente y distinto: la prueba 7 de 6G.1 verifica higiene del **aborto** (no borra ajenos, invalida salidas propias), no la política de escritura en el árbol de entrada. |
| 6 | El estado global puede devolver ACCEPT con grupos SIN_PERFIL | **Desconocido** | 0 menciones de «SIN_PERFIL» en los documentos de ambas ramas fuera del documento de transferencia. Requiere mapeo. |
| 7 | La alineación v3 usa downmix mono y no estima retardos independientes L/R | **Defecto reproducido** | Reproducido y documentado: expediente E6 (`ETAPA_6_ALINEACION_DIAGNOSTICO/DEFECTOS_REPRODUCIBLES.json`), validación 6B y matriz de trazabilidad 6C. Corrección aplicada **solo en copias experimentales** B/C/D (X2 CONFIRMADO: retardos independientes por canal, p. ej. #26 (1103,0) y #27 (0,1103) sin reloj común), con cadena 6C→6D→6E→6F (dictamen 6F: APROBADO CON LIMITACIONES). En **v3: sin corrección** (filas A1/A2 «Ninguno»; «Corrección en v3 NO CONFIRMADO») y los originales intactos. La evaluación en mono **no certifica** la alineación estéreo (REPORT.md Fase 1B). |
| 8 | El manifiesto del orquestador no coincide con el esquema esperado por v3 | **Pendiente de prueba** | Tabla de pruebas críticas del documento de transferencia: «Compatibilidad de manifiestos: Inspección realizada; **transformación no probada**» (Prioridad 4). |
| 9 | Discrepancia documental entre 71 archivos y 74 líneas de hashes | **Desconocido** (documental) | Única mención: el propio documento de transferencia (línea 176). Ninguna aclaración en el repositorio. Es puramente documental — no bloquea DSP, pero debe aclararse antes de confiar en los hashes de Fase 1B como referencia. |
| 10 | La prueba S5 «per_channel» en motores reales no ha sido completada | **Pendiente de prueba** | Desglosado en §3: la parte sintética ya ejecutada y auditada (histórico cerrado); la batería P1–P6 pendiente, con fixtures sintéticos controlados y sin canciones. |

**Resumen**: Cerrado con evidencia: **0 de 10** (los cierres con evidencia de la serie 6 corresponden a correcciones en **copias experimentales** de etapas 6B–6G.1, no a la lista de defectos de Fase 1B; ningún defecto de esta lista queda cerrado en los originales). Pendiente de prueba: **3** (#3, #8, #10). Defecto reproducido: **1** (#7). No aplicable al piloto: **0** (ninguno puede excluirse sin mapeo previo). Desconocido: **6** (#1, #2, #4, #5, #6, #9).

**No se asume** que los defectos sigan abiertos; **no se declara** ninguno corregido sin evidencia. Los defectos reproducidos en copias experimentales (#7) siguen abiertos en los **originales**.

---

## 6. Bloqueos reales para el piloto (actualizados)

1. **Material designado pero no inspeccionado ni hasheado** (§4): sin inventario, sin SHA-256, sin verificación de procedencia. Las rutas viven fuera del repositorio; quien custodie los archivos debe producir el inventario.
2. **AudioInput sin modalidad de verificación de archivos existentes**: la extensión C-1 no fue iniciada y **no debe iniciarse** (instrucción vigente: no abrir otra ronda de correcciones de AudioInput). Alternativa no elegida ni anticipada: los motores con copias 6G/6G.1 leen Mix real WAV/FLAC con lectura vigilada; elegir vía es decisión de Cris/Will.
3. **Batería S5 `per_channel` sin ejecutar** (P1–P6, Prioridad 2): independiente de las canciones; usa fixtures sintéticos controlados.
4. **Seis defectos Desconocidos** (#1, #2, #4, #5, #6, #9): riesgo no cuantificado hasta el mapeo; reproducirlos dinámicamente (Prioridad 5) requiere autorización y pruebas aisladas.
5. **v3 sin corrección de alineación L/R** (#7): si v3 participa, sus resultados de alineación no son independientes por canal — dato histórico vigente, no una descalificación anticipada.
6. **Defecto preexistente de Hardened en `analysis_only`** (6F/6G, abierto): si se usa esa copia en ese modo, abortará; no es regresión de 6G.1.
7. **MQR S7**: fallo documentado (división por cero con mid nulo) sin corrección en originales; condición de parada explícita exigida por el dictamen de auditoría S5 antes de lotes no supervisados.
8. **Estado de auditoría de 6G/6G.1 sin dictamen en repositorio** (índices preparados para auditoría): revisión de Cris pendiente.
9. **Entrega ≠ aprobación**: este informe de rectificación y el informe original requieren auditoría de Cris y decisión de Will.

---

## 7. Secuencia de trabajo recomendada

Cada paso requiere revisión de Cris y/o autorización expresa de Will antes de ejecutarse; ninguno está iniciado.

1. **Auditoría de esta rectificación** (Cris) y decisión (Will) sobre los puntos que dependen de ella.
2. **Mapeo documental de la rama `arena/89d5c189-sdv-sdi-sgm`** (solo lectura): revisión de los índices para auditoría de 6G/6G.1 y del dictamen 6F; cerrar la pregunta del estado de auditoría de 6G.1 y decidir si sus copias son candidatas para el piloto (sin selección anticipada).
3. **Mapeo de los defectos Desconocidos** (#1, #2, #4, #5, #6, #9): identificar origen y componente afectado; decidir reproducir dinámicamente (con pruebas aisladas y autorización) o archivar como no aplicables. #9 se aclara con una auditoría documental de los hashes de Fase 1B (solo lectura).
4. **S5 `per_channel`** (Prioridad 2): Cris selecciona el subconjunto de P1–P6 aplicable a los riesgos reales del material («validar los controles asociados a los riesgos que efectivamente tenga el material, no aprobar por número de ensayos»); ejecución con fixtures sintéticos controlados, sin canciones, en copias de trabajo.
5. **Material musical**: inventario + SHA-256 de ambas `Carpeta_Maestra` por quien custodie los archivos (dispositivo del usuario); registro de procedencia antes de cualquier lectura por cualquier componente.
6. **Vía de lectura para el piloto** (decisión Cris/Will, sin implementar ahora): (a) extensión AudioInput C-1 como subfase autorizable aparte, o (b) lectura directa por motores con las copias 6G/6G.1 tras su auditoría. No iniciar ninguna en esta tarea.
7. **Piloto Elis/Tristania** con el protocolo F0–F6 del informe original, solo cuando: material hasheado y verificado, vía de lectura decidida, S5 `per_channel` cerrada, y con evaluación auditiva ciega de Will como criterio final — **sin declaración de ganador** (restricción #9 del proyecto).

---

## 8. Evidencias y enlaces GitHub

Rama de trabajo (`arena/441a4bf8-sdv-sdi-sgm`):
- Informe original: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/INFORME_PREPARACION_PILOTO_ELIS_TRISTANIA.md (commit `152957a`)
- Documento de transferencia (blob `c24493ed`, idéntico en ambas ramas): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM%20%E2%80%94%20Estado%20y%20continuidad.txt
- Motor MQR original con pista de calibración: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM/sdv_sdi_mqr_engine.py
- Fase 1B: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/SDV-SDI_FASE_1B_ENTREGA/REPORT.md

Rama `arena/89d5c189-sdv-sdi-sgm` (solo lectura para esta rectificación):
- Etapa 6G.1 (commit `015e2f8`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/89d5c189-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA — validación: `INFORME_VALIDACION_6G1.md` (64 filas: 46 ACCEPTED / 6 PCM_IDENTICAL / 8 NOT_APPLICABLE / 4 NOT_EXECUTED / 0 REJECTED); índice de auditoría: `INDICE_PARA_AUDITORIA_6G1.md`; abierto: §7.1 (Hardened `analysis_only`).
- Etapa 6G (commit `ee19fe2`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/89d5c189-sdv-sdi-sgm/ETAPA_6G_SOPORTE_FLAC_MIX (matriz con RECHAZA para FLAC truncado/corrupto/sin audio).
- Trazabilidad de defectos 6C (X/H/C/D/A): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/89d5c189-sdv-sdi-sgm/ETAPA_6C_CORRECCION_EXPERIMENTAL/TRAZABILIDAD_DEFECTOS.md
- Etapa 6F (dictamen APROBADO CON LIMITACIONES): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/89d5c189-sdv-sdi-sgm/ETAPA_6F_CIERRE_CORRECTIVO
- S5 (estudio `c1ce9e2`, auditoría `9fc5fc9`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/89d5c189-sdv-sdi-sgm/S5_STEREO_VALIDATION — dictamen: `AUDIT_INDEPENDIENTE/INFORME_AUDITORIA_S5.md`; pendientes P1–P6: `AUDIT_INDEPENDIENTE/PRUEBAS_PENDIENTES.md`; informe: `reports/INFORME_S5.md`.

Comandos de verificación usados (todos de solo lectura): `git ls-remote`, `git fetch` (rama ajena, sin push), `git show`, `git ls-tree`, `git grep`, `git log`, `git diff --stat` entre blobs.

---

**Rectificación elaborada en modalidad solo lectura/documentación. No se modificó código ni motores; no se ejecutó DSP ni Android/Termux; no se abrió, copió ni procesó material musical; no se tocaron `main`, merges ni ramas ajenas. Pendiente de auditoría de Cris y decisión de Will.**
