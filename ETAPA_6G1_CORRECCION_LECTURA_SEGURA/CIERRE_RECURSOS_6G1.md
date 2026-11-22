# 6G.1 — Cierre determinista de recursos en abortos (instrucción de Cris sobre c38d00d)

- Rama: `arena/c7719286-sdv-sdi-sgm`.
- Commit padre obligatorio: `c38d00d505c6b359585fe7f474a21fd3ab272b4b`.
- Alcance: el cierre de los recursos de escritura y lectura antes del protocolo de aborto, en Hardened, EVO y MQR. Sólo se modificó `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`.
- Estado: **corrección propuesta para revisión de Cris**. 6G.1 **no** se declara cerrada ni lista para integración.

## 1. Problema (confirmado en c38d00d)

1. **Hardened y EVO** cierran los `CandidateRunner` y vacían los memmaps sólo en el camino normal. Sus manejadores de excepción cerraban únicamente `hmix` y `handles` antes de `abortar_corrida_6g1()`.
2. **MQR** cerraba los lectores de guías en un `finally`, pero los `CandidateRunner` y los memmaps sólo en el camino normal. Además, esos objetos son locales de `_run_core` y el manejador de `run_experiment` no tenía acceso a ellos.
3. **Batería CV.** A1 y A2 inyectaban después de `write_reports()`, con los escritores ya cerrados, así que no cubrían una interrupción con escritura WAV real en curso.

Efecto medido en c38d00d con la nueva batería, en los 3 motores:
- En la entrada de `abortar_6g1()` estaban abiertos **0/4 escritores** (Hardened, EVO) y **0/8** (MQR), y **0/6** y **0/10** memmaps.
- Al finalizar el proceso, las cabeceras RIFF seguían **sin finalizar**: chunk `data` de tamaño 0, con audio detrás. Los WAV parciales quedan corruptos.
- `engine_log.txt` se seguía escribiendo después de registrar el aborto.

## 2. Solución

### 2.1 Módulo `lectura_segura_6g1.py`: bloque nuevo `[6G.1-R/CR]` al final

| Función | Qué hace |
|---|---|
| `cerrar_recursos_corrida_6g1(runners, memmaps, lectores)` | Cierra en orden y de forma idempotente (ver detalle abajo). Nunca propaga errores. Devuelve un informe con los pasos, los errores y `completo`. |
| `preparar_aborto_6g1(run_dir, log, cerrar_log, runners, memmaps, lectores)` | Paso previo **obligatorio** al aborto en los 3 motores (ver detalle abajo). Nunca propaga errores. |
| `descriptores_bajo_dir_6g1`, `mapeos_bajo_dir_6g1`, `escritura_abierta_bajo_dir_6g1` | Comprobación a nivel de sistema operativo (`/proc/self/fd`, flags de `fdinfo`, `/proc/self/maps`). |
| `_cerrado_6g1`, `_cerrar_idempotente_6g1`, `_bajo_dir_6g1`, `resumen_cierre_6g1` | Auxiliares. |

Orden de cierre en `cerrar_recursos_corrida_6g1`:
1. **Escritores WAV** de todos los `CandidateRunner` ya construidos (`writer_sdv` y `writer_sdi`). `SoundFile.close()` finaliza la cabecera RIFF. El estado `closed` se verifica después de cada cierre.
2. **Memmaps.** Primero `flush()`. Después se cierra **explícitamente** el `mmap` subyacente, pero sólo si el cerrador es el **único titular** del array (`sys.getrefcount`). La entrada se retira del diccionario del motor y el contenido lógico no se toca.
   - Motivo del requisito de titularidad: `mmap.close()` **no falla** aunque existan arrays numpy que apunten a la región (verificado con numpy 1.26.4). Cerrar con referencias vivas dejaría memoria inválida en uso, con riesgo de fallo de segmentación.
   - Si hay referencias activas, no se cierra. El error queda documentado y `completo=False`.
3. **Lectores** (`MixHandle` y `SoundFile` de guías). No son críticos para el traslado porque no apuntan al provisional, pero sus errores también se documentan.

Pasos de `preparar_aborto_6g1`:
1. Llama a `cerrar_recursos_corrida_6g1`.
2. Comprueba que no queda ningún descriptor de escritura ni mapeo bajo el provisional, salvo el propio log.
3. Escribe el resumen y **cada error** en `engine_log.txt`.
4. **Cierra el log** (`close_tee`).
5. Vuelve a comprobar descriptores y mapeos.
6. Devuelve el informe, que se pasa como `cierre=` a `abortar_corrida_6g1()`.

