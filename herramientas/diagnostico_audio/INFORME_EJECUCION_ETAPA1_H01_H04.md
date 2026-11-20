# Informe de ejecución — Etapa 1 (H01 y H04)

**Destinatario:** Cris (auditoría técnica independiente, SDV-SDI_SGM)
**Fecha de ejecución:** 2026-11-20
**Rama:** `arena/ba75a3d5-sdv-sdi-sgm`
**Archivo evaluado:** `herramientas/diagnostico_audio/audioinput_diag.py`

---

## 1. Commit exacto y hash del archivo probado

| Item | Valor |
|---|---|
| **Commit de referencia** | `681e9ab3159d1ad5ee830f4e68e7640702448e9e` |
| **Parent commit** | `470da6b2b6a550f390deb5d94535208464f3c8b0` |
| **Fecha del commit** | 2026-11-20 14:29:29 +0000 |
| **Blob SHA-256 del archivo** | `86396b1b0a5fe0342bc7cfda3923205ebcf36683ba01ac25bf7649ab13ef5c8b` |

Verificación de integridad (ejecutada antes y después de la validación):

```
$ git rev-parse HEAD
681e9ab3159d1ad5ee830f4e68e7640702448e9e

$ git show HEAD:herramientas/diagnostico_audio/audioinput_diag.py | sha256sum
86396b1b0a5fe0342bc7cfda3923205ebcf36683ba01ac25bf7649ab13ef5c8b  -

$ sha256sum herramientas/diagnostico_audio/audioinput_diag.py
86396b1b0a5fe0342bc7cfda3923205ebcf36683ba01ac25bf7649ab13ef5c8b  herramientas/diagnostico_audio/audioinput_diag.py
```

El blob en disco coincide byte a byte con el blob del commit de referencia.

## 2. Entorno de ejecución

```
$ uname -a
Linux e2b.local 6.1.158+ #1 SMP PREEMPT_DYNAMIC Mon May 11 18:48:24 UTC 2026 x86_64 GNU/Linux

$ python3 --version
Python 3.11.2

$ python3 -c "import sys; print(sys.executable)"
/usr/bin/python3
```

- **Sistema operativo:** Linux x86_64 (e2b sandbox, kernel 6.1.158).
- **Python:** 3.11.2 (`/usr/bin/python3`).
- **Dependencias:** el módulo `audioinput_diag.py` se carga vía `importlib` (importación por ruta). No se instalaron ni modificaron dependencias; la validación usa únicamente el intérprete estándar (`os`, `io`, `shutil`, `contextlib`, `pathlib`, `importlib`, `ast`). No se ejecuta en Android/Termux ni se procesa audio real.

## 3. Comandos exactos ejecutados

1. **Integridad previa** (comprobación de HEAD, árbol y hash del archivo):
   `git rev-parse HEAD`, `git log -1 --format="%H %P %ad" --date=iso`, `git status --short`, `git show HEAD:herramientas/diagnostico_audio/audioinput_diag.py | sha256sum`, `sha256sum herramientas/diagnostico_audio/audioinput_diag.py`

2. **Compilación**:
   `python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py`

3. **Pruebas individuales (H01 + 3 H04)**:
   `python3 -` con un harness que importa el módulo por ruta (`importlib.util.spec_from_file_location("diagmod", "herramientas/diagnostico_audio/audioinput_diag.py")`) e invoca cada `@case` de la forma `mod.GROUPS["base"][nombre](directorio_temporal)` dentro de `contextlib.redirect_stdout(io.StringIO())`, catching `mod.Unavailable` → NOT_EXECUTED y cualquier otra excepción → FAIL.

4. **Suite completa**:
   `python3 -` con el mismo harness aplicado a todos los grupos `base`, `fd`, `paths`, `publish`, `term` (el grupo `audio` se excluye por prohibición de pruebas de audio/DSP).

5. **Integridad posterior**:
   `git status --short` y `git rev-parse HEAD` (ver sección 9).

## 4. Salida real de compilación

```
$ python3 -m py_compile herramientas/diagnostico_audio/audioinput_diag.py; echo "PY_COMPILE_EXIT=$?"
PY_COMPILE_EXIT=0
```

**Resultado: OK** (código de salida 0, sin errores).

## 5. Resultados individuales

### H01 — `base_parent_group_writable_blocked()`

**RESULTADO: PASS (ejecutada)**

Salida real (valor de retorno de la prueba):

```
RESULT base/base_parent_group_writable_blocked: PASS
  returned: {'blockers': ['directorio padre globalmente escribible con sticky, pero propietario no confiable (uid 0 != 1001): el sticky no demuestra confianza: descriptor 5', 'directorio padre escribible por grupo: el grupo contiene miembros distintos del usuario efectivo; no se puede demostrar aislamiento suficiente: descriptor 10'], 'control_clean': True}
```

