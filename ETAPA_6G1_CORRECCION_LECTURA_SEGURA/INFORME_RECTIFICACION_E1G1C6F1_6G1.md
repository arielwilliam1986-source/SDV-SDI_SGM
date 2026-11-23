# 6G.1 — RECTIFICACIÓN PUNTUAL PDA-1/EA: E1, G1, C6 y F1

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** rectificación de cuatro aspectos concretos del prototipo y documentación de sus límites. **CERO modificaciones en producción** (§7). 6G.1 ABIERTA. Parada obligatoria ejecutada.
- **Fecha:** 23 de noviembre de 2026.
- **Base adjudicada:** Cris reconoce los avances demostrados en **C y D**; no se repiten experimentos aceptados; se rectifican E1, G1, C6 y F1 según la instrucción.

---

## 0. Identidades Git y comparación de archivos modificados

| Elemento | Valor |
|---|---|
| Referencia de producción (autorizada) | `9fedc5b223444e73955d2b899b6a434b0f5c670e` |
| Segunda revisión (A/B) | `09961a42f19756a9d748126d3b87a037eb9349bd` |
| Tercera revisión (C/D/E/F/G, adjudicada) | `b72042789dd33852dd4c3ad3ddc14a3fb9495770` |
| Commit de esta rectificación | hijo **directo** de `b720427…` |
| Entorno del prototipo | Python 3.11.2, numpy 1.26.4, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64, kernel 6.1.158+, euid 1001 (single-uid; declarado) |

**Comparación de archivos modificados** (`git diff --name-status b720427..rectificación`):

| Archivo | Estado |
|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/prototipo_hallazgos_cdefg_6g1.py` | `M` (rectificado: E1/G1/C6/F1) |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/prototipo_hallazgos_cdefg_6g1/escenario_c6.json` | `M` (re-ejecutado) |
| `…/escenario_d1.json`, `…/escenario_e1.json`, `…/escenario_f1.json`, `…/escenario_g1.json`, `…/consolidado_prototipo_cdefg.json` | `M` (re-ejecutados) |
| `…/escenario_c1_c4.json`, `…/escenario_c5.json`, `…/escenario_d2.json` | idénticos byte a byte (no tocados por la rectificación) |
| `INFORME_RECTIFICACION_E1G1C6F1_6G1.md` + `MANIFEST_RECTIFICACION_E1G1C6F1_6G1.json` + `SHA256SUMS_RECTIFICACION_E1G1C6F1_6G1.txt` | `A` (nuevos) |

**Cero cambios de producción:** motores (`MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py`, `MOTOR_SEP_SDV-SDI_EVO.py`, `sdv_sdi_mqr_engine.py`), `lectura_segura_6g1.py`, DSP, fórmulas, fixtures y validadores permanecen byte a byte idénticos — el diff toca EXCLUSIVamente el prototipo independiente, sus evidencias, el informe y el manifiesto, como autoriza la instrucción.

## 1. E1 — guarda de completitud rectificada (`PASS`)

**Defecto reconocido:** la versión anterior admitía un parámetro `masks_presente_esperado` que **desactivaba la comprobación** para simular ausencia — exactamente lo que la instrucción prohíbe.

**Rectificación aplicada a `checklist_completitud(fd_run, fds_archivos, masks_obligatorio)`:**
1. El parámetro que desactivaba la comprobación **queda eliminado** de la firma.
2. La obligatoriedad **depende efectivamente** de `masks_obligatorio`: ausente + obligatorio → `ok=False`; ausente + opcional → `ok=True` (dimensión satisfecha).
3. Si `masks` **existe** (obligatorio u opcional): debe ser **directorio real y no symlink** (`S_ISDIR` y no `S_ISLNK`).
4. La ausencia se construye **REAL** en **directorios de prueba independientes** (`E1a…E1e`, cada uno con su provisional acreditado propio), no por parámetro.

**Escenarios ejecutados (todos con directorios independientes):**

| Sub-caso | Situación | Resultado |
|---|---|---|
| (a) `E1a-mqr-completo` | todo presente + masks obligatorio | `PASS` |
| (b) `E1b-mqr-masks-ausente` | **MQR**: masks ausente (real) + obligatorio | `FAIL` (`masks: existe=False, esperado=obligatorio, ok=False`) |
| (c) `E1c-hevo-masks-opcional` | **Hardened/EVO**: masks ausente (real) + opcional, resto completo | `PASS` respecto a esa dimensión (`masks.ok=True` y **todos** los demás artefactos `ok=True`) |
| (c2) mismo dir H/EVO | se elimina `analysis.txt` (real) | `FAIL` — **el resto de artefactos obligatorios sigue sometido a sus propias comprobaciones** aunque masks sea opcional |
| (d) `E1d-masks-symlink` | masks existe como symlink, **aun opcional** | `FAIL` (`tipo=symlink`); también FAIL si se declara obligatorio |
| (e1/e2/e3) `E1e-fallos-genericos` | obligatorio eliminado / `analysis.json` symlink / regular recreado (identidad ≠ fd) | `FAIL` / `FAIL` / `FAIL` |

