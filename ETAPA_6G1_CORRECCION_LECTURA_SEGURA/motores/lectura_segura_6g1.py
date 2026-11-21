"""6G.1 (rectificado por auditoría): lectura del Mix desde el mismo descriptor,
guarda final fail-closed y aborto con propiedad acreditada.

El DSP no debe volver a abrir el Mix por su ruta. `abrir_mix` mantiene un
descriptor abierto durante toda la corrida y entrega un objeto con la misma
interfaz que `soundfile.SoundFile`, pero respaldado por ese descriptor
(`/proc/self/fd/N`), de modo que una ruta sustituida no puede alimentar el DSP.

`abortar_6g1` (rectificado, corrección C) elimina únicamente archivos cuya
propiedad por la corrida actual esté **acreditada**: el motor registra cada
archivo que crea (ruta + identidad) y la limpieza verifica esa relación antes
de borrar. Si la propiedad no puede demostrarse (archivo ajeno no registrado,
o archivo registrado cuya identidad actual no coincide con la registrada),
el archivo **se conserva** y se lista con el motivo. Ninguna decisión de borrado
se toma por patrón de nombre ni por ubicación (`candidates/` incluido).
"""
import hashlib
import json
import os
import stat
from pathlib import Path

import soundfile as sf


class MixCambiado(RuntimeError):
    """El Mix no es el objeto validado (sustitución o modificación)."""


class VerificacionFallida6G1(RuntimeError):
    """La guarda final no acreditó la identidad del Mix (VERIFICACIÓN
    INCIERTA = ABORTO). El llamador ya ejecutó el aborto sobre el directorio
    provisional; este error sólo señala que no debe publicarse."""


def _identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size,
                mtime_ns=st.st_mtime_ns, mode=oct(st.st_mode))


def _sha_fd(fd):
    m = hashlib.sha256()
    g = os.fdopen(os.dup(fd), 'rb')
    try:
        g.seek(0)
        for block in iter(lambda: g.read(1 << 20), b''):
            m.update(block)
    finally:
        g.close()
    return m.hexdigest()


