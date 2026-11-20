# Informe de ejecución — Etapa 2 (H01, H02, H03)

**Destinatario:** Cris (auditoría técnica independiente, SDV-SDI_SGM)
**Fecha de ejecución:** 2026-11-20
**Rama autorizada:** `arena/ba75a3d5-sdv-sdi-sgm`
**Archivo evaluado:** `herramientas/diagnostico_audio/audioinput_diag.py`

---

## 1. Commit inicial y commit final

| Item | Valor |
|---|---|
| **Commit inicial de referencia** | `681e9ab3159d1ad5ee830f4e68e7640702448e9e` |
| **SHA-256 inicial del archivo** | `86396b1b0a5fe0342bc7cfda3923205ebcf36683ba01ac25bf7649ab13ef5c8b` |
| **Commit final (Etapa 2)** | `1614fbd901274533a0e167dbc1801a6e838ba8bb` |
| **Parent del commit final** | `0f0371bbdbf9c8a6fea025854adeb4e81da40fe4` (commit del informe de la Etapa 1) |
| **SHA-256 final del archivo** | `27cb0d986c35360f1dedd08802b6bc1761ab2b4845744d4465735d1818f72779` |

Verificación de integridad antes de modificar (el archivo en disco coincidía byte a byte con el commit de referencia, SHA-256 `86396b1b…`). Punto de recuperación verificable creado antes de aplicar cambios: `/tmp/diag_etapa2_recovery.py` (SHA-256 `86396b1b0a5fe0342bc7cfda3923205ebcf36683ba01ac25bf7649ab13ef5c8b`).

Nota de estado del clon: el clon local estaba desincronizado (branch local en `b64f15a`, archivos untracked). Se alineó por **fast-forward** contra `origin/arena/ba75a3d5-sdv-sdi-sgm` (`0f0371b`), sin reescritura de historia, tras verificar que los archivos en disco eran idénticos a los del commit. No se reconstruyó ni se sustituyó trabajo previo.

## 2. Entorno de ejecución

```
$ uname -a
Linux e2b.local 6.1.158+ #1 SMP PREEMPT_DYNAMIC Mon May 11 18:48:24 UTC 2026 x86_64 GNU/Linux

$ python3 --version
Python 3.11.2
```

- **Sistema operativo:** Linux x86_64 (e2b sandbox, kernel 6.1.158).
- **Python:** 3.11.2 (`/usr/bin/python3`).
- **Dependencias:** únicamente el intérprete estándar (`os`, `io`, `shutil`, `contextlib`, `pathlib`, `importlib`, `ast`, `json`, `subprocess`, `signal`, `time`, `traceback`). No se instalaron ni modificaron dependencias. No se ejecuta en Android/Termux ni se procesa audio real.

## 3. Comandos exactos ejecutados

1. **Integridad previa:** `git rev-parse HEAD`, `git status --short`, `git show 681e9ab:herramientas/diagnostico_audio/audioinput_diag.py | sha256sum`, `sha256sum herramientas/diagnostico_audio/audioinput_diag.py`.
2. **Compilación:** `python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py`
3. **Pruebas individuales (10 nuevas de H01/H02/H03):** harness que importa el módulo por ruta (`importlib.util.spec_from_file_location`) e invoca cada `@case` como `mod.GROUPS[grupo][nombre](directorio_temporal)` bajo `contextlib.redirect_stdout`, catching `mod.Unavailable` → NOT_EXECUTED y cualquier otra excepción → FAIL.
4. **Suite completa:** el mismo harness aplicado a los grupos `base`, `fd`, `paths`, `publish`, `term` (el grupo `audio` se excluye por prohibición de pruebas de audio/DSP).
5. **Integridad posterior y diff:** `git diff --stat`, `git diff | grep "^@@"`, `git status --short`.

## 4. Salida real de compilación

```
$ python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py
$ echo COMPILE_OK
COMPILE_OK
```

**Resultado: OK** (código de salida 0, sin errores). Se ejecutó tras cada cambio, incluido el último ajuste de pruebas.

## 5. Resumen de cada cambio (H01, H02, H03)

### H01 — Clasificación de EINVAL

**Problema:** `errno.EINVAL` estaba en el conjunto global `UNSUPPORTED`, por lo que `candidate()` lo convertía indiscriminadamente en `Unavailable` (NOT_EXECUTED), ocultando errores reales de argumentos inválidos.

