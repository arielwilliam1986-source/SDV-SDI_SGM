#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PROTOTIPO EXPERIMENTAL — Segunda revisión PDA-1: protección integral del
ciclo (Hallazgos A y B de Cris, 22-11-2026).

NO modifica producción. Reutiliza el mecanismo PDA-1 del prototipo anterior
(importa scripts/prototipo_publicacion_anclada_6g1.py) y añade:

  A1  ¿Puede PDA-1 publicar el directorio acreditado aunque sus artefactos
      hayan sido desviados al árbol sustituto? (escrituras por ruta NOMINAL,
      como los motores hoy) -> se espera: SÍ (identidad correcta, contenidos
      desviados): PDA-1 solo NO basta.
  A2  Escrituras ancladas (EA): fd_run conservado + rutas /proc/self/fd/fd_run
      para soundfile (WAV real), numpy open_memmap, open() builtin y log;
      sustitución del intermedio ANTES de escribir -> todo cae en el
      acreditado; publicación anclada -> publicado con TODOS los artefactos.
  A3  Sustitución DURANTE las escrituras (inyección entre artefactos) ->
      las escrituras posteriores siguen cayendo en el acreditado (fd_run
      designa el objeto, no una ruta).
  B1  Sustitución del DESTINO publicado DESPUÉS de la verificación post y
      antes del EXIT_OK (misma uid) -> qué garantía queda: el EXIT_OK se
      emite igual (límite); detección forense posible (identidad registrada
      vs ruta final).
  B2  Re-verificación del destino inmediatamente antes del EXIT_OK -> la
      sustitución anterior se DETECTA en ese punto (fail-closed posible);
      ventana residual restante: entre esa re-verificación y la salida del
      proceso.
  C   Cierre determinista de fd_padre/fd_run en éxito, excepción e
      interrupción (niveles de mecanismo; verificación en /proc/self/fd).

Uso:
  python -B scripts/prototipo_escrituras_ancladas_6g1.py \
      --work /tmp/ea_6g1 --out evidence/prototipo_escrituras_ancladas_6g1
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

import numpy as np                     # noqa: E402
import soundfile as sf                 # noqa: E402

SCHEMA = 'prototipo-ea-1/1'
SR = 44100


def ruta_proc(fd_dir, rel=''):
    return '/proc/self/fd/%d/%s' % (fd_dir, rel)


def listado_relativo(dirpath):
    """Listado recursivo con rutas relativas (para completitud)."""
    out = []
    for dp, dns, fns in os.walk(dirpath):
        for n in sorted(dns) + sorted(fns):
            rel = os.path.relpath(os.path.join(dp, n), dirpath)
            if not rel.startswith('..'):
                out.append(rel)
    return sorted(out)


def ino_de(path):
    try:
        st = os.lstat(path)
        return dict(dev=st.st_dev, ino=st.st_ino)
    except OSError:
        return None