- **Caso positivo:** la auditoría bloquea el directorio padre creado por el motivo de grupo — `"directorio padre escribible por grupo: el grupo contiene miembros distintos del usuario efectivo; no se puede demostrar aislamiento suficiente: descriptor 10"` — donde el descriptor `10` es el del padre creado por la prueba. (El bloqueo sticky del descriptor `5` es un bloqueador adicional de la auditoría, no el verificado por esta prueba.)
- **Control negativo:** `control_clean: True` — con la composición de grupo simulada `{euid}` únicamente, la política de producción **no** emite bloqueo por grupo para ese mismo padre, lo que demuestra que el bloqueo depende de la composición simulada y que la prueba no altera la política de producción.

### H04 — `storage_mount_device_mismatch`

**RESULTADO: PASS (ejecutada)**

```
RESULT base/storage_mount_device_mismatch: PASS
  returned: {'detected_class': 'other', 'control_class': 'termux_private'}
```

### H04 — `storage_home_outside_private_rejected`

**RESULTADO: PASS (ejecutada)**

```
RESULT base/storage_home_outside_private_rejected: PASS
  returned: {'detected_class': 'other', 'control_class': 'termux_private'}
```

### H04 — `storage_termux_env_without_evidence`

**RESULTADO: PASS (ejecutada)**

```
RESULT base/storage_termux_env_without_evidence: PASS
  returned: {'detected_class': 'other', 'control_class': 'termux_private'}
```

**Interpretación de las tres pruebas H04:** en cada caso, `detected_class` es `"other"` (rechazo) y el `control_class` es `"termux_private"`, es decir, el control con el mismo descriptor/montaje y condición canónica esperada se clasifica como `termux_private`. Esto demuestra que la condición verificada por cada prueba es la que decide el resultado, no el caso de montaje no vinculado.

## 6. Resultado de la suite completa

**La suite se ejecutó.** Grupos ejecutados: `base`, `fd`, `paths`, `publish`, `term` (el grupo `audio`, 10 pruebas, se excluye por prohibición de pruebas de audio/DSP).

Salida real:

```
SUITE_TOTAL_EXECUTED: 80
SUITE_COUNTS: {"PASS": 78, "NOT_EXECUTED": 2}
SUITE_FAILURES: none
SUITE_NOT_EXECUTED: ['term/terminate_parent_dies_descendant_holds_pipe', 'term/terminate_descendant_survives_sigterm']
```

**Resumen de la suite:**

| Estado | Cantidad |
|---|---|
| PASSED | 78 |
| FAILED | 0 |
| NOT_EXECUTED | 2 |
| **Total ejecutados** | **80** |

**Pruebas NOT_EXECUTED (no se presentan como aprobadas):**
- `term/terminate_parent_dies_descendant_holds_pipe`
- `term/terminate_descendant_survives_sigterm`

**Inspección-only (no ejecutadas, no pertenecientes a la ejecución):** las 10 pruebas del grupo `audio` no se ejecutaron por prohibición explícita de pruebas de audio/DSP.

## 7. Errores completos

**No hubo errores de compilación ni errores en las pruebas ejecutadas.** No se registraron excepciones durante `py_compile`, ni durante la ejecución individual de H01 y las tres pruebas H04, ni durante la suite (0 FAILED).

Las dos pruebas `term` no produciron errores de tipo FAIL: elevó `Unavailable` (excepciones controladas de disponibilidad) por la razón ambiental detallada en la sección 8.

## 8. Limitaciones y pruebas que no pudieron ejecutarse

1. **`term/terminate_parent_dies_descendant_holds_pipe`** y **`term/terminate_descendant_survives_sigterm`**: estas pruebas requieren que los procesos de grupo SIGKILL'd sean recolectados por init. En este entorno sandbox no hay un init que reap los procesos, por lo que los miembros del grupo permanecen como zombi, la inspección de `/proc` de grupo nunca alcanza el estado "vacío" esperado, y la prueba eleva `Unavailable` → **NOT_EXECUTED**. Esto es una limitación del entorno de ejecución, no un defecto de la prueba ni del código. Para su ejecución se requiere un entorno con init que reap procesos.

2. **Grupo `audio` (10 pruebas):** no ejecutadas por prohibición explícita de la etapa (no se realizan pruebas DSP ni se procesan archivos de audio reales).

3. **Entorno no Android/Termux:** toda la validación se realizó en Linux x86_64; se cumple la restricción de no ejecutar en Android/Termux.

## 9. Confirmación de que el código no fue modificado durante la validación

- Al inicio de la validación: `git rev-parse HEAD` → `681e9ab3159d1ad5ee830f4e68e7640702448e9e`; `git status --short` sin salida (árbol limpio); blob en disco == blob del commit (SHA-256 `86396b1b…`).
- Después de `py_compile` y de la ejecución de todas las pruebas: `git status --short` sin salida y `git rev-parse HEAD` → `681e9ab3159d1ad5ee830f4e68e7640702448e9e`.
- **No se modificó el script `audioinput_diag.py` ni ningún otro archivo durante esta validación.** El único archivo creado por esta solicitud es el propio informe `INFORME_EJECUCION_ETAPA1_H01_H04.md`. No se tocaron `main`, el PR #2, ni se realizaron fusiones, borrados o force push.

---

*El informe contiene únicamente salidas reales de ejecución capturadas durante esta validación.*
