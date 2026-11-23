#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FEASIBILITY-1-R1 (6G.1) — Rectificación metodológica del arnés y repetición de
las pruebas F1..F6 de validación empírica AISLADA de los mecanismos del plan
Hardened FLOW-1..4 v2.3.

Autorización: Cris (padre a94f50793dfa97bb7074bb3e20fe2d42c3306596).
REGLAS: este arnés NO importa ni ejecuta código de producción (motores/,
lectura_segura_6g1.py); implementa los mecanismos de forma independiente en un
espacio aislado (/tmp/feas1_6g1 por defecto).

Correcciones R1..R6 respecto de la versión a94f507:
- R1: veredicto global AGREGADO a partir de subpasos obligatorios booleanos;
  excepción inesperada => FAIL; UNKNOWN sólo con condición explícita justificada.
- R2: libro mayor (ledger) de TODOS los descriptores abiertos (propios,
  duplicados, cerrados por biblioteca/fdopen), cierre explícito y verificación
  de cada cierre por stat directo de /proc/self/fd/N (sin fd de listado).
- R3: F2 separado en parte procfs (UNKNOWN justificado si no está montado) y
  variante sin procfs que se ejecuta SIEMPRE bajo un GUARDIÁN que rechaza
  cualquier consulta a /proc/self/fd; el escenario «procfs realmente ausente»
  se declara no reproducible aquí (no equivale al mecanismo).
- R4: F3 compara MUESTRAS leídas vs sintéticas con tolerancia PCM_16 justificada.
- R5: F4 separa limpieza NOMINAL (v2.3, por descriptor del padre acreditado) de
  los escenarios de sustitución por symlink (fallo seguro + ajeno intacto).
- R6: F1 valida identidades en el descenso (obligatorio); F5 agrega todos sus
  controles al veredicto; R-31 se conserva como observación, no como garantía.
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
def _fd_existe(n):
    """¿Existe /proc/self/fd/N? — vía stat directo (sin abrir fd de listado)."""
    try:
        os.stat('/proc/self/fd/%d' % n)
        return True
    except OSError:
        return False


def _snapshot_fds():
    """Listado de /proc/self/fd (incluye el fd transitorio del listado)."""
    try:
        return set(os.listdir('/proc/self/fd'))
    except OSError as exc:
        return set(['ERROR:%s' % exc])


def _ident(st):
    return [st.st_dev, st.st_ino]          # lista (JSON-serializable)


def _crear_archivo_rel(padre_fd, nombre, contenido=b'', escritura=False):
    """openat O_CREAT|O_EXCL|O_NOFOLLOW relativo a un dirfd acreditado.
    escritura=True usa O_RDWR (necesario para mmap ACCESS_WRITE — observado)."""
    rw = os.O_RDWR if escritura else os.O_WRONLY
    fd = os.open(nombre, rw | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=padre_fd)
    if contenido:
        os.write(fd, contenido)
    return fd, _ident(os.fstat(fd))


def _registrar(pasos, nombre, ok, detalle, obligatorio=True):
    pasos.append(dict(paso=nombre, ok=bool(ok), obligatorio=bool(obligatorio),
                      detalle=detalle))


def _excepcion(nombre, exc):
    return dict(paso=nombre, excepcion=type(exc).__name__, mensaje=str(exc),
                errno=getattr(exc, 'errno', None))


def _json_default(o):
    if isinstance(o, bytes):
        return o.decode('utf-8', 'replace')
    if hasattr(o, 'item'):
        return o.item()
    if isinstance(o, tuple):
        return list(o)
    return str(o)


class Ledger:
    """Libro mayor de descriptores del arnés (R2).

    tipos: 'propio' (abierto y cerrado por el arnés),
           'duplicado' (os.dup; cerrado por fdopen),
           'fdopen_cierra' (os.fdopen sobre fd propio: la biblioteca cierra),
           'biblioteca_cierra' (cerrado por una biblioteca, p. ej. closefd=True).
    """
    ESTADOS_ABIERTO = ('abierto',)
    ESTADOS_CERRADO = ('cerrado', 'cerrado_por_fdopen', 'cerrado_por_biblioteca')

    def __init__(self):
        self.items = []

    def abrir(self, etiqueta, fd, tipo='propio'):
        if not isinstance(fd, int) or fd < 0:
            raise OSError('fd inválido al registrar %s: %r' % (etiqueta, fd))
        self.items.append(dict(etiqueta=etiqueta, fd=fd, tipo=tipo,
                               estado='abierto'))
        return fd

    def cerrar(self, fd, estado='cerrado'):
        for it in self.items:
            if it['fd'] == fd and it['estado'] in self.ESTADOS_ABIERTO:
                os.close(fd)
                it['estado'] = estado
                return
        raise OSError('cierre de fd no registrado o ya cerrado: %r' % fd)

    def marcar_cerrado(self, fd, estado):
        for it in self.items:
            if it['fd'] == fd and it['estado'] in self.ESTADOS_ABIERTO:
                it['estado'] = estado
                return
        raise OSError('marcado de fd no registrado: %r' % fd)

    def pendientes(self):
        return [dict(it) for it in self.items if it['estado'] in self.ESTADOS_ABIERTO]

    def verificar(self):
        """Cada item cerrado debe haber desaparecido de /proc/self/fd;
        cada item abierto es un residuo. Devuelve (ok, detalles)."""
        detalles, ok = [], True
        for it in self.items:
            if it['estado'] in self.ESTADOS_CERRADO:
                vivo = _fd_existe(it['fd'])
                ok = ok and not vivo
                detalles.append(dict(it, existe_tras_cierre=vivo))
            else:
                ok = False
                detalles.append(dict(it, residuo=True))
        return ok, detalles


