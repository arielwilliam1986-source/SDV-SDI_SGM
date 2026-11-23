# 6G.1 — DISEÑO RG-FLOW: PLAN DE PRUEBAS DE FLUJO REAL POR MOTOR (Hardened / EVO / MQR)

- **Destinatario:** Cris. **Naturaleza:** DISEÑO de pruebas (NO ejecutadas en esta fase de lectura/diseño). Su ejecución futura requiere autorización específica de Cris y arnés propio por motor. Ningún flujo declara compatibilidad EVO/MQR por similitud de código.
- **Principio rector:** cada flujo es una prueba de INTEGRACIÓN REAL (motor sin modificar + adaptación EA/PDA-1 cuando se autorice) — nunca se presentará una prueba de mecanismo como prueba de integración.
- **Precondiciones comunes (todas las FLOW):** directorios de trabajo bajo `/tmp` (prohibido audio real, Android, Termux); fixtures SINTÉTICOS generados por el arnés (PCM determinista, sin música); entorno single-uid declarado; registro JSON de evidencia por flujo (schema `rgflow-1/1`: flujo, motor, commit, precondiciones, acciones, observaciones con líneas, resultado, clasificación DOCUMENTED_FACT/EXPERIMENTAL_RESULT/THEORETICAL_DEDUCTION/HYPOTHESIS/UNKNOWN, criterio PASS/FAIL).
- **Invocación no interactiva por motor (rectificación B — auditoría estática de EVO):**
  - **Hardened:** receta `--manifest` (L2217) — la ÚNICA VERIFICADA EMPÍRICAMENTE (baterías anteriores).
  - **EVO — RECETA DEMOSTRADA POR CÓDIGO (DOCUMENTED_FACT, sin ejecución):** `main` L2351; rama `if args.manifest:` L2358–2391 **NO contiene ningún `input()`** — el camino interactivo queda EXCLUYENTE en `elif args.mix` L2392–2393 y `else` L2394–2395 (`interactive_collect_inputs` L518–540, prompts L529–540); ante stdin cerrado sin `--manifest`, `EOFError` → `EXIT_VALIDATION` (L2396–2398). `load_manifest` L488–515: JSON con `source_mix_file`|`mix_original`, `guide_pairs`|`pairs` (ítems: `pair_id`, `vocal_guide`|`vocal_path`, `instrumental_guide`|`instrumental_path`, opcionales `family`/`variant`/`configuration`/`source_service`/`overlap`), `calibration_parameters` opcionales (`power_p`, `epsilon`, `beta_consensus`, `n_fft`, `hop_length`, `use_physical_residuals`, `smoothing`, `consensus_order`, `consensus`, `mask_mode`) y `output_directory`; rutas relativas resueltas contra el directorio del manifiesto (L493–494). Flags existentes: `--mode` L2330 (default `MODE_FULL_PROCESSING` L2354/L136), `--out` L2331, `--png` L2347, `--keep-masks` L2348, `--write-all-candidates` L2346. **Receta:** `python MOTOR_SEP_SDV-SDI_EVO.py --mode full_processing --manifest <MANIFEST.json> --out <base>`. Su verificación EMPÍRICA queda como primer paso de la futura ejecución autorizada (no se ha corrido nada).
  - **MQR — BLOQUEADO por R-14:** la rama `--manifest` L3767–3768 tampoco llama a `input()`, PERO `mode = args.mode or _interactive_mode()` L3763 y `_interactive_mode()` L3727–3735 PROMPTA por consola (`_prompt_optional`, input L764/776): sin `--mode` explícito la invocación es interactiva. Receta candidata (`--manifest X --mode full_processing --out Y`, flags L3689/3695/3714/3717) **pendiente de confirmación estática completa** (validaciones previas, spec sha) y de verificación empírica. Los flujos MQR permanecen BLOQUEADOS hasta resolver R-14-MQR.

## 1. FLOW-1 — Flujo completo de éxito

- **Precondiciones:** fixture sintético válido; `out_base` limpio bajo `/tmp`; receta no interactiva por motor (§ Precondiciones comunes): H `--manifest` (verificada empíricamente); EVO receta estática demostrada por código (rectificación B) con verificación empírica como primer paso; **MQR: BLOQUEADO por R-14**. Flags según la matriz PROPIA de cada motor (H/EVO: `mix SDV.wav`/`mix SDI.wav` con prefijo; MQR: `SDV.wav`/`SDI.wav` fijos — NUNCA equiparar los nombres).
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
- **Alcance G1 — PRECISIÓN (rectificación A, obligatoria):** el alcance adjudicado de G1 permanece limitado a `analysis.json` y `mix SDV.wav` con los NOMBRES de Hardened/EVO. **NO se equipara `SDV.wav` (MQR, nombre fijo L2115/L2120) con `mix SDV.wav` (H/EVO)**; NO se amplía G1 y NO se altera su registro histórico.
- **FLOW-6 Hardened/EVO:** publica → identidad del publicado == provisional (inodo conservado) → colisión nunca reemplaza (sufijos) → auditoría externa independiente (lstat del publicado vs registro + SHA-256 recalculado vs almacenado) **SÓLO sobre los artefactos del alcance G1** (`analysis.json`, `mix SDV.wav`): coincide → PASS G1; tamper post-publicación → discrepancia detectada (patrón G1b).
- **FLOW-6 MQR (SEPARADO de la auditoría G1):** valida EXCLUSIVAMENTE (i) publicación sin reemplazo atómica, (ii) identidad del directorio publicado == provisional acreditado, (iii) colisiones resueltas con sufijos sin tocar el destino existente. **NO declara PASS de G1 para artefacto alguno**: los WAV de MQR (`SDV.wav`/`SDI.wav`) NO pertenecen al alcance adjudicado de G1, y la coincidencia nominal de `analysis.json` NO amplía el alcance (la auditoría SHA-256 G1 no se ejecuta en MQR hasta que Cris la autorice expresamente con la matriz MQR).
- **Evidencia:** JSON de auditoría externa independiente. **PASS si (H/EVO):** coincide=True y colisión nunca reemplaza. **PASS si (MQR):** (i)+(ii)+(iii) sin ningún enunciado G1. **FAIL si:** destino existente modificado o inodo distinto.

