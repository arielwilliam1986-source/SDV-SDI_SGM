# 6G.1 — RECTIFICACIÓN FINAL DE PRECISIÓN G1 Y NOMENCLATURA DEL PLAN HARDENED (SÓLO DISEÑO)

- **Destinatario:** Cris (ChatGPT), auditor y adjudicador.
- **Naturaleza:** **exclusivamente documentación**. No implementar el plan; no ejecutar pruebas ni motores; no audio real; no Android/Termux; no DSP/fórmulas/parámetros; no EVO/MQR; no `main`; sin merge ni cherry-pick; PR #2 intacto. Cero modificaciones de producción.
- **Fecha:** 23-11-2026. **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Commit padre directo (verificado ANTES de trabajar: local = origin = `gh api`):** `84fa356d8261c9be7c4d57783f389898f522bc1b` — CONFORME. Publicado en un **único commit hijo directo de `84fa356`**.
- **Documento rectificado:** `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` v2.2 → **v2.3**. La rectificación anterior de `candidates/` queda **aceptada como base documental, sin reabrir** (sus marcadores [v2.2] de ciclo de vida se conservan intactos).

---

## §1 Corrección A — Nomenclatura G1

Las dos referencias de **alcance G1** que aún usaban el nombre concreto de la línea base fueron corregidas a la forma general coherente con P-05:

| Ubicación | Antes | Después |
|---|---|---|
| §4 (tabla de arquitectura adjudicada, fila G1) | «comparación SHA-256 **sólo** `analysis.json` y `mix_sintetico SDV.wav`» | «comparación SHA-256 **sólo** `analysis.json` y `<track_base> SDV.wav` (en la línea base: `mix_sintetico SDV.wav`)» |
| §10 (limitaciones del modelo de amenazas) | «El hash G1 cubre sólo `analysis.json` + `mix_sintetico SDV.wav` (sin ampliación)» | «El hash G1 cubre sólo `analysis.json` + `<track_base> SDV.wav` (en la línea base: `mix_sintetico SDV.wav`; sin ampliación)» |

**Revisión de TODAS las apariciones del documento** (grep completo): quedan 4 menciones de `mix_sintetico`, todas **contextuales y no contradictorias** — (1) paréntesis de trazabilidad en §4, (2) nota de fixtures en la base real de §8ter («para los fixtures de la línea base = `mix_sintetico`»), (3) paréntesis de trazabilidad en §10, (4) nota histórica de la consolidación en §11. Cero sentencias de alcance con el nombre antiguo (verificadas por patrón: 0 resultados). **No se amplió el alcance G1 ni se cambió su significado técnico**: el alcance sigue siendo exactamente dos artefactos; sólo se expresa con el nombre dinámico general (`track_base`, H L1649), del que el nombre de la línea base es instancia.

## §2 Corrección B — Precisión de la garantía del hash (P-05 [v2.3])

**Afirmación incorrecta corregida:** el mecanismo [v2.2] decía «(i) el escritor ya está cerrado (paso 2) — **el contenido hash-eado es el final**», lo que implicaba que cerrar nuestro escritor garantiza inmutabilidad del contenido. Eso **no es demostrable** y queda eliminado. La distinción exacta (P-05 [v2.3], «Distinción exacta — qué garantiza y qué NO»):

1. **Cierre del escritor propio** (paso 2 de P-08): nuestro proceso ya no escribirá ese inodo por su descriptor — **NO implica que el contenido quede inmutable**.
2. **Identidad del inode** acreditada por `fstat(fd_h)` contra el registro propio (P-07) — identidad ≠ contenido.
3. **Lectura del contenido** mediante el descriptor `fd_h` — los bytes hash-eados son los que `fd_h` entrega durante la lectura.
4. **Posibilidad residual de modificación concurrente por otro proceso del mismo UID**, declarada expresamente: un same-UID puede modificar el inodo (por cualquier enlace válido o vía procfs) antes o durante la lectura.