## 2. G1 — verificación efectiva de integridad (`PASS`)

**Rectificación aplicada:** el escenario anterior sólo contrastaba la identidad del inodo; ahora ejecuta la auditoría de integridad **efectiva** exigida:

1. **Publicar el directorio** — `publicar_anclada` (PDA-1) sobre provisional acreditado con artefactos reales (WAV por descriptor + JSON).
2. **Leer el registro forense** — `publicacion_6g1.json` (schema `publicacion-6g1/1`) leído del directorio publicado.
3. **Recalcular los SHA-256** de los artefactos publicados por ruta externa (`mix SDV.wav`, `analysis.json`).
4. **Compararlos con los almacenados** en el registro.
5. **PASS al coincidir** — demostrado: `integridad_coincide=True`, `inodo_coincide=True`, `veredicto_auditoria='PASS'` (además de la re-verificación B2 del padre).
6. **Alteración deliberada en escenario INDEPENDIENTE** — segundo ciclo completo (`G1b`); tras publicar, la misma uid añade bytes a `analysis.json` publicado (residual post-return declarado).
7. **La auditoría detecta la discrepancia** — `veredicto_auditoria='DISCREPANCIA_DETECTADA'` (`analysis: coincide=False`; `mix_sdv: coincide=True`, intacto).

**Declaraciones mantenidas (sin atribuir garantías que no posee):** el registro **NO es inmutable frente a la misma uid** (demostrado: la reescritura del registro en el propio escenario lo confirma); el registro **NO posee garantías de autenticidad** — es evidencia de auditoría con coherencia verificable (inodo-vs-registro, SHA-256-vs-publicado); la detección de discrepancias **no identifica al autor ni impide la alteración**; es fiable frente a otra uid (`0700` del euid); la garantía post-return sigue declarada como limitación de prevención.

## 3. C6 — cobertura completa del log (`PASS`)

**Rectificación aplicada:** `engine_log.txt` incorporado al experimento de creación exclusiva + escritura por descriptor, con el **mecanismo compatible con Tee propuesto para producción, sin modificar el Tee real**: la clase real de los motores consume un objeto archivo (`self._file.write/.flush/.close`); la propuesta (replicada por `TeeAnclado6g1` en el prototipo, misma interfaz y semántica de `error_cierre_6g1`) es construir ese objeto sobre `os.fdopen(os.dup(fd_log), 'w')`, donde `fd_log` es el descriptor conservado de la creación exclusiva. La clase real no se importa ni se modifica.

**Seis puntos exigidos, todos demostrados (`EXPERIMENTAL_RESULT`):**

| Punto | Resultado |
|---|---|
| Creación exclusiva | `os.open('engine_log.txt', O_CREAT\|O_EXCL\|O_WRONLY\|O_NOFOLLOW, dir_fd=fd_run)` — sin error |
| Descriptor conservado | `fd_log` con `(dev,ino)` registrado en `identidad_creacion` |
| Sustitución de la entrada nominal | `unlink + symlink → objetivo_engine_log.txt` entre creación y escritura |
| Escritura por el descriptor original | 3 líneas escritas vía `TeeAnclado6g1(fd_log)`; relectura por el fd: 3 líneas correctas (`log_leido_via_fd`) |
| Contenido del destino ajeno SIN alteración | comparación **byte a byte** contra el centinela previo (`LINEA AJENA PREVIA`): `destino_ajeno_sin_alterar[objetivo_engine_log.txt]=True` — los 4 destinos ajenos (json/wav/npy/log) quedan sin alterar |
| Detección de identidad distinta | `fstat(fd_log)` vs `fstatat(fd_run, 'engine_log.txt', NOFOLLOW)`: `coincide=False`, `entrada_es_symlink=True` (4/4 archivos) |

Adicionalmente: `fd_log` permanece **válido tras el cierre de Tee** (`fd_log_valido_tras_cierre_de_tee=True`) — el escritor cierra su dup, nunca el fd del motor.

## 4. F1 — ciclo de vida ampliado (`PASS`)

**Rectificación aplicada al prototipo (`RegistroFds` sin cambios semánticos):**

