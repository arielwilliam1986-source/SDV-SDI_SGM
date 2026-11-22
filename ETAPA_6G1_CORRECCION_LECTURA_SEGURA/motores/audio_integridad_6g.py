"""6G: validación y lectura del Mix original en WAV (estricto 6F) y FLAC.

Capa de compatibilidad de contenedores: NO contiene procesamiento de audio.
El camino WAV delega íntegramente en `wav_integridad_6f` (sin debilitar nada).
El camino FLAC valida contra la cabecera real del contenedor (magic `fLaC`),
cruza STREAMINFO con lo que reporta libsndfile, decodifica el archivo completo
por bloques comprobando finitud, verifica el MD5 de PCM de STREAMINFO cuando
está disponible, calcula SHA-256 y detecta cambios de identidad entre
validación y lectura.
"""
import hashlib
import os
import stat
import struct

import numpy as np
import soundfile as sf

import wav_integridad_6f as w6

MAGIC_FLAC = b'fLaC'
FLAC_EXTENSIONS = ('.flac',)
WAV_EXTENSIONS = ('.wav',)
FLAC_SUBTYPES = ('PCM_S8', 'PCM_16', 'PCM_24')
FLAC_BLOCK = 1 << 16


class AudioError(ValueError):
    """Contenedor no admitido, incoherente o ilegible."""


class FlacSpec:
    __slots__ = ('path', 'format', 'subtype', 'bits', 'channels', 'rate',
                 'frames', 'md5_pcm', 'md5_checked', 'notes')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


def _identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size,
                mtime_ns=st.st_mtime_ns, mode=oct(st.st_mode))


def container_of(path):
    """Contenedor real por cabecera, no por extensión."""
    with open(path, 'rb') as f:
        head = f.read(12)
    if head[:4] == b'RIFF' and head[8:12] == b'WAVE':
        return 'WAV'
    if head[:4] == MAGIC_FLAC:
        return 'FLAC'
    if head[:4] == b'RF64':
        return 'RF64'
    if head[:4] == b'RIFX':
        return 'RIFX'
    if head[:4] == b'OggS':
        return 'OGG'
    if head[:3] == b'ID3':
        return 'MP3/ID3'
    return 'desconocido:' + head[:4].hex()


def _read_exact(fd, n, offset=0):
    f = os.fdopen(os.dup(fd), 'rb')
    try:
        f.seek(offset)
        data = f.read(n)
    finally:
        f.close()
    return data


def _digest(fd):
    m = hashlib.sha256()
    g = os.fdopen(os.dup(fd), 'rb')
    try:
        g.seek(0)
        for block in iter(lambda: g.read(1 << 20), b''):
            m.update(block)
    finally:
        g.close()
    return m.hexdigest()


def _parse_metadata(fd, physical):
    """Recorre los bloques de metadatos FLAC y devuelve (streaminfo, n_bloques)."""
    head = _read_exact(fd, 4, 0)
    if head != MAGIC_FLAC:
        raise AudioError('Cabecera FLAC ausente (magic != fLaC)')
    off = 4
    streaminfo = None
    blocks = 0
    while True:
        if off + 4 > physical:
            raise AudioError('Bloque de metadatos FLAC truncado')
        hdr = _read_exact(fd, 4, off)
        last = bool(hdr[0] & 0x80)
        btype = hdr[0] & 0x7F
        length = int.from_bytes(hdr[1:4], 'big')
        off += 4
        if off + length > physical:
            raise AudioError(f'Bloque de metadatos FLAC desborda el archivo '
                             f'(tipo {btype}, {length} bytes en offset {off})')
        if btype == 0:
            if streaminfo is not None:
                raise AudioError('STREAMINFO duplicado')
            if length != 34:
                raise AudioError(f'STREAMINFO con longitud {length} (se exige 34)')
            streaminfo = _read_exact(fd, 34, off)
        if blocks == 0 and btype != 0:
            raise AudioError('El primer bloque de metadatos no es STREAMINFO')
        blocks += 1
        off += length
        if last:
            break
        if blocks > 1024:
            raise AudioError('Demasiados bloques de metadatos')
    if streaminfo is None:
        raise AudioError('FLAC sin STREAMINFO')
    if off >= physical:
        raise AudioError('FLAC sin datos de audio')
    b = streaminfo
    rate = (b[10] << 12) | (b[11] << 4) | (b[12] >> 4)
    channels = ((b[12] >> 1) & 0x7) + 1
    bits = (((b[12] & 0x1) << 4) | (b[13] >> 4)) + 1
    total = ((b[13] & 0x0F) << 32) | (b[14] << 24) | (b[15] << 16) | (b[16] << 8) | b[17]
    md5 = b[18:34]
    return dict(rate=rate, channels=channels, bits=bits, frames=total,
                md5=md5, audio_offset=off, blocks=blocks)