## 6b. FLOW-6-MQR/T7 — Lectura segura del autotest T7 sin TOCTOU por ruta (rectificación C — DISEÑO, no implementado)

Contexto: T7 (`run_self_test`, def L3419) relee `analysis.json` del directorio publicado (L3577–3579) por ruta, DESPUÉS del retorno de `run_experiment`. Una comprobación previa por ruta (`lstat`) seguida de la apertura por ruta **conserva una ventana TOCTOU** (la sustitución puede ocurrir ENTRE el lstat y el open): se documenta la solución sin afirmar que el pre-chequeo por ruta elimine la ventana.

**Secuencia segura documentada (sin volver a resolver la ruta nominal tras la verificación):**
1. **Captura y conservación de la identidad del publicado:** el autotest necesita una identidad ATESTIGUADA por la corrida (`(dev,ino)` del provisional==publicado). Hoy `run_experiment` devuelve SOLO la ruta (contrato CV-B, L2368–2375) — la atestación exige adaptación futura del lado del autotest/evidencia de la corrida (NO es una ampliación de G1: es la referencia de identidad que el autotest necesita para su propio contraste).
2. **Apertura del directorio publicado por descriptor seguro:** UNA sola apertura por ruta: `fd_pub = os.open(ruta_publicada, O_RDONLY|O_DIRECTORY|O_NOFOLLOW)`; esta apertura es inevitable (el retorno es una ruta).
3. **Comparación de identidad del descriptor abierto:** `fstat(fd_pub)` vs la identidad atestiguada en (1): distinta → FAIL-CLOSED (no se lee nada); igual → `fd_pub` queda como ÚNICO punto de acceso. La ventana TOCTOU queda ACOTADA, no eliminada por pre-chequeo: cualquier sustitución previa a esta apertura se DETECTA por identidad (fail-closed), y toda lectura posterior es relativa al descriptor verificado, inmune a sustituciones de la entrada del directorio.
4. **Apertura de `analysis.json` RELATIVA al descriptor:** `os.open('analysis.json', O_RDONLY|O_NOFOLLOW, dir_fd=fd_pub)` — no se sigue la ruta nominal.
5. **Verificación del archivo abierto:** `fstat(fd_file)`: regular, no-symlink, propiedad del euid; si existe referencia de identidad/hash atestiguada por la corrida, contrastarla; si no, el contraste se limita a tipo/propiedad (declarado).
6. **Lectura desde el descriptor verificado:** `os.read`/`os.fdopen(os.dup(fd_file))` — sin re-resolver la ruta nominal en ningún punto posterior.

**Límites del modelo de amenazas (declaración explícita):**
- **Protección DENTRO del ciclo de ejecución:** dominio del modelo de prevención (EA/PDA-1, guardas E/D/G con descriptores) — NO activo hasta integración autorizada.
- **Auditoría POSTERIOR a la publicación:** el autotest T7 es auditoría externa post-publicación; la secuencia 1–6 cierra la ventana ENTRE retorno y lectura (detecta el impostor antes de leer), pero NO es prevención del ciclo.
- **Limitaciones post-return y misma uid:** la misma uid puede alterar el directorio o el archivo DESPUÉS de la verificación del autotest (residual inalienable, B1); si no hay identidad atestiguada (2), el contraste degrada a tipo/propiedad (weaker, declarado); SIGTERM/SIGKILL y el dominio post-return permanecen fuera del modelo de prevención. **G1 NO se amplía para resolver este punto** (alcance histórico intacto).

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

## 9. Matriz de exigencia por motor (estado tras la rectificación documental)

| Flujo | Hardened | EVO | MQR |
|---|---|---|---|
| FLOW-1..8 | **HABILITADOS** para futura autorización (receta `--manifest` verificada empíricamente) | **HABILITADOS** para futura autorización con receta demostrada POR CÓDIGO (rectificación B); verificación empírica de la receta como primer paso de la ejecución; corrida EVO REAL propia (no se hereda de H) | **BLOQUEADOS por R-14** (receta no interactiva no confirmada: `--mode` obligatorio explícito, L3763/L3727–3735); al habilitarse, FLOW-6 MQR valida publicación/identidad/colisiones SIN enunciados G1 (rectificación A) y FLOW-5/6 incorporan la lectura segura T7 de la sección 6b (rectificación C) |

Los flujos 2/3/7 requieren la inyección documentada por puntos concretos (L1456/L1398/L2190/L2776, handlers L2036/L2115/L2413, etc.); la inyección NO modifica los ficheros de producción en disco.

*Fin del diseño RG-FLOW (rectificado documentalmente — ver INFORME_RECTIFICACION_DOCUMENTAL_RG_FLOW_6G1.md). Agente en parada tras publicar.*