**Inventario de llamadas a `candidate()`:** `os.symlink` (`symlink()`), `os.open` (`ref_open()`, `fifo_case()`), `rename_noreplace` (3 sitios), `os.link`, `mkfifo`, `pread` (2 sitios), `fsync`. En todas ellas, `EINVAL` significa "argumento inválido", que es un error real del llamador, no una capacidad ambiental ausente. La ausencia real de capacidad se signala con `ENOSYS` / `ENOTSUP` / `EOPNOTSUPP`.

**Cambio (producción, 1 línea + documentación):** se retiró `errno.EINVAL` del conjunto global:

```python
UNSUPPORTED = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP}
```

**Justificación de que ninguna operación necesita EINVAL como ambiental:** ninguna de las operaciones inventariadas usa `EINVAL` para signalar ausencia de capacidad; todas la generan ante argumentos inválidos (flags/modo/offset/fd inadecuados), que son fallos reales. No se implementó excepción local porque no existe justificación válida para aplicar EINVAL universalmente ni por operación. La propagación de errores reales del llamador se conserva como fallos (no se ocultan como NOT_EXECUTED), y la excepción original (tipo, mensaje, errno) se propaga íntegra.

**Pruebas nuevas (grupo `paths`):**
- `candidate_einval_propagates_as_failure` — un EINVAL se propaga como `OSError` real (no `Unavailable`), conservando la excepción original (`exc is original`).
- `candidate_unsupported_errno_is_unavailable_with_cause` — ENOSYS/ENOTSUP/EOPNOTSUPP mantienen la clasificación ambiental (`Unavailable`) y se conserva la cadena de causa estructurada (`error(exc)["cause"]` con el errno original).

### H02 — Clasificación de terminación de procesos

**Problema:** los casos `terminate_parent_dies_descendant_holds_pipe` y `terminate_descendant_survives_sigterm` convertían cualquier `confirmed=False` en `Unavailable`, ocultando posibles fallos reales de terminación.

**Dato mínimo incorporado:** la inspección de grupo no distinguía un proceso **zombi** (estado `Z` en `/proc/<pid>/stat`) de un proceso **activo**. Se añadió el conteo estructurado `zombie_members` a `_group_inspection()` (el campo `fields[0]` de `/proc/<pid>/stat` es el estado del proceso; `"Z"` = zombi).

**Clasificación estructurada (sin coincidencias de texto sobre `reason`):**

```
TERMINATION_CONFIRMED        = "confirmed"             # grupo vacío verificado
TERMINATION_CHILD_ALIVE      = "child_alive"           # hijo vivo tras SIGKILL -> FALLO REAL
TERMINATION_GROUP_ALIVE      = "group_alive"           # miembros vivos en el grupo -> FALLO REAL
TERMINATION_GROUP_UNREAPED   = "group_unreaped"        # miembros todo zombi (sin recolectar) -> ambiental
TERMINATION_INSPECTION_INCOMPLETE = "inspection_incomplete"  # permisos/lectura/malformed -> ambiental
TERMINATION_PROCFS_UNAVAILABLE   = "procfs_unavailable"      # procfs ausente -> ambiental
TERMINATION_GROUP_NOT_VERIFIABLE = "group_not_verifiable"    # sin killpg -> ambiental
```

- `_classify_group_inspection(inspection)` deriva la clase exclusivamente del estado verificado y los conteos estructurados (`state`, `group_members`, `zombie_members`).
- `_confirm_group_termination()` adhiere `classification` a la inspección y distingue en `has_members`: todo zombi → `group_unreaped` (proceso ya salió, no hay init que reap; no se confunde con proceso activo) frente a miembros vivos → `group_alive`.
- `_terminate()` incluye `classification` en todos sus retornos; el caso "hijo vivo tras SIGTERM/SIGKILL" se clasifica como `child_alive` (fallo real).
- `TERMINATION_ENVIRONMENTAL` = {`procfs_unavailable`, `inspection_incomplete`, `group_unreaped`, `group_not_verifiable`} — incertidumbre ambiental que nunca se convierte en confirmación ni en fallo.
- Los dos casos originales se actualizaron para decidir por el campo estructurado: `confirmed` → verificar; clase ambiental → `Unavailable` con la clase; `child_alive`/`group_alive` → `AssertionError` (FAIL real). Su objetivo se conserva: verifican la terminación confirmada cuando el entorno lo permite, y nunca afirman sin evidencia.