def _sf_from_fd(fd):
    """Abre el MISMO inodo a través del descriptor (no de la ruta)."""
    proc = '/proc/self/fd/%d' % fd
    if not os.path.exists(proc):
        raise AudioError('No hay acceso a /proc/self/fd: no se puede garantizar '
                         'lectura del mismo objeto validado')
    return sf.SoundFile(proc)


def _md5_pcm(fd, bits, expected):
    """MD5 del PCM decodificado (LE, bps/8 bytes) contra el de STREAMINFO."""
    if not expected or expected == b'\x00' * 16:
        return False, 'STREAMINFO sin MD5 (no verificable)'
    if bits not in (8, 16, 24, 32):
        return False, f'profundidad {bits} no verificable'
    shift = 32 - bits
    m = hashlib.md5()
    with _sf_from_fd(fd) as snd:
        snd.seek(0)
        while True:
            blk = snd.read(FLAC_BLOCK, dtype='int32', always_2d=True)
            if blk.shape[0] == 0:
                break
            if shift:
                blk = np.right_shift(blk, shift)
            if bits == 8:
                raw = blk.astype('<i1').tobytes()
            elif bits == 16:
                raw = blk.astype('<i2').tobytes()
            elif bits == 24:
                v = (blk.astype('<i4') & 0xFFFFFF).view('u1').reshape(-1, 4)[:, :3]
                raw = v.tobytes()
            else:
                raw = blk.astype('<i4').tobytes()
            m.update(raw)
    got = m.digest()
    if got != expected:
        raise AudioError('MD5 de PCM distinto del declarado en STREAMINFO: '
                         'contenido corrupto o decodificación incompleta')
    return True, 'MD5 de PCM verificado contra STREAMINFO'


def _inspect_flac(path, want_samples=False):
    fd = os.open(path, os.O_RDONLY)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise AudioError('No es un archivo regular')
        ident = _identity(st)
        if st.st_size < 8:
            raise AudioError('Archivo FLAC demasiado pequeño')
        meta = _parse_metadata(fd, st.st_size)

        try:
            snd = _sf_from_fd(fd)
        except Exception as exc:
            raise AudioError(f'libsndfile no pudo abrir el FLAC: {exc}')
        with snd:
            if str(snd.format) != 'FLAC':
                raise AudioError(f'Contenedor real {snd.format!r}: se exige FLAC')
            if str(snd.subtype) not in FLAC_SUBTYPES:
                raise AudioError(f'Subtipo FLAC no admitido: {snd.subtype}')
            if (int(snd.samplerate), int(snd.channels), int(snd.frames)) != (
                    meta['rate'], meta['channels'], meta['frames']):
                raise AudioError('STREAMINFO y libsndfile no coinciden: '
                                 f"{meta['rate']}/{meta['channels']}/{meta['frames']} vs "
                                 f"{snd.samplerate}/{snd.channels}/{snd.frames}")
            total = 0
            chunks = []
            while True:
                try:
                    blk = snd.read(FLAC_BLOCK, dtype='float64', always_2d=True)
                except Exception as exc:
                    raise AudioError(f'Decodificación FLAC falló tras {total} frames: {exc}')
                if blk.shape[0] == 0:
                    break
                if not np.isfinite(blk).all():
                    raise AudioError(f'Muestras no finitas en FLAC (frame {total})')
                total += blk.shape[0]
                if want_samples:
                    chunks.append(blk)
            if total == 0:
                raise AudioError('FLAC sin frames de audio')
            if total != meta['frames']:
                raise AudioError(f'Frames decodificados {total} != declarados {meta["frames"]}')
            subtype = str(snd.subtype)
            rate, channels = int(snd.samplerate), int(snd.channels)

        md5_ok, md5_note = _md5_pcm(fd, meta['bits'], meta['md5'])

        digest = _digest(fd)
        if _identity(os.fstat(fd)) != ident:
            raise AudioError('El archivo cambió entre validación y lectura (fstat distinto)')

        spec = FlacSpec(path=os.path.abspath(path), format='FLAC', subtype=subtype,
                        bits=meta['bits'], channels=channels, rate=rate,
                        frames=total, md5_pcm=meta['md5'].hex(),
                        md5_checked=md5_ok, notes=md5_note)
        samples = np.concatenate(chunks, axis=0) if (want_samples and chunks) else None
        if want_samples:
            if samples is None:
                samples = np.zeros((0, channels), dtype='float64')
            if samples.shape != (total, channels):
                raise AudioError('Geometría de muestras FLAC incoherente')
        return dict(spec=spec, identity=ident, digest=digest, samples=samples,
                    metadata=dict(blocks=meta['blocks'], audio_offset=meta['audio_offset']))
    finally:
        os.close(fd)


