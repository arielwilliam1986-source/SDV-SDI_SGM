# 6G.1 — RECTIFICACIÓN FINAL DE E1: IDENTIDAD DE DESCRIPTORES Y DIRECTORIO MASKS

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** rectificación final de E1 (E1-A y E1-B) + delimitación documental de G1. **CERO modificaciones en producción** (§6). 6G.1 ABIERTA. Parada obligatoria ejecutada.
- **Fecha:** 23 de noviembre de 2026.
- **Base:** auditoría independiente de Cris sobre `a4139af…`: la rectificación anterior corrigió correctamente la obligatoriedad de `masks`, pero la revisión estática identificó dos insuficiencias (E1-A, E1-B), que se aceptan y se rectifican.

---

## 0. Identidades Git y comparación de archivos modificados

| Elemento | Valor |
|---|---|
| Referencia de producción (autorizada) | `9fedc5b223444e73955d2b899b6a434b0f5c670e` |
| Segunda revisión (A/B) | `09961a42f19756a9d748126d3b87a037eb9349bd` |
| Tercera revisión (C/D/E/F/G) | `b72042789dd33852dd4c3ad3ddc14a3fb9495770` |
| Rectificación anterior (E1/G1/C6/F1) | `a4139af556ec3a72b3d4063cb678143debda6d95` |
| Commit de esta rectificación final | hijo **directo** de `a4139af…` |
| Entorno del prototipo | Python 3.11.2, numpy 1.26.4, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64, kernel 6.1.158+, euid 1001 (single-uid; declarado) |

**Comparación de archivos modificados** (`git diff --name-status a4139af..rectificación_final`):

| Archivo | Estado | Motivo |
|---|---|---|
| `scripts/prototipo_hallazgos_cdefg_6g1.py` | `M` | rectificación E1-A/E1-B + delimitación G1 (`main()` NO modificado) |
| `evidence/…/escenario_e1.json` | `M` | 8 escenarios nuevos (E1-A1..A3, E1-B1..B5) |
| `evidence/…/escenario_g1.json` | `M` | campo `alcance_documental` + `alcance` en auditoría |
| `evidence/…/escenario_c6.json`, `…/escenario_d1.json`, `…/consolidado_prototipo_cdefg.json` | `M` | re-ejecución completa: variación experimental de `(dev,ino)`/timestamps reales (los veredictos no cambian) |
| `evidence/…/escenario_c1_c4.json`, `…/escenario_c5.json`, `…/escenario_d2.json`, `…/escenario_f1.json` | idénticos byte a byte | experimentos aceptados no alterados |
| `INFORME_RECTIFICACION_FINAL_E1_6G1.md` + `MANIFEST_RECTIFICACION_FINAL_E1_6G1.json` + `SHA256SUMS_RECTIFICACION_FINAL_E1_6G1.txt` | `A` | nuevos |

**Cero cambios de producción:** motores Hardened/EVO/MQR, `lectura_segura_6g1.py`, DSP, fórmulas, fixtures y validadores byte a byte idénticos; `main()` del prototipo sin modificar (restricción 4 respetada).

## 1. E1-A — descriptor de archivo ausente: rectificada (`PASS`)

**Insuficiencia aceptada:** `item.get('identidad_vs_fd', True)` aceptaba un archivo regular cuando NO existía descriptor correspondiente en `fds_archivos` (PASS por defecto).

**Rectificación aplicada a `checklist_completitud()`:**
1. El valor por defecto `True` **queda eliminado**: `identidad_vs_fd` sólo es `True` con entrada existente Y descriptor presente Y `(st_dev, st_ino)` coincidentes; en cualquier otro caso es `False`.
2. El campo `descriptor_presente` queda registrado por artefacto (trazabilidad explícita).
3. `item['ok']` exige **las cinco condiciones**: existe + regular + no-symlink + **descriptor presente** + identidad coincidente. La ausencia del descriptor produce **FAIL, nunca PASS por defecto**.

## 2. E1-B — identidad del directorio masks: rectificada (`PASS`)

**Insuficiencia aceptada:** la guarda validaba que `masks` fuera directorio real y no symlink, pero no contrastaba su identidad con el descriptor del directorio acreditado.

**Rectificación aplicada:**
1. Cuando `masks` existe: nueva comprobación `identidad_vs_fd` = `(st_dev, st_ino)` de la entrada nominal vía `fstatat(…, NOFOLLOW)` **==** `fstat(fd_masks)`.
2. `masks` presente sin descriptor (`fd_masks=None`) → **FAIL** (nunca PASS por defecto, mismo principio E1-A).
3. `masks` opcional y ausente → sigue siendo válido (`ok=True` en esa dimensión); `masks` obligatorio y ausente → **FAIL** (semántica de la rectificación anterior, conservada).

## 3. Pruebas independientes obligatorias (8/8 con el resultado exigido)

Todos los escenarios usan **provisionales acreditados independientes** (directorios `E1-A1…E1-B5`, cada uno creado desde cero con `crear_y_anclar`); ninguna ausencia, sustitución o symlink se simula con parámetros que desactiven comprobaciones (evidencia: `escenario_e1.json`, `EXPERIMENTAL_RESULT`):

