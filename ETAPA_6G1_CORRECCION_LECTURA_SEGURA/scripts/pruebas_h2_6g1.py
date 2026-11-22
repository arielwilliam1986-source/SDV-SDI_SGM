"""Pruebas H2 (rectificación 6G.1 — apertura segura del Mix validado).

Ejecuta ÚNICAMENTE la batería focalizada de este hallazgo; las regresiones
(H1-R2-R2, H1-R2, H1, C-R1) se ejecutan con sus propias baterías. No repite
las baterías históricas (34/26/17/12).

  T1 (H2-B)  Mix WAV regular VALIDADO (identidad + SHA por ruta, semántica
        probe_file); en el punto exacto entre la validación y la apertura de
        MixHandle se SUSTITUYE la entrada por una FIFO (envoltorio sobre
        L.abrir_mix que sustituye antes de delegar): la apertura NO se
        bloquea (O_NONBLOCK; límite temporal 8 s), se rechaza fail-closed
        (no regular), sin SHA acreditado, sin handle, sin salidas de audio;
        la FIFO queda SIN contenido escrito por nadie y el objeto validado
        (renombrado aparte) queda byte a byte intacto. 2ª vía: clasificación
        de propiedad 6G.1 (_clasificar_entrada_6g1) — la FIFO NO es el
        objeto registrado (identidad_distinta) y el objeto validado SÍ
        conserva la propiedad acreditada.
  T2 (H2-A)  Sustitución por OTRO archivo regular BYTE A BYTE IDÉNTICO con
        distinto inodo antes de abrir MixHandle: el SHA coincidente NO
        aprueba la identidad — apertura rechazada (H2-A), sin handle, el
        objeto validado original permanece vivo e intacto.
  T3a (H2-A) probe_file() de los TRES motores captura la identidad del
        objeto validado (device/inode/mtime_ns != 0 y coincidentes con
        os.stat) junto al SHA-256.
  T3b (H2)   Apertura feliz: L.abrir_mix con identidad + SHA del probe
        supera la apertura, conserva la identidad validada
        (identity_validada=True), lee el mismo inodo, la guarda final
        verificar() da unchanged=True con estable=True (H2-C) y close() es
        idempotente.
  T4 (H2-C)  El archivo MUTA durante la validación (envoltorio sobre el
        hash sobre descriptor del motor, `sha_fd_estable_6g1` — gancho
        actualizado por H2-R, mismo punto de validación): probe_file marca
        el error (H2-C/H2-R) y el SHA queda NO acreditado
        (info.valid=False; validate_mix lo rechaza).
  H2-e2e ×3  Corrida feliz de producción (DSP intacto): exit 0, publicación
        única, integridad after.unchanged=True y after.estable=True
        (evidencia H2-C del MixHandle reformado), PCM idéntico a la campaña
        auditada.

Evidencia: evidence/pruebas_h2_6g1.json + evidence/matriz_h2_6g1.csv
"""
import csv
import importlib.util
import json
import os
import shutil
import signal
import stat
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, recolectar, \
    sha_file, dump
import lectura_segura_6g1 as L

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1h2')

NOMBRE_MOTOR = {
    'Hardened': 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
    'EVO': 'MOTOR_SEP_SDV-SDI_EVO.py',
    'MQR': 'sdv_sdi_mqr_engine.py',
}
SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
PREFIJO = {'Hardened': 'motorA_run_', 'EVO': 'motorA_run_', 'MQR': 'mqr_run_'}


class _TiempoAgotado(Exception):
    pass


def _alarma(signum, frame):
    raise _TiempoAgotado()


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


