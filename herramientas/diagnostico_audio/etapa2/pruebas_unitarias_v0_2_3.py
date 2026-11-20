#!/usr/bin/env python3
"""Pruebas unitarias aisladas para la corrección controlada v0.2.3 (C1/C4/C5).

Se importan las funciones corregidas del instrumento
audioinput_diag_termux.py v0.2.3 y se las ejerce en directorios temporales.
NO se ejecuta Android/Termux, NO se procesa audio, NO se usan muestras reales.

Resultados honestos: si una dependencia o condición no está disponible, la
prueba se registra como NOT_EXECUTED, nunca como PASS inventado.
"""
import ast
import errno
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
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
    print("{0:4} {1:55} {2}".format(status, name, detail))


def run(name, fn):
    try:
        fn()
        record(name, 'PASS', 'OK')
    except (ImportError, ModuleNotFoundError) as exc:
        record(name, 'NOT_EXECUTED', 'dependencia no disponible: {0}'.format(exc))
    except AssertionError as exc:
        record(name, 'FAIL', str(exc))
    except Exception:
        record(name, 'ERROR', traceback.format_exc().splitlines()[-1])


def fresh_tmp():
    d = tempfile.mkdtemp(prefix='v023_ut_')
    return d


# ---------------------------------------------------------------- C1
def test_safe_makedirs_exclusive_anchored():
    d = fresh_tmp()
    try:
        p = os.path.join(d, 'a', 'b', 'c')
        r = mod.safe_makedirs_exclusive_anchored(p)
        assert os.path.isdir(p), 'no se creo el directorio'
        assert str(r) == p, 'retorno inconsistente'
        # segundo intento: debe fallar con EEXIST (no reutiliza)
        try:
            mod.safe_makedirs_exclusive_anchored(p)
            assert False, 'no fallo ante directorio preexistente'
        except OSError as exc:
            assert exc.errno == errno.EEXIST, 'errno esperado EEXIST, fue {0}'.format(exc.errno)
        # permisos 0o700
        st = os.stat(p)
        assert (st.st_mode & 0o777) == 0o700, 'permisos {0:o} != 700'.format(st.st_mode & 0o777)
        # symlink en destino: rechazo
        link = os.path.join(d, 'lnk')
        os.symlink(p, link)
        try:
            mod.safe_makedirs_exclusive_anchored(link)
            assert False, 'no rechazo symlink en destino'
        except OSError as exc:
            assert exc.errno == errno.ELOOP, 'errno esperado ELOOP, fue {0}'.format(exc.errno)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_ensure_parents_anchored():
    d = fresh_tmp()
    try:
        p = os.path.join(d, 'x1', 'x2', 'x3')
        r = mod._ensure_parents_anchored(p)
        assert os.path.isdir(p), 'no se crearon los padres anclados'
        assert str(r) == p
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_safe_create_file_exclusive_anchored():
    d = fresh_tmp()
    try:
        f = os.path.join(d, 'out.bin')
        ok, err, close_err = mod.safe_create_file_exclusive_anchored(f, b'hello-v023')
        assert ok, 'creacion fallo: {0}'.format(err)
        assert close_err is None, 'close_err esperado None, fue {0}'.format(close_err)
        with open(f, 'rb') as fh:
            assert fh.read() == b'hello-v023', 'contenido incorrecto'
        # EEXIST si ya existe
        ok2, err2, _ = mod.safe_create_file_exclusive_anchored(f, b'x')
        assert not ok2 and err2 and 'ya existe' in err2, 'no rechazo archivo existente'
        # error de cierre conservado y propagado
        real_close = mod.os.close

        def bad_close(fd):
            if fd > 2:
                raise OSError(errno.EBADF, 'cerrado externamente')
            return real_close(fd)

        mod.os.close = bad_close
        try:
            f2 = os.path.join(d, 'out2.bin')
            ok3, err3, close3 = mod.safe_create_file_exclusive_anchored(f2, b'data')
            assert ok3, 'creacion con close fallido no reporta ok'
            assert close3 is not None and 'close' in close3, 'no se propago error de cierre'
        finally:
            mod.os.close = real_close
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _has_ocreat(node):
    """True si el nodo AST contiene la bandera O_CREAT."""
    for n in ast.walk(node):
        if isinstance(n, ast.Attribute) and n.attr == 'O_CREAT':
            return True
    return False


