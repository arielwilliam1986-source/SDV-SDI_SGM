"""Mediciones sobre los WAV releídos, no sobre un downmix ni sobre métricas del motor."""
import hashlib
import json
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'build'
SR, N = 44100, 176400


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def load(path):
    def invalid(token):
        raise ValueError(f'{path}: constante no JSON: {token}')
    return json.loads(path.read_text(encoding='utf-8'), parse_constant=invalid)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    x, sr = sf.read(path, dtype='float64', always_2d=True)
    if sr != SR or x.shape != (N, 2) or sf.info(path).subtype != 'FLOAT':
        raise ValueError(f'Geometría o formato inesperado: {path}, {sr}, {x.shape}, {sf.info(path).subtype}')
    return x


def rms(x, axis=0):
    return np.sqrt(np.mean(np.square(x), axis=axis))


def difference(x, y):
    if x.shape != y.shape:
        raise ValueError('No se recortan ni realinean arrays para compararlos')
    d = x - y
    return dict(rms=rms(d).tolist(), max_abs=np.max(np.abs(d), axis=0).tolist())


def wav_stats(path):
    x = read(path)
    info = sf.info(path)
    counts = (~np.isfinite(x)).sum(axis=0).tolist()
    data = dict(path=path.relative_to(WORK).as_posix(), sha256=sha(path.read_bytes()),
                pcm_f32le_sha256=sha(x.astype('<f4').tobytes()), sr=info.samplerate,
                channels=info.channels, frames=info.frames, seconds=info.duration,
                subtype=info.subtype, nonfinite=counts)
    if any(counts):
        return data
    l, r = x.T
    lc, rc = l - l.mean(), r - r.mean()
    den = np.linalg.norm(lc) * np.linalg.norm(rc)
    # Medición independiente, no modifica el audio. No se afirma conformidad BS.1770.
    tp = np.max(np.abs(resample_poly(x, 4, 1, axis=0, window=('kaiser', 5.0))), axis=0)
    levels = rms(x)
    data.update(rms=levels.tolist(), peak=np.max(np.abs(x), axis=0).tolist(), tp4x=tp.tolist(),
                rms_R_over_L=float(levels[1] / levels[0]) if levels[0] else None,
                corr_LR=float(np.clip(np.dot(lc, rc) / den, -1., 1.)) if den else None,
                rms_L_minus_R=float(rms(l-r)), max_abs_L_minus_R=float(np.abs(l-r).max()))
    return data
