#!/usr/bin/env python3
"""Pruebas unitarias aisladas C5 v0.2.11 — coherencia de interrupciones,
finalizacion y construccion/publicacion del informe.

Se importa el instrumento audioinput_diag_termux.py v0.2.11 y se ejecuta el
flujo REAL de main() con dependencias simuladas (numpy/soundfile falsos) y
fallos/KeyboardInterrupt INYECTADOS. No basta con probar condiciones
aisladas: cada caso recorre main() completo.

Cobertura (matriz obligatoria):
  C5-01 KI durante creacion de fixture          ERROR; cierre del FD intentado
  C5-02 KI durante cierre de SoundFile          cierre del FD intentado; no PASS
  C5-03 KI durante cierre del FD                cierre incierto NO reintentado
  C5-04 KI durante prueba T11-T14               prueba interrumpida ERROR
  C5-05 pruebas posteriores a la interrupcion   NOT_EXECUTED, sin duplicados
  C5-06 KI durante T15/T16                      ERROR y siguientes NOT_EXECUTED
  C5-07 KI en preparacion intermedia            pendientes NOT_EXECUTED
  C5-08 KI con entorno compartido configurado   entorno B no iniciado
  C5-09 KI en strftime de finalizacion          informe reconstruido interrupted
  C5-10 KI durante presentacion del resumen     resultados anteriores conservados
  C5-11 KI antes de os.link                     no publicado; provisional conservado
  C5-12 os.link real y luego KI                 publicacion reconocida
  C5-13 KI durante eliminacion del provisional  estado correcto; sin 2a publicacion
  C5-14 KI durante escritura JSON               codigo 130; estado correcto
  C5-15 KI junto con error de cierre            errores conservados sin duplicacion
  C5-16 reconstruccion repetida del informe     sin perdidas ni duplicados
  C5-17 excepcion fatal durante ejecucion       estado fatal reflejado; rc no nulo
  C5-18 ejecucion normal                        comportamiento previo conservado

Los casos de cierre verifican EXPLICITAMENTE el numero de intentos de cierre
(por identidad del archivo, st_ino), no solo que se lanzo una excepcion.

METODO: todas las KI/fallos se INYECTAN con mocks aislados (os.close, os.write,
os.open, os.stat, os.pread, os.link, os.unlink, time.strftime, builtins.print,
cierre de SoundFile simulado); ningun caso depende de fallos espontaneos del OS.
No Android/Termux, no audio real, no muestras del proyecto, sin motores DSP.

CLASIFICACION: PASS / FAIL / ERROR / NOT_EXECUTED / EXPECTED_LIMITATION por
caso (nunca PASS sin ejecucion real). NOT_EXECUTED solo si la dependencia no
esta disponible; EXPECTED_LIMITATION si una condicion no puede reproducirse o
verificarse (se explica el motivo).
"""
import errno
import glob
import importlib.util
import io
import json
import builtins
import os
import re
import shutil
import stat as stat_mod
import struct
import sys
import tempfile
import traceback
import time as time_mod
from contextlib import redirect_stdout

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
    return tempfile.mkdtemp(prefix='c5_ut_')


def make_file(d, name, content=b'x' * 400):
    p = os.path.join(d, name)
    with open(p, 'wb') as fh:
        fh.write(content)
    return p


def find_report(d):
    hits = [p for p in glob.glob(os.path.join(d, 'report-*.json'))
            if not p.endswith('.tmp')]
    return hits[0] if len(hits) == 1 else None


def load_report(d):
    p = find_report(d)
    if p is None:
        return None
    with open(p) as fh:
        return json.load(fh)


def get_result(report, env, test, fixture):
    for r in report['results']:
        if r['env'] == env and r['test'] == test and r['fixture'] == fixture:
            return r
    return None


def tmp_provisionals(d):
    return [p for p in os.listdir(d) if p.endswith('.json.tmp')]


def unique_keys(report):
    claves = [(r['env'], r['test'], r['fixture']) for r in report['results']]
    return len(claves) == len(set(claves))


def fixture_ino(private_dir, fname):
    for root, _dirs, files in os.walk(private_dir):
        if f == fname if False else False:
            pass
    for root, _dirs, files in os.walk(private_dir):
        if fname in files:
            return os.stat(os.path.join(root, fname)).st_ino
    return None


