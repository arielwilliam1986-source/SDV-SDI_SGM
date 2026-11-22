# 6G.1 — AUDITORÍA INTEGRAL: CIERRE REAL DE WRAPPERS Y RETENCIÓN DE ABORTOS

- **Rama:** `arena/c7719286-sdv-sdi-sgm`
- **Commit padre (obligatorio):** `6a93e4ece2dcb1f4d79a5a4bb1501ace080f5dcd` (CR-R1)
- **Estado:** A–E implementados. La batería obligatoria da **18/27 PASS**. Los **9 FAIL** tienen una única causa: el **hallazgo F**, un defecto que ya existía en 6a93e4e y queda fuera de A–E. **No se ha corregido.** Según la instrucción, me detengo y lo documento.
- **6G.1 no está cerrada ni autorizada para integración.**

## 1. Resultado

| Elemento | Resultado |
|---|---|
| Batería AI (A1–E1 × Hardened/EVO/MQR), motores corregidos | **18/27 PASS** · 9 FAIL, todos atribuibles **sólo** a F (`fail_no_atribuibles = 0`) |
| Misma batería sobre la base 6a93e4e (diagnóstico) | **0/27 PASS** |
| AST frente a 6a93e4e, a nivel de método | **OK**: DSP intacto (12/12 Hardened/EVO, 11/11 MQR) y sólo cambian unidades de ciclo de vida o cierre |
| Cambios en DSP, Mix, fixtures, validadores, motores 6G o `main` | Ninguno |

### Matriz (motores corregidos)

| Escenario | Hardened | EVO | MQR |
|---|---|---|---|
| A1 cierre WAV fallido (antes del cierre físico) | PASS 29/29 | PASS 29/29 | FAIL 26/29 (F) |
| A2 cierre WAV fallido (después del cierre físico) | PASS 29/29 | PASS 29/29 | FAIL 26/29 (F) |
| B1 cierre interno de MixHandle fallido (antes) | PASS 28/28 | PASS 28/28 | FAIL 25/28 (F) |
| B2 cierre interno de MixHandle fallido (después) | PASS 28/28 | PASS 28/28 | FAIL 25/28 (F) |
| C1 `Tee.close()` fallido (antes del cierre físico) | PASS 28/28 | PASS 28/28 | FAIL 26/28 (F) |
| C2 `Tee.close()` fallido (después del cierre físico) | PASS 28/28 | PASS 28/28 | FAIL 26/28 (F) |
| D1 constructor falla tras abrir el 1.er escritor | PASS 27/27 | PASS 27/27 | PASS 27/27 |
| D2 D1 + cierre fallido del 1.er escritor | PASS 29/29 | PASS 29/29 | PASS 29/29 |
| E1 integridad final del Mix fallida tras generar `masks/` | FAIL 23/29 (F) | FAIL 23/29 (F) | FAIL 24/29 (F) |

En las 9 filas FAIL:
- **Todas las comprobaciones propias de A–E dan OK:**
  - el error inyectado aparece en el informe de cierre y en el motivo de conservación;
  - `completo=False`;
  - ABORT `/3` con `resultados_validos=[]`;
  - no hay traslado y el provisional se conserva en su sitio;
  - no se elimina ningún archivo y `masks/` se conserva;
  - no hay publicación como éxito;
  - el GC está deshabilitado y no hace ninguna colección.
- **Sólo fallan las comprobaciones de fds/mmaps** (y las que se derivan de ellas, como `log_cerrado` o `completo` en E1). Fallan porque, al registrar el ABORT, sigue abierto con escritura un único recurso: `masks/model_disagreement_map.npy` (fd + mapeo). La columna `atribuible_solo_a_F` del CSV lo comprueba caso por caso.

### Base 6a93e4e (diagnóstico)