def test_no_path_fallback_static():
    import ast
    src = open(TARGET).read()
    tree = ast.parse(src)
    # C1: en codigo real (no docstrings), no debe quedar creacion por ruta
    # completa: os.mkdir(str(...)) siempre; os.open(str(...)) solo cuando
    # crea (O_CREAT). Las lecturas por ruta de fixtures (T11-T16, congeladas)
    # no son creaciones y no se tocan.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ('mkdir', 'open') and node.args:
                first = node.args[0]
                if (isinstance(first, ast.Call)
                        and isinstance(first.func, ast.Name)
                        and first.func.id == 'str'):
                    if node.func.attr == 'mkdir':
                        assert False, 'crea por ruta completa: os.mkdir(str(...))'
                    if _has_ocreat(node):
                        assert False, 'crea archivo por ruta completa: os.open(str(...))'
    # creaciones ancladas: mkdir/open con dir_fd como kwarg
    anchored_mkdir = 0
    anchored_open = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            kw = {k.arg for k in node.keywords}
            if node.func.attr == 'mkdir' and 'dir_fd' in kw:
                anchored_mkdir += 1
            if node.func.attr == 'open' and 'dir_fd' in kw:
                anchored_open += 1
    assert anchored_mkdir >= 2, 'no hay mkdir anclados (con dir_fd): {0}'.format(anchored_mkdir)
    assert anchored_open >= 3, 'no hay open anclados (con dir_fd): {0}'.format(anchored_open)


# ---------------------------------------------------------------- C4
def test_close_error_logger_identity():
    c = mod.CloseErrorLogger()
    d = fresh_tmp()
    try:
        fd = os.open(d, os.O_RDONLY)
        c.register_fd(fd, 'probe')
        r = c.close_fd(fd, 'probe')
        assert r is None, 'cierre normal debe retornar None'
        assert c.errors == [], 'no debe haber errores'
        # doble cierre del mismo recurso: aviso, no error
        r2 = c.close_fd(fd, 'probe')
        assert r2 is None, 'doble cierre debe retornar None'
        assert len(c.errors) == 0, 'doble cierre no debe ser error'
        assert len(c.warnings) == 1, 'doble cierre debe registrar aviso'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_close_error_logger_fd_reuse():
    import pathlib
    c = mod.CloseErrorLogger()
    d = pathlib.Path(fresh_tmp())
    try:
        f1 = d / 'file_a.bin'
        f2 = d / 'file_b.bin'
        f1.write_bytes(b'a')
        f2.write_bytes(b'bb')
        fd = os.open(str(f1), os.O_RDONLY)
        c.register_fd(fd, 'probe')
        os.close(fd)  # se cierra externamente; numero queda libre
        # abrir otro archivo distinto: si reutiliza el numero de descriptor,
        # la identidad (dev, ino) difiere y el logger NO debe cerrarlo.
        fd2 = os.open(str(f2), os.O_RDONLY)
        try:
            if fd2 == fd:
                r = c.close_fd(fd2, 'probe')
                assert r is None, 'cierre sobre fd reutilizado debe evitarse'
                assert len(c.errors) == 0, 'fd reutilizado no debe ser error'
                assert any('reutilizado' in w.get('strerror', '')
                           for w in c.warnings), \
                    'no se registro aviso de reutilizacion: {0}'.format(c.warnings)
                # el descriptor de f2 queda abierto (no cerrado por el logger):
                # verificar que el inodo de f2 sigue abierto en fd2
                st_f2 = os.fstat(fd2)
                assert os.stat(f2).st_ino == st_f2.st_ino, 'f2 fue cerrado por error'
            else:
                # numero distinto: cerrar fd2 por el logger es correcto
                r = c.close_fd(fd2, 'probe2')
                assert r is None
                assert len(c.errors) == 0
            # descriptor invalido sin registro: error conservado y devuelto
            r = c.close_fd(9999, 'ghost')
            assert isinstance(r, OSError), \
                'descriptor invalido debe devolver OSError, fue {0}'.format(r)
            assert any(e['label'] == 'ghost' for e in c.errors), 'error de cierre no conservado'
        finally:
            try:
                os.close(fd2)
            except OSError:
                pass
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_close_error_logger_sink_conservation():
    mod._drain_close_error_sink()  # limpiar lo acumulado por pruebas previas
    mod._record_close_error({"label": 'sink_test', "errno": errno.EBADF,
                             "strerror": "sink"})
    drained = mod._drain_close_error_sink()
    assert len(drained) == 1 and drained[0]['label'] == 'sink_test', \
        'sink no conserva errores'
    assert mod._drain_close_error_sink() == [], 'sink no se drena correctamente'


