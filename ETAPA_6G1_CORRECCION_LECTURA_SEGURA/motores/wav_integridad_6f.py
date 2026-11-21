"""6F: estricta validación RIFF/WAVE y lectura desde el mismo descriptor.

Sin dependencia de scipy. La lectura de muestras se hace sobre los mismos bytes
que se validaron (mismo descriptor, mismo instante), de modo que el PCM usado
para el diagnóstico es el PCM inspeccionado.

Perfil admitido: RIFF/WAVE little-endian clásico, fmt PCM entero (8/16/24/32) o
IEEE float (32/64), incluido WAVE_FORMAT_EXTENSIBLE con GUID PCM/FLOAT.
Rechazado: RF64, RIFX, GUIDs comprimidos o no-PCM/no-float, bits válidos
incoherentes, channel mask inconsistente, chunks desbordados o desalineados,
tamaños de cabecera que no coinciden con el archivo físico.
"""
import hashlib
import math
import os
import struct

import numpy as np

FMT_PCM = 1
FMT_FLOAT = 3
FMT_EXTENSIBLE = 0xFFFE

GUID_PCM = bytes.fromhex('0100000000001000800000aa00389b71')
GUID_FLOAT = bytes.fromhex('0300000000001000800000aa00389b71')
GUID_ALIAS = {
    bytes.fromhex('0000000000001000800000aa00389b71'): 'PCM (alias de subformato)',
}

MAX_CHANNELS = 18
KNOWN_SPEAKERS = (1 << 18) - 1  # 18 posiciones estándar de WAVE_FORMAT_EXTENSIBLE

SUBTYPE_SPEC = {
    # subtype libsndfile -> (format tag, bits por muestra del contenedor)
    'PCM_U8': (FMT_PCM, 8), 'PCM_S8': (FMT_PCM, 8),
    'PCM_16': (FMT_PCM, 16), 'PCM_24': (FMT_PCM, 24), 'PCM_32': (FMT_PCM, 32),
    'FLOAT': (FMT_FLOAT, 32), 'DOUBLE': (FMT_FLOAT, 64),
}


class WaveError(ValueError):
    """Error de integridad física o de perfil de formato."""


class WaveSpec:
    __slots__ = ('path', 'audio_format', 'extensible', 'channels', 'rate', 'bits',
                 'valid_bits', 'block_align', 'byte_rate', 'frames', 'channel_mask',
                 'data_offset', 'data_size', 'riff_size', 'physical_size', 'chunks',
                 'fact_frames', 'notes')

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__slots__ if k != 'chunks'} | {
            'chunks': [dict(kind=k.decode('latin-1'), size=n, offset=o) for k, n, o in self.chunks]}

    @property
    def sample_width(self):
        return (self.bits + 7) // 8

    @property
    def duration_s(self):
        return self.frames / float(self.rate) if self.rate else 0.0


def _u32(b, off):
    return struct.unpack_from('<I', b, off)[0]