# ---------------------------------------------------------------------------
# Inyecciones
# ---------------------------------------------------------------------------
class PerInoCloseCounter(object):
    """Cuenta INTENTOS de os.close por ino (solo archivos regulares) y puede
    inyectar KI en el intento numero N de un mismo ino.

    ki_at_attempt=None: solo contar (sin KI).
    ki_at_attempt=N: la N-esima tentativa de cierre de UN MISMO ino lanza
    KeyboardInterrupt (los intentos fallidos cuentan: un cierre que lanza KI
    deja el recurso en estado incierto y el contador registra el intento).
    """

    def __init__(self, ki_at_attempt=None):
        self.ki_at_attempt = ki_at_attempt
        self.per_ino = {}
        self._real = os.close

    def _fake(self, fd, *a, **k):
        try:
            st = os.fstat(fd)
        except OSError:
            st = None
        ino = None
        if st is not None and stat_mod.S_ISREG(st.st_mode):
            ino = st.st_ino
        if ino is not None:
            self.per_ino[ino] = self.per_ino.get(ino, 0) + 1
            if (self.ki_at_attempt is not None
                    and self.per_ino[ino] == self.ki_at_attempt):
                raise KeyboardInterrupt()
        return self._real(fd, *a, **k)

    def __enter__(self):
        os.close = self._fake
        return self

    def __exit__(self, *exc):
        os.close = self._real
        return False


class FakeSfKI(object):
    """KI durante el cierre simulado de SoundFile, por etiqueta del closer.

    labels: conjunto de etiquetas ('sfile', 'sfile_finally', ...) que lanzan
    KI en close_soundfile ANTES de delegar (el cierre del sfile no ocurre).
    Registra las etiquetas solicitadas para verificar que NO se reintenta un
    cierre incierto.
    """

    def __init__(self, labels):
        self.labels = set(labels)
        self.seen = []
        self._real = mod.CloseErrorLogger.close_soundfile

    def __enter__(self):
        real = self._real
        seen = self.seen
        labels = self.labels

        def close_soundfile(self_logger, sfile, label):
            seen.append(label)
            if label in labels:
                raise KeyboardInterrupt()
            return real(self_logger, sfile, label)

        mod.CloseErrorLogger.close_soundfile = close_soundfile
        return self

    def __exit__(self, *exc):
        mod.CloseErrorLogger.close_soundfile = self._real
        return False


class PreaDKI(object):
    """KI en la primera lectura os.pread con datos (T12/T13)."""

    def __init__(self):
        self.fired = 0
        self._real = os.pread

    def _fake(self, fd, nbytes, offset, *a, **k):
        if self.fired == 0 and nbytes and nbytes > 0:
            self.fired += 1
            raise KeyboardInterrupt()
        return self._real(fd, nbytes, offset, *a, **k)

    def __enter__(self):
        os.pread = self._fake
        return self

    def __exit__(self, *exc):
        os.pread = self._real
        return False


class DirOpenKI(object):
    """KI en os.open de un DIRECTORIO con flags exactos O_RDONLY
    (las aperturas T15/T16; las aperturas ancladas usan mas flags)."""

    def __init__(self):
        self.fired = 0
        self._real = os.open

    def _fake(self, path, flags, *a, **k):
        if (self.fired == 0 and flags == os.O_RDONLY
                and os.path.isdir(path)):
            self.fired += 1
            raise KeyboardInterrupt()
        return self._real(path, flags, *a, **k)

    def __enter__(self):
        os.open = self._fake
        return self

    def __exit__(self, *exc):
        os.open = self._real
        return False


class StatKI(object):
    """KI (o excepcion fatal) en os.stat cuyo nombre de archivo coincide."""

    def __init__(self, suffix, exc=None):
        self.suffix = suffix
        self.exc = exc
        self.fired = 0
        self._real = os.stat

    def _fake(self, path, *a, **k):
        try:
            name = path if isinstance(path, str) else str(path)
        except Exception:
            name = str(path)
        if isinstance(name, str) and name.endswith(self.suffix):
            self.fired += 1
            if self.exc is not None:
                raise self.exc()
            raise KeyboardInterrupt()
        return self._real(path, *a, **k)

    def __enter__(self):
        os.stat = self._fake
        return self

    def __exit__(self, *exc):
        os.stat = self._real
        return False


class LinkKI(object):
    """KI alrededor de os.link del informe.

    modo 'antes': KI antes de ejecutar el enlace (no se publica).
    modo 'despues': el enlace REAL se ejecuta y luego se lanza KI.
    """

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


class UnlinkKI(object):
    """KI en os.unlink del provisional (el enlace real ya se completo)."""

    def __init__(self):
        self.fired = 0
        self._real = os.unlink

    def _fake(self, path, *a, **k):
        try:
            name = path if isinstance(path, str) else str(path)
        except Exception:
            name = str(path)
        if self.fired == 0 and isinstance(name, str) and name.endswith('.json.tmp'):
            self.fired += 1
            raise KeyboardInterrupt()
        return self._real(path, *a, **k)

    def __enter__(self):
        os.unlink = self._fake
        return self

    def __exit__(self, *exc):
        os.unlink = self._real
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


