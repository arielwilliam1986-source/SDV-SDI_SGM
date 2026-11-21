#!/usr/bin/env python3
"""Pruebas unitarias aisladas C4-A CIERRE v0.2.7 — contrato estricto de propiedad.

Se importa el instrumento audioinput_diag_termux.py v0.2.7 y se verifican los
ajustes de cierre C4-A (decision tecnica vinculante):

  - solo el propietario cierra su recurso, una unica vez, SIEMPRE con token;
  - close_fd() SIN token no cierra ningun descriptor (ni registrado OPEN);
  - get_resource(token) retorna una vista de solo lectura;
  - estados OPEN / CLOSING / CLOSED / CLOSE_FAILED_UNCERTAIN se conservan;
  - token cerrado, desconocido o incierto nunca inicia otro cierre;
  - SoundFile permanece con closefd=False y el propietario conserva el cierre;
  - ninguna ruta interna cierra directamente un descriptor registrado.

CLASIFICACION DE ESCENARIOS (vinculante):
  - PASS: comportamiento exigible verificado.
  - EXPECTED_LIMITATION: escenario que VIOLA deliberadamente el contrato y
    cuya deteccion no es portable (cierre externo + reutilizacion del MISMO
    numero para el MISMO archivo). NO es una aprobacion de seguridad; se
    verifica y documenta el comportamiento del limite.
  - NOT_EXECUTED: condicion no reproducible en este entorno (nunca PASS
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
    """Condicion del caso no reproducible en este entorno -> NOT_EXECUTED."""


def run(name, fn):
    """Prueba exigible: PASS o FAIL/ERROR/NOT_EXECUTED."""
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
    """Prueba de limitacion: el comportamiento documentado se verifica, pero
    el escenario NO contabiliza como PASS de seguridad."""
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
    return tempfile.mkdtemp(prefix='c4acierre_ut_')


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
    """Intenta reabrir `path` obteniendo el mismo numero target_fd.

    Retorna el fd reutilizado o None. Los intentos fallidos se cierran.
    """
    for _ in range(max_tries):
        cand = os.open(path, os.O_RDONLY)
        if cand == target_fd:
            return cand
        os.close(cand)
    return None


# ---- capa soundfile simulada minima (solo para la prueba SoundFile) ----
class _FakeSFile(object):
    def __init__(self, file, mode='r', closefd=False):
        self._fd = file
        self.closed = False
        st = os.fstat(file)
        self.channels = 2
        self.samplerate = 44100
        self.frames = st.st_size // 8

    def close(self):
        # closefd=False: el descriptor NO se cierra aqui (contrato).
        self.closed = True


def make_fake_sf():
    types = type(sys)('soundfile_sim_cierre')
    types.__version__ = 'sim-0.0'
    types.SoundFile = _FakeSFile
    return types


# ================================================================ minimos
def test_01_cierre_normal_propietario():
    """Cierre normal mediante el propietario: OPEN -> CLOSED, 1 os.close."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'a.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r1')
        res = c.get_resource(tok)
        assert res.state == mod.OwnedFdResource.STATE_OPEN
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'r1', token=tok) is None
        assert cc.count == 1
        assert res.state == mod.OwnedFdResource.STATE_CLOSED
        assert res.close_result == 'ok'
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_02_dos_aperturas_mismo_archivo_cada_token():
    """Dos aperturas del mismo archivo: recursos/tokens distintos; cada cierre con su token."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'b.bin')
        fd1 = os.open(p, os.O_RDONLY)
        fd2 = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'ap1')
        t2 = c.register_fd(fd2, 'ap2')
        assert t1 != t2
        r1, r2 = c.get_resource(t1), c.get_resource(t2)
        assert (r1.dev, r1.ino) == (r2.dev, r2.ino), 'mismo archivo (la comparacion no distingue)'
        assert c.close_fd(fd1, 'ap1', token=t1) is None
        assert fd_alive(fd2)
        assert c.close_fd(fd2, 'ap2', token=t2) is None
        assert r1.state == r2.state == mod.OwnedFdResource.STATE_CLOSED
        assert c.errors == []
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_03_doble_cierre():
    """Doble cierre del mismo recurso: aviso; os.close una sola vez."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'c.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r3')
        res = c.get_resource(tok)
        assert c.close_fd(fd, 'r3', token=tok) is None
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'r3', token=tok) is None
        assert cc.count == 0
        assert res.state == mod.OwnedFdResource.STATE_CLOSED
        assert any('obsoleto' in w.get('strerror', '') for w in c.warnings)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_04_token_antiguo_tras_cierre_correcto_y_reutilizacion():
    """Caso exigible (instruccion seccion 3): propietario cierra correctamente;
    el sistema reutiliza el numero para abrir el MISMO archivo; el token
    antiguo NO cierra la nueva apertura (su recurso ya esta CLOSED) y la
    nueva apertura permanece utilizable."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'd.bin')
        fd1 = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'propietario')
        assert c.close_fd(fd1, 'propietario', token=t1) is None
        fd2 = try_reuse_open(p, fd1)
        if fd2 is None:
            raise NotReproducible(
                'el sistema no reutilizó el mismo numero de fd en esta ejecucion')
        assert fd2 == fd1, 'reutilizacion del numero confirmada'
        with CloseCounter(fd2) as cc:
            r = c.close_fd(fd2, 'posterior', token=t1)
        assert r is None, 'el token antiguo no debe fallar ni cerrar'
        assert cc.count == 0, 'el token antiguo provoco os.close'
        assert fd_alive(fd2), 'la nueva apertura debe permanecer utilizable tras el token antiguo'
        # La nueva apertura es plenamente operable con su propio registro
        t2 = c.register_fd(fd2, 'nueva_apertura')
        assert c.close_fd(fd2, 'nueva_apertura', token=t2) is None
        assert c.get_resource(t2).state == mod.OwnedFdResource.STATE_CLOSED
        DETAILS['C4AC_04_token_antiguo_reutilizacion'] = (
            'reutilizacion del numero confirmada; token antiguo invalidado por '
            'estado CLOSED; nueva apertura utilizable y cerrable con token propio')
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_05_token_desconocido():
    """Token desconocido: aviso; no se cierra nada."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'e.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'desconocido', token=999999) is None
        assert cc.count == 0 and fd_alive(fd)
        assert any('desconocido' in w.get('strerror', '') for w in c.warnings)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_06_descriptor_no_registrado():
    """Descriptor no registrado: sin token no se cierra; token desconocido tampoco."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'f.bin')
        fd = os.open(p, os.O_RDONLY)  # NUNCA se registra
        c = mod.CloseErrorLogger()
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'sin_registro') is None
            assert c.close_fd(fd, 'con_token_desconocido', token=424242) is None
        assert cc.count == 0 and fd_alive(fd)
        assert any('sin token rechazado' in w.get('strerror', '') for w in c.warnings)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_07_cierre_sin_token_nunca_cierra():
    """Decision vinculante: close_fd() SIN token no cierra NI UN descriptor
    registrado como OPEN. El cierre requiere el token de la apertura."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'g.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'registrado')  # registrado y OPEN
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'sin_token', token=None) is None
            assert c.close_fd(fd, 'sin_token_arg') is None
        assert cc.count == 0, 'os.close invocado en cierre sin token'
        assert fd_alive(fd), 'el descriptor registrado fue cerrado sin token'
        res = c.get_resource(tok)
        assert res.state == mod.OwnedFdResource.STATE_OPEN, 'estado alterado por cierre sin token'
        assert any('sin token rechazado' in w.get('strerror', '') for w in c.warnings)
        assert c.errors == []
        # El propietario sigue pudiendo cerrar con su token
        assert c.close_fd(fd, 'propietario', token=tok) is None
        assert res.state == mod.OwnedFdResource.STATE_CLOSED
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_08_error_simulado_os_close():
    """Fallo simulado de os.close(): error devuelto y conservado; estado incierto."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'h.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r8')
        res = c.get_resource(tok)
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io simulado')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            r = c.close_fd(fd, 'r8', token=tok)
        finally:
            mod.os.close = real_close
        assert isinstance(r, OSError) and r.errno == errno.EIO
        assert len(c.errors) == 1 and c.errors[0]['errno'] == errno.EIO
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN
        assert res.close_result == 'uncertain:close_errno={0}'.format(errno.EIO)
        DETAILS['C4AC_08_error_simulado_os_close'] = \
            'estado CLOSE_FAILED_UNCERTAIN; error conservado en errors y sink'
        drained = mod._drain_close_error_sink()
        assert any(e.get('errno') == errno.EIO for e in drained)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_09_incierto_sin_segundo_intento():
    """Estado incierto tras error de cierre: el segundo intento NO invoca os.close."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'i.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r9')
        res = c.get_resource(tok)
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io simulado')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            c.close_fd(fd, 'r9', token=tok)
        finally:
            mod.os.close = real_close
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'r9', token=tok) is None
        assert cc.count == 0, 'os.close re-invocado tras estado incierto'
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN
        assert any('incierto' in w.get('strerror', '') for w in c.warnings)
        assert fd_alive(fd)
        DETAILS['C4AC_09_incierto_sin_segundo_intento'] = \
            'os.close no se invoca tras CLOSE_FAILED_UNCERTAIN (contador 0)'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_10_soundfile_closefd_false_cierre_por_propietario():
    """SoundFile(fd, closefd=False) NO asume propiedad; el propietario cierra luego por token."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'j.wav', content=b'RIFF' + b'\x00' * 500)
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'fd_propio')
        sf_fake = make_fake_sf()
        sfile = sf_fake.SoundFile(fd, mode='r', closefd=False)
        assert sfile.frames > 0
        sfile.close()          # SoundFile cierra su objeto, NO el descriptor
        assert sfile.closed
        assert fd_alive(fd), 'SoundFile cerro el descriptor pese a closefd=False'
        assert fd in [c.get_resource(tok).fd], 'propiedad intacta tras SoundFile'
        # El cierre posterior lo realiza el propietario mediante su token
        with CloseCounter(fd) as cc:
            assert c.close_fd(fd, 'fd_propio', token=tok) is None
        assert cc.count == 1
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        assert not fd_alive(fd)
        assert c.errors == []
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_11_vista_solo_lectura():
    """get_resource retorna vista de solo lectura: consulta OK; mutacion rechazada;
    el estado real solo se modifica dentro del logger."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'k.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r11')
        res = c.get_resource(tok)
        # Lectura: atributos y acceso tipo dict de compatibilidad
        assert res.state == mod.OwnedFdResource.STATE_OPEN
        assert res.token == tok and res.fd == fd and res.label == 'r11'
        assert res['state'] == mod.OwnedFdResource.STATE_OPEN
        assert 'state' in res
        # Mutacion por atributo: rechazada
        try:
            res.state = mod.OwnedFdResource.STATE_CLOSED
            raise AssertionError('la vista permitio mutar el estado (debe rechazarlo)')
        except AttributeError:
            pass
        # Mutacion por clave: rechazada
        try:
            res['state'] = mod.OwnedFdResource.STATE_CLOSED
            raise AssertionError('la vista permitio mutar por clave')
        except TypeError:
            pass
        # El estado real no cambio y el propietario sigue operando
        assert res.state == mod.OwnedFdResource.STATE_OPEN
        assert c.close_fd(fd, 'r11', token=tok) is None
        assert res.state == mod.OwnedFdResource.STATE_CLOSED, \
            'el cierre por token debe reflejarse en la vista'
        assert res.close_result == 'ok'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_12_auditoria_estatica_rutas_cierre():
    """Estatico: os.close solo en close_fd (propietario) y _close_fd_tracked
    (descriptores internos NO registrados); sin ruta de cierre sin token."""
    with open(TARGET, encoding='utf-8') as fh:
        src = fh.read()
    tree = ast.parse(src)
    # 1) funciones que contienen llamadas directas a os.close(...)
    os_close_funcs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'close' and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id == 'os':
                # localizar la funcion contenedora
                for parent in ast.walk(tree):
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for child in ast.walk(parent):
                            if child is node:
                                os_close_funcs.add(parent.name)
    assert os_close_funcs <= {'close_fd', '_close_fd_tracked'}, \
        'os.close fuera del propietario/_close_fd_tracked: {0}'.format(os_close_funcs)
    # 2) el camino de resolucion automatica sin token fue eliminado
    assert 'open_tokens' not in src, 'persiste la resolucion automatica por fd'
    # 3) el rechazo del cierre sin token existe antes del camino de cierre
    i_reject = src.find('cierre sin token rechazado')
    i_state = src.find('# Unico camino de cierre: OPEN -> CLOSING')
    assert i_reject != -1 and i_state != -1 and i_reject < i_state, \
        'el rechazo sin token no precede al camino de cierre'
    # 4) todos los llamadores internos del logger cierran con token
    import re
    callers = re.findall(r'closer\.close_fd\([^)]*\)', src)
    assert callers, 'sin llamadas al logger (inesperado)'
    sin_token = [cl for cl in callers if 'token=' not in cl]
    assert not sin_token, 'llamadas internas sin token: {0}'.format(sin_token)
    # 5) la vista de solo lectura esta conectada a get_resource
    assert 'return _ReadOnlyResourceView(resource)' in src
    DETAILS['C4AC_12_auditoria_estatica_rutas_cierre'] = \
        'os.close solo en {0}; sin resolucion automatica por fd; rechazo sin token presente; llamadores con token={1}'.format(
            sorted(os_close_funcs), len(callers))


