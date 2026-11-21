#!/usr/bin/env python3
"""Pruebas unitarias aisladas C4-A v0.2.8 — encapsulación de la consulta de recursos.

Se importa el instrumento audioinput_diag_termux.py v0.2.8 y se verifica la
corrección final C4-A: get_resource(token) retorna una INSTANTÁNEA INMUTABLE
(_ResourceSnapshot) que NO expone ni conserva referencia al objeto
OwnedFdResource interno; la mutación por atributo o clave es rechazada y, aun
en caso de mutación hostil del objeto retornado, el recurso interno no se ve
afectado (es una copia). Cada nueva llamada a get_resource refleja el estado
ACTUAL (semántica de fotografía).

CLASIFICACIÓN:
  - PASS: comportamiento exigible verificado.
  - EXPECTED_LIMITATION: escenario que VIOLA deliberadamente el contrato y
    cuya detección no es portable (cierre externo + reutilización del MISMO
    número para el MISMO archivo). NO es una aprobación de seguridad.
  - NOT_EXECUTED: condición no reproducible en este entorno (nunca PASS
    inventado).

No Android/Termux, no audio real, no muestras del proyecto, sin libsndfile.
"""
import ast
import errno
import importlib.util
import os
import shutil
import sys
import tempfile
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
    print("{0:20} {1:52} {2}".format(status, name, detail))


class NotReproducible(Exception):
    """Condición del caso no reproducible en este entorno -> NOT_EXECUTED."""


