# 6G.1 — ÚLTIMA RECTIFICACIÓN DE COHERENCIA DEL PLAN HARDENED v2.1 (SÓLO DISEÑO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **corrección documental puntual**. No autoriza implementar el plan. Cero modificaciones de motores o producción; cero ejecución de motores o pruebas adicionales; cero audio real; cero Android/Termux; cero EVO/MQR; cero cambios en `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Fecha:** 23-11-2026. **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Commit padre obligatorio (verificado ANTES de trabajar: local = origin = `gh api`):** `fc399ece21d59bfe598c3c4058f59ced999f31bd` — CONFORME. Este informe se publica en un **commit hijo directo de `fc399ec`**.
- **Documento rectificado:** `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` v2.1 → **v2.2**. Las decisiones A–D y la matriz §8ter **quedan aceptadas como base de diseño y NO se reabren** — esta rectificación sólo completa el ciclo de vida de `candidates/`, resuelve la contradicción del hash por descriptor tras el cierre y ejecuta la limpieza documental.

---

## §1 Corrección 1 — Ciclo de vida completo de `candidates/` (P-08 + P-09 + §7 unificados)

Antes de la rectificación, `fd_candidates`/`fd_cand_<grupo>` aparecían en P-08/P-09 (retención y cierre) pero **sin bloque de creación en el diagrama §7 y con un orden de cierre incompleto**. Corregido:

| Elemento exigido | Dónde queda resuelto |
|---|---|
| Creación de `candidates/` mediante `mkdir` relativo a `fd_run` | P-09 [v2.2] («Creación de `candidates/`») + diagrama §7 bloque `fd_cand` |
| Apertura y acreditación de `fd_candidates` | P-09 [v2.2]: `os.open("candidates", O_RDONLY\|O_DIRECTORY\|O_NOFOLLOW, dir_fd=fd_run)` → `fstat` → `I_candidates` + diagrama §7 |
| Creación y apertura componente a componente de cada `candidates/<grupo>/` | P-09 [v2.2]: `os.mkdir("<grupo>", 0o700, dir_fd=fd_candidates)` por grupo + diagrama §7 |
| Acreditación de cada `fd_cand_<grupo>` | P-09 [v2.2]: `os.open("<grupo>", O_DIRECTORY\|O_NOFOLLOW, dir_fd=fd_candidates)` → `fstat` → `I_cand_<grupo>` + diagrama §7 |
| Retención de todos los descriptores durante las dos compuertas | P-09 [v2.2] («Todos los subanclas se RETIENEN durante las dos compuertas») + P-08 paso (3) + diagrama §7 (ANCLA incluye `fd_candidates*`, `fd_cand_<grupo>*`) |
| Descenso por descriptores acreditados en gate-1 y gate-2 | P-08 pasos (4) y (6) (`+cada fd_cand_<grupo>`); P-05 (subanclas en ambas fases); §8 pasos 1 y 4; diagrama §7 |
| Cierre de TODOS los `fd_cand_<grupo>` antes de `fd_candidates` en el paso 7 | P-08 paso (7): «**todos los `fd_cand_<grupo>`** → `fd_candidates` → `fd_pub` → `fd_run` → `fd_padre`»; P-09 [v2.2] idéntico; diagrama §7 paso (7) idéntico |
| WAVs de grupo (fd-passthrough) | Diagrama §7 bloque `fd_WavG` (nuevo): `openat(fd_cand_<grupo>, O_CREAT\|O_EXCL\|O_NOFOLLOW)` → `sf.SoundFile(fd, closefd=False)` |
| Bloque ABORTO coherente | Diagrama §7: inventario «desde `fd_run`/`fd_masks`/`fd_cand_*` vivos (sin rutas)» |
| R-13 | Permanece **DESCONOCIDO** respecto de la validación empírica del descenso de dos niveles (P-09 nota final y §8ter nota 3, sin cambios de estado) |

**Verificación de no-desaparición:** ningún descriptor mencionado en P-08/P-09 (`fd_padre`, `fd_run`, `fd_masks`, `fd_candidates`, `fd_cand_<grupo>`, `fd_pub`, `fd_mm`, `fd_h`, `fd_log`, escritores WAV, lectores) carece ahora de bloque en el diagrama §7 y de posición en el orden de cierre.

## §2 Corrección 2 — Mecanismo exacto del hash por descriptor tras el cierre (resuelve la contradicción P-05 vs P-08/P-09)

**Contradicción detectada (real):** P-05 exigía SHA-256 «vía descriptor» para `analysis.json` y `<track_base> SDV.wav`, mientras P-08/P-09 cierran los descriptores de **escritura** antes de gate-1 — la compuerta no podía usar los fds de escritura y el mecanismo no estaba especificado.

