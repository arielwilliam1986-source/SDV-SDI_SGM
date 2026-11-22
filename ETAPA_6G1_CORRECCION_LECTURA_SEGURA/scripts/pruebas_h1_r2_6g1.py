"""Pruebas H1-R2 (rectificación 6G.1 — cierre de dos brechas de anclaje).

Ejecuta ÚNICAMENTE la batería focalizada de este hallazgo; no repite las
baterías históricas (34/26/17/12). Las regresiones focalizadas de H1
(H1a/H1b/H1c + tres flujos de aborto) y de C-R1 se ejecutan con sus propias
baterías (pruebas_h1_6g1.py y pruebas_c_r1_6g1.py, actualizadas).

  Prueba A (H1-R2/A — acreditación segura desde la creación):
    A1  crear_y_acreditar_dir_6g1 crea el provisional (mkdir dir_fd, modo
        0o700) dentro del padre validado y acredita por fstat la identidad
        del objeto CREADO; la identidad acreditada coincide con la de una
        apertura independiente O_NOFOLLOW del provisional.
    A2  sustitución de la ruta provisional por un IMPOSTOR (directorio real
        distinto) después de la acreditación: el sustituto NUNCA queda
        acreditado como provisional legítimo — el aborto por esa ruta es
        fail-closed (identidad_distinta), sin ABORT en el impostor y con su
        contenido intacto; el provisional acreditado (movido aparte) sigue
        vinculado a la corrida.
    A3  padre NO conforme (modificable por terceros, g+w): el mecanismo se
        niega (RuntimeError), no crea nada y no acredita nada (fail-closed).
  Prueba B (H1-R2/B — inventario exclusivamente por descriptores):
    B1  tras abrir y validar el descriptor del provisional, la ruta se
        sustituye por un IMPOSTOR (con un archivo señuelo de contenido
        distinto) ANTES de clasificar los archivos: la clasificación sigue
        correspondiendo al directorio originalmente abierto (ABORT_6G1.json
        aterriza en el ORIGINAL vía descriptor — verificado donde quedó el
        descriptor tras el renombrado), el árbol impostor/externo NO es
        consultado (sin ABORT allí, señuelo byte a byte intacto) y las
        salidas clasificadas corresponden al original.
    B2  la clasificación no re-consulta rutas: con la ruta del provisional
        apuntando al impostor durante TODO el inventario, el registro /3
        lista las salidas del original (imposible de ver por ruta).

Evidencia: evidence/pruebas_h1_r2_6g1.json + evidence/matriz_h1_r2_6g1.csv
"""
import csv
import json
import os
import shutil
import stat
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import sha_file, dump

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1h1r2')


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

    # ---------------- Prueba A ----------------
    # ---- A1: creación+acreditación por descriptores; identidad == lo creado
    try:
        base = TRABAJO / 'A1'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        padre = base / 'out'
        padre.mkdir()
        L.reiniciar_registro_6g1()
        ruta, (dev, ino) = L.crear_y_acreditar_dir_6g1(padre, 'run_partial')
        st_indep = os.fstat(os.open(ruta, os.O_RDONLY | os.O_DIRECTORY
                                    | os.O_NOFOLLOW))
        reg = L._DIR_6G1[ruta]
        checks = [
            ('provisional_creado', os.path.isdir(ruta), ruta),
            ('modo_privado_0o700',
             (os.lstat(ruta).st_mode & 0o777) == 0o700,
             oct(os.lstat(ruta).st_mode & 0o777)),
            ('acreditada_identidad_del_creado',
             (reg['device'], reg['inode']) == (dev, ino)
             and (dev, ino) == (st_indep.st_dev, st_indep.st_ino),
             str((reg['device'], reg['inode']), )),
            ('vinculada_a_la_corrida',
             L._anclar_dir_aborto_6g1(ruta)[0] is not None, ''),
        ]
        filas.append(fila('A1', 'lectura_segura_6g1',
                          'creación+acreditación por descriptores con padre '
                          'validado', checks))
        detalles['A1'] = dict(ruta=ruta, acreditada=(dev, ino))
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('A1', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['A1'] = dict(error=repr(exc))

    # ---- A2: sustituto en la ruta tras la acreditación -> nunca acreditado
    try:
        base = TRABAJO / 'A2'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        padre = base / 'out'
        padre.mkdir()
        L.reiniciar_registro_6g1()
        ruta, (dev, ino) = L.crear_y_acreditar_dir_6g1(padre, 'run_partial')
        # el provisional acreditado se mantiene VIVO, movido aparte (como en
        # el escenario real en que el motor conserva su objeto creado)
        aparte = base / 'original_vivo'
        os.rename(ruta, aparte)
        (aparte / 'propio.wav').write_bytes(b'salida del provisional acreditado\n')
        # impostor OCUPANDO la ruta original (directorio real distinto al
        # acreditado; creado directamente en la ruta tras el renombrado)
        bytes_imp = b'contenido del IMPOSTOR: nunca debe recibir el ABORT\n'
        imposter = Path(ruta)                      # ruta es str (del helper)
        imposter.mkdir()
        (imposter / 'señuelo.txt').write_bytes(bytes_imp)
        sha_imp = sha_file(imposter / 'señuelo.txt')
        info = L.abortar_6g1(ruta, 'PRUEBA_H1R2_A2')
        checks = [
            ('sustituto_nunca_acreditado',
             info.get('directorio_acreditado') is False
             and 'identidad_distinta' in str(info.get('anclaje_directorio', '')),
             str(info.get('anclaje_directorio'))),
            ('sin_abort_en_impostor', not (imposter / 'ABORT_6G1.json').exists(), ''),
            ('impostor_byte_a_byte',
             (imposter / 'señuelo.txt').read_bytes() == bytes_imp
             and sha_file(imposter / 'señuelo.txt') == sha_imp,
             sha_file(imposter / 'señuelo.txt')[:16]),
            ('nada_eliminado', (imposter / 'señuelo.txt').exists()
             and (aparte / 'propio.wav').exists(), ''),
            ('sin_salidas_validas', info.get('resultados_validos') == []
             and info.get('salidas_invalidadas') == []
             and info.get('conservados') == [], ''),
            ('schema_3', info.get('schema') == 'abort-6g1/3', ''),
        ]
        filas.append(fila('A2', 'lectura_segura_6g1',
                          'sustituto en la ruta tras la acreditación: nunca '
                          'acreditado como provisional legítimo', checks))
        detalles['A2'] = dict(info=info)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('A2', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['A2'] = dict(error=repr(exc))

    # ---- A3: padre no conforme -> fail-closed, sin crear ni acreditar
    try:
        base = TRABAJO / 'A3'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        padre = base / 'out'
        padre.mkdir()                              # 0755 (conforme)
        L.reiniciar_registro_6g1()
        os.chmod(padre, 0o775)                     # escritura de grupo -> NO
        error = None
        try:
            L.crear_y_acreditar_dir_6g1(padre, 'run_partial')
        except RuntimeError as exc:
            error = str(exc)
        checks = [
            ('negacion_fail_closed', error is not None
             and 'modificable por terceros' in error, str(error)),
            ('sin_acreditacion',
             not any(str(k).startswith(str(padre)) for k in L._DIR_6G1),
             str(list(L._DIR_6G1))),
            ('sin_acreditacion_ninguna', len(L._DIR_6G1) == 0,
             str(len(L._DIR_6G1))),
        ]
        os.chmod(padre, 0o755)
        filas.append(fila('A3', 'lectura_segura_6g1',
                          'padre modificable por terceros: el mecanismo se '
                          'niega (fail-closed, sin crear ni acreditar)',
                          checks))
        detalles['A3'] = dict(error=error)
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('A3', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['A3'] = dict(error=repr(exc))

    # ---------------- Prueba B ----------------
    # ---- B1/B2: ruta sustituida tras validar el descriptor, antes de clasificar
    try:
        base = TRABAJO / 'B1'
        shutil.rmtree(base, ignore_errors=True)
        base.mkdir(parents=True)
        run = base / 'run_partial'
        run.mkdir()
        bytes_propio = b'salida propia ORIGINAL (en el provisional real)\n'
        salida = run / 'salida.wav'
        salida.write_bytes(bytes_propio)
        ajeno = run / 'ajeno_ordinario.txt'
        ajeno.write_bytes(b'ajeno del provisional real\n')
        sha_ajeno = sha_file(ajeno)
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(salida, estable=True)
        L.acreditar_dir_6g1(run)

        original_clas = L._clasificar_entrada_6g1
        suceso = dict(sustituido=False, ruta_durante_clasificacion=[])

        def clas_con_sustitucion(nombre, st, fd_dir, ruta_esperada):
            if not suceso['sustituido']:
                # sustitución de la ruta DESPUÉS de abrir y validar el
                # descriptor y ANTES de clasificar los archivos: el original
                # se mueva aparte (sigue vivo, accesible sólo por descriptor)
                # y un impostor con contenido distinto ocupa la ruta
                movido = base / 'original_via_descriptor'
                os.rename(run, movido)
                run.mkdir()
                (run / 'salida.wav').write_bytes(
                    b'IMPOSTOR: el arbol externo no debe ser consultado\n')
                suceso['sustituido'] = True
            suceso['ruta_durante_clasificacion'].append(nombre)
            return original_clas(nombre, st, fd_dir, ruta_esperada)

        L._clasificar_entrada_6g1 = clas_con_sustitucion
        try:
            info = L.abortar_6g1(run, 'PRUEBA_H1R2_B1')
        finally:
            L._clasificar_entrada_6g1 = original_clas
        movido = base / 'original_via_descriptor'
        imposter = run
        bytes_imp = b'IMPOSTOR: el arbol externo no debe ser consultado\n'
        checks = [
            ('sustitucion_antes_de_clasificar', suceso['sustituido'], ''),
            ('abort_en_el_original_via_descriptor',
             (movido / 'ABORT_6G1.json').is_file()
             and not (imposter / 'ABORT_6G1.json').exists(),
             str(sorted(p.name for p in movido.iterdir()))),
            ('abort_directorio_acreditado_true',
             info.get('directorio_acreditado') is True,
             str(info.get('anclaje_directorio'))),
            ('clasificacion_del_original',
             'salida.wav' in info.get('salidas_invalidadas', [])
             and info.get('resultados_validos') == [],
             str(info.get('salidas_invalidadas'))),
            ('sin_consulta_del_arbol_impostor',
             not any('salida.wav' in str(m) and 'IMPOSTOR' in str(m)
                     for m in info.get('motivos_propiedad', {}).values()),
             str(info.get('motivos_propiedad', {}).get('salida.wav'))),
            ('impostor_byte_a_byte',
             (imposter / 'salida.wav').read_bytes() == bytes_imp,
             (imposter / 'salida.wav').read_bytes()[:40]),
            ('sin_abort_en_impostor', not (imposter / 'ABORT_6G1.json').exists(), ''),
            ('ajeno_original_intacto',
             (movido / 'ajeno_ordinario.txt').read_bytes()
             == b'ajeno del provisional real\n'
             and sha_file(movido / 'ajeno_ordinario.txt') == sha_ajeno,
             sha_file(movido / 'ajeno_ordinario.txt')[:16]),
            ('nada_eliminado', salida == run / 'salida.wav'
             and (movido / 'salida.wav').read_bytes() == bytes_propio, ''),
            ('schema_3', info.get('schema') == 'abort-6g1/3', ''),
        ]
        filas.append(fila('B1', 'lectura_segura_6g1',
                          'ruta sustituida tras validar el descriptor y antes '
                          'de clasificar: la clasificación sigue al '
                          'descriptor original, sin consultar el árbol '
                          'externo', checks))
        detalles['B1'] = dict(info=info,
                              clasificadas=suceso['ruta_durante_clasificacion'])
        shutil.rmtree(base, ignore_errors=True)
    except Exception as exc:
        filas.append(fila('B1', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['B1'] = dict(error=repr(exc))

    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== H1-R2 unidad (Prueba A y Prueba B) ==')
    fu, du = unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-14s %s' % (f['veredicto'], f['detalle'][:90]))
    dump(EV / 'pruebas_h1_r2_6g1.json',
         dict(schema='pruebas-h1-r2-6g1/1', filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_h1_r2_6g1.csv').open('w', newline='',
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
