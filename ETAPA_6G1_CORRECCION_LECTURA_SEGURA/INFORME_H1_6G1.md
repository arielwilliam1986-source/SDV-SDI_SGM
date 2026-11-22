# INFORME H1 — RECTIFICACIÓN 6G.1 (ANCLAJE DEL DIRECTORIO DE ABORTO)

**Implementador**: Arena.ai · **Responsable técnico**: Cris · **Decisor final**: Will
**Fecha**: 2026-11-21
**HEAD de partida obligatorio**: `4960b50c4f80b2c846a10bef5d42a86ca1971839` (padre directo del commit de esta entrega, verificado con `git rev-parse HEAD^`)
**Alcance**: exclusivamente el anclaje del directorio de aborto y su documentación. Sin cambios DSP; motores originales de 6G, `main` y rama de referencia intactos; baterías históricas 34/26/17/12 no repetidas.

> **Estado**: ENTREGADA, **NO CERRADA**. La aprobación final corresponde a Cris tras la auditoría independiente.

---

## 1. Defecto H1

`abortar_6g1()` abría el directorio de aborto con `os.open(str(run_dir), os.O_RDONLY | os.O_DIRECTORY)`: **sin `O_NOFOLLOW`** y **sin acreditar** que el directorio abierto siguiera siendo el provisional creado por la corrida. Un proceso concurrente podía sustituir la ruta por un enlace simbólico antes de esa apertura; el `O_NOFOLLOW` posterior sobre `ABORT_6G1.json` no protegía contra la sustitución del directorio padre (el ABORT habría aterrizado en el objetivo externo).

## 2. Solución implementada (`motores/lectura_segura_6g1.py` +3 motores)

1. **Acreditación en la creación** — nueva función pública `acreditar_dir_6g1(path)`: registra `(st_dev, st_ino)` del provisional (lstat, sin seguir enlaces) en el registro por corrida. Llamada por `create_run_dir()` de **los tres motores** inmediatamente después del `mkdir` exclusivo (F). La acreditación se asocia a la corrida y se limpia con `reiniciar_registro_6g1()` (una corrida nueva no hereda la del anterior).
2. **Apertura sin seguir enlaces** — nueva función `_anclar_dir_aborto_6g1(run_dir)`: abre con `os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW` (disponible y usado en todo el módulo).
3. **Verificación por descriptor** — `fstat(fd)` comparado contra la identidad acreditada: coincide → descriptor validado; no coincide, es un enlace (ELOOP), no es accesible (ENOENT/EACCES), no es directorio o `fstat` falla → fd cerrado y **fail-closed**.
4. **Fail-closed sin escritura** — si el anclaje falla, `abortar_6g1()` **no escribe `ABORT_6G1.json` en esa ubicación ni sigue el enlace**; devuelve el registro `/3` con `directorio_acreditado: False`, `anclaje_directorio: <motivo>`, `salidas_invalidadas: []`, `resultados_validos: []`, `conservados: []` (nada eliminado, ninguna salida válida declarada; el motivo original del aborto se conserva en el registro devuelto al llamador).
5. **Sin re-apertura por ruta** — cuando el anclaje es correcto, el **inventario** y la **escritura** de `ABORT_6G1.json` (`O_CREAT|O_EXCL|O_NOFOLLOW + dir_fd`) operan sobre **el mismo descriptor ya validado** (inventario recursivo con `os.listdir(fd)` + `os.lstat(…, dir_fd)` + apertura de subdirectorios con `O_NOFOLLOW` anclada al descriptor; ninguna parte del aborto recorre la ruta después de la acreditación).
6. **Preservación íntegra de C-R1 y E-R2** — ningún archivo se elimina; `analysis.json` permanece intacto; los parciales se conservan; `resultados_validos` vacío; el esquema sigue siendo **`abort-6g1/3`** (sólo campos aditivos `directorio_acreditado` y `anclaje_directorio`).
7. **Documentación corregida** — el docstring inicial del módulo ya no afirma que el aborto elimina archivos acreditados (ahora describe C-R1/E-R2/H1); el docstring de `abortar_6g1` incorpora el párrafo H1; el encabezado y §6 de `INFORME_C_R1_6G1.md` distinguen ahora la base histórica `71cfe4c` (padre del commit de implementación `8caa65b`) del padre directo real de la rectificación `4960b50` (`8caa65b`). **No se modificaron registros históricos de pruebas.**

## 3. Pruebas focalizadas — resultados

**Batería H1 (nueva, `scripts/pruebas_h1_6g1.py`): 10/10 PASS, 0 FAIL, 0 NOT_EXECUTED** (`evidence/matriz_h1_6g1.csv`; detalle: `evidence/pruebas_h1_6g1.json`). Todas las comprobaciones sobre estado real en disco (bytes, SHA-256, existencia, enlaces), no sólo códigos de retorno:

| Prueba | Qué comprueba | Resultado |
|---|---|---|
| **H1a** (obligatoria) | Provisional real creado y acreditado; ruta sustituida por **enlace simbólico** a un directorio externo (con centinela + SHA-256 y archivo extra) antes del aborto: el enlace **no se sigue** (`apertura_segura_fallo`/ELOOP); centinela y extra **byte a byte intactos**; **sin `ABORT_6G1.json` en el externo** (ni en ninguna ruta acreditada); fail-closed registrado (`directorio_acreditado: False`, motivo de anclaje); **nada eliminado**; **sin salidas válidas** ni invalidadas ni conservados (nada se clasificó fuera del provisional real); schema /3; motivo original conservado | PASS |
| H1b | Aborto normal con directorio acreditado: ABORT /3 en el provisional **real** con `directorio_acreditado=True`; semántica C-R1/E-R2 intacta (salida propia invalidada y conservada byte a byte; ajeno intacto; `resultados_validos==[]`) | PASS |
| H1c | Directorio acreditado sustituido por **otro directorio real** (el provisional acreditado sigue vivo, renombrado aparte): `fstat` no coincide → fail-closed `identidad_distinta`; **sin ABORT en el nuevo directorio**; contenido ajeno intacto | PASS |
| H1-CR1c-regresión | La ventana histórica (sustitución tras dictamen positivo) sigue cubierta con el anclaje activo: sustituto intacto, ABORT en el provisional real, clasificación por dictamen anterior | PASS |
| H1-e2e ×3 | Aborto real (guarda final) con la acreditación de `create_run_dir`: exit 2, sin definitivo, ABORT /3 en el provisional real con `directorio_acreditado=True`, salidas propias conservadas | 3× PASS |
| sanidad ×3 | Corrida feliz: exit 0, publicación única, integridad True, **PCM idéntico a la campaña auditada** (DSP intacto) | 3× PASS |

**Batería C-R1 actualizada y re-ejecutada (13/13 PASS)** — sus 6 ensayos unitarios acreditan ahora el provisional como hace `create_run_dir()` (precondición nueva H1, necesaria porque el aborto sin acreditación es fail-closed por diseño). CR1c (ventana histórica) y CR1e (exclusividad) siguen en verde; el flujo e2e demuestra la acreditación de los motores. **Baterías históricas 34/26/17/12: no ejecutadas** (sus arneses conservan expectativas `/2` y no deben usarse como aceptación de `/3` sin actualización).

**Registro de iteraciones del arnés H1** (ninguna de código de producción): (1) H1c inicial borraba el directorio acreditado antes de crear el sustituto y tmpfs reutilizó el mismo inodo → ensayo corregido para mantener el provisional vivo (renombrado), con identidad genuinamente distinta; (2) H1a no eliminaba el enlace simbólico residual de la corrida anterior → arranque robustecido. Ejecución final: 10/10.

## 4. SHA-256, DIFF y commits

- `SHA256SUMS_H1.txt` (11 ficheros con SHA previo en comentario; verificado con `sha256sum -c`: 11/11 OK).
- `DIFF_6G1_H1.patch`: diff incremental **reversible** respecto de `4960b50c4f80b2c846a10bef5d42a86ca1971839` (`patch -R -p1` devuelve el árbol base byte a byte; forward dry-run exit 0).
- **Commit anterior**: `4960b50c4f80b2c846a10bef5d42a86ca1971839` · **Nuevo commit**: hijo directo del anterior (verificado con `git rev-parse HEAD^` y contra el remoto tras el push; valores exactos en el informe de ejecución).

## 5. Límites respetados

Sin STFT/ISTFT/FFT/hop/chunking/máscaras/fórmulas/consenso/ganancias/polaridad/parámetros DSP (sanidad ×3 con PCM idéntico); motores originales de 6G, carpeta 6G de referencia, `main` y `arena/89d5c189-sdv-sdi-sgm` intactos; A–D/E–G/E-R1/E-R2/C-R1 intactos fuera de lo estrictamente necesario para H1 (anclaje del aborto, acreditación en `create_run_dir`, precondición de la batería C-R1 y la documentación señalada); sin canciones reales ni Elis/Tristania; sin Android/Termux; baterías históricas no repetidas; sin fusionar ramas ni abrir PR. **No se declara 6G.1 cerrada.**

## 6. Enlaces (URLs completas)

Informe H1 (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H1_6G1.md

Diff incremental vs 4960b50 (reversible):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_H1.patch

SHA-256 de los archivos modificados:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_H1.txt

Matriz H1:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_h1_6g1.csv

Resultados individuales por check:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_h1_6g1.json

Módulo corregido:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py

Informe C-R1 (documentación corregida):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_C_R1_6G1.md
