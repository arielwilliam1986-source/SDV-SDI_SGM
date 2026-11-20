#!/usr/bin/env python3
"""Diagnóstico aislado de E/S; sin motores, privilegios ni limpieza automática."""

import argparse
import collections
import errno
import hashlib
import json
import os
import platform
import re
import stat
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

SCRIPT = Path(__file__).resolve()
UNSUPPORTED = {errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EINVAL}
ACCESS = {errno.EACCES, errno.EPERM}
GROUPS = {}


class Unavailable(Exception):
    pass


def require(value, message):
    if not value:
        raise AssertionError(message)


def error(exc):
    result = {
        "type": type(exc).__name__,
        "message": str(exc),
        "errno": getattr(exc, "errno", None),
    }
    if exc.__cause__ is not None:
        result["cause"] = error(exc.__cause__)
    return result


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def case(group):
    def register(fn):
        GROUPS.setdefault(group, {})[fn.__name__] = fn
        return fn
    return register


def feature(name):
    if not hasattr(os, name):
        raise Unavailable(f"os.{name} no está disponible")
    return getattr(os, name)


def candidate(fn, *args, permission=False, **kwargs):
    try:
        return fn(*args, **kwargs)
    except OSError as exc:
        if exc.errno in UNSUPPORTED or (permission and exc.errno in ACCESS):
            raise Unavailable("operación no disponible en este contexto") from exc
        raise


def ident(s):
    return s.st_dev, s.st_ino


def record(s):
    return {
        "dev": s.st_dev, "ino": s.st_ino, "mode": oct(s.st_mode),
        "size": s.st_size, "mtime_ns": s.st_mtime_ns, "ctime_ns": s.st_ctime_ns,
    }


@contextmanager
def owned_fd(fd):
    try:
        yield fd
    finally:
        os.close(fd)


@contextmanager
def create(path):
    with path.open("xb") as f:
        emit("created", path=str(path), kind="file", **record(os.fstat(f.fileno())))
        yield f


def put(path, content):
    with create(path) as f:
        f.write(content)
    return path


def mkdir(path):
    path.mkdir(mode=0o700)
    emit("created", path=str(path), kind="directory", **record(path.lstat()))
    return path


def symlink(path, target):
    candidate(os.symlink, target, path, permission=True)
    emit("created", path=str(path), kind="symlink", target=target,
         **record(path.lstat()))


def ref_open(path, *, dir_fd=None, directory=False):
    flags = feature("O_PATH") | feature("O_NOFOLLOW")
    if directory:
        flags |= feature("O_DIRECTORY")
    kwargs = {} if dir_fd is None else {"dir_fd": dir_fd}
    return candidate(os.open, path, flags, permission=True, **kwargs)


def read_object(ref):
    before = os.fstat(ref)
    require(stat.S_ISREG(before.st_mode), "la referencia no es regular")
    try:
        fd = candidate(os.open, f"/proc/self/fd/{ref}", os.O_RDONLY,
                       permission=True)
    except FileNotFoundError as exc:
        raise Unavailable("procfs no entregó un lector de la referencia") from exc
    try:
        actual = os.fstat(fd)
        require(stat.S_ISREG(actual.st_mode) and ident(actual) == ident(before),
                "la referencia y el lector no son el mismo objeto regular")
        os.lseek(fd, 0, os.SEEK_SET)
        return fd
    except BaseException:
        os.close(fd)
        raise


@case("fd")
def proc_same_object(root):
    path = put(root / "source.bin", b"abcdef")
    with owned_fd(ref_open(path)) as ref:
        with owned_fd(read_object(ref)) as fd:
            require(os.read(fd, 6) == b"abcdef", "contenido distinto")
            return {"reference": record(os.fstat(ref)), "reader": record(os.fstat(fd))}


@case("fd")
def proc_after_replacement(root):
    source = put(root / "source.bin", b"equal-bytes")
    replacement = put(root / "replacement.bin", b"equal-bytes")
    retired = root / "retired.bin"
    with owned_fd(ref_open(source)) as ref:
        candidate(rename_noreplace, source, retired, permission=True)
        emit("moved", source=str(source), destination=str(retired),
             **record(retired.lstat()))
        candidate(os.link, replacement, source, permission=True)
        emit("created", path=str(source), kind="hardlink", **record(source.lstat()))
        with owned_fd(read_object(ref)) as fd:
            require(ident(os.fstat(fd)) != ident(source.stat()),
                    "el lector siguió el nombre sustituido")
            require(os.read(fd, 32) == source.read_bytes() == b"equal-bytes",
                    "los objetos del control no contienen los mismos bytes")
            return {"pinned": record(os.fstat(fd)), "replacement": record(source.stat())}


