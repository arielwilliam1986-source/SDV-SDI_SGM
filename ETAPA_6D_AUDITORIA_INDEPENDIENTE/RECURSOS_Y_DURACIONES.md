# E · Cuánta memoria y tiempo se midieron, y para qué operación

**EXPERIMENTAL_RESULT · CONFIRMADO en Linux x86_64.** Con **seis pares más el Mix**, los tres motores experimentales completaron el DSP en los estímulos de 2, 14 y 40 s. Se probaron también archivos de **1 074 790 444 bytes cada uno**, pero allí sólo se ejecutó `dry_run`. No es un ensayo de alineación o separación de archivos de 1 GiB. **No se observó un OOM ni se estableció un máximo admisible de tamaño, RAM o duración.**

## Protocolo y unidades

Python 3.11.2, Linux 6.1.158+ / glibc 2.36, x86_64, Intel Xeon, afinidad 2 CPU, MemTotal 4 034 452 KiB, sin swap en el entorno. NumPy 1.26.4, SciPy 1.13.1, SoundFile 0.13.1, libsndfile 1.2.2; BLAS/OMP/MKL a un hilo. [Entorno](environment.json). WAV FLOAT estéreo 44.1 kHz; el generador crea 13 contenedores con SHA distintos (Mix y seis pares con variantes de nivel), no trece procesos ni seis separaciones simultáneas. Códigos breves reproducibles en tres posiciones relativas, no audio denso o modelos reales. Cada CLI se inicia de nuevo, secuencialmente dentro de su serie, con configuración nativa por defecto, sin flag de permiso. Al medir el proceso completo no hay perfilador Python instalado en el motor.

- **RSS pico**: `os.wait4` del hijo en KiB Linux, padre monitor de biblioteca estándar, en un intérprete separado. Se sondeó `/proc/PID/status` cada ~100 ms (`VmRSS`, `VmHWM`, `RssAnon`, `RssFile`, `VmSwap`). La anónima muestreada no es el RSS total ni un pico exacto de toda memoria transitoria. Se midieron user/sys, tiempo de pared hasta recogida del hijo y tamaño lógico/asignado visible en el directorio de salida. Resolución de pared ~0.1 s; incluye arranque y escritura, no creación de fixtures. No son pruebas de latencia en aislamiento de CPU ni medianas sobre un conjunto de música.
- **Memoria transitoria del detector**: ensayo separado, `tracemalloc` alrededor de `analyze_alignment` completo (Mix/V); pico, retenida al retorno y su diferencia. Incluye las asignaciones trazables; no todas las páginas de FFT, bibliotecas, cache de archivos ni todo el DSP. No se suman RSS, trazas y disco. [Comparación original/copia](evidence/coste_detector.json.gz).
- [36 mediciones de referencia](evidence/resources_index.json) · [series temporales, argv, SHA, stdout/stderr e informes completos](evidence/resources_raw.json.gz). La [serie piloto](evidence/resources_piloto_raw.json.gz) se conservó pero **no se mezcló**: su padre, que también había medido arrays, aportaba un HWM heredado visible antes del `exec` en algunos `wait4`. En los seis dry grandes marcaba 468 908 KiB mientras el `VmHWM` del ejecutable era <95 000 KiB. Se repitió la serie con padre liviano, no se tocó ningún motor. [Incidencia](evidence/incidencias_instrumentacion.log).

## CLI experimental completa: RSS pico (MiB) / pared (s)

