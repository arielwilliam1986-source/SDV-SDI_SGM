"""Estímulos sintéticos 6G: mismas muestras PCM para WAV y FLAC.

Sin canciones ni material del piloto. Se usan enteros PCM_16 para que la
equivalencia WAV/FLAC sea verificable bit a bit tras la decodificación.
"""
import numpy as np
import soundfile as sf

SR = 44100
SEED = 618033


def fuentes(segundos=2.0, seed=SEED, amp=6000):
    """Devuelve (vocal, instrumental, mix) como int16 intercalados."""
    n = int(segundos * SR)
    rng = np.random.default_rng(seed)
    v = rng.integers(-amp, amp, (n, 2)).astype('int16')
    i = rng.integers(-amp, amp, (n, 2)).astype('int16')
    mix = np.clip(v.astype('int32') + i.astype('int32'), -32768, 32767).astype('int16')
    return v, i, mix


def escribir(path, datos, sr=SR, subtype='PCM_16'):
    sf.write(str(path), np.asarray(datos), sr, subtype=subtype)
    return str(path)


def escribir_wav(path, datos, sr=SR, subtype='PCM_16'):
    return escribir(path, datos, sr, subtype)


def escribir_flac(path, datos, sr=SR, subtype='PCM_16'):
    return escribir(path, datos, sr, subtype)


def escribir_tres(base, segundos=2.0, seed=SEED):
    """vocal/mezcla/instru en WAV PCM_16 y el Mix también en FLAC."""
    v, i, mix = fuentes(segundos, seed)
    rutas = dict(
        vocal=escribir_wav(base / 'vocal.wav', v),
        instrumental=escribir_wav(base / 'instrumental.wav', i),
        mix_wav=escribir_wav(base / 'mix.wav', mix),
        mix_flac=escribir_flac(base / 'mix.flac', mix),
    )
    return rutas, dict(vocal=v, instrumental=i, mix=mix)


def corromper_flac(origen, destino, desde=None, largo=64):
    """Voltea bytes dentro de los frames de audio (después de los metadatos)."""
    data = bytearray(open(origen, 'rb').read())
    if desde is None:
        desde = len(data) // 2
    for k in range(desde, min(desde + largo, len(data))):
        data[k] ^= 0xA5
    open(destino, 'wb').write(bytes(data))
    return str(destino)


def truncar(origen, destino, fraccion=0.5):
    data = open(origen, 'rb').read()
    corte = max(8, int(len(data) * fraccion))
    open(destino, 'wb').write(data[:corte])
    return str(destino)


def casos_invalidos(base, rutas_ok):
    """Corpus de rechazos exigidos por el encargo (§8)."""
    import shutil
    casos = []
    mix_wav, mix_flac = rutas_ok['mix_wav'], rutas_ok['mix_flac']

    p = base / 'wav_renombrado_flac.flac'
    shutil.copy(mix_wav, p)
    casos.append(('wav_como_flac', str(p), 'WAV con extensión .flac'))

    p = base / 'flac_renombrado_wav.wav'
    shutil.copy(mix_flac, p)
    casos.append(('flac_como_wav', str(p), 'FLAC con extensión .wav'))

    p = base / 'flac_truncado.flac'
    truncar(mix_flac, p)
    casos.append(('flac_truncado', str(p), 'FLAC cortado a la mitad'))

    p = base / 'flac_corrupto.flac'
    corromper_flac(mix_flac, p)
    casos.append(('flac_corrupto', str(p), 'frames FLAC alterados'))

    p = base / 'mix_48k.flac'
    x, _ = sf.read(mix_flac, dtype='int16', always_2d=True)
    sf.write(str(p), x, 48000, subtype='PCM_16')
    casos.append(('flac_48k', str(p), 'sample rate 48000 no admitido'))

    p = base / 'flac_3ch.flac'
    tri = np.repeat(x[:, :1], 3, axis=1)
    sf.write(str(p), tri, SR, subtype='PCM_16')
    casos.append(('flac_3ch', str(p), '3 canales no admitidos'))

    p = base / 'mp3_renombrado.flac'
    cod = bytearray(open(mix_flac, 'rb').read())
    cod[0:4] = b'OggS'
    open(p, 'wb').write(bytes(cod))
    casos.append(('otro_formato_como_flac', str(p), 'contenedor no FLAC'))

    return casos


def caso_nan(base):
    """WAV float con NaN: el formato permite representarlo; FLAC no."""
    x = np.zeros((SR, 2), dtype='float32')
    x[:SR // 2, 0] = 0.1
    x[SR // 2, 0] = np.nan
    p = base / 'mix_nan.wav'
    sf.write(str(p), x, SR, subtype='FLOAT')
    return str(p)
