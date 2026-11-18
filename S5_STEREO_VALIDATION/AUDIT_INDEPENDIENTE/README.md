# Revisión independiente de la evidencia S5

**Leer primero:** [dictamen, defectos y condiciones para un piloto](INFORME_AUDITORIA_S5.md). Objeto inmutable: [`c1ce9e29e15a9c5eb2789187097f94fc13cefaa0`](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/c1ce9e29e15a9c5eb2789187097f94fc13cefaa0). Revisión: Arena.ai. Revisión final: Cris. Autorización de avance: Will. Esta carpeta es **posterior** al objeto auditado; no forma parte de su sello.

| Archivo | Uso |
|---|---|
| [INFORME_AUDITORIA_S5.md](INFORME_AUDITORIA_S5.md) | Respuesta a A–G, alcance de S1–S7, controles, defectos y preparación. |
| [VERIFICACION_INTEGRIDAD.json](VERIFICACION_INTEGRIDAD.json) | Recuento propio, ancla Git/GitHub, referencias 1B, hashes, duplicados, resolución de 59 ensayos, mediciones, contrastes, ejemplos de discrepancias semánticas. |
| [MATRIZ_MOTORES_ESTEREO.csv](MATRIZ_MOTORES_ESTEREO.csv) | 13 filas. Separa configuración ejecutada, controles EVO y caminos de residuales inspeccionados pero no ejecutados. Un campo vacío de Ronly significa **no ensayado**, no cero. |
| [MATRIZ_EVIDENCIAS.csv](MATRIZ_EVIDENCIAS.csv) | 38 afirmaciones con prueba, ruta, clase epistemológica, veredicto y limitación. Algunas filas evalúan explícitamente una interpretación que la evidencia **contradice**, no una afirmación atribuida al informe S5. |
| [PRUEBAS_PENDIENTES.md](PRUEBAS_PENDIENTES.md) | Seis propuestas concretas, con prioridades. No se ejecutaron ni se autorizan por este informe. |
| [SHA256SUMS.txt](SHA256SUMS.txt) | SHA-256 de los seis documentos nuevos, incluido este índice. El hash de la lista se entrega por separado para evitar autorreferencia. |

**Cómo leer las referencias.** En el informe, `sources/`, `results/`, `signals/`, `scripts/`, `logs/`, `measurements/`, `hashes/` y `evidence/` son relativos a `S5_STEREO_VALIDATION/` del commit auditado. En los CSV las rutas parten de la raíz del repo y se separan con ` | ` dentro de la celda. Sus dos ejes de lectura son la **configuración** o la **afirmación**, no el nombre de una gráfica nativa. `archivo.tar.xz!ruta` significa el miembro literal dentro del paquete; `#L` indica líneas en una fuente. En el JSON de revisión, `inputs/...` pertenece a `evidence/inputs.tar.xz`; `runs/X/...` a `evidence/S5-X.tar.xz`. La clave `matriz.corridas["B/S2_per_channel"]`, por ejemplo, da el manifiesto, las entradas por rol, la consola, la máscara, los **dos** WAV y el índice (desde cero) en `runs` del resultado primario de B. No hace falta adivinar las carpetas con fecha.

### Método y reproducibilidad

1. Se verificó `arena/20d905c7-sdv-sdi-sgm` local y en `origin`, con el commit S5 exacto como punta antes de publicar esta carpeta. Se exportó con `git archive` a un temporal fuera del checkout. Nada se leyó de un `build/` previo. El árbol de GitHub del commit confirmó los OID y tamaños de los 47 blobs. Se contrastaron los bytes con la base por SHA, no con el estado actual de `main`.
2. Se procesaron únicamente miembros regulares, sin nombres absolutos, `..` ni colisiones. Se confrontaron **los conjuntos** árbol/lista/paquetes/miembros/manifiestos/corridas/filas CSV. Se diferenciaron duplicados de ruta, hashes repetidos de archivos y hashes del PCM sin cabecera. Se comprobaron también los metadatos nativos disponibles, no sólo el índice generado por S5.
3. El recálculo independiente usó Python 3.11.2 y el venv ya existente (versiones en `entorno_auditor`), sin importar ningún módulo de la entrega. PCM: lectura de los chunks RIFF `fmt ` y `data`, FLOAT IEEE-754 little-endian intercalado. Estadísticas en float64: `RMS=sqrt(Σx²/N)`, pico=`max(abs(x))`, Pearson centrado, RMS y máximo de `L−R`, razón de niveles RMS. En TP4x se evaluaron los máximos de las cuatro fases de un FIR de 81 coeficientes: `g[k]=sinc((k−40)/4)·Kaiser81(β=5)[k]`, `h=4g/Σg`, k=0…80 (sinc normalizada) y cero fuera del archivo. Fue una medición puntual de pico, no un WAV remuestreado ni una medición normativa certificada.
4. Para cada par completo se comparó `SDV+SDI−Mix` **por canal y por índice**. Para los contrastes, resta directa entre archivos de igual forma, sin ajuste; sólo en S6 se permutó el eje canal de la referencia. Se midieron estadísticas directamente en los NPY, distinguiendo una dimensión física de canal de la difusión de un mapa. Para la RMS ponderada se usaron las energías de la STFT del Mix con su Hann periódica y padding por cero (2048 muestras a izquierda, hasta cubrir 175 tramas a derecha). Se comprobaron **todos** los valores de los 37 contrastes; además se contrastaron expresiones redondeadas y cotas en el informe.
5. Como comprobación puntual de asociación, no otra separación: a partir de las guías se evaluó Q en seis tramas (0,40,64,100,128,174) y nueve bins (40,41,42,81,82,83,122,123,124). En las rutas que calculan el mid de las guías (B/C `mono` y D) se evaluó esa proyección por linealidad de la DFT; no se creó audio mono. En diez índices del WAV se evaluó `Σ w[j]·irfft(X·M)[j]/Σw[j]²`, sobre las ventanas que cubren ese índice, análogamente para `1−M`. Los índices comunes y las diferencias máximas por corrida se conservan en el JSON, no los espectros ni cada sumando. No se sintetizó un stem, no se cambió la tasa ni se escribieron datos en ninguna entrada o salida. En el híbrido de dos pares la confianza leave-one-out es simétrica entre esos dos valores; esta simplificación del testigo no se extrapola a más pares.
6. `metrologia` documenta el número de comparaciones de campos/arrays, sus discrepancias máximas y las que exceden la tolerancia de recálculo. Unidades lineales en FS para audio, adimensionales para máscaras y correlaciones. Para identidades de canal se comprobó también cero exacto; para las guías L de Ronly se guardan los dos hashes de columna. Los contrastes no son tests de significancia ni hay un umbral de calidad musical.