def _agregar_veredicto(r, pasos, condicion_unknown=None, nota=''):
    """R1: veredicto global a partir de los subpasos obligatorios."""
    fallidos = [p['paso'] for p in pasos if p.get('obligatorio') and not p['ok']]
    r['obligatorios_fallidos'] = fallidos
    if condicion_unknown:
        return r.finalizar('UNKNOWN', condicion_unknown)
    if fallidos:
        return r.finalizar('FAIL',
                           'subpasos obligatorios fallidos: ' + ', '.join(fallidos))
    return r.finalizar('PASS', nota)


def _entorno():
    import numpy
    import soundfile
    return dict(python=sys.version.split()[0], kernel=platform.release(),
                maquina=platform.machine(), plataforma=platform.platform(),
                numpy=numpy.__version__, soundfile=soundfile.__version__,
                libsndfile=soundfile.__libsndfile_version__,
                euid=os.geteuid(),
                ts=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))


# ---------------------------------------------------------------- F1 (R-13)
def f1(raiz):
    """R-13: subdirectorios candidates de DOS niveles por descriptores (R6)."""
    r = Resultado(flujo='F1', riesgo='R-13', raiz=os.path.join(raiz, 'f1'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    try:
        fd_base = led.abrir('fd_base', os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                               | os.O_NOFOLLOW))
        I_base = _ident(os.fstat(fd_base))
        _registrar(pasos, 'base_acreditada', True, dict(identidad=I_base))
        # candidates/ relativo a fd_base + apertura/acreditación
        os.mkdir('candidates', 0o700, dir_fd=fd_base)
        fd_cand = led.abrir('fd_candidates',
                            os.open('candidates', os.O_RDONLY | os.O_DIRECTORY
                                    | os.O_NOFOLLOW, dir_fd=fd_base))
        I_cand = _ident(os.fstat(fd_cand))
        _registrar(pasos, 'candidates_creado_y_acreditado', True,
                   dict(identidad=I_cand))
        # grupos de dos niveles, componente a componente
        grupos = ['individual_gp01', 'consensus_confidence_weighted_mean']
        identidades = {}
        for g in grupos:
            os.mkdir(g, 0o700, dir_fd=fd_cand)
            fd_g = led.abrir('fd_%s' % g,
                             os.open(g, os.O_RDONLY | os.O_DIRECTORY
                                     | os.O_NOFOLLOW, dir_fd=fd_cand))
            identidades[g] = _ident(os.fstat(fd_g))
            fd_a, _ = _crear_archivo_rel(fd_g, 'salida.wav', b'RIFF....WAVE')
            led.abrir('dato_salida_%s' % g, fd_a)
            led.cerrar(fd_a)
            _registrar(pasos, 'grupo_%s' % g, True,
                       dict(identidad=identidades[g],
                            creado='salida.wav via openat O_EXCL'))
        r['identidades'] = dict(base=I_base, candidates=I_cand,
                                grupos=identidades)
        # entradas inesperadas ANTES del descenso (symlink a un dir REAL existente)
        os.makedirs(os.path.join(d, 'fuera'), 0o700)
        fd_s, _ = _crear_archivo_rel(fd_cand, 'suelto.txt', b'u')
        led.abrir('dato_suelto', fd_s)
        led.cerrar(fd_s)
        os.symlink(os.path.join(d, 'fuera'), 'evil', dir_fd=fd_cand)
        # descenso/verificación SIN rutas nominales + VALIDACIÓN DE IDENTIDADES (R6)
        listado = sorted(os.listdir(fd_cand))
        verif = {}
        for nombre in listado:
            st = os.lstat(nombre, dir_fd=fd_cand)
            if stat.S_ISDIR(st.st_mode) and nombre in identidades:
                fd_x = led.abrir('tmp_verif_%s' % nombre,
                                 os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                                         | os.O_NOFOLLOW, dir_fd=fd_cand))
                I_x = _ident(os.fstat(fd_x))
                led.cerrar(fd_x)
                verif[nombre] = dict(tipo='dir',
                                     identidad_ok=I_x == identidades[nombre])
            elif stat.S_ISLNK(st.st_mode):
                verif[nombre] = dict(tipo='symlink')
            else:
                verif[nombre] = dict(tipo='regular_inesperado')
        identidades_validadas = all(verif[g]['identidad_ok'] for g in grupos)
        _registrar(pasos, 'descenso_sin_rutas_e_identidades_validadas',
                   identidades_validadas,
                   dict(listado=listado, verificacion=verif))
        # negativos: symlink rechazado al abrir con O_NOFOLLOW (errno observado)
        try:
            os.open('evil', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=fd_cand)
            _registrar(pasos, 'symlink_rechazado', False, 'la apertura NO falló')
        except OSError as exc:
            _registrar(pasos, 'symlink_rechazado', True,
                       _excepcion('open evil (objetivo real existente)', exc))
        inesperados = sorted(n for n, v in verif.items() if v['tipo'] != 'dir')
        _registrar(pasos, 'entradas_inesperadas_clasificadas',
                   inesperados == ['evil', 'suelto.txt'],
                   dict(inesperados=inesperados))
        # sustitución misma-uid del nombre de un grupo (el fd sigue designando el real)
        g0 = 'individual_gp01'
        os.rename(g0, g0 + '_movido', src_dir_fd=fd_cand, dst_dir_fd=fd_cand)
        os.mkdir(g0, 0o700, dir_fd=fd_cand)          # impostor con el nombre original
        fd_g0 = next(it['fd'] for it in led.items if it['etiqueta'] == 'fd_%s' % g0)
        I_fd = _ident(os.fstat(fd_g0))
        st_nombre = os.lstat(g0, dir_fd=fd_cand)
        _registrar(pasos, 'sustitucion_detectada_por_identidad',
                   I_fd != _ident(st_nombre),
                   dict(fd_designa=I_fd, nombre_actual=_ident(st_nombre),
                        real_conservado='fd sigue designando el inodo original'))
        # cierre ordenado (inverso de apertura) + verificación por descriptor
        orden = [('fd_%s' % g, None) for g in reversed(grupos)]
        for etiqueta, _f in orden:
            fd_x = next(it['fd'] for it in led.items if it['etiqueta'] == etiqueta)
            led.cerrar(fd_x)
        led.cerrar(fd_cand)
        led.cerrar(fd_base)
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_ordenado_y_sin_fugas', ok_ledger,
                   dict(cerrados=len(det_ledger), residuos=led.pendientes()))
        _agregar_veredicto(r, pasos)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f1', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
    return r