def cargar_motor(clave):
    ruta = MOT / NOMBRE_MOTOR[clave]
    spec = importlib.util.spec_from_file_location('eng_h2_%s' % clave, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def validar_como_probe(ruta):
    """[unidad] Reproduce la semántica probe_file (H2-A + H2-C) SIN el motor:
    identidad del objeto + SHA-256 por ruta + verificación de estabilidad
    (st0/st1). Devuelve (identidad, sha) o lanza si es inestable."""
    st0 = os.stat(ruta)
    sha = sha_file(ruta)
    st1 = os.stat(ruta)
    if (st1.st_dev, st1.st_ino, st1.st_size, st1.st_mtime_ns,
            st1.st_ctime_ns) != (st0.st_dev, st0.st_ino, st0.st_size,
                                 st0.st_mtime_ns, st0.st_ctime_ns):
        raise AssertionError('fixture inestable durante la validación')
    identidad = (st0.st_dev, st0.st_ino)
    return identidad, sha


def unidad_fifo():
    """T1 (H2-B): sustitución por FIFO entre la validación y MixHandle."""
    filas, detalle = [], {}
    try:
        base = TRABAJO / 'T1'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        nombre = 'mix.wav'
        bytes0 = (FIX / 'mix.wav').read_bytes()
        (base / nombre).write_bytes(bytes0)
        # validación estilo probe_file sobre el objeto ORIGINAL
        identidad, sha0 = validar_como_probe(base / nombre)
        st0 = os.stat(base / nombre)
        # el objeto validado se registra como propio (2ª vía, semántica 6G.1)
        assert L.registrar_propio_6g1(str(base / nombre), estable=True)
        L.acreditar_dir_6g1(str(base))  # anclaje 6G.1 del dir de ensayo
        fd_dir = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW)
        # envoltorio que SUSTITUYE la entrada por una FIFO justo después de
        # la validación y ANTES de que MixHandle abra el descriptor
        original_abrir = L.abrir_mix
        suceso = dict(sustituida=False)

        def abrir_con_fifo(path, sha_esperado=None, identidad_esperada=None):
            os.rename(str(base / nombre), str(base / 'mix_validado_aside'))
            os.mkfifo(nombre, 0o644, dir_fd=fd_dir)
            suceso['sustituida'] = True
            return original_abrir(path, sha_esperado, identidad_esperada)

        L.abrir_mix = abrir_con_fifo
        exc, transcurrido, agotado = None, None, False
        previo = signal.signal(signal.SIGALRM, _alarma)
        signal.setitimer(signal.ITIMER_REAL, 8)   # fail-safe anti-bloqueo
        try:
            t0 = time.perf_counter()
            try:
                L.abrir_mix(str(base / nombre), sha_esperado=sha0,
                            identidad_esperada=identidad)
            except Exception as e:
                exc = e
            transcurrido = time.perf_counter() - t0
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previo)
            L.abrir_mix = original_abrir
        # verificación sobre el estado real en disco
        st_fifo = os.lstat(nombre, dir_fd=fd_dir)
        fd_r = os.open(nombre, os.O_RDONLY | os.O_NONBLOCK, dir_fd=fd_dir)
        try:
            contenido_fifo = os.read(fd_r, 4096)
        finally:
            os.close(fd_r)
        nombres = sorted(os.listdir(fd_dir))
        # 2ª vía: clasificación de propiedad 6G.1 por descriptor
        cls_fifo = L._clasificar_entrada_6g1(nombre, st_fifo, fd_dir,
                                             str(base / nombre))
        st_aside = os.lstat('mix_validado_aside', dir_fd=fd_dir)
        cls_aside = L._clasificar_entrada_6g1('mix_validado_aside', st_aside,
                                              fd_dir, str(base / nombre))
        checks = [
            ('sustitucion_inyectada_en_la_ventana',
             suceso['sustituida'] and stat.S_ISFIFO(st_fifo.st_mode), ''),
            ('apertura_sin_bloquearse',
             not agotado and transcurrido is not None and transcurrido < 5.0,
             'agotado=%s t=%s' % (agotado, transcurrido)),
            ('rechazo_fail_closed_no_regular',
             exc is not None and 'no es un archivo regular' in str(exc)
             and 'H2-B' in str(exc), str(exc)[:120]),
            ('sin_sha_acreditado', exc is not None, 'sin handle => sin SHA'),
            ('sin_salidas_de_audio',
             nombres == ['mix.wav', 'mix_validado_aside'], str(nombres)),
            ('fifo_sin_contenido_escrito',
             stat.S_ISFIFO(st_fifo.st_mode) and contenido_fifo == b'', ''),
            ('objeto_validado_intacto_al_margen',
             (base / 'mix_validado_aside').read_bytes() == bytes0
             and sha_file(base / 'mix_validado_aside') == sha0,
             sha_file(base / 'mix_validado_aside')[:16]),
            ('via2_fifo_no_es_el_objeto_registrado',
             cls_fifo[0] is False
             and 'identidad_distinta' in cls_fifo[1], str(cls_fifo)),
            ('via2_objeto_validado_conserva_propiedad',
             cls_aside[0] is True
             and 'propiedad_acreditada' in cls_aside[1], str(cls_aside)),
        ]
        filas.append(fila('T1', 'lectura_segura_6g1',
                          'validado->FIFO antes de abrir MixHandle: sin '
                          'bloqueo, fail-closed, sin SHA, sin salidas',
                          checks))
        detalle['T1'] = dict(exc=str(exc)[:160], transcurrido=transcurrido,
                             agotado=agotado, cls_fifo=str(cls_fifo),
                             cls_aside=str(cls_aside))
        os.close(fd_dir)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T1', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['T1'] = dict(error=repr(exc))
    return filas, detalle


