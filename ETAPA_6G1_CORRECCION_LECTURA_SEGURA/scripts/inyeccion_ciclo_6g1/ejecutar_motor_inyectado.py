"""Ejecutor con inyección determinista de fallos del ciclo de vida 6G.1 (CV).

Uso:  python -B ejecutar_motor_inyectado.py ESCENARIO RUTA_MOTOR [args del motor]

Carga el motor como módulo (su propia carpeta en sys.path, de modo que importa
el MISMO `lectura_segura_6g1` que en producción), sustituye en memoria UN
punto del flujo según ESCENARIO y llama a `main()` exactamente como el bloque
`if __name__ == "__main__"` del motor (KeyboardInterrupt no capturada -> 130).
No modifica ningún archivo del motor ni del módulo.

En el instante de la inyección toma una instantánea (JSON en $SDVSDI_CV_SNAP)
del provisional: identidad, inventario con SHA-256 y SHA de analysis.json;
además siembra un archivo AJENO dentro del provisional y un destino
PREEXISTENTE `<final>_aborted/` con una marca, para verificar que nada ajeno
se elimina o sobrescribe y que ningún destino existente se reemplaza.

Escenarios:
  A1    write_reports() completa y luego KeyboardInterrupt.
  A2    write_reports() completa y luego RuntimeError.
  A2NA  como A2, pero antes de elevar se DESPLAZA el provisional y se coloca
        otro directorio vacío en su ruta (identidad no acreditable).
  A3    renameat2 indisponible (OSError ENOSYS) en la publicación segura.
  A4    apertura del Mix antes del DSP (ya creado el provisional): MixCambiado.
  A4b   apertura del Mix antes del DSP: OSError genérico.
  A5    guarda final: verificar() devuelve unchanged=False.
  A6    preparación inicial tras crear el provisional: init_tee() falla.
  A6b   creación del provisional: mkdir correcto y acreditación fallida.
  A7    como A2, pero la escritura de ABORT_6G1.json falla (OSError EIO en
        la creación exclusiva): el aborto no queda registrado de forma segura.
  E0    sin inyección (corrida feliz).
"""
import errno
import hashlib
import importlib.util
import json
import os
import sys

ESC = sys.argv[1]
MOTOR = os.path.abspath(sys.argv[2])
ARGS = sys.argv[3:]
SNAP = os.environ.get('SDVSDI_CV_SNAP', '')
OUT = os.environ.get('SDVSDI_CV_OUT', '')
AJENO_CONTENIDO = b'archivo ajeno sembrado por la prueba CV 6G.1\n'
MARCA_CONTENIDO = b'destino preexistente: no debe reemplazarse\n'

sys.path.insert(0, os.path.dirname(MOTOR))
import lectura_segura_6g1 as L  # noqa: E402  (mismo módulo que usará el motor)

_spec = importlib.util.spec_from_file_location('motor_cv_6g1', MOTOR)
M = importlib.util.module_from_spec(_spec)
sys.modules['motor_cv_6g1'] = M
_spec.loader.exec_module(M)

_estado = dict(escenario=ESC, instantanea=False, ki_escapo=False)


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _inventario(base):
    inv = {}
    for raiz, dirs, archivos in os.walk(base):
        dirs.sort()
        for a in sorted(archivos):
            p = os.path.join(raiz, a)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            inv[os.path.relpath(p, base)] = dict(bytes=os.path.getsize(p), sha256=_sha(p))
    return inv


def _provisional():
    cands = sorted(os.path.join(OUT, n) for n in os.listdir(OUT) if n.endswith('_partial'))
    return cands[0] if len(cands) == 1 else None


def instantanea(sembrar=True):
    """Instantánea del provisional en el punto de inyección (una sola vez)."""
    if _estado['instantanea']:
        return
    prov = _provisional()
    datos = dict(escenario=ESC, provisional=prov)
    if prov:
        st = os.lstat(prov)
        datos['identidad'] = [st.st_dev, st.st_ino]
        datos['inventario'] = _inventario(prov)
        an = os.path.join(prov, 'analysis.json')
        datos['analysis_sha256'] = _sha(an) if os.path.isfile(an) else None
        final = prov[:-len('_partial')]
        datos['final'] = final
        if sembrar:
            with open(os.path.join(prov, 'AJENO_CV.txt'), 'wb') as f:
                f.write(AJENO_CONTENIDO)
            os.mkdir(final + '_aborted', 0o700)
            with open(os.path.join(final + '_aborted', 'MARCA_DESTINO.txt'), 'wb') as f:
                f.write(MARCA_CONTENIDO)
            st_d = os.lstat(final + '_aborted')
            datos['destino_preexistente'] = dict(
                ruta=final + '_aborted', identidad=[st_d.st_dev, st_d.st_ino],
                marca_sha256=hashlib.sha256(MARCA_CONTENIDO).hexdigest())
            datos['ajeno_sha256'] = hashlib.sha256(AJENO_CONTENIDO).hexdigest()
    _estado['instantanea'] = True
    _estado['datos'] = datos
    _guardar()


