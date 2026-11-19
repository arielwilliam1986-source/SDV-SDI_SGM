# Etapa 6D · Expediente de auditoría independiente

**Empiece por el [informe y sus ocho respuestas](INFORME_AUDITORIA_6D.md).** B = Hardened, C = EVO, D = MQR. A/v3 sólo fue custodiado. La unidad de verdad es **caso / rol (vocal o instrumental) / canal**. `d>0` = guía tardía, `k=−d`. Candidato, medición publicada, admisión, ejecución de DSP y validación final son cosas distintas. Los casos nuevos son sintéticos. Esta carpeta no instala cambios en los motores.

| Pregunta | Documento | Evidencia que permite refutar la conclusión |
|---|---|---|
| ¿Se reproducen los tres fallos de 6C? | [Reproducción de ambigüedades](REPRODUCCION_AMBIGUEDADES.md) | [Verdad de composición](evidence/verdad_doble_origen.json), [todas las propuestas](evidence/candidatos_A.csv), [arrays de todos los lags](evidence/curvas/) |
| ¿Qué decide cada versión en entradas conocidas y reservadas? | [Por motor](ANALISIS_POR_MOTOR.md), [estéreo L/R](ANALISIS_ESTEREO_LR.md) | [Banco](BANCO_RESERVADO_MANIFEST.json), [WAV con componentes](evidence/banco_6d.tar.xz), [oráculo PCM](evidence/oraculo_pcm.json), [matriz](MATRIZ_RESULTADOS_6D.csv), [estratos](evidence/desglose.json) |
| ¿Qué llega al procesamiento y con qué permiso? | [Auditoría CLI](AUDITORIA_CLI.md) | [Índice de 154 ejecuciones](evidence/cli_index.json), [decisión por caso](evidence/cli_por_caso.csv), [controles adicionales](evidence/extra_raw.json.gz), [inventario y bordes](evidence/bordes_cli.json.gz) |
| ¿Se tocó el audio? ¿Por qué aborta S7? | [Paridad física](NO_REGRESION_6D.md), [diagnóstico S7](MQR_S7_DIAGNOSTICO.md) | [Índice de 20 parejas](evidence/dsp_index.json), primarios `evidence/dsp_{B,C,D}.json.gz` |
| ¿Cuánto costó y qué queda sin medir? | [Recursos y protocolo Termux](RECURSOS_Y_DURACIONES.md) | [Índice](evidence/resources_index.json), [monitor completo](evidence/resources_raw.json.gz), [coste pareado del detector](evidence/coste_detector.json.gz) |
| ¿Qué estuvo congelado? | [Plan previo](PLAN_DE_PRUEBAS.md), [originales](source_hashes.json), [copias](experimental_hashes.json), [entorno](environment.json) | [Preflight](evidence/preflight.json), [postflight](evidence/postflight.json), [recreación limpia](evidence/reproduccion_limpia.json), [QA](evidence/control_calidad.json), [sello](SHA256SUMS.txt) |

## Leer sin ejecutar un motor

Desde la raíz del repositorio (los SHA del sello son relativos a esta carpeta):

```sh
N=ETAPA_6D_AUDITORIA_INDEPENDIENTE
(cd "$N" && sha256sum -c SHA256SUMS.txt)
python -B "$N/scripts/sello.py"  # verifica también que no falten ni sobren entradas
python -B -m unittest discover -v -s "$N/tests"
```

Los 11 tests leen la evidencia, incluidos contraejemplos; **no** son un `PASS` de aptitud. [Salida guardada](evidence/tests.log). Los JSON `.gz` de esta etapa contienen un documento JSON por archivo, no JSON Lines. Ejemplo mínimo sin dependencias científicas:

```sh
python - <<'PY'
import gzip, json
p='ETAPA_6D_AUDITORIA_INDEPENDIENTE/evidence'
r=next(x for x in json.load(gzip.open(p+'/det_B_6C.json.gz')) if x['id']=='R_dos_origenes')
for ch,v in r['raw']['vocal']['channels'].items():
    w=v['windows'][0]
    print(ch, 'candidato d:',w['best']['d'],'publicado:',v['guide_delay_samples'],v['classification'])
PY
```

**Diccionario de la matriz.** 504 filas, 49 columnas. `particion`: 6B (13 testigos), A_6C (2 réplicas), DEV (2), RESERVA (25). `d_verdad` queda vacío cuando no hay origen único o hay error; `alternativas_d` conserva hipótesis, no un intervalo de confianza. Para `circular` se dan representantes de una clase periódica, no un período con origen absoluto. `*_original_*rol` es el retorno escalar **real** de la versión original sobre la misma entrada; `coincidencia_numerica_original` no convierte una identidad impuesta en evidencia. Las listas por ventana son JSON dentro de CSV. La mejor propuesta puede tener ρ y solape aunque la decisión de canal sea nula. `conf_publicada` tampoco es una probabilidad. `k_comun` y `clase_rol` son globales del rol, no de todo el archivo/ejecución. `cli_default_*` pertenece al **caso completo** y se repite para facilitar el cruce; vacío = no ejecutado/no aplicable (p. ej. CLI principal de los testigos 6B), nunca exit 0. Distinguir `False` de vacío. La columna `primario` identifica archivo y clave, no un número de línea comprimida. Mirar las particiones por separado.

