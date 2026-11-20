#!/usr/bin/env python3
"""Diagnóstico aislado de E/S; sin motores, privilegios ni limpieza automática.

Ambito protegido por descriptores (O_NOFOLLOW + dir_fd): el recorrido y la
inspección de la ruta base, el sondeo de escritura y la creación del
directorio de ejecución y de los directorios de caso se realizan sobre
descriptores anclados, sin seguir enlaces simbólicos.

Limitación residual documentada: dentro del directorio de ejecución y de
cada directorio de caso (creados por este diagnóstico con modo 0700 y
propiedad del usuario efectivo, no compartidos), las operaciones de
creación/acceso a artefactos usan rutas relativas normales. Es aceptable
porque esos directorios son privados del diagnóstico; los enlaces
simbólicos que las pruebas crean en ellos son propios del fixture y se
abren siempre con O_NOFOLLOW. No se afirma protección por descriptor sobre
operaciones fuera de ese ciclo.
"""

import argparse
import collections
import errno
import hashlib
import json
import os
import platform
import re
import signal
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
    """Limitación de capacidad del entorno: el caso no puede ejecutarse.

    Se traduce en NOT_EXECUTED. No debe usarse para errores reales del
    diagnóstico (véase DiagnosticError).
    """
    pass


class ProcfsUnavailable(Unavailable):
    """procfs no montado o no expone los descriptores de archivo."""


class ProcfsAccessDenied(Unavailable):
    """procfs presente pero no accesible (p.ej. EACCES): capacidad no disponible."""


class OperationUnsupported(Unavailable):
    """Operación no soportada por el kernel o el filesystem."""


class DiagnosticError(Exception):
    """Error real del diagnóstico: se conserva como FAIL, no como incompatibilidad."""


class InvalidDescriptor(DiagnosticError):
    """El descriptor de archivo de referencia no es válido."""


class InsufficientPermission(DiagnosticError):
    """Permisos insuficientes para completar la operación."""


class InterruptedTermination(KeyboardInterrupt):
    """Interrupción durante una prueba; conserva el resultado de terminación.

    Se propaga para que el proceso principal informe el resultado real de la
    terminación controlada, sin descartarlo ni afirmar éxito sin evidencia.
    """

    def __init__(self, termination):
        super().__init__("interrumpido durante la prueba")
        self.termination = termination


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


def _is_under(path_str, prefix):
    """True si path_str cae bajo prefix (prefix no raíz)."""
    if not prefix or prefix == os.sep:
        return False
    try:
        return os.path.commonpath([path_str, prefix]) == prefix
    except ValueError:
        return False


def _walk_anchored(path):
    """Recorrido anclado por descriptores con O_NOFOLLOW (correcciones A1/A4/B).

    Examina TODOS los componentes de la ruta —incluido el primero de una ruta
    relativa, que se abre frente al anclaje real (el CWD real del proceso)—
    sin resolver enlaces simbólicos ni atravesarlos. Cada apertura se realiza
    con dir_fd del componente anterior y O_NOFOLLOW | O_DIRECTORY, de modo que
    un cambio de componentes entre operaciones (TOCTOU) no puede hacer que se
    siga un enlace.

    Los descriptores intermedios se CIERRAN después de abrir correctamente el
    siguiente componente; se devuelve únicamente el descriptor final, que
    seguirá perteneciendo al llamador. Los componentes ".." se rechazan
    explícitamente. Enlaces finales e intermedios se rechazan explícitamente.
    """
    raw = Path(path)
    parts = raw.parts or (".",)
    if raw.is_absolute():
        anchor_fd = os.open(os.sep, os.O_DIRECTORY | feature("O_NOFOLLOW"))
        components = parts[1:]
        resolved = os.sep + os.sep.join(components)
    else:
        # Anclaje real para rutas relativas: el CWD real (sin enlaces).
        anchor_fd = os.open(".", os.O_DIRECTORY | feature("O_NOFOLLOW"))
        components = parts
        resolved = os.path.join(os.getcwd(), *components)
    flags = feature("O_NOFOLLOW") | feature("O_DIRECTORY")
    current = anchor_fd
    try:
        for index, component in enumerate(components):
            if component == "..":
                raise ValueError(
                    f"componente '..' no admitido en la ruta base: {raw}"
                )
            kind = "final" if index == len(components) - 1 else "intermedio"
            try:
                child = os.open(component, flags, dir_fd=current)
            except OSError as exc:
                if exc.errno == errno.ELOOP:
                    raise ValueError(
                        f"componente {kind} simbólico en la ruta base: {component}"
                    ) from exc
                if exc.errno == errno.ENOTDIR:
                    raise ValueError(
                        f"componente no es un directorio: {component}"
                    ) from exc
                raise
            # Cerrar el descriptor del componente anterior tras abrir el
            # siguiente: solo el descriptor final queda abierto.
            try:
                os.close(current)
            except OSError:
                pass
            current = child
        return current, os.path.normpath(resolved)
    except BaseException:
        try:
            os.close(current)
        except OSError:
            pass
        raise


