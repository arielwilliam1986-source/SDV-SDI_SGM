# COMPLEMENTO DOCUMENTAL DE ADJUDICACIÓN — AUDITORÍA MOTOR HARDENED / PLAN v2.3 (6G.1) — v1

- **Destinatario:** Cris (ChatGPT), responsable técnica y adjudicadora. **Ejecutor:** Arena.
- **Informe base:** `INFORME_AUDITORIA_ESTATICA_CORRESPONDENCIA_MOTOR_PLAN_6G1.md` (commit `2438559092c1970b99c069987cc30dad9ab0d689`, hijo de `ef90a45…`). Este complemento queda **claramente vinculado** a ese informe: incorpora DOS decisiones de adjudicación (A y B), establece el esquema de 4 etiquetas epistémicas y NO reescribe ni oculta ninguna sección del informe base.
- **Naturaleza:** rectificación **documental exclusivamente**. Sin implementación, sin modificación de fuentes, sin pruebas, sin ejecución.

## 1. Identidades Git

- **Padre directo obligatorio verificado ANTES de trabajar:** `2438559092c1970b99c069987cc30dad9ab0d689` — local = origin = `gh api` CONFORME; árbol limpio.
- **Informe base (referencia):** SHA256 `a32b40cc5be87db0d8ff81018d01d1e0397549284227d4b6543175b3135d8eb4` en su commit de publicación.
- **Archivos de producción citados:** los mismos del informe base (motor H, `lectura_segura_6g1.py`, plan v2.3) — sin cambios respecto de los SHA256 registrados en §1 del informe base (no se han modificado; verificable por `gh api`: ningún commit posterior a `2438559…` ha tocado producción).

## 2. Esquema epistémico vigente (a partir de este complemento)

Toda afirmación de este complemento y de los futuros documentos de la fase de preintegración usa UNA de estas etiquetas:

| Etiqueta | Significado |
|---|---|
| **DOCUMENTED_FACT** | Comportamiento comprobable en el código vigente (con archivo y línea). |
| **ADJUDICACIÓN** | Decisión expresa de Cris que vincula el trabajo futuro (no es observación de código ni diseño previo del plan). |
| **PROPOSED** | Mecanismo futuro previsto, todavía NO implementado. |
| **UNKNOWN** | Sin evidencia actual; no resuelto o no verificable estáticamente. |

El informe base usaba tres etiquetas (DOCUMENTED_FACT/PROPOSED/UNKNOWN) y registró en su §8.9 la brecha de las guías como «punto que requiere decisión». Este complemento introduce la etiqueta **ADJUDICACIÓN** y RESUELVE esa decisión sin reescribir el informe base (véase §5).

## 3. DECISIÓN A — Alcance de modos: `full_processing` exclusivamente

**Base real (DOCUMENTED_FACT, motor H sin modificar):**
- `MODE_SINGLE_PAIR = "single_pair"` (H L139) y `REQUIRED_MODES = (full_processing, analysis_only, dry_run, single_pair)` (H L140).
- `full_mode = (mode == MODE_FULL_PROCESSING or mode == MODE_SINGLE_PAIR)` (H **L1622**): en el motor vigente, `single_pair` recorre LA MISMA ruta de escritura que `full_processing` (writers WAV, `candidates/`, post_wav, reports) — de ahí el riesgo colateral documentado abajo.
- El plan v2.3 ya excluye los otros modos de la matriz: §8ter («Los modos `analysis_only`, `dry_run` y `single_pair` quedan FUERA de la matriz», plan L279) — pero el plan no explicitaba el alcance de P-01..P-09 respecto de `single_pair`.

