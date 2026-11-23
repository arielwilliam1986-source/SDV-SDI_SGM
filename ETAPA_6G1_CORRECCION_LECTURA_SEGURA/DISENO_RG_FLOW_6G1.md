# 6G.1 — DISEÑO RG-FLOW: PLAN DE PRUEBAS DE FLUJO REAL POR MOTOR (Hardened / EVO / MQR)

- **Destinatario:** Cris. **Naturaleza:** DISEÑO de pruebas (NO ejecutadas en esta fase de lectura/diseño). Su ejecución futura requiere autorización específica de Cris y arnés propio por motor. Ningún flujo declara compatibilidad EVO/MQR por similitud de código.
- **Principio rector:** cada flujo es una prueba de INTEGRACIÓN REAL (motor sin modificar + adaptación EA/PDA-1 cuando se autorice) — nunca se presentará una prueba de mecanismo como prueba de integración.
- **Precondiciones comunes (todas las FLOW):** directorios de trabajo bajo `/tmp` (prohibido audio real, Android, Termux); fixtures SINTÉTICOS generados por el arnés (PCM determinista, sin música); entorno single-uid declarado; registro JSON de evidencia por flujo (schema `rgflow-1/1`: flujo, motor, commit, precondiciones, acciones, observaciones con líneas, resultado, clasificación DOCUMENTED_FACT/EXPERIMENTAL_RESULT/THEORETICAL_DEDUCTION/HYPOTHESIS/UNKNOWN, criterio PASS/FAIL); invocación no interactiva: Hardened vía receta `--manifest` (única verificada), EVO/MQR con su receta propia a resolver en la ejecución (riesgo R-14).

## 1. FLOW-1 — Flujo completo de éxito

- **Precondiciones:** fixture sintético válido; `out_base` limpio bajo `/tmp`; flags por motor según matriz (H: `--manifest` + full; EVO idem; MQR con `--png` fuera).
- **Acciones:** ejecutar el motor completo; observar las líneas de la auditoría (creación L1448/L2181, Tee L1614/L1683/L2358, memmaps, reports, cierre acreditado, publicación L1984/L2095/L2838).
- **Resultado esperado:** `EXIT_OK` + ruta publicada; TODOS los artefactos OB de la matriz presentes con tipo correcto; identidad del publicado == identidad del provisional acreditado (`(dev,ino)` constatado por lstat externo); con adaptación EA: registro forense G y checklist E en PASS.
- **Evidencia:** JSON con (dev,ino) provisional/publicado, listado relativo recursivo, hashes, log de la corrida.
- **PASS si:** EXIT_OK, artefactos completos según matriz, identidad conservada, 0 descriptores residuales bajo el publicado. **FAIL si:** cualquier artefacto OB ausente/incorrecto, identidad distinta, o EXIT_OK con checklist E en FAIL.

## 2. FLOW-2 — Excepción después de abrir varios recursos

- **Precondiciones:** idem FLOW-1; arnés de inyección que MONOPATCHA un punto identificado de la auditoría para elevar tras varias aperturas (puntos por motor: H/EVO: `_open_memmap` L1456/L1456 o el segundo `sf.SoundFile` L1398; MQR: `_open_memmap` L2190 tras la primera pareja o `write_reports` L2776). Sin modificar el motor en disco (parche en memoria del arnés, importando el módulo real).
- **Acciones:** ejecutar con la inyección; dejar que el handler `except Exception` (H L2036/EVO L2115+MQR L2413) ejecute el protocolo completo (preparar L2046/L2157/L2422 → abortar_corrida L900–1026).
- **Resultado esperado:** aborto con `EXCEPCION_DURANTE_EL_PROCESAMIENTO`; TODOS los recursos abiertos cerrados de forma verificada (`cerrar_recursos_corrida_6g1` informe `completo`); `ABORT_6G1.json` presente y verificado (schema abort-6g1/3) en el provisional (o su traslado `_aborted*` sólo si `completo=True`); sin publicación; sin eliminación de archivos.
- **Evidencia:** informe de cierre (orden/errores), ABORT_6G1.json, listado del provisional, `/proc` sin descriptores bajo el provisional.
- **PASS si:** lo anterior. **FAIL si:** recursos sin cerrar, ABORT ausente/no verificado, publicación indebida, o archivos eliminados.

