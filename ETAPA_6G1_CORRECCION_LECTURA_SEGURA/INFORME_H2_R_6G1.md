# INFORME H2-R — RECTIFICACIÓN 6G.1 (VALIDACIÓN INICIAL ANCLADA AL MISMO OBJETO)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD obligatorio**: `af804244f4009b1b88e7cf97035b108ad5f2ce2a` (H2; padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente la fase `probe_file()` de los tres motores y los validadores auxiliares estrictamente necesarios (`audio_integridad_6g.verify_audio`, API de hash por descriptor del módulo compartido). Sin cambios DSP (STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros intactos); motores originales de 6G y carpeta de referencia intactos; `main`, `arena/89d5c189-sdv-sdi-sgm` y otras ramas sin tocar; baterías históricas 34/26/17/12 no repetidas; sin canciones reales, Elis/Tristania, Android/Termux; sin fusionar, integrar, cherry-pick ni abrir PR.

> **Estado**: ENTREGADA, **NO CERRADA**. No se declaran H2-R, H2, H1 ni 6G.1 cerradas: la aprobación técnica corresponde a Cris y la decisión final a Will.

---

## 1. Hallazgo y corrección

En los tres motores, `probe_file()` operaba sobre la **ruta**: `os.stat(path)` (identidad), `sf.info(path)` (metadatos), `_verify_audio_6g(path, sfi)` (contenedor), `sha256_file(path)` (SHA) y un segundo `os.stat(path)` (estabilidad). Cada operación reabría la ruta de forma independiente: la comparación entre los dos `stat()` **no garantiza que las operaciones intermedias hayan leído el mismo objeto** — una sustitución temporal de la ruta, restaurada antes del segundo `stat()`, escapaba a esa comprobación y podía mezclar metadatos del sustituto con identidad/SHA del original.

**Corrección**:

* **H2-R-A — Un único objeto abierto durante el probe.** `probe_file()` abre el Mix **una sola vez al comienzo** con `os.O_RDONLY | os.O_NONBLOCK` (sin bloqueos ante FIFO), comprueba por `fstat()` que el descriptor es un **archivo regular** y captura identidad y estado inicial **desde el descriptor** (`st_dev`, `st_ino`, `st_size`, `st_mtime_ns`, `st_ctime_ns`; también `info.size_bytes` procede ahora del objeto, no de `os.path.getsize`). El descriptor se mantiene durante toda la validación: los metadatos se obtienen con `sf.info('/proc/self/fd/N')` (referencia respaldada por el descriptor), las validaciones de contenedor se ejecutan sobre esa misma referencia (`_verify_audio_6g(proc, sfi, ext_ref=path)`) y el SHA-256 se calcula con la nueva API pública `sha_fd_estable_6g1(fd)` del módulo compartido (lectura incremental sobre `dup(fd)` + `seek(0)`, con fstat antes/después). **La ruta del usuario nunca se reabre durante la validación.**
* **H2-R-B — Estabilidad durante toda la validación.** Al finalizar todas las operaciones, `fstat()` sobre el descriptor original compara `st_dev`, `st_ino`, `st_size`, `st_mtime_ns`, `st_ctime_ns` contra el estado inicial. Si el objeto no es regular, no se puede validar o cambia durante la operación → **fail-closed**: `info.valid=False` y SHA **no acreditado** (`info.sha256=""`). Todos los campos `FileInfo` proceden del objeto realmente validado, no de consultas independientes a la ruta.
* **Auxiliar adaptado de forma acotada** (`audio_integridad_6g.py`, dentro de la carpeta de corrección): `verify_audio(path, decoder=None, ext_ref=None)` — nuevo parámetro opcional `ext_ref` que usa el **nombre** de la ruta del usuario para la política de extensión cuando `path` es una referencia respaldada por descriptor (`/proc/self/fd/N`). El contenedor y **todas** las validaciones (6F WAV estricta, STREAMINFO/MD5 FLAC, geometría, subtipos) se leen del objeto anclado; **sin `ext_ref` el comportamiento es idéntico al anterior** — ninguna validación se debilita. `container_of` (cabecera) y `wav_integridad_6f`/`_inspect_flac` ya eran internamente por descriptor y funcionan con `/proc/self/fd/N` sin cambios.
* **API pública del módulo compartido**: `sha_fd_estable_6g1(fd)` (envoltorio documentado de `_sha_fd_estable`), importada por los tres motores junto con `import stat` (añadido; no estaba).
* **Política de enlaces simbólicos SIN CAMBIO**: se siguen enlaces legítimos y se ancla el objeto al que resuelve la apertura inicial (documentado en el docstring del módulo y de cada `probe_file`). No se debilitan las validaciones de WAV/FLAC, geometría ni integridad.

