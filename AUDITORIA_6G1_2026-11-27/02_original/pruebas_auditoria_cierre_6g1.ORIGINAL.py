#!/usr/bin/env python3
"""Batería 6G.1 / AI: auditoría integral — cierre real de wrappers y retención
de abortos (instrucción de Cris sobre 6a93e4e).

Escenarios (inyector: scripts/inyeccion_auditoria_6g1/ejecutar_motor_auditoria.py),
cada uno sobre Hardened, EVO y MQR:
  A1/A2  fallo real del cierre de un escritor WAV en la finalización normal
         (A1: antes del cierre físico; A2: después, como soundfile cuando
         sf_close devuelve error) -> aborto, completo=False, sin traslado.
  B1/B2  fallo del cierre interno del lector del Mix (MixHandle) en la
         guarda final -> aborto, completo=False, sin traslado.
  C1/C2  fallo de Tee.close() en el camino normal (antes / después del
         cierre físico) -> aborto, completo=False, log_cerrado=False, error en
         el informe y en el motivo de conservación, sin traslado.
  D1     fallo al abrir el segundo escritor de un CandidateRunner después de
         abrir el primero -> el primer escritor se conoce, se cierra y se
         invalida; con todo cerrado y acreditado el aborto se traslada.
  D2     D1 + fallo del cierre de ese primer escritor -> completo=False, sin
         traslado.
  E1     fallo de la guarda final de integridad del Mix después de generar
         masks/ -> aborto sin traslado y masks/ CONSERVADA.

Todas las corridas usan una COPIA del Mix en la carpeta de trabajo (E1 la
altera; los fixtures no se tocan) y `--mode full_processing`
(+ `--keep-masks` en Hardened/EVO sólo en E1, para que exista masks/; MQR la
crea siempre).

Comprobaciones por caso: código (nunca EXIT_OK); inyección realizada;
protocolo de aborto ejecutado; `completo` y `log_cerrado` esperados; error
inyectado en el informe de cierre y (sin traslado) en el motivo de
conservación; ABORT_6G1.json schema /3, motivo, resultados_validos=[];
traslado sólo si cierre e integridad están acreditados; provisional
conservado; ningún archivo eliminado; ninguna publicación como éxito; en la
ENTRADA del registro ningún descriptor ni mapeo bajo la salida ni sobre las
entradas, escritores y lectores cerrados y memmaps liberados (/proc); ningún
cierre después del registro; SHA estable tras el registro (y tras terminar el
proceso); recolector cíclico deshabilitado en todo el proceso
(gc.disable(); 0 colecciones posteriores, vía gc.callbacks).

`--base DIR --etiqueta-base X` repite la batería sobre otra copia de los
motores (diagnóstico; no cambia el veredicto).
Evidencia: evidence/pruebas_auditoria_cierre_6g1.json,
           evidence/matriz_auditoria_cierre_6g1.csv,
           evidence/inyecciones_auditoria_6g1/<motor>_<esc>.json (estado
           completo de cada inyección sobre los motores corregidos).
Salida 0 sólo si todos los casos sobre los motores corregidos dan PASS.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, sha_file, entorno  # noqa: E402
from pruebas_cierre_recursos_6g1 import riff, inventario, ident, leer_abort  # noqa: E402

EV = RAIZ / 'evidence'
EV_INY = EV / 'inyecciones_auditoria_6g1'
EJECUTOR = RAIZ / 'scripts' / 'inyeccion_auditoria_6g1' / 'ejecutar_motor_auditoria.py'
TRABAJO = Path('/tmp/f6g1ai')
EXIT_OK, EXIT_PROCESSING = 0, 2
EXC = 'EXCEPCION_DURANTE_EL_PROCESAMIENTO'
MIXC = 'MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO'

# esc: (condición, motivo, completo, trasladado, fallo de cierre, log_cerrado,
#       tipo de inyección esperado)
ESCENARIOS = {
    'A1': ('Cierre WAV fallido en la finalización normal (antes del cierre físico)',
           EXC, False, False, True, True, 'cierre_escritor_fallido'),
    'A2': ('Cierre WAV fallido en la finalización normal (después del cierre físico)',
           EXC, False, False, True, True, 'cierre_escritor_fallido'),
    'B1': ('Cierre interno de MixHandle fallido en la guarda final (antes del cierre físico)',
           EXC, False, False, True, True, 'cierre_lector_fallido'),
    'B2': ('Cierre interno de MixHandle fallido en la guarda final (después del cierre físico)',
           EXC, False, False, True, True, 'cierre_lector_fallido'),
    'C1': ('Tee.close() fallido en el camino normal (antes del cierre físico)',
           EXC, False, False, True, False, 'cierre_log_fallido'),
    'C2': ('Tee.close() fallido en el camino normal (después del cierre físico)',
           EXC, False, False, True, False, 'cierre_log_fallido'),
    'D1': ('Construcción de CandidateRunner fallida tras abrir el primer escritor',
           EXC, True, True, False, True, 'apertura_segundo_escritor_fallida'),
    'D2': ('D1 + cierre fallido del primer escritor',
           EXC, False, False, True, True, 'apertura_segundo_escritor_fallida'),
    'E1': ('Guarda final de integridad del Mix fallida tras generar masks/',
           MIXC, True, False, False, True, 'mix_alterado_tras_masks'),
}
ENTRADAS_GUIAS = [FIX / 'vocal_mix.wav', FIX / 'instrumental_mix.wav']
# Hallazgo F (preexistente en 6a93e4e, fuera de A-E, NO corregido): tras
# `for arr in mm.values(): arr.flush()` + `del mm`, la variable de bucle `arr`
# conserva el ÚLTIMO memmap (masks/model_disagreement_map.npy) mapeado y con
# escritura hasta que la función retorna. Comprobaciones que ese recurso afecta:
CHECKS_F = {'completo_esperado', 'informe_sin_errores_de_cierre', 'log_cerrado_esperado',
            'sin_descriptores_ni_mapeos_al_registrar', 'memmaps_liberados_al_registrar',
            'sin_escritura_al_terminar'}
RECURSO_F = 'masks/model_disagreement_map.npy'


def atribucion_f(r, fallos):
    """True si TODOS los fallos están en CHECKS_F y el único recurso con
    escritura abierto al registrar (fd y mapeo) es RECURSO_F."""
    if not fallos:
        return None
    fe = (r['estado'].get('fotos') or {}).get('entrada_abortar') or {}
    abiertos = {os.path.relpath(d['destino'], (r['estado'].get('inyeccion') or {})
                                .get('provisional') or '/')
                for d in fe.get('descriptores_salida_o_entradas', []) if d.get('escritura')}
    abiertos |= {os.path.relpath(m, (r['estado'].get('inyeccion') or {}).get('provisional')
                                 or '/') for m in fe.get('mapeos_bajo_salida', [])}
    vivos = {os.path.basename(m['ruta']) for m in fe.get('memmaps', []) if m['vivo']}
    return (set(fallos) <= CHECKS_F and abiertos == {RECURSO_F}
            and vivos == {os.path.basename(RECURSO_F)})


def args_motor(motor, esc, man, out):
    # masks/ sólo donde el escenario lo exige (E1): en Hardened/EVO se escriben
    # con --keep-masks; MQR las escribe siempre. A-D prueban su objetivo sin
    # el hallazgo F (memmap retenido por la variable de bucle `arr`).
    a = ['--manifest', str(man), '--out', str(out), '--mode', 'full_processing']
    if motor in ('Hardened', 'EVO') and esc == 'E1':
        a.append('--keep-masks')
    return a


def ejecutar(motores_dir, motor, esc, etiqueta):
    work = TRABAJO / etiqueta / motor / esc
    if work.exists():
        shutil.rmtree(work)
    out = work / 'out'
    out.mkdir(parents=True, mode=0o700)
    mix = work / 'mix_copia.wav'
    shutil.copyfile(FIX / 'mix.wav', mix)
    man = escribir_manifest(work / 'manifest.json',
                            dict(mix=str(mix), vocal=str(ENTRADAS_GUIAS[0]),
                                 instrumental=str(ENTRADAS_GUIAS[1])))
    snap = work / 'estado.json'
    entradas = [mix] + ENTRADAS_GUIAS
    env = dict(os.environ, SDVSDI_AI_SNAP=str(snap), SDVSDI_AI_OUT=str(out),
               SDVSDI_AI_MIX=str(mix),
               SDVSDI_AI_ENTRADAS=os.pathsep.join(str(p) for p in entradas),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    cmd = [sys.executable, '-B', str(EJECUTOR), esc,
           str(motores_dir / MOTORES[motor])] + args_motor(motor, esc, man, out)
    p = subprocess.run(cmd, cwd=str(motores_dir), env=env, capture_output=True,
                       text=True, timeout=600)
    estado = json.loads(snap.read_text()) if snap.exists() else {}
    return dict(work=work, out=out, codigo=p.returncode, stdout=p.stdout or '',
                stderr=p.stderr or '', estado=estado, cmd=cmd[3:], snap=snap)


def verificar(motor, esc, r):
    cond, motivo_esp, completo_esp, tras_esp, fallo_cierre, logc_esp, tipo_esp = ESCENARIOS[esc]
    e = r['estado']
    ch = {}

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), str(detalle)[:700])

    marca = 'inyeccion AI-%s' % esc
    c('codigo_salida', r['codigo'] == EXIT_PROCESSING, r['codigo'])
    c('nunca_EXIT_OK', r['codigo'] != EXIT_OK, r['codigo'])
    ret = e.get('retorno_run_experiment') or {}
    c('run_experiment_sin_exito', ret.get('codigo') == EXIT_PROCESSING
      and ret.get('ruta_str') is None, ret)
    inj = e.get('inyeccion')
    c('inyeccion_realizada', bool(inj) and inj['detalle'].get('tipo') == tipo_esp,
      inj and inj['detalle'])
    if not inj or not inj.get('provisional'):
        return ch, {}
    prov, final = Path(inj['provisional']), Path(inj['final'])
    pre = e.get('preparar')
    c('protocolo_de_aborto_ejecutado', pre is not None)
    if pre is None:
        return ch, {}
    c('completo_esperado', pre.get('completo') is completo_esp,
      'completo=%s errores=%s' % (pre.get('completo'), pre.get('errores')))
    if fallo_cierre:
        c('error_de_cierre_en_informe', any(marca in str(x) for x in pre.get('errores') or []),
          pre.get('errores'))
    else:
        c('informe_sin_errores_de_cierre', not pre.get('errores'), pre.get('errores'))
    c('log_cerrado_esperado', pre.get('log_cerrado') is logc_esp, pre.get('log_cerrado'))
    ra = e.get('resultado_aborto') or {}
    c('abort_registrado', ra.get('abort_registrado') is True, ra.get('motivo_conservacion'))
    c('traslado_esperado', ra.get('trasladado') is tras_esp,
      (ra.get('trasladado'), ra.get('motivo_conservacion')))
    if not tras_esp and fallo_cierre:
        c('error_en_motivo_de_conservacion', marca in str(ra.get('motivo_conservacion'))
          and 'cierre de recursos incompleto' in str(ra.get('motivo_conservacion')),
          ra.get('motivo_conservacion'))
    if esc == 'E1':
        c('conservacion_por_integridad_sin_traslado',
          ra.get('traslado_solicitado') is False
          and 'traslado no solicitado' in str(ra.get('motivo_conservacion')),
          ra.get('motivo_conservacion'))
    ubic = Path(ra.get('ruta_final') or prov)
    entradas = sorted(os.listdir(r['out']))
    if tras_esp:
        c('trasladado_sin_reemplazo', ubic == Path(str(final) + '_aborted')
          and ubic.is_dir() and not prov.exists() and ident(ubic) == inj['identidad'], ubic.name)
    else:
        c('provisional_conservado_en_su_ubicacion', ubic == prov and prov.is_dir()
          and ident(prov) == inj['identidad'], entradas)
        c('ningun_aborted_creado', not [x for x in entradas if '_aborted' in x], entradas)
    pubs = [x for x in e.get('eventos', []) if x['tipo'] == 'publicar_entrada'
            and not str(x.get('destino', '')).endswith('_aborted')]
    c('sin_publicacion_exitosa', not pubs and final.name not in entradas
      and set(entradas) <= {prov.name, final.name + '_aborted'}, (entradas, pubs))

    ab = leer_abort(ubic) or {}
    c('ABORT_6G1_schema_3', ab.get('schema') == 'abort-6g1/3', ab.get('schema'))
    c('motivo', ab.get('motivo') == motivo_esp, ab.get('motivo'))
    c('resultados_validos_vacio', ab.get('resultados_validos') == [])
    post = inventario(ubic)
    c('ningun_archivo_eliminado', set(inj['archivos']) <= set(post),
      'faltan %s' % sorted(set(inj['archivos']) - set(post)))
    masks = sorted(k for k in inj['archivos'] if k.startswith('masks/'))
    if esc == 'E1':
        c('masks_generadas_y_conservadas', masks and all(k in post for k in masks)
          and all(k in (ab.get('salidas_invalidadas') or []) + (ab.get('conservados') or [])
                  for k in masks), '%d npy: %s' % (len(masks), masks[:4]))

    fe = e.get('fotos', {}).get('entrada_abortar')
    fs = e.get('fotos', {}).get('salida_abortar')
    ff = e.get('fotos', {}).get('fin_proceso')
    c('registro_invocado', fe is not None)
    if fe is None:
        return ch, {}
    c('sin_descriptores_ni_mapeos_al_registrar', fe['descriptores_salida_o_entradas'] == []
      and fe['mapeos_bajo_salida'] == [],
      (fe['descriptores_salida_o_entradas'], fe['mapeos_bajo_salida']))
    c('escritores_cerrados_al_registrar', all(w['cerrado'] for w in fe['escritores']),
      [(os.path.basename(w['ruta']), w['cerrado']) for w in fe['escritores']])
    c('lectores_cerrados_al_registrar', fe['lectores_abiertos'] == [], fe['lectores_abiertos'])
    c('memmaps_liberados_al_registrar', not any(m['vivo'] for m in fe['memmaps']),
      [os.path.basename(m['ruta']) for m in fe['memmaps'] if m['vivo']])
    ev = e.get('eventos', [])
    n_ab = min([x['n'] for x in ev if x['tipo'] == 'abortar_6g1_entrada'] or [10 ** 9])
    n_pre = min([x['n'] for x in ev if x['tipo'] == 'preparar_aborto_entrada'] or [10 ** 9])
    tarde = [x for x in ev if x['n'] > n_ab and x['tipo'] in ('escritor_cerrado', 'lector_cerrado',
                                                              'log_cerrado')]
    c('orden_cierre_antes_del_registro', n_pre < n_ab and not tarde,
      [(x['n'], x['tipo'], os.path.basename(x.get('ruta', '') or '')) for x in ev
       if x['n'] >= inj['n_evento']])
    if ff is not None and fs is not None:
        a_sal = dict(fs['archivos'])
        c('sha_estable_tras_registro', ff['archivos'] == a_sal and post == a_sal,
          sorted(k for k in set(a_sal) | set(post) if a_sal.get(k) != post.get(k)))
        c('sin_escritura_al_terminar', not [d for d in ff['descriptores_salida_o_entradas']
                                            if d['escritura'] is not False]
          and ff['mapeos_bajo_salida'] == [], ff['descriptores_salida_o_entradas'])
    else:
        c('sha_estable_tras_registro', False, 'sin fotos')
    c('sin_gc_en_todo_el_proceso', e.get('gc_deshabilitado_al_inicio') is True
      and e.get('gc_habilitado_al_final') is False
      and all(f.get('gc_habilitado') is False for f in e.get('fotos', {}).values())
      and e.get('gc_colecciones') == e.get('gc_colecciones_al_deshabilitar')
      and e.get('gc_colecciones_posteriores') == [],
      dict(al_deshabilitar=e.get('gc_colecciones_al_deshabilitar'),
           al_final=e.get('gc_colecciones'),
           posteriores=len(e.get('gc_colecciones_posteriores') or [])))

    if esc in ('D1', 'D2'):
        primer = inj['detalle'].get('primer_escritor')
        rel = os.path.relpath(primer, prov) if primer else None
        h = riff(ubic / rel) if rel and (ubic / rel).is_file() else dict(ok=False)
        c('primer_escritor_conocido_cerrado_e_invalidado', rel is not None
          and any(x['tipo'] == 'escritor_cerrado' and x.get('ruta') == primer and x['n'] < n_ab
                  for x in ev)
          and rel in (ab.get('salidas_invalidadas') or [])
          and h.get('ok') and h['riff_size'] == h['tamano'] - 8
          and h['data_offset'] + h['data_size'] == h['tamano'],
          dict(rel=rel, riff=h))
    if esc in ('A1', 'A2'):
        wavs = [k for k in inj['archivos'] if k.endswith('.wav')]
        c('wavs_conservados_e_invalidados', wavs and all(k in post for k in wavs)
          and all(k in (ab.get('salidas_invalidadas') or []) for k in wavs), wavs)
    c('resultado_del_aborto_en_consola', ('trasladado=%s' % tras_esp) in r['stdout'],
      r['stdout'][-300:])
    secuencia = [(x['n'], x['tipo'], os.path.basename(x.get('ruta', '') or ''))
                 for x in ev if x['n'] >= inj['n_evento']]
    extra = dict(inyeccion=inj['detalle'], preparar=dict(completo=pre.get('completo'),
                 log_cerrado=pre.get('log_cerrado'), errores=pre.get('errores')),
                 resultado_aborto=dict(trasladado=ra.get('trasladado'),
                                       ruta_final=ra.get('ruta_final'),
                                       motivo_conservacion=ra.get('motivo_conservacion')),
                 secuencia=secuencia, ubicacion_final=str(ubic),
                 masks_en_inyeccion=len(masks))
    return ch, extra


def bateria(motores_dir, etiqueta, guardar_estados=False):
    filas, detalle = [], {}
    for motor in MOTORES:
        for esc in ESCENARIOS:
            r = ejecutar(motores_dir, motor, esc, etiqueta)
            try:
                ch, extra = verificar(motor, esc, r)
            except Exception as exc:
                ch, extra = {'verificador': (False, repr(exc))}, {}
            ok = all(v[0] for v in ch.values())
            fallos = [k for k, v in ch.items() if not v[0]]
            af = atribucion_f(r, fallos)
            detalle['%s/%s' % (motor, esc)] = dict(atribuible_solo_a_hallazgo_F=af,
                condicion=ESCENARIOS[esc][0], codigo=r['codigo'], argumentos=r['cmd'],
                comprobaciones={k: dict(ok=v[0], detalle=v[1]) for k, v in ch.items()},
                veredicto='PASS' if ok else 'FAIL', fallos=fallos, **extra,
                stdout_tail=r['stdout'][-1500:], stderr_tail=r['stderr'][-1500:])
            filas.append(dict(prueba=esc, motor=motor, condicion=ESCENARIOS[esc][0],
                              codigo=r['codigo'],
                              completo=(extra.get('preparar') or {}).get('completo'),
                              log_cerrado=(extra.get('preparar') or {}).get('log_cerrado'),
                              trasladado=(extra.get('resultado_aborto') or {}).get('trasladado'),
                              comprobaciones='%d/%d' % (sum(v[0] for v in ch.values()), len(ch)),
                              fallos=';'.join(fallos), veredicto='PASS' if ok else 'FAIL',
                              atribuible_solo_a_F='' if af is None else af))
            if guardar_estados and r['snap'].exists():
                EV_INY.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(r['snap'], EV_INY / ('%s_%s.json' % (motor, esc)))
            print('%-8s %-3s codigo=%-4s %s %s%s' % (motor, esc, r['codigo'],
                                                    'PASS' if ok else 'FAIL', ','.join(fallos),
                                                    '' if af is None else ' [solo F=%s]' % af),
                  flush=True)
    return filas, detalle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=None)
    ap.add_argument('--etiqueta-base', default='base')
    a = ap.parse_args()
    res = dict(schema='pruebas-auditoria-cierre-6g1/1', entorno=entorno(),
               motores_sha256={m: sha_file(MOT / n) for m, n in MOTORES.items()},
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               escenarios={k: dict(condicion=v[0], motivo=v[1], completo=v[2], trasladado=v[3],
                                   fallo_de_cierre=v[4], log_cerrado=v[5], inyeccion=v[6])
                           for k, v in ESCENARIOS.items()},
               argumentos_motor='--mode full_processing [+ --keep-masks en Hardened/EVO sólo en E1]; '
                                'Mix = copia en la carpeta de trabajo')
    if a.base:
        bdir = Path(a.base).resolve()
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = bateria(bdir, a.etiqueta_base)
        res['diagnostico_base'] = dict(
            etiqueta=a.etiqueta_base, carpeta=str(bdir),
            motores_sha256={m: sha_file(bdir / n) for m, n in MOTORES.items()},
            filas=fb, detalle=db,
            resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb), total=len(fb)))
    print('== motores corregidos (%s)' % MOT)
    if EV_INY.exists():
        shutil.rmtree(EV_INY)
    filas, det = bateria(MOT, 'corregido', guardar_estados=True)
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas),
                            fail_atribuibles_solo_a_F=sum(f['atribuible_solo_a_F'] is True
                                                          for f in filas),
                            fail_no_atribuibles=sum(f['atribuible_solo_a_F'] is False
                                                    for f in filas)),
               hallazgo_F=dict(recurso=RECURSO_F, comprobaciones_afectadas=sorted(CHECKS_F),
                               causa='variable de bucle `arr` de `for arr in mm.values(): '
                                     'arr.flush()` retiene el último memmap tras `del mm`',
                               corregido=False))
    EV.mkdir(parents=True, exist_ok=True)
    (EV / 'pruebas_auditoria_cierre_6g1.json').write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    bidx = {(f['prueba'], f['motor']): f for f in res.get('diagnostico_base', {}).get('filas', [])}
    with open(EV / 'matriz_auditoria_cierre_6g1.csv', 'w', newline='', encoding='utf-8') as fh:
        cols = ['prueba', 'motor', 'condicion', 'codigo', 'completo', 'log_cerrado', 'trasladado',
                'comprobaciones', 'fallos', 'veredicto', 'atribuible_solo_a_F', 'codigo_base',
                'veredicto_base', 'fallos_base']
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for f in filas:
            b = bidx.get((f['prueba'], f['motor']), {})
            wr.writerow(dict(f, codigo_base=b.get('codigo', ''), veredicto_base=b.get('veredicto', ''),
                             fallos_base=b.get('fallos', '')))
    print('RESUMEN corregido: %d/%d PASS (FAIL sólo-F=%d, FAIL otros=%d)'
          % (res['resumen']['pass_'], res['resumen']['total'],
             res['resumen']['fail_atribuibles_solo_a_F'], res['resumen']['fail_no_atribuibles']))
    if 'diagnostico_base' in res:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base,
                                                res['diagnostico_base']['resumen']['pass_'],
                                                res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
