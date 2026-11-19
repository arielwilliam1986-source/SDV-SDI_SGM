# Etapa 6F · Auditoría de CLI y bloqueos

Ejecutado realmente (subprocess, no inspección estática):
`scripts/auditoria_cli_6f.py` (57 filas, desarrollo) y el bloque CLI de
`scripts/validar_reserva_6f.py` (30 filas, reserva). Evidencia:
`evidence/cli_6f.json`, `evidence/reserva_cli.json`, `MATRIZ_CLI_6F.csv`.

## 1. Regla aplicada

`alignment_gate(records, blocking, allow, log)` decide antes de crear el
directorio de corrida:

| Estado del diagnóstico | Sin permiso | Con `--allow-misaligned` |
|---|---|---|
| `ALIGNED` / `WARNING` (UNIQUE) | procesa | procesa (permiso no aplica) |
| `MISALIGNED` (UNIQUE con k) | bloquea | procesa, sin shift |
| `AMBIGUOUS` | bloquea | procesa, sin shift |
| `INSUFFICIENT_SIGNAL` | bloquea | procesa, sin shift |
| `NON_INFORMATIVE` | bloquea | procesa, sin shift |
| `ERROR` (incluye NaN y contenedor inválido) | bloquea | **bloquea** |

El permiso queda registrado en el informe como
`alignment_gate.permission = "cli_allow_misaligned"`,
`verdict = "ALLOWED_EXPLICIT"`, con la lista de estados permitidos y
`does_not_bypass = ["validacion_fisica_wav", "datos_no_finitos",
"integridad_identidad_archivo"]`. En MQR el mismo permiso se registra como
ítem `misalignment_user_authorized` de `validation_status`.

## 2. Qué se comprobó en cada modalidad

| Comprobación | Resultado |
|---|---|
| Código de salida por caso y motor | 57/57 y 30/30 coinciden con la expectativa |
| WAV generados cuando el caso se bloquea | 0 en todas las filas bloqueadas |
| Informe generado cuando el caso se bloquea | ausente en todas |
| Informe y 2 WAV cuando se permite | presente en todas las filas permitidas |
| PCM finito en las corridas permitidas | sí en las 30 filas |
| `action.applied_shift_samples` | 0 en todas |
| `action.polarity_changed` | `false` en todas |
| Determinismo con permiso (3 casos × 3 motores) | PCM, exit y diagnóstico idénticos |
| PCM 6F con permiso vs 6E con permiso | idéntico (12/12 pares) |
| Permiso no altera el diagnóstico | igual atribución y mismo k |

Casos bloqueados por defecto en la matriz: `dual_173`, `right_rival_.125`,
`different_lr`, `silent`, `shift_567` (retardo real, política heredada de
bloqueo), `res_dos_origenes`, `res_right_replica_.125_777`, `res_por_tramos`.
Invalidados incluso con permiso: `nonfinite`, `truncated`, `nan_samples`.

## 3. Límites

* No se ejecutaron pruebas de carrera de sustitución de archivo durante una
  corrida completa de CLI; la detección TOCTOU se probó a nivel del módulo de
  integridad (ver `AUDITORIA_WAV_6F.md`).
* No se recorrió toda la matriz de modos (`dry_run`, `analysis_only`,
  `single_file`, `self_test`) ni sus permisos heredados; sólo el modo usado,
  `full_processing`.
* Un código de salida correcto no se considera prueba de seguridad: por eso
  cada fila conserva artefactos, diagnóstico, permiso y PCM.
* El bloqueo depende del diagnóstico: si el estimador declarase `UNIQUE`
  erróneamente, la CLI no lo vetaría. 6F reduce ese riesgo con la prueba de
  réplica y el piso declarado, pero no lo elimina.
