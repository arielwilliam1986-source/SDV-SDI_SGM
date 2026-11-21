# INFORME E-R2 — RECTIFICACIÓN 6G.1 (CONSERVACIÓN DE analysis.json)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21 · **Base obligatoria**: `97d1bd0bd3c430470fa6fa1058fdbcbb61c778f2` (padre directo del commit de esta entrega)
**Alcance**: exclusivamente la conservación de `analysis.json` durante el aborto.

> **Estado**: ENTREGADA, **NO CERRADA**. La aprobación final corresponde a Cris.

---

## 1. Solución elegida (la preferida por la instrucción)

**`analysis.json` NO se modifica durante el aborto.** Toda la información del aborto (schema, motivo, detalle, salidas_invalidadas, conservados, motivos_propiedad) se registra exclusivamente en `ABORT_6G1.json`, que ya tiene creación exclusiva y no-follow anclada al descriptor del directorio (entrega E). La garantía de conservación pasa a ser **estructural**: no existe ninguna escritura dirigida a `analysis.json` en el camino del aborto, por lo que un fallo de `write()`/`fsync()` ya no puede destruir el contenido tras un truncado (el truncado ya no existe).

**Cambio puntual** (`motores/lectura_segura_6g1.py`, **+21/−95** — simplificación neta):

1. Eliminado el bloque de actualización de `analysis.json` que introdujo E-R1 (apertura `O_RDWR|O_NOFOLLOW`, acreditación, `ftruncate`+`lseek`+`write`+`fsync`).
2. Eliminada `_propiedad_fd_acreditada()` — su único uso era el camino de actualización retirado (código muerto en un módulo de seguridad).
3. `abortar_6g1()`: docstring actualizado; comentario E-R2 en el punto exacto donde ocurría la actualización; el registro `info` añade `analysis_intacto=True` y la política ampliada («analysis.json no se modifica durante el aborto (E-R2)»). **El schema se mantiene `abort-6g1/2`** (compatibilidad con la batería de 34, que lo exige; sólo se añaden campos).
4. Sin escrituras por nombre: no se reintroduce ninguna ventana TOCTOU.

## 2. Pruebas específicas — 12/12 PASS, 0 FAIL, 0 NOT_EXECUTED

`evidence/matriz_e_r2_6g1.csv` · detalle por check: `evidence/pruebas_e_r2_6g1.json`.

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| R2a | `analysis.json` propio acreditado: bytes, SHA-256 y `mtime_ns` **idénticos** antes/después; sin campo `abort_6g1`; `ABORT_6G1.json` creado regular con info completa (schema, motivo, `analysis_intacto`, salidas eliminadas); sin rastro de intento de actualización | PASS |
| R2b | `analysis.json` ajeno ordinario: byte a byte intacto; conservado con motivo `registro_interno_conservado`; ABORT con info completa | PASS |
| R2c | `analysis.json` simbólico: externo byte a byte intacto; enlace conservado; ABORT con info completa y motivo de enlace | PASS |
| R2d | Colisión de `ABORT_6G1.json` preexistente: `analysis.json` intacto, ABORT preexistente intacto (SHA), motivo de colisión e info completa conservados en el valor de retorno (canal documentado) | PASS |
| R2e | **Hostil**: `os.ftruncate` y `os.fsync` parcheados para elevar `RuntimeError` → el aborto completa **sin excepción**, `analysis.json` byte a byte intacto y ABORT creado con info completa — demuestra que ninguna de esas llamadas ya ocurre (conservación estructural) | PASS |
| R2-estático | Sin `os.ftruncate`, `O_RDWR` ni `_propiedad_fd_acreditada` en el código; campo `analysis_intacto=True` presente | PASS |
| R2-e2e ×3 | Aborto real (inyección `verificar_raise`) en los tres motores: exit 2, sin directorio definitivo, salidas propias eliminadas, `ABORT_6G1.json` regular con info completa, `analysis.json` presente, **parseable, sin truncar y sin `abort_6g1`** | 3× PASS |
| sanidad ×3 | Corrida feliz: exit 0, publicación única, integridad True, **PCM idéntico a la campaña auditada** (sin cambio DSP) | 3× PASS |

**Nota sobre filas de baterías anteriores**: al desaparecer por diseño la actualización de `analysis.json`, algunas filas específicas de las baterías previas quedan **obsoletas** (no se re-ejecutaron, según la instrucción): en la batería de 26, «E1 unidad» (`motivo_actualizacion_omitida`), «E3 unidad» (`motivo_sin_actualizar`) y «E2 end-to-end» ×3 (`motivo_colision_registrado` vía `analysis.json`); en la batería de 17, «E-R1a» y «E-R1b» (el camino que ejercitaban ya no existe). Las garantías que verificaban (externo/ajeno intactos, ABORT regular, colisión conservada) quedan cubiertas de forma equivalente por R2a–R2d. Documentado para la adjudicación de Cris.

## 3. Identidades y entregables

- **Diff incremental vs `97d1bd0`**: `DIFF_6G1_E_R2.patch` (884 líneas; **reversible verificado**: `patch -R -p1` devuelve el árbol de `97d1bd0` byte a byte — `diff -r` sin diferencias; forward dry-run exit 0).
- **SHA-256 de modificados**: `SHA256SUMS_E_R2.txt` (4 ficheros, con SHA previo en comentario; verificado 4/4 OK).
- Superficie de trabajo (sin entregables auto-referentes): **+724/−95** (módulo +21/−95; batería nueva 467 L; evidencia 249 L).
- **Padre del commit**: `97d1bd0bd3c430470fa6fa1058fdbcbb61c778f2` (verificado con `git rev-parse HEAD^`); HEAD remoto verificado igual al local tras el push.

## 4. Confirmaciones y límites

- **Sin cambios DSP**: la modificación se limita a `lectura_segura_6g1.py` (camino del aborto) y al arnés de pruebas; sanidad ×3 con PCM idéntico a la campaña auditada.
- No se modificaron A–D, F, G ni G-R1 (los motores no requieren cambios: llaman a `abortar_6g1` sin cambio de firma); motores originales, carpeta 6G de referencia, `main` y `arena/89d5c189-sdv-sdi-sgm` intactos; sin Elis/Tristania; sin Android/Termux; baterías anteriores no repetidas.
- **No se declara 6G.1 cerrada.**

## 5. Enlaces (URLs completas)

Informe E-R2 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_E_R2_6G1.md

Diff incremental vs 97d1bd0 (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_E_R2.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_E_R2.txt

Matriz E-R2:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_e_r2_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_e_r2_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
