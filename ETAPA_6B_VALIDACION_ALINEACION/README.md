# Etapa 6B · Validación experimental del reloj de las guías

**[Informe y diez respuestas para revisión](INFORME_VALIDACION_6B.md)** · [Análisis por motor](ANALISIS_POR_MOTOR.md) · [Qué cambia al comparar con v3](COMPARACION_CON_V3.md) · [Alcance y pendientes](LIMITACIONES_Y_CASOS_UNKNOWN.md).

Arena.ai, rama experimental `arena/20d905c7-sdv-sdi-sgm`. Esta entrega se añade **después** del diagnóstico `1f5d7e8f39c54f197b2bbf0a2fa520af4a39ddae`. Sólo prueba la **detección original** y, en MQR, su agregador de estados por separado. No hay separador nuevo, parámetros DSP nuevos, stems de salida, correcciones temporales o de polaridad, ni música.

## Inspección anterior a la ejecución

**DOCUMENTED_FACT · CONFIRMADO.** Se recuperaron los cuatro blobs completos mediante `git show` desde `b64f15ae8b28e46eef3c024dc62c85fe27c69494`. Se verificaron tamaño, SHA-256, referencia 1B, blobs de S5, copia S5 y original en el checkout. Sólo entonces se importaron los originales de `Proyecto SDV-SDI_SGM/`. [source_hashes.json](source_hashes.json) identifica cada uno por bytes, OID Git, `ENGINE_VERSION`, signatura, función llamadora y líneas reales de llamada. Hardened y EVO declaran **la misma** cadena de versión: los distingue el SHA, no el nombre anunciado. [environment.json](environment.json) fija intérprete, dependencias, arquitectura, hilos y commit a la partida.

| Clave | Entrada real invocada / registro | Qué se dejó fuera |
|---|---|---|
| A · v3 | `main:2103` llama `audit_alignment(pairs,mix_info)` (1113–1172). Se pasó una lista con un `PairMeta` real P1 (V e I) y el `FileInfo` del Mix sondeado. Se guardó **todo** el diccionario, incluidas guarda y banderas del par. | No se llamó a la separación ni a `audit_polarity`. `--correct-alignment` y `--fix-polarity` son operaciones posteriores de la CLI. Se ensayó por separado `check_degeneration` de las guías como comprobación previa; su rechazo se registra, **no** se presenta como retorno del detector. Esto permite caracterizar el mid nulo, incluso en el límite que la CLI rechazaría. S5 no había llamado a este detector. |
| B · Hardened | `run_experiment:1334` llama `analyze_alignment(mix_info,guide_info)` (524–573) por par y rol. Mismas dos invocaciones completas, con `probe_file` y validadores originales. | No `read_span`, LS ni máscaras. En la CLI `--allow-misaligned` permite continuar; no equivale a `--correct-alignment`. La clasificación se produce antes de ambos consumidores. |
| C · EVO | `run_experiment:1434`; `analyze_alignment` (529–625) incluye el barrido de energía, el recorte de segmentos, el refinamiento y la decisión de identidad. **No** se sustituyó por los auxiliares comunes a B. | Sin shifts, sin `analyze_guide_scale`, sin la inversión de signo que EVO podría realizar después. |
| D · MQR | `run_experiment:2109`; `analyze_alignment` (853–931) con los dos `FileInfo`, sin caché opcional. Además, `build_validation_status` (2882–2913) **original**, con las clasificaciones de esas llamadas, metadatos, advertencias de entrada y el valor admitido `MODE_ANALYSIS_ONLY` en `opt.mode`. | `detect_only_no_correction`. La prueba adicional del agregador **no es una corrida CLI `analysis_only`**, no ha habido confirmación interactiva, post-WAV ni un `exit` de separación. |

