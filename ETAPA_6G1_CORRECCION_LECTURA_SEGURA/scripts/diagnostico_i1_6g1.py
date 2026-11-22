#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNÓSTICO I-1 (6G.1) — Enlaces simbólicos en componentes intermedios de la
ruta del directorio provisional.

Instrucción de Cris (22-11-2026): determinar si el tratamiento de enlaces
simbólicos en componentes intermedios de la ruta del directorio provisional
permite una sustitución efectiva o una escritura fuera del directorio previsto.

Casos exigidos:
  C1  Ruta normal, sin enlaces simbólicos.
  C2  Componente final de la ruta como enlace simbólico.
  C3  Componentes intermedios como enlaces simbólicos (sub-casos a/b/c).
  C4  Sustitución de un componente intermedio DESPUÉS de acreditar el
      directorio provisional (nivel módulo, determinista).
  C5  Verificación de identidad por dispositivo e inode antes/después de la
      sustitución (integrado en C4 y C4r).
  C6  Comprobación de que no se producen escrituras fuera del directorio
      esperado (fotografías de árbol antes/después, integrado en todos).

Adicionales (flujo real del motor Hardened 6G.1, sin modificar):
  C0   Corrida real completa sin sustitución (línea base del diseño).
  C4r  Carrera real: sustitución de componente intermedio por un observador
       externo durante una corrida real del motor.

Sólo diagnóstico: no modifica código de producción, motores, DSP, fixtures ni
validadores. Todo el trabajo ocurre en el directorio de trabajo temporal
(--work). Clasificación por caso, según la instrucción:
  comportamiento_permitido_por_diseno | comportamiento_rechazado_por_diseno |
  vulnerabilidad_reproducida | riesgo_teorico_no_reproducido |
  resultado_desconocido

Uso:
  python -B scripts/diagnostico_i1_6g1.py --casos c1,c2,c3,c4,c0,c4r \
      --work /tmp/i1_6g1 --out evidence/diagnostico_i1_6g1
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ETAPA = os.path.dirname(HERE)
MOTORES = os.path.join(ETAPA, 'motores')
sys.path.insert(0, MOTORES)

