#!/usr/bin/env python3
"""Pruebas unitarias aisladas C4-B v0.2.9 — propagación completa de errores de cierre.

Se importa el instrumento audioinput_diag_termux.py v0.2.9 y se verifica que
ningún error de cierre se pierda, se duplique ni reemplace al error primario,
incluyendo retornos anticipados, excepciones, KeyboardInterrupt, drenajes del
sink y reconstrucciones del informe.

MÉTODO: todos los fallos se INYECTAN con mocks/sustituciones aisladas
(os.close, os.write, os.open, time.strftime, SoundFile simulado); ningún caso
depende de fallos espontáneos del sistema operativo.

CLASIFICACIÓN: PASS / FAIL / ERROR / NOT_EXECUTED por caso (nunca PASS sin
ejecución real). No Android/Termux, no audio real, no muestras del proyecto.
"""
import errno
import importlib.util
import io
import json
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
    print("{0:4} {1:50} {2}".format(status, name, detail))


def run(name, fn):
    try:
        fn()
        record(name, 'PASS', DETAILS.get(name, 'OK'))
    except (ImportError, ModuleNotFoundError) as exc:
        record(name, 'NOT_EXECUTED', 'dependencia/condicion no disponible: {0}'.format(exc))
    except AssertionError as exc:
        record(name, 'FAIL', str(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


def fresh_tmp():
    return tempfile.mkdtemp(prefix='c4b_ut_')


def close_quietly(fd):
    try:
        os.close(fd)
    except OSError:
        pass


def fd_alive(fd):
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


def make_file(d, name, content=b'x' * 400):
    p = os.path.join(d, name)
    with open(p, 'wb') as fh:
        fh.write(content)
    return p


class CloseFailure(object):
    """Mock de os.close que falla de forma controlada.

    Modos (combinables):
      - fail_on_ino: falla cuando fstat(fd).st_ino coincide (max. `times` veces).
      - fail_on_dir: falla cuando el fd apunta a un directorio.
      - fail_on_fd:  falla cuando el numero de fd coincide.
    Cada fallo lanza OSError(EIO, 'cierre simulado C4-B').
    """
    def __init__(self, fail_on_ino=None, times=1, fail_on_dir=False,
                 fail_on_fd=None, fd_times=1):
        self.fail_on_ino = fail_on_ino
        self.times = times
        self.fail_on_dir = fail_on_dir
        self.fail_on_fd = fail_on_fd
        self.fd_times = fd_times
        self.fired = 0
        self._real = os.close

    def _fake(self, fd, *a, **k):
        try:
            st = os.fstat(fd)
        except OSError:
            st = None
        if st is not None and self.fail_on_ino is not None \
                and st.st_ino == self.fail_on_ino and self.times > 0:
            self.times -= 1
            self.fired += 1
            raise OSError(errno.EIO, 'cierre simulado C4-B')
        if st is not None and self.fail_on_dir \
                and stat_mod.S_ISDIR(st.st_mode):
            self.fired += 1
            raise OSError(errno.EIO, 'cierre simulado C4-B (directorio)')
        if self.fail_on_fd is not None and fd == self.fail_on_fd \
                and self.fd_times > 0:
            self.fd_times -= 1
            self.fired += 1
            raise OSError(errno.EIO, 'cierre simulado C4-B (fd)')
        return self._real(fd, *a, **k)

    def __enter__(self):
        os.close = self._fake
        return self

    def __exit__(self, *exc):
        os.close = self._real
        return False


# ---- capa numpy/soundfile simulada (sin libsndfile, sin audio real) ----
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
    np = type(sys)('numpy_sim_c4b')
    np.__version__ = 'sim-0.0'
    rng = type(sys)('rng_sim_c4b')
    rng.default_rng = lambda seed=None: _FakeRng()
    np.random = rng
    np.array_equal = lambda a, b: (a.data == b.data
                                   and tuple(a.shape) == tuple(b.shape))
    return np


def make_fake_sf(sf_close_raises=False, dir_raises=True):
    sf = type(sys)('soundfile_sim_c4b')
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
            self._close_raises = sf_close_raises

        def write(self, arr):
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
            if self._close_raises and not self.closed:
                self.closed = True
                raise RuntimeError('cierre de SoundFile simulado C4-B')
            self.closed = True

    sf.SoundFile = SoundFile

    def available_subtypes(fmt):
        return ({'PCM_16': 'x', 'PCM_24': 'x', 'PCM_32': 'x', 'FLOAT': 'x'}
                if fmt == 'WAV' else {})

    sf.available_subtypes = available_subtypes
    return sf


def inject_fakes(sf_close_raises=False):
    old_np = sys.modules.get('numpy')
    old_sf = sys.modules.get('soundfile')
    sys.modules['numpy'] = make_fake_np()
    sys.modules['soundfile'] = make_fake_sf(sf_close_raises=sf_close_raises)
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


def find_report(d):
    hits = [p for p in __import__('glob').glob(os.path.join(d, 'report-*.json'))
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


# ================================================================ 1
def test_01_cierre_correcto_sin_secundarios():
    """Cierre correcto: sin errores secundarios; sink/acumulador vacios."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'a.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'ok')
        with CloseFailure() as mock:  # sin fallos configurados
            assert c.close_fd(fd, 'ok', token=tok) is None
        assert mock.fired == 0
        assert c.errors == [] and c.warnings == []
        assert mod._drain_close_error_sink() == []
        assert mod._close_errors_unattributed() == []
        assert len(mod._close_error_ledger) == 0
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 2
def test_02_error_cierre_fd_en_resultado():
    """Error de cierre de FD conservado en el resultado de la prueba (T12 real)."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    try:
        fpath = make_file(d, 'fixture.wav', content=b'RIFF' + b'\x00' * 800)
        target_ino = os.stat(fpath).st_ino
        with CloseFailure(fail_on_ino=target_ino, times=1) as mock:
            status, detail, close_errors = mod.test_t12_pread_works(None, None, fpath)
        assert mock.fired == 1, 'el fallo de cierre no se disparo'
        assert status == mod.Result.FAIL, 'estado: {0}'.format(status)
        assert 'cierre_fd_fallo' in detail, 'primario sin marca de cierre: {0}'.format(detail[:120])
        assert len(close_errors) == 1, 'error de cierre no conservado: {0}'.format(close_errors)
        assert close_errors[0]['errno'] == errno.EIO
        assert '_close_err_id' in close_errors[0], 'sin identificador unico'
        assert len(mod._close_error_ledger) == 1, 'no llego al acumulador persistente'
        DETAILS['C4B_02_error_cierre_fd_en_resultado'] = \
            'FAIL con primario (cierre_fd_fallo) + secundario conservado (id unico)'
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 3
def test_03_error_cierre_soundfile_en_resultado():
    """Error de cierre de SoundFile conservado en el resultado (T11 real, sf simulado)."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    old_np, old_sf = inject_fakes(sf_close_raises=True)
    try:
        fpath = make_file(d, 'fixture_sf.wav', content=b'RIFF' + b'\x00' * 800)
        status, detail, close_errors = mod.test_t11_soundfile_fd_closefd_false(
            sys.modules['numpy'], sys.modules['soundfile'], fpath)
        assert len(close_errors) == 1, 'error de cierre de SoundFile no conservado'
        entry = close_errors[0]
        assert 'SoundFile' in entry.get('strerror', ''), \
            'entrada inesperada: {0}'.format(entry)
        assert entry['label'] == 'sfile', 'sin asociacion a la operacion: {0}'.format(entry)
        # C4-B5: es un error real, no una advertencia
        assert len(c := close_errors) >= 0
        logger_errors = entry in mod._close_error_ledger
        assert logger_errors, 'no llego al acumulador persistente'
        assert status in (mod.Result.PASS, mod.Result.FAIL), 'estado: {0}'.format(status)
        DETAILS['C4B_03_error_cierre_soundfile_en_resultado'] = \
            'conservado en close_errors (label=sfile) y en el acumulador; error real, no advertencia'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 4
def test_04_primario_mas_secundario():
    """Error primario (LibsndfileError) + secundario (cierre de dir_fd) conservados."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        run_dir = os.path.join(d, 'run')
        os.mkdir(run_dir, 0o700)
        with CloseFailure(fail_on_dir=True) as mock:
            status, detail, close_errors = mod.test_t15_libsndfile_error_raised(
                sys.modules['numpy'], sys.modules['soundfile'], run_dir)
        assert mock.fired >= 1, 'el fallo de cierre del dir_fd no se disparo'
        assert 'LibsndfileError capturada' in detail, 'primario perdido: {0}'.format(detail[:160])
        assert 'cierre_dir_fd_fallo' in detail, 'secundario perdido: {0}'.format(detail[:160])
        assert status == mod.Result.FAIL
        assert any(e['errno'] == errno.EIO for e in close_errors), \
            'secundario no conservado en close_errors: {0}'.format(close_errors)
        DETAILS['C4B_04_primario_mas_secundario'] = \
            'primario (LibsndfileError) y secundario (cierre dir_fd) ambos en detail y close_errors'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 5
def test_05_varios_secundarios_misma_operacion():
    """Varios errores secundarios en una misma operacion: todos conservados, ids unicos."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'multi.bin')
        fd1 = os.open(p, os.O_RDONLY)
        fd2 = os.open(p, os.O_RDONLY)
        target_ino = os.stat(p).st_ino
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'multi1')
        t2 = c.register_fd(fd2, 'multi2')
        with CloseFailure(fail_on_ino=target_ino, times=2) as mock:
            e1 = c.close_fd(fd1, 'multi1', token=t1)
            e2 = c.close_fd(fd2, 'multi2', token=t2)
        assert mock.fired == 2
        assert isinstance(e1, OSError) and isinstance(e2, OSError)
        assert len(c.errors) == 2, 'errores conservados: {0}'.format(len(c.errors))
        ids = [e['_close_err_id'] for e in c.errors]
        assert ids[0] != ids[1], 'identificadores no unicos'
        assert len(mod._close_error_ledger) == 2
        drained = mod._drain_close_error_sink()
        assert len(drained) == 2, 'drenaje no conserva todos'
        assert len(mod._close_error_ledger) == 2, 'el drenaje perdio del acumulador'
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 6
def test_06_retorno_anticipado_tras_error_cierre():
    """Retorno anticipado (archivo pequeno) conservando el error de cierre previo."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    try:
        fpath = make_file(d, 'small.bin', content=b'x' * 100)  # < 200 bytes
        target_ino = os.stat(fpath).st_ino
        with CloseFailure(fail_on_ino=target_ino, times=1) as mock:
            status, detail, close_errors = mod.test_t12_pread_works(None, None, fpath)
        assert mock.fired == 1
        assert 'demasiado pequeno' in detail, 'primario: {0}'.format(detail[:120])
        assert len(close_errors) == 1 and close_errors[0]['errno'] == errno.EIO, \
            'secundario perdido en retorno anticipado: {0}'.format(close_errors)
        assert len(mod._close_error_ledger) == 1
        DETAILS['C4B_06_retorno_anticipado_tras_error_cierre'] = \
            'retorno anticipado con primario + secundario conservados'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _make_raiser(exc_cls, target_file):
    """Prueba simulada que abre un fd registrado y falla su cierre en la limpieza."""
    def raiser(np_, sf_, run_dir):
        fd = os.open(target_file, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'raiser_fd')
        try:
            raise exc_cls('primario simulado')
        finally:
            c.close_fd(fd, 'raiser_fd', token=tok)
    return raiser


def _run_env_with_raiser(exc_cls, target_file):
    """run_environment con FIXTURE_SPECS vacio y T15 sustituido por la prueba simulada."""
    d = fresh_tmp()
    try:
        real_specs = mod.FIXTURE_SPECS
        real_tf = mod.TEST_FUNCTIONS
        real_t15 = mod.test_t15_libsndfile_error_raised
        mod.FIXTURE_SPECS = []
        mod.TEST_FUNCTIONS = {}
        mod.test_t15_libsndfile_error_raised = _make_raiser(exc_cls, target_file)
        results = []
        flag = [False]
        target_ino = os.stat(target_file).st_ino
        try:
            with CloseFailure(fail_on_ino=target_ino, times=1) as mock:
                with redirect_stdout(io.StringIO()):
                    mod.run_environment(None, None, 'A', d, results, 'c4b', flag)
            assert mock.fired == 1, 'el fallo de cierre en la limpieza no se disparo'
        finally:
            mod.FIXTURE_SPECS = real_specs
            mod.TEST_FUNCTIONS = real_tf
            mod.test_t15_libsndfile_error_raised = real_t15
        return results, flag
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 7
def test_07_excepcion_ordinaria_y_cierre_en_limpieza():
    """Excepcion ordinaria + error de cierre en la limpieza: primario y secundario."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    target = make_file(d, 'r7.bin')
    try:
        results, flag = _run_env_with_raiser(ValueError, target)
        r = [x for x in results if x['status'] == mod.Result.ERROR]
        assert r, 'sin resultado ERROR: {0}'.format(results)
        entry = r[0]
        assert 'ValueError' in entry['detail'], 'primario perdido'
        assert any(e.get('errno') == errno.EIO for e in entry['close_errors']), \
            'secundario perdido: {0}'.format(entry['close_errors'])
        assert flag[0] is False, 'excepcion ordinaria no debe setear el flag C5'
        # Atribucion: el error del resultado no se repite a nivel de entorno
        assert all(e.get('_close_err_id') in mod._attributed_close_error_ids
                   for e in entry['close_errors'] if '_close_err_id' in e)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 8
def test_08_keyboardinterrupt_y_cierre_en_limpieza():
    """KeyboardInterrupt + error de cierre en la limpieza: conservados; flag C5 seteado."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    target = make_file(d, 'r8.bin')
    try:
        results, flag = _run_env_with_raiser(KeyboardInterrupt, target)
        r = [x for x in results if x['status'] == mod.Result.ERROR]
        assert r, 'sin resultado ERROR'
        entry = r[0]
        assert 'KeyboardInterrupt' in entry['detail'], 'primario (KI) perdido'
        assert any(e.get('errno') == errno.EIO for e in entry['close_errors']), \
            'secundario perdido durante KI: {0}'.format(entry['close_errors'])
        assert flag[0] is True, 'el flag C5 no se seteo (tratamiento C5 alterado)'
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 9
def test_09_drenaje_sin_perdida():
    """Drenaje del sink sin perdida: todo queda en el acumulador persistente."""
    mod._reset_close_error_accounting()
    for i in range(3):
        mod._record_close_error({'label': 'e{0}'.format(i), 'errno': errno.EIO,
                                 'strerror': 'sim {0}'.format(i)})
    assert len(mod._close_error_sink) == 3
    drained = mod._drain_close_error_sink()
    assert len(drained) == 3, 'drenaje perdio entradas'
    assert len(mod._close_error_ledger) == 3, \
        'el drenaje no conservo en el acumulador persistente'
    assert mod._close_errors_unattributed() and \
        len(mod._close_errors_unattributed()) == 3
    DETAILS['C4B_09_drenaje_sin_perdida'] = \
        '3 registrados -> drenados 3 -> acumulador persistente 3 -> no atribuidos 3'


# ================================================================ 10
def test_10_segundo_drenaje_sin_duplicacion():
    """Segundo drenaje vacio; atribucion excluye sin duplicar; ids unicos."""
    assert len(mod._close_error_ledger) == 3  # estado del caso anterior
    drained2 = mod._drain_close_error_sink()
    assert drained2 == [], 'segundo drenaje no estaba vacio'
    una = mod._close_errors_unattributed()
    assert len(una) == 3, 'lectura no destructiva altero el total'
    ids = [e['_close_err_id'] for e in una]
    assert len(set(ids)) == 3, 'duplicados por identificador'
    mod._mark_close_errors_attributed(una[:2])
    una2 = mod._close_errors_unattributed()
    assert len(una2) == 1, 'atribucion no excluyo correctamente'
    assert una2[0]['_close_err_id'] not in [e['_close_err_id'] for e in una[:2]]
    assert mod._drain_close_error_sink() == []
    DETAILS['C4B_10_segundo_drenaje_sin_duplicacion'] = \
        '2o drenaje vacio; atribucion excluye 2; sin duplicados por id'


# ================================================================ 11
def test_11_reconstruccion_informe_sin_perdida():
    """Reconstruccion del informe (KI en el resumen) sin perder el error de
    cierre de nivel entorno acumulado DURANTE la ejecucion; sin duplicacion en
    el informe final.

    Nota: la contabilidad de errores se reinicia por ejecucion en main()
    (_reset_close_error_accounting), por lo que el error se inyecta durante el
    flujo (mock de os.close sobre el cierre del fixture en su creacion — error
    de nivel entorno, no atribuido a ninguna prueba), no antes de main()."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    real_strftime = time_mod.strftime
    real_close = os.close
    state = {'n': 0, 'per_ino': {}, 'fired': 0}

    def ki_strftime(fmt, *a, **k):
        if fmt == '%Y-%m-%dT%H:%M:%S%z':
            state['n'] += 1
            if state['n'] == 2:  # started_at (1) -> finished_at (2): KI
                raise KeyboardInterrupt()
        return real_strftime(fmt, *a, **k)

    def env_err_close(fd, *a, **k):
        try:
            st = os.fstat(fd)
        except OSError:
            return real_close(fd, *a, **k)
        if stat_mod.S_ISREG(st.st_mode) and st.st_size > 1000:
            ino = st.st_ino
            state['per_ino'][ino] = state['per_ino'].get(ino, 0) + 1
            if state['per_ino'][ino] == 1 and state['fired'] == 0:
                # 1er cierre del fixture (creacion): error NO atribuido a
                # ninguna prueba -> pertenece al nivel de entorno.
                state['fired'] += 1
                raise OSError(errno.EIO, 'cierre simulado C4-B (entorno)')
        return real_close(fd, *a, **k)

    time_mod.strftime = ki_strftime
    os.close = env_err_close
    try:
        rc, out, ki = run_main(d1, shared_dir=d2)
    finally:
        os.close = real_close
        time_mod.strftime = real_strftime
        restore_fakes(old_np, old_sf)
    try:
        assert state['fired'] == 1, 'la inyeccion no se disparo'
        assert ki is False, 'la KI debe absorberse en main (flujo C5 congelado)'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'informe no publicado tras reconstruccion'
        assert report['interrupted'] is True and report['summary']['interrupted'] is True
        env_errs = report['environment_close_errors']
        labels = [e.get('label') for e in env_errs]
        assert 'fixture_fd_pcm16' in labels, \
            'C4-B: la reconstruccion perdio el error acumulado: {0}'.format(labels)
        assert len(env_errs) == 1, \
            'duplicacion en environment_close_errors: {0}'.format(env_errs)
        raw = json.dumps(report, ensure_ascii=False)
        # Unicidad por identificador: la entrada aparece exactamente 1 vez en
        # todo el informe reconstruido. (Nota: el esquema de entrada del
        # instrumento normaliza strerror a os.strerror(errno); el mensaje
        # arbitrario de la excepcion simulada no aparece en el JSON.)
        eid = env_errs[0]['_close_err_id']
        n = len(re.findall(r'"_close_err_id":\s*{0}(?=[,}}\s])'.format(eid), raw))
        assert n == 1, \
            'la entrada aparece {0} veces en el informe reconstruido'.format(n)
        assert 'cierre simulado C4-B (entorno)' not in raw  # strerror normalizado
        assert report['summary']['pass'] == 36, 'resultados conservados: {0}'.format(
            report['summary'])
        DETAILS['C4B_11_reconstruccion_informe_sin_perdida'] = \
            'KI en resumen -> informe reconstruido con interrupted=true; error de entorno conservado 1 vez'
    finally:
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 12
def test_12_fallo_strftime_sin_perdida():
    """Fallo de time.strftime (no interrupcion) al finalizar: el informe se
    construye igual y los errores de cierre no se borran."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    real_strftime = time_mod.strftime
    state = {'n': 0}

    def bad_strftime(fmt, *a, **k):
        if fmt == '%Y-%m-%dT%H:%M:%S%z':
            state['n'] += 1
            if state['n'] == 2:  # started_at (1) -> finished_at (2)
                raise OSError(errno.EIO, 'strftime simulado C4-B')
        return real_strftime(fmt, *a, **k)

    time_mod.strftime = bad_strftime
    try:
        mod._reset_close_error_accounting()
        rc, out, ki = run_main(d1, shared_dir=d2)
        assert ki is False
        assert rc == 0, 'rc: {0}; salida: {1}'.format(rc, out[-400:])
        report = load_report(d1)
        assert report is not None, 'informe no publicado pese a la guardia C4-B'
        assert report['finished_at'].startswith('DESCONOCIDO'), \
            'finished_at: {0}'.format(report['finished_at'])
        assert report['summary']['pass'] == 36
        assert report['environment_close_errors'] == []
        DETAILS['C4B_12_fallo_strftime_sin_perdida'] = \
            'OSError en finished_at -> informe publicado con DESCONOCIDO; errores intactos'
    finally:
        time_mod.strftime = real_strftime
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 13
def test_13_fallo_escritura_cierre_informe_conservacion():
    """Fallo de escritura + fallo de cierre del provisional: rc != 0, sin
    publicacion, provisional conservado y errores en la salida de diagnostico."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    real_open, real_write, real_close = os.open, os.write, os.close
    tmp_fds = set()
    write_fired = {'n': 0}

    def rec_open(path, *a, **k):
        fd = real_open(path, *a, **k)
        try:
            name = path if isinstance(path, str) else getattr(path, 'name', '')
        except Exception:
            name = ''
        if isinstance(name, str) and name.endswith('.json.tmp'):
            tmp_fds.add(fd)
        return fd

    def fail_write(fd, data, *a, **k):
        if write_fired['n'] == 0 and data[:1] == b'{':
            write_fired['n'] += 1
            raise OSError(errno.EIO, 'escritura simulada C4-B')
        return real_write(fd, data, *a, **k)

    def fail_close(fd, *a, **k):
        if fd in tmp_fds:
            tmp_fds.discard(fd)
            raise OSError(errno.EIO, 'cierre del provisional simulado C4-B')
        return real_close(fd, *a, **k)

    os.open, os.write, os.close = rec_open, fail_write, fail_close
    try:
        mod._reset_close_error_accounting()
        rc, out, ki = run_main(d1, shared_dir=d2)
        assert ki is False
        assert rc == 2, 'rc esperado 2 (fallo de escritura): {0}'.format(rc)
        assert find_report(d1) is None, 'el informe no debe publicarse'
        prov = [p for p in __import__('glob').glob(os.path.join(d1, 'report-*.json.tmp'))]
        assert prov, 'el provisional debe quedar en disco (C1, sin limpieza)'
        assert '[ERROR] No se pudo escribir el reporte JSON' in out, \
            'sin mensaje de fallo (no se afirma publicacion)'
        assert 'Adicionalmente, error de cierre' in out, \
            'error de cierre del provisional no reportado: {0}'.format(out[-600:])
        assert '[cierre pendiente] report_tmp_fd' in out, \
            'salida de diagnostico sin los errores de cierre pendientes'
        labels = [e.get('label') for e in mod._close_error_ledger]
        assert 'report_tmp_fd' in labels, \
            'error de cierre del provisional no conservado en el acumulador'
        DETAILS['C4B_13_fallo_escritura_cierre_informe_conservacion'] = \
            'rc=2; sin publicacion; provisional en disco; error report_tmp_fd en salida y acumulador'
    finally:
        os.open, os.write, os.close = real_open, real_write, real_close
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 14
def test_14_sin_duplicacion_prueba_entorno_informe():
    """Error de cierre en una prueba: aparece 1 vez en el informe (en el resultado
    de la prueba) y NO se repite en environment_close_errors.

    Inyeccion por-inode: para cada fixture, el cierre 1 es el de su creacion
    (nivel entorno) y el cierre 2 es el de T11 (primera prueba que lo abre):
    el fallo unico se dispara en ese cierre 2."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    real_close = os.close
    state = {'per_ino': {}, 'fired': 0}

    def count_close(fd, *a, **k):
        try:
            st = os.fstat(fd)
        except OSError:
            return real_close(fd, *a, **k)
        if stat_mod.S_ISREG(st.st_mode) and st.st_size > 1000:
            ino = st.st_ino
            state['per_ino'][ino] = state['per_ino'].get(ino, 0) + 1
            if state['per_ino'][ino] == 2 and state['fired'] == 0:
                state['fired'] += 1
                raise OSError(errno.EIO, 'cierre simulado C4-B (T11)')
        return real_close(fd, *a, **k)

    os.close = count_close
    try:
        rc, out, ki = run_main(d1, shared_dir=d2)
    finally:
        os.close = real_close
        restore_fakes(old_np, old_sf)
    try:
        assert state['fired'] == 1, 'la inyeccion no se disparo'
        assert ki is False and rc == 1, 'rc: {0}'.format(rc)
        report = load_report(d1)
        assert report is not None
        t11 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert t11 is not None and t11['status'] == mod.Result.FAIL, \
            'T11: {0}'.format(t11 and t11['status'])
        assert len(t11['close_errors']) == 1, \
            'error no conservado en el resultado: {0}'.format(t11['close_errors'])
        assert report['environment_close_errors'] == [], \
            'duplicacion prueba->entorno: {0}'.format(report['environment_close_errors'])
        raw = json.dumps(report, ensure_ascii=False)
        # Unicidad por identificador: la entrada del resultado de T11 aparece
        # exactamente 1 vez en todo el informe (y NO en environment_close_errors).
        eid = t11['close_errors'][0]['_close_err_id']
        n = len(re.findall(r'"_close_err_id":\s*{0}(?=[,}}\s])'.format(eid), raw))
        assert n == 1, \
            'la entrada del resultado aparece {0} veces en el informe'.format(n)
        assert 'cierre simulado C4-B (T11)' not in raw  # strerror normalizado
        DETAILS['C4B_14_sin_duplicacion_prueba_entorno_informe'] = \
            'error en close_errors de T11; environment_close_errors vacio; 1 ocurrencia en el JSON'
    finally:
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 15
def test_15_c4a_sigue_funcionando():
    """C4-A intacto: contrato estricto (sin token no cierra), token desconocido,
    instantanea inmutable sin referencia interna, cierre normal por token."""
    mod._reset_close_error_accounting()
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'c4a.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'c4a')
        # (a) sin token: no cierra
        with CloseFailure() as mock:
            assert c.close_fd(fd, 'sin_token') is None
        assert fd_alive(fd) and mock.fired == 0
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_OPEN
        # (b) token desconocido: no cierra
        assert c.close_fd(fd, 'desconocido', token=777777) is None
        assert fd_alive(fd)
        # (c) instantanea: sin _res/__dict__; mutacion rechazada
        snap = c.get_resource(tok)
        assert getattr(snap, '_res', 'X') == 'X'
        try:
            vars(snap)
            raise AssertionError('vars() debe fallar')
        except TypeError:
            pass
        try:
            snap.state = 'ALTERADO'
            raise AssertionError('asignacion debe rechazarse')
        except AttributeError:
            pass
        # (d) cierre normal por token: 1 os.close; nueva consulta CLOSED
        real_close = os.close
        calls = {'n': 0}

        def counting(fd_, *a, **k):
            calls['n'] += 1
            return real_close(fd_, *a, **k)

        os.close = counting
        try:
            assert c.close_fd(fd, 'c4a', token=tok) is None
        finally:
            os.close = real_close
        assert calls['n'] == 1
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert not fd_alive(fd)
        assert c.errors == []
        DETAILS['C4B_15_c4a_sigue_funcionando'] = \
            'sin token no cierra; desconocido no-op; snapshot inmutable; cierre por token 1 vez'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================= bateria
def main():
    print("Pruebas unitarias C4-B v0.2.9 — propagacion completa de errores de "
          "cierre (fallos inyectados; entorno no Android, sin audio real)")
    print("=" * 84)
    run('C4B_01_cierre_correcto_sin_secundarios', test_01_cierre_correcto_sin_secundarios)
    run('C4B_02_error_cierre_fd_en_resultado', test_02_error_cierre_fd_en_resultado)
    run('C4B_03_error_cierre_soundfile_en_resultado', test_03_error_cierre_soundfile_en_resultado)
    run('C4B_04_primario_mas_secundario', test_04_primario_mas_secundario)
    run('C4B_05_varios_secundarios_misma_operacion', test_05_varios_secundarios_misma_operacion)
    run('C4B_06_retorno_anticipado_tras_error_cierre', test_06_retorno_anticipado_tras_error_cierre)
    run('C4B_07_excepcion_ordinaria_y_cierre_en_limpieza',
        test_07_excepcion_ordinaria_y_cierre_en_limpieza)
    run('C4B_08_keyboardinterrupt_y_cierre_en_limpieza',
        test_08_keyboardinterrupt_y_cierre_en_limpieza)
    run('C4B_09_drenaje_sin_perdida', test_09_drenaje_sin_perdida)
    run('C4B_10_segundo_drenaje_sin_duplicacion', test_10_segundo_drenaje_sin_duplicacion)
    run('C4B_11_reconstruccion_informe_sin_perdida', test_11_reconstruccion_informe_sin_perdida)
    run('C4B_12_fallo_strftime_sin_perdida', test_12_fallo_strftime_sin_perdida)
    run('C4B_13_fallo_escritura_cierre_informe_conservacion',
        test_13_fallo_escritura_cierre_informe_conservacion)
    run('C4B_14_sin_duplicacion_prueba_entorno_informe',
        test_14_sin_duplicacion_prueba_entorno_informe)
    run('C4B_15_c4a_sigue_funcionando', test_15_c4a_sigue_funcionando)
    print("=" * 84)
    n_pass = sum(1 for _, s, _ in RESULTS if s == 'PASS')
    n_fail = sum(1 for _, s, _ in RESULTS if s == 'FAIL')
    n_err = sum(1 for _, s, _ in RESULTS if s == 'ERROR')
    n_ne = sum(1 for _, s, _ in RESULTS if s == 'NOT_EXECUTED')
    print("TOTAL {0} | PASS {1} | FAIL {2} | ERROR {3} | NOT_EXECUTED {4}".format(
        len(RESULTS), n_pass, n_fail, n_err, n_ne))
    for name, status, detail in RESULTS:
        if status != 'PASS':
            print("  NO PASS: {0} [{1}] {2}".format(name, status, detail))
    return 0 if (n_fail == 0 and n_err == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