**DOCUMENTED_FACT · CONFIRMADO.** Ninguno necesitó arrancar la separación. No se inventó un flag `detector-only`, ni se usó `dry_run` como si midiera alineación. El observador CPython recibe eventos de llamada/retorno de la ejecución real, lee locales y valores de retorno y no reemplaza funciones. En B/C/D observa el coseno grueso y el Pearson fino (25 scores), **antes** de que EVO pueda sustituir el candidato. En A no hay etapa gruesa: se deja vacía, no se escribe cero. Una lista de llamadas a operaciones posteriores vigila que ninguna alcance el procesamiento.

## Diseño y archivos

| Recurso | Contenido |
|---|---|
| [signals_manifest.json](signals_manifest.json) | 200 casos físicos A–F. Por caso: receta, duración, semilla, signos, ganancias impuestas, retardos en muestras, posiciones de las marcas y SHA de Mix, V, I, V0 e I0. El sufijo `0` identifica la referencia del rol en el reloj del Mix, **no** una señal suministrada al detector. Las ms exactas también se guardan por ejecución en el nativo y en la matriz. |
| `evidence/wav_{4,30,70}s.tar.xz` | Todos los WAV de entrada y referencias, sin pérdida. 338 contenedores distintos; el nombre interno es `<sha256>.wav`. La clave del fichero es su hash; el manifiesto contiene además hashes de PCM y de columnas, formato y metrología. No hay que descargar datasets ni recuperar un temporal anterior. |
| `evidence/{A,B,C,D}.jsonl` | Registro primario: una línea por caso/motor con ambos roles, retornos originales sin edición, traza, flags de acción, preflight, errores, consola, hash del retorno y SHA del registro canónico. Incluye un control técnico X por motor, **aparte** de los 200 físicos. |
| [evidence/oraculo.json](evidence/oraculo.json) | Relectura de los archivos de los tres paquetes en un directorio nuevo; comprobación L/R de reloj por marca, de periodicidad, varianza, suma y controles pareados. No usa el lag nativo para encontrar la marca. |
| [RESULTADOS_DETECTORES.json](RESULTADOS_DETECTORES.json) | Índice por motor, caso y rol, incluyendo números de línea y hashes que resuelven los retornos originales; denominadores y errores por rol. |
| [MATRIZ_RESULTADOS.csv](MATRIZ_RESULTADOS.csv) | Una fila por **motor, caso, P1, rol y canal de contraste**. Un campo vacío significa no disponible/no medible. No hay una estimación nativa L o R separada en ninguno de los cuatro. |
| [DESGLOSE_METRICAS.csv](DESGLOSE_METRICAS.csv) | Numeradores, denominadores y errores por motor y rol: grupo, duración, magnitud, retardo firmado, canal, grupo×duración y cruce grupo×duración×magnitud×canal. X no entra en las tasas físicas. |
| [ERRORES_Y_EXCEPCIONES.log](ERRORES_Y_EXCEPCIONES.log) | Rechazos de preflight, excepciones propagadas o capturadas por el motor, centinelas anómalos, avisos del intérprete y errores de observación si existieron. Las clasificaciones nativas de advertencia se conservan en JSONL y CSV. |
| [scripts/](scripts/) · [SHA256SUMS.txt](SHA256SUMS.txt) | Generación, ejecución, oráculo, consolidación y verificación. El sello cubre todos los archivos publicados de 6B salvo él mismo. |

**Diseño.** 44100 Hz, dos canales, FLOAT32LE. El Mix está en su propio reloj; `d>0` significa **guía tardía**. Los ±5 y ±25 ms se impusieron en ±221 y ±1103 muestras (mitades alejándose de cero), no en 220.5 ni 1102.5 muestras. Se distinguen ±1 **muestra** y ±1 ms. Magnitudes del barrido principal, en muestras → ms reales: 0 → 0; 1 → 0.022676; 221 → 5.011338; 441 → 10; 485 → 10.997732; 1103 → 25.011338; 4410 → 100; 22050 → 500 (ms aquí redondeadas). Un único cast en la escritura de la señal según la receta, sin normalización. La guía se construye a partir de su fuente sintética con signo, ganancia y tiempo predefinidos, nunca desplazando un archivo del motor para obtener `ALIGNED`. En las portadoras periódicas se usa extensión periódica, sin rellenar con silencio que revelaría artificialmente el retardo. En el resto se usa soporte finito. Para las tres relecturas S5 de 4 s se conservan exactamente los bytes archivados, no una aproximación al generador S5.

