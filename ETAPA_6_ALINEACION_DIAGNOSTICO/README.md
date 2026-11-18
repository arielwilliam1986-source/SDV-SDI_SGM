# Etapa 6 · Diagnóstico de alineación temporal

**Leer primero el [informe y dictamen](INFORME_DIAGNOSTICO_ALINEACION.md).** La pregunta es por qué se declara un desplazamiento donde el generador no desplazó la guía respecto a su Mix. Es distinta de si la separación conserva dos canales o si `SDV+SDI` reconstruye el Mix.

**Estado:** diagnóstico y diseño documental en `arena/20d905c7-sdv-sdi-sgm`. Ejecutor: Arena.ai. Revisión: ChatGPT/Cris y Will. No se importó ni ejecutó ningún motor, no se generaron WAV, no se corrió una batería, no se modificaron fuentes, opciones, S5 ni su auditoría. La medición nueva consiste en releer datos S5 ya archivados. **No hay defecto declarado resuelto ni autorización de avance.**

| Entregable | Qué permite revisar |
|---|---|
| [INFORME_DIAGNOSTICO_ALINEACION.md](INFORME_DIAGNOSTICO_ALINEACION.md) | Dictamen, denominadores, seis testigos causales, diferencias B/C/D, alcance y límites de v3. |
| [MATRIZ_COMPARATIVA_DETECTORES.csv](MATRIZ_COMPARATIVA_DETECTORES.csv) | Una fila por original, 22 campos: señal, ventana, normalización, rango, signo, clase, errores y consumidor del offset. CSV UTF-8 con cabecera y comillas estándar. |
| [DEFECTOS_REPRODUCIBLES.json](DEFECTOS_REPRODUCIBLES.json) | 14 hallazgos auditables. X1–X3: mecanismos compartidos; H1–H2: Hardened; C1–C4: EVO; D1–D3: MQR; A1–A2: limitaciones del comparador. Incluye mediciones, referencias literales, cómo comprobar y qué no se ensayó. No son 14 fallos independientes observados en ejecución. |
| [DISENO_BATERIA_VALIDACION.md](DISENO_BATERIA_VALIDACION.md) | V00–V12: señales, retardos impuestos, oráculo por canal, casos no identificables, errores, aceptación y validación reservada. Ningún V fue ejecutado. |
| [PROPUESTA_CORRECCION_POR_MOTOR.md](PROPUESTA_CORRECCION_POR_MOTOR.md) | Contrato de estados y de evidencia; adaptación distinta por motor; qué no portar de A y qué no debe tocar la separación. |
| [RIESGOS_Y_REGRESIONES.md](RIESGOS_Y_REGRESIONES.md) | Riesgos, controles de signo/estéreo/política y comparación de máscaras y PCM antes de una eventual integración. |
| `README.md` · [SHA256SUMS.txt](SHA256SUMS.txt) | Guía de lectura y sello SHA-256 de los **siete** documentos, incluido el índice. El hash de la propia lista se comunica fuera de ella. |

## Evidencia fijada y vocabulario

**DOCUMENTED_FACT · CONFIRMADO.** Las referencias de código apuntan a los originales completos en `Proyecto SDV-SDI_SGM/` de la [base](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/b64f15ae8b28e46eef3c024dc62c85fe27c69494). Los SHA-256 individuales están en `fuentes` del expediente JSON. `A=v3` es sólo referencia; `B=Hardened Final`, `C=EVO`, `D=MQR`. Se contrastaron estas fuentes con los blobs ejecutados en S5. Ninguna coincidencia entre textos de informes se tomó por prueba de comportamiento.

- **S5**, [commit c1ce9e2](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/c1ce9e29e15a9c5eb2789187097f94fc13cefaa0/S5_STEREO_VALIDATION): [INFORME_S5](../S5_STEREO_VALIDATION/reports/INFORME_S5.md), [manifiesto de señales](../S5_STEREO_VALIDATION/signals/manifest.json), [generador](../S5_STEREO_VALIDATION/scripts/generador_sintetico.py), [punto de entrada real](../S5_STEREO_VALIDATION/scripts/pruebas_s5.py), `results/s5_*.json`, [índice de paquetes](../S5_STEREO_VALIDATION/evidence/index.json) y [SHA de miembros](../S5_STEREO_VALIDATION/hashes/MIEMBROS_SHA256.txt). Los `analysis.json` y la consola del aborto en los paquetes son evidencia primaria, no el nombre de una figura ni un valor de SNR.
- **Auditoría independiente**, [commit 9fc5fc9](https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/9fc5fc958942845b63e151c02671bbca08362e2b/S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE): [INFORME_AUDITORIA_S5](../S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/INFORME_AUDITORIA_S5.md) §E, [MATRIZ_EVIDENCIAS](../S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/MATRIZ_EVIDENCIAS.csv) E1–E4, [MATRIZ_MOTORES_ESTEREO](../S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/MATRIZ_MOTORES_ESTEREO.csv), [PRUEBAS_PENDIENTES](../S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/PRUEBAS_PENDIENTES.md) P2/P3 e [inventario de trazas](../S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/VERIFICACION_INTEGRIDAD.json). Usar `matriz.corridas["B/S2_per_channel"]` como ejemplo para resolver rutas y argumentos en el `results` correspondiente. No incluir el aborto entre los 42 éxitos B/C/D.
- **1B**, ya en la base: [diagnóstico histórico](../SDV-SDI_FASE_1B_ENTREGA/ALIGNMENT_DIAGNOSTICS.md), [código de su evaluación](../SDV-SDI_FASE_1B_ENTREGA/src/bloque_b.py), [control de identidad](../SDV-SDI_FASE_1B_ENTREGA/src/bloque_b_control.py), [filas históricas](../SDV-SDI_FASE_1B_ENTREGA/results/alineacion_casos.csv) y [control L/R](../SDV-SDI_FASE_1B_ENTREGA/results/alineacion_lr_asimetrico.json). No equiparar los resultados de auxiliares con el clasificador completo de EVO.