**Receta de comprobación de los bytes**, desde la raíz del repositorio, sobre el SHA histórico (no escribe en la rama):

```sh
set -eu
S=c1ce9e29e15a9c5eb2789187097f94fc13cefaa0
T=$(mktemp -d)
git archive "$S" S5_STEREO_VALIDATION | tar -xf - -C "$T"
(cd "$T/S5_STEREO_VALIDATION" && sha256sum -c hashes/SHA256SUMS.txt --quiet)
mkdir "$T/miembros"
for p in "$T"/S5_STEREO_VALIDATION/evidence/*.tar.xz; do tar -xJf "$p" -C "$T/miembros"; done
(cd "$T/miembros" && sha256sum -c "$T/S5_STEREO_VALIDATION/hashes/MIEMBROS_SHA256.txt" --quiet)
# Sello NUEVO, distinto del anterior:
(cd S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE && sha256sum -c SHA256SUMS.txt)
```

Ejemplo mínimo para Cris: en ese temporal ya extraído, con NumPy y SoundFile disponibles, verificar el control central sin usar código de S5 ni ejecutar motores:

```sh
export T
python - <<'PY'
import json, os
from pathlib import Path
import numpy as np, soundfile as sf
p = Path(os.environ['T']); raw = p/'miembros'
for f in sorted((p/'S5_STEREO_VALIDATION/results').glob('s5_*.json')):
    d = json.loads(f.read_text()); runs = {r['id']:r for r in d['runs']}
    for mode in (['shared'] if d['block']=='D' else ['per_channel','mono']):
        a,b = runs['S2_'+mode], runs['Ronly_'+mode+'_unilateral']
        assert a['status']==b['status']=='OK' and a['inputs']['Mix']==b['inputs']['Mix']
        changed = {k for k in a['parsed_options'] if a['parsed_options'][k]!=b['parsed_options'][k]}
        assert changed=={'manifest','out'}
        for role,other in [('V','I'),('I','V')]:
            def guide(run,key):
                return sf.read(raw/run['inputs']['P1/'+key]['path'],dtype='float32',always_2d=True)[0]
            original,altered = guide(a,role),guide(b,role)
            assert original[:,0].tobytes()==altered[:,0].tobytes()
            assert guide(a,other)[:,1].tobytes()==altered[:,1].tobytes()
        def mask(run):
            return np.broadcast_to(np.load(raw/run['applied_mask'],allow_pickle=False),(2,2049,175))
        def wave(run,stem):
            return sf.read(raw/run['outputs'][stem]['path'],dtype='float64',always_2d=True)[0]
        delta = {k:np.sqrt(((wave(a,k)-wave(b,k))**2).mean(axis=0)) for k in ['SDV','SDI']}
        print(d['block'], mode, 'máx abs ΔM [L,R]:', abs(mask(a)-mask(b)).max(axis=(1,2)),
              'RMS ΔSDV [L,R]:', delta['SDV'], 'RMS ΔSDI [L,R]:', delta['SDI'])
PY
```

El verificador **original** `S5_STEREO_VALIDATION/scripts/verificar.py:165–168` enumera recursivamente los archivos de su directorio. Si se le pide verificar el directorio de la rama **después** de añadir esta auditoría encontrará archivos adicionales. Para evaluar el conjunto antiguo, usar el commit fijado; **no** usar `--sellar` para incorporar el subdirectorio al sello antiguo. Ningún hash viejo se actualizó.

### Vocabulario de decisión

`DOCUMENTED_FACT`: código, estructura o registro leído. `EXPERIMENTAL_RESULT`: medición reproducida sobre evidencia o traza observada, con su origen indicado. `THEORETICAL_DEDUCTION`: consecuencia razonada de la fórmula o del diseño. `HYPOTHESIS`: explicación o predicción todavía no aislada. `UNKNOWN`: sin observación suficiente. Una deducción o un comportamiento por código no se presenta como corrida nueva.

`CONFIRMADO`: evidencia directa del enunciado acotado. `CONFIRMADO CON LIMITACIONES`: válido dentro del alcance indicado. `NO CONFIRMADO`: explicación plausible, faltó el control discriminante. `CONTRADICHO`: código/datos incompatibles con la afirmación evaluada. `UNKNOWN`: no se midió o no existe evidencia apropiada. Independencia de esta revisión significa **procedimiento de medida independiente**, no una nueva institución ni un nuevo conjunto de audio.
