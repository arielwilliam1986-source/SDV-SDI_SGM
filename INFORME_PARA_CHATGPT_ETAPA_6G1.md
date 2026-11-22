# INFORME PARA CHATGPT — ETAPA 6G.1 (Corrección de lectura segura del Mix)

**Proyecto:** SDV-SDI / SGM (Santo Grial Musical)
**Repositorio:** https://github.com/arielwilliam1986-source/SDV-SDI_SGM
**Rama de trabajo actual:** `arena/f1c5739f-sdv-sdi-sgm` (continúa la historia completa de `arena/c7719286-sdv-sdi-sgm`)
**Commit punta:** `9fedc5b223444e73955d2b899b6a434b0f5c670e`
**Fecha del informe:** 22 de noviembre de 2026
**Destinatario:** ChatGPT, como auditor externo independiente.

---

## 0. OBJETO DE ESTE INFORME

Este informe te dirige a **ti (ChatGPT)** y no al operador humano. Se te entrega para que:

1. Conozcas el estado exacto de la etapa 6G.1 del proyecto SDV-SDI/SGM.
2. Audites, con los enlaces de GitHub incluidos, si la corrección del hallazgo F cierra la batería de auditoría integral.
3. Opines sobre si procede declarar **cerrada** la etapa 6G.1 y autorizar su integración, o qué pasos faltan.
4. Conozcas las reglas del proyecto que deben respetarse en cualquier corrección futura.

Todo lo que sigue está clasificado implícitamente como **DOCUMENTED_FACT** salvo que se indique lo contrario. Cada afirmación tiene evidencia enlazada.

---

## 1. CONTEXTO DEL PROYECTO

El proyecto busca un sistema de separación musical (SDV/SDI: `SDV = M − instrumental`, `SDI = M − vocal`) que preserve fidelidad perceptual al máster artístico: timbre, dinámica, integridad estéreo, información espacial e intimidad vocal. La limpieza nunca debe sacrificarse a costa de información musical.

Restricciones permanentes (resumen): no convertir a mono, no mezclar L/R, no imponer ganancia/normalización, no forzar fase, no cambiar sample rate sin autorización, no truncar archivos, no asumir que `SDV + SDI = Mix` demuestra separación correcta, y no declarar un motor ganador sin pruebas con música real.

**Antecedente inmediato:** la etapa **6G** (soporte FLAC del Mix, cierre `ee19fe208449249a20e194b09c9452b782c7de70`). La etapa **6G.1** es una corrección sobre 6G, autocontenida en la carpeta `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`, que no modifica 6G ni ninguna etapa anterior.

Documento de transferencia técnica del proyecto (contexto completo, definiciones matemáticas, restricciones y filosofía):
[Proyecto SDV-SDI_SGM — Estado y continuidad.txt](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/Proyecto%20SDV-SDI_SGM%20%E2%80%94%20Estado%20y%20continuidad.txt)

---

## 2. QUÉ RESUELVE 6G.1

1. El Mix se valida **una vez** y se lee siempre desde **el mismo descriptor** (`/proc/self/fd/N`) durante todo el DSP: ningún componente lo reabre por su ruta.
2. Si el archivo o la ruta cambian, el motor **aborta** de forma fail-closed: invalida las salidas de audio de esa corrida, registra el motivo en `ABORT_6G1.json` (schema `abort-6g1/3`), **no borra** archivos preexistentes ni ajenos, y no publica nada como éxito.
3. La matriz de validación exige PCM real con hash para declarar igualdad, y distingue `ACCEPTED`, `REJECTED`, `PCM_IDENTICAL`, `PCM_DIFFERENT`, `NOT_APPLICABLE` y `NOT_EXECUTED`.
4. **El DSP no cambia.** Se verificó por AST, por huella de literales/llamadas y por PCM idéntico byte a byte frente a 6G en WAV y FLAC.

Índice de auditoría de la entrega base 6G.1:
[INDICE_PARA_AUDITORIA_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INDICE_PARA_AUDITORIA_6G1.md)

