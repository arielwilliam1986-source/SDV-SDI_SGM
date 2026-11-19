"""Auditoría de integridad WAV de 6F.

Corpus construido byte a byte (válidos e inválidos) + pruebas de sustitución
entre validación y lectura. No autentica contenido ni promete inmunidad ante
escrituras concurrentes: mide qué se rechaza y qué se detecta.
"""
import os
import struct
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6f import EV, Cronometro, dump, sha_file

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'motores'))
from wav_integridad_6f import (WaveError, check_unchanged, open_validated,
                               verify_wave)

SR = 44100
CH = 2
N = 4410
GUID_PCM = bytes.fromhex('0100000000001000800000aa00389b71')
GUID_FLOAT = bytes.fromhex('0300000000001000800000aa00389b71')


def chunk(kind, payload, pad=True):
    out = kind + struct.pack('<I', len(payload)) + payload
    if pad and len(payload) % 2:
        out += b'\x00'
    return out


def fmt_chunk(code=1, channels=CH, rate=SR, bits=16, mask=None, valid=None,
              guid=None, align=None, byte_rate=None, cbsize=None, size=None):
    width = (bits + 7) // 8
    align = align if align is not None else channels * width
    byte_rate = byte_rate if byte_rate is not None else rate * align
    head = struct.pack('<HHIIHH', code, channels, rate, byte_rate, align, bits)
    if code == 0xFFFE:
        g = guid if guid is not None else (GUID_FLOAT if bits in (32, 64) else GUID_PCM)
        vb = valid if valid is not None else bits
        m = mask if mask is not None else (0x3 if channels == 2 else 0x4)
        body = head + struct.pack('<HHI', cbsize if cbsize is not None else 22, vb, m) + g
    else:
        body = head
    if size is not None:
        body = body[:size]
    return chunk(b'fmt ', body)


def riff(chunks, override_size=None, override_magic=b'RIFF'):
    body = b''.join(chunks)
    size = override_size if override_size is not None else len(body) + 4
    return override_magic + struct.pack('<I', size) + b'WAVE' + body


def pcm16(sig):
    return (np.clip(sig, -1, 1) * 32767).astype('<i2').tobytes()


def pcm24(sig):
    v = (np.clip(sig, -1, 1) * 8388607).astype('<i4')
    b = v.astype('<i4').tobytes()
    out = bytearray()
    for i in range(0, len(b), 4):
        out += b[i:i + 3]
    return bytes(out)


def pcm32(sig):
    return (np.clip(sig, -1, 1).astype('<f8') * 2147483647).astype('<i4').tobytes()


def sig(n=N, ch=CH):
    t = np.arange(n)[:, None] / SR
    x = np.zeros((n, ch))
    for c in range(ch):
        x[:, c] = .3 * np.sin(2 * np.pi * (220 + 110 * c) * t[:, 0]) + .05 * (c + 1)
    return x


def build(path, data):
    Path(path).write_bytes(data)
    return path


