# Etapa 6G.1 — No regresión DSP frente a 6G (auditoría final, código H2/H2-R)

**Objeto:** comprobar que el código actual de 6G.1, incluidas las modificaciones
H2/H2-R, no altera el DSP respecto de la 6G publicada.
**Fuentes comparadas:** `ETAPA_6G_SOPORTE_FLAC_MIX/motores/` (6G, publicada en
`ee19fe208449249a20e194b09c9452b782c7de70`) y
`ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/` (6G.1 en
`b362c56e724811feab2570618c44b082e0d79d3d`).
**Evidencia:** `evidence/no_regresion_dsp_6g1.csv`, `evidence/no_regresion_dsp_6g1.json`
(schema `no-regresion-dsp-6g1/2`).

> **Resultado: los 3 motores quedan en `REJECTED`.** El motivo es exclusivamente
> el criterio de **huella de literales numéricos** (`dsp_ok = False`) en dos
> definiciones que no son DSP: `FileInfo` y `create_run_dir`. PCM WAV y FLAC
> **idénticos** frente a 6G en los 3 motores, con salidas reales y geometría
> igual. No hay definiciones añadidas ni eliminadas, ni constantes cambiadas.
> Siguiendo la instrucción, **no se modificó producción ni se añadió ninguna
> exclusión a la huella** para hacerla pasar: el resultado se documenta y la
> tarea se detiene aquí (§5). Este informe **no** declara 6G.1 cerrada ni lista
> para integración: esa decisión corresponde a Cris tras la auditoría conjunta.

---

## 1. Procedencia y entorno

| Elemento | Valor |
|---|---|
| HEAD de partida (local = remoto `arena/441a4bf8-sdv-sdi-sgm`) | `b362c56e724811feab2570618c44b082e0d79d3d` |
| 6G de referencia | `ee19fe208449249a20e194b09c9452b782c7de70` (rama `arena/89d5c189-sdv-sdi-sgm`) |
| Verificación de la 6G extraída | `sha256sum -c ETAPA_6G_SOPORTE_FLAC_MIX/SHA256SUMS.txt` → **46/46 OK** |
| Entorno | Python 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2, linux x86_64, 2 CPU |
| Fixtures (verificados contra `fixtures/fixtures_manifest.json` por el propio script) | `mix.wav` `060d6c89…9627`, `mix.flac` `2f550ce2…45fa`, `vocal_mix.wav` `69a3a552…8357`, `instrumental_mix.wav` `896bd59b…cea8` — 4/4 coinciden |

**Limitación de ubicación resuelta sin tocar el repositorio:** la carpeta
`ETAPA_6G_SOPORTE_FLAC_MIX/` no está en la historia de `b362c56` (se publicó en
`ee19fe2`, rama `arena/89d5c189-sdv-sdi-sgm`). Igual que en la evidencia previa
(`fuentes_6g: /tmp/wt6g1/...`), se extrajo con `git archive ee19fe2` a
`/tmp/wt6g1/`, se verificó 46/46 y se ejecutó el script desde una copia
byte a byte de `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/` (comprobada con `diff -r`)
situada junto a ella. Sólo los dos archivos de evidencia se copiaron de vuelta.

| Motor | SHA-256 6G | SHA-256 6G.1 (`b362c56`) |
|---|---|---|
| Hardened | `29b30593d97733eb0c073de437ef6725c6264e42034e4a388b4e4baf3bbdcc1b` | `8c1fca989886de01d4cc8a849426a68851f0806e7dbdc1c62b36966372a1f571` |
| EVO | `87bf83651f8f237a4de94d45f0104559b47daf55c03b3e18265f83edfb8a522c` | `7b99ab805a9134fef2bc813024d38d107b3c31cb452282418e407e7779de19d8` |
| MQR | `f014cc0c71a0012054eb249862b55bd9cff112e3bd08855604e914c4b1ebe1e8` | `00734713ef729a607e173c518d49f844295af08a58c9ad4c2f6dbff45729372d` |

