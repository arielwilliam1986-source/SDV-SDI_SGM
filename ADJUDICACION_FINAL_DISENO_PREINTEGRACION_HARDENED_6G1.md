# ADJUDICACIÓN FINAL DEL DISEÑO PREINTEGRACIÓN — HARDENED 6G.1 — v1

- **Auditor y adjudicador:** Cris (ChatGPT). **Ejecutor documental:** Arena.
- **Naturaleza:** resolución que CONSOLIDA las decisiones de Cris y establece la frontera inequívoca entre diseño aceptado, requisitos obligatorios para una implementación futura, incertidumbres técnicas pendientes, autorizaciones todavía inexistentes y actividades expresamente prohibidas. **Exclusivamente documental**: no implementa, no ejecuta, no modifica el plan v2.3 ni el documento v5 ni ningún archivo existente.
- **Etiquetas (esquema de 4, sin mezclar):** **DOCUMENTED_FACT** (comportamiento comprobable en el código, con archivo y línea) · **ADJUDICACIÓN** (decisión expresa de Cris registrada aquí) · **PROPOSED** (mecanismo futuro, no implementado) · **UNKNOWN** (sin evidencia; no se presenta como comprobado nada que no tenga evidencia).

## 1. Identidad Git y padre directo

- **Repositorio:** `arielwilliam1986-source/SDV-SDI_SGM`; **rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Padre directo obligatorio, verificado ANTES de trabajar:** `e4eec2e9283b6b9551ca09ead03af99d185803f8` — HEAD local = origin = GitHub API CONFORMES; árbol limpio.
- Este documento se publica como commit único hijo directo del padre, con EXACTAMENTE un archivo nuevo (este documento).
- **SHA256 reales de las fuentes documentales, calculados sobre el árbol en `e4eec2e…`:**

| Fuente | SHA256 |
|---|---|
| `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (v2.3) | `39632eae6246a6103f7cc7d71b6c934ceb1cdc41cca54ff0e060ac41863f7af4` |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | `a4c157e7607f52a229cb35506ca9c5a57b86d30a6da179fec59ad7df445c416a` |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py` | `b6f7d7eb2646c37fac0a912b777a83369d9e31d8e50d756f36db213a93690caf` |
| `INFORME_AUDITORIA_ESTATICA_CORRESPONDENCIA_MOTOR_PLAN_6G1.md` (`2438559…`) | `a32b40cc5be87db0d8ff81018d01d1e0397549284227d4b6543175b3135d8eb4` |
| `COMPLEMENTO_ADJUDICACION_AUDITORIA_MOTOR_PLAN_6G1.md` (`1b9f5be…`) | `cce9edacc75b4d7f8f4ef0bb778e143472f758fd049a445c038b829015bad646` |
| `DISENO_TECNICO_COMPLEMENTARIO_PREINTEGRACION_HARDENED_6G1.md` (v5, `e4eec2e…`) | `ecb6535725ac75144a5fef2d3693fc0166431233e49204cf1359b42dbd62a00e` |
| `INFORME_FEASIBILITY_1_6G1.md` (v2/R2, `ef90a45…`) | `1b77d261f6c5caf8e6035ad589d27e9b0817d09293b939212c70a868c6e5b6a2` |

## 2. Fuentes documentales consideradas

1. **Plan Hardened FLOW-1..4 v2.3** (`PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md`) — diseño adjudicado (P-01..P-09, §8ter, ciclo P-08, matriz de bibliotecas §8bis). ADJUDICACIÓN de base (histórica, sin reabrir).
2. **Auditoría estática de correspondencia motor/plan** (`2438559…`) — mapa de funciones, brechas P-01..P-09, secuencia actual vs propuesta, inventario de descriptores, riesgos y UNKNOWN. Aceptada.
3. **Complemento documental de adjudicación** (`1b9f5be…`) — Decisiones A (alcance de modos) y B (SR-EI-1), esquema de 4 etiquetas. Aceptado.
4. **Diseño técnico complementario preintegración v5** (`981c29c→30b2b0a→f7450b9→e4eec2e`) — SR-EI-1 (S1-S8, GuiaHandle, A.4.1), aislamiento de modos (B.1-B.7), ciclo de vida y cierre efectivo de memmaps (B.7.0/B.7.1/B.7.2/C.1.1), matriz D-1..D-19. Aceptado con sus UNKNOWN/PROPOSED intactos.
5. **FEASIBILITY-1-R2** (`a94f507…`→`71d928b…`→`ef90a45…`; informe + arnés) — aceptada **exclusivamente como evidencia empírica AISLADA de mecanismos** (§6).
6. Código vigente como fuente de DOCUMENTED_FACT: motor H y `lectura_segura_6g1.py` en los SHA256 de §1 (líneas citadas por la auditoría y el diseño v5).

