"""Contrastes pareados dentro de cada motor y medidas L/R, incluidos artefactos abortados."""
import csv
from pathlib import Path

import numpy as np

from medidas import ROOT, WORK, difference, dump, load, read, wav_stats
from pruebas_s5 import RESULTS


def effective_mask(r):
    mask = np.load(WORK/r['applied_mask'], allow_pickle=False)
    return np.broadcast_to(mask, (2, *mask.shape[-2:]))


def compare(a, b, swap=False):
    """Compara A con B sin mover muestras; en S6 sólo invierte el eje L/R de B."""
    res = dict(a=a['id'], b=b['id'], swap_b=swap)
    if a['status'] != 'OK' or b['status'] != 'OK':
        return dict(**res, status='UNKNOWN', reason='Falta una corrida completada')
    for role in ('SDV','SDI'):
        x, y = [read(WORK/r['outputs'][role]['path']) for r in [a,b]]
        res[role] = difference(x,y[:,::-1] if swap else y)
    ma, mb = effective_mask(a), effective_mask(b)
    d = ma - (mb[::-1] if swap else mb)
    res['mask'] = dict(rms=np.sqrt((d**2).mean(axis=(1,2))).tolist(), max_abs=np.abs(d).max(axis=(1,2)).tolist())
    return dict(**res, status='EXPERIMENTAL_RESULT')


def csv_rows(block, series, case, mode, role, status, stats, reconstruction=None):
    for ch, label in enumerate(('L','R')):
        row = dict(block=block, series=series, case=case, mode=mode, role=role, status=status, channel=label)
        for key in ('path','sha256','pcm_f32le_sha256','sr','channels','frames','seconds','subtype','corr_LR','rms_R_over_L','rms_L_minus_R','max_abs_L_minus_R'):
            row[key] = stats.get(key)
        for key in ('rms','peak','tp4x','nonfinite'):
            row[key] = stats.get(key,[None,None])[ch]
        for key in ('rms','max_abs'):
            row['reconstruction_'+key] = reconstruction[key][ch] if reconstruction else None
        yield row


def main():
    rows = []
    catalog = load(ROOT/'signals/manifest.json')
    for path, s in catalog['audio'].items():
        p = Path(path)
        rows.extend(csv_rows('input','fixture',p.parent.name,'',p.stem,'INPUT',s))
    logs = []
    for block, name in RESULTS.items():
        path = ROOT/'results'/(name+'.json')
        data = load(path)
        runs = data['runs']
        r = {v['id']:v for v in runs}
        tests = {'mode_per_channel_vs_mono':{},'swap_S6_vs_S2':{},'Ronly_vs_S2':{}}
        for case in [f'S{n}' for n in range(1,8)]:
            if block!='D':
                tests['mode_per_channel_vs_mono'][case] = compare(r[case+'_per_channel'],r[case+'_mono'])
        for mode in (['shared'] if block=='D' else ['per_channel','mono']):
            ref = r['S2_'+mode]
            tests['swap_S6_vs_S2'][mode] = compare(r['S6_'+mode],ref,True)
            tests['Ronly_vs_S2'][mode] = compare(r['Ronly_'+mode+'_unilateral'],ref)
        if block=='C':
            pos = r['Ppos_per_channel_polaridad']
            tests['polarity_control'] = compare(r['Pneg_per_channel_polaridad'],pos)
            tests['hybrid_control'] = compare(r['Ppos_per_channel_hybrid'],pos)
        data['contrasts'] = tests
        for item in runs:
            log = (WORK/item['log']).read_text(errors='replace')
            logs.append((item['utc'],f"\n===== {block}/{item['id']} | {item['utc']} | {item['status']} | exit={item['engine_exit']} =====\n{log}"))
            stats = item.get('outputs',{})
            if item['status']!='OK':
                # Medir los artefactos del aborto sin convertir un fallo en éxito.
                stats = {p.stem:wav_stats(p) for p in sorted((WORK/item['log']).parent.rglob('*.wav'))}
                item['aborted_wavs_not_completed_outputs'] = stats
                (ROOT/'logs'/f"aborto_{block}_{item['id']}.log").write_text(log)
            for role, s in stats.items():
                rows.extend(csv_rows(block,item['series'],item['case'],item['mode'],role,item['status'],s,item.get('reconstruction')))
        dump(path,data)
    mdir = ROOT/'measurements'
    mdir.mkdir(exist_ok=True)
    with (mdir/'resultados.csv').open('w', newline='', encoding='utf-8') as out:
        w = csv.DictWriter(out,fieldnames=rows[0],lineterminator='\n')
        w.writeheader(); w.writerows(rows)
    (ROOT/'logs/ejecucion_completa.log').write_text('Agrupado por corrida, en orden de inicio UTC. Consola original, sin reinterpretar las etiquetas nativas.\n'+''.join(v for _,v in sorted(logs)))
    print(len(rows),'filas de canal;',len(logs),'corridas documentadas')


if __name__ == '__main__':
    main()