def _parse(f, physical):
    """Parsea RIFF/WAVE sobre un descriptor ya abierto (posicionado al inicio)."""
    f.seek(0)
    head = f.read(12)
    if len(head) != 12:
        raise WaveError('Cabecera RIFF/WAVE incompleta')
    if head[8:] != b'WAVE':
        raise WaveError('No es WAVE (form type distinto de WAVE)')
    if head[:4] == b'RF64':
        raise WaveError('RF64 no admitido en el perfil 6F')
    if head[:4] == b'RIFX':
        raise WaveError('RIFX (big-endian) no admitido en el perfil 6F')
    if head[:4] != b'RIFF':
        raise WaveError('Contenedor distinto de RIFF')
    riff_size = _u32(head, 4)
    declared = 8 + riff_size
    if declared != physical:
        raise WaveError(f'RIFF declara {declared} bytes; el archivo físico tiene {physical}')
    fmt = None
    data = None
    fact = None
    chunks = []
    pos = 12
    while pos < declared:
        if pos + 8 > declared:
            raise WaveError('Cabecera de chunk incompleta')
        f.seek(pos)
        hdr = f.read(8)
        kind, size = struct.unpack('<4sI', hdr)
        if size > 0x7FFFFFFF:
            raise WaveError(f'Tamaño de chunk fuera de rango: {kind!r}')
        body = pos + 8
        stop = body + size
        padded = stop + (size & 1)
        if stop > declared:
            raise WaveError(f'Chunk {kind!r} desborda el RIFF declarado')
        if padded > declared:
            raise WaveError(f'Chunk {kind!r} sin byte de padding dentro del RIFF')
        chunks.append((kind, size, pos))
        if kind == b'fmt ':
            if fmt is not None:
                raise WaveError('Chunk fmt duplicado')
            if size < 16:
                raise WaveError('fmt demasiado corto')
            if data is not None:
                raise WaveError('fmt después de data')
            fmt = (pos, size)
        elif kind == b'data':
            if data is not None:
                raise WaveError('Chunk data duplicado')
            if fmt is None:
                raise WaveError('data antes de fmt')
            data = (body, size)
        elif kind == b'fact' and fact is None:
            if size >= 4:
                f.seek(body)
                fact = struct.unpack('<I', f.read(4))[0]
        pos = padded
    if pos != declared:
        raise WaveError('Recorrido de chunks no cierra exactamente en el límite RIFF')
    if fmt is None:
        raise WaveError('Falta el chunk fmt')
    if data is None:
        raise WaveError('Falta el chunk data')

    f.seek(fmt[0] + 8)
    raw = f.read(fmt[1])
    code, channels, rate, byte_rate, align, bits = struct.unpack('<HHIIHH', raw[:16])
    valid_bits = bits
    mask = 0
    ext = False
    notes = []
    if code == FMT_EXTENSIBLE:
        ext = True
        if fmt[1] < 40:
            raise WaveError('WAVE_FORMAT_EXTENSIBLE exige fmt de al menos 40 bytes')
        cb_size, = struct.unpack_from('<H', raw, 16)
        if cb_size < 22 or 18 + cb_size > fmt[1]:
            raise WaveError(f'cbSize inválido en fmt extensible: {cb_size}')
        valid_bits, mask = struct.unpack_from('<HI', raw, 18)
        g = raw[24:40]
        if g == GUID_PCM:
            code = FMT_PCM
        elif g == GUID_FLOAT:
            code = FMT_FLOAT
        elif g in GUID_ALIAS:
            raise WaveError('GUID de subformato con alias no admitido (00000000-...): exige GUID PCM/FLOAT explícito')
        else:
            raise WaveError('GUID de subformato no admitido: sólo PCM (01...) o FLOAT (03...)')
        if valid_bits == 0 and len(raw) >= 20:
            notes.append('valid_bits=0: se interpreta como bits del contenedor')
            valid_bits = bits
    elif code not in (FMT_PCM, FMT_FLOAT):
        raise WaveError(f'Formato {code} no admitido: sólo PCM (1), IEEE float (3) o EXTENSIBLE')

    if channels < 1 or channels > MAX_CHANNELS:
        raise WaveError(f'Canales fuera de rango: {channels}')
    if rate <= 0:
        raise WaveError('Sample rate no positivo')
    if bits not in (8, 16, 24, 32, 64):
        raise WaveError(f'Bits por muestra no admitidos: {bits}')
    if code == FMT_PCM and bits == 64:
        raise WaveError('PCM entero de 64 bits no admitido')
    if code == FMT_FLOAT and bits not in (32, 64):
        raise WaveError(f'Float de {bits} bits no admitido')
    if not (1 <= valid_bits <= bits):
        raise WaveError(f'valid_bits={valid_bits} incoherente con bits={bits}')
    width = (bits + 7) // 8
    if align != channels * width:
        raise WaveError(f'block align {align} != canales*ancho ({channels*width})')
    if byte_rate != rate * align:
        raise WaveError(f'byte rate {byte_rate} != rate*align ({rate*align})')
    if mask:
        if mask & ~KNOWN_SPEAKERS:
            raise WaveError('channel mask con bits fuera del conjunto estándar')
        if bin(mask).count('1') != channels:
            raise WaveError(f'channel mask con {bin(mask).count("1")} bits para {channels} canales')
    else:
        notes.append('channel mask ausente o cero (geometría deducida del conteo de canales)')
    if code == FMT_FLOAT and fact is None:
        notes.append('float sin chunk fact (permitido; frames se derivan de data)')
    if code == FMT_FLOAT and fact is not None:
        pass  # se contrasta tras conocer frames
    size = data[1]
    if size % align:
        raise WaveError(f'Tamaño data {size} no múltiplo de block align {align}')
    frames = size // align
    if frames == 0:
        raise WaveError('data sin muestras (0 frames)')
    if fact is not None and fact != frames:
        raise WaveError(f'fact declara {fact} frames; data contiene {frames}')
    return WaveSpec(path=None, audio_format=code, extensible=ext, channels=channels,
                    rate=rate, bits=bits, valid_bits=valid_bits, block_align=align,
                    byte_rate=byte_rate, frames=frames, channel_mask=mask,
                    data_offset=data[0], data_size=size, riff_size=riff_size,
                    physical_size=physical, chunks=chunks, fact_frames=fact,
                    notes=notes)


