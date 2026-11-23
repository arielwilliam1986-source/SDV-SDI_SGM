# 6G.1 — INFORME DE RECTIFICACIÓN DOCUMENTAL DEL DISEÑO RG-FLOW (A, B, C)

- **Destinatario:** Cris (ChatGPT), coordinación y adjudicación.
- **Naturaleza:** rectificación EXCLUSIVAMENTE documental (lectura, análisis y modificación de documentos de diseño), conforme a la instrucción. **Cero modificaciones de producción**; nada implementado; ningún flujo ejecutado.
- **Commit padre obligatorio:** `28b91187dda1bd79b701970fdede87641044acae` (auditación estática aceptada). **Referencia de producción:** `9fedc5b223444e73955d2b899b6a434b0f5c670e`.
- **Ficheros modificados (exclusivamente los autorizados):** `DISENO_RG_FLOW_6G1.md` (M), `REGISTRO_RIESGOS_6G1.md` (M). **Ficheros nuevos:** este informe + manifiesto + sumas. Los documentos históricos (informes anteriores, matriz, prototipos, evidencias) NO se modifican ni eliminan.

## 1. Los tres hallazgos y la solución documental adoptada

**A — Alcance de G1 y MQR (precisión de nombres).** El alcance adjudicado de G1 permanece limitado a `analysis.json` y `mix SDV.wav` (nombres de Hardened/EVO). El diseño anterior permitía leer FLOW-6 como si la auditoría G1 cubriera también los artefactos de MQR. **Solución:** RG-FLOW §6 reestructurado — (i) prohibición explícita de equiparar `SDV.wav` (MQR, fijos L2115/L2120) con `mix SDV.wav` (H/EVO); (ii) G1 sin ampliación ni reescritura histórica; (iii) FLOW-6 separado por motor: Hardened/EVO ejecutan la auditoría G1 SOLO sobre su alcance adjudicado; **FLOW-6 MQR valida exclusivamente publicación sin reemplazo, identidad del directorio publicado y colisiones, SIN declarar PASS de G1 para artefacto alguno** (la coincidencia nominal de `analysis.json` no amplía el alcance); (iv) las tres matrices de artefactos se mantienen explícitamente distintas (R-22).

**B — Contradicción FLOW-1 EVO vs R-14 (receta no interactiva).** **Resuelta por auditoría estática A FAVOR de EVO:** la rama `if args.manifest:` de EVO `main` (L2358–2391) NO contiene ningún `input()`; el camino interactivo es EXCLUYENTE (`elif args.mix` L2392–2393 / `else` L2394–2395 → `interactive_collect_inputs` L518–540); sin `--manifest` y con stdin cerrado, `EOFError` → `EXIT_VALIDATION` (L2396–2398). `load_manifest` (L488–515) define el JSON exacto (`source_mix_file`|`mix_original`; `guide_pairs`|`pairs` con `pair_id`/`vocal_guide`|`vocal_path`/`instrumental_guide`|`instrumental_path` y opcionales; `calibration_parameters`; `output_directory`; rutas relativas al directorio del manifiesto). **Receta documentada (respaldada por el código, sin argumentos inventados):** `python MOTOR_SEP_SDV-SDI_EVO.py --mode full_processing --manifest <MANIFEST.json> --out <base>`. Estado: DOCUMENTED_FACT estático; la verificación empírica queda como PRIMER paso de la futura ejecución autorizada. R-14 actualizado: EVO resuelto por código; **MQR sigue BLOQUEADO** (rama `--manifest` L3767–3768 sin `input()`, PERO `mode = args.mode or _interactive_mode()` L3763 con prompt L3727–3735/L764/L776: sin `--mode` explícito la invocación es interactiva).

**C — Lectura segura del autotest T7 de MQR (TOCTOU).** El diseño anterior sugería "verificación previa de identidad del publicado"; **la observación de Cris es correcta: lstat seguido de apertura por ruta conserva la ventana TOCTOU.** **Solución documentada (RG-FLOW §6b, diseño no implementado):** (1) captura de la identidad ATESTIGUADA por la corrida — hoy `run_experiment` devuelve sólo la ruta (CV-B L2368–2375), por lo que la atestación `(dev,ino)` requiere adaptación futura del lado del autotest (NO amplía G1); (2) UNA sola apertura por ruta del directorio publicado (`O_RDONLY|O_DIRECTORY|O_NOFOLLOW`); (3) `fstat` del descriptor abierto vs identidad atestiguada → identidad distinta = FAIL-CLOSED sin leer; (4) apertura de `analysis.json` RELATIVA al descriptor (`dir_fd=fd_pub`, `O_NOFOLLOW`); (5) verificación del archivo abierto por `fstat` (regular, no-symlink, propiedad; contraste con identidad/hash atestiguada si existe); (6) lectura desde el descriptor verificado, **sin re-resolver la ruta nominal en ningún punto posterior**. **Límites declarados:** la ventana queda ACOTADA por identidad (no eliminada por pre-chequeo); dentro del ciclo = prevención (EA/PDA-1, no activo); T7 = auditoría post-publicación; la misma uid puede alterar DESPUÉS de la verificación (residual post-return, B1); si no hay identidad atestiguada, el contraste degrada a tipo/propiedad (declarado). R-21 añadido; R-08 actualizado. G1 NO se amplía.

## 2. Aspectos que continúan sin resolver

- **R-14-MQR:** confirmación estática completa de la receta no interactiva de MQR (`--manifest` + `--mode` explícito; validaciones previas y spec sha) y verificación empírica de las recetas (H ya verificada; EVO pendiente de ejecución).
- **Atestación de identidad para T7:** la secuencia §6b necesita que la corrida exponga `(dev,ino)` (hoy el retorno es sólo la ruta) — adaptación futura, no autorizada.
- R-11 (señales SIGTERM/SIGKILL), R-12 (matplotlib anclado), R-13 (subdirectorios de 2 niveles por descriptor), R-15 (rendimiento procfs), R-18 (arneses con fileobj-dup), R-05/R-06 (integración de anclajes MQR bifásico y `locals().get` H/EVO) y la ejecución íntegra de RG-FLOW siguen abiertos.

## 3. Flujos habilitados y bloqueados para una futura autorización

| Motor | Estado | Condición |
|---|---|---|
| **Hardened** | FLOW-1..8 **HABILITADOS** | receta `--manifest` verificada empíricamente; pendiente sólo la autorización de Cris |
| **EVO** | FLOW-1..8 **HABILITADOS** | receta demostrada por código (rectificación B); la verificación empírica de la receta es el primer paso obligatorio de la ejecución; corrida EVO real propia |
| **MQR** | **BLOQUEADO** | R-14-MQR: confirmar receta no interactiva; al habilitarse, FLOW-6 MQR sin enunciados G1 (rectificación A) y FLOW-5/6 con la lectura segura §6b (rectificación C) |

## 4. Verificación de sumas

`SHA256SUMS_RECT_DOC_RG_FLOW_6G1.txt` (5/5 OK) — verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_RECT_DOC_RG_FLOW_6G1.txt | sha256sum -c -`

## 5. PARADA OBLIGATORIA

La rectificación documental NO autoriza implementación ni ejecución RG-FLOW. El trabajo se detiene aquí, a la espera de la adjudicación de Cris.

*Fin del informe. Agente en parada.*
