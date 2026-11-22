# INFORME H2 — RECTIFICACIÓN 6G.1 (APERTURA SEGURA DEL MIX VALIDADO)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD obligatorio**: `16a64058f05316b03245ffacdda4daed084bea05` (H1-R2-R2-R; padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente la vinculación entre la validación inicial del Mix (probe/SHA) y la apertura del descriptor usado por el DSP. Sin cambios DSP (STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros intactos); motores originales de 6G y carpeta de referencia intactos; `main`, `arena/89d5c189-sdv-sdi-sgm` y otras ramas sin tocar; baterías históricas 34/26/17/12 no repetidas; sin canciones reales, Elis/Tristania, Android/Termux; sin fusionar, integrar ni abrir PR.

> **Estado**: ENTREGADA, **NO CERRADA**. No se declaran H2, H1 ni 6G.1 cerradas: la aprobación técnica corresponde a Cris y la decisión final a Will.

---

## 1. Hallazgo y corrección

Tras la validación inicial (probe + SHA-256 por ruta) existía una **ventana hasta la apertura del descriptor de procesamiento** en la que el objeto validado podía ser sustituido por otro en la misma ruta. `MixHandle` sólo contrastaba el **contenido** (SHA) contra el sondeo: un archivo **distinto** con contenido idéntico habría pasado; una **FIFO** colocada en la ventana habría bloqueado la apertura `O_RDONLY` antes del `fstat`; y ni el sondeo ni la apertura verificaban la **identidad del objeto** (dispositivo/inodo) ni la **estabilidad** del archivo durante la validación y el cálculo del SHA.

**Corrección** (tres piezas, modelo H2-A/B/C):

* **H2-A — Identidad del objeto validado.** `probe_file()` de los **tres motores** (Hardened, EVO, MQR) captura y conserva en `FileInfo` la identidad del objeto validado: `device`, `inode`, `mtime_ns`, `ctime_ns` (nuevos campos). `MixHandle.__init__` recibe `identidad_esperada=(device, inode)` a través de `abrir_mix(..., identidad_esperada=...)` y, tras el `fstat` de la apertura, **exige** `(st_dev, st_ino)` coincidente con la validada; si difiere → `MixCambiado` con el motivo explícito «La identidad del Mix abierto no coincide con la validada (H2-A): … un archivo distinto con SHA idéntico no es aceptable». El SHA coincidente **NO aprueba la identidad**. El modelo exacto de la fase: la identidad se obtiene por `os.stat()` sobre la ruta al inicio de `probe_file()` (antes de `sf.info` y del SHA por ruta) y la estabilidad se verifica con un segundo `os.stat()` tras el SHA (H2-C); el objeto validado es el que el validador abrió por ruta en ese intervalo, y esa identidad — no sólo el contenido — es la que se transmite y exige al abrir el descriptor de procesamiento.
* **H2-B — Apertura no bloqueante fail-closed.** `MixHandle.__init__` abre con `os.O_RDONLY | os.O_NONBLOCK`: una sustitución por FIFO entre la validación y la apertura devuelve el descriptor al instante y el `fstat` siguiente la clasifica como no regular → `MixCambiado` («El Mix no es un archivo regular (H2-B: apertura no bloqueante ante FIFO)»), sin leer ni procesar el objeto no regular. El descriptor queda **anclado** durante todo el procesamiento y la guarda final existente (`verificar()` + `ruta_apunta_al_mismo_objeto()`) se conserva.
* **H2-C — Hash estable.** `_sha_fd(fd)` se sustituye por `_sha_fd_estable(fd)`: `fstat` **antes y después** de la lectura incremental (identidad `st_dev/st_ino`, tamaño, `mtime_ns`, `ctime_ns`); cualquier cambio → SHA **no acreditado** (`MixCambiado` «H2-C: archivo modificado durante la lectura del SHA…»). La misma verificación se aplica en `probe_file()` de los tres motores (error «H2-C: el archivo cambió durante la validación; identidad y SHA-256 no acreditables» → `info.valid=False`) y en la guarda final `verificar()` (nuevo campo `estable` del dictámen).

