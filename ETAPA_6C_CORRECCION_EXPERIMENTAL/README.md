# Etapa 6C · Corrección experimental del diagnóstico de alineación

**[Informe de implementación y diez respuestas](INFORME_IMPLEMENTACION_6C.md)** · [Cruce por defecto](TRAZABILIDAD_DEFECTOS.md) · [Diseño](DISENO_TECNICO_CORRECCIONES.md) · [Estados y umbrales](TAXONOMIA_ESTADOS.md) · [Límites](LIMITACIONES_UNKNOWN.md).

Arena.ai ejecuta; Cris y Will revisan. Rama `arena/20d905c7-sdv-sdi-sgm`, a partir de la entrega 6B `7092c6cee764861d4bd8230eccb700f1d4d0556c`. **Diagnosticar no es corregir audio.** No usar estas copias como reemplazos de producción. No integración en `main`, sin ganador, sin música ni etapa 6D.

## Custodia y artefactos

- [Originales](source_hashes.json): recuperación desde el commit, SHA y tamaño contra 1B, S5, su auditoría, E6 y 6B; cotejo con el checkout. **v3 sólo se leyó.** [Copias congeladas](experimental_hashes.json) y [entorno](environment.json). La cadena de versión original no distingue las dos variantes B/C ni distingue original de experimento: usar SHA y `schema`.
- [motores/](motores/): **tres archivos completos y autocontenidos**. Cada uno incluye sus primitivas de medición; no se requiere copiar un módulo auxiliar junto al script. [Diff Hardened](DIFF_HARDENED.patch), [EVO](DIFF_EVO.patch), [MQR](DIFF_MQR.patch). Reaplicables en un directorio temporal con el archivo original exacto; no aplicar en `Proyecto SDV-SDI_SGM/`.
- [Matriz](MATRIZ_PRUEBAS_REGRESION.csv): una fila por motor/caso/P1/rol/canal, con **dos columnas históricas de contraste contra un mismo escalar**, no dos mediciones antiguas. `old_raw` apunta a una línea dentro de 6B. `raw` apunta a una línea descomprimida dentro de 6C. Campos vacíos = no disponible; cero numérico = cero medido (o histórico, si `old_`). `d_recipe` es nominal: para composiciones no identificables, ausencia o guía no relacionada no usarlo como verdad física. `d_mark` sólo existe con marca. `expected` usa severidad B/C/D a 44.1 kHz, distinta del simple «no cero» del oráculo 6B. `EXACT` requiere d **y** clase correctos.
- [Resultados de regresión](RESULTADOS_REGRESION.json): por partición, motor y rol, índices+SHA de todos los retornos, mediciones exactas, FP/FN, abstenciones y lista de fallos. [Estéreo](RESULTADOS_ESTEREO.json): ambos estados, soporte resumido, `dR−dL` y ausencia/presencia de k común. [Incidencias](ERRORES_Y_EXCEPCIONES.log): separa alarmas, avisos, error provocado y abortos de separación.
- `evidence/6B_{B,C,D}.jsonl.gz`: **nueva ejecución de las copias** sobre los 200 casos físicos y el control técnico X. No es una reejecución de los cuatro originales. Cada línea contiene `record` (ambos roles, preflight, ventanas, candidatos/solape/varianza, confidence, decisión y acción), y su SHA canónico. Se contrasta con el [oráculo anterior](../ETAPA_6B_VALIDACION_ALINEACION/evidence/oraculo.json), [CSV](../ETAPA_6B_VALIDACION_ALINEACION/MATRIZ_RESULTADOS.csv) e [índice](../ETAPA_6B_VALIDACION_ALINEACION/RESULTADOS_DETECTORES.json) sellados. `aggregator_only` es **sólo el agregador** D en contexto `analysis_only`, no certificación de un WAV.
- [Manifiesto reservado](evidence/reserva_manifest.json), `evidence/reserva_wav.tar.xz` y `evidence/reserva_{B,C,D}.jsonl.gz`: señales nuevas, receta/semillas, hashes de WAV/PCM/columnas, referencia de reloj, oráculo, 13 casos. No se ajustó el código a sus fallos. V0/I0 y los parámetros de receta **no se pasan al detector**.
- [No regresión](RESULTADOS_NO_REGRESION.json) y `evidence/no_regresion.jsonl.gz`: corrida nueva original y experimental para cada configuración sobre WAV de S5. Logs CLI íntegros, firmas de tensores en uso, máximos de diferencias elemento a elemento y PCM releído. El aborto conocido no cuenta como igualdad. No requiere confiar en que «el diff no toca la fórmula».
- [QA](evidence/control_calidad.json), [pruebas](tests/test_contratos.py), [resultado unitario](evidence/tests.log), [self-test MQR](evidence/mqr_self_test.log), [sello de la entrega](SHA256SUMS.txt). Todos los insumos publicados anteriormente se leen sin modificarlos.