def _decode(buf, spec):
    """Decodifica el payload validado a float64 (frames, canales)."""
    ch, width, vb = spec.channels, spec.sample_width, spec.valid_bits
    if spec.audio_format == FMT_FLOAT:
        dtype = '<f4' if width == 4 else '<f8'
        raw = np.frombuffer(buf, dtype=dtype).reshape(-1, ch)
        if not np.isfinite(raw).all():
            raise WaveError('Muestras no finitas en el payload float')
        return raw.astype('float64')
    if width == 1:
        x = (np.frombuffer(buf, dtype='u1').reshape(-1, ch).astype('int32') - 128)
        scale = 128.0
    elif width == 2:
        x = np.frombuffer(buf, dtype='<i2').reshape(-1, ch).astype('int32')
        scale = 32768.0
    elif width == 3:
        b = np.frombuffer(buf, dtype='u1').reshape(-1, 3)
        v = (b[:, 0].astype('uint32') | (b[:, 1].astype('uint32') << 8) |
             (b[:, 2].astype('uint32') << 16))
        v = np.where(v & 0x800000, v | 0xFF000000, v).astype('int64')
        x = v.reshape(-1, ch).astype('int32')
        scale = 8388608.0
    else:
        x = np.frombuffer(buf, dtype='<i4').reshape(-1, ch).astype('int64')
        scale = 2147483648.0
    if vb != spec.bits:
        # Escalado por bits válidos (contenedor alineado a la izquierda).
        shift = spec.bits - vb
        x = np.right_shift(x, shift)
        scale = float(2 ** (vb - 1))
    y = x.astype('float64') / scale
    if np.abs(y).max(initial=0.0) > 1.0:
        raise WaveError('Muestras PCM fuera del rango nominal [-1, 1]')
    return y


class ValidatedWave:
    """Archivo validado y leído desde el mismo descriptor."""

    def __init__(self, path, fd, spec, samples, digest, identity, unchanged_on_close):
        self.path, self.fd, self.spec, self.samples = path, fd, spec, samples
        self.digest, self.identity = digest, identity
        self.unchanged_on_close = unchanged_on_close

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size,
                mtime_ns=st.st_mtime_ns)


