# INDICE_PARA_REVISOR.md

**Guía de lectura y verificación de esta entrega.** Escrita para que un tercero (humano o
sistema) pueda auditar el paquete sin acceso al entorno donde se produjo.

- Paquete: `SDV-SDI_FASE_1B_ENTREGA.zip`
- Fase: **1B — sintética** (consensos, alineación, `mix_delta`/SDI_F2, orquestador)
- Fuente auditada: `Proyecto SDV-SDI_SGM.zip`
  (SHA-256 `47b7dc8ef1d24847000b60f426c9b7965301e2836c97ad865bff856a875af95f`)
- **Estado de las 10 fuentes: no modificadas, 0 bytes.** Se verifican con
  `hashes/FUENTES_SHA256.txt` (10/10 = SI).

---

## 1. Qué es y qué no es este paquete

**Es**: una auditoría reproducible sobre señales **sintéticas deterministas** que responde
cuatro preguntas concretas (consensos, alineación, fórmulas de `mix_delta`, seguridad del
orquestador), con resultados crudos, logs y un prototipo probado.

**No es**: una validación de música real, de calidad perceptual, de modelos MVSEP en línea, de
Android/Termux, ni una declaración de qué motor o candidato es mejor. **En todo el paquete no
se elige ganador en ningún momento.**

---

## 2. Verificación en cuatro comandos

Desde la raíz del paquete descomprimido:

```bash
# 1) Coherencia interna (estructura + cifras + referencias + literales)
python3 src/verificar_coherencia.py

# 2) Integridad de las 10 fuentes comparada con lo entregado
sha256sum -c hashes/FUENTES_SHA256.txt

# 3) Sumas de todos los ficheros del paquete
sha256sum -c hashes/SHA256SUMS.txt

# 4) Tests del prototipo del orquestador (21)
python3 -m pytest tests/ -q
```

Resultado esperado, y obtenido en la última compilación:

```
[A] estructura : 17/17
[B] cifras      : 40/40 cuadran
[C] referencias : 125 comprobadas, 0 rotas, 11 a fuentes externas (esperadas), 1 generadas al ejecutar
[D] literales   : 19/19 cifras aparecen en su documento
[OK] coherencia -> results/coherencia.json
```

`results/coherencia.json` guarda el detalle de las 40 cifras: para cada una, el valor
**declarado en el documento**, el **recalculado desde el artefacto crudo** y la fuente. Cualquier
discrepancia futura se detecta ahí.

> Nota sobre `sha256sum -c hashes/FUENTES_SHA256.txt`: ese fichero tiene tres columnas
> (esperado, real, SI/NO) más el nombre, así que es **para lectura**; la comprobación
> automática de las fuentes la hace `src/verificar_coherencia.py` y `src/preflight_1b.py`, que
> recalculan los 10 SHA-256.

---

## 3. Mapa: cada afirmación, su evidencia

| Afirmación | Documento | Artefacto que la respalda |
|---|---|---|
| La opción de consenso por defecto no cambia el audio | `CONSENSUS_VALIDATION.md` §2 | `results/consenso_e2e_veredicto.json` (max\|Δ\| = 0,0) |
| K=2 hace idénticos los 3 métodos de máscara por álgebra | `CONSENSUS_VALIDATION.md` §3 | `results/consenso_mallas.csv` |
| v3 tiene 4 métodos con taxonomía propia | `CONSENSUS_VALIDATION.md` §1 | `results/consenso_complejo.csv` |
| 554/780 aciertos, 10 FP, 0 FN | `ALIGNMENT_DIAGNOSTICS.md` §5 | `results/alineacion_resumen.json` |
| La superficie NCC está casi empatada | `ALIGNMENT_DIAGNOSTICS.md` §6 | `results/alineacion_casos.csv` (`ratio_real_vs_max`) |
| Solape ≥ 90 %: 554 → 602, 0 empeoran | `ALIGNMENT_DIAGNOSTICS.md` §9.2 | `alineacion_casos.csv` (`lag_ganador_con_solape_alto_env`) |
| Un solo retardo no representa L y R | `ALIGNMENT_DIAGNOSTICS.md` §8 | `results/alineacion_lr_asimetrico.json` |
| `SDI_F2` no existe | `FORMULA_AUDIT.md` §1 | `results/mix_delta_auditoria.json` (`busqueda_sdi_f2`) |
| El residuo de la identidad es exactamente `e_id` | `FORMULA_AUDIT.md` §3 | `results/delta_identidad_residuo.json` |
| `e = 0` no prueba separación | `FORMULA_AUDIT.md` §4 | `results/complementariedad_trivial.json` |
| La complementariedad depende de las guías, no de la rama | `FORMULA_AUDIT.md` §5.2 | `results/complementariedad_guias_degradadas.json` |
| `--allow-crop` es inoperante si existe `SDV_id` | `FORMULA_AUDIT.md` §6.1 | `results/mix_delta_guardas.json` + `allow_crop_sin_sdv_id.json` |
| La polaridad invertida no se detecta | `FORMULA_AUDIT.md` §6.2 | `results/mix_delta_guardas.json` |
| 16 defectos del orquestador, con línea | `ORCHESTRATOR_SPEC.md` §2 | `results/bloque_d_orquestador.json` → `auditoria` |
| El original produce 0 pares con los nombres reales | `ORCHESTRATOR_SPEC.md` §2.1 | `bloque_d_orquestador.json` → `demos_original` |
| SR 48 kHz ⇒ −8,13 % de tono y 7 800 muestras descartadas | `ORCHESTRATOR_SPEC.md` §2.1 | `results/bloque_d_demo_sr48_real.json` |
| 27/27 fixtures y 21 tests | `ORCHESTRATOR_SPEC.md` §6 | `bloque_d_orquestador.json` + `pytest tests/` |
| El prototipo no mezcla L/R (error 6·10⁻⁸ vs 0,350 si se intercambian) | `ORCHESTRATOR_SPEC.md` §7 | `bloque_d_orquestador.json` → `verificaciones_extra.lr` |

