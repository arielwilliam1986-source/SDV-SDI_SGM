# 6G.1 — Auditoría y corrección del ciclo de vida (hallazgos A y B de Cris)

- Rama: `arena/c7719286-sdv-sdi-sgm`. Commit base (padre obligatorio): `594a90f18c42139dcc7e753633afe33cb89cc752`.
- Alcance: el ciclo de vida de los archivos y el contrato de retorno de MQR en los 3 motores 6G.1 (Hardened, EVO, MQR) más el módulo compartido `lectura_segura_6g1.py`. Sólo se modificó `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`.
- Estado: **corrección propuesta para auditoría independiente**. 6G.1 **no** se declara cerrada ni lista para integración.

## 1. Informe de los hallazgos

### Hallazgo A — abortos incompletos (confirmado en los 3 motores en 594a90f)

| Punto | Comportamiento en 594a90f | Corrección |
|---|---|---|
| `KeyboardInterrupt` | trasladaba a `_aborted` con `_publicar_dir_6g1()` **sin** `abortar_6g1()` → sin `ABORT_6G1.json` | protocolo único: `INTERRUPCION_DEL_USUARIO`, registro antes de trasladar, código 130 |
| `except Exception` | igual: traslado sin registro | `EXCEPCION_DURANTE_EL_PROCESAMIENTO`, registro antes de trasladar, código 2 |
| Apertura del Mix antes del DSP | sólo se trataba `MixCambiado`; un `OSError` caía al except general (traslado sin registro) | `MIX_SUSTITUIDO_ANTES_DEL_DSP` / `MIX_NO_ABIERTO_ANTES_DEL_DSP`: registro, **sin traslado** |
| Guarda final de integridad | registraba el ABORT (Hardened y EVO ya cumplían; MQR se veía afectado por B) | `MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO`: registro, **sin traslado** y sin publicación |
| Publicación segura fallida | `return EXIT_PROCESSING` **sin** ABORT | `PUBLICACION_SEGURA_FALLIDA`: registro, provisional conservado en su ubicación |
| Preparación inicial (`init_tee`, `masks/`) | fuera del `try`: la excepción escapaba (código 1), sin ABORT | dentro del `try`: pasa por el protocolo único (código 2) |
| `create_run_dir` (mkdir + acreditación) | fuera del `try`: la excepción escapaba (código 1) | envuelto: código 2, sin escritura ni traslado (no hay directorio acreditado) |

### Hallazgo B — falso éxito en MQR (confirmado en 594a90f)

Ante un fallo de apertura del Mix, `_run_core()` devolvía `(EXIT_PROCESSING, None)` y `run_experiment()` asignaba esa tupla a `run_dir_final`, siguiendo por el camino de `return EXIT_OK`.

Matiz observado en la ejecución real: la línea previa, `log("Corrida COMPLETA: %s" % run_dir_final)`, eleva `TypeError` al formatear la tupla. Por eso, con la batería, el proceso terminaba con **código 1 por traceback no controlado** y sin ABORT (`evidence/pruebas_ciclo_vida_6g1.json` → `diagnostico_base.detalle["MQR/A4"].stdout_tail`). Ese `TypeError` es accidental: el camino de control llegaba a EXIT_OK, y el resultado nunca era el código de fallo controlado.

Contrato corregido:
- `_run_core()` devuelve **exclusivamente** la ruta final publicada.
- La apertura del Mix fallida, la guarda fallida y la publicación fallida se propagan como `FalloCorrida6G1`. La interrupción se propaga como `KeyboardInterrupt`.
- `run_experiment()` sólo acepta una ruta `str` distinta del provisional que exista como directorio. Cualquier otro valor es `CONTRATO_DE_RETORNO_INVALIDO` (código 2).
- `EXIT_OK` sólo se devuelve si `_run_core` terminó sin excepción y la ruta realmente publicada existe.

## 2. Protocolo único de aborto (idéntico en los 3 motores)

En `lectura_segura_6g1.py` se añadió un bloque `[6G.1-R/CV]` al final del módulo. No se cambió ninguna función existente del módulo.

