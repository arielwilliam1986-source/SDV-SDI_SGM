#!/usr/bin/env python3
"""Verificación estática (AST) de que la corrección del ciclo de vida 6G.1
no toca el DSP.

Compara cada motor 6G.1 del árbol de trabajo con su versión en un commit base
(por defecto 594a90f, padre de la corrección):
  - funciones/clases de nivel superior cambiadas, añadidas o eliminadas;
  - sentencias de nivel superior (no def/class) distintas;
  - en cada función cambiada: literales numéricos (multiconjunto) y
    llamadas DSP (conteo por nombre), con los MISMOS extractores
    `_numeros` y `_llamadas_dsp` de `no_regresion_dsp_6g1.py` (sólo
    importados; ese script no se modifica ni se ejecuta);
  - funciones DSP conocidas (analyze_guide_scale, CandidateRunner, ...):
    AST idéntico.

Uso (desde la raíz del repositorio):
    python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_ciclo_vida_6g1.py [BASE]
Evidencia: ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_ciclo_vida_6g1.json
Salida 0 sólo si: ninguna def añadida/eliminada, las defs cambiadas son
exactamente las del ciclo de vida, y en todas ellas literales y llamadas DSP
son iguales.
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

BASE_DEF = '594a90f18c42139dcc7e753633afe33cb89cc752'
MOTORES = {'Hardened': 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
           'EVO': 'MOTOR_SEP_SDV-SDI_EVO.py',
           'MQR': 'sdv_sdi_mqr_engine.py'}
# Defs de ciclo de vida autorizadas a cambiar (contrato de retorno + aborto).
PERMITIDAS = {'Hardened': {'run_experiment'},
              'EVO': {'run_experiment'},
              'MQR': {'run_experiment', '_run_core'}}


def defs(src):
    t = ast.parse(src)
    d, otros = {}, []
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            d[n.name] = n
        else:
            otros.append(n)
    return d, otros


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else BASE_DEF
    res = dict(schema='ast-ciclo-vida-6g1/1', base=base, motores={})
    ok_global = True
    for m, f in MOTORES.items():
        rel = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/' + f
        src_a = subprocess.run(['git', 'show', '%s:%s' % (base, rel)], cwd=str(REPO),
                               capture_output=True, text=True, check=True).stdout
        src_b = (REPO / rel).read_text(encoding='utf-8')
        a, oa = defs(src_a)
        b, ob = defs(src_b)
        da = [ast.dump(x) for x in oa]
        db = [ast.dump(x) for x in ob]
        cambiadas = sorted(k for k in a if k in b and ast.dump(a[k]) != ast.dump(b[k]))
        otras = [ast.unparse(x)[:300] for x, s in zip(ob, db) if s not in da]
        det = {}
        for k in cambiadas:
            na, nb = _numeros(a[k])[0], _numeros(b[k])[0]
            la, lb = _llamadas_dsp(a[k]), _llamadas_dsp(b[k])
            det[k] = dict(literales_iguales=na == nb, llamadas_dsp_iguales=la == lb,
                          llamadas_dsp=lb)
        sin_cambio = sorted(k for k in a if k in b and k not in cambiadas)
        ok = (not (set(b) - set(a)) and not (set(a) - set(b))
              and set(cambiadas) == PERMITIDAS[m]
              and all(v['literales_iguales'] and v['llamadas_dsp_iguales']
                      for v in det.values())
              and all(isinstance(x, (ast.Import, ast.ImportFrom))
                      for x, s in zip(ob, db) if s not in da))
        ok_global &= ok
        res['motores'][m] = dict(
            archivo=rel, defs_cambiadas=cambiadas, defs_añadidas=sorted(set(b) - set(a)),
            defs_eliminadas=sorted(set(a) - set(b)), defs_sin_cambio=len(sin_cambio),
            otras_sentencias_cambiadas=otras, detalle_defs_cambiadas=det,
            veredicto='OK' if ok else 'FALLO')
        print('%-8s cambiadas=%s añadidas=%s eliminadas=%s otras=%d sin_cambio=%d -> %s'
              % (m, cambiadas, sorted(set(b) - set(a)), sorted(set(a) - set(b)),
                 len(otras), len(sin_cambio), 'OK' if ok else 'FALLO'))
        for k, v in det.items():
            print('    %-16s literales_iguales=%s llamadas_dsp_iguales=%s'
                  % (k, v['literales_iguales'], v['llamadas_dsp_iguales']))
    res['veredicto'] = 'OK' if ok_global else 'FALLO'
    out = RAIZ / 'evidence' / 'ast_ciclo_vida_6g1.json'
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('VEREDICTO:', res['veredicto'])
    return 0 if ok_global else 1


if __name__ == '__main__':
    sys.exit(main())
