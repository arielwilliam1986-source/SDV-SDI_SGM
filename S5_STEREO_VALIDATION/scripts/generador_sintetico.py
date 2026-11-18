"""Construcción determinista de Mix y guías; WAV IEEE FLOAT sin metadatos de reloj."""
from io import BytesIO

import numpy as np
from scipy.io import wavfile

from medidas import ROOT, WORK, SR, N, dump, wav_stats

n = np.arange(N, dtype=np.int64)


def tone(f):
    return np.sin(2 * np.pi * ((n*f) % SR) / SR)


def gate(a, b):
    lo, hi = round(a*SR), round(b*SR)
    g = np.zeros(N)
    g[lo:hi] = np.sin(np.pi * (n[lo:hi]-lo)/(hi-lo))**2
    return g


def delay(x, d):
    return np.r_[np.zeros(d), x[:-d]]


def lr(l, r):
    return np.column_stack((l, r))


def fixtures():
    a, b, c = tone(441), tone(882), tone(1323)
    v, i = .16*a + .08*b, .07*a + .12*c
    v2, i2 = lr(.18*a, .16*b), lr(.13*c, .14*a)
    z = np.zeros(N)
    u = .2*(gate(.6,1.1) + .65*gate(2.2,2.7))*a
    w = .15*(gate(.8,1.5) + gate(2.45,3.1))*a + .06*gate(1.6,2.8)*c
    return {
        'S1': (lr(v,v), lr(i,i), 'V=(v,v), I=(i,i). Control L=R.'),
        'S2': (v2, i2, 'V=(0.18a,0.16b), I=(0.13c,0.14a). El tono a pertenece a roles opuestos en L/R.'),
        'S3': (lr(v,v/4), lr(i,i/4), 'V=(v,v/4), I=(i,i/4). Ganancia R/L exacta 1/4 en ambos roles.'),
        'S4': (lr(.08*b + .18*gate(.5,1)*a, z), lr(z, .08*a + .16*gate(2,2.5)*b),
               'V=(0.08b+0.18g[0.5,1]a,0), I=(0,0.08a+0.16g[2,2.5]b). Eventos exclusivos con fondo contralateral en su frecuencia.'),
        'S5': (lr(delay(u,137),delay(u,2342)), lr(delay(w,137),delay(w,2342)),
               'V=(D137(u),D2342(u)), I=(D137(w),D2342(w)); u=0.2(g[0.6,1.1]+0.65g[2.2,2.7])a; w=0.15(g[0.8,1.5]+g[2.45,3.1])a+0.06g[1.6,2.8]c. Retardos del contenido, no desalineación guía/Mix.'),
        'S6': (v2[:, ::-1], i2[:, ::-1], 'S2 permutado (R,L) en Mix y en las dos guías, sin otro cambio.'),
        'S7': (lr(v,-v), lr(i,-i), 'V=(v,-v), I=(i,-i). Contenido lateral no nulo, downmix nulo.'),
    }


def pair(pid, v, i):
    # Los parsers originales piden claves distintas; ambos nombres apuntan a los mismos bytes.
    return dict(pair_id=pid, family='SINTETICA', variant=pid, source='SINTETICA', source_service='SINTETICA',
                vocal_path=v, instrumental_path=i, vocal_guide=v, instrumental_guide=i)


def main():
    signals = fixtures()
    inputs = WORK / 'inputs'
    catalog = dict(sr=SR, frames=N, seconds=N/SR, format='WAV FLOAT 32 bit LE, estéreo',
                   definitions='n=0..176399; s_f[n]=sin(2π((fn) mod 44100)/44100); a=s441,b=s882,c=s1323; v=.16a+.08b, i=.07a+.12c. g[A,B]=sin²(π(n-lo)/(hi-lo)) para lo≤n<hi, 0 fuera; lo=round(44100A), hi=round(44100B). Dd[x][n]=x[n-d] con extensión por cero. Mix=V+I por canal en float64; se escribe cada WAV con un único cast float32. Sin ajuste posterior.',
                   cases={}, audio={})
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = BytesIO()
        wavfile.write(buf, SR, data.astype('<f4'))
        if not path.exists():
            path.write_bytes(buf.getvalue())
        elif path.read_bytes() != buf.getvalue():
            raise ValueError(f'Entrada existente no idéntica: {path}')
        catalog['audio'][str(path.relative_to(inputs))] = wav_stats(path)
    for key, (v, i, formula) in signals.items():
        d = inputs / key
        for name, x in [('Mix',v+i), ('V',v), ('I',i)]:
            write(d / (name+'.wav'), x)
        manifest = dict(mix_original='Mix.wav', pairs=[pair('P1','V.wav','I.wav')])
        dump(d / 'manifest.json', manifest)
        catalog['cases'][key] = dict(formula=formula, manifest=f'inputs/{key}/manifest.json')
    # Controles aislados EVO: segundo par deliberadamente distinto, con/sin inversión.
    v, i, _ = signals['S2']
    right = inputs / 'Ronly'
    write(right/'V.wav', lr(v[:,0],i[:,1]))
    write(right/'I.wav', lr(i[:,0],v[:,1]))
    dump(right/'manifest.json', dict(mix_original='../S2/Mix.wav', pairs=[pair('P1','V.wav','I.wav')]))
    catalog['cases']['Ronly'] = dict(formula='Control unilateral derivado de S2. Mismo archivo Mix; V e I sin cambio en L; sólo en R se permutan V e I.', manifest='inputs/Ronly/manifest.json')
    d = inputs / 'extra'
    vp, ip = .72*v + .28*i, .28*v + .72*i
    for name, x in [('V2',vp), ('menosV2',-vp), ('I2',ip)]:
        write(d / (name+'.wav'), x)
    for key, name, sign in [('Ppos','V2.wav','+'),('Pneg','menosV2.wav','−')]:
        dump(d / (key+'.json'), dict(mix_original='../S2/Mix.wav', pairs=[pair('P1','../S2/V.wav','../S2/I.wav'),pair('P2',name,'I2.wav')]))
        catalog['cases'][key] = dict(formula=f'Mix y P1 de S2; P2: V2={sign}(.72V+.28I), I2=.28V+.72I.',manifest=f'inputs/extra/{key}.json')
    dump(ROOT / 'signals/manifest.json', catalog)
    print(f'{len(catalog["audio"])} WAV de entrada escritos y releídos; 7 escenarios + control R + 2 manifiestos EVO.')


if __name__ == '__main__':
    main()