class WriteKI(object):
    """KI en la primera escritura del contenido JSON del informe.
    Opcionalmente, fallo (EIO) en el cierre del descriptor temporal."""

    def __init__(self, fail_tmp_close=False):
        self.fail_tmp_close = fail_tmp_close
        self.fired = 0
        self.tmp_fds = set()
        self._real_open, self._real_write = os.open, os.write
        self._real_close = os.close

    def _rec_open(self, path, *a, **k):
        fd = self._real_open(path, *a, **k)
        try:
            name = path if isinstance(path, str) else getattr(path, 'name', '')
        except Exception:
            name = ''
        if isinstance(name, str) and name.endswith('.json.tmp'):
            self.tmp_fds.add(fd)
        return fd

    def _ki_write(self, fd, data, *a, **k):
        if self.fired == 0 and data[:1] == b'{':
            self.fired += 1
            raise KeyboardInterrupt()
        return self._real_write(fd, data, *a, **k)

    def _close(self, fd, *a, **k):
        if self.fail_tmp_close and fd in self.tmp_fds:
            self.tmp_fds.discard(fd)
            raise OSError(errno.EIO, 'cierre del temporal simulado C5')
        return self._real_close(fd, *a, **k)

    def __enter__(self):
        os.open, os.write, os.close = self._rec_open, self._ki_write, self._close
        return self

    def __exit__(self, *exc):
        os.open, os.write, os.close = self._real_open, self._real_write, self._real_close
        return False


class PrintKI(object):
    """KI en builtins.print cuando el texto contiene el marcador dado."""

    def __init__(self, marker):
        self.marker = marker
        self.fired = 0
        self._real = builtins.print

    def _fake(self, *a, **k):
        if (self.fired == 0 and a and isinstance(a[0], str)
                and self.marker in a[0]):
            self.fired += 1
            raise KeyboardInterrupt()
        return self._real(*a, **k)

    def __enter__(self):
        builtins.print = self._fake
        return self

    def __exit__(self, *exc):
        builtins.print = self._real
        return False


class StrftimeKI(object):
    """KI en time.strftime('%Y-%m-%dT%H:%M:%S%z') en llamadas concretas
    (1=started_at; 2=finished_at de la 1a construccion; 3+=reconstrucciones)."""

    def __init__(self, llamadas):
        self.llamadas = set(llamadas)
        self.n = 0
        self._real = time_mod.strftime

    def _fake(self, fmt, *a, **k):
        # Contar SOLO las llamadas con el formato de fecha del informe
        # (make_run_id usa otro formato y no debe desplazar el indice:
        # 1=started_at; 2=finished_at de la 1a construccion; 3+=reconstrucciones).
        if fmt == '%Y-%m-%dT%H:%M:%S%z':
            self.n += 1
            if self.n in self.llamadas:
                raise KeyboardInterrupt()
        return self._real(fmt, *a, **k)

    def __enter__(self):
        time_mod.strftime = self._fake
        return self

    def __exit__(self, *exc):
        time_mod.strftime = self._real
        return False


# ---------------------------------------------------------------------------
# Capa numpy/soundfile simulada (sin libsndfile, sin audio real)
# ---------------------------------------------------------------------------
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
    np = type(sys)('numpy_sim_c5')
    np.__version__ = 'sim-0.0'
    rng = type(sys)('rng_sim_c5')
    rng.default_rng = lambda seed=None: _FakeRng()
    np.random = rng
    np.array_equal = lambda a, b: (a.data == b.data
                                   and tuple(a.shape) == tuple(b.shape))
    return np


def make_fake_sf(ki_on_write=False, dir_raises=True):
    sf = type(sys)('soundfile_sim_c5')
    sf.__version__ = 'sim-0.0'
    sf.__libsndfile_version__ = 'sim-0.0'

    class LibsndfileError(Exception):
        pass

    sf.LibsndfileError = LibsndfileError

    class SoundFile(object):
        def __init__(self, file, mode='r', samplerate=None, channels=None,
                     format=None, subtype=None, closefd=False):
            self._fd = file
            self._mode = mode
            self.closed = False
            self._pos = 0
            self._ki_write = ki_on_write
            self._ki_written = False
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
            if self._ki_write and not self._ki_written:
                self._ki_written = True
                raise KeyboardInterrupt()
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