**Primarios.** `det_{B,C,D}_{original,6C}.json.gz`: fuente/entrada por SHA, preflight y retornos completos. `cli_*.json.gz`, `dsp_*.json.gz` y `extra_raw.json.gz`: comando/argv, manifiesto y configuración cuando proceden, stdout/stderr, observaciones, informes nativos textuales, inventarios y huellas. Las rutas temporales en argv son evidencia de ejecución, no archivos que deban sobrevivir: los scripts reconstruyen su contenido. [Índice de incidencias de los motores](ERRORES_Y_EXCEPCIONES.log) y [de la instrumentación](evidence/incidencias_instrumentacion.log). Las curvas `npz` se comparten sólo tras cotejar **exactamente** el slice por motor. Para volcar todos los bins/solapes usar [curvas_a.py](scripts/curvas_a.py). `build/` es temporal y está excluido; los tar.xz de entrada, no ese directorio, son la referencia de bytes.

## Reproducir las mediciones sin sobrescribir la entrega

**DOCUMENTED_FACT.** Se necesita el repositorio con los objetos históricos 6B y 6C y sus archivos custodiados, Python 3.11, NumPy, SciPy y SoundFile/libsndfile. No se importa un harness antiguo para generar el banco 6D o ejecutar `analyze_alignment`; sí se usan manifiestos, archivos y etiquetas históricos como referencias declaradas. Las salidas de los motores no entrenan el oráculo. [Paquetes del entorno medido](requirements.txt). Conviene utilizar un venv externo. Por ejemplo en Linux, desde la raíz:

```sh
N=ETAPA_6D_AUDITORIA_INDEPENDIENTE
V=$(mktemp -d); python3.11 -m venv "$V/venv"; PY="$V/venv/bin/python"
"$PY" -m pip install -r "$N/requirements.txt"
export SDV6D_OUT=$(mktemp -d)       # sólo productos NUEVOS; no apuntar al expediente sellado
set -e
for step in preflight bank origenes oraculo_pcm detect cli dsp controles bordes_cli testigos_cli_original; do
  "$PY" -Bu "$N/scripts/$step.py"
done
"$PY" -Bu "$N/scripts/resources.py"             # monitor liviano; incluye los dry-run dispersos
"$PY" -Bu "$N/scripts/coste_detector.py"         # experimento separado, con tracemalloc
"$PY" -Bu "$N/scripts/consolidar.py"
"$PY" -Bu "$N/scripts/verificar.py"
"$PY" -B -m unittest discover -v -s "$N/tests"
"$PY" -Bu "$N/scripts/replicar.py"
```

El preflight lee archivos comprimidos que representan >4 GB históricos y restaura sólo la selección necesaria. El ensayo de recursos grande crea **temporalmente** 13 archivos lógicos de >1 GiB y salidas adicionales en otras duraciones: verificar espacio libre y soporte del sistema de archivos antes de ejecutarlo. No hay un límite artificial de memoria. `resources.py --monitor-en-padre` reproduce el procedimiento **piloto** separado; no es necesario para regenerar la serie formal. `medir.py` permite usar el monitor sobre una sola CLI sin tener instalado `/usr/bin/time`. El protocolo local ARM64 se detalla en su documento y **no se da por ejecutado**.

**Resultados deterministas vs observaciones.** El manifiesto, el TAR nuevo, la reconstrucción, el desglose y la matriz se recrearon en una raíz temporal: [11 productos con SHA idéntico](evidence/reproduccion_limpia.json). Ésta es repetición del banco/oráculo y de los derivados desde primarios; no es otra ejecución de todas las CLI. Una nueva CLI puede variar hora, nombres de temporales, cabeceras, duración y RSS. Comparar campos físicos y procedencia, no exigir SHA de dos informes con timestamp distinto. No cambiar umbrales si aparece una discrepancia. Se conservó la primera serie de recursos y la razón del cambio de monitor.

**Etiquetas.** `DOCUMENTED_FACT`: código, trazabilidad o hecho documental; `EXPERIMENTAL_RESULT`: medición; `THEORETICAL_DEDUCTION`: consecuencia razonada, no una corrida adicional; `HYPOTHESIS`: explicación/ensayo por contrastar; `UNKNOWN`: falta evidencia. `CONFIRMADO` se limita al enunciado y alcance ensayado, `PARCIALMENTE CONFIRMADO` separa casos favorables y contrarios, `NO REPRODUCIDO` no demuestra imposibilidad, `REGRESIÓN` exige comparación contra un original, `UNKNOWN` no es fallo ni éxito.

Para entregar una copia portátil a otra persona sin publicar nada ni incluir `build/`, desde la raíz: `tar --exclude=build --exclude=__pycache__ -czf /tmp/expediente-6D.tar.gz ETAPA_6D_AUDITORIA_INDEPENDIENTE`. El destinatario puede comprobar `SHA256SUMS.txt` sin ejecutar las CLI; la reproducción de históricos requiere además los commits indicados.

**Publicación.** Sólo se añadieron entregables bajo esta carpeta de la rama activa asignada por la sesión. No se creó una rama distinta, no se hizo push/PR, no se modificó `main`, v3, los otros originales ni las copias o históricos sellados. No hay autorización de promoción, canciones reales ni fase posterior.