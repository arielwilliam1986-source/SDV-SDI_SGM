#!/usr/bin/env python3
"""Verificación estática (AST) de la corrección CR (cierre determinista de
recursos): el DSP permanece intacto.

Reutiliza `defs`, MOTORES y PERMITIDAS de verificar_ast_ciclo_vida_6g1.py,
que sólo se importan: ese script y su evidencia (c38d00d) no se modifican ni
se ejecutan. Los extractores `_numeros`/`_llamadas_dsp` vienen de
no_regresion_dsp_6g1.py, también sólo importados.

Compara cada motor del árbol de trabajo con dos bases:
  - c38d00d: el cambio de esta corrección;
  - 594a90f: el cambio acumulado desde antes de CV.
Para cada base informa:
  - defs cambiadas, añadidas y eliminadas;
  - sentencias de nivel superior distintas (sólo se admiten imports);
  - literales numéricos y llamadas DSP en cada def cambiada;
  - lista de defs DSP con AST idéntico.
Además resume los cambios en `lectura_segura_6g1.py`: defs añadidas y
cambiadas. Ese módulo no contiene DSP.

Uso (desde la raíz del repo):
    python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_cierre_recursos_6g1.py
Evidencia: ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_cierre_recursos_6g1.json
"""
import ast
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
REPO = RAIZ.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from no_regresion_dsp_6g1 import _numeros, _llamadas_dsp  # noqa: E402
from verificar_ast_ciclo_vida_6g1 import defs, MOTORES, PERMITIDAS  # noqa: E402

BASES = {'c38d00d': 'c38d00d505c6b359585fe7f474a21fd3ab272b4b',
         '594a90f': '594a90f18c42139dcc7e753633afe33cb89cc752'}
DSP_DEFS = ('analyze_guide_scale', 'CandidateRunner', 'OlaStream', 'stft_span_frames',
            'compute_vocal_mask', 'consensus_from_masks', 'confidence_and_disagreement',
            'apply_sfumato_smoothing', 'read_span', 'mono_downmix', 'FramePlan',
            'post_wav_identity', 'build_band_masks')


def fuente(base, rel):
    return subprocess.run(['git', 'show', '%s:%s' % (base, rel)], cwd=str(REPO),
                          capture_output=True, text=True, check=True).stdout


def comparar(base, m, f):
    rel = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/' + f
    a, oa = defs(fuente(base, rel))
    b, ob = defs((REPO / rel).read_text(encoding='utf-8'))
    da, db = [ast.dump(x) for x in oa], [ast.dump(x) for x in ob]
    cambiadas = sorted(k for k in a if k in b and ast.dump(a[k]) != ast.dump(b[k]))
    otras = [x for x, s in zip(ob, db) if s not in da]
    det = {}
    for k in cambiadas:
        det[k] = dict(literales_iguales=_numeros(a[k])[0] == _numeros(b[k])[0],
                      llamadas_dsp_iguales=_llamadas_dsp(a[k]) == _llamadas_dsp(b[k]))
    dsp = {k: (k in a and k in b and ast.dump(a[k]) == ast.dump(b[k]))
           for k in DSP_DEFS if k in a or k in b}
    ok = (not (set(b) - set(a)) and not (set(a) - set(b))
          and set(cambiadas) <= PERMITIDAS[m]
          and all(v['literales_iguales'] and v['llamadas_dsp_iguales'] for v in det.values())
          and all(isinstance(x, (ast.Import, ast.ImportFrom)) for x in otras)
          and all(dsp.values()))
    return dict(defs_cambiadas=cambiadas, defs_añadidas=sorted(set(b) - set(a)),
                defs_eliminadas=sorted(set(a) - set(b)),
                defs_sin_cambio=len([k for k in a if k in b and k not in cambiadas]),
                otras_sentencias_cambiadas=[ast.unparse(x)[:400] for x in otras],
                detalle_defs_cambiadas=det, defs_dsp_identicas=dsp,
                veredicto='OK' if ok else 'FALLO')


def modulo(base):
    rel = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py'
    a, _ = defs(fuente(base, rel))
    b, _ = defs((REPO / rel).read_text(encoding='utf-8'))
    return dict(defs_añadidas=sorted(set(b) - set(a)), defs_eliminadas=sorted(set(a) - set(b)),
                defs_cambiadas=sorted(k for k in a if k in b and ast.dump(a[k]) != ast.dump(b[k])))


def main():
    res = dict(schema='ast-cierre-recursos-6g1/1', bases=BASES, motores={}, modulo={})
    ok_global = True
    for etq, base in BASES.items():
        for m, f in MOTORES.items():
            r = comparar(base, m, f)
            res['motores'].setdefault(m, {})[etq] = r
            ok_global &= r['veredicto'] == 'OK'
            print('%-8s vs %s: cambiadas=%s añadidas=%s eliminadas=%s otras=%d dsp_identicas=%d/%d -> %s'
                  % (m, etq, r['defs_cambiadas'], r['defs_añadidas'], r['defs_eliminadas'],
                     len(r['otras_sentencias_cambiadas']), sum(r['defs_dsp_identicas'].values()),
                     len(r['defs_dsp_identicas']), r['veredicto']))
            for k, v in r['detalle_defs_cambiadas'].items():
                print('    %-16s literales_iguales=%s llamadas_dsp_iguales=%s'
                      % (k, v['literales_iguales'], v['llamadas_dsp_iguales']))
        res['modulo'][etq] = modulo(base)
        print('lectura_segura_6g1 vs %s: %s' % (etq, res['modulo'][etq]))
    res['veredicto'] = 'OK' if ok_global else 'FALLO'
    out = RAIZ / 'evidence' / 'ast_cierre_recursos_6g1.json'
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('VEREDICTO:', res['veredicto'])
    return 0 if ok_global else 1


if __name__ == '__main__':
    sys.exit(main())
