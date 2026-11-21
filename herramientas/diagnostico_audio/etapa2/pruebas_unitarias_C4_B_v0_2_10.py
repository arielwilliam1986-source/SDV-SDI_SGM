#!/usr/bin/env python3
"""Pruebas unitarias aisladas C4-B v0.2.10 — registro unico por evento de
cierre fallido e informe de errores ante interrupcion durante la
escritura/publicacion del informe.

Se importa el instrumento audioinput_diag_termux.py v0.2.10 y se verifican
los dos defectos residuales corregidos:

  C4-B-1: write_report_json_robust() registraba dos veces el mismo evento de
          cierre fallido (temporal via closer.close_fd + _record_close_error
          redundante; directorio padre via _close_fd_tracked +
          _record_close_error redundante). Ahora cada evento real queda
          registrado EXACTAMENTE una vez (por el propietario), con detalle
          conservado en el retorno e identificadores _close_err_id unicos.

  C4-B-2: el except KeyboardInterrupt de main() hacia sys.exit(130) ANTES del
          drenaje final: los errores de cierre producidos durante la
          escritura/publicacion interrumpida no llegaban a la salida de
          diagnostico. Ahora se drenan e informan ANTES del exit(130).

METODO: todos los fallos se INYECTAN con mocks/sustituciones aisladas
(os.close, os.write, os.link, registro de fds); ningun caso depende de fallos
espontaneos del sistema operativo. No Android/Termux, no audio real, no
muestras del proyecto, sin ejecucion de motores DSP.

CLASIFICACION: PASS / FAIL / ERROR / NOT_EXECUTED por caso (nunca PASS sin
ejecucion real). NOT_EXECUTED solo si la dependencia no esta disponible.
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
    return tempfile.mkdtemp(prefix='c4b10_ut_')


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
    np = type(sys)('numpy_sim_c4b10')
    np.__version__ = 'sim-0.0'
    rng = type(sys)('rng_sim_c4b10')
    rng.default_rng = lambda seed=None: _FakeRng()
    np.random = rng
    np.array_equal = lambda a, b: (a.data == b.data
                                   and tuple(a.shape) == tuple(b.shape))
    return np


def make_fake_sf(sf_close_raises=False, dir_raises=True):
    sf = type(sys)('soundfile_sim_c4b10')
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


def tmp_provisionals(d):
    return [p for p in os.listdir(d) if p.endswith('.json.tmp')]


# ---------------------------------------------------------------------------
# Inyeccion para write_report_json_robust aislado
# ---------------------------------------------------------------------------
class WriterInjection(object):
    """Llama write_report_json_robust real con fallos de cierre inyectados.

    - fail_tmp:    el cierre del descriptor temporal falla (OSError EIO).
    - fail_parent: el cierre del descriptor del directorio padre falla.
    Registra los disparos para confirmar que la inyeccion ocurrio.
    """

    def __init__(self, fail_tmp=False, fail_parent=False):
        self.fail_tmp = fail_tmp
        self.fail_parent = fail_parent
        self.box = {'parent_fd': None, 'tmp_fds': set(),
                    'fired_tmp': 0, 'fired_parent': 0}
        self._real_close = os.close
        self._real_soda = mod.safe_open_dir_anchored
        self._real_register = mod.CloseErrorLogger.register_fd
        self.result = None
        self.ledger = None

    def _soda(self, path):
        fd, msg = self._real_soda(path)
        self.box['parent_fd'] = fd
        return fd, msg

    def _register(self, fd, label):
        if label == 'report_tmp_fd':
            self.box['tmp_fds'].add(fd)
        return self._real_register(fd, label)

    def _mock_close(self, fd, *a, **k):
        if self.fail_tmp and fd in self.box['tmp_fds']:
            self.box['tmp_fds'].discard(fd)
            self.box['fired_tmp'] += 1
            raise OSError(errno.EIO, 'cierre del temporal simulado')
        if self.fail_parent and fd == self.box['parent_fd']:
            self.box['fired_parent'] += 1
            raise OSError(errno.EIO, 'cierre del directorio padre simulado')
        return self._real_close(fd, *a, **k)

    def __enter__(self):
        mod._reset_close_error_accounting()
        os.close = self._mock_close
        mod.safe_open_dir_anchored = self._soda
        # close_fd es invocado como metodo de instancia; parchear la clase
        # afectaria a otros tests: parchear solo el registro (bound original).
        self._patched_register()
        return self

    def _patched_register(self):
        real_register = self._real_register
        box = self.box

        def register_fd(self_logger, fd, label):
            if label == 'report_tmp_fd':
                box['tmp_fds'].add(fd)
            return real_register(self_logger, fd, label)

        mod.CloseErrorLogger.register_fd = register_fd

    def __exit__(self, *exc):
        os.close = self._real_close
        mod.safe_open_dir_anchored = self._real_soda
        mod.CloseErrorLogger.register_fd = self._real_register
        return False

    def call(self, parent_dir, name='report-diag.json'):
        rp = Path(parent_dir) / name
        self.result = mod.write_report_json_robust(
            rp, {'diagnostico': 'inyeccion', 'n': 1})
        self.ledger = list(mod._close_error_ledger)
        return self.result


def ledger_labels():
    return [e.get('label') for e in mod._close_error_ledger]


def ids_unique(entries):
    ids = [e.get('_close_err_id') for e in entries if isinstance(e, dict)]
    return len(ids) == len(set(ids)) and all(i is not None for i in ids)


# ================================================================ 1
def test_01_registro_unico_cierre_temporal():
    """C4-B-1.A: fallo de cierre del descriptor temporal -> EXACTAMENTE una
    entrada en el acumulador (el propietario close_fd la registra)."""
    d = fresh_tmp()
    try:
        with WriterInjection(fail_tmp=True) as inj:
            res = inj.call(d)
        assert inj.box['fired_tmp'] == 1, 'la inyeccion no disparo'
        assert inj.box['fired_parent'] == 0
        tmp_e = [e for e in inj.ledger if e.get('label') == 'report_tmp_fd']
        assert len(tmp_e) == 1, \
            'C4-B-1.A: el mismo evento quedo {0} veces en el acumulador'.format(
                len(tmp_e))
        assert len(inj.ledger) == 1, \
            'entradas inesperadas: {0}'.format(ledger_labels())
        assert tmp_e[0]['errno'] == errno.EIO
        assert ids_unique(inj.ledger), 'ids no unicos'
        assert 'report_tmp_fd' in (res[2] or ''), \
            'detalle del error perdido en el retorno: {0}'.format(res)
        DETAILS['C4B10_01_registro_unico_cierre_temporal'] = \
            '1 evento -> 1 entrada (id {0}); detalle en retorno conservado'.format(
                tmp_e[0]['_close_err_id'])
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 2
def test_02_registro_unico_cierre_padre():
    """C4-B-1.B: fallo de cierre del descriptor del directorio padre ->
    EXACTAMENTE una entrada en el acumulador (_close_fd_tracked la registra)."""
    d = fresh_tmp()
    try:
        with WriterInjection(fail_parent=True) as inj:
            res = inj.call(d)
        assert inj.box['fired_parent'] == 1, 'la inyeccion no disparo'
        assert inj.box['fired_tmp'] == 0
        par_e = [e for e in inj.ledger if e.get('label') == 'report_parent_fd']
        assert len(par_e) == 1, \
            'C4-B-1.B: el mismo evento quedo {0} veces en el acumulador'.format(
                len(par_e))
        assert len(inj.ledger) == 1, \
            'entradas inesperadas: {0}'.format(ledger_labels())
        assert par_e[0]['errno'] == errno.EIO
        assert ids_unique(inj.ledger), 'ids no unicos'
        assert 'parent_fd close errno' in (res[2] or ''), \
            'detalle del error perdido en el retorno: {0}'.format(res)
        DETAILS['C4B10_02_registro_unico_cierre_padre'] = \
            '1 evento -> 1 entrada (id {0}); detalle en retorno conservado'.format(
                par_e[0]['_close_err_id'])
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 3
def test_03_ambos_eventos_distintos_una_vez():
    """C4-B-1: fallo de AMBOS descriptores -> dos eventos distintos, cada uno
    exactamente una vez en el acumulador."""
    d = fresh_tmp()
    try:
        with WriterInjection(fail_tmp=True, fail_parent=True) as inj:
            res = inj.call(d)
        assert inj.box['fired_tmp'] == 1 and inj.box['fired_parent'] == 1, \
            'inyeccion incompleta: {0}'.format(inj.box)
        tmp_e = [e for e in inj.ledger if e.get('label') == 'report_tmp_fd']
        par_e = [e for e in inj.ledger if e.get('label') == 'report_parent_fd']
        assert len(tmp_e) == 1, 'temporal registrado {0} veces'.format(len(tmp_e))
        assert len(par_e) == 1, 'padre registrado {0} veces'.format(len(par_e))
        assert len(inj.ledger) == 2, \
            'C4-B-1: 2 eventos reales pero {0} entradas'.format(len(inj.ledger))
        assert tmp_e[0]['_close_err_id'] != par_e[0]['_close_err_id'], \
            'eventos distintos comparten id'
        assert ids_unique(inj.ledger), 'ids no unicos'
        assert 'report_tmp_fd' in (res[2] or '') and \
            'parent_fd close errno' in (res[2] or ''), \
            'detalle de algun evento perdido en el retorno: {0}'.format(res)
        DETAILS['C4B10_03_ambos_eventos_distintos_una_vez'] = \
            '2 eventos -> 2 entradas (ids {0} y {1}), cada una 1 vez'.format(
                tmp_e[0]['_close_err_id'], par_e[0]['_close_err_id'])
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ================================================================ 4
def test_04_ids_unicos_sin_duplicacion_de_ocurrencia():
    """C4-B-1: los identificadores _close_err_id son unicos y ninguna
    ocurrencia del mismo evento se duplica (escenarios limpio/temporal/padre/
    ambos + validacion global del acumulador)."""
    escenarios = ((False, False), (True, False), (False, True), (True, True))
    esperado = (0, 1, 1, 2)
    for i, ((ft, fp), n_esp) in enumerate(zip(escenarios, esperado)):
        d = fresh_tmp()
        try:
            with WriterInjection(fail_tmp=ft, fail_parent=fp) as inj:
                inj.call(d)
            assert len(inj.ledger) == n_esp, \
                'escenario {0}: {1} entradas, esperado {2}'.format(
                    i, len(inj.ledger), n_esp)
            assert ids_unique(inj.ledger), \
                'escenario {0}: ids no unicos o ausentes'.format(i)
            # ninguna ocurrencia identica repetida (mismo label+errno+strerror)
            claves = [(e.get('label'), e.get('errno'), e.get('strerror'))
                      for e in inj.ledger]
            assert len(claves) == len(set(claves)), \
                'escenario {0}: ocurrencia duplicada: {1}'.format(i, claves)
            for e in inj.ledger:
                assert '_close_err_id' in e, 'entrada sin id: {0}'.format(e)
        finally:
            shutil.rmtree(d, ignore_errors=True)
    DETAILS['C4B10_04_ids_unicos_sin_duplicacion_de_ocurrencia'] = \
        'limpio=0, temporal=1, padre=1, ambos=2 entradas; ids unicos; 0 ocurrencias repetidas'


# ================================================================ 5
def test_05_retorno_conserva_errores_correspondientes():
    """C4-B-1: el resultado de escritura conserva los errores de cierre
    correspondientes a cada evento (detalle completo, sin perder ninguno)."""
    d = fresh_tmp()
    try:
        with WriterInjection(fail_tmp=True, fail_parent=True) as inj:
            ok, err, cerr = inj.call(d)
        assert err is None, 'la escritura primaria no debio fallar: {0}'.format(err)
        assert cerr is not None and cerr != '', 'close_err vacio'
        assert 'report_tmp_fd' in cerr, 'falta el evento del temporal: {0}'.format(cerr)
        assert 'parent_fd close errno' in cerr, 'falta el evento del padre: {0}'.format(cerr)
        # y el acumulador tambien conserva ambos
        labels = ledger_labels()
        assert labels.count('report_tmp_fd') == 1 and \
            labels.count('report_parent_fd') == 1, \
            'acumulador inconsistente con el retorno: {0}'.format(labels)
        DETAILS['C4B10_05_retorno_conserva_errores_correspondientes'] = \
            'close_err = "{0}" (ambos eventos, escritura primaria intacta)'.format(cerr)
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# Inyeccion para el flujo main() completo (C4-B-2)
# ---------------------------------------------------------------------------
class FlowKIInjection(object):
    """Inyecta KeyboardInterrupt y/o fallos de cierre durante la escritura/
    publicacion del informe, dentro del flujo main() real.

    - ki_write: KI en la primera escritura del contenido JSON.
    - ki_link:  KI en os.link de publicacion (src termina en .json.tmp).
    - fail_tmp:    el cierre del temporal falla (OSError EIO).
    - fail_parent: el PRIMER cierre de un descriptor de directorio posterior
      a la apertura del temporal falla (es el cierre del padre del informe:
      dentro de write_report_json_robust no se abre ningun otro directorio).
    """

    def __init__(self, ki_write=False, ki_link=False,
                 fail_tmp=False, fail_parent=False):
        self.ki_write = ki_write
        self.ki_link = ki_link
        self.fail_tmp = fail_tmp
        self.fail_parent = fail_parent
        self.box = {'tmp_fds': set(), 'parent_phase': False,
                    'fired_ki_write': 0, 'fired_ki_link': 0,
                    'fired_tmp': 0, 'fired_parent': 0}
        self._real_open, self._real_write = os.open, os.write
        self._real_close, self._real_link = os.close, os.link

    def _rec_open(self, path, *a, **k):
        fd = self._real_open(path, *a, **k)
        try:
            name = path if isinstance(path, str) else getattr(path, 'name', '')
        except Exception:
            name = ''
        if isinstance(name, str) and name.endswith('.json.tmp'):
            self.box['tmp_fds'].add(fd)
            self.box['parent_phase'] = True
        return fd

    def _ki_write(self, fd, data, *a, **k):
        if self.ki_write and self.box['fired_ki_write'] == 0 \
                and data[:1] == b'{':
            self.box['fired_ki_write'] += 1
            raise KeyboardInterrupt()
        return self._real_write(fd, data, *a, **k)

    def _ki_link(self, *a, **k):
        if self.ki_link and self.box['fired_ki_link'] == 0 \
                and a and isinstance(a[0], str) and a[0].endswith('.json.tmp'):
            self.box['fired_ki_link'] += 1
            raise KeyboardInterrupt()
        return self._real_link(*a, **k)

    def _mock_close(self, fd, *a, **k):
        if self.fail_tmp and fd in self.box['tmp_fds']:
            self.box['tmp_fds'].discard(fd)
            self.box['fired_tmp'] += 1
            raise OSError(errno.EIO, 'cierre del temporal simulado')
        if self.fail_parent and self.box['parent_phase'] \
                and self.box['fired_parent'] == 0:
            try:
                st = os.fstat(fd)
            except OSError:
                st = None
            if st is not None and stat_mod.S_ISDIR(st.st_mode):
                self.box['fired_parent'] += 1
                raise OSError(errno.EIO,
                              'cierre del directorio padre simulado')
        return self._real_close(fd, *a, **k)

    def __enter__(self):
        mod._reset_close_error_accounting()
        os.open, os.write = self._rec_open, self._ki_write
        os.close, os.link = self._mock_close, self._ki_link
        return self

    def __exit__(self, *exc):
        os.open, os.write = self._real_open, self._real_write
        os.close, os.link = self._real_close, self._real_link
        return False


# ================================================================ 6
def test_06_ki_escritura_sin_fallos_de_cierre():
    """C4-B-2: KI durante la escritura del informe (sin fallos de cierre):
    rc=130, no se publica, provisional conservado, sin errores pendientes."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with FlowKIInjection(ki_write=True) as inj:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert inj.box['fired_ki_write'] == 1, 'la KI no se disparo'
        assert ki is False, 'la KI debe absorberse en main (C5 congelado)'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert '[INTERRUMPIDO] KeyboardInterrupt durante la publicacion' in out, \
            'sin mensaje de interrupcion durante la publicacion'
        assert find_report(d1) is None, 'el informe no debe publicarse'
        provs = tmp_provisionals(d1)
        assert provs, 'el provisional debe quedar en disco (C1, sin limpieza)'
        assert len(mod._close_error_ledger) == 0, \
            'sin fallos de cierre no debe haber errores: {0}'.format(
                ledger_labels())
        assert out.count('[cierre pendiente]') == 0, \
            'no debe anunciar errores de cierre inexistentes'
        DETAILS['C4B10_06_ki_escritura_sin_fallos_de_cierre'] = \
            'rc=130; sin publicacion; provisional {0} conservado; 0 errores de cierre'.format(
                provs[0][:30] + '...')
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 7
def test_07_ki_escritura_mas_cierre_temporal():
    """C4-B-2: KI durante la escritura + fallo de cierre del temporal: el
    error llega a la salida de diagnostico ANTES del exit(130), una vez."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with FlowKIInjection(ki_write=True, fail_tmp=True) as inj:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert inj.box['fired_ki_write'] == 1 and inj.box['fired_tmp'] == 1, \
            'inyeccion incompleta: {0}'.format(inj.box)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert out.count('[cierre pendiente]') == 1, \
            'el error de cierre debe aparecer exactamente 1 vez: {0}'.format(
                out.count('[cierre pendiente]'))
        assert '[cierre pendiente] report_tmp_fd' in out, \
            'salida sin el error del temporal'
        tmp_e = [e for e in mod._close_error_ledger
                 if e.get('label') == 'report_tmp_fd']
        assert len(tmp_e) == 1, \
            'registro unico tambien bajo KI: {0} entradas'.format(len(tmp_e))
        assert ids_unique(mod._close_error_ledger), 'ids no unicos'
        assert find_report(d1) is None, 'no se debe publicar'
        assert tmp_provisionals(d1), 'provisional conservado'
        DETAILS['C4B10_07_ki_escritura_mas_cierre_temporal'] = \
            'rc=130; "[cierre pendiente] report_tmp_fd" 1 vez; 1 entrada; provisional conservado'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 8
def test_08_ki_publicacion_mas_cierre_padre():
    """C4-B-2: KI durante la publicacion (os.link) + fallo de cierre del
    descriptor del directorio padre: el error llega a la salida antes del
    exit(130); sin publicacion; provisional conservado."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with FlowKIInjection(ki_link=True, fail_parent=True) as inj:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert inj.box['fired_ki_link'] == 1, \
            'la KI de os.link no se disparo (ruta no alcanzada)'
        assert inj.box['fired_parent'] == 1, \
            'el fallo del cierre del padre no se disparo'
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert out.count('[cierre pendiente]') == 1, \
            'el error del padre debe aparecer exactamente 1 vez'
        assert '[cierre pendiente] report_parent_fd' in out, \
            'salida sin el error del directorio padre'
        par_e = [e for e in mod._close_error_ledger
                 if e.get('label') == 'report_parent_fd']
        assert len(par_e) == 1, \
            'registro unico tambien bajo KI: {0} entradas'.format(len(par_e))
        assert find_report(d1) is None, 'no se debe publicar (KI en el link)'
        assert tmp_provisionals(d1), \
            'el provisional debe quedar en disco (unlink solo tras link exitoso)'
        DETAILS['C4B10_08_ki_publicacion_mas_cierre_padre'] = \
            'ruta alcanzada; rc=130; "[cierre pendiente] report_parent_fd" 1 vez; provisional conservado'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 9
