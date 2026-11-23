# 6G.1 — TERCERA REVISIÓN PDA-1/EA: CIERRE DE GARANTÍAS PENDIENTES (Hallazgos C, D, E, F y G)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** informe de diseño, análisis estático y prototipos independientes. **CERO modificaciones en producción** (§9). 6G.1 ABIERTA. Parada obligatoria ejecutada.
- **Fecha:** 22 de noviembre de 2026.
- **Adjudicación registrada (base de esta entrega):** Hallazgos A y B **demostrados**; PDA-1 **base arquitectónica aceptada**; EA por `fd_run` **prometedor, demostrado frente a sustitución de componentes intermedios**; B2 **mitigación válida** hasta el último control. **No se autoriza implementación en producción.**

---

## 0. Identidades Git y comparación de archivos modificados

| Elemento | Valor |
|---|---|
| Referencia de producción (autorizada) | `9fedc5b223444e73955d2b899b6a434b0f5c670e` |
| Diagnóstico I-1 adjudicado | `88a3ea2b9e41938db7c4a894370f2d68033ccbe8` |
| Diseño PDA-1 (base aceptada) | `9975f507a70466ea70369bca9fba053888e63353` |
| Segunda revisión (A/B, referenciada por Cris) | `09961a42f19756a9d748126d3b87a037eb9349bd` |
| Commit de esta entrega | hijo **directo** de `09961a4…`; contiene **exclusivamente** documentos de diseño, prototipo independiente y evidencias |
| Entorno del prototipo | Python 3.11.2, numpy 1.26.4, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64, kernel 6.1.158+, euid 1001 (single-uid; declarado) |

**Comparación de archivos modificados:** el commit **sólo añade** ficheros (0 modificados, 0 eliminados): informe, 1 prototipo nuevo (`scripts/prototipo_hallazgos_cdefg_6g1.py`), 9 JSON de evidencia, manifiesto y sumas. Verificación: `git diff --name-status <padre>..<commit>` → sólo `A`; `git status --porcelain` sin ficheros modificados de producción; los motores, `lectura_segura_6g1.py`, DSP, fixtures y validadores permanecen byte a byte idénticos. Nota de sesión: el sandbox se reinició durante esta entrega y el árbol local fue re-sincronizado byte a byte (283 ficheros verificados idénticos a GitHub) antes de continuar; ninguna evidencia se re-generó ni alteró.

## 1. HALLAZGO C — sustitución de archivos dentro del directorio anclado

### 1.1 La brecha (C1–C4, `DEMOSTRADO`)

**Concesión explícita: Cris tiene razón.** La ruta procfs del **directorio** (`/proc/self/fd/<fd_run>/<archivo>`) protege los componentes intermedios, pero la **entrada final** se resuelve con semántica `open()` normal y **sigue enlaces simbólicos**. Demostrado con las bibliotecas reales: la misma uid sustituye la entrada final por un symlink y la escritura termina **fuera del acreditado**:

| Caso | API | Resultado |
|---|---|---|
| C1 | `analysis.json` con `open()` | Escritura en el objetivo ajeno (`EXPERIMENTAL_RESULT`) |
| C2 | `mix SDV.wav` con `sf.SoundFile` | WAV completo escrito fuera (44.100 frames en el objetivo ajeno) |
| C3 | `.npy` con `np.open_memmap` | memmap creado fuera (shape verificada en el objetivo) |
| C4 | `engine_log.txt` con `Tee/open` | Log escrito fuera |

**Distinción exigida de garantías:**
- **Frente a OTRA uid:** la brecha **no es explotable** — no puede crear entradas dentro de un directorio `0700` del euid (razonado por permisos; entorno single-uid declarado). EA conserva su valor frente a sustitución de componentes de ruta.
- **Frente a sustitución de componentes de RUTA:** cubierta (EA, segunda revisión).
- **Frente a la MISMA uid:** la entrada final **quedaba desprotegida** → se declara expresamente y se cierra con 1.2/1.3 para las escrituras (con límites residuales declarados en 1.4).