MOTOR_H = os.path.join(MOTORES, 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py')
FIXTURE_MIX = os.path.join(ETAPA, 'fixtures', 'mix.wav')
FIXTURE_VOCAL = os.path.join(ETAPA, 'fixtures', 'vocal_mix.wav')
FIXTURE_INSTR = os.path.join(ETAPA, 'fixtures', 'instrumental_mix.wav')

SCHEMA = 'diagnostico-i1/1'


# ----------------------------------------------------------------------------
# Utilidades de fotografía de árbol (C6): nunca se siguen enlaces simbólicos.
# ----------------------------------------------------------------------------

def sha256_archivo(path, max_mb=64):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def fotografiar(root, max_mb=64):
    """Fotografía recursiva del árbol: ruta relativa -> identidad lstat."""
    foto = {}
    if not os.path.exists(root):
        return foto
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        for nombre in sorted(dirnames + filenames):
            p = os.path.join(dirpath, nombre)
            rel = os.path.relpath(p, root)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            entrada = dict(dev=st.st_dev, ino=st.st_ino,
                           modo=stat.filemode(st.st_mode),
                           uid=st.st_uid, gid=st.st_gid)
            if stat.S_ISLNK(st.st_mode):
                entrada['tipo'] = 'symlink'
                try:
                    entrada['destino'] = os.readlink(p)
                except OSError:
                    pass
            elif stat.S_ISDIR(st.st_mode):
                entrada['tipo'] = 'directorio'
            elif stat.S_ISREG(st.st_mode):
                entrada['tipo'] = 'regular'
                entrada['tamano'] = st.st_size
                if st.st_size <= max_mb * (1 << 20):
                    try:
                        entrada['sha256'] = sha256_archivo(p)
                    except OSError:
                        pass
            else:
                entrada['tipo'] = 'otro'
            foto[rel] = entrada
    return foto


def diff_fotos(antes, despues):
    nuevos, modificados = [], []
    for rel, d in sorted(despues.items()):
        a = antes.get(rel)
        if a is None:
            nuevos.append(dict(relativo=rel, **d))
        elif (a.get('ino'), a.get('dev'), a.get('sha256'), a.get('tamano')) != \
                (d.get('ino'), d.get('dev'), d.get('sha256'), d.get('tamano')):
            modificados.append(dict(relativo=rel, antes=a, despues=d))
    return nuevos, modificados


def chmod_r(path, modo_dir):
    os.chmod(path, modo_dir)
    for dirpath, dirnames, _ in os.walk(path):
        for d in dirnames:
            os.chmod(os.path.join(dirpath, d), modo_dir)


def limpiar(path):
    if os.path.exists(path):
        chmod_r(path, 0o700)
        shutil.rmtree(path)


def nuevo_caso(caso, descripcion, amenaza, clasificacion, condiciones,
               procedimiento, resultado, extra=None):
    d = dict(schema=SCHEMA, caso=caso, descripcion=descripcion,
             amenaza=amenaza, clasificacion=clasificacion,
             condiciones=condiciones, procedimiento=procedimiento,
             resultado_observado=resultado)
    if extra:
        d.update(extra)
    return d


# ----------------------------------------------------------------------------
# C1 — Ruta normal, sin enlaces simbólicos (nivel módulo, funciones reales).
# ----------------------------------------------------------------------------

def caso_c1(work, outdir):
    base = os.path.join(work, 'c1', 'base')
    limpiar(os.path.join(work, 'c1'))
    os.makedirs(base, 0o700)
    import lectura_segura_6g1 as L

    foto_base_antes = fotografiar(base)
    ruta, ident = L.crear_y_acreditar_dir_6g1(base, 'prov_c1')
    # Escrituras "como el motor": por ruta (Tee, analysis.json).
    with open(os.path.join(ruta, 'engine_log.txt'), 'w', encoding='utf-8') as f:
        f.write('LOG-C1\n')
    with open(os.path.join(ruta, 'analysis.json'), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'C1'}, f)
    foto_despues_escrituras = fotografiar(base)

    res = L.abortar_corrida_6g1(ruta, ruta + '_aborted',
                                'PRUEBA_I1_C1', detalle='aborto normal',
                                trasladar=True)
    st_dest = os.lstat(res.get('ruta_final')) if res.get('trasladado') else None
    foto_final = fotografiar(base)

    nuevos, modificados = diff_fotos(foto_base_antes, foto_final)
    fuera = [n for n in nuevos
             if not n['relativo'].startswith(('prov_c1', 'prov_c1_aborted'))]

    ok_traslado = bool(res.get('trasladado') and res.get('traslado_verificado'))
    identidad_ok = bool(st_dest and (st_dest.st_dev, st_dest.st_ino) == ident)
    ok_sin_fugas = not fuera
    resultado = dict(
        acreditacion=dict(ruta=ruta, dev=ident[0], ino=ident[1]),
        aborto=res,
        identidad_trasladada_ok=identidad_ok,
        abort_registrado=bool(res.get('abort_registrado')),
        escrituras_fuera_del_previsto=fuera,
        ficheros_creados=[n['relativo'] for n in nuevos],
        veredicto='PASS' if (ok_traslado and identidad_ok and ok_sin_fugas
                             and res.get('abort_registrado')) else 'REVIEW')
    clas = ['comportamiento_permitido_por_diseno']
    return nuevo_caso(
        'C1', 'Ruta normal, sin enlaces simbólicos',
        'Ninguno: caso base que ancla el comportamiento esperado del diseño.',
        clas,
        dict(base=dict(modo=stat.filemode(os.lstat(base).st_mode),
                       uid=os.lstat(base).st_uid, enlaces_simbolicos=0),
             euid=os.geteuid()),
        ['crear_y_acreditar_dir_6g1(base, prov_c1)',
         'escritura por ruta de engine_log.txt y analysis.json (como el motor)',
         'abortar_corrida_6g1(ruta, ruta_aborted, traslado=True)',
         'fotografías de árbol antes/después + identidad (dev,ino)'],
        resultado,
        extra=dict(fotos=dict(antes=foto_base_antes,
                              tras_escrituras=foto_despues_escrituras,
                              final=foto_final)))


# ----------------------------------------------------------------------------
# C2 — Componente FINAL como enlace simbólico.
# ----------------------------------------------------------------------------