## 3. Adjudicaciones aceptadas

### 3.A Base documental aceptada (ADJUDICACIÓN)

Quedan aceptadas como base documental de diseño las fuentes 1-4 de §2, más FEASIBILITY-1-R2 en el límite del §6. **La aceptación documental NO equivale a implementación ni a certificación de seguridad del motor** — el motor no ha sido modificado ni ejecutado para validar ninguna de estas decisiones (DOCUMENTED_FACT: cero ejecuciones en toda la fase preintegración).

### 3.B Alcance por modo (ADJUDICACIÓN, D-13 y A del complemento)

- **P-01..P-09 y FLOW-1..4: exclusivamente `full_processing`.**
- **SR-EI-1: ambos modos** (`full_processing` y `single_pair`), conforme a D-13 — verificación de identidad de guías antes del DSP, independiente de las compuertas P-05.
- **`single_pair`: conserva su circuito propio de publicación y aborto** (publicación por rutas vigente, protocolo vigente de aborto); **NO recibe las compuertas P-05** ni la matriz §8ter ni P-06 `_v2` ni P-02 `_v2`.
- **Las equivalencias ordinarias y los cambios deliberados de seguridad siguen diferenciados:** los escenarios ordinarios de `single_pair` exigen equivalencia de artefactos/nombres/contenido/rc; el rechazo fail-closed ante sustitución de guía es un CAMBIO DE SEGURIDAD DELIBERADO en ambos modos, no una regresión de equivalencia.

### 3.C Requisitos obligatorios para una implementación futura (ADJUDICACIÓN)

Se conservan como REQUISITOS de diseño vinculantes (su implementación concreta es PROPOSED hasta fase autorizada; ver matriz §4):

1. **Identidad continua de entradas mediante SR-EI-1** (reapertura controlada + fstat + comparación `(dev,ino)` contra FileInfo + rechazo fail-closed + entrega del mismo descriptor a soundfile vía int fd, sin re-resolver la ruta nominal).
2. **Anclaje de directorios y operaciones relativas a descriptores** (componente a componente; prohibición de rutas multi-componente para abrir).
3. **Entrega de descriptores a bibliotecas sin reabrir rutas nominales cuando el requisito exige identidad continua** (fd-passthrough: `sf_open_fd` closefd=False, `fdopen`, magic-link o cabecera manual).
4. **Gestión explícita del ciclo de vida de writers, lectores, memmaps y descriptores** (creación/acreditación/entrega/cierre emparejados; fallo persistente registrado; sin declarar cerrado sin acreditación).
5. **Cierre efectivo de memmaps antes de publicar** (condición VERIFICABLE, no liberación de referencias; B.7.2).
6. **Acreditación de mapeos por identidad `(dev,ino)`** y consideración de TODAS las entradas de `/proc/self/maps` correspondientes al objeto (no por ruta textual; imposible acreditar ⇒ UNKNOWN, nunca PASS — B.7.2.2-b v5).
7. **Publicación y aborto diferenciados por modo** (`full_processing`: P-06 `_v2` + compuertas + P-02 `_v2`; `single_pair`: circuito propio vigente, sin P-05).
8. **Fallo cerrado ante errores de identidad, cierre o acreditación** (sin EXIT_OK; `CierreNoAcreditado6G1`/`FalloCorrida6G1` según el circuito de cada modo).
9. **Preservación absoluta de las fórmulas y del comportamiento DSP no incluido en la autorización** (STFT/ISTFT/FFT/máscaras/fórmulas/parámetros/reconstrucción intocables; SR-EI-1 y P-03/P-04 cambian CÓMO se accede a los recursos, no QUÉ se calcula).

### 3.D Incertidumbres que NO deben convertirse en PASS (ADJUDICACIÓN)

Queda expresamente prohibido presentar cualquiera de los siguientes puntos como comprobado, validado o integrado:

- **D-16:** PENDIENTE de autorización (regresión comparativa `single_pair` y pruebas con motor).
- **D-18:** UNKNOWN — no existe evidencia de integración de la acreditación de mapeos por identidad `(dev,ino)` (el barrido vigente casa por nombre: DOCUMENTED_FACT, LS L1094-1112).
- **D-19:** PROPOSED — NO se convierte en requisito adjudicado (la apertura componente a componente para pureza de symlink de la ruta completa sigue sin ser exigible).
- **D-8:** FLAC por descriptor — UNKNOWN.
- **Integración de memmaps A/B/C en el motor:** PROPOSED, sin validación.
- **Anclas transitorias de `single_pair` (B.7):** PROPOSED, sin validación exhaustiva.
- **Ausencia de fugas en `single_pair`:** UNKNOWN (requeriría D-16).
- **Android/Termux:** sin validación.
- **R-15:** rendimiento, sin medición.
- **Cualquier comportamiento no ejercitado:** UNKNOWN por defecto.