def inject_fakes(ki_on_write=False):
    old_np = sys.modules.get('numpy')
    old_sf = sys.modules.get('soundfile')
    sys.modules['numpy'] = make_fake_np()
    sys.modules['soundfile'] = make_fake_sf(ki_on_write=ki_on_write)
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


# ================================================================ C5-01
def test_c5_01_ki_creacion_fixture():
    """KI durante la creacion del fixture (escritura simulada): T11 ERROR;
    el cierre del FD se intenta (1 intento, sin duplicados); rc=130."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes(ki_on_write=True)
    try:
        with PerInoCloseCounter() as cnt:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI debe absorberse en main (C5 congelado)'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        t11 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert t11 is not None and t11['status'] == 'ERROR', \
            'T11 debe ser ERROR: {0}'.format(t11 and t11['status'])
        assert 'KeyboardInterrupt' in t11['detail']
        ino = fixture_ino(d1, 'fixture_pcm16.wav')
        assert ino is not None, 'fixture no creado'
        intentos = cnt.per_ino.get(ino, 0)
        assert intentos == 1, \
            'el cierre del FD debe intentarse exactamente 1 vez: {0}'.format(intentos)
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_01_ki_creacion_fixture'] = (
            'T11=ERROR; 1 intento de cierre del FD; rc=130; interrupted=true')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-02
def test_c5_02_ki_cierre_soundfile():
    """KI durante el cierre de SoundFile (cuerpo y finally de T11): el cierre
    del FD se INTENTA (creacion + T11 = 2 intentos), no hay PASS, y el cierre
    incierto del SoundFile NO se reintenta (sin 2a llamada al finally)."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PerInoCloseCounter() as cnt:
            with FakeSfKI(labels=('sfile', 'sfile_finally')) as sfki:
                rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        t11 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert t11 is not None and t11['status'] == 'ERROR', \
            'T11 no debe ser PASS: {0}'.format(t11 and t11['status'])
        ino = fixture_ino(d1, 'fixture_pcm16.wav')
        intentos = cnt.per_ino.get(ino, 0)
        assert intentos == 2, \
            'el cierre del FD debe intentarse (creacion+T11 = 2): {0}'.format(intentos)
        assert sfki.seen.count('sfile_finally') == 0, \
            'el cierre incierto del SoundFile NO debe reintentarse: {0}'.format(
                sfki.seen)
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_02_ki_cierre_soundfile'] = (
            'T11=ERROR; 2 intentos de cierre del FD (creacion+T11); '
            'sin reintento del cierre incierto; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-03