| Escenario | Comportamiento en la base |
|---|---|
| A1/A2, B1/B2, C1/C2 (los 3 motores) | **Salida 0 y publicación como ÉXITO** pese al cierre fallido: el error se tragaba y la referencia pasaba a `None` |
| D1/D2 | El primer escritor queda huérfano: abierto, fuera del protocolo y no invalidado |
| E1 Hardened/EVO | Se elimina `masks/` antes de la guarda (`ningun_archivo_eliminado` FAIL) |
| E1 MQR | Sólo F (`atribuible_solo_a_F=True` también en la base), lo que confirma que F existía antes |

## 2. Correcciones (A–E)

### `lectura_segura_6g1.py`

- **Nuevo `CierreNoAcreditado6G1(RuntimeError)`.** Lo usa todo cierre no acreditado e impide publicar.
- **Registro de fallos de cierre:**
  - `fallo_cierre_6g1` lee el atributo `_cierre_fallido_6g1` del propio objeto;
  - `_marcar_fallo_cierre_6g1` guarda sólo el primer fallo.
- **`_estado_fisico_6g1`** da el estado físico.
- **`_cerrado_6g1`** pasa a ser el estado **acreditado**: `False` si consta algún fallo, aunque `closed` sea True.
  - Esto importa porque soundfile 0.13.1 pone `_file=None` *antes* de elevar el error de `sf_close`.
- **`cerrar_verificado_6g1(obj) -> (ok, err)`:**
  - nunca eleva;
  - cierra sólo si el objeto no consta cerrado físicamente, sin dobles cierres;
  - el fallo persiste;
  - `ok` sólo es True con cierre físico y sin ningún fallo, ni presente ni previo.
- **`_cerrar_idempotente_6g1`** delega en `cerrar_verificado_6g1`. Por eso `cerrar_recursos_corrida_6g1` (escritores y lectores) ve los fallos previos como `(False, "cierre fallido previo: …")`, lo que da `completo=False`.
- **B · `MixHandle`:**
  - `_cerrar_6g1()` nunca eleva y devuelve la lista de errores;
  - `_snd` se suelta sólo si `closed` es True;
  - `fd` pasa a `None` **antes** de un único `os.close` (sin reintento, para no cerrar un fd reutilizado);
  - el primer fallo persiste;
  - `close()` eleva `OSError` si hubo error;
  - si la apertura falla, se limpia con `_cerrar_6g1()` y se re-eleva.
- **C · `preparar_aborto_6g1`:**
  - `cerrar_log` puede devolver `(ok, err)`;
  - una excepción u `ok=False` da `log_cerrado=False`, `completo=False` y añade el error;
  - si no, `log_cerrado` sólo es True cuando la comprobación en `/proc` es observable y no queda escritura abierta.
- **D · `runner_parcial_6g1(runner, registro)`:** incorpora el runner parcial a la lista de la corrida y cierra de forma verificable los escritores ya abiertos.

### Motores (Hardened, EVO, MQR)

- **A · `CandidateRunner.close()`:**
  - usa `cerrar_verificado_6g1` y **conserva** las referencias;
  - si algo falla, eleva `CierreNoAcreditado6G1` con todos los errores.
  - Resultado: la corrida va al manejador `Exception` (EXCEPCION), el protocolo ve el fallo marcado, `completo=False` y no hay traslado.
- **B · Guarda final (`finally` del Mix):** el error de cierre del Mix se captura y, después del `try`, se eleva `CierreNoAcreditado6G1("cierre del Mix no acreditado…")` antes de la comprobación `MIX_CAMBIADO`.
- **C · `Tee` / `close_tee`:**
  - **`Tee.close()`:** guarda `error_cierre_6g1`, re-eleva el error y suelta `_file` sólo si `f.closed`.
  - **`close_tee() -> (ok, err)`:**
    - nunca eleva;
    - conserva `_G_TEE` si el archivo no quedó cerrado;
    - sigue informando el fallo, a través de `_G_TEE_FALLO`, hasta el siguiente `init_tee`.
  - **Punto de comprobación:** el camino normal comprueba el resultado **antes de publicar** (Hardened/EVO antes de la guarda; MQR en `_run_core`, antes de `[6G.1-R/G]`).
  - **Si falla:** se eleva `CierreNoAcreditado6G1` y el protocolo recibe `(False, err)`.
  - **Dónde queda el error:** en el informe, en `ABORT_6G1.json` y en el motivo de conservación, aunque el log ya no admita escritura.
