#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROTOTIPO EXPERIMENTAL — Publicación anclada por descriptores (6G.1, I-1/D).

Instrucción de Cris (22-11-2026): analizar y PROPONER (no implementar) una
solución que elimine la sustitución TOCTOU de la publicación exitosa. Este
prototipo NO modifica producción: implementa el mecanismo propuesto en un
módulo de diagnóstico independiente y lo somete a los escenarios exigidos.

Mecanismo propuesto (PDA-1, "publicación por par anclado"):
  1. En la creación del provisional se CONSERVA el descriptor del directorio
     padre validado (O_DIRECTORY|O_NOFOLLOW, privacidad euid verificada) junto
     con el NOMBRE RELATIVO acreditado y la identidad (st_dev, st_ino) del
     provisional, obtenida por fstat sobre descriptor.
  2. En la publicación se opera EXCLUSIVAMENTE con renameat2 relativo a ese
     descriptor (src_dir_fd=dst_dir_fd=fd_padre): la cadena absoluta de
     componentes intermedios NO se vuelve a resolver jamás.
  3. Antes del renombrado: fstat(padre) re-verifica privacidad y fstatat
     (AT_SYMLINK_NOFOLLOW) verifica que la entrada nominal sigue siendo el
     directorio acreditado (no symlink, identidad exacta).
  4. renameat2(RENAME_NOREPLACE): colisión -> EEXIST sin tocar el destino
     existente (fail-closed o sufijo re-verificado).
  5. Tras el renombrado: fstatat del destino por descriptor verifica que el
     objeto publicado es EXACTAMENTE el acreditado; si no, fail-closed sin
     éxito declarado.

Uso:
  python -B scripts/prototipo_publicacion_anclada_6g1.py \
      --work /tmp/pda_6g1 \
      --out evidence/prototipo_publicacion_anclada_6g1
