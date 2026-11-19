"""Reserva independiente 6F: definida DESPUÉS del congelamiento.

Reglas:
* Semilla nueva, distinta de la de desarrollo (609174223 / 20261119).
* Construcciones y retardos distintos de los usados al ajustar.
* Las expectativas se fijan por construcción (m[t] ~ g[t-k] => k = retardo
  aplicado a la señal con relleno de ceros), antes de ejecutar el detector.
* No se reajusta el código con estos casos.

Un caso (`res_replica_bajo_piso`) declara explícitamente dos resultados
admisibles porque su réplica queda por debajo del piso de detección publicado.
"""
import numpy as np

SR = 44100
SEED_RESERVA = 770315


def delay(x, d):
    z = np.zeros_like(x)
    if d > 0:
        z[d:] = x[:-d]
    elif d < 0:
        z[:d] = x[-d:]
    else:
        z[:] = x
    return z


def noise(rng, n):
    return rng.integers(-4096, 4096, (n, 2)).astype('float32') / np.float32(32768)


def marks(rng, n, period=137, width=2, amp=.45):
    x = np.zeros(n, dtype='float32')
    pos = 3
    while pos < n - width:
        x[pos:pos + width] = amp * rng.uniform(.55, 1.0, width).astype('float32')
        pos += width + int(period * rng.uniform(.55, 1.45)) + 1
    return np.column_stack([x, x])


