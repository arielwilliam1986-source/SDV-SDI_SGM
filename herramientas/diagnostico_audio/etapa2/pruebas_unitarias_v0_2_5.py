#!/usr/bin/env python3
"""Pruebas unitarias aisladas para la corrección v0.2.5 (C4/C5).

Se importa el instrumento audioinput_diag_termux.py v0.2.5 y se ejercita:

  C4 (v0.2.5) — registro, propiedad y cierre correcto de descriptores:
    - patrón token de apertura (registrar -> cerrar asociado al token);
    - T11–T16 sin fuga de descriptores (verificación por /proc/self/fd);
    - safe_create_file_exclusive_anchored con token y contrato intacto;
    - ausencia del patrón de cierre sin registro (chequeo estático).

  C5 (v0.2.5) — propagación de interrupciones y prueba del FLUJO REAL de
  main(): se ejecuta main() completo (argparse, directorios anclados,
  metadatos, run_environment, fixtures, T11–T16, informe, códigos de
  salida) con numpy/soundfile SIMULADOS inyectados en sys.modules.

HONESTIDAD DE LOS RESULTADOS (sin PASS inventados):
  - La capa numpy/soundfile es una SIMULACIÓN: no se instala ni ejecuta
    libsndfile, no se decodifica audio real, no se ejecuta Android/Termux.
    Los resultados PASS de T11–T16 en el flujo real verifican la LÓGICA de
    flujo, propagación, registro y cierre — NO la compatibilidad con
    libsndfile real ni con Android/Termux (eso queda NOT_EXECUTED).
  - Si /proc/self/fd no está disponible, las pruebas de fuga se registran
    NOT_EXECUTED.
"""
import glob
import io
import importlib.util
import json
import os
import shutil
import stat as stat_mod
import struct
import sys
import tempfile
import time
import traceback
from contextlib import redirect_stdout

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'audioinput_diag_termux.py')

_spec = importlib.util.spec_from_file_location('audioinput_diag_termux', TARGET)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

RESULTS = []


def record(name, status, detail):
    RESULTS.append((name, status, detail))
    print("{0:4} {1:58} {2}".format(status, name, detail))


