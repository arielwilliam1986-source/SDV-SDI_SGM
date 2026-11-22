# 6G.1 — Rectificación CR-R1: fallo de cierre de lectores y del log

- Rama: `arena/c7719286-sdv-sdi-sgm`.
- Commit padre obligatorio: `8e773df9506f3d6600fa5fe675ef8fbddfd882ad`.
- Alcance: sólo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`.
- Estado: **rectificación propuesta para revisión de Cris**. 6G.1 **no** se declara cerrada ni lista para integración.

## 1. Hallazgo (confirmado por Cris y reproducido)

Los dos huecos están en `motores/lectura_segura_6g1.py` de 8e773df:

1. **Lectores.** `cerrar_recursos_corrida_6g1()` cerraba los lectores con `paso('lector', nombre, 'close', ok, err, critico=False)`.
   - Un lector que no se cerraba dejaba `inf['completo']=True`.
   - Los lectores (Mix y guías) apuntan a las **entradas**, fuera del provisional, así que la comprobación en `/proc` tampoco los detectaba.
   - Resultado: `abortar_corrida_6g1()` **trasladaba**.
2. **Log.** En `preparar_aborto_6g1()`, un fallo de `cerrar_log()` sólo se anotaba en `errores`, sin `completo=False`.
   - Si el archivo llegaba a cerrarse (p. ej. el error ocurre al vaciar), no quedaba ningún descriptor y el traslado **se permitía**.

Reproducción en 8e773df, con las pruebas nuevas:

| Prueba | Condición | 8e773df |
|---|---|---|
| Protocolo P1 | fallo de cierre de un lector | `completo=True`, **trasladado** a `_aborted_r001` |
| Protocolo P2 | fallo de `cerrar_log()` tras cerrar el archivo | `completo=True`, **trasladado** |
| Motores R5 (Hardened, EVO, MQR) | fallo de cierre del lector del Mix | `completo=True`, **trasladado** a `_aborted_r001` en los 3 |

## 2. Corrección (sólo `lectura_segura_6g1.py`)

| Def | Cambio |
|---|---|
| `cerrar_recursos_corrida_6g1` | El paso de lectores pasa a ser **crítico**: `paso('lector', nombre, 'close', ok, err)`. Un lector que eleva al cerrar, o cuyo estado de cierre no es verificable, deja `completo=False`. El docstring describe `completo` para escritores, memmaps y lectores. |
| `preparar_aborto_6g1` | Si `cerrar_log()` falla: `completo=False`, `log_cerrado=False` y el error queda en `errores`. Como el log ya no está disponible, el error se propaga al motivo de conservación del resultado del aborto. Con éxito: `log_cerrado=True`. El docstring describe `completo` con **todos** los recursos exigidos (ver abajo). |
| Comentario de cabecera del bloque `[6G.1-R/CR]` | Cualquier fallo o cierre no verificado de escritor, memmap, lector o log marca el cierre como incompleto. |

Recursos que exige `completo=True` según el docstring de `preparar_aborto_6g1`:
- (a) cada escritor, memmap y lector cerrado y verificado;
- (b) `cerrar_log()` sin fallo;
- (c) ningún descriptor de escritura ni mapeo bajo el provisional, ni antes ni después de cerrar el log.

Sin cambios:
- `abortar_corrida_6g1`. Ya era fail-closed con `cierre.completo=False`: registra `ABORT_6G1.json` (`/3`, `resultados_validos=[]`) y conserva el provisional en su ubicación, sin traslado, sin publicación y sin eliminación.
- El tratamiento de memmaps: nunca se cierra un mmap con referencias activas. R3 sigue pasando.
- Los **3 motores**, byte a byte idénticos a 8e773df, y por tanto todo el DSP.

AST de `lectura_segura_6g1.py` frente a 8e773df:
- defs cambiadas: `cerrar_recursos_corrida_6g1` y `preparar_aborto_6g1`;
- 0 defs añadidas y 0 eliminadas;
- las demás sentencias de nivel de módulo son iguales.

Documentación: `CIERRE_RECURSOS_6G1.md` (8e773df) **no se reescribió**, por ser el informe histórico de ese commit. Su frase del §2.1 «Lectores … no son críticos para el traslado» y la definición de `completo` («todo escritor y todo memmap») **quedan sustituidas** por este documento y por los docstrings corregidos.

## 3. Pruebas

### 3.1 Prueba focalizada del protocolo

Script: `scripts/pruebas_protocolo_cierre_cr_r1_6g1.py`, sin motores ni DSP.

Cada caso parte de un provisional creado con `crear_y_acreditar_dir_6g1()` que contiene:
- un WAV parcial propio, registrado;
- un archivo ajeno;
- `engine_log.txt` abierto;
- un destino `<final>_aborted` **preexistente**.

Después se llama a `preparar_aborto_6g1()` → `abortar_corrida_6g1(trasladar=True)`.

| Caso | Inyección | Esperado | Corregido | 8e773df |
|---|---|---|---|---|
| P0 | ninguna (control) | `completo=True`, traslado sin reemplazo a `_aborted_r001` | PASS 13/13 | PASS 13/13 |
| P1 | `close()` del lector eleva OSError y el lector queda abierto | error en `engine_log.txt`, `completo=False`, sin traslado | PASS 16/16 | **FAIL** 10/16: `completo=True`, trasladado |
| P2 | `cerrar_log()` cierra el archivo y después eleva OSError | `completo=False`, `log_cerrado=False`, sin traslado; error en el informe y en el motivo de conservación | PASS 17/17 | **FAIL** 10/17: `completo=True`, trasladado |
| P3 | `cerrar_log()` eleva OSError con el descriptor abierto | `completo=False`, sin traslado | PASS 17/17 | FAIL 16/17, sólo por `log_cerrado` (campo nuevo); el traslado ya quedaba bloqueado por la comprobación en `/proc` |

Resultado: **corregido 4/4 PASS · 8e773df 1/4**.

Además de lo indicado en la tabla, cada caso comprueba:
- `ABORT_6G1.json` con schema `/3`, motivo correcto y `resultados_validos=[]`;
- WAV parcial invalidado y conservado; ajeno conservado;
- destino preexistente intacto;
- ningún `_aborted_r*` salvo en P0;
- sin publicación como éxito;
- ningún archivo eliminado ni modificado, salvo el log.

### 3.2 Motores: escenario nuevo R5 y no regresión de R1–R4 y E0

Batería: `scripts/pruebas_cierre_recursos_6g1.py`. Inyector: `scripts/inyeccion_cierre_6g1/ejecutar_motor_cierre.py`.

**R5** parte de R2: `RuntimeError` a mitad del procesamiento, con 4 escritores abiertos (8 en MQR), 6 memmaps (10 en MQR) y bloques ya escritos. Además, el **primer** `MixHandle.close()` posterior a la inyección eleva `OSError(5)` sin cerrar nada. El lector del Mix queda abierto, en sólo lectura y fuera del provisional.

Las comprobaciones de R5 son las de R2 con estos ajustes:
- se toleran **sólo** los descriptores de sólo lectura del lector fallido;
- `provisional_conservado_sin_traslado`;
- `fallo_de_cierre_de_lector_inyectado` y `unico_lector_abierto_es_el_fallido`;
- `log_documenta_error_de_cierre_del_lector`: `completo=False`, `ERROR de cierre` y el mensaje inyectado con la ruta del lector;
- `resultado_del_aborto_traslado_bloqueado`: `trasladado=False` y `cierre de recursos incompleto` en la línea del resultado del aborto.

Para R1–R5 se añade `ningun_archivo_eliminado`: el inventario del momento de la inyección queda contenido en el final.

| Motor | R1 | R2 | R3 | R4 | **R5** | E0 |
|---|---|---|---|---|---|---|
| Hardened | 130 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | **2 PASS 37/37** | 0 PASS 9/9 |
| EVO | 130 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | **2 PASS 37/37** | 0 PASS 9/9 |
| MQR | 130 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | 2 PASS 35/35 | **2 PASS 37/37** | 0 PASS 9/9 |

Resultado: **corregido 18/18 PASS · 8e773df 15/18**. Los 3 FAIL de la base son R5: traslado a `_aborted_r001` y log con `completo=True`.

Secuencia de R5 en el motor corregido, por ejemplo Hardened:

```
7 inyeccion → 8–11 escritor_cerrado → 12 lector_cierre_fallido (mix.wav) → 13–14 lector_cerrado
→ 15 abortar_6g1_entrada → 16 abortar_6g1_salida → 17 fin_main     (sin traslado)
```

En MQR: 8 inyeccion → 9–10 guías (`finally` de `_run_core`) → 11–18 escritores → 19 `lector_cierre_fallido` → 20/21 abortar → 22 fin, sin traslado.

`engine_log.txt` (Hardened R5):

```
[6G.1-R/CR] cierre de recursos previo al aborto: escritores=4 memmaps=6 lectores=3 completo=False errores=1
[6G.1-R/CR] ERROR de cierre (documentado; el aborto continúa sin traslado): lector …/fixtures/mix.wav (close): OSError: [Errno 5] inyeccion CR R5: fallo de E/S al cerrar el lector del Mix
[6G.1-R/CR] se cierra engine_log.txt; a continuación se registra el aborto
```

Resultado del aborto: `abort_registrado=True trasladado=False … conservacion=cierre de recursos incompleto: lector …/fixtures/mix.wav (close): OSError …: provisional conservado en su ubicación`.

### 3.3 Qué no se ejecutó

- La batería CV, H1, C-R1, H2 ni las baterías históricas (34/26/17/12).
- La prueba DSP.
- Audio real o Android/Termux.

La batería CR (R1–R4 y E0) se re-ejecutó porque la instrucción pide confirmar su no regresión.

## 4. Evidencia e integridad

- `evidence/pruebas_protocolo_cierre_cr_r1_6g1.json` y `evidence/matriz_protocolo_cierre_cr_r1_6g1.csv`.
- `evidence/pruebas_rectificacion_cr_r1_6g1.json` (schema `pruebas-cierre-recursos-6g1/2`) y `evidence/matriz_rectificacion_cr_r1_6g1.csv`. Incluyen el diagnóstico sobre 8e773df.
- La evidencia de 8e773df (`pruebas_cierre_recursos_6g1.json`, `matriz_cierre_recursos_6g1.csv`, `ast_cierre_recursos_6g1.json`) **no se sobrescribió**. Las opciones nuevas `--json` y `--csv` de la batería mantienen esas rutas como valor por defecto.
- `MANIFEST_RECTIFICACION_CR_R1_6G1.json`, `SHA256SUMS_RECTIFICACION_CR_R1_6G1.txt` y `DIFF_RECTIFICACION_CR_R1_6G1_vs_8e773df.patch` (reversible con `git apply -R`).

| Archivo | SHA-256 en 8e773df | SHA-256 actual |
|---|---|---|
| `motores/lectura_segura_6g1.py` | `c1b73d4cb26f8ebc17aa873bbca694ca0cb169ad2e40988833185a5077c00407` | `833077a57c091f730c2e315460e9c11d768f0810e36b32f896b4ffdee85c2ff8` |
| Hardened | `e3a0574fa6f4a35dd59968093df8a338431423d47f55f30e3114c80c272c5fe8` | sin cambios |
| EVO | `438bb7a8eb834dee0bba060c9fe3d1d5e350909cb5d51c6e0c90f40b39b2690c` | sin cambios |
| MQR | `41b075dfdac23b4a4ecbb543051cfcfddabc36dfa4e496d90e7cb3b27efdbaf7` | sin cambios |

## 5. Limitaciones

- La detección de descriptores y mapeos usa `/proc` y sólo funciona en Linux. Sin ella, la protección depende de `completo`, que ahora cubre lectores y log.
- R5 inyecta un único fallo transitorio en `MixHandle.close`. Un lector de guías que falle sigue el mismo camino crítico (P1 lo cubre a nivel de protocolo con un `SoundFile`).
- `--chunk-frames 16` es sólo un argumento de línea de órdenes, como en 8e773df.

Pendiente de revisión de Cris. 6G.1 no se declara cerrada ni hay autorización de integración.