**Política de enlaces simbólicos (sin cambio, documentada):** la apertura del Mix **sigue** enlaces legítimos (como toda la fase de validación, que abre por ruta con `soundfile`); el anclaje se logra **por identidad del objeto abierto** (H2-A), no con `O_NOFOLLOW`. Rechazar symlinks rompería instalaciones legítimas sin aportar seguridad frente a sustitución (el atacante con capacidad de sustituir la entrada también puede sustituir el objetivo del enlace); la política queda documentada en el docstring del módulo y en `MixHandle.__init__`. No hay cambio de política implícito: el comportamiento symlink es idéntico al previo a H2.

## 2. Pruebas deterministas — 10/10 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_h2_6g1.csv` · detalle: `evidence/pruebas_h2_6g1.json` (schema `pruebas-h2-6g1/1`). Arnés independiente `scripts/pruebas_h2_6g1.py`. Todas verifican el **estado real en disco** (lstat/bytes/SHA-256), no sólo los retornos:

| Prueba | Motor | Checks | Resultado |
|---|---|---|---|
| **T1** — validado→FIFO entre validación y apertura | `lectura_segura_6g1` | 9/9 | PASS |
| **T2** — gemelo byte a byte con distinto inodo | `lectura_segura_6g1` | 7/7 | PASS |
| **T3a** — `probe_file` captura identidad (H2-A) | Hardened / EVO / MQR | 5/5 ×3 | PASS ×3 |
| **T3b** — apertura feliz + guarda final estable | `lectura_segura_6g1` | 8/8 | PASS |
| **T4** — mutación durante la validación | Hardened | 4/4 | PASS |
| **H2-e2e** — producción, DSP intacto | Hardened / EVO / MQR | 5/5 ×3 | PASS ×3 |

* **T1**: el objeto validado (WAV regular con identidad+SHA estilo `probe_file`) se sustituye por una FIFO **en el punto exacto** (envoltorio de `L.abrir_mix` que sustituye antes de delegar); bajo vigía temporal (`setitimer` 8 s) la apertura **no se bloquea**, se rechaza fail-closed (motivo no regular H2-B), **sin SHA acreditado, sin handle y sin salidas de audio** (`['mix.wav', 'mix_validado_aside']`), la FIFO queda **sin contenido escrito por nadie** y el objeto validado renombrado aparte permanece **byte a byte intacto**. **2ª vía (anclaje 6G.1)**: con el objeto validado registrado (`registrar_propio_6g1` estable + `acreditar_dir_6g1`), la clasificación por descriptor `_clasificar_entrada_6g1` dictamina la FIFO **no-propia por `identidad_distinta`** y el objeto validado **`propiedad_acreditada`** — dos mecanismos independientes (H2 y 6G.1) rechazan el sustituto.
* **T2**: sustitución por OTRO regular **byte a byte idéntico** con distinto inodo antes de abrir MixHandle: el arnés comprueba que el SHA del impostor **coincide** con el validado y, aun así, la apertura se rechaza por identidad (motivo H2-A), sin handle; el objeto validado original permanece vivo e intacto al margen.
* **T3a**: `probe_file()` de los tres motores devuelve `device`/`inode` != 0 coincidentes con `os.stat`, `mtime_ns`/`ctime_ns` capturados y el SHA-256 correcto.
* **T3b**: `abrir_mix` con identidad+SHA del probe supera la apertura; `identity_validada=True`, identidad conservada igual al probe, SHA sobre descriptor igual al probe, mismo inodo legible por soundfile, guarda final `verificar()` con `unchanged=True` y **`estable=True`** (H2-C), `ruta_apunta_al_mismo_objeto` afirmativo, `close()` idempotente y disco sin cambios.
* **T4**: mutación inyectada dentro de la ventana de validación (envoltorio de `sha256_file` del motor Hardened): `probe_file` marca el error H2-C, `info.valid=False` y `validate_mix` rechaza; el SHA del contenido mutado queda **no acreditado**.
* **H2-e2e ×3**: corrida feliz de producción por motor: `exit 0`, publicación única, integridad `after.unchanged=True` **y `after.estable=True`** (evidencia H2-C del MixHandle reformado en producción) y **PCM idéntico a la campaña auditada** (`contenedores_6g1.json`) — el DSP no cambió.

**Regresiones autorizadas (sólo éstas)**, evidencias regeneradas en `evidence/`: batería **H1-R2-R2**: **1/1 PASS** · batería **H1-R2**: **4/4 PASS** · batería **H1**: **10/10 PASS** · batería **C-R1**: **13/13 PASS**. Baterías históricas 34/26/17/12: no ejecutadas.

