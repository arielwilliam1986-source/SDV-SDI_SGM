"""Validación de DESARROLLO 6F (atribución por motor y por canal).

No es la reserva: estos casos se usaron durante el ajuste. La reserva
independiente se define después de congelar (`reserva_6f.py`).

Uso: python -B scripts/validar_dev_6f.py
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import (EV, MOTORES, SR, Cronometro, dump, engine_path,
                      load_engine, sha_file)
from estimulos_6f import casos_dev, casos_dev4

import numpy as np
import soundfile as sf


def escribir(path, arr):
    a = np.asarray(arr, dtype='float32')
    if a.ndim == 1:
        a = np.column_stack([a, a])
    sf.write(path, a, SR, subtype='FLOAT')


def main():
    casos = dict(casos_dev())
    casos.update(casos_dev4())
    evidencia, filas = {}, []
    with Cronometro() as cron:
        with tempfile.TemporaryDirectory(prefix='sdv6f-dev-') as tmp:
            tmp = Path(tmp)
            rutas = {}
            for name, c in casos.items():
                ps = []
                for role in ('mix', 'guide', 'inst'):
                    p = tmp / f'{name}-{role}.wav'
                    escribir(p, c[role])
                    ps.append(p)
                rutas[name] = ps
            for label in MOTORES:
                eng = load_engine(engine_path(label), tag=f'dev_{label}')
                evidencia[label] = {}
                for name, c in casos.items():
                    m, g, i = rutas[name]
                    infos = [eng.probe_file(str(p), r) for p, r in
                             zip((m, g, i), ('mix', 'vocal', 'instrumental'))]
                    res = eng.analyze_alignment(infos[0], infos[1])
                    got = res['attribution']
                    gk = res.get('estimated_offset_samples')
                    want, wk = c['expected'], c['k']
                    ok = got == want and gk == wk
                    chans = {}
                    for ch, v in res['channels'].items():
                        chans[ch] = dict(attribution=v.get('attribution'),
                                         classification=v.get('classification'),
                                         k=v.get('estimated_offset_samples'),
                                         rho=v.get('correlation_peak'),
                                         confidence=v.get('alignment_confidence'),
                                         coverage=v.get('coverage'),
                                         floor=v.get('replica_detection_floor'),
                                         rivals=v.get('rivals', []),
                                         structural=v.get('structural', []))
                        filas.append(dict(engine=label, caso=name, canal=ch,
                                          esperado=want, esperado_k=wk,
                                          atribucion=v.get('attribution'),
                                          clase=v.get('classification'),
                                          k=v.get('estimated_offset_samples'),
                                          cubierta=v.get('coverage'),
                                          piso_replica=v.get('replica_detection_floor'),
                                          ok=int(v.get('attribution') == want and
                                                 v.get('estimated_offset_samples') == wk),
                                          detalle=v.get('reason')))
                    filas.append(dict(engine=label, caso=name, canal='AGG',
                                      esperado=want, esperado_k=wk, atribucion=got,
                                      clase=res.get('classification'), k=gk,
                                      cubierta=None, piso_replica=None, ok=int(ok),
                                      detalle=res.get('reason')))
                    evidencia[label][name] = dict(
                        expected=want, expected_k=wk, attribution=got, k=gk,
                        ok=ok, reason=res.get('reason'),
                        channel_lags=res.get('channel_lags'),
                        channel_states=res.get('channel_states'),
                        channels=chans,
                        search_window_samples=res.get('search_window_samples'),
                        integrity=res.get('integrity', {}).get('same_descriptor_read'),
                        wav_sha256={p.name: sha_file(p) for p in (m, g, i)},
                        wav_bytes={p.name: p.stat().st_size for p in (m, g, i)})
    agg = [f for f in filas if f['canal'] == 'AGG']
    resumen = {label: [sum(1 for f in agg if f['engine'] == label and f['ok']),
                       sum(1 for f in agg if f['engine'] == label)]
               for label in MOTORES}
    dump(EV / 'atribucion_dev.json',
         dict(casos=sorted(casos), results=evidencia, summary=resumen,
              seconds=cron.seconds, maxrss_kib=cron.maxrss_kib))
    with (EV / 'matriz_dev.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    for label, (ok, tot) in resumen.items():
        print(f'{label}: {ok}/{tot} casos (agregado) en {cron.seconds:.1f}s')
    fallos = [f for f in agg if not f['ok']]
    for f in fallos:
        print('FALLA', f['engine'], f['caso'], f['atribucion'], f['k'],
              'esperado', f['esperado'], f['esperado_k'], f['detalle'])
    return 0 if not fallos else 1


if __name__ == '__main__':
    raise SystemExit(main())