**Convenciones.** Las rutas del JSON son relativas a la **raíz** del repo; `archivo.tar.xz!miembro` nombra el miembro exacto (sin `build/`), `#Lx-Ly` un tramo de fuente. Dentro de los CSV o prosa `X:n–m` son líneas del original X. `k` es el lag nativo, `d` el retardo de la guía, `ρ` el Pearson de la onda, RMS en FS. Cuidado: la etiqueta de fixture **S5** (retardo del contenido de R) no es el nombre de una versión de motor. En las tablas B/C/D `±1` **muestra** no es `±1` **ms**.

**Clase y dictamen son dos ejes.** `DOCUMENTED_FACT` = contenido comprobado de código o documento; `EXPERIMENTAL_RESULT` = registro medido o cálculo sobre PCM identificado; `THEORETICAL_DEDUCTION` = consecuencia de índices o fórmulas; `HYPOTHESIS` = propuesta o explicación aún sin control; `UNKNOWN` = no hay evidencia apropiada. `CONFIRMADO` y `CONFIRMADO CON LIMITACIONES` se refieren al enunciado acotado, no a una solución; `NO CONFIRMADO` indica que falta demostrarlo; `CONTRADICHO` evalúa una interpretación explícita refutada por los datos; `UNKNOWN` no equivale a fallo ni aprobación. En los documentos de diseño la etiqueta al inicio de cada tabla/sección se aplica a todas sus propuestas salvo indicación distinta.

## Verificación pasiva, sin ejecutar el proyecto

Desde la raíz del checkout, la comprobación de integridad no requiere dependencias de audio:

```sh
(cd ETAPA_6_ALINEACION_DIAGNOSTICO && sha256sum -c SHA256SUMS.txt && sha256sum SHA256SUMS.txt)
```

**Ejemplo para Cris/Will: verificar S2/I en los bytes publicados**, con Python, NumPy y SoundFile disponibles. No extrae archivos al disco, no importa los motores, no desplaza señal: los slices sólo delimitan los índices que se comparan. El campo `testigos_pcm.lecturas` contiene los otros controles y ambos niveles del correlador. Para replicar el grueso, evaluar la NCC en todos los bins válidos con los límites del motor (detallados en el informe), no sólo en los dos puntos de este ejemplo.

```python
import hashlib, io, json, subprocess, tarfile
import numpy as np, soundfile as sf
S = 'c1ce9e29e15a9c5eb2789187097f94fc13cefaa0'
P = 'S5_STEREO_VALIDATION/'
def blob(path):
    return subprocess.check_output(['git', 'show', S + ':' + P + path])
hashes = dict(line.split('  ', 1)[::-1] for line in blob('hashes/MIEMBROS_SHA256.txt').decode().splitlines())
def archived(package, member):
    with tarfile.open(fileobj=io.BytesIO(blob('evidence/' + package + '.tar.xz')), mode='r:xz') as tar:
        data = tar.extractfile(member).read()
    assert hashlib.sha256(data).hexdigest() == hashes[member]
    return data
with open('ETAPA_6_ALINEACION_DIAGNOSTICO/DEFECTOS_REPRODUCIBLES.json', encoding='utf-8') as f:
    witnesses = json.load(f)['testigos_pcm']['lecturas']
w = next(r for r in witnesses if (r['caso'],r['rol']) == ('S2','I'))
raw = json.loads(archived('S5-D', w['por_motor']['D']['primaria'].split('!', 1)[1]))
r = next(row for row in raw['alignment'] if row['role'] == 'instrumental')
x,g = [sf.read(io.BytesIO(archived('inputs','inputs/S2/'+name+'.wav')),
               dtype='float64', always_2d=True)[0].mean(axis=1) for name in ('Mix','I')]
def pearson(k):
    l, h = max(0,k), min(len(x),len(g)+k)
    a, b = x[l:h], g[l-k:h-k]
    a, b = a-a.mean(), b-b.mean()
    return (a @ b) / np.sqrt((a @ a)*(b @ b))
c = r['coarse_lag_samples']
k = max(range(c-12,c+13), key=pearson)
print(c, k, round(pearson(0),6), round(pearson(k),6), r['classification'])
# -1224 -1212 0.848408 0.301035 MISALIGNED
```

**Parada:** revisar los hallazgos y las condiciones de aceptación. No iniciar el protocolo V00–V12, un parche ni pruebas musicales sin autorización expresa de Cris y Will.
