"""Matriz 6G por motor, modo y contenedor.

Comprueba que un Mix WAV y su FLAC equivalente (mismas muestras PCM) recorren el
mismo camino y producen las mismas salidas. No se acepta como prueba el mero
exit code: se comparan PCM de salida, geometría, alineación y secciones DSP del
informe.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import (EV, HERE, MOTORES, SINGLE_MODE, Cronometro, dump,
                      ejecutar, entorno, sha_file)

FIX = HERE / 'fixtures'
VOLATILES = {'document_meta', 'mix_original', 'guide_inventory',
             'guide_family_inventory', 'guide_variant_inventory',
             'input_integrity', 'post_wav_validation', 'input_integrity_6g'}


def _resumen_integridad(d):
    """Reduce el bloque de integridad a lo comparable entre contenedores."""
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        if k == 'same_descriptor_read':
            out[k] = v
        elif k.endswith('_unchanged_on_close'):
            out[k] = bool(v)
        elif k.endswith('_after'):
            out[k] = bool(v.get('unchanged')) if isinstance(v, dict) else v
        elif k in ('error', 'policy'):
            out[k] = v
    return out


def normalizar(obj, marcas):
    if isinstance(obj, dict):
        if 'integrity' in obj:
            obj = dict(obj)
            obj['integrity'] = _resumen_integridad(obj['integrity'])
        return {k: normalizar(v, marcas) for k, v in obj.items() if k not in VOLATILES}
    if isinstance(obj, list):
        return [normalizar(v, marcas) for v in obj]
    if isinstance(obj, str):
        for m in marcas:
            if m and m in obj:
                return '<MIX>'
        return obj
    return obj


def comparar(a, b, marcas):
    na, nb = normalizar(a, marcas), normalizar(b, marcas)
    if na == nb:
        return True, []
    difs = []

    def walk(x, y, ruta=''):
        if type(x) is not type(y):
            difs.append(f'{ruta}: tipo {type(x).__name__} vs {type(y).__name__}')
        elif isinstance(x, dict):
            for k in sorted(set(x) | set(y)):
                if k not in x:
                    difs.append(f'{ruta}.{k}: sólo en FLAC')
                elif k not in y:
                    difs.append(f'{ruta}.{k}: sólo en WAV')
                else:
                    walk(x[k], y[k], f'{ruta}.{k}')
        elif isinstance(x, list):
            if len(x) != len(y):
                difs.append(f'{ruta}: longitud {len(x)} vs {len(y)}')
            else:
                for idx, (xi, yi) in enumerate(zip(x, y)):
                    walk(xi, yi, f'{ruta}[{idx}]')
        elif x != y:
            difs.append(f'{ruta}: {x!r} vs {y!r}')

    walk(na, nb)
    return False, difs[:25]


def main():
    trabajo = Path('/tmp/f6g/motores')
    rutas = dict(vocal=str(FIX / 'vocal.wav'), instrumental=str(FIX / 'instrumental.wav'))
    antes = {p.name: sha_file(p) for p in FIX.iterdir() if p.is_file()}

    xw, srw = sf.read(FIX / 'mix.wav', dtype='float64', always_2d=True)
    xf, srf = sf.read(FIX / 'mix.flac', dtype='float64', always_2d=True)
    entrada_igual = bool(np.array_equal(xw, xf) and srw == srf)

    filas = []
    detalle = {}
    with Cronometro() as cron:
        for motor in MOTORES:
            for modo in ('dry_run', 'analysis_only', 'single', 'full_processing'):
                modo_cli = SINGLE_MODE[motor] if modo == 'single' else modo
                res = {}
                for cont, archivo in (('wav', 'mix.wav'), ('flac', 'mix.flac')):
                    mix = dict(rutas, mix=str(FIX / archivo))
                    r = ejecutar(motor, mix, trabajo / f'{motor}_{modo}_{cont}',
                                 modo_cli)
                    res[cont] = r
                    filas.append(dict(
                        motor=motor, modo=modo_cli, contenedor=cont,
                        exit=r['exit'], wavs=r['wavs'], report=r['report'],
                        attribution=r['attribution'], k=r['k'],
                        seconds=r['seconds'],
                        container_6g=(r['input_integrity_6g'] or {}).get('container'),
                        pcm_sdv=r['pcm'].get('mix SDV.wav') or r['pcm'].get('SDV.wav'),
                        pcm_sdi=r['pcm'].get('mix SDI.wav') or r['pcm'].get('SDI.wav'),
                        geometry=json.dumps(r['shapes'], sort_keys=True)))
                marcas = [str(FIX / 'mix.wav'), str(FIX / 'mix.flac'), 'mix.wav', 'mix.flac']
                ok_rep, difs = comparar(res['wav']['report_obj'], res['flac']['report_obj'], marcas)
                igual_pcm = res['wav']['pcm'] == res['flac']['pcm']
                igual_geo = res['wav']['shapes'] == res['flac']['shapes']
                igual_ext = (res['wav']['exit'] == res['flac']['exit']
                             and res['wav']['wavs'] == res['flac']['wavs'])
                igual_align = (res['wav']['attribution'] == res['flac']['attribution']
                               and res['wav']['k'] == res['flac']['k'])
                detalle[f'{motor}/{modo_cli}'] = dict(
                    pcm_igual=igual_pcm, geometria_igual=igual_geo,
                    exit_y_wavs_iguales=igual_ext, alineacion_igual=igual_align,
                    informe_igual=ok_rep, diferencias_informe=difs,
                    pcm=res['wav']['pcm'], shapes=res['wav']['shapes'],
                    attribution=res['wav']['attribution'], k=res['wav']['k'])

    despues = {p.name: sha_file(p) for p in FIX.iterdir() if p.is_file()}
    intactos = antes == despues

    EV.mkdir(exist_ok=True)
    with (EV / 'matriz_motores_6g.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    n_ok = sum(1 for d in detalle.values()
               if all(d[k] for k in ('pcm_igual', 'geometria_igual',
                                     'exit_y_wavs_iguales', 'alineacion_igual',
                                     'informe_igual')))
    dump(EV / 'motores_6g.json', dict(
        seconds=cron.seconds, maxrss_kib=cron.maxrss_kib, entorno=entorno(),
        entrada_decodificada_identica=entrada_igual,
        fixtures_intactos=intactos, detalle=detalle, filas=filas,
        resumen=dict(combinaciones_identicas=n_ok, total=len(detalle),
                     entrada_decodificada_identica=entrada_igual,
                     fixtures_intactos=intactos)))

    print(f'combinaciones motor×modo: {n_ok}/{len(detalle)} con salidas idénticas')
    print('entrada decodificada idéntica:', entrada_igual, '| fixtures intactos:', intactos)
    for k, d in detalle.items():
        if not all(d[x] for x in ('pcm_igual', 'geometria_igual', 'exit_y_wavs_iguales',
                                  'alineacion_igual', 'informe_igual')):
            print('DIF', k, {x: d[x] for x in ('pcm_igual', 'geometria_igual',
                                               'exit_y_wavs_iguales', 'alineacion_igual',
                                               'informe_igual')}, d['diferencias_informe'][:5])


if __name__ == '__main__':
    main()