## 3. FLOW-3 — Interrupción después de abrir varios recursos

- **Precondiciones:** idem FLOW-2 (sin parche); arnés que lanza el motor y envía **SIGINT** tras detectar (por log) que los runners/memmaps ya se abrieron (H L1628–1639/EVO L1698–1709/MQR L2469–2487).
- **Acciones:** SIGINT → `except KeyboardInterrupt` (H L2004/EVO L2115/MQR L2377) → preparar → abortar `INTERRUPCION_DEL_USUARIO` → `EXIT_ABORTED`.
- **Resultado esperado:** ídem FLOW-2 con motivo de interrupción; si `completo=False` (p.ej. log no cerrable), traslado omitido y provisional conservado (fail-closed).
- **Evidencia:** idem FLOW-2 + señal/envío registrado. **PASS/FAIL:** idem FLOW-2.
- **Nota (riesgo R-11):** SIGTERM/SIGKILL NO ejecutan este protocolo (sin `signal.signal`): el diseño los declara fuera del modelo de aborto Python (provisional queda sin ABORT; conservación por omisión).

## 4. FLOW-4 — Sustitución de una entrada nominal (misma uid)

- **Precondiciones:** arnés con proceso atacante de la MISMA uid que tras la acreditación (L1448/L2181) sustituye componentes: (a) intermedio (`user/base` → árbol sustituto, escenario D1) y (b) entrada final de `analysis.json` (symlink, escenario C).
- **Acciones:** ejecutar el motor; el atacante sustituye durante el procesamiento.
- **Resultado esperado hoy (sin adaptación):** caso (a): aborto fail-closed con `identidad_distinta (H1)` y **sin ABORT en ningún sitio** (D1 demostrado) — con la adaptación D2: aborto anclado con ABORT dentro del acreditado real; caso (b): la escritura cae FUERA del acreditado (brecha C demostrada) y la detección queda para la adaptación C5/C6+E (creación exclusiva rechaza, checklist detecta identidad distinta) — **FAIL esperado del flujo si la adaptación no está autorizada** (documenta la brecha vigente).
- **Evidencia:** JSON con identidades `(dev,ino)` de los árboles, contenido del objetivo ajeno, estado del protocolo de aborto. **PASS si (con adaptación):** escritura no desviada + sustitución detectada + aborto anclado verificado. **FAIL si:** EXIT_OK con sustitución no detectada.

## 5. FLOW-5 — Comprobación de identidad de TODOS los artefactos (guarda E integrada)

- **Precondiciones:** adaptación autorizada que registre `fd_padre/fd_run/fd_masks/fd_candidates/fd_archivo` por motor (puntos de anclaje de la auditoría: creación L1448/L2181; writers L1396/L1398/L2115/L2120; memmaps L1456/L2190; Tee; makedirs→openat) con el registro de recursos (F1) y el checklist E rectificado (E1-A/E1-B) ejecutándose antes del cierre acreditado del log.
- **Acciones:** corrida exitosa normal + corrida con la misma uid sustituyendo UNA entrada (por artefacto, una corrida por artefacto de la matriz).
- **Resultado esperado:** checklist PASS en la corrida limpia; en cada corrida de sustitución: FAIL del checklist (descriptor ausente/identidad distinta/symlink/directorio sustituido según el caso E1-A1..B5) y BLOCKEO de EXIT_OK (aborto `GUARDA_COMPLETIDAD`).
- **Evidencia:** detalle del checklist por artefacto (existe/tipo/no-symlink/descriptor/identidad). **PASS si:** 0 artefactos OB con PASS defectuoso y bloqueo ante cada sustitución. **FAIL si:** EXIT_OK con cualquier artefacto OB comprometido.