def test_13_auditoria_runtime_rutas_cierre():
    """Runtime: durante un flujo completo (fixture + T11-T14 + T15/T16 +
    safe_create_file + informe), ninguna funcion distinta del propietario
    cierra un descriptor registrado."""
    import io as _io
    import json as _json
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
        # Modelo del ciclo de vida del NUMERO: tras un cierre CONFIRMADO
        # por el propietario (state CLOSED), el numero queda libre y el
        # kernel puede reasignarlo a descriptores internos no registrados
        # (p. ej. cadena anclada, parent_fd). Eso NO es una violacion.
        # Una violacion real seria os.close de un numero cuyo recurso
        # registrado sigue OPEN/registrado, desde otra funcion.
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

    # capa simulada minima numpy/soundfile (sin libsndfile, sin audio real)
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

    fake_np = type(sys)('numpy_sim_cierre')
    fake_np.__version__ = 'sim-0.0'
    rng_mod = type(sys)('rng_sim')
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
            import struct as _s
            for row in arr.data:
                for v in row:
                    buf += _s.pack('<f', float(v))
            os.write(self._fd, bytes(buf))
            self.frames += len(arr.data)

        def read(self, frames, dtype='float64', always_2d=False):
            nbytes = frames * self.channels * 4
            data = os.pread(self._fd, nbytes, self._pos)
            self._pos += len(data)
            import struct as _s
            n = len(data) // (self.channels * 4)
            rows = [_s.unpack_from('<{0}f'.format(self.channels), data,
                                   i * self.channels * 4)
                    for i in range(n)]
            return _FakeArr([list(r) for r in rows], (n, self.channels))

        def seek(self, offset, whence=0):
            self._pos = offset
            return self._pos

        def close(self):
            self.closed = True

    fake_sf = type(sys)('soundfile_sim_cierre')
    fake_sf.__version__ = 'sim-0.0'
    fake_sf.SoundFile = _FakeSFile
    fake_sf.LibsndfileError = type('LibsndfileError', (Exception,), {})
    fake_sf.available_subtypes = lambda fmt: ({'PCM_16': 'x', 'PCM_24': 'x',
                                               'PCM_32': 'x', 'FLOAT': 'x'}
                                              if fmt == 'WAV' else {})

    run_dir = os.path.join(d, 'run')
    os.mkdir(run_dir, 0o700)
    results = []
    flag = [False]
    closer_fx = mod.CloseErrorLogger()
    mod.os.close = audited_close
    mod.CloseErrorLogger.register_fd = patched_register
    mod.CloseErrorLogger.close_fd = patched_close_fd
    try:
        # Flujo: creacion de fixture, T11-T14 sobre el fixture, T15/T16,
        # safe_create_file_exclusive_anchored y publicacion de informe.
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
                {'auditoria': 'rutas de cierre'})
            assert ok_rep, 'informe no publicado: {0}'.format(err_rep)
        assert violations == [], \
            'cierres de descriptores registrados fuera del propietario: {0}'.format(violations)
        DETAILS['C4AC_13_auditoria_runtime_rutas_cierre'] = (
            '{0} aperturas registradas vivas durante el flujo; 0 cierres de '
            'numeros de recursos registrados aun abiertos fuera del propietario '
            '(close_fd); los numeros liberados por cierre confirmado pueden ser '
            'reasignados por el kernel (verificado)'.format(
                len(registered)))
    finally:
        mod.os.close = orig_close
        mod.CloseErrorLogger.register_fd = orig_register
        mod.CloseErrorLogger.close_fd = orig_close_fd
        registered.clear()  # la limpieza del harness no es parte del flujo
        shutil.rmtree(d, ignore_errors=True)