No se usa `__del__`, la recolección ni la liberación implícita: cada recurso se cierra con una llamada explícita y su estado se verifica.

`abortar_corrida_6g1(..., cierre=None)` **(modificada)**:
- Comprueba por su cuenta los descriptores de escritura y mapeos bajo el provisional.
- Si `cierre.completo` es falso o queda algo abierto, el aborto **se registra igualmente** (ABORT `/3` y C-R1), pero **nunca se traslada**: un descriptor vivo seguiría escribiendo en la ruta trasladada.
- Nunca publica como éxito ni elimina nada.

Además se añadió `import sys` al módulo.

### 2.2 Motores

| Motor | Def | Cambio |
|---|---|---|
| Hardened | `run_experiment` | Los 3 manejadores (`KeyboardInterrupt`, `FalloCorrida6G1`, `Exception`) llaman a `_preparar_aborto_6g1(run_dir, log, close_tee, runners=locals().get("runners"), memmaps=locals().get("mm"), lectores=(hmix, handles))` y pasan `cierre=` al aborto. El `traceback.print_exc()` del manejador general pasa a ir **antes** del cierre del log, para que quede en `engine_log.txt`. Import: se añade `preparar_aborto_6g1`. |
| EVO | `run_experiment` | Idéntico a Hardened. |
| MQR | `_run_core` | Registra en `ctx["_recursos_6g1"]` los mismos objetos que llena en sitio: `memmaps` (`mm`), `runners` y `lectores` (`handles`). En el camino normal retira `memmaps` justo tras su `del mm`, de modo que la vida útil no cambia. |
| MQR | `run_experiment` | Los 3 manejadores llaman a `_preparar_aborto_6g1` con esos recursos y con `ctx["_mix_handle_6g1"]`, y pasan `cierre=`. Import: se añade `preparar_aborto_6g1`. |

Orden resultante en los 3 motores:

**cierre de escritores → flush y cierre de memmaps → cierre de lectores → registro en el log → cierre del log → verificación en el sistema operativo → `abortar_6g1()` (registro) → traslado eventual con `publicar_dir_6g1` (NOREPLACE)**

El nombre `_cerrar_recursos_6g1` queda importado pero ya no se usa en los motores. Se mantuvo para que la única sentencia no-def cambiada en cada motor siga siendo el import, y sólo con un nombre añadido.

## 3. Pruebas: `scripts/pruebas_cierre_recursos_6g1.py`

Inyector: `scripts/inyeccion_cierre_6g1/ejecutar_motor_cierre.py`. Ambos son nuevos; la batería CV de c38d00d y su evidencia no se tocaron ni se re-ejecutaron.

**Instrumentación**, sólo en memoria (no se modifica ningún motor ni módulo):
- Subclase de `soundfile.SoundFile`: registra cada instancia, cuenta los frames escritos y anota cada cierre efectivo como evento ordenado. Un cierre desde `__del__` posterior al registro también quedaría anotado.
- `np.lib.format.open_memmap`: referencias débiles al array y al `mmap`. El arnés no prolonga su vida.
- `abortar_6g1`: eventos de entrada y salida, con una fotografía completa en cada uno (ver más abajo).
- `publicar_dir_6g1`: eventos de traslado.

La fotografía incluye:
- SHA-256 de todos los archivos;
- descriptores y mapeos bajo la salida y sobre las entradas;
- estado de escritores, lectores y memmaps.

**Inyección R1/R2.** Dentro de `OlaStream.push`, inmediatamente después de un push con escritor cuyo flujo **ya había escrito un bloque antes**. En ese instante se cumple:
- hay varios `CandidateRunner` con escritores abiertos (`--write-all-candidates`: 4 escritores en Hardened y EVO, 8 en MQR);
- el flujo que dispara lleva 2 bloques escritos (30720 frames) y su gemelo SDI 1 bloque;
- los memmaps están vivos (`--keep-masks` en Hardened y EVO: 6; MQR: 10);
- los WAV parciales existen con datos.

