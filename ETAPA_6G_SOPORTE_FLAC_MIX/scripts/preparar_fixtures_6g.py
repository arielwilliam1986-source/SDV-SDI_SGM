"""Genera el corpus sintético 6G en `fixtures/` (determinista).

Mismas muestras PCM para WAV y FLAC. Ningún archivo del piloto ni comercial.
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import HERE, dump, sha_file
from estimulos_6g import (SR, caso_nan, casos_invalidos, corromper_flac,
                          escribir_wav, escribir_flac, fuentes, truncar)

FIX = HERE / 'fixtures'


def main():
    FIX.mkdir(exist_ok=True)
    v, i, mix = fuentes(1.0)
    rutas = dict(
        vocal=escribir_wav(FIX / 'vocal.wav', v),
        instrumental=escribir_wav(FIX / 'instrumental.wav', i),
        mix_wav=escribir_wav(FIX / 'mix.wav', mix),
        mix_flac=escribir_flac(FIX / 'mix.flac', mix),
    )
    # variantes de profundidad y tasa
    escribir_flac(FIX / 'mix_24bit.flac', mix, subtype='PCM_24')
    escribir_wav(FIX / 'mix_24bit.wav', mix, subtype='PCM_24')

    casos = casos_invalidos(FIX, rutas)
    nan_wav = caso_nan(FIX)
    casos.append(('wav_nan', nan_wav, 'muestras no finitas (FLOAT WAV)'))

    # FLAC solo con metadatos (sin frames de audio)
    data = open(rutas['mix_flac'], 'rb').read()
    corte = data.find(b'\xff\xf8')
    if corte > 0:
        p = FIX / 'flac_sin_audio.flac'
        open(p, 'wb').write(data[:corte])
        casos.append(('flac_sin_audio', str(p), 'FLAC sin frames de audio'))

    manifiesto = dict(
        sr=SR, seed=618033, frames=int(len(mix)),
        validos={k: dict(path=str(Path(p).name), sha256=sha_file(p))
                 for k, p in rutas.items()},
        validos_extra={p.name: sha_file(p) for p in
                       (FIX / 'mix_24bit.flac', FIX / 'mix_24bit.wav')},
        invalidos=[dict(caso=c, path=Path(p).name, sha256=sha_file(p), nota=n)
                   for c, p, n in casos],
    )
    dump(HERE / 'fixtures' / 'fixtures_manifest.json', manifiesto)
    print('fixtures:', len(list(FIX.glob('*'))) - 1, 'archivos')
    for c, p, n in casos:
        print(' ', c, Path(p).name)


if __name__ == '__main__':
    main()