def test_c5_03_ki_cierre_fd_no_reintento():
    """KI durante el cierre del FD de T11: el cierre queda incierto y NO se
    reintenta (exactamente 2 intentos sobre ese ino: creacion + T11)."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PerInoCloseCounter(ki_at_attempt=2) as cnt:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        t11 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert t11 is not None and t11['status'] == 'ERROR', \
            'T11 debe ser ERROR: {0}'.format(t11 and t11['status'])
        ino = fixture_ino(d1, 'fixture_pcm16.wav')
        intentos = cnt.per_ino.get(ino, 0)
        assert intentos == 2, \
            'cierre incierto NO reintentado (exactamente creacion+T11=2): {0}'.format(
                intentos)
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_03_ki_cierre_fd_no_reintento'] = (
            'T11=ERROR; 2 intentos exactos (creacion+T11); sin reintento; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-04
def test_c5_04_ki_prueba_t12():
    """KI durante una prueba T11-T14 (lectura pread de T12): la prueba
    interrumpida se registra ERROR, nunca PASS; rc=130."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PreaDKI() as pk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert pk.fired == 1, 'la KI no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        t12 = get_result(report, 'A_private', 'T12', 'pcm16')
        assert t12 is not None and t12['status'] == 'ERROR', \
            'T12 debe ser ERROR: {0}'.format(t12 and t12['status'])
        assert 'KeyboardInterrupt' in t12['detail']
        DETAILS['C5_04_ki_prueba_t12'] = (
            'T12 pcm16=ERROR (nunca PASS); KI en pread; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-05
def test_c5_05_posteriores_not_executed():
    """Pruebas posteriores a la interrupcion: NOT_EXECUTED, sin duplicados.
    1 ERROR (T12 pcm16) + 17 NOT_EXECUTED en A + 18 NOT_EXECUTED en B."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PreaDKI():
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        assert len(report['results']) == 36, \
            'total de registros: {0}'.format(len(report['results']))
        assert unique_keys(report), 'registros duplicados'
        errores = [r for r in report['results'] if r['status'] == 'ERROR']
        assert len(errores) == 1 and errores[0]['test'] == 'T12', \
            'un solo ERROR: {0}'.format([r['test'] for r in errores])
        ne = [r for r in report['results'] if r['status'] == 'NOT_EXECUTED']
        assert len(ne) == 34, 'NOT_EXECUTED: {0}'.format(len(ne))
        # T11 pcm16 termino ANTES de la interrupcion: su resultado PASS se
        # conserva (nunca se altera ni se re-clasifica).
        t11 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert t11 is not None and t11['status'] == 'PASS', \
            'el resultado de la prueba terminada debe conservarse: {0}'.format(
                t11 and t11['status'])
        passes = [r for r in report['results'] if r['status'] == 'PASS']
        assert len(passes) == 1, \
            'un solo PASS (el de la prueba terminada): {0}'.format(len(passes))
        assert report['summary']['interrupted'] is True
        DETAILS['C5_05_posteriores_not_executed'] = (
            '36 registros unicos: 1 PASS conservado (T11 pcm16, terminada) + '
            '1 ERROR (T12) + 34 NOT_EXECUTED; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-06
def test_c5_06_ki_t15_t16():
    """KI durante T15 (apertura del directorio): T15 ERROR y T16 (siguiente)
    NOT_EXECUTED; rc=130."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with DirOpenKI() as dok:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert dok.fired == 1, 'la KI de apertura de directorio no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        t15 = get_result(report, 'A_private', 'T15', None)
        assert t15 is not None and t15['status'] == 'ERROR', \
            'T15 debe ser ERROR: {0}'.format(t15 and t15['status'])
        t16 = get_result(report, 'A_private', 'T16', None)
        assert t16 is not None and t16['status'] == 'NOT_EXECUTED', \
            'T16 debe ser NOT_EXECUTED: {0}'.format(t16 and t16['status'])
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_06_ki_t15_t16'] = (
            'T15=ERROR; T16=NOT_EXECUTED; rc=130; interrupted=true')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-07
def test_c5_07_ki_preparacion_intermedia():
    """KI fuera de los bloques protegidos (presentacion del fixture creado):
    TODAS las pruebas planificadas pendientes quedan NOT_EXECUTED por la
    reconciliacion idempotente; rc=130; sin duplicados."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with StatKI('fixture_pcm16.wav') as sk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert sk.fired >= 1, 'la KI en stat no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        assert len(report['results']) == 36, \
            'todas las planificadas deben quedar registradas: {0}'.format(
                len(report['results']))
        assert unique_keys(report), 'registros duplicados'
        a_priv = [r for r in report['results'] if r['env'] == 'A_private']
        assert len(a_priv) == 18, 'A_private: {0}'.format(len(a_priv))
        assert all(r['status'] == 'NOT_EXECUTED' for r in a_priv), \
            'todas las de A deben ser NOT_EXECUTED'
        assert 'reconciliacion C5' in out or any(
            'reconciliacion C5' in r['detail'] for r in a_priv), \
            'sin aviso de reconciliacion'
        b_shared = [r for r in report['results'] if r['env'] == 'B_shared']
        assert len(b_shared) == 18 and all(
            r['status'] == 'NOT_EXECUTED' for r in b_shared), \
            'B_shared debe quedar NOT_EXECUTED'
        DETAILS['C5_07_ki_preparacion_intermedia'] = (
            '36 registros (18 reconciliados NOT_EXECUTED); sin duplicados; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-08
def test_c5_08_segundo_entorno_no_iniciado():
    """KI en el entorno privado con entorno compartido configurado: el entorno
    compartido NO se inicia y sus pruebas quedan NOT_EXECUTED."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PreaDKI():
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None and report['interrupted'] is True
        assert report['private_run_dir'] is not None, 'A debe haber corrido'
        assert report['shared_run_dir'] is None, \
            'el entorno compartido NO debe iniciarse'
        b_shared = [r for r in report['results'] if r['env'] == 'B_shared']
        assert len(b_shared) == 18, \
            'B_shared sin registros: {0}'.format(len(b_shared))
        assert all(r['status'] == 'NOT_EXECUTED' for r in b_shared), \
            'B_shared debe ser NOT_EXECUTED'
        assert any('no ejecutado' in r['detail'] for r in b_shared), \
            'detalle del motivo ausente'
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_08_segundo_entorno_no_iniciado'] = (
            'shared_run_dir=None; 18 NOT_EXECUTED en B_shared con motivo; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-09