@case("fd")
def symlink_final(root):
    put(root / "regular.bin", b"x")
    link = root / "final-link"
    symlink(link, "regular.bin")
    try:
        fd = ref_open(link)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            return {"rejected": True, "observed": error(exc)}
        raise
    with owned_fd(fd):
        require(stat.S_ISLNK(os.fstat(fd).st_mode), "se siguió el enlace final")
        return {"rejected": True, "reference_type": "symlink",
                "decoder_called": False}


class WalkRejected(Exception):
    def __init__(self, index, component, cause, leaf_attempted):
        super().__init__(f"componente {index}: {component}")
        self.index = index
        self.component = component
        self.cause = cause
        self.leaf_attempted = leaf_attempted


def walk_ref(anchor, components):
    """Recorrido del fixture; cada apertura se ancla al directorio anterior."""
    require(len(components) >= 2 and all(
        c not in ("", ".", "..") and "/" not in c for c in components
    ), "componentes no admitidos")
    current = os.dup(anchor)
    try:
        for index, component in enumerate(components[:-1]):
            try:
                child = ref_open(component, dir_fd=current, directory=True)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise WalkRejected(index, component, exc, False) from exc
                raise
            if not stat.S_ISDIR(os.fstat(child).st_mode):
                os.close(child)
                raise WalkRejected(index, component, None, False)
            previous, current = current, child
            os.close(previous)
        return ref_open(components[-1], dir_fd=current)
    finally:
        os.close(current)


@case("fd")
def symlink_intermediate_walk(root):
    outer = mkdir(root / "outer")
    real = mkdir(outer / "real")
    leaf = put(real / "leaf.bin", b"safe")
    symlink(outer / "redirect", "real")
    with owned_fd(ref_open(root, directory=True)) as anchor:
        with owned_fd(walk_ref(anchor, ("outer", "real", "leaf.bin"))) as control:
            require(ident(os.fstat(control)) == ident(leaf.stat()),
                    "el control de ruta legítima falló")
        try:
            fd = walk_ref(anchor, ("outer", "redirect", "leaf.bin"))
        except WalkRejected as exc:
            require(exc.index == 1 and exc.component == "redirect"
                    and not exc.leaf_attempted,
                    "no se rechazó el enlace en el punto esperado")
            return {"positive_control": True, "rejected_index": exc.index,
                    "rejected_component": exc.component, "leaf_attempted": False,
                    "observed": error(exc.cause) if exc.cause else None}
        else:
            os.close(fd)
            raise AssertionError("el recorrido aceptó un enlace intermedio")


@case("fd")
def dev_null_reference(root):
    # Único dispositivo permitido: adquirir una referencia, nunca contenido.
    try:
        fd = ref_open("/dev/null")
    except FileNotFoundError as exc:
        raise Unavailable("/dev/null no existe en este entorno") from exc
    with owned_fd(fd):
        st = os.fstat(fd)
        require(stat.S_ISCHR(st.st_mode), "/dev/null no es dispositivo de carácter")
        return {"path": "/dev/null", "type": "character_device",
                "reference": record(st), "content_opened": False,
                "read": False, "written": False}


def fifo_case(root, direct):
    path = root / "fixture.fifo"
    candidate(feature("mkfifo"), path, 0o600, permission=True)
    emit("created", path=str(path), kind="fifo", **record(path.lstat()))
    fd = (candidate(os.open, path, os.O_RDONLY | feature("O_NONBLOCK"),
                    permission=True) if direct else ref_open(path))
    with owned_fd(fd):
        require(stat.S_ISFIFO(os.fstat(fd).st_mode), "el objeto no es un FIFO")
    return {"type": "FIFO", "opened_direct_nonblock": direct, "read": False}


@case("fd")
def fifo_reference_only(root):
    return fifo_case(root, False)


