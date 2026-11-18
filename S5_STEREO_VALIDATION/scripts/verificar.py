"""Verifica el paquete publicado SIN necesitar build/ ni volver a ejecutar los motores."""
import argparse
import csv
from io import BytesIO
import json
from pathlib import Path
import tarfile

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from medidas import ROOT, SR, N, difference, dump, load, rms, sha
from preparar_fuentes import verify
from pruebas_s5 import RESULTS, jobs


def require(ok, message):
    if not ok:
        raise ValueError(message)


def reject(token):
    raise ValueError('Constante no JSON: '+token)


def close(x, y):
    np.testing.assert_allclose(x, y, rtol=1e-11, atol=1e-14)


def check_contrast(contrast, waves, masks, records):
    a, b = (records[contrast[k]] for k in ('a','b'))
    if contrast['status']=='UNKNOWN':
        require('OK' not in (a['status'],b['status']) or a['status']!=b['status'], 'Contraste UNKNOWN sin fallo')
        return
    for role in ('SDV','SDI'):
        x,y = [waves[r['outputs'][role]['path']].astype('float64') for r in (a,b)]
        dif = difference(x,y[:,::-1] if contrast['swap_b'] else y)
        for key, value in dif.items():
            close(contrast[role][key], value)
    x,y = [np.broadcast_to(masks[r['applied_mask']], (2,2049,175)) for r in (a,b)]
    delta = x - (y[::-1] if contrast['swap_b'] else y)
    close(contrast['mask']['rms'], np.sqrt((delta**2).mean(axis=(1,2))))
    close(contrast['mask']['max_abs'], np.abs(delta).max(axis=(1,2)))