# ---------------------------------------------------------------- F2 (R-29)
def _guardian_sin_procfs():
    """Parchea os.open/os.stat/os.listdir para RECHAZAR rutas de /proc/self/fd.

    Devuelve (restaurador, disparos). R3: la variante sin procfs debe poder
    ejecutarse sin consultar procfs; el guardián lo comprueba en runtime."""
    disparos = []
    real = dict(open=os.open, stat=os.stat, listdir=os.listdir)

    def _guard(nombre):
        fn = real[nombre]

        def w(path, *a, **k):
            if '/proc/self/fd' in str(path):
                disparos.append(dict(funcion=nombre, ruta=str(path)))
                raise RuntimeError('FEASIBILITY-1-R1/Guardian: consulta a '
                                   'procfs prohibida en la variante sin procfs')
            return fn(path, *a, **k)
        return w
    os.open, os.stat, os.listdir = (_guard('open'), _guard('stat'),
                                    _guard('listdir'))

    def restaurar():
        os.open, os.stat, os.listdir = real['open'], real['stat'], real['listdir']
    return restaurar, disparos


def f2(raiz):
    """R-29: parte A procfs (si está montado) + parte B variante SIN procfs."""
    import numpy as np
    r = Resultado(flujo='F2', riesgo='R-29', raiz=os.path.join(raiz, 'f2'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    cond_unknown = None
    try:
        procfs_disponible = os.path.isdir('/proc/self/fd')
        _registrar(pasos, 'procfs_disponible_en_el_entorno', procfs_disponible,
                   dict(entradas=len(_snapshot_fds()) if procfs_disponible else None),
                   obligatorio=False)
        fd_dir = led.abrir('fd_base', os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                              | os.O_NOFOLLOW))
        # -------- PARTE A: procfs (sólo si está montado) --------
        if procfs_disponible:
            ruta = os.path.join(d, 'objeto.txt')
            fd0, I0 = _crear_archivo_rel(fd_dir, 'objeto.txt', b'payload-feas1')
            led.abrir('objeto_txt', fd0)
            magic = led.abrir('magic_link',
                              os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY))
            I_magic = _ident(os.fstat(magic))
            contenido = os.read(magic, 64)
            led.cerrar(magic)
            _registrar(pasos, 'A_magic_link_designa_el_objeto',
                       I_magic == I0 and contenido == b'payload-feas1',
                       dict(identidad_fd=I0, identidad_magic=I_magic))
            os.unlink(ruta)                       # el objeto sigue vivo por fd
            magic2 = led.abrir('magic_link_2',
                               os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY))
            contenido2 = os.read(magic2, 64)
            led.cerrar(magic2)
            _registrar(pasos, 'A_objeto_vivo_sin_ruta_nominal',
                       contenido2 == b'payload-feas1',
                       dict(leido_tras_unlink=contenido2.decode('utf-8',
                                                                'replace')))
            led.cerrar(fd0)
            try:
                os.open('/proc/self/fd/%d' % fd0, os.O_RDONLY)
                _registrar(pasos, 'A_fd_cerrado_magic_desaparece', False,
                           'no falló')
            except OSError as exc:
                _registrar(pasos, 'A_fd_cerrado_magic_desaparece', True,
                           _excepcion('open magic tras close', exc))
        else:
            cond_unknown = ('procfs no está montado en este entorno: la parte A '
                            '(magic-link) no es probable aquí; la parte B se '
                            'ejecuta de todos modos')
        # -------- PARTE B: variante SIN procfs (SIEMPRE, con guardián) --------
        fd_n, I_n = _crear_archivo_rel(fd_dir, 'alt.npy', escritura=True)
        led.abrir('alt_npy', fd_n)
        fo = os.fdopen(fd_n, 'r+b', closefd=False)   # el arnés cierra fo
        shape = (256, 512)
        restaurar, disparos = _guardian_sin_procfs()
        try:
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
            del mm
        except BaseException:
            restaurar()
            raise
        restaurar()
        _registrar(pasos, 'B_variante_sin_consultar_procfs_guardian', not disparos,
                   dict(disparos=disparos,
                       mecanismo='np.lib.format.write_array_header_1_0 + '
                                 'np.memmap(file object, r+, offset)'))
        fo.close()
        I_n2 = _ident(os.fstat(fd_n))
        _fd_dup = led.abrir('dup_verificacion', os.dup(fd_n), tipo='duplicado')
        # el DUP comparte la descripción abierta (offset) con fd_n: rebobinar
        os.lseek(_fd_dup, 0, os.SEEK_SET)
        chk = np.lib.format.read_array(os.fdopen(_fd_dup, 'rb', closefd=True))
        led.marcar_cerrado(_fd_dup, 'cerrado_por_fdopen')
        led.cerrar(fd_n)
        ok_b = (I_n == I_n2 and chk.shape == shape
                and int(chk[7, 9]) == 7 * 512 + 9)
        _registrar(pasos, 'B_alternativa_sin_procfs_contenido_e_identidad', ok_b,
                   dict(identidad_antes=I_n, identidad_despues=I_n2,
                        forma=list(chk.shape), valor=chk[7, 9].item()))
        led.cerrar(fd_dir)
        # escenario NO reproducible aquí (declaración expresa, R3)
        _registrar(pasos, 'escenario_procfs_realemente_ausente', False,
                   dict(reproducido=False,
                        razon='/proc está montado en este sandbox; la ausencia '
                              'REAL de procfs no puede demostrarse aquí; el '
                              'mecanismo B se probó SIN CONSULTAR procfs '
                              '(guardián), que NO es equivalente a ejecutar '
                              'con procfs ausente'),
                   obligatorio=False)
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_y_verificacion_de_todos_los_fds', ok_ledger,
                   dict(fds_registrados=len(det_ledger),
                        residuos=led.pendientes()))
        _agregar_veredicto(r, pasos, cond_unknown)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f2', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
    return r


