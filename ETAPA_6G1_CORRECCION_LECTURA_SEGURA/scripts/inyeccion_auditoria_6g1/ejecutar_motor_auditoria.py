#!/usr/bin/env python3
"""Arnés de inyección 6G.1 / AI (auditoría integral: cierre real de wrappers y
retención de abortos).

Uso (cwd = carpeta de los motores):
    python -B ejecutar_motor_auditoria.py ESC MOTOR [args del motor...]

Escenarios (B, C y E se arman tras write_reports(); A y D no requieren armado):
  A1  primer close() de un escritor WAV bajo la salida (finalización normal)
      eleva OSError SIN cerrar el archivo.
  A2  ídem, pero el archivo se cierra físicamente y DESPUÉS se eleva (es el
      comportamiento real de soundfile cuando sf_close devuelve error:
      `_file=None` y luego la excepción).
  B1  el cierre interno del lector del Mix (SoundFile de MixHandle) en la
      guarda final eleva OSError SIN cerrar.
  B2  ídem, cerrando físicamente antes de elevar.
  C1  close() del archivo de engine_log.txt (Tee) en el camino normal eleva
      OSError SIN cerrar el archivo.
  C2  ídem, cerrando físicamente antes de elevar.
  D1  la apertura del SEGUNDO escritor (SDI.wav) de un CandidateRunner falla
      después de abrir el primero (SDV.wav).
  D2  D1 + el primer cierre del escritor SDV.wav huérfano eleva SIN cerrar.
  E1  tras write_reports() (masks/ ya generadas) se altera un byte de la COPIA
      del Mix en la carpeta de trabajo: la guarda final de integridad falla.
      (Los fixtures no se tocan: el manifiesto apunta a la copia.)

Instrumentación (sólo en memoria; ningún motor ni módulo se modifica):
  * gc.disable() al inicio: el recolector cíclico no actúa en todo el
    proceso; cualquier liberación observada es explícita.
  * subclase de soundfile.SoundFile: registro de instancias, frames y eventos
    ordenados de cierre; puntos de inyección A, B, D.
  * proxy del archivo de Tee (C) instalado tras init_tee().
  * np.lib.format.open_memmap: referencias débiles (estado en /proc).
  * envolturas de write_reports (armado), _preparar_aborto_6g1 (informe de
    cierre), _abortar_corrida_6g1 (resultado), abortar_6g1 (fotografías de
    entrada/salida) y publicar_dir_6g1 (eventos de traslado/publicación).
Escribe todo en JSON en $SDVSDI_AI_SNAP.
"""
import gc
gc.disable()                                   # noqa: E402  (antes de todo)

import hashlib            # noqa: E402
import importlib.util     # noqa: E402
import json               # noqa: E402
import os                 # noqa: E402
import sys                # noqa: E402
import time               # noqa: E402
import weakref            # noqa: E402

ESC = sys.argv[1]
MOTOR = os.path.abspath(sys.argv[2])
ARGS = sys.argv[3:]
SNAP = os.environ['SDVSDI_AI_SNAP']
OUT = os.path.realpath(os.environ['SDVSDI_AI_OUT'])
ENTRADAS = [os.path.realpath(p) for p in
            os.environ.get('SDVSDI_AI_ENTRADAS', '').split(os.pathsep) if p]
MIX_COPIA = os.environ.get('SDVSDI_AI_MIX')
if ESC not in ('A1', 'A2', 'B1', 'B2', 'C1', 'C2', 'D1', 'D2', 'E1'):
    raise SystemExit('escenario desconocido: %s' % ESC)

EVENTOS = []
ESTADO = dict(escenario=ESC, eventos=EVENTOS, fotos={}, inyeccion=None,
              armado=False, gc_deshabilitado_al_inicio=not gc.isenabled(),
              # colecciones hechas por el arranque del intérprete ANTES de
              # gc.disable(): referencia para medir las posteriores
              gc_colecciones_al_deshabilitar=[g['collections'] for g in gc.get_stats()],
              gc_colecciones_posteriores=[])


def _gc_callback(fase, info):
    # cualquier colección posterior a gc.disable() (sólo posible con un
    # gc.collect() explícito) queda registrada con su origen
    if fase == 'start':
        import traceback
        ESTADO['gc_colecciones_posteriores'].append(dict(
            generacion=info.get('generation'),
            origen=traceback.format_stack(limit=12)[:-1]))


gc.callbacks.append(_gc_callback)


def ev(tipo, **datos):
    EVENTOS.append(dict(n=len(EVENTOS) + 1, t=time.monotonic(), tipo=tipo, **datos))


