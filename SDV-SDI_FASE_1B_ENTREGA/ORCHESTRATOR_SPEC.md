# ORCHESTRATOR_SPEC.md — Bloque D

**Fase sintética 1B · auditoría de `orquestador_maestro.py` y arquitectura por perfiles
semánticos**

Fuente auditada: `/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM/orquestador_maestro.py`
(75 líneas, SHA‑256 `ea16344ae64eea4e…`), **sin modificar**. El original solo se ha
**ejecutado** en directorios de trabajo desechables para observar su comportamiento.

Prototipo: `src/orchestrator_spec/` (9 módulos, aislado, no importa el original).
Matriz: **27/27 fixtures** · **10/10 tests unitarios** · **16/16 afirmaciones de auditoría**.

---

## 0. Resumen en una tabla

| Pregunta (4.11) | Respuesta corta |
|---|---|
| Qué es funcional | La resta `M − stem`; la escritura WAV FLOAT; el manifiesto JSON básico |
| Qué es peligroso | Recorte silencioso, SR del mix impuesto a todos, elección de fichero por orden de `listdir`, omisión silenciosa de modelos y componentes |
| Cómo no depender de nombres de modelo | Registro de perfiles en JSON: el código solo conoce **roles**, nunca `sucial`/`anvuew` |
| C agregado vs dividido | Estrategia declarada en el perfil + `excluye` en los patrones; agregado y subcomponentes juntos ⇒ `AMBIGUOUS` |
| Cuándo es válido `C_total` | Agregado solo, **o** Reverb+Others exactamente, con geometría idéntica validada |
| Qué residuales por subconjunto | Tabla §5.3 |
| Cómo se prueba que no mezcla L/R | `SDV1`/`SDI1` contra ground truth: **6,1·10⁻⁸** de error; si se intercambiaran los canales, **0,350** |
| Qué debe cambiar el futuro orquestador | §8, 10 cambios concretos |

---

## 1. Hallazgo previo que condiciona todo: los nombres reales no casan

`DOCUMENTED_FACT`. El manifiesto entregado `MANIFEST_SEP_SDV-SDI.json` declara sus pares así:

```
par1_roformer_instrum_only.wav   /  par1_roformer_vocals_full.wav
par2_mdxb_instrum_only.wav       /  par2_mdxb_vocals_full.wav
par3_sucial_...                  /  par4_anvuew_...
```

El orquestador busca `*_instrum.wav` y `*_vocals.wav` (l.27‑29). **Ejecutado sobre esos
nombres reales produce 0 pares**, sin error y con `rc=0` (demo *a*). La rama simple del
orquestador **no reconoce la nomenclatura que usa el propio proyecto**.

Además, **ningún manifiesto entregado contiene una sola etiqueta `[A]`, `[B]`, `[C]`, `[D]`
ni `[E]`** (0 coincidencias en `MANIFEST_SEP_SDV-SDI.json` y `manifest_genio.json`). La
convención `_[A]/.wav` sobre la que se apoya la rama de Reverb Removal **no tiene ningún
ejemplo real en el material entregado**. Los nombres de salida reales que sí aparecen son
del estilo `Genio_Atrapado_DeReverb_mt_6_SDV_B1.wav`.

> Consecuencia de método: los perfiles de Reverb Removal de este prototipo son **SINTÉTICOS
> y están etiquetados como tales** en el JSON de perfiles. No se presentan como patrones
> reales observados. Los modelos `sucial`, `anvuew`, `roformer` y `mdxb` sí aparecen en los
> manifiestos, lo que confirma que la lista cableada de dos modelos del original es
> incompleta al menos en dos.

---

## 2. Auditoría del comportamiento actual · 16/16 confirmadas

Cada fila se comprobó buscando el texto exacto en el fichero y anotando la línea
(`results/bloque_d_orquestador.json → auditoria`).