def _group_inspection(pgid):
    """Inspección de miembros del grupo/sesión mediante /proc (corrección F).

    Lee /proc/<pid>/stat para todo el conjunto de procesos y clasifica cada
    lectura: desaparecido (el proceso salió durante el recorrido), error de
    permisos, error de lectura o datos malformados. Devuelve un dict con:

      - state: "has_members" (membresía del grupo confirmada), "empty"
        (grupo vacío verificable: no hubo errores y ningún miembro),
        "incomplete" (inspección incompleta: hubo errores de permisos, de
        lectura o datos malformados) o "unavailable" (procfs no disponible).
      - group_members / session_members: conteos informativos.
      - counts: desagregado de lecturas (ok, disappeared, permission, read,
        malformed, listed).

    Interpretación documentada de /proc/<pid>/stat: después del campo comm
    (que puede contener espacios y paréntesis, por lo que se parsea desde el
    último ')'), los campos son: state(3), ppid(4), pgrp(5), session(6).
    Por tanto pgrp es fields[2] y session es fields[3]. Se vigila la
    pertenencia al GRUPO (pgrp) como objetivo de terminación (es lo que
    señaliza killpg). Los conteos de sesión son informativos: se explicita
    que no se confunden con la pertenencia al grupo original y que NO se
    afirma detectar procesos que escapen creando otra sesión.

    La incertidumbre nunca se convierte en confirmación positiva: si la
    inspección es incompleta, el estado es "incomplete", nunca "empty".
    """
    result = {"pgid": pgid, "state": "incomplete", "group_members": 0,
              "session_members": 0,
              "counts": {"listed": 0, "ok": 0, "disappeared": 0,
                         "permission": 0, "read": 0, "malformed": 0}}
    try:
        pids = [int(name) for name in os.listdir("/proc") if name.isdigit()]
    except OSError:
        result["state"] = "unavailable"
        return result
    result["counts"]["listed"] = len(pids)
    errors = 0
    for pid in pids:
        try:
            with open(f"/proc/{pid}/stat", "rb") as handle:
                data = handle.read()
        except FileNotFoundError:
            # El proceso desapareció durante el recorrido: no es un error
            # de inspección, pero impide confirmar vacío sin más contexto.
            result["counts"]["disappeared"] += 1
            errors += 1
            continue
        except PermissionError:
            result["counts"]["permission"] += 1
            errors += 1
            continue
        except OSError:
            result["counts"]["read"] += 1
            errors += 1
            continue
        result["counts"]["ok"] += 1
        try:
            # El campo comm puede contener espacios/paréntesis: parsear desde
            # el último ')'. pgrp = fields[2], session = fields[3].
            rparen = data.rfind(b")")
            if rparen == -1:
                result["counts"]["malformed"] += 1
                errors += 1
                continue
            fields = data[rparen + 2:].split()
            if len(fields) < 4:
                result["counts"]["malformed"] += 1
                errors += 1
                continue
            if int(fields[2]) == pgid:
                result["group_members"] += 1
            if int(fields[3]) == pgid:
                result["session_members"] += 1
        except (ValueError, IndexError):
            result["counts"]["malformed"] += 1
            errors += 1
            continue
    if result["group_members"]:
        result["state"] = "has_members"
    elif errors == 0 and result["counts"]["ok"] > 0:
        result["state"] = "empty"
    else:
        result["state"] = "incomplete"
    return result


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
    try:
        before = os.fstat(ref)
    except OSError as exc:
        if exc.errno == errno.EBADF:
            raise InvalidDescriptor(
                "el descriptor de referencia no es válido"
            ) from exc
        raise
    require(stat.S_ISREG(before.st_mode), "la referencia no es regular")
    try:
        fd = os.open(f"/proc/self/fd/{ref}", os.O_RDONLY)
    except FileNotFoundError as exc:
        # El descriptor es válido (acabamos de hacerle fstat), así que la ruta
        # /proc no resolvió: procfs no montado o no expone los descriptores.
        raise ProcfsUnavailable(
            "procfs no entregó un lector de la referencia (¿no montado?)"
        ) from exc
    except PermissionError as exc:
        # Sin acceso a procfs no se puede obtener el lector de la referencia:
        # es una capacidad opcional del entorno no disponible -> NOT_EXECUTED
        # (no un fallo funcional). Se conserva el errno/original en el informe.
        raise ProcfsAccessDenied(
            "procfs no accesible para abrir /proc/self/fd/<ref> (permisos)"
        ) from exc
    except OSError as exc:
        if exc.errno in UNSUPPORTED:
            raise OperationUnsupported(
                "apertura vía procfs no soportada por el kernel"
            ) from exc
        raise  # error real de apertura: se conserva como fallo
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
    except (Unavailable, ValueError, AttributeError, TypeError) as exc:
        return {"md5_status": "CAPABILITY_UNAVAILABLE",
                "stored": stored.hex(), "error": error(exc)}
    # MD5 solo reproduce el checksum del formato FLAC. Algunas plataformas no
    # admiten usedforsecurity=False: se clasifica como incapacidad, no como fallo.
    try:
        md5 = hashlib.md5(usedforsecurity=False)
    except (ValueError, TypeError, AttributeError) as exc:
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
    except AssertionError as exc:
        # Inconsistencia o fallo de decodificación real, no limitación de formato.
        return {"md5_status": "DECODE_ERROR", "stored": stored.hex(),
                "frames_read": frames, "error": error(exc)}
    except Exception as exc:
        return {"md5_status": "DECODE_ERROR", "stored": stored.hex(),
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
        libc = ctypes.CDLL(None, use_errno=True)
        operation = libc.renameat2
    except AttributeError as exc:
        # El símbolo renameat2 no existe en esta libc.
        raise Unavailable("símbolo renameat2 ausente en libc") from exc
    except (ImportError, OSError) as exc:
        raise Unavailable("libc inaccesible para cargar renameat2") from exc
    operation.argtypes = [
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
    ]
    operation.restype = ctypes.c_int
    # ABI Linux/Android: AT_FDCWD=-100, RENAME_NOREPLACE=1.
    if operation(-100, os.fsencode(source), -100, os.fsencode(target), 1):
        code = ctypes.get_errno()
        if code in (errno.ENOSYS, errno.ENOTSUP, errno.EOPNOTSUPP):
            # Syscall ausente en el kernel o no soportado por el filesystem:
            # limitación de capacidad, no un fallo del diagnóstico.
            raise Unavailable(f"renameat2 no disponible ({os.strerror(code)}, {code})")
        # EEXIST se propaga como OSError para que el llamador detecte la colisión
        # (no se sobrescribe el destino). El resto (p.ej. EACCES/EPERM) se conserva
        # como error operativo real.
        raise OSError(code, os.strerror(code), str(source), None, str(target))
    return None


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


def _open_fd_count():
    try:
        return len(os.listdir("/proc/self/fd"))
    except OSError as exc:
        raise Unavailable(
            "procfs no disponible para el conteo de descriptores"
        ) from exc


@case("paths")
def walk_absolute_ok(root):
    inner = mkdir(root / "a")
    mid = mkdir(inner / "b")
    leaf = mkdir(mid / "c")
    fd, resolved = _walk_anchored(str(leaf))
    try:
        st = os.fstat(fd)
        require(ident(st) == ident(leaf.lstat()),
                "el descriptor final no corresponde al directorio esperado")
        require(resolved == str(leaf), "la ruta resuelta no coincide")
        return {"resolved": resolved, "final_fd_valid": True}
    finally:
        os.close(fd)


@case("paths")
def walk_relative_ok(root):
    # El primer componente de una ruta relativa se examina frente al anclaje
    # real (el CWD real del proceso).
    parent = root.parent
    previous = os.getcwd()
    try:
        os.chdir(str(parent))
        fd, resolved = _walk_anchored(root.name)
        try:
            require(os.path.isabs(resolved),
                    "la ruta resuelta de una ruta relativa no es absoluta")
            require(ident(os.fstat(fd)) == ident(root.lstat()),
                    "el descriptor no corresponde al directorio relativo")
            return {"resolved": resolved, "anchored_to_real_cwd": True}
        finally:
            os.close(fd)
    finally:
        os.chdir(previous)


@case("paths")
def walk_dotdot_rejected(root):
    try:
        _walk_anchored(str(root / ".." / root.name))
    except ValueError as exc:
        require(".." in str(exc), "no se mencionó el componente '..'")
        return {"rejected": True, "reason": str(exc)}
    raise AssertionError("se acceptó un componente '..' en la ruta base")


@case("paths")
def walk_final_symlink_rejected(root):
    real = mkdir(root / "real-dir")
    link = root / "final-link"
    symlink(link, "real-dir")
    try:
        _walk_anchored(str(link))
    except ValueError as exc:
        require("simbólico" in str(exc), "no se clasificó como enlace simbólico")
        return {"rejected": True, "component": "final", "reason": str(exc)}
    raise AssertionError("se acceptó un enlace simbólico final")


@case("paths")
def walk_intermediate_symlink_rejected(root):
    outer = mkdir(root / "outer")
    target = mkdir(root / "target")
    symlink(outer / "redirect", str(target.name))
    leaf = mkdir(target / "leaf")
    try:
        _walk_anchored(str(outer / "redirect" / "leaf"))
    except ValueError as exc:
        require("simbólico" in str(exc), "no se clasificó como enlace simbólico")
        return {"rejected": True, "component": "intermedio", "reason": str(exc)}
    raise AssertionError("se acceptó un enlace simbólico intermedio")


@case("paths")
def walk_fd_closed_on_success(root):
    # Solo el descriptor final queda abierto tras el recorrido (B).
    inner = mkdir(root / "x")
    leaf = mkdir(inner / "y")
    baseline = _open_fd_count()
    fd, _ = _walk_anchored(str(leaf))
    try:
        during = _open_fd_count()
        require(during == baseline + 1,
                "se dejaron descriptores intermedios abiertos tras el recorrido")
    finally:
        os.close(fd)
    after = _open_fd_count()
    require(after == baseline, "no se cerraron todos los descriptores tras cerrar el final")
    return {"baseline": baseline, "during": during, "after": after}


@case("paths")
def walk_fd_closed_on_rejection(root):
    # En un rechazo no quedan descriptores abiertos del recorrido (B).
    real = mkdir(root / "real-dir2")
    link = root / "rej-link"
    symlink(link, "real-dir2")
    baseline = _open_fd_count()
    try:
        _walk_anchored(str(link))
    except ValueError:
        pass
    else:
        raise AssertionError("no se rechazó el enlace simbólico")
    after = _open_fd_count()
    require(after == baseline,
            "quedaron descriptores abiertos tras un recorrido rechazado")
    return {"baseline": baseline, "after": after}


@case("base")
def base_group_writable_blocked(root):
    # Un directorio escribible por grupo se rechaza: otros miembros del
    # grupo podrían modificarlo y no se puede demostrar su aislamiento (C).
    directory = mkdir(root / "grp-dir")
    os.chmod(str(directory), 0o770)
    analysis = analyze_base(directory, "private", probe_writability=True)
    blockers = _base_blockers(analysis, ([], []))
    require(any("grupo" in b for b in blockers),
            "no se detectó el bloqueo por grupo escribible")
    return {"blockers": blockers}


@case("base")
def base_world_writable_blocked(root):
    directory = mkdir(root / "world-dir")
    os.chmod(str(directory), 0o777)
    analysis = analyze_base(directory, "private", probe_writability=True)
    blockers = _base_blockers(analysis, ([], []))
    require(any("globalmente escribible" in b for b in blockers),
            "no se detectó el bloqueo por directorio globalmente escribible")
    return {"blockers": blockers}


@case("base")
def base_foreign_owner_blocked(root):
    # Sin privilegios no se puede crear un directorio de propietario ajeno; se
    # verifica la decisión sobre una inspección sintética (C).
    analysis = {"world_writable": False, "group_writable": False,
                "owned_by_current_user": False, "acl_present": False}
    blockers = _base_blockers(analysis, ([], []))
    require(any("propiedad" in b for b in blockers),
            "no se detectó el bloqueo por propiedad ajena")
    return {"blockers": blockers,
            "note": "inspección sintética: el cambio de propietario requiere privilegios"}


@case("base")
def base_storage_shared_classification(root):
    # Almacenamiento compartido se clasifica como compartido (D).
    detected, mount, caveat = _classify_storage("/sdcard/diag-cls-test")
    require(detected == "android_shared",
            f"la ruta compartida no se clasificó como android_shared: {detected}")
    return {"detected_class": detected, "caveat": caveat}


@case("base")
def base_storage_shared_precedence(root):
    # Con TERMUX_VERSION presente, una ruta compartida no se clasifica como
    # privada por precedencia de condiciones (D).
    previous = os.environ.get("TERMUX_VERSION")
    os.environ["TERMUX_VERSION"] = "test-precedence"
    try:
        detected, _, _ = _classify_storage("/sdcard/diag-cls-test")
    finally:
        if previous is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous
    require(detected == "android_shared",
            f"la precedencia no dejó la ruta compartida como android_shared: {detected}")
    return {"detected_class": detected}


@case("base")
def base_storage_generic_undetermined(root):
    # Una ubicación genérica, sin evidencia de montaje privado, queda en
    # clase indeterminada y no aprobable (D).
    directory = mkdir(root / "generic-dir")
    previous = os.environ.pop("TERMUX_VERSION", None)
    try:
        detected, _, _ = _classify_storage(str(directory))
        analysis = analyze_base(directory, "private", probe_writability=True)
    finally:
        if previous is not None:
            os.environ["TERMUX_VERSION"] = previous
    require(detected == "other", f"clasificación inesperada: {detected}")
    require(analysis["storage_suitable"] is False,
            "una ubicación genérica no debe ser aprobable")
    return {"detected_class": detected, "storage_suitable": False}


@case("term")
def terminate_parent_dies_descendant_holds_pipe(root):
    # El proceso principal termina, pero un descendiente conserva los pipes
    # abiertos: no confirmar sin revisar y terminar al grupo (E).
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
    )
    out, err, rc, failure = child_output(
        [sys.executable, "-c", code], 5, kill_wait=2.0
    )
    require(failure is not None and failure["status"] == "FAIL",
            "no se reportó el agotamiento del tiempo de espera")
    termination = failure["termination_detail"]
    require(termination["confirmed"] is True,
            "no se confirmó la terminación del grupo tras SIGKILL: "
            f"{termination['reason']}")
    return {"child_terminated": True, "termination": termination}