---

## 2. Método y ajuste del arnés

1. **AST.** Definiciones de nivel superior (funciones y clases) y constantes en
   mayúsculas de cada motor, 6G frente a 6G.1.
2. **Huella DSP de cada definición cambiada:** multiconjunto de literales
   numéricos (con signo para `-x`; se excluye sólo el argumento `indent` de
   serialización JSON, conteo registrado) y multiconjunto de llamadas a
   primitivas DSP (`fft`, `rfft`, `hann`, `sqrt`, `exp`, `abs`, `power`,
   `maximum`, `where`, `sum`, `mean`, `convolve`, `einsum`, `percentile`, …;
   `log(...)` sin punto es el registro del motor y se excluye).
3. **PCM:** `mix.wav` y `mix.flac` (con `vocal_mix.wav` / `instrumental_mix.wav`)
   procesados en `full_processing` por la copia 6G y por la 6G.1 de cada motor;
   hash SHA-256 del PCM decodificado (`float64`) por nombre de salida.
4. **Informe** `analysis.json`: comparación diagnóstica (no entra en el veredicto).

**Ajuste realizado en `scripts/no_regresion_dsp_6g1.py` (sólo el arnés):**

* `dsp_ok` ahora **rechaza definiciones añadidas** (antes sólo rechazaba las
  eliminadas) y también constantes añadidas o eliminadas, además de las
  cambiadas: `dsp_ok = sin defs añadidas ∧ sin defs eliminadas ∧ sin constantes
  cambiadas/añadidas/eliminadas ∧ huella idéntica en cada definición cambiada`.
* **Existencia real de salidas:** cada salida debe existir en disco (archivo
  regular, no enlace, tamaño > 0, SHA-256 de archivo recalculado = registrado),
  ambos procesos con salida 0 y mismo conjunto de nombres en 6G y 6G.1.
* **Geometría** `(frames, canales, sr)` por salida, 6G frente a 6G.1; entra en
  `identicos`.
* Verificación de los 4 fixtures contra el manifiesto antes de ejecutar.
* Registro de SHA-256 de los motores comparados y de los criterios aplicados.

No se tocó la definición de la huella (ni literales ni lista de primitivas DSP)
ni ningún otro criterio de aceptación.

---

## 3. Resultado por motor

### 3.1 AST, constantes y huella

| Motor | Definiciones cambiadas (todas) | Añadidas | Eliminadas | Constantes cambiadas / añadidas / eliminadas | Huella literales | Huella llamadas DSP | `dsp_ok` |
|---|---|---|---|---|---|---|---|
| Hardened | `CandidateRunner`, `FileInfo`, `_open_memmap`, `analyze_guide_scale`, `create_run_dir`, `probe_file`, `run_experiment`, `write_reports` (8) | — | — | — / — / — | **distinta en `FileInfo`, `create_run_dir`** | idéntica (8/8) | **False** |
| EVO | `CandidateRunner`, `FileInfo`, `_open_memmap`, `analyze_guide_scale`, `create_run_dir`, `probe_file`, `run_experiment`, `write_reports` (8) | — | — | — / — / — | **distinta en `FileInfo`, `create_run_dir`** | idéntica (8/8) | **False** |
| MQR | `CandidateRunner`, `FileInfo`, `_open_memmap`, `_run_core`, `analyze_guide_scale`, `create_run_dir`, `probe_file`, `run_experiment`, `write_reports` (9) | — | — | — / — / — | **distinta en `FileInfo`, `create_run_dir`** | idéntica (9/9) | **False** |

`probe_file` **sí** figura como cambiada: el AST confirma que cambió en H2
(`af80424`) y otra vez en H2-R (`af70c26`). Su huella (literales y llamadas DSP)
es idéntica a 6G.

**Diferencias de huella (idénticas en los 3 motores):**