def test_09_error_cierre_una_sola_vez_en_salida():
    """C4-B-2: con dos eventos de cierre durante la interrupcion (temporal y
    padre), cada uno aparece EXACTAMENTE una vez en la salida de diagnostico."""
    d1, d2 = fresh_tmp(), fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        with FlowKIInjection(ki_write=True, fail_tmp=True,
                             fail_parent=True) as inj:
            rc, out, ki = run_main(d1, shared_dir=d2)
        assert inj.box['fired_ki_write'] == 1 and inj.box['fired_tmp'] == 1 \
            and inj.box['fired_parent'] == 1, \
            'inyeccion incompleta: {0}'.format(inj.box)
        assert rc == 130, 'rc esperado 130: {0}'.format(rc)
        assert out.count('[cierre pendiente]') == 2, \
            '2 eventos -> 2 lineas en salida: {0}'.format(
                out.count('[cierre pendiente]'))
        assert out.count('[cierre pendiente] report_tmp_fd') == 1, \
            'el evento del temporal aparece mas de una vez'
        assert out.count('[cierre pendiente] report_parent_fd') == 1, \
            'el evento del padre aparece mas de una vez'
        labels = ledger_labels()
        assert labels.count('report_tmp_fd') == 1 and \
            labels.count('report_parent_fd') == 1, \
            'acumulador con duplicados: {0}'.format(labels)
        assert ids_unique(mod._close_error_ledger), 'ids no unicos'
        DETAILS['C4B10_09_error_cierre_una_sola_vez_en_salida'] = \
            'rc=130; temporal 1 vez + padre 1 vez en salida; acumulador sin duplicados'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ================================================================ 10
