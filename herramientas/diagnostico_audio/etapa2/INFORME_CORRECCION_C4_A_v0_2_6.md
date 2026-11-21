# INFORME DE CORRECCIÓN C4-A — AudioInput ETAPA 2 **v0.2.6 (provisional)**

**Instrumento:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Versión de partida:** v0.2.5 (commit [`fb2a96c`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/fb2a96c7073d51dd6d16505e1616d3abc5fabe28); blob `a41d7b954e6182e75c59706b329317f386edd69d`; SHA-256 `8a2ad0e4c191ea945a6918dd7b50fbc6bffbf3bc8b8e68ccd3438a36aa98b902`)
**Versión entregada:** v0.2.6 (provisional)
**Etapa:** C4-A — Propiedad y ciclo de vida de descriptores
**Auditor independiente:** Cris (ChatGPT) | **Implementación:** Arena | **Decisor:** Will
**Fecha:** 2026-11-21
**Rama de trabajo:** `arena/441a4bf8-sdv-sdi-sgm` (rama de sesión autorizada)
**Condición:** entrega publicada; **C4-A NO queda aprobado**. La aprobación
corresponde exclusivamente a Cris tras auditoría independiente. No se inicia
C4-B ni C5 sin nuevas instrucciones.

---

## 1. Punto de partida (verificado antes de modificar)

| # | Verificación | Resultado |
|---|---|---|
| 1 | La rama de sesión contiene exactamente el estado publicado de v0.2.5 | **OK** — HEAD remoto = HEAD local = `b947c05e8f936b59c58550f5b538b3b9746f21cc` (verificado por `git fetch` en el momento) |
| 2 | Commit, blob del instrumento y SHA del diff identificados | **OK** — código: `fb2a96c…`; blob script: `a41d7b95…`; SHA-256 script: `8a2ad0e4…98b902`; diff v0.2.4→v0.2.5: SHA-256 `4b090a2aaad33bb35abdfd2d21451732adb0487b32454f569def0bfea6663a69` |
| 3 | Árbol de trabajo limpio | **OK** — sin modificaciones (único elemento: `__pycache__/` sin seguimiento, residuo de ejecución de pruebas, no commiteado; no se eliminó por restricción de no-limpieza) |
| 4 | v0.2.5 conservado como referencia inmutable | **OK** — commits `fb2a96c`/`b947c05` en el historial (inmutables); recovery point `/tmp/diag_v025_recovery.py` (SHA-256 idéntico al de entrada); el diff v0.2.5→v0.2.6 es reversible y reconstruye v0.2.5 byte a byte |
| 5 | No se reconstruyó el instrumento | **OK** — corrección delimitada sobre v0.2.5 |

---

## 2. HECHOS COMPROBADOS

### 2.1 El caso obligatorio de la instrucción (análisis)

Caso: (1) se abre un archivo; (2) se registra el descriptor y se conserva su
token; (3) el descriptor se cierra por vía externa; (4) el sistema reutiliza el
mismo número para abrir nuevamente el mismo archivo; (5) se intenta cerrar con
el token anterior.

**Hecho 1 (limitación del kernel/documentada):** Python no expone una identidad
portátil del *open-file-description* (OFD) del kernel. `fstat()` retorna
`(st_dev, st_ino)` del archivo subyacente: si el número fue reutilizado para el
MISMO archivo, la comparación coincide y **no permite distinguir las dos
aperturas**. Ningún mecanismo portátil disponible en el instrumento
(`fstat`, `lstat`, `F_GETFL`/`F_GETFD`, posición del OFD) constituye una prueba
de identidad de apertura; son heurísticas que fallan en casos reales (p. ej.,
OFD en posición 0 en ambas aperturas).

**Hecho 2 (comportamiento de v0.2.5 en el caso obligatorio):** en v0.2.5 el
modelo usaba token + comparación `(st_dev, st_ino)` como verificación previa al
cierre. En el paso (5), la coincidencia de `(dev, ino)` era aceptada y
`os.close()` se ejecutaba sobre el número → cerraba la **apertura ajena**
(paso 4). La comparación era usada de facto como identidad: defecto que C4-A
debe resolver.