Con `--chunk-frames 16`, el fixture sintético de 89 tramas da 6 bloques y el fallo cae a mitad del procesamiento. Son argumentos de línea de órdenes, no cambios de código. La corrida aborta y no se evalúa ningún audio. E0 usa los argumentos por defecto.

| Esc. | Inyección | Esperado |
|---|---|---|
| **R1** (obligatoria) | `KeyboardInterrupt` durante el procesamiento con escritores abiertos | 130; `INTERRUPCION_DEL_USUARIO`; traslado a `_aborted_r001` |
| **R2** (obligatoria) | `RuntimeError` durante el procesamiento con escritores abiertos | 2; `EXCEPCION_DURANTE_EL_PROCESAMIENTO`; traslado a `_aborted_r001` |
| R3 (complementaria) | R2, con el arnés reteniendo una vista viva de un memmap (no cerrable de forma segura) | 2; error documentado en `engine_log.txt`; ABORT registrado; **sin traslado** |
| R4 (complementaria) | Apertura del Mix fallida tras construir los `CandidateRunner` (escritores y memmaps abiertos, 0 frames) | 2; `MIX_NO_ABIERTO_ANTES_DEL_DSP`; sin traslado. Ejercita el manejador de `FalloCorrida6G1` |
| E0 (complementaria) | Sin inyección, argumentos por defecto | 0; publicación única sin ABORT; PCM = referencia; sin descriptores ni mapeos al terminar `main()` |

**Comprobaciones por caso** (34 en R1–R4 y 9 en E0):
- código de salida y retorno real de `run_experiment()`: nunca `EXIT_OK`;
- condiciones de la inyección;
- en la **entrada** de `abortar_6g1`:
  - todos los escritores cerrados;
  - lectores cerrados;
  - memmaps con el `mmap` cerrado y sin mapeo ni descriptor en el sistema operativo;
  - ningún descriptor ni mapeo bajo la salida ni sobre las entradas;
- **orden temporal**: inyección < cada cierre de escritor < entrada al registro < salida del registro < traslado, y ningún cierre después del registro;
- ABORT `/3`, motivo, `resultados_validos=[]`, `directorio_acreditado=True`;
- salidas parciales (WAV y `.npy`) invalidadas y conservadas;
- **cabeceras RIFF finalizadas**: `riff_size = tamaño − 8`, el chunk `data` termina en EOF y `data_size = frames escritos × block_align`;
- **contenido lógico de cada memmap** igual al del instante de la inyección;
- `analysis.json` intacto (no existía en la inyección y el aborto no lo crea);
- archivo ajeno conservado, destino preexistente `_aborted` no reemplazado, nada escrito fuera e identidad del directorio conservada;
- **SHA-256 estable** entre la entrada al registro, su salida (salvo el `ABORT_6G1.json` nuevo), el final de `main()` y **después de terminar el proceso**, es decir, tras los finalizadores del intérprete;
- ningún descriptor de escritura vivo al terminar `main()`;
- `engine_log.txt` documenta el cierre (`completo=True`, o en R3 `ERROR de cierre … referencias activas`).

### 3.1 Resultados

**Motores corregidos: 15/15 PASS. Diagnóstico sobre c38d00d (misma batería): 3/15**, sólo los E0 (`evidence/matriz_cierre_recursos_6g1.csv` y `evidence/pruebas_cierre_recursos_6g1.json`).

Leyenda de la secuencia de eventos: I = inyección, W = escritor cerrado, L = lector cerrado, A> / A< = entrada / salida de `abortar_6g1`, T> / T< = entrada / salida del traslado, F = fin de `main()`.

