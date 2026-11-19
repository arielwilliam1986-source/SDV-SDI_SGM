"""Estímulos de desarrollo 6F (los de la reserva NO están aquí).

Cada caso devuelve Mix, guía vocal, guía instrumental y la expectativa
declarada *antes* de ejecutar el detector. Las expectativas se fijan por
construcción de la señal, no por el resultado observado.

Casos de desarrollo = usados durante el ajuste. La reserva independiente se
genera con `reserva_6f.py` después de congelar la implementación.
"""
import numpy as np

SR = 44100
SEED_DEV = 609174223
SEED_DEV4 = 20261119


def delay(x, d):
    """Desplazamiento con relleno de ceros (convención de los estímulos)."""
    z = np.zeros_like(x)
    if d > 0:
        z[d:] = x[:-d]
    elif d < 0:
        z[:d] = x[-d:]
    else:
        z[:] = x
    return z


def noise(rng, n, ch=2):
    return rng.integers(-2048, 2048, (n, ch)).astype('float32') / np.float32(32768)


def marks(rng, n, period=97, width=3, amp=.5):
    """Marcas temporales únicas (aperiódicas): impulsos con jitter."""
    x = np.zeros(n, dtype='float32')
    pos = 0
    while pos < n - width:
        x[pos:pos + width] = amp * rng.uniform(.6, 1.0, width).astype('float32')
        pos += width + int(period * rng.uniform(.6, 1.4)) + 1
    return np.column_stack([x, x])


def ramp(x, lo=.2, hi=1.0):
    g = np.linspace(lo, hi, len(x), dtype='float32')[:, None]
    return (x * g).astype('float32')