- **A:** sweep de 15 retardos en las tres duraciones, I fija, V intervenida; copia exacta V=Mix con I muda; ocho fronteras adicionales en 4 s. Las tomas repetidas de I no son pruebas independientes de retardo cero.
- **B:** sincronía, L solo, R solo, oposición, retardos distintos, R/L=1/4, espectros diferentes, actividad de V unilateral, swap exacto, e I con dos relojes. Los WAV suministrados **siempre** tienen dos canales.
- **C:** tonos/armónicos estacionarios con controles de bytes iguales y verdad nominal distinta; transitorios, portadoras más marcas, tren de 1001 muestras frente a portadora de período 100, material con AC alta y marca finita, ráfagas pseudoaleatorias. Sólo en estas últimas interviene ruido PCG64 real (semilla 6011, subflujos por rol y columna); las otras recetas no dependen del azar aunque se registra 6001.
- **D/E:** silencio, silencio parcial, DC, guía a 10⁻⁷, guía nula o sólo R débil, lateral exacto y casi lateral; cuatro combinaciones de polaridad de V en 0 y +1103 muestras. Se evalúa la polaridad **impuesta**, no se invierte audio a la salida.
- **F:** tres posiciones con d=0 y ±22050; en 70 s se separa actividad a 62–66 s de actividad a 68–69.3 s. No se confunde el rango de lag con la porción de archivo escuchada.
- **X:** se sondean metadatos válidos y se pasa una **ruta deliberadamente ausente** en la lectura de V; no se borra un WAV. En A el par queda interrumpido; en B/C/D se invoca I independientemente. Es una prueba de contrato posterior al sondeo, no una entrada física con lag medible ni una prueba de que la CLI admitiría una ruta inexistente.

## Cómo interpretar una fila

`k_nativo` (columna `lag_nativo`) mantiene el signo del motor; `d_publicado_comun` aplica `+k` en A y `−k` en B/C/D. En A es el valor **efectivo**, distinto del candidato si actúa la guarda; en C se conserva además el lag fino anterior a identidad. `delta_nominal` es aritmética incluso si el tiempo es inobservable; `error_contra_marca=d_publicado_comun−d_marca` sólo existe con marca medida y retorno sin error. Ninguno de estos números es una inferencia de reloj por canal del motor. `sha256_retorno_nativo` sella la lista de retornos por invocación, con los dos roles dentro de un único retorno para A. La línea JSONL entera tiene sello adicional (incluye tiempo de ejecución). En `RESULTADOS_DETECTORES.json`, `evidence/B.jsonl:1` significa primera línea, no nombre de fichero con dos puntos.

**Taxonomía externa.** El *oráculo* dice `ALIGNED` si una marca única, buscada en toda la columna de referencia y en toda la guía, demuestra 0 muestras; `MISALIGNED` si demuestra otro entero. Para buscar la marca sólo se transforma el **patrón esperado** con el signo y la ganancia de construcción, no la señal que recibe el detector. Las dos referencias se verifican contra el Mix. Un ciclo repetido sin marca es `AMBIGUOUS`, una columna constante o sin rol es `INSUFFICIENT_SIGNAL`; una coincidencia no única de la marca sería `WARNING`, y la lectura ausente `ERROR`. Separadamente, `estado_externo` revisa el **resultado del detector**: no aprueba un centinela, identidad forzada, varianza nula del mid leído o un único reloj para dos retardos incompatibles. `WARNING` también identifica una estimación no exacta frente a una marca conocida: consultar el error en muestras, no interpretarlo como un umbral de audibilidad. Ni esta taxonomía ni la comparación exacta del fixture cambian los límites de producción de ningún motor.