@case("term")
def terminate_descendant_survives_sigterm(root):
    # Un descendiente que ignora SIGTERM debe morir por SIGKILL y el grupo
    # debe quedar verificado vacío (E).
    code = (
        "import subprocess, sys\n"
        "subprocess.Popen([sys.executable, '-c',\n"
        " 'import signal, time; "
        "signal.signal(signal.SIGTERM, lambda *a: None); time.sleep(30)'])\n"
    )
    out, err, rc, failure = child_output(
        [sys.executable, "-c", code], 5, kill_wait=2.0
    )
    require(failure is not None and failure["status"] == "FAIL",
            "no se reportó el agotamiento del tiempo de espera")
    termination = failure["termination_detail"]
    require(termination["confirmed"] is True,
            "no se confirmó la terminación tras SIGKILL al grupo: "
            f"{termination['reason']}")
    return {"child_terminated": True, "termination": termination}


@case("term")
def proc_inspection_unknown_group_empty(root):
    # Un grupo que no existe se verifica vacío (cuando /proc es leíble).
    inspection = _group_inspection(2 ** 22)
    if inspection["state"] != "empty":
        raise Unavailable(
            "inspección de /proc no concluyente en este entorno: "
            f"{inspection['state']}"
        )
    require(inspection["group_members"] == 0,
            "un grupo inexistente reportó miembros")
    return {"state": inspection["state"], "counts": inspection["counts"]}


