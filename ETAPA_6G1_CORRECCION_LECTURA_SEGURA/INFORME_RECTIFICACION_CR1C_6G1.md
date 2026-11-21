# INFORME DE RECTIFICACIÓN DE EVIDENCIA — CR1c (C-R1 / 6G.1) [C-R1-R]

**Implementador**: Arena.ai · **Responsable técnico**: Cris (implementación C-R1 aceptada técnicamente)
**Fecha**: 2026-11-21 · **Naturaleza**: exclusivamente evidencia y documentación — **cero modificaciones al código de producción**
**Commit de referencia de la implementación aceptada**: `8caa65bbaab2ba57961430f2891e89b34d72ec10` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**No se declara 6G.1 cerrada. La auditoría final de integración sigue pendiente.**

---

## 1. Qué se rectificó

**Prueba CR1c** (`scripts/pruebas_c_r1_6g1.py`, único archivo de pruebas modificado): el mecanismo de inyección anterior interceptaba `os.lstat` **dentro** de `propiedad_de_6g1()` (es decir, *antes* de que el dictamen se computara), por lo que no reproducía exactamente la ventana histórica del hallazgo C-R1. El nuevo mecanismo, según la instrucción:

1. Intercepta `propiedad_de_6g1()`.
2. Ejecuta la **función original** y obtiene su dictamen (sobre el archivo registrado, antes de cualquier sustitución).
3. **Inmediatamente después de un dictamen positivo** sustituye el archivo por otro regular mediante `os.replace()` (el sustituto conserva su propia ruta; se planta una copia bajo el nombre de la salida).
4. **Devuelve el dictamen original** al llamador (`abortar_6g1`).
5. Ejecuta el aborto y comprueba que el sustituto permanece **byte a byte intacto**.

La secuencia registrada por la prueba (`['dictamen_positivo', 'sustitucion_os_replace']`) y la posición del reemplazo dentro del envoltorio (antes del `return` al llamador) demuestran que la sustitución ocurrió **después del dictamen positivo y antes de que el llamador continuara** — exactamente la ventana en la que el código anterior a C-R1 habría ejecutado `os.unlink` sobre el sustituto ajeno. El módulo `lectura_segura_6g1.py` **no** fue modificado para facilitar la prueba.

**Clasificación en el informe de aborto**: la prueba verifica que `salida_concurrente.wav` queda en `salidas_invalidadas` como **clasificación basada en el dictamen obtenido antes de la sustitución** (motivo `salida_parcial_invalidada_y_conservada (sin eliminación; C-R1)`, que no afirma la identidad del objeto posterior); la prueba lo comprueba expresamente (`motivo_sin_afirmar_identidad_posterior`).

## 2. Resultados — batería C-R1 focalizada re-ejecutada (única batería ejecutada)

**13/13 PASS, 0 FAIL, 0 NOT_EXECUTED** con el nuevo mecanismo (`evidence/pruebas_c_r1_6g1.json` + `evidence/matriz_c_r1_6g1.csv` regenerados). CR1c nueva: 9 checks, todos PASS (dictamen positivo original; orden dictamen→sustitución; sustituto byte a byte e intacto en disco; nada eliminado; clasificación por dictamen anterior; motivo sin afirmar identidad posterior; schema `abort-6g1/3`). Baterías históricas (34/26/17/12) **no ejecutadas**.

## 3. Señalización sobre arneses históricos

Los arneses `pruebas_correccion_6g1.py` (batería 34) y `pruebas_e_r2_6g1.py` (batería 12) **conservan expectativas semánticas de `abort-6g1/2`** (sólo se les añadió compatibilidad de *lectura* de versión `/2|/3`): **no deben utilizarse como pruebas de aceptación de `abort-6g1/3` sin actualización**. Sus registros históricos permanecen válidos para sus commits. Señalizado también en `INFORME_C_R1_6G1.md` (§2 y §3).

## 4. Archivos y SHA-256

`SHA256SUMS_RECT_CR1C.txt` (4 ficheros con SHA previo en comentario; verificado con `sha256sum -c`):

| Archivo | Cambio |
|---|---|
| `scripts/pruebas_c_r1_6g1.py` | mecanismo CR1c reescrito (único cambio de código de prueba) |
| `evidence/pruebas_c_r1_6g1.json` | regenerado con el nuevo mecanismo |
| `evidence/matriz_c_r1_6g1.csv` | regenerado con el nuevo mecanismo |
| `INFORME_C_R1_6G1.md` | fila CR1c, registro de iteración y señal de arneses `/2` |

**Sin cambios**: `motores/lectura_segura_6g1.py`, los tres motores, cualquier código de producción, baterías históricas. Sin cambios DSP (la batería re-ejecutada incluye la sanidad ×3 con PCM idéntico a la campaña auditada).

## 5. Commits

- **Commit anterior (base)**: `8caa65bbaab2ba57961430f2891e89b34d72ec10`
- **Commit de esta rectificación**: hijo directo del anterior — ver §7 y el informe de ejecución (verificado con `git rev-parse HEAD^` y contra el remoto tras el push).

## 6. Límites respetados

Cero modificaciones al código de producción; cero cambios DSP; motores originales, carpeta 6G, `main` y `arena/89d5c189-sdv-sdi-sgm` intactos; sin canciones reales ni Elis/Tristania; sin Android/Termux; sin fusionar ramas ni abrir PR; baterías históricas no repetidas (sólo la batería C-R1 focalizada).

## 7. Enlaces (URLs completas)

Informe de rectificación (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_RECTIFICACION_CR1C_6G1.md

Informe C-R1 actualizado:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_C_R1_6G1.md

SHA-256:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_RECT_CR1C.txt

Evidencia actualizada:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_c_r1_6g1.csv
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_c_r1_6g1.json

Prueba rectificada:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_c_r1_6g1.py