@case("fd")
def fifo_direct_nonblock(root):
    return fifo_case(root, True)


@case("fd")
def dup_and_pread(root):
    path = put(root / "offset.bin", b"abcdef")
    with owned_fd(os.open(path, os.O_RDONLY)) as fd:
        with owned_fd(os.dup(fd)) as alias:
            require(os.read(alias, 2) == b"ab", "lectura por dup incorrecta")
            shared = os.lseek(fd, 0, os.SEEK_CUR)
            require(shared == 2, "no se observó el offset compartido")
            require(candidate(feature("pread"), fd, 3, 0) == b"abc",
                    "pread incorrecto")
            require(os.lseek(fd, 0, os.SEEK_CUR) == shared, "pread movió el offset")
    return {"after_dup_read": shared, "after_pread": shared}


def dependencies(fmt=None, subtype=None):
    try:
        import numpy as np
        import soundfile as sf
    except Exception as exc:
        raise Unavailable("NumPy/SoundFile/libsndfile no se pudieron cargar") from exc
    if fmt and (fmt not in sf.available_formats()
                or subtype not in sf.available_subtypes(fmt)):
        raise Unavailable(f"libsndfile no declara {fmt}/{subtype}")
    return np, sf


def inventory_audio():
    result = {}
    for name in ("numpy", "soundfile"):
        try:
            mod = __import__(name)
            row = {"version": getattr(mod, "__version__", None)}
            if name == "soundfile":
                row["libsndfile"] = getattr(mod, "__libsndfile_version__", None)
                row["formats"] = {
                    f: list(mod.available_subtypes(f))
                    for f in ("WAV", "FLAC") if f in mod.available_formats()
                }
            result[name] = row
        except Exception as exc:
            result[name] = {"error": error(exc)}
    return result


def fixture(root, fmt, bits, channels, rate):
    subtype = f"PCM_{bits}"
    np, sf = dependencies(fmt, subtype)
    limit = 1 << (bits - 1)
    pcm = np.random.default_rng(42).integers(
        -limit, limit, (1003, channels), dtype=np.int32
    )
    pcm[0, :] = -limit
    pcm[-1, :] = limit - 1
    pcm <<= 32 - bits
    path = root / f"fixture-{bits}.{fmt.lower()}"
    with create(path) as f:
        with sf.SoundFile(f.fileno(), mode="w", samplerate=rate,
                          channels=channels, format=fmt, subtype=subtype,
                          closefd=False) as writer:
            writer.write(pcm)
    return path, pcm, np, sf