| Duración; pares | Hardened | EVO | MQR |
|---|---:|---:|---:|
| 2 s; 1 | 162.6 / 1.01 | 163.0 / 0.90 | 169.5 / 1.21 |
| 2 s; 2 | 173.6 / 1.21 | 174.0 / 1.21 | 177.3 / 1.51 |
| 2 s; 3 | 183.6 / 1.41 | 184.2 / 1.51 | 192.1 / 1.81 |
| 2 s; 4 | 195.9 / 1.71 | 196.4 / 1.71 | 203.2 / 2.11 |
| 2 s; 5 | 207.3 / 2.01 | 208.7 / 1.91 | 212.7 / 2.41 |
| 2 s; 6 | 220.3 / 2.21 | 220.6 / 2.21 | 224.3 / 2.72 |
| 14 s; 1 | 333.0 / 3.52 | 332.4 / 3.62 | 370.0 / 5.63 |
| 14 s; 6 | 589.1 / 13.67 | 582.5 / 12.97 | 678.4 / 16.90 |
| 40 s; 1 | 388.6 / 9.24 | 383.4 / 7.84 | 487.9 / 14.57 |
| 40 s; 6 | 638.8 / 38.30 | 631.5 / 30.22 | 935.7 / 45.17 |

**EXPERIMENTAL_RESULT · CONFIRMADO.** 30 exits 0, cada uno con informe final y dos WAV. A 2/14/40 s, bytes de **cada entrada**: 705 644 / 4 939 244 / 14 112 044; total lógico para `P` pares: `(2P+1)×bytes`. A 40 s y seis pares son **183 456 572 bytes** de entrada. Máximo de bytes lógicos de salida visibles en esa corrida: B 29 409 999, C 29 507 943, D 312 668 348 (incluye memmaps/máscaras e informes); anónima máxima muestreada: 599.9, 592.9, 629.2 MiB. Esto distingue memoria de trabajo, páginas de archivos y ocupación en disco. El tamaño temporal muestreado puede perder un archivo muy efímero. No hay límite impuesto ni recomendación de reducir pares.

### Coste del detector en procesos frescos: original → copia

**EXPERIMENTAL_RESULT · REGRESIÓN de huella temporal en los tamaños medidos.** Pico **trazado** en MiB, un rol por proceso, con las mismas entradas para cada versión. No son los 30 procesos CLI de la tabla anterior. El sentido del cambio de tiempo en estos estímulos dispersos no tiene por qué ser el mismo que en material denso.

| Motor | 2 s, pico | 14 s, pico | 40 s, pico | 40 s, pared de la llamada trazada original → copia | 40 s, HWM del proceso tras la llamada (KiB) |
|---|---:|---:|---:|---:|---:|
| B | 7.5 → 15.8 | 52.1 → 80.1 | 148.9 → 227.8 | 11.31 → 1.29 s | 247 988 → 391 708 |
| C | 6.1 → 15.8 | 42.7 → 71.2 | 58.6 → 116.7 | 0.97 → 0.75 s | 153 424 → 244 720 |
| D | 6.7 → 15.8 | 47.1 → 80.1 | 134.6 → 227.8 | 11.26 → 1.31 s | 231 376 → 391 748 |

En la medición transitoria complementaria de la serie CLI, a 40 s la diferencia «pico trazado menos retenida al retorno» fue 238 823 350 B (B y D) y 122 270 825 B (C). B/D correlacionan el archivo en un rango global acotado; C afina una o dos ventanas pero **decodifica las dos entradas completas** al medir cada guía. Los pares se recorren; el coste de una pareja de arrays no se multiplica sin más por trece archivos.

### Más de 1 GiB por archivo: qué ocurrió realmente

**EXPERIMENTAL_RESULT · CONFIRMADO (sólo preflight).** 134 348 800 frames, 3046.458 s, 1 074 790 444 bytes lógicos por contenedor. Archivos creados por `truncate` + escrituras posicionadas, distintos por contenido/SHA; no son 50 minutos de señal densa. Para 6 pares, 13 archivos, total lógico **13 972 275 772 B**; bloques asignados reportados por este FS, **4 299 855 872 B** para los trece al inventariar. No usar el tamaño lógico como medida de I/O físico. Todas las CLI devolvieron 0, **cero** informes de análisis final/WAV. RSS MiB / s de dry-run para 1 y 6 pares: B 90.7/4.22 y 90.8/17.08; C 91.0/4.12 y 91.1/16.39; D 92.0/3.92 y 92.3/16.47. Es prueba de admisión y planificación del inventario grande, no de una medición de reloj grande.