@case("term")
def proc_stat_field_interpretation(root):
    # Verificación de la interpretación de pgrp (fields[2]) y session
    # (fields[3]) de /proc/<pid>/stat (F).
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, errors="replace", start_new_session=True)
    try:
        with open(f"/proc/{p.pid}/stat", "rb") as handle:
            data = handle.read()
        rparen = data.rfind(b")")
        require(rparen != -1, "campo comm malformado")
        fields = data[rparen + 2:].split()
        require(len(fields) >= 4, "stat incompleto")
        pgrp, session = int(fields[2]), int(fields[3])
        require(pgrp == p.pid, f"pgrp {pgrp} != pid {p.pid}")
        require(session == p.pid, f"session {session} != pid {p.pid}")
        inspection = _group_inspection(p.pid)
        require(inspection["state"] == "has_members",
                "la inspección no detectó al líder del grupo")
        return {"pgrp": pgrp, "session": session,
                "inspection_state": inspection["state"]}
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


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


def _confirm_group_termination(pgid):
    """Verifica por /proc que el grupo de procesos está vacío (corrección E).

    Devuelve (confirmed, reason, inspection). La confirmación positiva exige
    un estado "empty" verificable; "has_members", "incomplete" e
    "unavailable" se reportan como NO confirmado.
    """
    inspection = _group_inspection(pgid)
    state = inspection["state"]
    if state == "empty":
        return True, "grupo confirmado vacío tras la verificación", inspection
    if state == "has_members":
        return False, "miembros del grupo aún presentes tras SIGKILL", inspection
    if state == "incomplete":
        return False, ("inspección de /proc incompleta: no se puede confirmar "
                       "la terminación del grupo"), inspection
    return False, "procfs no disponible: no se puede confirmar la " \
                  "terminación del grupo", inspection