def test_close_error_logger_close_soundfile():
    c = mod.CloseErrorLogger()

    class FakeSf:
        def __init__(self, fail=False):
            self.fail = fail
            self.closed = False

        def close(self):
            if self.fail:
                raise OSError(errno.EIO, 'io')
            self.closed = True

    f = FakeSf()
    assert c.close_soundfile(f, 'sf1') is None and f.closed, 'cierre normal fallo'
    # doble cierre: aviso, no error
    c.close_soundfile(f, 'sf1')
    assert len(c.errors) == 0 and len(c.warnings) == 1, 'doble cierre sf no aviso'
    f2 = FakeSf(fail=True)
    c.close_soundfile(f2, 'sf2')
    assert len(c.errors) == 1 and c.errors[0]['label'] == 'sf2', \
        'error de cierre de SoundFile no conservado'


# ---------------------------------------------------------------- C5
def test_run_environment_interruption():
    d = fresh_tmp()
    try:
        # sin numpy/soundfile: FIXTURE_SPECS vacio para no tocar creacion real.
        # El bucle T15/T16 referencia las funciones a nivel de modulo, por
        # eso se patchean tambien test_t15_libsndfile_error_raised y
        # test_t16_fd_survives_closefd_false_failure.
        mod.FIXTURE_SPECS = []
        calls = {'n': 0}

        def fake_t15(np_, sf_, run_dir):
            calls['n'] += 1
            raise KeyboardInterrupt()

        def fake_t16(np_, sf_, run_dir):
            return ('PASS', 'no debe ejecutarse', [])

        real_tf = mod.TEST_FUNCTIONS
        real_t15 = mod.test_t15_libsndfile_error_raised
        real_t16 = mod.test_t16_fd_survives_closefd_false_failure
        mod.TEST_FUNCTIONS = {'T15': fake_t15, 'T16': fake_t16}
        mod.test_t15_libsndfile_error_raised = fake_t15
        mod.test_t16_fd_survives_closefd_false_failure = fake_t16
        try:
            results = []
            flag = [False]
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_dir = mod.run_environment(None, None, 'UT', d, results, 'ut1', flag)
            assert run_dir is not None, 'run_dir no creado'
            assert flag[0] is True, 'interrupt_flag no se setea en KI absorbida'
            t15 = [r for r in results if r['test'] == 'T15']
            assert len(t15) == 1 and t15[0]['status'] == mod.Result.ERROR, \
                'KI no se registra como ERROR: {0}'.format(t15)
            assert t15[0]['status'] != mod.Result.PASS, 'KI nunca PASS'
            t16 = [r for r in results if r['test'] == 'T16']
            assert len(t16) == 1 and t16[0]['status'] == mod.Result.NOT_EXECUTED, \
                'prueba posterior a KI no NOT_EXECUTED: {0}'.format(t16)
        finally:
            mod.TEST_FUNCTIONS = real_tf
            mod.test_t15_libsndfile_error_raised = real_t15
            mod.test_t16_fd_survives_closefd_false_failure = real_t16
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_run_environment_interruption_close_errors_conserved():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        mod.FIXTURE_SPECS = []
        mod._record_close_error({"label": 'ut_close_err', "errno": errno.EIO,
                                 "strerror": "simulado"})

        def fake_t15(np_, sf_, run_dir):
            raise KeyboardInterrupt()

        real_tf = mod.TEST_FUNCTIONS
        real_t15 = mod.test_t15_libsndfile_error_raised
        mod.TEST_FUNCTIONS = {'T15': fake_t15}
        mod.test_t15_libsndfile_error_raised = fake_t15
        try:
            results = []
            flag = [False]
            buf = io.StringIO()
            with redirect_stdout(buf):
                mod.run_environment(None, None, 'UT2', d, results, 'ut2', flag)
            t15 = [r for r in results if r['test'] == 'T15']
            assert len(t15) == 1, 'resultado T15 ausente'
            assert len(t15[0]['close_errors']) == 1, \
                'close_errors vacio tras KI con error acumulado: {0}'.format(t15[0])
        finally:
            mod.TEST_FUNCTIONS = real_tf
            mod.test_t15_libsndfile_error_raised = real_t15
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_main_interrupted_coherence_static():
    src = open(TARGET).read()
    # C5: main debe reconciliar interrupt_flag con interrupted
    assert 'if interrupt_flag[0] and not interrupted:' in src, \
        'main no reconcilia interrupt_flag con interrupted'
    assert 'interrupcion detectada via interrupt_flag' in src, \
        'main no registra mensaje de reconciliacion'
    assert 'env_close_errors = _drain_close_error_sink()' in src, \
        'main no drena el sink de errores de cierre'