## 2. Pruebas deterministas — 15/15 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_h2_r_6g1.csv` · detalle: `evidence/pruebas_h2_r_6g1.json` (schema `pruebas-h2-r-6g1/1`). Arnés independiente `scripts/pruebas_h2_r_6g1.py`; sustituto sintético (48 kHz / mono / 44100 frames, PCM_16) con metadatos distinguibles del fixture (44100 Hz / estéreo / 88200). Todas verifican el **estado real en disco y el objeto leído**, no sólo mensajes:

| Prueba | Motores | Checks | Resultado |
|---|---|---|---|
| **T1** — sustitución temporal durante los metadatos | Hardened / EVO / MQR | 7/7 ×3 | PASS ×3 |
| **T2** — sustitución temporal durante el SHA | Hardened / EVO / MQR | 7/7 ×3 | PASS ×3 |
| **T3** — regresión estable (mismo objeto) | Hardened / EVO / MQR | 8/8 ×3 | PASS ×3 |
| **T4** — regresión FIFO al comenzar el probe | Hardened / EVO / MQR | 5/5 ×3 | PASS ×3 |
| **H2-R-e2e** — producción, DSP intacto | Hardened / EVO / MQR | 5/5 ×3 | PASS ×3 |

* **T1** (rama «rechaza la validación», determinista): la ruta se sustituye temporalmente por otro WAV válido (rename con restauración previa al fin del probe), inyectada en el punto exacto de `sf.info`. El `rename` de la sustitución **actualiza `st_ctime` del objeto movido** (Linux) y **H2-R-B lo detecta** → rechazo fail-closed (`valid=False`, SHA no acreditado). Demostrado además: los campos presentes provienen del **objeto anclado** (identidad e inodo originales; metadatos 44100/2/88200 del original, **no** los 48000/1/44100 del sustituto — jamás se mezclan), y la ruta queda restaurada byte a byte con su inodo original. El arnés fuerza el determinismo con un `sleep(0.05)` previo (garantiza que el delta de ctime supere la granularidad de sellado).
* **T2** (rama «el SHA corresponde al objeto anclado», determinista): la ruta `mix.wav` es un enlace simbólico legítimo al Mix regular `mix_original.wav`; durante el cálculo del SHA el enlace se **re-dirige atómicamente** (`rename`) al sustituto de contenido distinto y se restaura antes de devolver. El objeto original **jamás se toca**: el probe completa **válido** con identidad, metadatos y **SHA del objeto anclado** (`sha_probe == sha_original != sha_sustituto`) — demostración expresa de que el SHA del sustituto **no** se acredita como si perteneciera al original, y de que el probe nunca reabrió la ruta.
* **T3**: Mix WAV estable supera el probe en los tres motores con identidad (`device/inode`), `mtime_ns/ctime_ns`, tamaño, metadatos (`sf.info` de referencia) y SHA-256 correspondientes al **mismo objeto** (cotejo contra el disco real); `validate_mix` lo acepta y el disco queda sin cambios.
* **T4**: FIFO presente al comenzar el probe → rechazada **sin bloqueo** (`O_NONBLOCK`; vigía `setitimer` 8 s, t≈0.000 s), `valid=False`, **sin SHA acreditado** (`sha256=""`), motivo «H2-R: el objeto no es un archivo regular… fail-closed», la FIFO queda sin contenido escrito por nadie y **no se crea ninguna salida**.
* **H2-R-e2e ×3**: corrida feliz de producción con el probe anclado: `exit 0`, publicación única, integridad `after.unchanged=True` y `after.estable=True`, **PCM idéntico a la campaña auditada** (`contenedores_6g1.json`) — el DSP no cambió.

**Regresiones focalizadas autorizadas** (evidencias regeneradas en `evidence/`): batería **H2**: **10/10 PASS** · batería **H1-R2-R2**: **1/1 PASS** · batería **H1-R2**: **4/4 PASS** · batería **H1**: **10/10 PASS** · batería **C-R1**: **13/13 PASS**. Baterías históricas 34/26/17/12: no ejecutadas.