def _terminate(process, wait):
    """Terminación controlada del hijo y su grupo de procesos.

    El hijo se inicia con start_new_session=True, por lo que es líder de su
    propio grupo; así os.killpg alcanza también a los procesos descendientes.
    Estrategia: SIGTERM al grupo -> espera -> SIGKILL al grupo -> espera ->
    inspección de /proc del grupo (correcciones D1/E).

    NO se devuelve tras el SIGTERM aunque el proceso principal haya terminado:
    podría haber dejado descendientes vivos. Si el proceso principal ya
    terminó cuando se invoca la terminación (por ejemplo, porque sus
    descendientes mantuvieron los pipes abiertos), no se devuelve
    confirmed=True sin comprobar el grupo: se envía SIGKILL al grupo cuando
    corresponde y se verifica el resultado después. Devuelve un dict con
    "confirmed" (bool), "reason" e "inspection". La confirmación positiva
    requiere poll() del proceso principal y una inspección de /proc en estado
    "empty"; cualquier incertidumbre se reporta como NO confirmada. Esperas
    limitadas; no hay re-escalación ni esperas ilimitadas.
    """
    def alive():
        return process.poll() is None

    use_group = hasattr(os, "killpg")
    pgid = process.pid if use_group else None
    if not alive():
        # Caso E: el proceso principal ya terminó, pero sus descendientes
        # pueden conservar los pipes abiertos. No confirmar sin revisar el
        # grupo; enviar SIGKILL al grupo cuando corresponda y verificar después.
        if not use_group:
            return {"confirmed": False, "inspection": None,
                    "reason": "sin grupos de procesos: solo se observó la "
                              "muerte del hijo directo; los descendientes "
                              "podrían sobrevivir (límite documentado)"}
        inspection = _group_inspection(pgid)
        if inspection["state"] in ("has_members", "incomplete"):
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
            try:
                process.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                pass
        confirmed, reason, inspection = _confirm_group_termination(pgid)
        if confirmed:
            reason = "el hijo había terminado y el grupo se confirmó vacío"
        return {"confirmed": confirmed, "reason": reason,
                "inspection": inspection}
    for stage in ("term", "kill"):
        sig = signal.SIGTERM if stage == "term" else signal.SIGKILL
        if use_group:
            try:
                os.killpg(pgid, sig)
            except (OSError, ProcessLookupError):
                pass
        else:
            # Sin grupos de procesos: solo el hijo directo; los descendientes
            # podrían sobrevivir (límite documentado, no una garantía).
            try:
                process.send_signal(sig)
            except (OSError, ProcessLookupError):
                pass
        try:
            process.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            # Se continúa al siguiente stage: una espera agotada no impide
            # completar la secuencia de terminación.
            pass
    if not alive():
        if not use_group:
            # Sin killpg no hay evidencia sobre los descendientes: no afirmar
            # su terminación (límite documentado del mecanismo).
            return {"confirmed": False, "inspection": None,
                    "reason": "sin grupos de procesos: solo se observó la "
                              "muerte del hijo directo; los descendientes "
                              "podrían sobrevivir (límite documentado)"}
        confirmed, reason, inspection = _confirm_group_termination(pgid)
        return {"confirmed": confirmed, "reason": reason,
                "inspection": inspection}
    return {"confirmed": False, "inspection": None,
            "reason": "el hijo seguía vivo tras SIGTERM/SIGKILL"}


def child_output(command, timeout, kill_wait=2.0):
    """Ejecuta el comando en un proceso hijo con terminación controlada.

    El hijo se inicia en su propio grupo de procesos (start_new_session=True)
    para que la terminación alcance también a los descendientes (os.killpg).
    - Timeout: se termina al grupo (SIGTERM -> espera -> SIGKILL -> inspección
      de /proc) y se reporta el estado REAL (child_terminated solo si se
      confirma la terminación del hijo y de su grupo).
    - KeyboardInterrupt durante la prueba: se termina al grupo, se CONSERVA el
      resultado de terminación y se propaga para que se informe (D3).
    No se limpian archivos ni directorios; los artefactos parciales pueden quedar.
    """
    try:
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             text=True, errors="replace", start_new_session=True)
    except OSError as exc:
        return "", "", None, {"status": "NOT_EXECUTED", "error": error(exc)}
    try:
        out, err = p.communicate(timeout=timeout)
        return out, err, p.returncode, None
    except subprocess.TimeoutExpired as exc:
        termination = _terminate(p, kill_wait)
        terminated = termination["confirmed"]
        out = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        result = {
            "status": "FAIL", "error": error(exc), "timeout_s": timeout,
            "child_terminated": terminated,
            "termination_detail": termination,
            "process_group_used": True,
        }
        if not terminated:
            # No se pudo confirmar la terminación: estado de error inequívoco.
            result["termination_error"] = termination["reason"]
        return out, err, None, result
    except KeyboardInterrupt:
        termination = _terminate(p, kill_wait)
        raise InterruptedTermination(termination) from None


def run_case(group, name, run, timeout, write, location_declared, run_fd):
    folder = run / name
    key = {"group": group, "test": name}
    try:
        if run_fd is not None:
            # Creación relativa a descriptor (B): API estándar os.mkdir con
            # dir_fd; la inspección del directorio creado también por descriptor.
            os.mkdir(name, 0o700, dir_fd=run_fd)
            probe = os.open(name, os.O_RDONLY | feature("O_DIRECTORY")
                            | feature("O_NOFOLLOW"), dir_fd=run_fd)
            try:
                info = record(os.fstat(probe))
            finally:
                os.close(probe)
        else:
            os.mkdir(str(folder), mode=0o700)
            info = record(folder.lstat())
        write({"event": "created", "path": str(folder), "kind": "case_directory",
               **key, **info})
    except OSError as exc:
        result = {"status": "NOT_EXECUTED", "error": error(exc)}
    else:
        # Se transmite la ubicación declarada para que el trabajador evalue
        # el directorio con los mismos criterios que el proceso principal
        # (evita que un directorio privado de Termux aprobado por el proceso
        # principal sea rechazado por el trabajador). No se eliminan las
        # verificaciones de seguridad.
        argv = [sys.executable, str(SCRIPT), "--_worker", group, name,
                str(folder), location_declared]
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