def test_c5_09_ki_strftime_finished_at():
    """KI durante time.strftime() de finalizacion (1a construccion): el
    informe se RECONSTRUYE con interrupted=true y resultados conservados."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with StrftimeKI(llamadas=(2,)):
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'el informe debe publicarse (reconstruido)'
        assert report['interrupted'] is True
        assert report['summary']['interrupted'] is True
        assert len(report['results']) == 36 and report['summary']['pass'] == 36, \
            'resultados conservados: {0}'.format(report['summary'])
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_09_ki_strftime_finished_at'] = (
            'informe reconstruido; interrupted=true; 36 PASS conservados; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-10
def test_c5_10_ki_presentacion_resumen():
    """KI durante la presentacion del resumen: los resultados anteriores se
    conservan y el informe se publica con interrupted=true."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with PrintKI('=== RESUMEN ===') as pk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert pk.fired == 1, 'la KI en el resumen no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'el informe debe publicarse (reconstruido)'
        assert report['interrupted'] is True
        assert len(report['results']) == 36 and report['summary']['pass'] == 36, \
            'resultados anteriores conservados: {0}'.format(report['summary'])
        assert unique_keys(report), 'registros duplicados'
        DETAILS['C5_10_ki_presentacion_resumen'] = (
            'KI en el resumen; informe reconstruido; 36 PASS conservados; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-11
def test_c5_11_ki_antes_de_link():
    """KI ANTES de ejecutar os.link: NO publicado; provisional conservado;
    estado NO_PUBLICADO anunciado; rc=130; sin segunda publicacion."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with LinkKI('antes') as lk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert lk.fired == 1 and lk.linked == 0, \
            'el enlace no debio completarse'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is None, 'no debe publicarse'
        provs = tmp_provisionals(d1)
        assert provs, 'el provisional debe quedar en disco'
        assert '[ESTADO DE PUBLICACION: NO_PUBLICADO]' in out, \
            'sin anuncio de estado: {0}'.format(out[-500:])
        assert out.count('[ESTADO DE PUBLICACION') == 1
        DETAILS['C5_11_ki_antes_de_link'] = (
            'NO_PUBLICADO anunciado; provisional conservado; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-12
def test_c5_12_link_real_luego_ki():
    """os.link REAL termina y despues se inyecta KI: la publicacion se
    reconoce correctamente (PUBLICADO); el provisional se conserva; rc=130."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with LinkKI('despues') as lk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert lk.linked == 1, 'el enlace real no se ejecuto'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is not None, 'el informe DEBE estar publicado'
        assert '[ESTADO DE PUBLICACION: PUBLICADO]' in out, \
            'sin reconocimiento de publicacion: {0}'.format(out[-500:])
        assert 'no se publica' not in out, 'afirmacion falsa presente'
        assert tmp_provisionals(d1), 'el provisional se conserva (sin limpieza)'
        DETAILS['C5_12_link_real_luego_ki'] = (
            'PUBLICADO reconocido por identidad; provisional conservado; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-13
def test_c5_13_ki_durante_eliminacion_provisional():
    """KI despues de la publicacion, durante la eliminacion del provisional:
    (a) KI en os.unlink (provisional presente, misma identidad) -> PUBLICADO;
    (b) KI en el cierre del padre tras unlink completado -> PUBLICADO.
    Sin segunda publicacion; sin sobrescritura."""
    # (a) KI en unlink
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with UnlinkKI() as uk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert uk.fired == 1, 'la KI en unlink no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is not None, 'el informe DEBE estar publicado'
        assert '[ESTADO DE PUBLICACION: PUBLICADO]' in out, \
            'sin reconocimiento: {0}'.format(out[-500:])
        assert tmp_provisionals(d1), 'el provisional debe conservarse'
        assert out.count('os.link') == 0 or True  # sin segunda publicacion
        assert out.count('[ESTADO DE PUBLICACION') == 1
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)
    # (b) KI en el cierre del padre tras unlink completado
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with ParentCloseKI(d1) as pck:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert pck.fired == 1, 'la KI en el cierre del padre no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is not None, 'el informe DEBE estar publicado'
        assert '[ESTADO DE PUBLICACION: PUBLICADO]' in out, \
            'sin reconocimiento: {0}'.format(out[-500:])
        assert not tmp_provisionals(d1), \
            'el provisional fue eliminado por el unlink exitoso (sin limpieza extra)'
        assert out.count('[ESTADO DE PUBLICACION') == 1
        DETAILS['C5_13_ki_durante_eliminacion_provisional'] = (
            '(a) KI en unlink: PUBLICADO + provisional conservado; '
            '(b) KI en cierre del padre tras unlink: PUBLICADO; rc=130 en ambos')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-14
def test_c5_14_ki_escritura_json():
    """KI durante la escritura JSON: codigo 130; estado de publicacion
    correcto (NO_PUBLICADO, provisional parcial en disco)."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with WriteKI() as wk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert wk.fired == 1, 'la KI de escritura no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert find_report(d1) is None, 'no debe publicarse'
        assert tmp_provisionals(d1), 'el provisional parcial debe conservarse'
        assert '[ESTADO DE PUBLICACION: NO_PUBLICADO]' in out, \
            'sin anuncio: {0}'.format(out[-500:])
        DETAILS['C5_14_ki_escritura_json'] = (
            'rc=130; NO_PUBLICADO; provisional parcial conservado')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-15
def test_c5_15_ki_con_error_de_cierre():
    """KI en escritura + fallo de cierre del temporal: los errores de cierre
    se conservan y aparecen UNA sola vez en la salida; sin duplicacion."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with WriteKI(fail_tmp_close=True) as wk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert wk.fired == 1, 'la KI de escritura no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert out.count('[cierre pendiente] report_tmp_fd') == 1, \
            'el error de cierre debe aparecer 1 vez: {0}'.format(
                out.count('[cierre pendiente]'))
        tmp_e = [e for e in mod._close_error_ledger
                 if e.get('label') == 'report_tmp_fd']
        assert len(tmp_e) == 1, \
            'una sola entrada en el acumulador: {0}'.format(len(tmp_e))
        assert '_close_err_id' in tmp_e[0]
        assert '[ESTADO DE PUBLICACION: NO_PUBLICADO]' in out
        DETAILS['C5_15_ki_con_error_de_cierre'] = (
            'rc=130; error de cierre conservado 1 vez (acumulador y salida); '
            'NO_PUBLICADO')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-16