| Motor | Esc. | Código | Comprob. | Escritores cerrados al registrar | Memmaps cerrados al registrar | Ubicación final | Secuencia de eventos | c38d00d |
|---|---|---|---|---|---|---|---|---|
| Hardened | R1 | 130 | 34/34 | 4/4 | 6/6 | `_aborted_r001` | I7 W8–W11 L12–L14 A>15 A<16 T>17 T<18 F19 | FAIL (0/4, 0/6) |
| Hardened | R2 | 2 | 34/34 | 4/4 | 6/6 | `_aborted_r001` | igual que R1 | FAIL (0/4, 0/6) |
| Hardened | R3 | 2 | 34/34 | 4/4 | 5/6 (retenido documentado) | `_partial` (sin traslado) | I7 W8–W11 L12–L14 A>15 A<16 F17 | FAIL |
| Hardened | R4 | 2 | 34/34 | 4/4 | 6/6 | `_partial` | I7 W8–W11 A>12 A<13 F14 | FAIL (0/4, 0/6) |
| Hardened | E0 | 0 | 9/9 | — | — | publicado, PCM = ref. | — | PASS |
| EVO | R1 | 130 | 34/34 | 4/4 | 6/6 | `_aborted_r001` | I7 W8–W11 L12–L14 A>15 A<16 T>17 T<18 F19 | FAIL (0/4, 0/6) |
| EVO | R2 | 2 | 34/34 | 4/4 | 6/6 | `_aborted_r001` | igual que R1 | FAIL (0/4, 0/6) |
| EVO | R3 | 2 | 34/34 | 4/4 | 5/6 (retenido documentado) | `_partial` | I7 W8–W11 L12–L14 A>15 A<16 F17 | FAIL |
| EVO | R4 | 2 | 34/34 | 4/4 | 6/6 | `_partial` | I7 W8–W11 A>12 A<13 F14 | FAIL (0/4, 0/6) |
| EVO | E0 | 0 | 9/9 | — | — | publicado, PCM = ref. | — | PASS |
| MQR | R1 | 130 | 34/34 | 8/8 | 10/10 | `_aborted_r001` | I8 L9–L10 W11–W18 L19 A>20 A<21 T>22 T<23 F24 | FAIL (0/8, 0/10) |
| MQR | R2 | 2 | 34/34 | 8/8 | 10/10 | `_aborted_r001` | igual que R1 | FAIL (0/8, 0/10) |
| MQR | R3 | 2 | 34/34 | 8/8 | 9/10 (retenido documentado) | `_partial` | I8 L9–L10 W11–W18 L19 A>20 A<21 F22 | FAIL |
| MQR | R4 | 2 | 34/34 | 8/8 | 10/10 | `_partial` | I8 W9–W16 A>17 A<18 F19 | FAIL (0/8, 0/10) |
| MQR | E0 | 0 | 9/9 | — | — | publicado, PCM = ref. | — | PASS |

En MQR, L9–L10 son el `finally` preexistente de `_run_core`, que cierra los lectores de guías antes de llegar al manejador.

En c38d00d, los WAV parciales de R1–R4 quedan con chunk `data` de tamaño 0 incluso después de terminar el proceso, y `engine_log.txt` cambia después del registro del aborto.

Cabeceras en los motores corregidos, por ejemplo Hardened R1:

| Archivo | data_size (bytes) | Frames escritos |
|---|---|---|
| `candidates/individual_P01/mix SDV.wav` | 245760 | 30720 |
| `mix SDV.wav` | 114688 | 14336 |

En ambos casos la cabecera es coherente con el tamaño del archivo.

### 3.2 Evidencia del orden de cierre y aborto

En `evidence/pruebas_cierre_recursos_6g1.json`, para cada caso:
- `secuencia`: eventos numerados desde la inyección;
- `entrada_abortar`: estado de escritores, memmaps, lectores, descriptores y mapeos en el instante de entrar a `abortar_6g1`;
- `comprobaciones.orden_cierre_registro_traslado`.

`engine_log.txt` de cada corrida abortada contiene `[6G.1-R/CR] cierre de recursos previo al aborto: escritores=N memmaps=M lectores=K completo=…`, seguido de `se cierra engine_log.txt; a continuación se registra el aborto`. En R3 aparecen además las líneas `ERROR de cierre … referencias activas al memmap … sigue mapeado`.

### 3.3 Registro honesto de la ejecución

- **Primer intento: 14/15.** MQR E0 marcaba 10 descriptores RW sobre las máscaras al terminar `main()`. La causa era el **propio arnés**: guardaba una referencia fuerte a cada objeto `mmap` y prolongaba el mapeo.
  - Se corrigió el arnés: referencias débiles y verificación del estado en el sistema operativo.
  - No se tocó el código de producción por ese motivo.
  - Ejecución final: 15/15.
- **Hallazgo técnico**, que motivó el requisito de titularidad del §2.1: `mmap.close()` no lanza `BufferError` aunque haya arrays numpy vivos sobre la región, así que un cierre ingenuo sería inseguro.
- **No se re-ejecutó** la batería CV de c38d00d (A1–A7), ni H1, C-R1, H2 ni las baterías históricas. Los tres manejadores modificados quedan ejercitados por R1 (`KeyboardInterrupt`), R2/R3 (`Exception`) y R4 (`FalloCorrida6G1`). El camino normal queda ejercitado por E0, con el PCM idéntico al registrado.

