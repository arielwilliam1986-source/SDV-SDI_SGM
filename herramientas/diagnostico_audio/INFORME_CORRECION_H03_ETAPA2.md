# Informe de corrección — Etapa 2, H03 (H03-A y H03-B)

**Destinatario:** Cris (revisión independiente, SDV-SDI_SGM)
**Fecha de ejecución:** 2026-11-20
**Rama:** `arena/ba75a3d5-sdv-sdi-sgm`
**Archivo:** `herramientas/diagnostico_audio/audioinput_diag.py`

---

## 1. Punto de partida y punto de recuperación

| Item | Valor |
|---|---|
| **Commit de código de referencia** | `1614fbd901274533a0e167dbc1801a6e838ba8bb` |
| **Commit de inicio de trabajo** | `db4e2fcf3495a08cd35c28111d1d368b02b85987` (informe Etapa 2) |
| **SHA-256 inicial del archivo** | `27cb0d986c35360f1dedd08802b6bc1761ab2b4845744d4465735d1818f72779` |
| **Commit final (corrección H03)** | `ac97e5cb8960191205d09933745d6e401e6d4473` |
| **SHA-256 final del archivo** | `eac9ee6777ff61e354d4358f83f97b275b41445a0e862c288265037e6dc3bfe9` |

- **Punto de recuperación verificable** creado antes de modificar: `/tmp/diag_h03_recovery.py`, SHA-256 `27cb0d986c35360f1dedd08802b6bc1761ab2b4845744d4465735d1818f72779` (idéntico al archivo inicial).
- Verificación previa: `git rev-parse HEAD` → `db4e2fc…` (padre `1614fbd…`); `git status --short` limpio; blob en disco == blob de referencia (SHA-256 `27cb0d98…`).

## 2. Entorno de ejecución

```
$ uname -a
Linux e2b.local 6.1.158+ #1 SMP PREEMPT_DYNAMIC Mon May 11 18:48:24 UTC 2026 x86_64 GNU/Linux

$ python3 --version
Python 3.11.2
```

- Linux x86_64 (e2b sandbox, kernel 6.1.158); Python 3.11.2 (`/usr/bin/python3`).
- Solo intérprete estándar (`os`, `io`, `shutil`, `contextlib`, `pathlib`, `importlib`, `json`, `subprocess`, `signal`, `errno`). No se instalaron ni modificaron dependencias. No se ejecutaron pruebas de audio/DSP ni en Android/Termux.

## 3. Comandos exactos ejecutados

1. **Integridad previa:** `git rev-parse HEAD`, `git log -1 --format="%H %P"`, `git status --short`, `sha256sum herramientas/diagnostico_audio/audioinput_diag.py`, `git show 1614fbd:herramientas/diagnostico_audio/audioinput_diag.py | sha256sum`.
2. **Compilación (tras cada cambio):** `python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py`
3. **Pruebas individuales H03:** harness que importa el módulo por ruta e invoca cada `@case` como `mod.GROUPS[grupo][nombre](directorio_temporal)` bajo `contextlib.redirect_stdout`, catching `mod.Unavailable` → NOT_EXECUTED y cualquier otra excepción → FAIL.
4. **Suite completa no-audio:** mismo harness sobre grupos `base`, `fd`, `paths`, `publish`, `term` (grupo `audio` excluido por prohibición).
5. **Integridad posterior y diff:** `git diff --stat`, `git diff | grep "^@@"`, `git status --short`.

## 4. Salida real de compilación

```
$ python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py
$ echo COMPILE_OK
COMPILE_OK
```

**Resultado: OK** (código de salida 0, sin errores).

## 5. Cambios implementados

### H03-A — Manejo de interrupciones en `_worker_entry()`

**Defecto:** `except BaseException` capturaba `KeyboardInterrupt` y `SystemExit` como errores operativos ordinarios (emitiendo un evento `case` FAIL), confundiendo una interrupción del proceso con un error operativo.

