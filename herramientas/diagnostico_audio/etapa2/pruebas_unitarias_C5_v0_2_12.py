#!/usr/bin/env python3
"""Pruebas unitarias aisladas C5 v0.2.12 — garantia del segundo cierre ante
interrupcion (C5-A) e identidad real de publicacion (C5-C).

Se importa el instrumento audioinput_diag_termux.py v0.2.12 y se verifican
los dos defectos corregidos sobre v0.2.11:

  C5-A: _close_pair_conserving_interrupt() garantiza ahora el intento de
  cierre del descriptor propietario mediante un finally que abarca el
  cierre de SoundFile, con los metodos del propietario PRE-VINCULADOS
  antes del primer intento (sin ventana de acceso a atributos entre ambas
  operaciones donde una KI asincrona impida el intento).

  C5-C: _publication_state_after_interrupt() verifica mediante el
  directorio anclado (C1) y lstat relativo (sin seguir enlaces
  simbolicos); PUBLICADO solo con identidad (st_dev, st_ino) compartida
  entre final y provisional REGULARES; provisional ausente sin evidencia
  de identidad implica INDETERMINADO (nunca una afirmacion falsa).

PRUEBAS OBLIGATORIAS CUBIERTAS:
  C5-A: (1) KI dentro de close_soundfile; (2) KI en el limite entre ambas
        operaciones — post-completacion y asincrona real (SIGALRM);
        (3) KI dentro de close_fd; (4) excepcion ordinaria de SoundFile
        seguida de cierre del FD; (5) cierre normal de ambos;
        (6) exactamente un intento de cierre del FD por escenario;
        (7) sin reintento de recursos inciertos.
  C5-C: (1) misma identidad -> PUBLICADO; (2) final ajeno -> NO_PUBLICADO;
        (3) provisional ausente sin evidencia -> INDETERMINADO;
        (4) final simbolico -> nunca PUBLICADO; (5) error de acceso ->
        INDETERMINADO; (6) publicacion real + KI antes del unlink;
        (7) publicacion real + unlink + KI posterior: sin afirmar
        PUBLICADO sin evidencia; (8) ninguna segunda publicacion ni
        sobrescritura en ningun escenario.

METODO: fallos/KI INYECTADOS con mocks aislados (closer scriptado sobre un
CloseErrorLogger real con fd y token reales; os.link/os.close/os.unlink
envueltos; SIGALRM para la KI asincrona real); ningun caso depende de
fallos espontaneos del OS. Las pruebas de cierre verifican EXPLICITAMENTE
el numero de intentos (contadores de llamadas), no solo la excepcion.
No Android/Termux, no audio real, no muestras del proyecto, sin DSP.

CLASIFICACION: PASS / FAIL / ERROR / NOT_EXECUTED / EXPECTED_LIMITATION
por caso (nunca PASS sin ejecucion real).
"""
import errno
import glob
import importlib.util
import os
import shutil
import signal
import stat as stat_mod
import sys
import tempfile
import time
import traceback
from pathlib import Path

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'audioinput_diag_termux.py')

_spec = importlib.util.spec_from_file_location('audioinput_diag_termux', TARGET)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

RESULTS = []
DETAILS = {}


def record(name, status, detail):
    RESULTS.append((name, status, detail))
    print("{0:4} {1:52} {2}".format(status, name, detail))