## 4. DSP intacto (verificación AST)

`python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_cierre_recursos_6g1.py` → **VEREDICTO: OK** (`evidence/ast_cierre_recursos_6g1.json`).

| Motor | Base | Defs cambiadas | Añadidas / eliminadas | Otras sentencias | Literales / llamadas DSP | Defs DSP idénticas |
|---|---|---|---|---|---|---|
| Hardened | c38d00d | `run_experiment` | 0 / 0 | 1 (import) | iguales / iguales | 13/13 |
| EVO | c38d00d | `run_experiment` | 0 / 0 | 1 (import) | iguales / iguales | 13/13 |
| MQR | c38d00d | `_run_core`, `run_experiment` | 0 / 0 | 1 (import) | iguales / iguales | 12/12 |
| los 3 | 594a90f (acumulado) | las mismas | 0 / 0 | 1 (import) | iguales / iguales | 13 / 13 / 12 |

Las defs DSP verificadas incluyen `analyze_guide_scale`, `CandidateRunner`, `OlaStream`, `stft_span_frames`, `compute_vocal_mask`, `consensus_from_masks`, `confidence_and_disagreement`, `apply_sfumato_smoothing`, `read_span` y `post_wav_identity`.

Cambios en `lectura_segura_6g1.py` frente a c38d00d (el módulo no contiene DSP):
- 9 defs añadidas, todas del bloque CR;
- `abortar_corrida_6g1` cambiada (parámetro `cierre`);
- ninguna def eliminada.

## 5. Archivos que no se tocaron

- Motores 6G originales y `main`.
- Validadores WAV/FLAC (`wav_integridad_6f.py`, `audio_integridad_6g.py`, `atribucion_6f.py`).
- Fixtures.
- Toda la evidencia y los scripts de c38d00d: `CICLO_VIDA_6G1.md`, `pruebas_ciclo_vida_6g1.*`, `matriz_ciclo_vida_6g1.csv`, `ast_ciclo_vida_6g1.json`, `MANIFEST/SHA256SUMS_CICLO_VIDA_6G1`, el patch de CV, `pruebas_ciclo_vida_6g1.py`, `verificar_ast_ciclo_vida_6g1.py` y `inyeccion_ciclo_6g1/`.
- La evidencia de la prueba DSP y la adjudicación.
- La matriz global y la consolidación.
- Sin audio real; sin Elis/Tristania; sin Android/Termux.

## 6. Integridad

- `SHA256SUMS_CIERRE_RECURSOS_6G1.txt`: comprobar desde la raíz del repo con `grep -v '^#' … | sha256sum -c`.
- `MANIFEST_CIERRE_RECURSOS_6G1.json`: SHA en c38d00d y actuales, y resultados.
- `DIFF_CIERRE_RECURSOS_6G1_vs_c38d00d.patch`: diff completo y reversible con `git apply -R`.

| Archivo | SHA-256 en c38d00d | SHA-256 actual |
|---|---|---|
| Hardened | `3977473dd4eab50c9bf365cbc913691f0c977d0c95f29e3b14764ebc6d4b5c8c` | `e3a0574fa6f4a35dd59968093df8a338431423d47f55f30e3114c80c272c5fe8` |
| EVO | `cd5aa200903b98065de9a722613581c66404d7962d9c6827f3689818dc80858d` | `438bb7a8eb834dee0bba060c9fe3d1d5e350909cb5d51c6e0c90f40b39b2690c` |
| MQR | `75f41cdaa811ad61822292ea3bbbc1e3c279389190a350f7d9b9e8dd989f717a` | `41b075dfdac23b4a4ecbb543051cfcfddabc36dfa4e496d90e7cb3b27efdbaf7` |
| `lectura_segura_6g1.py` | `e66ae40f39042da5c7b2fb5e5e129064224b856bc73e830175001744a0091c09` | `c1b73d4cb26f8ebc17aa873bbca694ca0cb169ad2e40988833185a5077c00407` |

Pendiente de revisión de Cris. La decisión final corresponde al responsable. 6G.1 no se declara cerrada.
