"""Validación con la reserva independiente 6F (definida tras el congelamiento).

No se modifica el código ni los umbrales a partir de estos resultados.
Ejecuta tres bloques: atribución (3 motores), corpus WAV y CLI.
"""
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import (EV, MOTORES, SR, Cronometro, dump, engine_path,
                      load_engine, sha_bytes, sha_file)

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from reserva_6f import casos_reserva, cli_reserva
from auditoria_wav_6f import (GUID_PCM, GUID_FLOAT, chunk, fmt_chunk, pcm16,
                              pcm24, riff, sig)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'motores'))
from wav_integridad_6f import WaveError, open_validated, verify_wave

ACEPTA = {'UNIQUE_O_AMBIGUOUS': {'UNIQUE', 'AMBIGUOUS'}}


def escribir(p, arr):
    a = np.asarray(arr, dtype='float32')
    if a.ndim == 1:
        a = np.column_stack([a, a])
    sf.write(p, a, SR, subtype='FLOAT')


def run_cli(engine_py, paths, work, flags):
    work.mkdir(parents=True, exist_ok=True)
    out = work / 'out'
    out.mkdir(exist_ok=True)
    man = work / 'm.json'
    mix, voc, ins = (str(p) for p in paths)
    man.write_text(json.dumps(dict(mix_original=mix, pairs=[dict(
        pair_id='R01', family='RESERVA', variant='R', configuration='synthetic',
        vocal_path=voc, vocal_guide=voc, instrumental_path=ins,
        instrumental_guide=ins)])))
    proc = subprocess.run([sys.executable, '-B', str(engine_py), '--manifest', str(man),
                           '--out', str(out), '--mode', 'full_processing', *flags],
                          capture_output=True, text=True)
    reports = list(out.rglob('analysis.json'))
    wavs = sorted(out.rglob('*.wav'))
    rep = json.loads(reports[0].read_text()) if len(reports) == 1 else {}
    pcm = {}
    for w in wavs:
        x, s = sf.read(w, dtype='float64', always_2d=True)
        pcm[w.name] = dict(sha256=sha_bytes(x.astype('<f8').tobytes()),
                           shape=list(x.shape), finite=bool(np.isfinite(x).all()))
    align = rep.get('alignment_analysis') or rep.get('alignment') or []
    gate = rep.get('alignment_gate')
    perm = (gate or {}).get('permission')
    if perm is None:
        for it in (rep.get('validation_status') or {}).get('items', []):
            if it.get('check') == 'misalignment_user_authorized':
                perm = it.get('source')
    return dict(exit=proc.returncode, wavs=len(wavs), report=bool(rep), pcm=pcm,
                attribution=(align[0].get('attribution') if align else None),
                k=(align[0].get('estimated_offset_samples') if align else None),
                gate=(gate or {}).get('verdict'), permission=perm)


def corpus_wav(tmp):
    x = sig(n=4410)
    out = {}
    out['wav_pcm16_mono'] = (riff([fmt_chunk(channels=1, bits=16),
                                   chunk(b'data', pcm16(x[:, :1]))]), True)
    out['wav_ext_pcm24_mask3'] = (riff([fmt_chunk(code=0xFFFE, bits=24, valid=24, mask=0x3),
                                        chunk(b'data', pcm24(x))]), True)
    out['wav_ext_float_mask3'] = (riff([fmt_chunk(code=0xFFFE, bits=32, mask=0x3,
                                                  guid=GUID_FLOAT),
                                        chunk(b'fact', (4410).to_bytes(4, 'little')),
                                        chunk(b'data', x.astype('<f4').tobytes())]), True)
    good = riff([fmt_chunk(bits=16), chunk(b'data', pcm16(x))])
    out['wav_truncado'] = (good[:-777], False)
    out['wav_mask_mala'] = (riff([fmt_chunk(code=0xFFFE, bits=16, mask=0x3F),
                                  chunk(b'data', pcm16(x))]), False)
    out['wav_cbsize_cero'] = (riff([fmt_chunk(code=0xFFFE, bits=16, cbsize=0),
                                    chunk(b'data', pcm16(x))]), False)
    out['wav_guid_alaw'] = (riff([fmt_chunk(code=0xFFFE, bits=16,
                                            guid=bytes.fromhex('0600000000001000800000aa00389b71')),
                                  chunk(b'data', pcm16(x))]), False)
    out['wav_data_desborda'] = (riff([fmt_chunk(bits=16),
                                      b'data' + (len(pcm16(x)) + 10).to_bytes(4, 'little') +
                                      pcm16(x)]), False)
    out['wav_rf64'] = (b'RF64' + good[4:], False)
    out['wav_sin_padding'] = (riff([fmt_chunk(bits=16),
                                    chunk(b'data', pcm16(x)[:-1], pad=False)]), False)
    paths = {}
    for name, (data, ok) in out.items():
        p = Path(tmp) / f'{name}.wav'
        p.write_bytes(data)
        paths[name] = (p, ok)
    return paths