**Pruebas nuevas (grupo `term`):**
- `terminate_child_alive_after_sigkill_is_failure` — proceso ficticio siempre vivo tras SIGKILL → `classification == "child_alive"`, `confirmed is False`, y `child_alive` NO pertenece a `TERMINATION_ENVIRONMENTAL`.
- `terminate_group_zombie_vs_alive_classification` — inspección con miembros todo zombi → `group_unreaped` (ambiental); con miembros vivos → `group_alive` (fallo real).
- `terminate_group_inspection_incomplete_classification` — inspección incompleta → `inspection_incomplete`, nunca confirmada.
- `group_inspection_real_zombie_not_confused_with_alive` — con procesos reales: un proceso SIGKILL'd sin recolectar se contabiliza como `zombie_members >= 1`; un proceso activo como `zombie_members == 0`.
- `terminate_procfs_unavailable_descendant_alive` (existente) se amplió con el assert de `classification == "procfs_unavailable"`.

### H03 — Error de `approved_base()` en el worker

**Problema:** en `__main__`, el modo `--_worker` llamaba a `approved_base()` **antes** del bloque `try/finally` que protege la ejecución del worker; si la preparación fallaba, el proceso hijo podía terminar sin emitir un evento `case` estructurado.

**Cambio (producción):** se extrajo la lógica del worker a `_worker_entry(group, name, base_arg, location)`:

- `approved_base()` se evalúa **dentro** del manejo de errores.
- Si falla por condición ambiental (`Unavailable`) → se emite evento `case` con `status: "NOT_EXECUTED"`.
- Si falla por error real (cualquier otra excepción) → evento `case` con `status: "FAIL"`.
- El evento conserva tipo, mensaje y cadena de causa vía `error(exc)` (que incluye `cause` cuando existe).
- Un error de preparación **nunca** se convierte en éxito; el worker no se invoca cuando la preparación falla.
- `base_fd` se inicializa en `None` y se cierra **solo si fue adquirido** (`if base_fd is not None`); si la preparación falló antes de asignarlo, no se asume que el descriptor existe.
- `__main__` invoca `_worker_entry(...)`; el `finally` de cierre del descriptor se mantiene dentro de la función.

**Pruebas nuevas (grupo `fd`):**
- `worker_entry_approval_unavailable_emits_not_executed` — `approved_base` levanta `Unavailable` con causa `OSError(ENOENT)` → evento `NOT_EXECUTED`, tipo `Unavailable`, causa estructurada conservada, worker NO invocado.
- `worker_entry_approval_real_error_emits_fail` — `approved_base` levanta `ValueError` → evento `FAIL`, tipo `ValueError`, mensaje conservado, worker NO invocado.
- `worker_entry_approval_success_closes_base_fd` — preparación correcta → worker invocado con el base, evento `case` emitido, descriptor base cerrado al terminar (`EBADF` posterior verificado).
- `run_case_interprets_worker_events` — lado padre: evento `case` válido se adopta; evento ausente → `FAIL` ("sin resultado válido"); evento contradictorio (`PASS`) junto a fallo del hijo → `FAIL` (nunca PASS).

## 6. Pruebas ejecutadas y sus resultados

### Pruebas individuales nuevas (10/10 ejecutadas)

| Prueba | Grupo | Resultado |
|---|---|---|
| `candidate_einval_propagates_as_failure` | paths | **PASS** |
| `candidate_unsupported_errno_is_unavailable_with_cause` | paths | **PASS** |
| `terminate_child_alive_after_sigkill_is_failure` | term | **PASS** |
| `terminate_group_zombie_vs_alive_classification` | term | **PASS** |
| `terminate_group_inspection_incomplete_classification` | term | **PASS** |
| `group_inspection_real_zombie_not_confused_with_alive` | term | **PASS** |
| `worker_entry_approval_unavailable_emits_not_executed` | fd | **PASS** |
| `worker_entry_approval_real_error_emits_fail` | fd | **PASS** |
| `worker_entry_approval_success_closes_base_fd` | fd | **PASS** |
| `run_case_interprets_worker_events` | fd | **PASS** |

### Suite completa (ejecutada)

```
TOTAL: 90
COUNTS: {"PASS": 88, "NOT_EXECUTED": 2}
FAILURES: (ninguno)
NOT_EXECUTED:
  term/terminate_parent_dies_descendant_holds_pipe: ... (inspection_incomplete)
  term/terminate_descendant_survives_sigterm: ... (inspection_incomplete)
```

- **90 pruebas ejecutadas** (grupos `base`, `fd`, `paths`, `publish`, `term`): **88 PASS, 0 FAIL, 2 NOT_EXECUTED**.
- Baseline previo (Etapa 1, commit `681e9ab`): 80 pruebas → 78 PASS / 2 NOT_EXECUTED. Las 78 pruebas previamente válidas siguen pasando; se añadieron 10 nuevas (todas PASS).

## 7. Pruebas omitidas y motivos