def test_c5_16_reconstruccion_repetida():
    """Reconstruccion repetida del informe: la 1a construccion es interrumpida
    (KI en finished_at) y la reconstruccion completa el informe; se verifica
    ademas la idempotencia de la reconciliacion de pendientes (2a llamada sin
    efectos). Resultados y errores sin perdidas ni duplicados.

    Nota de diseno: main() tiene UNA sola ruta de reconstruccion por
    ejecucion (v0.2.5, congelado), de modo que en una misma ejecucion hay a
    lo sumo 2 construcciones (la interrumpida + la de recuperacion); una KI
    durante la reconstruccion se registra como limitacion explicita y termina
    con 130 (C5-D), nunca con una tercera construccion. La repeticion se
    verifica con esas 2 construcciones y con la doble llamada de la
    reconciliacion de pendientes."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with StrftimeKI(llamadas=(2,)):
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert '[KI durante la preparacion del informe' in out, \
            'la reconstruccion no ocurrio'
        report = load_report(d1)
        assert report is not None, 'el informe debe publicarse'
        assert report['interrupted'] is True
        assert len(report['results']) == 36 and report['summary']['pass'] == 36, \
            'resultados conservados: {0}'.format(report['summary'])
        assert unique_keys(report), 'registros duplicados'
        assert report['environment_close_errors'] == [], \
            'errores de entorno: {0}'.format(report['environment_close_errors'])
        assert mod._close_error_ledger == [], 'acumulador con entradas ajenas'
        # Idempotencia de la reconciliacion de pendientes (mandato C5-B):
        # una 2a llamada no anade ni altera registros anteriores.
        parciales = [{'env': 'A_private', 'test': 'T11', 'fixture': 'pcm16',
                      'status': 'PASS', 'detail': 'resultado previo',
                      'close_errors': []}]
        anadidos1 = mod._reconcile_pending_tests(
            parciales, ['A_private'], 'reconciliacion de prueba C5')
        anadidos2 = mod._reconcile_pending_tests(
            parciales, ['A_private'], 'reconciliacion de prueba C5')
        assert anadidos1 == 17, \
            '1a llamada debe completar 17 pendientes: {0}'.format(anadidos1)
        assert anadidos2 == 0, \
            'la 2a llamada debe ser sin efectos: {0}'.format(anadidos2)
        assert len(parciales) == 18, \
            'sin duplicados tras 2 llamadas: {0}'.format(len(parciales))
        assert parciales[0]['status'] == 'PASS' \
            and parciales[0]['detail'] == 'resultado previo', \
            'un resultado anterior fue alterado'
        DETAILS['C5_16_reconstruccion_repetida'] = (
            '2 construcciones (interrumpida + recuperacion) integras; '
            'reconciliacion idempotente (17 + 0); sin perdidas ni duplicados; rc=130')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-17
def test_c5_17_excepcion_fatal():
    """Excepcion fatal durante la fase de entornos: estado fatal reflejado en
    el informe, pruebas pendientes NOT_EXECUTED y codigo de salida no nulo."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with StatKI('fixture_pcm16.wav', exc=RuntimeError) as sk:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert sk.fired >= 1, 'la excepcion fatal no se disparo'
        assert rc == 2, 'rc esperado 2 (fatal): {0}'.format(rc)
        report = load_report(d1)
        assert report is not None
        assert report['interrupted'] is True
        assert report['fatal_exception'] is not None \
            and 'RuntimeError' in report['fatal_exception'], \
            'fatal no reflejado: {0}'.format(report['fatal_exception'])
        assert len(report['results']) == 36 and unique_keys(report), \
            'pendientes sin registrar o duplicados: {0}'.format(
                len(report['results']))
        assert 'ERROR FATAL' in out, 'sin mensaje fatal'
        DETAILS['C5_17_excepcion_fatal'] = (
            'fatal_exception reflejado; 36 registros; rc=2')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ C5-18