def open_validated(path):
    """Valida y decodifica sin cerrar el descriptor; detecta cambios al cerrar."""
    fd = os.open(path, os.O_RDONLY)
    try:
        st = os.fstat(fd)
        if not (st.st_mode & 0o170000) == 0o100000:
            raise WaveError('No es un archivo regular')
        ident = _identity(st)
        with os.fdopen(os.dup(fd), 'rb') as fh:
            spec = _parse(fh, st.st_size)
        spec.path = os.path.abspath(path)
        f = os.fdopen(os.dup(fd), 'rb')  # vista independiente del mismo inodo
        try:
            f.seek(spec.data_offset)
            buf = f.read(spec.data_size)
            if len(buf) != spec.data_size:
                raise WaveError('Lectura del payload incompleta (archivo truncado durante la lectura)')
        finally:
            f.close()
        m = hashlib.sha256()
        g = os.fdopen(os.dup(fd), 'rb')
        try:
            g.seek(0)
            for block in iter(lambda: g.read(1 << 20), b''):
                m.update(block)
        finally:
            g.close()
        samples = _decode(buf, spec)
        if len(samples) != spec.frames:
            raise WaveError('Frames decodificados distintos de los declarados')
        before = ident
        after = _identity(os.fstat(fd))
        unchanged = before == after
        if not unchanged:
            raise WaveError('El archivo cambió entre validación y lectura (fstat distinto)')
        return ValidatedWave(os.path.abspath(path), fd, spec, samples,
                             m.hexdigest(), ident, unchanged)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise


CLAVES_IDENTIDAD_6G1 = ('device', 'inode', 'size', 'mtime_ns')


def _identidad_comparable(ident):
    """Identidad de objeto comparable entre orígenes WAV y FLAC.

    `wav_integridad_6f` y `audio_integridad_6g` describen la identidad con
    campos distintos (`mode` sólo en el segundo). Comparar los diccionarios
    completos producía un falso negativo en todo FLAC (`identidad fstat
    distinta` aun sin cambios, defecto 6G detectado en 6G.1). Se comparan
    únicamente los campos que definen el objeto: dispositivo, inodo, tamaño y
    mtime; `mode` se conserva en la evidencia pero no en la comparación.
    """
    if not isinstance(ident, dict):
        return ident
    return {k: ident.get(k) for k in CLAVES_IDENTIDAD_6G1}


def check_unchanged(vw):
    """Comprueba que la ruta siga apuntando al mismo objeto/sha tras la corrida."""
    try:
        st = os.stat(vw.path)
    except OSError as exc:
        return dict(unchanged=False, reason=f'no accesible: {exc}')
    ident = _identity(st)
    if _identidad_comparable(ident) != _identidad_comparable(vw.identity):
        return dict(unchanged=False, reason='identidad fstat distinta',
                    before=vw.identity, after=ident,
                    identidad_comparada_6g1=_identidad_comparable(ident))
    m = hashlib.sha256()
    with open(vw.path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            m.update(block)
    digest = m.hexdigest()
    return dict(unchanged=digest == vw.digest, reason='sha256 revalidado',
                sha256=digest,
                identidad_comparada_6g1=_identidad_comparable(ident))


def verify_wave(path, decoder):
    """Compatibilidad con 6E: valida y contrasta con la metadata del decodificador."""
    vw = open_validated(path)
    try:
        spec = vw.spec
        if decoder is not None:
            if (spec.channels, spec.rate, spec.frames) != (int(decoder.channels), int(decoder.samplerate), int(decoder.frames)):
                raise WaveError('Geometría WAV incompatible con el decodificador: '
                                f'{spec.channels}/{spec.rate}/{spec.frames} vs '
                                f'{decoder.channels}/{decoder.samplerate}/{decoder.frames}')
            subtype = str(getattr(decoder, 'subtype', '') or '')
            if subtype:
                want = SUBTYPE_SPEC.get(subtype)
                if want is None:
                    raise WaveError(f'Subtipo de decodificador no admitido: {subtype}')
                if want != (spec.audio_format, spec.bits):
                    raise WaveError(f'Subtipo {subtype} no coincide con fmt ({spec.audio_format},{spec.bits})')
        return spec
    finally:
        vw.close()