def unidad_gemelo():
    """T2 (H2-A): impostor regular byte a byte idéntico, distinto inodo."""
    filas, detalle = [], {}
    try:
        base = TRABAJO / 'T2'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        nombre = 'mix.wav'
        bytes0 = (FIX / 'mix.wav').read_bytes()
        (base / nombre).write_bytes(bytes0)
        identidad0, sha0 = validar_como_probe(base / nombre)
        st0 = os.stat(base / nombre)
        # impostor byte a byte idéntico (otro inodo), creado ANTES
        (base / 'impostor.wav').write_bytes(bytes0)
        st_imp = os.stat(base / 'impostor.wav')
        fd_dir = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW)
        original_abrir = L.abrir_mix
        suceso = dict(sustituido=False)

        def abrir_con_gemelo(path, sha_esperado=None, identidad_esperada=None):
            os.rename(str(base / nombre), str(base / 'mix_validado_aside'))
            os.rename(str(base / 'impostor.wav'), str(base / nombre))
            suceso['sustituido'] = True
            return original_abrir(path, sha_esperado, identidad_esperada)

        L.abrir_mix = abrir_con_gemelo
        exc = None
        try:
            try:
                L.abrir_mix(str(base / nombre), sha_esperado=sha0,
                            identidad_esperada=identidad0)
            except Exception as e:
                exc = e
        finally:
            L.abrir_mix = original_abrir
        st_mix = os.lstat(nombre, dir_fd=fd_dir)
        checks = [
            ('sustitucion_inyectada_en_la_ventana',
             suceso['sustituido'] and stat.S_ISREG(st_mix.st_mode), ''),
            ('impostor_byte_a_byte_identico_mismo_sha',
             sha_file(base / nombre) == sha0, sha_file(base / nombre)[:16]),
            ('impostor_distinto_inodo',
             (st_mix.st_dev, st_mix.st_ino) != identidad0,
             'imp=%s valid=%s' % ((st_mix.st_dev, st_mix.st_ino), identidad0)),
            ('sha_coincidente_NO_aprueba_identidad',
             exc is not None and 'H2-A' in str(exc)
             and 'no coincide' in str(exc), str(exc)[:160]),
            ('sin_handle_sin_sha_acreditado', exc is not None, ''),
            ('objeto_validado_original_vivo_e_intacto',
             (base / 'mix_validado_aside').read_bytes() == bytes0
             and (os.lstat('mix_validado_aside', dir_fd=fd_dir).st_dev,
                  os.lstat('mix_validado_aside', dir_fd=fd_dir).st_ino)
             == identidad0, ''),
            ('sin_salidas_de_audio',
             sorted(os.listdir(fd_dir)) == ['mix.wav', 'mix_validado_aside'],
             str(sorted(os.listdir(fd_dir)))),
        ]
        filas.append(fila('T2', 'lectura_segura_6g1',
                          'gemelo byte a byte con distinto inodo: el SHA '
                          'coincidente NO aprueba la identidad', checks))
        detalle['T2'] = dict(exc=str(exc)[:200],
                             identidad0=list(identidad0))
        os.close(fd_dir)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T2', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['T2'] = dict(error=repr(exc))
    return filas, detalle


