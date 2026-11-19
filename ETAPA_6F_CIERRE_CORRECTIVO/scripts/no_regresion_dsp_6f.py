"""No regresión DSP 6F: PCM de SDV/SDI frente a 6C y 6E + auditoría AST.

No se acepta una afirmación genérica de «sin regresión»: se comparan hashes de
las muestras decodificadas, formas, finitud, crestas de MQR y el conjunto de
definiciones de nivel superior que cambian en cada motor.
"""
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import (EV, MOTORES, REFS, SR, Cronometro, dump, engine_path,
                      sha_bytes, sha_file)

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from estimulos_6f import casos_dev, casos_dev4

CASOS = ('clean', 'side', 'dual_173', 'shift_567', 'right_rival_.125',
         'different_lr', '4s_clean', '4s_shift_1000')


def write(p, arr):
    a = np.asarray(arr, dtype='float32')
    if a.ndim == 1:
        a = np.column_stack([a, a])
    sf.write(p, a, SR, subtype='FLOAT')


def run(engine_py, man, out, flags):
    cmd = [sys.executable, '-B', str(engine_py), '--manifest', str(man),
           '--out', str(out), '--mode', 'full_processing', *flags]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    wavs = sorted(Path(out).rglob('*.wav'))
    pcm = {}
    for w in wavs:
        x, s = sf.read(w, dtype='float64', always_2d=True)
        pcm[w.name] = dict(sha256=sha_bytes(x.astype('<f8').tobytes()),
                           shape=list(x.shape), sr=int(s),
                           finite=bool(np.isfinite(x).all()),
                           peak=float(np.abs(x).max()))
    rep = list(Path(out).rglob('analysis.json'))
    crest = {}
    if rep:
        r = json.loads(rep[0].read_text())
        for cid, d in (r.get('source_fidelity_metrics') or {}).items():
            crest[cid] = d.get('crest_factor_sdv')
            crest[cid + '/mix'] = d.get('crest_factor_mix')
    return dict(exit=proc.returncode, wavs=len(wavs), pcm=pcm, crest=crest,
                report=bool(rep), stderr=proc.stderr[-3000:])


def definiciones(path):
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    defs, assigns = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            defs[node.name] = ast.dump(node, include_attributes=False)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    assigns[t.id] = ast.dump(node.value, include_attributes=False)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.isupper():
                assigns[node.target.id] = ast.dump(node.value, include_attributes=False)
    return defs, assigns


def main():
    casos = dict(casos_dev())
    casos.update(casos_dev4())
    filas, ast_rows = {}, {}
    with Cronometro() as cron, tempfile.TemporaryDirectory(prefix='sdv6f-dsp-') as tmp:
        root = Path(tmp)
        man = {}
        for name in CASOS:
            ps = []
            for role in ('mix', 'guide', 'inst'):
                p = root / f'{name}-{role}.wav'
                write(p, casos[name][role])
                ps.append(str(p))
            m = root / f'{name}-manifest.json'
            m.write_text(json.dumps(dict(
                mix_original=ps[0],
                pairs=[dict(pair_id='P01', family='AUDIT', variant='V01',
                            configuration='synthetic', vocal_path=ps[1],
                            vocal_guide=ps[1], instrumental_path=ps[2],
                            instrumental_guide=ps[2])])))
            man[name] = m
        for label in MOTORES:
            for ver in ('6C', '6E', '6F'):
                py = (engine_path(label, ver) if ver != '6F'
                      else REFS['6F'] / MOTORES[label][0])
                for case in CASOS:
                    out = root / f'{ver}_{label}_{case}'
                    filas[f'{label}/{ver}/{case}'] = run(
                        py, man[case], out, ['--allow-misaligned'])
        comparisons = {}
        for label in MOTORES:
            for case in CASOS:
                cur = filas[f'{label}/6F/{case}']
                row = {}
                for ver in ('6C', '6E'):
                    ref = filas[f'{label}/{ver}/{case}']
                    comparable = (ref['exit'] == 0 and cur['exit'] == 0 and
                                  bool(ref['pcm']) and bool(cur['pcm']))
                    row[ver] = dict(
                        ref_exit=ref['exit'], cur_exit=cur['exit'],
                        ref_wavs=ref['wavs'], cur_wavs=cur['wavs'],
                        comparable=comparable,
                        identical_pcm=(comparable and
                                       {k: v['sha256'] for k, v in ref['pcm'].items()} ==
                                       {k: v['sha256'] for k, v in cur['pcm'].items()}),
                        same_shape=(comparable and
                                    {k: v['shape'] for k, v in ref['pcm'].items()} ==
                                    {k: v['shape'] for k, v in cur['pcm'].items()}),
                        same_crest=(ref['crest'] == cur['crest']))
                comparisons[f'{label}/{case}'] = row
        # ---- auditoría AST ----------------------------------------------
        for label in MOTORES:
            cur_path = REFS['6F'] / MOTORES[label][0]
            cdefs, cconst = definiciones(cur_path)
            for ver in ('6C', '6E'):
                rdefs, rconst = definiciones(engine_path(label, ver))
                changed = sorted(k for k in cdefs if k in rdefs and cdefs[k] != rdefs[k])
                removed = sorted(set(rdefs) - set(cdefs))
                added = sorted(set(cdefs) - set(rdefs))
                consts = sorted(k for k in cconst if k in rconst and cconst[k] != rconst[k])
                ast_rows[f'{label}/{ver}'] = dict(
                    changed=changed, added=added, removed=removed,
                    changed_constants=consts,
                    dsp_changed=sorted(set(changed) & {
                        'mono_downmix', 'read_span', 'stft_span_frames', 'OlaStream',
                        'apply_sfumato_smoothing', 'TruePeakStream', 'build_band_masks',
                        'compute_vocal_mask', 'confidence_and_disagreement',
                        'consensus_from_masks', 'FramePlan', 'mask_stats_stream_init',
                        'mask_stats_stream_update', 'mask_stats_stream_finalize',
                        'PairwiseAccum', 'GlobalMaskAccum', 'PearsonAccum',
                        'next_pow2', '_moving_rms', '_decimate_block_mean'}),
                    unchanged_defs=sum(1 for k in cdefs if k in rdefs and cdefs[k] == rdefs[k]))
    dump(EV / 'dsp_no_regresion.json', dict(
        rows=filas, comparisons=comparisons, ast=ast_rows,
        seconds=cron.seconds, maxrss_kib=cron.maxrss_kib,
        child_rss_kib=cron.child_rss_kib))
    for k, v in comparisons.items():
        print(k, '| 6C:', 'idéntico' if v['6C']['identical_pcm'] else
              ('no comparable' if not v['6C']['comparable'] else 'DISTINTO'),
              '| 6E:', 'idéntico' if v['6E']['identical_pcm'] else
              ('no comparable' if not v['6E']['comparable'] else 'DISTINTO'),
              '| crest igual:', v['6E']['same_crest'])
    for k, v in ast_rows.items():
        print('AST', k, 'cambiadas', v['changed'], 'añadidas', v['added'],
              'eliminadas', v['removed'], 'constantes', v['changed_constants'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
