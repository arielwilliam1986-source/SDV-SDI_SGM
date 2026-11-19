"""No regresión DSP 6G: estructura y muestras frente a las fuentes 6F.

1. AST: qué definiciones y constantes cambian entre 6F y 6G.
2. PCM: mismo Mix WAV procesado por 6F y por 6G en cada motor -> salidas
   idénticas byte a byte (float64) y misma geometría.
3. Informe: secciones DSP comparadas tras descartar metadatos volátiles.
"""
import ast
import csv
import json
import sys
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g import (EV, HERE, MOTORES, SIX, Cronometro, dump, ejecutar,
                      entorno, sha_file)

FIX = HERE / 'fixtures'

DSP_PERMITIDO = set()  # ninguna función DSP puede cambiar
VOLATILES = {'document_meta', 'mix_original', 'guide_inventory',
             'guide_family_inventory', 'guide_variant_inventory',
             'input_integrity', 'post_wav_validation'}


def defs_y_constantes(path):
    arbol = ast.parse(Path(path).read_text(encoding='utf-8'))
    defs, consts = {}, {}
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defs[nodo.name] = ast.dump(nodo)
        elif isinstance(nodo, ast.Assign):
            for t in nodo.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    try:
                        consts[t.id] = ast.literal_eval(nodo.value)
                    except Exception:
                        consts[t.id] = ast.dump(nodo.value)
    return defs, consts


def normalizar(obj):
    if isinstance(obj, dict):
        return {k: normalizar(v) for k, v in obj.items() if k not in VOLATILES}
    if isinstance(obj, list):
        return [normalizar(v) for v in obj]
    return obj


def main():
    trabajo = Path('/tmp/f6g/noreg')
    rutas = dict(vocal=str(FIX / 'vocal.wav'), instrumental=str(FIX / 'instrumental.wav'),
                 mix=str(FIX / 'mix.wav'))
    filas = []
    comparaciones = {}
    with Cronometro() as cron:
        for motor, nombre in MOTORES.items():
            d6f, c6f = defs_y_constantes(SIX / nombre)
            d6g, c6g = defs_y_constantes(HERE / 'motores' / nombre)
            cambiadas = sorted(k for k in d6f if k in d6g and d6f[k] != d6g[k])
            anadidas = sorted(set(d6g) - set(d6f))
            quitadas = sorted(set(d6f) - set(d6g))
            const_cambiadas = {k: dict(antes=c6f[k], ahora=c6g[k])
                               for k in c6f if k in c6g and c6f[k] != c6g[k]}
            identicas = sum(1 for k in d6f if k in d6g and d6f[k] == d6g[k])
            dsp_tocadas = sorted(set(cambiadas) & DSP_PERMITIDO) if DSP_PERMITIDO else []
            comparaciones[f'{motor}/ast'] = dict(
                cambiadas=cambiadas, anadidas=anadidas, quitadas=quitadas,
                constantes_cambiadas=const_cambiadas, defs_identicas=identicas,
                dsp_tocadas=dsp_tocadas)

            r6f = ejecutar(motor, rutas, trabajo / f'{motor}_6f', 'full_processing', version='6f')
            r6g = ejecutar(motor, rutas, trabajo / f'{motor}_6g', 'full_processing')
            pcm_igual = r6f['pcm'] == r6g['pcm'] and r6f['shapes'] == r6g['shapes']
            rep_igual = normalizar(r6f['report_obj']) == normalizar(r6g['report_obj'])
            comparaciones[f'{motor}/pcm'] = dict(
                pcm_igual=pcm_igual, informe_igual=rep_igual,
                pcm_6f=r6f['pcm'], pcm_6g=r6g['pcm'],
                shapes_6f=r6f['shapes'], shapes_6g=r6g['shapes'],
                exit_6f=r6f['exit'], exit_6g=r6g['exit'])
            filas.append(dict(motor=motor, defs_cambiadas=';'.join(cambiadas),
                              defs_anadidas=';'.join(anadidas),
                              defs_quitadas=';'.join(quitadas),
                              constantes=';'.join(sorted(const_cambiadas)),
                              defs_identicas=identicas,
                              pcm_6f_vs_6g='IDENTICO' if pcm_igual else 'DISTINTO',
                              informe_igual=rep_igual))

    EV.mkdir(exist_ok=True)
    with (EV / 'matriz_no_regresion_6g.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]), lineterminator='\n')
        w.writeheader()
        w.writerows(filas)
    dump(EV / 'no_regresion_6g.json', dict(
        seconds=cron.seconds, maxrss_kib=cron.maxrss_kib, entorno=entorno(),
        comparaciones=comparaciones, filas=filas,
        resumen=dict(motores_con_pcm_identico=sum(
                        1 for f in filas if f['pcm_6f_vs_6g'] == 'IDENTICO'),
                     motores_con_informe_igual=sum(
                        1 for f in filas if f['informe_igual']), total=len(filas))))
    for f in filas:
        print(f"{f['motor']}: cambiadas={f['defs_cambiadas'] or '-'} "
              f"añadidas={f['defs_anadidas'] or '-'} constantes={f['constantes'] or '-'} "
              f"pcm={f['pcm_6f_vs_6g']} informe={f['informe_igual']}")


if __name__ == '__main__':
    main()