### Inspección puntual sin dependencias de audio

Desde esta carpeta, sólo con la biblioteca estándar de Python:

```python
import json
from pathlib import Path
caso = 'F_interior_-22050_30s'
ij = json.loads(Path('RESULTADOS_DETECTORES.json').read_text())
path, line = ij['motores']['C']['cases'][caso]['raw'].rsplit(':', 1)
r = json.loads(Path(path).read_text().splitlines()[int(line)-1])['record']
q = next(c for c in r['calls'] if c['roles'] == ['vocal'])
print(r['truth_samples']['vocal'], q['trace']['tG'], q['trace']['tM'],
      q['trace']['uncensored_global_native_subsample'], q['raw']['classification'])
# [-22050, -22050] 661500 595350 -50058.0 ALIGNED_BY_IDENTITY
```

[control_calidad.json](evidence/control_calidad.json) conserva el cierre del inventario. En otro directorio sin `build/` se volvieron a obtener desde los paquetes, oráculo y JSONL seis derivados idénticos byte a byte: matriz, desglose, índice de resultados, log de incidencias, testigos y control de calidad. [reproduccion_pcm.json](evidence/reproduccion_pcm.json) verifica además la regeneración en memoria, y [testigos.json](evidence/testigos.json) enlaza cuatro comparaciones de onda y dos consumidores históricos con sus archivos primarios.

## Reproducir sin sobreescribir esta entrega

Primero, desde la raíz de este repositorio: `(cd ETAPA_6B_VALIDACION_ALINEACION && sha256sum -c SHA256SUMS.txt)`. Para repetir cálculos, usar Python 3.11 con las versiones de `environment.json` (NumPy 1.26.4, SciPy 1.13.1, SoundFile 0.13.1). Ejemplo POSIX, en un directorio **nuevo**, no en la evidencia sellada:

```sh
set -eu
S="$PWD/ETAPA_6B_VALIDACION_ALINEACION/scripts"
export SDV6B_OUT="$(mktemp -d)"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
python -B "$S/base.py"
python -B "$S/generar.py"
python -B "$S/ejecutar.py" ABCD
python -B "$S/oraculo.py"
python -B "$S/consolidar.py"
python -B "$S/testigos.py"
python -B "$S/verificar.py" --regenerar-pcm
python -B "$S/verificar.py"
```

Alternativa a generar: copiar `signals_manifest.json` y los tres paquetes `wav_*.tar.xz` bajo `$SDV6B_OUT/evidence/` (el manifiesto en `$SDV6B_OUT/`), y llamar `generar.py --restaurar`. El ejecutor rehúsa sobreescribir un nativo preexistente. Se puede repartir `AC` y `BD` en dos procesos sobre el mismo conjunto ya materializado; no lanzar dos procesos para el mismo motor. Prever al menos 9 GiB libres para WAV expandidos y verificación independiente, además de memoria para la FFT de v3. Los paquetes y retornos publicados bastan para inspeccionar resultados; no hace falta el venv histórico ni una carpeta `build/` persistida. SHA del registro completo puede variar con tiempos/rutas de traceback; comparar primero PCM y **retorno nativo** en igual entorno.

**Lectura de los dictámenes.** Los inventarios y contratos descritos son `DOCUMENTED_FACT · CONFIRMADO`. Los valores observados se identifican con `EXPERIMENTAL_RESULT`; `THEORETICAL_DEDUCTION` indica una consecuencia de fórmulas o evidencia, no otra corrida. `HYPOTHESIS` y `UNKNOWN` no son reparaciones ni aprobaciones. El dictamen se refiere al enunciado y alcance indicados.

**Punto de parada.** Esta batería caracteriza los originales; no entrena umbrales ni valida una implementación corregida. Cualquier intervención y cualquier uso de material musical requieren una nueva revisión de Cris y del usuario.