def guardar():
    with open(SNAP, 'w', encoding='utf-8') as f:
        json.dump(ESTADO, f, indent=2, default=str)


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def inventario(d):
    res = {}
    for raiz, _dirs, archivos in os.walk(d):
        for a in archivos:
            p = os.path.join(raiz, a)
            if os.path.isfile(p) and not os.path.islink(p):
                res[os.path.relpath(p, d)] = _sha(p)
    return res


def provisional():
    ps = [d for d in os.listdir(OUT) if d.endswith('_partial')]
    return os.path.join(OUT, ps[0]) if ps else None


def registrar_inyeccion(detalle):
    """Primera inyección: fotografía plana del provisional."""
    if ESTADO['inyeccion'] is not None:
        return
    prov = provisional()
    st = os.lstat(prov) if prov else None
    ESTADO['inyeccion'] = dict(
        detalle=detalle, provisional=os.path.realpath(prov) if prov else None,
        final=os.path.realpath(prov)[:-len('_partial')] if prov else None,
        identidad=[st.st_dev, st.st_ino] if st else None,
        archivos=inventario(prov) if prov else {}, n_evento=len(EVENTOS) + 1)
    ev('inyeccion', escenario=ESC, detalle=detalle)
    guardar()


# ------------------------------------------------------------ instrumentación
import numpy as np            # noqa: E402
import soundfile              # noqa: E402

_SF = soundfile.SoundFile
REG_SF = []


def _escritura(modo):
    return 'w' in modo or '+' in modo


class SoundFileInstr(_SF):
    def __init__(self, file, mode='r', *a, **k):
        ruta = os.path.realpath(str(file)) if isinstance(file, (str, os.PathLike)) else None
        if (ESC in ('D1', 'D2') and _escritura(mode) and ruta
                and ruta.endswith('SDI.wav') and ruta.startswith(OUT + os.sep)
                and ESTADO['inyeccion'] is None):
            previos = [s for s in REG_SF if _escritura(s._cr_modo) and not s.closed
                       and s._cr_ruta == os.path.join(os.path.dirname(ruta),
                                                      os.path.basename(ruta)[:-7] + 'SDV.wav')]
            if ESC == 'D2' and previos:
                previos[-1]._cr_falla_cierre = 'antes'
            registrar_inyeccion(dict(tipo='apertura_segundo_escritor_fallida', ruta=ruta,
                                     primer_escritor=previos[-1]._cr_ruta if previos else None))
            raise OSError(28, 'inyeccion AI-%s: fallo al abrir el segundo escritor %s'
                          % (ESC, os.path.basename(ruta)))
        _SF.__init__(self, file, mode, *a, **k)
        self._cr_frames = 0
        self._cr_ruta = os.path.realpath(str(self.name))
        self._cr_modo = self.mode
        self._cr_falla_cierre = None
        REG_SF.append(self)

    def write(self, data):
        r = _SF.write(self, data)
        self._cr_frames += len(data)
        return r

    def close(self):
        if self.closed:
            return _SF.close(self)
        escritura = _escritura(self._cr_modo)
        modo_fallo = self._cr_falla_cierre
        if modo_fallo is None and ESTADO['inyeccion'] is None:
            # A: en el camino normal el PRIMER cierre de un escritor bajo la
            # salida es el de la finalización (Flush final / cierre de
            # writers), anterior a write_reports(): no requiere armado.
            if ESC in ('A1', 'A2') and escritura and self._cr_ruta.startswith(OUT + os.sep):
                modo_fallo = 'antes' if ESC == 'A1' else 'despues'
            if (ESC in ('B1', 'B2') and ESTADO['armado'] and not escritura and MIX_COPIA
                    and self._cr_ruta == os.path.realpath(MIX_COPIA)):
                modo_fallo = 'antes' if ESC == 'B1' else 'despues'
        if modo_fallo is not None:
            self._cr_falla_cierre = None            # fallo único (transitorio)
            tipo = ('cierre_escritor_fallido' if escritura else 'cierre_lector_fallido')
            registrar_inyeccion(dict(tipo=tipo, ruta=self._cr_ruta, modo=modo_fallo))
            if modo_fallo == 'despues':
                _SF.close(self)
                ev(('escritor_cerrado' if escritura else 'lector_cerrado'),
                   ruta=self._cr_ruta, frames=self._cr_frames, con_error=True)
            ev(tipo, ruta=self._cr_ruta, modo=modo_fallo)
            guardar()
            raise OSError(5, 'inyeccion AI-%s: fallo de E/S al cerrar %s (%s del cierre fisico)'
                          % (ESC, os.path.basename(self._cr_ruta), modo_fallo))
        ev('escritor_cerrado' if escritura else 'lector_cerrado',
           ruta=self._cr_ruta, frames=self._cr_frames)
        return _SF.close(self)