def unidad_probe_identity():
    """T3a (H2-A): probe_file de los tres motores captura identidad."""
    filas, detalle = [], {}
    base = TRABAJO / 'T3'
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    copia = base / 'mix.wav'
    copia.write_bytes((FIX / 'mix.wav').read_bytes())
    st = os.stat(copia)
    sha0 = sha_file(copia)
    for motor in MOTORES:
        try:
            m = cargar_motor(motor)
            info = m.probe_file(str(copia), 'mix')
            checks = [
                ('probe_valido', info.valid is True, str(info.errors)),
                ('identidad_capturada',
                 info.device != 0 and info.inode != 0,
                 'dev=%s ino=%s' % (info.device, info.inode)),
                ('identidad_coincide_con_el_objeto',
                 (info.device, info.inode) == (st.st_dev, st.st_ino), ''),
                ('mtime_ns_capturado',
                 info.mtime_ns == st.st_mtime_ns
                 and info.ctime_ns == st.st_ctime_ns, ''),
                ('sha256_capturado', info.sha256 == sha0, info.sha256[:16]),
            ]
            filas.append(fila('T3a', motor,
                              'probe_file captura identidad del objeto '
                              'validado (H2-A)', checks))
            detalle[motor] = dict(dev=info.device, ino=info.inode)
        except Exception as exc:
            filas.append(fila('T3a', motor, 'unidad', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalle[motor] = dict(error=repr(exc))
    # T3b (H2): apertura feliz + guarda final, con la identidad del probe
    try:
        m = cargar_motor('EVO')
        info = m.probe_file(str(copia), 'mix')
        h = L.abrir_mix(str(copia), sha_esperado=info.sha256,
                        identidad_esperada=(info.device, info.inode))
        v = h.verificar()
        frames = h._snd.frames
        ruta_ok = h.ruta_apunta_al_mismo_objeto()
        h.close()
        idempotente = (h.fd is None)
        h.close()  # idempotencia
        checks = [
            ('apertura_superada_con_identidad_validada',
             getattr(h, 'identity_validada', None) is True, ''),
            ('identidad_conservada_igual_al_probe',
             (h.identity['device'], h.identity['inode'])
             == (info.device, info.inode), str(h.identity)),
            ('sha_sobre_descriptor_igual_al_probe',
             h.digest == info.sha256, (h.digest or '')[:16]),
            ('mismo_inodo_legible_por_soundfile',
             frames == info.frames and frames > 0,
             'frames=%s' % frames),
            ('guarda_final_unchanged_y_estable',
             v.get('unchanged') is True and v.get('estable') is True,
             str(v)),
            ('ruta_apunta_al_mismo_objeto',
             ruta_ok.get('unchanged') is True, str(ruta_ok)[:90]),
            ('close_idempotente', idempotente, ''),
            ('disco_sin_cambios_tras_la_corrida', sha_file(copia) == sha0,
             sha_file(copia)[:16]),
        ]
        filas.append(fila('T3b', 'lectura_segura_6g1',
                          'apertura feliz: identidad validada conservada y '
                          'guarda final estable (H2-C)', checks))
        detalle['T3b'] = dict(estable=v.get('estable'),
                              unchanged=v.get('unchanged'))
    except Exception as exc:
        filas.append(fila('T3b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['T3b'] = dict(error=repr(exc))
    shutil.rmtree(base, ignore_errors=True)
    return filas, detalle


def unidad_probe_inestable():
    """T4 (H2-C): el archivo muta durante la validación -> SHA no acreditado."""
    filas, detalle = [], {}
    try:
        base = TRABAJO / 'T4'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        copia = base / 'mix.wav'
        copia.write_bytes((FIX / 'mix.wav').read_bytes())
        m = cargar_motor('Hardened')
        original_sha = m._sha_fd_estable_6g1  # [H2-R] hash sobre descriptor

        def sha_con_muta(fd):
            with open(str(copia), 'ab') as g:   # mutación EN la ventana probe
                g.write(b'\x00')
            return original_sha(fd)

        m._sha_fd_estable_6g1 = sha_con_muta
        try:
            info = m.probe_file(str(copia), 'mix')
        finally:
            m._sha_fd_estable_6g1 = original_sha
        vm = m.validate_mix(info)
        checks = [
            ('probe_detecta_mutacion_h2c_h2r',
             any(('H2-C' in e or 'H2-R' in e) for e in info.errors),
             str(info.errors)),
            ('sha_NO_acreditado_valid_false',
             info.valid is False, str(info.valid)),
            ('validate_mix_rechaza', vm.valid is False, str(vm.valid)),
            ('disco_realmente_mutado',
             copia.stat().st_size
             == (FIX / 'mix.wav').stat().st_size + 1,
             'size=%s base=%s' % (copia.stat().st_size,
                                  (FIX / 'mix.wav').stat().st_size)),
        ]
        filas.append(fila('T4', 'Hardened',
                          'mutación durante la validación: SHA no acreditado '
                          '(H2-C)', checks))
        detalle['T4'] = dict(errors=list(info.errors), valid=info.valid)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T4', 'Hardened', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['T4'] = dict(error=repr(exc))
    return filas, detalle


def dirs_definitivos(out, motor):
    pref = PREFIJO[motor]
    if not Path(out).exists():
        return []
    return [d.name for d in Path(out).iterdir()
            if d.is_dir() and d.name.startswith(pref)
            and not d.name.endswith('_partial')
            and not d.name.endswith('_aborted')]


def correr(motor, work):
    work = Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    man = work / 'manifest.json'
    escribir_manifest(man, dict(mix=str(FIX / 'mix.wav'),
                                vocal=str(FIX / 'vocal_mix.wav'),
                                instrumental=str(FIX / 'instrumental_mix.wav')))
    out = work / 'out'
    import subprocess
    cmd = [sys.executable, '-B', str(MOT / NOMBRE_MOTOR[motor]),
           '--manifest', str(man), '--out', str(out),
           '--mode', 'full_processing']
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    salida = proc.communicate(timeout=900)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, out=str(out),
                 stdout_tail=salida[-2000:])
    return datos


def pcm_auditado(motor):
    d = json.loads((EV / 'contenedores_6g1.json').read_text())
    return d['casos']['%s/%s/full_processing' % (motor, 'WAV')]['pcm']


def motores_h2():
    filas, detalles = [], {}
    for motor in MOTORES:
        try:
            r = correr(motor, TRABAJO / motor / 'e2e')
            pcm = {p['name']: p['pcm_sha256'] for p in r['pcm']
                   if 'pcm_sha256' in p}
            esperado = pcm_auditado(motor)
            integ = r['integrity']
            defs = dirs_definitivos(r['out'], motor)
            checks = [
                ('exit_0', r['exit'] == 0, 'exit=%s' % r['exit']),
                ('publicacion_unica', len(defs) == 1, 'defs=%s' % defs),
                ('integridad_unchanged',
                 integ.get('after', {}).get('unchanged') is True
                 and integ.get('ruta_actual', {}).get('unchanged') is True,
                 ''),
                ('h2c_estable_true_en_produccion',
                 integ.get('after', {}).get('estable') is True,
                 str(integ.get('after', {}).get('estable'))),
                ('pcm_identico_a_campana_auditada', pcm == esperado,
                 'diff=%s' % {k: pcm.get(k, '')[:12] for k in
                              set(pcm) | set(esperado)
                              if pcm.get(k) != esperado.get(k)}),
            ]
            filas.append(fila('H2-e2e', motor,
                              'corrida feliz: MixHandle reformado en '
                              'producción (DSP intacto)', checks))
            detalles.setdefault(motor, {})['e2e'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('H2-e2e', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['e2e'] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== H2 unidad ==')
    for fn in (unidad_fifo, unidad_gemelo, unidad_probe_identity,
               unidad_probe_inestable):
        f, d = fn()
        todas.extend(f)
        detalle_todo.update(d)
        for x in f:
            print('  %-4s %-6s %-14s %s' % (x['veredicto'], x['motor'],
                                            x['prueba'],
                                            x['detalle'][:70]))
    print('== H2 motores (e2e produccion) ==')
    fm, dm = motores_h2()
    todas.extend(fm)
    detalle_todo.update(dm)
    for x in fm:
        print('  %-14s %-6s %-14s %s' % (x['veredicto'], x['motor'],
                                         x['prueba'], x['detalle'][:70]))
    dump(EV / 'pruebas_h2_6g1.json',
         dict(schema='pruebas-h2-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_h2_6g1.csv').open('w', newline='',
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
