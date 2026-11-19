# Etapa 6F · Cierre correctivo experimental de atribución e integridad

Estado: implementación congelada **antes** de definir la reserva independiente,
y reserva ejecutada sin cambios posteriores de código ni de umbrales.
Base: `b72ce49ae787c72a1148bbec95db35dba460d279` (entrega 6E).
Rama de trabajo: `arena/89d5c189-sdv-sdi-sgm` (rama de sesión fija; ver
`INFORME_IMPLEMENTACION_6F.md` §1 para la desviación respecto del nombre de rama
pedido en el encargo). Ningún archivo fuera de esta carpeta se modifica.

## Resultado en una línea

Atribución 93/93 (desarrollo) y 84/84 (reserva); CLI 57/57 y 30/30; WAV 39/39 y
10/10; MQR S7 reproducido; DSP idéntico a 6E en 24/24 y a 6C en 23/24
(1 no comparable). Dictamen: **APROBADO CON LIMITACIONES**.

## Contenido

- `motores/`: copias experimentales 6F de Hardened, EVO y MQR, más los módulos
  nuevos `atribucion_6f.py` (atribución) y `wav_integridad_6f.py` (integridad
  RIFF/WAVE y lectura desde el mismo descriptor). Las copias se generan desde
  6E con `scripts/construir_motores_6f.py`; ningún archivo de 6C/6E/original se
  modifica.
- `scripts/`: estímulos, validaciones, auditorías, diagnóstico y consolidación.
- `evidence/`: resultados JSON/CSV reproducibles.
- Informes: `INFORME_IMPLEMENTACION_6F.md`, `INFORME_VALIDACION_INDEPENDIENTE_6F.md`,
  `AUDITORIA_CLI_6F.md`, `AUDITORIA_WAV_6F.md`, `DIAGNOSTICO_MQR_S7_6F.md`,
  `ANALISIS_ESTEREO_LR_6F.md`, `NO_REGRESION_DSP_6F.md`,
  `RECURSOS_Y_DURACIONES_6F.md`, `LIMITACIONES_Y_CASOS_UNKNOWN_6F.md`.
- Matrices: `MATRIZ_RESULTADOS_6F.csv`, `MATRIZ_CLI_6F.csv`, `MATRIZ_WAV_6F.csv`.
- `MANIFEST_6F.json` (commit base, rama, hashes de motores, módulos, scripts,
  fuentes protegidas, estímulos, resultados, entorno) y `SHA256SUMS.txt`.

## Ejecución reproducible

```sh
python -m venv /tmp/sdv6f-env
/tmp/sdv6f-env/bin/pip install -r requirements.txt

PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/construir_motores_6f.py --check
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/validar_dev_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/auditoria_wav_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/auditoria_cli_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/no_regresion_dsp_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/mqr_s7_6f.py
```

Después del congelamiento (reserva independiente, no usar para ajustar):

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/reserva_6f.py     # imprime y verifica la reserva
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/validar_reserva_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/consolidar_6f.py
```

Duraciones medidas: dev 15 s, WAV 0,2 s, CLI 41 s, DSP 67 s, S7 13 s,
reserva 37 s. Requiere BLAS/OpenMP en 1 hilo (`comun_6f.py` lo fija).

Para comprobar un expediente publicado sin regenerarlo:
`cd ETAPA_6F_CIERRE_CORRECTIVO && sha256sum -c SHA256SUMS.txt`.
`consolidar_6f.py` reescribe `MANIFEST_6F.json` y `SHA256SUMS.txt`; si se
ejecuta después de un commit, esos dos archivos cambian y deben commitearse.