# ---------------------------------------------------------------- F3 (R-34)
def f3(raiz):
    """R-34: soundfile por descriptor (R4: contenido PCM_16) y numpy memmap."""
    import numpy as np
    import soundfile
    r = Resultado(flujo='F3', riesgo='R-34', raiz=os.path.join(raiz, 'f3'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    try:
        fs = 44100
        rng = np.random.default_rng(20261122)
        # fixture ACOTADO al rango PCM_16: libsndfile RECORTA float >1.0 al
        # convertir a PCM_16 (observado: max_abs_diff 0.416 con ruido sin clip),
        # por eso el contenido esperado es la señal recortada a [-0.999, 0.999]
        datos = (0.30 * rng.standard_normal((fs, 2))).astype(np.float32)
        np.clip(datos, -0.999, 0.999, out=datos)
        fd_dir = led.abrir('fd_base', os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                              | os.O_NOFOLLOW))
        # (a) escritor por descriptor con closefd=False (+format exigido por fd)
        fd_w, I1 = _crear_archivo_rel(fd_dir, 'salida.wav', escritura=False)
        led.abrir('wav_fd_escritor', fd_w)
        w = soundfile.SoundFile(fd_w, mode='w', samplerate=fs, channels=2,
                                subtype='PCM_16', format='WAV', closefd=False)
        w.write(datos)
        w.close()                                   # cierra sf, NO nuestro fd
        I2 = _ident(os.fstat(fd_w))
        _registrar(pasos, 'sf_escritor_fd_closefd_false_identidad', I1 == I2,
                   dict(identidad_antes=I1, identidad_despues=I2,
                        fd_sigue_abierto_tras_sf_close=True,
                        nota='format="WAV" obligatorio al abrir por fd en '
                             'escritura (observado)'))
        # (b) lectura por descriptor + COMPARACIÓN DE CONTENIDO (R4)
        fd_r = led.abrir('wav_fd_lector',
                         os.open('salida.wav', os.O_RDONLY | os.O_NOFOLLOW,
                                 dir_fd=fd_dir))
        rd = soundfile.SoundFile(fd_r, mode='r', closefd=False)  # auto-detecta
        leido = rd.read(dtype='float32', always_2d=True)
        rd.close()
        led.cerrar(fd_r)
        esperado = np.clip(datos, -0.999, 0.999)   # lo que PCM_16 puede representar
        max_diff = float(np.max(np.abs(leido - esperado)))
        # PCM_16: error de cuantización <= medio LSB (1/65536); cota conservadora 1 LSB
        tolerancia = 1.0 / 32768.0
        _registrar(pasos, 'sf_lector_fd_forma', leido.shape == datos.shape,
                   dict(frames=leido.shape[0], canales=leido.shape[1]))
        _registrar(pasos, 'sf_contenido_coincide_cuantizacion_pcm16',
                   max_diff <= tolerancia,
                   dict(max_abs_diff=max_diff, tolerancia=tolerancia,
                        justificacion='PCM_16: redondeo <= medio LSB '
                                      '(1/65536); cota conservadora 1 LSB'))
        led.cerrar(fd_w)
        # (c) comportamiento observado con closefd=True (por defecto)
        fd_t, _ = _crear_archivo_rel(fd_dir, 'tmp_closefd.wav', escritura=False)
        led.abrir('wav_tmp_closefd_true', fd_t)
        wt = soundfile.SoundFile(fd_t, mode='w', samplerate=fs, channels=2,
                                 subtype='PCM_16', format='WAV')  # closefd=True
        wt.write(datos[:100])
        wt.close()
        try:
            os.fstat(fd_t)
            _registrar(pasos, 'sf_closefd_true_cierra_fd', False,
                       'el fd sigue abierto (esperado: cerrado por libsndfile)')
        except OSError as exc:
            ok = exc.errno == errno.EBADF
            if ok:
                led.marcar_cerrado(fd_t, 'cerrado_por_biblioteca')
            _registrar(pasos, 'sf_closefd_true_cierra_fd', ok,
                       _excepcion('fstat tras sf.close (closefd=True)', exc))
        # (d) numpy: open_memmap vía /proc/self/fd con fd retenido (parte procfs)
        fd_m, I3 = _crear_archivo_rel(fd_dir, 'mask.npy', escritura=True)
        led.abrir('mask_npy', fd_m)
        shape = (1024, 2048)
        mm = np.lib.format.open_memmap('/proc/self/fd/%d' % fd_m, mode='w+',
                                       dtype=np.float32, shape=shape)
        mm[100, 200] = 3.25
        mm.flush()
        del mm
        I4 = _ident(os.fstat(fd_m))
        led.cerrar(fd_m)
        fd_chk = led.abrir('mask_npy_verif',
                           os.open('mask.npy', os.O_RDONLY | os.O_NOFOLLOW,
                                   dir_fd=fd_dir))
        fd_dup = led.abrir('dup_mask_verif', os.dup(fd_chk), tipo='duplicado')
        chk = np.lib.format.read_array(os.fdopen(fd_dup, 'rb', closefd=True))
        led.marcar_cerrado(fd_dup, 'cerrado_por_fdopen')  # fdopen cerró el DUP
        _registrar(pasos, 'open_memmap_via_procfs_fd_retenido',
                   I3 == I4 and float(chk[100, 200]) == 3.25,
                   dict(identidad_antes=I3, identidad_despues=I4,
                        valor=chk[100, 200].item()))
        led.cerrar(fd_chk)
        led.cerrar(fd_dir)
        # (e) ledger completo
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_y_verificacion_de_todos_los_fds', ok_ledger,
                   dict(fds_registrados=len(det_ledger),
                        residuos=led.pendientes()))
        _agregar_veredicto(r, pasos)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f3', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
    return r