"""
import argparse
import ctypes
import errno
import hashlib
import json
import os
import shutil
import stat
import time

SCHEMA = 'prototipo-pda-1/1'

_AT_FDCWD = -100
_RENAME_NOREPLACE = (1 << 0)


# ---------------------------------------------------------------------------
# Primitivas relativas a descriptores (mecanismo propuesto).
# ---------------------------------------------------------------------------

def _libc():
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, 'renameat2', None)
    if fn is None:
        raise OSError('renameat2 indisponible (requerido por el diseño)')
    fn.restype = ctypes.c_int
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                   ctypes.c_char_p, ctypes.c_uint]
    return fn


def fstatat_nofollow(fd_dir, nombre):
    """fstat relativo al descriptor, sin seguir enlaces. None si falla."""
    try:
        return os.stat(str(nombre), dir_fd=fd_dir, follow_symlinks=False)
    except OSError:
        return None


def renameat2_noreplace_fd(src_fd, src_name, dst_fd, dst_name):
    """renameat2(RENAME_NOREPLACE) relativo a descriptores de directorio."""
    fn = _libc()
    r = fn(src_fd, os.fsencode(str(src_name)), dst_fd,
           os.fsencode(str(dst_name)), _RENAME_NOREPLACE)
    if r != 0:
        e = ctypes.get_errno()
        if e == errno.EEXIST:
            raise FileExistsError(e, 'destino existente', str(dst_name))
        raise OSError(e, os.strerror(e), str(src_name), None, str(dst_name))


def _privacidad_ok(st):
    return (st.st_uid == os.geteuid()
            and not (st.st_mode & (stat.S_IWGRP | stat.S_IWOTH)))


def crear_y_anclar(padre_ruta, nombre_base='prov'):
    """Crea el provisional y devuelve el PAR ANCLADO conservado:
    fd_padre (descriptor del padre validado), nombre relativo acreditado,
    identidad del provisional y del padre, todo obtenido por descriptor."""
    fd_padre = os.open(padre_ruta,
                       os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st_padre = os.fstat(fd_padre)
        if not stat.S_ISDIR(st_padre.st_mode):
            raise RuntimeError('el padre no es un directorio')
        if not _privacidad_ok(st_padre):
            raise RuntimeError('padre no privado (euid / permisos grupo-otros)')
        identidad_padre = dict(dev=st_padre.st_dev, ino=st_padre.st_ino,
                               modo=stat.filemode(st_padre.st_mode),
                               uid=st_padre.st_uid)
        intento = 0
        while True:
            nombre = '%s_%s%s' % (nombre_base,
                                  time.strftime('%Y%m%d_%H%M%S'),
                                  '' if intento == 0 else '_%03d' % intento)
            try:
                os.mkdir(nombre, 0o700, dir_fd=fd_padre)
                break
            except FileExistsError:
                intento += 1
                if intento > 999:
                    raise
        fd_dir = os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW, dir_fd=fd_padre)
        try:
            st = os.fstat(fd_dir)
            if not stat.S_ISDIR(st.st_mode):
                raise RuntimeError('lo creado no es un directorio')
        finally:
            os.close(fd_dir)
        return dict(fd_padre=fd_padre, nombre=nombre,
                    identidad=dict(dev=st.st_dev, ino=st.st_ino),
                    identidad_padre=identidad_padre,
                    ruta_nominal=os.path.join(os.path.abspath(padre_ruta),
                                              nombre))
    except Exception:
        os.close(fd_padre)
        raise


def publicar_anclada(ancla, nombre_final, inyector=None, usar_sufijos=True,
                     max_intentos=64):
    """Publicación anclada PDA-1. Cada paso queda registrado. Fail-closed:
    `exito` sólo es True si el objeto publicado en el destino resultó ser
    EXACTAMENTE el provisional acreditado (verificado por descriptor)."""
    fd_padre = ancla['fd_padre']
    nombre_prov = ancla['nombre']
    ident = ancla['identidad']
    pasos = []
    resultado = dict(exito=False, publicado=False,
                     traslado_verificado=False,
                     destino=None, motivos=[], pasos=pasos)

    def motivo(m):
        resultado['motivos'].append(m)

    # (1) El descriptor del padre sigue siendo un directorio privado y es el
    #     mismo objeto acreditado en la creación (fstat, sin rutas).
    try:
        st_padre = os.fstat(fd_padre)
    except OSError as exc:
        motivo('padre_fd_no_valido: %s' % exc)
        return resultado
    if not stat.S_ISDIR(st_padre.st_mode):
        motivo('padre_fd_no_es_directorio')
        return resultado
    if not _privacidad_ok(st_padre):
        motivo('padre_perdio_privacidad (chmod o cambio de propietario)')
        return resultado
    if (st_padre.st_dev, st_padre.st_ino) != \
            (ancla['identidad_padre']['dev'], ancla['identidad_padre']['ino']):
        motivo('padre_fd_identidad_distinta')
        return resultado
    pasos.append(dict(paso=1, fstat_padre='OK (directorio privado, identidad '
                                       'de la creación)'))

    # (2) La entrada nominal, RELATIVA al descriptor validado y SIN seguir
    #     enlaces, sigue siendo el provisional acreditado.
    st_ent = fstatat_nofollow(fd_padre, nombre_prov)
    if st_ent is None:
        motivo('entrada_nominal_ausente (renombrada o eliminada dentro del '
               'padre validado)')
        return resultado
    if stat.S_ISLNK(st_ent.st_mode):
        motivo('entrada_nominal_es_symlink')
        return resultado
    if not stat.S_ISDIR(st_ent.st_mode):
        motivo('entrada_nominal_no_es_directorio')
        return resultado
    if (st_ent.st_dev, st_ent.st_ino) != (ident['dev'], ident['ino']):
        motivo('entrada_nominal_identidad_distinta (sustituida dentro del '
               'padre validado)')
        return resultado
    pasos.append(dict(paso=2, fstatat_entrada='OK (identidad del provisional '
                                              'acreditado)'))

    # (3) Punto de inyección DETERMINISTA para pruebas (sólo diagnóstico):
    #     llamada entre la comprobación y el renombrado.
    if inyector is not None:
        pasos.append(dict(paso=3, inyector=inyector(nombre_prov)))
        st_post = fstatat_nofollow(fd_padre, nombre_prov)
        resultado['inyeccion_aplicada'] = True
        resultado['identidad_entrada_tras_inyeccion'] = (
            dict(dev=st_post.st_dev, ino=st_post.st_ino) if st_post else None)

    # (4) renameat2(RENAME_NOREPLACE) relativo al MISMO descriptor validado:
    #     la cadena absoluta de componentes intermedios no se resuelve.
    destino = nombre_final
    for i in range(max_intentos):
        try:
            renameat2_noreplace_fd(fd_padre, nombre_prov, fd_padre, destino)
            break
        except FileExistsError:
            if not usar_sufijos:
                motivo('destino_colisionado (EEXIST, fail-closed sin sufijo)')
                return resultado
            destino = '%s_r%03d' % (nombre_final, i + 1)
            pasos.append(dict(paso=4, colision=destino))
            continue
        except OSError as exc:
            motivo('renameat2_fallo: %s' % exc)
            return resultado
    else:
        motivo('agotados_intentos_de_colision')
        return resultado
    pasos.append(dict(paso=4, renameat2='OK', destino=destino))

    # (5) Verificación POST por descriptor: el objeto publicado es el
    #     acreditado. Sin esta verificación no se declara éxito nunca.
    st_dst = fstatat_nofollow(fd_padre, destino)
    if st_dst is None:
        motivo('destino_no_observable_tras_renombrado')
        return resultado
    if stat.S_ISLNK(st_dst.st_mode):
        motivo('destino_es_symlink_tras_renombrado')
        return resultado
    publicado_es_acreditado = (st_dst.st_dev, st_dst.st_ino) == \
        (ident['dev'], ident['ino'])
    pasos.append(dict(paso=5, verificacion_post=dict(
        destino=destino,
        identidad_publicada=dict(dev=st_dst.st_dev, ino=st_dst.st_ino),
        identidad_acreditada=ident,
        coincide=publicado_es_acreditado)))
    resultado.update(destino=destino, publicado=True,
                     traslado_verificado=publicado_es_acreditado,
                     exito=bool(publicado_es_acreditado))
    if not publicado_es_acreditado:
        motivo('OBJETO_PUBLICADO_DISTINTO_DEL_ACREDITADO (sustitución dentro '
               'de la microventana entre fstatat y renameat2; imposible para '
               'un atacante sin permiso de escritura sobre el padre validado; '
               'fail-closed: sin éxito declarado)')
    return resultado


def ruta_real_del_ancla(fd_padre, nombre):
    """Ruta física real de la entrada (vía /proc, sin resolver componentes)."""
    with open('/proc/self/fd/%d/%s' % (fd_padre, nombre), 'rb') as f:
        return os.path.realpath(f.name)


# ---------------------------------------------------------------------------
# Escenarios de diagnóstico.
# ---------------------------------------------------------------------------

def limpiar(p):
    if os.path.islink(p) or os.path.isfile(p):
        os.unlink(p)
    elif os.path.isdir(p):
        os.chmod(p, 0o700)
        for dp, dns, _fns in os.walk(p):
            for d in dns:
                try:
                    os.chmod(os.path.join(dp, d), 0o700)
                except OSError:
                    pass
        shutil.rmtree(p)


def nuevo(name, titulo, amenaza, clasificacion, resultado, extra=None):
    d = dict(schema=SCHEMA, escenario=name, titulo=titulo, amenaza=amenaza,
             clasificacion=clasificacion, resultado=resultado)
    if extra:
        d.update(extra)
    return d


def _escenario_base(work, name, sustituir_antes=False):
    """Estructura compartida: shared(0777)/user(0700)/base(0700) con ancla
    creada por crear_y_anclar en base; devuelve (ancla, rutas)."""
    raiz = os.path.join(work, name)
    limpiar(raiz)
    shared = os.path.join(raiz, 'shared')
    user = os.path.join(shared, 'user')
    base = os.path.join(user, 'base')
    os.makedirs(base, 0o700)
    os.chmod(shared, 0o777)
    ancla = crear_y_anclar(base)
    rutas = dict(raiz=raiz, shared=shared, user=user, base=base)
    if sustituir_antes:
        # atacante con permiso de escritura sobre shared: rename + reconstrucción
        os.rename(user, user + '.orig')
        os.mkdir(user, 0o777)
        os.mkdir(os.path.join(user, 'base'), 0o700)
        rutas.update(user_orig=user + '.orig', base_atacante=os.path.join(user, 'base'))
    return ancla, rutas


def escenario_p0(work, outdir):
    ancla, r = _escenario_base(work, 'P0')
    os.mkdir(os.path.join(r['base'], ancla['nombre'], 'contenido'),
             0o700)  # artefacto DENTRO del provisional
    res = publicar_anclada(ancla, 'run_final')
    st_dst = fstatat_nofollow(ancla['fd_padre'], res['destino'] or '')
    ruta_publicada = os.path.join(os.path.abspath(r['base']),
                                  res['destino'] or 'x')
    detalle = dict(
        publicacion=res,
        destino_existe=os.path.isdir(ruta_publicada),
        contenido_publicado=sorted(os.listdir(ruta_publicada))
        if os.path.isdir(ruta_publicada) else None,
        provisional_desaparecio_del_padre=(
            fstatat_nofollow(ancla['fd_padre'], ancla['nombre']) is None),
        ruta_nominal_publicada=ruta_publicada)
    ok = (res['exito'] and res['traslado_verificado']
          and detalle['provisional_desaparecio_del_padre']
          and detalle['contenido_publicado'] == ['contenido'])
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P0', 'Publicación anclada normal (sin ataque)',
                 'Ninguna: línea base del mecanismo propuesto.',
                 ['comportamiento_permitido_por_diseno'], detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW'))


def escenario_p1(work, outdir):
    """Sustitución del componente intermedio ANTES de publicar."""
    ancla, r = _escenario_base(work, 'P1', sustituir_antes=True)
    os.mkdir(os.path.join(r['user_orig'], 'base', ancla['nombre'],
                          'contenido'), 0o700)
    # el atacante deja un señuelo con el MISMO nombre nominal del provisional
    prov_atacante = os.path.join(r['base_atacante'], ancla['nombre'])
    os.mkdir(prov_atacante, 0o700)
    with open(os.path.join(prov_atacante, 'ATAQUE.txt'), 'w') as f:
        f.write('senuelo del atacante\n')
    res = publicar_anclada(ancla, 'run_final')
    publicado_en_arbol_real = os.path.join(r['user_orig'], 'base',
                                           res['destino'] or 'x')
    publicado_en_arbol_atacante = os.path.join(r['base_atacante'],
                                               res['destino'] or 'x')
    detalle = dict(
        publicacion=res,
        ruta_nominal_que_habria_resuelto_el_motor=os.path.join(
            r['base_atacante'], 'run_final'),
        publicado_en_arbol_real=dict(
            existe=os.path.isdir(publicado_en_arbol_real),
            identidad=dict(dev=os.lstat(publicado_en_arbol_real).st_dev,
                           ino=os.lstat(publicado_en_arbol_real).st_ino)
            if os.path.isdir(publicado_en_arbol_real) else None,
            contenido=sorted(os.listdir(publicado_en_arbol_real))
            if os.path.isdir(publicado_en_arbol_real) else None),
        publicado_en_arbol_atacante=dict(
            existe=os.path.isdir(publicado_en_arbol_atacante),
            contenido=sorted(os.listdir(publicado_en_arbol_atacante))
            if os.path.isdir(publicado_en_arbol_atacante) else None),
        senuelo_atacante_no_movido=os.path.isdir(prov_atacante))
    ok = (res['exito'] and res['traslado_verificado']
          and detalle['publicado_en_arbol_real']['contenido'] == ['contenido']
          and not detalle['publicado_en_arbol_atacante']['existe']
          and detalle['senuelo_atacante_no_movido'])
    clas = ['vulnerabilidad_eliminada_por_diseno',
            'comportamiento_permitido_por_diseno']
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P1', 'Sustitución del componente INTERMEDIO antes de la '
                 'publicación (atacante con escritura sobre el directorio '
                 'del componente)',
                 'Que la publicación renombre un objeto del atacante o caiga '
                 'fuera del provisional acreditado.',
                 clas, detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW',
                            nota='el renombrado ocurre SIEMPRE sobre el '
                                 'descriptor del padre validado de la '
                                 'creación; la ruta nominal secuestrada no '
                                 'participa en la operación'))


def escenario_p2(work, outdir):
    ancla, r = _escenario_base(work, 'P2')
    os.mkdir(os.path.join(r['base'], 'run_final'), 0o700)   # colisión
    os.mkdir(os.path.join(r['base'], ancla['nombre'], 'contenido'), 0o700)
    res_fc = publicar_anclada(ancla, 'run_final', usar_sufijos=False)
    st_colision = fstatat_nofollow(ancla['fd_padre'], 'run_final')
    colision_intacto = (st_colision is not None
                        and len(os.listdir(os.path.join(r['base'],
                                                        'run_final'))) == 0)
    # variante del diseño: sufijos con re-verificación de identidad
    res_suf = publicar_anclada(ancla, 'run_final', usar_sufijos=True)
    detalle = dict(
        fail_closed_sin_sufijos={k: v for k, v in res_fc.items()
                                 if k != 'pasos'},
        destino_original_intacto=colision_intacto,
        variante_con_sufijos={k: v for k, v in res_suf.items()
                              if k != 'pasos'},
        destino_sufijo=res_suf.get('destino'),
        sufijo_re_verificado=res_suf.get('traslado_verificado'))
    ok = (not res_fc['exito'] and 'EEXIST' in ''.join(res_fc['motivos'])
          and colision_intacto
          and res_suf['exito'] and res_suf['traslado_verificado']
          and res_suf.get('destino') == 'run_final_r001')
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P2', 'Colisión del destino (nombre final ya existente)',
                 'Que la publicación reemplace el destino existente.',
                 ['comportamiento_rechazado_por_diseno'], detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW',
                            nota='RENAME_NOREPLACE: EEXIST, sin tocar el '
                                 'destino; con sufijos se re-verificaría '
                                 'identidad (usar_sufijos=True)'))


def escenario_p3(work, outdir):
    ancla, r = _escenario_base(work, 'P3')
    ajeno = os.path.join(r['base'], 'run_final')
    os.mkdir(ajeno, 0o700)
    with open(os.path.join(ajeno, 'OBJETO_AJENO.txt'), 'w') as f:
        f.write('ajeno\n')
    res = publicar_anclada(ancla, 'run_final', usar_sufijos=False)
    ajeno_intacto = sorted(os.listdir(ajeno)) == ['OBJETO_AJENO.txt']
    detalle = dict(publicacion=res, objeto_ajeno_intacto=ajeno_intacto)
    ok = not res['exito'] and ajeno_intacto
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P3', 'Destino sustituido por un objeto ajeno preexistente',
                 'Que la publicación sobrescriba o fusione el objeto ajeno.',
                 ['comportamiento_rechazado_por_diseno'], detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW'))


def escenario_p4(work, outdir):
    ancla, r = _escenario_base(work, 'P4')
    # atacante de la MISMA uid renombra la entrada DENTRO del padre validado
    # y deja un impostor con el mismo nombre
    os.rename(os.path.join(r['base'], ancla['nombre']),
              os.path.join(r['base'], ancla['nombre'] + '.robado'))
    impostor = os.path.join(r['base'], ancla['nombre'])
    os.mkdir(impostor, 0o700)
    with open(os.path.join(impostor, 'IMPOSTOR.txt'), 'w') as f:
        f.write('impostor\n')
    res = publicar_anclada(ancla, 'run_final', usar_sufijos=False)
    impostor_intacto = os.path.isdir(impostor) and \
        sorted(os.listdir(impostor)) == ['IMPOSTOR.txt']
    robado_aun_existe = os.path.isdir(
        os.path.join(r['base'], ancla['nombre'] + '.robado'))
    detalle = dict(publicacion=res,
                   impostor_no_publicado=impostor_intacto,
                   provisional_robado_conservado=robado_aun_existe)
    ok = (not res['exito'] and impostor_intacto and robado_aun_existe
          and any('identidad_distinta' in m or 'ausente' in m
                  for m in res['motivos']))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P4', 'Sustitución de la ENTRADA nominal dentro del padre '
                 'validado (atacante de la MISMA uid) antes de la publicación',
                 'Que la publicación renombre el objeto impostor.',
                 ['comportamiento_rechazado_por_diseno (detección por '
                  'fstatat previo)',
                  'limitacion_residual_atacante_misma_uid'], detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW',
                            nota='imposible para atacante de OTRA uid: el '
                                 'padre es 0700 del euid; la detección '
                                 'fstatat(AT_SYMLINK_NOFOLLOW) cubre el caso'))


def escenario_p5(work, outdir):
    ancla, r = _escenario_base(work, 'P5')

    def inyector_durante(nombre_prov):
        """Atacante de la MISMA uid actúa en la microventana entre fstatat y
        renameat2 (inyección determinista, sólo diagnóstico)."""
        os.rename(os.path.join(r['base'], nombre_prov),
                  os.path.join(r['base'], nombre_prov + '.robado'))
        os.mkdir(os.path.join(r['base'], nombre_prov), 0o700)
        with open(os.path.join(r['base'], nombre_prov, 'IMPOSTOR.txt'),
                  'w') as f:
            f.write('impostor\n')
        return 'entrada sustituida por impostor dentro del padre validado'

    res = publicar_anclada(ancla, 'run_final', inyector=inyector_durante,
                           usar_sufijos=False)
    det = res['pasos'][-1]['verificacion_post'] if res['pasos'] and \
        res['pasos'][-1].get('verificacion_post') else None
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        pasos=res['pasos'],
        verificacion_post=det,
        provisional_robado_conservado=os.path.isdir(
            os.path.join(r['base'], ancla['nombre'] + '.robado')))
    # el impostor pudo ser renombrado (misma uid), pero NUNCA se declara éxito
    ok = (not res['exito'] and res.get('traslado_verificado') is False
          and det is not None and det['coincide'] is False)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P5', 'Sustitución ENTRE la comprobación y el renombrado '
                 '(inyección determinista en la microventana; atacante de la '
                 'misma uid)',
                 'Que la publicación renombre un objeto distinto del '
                 'acreditado Y lo declare éxito.',
                 ['limitacion_residual_atacante_misma_uid (el rename puede '
                  'mover el impostor en la microventana)',
                  'comportamiento_rechazado_por_diseno (nunca se declara '
                  'éxito: verificación post por descriptor -> fail-closed)'],
                 detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW',
                            nota='para atacante de OTRA uid la microventana '
                                 'no es explotable: no puede crear/sustituir '
                                 'entradas dentro del padre 0700 del euid; '
                                 'el EXIT_OK exige traslado_verificado=True'))


def escenario_p6(work, outdir):
    ancla, r = _escenario_base(work, 'P6')
    os.chmod(r['base'], 0o777)   # el propietario abre el padre al mundo
    res = publicar_anclada(ancla, 'run_final')
    os.chmod(r['base'], 0o700)
    detalle = dict(publicacion=res,
                   modo_padre_tras_chmod='0777 en el momento de publicar')
    ok = not res['exito'] and any('privacidad' in m for m in res['motivos'])
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P6', 'El padre validado pierde privacidad (chmod 0777) '
                 'antes de la publicación',
                 'Que la publicación ocurra sobre un padre ya modificable '
                 'por terceros.',
                 ['comportamiento_rechazado_por_diseno'], detalle,
                 extra=dict(veredicto='PASS' if ok else 'REVIEW'))


def escenario_p7(work, outdir):
    """¿Bastaría con conservar SOLO el descriptor del provisional?"""
    # (A) sin fd del padre, la única opción de rename es re-resolver la ruta
    #     nominal -> reproducimos la vulnerabilidad del diseño actual.
    ancla, r = _escenario_base(work, 'P7', sustituir_antes=True)
    prov_real = os.path.join(r['user_orig'], 'base', ancla['nombre'])
    os.mkdir(os.path.join(r['user_orig'], 'base', ancla['nombre'],
                          'contenido'), 0o700)
    prov_atacante = os.path.join(r['base_atacante'], ancla['nombre'])
    os.mkdir(prov_atacante, 0o700)
    # Ruta nominal secuestrada: rename POR RUTA (como publicar_dir_6g1 hoy)
    destino_nominal = os.path.join(r['base_atacante'], 'run_final_via_ruta')
    os.rename(os.path.join(r['base_atacante'], ancla['nombre']),
              destino_nominal)
    published_is_accredited = False
    try:
        st = os.lstat(destino_nominal)
        published_is_accredited = (st.st_dev, st.st_ino) == \
            (ancla['identidad']['dev'], ancla['identidad']['ino'])
    except OSError:
        pass
    real_intacto = os.path.isdir(prov_real)
    # (B) alternativa linkat O_PATH + AT_EMPTY_PATH: ¿factible sin CAP_DAC_
    #     READ_SEARCH? ¿qué semántica deja?
    linkat = dict(intentado=False)
    try:
        fd_opath = os.open('/proc/self/fd/%d' % ancla['fd_padre'],
                           os.O_RDONLY | os.O_DIRECTORY)  # reabre el PADRE real
        # el objeto a publicar: el provisional real, abierto por descriptor
        fd_prov = os.open(ancla['nombre'],
                          os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                          dir_fd=ancla['fd_padre'])
        os.close(fd_opath)
        libc = ctypes.CDLL(None, use_errno=True)
        # glibc rechaza la cadena vacía con ENOENT antes de llegar al kernel;
        # para obtener la respuesta REAL del kernel se usa syscall() directo.
        NR_LINKAT = {'x86_64': 265, 'aarch64': 37}
        nr = NR_LINKAT.get(os.uname().machine)
        destino_link = 'run_final_via_linkat'
        if nr is None:
            linkat['error'] = 'sin número de syscall linkat para %s' \
                % os.uname().machine
            rc, e = None, None
        else:
            sysc = libc.syscall
            sysc.restype = ctypes.c_long
            sysc.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                             ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            rc = sysc(nr, fd_prov, b'', ancla['fd_padre'],
                      os.fsencode(destino_link), 0x1000)  # AT_EMPTY_PATH
            e = ctypes.get_errno() if rc != 0 else 0
            linkat.update(intentado=True, via='syscall directo al kernel',
                          rc=rc,
                          errno=e, errno_nombre=os.strerror(e) if e else None,
                          destino_creado=(rc == 0),
                          nota=('si rc==0, el inodo acreditado tendría DOS '
                                'nombres: el original (en el árbol posiblemente '
                                'secuestrado) y el nuevo; el atacante retiene '
                                'el original y el provisional no se MUEVE'))
            if rc == 0:
                os.unlink(destino_link, dir_fd=ancla['fd_padre'])
        os.close(fd_prov)
        # variante O_PATH: man 2 linkat permite AT_EMPTY_PATH sin
        # CAP_DAC_READ_SEARCH cuando oldfd se abrió con O_PATH
        fd_opath = os.open('/proc/self/fd/%d' % ancla['fd_padre'],
                           os.O_PATH | os.O_DIRECTORY)
        try:
            sysc = libc.syscall
            sysc.restype = ctypes.c_long
            sysc.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                             ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            destino_opath = 'run_final_via_linkat_opath'
            rc2 = sysc(nr, fd_opath, b'', ancla['fd_padre'],
                       os.fsencode(destino_opath), 0x1000)
            e2 = ctypes.get_errno() if rc2 != 0 else 0
            linkat['via_opath'] = dict(rc=rc2, errno=e2,
                                       errno_nombre=os.strerror(e2) if e2
                                       else None,
                                       destino_creado=(rc2 == 0))
            if rc2 == 0:
                os.unlink(destino_opath, dir_fd=ancla['fd_padre'])
        finally:
            os.close(fd_opath)
    except OSError as exc:
        linkat['error'] = '%s: %s' % (type(exc).__name__, exc)
    try:
        sysctl_ph = open('/proc/sys/fs/protected_hardlinks').read().strip()
    except OSError:
        sysctl_ph = 'desconocido'
    detalle = dict(
        entorno_linkat=dict(protected_hardlinks=sysctl_ph,
                            euid=os.geteuid(),
                            cap_dac_read_search='no (sin capacidades '
                                                'extrañas, euid normal)'),
        solo_fd_provisional=dict(
            via_re_resolucion_ruta=dict(
                resultado='renombra el objeto del atacante (vulnerabilidad '
                          'reproducida)' if not published_is_accredited
                else 'renombró el acreditado',
                publicado_es_acreditado=published_is_accredited,
                provisional_real_conservado_en_arbol_real=real_intacto),
            via_linkat_at_empty_path=linkat,
            conclusion=('NO es suficiente: rename* exige (dirfd_padre, '
                        'nombre); sin el padre hay que re-resolver rutas '
                        '(vulnerable) o usar linkat/AT_EMPTY_PATH (semántica '
                        'de doble nombre, no mueve, y dependiente de '
                        'privilegios/limitaciones del kernel)')),
        ancla_con_padre=dict(
            nota='con (fd_padre, nombre): la operación relativa renombra la '
                 'entrada correcta del padre validado (ver P1)'))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo('P7', 'Análisis experimental: ¿conservar sólo el descriptor '
                 'del provisional sin el descriptor del padre?',
                 'Determinar si el par (fd_padre, nombre) es prescindible.',
                 ['resultado_experimental', 'DOCUMENTED_FACT (conclusión)'],
                 detalle,
                 extra=dict(veredicto='CONCLUIDO'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='/tmp/pda_6g1')
    ap.add_argument('--out',
                    default=os.path.join(
                        os.path.dirname(os.path.dirname(
                            os.path.abspath(__file__))),
                        'evidence', 'prototipo_publicacion_anclada_6g1'))
    args = ap.parse_args()
    os.makedirs(args.work, 0o700, exist_ok=True)
    os.makedirs(args.out, 0o755, exist_ok=True)
    escenarios = dict(P0=escenario_p0, P1=escenario_p1, P2=escenario_p2,
                      P3=escenario_p3, P4=escenario_p4, P5=escenario_p5,
                      P6=escenario_p6, P7=escenario_p7)
    resultados = []
    for name in ['P0', 'P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7']:
        print('=== %s ===' % name, flush=True)
        r = escenarios[name](args.work, args.out)
        p = os.path.join(args.out, 'escenario_%s.json' % name)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=1, ensure_ascii=False, sort_keys=True)
        v = r.get('veredicto', '?')
        print('  ->', p, '| veredicto:', v, flush=True)
        resultados.append(dict(escenario=name, veredicto=v,
                               clasificacion=r['clasificacion'],
                               fichero=os.path.basename(p)))
    con = dict(schema=SCHEMA,
               generado=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               mecanismo='PDA-1 (par anclado fd_padre + nombre relativo, '
                         'renameat2 RENAME_NOREPLACE relativo)',
               entorno=dict(python='.'.join(map(str, __import__('sys')
                                                .version_info[:3])),
                            euid=os.geteuid(),
                            kernel=open('/proc/sys/kernel/osrelease')
                            .read().strip()),
               escenarios=resultados)
    with open(os.path.join(args.out,
                           'consolidado_prototipo_pda_1.json'), 'w',
              encoding='utf-8') as f:
        json.dump(con, f, indent=1, ensure_ascii=False)
    print('consolidado:', os.path.join(args.out,
                                       'consolidado_prototipo_pda_1.json'))


if __name__ == '__main__':
    main()