| Definición | Literales añadidos en 6G.1 | Origen en el código | Commit que lo introdujo |
|---|---|---|---|
| `FileInfo` | `0` ×4 | valores por defecto de los campos nuevos `device: int = 0`, `inode: int = 0`, `mtime_ns: int = 0`, `ctime_ns: int = 0` (identidad del objeto validado) | H2 `af80424` |
| `create_run_dir` | `0` ×2, `1` ×1, `999` ×1 | contador de reintentos del directorio provisional exclusivo: `intento = 0`, `intento == 0`, `intento += 1`, `intento > 999` | Seguridad E–G `2248e2e` (pre-H2; no capturado antes porque la evidencia previa se generó en `64b3c2d`) |

Ninguna de las dos definiciones contiene llamadas DSP ni participa en el cálculo
de señal; aun así, el criterio de huella vigente exige literales idénticos en
toda definición cambiada y por eso marca `False`. **No se ha añadido ninguna
excepción**: queda para decisión de la auditoría conjunta.

Literales `indent` excluidos (registrados en `huellas[*].indent_excluidos_6g/6g1`):
`run_experiment` 1/1 y `write_reports` 1/1 en Hardened y EVO; en MQR
`write_reports` 1/1, `_run_core` 0/1 y `run_experiment` 1/0 (el `indent=2` se
trasladó entre funciones; el total por motor se conserva).

### 3.2 Historia AST de las definiciones cambiadas (6G → `b362c56`)

| Commit | Hardened / EVO | MQR |
|---|---|---|
| `64b3c2d` (corrección auditoría) | `CandidateRunner`, `_open_memmap`, `analyze_guide_scale`, `run_experiment`, `write_reports` | ídem + `_run_core` |
| `2248e2e` (Seguridad E–G) | `create_run_dir`, `run_experiment` | `_run_core`, `create_run_dir` |
| `97d1bd0` (E-R1/G-R1) | `run_experiment` | `run_experiment` |
| `f54ceb5` (H1) | `create_run_dir` | `create_run_dir` |
| `2c3227f` (H1-R2) | `create_run_dir` | `create_run_dir` |
| `af80424` (H2) | `FileInfo`, `analyze_guide_scale`, `probe_file`, `run_experiment` | `FileInfo`, `_run_core`, `analyze_guide_scale`, `probe_file` |
| `af70c26` (H2-R) | `probe_file` | `probe_file` |

### 3.3 PCM, salidas y geometría

| Motor | Contenedor | exit 6G / 6G.1 | Salidas reales (6G / 6G.1) | Geometría | Hash PCM 6G = 6G.1 |
|---|---|---|---|---|---|
| Hardened | WAV | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |
| Hardened | FLAC | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |
| EVO | WAV | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |
| EVO | FLAC | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |
| MQR | WAV | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |
| MQR | FLAC | 0 / 0 | 2 / 2 | igual | **IDÉNTICO** |

Hashes PCM decodificados (`float64`, iguales en 6G y 6G.1, y en WAV y FLAC):

| Motor | Salida | Geometría (frames, canales, sr) | SHA-256 PCM |
|---|---|---|---|
| Hardened | `mix SDI.wav` | 88200, 2, 44100 | `368d3ecbc3a07d053a67e2fb1157a66eb290d8f0a7a31087a5a3060a81574f85` |
| Hardened | `mix SDV.wav` | 88200, 2, 44100 | `a347838da989c3645115f9d08dd296a9902a2b8ac0372fde5002e40f1d420bc0` |
| EVO | `mix SDI.wav` | 88200, 2, 44100 | `368d3ecbc3a07d053a67e2fb1157a66eb290d8f0a7a31087a5a3060a81574f85` |
| EVO | `mix SDV.wav` | 88200, 2, 44100 | `a347838da989c3645115f9d08dd296a9902a2b8ac0372fde5002e40f1d420bc0` |
| MQR | `SDI.wav` | 88200, 2, 44100 | `565bc8b6adbf2e489723a2dd11471f05a181608359163d0dbf44b509083754d3` |
| MQR | `SDV.wav` | 88200, 2, 44100 | `8fb3578a2b56b062d6bcb9b9d72b2657106efcd1aa838cc5de8f8a42fe6f9af8` |

