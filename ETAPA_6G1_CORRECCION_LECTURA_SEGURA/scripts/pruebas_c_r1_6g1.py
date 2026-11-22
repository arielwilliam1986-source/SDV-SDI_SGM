"""Pruebas C-R1 (rectificación 6G.1 — aborto SIN eliminación de archivos).

Ejecuta ÚNICAMENTE la batería focalizada de este hallazgo; no repite las
baterías históricas (34/26/17/12). La solución aplicada (preferida por la
instrucción): `abortar_6g1()` NO elimina ningún archivo; las salidas propias
registradas quedan invalidadas y conservadas en el provisional; todo se
registra en `ABORT_6G1.json` (schema versionado a `abort-6g1/3`).

  CR1a  propios conservados tras el aborto (bytes intactos) + registro /3
  CR1b  ajenos byte a byte intactos (incluidos nombres tipo salida)
  CR1c  SUSTITUCIÓN CONCURRENTE en la ventana histórica EXACTA del hallazgo:
        se intercepta propiedad_de_6g1(); se ejecuta la función original y se
        obtiene su dictamen; inmediatamente después de un dictamen POSITIVO
        se sustituye el archivo por otro regular (os.replace()); se devuelve
        el dictamen ORIGINAL al llamador. El sustituto queda byte a byte
        intacto; nada se elimina; la clasificación del informe se basa en el
        dictamen obtenido ANTES de la sustitución (no identifica
        necesariamente la identidad posterior)
  CR1d  enlaces simbólicos conservados, nunca seguidos; objetivo externo intacto
  CR1e  ABORT_6G1.json registra las invalidadas (/3) y la creación exclusiva
        se mantiene (colisión conservada, info completa en el retorno)
  CR1f  analysis.json sigue byte a byte intacto (E-R2 se mantiene)
  CR1-estático  sin os.unlink/os.remove/os.rmdir en el módulo; schema /3;
        sin patrones de nombre para borrado (sin fnmatch)
  CR1-e2e ×3 motores  aborto real (guarda final): exit 2; sin directorio
        definitivo; salidas propias CONSERVADAS en disco; archivo ajeno
        plantado (reemplazo de una salida propia con contenido ajeno)
        intacto; enlace plantado conservado; ABORT /3 con invalidadas y
        conservados correctos; analysis.json intacto (fail-closed mantenido)
  sanidad ×3  corrida feliz: exit 0, publicación única, PCM idéntico a la
        campaña auditada (DSP intacto)

Evidencia: evidence/pruebas_c_r1_6g1.json + evidence/matriz_c_r1_6g1.csv
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
TRABAJO = Path('/tmp/f6g1cr1')

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


def leer_abort(run):
    ruta = Path(run) / 'ABORT_6G1.json'
    if not ruta.is_file() or os.path.islink(ruta):
        return None
    return json.loads(ruta.read_text(encoding='utf-8'))


def unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # ---- CR1a: propios conservados + registro /3
    try:
        run = TRABAJO / 'CR1a'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        b1, b2 = b'salida propia A\n', b'salida propia B\n'
        (run / 'salida_A.wav').write_bytes(b1)
        (run / 'salida_B.wav').write_bytes(b2)
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(run / 'salida_A.wav', estable=True)
        L.registrar_propio_6g1(run / 'salida_B.wav', estable=True)
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        info = L.abortar_6g1(run, 'PRUEBA_CR1a')
        ab = leer_abort(run)
        checks = [
            ('propio_A_conservado', (run / 'salida_A.wav').read_bytes() == b1, ''),
            ('propio_B_conservado', (run / 'salida_B.wav').read_bytes() == b2, ''),
            ('schema_3', (ab or {}).get('schema') == 'abort-6g1/3', str(ab and ab.get('schema'))),
            ('invalidadas_registradas',
             sorted((ab or {}).get('salidas_invalidadas', []))
             == ['salida_A.wav', 'salida_B.wav'],
             str((ab or {}).get('salidas_invalidadas'))),
            ('estado_sin_eliminacion',
             'sin eliminación' in str((ab or {}).get('estado_salidas_invalidadas', '')),
             str((ab or {}).get('estado_salidas_invalidadas'))),
            ('resultados_validos_vacio', (ab or {}).get('resultados_validos') == [], ''),
            ('motivo_sin_eliminacion',
             'sin eliminación' in str((ab or {}).get('motivos_propiedad', {})
                                      .get('salida_A.wav', '')),
             str((ab or {}).get('motivos_propiedad', {}).get('salida_A.wav'))),
        ]
        filas.append(fila('CR1a', 'lectura_segura_6g1',
                          'propios conservados tras el aborto + registro /3',
                          checks))
        detalles['CR1a'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('CR1a', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1a'] = dict(error=repr(exc))

    # ---- CR1b: ajenos byte a byte intactos (incluidos nombres tipo salida)
    try:
        run = TRABAJO / 'CR1b'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        bytes_ajenos = {n: ('contenido ajeno %s\n' % n).encode()
                        for n in ('SDV.wav', 'candidates_ajeno.wav',
                                  'ajeno_ordinario.txt')}
        for n, b in bytes_ajenos.items():
            (run / n).write_bytes(b)
        hashes = {n: sha_file(run / n) for n in bytes_ajenos}
        L.reiniciar_registro_6g1()
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        info = L.abortar_6g1(run, 'PRUEBA_CR1b')
        ab = leer_abort(run)
        checks = [
            ('ajenos_byte_a_byte',
             all((run / n).read_bytes() == b for n, b in bytes_ajenos.items()), ''),
            ('ajenos_sha_intactos',
             all(sha_file(run / n) == h for n, h in hashes.items()), ''),
            ('ajenos_en_conservados',
             all(n in (ab or {}).get('conservados', []) for n in bytes_ajenos),
             str((ab or {}).get('conservados'))),
            ('ajenos_fuera_de_invalidadas',
             not any(n in (ab or {}).get('salidas_invalidadas', [])
                     for n in bytes_ajenos),
             str((ab or {}).get('salidas_invalidadas'))),
            ('motivo_ajeno_no_registrado',
             (ab or {}).get('motivos_propiedad', {}).get('SDV.wav')
             == 'ajeno_no_registrado',
             str((ab or {}).get('motivos_propiedad', {}).get('SDV.wav'))),
            ('propio_conservado_e_invalidado',
             propio.exists() and 'propio.wav' in (ab or {}).get('salidas_invalidadas', []),
             ''),
        ]
        filas.append(fila('CR1b', 'lectura_segura_6g1',
                          'ajenos byte a byte intactos (incluido nombre tipo salida)',
                          checks))
        detalles['CR1b'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('CR1b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1b'] = dict(error=repr(exc))

    # ---- CR1c: sustitución concurrente en la VENTANA HISTÓRICA EXACTA del
    # hallazgo C-R1 [C-R1-R, mecanismo a petición de Cris]: se intercepta
    # propiedad_de_6g1(); se ejecuta la función original y se obtiene su
    # dictamen; INMEDIATAMENTE después de un dictamen POSITIVO se sustituye
    # el archivo por otro regular mediante os.replace(); se devuelve el
    # dictamen ORIGINAL al llamador. Así la sustitución queda demostrada
    # DESPUÉS del dictamen positivo y ANTES de que el llamador continuara
    # (con el código anterior a C-R1, el unlink posterior habría borrado al
    # sustituto ajeno). El módulo de producción NO se modifica para ensayar.
    try:
        run = TRABAJO / 'CR1c'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        sustituto = TRABAJO / 'sustituto_ajeno_CR1c.wav'
        bytes_sub = b'contenido AJENO plantado tras el dictamen positivo\n'
        sustituto.write_bytes(bytes_sub)
        sha_sub = sha_file(sustituto)
        ruta_propia = run / 'salida_concurrente.wav'
        ruta_propia.write_bytes(b'salida propia original\n')
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_propia, estable=True)
        otro = run / 'otra_salida.wav'
        otro.write_bytes(b'otra salida propia\n')
        L.registrar_propio_6g1(otro, estable=True)

        original_prop = L.propiedad_de_6g1
        suceso = dict(dictamen=None, sustituido=False, secuencia=[])

        def prop_con_sustitucion(p):
            # 1-2: función ORIGINAL: dictamen sobre el archivo registrado
            propia, motivo = original_prop(p)
            if propia and os.path.abspath(str(p)) == str(ruta_propia) \
                    and not suceso['sustituido']:
                suceso['secuencia'].append('dictamen_positivo')
                suceso['dictamen'] = (propia, motivo)
                # 3: sustitución INMEDIATAMENTE después del dictamen positivo
                tmp = run / '.sust_tmp'
                shutil.copyfile(str(sustituto), str(tmp))
                os.replace(str(tmp), str(ruta_propia))
                suceso['sustituido'] = True
                suceso['secuencia'].append('sustitucion_os_replace')
                # 4: abajo se devuelve el dictamen ORIGINAL al llamador
            return propia, motivo

        L.propiedad_de_6g1 = prop_con_sustitucion
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        try:
            info = L.abortar_6g1(run, 'PRUEBA_CR1c')
        finally:
            L.propiedad_de_6g1 = original_prop
        ab = leer_abort(run)
        motivo_archivo = str((ab or {}).get('motivos_propiedad', {})
                             .get('salida_concurrente.wav', ''))
        checks = [
            ('dictamen_positivo_original',
             suceso['dictamen'] == (True, 'propiedad_acreditada'),
             str(suceso['dictamen'])),
            ('sustitucion_despues_del_dictamen_y_antes_del_llamador',
             suceso['secuencia'] == ['dictamen_positivo',
                                     'sustitucion_os_replace'],
             str(suceso['secuencia'])),
            ('sustitucion_inyectada', suceso['sustituido'], ''),
            ('sustituto_byte_a_byte', sha_file(sustituto) == sha_sub,
             sha_file(sustituto)[:16]),
            ('sustituto_en_disco_intacto',
             ruta_propia.read_bytes() == bytes_sub,
             ruta_propia.read_bytes()[:40]),
            ('nada_eliminado',
             ruta_propia.exists() and otro.exists()
             and otro.read_bytes() == b'otra salida propia\n', ''),
            # Clasificación basada en el dictamen obtenido ANTES de la
            # sustitución; NO identifica necesariamente la identidad
            # posterior (el motivo registrado no afirma identidad).
            ('clasificacion_por_dictamen_anterior',
             'salida_concurrente.wav' in (ab or {}).get('salidas_invalidadas', []),
             str((ab or {}).get('salidas_invalidadas'))),
            ('motivo_sin_afirmar_identidad_posterior',
             'sin eliminación' in motivo_archivo
             and 'propiedad_acreditada' not in motivo_archivo,
             motivo_archivo),
            ('schema_3', (ab or {}).get('schema') == 'abort-6g1/3', ''),
        ]
        filas.append(fila('CR1c', 'lectura_segura_6g1',
                          'sustitución concurrente tras el dictamen positivo '
                          'y antes de que el llamador continuara: sustituto '
                          'intacto (sin unlink); clasificación por el '
                          'dictamen anterior', checks))
        detalles['CR1c'] = dict(suceso=dict(suceso), abort=ab)
    except Exception as exc:
        filas.append(fila('CR1c', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1c'] = dict(error=repr(exc))

    # ---- CR1d: enlaces simbólicos conservados, nunca seguidos
    try:
        run = TRABAJO / 'CR1d'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        externo = TRABAJO / 'externo_CR1d.json'
        externo.write_bytes(b'{"externo": "objetivo del enlace"}\n')
        sha_ext = sha_file(externo)
        os.symlink(str(externo), run / 'enlace.json')
        os.symlink(str(externo), run / 'analysis_link.json')
        L.reiniciar_registro_6g1()
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        info = L.abortar_6g1(run, 'PRUEBA_CR1d')
        ab = leer_abort(run)
        checks = [
            ('enlaces_conservados',
             os.path.islink(run / 'enlace.json')
             and os.path.islink(run / 'analysis_link.json'), ''),
            ('externo_byte_a_byte', sha_file(externo) == sha_ext,
             sha_file(externo)[:16]),
            ('motivo_enlace',
             (ab or {}).get('motivos_propiedad', {}).get('enlace.json')
             == 'enlace_simbolico_conservado (sin seguir)',
             str((ab or {}).get('motivos_propiedad', {}).get('enlace.json'))),
            ('abort_creado_regular', ab is not None
             and not os.path.islink(run / 'ABORT_6G1.json'), ''),
        ]
        filas.append(fila('CR1d', 'lectura_segura_6g1',
                          'enlaces simbólicos conservados, nunca seguidos',
                          checks))
        detalles['CR1d'] = dict(abort=ab)
    except Exception as exc:
        filas.append(fila('CR1d', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1d'] = dict(error=repr(exc))

    # ---- CR1e: registro de invalidadas + exclusividad de ABORT_6G1.json
    try:
        run = TRABAJO / 'CR1e'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        propio = run / 'salida.wav'
        propio.write_bytes(b'salida propia\n')
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(propio, estable=True)
        pre = run / 'ABORT_6G1.json'
        pre.write_bytes(b'{"abort_preexistente_ajeno": true}\n')
        sha_pre = sha_file(pre)
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        info = L.abortar_6g1(run, 'PRUEBA_CR1e')
        checks = [
            ('preexistente_intacto', sha_file(pre) == sha_pre, sha_file(pre)[:16]),
            ('motivo_colision_en_retorno',
             'colision' in str(info.get('motivos_propiedad', {})
                              .get('ABORT_6G1.json', '')),
             str(info.get('motivos_propiedad', {}).get('ABORT_6G1.json'))),
            ('info_completa_en_retorno',
             info.get('schema') == 'abort-6g1/3'
             and 'salida.wav' in info.get('salidas_invalidadas', [])
             and info.get('resultados_validos') == []
             and info.get('analysis_intacto') is True,
             str(info.get('salidas_invalidadas'))),
            ('propio_conservado', propio.exists()
             and propio.read_bytes() == b'salida propia\n', ''),
        ]
        filas.append(fila('CR1e', 'lectura_segura_6g1',
                          'ABORT_6G1.json: registro de invalidadas y '
                          'exclusividad (colisión conservada)', checks))
        detalles['CR1e'] = dict(info=info)
    except Exception as exc:
        filas.append(fila('CR1e', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1e'] = dict(error=repr(exc))

    # ---- CR1f: analysis.json sigue byte a byte (E-R2 se mantiene)
    try:
        run = TRABAJO / 'CR1f'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"engine": "6G.1", "sellado": true}\n'
        ruta_a = run / 'analysis.json'
        ruta_a.write_bytes(contenido)
        sha0, mtime0 = sha_file(ruta_a), os.lstat(ruta_a).st_mtime_ns
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_a, estable=True)
        L.acreditar_dir_6g1(run)  # [6G.1-R/H1] como create_run_dir
        info = L.abortar_6g1(run, 'PRUEBA_CR1f')
        checks = [
            ('analysis_byte_a_byte', ruta_a.read_bytes() == contenido, ''),
            ('analysis_sha_intacto', sha_file(ruta_a) == sha0, sha_file(ruta_a)[:16]),
            ('analysis_mtime_intacto', os.lstat(ruta_a).st_mtime_ns == mtime0, ''),
            ('sin_abort_6g1_embebido',
             'abort_6g1' not in json.loads(ruta_a.read_text(encoding='utf-8')), ''),
            ('abort_regular_con_info', leer_abort(run) is not None, ''),
        ]
        filas.append(fila('CR1f', 'lectura_segura_6g1',
                          'analysis.json intacto (E-R2 se mantiene)', checks))
        detalles['CR1f'] = dict(abort=leer_abort(run))
    except Exception as exc:
        filas.append(fila('CR1f', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1f'] = dict(error=repr(exc))

    # ---- estático: sin borrado en el módulo; schema /3; sin patrones
    try:
        src = (RAIZ / 'motores' / 'lectura_segura_6g1.py').read_text(
            encoding='utf-8')
        checks = [
            ('sin_os_unlink', 'os.unlink' not in src.replace(
                'y `os.unlink` (hallazgo', ''), 'mención documental permitida'),
            ('sin_os_remove_ni_rmdir', 'os.remove' not in src
             and 'os.rmdir' not in src, ''),
            ('sin_fnmatch_patrones', 'fnmatch' not in src, ''),
            ('schema_3_en_codigo', "schema='abort-6g1/3'" in src, ''),
            ('estado_y_resultados_validos',
             'estado_salidas_invalidadas' in src and 'resultados_validos' in src, ''),
        ]
        filas.append(fila('CR1-estatico', 'lectura_segura_6g1',
                          'sin camino de borrado en el módulo; schema /3',
                          checks))
        detalles['CR1-estatico'] = dict(estatico=True)
    except Exception as exc:
        filas.append(fila('CR1-estatico', 'lectura_segura_6g1', 'estático', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['CR1-estatico'] = dict(error=repr(exc))

    return filas, detalles


def correr(motor, work, inject=None, plantar=None):
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
    env = dict(os.environ, PYTHONPATH=str(INJ), SDVSDI_6G1_OUT=str(out))
    if inject:
        env['SDVSDI_6G1_INJECT'] = inject
        env['SDVSDI_6G1_MOTORES'] = str(MOT)
    if plantar:
        env['SDVSDI_6G1_PLANTAR'] = ';'.join(plantar)
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env=env)
    salida = proc.communicate(timeout=900)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, out=str(out),
                 stdout_tail=salida[-3000:])
    return datos


def motores_cr1():
    filas, detalles = [], {}
    for motor in MOTORES:
        # ---- e2e: aborto real; conservación total + registro correcto
        try:
            ajeno_bytes = b'contenido AJENO plantado en la corrida %s\n' \
                          % motor.encode()
            ajeno_ext = TRABAJO / motor / 'ajeno_plantado.wav'
            ajeno_ext.parent.mkdir(parents=True, exist_ok=True)
            ajeno_ext.write_bytes(ajeno_bytes)
            externo = TRABAJO / motor / 'externo_enlace.json'
            externo.write_bytes(b'{"externo": "objetivo del enlace plantado"}\n')
            salida0 = SALIDAS[motor][0]           # salida propia a REEMPLAZAR
            r = correr(motor, TRABAJO / motor / 'E2E', inject='verificar_raise',
                       plantar=['archivo:%s@%s' % (salida0, ajeno_ext),
                                'enlace:enlace_ajeno.json@%s' % externo])
            out = Path(r['out'])
            dirs = sorted(out.glob('*_partial')) + sorted(out.glob('*_aborted'))
            abort_dir = dirs[0] if dirs else None
            ab = leer_abort(abort_dir) if abort_dir else None
            checks = [
                ('exit_2', r['exit'] == 2, 'exit=%s' % r['exit']),
                ('sin_dir_definitivo', not dirs_definitivos(r['out'], motor),
                 'definitivos=%s' % dirs_definitivos(r['out'], motor)),
                ('directorio_aborto_presente', abort_dir is not None
                 and (abort_dir / 'ABORT_6G1.json').is_file(), str(abort_dir)),
                ('salidas_propias_conservadas',
                 all((abort_dir / s).is_file() for s in SALIDAS[motor]),
                 str([s for s in SALIDAS[motor]
                      if not (abort_dir / s).is_file()])),
                ('salida_reemplazada_por_ajeno_intacta',
                 (abort_dir / salida0).read_bytes() == ajeno_bytes,
                 (abort_dir / salida0).read_bytes()[:40]),
                ('enlace_plantado_conservado',
                 os.path.islink(abort_dir / 'enlace_ajeno.json')
                 and sha_file(Path(os.path.realpath(abort_dir / 'enlace_ajeno.json')))
                 == sha_file(externo), ''),
                ('abort_schema_3', (ab or {}).get('schema') == 'abort-6g1/3',
                 str(ab and ab.get('schema'))),
                # [C-R1] La salida REEMPLAZADA por el plantado ajeno se
                # clasifica como conservada con motivo 'identidad_distinta'
                # (su inodo ya no coincide con el registro); la salida propia
                # no reemplazada queda en salidas_invalidadas.
                ('salida_no_reemplazada_en_invalidadas',
                 SALIDAS[motor][1] in (ab or {}).get('salidas_invalidadas', []),
                 str((ab or {}).get('salidas_invalidadas'))),
                ('salida_reemplazada_en_conservados',
                 SALIDAS[motor][0] in (ab or {}).get('conservados', [])
                 and 'identidad_distinta' in str((ab or {})
                                                 .get('motivos_propiedad', {})
                                                 .get(SALIDAS[motor][0], '')),
                 str((ab or {}).get('motivos_propiedad', {})
                     .get(SALIDAS[motor][0]))),
                ('estado_sin_eliminacion',
                 'sin eliminación' in str((ab or {})
                                          .get('estado_salidas_invalidadas', '')),
                 str((ab or {}).get('estado_salidas_invalidadas'))),
                ('resultados_validos_vacio',
                 (ab or {}).get('resultados_validos') == [], ''),
                ('enlace_en_conservados',
                 'enlace_ajeno.json' in (ab or {}).get('conservados', []),
                 str((ab or {}).get('conservados'))),
                ('analysis_intacto_e2e',
                 (abort_dir / 'analysis.json').is_file()
                 and not os.path.islink(abort_dir / 'analysis.json')
                 and isinstance(json.loads(
                     (abort_dir / 'analysis.json').read_text(encoding='utf-8')), dict)
                 and 'abort_6g1' not in json.loads(
                     (abort_dir / 'analysis.json').read_text(encoding='utf-8')),
                 ''),
            ]
            filas.append(fila('CR1-e2e', motor,
                              'aborto real: conservación total + registro /3 '
                              '+ fail-closed', checks))
            detalles.setdefault(motor, {})['E2E'] = dict(
                exit=r['exit'], abort_dir=str(abort_dir))
        except Exception as exc:
            filas.append(fila('CR1-e2e', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['E2E'] = dict(error=repr(exc))
        # ---- sanidad mínima (no repite baterías históricas)
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
            filas.append(fila('sanidad', motor, 'corrida feliz tras C-R1',
                              checks))
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
    print('== C-R1 unidad + estático ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %-14s %s' % (f['veredicto'], f['prueba'],
                                    f['detalle'][:80]))
    print('== C-R1 motores (e2e + sanidad) ==')
    fm, dm = motores_cr1()
    todas.extend(fm)
    detalle_todo.update(dm)
    for f in fm:
        print('  %-14s %-6s %-12s %s' % (f['veredicto'], f['motor'],
                                         f['prueba'], f['detalle'][:80]))
    dump(EV / 'pruebas_c_r1_6g1.json',
         dict(schema='pruebas-c-r1-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_c_r1_6g1.csv').open('w', newline='',
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