**THEORETICAL_DEDUCTION · CONFIRMADO como cuenta de bytes, no como resultado de ejecución.** Dos arrays estéreo `float64` de esa longitud representan `2×134348800×2×8=4 299 161 600 B` antes de correlación, copias y DSP. Ese volumen lógico ya excede el MemTotal declarado aquí. No se forzó el cálculo completo grande en el sandbox. No se observó su RSS, éxito ni fracaso, y no se deduce de esto un OOM en otro equipo. No se cambió lectura, ventana, chunk ni arquitectura por anticipado.

## Protocolo Termux/ARM64 para ejecutar localmente si se autoriza

**DOCUMENTED_FACT (declaración del usuario).** El usuario trabaja con archivos >1 GB y hasta seis pares + Mix en Termux, con un mecanismo para mantener Termux activo. Se respeta esa experiencia; no se tomó como medida de estas copias. **UNKNOWN · UNKNOWN:** RAM efectiva, tiempo, políticas de Android y resultados de esta batería allí. El protocolo siguiente está **diseñado, no ejecutado en Android**.

1. Usar un checkout con los SHA indicados, el Python ≥3.11 y las dependencias científicas que funcionen en el dispositivo. Anotar `uname -a`, `getprop ro.product.cpu.abi`, versión Android/API, `python -VV`, versiones NumPy/SciPy/SoundFile/libsndfile, hilos, `/proc/meminfo`, almacenamiento y sistema de archivos, swap/zram si visibles, batería/temperatura y la configuración habitual del usuario para mantener la sesión. No solicitar contraseñas, root, deshabilitación de protecciones ni un límite artificial de RAM. Trabajar en un directorio privado nuevo y con espacio comprobado, sin canciones reales.
2. Desde la raíz, este ejemplo **sólo sintético** genera los manifiestos para 1…6 pares. Usar primero los mismos tamaños que Linux. `ENGINE` toma el motor B; cambiar únicamente la clave para repetir con C o D. Conservar logs por corrida y no reusar un directorio de salida.

```sh
N=ETAPA_6D_AUDITORIA_INDEPENDIENTE
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
R=$(mktemp -d)
python -B "$N/scripts/resources.py" --prepare "$R/inputs" --frames 88200
ENGINE=$(python -c 'import json,sys; print(json.load(open(sys.argv[1]))["engines"]["B"]["path"])' "$N/experimental_hashes.json")
for P in 1 2 3 4 5 6; do
  mkdir -p "$R/out-$P"
  python -B "$N/scripts/medir.py" "$R/log-$P" "$R/out-$P" -- \
    python -Bu "$ENGINE" --manifest "$R/inputs/p$P.json" --mode full_processing --out "$R/out-$P" || break
done
```

3. Repetir con 617400 y 1764000 frames en directorios nuevos; registrar repeticiones por separado. Para el inventario grande: `--frames 134348800`, primero `--mode dry_run`. Registrar para cada archivo `stat`/SHA, bytes lógicos/asignados, duración, nº pares, stdout/stderr, exit o señal, métricas del monitor y archivos finales/abortados. En algunos Android `/proc/PID/status` puede estar restringido: conservar el `wait4` si disponible y marcar el dato faltante, no rellenarlo con cero como si fuera una medición. Verificar que el FS dispone de espacio real para entradas **y** salidas.
4. Sólo bajo decisión local separada, ensayar una carga completa larga progresando duración y nº de pares, sin alterar el motor. Identificar siempre preflight vs detector vs pipeline terminado; separar RSS propio de memoria del sistema, transitorio trazado, almacenamiento y cache. Si Android detiene una corrida, recoger la evidencia de terminación disponible al usuario; no llamarla OOM sólo por haber perdido la sesión. La autorización de ese ensayo y sus resultados no forman parte de 6D.