**Corrección:**
- Se distinguen las interrupciones (`KeyboardInterrupt`, `SystemExit`) de las excepciones operativas.
- En la preparación (`approved_base`) y en la ejecución (`worker`), una interrupción:
  - **no** emite evento `case` de resultado (no se convierte en PASS ni en FAIL operativo ni en NOT_EXECUTED fabricado);
  - emite un evento estructurado **`case_interrupted`** con semántica definida: *el worker fue interrumpido y no produjo un resultado terminal de prueba*; lleva `group`, `test`, `interruption` (tipo) y `message`;
  - **re-lanza** la interrupción (el proceso termina por la interrupción);
  - **conserva el cierre del descriptor** cuando fue adquirido: en la preparación se cierra `base_fd` si está asignado (con protección contra `OSError`); en la ejecución el cierre se mantiene en el `finally`.
- La captura operativa se reduce a `except BaseException` **después** de las capturas de interrupción, por lo que solo errores reales operativos alcanzan el evento `case` FAIL.

### H03-B — Validación de eventos terminales en `run_case()`

**Defecto:** el padre aceptaba simplemente el último evento `case` recibido.

**Corrección:** se recopila **toda** la lista de eventos `case` y se valida:

1. **Exactamente un evento terminal:** 0 → FAIL ("proceso hijo sin resultado válido"); >1 → FAIL ("eventos terminales duplicados o contradictorios").
2. **Identidad:** el evento debe coincidir con el `group` y `test` solicitados; identidad incorrecta → FAIL.
3. **Estado permitido:** `PASS`, `FAIL` o `NOT_EXECUTED`; estado desconocido → FAIL.
4. **Duplicados/contradicciones:** cubiertos por el conteo exacto y por la precedencia de `failed` (fallo real del hijo gana sobre cualquier evento).
5. **Código de salida no satisfactorio:** `rc != 0` → FAIL ("código de salida no satisfactorio"), incluso si el evento es PASS.
6. **Ausencia, malformado, identidad incorrecta, estado desconocido:** todos → FAIL.
7. **Evento `case_interrupted`:** el padre lo interpreta como resultado no válido → FAIL, incluso si acompaña a un evento `case` PASS o si el código de salida es 0.

Precedencia final: `failed` (fallo real del hijo) > `case_interrupted` > conteo/identidad/estado > `rc != 0` > evento válido.

## 6. Pruebas nuevas y existentes relacionadas

### Pruebas nuevas (3) y existentes (4) — todas ejecutadas

| Prueba | Resultado |
|---|---|
| `fd/worker_entry_keyboard_interrupt_emits_interruption` (**nueva, H03-A**) | **PASS** |
| `fd/worker_entry_interruption_during_preparation` (**nueva, H03-A**) | **PASS** |
| `fd/run_case_interruption_event_never_pass` (**nueva, H03-A/H03-B**) | **PASS** |
| `fd/run_case_interprets_worker_events` (**reescrita, H03-B**: 12 escenarios) | **PASS** |
| `fd/worker_entry_approval_unavailable_emits_not_executed` (existente) | **PASS** |
| `fd/worker_entry_approval_real_error_emits_fail` (existente) | **PASS** |
| `fd/worker_entry_approval_success_closes_base_fd` (existente) | **PASS** |

**Escenarios verificados por `run_case_interprets_worker_events` (12, todos PASS):**
1. Único evento válido NOT_EXECUTED → NOT_EXECUTED.
2. Ningún evento → FAIL.
3. FAIL seguido de PASS → FAIL (duplicado).
4. PASS seguido de FAIL → FAIL (duplicado).
5. Grupo incorrecto → FAIL.
6. Prueba incorrecta → FAIL.
7. Estado desconocido → FAIL.
8. PASS con código de salida no satisfactorio → FAIL.
9. NOT_EXECUTED válido → NOT_EXECUTED.
10. PASS válido → PASS.
11. PASS junto a fallo del hijo → FAIL (contradictorio).
12. Línea malformada (JSON inválido) como única salida → FAIL.

**Verificación de interrupción (H03-A):**
- `worker_entry_keyboard_interrupt_emits_interruption`: `KeyboardInterrupt` durante el worker → evento `case_interrupted` con tipo `KeyboardInterrupt`, re-lanzamiento, **no** emite `case`, descriptor base cerrado (EBADF posterior verificado).
- `worker_entry_interruption_during_preparation`: `SystemExit(3)` durante `approved_base` → evento `case_interrupted` tipo `SystemExit`, re-lanzamiento con código 3, no emite `case`.
- `run_case_interruption_event_never_pass`: `case_interrupted` solo → FAIL; `case_interrupted` junto a `case` PASS válido → FAIL.