| ID | Línea | Hecho verificado |
|---|---|---|
| D‑01 | 27 | Busca pares con `*_instrum.wav` (y `_vocals.wav`, l.29) |
| D‑02 | 30 | Si falta `_vocals.wav`, se salta **en silencio** |
| D‑03 | 47 | En Reverb itera **solo** `["sucial", "anvuew"]` |
| D‑04 | 51 | Reconoce `[A]`, `[C]`, `[D]` |
| D‑05 | — | No aparece `[B]` ni `[E]` en **ninguna** línea |
| D‑06 | 61 | `SDV = mix − A + D` |
| D‑07 | 62 | `SDI = mix − C − D` |
| D‑08 | 49 | Recorre `os.listdir`; un segundo fichero del mismo rol **pisa** al primero |
| D‑09 | 60 | `min_len` recorta a lo más corto (Reverb) |
| D‑10 | 34 | `min_len` recorta a lo más corto (Simples) |
| D‑11 | 40/66 | Escribe con el `sr` **del Mix** para todos los stems |
| D‑12 | 55 | Exige A, C y D a la vez; si falta uno, omite el modelo **en silencio** |
| D‑13 | — | No comprueba `samplerate` en ningún punto |
| D‑14 | — | No comprueba `channels` en ningún punto |
| D‑15 | — | El manifiesto no guarda ningún hash |
| D‑16 | 17 | Escribe **dentro** del árbol de entrada (no hay `--out`) |

### 2.1 Demos ejecutando el original (no solo lectura de código)

`EXPERIMENTAL_RESULT`. Ocho escenarios en `work/d/orig_*`, todas con `rc=0`:

| Demo | Montaje | Resultado observado |
|---|---|---|
| a | nombres **reales** del manifiesto | **0 pares** |
| b | nombres que el original espera | 1 par |
| c | Reverb con modelo `otromodelo` | **0 pares, sin aviso** |
| d | Reverb sin `[D]` | **0 pares, sin aviso** |
| e | dos `[C]` para `sucial` | 1 par, **gana `sucial_uno_[C]` (el último del `listdir`)**, sin aviso |
| f | `[C]` a **48 kHz** | 1 par, `rc=0`, **sin aviso** |
| g | `[C]` de 1,5 s | salida de **1,5 s** (recorte silencioso) |
| h | `[C]` **mono** | salida estéreo por *broadcasting*, sin aviso |

Medición precisa del caso f (`results/bloque_d_demo_sr48_real.json`): `[C]` de 48 000 Hz y
96 000 muestras (2,0 s) frente a Mix de 44 100 Hz y 88 200 muestras:

- se **descartan 7 800 muestras** del `[C]` (0,1625 s de cola, 8,13 %);
- lo que queda se reinterpreta a 44,1 kHz, es decir **8,13 % más grave**;
- la salida dura 2,0 s y `rc=0`, **sin ningún aviso**.

En el caso e, el candidato ganador se identificó comparando la salida con cada uno:
residuo `5,6·10⁻⁸` frente a `sucial_uno_[C]` y `1,95·10⁻¹` frente a `sucial_dos_[C]`.

---

## 3. Arquitectura propuesta: nueve fases

```
1 inventario  →  2 clasificación  →  3 agrupación  →  4 candidatos
   →  5 validación estricta  →  6 Mix  →  7 C_total  →  8 residuales  →  9 manifiesto
```

| Fase | Módulo | Qué garantiza |
|---|---|---|
| 1 Inventario | `inventario.py` | Solo `os.walk` + `stat`: **no abre audio**. Registra los ignorados con motivo |
| 2 Clasificación | `clasificador.py` | Rol por **regex anclada del perfil**, con evidencia, prioridad y `excluye` |
| 3 Agrupación | `agrupador.py` | Clave `(perfil, run, carpeta)`: **nunca** se mezclan corridas |
| 4 Candidatos | `agrupador.py` | Detecta 0, 1 o N candidatos por rol |
| 5 Validación | `validador.py` | SR, canales, frames, subtype y finitud **estrictos**; sin truncar |
| 6 Mix | `validador.py` | Exactamente un Mix; hash opcional verificado |
| 7 C_total | `c_total.py` | Solo con la estrategia declarada; jamás agregado+subcomponentes |
| 8 Residuales | `residuales.py` | Solo fórmulas con insumos **completos y validados** |
| 9 Manifiesto | `manifiesto.py` | Rutas, hashes, roles, patrón que casó, metadatos, fórmulas |

El prototipo **no escribe jamás dentro del árbol de entrada**: `--out` es obligatorio.

### 3.1 Perfiles: el cálculo no conoce ningún nombre de modelo

`configs/perfiles_orquestador.json` (esquema `orchestrator_profile/1`). Tres perfiles:

| `model_id` | Origen de los patrones |
|---|---|
| `mvsep_simple` | **Evidencia real** (`MANIFEST_SEP`: `_instrum_only`/`_vocals_full`) + convención del original (`_instrum`/`_vocals`) + variantes de igual prioridad `_instrumental`/`_acapella` |
| `reverb_tagged` | **Sintético declarado** (`[A]`…`[E]`, `Reverb [C]`, `Others [C]`) |
| `modelo_nuevo_x` | **Sintético** (`__restored`, `__backing`, `__wet`, `__dryvox`, `__vox`): sin corchetes, sin relación con `sucial`/`anvuew` |

