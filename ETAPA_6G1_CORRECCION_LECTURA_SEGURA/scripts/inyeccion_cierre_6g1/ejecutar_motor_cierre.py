"""Ejecutor con inyección determinista DURANTE el procesamiento (6G.1 / CR).

Uso:  python -B ejecutar_motor_cierre.py ESCENARIO RUTA_MOTOR [args del motor]

Carga el motor como módulo (con su propia carpeta en sys.path, de modo que
importa el MISMO `lectura_segura_6g1` que en producción) y llama a `main()`
como el bloque `if __name__ == "__main__"` del motor. No modifica ningún
archivo del motor ni del módulo; sólo instrumenta en memoria:

  * `soundfile.SoundFile`: subclase que registra cada instancia (modo,
    ruta), cuenta los frames escritos y anota cada cierre efectivo como
    evento ordenado. Un cierre posterior al registro del aborto (por
    ejemplo, desde `__del__` en la recolección) también queda anotado.
  * `numpy.lib.format.open_memmap`: registra cada memmap con referencias
    DÉBILES al array y al objeto mmap subyacente; el arnés no prolonga su
    vida. El estado «cerrado» combina `mmap.closed` (si el objeto sigue
    vivo) con la vista del sistema operativo: ningún mapeo en
    /proc/self/maps ni descriptor en /proc/self/fd sobre el archivo.
  * `lectura_segura_6g1.abortar_6g1`: eventos de entrada y salida y una
    fotografía completa en cada uno (SHA-256 de todos los archivos del
    provisional, descriptores y mapeos bajo el directorio de salida, estado
    de escritores, lectores y memmaps).
  * `lectura_segura_6g1.publicar_dir_6g1`: eventos de traslado.
  * `OlaStream.push` del motor: punto de inyección. El fallo se provoca
    DESPUÉS de un push con escritor WAV cuyo flujo ya había escrito al menos
    un bloque antes, es decir, a mitad del procesamiento, con los
    CandidateRunner construidos, los escritores abiertos, al menos dos
    bloques escritos en ese flujo y los memmaps vivos.

Escenarios:
  R1  KeyboardInterrupt durante el procesamiento con escritores abiertos.
  R2  RuntimeError durante el procesamiento con escritores abiertos.
  R3  (complementario) como R2, pero el arnés conserva una vista viva de
      un memmap: no puede cerrarse de forma segura. El error debe quedar
      documentado y el aborto debe registrarse SIN traslado.
  R4  (complementario) la apertura del Mix falla (OSError) DESPUÉS de
      construir los CandidateRunner, es decir, con los escritores y los
      memmaps abiertos. Ejercita el manejador de FalloCorrida6G1.
  E0  (complementario) sin inyección: corrida feliz instrumentada.

En el instante de la inyección siembra AJENO_CV.txt dentro del provisional y
un destino preexistente `<final>_aborted/MARCA_DESTINO.txt`. Escribe todo en
JSON en $SDVSDI_CR_SNAP.
"""
import hashlib
import importlib.util
import json
import os
import sys
import time
import weakref

ESC = sys.argv[1]
MOTOR = os.path.abspath(sys.argv[2])
ARGS = sys.argv[3:]
SNAP = os.environ['SDVSDI_CR_SNAP']
OUT = os.path.realpath(os.environ['SDVSDI_CR_OUT'])
ENTRADAS = [os.path.realpath(p) for p in
            os.environ.get('SDVSDI_CR_ENTRADAS', '').split(os.pathsep) if p]
AJENO_CONTENIDO = b'archivo ajeno sembrado por la prueba CR 6G.1\n'
MARCA_CONTENIDO = b'destino preexistente: no debe reemplazarse\n'

EVENTOS = []
ESTADO = dict(escenario=ESC, eventos=EVENTOS, fotos={}, inyeccion=None,
              ki_escapo=False)


def ev(tipo, **datos):
    EVENTOS.append(dict(n=len(EVENTOS) + 1, t=time.monotonic(), tipo=tipo, **datos))


def guardar():
    with open(SNAP, 'w', encoding='utf-8') as f:
        json.dump(ESTADO, f, indent=2, default=str)


# ------------------------------------------------------------ instrumentación
import numpy as np            # noqa: E402
import soundfile              # noqa: E402

_SF = soundfile.SoundFile
REG_SF = []