**Declaración central:** «**El hash representa los bytes OBSERVADOS durante su lectura: NO constituye por sí mismo una garantía de inmutabilidad ni de integridad frente a un atacante same-UID.**» Se precisó además que la condición procfs «cero descriptores de escritura abiertos» cubre los descriptores **propios** de la corrida, no los de terceros. El modelo de amenazas (§10) incorpora la misma precisión; **no se modificó el modelo ni se presentó garantía superior a lo demostrable**.

## §3 Corrección C — Relación entre gate-1 y gate-2 (declaración expresa, sin garantía nueva)

Documentado en P-05 [v2.3] («Relación gate-1/gate-2 con los hashes») y reflejado en el diagrama §7 (bloque HASH G1) y §11:

- **¿Se comparan los hashes de ambas compuertas?** **NO** — no existe comparación en el diseño; cada hash es una **huella registrada** independiente, **no una comprobación de estabilidad de contenido entre compuertas**.
- **¿Qué registro conserva cada resultado?** El veredicto de cada compuerta (con los dos hashes y su fase) se conserva **en memoria** para la decisión y se refleja en la **salida estándar directa** (el `engine_log` está cerrado desde el paso 2 — R-32); si la compuerta falla, los hashes observados van en el `detalle` de `CONJUNTO_PUBLICABLE_NO_VALIDO` → **`ABORT_6G1.json`** (persistente). Ningún artefacto de una corrida EXIT_OK persiste las huellas (límite R-32 sin cambios).
- **¿Una diferencia provoca rechazo y aborto?** **NO** — una diferencia de hash entre gate-1 y gate-2 no provoca rechazo ni aborto (no hay tal comparación).
- Lo que gate-2 **sí** re-verifica: tipos, obligatoriedad, entradas inesperadas e **identidad** (P-07) — estabilidad de identidad, no de contenido.
- **Sin inventar garantía nueva ni cambio silencioso de comportamiento:** una comparación futura de hashes entre compuertas (o la persistencia de huellas en artefacto) sería un comportamiento nuevo y **exige adjudicación expresa de Cris**.

## §4 Trazabilidad

- Documentos afectados (sólo éstos): `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` — cabecera (título v2.3 + historial), §4 fila G1, P-05 marcador y sub-puntos [v2.3] (mecanismo con distinción exacta + relación gate-1/gate-2), P-08 paso (4) y §8 pasos 1/4 (referencias al mecanismo [v2.3]), §7 bloque HASH G1, §10 limitaciones, §11 PROPUESTO, línea final («— Fin del plan v2.3 (precisión G1 y nomenclatura sobre v2.2)»). Los marcadores [v2.2] del ciclo de vida `candidates/` **no se tocaron** (base aceptada). Los informes históricos (rectificación A–D, consolidación, rectificación de coherencia) permanecen **congelados en sus commits** como entrega de su momento; el plan v2.3 es el documento de registro vigente y prevalece.
- `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` regenerado (5 documentos) y verificado contra los publicados.
- `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` regenerado (schema `plan-integracion-hardened-flow14/5`).

## §5 Registro de publicación

- **Commit padre directo:** `84fa356d8261c9be7c4d57783f389898f522bc1b` (verificado local = origin = `gh api` ANTES de trabajar).
- **Commit de esta rectificación:** el SHA completo se declara en el informe de entrega a Cris y es verificable vía `git`/`gh api` (un commit no puede contener su propio hash).
- **Archivos de este commit (5; nada de producción):** `RECTIFICACION_FINAL_G1_NOMENCLATURA_PLAN_HARDENED_FLOW1_4_6G1.md` (A), `PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.md` (M), `MANIFEST_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.json` (M), `SHA256SUMS_PLAN_INTEGRACION_HARDENED_FLOW1_4_6G1.txt` (M).
- **Evidencia de cero modificaciones de producción:** verificación `gh api` del commit — 0 archivos bajo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/`; `git status` limpio tras el commit.

## §6 Parada

Publicados el informe, el plan v2.3, el manifiesto (schema /5) y los SHA256SUMS. **No se implementó nada. Parada obligatoria** a la espera de la adjudicación de Cris.