---

## 3. CADENA DE TRABAJO DE 6G.1 (commits y baterías)

Secuencia verificable de commits, en orden:

| # | Hallazgo / corrección | Commit | Batería | Resultado |
|---|---|---|---|---|
| 1 | Correcciones A–D de la auditoría sobre 015e2f8 (guarda final, publicación, aborto con propiedad, comparación) | `64b3c2d` | 34/34 PASS; no-regresión 3× ACCEPTED | DSP intacto |
| 2 | Seguridad E–G (E/S anclada a dirfd con O_NOFOLLOW, provisional exclusivo, publicación `renameat2 RENAME_NOREPLACE`) | `2248e2e` | E1–E7 26/26 PASS ×3 motores | DSP intacto |
| 3 | E-R1/G-R1 (actualización de `analysis.json` con descriptor único verificado; traslado con `RENAME_NOREPLACE` en 6 sitios) | `97d1bd0` | 17/17 PASS | DSP intacto |
| 4 | E-R2 (`analysis.json` permanece intacto durante el aborto; todo vive en `ABORT_6G1.json`) | `03c6a80` | 12/12 PASS | DSP intacto |
| 5 | C-R1 (aborto **sin eliminación de archivos**: eliminada la ventana TOCTOU `lstat→acreditación→unlink`; salidas propias invalidadas y conservadas) | `8caa65b` | 13/13 PASS | DSP intacto |
| 6 | H1 (anclaje del directorio de aborto: `O_DIRECTORY\|O_NOFOLLOW` + fstat contra lo acreditado) | `f54ceb5` | H1 10/10 + C-R1 13/13 | DSP intacto |
| 7 | H1-R2 (creación y acreditación de directorios por descriptores; inventario y clasificación exclusivamente por descriptor) | `2c3227f` | 4/4 + regresiones H1 10/10, C-R1 13/13 | DSP intacto |
| 8 | H1-R2-R1 (SHA-256 con verificación del archivo **durante** toda la lectura: fstat inicial + incremental + fstat final) | `cda4363` | 2/2 + regresiones | DSP intacto |
| 9 | H1-R2-R2 (apertura con `O_NONBLOCK`: cierra la ventana lstat→apertura; una sustitución por FIFO ya no puede bloquear) | `d1655e0` | 1/1 + regresiones | DSP intacto |
| 10 | H2 (apertura segura del Mix: identidad por `probe_file` exigida en `MixHandle`, O_NONBLOCK fail-closed, hash estable con doble fstat) | `af80424` | T1–T4 10/10 + e2e ×3 | DSP intacto |
| 11 | H2-R (probe_file anclado a una única apertura; metadatos/contenedor/SHA sobre el descriptor vía `/proc/self/fd/N`; fstat final fail-closed) | `af70c26` | 15/15 + regresiones focalizadas | DSP intacto |
| 12 | Auditoría final de no regresión DSP frente a 6G: detector `REJECTED ×3` por huella de literales en `FileInfo` (H2) y `create_run_dir` (E-G); PCM WAV/FLAC idéntico y llamadas DSP idénticas | `bd76831` | — | Detenido por decisión de Cris |
| 13 | **Adjudicación de Cris:** equivalencia DSP 6G.1 aceptada con alcance limitado (`FileInfo` y `create_run_dir` clasificados como gestión de archivos/seguridad, no DSP). **6G.1 NO CERRADA** | `594a90f` | — | Reanudación autorizada |
| 14 | CV — ciclo de vida: protocolo único de aborto (hallazgo A) y contrato de retorno de MQR (hallazgo B: falso éxito) | `c38d00d` | 33/33 PASS | DSP intacto |
| 15 | CR — cierre determinista de recursos (escritores WAV, memmaps, lectores, log) antes del aborto | `8e773df` | 15/15 PASS | DSP intacto |
| 16 | CR-R1 (fallo de cierre de lectores o de `cerrar_log()` marca `completo=False`; ABORT registrado, sin traslado) | `6a93e4e` | 18/18 PASS | DSP intacto |
| 17 | **AI — Auditoría integral** de cierre real de wrappers y retención de abortos (A–E): 9 FAIL atribuibles **sólo** al hallazgo F preexistente (memmap retenido por la variable de bucle); base 6a93e4e: 0/27 | `2f4aae4` | 18/27 PASS | F no corregido; detenido y documentado |
| 18 | **AI-F — Corrección F** (`arr = None` tras el flush de memmaps; +3 líneas, −0) | `9fedc5b` (punta) | **27/27 PASS** (padre 18/27) | AST: única inserción, resto idéntico |

