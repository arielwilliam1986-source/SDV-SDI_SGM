#!/usr/bin/env python3
"""Verificación estática (AST) de la corrección F 6G.1 frente al padre 2f4aae4.

Prueba que el ÚNICO cambio en los motores es la sentencia `arr = None`
insertada tras el bucle de flush() de memmaps:
  * Hardened/EVO: sólo cambia `run_experiment`; MQR: sólo `_run_core`;
  * en la unidad cambiada hay exactamente UNA sentencia `arr = None` nueva,
    situada inmediatamente después de `for arr in mm.values(): ...` y antes
    de `del mm` en el mismo bloque; al retirarla, el AST es idéntico al del
    padre;
  * resto de unidades (a nivel de método) y sentencias de nivel superior
    idénticas; lectura_segura_6g1.py idéntico byte a byte.
Uso (desde la raíz del repo):
    python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_correccion_f_6g1.py
Evidencia: ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_correccion_f_6g1.json
"""
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
REPO = RAIZ.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from verificar_ast_auditoria_integral_6g1 import unidades, _dump  # noqa: E402
from verificar_ast_ciclo_vida_6g1 import MOTORES  # noqa: E402

BASE = '2f4aae411ce1672ec9aa57cc9a967e0556631d85'
UNIDAD = {'Hardened': 'run_experiment', 'EVO': 'run_experiment', 'MQR': '_run_core'}
REL = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/'


def fuente(rel):
    return subprocess.run(['git', 'show', '%s:%s' % (BASE, rel)], cwd=str(REPO),
                          capture_output=True, check=True).stdout


def es_arr_none(n):
    return (isinstance(n, ast.Assign) and len(n.targets) == 1
            and isinstance(n.targets[0], ast.Name) and n.targets[0].id == 'arr'
            and isinstance(n.value, ast.Constant) and n.value.value is None)


def retirar_arr_none(nodo):
    """Retira las sentencias `arr = None` y devuelve su contexto."""
    ctx = []
    for padre in ast.walk(nodo):
        for campo in ('body', 'orelse', 'finalbody'):
            cuerpo = getattr(padre, campo, None)
            if not isinstance(cuerpo, list):
                continue
            for i, s in enumerate(list(cuerpo)):
                if es_arr_none(s):
                    prev = cuerpo[i - 1] if i > 0 else None
                    sig = cuerpo[i + 1] if i + 1 < len(cuerpo) else None
                    ctx.append(dict(
                        linea=s.lineno,
                        anterior=ast.unparse(prev).split('\n')[0] if prev is not None else None,
                        siguiente=ast.unparse(sig).split('\n')[0] if sig is not None else None,
                        tras_bucle_flush=(isinstance(prev, ast.For)
                                          and isinstance(prev.target, ast.Name)
                                          and prev.target.id == 'arr'
                                          and 'mm.values()' in ast.unparse(prev.iter)),
                        bloque=campo, padre=type(padre).__name__))
            cuerpo[:] = [s for s in cuerpo if not es_arr_none(s)]
    return ctx


def siguiente_es_del_mm(src_b, ctx, motor):
    """`del mm` es la sentencia siguiente (MQR) o la primera tras el bloque
    `if write_masks:` que contiene la inserción (Hardened/EVO)."""
    lineas = src_b.decode('utf-8').split('\n')
    for c in ctx:
        resto = [x.strip() for x in lineas[c['linea']:c['linea'] + 3] if x.strip()]
        c['primera_sentencia_posterior'] = resto[0] if resto else None
        c['antes_de_del_mm'] = bool(resto) and resto[0] == 'del mm'
    return all(c['antes_de_del_mm'] for c in ctx)


def comparar(m, f):
    sa, sb = fuente(REL + f), (REPO / REL / f).read_bytes()
    a, oa = unidades(sa.decode('utf-8'))
    b, ob = unidades(sb.decode('utf-8'))
    cambiadas = sorted(k for k in a if k in b and _dump(a[k]) != _dump(b[k]))
    u = UNIDAD[m]
    nb = ast.parse(sb.decode('utf-8'))
    nodo_b = next(n for n in nb.body if isinstance(n, ast.FunctionDef) and n.name == u)
    na = ast.parse(sa.decode('utf-8'))
    nodo_a = next(n for n in na.body if isinstance(n, ast.FunctionDef) and n.name == u)
    ctx_a = retirar_arr_none(nodo_a)
    ctx_b = retirar_arr_none(nodo_b)
    identico_sin_insercion = _dump(nodo_a) == _dump(nodo_b)
    del_mm = siguiente_es_del_mm(sb, ctx_b, m)
    otras = ([_dump(x) for x in oa] == [_dump(x) for x in ob])
    ok = (cambiadas == [u] and not (set(a) ^ set(b)) and otras and len(ctx_a) == 0
          and len(ctx_b) == 1 and ctx_b[0]['tras_bucle_flush'] and del_mm
          and identico_sin_insercion)
    return dict(unidades_cambiadas=cambiadas, unidad_autorizada=u,
                unidades_añadidas=sorted(set(b) - set(a)),
                unidades_eliminadas=sorted(set(a) - set(b)),
                sentencias_superiores_identicas=otras,
                inserciones_arr_none_padre=len(ctx_a), inserciones_arr_none=ctx_b,
                ast_identico_al_padre_sin_la_insercion=identico_sin_insercion,
                sha256_padre=hashlib.sha256(sa).hexdigest(),
                sha256=hashlib.sha256(sb).hexdigest(), veredicto='OK' if ok else 'FALLO')


def main():
    res = dict(schema='ast-correccion-f-6g1/1', base=BASE, motores={})
    ok_global = True
    for m, f in MOTORES.items():
        r = comparar(m, f)
        res['motores'][m] = r
        ok_global &= r['veredicto'] == 'OK'
        c = r['inserciones_arr_none']
        print('%-8s cambiadas=%s inserciones=%d tras_bucle=%s antes_de_del_mm=%s '
              'identico_sin_insercion=%s superiores_identicas=%s -> %s'
              % (m, r['unidades_cambiadas'], len(c), [x['tras_bucle_flush'] for x in c],
                 [x['antes_de_del_mm'] for x in c], r['ast_identico_al_padre_sin_la_insercion'],
                 r['sentencias_superiores_identicas'], r['veredicto']))
    rel = REL + 'lectura_segura_6g1.py'
    igual = fuente(rel) == (REPO / rel).read_bytes()
    res['lectura_segura_6g1_identico'] = igual
    ok_global &= igual
    print('lectura_segura_6g1 idéntico al padre:', igual)
    res['veredicto'] = 'OK' if ok_global else 'FALLO'
    out = RAIZ / 'evidence' / 'ast_correccion_f_6g1.json'
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('VEREDICTO:', res['veredicto'])
    return 0 if ok_global else 1


if __name__ == '__main__':
    sys.exit(main())
