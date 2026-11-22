"""Pruebas CV (ciclo de vida 6G.1): hallazgos A (abortos incompletos) y B
(retorno incorrecto de MQR). Batería dirigida y determinista; no repite las
baterías históricas (34/26/17/12) ni procesa audio real.

Cada escenario se ejecuta en Hardened, EVO y MQR (modo full_processing,
fixtures sintéticos `mix.wav` + `vocal_mix.wav` + `instrumental_mix.wav`) con
`inyeccion_ciclo_6g1/ejecutar_motor_inyectado.py`, que sustituye en memoria UN
punto del flujo (ver su docstring) y toma una instantánea del provisional en
el instante de la inyección.

  A1    KeyboardInterrupt tras generar salidas parciales
  A2    excepción general tras generar salidas parciales
  A2NA  excepción general con el provisional sustituido (no acreditable)
  A3    fallo de publicación segura (renameat2 indisponible)
  A4    fallo de apertura del Mix (MixCambiado)
  A4b   fallo de apertura del Mix (OSError genérico)
  A5    fallo de la guarda final
  A6    fallo de la preparación inicial tras crear el provisional (log)
  A6b   provisional creado pero no acreditado
  A7    excepción general con escritura de ABORT_6G1.json fallida: provisional
        conservado en su ubicación, sin traslado ni éxito
  E0    corrida feliz (contrato EXIT_OK + PCM igual al registrado)

Uso:
  python -B scripts/pruebas_ciclo_vida_6g1.py            # motores corregidos
  python -B scripts/pruebas_ciclo_vida_6g1.py --base DIR # diagnóstico: mismos
        escenarios contra otra copia de motores (p. ej. los de 594a90f); sólo
        se registra en la evidencia, no cambia el veredicto.

Evidencia: evidence/pruebas_ciclo_vida_6g1.json + evidence/matriz_ciclo_vida_6g1.csv
"""
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, sha_file, dump, entorno  # noqa: E402

EV = RAIZ / 'evidence'
EJECUTOR = RAIZ / 'scripts' / 'inyeccion_ciclo_6g1' / 'ejecutar_motor_inyectado.py'
TRABAJO = Path('/tmp/f6g1cv')
EXIT_OK, EXIT_PROCESSING, EXIT_ABORTED = 0, 2, 130
SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
AJENO_EXTERNO = b'archivo ajeno junto al directorio de salida (CV 6G.1)\n'

# escenario: (condición, código esperado, motivo esperado o None, registrado,
#             trasladado, salidas parciales exigidas)
ESCENARIOS = {
    'A1': ('KeyboardInterrupt tras salidas parciales', EXIT_ABORTED,
           'INTERRUPCION_DEL_USUARIO', True, True, True),
    'A2': ('Excepción general tras salidas parciales', EXIT_PROCESSING,
           'EXCEPCION_DURANTE_EL_PROCESAMIENTO', True, True, True),
    'A2NA': ('Excepción general con provisional sustituido (no acreditable)',
             EXIT_PROCESSING, None, False, False, False),
    'A3': ('Fallo de publicación segura (renameat2 indisponible)',
           EXIT_PROCESSING, 'PUBLICACION_SEGURA_FALLIDA', True, False, True),
    'A4': ('Fallo de apertura del Mix (MixCambiado)', EXIT_PROCESSING,
           'MIX_SUSTITUIDO_ANTES_DEL_DSP', True, False, False),
    'A4b': ('Fallo de apertura del Mix (OSError)', EXIT_PROCESSING,
            'MIX_NO_ABIERTO_ANTES_DEL_DSP', True, False, False),
    'A5': ('Fallo de la guarda final', EXIT_PROCESSING,
           'MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO', True, False, True),
    'A6': ('Fallo de preparación inicial tras crear el provisional (log)',
           EXIT_PROCESSING, 'EXCEPCION_DURANTE_EL_PROCESAMIENTO', True, True, False),
    'A6b': ('Provisional creado pero no acreditado', EXIT_PROCESSING, None,
            False, False, False),
    'A7': ('Escritura de ABORT_6G1.json fallida (tras excepción general)',
           EXIT_PROCESSING, None, False, False, True),
    'E0': ('Corrida feliz (sin inyección)', EXIT_OK, None, False, False, True),
}


def sha_pcm(path):
    import soundfile as sf
    x, _ = sf.read(str(path), dtype='float64', always_2d=True)
    return hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()


def pcm_registrado():
    d = json.loads((EV / 'no_regresion_dsp_6g1.json').read_text(encoding='utf-8'))
    return {m: v['pcm']['WAV']['pcm_6g1'] for m, v in d['motores'].items()}


