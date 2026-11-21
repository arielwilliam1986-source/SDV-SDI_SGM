#!/usr/bin/env python3
"""Pruebas unitarias aisladas C4-A v0.2.6 — propiedad y ciclo de vida de descriptores.

Se importa el instrumento audioinput_diag_termux.py v0.2.6 y se ejercita el
modelo de propiedad por recurso (OwnedFdResource + CloseErrorLogger) con los
casos obligatorios de la instruccion C4-A:

  1. Apertura y cierre normal.
  2. Dos aperturas independientes del mismo archivo.
  3. Dos recursos simultaneamente abiertos con tokens diferentes.
  4. Doble cierre del mismo recurso.
  5. Token obsoleto despues de un cierre confirmado.
  6. Intento de cierre de un descriptor no registrado.
  7. Fallo simulado de os.close().
  8. Resultado incierto despues de un error de cierre (no se reintenta).
  9. Reutilizacion del numero de FD tras un cierre externo:
     9a. contrato respetado (cierre solo por el propietario; token invalidado);
     9b. contrato violado detectable (tercero cierra; el diseno NO vuelve a
         cerrar con el token antiguo);
     9c. contrato violado indetectable (reutilizacion del MISMO numero para
         el MISMO archivo): LIMITE DE CONTRATO DOCUMENTADO — no existe
         deteccion portatil; la prueba verifica el comportamiento
         documentado (el cierre procede bajo contrato) y NO constituye una
         deteccion.

HONESTIDAD:
  - No Android/Termux, no audio real, no muestras del proyecto.
  - Los archivos temporales que abre el HARNESS para ejercitar el logger son
    recursos del propio harness: su limpieza (cierres directos en finally)
    es higiene de prueba y no forma parte del contrato del instrumento.
  - La prueba 9c documenta un limite: no se presenta como PASS una
    deteccion que no existe.
"""
import ast
import errno
import importlib.util
import os
import shutil
import sys
import tempfile
import traceback

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'audioinput_diag_termux.py')

_spec = importlib.util.spec_from_file_location('audioinput_diag_termux', TARGET)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

RESULTS = []
DETAILS = {}


def record(name, status, detail):
    RESULTS.append((name, status, detail))
    print("{0:4} {1:56} {2}".format(status, name, detail))


class NotReproducible(Exception):
    """Condicion del caso no reproducible en este entorno -> NOT_EXECUTED."""


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


def fresh_tmp():
    return tempfile.mkdtemp(prefix='c4a_ut_')


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


def make_file(d, name, content=b'x'):
    p = os.path.join(d, name)
    with open(p, 'wb') as fh:
        fh.write(content)
    return p


# ===================================================================== 1
def test_01_apertura_cierre_normal():
    """Apertura y cierre normal: OPEN -> CLOSED, un solo os.close."""
    d = fresh_tmp()
    try:
        p = make_file(d, 'a.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r1')
        assert tok is not None, 'register_fd no retorno token'
        res = c.get_resource(tok)
        assert res is not None and res.state == mod.OwnedFdResource.STATE_OPEN, \
            'estado inicial no es OPEN: {0}'.format(res and res.state)
        with CloseCounter(fd) as cc:
            err = c.close_fd(fd, 'r1', token=tok)
        assert err is None, 'cierre normal fallo: {0}'.format(err)
        assert res.state == mod.OwnedFdResource.STATE_CLOSED, \
            'estado final no es CLOSED: {0}'.format(res.state)
        assert res.close_result == 'ok', 'close_result: {0}'.format(res.close_result)
        assert cc.count == 1, 'os.close invocado {0} veces (esperado 1)'.format(cc.count)
        assert not fd_alive(fd), 'el descriptor sigue abierto tras el cierre'
        assert c.errors == [], 'errores inesperados: {0}'.format(c.errors)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 2
