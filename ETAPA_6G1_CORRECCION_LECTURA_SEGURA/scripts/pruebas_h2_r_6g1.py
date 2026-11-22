"""Pruebas H2-R (rectificación 6G.1 — validación inicial anclada al mismo objeto).

Ejecuta ÚNICAMENTE la batería focalizada de este hallazgo; las regresiones
(H2, H1-R2-R2, H1-R2, H1, C-R1) se ejecutan con sus propias baterías. No
repite las baterías históricas (34/26/17/12).

NOTA DE DETERMINISMO: cualquier sustitución real de la ruta por rename/unlink
ACTUALIZA st_ctime del objeto movido (Linux), y H2-R-B lo detecta al final.
T1 fuerza esa rama (rechazo fail-closed) de forma determinista (sleep previo
que garantiza el delta de ctime); T2 inyecta la sustitución SIN tocar el
objeto original (la ruta es un ENLACE SIMBÓLICO que se re-dirige atómicamente
con rename), de modo que la rama "el SHA corresponde al objeto anclado" es
la determinista. Entre ambas cubren las dos ramas del "o" de la instrucción.

  T1 (H2-R-A)  Mix WAV regular válido; una sustitución TEMPORAL de la ruta
        por OTRO WAV válido con metadatos DISTINGUIBLES (48 kHz / mono /
        44100 frames, sintético) se inyecta en el punto exacto de la
        obtención de metadatos (envoltorio de `sf.info` del motor que
        sustituye antes de delegar y RESTAURA antes de devolver). El probe
        debe RECHAZAR fail-closed (el rename de la sustitución actualiza
        st_ctime del objeto movido y H2-R-B lo detecta) y NUNCA mezclar
        metadatos del sustituto con identidad del original: los campos
        presentes provienen del objeto ANCLADO (identidad y metadatos del
        original), el SHA queda NO acreditado y la ruta se restaura byte a
        byte en disco.
  T2 (H2-R-A)  Sustitución temporal de la ruta (enlace re-dirigido) por otro
        archivo de contenido distinto en el punto exacto del cálculo del SHA
        (envoltorio de `_sha_fd_estable_6g1` del motor): el SHA acreditado
        debe ser el del OBJETO ANCLADO — el probe completa válido con
        identidad, metadatos y SHA del original — y se demuestra que el SHA
        del sustituto NO se acredita (sha_sub != sha_probe == sha_original).
  T3   Regresión estable: un Mix WAV estable supera probe_file() en los
        TRES motores con identidad, metadatos y SHA correspondientes al
        MISMO objeto (cotejo contra os.stat, sf.info y SHA-256 reales del
        disco) y validate_mix lo acepta.
  T4   Regresión FIFO: una FIFO presente al COMENZAR el probe se rechaza
        SIN bloqueo (O_NONBLOCK, vigía temporal 8 s), sin SHA acreditado
        y sin crear ninguna salida (fail-closed).
  H2-R-e2e ×3  Corrida feliz de producción (DSP intacto): exit 0,
        publicación única, integridad after.unchanged=True y
        after.estable=True, PCM idéntico a la campaña auditada.

Evidencia: evidence/pruebas_h2_r_6g1.json + evidence/matriz_h2_r_6g1.csv
"""
import csv
import importlib.util
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, recolectar, \
    sha_file, dump

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1h2r')

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
    spec = importlib.util.spec_from_file_location('eng_h2r_%s' % clave, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def crear_wav_sustituto(ruta):
    """WAV válido con metadatos DISTINGUIBLES del fixture (48 kHz, mono,
    44100 frames) y contenido distinto (sintético, sin material real)."""
    datos = 0.1 * np.sin(2.0 * np.pi * 440.0
                         * np.arange(44100, dtype=np.float32) / 48000.0)
    sf.write(str(ruta), datos, 48000, subtype='PCM_16')


def preparar_base(nombre, sub_nombre='sustituto.wav'):
    base = TRABAJO / nombre
    shutil.rmtree(base, ignore_errors=True)
    base.mkdir(parents=True)
    copia = base / 'mix.wav'
    bytes0 = (FIX / 'mix.wav').read_bytes()
    copia.write_bytes(bytes0)
    st0 = os.stat(copia)
    sha0 = sha_file(copia)
    sub = base / sub_nombre
    crear_wav_sustituto(sub)
    time.sleep(0.05)  # garantiza que un rename posterior actualice st_ctime
    return base, copia, bytes0, st0, sha0, sub


def unidad_t1():
    """T1: sustitución temporal de la ruta durante la obtención de metadatos.

    Mecánica determinista: el rename de la sustitución actualiza st_ctime
    del objeto movido (Linux) y H2-R-B lo detecta al final -> el probe
    RECHAZA fail-closed. Lo demostrable: los campos presentes (identidad,
    metadatos) provienen del objeto ANCLADO (nunca del sustituto), el SHA
    queda NO acreditado y la ruta se restaura byte a byte."""
    filas, detalle = [], {}
    try:
        base, copia, bytes0, st0, sha0, sub = preparar_base('T1')
        sfi_sub = sf.info(str(sub))
        sha_sub = sha_file(sub)
        ruta_mix, ruta_aside, ruta_sub = str(copia), str(base / 'mix_aside.wav'), str(sub)
        for motor in MOTORES:
            try:
                m = cargar_motor(motor)
                suceso = dict(sustituido=False, restaurado=False)

                def info_con_sustitucion(ruta_, _o=sf.info, _s=suceso,
                                         _m=ruta_mix, _a=ruta_aside,
                                         _sub=ruta_sub):
                    os.rename(_m, _a)
                    shutil.copyfile(_sub, _m)
                    _s['sustituido'] = True
                    try:
                        return _o(ruta_)
                    finally:
                        os.unlink(_m)
                        os.rename(_a, _m)
                        _s['restaurado'] = True

                m.sf.info = info_con_sustitucion  # m.sf ES el módulo soundfile
                try:
                    info = m.probe_file(ruta_mix, 'mix')
                finally:
                    sf.info = info_con_sustitucion.__defaults__[0]
                checks = [
                    ('sustitucion_inyectada_en_la_ventana_de_metadatos',
                     suceso['sustituido'] and suceso['restaurado'],
                     str(suceso)),
                    ('probe_rechaza_fail_closed_h2r',
                     info.valid is False
                     and any('H2-R' in e and 'cambió' in e
                             for e in info.errors), str(info.errors)),
                    ('sin_sha_acreditado', info.sha256 == '',
                     repr(info.sha256)),
                    ('metadatos_del_original_no_del_sustituto',
                     info.sample_rate == 44100 and info.channels == 2
                     and info.frames == 88200
                     and info.sample_rate != int(sfi_sub.samplerate)
                     and info.channels != int(sfi_sub.channels)
                     and info.frames != int(sfi_sub.frames),
                     'probe=%s/%s/%s sub=%s/%s/%s' % (
                         info.sample_rate, info.channels, info.frames,
                         sfi_sub.samplerate, sfi_sub.channels, sfi_sub.frames)),
                    ('identidad_del_original',
                     (info.device, info.inode) == (st0.st_dev, st0.st_ino),
                     '%s/%s' % (info.device, info.inode)),
                    ('ruta_restaurada_byte_a_byte_en_disco',
                     copia.read_bytes() == bytes0 and sha_file(copia) == sha0,
                     sha_file(copia)[:16]),
                    ('inodo_restaurado_en_la_ruta',
                     os.stat(copia).st_ino == st0.st_ino,
                     '%s' % os.stat(copia).st_ino),
                ]
                filas.append(fila('T1', motor,
                                  'sustitución temporal durante los metadatos: '
                                  'rechazo fail-closed, campos del objeto '
                                  'anclado, sustituto jamás leído', checks))
                detalle[motor] = dict(valid=info.valid,
                                      errors=str(info.errors)[:140])
            except Exception as exc:
                filas.append(fila('T1', motor, 'unidad', None,
                                  motivo_ne='entorno de ensayo: %r' % exc))
                detalle[motor] = dict(error=repr(exc))
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T1', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['entorno'] = dict(error=repr(exc))
    return filas, detalle


def unidad_t2():
    """T2: sustitución temporal de la ruta durante el cálculo del SHA.

    Mecánica determinista: la ruta 'mix.wav' es un ENLACE SIMBÓLICO al Mix
    regular 'mix_original.wav'; el envoltorio re-dirige el enlace al
    sustituto (rename atómico) durante el hash y lo restaura antes de
    devolver. El objeto original JAMÁS se toca -> el probe completa válido
    y el SHA acreditado es el del OBJETO ANCLADO; el sustituto (contenido
    distinto) jamás entra."""
    filas, detalle = [], {}
    try:
        base = TRABAJO / 'T2'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        real = base / 'mix_original.wav'
        bytes0 = (FIX / 'mix.wav').read_bytes()
        real.write_bytes(bytes0)
        st0 = os.stat(real)
        sha0 = sha_file(real)
        enlace = base / 'mix.wav'
        os.symlink('mix_original.wav', enlace)  # política: enlaces legítimos
        sub = base / 'sustituto.wav'
        crear_wav_sustituto(sub)
        sha_sub = sha_file(sub)
        ruta_mix = str(enlace)
        for motor in MOTORES:
            try:
                m = cargar_motor(motor)
                suceso = dict(sustituido=False, restaurado=False)

                def sha_con_sustitucion(fd, _o=m._sha_fd_estable_6g1,
                                        _s=suceso, _m=ruta_mix,
                                        _sub=str(sub), _rel='mix_original.wav'):
                    tmp = _m + '.tmp'
                    os.symlink(_sub, tmp)
                    os.rename(tmp, _m)   # la ruta pasa a apuntar al sustituto
                    _s['sustituido'] = True
                    try:
                        return _o(fd)
                    finally:
                        tmp2 = _m + '.tmp'
                        os.symlink(_rel, tmp2)
                        os.rename(tmp2, _m)   # ruta restaurada al original
                        _s['restaurado'] = True

                m._sha_fd_estable_6g1 = sha_con_sustitucion
                try:
                    info = m.probe_file(ruta_mix, 'mix')
                finally:
                    m._sha_fd_estable_6g1 = sha_con_sustitucion.__defaults__[0]
                checks = [
                    ('sustitucion_inyectada_en_la_ventana_del_sha',
                     suceso['sustituido'] and suceso['restaurado'],
                     str(suceso)),
                    ('probe_valido_con_objeto_anclado', info.valid is True,
                     str(info.errors)),
                    ('sha_acreditado_es_el_del_objeto_anclado',
                     info.sha256 == sha0, info.sha256[:16]),
                    ('sha_del_sustituto_NO_acreditado',
                     sha_sub != sha0 and info.sha256 != sha_sub,
                     'probe=%s sub=%s' % (info.sha256[:16], sha_sub[:16])),
                    ('identidad_del_original',
                     (info.device, info.inode) == (st0.st_dev, st0.st_ino),
                     '%s/%s' % (info.device, info.inode)),
                    ('metadatos_del_original_no_del_sustituto',
                     info.sample_rate == 44100 and info.channels == 2
                     and info.frames == 88200, ''),
                    ('ruta_restaurada_y_objeto_intacto',
                     real.read_bytes() == bytes0 and sha_file(real) == sha0
                     and os.path.islink(enlace)
                     and os.readlink(enlace) == 'mix_original.wav'
                     and sha_file(enlace) == sha0, ''),
                ]
                filas.append(fila('T2', motor,
                                  'sustitución temporal durante el SHA: el SHA '
                                  'acreditado es el del objeto anclado', checks))
                detalle[motor] = dict(valid=info.valid,
                                      sha=info.sha256[:16])
            except Exception as exc:
                filas.append(fila('T2', motor, 'unidad', None,
                                  motivo_ne='entorno de ensayo: %r' % exc))
                detalle[motor] = dict(error=repr(exc))
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T2', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['entorno'] = dict(error=repr(exc))
    return filas, detalle


def unidad_t3():
    """T3: regresión estable en los tres motores (mismo objeto)."""
    filas, detalle = [], {}
    try:
        base, copia, bytes0, st0, sha0, _sub = preparar_base('T3')
        sfi_ref = sf.info(str(copia))
        for motor in MOTORES:
            try:
                m = cargar_motor(motor)
                info = m.probe_file(str(copia), 'mix')
                vm = m.validate_mix(info)
                checks = [
                    ('probe_valido', info.valid is True, str(info.errors)),
                    ('identidad_coincide_con_el_objeto',
                     (info.device, info.inode) == (st0.st_dev, st0.st_ino),
                     '%s/%s' % (info.device, info.inode)),
                    ('mtime_ctime_del_objeto',
                     info.mtime_ns == st0.st_mtime_ns
                     and info.ctime_ns == st0.st_ctime_ns, ''),
                    ('size_del_objeto', info.size_bytes == st0.st_size,
                     '%s' % info.size_bytes),
                    ('metadatos_iguales_al_objeto',
                     info.sample_rate == int(sfi_ref.samplerate)
                     and info.channels == int(sfi_ref.channels)
                     and info.frames == int(sfi_ref.frames)
                     and info.subtype == str(sfi_ref.subtype)
                     and info.format == str(sfi_ref.format), ''),
                    ('sha_igual_al_disco', info.sha256 == sha_file(copia),
                     info.sha256[:16]),
                    ('validate_mix_acepta', vm.valid is True,
                     str(vm.errors)),
                    ('disco_sin_cambios',
                     copia.read_bytes() == bytes0 and os.stat(copia).st_ino
                     == st0.st_ino, ''),
                ]
                filas.append(fila('T3', motor,
                                  'Mix estable: identidad, metadatos y SHA del '
                                  'mismo objeto', checks))
                detalle[motor] = dict(valid=info.valid)
            except Exception as exc:
                filas.append(fila('T3', motor, 'unidad', None,
                                  motivo_ne='entorno de ensayo: %r' % exc))
                detalle[motor] = dict(error=repr(exc))
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T3', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['entorno'] = dict(error=repr(exc))
    return filas, detalle


def unidad_t4():
    """T4: FIFO al comenzar el probe -> rechazo sin bloqueo, sin SHA, sin salidas."""
    filas, detalle = [], {}
    try:
        base = TRABAJO / 'T4'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        tubo = base / 'mix.wav'
        os.mkfifo(tubo, 0o644)
        for motor in MOTORES:
            try:
                m = cargar_motor(motor)
                exc, agotado, transcurrido = None, False, None
                previo = signal.signal(signal.SIGALRM, _alarma)
                signal.setitimer(signal.ITIMER_REAL, 8)  # fail-safe anti-bloqueo
                try:
                    t0 = time.perf_counter()
                    try:
                        info = m.probe_file(str(tubo), 'mix')
                    except _TiempoAgotado:
                        agotado = True
                        info = None
                    transcurrido = time.perf_counter() - t0
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previo)
                st_tubo = os.lstat(tubo)
                fd_r = os.open(str(tubo), os.O_RDONLY | os.O_NONBLOCK)
                try:
                    contenido = os.read(fd_r, 4096)
                finally:
                    os.close(fd_r)
                nombres = sorted(os.listdir(base))
                checks = [
                    ('sin_bloqueo',
                     not agotado and transcurrido is not None
                     and transcurrido < 5.0,
                     'agotado=%s t=%s' % (agotado, transcurrido)),
                    ('rechazo_fail_closed_no_regular',
                     info is not None and info.valid is False
                     and any('H2-R' in e and 'no es un archivo regular' in e
                             for e in info.errors), str(info.errors)),
                    ('sin_sha_acreditado',
                     info is not None and info.sha256 == '',
                     repr(info.sha256) if info is not None else ''),
                    ('sin_salidas_creadas',
                     nombres == ['mix.wav'] and stat.S_ISFIFO(st_tubo.st_mode),
                     str(nombres)),
                    ('fifo_sin_contenido_escrito',
                     stat.S_ISFIFO(st_tubo.st_mode) and contenido == b'', ''),
                ]
                filas.append(fila('T4', motor,
                                  'FIFO al comenzar el probe: sin bloqueo, '
                                  'fail-closed, sin SHA, sin salidas', checks))
                detalle[motor] = dict(t=transcurrido,
                                      errors=str(info.errors)[:120]
                                      if info is not None else '')
            except Exception as exc:
                filas.append(fila('T4', motor, 'unidad', None,
                                  motivo_ne='entorno de ensayo: %r' % exc))
                detalle[motor] = dict(error=repr(exc))
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('T4', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalle['entorno'] = dict(error=repr(exc))
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


def motores_h2r():
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
            filas.append(fila('H2-R-e2e', motor,
                              'corrida feliz con probe anclado (DSP intacto)',
                              checks))
            detalles.setdefault(motor, {})['e2e'] = dict(exit=r['exit'])
        except Exception as exc:
            filas.append(fila('H2-R-e2e', motor, 'end-to-end', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['e2e'] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== H2-R unidad ==')
    for fn in (unidad_t1, unidad_t2, unidad_t3, unidad_t4):
        f, d = fn()
        todas.extend(f)
        detalle_todo.update(d)
        for x in f:
            print('  %-4s %-6s %-14s %s' % (x['veredicto'], x['motor'],
                                            x['prueba'],
                                            x['detalle'][:70]))
    print('== H2-R motores (e2e produccion) ==')
    fm, dm = motores_h2r()
    todas.extend(fm)
    detalle_todo.update(dm)
    for x in fm:
        print('  %-14s %-6s %-14s %s' % (x['veredicto'], x['motor'],
                                         x['prueba'], x['detalle'][:70]))
    dump(EV / 'pruebas_h2_r_6g1.json',
         dict(schema='pruebas-h2-r-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_h2_r_6g1.csv').open('w', newline='',
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
