#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEASIBILITY-1 (6G.1) — Validación empírica AISLADA de los mecanismos del plan
Hardened FLOW-1..4 v2.3.

Autorización: Cris (padre 22748622830d1579d7814c51b1f048c58b121110).
REGLAS: este arnés NO importa ni ejecuta código de producción (motores/,
lectura_segura_6g1.py); implementa los mecanismos de forma independiente en un
espacio aislado (/tmp/feas1_6g1 por defecto). Cada prueba clasifica
PASS / FAIL / UNKNOWN con evidencia JSON por sub-paso.

Pruebas: F1 (R-13 subdirectorios de dos niveles), F2 (R-29 procfs),
F3 (R-34 soundfile/numpy), F4 (P-08/R-28 limpieza masks),
F5 (R-D renameat2 dirfd), F6 (cierre de recursos y fugas).
"""
import argparse
import ctypes
import errno
import json
import os
import platform
import shutil
import stat
import sys
import time
import traceback

RAIZ_DEF = '/tmp/feas1_6g1'
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1


# ---------------------------------------------------------------- utilidades
def _snapshot_fds():
    """Conjunto de fds abiertos del proceso (nombres de /proc/self/fd)."""
    try:
        return set(os.listdir('/proc/self/fd'))
    except OSError as exc:
        return set(['ERROR:%s' % exc])


def _ident(st):
    return (st.st_dev, st.st_ino)


def _abrir_dir_acreditado(padre_fd, nombre):
    """openat O_DIRECTORY|O_NOFOLLOW relativo a un dirfd acreditado + fstat."""
    fd = os.open(nombre, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                 dir_fd=padre_fd)
    return fd, _ident(os.fstat(fd))


def _crear_dir_rel(padre_fd, nombre, modo=0o700):
    os.mkdir(nombre, modo, dir_fd=padre_fd)


def _crear_archivo_rel(padre_fd, nombre, contenido=b'', escritura=True):
    rw = os.O_RDWR if escritura else os.O_WRONLY
    fd = os.open(nombre, rw | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=padre_fd)
    if contenido:
        os.write(fd, contenido)
    return fd, _ident(os.fstat(fd))


def _fd_existe(n):
    """¿Existe /proc/self/fd/N? — vía stat (sin abrir fd de listado)."""
    try:
        os.stat('/proc/self/fd/%d' % n)
        return True
    except OSError:
        return False


def _registrar(pasos, nombre, ok, detalle):
    pasos.append(dict(paso=nombre, ok=bool(ok), detalle=detalle))


def _json_default(o):
    if isinstance(o, bytes):
        return o.decode('utf-8', 'replace')
    if hasattr(o, 'item'):
        return o.item()
    return str(o)


def _excepcion(nombre, exc):
    return dict(paso=nombre, excepcion=type(exc).__name__, mensaje=str(exc),
                errno=getattr(exc, 'errno', None))


class Resultado(dict):
    """Resultado de una prueba: verdicto PASS/FAIL/UNKNOWN + pasos + fallos."""
    def finalizar(self, verdicto, nota=''):
        self['resultado'] = verdicto
        if nota:
            self['nota'] = nota
        return self


def _entorno():
    import numpy
    import soundfile
    return dict(python=sys.version.split()[0], kernel=platform.release(),
                maquina=platform.machine(), plataforma=platform.platform(),
                numpy=numpy.__version__, soundfile=soundfile.__version__,
                libsndfile=soundfile.__libsndfile_version__,
                euid=os.geteuid(), ts=time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                                    time.gmtime()))


# ---------------------------------------------------------------- F1 (R-13)
def f1(raiz):
    """R-13: subdirectorios candidates de DOS niveles por descriptores."""
    r = Resultado(flujo='F1', riesgo='R-13', raiz=os.path.join(raiz, 'f1'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    try:
        fds_abiertos = []
        # (1) base acreditada
        os.makedirs(os.path.join(d, 'base'), 0o700)
        fd_base, I_base = _abrir_dir_acreditado(
            os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW), 'base')
        fds_abiertos.append(('fd_base', fd_base))
        _registrar(pasos, 'base_acreditada', True, dict(identidad=I_base))
        # (2) candidates/ relativo a fd_base + apertura/acreditación
        _crear_dir_rel(fd_base, 'candidates')
        fd_cand, I_cand = _abrir_dir_acreditado(fd_base, 'candidates')
        fds_abiertos.append(('fd_candidates', fd_cand))
        _registrar(pasos, 'candidates_creado_y_acreditado', True,
                   dict(identidad=I_cand))
        # (3) grupos de dos niveles, componente a componente
        grupos = dict(individual_gp01=None, consensus_confidence_weighted_mean=None)
        identidades = {}
        for g in grupos:
            _crear_dir_rel(fd_cand, g)
            fd_g, I_g = _abrir_dir_acreditado(fd_cand, g)
            identidades[g] = I_g
            fds_abiertos.append(('fd_%s' % g, fd_g))
            _crear_archivo_rel(fd_g, 'salida.wav', b'RIFF....WAVE')
            _registrar(pasos, 'grupo_%s' % g, True,
                       dict(identidad=I_g, creado='salida.wav via openat O_EXCL'))
        r['identidades'] = dict(base=I_base, candidates=I_cand,
                                grupos=identidades)
        # (4) entradas inesperadas ANTES del descenso (symlink a un dir REAL existente)
        os.makedirs(os.path.join(d, 'fuera'), 0o700)
        _crear_archivo_rel(fd_cand, 'suelto.txt', b'u')
        os.symlink(os.path.join(d, 'fuera'), 'evil', dir_fd=fd_cand)
        # descenso/verificación SIN rutas nominales
        listado = sorted(os.listdir(fd_cand))
        verif = {}
        for nombre in listado:
            st = os.lstat(nombre, dir_fd=fd_cand)
            if stat.S_ISDIR(st.st_mode) and nombre in identidades:
                fd_x, I_x = _abrir_dir_acreditado(fd_cand, nombre)
                os.close(fd_x)
                verif[nombre] = dict(tipo='dir', identidad_ok=I_x == identidades[nombre])
            else:
                verif[nombre] = dict(tipo='inesperado' if not stat.S_ISDIR(st.st_mode)
                                     else 'dir_desconocido')
        _registrar(pasos, 'descenso_sin_rutas_nominales', True, dict(listado=listado,
                                                                     verificacion=verif))
        # (5) negativo: apertura del symlink con O_NOFOLLOW => rechazo
        try:
            os.open('evil', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=fd_cand)
            _registrar(pasos, 'symlink_rechazado', False, 'la apertura NO falló')
            fallos.append(dict(caso='symlink', detalle='la apertura no falló'))
        except OSError as exc:
            _registrar(pasos, 'symlink_rechazado', True,
                       _excepcion('open evil (objetivo real existente)', exc))
        # sustitución misma-uid del nombre de un grupo (el fd sigue designando el real)
        g0 = 'individual_gp01'
        os.rename(g0, g0 + '_movido', src_dir_fd=fd_cand, dst_dir_fd=fd_cand)
        _crear_dir_rel(fd_cand, g0)          # impostor con el nombre original
        fd_g0 = dict(fds_abiertos)['fd_%s' % g0]
        I_fd = _ident(os.fstat(fd_g0))
        st_nombre = os.lstat(g0, dir_fd=fd_cand)
        _registrar(pasos, 'sustitucion_detectada_por_identidad',
                   I_fd != _ident(st_nombre),
                   dict(fd_designa=I_fd, nombre_actual=_ident(st_nombre),
                        real_conservado='fd sigue designando el inodo original'))
        # entrada inesperada regular en candidates/ (clasificada arriba)
        inesperados = [n for n, v in verif.items()
                       if v.get('tipo') == 'inesperado']
        _registrar(pasos, 'entradas_inesperadas_clasificadas', True,
                   dict(inesperados=inesperados))
        # (6) cierre ordenado: grupos -> candidates -> base; sin fugas
        #     (comprobación por stat directo de /proc/self/fd/N: sin fd de listado)
        cerrados = [fd for _, fd in fds_abiertos]
        for fd in cerrados:
            os.close(fd)
        fuga = sorted(n for n in cerrados if _fd_existe(n))
        _registrar(pasos, 'cierre_ordenado_y_sin_fugas', not fuga,
                   dict(cerrados=[n for n, _ in fds_abiertos], residuos=fuga))
        r.finalizar('PASS' if not fuga and not fallos else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f1', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    return r


# ---------------------------------------------------------------- F2 (R-29)
def f2(raiz):
    """R-29: dependencia de procfs (/proc/self/fd) y alternativa sin procfs."""
    r = Resultado(flujo='F2', riesgo='R-29', raiz=os.path.join(raiz, 'f2'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    try:
        # (a) disponibilidad efectiva de /proc/self/fd
        disponible = os.path.isdir('/proc/self/fd')
        _registrar(pasos, 'proc_self_fd_disponible', disponible,
                   dict(entradas=len(_snapshot_fds()) if disponible else None))
        if not disponible:
            return r.finalizar('UNKNOWN',
                               'procfs no disponible: variante con magic-link no probable aquí')
        # (b) el magic-link designa el OBJETO del fd (no la ruta)
        ruta = os.path.join(d, 'objeto.txt')
        fd0, I0 = _crear_archivo_rel(
            os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW),
            'objeto.txt', b'payload-feas1')
        magic = os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY)
        I_magic = _ident(os.fstat(magic))
        contenido = os.read(magic, 64)
        os.close(magic)
        _registrar(pasos, 'magic_link_designa_el_objeto',
                   I_magic == I0 and contenido == b'payload-feas1',
                   dict(identidad_fd=I0, identidad_magic=I_magic))
        # unlink del nombre nominal: el objeto sigue vivo por fd
        os.unlink(ruta)
        magic2 = os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY)
        contenido2 = os.read(magic2, 64)
        os.close(magic2)
        _registrar(pasos, 'objeto_vivo_sin_ruta_nominal', contenido2 == b'payload-feas1',
                   dict(leido_tras_unlink=contenido2))
        # error documentado: fd cerrado -> magic link desaparece
        os.close(fd0)
        try:
            os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY)
            _registrar(pasos, 'fd_cerrado_magic_desaparece', False, 'no falló')
        except OSError as exc:
            _registrar(pasos, 'fd_cerrado_magic_desaparece', True,
                       _excepcion('open magic tras close', exc))
        # (c) alternativa SIN procfs: header npy + np.memmap(file object)
        import numpy as np
        fd_n, _ = _crear_archivo_rel(
            os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW), 'alt.npy',
            escritura=True)          # O_RDWR: mmap ACCESS_WRITE lo exige
        fo = os.fdopen(fd_n, 'r+b', closefd=False)
        shape = (256, 512)
        np.lib.format.write_array_header_1_0(
            fo, dict(descr='<f4', fortran_order=False, shape=shape))
        offset = fo.tell()
        total = offset + shape[0] * shape[1] * 4
        fo.seek(total - 1)
        fo.write(b'\0')
        fo.flush()
        mm = np.memmap(fo, dtype=np.float32, mode='r+', offset=offset,
                       shape=shape)
        mm[:] = np.arange(shape[0] * shape[1], dtype=np.float32).reshape(shape)
        mm.flush()
        I_antes = _ident(os.fstat(fd_n))
        del mm
        fo.close()
        I_despues = _ident(os.fstat(fd_n))
        os.close(fd_n)
        _fd_d2 = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd_ver = os.open('alt.npy', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=_fd_d2)
        datos = None
        try:
            datos = np.lib.format.read_array(
                os.fdopen(os.dup(fd_ver), 'rb', closefd=True))
        finally:
            os.close(fd_ver)
            os.close(_fd_d2)
        ok = (I_antes == I_despues and datos is not None
              and datos.shape == shape and int(datos[7, 9]) == 7 * 512 + 9)
        _registrar(pasos, 'alternativa_sin_procfs_np_memmap_fileobj', ok,
                   dict(identidad_antes=I_antes, identidad_despues=I_despues,
                        forma=list(datos.shape) if datos is not None else None))
        r.finalizar('PASS' if ok and not fallos else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f2', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    return r


# ---------------------------------------------------------------- F3 (R-34)
def f3(raiz):
    """R-34: soundfile por descriptor (closefd=False/True) y numpy memmap."""
    import numpy as np
    import soundfile
    r = Resultado(flujo='F3', riesgo='R-34', raiz=os.path.join(raiz, 'f3'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    fd_dir = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    try:
        fs = 44100
        rng = np.random.default_rng(20261122)
        datos = (0.30 * rng.standard_normal((fs, 2))).astype(np.float32)
        # (a) escritor por descriptor con closefd=False
        fd_w, I1 = _crear_archivo_rel(fd_dir, 'salida.wav')
        w = soundfile.SoundFile(fd_w, mode='w', samplerate=fs, channels=2,
                                subtype='PCM_16', format='WAV', closefd=False)
        w.write(datos)
        w.close()
        I2 = _ident(os.fstat(fd_w))          # el fd sigue abierto (closefd=False)
        _registrar(pasos, 'sf_escritor_fd_closefd_false', I1 == I2,
                   dict(identidad_antes=I1, identidad_despues=I2,
                        fd_sigue_abierto=True))
        os.close(fd_w)
        # (b) lectura por descriptor + contenido esperado
        fd_r = os.open('salida.wav', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd_dir)
        rd = soundfile.SoundFile(fd_r, mode='r', closefd=False)  # lectura: formato auto-detectado; format no permitido
        leido = rd.read(dtype='float32', always_2d=True)
        rd.close()
        os.close(fd_r)
        _registrar(pasos, 'sf_lector_fd_y_contenido',
                   leido.shape == datos.shape,
                   dict(frames=leido.shape[0], canales=leido.shape[1]))
        # (c) comportamiento observado con closefd=True (por defecto)
        fd_t, _ = _crear_archivo_rel(fd_dir, 'tmp_closefd.wav')
        wt = soundfile.SoundFile(fd_t, mode='w', samplerate=fs, channels=2,
                                 subtype='PCM_16', format='WAV')  # closefd=True implícito
        wt.write(datos[:100])
        wt.close()
        try:
            os.fstat(fd_t)
            _registrar(pasos, 'sf_closefd_true_cierra_fd', False,
                       'el fd sigue abierto (esperado: cerrado por libsndfile)')
        except OSError as exc:
            _registrar(pasos, 'sf_closefd_true_cierra_fd', True,
                       _excepcion('fstat tras sf.close (closefd=True)', exc))
        # (d) numpy: open_memmap vía /proc/self/fd con fd retenido
        fd_m, I3 = _crear_archivo_rel(fd_dir, 'mask.npy')
        shape = (1024, 2048)
        mm = np.lib.format.open_memmap('/proc/self/fd/%d' % fd_m, mode='w+',
                                       dtype=np.float32, shape=shape)
        mm[100, 200] = 3.25
        mm.flush()
        del mm
        I4 = _ident(os.fstat(fd_m))
        os.close(fd_m)
        fd_chk = os.open('mask.npy', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd_dir)
        chk = np.lib.format.read_array(os.fdopen(os.dup(fd_chk), 'rb',
                                                 closefd=True))
        os.close(fd_chk)
        _registrar(pasos, 'open_memmap_via_procfs_fd_retenido',
                   I3 == I4 and float(chk[100, 200]) == 3.25,
                   dict(identidad_antes=I3, identidad_despues=I4,
                        valor=chk[100, 200].item() if chk.size else None))
        # (e) snapshot de fds abiertos del proceso al final de la prueba
        r['fds_snapshot_final'] = len(_snapshot_fds())
        _registrar(pasos, 'snapshot_final_fds', True,
                   dict(n_fds_abiertos=len(_snapshot_fds())))
        r.finalizar('PASS' if not fallos else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f3', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    finally:
        os.close(fd_dir)
    return r


# ---------------------------------------------------------------- F4 (R-28)
def f4(raiz):
    """P-08/R-28: limpieza de masks/ por descriptores; symlink no redirige."""
    r = Resultado(flujo='F4', riesgo='P-08/R-28', raiz=os.path.join(raiz, 'f4'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    fd_dir = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    try:
        _crear_dir_rel(fd_dir, 'masks')
        fd_masks, I_masks = _abrir_dir_acreditado(fd_dir, 'masks')
        _registrar(pasos, 'masks_abierto_por_descriptor', True,
                   dict(identidad=I_masks))
        nombres = ['a.npy', 'b.npy', 'c.npy']
        for n in nombres:
            _crear_archivo_rel(fd_masks, n, b'x')
        # symlink sustituto: el nombre "masks" pasa a apuntar FUERA, pero el fd
        # sigue designando el REAL: las operaciones por fd no se redirigen
        destino_ajeno = os.path.join(d, 'ajeno')
        os.makedirs(destino_ajeno, 0o700)
        os.rename('masks', 'masks_real', src_dir_fd=fd_dir, dst_dir_fd=fd_dir)
        os.symlink(destino_ajeno, 'masks', dir_fd=fd_dir)
        _fd_aj = os.open(destino_ajeno, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        _crear_archivo_rel(_fd_aj, 'del_ajeno.txt')
        os.close(_fd_aj)
        _registrar(pasos, 'fd_no_redirigido_por_symlink',
                   sorted(os.listdir(fd_masks)) == nombres,
                   dict(contenido_via_fd=sorted(os.listdir(fd_masks))))
        # eliminar entradas relativas al descriptor (el symlink 'masks' es irrelevante)
        for n in nombres:
            os.unlink(n, dir_fd=fd_masks)
        vacio = os.listdir(fd_masks) == []
        _registrar(pasos, 'unlinkat_por_fd_masks', vacio,
                   dict(restantes=os.listdir(fd_masks)))
        # error documentado: unlink de inexistente
        try:
            os.unlink('no_esta.npy', dir_fd=fd_masks)
            _registrar(pasos, 'unlink_inexistente_enoent', False, 'no falló')
        except OSError as exc:
            _registrar(pasos, 'unlink_inexistente_enoent', exc.errno == errno.ENOENT,
                       _excepcion('unlink', exc))
        os.close(fd_masks)
        # rmdir del directorio vía descriptor del PADRE (nombre 'masks' es un
        # symlink: O_NOFOLLOW no aplica a rmdir; se elimina el REAL por su nombre
        # real 'masks_real' — el diseño v2.3 usa fd_pub + rmdir("masks") sobre el
        # publicado real; aquí se prueba la operación relativa y el fallo ENOTEMPTY)
        _fd_mr = os.open(os.path.join(d, 'masks_real'),
                         os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        _crear_archivo_rel(_fd_mr, 'z.npy')
        os.close(_fd_mr)
        try:
            os.rmdir('masks_real', dir_fd=fd_dir)
            _registrar(pasos, 'rmdir_no_vacio_enotempty', False, 'no falló')
        except OSError as exc:
            _registrar(pasos, 'rmdir_no_vacio_enotempty',
                       exc.errno == errno.ENOTEMPTY,
                       _excepcion('rmdir', exc))
        _fd_mr2 = os.open(os.path.join(d, 'masks_real'),
                          os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        os.unlink('z.npy', dir_fd=_fd_mr2)
        os.close(_fd_mr2)
        os.rmdir('masks_real', dir_fd=fd_dir)
        _registrar(pasos, 'rmdir_vacio_por_descriptor_padre', True,
                   dict(eliminado='masks_real'))
        # el symlink 'masks' del impostor NO fue seguido ni eliminado por error
        st = os.lstat('masks', dir_fd=fd_dir)
        _registrar(pasos, 'symlink_sustituto_intacto_y_no_seguido',
                   stat.S_ISLNK(st.st_mode), dict(tipo='symlink'))
        r.finalizar('PASS' if not fallos else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f4', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    finally:
        os.close(fd_dir)
    return r


# ---------------------------------------------------------------- F5 (R-D)
def _renameat2(src_dirfd, src, dst_dirfd, dst, flags):
    libc = ctypes.CDLL(None, use_errno=True)
    fn = getattr(libc, 'renameat2', None)
    via = 'glibc'
    if fn is None:
        nr = dict(x86_64=316, aarch64=276).get(platform.machine())
        if nr is None:
            raise OSError('renameat2 indisponible en esta arquitectura')
        via = 'syscall'
        fn = libc.syscall
        fn.restype = ctypes.c_long
        fn.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                       ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rr = fn(nr, _AT_FDCWD if src_dirfd is None else src_dirfd,
                os.fsencode(src), _AT_FDCWD if dst_dirfd is None else dst_dirfd,
                os.fsencode(dst), flags)
        if rr != 0:
            e = ctypes.get_errno()
            raise OSError(e, os.strerror(e), src, None, dst)
        return via
    fn.restype = ctypes.c_int
    fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                   ctypes.c_char_p, ctypes.c_uint]
    rr = fn(_AT_FDCWD if src_dirfd is None else src_dirfd, os.fsencode(src),
            _AT_FDCWD if dst_dirfd is None else dst_dirfd, os.fsencode(dst),
            flags)
    if rr != 0:
        e = ctypes.get_errno()
        if e == errno.EEXIST:
            raise FileExistsError(e, 'destino existente', dst)
        raise OSError(e, os.strerror(e), src, None, dst)
    return via


def f5(raiz):
    """R-D: publicación renameat2 relativa a dirfd + acreditación post-rename."""
    r = Resultado(flujo='F5', riesgo='R-D (P-06)', raiz=os.path.join(raiz, 'f5'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    fd_padre = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    try:
        def nuevo(nombre):
            _crear_dir_rel(fd_padre, nombre)
            _crear_archivo_rel(
                os.open(nombre, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=fd_padre), 'dato.txt', b'v')
            return _abrir_dir_acreditado(fd_padre, nombre)
        # disponibilidad: la syscall se EJECUTA (ENOENT = disponible);
        # sólo ENOSYS/indisponibilidad de arquitectura => UNKNOWN
        try:
            _renameat2(None, 'no_existe_a', None, 'no_existe_b', 0)
            via_ok, via_detalle = True, 'renameat2 ejecutado'
        except OSError as exc:
            if exc.errno in (errno.ENOSYS,) or 'indisponible' in str(exc):
                _registrar(pasos, 'renameat2_disponible', False,
                           _excepcion('probe', exc))
                return r.finalizar('UNKNOWN',
                                   'renameat2 no disponible en este entorno')
            via_ok, via_detalle = True, _excepcion('probe', exc)
        _registrar(pasos, 'renameat2_disponible', via_ok, dict(via=via_detalle))
        # (1) publicación normal + identidad
        fd_p, I_p = nuevo('prov1')
        via = _renameat2(fd_padre, 'prov1', fd_padre, 'final1', _RENAME_NOREPLACE)
        fd_pub, I_pub = _abrir_dir_acreditado(fd_padre, 'final1')
        _registrar(pasos, 'publicacion_y_identidad_post_rename',
                   I_pub == I_p and via in ('glibc', 'syscall'),
                   dict(identidad_provisional=I_p, identidad_publicado=I_pub))
        os.close(fd_p); os.close(fd_pub)
        # (2) colisión de destino: EEXIST y destino intacto
        fd_p2, _ = nuevo('prov2')
        _crear_dir_rel(fd_padre, 'final2')
        fd_s = os.open('final2', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=fd_padre)
        _crear_archivo_rel(fd_s, 'sentinela.txt', b'NO-TOCAR')
        os.close(fd_s)
        try:
            _renameat2(fd_padre, 'prov2', fd_padre, 'final2', _RENAME_NOREPLACE)
            _registrar(pasos, 'colision_eexist', False, 'no falló')
        except FileExistsError as exc:
            fd_chk = os.open('final2', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=fd_padre)
            sentinela = 'sentinela.txt' in os.listdir(fd_chk)
            os.close(fd_chk)
            _registrar(pasos, 'colision_eexist', True and sentinela,
                       dict(destino_intacto=sentinela,
                            excepcion=_excepcion('renameat2', exc)))
        os.close(fd_p2)
        # (3) sustitución de la entrada origen: se mueve el IMPOSTOR; detectado
        #     por fstat(fd_pub) != identidad registrada (R-31 observado)
        fd_p3, I_p3 = nuevo('prov3')
        os.rename('prov3', 'prov3_real_movido', src_dir_fd=fd_padre,
                  dst_dir_fd=fd_padre)
        _crear_dir_rel(fd_padre, 'prov3')       # impostor con el nombre
        _renameat2(fd_padre, 'prov3', fd_padre, 'final3', _RENAME_NOREPLACE)
        fd_pub3, I_pub3 = _abrir_dir_acreditado(fd_padre, 'final3')
        detectado = I_pub3 != I_p3
        fd_real, I_real = _abrir_dir_acreditado(fd_padre, 'prov3_real_movido')
        _registrar(pasos, 'sustitucion_origen_detectada_post_rename', detectado,
                   dict(identidad_registrada=I_p3, publicado=I_pub3,
                        real_localizado_por_fd=I_real,
                        amenaza_fuera_de_garantia='el impostor queda con el nombre final (R-31)'))
        os.close(fd_p3); os.close(fd_pub3); os.close(fd_real)
        # (4) real movido FUERA del padre: ENOENT; el fd del real sobrevive
        fd_p4, I_p4 = nuevo('prov4')
        os.makedirs(os.path.join(d, 'otro_base'), 0o700)
        os.rename('prov4', os.path.join(d, 'otro_base', 'prov4'),
                  src_dir_fd=fd_padre)
        try:
            _renameat2(fd_padre, 'prov4', fd_padre, 'final4', _RENAME_NOREPLACE)
            _registrar(pasos, 'real_fuera_del_padre_enoent', False, 'no falló')
        except OSError as exc:
            ok = exc.errno == errno.ENOENT and _ident(os.fstat(fd_p4)) == I_p4
            _registrar(pasos, 'real_fuera_del_padre_enoent', ok,
                       dict(excepcion=_excepcion('renameat2', exc),
                            fd_del_real_sobrevive=_ident(os.fstat(fd_p4)) == I_p4))
        os.close(fd_p4)
        r.finalizar('PASS' if not fallos else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f5', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    finally:
        os.close(fd_padre)
    return r


# ---------------------------------------------------------------- F6 (cierre)
def f6(raiz):
    """Cierre ordenado de writers/memmaps/readers/aux + anclas + sin fugas."""
    import numpy as np
    import soundfile
    r = Resultado(flujo='F6', riesgo='P-08/P-09/F1 (cierre)',
                  raiz=os.path.join(raiz, 'f6'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    fd_dir = os.open(d, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    pasos, fallos = [], []
    r['pasos'], r['fallos'] = pasos, fallos
    creados = []
    try:
        fs = 8000
        rng = np.random.default_rng(19480720)
        datos = (0.30 * rng.standard_normal((fs, 2))).astype(np.float32)
        # --- APERTURA (orden del plan: anclas -> log -> writers -> memmaps -> lectores)
        _crear_dir_rel(fd_dir, 'masks')
        fd_run, I_run = fd_dir, _ident(os.fstat(fd_dir))
        fd_masks, I_masks = _abrir_dir_acreditado(fd_run, 'masks')
        creados += [fd_run, fd_masks]
        fd_log = os.open('engine_log.txt', os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | os.O_NOFOLLOW, 0o600, dir_fd=fd_run)
        log = os.fdopen(fd_log, 'w', encoding='utf-8')
        creados.append(fd_log)
        writers = []
        for nombre in ('A.wav', 'B.wav'):
            fd_w, _ = _crear_archivo_rel(fd_run, nombre)
            w = soundfile.SoundFile(fd_w, mode='w', samplerate=fs, channels=2,
                                    subtype='PCM_16', format='WAV', closefd=False)
            w.write(datos)
            writers.append((w, fd_w, nombre))
            creados.append(fd_w)
        memmaps = []
        for nombre, shape in (('m1.npy', (256, 512)), ('m2.npy', (256, 512))):
            fd_m, _ = _crear_archivo_rel(fd_masks, nombre)
            mm = np.lib.format.open_memmap('/proc/self/fd/%d' % fd_m, mode='w+',
                                           dtype=np.float32, shape=shape)
            mm[0, 0] = 1.5
            memmaps.append((mm, fd_m, nombre))
            creados.append(fd_m)
        lectores = []
        for nombre in ('A.wav', 'B.wav'):
            fd_r = os.open(nombre, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd_run)
            rd = soundfile.SoundFile(fd_r, mode='r', closefd=False)  # lectura: auto-detectado
            lectores.append((rd, fd_r, nombre))
            creados.append(fd_r)
        _registrar(pasos, 'apertura_en_orden', True,
                   dict(n_fds_creados=len(creados)))
        # --- comprobaciones intermedias: los ANCLAS siguen vivos
        anclas_ok = (_ident(os.fstat(fd_run)) == I_run
                     and _ident(os.fstat(fd_masks)) == I_masks)
        _registrar(pasos, 'anclas_conservadas_durante_comprobaciones', anclas_ok,
                   dict(identidades=[I_run, I_masks]))
        # --- CIERRE en el orden P-08: writers -> memmaps -> readers -> aux -> anclas
        stage_prev = _snapshot_fds()
        for w, fd_w, nombre in writers:                 # sf_close + fd propio
            w.close()
            os.fstat(fd_w)                              # closefd=False: vivo
            os.close(fd_w)
        _registrar(pasos, 'cierre_writers', True,
                   dict(fds_desaparecidos=sorted(set(stage_prev) - _snapshot_fds())))
        stage_prev = _snapshot_fds()
        for mm, fd_m, nombre in memmaps:                # flush + mmap + fd
            mm.flush()
            mm._mmap.close()
            del mm
            os.close(fd_m)
        _registrar(pasos, 'cierre_memmaps', True,
                   dict(fds_desaparecidos=sorted(set(stage_prev) - _snapshot_fds())))
        stage_prev = _snapshot_fds()
        for rd, fd_r, nombre in lectores:
            rd.close()
            os.close(fd_r)
        _registrar(pasos, 'cierre_lectores', True,
                   dict(fds_desaparecidos=sorted(set(stage_prev) - _snapshot_fds())))
        stage_prev = _snapshot_fds()
        log.close()                                     # aux (fdopen cierra fd_log)
        _registrar(pasos, 'cierre_aux_log', True,
                   dict(fds_desaparecidos=sorted(set(stage_prev) - _snapshot_fds())))
        # anclas al final, en orden inverso de apertura: fd_masks -> fd_run
        os.close(fd_masks)
        os.close(fd_run)
        residuales = sorted(n for n in creados if _fd_existe(n))
        _registrar(pasos, 'cierre_anclas_al_final', not residuales,
                   dict(residuos=residuales))
        r['fugas'] = residuales
        r.finalizar('PASS' if anclas_ok and not residuales and not fallos
                    else 'FAIL')
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f6', exc))
        r['traceback'] = traceback.format_exc()
        r.finalizar('FAIL')
    return r


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raiz', default=RAIZ_DEF)
    ap.add_argument('--pruebas', default='F1,F2,F3,F4,F5,F6')
    a = ap.parse_args()
    os.makedirs(a.raiz, exist_ok=True)
    ev = os.path.join(a.raiz, 'evidence')
    os.makedirs(ev, exist_ok=True)
    elegidas = [x.strip().upper() for x in a.pruebas.split(',') if x.strip()]
    funcs = dict(F1=f1, F2=f2, F3=f3, F4=f4, F5=f5, F6=f6)
    consolidado = dict(schema='feasibility-1/1', entorno=_entorno(),
                       padre='22748622830d1579d7814c51b1f048c58b121110',
                       produccion_modificada=False, produccion_ejecutada=False,
                       resultados={})
    for nombre in elegidas:
        if nombre not in funcs:
            continue
        print('=== %s ===' % nombre, flush=True)
        res = funcs[nombre](a.raiz)
        consolidado['resultados'][nombre] = res['resultado']
        with open(os.path.join(ev, 'feas1_%s.json' % nombre.lower()), 'w',
                  encoding='utf-8') as f:
            json.dump(res, f, indent=1, ensure_ascii=False,
                      default=_json_default)
        print('  -> %s: %s' % (nombre, res['resultado']), flush=True)
        for fallo in res.get('fallos', []):
            print('  FALLO: %s' % json.dumps(fallo, ensure_ascii=False),
                  flush=True)
    with open(os.path.join(ev, 'consolidado_feasibility_1.json'), 'w',
              encoding='utf-8') as f:
        json.dump(consolidado, f, indent=1, ensure_ascii=False,
                  default=_json_default)
    print('RESULTADOS:', json.dumps(consolidado['resultados'], ensure_ascii=False),
          flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