**Hecho 3 (solución adoptada en v0.2.6, conforme a la instrucción):** la
identidad de la apertura es el **objeto recurso** creado en el registro
(`OwnedFdResource`), no un predicado observable. La solución establece y hace
cumplir un **contrato de propiedad**: ningún componente cierra el descriptor
registrado por vía externa; dentro del instrumento, el único camino de cierre
es el recurso del propietario (una vez) y SoundFile opera con `closefd=False`
por contrato. Si el contrato se viola y la violación es **observable**
(`EBADF` en la guardia previa, o identidad `(dev, ino)` distinta — número
reutilizado por OTRO archivo), el recurso pasa a `CLOSE_FAILED_UNCERTAIN`,
`os.close()` **no se invoca** y el cierre **no se reintenta** por ese token.
Si la violación es **indetectable** (reutilización del MISMO número para el
MISMO archivo), se documenta como límite del contrato (sección 5) — **no se
presenta como detección**.

**Hecho 4 (guardia ≠ identidad):** `fstat()` permanece en v0.2.6 únicamente
como **guardia defensiva previa** al cierre: detecta lo detectable (EBADF →
cierre externo o número re-cerrado; `(dev, ino)` distinto → número reutilizado
por otro archivo). No se usa ni se presenta como solución al caso obligatorio:
la solución es el modelo de recursos + contrato.

### 2.2 Modelo de propiedad implementado (estados y transiciones)

**Clase nueva `OwnedFdResource`** — encapsula el número de descriptor y su
estado. El token es el identificador externo del recurso (API pública
`register_fd(fd, label) -> token` y `close_fd(fd, label, token=…)` se
conservan: las llamadas de C1 en `write_report_json_robust` y las de T11–T16 y
`create_fixture` no requieren cambios).

Estados (nombres internos en minúsculas por compatibilidad con los registros de
v0.2.4/v0.2.5; justificación técnica: los harness congelados y el sink usan
esos literales):

| Estado | Significado |
|---|---|
| `OPEN` | Apertura registrada; propiedad vigente. |
| `CLOSING` | Cierre iniciado (transitorio; solo se alcanza desde `OPEN` y una única vez). |
| `CLOSED` | Cierre confirmado: `os.close()` retornó sin error para el recurso del propietario. |
| `CLOSE_FAILED_UNCERTAIN` | El resultado no permite garantizar que el número siga perteneciendo al recurso original: `EBADF` en guardia previa, identidad distinta en guardia previa, o error de `os.close()`. **Terminal: nunca se reintenta.** |

Transiciones:

```
(registro) --> OPEN --cierre único--> CLOSING --os.close OK--> CLOSED
                                    |-- guardia EBADF / identidad distinta
                                    |   / error de os.close
                                    v
                          CLOSE_FAILED_UNCERTAIN  (terminal)
```

Reglas implementadas y verificadas (sección 4):

1. Un recurso solo puede iniciar un cierre una vez (`OPEN → CLOSING` único
   camino; reentrada en `CLOSING` → aviso, sin operación).
2. Un token obsoleto (`CLOSED`, `CLOSE_FAILED_UNCERTAIN` o desconocido) nunca
   inicia un segundo cierre (aviso; sin `os.close`).
3. Un cierre incierto nunca se reintenta automáticamente.
4. Un descriptor no registrado no se cierra mediante el logger (aviso; sin
   `os.close`).
5. Los errores de cierre se conservan en `errors` del logger y en el sink
   global para su posterior propagación (la propagación completa ante
   `KeyboardInterrupt` corresponde a **C4-B**, fuera de esta etapa).