def main():
    casos = casos_reserva()
    filas, resumen = [], {}
    atribucion = {}
    with Cronometro() as cron, tempfile.TemporaryDirectory(prefix='sdv6f-res-') as tmp:
        root = Path(tmp)
        rutas = {}
        for name, c in casos.items():
            ps = []
            for role in ('mix', 'guide', 'inst'):
                p = root / f'{name}-{role}.wav'
                escribir(p, c[role])
                ps.append(p)
            rutas[name] = ps
        for label in MOTORES:
            eng = load_engine(engine_path(label), tag=f'res_{label}')
            atribucion[label] = {}
            okn = 0
            for name, c in casos.items():
                m, g, i = rutas[name]
                infos = [eng.probe_file(str(p), r) for p, r in
                         zip((m, g, i), ('mix', 'vocal', 'instrumental'))]
                res = eng.analyze_alignment(infos[0], infos[1])
                got, gk = res['attribution'], res.get('estimated_offset_samples')
                want, wk = c['expected'], c['k']
                if want in ACEPTA:
                    good = got in ACEPTA[want]
                else:
                    good = got == want and gk == wk
                okn += good
                chans = {ch: dict(attribution=v.get('attribution'),
                                  classification=v.get('classification'),
                                  k=v.get('estimated_offset_samples'),
                                  coverage=v.get('coverage'),
                                  floor=v.get('replica_detection_floor'),
                                  rivals=v.get('rivals', []),
                                  structural=v.get('structural', []),
                                  channel_lags=v.get('channel_lags'))
                         for ch, v in res['channels'].items()}
                atribucion[label][name] = dict(
                    expected=want, expected_k=wk, attribution=got, k=gk,
                    ok=good, reason=res.get('reason'), channels=chans,
                    channel_lags=res.get('channel_lags'),
                    channel_states=res.get('channel_states'))
                filas.append(dict(engine=label, case=name, expected=want,
                                  expected_k=wk, attribution=got, k=gk,
                                  coverage=(chans.get('L') or {}).get('coverage'),
                                  floor=(chans.get('L') or {}).get('replica_detection_floor'),
                                  ok=int(good), reason=res.get('reason'),
                                  channel_lags=json.dumps(res.get('channel_lags') or {},
                                                          default=str)))
            resumen[label] = [okn, len(casos)]
        # ---- WAV de reserva ---------------------------------------------
        wav = {}
        for name, (p, ok) in corpus_wav(root).items():
            row = dict(expected_valid=ok, size=p.stat().st_size, sha256=sha_file(p))
            try:
                info = sf.info(str(p))
            except Exception:
                info = None
            try:
                verify_wave(str(p), info)
                vw = open_validated(str(p))
                row.update(accepted=True, frames=vw.spec.frames,
                           same_descriptor=vw.unchanged_on_close)
                vw.close()
            except WaveError as exc:
                row.update(accepted=False, error=str(exc))
            row['ok'] = row['accepted'] == ok
            wav[name] = row
        # ---- CLI de reserva ---------------------------------------------
        cli = {}
        for label in MOTORES:
            py = engine_path(label)
            for case, override, want, perm in cli_reserva():
                flags = ['--allow-misaligned'] if override else []
                tag = f'{label}_{case}_{int(override)}'
                r = run_cli(py, rutas[case], root / tag, flags)
                ok = r['exit'] == want and ((want == 0 and r['report'] and r['wavs'] >= 2)
                                            or (want != 0 and r['wavs'] == 0))
                if perm:
                    ok = ok and r['permission'] == perm
                if want != 0:
                    ok = ok and not r['report']
                cli[tag] = dict(case=case, override=override, expected_exit=want,
                                **{k: v for k, v in r.items()}, ok=ok)
    agg_ok = sum(v[0] for v in resumen.values())
    agg_tot = sum(v[1] for v in resumen.values())
    dump(EV / 'reserva_atribucion.json', dict(
        seed=770315, cases=atribucion, summary=resumen,
        seconds=cron.seconds, maxrss_kib=cron.maxrss_kib))
    dump(EV / 'reserva_wav.json', dict(casos=wav,
                                       ok=sum(1 for v in wav.values() if v['ok']),
                                       total=len(wav)))
    dump(EV / 'reserva_cli.json', dict(rows=cli,
                                       ok=sum(1 for v in cli.values() if v['ok']),
                                       total=len(cli),
                                       child_rss_kib=cron.child_rss_kib))
    with (EV / 'matriz_reserva.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    print('Atribución reserva:', agg_ok, '/', agg_tot, resumen)
    print('WAV reserva:', sum(1 for v in wav.values() if v['ok']), '/', len(wav))
    print('CLI reserva:', sum(1 for v in cli.values() if v['ok']), '/', len(cli))
    for label in MOTORES:
        for name, r in atribucion[label].items():
            if not r['ok']:
                print('FALLA', label, name, r['attribution'], r['k'],
                      'esperado', r['expected'], r['expected_k'], r['reason'])
    for k, v in cli.items():
        if not v['ok']:
            print('FALLA CLI', k, v['exit'], v['wavs'], v['report'], v['permission'])
    for k, v in wav.items():
        if not v['ok']:
            print('FALLA WAV', k, v)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