**ADJUDICACIÓN (Cris, vinculante):**
1. **P-01..P-09 y FLOW-1..4 se autorizan exclusivamente para `full_processing`.**
2. **`single_pair` queda fuera de esta integración.**
3. **No se deben extender automáticamente las compuertas (P-05) ni la matriz de obligatoriedad (§8ter) a `single_pair`.**
4. **La futura adaptación de funciones compartidas debe preservar el comportamiento de `single_pair` y evitar efectos colaterales** (ver nota de riesgo).
5. **Cualquier ampliación de alcance requerirá adjudicación expresa de Cris.**

**Nota de riesgo colateral (DOCUMENTED_FACT → UNKNOWN):** por H L1622, las funciones que P-01..P-09 adapta — `CandidateRunner.__init__` (H L1396-1399), `_open_memmap` (H L1456), `Tee`/`init_tee` (H L173/215), `create_run_dir` (H L1430), `post_wav_identity` (H L1461), bloque `input_integrity` (H L1957-1965) — son **compartidas por `full_processing` y `single_pair`** (ambos modos activan `full_mode=True`). Toda modificación de esas funciones con vistas a P-01..P-09 afecta estructuralmente también a `single_pair`; la exigencia de preservación (ADJUDICACIÓN A.4) es, por tanto, un requisito de diseño futuro (PROPOSED). El MÉTODO de verificación de esa preservación (regresión comparativa de `single_pair` pre/post-integración) **no está definido ni autorizado** en esta fase — UNKNOWN hasta nueva adjudicación.

**Efecto sobre el informe base:** la matriz de correspondencia §3 del informe base queda delimitada por esta adjudicación a `full_processing`; sus filas no se reescriben.

## 4. DECISIÓN B — Continuidad de identidad de las guías (subrequisito SR-EI-1)

### 4.1 Secuencia actual (DOCUMENTED_FACT, motor H sin modificar)

1. **Validación inicial por descriptor:** `probe_file(path, role)` abre UNA vez `os.open(path, O_RDONLY|O_NONBLOCK)` (H L372), exige archivo regular (L379-382) y conserva identidad: `info.device, info.inode = st0.st_dev, st0.st_ino` (H **L383**); el SHA estable se calcula por ese descriptor (L404) y la estabilidad se verifica con fstat final (L411-418).
2. **Las guías pasan por ese probe:** `p.vocal = validate_guide(probe_file(p.vocal_path, "vocal_guide"))` y `p.instrumental = validate_guide(probe_file(p.instrumental_path, "instrumental_guide"))` (H **L1522-1523**); `PairMeta.vocal/.instrumental` son `FileInfo` (H L468-469); `validate_guide` (H L442-452) sólo valida extensión/sample-rate/canales y **NO altera ni anula** `device`/`inode` del FileInfo.
3. **Reapertura por ruta para el DSP:** `handles[(p.pair_id,"vocal")] = sf.SoundFile(p.vocal.path)` y `handles[(p.pair_id,"instrumental")] = sf.SoundFile(p.instrumental.path)` (H **L1697-1698**); soundfile abre SU PROPIO descriptor resolviendo la ruta nominal; los handles viven durante todo el DSP y se cierran en H L1878.
4. **Conclusión (DOCUMENTED_FACT):** entre la validación (L1522-1523) y la reapertura (L1697-1698) **no existe ninguna comparación de `(st_dev, st_ino)` contra el FileInfo**: la reapertura por ruta **no acredita que el objeto utilizado durante el DSP sea el mismo que fue validado** (exactamente la brecha registrada como §8.9 del informe base). El mecanismo correctivo ya existe para el MIX — `abrir_mix`/`MixHandle` exige `identidad_esperada` y rechaza por fstat (LS L152-158) — pero NO se aplica a las guías.

### 4.2 ADJUDICACIÓN (Cris, vinculante)

**La futura integración debe exigir continuidad de identidad entre la validación inicial y el lector utilizado durante el DSP:**
1. **Reapertura controlada** del objeto de guía.
2. **`fstat` del descriptor abierto.**
3. **Comparación de `(dev, ino)`** contra la identidad conservada en `FileInfo`.
4. **Rechazo fail-closed** si no coincide o no puede acreditarse.
5. **Entrega del mismo descriptor a soundfile**, sin volver a resolver la ruta nominal para abrir el objeto utilizado.