**Encapsulación:** `OwnedFdResource` es el titular del número; `get_resource(token)`
expone el recurso para inspección; el cierre solo es iniciable a través de
`close_fd`/recurso en estado `OPEN`. En el instrumento no existe ninguna otra
invocación de `os.close()` sobre descriptores registrados (verificado
estáticamente: los cierres de T11–T16, `create_fixture`,
`safe_create_file_exclusive_anchored` y `write_report_json_robust` son todos
con token a través del logger; `_close_fd_tracked` solo atiende descriptores
internos no registrados, de vida mínima, cerrados inmediatamente).

### 2.3 Semántica nueva respecto a v0.2.5 (relevantes para auditoría)

| Situación | v0.2.5 | v0.2.6 |
|---|---|---|
| Token ya cerrado | Aviso; no cierra | Ídem (sin cambio observable) |
| Cierre externo detectado (`EBADF` con recurso `OPEN`) | Marcaba la entrada como `closed` con `error:EBADF` y retornaba `OSError`; **un reintento posterior con el mismo token habría invocado `os.close` de nuevo sobre un número potencialmente reutilizado** | Estado `CLOSE_FAILED_UNCERTAIN` (terminal); retorna `OSError`; **ningún `os.close` posterior por el token**, verificado con contador |
| Número reutilizado por OTRO archivo | Aviso; no cierra; estado seguía `open` | Estado `CLOSE_FAILED_UNCERTAIN` + anomalía conservada en `errors` (contrato violado); no cierra el recurso ajeno |
| Error de `os.close()` | Estado `closed` con `error:errno` | Estado `CLOSE_FAILED_UNCERTAIN` (semántica exigida: el resultado no garantiza pertenencia) |
| Reutilización del MISMO número para el MISMO archivo | Cerraba la apertura ajena (comparación usada como identidad) | **Comportamiento documentado como límite de contrato**: el cierre del propietario procede (no existe detección); mitigación por encapsulación y contrato (sección 5) |

---

## 3. RESULTADOS DE PRUEBAS

Entorno: contenedor Linux (no Android), Python 3.11.2, sin numpy/soundfile/libsndfile.

### 3.1 Pruebas obligatorias C4-A — `pruebas_unitarias_C4_A_v0_2_6.py`

`TOTAL 13 | PASS 13 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0`

| # | Prueba | Estado | Evidencia |
|---|---|---|---|
| 1 | `C4A_01_apertura_cierre_normal` | **PASS** | `OPEN → CLOSED`; `os.close` invocado exactamente 1 vez (contador); sin errores |
| 2 | `C4A_02_dos_aperturas_mismo_archivo` | **PASS** | Tokens distintos; `(dev, ino)` idénticos; cerrar una no afecta la otra |
| 3 | `C4A_03_recursos_simultaneos_tokens_distintos` | **PASS** | Cierre en orden inverso sin efectos cruzados |
| 4 | `C4A_04_doble_cierre` | **PASS** | Aviso; contador `os.close` = 0 en el reintento; estado `CLOSED` intacto |
| 5 | `C4A_05_token_obsoleto_tras_cierre_confirmado` | **PASS** | Token obsoleto no cierra el recurso nuevo (contador 0; fd nuevo vivo) |
| 6 | `C4A_06_cierre_no_registrado` | **PASS** | Sin registro → aviso, sin cierre; token desconocido → aviso, sin cierre |
| 7 | `C4A_07_fallo_simulado_os_close` | **PASS** | `OSError(EIO)` devuelta; conservada en `errors` y sink; estado `CLOSE_FAILED_UNCERTAIN` |
| 8 | `C4A_08_incierto_no_se_reintenta` | **PASS** | Tras estado incierto, reintento → aviso; contador `os.close` = 0 |
| 9a | `C4A_09a_reutilizacion_contrato_respetado` | **PASS** | Cierre exclusivo del propietario (1 `os.close`); número reutilizado en la ejecución; token anterior invalidado sin efecto |
| 9b | `C4A_09b_contrato_violado_detectable` | **PASS** | Tercero cierra → guardia detecta `EBADF` → `CLOSE_FAILED_UNCERTAIN`; el diseño **nunca invoca `os.close`** (contador 0); apertura posterior no es cerrada por el token antiguo |
| 9c | `C4A_09c_mismo_archivo_limite_contrato` | **PASS** (comportamiento documentado, **no es detección**) | Subcaso reproducible (mismo número, mismo archivo); el cierre procede bajo contrato; el detalle de la prueba declara el límite explícitamente |
| +10 | `C4A_10_estado_closing_no_duplica` (soporte) | **PASS** | Reentrada en `CLOSING` → aviso; sin `os.close` |
| +11 | `C4A_11_estatico_contrato_en_t11_a_t16` (soporte) | **PASS** | `register_fd` en 10 sitios; 24 cierres asociados a token; sin `except OSError: pass` (salvo `_identity`) |