- `FalloCorrida6G1(motivo, detalle, trasladar)` lleva los fallos conocidos al mismo manejador.
- `cerrar_recursos_6g1(...)` cierra descriptores de lectura sin propagar errores. No toca el disco.
- `abortar_corrida_6g1(run_dir, destino, motivo, detalle, trasladar)` sigue estos pasos:
  1. Llama **siempre primero** a `abortar_6g1()`, que respeta C-R1/E-R2/H1: no elimina nada, deja `analysis.json` intacto, invalida y conserva las salidas propias, fija `resultados_validos=[]` y usa el schema `abort-6g1/3`.
  2. Si el directorio no está acreditado, o si `ABORT_6G1.json` no se pudo escribir de forma segura (`motivos_propiedad['ABORT_6G1.json']`), **conserva el provisional en su ubicación**.
  3. Vuelve a anclar el directorio y relee `ABORT_6G1.json` con `O_NOFOLLOW` sobre el descriptor acreditado. Comprueba schema, motivo, `resultados_validos=[]` y `directorio_acreditado=True`.
  4. Sólo si el motor pidió traslado y `lstat(ruta) == fstat(descriptor)`, traslada con `publicar_dir_6g1()` (renameat2 `RENAME_NOREPLACE`, sufijo `_rNNN` si hay colisión, nunca reemplaza). Después verifica la identidad del destino.
  5. En cualquier otro caso no hay traslado. Nunca publica como éxito y nunca elimina nada.
- `resumen_aborto_6g1(res)` genera la línea de log.

Política de traslado (la misma en los 3 motores):

| Motivo | Traslado |
|---|---|
| `INTERRUPCION_DEL_USUARIO`, `EXCEPCION_DURANTE_EL_PROCESAMIENTO` (incluye la preparación inicial) | sí, sólo si el aborto quedó registrado y verificado |
| `MIX_SUSTITUIDO_ANTES_DEL_DSP`, `MIX_NO_ABIERTO_ANTES_DEL_DSP`, `MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO` | no: se registra en el provisional (contrato histórico de los abortos por integridad, H1) |
| `PUBLICACION_SEGURA_FALLIDA`, `CONTRATO_DE_RETORNO_INVALIDO` | no: el mecanismo atómico no es fiable o el estado es incierto |

Orden del manejador en los 3 motores: `cerrar_recursos_6g1` → `abortar_corrida_6g1` → `close_tee` → código (130 para la interrupción, 2 para el resto).

## 3. Archivos modificados y justificación

| Archivo | Cambio | Justificación |
|---|---|---|
| `motores/lectura_segura_6g1.py` | +bloque CV al final (5 definiciones nuevas) | un único protocolo compartido evita tres implementaciones divergentes |
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | `run_experiment` + nombres añadidos al import existente | A: los 7 puntos de la tabla del §1 |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | `run_experiment` + nombres añadidos al import existente | A: los mismos 7 puntos |
| `motores/sdv_sdi_mqr_engine.py` | `run_experiment`, `_run_core` + nombres añadidos al import existente | A, y B (contrato de retorno) |
| `scripts/inyeccion_ciclo_6g1/ejecutar_motor_inyectado.py` (nuevo) | ejecutor con inyección determinista en memoria | no modifica motores ni módulo |
| `scripts/pruebas_ciclo_vida_6g1.py` (nuevo) | batería: 11 escenarios × 3 motores | pruebas obligatorias A1–A6, más A2NA, A4b, A6b, A7 y E0 |
| `scripts/verificar_ast_ciclo_vida_6g1.py` (nuevo) | verificación AST frente a 594a90f | prueba de que el DSP no cambió |
| `evidence/pruebas_ciclo_vida_6g1.json`, `evidence/matriz_ciclo_vida_6g1.csv`, `evidence/ast_ciclo_vida_6g1.json` (nuevos) | evidencia | — |
| `CICLO_VIDA_6G1.md`, `SHA256SUMS_CICLO_VIDA_6G1.txt`, `MANIFEST_CICLO_VIDA_6G1.json`, `DIFF_CICLO_VIDA_6G1_vs_594a90f.patch` (nuevos) | documentación, integridad y diff | — |

Nombres que quedan importados pero sin uso:
- `abortar_6g1 as _abortar_6g1` en Hardened y EVO.
- `_VerifFallida_6g1` en MQR.

Se mantuvieron a propósito: la única sentencia no-def que cambia en cada motor es el import, y sólo con nombres **añadidos**.

## 4. Pruebas y resultados

Ejecución:

```
cd ETAPA_6G1_CORRECCION_LECTURA_SEGURA
python -B scripts/pruebas_ciclo_vida_6g1.py --base <motores 594a90f> --etiqueta-base 594a90f
```

- Entorno: CPython 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2.
- Fixtures: los sintéticos `full_processing` existentes, sólo lectura. Sin audio real.
- El diagnóstico `--base` corre la **misma** batería sobre los motores de 594a90f extraídos con `git show`. Sólo sirve para el diagnóstico: el veredicto lo dan los motores corregidos.

**Resultado: motores corregidos 33/33 PASS. Base 594a90f: 8/33** (`evidence/matriz_ciclo_vida_6g1.csv`; detalle por comprobación en `evidence/pruebas_ciclo_vida_6g1.json`).