def escribir_artefactos_por_ruta(base_nominal, nombre_prov, etiqueta):
    """Escrituras COMO LOS MOTORES HOY: por ruta absoluta nominal."""
    with open(os.path.join(base_nominal, nombre_prov, 'analysis.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'etiqueta': etiqueta, 'via': 'ruta-nominal'}, f)
    data = np.zeros((SR, 2), dtype='float64')
    data[:, 0] = 0.3
    sf.SoundFile(os.path.join(base_nominal, nombre_prov, 'mix SDV.wav'),
                 mode='w', samplerate=SR, channels=2).write(data)
    sf.SoundFile(os.path.join(base_nominal, nombre_prov, 'mix SDI.wav'),
                 mode='w', samplerate=SR, channels=2).write(data * 0.5)


def escribir_artefactos_anclados(fd_run, fd_dir_masks, etiqueta,
                                 con_memmap=True):
    """Escrituras ANCLADAS (mecanismo EA propuesto): rutas /proc/self/fd/fd_run
    (bibliotecas) y openat/mkdir relativo (builtin)."""
    arte = []
    # log (Tee-like) por ruta /proc
    p = ruta_proc(fd_run, 'engine_log.txt')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('LOG %s\n' % etiqueta)
    arte.append('engine_log.txt')
    # JSON por ruta /proc
    p = ruta_proc(fd_run, 'analysis.json')
    with open(p, 'w', encoding='utf-8') as f:
        json.dump({'etiqueta': etiqueta, 'via': 'escrituras-ancladas'}, f)
    arte.append('analysis.json')
    # WAV real con soundfile por ruta /proc
    data = np.zeros((SR, 2), dtype='float64')
    data[:, 0] = 0.3
    p = ruta_proc(fd_run, 'mix SDV.wav')
    with sf.SoundFile(p, mode='w', samplerate=SR, channels=2) as h:
        h.write(data)
    arte.append('mix SDV.wav')
    p = ruta_proc(fd_run, 'mix SDI.wav')
    with sf.SoundFile(p, mode='w', samplerate=SR, channels=2) as h:
        h.write(data * 0.5)
    arte.append('mix SDI.wav')
    if con_memmap:
        # memmap real dentro de masks/ (masks ya creada con mkdir relativo)
        p = ruta_proc(fd_dir_masks, 'confidence_map.npy')
        mm = np.lib.format.open_memmap(p, mode='w+', dtype='float32',
                                       shape=(64, 8))
        mm[:] = 0.5
        mm.flush()
        del mm
        arte.append('masks/confidence_map.npy')
    return arte


def leer_via_ruta(ruta_base_publicado):
    """Lectura de verificación (como post_wav_identity de los motores)."""
    out = {}
    for nombre in ['mix SDV.wav', 'mix SDI.wav']:
        p = os.path.join(ruta_base_publicado, nombre)
        try:
            data, sr = sf.read(p, dtype='float64')
            out[nombre] = dict(frames=len(data), sr=sr,
                               sha=hashlib.sha256(data.tobytes()).hexdigest())
        except Exception as exc:
            out[nombre] = dict(error='%s: %s' % (type(exc).__name__, exc))
    return out


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
        # el atacante recrea el provisional con el MISMO nombre nominal
        os.mkdir(os.path.join(user, 'base', ancla['nombre']), 0o700)
        r['base_nominal'] = os.path.join(user, 'base')  # secuestrada
        r['base_real'] = os.path.join(user + '.orig', 'base')
    return ancla, r


def escenario_a1(work, outdir):
    """Hallazgo A: PDA-1 publicando el acreditado con artefactos desviados."""
    ancla, r = _estructura(work, 'A1', sustituir=True)
    # escrituras por ruta NOMINAL (como los motores hoy) tras la sustitución
    escribir_artefactos_por_ruta(r['base_nominal'], ancla['nombre'], 'A1')
    arte_real = os.path.join(r['base_real'], ancla['nombre'])
    res = publicar_anclada(ancla, 'run_final')
    publicado = os.path.join(r['base_real'], res['destino'] or 'x')
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        publicado_identidad=dict(dev=ancla['identidad']['dev'],
                                 ino=ancla['identidad']['ino']),
        contenido_acreditado_publicado=sorted(os.listdir(publicado))
        if os.path.isdir(publicado) else None,
        contenido_sustituto_atacante=sorted(os.listdir(
            os.path.join(r['base_nominal'], ancla['nombre'])))
        if os.path.isdir(os.path.join(r['base_nominal'],
                                      ancla['nombre'])) else None,
        artefactos_reales_en_acreditado=os.path.isdir(
            os.path.join(arte_real, 'analysis.json')))
    pda1_publica_con_contenido_desviado = (
        res['exito'] and detalle['contenido_acreditado_publicado'] == []
        and detalle['contenido_sustituto_atacante']
        and 'analysis.json' in detalle['contenido_sustituto_atacante'])
    detalle['respuesta_hallazgo_A'] = (
        'SI: PDA-1 publica correctamente (identidad) el directorio acreditado '
        'aunque TODOS los artefactos hayan sido desviados al sustituto — la '
        'identidad del directorio NO implica contenidos correctos. Se '
        'requiere protección de escrituras (EA) y checklist de completitud.'
        if pda1_publica_con_contenido_desviado else 'NO (revisar)')
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'A1', 'Hallazgo A: publicación anclada del provisional acreditado '
        'tras sustitución del intermedio y escrituras por ruta nominal '
        '(como los motores hoy)',
        'Que EXIT_OK se emita sobre el directorio correcto con CONTENIDOS '
        'desviados (o ausentes).',
        ['vulnerabilidad_reproducida_sin_escrituras_ancladas',
         'resultado_experimental'], detalle,
        extra=dict(veredicto='DEMOSTRADO' if pda1_publica_con_contenido_desviado
                   else 'REVIEW'))


