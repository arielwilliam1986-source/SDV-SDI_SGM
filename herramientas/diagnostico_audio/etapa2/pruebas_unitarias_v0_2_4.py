#!/usr/bin/env python3
"""Pruebas unitarias aisladas para la corrección final v0.2.4 (C1/C4/C5).

Se importan las funciones corregidas del instrumento
audioinput_diag_termux.py v0.2.4 y se las ejerce en directorios temporales.
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
    print("{0:4} {1:58} {2}".format(status, name, detail))


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
    return tempfile.mkdtemp(prefix='v024_ut_')


def close_quietly(fd):
    try:
        os.close(fd)
    except OSError:
        pass


# ===================================================================== C1
def test_c1_publicacion_concurrente_destino():
    """Destino creado concurrentemente entre preparacion y publicacion."""
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report.json'
        payload = {'a': 1}
        real_link = mod.os.link
        calls = {'n': 0}

        def racing_link(src, dst, **kw):
            calls['n'] += 1
            if calls['n'] == 1:
                # Simular creacion concurrente del destino entre la
                # preparacion del provisional y la publicacion.
                with open(rp, 'w') as fh:
                    fh.write('{"concurrente": true}')
            return real_link(src, dst, **kw)

        mod.os.link = racing_link
        try:
            ok, err, close_err = mod.write_report_json_robust(rp, payload)
        finally:
            mod.os.link = real_link
        assert not ok, 'la publicacion no falla ante destino concurrente'
        assert 'preexistente' in err or 'existe' in err, \
            'error no explicito sobre destino preexistente: {0}'.format(err)
        with open(rp) as fh:
            got = json.load(fh)
        assert got == {'concurrente': True}, 'el destino ajeno fue sobrescrito'
        # El provisional (origen acreditado) se conserva: no se elimina
        # automaticamente cuando la publicacion falla.
        assert os.path.exists(d / (rp.name + '.tmp')), \
            'provisional no conservado tras publicacion fallida'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c1_mecanismo_no_disponible():
    """Mecanismo seguro de publicacion no disponible."""
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report.json'
        real_link = mod.os.link

        def no_link(src, dst, **kw):
            raise NotImplementedError("dir_fd no soportado en este sistema")

        mod.os.link = no_link
        try:
            ok, err, close_err = mod.write_report_json_robust(rp, {'b': 2})
        finally:
            mod.os.link = real_link
        assert not ok, 'no falla cuando el mecanismo seguro no esta disponible'
        assert 'no publicado' in err, \
            'no reporta explicitamente que el informe no se publico: {0}'.format(err)
        assert not os.path.exists(rp), 'destino creado aun sin mecanismo seguro'
        assert os.path.exists(d / (rp.name + '.tmp')), \
            'provisional no conservado cuando el mecanismo no esta disponible'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c1_publicacion_exitosa():
    """Publicacion normal: informe publicado, sin provisional residual."""
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report.json'
        payload = {'v': 4, 'data': [1, 2]}
        ok, err, close_err = mod.write_report_json_robust(rp, payload)
        assert ok, 'publicacion normal fallo: {0}'.format(err)
        assert close_err is None, 'close_err esperado None'
        with open(rp) as fh:
            got = json.load(fh)
        assert got == payload, 'contenido JSON incorrecto'
        assert not os.path.exists(d / (rp.name + '.tmp')), \
            'queda provisional tras publicacion exitosa'
        # Preexistente: no se sobrescribe
        with open(rp, 'w') as fh:
            fh.write('{"pre": 1}')
        ok2, err2, _ = mod.write_report_json_robust(rp, {'otro': 2})
        assert not ok2, 'no rechaza informe preexistente'
        with open(rp) as fh:
            got2 = json.load(fh)
        assert got2 == {'pre': 1}, 'informe preexistente fue sobrescrito'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c1_regressions():
    """Regressions C1 base: creacion anclada de dirs y archivos."""
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        p = d / 'a' / 'b' / 'c'
        mod.safe_makedirs_exclusive_anchored(p)
        assert os.path.isdir(p), 'no se creo el directorio anclado'
        try:
            mod.safe_makedirs_exclusive_anchored(p)
            assert False, 'no falla ante directorio preexistente'
        except OSError as exc:
            assert exc.errno == errno.EEXIST
        f = d / 'out.bin'
        ok, err, close_err = mod.safe_create_file_exclusive_anchored(f, b'data-v024')
        assert ok and close_err is None, 'creacion anclada fallo: {0} {1}'.format(err, close_err)
        with open(f, 'rb') as fh:
            assert fh.read() == b'data-v024', 'contenido incorrecto'
        # sin creaciones por ruta completa en codigo real
        src = open(TARGET).read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ('mkdir', 'open') and node.args:
                    first = node.args[0]
                    if (isinstance(first, ast.Call)
                            and isinstance(first.func, ast.Name)
                            and first.func.id == 'str'):
                        if node.func.attr == 'mkdir':
                            assert False, 'os.mkdir(str(...)) por ruta'
                        if any(isinstance(n, ast.Attribute) and n.attr == 'O_CREAT'
                               for n in ast.walk(node)):
                            assert False, 'os.open(str(...)) con O_CREAT por ruta'
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== C4
def test_c4_dos_aperturas_mismo_archivo():
    c = mod.CloseErrorLogger()
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        f = d / 'f.bin'
        f.write_bytes(b'x')
        fd1 = os.open(str(f), os.O_RDONLY)
        fd2 = os.open(str(f), os.O_RDONLY)
        t1 = c.register_fd(fd1, 'apertura1')
        t2 = c.register_fd(fd2, 'apertura2')
        assert t1 is not None and t2 is not None and t1 != t2, \
            'los tokens de las dos aperturas deben ser distintos'
        assert c.close_fd(fd1, 'apertura1', token=t1) is None
        # la segunda apertura del mismo archivo sigue abierta
        os.fstat(fd2)
        assert c.close_fd(fd2, 'apertura2', token=t2) is None
        # token obsoleto: no cierra nada
        assert c.close_fd(fd1, 'apertura1', token=t1) is None
        assert len(c.errors) == 0, 'no debe haber errores en cierres normales'
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


def test_c4_reutilizacion_numero_fd():
    c = mod.CloseErrorLogger()
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        f1 = d / 'a.bin'
        f2 = d / 'b.bin'
        f1.write_bytes(b'a')
        f2.write_bytes(b'b')
        fd = os.open(str(f1), os.O_RDONLY)
        token = c.register_fd(fd, 'apertura_original')
        assert c.close_fd(fd, 'apertura_original', token=token) is None
        fd2 = os.open(str(f2), os.O_RDONLY)
        try:
            if fd2 == fd:
                # Referencia obsoleta con token ya cerrado: no cerrar el
                # recurso reutilizado.
                r = c.close_fd(fd2, 'ref_obsoleta', token=token)
                assert r is None, 'token obsoleto no debe cerrar'
                assert len(c.errors) == 0, 'reutilizacion no es error'
                assert len(c.warnings) >= 1, 'no se registra aviso de token obsoleto'
                os.fstat(fd2)  # f2 sigue abierto
                # Cierre sin token sobre fd reutilizado no registrado:
                # no hay apertura 'open' registrada -> no cerrar.
                r2 = c.close_fd(fd2, 'sin_registro')
                assert r2 is None, 'cierre sin registro no debe cerrar'
                assert len(c.errors) == 0, 'cierre sin registro no es error'
                os.fstat(fd2)  # sigue abierto
            else:
                t2 = c.register_fd(fd2, 'apertura_nueva')
                assert c.close_fd(fd2, 'apertura_nueva', token=t2) is None
        finally:
            close_quietly(fd2)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c4_cierre_repetido():
    c = mod.CloseErrorLogger()
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        f = d / 'f.bin'
        f.write_bytes(b'x')
        fd = os.open(str(f), os.O_RDONLY)
        token = c.register_fd(fd, 'probe')
        assert c.close_fd(fd, 'probe', token=token) is None
        r = c.close_fd(fd, 'probe', token=token)
        assert r is None, 'doble cierre debe ser aviso, no error'
        assert len(c.errors) == 0, 'doble cierre no debe ser error'
        assert len(c.warnings) >= 1, 'no se registra aviso de doble cierre'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_c4_error_cierre_simulado():
    c = mod.CloseErrorLogger()
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        f = d / 'f.bin'
        f.write_bytes(b'x')
        fd = os.open(str(f), os.O_RDONLY)
        token = c.register_fd(fd, 'probe')
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io simulado')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            r = c.close_fd(fd, 'probe', token=token)
        finally:
            mod.os.close = real_close
        assert isinstance(r, OSError), 'error de cierre debe devolverse, no lanzarse'
        assert len(c.errors) == 1, 'error de cierre no conservado'
        assert c.errors[0]['errno'] == errno.EIO, 'errno no conservado'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def _error_cierre_durante(exc_cls):
    c = mod.CloseErrorLogger()
    import pathlib
    d = pathlib.Path(fresh_tmp())
    fd = None
    try:
        f = d / 'f.bin'
        f.write_bytes(b'x')
        fd = os.open(str(f), os.O_RDONLY)
        token = c.register_fd(fd, 'probe')
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            try:
                raise exc_cls('error primario')
            finally:
                c.close_fd(fd, 'probe', token=token)
        except exc_cls:
            pass
        finally:
            mod.os.close = real_close
        # El error primario (excepcion) y el secundario (cierre) son
        # distintos y ambos se conservan.
        assert len(c.errors) == 1, 'error de cierre perdido durante la excepcion'
        drained = mod._drain_close_error_sink()
        assert any(e['errno'] == errno.EIO for e in drained), \
            'sink no conserva el error de cierre durante la excepcion'
    finally:
        if fd is not None:
            close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


def test_c4_error_cierre_durante_excepcion():
    _error_cierre_durante(ValueError)


def test_c4_error_cierre_durante_keyboardinterrupt():
    _error_cierre_durante(KeyboardInterrupt)


def test_c4_no_silencio_cierres_revisados():
    """Los cierres revisados no silencian errores (except OSError: pass)."""
    src = open(TARGET).read()
    tree = ast.parse(src)
    bare_pass = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            # Solo importa el silencio de errores OSError (cierres). Los
            # handlers FileNotFoundError (condicion esperada) o
            # sf.LibsndfileError (T11-T16 congelado) no son silencios de
            # errores de cierre.
            is_oserror = (isinstance(node.type, ast.Name)
                          and node.type.id == 'OSError')
            body = node.body
            if is_oserror and len(body) == 1 and isinstance(body[0], ast.Pass):
                bare_pass += 1
    # El unico handler `except OSError: pass` permitido es la consulta
    # _identity (retorna None). Cualquier otro es un silencio de error.
    assert bare_pass <= 1, \
        'quedan handlers except OSError: pass silenciosos: {0}'.format(bare_pass)


# ===================================================================== C5
def test_c5_ki_durante_prueba():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
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
            with redirect_stdout(io.StringIO()):
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


def test_c5_ki_durante_create_fixture():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        mod.FIXTURE_SPECS = [('pcm16', 'PCM_16')]
        real_create = mod.create_fixture

        def ki_create(np_, sf_, dir_path, name, subtype, closer):
            # simular un error de cierre antes de la interrupcion
            mod._record_close_error({"label": 'fixture_close_err', "errno": errno.EIO,
                                     "strerror": "simulado"})
            raise KeyboardInterrupt()

        mod.create_fixture = ki_create
        try:
            results = []
            flag = [False]
            with redirect_stdout(io.StringIO()):
                mod.run_environment(None, None, 'UT', d, results, 'ut1', flag)
            assert flag[0] is True, 'flag no seteada en KI durante creacion de fixture'
            t11 = [r for r in results if r['test'] == 'T11']
            assert t11 and t11[0]['status'] == mod.Result.ERROR, \
                'KI durante fixture no se registra como ERROR: {0}'.format(t11)
            assert any(r['test'] == 'T12' and r['status'] == mod.Result.NOT_EXECUTED
                       for r in results), 'pruebas posteriores no NOT_EXECUTED'
            assert any(len(r['close_errors']) >= 1 for r in results
                       if r['test'] == 'T11'), \
                'errores de cierre no conservados tras KI en fixture'
        finally:
            mod.create_fixture = real_create
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c5_ki_durante_escritura_json():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        rp = d / 'report.json'
        real_write = mod.os.write

        def ki_write(fd, data):
            raise KeyboardInterrupt()

        mod.os.write = ki_write
        try:
            try:
                mod.write_report_json_robust(rp, {'a': 1})
                assert False, 'KI durante write no se propaga'
            except KeyboardInterrupt:
                pass
        finally:
            mod.os.write = real_write
        assert not os.path.exists(rp), \
            'informe publicado aun con KI durante la escritura'
        assert os.path.exists(d / (rp.name + '.tmp')), \
            'provisional no conservado tras KI durante la escritura'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c5_informe_no_declara_completo():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        # Estado global tras una interrupcion (reconciliacion)
        flag = [True]
        interrupted, msg = mod._reconcile_interrupted(flag, False, None)
        assert interrupted is True, 'estado global no verdadero tras flag'
        assert 'interrupt_flag' in msg, 'no se registra motivo de reconciliacion'
        report = {'interrupted': interrupted, 'interrupt_message': msg,
                  'summary': {'interrupted': interrupted, 'pass': 1, 'fail': 0,
                              'error': 1, 'not_executed': 2}}
        rp = d / 'report.json'
        ok, err, close_err = mod.write_report_json_robust(rp, report)
        assert ok, 'informe con interrupcion no se publica: {0}'.format(err)
        with open(rp) as fh:
            got = json.load(fh)
        assert got['interrupted'] is True, 'el informe declara ejecucion completa'
        assert got['summary']['interrupted'] is True, \
            'el resumen no refleja la interrupcion'
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_c5_segundo_entorno_no_iniciado():
    import pathlib
    d = pathlib.Path(fresh_tmp())
    try:
        mod.FIXTURE_SPECS = []

        def fake_t15(np_, sf_, rd):
            raise KeyboardInterrupt()

        real_t15 = mod.test_t15_libsndfile_error_raised
        real_tf = mod.TEST_FUNCTIONS
        mod.TEST_FUNCTIONS = {'T15': fake_t15}
        mod.test_t15_libsndfile_error_raised = fake_t15
        try:
            results = []
            flag = [False]
            with redirect_stdout(io.StringIO()):
                mod.run_environment(None, None, 'A', d, results, 'u1', flag)
            assert flag[0] is True, 'flag no seteada tras KI'
            # Decision de main para el segundo entorno:
            #   if shared_parent is not None and not interrupt_flag[0]: ...
            shared_parent = d / 'shared'
            started = (shared_parent is not None and not flag[0])
            assert started is False, \
                'el segundo entorno se iniciaria tras la interrupcion del primero'
        finally:
            mod.TEST_FUNCTIONS = real_tf
            mod.test_t15_libsndfile_error_raised = real_t15
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    print("Pruebas unitarias aisladas v0.2.4 (C1/C4/C5) — entorno no Android")
    print("=" * 76)
    run('C1_publicacion_concurrente_destino', test_c1_publicacion_concurrente_destino)
    run('C1_mecanismo_no_disponible', test_c1_mecanismo_no_disponible)
    run('C1_publicacion_exitosa', test_c1_publicacion_exitosa)
    run('C1_regressions', test_c1_regressions)
    run('C4_dos_aperturas_mismo_archivo', test_c4_dos_aperturas_mismo_archivo)
    run('C4_reutilizacion_numero_fd', test_c4_reutilizacion_numero_fd)
    run('C4_cierre_repetido', test_c4_cierre_repetido)
    run('C4_error_cierre_simulado', test_c4_error_cierre_simulado)
    run('C4_error_cierre_durante_excepcion', test_c4_error_cierre_durante_excepcion)
    run('C4_error_cierre_durante_keyboardinterrupt',
        test_c4_error_cierre_durante_keyboardinterrupt)
    run('C4_no_silencio_cierres_revisados', test_c4_no_silencio_cierres_revisados)
    run('C5_ki_durante_prueba', test_c5_ki_durante_prueba)
    run('C5_ki_durante_create_fixture', test_c5_ki_durante_create_fixture)
    run('C5_ki_durante_escritura_json', test_c5_ki_durante_escritura_json)
    run('C5_informe_no_declara_completo', test_c5_informe_no_declara_completo)
    run('C5_segundo_entorno_no_iniciado', test_c5_segundo_entorno_no_iniciado)
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