def _classify_storage(base):
    """Clasifica la clase de almacenamiento contra información real de montaje.

    No se basa exclusivamente en TERMUX_VERSION, HOME o PREFIX: la ruta se
    contrasta con /proc/self/mountinfo y con la ubicación privada real de la
    aplicación Termux. La clasificación compartida tiene PRECEDENCIA sobre la
    privada para evitar que una ruta compartida se clasifique como privada por
    precedencia de condiciones. Devuelve (detected_class, mount, caveat).

    Se mantiene rechazado el almacenamiento compartido mientras no se demuestre
    su idoneidad para staging/publicación, y se mantienen rechazadas las
    ubicaciones genéricas o de clase indeterminada.
    """
    s = str(base)
    termux = os.environ.get("TERMUX_VERSION")
    private_prefixes = [
        p for p in ("/data/data/com.termux", os.environ.get("PREFIX") or "",
                   str(Path.home()))
        if p and p != os.sep
    ]
    shared_prefixes = ("/sdcard", "/storage/emulated", "/mnt/sdcard")
    # Precedencia: una ruta compartida nunca se clasifica como privada.
    for prefix in shared_prefixes:
        if _is_under(s, prefix):
            return ("android_shared", mount_info(s),
                    "almacenamiento compartido de Android: que sea escribible "
                    "NO demuestra que sea apropiado para staging/publicación "
                    "(scoped storage, MediaStore); no se afirma su seguridad "
                    "sin evidencia.")
    mount = mount_info(s)
    mount_point = (mount or {}).get("mountpoint")
    mount_ok = bool(mount_point) and _is_under(s, mount_point)
    if termux and private_prefixes and mount_ok:
        # Contrastar con la ubicación privada real de la aplicación Termux:
        # el punto de montaje debe estar anclado en la jerarquía privada y el
        # montaje no debe ser de clase compartida.
        mount_source = str((mount or {}).get("source") or "")
        if any(_is_under(mount_point, p) for p in private_prefixes) and not any(
            seg in mount_source for seg in ("sdcard", "emulated", "mtp")
        ):
            return ("termux_private", mount,
                    "almacenamiento privado de Termux, confirmado por el "
                    "montaje.")
    return ("other", mount,
            "clase de almacenamiento no determinable con la información de "
            "montaje disponible; no se aprueba por defecto.")


def analyze_base(base, location_declared=None, probe_writability=False,
                 base_fd=None):
    """Evalúa (sin aprobar por defecto) las condiciones del directorio base.

    No usa root ni modifica permisos ajenos. Las incertidumbres se registran
    como tales. El sondeo de escritura, si se solicita, crea y elimina únicamente
    sus propios artefactos; no limpia nada del diagnóstico. Cuando se provee
    base_fd, la inspección y el sondeo se realizan sobre el descriptor anclado
    (O_NOFOLLOW) y no sobre la ruta, para no dejar una ventana TOCTOU entre la
    comprobación y el uso.

    Campos consumidos por approved_base para la aprobación:
      - status: "OK" | "UNVERIFIABLE" | "REJECTED"
      - verified_writable: bool (solo si se sondeó) o None
      - storage_suitable: True solo si la clase de almacenamiento es
        fundamentada y verificable; en caso contrario False
      - world_writable / group_writable / group_authorized: hechos para que
        approved_base decida sobre riesgo de modificación por terceros
    """
    info = {"path": str(base), "location_declared": location_declared}
    if base_fd is not None:
        try:
            st = os.fstat(base_fd)
        except OSError as exc:
            info.update(status="UNVERIFIABLE", verified_writable=None,
                        storage_suitable=False, error=error(exc))
            return info
    else:
        try:
            st = base.lstat()
        except OSError as exc:
            info.update(status="UNVERIFIABLE", verified_writable=None,
                        storage_suitable=False, error=error(exc))
            return info
    mode = st.st_mode
    if stat.S_ISLNK(mode):
        info.update(status="REJECTED", verified_writable=None,
                    storage_suitable=False,
                    object_type="symlink",
                    reason="el objetivo es un enlace simbólico, no un directorio real")
        return info
    if not stat.S_ISDIR(mode):
        info.update(status="REJECTED", verified_writable=None,
                    storage_suitable=False,
                    object_type="other", reason="el objetivo no es un directorio")
        return info
    info["object_type"] = "directory"
    info["status"] = "OK"
    # A2: credenciales efectivas, grupos suplementarios y permisos reales.
    info["uid"] = os.getuid()
    info["euid"] = os.geteuid()
    info["gid"] = os.getgid()
    info["egid"] = os.getegid()
    info["supplementary_groups"] = list(os.getgroups())
    info["owner_uid"] = st.st_uid
    info["owner_gid"] = st.st_gid
    info["owned_by_current_user"] = (st.st_uid == os.geteuid())
    perms = mode & 0o777
    info["mode"] = oct(perms)
    info["world_writable"] = bool(perms & 0o002)
    info["group_writable"] = bool(perms & 0o020)
    info["owner_writable"] = bool(perms & 0o200)
    # Permisos reales del proceso efectivo (euid/egid + grupos suplementarios).
    effective_groups = set(os.getgroups())
    effective_groups.add(os.getegid())
    info["group_authorized"] = st.st_gid in effective_groups
    if os.geteuid() == 0:
        info["effective_can_write_mode"] = True
    elif st.st_uid == os.geteuid():
        info["effective_can_write_mode"] = bool(perms & 0o200)
    elif st.st_gid in effective_groups:
        info["effective_can_write_mode"] = bool(perms & 0o020)
    else:
        info["effective_can_write_mode"] = bool(perms & 0o002)
    verified = None
    if probe_writability:
        probe = {"attempted": True}
        writable = False
        probe_fd = None
        try:
            if base_fd is not None:
                # Sondeo anclado al descriptor: sin TOCTOU con la ruta.
                # API estándar os.mkdir con dir_fd (corrección A); los errores
                # de creación se capturan y quedan registrados en probe["error"].
                probe_name = "base-probe-" + os.urandom(6).hex()
                os.mkdir(probe_name, 0o700, dir_fd=base_fd)
                probe_fd = os.open(
                    probe_name,
                    os.O_RDONLY | feature("O_DIRECTORY") | feature("O_NOFOLLOW"),
                    dir_fd=base_fd,
                )
                probe_file_fd = os.open(
                    "w", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                    dir_fd=probe_fd,
                )
                os.write(probe_file_fd, b"x")
                os.close(probe_file_fd)
            else:
                probe_dir = tempfile.mkdtemp(prefix="base-probe-", dir=base)
                probe_file = Path(probe_dir) / "w"
                probe_file.write_bytes(b"x")
            probe["dir_created"] = True
            probe["file_created"] = True
            writable = True
            try:
                if base_fd is not None:
                    os.unlink("w", dir_fd=probe_fd)
                    os.rmdir(probe_name, dir_fd=base_fd)
                else:
                    probe_file.unlink()
                    os.rmdir(probe_dir)
                probe["self_cleaned"] = True
            except OSError as exc:
                probe["self_cleaned"] = False
                probe["clean_error"] = error(exc)
        except OSError as exc:
            probe["dir_created"] = False
            probe["file_created"] = False
            probe["error"] = error(exc)
        finally:
            if probe_fd is not None:
                try:
                    os.close(probe_fd)
                except OSError:
                    pass
        info["writability_probe"] = probe
        verified = writable
    else:
        info["writability_probe"] = {"attempted": False}
    info["verified_writable"] = verified
    # A3: clasificación contra información real de montaje (corrección D).
    # Almacenamiento compartido y genérico no se aprueban por ser escribibles;
    # si no se puede determinar la adecuación, se rechaza.
    detected, mount, caveat = _classify_storage(base)
    storage = {
        "termux_version": os.environ.get("TERMUX_VERSION"),
        "location_declared": location_declared,
        "detected_class": detected,
        "mount": mount,
        "caveat": caveat,
    }
    if detected == "android_shared":
        # No se aprueba por ser escribible; no hay condiciones verificables
        # que demuestren adecuación para staging/publicación.
        storage["suitability"] = "REJECTED_shared_not_demonstrated"
    elif detected == "termux_private":
        storage["suitability"] = (
            "termux_private_approved" if location_declared == "private"
            else "REJECTED_mismatch"
        )
    else:
        storage["suitability"] = "UNDETERMINED"
    info["android"] = storage
    info["storage_suitable"] = (storage["suitability"] == "termux_private_approved")
    return info