Cada patrón declara `regex` (con grupo nombrado `run`), `prioridad` y, opcionalmente,
`excluye`. Añadir un modelo nuevo = **añadir un perfil**, sin tocar código de cálculo.

### 3.2 La trampa de `[C]`, resuelta en datos

El original usa `if "_[C]" in f` (substring). Este prototipo exige regex **anclada** y
declara exclusiones explícitas:

```json
"C_AGGREGATE": [{"regex": "^(?P<run>.+?)_\\[C\\]\\.wav$", "prioridad": 10,
                 "excluye": ["Reverb\\s*\\[C\\]", "Others\\s*\\[C\\]"]}]
```

Test unitario: `m_[C].wav → C_AGGREGATE`, `m_Reverb [C].wav → C_REVERB`,
`m_Others [C].wav → C_OTHERS`. Y si dos patrones de **igual** prioridad reclaman el mismo
fichero para roles distintos, el fichero queda `AMBIGUO`: **nunca gana el primero**.

---

## 4. Identificación semántica: roles y estados

**Roles**: `INSTRUMENTAL`, `VOCALS`, `A_RESTORED`, `B_INSTRUMENT`, `C_AGGREGATE`,
`C_REVERB`, `C_OTHERS`, `D_DRY_VOCAL`, `E_VOCALS`. `C_TOTAL` es derivado, nunca leído.

**Estados**, con precedencia `ACCEPT < INCOMPLETE < AMBIGUOUS < INCOMPATIBLE < REJECTED`:

| Estado | Significado | Efecto |
|---|---|---|
| `ACCEPT` | Todo lo calculable se calculó | — |
| `INCOMPLETE` | Falta algún insumo para al menos una fórmula declarada | Se generan las demás |
| `AMBIGUOUS` | 0/1/N candidatos por rol, o conflicto de C | **No se genera nada** del grupo |
| `INCOMPATIBLE` | SR, canales, frames o subtype discrepan | Se descarta **esa fórmula** |
| `REJECTED` | Corrupto, NaN/Inf, Mix ausente/ambiguo/hash cambiado | Se descarta **esa fórmula** |

> **Regla de agregación, explícita:** el estado del **grupo** es el peor de sus fórmulas.
> Por eso un modelo que trae A/C/D pero no B/E sale `INCOMPLETE` aunque genere `SDV2` y
> `SDI2`: es la información honesta. En producción se recomienda **un perfil por modelo**
> declarando solo los componentes que ese modelo entrega de verdad; así `INCOMPLETE`
> significa siempre «este modelo debería haberlo traído y no está».

---

## 5. Fórmulas y C_total

### 5.1 Las cuatro fórmulas, con sus insumos

| Residual | Expresión | Requiere |
|---|---|---|
| `SDV1` | `M − B` | `B_INSTRUMENT` |
| `SDV2` | `M − A + D` | `A_RESTORED`, `D_DRY_VOCAL` |
| `SDI1` | `M − E` | `E_VOCALS` |
| `SDI2` | `M − C_total − D` | `C_TOTAL`, `D_DRY_VOCAL` |
| `SDV_SIMPLE` | `M − Instrumental` | `INSTRUMENTAL` |
| `SDI_SIMPLE` | `M − Vocals` | `VOCALS` |

Idénticas a las del original en `SDV2` (l.61) y `SDI2` (l.62); `SDV1` y `SDI1` **no existen**
en el original porque `[B]` y `[E]` no se leen nunca (D‑05).

### 5.2 Construcción de `C_total` — cuatro situaciones

| Situación | Estrategia | Resultado (medido) |
|---|---|---|
| Solo `C` agregado | `single_aggregate`, 1 sumando | 1 sumando, `C_total = C_aggregate` |
| `Reverb [C]` + `Others [C]` | `split_reverb_others`, 2 sumandos | `C_total = C_reverb + C_others` |
| Solo uno de los dos | `parcial` | **`INCOMPLETE`**: «no se infiere C_total» |
| Agregado **y** subcomponentes | `conflicto` | **`AMBIGUOUS`**: no se elige **ni se suma** |

El agregado y sus subcomponentes **nunca** se suman. La única excepción prevista es que el
perfil declare `representaciones_alternativas: {declara: true, usar: "aggregate"|"split"}`,
y en ese caso queda registrado en los motivos del grupo.

