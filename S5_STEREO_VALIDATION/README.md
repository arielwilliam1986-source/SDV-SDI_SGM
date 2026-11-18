# SDV-SDI / SGM · Etapa S5

**[Informe y conclusiones por motor](reports/INFORME_S5.md)** · [CSV por canal](measurements/resultados.csv) · [Control de calidad](results/control_calidad.json)

Estudio sintético en la rama `arena/20d905c7-sdv-sdi-sgm`. Coordinación: Cris; autorización: Will; ejecución: Arena.ai. Ningún cambio en `main`, los cuatro originales ni Fase 1B. Aquí `S5` designa **la etapa**; `S1`…`S7` designan **fixtures**, y `S5` como fixture sólo designa el de retardos.

| Evidencia | Dónde encontrarla |
|---|---|
| Procedencia | [Cuatro copias y SHA-256 oficiales](source_hashes.json), `sources/`. Descargadas con la API de GitHub al SHA de `main` y cotejadas también con `git show`. |
| Entorno y requisitos | [Entorno activo](environment.json), [entorno previo](logs/entorno_inicial.json), [fallo previo](logs/preflight_inicial.log), [versiones exactas](logs/requirements-entorno.txt), `logs/help_*.txt`. |
| Señales | [Fórmulas discretas, dimensiones, mediciones y hashes](signals/manifest.json); [generador](scripts/generador_sintetico.py); [26 WAV de entrada y sus manifiestos](evidence/inputs.tar.xz). |
| Experimentos | [A · v3](results/s5_a_v3.json), [B · Hardened](results/s5_b_hardened.json), [C · EVO](results/s5_c_evo.json), [D · MQR](results/s5_d_mqr.json). Identificador único `(block,id)`; `series` separa `principal`, `unilateral`, `polaridad` y `hybrid`. |
| Consola | [Todas las corridas](logs/ejecucion_completa.log), [aborto antifase MQR](logs/aborto_D_S7_shared.log). Los mensajes de éxito/SNR de los motores se conservan como salida nativa, no como juicio del estudio. |
| WAV, máscaras e informes nativos | [Índice](evidence/index.json), [A](evidence/S5-A.tar.xz), [B](evidence/S5-B.tar.xz), [C](evidence/S5-C.tar.xz), [D](evidence/S5-D.tar.xz). Cada ruta `runs/...` o `inputs/...` de los resultados es un miembro de estos paquetes. |
| Integridad | [SHA-256 de cada archivo publicado](hashes/SHA256SUMS.txt) (excepto la propia lista), [SHA-256 por miembro descomprimido](hashes/MIEMBROS_SHA256.txt). |

### Verificar sin ejecutar DSP de los motores

Desde `S5_STEREO_VALIDATION/`, en una copia de este commit:

```sh
sha256sum -c hashes/SHA256SUMS.txt
python3 -B scripts/preparar_fuentes.py  # verificación local con stdlib, sin descarga
```

Con los paquetes indicados en `logs/requirements-entorno.txt` **ya disponibles** en un intérprete CPython 3.11 (`$PY`), ejecutar:

```sh
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
"$PY" scripts/verificar.py
```

Esto lee los tar.xz **sin extraerlos**, abre todo WAV, valida JSON nativos y de entrega, CSV, formas de máscaras y hashes; recalcula medidas, reconstrucción y contrastes pareados. `PASS_INTEGRITY` **no** significa que no haya escenarios fallidos. Para escuchar o inspeccionar sólo un bloque, p. ej. B: `mkdir -p build && tar -xJf evidence/S5-B.tar.xz -C build`. Se conservan los **144 WAV completos** (26 de entrada, 116 de corridas completadas y 2 del aborto), 59 máscaras efectivamente aplicadas en NPY de precisión original y los demás archivos nativos, incluidos los que dejó el fallo. Los cinco paquetes suman 55 911 452 bytes para 565 978 358 bytes de miembros; mayor paquete <18 MB. Compresión sin pérdidas, sin conversión a PCM de menor precisión. No se requiere un servicio externo.

### Repetir las corridas (en otra copia local de la entrega)

Usar un directorio `build/` inicialmente **ausente o vacío**; el ejecutor rechaza reutilizar un directorio de corrida. No repetir dentro de una copia que se desee conservar sellada. El venv utilizado en Arena estaba fuera del repo y se instaló sólo tras autorización de Will. Los scripts **no instalan nada**. Para reponer fuentes si procede, `scripts/preparar_fuentes.py --descargar` verifica primero que `main` siga exactamente en el SHA del estudio; la verificación sin `--descargar` permite reproducir desde el commit fijado aunque `main` avance.

```sh
# cwd: S5_STEREO_VALIDATION; $PY: ruta del intérprete con las versiones registradas
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
"$PY" scripts/preparar_fuentes.py
"$PY" scripts/entorno.py
"$PY" scripts/generador_sintetico.py
"$PY" scripts/pruebas_s5.py all    # o A, B, C, D por separado
"$PY" scripts/consolidar.py
"$PY" scripts/archivar.py
"$PY" scripts/verificar.py --sellar   # sólo en la copia de la nueva corrida
```

`pruebas_s5.py` comprueba hashes, `--help`, parser y argumentos de cada bloque. A usa el núcleo nativo (su CLI llamaría a la auditoría de alineación); B, C y D entran por `main` con su propio parser. `--allow-misaligned` en B/C/D permite estudiar estos estímulos periódicos o cancelados sin corregir desplazamientos. No se trata el diagnóstico temporal nativo como verdad de referencia. En la campaña original se añadió `Ronly` **después** de la matriz principal mediante `--solo-control-r`; la ejecución `all` limpia ya lo incluye. La CLI de cada bloque, las opciones resueltas, los parámetros API específicos de A y los hashes exactos de las entradas están en `runs[]`. En una repetición pueden variar marcas de tiempo, rutas nativas, cabecera PEAK del WAV FLOAT y hashes del contenedor; comparar además `pcm_f32le_sha256` (muestras intercaladas L,R float32 LE) y las medidas. Los hashes publicados verifican **esta** corrida, no una predicción.

### Leer las magnitudes sin confundir conceptos

- Ejes de espectros: **canal, bin de frecuencia, trama**. En máscaras, la ausencia de eje canal (o un eje de longitud uno en v3) significa **una sola estimación**. `applied_mask.npy` concatena los chunks por el eje de tramas sin alterar el dtype ni duplicar la máscara compartida.
- `lr_mix_energy_weighted_rms = sqrt(Σ E·(M_L−M_R)²/Σ E)`, con `E=|X_L|²+|X_R|²`. También se informan máximo y RMS sin ponderar, y media, desviación, mínimo y máximo por mapa real. En los contrastes de modos se difunde explícitamente el mapa compartido para comparar ambos canales.
- `outputs.*.rms`, `peak`, `tp4x`, `nonfinite` y `reconstruction.{rms,max_abs}` son listas **[L,R]**; las magnitudes de audio son lineales, en FS. Las diferencias entre modos son **RMS de la resta de muestras**, no restas de dos niveles RMS. `null`/campo vacío corresponde a indefinido o no aplicable, nunca a un cero imputado.
- Los WAV de un aborto figuran como `FAILED` en CSV y `aborted_wavs_not_completed_outputs` en JSON. No alimentan los contrastes de corridas completadas. Para medidas, suposiciones y alcance científico, ver el [informe](reports/INFORME_S5.md).