soundfile.SoundFile = SoundFileInstr

_orig_open_memmap = np.lib.format.open_memmap
REG_MM = []


def _open_memmap_instr(*a, **k):
    arr = _orig_open_memmap(*a, **k)
    m = getattr(arr, '_mmap', None)
    REG_MM.append(dict(ref=weakref.ref(arr),
                       mmap=weakref.ref(m) if m is not None else None,
                       ruta=os.path.realpath(str(arr.filename))))
    return arr


np.lib.format.open_memmap = _open_memmap_instr

sys.path.insert(0, os.path.dirname(MOTOR))
import lectura_segura_6g1 as L  # noqa: E402

_spec = importlib.util.spec_from_file_location('motor_ai_6g1', MOTOR)
M = importlib.util.module_from_spec(_spec)
sys.modules['motor_ai_6g1'] = M
_spec.loader.exec_module(M)


# ---------------------------------------------------------------- fotografías
def fds_proceso():
    res = []
    for s in os.listdir('/proc/self/fd'):
        try:
            dest = os.readlink('/proc/self/fd/' + s)
        except OSError:
            continue
        esc = None
        try:
            with open('/proc/self/fdinfo/' + s) as f:
                for linea in f:
                    if linea.startswith('flags:'):
                        fl = int(linea.split()[1], 8)
                        esc = (fl & os.O_ACCMODE) in (os.O_WRONLY, os.O_RDWR)
        except (OSError, ValueError):
            pass
        res.append(dict(fd=int(s), destino=dest, escritura=esc))
    return res


def mapeos_proceso():
    res = set()
    with open('/proc/self/maps') as f:
        for linea in f:
            partes = linea.split(None, 5)
            if len(partes) == 6:
                res.add(partes[5].strip())
    return res


def _bajo(p, base):
    return p == base or p.startswith(base.rstrip('/') + '/')


def foto(directorio, etiqueta):
    directorio = os.path.realpath(directorio)
    fds = fds_proceso()
    maps = mapeos_proceso()
    f = dict(
        etiqueta=etiqueta, n_evento=len(EVENTOS), directorio=directorio,
        gc_habilitado=gc.isenabled(),
        identidad=([os.lstat(directorio).st_dev, os.lstat(directorio).st_ino]
                   if os.path.isdir(directorio) else None),
        archivos=inventario(directorio) if os.path.isdir(directorio) else {},
        descriptores_salida_o_entradas=[d for d in fds if _bajo(d['destino'], OUT)
                                        or d['destino'] in ENTRADAS],
        mapeos_bajo_salida=sorted(m for m in maps if _bajo(m, OUT)),
        escritores=[dict(ruta=s._cr_ruta, cerrado=bool(s.closed), frames=s._cr_frames)
                    for s in REG_SF if _escritura(s._cr_modo)
                    and s._cr_ruta.startswith(OUT + os.sep)],
        lectores_abiertos=[s._cr_ruta for s in REG_SF
                           if not _escritura(s._cr_modo) and not s.closed],
        memmaps=[dict(ruta=m['ruta'], vivo=(m['mmap']() is not None if m['mmap'] else False))
                 for m in REG_MM],
    )
    ESTADO['fotos'][etiqueta] = f
    guardar()
    return f


# ----------------------------------------------------------------- envolturas
_orig_write_reports = M.write_reports


def _write_reports_instr(*a, **k):
    r = _orig_write_reports(*a, **k)
    ev('write_reports')
    if ESC == 'E1':
        # integridad final: un byte del final de la COPIA del Mix cambia
        # (mismo inodo, cabecera intacta) DESPUÉS de generar masks/
        registrar_inyeccion(dict(tipo='mix_alterado_tras_masks', ruta=MIX_COPIA))
        with open(MIX_COPIA, 'r+b') as f:
            f.seek(-1, os.SEEK_END)
            b = f.read(1)
            f.seek(-1, os.SEEK_END)
            f.write(bytes([b[0] ^ 0x01]))
        ev('mix_alterado', ruta=MIX_COPIA)
    ESTADO['armado'] = True
    guardar()
    return r


M.write_reports = _write_reports_instr