def ejecutar(motores_dir, motor, esc, etiqueta):
    work = TRABAJO / etiqueta / motor / esc
    if work.exists():
        shutil.rmtree(work)
    out = work / 'out'
    out.mkdir(parents=True, mode=0o700)
    externo = out / 'AJENO_EXTERNO.txt'
    externo.write_bytes(AJENO_EXTERNO)
    man = escribir_manifest(work / 'manifest.json',
                            dict(mix=str(FIX / 'mix.wav'),
                                 vocal=str(FIX / 'vocal_mix.wav'),
                                 instrumental=str(FIX / 'instrumental_mix.wav')))
    snap = work / 'instantanea.json'
    env = dict(os.environ, SDVSDI_CV_SNAP=str(snap), SDVSDI_CV_OUT=str(out),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    cmd = [sys.executable, '-B', str(EJECUTOR), esc,
           str(motores_dir / MOTORES[motor]), '--manifest', str(man),
           '--out', str(out), '--mode', 'full_processing']
    p = subprocess.run(cmd, cwd=str(motores_dir), env=env, capture_output=True,
                       text=True, timeout=600)
    estado = json.loads(snap.read_text()) if snap.exists() else {}
    return dict(work=work, out=out, externo=externo, codigo=p.returncode,
                stdout=(p.stdout or '')[-3000:], stderr=(p.stderr or '')[-3000:],
                estado=estado)


def _ident(p):
    try:
        st = os.lstat(p)
        return [st.st_dev, st.st_ino]
    except OSError:
        return None


def _listar(p):
    try:
        return sorted(os.listdir(p))
    except OSError:
        return None


def _sha_o_none(p):
    try:
        return sha_file(p) if Path(p).is_file() and not Path(p).is_symlink() else None
    except OSError:
        return None


def _leer_abort(d):
    p = Path(d) / 'ABORT_6G1.json'
    if not p.is_file() or p.is_symlink():
        return None
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except ValueError:
        return {'_ilegible': True}


def verificar(motor, esc, r, pcm_ref):
    cond, cod_esp, motivo_esp, registrado, trasladado, salidas_req = ESCENARIOS[esc]
    out = r['out']
    datos = r['estado'].get('datos', {})
    ch = {}                                 # comprobación -> (ok, detalle)

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), detalle)

    c('codigo_salida', r['codigo'] == cod_esp, 'obtenido %s, esperado %s' % (r['codigo'], cod_esp))
    if esc != 'E0':
        c('nunca_EXIT_OK', r['codigo'] != EXIT_OK, 'codigo %s' % r['codigo'])
    c('externo_intacto', r['externo'].is_file()
      and r['externo'].read_bytes() == AJENO_EXTERNO)
    c('ki_no_escapa_del_motor', not r['estado'].get('ki_escapo', False))
    ret = r['estado'].get('retorno_run_experiment') or {}
    if esc == 'E0':
        c('run_experiment_EXIT_OK_con_ruta_publicada',
          ret.get('codigo') == EXIT_OK and ret.get('ruta_es_directorio') is True, str(ret))
    else:
        c('run_experiment_nunca_EXIT_OK', bool(ret) and ret.get('codigo') != EXIT_OK
          and ret.get('codigo') == cod_esp, str(ret))
    entradas = sorted(os.listdir(out))

    if esc == 'E0':
        finales = [e for e in entradas if (out / e).is_dir()]
        ok_dir = len(finales) == 1 and not re.search(r'_(partial|aborted)', finales[0])
        c('publicacion_unica', ok_dir, str(entradas))
        if ok_dir:
            fin = out / finales[0]
            c('sin_ABORT', not (fin / 'ABORT_6G1.json').exists())
            hashes = {n: sha_pcm(fin / n) for n in SALIDAS[motor] if (fin / n).is_file()}
            c('salidas_reales', len(hashes) == 2, str(sorted(hashes)))
            c('pcm_igual_al_registrado', hashes == {k: pcm_ref[motor][k] for k in SALIDAS[motor]},
              json.dumps(hashes))
        return ch

    c('instantanea_tomada', bool(datos.get('provisional')), datos.get('provisional') or 'sin provisional')
    if not datos.get('provisional'):
        return ch
    prov = Path(datos['provisional'])
    final = Path(datos['final'])
    ident = datos.get('identidad')
    dest = datos.get('destino_preexistente', {})
    # destino preexistente intacto (nunca reemplazado)
    dp = Path(dest.get('ruta', str(final) + '_aborted'))
    try:
        st = os.lstat(dp)
        dp_ok = ([st.st_dev, st.st_ino] == dest.get('identidad')
                 and sorted(os.listdir(dp)) == ['MARCA_DESTINO.txt']
                 and sha_file(dp / 'MARCA_DESTINO.txt') == dest.get('marca_sha256'))
    except OSError:
        dp_ok = False
    c('destino_preexistente_no_reemplazado', dp_ok, str(dp))
    # ninguna publicación como éxito
    exito = [e for e in entradas if e == final.name or re.fullmatch(re.escape(final.name) + r'_r\d{3}', e)]
    c('sin_publicacion_exitosa', not exito, str(exito))

    if not registrado:
        abort_en = [str(p) for p in out.rglob('ABORT_6G1.json')]
        c('sin_ABORT_fuera_de_lo_acreditado', not abort_en, str(abort_en))
        c('sin_traslado', not any(e.startswith(final.name + '_aborted_r') for e in entradas),
          str(entradas))
        if esc == 'A2NA':
            desp = Path(datos['desplazado'])
            c('provisional_original_intacto', _ident(desp) == ident)
            c('archivos_conservados', all((desp / k).is_file() for k in datos['inventario']))
            c('archivos_estables_sin_cambios',
              all(_sha_o_none(desp / k) == v['sha256']
                  for k, v in datos['inventario'].items() if k != 'engine_log.txt'))
            an = datos.get('analysis_sha256')
            c('analysis_json_intacto', an is not None and _sha_o_none(desp / 'analysis.json') == an)
            c('sustituto_no_trasladado_ni_escrito',
              _ident(prov) == datos.get('sustituto_identidad') and _listar(prov) == [],
              'ruta %s: identidad %s, contenido %s' % (prov.name, _ident(prov), _listar(prov)))
            permitidas = {'AJENO_EXTERNO.txt', dp.name, prov.name, desp.name}
        elif esc == 'A7':
            c('fallo_de_escritura_inyectado', r['estado'].get('abort_escritura_fallida') is True)
            c('provisional_conservado_en_su_ubicacion', _ident(prov) == ident)
            c('salidas_parciales_presentes', all((prov / n).is_file() for n in SALIDAS[motor]))
            c('archivos_conservados', all((prov / k).is_file() for k in datos['inventario']))
            c('archivos_estables_sin_cambios',
              all(_sha_o_none(prov / k) == v['sha256']
                  for k, v in datos['inventario'].items() if k != 'engine_log.txt'))
            an = datos.get('analysis_sha256')
            c('analysis_json_intacto', an is not None and _sha_o_none(prov / 'analysis.json') == an)
            c('ajeno_intacto', _sha_o_none(prov / 'AJENO_CV.txt') == datos.get('ajeno_sha256'))
            permitidas = {'AJENO_EXTERNO.txt', dp.name, prov.name}
        else:   # A6b
            c('provisional_conservado_en_su_ubicacion', _ident(prov) == ident)
            c('provisional_sin_escrituras', _listar(prov) == ['AJENO_CV.txt'], str(_listar(prov)))
            permitidas = {'AJENO_EXTERNO.txt', dp.name, prov.name}
        c('sin_escritura_fuera', set(entradas) <= permitidas, str(entradas))
        return ch

    # --- aborto registrado ----------------------------------------------------
    if trasladado:
        ubic = Path(str(final) + '_aborted_r001')
        c('trasladado_sin_reemplazo', ubic.is_dir() and not prov.exists(),
          'esperado %s' % ubic.name)
    else:
        ubic = prov
        c('provisional_conservado_en_su_ubicacion', prov.is_dir()
          and not any(e.startswith(final.name + '_aborted_r') for e in entradas))
    c('identidad_del_directorio_conservada', _ident(ubic) == ident, str(ubic.name))
    ab = _leer_abort(ubic)
    c('ABORT_6G1_existe', ab is not None and '_ilegible' not in ab)
    ab = ab or {}
    c('schema_abort_6g1_3', ab.get('schema') == 'abort-6g1/3', str(ab.get('schema')))
    c('motivo', ab.get('motivo') == motivo_esp, str(ab.get('motivo')))
    c('resultados_validos_vacio', ab.get('resultados_validos') == [])
    c('directorio_acreditado', ab.get('directorio_acreditado') is True)
    inval = ab.get('salidas_invalidadas') or []
    if salidas_req:
        c('salidas_parciales_invalidadas', all(n in inval for n in SALIDAS[motor]), str(inval))
    c('salidas_invalidadas_conservadas', all((ubic / n).is_file() for n in inval), str(inval))
    c('salidas_parciales_presentes', (not salidas_req)
      or all((ubic / n).is_file() for n in SALIDAS[motor]))
    an = datos.get('analysis_sha256')
    if salidas_req:
        c('analysis_json_intacto', an is not None and _sha_o_none(ubic / 'analysis.json') == an)
    inv = datos.get('inventario', {})
    c('archivos_conservados', all((ubic / k).is_file() for k in inv),
      '%d archivos en la instantánea' % len(inv))
    # SHA sin cambios para todo archivo cerrado en el instante de la
    # instantánea. Excepciones (sólo existencia): engine_log.txt (sigue
    # creciendo) y, cuando la inyección ocurre ANTES de cerrar los escritores
    # (A4/A6), los WAV/memmap propios abiertos, cuya cabecera se finaliza al
    # cerrar el descriptor.
    abiertos = set() if salidas_req else {k for k in inv if k.endswith(('.wav', '.npy'))}
    c('archivos_estables_sin_cambios',
      all(_sha_o_none(ubic / k) == v['sha256'] for k, v in inv.items()
          if k != 'engine_log.txt' and k not in abiertos),
      'solo existencia: %s' % sorted(abiertos | ({'engine_log.txt'} & set(inv))))
    aj = ubic / 'AJENO_CV.txt'
    c('ajeno_intacto_y_conservado', _sha_o_none(aj) == datos.get('ajeno_sha256')
      and 'AJENO_CV.txt' in (ab.get('conservados') or []))
    permitidas = {'AJENO_EXTERNO.txt', dp.name, ubic.name}
    c('sin_escritura_fuera', set(entradas) <= permitidas, str(entradas))
    return ch