def _guardar():
    if SNAP:
        with open(SNAP, 'w', encoding='utf-8') as f:
            json.dump(_estado, f, indent=2)


# ----------------------------------------------------------------- escenarios
if ESC in ('A1', 'A2', 'A2NA', 'A7'):
    _orig_wr = M.write_reports

    def _wr(*a, **k):
        r = _orig_wr(*a, **k)
        instantanea()
        if ESC == 'A1':
            raise KeyboardInterrupt()
        if ESC == 'A2NA':
            prov = _estado['datos']['provisional']
            os.rename(prov, prov + '.desplazado')
            os.mkdir(prov, 0o700)
            st = os.lstat(prov)
            _estado['datos']['sustituto_identidad'] = [st.st_dev, st.st_ino]
            _estado['datos']['desplazado'] = prov + '.desplazado'
            _guardar()
        if ESC == 'A7':
            # Desde aquí, la creación de ABORT_6G1.json falla (E/S); el resto
            # de aperturas no se altera.
            _orig_open = os.open

            def _open_abort_falla(path, flags, *a, **k):
                if (os.path.basename(str(path)) == 'ABORT_6G1.json'
                        and flags & os.O_CREAT):
                    _estado['abort_escritura_fallida'] = True
                    _guardar()
                    raise OSError(errno.EIO, 'inyeccion CV A7: escritura de ABORT_6G1.json fallida')
                return _orig_open(path, flags, *a, **k)
            os.open = _open_abort_falla
        raise RuntimeError('inyeccion CV %s: excepcion general tras salidas parciales' % ESC)
    M.write_reports = _wr

elif ESC == 'A3':
    def _renameat2_indisponible(origen, destino):
        instantanea()
        raise OSError(errno.ENOSYS, 'inyeccion CV A3: renameat2 indisponible')
    L._renameat2_noreplace = _renameat2_indisponible

elif ESC in ('A4', 'A4b'):
    _orig_abrir = M._abrir_mix_6g1

    def _abrir_falla(*a, **k):
        # Sólo la apertura del DSP (con el provisional ya creado) falla; la
        # lectura previa de analyze_guide_scale() usa la apertura real.
        if _provisional() is None:
            return _orig_abrir(*a, **k)
        instantanea()
        if ESC == 'A4':
            raise L.MixCambiado('inyeccion CV A4: Mix sustituido antes del DSP')
        raise OSError(errno.EIO, 'inyeccion CV A4b: fallo de E/S al abrir el Mix')
    M._abrir_mix_6g1 = _abrir_falla

elif ESC == 'A5':
    def _verificar_falso(self, *a, **k):
        instantanea()
        return dict(unchanged=False, reason='inyeccion CV A5: guarda final no superada')
    L.MixHandle.verificar = _verificar_falso

elif ESC == 'A6':
    def _init_tee_falla(path):
        instantanea()
        raise OSError(errno.EACCES, 'inyeccion CV A6: no se pudo crear el log', path)
    M.init_tee = _init_tee_falla

elif ESC == 'A6b':
    def _crear_sin_acreditar(padre, nombre):
        os.mkdir(os.path.join(os.path.abspath(padre), nombre), 0o700)
        instantanea()
        raise RuntimeError('inyeccion CV A6b: acreditacion del provisional fallida')
    M._crear_y_acreditar_dir_6g1 = _crear_sin_acreditar

elif ESC != 'E0':
    raise SystemExit('escenario desconocido: %s' % ESC)


# Retorno REAL de run_experiment() (contrato B): se registra antes de que
# main() lo interprete.
_orig_run = M.run_experiment


def _run_registrado(*a, **k):
    r = _orig_run(*a, **k)
    try:
        cod, ruta = r
    except Exception:
        cod, ruta = None, r
    _estado['retorno_run_experiment'] = dict(
        codigo=cod, ruta=repr(ruta),
        ruta_es_directorio=isinstance(ruta, str) and os.path.isdir(ruta))
    _guardar()
    return r


M.run_experiment = _run_registrado


if __name__ == '__main__':
    sys.argv = [MOTOR] + ARGS
    try:
        codigo = M.main()
    except KeyboardInterrupt:
        _estado['ki_escapo'] = True
        _guardar()
        codigo = getattr(M, 'EXIT_ABORTED', 130)
    _estado['codigo_main'] = codigo
    _guardar()
    sys.exit(codigo)