def _sha_archivo(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            m.update(block)
    return m.hexdigest()


class MixHandle:
    """Descriptor del Mix validado + lector SoundFile sobre el mismo inodo."""

    def __init__(self, path, sha_esperado=None):
        object.__setattr__(self, '_snd', None)
        self.path = os.path.abspath(path)
        self.fd = os.open(self.path, os.O_RDONLY)
        try:
            st = os.fstat(self.fd)
            if not stat.S_ISREG(st.st_mode):
                raise MixCambiado('El Mix no es un archivo regular')
            self.identity = _identity(st)
            self.digest = _sha_fd(self.fd)
            if sha_esperado is not None and self.digest != sha_esperado:
                raise MixCambiado(
                    'SHA-256 del Mix distinto del sondeo: sustitución antes del DSP '
                    f'({self.digest[:16]} != {str(sha_esperado)[:16]})')
            proc = '/proc/self/fd/%d' % self.fd
            if not os.path.exists(proc):
                raise MixCambiado('Sin /proc/self/fd: no se puede leer el mismo inodo')
            self._snd = sf.SoundFile(proc)
        except Exception:
            self.close()
            raise

    # --- interfaz SoundFile -------------------------------------------------
    def __getattr__(self, nombre):
        snd = object.__getattribute__(self, '_snd')
        if snd is None:
            raise AttributeError(nombre)
        return getattr(snd, nombre)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        snd = object.__getattribute__(self, '_snd')
        if snd is not None:
            try:
                snd.close()
            except Exception:
                pass
            object.__setattr__(self, '_snd', None)
        fd = getattr(self, 'fd', None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self.fd = None

    # --- integridad ---------------------------------------------------------
    def verificar(self):
        """Relee el descriptor y compara bytes e identidad con la apertura."""
        if self.fd is None:
            return dict(unchanged=False, reason='descriptor cerrado')
        st = os.fstat(self.fd)
        ident = _identity(st)
        digest = _sha_fd(self.fd)
        ok = (digest == self.digest and ident == self.identity)
        return dict(unchanged=ok,
                    reason='sha256 e identidad revalidados' if ok
                    else ('contenido distinto' if digest != self.digest
                          else 'identidad fstat distinta'),
                    sha256=digest, expected=self.digest,
                    identity=ident, identity_expected=self.identity)

    def ruta_lectura(self):
        """Ruta al mismo inodo (para funciones que exigen un nombre de archivo)."""
        if self.fd is None:
            raise MixCambiado('descriptor cerrado')
        return '/proc/self/fd/%d' % self.fd

    def ruta_apunta_al_mismo_objeto(self):
        try:
            st = os.stat(self.path)
        except OSError as exc:
            return dict(unchanged=False, reason=f'ruta inaccesible: {exc}')
        ident = _identity(st)
        return dict(unchanged=ident == self.identity,
                    reason='ruta e inodo de apertura coinciden' if ident == self.identity
                    else 'la ruta ya no apunta al inodo validado',
                    identity=ident, identity_expected=self.identity)


def abrir_mix(path, sha_esperado=None):
    return MixHandle(path, sha_esperado)


# ---------------------------------------------------------------------------
# Registro de propiedad de la corrida (corrección C, rectificación 6G.1)
# ---------------------------------------------------------------------------

_PROPIOS_6G1 = {}


def reiniciar_registro_6g1():
    """Limpia el registro de propiedad (uso en pruebas y al iniciar corrida)."""
    _PROPIOS_6G1.clear()


def registrar_propio_6g1(path, estable=True):
    """Registra un archivo creado por esta corrida con su identidad.

    `estable=True`: archivo finalizado (informes); se sella tamaño, mtime y
    SHA-256 en el registro. `estable=False`: archivo en curso (WAV/memmap
    abiertos por el motor); la propiedad se acredita por ruta registrada +
    continuidad de inodo (el contenido crece legítimamente mientras el motor
    lo escribe). Si el archivo no puede observarse, NO se registra y, por
    tanto, la limpieza lo conservará (fail-closed, sin interrumpir al motor).
    """
    p = os.path.abspath(str(path))
    try:
        st = os.stat(p)
    except OSError:
        return False
    _PROPIOS_6G1[p] = dict(device=st.st_dev, inode=st.st_ino,
                           size=st.st_size, mtime_ns=st.st_mtime_ns,
                           sha256=_sha_archivo(p) if estable else None,
                           estable=bool(estable))
    return True


def propiedad_de_6g1(path):
    """Dictamen de propiedad de un archivo para esta corrida.

    Devuelve `(es_propia, motivo)`. Fail-closed: cualquier duda conserva el
    archivo (`ajeno_no_registrado`, `identidad_distinta`, `modificado`,
    `no_accesible`).
    """
    p = os.path.abspath(str(path))
    reg = _PROPIOS_6G1.get(p)
    if reg is None:
        return False, 'ajeno_no_registrado'
    try:
        st = os.stat(p)
    except OSError as exc:
        return False, 'no_accesible: %s' % exc
    if (st.st_dev, st.st_ino) != (reg['device'], reg['inode']):
        return False, 'identidad_distinta (sustituido o reemplazado tras el registro)'
    if reg['estable']:
        if st.st_size != reg['size'] or st.st_mtime_ns != reg['mtime_ns']:
            return False, 'tamaño/mtime distintos de los registrados'
        if _sha_archivo(p) != reg['sha256']:
            return False, 'contenido modificado tras el registro'
    return True, 'propiedad_acreditada'


def _es_registro_interno(nombre):
    """Archivos de registro forense que el aborto conserva siempre."""
    return nombre in ('ABORT_6G1.json', 'engine_log.txt',
                      'analysis.json', 'input_integrity_6g.json')


def abortar_6g1(run_dir, motivo, detalle=None):
    """Invalida las salidas de la corrida y registra el aborto (corrección C).

    Sólo borra archivos con **propiedad acreditada** por el registro de la
    corrida (ruta + identidad verificada). Un archivo ajeno —incluido uno que
    coincida con un nombre de salida del motor o que esté dentro de
    `candidates/`— y un archivo registrado cuya identidad actual no coincida
    con la registrada (sustituido tras su creación) se **conservan** y se
    listan con el motivo. Los archivos de registro forense
    (`ABORT_6G1.json`, `engine_log.txt`, `analysis.json`,
    `input_integrity_6g.json`) se conservan.
    """
    run_dir = Path(run_dir)
    eliminados, conservados, motivos = [], [], {}
    if run_dir.exists():
        for p in sorted(run_dir.rglob('*')):
            if not p.is_file():
                continue
            rel = str(p.relative_to(run_dir))
            if _es_registro_interno(p.name):
                conservados.append(rel)
                motivos[rel] = 'registro_interno_conservado'
                continue
            propia, motivo_p = propiedad_de_6g1(p)
            if propia:
                try:
                    p.unlink()
                    eliminados.append(rel)
                except OSError as exc:
                    conservados.append(rel)
                    motivos[rel] = 'ERROR al eliminar: %s' % exc
            else:
                conservados.append(rel)
                motivos[rel] = motivo_p
    info = dict(schema='abort-6g1/2', motivo=motivo, detalle=detalle,
                salidas_invalidadas=eliminados, conservados=conservados,
                motivos_propiedad=motivos,
                politica='propiedad_acreditada_o_conserva; sin borrado por '
                         'patrón de nombre ni por ubicación')
    if run_dir.exists():
        objetivo = run_dir / 'ABORT_6G1.json'
        objetivo.write_text(json.dumps(info, indent=2, ensure_ascii=False, default=str),
                            encoding='utf-8')
        analisis = run_dir / 'analysis.json'
        if analisis.exists():
            try:
                data = json.loads(analisis.read_text(encoding='utf-8'))
                data['abort_6g1'] = info
                analisis.write_text(json.dumps(data, indent=2, ensure_ascii=False,
                                               allow_nan=True, default=str),
                                    encoding='utf-8')
            except Exception:
                pass
    return info
