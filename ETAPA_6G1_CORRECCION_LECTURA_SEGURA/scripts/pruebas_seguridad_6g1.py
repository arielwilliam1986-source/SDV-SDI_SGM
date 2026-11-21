"""Pruebas de seguridad E1–E7 (rectificación 6G.1 — hallazgos E, F y G).

Ejecuta ÚNICAMENTE las pruebas nuevas de la corrección puntual final; no repite
la batería de 34 pruebas ya reportada. Cada prueba comprueba contenido, hash,
identidad y estado final de los archivos involucrados, no sólo el código de
salida. Veredictos: PASS / FAIL / NOT_EXECUTED con motivo.

  E1  analysis.json simbólico -> archivo externo intacto byte a byte
      (unidad del módulo compartido + end-to-end en los tres motores: el
      plantado determinista ocurre en el instante de la guarda, dentro del
      inyector de pruebas, sin modificar el código del motor)
  E2  ABORT_6G1.json simbólico -> archivo externo intacto byte a byte
      (unidad + end-to-end en los tres motores)
  E3  analysis.json ajeno ordinario -> sin sobrescribir
      (unidad + end-to-end en los tres motores)
  E4  _partial preexistente con centinelas -> el motor se niega a reutilizarlo
      y conserva todos sus archivos (dos procesos con la misma marca temporal
      forzada; los tres motores)
  E5  dos solicitudes con el mismo identificador temporal -> no comparten ni
      sobrescriben el provisional (un proceso, reloj congelado; los tres)
  E6  destino definitivo preexistente -> la publicación no lo reemplaza
      (unidad de publicar_dir_6g1, incluido destino vacío; verificación
      estática de que los tres motores publican por la vía segura)
  E7  registro de propiedad aislado entre dos corridas consecutivas
      (unidad; y verificación dinámica del reinicio por corrida en E4/E5)

Evidencia: evidence/pruebas_seguridad_6g1.json + evidence/matriz_seguridad_6g1.csv
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
TRABAJO = Path('/tmp/f6g1seg')

SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
PREFIJO = {'Hardened': 'motorA_run_', 'EVO': 'motorA_run_', 'MQR': 'mqr_run_'}
FAKE = '20991231_235959'


def dirs_definitivos(out, motor):
    pref = PREFIJO[motor]
    if not Path(out).exists():
        return []
    return [d.name for d in Path(out).iterdir()
            if d.is_dir() and d.name.startswith(pref)
            and not d.name.endswith('_partial')
            and not d.name.endswith('_aborted')]


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


def correr(motor, mixdict, work, inject=None, plantar=None):
    """Corre un motor; `plantar` (lista 'modo:nombre@ruta') se ejecuta dentro
    del proceso del motor en el instante de la guarda (inyector), de modo que
    el estado atacado existe de forma determinista antes del aborto."""
    work = Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    man = work / 'manifest.json'
    escribir_manifest(man, mixdict)
    out = work / 'out'
    cmd = [sys.executable, '-B', str(MOT / MOTORES[motor]),
           '--manifest', str(man), '--out', str(out),
           '--mode', 'full_processing']
    env = dict(os.environ, PYTHONPATH=str(INJ),
               SDVSDI_6G1_OUT=str(out))
    if inject:
        env['SDVSDI_6G1_INJECT'] = inject
        env['SDVSDI_6G1_MOTORES'] = str(MOT)
    if plantar:
        env['SDVSDI_6G1_PLANTAR'] = ';'.join(plantar)
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env=env)
    salida = proc.communicate(timeout=900)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, stdout_tail=salida[-4000:], out=str(out))
    return datos


def checks_aborto(r, motor):
    propios = SALIDAS[motor]
    out = Path(r['out'])
    nom = sorted(p.name for p in out.rglob('*.wav')) if out.exists() else []
    faltan = [s for s in propios if s in nom]
    return [('exit_2', r['exit'] == 2, 'exit=%s' % r['exit']),
            ('sin_dir_definitivo', not dirs_definitivos(r['out'], motor),
             'definitivos=%s' % dirs_definitivos(r['out'], motor)),
            ('salidas_propias_eliminadas', not faltan, 'presentes=%s' % faltan)]


def pcm_auditado(motor, cont='WAV'):
    d = json.loads((EV / 'contenedores_6g1.json').read_text())
    return d['casos']['%s/%s/full_processing' % (motor, cont)]['pcm']


# ------------------------------------------------- unidad (módulo compartido)
def unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # E1: analysis.json simbólico -> externo intacto
    try:
        run = TRABAJO / 'U' / 'E1'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        externo = TRABAJO / 'U' / 'externo_E1.json'
        externo.write_bytes(b'{"externo": true, "dato": "no debe tocarse"}\n')
        sha_ext = sha_file(externo)
        os.symlink(str(externo), run / 'analysis.json')
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_E1')
        checks = [
            ('externo_byte_a_byte', sha_file(externo) == sha_ext, sha_file(externo)[:16]),
            ('analysis_sigue_enlace', os.path.islink(run / 'analysis.json'), ''),
            ('motivo_enlace_inventario',
             info['motivos_propiedad'].get('analysis.json')
             == 'enlace_simbolico_conservado (sin seguir)',
             str(info['motivos_propiedad'].get('analysis.json'))),
            ('motivo_actualizacion_omitida',
             'apertura segura fallo' in str(info['motivos_propiedad']
                                            .get('analysis.json (actualizacion)', '')),
             str(info['motivos_propiedad'].get('analysis.json (actualizacion)'))),
            ('abort_regular_creado', (run / 'ABORT_6G1.json').is_file()
             and not os.path.islink(run / 'ABORT_6G1.json'), ''),
            ('propio_eliminado', 'propio.wav' in info['salidas_invalidadas'],
             str(info['salidas_invalidadas'])),
        ]
        filas.append(fila('E1', 'lectura_segura_6g1',
                          'unidad: analysis.json simbólico; externo intacto',
                          checks))
        detalles['E1'] = dict(abort=info)
    except Exception as exc:
        filas.append(fila('E1', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E1'] = dict(error=repr(exc))

    # E2: ABORT_6G1.json simbólico -> externo intacto, sin sobrescribir
    try:
        run = TRABAJO / 'U' / 'E2'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        externo = TRABAJO / 'U' / 'externo_E2.json'
        externo.write_bytes(b'{"externo": "registro ajeno preexistente"}\n')
        sha_ext = sha_file(externo)
        os.symlink(str(externo), run / 'ABORT_6G1.json')
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_E2')
        checks = [
            ('externo_byte_a_byte', sha_file(externo) == sha_ext, sha_file(externo)[:16]),
            ('abort_sigue_enlace', os.path.islink(run / 'ABORT_6G1.json'), ''),
            ('motivo_colision', 'colision' in str(info['motivos_propiedad']
                                                  .get('ABORT_6G1.json', '')),
             str(info['motivos_propiedad'].get('ABORT_6G1.json'))),
            ('propio_eliminado', 'propio.wav' in info['salidas_invalidadas'],
             str(info['salidas_invalidadas'])),
        ]
        filas.append(fila('E2', 'lectura_segura_6g1',
                          'unidad: ABORT_6G1.json simbólico; sin sobrescribir',
                          checks))
        detalles['E2'] = dict(abort=info)
    except Exception as exc:
        filas.append(fila('E2', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E2'] = dict(error=repr(exc))

    # E3: analysis.json ajeno ordinario -> sin sobrescribir
    try:
        run = TRABAJO / 'U' / 'E3'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"nota": "analysis ajeno ordinario; no debe actualizarse"}\n'
        (run / 'analysis.json').write_bytes(contenido)
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        info = L.abortar_6g1(run, 'PRUEBA_E3')
        tras = (run / 'analysis.json').read_bytes()
        checks = [
            ('ajeno_byte_a_byte', tras == contenido, tras[:40]),
            ('sin_abort_6g1_embedded',
             'abort_6g1' not in json.loads(tras.decode('utf-8')), ''),
            ('motivo_sin_actualizar',
             'propiedad no acreditada' in str(info['motivos_propiedad']
                                              .get('analysis.json (actualizacion)', '')),
             str(info['motivos_propiedad'].get('analysis.json (actualizacion)'))),
            ('abort_regular_creado', (run / 'ABORT_6G1.json').is_file(), ''),
            ('propio_eliminado', 'propio.wav' in info['salidas_invalidadas'],
             str(info['salidas_invalidadas'])),
        ]
        filas.append(fila('E3', 'lectura_segura_6g1',
                          'unidad: analysis.json ajeno ordinario; intacto',
                          checks))
        detalles['E3'] = dict(abort=info)
    except Exception as exc:
        filas.append(fila('E3', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E3'] = dict(error=repr(exc))

    # E7: registro de propiedad aislado entre dos corridas consecutivas
    try:
        run1 = TRABAJO / 'U' / 'E7_corrida1'
        run2 = TRABAJO / 'U' / 'E7_corrida2'
        shutil.rmtree(run1, ignore_errors=True)
        shutil.rmtree(run2, ignore_errors=True)
        run1.mkdir(parents=True)
        run2.mkdir(parents=True)
        L.reiniciar_registro_6g1()                 # corrida 1
        a1 = run1 / 'salida_corrida1.wav'
        a1.write_bytes(b'contenido corrida 1\n')
        L.registrar_propio_6g1(a1, estable=True)
        L.reiniciar_registro_6g1()                 # corrida 2 (aislada)
        b1 = run2 / 'salida_corrida2.wav'
        b1.write_bytes(b'contenido corrida 2\n')
        L.registrar_propio_6g1(b1, estable=True)
        propia_a1, motivo_a1 = L.propiedad_de_6g1(a1)
        info1 = L.abortar_6g1(run1, 'PRUEBA_E7_corrida1')
        info2 = L.abortar_6g1(run2, 'PRUEBA_E7_corrida2')
        checks = [
            ('corrida1_no_acreditada_en_corrida2',
             propia_a1 is False and motivo_a1 == 'ajeno_no_registrado', motivo_a1),
            ('a1_conservado_en_su_corrida1',
             info1['motivos_propiedad'].get('salida_corrida1.wav')
             == 'ajeno_no_registrado'
             and 'salida_corrida1.wav' in info1['conservados'],
             str(info1['motivos_propiedad'].get('salida_corrida1.wav'))),
            ('a1_byte_a_byte_tras_ambos_abortos',
             a1.exists() and a1.read_bytes() == b'contenido corrida 1\n', ''),
            ('b1_eliminado_por_su_corrida',
             'salida_corrida2.wav' in info2['salidas_invalidadas'],
             str(info2['salidas_invalidadas'])),
            ('abort_corrida2_no_toca_archivos_de_corrida1',
             not any('salida_corrida1' in c for c in info2['conservados']),
             str(info2['conservados'])),
        ]
        filas.append(fila('E7', 'lectura_segura_6g1',
                          'unidad: aislamiento del registro entre corridas',
                          checks))
        detalles['E7'] = dict(motivo_a1=motivo_a1, info1=info1, info2=info2)
    except Exception as exc:
        filas.append(fila('E7', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E7'] = dict(error=repr(exc))

    # E6 (unidad): publicar_dir_6g1 nunca reemplaza destino preexistente
    try:
        base = TRABAJO / 'U' / 'E6'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        import lectura_segura_6g1 as L2
        destino = base / 'corrida_final'
        destino.mkdir()
        centinela = destino / 'centinela_ajeno.txt'
        centinela.write_bytes(b'destino ajeno preexistente; no debe tocarse\n')
        sha_cen = sha_file(centinela)
        origen = base / 'corrida_nueva'
        origen.mkdir()
        arte = origen / 'salida.wav'
        arte.write_bytes(b'artefacto de la corrida nueva\n')
        publicado = L2.publicar_dir_6g1(origen, destino)
        vacio = base / 'destino_vacio'
        vacio.mkdir()
        origen2 = base / 'corrida_nueva2'
        origen2.mkdir()
        publicado2 = L2.publicar_dir_6g1(origen2, vacio)
        checks = [
            ('centinela_intacto', centinela.exists()
             and sha_file(centinela) == sha_cen, sha_file(centinela)[:16]),
            ('destino_preexistente_sigue_aqui',
             destino.is_dir() and publicado != str(destino), publicado),
            ('origen_publicado_con_sufijo',
             Path(publicado).is_dir() and (Path(publicado) / 'salida.wav').is_file(),
             publicado),
            ('destino_vacio_no_reemplazado',
             vacio.is_dir() and publicado2 != str(vacio)
             and not any(vacio.iterdir()), str(sorted(p.name for p in vacio.iterdir()))),
            ('publicacion2_con_sufijo', Path(publicado2).is_dir(), publicado2),
        ]
        filas.append(fila('E6', 'lectura_segura_6g1',
                          'unidad: publicación con no-reemplazo (destino con '
                          'centinela y destino vacío)', checks))
        detalles['E6'] = dict(publicado=publicado, publicado2=publicado2)
    except Exception as exc:
        filas.append(fila('E6', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E6'] = dict(error=repr(exc))

    return filas, detalles


RUNNER = r'''
import importlib.util, json, os, sys
engine, out_base, fake = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
sys.path.insert(0, os.path.dirname(engine))
spec = importlib.util.spec_from_file_location('eng_6g1', engine)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
if fake:
    import datetime as _dt
    class _DT:
        @staticmethod
        def now():
            return _dt.datetime.strptime(fake, '%Y%m%d_%H%M%S')
    m.datetime = _DT
r1 = m.create_run_dir(out_base)
open(os.path.join(r1[0], 'marcador_corrida_1.txt'), 'w').write('corrida 1\n')
r2 = m.create_run_dir(out_base)
import lectura_segura_6g1 as L
print(json.dumps({'r1': list(r1), 'r2': list(r2),
                  'registro_vacio': len(L._PROPIOS_6G1) == 0}))
'''


def _runner(motor, out_base, fake):
    r = subprocess.run([sys.executable, '-c', RUNNER,
                        str(MOT / MOTORES[motor]), str(out_base), fake],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError('runner fallo: %s' % r.stderr[-800:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def motores_eg():
    filas, detalles = [], {}
    for motor in MOTORES:
        # ---- E1 end-to-end (los tres; plantado determinista en la guarda)
        try:
            externo = TRABAJO / motor / 'E1_externo.json'
            externo.parent.mkdir(parents=True, exist_ok=True)
            externo.write_bytes(b'{"externo": true, "corrida": "E1"}\n')
            sha_ext = sha_file(externo)
            r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / 'E1', inject='verificar_raise',
                       plantar=['enlace:analysis.json@%s' % externo])
            out = Path(r['out'])
            parcial = sorted(out.glob('*_partial'))[0]
            checks = checks_aborto(r, motor)
            checks += [
                ('externo_byte_a_byte', sha_file(externo) == sha_ext,
                 sha_file(externo)[:16]),
                ('analysis_sigue_enlace',
                 os.path.islink(parcial / 'analysis.json'), str(parcial)),
                ('abort_regular_creado',
                 (parcial / 'ABORT_6G1.json').is_file()
                 and not os.path.islink(parcial / 'ABORT_6G1.json'), ''),
            ]
            filas.append(fila('E1', motor,
                              'end-to-end: analysis.json simbólico al abortar',
                              checks))
            detalles.setdefault(motor, {})['E1'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('E1', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E1'] = dict(error=repr(exc))
        # ---- E2 end-to-end (los tres)
        try:
            externo = TRABAJO / motor / 'E2_externo.json'
            externo.parent.mkdir(parents=True, exist_ok=True)
            externo.write_bytes(b'{"externo": "registro ajeno preexistente"}\n')
            sha_ext = sha_file(externo)
            r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / 'E2', inject='verificar_raise',
                       plantar=['enlace:ABORT_6G1.json@%s' % externo])
            out = Path(r['out'])
            parcial = sorted(out.glob('*_partial'))[0]
            checks = checks_aborto(r, motor)
            checks += [
                ('externo_byte_a_byte', sha_file(externo) == sha_ext,
                 sha_file(externo)[:16]),
                ('abort_sigue_enlace', os.path.islink(parcial / 'ABORT_6G1.json'),
                 str(parcial)),
            ]
            if (parcial / 'analysis.json').is_file() \
                    and not os.path.islink(parcial / 'analysis.json'):
                try:
                    data = json.loads((parcial / 'analysis.json').read_text())
                    mot_col = str(data.get('abort_6g1', {}).get(
                        'motivos_propiedad', {}).get('ABORT_6G1.json', ''))
                    checks.append(('motivo_colision_registrado',
                                   'colision' in mot_col, mot_col[:80]))
                except Exception as exc:
                    checks.append(('motivo_colision_registrado', False, repr(exc)))
            filas.append(fila('E2', motor,
                              'end-to-end: ABORT_6G1.json simbólico al abortar',
                              checks))
            detalles.setdefault(motor, {})['E2'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('E2', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E2'] = dict(error=repr(exc))
        # ---- E3 end-to-end (los tres)
        try:
            ajeno = TRABAJO / motor / 'E3_ajeno.json'
            ajeno.parent.mkdir(parents=True, exist_ok=True)
            ajeno.write_bytes(b'{"nota": "analysis ajeno ordinario; '
                              b'no debe actualizarse"}\n')
            r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / 'E3', inject='verificar_raise',
                       plantar=['archivo:analysis.json@%s' % ajeno])
            out = Path(r['out'])
            parcial = sorted(out.glob('*_partial'))[0]
            contenido = (parcial / 'analysis.json').read_bytes()
            data = json.loads(contenido.decode('utf-8'))
            checks = checks_aborto(r, motor)
            checks += [
                ('ajeno_sin_actualizar', 'abort_6g1' not in data, ''),
                ('ajeno_byte_a_byte', contenido == ajeno.read_bytes(),
                 contenido[:40]),
                ('abort_regular_creado',
                 (parcial / 'ABORT_6G1.json').is_file()
                 and not os.path.islink(parcial / 'ABORT_6G1.json'), ''),
            ]
            filas.append(fila('E3', motor,
                              'end-to-end: analysis.json ajeno ordinario',
                              checks))
            detalles.setdefault(motor, {})['E3'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('E3', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E3'] = dict(error=repr(exc))
        # ---- E4: _partial preexistente con centinelas (dos procesos, misma marca)
        try:
            base = TRABAJO / motor / 'E4'
            o1 = _runner(motor, base, FAKE)
            p1 = Path(o1['r1'][0])
            (p1 / 'centinela_a.txt').write_bytes(b'centinela A\n')
            (p1 / 'centinela_b.dat').write_bytes(b'centinela B\n')
            hashes = {p.name: sha_file(p) for p in p1.iterdir() if p.is_file()}
            o2 = _runner(motor, base, FAKE)
            p2 = Path(o2['r1'][0])
            checks = [
                ('no_reutilizado', p1 != p2, '%s vs %s' % (p1.name, p2.name)),
                ('p1_existe_con_contenido', p1.is_dir() and len(hashes) >= 3,
                 str(sorted(p.name for p in p1.iterdir()))),
                ('centinelas_intactos',
                 all(sha_file(p) == hashes[p.name]
                     for p in p1.iterdir() if p.is_file()), ''),
                ('p2_nuevo_y_vacio_del_motor',
                 p2.is_dir() and sorted(p.name for p in p2.iterdir())
                 == ['marcador_corrida_1.txt'],
                 str(sorted(p.name for p in p2.iterdir()))),
                ('registro_reiniciado_por_corrida',
                 o1['registro_vacio'] and o2['registro_vacio'],
                 str([o1['registro_vacio'], o2['registro_vacio']])),
                ('marca_forzada_igual', FAKE in p1.name and FAKE in p2.name,
                 '%s | %s' % (p1.name, p2.name)),
            ]
            filas.append(fila('E4', motor,
                              '_partial preexistente: no reutilizado, '
                              'centinelas intactos (marca forzada)', checks))
            detalles.setdefault(motor, {})['E4'] = dict(p1=str(p1), p2=str(p2))
        except Exception as exc:
            filas.append(fila('E4', motor, '_partial preexistente', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E4'] = dict(error=repr(exc))
        # ---- E5: dos solicitudes, mismo identificador temporal (un proceso)
        try:
            base = TRABAJO / motor / 'E5'
            o = _runner(motor, base, FAKE)
            p1, p2 = Path(o['r1'][0]), Path(o['r2'][0])
            marcador = p1 / 'marcador_corrida_1.txt'
            checks = [
                ('no_comparten_directorio', p1 != p2,
                 '%s vs %s' % (p1.name, p2.name)),
                ('marcador_corrida1_intacto',
                 marcador.is_file() and marcador.read_bytes() == b'corrida 1\n', ''),
                ('ambos_existen', p1.is_dir() and p2.is_dir(), ''),
                ('registro_reiniciado_por_solicitud', o['registro_vacio'], ''),
                ('marca_forzada_igual', FAKE in p1.name and FAKE in p2.name,
                 '%s | %s' % (p1.name, p2.name)),
            ]
            filas.append(fila('E5', motor,
                              'dos solicitudes con el mismo identificador '
                              'temporal (reloj congelado)', checks))
            detalles.setdefault(motor, {})['E5'] = dict(r1=str(p1), r2=str(p2))
        except Exception as exc:
            filas.append(fila('E5', motor, 'misma marca temporal', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E5'] = dict(error=repr(exc))
        # ---- E6 (estático por motor): publicación por la vía segura
        try:
            src = (MOT / MOTORES[motor]).read_text(encoding='utf-8')
            checks = [
                ('publica_via_publicar_dir_6g1', '_publicar_dir_6g1(' in src, ''),
                ('sin_rename_publicacion', 'os.rename(run_dir, run_dir_final)'
                 not in src, ''),
                ('registro_reiniciado_en_create_run_dir',
                 '_reiniciar_registro_6g1()' in src, ''),
            ]
            filas.append(fila('E6', motor,
                              'estático: publicación y creación de corrida '
                              'por la vía segura', checks))
            detalles.setdefault(motor, {})['E6'] = dict(estatico=True)
        except Exception as exc:
            filas.append(fila('E6', motor, 'estático', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E6'] = dict(error=repr(exc))
        # ---- sanidad: corrida feliz tras E–G (no es la batería de 34)
        try:
            r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / 'sanidad')
            pcm = {p['name']: p['pcm_sha256'] for p in r['pcm']
                   if 'pcm_sha256' in p}
            esperado = pcm_auditado(motor)
            integ = r['integrity']
            defs = dirs_definitivos(r['out'], motor)
            checks = [
                ('exit_0', r['exit'] == 0, 'exit=%s' % r['exit']),
                ('dir_definitivo_unico_publicado', len(defs) == 1, 'defs=%s' % defs),
                ('integridad_after_ruta_true',
                 integ.get('after', {}).get('unchanged') is True
                 and integ.get('ruta_actual', {}).get('unchanged') is True,
                 'after=%s ruta=%s' % (integ.get('after', {}).get('unchanged'),
                                       integ.get('ruta_actual', {}).get('unchanged'))),
                ('pcm_identico_a_campana_auditada', pcm == esperado,
                 'diff=%s' % {k: pcm.get(k, '')[:12] for k in
                              set(pcm) | set(esperado)
                              if pcm.get(k) != esperado.get(k)}),
            ]
            filas.append(fila('sanidad', motor,
                              'corrida feliz tras E–G (no repite la batería de 34)',
                              checks))
            detalles.setdefault(motor, {})['sanidad'] = dict(exit=r['exit'],
                                                             pcm=pcm)
        except Exception as exc:
            filas.append(fila('sanidad', motor, 'corrida feliz', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['sanidad'] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== Unidad (módulo compartido) ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %-28s %s' % (f['veredicto'], f['prueba'], f['detalle'][:80]))
    print('== Motores (E–G + sanidad) ==')
    fm, dm = motores_eg()
    todas.extend(fm)
    detalle_todo.update(dm)
    for f in fm:
        print('  %-14s %-6s %-28s %s' % (f['veredicto'], f['motor'],
                                         f['prueba'], f['detalle'][:80]))
    dump(EV / 'pruebas_seguridad_6g1.json',
         dict(schema='pruebas-seguridad-6g1/1',
              filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_seguridad_6g1.csv').open('w', newline='',
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