class SoundFileInstr(_SF):
    def __init__(self, *a, **k):
        _SF.__init__(self, *a, **k)
        self._cr_frames = 0
        self._cr_ruta = os.path.realpath(str(self.name))
        self._cr_modo = self.mode
        REG_SF.append(self)

    def write(self, data):
        r = _SF.write(self, data)
        self._cr_frames += len(data)
        return r

    def close(self):
        if not self.closed:
            escritura = 'w' in self._cr_modo or '+' in self._cr_modo
            ev('escritor_cerrado' if escritura else 'lector_cerrado',
               ruta=self._cr_ruta, frames=self._cr_frames)
        _SF.close(self)


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

_spec = importlib.util.spec_from_file_location('motor_cr_6g1', MOTOR)
M = importlib.util.module_from_spec(_spec)
sys.modules['motor_cr_6g1'] = M
_spec.loader.exec_module(M)


# ---------------------------------------------------------------- fotografías
def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def inventario(d):
    res = {}
    for raiz, dirs, archivos in os.walk(d):
        for a in archivos:
            p = os.path.join(raiz, a)
            if os.path.isfile(p) and not os.path.islink(p):
                res[os.path.relpath(p, d)] = _sha(p)
    return res


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


def _estado_memmap(m, maps, fds):
    obj = m['mmap']() if m['mmap'] is not None else None
    en_so = (m['ruta'] in maps) or any(d['destino'] == m['ruta'] for d in fds)
    return dict(ruta=m['ruta'], mmap_vivo=obj is not None,
                mmap_cerrado=((obj is None or obj.closed) and not en_so),
                mapeado_o_abierto_en_so=en_so, array_vivo=m['ref']() is not None)


def foto(directorio, etiqueta):
    directorio = os.path.realpath(directorio)
    fds = fds_proceso()
    maps = mapeos_proceso()
    sospechosos = [d for d in fds if _bajo(d['destino'], OUT)
                   or any(d['destino'] == e for e in ENTRADAS)]
    f = dict(
        etiqueta=etiqueta, n_evento=len(EVENTOS), directorio=directorio,
        identidad=([os.lstat(directorio).st_dev, os.lstat(directorio).st_ino]
                   if os.path.isdir(directorio) else None),
        archivos=inventario(directorio) if os.path.isdir(directorio) else {},
        descriptores_salida_o_entradas=sospechosos,
        mapeos_bajo_salida=sorted(m for m in maps if _bajo(m, OUT)),
        escritores=[dict(ruta=s._cr_ruta, cerrado=bool(s.closed), frames=s._cr_frames)
                    for s in REG_SF if 'w' in s._cr_modo or '+' in s._cr_modo],
        lectores_abiertos=[s._cr_ruta for s in REG_SF
                           if not ('w' in s._cr_modo or '+' in s._cr_modo)
                           and not s.closed],
        memmaps=[_estado_memmap(m, maps, fds) for m in REG_MM],
    )
    ESTADO['fotos'][etiqueta] = f
    guardar()
    return f


# ----------------------------------------------------------- envolturas de L
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
    ev('traslado_entrada', origen=os.path.realpath(origen), destino=destino)
    r = _orig_publicar(origen, destino, *a, **k)
    ev('traslado_salida', ruta=os.path.realpath(r) if isinstance(r, str) else repr(r))
    return r


L.publicar_dir_6g1 = _publicar_instr

# ----------------------------------------------------------------- inyección
VISTAS_R3 = []


def _datos_inyeccion(stream=None):
    """Fotografía en el instante de la inyección. Sólo devuelve datos planos:
    ninguna referencia a arrays queda en marcos vivos del traceback."""
    parciales = [d for d in os.listdir(OUT) if d.endswith('_partial')]
    prov = os.path.join(OUT, parciales[0])
    final = prov[:-len('_partial')]
    ajeno = os.path.join(prov, 'AJENO_CV.txt')
    with open(ajeno, 'wb') as f:
        f.write(AJENO_CONTENIDO)
    dest = final + '_aborted'
    os.mkdir(dest, 0o700)
    with open(os.path.join(dest, 'MARCA_DESTINO.txt'), 'wb') as f:
        f.write(MARCA_CONTENIDO)
    st_d = os.lstat(dest)
    mm = []
    for m in REG_MM:
        a = m['ref']()
        if a is None:
            continue
        mm.append(dict(ruta=m['ruta'], sha_logico=hashlib.sha256(a.tobytes()).hexdigest(),
                       shape=list(a.shape), dtype=str(a.dtype)))
        del a
    escritores = [dict(ruta=s._cr_ruta, abierto=not s.closed, frames=s._cr_frames)
                  for s in REG_SF if 'w' in s._cr_modo or '+' in s._cr_modo]
    an = os.path.join(prov, 'analysis.json')
    st_p = os.lstat(prov)
    return dict(
        provisional=os.path.realpath(prov), final=os.path.realpath(final),
        identidad=[st_p.st_dev, st_p.st_ino],
        flujo=getattr(stream, 'label', None),
        flujo_ruta=(os.path.realpath(str(stream.writer.name)) if stream else None),
        flujo_frames=(stream.writer._cr_frames if stream else 0),
        flujo_pushes=(stream._cr_pushes if stream else 0),
        escritores=escritores, memmaps=mm,
        archivos=inventario(prov),
        tamanos={os.path.relpath(e['ruta'], prov): os.path.getsize(e['ruta'])
                 for e in escritores},
        analysis_sha256=_sha(an) if os.path.isfile(an) else None,
        ajeno_sha256=hashlib.sha256(AJENO_CONTENIDO).hexdigest(),
        destino_preexistente=dict(ruta=os.path.realpath(dest),
                                  identidad=[st_d.st_dev, st_d.st_ino],
                                  marca_sha256=hashlib.sha256(MARCA_CONTENIDO).hexdigest()),
        n_evento=len(EVENTOS) + 1)


