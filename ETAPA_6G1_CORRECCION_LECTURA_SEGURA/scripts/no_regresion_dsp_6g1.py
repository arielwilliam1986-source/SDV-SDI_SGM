"""Prueba 10: no regresión DSP de 6G.1 frente a 6G.

1. AST: definiciones y constantes que cambian entre la copia 6G y la 6G.1.
2. Huella DSP de cada definición tocada: literales numéricos y llamadas a
   primitivas DSP deben ser idénticos; sólo puede variar la gestión de lectura.
3. PCM: mismo Mix (WAV y FLAC) procesado por 6G y por 6G.1 en cada motor ->
   archivos reales, mismos hashes PCM y misma geometría.
"""
import ast
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g1 import (EV, FIX, G6, MOT, MOTORES, dump, ejecutar, entorno)

VOLATILES = {'document_meta', 'mix_original', 'guide_inventory',
             'guide_family_inventory', 'guide_variant_inventory',
             'input_integrity', 'input_integrity_6g', 'post_wav_validation',
             'container_6g'}

DSP = {'fft', 'ifft', 'rfft', 'irfft', 'hann', 'hanning', 'stft', 'istft',
       'sqrt', 'exp', 'log', 'log1p', 'abs', 'angle', 'power', 'maximum',
       'minimum', 'where', 'clip', 'sum', 'mean', 'median', 'convolve',
       'asarray', 'array', 'zeros', 'ones', 'empty', 'stack', 'einsum',
       'dot', 'matmul', 'sign', 'real', 'imag', 'conj', 'cumsum', 'rms',
       'percentile', 'interp', 'pad', 'resample_poly', 'float64', 'float32'}
NUEVOS_6G1 = ('6g1', '_abrir_mix', 'abortar_6g1', 'ruta_lectura',
              'ruta_apunta_al_mismo_objeto', 'verificar', 'MixCambiado',
              'close_tee', '_check_unchanged_6g', 'ABORT_6G1')


def _defs(path):
    arbol = ast.parse(Path(path).read_text(encoding='utf-8'))
    defs, consts = {}, {}
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[nodo.name] = nodo
        elif isinstance(nodo, ast.Assign):
            for t in nodo.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    try:
                        consts[t.id] = ast.literal_eval(nodo.value)
                    except Exception:
                        consts[t.id] = 'NO_LITERAL'
    return arbol, defs, consts


def _numeros(nodo):
    vals = []
    for n in ast.walk(nodo):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) \
                and not isinstance(n.value, bool):
            vals.append(round(float(n.value), 12))
        elif isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub) \
                and isinstance(n.operand, ast.Constant) \
                and isinstance(n.operand.value, (int, float)):
            vals.append(round(-float(n.operand.value), 12))
    return sorted(vals)


def _llamadas_dsp(nodo):
    nombres = []
    for n in ast.walk(nodo):
        if isinstance(n, ast.Call):
            f = n.func
            es_atributo = isinstance(f, ast.Attribute)
            nombre = f.attr if es_atributo else getattr(f, 'id', '')
            # `log(...)` sin punto es el registro del motor, no np.log
            if nombre in DSP and (es_atributo or nombre != 'log'):
                nombres.append(nombre)
    return sorted(nombres)


def normalizar(obj):
    if isinstance(obj, dict):
        return {k: normalizar(v) for k, v in obj.items() if k not in VOLATILES}
    if isinstance(obj, list):
        return [normalizar(v) for v in obj]
    return obj


