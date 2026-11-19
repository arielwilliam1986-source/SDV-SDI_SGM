"""Reproducción del estímulo histórico S7 (S5/6D) contra 6C, 6E y 6F.

S7: V=(v,-v), I=(i,-i) sobre el Mix S1; Mid nulo exacto, canales no nulos y
métrica de cresta indefinida (pico L/R dividido por RMS de Mid).

Se registra: código de salida, aborto, presencia de informe/WAV y el valor
exacto de las crestas. No se introduce epsilon: si el cociente no está
definido, el informe debe decirlo.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import EV, MOTORES, REFS, SR, Cronometro, dump, sha_file

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from estimulos_6f import fixture_s7, fixture_s7_manifest


def write_manifest(path, mix, voc, ins):
    path.write_text(json.dumps(dict(
        mix_original=str(mix),
        pairs=[dict(pair_id='P1', family='S5', variant='S7',
                    configuration='synthetic', source='synthetic',
                    vocal_path=str(voc), vocal_guide=str(voc),
                    instrumental_path=str(ins), instrumental_guide=str(ins))])))


def run(engine_py, manifest, out, flags):
    cmd = [sys.executable, '-B', str(engine_py), '--manifest', str(manifest),
           '--out', str(out), '--mode', 'full_processing', *flags]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    reports = list(Path(out).rglob('analysis.json'))
    rep = json.loads(reports[0].read_text()) if len(reports) == 1 else None
    wavs = sorted(Path(out).rglob('*.wav'))
    pcm = {}
    for w in wavs:
        x, s = sf.read(w, dtype='float64', always_2d=True)
        mid = x.mean(axis=1)
        pcm[w.name] = dict(frames=int(len(x)), sr=int(s),
                           sha256=sha_file(w),
                           lr_peak=float(np.abs(x).max()),
                           mid_rms=float(np.sqrt(np.mean(mid ** 2))),
                           finite=bool(np.isfinite(x).all()))
    crest = {}
    align = {}
    status = None
    if rep:
        for cid, data in (rep.get('source_fidelity_metrics') or {}).items():
            crest[cid] = data.get('crest_factor_sdv', 'AUSENTE')
            crest[cid + '/mix'] = data.get('crest_factor_mix', 'AUSENTE')
        for rec in (rep.get('alignment') or rep.get('alignment_analysis') or []):
            align[f"{rec.get('pair_id')}/{rec.get('role')}"] = dict(
                attribution=rec.get('attribution'),
                classification=rec.get('classification'),
                reason=rec.get('reason'), k=rec.get('estimated_offset_samples'),
                channel_lags=rec.get('channel_lags'),
                channel_states=rec.get('channel_states'))
        status = (rep.get('validation_status') or {}).get('overall')
    return dict(exit=proc.returncode, report=rep is not None, wavs=len(wavs),
                pcm=pcm, crest=crest, alignment=align, validation_overall=status,
                stdout=proc.stdout[-3000:], stderr=proc.stderr[-6000:],
                abort='ZeroDivisionError' in proc.stderr or 'FATAL' in proc.stdout)


def main():
    v, i = fixture_s7()
    frames, sr, definicion = fixture_s7_manifest()
    assert sr == SR and len(v) == frames, (len(v), frames)
    mix = (v + i).astype('float32')
    filas = {}
    with Cronometro() as cron, tempfile.TemporaryDirectory(prefix='sdv6f-s7-') as tmp:
        root = Path(tmp)
        for name, arr in (('mix', mix), ('voc', v), ('ins', i)):
            sf.write(root / f'{name}.wav', arr, SR, subtype='FLOAT')
        man = root / 'manifest.json'
        write_manifest(man, root / 'mix.wav', root / 'voc.wav', root / 'ins.wav')
        for label in MOTORES:
            for ref, flags in (('6C', ['--allow-misaligned']),
                               ('6E', ['--allow-misaligned']),
                               ('6F', []), ('6F', ['--allow-misaligned'])):
                py = REFS[ref] / MOTORES[label][0] if ref != '6F' else \
                    REFS['6F'] / MOTORES[label][0]
                tag = f'{label}_{ref}_' + ('perm' if flags else 'noperm')
                out = root / tag
                r = run(py, man, out, flags)
                r.update(engine=label, version=ref, flags=flags)
                filas[tag] = r
        # matemática del estimador de cresta sobre las muestras de entrada
        mid = mix.mean(axis=1)
        filas['_matematica'] = dict(
            mix_mid_rms=float(np.sqrt(np.mean(mid ** 2))),
            mix_lr_peak=float(np.abs(mix).max()),
            guia_v_mid_rms=float(np.sqrt(np.mean(v.mean(axis=1) ** 2))),
            notas='cresta = pico L/R / RMS Mid: no definida si RMS Mid = 0, '
                  'aunque el pico sea positivo')
        sha = {p.name: sha_file(p) for p in
               (root / 'mix.wav', root / 'voc.wav', root / 'ins.wav')}
    dump(EV / 'mqr_s7.json', dict(definicion=definicion, frames=frames, sr=sr,
                                  sha_wav=sha, resultados=filas, seconds=cron.seconds,
                                  maxrss_kib=cron.maxrss_kib,
                                  child_rss_kib=cron.child_rss_kib))
    for tag, r in filas.items():
        if tag == '_matematica':
            continue
        print(f'{tag:18s} exit={r["exit"]} abort={r["abort"]} informe={r["report"]} '
              f'wavs={r["wavs"]} crest={r["crest"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