### 1.2 Creación exclusiva (C5, `PASS`)

`os.open(nombre, O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW, 0o600, dir_fd=fd_run)`:
- symlink **precolocado** → `FileExistsError` (no lo sigue, no lo reemplaza) — fail-closed;
- regular **ajeno precolocado** → `FileExistsError` — fail-closed (el motor no crea el archivo si no es el primero con ese nombre dentro del acreditado);
- nombre libre → creado exclusivo, identidad acreditada por `fstat` del descriptor.

### 1.3 Archivo anclado por SU PROPIO descriptor (C6, `PASS`)

Mecanismo propuesto: **conservar el `fd_archivo` de la creación exclusiva** y entregarlo a las bibliotecas:

- **soundfile (WAV real):** objeto archivo sobre `dup(fd_archivo)` con `format='WAV'` — escrito y releído íntegro (44.100 frames). Nota técnica documentada en el prototipo: la ruta procfs de **archivo** en modo `'w'` exige `format=` explícito y libsndfile rechaza el camino con `/` final; el patrón fileobj lo evita (además del probado en A2 vía ruta procfs del directorio con nombre+extensión).
- **numpy `open_memmap` (.npy real):** vía `/proc/self/fd/<fd_archivo>` (creado `O_RDWR|O_EXCL|O_NOFOLLOW`) — memmap con flush correcto.
- **`open()` builtin (JSON/log):** `os.write` sobre el fd (o `os.fdopen(os.dup(fd))`).
- **Sustitución de la entrada ENTRE creación y escritura** (misma uid: `unlink` + symlink con el mismo nombre): las escrituras por el descriptor conservado **ignoran la entrada** y caen íntegras en el inodo acreditado (contenido del symlink: vacío, demostrado en los 3 tipos); la **verificación de identidad por archivo** `fstat(fd_archivo)` vs `fstatat(fd_run, nombre, AT_SYMLINK_NOFOLLOW)` **detecta el swap** (3/3: entrada symlink, identidad distinta) → fail-closed con el symlink conservado como entrada ajena (sin eliminación) y registrado por el checklist (E).

### 1.4 Límite residual declarado (misma uid, contenido)

La misma uid con acceso al proceso puede abrir `/proc/<pid>/fd/<n>` (mismo propietario) y escribir sobre los ficheros anclados **por contenido**: el anclaje por descriptor no protege el **contenido** frente a la misma uid; la detección queda en las comprobaciones de identidad/estabilidad y en la evidencia forense (G). **Declaración explícita exigida por Cris:** la integridad de *contenido* frente a la misma uid está **fuera del modelo de prevención**; el mecanismo garantiza (i) que la escritura del motor no es **desviada** a un objeto ajeno y (ii) que toda sustitución de entrada es **detectable**. Para otra uid: sin vía conocida (razonado por permisos, entorno single-uid).

## 2. HALLAZGO D — compatibilidad con el aborto vigente

### 2.1 El protocolo vigente NO llega (D1, `DEMOSTRADO` con el módulo REAL sin modificar)

Secuencia obligatoria ejecutada con `crear_y_acreditar_dir_6g1` y `abortar_6g1` **reales** (importados, no modificados): acreditar → conservar `fd_run` → sustituir el componente intermedio → excepción → `abortar_6g1(ruta, …)`:

- `_anclar_dir_aborto_6g1` por ruta: apertura `O_NOFOLLOW` tiene éxito (el atacante reconstruyó la ruta) pero `fstat` ≠ acreditado → `identidad_distinta (H1)`, `directorio_acreditado=False`;
- **`ABORT_6G1.json` NO se escribe en ningún sitio** (ni en el acreditado real, ni en el árbol del atacante) — fail-closed correcto, pero **no localiza ni identifica el provisional real** y por tanto no puede invalidar/conservar ni registrar nada en él. Confirmado experimentalmente: el acreditado real contiene `analysis.json` y nada más.

**Conclusión exigida por Cris obtenida:** H1-R2 **no basta** ante sustitución de intermedios: el protocolo vigente queda fail-closed pero ciego. No se aceptó "sigue siendo válido" sin demostrarlo — se demostró lo contrario.