- **D · Construcción del runner:**
  - cada WAV se registra como propio en cuanto se abre;
  - una `BaseException` posterior llama a `runner_parcial_6g1(self, registro_6g1)` y se re-eleva;
  - las llamadas pasan `registro_6g1=runners`;
  - sin `__del__`, finalizadores ni GC.
- **E · Retención de `masks/`:**
  - Hardened/EVO: el `rmtree(masks_dir)` previo a la guarda se ha eliminado; la limpieza ([PATCH 4], incondicional como antes) se hace **después de publicar**, sobre `run_dir_final/masks`, y un fallo sólo avisa.
  - MQR: no tiene ningún `rmtree`, `remove` ni `unlink`, así que `masks/` nunca se borraba. No requiere corrección.

## 3. Hallazgo F (preexistente, fuera de A–E, **no corregido**)

**Código** (idéntico en 6a93e4e):

| Motor | Ubicación | Cuándo aparece |
|---|---|---|
| Hardened | L1880–1881 | sólo con `--png` o `--keep-masks` |
| EVO | L1991–1992 | sólo con `--png` o `--keep-masks` |
| MQR | L2715–2717, en `_run_core` | siempre (escribe `masks/` siempre) |

```python
for arr in mm.values(): arr.flush()
del mm
```

**Causa:**
1. `del mm` suelta el diccionario.
2. La variable de bucle `arr` sigue referenciando el **último** memmap (`model_disagreement_map`), que queda mapeado y con escritura hasta que la función retorna.
3. El protocolo no puede cerrarlo:
   - ya no está en `mm`;
   - la guarda de refcount impide cerrar un mmap con referencias vivas.

**Efecto:**
- Todo aborto posterior a ese punto se registra con un fd y un mapeo de escritura abiertos sobre `masks/model_disagreement_map.npy`. Afecta a:
  - Hardened/EVO con máscaras;
  - en MQR, a A, B, C y E, porque sus escritores se cierran después del flush.
- El protocolo actúa **fail-closed**: `completo=False`, error documentado y sin traslado. Aun así, no se cumple «fds y mmaps cerrados al registrar», así que esos escenarios fallan.
- Antes de E, en Hardened/EVO el defecto quedaba oculto: el `rmtree` desvinculaba el archivo y el mapeo apuntaba a «(deleted)».

**Corrección propuesta (pendiente de autorización):** soltar la variable tras el bucle, por ejemplo con `arr = None` tras el bucle de flush. No toca el DSP: es la misma liberación que ya pretende `del mm`.
- Afectaría a `run_experiment` (Hardened/EVO) y `_run_core` (MQR), ya autorizados.
- Habría que repetir la batería AI.

**No la he aplicado** porque la instrucción prohíbe correcciones adicionales y modificar producción para forzar un PASS.

## 4. Pruebas

| Elemento | Detalle |
|---|---|
| Inyector | `scripts/inyeccion_auditoria_6g1/ejecutar_motor_auditoria.py` |
| Batería | `scripts/pruebas_auditoria_cierre_6g1.py` (`--base` para el diagnóstico) |
| Fixture | sintético del repositorio, sin audio real |
| Mix | se usa una **copia** en la carpeta de trabajo; E1 altera un byte de esa copia, y los fixtures no se tocan |
| Argumentos | `--mode full_processing`; `--keep-masks` sólo en E1 de Hardened/EVO; MQR escribe `masks/` siempre. Así A–D prueban su objetivo sin F en Hardened/EVO |

