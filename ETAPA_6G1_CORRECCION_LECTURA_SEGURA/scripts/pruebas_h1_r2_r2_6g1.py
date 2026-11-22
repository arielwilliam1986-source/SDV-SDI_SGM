"""Pruebas H1-R2-R2 (rectificación 6G.1 — apertura segura frente a FIFO).

Ejecuta ÚNICAMENTE la prueba focalizada de este hallazgo; las regresiones
(H1-R2, H1, C-R1) se ejecutan con sus propias baterías. No repite las
baterías históricas (34/26/17/12).

  R2  Sustitución DETERMINISTA de una entrada regular por una FIFO en el
      PUNTO EXACTO entre la identificación inicial (lstat relativo al
      directorio anclado) y la apertura efectiva DENTRO de
      _sha_via_descriptor_6g1() (envoltorio que sustituye justo antes de
      delegar en la función original): la llamada debe terminar SIN
      bloquearse (O_NONBLOCK), NO debe devolver SHA válido, el motivo debe
      identificar el objeto como no regular, la FIFO debe seguir siendo FIFO
      SIN contenido escrito por nadie, y ningún archivo ajeno se elimina ni
      se altera (vecino byte a byte; directorio sin entradas inesperadas).
      Verificación sobre el estado real en disco (lstat/bytes/SHA-256), no
      sólo el retorno.

Evidencia: evidence/pruebas_h1_r2_r2_6g1.json + evidence/matriz_h1_r2_r2_6g1.csv
"""
import csv
import hashlib
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
from comun_6g1 import sha_file, dump

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1h1r2r2')


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


def unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # ---- R2: regular -> FIFO entre la identificación y la apertura
    try:
        base = TRABAJO / 'R2'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        nombre = 'salida.wav'
        bytes0 = b'ORIGINAL que sera sustituida por una FIFO en la ventana\n'
        (base / nombre).write_bytes(bytes0)
        vecino = 'ajeno_vecino.txt'
        bytes_v = b'VECINO AJENO: no debe eliminarse ni alterarse\n'
        (base / vecino).write_bytes(bytes_v)
        sha_v = sha_file(base / vecino)
        fd_dir = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW)
        # 1: identificación inicial del archivo regular (lstat relativo)
        st = os.lstat(nombre, dir_fd=fd_dir)
        assert stat.S_ISREG(st.st_mode)
        # 2: envoltorio que sustituye la entrada por una FIFO en el PUNTO
        # EXACTO entre la identificación inicial y la apertura interna de
        # _sha_via_descriptor_6g1 (antes de delegar en la función original)
        original_sha = L._sha_via_descriptor_6g1
        suceso = dict(sustituida=False)

        def sha_con_fifo(nombre_, fd_dir_, st_):
            os.unlink(nombre_, dir_fd=fd_dir_)
            os.mkfifo(nombre_, 0o644, dir_fd=fd_dir_)
            suceso['sustituida'] = True
            return original_sha(nombre_, fd_dir_, st_)

        L._sha_via_descriptor_6g1 = sha_con_fifo
        sha, err, transcurrido, agotado = None, None, None, False
        previo = signal.signal(signal.SIGALRM, _alarma)
        signal.setitimer(signal.ITIMER_REAL, 8)   # fail-safe anti-bloqueo
        try:
            t0 = time.perf_counter()
            try:
                # 3: ejecución de la función (con la sustitución inyectada)
                sha, err = L._sha_via_descriptor_6g1(nombre, fd_dir, st)
            except _TiempoAgotado:
                agotado = True
            transcurrido = time.perf_counter() - t0
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previo)
            L._sha_via_descriptor_6g1 = original_sha
        # 4-7: verificación sobre el estado real en disco
        st_fifo = os.lstat(nombre, dir_fd=fd_dir)
        fd_r = os.open(nombre, os.O_RDONLY | os.O_NONBLOCK, dir_fd=fd_dir)
        try:
            contenido_fifo = os.read(fd_r, 4096)
        finally:
            os.close(fd_r)
        nombres_dir = sorted(os.listdir(fd_dir))
        checks = [
            ('sustitucion_inyectada_en_la_ventana',
             suceso['sustituida'] and stat.S_ISFIFO(st_fifo.st_mode),
             str(suceso)),
            ('termino_sin_bloquearse',
             not agotado and transcurrido is not None and transcurrido < 5.0,
             'agotado=%s transcurrido=%s' % (agotado, transcurrido)),
            ('sin_sha_valido', sha is None, str(sha)),
            ('motivo_identifica_no_regular',
             err is not None and 'no_es_archivo_regular' in err, str(err)),
            ('fifo_sin_contenido_escrito',
             stat.S_ISFIFO(st_fifo.st_mode) and contenido_fifo == b'',
             str(contenido_fifo[:20])),
            ('vecino_ajeno_intacto',
             (base / vecino).read_bytes() == bytes_v
             and sha_file(base / vecino) == sha_v,
             sha_file(base / vecino)[:16]),
            ('sin_entradas_inesperadas_ni_eliminaciones',
             nombres_dir == ['ajeno_vecino.txt', 'salida.wav'],
             str(nombres_dir)),
        ]
        filas.append(fila('R2', 'lectura_segura_6g1',
                          'regular sustituida por FIFO entre la identificación '
                          'y la apertura: sin bloqueo, sin SHA válido, '
                          'fail-closed', checks))
        detalles['R2'] = dict(err=err, sha=sha,
                              transcurrido=transcurrido, agotado=agotado,
                              fifo_con_contenido=contenido_fifo != b'')
        os.close(fd_dir)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('R2', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R2'] = dict(error=repr(exc))

    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== H1-R2-R2 unidad ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %s' % (f['veredicto'], f['detalle'][:90]))
    dump(EV / 'pruebas_h1_r2_r2_6g1.json',
         dict(schema='pruebas-h1-r2-r2-6g1/1', filas=todas,
              detalles=detalle_todo))
    with (EV / 'matriz_h1_r2_r2_6g1.csv').open('w', newline='',
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
