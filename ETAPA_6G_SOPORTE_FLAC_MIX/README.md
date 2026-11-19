# Etapa 6G · Soporte nativo WAV/FLAC para el Mix original

Base: `663fb5f8b4d53c8445d482ecec4df6a0208c59f0` (cierre 6F).
Rama: `arena/89d5c189-sdv-sdi-sgm` (rama de sesión; ver §1 del informe de
implementación para la desviación autorizada por el usuario).
Todo el trabajo vive en esta carpeta; 6C/6D/6E/6F, el motor v3 y `main` quedan
intactos.

## Qué hace

Los tres motores 6G aceptan el Mix original en **WAV** (validación estricta 6F,
sin cambios) o **FLAC** (validador propio), lo leen **directamente** desde el
mismo inodo validado y lo entregan al mismo DSP. No hay conversión, remuestreo,
downmix, normalización, ganancia, polaridad ni desplazamiento.

## Estructura

```
motores/    tres motores 6G + audio_integridad_6g.py + copias de
            atribucion_6f.py y wav_integridad_6f.py (esta última idéntica a 6F)
scripts/    fixtures, validaciones, TOCTOU, no regresión y consolidación
fixtures/   corpus sintético WAV/FLAC (mismas muestras) + variantes inválidas
evidence/   matrices CSV y resultados JSON
```

## Ejecución reproducible

```sh
python -m venv /tmp/sdv6g-env
/tmp/sdv6g-env/bin/pip install -r requirements.txt

cd ETAPA_6G_SOPORTE_FLAC_MIX
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/preparar_fixtures_6g.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/validar_contenedores_6g.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/validar_motores_6g.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/toctou_6g.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/no_regresion_dsp_6g.py
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6g-env/bin/python -B scripts/consolidar_6g.py
```

`consolidar_6g.py` regenera los diffs, `MANIFEST_6G.json` y `SHA256SUMS.txt`
(por eso debe ejecutarse al final y volver a commitearse si cambió algo).

Verificación de un expediente publicado:

```sh
cd ETAPA_6G_SOPORTE_FLAC_MIX && sha256sum -c SHA256SUMS.txt
```

Duración medida: fixtures ~1 s, contenedores 15.5 s, motores 17.8 s,
TOCTOU 0.4 s, no regresión 5.1 s. Hilos BLAS/OpenMP fijados a 1 por
`scripts/comun_6g.py`.

## Resultado

* Contenedores: módulo 13/13 y 13/13 en cada motor.
* Motores: 12/12 combinaciones motor×modo con salidas idénticas WAV vs FLAC
  (PCM, geometría, alineación e informe).
* TOCTOU: detectado en módulo y en los tres motores (abortan sin WAV ni informe).
* DSP: sólo cambian `probe_file` y `run_experiment` (validación y traza); PCM
  idéntico a 6F.

Detalle en `INFORME_IMPLEMENTACION_6G.md`, `INFORME_VALIDACION_6G.md` y
`NO_REGRESION_DSP_6G.md`.
