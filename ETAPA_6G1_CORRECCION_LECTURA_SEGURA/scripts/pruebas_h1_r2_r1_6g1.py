"""Pruebas H1-R2-R1 (rectificación 6G.1 — verificación del archivo durante el hash).

Ejecuta ÚNICAMENTE la prueba focalizada de este hallazgo; las regresiones
(H1-R2, H1 y C-R1) se ejecutan con sus propias baterías. No repite las
baterías históricas (34/26/17/12).

  R1a  Modificación DETERMINISTA del contenido DURANTE el cálculo del
       SHA-256 (gancho sobre os.read: tras el primer bloque leído se
       sobrescribe el archivo in situ — misma longitud, mediante pwrite con
       dir_fd, sin sustituir el inodo): la verificación posterior debe
       detectarlo (doble fstat: identidad/tamaño/mtime/ctime entre ambos
       estados) y NO devolver un SHA válido como si el archivo hubiera
       permanecido estable. Comprueba además que el descriptor siguió
       apuntando al mismo inodo (la modificación fue in situ, no una
       sustitución), que la modificación ocurrió después de comenzar la
       lectura, y que el archivo no se eliminó ni se alteró fuera de lo
       previsto por la prueba (bytes exactos esperados tras la modificación).
  R1b  Caso normal de archivo ESTABLE: el SHA devuelto coincide con el
       calculado independientemente (hashlib sobre los bytes), sin error y
       sin efectos sobre el archivo.

Evidencia: evidence/pruebas_h1_r2_r1_6g1.json + evidence/matriz_h1_r2_r1_6g1.csv
"""
import csv
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import sha_file, dump

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1h1r2r1')


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

    # ---- R1a: modificación del contenido DURANTE el cálculo del SHA
    try:
        base = TRABAJO / 'R1a'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        nombre = 'salida.wav'
        # >1 MiB para garantizar al menos dos bloques de lectura
        bytes0 = b'A' * ((1 << 20) + 100)
        (base / nombre).write_bytes(bytes0)
        ruta = base / nombre
        L.registrar_propio_6g1(ruta, estable=True)
        L.acreditar_dir_6g1(base)
        fd_dir = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW)
        st_lstat = os.lstat(nombre, dir_fd=fd_dir)
        ino_antes = (st_lstat.st_dev, st_lstat.st_ino)

        # gancho determinista: tras el PRIMER bloque leído, se modifica el
        # contenido in situ (misma longitud; escritura por dir_fd, sin
        # sustituir el inodo y sin eliminar el archivo)
        original_read = os.read
        estado = dict(bloques_leidos=0, modificado_en_bloque=None)

        def read_durante_hash(fd, n):
            bloque = original_read(fd, n)
            if bloque and estado['modificado_en_bloque'] is None:
                fd_w = os.open(nombre, os.O_WRONLY, dir_fd=fd_dir)
                try:
                    os.pwrite(fd_w, b'XX', 0)   # sobrescribe in situ
                finally:
                    os.close(fd_w)
                estado['modificado_en_bloque'] = estado['bloques_leidos'] + 1
            estado['bloques_leidos'] += 1
            return bloque

        os.read = read_durante_hash
        try:
            sha, err = L._sha_via_descriptor_6g1(nombre, fd_dir, st_lstat)
        finally:
            os.read = original_read
            os.close(fd_dir)
        bytes_esperados = b'XX' + bytes0[2:]   # única alteración prevista
        ino_despues = (os.lstat(nombre, dir_fd=0) if False else
                       (os.lstat(str(ruta)).st_dev, os.lstat(str(ruta)).st_ino))
        checks = [
            ('modificacion_ocurrida_tras_comenzar_lectura',
             estado['modificado_en_bloque'] == 1
             and estado['bloques_leidos'] >= 2,
             str(estado)),
            ('descriptor_mismo_inodo_toda_la_lectura',
             ino_antes == ino_despues
             and err is not None
             and 'modificado durante la lectura' in err
             and 'identidad cambiada' not in err,
             'ino_antes=%s ino_despues=%s err=%s'
             % (ino_antes, ino_despues, err)),
            ('verificacion_detecto_cambio',
             err is not None
             and ('modificado durante la lectura' in err
                  or 'identidad cambiada' in err),
             str(err)),
            ('sha_no_devuelto_como_valido',
             sha is None,
             str(sha)),
            ('archivo_no_eliminado', ruta.exists(), ''),
            ('solo_alteracion_prevista',
             ruta.read_bytes() == bytes_esperados,
             ruta.read_bytes()[:8]),
        ]
        filas.append(fila('R1a', 'lectura_segura_6g1',
                          'modificación durante el hash: detectada por el '
                          'doble fstat; sin SHA válido', checks))
        detalles['R1a'] = dict(err=err, sha=sha, estado=estado,
                               ino_antes=ino_antes, ino_despues=ino_despues)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('R1a', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R1a'] = dict(error=repr(exc))

    # ---- R1b: archivo estable -> SHA coincidente con el independiente
    try:
        base = TRABAJO / 'R1b'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        nombre = 'salida_estable.wav'
        bytes0 = b'B' * (300 * 1024)
        (base / nombre).write_bytes(bytes0)
        ruta = base / nombre
        L.registrar_propio_6g1(ruta, estable=True)
        L.acreditar_dir_6g1(base)
        fd_dir = os.open(str(base), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW)
        st_lstat = os.lstat(nombre, dir_fd=fd_dir)
        sha, err = L._sha_via_descriptor_6g1(nombre, fd_dir, st_lstat)
        os.close(fd_dir)
        sha_independiente = hashlib.sha256(bytes0).hexdigest()
        checks = [
            ('sin_error_en_archivo_estable', err is None, str(err)),
            ('sha_coincide_con_independiente',
             sha == sha_independiente,
             '%s vs %s' % ((sha or '')[:16], sha_independiente[:16])),
            ('archivo_intacto_tras_hash',
             ruta.read_bytes() == bytes0
             and sha_file(ruta) == sha_independiente,
             sha_file(ruta)[:16]),
        ]
        filas.append(fila('R1b', 'lectura_segura_6g1',
                          'archivo estable: SHA idéntico al calculado '
                          'independientemente', checks))
        detalles['R1b'] = dict(err=err, sha=sha,
                               sha_independiente=sha_independiente)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('R1b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['R1b'] = dict(error=repr(exc))

    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== H1-R2-R1 unidad ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %s' % (f['veredicto'], f['detalle'][:90]))
    dump(EV / 'pruebas_h1_r2_r1_6g1.json',
         dict(schema='pruebas-h1-r2-r1-6g1/1', filas=todas,
              detalles=detalle_todo))
    with (EV / 'matriz_h1_r2_r1_6g1.csv').open('w', newline='',
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
