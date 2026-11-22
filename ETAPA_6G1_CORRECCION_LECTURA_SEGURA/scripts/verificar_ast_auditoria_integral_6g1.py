#!/usr/bin/env python3
"""Verificación estática (AST) de la auditoría integral 6G.1 / AI (cierre real
de wrappers y retención de abortos): el DSP permanece intacto.

Base: 6a93e4e (CR-R1). Comparación a nivel de MÉTODO: cada clase de nivel
superior se descompone en `Clase.metodo` (y su cuerpo no-método), de modo que
un cambio en `CandidateRunner.__init__`/`close` (gestión de escritores) se
distingue de cualquier cambio en el resto de la clase.

Para cada motor:
  * unidades cambiadas ⊆ PERMITIDAS (ciclo de vida/cierre; ninguna DSP);
  * ninguna unidad añadida ni eliminada;
  * sentencias de nivel superior distintas: sólo imports y el nuevo global
    `_G_TEE_FALLO = None`;
  * en cada unidad cambiada: literales numéricos y llamadas DSP idénticos
    (extractores `_numeros`/`_llamadas_dsp` de no_regresion_dsp_6g1.py, sólo
    importados; ese script y su evidencia no se tocan ni se ejecutan);
  * `CandidateRunner.__init__`: las asignaciones de estado DSP (`ola_sdv`,
    `ola_sdi`, `metrics`, `cand_id`, `mask_source`, `plan`, `write_audio`) y
    las llamadas `sf.SoundFile(...)` de apertura de los WAV tienen AST
    idéntico (mismos argumentos: ruta, samplerate, canales, subtipo);
  * defs DSP (DSP_DEFS, salvo CandidateRunner tratada por métodos) con AST
    idéntico.
Para lectura_segura_6g1.py (sin DSP): unidades añadidas/cambiadas/eliminadas
⊆ lo autorizado y ninguna llamada DSP nueva.

Uso (desde la raíz del repo):
    python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/verificar_ast_auditoria_integral_6g1.py
Evidencia: ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/ast_auditoria_integral_6g1.json
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
from verificar_ast_ciclo_vida_6g1 import MOTORES  # noqa: E402

BASE = '6a93e4ece2dcb1f4d79a5a4bb1501ace080f5dcd'
DSP_DEFS = ('analyze_guide_scale', 'OlaStream', 'stft_span_frames',
            'compute_vocal_mask', 'consensus_from_masks', 'confidence_and_disagreement',
            'apply_sfumato_smoothing', 'read_span', 'mono_downmix', 'FramePlan',
            'post_wav_identity', 'build_band_masks')
_COMUNES = {'Tee.__init__', 'Tee.close', 'close_tee', 'init_tee',
            'CandidateRunner.__init__', 'CandidateRunner.close', 'run_experiment'}
PERMITIDAS = {'Hardened': _COMUNES, 'EVO': _COMUNES, 'MQR': _COMUNES | {'_run_core'}}
GLOBALES_NUEVOS = {'_G_TEE_FALLO = None'}
ESTADO_DSP_RUNNER = ('ola_sdv', 'ola_sdi', 'metrics', 'cand_id', 'mask_source', 'plan',
                     'write_audio')
MODULO_PERMITIDAS = dict(
    añadidas={'CierreNoAcreditado6G1.<cuerpo>', 'fallo_cierre_6g1', '_marcar_fallo_cierre_6g1',
              '_estado_fisico_6g1', 'cerrar_verificado_6g1', 'runner_parcial_6g1',
              'MixHandle._cerrar_6g1'},
    cambiadas={'MixHandle.__init__', 'MixHandle.close', '_cerrado_6g1',
               '_cerrar_idempotente_6g1', 'preparar_aborto_6g1'})


def fuente(base, rel):
    return subprocess.run(['git', 'show', '%s:%s' % (base, rel)], cwd=str(REPO),
                          capture_output=True, text=True, check=True).stdout


def unidades(src):
    """{nombre: nodo} con clases descompuestas en métodos + '<Clase>.<cuerpo>'
    (sentencias no-método de la clase); y la lista de otras sentencias."""
    t = ast.parse(src)
    d, otros = {}, []
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            d[n.name] = n
        elif isinstance(n, ast.ClassDef):
            resto = []
            for m in n.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    d['%s.%s' % (n.name, m.name)] = m
                else:
                    resto.append(m)
            d['%s.<cuerpo>' % n.name] = ast.Module(
                body=resto + [ast.Expr(ast.Constant([ast.dump(b) for b in n.bases]))],
                type_ignores=[])
        else:
            otros.append(n)
    return d, otros


def _dump(n):
    return ast.dump(n, include_attributes=False)


def estado_runner(nodo):
    """Asignaciones self.<estado DSP> y llamadas sf.SoundFile(...) de __init__."""
    asig, aperturas = {}, []
    for n in ast.walk(nodo):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                    and t.value.id == 'self' and t.attr in ESTADO_DSP_RUNNER):
                asig.setdefault(t.attr, []).append(_dump(n.value))
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == 'SoundFile'):
            aperturas.append(_dump(n))
    return asig, aperturas


def comparar(m, f):
    rel = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/' + f
    a, oa = unidades(fuente(BASE, rel))
    b, ob = unidades((REPO / rel).read_text(encoding='utf-8'))
    da, db = [_dump(x) for x in oa], [_dump(x) for x in ob]
    cambiadas = sorted(k for k in a if k in b and _dump(a[k]) != _dump(b[k]))
    otras_b = [ast.unparse(x) for x, s in zip(ob, db) if s not in da]
    otras_a = [ast.unparse(x) for x, s in zip(oa, da) if s not in db]
    det = {}
    for k in cambiadas:
        det[k] = dict(literales_iguales=_numeros(a[k])[0] == _numeros(b[k])[0],
                      llamadas_dsp_iguales=_llamadas_dsp(a[k]) == _llamadas_dsp(b[k]),
                      llamadas_dsp=_llamadas_dsp(b[k]))
    ea, eb = estado_runner(a['CandidateRunner.__init__']), estado_runner(b['CandidateRunner.__init__'])
    runner = dict(asignaciones_estado_dsp_identicas=ea[0] == eb[0],
                  aperturas_soundfile_identicas=ea[1] == eb[1],
                  estado_dsp_comparado=sorted(eb[0]), n_aperturas=len(eb[1]),
                  cuerpo_clase_identico=_dump(a['CandidateRunner.<cuerpo>'])
                  == _dump(b['CandidateRunner.<cuerpo>']))
    dsp = {}
    for k in DSP_DEFS:
        ks = sorted(u for u in set(a) | set(b) if u == k or u.startswith(k + '.'))
        if ks:
            dsp[k] = all(u in a and u in b and _dump(a[u]) == _dump(b[u]) for u in ks)
    otras_ok = (all(s.startswith(('import ', 'from ')) or s in GLOBALES_NUEVOS for s in otras_b)
                and all(s.startswith(('import ', 'from ')) for s in otras_a))
    ok = (not (set(b) - set(a)) and not (set(a) - set(b))
          and set(cambiadas) <= PERMITIDAS[m]
          and all(v['literales_iguales'] and v['llamadas_dsp_iguales'] for v in det.values())
          and otras_ok and all(runner[x] for x in ('asignaciones_estado_dsp_identicas',
                                                   'aperturas_soundfile_identicas',
                                                   'cuerpo_clase_identico'))
          and all(dsp.values()))
    return dict(unidades_cambiadas=cambiadas, unidades_añadidas=sorted(set(b) - set(a)),
                unidades_eliminadas=sorted(set(a) - set(b)),
                unidades_sin_cambio=len([k for k in a if k in b and k not in cambiadas]),
                permitidas=sorted(PERMITIDAS[m]),
                sentencias_superiores_nuevas=[s[:400] for s in otras_b],
                sentencias_superiores_retiradas=[s[:400] for s in otras_a],
                detalle_unidades_cambiadas=det, candidate_runner=runner,
                defs_dsp_identicas=dsp, veredicto='OK' if ok else 'FALLO')


def modulo():
    rel = 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py'
    a, oa = unidades(fuente(BASE, rel))
    b, ob = unidades((REPO / rel).read_text(encoding='utf-8'))
    ca = sorted(k for k in a if k in b and _dump(a[k]) != _dump(b[k]))
    an, el = sorted(set(b) - set(a)), sorted(set(a) - set(b))
    dsp_nuevas = {k: _llamadas_dsp(b[k]) for k in ca + an
                  if _llamadas_dsp(b[k]) != (_llamadas_dsp(a[k]) if k in a else [])}
    otras = [ast.unparse(x)[:200] for x in ob if _dump(x) not in [_dump(y) for y in oa]]
    ok = (set(an) <= MODULO_PERMITIDAS['añadidas'] and set(ca) <= MODULO_PERMITIDAS['cambiadas']
          and not el and not dsp_nuevas and all(s.startswith(('import ', 'from ')) for s in otras))
    return dict(unidades_añadidas=an, unidades_cambiadas=ca, unidades_eliminadas=el,
                autorizadas={k: sorted(v) for k, v in MODULO_PERMITIDAS.items()},
                llamadas_dsp_nuevas=dsp_nuevas, sentencias_superiores_nuevas=otras,
                veredicto='OK' if ok else 'FALLO')


def main():
    res = dict(schema='ast-auditoria-integral-6g1/1', base=BASE, motores={})
    ok_global = True
    for m, f in MOTORES.items():
        r = comparar(m, f)
        res['motores'][m] = r
        ok_global &= r['veredicto'] == 'OK'
        print('%-8s cambiadas=%s añadidas=%s eliminadas=%s nuevas_sup=%s dsp_identicas=%d/%d '
              'runner=%s -> %s' % (m, r['unidades_cambiadas'], r['unidades_añadidas'],
                                   r['unidades_eliminadas'], r['sentencias_superiores_nuevas'],
                                   sum(r['defs_dsp_identicas'].values()),
                                   len(r['defs_dsp_identicas']), r['candidate_runner'],
                                   r['veredicto']))
        for k, v in r['detalle_unidades_cambiadas'].items():
            print('    %-26s literales_iguales=%s llamadas_dsp_iguales=%s'
                  % (k, v['literales_iguales'], v['llamadas_dsp_iguales']))
    res['modulo'] = modulo()
    ok_global &= res['modulo']['veredicto'] == 'OK'
    print('lectura_segura_6g1:', {k: v for k, v in res['modulo'].items() if k != 'autorizadas'})
    res['veredicto'] = 'OK' if ok_global else 'FALLO'
    out = RAIZ / 'evidence' / 'ast_auditoria_integral_6g1.json'
    out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('VEREDICTO:', res['veredicto'])
    return 0 if ok_global else 1


if __name__ == '__main__':
    sys.exit(main())