Los 24 hashes (3 motores × 2 contenedores × 2 versiones × 2 salidas) coinciden
también con los de la evidencia anterior (`64b3c2d`). Rutas, tamaños y SHA-256
de archivo de cada salida: `motores[*].pcm[WAV|FLAC].salidas_disco_6g/6g1`.

### 3.4 `analysis.json` (diagnóstico, fuera del veredicto)

Igual que en la rectificación D (§6), los informes normalizados **no** son
iguales y sólo difieren en el bloque `integrity` de la alineación: en WAV,
`guide_after/mix_after.identidad_comparada_6g1` (4 rutas); en FLAC, además
`mix_after.{after,before,reason,sha256,unchanged}` (14 rutas; 6G.1 corrige el
falso negativo FLAC de 6G). Ningún campo de cálculo DSP difiere. Detalle en
`campos_diferentes_estricto` / `campos_diferentes_normalizado`.

### 3.5 Veredicto

| Motor | `dsp_ok` | PCM WAV | PCM FLAC | Veredicto |
|---|---|---|---|---|
| Hardened | False (huella `FileInfo`, `create_run_dir`) | IDÉNTICO | IDÉNTICO | **REJECTED** |
| EVO | False (huella `FileInfo`, `create_run_dir`) | IDÉNTICO | IDÉNTICO | **REJECTED** |
| MQR | False (huella `FileInfo`, `create_run_dir`) | IDÉNTICO | IDÉNTICO | **REJECTED** |

---

## 4. NOT_EXECUTED / no actualizado

* Las 6 corridas PCM previstas (3 motores × WAV/FLAC, 6G y 6G.1) **se
  ejecutaron**; no hay casos `NOT_EXECUTED` dentro de la prueba.
* `scripts/consolidar_6g1.py` **no se ejecutó** (fuera de alcance): las filas de
  prueba `10` de `evidence/matriz_global_6g1.csv` y `evidence/resumen_6g1.json`
  siguen reflejando la evidencia anterior (`ACCEPTED`).
* `SHA256SUMS.txt` y `MANIFEST_6G1.json` de la etapa **no se actualizaron**: sus
  entradas de estos cuatro archivos quedan desfasadas. Los hashes vigentes están
  en `SHA256SUMS_NOREG_DSP_FINAL.txt`.
* No se ejecutó audio real, Elis, Tristania, Android ni Termux; no se repitió
  ninguna batería histórica (34/26/17/12, H1, C-R1, H2…).

## 5. Estado y detención

La prueba falla por el criterio de huella en `FileInfo` y `create_run_dir`. Según
la instrucción, no se modificó producción ni se relajó la huella (añadir una
exclusión para literales de definiciones no DSP sería un cambio de criterio que
excede el ajuste mínimo indicado). La tarea se detiene aquí. Queda para la
auditoría conjunta decidir si se aceptan esas dos diferencias como no DSP (con
el respaldo de PCM idéntico y llamadas DSP idénticas) o si se requiere otra
acción.

---

## 6. Rectificación de la comparación de informes [6G.1-R, corrección D] (histórico)

`informe_igual` (6G vs 6G.1) es y debe ser **False**: los informes difieren
exclusivamente en campos del bloque `integrity` que 6G.1 corrige por diseño
(campo nuevo `identidad_comparada_6g1`; contenido de `mix_after` en FLAC). La
igualdad no se fabrica: se registra campo por campo (`campos_diferentes_estricto`,
`campos_diferentes_normalizado`) junto con el conjunto de exclusión aplicado
(`volatiles`; `volatiles_adicionales` vacío). La huella excluye los literales del
argumento `indent` de serialización JSON (formato, no DSP), con conteo por
definición.