Todo escenario con inyección verifica, entre otras cosas:
- código esperado, y nunca EXIT_OK en el proceso ni en el retorno real de `run_experiment()`;
- ninguna publicación como éxito;
- el destino `_aborted` preexistente sembrado no se reemplaza;
- el archivo ajeno dentro del provisional (`AJENO_CV.txt`) y fuera (`AJENO_EXTERNO.txt`) queda intacto;
- ninguna escritura fuera de lo permitido;
- identidad (dev, ino) del directorio conservada;
- archivos conservados, con SHA sin cambios en los archivos cerrados;
- `analysis.json` intacto;
- para un ABORT registrado: schema `abort-6g1/3`, motivo, `resultados_validos=[]`, `directorio_acreditado=True`, salidas parciales invalidadas y conservadas.

### Tabla de códigos de retorno por escenario (idéntica en Hardened / EVO / MQR)

| Esc. | Condición | Corregido | Ubicación final | Base 594a90f (H / E / MQR) |
|---|---|---|---|---|
| A1 | KeyboardInterrupt tras salidas parciales | **130** PASS | `_aborted_r001` (ABORT registrado) | 130/130/130 FAIL: traslado sin ABORT |
| A2 | Excepción general tras salidas parciales | **2** PASS | `_aborted_r001` (ABORT registrado) | 2/2/2 FAIL: traslado sin ABORT |
| A2NA | A2 con el provisional sustituido (no acreditable) | **2** PASS | nada se traslada ni se escribe | 2/2/2 FAIL: trasladaba el sustituto |
| A3 | Publicación segura fallida (renameat2 ENOSYS) | **2** PASS | provisional en su ubicación (ABORT) | 2/2/2 FAIL: sin ABORT |
| A4 | Apertura del Mix: `MixCambiado` | **2** PASS | provisional (ABORT) | 2 PASS / 2 PASS / **1** FAIL (B: TypeError, sin ABORT) |
| A4b | Apertura del Mix: `OSError` | **2** PASS | provisional (ABORT) | 2/2/2 FAIL: traslado sin ABORT |
| A5 | Guarda final no superada | **2** PASS | provisional (ABORT), sin publicar | 2/2/2 PASS |
| A6 | Fallo de `init_tee` tras crear el provisional | **2** PASS | `_aborted_r001` (ABORT registrado) | **1**/**1**/**1** FAIL: excepción no controlada |
| A6b | Provisional creado pero no acreditado | **2** PASS | provisional intacto, sin escrituras | **1**/**1**/**1** FAIL |
| A7 | A2 con escritura de `ABORT_6G1.json` fallida (EIO) | **2** PASS | provisional en su ubicación, sin traslado | 2/2/2 FAIL: traslado sin ABORT |
| E0 | Corrida feliz | **0** PASS | publicación única; PCM = referencia | 0/0/0 PASS |

Correspondencia con las pruebas obligatorias: A1→A1, A2→A2, A3→A3, A4→A4+A4b, A5→A5, A6→A6+A6b. A7 cubre el requisito «si el registro de aborto no puede escribirse de forma segura, conservar el provisional en su ubicación». A2NA cubre «nunca trasladar una ruta no acreditada».

E0 reproduce exactamente los hashes PCM registrados en `evidence/no_regresion_dsp_6g1.json` (`pcm_6g1`), con geometría 88200×2 a 44100 Hz:

| Motor | SDI | SDV |
|---|---|---|
| Hardened/EVO | `368d3ecb…74f85` | `a347838d…20bc0` |
| MQR | `565bc8b6…754d3` | `8fb3578a…af8` |

## 5. Confirmación de que el DSP no cambió (verificación estática)

`python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_ciclo_vida_6g1.py` → **VEREDICTO: OK** (`evidence/ast_ciclo_vida_6g1.json`).

| Motor | Defs cambiadas | Añadidas / eliminadas | Defs sin cambio | Otras sentencias | Literales | Llamadas DSP |
|---|---|---|---|---|---|---|
| Hardened | `run_experiment` | 0 / 0 | 64 | 1 (import) | iguales | iguales |
| EVO | `run_experiment` | 0 / 0 | 67 | 1 (import) | iguales | iguales |
| MQR | `run_experiment`, `_run_core` | 0 / 0 | 86 | 1 (import) | iguales | iguales |

`analyze_guide_scale`, `CandidateRunner`, la STFT/ISTFT, las máscaras, el consenso y la reconstrucción tienen un AST idéntico al de 594a90f. Los extractores `_numeros`/`_llamadas_dsp` son los de `no_regresion_dsp_6g1.py`: sólo se importan, y ese script no se modificó ni se ejecutó. En las funciones cambiadas, los únicos movimientos de código DSP-adyacente son líneas de log con parámetros que pasan a estar dentro del `try`, es decir, cambios de sangría: literales y llamadas son iguales.

## 6. Archivos que no se tocaron