def run(name, fn):
    try:
        fn()
        record(name, 'PASS', DETAILS.get(name, 'OK'))
    except (ImportError, ModuleNotFoundError) as exc:
        record(name, 'NOT_EXECUTED', 'dependencia/condicion no disponible: {0}'.format(exc))
    except AssertionError as exc:
        record(name, 'FAIL', str(exc))
    except ExpectedLimitation as exc:
        record(name, 'EXPECTED_LIMITATION', str(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


class ExpectedLimitation(Exception):
    """Condicion no reproducible o no verificable: se documenta, no es PASS."""


def fresh_tmp():
    return tempfile.mkdtemp(prefix='c512_ut_')


def make_file(d, name, content=b'x' * 64):
    p = os.path.join(d, name)
    with open(p, 'wb') as fh:
        fh.write(content)
    return p


def fd_vivo(fd):
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


class SFileSim(object):
    """SoundFile simulado minimo para los cierres del helper."""

    def __init__(self):
        self.closed = False
        self.close_calls = 0

    def close(self):
        self.close_calls += 1
        self.closed = True


class ScriptedCloser(object):
    """Envuelve un CloseErrorLogger REAL (token/propiedad C4-A intactos) y
    permite scriptar el comportamiento de close_soundfile/close_fd:
      'ok'                  -> delega (cierre real)
      'ki_pre'              -> lanza KI ANTES del efecto del cierre
      'ki_post'             -> completa el efecto del cierre y LUEGO lanza KI
      'ki_dentro_lento'     -> delega tras dormir (el KI asincrono cae dentro)
      'RuntimeError'        -> lanza RuntimeError
      'ki_al_acceder'       -> lanza KI cuando se ACCEDA al metodo
    Registra cuantas veces se invoco cada cierre (conteo de intentos).
    """

    def __init__(self, real, sf_script='ok', fd_script='ok',
                 ki_al_acceder=None):
        self.real = real
        self.sf_script = sf_script
        self.fd_script = fd_script
        self.sf_calls = 0
        self.fd_calls = 0
        self.ki_al_acceder = ki_al_acceder
        self._acceso_fd = False
        self._acceso_sf = False

    def _ejecutar(self, script, efecto):
        if script == 'ki_pre':
            raise KeyboardInterrupt()
        efecto()
        if script == 'ki_post':
            raise KeyboardInterrupt()
        if script == 'RuntimeError':
            raise RuntimeError('error ordinario simulado C5-A')
        if script == 'ki_dentro_lento':
            time.sleep(0.2)

    def close_soundfile(self, sfile, label):
        self.sf_calls += 1
        self._ejecutar(self.sf_script,
                       lambda: self.real.close_soundfile(sfile, label))
        return None

    @property
    def close_fd(self):
        if self.ki_al_acceder == 'fd':
            if not self._acceso_fd:
                self._acceso_fd = True
                raise KeyboardInterrupt()
        return self._close_fd_call

    def _close_fd_call(self, fd, label, token=None):
        self.fd_calls += 1
        self._ejecutar(self.fd_script,
                       lambda: self.real.close_fd(fd, label, token=token))
        return None

    @property
    def close_soundfile_metodo(self):
        return self.close_soundfile


def nuevo_par_fd_closer(d):
    """Crea un archivo real, lo abre y registra el token en un closer real."""
    fpath = make_file(d, 'recurso.bin')
    fd = os.open(fpath, os.O_RDONLY)
    real_closer = mod.CloseErrorLogger()
    token = real_closer.register_fd(fd, 'recurso_fd')
    return fd, real_closer, token


# ---------------------------------------------------------------------------
# Inyecciones de flujo (reutilizan los patrones del harness v0.2.11)
# ---------------------------------------------------------------------------
class LinkKI(object):
    """KI alrededor de os.link del informe.
    modo 'antes': KI antes del enlace (no se publica).
    modo 'despues': el enlace REAL se ejecuta y luego se lanza KI."""

    def __init__(self, modo):
        self.modo = modo
        self.fired = 0
        self.linked = 0
        self._real = os.link

    def _fake(self, *a, **k):
        es_informe = (a and isinstance(a[0], str)
                      and a[0].endswith('.json.tmp'))
        if es_informe and self.modo == 'antes' and self.fired == 0:
            self.fired += 1
            raise KeyboardInterrupt()
        r = self._real(*a, **k)
        if es_informe and self.modo == 'despues' and self.fired == 0:
            self.linked += 1
            self.fired += 1
            raise KeyboardInterrupt()
        return r

    def __enter__(self):
        os.link = self._fake
        return self

    def __exit__(self, *exc):
        os.link = self._real
        return False


class ParentCloseKI(object):
    """KI en el cierre del descriptor del directorio padre del informe SOLO
    cuando el informe final ya existe (tras enlace + eliminacion)."""

    def __init__(self, private_dir):
        self.private_dir = private_dir
        self.parent_fds = set()
        self.fired = 0
        self._real_soda = mod.safe_open_dir_anchored
        self._real_close = os.close

    def _soda(self, path, *a, **k):
        fd, msg = self._real_soda(path, *a, **k)
        if str(path) == self.private_dir:
            self.parent_fds.add(fd)
        return fd, msg

    def _close(self, fd, *a, **k):
        if fd in self.parent_fds:
            hits = [p for p in glob.glob(
                os.path.join(self.private_dir, 'report-*.json'))
                if not p.endswith('.tmp')]
            if hits:
                self.parent_fds.discard(fd)
                self.fired += 1
                raise KeyboardInterrupt()
        return self._real_close(fd, *a, **k)

    def __enter__(self):
        mod.safe_open_dir_anchored = self._soda
        os.close = self._close
        return self

    def __exit__(self, *exc):
        mod.safe_open_dir_anchored = self._real_soda
        os.close = self._real_close
        return False


class _FakeArr(object):
    __slots__ = ('data', 'shape')

    def __init__(self, data, shape):
        self.data = data
        self.shape = shape

    def __setitem__(self, key, value):
        i, j = key
        self.data[i][j] = value


class _FakeRng(object):
    def uniform(self, low, high, size):
        rows = [[low] * size[1] for _ in range(size[0])]
        return _FakeArr(rows, (size[0], size[1]))


def make_fake_np():
    np = type(sys)('numpy_sim_c512')
    np.__version__ = 'sim-0.0'
    rng = type(sys)('rng_sim_c512')
    rng.default_rng = lambda seed=None: _FakeRng()
    np.random = rng
    np.array_equal = lambda a, b: (a.data == b.data
                                   and tuple(a.shape) == tuple(b.shape))
    return np


def make_fake_sf(dir_raises=True):
    sf = type(sys)('soundfile_sim_c512')
    sf.__version__ = 'sim-0.0'
    sf.__libsndfile_version__ = 'sim-0.0'

    class LibsndfileError(Exception):
        pass

    sf.LibsndfileError = LibsndfileError

    class SoundFile(object):
        def __init__(self, file, mode='r', samplerate=None, channels=None,
                     format=None, subtype=None, closefd=False):
            self._fd = file
            self.closed = False
            self._pos = 0
            st = os.fstat(file)
            if dir_raises and stat_mod.S_ISDIR(st.st_mode):
                raise LibsndfileError('sim: fd de directorio no soportado')
            if mode == 'w':
                self.samplerate = samplerate
                self.channels = channels
                self.frames = 0
            else:
                self.channels = 2
                self.samplerate = 44100
                self.frames = st.st_size // 8

        def write(self, arr):
            import struct
            buf = bytearray()
            for row in arr.data:
                for v in row:
                    buf += struct.pack('<f', float(v))
            os.write(self._fd, bytes(buf))
            self.frames += len(arr.data)

        def read(self, frames, dtype='float64', always_2d=False):
            nbytes = frames * self.channels * 4
            data = os.pread(self._fd, nbytes, self._pos)
            self._pos += len(data)
            n = len(data) // (self.channels * 4)
            import struct
            rows = [struct.unpack_from('<{0}f'.format(self.channels), data,
                                       i * self.channels * 4) for i in range(n)]
            return _FakeArr([list(r) for r in rows], (n, self.channels))

        def seek(self, offset, whence=0):
            self._pos = offset
            return self._pos

        def close(self):
            self.closed = True

    sf.SoundFile = SoundFile

    def available_subtypes(fmt):
        return ({'PCM_16': 'x', 'PCM_24': 'x', 'PCM_32': 'x', 'FLOAT': 'x'}
                if fmt == 'WAV' else {})

    sf.available_subtypes = available_subtypes
    return sf


def inject_fakes():
    old_np = sys.modules.get('numpy')
    old_sf = sys.modules.get('soundfile')
    sys.modules['numpy'] = make_fake_np()
    sys.modules['soundfile'] = make_fake_sf()
    return old_np, old_sf


def restore_fakes(old_np, old_sf):
    if old_np is None:
        sys.modules.pop('numpy', None)
    else:
        sys.modules['numpy'] = old_np
    if old_sf is None:
        sys.modules.pop('soundfile', None)
    else:
        sys.modules['soundfile'] = old_sf


def run_main(private_dir, shared_dir=None):
    """Ejecuta main() real; retorna (rc, stdout, ki_propagada)."""
    import io
    from contextlib import redirect_stdout
    argv = [TARGET, '--private-dir', private_dir]
    if shared_dir is not None:
        argv += ['--shared', shared_dir]
    old_argv = sys.argv
    sys.argv = argv
    buf = io.StringIO()
    rc = None
    ki = False
    try:
        with redirect_stdout(buf):
            try:
                mod.main()
            except SystemExit as e:
                rc = e.code
            except KeyboardInterrupt:
                ki = True
    finally:
        sys.argv = old_argv
    return rc, buf.getvalue(), ki


def find_report(d):
    hits = [p for p in glob.glob(os.path.join(d, 'report-*.json'))
            if not p.endswith('.tmp')]
    return hits[0] if len(hits) == 1 else None


def snapshot_directorio(d):
    """Lista de (nombre, st_dev, st_ino) para verificar ausencia de
    creaciones/borrados/sobrescrituras (solo lectura)."""
    out = []
    for nombre in sorted(os.listdir(d)):
        st = os.lstat(os.path.join(d, nombre))
        out.append((nombre, st.st_dev, st.st_ino))
    return out


# ================================================================ C5-A (1)
def test_c5a_01_ki_dentro_close_soundfile():
    """KI DENTRO de close_soundfile (antes del efecto del cierre): el cierre
    del descriptor se INTENTA exactamente 1 vez; retorno True; fd cerrado."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        sf = SFileSim()
        bc = ScriptedCloser(real_closer, sf_script='ki_pre')
        r = mod._close_pair_conserving_interrupt(bc, sf, 'sfile_prueba',
                                                 fd, 'recurso_fd', token)
        assert r is True, 'el helper debe reportar la KI absorbida: {0}'.format(r)
        assert bc.sf_calls == 1, \
            'close_soundfile invocado {0} veces (sin reintentos)'.format(bc.sf_calls)
        assert bc.fd_calls == 1, \
            'el intento de cierre del FD debe ser exactamente 1: {0}'.format(
                bc.fd_calls)
        assert not fd_vivo(fd), 'el FD debio quedar cerrado por el intento'
        DETAILS['C5A12_01_ki_dentro_close_soundfile'] = (
            'KI dentro de close_soundfile; intento de FD=1; retorno True; fd cerrado')
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-A (2)
def test_c5a_02_ki_en_el_limite():
    """KI en el LIMITE entre ambas operaciones, no solo dentro de
    close_soundfile: (a) el cierre de SoundFile se COMPLETA y el KI llega
    justo al terminar; (b) KI asincrona REAL (SIGALRM) entregada tras
    completarse close_soundfile. En ambos: intento del FD exactamente 1."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        # (a) post-completacion: el efecto del cierre ocurre y LUEGO el KI
        sf = SFileSim()
        bc = ScriptedCloser(real_closer, sf_script='ki_post')
        r = mod._close_pair_conserving_interrupt(bc, sf, 'sfile_prueba',
                                                 fd, 'recurso_fd', token)
        assert r is True, 'retorno: {0}'.format(r)
        assert bc.fd_calls == 1, \
            'KI en el limite: el intento del FD debe ser exactamente 1: {0}'.format(
                bc.fd_calls)
        assert sf.close_calls == 1, \
            'el cierre de SoundFile debio completarse una vez: {0}'.format(
                sf.close_calls)
        assert not fd_vivo(fd), 'el FD debio quedar cerrado'
        assert not mod._close_error_ledger or all(
            e.get('label') != 'recurso_fd' for e in mod._close_error_ledger), \
            'errores espurios en el acumulador'
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)
    # (b) KI asincrona real: SIGALRM armada al completarse close_soundfile;
    # el punto de entrega depende del planificador (eso ES una interrupcion
    # asincrona); la asercion es invariante al punto de entrega.
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    old_handler = None
    try:
        sf = SFileSim()
        bc = ScriptedCloser(real_closer, sf_script='ok', fd_script='ki_dentro_lento')

        def armar_timer(label, sfile):
            signal.setitimer(signal.ITIMER_REAL, 0.05)

        # envolver: al completarse el cierre del sfile, armar el temporizador
        real_close_sf = mod.CloseErrorLogger.close_soundfile

        def close_sf_con_timer(self_logger, sfile, label):
            r2 = real_close_sf(self_logger, sfile, label)
            armar_timer(label, sfile)
            return r2

        mod.CloseErrorLogger.close_soundfile = close_sf_con_timer
        old_handler = signal.signal(
            signal.SIGALRM,
            lambda signum, frame: (_ for _ in ()).throw(KeyboardInterrupt()))
        resultado = None
        try:
            resultado = mod._close_pair_conserving_interrupt(
                bc, sf, 'sfile_prueba', fd, 'recurso_fd', token)
        except KeyboardInterrupt:
            resultado = 'KI_PROPAGADA'
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            mod.CloseErrorLogger.close_soundfile = real_close_sf
        assert bc.fd_calls == 1, \
            'KI asincrona: el intento del FD debe ser exactamente 1: {0}'.format(
                bc.fd_calls)
        assert resultado in (True, 'KI_PROPAGADA'), \
            'resultado: {0}'.format(resultado)
        assert bc.sf_calls == 1, 'sin reintentos de close_soundfile: {0}'.format(
            bc.sf_calls)
        DETAILS['C5A12_02_ki_en_el_limite'] = (
            '(a) post-completacion: FD intentado 1 vez, fd cerrado; '
            '(b) SIGALRM asincrona real: FD intentado 1 vez; sin reintentos')
    finally:
        if old_handler is not None:
            signal.signal(signal.SIGALRM, old_handler)
        signal.setitimer(signal.ITIMER_REAL, 0)
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-A (3)
def test_c5a_03_ki_dentro_close_fd():
    """KI DENTRO de close_fd (antes del efecto del cierre): el intento es
    unico (sin reintento del cierre incierto); retorno True; fd incierto."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        sf = SFileSim()
        bc = ScriptedCloser(real_closer, sf_script='ok', fd_script='ki_pre')
        r = mod._close_pair_conserving_interrupt(bc, sf, 'sfile_prueba',
                                                 fd, 'recurso_fd', token)
        assert r is True, 'retorno: {0}'.format(r)
        assert bc.fd_calls == 1, \
            'cierre incierto NO se reintenta (1 unico intento): {0}'.format(
                bc.fd_calls)
        assert fd_vivo(fd), \
            'el FD queda en estado incierto (el cierre no se realizo)'
        assert sf.closed, 'el cierre del SoundFile debio completarse'
        DETAILS['C5A12_03_ki_dentro_close_fd'] = (
            'KI dentro de close_fd; 1 unico intento; sin reintento; fd incierto')
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-A (4)
def test_c5a_04_excepcion_ordinaria_sf():
    """Excepcion ORDINARIA de SoundFile seguida del cierre del FD: el intento
    del FD se realiza (finally) y la excepcion ordinaria se propaga."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        sf = SFileSim()
        bc = ScriptedCloser(real_closer, sf_script='RuntimeError')
        propagada = None
        r = None
        try:
            r = mod._close_pair_conserving_interrupt(
                bc, sf, 'sfile_prueba', fd, 'recurso_fd', token)
        except RuntimeError as exc:
            propagada = exc
        assert propagada is not None, \
            'la excepcion ordinaria debe propagarse (no se absorbe)'
        assert bc.fd_calls == 1, \
            'tras la excepcion ordinaria, el intento del FD debe ser 1: {0}'.format(
                bc.fd_calls)
        assert not fd_vivo(fd), 'el FD debio quedar cerrado por el intento'
        DETAILS['C5A12_04_excepcion_ordinaria_sf'] = (
            'RuntimeError de SoundFile propaga; intento de FD=1 (finally); fd cerrado')
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-A (5)
def test_c5a_05_cierre_normal_ambos():
    """Cierre normal de ambos recursos: 1 llamada a cada cierre, retorno
    False (sin KI absorbida), fd cerrado, SoundFile cerrado."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        sf = SFileSim()
        bc = ScriptedCloser(real_closer)
        r = mod._close_pair_conserving_interrupt(bc, sf, 'sfile_prueba',
                                                 fd, 'recurso_fd', token)
        assert r is False, 'sin KI el retorno debe ser False: {0}'.format(r)
        assert bc.sf_calls == 1 and bc.fd_calls == 1, \
            'un cierre por recurso: sf={0} fd={1}'.format(bc.sf_calls, bc.fd_calls)
        assert sf.closed and not fd_vivo(fd)
        DETAILS['C5A12_05_cierre_normal_ambos'] = (
            'sf=1 llamada, fd=1 llamada; retorno False; ambos cerrados')
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-A (6)
def test_c5a_06_intento_unico_por_escenario():
    """Exactamente UN intento de cierre del FD en cada escenario obligatorio
    (verificacion agregada con recursos frescos por escenario)."""
    escenarios = ('ki_pre_sf', 'ki_post_sf', 'ki_fd', 'RuntimeError_sf', 'ok')
    for escenario in escenarios:
        d = fresh_tmp()
        fd, real_closer, token = nuevo_par_fd_closer(d)
        try:
            sf = SFileSim()
            if escenario == 'ki_pre_sf':
                bc = ScriptedCloser(real_closer, sf_script='ki_pre')
            elif escenario == 'ki_post_sf':
                bc = ScriptedCloser(real_closer, sf_script='ki_post')
            elif escenario == 'ki_fd':
                bc = ScriptedCloser(real_closer, fd_script='ki_pre')
            elif escenario == 'RuntimeError_sf':
                bc = ScriptedCloser(real_closer, sf_script='RuntimeError')
            else:
                bc = ScriptedCloser(real_closer)
            try:
                mod._close_pair_conserving_interrupt(
                    bc, sf, 'sfile_prueba', fd, 'recurso_fd', token)
            except (KeyboardInterrupt, RuntimeError):
                pass
            assert bc.fd_calls == 1, \
                'escenario {0}: intentos del FD = {1} (esperado 1)'.format(
                    escenario, bc.fd_calls)
        finally:
            if fd_vivo(fd):
                os.close(fd)
            shutil.rmtree(d, ignore_errors=True)
    DETAILS['C5A12_06_intento_unico_por_escenario'] = (
        '5 escenarios: intento de FD = 1 exactamente en cada uno')


# ================================================================ C5-A (7)
def test_c5a_07_sin_reintento_inciertos():
    """Sin reintento de recursos con resultado incierto: KI dentro de
    close_fd => close_fd invocado exactamente 1 vez; KI dentro de
    close_soundfile => close_soundfile invocado exactamente 1 vez."""
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        bc = ScriptedCloser(real_closer, fd_script='ki_pre')
        mod._close_pair_conserving_interrupt(bc, SFileSim(), 'sfile_prueba',
                                             fd, 'recurso_fd', token)
        assert bc.fd_calls == 1, \
            'cierre incierto del FD reintentado: {0}'.format(bc.fd_calls)
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)
    d = fresh_tmp()
    fd, real_closer, token = nuevo_par_fd_closer(d)
    try:
        bc = ScriptedCloser(real_closer, sf_script='ki_pre')
        mod._close_pair_conserving_interrupt(bc, SFileSim(), 'sfile_prueba',
                                             fd, 'recurso_fd', token)
        assert bc.sf_calls == 1, \
            'cierre incierto del SoundFile reintentado: {0}'.format(bc.sf_calls)
        assert bc.fd_calls == 1, \
            'el intento del FD debe seguir siendo unico: {0}'.format(bc.fd_calls)
        DETAILS['C5A12_07_sin_reintento_inciertos'] = (
            'close_fd=1 y close_soundfile=1 en sus escenarios de KI: sin reintentos')
    finally:
        if fd_vivo(fd):
            os.close(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (1)
def test_c5c_01_misma_identidad():
    """Final y provisional con la MISMA identidad (enlace duro real):
    PUBLICADO."""
    d = fresh_tmp()
    try:
        prov = Path(d) / 'informe-x.json.tmp'
        prov.write_text('{"ejecucion": true}')
        final = Path(d) / 'informe-x.json'
        os.link(str(prov), str(final))
        estado, detalle = mod._publication_state_after_interrupt(final)
        assert estado == 'PUBLICADO', \
            'esperado PUBLICADO: {0} ({1})'.format(estado, detalle)
        assert 'st_dev' in detalle and 'st_ino' in detalle, \
            'el detalle debe mencionar la identidad: {0}'.format(detalle)
        DETAILS['C5C12_01_misma_identidad'] = 'PUBLICADO (identidad compartida, ambos regulares)'
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (2)
def test_c5c_02_final_ajeno():
    """Final preexistente ajeno + provisional propio: NO_PUBLICADO (no se
    confunde un archivo ajeno con el informe de esta ejecucion)."""
    d = fresh_tmp()
    try:
        final = Path(d) / 'informe-x.json'
        final.write_text('{"ajeno": true}')
        Path(d, 'informe-x.json.tmp').write_text('{"ejecucion": true}')
        estado, detalle = mod._publication_state_after_interrupt(final)
        assert estado == 'NO_PUBLICADO', \
            'esperado NO_PUBLICADO: {0} ({1})'.format(estado, detalle)
        DETAILS['C5C12_02_final_ajeno'] = 'NO_PUBLICADO (identidades distintas)'
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (3)
def test_c5c_03_provisional_ausente():
    """Provisional ausente + final regular existente: INDETERMINADO (sin
    evidencia independiente de identidad; otro proceso pudo eliminar el
    provisional). Nunca PUBLICADO por inferencia."""
    d = fresh_tmp()
    try:
        final = Path(d) / 'informe-x.json'
        final.write_text('{"ejecucion": true}')
        estado, detalle = mod._publication_state_after_interrupt(final)
        assert estado == 'INDETERMINADO', \
            'esperado INDETERMINADO: {0} ({1})'.format(estado, detalle)
        assert 'evidencia' in detalle, 'detalle sin motivo: {0}'.format(detalle)
        DETAILS['C5C12_03_provisional_ausente'] = (
            'INDETERMINADO (sin evidencia de identidad; sin afirmacion falsa)')
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (4)
def test_c5c_04_final_simbolico():
    """Final simbolico: NUNCA declararlo PUBLICADO por seguir el enlace
    (lstat no sigue simbolos). Sin provisional: NO_PUBLICADO; con
    provisional: NO_PUBLICADO (identidad de la entrada no coincide)."""
    d = fresh_tmp()
    try:
        destino = Path(d) / 'objetivo-regular.bin'
        destino.write_text('{"x": 1}')
        final = Path(d) / 'informe-x.json'
        os.symlink(str(destino), str(final))
        estado_a, _ = mod._publication_state_after_interrupt(final)
        assert estado_a == 'NO_PUBLICADO', \
            'simbolico sin provisional: {0} (nunca PUBLICADO)'.format(estado_a)
        Path(d, 'informe-x.json.tmp').write_text('{"ejecucion": true}')
        estado_b, _ = mod._publication_state_after_interrupt(final)
        assert estado_b == 'NO_PUBLICADO', \
            'simbolico con provisional: {0} (nunca PUBLICADO)'.format(estado_b)
        DETAILS['C5C12_04_final_simbolico'] = (
            'NO_PUBLICADO en ambos casos (lstat no sigue el enlace)')
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (5)
def test_c5c_05_error_de_acceso():
    """Error de acceso durante la verificacion: INDETERMINADO (directorio
    sin permisos: la apertura anclada falla)."""
    d = fresh_tmp()
    try:
        os.chmod(d, 0o000)
        estado, detalle = mod._publication_state_after_interrupt(
            Path(d) / 'informe-x.json')
        assert estado == 'INDETERMINADO', \
            'esperado INDETERMINADO: {0} ({1})'.format(estado, detalle)
        DETAILS['C5C12_05_error_de_acceso'] = 'INDETERMINADO (anclaje imposible)'
    finally:
        os.chmod(d, 0o700)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ C5-C (6)
def test_c5c_06_publicacion_real_ki_antes_unlink():
    """Flujo real: publicacion REAL seguida de KI antes de eliminar el
    provisional: PUBLICADO anunciado (identidad verificable); provisional
    conservado; rc=130; sin segunda publicacion."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with LinkKI('despues') as lk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert lk.linked == 1, 'el enlace real no se ejecuto'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is not None, 'el informe DEBE estar publicado'
        assert '[ESTADO DE PUBLICACION: PUBLICADO]' in out, \
            'sin reconocimiento: {0}'.format(out[-500:])
        assert out.count('[ESTADO DE PUBLICACION') == 1
        provs = [p for p in os.listdir(d1) if p.endswith('.json.tmp')]
        assert provs, 'el provisional debe conservarse'
        DETAILS['C5C12_06_publicacion_real_ki_antes_unlink'] = (
            'PUBLICADO por identidad; provisional conservado; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-C (7)
def test_c5c_07_publicacion_unlink_ki_posterior():
    """Flujo real: publicacion real, eliminacion del provisional completada
    y KI posterior: NO se afirma PUBLICADO sin evidencia suficiente; se
    anuncia INDETERMINADO; rc=130; sin segunda publicacion."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with ParentCloseKI(d1) as pck:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert pck.fired >= 1, 'la KI en el cierre del padre no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is not None, 'el informe existe en disco'
        assert '[ESTADO DE PUBLICACION: PUBLICADO]' not in out, \
            'se afirmo PUBLICADO sin evidencia de identidad'
        assert '[ESTADO DE PUBLICACION: INDETERMINADO]' in out, \
            'sin anuncio INDETERMINADO: {0}'.format(out[-500:])
        assert out.count('[ESTADO DE PUBLICACION') == 1
        assert not [p for p in os.listdir(d1) if p.endswith('.json.tmp')], \
            'sin limpieza extra (el provisional ya fue eliminado por el unlink)'
        DETAILS['C5C12_07_publicacion_unlink_ki_posterior'] = (
            'INDETERMINADO anunciado (sin evidencia); sin afirmacion falsa; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-C (8)
def test_c5c_08_sin_segunda_publicacion_ni_sobrescritura():
    """Ningun escenario provoca segunda publicacion o sobrescritura: la
    verificacion es de solo lectura (la instantanea del directorio no
    cambia en los escenarios unitarios) y en los flujos hay exactamente un
    anuncio de estado y un unico informe."""
    # (a) escenarios unitarios: solo lectura (sin creaciones/borrados/
    # sobrescrituras: la instantanea (nombre, dev, ino) es identica)
    escenarios_unit = ('misma_identidad', 'final_ajeno', 'provisional_ausente',
                       'simbolico', 'ninguno')
    for escenario in escenarios_unit:
        d = fresh_tmp()
        try:
            final = Path(d) / 'informe-x.json'
            if escenario == 'misma_identidad':
                Path(d, 'informe-x.json.tmp').write_text('{"e": 1}')
                os.link(str(Path(d, 'informe-x.json.tmp')), str(final))
            elif escenario == 'final_ajeno':
                final.write_text('{"ajeno": true}')
                Path(d, 'informe-x.json.tmp').write_text('{"e": 1}')
            elif escenario == 'provisional_ausente':
                final.write_text('{"e": 1}')
            elif escenario == 'simbolico':
                destino = Path(d) / 'objetivo.bin'
                destino.write_text('{"x": 1}')
                os.symlink(str(destino), str(final))
            antes = snapshot_directorio(d)
            mod._publication_state_after_interrupt(final)
            despues = snapshot_directorio(d)
            assert antes == despues, \
                'escenario {0}: el directorio cambio (no es solo lectura): {1} -> {2}'.format(
                    escenario, antes, despues)
        finally:
            shutil.rmtree(d, ignore_errors=True)
    # (b) flujo: exactamente un anuncio y un unico informe; sin archivos
    # adicionales de publicacion
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with LinkKI('despues'):
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130
        assert out.count('[ESTADO DE PUBLICACION') == 1, \
            'anuncios multiples de estado'
        informes = [p for p in os.listdir(d1) if p.endswith('.json')]
        assert len(informes) == 1, \
            'publicaciones multiples o sobrescritura: {0}'.format(informes)
        nombres = sorted(os.listdir(d1))
        assert all(n.endswith('.json') or n.endswith('.json.tmp')
                   or n.startswith('run-') for n in nombres), \
            'archivos inesperados creados: {0}'.format(nombres)
        DETAILS['C5C12_08_sin_segunda_publicacion_ni_sobrescritura'] = (
            '5 escenarios de solo lectura (instantanea identica); 1 anuncio; '
            '1 unico informe; sin archivos extra')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================
def main():
    print('Pruebas unitarias C5 v0.2.12 — garantia del segundo cierre (C5-A) e '
          'identidad real de publicacion (C5-C) (fallos/KI inyectados; entorno '
          'no Android, sin audio real)')
    print('=' * 88)
    casos = [
        ('C5A12_01_ki_dentro_close_soundfile', test_c5a_01_ki_dentro_close_soundfile),
        ('C5A12_02_ki_en_el_limite', test_c5a_02_ki_en_el_limite),
        ('C5A12_03_ki_dentro_close_fd', test_c5a_03_ki_dentro_close_fd),
        ('C5A12_04_excepcion_ordinaria_sf', test_c5a_04_excepcion_ordinaria_sf),
        ('C5A12_05_cierre_normal_ambos', test_c5a_05_cierre_normal_ambos),
        ('C5A12_06_intento_unico_por_escenario', test_c5a_06_intento_unico_por_escenario),
        ('C5A12_07_sin_reintento_inciertos', test_c5a_07_sin_reintento_inciertos),
        ('C5C12_01_misma_identidad', test_c5c_01_misma_identidad),
        ('C5C12_02_final_ajeno', test_c5c_02_final_ajeno),
        ('C5C12_03_provisional_ausente', test_c5c_03_provisional_ausente),
        ('C5C12_04_final_simbolico', test_c5c_04_final_simbolico),
        ('C5C12_05_error_de_acceso', test_c5c_05_error_de_acceso),
        ('C5C12_06_publicacion_real_ki_antes_unlink', test_c5c_06_publicacion_real_ki_antes_unlink),
        ('C5C12_07_publicacion_unlink_ki_posterior', test_c5c_07_publicacion_unlink_ki_posterior),
        ('C5C12_08_sin_segunda_publicacion_ni_sobrescritura', test_c5c_08_sin_segunda_publicacion_ni_sobrescritura),
    ]
    for nombre, fn in casos:
        run(nombre, fn)
    print('=' * 88)
    total = len(RESULTS)
    npass = sum(1 for _, s, _ in RESULTS if s == 'PASS')
    nfail = sum(1 for _, s, _ in RESULTS if s == 'FAIL')
    nerr = sum(1 for _, s, _ in RESULTS if s == 'ERROR')
    nel = sum(1 for _, s, _ in RESULTS if s == 'NOT_EXECUTED')
    nlim = sum(1 for _, s, _ in RESULTS if s == 'EXPECTED_LIMITATION')
    print('TOTAL {0} | PASS {1} | FAIL {2} | ERROR {3} | NOT_EXECUTED {4} | '
          'EXPECTED_LIMITATION {5}'.format(total, npass, nfail, nerr, nel, nlim))
    for name, status, detail in RESULTS:
        if status != 'PASS':
            print('  NO PASS: {0} [{1}] {2}'.format(name, status, detail))
    if nfail or nerr:
        sys.exit(1)


if __name__ == '__main__':
    main()