### 5.3 Qué se puede generar con cada subconjunto

| Componentes presentes | Genera |
|---|---|
| `B` | `SDV1` |
| `A`, `D` | `SDV2` |
| `E` | `SDI1` |
| `C` (agregado o dividido), `D` | `SDI2` |
| `A`, `B`, `C`, `D`, `E` | las cuatro |
| Inventario + Vocals | `SDV_SIMPLE`, `SDI_SIMPLE` |

### 5.4 `E ≈ C_total + D`: se mide, no se impone

`EXPERIMENTAL_RESULT` (tres fixtures, por canal L/R):

| Caso | `max|E − C_total − D|` | SNR canal L | ¿exacta? |
|---|---|---|---|
| exacto por construcción | 5,50·10⁻⁸ | 149,05 dB | no (redondeo de WAV FLOAT) |
| desviación leve (×1,01) | 8,09·10⁻³ | 40,09 dB | no |
| desviación severa (×1,5 + ruido) | 3,99·10⁻¹ | 9,32 dB | no |

La relación **no se usa nunca** para fabricar un componente ausente: solo se reporta.

---

## 6. Matriz de fixtures · 27/27

Cada caso declara su resultado esperado antes de ejecutarse. WAV FLOAT estéreo, `M = V + I`,
semilla 20261117, evento exclusivo del canal L y paneo asimétrico.

| # | Caso | Esperado | Obtenido | Residuales |
|---|---|---|---|---|
| 01 | par simple válido | `ACCEPT` | `ACCEPT` | `SDV_SIMPLE`, `SDI_SIMPLE` |
| 02 | falta vocals | `INCOMPLETE` | `INCOMPLETE` | `SDV_SIMPLE` |
| 03 | **dos ficheros reclaman INSTRUMENTAL** | `AMBIGUOUS` | `AMBIGUOUS` | — |
| 03b | dos corridas con prefijo común | `INCOMPLETE` | `INCOMPLETE` | 2 grupos, no se mezclan |
| 04 | dos corridas en la misma carpeta | `ACCEPT` | `ACCEPT` | 2 grupos × 2 |
| 05 | C agregado | `INCOMPLETE` | `INCOMPLETE` | `SDV2`, `SDI2` |
| 06 | C dividido Reverb+Others | `INCOMPLETE` | `INCOMPLETE` | `SDV2`, `SDI2` |
| 07 | **solo `Reverb [C]`** | `INCOMPLETE` | `INCOMPLETE` | `SDV2` (sin `SDI2`) |
| 08 | **agregado + subcomponentes** | `AMBIGUOUS` | `AMBIGUOUS` | — |
| 09 | A/B/C/D/E completos | `ACCEPT` | `ACCEPT` | las cuatro |
| 10 | solo `B` | `INCOMPLETE` | `INCOMPLETE` | `SDV1` |
| 11a/b/c | `E` vs `C_total+D`: exacto / leve / severo | `INCOMPLETE` | `INCOMPLETE` | `SDV2`, `SDI1`, `SDI2` |
| 12 | modelo nuevo, nombres sin corchetes | `ACCEPT` | `ACCEPT` | las cuatro |
| 13 | corridas mezcladas en una carpeta | `INCOMPLETE` | `INCOMPLETE` | 2 grupos |
| 14a | **SR distinta** (48 k) | `INCOMPATIBLE` | `INCOMPATIBLE` | solo `SDI2` |
| 14b | **canales distintos** (mono) | `INCOMPATIBLE` | `INCOMPATIBLE` | solo `SDI2` |
| 14c | **longitud distinta** | `INCOMPATIBLE` | `INCOMPATIBLE` | solo `SDI2` |
| 14d | **subtype distinto** (PCM_16) | `INCOMPATIBLE` | `INCOMPATIBLE` | solo `SDI2` |
| 14e | **NaN** | `REJECTED` | `REJECTED` | solo `SDI2` |
| 15 | L/R asimétrico con ground truth | `ACCEPT` | `ACCEPT` | las cuatro |
| 16a | **WAV corrupto** | `REJECTED` | `REJECTED` | solo `SDI2` |
| 16b | fichero `.txt` en la carpeta | `INCOMPLETE` | `INCOMPLETE` | ignorado y registrado |
| 17a | **Mix ausente** | `REJECTED` | `REJECTED` | — |
| 17b | **dos Mix candidatos** | `REJECTED` | `REJECTED` | — |
| 17c | **hash del Mix no coincide** | `REJECTED` | `REJECTED` | — |