class ValidatedFlac:
    """FLAC validado y decodificado; misma interfaz que ValidatedWave."""

    container = 'FLAC'

    def __init__(self, path, spec, samples, digest, identity):
        self.path, self.spec, self.samples = path, spec, samples
        self.digest, self.identity = digest, identity
        self.fd = None
        self.unchanged_on_close = True

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def open_validated_flac(path):
    data = _inspect_flac(path, want_samples=True)
    return ValidatedFlac(os.path.abspath(path), data['spec'], data['samples'],
                         data['digest'], data['identity'])


def verify_audio(path, decoder=None, ext_ref=None):
    """Valida el contenedor real y su coherencia con la extensión.

    WAV -> validación estricta 6F (RIFF/WAVE, chunks, geometría, bits).
    FLAC -> STREAMINFO + libsndfile + decodificación completa + MD5 de PCM.

    [H2-R] `ext_ref`: ruta cuyo NOMBRE se usa para la política de extensión
    cuando `path` es una referencia respaldada por descriptor
    (/proc/self/fd/N). El contenedor y TODAS las validaciones se leen del
    objeto anclado a `path`; sin `ext_ref` el comportamiento es idéntico al
    anterior (ninguna validación se debilita).
    """
    cont = container_of(path)
    ext = os.path.splitext(ext_ref if ext_ref is not None else path)[1].lower()
    if cont == 'WAV':
        if ext not in WAV_EXTENSIONS:
            raise AudioError(f'Contenedor WAV con extensión {ext!r}: se exige .wav')
        spec = w6.verify_wave(path, decoder)
        return dict(container='WAV', spec=spec, md5_checked=None)
    if cont == 'FLAC':
        if ext not in FLAC_EXTENSIONS:
            raise AudioError(f'Contenedor FLAC con extensión {ext!r}: se exige .flac')
        data = _inspect_flac(path, want_samples=False)
        spec = data['spec']
        if decoder is not None:
            if (int(decoder.samplerate), int(decoder.channels), int(decoder.frames)) != (
                    spec.rate, spec.channels, spec.frames):
                raise AudioError('Geometría FLAC incompatible con el decodificador')
            if str(getattr(decoder, 'subtype', '') or '') != spec.subtype:
                raise AudioError(f"Subtipo FLAC {spec.subtype} != {decoder.subtype}")
        return dict(container='FLAC', spec=spec, md5_checked=spec.md5_checked,
                    metadata=data['metadata'], sha256=data['digest'])
    raise AudioError(f'Contenedor no admitido: {cont}')


def open_audio(path):
    """Abre para análisis garantizando que el PCM es el del objeto validado."""
    cont = container_of(path)
    ext = os.path.splitext(path)[1].lower()
    if cont == 'WAV':
        if ext not in WAV_EXTENSIONS:
            raise AudioError(f'Contenedor WAV con extensión {ext!r}: se exige .wav')
        return w6.open_validated(path)
    if cont == 'FLAC':
        if ext not in FLAC_EXTENSIONS:
            raise AudioError(f'Contenedor FLAC con extensión {ext!r}: se exige .flac')
        return open_validated_flac(path)
    raise AudioError(f'Contenedor no admitido: {cont}')


CLAVES_IDENTIDAD_6G1 = ('device', 'inode', 'size', 'mtime_ns')


def _identidad_comparable(ident):
    """Sólo los campos que definen el objeto (WAV y FLAC difieren en `mode`)."""
    if not isinstance(ident, dict):
        return ident
    return {k: ident.get(k) for k in CLAVES_IDENTIDAD_6G1}


def check_file_unchanged(path, digest, identity=None):
    """Comprueba que el archivo siga siendo el mismo objeto y contenido."""
    try:
        st = os.stat(path)
    except OSError as exc:
        return dict(unchanged=False, reason=f'no accesible: {exc}')
    ident = _identity(st)
    if identity is not None and _identidad_comparable(ident) != _identidad_comparable(identity):
        return dict(unchanged=False, reason='identidad fstat distinta',
                    before=identity, after=ident,
                    identidad_comparada_6g1=_identidad_comparable(ident))
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            m.update(block)
    got = m.hexdigest()
    return dict(unchanged=got == digest, reason='sha256 revalidado',
                sha256=got, expected=digest)