def run(name, fn):
    try:
        fn()
        record(name, 'PASS', 'OK')
    except (ImportError, ModuleNotFoundError) as exc:
        record(name, 'NOT_EXECUTED', 'dependencia/condicion no disponible: {0}'.format(exc))
    except AssertionError as exc:
        record(name, 'FAIL', str(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


def fresh_tmp():
    return tempfile.mkdtemp(prefix='v025_ut_')


def count_open_fds():
    """Numero de descriptores abiertos del proceso (Linux). None si no hay /proc."""
    try:
        return len(os.listdir('/proc/self/fd'))
    except OSError:
        return None


# ============================================================================
# Capa simulada de numpy/soundfile (sin libsndfile, sin audio real)
# ============================================================================

class FakeArray(object):
    __slots__ = ('data', 'shape')

    def __init__(self, data, shape):
        self.data = data
        self.shape = shape

    def __setitem__(self, key, value):
        i, j = key
        self.data[i][j] = value


class _FakeRng(object):
    def __init__(self, seed=None):
        self.seed = seed

    def uniform(self, low, high, size):
        rows = [[low] * size[1] for _ in range(size[0])]
        return FakeArray(rows, (size[0], size[1]))


class _FakeRandom(object):
    def default_rng(self, seed=None):
        return _FakeRng(seed)


def make_fake_np():
    """Modulo numpy simulado: random.default_rng + array_equal (minimo usado)."""
    types = type(sys)('numpy_sim')
    types.__version__ = 'sim-0.0'
    types.random = _FakeRandom()

    def array_equal(a, b):
        return (a.data == b.data) and (tuple(a.shape) == tuple(b.shape))

    types.array_equal = array_equal
    return types


def make_fake_sf(ki_at_construction=None):
    """Modulo soundfile simulado.

    - SoundFile(fd, mode='w'|'r', closefd=False): escribe/lee bytes
      deterministas (float32 empaquetado) sobre el descriptor REAL.
    - close() NO cierra el descriptor (contrato closefd=False).
    - Un fd de directorio dispara LibsndfileError (como libsndfile real).
    - ki_at_construction: numero de apertura (1-based) en la que se inyecta
      KeyboardInterrupt, para simular interrupciones en puntos controlados
      del flujo real sin alterar el codigo del instrumento.
    """
    types = type(sys)('soundfile_sim')
    types.__version__ = 'sim-0.0'
    types.__libsndfile_version__ = 'sim-libsndfile-0.0'

    class LibsndfileError(Exception):
        pass

    types.LibsndfileError = LibsndfileError

    counter = {'n': 0}

    class SoundFile(object):
        def __init__(self, file, mode='r', samplerate=None, channels=None,
                     format=None, subtype=None, closefd=False):
            counter['n'] += 1
            if ki_at_construction is not None and counter['n'] == ki_at_construction:
                raise KeyboardInterrupt()
            self._fd = file
            self._mode = mode
            self.closed = False
            self._pos = 0
            st = os.fstat(file)
            if stat_mod.S_ISDIR(st.st_mode):
                raise LibsndfileError('sim: fd de directorio no soportado')
            if mode == 'w':
                self.samplerate = samplerate
                self.channels = channels
                self.frames = 0
            else:
                self.channels = 2
                self.samplerate = 44100
                self.frames = st.st_size // (2 * 4)

        def write(self, arr):
            if self.closed:
                raise LibsndfileError('sim: SoundFile cerrado')
            buf = bytearray()
            for row in arr.data:
                for v in row:
                    buf += struct.pack('<f', float(v))
            os.write(self._fd, bytes(buf))
            self.frames += len(arr.data)

        def read(self, frames, dtype='float64', always_2d=False):
            if self.closed:
                raise LibsndfileError('sim: SoundFile cerrado')
            nbytes = frames * self.channels * 4
            data = os.pread(self._fd, nbytes, self._pos)
            self._pos += len(data)
            n = len(data) // (self.channels * 4)
            rows = []
            for i in range(n):
                rows.append(list(struct.unpack_from(
                    '<{0}f'.format(self.channels), data, i * self.channels * 4)))
            return FakeArray(rows, (n, self.channels))

        def seek(self, offset, whence=0):
            self._pos = offset
            return self._pos

        def close(self):
            # closefd=False: el descriptor NO se cierra aqui (contrato).
            self.closed = True

    types.SoundFile = SoundFile

    def available_subtypes(fmt):
        if fmt == 'WAV':
            return {'PCM_16': 'x', 'PCM_24': 'x', 'PCM_32': 'x', 'FLOAT': 'x'}
        return {}

    types.available_subtypes = available_subtypes
    return types


def inject_fakes(ki_at_construction=None):
    """Inyecta numpy/soundfile simulados en sys.modules; retorna respaldo."""
    old_np = sys.modules.get('numpy')
    old_sf = sys.modules.get('soundfile')
    sys.modules['numpy'] = make_fake_np()
    sys.modules['soundfile'] = make_fake_sf(ki_at_construction)
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


# ============================================================================
# Ejecucion del flujo REAL de main()
# ============================================================================

def run_main(private_dir, shared_dir=None):
    """Ejecuta mod.main() con el flujo real; retorna (rc, ki_propagada, stdout)."""
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
    return rc, ki, buf.getvalue()


def find_published_report(private_dir):
    hits = [p for p in glob.glob(os.path.join(private_dir, 'report-*.json'))
            if not p.endswith('.tmp')]
    return hits[0] if len(hits) == 1 else (hits or [None])[0] if hits else None


def find_provisional(private_dir):
    hits = glob.glob(os.path.join(private_dir, 'report-*.json.tmp'))
    return hits[0] if hits else None


def load_report(private_dir):
    p = find_published_report(private_dir)
    if p is None:
        return None
    with open(p) as fh:
        return json.load(fh)


def get_result(report, env, test, fixture):
    for r in report['results']:
        if r['env'] == env and r['test'] == test and r['fixture'] == fixture:
            return r
    return None


def count_results(report, env):
    return sum(1 for r in report['results'] if r['env'] == env)


# ============================================================================
# C4 (v0.2.5)
# ============================================================================

def test_c4_v05_patron_token_cierre_y_obsoleto():
    """Registrar -> cerrar con token cierra; token obsoleto no cierra nada."""
    d = fresh_tmp()
    try:
        p = os.path.join(d, 'x.bin')
        fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b'abc')
        finally:
            pass
        closer = mod.CloseErrorLogger()
        tok = closer.register_fd(fd, 'x')
        assert tok is not None, 'register_fd no retorno token'
        err = closer.close_fd(fd, 'x', token=tok)
        assert err is None, 'cierre con token fallo: {0}'.format(err)
        try:
            os.fstat(fd)
            raise AssertionError('el fd sigue abierto tras cierre con token')
        except OSError:
            pass
        entry = closer._entries[tok]
        assert entry['state'] == 'closed' and entry['close_result'] == 'ok', \
            'estado del registro incorrecto: {0}'.format(entry)

        # Token obsoleto/desconocido: no cierra el recurso ajeno
        fd2 = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            err2 = closer.close_fd(fd2, 'y', token=tok)
            assert err2 is None, 'token obsoleto no debe lanzar'
            # tok esta registrado pero ya cerrado -> aviso "ya cerrada
            # (token obsoleto)"; el fd ajeno no debe tocarse.
            assert any('obsoleto' in w.get('strerror', '') for w in closer.warnings), \
                'no se registro aviso de token obsoleto: {0}'.format(closer.warnings)
            try:
                os.fstat(fd2)
                alive = True
            except OSError:
                alive = False
            assert alive, 'el token obsoleto cerro el descriptor ajeno (fuga de propiedad)'
        finally:
            os.close(fd2)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c4_v05_T11_T14_sin_fuga_descriptores():
    """T11–T14 sobre fixture real: PASS, sin close_errors y sin fuga de fd."""
    d = fresh_tmp()
    try:
        if count_open_fds() is None:
            raise ImportError('/proc/self/fd no disponible')
        fake_np = make_fake_np()
        fake_sf = make_fake_sf()
        run_dir = os.path.join(d, 'run')
        os.mkdir(run_dir, 0o700)
        closer_fx = mod.CloseErrorLogger()
        fpath, ferr = mod.create_fixture(fake_np, fake_sf, run_dir, 'pcm16',
                                         'PCM_16', closer_fx)
        assert ferr is None, 'create_fixture fallo: {0}'.format(ferr)
        assert fpath is not None and os.path.exists(fpath), 'fixture no creado'
        assert closer_fx.errors == [], 'errores de cierre en creacion: {0}'.format(
            closer_fx.errors)
        assert os.path.getsize(fpath) >= 200, 'fixture demasiado pequeno'

        for name, fn in [('T11', mod.test_t11_soundfile_fd_closefd_false),
                         ('T12', mod.test_t12_pread_works),
                         ('T13', mod.test_t13_pread_hash_matches_canonical),
                         ('T14', mod.test_t14_pread_coexists_with_soundfile)]:
            before = count_open_fds()
            ret = fn(fake_np, fake_sf, fpath)
            after = count_open_fds()
            assert len(ret) == 3, '{0}: contrato de retorno (status, detail, close_errors)'.format(name)
            status, detail, close_errors = ret
            assert status == mod.Result.PASS, \
                '{0}: status={1} detail={2}'.format(name, status, str(detail)[:160])
            assert close_errors == [], \
                '{0}: close_errors={1}'.format(name, close_errors)
            assert after == before, \
                '{0}: FUGA de descriptores: antes={1} despues={2}'.format(
                    name, before, after)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c4_v05_T15_T16_sin_fuga_descriptores():
    """T15–T16 con fd de directorio: PASS y sin fuga de descriptores."""
    d = fresh_tmp()
    try:
        if count_open_fds() is None:
            raise ImportError('/proc/self/fd no disponible')
        fake_np = make_fake_np()
        fake_sf = make_fake_sf()
        for name, fn in [('T15', mod.test_t15_libsndfile_error_raised),
                         ('T16', mod.test_t16_fd_survives_closefd_false_failure)]:
            before = count_open_fds()
            ret = fn(fake_np, fake_sf, d)
            after = count_open_fds()
            status, detail, close_errors = ret
            assert status == mod.Result.PASS, \
                '{0}: status={1} detail={2}'.format(name, status, str(detail)[:160])
            assert close_errors == [], \
                '{0}: close_errors={1}'.format(name, close_errors)
            assert after == before, \
                '{0}: FUGA de descriptores: antes={1} despues={2}'.format(
                    name, before, after)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c4_v05_safe_create_file_token_contrato():
    """safe_create_file_exclusive_anchored: token interno, contrato (ok,err,cerr) intacto."""
    d = fresh_tmp()
    try:
        if count_open_fds() is None:
            raise ImportError('/proc/self/fd no disponible')
        p = os.path.join(d, 'f.bin')
        before = count_open_fds()
        ok, err, cerr = mod.safe_create_file_exclusive_anchored(p, b'HOLA-MUNDO')
        after = count_open_fds()
        assert ok is True and err is None and cerr is None, \
            'primera creacion: ok={0} err={1} cerr={2}'.format(ok, err, cerr)
        with open(p, 'rb') as fh:
            assert fh.read() == b'HOLA-MUNDO', 'contenido incorrecto'
        assert after == before, 'fuga de descriptores en creacion exitosa'

        # EEXIST: sin sobrescritura, contrato conservado
        ok2, err2, cerr2 = mod.safe_create_file_exclusive_anchored(p, b'OTRO')
        assert ok2 is False and 'ya existe' in (err2 or ''), \
            'EEXIST no detectado: ok={0} err={1}'.format(ok2, err2)
        with open(p, 'rb') as fh:
            assert fh.read() == b'HOLA-MUNDO', 'el archivo fue sobrescrito'
        assert count_open_fds() == before, 'fuga de descriptores en EEXIST'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c4_v05_sin_patron_cierre_sin_token():
    """Estatico: en el script no queda el patron de cierre sin registro."""
    with open(TARGET, encoding='utf-8') as fh:
        src = fh.read()
    leaky = ["closer.close_fd(fd, 'fd')\n",
             "closer.close_fd(fd, 'fd_finally')\n",
             "closer.close_fd(dir_fd, 'dir_fd')\n",
             "closer.close_fd(dir_fd, 'dir_fd_finally')\n"]
    for pat in leaky:
        assert pat not in src, 'patron de cierre sin token presente: {0!r}'.format(pat)
    # Todas las aperturas de pruebas/helpers registran propiedad (token)
    n_register = src.count('register_fd(')
    assert n_register >= 8, \
        'register_fd presente {0} veces (se esperaban >= 8)'.format(n_register)


# ============================================================================
# C5 (v0.2.5) — flujo real de main()
# ============================================================================

def test_c5_v05_flujo_real_main_completo():
    """main() completo sin interrupcion: rc=0, informe publicado, 36 PASS."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    old_np, old_sf = inject_fakes()
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'KeyboardInterrupt propagada sin causa'
        assert rc == 0, 'rc esperado 0, obtenido {0}; stdout:\n{1}'.format(rc, out[-800:])
        assert 'v0.2.5' in out, 'el banner no anuncia v0.2.5'
        report = load_report(d1)
        assert report is not None, 'informe JSON no publicado'
        assert report['interrupted'] is False, 'interrupted debe ser False'
        assert report['metadata']['script_version'] == '0.2.5', 'version en metadatos'
        assert len(report['results']) == 36, \
            'resultados={0} esperados 36'.format(len(report['results']))
        assert report['summary']['pass'] == 36, 'summary.pass={0}'.format(
            report['summary']['pass'])
        assert report['summary']['interrupted'] is False, 'summary.interrupted'
        assert report['environment_close_errors'] == [], 'close_errors de entorno'
        for r in report['results']:
            assert r['status'] == mod.Result.PASS, \
                '{0}/{1}/{2}: {3} — {4}'.format(r['env'], r['test'], r['fixture'],
                                                r['status'], str(r['detail'])[:120])
            assert r['close_errors'] == [], 'close_errors en {0}'.format(r['test'])
        assert report['private_run_dir'] and os.path.isdir(report['private_run_dir'])
        assert report['shared_run_dir'] and os.path.isdir(report['shared_run_dir'])
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


def test_c5_v05_flujo_real_main_ki_prueba():
    """KI dentro de T11/pcm16 (flujo real): ERROR + cascada NOT_EXECUTED + rc 130."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    # Aperturas: 4 fixtures (escritura) + T11/pcm16 (lectura) = constructor 5
    old_np, old_sf = inject_fakes(ki_at_construction=5)
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI debe absorberse dentro de main (rc 130)'
        assert rc == 130, 'rc esperado 130, obtenido {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'informe no publicado tras interrupcion'
        assert report['interrupted'] is True, 'interrupted debe ser True'
        assert report['summary']['interrupted'] is True, 'summary.interrupted'
        r = get_result(report, 'A_private', 'T11', 'pcm16')
        assert r and r['status'] == mod.Result.ERROR, \
            'T11/pcm16 debe ser ERROR: {0}'.format(r and r['status'])
        assert 'KeyboardInterrupt' in r['detail'], 'detalle sin marca de KI'
        for tid in ['T12', 'T13', 'T14']:
            r2 = get_result(report, 'A_private', tid, 'pcm16')
            assert r2 and r2['status'] == mod.Result.NOT_EXECUTED, \
                '{0}/pcm16 debe ser NOT_EXECUTED'.format(tid)
        for fx in ['pcm24', 'pcm32', 'float32']:
            r3 = get_result(report, 'A_private', 'T11', fx)
            assert r3 and r3['status'] == mod.Result.NOT_EXECUTED, \
                'T11/{0} debe ser NOT_EXECUTED (interrupcion previa)'.format(fx)
        r4 = get_result(report, 'A_private', 'T15', None)
        assert r4 and r4['status'] == mod.Result.NOT_EXECUTED, 'T15 debe ser NOT_EXECUTED'
        r5 = get_result(report, 'B_shared', 'T11', 'pcm16')
        assert r5 and r5['status'] == mod.Result.NOT_EXECUTED, \
            'el segundo entorno no debe ejecutarse tras la interrupcion'
        assert count_results(report, 'A_private') == 18, 'entradas de entorno A'
        assert count_results(report, 'B_shared') == 18, 'entradas de entorno B'
        assert report['summary']['error'] == 1 and report['summary']['pass'] == 0, \
            'summary inconsistente: {0}'.format(report['summary'])
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


def test_c5_v05_flujo_real_main_ki_create_fixture():
    """KI durante create_fixture (flujo real): ERROR + cascada NOT_EXECUTED + rc 130."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    # Aperturas: pcm16 (1) y pcm24 (2): la KI cae creando pcm24
    old_np, old_sf = inject_fakes(ki_at_construction=2)
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI debe absorberse dentro de main (rc 130)'
        assert rc == 130, 'rc esperado 130, obtenido {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'informe no publicado tras interrupcion'
        assert report['interrupted'] is True, 'interrupted debe ser True'
        r = get_result(report, 'A_private', 'T11', 'pcm24')
        assert r and r['status'] == mod.Result.ERROR, \
            'T11/pcm24 debe ser ERROR (KI creando fixture): {0}'.format(
                r and r['status'])
        r2 = get_result(report, 'A_private', 'T12', 'pcm24')
        assert r2 and r2['status'] == mod.Result.NOT_EXECUTED, \
            'T12/pcm24 debe ser NOT_EXECUTED (fixture interrumpido)'
        r3 = get_result(report, 'A_private', 'T11', 'pcm32')
        assert r3 and r3['status'] == mod.Result.NOT_EXECUTED, \
            'T11/pcm32 debe ser NOT_EXECUTED (fixture posterior)'
        r4 = get_result(report, 'A_private', 'T11', 'pcm16')
        assert r4 and r4['status'] == mod.Result.NOT_EXECUTED, \
            'T11/pcm16 debe ser NOT_EXECUTED (interrupcion previa; no se inventa PASS)'
        r5 = get_result(report, 'B_shared', 'T16', None)
        assert r5 and r5['status'] == mod.Result.NOT_EXECUTED, \
            'segundo entorno no ejecutado'
        assert report['summary']['error'] == 1 and report['summary']['pass'] == 0, \
            'summary inconsistente: {0}'.format(report['summary'])
        assert len(report['results']) == 36, '36 entradas registradas'
    finally:
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


def test_c5_v05_flujo_real_main_ki_makedirs():
    """KI creando el directorio de ejecucion (flujo real): entorno NOT_EXECUTED + rc 130."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    real_makedirs = mod.safe_makedirs_exclusive_anchored

    def ki_makedirs(path):
        raise KeyboardInterrupt()

    mod.safe_makedirs_exclusive_anchored = ki_makedirs
    old_np, old_sf = inject_fakes()
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI debe absorberse dentro de main (rc 130)'
        assert rc == 130, 'rc esperado 130, obtenido {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, 'informe no publicado tras interrupcion'
        assert report['interrupted'] is True, 'interrupted debe ser True'
        # C5 (v0.2.5): el entorno interrumpido registra TODAS sus pruebas
        # (coherente con la ruta OSError), no cero entradas.
        assert count_results(report, 'A_private') == 18, \
            'el entorno interrumpido debe registrar 18 entradas NOT_EXECUTED'
        for tid, fx in [('T11', 'pcm16'), ('T16', None)]:
            r = get_result(report, 'A_private', tid, fx)
            assert r and r['status'] == mod.Result.NOT_EXECUTED, \
                '{0}/{1} debe ser NOT_EXECUTED'.format(tid, fx)
            assert 'KeyboardInterrupt' in r['detail'] or 'interrump' in r['detail'], \
                'detalle sin marca de interrupcion: {0}'.format(r['detail'][:80])
        r_b = get_result(report, 'B_shared', 'T11', 'pcm16')
        assert r_b and r_b['status'] == mod.Result.NOT_EXECUTED, \
            'segundo entorno no ejecutado'
        assert report['summary']['pass'] == 0 and report['summary']['error'] == 0, \
            'summary inconsistente: {0}'.format(report['summary'])
    finally:
        mod.safe_makedirs_exclusive_anchored = real_makedirs
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


def test_c5_v05_flujo_real_main_ki_preparacion_informe():
    """KI en la fase de resumen/informe (flujo real): resultados conservados + informe con interrupted=true."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    real_strftime = time.strftime
    state = {'n': 0}

    def ki_strftime(fmt, *a, **k):
        if fmt == '%Y-%m-%dT%H:%M:%S%z':
            state['n'] += 1
            if state['n'] == 2:
                # 1a llamada: started_at; 2a llamada: finished_at (fase de informe)
                raise KeyboardInterrupt()
        return real_strftime(fmt, *a, **k)

    time.strftime = ki_strftime
    old_np, old_sf = inject_fakes()
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI de la fase de informe debe absorberse en main'
        assert rc == 130, 'rc esperado 130, obtenido {0}'.format(rc)
        report = load_report(d1)
        assert report is not None, \
            'C5 (v0.2.5): la KI en la fase de informe NO debe perder los resultados'
        assert report['interrupted'] is True, 'interrupted debe ser True'
        assert report['summary']['interrupted'] is True, 'summary.interrupted'
        assert report['summary']['pass'] == 36, \
            'los 36 resultados obtenidos deben conservarse: {0}'.format(
                report['summary'])
        assert len(report['results']) == 36, 'resultados conservados'
        assert 'resultados conservados' in (report['interrupt_message'] or ''), \
            'mensaje de interrupcion sin marca de conservacion'
    finally:
        time.strftime = real_strftime
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


def test_c5_v05_flujo_real_main_ki_publicacion():
    """KI durante la publicacion del informe (flujo real): rc 130, provisional conservado, sin publicacion."""
    d1 = fresh_tmp()
    d2 = fresh_tmp()
    real_write = os.write
    state = {'fired': False}

    def ki_write(fd, data, *a, **k):
        if not state['fired'] and data[:1] == b'{':
            # El JSON del informe empieza con '{'; los fixtures simulados no.
            state['fired'] = True
            raise KeyboardInterrupt()
        return real_write(fd, data, *a, **k)

    os.write = ki_write
    old_np, old_sf = inject_fakes()
    try:
        rc, ki, out = run_main(d1, shared_dir=d2)
        assert ki is False, 'la KI de publicacion debe absorberse (mensaje explicito + rc 130)'
        assert rc == 130, 'rc esperado 130, obtenido {0}'.format(rc)
        assert state['fired'], 'la KI de escritura no se disparo (contenido JSON)'
        assert find_published_report(d1) is None, \
            'el informe NO debe publicarse si la escritura fue interrumpida'
        prov = find_provisional(d1)
        assert prov is not None, \
            'el provisional debe quedar en disco (sin limpieza automatica)'
        assert 'no se publica' in out and 'INTERRUMPIDO' in out, \
            'stdout sin mensaje explicito de publicacion interrumpida'
    finally:
        os.write = real_write
        restore_fakes(old_np, old_sf)
        shutil.rmtree(d1, ignore_errors=True)
        shutil.rmtree(d2, ignore_errors=True)


# ============================================================================
# Bateria
# ============================================================================

def main():
    print("Pruebas unitarias aisladas v0.2.5 (C4/C5) — flujo real de main() con "
          "capa numpy/soundfile SIMULADA; entorno no Android; sin audio real")
    print("=" * 76)
    run('C4_v05_patron_token_cierre_y_obsoleto', test_c4_v05_patron_token_cierre_y_obsoleto)
    run('C4_v05_T11_T14_sin_fuga_descriptores', test_c4_v05_T11_T14_sin_fuga_descriptores)
    run('C4_v05_T15_T16_sin_fuga_descriptores', test_c4_v05_T15_T16_sin_fuga_descriptores)
    run('C4_v05_safe_create_file_token_contrato', test_c4_v05_safe_create_file_token_contrato)
    run('C4_v05_sin_patron_cierre_sin_token', test_c4_v05_sin_patron_cierre_sin_token)
    run('C5_v05_flujo_real_main_completo', test_c5_v05_flujo_real_main_completo)
    run('C5_v05_flujo_real_main_ki_prueba', test_c5_v05_flujo_real_main_ki_prueba)
    run('C5_v05_flujo_real_main_ki_create_fixture', test_c5_v05_flujo_real_main_ki_create_fixture)
    run('C5_v05_flujo_real_main_ki_makedirs', test_c5_v05_flujo_real_main_ki_makedirs)
    run('C5_v05_flujo_real_main_ki_preparacion_informe',
        test_c5_v05_flujo_real_main_ki_preparacion_informe)
    run('C5_v05_flujo_real_main_ki_publicacion', test_c5_v05_flujo_real_main_ki_publicacion)
    print("=" * 76)
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