### 2.2 Aborto anclado propuesto (D2, `PASS`)

`abortar_anclado_6g1(fd_padre, nombre_prov, fd_run, motivo, propios)` — propuesta **nueva** (bloque adicional, sin modificar `lectura_segura_6g1.py`):

1. **Anclaje por descriptor:** inventario desde `fd_run` (`os.listdir(fd_run)`, `lstat(dir_fd)`, descenso por subdirectorios con `openat(O_DIRECTORY|O_NOFOLLOW, dir_fd=…)`) — sin ninguna resolución de rutas.
2. **`ABORT_6G1.json` exclusivo y no-follow DENTRO del acreditado real:** `os.open('ABORT_6G1.json', O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW, 0o600, dir_fd=fd_run)`; contenido schema `abort-6g1/3` (mismo contrato: `salidas_invalidadas`, `estado_salidas_invalidadas` conservadas, `resultados_validos=[]`, `analysis_intacto`, `directorio_acreditado=True`, `anclaje_directorio='fd_run (descriptor, sin rutas)'`).
3. **Clasificación:** salidas propias (por nombre/relativo registrado por la corrida) → **invalidadas y conservadas**; enlaces → conservados sin seguir; ajenos/internos → conservados. **Sin eliminación** (C-R1 intacto).
4. **Verificación:** re-lectura anclada del ABORT (`O_NOFOLLOW`, mismo descriptor) con los invariantes del schema.
5. **Ejecutado en la secuencia completa obligatoria:** fds abiertos (WAV+JSON escritos por fd), intermedio sustituido, excepción → `abort_verificado=True`, `analysis.json`/`mix SDV.wav` en `salidas_invalidadas`, `ABORT_6G1.json` dentro del acreditado real, **atacante sin ABORT**, cierre de todos los descriptores → **0 residuales**.

**Integración propuesta (diseño):** el motor añade `fd_run`/`fd_padre`/subdirectorios al registro de recursos; `preparar_aborto_6g1` cierra primero escritores y memmaps (CR vigente), después subdirectorios, `fd_run` y `fd_padre`; el protocolo de aborto llama a la variante anclada **sólo cuando el anclaje por ruta H1 falla** (fallback seguro: primero vigente, si falla el anclaje de ruta → anclado por descriptors conservados); en el camino normal el anclaje por ruta sigue funcionando y el vigente queda intacto. Ninguna eliminación de archivos.

## 3. HALLAZGO E — guarda de completitud (E1, `PASS`)

**Función propuesta:** `checklist_completitud(fd_run, fds_archivos, masks_obligatorio)` — por descriptor, sin `exists()` de rutas: para cada artefacto: existencia (`fstatat` NOFOLLOW), **tipo esperado** (regular/directorio), **no-symlink**, e **identidad vs fd de creación** cuando exista (`(dev,ino)`); subdirectorios: directorio real sin symlink; cualquier fallo → `FalloCorrida6G1` (sin EXIT_OK).

**Matriz de artefactos por motor y modo** (obligatorio/opcional, tipos esperados):

| Artefacto | Hardened | EVO | MQR | Verificaciones |
|---|---|---|---|---|
| `engine_log.txt` | obligatorio | obligatorio | obligatorio | regular, no-symlink |
| `analysis.json` | obligatorio | obligatorio | obligatorio (+ **re-lectura L3578** por ruta anclada) | regular, no-symlink, identidad==fd |
| `analysis.txt` | obligatorio | obligatorio | obligatorio | regular, no-symlink |
| `input_integrity_6g.json` | obligatorio | obligatorio | obligatorio | regular, no-symlink |
| `mix SDV.wav` / `mix SDI.wav` | obligatorio (`full_processing`) | igual | igual | regular, no-symlink, identidad==fd |
| `masks/` (+ .npy) | condicional (`--png`/`--keep-masks`) | igual | **SIEMPRE obligatorio** | directorio real, no-symlink; .npy regulares con identidad==fd si se conservan |
| `candidates/<par>/…` | condicional (`--write-all-candidates`) | igual | igual | directorio real + regulares |
| PNGs (matplotlib) | opcional | opcional | opcional | regulares si presentes |
| `publicacion_6g1.json` (G, propuesto) | obligatorio al publicar | igual | igual | regular, no-symlink, creado por fd_run |