def test_10_rc130_sin_publicacion_provisional_conservado():
    """C4-B-2: en todos los escenarios con KI, el codigo de salida sigue
    siendo 130, el informe no se publica y el provisional no se borra."""
    escenarios = (
        {'ki_write': True},
        {'ki_write': True, 'fail_tmp': True},
        {'ki_link': True, 'fail_parent': True},
        {'ki_write': True, 'fail_tmp': True, 'fail_parent': True},
    )
    for i, kwargs in enumerate(escenarios):
        d1, d2 = fresh_tmp(), fresh_tmp()
        old_np, old_sf = inject_fakes()
        try:
            with FlowKIInjection(**kwargs) as inj:
                rc, out, ki = run_main(d1, shared_dir=d2)
            assert inj.box['fired_ki_write'] + inj.box['fired_ki_link'] >= 1, \
                'escenario {0}: la KI no se disparo'.format(i)
            assert rc == 130, \
                'escenario {0}: rc {1} != 130'.format(i, rc)
            assert find_report(d1) is None, \
                'escenario {0}: el informe no debe publicarse'.format(i)
            assert tmp_provisionals(d1), \
                'escenario {0}: provisional eliminado (C1 violado)'.format(i)
            assert '[INTERRUMPIDO] KeyboardInterrupt durante la publicacion' in out, \
                'escenario {0}: sin mensaje explicito de no publicacion'.format(i)
        finally:
            restore_fakes(old_np, old_sf)
            shutil.rmtree(d1, ignore_errors=True)
            shutil.rmtree(d2, ignore_errors=True)
    DETAILS['C4B10_10_rc130_sin_publicacion_provisional_conservado'] = \
        '4 escenarios KI: rc=130, sin publicacion, provisional conservado, mensaje explicito'