def casos_dev(seconds=1.0):
    rng = np.random.default_rng(SEED_DEV)
    n = int(SR * seconds)
    v, i, j = noise(rng, n), noise(rng, n), noise(rng, n)
    side = lambda x: np.column_stack((x[:, 0], -x[:, 0]))
    sine = np.broadcast_to((np.arange(n) % 32 == 0)[:, None], v.shape) * np.float32(.125)
    tone = np.column_stack([np.sin(2 * np.pi * 440 * np.arange(n) / SR)] * 2).astype('float32')
    right = v + i + np.float32(.125) * delay(v, 123)
    right[:, 0] = (v + i)[:, 0]
    left = v + i + np.float32(.125) * delay(v, 211)
    left[:, 1] = (v + i)[:, 1]
    loud = v + i + np.float32(.5) * delay(v, 301)
    loud[:, 0] = (v + i)[:, 0]
    three = v + i + np.float32(.25) * delay(v, 173) + np.float32(.25) * delay(v, -241)
    piece = v.copy()
    piece[n // 2:] = delay(v, 53)[n // 2:]
    rampv = ramp(v)
    mk = marks(rng, n) * np.float32(.4)
    cases = {
        'clean': dict(mix=v + i, guide=v, inst=i, expected='UNIQUE', k=0,
                      note='sin réplica'),
        'signed': dict(mix=v + i, guide=-v, inst=i, expected='UNIQUE', k=0,
                       note='polaridad invertida en el estímulo'),
        'side': dict(mix=side(v + i), guide=side(v), inst=side(i), expected='UNIQUE', k=0),
        'side_output': dict(mix=side(v + i), guide=v, inst=side(i),
                            expected='INSUFFICIENT_SIGNAL', k=None,
                            note='R de la guía sin relación con R del mix'),
        'shift_567': dict(mix=np.pad(v + i, ((0, 567), (0, 0))),
                          guide=np.pad(v, ((567, 0), (0, 0))),
                          inst=np.pad(i, ((0, 567), (0, 0))),
                          expected='UNIQUE', k=-567, note='retardo uniforme de la reserva 6E'),
        'dual_173': dict(mix=v + i + delay(v, 173), guide=v, inst=i,
                         expected='AMBIGUOUS', k=None, note='dos copias iguales'),
        'dominant_.25': dict(mix=v + i + np.float32(.25) * delay(v, -283), guide=v, inst=i,
                             expected='AMBIGUOUS', k=None, note='réplica 0.25 bilateral'),
        'piecewise_53': dict(mix=piece + i, guide=v, inst=i, expected='AMBIGUOUS', k=None,
                             note='cambio de reloj por tramos'),
        'right_rival_.125': dict(mix=right, guide=v, inst=i, expected='AMBIGUOUS', k=None,
                                 note='defecto prioritario heredado: rival exclusivo de R'),
        'left_rival_.125': dict(mix=left, guide=v, inst=i, expected='AMBIGUOUS', k=None,
                                note='réplica exclusiva de L'),
        'right_rival_.25': dict(mix=np.column_stack((v[:, 0], (v + i)[:, 1] +
                                                     np.float32(.25) * delay(v, 400)[:, 1])) + i,
                                guide=v, inst=i, expected='AMBIGUOUS', k=None),
        'right_rival_.5': dict(mix=loud, guide=v, inst=i, expected='AMBIGUOUS', k=None,
                               note='réplica 0.5 exclusiva de R'),
        'different_lr': dict(mix=np.column_stack((v[:, 0], delay(v, 33)[:, 1])) + i,
                             guide=v, inst=i, expected='AMBIGUOUS', k=None,
                             note='desacuerdo L/R real'),
        'periodic_32': dict(mix=sine + i, guide=sine, inst=i, expected='AMBIGUOUS', k=None),
        'unrelated': dict(mix=v + i, guide=j, inst=i, expected='INSUFFICIENT_SIGNAL', k=None),
        'silent': dict(mix=v + i, guide=np.zeros_like(v), inst=i,
                       expected='NON_INFORMATIVE', k=None),
        'dc': dict(mix=v + i, guide=np.full_like(v, .125), inst=i,
                   expected='NON_INFORMATIVE', k=None),
        'nonfinite': dict(mix=v + i, guide=np.full_like(v, np.nan), inst=i,
                          expected='ERROR', k=None),
        'three_copies': dict(mix=three, guide=v, inst=i, expected='AMBIGUOUS', k=None),
        'delay_boundary_+3000_delayed': dict(mix=delay(v + i, 3000), guide=v, inst=delay(i, 3000),
                                     expected='UNIQUE', k=3000,
                                     note='retardo grande; solape parcial'),
        'delay_boundary_+3000': dict(mix=np.pad(v + i, ((3000, 0), (0, 0))),
                                     guide=np.pad(v, ((0, 3000), (0, 0))),
                                     inst=np.pad(i, ((3000, 0), (0, 0))),
                                     expected='UNIQUE', k=3000),
        'partial_guide': dict(mix=v + i, guide=v[:3 * n // 4], inst=i,
                              expected='UNIQUE', k=0, note='guía más corta que el mix'),
        'nonstationary_ramp': dict(mix=rampv + i, guide=v, inst=i, expected='UNIQUE', k=0,
                                   note='amplitud que cambia por tramos lineales'),
        'unique_marks': dict(mix=mk + v + i, guide=mk, inst=i,
                             expected='UNIQUE', k=0, note='marcas no periódicas'),
    }
    for key, c in cases.items():
        m = np.asarray(c['mix'], dtype='float32')
        g = np.asarray(c['guide'], dtype='float32')
        ins = np.asarray(c['inst'], dtype='float32')
        for arr in (m, g, ins):
            if arr.ndim == 1:
                raise SystemExit(f'{key}: se esperaba estéreo (n,2)')
        c.update(mix=m, guide=g, inst=ins)
    return cases


def fixture_s7():
    """Estímulo histórico S7 de S5/6D, replicado desde su receta publicada.

    n=0..176399; s_f[n]=sin(2*pi*((f*n) mod 44100)/44100); a=s441,b=s882,c=s1323;
    v=.16a+.08b, i=.07a+.12c; V=(v,-v), I=(i,-i), Mix=V+I.
    """
    N, sr = 176400, SR
    n = np.arange(N, dtype=np.int64)
    tone = lambda f: np.sin(2 * np.pi * ((n * f) % sr) / sr)
    a, b, c = tone(441), tone(882), tone(1323)
    v, i = .16 * a + .08 * b, .07 * a + .12 * c
    return (np.column_stack((v, -v)).astype('float32'),
            np.column_stack((i, -i)).astype('float32'))


def fixture_s7_manifest():
    import json
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    data = json.loads((root / 'S5_STEREO_VALIDATION' / 'signals' / 'manifest.json').read_text())
    return data['frames'], data['sr'], data['definitions']


if __name__ == '__main__':
    for name, c in casos_dev().items():
        print(f"{name:22s} esperado {c['expected']:20s} k={c['k']} frames={len(c['mix'])}")


def casos_dev4():
    """Casos de desarrollo de 4 s (escala tipo S5/S7, semilla distinta)."""
    rng = np.random.default_rng(SEED_DEV4)
    n = 4 * SR
    v, i = noise(rng, n), noise(rng, n)
    right = v + i + np.float32(.125) * delay(v, 321)
    right[:, 0] = (v + i)[:, 0]
    left = v + i + np.float32(.25) * delay(v, 1000)
    left[:, 1] = (v + i)[:, 1]
    piece = v.copy()
    piece[n // 3:] = delay(v, 777)[n // 3:]
    mk = marks(rng, n, period=211, width=2) * np.float32(.35)
    return {
        '4s_clean': dict(mix=v + i, guide=v, inst=i, expected='UNIQUE', k=0),
        '4s_right_rival_.125': dict(mix=right, guide=v, inst=i,
                                    expected='AMBIGUOUS', k=None),
        '4s_left_rival_.25': dict(mix=left, guide=v, inst=i,
                                  expected='AMBIGUOUS', k=None),
        '4s_shift_1000': dict(mix=np.pad(v + i, ((0, 1000), (0, 0))),
                              guide=np.pad(v, ((1000, 0), (0, 0))),
                              inst=np.pad(i, ((0, 1000), (0, 0))),
                              expected='UNIQUE', k=-1000),
        '4s_dual_3217': dict(mix=v + i + delay(v, 3217), guide=v, inst=i,
                             expected='AMBIGUOUS', k=None),
        '4s_piecewise_777': dict(mix=piece + i, guide=v, inst=i,
                                 expected='AMBIGUOUS', k=None),
        '4s_marks': dict(mix=mk + v + i, guide=mk, inst=i, expected='UNIQUE', k=0),
    }