---

## 4. Glosario de etiquetas

| Etiqueta | Significado |
|---|---|
| `DOCUMENTED_FACT` | Afirmado por el código o los manifiestos, con línea citada |
| `EXPERIMENTAL_RESULT` | Medido en esta fase, reproducible con los comandos del `README.md` |
| `THEORETICAL_DEDUCTION` | Derivado algebraicamente y contrastado numéricamente |
| `HYPOTHESIS` | Plausible, no demostrado; se señala como tal |
| `UNKNOWN` | No medido o no presente en el material. **No se rellena por inferencia** |

Cuando un dato no existe, el paquete pone `UNKNOWN` y lo explica. Si encuentras un hueco sin
etiquetar, es un fallo de la entrega: repórtalo.

---

## 5. Qué queda FUERA del ZIP, y por qué

| Ausente | Motivo | Cómo recuperarlo |
|---|---|---|
| Los 10 ficheros fuente | Es la entrada inmutable, no el entregable. Sus SHA-256 sí están dentro | `hashes/FUENTES_SHA256.txt` |
| `results/alineacion_curvas.json` (120 MB) | Tamaño. Va la versión decimada 1/8, conservando el máximo exacto | `python3 src/analisis_b.py` |
| `work/` (fixtures WAV ~583 MB) | Scratch regenerable | `python3 src/bloque_d.py` |
| `manifest_orquestador.json` | Se genera en cada ejecución | `python3 -m orchestrator_spec.cli …` |

Los fixtures **no se incluyen como audio** a propósito: son deterministas (semilla `20261117`,
WAV FLOAT estéreo, `M = V + I` exacto, evento solo en el canal L). El audio regenerado es
idéntico muestra a muestra; los **bytes** del fichero pueden diferir por el chunk `PEAK` con
marca de tiempo de libsndfile. Por eso **todas** las comparaciones del laboratorio se hacen
sobre audio decodificado, nunca sobre el hash del fichero.

---

## 6. Los nueve criterios de rechazo del encargo, uno por uno

| Criterio de rechazo | Estado | Evidencia |
|---|---|---|
| Se modificó algún archivo fuente | **No** | `hashes/FUENTES_SHA256.txt`: 10/10 idénticos |
| Se eligió un archivo ambiguo sin reportarlo | **No** | Fixtures `03` y `08` → `AMBIGUOUS`; demo *e* demuestra que el original sí lo hace y se reporta |
| Se mezclaron componentes de distintas corridas | **No** | Clave de grupo `(perfil, run, carpeta)`; fixtures `03b`, `04`, `13` |
| Se recortaron/resamplearon/normalizaron en silencio | **No** | `14a`–`14d` → `INCOMPATIBLE`; el prototipo no trunca nunca |
| Se sumó C agregado con sus subcomponentes | **No** | Fixture `08` → `AMBIGUOUS`; test unitario que lo impide |
| Se declaró `E = C + D` sin medirlo | **No** | Fixtures `11a/b/c` y §5.4: solo se mide (149,05 / 40,09 / 9,32 dB) |
| Se confundió reconstrucción con separación | **No** | `FORMULA_AUDIT.md` §4: separación nula = 336,87 dB > separación perfecta = 325,83 dB |
| Se afirmó que `SDI_F2` existe | **No** | Cero apariciones; declarado `UNKNOWN` |
| Se omitieron fallos o resultados crudos | **No** | `results/logs/` (7 logs), `results/raw.jsonl` (7 724 registros), demos fallidas incluidas |

---

## 7. Estado del proyecto y qué sigue

| Bloque | Estado | Pendiente |
|---|---|---|
| **A** Consensos | **Cerrado** | Nada |
| **B** Alineación | **Diagnóstico cerrado** | Las 2 propuestas (θ = 0,35 y solape ≥ 90 %) **medidas, no aplicadas**: requieren validación externa sobre música real |
| **C** `mix_delta` / SDI_F2 | **Cerrado** | `SDI_F2` = `UNKNOWN`; 2 defectos reportados y **no parcheados** (`--allow-crop` con `SDV_id`, polaridad no detectada) |
| **D** Orquestador | **Cerrado** (auditoría + prototipo) | El original **no se ha tocado**; los 10 cambios propuestos están en `ORCHESTRATOR_SPEC.md` §8 |

**Restricciones que siguen vigentes** (no revertidas por el usuario):

1. Solo lectura sobre las fuentes; todo cambio va en un `src/` aparte, con diff, hash y etiqueta.
2. Prohibido elegir ganador o declarar «mejor motor».
3. Prohibido inventar métricas, definiciones o patrones de nombres: sin medida → `UNKNOWN`.
4. No asumir `SDV + SDI = Mix` como prueba de separación.
5. No normalizar ni forzar ganancia/polaridad/fase/SR/canales/duración.
6. Ambigüedad = error explícito, nunca el primer archivo encontrado.
7. No truncar salvo `--allow-crop` explícito y reportado.
8. Nunca sumar C agregado con sus subcomponentes.
9. El **verificador de alineación sigue sin parchear** (decisión del usuario).

**Lo que este paquete no autoriza a concluir**: que un motor sea mejor, que un candidato sirva
para una canción, ni que los resultados se sostengan sobre música real. Para eso hace falta la
validación externa que aquí se deja explícitamente pendiente.