### Inspección de una medida, sin dependencias DSP

Desde esta carpeta:

```python
import gzip, itertools, json
from pathlib import Path
idx = json.loads(Path('RESULTADOS_REGRESION.json').read_text())['index']
ref = idx['C']['6B']['F_interior_-22050_30s']['row']
f, n = ref.rsplit(':', 1)
with gzip.open(f, 'rt') as stream:
    run = json.loads(next(itertools.islice(stream, int(n)-1, None)))['record']
w = run['raw']['vocal']['channels']['L']['windows'][0]
print(w['tM'], w['tG'], w['local_requested'], w['best']['q'], w['estimated_offset_samples'])
```

El signo `k` nativo no es `d` de la guía. En un caso sin reloj no hay `best` obligatorio ni un entero para desplazar. Las correlaciones negativas binarias son evidencia temporal firmada, nunca una orden de invertir PCM.

## Reproducir sin escribir sobre la entrega

En Linux, desde esta carpeta dentro del clon con el historial Git. Python **3.11**, NumPy 1.26.4, SciPy 1.13.1, SoundFile 0.13.1, libsndfile 1.2.2, `git`, `patch`, espacio temporal para WAV (más de 5 GiB si falta la caché). No se instala nada por cuenta del usuario. `PY` designa el intérprete de ese entorno. Los scripts fijan BLAS a un hilo; ejecutar la primera restauración en serie.

```sh
sha256sum -c SHA256SUMS.txt
PY=${PY:-python3}
export SDV6C_OUT="$(mktemp -d)"
mkdir -p "$SDV6C_OUT/evidence"
"$PY" -B scripts/verificar.py --parches
"$PY" -B tests/test_contratos.py >"$SDV6C_OUT/evidence/tests.log" 2>&1
OPENBLAS_NUM_THREADS=1 "$PY" -B motores/sdv_sdi_mqr_engine.py --self-test >"$SDV6C_OUT/evidence/mqr_self_test.log" 2>&1
"$PY" -B scripts/regresion.py 6B BCD
"$PY" -B scripts/reserva.py
"$PY" -B scripts/regresion.py reserva BCD
"$PY" -B scripts/no_regresion.py
"$PY" -B scripts/consolidar.py
"$PY" -B scripts/verificar.py
```

La caché de WAV 6B se usa sólo si está completa y coincide con sus SHA; sin ella los miembros se extraen **en la salida 6C**. Los paquetes S5 y los manifiestos 6B se verifican contra Git. No hacen falta red, `gh`, audio real ni servicios de voz. En un replay cambian las rutas de temporales en trazas, tiempos de CLI y timestamp `PEAK` de los contenedores FLOAT; distinguirlos de diferencias en PCM. `build/` es descartable. Para recalcular tablas sin ejecutar motores, copiar `evidence/` y `RESULTADOS_NO_REGRESION.json` a una salida independiente y ejecutar `consolidar.py`; los datos medidos no se reconstruyen a partir de una tabla de respuestas esperadas.