# ---------------------------------------------------------------- F4 (R-28/R5)
def f4(raiz):
    """P-08/R-28: limpieza masks (R5: escenarios nominal / symlink / errores)."""
    r = Resultado(flujo='F4', riesgo='P-08/R-28', raiz=os.path.join(raiz, 'f4'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    try:
        fd_dir = led.abrir('fd_base_publicado',
                           os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                   | os.O_NOFOLLOW))
        # ---- ESCENARIO A: limpieza NOMINAL del plan v2.3 (paso 5bis) ----
        os.mkdir('masks', 0o700, dir_fd=fd_dir)
        fd_masks = led.abrir('fd_masks_A',
                             os.open('masks', os.O_RDONLY | os.O_DIRECTORY
                                     | os.O_NOFOLLOW, dir_fd=fd_dir))
        I_masks = _ident(os.fstat(fd_masks))
        nombres = ['a.npy', 'b.npy', 'c.npy']
        for n in nombres:
            fd_a, _ = _crear_archivo_rel(fd_masks, n, b'x')
            led.abrir('dato_A_%s' % n, fd_a)
            led.cerrar(fd_a)
        for n in nombres:                            # unlinkat vía fd_masks
            os.unlink(n, dir_fd=fd_masks)
        vacio = os.listdir(fd_masks) == []
        _registrar(pasos, 'A_unlinkat_por_fd_masks', vacio,
                   dict(eliminadas=nombres, restantes=os.listdir(fd_masks)))
        os.rmdir('masks', dir_fd=fd_dir)             # rmdir vía descriptor del padre
        try:
            os.lstat('masks', dir_fd=fd_dir)
            eliminado_ok = False
        except FileNotFoundError:
            eliminado_ok = True
        fd_masks_vivo = _ident(os.fstat(fd_masks)) == I_masks
        led.cerrar(fd_masks)
        _registrar(pasos, 'A_rmdir_via_descriptor_del_padre_y_verificacion',
                   eliminado_ok and fd_masks_vivo,
                   dict(eliminado='masks',
                        nota='fd_dir asume aquí el rol del descriptor del padre '
                             'del publicado (fd_pub) del plan v2.3'))
        # ---- ESCENARIO B: sustitución del nombre por un symlink (fallo seguro) ----
        os.mkdir('masks2', 0o700, dir_fd=fd_dir)
        fd_masks2 = led.abrir('fd_masks_B',
                              os.open('masks2', os.O_RDONLY | os.O_DIRECTORY
                                      | os.O_NOFOLLOW, dir_fd=fd_dir))
        fd_e, _ = _crear_archivo_rel(fd_masks2, 'e1.npy', b'x')
        led.abrir('dato_B_e1', fd_e)
        led.cerrar(fd_e)
        ajeno = os.path.join(d, 'ajeno')
        os.makedirs(ajeno, 0o700)
        fd_aj = led.abrir('fd_ajeno', os.open(ajeno, os.O_RDONLY
                                              | os.O_DIRECTORY | os.O_NOFOLLOW))
        fd_da, _ = _crear_archivo_rel(fd_aj, 'del_ajeno.txt')
        led.abrir('dato_ajeno', fd_da)
        led.cerrar(fd_da)
        os.rename('masks2', 'masks2_real', src_dir_fd=fd_dir, dst_dir_fd=fd_dir)
        os.symlink(ajeno, 'masks2', dir_fd=fd_dir)   # sustitución misma-uid
        # B1: operación sobre el NOMBRE sustituido falla de forma segura
        ajeno_antes = sorted(os.listdir(fd_aj))
        try:
            os.rmdir('masks2', dir_fd=fd_dir)
            b1_ok, b1_exc = False, 'rmdir sobre symlink NO falló'
        except OSError as exc:
            b1_ok = ('del_ajeno.txt' in sorted(os.listdir(fd_aj)))
            b1_exc = _excepcion('rmdir masks2 (symlink)', exc)
        _registrar(pasos, 'B_rmdir_sobre_nombre_sustituido_falla_seguro',
                   b1_ok, dict(excepcion=b1_exc, ajeno_intacto=b1_ok,
                               errno_observado=b1_exc.get('errno')
                               if isinstance(b1_exc, dict) else None))
        # B2: apertura O_DIRECTORY|O_NOFOLLOW del nombre sustituido rechaza
        try:
            os.open('masks2', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=fd_dir)
            b2_ok, b2_exc = False, 'la apertura NO falló'
        except OSError as exc:
            b2_ok, b2_exc = True, _excepcion('open masks2 (symlink)', exc)
        _registrar(pasos, 'B_apertura_nofollow_del_nombre_sustituido_rechaza',
                   b2_ok, b2_exc)
        # B3: el REAL retenido por fd_masks2 NO se redirige
        _registrar(pasos, 'B_fd_masks2_no_redirigido',
                   sorted(os.listdir(fd_masks2)) == ['e1.npy'],
                   dict(contenido_via_fd=sorted(os.listdir(fd_masks2))))
        # B4: eliminación por fd del real + rmdir del real por el padre
        os.unlink('e1.npy', dir_fd=fd_masks2)
        os.rmdir('masks2_real', dir_fd=fd_dir)
        _registrar(pasos, 'B_eliminacion_por_fd_del_real_y_rmdir', True,
                   dict(eliminado='masks2_real vía descriptor del padre'))
        # B5: el symlink sigue presente y sigue siendo symlink
        st = os.lstat('masks2', dir_fd=fd_dir)
        _registrar(pasos, 'B_symlink_sustituto_presente_no_seguido',
                   stat.S_ISLNK(st.st_mode), dict(tipo='symlink'))
        # B6: unlinkat del ENLACE (no del destino) — remoción segura del link
        os.unlink('masks2', dir_fd=fd_dir)
        ajeno_despues = sorted(os.listdir(fd_aj))
        _registrar(pasos, 'B_unlinkat_elimina_el_enlace_no_el_destino',
                   'del_ajeno.txt' in ajeno_despues
                   and ajeno_antes == ajeno_despues,
                   dict(ajeno_antes=ajeno_antes, ajeno_despues=ajeno_despues))
        led.cerrar(fd_aj)
        led.cerrar(fd_masks2)
        # ---- ESCENARIO C: errores documentados ----
        os.mkdir('masks3', 0o700, dir_fd=fd_dir)
        fd_m3 = led.abrir('fd_masks_C',
                          os.open('masks3', os.O_RDONLY | os.O_DIRECTORY
                                  | os.O_NOFOLLOW, dir_fd=fd_dir))
        fd_c, _ = _crear_archivo_rel(fd_m3, 'queda.npy', b'x')
        led.abrir('dato_C', fd_c)
        led.cerrar(fd_c)
        try:
            os.rmdir('masks3', dir_fd=fd_dir)
            c1_ok, c1_exc = False, 'rmdir no vacío NO falló'
        except OSError as exc:
            c1_ok, c1_exc = exc.errno == errno.ENOTEMPTY, _excepcion('rmdir', exc)
        _registrar(pasos, 'C_rmdir_no_vacio_enotempty', c1_ok, c1_exc)
        try:
            os.unlink('no_esta.npy', dir_fd=fd_m3)
            c2_ok, c2_exc = False, 'unlink inexistente NO falló'
        except OSError as exc:
            c2_ok, c2_exc = exc.errno == errno.ENOENT, _excepcion('unlink', exc)
        _registrar(pasos, 'C_unlink_inexistente_enoent', c2_ok, c2_exc)
        led.cerrar(fd_m3)
        led.cerrar(fd_dir)      # ancla del árbol de la prueba
        # ---- ledger completo ----
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_y_verificacion_de_todos_los_fds', ok_ledger,
                   dict(fds_registrados=len(det_ledger),
                        residuos=led.pendientes()))
        _agregar_veredicto(r, pasos)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f4', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
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
    """R-D: renameat2 dirfd + acreditación post-rename (R6: veredicto agregado)."""
    r = Resultado(flujo='F5', riesgo='R-D (P-06)', raiz=os.path.join(raiz, 'f5'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    try:
        fd_padre = led.abrir('fd_padre', os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                                 | os.O_NOFOLLOW))

        def nuevo(nombre):
            os.mkdir(nombre, 0o700, dir_fd=fd_padre)
            fd_tmp = led.abrir('tmp_' + nombre,
                               os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                                       | os.O_NOFOLLOW, dir_fd=fd_padre))
            fd_d, _ = _crear_archivo_rel(fd_tmp, 'dato.txt', b'v')
            led.abrir('dato_' + nombre, fd_d)
            led.cerrar(fd_d)
            led.cerrar(fd_tmp)
            fd_p = led.abrir('prov_' + nombre,
                             os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                                     | os.O_NOFOLLOW, dir_fd=fd_padre))
            return fd_p, _ident(os.fstat(fd_p))
        # disponibilidad: la syscall se EJECUTA (ENOENT = disponible);
        # sólo ENOSYS/arquitectura sin soporte => UNKNOWN
        cond_unknown = None
        try:
            _renameat2(None, 'no_existe_a', None, 'no_existe_b', 0)
            _registrar(pasos, 'renameat2_disponible', True,
                       dict(via='glibc/syscall (probe ENOENT = ejecutada)'))
        except OSError as exc:
            if exc.errno == errno.ENOSYS or 'indisponible' in str(exc):
                cond_unknown = 'renameat2 no disponible en este entorno'
                _registrar(pasos, 'renameat2_disponible', False,
                           _excepcion('probe', exc))
            else:
                _registrar(pasos, 'renameat2_disponible', True,
                           dict(via='probe con error esperado',
                                excepcion=_excepcion('probe', exc)))
        # (1) publicación normal + identidad post-rename
        fd_p1, I_p1 = nuevo('prov1')
        via = _renameat2(fd_padre, 'prov1', fd_padre, 'final1', _RENAME_NOREPLACE)
        fd_pub1 = led.abrir('pub_final1',
                            os.open('final1', os.O_RDONLY | os.O_DIRECTORY
                                    | os.O_NOFOLLOW, dir_fd=fd_padre))
        I_pub1 = _ident(os.fstat(fd_pub1))
        _registrar(pasos, 'publicacion_y_identidad_post_rename',
                   I_pub1 == I_p1 and via in ('glibc', 'syscall'),
                   dict(identidad_provisional=I_p1, identidad_publicado=I_pub1))
        led.cerrar(fd_p1)
        led.cerrar(fd_pub1)
        # (2) colisión de destino: EEXIST y destino intacto
        fd_p2, _ = nuevo('prov2')
        os.mkdir('final2', 0o700, dir_fd=fd_padre)
        fd_s = led.abrir('destino_final2',
                         os.open('final2', os.O_RDONLY | os.O_DIRECTORY
                                 | os.O_NOFOLLOW, dir_fd=fd_padre))
        fd_sent, _ = _crear_archivo_rel(fd_s, 'sentinela.txt', b'NO-TOCAR')
        led.abrir('sentinela', fd_sent)
        led.cerrar(fd_sent)
        try:
            _renameat2(fd_padre, 'prov2', fd_padre, 'final2', _RENAME_NOREPLACE)
            ok2, exc2, intacto = False, 'colisión NO falló', None
        except FileExistsError as exc:
            intacto = 'sentinela.txt' in os.listdir(fd_s)
            ok2, exc2 = intacto, _excepcion('renameat2 colisión', exc)
        _registrar(pasos, 'colision_eexist_destino_intacto', ok2,
                   dict(excepcion=exc2, destino_intacto=intacto))
        led.cerrar(fd_p2)
        led.cerrar(fd_s)
        # (3) sustitución de la entrada origen: se mueve el IMPOSTOR; detectado
        #     por fstat(fd_pub) != identidad registrada (R-31: observación, NO
        #     garantía de publicación atómica del objeto acreditado)
        fd_p3, I_p3 = nuevo('prov3')
        os.rename('prov3', 'prov3_real_movido', src_dir_fd=fd_padre,
                  dst_dir_fd=fd_padre)
        os.mkdir('prov3', 0o700, dir_fd=fd_padre)    # impostor con el nombre
        _renameat2(fd_padre, 'prov3', fd_padre, 'final3', _RENAME_NOREPLACE)
        fd_pub3 = led.abrir('pub_final3',
                            os.open('final3', os.O_RDONLY | os.O_DIRECTORY
                                    | os.O_NOFOLLOW, dir_fd=fd_padre))
        I_pub3 = _ident(os.fstat(fd_pub3))
        fd_real3 = led.abrir('real_movido',
                             os.open('prov3_real_movido', os.O_RDONLY
                                     | os.O_DIRECTORY | os.O_NOFOLLOW,
                                     dir_fd=fd_padre))
        I_real3 = _ident(os.fstat(fd_real3))
        _registrar(pasos, 'sustitucion_origen_detectada_post_rename',
                   I_pub3 != I_p3 and I_real3 == I_p3,
                   dict(identidad_registrada=I_p3, publicado_impostor=I_pub3,
                        real_localizado_por_fd=I_real3,
                        r31='el impostor queda con el nombre final; la detección '
                            'es POST-rename; NO es garantía de publicación '
                            'atómica por identidad del objeto original'))
        led.cerrar(fd_p3)
        led.cerrar(fd_pub3)
        led.cerrar(fd_real3)
        # (4) real movido FUERA del padre: ENOENT; el fd del real sobrevive
        fd_p4, I_p4 = nuevo('prov4')
        os.makedirs(os.path.join(d, 'otro_base'), 0o700)
        os.rename('prov4', os.path.join(d, 'otro_base', 'prov4'),
                  src_dir_fd=fd_padre)
        try:
            _renameat2(fd_padre, 'prov4', fd_padre, 'final4', _RENAME_NOREPLACE)
            ok4, exc4 = False, 'rename fuera-del-padre NO falló'
        except OSError as exc:
            ok4 = (exc.errno == errno.ENOENT
                   and _ident(os.fstat(fd_p4)) == I_p4)
            exc4 = _excepcion('renameat2 real fuera del padre', exc)
        _registrar(pasos, 'real_fuera_del_padre_enoent_fd_sobrevive', ok4,
                   dict(excepcion=exc4,
                        fd_del_real_sobrevive=_ident(os.fstat(fd_p4)) == I_p4))
        led.cerrar(fd_p4)
        # ---- ledger completo (incluye el ancla fd_padre) ----
        led.cerrar(fd_padre)
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_y_verificacion_de_todos_los_fds', ok_ledger,
                   dict(fds_registrados=len(det_ledger),
                        residuos=led.pendientes()))
        _agregar_veredicto(r, pasos, cond_unknown)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f5', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
    return r


