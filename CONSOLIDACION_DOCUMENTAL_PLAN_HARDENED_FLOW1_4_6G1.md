# 6G.1 — CONSOLIDACIÓN DOCUMENTAL FINAL DEL PLAN HARDENED FLOW-1..4 (SÓLO DISEÑO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **exclusivamente diseño y documentación**. No autoriza implementar el plan («La implementación requerirá una adjudicación y autorización separadas de Cris»). Cero modificaciones de producción; cero ejecución de motores; cero pruebas adicionales; cero audio real; cero Android/Termux; cero EVO/MQR; cero cambios en `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Fecha:** 23-11-2026. **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Commit padre obligatorio (verificado ANTES de trabajar: local = origin = `gh api`):** `d7ed220c2c6a1680ece978afaaf242e0a132b965` — CONFORME. Este informe y la documentación consolidada se publican en un **commit hijo directo de `d7ed220`**.
- **Documento consolidado:** `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` v2 → **v2.1**. Las rectificaciones A–D **quedan aceptadas como base arquitectónica y NO se reabren ni alteran**; la consolidación sólo resuelve contradicciones reales, señaladas expresamente (mandato §1 de la adjudicación).

---

## §1 Corrección 1 — Matriz de obligatoriedad por modo (resuelve la contradicción P-05 vs matriz FLOW-1 sobre `masks/`)

**Contradicción detectada (real, señalada expresamente):** el plan v2 exigía en P-05 «`masks/` acreditado con sus 6 npy» en la compuerta (obligatorio) y simultáneamente clasificaba `masks/` como opcional en la matriz FLOW-1. Además, la inspección del código vigente demostró que ambas clasificaciones eran incorrectas:

- `write_masks = opt.png or opt.keep_masks` (H L1625): los 6 npy **sólo** se crean con `--png` o `--keep-masks`.
- `masks/` (directorio) se crea **SIEMPRE** en el provisional (H L1616), con o sin npy.
- `masks/` se elimina del publicado **SIEMPRE**, con o sin `--keep-masks` (H L1988–1997).

**Resolución (nueva §8ter del plan): matriz de obligatoriedad determinista por (fase, flags)**, con clasificación única por entrada — OB / OB-C (obligatorio condicionado a flags; si no, PROHIBIDO) / PROH — **sin clasificación dual**:

| Aspecto exigido | Resolución |
|---|---|
| Obligatorios por modo | Modo `full_processing` (alcance autorizado): SIEMPRE OB en provisional y publicado: `analysis.json`, `analysis.txt`, `engine_log.txt`, `input_integrity_6g.json`, `<track_base> SDV.wav`, `<track_base> SDI.wav`. Los modos `analysis_only`/`dry_run`/`single_pair` quedan FUERA de la matriz (sin cobertura empírica; BD). |
| Opcionales por modo | No existen «opcionales» discrecionales: toda entrada condicionada es **OB-C** (determinística por flags). |
| `masks/` | OB en provisional (siempre creada, H L1616) / **PROH en publicado** (eliminada en 5bis; presencia ⇒ rechazo). Nunca dual. |
| `masks/*.npy` (6) | OB-C: OB si (`--png` ∨ `--keep-masks`); si no, `masks/` debe estar VACÍA (0 entradas). |
| Archivos permitidos con `--write-all-candidates` | Estructura EXACTA: `candidates/individual_<pair_id>/` con `<track_base> SDV.wav`+`SDI.wav` y `candidates/consensus_<method>/` con `<method> SDV.wav`+`SDI.wav` (métodos no-default escritores); sin el flag, `candidates/` es PROH. **Corrección documental adicional:** v2 declaraba «`candidates/` NO existe en Hardened» — INCORRECTO: con este flag se crean subdirectorios de dos niveles (H L1652–1671); la cadena acreditada se extiende `fd_run → fd_candidates → fd_cand_<grupo>` y el descenso de dos niveles queda etiquetado R-13 (validación empírica pendiente, UNKNOWN). |
| Tratamiento de `--png` | OB-C compuesto: `png/` con EXACTAMENTE 2 PNGs (`Mapa_de_Confianza_Espectral.png`, `Mapa_de_Desacuerdo_Inter_Modelo.png`) si `--png` ∧ MATPLOTLIB_OK (H L1919–1920, L2203); PROH si la condición efectiva no se cumple (runtime-determinista; R-12 sin cambios). |
| Entradas inesperadas | PROH → RECHAZO (fail-closed) en ambas compuertas: archivos extra, symlinks, dispositivos, subdirectorios no previstos, entradas adicionales dentro de `masks/`, `png/` o `candidates/<grupo>/`. |
| Momento y condiciones de eliminación de `masks/` | Paso **5bis** del ciclo de vida: tras el rename y la acreditación `fstat(fd_pub)==I_run`, ANTES de la compuerta-2, por descriptores (`unlinkat` vía `fd_masks` + `os.rmdir("masks", dir_fd=fd_pub)`); migración del `rmtree` por ruta (R-28). **Fallo ⇒ `masks/` presente en gate-2 ⇒ RECHAZO ⇒ sin EXIT_OK** — cambio semántico WARN→fail-closed respecto del vigente (H L1992–1997), señalado expresamente como consecuencia determinista de la lista de aceptación; decisión PROPUESTA para adjudicación. |
| Corrección adicional de nombres | Los WAV raíz obligatorios son **dinámicos**: `<track_base> SDV.wav|SDI.wav` con `track_base = basename(mix) sin extensión` (H L1649) — v2 los fijaba erróneamente como constantes `mix_sintetico`; el alcance G1 se re-expresa como `analysis.json` + `<track_base> SDV.wav` (equivalente al adjudicado para los fixtures de la línea base), sin ampliación. |

La compuerta (P-05 v2.1) consume **L_acept = f(modo, flags efectivos, track_base)** — lista de aceptación determinista, con listas distintas para gate-1 (provisional) y gate-2 (publicado). Riesgo nuevo **R-35** (deriva lista vs flags) con mitigación por derivación programática y regresión REG-M-a..d.

## §2 Corrección 2 — Ciclo de vida único de descriptores (unifica P-08 + P-09 + §7)

Secuencia única y sin contradicciones (P-08 v2.1; diagrama §7 actualizado; P-09 alineado):

| Pregunta exigida | Respuesta única |
|---|---|
| Descriptores abiertos durante AMBAS compuertas | `fd_run` y `fd_padre` (siempre); `fd_pub` (desde el paso 5); `fd_candidates`/`fd_cand_<grupo>` si `--write-all-candidates` (candidates/ se publica y gate-2 lo desciende). `fd_masks` está abierto en gate-1 y **ya cerrado** en gate-2 (masks/ es PROH en publicado; gate-2 no lo necesita). |
| Cuándo se cierra `fd_masks` | Paso **5bis**, tras eliminar `masks/` del publicado (su última operación requerida). NO se cierra en el paso 2 (la compuerta-1 lo requiere para el descenso). |
| Cuándo se cierra `fd_pub` | Paso **7**, primero del cierre del anclaje. |
| Cuándo se cierran `fd_run` y `fd_padre` | Paso **7** (`fd_run` antes que `fd_padre`; `fd_padre` el último). |
| Recursos vivos hasta cada mapeo/biblioteca | Escritores WAV hasta `sf_close` (paso 2); memmaps + mmap hasta `flush`+`mmap.close` con su `fd_mm` retenido mientras el mapeo vive (cerrado tras el mmap, paso 2); `Tee` hasta `close()` (paso 2, contrato R-17); subanclas según la tabla anterior. Nunca cerrar un fd del que depende un recurso vivo (procfs-magic, mmap). |
| Errores de cierre | Cualquier error ⇒ `CierreNoAcreditado6G1` ⇒ protocolo de aborto (P-02) con rc≠0: jamás compuerta, jamás publicación, jamás EXIT_OK. |
| Aborto | Secuencia vigente: cierre determinista → ABORT vía descriptor (`fd_run`; inventario por descriptor; subanclas vivas o re-apertura por componente único acreditado) → traslado opcional por ancla; descriptor muerto ⇒ `abort_registrado=False` + rc≠0 (R-23). |
| Escrituras post-compuerta-2 | **Prohibidas** (escrituras ordinarias Y mutaciones del conjunto). Única excepción: `ABORT_6G1.json` vía `fd_pub`/`fd_run` si la compuerta final falla + rc≠0. |