| Escenario | Situación (REAL, dir independiente) | Veredicto | Detalle clave |
|---|---|---|---|
| **E1-A1** | archivo obligatorio presente + descriptor correcto (+ fd_masks) | `PASS` | `analysis.ok=True`; `masks.identidad_vs_fd=True` |
| **E1-A2** | archivo obligatorio presente, descriptor OMITIDO del registro (fd abierto en el motor) | `FAIL` | `descriptor_presente=False`, `identidad_vs_fd=False`, `ok=False` — sin PASS por defecto |
| **E1-A3** | archivo sustituido por otro regular con identidad distinta (misma uid: unlink + O_EXCL impostor) | `FAIL` | `identidad_vs_fd=False` (el descriptor del registro apunta al original) |
| **E1-B1** | `masks` presente y coincide con `fd_masks` | `PASS` | `masks.identidad_vs_fd=True` |
| **E1-B2** | `masks` sustituido por OTRO DIRECTORIO REAL con identidad distinta (misma uid: rmdir + mkdir, nuevo inodo, mismo nombre) | `FAIL` | `tipo='directorio'` (real) pero `identidad_vs_fd=False` — detectada por el contraste con `fd_masks`, que conserva el inodo original |
| **E1-B3** | `masks` ausente y OPCIONAL (Hardened/EVO) | `PASS` en esa dimensión | `existe=False`, `esperado='opcional'`, `ok=True` |
| **E1-B4** | `masks` ausente y OBLIGATORIO (MQR) | `FAIL` | `existe=False`, `esperado='obligatorio'`, `ok=False` |
| **E1-B5** | `masks` presente como symlink (precolocado) | `FAIL` | `tipo='symlink'`; también FAIL declarándolo opcional (`veredicto_si_opcional='FAIL'`) |

El veredicto global del escenario E1 es `PASS` (los 8 sub-casos produjeron el resultado exigido).

## 4. G1 — precisión del alcance documental

**Rectificación aplicada (sin repetir la prueba):** los resultados SHA-256 aceptados se **mantienen**; el alcance queda delimitado expresamente en la evidencia:
- Nuevo campo `alcance` en cada auditoría (`_auditar_integridad`): `artefactos_verificados=['analysis.json', 'mix SDV.wav']`, cobertura = "demostración DELIMITADA del mecanismo de comparación SHA-256; NO constituye la verificación de TODOS los artefactos de producción (exige la matriz real de artefactos por motor y modo, hallazgo E)".
- Nuevo campo `alcance_documental` en el resultado del escenario: la verificación demostrada corresponde a `mix SDV.wav` y `analysis.json`; **no se afirma** que se hayan verificado todos los artefactos de producción; **no se amplía** la prueba a otros ficheros hasta definir la matriz real de artefactos por motor y modo (matriz propuesta en el hallazgo E, pendiente de consolidación en implementación).

Se mantienen las declaraciones previas: el registro **NO es inmutable** frente a la misma uid y **NO posee garantías de autenticidad**.

## 5. Resultados consolidados de la re-ejecución

| Escenario | Veredicto | Observación |
|---|---|---|
| C1–C4 / C5 / D1 / D2 | `DEMOSTRADO` / `PASS` / `DEMOSTRADO` / `PASS` | sin cambios (experimentos aceptados; evidencias byte-idénticas salvo inodos/ts de re-ejecución) |
| C6 / F1 | `PASS` / `PASS` | sin cambios funcionales (rectificados en `a4139af`) |
| **E1** | `PASS` | **rectificación FINAL**: E1-A + E1-B + 8 escenarios nuevos |
| **G1** | `PASS` | **alcance documental delimitado** |

**Separación exigida:** todo es prueba de **MECANISMO**; RG-FLOW real por motor sigue pendiente de autorización; compatibilidad EVO/MQR no inferida por similitud; diseño no declarado completo hasta resolver los puntos exclusivos de MQR (re-lectura de `analysis.json` L3578) en flujo real.

## 6. Declaración explícita de qué NO se hizo

- **Cero modificaciones en producción**; `main()` del prototipo sin modificar; el diff toca sólo el prototipo, sus evidencias, el informe y el manifiesto/sumas (§0).
- No se ejecutaron corridas reales de motores, baterías históricas ni prueba DSP; sin audio real, Android ni Termux; sin fusión, integración ni cherry-pick; experimentos ya aceptados no repetidos (sus veredictos permanecen; las evidencias c1_c4/c5/d2/f1 byte-idénticas).
- No se amplió la verificación SHA-256 de G1 a otros artefactos (restricción explícita de la instrucción).

## 7. Entregables y verificación

| Fichero | Contenido |
|---|---|
| `INFORME_RECTIFICACION_FINAL_E1_6G1.md` | Este informe |
| `scripts/prototipo_hallazgos_cdefg_6g1.py` | Prototipo rectificado (E1-A/E1-B + alcance G1) |
| `evidence/prototipo_hallazgos_cdefg_6g1/` | Evidencias JSON (schema `prototipo-cdefg-1/1`) |
| `MANIFEST_RECTIFICACION_FINAL_E1_6G1.json` + `SHA256SUMS_RECTIFICACION_FINAL_E1_6G1.txt` | Manifiesto y sumas — verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_RECTIFICACION_FINAL_E1_6G1.txt \| sha256sum -c -` |

Re-ejecución:
```bash
python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/prototipo_hallazgos_cdefg_6g1.py \
    --work /tmp/cdefg_6g1 \
    --out ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/prototipo_hallazgos_cdefg_6g1
```

## 8. PARADA OBLIGATORIA

El trabajo se detiene aquí, a la espera de la adjudicación de Cris. No se implementa el mecanismo en producción.

*Fin del informe. Agente en parada.*
