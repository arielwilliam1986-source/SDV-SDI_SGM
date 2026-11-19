"""Detección de sustitución entre validación y lectura (6G).

Dos pruebas:
A. Módulo: `open_audio` decodifica desde el mismo descriptor; si la ruta se
   reemplaza después de abrir, las muestras siguen siendo las validadas y
   `check_file_unchanged` detecta el cambio.
B. Motor: se sustituye el Mix justo después del sondeo (monkeypatch de
   `probe_file`) y se ejecuta `run_experiment` real; la guarda de cierre debe
   abortar con EXIT_PROCESSING y no debe dejar informe.
"""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import EV, HERE, MOT, MOTORES, Cronometro, dump, entorno

sys.path.insert(0, str(HERE / 'motores'))
import audio_integridad_6g as A

FIX = HERE / 'fixtures'
TRABAJO = Path('/tmp/f6g/toctou')


def cargar(motor):
    ruta = MOT / MOTORES[motor]
    spec = importlib.util.spec_from_file_location(f'motor_{motor}', ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f'motor_{motor}'] = mod
    spec.loader.exec_module(mod)
    return mod


def prueba_modulo():
    fuente = FIX / 'mix.flac'
    otro = FIX / 'mix_24bit.flac'
    destino = TRABAJO / 'modulo' / 'mix.flac'
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(fuente, destino)
    v = A.open_audio(str(destino))
    originales = v.samples.copy()
    ok_antes = A.check_file_unchanged(str(destino), v.digest, v.identity)
    shutil.copy(otro, destino)          # sustitución tras abrir
    tras_leer = np.array_equal(v.samples, originales)
    ok_despues = A.check_file_unchanged(str(destino), v.digest, v.identity)
    return dict(caso='modulo_open_audio',
                muestras_siguen_siendo_las_validadas=bool(tras_leer),
                intacto_antes=bool(ok_antes['unchanged']),
                sustitucion_detectada=bool(not ok_despues['unchanged']),
                detalle=ok_despues.get('reason'))


def prueba_motor(motor):
    mod = cargar(motor)
    trabajo = TRABAJO / motor
    trabajo.mkdir(parents=True, exist_ok=True)
    mix = trabajo / 'mix.flac'
    shutil.copy(FIX / 'mix.flac', mix)
    sustituto = FIX / 'mix_24bit.flac'   # mismo contenedor, contenido distinto

    original_probe = mod.probe_file

    def probe_y_sustituir(path, role):
        info = original_probe(path, role)
        if role == 'mix':
            shutil.copy(sustituto, path)   # cambia el contenido tras el sondeo
        return info

    mod.probe_file = probe_y_sustituir
    man = trabajo / 'manifest.json'
    man.write_text(json.dumps(dict(
        mix_original=str(mix),
        pairs=[dict(pair_id='P01', family='6G', variant='V01',
                    configuration='synthetic', source='synthetic',
                    vocal_path=str(FIX / 'vocal.wav'), vocal_guide=str(FIX / 'vocal.wav'),
                    instrumental_path=str(FIX / 'instrumental.wav'),
                    instrumental_guide=str(FIX / 'instrumental.wav'))])))
    parser = mod.build_arg_parser()
    opt = parser.parse_args(['--mode', 'full_processing', '--out', str(trabajo / 'out')])
    opt.manifest_path = str(man)
    devuelto = mod.load_manifest(str(man))
    pairs = devuelto[1]
    try:
        code, run_dir = mod.run_experiment(str(mix), pairs, 'full_processing', opt)
    finally:
        mod.probe_file = original_probe
    informes = list((trabajo / 'out').rglob('analysis.json'))
    wavs = list((trabajo / 'out').rglob('*.wav'))
    return dict(caso=f'motor_{motor}', exit=code,
                abortado=bool(code != 0),
                informes=len(informes), wavs=len(wavs),
                run_dir=str(run_dir))


def main():
    TRABAJO.mkdir(parents=True, exist_ok=True)
    with Cronometro() as cron:
        filas = [prueba_modulo()]
        for motor in MOTORES:
            try:
                filas.append(prueba_motor(motor))
            except Exception as exc:
                filas.append(dict(caso=f'motor_{motor}', exit=None,
                                  abortado=False, informes=0, wavs=0,
                                  error=f'{type(exc).__name__}: {exc}'))
    detectados = sum(1 for f in filas if f.get('abortado') or
                     f.get('sustitucion_detectada'))
    dump(EV / 'toctou_6g.json', dict(seconds=cron.seconds, entorno=entorno(), filas=filas,
                                     maxrss_kib=cron.maxrss_kib,
                                     resumen=dict(detectados=detectados, total=len(filas))))
    for f in filas:
        print(f)


if __name__ == '__main__':
    main()
