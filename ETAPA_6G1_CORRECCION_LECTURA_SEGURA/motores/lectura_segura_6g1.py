"""6G.1: lectura del Mix desde el mismo descriptor e aborto seguro.

El DSP no debe volver a abrir el Mix por su ruta. `abrir_mix` mantiene un
descriptor abierto durante toda la corrida y entrega un objeto con la misma
interfaz que `soundfile.SoundFile`, pero respaldado por ese descriptor
(`/proc/self/fd/N`), de modo que una ruta sustituida no puede alimentar el DSP.

`abortar_6g1` elimina únicamente las salidas producidas por la corrida actual y
deja registro del motivo.
"""
import hashlib
import json
import os
import stat
from pathlib import Path

import soundfile as sf


class MixCambiado(RuntimeError):
    """El Mix no es el objeto validado (sustitución o modificación)."""


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


def _es_salida_de_la_corrida(p, run_dir):
    """Sólo las salidas que produce el motor en esta corrida.

    Regla conservadora: se reconocen los nombres que el motor escribe
    (`<base> SDV.wav`, `<base> SDI.wav`, cualquier WAV dentro de `candidates/`
    y PNG cuyo nombre contenga SDV/SDI). Todo lo demás se conserva intacto.
    """
    nombre = p.name
    suf = p.suffix.lower()
    if suf == '.wav':
        if 'candidates' in p.relative_to(run_dir).parts:
            return True
        return (nombre.endswith(' SDV.wav') or nombre.endswith(' SDI.wav')
                or nombre in ('SDV.wav', 'SDI.wav'))
    if suf == '.png':
        return ('SDV' in nombre) or ('SDI' in nombre)
    return False


def abortar_6g1(run_dir, motivo, detalle=None):
    """Invalida las salidas de audio de la corrida actual y registra el aborto.

    Sólo toca salidas reconocidas como propias de la corrida dentro de
    `run_dir`; cualquier archivo preexistente o ajeno se conserva y se lista.
    """
    run_dir = Path(run_dir)
    eliminados, conservados = [], []
    if run_dir.exists():
        for p in sorted(run_dir.rglob('*')):
            if not p.is_file():
                continue
            if p.name in ('ABORT_6G1.json', 'analysis.json', 'engine_log.txt'):
                continue
            if _es_salida_de_la_corrida(p, run_dir):
                try:
                    p.unlink()
                    eliminados.append(str(p.relative_to(run_dir)))
                except OSError as exc:
                    conservados.append(f'ERROR {p.name}: {exc}')
            else:
                conservados.append(str(p.relative_to(run_dir)))
    info = dict(schema='abort-6g1/1', motivo=motivo, detalle=detalle,
                salidas_invalidadas=eliminados, conservados=conservados,
                politica='sin_salidas_parciales; no se borran archivos ajenos')
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