def test_14_violacion_mismo_archivo_limite():
    """EXPECTED_LIMITATION: cierre externo + reutilizacion del MISMO numero
    para el MISMO archivo. No es detectable de forma portable (fstat
    coincide); se verifica el comportamiento DOCUMENTADO del limite (el
    cierre del propietario procede y afecta a la apertura ajena). NO es una
    aprobacion de seguridad."""
    d = fresh_tmp()
    fd = fd2 = None
    try:
        p = make_file(d, 'm.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'ap_original')
        st_orig = os.fstat(fd)
        # VIOLACION DEL CONTRATO: un tercero cierra por via externa.
        os.close(fd)
        # El sistema reutiliza el MISMO numero para el MISMO archivo.
        fd2 = try_reuse_open(p, fd)
        if fd2 is None:
            raise NotReproducible(
                'el sistema no reutilizó el mismo numero de fd en esta ejecucion')
        st_new = os.fstat(fd2)
        assert (st_new.st_dev, st_new.st_ino) == (st_orig.st_dev, st_orig.st_ino)
        # El diseno NO puede distinguir las aperturas (fstat coincide):
        # comportamiento documentado: el cierre procede bajo contrato.
        with CloseCounter(fd2) as cc:
            r = c.close_fd(fd2, 'ap_original', token=tok)
        assert r is None, 'comportamiento documentado: el cierre procede'
        assert cc.count == 1
        res = c.get_resource(tok)
        assert res.state == mod.OwnedFdResource.STATE_CLOSED
        # Consecuencia del limite (documentada, no oculta): la apertura
        # ajena quedo cerrada.
        assert not fd_alive(fd2), 'consecuencia del limite no observada'
        DETAILS['C4AC_14_violacion_mismo_archivo_limite'] = (
            'LIMITE DOCUMENTADO (no es deteccion ni proteccion): (dev,ino) '
            'coincide para el mismo archivo; ninguna primitiva portable '
            'identifica el open-file-description; el cierre del propietario '
            'procede y afecta a la apertura ajena. Mitigacion: contrato de '
            'propiedad + encapsulacion (ningun componente del instrumento '
            'cierra externamente).')
    finally:
        close_quietly(fd)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_15_estado_closing_guardia_reentrada():
    """CLOSING no inicia un segundo cierre (verificado por reentrada real,
    sin mutar estado desde fuera)."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'n.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r15')
        res = c.get_resource(tok)
        real_close = mod.os.close
        calls = {'n': 0}

        def reentrant_close(fd_):
            if fd_ == fd:
                calls['n'] += 1
                if calls['n'] == 1:
                    # Reentrada durante el cierre iniciado: el recurso esta
                    # en CLOSING; el logger debe rechazar sin re-cerrar.
                    c.close_fd(fd, 'r15', token=tok)
            return real_close(fd_)

        mod.os.close = reentrant_close
        try:
            r = c.close_fd(fd, 'r15', token=tok)
        finally:
            mod.os.close = real_close
        assert r is None
        assert calls['n'] == 1, 'os.close invocado {0} veces'.format(calls['n'])
        assert res.state == mod.OwnedFdResource.STATE_CLOSED
        assert any('ya iniciado' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de cierre ya iniciado: {0}'.format(c.warnings)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ================================================================= bateria
def main():
    print("Pruebas unitarias C4-A CIERRE v0.2.7 — contrato estricto de propiedad "
          "(entorno no Android, sin audio real)")
    print("=" * 84)
    run('C4AC_01_cierre_normal_propietario', test_01_cierre_normal_propietario)
    run('C4AC_02_dos_aperturas_cada_token', test_02_dos_aperturas_mismo_archivo_cada_token)
    run('C4AC_03_doble_cierre', test_03_doble_cierre)
    run('C4AC_04_token_antiguo_reutilizacion', test_04_token_antiguo_tras_cierre_correcto_y_reutilizacion)
    run('C4AC_05_token_desconocido', test_05_token_desconocido)
    run('C4AC_06_descriptor_no_registrado', test_06_descriptor_no_registrado)
    run('C4AC_07_cierre_sin_token_nunca_cierra', test_07_cierre_sin_token_nunca_cierra)
    run('C4AC_08_error_simulado_os_close', test_08_error_simulado_os_close)
    run('C4AC_09_incierto_sin_segundo_intento', test_09_incierto_sin_segundo_intento)
    run('C4AC_10_soundfile_closefd_false', test_10_soundfile_closefd_false_cierre_por_propietario)
    run('C4AC_11_vista_solo_lectura', test_11_vista_solo_lectura)
    run('C4AC_12_auditoria_estatica_rutas_cierre', test_12_auditoria_estatica_rutas_cierre)
    run('C4AC_13_auditoria_runtime_rutas_cierre', test_13_auditoria_runtime_rutas_cierre)
    run_limitation('C4AC_14_violacion_mismo_archivo_limite',
                   test_14_violacion_mismo_archivo_limite)
    run('C4AC_15_estado_closing_guardia_reentrada', test_15_estado_closing_guardia_reentrada)
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
          "limite documentado del contrato (ver INFORME_CIERRE_C4_A.md).")
    for name, status, detail in RESULTS:
        if status not in ('PASS', 'EXPECTED_LIMITATION'):
            print("  REVISAR: {0} [{1}] {2}".format(name, status, detail))
    return 0 if (n_fail == 0 and n_err == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