# ---------------------------------------------------------------- F6 (cierre)
def f6(raiz):
    """Cierre ordenado (R2: etapas por fd conocido, sin diffs de listados)."""
    import numpy as np
    import soundfile
    r = Resultado(flujo='F6', riesgo='P-08/P-09/F1 (cierre)',
                  raiz=os.path.join(raiz, 'f6'))
    d = r['raiz']
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, 0o700)
    pasos, fallos, led = [], [], Ledger()
    r['pasos'], r['fallos'], r['ledger'] = pasos, fallos, None
    try:
        fs = 8000
        rng = np.random.default_rng(19480720)
        datos = (0.30 * rng.standard_normal((fs, 2))).astype(np.float32)
        # --- APERTURA (orden del plan: anclas -> log -> writers -> memmaps -> lectores)
        fd_run = led.abrir('ancla_fd_run',
                           os.open(d, os.O_RDONLY | os.O_DIRECTORY
                                   | os.O_NOFOLLOW))
        I_run = _ident(os.fstat(fd_run))
        os.mkdir('masks', 0o700, dir_fd=fd_run)
        fd_masks = led.abrir('ancla_fd_masks',
                             os.open('masks', os.O_RDONLY | os.O_DIRECTORY
                                     | os.O_NOFOLLOW, dir_fd=fd_run))
        I_masks = _ident(os.fstat(fd_masks))
        fd_log = led.abrir('engine_log', os.open('engine_log.txt',
                                                 os.O_WRONLY | os.O_CREAT
                                                 | os.O_EXCL | os.O_NOFOLLOW,
                                                 0o600, dir_fd=fd_run))
        log = os.fdopen(fd_log, 'w', encoding='utf-8')   # cerrará fd_log
        writers = []
        for nombre in ('A.wav', 'B.wav'):
            fd_w, _ = _crear_archivo_rel(fd_run, nombre, escritura=False)
            led.abrir('writer_%s' % nombre, fd_w)
            w = soundfile.SoundFile(fd_w, mode='w', samplerate=fs, channels=2,
                                    subtype='PCM_16', format='WAV',
                                    closefd=False)
            w.write(datos)
            writers.append((w, fd_w, nombre))
        memmaps = []
        for nombre, shape in (('m1.npy', (256, 512)), ('m2.npy', (256, 512))):
            fd_m, _ = _crear_archivo_rel(fd_masks, nombre, escritura=True)
            led.abrir('memmap_%s' % nombre, fd_m)
            mm = np.lib.format.open_memmap('/proc/self/fd/%d' % fd_m, mode='w+',
                                           dtype=np.float32, shape=shape)
            mm[0, 0] = 1.5
            memmaps.append((mm, fd_m, nombre))
        lectores = []
        for nombre in ('A.wav', 'B.wav'):
            fd_r = led.abrir('lector_%s' % nombre,
                             os.open(nombre, os.O_RDONLY | os.O_NOFOLLOW,
                                     dir_fd=fd_run))
            rd = soundfile.SoundFile(fd_r, mode='r', closefd=False)
            lectores.append((rd, fd_r, nombre))
        total_fds = len(led.items)
        _registrar(pasos, 'apertura_en_orden_y_registrada', total_fds == 9,
                   dict(n_fds_creados=total_fds,
                        tipos={it['etiqueta']: it['tipo'] for it in led.items}))
        # --- comprobaciones intermedias: los ANCLAS siguen vivos
        anclas_ok = (_ident(os.fstat(fd_run)) == I_run
                     and _ident(os.fstat(fd_masks)) == I_masks)
        _registrar(pasos, 'anclas_conservadas_durante_comprobaciones', anclas_ok,
                   dict(identidades=[I_run, I_masks]))
        # --- CIERRE en el orden P-08, verificando CADA fd por stat conocido
        def etapas(fds_cerrados, fds_restantes, etiqueta):
            desaparecidos = all(not _fd_existe(fd) for fd in fds_cerrados)
            permanecen = all(_fd_existe(fd) for fd in fds_restantes)
            _registrar(pasos, etiqueta, desaparecidos and permanecen,
                       dict(cerrados=len(fds_cerrados),
                            permanecen=len(fds_restantes)))
            return desaparecidos and permanecen
        fd_writers = [fd for _, fd, _ in writers]
        for w, fd_w, _n in writers:
            w.close()                                   # sf_close (cabecera)
            led.cerrar(fd_w)                            # nuestro fd sigue abierto
        etapas(fd_writers, [fd for _, fd, _ in memmaps]
               + [fd for _, fd, _ in lectores] + [fd_log, fd_masks, fd_run],
               'cierre_writers')
        fd_mms = [fd for _, fd, _ in memmaps]
        for mm, fd_m, _n in memmaps:
            mm.flush()
            mm._mmap.close()
            del mm
            led.cerrar(fd_m)
        etapas(fd_mms, [fd for _, fd, _ in lectores]
               + [fd_log, fd_masks, fd_run], 'cierre_memmaps')
        fd_rds = [fd for _, fd, _ in lectores]
        for rd, fd_r, _n in lectores:
            rd.close()
            led.cerrar(fd_r)
        etapas(fd_rds, [fd_log, fd_masks, fd_run], 'cierre_lectores')
        log.close()                                     # fdopen cierra fd_log
        led.marcar_cerrado(fd_log, 'cerrado_por_fdopen')
        etapas([fd_log], [fd_masks, fd_run], 'cierre_aux_log')
        # anclas al final, en orden inverso de apertura: fd_masks -> fd_run
        led.cerrar(fd_masks)
        led.cerrar(fd_run)
        ok_ledger, det_ledger = led.verificar()
        r['ledger'] = dict(items=det_ledger, residuos=led.pendientes())
        _registrar(pasos, 'cierre_anclas_al_final_y_verificacion_total',
                   ok_ledger and not led.pendientes(),
                   dict(fds_registrados=len(det_ledger),
                        residuos=led.pendientes()))
        _agregar_veredicto(r, pasos)
    except Exception as exc:                       # noqa: BLE001
        fallos.append(_excepcion('f6', exc))
        r['traceback'] = traceback.format_exc()
        r['ledger'] = dict(residuos=led.pendientes())
        r.finalizar('FAIL', 'excepción inesperada (R1: FAIL por defecto)')
    return r