def escenario_a2(work, outdir):
    """Mecanismo EA: escrituras ancladas con las bibliotecas reales."""
    ancla, r = _estructura(work, 'A2', sustituir=True)
    # EA: conservar fd_run desde la creación + masks/ con mkdir relativo
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    fd_masks = os.open('masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=fd_run)
    # sustitución del intermedio ANTES de escribir (el intermedio ya no
    # participa: fd_run designa el objeto acreditado)
    arte = escribir_artefactos_anclados(fd_run, fd_masks, 'A2')
    res = publicar_anclada(ancla, 'run_final')
    publicado_dir = os.path.join(r['base_real'], res['destino'] or 'x')
    contenido = listado_relativo(publicado_dir) if os.path.isdir(
        publicado_dir) else []
    lectura = leer_via_ruta(publicado_dir)
    faltan = [a for a in arte if a not in contenido]
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        artefactos_escritos_anclados=arte,
        contenido_publicado=contenido,
        faltan_en_publicado=faltan,
        lectura_posterior_via_ruta_publicada=lectura,
        sustituto_atacante_contenido=sorted(os.listdir(
            os.path.join(r['base_nominal'], ancla['nombre'])))
        if os.path.isdir(os.path.join(r['base_nominal'],
                                      ancla['nombre'])) else None,
        respuesta_hallazgo_A=('CON EA (fd_run + /proc/self/fd + openat '
                              'relativo): todos los artefactos (soundfile, '
                              'numpy memmap, open builtin, log) caen en el '
                              'directorio acreditado aunque la ruta nominal '
                              'esté secuestrada; la publicación devuelve un '
                              'directorio identidad-correcta y '
                              'contenido-correcto.')
        if not faltan and res['exito'] else 'REVISAR')
    os.close(fd_masks)
    os.close(fd_run)
    ok = (res['exito'] and not faltan
          and all('error' not in v for v in lectura.values()))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'A2', 'Mecanismo EA propuesto: escrituras ancladas por descriptor '
        '(soundfile WAV real, numpy open_memmap real, open builtin, log) con '
        'sustitución del intermedio antes de escribir',
        'Que alguna escritura caiga fuera del acreditado por seguir la ruta '
        'secuestrada.',
        ['comportamiento_permitido_por_diseno',
         'vulnerabilidad_eliminada_por_diseno'], detalle,
        extra=dict(veredicto='PASS' if ok else 'REVIEW'))


def escenario_a3(work, outdir):
    """Sustitución DURANTE las escrituras: fd_run inmune."""
    ancla, r = _estructura(work, 'A3', sustituir=False)
    fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                     | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
    os.mkdir('masks', 0o700, dir_fd=fd_run)
    fd_masks = os.open('masks', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=fd_run)
    # primera escritura anclada (WAV SDV)
    data = np.zeros((SR, 2), dtype='float64')
    data[:, 0] = 0.3
    with sf.SoundFile(ruta_proc(fd_run, 'mix SDV.wav'), mode='w',
                      samplerate=SR, channels=2) as h:
        h.write(data)
    # --- sustitución del intermedio EN PLENO procesamiento ---
    user = r['user']
    os.rename(user, user + '.orig')
    os.mkdir(user, 0o777)
    os.mkdir(os.path.join(user, 'base'), 0o700)
    r['base_nominal'] = os.path.join(user, 'base')
    r['base_real'] = os.path.join(user + '.orig', 'base')
    # escrituras ancladas restantes
    arte = escribir_artefactos_anclados(fd_run, fd_masks, 'A3',
                                        con_memmap=True)
    arte.append('mix SDV.wav')
    res = publicar_anclada(ancla, 'run_final')
    publicado_dir = os.path.join(r['base_real'], res['destino'] or 'x')
    contenido = listado_relativo(publicado_dir) if os.path.isdir(
        publicado_dir) else []
    faltan = [a for a in arte if a not in contenido]
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        contenido_publicado=contenido,
        faltan_en_publicado=faltan,
        sustituto_atacante_contenido=sorted(os.listdir(
            os.path.join(r['base_nominal'], ancla['nombre'])))
        if os.path.isdir(os.path.join(r['base_nominal'],
                                      ancla['nombre'])) else None)
    ok = (res['exito'] and not faltan)
    os.close(fd_masks)
    os.close(fd_run)
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'A3', 'Sustitución del componente intermedio DURANTE las escrituras '
        '(inyección entre artefactos) con mecanismo EA activo',
        'Que las escrituras posteriores a la sustitución se desvíen.',
        ['comportamiento_permitido_por_diseno'], detalle,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   nota='fd_run designa el OBJETO acreditado; el secuestro '
                        'posterior de la ruta no afecta a /proc/self/fd'))