**Designación documental:** esta exigencia queda registrada como **subrequisito SR-EI-1 («continuidad de identidad de entradas»)**, **relacionado con P-04 pero diferenciado de sus lecturas post-escritura** (P-04a pread `input_integrity`, P-04c post_wav, P-04d engine_log, P-04e analysis.txt). Estado: **PROPOSED** — no implementado. **El plan v2.3 NO se modifica** (esta designación vive exclusivamente en este complemento y en los futuros documentos que lo citen) y **no se afirma que este requisito ya esté integrado**: en el código vigente la reapertura de guías es por ruta sin verificación (§4.1.4, DOCUMENTED_FACT).

**Coherencia técnica (DOCUMENTED_FACT):** el patrón exigido (apertura segura → fstat → comparación con identidad esperada → entrega del fd a la biblioteca) es el MISMO que ya aplica el motor al Mix vía `abrir_mix(mix_info.path, mix_info.sha256, identidad_esperada=(mix_info.device, mix_info.inode))` (H L1687) con `MixHandle` (LS L142/L152-158/L177). SR-EI-1 extendería ese patrón a las guías; la forma exacta de integración (firma, momento, tratamiento del fallo dentro del protocolo de aborto) es decisión de diseño futura — PROPOSED, no definida aquí.

## 5. Efectos sobre el informe base (vínculo, sin reescritura)

| Sección del informe base | Efecto de este complemento |
|---|---|
| §8.9 (handles de guías «requiere decisión») | **RESUELTA por ADJUDICACIÓN B** (SR-EI-1). La brecha descrita allí sigue siendo DOCUMENTED_FACT vigente; la decisión sobre su tratamiento queda registrada aquí. |
| §8 puntos 1-12 (riesgos) | Se añade el riesgo colateral de modos compartidos (§3 de este complemento, ADJUDICACIÓN A.4 + UNKNOWN del método de verificación). |
| §3 (matriz P-01..P-09) | Delimitada expresamente a `full_processing` (ADJUDICACIÓN A.1-A.3). |
| §9 (orden técnico recomendado) | Nota: SR-EI-1 se ejecutaría junto con P-03/P-04 (apertura de guías por descriptor) en la futura implementación — indicación documental, sin reordenar el §9 original. |
| §10 (NO demostrado/UNKNOWN) | El punto «asignación de las guías a un P-xx» pasa de UNKNOWN a **ADJUDICADA** (SR-EI-1; PROPOSED su implementación). |
| Esquema de etiquetas | 3 etiquetas → **4 etiquetas** (§2 de este complemento). |

## 6. Restricciones reafirmadas

No se modifica `motores/` ni `lectura_segura_6g1.py`; no se modifica el plan v2.3; no se ejecuta ni importa producción; no se ejecutan arneses, pruebas ni fixtures; sin audio real ni Android/Termux; sin tocar DSP, fórmulas, parámetros ni máscaras; sin intervenir EVO/MQR, FLOW-5..8, `main` ni PR #2; sin merge, cherry-pick ni integración. Este complemento es exclusivamente documental.

## 7. Declaración expresa y parada

Este complemento incorpora las dos decisiones de adjudicación de Cris (alcance de modos; continuidad de identidad de guías como SR-EI-1) y el esquema de 4 etiquetas epistémicas. **Nada queda integrado por este documento**: SR-EI-1 es PROPOSED; la delimitación a `full_processing` es una regla de alcance, no un cambio de código. El informe base no se reescribe; la trazabilidad completa queda en el historial Git. Parada obligatoria: publicado y detenido — no se continúa con ninguna implementación hasta nueva adjudicación de Cris.

— Fin del complemento documental de adjudicación.