**Resolución (P-05 [v2.2], sub-sección «Mecanismo EXACTO del hash G1 por descriptor tras el cierre»):** **reapertura en lectura**, no retención de descriptores de lectura extra:

1. `fd_h = os.open(nombre, O_RDONLY | O_NOFOLLOW, dir_fd=<fd acreditado de la fase>)` — componente único sobre `fd_run` (gate-1) o `fd_pub` (gate-2); **nunca por ruta nominal**.
2. `os.fstat(fd_h)` debe igualar la identidad `(dev,ino)` del **registro propio por identidad** (P-07); desigualdad → RECHAZO (`CONJUNTO_PUBLICABLE_NO_VALIDO`).
3. El SHA-256 se calcula leyendo **exclusivamente de `fd_h`**.
4. `os.close(fd_h)` **inmediatamente después de cada hash** — punto de cierre inequívoco: dentro de la propia compuerta, uno por archivo; ningún `fd_h` sobrevive a la compuerta.

**Garantías exigidas, verificadas por el diseño:**
- El escritor ya está cerrado (paso 2 de P-08 precede a gate-1) → el contenido hash-eado es el final.
- El descriptor usado para el hash corresponde al inode registrado (`fstat` contra el registro propio; desigualdad ⇒ rechazo).
- No se reabre por ruta nominal (`openat` + `O_NOFOLLOW` sobre dirfd acreditado).
- No quedan descriptores de escritura abiertos durante las compuertas (condición procfs de la propia compuerta P-05).
- Los descriptores de lectura se cierran en un punto inequívoco (dentro de la compuerta, tras cada hash).

Diagrama §7: bloque HASH G1 [v2.2] añadido al paso (4); §8 pasos 1 y 4 citan el mecanismo (gate-2 usa `fd_pub` como dirfd). **Sin afirmación de integridad de contenido más allá del alcance G1 adjudicado** (`analysis.json` + `<track_base> SDV.wav`; «LECTURA ANCLADA», nunca «contenido íntegro» — T7).

## §3 Corrección 3 — Limpieza documental y comprobación de no-contradicción

- «Fin del plan v2» → «— Fin del plan v2.2 (rectificada de coherencia sobre v2.1)».
- §11: lista PROPUESTO actualizada — «riesgos **R-23..R-35**» y «arnés de regresión ampliado (**15 casos**: 11 + REG-M-a..d)»; se añaden explícitamente el ciclo de vida de `candidates/` y el mecanismo del hash G1 [v2.2].
- **Comprobación de no-contradicción P-08/P-09/§7/§11** (realizada tras la edición): el orden de cierre es idéntico en las tres fuentes (`fd_cand_<grupo>` TODOS → `fd_candidates` → `fd_pub` → `fd_run` → `fd_padre`); `fd_masks` cierra en 5bis en las tres; la retención durante ambas compuertas es idéntica; el hash G1 aparece con el mismo mecanismo en P-05, P-08 (4), §7 (4) y §8 (1/4); R-13 consta como DESCONOCIDO en P-09 y §8ter; R-35 consta en §10 y §11. Sin contradicciones pendientes.

## §4 Trazabilidad

- Documentos afectados y modificados (sólo éstos): `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (cabecera v2.2 + historial; P-05 [v2.2] con mecanismo del hash; P-08 pasos (3)/(4)/(6)/(7) y marcador v2.2; P-09 [v2.2] completo; §7 diagrama — bloque `fd_cand`, bloque `fd_WavG`, ANCLA, paso (4) HASH G1, paso (6), paso (7), bloque ABORTO; §8 pasos 1 y 4; §11 PROPUESTO; §12; línea final). El informe de consolidación y el de rectificación A–D **no se tocaron**.
- `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` regenerado sobre los documentos publicados exactos.
- `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` regenerado (schema `plan-integracion-hardened-flow14/4`) y verificado contra los documentos publicados.

## §5 Registro de publicación

- **Commit padre directo:** `fc399ece21d59bfe598c3c4058f59ced999f31bd` (verificado local = origin = `gh api` ANTES de trabajar).
- **Commit de esta rectificación:** el hash exacto se declara en el informe de entrega a Cris y es verificable vía `git`/`gh api` (un commit no puede contener su propio hash).
- **Archivos de este commit (4; nada de producción):** `RECTIFICACION_COHERENCIA_PLAN_HARDENED_FLOW1_4_6G1.md` (A), `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (M), `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` (M), `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` (M).
- **Evidencia de cero modificaciones de producción:** verificación `gh api` del commit — 0 archivos bajo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/`; `git status` limpio tras el commit.
- **Manifiesto:** schema /4 con hashes de los 3 documentos y del SHA256SUMS.

## §6 Parada

Publicados el informe, el plan v2.2, el manifiesto (schema /4) y los SHA256SUMS. **No se implementa nada. Parada obligatoria** a la espera de la adjudicación de Cris.