**Demostrado (E1):** (a) corrida completa → `PASS`; (b) `analysis.txt` eliminado → `FAIL`; (c) `analysis.json` sustituido por symlink → `FAIL`; (d) regular recreado por la misma uid (identidad ≠ fd) → `FAIL`; (e) `masks/` obligatorio ausente y WAV ausente → `FAIL` por artefacto; (f) `masks` opcional ausente → sin efecto en su dimensión. `exists()` ni "algún objeto" no bastan: el checklist exige tipo, no-symlink e identidad exacta.

## 4. HALLAZGO F — ciclo de vida de descriptores (F1, `PASS`)

**Tabla de ciclo de vida propuesta (por descriptor):**

| Descriptor | Creación | Holder | Éxito | Excepción | Interrupción | Construcción parcial |
|---|---|---|---|---|---|---|
| `fd_padre` | `crear_y_acreditar_dir_6g1` v2 | motor (`run_experiment`/`_run_core`) | cierre acreditado tras publicar+forense | `preparar_aborto_6g1`→cerrar | `preparar_aborto_6g1`→cerrar | cerrar si ya abierto |
| `fd_run` | v2 (justo tras mkdir) | motor | ídem | ídem | ídem | ídem |
| `fd_masks` | tras `mkdir('masks', dir_fd=fd_run)` | motor (MQR siempre; H/EVO si masks) | ídem | ídem | ídem | si falla su apertura: cerrar fd_run/fd_padre y abortar |
| `fd_candidates` | tras `mkdir('candidates')` | motor si aplica | ídem | ídem | ídem | ídem |
| `fd_archivo` (por salida) | creación exclusiva O_EXCL al abrir cada salida | `CandidateRunner`/Tee v2/write_reports | tras cierre de la biblioteca | ídem | ídem | registrado al crearse (runner parcial D de AI) |
| descriptores de biblioteca | soundfile/numpy vía fileobj-dup o procfs | biblioteca | cerrados por la biblioteca | ídem | ídem | — |

**Reglas demostradas (F1):** cierre **exactamente una vez** (registro idempotente, `cierres_duplicados=0` ante doble llamada); **orden inverso** (archivos → subdirectorios → `fd_run` → `fd_padre`); **sin cierre prematuro** — el WAV queda legible (44.100 frames) mientras la biblioteca lo usa y el cierre propio ocurre después del cierre de la biblioteca (patrón fileobj-dup: la biblioteca cierra su dup, nunca el fd del motor); **construcción parcial** (`candidates` inexistente) → cierra lo abierto → 0 residuales verificados por `/proc/self/fd`.

**Integración en los protocolos vigentes (diseño):** un único registro de recursos por corrida alimenta `cerrar_recursos_corrida_6g1` (CR) y `preparar_aborto_6g1`, con los descriptores nuevos añadidos como recursos de cierre verificado (`cerrar_verificado_6g1`); el cierre normal acreditado (AI) se extiende igual. Cada descriptor se cierra exactamente una vez porque el registro consume la pila y `cerrar_verificado_6g1` ya es idempotente.

## 5. HALLAZGO G — evidencia forense (G1, `PASS`)

Respuesta concreta a los seis puntos:

1. **Dónde:** `publicacion_6g1.json` creado **dentro del provisional** vía `fd_run` (`O_CREAT|O_EXCL|O_WRONLY|O_NOFOLLOW, dir_fd=fd_run`) tras superar el checklist y antes del `renameat2`. Contenido: schema `publicacion-6g1/1`, timestamp, `(dev,ino)` del provisional, `(dev,ino)` del padre, destino solicitado, SHA-256 de los artefactos.
2. **Cuándo:** tras el checklist de completitud (E) y antes de publicar; nada se registra después de la publicación (la identidad del inodo no cambia con el renombrado).
3. **Cómo se garantiza que pertenece a la corrida acreditada:** se crea exclusivamente dentro del inodo acreditado mediante el descriptor conservado (no por ruta); el renombrado **conserva el inodo**, por lo que el registro **viaja con el objeto publicado**; la auditoría externa compara `lstat(dir publicado)` con el inodo registrado **dentro** del propio directorio — demostrado (`coincide=True`, `registro_viajo_con_el_inodo=True`).
4. **Conservación ante aborto:** si no hubo publicación, el registro forense es `ABORT_6G1.json` (D2) escrito por `fd_run` dentro del acreditado; `publicacion_6g1.json` no existe (nunca se publicó). En ambos casos el registro está en el objeto acreditado real, no en rutas sustituibles.
5. **Verificación posterior:** `lstat` del directorio publicado vs inodo del registro + hashes de artefactos vs los registrados; independiente del proceso de la corrida (demostrado).
6. **Protección real frente a la misma uid:** **TAMPERABLE — demostrado en el prototipo** (la misma uid reescribió el registro). **Se declara expresamente: el registro NO es evidencia inmutable frente a la misma uid.** Es fiable frente a otra uid (no puede escribir en el `0700` del euid) y constituye **evidencia de auditoría con coherencia verificable** (inodo-vs-registro), no prevención. La garantía post-return permanece declarada como **limitación de prevención** (segunda revisión, B1/B2), no como protección absoluta. Refuerzo posible (futuro, fuera de alcance): registro espejo en ubicación externa del operador o mecanismos del sistema (audit/journald) — requieren decisión de Cris.

## 6. Pruebas de diseño obligatorias → escenarios ejecutados

| Prueba exigida | Escenario | Veredicto |
|---|---|---|
| Symlink en cada archivo de salida | C1–C4 | `DEMOSTRADO` (brecha, misma uid) + C5/C6 cierran |
| Sustitución de archivo entre creación y escritura | C6 | `PASS` (escritura inmune, identidad detecta) |
| Sustitución durante la escritura | A3 (2.ª revisión, conservado como precedente) + C6 (por fd) | `PASS` |
| Eliminación de un artefacto obligatorio | E1(b) | `FAIL` del checklist (sin EXIT_OK) |
| Sustitución del directorio durante una excepción | D1 (`DEMOSTRADO` del fallo vigente) → D2 (`PASS` anclado) | ambos |
| Aborto con `fd_run` todavía abierto | D2 | `PASS` |
| Cierre de TODOS los descriptores (subdirectorios y archivos) | F1(a)/(b), D2 | `PASS`, 0 residuales |
| Re-verificación B2 y persistencia de la evidencia forense | G1 (+B2 de la 2.ª revisión) | `PASS` |

**Separación exigida:** todas las anteriores son **pruebas de MECANISMO** (prototipo independiente). Las pruebas de **integración real** por motor (RG-FLOW 1–9 de la segunda revisión, con corridas reales de Hardened/EVO/MQR e inyección por envolventes) **siguen pendientes de autorización** y no se presentan como ejecutadas. La compatibilidad de EVO y MQR **no se considera demostrada por similitud de código** (§7).

## 7. Análisis individual por motor (Hallazgos C/D/E/F/G aplicados)

**Hardened** — writers L1396/L1398 → creación exclusiva + `fd_archivo` por WAV; memmaps L1628–1639 (sólo si masks) → `fd_masks` condicional; JSON/log L2130/L1957-1963; re-lectura `input_integrity` L1957-1963 por ruta → anclada; `rmtree(masks)` L1997 tras publicación (post-verificación; mantener ruta normal o anclada — decisión de implementación); aborto: D2 aplicable directamente.

**EVO** — líneas propias verificadas individualmente (L1396/1398, L1683-1709, L2068/2074, L2108, L2241, L2296); mismas adaptaciones que Hardened; **compatibilidad no inferida por similitud**: la implementación incluirá su batería RG-FLOW propia (FLOW-7) antes de cualquier declaración.

