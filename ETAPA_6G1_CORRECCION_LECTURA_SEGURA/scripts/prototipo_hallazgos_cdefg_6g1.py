#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROTOTIPO EXPERIMENTAL — Hallazgos C, D, E, F y G (PDA-1/EA, 22-11-2026).

Instrucción de Cris: cierre de garantías pendientes. NO modifica producción;
reutiliza el mecanismo PDA-1 (prototipo_publicacion_anclada_6g1) y, para el
caso obligatorio del hallazgo D, las FUNCIONES REALES sin modificar de
motores/lectura_segura_6g1.py (sólo se importan y se llaman).

Escenarios:
  C1..C4  symlink en la ENTRADA FINAL de cada tipo de artefacto, abierto vía
          la ruta procfs del directorio anclado -> ¿la escritura termina
          fuera del acreditado? (brecha, esperada: SÍ, misma uid)
  C5      creación EXCLUSIVA openat(O_CREAT|O_EXCL|O_NOFOLLOW): rechaza
          symlink y regular precolocados (fail-closed)
  C6      archivo anclado por SU PROPIO descriptor (fd_archivo conservado,
          bibliotecas vía /proc/self/fd/<fd_archivo>): sustitución de la
          entrada entre creación y escritura no desvía la escritura;
          verificación de identidad por archivo. RECTIFICACIÓN (Cris): incluye
          engine_log.txt con el mecanismo compatible con Tee propuesto para
          producción (objeto archivo sobre dup(fd_log); clase real NO
          modificada) y verificación por BYTES de que el destino ajeno queda
          sin alteración
  D1      secuencia OBLIGATORIA con el módulo REAL (sin modificar):
          acreditar -> conservar -> sustituir intermedio -> abortar_6g1 real
          -> ¿puede localizar/identificar/invalidar/conservar?
  D2      aborto anclado relativo a fd_run/fd_padre (propuesta): ABORT_6G1.json
          exclusivo y no-follow DENTRO del acreditado real, inventario por
          descriptor, invalidación sin eliminación, con fds abiertos y en
          camino de excepción; cierre de todos los descriptores (0 residuales)
  E1      guarda de completitud (matriz por motor/modo): existencia, tipo,
          no-symlink, identidad vs fd de creación. RECTIFICACIÓN FINAL
          (Cris): E1-A todo artefacto obligatorio EXIGE descriptor válido y
          coincidente (descriptor ausente -> FAIL, sin PASS por defecto);
          E1-B masks presente exige identidad (dev,ino) == fstat(fd_masks).
          RECTIFICACIÓN previa: la
          obligatoriedad de masks depende EFECTIVAMENTE de masks_obligatorio
          (sin parámetro que desactive la comprobación): directorios de
          prueba INDEPENDIENTES — MQR masks ausente+obligatorio -> FAIL;
          Hardened/EVO masks ausente+opcional -> PASS en esa dimensión; masks
          existente (aun opcional) debe ser directorio real, no symlink; el
          resto de artefactos obligatorios sigue sometido a sus comprobaciones
  F1      ciclo de vida de descriptores: cierre EXACTO una vez, sin cierre
          prematuro mientras la biblioteca usa el objeto, fallo tras abrir
          VARIOS recursos -> 0 descriptores residuales. RECTIFICACIÓN (Cris):
          fd_candidates creado CORRECTAMENTE, descriptores de archivos
          individuales, cierre en orden inverso; distinción explícita entre
          lo demostrado por el prototipo y lo que requiere integración en los
          motores (el ciclo real de los motores NO queda validado aquí)
  G1      evidencia forense: publicacion_6g1.json escrito por fd_run ANTES de
          publicar (viaja con el inodo), verificación externa post-B2;
          manipulación por la misma uid demostrada (NO inmutable, declarado).
          RECTIFICACIÓN FINAL (Cris): verificación EFECTIVA de integridad con
          alcance documental DELIMITADO (mix SDV.wav y analysis.json; NO se
          afirma la verificación de todos los artefactos de producción) —
          publicar -> leer el registro -> RECALCULAR los SHA-256 de los
          artefactos publicados -> comparar -> PASS al coincidir; escenario
          INDEPENDIENTE con alteración deliberada de un artefacto publicado
          -> la auditoría detecta la discrepancia; se mantiene la declaración
          de que el registro NO es inmutable frente a la misma uid y NO se le
          atribuyen garantías de autenticidad que no posee

Uso:
  python -B scripts/prototipo_hallazgos_cdefg_6g1.py \
      --work /tmp/cdefg_6g1 --out evidence/prototipo_hallazgos_cdefg_6g1