| Exigencia | Demostración (`EXPERIMENTAL_RESULT`) |
|---|---|
| `fd_candidates` correctamente creado | `mkdir('candidates', dir_fd=fd_run)` + `openat(O_DIRECTORY\|O_NOFOLLOW)` registrado y cerrado en su posición correcta |
| Descriptores de archivos individuales | tres fds de archivo (wav, json, log) creados exclusivamente y cerrados |
| Fallo DESPUÉS de abrir varios recursos | con **5 recursos abiertos** (fd_padre, fd_run, fd_masks, fd_candidates, wav), la creación exclusiva de `analysis.json` choca con un symlink precolocado → `FileExistsError` → el registro cierra **los 5** en orden inverso `['wav','fd_candidates','fd_masks','fd_run','fd_padre']`, con el symlink precolocado **conservado** (sin eliminación) |
| Cierre en orden inverso | (a) éxito: `['log','json','wav','fd_candidates','fd_masks','fd_run','fd_padre']` — exactamente el inverso de la apertura |
| Sin cierre prematuro | soundfile escribe y el WAV conserva sus 44.100 frames antes del cierre; los escritores JSON/log usan su dup y el fd del motor queda **válido después** (`fds_archivo_validos_tras_biblioteca=True`) |
| Cero descriptores residuales | medido por `/proc/self/fd` en (a) y (b): `fds_residuales=[]`; `cierres_duplicados=0` (idempotencia ante doble llamada) |

**Distinción expresamente declarada en la evidencia (`extra` del escenario):**
- **Demostrado por el prototipo:** el mecanismo de registro (cierre exacto, orden inverso, sin cierre prematuro, fallo tardío, 0 residuales).
- **Pendiente de integración en los motores:** el ciclo **REAL** de los motores **NO queda validado** aquí; exige que cada motor use este registro en sus tres caminos (éxito/excepción/interrupción) junto a `preparar_aborto_6g1` (`cerrar_recursos_corrida_6g1` ampliado) y el cierre acreditado normal; se validará con RG-FLOW por motor, **pendiente de autorización**.

## 5. Resultados consolidados de esta re-ejecución

| Escenario | Veredicto | Observación |
|---|---|---|
| C1–C4 | `DEMOSTRADO` | sin cambios (brecha de la entrada final, misma uid) |
| C5 | `PASS` | sin cambios (creación exclusiva) |
| **C6** | `PASS` | **rectificado** (log con mecanismo Tee + destinos ajenos por bytes) |
| D1 / D2 | `DEMOSTRADO` / `PASS` | sin cambios (protocolo vigente ciego / aborto anclado) |
| **E1** | `PASS` | **rectificado** (obligatoriedad efectiva, directorios independientes) |
| **F1** | `PASS` | **ampliado** (fd_candidates, fallo tardío, distinción prototipo/motores) |
| **G1** | `PASS` | **ampliado** (auditoría de integridad efectiva + alteración detectada) |

**Separación exigida:** todo es prueba de **MECANISMO** (prototipo independiente). Las pruebas de integración real por motor (RG-FLOW, corridas reales de Hardened/EVO/MQR) siguen **pendientes de autorización**; compatibilidad EVO/MQR **no inferida por similitud de código**; el diseño no se declara completo hasta resolver los puntos exclusivos de MQR (re-lectura de `analysis.json` L3578) en flujo real.

## 6. Entregables, manifiesto y SHA-256

| Fichero | Contenido |
|---|---|
| `INFORME_RECTIFICACION_E1G1C6F1_6G1.md` | Este informe |
| `scripts/prototipo_hallazgos_cdefg_6g1.py` | Prototipo rectificado (E1/G1/C6/F1) |
| `evidence/prototipo_hallazgos_cdefg_6g1/` | 8 escenarios + consolidado (schema `prototipo-cdefg-1/1`) |
| `MANIFEST_RECTIFICACION_E1G1C6F1_6G1.json` + `SHA256SUMS_RECTIFICACION_E1G1C6F1_6G1.txt` | Manifiesto y sumas — verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_RECTIFICACION_E1G1C6F1_6G1.txt \| sha256sum -c -` |

Re-ejecución:
```bash
python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/prototipo_hallazgos_cdefg_6g1.py \
    --work /tmp/cdefg_6g1 \
    --out ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/prototipo_hallazgos_cdefg_6g1
```

## 7. Declaración explícita de qué NO se hizo

- **Cero modificaciones en producción**: motores, `lectura_segura_6g1.py`, DSP, fórmulas, fixtures y validadores byte a byte idénticos (comparación §0); el diff toca sólo prototipo, evidencias, informe y manifiesto.
- La clase **Tee real no se importa ni se modifica**: el mecanismo compatible se replica en el prototipo (`TeeAnclado6g1`) documentando la propuesta de producción.
- No se ejecutaron corridas reales de motores, baterías históricas ni prueba DSP; sin audio real, Android ni Termux; sin fusión, integración ni cherry-pick. No se repitieron experimentos ya aceptados (C/D permanecen; sus evidencias no modificadas quedaron byte-idénticas). 6G.1 ABIERTA.

## 8. PARADA OBLIGATORIA

El trabajo se detiene aquí, a la espera de la adjudicación de Cris sobre esta rectificación.

*Fin del informe. Agente en parada.*