- Motores 6G originales (`ETAPA_6G_SOPORTE_FLAC_MIX`): no se modificaron. Esa carpeta no existe en el árbol de esta rama.
- `main`: no se tocó.
- Validadores WAV/FLAC (`wav_integridad_6f.py`, `audio_integridad_6g.py`, `atribucion_6f.py`): sin cambios.
- Fixtures, Mix y stems: sin cambios.
- Evidencia de la prueba DSP (`no_regresion_dsp_6g1.py`, `evidence/no_regresion_dsp_6g1.{json,csv}`, `NO_REGRESION_DSP_6G1.md`, `SHA256SUMS_NOREG_DSP_FINAL.txt`) y `ADJUDICACION_CRIS_NO_REGRESION_DSP_6G1.md`: sin cambios.
- Matriz global, consolidación, `SHA256SUMS.txt` y `MANIFEST_6G1.json`: sin cambios. Siguen desactualizados y fuera del alcance.
- `git diff 594a90f --stat` sólo muestra los 4 archivos de `motores/` indicados, más archivos nuevos.

## 7. Registro honesto de la ejecución (desviaciones)

1. **Se ejecutaron baterías que estaba indicado no repetir.** Para comprobar regresiones se ejecutaron H1, C-R1, H1-R2, H1-R2-R1, H1-R2-R2, H2 y H2-R sobre una **copia** de la carpeta en `/tmp`. La restricción indicaba no repetir H1, C-R1 ni H2.
   - Su evidencia en el repositorio no se modificó: nada se escribió en `evidence/` del repo, ni con esos resultados ni con ninguna salida.
   - No se repitieron las baterías 34/26/17/12.
   - Esto queda declarado como desviación del procedimiento.
2. **Ajuste de diseño originado por esa ejecución.** La primera versión de la corrección trasladaba a `_aborted*` también los abortos por integridad del Mix (A4, A4b, A5). H1-e2e (3 motores) quedó NOT_EXECUTED porque esperaba el ABORT en el `_partial`, que es el contrato histórico auditado.
   - Se cambió a `trasladar=False` en esos tres puntos, en los 3 motores, y se ajustaron las expectativas de A4/A4b/A5 en la batería CV. Eso explica que la base 594a90f pase A4/A5 en Hardened/EVO.
   - Tras el ajuste, todas esas baterías dieron PASS (H1 10/10, C-R1 13/13, H1-R2 4/4, H1-R2-R1 2/2, H1-R2-R2 1/1, H2 10/10, H2-R 15/15), y la batería CV 33/33.
3. **Iteraciones del arnés CV**, sin efecto sobre producción:
   - inyección de A4 limitada a después de crear el provisional;
   - comprobación sólo de existencia para los WAV todavía abiertos en A4/A6, cuya cabecera se finaliza al cerrar;
   - helpers seguros con `lstat`.
4. **No revisado en profundidad (sin cambio respecto de 594a90f).** En MQR, el manejador cierra el `MixHandle` (`ctx["_mix_handle_6g1"]`). Los escritores de `CandidateRunner` se liberan igual que antes: al recolectarse. A1, A4 y A6 confirman que las salidas se conservan.

## 8. Integridad

- `SHA256SUMS_CICLO_VIDA_6G1.txt`: SHA-256 de cada archivo modificado o nuevo. Verificar desde la raíz del repo con `sha256sum -c`.
- `MANIFEST_CICLO_VIDA_6G1.json`: commit base, SHA pre y post por archivo, y resultados.
- `DIFF_CICLO_VIDA_6G1_vs_594a90f.patch`: diff completo y reversible (`git apply -R`) de todo lo anterior frente a 594a90f, excepto el propio patch y los archivos de integridad que lo referencian.

Pre-fix (594a90f) → post-fix:

| Archivo | SHA-256 en 594a90f | SHA-256 post-fix |
|---|---|---|
| Hardened | `8c1fca989886de01d4cc8a849426a68851f0806e7dbdc1c62b36966372a1f571` | `3977473dd4eab50c9bf365cbc913691f0c977d0c95f29e3b14764ebc6d4b5c8c` |
| EVO | `7b99ab805a9134fef2bc813024d38d107b3c31cb452282418e407e7779de19d8` | `cd5aa200903b98065de9a722613581c66404d7962d9c6827f3689818dc80858d` |
| MQR | `00734713ef729a607e173c518d49f844295af08a58c9ad4c2f6dbff45729372d` | `75f41cdaa811ad61822292ea3bbbc1e3c279389190a350f7d9b9e8dd989f717a` |
| `lectura_segura_6g1.py` | `a4c3b5d1a7659731bb2af2f5af4b28b402f2323d707d870a481c82c5f5741759` | `e66ae40f39042da5c7b2fb5e5e129064224b856bc73e830175001744a0091c09` |

Pendiente de auditoría independiente (Cris). La decisión final corresponde al responsable. 6G.1 no se declara cerrada.
