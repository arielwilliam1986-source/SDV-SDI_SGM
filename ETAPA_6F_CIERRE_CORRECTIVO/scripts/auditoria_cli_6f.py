"""Auditoría CLI 6F: bloqueos, permisos registrados y PCM.

Comprueba, por motor y por caso, código de salida, ausencia/presencia de WAV,
informe, diagnóstico publicado, registro del permiso y contenido PCM. Un
exit code por sí solo no se considera prueba de seguridad: cada fila incluye
los artefactos observados.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import EV, MOTORES, SR, Cronometro, dump, engine_path, sha_bytes

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from estimulos_6f import casos_dev

MODES = 'full_processing'


def write(path, arr):
    a = np.asarray(arr, dtype='float32')
    if a.ndim == 1:
        a = np.column_stack([a, a])
    sf.write(path, a, SR, subtype='FLOAT')


def run(engine_py, paths, work, flags, tag):
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'out'
    out.mkdir(exist_ok=True)
    man = work / 'manifest.json'
    mix, voc, ins = (str(p) for p in paths)
    man.write_text(json.dumps(dict(
        mix_original=mix,
        pairs=[dict(pair_id='P01', family='AUDIT', variant='V01',
                    configuration='synthetic', source='synthetic',
                    vocal_path=voc, vocal_guide=voc,
                    instrumental_path=ins, instrumental_guide=ins)])))
    cmd = [sys.executable, '-B', str(engine_py), '--manifest', str(man),
           '--out', str(out), '--mode', MODES, *flags]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    reports = list(out.rglob('analysis.json'))
    wavs = sorted(out.rglob('*.wav'))
    report = json.loads(reports[0].read_text()) if len(reports) == 1 else {}
    pcm = {}
    for w in wavs:
        x, s = sf.read(w, dtype='float64', always_2d=True)
        pcm[w.name] = dict(sha256=sha_bytes(x.astype('<f8').tobytes()),
                           shape=list(x.shape), sr=s,
                           finite=bool(np.isfinite(x).all()))
    align = report.get('alignment_analysis') or report.get('alignment')
    gate = report.get('alignment_gate')
    perm = None
    if gate:
        perm = gate.get('permission')
    elif report.get('validation_status'):
        for it in report['validation_status'].get('items', []):
            if it.get('check') == 'misalignment_user_authorized':
                perm = it.get('source')
    return dict(exit=proc.returncode, stdout=proc.stdout[-4000:],
                stderr=proc.stderr[-8000:], n_wavs=len(wavs),
                wav_names=[w.name for w in wavs], report_present=bool(report),
                attribution=(align[0].get('attribution') if align else None),
                classification=(align[0].get('classification') if align else None),
                k=(align[0].get('estimated_offset_samples') if align else None),
                channel_lags=(align[0].get('channel_lags') if align else None),
                gate=gate, permission=perm, pcm=pcm,
                action=(align[0].get('action') if align else None),
                run_dir=str(out))


def main():
    casos = casos_dev()
    filas, logs = [], []
    with Cronometro() as cron, tempfile.TemporaryDirectory(prefix='sdv6f-cli-') as tmp:
        root = Path(tmp)
        rutas = {}
        for name in ('clean', 'side', 'dual_173', 'right_rival_.125', 'silent',
                     'nonfinite', 'different_lr', 'shift_567'):
            ps = []
            for role in ('mix', 'guide', 'inst'):
                p = root / f'{name}-{role}.wav'
                write(p, casos[name][role])
                ps.append(p)
            rutas[name] = ps
        # guía truncada: contenedor inválido
        p = root / 'truncated-guide.wav'
        p.write_bytes(rutas['clean'][1].read_bytes()[:-1000])
        rutas['truncated'] = [rutas['clean'][0], p, rutas['clean'][2]]
        # guía con NaN
        nan = root / 'nan-guide.wav'
        arr = np.asarray(casos['clean']['guide'], dtype='float32').copy()
        arr[100:103, :] = np.nan
        sf.write(nan, arr, SR, subtype='FLOAT')
        rutas['nan_samples'] = [rutas['clean'][0], nan, rutas['clean'][2]]

        plan = [
            ('clean', False, 0), ('clean', True, 0),
            ('side', False, 0),
            ('shift_567', False, 1), ('shift_567', True, 0),
            ('dual_173', False, 1), ('dual_173', True, 0),
            ('right_rival_.125', False, 1), ('right_rival_.125', True, 0),
            ('different_lr', False, 1), ('different_lr', True, 0),
            ('silent', False, 1), ('silent', True, 0),
            ('nonfinite', False, 1), ('nonfinite', True, 1),
            ('truncated', False, 1), ('truncated', True, 1),
            ('nan_samples', False, 1), ('nan_samples', True, 1),
        ]
        for label in MOTORES:
            py = engine_path(label)
            for case, override, want in plan:
                flags = ['--allow-misaligned'] if override else []
                tag = f'{label}_{case}_{int(override)}'
                r = run(py, rutas[case], root / tag, flags, tag)
                row = dict(engine=label, case=case, override=override,
                           expected_exit=want, exit=r['exit'],
                           n_wavs=r['n_wavs'], report=r['report_present'],
                           attribution=r['attribution'], classification=r['classification'],
                           k=r['k'], channel_lags=r['channel_lags'],
                           permission=r['permission'], gate_verdict=(r['gate'] or {}).get('verdict'),
                           pcm=r['pcm'])
                ok = (r['exit'] == want and
                      ((want == 0 and r['report_present'] and r['n_wavs'] >= 2) or
                       (want != 0 and r['n_wavs'] == 0)))
                row['ok'] = ok
                if want == 0 and r['report_present']:
                    pcm = list(r['pcm'].values())
                    row['pcm_finite'] = all(p['finite'] for p in pcm)
                    ok = ok and row['pcm_finite']
                    row['ok'] = ok
                row['permission_recorded'] = r['permission'] is not None
                row['action'] = r['action']
                if override and want == 0:
                    blocked_default = next(f for f in filas
                                           if f['engine'] == label and f['case'] == case
                                           and f['override'] is False)['exit'] != 0
                    row['blocked_by_default'] = blocked_default
                    if blocked_default:
                        ok = ok and row['permission_recorded']
                    act = r['action'] or {}
                    ok = ok and act.get('applied_shift_samples') == 0 and \
                        act.get('polarity_changed') is False
                    row['ok'] = ok
                filas.append(row)
                logs.append(dict(run=tag, exit=r['exit'], stdout=r['stdout'],
                                 stderr=r['stderr'], files=r['wav_names'],
                                 run_dir=r['run_dir']))
        # ---- determinismo y no interferencia del permiso ----------------
        permiso = {}
        for label in MOTORES:
            for case in ('dual_173', 'shift_567', 'clean'):
                a = next(f for f in filas if f['engine'] == label and f['case'] == case
                         and f['override'] is True)
                r2 = run(engine_path(label), rutas[case], root / f'{label}_{case}_rep',
                         ['--allow-misaligned'], f'{label}_{case}_rep')
                permiso[f'{label}/{case}/determinismo'] = dict(
                    same_pcm={k: v['sha256'] for k, v in a['pcm'].items()} ==
                             {k: v['sha256'] for k, v in r2['pcm'].items()},
                    same_exit=a['exit'] == r2['exit'],
                    same_diagnostic=a['attribution'] == r2['attribution'] and a['k'] == r2['k'])
        # ---- 6F con permiso frente a 6E con permiso (mismas muestras) ---
        dsp = {}
        for label in MOTORES:
            for case in ('clean', 'dual_173', 'shift_567', 'right_rival_.125'):
                ref = run(engine_path(label, '6E'), rutas[case],
                          root / f'6E_{label}_{case}', ['--allow-misaligned'],
                          f'6E_{label}_{case}')
                cur = next(f for f in filas if f['engine'] == label and
                           f['case'] == case and f['override'] is True)
                ref_h = {k: v['sha256'] for k, v in ref['pcm'].items()}
                cur_h = {k: v['sha256'] for k, v in cur['pcm'].items()}
                dsp[f'{label}/{case}'] = dict(
                    ref_exit=ref['exit'], cur_exit=cur['exit'],
                    ref_wavs=ref['n_wavs'], cur_wavs=cur['n_wavs'],
                    identical_pcm=(ref_h == cur_h and bool(ref_h)),
                    same_shape={k: v['shape'] for k, v in cur['pcm'].items()} ==
                               {k: v['shape'] for k, v in ref['pcm'].items()})
        conformes = sum(1 for f in filas if f['ok'])
    dump(EV / 'cli_6f.json', dict(rows=filas, logs=logs,
                                  resumen=dict(ok=conformes, total=len(filas)),
                                  determinism_and_permission=permiso,
                                  dsp_vs_6E=dsp,
                                  seconds=cron.seconds,
                                  maxrss_kib=cron.maxrss_kib,
                                  child_rss_kib=cron.child_rss_kib))
    print(f'CLI: {conformes}/{len(filas)} filas conformes en {cron.seconds:.1f}s')
    for f in filas:
        if not f['ok']:
            print('FALLA', f['engine'], f['case'], f['override'], 'exit',
                  f['exit'], 'wavs', f['n_wavs'], 'report', f['report'],
                  'attr', f['attribution'], 'perm', f['permission'])
    for k, v in permiso.items():
        print('DET', k, 'pcm', 'igual' if v['same_pcm'] else 'DISTINTO',
              'diag', 'intacto' if v['same_diagnostic'] else 'CAMBIÓ')
    for k, v in dsp.items():
        print('DSP vs 6E', k, 'pcm', 'idéntico' if v['identical_pcm'] else 'DISTINTO',
              'formas', 'iguales' if v['same_shape'] else 'distintas',
              'exit', v['ref_exit'], v['cur_exit'])
    return 0 if conformes == len(filas) else 1


if __name__ == '__main__':
    raise SystemExit(main())
