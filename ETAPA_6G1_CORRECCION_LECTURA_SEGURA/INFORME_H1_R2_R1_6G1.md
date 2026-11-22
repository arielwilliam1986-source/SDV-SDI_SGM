# INFORME H1-R2-R1 — RECTIFICACIÓN 6G.1 (VERIFICACIÓN DEL ARCHIVO DURANTE EL HASH)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD obligatorio**: `2c3227f473a308fd9d7242b0b89936fd31493125` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente `_sha_via_descriptor_6g1()` y su prueba focalizada. Sin cambios DSP; motores originales de 6G, `main` y rama de referencia intactos; baterías históricas 34/26/17/12 no repetidas; A1/A2/A3/B1 sin cambios (dependencia indirecta cubierta por las regresiones).

> **Estado**: ENTREGADA, **NO CERRADA**. No se declaran H1 ni 6G.1 cerradas: la aprobación continúa dependiendo de la auditoría independiente.

---

## 1. Hallazgo

`_sha_via_descriptor_6g1()` obtenía `fstat()` antes de leer, pero no después: comparaba dos estados iniciales (el del `lstat` y el inicial del descriptor) sin demostrar que el archivo permaneció estable **durante toda la lectura**. Además acumulaba el contenido completo en memoria (`datos += bloque`, copias repetidas).

## 2. Corrección (exclusivamente `_sha_via_descriptor_6g1()`, +36/−13)

1. `fstat()` **al abrir** el descriptor (`O_NOFOLLOW` + `dir_fd`, anclado y sin rutas).
2. Comprobación de que corresponde al **mismo archivo regular** identificado por `lstat` (identidad `st_dev/st_ino` + `S_ISREG`).
3. SHA-256 por **actualización incremental** de `hashlib` (`h.update(bloque)`) — sin acumular el archivo completo en memoria.
4. **Segundo `fstat()`** al terminar la lectura.
5. Comparación de **identidad, tamaño, `mtime_ns` y `ctime_ns`** entre ambos estados (`ctime_ns` detecta también cambios de metadatos con tamaño constante; disponible desde Python 3.3 → compatible con 3.8).
6. Si cualquier dato cambia → **(None, motivo)**: el SHA **no se acredita como válido** (motivos nuevos: `identidad cambiada durante la lectura (H1-R2-R1)` / `archivo modificado durante la lectura (H1-R2-R1): SHA no acreditable`).
7. Se mantienen `O_NOFOLLOW`, `dir_fd` y el descriptor anclado; sin rutas.

Los llamadores (`_clasificar_entrada_6g1`) y las garantías C-R1 no cambian: un SHA no acreditable clasifica la entrada como conservada con su motivo (fail-closed).

## 3. Prueba focalizada — 2/2 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_h1_r2_r1_6g1.csv` · detalle: `evidence/pruebas_h1_r2_r1_6g1.json`. Verificación sobre el estado real en disco (bytes, SHA-256, inodos).

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| **R1a** | Modificación **determinista** durante el cálculo del SHA (gancho sobre `os.read`: tras el primer bloque leído se sobrescribe el archivo in situ, misma longitud, vía `pwrite` con `dir_fd` — sin sustituir el inodo): la modificación ocurre **después de comenzar la lectura** (bloque 1 de ≥2); el **descriptor siguió apuntando al mismo inodo** (inodo antes == después y el error disparado es de estabilidad, no de identidad); la **verificación posterior detectó el cambio** (`archivo modificado durante la lectura (H1-R2-R1)`); **no se devuelve SHA válido** (`sha is None`); el archivo **no se eliminó** y su contenido final es **exactamente el previsto** por la prueba (`XX` + resto original — única alteración) | PASS |
| **R1b** | Archivo **estable**: sin error y el SHA devuelto **coincide** con el calculado independientemente (`hashlib` sobre los bytes); el archivo permanece intacto tras el hash | PASS |

**Regresiones ejecutadas (sólo las autorizadas)**: batería **H1-R2** (A1/A2/A3/B1): **4/4 PASS** · batería **H1** (H1a/H1b/H1c + tres flujos de aborto + sanidad ×3): **10/10 PASS** · batería **C-R1**: **13/13 PASS** (evidencias regeneradas). Baterías históricas 34/26/17/12: no ejecutadas. Sin cambios DSP (sanidad ×3 con PCM idéntico a la campaña auditada, incluida en la regresión H1).

## 4. SHA-256, DIFF y commits

- `SHA256SUMS_H1_R2_R1.txt` (9 ficheros con SHA previo en comentario; verificado con `sha256sum -c`: 9/9 OK).
- `DIFF_6G1_H1_R2_R1.patch`: diff incremental **reversible** respecto de `2c3227f473a308fd9d7242b0b89936fd31493125` (`patch -R -p1` → árbol base byte a byte; forward dry-run exit 0).
- **Padre directo**: `2c3227f473a308fd9d7242b0b89936fd31493125` · **Nuevo commit**: hijo directo (SHA completo en el informe de ejecución).

## 5. Límites respetados

Sin STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP; los tres motores y sus parámetros **sin cambios** (la corrección es interna al módulo compartido); motores originales de 6G, carpeta 6G de referencia, `main` y otras ramas intactos; A1/A2/A3/B1 sin modificar; sin audio real, Elis/Tristania ni Android/Termux; sin fusionar ni abrir PR; baterías históricas no repetidas. **No se declaran H1 ni 6G.1 cerradas.**

## 6. Enlaces (URLs completas)

Informe H1-R2-R1 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H1_R2_R1_6G1.md

Diff incremental vs 2c3227f (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H1_R2_R1.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H1_R2_R1.txt

Matriz H1-R2-R1:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h1_r2_r1_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h1_r2_r1_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