### 3.E Decisión sobre implementación (ADJUDICACIÓN)

**La aceptación del diseño no autoriza implementar cambios en el motor Hardened.**

No existe autorización para:

- Modificar `motores/`.
- Modificar `lectura_segura_6g1.py`.
- Ejecutar regresiones o pruebas con el motor.
- Ejecutar con audio real.
- Ejecutar en Android/Termux.
- Modificar DSP, fórmulas, parámetros, máscaras o reconstrucción.
- Integrar EVO o MQR.
- Integrar FLOW-5..8.
- Fusionar PR #2.
- Modificar `main`.
- Hacer merge o cherry-pick.

**La eventual fase de implementación requerirá una autorización posterior, expresa y delimitada de Cris.**

## 4. Matriz de requisitos obligatorios

| # | Requisito obligatorio (ADJUDICACIÓN) | Fuente del diseño (PROPOSED su implementación) | Modo |
|---|---|---|---|
| R1 | Identidad continua de entradas (SR-EI-1) | v5 §A (S1-S8, GuiaHandle, ruta int fd) | AMBOS |
| R2 | Anclaje por descriptores, componente a componente | plan P-01 [R-C]; v5 B.7/B.7.0 | full_processing (anclas retenidas) / ambos para aperturas relativas |
| R3 | fd-passthrough sin reabrir rutas nominales donde exige identidad continua | plan P-03/§8bis; v5 A.3 | AMBOS |
| R4 | Ciclo de vida explícito writers/lectores/memmaps/fds | plan P-08/P-09; v5 B.7.1/B.7.2, C.2 | AMBOS (ramas diferenciadas) |
| R5 | Cierre efectivo de memmaps antes de publicar (condición verificable) | v5 B.7.2 | AMBOS |
| R6 | Acreditación de mapeos por `(dev,ino)` + todas las entradas de maps | v5 B.7.2.2-b (v5) | AMBOS (mecanismo hoy inexistente: UNKNOWN D-18) |
| R7 | Publicación y aborto diferenciados por modo | complemento Decisión A; v5 B.1-B.3/B.7.2.6 | AMBOS |
| R8 | Fail-closed ante identidad/cierre/acreditación fallidos | plan P-02/P-05; v5 A.5/B.4.2/B.7.2.6 | AMBOS |
| R9 | Preservación absoluta de fórmulas y DSP no autorizado | restricción permanente | AMBOS |

## 5. Matriz de incertidumbres y pendientes

| ID | Incertidumbre | Estado | Qué la resolvería |
|---|---|---|---|
| D-16 | Regresión comparativa `single_pair` y pruebas con motor | PENDIENTE de autorización | Adjudicación expresa de Cris (protocolo B.6 de v5: escenarios ordinarios = equivalencia; adversariales = fail-closed nuevo) |
| D-18 | Acreditación de mapeos por identidad `(dev,ino)` | UNKNOWN | Implementación + prueba del mecanismo en fase autorizada (no existe hoy: DOCUMENTED_FACT) |
| D-19 | Recorrido componente a componente (pureza symlink de la ruta completa) | PROPOSED | Decisión expresa de Cris sobre si se convierte en requisito obligatorio |
| D-8 | FLAC por descriptor (lectura) | UNKNOWN | Prueba autorizada |
| Memmaps A/B/C | Integración en el motor | PROPOSED, sin validación | Fase de implementación + pruebas autorizadas |
| Anclas transitorias B.7 | Mecanismo de `single_pair` | PROPOSED, sin validación exhaustiva | Fase de implementación + regresión autorizada |
| Fugas en `single_pair` | Ausencia de fugas de fds/mapeos | UNKNOWN | Regresión con verificación (D-16) |
| Android/Termux | Entorno alternativo | Sin validación | Adjudicación específica (fuera de alcance) |
| R-15 | Rendimiento (barridos procfs/compuertas) | Sin medición | Medición en fase autorizada |
| General | Cualquier comportamiento no ejercitado | UNKNOWN por defecto | Evidencia específica |

## 6. Límites de FEASIBILITY-1-R2 (ADJUDICACIÓN)