**MQR** — writers L2115/L2120; **`masks/` SIEMPRE** (L2361) → `fd_masks` obligatorio en MQR; memmaps L2469–2484; punto exclusivo: **re-lectura de `analysis.json` (L3578)** → con EA se lee por la ruta anclada (`/proc/self/fd/<fd_run>/analysis.json` o por `fd_archivo` conservado en `write_reports`), eliminando la dependencia de la ruta nominal (la lectura en modo `'r'` por procfs ya demostrada en A2/C0); `input_integrity` L2805/2811; publicación en `_run_core` L2838 tras `close_tee` L2830 (CV); el ancla (`fd_padre`,`fd_run`) debe propagarse de `run_experiment` a `_run_core` (patrón `ctx` vigente). Diseño completo **sólo cuando** el flujo MQR con re-lectura anclada pase RG-FLOW-6/8 (futuro).

**Separación demostrado/deducción/desconocido:** `EXPERIMENTAL_RESULT`: C1–C4, C5, C6, D1, D2, E1, F1, G1 (+A1–A3, B1, B2, P0–P7 previos). `DOCUMENTED_FACT`: inventario de líneas y puntos de publicación (código, motores sin modificar). `THEORETICAL_DEDUCTION`: adaptación exacta por motor e integración en protocolos (pendientes de RG-FLOW). `UNKNOWN`/limitaciones: (i) integridad de **contenido** frente a misma uid con acceso a `/proc/<pid>/fd` (fuera del modelo de prevención, detectable por hashes); (ii) matplotlib por rutas ancladas (no probado); (iii) subdirectorios de dos niveles (`candidates/<par>`) por descriptor (patrón de un nivel probado); (iv) Termux/Android (prohibido); (v) rendimiento del pathwalk procfs (por medir en implementación).

## 8. Entregables, manifiesto y SHA-256

| Fichero | Contenido |
|---|---|
| `INFORME_PDA1_HALLAZGOS_CDEFG_6G1.md` | Este informe |
| `scripts/prototipo_hallazgos_cdefg_6g1.py` | Prototipo independiente (C1–C4, C5, C6, D1 con módulo REAL, D2, E1, F1, G1) |
| `evidence/prototipo_hallazgos_cdefg_6g1/escenario_*.json` (8) + `consolidado_prototipo_cdefg.json` | Evidencia (schema `prototipo-cdefg-1/1`) |
| `MANIFEST_PDA1_HALLAZGOS_CDEFG.json` + `SHA256SUMS_PDA1_HALLAZGOS_CDEFG.txt` | Manifiesto y sumas — verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_PDA1_HALLAZGOS_CDEFG.txt \| sha256sum -c -` |

Re-ejecución del prototipo:
```bash
python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/prototipo_hallazgos_cdefg_6g1.py \
    --work /tmp/cdefg_6g1 \
    --out ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/prototipo_hallazgos_cdefg_6g1
```

## 9. Declaración explícita de qué NO se hizo

- **Cero modificaciones en producción**: motores, `lectura_segura_6g1.py`, DSP, fórmulas, fixtures y validadores byte a byte idénticos; el commit sólo añade diseño/prototipo/evidencia (verificado con `git diff --name-status`: sólo `A`).
- `lectura_segura_6g1.py` **no se modificó**: para D1 se importó y se llamó tal cual (fotografía de su comportamiento vigente); D2 es una propuesta en el prototipo.
- No se ejecutaron corridas reales de motores (ni Hardened) en esta entrega: todas las pruebas son de mecanismo; RG-FLOW (incl. EVO y MQR reales) sigue pendiente de autorización.
- No se ejecutaron baterías históricas ni prueba DSP; sin audio real, Android ni Termux; sin fusión, integración ni cherry-pick. 6G.1 ABIERTA.

## 10. PARADA OBLIGATORIA

El trabajo se detiene aquí. La autorización para implementar (PDA-1 + EA + checklist + aborto anclado + registro forense, en la forma que Cris decida) corresponde exclusivamente a Cris tras revisar este informe.

*Fin del informe. Agente en parada.*