## §3 Corrección 3 — Trazabilidad

- Documentos actualizados (única y exclusivamente los afectados): `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (cabecera v2.1 + historial; P-05; P-08; P-09; §6 FLOW-1 filas «Funciones que cambian», «Obligatorios / opcionales» y «Riesgos residuales»; §7 diagrama; §8 paso 3bis; **nueva §8ter**; §9 casos REG-M-a/b/c/d; §10 R-28 actualizado + R-35 nuevo; §11 contradicciones señaladas; §12 nota de regeneración). El informe de rectificación A–D NO se tocó (A–D aceptados, sin reabrir).
- `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` regenerado sobre los documentos publicados exactos.
- `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` regenerado (schema `plan-integracion-hardened-flow14/3`) y **verificado contra los documentos publicados**: cada hash corresponde al contenido exacto publicado en este commit (comprobación realizada en el momento de la generación, tras la última edición de cada documento).

## §4 Identificadores exactos y archivos (se completan con los valores reales al publicar)

- **Commit padre directo:** `d7ed220c2c6a1680ece978afaaf242e0a132b965`.
- **Commit de esta consolidación:** ver §6 (hash real publicado).
- **Archivos modificados/añadidos en este commit:** ver §6 (lista real del commit).
- **Manifiesto:** `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` (schema /3; hash del propio informe incluido).
- **SHA256SUMS:** `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt`.

## §5 Clasificación epistémica de la consolidación

- **DEMOSTRADO:** condiciones reales de artefactos citadas (H L1625, L1616, L1919–1920, L1988–1997, L1652–1671, L1649, L140) — inspección estática sin ejecución.
- **PROPUESTO:** matriz §8ter completa; paso 5bis y su semántica fail-closed; ciclo de vida unificado; casos REG-M-a..d; R-35; migración R-28.
- **Sin cambios:** decisiones A–D (aceptadas); línea base adjudicada; restricciones.
- **DESCONOCIDO:** modos fuera de `full_processing`; descenso de dos niveles con `--write-all-candidates` (R-13); todo lo listado en §11 del plan.

## §6 Registro de publicación

- **Commit padre directo:** `d7ed220c2c6a1680ece978afaaf242e0a132b965` (verificado local = origin = `gh api` ANTES de trabajar).
- **Commit de esta consolidación:** el hash exacto se declara en el informe de entrega a Cris y es verificable vía `git`/`gh api` (un commit no puede contener su propio hash; el manifiesto registra el padre y los hashes de los documentos publicados).
- **Archivos de este commit (4; nada de producción):** `CONSOLIDACION_DOCUMENTAL_PLAN_HARDENED_FLOW1_4_6G1.md` (A), `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (M), `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` (M), `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` (M).
- **Manifiesto:** schema `plan-integracion-hardened-flow14/3`, con hashes SHA-256 de los 3 documentos y del SHA256SUMS.
- **Verificación remota:** push a `origin/arena/f1c5739f-sdv-sdi-sgm` + comprobación `gh api` del commit (padre, archivos y cero cambios en `motores/`).

## §7 Parada

Publicados el informe, el plan v2.1 consolidado, el manifiesto (schema /3) y los SHA256SUMS. **No se implementa nada. Parada obligatoria** a la espera de la adjudicación de Cris.