Informe de la auditoría integral:
[AUDITORIA_INTEGRAL_CIERRE_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/AUDITORIA_INTEGRAL_CIERRE_6G1.md)

Informe de la corrección F:
[CORRECCION_F_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/CORRECCION_F_6G1.md)

---

## 4. ESTADO ACTUAL (verificado el 22-11-2026 desde un árbol limpio en `9fedc5b`)

| Verificación | Resultado |
|---|---|
| Batería AI completa (27 casos: A1–E1 × Hardened/EVO/MQR) | **27/27 PASS**; `hallazgo_F_resuelto` 27/27 ([evidencia](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_correccion_f_6g1.json)) |
| Liberación del memmap retenido (fd, mapeo y referencia débil) | Comprobada en ejecución en los 11 casos donde existe `masks/model_disagreement_map.npy` (con GC deshabilitado y 0 colecciones) |
| AST frente al padre `2f4aae4` | OK: exactamente una inserción `arr = None` por motor; retirándola el AST es idéntico ([evidencia](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_correccion_f_6g1.json)) |
| Integridad de la entrega F | `sha256sum -c SHA256SUMS_CORRECCION_F_6G1.txt` → **38/38 ficheros OK, 0 fallos** (re-ejecutado hoy desde la raíz del repo) |
| Motores originales y Fase 1B | **Intactos**: cero cambios en `Proyecto SDV-SDI_SGM/` y `SDV-SDI_FASE_1B_ENTREGA/` desde la base; los motores 6G.1 son copias dentro de la carpeta de la etapa |
| Alcance total de la rama | 243 ficheros, +277.513 / −258, todo dentro de `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/` y `herramientas/diagnostico_audio/` |
| Entorno de las pruebas | Python 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64 |
| **Estado de la etapa** | **6G.1 NO está cerrada ni autorizada para integración** (pendiente de adjudicación del cierre tras la corrección F) |

**No ejecutado en la corrección F (declarado en su informe):** baterías históricas (H1, C-R1, H2, CV, CR), la prueba DSP, audio real, Android y Termux. No se ha fusionado ni integrado nada.

---

## 5. CÓMO AUDITAR LA EVIDENCIA (enlaces GitHub)

Todos los enlaces apuntan a la rama `arena/f1c5739f-sdv-sdi-sgm`; el mismo contenido (sin este informe) existe también en la rama original `arena/c7719286-sdv-sdi-sgm`.

**Carpeta de la etapa:** https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA

### 5.1 Documentos principales