**Fallos inyectados**, por instancia y en memoria (ningún archivo de producción se modifica):

| Escenario | Inyección |
|---|---|
| A | primer `close()` de un escritor WAV en la finalización normal |
| B | cierre del `SoundFile` lector del Mix en la guarda |
| C | proxy del archivo de `engine_log.txt` cuyo primer `close()` falla |
| D | apertura del 2.º escritor; en D2, además, falla el cierre del 1.º |
| E | se altera un byte de la copia del Mix tras `write_reports()` |

En todos los casos, «antes» significa que el archivo sigue abierto y «después» que ya está cerrado físicamente y luego se eleva el error.

**Comprobaciones por caso (27–29):**
- código 2, nunca `EXIT_OK`, y `run_experiment` sin éxito;
- inyección realizada y protocolo ejecutado;
- `completo` y `log_cerrado` esperados;
- error en el informe y en el motivo de conservación;
- ABORT schema `/3`, motivo esperado y `resultados_validos=[]`;
- traslado sólo con cierre e integridad acreditados (D1); en el resto, el provisional se conserva con su identidad (dev/ino) y no se crea `_aborted`;
- ninguna publicación;
- ningún archivo eliminado; `masks/` conservada e invalidada (E1); WAV conservados e invalidados (A); primer escritor conocido, cerrado, invalidado y con RIFF coherente (D);
- al registrar: sin fds ni mapeos bajo la salida o sobre las entradas, escritores y lectores cerrados y memmaps liberados (`/proc/self/{fd,fdinfo,maps}` + `weakref`);
- ningún cierre después del registro;
- SHA estable tras el registro y al terminar el proceso;
- **sin GC:** `gc.disable()` antes de importar nada y `gc.callbacks` para registrar cualquier colección posterior. Resultado: 0 colecciones; las 9 de generación 0 ocurren en el arranque del intérprete, antes de `gc.disable()`.

## 5. Entregables

| Archivo | Contenido |
|---|---|
| `AUDITORIA_INTEGRAL_CIERRE_6G1.md` | este informe |
| `evidence/pruebas_auditoria_cierre_6g1.json` | detalle de cada caso, corregido y base |
| `evidence/matriz_auditoria_cierre_6g1.csv` | matriz |
| `evidence/inyecciones_auditoria_6g1/<motor>_<esc>.json` (27) | estado completo de cada inyección: eventos ordenados, fotografías `/proc`, informe de cierre y resultado del aborto |
| `evidence/ast_auditoria_integral_6g1.json` | no-regresión DSP por AST |
| `scripts/verificar_ast_auditoria_integral_6g1.py`, `scripts/pruebas_auditoria_cierre_6g1.py`, `scripts/inyeccion_auditoria_6g1/ejecutar_motor_auditoria.py` | scripts |
| `MANIFEST_AUDITORIA_INTEGRAL_6G1.json`, `SHA256SUMS_AUDITORIA_INTEGRAL_6G1.txt` | manifiesto y sumas |
| `DIFF_AUDITORIA_INTEGRAL_6G1_vs_6a93e4e.patch` | se aplica y se revierte sobre 6a93e4e |

**Evidencia histórica sin modificar:** CV (c38d00d), CR (8e773df), CR-R1 (6a93e4e) y la prueba DSP.

**No ejecutado:**
- H1, C-R1, H2, la batería CV y las baterías históricas (34/26/17/12);
- la prueba DSP;
- audio real, Android y Termux.

## 6. Decisión pendiente (Cris)

¿Autorizas la corrección de F (`arr = None` tras el bucle de flush en `run_experiment` de Hardened/EVO y en `_run_core` de MQR) y la repetición de la batería AI? Hasta entonces, la auditoría integral queda **abierta** con 9/27 casos bloqueados por F.