FEASIBILITY-1-R2 queda aceptada **exclusivamente como evidencia empírica aislada de mecanismos de biblioteca**, en el entorno Linux documentado (Linux 6.1.158+/x86_64/glibc 2.36, Python 3.11.2, numpy 1.26.4, soundfile 0.13.1/libsndfile 1.2.2, euid 1001):

- **Lo que acredita:** lectura/escritura por fd int vía `sf_open_fd` con `closefd=False` (identidad conservada; `closefd=True` cierra el fd propio — EBADF); auto-detección en lectura por fd (TypeError con `format`); open_memmap vía magic-link con fd retenido; variante sin procfs (cabecera manual + `np.memmap(file object)`, guardián 0 disparos); RENAME_NOREPLACE atómico (EEXIST, destino intacto); sustitución del origen detectada SOLO post-rename (R-31, observación, no garantía); magic-link designa el objeto; ledger de descriptores con cierre verificable; errno de rechazo symlink ENOTDIR(20); recorte ±1.0 de libsndfile en PCM_16; dup comparte offset.
- **Lo que NO acredita:** integración de NINGÚN mecanismo en el motor; las anclas transitorias de `single_pair`; la acreditación de mapeos por identidad; FLAC por fd; el comportamiento de `single_pair`; la seguridad del motor. NO es certificación de seguridad ni autorización de implementación.

## 7. Separación de alcance entre `full_processing` y `single_pair` (ADJUDICACIÓN)

| Aspecto | `full_processing` | `single_pair` |
|---|---|---|
| P-01..P-09, FLOW-1..4 | SÍ (implementación futura autorizable) | NO (fuera de la integración) |
| SR-EI-1 | SÍ | SÍ (D-13) |
| Compuertas P-05 / §8ter / hashes G1 / 5bis | SÍ (exclusivas) | NO |
| Publicación | P-06 `_v2` por anclas + `fstat(fd_pub)==I_run` | Circuito propio vigente por rutas |
| Aborto | P-02 `_v2` con anclas retenidas | Circuito propio vigente por rutas |
| Anclas | Retenidas (P-01) | Transitorias (PROPOSED, sin validar) |
| Invariantes de verificación | Según FLOW-1..4 y §8ter | Equivalencia ordinaria + cambios deliberados de seguridad diferenciados |

## 8. Decisión de no autorización de implementación (ADJUDICACIÓN)

**La aceptación del diseño no autoriza implementar cambios en el motor Hardened.** Las once prohibiciones de §3.E quedan registradas y vigentes hasta una nueva adjudicación. Ninguna aceptación documental de §3.A habilita por sí sola actividad sobre el código.

## 9. Condiciones necesarias para abrir una fase posterior (todas PENDIENTES de Cris)

1. **Autorización expresa y delimitada de Cris** que especifique: archivos modificables, mecanismos incluidos (subconjunto de P-01..P-09/SR-EI-1), modo(s) afectados y criterios de aceptación.
2. **Decisión sobre D-19** (obligatorio u optativo el recorrido componente a componente).
3. **Autorización D-16** (protocolo de regresión comparativa de `single_pair` y/o pruebas con motor, con fixtures sintéticos definidos, sin audio real).
4. **Orden técnico de referencia** (v5 §C.1/C.1.1: P-01+P-07 → P-03 → P-04 → SR-EI-1 → P-09 → P-06 → P-08+P-05 → P-02) y su delimitación por tramos (mapa FLOW-1..4 de la auditoría §9).
5. **Mecanismo de acreditación de mapeos por identidad (D-18)** definido como requisito de implementación, sin presentar el barrido vigente por nombre como suficiente.
6. **Verificación previa de que la base documental sigue vigente** (padre exacto, árbol limpio, fuentes sin cambios).
7. **Parada obligatoria** tras cada fase, con adjudicación de Cris entre fases.

## 10. Declaración de parada

Resolución exclusivamente documental: este commit contiene EXACTAMENTE un archivo nuevo (este documento); cero modificaciones de código; cero modificaciones del plan v2.3 y del documento v5; sin pruebas, arneses, fixtures, importaciones ni ejecución de producción; sin audio real ni Android/Termux; sin DSP/fórmulas/parámetros/máscaras/reconstrucción tocados; sin EVO/MQR, FLOW-5..8, `main`; sin merge ni cherry-pick; PR #2 intacto. Los SHA256 de §1 fueron calculados realmente sobre el árbol en el padre `e4eec2e…` (no se afirma hash alguno no calculado). Después de publicar, **parada**: no se inicia implementación, pruebas ni otra fase — se espera la auditoría y adjudicación de Cris.

— Fin de la adjudicación final del diseño preintegración. v1.