def casos_reserva():
    rng = np.random.default_rng(SEED_RESERVA)
    n2 = 2 * SR
    n1 = SR
    v2, i2, j2 = noise(rng, n2), noise(rng, n2), noise(rng, n2)
    v1, i1 = v2[:n1], i2[:n1]
    side = lambda x: np.column_stack((x[:, 0], -x[:, 0]))
    impulses = np.broadcast_to((np.arange(n2) % 64 == 0)[:, None], v2.shape) * np.float32(.2)
    mk = marks(rng, n2)
    piece = v2.copy()
    piece[n2 // 2:] = delay(v2, 333)[n2 // 2:]
    right125 = v2 + i2 + np.float32(.125) * delay(v2, 777)
    right125[:, 0] = (v2 + i2)[:, 0]
    left125 = v2 + i2 + np.float32(.125) * delay(v2, 777)
    left125[:, 1] = (v2 + i2)[:, 1]
    right25 = v2 + i2 + np.float32(.25) * delay(v2, -450)
    right25[:, 0] = (v2 + i2)[:, 0]
    left50 = v2 + i2 + np.float32(.5) * delay(v2, 1901)
    left50[:, 1] = (v2 + i2)[:, 1]
    two = v2 + i2 + np.float32(.3) * delay(v2, 250) + np.float32(.3) * delay(v2, -900)
    diff = np.column_stack((v2[:, 0], delay(v2, 58)[:, 1])) + i2
    asym = np.column_stack(((v2 + i2)[:, 0], (np.float32(.3) * (v2 + i2))[:, 1]))
    ramp = (v2 * np.linspace(.5, 1.0, n2, dtype='float32')[:, None]) + i2
    below = v2 + i2 + np.float32(.03) * delay(v2, 611)
    below[:, 0] = (v2 + i2)[:, 0]
    midnull_v = np.column_stack((v2[:, 0], -v2[:, 0]))
    midnull_i = np.column_stack((i2[:, 0], -i2[:, 0]))

    casos = {
        'res_clean_1s': dict(mix=v1 + i1, guide=v1, inst=i1, expected='UNIQUE', k=0),
        'res_clean_2s': dict(mix=v2 + i2, guide=v2, inst=i2, expected='UNIQUE', k=0),
        'res_polaridad': dict(mix=v2 + i2, guide=-v2, inst=i2, expected='UNIQUE', k=0),
        'res_side': dict(mix=side(v2 + i2), guide=side(v2), inst=side(i2),
                         expected='UNIQUE', k=0),
        'res_delay_pos_1901': dict(mix=delay(v2 + i2, 1901), guide=v2,
                                   inst=delay(i2, 1901), expected='UNIQUE', k=1901),
        'res_delay_neg_1901': dict(mix=delay(v2 + i2, -1901), guide=v2,
                                   inst=delay(i2, -1901), expected='UNIQUE', k=-1901),
        'res_shift_pad_567': dict(mix=np.pad(v2 + i2, ((0, 567), (0, 0))),
                                  guide=np.pad(v2, ((567, 0), (0, 0))),
                                  inst=np.pad(i2, ((0, 567), (0, 0))),
                                  expected='UNIQUE', k=-567),
        'res_right_replica_.125_777': dict(mix=right125, guide=v2, inst=i2,
                                           expected='AMBIGUOUS', k=None),
        'res_left_replica_.125_777': dict(mix=left125, guide=v2, inst=i2,
                                          expected='AMBIGUOUS', k=None),
        'res_right_replica_.25_-450': dict(mix=right25, guide=v2, inst=i2,
                                           expected='AMBIGUOUS', k=None),
        'res_left_replica_.5_1901': dict(mix=left50, guide=v2, inst=i2,
                                         expected='AMBIGUOUS', k=None),
        'res_dos_origenes': dict(mix=two, guide=v2, inst=i2, expected='AMBIGUOUS', k=None),
        'res_por_tramos': dict(mix=piece + i2, guide=v2, inst=i2,
                               expected='AMBIGUOUS', k=None),
        'res_periodica_64': dict(mix=impulses + i2, guide=impulses, inst=i2,
                                 expected='AMBIGUOUS', k=None),
        'res_marcas_unicas': dict(mix=mk + v2 + i2, guide=mk, inst=i2,
                                  expected='UNIQUE', k=0),
        'res_no_relacionada': dict(mix=v2 + i2, guide=j2, inst=i2,
                                   expected='INSUFFICIENT_SIGNAL', k=None),
        'res_silencio': dict(mix=v2 + i2, guide=np.zeros_like(v2), inst=i2,
                             expected='NON_INFORMATIVE', k=None),
        'res_dc': dict(mix=v2 + i2, guide=np.full_like(v2, .3), inst=i2,
                       expected='NON_INFORMATIVE', k=None),
        'res_nan': dict(mix=v2 + i2, guide=np.full_like(v2, np.nan), inst=i2,
                        expected='ERROR', k=None),
        'res_lr_distintos_58': dict(mix=diff, guide=v2, inst=i2,
                                    expected='AMBIGUOUS', k=None),
        'res_asimetria_ganancia': dict(mix=asym, guide=v2, inst=i2,
                                       expected='UNIQUE', k=0),
        'res_guia_parcial': dict(mix=v2 + i2, guide=v2[:n2 * 3 // 4], inst=i2,
                                 expected='UNIQUE', k=0),
        'res_retardo_borde_4000': dict(mix=delay(v2 + i2, 4000), guide=v2,
                                       inst=delay(i2, 4000), expected='UNIQUE', k=4000),
        'res_nivel_bajo': dict(mix=np.float32(.01) * (v2 + i2), guide=v2, inst=i2,
                               expected='UNIQUE', k=0),
        'res_guia_debil': dict(mix=v2 + i2, guide=np.float32(.02) * v2, inst=i2,
                               expected='UNIQUE', k=0),
        'res_mid_nulo': dict(mix=midnull_v + midnull_i, guide=midnull_v, inst=midnull_i,
                             expected='UNIQUE', k=0),
        'res_amplitud_variable': dict(mix=ramp, guide=v2, inst=i2,
                                      expected='UNIQUE', k=0),
        'res_replica_bajo_piso': dict(mix=below, guide=v2, inst=i2,
                                      expected='UNIQUE_O_AMBIGUOUS', k=None,
                                      note='réplica 0.03: por debajo del piso publicado'),
    }
    for key, c in casos.items():
        for role in ('mix', 'guide', 'inst'):
            a = np.asarray(c[role], dtype='float32')
            if a.ndim != 2:
                raise SystemExit(f'{key}: {role} debe ser estéreo')
            c[role] = a
    return casos


def cli_reserva():
    """Subconjunto de CLI de la reserva (sin reutilizar los casos de desarrollo)."""
    return [
        ('res_clean_1s', False, 0, None),
        ('res_clean_1s', True, 0, None),
        ('res_dos_origenes', False, 1, None),
        ('res_dos_origenes', True, 0, 'cli_allow_misaligned'),
        ('res_right_replica_.125_777', False, 1, None),
        ('res_right_replica_.125_777', True, 0, 'cli_allow_misaligned'),
        ('res_silencio', True, 0, 'cli_allow_misaligned'),
        ('res_lr_distintos_58', True, 0, 'cli_allow_misaligned'),
        ('res_nan', True, 1, None),
        ('res_por_tramos', True, 0, 'cli_allow_misaligned'),
    ]


if __name__ == '__main__':
    for name, c in casos_reserva().items():
        print(f"{name:28s} {c['expected']:22s} k={c['k']} frames={len(c['mix'])}")