### 3.2 Regresión — harness v0.2.4 (congelado) sobre el script v0.2.6

`TOTAL 16 | PASS 16 | FAIL 0 | ERROR 0 | NOT_EXECUTED 0` — sin regresiones
(incluye `C4_dos_aperturas_mismo_archivo`, `C4_reutilizacion_numero_fd`,
`C4_cierre_repetido`, `C4_error_cierre_simulado`,
`C4_error_cierre_durante_excepcion/keyboardinterrupt`,
`C4_no_silencio_cierres_revisados`, y las 6 de C1/C5).

### 3.3 Regresión — harness v0.2.5 (congelado) sobre el script v0.2.6

`TOTAL 11 | PASS 10 | FAIL 1 | ERROR 0 | NOT_EXECUTED 0`

- **FAIL esperado y explicado:** `C5_v05_flujo_real_main_completo` tiene la
  aserción `'v0.2.5' in banner` (pin de versión del harness congelado); el
  instrumento ahora anuncia v0.2.6. **No es una regresión de lógica.**
- **Verificación suplementaria ejecutada** (reutilizando las utilidades del
  harness v0.2.5, sin modificarlo): el resto de las aserciones de esa prueba
  pasa íntegro sobre v0.2.6 — rc=0, banner v0.2.6, `script_version=0.2.6`,
  36 resultados, 36 PASS, `interrupted=false`, `close_errors` vacíos, informe
  publicado, `run_dir` privado y compartido creados.
- Las otras 10 pruebas (flujo real de `main()` con KI en prueba, fixture,
  makedirs, preparación del informe y publicación; T11–T14/T15–T16 sin fuga;
  patrón token; `safe_create_file`) pasan sin cambios.

### 3.4 Controles del instrumento

| Verificación | Resultado |
|---|---|
| `py_compile` v0.2.6 | **PASS** |
| `--help` | **PASS** (rc 0, interfaz correcta) |

---

## 4. Entregables e identificación

| Artefacto | Valor |
|---|---|
| Instrumento v0.2.6 | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| **Commit de código** | `5e38e0f002f53210f8a1a5d87c41dc548f69a2e5` (padre `b947c05e8f936b59c58550f5b538b3b9746f21cc`) |
| **Blob del instrumento** | `1a9854471fedd79e2b687df05e7749162f850c9b` |
| **SHA-256 del instrumento** | `a0d2ad299084c6c55e66556d26a415dc9a11ca7cf028e1facac8354b12a563a2` |
| Tamaño / líneas | 128441 bytes / 2678 líneas |
| **Diff v0.2.5→v0.2.6** | `DIFF_v0_2_5_A_v0_2_6.patch` — SHA-256 `1d8ace3466ff8811df813c65a3f6388658a01e0e302f0d66d6fb247b4bd26c49`, blob `fe0ae65ed3b1441d7902633648830e39552fd157`, 423 líneas (21856 bytes); **reversible** (patch inverso reconstruye v0.2.5 byte a byte, SHA-256 verificado) |
| **Harness C4-A** | `pruebas_unitarias_C4_A_v0_2_6.py` — SHA-256 `c43bebdcbf15f731ac42b5a575acd46c97729262f643c3b8c1c981c5089d34fd`, blob `c9717c0d8f0be8c5cbe232acd3670ed491e5ccf6`, 588 líneas (25737 bytes) |
| Commit del informe | (este commit, hijo de `5e38e0f`) |
| Rama | `arena/441a4bf8-sdv-sdi-sgm` (sin PR, sin fusión, sin `main`) |

