#!/usr/bin/env python3
"""Batería 6G.1 / AI-F: repetición COMPLETA de la batería AI (A1/A2, B1/B2,
C1/C2, D1/D2, E1 × Hardened/EVO/MQR = 27 casos) tras la corrección F
(`arr = None` después del bucle de flush() de memmaps; padre 2f4aae4).

Reutiliza SIN MODIFICARLOS el inyector (scripts/inyeccion_auditoria_6g1/
ejecutar_motor_auditoria.py) y el verificador de la batería AI
(scripts/pruebas_auditoria_cierre_6g1.py, sólo importado): mismas
comprobaciones, mismos argumentos de motor. La evidencia de la batería AI
(2f4aae4) no se sobrescribe: esta batería escribe con nombres nuevos.

Añade a cada caso una comprobación explícita del hallazgo F:
  hallazgo_F_resuelto — en la ENTRADA del registro del aborto no hay fd ni
  mapeo sobre masks/model_disagreement_map.npy y, si ese memmap llegó a
  crearse, su referencia débil está muerta (memmap liberado).
  (`aplica_F` indica si el memmap existió en ese caso.)

`--base DIR --etiqueta-base X` repite la batería sobre otra copia de los
motores (diagnóstico; no cambia el veredicto).
Evidencia: evidence/pruebas_correccion_f_6g1.json,
           evidence/matriz_correccion_f_6g1.csv,
           evidence/inyecciones_correccion_f_6g1/<motor>_<esc>.json
Salida 0 sólo si los 27 casos sobre los motores corregidos dan PASS.
"""
import argparse
import csv
import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
import pruebas_auditoria_cierre_6g1 as AI  # noqa: E402
from comun_6g1 import MOT, MOTORES, sha_file, entorno  # noqa: E402

EV = RAIZ / 'evidence'
AI.EV_INY = EV / 'inyecciones_correccion_f_6g1'
AI.TRABAJO = Path('/tmp/f6g1f')
RECURSO_F = AI.RECURSO_F
_verificar_ai = AI.verificar


def verificar_f(motor, esc, r):
    ch, extra = _verificar_ai(motor, esc, r)
    e = r['estado']
    inj = e.get('inyeccion') or {}
    fe = (e.get('fotos') or {}).get('entrada_abortar')
    if fe is not None and inj.get('provisional'):
        prov = inj['provisional']
        fds = [d for d in fe['descriptores_salida_o_entradas']
               if os.path.relpath(d['destino'], prov) == RECURSO_F]
        maps = [m for m in fe['mapeos_bajo_salida'] if os.path.relpath(m, prov) == RECURSO_F]
        mms = [m for m in fe['memmaps']
               if os.path.basename(m['ruta']) == os.path.basename(RECURSO_F)]
        ok = not fds and not maps and not any(m['vivo'] for m in mms)
        ch['hallazgo_F_resuelto'] = (ok, str(dict(aplica_F=bool(mms), fds=fds, mapeos=maps,
                                                  memmap_vivo=[m['vivo'] for m in mms]))[:700])
        extra['aplica_F'] = bool(mms)
    else:
        ch['hallazgo_F_resuelto'] = (False, 'sin fotografía de entrada al registro')
    return ch, extra


AI.verificar = verificar_f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=None)
    ap.add_argument('--etiqueta-base', default='base')
    a = ap.parse_args()
    res = dict(schema='pruebas-correccion-f-6g1/1', entorno=entorno(),
               commit_padre='2f4aae411ce1672ec9aa57cc9a967e0556631d85',
               correccion='arr = None tras el bucle de flush() de memmaps (Hardened/EVO '
                          'run_experiment; MQR _run_core)',
               motores_sha256={m: sha_file(MOT / n) for m, n in MOTORES.items()},
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               escenarios={k: dict(condicion=v[0], motivo=v[1], completo=v[2], trasladado=v[3],
                                   fallo_de_cierre=v[4], log_cerrado=v[5], inyeccion=v[6])
                           for k, v in AI.ESCENARIOS.items()},
               argumentos_motor='--mode full_processing [+ --keep-masks en Hardened/EVO sólo '
                                'en E1]; Mix = copia en la carpeta de trabajo (idénticos a AI)',
               verificador='pruebas_auditoria_cierre_6g1.verificar (sin cambios) + '
                           'hallazgo_F_resuelto')
    if a.base:
        bdir = Path(a.base).resolve()
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = AI.bateria(bdir, a.etiqueta_base)
        res['diagnostico_base'] = dict(
            etiqueta=a.etiqueta_base, carpeta=str(bdir),
            motores_sha256={m: sha_file(bdir / n) for m, n in MOTORES.items()},
            filas=fb, detalle=db,
            resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb), total=len(fb)))
    print('== motores corregidos (%s)' % MOT)
    if AI.EV_INY.exists():
        shutil.rmtree(AI.EV_INY)
    filas, det = AI.bateria(MOT, 'corregido', guardar_estados=True)
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas),
                            casos_donde_aplica_F=sum(bool(d.get('aplica_F')) for d in det.values()),
                            hallazgo_F_resuelto=sum(d['comprobaciones']['hallazgo_F_resuelto']['ok']
                                                    for d in det.values())))
    EV.mkdir(parents=True, exist_ok=True)
    (EV / 'pruebas_correccion_f_6g1.json').write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    bidx = {(f['prueba'], f['motor']): f for f in res.get('diagnostico_base', {}).get('filas', [])}
    with open(EV / 'matriz_correccion_f_6g1.csv', 'w', newline='', encoding='utf-8') as fh:
        cols = ['prueba', 'motor', 'condicion', 'codigo', 'completo', 'log_cerrado', 'trasladado',
                'aplica_F', 'hallazgo_F_resuelto', 'comprobaciones', 'fallos', 'veredicto',
                'codigo_base', 'comprobaciones_base', 'veredicto_base', 'fallos_base']
        wr = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        wr.writeheader()
        for f in filas:
            d = det['%s/%s' % (f['motor'], f['prueba'])]
            b = bidx.get((f['prueba'], f['motor']), {})
            wr.writerow(dict(f, aplica_F=bool(d.get('aplica_F')),
                             hallazgo_F_resuelto=d['comprobaciones']['hallazgo_F_resuelto']['ok'],
                             codigo_base=b.get('codigo', ''),
                             comprobaciones_base=b.get('comprobaciones', ''),
                             veredicto_base=b.get('veredicto', ''), fallos_base=b.get('fallos', '')))
    print('RESUMEN corregido: %d/%d PASS (F aplica en %d casos; F resuelto en %d/%d)'
          % (res['resumen']['pass_'], res['resumen']['total'],
             res['resumen']['casos_donde_aplica_F'], res['resumen']['hallazgo_F_resuelto'],
             res['resumen']['total']))
    if 'diagnostico_base' in res:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base,
                                                res['diagnostico_base']['resumen']['pass_'],
                                                res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