def verify_package():
    verify()
    for path in ROOT.rglob('*.json'):
        if 'build' not in path.relative_to(ROOT).parts:
            load(path)
    catalog = load(ROOT/'signals/manifest.json')
    stats = {s['path']:s for s in catalog['audio'].values()}
    data = {b:load(ROOT/'results'/(name+'.json')) for b,name in RESULTS.items()}
    successes, failures, obs_by_path = 0, [], {}
    for b, d in data.items():
        require({(r['case'],r['mode'],r['series']) for r in d['runs']}==set(jobs(b)), f'Matriz incompleta: {b}')
        require(len(d['runs'])==len(set(jobs(b))), f'Corrida duplicada: {b}')
        for r in d['runs']:
            if r['status']=='OK':
                successes += 1
            else:
                failures.append(dict(block=b, id=r['id'], status=r['status'], engine_exit=r['engine_exit']))
            outputs = r.get('outputs',r.get('aborted_wavs_not_completed_outputs',{}))
            stats.update({s['path']:s for s in outputs.values()})
            for v in r['inputs'].values():
                require(stats[v['path']]['sha256']==v['sha256'], 'Hash de entrada no corresponde al ensayo')
            obs = r['observation']
            obs_by_path[r['applied_mask']] = obs
            require(not obs['errors'] and obs['nonfinite']==0 and [ch['f0'] for ch in obs['chunks']]==[0,64,128], 'Observación incompleta')
            for ch in obs['chunks']:
                last = 47 if ch['f0']==128 else 64
                require(ch['mix_stft_shape']==ch['SDV_stft_shape']==ch['SDI_stft_shape']==[2,2049,last], 'Geometría del Mix/candidatos')
                require(ch['max_abs_SDV_minus_XM']==ch['max_abs_SDI_minus_X1mM']==0, 'Producto observado no coincide')
                if b in ('B','C'):
                    require(ch['config']['use_physical_residuals'] is False and ch['config']['mask_mode']==r['mode'], 'Configuración estéreo incorrecta')
                if b=='A':
                    require(ch['config']['branch']=='identity' and ch['config']['pre_share_formula_max_error']==0, 'Rama/fórmula de v3 incorrecta')
            require(all(g['relation_max_error']==0 for g in obs['guide_inputs']), 'Las guías no llegan como se describe')
    with (ROOT/'measurements/resultados.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    require(all(None not in r and None not in r.values() for r in rows), 'Fila CSV irregular')
    csv_map = {(r['path'],r['channel']):r for r in rows}
    require(len(csv_map)==len(rows)==2*len(stats), 'Filas duplicadas o incompletas en CSV')
    digests = {}
    for line in (ROOT/'hashes/MIEMBROS_SHA256.txt').read_text().splitlines():
        digest, member = line.split('  ',1)
        require(member not in digests, 'Miembro duplicado en manifiesto')
        digests[member] = digest
    seen, checked_wavs, checked_masks, inputs = set(), set(), set(), {}
    native_json = 0
    for pack in load(ROOT/'evidence/index.json')['archives']:
        path = ROOT/pack['path']
        require(sha(path.read_bytes())==pack['sha256'] and path.stat().st_size==pack['packed_bytes'], str(path))
        waves, masks = {}, {}
        count = raw_size = 0
        with tarfile.open(path,'r|xz') as tar:
            for m in tar:
                name = m.name
                require(m.isfile() and not Path(name).is_absolute() and '..' not in Path(name).parts, 'Miembro no regular')
                buf = tar.extractfile(m).read()
                digest = sha(buf)
                require(name not in seen and digests[name]==digest, name)
                seen.add(name); count += 1; raw_size += len(buf)
                if name.endswith('.json'):
                    json.loads(buf, parse_constant=reject); native_json += 1
                elif name.endswith('.wav'):
                    f = BytesIO(buf); info = sf.info(f); f.seek(0)
                    x, sr = sf.read(f, dtype='float32',always_2d=True)
                    require((len(x),sr,info.channels,info.subtype)==(N,SR,2,'FLOAT'), 'WAV no cumple el formato: '+name)
                    s = stats[name]
                    require(sha(x.astype('<f4').tobytes())==s['pcm_f32le_sha256'] and digest==s['sha256'], 'WAV no corresponde a sus medidas')
                    y = x.astype('float64')
                    require(np.isfinite(y).all(), 'Muestra no finita: '+name)
                    levels = rms(y)
                    tp = np.abs(resample_poly(y,4,1,axis=0)).max(axis=0)
                    for ch,label in enumerate('LR'):
                        row = csv_map[name,label]
                        require((row['sha256'],row['pcm_f32le_sha256'],int(row['sr']),int(row['frames']),int(row['channels']),float(row['seconds']),int(row['nonfinite'])) == (digest,s['pcm_f32le_sha256'],SR,N,2,N/SR,0), 'CSV incompatible con WAV')
                        for k,val in [('rms',levels[ch]),('peak',np.abs(y[:,ch]).max()),('tp4x',tp[ch])]:
                            close(val,float(row[k])); close(val,s[k][ch])
                    checked_wavs.add(name); waves[name]=x
                elif name in obs_by_path:
                    obs = obs_by_path[name]; a = np.load(BytesIO(buf),allow_pickle=False)
                    require(digest==obs['mask_npy_sha256'] and list(a.shape)==obs['shape'] and str(a.dtype)==obs['dtype'], 'Máscara no corresponde a la sonda')
                    require(np.isfinite(a).all() and a.min()>=0 and a.max()<=1, 'Máscara fuera de dominio')
                    masks[name]=a; checked_masks.add(name)
        require((count,raw_size)==(pack['files'],pack['raw_bytes']), 'Inventario de archivo comprimido')
        if path.name=='inputs.tar.xz':
            inputs=waves
            for role in ('Mix','V','I'):
                x=inputs[f'inputs/S2/{role}.wav']
                require(np.array_equal(x[:,::-1],inputs[f'inputs/S6/{role}.wav']), 'S6 no es swap exacto')
                for case,factor in [('S1',1),('S3',.25),('S7',-1)]:
                    y=inputs[f'inputs/{case}/{role}.wav']; require(np.array_equal(y[:,0]*factor,y[:,1]),f'Fixture inválido: {case}/{role}')
            for role,other in [('V','I'),('I','V')]:
                x=inputs[f'inputs/Ronly/{role}.wav']
                require(np.array_equal(x[:,0],inputs[f'inputs/S2/{role}.wav'][:,0]) and np.array_equal(x[:,1],inputs[f'inputs/S2/{other}.wav'][:,1]), 'Control unilateral no aislado')
        else:
            b = path.name.split('-')[1][0]; records={r['id']:r for r in data[b]['runs']}
            for r in records.values():
                if r['status']=='OK':
                    v,i = [waves[r['outputs'][k]['path']].astype('float64') for k in ('SDV','SDI')]
                    res = difference(v+i,inputs[r['inputs']['Mix']['path']])
                    for k in res: close(res[k],r['reconstruction'][k])
            for group in data[b]['contrasts'].values():
                for comp in [group] if 'a' in group else group.values():
                    check_contrast(comp,waves,masks,records)
    require(seen==set(digests) and checked_wavs==set(stats) and checked_masks==set(obs_by_path), 'Inventario incompleto')
    return dict(status='PASS_INTEGRITY', runs_completed=successes, runs_incomplete=failures,
                sources_identical=4, archives=5, archive_members_hashed=len(seen), json_inside_archives_parsed=native_json,
                wav_files_reopened=len(checked_wavs), csv_channel_rows=len(rows), actual_masks_reopened=len(checked_masks),
                reconstruction_and_paired_contrasts_recomputed=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sellar',action='store_true',help='registrar QC y hashes de una entrega nueva, después de las comprobaciones')
    seal = p.parse_args().sellar
    qc = verify_package()
    quality = ROOT/'results/control_calidad.json'
    sums = ROOT/'hashes/SHA256SUMS.txt'
    if seal: dump(quality,qc)
    require(qc==load(quality),'QC no coincide')
    paths = sorted(p for p in ROOT.rglob('*') if p.is_file() and p!=sums and not {'build','__pycache__'}.intersection(p.relative_to(ROOT).parts))
    txt = ''.join(f'{sha(p.read_bytes())}  {p.relative_to(ROOT).as_posix()}\n' for p in paths)
    if seal: sums.write_text(txt,encoding='utf-8')
    require(sums.read_text()==txt,'SHA256SUMS no corresponde al paquete')
    print(json.dumps(qc,indent=2))
    print(len(paths),'archivos de entrega verificados (sin autorreferencia).')


if __name__=='__main__':
    main()