def corpus(tmp):
    x = sig()
    fmt_pcm16 = fmt_chunk(bits=16)
    data16 = chunk(b'data', pcm16(x))
    f32 = np.asarray(x, dtype='<f4').tobytes()
    cases = {}

    cases['pcm16'] = dict(bytes=bytes(riff([fmt_pcm16, data16])), valid=True)
    cases['pcm24'] = dict(bytes=bytes(riff([fmt_chunk(bits=24), chunk(b'data', pcm24(x))])), valid=True)
    cases['pcm32'] = dict(bytes=bytes(riff([fmt_chunk(bits=32), chunk(b'data', pcm32(x))])), valid=True)
    cases['float32'] = dict(bytes=bytes(riff([fmt_chunk(code=3, bits=32),
                                              chunk(b'data', f32)])), valid=True)
    cases['float64'] = dict(bytes=bytes(riff([fmt_chunk(code=3, bits=64),
                                              chunk(b'data', x.astype('<f8').tobytes())])), valid=True)
    cases['ext_pcm16_mask3'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16,
                                                               mask=0x3), data16])), valid=True)
    cases['ext_float32_mask3'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=32,
                                                                 guid=GUID_FLOAT, mask=0x3),
                                                        chunk(b'data', f32)])), valid=True)
    cases['ext_pcm24_vb24_mask3'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=24, valid=24,
                                                                    mask=0x3),
                                                           chunk(b'data', pcm24(x))])), valid=True)
    v24 = (np.clip(x, -1, 1) * 8388607).astype('<i8')
    vb24_in32 = (v24 << 8).astype('<i4').tobytes()
    cases['ext_pcm24_in32_vb24'] = dict(bytes=bytes(riff([
        fmt_chunk(code=0xFFFE, bits=32, valid=24, mask=0x3, guid=GUID_PCM),
        chunk(b'data', vb24_in32)])), valid=True)
    cases['mono_pcm16'] = dict(bytes=bytes(riff([fmt_chunk(channels=1, bits=16),
                                                chunk(b'data', pcm16(x[:, :1]))])), valid=True)
    cases['ext_mask_zero'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16, mask=0),
                                                   data16])), valid=True)
    cases['extra_list'] = dict(bytes=bytes(riff([fmt_chunk(bits=16),
                                                 chunk(b'LIST', b'INFOISFT' + struct.pack('<I', 3) + b'abc'),
                                                 chunk(b'data', pcm16(x))])), valid=True)
    cases['fact_float'] = dict(bytes=bytes(riff([fmt_chunk(code=3, bits=32),
                                                 chunk(b'fact', struct.pack('<I', N)),
                                                 chunk(b'data', f32)])), valid=True)

    # ---- inválidos -------------------------------------------------------
    good = bytes(riff([fmt_pcm16, data16]))
    cases['truncado'] = dict(bytes=good[:-1000], valid=False, motivo='data desborda el archivo')
    cases['riff_size_corto'] = dict(bytes=riff([fmt_pcm16, data16], override_size=len(good)),
                                    valid=False, motivo='RIFF no coincide con tamaño físico')
    cases['riff_size_largo'] = dict(bytes=riff([fmt_pcm16, data16], override_size=8),
                                    valid=False, motivo='declara menos que el archivo')
    cases['data_desborda'] = dict(bytes=riff([fmt_pcm16, chunk(b'data', pcm16(x)[:-100])],
                                             override_size=len(good) - 8),
                                  valid=False, motivo='chunk data incompleto')
    cases['data_no_multiplo'] = dict(bytes=bytes(riff([fmt_pcm16, chunk(b'data', pcm16(x)[:-2])])),
                                     valid=False, motivo='data no múltiplo de block align')
    cases['sin_padding'] = dict(bytes=bytes(riff([fmt_pcm16, chunk(b'data', pcm16(x)[:-1], pad=False)])),
                                valid=False, motivo='data impar sin byte de padding')
    cases['guid_alaw'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16,
                                                         guid=bytes.fromhex('0600000000001000800000aa00389b71')),
                                                data16])), valid=False, motivo='GUID no PCM/float')
    cases['ext_cbsize_corto'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16, cbsize=10),
                                                       data16])), valid=False, motivo='cbSize < 22')
    cases['valid_bits_mayor'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16, valid=24),
                                                       data16])), valid=False, motivo='valid_bits > bits')
    cases['mask_incoherente'] = dict(bytes=bytes(riff([fmt_chunk(code=0xFFFE, bits=16, mask=0x7),
                                                       data16])), valid=False, motivo='channel mask 3 bits para 2 canales')
    cases['align_malo'] = dict(bytes=bytes(riff([fmt_chunk(bits=16, align=6), data16])),
                               valid=False, motivo='block align != canales*ancho')
    cases['byte_rate_malo'] = dict(bytes=bytes(riff([fmt_chunk(bits=16, byte_rate=12345), data16])),
                                   valid=False, motivo='byte rate incoherente')
    cases['data_duplicado'] = dict(bytes=bytes(riff([fmt_pcm16, data16, data16])),
                                   valid=False, motivo='data repetido')
    cases['fmt_despues_data'] = dict(bytes=bytes(riff([data16, fmt_pcm16])),
                                     valid=False, motivo='data antes de fmt')
    cases['sin_fmt'] = dict(bytes=bytes(riff([data16])), valid=False, motivo='falta fmt')
    cases['sin_data'] = dict(bytes=bytes(riff([fmt_pcm16])), valid=False, motivo='falta data')
    cases['data_vacio'] = dict(bytes=bytes(riff([fmt_pcm16, chunk(b'data', b'')])),
                               valid=False, motivo='0 frames')
    cases['rf64'] = dict(bytes=b'RF64' + good[4:], valid=False, motivo='RF64 no admitido')
    cases['rifx'] = dict(bytes=b'RIFX' + good[4:], valid=False, motivo='RIFX no admitido')
    cases['alaw'] = dict(bytes=bytes(riff([fmt_chunk(code=6, bits=8), data16])),
                         valid=False, motivo='formato comprimido')
    cases['bits_20'] = dict(bytes=bytes(riff([fmt_chunk(bits=20), data16])),
                            valid=False, motivo='profundidad no admitida')
    cases['pcm64'] = dict(bytes=bytes(riff([fmt_chunk(bits=64), data16])),
                          valid=False, motivo='PCM entero 64 bits')
    cases['nan_float'] = dict(bytes=bytes(riff([fmt_chunk(code=3, bits=32),
                                                chunk(b'data', np.full((N, CH), np.nan,
                                                                       dtype='<f4').tobytes())])),
                              valid=False, motivo='muestras no finitas')
    cases['fmt_corto'] = dict(bytes=bytes(riff([fmt_chunk(bits=16, size=14), data16])),
                              valid=False, motivo='fmt de 14 bytes')
    cases['fact_malo'] = dict(bytes=bytes(riff([fmt_chunk(code=3, bits=32),
                                                chunk(b'fact', struct.pack('<I', N - 5)),
                                                chunk(b'data', f32)])),
                              valid=False, motivo='fact no coincide con frames')
    cases['chunk_gigante'] = dict(bytes=bytes(riff([fmt_pcm16,
                                                    b'data' + struct.pack('<I', 0xFFFFFFF0)])),
                                  valid=False, motivo='tamaño de chunk absurdo')
    out = {}
    for name, c in cases.items():
        p = Path(tmp) / f'{name}.wav'
        p.write_bytes(c['bytes'])
        out[name] = dict(path=p, expected_valid=c['valid'], motivo=c.get('motivo'))
    return out


