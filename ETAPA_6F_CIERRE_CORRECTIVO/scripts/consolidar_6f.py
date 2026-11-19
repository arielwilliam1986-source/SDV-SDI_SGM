"""Consolida el expediente 6F: matrices, manifiesto y SHA256SUMS.

Uso: python -B scripts/consolidar_6f.py
"""
import csv
import hashlib
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import (BASE, EV, HERE, MOTORES, ORIG, REFS, ROOT, SR, dump,
                      entorno, git, sha_bytes, sha_file)

import numpy as np
import soundfile as sf

sys.path.insert(0, str(HERE / 'scripts'))
from estimulos_6f import casos_dev, casos_dev4
from reserva_6f import casos_reserva


def matriz_atribucion():
    rows = []
    dev = json.loads((EV / 'atribucion_dev.json').read_text())['results']
    for engine, cases in dev.items():
        for case, r in cases.items():
            rows.append(dict(origin='desarrollo', engine=engine, case=case,
                             expected=r['expected'], expected_k=r['expected_k'],
                             attribution=r['attribution'], k=r['k'],
                             verdict='PASS' if r['ok'] else 'FAIL',
                             reason=r['reason'],
                             channel_lags=json.dumps(r.get('channel_lags') or {})))
    res = json.loads((EV / 'reserva_atribucion.json').read_text())['cases']
    for engine, cases in res.items():
        for case, r in cases.items():
            rows.append(dict(origin='reserva', engine=engine, case=case,
                             expected=r['expected'], expected_k=r['expected_k'],
                             attribution=r['attribution'], k=r['k'],
                             verdict='PASS' if r['ok'] else 'FAIL',
                             reason=r['reason'],
                             channel_lags=json.dumps(r.get('channel_lags') or {})))
    return rows


def hashes_estimulos():
    """SHA-256 de los WAV regenerados (deterministas) sin conservar binarios."""
    out = {}
    with tempfile.TemporaryDirectory(prefix='sdv6f-hash-') as tmp:
        tmp = Path(tmp)
        for origen, casos in (('desarrollo', {**casos_dev(), **casos_dev4()}),
                              ('reserva', casos_reserva())):
            out[origen] = {}
            for name, c in casos.items():
                entry = {}
                for role in ('mix', 'guide', 'inst'):
                    p = tmp / f'{name}-{role}.wav'
                    a = np.asarray(c[role], dtype='float32')
                    if a.ndim == 1:
                        a = np.column_stack([a, a])
                    sf.write(p, a, SR, subtype='FLOAT')
                    entry[role] = dict(sha256=sha_file(p), bytes=p.stat().st_size,
                                       frames=int(a.shape[0]))
                entry['expected'] = c['expected']
                entry['expected_k'] = c['k']
                out[origen][name] = entry
    return out


def fuentes_protegidas():
    rutas = []
    for base in (ORIG, REFS['6C'], REFS['6E']):
        for p in sorted(base.glob('*.py')):
            rutas.append(p)
    return {p.relative_to(ROOT).as_posix(): sha_file(p) for p in rutas}


