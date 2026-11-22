# 6G.1 — CORRECCIÓN F (memmap retenido por la variable de bucle)

- **Rama:** `arena/c7719286-sdv-sdi-sgm`
- **Commit padre (obligatorio):** `2f4aae411ce1672ec9aa57cc9a967e0556631d85` (auditoría integral AI)
- **Autorización:** puntual, sólo para el hallazgo F (Cris).
- **Resultado:** batería AI completa **27/27 PASS** (padre 2f4aae4: 18/27).
- **6G.1 no está cerrada ni autorizada para integración.**

## 1. Cambio

Se añade una sola sentencia por motor, inmediatamente después del bucle de `flush()` de los memmaps y antes de `del mm`:

| Motor | Unidad | Línea | Contexto |
|---|---|---|---|
| Hardened | `run_experiment` | L1881 | dentro de `if write_masks:` (único camino en que el bucle asigna `arr`) |
| EVO | `run_experiment` | L1992 | ídem |
| MQR | `_run_core` | L2717 | mismo nivel que el bucle (MQR escribe `masks/` siempre) |

```python
for arr in mm.values(): arr.flush()
arr = None   # [6G.1-R/AI-F] suelta la última referencia al memmap retenida por la variable de bucle
del mm
```

- El diff contra el padre es de **3 líneas añadidas** y ninguna eliminada.
- Los `arr` de las comprensiones (`{pid: arr[lo:hi] …}`) tienen su propio ámbito y no se ven afectados.
- No cambia ninguna otra lógica: ni el DSP, ni el Mix, ni `lectura_segura_6g1.py`, ni los fixtures, validadores, motores 6G o `main`.

**Liberación efectiva, comprobada en ejecución.** En los 11 casos en que se crea `masks/model_disagreement_map.npy` (E1 de Hardened y EVO, y los 9 escenarios de MQR), al registrar el aborto:
- no queda ningún fd sobre ese archivo (`/proc/self/fd` + `fdinfo`);
- no queda ningún mapeo (`/proc/self/maps`);
- la referencia débil al memmap está muerta.

El GC está deshabilitado en todo el proceso, así que la liberación es la determinista por recuento de referencias al soltar `arr` y `mm`, no una recolección.

## 2. Validación: batería AI completa (27 casos)

**Método:**
- Se reutilizan sin modificarlos el inyector (`scripts/inyeccion_auditoria_6g1/ejecutar_motor_auditoria.py`) y el verificador de la batería AI (`pruebas_auditoria_cierre_6g1.verificar`), con las mismas comprobaciones y los mismos argumentos de motor.
- Se añade la comprobación explícita `hallazgo_F_resuelto`.
- Script: `scripts/pruebas_correccion_f_6g1.py`. Escribe con nombres nuevos y no sobrescribe la evidencia AI de 2f4aae4.

| Escenario | Hardened | EVO | MQR |
|---|---|---|---|
| A1 cierre WAV fallido (antes del cierre físico) | PASS 30/30 | PASS 30/30 | PASS 30/30 |
| A2 cierre WAV fallido (después del cierre físico) | PASS 30/30 | PASS 30/30 | PASS 30/30 |
| B1 cierre interno de MixHandle fallido (antes) | PASS 29/29 | PASS 29/29 | PASS 29/29 |
| B2 cierre interno de MixHandle fallido (después) | PASS 29/29 | PASS 29/29 | PASS 29/29 |
| C1 `Tee.close()` fallido (antes) | PASS 29/29 | PASS 29/29 | PASS 29/29 |
| C2 `Tee.close()` fallido (después) | PASS 29/29 | PASS 29/29 | PASS 29/29 |
| D1 constructor falla tras abrir el 1.er escritor | PASS 28/28 | PASS 28/28 | PASS 28/28 |
| D2 D1 + cierre fallido del 1.er escritor | PASS 30/30 | PASS 30/30 | PASS 30/30 |
| E1 integridad final del Mix fallida tras generar `masks/` | PASS 30/30 | PASS 30/30 | PASS 30/30 |