def main():
    ev = {}
    with Cronometro() as cron, tempfile.TemporaryDirectory(prefix='sdv6f-wav-') as tmp:
        for name, c in corpus(tmp).items():
            p = c['path']
            row = dict(path=p.name, size=p.stat().st_size, sha256=sha_file(p),
                       expected_valid=c['expected_valid'], motivo=c.get('motivo'))
            try:
                info = sf.info(str(p))
                row['decoder'] = dict(frames=info.frames, channels=info.channels,
                                      samplerate=info.samplerate, subtype=info.subtype)
            except Exception as exc:
                row['decoder'] = None
                row['decoder_error'] = f'{type(exc).__name__}: {exc}'
            try:
                spec = verify_wave(str(p), row['decoder'] and
                                   type('D', (), {k: getattr(sf.info(str(p)), k) for k in
                                                  ('frames', 'channels', 'samplerate', 'subtype')})())
                vw = open_validated(str(p))
                try:
                    row['spec'] = spec.as_dict()
                    row['samples_shape'] = list(vw.samples.shape)
                    row['samples_finite'] = bool(np.isfinite(vw.samples).all())
                    row['peak'] = float(np.abs(vw.samples).max())
                    row['same_descriptor'] = vw.unchanged_on_close
                    row['unchanged_after'] = check_unchanged(vw)
                finally:
                    vw.close()
                row['accepted'] = True
                row['error'] = None
            except WaveError as exc:
                row['accepted'] = False
                row['error'] = str(exc)
            except Exception as exc:  # noqa: BLE001
                row['accepted'] = False
                row['error'] = f'{type(exc).__name__}: {exc}'
            row['ok'] = row['accepted'] == c['expected_valid']
            ev[name] = row

        # ---- sustitución entre validación y lectura ----------------------
        sub = {}
        base = Path(tmp) / 'pcm16.wav'
        other = Path(tmp) / 'float32.wav'
        vw = open_validated(str(base))
        before = vw.digest
        samples_before = vw.samples.copy()
        os.replace(str(other), str(base))
        sub['replace_after_open'] = dict(
            samples_unchanged=bool(np.array_equal(samples_before, vw.samples)),
            digest_original=before, sha_on_disk=sha_file(base),
            detection=check_unchanged(vw))
        vw.close()
        # modificación en sitio detectada por identidad/sha
        p2 = Path(tmp) / 'inplace.wav'
        p2.write_bytes(base.read_bytes())
        vw2 = open_validated(str(p2))
        with open(p2, 'r+b') as f:
            f.seek(-4, 2)
            f.write(b'\x00\x00\x00\x00')
        sub['inplace_modification'] = check_unchanged(vw2)
        vw2.close()
        # sustitución entre sondeo y lectura detectada por sha del sondeo
        from comun_6f import load_engine
        eng = load_engine(EV.parent / 'motores' / 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
                          tag='wav_audit_engine')
        mix = Path(tmp) / 'mix.wav'
        guide = Path(tmp) / 'guide.wav'
        x = sig()
        for dest, arr in ((mix, x), (guide, x)):
            sf.write(dest, arr, SR, subtype='FLOAT')
        infos = [eng.probe_file(str(p), r) for p, r in ((mix, 'mix'), (guide, 'vocal'))]
        sf.write(guide, np.roll(x, 5, axis=0), SR, subtype='FLOAT')  # sustitución
        res = eng.analyze_alignment(infos[0], infos[1])
        sub['probe_then_substitute'] = dict(attribution=res.get('attribution'),
                                            error=res.get('error'),
                                            detected=res.get('attribution') == 'ERROR')
        ev['_toctou'] = sub
        conformes = sum(1 for k, v in ev.items()
                        if k != '_toctou' and v.get('ok'))
        total = sum(1 for k in ev if k != '_toctou')
    dump(EV / 'wav_auditoria.json', dict(casos=ev, conformes=conformes,
                                         total=total, seconds=cron.seconds,
                                         maxrss_kib=cron.maxrss_kib,
                                         entorno=__import__('comun_6f').entorno()))
    t = ev['_toctou']
    print(f'WAV: {conformes}/{total} expectativas; TOCTOU detectado: '
          f"reemplazo={not t['replace_after_open']['detection']['unchanged']}, "
          f"modificacion_en_sitio={not t['inplace_modification']['unchanged']}, "
          f"sustitucion_tras_sondeo={t['probe_then_substitute']['detected']}")
    malos = [k for k, v in ev.items() if k != '_toctou' and not v.get('ok')]
    for k in malos:
        print('FALLA', k, ev[k]['expected_valid'], ev[k]['accepted'], ev[k]['error'])
    return 0 if not malos else 1


if __name__ == '__main__':
    raise SystemExit(main())