**Actualización señalizada del arnés H2** (`scripts/pruebas_h2_6g1.py`, test T4): el gancho de mutación envolvía `sha256_file` del motor, que el probe ya no usa; ahora envuelve `_sha_fd_estable_6g1` (mismo punto de validación) y el marcador acepta H2-C o H2-R. La INTENCIÓN de la prueba es idéntica (mutación durante la validación → SHA no acreditado, fail-closed) y pasa 4/4 checks.

## 3. SHA-256, DIFF y commits

- `SHA256SUMS_H2_R.txt` (**16 ficheros** — 3 motores, módulo compartido, auxiliar `audio_integridad_6g`, informe H2 (adenda marcada), informe H2-R, ambos arneses y 7 evidencias (JSON+CSV nuevos y 5 JSON regenerados de las regresiones, cuyos CSV quedan byte a byte idénticos al no cambiar sus filas) — con SHA previo en comentario; verificado con `sha256sum -c`: **16/16 OK**).
- `DIFF_6G1_H2_R.patch`: diff incremental **reversible** respecto de `af804244f4009b1b88e7cf97035b108ad5f2ce2a` (`patch -R -p1` → árbol base byte a byte; forward dry-run exit 0).
- **Padre directo**: `af804244f4009b1b88e7cf97035b108ad5f2ce2a` · **Nuevo commit**: hijo directo (SHA completo en el informe de ejecución).
- **Resumen exacto de archivos** (numstat vs base): `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` +64/−34 · `motores/MOTOR_SEP_SDV-SDI_EVO.py` +64/−34 · `motores/sdv_sdi_mqr_engine.py` +63/−32 · `motores/audio_integridad_6g.py` +8/−2 · `motores/lectura_segura_6g1.py` +16/−0 · `scripts/pruebas_h2_6g1.py` +14/−11 · `scripts/pruebas_h2_r_6g1.py` nuevo · `evidence/pruebas_h2_r_6g1.json` + `evidence/matriz_h2_r_6g1.csv` nuevos · 4 evidencias JSON regeneradas (`pruebas_h2_6g1.json` +4/−4, `pruebas_c_r1_6g1.json` +3/−3, `pruebas_h1_r2_6g1.json` +1/−1, `pruebas_h1_r2_r2_6g1.json` +1/−1) · `INFORME_H2_6G1.md` adenda marcada · `INFORME_H2_R_6G1.md` nuevo.

## 4. Confirmación de invariantes

* **H2-B / H2-A / H2-C se mantienen**: batería H2 10/10 (T1 validado→FIFO ante MixHandle; T2 gemelo con SHA idéntico rechazado por identidad; T3a identidad en probe — ahora capturada por descriptor; T3b apertura feliz + guarda estable; T4 mutación → SHA no acreditado; e2e ×3 con `estable=True`). `MixHandle` no se modificó en esta ronda.
* **H1, H1-R2, H1-R2-R1, H1-R2-R2 se mantienen**: baterías 10/10, 4/4, (R1 cubierta por las cadenas e2e) y 1/1 en verde.
* **C-R1 y E-R2 se mantienen**: batería C-R1 13/13 (aborto sin borrado, semántica /3, `analysis.json` intacto, propiedad acreditada).
* **Sin cambios DSP ni en fuentes originales**: fuera de `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/` no se modificó ningún fichero (`git status`); sanidad e2e ×3 con PCM byte a byte idéntico a la campaña auditada.

## 5. Límites respetados

Cambios aplicados sólo en los tres motores de la carpeta de corrección y en los auxiliares estrictamente necesarios (`audio_integridad_6g.verify_audio` con `ext_ref`; `sha_fd_estable_6g1` en el módulo compartido). Sin tocar STFT/ISTFT/FFT/hop/chunking/máscaras/consenso/fórmulas/ganancias/polaridad/parámetros DSP; motores originales fuera de la carpeta intactos; `main` y otras ramas intactos; sin canciones reales ni Elis/Tristania; sin Android/Termux; sin fusionar, integrar, cherry-pick ni PR; baterías históricas no repetidas; sólo regresiones focalizadas. **No se declaran H2-R, H2, H1 ni 6G.1 cerradas.**

## 6. Enlaces (URLs completas, texto plano — sin markdown)

```
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H2_R_6G1.md
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/audio_integridad_6g.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_h2_r_6g1.py
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h2_r_6g1.json
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h2_r_6g1.csv
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H2_R.txt
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H2_R.patch
```