def _parent_audit(base):
    """Auditoría estática de los directorios padre (corrección C).

    Registra el modo de cada padre y devuelve bloqueos para riesgos
    relevantes: un padre globalmente escribible sin bit sticky permite a
    terceros renombrar/sustituir la entrada; se registran también los padres
    escribibles por grupo como riesgo residual documentado. No se modifican
    permisos ni propietarios ajenos.
    """
    rows = []
    blockers = []
    for parent in (base, *base.parents):
        try:
            st = parent.lstat()
        except OSError:
            break
        if not stat.S_ISDIR(st.st_mode):
            break
        perms = st.st_mode & 0o777
        row = {
            "path": str(parent), "mode": oct(perms),
            "world_writable": bool(perms & 0o002),
            "group_writable": bool(perms & 0o020),
            "sticky": bool(st.st_mode & 0o1000),
        }
        rows.append(row)
        if row["world_writable"] and not row["sticky"]:
            blockers.append(
                f"directorio padre globalmente escribible sin sticky: {parent}"
            )
    if rows:
        return rows, blockers
    return rows, blockers


def _base_blockers(analysis, parents):
    """Decisión de confianza sobre la ubicación (corrección C).

    No se considera confiable un grupo simplemente por pertenecer a él: un
    directorio escribible por grupo permite a otros miembros modificarlo, y
    no se puede demostrar el aislamiento de esos miembros, por lo que se
    rechaza. También se rechazan directorios que no sean propiedad del
    usuario efectivo, globalmente escribibles, con ACL presentes (no
    evaluables por este diagnóstico) y padres con riesgo de sustitución.
    """
    blockers = []
    if analysis.get("world_writable"):
        blockers.append(
            "directorio globalmente escribible: riesgo de modificación por terceros"
        )
    if analysis.get("group_writable"):
        blockers.append(
            "directorio escribible por grupo: otros miembros del grupo "
            "podrían modificarlo; no se puede demostrar aislamiento suficiente"
        )
    if not analysis.get("owned_by_current_user"):
        blockers.append(
            "directorio no propiedad del usuario efectivo: no se aprueba "
            "automáticamente"
        )
    if analysis.get("acl_present"):
        blockers.append(
            "ACL presentes en el directorio: no evaluables por este "
            "diagnóstico; no se puede demostrar aislamiento suficiente"
        )
    blockers.extend(parents[1])
    return blockers