def escenario_b1(work, outdir):
    """Hallazgo B: sustitución del DESTINO tras la verificación post."""
    ancla, r = _estructura(work, 'B1')
    os.mkdir(os.path.join(r['base'], ancla['nombre'], 'contenido'), 0o700)
    res = publicar_anclada(ancla, 'run_final')
    exito_en_verificacion = res['exito'] and res['traslado_verificado']
    # --- misma uid sustituye el destino publicado ANTES del EXIT_OK ---
    destino_pub = os.path.join(r['base'], res['destino'])
    os.rename(destino_pub, destino_pub + '.robado')
    os.mkdir(destino_pub, 0o700)
    with open(os.path.join(destino_pub, 'IMPOSTOR.txt'), 'w') as f:
        f.write('impostor post-verificacion\n')
    st_ruta_final = os.lstat(destino_pub)
    identidad_ruta = dict(dev=st_ruta_final.st_dev, ino=st_ruta_final.st_ino)
    exitok_emitido = True   # el diseño vigente emitiría EXIT_OK aquí
    # detección forense posible: identidad registrada vs ruta final
    deteccion = identidad_ruta != ancla['identidad']
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        exitok_emitido=exitok_emitido,
        exito_en_verificacion=exito_en_verificacion,
        identidad_acreditada=ancla['identidad'],
        identidad_ruta_final=identidad_ruta,
        ruta_final_designa_impostor=True,
        deteccion_forense_posible=deteccion,
        provisional_robado_conservado=os.path.isdir(destino_pub + '.robado'))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'B1', 'Hallazgo B: sustitución del DESTINO publicado después de la '
        'verificación post y antes del EXIT_OK (misma uid)',
        'Que el EXIT_OK declare éxito sobre una ruta que ya no designa el '
        'objeto verificado.',
        ['limitacion_residual_atacante_misma_uid (confirmada)',
         'resultado_experimental'], detalle,
        extra=dict(veredicto='DEMOSTRADO' if (exito_en_verificacion
                                              and exitok_emitido
                                              and deteccion) else 'REVIEW',
                   nota='PDA-1 garantiza la identidad del objeto publicado EN '
                        'EL INSTANTE de la verificación; después, la misma '
                        'uid puede secuestrar la ruta: el EXIT_OK sería '
                        'emitido igual. Detección forense posible; prevención '
                        'imposible sin soporte del kernel.'))


def escenario_b2(work, outdir):
    """Mitigación propuesta: re-verificación del destino antes del EXIT_OK."""
    ancla, r = _estructura(work, 'B2')
    os.mkdir(os.path.join(r['base'], ancla['nombre'], 'contenido'), 0o700)
    res = publicar_anclada(ancla, 'run_final')
    # (escenario B1) la misma uid sustituye el destino
    destino_pub = os.path.join(r['base'], res['destino'])
    os.rename(destino_pub, destino_pub + '.robado')
    os.mkdir(destino_pub, 0o700)
    # --- re-verificación tardía (punto añadido al diseño antes del EXIT_OK):
    st = fstatat_nofollow(ancla['fd_padre'], res['destino'])
    exitok = bool(st) and not stat.S_ISLNK(st.st_mode) and \
        (st.st_dev, st.st_ino) == (ancla['identidad']['dev'],
                                   ancla['identidad']['ino'])
    detalle = dict(
        publicacion={k: v for k, v in res.items() if k != 'pasos'},
        reverificacion=dict(existe=st is not None,
                            coincide=bool(st) and
                            (st.st_dev, st.st_ino) ==
                            (ancla['identidad']['dev'],
                             ancla['identidad']['ino'])),
        exitok_emitido=exitok,
        provisional_robado_conservado=os.path.isdir(destino_pub + '.robado'))
    os.close(ancla['fd_padre'])
    limpiar(r['raiz'])
    return nuevo(
        'B2', 'Mitigación propuesta: re-verificación de la identidad del '
        'destino (por descriptor del padre) inmediatamente antes del EXIT_OK',
        'Que el motor declare EXIT_OK cuando la ruta final ya no designa el '
        'objeto verificado.',
        ['comportamiento_rechazado_por_diseno (detección en el punto '
         'añadido)',
         'limitacion_residual_atacante_misma_uid (ventana entre la '
         're-verificación y la salida del proceso)'], detalle,
        extra=dict(veredicto='PASS' if (not exitok) else 'REVIEW',
                   nota='cierra la ventana B1 hasta el return EXIT_OK; el '
                        'residual inalienable (post-return, misma uid) queda '
                        'cubierto por el registro forense de identidad'))


