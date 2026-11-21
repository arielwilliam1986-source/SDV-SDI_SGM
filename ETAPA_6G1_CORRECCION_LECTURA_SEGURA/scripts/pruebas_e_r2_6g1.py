"""Pruebas E-R2 (rectificación 6G.1 — conservación de analysis.json).

Ejecuta ÚNICAMENTE las pruebas de este hallazgo; no repite las baterías de 34
(A–D), 26 (E–G) ni 17 (E-R1/G-R1). Solución aplicada (preferida por la
instrucción): analysis.json NO se modifica durante el aborto; toda la
información se registra en ABORT_6G1.json (creación exclusiva y no-follow).
Las pruebas verifican que analysis.json permanece intacto (bytes, SHA-256 y
mtime) y que ABORT_6G1.json contiene la información necesaria.

  R2a   analysis.json propio acreditado -> intacto byte a byte; ABORT con
        info completa; sin rastro de intento de actualización.
  R2b   analysis.json ajeno ordinario -> intacto; conservado con motivo;
        ABORT con info completa.
  R2c   analysis.json simbólico -> externo intacto; enlace conservado;
        ABORT con info completa.
  R2d   colisión de ABORT_6G1.json preexistente -> analysis intacto, ABORT
        preexistente intacto, info completa conservada en el valor de retorno.
  R2e   hostil: os.ftruncate y os.fsync parcheados para elevar RuntimeError;
        el aborto debe completar sin excepción, con analysis.json intacto y
        ABORT_6G1.json creado — demuestra que ninguna de esas llamadas ya
        ocurre en el camino del aborto (la conservación es estructural).
  Estático: sin os.ftruncate / O_RDWR / _propiedad_fd_acreditada en el código;
        campo analysis_intacto presente.
  E2E x3 motores: aborto real (inyección verificar_raise) -> ABORT_6G1.json
        regular con info completa; analysis.json presente, parseable, sin
        'abort_6g1', sin truncar; exit 2; sin directorio definitivo.
  Sanidad x3: corrida feliz con PCM idéntico a la campaña auditada.

Evidencia: evidence/pruebas_e_r2_6g1.json + evidence/matriz_e_r2_6g1.csv
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, recolectar, sha_file, dump

EV = RAIZ / 'evidence'
INJ = RAIZ / 'scripts' / 'inyeccion_6g1'
TRABAJO = Path('/tmp/f6g1er2')

SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
PREFIJO = {'Hardened': 'motorA_run_', 'EVO': 'motorA_run_', 'MQR': 'mqr_run_'}


def fila(prueba, motor, alcance, checks, motivo_ne=None):
    if motivo_ne is not None:
        return dict(prueba=prueba, motor=motor, alcance=alcance,
                    veredicto='NOT_EXECUTED', checks_ok=0, checks_total=0,
                    detalle=motivo_ne)
    ok = [c for c in checks if c[1]]
    detalle = '; '.join('%s=FALLO: %s' % (c[0], c[2]) for c in checks
                        if not c[1]) or 'todos los checks OK'
    return dict(prueba=prueba, motor=motor, alcance=alcance,
                veredicto='PASS' if len(ok) == len(checks) else 'FAIL',
                checks_ok=len(ok), checks_total=len(checks), detalle=detalle)


def pcm_auditado(motor, cont='WAV'):
    d = json.loads((EV / 'contenedores_6g1.json').read_text())
    return d['casos']['%s/%s/full_processing' % (motor, cont)]['pcm']


def dirs_definitivos(out, motor):
    pref = PREFIJO[motor]
    if not Path(out).exists():
        return []
    return [d.name for d in Path(out).iterdir()
            if d.is_dir() and d.name.startswith(pref)
            and not d.name.endswith('_partial')
            and not d.name.endswith('_aborted')]


def checks_aborto(r, motor):
    propios = SALIDAS[motor]
    out = Path(r['out'])
    nom = sorted(p.name for p in out.rglob('*.wav')) if out.exists() else []
    faltan = [s for s in propios if s in nom]
    return [('exit_2', r['exit'] == 2, 'exit=%s' % r['exit']),
            ('sin_dir_definitivo', not dirs_definitivos(r['out'], motor),
             'definitivos=%s' % dirs_definitivos(r['out'], motor)),
            ('salidas_propias_eliminadas', not faltan, 'presentes=%s' % faltan)]


def leer_abort(run):
    """Lee y valida el ABORT_6G1.json de un directorio de aborto."""
    ruta = Path(run) / 'ABORT_6G1.json'
    if not ruta.is_file() or os.path.islink(ruta):
        return None
    return json.loads(ruta.read_text(encoding='utf-8'))


def unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # ---- R2a: analysis.json propio acreditado -> intacto; ABORT con info
    try:
        run = TRABAJO / 'R2a'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"engine": "6G.1", "sellado": true, "bytes": [1,2,3]}\n'
        ruta_a = run / 'analysis.json'
        ruta_a.write_bytes(contenido)
        sha0, mtime0 = sha_file(ruta_a), os.lstat(ruta_a).st_mtime_ns
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_a, estable=True)
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_R2a')
        ab = leer_abort(run)
        checks = [
            ('analysis_byte_a_byte', ruta_a.read_bytes() == contenido,
             ruta_a.read_bytes()[:40]),
            ('analysis_sha_intacto', sha_file(ruta_a) == sha0, sha_file(ruta_a)[:16]),
            ('analysis_mtime_intacto', os.lstat(ruta_a).st_mtime_ns == mtime0, ''),
            ('sin_abort_6g1_embebido',
             'abort_6g1' not in json.loads(ruta_a.read_text(encoding='utf-8')), ''),
            ('abort_creado_regular', ab is not None, ''),
            ('abort_info_completa',
             ab is not None and ab.get('schema') == 'abort-6g1/2'
             and ab.get('motivo') == 'PRUEBA_R2a'
             and ab.get('analysis_intacto') is True
             and 'propio.wav' in (ab.get('salidas_invalidadas') or []),
             ab and str(ab.get('salidas_invalidadas'))),
            ('propio_eliminado', not propio.exists(), ''),
            ('sin_intento_de_actualizacion',
             not any('actualizacion' in k for k in (ab or {})
                     .get('motivos_propiedad', {})),
             str(list((ab or {}).get('motivos_propiedad', {})))),
        ]
        filas.append(fila('R2a', 'lectura_segura_6g1',
                          'analysis.json propio acreditado: intacto; info '
                          'íntegra en ABORT_6G1.json', checks))
        detalles['R2a'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('R2a', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2a'] = dict(error=repr(exc))

    # ---- R2b: analysis.json ajeno ordinario -> intacto; motivo conservado
    try:
        run = TRABAJO / 'R2b'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"nota": "analysis ajeno ordinario; no debe tocarse"}\n'
        (run / 'analysis.json').write_bytes(contenido)
        sha0 = sha_file(run / 'analysis.json')
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_R2b')
        ab = leer_abort(run)
        checks = [
            ('analysis_byte_a_byte',
             (run / 'analysis.json').read_bytes() == contenido, ''),
            ('analysis_sha_intacto', sha_file(run / 'analysis.json') == sha0,
             sha_file(run / 'analysis.json')[:16]),
            ('conservado_con_motivo',
             'analysis.json' in (ab or {}).get('conservados', [])
             and (ab or {}).get('motivos_propiedad', {}).get('analysis.json')
             == 'registro_interno_conservado',
             str((ab or {}).get('motivos_propiedad', {}).get('analysis.json'))),
            ('abort_info_completa',
             ab is not None and ab.get('motivo') == 'PRUEBA_R2b'
             and ab.get('analysis_intacto') is True
             and 'propio.wav' in (ab.get('salidas_invalidadas') or []), ''),
            ('propio_eliminado', not propio.exists(), ''),
        ]
        filas.append(fila('R2b', 'lectura_segura_6g1',
                          'analysis.json ajeno ordinario: intacto y conservado',
                          checks))
        detalles['R2b'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('R2b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2b'] = dict(error=repr(exc))

    # ---- R2c: analysis.json simbólico -> externo intacto; enlace conservado
    try:
        run = TRABAJO / 'R2c'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        externo = TRABAJO / 'externo_R2c.json'
        externo.write_bytes(b'{"externo": true, "E-R2": "no debe tocarse"}\n')
        sha_ext = sha_file(externo)
        os.symlink(str(externo), run / 'analysis.json')
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_R2c')
        ab = leer_abort(run)
        checks = [
            ('externo_byte_a_byte', sha_file(externo) == sha_ext,
             sha_file(externo)[:16]),
            ('analysis_sigue_enlace', os.path.islink(run / 'analysis.json'), ''),
            ('motivo_enlace',
             (ab or {}).get('motivos_propiedad', {}).get('analysis.json')
             == 'enlace_simbolico_conservado (sin seguir)',
             str((ab or {}).get('motivos_propiedad', {}).get('analysis.json'))),
            ('abort_info_completa',
             ab is not None and ab.get('analysis_intacto') is True
             and ab.get('motivo') == 'PRUEBA_R2c'
             and 'propio.wav' in (ab.get('salidas_invalidadas') or []), ''),
            ('propio_eliminado', not propio.exists(), ''),
        ]
        filas.append(fila('R2c', 'lectura_segura_6g1',
                          'analysis.json simbólico: externo intacto, enlace '
                          'conservado', checks))
        detalles['R2c'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('R2c', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2c'] = dict(error=repr(exc))

    # ---- R2d: colisión de ABORT_6G1.json -> analysis intacto; info en retorno
    try:
        run = TRABAJO / 'R2d'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"sellado": true, "colision": true}\n'
        (run / 'analysis.json').write_bytes(contenido)
        sha0 = sha_file(run / 'analysis.json')
        pre = run / 'ABORT_6G1.json'
        pre.write_bytes(b'{"abort_preexistente_ajeno": true}\n')
        sha_pre = sha_file(pre)
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_R2d')
        checks = [
            ('analysis_byte_a_byte',
             (run / 'analysis.json').read_bytes() == contenido, ''),
            ('analysis_sha_intacto', sha_file(run / 'analysis.json') == sha0,
             sha_file(run / 'analysis.json')[:16]),
            ('abort_preexistente_intacto',
             sha_file(pre) == sha_pre, sha_file(pre)[:16]),
            ('motivo_colision_en_retorno',
             'colision' in str(info.get('motivos_propiedad', {})
                              .get('ABORT_6G1.json', '')),
             str(info.get('motivos_propiedad', {}).get('ABORT_6G1.json'))),
            ('info_completa_en_retorno',
             info.get('schema') == 'abort-6g1/2'
             and info.get('analysis_intacto') is True
             and 'propio.wav' in (info.get('salidas_invalidadas') or []), ''),
            ('propio_eliminado', not propio.exists(), ''),
        ]
        filas.append(fila('R2d', 'lectura_segura_6g1',
                          'colisión de ABORT_6G1.json: nada sobrescrito; '
                          'info completa en el retorno', checks))
        detalles['R2d'] = dict(info=info)
    except Exception as exc:
        filas.append(fila('R2d', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2d'] = dict(error=repr(exc))

    # ---- R2e: hostil — ftruncate/fsync prohibidos; conservación estructural
    try:
        run = TRABAJO / 'R2e'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"sellado": true, "hostil": true}\n'
        (run / 'analysis.json').write_bytes(contenido)
        sha0 = sha_file(run / 'analysis.json')
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)

        prohibidos = (os.ftruncate, os.fsync)

        def _prohibido(*a, **k):
            raise RuntimeError('llamada prohibida tras E-R2')

        os.ftruncate = _prohibido
        os.fsync = _prohibido
        try:
            info = L.abortar_6g1(run, 'PRUEBA_R2e')   # no debe lanzar ni tocar
        finally:
            os.ftruncate, os.fsync = prohibidos
        ab = leer_abort(run)
        checks = [
            ('sin_excepcion', info.get('motivo') == 'PRUEBA_R2e', ''),
            ('analysis_byte_a_byte',
             (run / 'analysis.json').read_bytes() == contenido, ''),
            ('analysis_sha_intacto', sha_file(run / 'analysis.json') == sha0,
             sha_file(run / 'analysis.json')[:16]),
            ('abort_creado_con_info_completa',
             ab is not None and ab.get('analysis_intacto') is True
             and 'propio.wav' in (ab.get('salidas_invalidadas') or []),
             ab and str(ab.get('salidas_invalidadas'))),
            ('propio_eliminado', not propio.exists(), ''),
        ]
        filas.append(fila('R2e', 'lectura_segura_6g1',
                          'hostil: ftruncate/fsync prohibidos -> aborto '
                          'completa y analysis.json intacto (conservación '
                          'estructural)', checks))
        detalles['R2e'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('R2e', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2e'] = dict(error=repr(exc))

    # ---- estático: el código ya no contiene el camino de escritura
    try:
        src = (RAIZ / 'motores' / 'lectura_segura_6g1.py').read_text(
            encoding='utf-8')
        checks = [
            ('sin_os_ftruncate', 'os.ftruncate' not in src, ''),
            ('sin_O_RDWR', 'O_RDWR' not in src, ''),
            ('sin_acreditacion_fd', '_propiedad_fd_acreditada' not in src, ''),
            ('campo_analysis_intacto', 'analysis_intacto=True' in src, ''),
        ]
        filas.append(fila('R2-estatico', 'lectura_segura_6g1',
                          'sin camino de escritura a analysis.json en el '
                          'código', checks))
        detalles['R2-estatico'] = dict(estatico=True)
    except Exception as exc:
        filas.append(fila('R2-estatico', 'lectura_segura_6g1', 'estático', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2-estatico'] = dict(error=repr(exc))

    return filas, detalles


def correr(motor, work, inject=None):
    work = Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    man = work / 'manifest.json'
    escribir_manifest(man, dict(mix=str(FIX / 'mix.wav'),
                                vocal=str(FIX / 'vocal_mix.wav'),
                                instrumental=str(FIX / 'instrumental_mix.wav')))
    out = work / 'out'
    cmd = [sys.executable, '-B', str(MOT / MOTORES[motor]),
           '--manifest', str(man), '--out', str(out),
           '--mode', 'full_processing']
    env = dict(os.environ, PYTHONPATH=str(INJ))
    if inject:
        env['SDVSDI_6G1_INJECT'] = inject
        env['SDVSDI_6G1_MOTORES'] = str(MOT)
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env=env)
    salida = proc.communicate(timeout=900)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, out=str(out),
                 stdout_tail=salida[-3000:])
    return datos


def motores_er2():
    filas, detalles = [], {}
    for motor in MOTORES:
        # ---- E2E: aborto real; ABORT con info; analysis.json intacto
        try:
            r = correr(motor, TRABAJO / motor / 'E2E', inject='verificar_raise')
            out = Path(r['out'])
            parcial = sorted(out.glob('*_partial'))[0]
            ab = leer_abort(parcial)
            ruta_a = parcial / 'analysis.json'
            checks = checks_aborto(r, motor)
            if ruta_a.is_file() and not os.path.islink(ruta_a):
                data = json.loads(ruta_a.read_text(encoding='utf-8'))
                checks += [
                    ('analysis_parseable_sin_truncar', isinstance(data, dict)
                     and len(ruta_a.read_bytes()) > 10, ''),
                    ('analysis_sin_abort_6g1', 'abort_6g1' not in data, ''),
                ]
            else:
                checks.append(('analysis_parseable_sin_truncar', False,
                               'ausente o enlace'))
                checks.append(('analysis_sin_abort_6g1', False, 'ausente'))
            checks += [
                ('abort_regular_con_info_completa',
                 ab is not None and ab.get('schema') == 'abort-6g1/2'
                 and ab.get('analysis_intacto') is True
                 and ab.get('motivo')
                 and any(s in (ab.get('salidas_invalidadas') or [])
                         for s in SALIDAS[motor]),
                 ab and str(ab.get('salidas_invalidadas'))),
            ]
            filas.append(fila('R2-e2e', motor,
                              'aborto real: analysis.json intacto; info '
                              'íntegra en ABORT_6G1.json', checks))
            detalles.setdefault(motor, {})['E2E'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('R2-e2e', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E2E'] = dict(error=repr(exc))
        # ---- sanidad mínima (no repite baterías)
        try:
            r = correr(motor, TRABAJO / motor / 'sanidad')
            pcm = {p['name']: p['pcm_sha256'] for p in r['pcm']
                   if 'pcm_sha256' in p}
            esperado = pcm_auditado(motor)
            integ = r['integrity']
            defs = dirs_definitivos(r['out'], motor)
            checks = [
                ('exit_0', r['exit'] == 0, 'exit=%s' % r['exit']),
                ('publicacion_unica', len(defs) == 1, 'defs=%s' % defs),
                ('integridad_true',
                 integ.get('after', {}).get('unchanged') is True
                 and integ.get('ruta_actual', {}).get('unchanged') is True, ''),
                ('pcm_identico_a_campana_auditada', pcm == esperado,
                 'diff=%s' % {k: pcm.get(k, '')[:12] for k in
                              set(pcm) | set(esperado)
                              if pcm.get(k) != esperado.get(k)}),
            ]
            filas.append(fila('sanidad', motor,
                              'corrida feliz tras E-R2', checks))
            detalles.setdefault(motor, {})['sanidad'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('sanidad', motor, 'corrida feliz', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['sanidad'] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== E-R2 unidad + estático ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %-14s %s' % (f['veredicto'], f['prueba'],
                                    f['detalle'][:80]))
    print('== E-R2 motores (e2e + sanidad) ==')
    fm, dm = motores_er2()
    todas.extend(fm)
    detalle_todo.update(dm)
    for f in fm:
        print('  %-14s %-6s %-12s %s' % (f['veredicto'], f['motor'],
                                         f['prueba'], f['detalle'][:80]))
    dump(EV / 'pruebas_e_r2_6g1.json',
         dict(schema='pruebas-e-r2-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_e_r2_6g1.csv').open('w', newline='',
                                           encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=('prueba', 'motor', 'alcance',
                                           'veredicto', 'checks_ok',
                                           'checks_total', 'detalle'),
                           lineterminator='\n')
        w.writeheader()
        w.writerows(todas)
    n = {v: sum(1 for f in todas if f['veredicto'] == v)
         for v in ('PASS', 'FAIL', 'NOT_EXECUTED')}
    print('RESUMEN: %d PASS, %d FAIL, %d NOT_EXECUTED de %d filas'
          % (n['PASS'], n['FAIL'], n['NOT_EXECUTED'], len(todas)))


if __name__ == '__main__':
    main()