def main():
    trabajos = Path('/tmp/f6g1/noreg')
    filas, detalles = [], {}
    for motor, nombre in MOTORES.items():
        _, d6g, c6g = _defs(G6 / nombre)
        _, d6g1, c6g1 = _defs(MOT / nombre)
        cambiadas = sorted(k for k in d6g if k in d6g1
                           and ast.dump(d6g[k]) != ast.dump(d6g1[k]))
        anadidas = sorted(set(d6g1) - set(d6g))
        quitadas = sorted(set(d6g) - set(d6g1))
        const_cambiadas = {k: [c6g[k], c6g1[k]] for k in c6g
                           if k in c6g1 and c6g[k] != c6g1[k]}
        huellas = {}
        for k in cambiadas:
            num_a, num_b = _numeros(d6g[k]), _numeros(d6g1[k])
            dsp_a, dsp_b = _llamadas_dsp(d6g[k]), _llamadas_dsp(d6g1[k])
            huellas[k] = dict(numeros_iguales=num_a == num_b,
                              numeros_6g=num_a, numeros_6g1=num_b,
                              llamadas_dsp_iguales=dsp_a == dsp_b,
                              llamadas_6g=dsp_a, llamadas_6g1=dsp_b)
        dsp_ok = (not const_cambiadas and not quitadas
                  and all(h['numeros_iguales'] and h['llamadas_dsp_iguales']
                          for h in huellas.values()))

        pcm = {}
        for contenedor, archivo in (('WAV', 'mix.wav'), ('FLAC', 'mix.flac')):
            r6g = ejecutar(motor, dict(mix=str(FIX / archivo),
                                       vocal=str(FIX / 'vocal_mix.wav'),
                                       instrumental=str(FIX / 'instrumental_mix.wav')),
                           trabajos / f'{motor}_{contenedor}_6g', 'full_processing',
                           version='6g')
            r61 = ejecutar(motor, dict(mix=str(FIX / archivo),
                                       vocal=str(FIX / 'vocal_mix.wav'),
                                       instrumental=str(FIX / 'instrumental_mix.wav')),
                           trabajos / f'{motor}_{contenedor}_6g1', 'full_processing')
            p6g = {p['name']: p['pcm_sha256'] for p in r6g['pcm'] if 'pcm_sha256' in p}
            p61 = {p['name']: p['pcm_sha256'] for p in r61['pcm'] if 'pcm_sha256' in p}
            reales = bool(p6g) and bool(p61)
            pcm[contenedor] = dict(
                pcm_6g=p6g, pcm_6g1=p61, reales=reales,
                identicos=(reales and p6g == p61),
                exit_6g=r6g['exit'], exit_6g1=r61['exit'],
                informe_igual=normalizar(r6g['report']) == normalizar(r61['report']))

        veredicto = 'ACCEPTED' if (dsp_ok and all(
            v['identicos'] for v in pcm.values())) else 'REJECTED'
        detalles[motor] = dict(cambiadas=cambiadas, anadidas=anadidas,
                               quitadas=quitadas,
                               constantes_cambiadas=const_cambiadas,
                               huellas=huellas, dsp_ok=dsp_ok, pcm=pcm,
                               veredicto=veredicto)
        filas.append(dict(motor=motor, defs_cambiadas=';'.join(cambiadas),
                          defs_anadidas=';'.join(anadidas),
                          defs_quitadas=';'.join(quitadas),
                          constantes_cambiadas=';'.join(sorted(const_cambiadas)),
                          huella_dsp_ok=dsp_ok,
                          pcm_wav='IDENTICO' if pcm['WAV']['identicos'] else 'DISTINTO',
                          pcm_flac='IDENTICO' if pcm['FLAC']['identicos'] else 'DISTINTO',
                          veredicto=veredicto))

    EV.mkdir(parents=True, exist_ok=True)
    with (EV / 'no_regresion_dsp_6g1.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    dump(EV / 'no_regresion_dsp_6g1.json', dict(
        schema='no-regresion-dsp-6g1/1', entorno=entorno(),
        fuentes_6g=str(G6), fuentes_6g1=str(MOT),
        motores=detalles, filas=filas,
        resumen=dict(aprobados=sum(1 for f in filas if f['veredicto'] == 'ACCEPTED'),
                     total=len(filas))))
    for f in filas:
        print(f"{f['motor']}: cambiadas={f['defs_cambiadas'] or '-'} "
              f"añadidas={f['defs_anadidas'] or '-'} eliminadas={f['defs_quitadas'] or '-'} "
              f"constantes={f['constantes_cambiadas'] or '-'} "
              f"huella={f['huella_dsp_ok']} pcm_wav={f['pcm_wav']} "
              f"pcm_flac={f['pcm_flac']} -> {f['veredicto']}")


if __name__ == '__main__':
    main()