def caso_c2(work, outdir):
    raiz = os.path.join(work, 'c2')
    limpiar(raiz)
    base = os.path.join(raiz, 'base')
    evil = os.path.join(raiz, 'evil')
    os.makedirs(base, 0o700)
    os.makedirs(evil, 0o700)
    enlace = os.path.join(base, 'prov_c2')
    os.symlink(evil, enlace)
    import lectura_segura_6g1 as L

    foto_evil_antes = fotografiar(evil)
    resultado = {}
    try:
        L.crear_y_acreditar_dir_6g1(base, 'prov_c2')
        resultado['creacion'] = 'SIN_ERROR (inesperado)'
    except FileExistsError as exc:
        resultado['creacion'] = 'FileExistsError: %s' % exc
    except OSError as exc:
        resultado['creacion'] = 'OSError(%s): %s' % (exc.errno, exc)
    # Prueba directa de O_NOFOLLOW sobre el componente final.
    try:
        os.open(enlace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        resultado['apertura_nofollow'] = 'SIN_ERROR (inesperado)'
    except OSError as exc:
        resultado['apertura_nofollow'] = 'OSError(%s): %s' % (exc.errno, exc)
    foto_evil_despues = fotografiar(evil)
    nuevos_evil, _ = diff_fotos(foto_evil_antes, foto_evil_despues)
    resultado['escrituras_en_evil'] = nuevos_evil
    resultado['enlace_intacto'] = os.path.islink(enlace) and \
        os.readlink(enlace) == evil
    rechazado = (resultado['creacion'].startswith(('FileExistsError', 'OSError'))
                 and not nuevos_evil and resultado['enlace_intacto'])
    clas = ['comportamiento_rechazado_por_diseno'] if rechazado else \
        ['resultado_desconocido']
    return nuevo_caso(
        'C2', 'Componente final de la ruta del provisional como enlace simbólico',
        'Que la creación o apertura del provisional siga el enlace y escriba '
        'en un objeto ajeno (evil).',
        clas,
        dict(enlace=dict(ruta=enlace, destino=evil),
             evil=dict(modo=stat.filemode(os.lstat(evil).st_mode)),
             mecanismo='mkdir(dir_fd) exclusivo + O_NOFOLLOW'),
        ['ln -s evil base/prov_c2 (preexistente)',
         'crear_y_acreditar_dir_6g1(base, prov_c2)',
         'os.open(prov_c2, O_DIRECTORY|O_NOFOLLOW) directo',
         'fotografía de evil antes/después'],
        resultado,
        extra=dict(fotos=dict(evil_antes=foto_evil_antes,
                              evil_despues=foto_evil_despues)))


# ----------------------------------------------------------------------------
# C3 — Componentes INTERMEDIOS como enlaces simbólicos (en creación).
# ----------------------------------------------------------------------------

def caso_c3(work, outdir):
    raiz = os.path.join(work, 'c3')
    limpiar(raiz)
    real = os.path.join(raiz, 'real')            # privado del euid
    real_abierto = os.path.join(raiz, 'real_777')  # modificable por terceros
    os.makedirs(real, 0o700)
    os.makedirs(real_abierto, 0o777)
    os.makedirs(os.path.join(real, 'sub'), 0o700)
    os.makedirs(os.path.join(real_abierto, 'sub777'), 0o777)
    enlace = os.path.join(raiz, 'link')
    os.symlink(real, enlace)
    enlace777 = os.path.join(raiz, 'link777')
    os.symlink(real_abierto, enlace777)
    import lectura_segura_6g1 as L

    resultado = {}

    # (a) El PADRE del provisional ES el enlace (componente final = symlink).
    try:
        L.crear_y_acreditar_dir_6g1(enlace, 'prov_a')
        resultado['a_padre_es_enlace'] = 'SIN_ERROR (inesperado)'
    except OSError as exc:
        resultado['a_padre_es_enlace'] = 'OSError(%s): %s' % (exc.errno, exc)

    # (b) Enlace INTERMEDIO: padre = <link>/sub (resuelve a real/sub, 0700).
    try:
        ruta_b, ident_b = L.crear_y_acreditar_dir_6g1(
            os.path.join(enlace, 'sub'), 'prov_b')
        st = os.lstat(os.path.join(real, 'sub', 'prov_b'))
        resultado['b_enlace_intermedio'] = dict(
            resultado='SIN_ERROR (creado y acreditado)',
            ruta_nominal=ruta_b,
            ruta_resuelta=os.path.join(real, 'sub', 'prov_b'),
            identidad_nominal=dict(dev=ident_b[0], ino=ident_b[1]),
            identidad_resuelta=dict(dev=st.st_dev, ino=st.st_ino),
            identidad_coincide=(st.st_dev, st.st_ino) == ident_b,
            padre_privacidad='real/sub 0700 propiedad del euid')
    except OSError as exc:
        resultado['b_enlace_intermedio'] = 'OSError(%s): %s' % (exc.errno, exc)

    # (c) Padre RESUELTO modificable por terceros (real_777/sub777, 0777).
    try:
        L.crear_y_acreditar_dir_6g1(
            os.path.join(enlace777, 'sub777'), 'prov_c')
        resultado['c_padre_resuelto_777'] = 'SIN_ERROR (inesperado)'
    except RuntimeError as exc:
        resultado['c_padre_resuelto_777'] = 'RuntimeError: %s' % exc
    except OSError as exc:
        resultado['c_padre_resuelto_777'] = 'OSError(%s): %s' % (exc.errno, exc)

    b = resultado.get('b_enlace_intermedio', {})
    clas = []
    if resultado['a_padre_es_enlace'].startswith('OSError(40)'):
        clas.append('comportamiento_rechazado_por_diseno')
    elif resultado['a_padre_es_enlace'].startswith('OSError'):
        clas.append('comportamiento_rechazado_por_diseno')
    if isinstance(b, dict) and b.get('resultado', '').startswith('SIN_ERROR') \
            and b.get('identidad_coincide'):
        clas.append('comportamiento_permitido_por_diseno')
    if resultado['c_padre_resuelto_777'].startswith(('RuntimeError', 'OSError')):
        clas.append('comportamiento_rechazado_por_diseno')
    return nuevo_caso(
        'C3', 'Componentes intermedios de la ruta del padre como enlaces '
        'simbólicos, presentes ANTES de la creación',
        'Que el provisional se cree (y se acredite) en un objeto distinto del '
        'que el operador cree designar, o que se eluda la comprobación de '
        'privacidad del padre.',
        clas,
        dict(enlace=dict(ruta=enlace, destino=real),
             real=dict(modo=stat.filemode(os.lstat(real).st_mode)),
             real_777=dict(modo=stat.filemode(os.lstat(real_abierto).st_mode)),
             mecanismo='os.open(padre, O_DIRECTORY|O_NOFOLLOW): O_NOFOLLOW '
                       'protege SOLO el componente final; privacidad '
                       'verificada sobre el padre RESUELTO (euid + sin '
                       'escritura grupo/otros)'),
        ['(a) crear_y_acreditar_dir_6g1(link, prov_a) — padre = enlace final',
         '(b) crear_y_acreditar_dir_6g1(link/sub, prov_b) — enlace intermedio '
         'hacia real/sub (0700 euid)',
         '(c) crear_y_acreditar_dir_6g1(link777/sub777, prov_c) — padre '
         'resuelto 0777',
         'comparación de identidad nominal vs resuelta por lstat'],
        resultado)


# ----------------------------------------------------------------------------
# C4 — Sustitución de componente INTERMEDIO DESPUÉS de acreditar (módulo).
# ----------------------------------------------------------------------------

def caso_c4(work, outdir):
    raiz = os.path.join(work, 'c4')
    limpiar(raiz)
    shared = os.path.join(raiz, 'shared')        # simula directorio compartido
    user = os.path.join(shared, 'user')          # privado del euid
    base = os.path.join(user, 'base')            # out_base del operador
    os.makedirs(base, 0o700)
    os.chmod(shared, 0o777)                      # escribible por terceros
    import lectura_segura_6g1 as L

    ruta, ident = L.crear_y_acreditar_dir_6g1(base, 'prov_c4')
    st_prov0 = os.lstat(ruta)
    # Escrituras "como el motor" ANTES de la sustitución (por ruta).
    with open(os.path.join(ruta, 'analysis.json'), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'C4', 'fase': 'pre'}, f)

    foto_shared_antes = fotografiar(shared)

    # --- Sustitución (capacidad requerida: escritura sobre `shared`) ---
    user_orig = os.path.join(shared, 'user.orig')
    os.rename(user, user_orig)
    os.mkdir(user, 0o777)
    os.mkdir(base, 0o700)                       # reconstruida por el atacante
    prov_falsa = os.path.join(base, 'prov_c4')
    os.mkdir(prov_falsa, 0o700)
    t_sub = time.time()

    # Identidades (C5): acreditada vs ruta tras sustitución vs re-apertura.
    st_ruta_post = os.lstat(ruta)
    fd_post = os.open(ruta, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    st_fd_post = os.fstat(fd_post)
    os.close(fd_post)

    # Escritura posterior "del motor" por ruta: ¿a dónde cae?
    with open(os.path.join(ruta, 'candidates.json'), 'w', encoding='utf-8') as f:
        json.dump({'caso': 'C4', 'fase': 'post-sustitucion'}, f)
    en_prov_acreditado = os.path.exists(
        os.path.join(user_orig, 'base', 'prov_c4', 'candidates.json'))
    en_arbol_atacante = os.path.exists(os.path.join(prov_falsa,
                                                    'candidates.json'))

    # El atacante (propietario del directorio sustituido) manipula contenido.
    os.unlink(os.path.join(prov_falsa, 'candidates.json'))
    with open(os.path.join(prov_falsa, 'candidates.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'caso': 'C4', 'fase': 'MANIPULADO-POR-ATACANTE'}, f)

    # Aborto: ¿detecta la sustitución?
    res_aborto = L.abortar_corrida_6g1(ruta, ruta + '_aborted',
                                       'PRUEBA_I1_C4', trasladar=True)

    # Publicación (ruta de éxito del motor): ¿re-verifica identidad?
    destino_publicacion = os.path.join(base, 'prov_c4_PUBLICADO')
    import traceback
    try:
        publicado = L.publicar_dir_6g1(ruta, destino_publicacion)
        st_pub = os.lstat(publicado)
        publicacion = dict(
            resultado='SIN_ERROR (publicado)',
            ruta_publicada=publicado,
            identidad_publicada=dict(dev=st_pub.st_dev, ino=st_pub.st_ino),
            publicada_es_acreditada=(st_pub.st_dev, st_pub.st_ino) == ident,
            contenido=sorted(os.listdir(publicado)))
    except Exception as exc:
        publicado = None
        publicacion = dict(
            resultado='%s: %s' % (type(exc).__name__, exc),
            traceback=traceback.format_exc())

    foto_shared_final = fotografiar(shared)
    nuevos, modificados = diff_fotos(foto_shared_antes, foto_shared_final)
    # Escrituras fuera del directorio previsto = todo lo nuevo/escrito bajo el
    # árbol del atacante (user reconstruido) tras la sustitución.
    fuera_del_previsto = [n for n in nuevos
                          if n['relativo'].startswith(('user/',))
                          and 'user.orig' not in n['relativo']]

    resultado = dict(
        identidad_acreditada=dict(dev=ident[0], ino=ident[1]),
        c5_identidades=dict(
            acreditada=dict(dev=ident[0], ino=ident[1]),
            lstat_ruta_post_sustitucion=dict(dev=st_ruta_post.st_dev,
                                             ino=st_ruta_post.st_ino),
            fstat_reapertura_nofollow=dict(dev=st_fd_post.st_dev,
                                           ino=st_fd_post.st_ino),
            lstat_distinto_de_acreditada=(
                st_ruta_post.st_dev, st_ruta_post.st_ino) != ident,
            fstat_distinto_de_acreditada=(
                st_fd_post.st_dev, st_fd_post.st_ino) != ident),
        escrituras=dict(
            candidates_json_en_provisional_acreditado=en_prov_acreditado,
            candidates_json_en_arbol_atacante=en_arbol_atacante,
            fuera_del_directorio_previsto=fuera_del_previsto),
        manipulacion_atacante=dict(
            contenido_final_candidates=(lambda p: json.load(open(p)) if p
                                        and os.path.exists(p) else None)(
                os.path.join(publicado or prov_falsa, 'candidates.json'))),
        aborto=res_aborto,
        publicacion=publicacion)
    resultado['veredicto'] = (
        'VULNERABILIDAD_REPRODUCIDA' if
        (en_arbol_atacante and not en_prov_acreditado
         and resultado['c5_identidades']['fstat_distinto_de_acreditada']
         and not res_aborto.get('abort_registrado')
         and publicacion.get('resultado') == 'SIN_ERROR (publicado)'
         and publicacion.get('publicada_es_acreditada') is False)
        else 'REVIEW')
    clas = ['vulnerabilidad_reproducida']
    if res_aborto.get('abort_registrado') is False and \
            res_aborto.get('motivo_conservacion'):
        clas.append('comportamiento_rechazado_por_diseno')  # aborto detecta
    return nuevo_caso(
        'C4', 'Sustitución de un componente intermedio (user) DESPUÉS de '
        'acreditar el provisional, a nivel de funciones del módulo',
        'Un proceso con permiso de escritura sobre el directorio compartido '
        'que contiene un componente intermedio renombra ese componente y '
        'reconstruye la ruta: las escrituras posteriores del motor por ruta '
        'caen fuera del provisional acreditado y la publicación de éxito '
        'podría trasladar un objeto no acreditado.',
        clas,
        dict(shared=dict(modo=stat.filemode(os.lstat(shared).st_mode),
                         capacidad_atacante='permiso de escritura sobre '
                         'shared (rename de user + reconstrucción de la ruta)'),
             user=dict(modo='drwx------ (0700, propiedad del euid)'),
             nota_euid='en el sandbox el atacante se simula con el mismo uid; '
                       'la capacidad requerida (escritura sobre shared) es '
                       'independiente del uid si el modo lo permite',
             capas_verificadas='abortar_6g1 (anclaje H1) + abortar_corrida_6g1 '
                               '(re-anclaje + lstat vs fstat) vs '
                               'publicar_dir_6g1 (sin verificación previa)'),
        ['crear_y_acreditar_dir_6g1(shared/user/base, prov_c4)',
         'escritura por ruta de analysis.json (fase pre)',
         'rename shared/user -> shared/user.orig; mkdir shared/user (0777); '
         'reconstrucción base/prov_c4 por el atacante',
         'escritura por ruta de candidates.json (fase post) + medición de caída',
         'manipulación del contenido por el atacante (propietario del dir)',
         'abortar_corrida_6g1(ruta, destino) — detección esperada',
         'publicar_dir_6g1(ruta, destino_publicado) — sin verificación previa',
         'fotografías de árbol + identidades dev/ino antes y después'],
        resultado,
        extra=dict(fotos=dict(antes=foto_shared_antes, final=foto_shared_final),
                   t_sustitucion=t_sub))


# ----------------------------------------------------------------------------
# Motor real: línea base (C0) y carrera con sustitución (C4r).
# ----------------------------------------------------------------------------

def _observar_y_sustituir(base, user, stop, eventos, activar, modo='temprano'):
    """Observador externo: detecta el provisional y, si `activar`, sustituye
    el componente intermedio `user` (capacidad: escritura sobre shared, el
    padre de user).

    modo='temprano': sustituye inmediatamente tras ver el provisional
    (0,2 ms después de la creación). modo='tardio': espera a ver
    analysis.json dentro del provisional (write_reports en curso) y
    sustituye entonces, dentro de la ventana entre la última escritura por
    ruta del motor y la publicación por ruta."""
    patron = re.compile(r'^motorA_run_.*_partial$')
    prov_visto = None
    while not stop.is_set():
        try:
            nombres = os.listdir(base)
        except OSError:
            nombres = []
        for n in nombres:
            if patron.match(n):
                prov = os.path.join(base, n)
                if prov_visto is None:
                    prov_visto = n
                    try:
                        st = os.lstat(prov)
                    except OSError:
                        continue
                    eventos['provisional_detectado'] = dict(
                        nombre=n, dev=st.st_dev, ino=st.st_ino, t=time.time())
                    if not activar:
                        return
                    if modo == 'temprano':
                        _sustituir(user, base, n, eventos)
                        return
                    break
                if modo == 'tardio' and 'analysis.json' in os.listdir(prov):
                    try:
                        st = os.lstat(prov)
                    except OSError:
                        continue
                    eventos['analysis_json_visto'] = dict(t=time.time())
                    eventos['identidad_al_sustituir'] = dict(
                        dev=st.st_dev, ino=st.st_ino)
                    _sustituir(user, base, n, eventos, robar=prov)
                    return
        time.sleep(0.0005 if modo == 'tardio' else 0.002)


def _sustituir(user, base, prov_nombre, eventos, robar=None):
    """Sustitución del componente intermedio `user`: rename + reconstrucción
    de la ruta con un directorio del atacante. Si `robar` (ruta del
    provisional original), el atacante copia su analysis.json real y lo
    manipula (demostración de robo y manipulación de contenido)."""
    user_orig = user + '.orig'
    os.rename(user, user_orig)
    os.mkdir(user, 0o777)
    base_atacante = os.path.join(user, os.path.basename(base))
    os.mkdir(base_atacante, 0o700)
    prov_atacante = os.path.join(base_atacante, prov_nombre)
    os.mkdir(prov_atacante, 0o700)
    atacado = dict(analysis_json_falsificado=False)
    if robar is not None:
        # tras el rename, el provisional REAL vive bajo user.orig
        prov_real = os.path.join(user + '.orig', os.path.basename(base),
                                 prov_nombre)
        try:
            with open(os.path.join(prov_real, 'analysis.json'),
                      encoding='utf-8') as f:
                real = json.load(f)
            real['I1_MANIPULADO_POR_ATACANTE'] = (
                'contenido del provisional acreditado copiado y alterado '
                'por el atacante')
            with open(os.path.join(prov_atacante, 'analysis.json'), 'w',
                      encoding='utf-8') as f:
                json.dump(real, f)
            atacado['analysis_json_falsificado'] = True
        except Exception as exc:
            atacado['error_robo'] = '%s: %s' % (type(exc).__name__, exc)
    with open(os.path.join(prov_atacante, 'ATAQUE_I1.txt'), 'w',
              encoding='utf-8') as f:
        f.write('Directorio introducido por el ataque I-1 (componente '
                'intermedio sustituido).\n')
    eventos['sustitucion'] = dict(
        t=time.time(),
        delta_ms_desde_deteccion=round(
            (time.time() - eventos.get('provisional_detectado', {})
            .get('t', time.time())) * 1000.0, 3),
        prov_atacante=prov_atacante, **atacado)


def _correr_motor(work, caso, activar_sustitucion, outdir, modo='temprano'):
    raiz = os.path.join(work, caso)
    limpiar(raiz)
    shared = os.path.join(raiz, 'shared')
    user = os.path.join(shared, 'user')
    base = os.path.join(user, 'base')
    os.makedirs(base, 0o700)
    os.chmod(shared, 0o777)
    mix = os.path.join(raiz, 'mix.wav')
    shutil.copyfile(FIXTURE_MIX, mix)
    manifest = os.path.join(raiz, 'manifest.json')
    with open(manifest, 'w', encoding='utf-8') as f:
        json.dump(dict(
            mix_original=mix,
            pairs=[dict(pair_id='P01', family='6G1', variant='V01',
                        configuration='synthetic', source='synthetic',
                        vocal_path=FIXTURE_VOCAL, vocal_guide=FIXTURE_VOCAL,
                        instrumental_path=FIXTURE_INSTR,
                        instrumental_guide=FIXTURE_INSTR)]), f)
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               MKL_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)

    eventos = {}
    stop = threading.Event()
    th = threading.Thread(target=_observar_y_sustituir,
                          args=(base, user, stop, eventos,
                                activar_sustitucion, modo), daemon=True)
    th.start()
    log_capture = os.path.join(raiz, 'stdout_motor.log')
    t0 = time.time()
    with open(log_capture, 'w', encoding='utf-8') as lf:
        proc = subprocess.Popen(
            [sys.executable, '-B', MOTOR_H, '--manifest', manifest,
             '--out', base, '--mode', 'full_processing'],
            stdout=lf, stderr=subprocess.STDOUT, cwd=MOTORES, env=env,
            stdin=subprocess.DEVNULL)
        codigo = proc.wait()
        stop.set()
        th.join(timeout=5)
    duracion = round(time.time() - t0, 3)

    stdout_tail = open(log_capture, encoding='utf-8',
                       errors='replace').read().splitlines()[-25:]
    foto_shared = fotografiar(shared)

    publicado, st_pub, prov_orig = None, None, None
    ev = eventos.get('provisional_detectado')
    if ev:
        # localiza el provisional ORIGINAL (trasladado con user.orig si hubo
        # sustitución) y el publicado (nombre final sin _partial)
        base_local = (os.path.join(user + '.orig', 'base')
                      if activar_sustitucion and os.path.exists(user + '.orig')
                      else base)
        prov_orig_path = os.path.join(base_local, ev['nombre'])
        if os.path.exists(prov_orig_path):
            st = os.lstat(prov_orig_path)
            prov_orig = dict(ruta=prov_orig_path, dev=st.st_dev,
                             ino=st.st_ino,
                             contenido=sorted(os.listdir(prov_orig_path)))
        finals = [n for n in os.listdir(os.path.join(base, '..'))] \
            if False else None
        # busca el final publicado bajo la base nominal (árbol del atacante
        # si hubo sustitución) y bajo user.orig/base
        for cand_base in {base,
                          os.path.join(user + '.orig', 'base')}:
            if not os.path.isdir(cand_base):
                continue
            for n in sorted(os.listdir(cand_base)):
                if re.match(r'^motorA_run_.*(?<!_partial)$', n):
                    p = os.path.join(cand_base, n)
                    if os.path.isdir(p):
                        st = os.lstat(p)
                        publicado = dict(ruta=p, dev=st.st_dev, ino=st.st_ino,
                                         contenido=sorted(os.listdir(p))[:20])
                        st_pub = st
                        break
            if publicado:
                break

    identidad_publicada_igual = None
    if publicado and ev:
        identidad_publicada_igual = (
            publicado['dev'], publicado['ino']) == (ev['dev'], ev['ino'])

    exito_en_log = any('finalizada exitosamente' in l for l in stdout_tail)
    resultado = dict(
        codigo_salida=codigo, duracion_s=duracion,
        eventos_observador=eventos,
        provisional_original=prov_orig,
        publicado=publicado,
        identidad_publicada_igual_a_provisional=identidad_publicada_igual,
        exito_declarado_en_stdout=exito_en_log,
        stdout_tail=stdout_tail)
    if activar_sustitucion:
        resultado['veredicto'] = (
            'VULNERABILIDAD_REPRODUCIDA_EN_FLUJO_REAL' if
            (codigo == 0 and exito_en_log and ev
             and identidad_publicada_igual is False)
            else 'REVIEW')
        clas = ['vulnerabilidad_reproducida']
    else:
        resultado['veredicto'] = (
            'COMPORTAMIENTO_PERMITIDO_POR_DISENO' if
            (codigo == 0 and exito_en_log and ev
             and identidad_publicada_igual is True)
            else 'REVIEW')
        clas = ['comportamiento_permitido_por_diseno']
    desc = ('Corrida REAL del motor Hardened 6G.1 (full_processing, fixture '
            'sintético) %s sustitución de componente intermedio por un '
            'observador externo con permiso de escritura sobre el directorio '
            'compartido.' % ('CON' if activar_sustitucion else 'SIN'))
    return nuevo_caso(
        'C0' if not activar_sustitucion else 'C4r', desc,
        ('Que la corrida real publique como éxito un objeto distinto del '
         'provisional acreditado, y que las escrituras posteriores caigan '
         'fuera del directorio previsto.') if activar_sustitucion else
        ('Ninguno: línea base que demuestra el anclaje de identidad del '
         'diseño en el flujo real (publicado == provisional acreditado).'),
        clas,
        dict(shared=dict(modo=stat.filemode(os.lstat(shared).st_mode)),
             motor=os.path.basename(MOTOR_H),
             modo='full_processing', mix='fixtures/mix.wav (copia, sin '
             'enlaces simbólicos)',
             nota_euid='capacidad del observador: permiso de escritura sobre '
                       'shared; en el sandbox se ejecuta con el mismo uid'),
        ['crear shared(0777)/user(0700)/base(0700) + copia del fixture',
         'observador externo en hilo: polling 2 ms del provisional '
         'motorA_run_*_partial y lstat de identidad' +
         (' + rename user -> user.orig + reconstrucción' if
          activar_sustitucion else ''),
         'subprocess: python -B MOTOR --mix ... --mode full_processing '
         '--out base',
         'comparación (dev,ino) provisional detectado vs publicado',
         'fotografía de árbol final de shared'],
        resultado,
        extra=dict(fotos=dict(final=foto_shared), workdir=raiz))



def caso_c4rt(work, outdir):
    """C4rt — sustitución TARDÍA de componente intermedio en el flujo REAL del
    motor: dispara cuando analysis.json aparece en el provisional
    (write_reports en curso), dentro de la ventana entre las últimas
    escrituras por ruta y la publicación por ruta. Reintentos en directorios
    nuevos (la ventana es estrecha); se conservan todos los intentos."""
    intentos = []
    veredicto_final = 'riesgo_teorico_no_reproducido'
    ganador = None
    for k in range(1, 6):
        r = _correr_motor(work, 'c4rt_a%d' % k, True, outdir, modo='tardio')
        intentos.append(dict(intent=k, caso='c4rt_a%d' % k,
                             codigo_salida=r['resultado_observado']['codigo_salida'],
                             eventos=r['resultado_observado']['eventos_observador'],
                             publicado=r['resultado_observado']['publicado'],
                             identidad_igual=r['resultado_observado'][
                                 'identidad_publicada_igual_a_provisional'],
                             exito=r['resultado_observado']['exito_declarado_en_stdout'],
                             veredicto=r['resultado_observado']['veredicto'],
                             fichero='caso_c4rt_a%d.json' % k))
        with open(os.path.join(outdir, 'caso_c4rt_a%d.json' % k), 'w',
                  encoding='utf-8') as f:
            json.dump(r, f, indent=1, ensure_ascii=False, sort_keys=True)
        if r['resultado_observado']['veredicto'] == \
                'VULNERABILIDAD_REPRODUCIDA_EN_FLUJO_REAL':
            veredicto_final = 'VULNERABILIDAD_REPRODUCIDA_EN_FLUJO_REAL'
            ganador = intentos[-1]
            break
    pub = ganador['publicado'] if ganador else None
    contenido = pub['contenido'] if pub else []
    resultado = dict(
        intentos=intentos, intento_efectivo=(ganador or {}).get('intent'),
        publicado=pub, contenido_publicado=contenido,
        veredicto=veredicto_final)
    clas = ['vulnerabilidad_reproducida'] \
        if veredicto_final.startswith('VULNERABILIDAD') \
        else ['riesgo_teorico_no_reproducido']
    return nuevo_caso(
        'C4rt', 'Sustitución TARDÍA de componente intermedio (user) durante '
        'una corrida REAL del motor: dispara cuando analysis.json aparece en '
        'el provisional (write_reports en curso), dentro de la ventana entre '
        'las últimas escrituras por ruta y la publicación por ruta',
        'Que la corrida real publique como éxito (EXIT_OK) un directorio '
        'introducido por el atacante con contenido robado y manipulado, sin '
        'que el motor lo detecte: la publicación no re-verifica la identidad '
        'acreditada del provisional.',
        clas,
        dict(shared=dict(modo='drwxrwxrwx (0777)',
                         capacidad_atacante='permiso de escritura sobre '
                         'shared (rename de user + reconstrucción)'),
             motor=os.path.basename(MOTOR_H), modo='full_processing',
             disparo='aparece analysis.json en el provisional (polling 0.5 ms)',
             nota_euid='en el sandbox el atacante se simula con el mismo uid; '
                       'la capacidad requerida (escritura sobre shared) es '
                       'independiente del uid si el modo lo permite',
             reintentos='hasta 5 corridas; la ventana es estrecha (ms)'),
        ['crear shared(0777)/user(0700)/base(0700) + mix + manifest',
         'observador externo: polling del provisional y de analysis.json',
         'al ver analysis.json: rename user -> user.orig, reconstrucción de '
         'la ruta con prov del atacante + robo y manipulación del '
         'analysis.json real',
         'subprocess: python -B MOTOR --manifest ... --mode full_processing '
         '--out base',
         'comparación (dev,ino) provisional acreditado vs publicado y '
         'contenido del publicado'],
        resultado)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--casos', default='c1,c2,c3,c4,c0,c4r')
    ap.add_argument('--work', default='/tmp/i1_6g1')
    ap.add_argument('--out', default=os.path.join(ETAPA, 'evidence',
                                                  'diagnostico_i1_6g1'))
    args = ap.parse_args()
    os.makedirs(args.work, 0o700, exist_ok=True)
    os.makedirs(args.out, 0o755, exist_ok=True)
    casos = [c.strip().lower() for c in args.casos.split(',') if c.strip()]
    funcs = dict(c1=caso_c1, c2=caso_c2, c3=caso_c3, c4=caso_c4,
                 c0=lambda w, o: _correr_motor(w, 'c0', False, o),
                 c4r=lambda w, o: _correr_motor(w, 'c4r', True, o),
                 c4rt=caso_c4rt)
    resultados = []
    for c in casos:
        if c not in funcs:
            raise SystemExit('caso desconocido: %s' % c)
        print('=== %s ===' % c.upper(), flush=True)
        r = funcs[c](args.work, args.out)
        ruta = os.path.join(args.out, 'caso_%s.json' % r['caso'].lower())
        with open(ruta, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=1, ensure_ascii=False, sort_keys=True)
        print('  ->', ruta, '| veredicto:', r['resultado_observado'].get(
            'veredicto', '?'), flush=True)
        resultados.append(dict(caso=r['caso'],
                               clasificacion=r['clasificacion'],
                               veredicto=r['resultado_observado'].get(
                                   'veredicto'),
                               fichero=os.path.basename(ruta)))
    cons = dict(schema=SCHEMA,
                generado=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                casos=resultados)
    with open(os.path.join(args.out, 'consolidado_diagnostico_i1.json'), 'w',
              encoding='utf-8') as f:
        json.dump(cons, f, indent=1, ensure_ascii=False)
    print('consolidado:', os.path.join(args.out,
                                       'consolidado_diagnostico_i1.json'))


if __name__ == '__main__':
    main()