def bateria(motores_dir, pcm_ref, etiqueta):
    filas, detalle = [], {}
    for motor in MOTORES:
        for esc in ESCENARIOS:
            r = ejecutar(motores_dir, motor, esc, etiqueta)
            ch = verificar(motor, esc, r, pcm_ref)
            ok = all(v[0] for v in ch.values())
            fallos = [k for k, v in ch.items() if not v[0]]
            detalle['%s/%s' % (motor, esc)] = dict(
                condicion=ESCENARIOS[esc][0], codigo=r['codigo'],
                codigo_esperado=ESCENARIOS[esc][1],
                comprobaciones={k: dict(ok=v[0], detalle=v[1]) for k, v in ch.items()},
                veredicto='PASS' if ok else 'FAIL', fallos=fallos,
                instantanea=r['estado'].get('datos', {}).get('provisional'),
                stdout_tail=r['stdout'][-1500:], stderr_tail=r['stderr'][-1500:])
            filas.append(dict(prueba=esc, motor=motor, condicion=ESCENARIOS[esc][0],
                              codigo_esperado=ESCENARIOS[esc][1], codigo=r['codigo'],
                              comprobaciones='%d/%d' % (sum(v[0] for v in ch.values()), len(ch)),
                              fallos=';'.join(fallos), veredicto='PASS' if ok else 'FAIL'))
            print('%-8s %-5s codigo=%-4s %s %s' % (motor, esc, r['codigo'],
                                                   'PASS' if ok else 'FAIL',
                                                   ','.join(fallos)), flush=True)
    return filas, detalle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=None,
                    help='carpeta de motores a diagnosticar (no cambia el veredicto)')
    ap.add_argument('--etiqueta-base', default='base')
    a = ap.parse_args()
    pcm_ref = pcm_registrado()
    res = dict(schema='pruebas-ciclo-vida-6g1/1', entorno=entorno(),
               motores_sha256={m: sha_file(MOT / n) for m, n in MOTORES.items()},
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               escenarios={k: dict(condicion=v[0], codigo_esperado=v[1], motivo=v[2],
                                   abort_registrado=v[3], trasladado=v[4],
                                   salidas_parciales=v[5]) for k, v in ESCENARIOS.items()})
    if a.base:
        bdir = Path(a.base).resolve()
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = bateria(bdir, pcm_ref, a.etiqueta_base)
        res['diagnostico_base'] = dict(etiqueta=a.etiqueta_base, carpeta=str(bdir),
                                       motores_sha256={m: sha_file(bdir / n) for m, n in MOTORES.items()},
                                       filas=fb, detalle=db,
                                       resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb),
                                                    total=len(fb)))
    print('== motores corregidos (%s)' % MOT)
    filas, det = bateria(MOT, pcm_ref, 'corregido')
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas)))
    EV.mkdir(parents=True, exist_ok=True)
    base_cod = {}
    if a.base:
        base_cod = {(f['motor'], f['prueba']): f for f in res['diagnostico_base']['filas']}
    with (EV / 'matriz_ciclo_vida_6g1.csv').open('w', newline='', encoding='utf-8') as fh:
        cols = list(filas[0]) + (['codigo_base', 'veredicto_base'] if a.base else [])
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator='\n')
        w.writeheader()
        for f in filas:
            g = dict(f)
            if a.base:
                b = base_cod.get((f['motor'], f['prueba']), {})
                g.update(codigo_base=b.get('codigo'), veredicto_base=b.get('veredicto'))
            w.writerow(g)
    dump(EV / 'pruebas_ciclo_vida_6g1.json', res)
    print('RESUMEN corregido: %d/%d PASS' % (res['resumen']['pass_'], res['resumen']['total']))
    if a.base:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base,
                                                res['diagnostico_base']['resumen']['pass_'],
                                                res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