class ArchivoLogInstr:
    """Proxy del archivo de engine_log.txt: delega todo; el PRIMER close()
    tras el armado falla (C1: antes del cierre físico; C2: después)."""

    def __init__(self, real):
        object.__setattr__(self, '_real', real)
        object.__setattr__(self, '_fallado', False)

    def __getattr__(self, n):
        return getattr(object.__getattribute__(self, '_real'), n)

    @property
    def closed(self):
        return object.__getattribute__(self, '_real').closed

    def write(self, d):
        return object.__getattribute__(self, '_real').write(d)

    def flush(self):
        return object.__getattribute__(self, '_real').flush()

    def close(self):
        real = object.__getattribute__(self, '_real')
        if ESTADO['armado'] and not object.__getattribute__(self, '_fallado'):
            object.__setattr__(self, '_fallado', True)
            modo = 'antes' if ESC == 'C1' else 'despues'
            registrar_inyeccion(dict(tipo='cierre_log_fallido', modo=modo,
                                     ruta=os.path.realpath(real.name)))
            if modo == 'despues':
                real.close()
                ev('log_cerrado', con_error=True)
            ev('cierre_log_fallido', modo=modo)
            guardar()
            raise OSError(28, 'inyeccion AI-%s: fallo al cerrar engine_log.txt (%s del '
                              'cierre fisico)' % (ESC, modo))
        if not real.closed:
            ev('log_cerrado')
        return real.close()


if ESC in ('C1', 'C2'):
    _orig_init_tee = M.init_tee

    def _init_tee_instr(path):
        _orig_init_tee(path)
        M._G_TEE._file = ArchivoLogInstr(M._G_TEE._file)
    M.init_tee = _init_tee_instr

_orig_preparar = M._preparar_aborto_6g1


def _preparar_instr(*a, **k):
    ev('preparar_aborto_entrada')
    inf = _orig_preparar(*a, **k)
    ESTADO['preparar'] = dict(completo=inf.get('completo'), errores=inf.get('errores'),
                              log_cerrado=inf.get('log_cerrado'),
                              escritores=inf.get('escritores'), memmaps=inf.get('memmaps'),
                              lectores=inf.get('lectores'), orden=inf.get('orden'),
                              escritura_abierta_al_registrar=inf.get('escritura_abierta_al_registrar'))
    ev('preparar_aborto_salida', completo=inf.get('completo'))
    guardar()
    return inf


M._preparar_aborto_6g1 = _preparar_instr

_orig_abortar_corrida = M._abortar_corrida_6g1


def _abortar_corrida_instr(*a, **k):
    res = _orig_abortar_corrida(*a, **k)
    ESTADO['resultado_aborto'] = {k2: res.get(k2) for k2 in (
        'motivo', 'abort_registrado', 'trasladado', 'ruta_final', 'traslado_solicitado',
        'traslado_bloqueado', 'motivo_conservacion', 'cierre_recursos_completo',
        'escritura_abierta_al_registrar', 'salidas_invalidadas')}
    guardar()
    return res


M._abortar_corrida_6g1 = _abortar_corrida_instr

_orig_abortar = L.abortar_6g1


def _abortar_instr(run_dir, motivo, detalle=None):
    ev('abortar_6g1_entrada', motivo=motivo, run_dir=os.path.realpath(run_dir))
    foto(run_dir, 'entrada_abortar')
    r = _orig_abortar(run_dir, motivo, detalle)
    ev('abortar_6g1_salida', motivo=motivo)
    foto(run_dir, 'salida_abortar')
    return r


L.abortar_6g1 = _abortar_instr

_orig_publicar = L.publicar_dir_6g1


def _publicar_instr(origen, destino, *a, **k):
    ev('publicar_entrada', origen=os.path.realpath(origen), destino=destino)
    r = _orig_publicar(origen, destino, *a, **k)
    ev('publicar_salida', ruta=os.path.realpath(r) if isinstance(r, str) else repr(r))
    return r


L.publicar_dir_6g1 = _publicar_instr
if hasattr(M, '_publicar_dir_6g1'):
    M._publicar_dir_6g1 = _publicar_instr

_orig_run = M.run_experiment


def _run_registrado(*a, **k):
    r = _orig_run(*a, **k)
    try:
        cod, ruta = r
    except Exception:
        cod, ruta = None, r
    ESTADO['retorno_run_experiment'] = dict(codigo=cod, ruta=repr(ruta),
                                            ruta_str=ruta if isinstance(ruta, str) else None)
    guardar()
    return r


M.run_experiment = _run_registrado


if __name__ == '__main__':
    sys.argv = [MOTOR] + ARGS
    try:
        codigo = M.main()
    except KeyboardInterrupt:
        codigo = getattr(M, 'EXIT_ABORTED', 130)
    ESTADO['codigo_main'] = codigo
    ESTADO['gc_habilitado_al_final'] = gc.isenabled()
    ESTADO['gc_colecciones'] = [g['collections'] for g in gc.get_stats()]
    ev('fin_main', codigo=codigo)
    ra = ESTADO.get('resultado_aborto') or {}
    ubic = ra.get('ruta_final') or (ESTADO.get('inyeccion') or {}).get('provisional')
    if ubic and os.path.isdir(ubic):
        foto(ubic, 'fin_proceso')
    guardar()
    sys.exit(codigo)