**Alcance del diff (hunks):** línea 83 (`SCRIPT_VERSION`), bloque
`CloseErrorLogger` (reemplazo por `OwnedFdResource` + clase con máquina de
estados), y una entrada de documentación en la lista de notas del informe JSON.
**Sin cambios de lógica en C1 ni C5** (los hunks de C5/C1 no existen; la única
línea en la zona de `_finalize_report` es la nota de documentación, sin tocar
ninguna sentencia — declarado para auditoría).

---

## 5. LIMITACIONES (no resolubles de forma portable)

1. **Identidad del OFD:** Python/Linux no proporcionan una identidad portátil
   del open-file-description que permita reconocer cualquier cierre externo y
   posterior reutilización del mismo número. `fstat()` (ni `lstat`, ni flags
   `F_GETFL/F_GETFD`, ni posición del OFD) prueba la identidad de una apertura.
   **No se promete una garantía que el mecanismo no pueda proporcionar.**
2. **Violación indetectable del contrato:** si un tercero cierra el descriptor
   y el número es reutilizado para el MISMO archivo, el diseño **no puede
   detectarlo**; en ese caso el cierre del propietario procedería y afectaría
   a la apertura ajena. Está documentado como límite del contrato (y verificado
   como comportamiento documentado en `C4A_09c`) — **no se presenta como una
   detección**. Mitigación: encapsulación (ningún otro componente del
   instrumento cierra descriptores registrados) + contrato con SoundFile
   (`closefd=False`).
3. **Detección pasiva de cierres externos:** no existe; la violación solo se
   observa cuando el propietario intenta el cierre (guardia previa) o cuando
   una operación sobre el número falla.
4. **`kcmp(KCMP_FILE)`** (Linux ≥ 3.5, `CONFIG_CHECKPOINT_RESTORE`) podría
   comparar OFD de dos números, pero no es portátil, no está expuesto por
   Python y requeriría syscalls crudas por ctypes: **evaluado y no adoptado**
   (incompatibilidad potencial con Android/Termux y complejidad no justificada
   para el instrumento).
5. **Posición del OFD como heurística:** considerada y **rechazada**: no es
   fiable (posiciones 0 legítimas en aperturas no leídas); presentarla como
   detección violaría la regla de no inventar garantías.

---

## 6. Lista exacta de funciones modificadas

| Función / clase | Naturaleza | Contenido |
|---|---|---|
| `OwnedFdResource` | **NUEVA clase** (auxiliar del modelo de propiedad) | Encapsula fd + estado; máquina de estados `OPEN/CLOSING/CLOSED/CLOSE_FAILED_UNCERTAIN`; acceso por clave compatible con harness v0.2.4/v0.2.5 |
| `CloseErrorLogger` | **Reemplazo interno** (permitido: "CloseErrorLogger o su reemplazo") | Docstring (modelo/contrato/reglas); `__init__` (mismos campos; `_entries` ahora almacena recursos); `_identity` (misma lógica; docstring de guardia); `_append_error` (idéntica); **nuevo** `get_resource(token)`; `register_fd` (misma firma; crea recurso); `close_fd` (misma firma y contrato de retorno; máquina de estados + guardias + cierre único) |
| `SCRIPT_VERSION` | Constante | `"0.2.5"` → `"0.2.6"` |
| Notas del informe JSON (dentro de `_finalize_report`, `main()`) | **Documentación** (1 entrada añadida, sin sentencias modificadas) | Declara el modelo C4-A y su límite. Declarado expresamente: es la única línea en zona C5; no modifica la lógica de interrupciones ni el flujo de `main()` |
| `test_t11…` a `test_t16…` | **SIN cambios** | Ya operan correctamente el modelo (registro por apertura + cierres con token desde v0.2.5); verificado estáticamente (24 cierres con token) |
| `create_fixture`, `safe_create_file_exclusive_anchored`, `write_report_json_robust` | **SIN cambios** | Sus llamadas al logger son compatibles con la nueva implementación (API pública intacta) |
| C1 (publicación JSON), C5 (interrupciones/flujo), `sha256_pread_v2`, clasificaciones SHA-256, SoundFile `closefd=False`, `pread`, WAV/subtipos, señales sintéticas, criterios PASS/FAIL T11–T16 | **SIN cambios** | Sectores congelados preservados (verificado por hunks del diff y por las regresiones 16/16 y 10/11+suplemento) |