def escenario_c(work, outdir):
    """Cierre determinista de fd_padre/fd_run en los tres caminos."""
    def medir_fds():
        return sorted(int(x) for x in os.listdir('/proc/self/fd'))

    resultados = {}
    for camino in ['exito', 'excepcion', 'interrupcion']:
        sub = os.path.join(work, 'C_%s' % camino)
        limpiar(sub)
        os.makedirs(sub, 0o700)
        antes = medir_fds()
        try:
            ancla = crear_y_anclar(sub, 'prov_%s' % camino)
            fd_run = os.open(ancla['nombre'], os.O_RDONLY | os.O_DIRECTORY
                             | os.O_NOFOLLOW, dir_fd=ancla['fd_padre'])
            res = publicar_anclada(ancla, 'run_final_%s' % camino)
            if camino == 'excepcion':
                raise RuntimeError('fallo simulado')
            if camino == 'interrupcion':
                raise KeyboardInterrupt()
            # éxito: cierre normal
            os.close(fd_run)
            os.close(ancla['fd_padre'])
            errores = []
        except KeyboardInterrupt:
            os.close(fd_run)
            os.close(ancla['fd_padre'])
            errores = []
            res = dict(exito=False)
        except RuntimeError:
            os.close(fd_run)
            os.close(ancla['fd_padre'])
            errores = []
            res = dict(exito=False)
        despues = medir_fds()
        resultados[camino] = dict(
            fds_antes=antes, fds_despues=despues,
            fds_residuales=[f for f in despues if f not in antes],
            exito_publicacion=res.get('exito'))
        limpiar(sub)
    ok = all(not v['fds_residuales'] for v in resultados.values())
    return nuevo(
        'C', 'Cierre determinista de fd_padre y fd_run en éxito, excepción e '
        'interrupción (nivel de mecanismo)',
        'Que queden descriptores residuales en cualquier camino de salida.',
        ['comportamiento_permitido_por_diseno'], resultados,
        extra=dict(veredicto='PASS' if ok else 'REVIEW',
                   nota='en producción, el cierre pasa a los protocolos '
                        'vigentes (preparar_aborto_6g1 / cierre normal '
                        'acreditado)'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--work', default='/tmp/ea_6g1')
    ap.add_argument('--out', default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'evidence', 'prototipo_escrituras_ancladas_6g1'))
    args = ap.parse_args()
    os.makedirs(args.work, 0o700, exist_ok=True)
    os.makedirs(args.out, 0o755, exist_ok=True)
    esc = dict(A1=escenario_a1, A2=escenario_a2, A3=escenario_a3,
               B1=escenario_b1, B2=escenario_b2, C=escenario_c)
    resultados = []
    for name in ['A1', 'A2', 'A3', 'B1', 'B2', 'C']:
        print('=== %s ===' % name, flush=True)
        r = esc[name](args.work, args.out)
        p = os.path.join(args.out, 'escenario_%s.json' % name)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(r, f, indent=1, ensure_ascii=False, sort_keys=True)
        print('  ->', p, '| veredicto:', r.get('veredicto', '?'), flush=True)
        resultados.append(dict(escenario=name, veredicto=r.get('veredicto'),
                               clasificacion=r['clasificacion'],
                               fichero=os.path.basename(p)))
    con = dict(schema=SCHEMA,
               generado=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
               entorno=dict(python='.'.join(map(str, sys.version_info[:3])),
                            numpy=np.__version__, soundfile=sf.__version__,
                            libsndfile=sf.__libsndfile_version__,
                            euid=os.geteuid()),
               escenarios=resultados)
    with open(os.path.join(args.out, 'consolidado_prototipo_ea_1.json'),
              'w', encoding='utf-8') as f:
        json.dump(con, f, indent=1, ensure_ascii=False)
    print('consolidado:', os.path.join(args.out,
                                       'consolidado_prototipo_ea_1.json'))


if __name__ == '__main__':
    main()