## 7. Suite completa no-audio (ejecutada)

```
TOTAL: 93
COUNTS: {"PASS": 91, "NOT_EXECUTED": 2}
FAILURES: (ninguno)
NOT_EXECUTED: ['term/terminate_parent_dies_descendant_holds_pipe',
               'term/terminate_descendant_survives_sigterm']
FROZEN: {'base/base_parent_group_writable_blocked': 'PASS',
         'base/storage_mount_device_mismatch': 'PASS',
         'base/storage_home_outside_private_rejected': 'PASS',
         'base/storage_termux_env_without_evidence': 'PASS'}
```

- **93 pruebas ejecutadas** (grupos `base`, `fd`, `paths`, `publish`, `term`): **91 PASS, 0 FAIL, 2 NOT_EXECUTED**.
- Las **cuatro pruebas congeladas de la Etapa 1 (H01/H04) siguen PASS**.
- Las pruebas previas de H01/H02/H03 (Etapa 2 anterior) siguen PASS; no se modificó H01 ni H02 (diff: 0 coincidencias con `UNSUPPORTED`, `_group_inspection`, `_classify_group_inspection`, `_confirm_group_termination`, `_terminate`).

## 8. Pruebas no ejecutadas y motivos (NO_APPLICABLE / NOT_EXECUTED)

| Estado | Prueba | Motivo |
|---|---|---|
| **NOT_EXECUTED** | `term/terminate_parent_dies_descendant_holds_pipe` | Entorno sandbox: la inspección de `/proc` del grupo no es concluyente (lecturas con errores durante el recorrido). Se reporta como `Unavailable` con clase `inspection_incomplete`; nunca se afirma terminación ni se simula éxito. |
| **NOT_EXECUTED** | `term/terminate_descendant_survives_sigterm` | Igual motivo (limitación ambiental demostrada, no defecto). |
| **NOT_APPLICABLE** | Grupo `audio` (10 pruebas) | Fuera del alcance de la etapa: prohibición de pruebas de audio/DSP y de procesar muestras reales. Inspeccionadas, no ejecutadas. |

No se cuentan los NOT_EXECUTED como pruebas ejecutadas.

## 9. Resumen del diff

**Commit final:** `ac97e5cb8960191205d09933745d6e401e6d4473` — **1 archivo**: `herramientas/diagnostico_audio/audioinput_diag.py`, **285 insertions / 24 deletions**.

**Bloques afectados:**

| Línea (antes) | Contenido |
|---|---|
| `@@ -3363` | Reescritura de `run_case_interprets_worker_events` (prueba propia de la etapa, en alcance) |
| `@@ -3384` | Nuevas pruebas H03-A (2) + reescritura completa de la prueba H03-B |
| `@@ -3806` `@@ -3816` `@@ -3823` | `_worker_entry` (H03-A): capturas de interrupción, evento `case_interrupted`, re-lanzamiento, cierre del descriptor |
| `@@ -3898` `@@ -3907` | `run_case` (H03-B): validación de eventos terminales |

## 10. Confirmación de límites de alcance

- **No se modificó H01 ni H02** (ni sus pruebas ni sus funciones de producción): 0 coincidencias en el diff.
- **No se modificaron las cuatro pruebas congeladas de la Etapa 1** (`base_parent_group_writable_blocked`, `storage_mount_device_mismatch`, `storage_home_outside_private_rejected`, `storage_termux_env_without_evidence`): 0 coincidencias en el diff; todas PASS en la suite.
- **No se modificó lógica de AudioInput ajena a H03**, ni motores DSP, fórmulas, parámetros ni algoritmos.
- **No se ejecutó audio ni DSP, ni pruebas Android/Termux.**
- **No se tocó `main` ni el PR #2**; no se fusionaron, borraron ramas ni se hizo force push.
- **No se declara H03 aprobado.** La entrega queda a la revisión independiente de Cris.