def audio_pcm(root, fmt, bits, channels, rate):
    path, original, np, sf = fixture(root, fmt, bits, channels, rate)
    expected = (fmt, f"PCM_{bits}", rate, channels, len(original))
    fd = os.open(path, os.O_RDONLY)
    with owned_fd(fd):
        before = ident(os.fstat(fd))
        with sf.SoundFile(fd, closefd=False) as decoder:
            actual = (decoder.format, decoder.subtype, decoder.samplerate,
                      decoder.channels, decoder.frames)
            require(actual == expected, f"geometría/formato: {actual} != {expected}")
            cursor = 0
            for block in decoder.blocks(blocksize=127, dtype="int32", always_2d=True):
                require(block.dtype == np.dtype("int32") and block.ndim == 2
                        and block.shape[1] == channels, "dtype/forma inesperados")
                require(np.array_equal(block, original[cursor:cursor + len(block)]),
                        f"PCM distinto en frame {cursor}")
                cursor += len(block)
            require(cursor == len(original), "conteo por bloques incorrecto")
            for pos in (len(original) - 2, 0, len(original) // 2):
                require(decoder.seek(pos) == pos and decoder.tell() == pos,
                        "seek/tell incorrecto")
                block = decoder.read(2, dtype="float64", always_2d=True)
                expected_float = original[pos:pos + 2].astype(np.float64) / (2 ** 31)
                require(block.dtype == np.dtype("float64")
                        and np.array_equal(block, expected_float),
                        f"ventana float64 distinta en frame {pos}")
        require(ident(os.fstat(fd)) == before, "el decoder cerró o cambió el FD raíz")
    # No abrir otros FDs entre cerrar el nuestro e intentar fstat.
    try:
        os.fstat(fd)
    except OSError as exc:
        if exc.errno != errno.EBADF:
            raise
    else:
        raise AssertionError("el FD seguía válido tras el cierre del propietario")
    return {"geometry": actual, "pcm_exact": True, "int_dtype": "int32",
            "seek_dtype": "float64", "owner_close_checked": True}


@case("audio")
def wav_pcm16_mono(root):
    return audio_pcm(root, "WAV", 16, 1, 44100)


@case("audio")
def wav_pcm24_stereo(root):
    return audio_pcm(root, "WAV", 24, 2, 48000)


@case("audio")
def flac_pcm16_mono(root):
    return audio_pcm(root, "FLAC", 16, 1, 44100)


@case("audio")
def flac_pcm24_stereo(root):
    return audio_pcm(root, "FLAC", 24, 2, 48000)


def streaminfo(path):
    with path.open("rb") as f:
        data = f.read(42)
    if (len(data) != 42 or data[:4] != b"fLaC" or data[4] & 0x7f
            or int.from_bytes(data[5:8], "big") != 34):
        raise ValueError("cabecera FLAC nativa/STREAMINFO no verificable")
    packed = int.from_bytes(data[18:26], "big")
    return {
        "rate": packed >> 44,
        "channels": ((packed >> 41) & 7) + 1,
        "bits": ((packed >> 36) & 31) + 1,
        "frames": packed & ((1 << 36) - 1),
        "md5": data[26:42],
    }


def flac_md5(path):
    try:
        info = streaminfo(path)
    except (OSError, ValueError) as exc:
        return {"md5_status": "NOT_VERIFIABLE", "error": error(exc)}
    stored = info["md5"]
    if stored == bytes(16):
        return {"md5_status": "ABSENT", "stored": stored.hex()}
    if info["bits"] not in (16, 24):
        return {"md5_status": "NOT_VERIFIABLE", "stored": stored.hex(),
                "reason": "el verificador sólo cubre PCM16 y PCM24"}
    try:
        np, sf = dependencies("FLAC", f"PCM_{info['bits']}")
        # MD5 se usa sólo para reproducir el checksum del formato FLAC.
        md5 = hashlib.md5(usedforsecurity=False)
    except (Unavailable, ValueError, AttributeError, TypeError) as exc:
        return {"md5_status": "CAPABILITY_UNAVAILABLE",
                "stored": stored.hex(), "error": error(exc)}
    frames = 0
    try:
        with sf.SoundFile(path) as decoder:
            require((decoder.samplerate, decoder.channels, decoder.frames) ==
                    (info["rate"], info["channels"], info["frames"]),
                    "geometría de STREAMINFO distinta del decoder")
            require(decoder.format == "FLAC"
                    and decoder.subtype == f"PCM_{info['bits']}",
                    "formato/subtipo distinto del esperado")
            for block in decoder.blocks(blocksize=127, dtype="int32", always_2d=True):
                require(block.dtype == np.dtype("int32") and block.ndim == 2
                        and block.shape[1] == info["channels"],
                        "representación PCM inesperada")
                # int32 de libsndfile alineado a la izquierda: recuperar los
                # enteros válidos, intercalados por frame y luego por canal.
                values = block >> (32 - info["bits"])
                width = info["bits"] // 8
                md5.update(b"".join(int(v).to_bytes(width, "little", signed=True)
                                    for v in values.ravel(order="C")))
                frames += len(block)
        require(frames == info["frames"], "conteo PCM incompleto")
    except Exception as exc:
        return {"md5_status": "NOT_VERIFIABLE", "stored": stored.hex(),
                "frames_read": frames, "error": error(exc)}
    return {"md5_status": "MATCH" if md5.digest() == stored else "MISMATCH",
            "stored": stored.hex(), "computed": md5.hexdigest(),
            "bits": info["bits"], "channels": info["channels"], "frames": frames}


def md5_case(root, bits, variant):
    path, _, _, _ = fixture(root, "FLAC", bits, 1 if bits == 16 else 2, 44100)
    target = path
    if variant != "normal":
        data = bytearray(path.read_bytes())
        old = streaminfo(path)["md5"]
        if variant == "absent":
            data[26:42] = bytes(16)
        else:
            # Control conocido: usar una huella no nula y distinta del PCM
            # que acabamos de generar. No tocar el fixture fuente.
            baseline = flac_md5(path)
            emit("md5_observation", variant="baseline", **baseline)
            if baseline["md5_status"] in ("CAPABILITY_UNAVAILABLE", "NOT_VERIFIABLE"):
                raise Unavailable("no se puede recalcular el MD5 del control")
            require(baseline["md5_status"] == "MATCH",
                    "el fixture fuente no tiene un MD5 verificado")
            changed = bytearray(old)
            changed[0] ^= 1
            if not any(changed):
                changed[1] = 1
            data[26:42] = changed
        target = put(root / f"md5-{variant}.flac", data)
    result = flac_md5(target)
    emit("md5_observation", variant=variant, **result)
    observed = result["md5_status"]
    if observed == "CAPABILITY_UNAVAILABLE":
        raise Unavailable("capacidad de verificación MD5 no disponible")
    if variant == "normal" and observed == "ABSENT":
        raise Unavailable("el codificador no escribió un MD5 verificable")
    if variant == "wrong" and observed == "NOT_VERIFIABLE":
        # Si el backend rechaza la decodificación no se obtuvo un MD5
        # calculado: no etiquetar ese desenlace como MISMATCH verificado.
        raise Unavailable("el backend no permitió verificar el control alterado")
    expected = {"normal": "MATCH", "absent": "ABSENT", "wrong": "MISMATCH"}[variant]
    require(observed == expected, f"MD5 observado {observed}; esperado {expected}")
    return result


@case("audio")
def flac_md5_pcm16(root):
    return md5_case(root, 16, "normal")


@case("audio")
def flac_md5_pcm24(root):
    return md5_case(root, 24, "normal")


@case("audio")
def flac_md5_absent_control(root):
    return md5_case(root, 16, "absent")


@case("audio")
def flac_md5_wrong_control(root):
    return md5_case(root, 24, "wrong")


def raw_hash(fd):
    pread = feature("pread")
    sha = hashlib.sha256()
    offset = 0
    while True:
        data = candidate(pread, fd, 65536, offset)
        if not data:
            return {"bytes": offset, "sha256": sha.hexdigest()}
        sha.update(data)
        offset += len(data)


def truncation(root, fmt):
    path, _, _, sf = fixture(root, fmt, 16, 1, 44100)
    with owned_fd(os.open(path, os.O_RDONLY)) as fd:
        old = os.fstat(fd)
        before = raw_hash(fd)
        with sf.SoundFile(fd, closefd=False) as decoder:
            expected = decoder.frames
            with path.open("r+b") as writer:
                require(ident(os.fstat(writer.fileno())) == ident(old),
                        "el descriptor escritor no corresponde al fixture")
                writer.truncate(64)
            try:
                block = decoder.read(expected, dtype="int32", always_2d=True)
                reading = {"frames_returned": len(block)}
            except Exception as exc:
                reading = {"decoder_error": error(exc)}
        after = raw_hash(fd)
        require(ident(os.fstat(fd)) == ident(old), "no se truncó el mismo objeto")
        require(before["bytes"] != after["bytes"]
                and before["sha256"] != after["sha256"],
                "la guarda independiente no detectó el truncamiento")
    return {"declared_frames": expected, "decoder": reading,
            "before": before, "after": after, "guard_detected_change": True}


@case("audio")
def truncate_open_wav(root):
    return truncation(root, "WAV")


@case("audio")
def truncate_open_flac(root):
    return truncation(root, "FLAC")


def rename_noreplace(source, target):
    try:
        import ctypes
        operation = ctypes.CDLL(None, use_errno=True).renameat2
    except (ImportError, OSError, AttributeError) as exc:
        raise Unavailable("renameat2 no está accesible en ctypes/libc") from exc
    operation.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    # ABI Linux/Android: AT_FDCWD=-100, RENAME_NOREPLACE=1.
    if operation(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(source), None, str(target))


@case("publish")
def rename_collision_and_publish(root):
    stage = mkdir(root / "stage")
    existing = mkdir(root / "existing")
    put(stage / "manifest.txt", b"prepared\n")
    foreign = put(existing / "foreign.bin", b"do not replace")
    before = ident(stage.stat())
    try:
        candidate(rename_noreplace, stage, existing)
    except OSError as exc:
        if exc.errno != errno.EEXIST:
            raise
        collision = error(exc)
    else:
        raise AssertionError("se aceptó la colisión con un destino existente")
    require(foreign.read_bytes() == b"do not replace" and stage.is_dir(),
            "la colisión alteró el fixture de destino o staging")
    final = root / "published"
    candidate(rename_noreplace, stage, final)
    emit("moved", source=str(stage), destination=str(final), **record(final.lstat()))
    require(not stage.exists() and ident(final.stat()) == before
            and (final / "manifest.txt").read_bytes() == b"prepared\n",
            "resultado distinto o incompleto tras el rename")
    return {"collision": collision, "foreign_preserved": True,
            "published_same_object": True, "durability_confirmed": False}


def sync_case(root, is_directory):
    path = mkdir(root / "sync-dir") if is_directory else put(root / "sync.bin", b"data")
    flags = (os.O_RDONLY | feature("O_DIRECTORY")) if is_directory else os.O_RDWR
    with owned_fd(os.open(path, flags)) as fd:
        candidate(feature("fsync"), fd)
    return {"kind": "directory" if is_directory else "file",
            "fsync_returned_success": True, "durability_confirmed": False}


@case("publish")
def fsync_file(root):
    return sync_case(root, False)


@case("publish")
def fsync_directory(root):
    return sync_case(root, True)


def command_info(*args):
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=5)
        return {"argv": args, "exit": p.returncode,
                "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": args, "error": error(exc)}