def run(name, fn):
    try:
        fn()
        record(name, 'PASS', DETAILS.get(name, 'OK'))
    except NotReproducible as exc:
        record(name, 'NOT_EXECUTED', str(exc))
    except (ImportError, ModuleNotFoundError) as exc:
        record(name, 'NOT_EXECUTED', 'dependencia/condicion no disponible: {0}'.format(exc))
    except AssertionError as exc:
        record(name, 'FAIL', str(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


def run_limitation(name, fn):
    try:
        fn()
        record(name, 'EXPECTED_LIMITATION', DETAILS.get(name, 'limite documentado'))
    except NotReproducible as exc:
        record(name, 'NOT_EXECUTED', str(exc))
    except AssertionError as exc:
        record(name, 'FAIL', 'comportamiento difiere del documentado: {0}'.format(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


def fresh_tmp():
    return tempfile.mkdtemp(prefix='c4a8_ut_')


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


class CloseCounter(object):
    """Cuenta las llamadas reales a os.close sobre un fd objetivo."""

    def __init__(self, target_fd):
        self.target = target_fd
        self.count = 0
        self._real = mod.os.close

    def _fake(self, fd, *a, **k):
        if fd == self.target:
            self.count += 1
        return self._real(fd, *a, **k)

    def __enter__(self):
        mod.os.close = self._fake
        return self

    def __exit__(self, *exc):
        mod.os.close = self._real
        return False


def make_file(d, name, content=b'x' * 400):
    p = os.path.join(d, name)
    with open(p, 'wb') as fh:
        fh.write(content)
    return p


def try_reuse_open(path, target_fd, max_tries=40):
    """Intenta reabrir `path` obteniendo el mismo numero target_fd."""
    for _ in range(max_tries):
        cand = os.open(path, os.O_RDONLY)
        if cand == target_fd:
            return cand
        os.close(cand)
    return None


# ============================================== pruebas de encapsulacion v0.2.8
def test_01_consulta_atributos_y_claves():
    """Consulta por atributo y por clave de los 7 campos; clave desconocida -> KeyError."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'a.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'consulta')
        snap = c.get_resource(tok)
        for field in ('token', 'fd', 'label', 'dev', 'ino', 'state', 'close_result'):
            assert hasattr(snap, field), 'falta atributo {0}'.format(field)
            assert field in snap, 'falta clave {0}'.format(field)
            assert getattr(snap, field) == snap[field], \
                'atributo y clave difieren para {0}'.format(field)
        assert snap.token == tok
        assert snap.fd == fd
        assert snap.label == 'consulta'
        assert snap.state == mod.OwnedFdResource.STATE_OPEN
        assert snap.close_result is None
        try:
            snap['clave_inexistente']
            raise AssertionError('clave inexistente debe lanzar KeyError')
        except KeyError:
            pass
        assert 'clave_inexistente' not in snap
        DETAILS['C4A8_01_consulta_atributos_y_claves'] = \
            '7 campos accesibles por atributo y clave; valores correctos'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_02_sin_referencia_al_recurso_interno():
    """La instantanea NO expone _res ni otra referencia al objeto interno."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'b.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'sin_ref')
        snap = c.get_resource(tok)
        sentinel = object()
        for probe in ('_res', 'resource', '_resource', '_entry', 'res',
                      '_entries', '_internal', '__dict__'):
            assert getattr(snap, probe, sentinel) is sentinel, \
                'la instantanea expone {0!r} (referencia accesible al interno)'.format(probe)
        try:
            vars(snap)
            raise AssertionError('vars() debe fallar (sin __dict__): el interno no es alcanzable')
        except TypeError:
            pass
        # dir() solo contiene los campos y atributos de clase
        publico = [n for n in dir(snap) if not n.startswith('__')]
        assert set(publico) <= set(snap._FIELDS) | {'_FIELDS'}, \
            'atributos publicos inesperados: {0}'.format(publico)
        DETAILS['C4A8_02_sin_referencia_al_recurso_interno'] = \
            'sin _res/resource/__dict__/vars; solo los 7 campos de consulta'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_03_mutacion_rechazada_e_interno_intacto():
    """Modificar el estado/FD a traves del objeto retornado no altera el recurso interno.

    NO se limita a comprobar la excepcion: incluso con un bypass hostil
    (object.__setattr__ sobre la instantanea, fuera del alcance exigido), el
    recurso interno permanece intacto porque la instantanea es una COPIA.
    """
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'c.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'mutacion')
        snap = c.get_resource(tok)
        st_orig = os.fstat(fd)
        # Asignacion por atributo: rechazada
        try:
            snap.state = mod.OwnedFdResource.STATE_CLOSED
            raise AssertionError('la asignacion de state debe rechazarse')
        except AttributeError:
            pass
        # Asignacion de fd por atributo: rechazada
        try:
            snap.fd = 999999
            raise AssertionError('la asignacion de fd debe rechazarse')
        except AttributeError:
            pass
        # Asignacion por clave: rechazada
        try:
            snap['state'] = mod.OwnedFdResource.STATE_CLOSED
            raise AssertionError('la asignacion por clave debe rechazarse')
        except TypeError:
            pass
        # Bypass hostil (fuera del alcance exigido): muta la COPIA, no el interno
        object.__setattr__(snap, 'state', 'ALTERADO_HOSTIL')
        object.__setattr__(snap, 'fd', 123456)
        # El recurso interno NO cambio (verificado con NUEVAS consultas)
        snap2 = c.get_resource(tok)
        assert snap2.state == mod.OwnedFdResource.STATE_OPEN, \
            'el estado interno fue alterado a traves del objeto retornado'
        assert snap2.fd == fd, 'el fd interno fue alterado'
        st_now = os.fstat(fd)
        assert (st_now.st_dev, st_now.st_ino) == (st_orig.st_dev, st_orig.st_ino) \
            and fd_alive(fd), 'el descriptor real fue alterado'
        DETAILS['C4A8_03_mutacion_rechazada_e_interno_intacto'] = \
            'asignaciones rechazadas (AttributeError/TypeError); bypass hostil solo altera la copia; interno intacto (nueva consulta)'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_04_cierre_reflejado_en_nueva_consulta():
    """Tras el cierre correcto por token, una NUEVA consulta retorna CLOSED.

    La instantanea previa no se actualiza (semantica de fotografia,
    documentada en v0.2.8).
    """
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'd.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'fotografia')
        snap_antes = c.get_resource(tok)
        assert snap_antes.state == mod.OwnedFdResource.STATE_OPEN
        assert c.close_fd(fd, 'fotografia', token=tok) is None
        # La instantanea anterior no se actualiza (documentado)
        assert snap_antes.state == mod.OwnedFdResource.STATE_OPEN, \
            'la instantanea previa no debe mutarse retroactivamente'
        # La NUEVA consulta refleja el estado actual
        snap_despues = c.get_resource(tok)
        assert snap_despues.state == mod.OwnedFdResource.STATE_CLOSED, \
            'la nueva consulta debe reflejar CLOSED'
        assert snap_despues.close_result == 'ok'
        DETAILS['C4A8_04_cierre_reflejado_en_nueva_consulta'] = \
            'nueva consulta -> CLOSED/ok; instantanea previa sin cambios (fotografia)'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ============================================== casos C4-A (continuan funcionando)
def test_05_token_obsoleto_sin_segundo_close():
    """Token obsoleto sigue sin provocar un segundo os.close."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'e.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'obsoleto')
        assert c.close_fd(fd, 'obsoleto', token=tok) is None
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'obsoleto', token=tok)
        assert r is None and cc.count == 0
        assert any('obsoleto' in w.get('strerror', '') for w in c.warnings)
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_06_caso_exigible_reutilizacion_mismo_archivo():
    """Caso exigible: cierre correcto -> reutilizacion del numero para el MISMO
    archivo -> token antiguo NO cierra la nueva apertura (recurso CLOSED);
    la nueva apertura permanece utilizable."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'f.bin')
        fd1 = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'propietario')
        assert c.close_fd(fd1, 'propietario', token=t1) is None
        assert c.get_resource(t1).state == mod.OwnedFdResource.STATE_CLOSED
        fd2 = try_reuse_open(p, fd1)
        if fd2 is None:
            raise NotReproducible(
                'el sistema no reutilizó el mismo numero de fd en esta ejecucion')
        with CloseCounter(fd2) as cc:
            assert c.close_fd(fd2, 'posterior', token=t1) is None
        assert cc.count == 0 and fd_alive(fd2)
        t2 = c.register_fd(fd2, 'nueva_apertura')
        assert c.close_fd(fd2, 'nueva_apertura', token=t2) is None
        DETAILS['C4A8_06_caso_exigible_reutilizacion_mismo_archivo'] = \
            'reutilizacion confirmada; token antiguo invalidado; nueva apertura utilizable'
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_07_cierre_sin_token_nunca_cierra():
    """Contrato estricto (v0.2.7, intacto): close_fd sin token no cierra nada."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'g.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'registrado')
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'sin_token') is None
        assert cc.count == 0
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_OPEN
        assert fd_alive(fd)
        assert any('sin token rechazado' in w.get('strerror', '') for w in c.warnings)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_08_doble_cierre():
    """Doble cierre: aviso; os.close una sola vez."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'h.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r8')
        assert c.close_fd(fd, 'r8', token=tok) is None
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'r8', token=tok) is None
        assert cc.count == 0
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_09_token_desconocido_y_no_registrado():
    """Token desconocido y descriptor no registrado: nunca se cierra."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'i.bin')
        fd = os.open(p, os.O_RDONLY)  # nunca se registra
        c = mod.CloseErrorLogger()
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'desconocido', token=987654) is None
            assert c.close_fd(fd, 'sin_registro') is None
        assert cc.count == 0 and fd_alive(fd)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_10_dos_aperturas_mismo_archivo():
    """Dos aperturas independientes del mismo archivo; cada cierre con su token."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'j.bin')
        fd1 = os.open(p, os.O_RDONLY)
        fd2 = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'ap1')
        t2 = c.register_fd(fd2, 'ap2')
        assert t1 != t2
        assert c.close_fd(fd1, 'ap1', token=t1) is None
        assert fd_alive(fd2)
        assert c.close_fd(fd2, 'ap2', token=t2) is None
        assert c.get_resource(t1).state == mod.OwnedFdResource.STATE_CLOSED
        assert c.get_resource(t2).state == mod.OwnedFdResource.STATE_CLOSED
        assert c.errors == []
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_11_error_simulado_e_incierto_sin_reintento():
    """Fallo simulado de os.close(): estado incierto; la nueva consulta lo refleja;
    el segundo intento NO invoca os.close."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'k.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r11')
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io simulado')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            r = c.close_fd(fd, 'r11', token=tok)
        finally:
            mod.os.close = real_close
        assert isinstance(r, OSError) and r.errno == errno.EIO
        assert len(c.errors) == 1
        # La NUEVA consulta refleja el estado actual (incierto)
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_UNCERTAIN
        assert c.get_resource(tok).close_result == \
            'uncertain:close_errno={0}'.format(errno.EIO)
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'r11', token=tok) is None
        assert cc.count == 0
        assert fd_alive(fd)
        DETAILS['C4A8_11_error_simulado_e_incierto_sin_reintento'] = \
            'nueva consulta -> CLOSE_FAILED_UNCERTAIN; reintento sin os.close'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ---- capa soundfile simulada minima ----
class _FakeSFile(object):
    def __init__(self, file, mode='r', closefd=False):
        self._fd = file
        self.closed = False
        st = os.fstat(file)
        self.channels = 2
        self.samplerate = 44100
        self.frames = st.st_size // 8

    def close(self):
        self.closed = True  # closefd=False: el descriptor NO se cierra aqui


def test_12_soundfile_closefd_false():
    """SoundFile(fd, closefd=False) no asume propiedad; el propietario cierra luego."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'l.wav', content=b'RIFF' + b'\x00' * 500)
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'fd_propio')
        sf_fake = type(sys)('soundfile_sim_v028')
        sf_fake.SoundFile = _FakeSFile
        sfile = sf_fake.SoundFile(fd, mode='r', closefd=False)
        sfile.close()
        assert sfile.closed and fd_alive(fd)
        assert c.get_resource(tok).fd == fd
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'fd_propio', token=tok) is None
        assert cc.count == 1
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert not fd_alive(fd)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_13_reentrada_closing():
    """Reentrada durante el cierre: aviso; un solo os.close; CLOSED final
    (maquina de estados intacta, verificada via nuevas consultas)."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'm.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r13')
        real_close = mod.os.close
        calls = {'n': 0}

        def reentrant_close(fd_):
            if fd_ == fd:
                calls['n'] += 1
                if calls['n'] == 1:
                    c.close_fd(fd, 'r13', token=tok)
            return real_close(fd_)

        mod.os.close = reentrant_close
        try:
            r = c.close_fd(fd, 'r13', token=tok)
        finally:
            mod.os.close = real_close
        assert r is None and calls['n'] == 1
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert any('ya iniciado' in w.get('strerror', '') for w in c.warnings)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_14_auditoria_estatica():
    """Estatico: os.close solo en el propietario/_close_fd_tracked; snapshot
    conectada a get_resource; sin restos de la vista; llamadores con token."""
    with open(TARGET, encoding='utf-8') as fh:
        src = fh.read()
    tree = ast.parse(src)
    os_close_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'close' and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == 'os':
                for parent in ast.walk(tree):
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for child in ast.walk(parent):
                            if child is node:
                                os_close_funcs.add(parent.name)
    assert os_close_funcs <= {'close_fd', '_close_fd_tracked'}, \
        'os.close fuera del propietario/_close_fd_tracked: {0}'.format(os_close_funcs)
    assert 'open_tokens' not in src, 'persiste la resolucion automatica por fd'
    assert '_ReadOnlyResourceView' not in src, 'persiste la vista defectuosa'
    assert 'return _ResourceSnapshot(resource)' in src, \
        'get_resource no retorna la instantanea'
    assert '__slots__ = _FIELDS' in src, 'la instantanea no esta restringida a _FIELDS'
    import re
    callers = re.findall(r'closer\.close_fd\([^)]*\)', src)
    sin_token = [cl for cl in callers if 'token=' not in cl]
    assert not sin_token, 'llamadas internas sin token: {0}'.format(sin_token)
    DETAILS['C4A8_14_auditoria_estatica'] = \
        'os.close solo en {0}; sin vista; snapshot en get_resource; llamadores con token={1}'.format(
            sorted(os_close_funcs), len(callers))


def test_15_auditoria_runtime():
    """Runtime: durante un flujo completo, 0 cierres de numeros de recursos
    registrados vivos fuera del propietario."""
    import io as _io
    import struct as _s
    from contextlib import redirect_stdout as _rso

    d = fresh_tmp()
    registered = set()
    violations = []

    orig_register = mod.CloseErrorLogger.register_fd
    orig_close_fd = mod.CloseErrorLogger.close_fd
    orig_close = mod.os.close

    def patched_register(self, fd, label):
        if fd is not None:
            registered.add(fd)
        return orig_register(self, fd, label)

    def patched_close_fd(self, fd, label, token=None):
        r = orig_close_fd(self, fd, label, token=token)
        if token is not None:
            res = self._entries.get(token)
            if res is not None and res.state == mod.OwnedFdResource.STATE_CLOSED:
                registered.discard(res.fd)
        return r

    def audited_close(fd, *a, **k):
        caller = sys._getframe(1).f_code.co_name
        if fd in registered and caller != 'close_fd':
            violations.append((caller, fd))
        return orig_close(fd, *a, **k)

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

    fake_np = type(sys)('numpy_sim_v028')
    fake_np.__version__ = 'sim-0.0'
    rng_mod = type(sys)('rng_sim_v028')
    rng_mod.default_rng = lambda seed=None: _FakeRng()
    fake_np.random = rng_mod
    fake_np.array_equal = lambda a, b: (a.data == b.data and tuple(a.shape) == tuple(b.shape))

    class _FakeSFile(object):
        def __init__(self, file, mode='r', samplerate=None, channels=None,
                     format=None, subtype=None, closefd=False):
            self._fd = file
            self.closed = False
            self._pos = 0
            st = os.fstat(file)
            if mode == 'w':
                self.samplerate = samplerate
                self.channels = channels
                self.frames = 0
            else:
                self.channels = 2
                self.samplerate = 44100
                self.frames = st.st_size // 8

        def write(self, arr):
            buf = bytearray()
            for row in arr.data:
                for v in row:
                    buf += _s.pack('<f', float(v))
            os.write(self._fd, bytes(buf))
            self.frames += len(arr.data)

        def read(self, frames, dtype='float64', always_2d=False):
            nbytes = frames * self.channels * 4
            data = os.pread(self._fd, nbytes, self._pos)
            self._pos += len(data)
            n = len(data) // (self.channels * 4)
            rows = [_s.unpack_from('<{0}f'.format(self.channels), data,
                                   i * self.channels * 4) for i in range(n)]
            return _FakeArr([list(r) for r in rows], (n, self.channels))

        def seek(self, offset, whence=0):
            self._pos = offset
            return self._pos

        def close(self):
            self.closed = True

    fake_sf = type(sys)('soundfile_sim_v028')
    fake_sf.__version__ = 'sim-0.0'
    fake_sf.SoundFile = _FakeSFile
    fake_sf.LibsndfileError = type('LibsndfileError', (Exception,), {})
    fake_sf.available_subtypes = lambda fmt: ({'PCM_16': 'x', 'PCM_24': 'x',
                                               'PCM_32': 'x', 'FLOAT': 'x'}
                                              if fmt == 'WAV' else {})

    run_dir = os.path.join(d, 'run')
    os.mkdir(run_dir, 0o700)
    closer_fx = mod.CloseErrorLogger()

    mod.os.close = audited_close
    mod.CloseErrorLogger.register_fd = patched_register
    mod.CloseErrorLogger.close_fd = patched_close_fd
    try:
        fpath, ferr = mod.create_fixture(fake_np, fake_sf, run_dir, 'pcm16',
                                         'PCM_16', closer_fx)
        assert ferr is None, 'create_fixture fallo: {0}'.format(ferr)
        with _rso(_io.StringIO()):
            for tid, fn in mod.TEST_FUNCTIONS.items():
                fn(fake_np, fake_sf, fpath)
            for tid, fn in [('T15', mod.test_t15_libsndfile_error_raised),
                            ('T16', mod.test_t16_fd_survives_closefd_false_failure)]:
                fn(fake_np, fake_sf, run_dir)
            ok_file, err_file, cerr_file = mod.safe_create_file_exclusive_anchored(
                os.path.join(d, 'extra.bin'), b'DATOS')
            assert ok_file, 'safe_create_file fallo: {0}'.format(err_file)
            ok_rep, err_rep, cerr_rep = mod.write_report_json_robust(
                Path(os.path.join(run_dir, 'informe_auditoria.json')),
                {'auditoria': 'rutas de cierre v0.2.8'})
            assert ok_rep, 'informe no publicado: {0}'.format(err_rep)
        assert violations == [], \
            'cierres de descriptores registrados fuera del propietario: {0}'.format(violations)
        DETAILS['C4A8_15_auditoria_runtime'] = (
            '{0} aperturas registradas vivas durante el flujo; 0 cierres de '
            'numeros de recursos registrados vivos fuera del propietario'.format(
                len(registered)))
    finally:
        mod.os.close = orig_close
        mod.CloseErrorLogger.register_fd = orig_register
        mod.CloseErrorLogger.close_fd = orig_close_fd
        registered.clear()
        shutil.rmtree(d, ignore_errors=True)


def test_16_violacion_mismo_archivo_limite():
    """EXPECTED_LIMITATION: cierre externo + reutilizacion del MISMO numero para
    el MISMO archivo. No detectable de forma portable; comportamiento
    documentado verificado (el cierre procede y afecta a la apertura ajena).
    NO es una aprobacion de seguridad."""
    d = fresh_tmp()
    fd = fd2 = None
    try:
        p = make_file(d, 'n.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'ap_original')
        st_orig = os.fstat(fd)
        os.close(fd)  # VIOLACION: cierre externo
        fd2 = try_reuse_open(p, fd)
        if fd2 is None:
            raise NotReproducible(
                'el sistema no reutilizó el mismo numero de fd en esta ejecucion')
        st_new = os.fstat(fd2)
        assert (st_new.st_dev, st_new.st_ino) == (st_orig.st_dev, st_orig.st_ino)
        with CloseCounter(fd2) as cc:
            r = c.close_fd(fd2, 'ap_original', token=tok)
        assert r is None and cc.count == 1
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert not fd_alive(fd2), 'consecuencia del limite no observada'
        DETAILS['C4A8_16_violacion_mismo_archivo_limite'] = (
            'LIMITE DOCUMENTADO (no es deteccion ni proteccion): fstat coincide '
            'para el mismo archivo; ninguna primitiva portable identifica el '
            'open-file-description; el cierre del propietario procede y afecta a '
            'la apertura ajena. Mitigacion: contrato de propiedad + encapsulacion.')
    finally:
        close_quietly(fd)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================= bateria
def main():
    print("Pruebas unitarias C4-A v0.2.8 — encapsulacion de la consulta "
          "(entorno no Android, sin audio real)")
    print("=" * 84)
    run('C4A8_01_consulta_atributos_y_claves', test_01_consulta_atributos_y_claves)
    run('C4A8_02_sin_referencia_al_recurso_interno', test_02_sin_referencia_al_recurso_interno)
    run('C4A8_03_mutacion_rechazada_e_interno_intacto',
        test_03_mutacion_rechazada_e_interno_intacto)
    run('C4A8_04_cierre_reflejado_en_nueva_consulta',
        test_04_cierre_reflejado_en_nueva_consulta)
    run('C4A8_05_token_obsoleto_sin_segundo_close', test_05_token_obsoleto_sin_segundo_close)
    run('C4A8_06_caso_exigible_reutilizacion', test_06_caso_exigible_reutilizacion_mismo_archivo)
    run('C4A8_07_cierre_sin_token_nunca_cierra', test_07_cierre_sin_token_nunca_cierra)
    run('C4A8_08_doble_cierre', test_08_doble_cierre)
    run('C4A8_09_token_desconocido_y_no_registrado', test_09_token_desconocido_y_no_registrado)
    run('C4A8_10_dos_aperturas_mismo_archivo', test_10_dos_aperturas_mismo_archivo)
    run('C4A8_11_error_simulado_e_incierto_sin_reintento',
        test_11_error_simulado_e_incierto_sin_reintento)
    run('C4A8_12_soundfile_closefd_false', test_12_soundfile_closefd_false)
    run('C4A8_13_reentrada_closing', test_13_reentrada_closing)
    run('C4A8_14_auditoria_estatica', test_14_auditoria_estatica)
    run('C4A8_15_auditoria_runtime', test_15_auditoria_runtime)
    run_limitation('C4A8_16_violacion_mismo_archivo_limite',
                   test_16_violacion_mismo_archivo_limite)
    print("=" * 84)
    n_pass = sum(1 for _, s, _ in RESULTS if s == 'PASS')
    n_lim = sum(1 for _, s, _ in RESULTS if s == 'EXPECTED_LIMITATION')
    n_ne = sum(1 for _, s, _ in RESULTS if s == 'NOT_EXECUTED')
    n_fail = sum(1 for _, s, _ in RESULTS if s == 'FAIL')
    n_err = sum(1 for _, s, _ in RESULTS if s == 'ERROR')
    print("TOTAL {0} | PASS {1} | EXPECTED_LIMITATION {2} | NOT_EXECUTED {3} | "
          "FAIL {4} | ERROR {5}".format(len(RESULTS), n_pass, n_lim, n_ne,
                                        n_fail, n_err))
    print("NOTA: EXPECTED_LIMITATION NO es una aprobacion de seguridad; es un "
          "limite documentado del contrato.")
    for name, status, detail in RESULTS:
        if status not in ('PASS', 'EXPECTED_LIMITATION'):
            print("  REVISAR: {0} [{1}] {2}".format(name, status, detail))
    return 0 if (n_fail == 0 and n_err == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
