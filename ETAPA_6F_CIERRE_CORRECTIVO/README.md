# Etapa 6F · Cierre correctivo experimental de atribución e integridad

Estado: implementación congelada antes de definir la reserva independiente.
Base: `b72ce49ae787c72a1148bbec95db35dba460d279` (entrega 6E).
Rama de trabajo: `arena/89d5c189-sdv-sdi-sgm` (rama de sesión fija; ver
`INFORME_IMPLEMENTACION_6F.md` para la desviación respecto del nombre de rama
pedido en el encargo).

## Contenido

- `motores/`: copias experimentales 6F de Hardened, EVO y MQR, más los módulos
  nuevos `atribucion_6f.py` (atribución) y `wav_integridad_6f.py` (integridad
  RIFF/WAVE y lectura desde el mismo descriptor). Las copias se generan desde
  6E con `scripts/construir_motores_6f.py`; ningún archivo de 6C/6E/original se
  modifica.
- `scripts/`: estímulos de desarrollo, validación, auditorías y reproducción.
- `evidence/`: resultados JSON/CSV reproducibles.

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

La reserva independiente se ejecuta después del congelamiento:

```sh
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/validar_reserva_6f.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6f-env/bin/python -B scripts/consolidar_6f.py
```

Para comprobar un expediente publicado sin regenerarlo: `sha256sum -c SHA256SUMS.txt`.