| Documento | Contenido | Enlace |
|---|---|---|
| README de la etapa | Qué resuelve 6G.1, cómo reproducir | [README.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/README.md) |
| Índice para auditoría | Mapa de archivos, preguntas que responde, comandos | [INDICE_PARA_AUDITORIA_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INDICE_PARA_AUDITORIA_6G1.md) |
| Implementación 6G.1 | Qué se cambió y por qué | [INFORME_IMPLEMENTACION_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_IMPLEMENTACION_6G1.md) |
| Validación (pruebas 1–10) | Veredictos y casos no ejecutados | [INFORME_VALIDACION_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_VALIDACION_6G1.md) |
| No regresión DSP | Por qué el DSP es el mismo que 6G | [NO_REGRESION_DSP_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/NO_REGRESION_DSP_6G1.md) |
| Adjudicación de Cris (no regresión) | Alcance limitado; 6G.1 no cerrada | [ADJUDICACION_CRIS_NO_REGRESION_DSP_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/ADJUDICACION_CRIS_NO_REGRESION_DSP_6G1.md) |
| Seguridad E–G | Hallazgos E, F(estructura), G y corrección | [INFORME_SEGURIDAD_EG_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_SEGURIDAD_EG_6G1.md) |
| C-R1 | Aborto sin eliminación de archivos | [INFORME_C_R1_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_C_R1_6G1.md) |
| H1 → H2-R | Anclaje de directorios y apertura segura del Mix | [INFORME_H1_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H1_6G1.md) · [INFORME_H2_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H2_6G1.md) · [INFORME_H2_R_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_H2_R_6G1.md) |
| Ciclo de vida (CV) | Protocolo único de aborto + contrato MQR | [CICLO_VIDA_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/CICLO_VIDA_6G1.md) |
| Cierre de recursos (CR/CR-R1) | Cierre determinista antes del aborto | [CIERRE_RECURSOS_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/CIERRE_RECURSOS_6G1.md) |
| Auditoría integral (AI) | A–E; hallazgo F documentado | [AUDITORIA_INTEGRAL_CIERRE_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/AUDITORIA_INTEGRAL_CIERRE_6G1.md) |
| Corrección F (AI-F) | `arr = None`; 27/27 | [CORRECCION_F_6G1.md](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/CORRECCION_F_6G1.md) |

### 5.2 Evidencia clave

| Evidencia | Enlace |
|---|---|
| Matriz global (pruebas 1–10) | [evidence/matriz_global_6g1.csv](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_global_6g1.csv) |
| Resumen consolidado 6G.1 | [evidence/resumen_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/resumen_6g1.json) |
| Pruebas auditoría integral | [evidence/pruebas_auditoria_cierre_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_auditoria_cierre_6g1.json) |
| Pruebas corrección F (27/27) | [evidence/pruebas_correccion_f_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/pruebas_correccion_f_6g1.json) |
| Matriz corrección F | [evidence/matriz_correccion_f_6g1.csv](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_correccion_f_6g1.csv) |
| No regresión DSP (JSON) | [evidence/no_regresion_dsp_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/no_regresion_dsp_6g1.json) |
| AST auditoría integral | [evidence/ast_auditoria_integral_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_auditoria_integral_6g1.json) |
| AST corrección F | [evidence/ast_correccion_f_6g1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_correccion_f_6g1.json) |
| Inyecciones de corrección F (27) | [evidence/inyecciones_correccion_f_6g1/](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/inyecciones_correccion_f_6g1) |

### 5.3 Integridad y diffs reversibles

| Elemento | Enlace |
|---|---|
| Manifiesto entrega base 6G.1 | [MANIFEST_6G1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/MANIFEST_6G1.json) · [SHA256SUMS.txt](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS.txt) |
| Manifiesto corrección F (vigente) | [MANIFEST_CORRECCION_F_6G1.json](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/MANIFEST_CORRECCION_F_6G1.json) · [SHA256SUMS_CORRECCION_F_6G1.txt](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_CORRECCION_F_6G1.txt) |
| Diff auditable → corrección | [DIFF_6G1_AUDITADO_A_CORRECCION.patch](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_6G1_AUDITADO_A_CORRECCION.patch) |
| Diff corrección F vs `2f4aae4` | [DIFF_CORRECCION_F_6G1_vs_2f4aae4.patch](https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/f1c5739f-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIFF_CORRECCION_F_6G1_vs_2f4aae4.patch) |
| Commit punta | https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/9fedc5b223444e73955d2b899b6a434b0f5c670e |

### 5.4 Comandos de verificación (contra un clon de la rama)