def test_02_dos_aperturas_mismo_archivo():
    """Dos aperturas independientes del mismo archivo; cerrar una no afecta la otra."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p = make_file(d, 'b.bin')
        fd1 = os.open(p, os.O_RDONLY)
        fd2 = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'ap1')
        t2 = c.register_fd(fd2, 'ap2')
        assert t1 != t2, 'los tokens deben ser distintos'
        r1 = c.get_resource(t1)
        r2 = c.get_resource(t2)
        assert r1.dev == r2.dev and r1.ino == r2.ino, \
            '(dev, ino) identicos (mismo archivo): la comparacion no distingue aperturas'
        assert c.close_fd(fd1, 'ap1', token=t1) is None, 'cierre de ap1 fallo'
        assert r1.state == mod.OwnedFdResource.STATE_CLOSED
        assert fd_alive(fd2), 'cerrar ap1 afecto a ap2 (apertura independiente violada)'
        assert c.close_fd(fd2, 'ap2', token=t2) is None, 'cierre de ap2 fallo'
        assert not fd_alive(fd1) and not fd_alive(fd2)
        assert c.errors == [], 'errores inesperados: {0}'.format(c.errors)
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 3
def test_03_dos_recursos_simultaneos_tokens_distintos():
    """Dos recursos simultaneamente abiertos con tokens diferentes (cierre inverso)."""
    d = fresh_tmp()
    fda = fdb = None
    try:
        pa = make_file(d, 'c.bin', b'aaa')
        pb = make_file(d, 'd.bin', b'bbb')
        fda = os.open(pa, os.O_RDONLY)
        fdb = os.open(pb, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        ta = c.register_fd(fda, 'recA')
        tb = c.register_fd(fdb, 'recB')
        assert ta != tb
        ra, rb = c.get_resource(ta), c.get_resource(tb)
        assert ra.state == rb.state == mod.OwnedFdResource.STATE_OPEN
        # Cierre en orden inverso al registro
        assert c.close_fd(fdb, 'recB', token=tb) is None
        assert rb.state == mod.OwnedFdResource.STATE_CLOSED
        assert ra.state == mod.OwnedFdResource.STATE_OPEN, 'estado de recA afectado'
        assert fd_alive(fda), 'recA fue cerrado por error'
        assert c.close_fd(fda, 'recA', token=ta) is None
        assert ra.state == mod.OwnedFdResource.STATE_CLOSED
        assert c.errors == [], 'errores inesperados: {0}'.format(c.errors)
    finally:
        close_quietly(fda)
        close_quietly(fdb)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 4
def test_04_doble_cierre():
    """Doble cierre del mismo recurso: aviso, os.close una sola vez."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'e.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r4')
        res = c.get_resource(tok)
        assert c.close_fd(fd, 'r4', token=tok) is None
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'r4', token=tok)
        assert r is None, 'doble cierre debe ser aviso, no error'
        assert cc.count == 0, 'os.close re-invocado en doble cierre'
        assert res.state == mod.OwnedFdResource.STATE_CLOSED, 'estado alterado'
        assert any('obsoleto' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de token obsoleto: {0}'.format(c.warnings)
        assert c.errors == [], 'doble cierre no debe ser error'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 5
def test_05_token_obsoleto_tras_cierre_confirmado():
    """Token obsoleto tras cierre confirmado: no cierra el recurso nuevo."""
    d = fresh_tmp()
    fd_old = fd_new = None
    try:
        p1 = make_file(d, 'f1.bin')
        p2 = make_file(d, 'f2.bin')
        fd_old = os.open(p1, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t_old = c.register_fd(fd_old, 'original')
        assert c.close_fd(fd_old, 'original', token=t_old) is None, 'cierre original fallo'
        # Nueva apertura (el numero puede o no reutilizarse)
        fd_new = os.open(p2, os.O_RDONLY)
        with CloseCounter(fd_new) as cc:
            r = c.close_fd(fd_new, 'recurso_nuevo', token=t_old)
        assert r is None, 'token obsoleto no debe cerrar ni fallar'
        assert cc.count == 0, 'el token obsoleto provojo os.close sobre el recurso nuevo'
        assert fd_alive(fd_new), 'el token obsoleto CERRO el recurso nuevo'
        assert any('obsoleto' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de token obsoleto: {0}'.format(c.warnings)
        assert c.errors == [], 'errores inesperados: {0}'.format(c.errors)
        # El recurso nuevo sigue manejable con su propio registro/cierre
        t_new = c.register_fd(fd_new, 'nuevo')
        assert c.close_fd(fd_new, 'nuevo', token=t_new) is None
        assert not fd_alive(fd_new)
    finally:
        close_quietly(fd_old)
        close_quietly(fd_new)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 6
def test_06_cierre_no_registrado():
    """Descriptor no registrado no se cierra mediante el logger; token desconocido tampoco."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'g.bin')
        fd = os.open(p, os.O_RDONLY)  # NUNCA se registra
        c = mod.CloseErrorLogger()
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'sin_registro')
        assert r is None, 'cierre sin registro debe ser aviso, no error'
        assert cc.count == 0, 'os.close invocado sobre descriptor no registrado'
        assert fd_alive(fd), 'el logger cerro un descriptor no registrado'
        assert any('no hay apertura registrada' in w.get('strerror', '')
                   for w in c.warnings), 'sin aviso: {0}'.format(c.warnings)
        # Token desconocido
        r2 = c.close_fd(fd, 'token_desconocido', token=99999)
        assert r2 is None and cc.count == 0 and fd_alive(fd), \
            'token desconocido provoco cierre'
        assert any('desconocido' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de token desconocido'
        assert c.errors == [], 'errores inesperados: {0}'.format(c.errors)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 7
def test_07_fallo_simulado_os_close():
    """Fallo simulado de os.close(): error devuelto y conservado; estado incierto."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'h.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r7')
        res = c.get_resource(tok)
        real_close = mod.os.close

        def bad_close(fd_):
            if fd_ == fd:
                raise OSError(errno.EIO, 'io simulado')
            return real_close(fd_)

        mod.os.close = bad_close
        try:
            r = c.close_fd(fd, 'r7', token=tok)
        finally:
            mod.os.close = real_close
        assert isinstance(r, OSError), 'el error de cierre debe devolverse: {0}'.format(r)
        assert r.errno == errno.EIO, 'errno incorrecto: {0}'.format(r.errno)
        assert len(c.errors) == 1, 'error de cierre no conservado: {0}'.format(c.errors)
        assert c.errors[0]['errno'] == errno.EIO
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN, \
            'estado tras error de cierre: {0}'.format(res.state)
        assert res.close_result == 'uncertain:close_errno={0}'.format(errno.EIO), \
            'close_result: {0}'.format(res.close_result)
        DETAILS['C4A_07_fallo_simulado_os_close'] = \
            'estado CLOSE_FAILED_UNCERTAIN; error conservado en errors y sink'
        # El sink global tambien conserva el error (propagacion posterior = C4-B)
        drained = mod._drain_close_error_sink()
        assert any(e.get('errno') == errno.EIO for e in drained), \
            'el sink global no conservo el error de cierre'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 8
def test_08_incierto_no_se_reintenta():
    """Resultado incierto tras error de cierre: NUNCA se reintenta automaticamente."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'i.bin')
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
            c.close_fd(fd, 'r8', token=tok)  # primer cierre: incierto
        finally:
            mod.os.close = real_close
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'r8', token=tok)
        assert r is None, 'el reintento debe ser aviso, no error'
        assert cc.count == 0, 'os.close RE-INVOCADO tras estado incierto'
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN, 'estado alterado'
        assert any('incierto' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de no reintento: {0}'.format(c.warnings)
        assert fd_alive(fd), 'el descriptor fue tocado tras estado incierto'
        DETAILS['C4A_08_incierto_no_se_reintenta'] = \
            'os.close no se invoca tras CLOSE_FAILED_UNCERTAIN (contador 0)'
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 9a
def test_09a_reutilizacion_contrato_respetado():
    """Contrato respetado: cierre solo por el propietario; token anterior invalidado."""
    d = fresh_tmp()
    fd1 = fd2 = None
    try:
        p1 = make_file(d, 'j1.bin')
        p2 = make_file(d, 'j2.bin')
        fd1 = os.open(p1, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        t1 = c.register_fd(fd1, 'propio')
        with CloseCounter(fd1) as cc:
            assert c.close_fd(fd1, 'propio', token=t1) is None
        assert cc.count == 1, 'el cierre del propietario invoca os.close una vez'
        assert c.get_resource(t1).state == mod.OwnedFdResource.STATE_CLOSED
        # Nueva apertura (posible reutilizacion del numero)
        fd2 = os.open(p2, os.O_RDONLY)
        reuso = (fd2 == fd1)
        with CloseCounter(fd2) as cc2:
            r = c.close_fd(fd2, 'posterior', token=t1)
        assert r is None, 'token invalidado no debe fallar'
        assert cc2.count == 0, 'el token invalidado provojo un cierre'
        assert fd_alive(fd2), 'el token invalidado cerro la apertura nueva'
        t2 = c.register_fd(fd2, 'nuevo_propio')
        assert c.close_fd(fd2, 'nuevo_propio', token=t2) is None
        DETAILS['C4A_09a_reutilizacion_contrato_respetado'] = \
            'cierre exclusivamente por el propietario (1 os.close); numero {0}; token anterior invalidado'.format(
                'reutilizado' if reuso else 'no reutilizado en esta ejecucion')
    finally:
        close_quietly(fd1)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 9b
def test_09b_reutilizacion_contrato_violado_detectable():
    """Contrato violado (tercero cierra): estado incierto; el diseno NO vuelve a cerrar."""
    d = fresh_tmp()
    fd = fd3 = None
    try:
        p = make_file(d, 'k.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'violado')
        res = c.get_resource(tok)
        assert res.state == mod.OwnedFdResource.STATE_OPEN
        # VIOLACION DEL CONTRATO: un tercero cierra el descriptor por via externa.
        os.close(fd)
        assert not fd_alive(fd), 'el cierre externo no se efectuo'
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'violado', token=tok)
        assert isinstance(r, OSError), 'se esperaba OSError por cierre externo'
        assert cc.count == 0, 'el diseno invoco os.close sobre un numero con contrato violado'
        assert res.state == mod.OwnedFdResource.STATE_UNCERTAIN, \
            'estado tras violacion detectable: {0}'.format(res.state)
        assert any('externamente' in e.get('strerror', '') for e in c.errors), \
            'anomalia no conservada: {0}'.format(c.errors)
        # El token antiguo NO puede cerrar una apertura posterior (ni con el
        # numero reutilizado ni con otro): no se reintenta.
        fd3 = os.open(p, os.O_RDONLY)
        with CloseCounter(fd3) as cc3:
            r2 = c.close_fd(fd3, 'posterior_violacion', token=tok)
        assert r2 is None and cc3.count == 0 and fd_alive(fd3), \
            'el token antiguo cerro una apertura posterior tras violacion detectada'
        DETAILS['C4A_09b_contrato_violado_detectable'] = \
            'EBADF detectado -> CLOSE_FAILED_UNCERTAIN; os.close nunca invocado por el diseno; token antiguo sin efecto'
    finally:
        close_quietly(fd)
        close_quietly(fd3)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 9c
def test_09c_reutilizacion_mismo_archivo_limite_contrato():
    """LIMITE DE CONTRATO (9c): reutilizacion del MISMO numero para el MISMO archivo.

    No existe mecanismo portatil de deteccion (fstat coincide). La prueba
    verifica el comportamiento DOCUMENTADO: el cierre del propietario
    procede (no hay deteccion que lo impida) — NO constituye una deteccion.
    """
    d = fresh_tmp()
    fd = fd2 = None
    try:
        p = make_file(d, 'm.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'ap_original')
        st_orig = os.fstat(fd)
        # VIOLACION INDETECTABLE: tercero cierra; se reabre el MISMO archivo.
        os.close(fd)
        fd2 = os.open(p, os.O_RDONLY)
        if fd2 != fd:
            raise NotReproducible(
                'el sistema no reutilizó el mismo numero de fd en esta ejecucion '
                '(original={0}, reabierta={1}); subcaso no reproducible'.format(fd, fd2))
        st_new = os.fstat(fd2)
        assert (st_new.st_dev, st_new.st_ino) == (st_orig.st_dev, st_orig.st_ino), \
            'la reapertura no es del mismo archivo'
        # El diseno NO puede distinguir las aperturas con fstat (documentado).
        with CloseCounter(fd2) as cc:
            r = c.close_fd(fd2, 'ap_original', token=tok)
        assert r is None, 'comportamiento documentado: el cierre procede bajo contrato'
        assert cc.count == 1, 'el cierre del propietario debe proceder una vez'
        assert c.get_resource(tok).state == mod.OwnedFdResource.STATE_CLOSED
        DETAILS['C4A_09c_mismo_archivo_limite_contrato'] = (
            'LIMITE DOCUMENTADO (no es deteccion): (dev,ino) coincide para el mismo '
            'archivo; no existe mecanismo portatil para distinguir las aperturas; '
            'el diseno procede con el cierre bajo el contrato de propiedad; la '
            'mitigacion es la encapsulacion (ningun otro componente cierra el fd)')
        # El registro refleja el cierre; el token queda invalidado en lo sucesivo.
        with CloseCounter(fd2) as cc2:
            r2 = c.close_fd(fd2, 'ap_original', token=tok)
        assert r2 is None and cc2.count == 0, 'token posterior al cierre re-invoco os.close'
    finally:
        close_quietly(fd)
        close_quietly(fd2)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 10 (soporte)
def test_10_estado_closing_no_duplica():
    """Guardia de reentrada: CLOSING no inicia un segundo cierre."""
    d = fresh_tmp()
    fd = None
    try:
        p = make_file(d, 'n.bin')
        fd = os.open(p, os.O_RDONLY)
        c = mod.CloseErrorLogger()
        tok = c.register_fd(fd, 'r10')
        res = c.get_resource(tok)
        # Simular cierre ya iniciado (sin tocar os.close real)
        res.state = mod.OwnedFdResource.STATE_CLOSING
        with CloseCounter(fd) as cc:
            r = c.close_fd(fd, 'r10', token=tok)
        assert r is None, 'CLOSING debe ser aviso, no error'
        assert cc.count == 0, 'os.close invocado con cierre ya iniciado'
        assert fd_alive(fd), 'el descriptor fue cerrado con estado CLOSING'
        assert any('ya iniciado' in w.get('strerror', '') for w in c.warnings), \
            'sin aviso de cierre ya iniciado: {0}'.format(c.warnings)
    finally:
        close_quietly(fd)
        shutil.rmtree(d, ignore_errors=True)


# ===================================================================== 11 (soporte, estático)
def test_11_estatico_contrato_en_t11_a_t16():
    """Estatico: T11-T16 registran propiedad y cierran asociado al token."""
    with open(TARGET, encoding='utf-8') as fh:
        src = fh.read()
    n_register = src.count('register_fd(')
    assert n_register >= 8, 'register_fd presente {0} veces (esperado >= 8)'.format(n_register)
    for pat in ["closer.close_fd(fd, 'fd')\n",
                "closer.close_fd(fd, 'fd_finally')\n",
                "closer.close_fd(dir_fd, 'dir_fd')\n",
                "closer.close_fd(dir_fd, 'dir_fd_finally')\n"]:
        assert pat not in src, 'cierre sin token presente: {0!r}'.format(pat)
    n_token = src.count('token=fd_token') + src.count('token=dir_fd_token')
    assert n_token >= 20, 'cierres asociados a token insuficientes: {0}'.format(n_token)
    # Sin silencio de errores de cierre (except OSError: pass), salvo _identity
    tree = ast.parse(src)
    bare_pass = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            is_oserror = (isinstance(node.type, ast.Name)
                          and node.type.id == 'OSError')
            if is_oserror and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                bare_pass += 1
    assert bare_pass <= 1, \
        'handlers except OSError: pass silenciosos: {0}'.format(bare_pass)
    DETAILS['C4A_11_estatico_contrato_en_t11_a_t16'] = \
        'register_fd={0} sitios; cierres con token={1}; sin except OSError: pass (salvo _identity)'.format(
            n_register, n_token)


# ===================================================================== Bateria
def main():
    print("Pruebas unitarias C4-A v0.2.6 — propiedad y ciclo de vida de descriptores "
          "(entorno no Android, sin audio real)")
    print("=" * 78)
    run('C4A_01_apertura_cierre_normal', test_01_apertura_cierre_normal)
    run('C4A_02_dos_aperturas_mismo_archivo', test_02_dos_aperturas_mismo_archivo)
    run('C4A_03_recursos_simultaneos_tokens_distintos',
        test_03_dos_recursos_simultaneos_tokens_distintos)
    run('C4A_04_doble_cierre', test_04_doble_cierre)
    run('C4A_05_token_obsoleto_tras_cierre_confirmado',
        test_05_token_obsoleto_tras_cierre_confirmado)
    run('C4A_06_cierre_no_registrado', test_06_cierre_no_registrado)
    run('C4A_07_fallo_simulado_os_close', test_07_fallo_simulado_os_close)
    run('C4A_08_incierto_no_se_reintenta', test_08_incierto_no_se_reintenta)
    run('C4A_09a_reutilizacion_contrato_respetado',
        test_09a_reutilizacion_contrato_respetado)
    run('C4A_09b_contrato_violado_detectable',
        test_09b_reutilizacion_contrato_violado_detectable)
    run('C4A_09c_mismo_archivo_limite_contrato',
        test_09c_reutilizacion_mismo_archivo_limite_contrato)
    run('C4A_10_estado_closing_no_duplica', test_10_estado_closing_no_duplica)
    run('C4A_11_estatico_contrato_en_t11_a_t16', test_11_estatico_contrato_en_t11_a_t16)
    print("=" * 78)
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