def approved_base(path, location_declared=None):
    """Aprueba el directorio base tras un recorrido anclado por descriptores.

    Devuelve (base, base_fd, analysis). La ruta se recorre con dir_fd y
    O_NOFOLLOW examinando todos sus componentes (finales e intermedios,
    incluido el primero de una ruta relativa frente al anclaje real), de modo
    que no se resuelve ni se atraviesa ningún enlace simbólico y no queda una
    ventana TOCTOU entre inspección y uso (correcciones A1/A4/B). La aprobación
    depende de condiciones verificadas: estado OK, escritura verificada,
    clase de almacenamiento fundamentada (A3) y ausencia de riesgo de
    modificación por terceros (A2). Si cualquier comprobación posterior
    falla, se cerrara el descriptor anclado antes de rechazar. Devuelve el
    descriptor anclado para que el llamador realice creaciones sobre él.
    """
    raw = Path(path).expanduser()
    if os.geteuid() == 0:
        raise ValueError("--base no debe ejecutarse como root")
    # 1) Recorrido anclado: todos los componentes se examinan sin seguir
    #    enlaces simbólicos. Cualquier enlace final o intermedio se rechaza.
    base_fd, resolved = _walk_anchored(raw)
    base = Path(resolved)
    try:
        # 2) La aprobación depende de condiciones verificadas sobre el
        #    descriptor, no solo de registrar la ruta.
        analysis = analyze_base(base, location_declared, probe_writability=True,
                                base_fd=base_fd)
        # Detección de ACL (solo lectura; no se modifica nada ajeno).
        try:
            xattrs = os.listxattr(str(base), follow_symlinks=False)
        except (OSError, AttributeError):
            xattrs = None
        analysis["acl_present"] = "system.posix_acl" in (xattrs or [])
        # Auditoría de padres.
        parents, parent_blockers = _parent_audit(base)
        analysis["parents"] = parents
        if analysis["status"] != "OK":
            raise ValueError(f"--base rechazado: {analysis.get('reason')}")
        if analysis.get("verified_writable") is not True:
            raise ValueError("--base: la capacidad de escritura no pudo verificarse; no se aprueba")
        if not analysis.get("storage_suitable", False):
            raise ValueError(
                "--base: la clase de almacenamiento no es apropiada o no está "
                "fundamentada; no se aprueba"
            )
        # A2: decisión de confianza (propiedad, permisos, riesgo de terceros).
        blockers = _base_blockers(analysis, (parents, parent_blockers))
        if blockers:
            raise ValueError("--base rechazado: " + "; ".join(blockers))
        if base == base.parent:
            raise ValueError("--base debe ser un directorio de diagnóstico, no la raíz")
        for parent in (base, *base.parents):
            try:
                (parent / ".git").lstat()
            except FileNotFoundError:
                continue
            raise ValueError(f"--base está dentro de un árbol Git: {parent}")
        emit("approved_base", **analysis)
        return base, base_fd, analysis
    except BaseException:
        # Cerrar el descriptor anclado si cualquier comprobación falla (B).
        try:
            os.close(base_fd)
        except OSError:
            pass
        raise


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
    base_fd = None
    run_fd = None
    try:
        if os.getuid() == 0 or os.geteuid() == 0:
            raise ValueError("ejecutar sólo como usuario normal, sin root")
        base, base_fd, base_analysis = approved_base(args.base, args.location)
        # Crear el directorio de ejecución sobre el descriptor anclado
        # (O_NOFOLLOW), sin recurrir a una ruta que podría cambiar entre
        # comprobaciones (A4). API estándar os.mkdir con dir_fd (A).
        run_name = "audioinput-diag-" + os.urandom(6).hex()
        os.mkdir(run_name, 0o700, dir_fd=base_fd)
        run = base / run_name
        # Descriptor del directorio de ejecución para crear artefactos
        # relativos a descriptores (B).
        run_fd = os.open(run_name, os.O_DIRECTORY | feature("O_NOFOLLOW"),
                         dir_fd=base_fd)
        print(f"RUN_DIR={run}", flush=True)
        report = run / "report.jsonl"
        report_fd = os.open("report.jsonl", os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                            0o600, dir_fd=run_fd)
        handle = os.fdopen(report_fd, "w", encoding="utf-8")
    except (OSError, ValueError) as exc:
        for fd in (run_fd, base_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        emit("setup", status="NOT_EXECUTED", args=sys.argv[1:], error=error(exc))
        return 2

    counts = collections.Counter()
    complete = False
    try:
        with handle:
            def write(row):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
                handle.flush()

            write({"event": "created", "path": str(run), "kind": "run_directory",
                   **record(os.fstat(run_fd))})
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
                "uid": os.getuid(), "euid": os.geteuid(),
                "features_exposed": {k: hasattr(os, k) for k in (
                    "O_PATH", "O_NOFOLLOW", "O_NONBLOCK", "O_DIRECTORY", "pread", "fsync"
                )},
                "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            })
            write({"event": "approved_base_analysis", **base_analysis})
            try:
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
                selected = GROUPS if args.group == "all" else (args.group,)
                for group in selected:
                    for name in GROUPS[group]:
                        counts[run_case(group, name, run, args.timeout, write,
                                        args.location, run_fd)] += 1
                complete = True
            except KeyboardInterrupt as exc:
                # D3: conservar e informar el resultado de terminación, sin
                # afirmar que los descendientes terminaron sin evidencia.
                termination = getattr(exc, "termination", None)
                write({
                    "event": "interrupted",
                    "message": "se conservan los restos; los procesos hijos "
                               "se terminan de forma controlada",
                    "child_termination": termination,
                    "child_termination_confirmed": bool(
                        termination and termination.get("confirmed")
                    ),
                })
            finally:
                write({"event": "summary", "complete": complete,
                       "counts": dict(counts), "cleanup": "none",
                       "android_compatibility_claimed": False,
                       "partial_artifacts_may_remain": True,
                       "child_process_termination":
                           "controlled_sigterm_then_sigkill_process_group_with_procfs_verification",
                       "child_process_group": True})
                print(f"REPORT={report}", flush=True)
    finally:
        for fd in (run_fd, base_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass

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
    elif len(sys.argv) == 6 and sys.argv[1] == "--_worker":
        # El trabajador recibe la ubicación declarada para evaluar el
        # directorio con los mismos criterios que el proceso principal.
        base, base_fd, _ = approved_base(Path(sys.argv[4]), sys.argv[5])
        try:
            worker(sys.argv[2], sys.argv[3], base)
        finally:
            os.close(base_fd)
    else:
        sys.exit(main())