"""
import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from prototipo_publicacion_anclada_6g1 import (  # noqa: E402
    crear_y_anclar, publicar_anclada, fstatat_nofollow, limpiar)

MOTORES = os.path.join(os.path.dirname(HERE), 'motores')
sys.path.insert(0, MOTORES)

import numpy as np                     # noqa: E402
import soundfile as sf                 # noqa: E402

SCHEMA = 'prototipo-cdefg-1/1'
SR = 44100


def proc(fd, rel=''):
    if rel:
        return '/proc/self/fd/%d/%s' % (fd, rel)
    return '/proc/self/fd/%d' % fd


def datos_wav(amplitud=0.3):
    d = np.zeros((SR, 2), dtype='float64')
    d[:, 0] = amplitud
    return d


def nuevo(name, titulo, amenaza, clasificacion, resultado, extra=None):
    d = dict(schema=SCHEMA, escenario=name, titulo=titulo, amenaza=amenaza,
             clasificacion=clasificacion, resultado=resultado)
    if extra:
        d.update(extra)
    return d


def _estructura(work, name, sustituir=False):
    raiz = os.path.join(work, name)
    limpiar(raiz)
    shared = os.path.join(raiz, 'shared')
    user = os.path.join(shared, 'user')
    base = os.path.join(user, 'base')
    os.makedirs(base, 0o700)
    os.chmod(shared, 0o777)
    ancla = crear_y_anclar(base)
    r = dict(raiz=raiz, shared=shared, user=user, base=base,
             base_nominal=base)
    if sustituir:
        os.rename(user, user + '.orig')
        os.mkdir(user, 0o777)
        os.mkdir(os.path.join(user, 'base'), 0o700)
        os.mkdir(os.path.join(user, 'base', ancla['nombre']), 0o700)
        r['base_nominal'] = os.path.join(user, 'base')
        r['base_real'] = os.path.join(user + '.orig', 'base')
    return ancla, r


# ---------------------------------------------------------------------------
# Hallazgo C — symlink en la entrada final (brecha) y soluciones.
# ---------------------------------------------------------------------------

def _preparar_symlink(r, ancla, nombre, objetivo):
    """La misma uid sustituye la entrada final por un symlink dentro del
    acreditado (el directorio es 0700 del euid: la misma uid puede)."""
    entrada = os.path.join(r['base'], ancla['nombre'], nombre)
    os.symlink(objetivo, entrada)
    return entrada


def escenario_c1_c4(work, outdir):
    """C1-C4: symlink final en analysis.json / WAV / .npy / engine_log,
    escritos por la ruta procfs del DIRECTORIO anclado (mecanismo EA de la
    revisión anterior, sin protección de la entrada final)."""
    casos = []
    # C1 — analysis.json con open()
    ancla, r = _estructura(work, 'C1')
    objetivo = os.path.join(r['raiz'], 'objetivo_ajeno.txt')
    _preparar_symlink(r, ancla, 'analysis.json', objetivo)
    with open(proc(ancla['fd_padre'], ancla['nombre'] + '/analysis.json'),
              'w', encoding='utf-8') as f:
        json.dump({'caso': 'C1'}, f)
    c1 = dict(
        fuera_del_acreditado=os.path.exists(objetivo)
        and 'caso' in open(objetivo, encoding='utf-8').read(),
        entrada_final_es_symlink=os.path.islink(os.path.join(
            r['base'], ancla['nombre'], 'analysis.json')),
        acreditado_contiene_archivo_regular=os.path.isfile(
            os.path.join(r['base'], ancla['nombre'], 'analysis.json'))
        and not os.path.islink(os.path.join(r['base'], ancla['nombre'],
                                            'analysis.json')))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    casos.append(('C1', 'analysis.json (open builtin)', c1))
    # C2 — WAV con soundfile
    ancla, r = _estructura(work, 'C2')
    objetivo = os.path.join(r['raiz'], 'objetivo_ajeno.wav')
    _preparar_symlink(r, ancla, 'mix SDV.wav', objetivo)
    with sf.SoundFile(proc(ancla['fd_padre'],
                           ancla['nombre'] + '/mix SDV.wav'),
                      mode='w', samplerate=SR, channels=2) as h:
        h.write(datos_wav())
    c2 = dict(fuera_del_acreditado=os.path.exists(objetivo),
              frames_en_objetivo_ajeno=None)
    if os.path.exists(objetivo):
        d, sr = sf.read(objetivo, dtype='float64')
        c2['frames_en_objetivo_ajeno'] = len(d)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    casos.append(('C2', 'mix SDV.wav (sf.SoundFile)', c2))
    # C3 — .npy con open_memmap
    ancla, r = _estructura(work, 'C3')
    objetivo = os.path.join(r['raiz'], 'objetivo_ajeno.npy')
    _preparar_symlink(r, ancla, 'masks.npy', objetivo)
    mm = np.lib.format.open_memmap(
        proc(ancla['fd_padre'], ancla['nombre'] + '/masks.npy'),
        mode='w+', dtype='float32', shape=(32, 4))
    mm[:] = 0.5
    mm.flush()
    del mm
    c3 = dict(fuera_del_acreditado=os.path.exists(objetivo))
    if os.path.exists(objetivo):
        arr = np.load(objetivo)
        c3['shape_en_objetivo_ajeno'] = list(arr.shape)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    casos.append(('C3', 'masks.npy (np.open_memmap)', c3))
    # C4 — engine_log.txt con open (Tee)
    ancla, r = _estructura(work, 'C4')
    objetivo = os.path.join(r['raiz'], 'objetivo_ajeno.log')
    _preparar_symlink(r, ancla, 'engine_log.txt', objetivo)
    with open(proc(ancla['fd_padre'], ancla['nombre'] + '/engine_log.txt'),
              'w', encoding='utf-8') as f:
        f.write('LOG C4\n')
    c4 = dict(fuera_del_acreditado=os.path.exists(objetivo)
              and 'LOG C4' in open(objetivo, encoding='utf-8').read())
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    casos.append(('C4', 'engine_log.txt (Tee/open)', c4))

    detalle = {}
    brechas = 0
    for name, api, res in casos:
        res['respuesta'] = ('ESCRITURA FUERA DEL ACREDITADO (brecha '
                            'confirmada): la ruta procfs del DIRECTORIO '
                            'protege los componentes intermedios pero NO la '
                            'entrada final; aplicable a la MISMA uid (una '
                            'uid distinta no puede crear entradas dentro de '
                            'un 0700 del euid)' if res['fuera_del_acreditado']
                            else 'sin desvío (revisar)')
        if res['fuera_del_acreditado']:
            brechas += 1
        detalle[name] = dict(api=api, **res)
    return nuevo(
        'C1-C4', 'Symlink en la ENTRADA FINAL de cada artefacto, con el '
        'mecanismo EA anterior (ruta procfs del directorio anclado)',
        'Que una escritura termine FUERA del directorio acreditado pese al '
        'anclaje del directorio.',
        ['vulnerabilidad_reproducida_para_misma_uid',
         'comportamiento_rechazado_para_otra_uid (por construcción del '
         'padre 0700: no puede precolocar la entrada)'],
        detalle,
        extra=dict(veredicto='DEMOSTRADO' if brechas == 4 else 'REVIEW',
                   nota='no atribuir a EA protecciones de la entrada final '
                        'que no ofrece: la ruta procfs del directorio sigue '
                        'el componente final con semántica open normal'))


def escenario_c5(work, outdir):
    """C5: creación exclusiva O_CREAT|O_EXCL|O_NOFOLLOW vía openat."""
    ancla, r = _estructura(work, 'C5')
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    res = {}
    # (a) symlink precolocado -> EEXIST
    _preparar_symlink(r, ancla, 'analysis.json',
                      os.path.join(r['raiz'], 'ajeno.txt'))
    try:
        os.open('analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
        res['a_symlink_precolocado'] = 'SIN_ERROR (inesperado)'
    except FileExistsError as exc:
        res['a_symlink_precolocado'] = 'FileExistsError (EEXIST): rechazado'
    except OSError as exc:
        res['a_symlink_precolocado'] = 'OSError(%s): %s' % (exc.errno, exc)
    # (b) regular ajeno precolocado -> EEXIST
    with open(os.path.join(r['base'], ancla['nombre'], 'mix SDV.wav'),
              'w') as f:
        f.write('ajeno')
    try:
        os.open('mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
        res['b_regular_precolocado'] = 'SIN_ERROR (inesperado)'
    except FileExistsError:
        res['b_regular_precolocado'] = 'FileExistsError (EEXIST): rechazado'
    # (c) nombre LIBRE -> creado exclusivo (otro nombre, sin precolocación)
    fd = os.open('input_integrity_6g.json',
                 os.O_CREAT | os.O_EXCL | os.O_WRONLY
                 | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    os.close(fd)
    res['c_nombre_libre'] = 'creado (descriptor exclusivo)'
    ok = (res['a_symlink_precolocado'].startswith('FileExistsError')
          and res['b_regular_precolocado'].startswith('FileExistsError'))
    os.close(fd_run)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'C5', 'Creación EXCLUSIVA de cada archivo con openat(O_CREAT|O_EXCL|'
        'O_NOFOLLOW) relativo a fd_run',
        'Que una entrada precolocada (symlink o regular ajeno) sea seguida '
        'por la creación.',
        ['comportamiento_rechazado_por_diseno'], res,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   nota='O_EXCL|O_CREAT|O_NOFOLLOW: EEXIST ante symlink '
                        'precolocado (no lo sigue y no lo reemplaza) y ante '
                        'regular preexistente; el motor no crea el archivo '
                        'si no es el PRIMERO con ese nombre dentro del '
                        'acreditado (fail-closed ante precolocación)'))


class TeeAnclado6g1:
    """Mecanismo compatible con Tee PROPUESTO PARA PRODUCCIÓN (sólo prototipo).

    La clase Tee real (motores, NO modificada) consume un objeto archivo
    `self._file` con la interfaz write/flush/close. La propuesta es construir
    ESE objeto sobre `os.fdopen(os.dup(fd_log), 'w')`, donde fd_log es el
    descriptor conservado de la creación EXCLUSIVA de engine_log.txt
    (O_CREAT|O_EXCL|O_NOFOLLOW relativo a fd_run). Esta clase replica la misma
    interfaz y semántica de error de cierre (error_cierre_6g1) para demostrar
    el mecanismo sin importar ni modificar el módulo real del motor.
    """

    def __init__(self, fd_log):
        self._file = os.fdopen(os.dup(fd_log), 'w', encoding='utf-8')
        self.error_cierre_6g1 = None

    def write(self, data):
        self._file.write(data)
        self._file.flush()

    def flush(self):
        self._file.flush()

    def close(self):
        try:
            self._file.close()
        except Exception as exc:
            if self.error_cierre_6g1 is None:
                self.error_cierre_6g1 = '%s: %s' % (type(exc).__name__, exc)
            raise
        finally:
            if getattr(self._file, 'closed', False) is True:
                self._file = None


def escenario_c6(work, outdir):
    """C6: archivo anclado por SU PROPIO descriptor; sustitución de la
    entrada entre creación y escritura; verificación de identidad final."""
    ancla, r = _estructura(work, 'C6', sustituir=True)
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    fd_masks = os.open('masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=fd_run)
    # destinos AJENOS del atacante (fuera del acreditado) con contenido
    # centinela conocido ANTES de la sustitución; tras el experimento deben
    # seguir byte a byte idénticos (la escritura NO debió desviarse)
    centinelas = {
        'objetivo_analysis.json': b'{"ajeno": true}\n',
        'objetivo_mix SDV.wav': b'AJENO-WAV-SENTINEL\n',
        'objetivo_confidence_map.npy': b'AJENO-NPY-SENTINEL\n',
        'objetivo_engine_log.txt': b'LINEA AJENA PREVIA\n'}
    for nombre_c, contenido_c in centinelas.items():
        with open(os.path.join(r['raiz'], nombre_c), 'wb') as f:
            f.write(contenido_c)
    # creación EXCLUSIVA + conservación del descriptor de cada archivo
    # (engine_log.txt incluido: mecanismo compatible con Tee, clase real
    # sin modificar)
    fd_json = os.open('analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                      | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    fd_wav = os.open('mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                     | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    fd_npy = os.open('confidence_map.npy',
                     os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
                     0o600, dir_fd=fd_masks)
    fd_log = os.open('engine_log.txt', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                     | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    identidad_creacion = dict(
        analysis=ino_de_fd(fd_json), wav=ino_de_fd(fd_wav),
        npy=ino_de_fd(fd_npy), log=ino_de_fd(fd_log))
    # --- el atacante (misma uid) sustituye las ENTRADAS entre creación y
    #     escritura: unlink + symlink con el mismo nombre ---
    sustituciones = {}
    for nombre in ['analysis.json', 'mix SDV.wav', 'masks/confidence_map.npy',
                   'engine_log.txt']:
        sub, _, base_n = nombre.rpartition('/')
        dirfd = fd_masks if sub else fd_run
        os.unlink(base_n, dir_fd=dirfd)
        os.symlink(os.path.join(r['raiz'], 'objetivo_%s' % base_n), base_n,
                   dir_fd=dirfd)
        sustituciones[nombre] = 'unlink + symlink precolocado'
    # --- escrituras por el DESCRIPTOR conservado (bibliotecas vía procfs) ---
    with os.fdopen(os.dup(fd_json), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'C6', 'via': 'fd_archivo'}, f)
    sf_write_wav_fd(fd_wav, datos_wav())
    mm = np.lib.format.open_memmap(proc(fd_npy), mode='w+',
                                   dtype='float32', shape=(32, 4))
    mm[:] = 0.5
    mm.flush()
    del mm
    # log vía el mecanismo compatible con Tee (objeto archivo sobre
    # dup(fd_log)); el cierre de Tee cierra su DUP, no el fd del motor
    tee = TeeAnclado6g1(fd_log)
    for i in range(3):
        tee.write('[Motor] linea de log %d escrita por el descriptor anclado\n'
                  % i)
    tee.close()
    try:
        os.fstat(fd_log)
        fd_log_valido_tras_tee = True
    except OSError:
        fd_log_valido_tras_tee = False
    # verificación del destino ajeno SIN ALTERACIÓN (comparación byte a byte
    # contra el centinela previo a la sustitución)
    destino_ajeno_sin_alterar = {}
    for nombre_c, contenido_c in centinelas.items():
        with open(os.path.join(r['raiz'], nombre_c), 'rb') as f:
            destino_ajeno_sin_alterar[nombre_c] = f.read() == contenido_c
    # --- verificación de identidad POR ARCHIVO: fd vs entrada nominal ---
    verificacion = dict(
        analysis=dict(fd=ino_de_fd(fd_json),
                      entrada=ino_entrada(fd_run, 'analysis.json')),
        wav=dict(fd=ino_de_fd(fd_wav),
                 entrada=ino_entrada(fd_run, 'mix SDV.wav')),
        npy=dict(fd=ino_de_fd(fd_npy),
                 entrada=ino_entrada(fd_masks, 'confidence_map.npy')),
        log=dict(fd=ino_de_fd(fd_log),
                 entrada=ino_entrada(fd_run, 'engine_log.txt')))
    for k, v in verificacion.items():
        v['coincide'] = (v['entrada'] is not None
                         and (v['fd']['dev'], v['fd']['ino'])
                         == (v['entrada']['dev'], v['entrada']['ino']))
        v['entrada_es_symlink'] = None
    for nombre, dirfd, clave in [('analysis.json', fd_run, 'analysis'),
                                 ('mix SDV.wav', fd_run, 'wav'),
                                 ('masks/confidence_map.npy', fd_masks,
                                  'npy'),
                                 ('engine_log.txt', fd_run, 'log')]:
        st = os.stat(nombre.rpartition('/')[2], dir_fd=dirfd,
                     follow_symlinks=False)
        verificacion[clave]['entrada_es_symlink'] = bool(
            stat.S_ISLNK(st.st_mode))
    with open(proc(fd_log), 'rb') as f:
        contenido_log = f.read().decode('utf-8')
    contenido_acreditado = dict(
        wav_leido_via_fd=sf.read(proc(fd_wav), dtype='float64')[0].shape[0],
        npy_leido_via_fd=list(np.load(proc(fd_npy)).shape),
        log_leido_via_fd=dict(
            lineas=contenido_log.count('\n'),
            correcto=all('[Motor] linea de log %d' % i in contenido_log
                         for i in range(3))))
    for f in (fd_json, fd_wav, fd_npy, fd_log):
        os.close(f)
    os.close(fd_masks)
    os.close(fd_run)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    ok = (all(destino_ajeno_sin_alterar.values())
          and all(not v['coincide'] and v['entrada_es_symlink']
                  for v in verificacion.values())
          and contenido_acreditado['wav_leido_via_fd'] == SR
          and contenido_acreditado['npy_leido_via_fd'] == [32, 4]
          and contenido_acreditado['log_leido_via_fd']['lineas'] == 3
          and contenido_acreditado['log_leido_via_fd']['correcto']
          and fd_log_valido_tras_tee)
    return nuevo(
        'C6', 'Archivo anclado por SU PROPIO descriptor (creación exclusiva '
        'O_EXCL|O_NOFOLLOW + bibliotecas vía /proc/self/fd/<fd_archivo>), '
        'con sustitución de la entrada entre creación y escritura; incluye '
        'engine_log.txt vía mecanismo compatible con Tee (clase real sin '
        'modificar) y destino ajeno verificado por bytes',
        'Que la escritura se desvíe por el symlink de la entrada sustituida, '
        'que el destino ajeno reciba contenido, o que una identidad distinta '
        'pase la verificación final.',
        ['comportamiento_permitido_por_diseno',
         'comportamiento_rechazado_por_diseno (verificación por archivo)'],
        dict(identidad_creacion=identidad_creacion,
             sustituciones=sustituciones,
             destino_ajeno_sin_alterar=destino_ajeno_sin_alterar,
             fd_log_valido_tras_cierre_de_tee=fd_log_valido_tras_tee,
             verificacion_identidad_por_archivo=verificacion,
             contenido_acreditado_via_fd=contenido_acreditado),
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   nota='la escritura por el descriptor conservado ignora la '
                        'entrada nominal (el fd designa el inodo acreditado); '
                        'la verificación fstat(fd) vs fstatat(entrada, '
                        'NOFOLLOW) DETECTA el swap por archivo (4/4, incluido '
                        'engine_log.txt); el destino ajeno queda SIN ALTERAR '
                        '(comparación byte a byte con el centinela previo); '
                        'el symlink queda en el acreditado como entrada ajena '
                        'conservada (sin eliminación), registrada por el '
                        'checklist E; el log se escribe por el mecanismo '
                        'compatible con Tee propuesto para producción '
                        '(objeto archivo sobre dup(fd_log)), sin modificar '
                        'la clase Tee real de los motores'))


def sf_write_wav_fd(fd, datos):
    """Escritura WAV real entregando a soundfile un OBJETO ARCHIVO sobre un
    dup() del descriptor acreditado (sin ruta; el fd original permanece).
    Nota de diseño: por ruta procfs de ARCHIVO (sin extensión) soundfile en
    modo 'w' exige format= y libsndfile rechaza el camino con '/' final; el
    patrón fileobj evita ambas cuestiones."""
    fobj = os.fdopen(os.dup(fd), 'wb')
    try:
        h = sf.SoundFile(fobj, mode='w', samplerate=SR, channels=2,
                         format='WAV')
    except Exception:
        fobj.close()
        raise
    with h:
        h.write(datos)


def ino_de_fd(fd):
    st = os.fstat(fd)
    return dict(dev=st.st_dev, ino=st.st_ino)


def ino_entrada(fd_dir, nombre):
    st = fstatat_nofollow(fd_dir, nombre)
    return dict(dev=st.st_dev, ino=st.st_ino) if st else None


# ---------------------------------------------------------------------------
# Hallazgo D — aborto con componente intermedio sustituido.
# ---------------------------------------------------------------------------

def escenario_d1(work, outdir):
    """D1: secuencia obligatoria con el MÓDULO REAL (sin modificar)."""
    import lectura_segura_6g1 as L
    raiz = os.path.join(work, 'D1')
    limpiar(raiz)
    shared = os.path.join(raiz, 'shared')
    user = os.path.join(shared, 'user')
    base = os.path.join(user, 'base')
    os.makedirs(base, 0o700)
    os.chmod(shared, 0o777)
    ruta, ident = L.crear_y_acreditar_dir_6g1(base, 'prov_D1')
    st_prov0 = os.lstat(ruta)
    with open(os.path.join(ruta, 'analysis.json'), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'D1'}, f)
    fd_run = os.open(ruta, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    # --- sustitución del componente intermedio ---
    os.rename(user, user + '.orig')
    os.mkdir(user, 0o777)
    os.mkdir(os.path.join(user, 'base'), 0o700)
    os.mkdir(os.path.join(user, 'base', 'prov_D1'), 0o700)
    base_real = os.path.join(user + '.orig', 'base')
    # --- excepción simulada -> protocolo REAL de aborto ---
    info = L.abortar_6g1(ruta, 'EXCEPCION_DURANTE_EL_PROCESAMIENTO',
                         detalle='D1 (módulo real, sin modificar)')
    ab_en_acreditado = os.path.exists(
        os.path.join(base_real, 'prov_D1', 'ABORT_6G1.json'))
    ab_en_atacante = os.path.exists(
        os.path.join(user, 'base', 'prov_D1', 'ABORT_6G1.json'))
    contenido_acreditado = sorted(os.listdir(
        os.path.join(base_real, 'prov_D1')))
    os.close(fd_run)
    detalle = dict(
        identidad_acreditada=dict(dev=ident[0], ino=ident[1]),
        anclaje_directorio=info.get('anclaje_directorio'),
        directorio_acreditado=info.get('directorio_acreditado'),
        abort_en_acreditado_real=ab_en_acreditado,
        abort_en_atacante=ab_en_atacante,
        contenido_acreditado=contenido_acreditado,
        politica=info.get('politica', '')[:120])
    ok = (info.get('directorio_acreditado') is False
          and not ab_en_acreditado and not ab_en_atacante)
    limpiar(raiz)
    return nuevo(
        'D1', 'Secuencia OBLIGATORIA con el protocolo REAL vigente '
        '(abortar_6g1 sin modificar): acreditar -> conservar fd_run -> '
        'sustituir intermedio -> excepción -> aborto',
        'Que el protocolo vigente localice/identifique/invalidar/conservar '
        'el directorio original sin confiar en la ruta sustituida.',
        ['vulnerabilidad_reproducida_del_protocolo_vigente_frente_a_'
         'sustitucion_de_intermedio (fail-closed: no escribe nada, pero NO '
         'localiza el provisional acreditado ni registra el aborto en él)',
         'resultado_experimental'], detalle,
        extra=dict(veredicto='DEMOSTRADO' if ok else 'REVIEW',
                   nota='el protocolo vigente actúa fail-closed (sin ABORT '
                        'en ubicación no acreditada) pero no puede llegar '
                        'al provisional real: se requiere aborto relativo a '
                        'descriptores (D2)'))


def abortar_anclado_6g1(fd_padre, nombre_prov, fd_run, motivo, detalle=None,
                        propios=()):
    """Propuesta: aborto relativo a descriptores (sin rutas).
    Inventariado por fd_run (O_NOFOLLOW, sin seguir), ABORT_6G1.json exclusivo
    y no-follow creado vía openat(dir_fd=fd_run), clasificación de salidas
    propias (invalidadas y CONSERVADAS, sin eliminación), verificación por
    re-lectura anclada. Devuelve dict informativo."""
    invalidadas, conservados, motivos = [], [], {}
    propios = set(propios)

    def inventariar(fd_base, prefijo=''):
        for nombre in sorted(os.listdir(fd_base)):
            rel = prefijo + nombre
            try:
                st = os.stat(nombre, dir_fd=fd_base, follow_symlinks=False)
            except OSError:
                continue
            if stat.S_ISLNK(st.st_mode):
                conservados.append(rel)
                motivos[rel] = 'enlace_simbolico_conservado (sin seguir)'
                continue
            if stat.S_ISDIR(st.st_mode):
                try:
                    fd_sub = os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                                     | os.O_NOFOLLOW, dir_fd=fd_base)
                except OSError:
                    continue
                try:
                    inventariar(fd_sub, rel + '/')
                finally:
                    os.close(fd_sub)
                continue
            if not stat.S_ISREG(st.st_mode):
                continue
            base_n = nombre
            if base_n in propios or rel in propios:
                invalidadas.append(rel)
                motivos[rel] = ('salida_parcial_invalidada_y_conservada '
                                '(sin eliminación; C-R1)')
            else:
                conservados.append(rel)
                motivos[rel] = 'ajeno_o_interno_conservado'

    inventariar(fd_run)
    ab = None
    motivo_ab = None
    try:
        fd_ab = os.open('ABORT_6G1.json', os.O_CREAT | os.O_EXCL
                        | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
        contenido = dict(schema='abort-6g1/3', motivo=motivo,
                         detalle=detalle,
                         salidas_invalidadas=sorted(invalidadas),
                         estado_salidas_invalidadas=('conservadas en el '
                             'provisional; sin eliminación (C-R1)'),
                         resultados_validos=[],
                         conservados=sorted(conservados),
                         motivos_propiedad=motivos,
                         analysis_intacto=('analysis.json' not in invalidadas),
                         directorio_acreditado=True,
                         anclaje_directorio=('fd_run (descriptor del '
                             'provisional acreditado, sin rutas)'),
                         politica='sin_eliminacion; aborto anclado por '
                                  'descriptores (propuesta D)')
        os.write(fd_ab, json.dumps(contenido, ensure_ascii=False,
                                   indent=1).encode('utf-8'))
        os.close(fd_ab)
        # verificación: re-lectura anclada (O_NOFOLLOW, mismo descriptor)
        fd_v = os.open('ABORT_6G1.json', os.O_RDONLY | os.O_NOFOLLOW,
                       dir_fd=fd_run)
        datos = json.loads(os.read(fd_v, 1 << 20).decode('utf-8'))
        os.close(fd_v)
        ab = (datos.get('schema') == 'abort-6g1/3'
              and datos.get('motivo') == motivo
              and datos.get('resultados_validos') == []
              and datos.get('directorio_acreditado') is True)
        motivo_ab = 'escrito y verificado sobre fd_run'
    except OSError as exc:
        motivo_ab = 'fallo de escritura ABORT: %s' % exc
        ab = False
    return dict(motivo=motivo, abort_verificado=bool(ab),
                motivo_verificacion=motivo_ab,
                salidas_invalidadas=sorted(invalidadas),
                conservados=sorted(conservados),
                ninguna_eliminacion=True,
                anclaje='fd_run/fd_padre (relativo, sin rutas)')


def escenario_d2(work, outdir):
    """D2: aborto anclado en la secuencia obligatoria (fds abiertos,
    excepción, sustitución previa) + cierre de todos los descriptores."""
    def medir_fds():
        return sorted(int(x) for x in os.listdir('/proc/self/fd'))

    ancla, r = _estructura(work, 'D2', sustituir=True)
    fds_antes = medir_fds()
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    fd_masks = os.open('masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=fd_run)
    fd_wav = os.open('mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                     | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    fd_json = os.open('analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                      | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    propios = {'mix SDV.wav', 'analysis.json'}
    # escrituras parciales por fd (corrida interrumpida)
    with os.fdopen(os.dup(fd_json), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'D2', 'parcial': True}, f)
    sf_write_wav_fd(fd_wav, datos_wav(0.2))
    # --- EXCEPCIÓN con fds abiertos + intermedio YA SUSTITUIDO ---
    res = abortar_anclado_6g1(ancla['fd_padre'], ancla['nombre'], fd_run,
                              'EXCEPCION_DURANTE_EL_PROCESAMIENTO',
                              detalle='D2', propios=propios)
    # cierre determinista de TODOS los descriptores (archivos -> subdir ->
    # fd_run -> fd_padre), exactamente una vez
    for f in (fd_wav, fd_json, fd_masks, fd_run):
        os.close(f)
    os.close(ancla['fd_padre'])
    fds_despues = medir_fds()
    residuales = [f for f in fds_despues if f not in fds_antes]
    base_real = r['base_real']
    contenido_acreditado = sorted(os.listdir(
        os.path.join(base_real, ancla['nombre'])))
    with open(os.path.join(base_real, ancla['nombre'], 'ABORT_6G1.json'),
              encoding='utf-8') as f:
        ab = json.load(f)
    detalle = dict(
        aborto=res,
        ab_schema=ab.get('schema'), ab_motivo=ab.get('motivo'),
        ab_resultados_validos=ab.get('resultados_validos'),
        ab_salidas_invalidadas=ab.get('salidas_invalidadas'),
        ab_anclaje=ab.get('anclaje_directorio'),
        contenido_acreditado_tras_aborto=contenido_acreditado,
        atacante_sin_abort=not os.path.exists(
            os.path.join(r['base_nominal'], ancla['nombre'],
                         'ABORT_6G1.json')),
        fds_residuales=residuales)
    ok = (res['abort_verificado'] and res['ninguna_eliminacion']
          and 'ABORT_6G1.json' in contenido_acreditado
          and detalle['ab_resultados_validos'] == []
          and 'analysis.json' in detalle['ab_salidas_invalidadas']
          and detalle['atacante_sin_abort'] and not residuales)
    limpiar(r['raiz'])
    return nuevo(
        'D2', 'Aborto anclado relativo a fd_run/fd_padre (propuesta): '
        'secuencia obligatoria completa con fds abiertos, excepción e '
        'intermedio sustituido, más cierre de todos los descriptores',
        'Que el aborto no pueda registrar/inventariar/conservar el '
        'provisional acreditado sin confiar en la ruta sustituida, o que '
        'queden descriptores residuales.',
        ['comportamiento_permitido_por_diseno (propuesta)',
         'vulnerabilidad_eliminada_por_diseno (anclaje por descriptor)'],
        detalle,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   nota='ABORT_6G1.json exclusivo y no-follow creado DENTRO '
                        'del acreditado real vía openat(dir_fd=fd_run); '
                        'inventario por descriptor sin seguir enlaces; '
                        'salidas propias invalidadas y conservadas (sin '
                        'eliminación); el árbol del atacante no recibe '
                        'ABORT; 0 fds residuales'))


# ---------------------------------------------------------------------------
# Hallazgo E — guarda de completitud (matriz por motor/modo).
# ---------------------------------------------------------------------------

SPEC_COMUN = {
    'engine_log.txt': dict(tipo='regular'),
    'analysis.json': dict(tipo='regular'),
    'analysis.txt': dict(tipo='regular'),
    'input_integrity_6g.json': dict(tipo='regular'),
    'mix SDV.wav': dict(tipo='regular'),
    'mix SDI.wav': dict(tipo='regular'),
}
DIF_MOTOR = {
    'Hardened': dict(masks='condicional (--png/--keep-masks)',
                     candidatos='condicional (--write-all-candidates)',
                     png='opcional (matplotlib)'),
    'EVO': dict(masks='condicional (--png/--keep-masks)',
                candidatos='condicional (--write-all-candidates)',
                png='opcional (matplotlib)'),
    'MQR': dict(masks='SIEMPRE obligatorio',
                candidatos='condicional (--write-all-candidates)',
                png='opcional (matplotlib)'),
}


def checklist_completitud(fd_run, fds_archivos, masks_obligatorio,
                          fd_masks=None):
    """Guarda de completitud por descriptor: existencia, tipo, no-symlink e
    identidad vs fd de creación. RECTIFICACIÓN FINAL Cris (E1-A/E1-B):
    E1-A: todo artefacto obligatorio EXIGE un descriptor válido y coincidente;
    la AUSENCIA del descriptor produce FAIL (nunca PASS por defecto: se
    elimina el valor por defecto True de item.get('identidad_vs_fd', True)).
    E1-B: si masks EXISTE, su identidad nominal (st_dev, st_ino) debe
    coincidir con fstat(fd_masks); masks presente sin descriptor -> FAIL.
    masks opcional y ausente sigue siendo válido; obligatorio y ausente ->
    FAIL. Devuelve (veredicto, detalles)."""
    det, ok = {}, True
    for nombre, spec in SPEC_COMUN.items():
        st = fstatat_nofollow(fd_run, nombre)
        item = dict(existe=st is not None,
                    tipo=('symlink' if st and stat.S_ISLNK(st.st_mode)
                          else 'regular' if st and stat.S_ISREG(st.st_mode)
                          else 'directorio' if st and stat.S_ISDIR(st.st_mode)
                          else 'otro/ausente'),
                    descriptor_presente=nombre in fds_archivos)
        fd = fds_archivos.get(nombre)
        if st is not None and fd is not None:
            item['identidad_vs_fd'] = (st.st_dev, st.st_ino) == \
                (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
        else:
            item['identidad_vs_fd'] = False
        item['ok'] = (st is not None and stat.S_ISREG(st.st_mode)
                      and not stat.S_ISLNK(st.st_mode)
                      and fd is not None
                      and item['identidad_vs_fd'])
        ok = ok and item['ok']
        det[nombre] = item
    st_m = fstatat_nofollow(fd_run, 'masks')
    m = dict(existe=st_m is not None,
             tipo=('symlink' if st_m and stat.S_ISLNK(st_m.st_mode)
                   else 'directorio' if st_m and stat.S_ISDIR(st_m.st_mode)
                   else 'regular/ausente' if st_m else 'ausente'),
             esperado=('obligatorio' if masks_obligatorio else 'opcional'),
             descriptor_presente=fd_masks is not None)
    if st_m is None:
        m['ok'] = not masks_obligatorio   # ausente: sólo vale si es OPCIONAL
    else:
        # presente (obligatorio u opcional): directorio REAL, no symlink y
        # con IDENTIDAD coincidente con fd_masks (E1-B); descriptor ausente
        # -> FAIL (nunca PASS por defecto)
        m['identidad_vs_fd'] = (fd_masks is not None
                                and (st_m.st_dev, st_m.st_ino)
                                == (os.fstat(fd_masks).st_dev,
                                    os.fstat(fd_masks).st_ino))
        m['ok'] = (stat.S_ISDIR(st_m.st_mode)
                   and not stat.S_ISLNK(st_m.st_mode)
                   and m['identidad_vs_fd'])
    ok = ok and m['ok']
    det['masks'] = m
    return ('PASS' if ok else 'FAIL'), det


def _dir_e1(work, etiqueta, con_masks=True, masks_symlink=False):
    """Directorio de prueba INDEPENDIENTE para E1: provisional acreditado con
    todos los artefactos comunes y masks (real / ausente / symlink) según el
    sub-caso. Devuelve (ancla, r, fd_run, fds, fd_masks). Sin simulaciones por
    parámetro que desactiven comprobaciones: la ausencia, el symlink o la
    sustitución son REALES en cada directorio."""
    ancla, r = _estructura(work, etiqueta)
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    fds = {}
    for nombre in SPEC_COMUN:
        fds[nombre] = os.open(nombre, os.O_CREAT | os.O_EXCL | os.O_WRONLY
                              | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    fd_masks = None
    if masks_symlink:
        os.symlink(os.path.join(r['raiz'], 'ajeno_masks'), 'masks',
                   dir_fd=fd_run)
    elif con_masks:
        os.mkdir('masks', 0o700, dir_fd=fd_run)
        fd_masks = os.open('masks', os.O_RDONLY | os.O_DIRECTORY
                           | os.O_NOFOLLOW, dir_fd=fd_run)
    return ancla, r, fd_run, fds, fd_masks


def _cerrar_dir_e1(ancla_x, fd_run_x, fds_x, fd_masks_x, raiz_x):
    for f in fds_x.values():
        os.close(f)
    if fd_masks_x is not None:
        os.close(fd_masks_x)
    os.close(fd_run_x)
    os.close(ancla_x['fd_padre'])
    limpiar(raiz_x)


def escenario_e1(work, outdir):
    """E1 (rectificación FINAL Cris): identidad de descriptores (E1-A) y del
    directorio masks (E1-B) — 8 escenarios nuevos con provisionales
    acreditados independientes; sin simulaciones por parámetro."""
    resultados = {}
    # E1-A1: archivo obligatorio presente y descriptor correcto -> PASS
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-A1')
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=fm)
    resultados['E1-A1'] = dict(
        situacion='todos los artefactos obligatorios presentes con '
                  'descriptores correctos (incluido fd_masks)',
        veredicto=v, analysis=det['analysis.json'], masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-A2: archivo obligatorio presente pero descriptor OMITIDO -> FAIL
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-A2')
    fd_omitido = fds.pop('analysis.json')   # el registro omite ese descriptor
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=fm)
    resultados['E1-A2'] = dict(
        situacion='analysis.json presente pero su descriptor fue omitido del '
                  'registro (el fd sigue abierto en el motor)',
        veredicto=v, analysis=det['analysis.json'])
    os.close(fd_omitido)
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-A3: archivo sustituido por otro regular con identidad distinta -> FAIL
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-A3')
    os.unlink('analysis.json', dir_fd=fr)
    fd_imp = os.open('analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                     | os.O_NOFOLLOW, 0o600, dir_fd=fr)  # impostor (misma uid)
    os.close(fd_imp)
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=fm)
    resultados['E1-A3'] = dict(
        situacion='analysis.json sustituido por otro regular con identidad '
                  'distinta (el descriptor del registro apunta al original)',
        veredicto=v, analysis=det['analysis.json'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-B1: masks presente y coincide con fd_masks -> PASS
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-B1')
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=fm)
    resultados['E1-B1'] = dict(
        situacion='masks presente (directorio real) y coincide con fd_masks',
        veredicto=v, masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-B2: masks sustituido por OTRO DIRECTORIO REAL con identidad distinta
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-B2')
    os.rmdir('masks', dir_fd=fr)          # el atacante (misma uid) sustituye
    os.mkdir('masks', 0o700, dir_fd=fr)   # nuevo inodo, mismo nombre
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=fm)  # fd_masks: inodo ORIGINAL
    resultados['E1-B2'] = dict(
        situacion='masks sustituido por otro directorio REAL con identidad '
                  'distinta (fd_masks conserva el inodo original)',
        veredicto=v, masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-B3: masks ausente y OPCIONAL -> PASS en esa dimensión
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-B3', con_masks=False)
    v, det = checklist_completitud(fr, fds, masks_obligatorio=False,
                                   fd_masks=None)
    resultados['E1-B3'] = dict(
        situacion='masks AUSENTE (real, sin simulación) en modo Hardened/EVO '
                  'sin masks', veredicto=v, masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-B4: masks ausente y OBLIGATORIO -> FAIL
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-B4', con_masks=False)
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=None)
    resultados['E1-B4'] = dict(
        situacion='masks AUSENTE (real, sin simulación) en modo MQR '
                  '(siempre obligatorio)', veredicto=v, masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    # E1-B5: masks presente como symlink -> FAIL
    an, r_x, fr, fds, fm = _dir_e1(work, 'E1-B5', masks_symlink=True)
    v, det = checklist_completitud(fr, fds, masks_obligatorio=True,
                                   fd_masks=None)
    v2, det2 = checklist_completitud(fr, fds, masks_obligatorio=False,
                                     fd_masks=None)
    resultados['E1-B5'] = dict(
        situacion='masks precolocado como symlink por el atacante (aun '
                  'opcional debe ser directorio real)',
        veredicto=v, veredicto_si_opcional=v2, masks=det['masks'])
    _cerrar_dir_e1(an, fr, fds, fm, r_x['raiz'])
    ok = (resultados['E1-A1']['veredicto'] == 'PASS'
          and resultados['E1-A1']['masks']['identidad_vs_fd'] is True
          and resultados['E1-A1']['analysis']['ok'] is True
          and resultados['E1-A2']['veredicto'] == 'FAIL'
          and resultados['E1-A2']['analysis']['ok'] is False
          and resultados['E1-A2']['analysis']['descriptor_presente'] is False
          and resultados['E1-A2']['analysis']['identidad_vs_fd'] is False
          and resultados['E1-A3']['veredicto'] == 'FAIL'
          and resultados['E1-A3']['analysis']['ok'] is False
          and resultados['E1-A3']['analysis']['identidad_vs_fd'] is False
          and resultados['E1-B1']['veredicto'] == 'PASS'
          and resultados['E1-B1']['masks']['identidad_vs_fd'] is True
          and resultados['E1-B2']['veredicto'] == 'FAIL'
          and resultados['E1-B2']['masks']['identidad_vs_fd'] is False
          and resultados['E1-B2']['masks']['tipo'] == 'directorio'
          and resultados['E1-B3']['veredicto'] == 'PASS'
          and resultados['E1-B3']['masks']['ok'] is True
          and resultados['E1-B3']['masks']['esperado'] == 'opcional'
          and resultados['E1-B4']['veredicto'] == 'FAIL'
          and resultados['E1-B4']['masks']['ok'] is False
          and resultados['E1-B4']['masks']['esperado'] == 'obligatorio'
          and resultados['E1-B5']['veredicto'] == 'FAIL'
          and resultados['E1-B5']['veredicto_si_opcional'] == 'FAIL'
          and resultados['E1-B5']['masks']['tipo'] == 'symlink')
    return nuevo(
        'E1', 'Guarda de completitud por descriptor: existencia, tipo, '
        'no-symlink e identidad vs fd de creación; RECTIFICACIÓN FINAL: '
        'descriptor ausente -> FAIL (sin PASS por defecto) e identidad del '
        'directorio masks vs fd_masks, con 8 escenarios independientes',
        'Que un artefacto obligatorio pase la guarda sin descriptor válido y '
        'coincidente (PASS por defecto), o que la identidad del directorio '
        'masks no se contraste con el descriptor del directorio acreditado.',
        ['comportamiento_rechazado_por_diseno'], resultados,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   matriz_motores=DIF_MOTOR,
                   nota='E1-A: item.get("identidad_vs_fd", True) ELIMINADO — '
                        'la ausencia del descriptor es FAIL (nunca PASS por '
                        'defecto); E1-B: masks presente exige (st_dev, '
                        'st_ino) == fstat(fd_masks) además de directorio real '
                        'y no symlink; masks opcional ausente sigue siendo '
                        'válido (E1-B3) y obligatorio ausente FAIL (E1-B4); '
                        'E1-B2 demuestra la detección de la sustitución por '
                        'OTRO DIRECTORIO REAL (nuevo inodo, mismo nombre) '
                        'gracias al contraste con fd_masks; ningún parámetro '
                        'desactiva comprobaciones: ausencias, sustituciones y '
                        'symlinks son reales en provisionales acreditados '
                        'independientes'))


# ---------------------------------------------------------------------------
# Hallazgo F — ciclo de vida de descriptores.
# ---------------------------------------------------------------------------

class RegistroFds:
    """Registro de ciclo de vida: cada descriptor se cierra EXACTAMENTE una
    vez; cierre en orden inverso de apertura; idempotente."""

    def __init__(self):
        self._pila = []          # (etiqueta, fd)
        self._cerrados = []
        self._cierres_duplicados = 0

    def registrar(self, etiqueta, fd):
        self._pila.append((etiqueta, fd))
        return fd

    def cerrar_todos(self):
        while self._pila:
            etiqueta, fd = self._pila.pop()
            try:
                os.fstat(fd)     # ¿sigue válido?
                os.close(fd)
                self._cerrados.append(etiqueta)
            except OSError:
                self._cierres_duplicados += 1
        return self._cerrados, self._cierres_duplicados


def escenario_f1(work, outdir):
    """F1: ciclo de vida — fd_candidates correctamente creado, descriptores
    de archivos individuales, fallo DESPUÉS de abrir varios recursos, cierre
    exacto en orden inverso, sin cierre prematuro y 0 residuales
    (rectificación Cris)."""
    def medir_fds():
        return sorted(int(x) for x in os.listdir('/proc/self/fd'))

    resultados = {}
    # (a) ciclo COMPLETO con éxito: fd_padre, fd_run, fd_masks y fd_candidates
    #     creados CORRECTAMENTE + tres descriptores de archivos individuales
    ancla, r = _estructura(work, 'F1a')
    antes = medir_fds()
    reg = RegistroFds()
    fd_padre = reg.registrar('fd_padre', ancla['fd_padre'])
    fd_run = reg.registrar('fd_run', os.open(
        ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=fd_padre))
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    reg.registrar('fd_masks', os.open(
        'masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=fd_run))
    os.mkdir('candidates', 0o700, dir_fd=fd_run)
    reg.registrar('fd_candidates', os.open(     # creado CORRECTAMENTE
        'candidates', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=fd_run))
    fd_wav = reg.registrar('wav', os.open(
        'mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600, dir_fd=fd_run))
    fd_json = reg.registrar('json', os.open(
        'analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600, dir_fd=fd_run))
    fd_log = reg.registrar('log', os.open(
        'engine_log.txt', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600, dir_fd=fd_run))
    # bibliotecas usando los objetos ANTES del cierre (sin cierre prematuro):
    # soundfile escribe el WAV; el escritor de JSON y el de log usan su DUP
    # (lo cierran ellos); el fd del MOTOR permanece válido después
    sf_write_wav_fd(fd_wav, datos_wav())
    with os.fdopen(os.dup(fd_json), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'F1a'}, f)
    with os.fdopen(os.dup(fd_log), 'w', encoding='utf-8') as f:
        f.write('[Motor] F1a\n')
    try:
        os.fstat(fd_log)
        fds_archivo_validos_tras_biblioteca = True
    except OSError:
        fds_archivo_validos_tras_biblioteca = False
    frames_antes = sf.read(proc(fd_wav), dtype='float64')[0].shape[0]
    cerrados, duplicados = reg.cerrar_todos()
    reg.cerrar_todos()   # segunda llamada: nada que cerrar (idempotente)
    despues = medir_fds()
    resultados['a_ciclo_completo'] = dict(
        recursos_registrados=['fd_padre', 'fd_run', 'fd_masks',
                              'fd_candidates', 'wav', 'json', 'log'],
        orden_cerrados=cerrados, cierres_duplicados=duplicados,
        frames_wav_antes_del_cierre=frames_antes,
        fds_archivo_validos_tras_biblioteca=fds_archivo_validos_tras_biblioteca,
        fds_residuales=[f for f in despues if f not in antes])
    limpiar(r['raiz'])
    # (b) fallo DESPUÉS de abrir VARIOS recursos: la creación exclusiva de
    #     'analysis.json' choca con un symlink precolocado por el atacante
    #     (FileExistsError, C5) -> el registro cierra lo abierto, 0 residuales
    ancla, r = _estructura(work, 'F1b')
    antes = medir_fds()
    reg = RegistroFds()
    reg.registrar('fd_padre', ancla['fd_padre'])
    fd_run = reg.registrar('fd_run', os.open(
        ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=ancla['fd_padre']))
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    reg.registrar('fd_masks', os.open(
        'masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd_run))
    os.mkdir('candidates', 0o700, dir_fd=fd_run)
    reg.registrar('fd_candidates', os.open(
        'candidates', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
        dir_fd=fd_run))
    reg.registrar('wav', os.open(
        'mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
        0o600, dir_fd=fd_run))
    os.symlink(os.path.join(r['raiz'], 'ajeno.json'), 'analysis.json',
               dir_fd=fd_run)     # atacante precoloca la entrada
    error = None
    try:
        reg.registrar('json', os.open(
            'analysis.json',
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW,
            0o600, dir_fd=fd_run))
    except OSError as exc:
        error = '%s (%s)' % (type(exc).__name__, exc)
        st_aj = os.stat('analysis.json', dir_fd=fd_run,
                        follow_symlinks=False)
        cerrados, dup = reg.cerrar_todos()
    despues = medir_fds()
    resultados['b_fallo_tras_varios_recursos'] = dict(
        recursos_abiertos_al_fallar=5,
        error=error, cerrados=cerrados,
        symlink_precolocado_conservado=bool(stat.S_ISLNK(st_aj.st_mode)),
        fds_residuales=[f for f in despues if f not in antes])
    ok = (not resultados['a_ciclo_completo']['fds_residuales']
          and resultados['a_ciclo_completo']['cierres_duplicados'] == 0
          and resultados['a_ciclo_completo']['orden_cerrados'] ==
          ['log', 'json', 'wav', 'fd_candidates', 'fd_masks', 'fd_run',
           'fd_padre']
          and resultados['a_ciclo_completo']['frames_wav_antes_del_cierre']
          == SR
          and resultados['a_ciclo_completo']
          ['fds_archivo_validos_tras_biblioteca']
          and not resultados['b_fallo_tras_varios_recursos']['fds_residuales']
          and resultados['b_fallo_tras_varios_recursos']['error']
          .startswith('FileExistsError')
          and resultados['b_fallo_tras_varios_recursos']['cerrados'] ==
          ['wav', 'fd_candidates', 'fd_masks', 'fd_run', 'fd_padre']
          and resultados['b_fallo_tras_varios_recursos']
          ['symlink_precolocado_conservado'])
    limpiar(r['raiz'])
    return nuevo(
        'F1', 'Ciclo de vida de descriptores: fd_candidates creado '
        'correctamente, descriptores de archivos individuales, fallo después '
        'de abrir varios recursos, cierre EXACTO en orden inverso, sin '
        'cierre prematuro y 0 residuales',
        'Que queden descriptores residuales, se cierren dos veces, se '
        'cierren en orden incorrecto, se cierren mientras una biblioteca los '
        'usa, o que un fallo tardío deje recursos abiertos.',
        ['comportamiento_permitido_por_diseno'], resultados,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   demostrado_por_prototipo='fd_candidates creado '
                   '(mkdir+openat) y cerrado en posición correcta; 3 fds de '
                   'archivo individuales (wav/json/log); fallo tras abrir '
                   'CINCO recursos con cierre completo de los mismos; orden '
                   'inverso exacto (archivos -> fd_candidates -> fd_masks -> '
                   'fd_run -> fd_padre); sin cierre prematuro (la biblioteca '
                   'usa su dup y el fd del motor queda válido después; el '
                   'WAV conserva sus frames antes del cierre); 0 residuales '
                   'medidos por /proc/self/fd',
                   pendiente_de_integracion_en_motores='el ciclo REAL de los '
                   'motores NO queda validado aquí: la integración exige que '
                   'cada motor registre sus descriptores en este registro en '
                   'sus tres caminos (éxito/excepción/interrupción) junto a '
                   'preparar_aborto_6g1 (cerrar_recursos_corrida_6g1 '
                   'ampliado) y el cierre acreditado normal; se validará con '
                   'RG-FLOW por motor (pendiente de autorización)'))


# ---------------------------------------------------------------------------
# Hallazgo G — evidencia forense de publicación.
# ---------------------------------------------------------------------------

def sha_archivo_via_fd(fd):
    os.lseek(fd, 0, os.SEEK_SET) if hasattr(os, 'lseek') else None
    try:
        with open(proc(fd), 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except OSError:
        return None


def sha_archivo_por_ruta(p):
    with open(p, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


_MAPA_ARTEFACTOS = dict(mix_sdv='mix SDV.wav', analysis='analysis.json')


def _publicar_con_registro(work, etiqueta):
    """Provisional acreditado con artefactos + registro forense escrito por
    fd_run ANTES de publicar + publicación (el registro viaja con el inodo)."""
    ancla, r = _estructura(work, etiqueta)
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    fd_wav = os.open('mix SDV.wav', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                     | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    fd_json = os.open('analysis.json', os.O_CREAT | os.O_EXCL | os.O_WRONLY
                      | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    sf_write_wav_fd(fd_wav, datos_wav())
    with os.fdopen(os.dup(fd_json), 'w', encoding='utf-8') as f:
        json.dump({'caso': etiqueta}, f)
    hashes = dict(mix_sdv=sha_archivo_via_fd(fd_wav),
                  analysis=sha_archivo_via_fd(fd_json))
    os.close(fd_wav)
    os.close(fd_json)
    registro = dict(
        schema='publicacion-6g1/1',
        ts=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        provisional=dict(dev=ancla['identidad']['dev'],
                         ino=ancla['identidad']['ino']),
        padre=dict(dev=ancla['identidad_padre']['dev'],
                   ino=ancla['identidad_padre']['ino']),
        destino_solicitado='run_final',
        artefactos=hashes,
        politica='el inodo del provisional se conserva en el renombrado: '
                 'lstat(dir publicado) debe == provisional.ino; los SHA-256 '
                 'permiten verificar la integridad del CONTENIDO publicado')
    fd_reg = os.open('publicacion_6g1.json', os.O_CREAT | os.O_EXCL
                     | os.O_WRONLY | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
    os.write(fd_reg, json.dumps(registro, indent=1).encode('utf-8'))
    os.close(fd_reg)
    res = publicar_anclada(ancla, 'run_final')
    publicado = os.path.join(r['base'], res['destino'])
    return dict(ancla=ancla, r=r, fd_run=fd_run, registro=registro, res=res,
                publicado=publicado)


def _auditar_integridad(ctx):
    """Auditoría EXTERNA de integridad: lee el registro del directorio
    publicado, RECALCULA los SHA-256 de los artefactos publicados por ruta y
    los compara con los almacenados; contrasta además el inodo publicado con
    el registrado (coherencia, NO autenticidad)."""
    publicado = ctx['publicado']
    rec = json.load(open(os.path.join(publicado, 'publicacion_6g1.json'),
                         encoding='utf-8'))
    recalculados, comparacion = {}, {}
    for clave, nombre in _MAPA_ARTEFACTOS.items():
        sha_r = sha_archivo_por_ruta(os.path.join(publicado, nombre))
        recalculados[clave] = sha_r
        comparacion[clave] = dict(
            almacenado=rec['artefactos'][clave], recalculado=sha_r,
            coincide=sha_r == rec['artefactos'][clave])
    st_ext = os.lstat(publicado)
    return dict(
        registro_leido_del_publicado=True,
        sha_recalculados=recalculados,
        comparacion=comparacion,
        integridad_coincide=all(c['coincide']
                                for c in comparacion.values()),
        ino_publicado=st_ext.st_ino,
        ino_en_registro=rec['provisional']['ino'],
        inodo_coincide=st_ext.st_ino == rec['provisional']['ino'],
        contenido_publicado=sorted(os.listdir(publicado)),
        alcance=dict(
            artefactos_verificados=sorted(_MAPA_ARTEFACTOS.values()),
            cobertura='demostración DELIMITADA del mecanismo de comparación '
                      'SHA-256; NO constituye la verificación de TODOS los '
                      'artefactos de producción (exige la matriz real de '
                      'artefactos por motor y modo, hallazgo E)'))


def escenario_g1(work, outdir):
    """G1: evidencia forense — registro ANTES de publicar (viaja con el
    inodo); verificación EFECTIVA de integridad: publicar -> leer registro ->
    recalcular SHA-256 publicados -> comparar -> PASS al coincidir; escenario
    INDEPENDIENTE con alteración deliberada -> la auditoría detecta la
    discrepancia; el registro NO es inmutable frente a la misma uid
    (rectificación Cris)."""
    resultados = {}
    # (a) ciclo completo: publicar -> leer registro -> recalcular -> comparar
    ctx = _publicar_con_registro(work, 'G1a')
    st_final = fstatat_nofollow(ctx['ancla']['fd_padre'],
                                ctx['res']['destino'])
    b2 = dict(coincide=bool(st_final)
              and (st_final.st_dev, st_final.st_ino)
              == (ctx['ancla']['identidad']['dev'],
                  ctx['ancla']['identidad']['ino']))
    aud = _auditar_integridad(ctx)
    resultados['a_publicar_leer_recalcular_comparar'] = dict(
        publicacion=dict(exito=ctx['res']['exito'],
                         destino=ctx['res']['destino']),
        reverificacion_b2=b2,
        auditoria_integridad=aud,
        veredicto_auditoria='PASS' if (aud['integridad_coincide']
                                       and aud['inodo_coincide'])
        else 'FAIL')
    # (b) escenario INDEPENDIENTE: alterar deliberadamente un artefacto
    #     publicado (misma uid, post-publicación: residual declarado) ->
    #     la auditoría DETECTA la discrepancia
    ctx2 = _publicar_con_registro(work, 'G1b')
    with open(os.path.join(ctx2['publicado'], 'analysis.json'), 'ab') as f:
        f.write(b'\nALTERACION DELIBERADA POST-PUBLICACION\n')
    aud2 = _auditar_integridad(ctx2)
    resultados['b_alteracion_detectada'] = dict(
        alteracion_aplicada='analysis.json publicado: bytes añadidos '
                            'post-publicación (misma uid)',
        auditoria_integridad=aud2,
        veredicto_auditoria=('DISCREPANCIA_DETECTADA'
                             if not aud2['integridad_coincide']
                             else 'PASS (INESPERADO)'),
        detalle_discrepancia={k: v['coincide']
                              for k, v in aud2['comparacion'].items()})
    # alcance documental DELIMITADO (rectificación final Cris, punto 3):
    # la auditoría demuestra el mecanismo SHA-256 sobre los artefactos del
    # registro; NO se afirma la verificación de TODOS los artefactos de
    # producción ni se amplía la prueba sin la matriz real por motor/modo
    resultados['alcance_documental'] = dict(
        artefactos_con_sha_verificado=sorted(_MAPA_ARTEFACTOS.values()),
        declaracion='ALCANCE DELIMITADO: los resultados SHA-256 aceptados '
                    'corresponden a mix SDV.wav y analysis.json; NO se '
                    'afirma que se hayan verificado TODOS los artefactos de '
                    'producción; ampliar la prueba a otros ficheros exige '
                    'definir antes la matriz real de artefactos por motor y '
                    'modo (hallazgo E)')
    # (c) el registro NO es inmutable frente a la misma uid (declaración
    #     mantenida; sin garantías de autenticidad)
    ruta_reg = os.path.join(ctx2['publicado'], 'publicacion_6g1.json')
    rec3 = json.load(open(ruta_reg, encoding='utf-8'))
    with open(ruta_reg, 'w', encoding='utf-8') as f:
        rec3['provisional']['ino'] = 1
        json.dump(rec3, f)
    reescribiendo = json.load(open(ruta_reg,
                                   encoding='utf-8'))['provisional']['ino'] == 1
    resultados['c_registro_no_inmutable'] = dict(
        misma_uid_reescribio_registro=reescribiendo,
        declaracion='el registro es evidencia de auditoría con coherencia '
                    'verificable (inodo-vs-registro, SHA-256-vs-publicado); '
                    'NO es inmutable frente a la misma uid (demostrado) y NO '
                    'posee garantías de autenticidad; es fiable frente a '
                    'otra uid (0700 del euid)')
    for ctx_x in (ctx, ctx2):
        os.close(ctx_x['fd_run'])
        os.close(ctx_x['ancla']['fd_padre'])
    ok = (resultados['a_publicar_leer_recalcular_comparar']
          ['publicacion']['exito']
          and b2['coincide']
          and resultados['a_publicar_leer_recalcular_comparar']
          ['veredicto_auditoria'] == 'PASS'
          and resultados['b_alteracion_detectada']['veredicto_auditoria']
          == 'DISCREPANCIA_DETECTADA'
          and reescribiendo)
    limpiar(ctx['r']['raiz'])
    limpiar(ctx2['r']['raiz'])
    return nuevo(
        'G1', 'Evidencia forense de publicación con verificación EFECTIVA de '
        'integridad: registro escrito por fd_run ANTES del renombrado (viaja '
        'con el inodo), auditoría externa que RECALCULA los SHA-256 de los '
        'artefactos publicados y compara, detección de alteración '
        'deliberada, y límite frente a la misma uid',
        'Que el registro no pertenezca a la corrida acreditada, que una '
        'alteración del contenido publicado pase inadvertida, o presentar '
        'como inmutable/auténtico un registro modificable por la misma uid.',
        ['comportamiento_permitido_por_diseno',
         'limitacion_declarada_evidencia_frente_a_misma_uid'], resultados,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   registro_en_aborto='ante aborto, el registro forense es '
                                      'ABORT_6G1.json (D2), escrito por '
                                      'fd_run dentro del acreditado; el '
                                      'registro de publicación no existe '
                                      'si no hubo publicación',
                   proteccion_real='otra uid no puede escribir en el '
                                   'acreditado (0700 del euid): el registro '
                                   'es fiable frente a otra uid; frente a la '
                                   'MISMA uid es TAMPERABLE (demostrado) -> '
                                   'evidencia de auditoría con coherencia '
                                   'verificable (inodo-vs-registro, '
                                   'SHA-256-vs-publicado), SIN garantías de '
                                   'autenticidad ni inmutabilidad; la '
                                   'detección de discrepancias no identifica '
                                   'al autor ni impide la alteración'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='/tmp/cdefg_6g1')
    ap.add_argument('--out', default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'evidence', 'prototipo_hallazgos_cdefg_6g1'))
    args = ap.parse_args()
    os.makedirs(args.work, 0o700, exist_ok=True)
    os.makedirs(args.out, 0o755, exist_ok=True)
    esc = [escenario_c1_c4, escenario_c5, escenario_c6, escenario_d1,
           escenario_d2, escenario_e1, escenario_f1, escenario_g1]
    resultados = []
    for fn in esc:
        print('=== %s ===' % fn.__name__.replace('escenario_', '').upper(),
              flush=True)
        r = fn(args.work, args.out)
        nombre = r['escenario'].lower().replace('-', '_')
        p = os.path.join(args.out, 'escenario_%s.json' % nombre)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=1, ensure_ascii=False, sort_keys=True)
        print('  ->', p, '| veredicto:', r.get('veredicto', '?'), flush=True)
        resultados.append(dict(escenario=r['escenario'],
                               veredicto=r.get('veredicto'),
                               clasificacion=r['clasificacion'],
                               fichero=os.path.basename(p)))
    con = dict(schema=SCHEMA,
               generado=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               entorno=dict(python='.'.join(map(str, sys.version_info[:3])),
                            numpy=np.__version__, soundfile=sf.__version__,
                            libsndfile=sf.__libsndfile_version__,
                            euid=os.geteuid()),
               escenarios=resultados)
    with open(os.path.join(args.out, 'consolidado_prototipo_cdefg.json'),
              'w', encoding='utf-8') as f:
        json.dump(con, f, indent=1, ensure_ascii=False)
    print('consolidado:', os.path.join(args.out,
                                       'consolidado_prototipo_cdefg.json'))


if __name__ == '__main__':
    main()