def main():
    dev = json.loads((EV / 'atribucion_dev.json').read_text())
    res = json.loads((EV / 'reserva_atribucion.json').read_text())
    cli = json.loads((EV / 'cli_6f.json').read_text())
    wav = json.loads((EV / 'wav_auditoria.json').read_text())
    dsp = json.loads((EV / 'dsp_no_regresion.json').read_text())
    s7 = json.loads((EV / 'mqr_s7.json').read_text())
    cli_res = json.loads((EV / 'reserva_cli.json').read_text())
    wav_res = json.loads((EV / 'reserva_wav.json').read_text())

    rows = matriz_atribucion()
    with (HERE / 'MATRIZ_RESULTADOS_6F.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    with (HERE / 'MATRIZ_CLI_6F.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['conjunto', 'engine', 'case', 'override', 'expected_exit',
                    'exit', 'wavs', 'report', 'attribution', 'k', 'permission',
                    'verdict'])
        for r in cli['rows']:
            w.writerow(['desarrollo', r['engine'], r['case'], r['override'],
                        r['expected_exit'], r['exit'], r['n_wavs'], r['report'],
                        r['attribution'], r['k'], r['permission'],
                        'PASS' if r['ok'] else 'FAIL'])
        for k, r in cli_res['rows'].items():
            w.writerow(['reserva', r.get('case'), r.get('override'),
                        r.get('expected_exit'), r.get('exit'), r.get('wavs'),
                        r.get('report'), r.get('attribution'), r.get('k'),
                        r.get('permission'), 'PASS' if r['ok'] else 'FAIL'])
    with (HERE / 'MATRIZ_WAV_6F.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['conjunto', 'case', 'expected_valid', 'accepted', 'error',
                    'bytes', 'sha256', 'verdict'])
        for k, r in wav['casos'].items():
            if k == '_toctou':
                continue
            w.writerow(['desarrollo', k, r['expected_valid'], r['accepted'],
                        r.get('error'), r['size'], r['sha256'],
                        'PASS' if r['ok'] else 'FAIL'])
        for k, r in wav_res['casos'].items():
            w.writerow(['reserva', k, r['expected_valid'], r['accepted'],
                        r.get('error'), r['size'], r['sha256'],
                        'PASS' if r['ok'] else 'FAIL'])

    motores = {}
    for label, (name, _) in MOTORES.items():
        p = HERE / 'motores' / name
        motores[label] = dict(file=name, sha256=sha_file(p), bytes=p.stat().st_size)
    modulos = {p.name: dict(sha256=sha_file(p), bytes=p.stat().st_size)
               for p in sorted((HERE / 'motores').glob('*.py'))
               if p.name not in {n for n, _ in MOTORES.values()}}
    scripts = {p.name: sha_file(p) for p in sorted((HERE / 'scripts').glob('*.py'))}

    manifiesto = dict(
        stage='6F', base_commit=BASE, branch=git('branch', '--show-current'),
        freeze_commit=git('rev-parse', '--short', 'HEAD'),
        head=git('rev-parse', 'HEAD'),
        manifest_note='el commit final es el que contiene este manifiesto; '
                      'freeze_commit es el árbol congelado antes de la reserva',
        engines=motores, new_modules=modulos, scripts=scripts,
        protected_sources=fuentes_protegidas(),
        environment=entorno(),
        stimuli=hashes_estimulos(),
        results=dict(
            dev=dev['summary'],
            reserve=res['summary'],
            cli=dict(dev=cli['resumen'],
                     reserve=dict(ok=cli_res['ok'], total=cli_res['total'])),
            wav=dict(dev=dict(ok=wav['conformes'], total=wav['total']),
                     reserve=dict(ok=wav_res['ok'], total=wav_res['total'])),
            dsp_no_regression={k: {v2: d['identical_pcm'] for v2, d in row.items()}
                               for k, row in dsp['comparisons'].items()},
            mqr_s7={k: dict(exit=v['exit'], abort=v['abort'], report=v['report'],
                            wavs=v['wavs'], crest=v.get('crest'),
                            validation_overall=v.get('validation_overall'))
                    for k, v in s7['resultados'].items() if k != '_matematica'},
        ),
        resources=dict(
            dev_seconds=dev['seconds'], dev_maxrss_kib=dev['maxrss_kib'],
            reserve_seconds=res['seconds'], reserve_maxrss_kib=res['maxrss_kib'],
            cli_seconds=cli['seconds'], cli_maxrss_self_kib=cli['maxrss_kib'],
            cli_maxrss_children_kib=cli['child_rss_kib'],
            wav_seconds=wav['seconds'], wav_maxrss_kib=wav.get('maxrss_kib'),
            dsp_seconds=dsp['seconds'], dsp_maxrss_kib=dsp['maxrss_kib'],
            dsp_maxrss_children_kib=dsp['child_rss_kib'],
            s7_seconds=s7['seconds'], s7_maxrss_kib=s7['maxrss_kib'],
            s7_maxrss_children_kib=s7['child_rss_kib'],
        ),
        notes=dict(
            arena='mediciones del entorno Arena (Linux x86_64, 2 CPU, 1 hilo BLAS)',
            termux='no se extrapolan tiempos, memoria ni capacidad a Termux ARM64',
            dsp='copias 6F sólo cambian diagnóstico, validación de archivos y CLI',
        ),
    )
    dump(HERE / 'MANIFEST_6F.json', manifiesto)

    # SHA256SUMS (sin incluirse a sí mismo)
    lines = []
    for p in sorted(HERE.rglob('*')):
        if p.is_dir() or p.name == 'SHA256SUMS.txt':
            continue
        lines.append(f'{sha_file(p)}  ./{p.relative_to(HERE).as_posix()}')
    (HERE / 'SHA256SUMS.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Matriz:', len(rows), 'filas | archivos con hash:', len(lines))


if __name__ == '__main__':
    main()