## 3. SHA-256, DIFF y commits

- `SHA256SUMS_H2.txt` (**13 ficheros** — 3 motores, módulo compartido, 2 docs rectificados, informe H2, arnés de pruebas y 5 evidencias: JSON+CSV de la batería nueva y los 3 JSON regenerados de las regresiones, cuyos CSV quedan byte a byte idénticos al no cambiar sus filas — con SHA previo en comentario; verificado con `sha256sum -c`: **13/13 OK**).
- `DIFF_6G1_H2.patch`: diff incremental **reversible** respecto de `16a64058f05316b03245ffacdda4daed084bea05` (`patch -R -p1` → árbol base byte a byte; forward dry-run exit 0).
- **Padre directo**: `16a64058f05316b03245ffacdda4daed084bea05` · **Nuevo commit**: hijo directo (SHA completo en el informe de ejecución).
- **Resumen exacto de archivos** (numstat vs base): `motores/lectura_segura_6g1.py` +86/−16 · `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` +17/−2 · `motores/MOTOR_SEP_SDV-SDI_EVO.py` +17/−2 · `motores/sdv_sdi_mqr_engine.py` +17/−2 · `INDICE_PARA_AUDITORIA_6G1.md` +12/−5 · `INFORME_IMPLEMENTACION_6G1.md` +21/−6 · `scripts/pruebas_h2_6g1.py` nuevo · `evidence/pruebas_h2_6g1.json` + `evidence/matriz_h2_6g1.csv` nuevos · evidencias regeneradas de regresiones (`pruebas_h1_r2_r2_6g1.json`, `pruebas_h1_r2_6g1.json`, `pruebas_c_r1_6g1.json`; los CSV de regresiones se regeneran byte a byte idénticos al no cambiar sus filas).

## 4. Rectificación documental (únicamente los pasajes señalados)

* `INDICE_PARA_AUDITORIA_6G1.md`: pregunta 3 («¿Quedan salidas parciales tras abortar?») e ítem 3 de la lista de verificación describían la semántica `abort-6g1/2` (borrado de salidas acreditadas). Rectificados al comportamiento **vigente C-R1** (`abort-6g1/3`: nada se elimina; salidas propias invalidadas y conservadas; `resultados_validos` vacío), dejando constancia expresa de que las filas/casos citados son registro **histórico** de la semántica /2. No se reescribió ninguna otra parte ni ningún informe histórico de pruebas.
* `INFORME_IMPLEMENTACION_6G1.md`: §2.1 (bullet de `abortar_6g1` con la «regla de borrado conservadora» histórica) rectificado al comportamiento vigente (no elimina nada; esquema /3; invalidadas y conservadas; `analysis.json` intacto E-R2), conservando el texto histórico entre corchetes como referencia; §5.3 punto 3 (corrección C) se conserva como referencia histórica y se añade la nota [6G.1-R/C-R1 — política vigente] con el estado actual y la referencia a `INFORME_C_R1_6G1.md`.

## 5. Límites respetados

Sin modificaciones en STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP: los cambios DSP-visible son cero (sanidad e2e ×3 con PCM idéntico a la campaña auditada). Los tres motores de la carpeta de corrección reciben únicamente la captura de identidad en `FileInfo`/`probe_file`, la verificación de estabilidad y el paso de `identidad_esperada` en las dos llamadas de apertura de cada motor (6 call sites en total). Motores originales de 6G y carpeta de referencia intactos (fuera de `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/` no se modificó ningún fichero); `main` intacto; sin canciones reales ni Elis/Tristania; sin Android/Termux; sin fusionar, integrar, cherry-pick ni PR; baterías históricas no repetidas; H2-A/B/C aplicados sin alterar H1, H1-R2, H1-R2-R1, H1-R2-R2, C-R1 ni E-R2 (regresiones en verde). **No se declaran H2, H1 ni 6G.1 cerradas.**

## 6. Enlaces (URLs completas, texto plano — sin markdown)

```
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_EVO.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/sdv_sdi_mqr_engine.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_h2_6g1.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h2_6g1.json
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h2_6g1.csv
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H2_6G1.md
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H2.txt
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H2.patch
```