**Estado del aborto por escenario** (igual en los tres motores):

| Escenario | `completo` | `log_cerrado` | Traslado |
|---|---|---|---|
| A, B, D2 | False | True | no |
| C | False | False | no |
| D1 | True | True | `_aborted` |
| E1 | **True** | **True** | no (MIX_CAMBIADO: traslado no solicitado) |

E1 queda ahora con todo cerrado y acreditado, y aun así no hay traslado ni se elimina ningún archivo. En el padre, `completo` era False y quedaba escritura abierta.

**Cubierto en cada caso:**
- código 2, nunca `EXIT_OK`, y `run_experiment` sin éxito;
- ABORT schema `/3` con `resultados_validos=[]`;
- sin traslado cuando el cierre no está acreditado o en MIX_CAMBIADO;
- provisional conservado con su identidad dev/ino;
- ningún archivo eliminado; `masks/` conservada e invalidada (E1);
- ninguna publicación como éxito;
- al registrar: sin fds ni mapeos bajo la salida o sobre las entradas, escritores y lectores cerrados y **todos los memmaps liberados**;
- ningún cierre después del registro;
- SHA estable tras el registro y al terminar el proceso, sin escrituras posteriores;
- **GC deshabilitado** antes de cualquier importación y 0 colecciones posteriores (comprobado con `gc.callbacks`).

**Diagnóstico sobre el padre 2f4aae4 (misma batería): 18/27.**
- Fallan exactamente los 9 casos documentados en AI: Hardened E1, EVO E1 y MQR A1/A2/B1/B2/C1/C2/E1.
- En todos falla `hallazgo_F_resuelto`.
- El indicador `atribuible_solo_a_F` sale False en el padre sólo porque la nueva comprobación `hallazgo_F_resuelto` no figura en la lista `CHECKS_F` de AI. Los fallos son los mismos 9 de AI más esta comprobación.

## 3. AST frente al padre (`scripts/verificar_ast_correccion_f_6g1.py`): OK

- Sólo cambian `run_experiment` (Hardened/EVO) y `_run_core` (MQR).
- Hay exactamente una inserción `arr = None` por motor:
  - situada tras `for arr in mm.values()`;
  - la siguiente sentencia es `del mm`;
  - al retirarla, el AST es **idéntico** al del padre.
- El resto de unidades (a nivel de método) y las sentencias de nivel superior son idénticas.
- `lectura_segura_6g1.py` es idéntico byte a byte.

## 4. Entregables

| Archivo | Contenido |
|---|---|
| `CORRECCION_F_6G1.md` | este informe |
| `evidence/pruebas_correccion_f_6g1.json` | detalle de los 27 casos, corregido y padre |
| `evidence/matriz_correccion_f_6g1.csv` | matriz, con columnas `aplica_F` y `hallazgo_F_resuelto` |
| `evidence/inyecciones_correccion_f_6g1/<motor>_<esc>.json` (27) | evidencia por inyección: eventos ordenados, fotografías `/proc`, memmaps, informe de cierre y resultado del aborto |
| `evidence/ast_correccion_f_6g1.json` | verificación AST |
| `scripts/pruebas_correccion_f_6g1.py`, `scripts/verificar_ast_correccion_f_6g1.py` | scripts |
| `MANIFEST_CORRECCION_F_6G1.json`, `SHA256SUMS_CORRECCION_F_6G1.txt` | manifiesto y sumas |
| `DIFF_CORRECCION_F_6G1_vs_2f4aae4.patch` | se aplica y se revierte sobre 2f4aae4 |

**Sin modificar:**
- evidencia AI (2f4aae4), CR-R1, CR, CV y la prueba DSP;
- inyector y verificador AI (sólo se importan);
- motores 6G, `main`, fixtures y validadores.

**No ejecutado:**
- baterías históricas, H1, C-R1, H2, CV y la prueba DSP;
- audio real, Android y Termux.

No se ha fusionado ni integrado nada.
