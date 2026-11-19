"""Fixtures sintéticos de la Etapa 6G.1 (sin canciones reales).

El Mix es la suma de dos componentes sintéticas (vocal + instrumental); las
guías son esas mismas componentes. Así la alineación y las máscaras se pueden
verificar de forma reproducible. Se generan WAV y FLAC con el mismo PCM, más
sustitutos válidos (FLAC 24 bits y FLAC/WAV con otro PCM).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf

HERE = Path(__file__).resolve().parent.parent
FIX = HERE / 'fixtures'
SR = 44100
BITS = 'PCM_16'


def _sha(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            m.update(b)
    return m.hexdigest()


def _componente(segundos, semilla, f0):
    """Componente estéreo de banda ancha (tono + ruido filtrado por tramos)."""
    rng = np.random.default_rng(semilla)
    n = int(round(segundos * SR))
    t = np.arange(n) / SR
    ch = []
    for c in range(2):
        ruido = rng.standard_normal(n)
        # suavizado simple: ruido de banda limitada (correlación temporal)
        k = np.ones(17) / 17.0
        ruido = np.convolve(ruido, k, mode='same')
        env = 0.4 + 0.6 * np.exp(-((t - segundos * (0.25 + 0.3 * c)) ** 2)
                                 / (0.05 + segundos / 8.0))
        x = env * (0.5 * np.sin(2 * np.pi * f0 * (1 + 0.1 * c) * t)
                   + 1.8 * ruido)
        ch.append(x)
    x = np.stack(ch, axis=1)
    return x / (np.max(np.abs(x)) or 1.0)


def _cuantizar(x, pico=0.9):
    return np.round(pico * x / (np.max(np.abs(x)) or 1.0) * 32767.0).astype(np.int16)


def _escribir(path, pcm, subtipo=BITS):
    sf.write(str(path), pcm, SR, subtype=subtipo, format=path.suffix[1:].upper())


def _par(segundos, semilla_v, semilla_i, base):
    """Genera Mix (suma) y guías, en WAV y FLAC, con PCM idéntico por formato."""
    v = _componente(segundos, semilla_v, 233.0)
    i = _componente(segundos, semilla_i, 117.0)
    mix = 0.6 * v + 0.6 * i
    pcm_mix = _cuantizar(mix)
    pcm_v = _cuantizar(v)
    pcm_i = _cuantizar(i)
    rutas = {}
    for nombre, pcm in ((f'{base}.wav', pcm_mix), (f'{base}.flac', pcm_mix),
                        (f'vocal_{base}.wav', pcm_v),
                        (f'instrumental_{base}.wav', pcm_i)):
        _escribir(FIX / nombre, pcm)
        rutas[nombre] = pcm
    return dict(base=base, segundos=segundos, frames=int(pcm_mix.shape[0]),
                pcm_sha256_mix=_sha(FIX / f'{base}.wav'),
                guias=dict(vocal=f'vocal_{base}.wav',
                           instrumental=f'instrumental_{base}.wav'))


def main():
    FIX.mkdir(parents=True, exist_ok=True)
    grupos = {}
    grupos['corto'] = _par(2.0, 11, 12, 'mix')
    grupos['largo'] = _par(12.0, 21, 22, 'mix_12s')

    # sustitutos válidos con otro PCM (mismo contenedor que el Mix original)
    for nombre, subtipo, semilla in (('mix_24bit.flac', 'PCM_24', 303),
                                     ('mix_otro.flac', BITS, 404),
                                     ('mix_otro.wav', BITS, 505)):
        otro = _componente(2.0, semilla, 311.0)
        _escribir(FIX / nombre, _cuantizar(otro), subtipo)
        grupos.setdefault('sustitutos', {})[nombre] = dict(
            subtype=subtipo, sha256=_sha(FIX / nombre))

    detalle = {}
    for p in sorted(FIX.glob('*')):
        if p.suffix.lower() not in ('.wav', '.flac'):
            continue
        info = sf.info(str(p))
        detalle[p.name] = dict(bytes=p.stat().st_size, frames=int(info.frames),
                               sr=int(info.samplerate), channels=int(info.channels),
                               subtype=info.subtype, format=info.format,
                               sha256=_sha(p))
    (FIX / 'fixtures_manifest.json').write_text(json.dumps(
        dict(schema='fixtures-6g1/1', sr=SR, generado_por='scripts/preparar_fixtures_6g1.py',
             grupos=grupos, archivos=detalle), indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8')
    print(json.dumps({k: v['sha256'][:16] for k, v in detalle.items()}, indent=2))
    print('fixtures:', len(detalle))


if __name__ == '__main__':
    main()