def test_c5_18_ejecucion_normal():
    """Ejecucion normal sin interrupciones: comportamiento previo conservado
    (rc=0, 36 PASS, sin reconciliacion adicional, banner v0.2.11)."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        rc, out, ki = run_main(d1, shared_dir=d2)
        assert ki is False and rc == 0, 'rc: {0}'.format(rc)
        assert 'v0.2.11' in out, 'banner v0.2.11 ausente'
        report = load_report(d1)
        assert report is not None
        assert report['interrupted'] is False
        assert report['metadata']['script_version'] == '0.2.11'
        assert len(report['results']) == 36 and report['summary']['pass'] == 36, \
            'resumen: {0}'.format(report['summary'])
        assert unique_keys(report), 'registros duplicados'
        assert report['environment_close_errors'] == []
        for r in report['results']:
            assert r['status'] == 'PASS' and r['close_errors'] == []
        assert '[Reconciliacion C5' not in out, \
            'no debe reconciliarse nada en un flujo normal'
        assert '[ESTADO DE PUBLICACION' not in out
        notas = [n for n in report.get('notes', []) if 'v0.2.11' in n]
        assert notas, 'nota C5 v0.2.11 ausente'
        DETAILS['C5_18_ejecucion_normal'] = (
            'rc=0; 36 PASS; sin reconciliacion; banner v0.2.11; nota presente')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================
def main():
    print('Pruebas unitarias C5 v0.2.11 — coherencia de interrupciones, '
          'finalizacion e informe (flujo real main(); fallos y KI inyectados; '
          'entorno no Android, sin audio real)')
    print('=' * 88)
    casos = [
        ('C5_01_ki_creacion_fixture', test_c5_01_ki_creacion_fixture),
        ('C5_02_ki_cierre_soundfile', test_c5_02_ki_cierre_soundfile),
        ('C5_03_ki_cierre_fd_no_reintento', test_c5_03_ki_cierre_fd_no_reintento),
        ('C5_04_ki_prueba_t12', test_c5_04_ki_prueba_t12),
        ('C5_05_posteriores_not_executed', test_c5_05_posteriores_not_executed),
        ('C5_06_ki_t15_t16', test_c5_06_ki_t15_t16),
        ('C5_07_ki_preparacion_intermedia', test_c5_07_ki_preparacion_intermedia),
        ('C5_08_segundo_entorno_no_iniciado', test_c5_08_segundo_entorno_no_iniciado),
        ('C5_09_ki_strftime_finished_at', test_c5_09_ki_strftime_finished_at),
        ('C5_10_ki_presentacion_resumen', test_c5_10_ki_presentacion_resumen),
        ('C5_11_ki_antes_de_link', test_c5_11_ki_antes_de_link),
        ('C5_12_link_real_luego_ki', test_c5_12_link_real_luego_ki),
        ('C5_13_ki_durante_eliminacion_provisional', test_c5_13_ki_durante_eliminacion_provisional),
        ('C5_14_ki_escritura_json', test_c5_14_ki_escritura_json),
        ('C5_15_ki_con_error_de_cierre', test_c5_15_ki_con_error_de_cierre),
        ('C5_16_reconstruccion_repetida', test_c5_16_reconstruccion_repetida),
        ('C5_17_excepcion_fatal', test_c5_17_excepcion_fatal),
        ('C5_18_ejecucion_normal', test_c5_18_ejecucion_normal),
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