_orig_push = M.OlaStream.push


def _push_instr(self, X):
    w = getattr(self, 'writer', None)
    previo = w is not None and getattr(w, '_cr_frames', 0) > 0
    r = _orig_push(self, X)
    if w is not None:
        self._cr_pushes = getattr(self, '_cr_pushes', 0) + 1
    if w is not None and previo and ESTADO['inyeccion'] is None:
        ESTADO['inyeccion'] = _datos_inyeccion(self)
        ev('inyeccion', escenario=ESC, flujo=getattr(self, 'label', '?'))
        if ESC == 'R3':
            # el arnés conserva una vista viva del primer memmap
            for m in REG_MM:
                a = m['ref']()
                if a is not None:
                    VISTAS_R3.append(a[:1])
                    ESTADO['inyeccion']['memmap_retenido'] = m['ruta']
                    del a
                    break
        guardar()
        del w, r
        if ESC == 'R1':
            raise KeyboardInterrupt()
        raise RuntimeError('inyeccion CR %s: fallo durante el procesamiento con '
                           'escritores abiertos' % ESC)
    return r


if ESC in ('R1', 'R2', 'R3'):
    M.OlaStream.push = _push_instr
elif ESC == 'R4':
    _orig_abrir = M._abrir_mix_6g1

    def _abrir_falla(*a, **k):
        # sólo la apertura posterior a crear el provisional (la de
        # analyze_guide_scale, previa, no se altera)
        if not [d for d in os.listdir(OUT) if d.endswith('_partial')]:
            return _orig_abrir(*a, **k)
        ESTADO['inyeccion'] = _datos_inyeccion(None)
        ev('inyeccion', escenario=ESC, flujo=None)
        guardar()
        raise OSError(5, 'inyeccion CR R4: fallo de E/S al abrir el Mix con '
                         'escritores abiertos')
    M._abrir_mix_6g1 = _abrir_falla
elif ESC != 'E0':
    raise SystemExit('escenario desconocido: %s' % ESC)

_orig_run = M.run_experiment


def _run_registrado(*a, **k):
    r = _orig_run(*a, **k)
    try:
        cod, ruta = r
    except Exception:
        cod, ruta = None, r
    ESTADO['retorno_run_experiment'] = dict(
        codigo=cod, ruta=repr(ruta),
        ruta_str=ruta if isinstance(ruta, str) else None,
        ruta_es_directorio=isinstance(ruta, str) and os.path.isdir(ruta))
    guardar()
    return r


M.run_experiment = _run_registrado


if __name__ == '__main__':
    sys.argv = [MOTOR] + ARGS
    try:
        codigo = M.main()
    except KeyboardInterrupt:
        ESTADO['ki_escapo'] = True
        codigo = getattr(M, 'EXIT_ABORTED', 130)
    ESTADO['codigo_main'] = codigo
    ev('fin_main', codigo=codigo)
    # ubicación final: destino del traslado si lo hubo; si no, el provisional
    tr = [e for e in EVENTOS if e['tipo'] == 'traslado_salida']
    inj = ESTADO.get('inyeccion') or {}
    ubic = tr[-1]['ruta'] if tr else inj.get('provisional')
    if ESC == 'E0':
        ubic = (ESTADO.get('retorno_run_experiment') or {}).get('ruta_str')
    if ubic and os.path.isdir(ubic):
        foto(ubic, 'fin_proceso')
    guardar()
    sys.exit(codigo)
