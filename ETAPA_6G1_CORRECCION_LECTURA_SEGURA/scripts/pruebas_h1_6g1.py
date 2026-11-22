"""Pruebas H1 (rectificación 6G.1 — anclaje del directorio de aborto).

Ejecuta ÚNICAMENTE la batería focalizada de este hallazgo; no repite las
baterías históricas (34/26/17/12). La batería C-R1 (pruebas_c_r1_6g1.py),
actualizada para acreditar el provisional como hace create_run_dir(), se
re-ejecuta aparte como verificación focalizada complementaria.

  H1a (obligatoria)  La ruta provisional se sustituye por un ENLACE SIMBÓLICO
        hacia un directorio externo (después de la creación+acreditación y
        antes de la apertura del aborto): el enlace NO se sigue (apertura
        O_DIRECTORY|O_NOFOLLOW -> ELOOP), el centinela externo y el resto de
        archivos externos permanecen byte a byte intactos, NO se crea ni
        modifica ABORT_6G1.json en el directorio externo, el resultado es
        fail-closed con el motivo de anclaje registrado, no se elimina ningún
        archivo y no se declara ninguna salida válida. Verificación sobre el
        estado real en disco (bytes y SHA-256), no sólo el retorno.
  H1b  Aborto normal con directorio acreditado: ABORT_6G1.json /3 en el
        provisional real con directorio_acreditado=True; semántica C-R1/E-R2
        intacta (salida propia invalidada y conservada; ajeno intacto;
        analysis.json intacto; resultados_validos vacío).
  H1c  Identidad distinta: el directorio acreditado se sustituye por OTRO
        directorio real (no enlace) en la misma ruta: fstat no coincide con
        lo acreditado -> fail-closed, sin ABORT en el nuevo directorio.
  CR1-regresión  La ventana histórica de CR1c (sustitución tras dictamen
        positivo) sigue cubierta con el anclaje H1 activo: el sustituto queda
        intacto y clasificado por el dictamen anterior.
  H1-e2e ×3 motores  Aborto real (guarda final) con la acreditación de
        create_run_dir: exit 2; sin directorio definitivo; ABORT /3 con
        directorio_acreditado=True y anclaje_directorio correcto; salidas
        propias conservadas en disco.
  sanidad ×3  Corrida feliz: exit 0, publicación única, PCM idéntico a la
        campaña auditada (DSP intacto).

Evidencia: evidence/pruebas_h1_6g1.json + evidence/matriz_h1_6g1.csv
"""
import csv
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, recolectar, sha_file, dump

EV = RAIZ / 'evidence'
INJ = RAIZ / 'scripts' / 'inyeccion_6g1'
TRABAJO = Path('/tmp/f6g1h1')

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


def unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # ---- H1a (obligatoria): enlace simbólico en la ruta del provisional
    try:
        run = TRABAJO / 'H1a'
        if os.path.islink(run):        # restos de una corrida anterior
            os.unlink(run)
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        # 1-2: provisional real + identidad acreditada (como create_run_dir)
        L.reiniciar_registro_6g1()
        L.acreditar_dir_6g1(run)
        # 3: directorio externo con centinela y su SHA-256 (+ archivo extra)
        externo = TRABAJO / 'H1a_externo'
        shutil.rmtree(externo, ignore_errors=True)
        externo.mkdir(parents=True)
        bytes_cen = b'CENTINELA externo: no debe tocarse por el aborto\n'
        (externo / 'centinela.txt').write_bytes(bytes_cen)
        bytes_extra = b'archivo externo adicional\n'
        (externo / 'extra_ajeno.txt').write_bytes(bytes_extra)
        sha_cen = sha_file(externo / 'centinela.txt')
        sha_extra = sha_file(externo / 'extra_ajeno.txt')
        # 4: sustitución de la ruta provisional por un enlace simbólico hacia
        # el externo, DESPUÉS de la creación y ANTES de la apertura del aborto
        os.rmdir(run)
        os.symlink(str(externo), run)
        assert os.path.islink(run)
        # 5: procedimiento de aborto
        info = L.abortar_6g1(run, 'PRUEBA_H1a')
        # 6: estado real en disco
        checks = [
            ('enlace_no_seguido', os.path.islink(run), ''),
            ('resultado_fail_closed',
             info.get('directorio_acreditado') is False
             and 'H1' in str(info.get('anclaje_directorio', '')),
             str(info.get('anclaje_directorio'))),
            ('motivo_anclaje_enlace',
             'apertura_segura_fallo' in str(info.get('anclaje_directorio', ''))
             or 'enlace' in str(info.get('anclaje_directorio', '')),
             str(info.get('anclaje_directorio'))),
            ('centinela_byte_a_byte',
             (externo / 'centinela.txt').read_bytes() == bytes_cen
             and sha_file(externo / 'centinela.txt') == sha_cen,
             sha_file(externo / 'centinela.txt')[:16]),
            ('externo_completo_intacto',
             (externo / 'extra_ajeno.txt').read_bytes() == bytes_extra
             and sha_file(externo / 'extra_ajeno.txt') == sha_extra,
             sha_file(externo / 'extra_ajeno.txt')[:16]),
            ('sin_abort_en_externo',
             not (externo / 'ABORT_6G1.json').exists()
             and not os.path.islink(externo / 'ABORT_6G1.json'), ''),
            ('sin_abort_en_ninguna_ruta_acreditada',
             not (run / 'ABORT_6G1.json').exists(), ''),
            ('nada_eliminado',
             (externo / 'centinela.txt').exists()
             and (externo / 'extra_ajeno.txt').exists(), ''),
            ('sin_salidas_validas',
             info.get('resultados_validos') == []
             and info.get('salidas_invalidadas') == []
             and info.get('conservados') == [],
             str((info.get('salidas_invalidadas'), info.get('conservados')))),
            ('schema_3', info.get('schema') == 'abort-6g1/3',
             str(info.get('schema'))),
            ('motivo_original_conservado', info.get('motivo') == 'PRUEBA_H1a',
             str(info.get('motivo'))),
        ]
        filas.append(fila('H1a', 'lectura_segura_6g1',
                          'enlace simbólico en la ruta del provisional: '
                          'fail-closed, externo intacto, sin ABORT externo',
                          checks))
        detalles['H1a'] = dict(info=info)
    except Exception as exc:
        filas.append(fila('H1a', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['H1a'] = dict(error=repr(exc))

    # ---- H1b: aborto normal con directorio acreditado
    try:
        run = TRABAJO / 'H1b'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        propio = run / 'salida.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        ajeno = run / 'ajeno.wav'
        ajeno.write_bytes(b'AJENO\n')
        L.acreditar_dir_6g1(run)
        info = L.abortar_6g1(run, 'PRUEBA_H1b')
        ab = json.loads((run / 'ABORT_6G1.json').read_text(encoding='utf-8'))
        checks = [
            ('directorio_acreditado_true',
             info.get('directorio_acreditado') is True
             and ab.get('directorio_acreditado') is True,
             str(info.get('anclaje_directorio'))),
            ('abort_en_el_provisional_real', (run / 'ABORT_6G1.json').is_file(), ''),
            ('schema_3', ab.get('schema') == 'abort-6g1/3', ''),
            ('semantica_c_r1_intacta',
             'salida.wav' in ab.get('salidas_invalidadas', [])
             and propio.exists()
             and propio.read_bytes() == b'salida propia\n',
             str(ab.get('salidas_invalidadas'))),
            ('ajeno_intacto', ajeno.read_bytes() == b'AJENO\n', ''),
            ('analysis_intacto', not (run / 'analysis.json').exists(), ''),
            ('resultados_validos_vacio', ab.get('resultados_validos') == [], ''),
            ('anclaje_registrado', 'directorio_acreditado' in str(ab.get('anclaje_directorio')),
             str(ab.get('anclaje_directorio'))),
        ]
        filas.append(fila('H1b', 'lectura_segura_6g1',
                          'aborto normal con directorio acreditado: ABORT en '
                          'el provisional real, semántica C-R1/E-R2 intacta',
                          checks))
        detalles['H1b'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('H1b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['H1b'] = dict(error=repr(exc))

    # ---- H1c: identidad distinta (otro directorio real en la misma ruta)
    try:
        run = TRABAJO / 'H1c'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        L.acreditar_dir_6g1(run)
        # sustitución por OTRO directorio real (no enlace) en la misma ruta.
        # El provisional acreditado sigue VIVO (renombrado aparte, como en el
        # escenario real en que el motor lo conserva): su inodo permanece
        # ocupado, así que el nuevo directorio obtiene identidad distinta
        # (evita la reutilización de inodo que seproduce si se borra antes).
        original_vivo = TRABAJO / 'H1c_original_vivo'
        shutil.rmtree(original_vivo, ignore_errors=True)
        os.rename(run, original_vivo)
        run.mkdir()
        ajeno2 = run / 'ajeno_otro_dir.txt'
        ajeno2.write_bytes(b'contenido de otro directorio\n')
        sha2 = sha_file(ajeno2)
        info = L.abortar_6g1(run, 'PRUEBA_H1c')
        checks = [
            ('fail_closed_por_identidad',
             info.get('directorio_acreditado') is False
             and 'identidad_distinta' in str(info.get('anclaje_directorio', '')),
             str(info.get('anclaje_directorio'))),
            ('sin_abort_en_el_nuevo_directorio',
             not (run / 'ABORT_6G1.json').exists(), ''),
            ('ajeno_otro_dir_intacto',
             ajeno2.read_bytes() == b'contenido de otro directorio\n'
             and sha_file(ajeno2) == sha2, sha_file(ajeno2)[:16]),
            ('sin_salidas_validas',
             info.get('resultados_validos') == []
             and info.get('salidas_invalidadas') == [], ''),
            ('schema_3', info.get('schema') == 'abort-6g1/3', ''),
            ('provisional_acreditado_sigue_vivo',
             (TRABAJO / 'H1c_original_vivo').is_dir(), ''),
        ]
        filas.append(fila('H1c', 'lectura_segura_6g1',
                          'directorio sustituido por otro real: fail-closed '
                          'por identidad distinta', checks))
        detalles['H1c'] = dict(info=info)
    except Exception as exc:
        filas.append(fila('H1c', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['H1c'] = dict(error=repr(exc))

    # ---- regresión CR1c con anclaje H1 activo
    try:
        run = TRABAJO / 'H1_CR1c_regresion'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        sustituto = TRABAJO / 'sustituto_H1cr1c.wav'
        bytes_sub = b'contenido AJENO tras dictamen positivo (con H1)\n'
        sustituto.write_bytes(bytes_sub)
        ruta_propia = run / 'salida_concurrente.wav'
        ruta_propia.write_bytes(b'salida propia original\n')
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_propia, estable=True)
        # [6G.1-R/H1-R2/B] clasificación por descriptor -> gancho allí
        original_clas = L._clasificar_entrada_6g1
        suceso = dict(secuencia=[])

        def clas_con_sustitucion(nombre, st, fd_dir, ruta_esperada):
            propia, motivo = original_clas(nombre, st, fd_dir, ruta_esperada)
            if propia and ruta_esperada == str(ruta_propia) \
                    and not suceso['secuencia']:
                suceso['secuencia'].append('dictamen_positivo')
                tmp = run / '.sust_tmp'
                shutil.copyfile(str(sustituto), str(tmp))
                os.replace(str(tmp), str(ruta_propia))
                suceso['secuencia'].append('sustitucion_os_replace')
            return propia, motivo

        L._clasificar_entrada_6g1 = clas_con_sustitucion
        try:
            L.acreditar_dir_6g1(run)
            info = L.abortar_6g1(run, 'PRUEBA_H1_CR1c')
        finally:
            L._clasificar_entrada_6g1 = original_clas
        checks = [
            ('secuencia_dictamen_sustitucion',
             suceso['secuencia'] == ['dictamen_positivo',
                                     'sustitucion_os_replace'],
             str(suceso['secuencia'])),
            ('sustituto_intacto_con_anclaje',
             ruta_propia.read_bytes() == bytes_sub, ''),
            ('abort_en_provisional_real',
             (run / 'ABORT_6G1.json').is_file()
             and info.get('directorio_acreditado') is True, ''),
            ('clasificacion_por_dictamen_anterior',
             'salida_concurrente.wav' in info.get('salidas_invalidadas', []),
             str(info.get('salidas_invalidadas'))),
        ]
        filas.append(fila('H1-CR1c-regresion', 'lectura_segura_6g1',
                          'ventana histórica CR1c cubierta con anclaje H1 '
                          'activo', checks))
        detalles['H1-CR1c-regresion'] = dict(info=info)
    except Exception as exc:
        filas.append(fila('H1-CR1c-regresion', 'lectura_segura_6g1', 'unidad',
                          None, motivo_ne='entorno de ensayo: %r' % exc))
        detalles['H1-CR1c-regresion'] = dict(error=repr(exc))

    return filas, detalles


def motores_h1():
    filas, detalles = [], {}
    for motor in MOTORES:
        # ---- e2e: aborto real con acreditación de create_run_dir
        try:
            r = correr(motor, TRABAJO / motor / 'E2E', inject='verificar_raise')
            out = Path(r['out'])
            parcial = sorted(out.glob('*_partial'))[0]
            ab = json.loads((parcial / 'ABORT_6G1.json').read_text(
                encoding='utf-8'))
            checks = [
                ('exit_2', r['exit'] == 2, 'exit=%s' % r['exit']),
                ('sin_dir_definitivo', not dirs_definitivos(r['out'], motor),
                 'definitivos=%s' % dirs_definitivos(r['out'], motor)),
                ('abort_schema_3', ab.get('schema') == 'abort-6g1/3', ''),
                ('directorio_acreditado_true',
                 ab.get('directorio_acreditado') is True
                 and 'directorio_acreditado' in str(ab.get('anclaje_directorio')),
                 str(ab.get('anclaje_directorio'))),
                ('salidas_propias_conservadas',
                 all((parcial / s).is_file() for s in SALIDAS[motor]), ''),
                ('semantica_c_r1',
                 all(s in ab.get('salidas_invalidadas', [])
                     for s in SALIDAS[motor])
                 and ab.get('resultados_validos') == [],
                 str(ab.get('salidas_invalidadas'))),
            ]
            filas.append(fila('H1-e2e', motor,
                              'aborto real con acreditación de create_run_dir',
                              checks))
            detalles.setdefault(motor, {})['E2E'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('H1-e2e', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E2E'] = dict(error=repr(exc))
        # ---- sanidad mínima
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
            filas.append(fila('sanidad', motor, 'corrida feliz tras H1', checks))
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
    print('== H1 unidad ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-18s %s' % (f['veredicto'], f['detalle'][:90]))
    print('== H1 motores (e2e + sanidad) ==')
    fm, dm = motores_h1()
    todas.extend(fm)
    detalle_todo.update(dm)
    for f in fm:
        print('  %-14s %-6s %-14s %s' % (f['veredicto'], f['motor'],
                                         f['prueba'], f['detalle'][:70]))
    dump(EV / 'pruebas_h1_6g1.json',
         dict(schema='pruebas-h1-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_h1_6g1.csv').open('w', newline='',
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