def mount_info(path):
    def unescape(value):
        return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)
    matches = []
    try:
        for line in Path("/proc/self/mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            fields, fs = left.split(), right.split()
            point = unescape(fields[4])
            if str(path) == point or str(path).startswith(point.rstrip("/") + "/"):
                matches.append((len(point), {
                    "mountpoint": point, "filesystem": fs[0], "device": fields[2],
                    "source": unescape(fs[1]), "mount_options": fields[5],
                }))
    except (OSError, ValueError, IndexError) as exc:
        return {"mountpoint": None, "filesystem": None, "error": error(exc)}
    if not matches:
        return {"mountpoint": None, "filesystem": None}
    return max(matches, key=lambda item: item[0])[1]


def worker(group, name, path):
    start = time.monotonic()
    try:
        result = {"status": "PASS", "observed": GROUPS[group][name](path)}
    except Unavailable as exc:
        result = {"status": "NOT_EXECUTED", "error": error(exc)}
    except Exception as exc:
        result = {"status": "FAIL", "error": error(exc),
                  "traceback": traceback.format_exc()}
    emit("case", group=group, test=name,
         elapsed_s=round(time.monotonic() - start, 6), **result)


def child_output(command, timeout):
    try:
        p = subprocess.run(command, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        return p.stdout, p.stderr, p.returncode, None
    except subprocess.TimeoutExpired as exc:
        def text(value):
            return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""
        return text(exc.stdout), text(exc.stderr), None, {
            "status": "FAIL", "error": error(exc), "timeout_s": timeout,
        }
    except OSError as exc:
        return "", "", None, {"status": "NOT_EXECUTED", "error": error(exc)}


def run_case(group, name, run, timeout, write):
    folder = run / name
    key = {"group": group, "test": name}
    try:
        folder.mkdir(mode=0o700)
        write({"event": "created", "path": str(folder), "kind": "case_directory",
               **key, **record(folder.lstat())})
    except OSError as exc:
        result = {"status": "NOT_EXECUTED", "error": error(exc)}
    else:
        argv = [sys.executable, str(SCRIPT), "--_worker", group, name, str(folder)]
        out, stderr, rc, failed = child_output(argv, timeout)
        terminal = None
        for line in out.splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                row = {"event": "worker_output", "text": line}
            if not isinstance(row, dict):
                row = {"event": "worker_output", "text": line}
            if row.get("event") == "case":
                terminal = row
            else:
                write({**row, **key})
        if stderr:
            write({"event": "worker_stderr", "text": stderr, **key})
        if failed:
            result = failed
        elif rc != 0 or terminal is None:
            result = {"status": "FAIL", "worker_exit": rc,
                      "message": "proceso hijo sin resultado válido"}
        else:
            result = terminal
    row = {"event": "case", **result, **key}
    write(row)
    print(f"{row['status']:12} {group}/{name}", flush=True)
    return row["status"]


def approved_base(path):
    base = path.expanduser().resolve(strict=True)
    if not base.is_dir() or base == base.parent:
        raise ValueError("--base debe ser un directorio de diagnóstico, no la raíz")
    for parent in (base, *base.parents):
        try:
            (parent / ".git").lstat()
        except FileNotFoundError:
            continue
        raise ValueError(f"--base está dentro de un árbol Git: {parent}")
    return base


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path,
                        help="directorio de diagnóstico existente fuera del repositorio")
    parser.add_argument("--location", required=True, choices=("private", "shared"),
                        help="etiqueta declarada por el operador")
    parser.add_argument("--group", choices=("all", *GROUPS), default="all")
    parser.add_argument("--timeout", type=float, default=30)
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error("--timeout debe ser mayor que 0 y como máximo 600")
    try:
        if os.getuid() == 0 or os.geteuid() == 0:
            raise ValueError("ejecutar sólo como usuario normal, sin root")
        base = approved_base(args.base)
        run = Path(tempfile.mkdtemp(prefix="audioinput-diag-", dir=base))
        print(f"RUN_DIR={run}", flush=True)
        report = run / "report.jsonl"
        handle = report.open("x", encoding="utf-8")
    except (OSError, ValueError) as exc:
        emit("setup", status="NOT_EXECUTED", args=sys.argv[1:], error=error(exc))
        return 2

    counts = collections.Counter()
    complete = False
    with handle:
        def write(row):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()

        write({"event": "created", "path": str(run), "kind": "run_directory",
               **record(run.lstat())})
        write({"event": "created", "path": str(report), "kind": "report",
               **record(os.fstat(handle.fileno()))})
        write({
            "event": "environment", "schema": 2, "args": sys.argv[1:],
            "location_declared": args.location, "resolved_base": str(base),
            "mount": mount_info(run), "architecture": platform.machine(),
            "kernel": platform.release(), "python": sys.version,
            "android_release": command_info("getprop", "ro.build.version.release"),
            "android_api": command_info("getprop", "ro.build.version.sdk"),
            "termux_version_env": os.environ.get("TERMUX_VERSION"),
            "termux_tools_package": command_info(
                "dpkg-query", "-W", "-f=${Version}", "termux-tools"
            ),
            "uid": os.getuid(),
            "features_exposed": {k: hasattr(os, k) for k in (
                "O_PATH", "O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY", "pread", "fsync"
            )},
            "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
        })
        out, stderr, rc, failure = child_output(
            [sys.executable, str(SCRIPT), "--_dependencies"], args.timeout
        )
        try:
            versions = json.loads(out)
        except ValueError:
            versions = None
        write({"event": "dependencies", "versions": versions, "exit": rc,
               "stderr": stderr, "failure": failure,
               "unparsed_stdout": out if versions is None else None})
        try:
            selected = GROUPS if args.group == "all" else (args.group,)
            for group in selected:
                for name in GROUPS[group]:
                    counts[run_case(group, name, run, args.timeout, write)] += 1
            complete = True
        except KeyboardInterrupt:
            write({"event": "interrupted", "message": "se conservan los restos"})
        finally:
            write({"event": "summary", "complete": complete,
                   "counts": dict(counts), "cleanup": "none",
                   "android_compatibility_claimed": False})
            print(f"REPORT={report}", flush=True)

    if not complete:
        return 130
    if counts["FAIL"]:
        return 1
    return 2 if counts["NOT_EXECUTED"] else 0


if __name__ == "__main__":
    # También rechazar ejecución privilegiada al invocar un hijo directamente.
    if os.getuid() == 0 or os.geteuid() == 0:
        emit("setup", status="NOT_EXECUTED", message="ejecutar sin root")
        sys.exit(2)
    if sys.argv[1:] == ["--_dependencies"]:
        print(json.dumps(inventory_audio(), ensure_ascii=False))
    elif len(sys.argv) == 5 and sys.argv[1] == "--_worker":
        worker(sys.argv[2], sys.argv[3], approved_base(Path(sys.argv[4])))
    else:
        sys.exit(main())
