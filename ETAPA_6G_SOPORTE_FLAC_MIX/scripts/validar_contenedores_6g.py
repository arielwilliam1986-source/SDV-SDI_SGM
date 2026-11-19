"""Valida el corpus de contenedores 6G en dos capas.

Capa módulo: `audio_integridad_6g.verify_audio` (contenedor e integridad).
Capa motor: CLI real en `dry_run` (aceptación/rechazo de la entrada Mix).

Un exit code por sí solo no se considera prueba: se registran WAV, informe y
mensaje de error. Las expectativas de tasa/canales pertenecen al motor, no al
validador de contenedor (se documenta esa diferencia).
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import EV, HERE, MOT, MOTORES, Cronometro, dump, ejecutar, entorno

sys.path.insert(0, str(HERE / 'motores'))

FIX = HERE / 'fixtures'
SR = 44100

# (caso, archivo, esperado módulo, esperado motor, motivo)
CASOS = [
    ('wav_valido', 'mix.wav', 'ACEPTA', 'ACEPTA', 'WAV PCM_16 estricto'),
    ('flac_valido', 'mix.flac', 'ACEPTA', 'ACEPTA', 'FLAC PCM_16'),
    ('wav_24bit', 'mix_24bit.wav', 'ACEPTA', 'ACEPTA', 'WAV PCM_24'),
    ('flac_24bit', 'mix_24bit.flac', 'ACEPTA', 'ACEPTA', 'FLAC PCM_24'),
    ('wav_como_flac', 'wav_renombrado_flac.flac', 'RECHAZA', 'RECHAZA',
     'contenedor WAV con extensión .flac'),
    ('flac_como_wav', 'flac_renombrado_wav.wav', 'RECHAZA', 'RECHAZA',
     'contenedor FLAC con extensión .wav'),
    ('flac_truncado', 'flac_truncado.flac', 'RECHAZA', 'RECHAZA', 'FLAC cortado'),
    ('flac_corrupto', 'flac_corrupto.flac', 'RECHAZA', 'RECHAZA',
     'frames FLAC alterados'),
    ('flac_sin_audio', 'flac_sin_audio.flac', 'RECHAZA', 'RECHAZA',
     'solo metadatos, sin frames'),
    ('flac_48k', 'mix_48k.flac', 'ACEPTA', 'RECHAZA',
     'contenedor válido; tasa no admitida es política del motor'),
    ('flac_3ch', 'flac_3ch.flac', 'ACEPTA', 'RECHAZA',
     'contenedor válido; 3 canales fuera de rango del motor'),
    ('wav_nan', 'mix_nan.wav', 'RECHAZA', 'RECHAZA', 'muestras no finitas'),
    ('otro_formato', 'mp3_renombrado.flac', 'RECHAZA', 'RECHAZA',
     'contenedor OGG/otro con extensión .flac'),
]


def capa_modulo():
    import audio_integridad_6g as A
    filas = []
    for caso, archivo, esperado, _motor, motivo in CASOS:
        p = FIX / archivo
        try:
            r = A.verify_audio(str(p), None)
            obs, detalle = 'ACEPTA', f"container={r['container']}"
            spec = r['spec']
            detalle += f" rate={getattr(spec, 'rate', None)}" \
                       f" ch={getattr(spec, 'channels', None)}" \
                       f" frames={getattr(spec, 'frames', None)}"
            if r.get('md5_checked') is not None:
                detalle += f" md5_checked={r['md5_checked']}"
        except Exception as exc:
            obs, detalle = 'RECHAZA', f'{type(exc).__name__}: {exc}'
        filas.append(dict(capa='modulo', motor='-', caso=caso, archivo=archivo,
                          esperado=esperado, observado=obs, exit='-', wavs='-',
                          report='-', detalle=detalle, motivo=motivo,
                          verdict='PASS' if obs == esperado else 'FAIL'))
    return filas


def capa_motores(trabajo):
    filas = []
    rutas_base = dict(vocal=str(FIX / 'vocal.wav'),
                      instrumental=str(FIX / 'instrumental.wav'))
    for motor in MOTORES:
        for caso, archivo, _mod, esperado, motivo in CASOS:
            mix = dict(rutas_base, mix=str(FIX / archivo))
            work = trabajo / f'{motor}_{caso}'
            r = ejecutar(motor, mix, work, 'dry_run')
            obs = 'ACEPTA' if r['exit'] == 0 else 'RECHAZA'
            detalle = (r['stderr_tail'].strip().splitlines() or [''])[-1][:200]
            ok = obs == esperado and (obs == 'ACEPTA' or
                                      (r['wavs'] == 0 and not r['report']))
            filas.append(dict(capa='motor', motor=motor, caso=caso, archivo=archivo,
                              esperado=esperado, observado=obs, exit=r['exit'],
                              wavs=r['wavs'], report=str(r['report']),
                              detalle=detalle, motivo=motivo,
                              verdict='PASS' if ok else 'FAIL'))
    return filas


def main():
    trabajo = Path('/tmp/f6g/contenedores')
    with Cronometro() as c:
        filas = capa_modulo() + capa_motores(trabajo)
    resumen = {}
    for f in filas:
        k = f['capa'] if f['capa'] == 'modulo' else f['motor']
        ok, tot = resumen.get(k, (0, 0))
        resumen[k] = (ok + (f['verdict'] == 'PASS'), tot + 1)
    EV.mkdir(exist_ok=True)
    with (EV / 'matriz_contenedores_6g.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    dump(EV / 'contenedores_6g.json', dict(
        seconds=c.seconds, maxrss_kib=c.maxrss_kib, entorno=entorno(),
        resumen={k: dict(ok=v[0], total=v[1]) for k, v in resumen.items()},
        filas=filas))
    for k, v in resumen.items():
        print(f'{k}: {v[0]}/{v[1]}')
    fallos = [f for f in filas if f['verdict'] == 'FAIL']
    for f in fallos:
        print('FALLA', f['motor'], f['caso'], f['esperado'], f['observado'],
              f['exit'], f['detalle'][:120])


if __name__ == '__main__':
    main()