En 14a–e y 16a el grupo entero no se aborta: **solo se descarta la fórmula afectada**, y
`SDI2` (que no usa el fichero defectuoso) se genera igualmente. Es la diferencia entre
«abortar el grupo» y «abortar la fórmula», y se eligió lo segundo por trazabilidad.

---

## 7. Prueba de que no mezcla L/R ni altera duración/SR

`EXPERIMENTAL_RESULT` (fixture 15, con `B = I_true` y `E = V_true`, de modo que la respuesta
correcta es conocida):

| Medición | Valor |
|---|---|
| `max|SDV1 − V_true|` (canal a canal) | **6,06·10⁻⁸** |
| `max|SDI1 − I_true|` | **5,62·10⁻⁸** |
| `max|SDV1 − V_true_intercambiando_LR|` | **0,350** |
| frames de salida / frames del Mix | 88 200 / 88 200 |
| sample rate de salida | 44 100 Hz (idéntico) |
| subtype de salida | `FLOAT` |
| canales | 2 |
| evento presente solo en L | reproducido en L |

La fila del intercambio es la que da valor a la prueba: **si el prototipo mezclara L y R, el
error sería 0,350 en vez de 6·10⁻⁸**, cinco millones de veces mayor. El evento inyectado
únicamente en el canal L aparece en la salida solo en L.

---

## 8. Cambios concretos que debería recibir el futuro `orquestador_maestro.py`

1. **Sacar los nombres de modelo del código** (l.47) a un registro de perfiles en JSON.
2. **Aceptar la nomenclatura real del proyecto** (`_instrum_only`/`_vocals_full`) además de
   la heredada (§1: hoy produce 0 pares con los nombres del propio manifiesto).
3. **Añadir `[B]` y `[E]`** para poder construir `SDV1 = M − B` y `SDI1 = M − E`.
4. **Prohibir el primer match**: 0 candidatos ⇒ `INCOMPLETE`; ≥2 ⇒ `AMBIGUOUS`, con lista
   (hoy gana el último del `listdir`, demo *e*).
5. **No recortar**: `min_len` fuera (demos *f*, *g*); discrepancia de frames ⇒ `INCOMPATIBLE`.
6. **Validar SR, canales y subtype de cada entrada** antes de restar (demos *f*, *h*).
7. **Escribir con el SR verificado**, no con el del Mix por decreto (l.40/66).
8. **`--out` obligatorio**: no escribir dentro del árbol de entrada (l.17).
9. **Manifiesto con hashes, roles, patrón que casó, metadatos y estado** (hoy no hay hashes).
10. **Código de salida ≠ 0 ante ambigüedad o incompatibilidad** (hoy siempre 0).

---

## 9. Lo que este bloque NO dice

- **`UNKNOWN`**: cuál es la convención de nombres real de los componentes de Reverb Removal.
  No hay ni un ejemplo en el material entregado (§1). Los perfiles `reverb_tagged` y
  `modelo_nuevo_x` son sintéticos y están etiquetados.
- **`UNKNOWN`**: si `sucial`/`anvuew` entregan realmente A/C/D o algún otro subconjunto.
- **`UNKNOWN`**: si `C` viene agregado o dividido en la práctica.
- No se valida calidad perceptual ni idoneidad musical: solo clasificación, integridad y
  aritmética sobre señales sintéticas.
- El prototipo **no sustituye** al orquestador: es externo y aislado, y no se ha tocado el
  original.

---

## 10. Reproducción

```bash
cd /home/user/fase1b/FASE_1B_RESULTADOS
python3 -u src/bloque_d.py            # auditoría + 8 demos + 27 fixtures + 10 tests (~2,5 s)

# prototipo por separado, sobre cualquier carpeta:
PYTHONPATH=src python3 -m orchestrator_spec.cli \
    --dir work/d/fx/09_reverb_abcde \
    --perfiles configs/perfiles_orquestador.json \
    --mix Mix.wav --out /tmp/salida
```

| Artefacto | Contenido |
|---|---|
| `results/bloque_d_orquestador.json` | auditoría, demos, las 27 filas, resultado completo y tests |
| `results/bloque_d_demos_medidos.json` | ganador del duplicado y desviación por SR |
| `results/bloque_d_demo_sr48_real.json` | medición exacta del recorte y del descenso de tono |
| `work/d/fx/<caso>/` | los 27 fixtures con su audio sintético |
| `work/d/out/<caso>/manifest_orquestador.json` | manifiesto de procedencia por fixture |