## 6. FLOW-6 — Publicación acreditada (PDA-1 integrada)

- **Precondiciones:** adaptación autorizada; destino ocupado precolocado (colisión) y destino libre en dos corridas separadas.
- **Acciones:** publicar con `publicar_dir_6g1` (renameat2 NOREPLACE) tras checklist E y registro forense G (`publicacion_6g1.json` por fd_run antes del renombrado).
- **Resultado esperado:** publicación atómica sin reemplazo (sufijo ante colisión); identidad del publicado == provisional (renombre conserva inodo); auditoría externa: lstat vs registro + SHA-256 de los artefactos del registro (alcance G1 vigente: `analysis.json`, `mix SDV.wav` — SIN ampliar) — coincide → PASS; tamper post-publicación → discrepancia detectada (patrón G1b).
- **Evidencia:** JSON de auditoría externa independiente. **PASS si:** coincide=True y colisión nunca reemplaza. **FAIL si:** destino existente modificado o inodo distinto.

## 7. FLOW-7 — Aborto acreditado (D2 integrada)

- **Precondiciones:** adaptación autorizada; inyección de excepción con intermedio sustituido (escenario D1) para forzar el fallback del anclaje por ruta.
- **Acciones:** protocolo vigente primero; si `identidad_distinta (H1)` → aborto anclado `abortar_anclado_6g1(fd_padre, nombre_prov, fd_run, …)` (diseño D2): inventario por descriptor, `ABORT_6G1.json` O_EXCL|NOFOLLOW dentro del acreditado real, invalidadas conservadas sin eliminación, verificación por re-lectura anclada, cierre F1 completo.
- **Resultado esperado:** ABORT verificado DENTRO del acreditado real; atacante sin ABORT; salidas propias en `salidas_invalidadas` conservadas; 0 descriptores residuales.
- **Evidencia:** ABORT_6G1.json + inventario + `/proc`. **PASS si:** lo anterior. **FAIL si:** ABORT escrito fuera del acreditado o archivos eliminados.

## 8. FLOW-8 — Cierre inverso y cero descriptores residuales

- **Precondiciones:** adaptación autorizada (registro F1 integrado en `cerrar_recursos_corrida_6g1`/`preparar_aborto_6g1` y en el cierre acreditado normal).
- **Acciones:** los tres caminos (éxito/excepción/interrupción) con verificación `/proc/self/fd` antes/después; orden de cierre registrado.
- **Resultado esperado:** orden inverso exacto (archivos → `fd_candidates` → `fd_masks` → `fd_run` → `fd_padre`); cierre exacto una vez (idempotente); sin cierre prematuro (bibliotecas usan su dup; WAV con frames íntegros antes del cierre); 0 residuales en los tres caminos.
- **Evidencia:** informe de cierre con orden + medición de `/proc`. **PASS si:** 0 residuales + orden correcto + duplicados=0. **FAIL si:** cualquier descriptor residual o cierre prematuro detectable (frames corruptos).

## 9. Matriz de exigencia por motor

| Flujo | Hardened | EVO | MQR |
|---|---|---|---|
| FLOW-1..8 | obligatorios (receta `--manifest` verificada) | **obligatorios con corrida EVO REAL propia** (no se hereda de H) | **obligatorios con corrida MQR REAL propia**; FLOW-5/6 incluyen además la verificación de identidad del publicado para la relectura del autotest T7 (L3578–3579, informe §4.2) |

Los flujos 2/3/7 requieren la inyección documentada por puntos concretos (L1456/L1398/L2190/L2776, handlers L2036/L2115/L2413, etc.); la inyección NO modifica los ficheros de producción en disco.

*Fin del diseño RG-FLOW. Agente en parada tras publicar.*
