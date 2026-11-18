# FASE SINTÉTICA 1B — entrega reproducible

Laboratorio de auditoría sobre la fuente inmutable `Proyecto SDV-SDI_SGM.zip`.
**Las 10 fuentes no se han modificado: 0 bytes.** Todo el trabajo vive en `src/`.

Todo se ejecuta sobre **señales sintéticas deterministas**. No se valida música real, calidad
perceptual ni la idoneidad de ningún candidato.

---

## 1. Requisitos

- Python ≥ 3.11
- `numpy`, `scipy`, `soundfile` (con libsndfile)
- `pytest` solo para `tests/` (los tests también corren sin él)

Sin `librosa` en ningún punto, por decisión del encargo: **no se importa en ningún módulo
del laboratorio**. Aviso de transparencia: en este entorno `librosa` **está instalada**
(`src/preflight_1b.py` lo detecta y lo reporta), pero ninguna ruta de código la usa; la única
mención en el árbol es la sonda de detección del propio preflight.

Comprobación rápida del entorno:

```bash
python3 -c "import numpy, scipy, soundfile; print(numpy.__version__, scipy.__version__, soundfile.__version__)"
```

---

## 2. Reproducir los cuatro bloques

```bash
cd FASE_1B_RESULTADOS

# Entorno + integridad de las fuentes (10/10)
python3 src/preflight_1b.py

# Coherencia interna del paquete (estructura, cifras, referencias, literales)
python3 src/verificar_coherencia.py

# BLOQUE A — consensos  (~62 s, el más largo: motores reales)
python3 -u src/bloque_a.py 2>&1 | tee results/logs/bloque_a_stdout.log

# BLOQUE B — alineación (~366 s, 780 casos)
python3 -u src/bloque_b.py 2>&1 | tee results/logs/bloque_b_stdout.log
python3 -u src/analisis_b.py            # figuras SVG y análisis

# BLOQUE C — mix_delta y SDI_F2 (~13 s)
python3 -u src/bloque_c.py 2>&1 | tee results/logs/bloque_c_stdout.log

# BLOQUE D — orquestador (~2,5 s: auditoría + 8 demos + 27 fixtures + 10 tests)
python3 -u src/bloque_d.py 2>&1 | tee results/logs/bloque_d_stdout.log

# Consolidar results/results.csv|json|raw.jsonl
python3 src/consolidar_resultados.py

# Tests del prototipo (21)
python3 -m pytest tests/ -q      # o: python3 tests/test_orquestador_prototipo.py

# Empaquetar y re-verificar (exige coherencia OK, luego integridad + manifiestos + hashes)
python3 src/empaquetar.py
```

Cada bloque escribe a la vez en `results/` y `results/logs/`; los fallos se conservan, no se
resumen.

---

## 3. Usar el prototipo del orquestador por separado

```bash
PYTHONPATH=src python3 -m orchestrator_spec.cli \
    --dir  <carpeta_de_la_cancion> \
    --perfiles configs/perfiles_orquestador.json \
    --mix  Mix.wav \
    --out  /tmp/salida           # obligatorio y SIEMPRE fuera del árbol de entrada
```

Opciones: `--no-generar` (solo auditar), `--subtype-laxo` (no exigir subtype idéntico).

Salidas: WAV **FLOAT** por residual (`SDV1`, `SDV2`, `SDI1`, `SDI2`, `SDV_SIMPLE`,
`SDI_SIMPLE`) y `manifest_orquestador.json` con fórmulas, rutas, roles, patrón que casó,
hashes, metadatos, estado de validación y `transformaciones_aplicadas: "none"`.

**Política por defecto:** sin primer match · sin truncar · sin resamplear · sin convertir
mono/estéreo · sin alinear · sin normalizar · sin tocar ganancia ni polaridad.

---

## 4. Añadir un modelo nuevo (sin tocar código)

Edita `configs/perfiles_orquestador.json` y añade un objeto a `perfiles`:

```json
{
  "model_id": "mi_modelo_v1",
  "version": "1.0",
  "procedencia": "de dónde salen estos nombres y con qué evidencia",
  "roles": {
    "A_RESTORED":   [{"regex": "^(?P<run>.+?)__restored\\.wav$"}],
    "B_INSTRUMENT": [{"regex": "^(?P<run>.+?)__backing\\.wav$"}],
    "C_AGGREGATE":  [{"regex": "^(?P<run>.+?)__wet\\.wav$"}],
    "D_DRY_VOCAL":  [{"regex": "^(?P<run>.+?)__dryvox\\.wav$"}],
    "E_VOCALS":     [{"regex": "^(?P<run>.+?)__vox\\.wav$"}]
  }
}
```

Reglas: el grupo nombrado `run` es lo que separa corridas; `prioridad` resuelve solapes;
`excluye` impide que un patrón genérico se coma un subcomponente (por ejemplo `[C]` frente a
`Reverb [C]`). El código de cálculo no cambia nunca.

---

## 5. Mapa de la entrega

| Ruta | Qué hay |
|---|---|
| `REPORT.md` | Informe principal y respuestas a las 8 preguntas |
| `SOURCE_AUDIT.md` | Las 10 fuentes: hashes y defectos por fichero |
| `CONSENSUS_VALIDATION.md` | Bloque A |
| `ALIGNMENT_DIAGNOSTICS.md` | Bloque B |
| `FORMULA_AUDIT.md` | Bloque C |
| `ORCHESTRATOR_SPEC.md` | Bloque D |
| `src/` | Laboratorio (`senales`, `guias`, `metricas`, `adaptadores`, `bloque_a..d`, `analisis_b`, `consolidar_resultados`, `empaquetar`) + `orchestrator_spec/` |
| `tests/` | 21 tests del prototipo (además de los 10 internos de `src/bloque_d.py`) |
| `configs/perfiles_orquestador.json` | Registro de perfiles semánticos |
| `fixtures/fixtures_especificacion.json` | Los 27 casos con su resultado esperado |
| `results/results.csv` | 7 724 filas normalizadas (`bloque, conjunto, caso, clave, valor, estado, fuente`) |
| `results/results.json` | Resumen estructurado y veredictos por bloque |
| `results/raw.jsonl` | Los mismos 7 724 registros, uno por línea |
| `results/*.csv|json` | Artefactos crudos por bloque |
| `results/logs/` | stdout/stderr de cada corrida |
| `manifests/MANIFEST_ENTREGABLES.json` | Inventario con SHA‑256 de todo lo entregado |
| `hashes/SHA256SUMS.txt` | Sumas verificables |
| `hashes/FUENTES_SHA256.txt` | Verificación de las 10 fuentes (esperado vs real) |

---

## 6. Sobre el audio y las figuras

- **No se incluye audio** (ni comercial ni del usuario). Los 27/27 fixtures son deterministas:
  semilla `20261117`, WAV FLOAT estéreo, `M = V + I` exacto, evento inyectado solo en el
  canal L. Se regeneran con `python3 src/bloque_d.py`.
- El audio regenerado es **idéntico muestra a muestra**, pero los **bytes** del fichero pueden
  diferir: libsndfile escribe un chunk `PEAK` con marca de tiempo. Por eso todas las
  comparaciones del laboratorio se hacen sobre **audio decodificado**, nunca sobre el hash
  del fichero (hallazgo del Bloque A, documentado en `CONSENSUS_VALIDATION.md`).
- `results/alineacion_curvas.json` completo pesa 120 MB y **no va en el ZIP**: se incluye
  `alineacion_curvas_reducidas.json` (decimación 1/8 conservando el máximo exacto) y el
  original se regenera con `python3 src/analisis_b.py`. Por presupuesto de espacio, ese
  fichero de 120 MB **tampoco se conserva en el workspace** del laboratorio; lo mismo vale
  para `work/` (fixtures, salidas de los motores y demos del orquestador), que es scratch
  100 % regenerable con los comandos de la sección 2.

---

## 7. Estado y pendientes

Cerrados: **A**, **B** (como diagnóstico), **C**, **D**.

Pendiente de **validación externa**, no aplicado: las dos propuestas del Bloque B (umbral
exploratorio θ = 0,35 y restricción de solape ≥ 90 %). El **verificador de alineación sigue
sin parchear**.

Declarado `UNKNOWN` y no reconstruido: **`SDI_F2`** (0 apariciones en el código), la
convención real de nombres de Reverb Removal, y el motivo histórico de cada ausencia.