def test_write_report_json_robust():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report.json'
        payload = {'v': 1, 'data': [1, 2, 3], 'text': 'ok'}
        ok, err, close_err = mod.write_report_json_robust(rp, payload)
        assert ok, 'escritura fallo: {0}'.format(err)
        assert close_err is None, 'close_err esperado None'
        with open(rp) as fh:
            got = json.load(fh)
        assert got == payload, 'contenido JSON incorrecto'
        # no debe quedar provisional
        tmp = rp.parent / (rp.name + '.tmp')
        assert not os.path.exists(tmp), 'queda provisional tras publicacion'
        # preexistente: no se sobrescribe
        with open(rp, 'w') as fh:
            fh.write('{"preexistente": true}')
        ok2, err2, _ = mod.write_report_json_robust(rp, {'otra': 1})
        assert not ok2, 'no rechaza informe preexistente'
        assert 'preexistente' in err2 or 'existe' in err2, \
            'error no explicito sobre preexistente: {0}'.format(err2)
        with open(rp) as fh:
            got2 = json.load(fh)
        assert got2 == {'preexistente': True}, 'informe preexistente fue sobrescrito'
        # provisional debe quedar tras intento fallido
        assert os.path.exists(tmp), 'provisional no queda tras intento fallido'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_write_report_json_robust_close_error_conserved():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report2.json'
        real_close = mod.os.close

        def bad_close(fd):
            if fd > 2:
                raise OSError(errno.EBADF, 'cerrado externamente')
            return real_close(fd)

        mod.os.close = bad_close
        try:
            ok, err, close_err = mod.write_report_json_robust(rp, {'a': 1})
            mod.os.close = real_close
            # el cierre fallido se conserva; la publicacion puede seguir
            assert ok, 'report publicado aun con close error'
            assert close_err is not None, 'close_err no conservado'
            assert os.path.exists(rp), 'report no publicado'
        finally:
            mod.os.close = real_close
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    print("Pruebas unitarias aisladas v0.2.3 (C1/C4/C5) — entorno no Android")
    print("=" * 72)
    run('C1_safe_makedirs_exclusive_anchored', test_safe_makedirs_exclusive_anchored)
    run('C1_ensure_parents_anchored', test_ensure_parents_anchored)
    run('C1_safe_create_file_exclusive_anchored', test_safe_create_file_exclusive_anchored)
    run('C1_no_path_fallback_static', test_no_path_fallback_static)
    run('C4_close_error_logger_identity', test_close_error_logger_identity)
    run('C4_close_error_logger_fd_reuse', test_close_error_logger_fd_reuse)
    run('C4_close_error_logger_sink_conservation', test_close_error_logger_sink_conservation)
    run('C4_close_error_logger_close_soundfile', test_close_error_logger_close_soundfile)
    run('C5_run_environment_interruption', test_run_environment_interruption)
    run('C5_run_environment_close_errors_conserved', test_run_environment_interruption_close_errors_conserved)
    run('C5_main_interrupted_coherence_static', test_main_interrupted_coherence_static)
    run('C5_write_report_json_robust', test_write_report_json_robust)
    run('C5_write_report_close_error_conserved', test_write_report_json_robust_close_error_conserved)
    print("=" * 72)
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