```bash
git clone --branch arena/f1c5739f-sdv-sdi-sgm https://github.com/arielwilliam1986-source/SDV-SDI_SGM.git
cd SDV-SDI_SGM
sha256sum -c ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_CORRECCION_F_6G1.txt   # 38/38 OK

cd ETAPA_6G1_CORRECCION_LECTURA_SEGURA
python -B scripts/preparar_fixtures_6g1.py
python -B scripts/validar_contenedores_6g1.py
python -B scripts/sustituciones_6g1.py
python -B scripts/no_regresion_dsp_6g1.py
python -B scripts/consolidar_6g1.py
```

Requisitos: Python 3.11, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1 (libsndfile 1.2.2), Linux con `/proc`. Los scripts escriben en `/tmp/f6g1/…`; sólo `evidence/`, `fixtures/`, `SHA256SUMS.txt` y `MANIFEST_6G1.json` se actualizan en el repositorio.

---

## 6. PREGUNTAS ABIERTAS PARA TI (CHATGPT)

1. **Cierre del hallazgo F:** ¿la corrección `arr = None` (+3 líneas, AST con única inserción, batería 27/27 con `hallazgo_F_resuelto` en todos los casos) constituye evidencia suficiente para considerar **resuelto** el hallazgo F documentado en `2f4aae4`?
2. **Cierre de 6G.1:** si (1) es afirmativo, ¿consideras cerrada la etapa 6G.1 para efectos de adjudicación, o exiges re-ejecutar las baterías históricas (H1, C-R1, H2, CV, CR) y/o la prueba DSP antes de la integración? Ten en cuenta que la corrección F declaró explícitamente que **no** las re-ejecutó.
3. **Riesgo residual de la corrección F:** los `arr` de las comprensiones (`{pid: arr[lo:hi] …}`) tienen ámbito propio y no se ven afectados según el informe. ¿Ves alguna otra vía de retención de memmaps o de fds que la batería AI no cubra?
4. **Orden de la siguiente etapa:** el proyecto tiene pendientes: S5 (`per_channel`) con motores reales y L/R diferenciados, compatibilidad de manifiestos orquestador→v3, validación con música real y selección de motor ganador (regla: prohibido sin material musical real). ¿Qué orden recomiendas tras la eventual integración de 6G.1?

---

## 7. REGLAS QUE CUALQUIER CONTINUACIÓN DEBE RESPETAR

(Extraídas del documento de transferencia y del protocolo que se ha aplicado en toda la etapa.)

- No modificar los motores originales antes de completar la auditoría; 6G.1 trabaja sobre copias en su propia carpeta.
- No corregir varios defectos simultáneamente sin pruebas aisladas.
- No inventar resultados cuando una dependencia o herramienta no esté disponible; declarar `NOT_EXECUTED`.
- No considerar una prueba aprobada si únicamente se inspeccionó el código: la inspección no equivale a prueba dinámica.
- Clasificar toda afirmación como `DOCUMENTED_FACT`, `EXPERIMENTAL_RESULT`, `THEORETICAL_DEDUCTION`, `HYPOTHESIS` o `UNKNOWN`.
- Toda corrección futura debe tener: identificador del defecto, evidencia de origen, cambio aislado, prueba de regresión, hash antes y después, justificación técnica y evaluación de efectos secundarios.
- Cada corrección se detiene tras ejecutarse y se somete a adjudicación independiente antes de continuar (así se hizo en H1→H2-R, CV, CR, CR-R1, AI y F).

---

## 8. DECLARACIÓN FINAL

- La etapa 6G.1 llegó al commit `9fedc5b` con la batería de auditoría integral en **27/27 PASS** tras la corrección F, con el DSP intacto y con los motores originales sin modificar.
- **Nada está fusionado, integrado ni declarado ganador.** La etapa sigue formalmente **abierta**, a la espera de la adjudicación del cierre.
- Este informe fue generado el 22-11-2026 desde un árbol Git limpio en `9fedc5b`, con los manifiestos SHA-256 re-verificados en esa fecha.

*Fin del informe dirigido a ChatGPT.*