- **Grupo `audio` (10 pruebas):** NO ejecutadas por prohibición explícita de la etapa (no se realizan pruebas DSP ni se procesan archivos de audio reales). Se reportan como **inspeccionadas, no ejecutadas**; no se afirma que pasaron.
- **`term/terminate_parent_dies_descendant_holds_pipe` y `term/terminate_descendant_survives_sigterm`:** **NOT_EXECUTED**. El entorno sandbox no garantiza una inspección de `/proc` concluyente (lecturas con errores durante el recorrido / procesos sin recolectar). Con la nueva clasificación estructurada, estos casos se reportan explícitamente como `Unavailable` con clase `inspection_incomplete`: inspección incompleta, **nunca** confirmación positiva ni fallo afirmado. No se simula un éxito.

## 8. Diff y líneas afectadas

**Commit de la Etapa 2:** `1614fbd901274533a0e167dbc1801a6e838ba8bb` — **1 archivo**: `herramientas/diagnostico_audio/audioinput_diag.py`, **544 insertions / 33 deletions**.

**Líneas afectadas (bloques del diff):**

| Línea (antes) | Contenido |
|---|---|
| `@@ -35` | `UNSUPPORTED` (H01): retirada de `EINVAL` + documentación |
| `@@ -318` `@@ -334` `@@ -378` | `_group_inspection` (H02): `zombie_members` |
| `@@ -997` | Pruebas H01 (grupo paths, 2 pruebas) |
| `@@ -1768` `@@ -1799` | Pruebas `term` originales (H02): clasificación estructurada |
| `@@ -1850` | `terminate_procfs_unavailable_descendant_alive` (H02): assert de clase |
| `@@ -1878` | Pruebas H02 nuevas (grupo term, 4 pruebas) |
| `@@ -2986` | Pruebas H03 nuevas (grupo fd, 4 pruebas) |
| `@@ -3192` | `_worker_entry` (H03, nueva) |
| `@@ -3200` `@@ -3208` | `_confirm_group_termination` (H02): clasificación |
| `@@ -3252` `@@ -3278` `@@ -3305` | `_terminate` (H02): `classification` en retornos |
| `@@ -4238` | `__main__` (H03): invocación de `_worker_entry` |

## 9. Riesgos residuales y cuestiones no demostradas

1. **EINVAL-ambiental futuro:** si en el futuro una operación nueva requiriera tratar `EINVAL` como incompatibilidad ambiental (p.ej., un flag no soportado por un kernel concreto), se necesitaría una excepción local documentada. Actualmente no existe tal operación en el inventario; esto es una decisión explícita, no una omisión.
2. **Zombi vs. vivo en entornos con init:** la distinción `group_unreaped` vs `group_alive` se verifica con inspecciones simuladas y con un zombi real en el sandbox. En un entorno con init que reap, el flujo `confirmed` (grupo vacío verificado) es el esperado; no se pudo observar un grupo confirmado vacío en este sandbox (los dos casos originales quedan NOT_EXECUTED).
3. **`inspection_incomplete` en el sandbox:** el recorrido de `/proc` produce lecturas con errores en este entorno, por lo que la inspección nunca alcanza "empty" para los grupos de los casos originales. La clasificación reporta la incertidumbre explícitamente; no se oculta.
4. **Worker vía subprocess real:** las pruebas H03 invocan `_worker_entry` en proceso con stubs (patrón ya usado por las pruebas de aprobación existentes). La ruta completa `--_worker` por subprocess requiere un base que `approved_base` apruebe, que este entorno no provee (rechaza `/tmp`); no se ejecutó esa ruta end-to-end en esta etapa. La interpretación padre-side (`run_case`) se verifica con stubs de `child_output`.
5. **No se declara confirmación de terminación** en ningún caso sin evidencia de grupo vacío verificable.

## 10. Confirmación de límites de alcance

- **No se modificó ningún motor DSP, fórmula, algoritmo o parámetro.** El archivo modificado es únicamente `herramientas/diagnostico_audio/audioinput_diag.py`.
- **No se modificó `main` ni el PR #2** (`arena/532e54a0-sdv-sdi-sgm`), ni se fusionaron, borraron o se hizo force push.
- **No se ejecutaron pruebas en Android/Termux ni se procesó audio real.**
- **Secciones congeladas de la Etapa 1:** las cuatro pruebas de la Etapa 1 (`base_parent_group_writable_blocked`, `storage_mount_device_mismatch`, `storage_home_outside_private_rejected`, `storage_termux_env_without_evidence`) **no fueron modificadas** (verificado por diff: cero coincidencias en el diff para esas pruebas).
- El trabajo se presenta **entregado, no aprobado**. Cris revisará independientemente el diff, este informe y las pruebas.
