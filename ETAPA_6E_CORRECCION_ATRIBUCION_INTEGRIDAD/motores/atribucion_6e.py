"""Experimental additive-copy evidence; no audio edits or clock correction."""
import math
import os
import struct
from statistics import NormalDist

import numpy as np
from scipy.signal import correlate


def verify_wave(path, decoder):
    """Strict little-endian RIFF/WAVE, one fmt and one data chunk."""
    with open(path, 'rb') as f:
        physical = os.fstat(f.fileno()).st_size
        head = f.read(12)
        if len(head) != 12 or head[:4] != b'RIFF' or head[8:] != b'WAVE':
            raise ValueError('Se requiere contenedor RIFF/WAVE clásico')
        end = 8 + struct.unpack_from('<I', head, 4)[0]
        if end != physical:
            raise ValueError(f'RIFF declara {end} bytes; existen {physical}')
        fmt = size = None
        while f.tell() < end:
            header = f.read(8)
            if len(header) != 8:
                raise ValueError('Cabecera de chunk incompleta')
            kind, n = struct.unpack('<4sI', header)
            start = f.tell()
            stop = start + n + (n & 1)
            if stop > end:
                raise ValueError(f'Chunk incompleto: {kind!r}')
            if kind == b'fmt ':
                if fmt is not None or n < 16:
                    raise ValueError('fmt inválido o repetido')
                fmt = struct.unpack('<HHIIHH', f.read(16))
            if kind == b'data':
                if size is not None or fmt is None:
                    raise ValueError('data repetido o sin fmt previo')
                size = n
            f.seek(stop)
        if fmt is None or size is None:
            raise ValueError('Falta fmt o data')
        code, channels, rate, byte_rate, align, bits = fmt
        if (code not in (1, 3, 65534) or not bits or not align or
                align != channels * ((bits + 7) // 8) or byte_rate != rate * align or
                size % align or (channels, rate, size // align) !=
                (decoder.channels, decoder.samplerate, decoder.frames)):
            raise ValueError('Geometría WAV incompatible con payload o decodificador')


def _scores(search, template):
    n = len(template)
    dot = correlate(search, template, mode='valid', method='fft')
    sums = np.r_[0., np.cumsum(search)]
    squares = np.r_[0., np.cumsum(search * search)]
    energy = squares[n:] - squares[:-n] - (sums[n:] - sums[:-n])**2/n
    denom = np.sqrt(np.maximum(energy, 0) * np.dot(template, template))
    return np.clip(np.divide(dot, denom, out=np.zeros_like(dot), where=denom > 0), -1, 1)


def measure(mix, guide, radius, rate, decision, severity):
    if not (np.isfinite(mix).all() and np.isfinite(guide).all()):
        raise ValueError('Muestras no finitas')
    if not len(guide) or not len(mix) or np.ptp(guide) == 0 or np.ptp(mix) == 0:
        return decision('NON_INFORMATIVE', 'EMPTY_OR_CONSTANT'), []
    # Contiguous coverage; independent halves must corroborate each local lag.
    count = max(1, math.ceil(len(guide)/(rate/4)))
    windows = []
    for j in range(count):
        start, stop = j*len(guide)//count, (j+1)*len(guide)//count
        n = stop-start
        lo, hi = max(0, start-radius), min(len(mix)-n, start+radius)
        t = guide[start:stop].copy()
        w = dict(start=start, stop=stop, lags=[], rho=[], rival=[])
        windows.append(w)
        if n < 128 or hi < lo or np.ptp(t) == 0:
            w['state'] = 'INSUFFICIENT_SIGNAL'
            continue
        y = mix[lo:hi+n]
        # Fisher score with multiplicity budget. Correlated audio violates the
        # white null: also demand short-memory template on both holdouts.
        cuts = [(0, n//2), (n//2, n)]
        for a, b in cuts:
            x = t[a:b] - np.mean(t[a:b])
            power = np.dot(x, x)
            if not power:
                break
            auto = correlate(x, x, method='fft')[len(x)-1:]/power
            if np.max(abs(auto[1:])) >= .95:
                w['state'] = 'AMBIGUOUS'
                break
            effective = len(x)/(1+2*np.dot(auto[1:], auto[1:]))
            if effective <= 3:
                break
            threshold = math.tanh(NormalDist().inv_cdf(1-0.001/(8*count*(hi-lo+1))) / math.sqrt(effective-3))
            s = y[a:hi-lo+b]
            rho = _scores(s, x)
            i = int(np.argmax(abs(rho)))
            if abs(rho[i]) <= threshold:
                break
            residual = s.copy()
            segment = residual[i:i+len(x)]
            segment -= np.dot(segment, x)/power*x
            # Compare residual dot products to ORIGINAL local energy: subtraction
            # must not turn floating-point dust into a unit correlation.
            rival = _scores(residual, x)
            m = len(x)
            def local_energy(v):
                z = np.r_[0., np.cumsum(v)]
                q = np.r_[0., np.cumsum(v*v)]
                return np.maximum(q[m:]-q[:-m]-(z[m:]-z[:-m])**2/m, 0)
            e = local_energy(s)
            rival *= np.sqrt(np.divide(local_energy(residual), e, out=np.zeros_like(e), where=e>0))
            # Check alternatives before and after subtracting dominant copy.
            alternate = max(float(np.max(abs(rival))), float(np.max(abs(np.delete(rho, i)), initial=0)))
            w['lags'].append(lo+i-start)
            w['rho'].append(float(rho[i]))
            w['rival'].append(dict(score=alternate, threshold=threshold))
            if alternate > threshold:
                w['state'] = 'AMBIGUOUS'
                break
        if 'state' not in w:
            w['state'] = ('INSUFFICIENT_SIGNAL' if len(w['lags']) != 2 else
                          'UNIQUE' if len(set(w['lags'])) == 1 and np.sign(w['rho'][0]) == np.sign(w['rho'][1]) else 'AMBIGUOUS')
    states = {w['state'] for w in windows}
    lags = {w['lags'][0] for w in windows if w['state'] == 'UNIQUE'}
    if 'AMBIGUOUS' in states or len(lags) > 1:
        return decision('AMBIGUOUS', 'RIVAL_OR_VARIABLE_CLOCK'), windows
    if states != {'UNIQUE'}:
        return decision('INSUFFICIENT_SIGNAL', 'INCOMPLETE_TEMPORAL_COVERAGE'), windows
    k = lags.pop()
    rho = min((r for w in windows for r in w['rho']), key=abs)
    return decision(severity(k), 'UNIQUE_WITHIN_SEARCH_MODEL', k, rho, abs(rho)), windows