class Resultado(dict):
    def finalizar(self, verdicto, nota=''):
        self['resultado'] = verdicto
        if nota:
            self['nota'] = nota
        return self


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
    consolidado = dict(schema='feasibility-1-r1/1', entorno=_entorno(),
                       padre='a94f50793dfa97bb7074bb3e20fe2d42c3306596',
                       produccion_modificada=False, produccion_ejecutada=False,
                       resultados={})
    for nombre in elegidas:
        if nombre not in funcs:
            continue
        print('=== %s ===' % nombre, flush=True)
        res = funcs[nombre](a.raiz)
        consolidado['resultados'][nombre] = res['resultado']
        consolidado.setdefault('obligatorios_fallidos', {})[nombre] = \
            res.get('obligatorios_fallidos', [])
        with open(os.path.join(ev, 'feas1r1_%s.json' % nombre.lower()), 'w',
                  encoding='utf-8') as f:
            json.dump(res, f, indent=1, ensure_ascii=False, default=_json_default)
        print('  -> %s: %s' % (nombre, res['resultado']), flush=True)
        for p in res.get('pasos', []):
            if p.get('obligatorio') and not p['ok']:
                print('  OBLIGATORIO FALLIDO: %s -> %s'
                      % (p['paso'], json.dumps(p['detalle'], ensure_ascii=False,
                                               default=_json_default)), flush=True)
        for fallo in res.get('fallos', []):
            print('  FALLO: %s' % json.dumps(fallo, ensure_ascii=False), flush=True)
    with open(os.path.join(ev, 'consolidado_feasibility_1_r1.json'), 'w',
              encoding='utf-8') as f:
        json.dump(consolidado, f, indent=1, ensure_ascii=False,
                  default=_json_default)
    print('RESULTADOS:', json.dumps(consolidado['resultados'], ensure_ascii=False),
          flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