# ================================================================
def main():
    print('Pruebas unitarias C4-B v0.2.10 — registro unico por evento de cierre '
          'e informe de errores ante interrupcion (fallos inyectados; entorno no '
          'Android, sin audio real)')
    print('=' * 84)
    casos = [
        ('C4B10_01_registro_unico_cierre_temporal', test_01_registro_unico_cierre_temporal),
        ('C4B10_02_registro_unico_cierre_padre', test_02_registro_unico_cierre_padre),
        ('C4B10_03_ambos_eventos_distintos_una_vez', test_03_ambos_eventos_distintos_una_vez),
        ('C4B10_04_ids_unicos_sin_duplicacion_de_ocurrencia', test_04_ids_unicos_sin_duplicacion_de_ocurrencia),
        ('C4B10_05_retorno_conserva_errores_correspondientes', test_05_retorno_conserva_errores_correspondientes),
        ('C4B10_06_ki_escritura_sin_fallos_de_cierre', test_06_ki_escritura_sin_fallos_de_cierre),
        ('C4B10_07_ki_escritura_mas_cierre_temporal', test_07_ki_escritura_mas_cierre_temporal),
        ('C4B10_08_ki_publicacion_mas_cierre_padre', test_08_ki_publicacion_mas_cierre_padre),
        ('C4B10_09_error_cierre_una_sola_vez_en_salida', test_09_error_cierre_una_sola_vez_en_salida),
        ('C4B10_10_rc130_sin_publicacion_provisional_conservado', test_10_rc130_sin_publicacion_provisional_conservado),
    ]
    for nombre, fn in casos:
        run(nombre, fn)
    print('=' * 84)
    total = len(RESULTS)
    npass = sum(1 for _, s, _ in RESULTS if s == 'PASS')
    nfail = sum(1 for _, s, _ in RESULTS if s == 'FAIL')
    nerr = sum(1 for _, s, _ in RESULTS if s == 'ERROR')
    nel = sum(1 for _, s, _ in RESULTS if s == 'NOT_EXECUTED')
    print('TOTAL {0} | PASS {1} | FAIL {2} | ERROR {3} | NOT_EXECUTED {4}'.format(
        total, npass, nfail, nerr, nel))
    for name, status, detail in RESULTS:
        if status != 'PASS':
            print('  NO PASS: {0} [{1}] {2}'.format(name, status, detail))
    if nfail or nerr:
        sys.exit(1)


if __name__ == '__main__':
    main()