---

## 7. RIESGOS RESIDUALES

1. **Aprobación pendiente:** C4-A no está aprobado; corresponde a Cris
   (auditoría limitada a la etapa).
2. **Límite de contrato (sección 5.2):** la violación indetectable del contrato
   de propiedad no puede detectarse de forma portátil; el diseño la mitiga por
   encapsulación, no por detección.
3. **Compatibilidad de harness congelado:** el harness v0.2.5 falla su
   aserción de pin de versión (`'v0.2.5'` en banner) contra v0.2.6 — esperado;
   el resto de sus aserciones está verificado por suplemento (sección 3.3).
4. **Cambios de semántica interna observables:** estado de entrada tras error
   de cierre ahora `close_failed_uncertain` (antes `closed`); identidad
   distinta ahora además conserva anomalía en `errors` (antes solo warning).
   Los harness congelados no dependían de esos literales (regresión 16/16 OK;
   el harness v0.2.5 accede a `_entries[t]['state']` vía la compatibilidad de
   claves).
5. **No se ejecutó Android/Termux, ni audio real, ni libsndfile real, ni
   muestras del proyecto; no se declara compatibilidad Android.**
6. **`__pycache__/` sin seguimiento** permanece en el árbol de trabajo (residuo
   de pruebas; no commiteado; no se eliminó por restricción de no-limpieza).

---

## 8. ELEMENTOS NO EJECUTADOS (NOT_EXECUTED, nunca PASS inventado)

- **Prueba 9c en sistemas que no reutilicen el número de fd:** el subcaso
  requiere que el kernel retorne el mismo número al reabrir el mismo archivo;
  si no ocurre, la prueba se registra `NOT_EXECUTED` con la explicación
  (`NotReproducible`). En la ejecución de esta entrega **sí fue reproducible**
  (PASS con límite documentado); la vía `NOT_EXECUTED` queda implementada para
  otros entornos.
- **Android/Termux:** no ejecutado (prohibido). **Audio real / libsndfile
  real / motores DSP / muestras del proyecto:** no ejecutados (prohibidos).
- **C4-B (propagación completa de interrupciones) y C5:** no iniciados, conforme
  a la instrucción ("No comenzar C4-B ni C5 sin recibir nuevas instrucciones").

---

## 9. Confirmaciones explícitas

- No se ejecutó Android/Termux; no se usó root; no hubo audio real; no se
  usaron muestras del proyecto; no se modificaron motores DSP ni archivos de
  `main` (branch); no se fusionaron ramas; no se abrió ni integró PR; no se
  publicó en `main`; no se eliminó archivo alguno; no se realizó limpieza
  automática; no se reconstruyó el instrumento.
- Solo se modificó el archivo autorizado `audioinput_diag_termux.py`, además de
  los artefactos de entrega: `INFORME_CORRECCION_C4_A_v0_2_6.md`,
  `DIFF_v0_2_5_A_v0_2_6.patch` y `pruebas_unitarias_C4_A_v0_2_6.py` (nuevo).
  Los artefactos de v0.2.4 y v0.2.5 quedaron intactos.
- Los criterios funcionales PASS/FAIL de T11–T16 no se modificaron.
- **C4-A no se declara aprobado.**
