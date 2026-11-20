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


def _close_chain(chain):
    """Cierra una cadena de descriptores registrando los errores (asunto 3).

    Devuelve (closed, failed): los descriptores cuyo cierre se confirmó y
    los cuyos cierres fallaron (con su error). Un descriptor cuyo cierre
    falló queda en estado INCIERTO: no se reutiliza y no se declara como
    cerrado.
    """
    closed = []
    failed = []
    for fd in chain:
        try:
            os.close(fd)
            closed.append(fd)
        except OSError as exc:
            failed.append({"fd": fd, "error": error(exc)})
    return closed, failed


def _walk_anchored_chain(path):
    """Recorrido anclado que conserva la CADENA de descriptores (root..final).

    Como _walk_anchored, pero en lugar de cerrar los descriptores
    intermedios los conserva en una lista, de modo que la auditoría de
    padres pueda inspeccionar cada objeto mediante fstat sobre el propio
    descriptor (sin rutas, sin TOCTOU). Devuelve (chain_fds, resolved); el
    último elemento de chain_fds es el descriptor del directorio final y el
    llamador debe cerrar todos los descriptores de la cadena.
    """
    raw = Path(path)
    parts = raw.parts or (".",)
    if raw.is_absolute():
        anchor_fd = os.open(os.sep, os.O_DIRECTORY | feature("O_NOFOLLOW"))
        components = parts[1:]
        resolved = os.sep + os.sep.join(components)
    else:
        anchor_fd = os.open(".", os.O_DIRECTORY | feature("O_NOFOLLOW"))
        components = parts
        resolved = os.path.join(os.getcwd(), *components)
    flags = feature("O_NOFOLLOW") | feature("O_DIRECTORY")
    chain = [anchor_fd]
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
            chain.append(child)
            current = child
        return chain, os.path.normpath(resolved)
    except BaseException as exc:
        # Cierre de la cadena con registro de errores (asunto 3); los
        # descriptores con cierre fallido quedan en estado incierto.
        _, failed = _close_chain(chain)
        if failed:
            exc.chain_close_failed = failed
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
                "owned_by_current_user": False, "acl_state": "absent"}
    blockers = _base_blockers(analysis, ([], [], True))
    require(any("propiedad" in b for b in blockers),
            "no se detectó el bloqueo por propiedad ajena")
    return {"blockers": blockers,
            "note": "inspección sintética: el cambio de propietario requiere privilegios"}


@case("base")
def base_acl_present_blocked(root):
    # ACL presentes: no evaluables, se bloquea la aprobación (B).
    analysis = {"world_writable": False, "group_writable": False,
                "owned_by_current_user": True, "acl_state": "present"}
    blockers = _base_blockers(analysis, ([], [], True))
    require(any("ACL" in b for b in blockers),
            "no se detectó el bloqueo por ACL presentes")
    return {"blockers": blockers}


@case("base")
def base_acl_unknown_blocked(root):
    # Estado de ACL desconocido: no se aprueba automáticamente (B).
    analysis = {"world_writable": False, "group_writable": False,
                "owned_by_current_user": True, "acl_state": "unknown"}
    blockers = _base_blockers(analysis, ([], [], True))
    require(any("desconocido" in b for b in blockers),
            "no se detectó el bloqueo por ACL desconocida")
    return {"blockers": blockers}


@case("base")
def base_acl_query_error_unknown(root):
    # Si la consulta de ACL falla, el estado es unknown: ausencia de
    # información no es ausencia de ACL (B).
    state, err, method = _acl_state(root / "no-existe-acl-xyz")
    require(state == "unknown", f"estado inesperado: {state}")
    return {"state": state, "error": err, "method": method}


@case("base")
def base_parent_inspection_error_incomplete(root):
    # Si no se puede inspeccionar un padre (por descriptor), la auditoría es
    # incompleta y se rechaza la ubicación (punto 1).
    directory = mkdir(root / "audit-dir")
    chain, _ = _walk_anchored_chain(str(directory))
    try:
        target_fd = chain[-2]  # el padre (directorio de caso)
        previous = os.fstat

        def fake_fstat(fd, *args, **kwargs):
            if fd == target_fd:
                raise OSError(errno.EACCES, "simulado: inspección de padre")
            return previous(fd, *args, **kwargs)

        os.fstat = fake_fstat
        try:
            rows, blockers, complete = _parent_audit(chain, os.geteuid())
        finally:
            os.fstat = previous
    finally:
        for fd in chain:
            os.close(fd)
    require(complete is False, "la auditoría no se clasificó como incompleta")
    decision = _base_blockers({"acl_state": "absent"}, (rows, blockers, complete))
    require(any("incompleta" in b for b in decision),
            "no se bloqueó por auditoría de padres incompleta")
    return {"complete": complete, "blockers": decision}


@case("base")
def base_parent_group_writable_blocked(root):
    # Directorio padre escribible por grupo: no se puede demostrar
    # aislamiento suficiente, se bloquea (A).
    parent = mkdir(root / "grp-parent")
    os.chmod(str(parent), 0o775)
    child = mkdir(parent / "child")
    chain, _ = _walk_anchored_chain(str(child))
    try:
        rows, blockers, complete = _parent_audit(chain, os.geteuid())
    finally:
        for fd in chain:
            os.close(fd)
    require(complete is True, "auditoría incompleta inesperada")
    require(any("grupo" in b for b in blockers),
            "no se bloqueó el padre escribible por grupo")
    return {"blockers": blockers}


@case("base")
def base_parent_audit_descriptor_bound(root):
    # La auditoría de padres se realiza sobre la cadena de descriptores, no
    # sobre rutas (punto 1).
    inner = mkdir(root / "pb" / "pc")
    chain, resolved = _walk_anchored_chain(str(inner))
    try:
        rows, blockers, complete = _parent_audit(chain, os.geteuid())
    finally:
        for fd in chain:
            os.close(fd)
    require(complete is True, "auditoría incompleta inesperada")
    require(rows, "la auditoría no produjo filas")
    require(all("fd" in row for row in rows),
            "la auditoría no fue realizada por descriptores")
    require(rows[-1]["fd"] == chain[-1],
            "la fila del directorio base no usa el descriptor final")
    require(rows[-1]["mode"] == oct(inner.lstat().st_mode & 0o777),
            "el modo del base por descriptor no coincide con el objeto")
    return {"rows": len(rows), "resolved": resolved}


@case("base")
def base_acl_state_fd_method(root):
    # La consulta de ACL se realiza sobre el descriptor cuando la plataforma
    # lo permite; si no, el estado es unknown (punto 1).
    directory = mkdir(root / "acl-fd")
    fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        state, err, method = _acl_state(directory, fd)
    finally:
        os.close(fd)
    require(method == "fd", f"método inesperado: {method}")
    require(state in ("absent", "unknown"), f"estado inesperado: {state}")
    return {"state": state, "method": method, "error": err}


@case("base")
def base_parent_sticky_foreign_owner_blocked(root):
    # Padre globalmente escribible con sticky pero propietario no confiable:
    # no se aprueba automáticamente (punto 2).
    row = {"fd": 99, "world_writable": True, "sticky": True,
           "group_writable": False, "owner_uid": 123456}
    blockers = _parent_risk_blockers(row, os.geteuid())
    require(any("no confiable" in b for b in blockers),
            "no se bloqueó el padre sticky con propietario ajeno")
    return {"blockers": blockers}


@case("base")
def base_parent_sticky_trusted_owner_allowed(root):
    # Padre globalmente escribible con sticky y propietario confiable (el
    # usuario efectivo): sin bloqueo por esa política (punto 2).
    row = {"fd": 99, "world_writable": True, "sticky": True,
           "group_writable": False, "owner_uid": os.geteuid()}
    blockers = _parent_risk_blockers(row, os.geteuid())
    require(blockers == [], f"bloqueos inesperados: {blockers}")
    return {"blockers": blockers}


@case("base")
def base_parent_sticky_real_dir(root):
    # Padre real globalmente escribible con sticky, sin grupo escribible y
    # propiedad del usuario efectivo: la auditoría no bloquea por sticky
    # (punto 2).
    parent = mkdir(root / "sticky-parent")
    os.chmod(str(parent), 0o1707)
    child = mkdir(parent / "child")
    chain, _ = _walk_anchored_chain(str(child))
    try:
        rows, blockers, complete = _parent_audit(chain, os.geteuid())
    finally:
        for fd in chain:
            os.close(fd)
    require(complete is True, "auditoría incompleta inesperada")
    require(not any("globalmente" in b or "grupo" in b for b in blockers),
            f"bloqueos inesperados para padre sticky confiable: {blockers}")
    return {"blockers": blockers}


@case("base")
def storage_home_inside_private_ok(root):
    # HOME dentro de la ubicación privada esperada: evidencia suficiente,
    # con el montaje vinculado al descriptor abierto (asunto 2).
    previous = {k: os.environ.get(k) for k in ("TERMUX_VERSION", "HOME")}
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        st = os.fstat(fd)
        dev = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
        os.environ["TERMUX_VERSION"] = "test-home-private"
        os.environ["HOME"] = "/data/data/com.termux/files/home"
        globals()["_read_mountinfo"] = lambda: [
            {"mountpoint": "/", "device": dev, "filesystem": "ext4",
             "source": "/dev/block/dm-0", "mount_options": "rw"},
        ]
        try:
            detected, _, _ = _classify_storage(
                "/data/data/com.termux/files/home/diag-private", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    require(detected == "termux_private",
            f"clasificación inesperada: {detected}")
    return {"detected_class": detected}


@case("base")
def storage_home_outside_private_rejected(root):
    # HOME apuntando a una ubicación ajena: no es evidencia de almacenamiento
    # privado (punto 3).
    previous = {k: os.environ.get(k) for k in ("TERMUX_VERSION", "HOME")}
    previous_mount = globals()["mount_info"]
    os.environ["TERMUX_VERSION"] = "test-home-outside"
    os.environ["HOME"] = "/tmp/fakehome-diag-xyz"
    globals()["mount_info"] = lambda path: {
        "mountpoint": "/", "filesystem": "ext4", "device": "none",
        "source": "/dev/block/dm-0", "mount_options": "rw",
    }
    try:
        detected, _, _ = _classify_storage("/tmp/fakehome-diag-xyz/diag")
    finally:
        globals()["mount_info"] = previous_mount
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    require(detected == "other", f"clasificación inesperada: {detected}")
    return {"detected_class": detected}


@case("base")
def storage_termux_env_without_evidence(root):
    # TERMUX_VERSION presente pero sin evidencia de ubicación privada: no se
    # clasifica como privado (punto 3).
    previous = os.environ.get("TERMUX_VERSION")
    previous_mount = globals()["mount_info"]
    os.environ["TERMUX_VERSION"] = "test-no-evidence"
    globals()["mount_info"] = lambda path: {
        "mountpoint": "/", "filesystem": "ext4", "device": "none",
        "source": "/dev/block/dm-0", "mount_options": "rw",
    }
    try:
        detected, _, _ = _classify_storage("/data/other-app/diag")
    finally:
        globals()["mount_info"] = previous_mount
        if previous is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous
    require(detected == "other", f"clasificación inesperada: {detected}")
    return {"detected_class": detected}


@case("base")
def storage_shared_precedence_with_altered_home(root):
    # HOME alterado hacia almacenamiento compartido: la precedencia de
    # rechazo se mantiene (punto 3).
    previous = {k: os.environ.get(k) for k in ("TERMUX_VERSION", "HOME")}
    os.environ["TERMUX_VERSION"] = "test-shared-home"
    os.environ["HOME"] = "/sdcard/fakehome-diag"
    try:
        detected, _, _ = _classify_storage("/sdcard/fakehome-diag/diag")
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    require(detected == "android_shared",
            f"precedencia de rechazo no se mantuvo: {detected}")
    return {"detected_class": detected}


@case("base")
def probe_close_failure_registered(root):
    # Fallo de cierre de los descriptores del sondeo: se registra, no se
    # declara autolimpieza y se conserva la información (punto 4).
    directory = mkdir(root / "probe-close")
    base_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                      | feature("O_NOFOLLOW"))
    refused = []
    previous_close = os.close

    def fake_close(fd, *args, **kwargs):
        if fd == base_fd or fd in (0, 1, 2):
            return previous_close(fd, *args, **kwargs)
        refused.append(fd)
        raise OSError(errno.EIO, "simulado: cierre")

    os.close = fake_close
    try:
        analysis = analyze_base(directory, "private", probe_writability=True,
                                base_fd=base_fd)
    finally:
        os.close = previous_close
        os.close(base_fd)
    probe = analysis["writability_probe"]
    require(probe.get("close_errors"), "no se registraron errores de cierre")
    require(probe["self_cleaned"] is False,
            "no se debe declarar autolimpieza con cierre fallido")
    require(probe.get("close_error"), "no se registró el error de cierre")
    for fd in refused:
        os.close(fd)
    return {"close_errors": probe["close_errors"], "refused_fds": refused}


@case("base")
def probe_cleanup_partial_file_residue(root):
    # Limpieza parcial: si la limpieza del archivo falla, se registra el
    # residuo con su ubicación y no se declara autolimpieza (punto 4).
    directory = mkdir(root / "probe-partial")
    base_fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                      | feature("O_NOFOLLOW"))
    previous_unlink = os.unlink

    def fake_unlink(path, *args, **kwargs):
        if path == "w":
            raise OSError(errno.EPERM, "simulado: unlink")
        return previous_unlink(path, *args, **kwargs)

    try:
        os.unlink = fake_unlink
        try:
            analysis = analyze_base(directory, "private",
                                    probe_writability=True, base_fd=base_fd)
        finally:
            os.unlink = previous_unlink
    finally:
        os.close(base_fd)
    probe = analysis["writability_probe"]
    require(probe["self_cleaned"] is False, "no se debe declarar autolimpieza")
    require(probe.get("residue"), "no se registró el residuo")
    kinds = [entry["kind"] for entry in probe["residue"]]
    require("file" in kinds, "no se registró el residuo del archivo")
    require(all("path" in entry and "error" in entry
                for entry in probe["residue"]),
            "el residuo no conserva ubicación y error")
    return {"residue": probe["residue"]}


@case("base")
def probe_partial_failure_fds_closed(root):
    # Fallo parcial del sondeo: se registra el fallo, se cierran todos los
    # descriptores y se limpian los artefactos propios (E).
    directory = mkdir(root / "probe-dir")
    baseline = _open_fd_count()
    fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    previous_open = os.open

    def fake_open(path, flags, *args, **kwargs):
        if path == "w":
            raise OSError(errno.EACCES, "simulado: apertura de sondeo")
        return previous_open(path, flags, *args, **kwargs)

    os.open = fake_open
    try:
        analysis = analyze_base(directory, "private", probe_writability=True,
                                base_fd=fd)
    finally:
        os.open = previous_open
        os.close(fd)
    probe = analysis["writability_probe"]
    require(probe.get("error") is not None, "no se registró el fallo del sondeo")
    require(probe["dir_created"] is True, "no se registró el directorio creado")
    require(probe["file_created"] is False,
            "no se debe registrar el archivo que no se creó")
    require(analysis["verified_writable"] is False,
            "no se debe marcar escribible tras un fallo")
    require(_open_fd_count() == baseline,
            "quedaron descriptores del sondeo abiertos tras el fallo")
    require(probe["self_cleaned"] is True, "no se limpió el directorio del sondeo")
    return probe


@case("base")
def probe_cleanup_failure_registers_residue(root):
    # Si la limpieza falla, se registra el residuo y su ubicación (E).
    directory = mkdir(root / "probe-dir2")
    fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    previous_rmdir = os.rmdir
    captured = {}

    def fake_rmdir(path, *args, **kwargs):
        captured["path"] = str(path)
        raise OSError(errno.ENOTEMPTY, "simulado: limpieza")

    try:
        os.rmdir = fake_rmdir
        try:
            analysis = analyze_base(directory, "private",
                                    probe_writability=True, base_fd=fd)
        finally:
            os.rmdir = previous_rmdir
    finally:
        os.close(fd)
    probe = analysis["writability_probe"]
    require(probe["self_cleaned"] is False, "no se registró la limpieza fallida")
    require(probe.get("residue"), "no se registró el residuo")
    require(captured.get("path"), "no se capturó la ubicación del residuo")
    return {"residue": probe["residue"], "clean_error": probe.get("clean_error")}


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


@case("base")
def storage_private_mount_point_above(root):
    # Punto de montaje superior (ancestro) a la ruta privada, vinculado al
    # descriptor abierto: compatible (asunto 2).
    previous_env = os.environ.get("TERMUX_VERSION")
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        st = os.fstat(fd)
        dev = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
        os.environ["TERMUX_VERSION"] = "test-mount-above"
        globals()["_read_mountinfo"] = lambda: [
            {"mountpoint": "/", "device": dev, "filesystem": "ext4",
             "source": "/dev/block/dm-0", "mount_options": "rw"},
        ]
        try:
            detected, mount, caveat = _classify_storage(
                "/data/data/com.termux/files/home/diag-private", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        if previous_env is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous_env
    require(detected == "termux_private",
            f"clasificación inesperada: {detected}")
    return {"detected_class": detected, "mount_point": mount["mountpoint"]}


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
def terminate_procfs_unavailable_descendant_alive(root):
    # Descendiente vivo y procfs no disponible: se intenta SIGKILL al grupo,
    # pero el resultado se mantiene NO confirmado (D).
    code = (
        "import subprocess, sys\n"
        "open(sys.argv[1], 'w').write(str(subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(30)']).pid))\n"
    )
    marker = root / "grandchild.pid"
    p = subprocess.Popen([sys.executable, "-c", code, str(marker)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, errors="replace", start_new_session=True)
    try:
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            raise AssertionError("el hijo no terminó tras la generación del descendiente")
        grandchild = int(marker.read_text().strip())
        require(os.path.exists(f"/proc/{grandchild}"),
                "el descendiente no quedó vivo para el caso")
        previous = globals()["_group_inspection"]
        globals()["_group_inspection"] = lambda pgid: {
            "pgid": pgid, "state": "unavailable", "group_members": 0,
            "session_members": 0,
            "counts": {"listed": 0, "ok": 0, "disappeared": 0,
                       "permission": 0, "read": 0, "malformed": 0},
        }
        try:
            result = _terminate(p, 2.0)
        finally:
            globals()["_group_inspection"] = previous
        require(result["confirmed"] is False,
                "no se debe confirmar la terminación sin evidencia")
        require(result["sigkill_attempted"] is True,
                "no se intentó SIGKILL al grupo cuando procfs no está disponible")
        require("procfs" in result["reason"],
                "no se informó la falta de procfs en la razón")
        # Observación del efecto real del SIGKILL intentado (intento, no
        # confirmación por inspección).
        deadline = time.monotonic() + 2.0
        descendant_gone = False
        while time.monotonic() < deadline:
            try:
                os.kill(grandchild, 0)
            except ProcessLookupError:
                descendant_gone = True
                break
            time.sleep(0.05)
        return {"confirmed": result["confirmed"],
                "sigkill_attempted": result["sigkill_attempted"],
                "reason": result["reason"],
                "descendant_gone_after_sigkill": descendant_gone}
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


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


@case("paths")
def parent_group_writable_trusted_group(root):
    # Grupo escribible con composición verificable: el grupo contiene SOLO al
    # usuario efectivo -> no se bloquea (asunto 1). No se confía en el nombre
    # ni el GID: se verifica la composición real.
    directory = mkdir(root / "grp-trusted")
    os.chmod(str(directory), 0o770)
    row = {"path": str(directory), "owner_uid": os.getuid(),
           "owner_gid": os.getgid(), "world_writable": False,
           "group_writable": True, "sticky": False}
    blockers = _parent_risk_blockers(row, os.getuid(),
                                     group_members={os.getuid()})
    require(not blockers, f"se bloqueó un grupo confiable: {blockers}")
    return {"blockers": blockers, "group_composition": "verificada"}


@case("paths")
def parent_group_writable_untrusted_group(root):
    # Grupo escribible con miembros distintos del usuario efectivo: se
    # bloquea, aunque el nombre del grupo sugiera confianza (asunto 1).
    directory = mkdir(root / "grp-untrusted")
    os.chmod(str(directory), 0o770)
    foreign_uid = os.getuid() + 1
    row = {"path": str(directory), "owner_uid": os.getuid(),
           "owner_gid": os.getgid(), "world_writable": False,
           "group_writable": True, "sticky": False}
    blockers = _parent_risk_blockers(row, os.getuid(),
                                     group_members={os.getuid(), foreign_uid})
    require(len(blockers) == 1 and "grupo" in blockers[0],
            "no se bloqueó el grupo con miembros ajenos")
    return {"blockers": blockers}


@case("paths")
def parent_group_writable_unknown_composition(root):
    # Composición del grupo que no se puede verificar: estado desconocido ->
    # se mantiene el rechazo (asunto 1).
    directory = mkdir(root / "grp-unknown")
    os.chmod(str(directory), 0o770)
    row = {"path": str(directory), "owner_uid": os.getuid(),
           "owner_gid": os.getgid(), "world_writable": False,
           "group_writable": True, "sticky": False}
    blockers = _parent_risk_blockers(row, os.getuid(), group_members=None)
    require(len(blockers) == 1 and "desconocido" in blockers[0],
            "no se bloqueó la composición desconocida")
    return {"blockers": blockers}


@case("paths")
def parent_audit_group_composition_verified(root):
    # _parent_audit verifica la composición del grupo escribible contra
    # /etc/group y marca la fila; si /etc/group no se puede leer, la
    # composición es desconocida (asunto 1).
    directory = mkdir(root / "grp-audit")
    os.chmod(str(directory), 0o770)
    fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        rows, blockers, complete = _parent_audit(
            [{"fd": fd, "path": str(directory)}], os.getuid())
        require(complete, "la auditoría debería ser completa")
        require(len(rows) == 1, "no se produjo la fila del padre")
        row = rows[0]
        require("group_members" in row,
                "no se registró la composición del grupo")
        require(not blockers or "grupo" in "".join(blockers),
                f"bloqueo inesperado: {blockers}")
    finally:
        os.close(fd)
    previous = globals()["_group_member_uids"]
    globals()["_group_member_uids"] = lambda gid: None
    try:
        fd = os.open(str(directory), os.O_RDONLY | os.O_DIRECTORY
                     | feature("O_NOFOLLOW"))
        try:
            rows, blockers, _ = _parent_audit(
                [{"fd": fd, "path": str(directory)}], os.getuid())
        finally:
            os.close(fd)
    finally:
        globals()["_group_member_uids"] = previous
    require(rows[0]["group_members"] is None,
            "no se registró la composición desconocida")
    require(any("desconocido" in b for b in blockers),
            "no se bloqueó la composición desconocida en la auditoría")
    return {"group_members": rows[0]["group_members"],
            "unknown_blocked": True}


@case("base")
def storage_mount_linked_to_open_object(root):
    # La información de montaje se vincula al descriptor abierto por
    # dispositivo + ancestro verificable (asunto 2).
    previous_env = os.environ.get("TERMUX_VERSION")
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        st = os.fstat(fd)
        dev = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
        os.environ["TERMUX_VERSION"] = "test-mount-fd"
        globals()["_read_mountinfo"] = lambda: [
            {"mountpoint": "/", "device": dev, "filesystem": "ext4",
             "source": "/dev/block/dm-0", "mount_options": "rw"},
        ]
        try:
            detected, mount, caveat = _classify_storage(
                "/data/data/com.termux/files/home/diag-linked", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        if previous_env is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous_env
    require(detected == "termux_private", f"clasificación inesperada: {detected}")
    require(mount and mount["device"] == dev,
            "el montaje no se vinculó al descriptor")
    return {"detected_class": detected, "linked_device": mount["device"]}


@case("base")
def storage_mount_path_replaced_after_open(root):
    # Ruta distinta de la del montaje del descriptor abierto: la vinculación
    # no puede coincidir con el descriptor -> indeterminado -> rechazo (asunto 2).
    previous_env = os.environ.get("TERMUX_VERSION")
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        st = os.fstat(fd)
        dev = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
        os.environ["TERMUX_VERSION"] = "test-mount-other"
        globals()["_read_mountinfo"] = lambda: [
            {"mountpoint": "/data/other-app", "device": dev, "filesystem": "ext4",
             "source": "/dev/block/dm-0", "mount_options": "rw"},
        ]
        try:
            detected, mount, caveat = _classify_storage(
                "/data/other-app/diag", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        if previous_env is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous_env
    require(detected == "other", f"clasificación inesperada: {detected}")
    return {"detected_class": detected, "mount": mount}


@case("base")
def storage_mount_device_mismatch(root):
    # Montaje con dispositivo distinto del del descriptor abierto: no hay
    # correspondencia verificable -> indeterminado (asunto 2).
    previous_env = os.environ.get("TERMUX_VERSION")
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        os.environ["TERMUX_VERSION"] = "test-mount-dev"
        globals()["_read_mountinfo"] = lambda: [
            {"mountpoint": "/", "device": "0:999", "filesystem": "ext4",
             "source": "/dev/block/other", "mount_options": "rw"},
        ]
        try:
            detected, mount, caveat = _classify_storage(
                "/data/data/com.termux/files/home/diag-dev", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        if previous_env is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous_env
    require(detected == "other", f"clasificación inesperada: {detected}")
    return {"detected_class": detected}


@case("base")
def storage_mount_info_inaccessible(root):
    # Información de montaje incompleta o inaccesible: no se puede vincular ->
    # indeterminado -> rechazo (asunto 2).
    previous_env = os.environ.get("TERMUX_VERSION")
    previous_mountinfo = globals()["_read_mountinfo"]
    fd = os.open(str(root), os.O_RDONLY | os.O_DIRECTORY
                 | feature("O_NOFOLLOW"))
    try:
        os.environ["TERMUX_VERSION"] = "test-mount-unreadable"

        def inaccessible():
            raise OSError(errno.EACCES, "simulado: mountinfo no accesible")

        globals()["_read_mountinfo"] = inaccessible
        try:
            detected, mount, caveat = _classify_storage(
                "/data/data/com.termux/files/home/diag-noinfo", fd)
        finally:
            globals()["_read_mountinfo"] = previous_mountinfo
    finally:
        os.close(fd)
        if previous_env is None:
            os.environ.pop("TERMUX_VERSION", None)
        else:
            os.environ["TERMUX_VERSION"] = previous_env
    require(detected == "other", f"clasificación inesperada: {detected}")
    require(mount is None, "no debe haber montaje sin vinculación")
    return {"detected_class": detected, "mount": mount}


@case("fd")
def chain_close_failure_during_approval(root):
    # Cierre fallido de un descriptor de la cadena durante la aprobación: se
    # registran los errores y no se declara el cierre limpio (asunto 3).
    inner = mkdir(root / "close-appr")
    events = []
    fd_marker = {}

    real_open = os.open
    real_close = os.close

    def spy_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        fd_marker.setdefault("fds", []).append(fd)
        return fd

    def spy_close(fd):
        if fd_marker["fds"] and fd != fd_marker["fds"][-1]:
            raise OSError(errno.EBADF, "simulado: cierre fallido")
        return real_close(fd)

    import io
    from contextlib import redirect_stdout
    buffer = io.StringIO()
    try:
        os.open = spy_open
        os.close = spy_close
        try:
            with redirect_stdout(buffer):
                base, base_fd, analysis = approved_base(str(inner))
        finally:
            os.open = real_open
            os.close = real_close
    finally:
        real_close(base_fd)
    for line in buffer.getvalue().splitlines():
        events.append(json.loads(line))
    parent_close = analysis["chain_close_parents"]
    require(parent_close["failed"], "no se registró el cierre fallido")
    require(any(e["event"] == "chain_close_warning" for e in events),
            "no se emitió la advertencia de cierre fallido")
    return {"failed": parent_close["failed"]}


@case("fd")
def chain_close_failure_during_rejection(root):
    # Cierre fallido durante un rechazo de la cadena: se registra y se
    # retiene la información del error (asunto 3).
    from contextlib import redirect_stdout
    import io
    events = []
    inner = mkdir(root / "close-rej")
    real_open = os.open
    real_close = os.close
    marker = {"fds": []}

    def spy_open(path, flags, *args, **kwargs):
        fd = real_open(path, flags, *args, **kwargs)
        marker["fds"].append(fd)
        return fd

    def spy_close(fd):
        if marker["fds"] and fd != marker["fds"][-1]:
            raise OSError(errno.EBADF, "simulado: cierre fallido")
        return real_close(fd)

    buffer = io.StringIO()
    raised = None
    try:
        os.open = spy_open
        os.close = spy_close
        try:
            with redirect_stdout(buffer):
                approved_base(str(Path(str(inner)) / ".." / ".." / "no-existe"))
        except (ValueError, OSError) as exc:
            raised = exc
        finally:
            os.open = real_open
            os.close = real_close
    finally:
        for fd in marker["fds"]:
            try:
                real_close(fd)
            except OSError:
                pass
    for line in buffer.getvalue().splitlines():
        events.append(json.loads(line))
    require(raised is not None, "no se rechazó la ruta inválida")
    require(raised.chain_close_failed,
            "no se retuvo la información del cierre fallido")
    require(any(e["event"] == "chain_close_error" for e in events),
            "no se emitió el error de cierre fallido")
    return {"failed": raised.chain_close_failed}


@case("fd")
def chain_close_clean_no_false_failure(root):
    # Cierre limpio de la cadena durante la aprobación: se registran los
    # descriptores cerrados, sin fallos ni declaraciones inciertas (asunto 3).
    inner = mkdir(root / "close-ok")
    _, _, analysis = approved_base(str(inner))
    parent_close = analysis["chain_close_parents"]
    require(parent_close["failed"] == [],
            "no debe haber cierres fallidos en una cadena sana")
    require(len(parent_close["closed"]) >= 1,
            "no se registró el cierre de los descriptores padres")
    return {"closed": parent_close["closed"]}


def command_info(*args):
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=5)
        return {"argv": args, "exit": p.returncode,
                "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"argv": args, "error": error(exc)}


def _read_mountinfo():
    """Lee y parsea /proc/self/mountinfo (asunto 2).

    Devuelve la lista de entradas de montaje o eleva la OSError si no se
    puede leer. Cada entrada mantiene el dispositivo (fields[2], p.ej.
    "0:34"), el punto de montaje y la fuente.
    """
    entries = []

    def unescape(value):
        return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), value)

    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        left, right = line.split(" - ", 1)
        fields, fs = left.split(), right.split()
        entries.append({
            "mountpoint": unescape(fields[4]),
            "device": fields[2],
            "filesystem": fs[0],
            "source": unescape(fs[1]),
            "mount_options": fields[5],
        })
    return entries


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


def _mount_for_fd(base_fd, path):
    """Vincula la información de montaje al objeto ABIERTO (asunto 2).

    La correspondencia verificable entre el descriptor y el montaje se
    compone de: (1) el dispositivo del objeto abierto (st_dev del descriptor
    convertido a "major:minor", que NO se asume por sí solo como identificador
    unívoco de montaje), (2) un punto de montaje que sea ANCESTRO de la ruta
    verificada por la cadena de descriptores, y (3) exactamente un candidato
    en mountinfo. Si hay cero candidatos, varios ambiguos, o la información
    de montaje es incompleta/inaccesible, devuelve None (estado indeterminado
    -> rechazo de la aprobación automática).
    """
    try:
        st = os.fstat(base_fd)
    except OSError:
        return None
    dev = f"{os.major(st.st_dev)}:{os.minor(st.st_dev)}"
    try:
        entries = _read_mountinfo()
    except OSError:
        return None
    candidates = [entry for entry in entries
                  if entry["device"] == dev
                  and _is_under(str(path), entry["mountpoint"])]
    if len(candidates) != 1:
        # 0: el montaje no corresponde al objeto; >1: ambigüedad.
        return None
    return candidates[0]


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
        # grupo; enviar SIGKILL al grupo cuando corresponda (incluido cuando
        # procfs no está disponible) y verificar después. Una señalización
        # intentada NO se confunde con terminación confirmada.
        if not use_group:
            return {"confirmed": False, "inspection": None,
                    "sigkill_attempted": False,
                    "reason": "sin grupos de procesos: solo se observó la "
                              "muerte del hijo directo; los descendientes "
                              "podrían sobrevivir (límite documentado)"}
        inspection = _group_inspection(pgid)
        sigkill_attempted = False
        if inspection["state"] in ("has_members", "incomplete", "unavailable"):
            # procfs no disponible: intentar SIGKILL al grupo cuando sea
            # posible (best effort), pero sin afirmar terminación.
            try:
                os.killpg(pgid, signal.SIGKILL)
                sigkill_attempted = True
            except (OSError, ProcessLookupError):
                sigkill_attempted = False
            try:
                process.wait(timeout=wait)
            except subprocess.TimeoutExpired:
                pass
        confirmed, reason, inspection = _confirm_group_termination(pgid)
        if confirmed:
            reason = "el hijo había terminado y el grupo se confirmó vacío"
        elif inspection["state"] == "unavailable" and sigkill_attempted:
            reason = (
                "procfs no disponible: se intentó SIGKILL al grupo, pero no "
                "hay evidencia suficiente para confirmar la terminación"
            )
        return {"confirmed": confirmed, "reason": reason,
                "inspection": inspection, "sigkill_attempted": sigkill_attempted}
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
                    "sigkill_attempted": False,
                    "reason": "sin grupos de procesos: solo se observó la "
                              "muerte del hijo directo; los descendientes "
                              "podrían sobrevivir (límite documentado)"}
        confirmed, reason, inspection = _confirm_group_termination(pgid)
        return {"confirmed": confirmed, "reason": reason,
                "inspection": inspection, "sigkill_attempted": True}
    return {"confirmed": False, "inspection": None,
            "sigkill_attempted": use_group,
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


def _classify_storage(base, base_fd=None):
    """Clasifica la clase de almacenamiento contra información real de montaje.

    No se basa exclusivamente en TERMUX_VERSION, HOME o PREFIX: la ruta se
    contrasta con /proc/self/mountinfo y con la ubicación privada real de la
    aplicación Termux. La clasificación compartida tiene PRECEDENCIA sobre la
    privada para evitar que una ruta compartida se clasifique como privada por
    precedencia de condiciones. Devuelve (detected_class, mount, caveat).

    La información de montaje se VINCULARÁ al objeto abierto mediante
    _mount_for_fd (dispositivo del descriptor + ancestro verificable +
    candidatu único). Si no se puede vincular al descriptor, el estado es
    indeterminado y se rechaza la aprobación automática.

    Para la clasificación privada se verifica que: (1) la ruta solicitada está
    dentro de la ubicación privada esperada, (2) el punto de montaje es un
    ANCESTRO compatible de la ruta, y (3) el montaje no es de clase
    compartida. NO se exige que el propio punto de montaje esté dentro del
    directorio privado de Termux: un montaje superior que cubra la ruta
    privada es compatible.

    Evidencia de ubicación privada: el prefijo canónico de almacenamiento
    privado de la aplicación Termux (/data/data/com.termux). PREFIX y HOME
    NO se aceptan como prueba por sí mismos: solo se incorporan como
    prefijos adicionales cuando POR SI MISMOS están dentro del prefijo
    canónico. Un HOME arbitrario o alterado no demuestra almacenamiento
    privado real; sin evidencia suficiente la clasificación es "other" (no
    se aprueba).

    Se mantiene rechazado el almacenamiento compartido mientras no se demuestre
    su idoneidad para staging/publicación, y se mantienen rechazadas las
    ubicaciones genéricas o de clase indeterminada.
    """
    s = str(base)
    termux = os.environ.get("TERMUX_VERSION")
    canonical = "/data/data/com.termux"
    private_prefixes = [canonical]
    for candidate in (os.environ.get("PREFIX"), str(Path.home())):
        # PREFIX/HOME solo constituyen evidencia si están dentro del prefijo
        # canónico privado; un HOME arbitrario o alterado no se acepta.
        if candidate and candidate != os.sep and _is_under(candidate, canonical):
            private_prefixes.append(candidate)
    shared_prefixes = ("/sdcard", "/storage/emulated", "/mnt/sdcard")
    # Precedencia: una ruta compartida nunca se clasifica como privada.
    for prefix in shared_prefixes:
        if _is_under(s, prefix):
            return ("android_shared", mount_info(s),
                    "almacenamiento compartido de Android: que sea escribible "
                    "NO demuestra que sea apropiado para staging/publicación "
                    "(scoped storage, MediaStore); no se afirma su seguridad "
                    "sin evidencia.")
    # Vinculación de la información de montaje al objeto abierto (asunto 2).
    if base_fd is not None:
        mount = _mount_for_fd(base_fd, s)
        mount_linked = mount is not None
    else:
        # Sin descriptor no hay vinculación verificable: estado indeterminado.
        mount = None
        mount_linked = False
    if termux and private_prefixes and mount_linked:
        # La ruta debe estar dentro de la ubicación privada esperada; NO se
        # exige que el punto de montaje esté dentro del directorio privado.
        if any(_is_under(s, p) for p in private_prefixes):
            mount_source = str((mount or {}).get("source") or "")
            if not any(seg in mount_source for seg in ("sdcard", "emulated",
                                                       "mtp")):
                return ("termux_private", mount,
                        "almacenamiento privado de Termux, confirmado por el "
                        "montaje vinculado al descriptor abierto.")
    return ("other", mount,
            "clase de almacenamiento no determinable: la información de "
            "montaje no pudo vincularse al objeto abierto o no es suficiente; "
            "no se aprueba por defecto.")


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
        probe_file_fd = None
        probe_name = None
        probe_dir = None
        probe_file = None
        # Artefactos propios creados, registrados para la limpieza (E).
        created = []
        try:
            if base_fd is not None:
                # Sondeo anclado al descriptor: sin TOCTOU con la ruta.
                # API estándar os.mkdir con dir_fd (corrección A); los errores
                # de creación se capturan y quedan registrados en probe["error"].
                probe_name = "base-probe-" + os.urandom(6).hex()
                os.mkdir(probe_name, 0o700, dir_fd=base_fd)
                probe["dir_created"] = True
                created.append(("dir", probe_name))
                probe_fd = os.open(
                    probe_name,
                    os.O_RDONLY | feature("O_DIRECTORY") | feature("O_NOFOLLOW"),
                    dir_fd=base_fd,
                )
                emit("created", path=str(base / probe_name),
                     kind="probe_directory", **record(os.fstat(probe_fd)))
                probe_file_fd = os.open(
                    "w", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600,
                    dir_fd=probe_fd,
                )
                created.append(("file", probe_name, "w"))
                os.write(probe_file_fd, b"x")
                os.close(probe_file_fd)
                probe_file_fd = None
                emit("created", path=str(base / probe_name / "w"),
                     kind="probe_file")
                probe["file_created"] = True
                writable = True
            else:
                probe_dir = tempfile.mkdtemp(prefix="base-probe-", dir=base)
                probe_file = Path(probe_dir) / "w"
                probe["dir_created"] = True
                created.append(("dir", probe_dir))
                probe_file.write_bytes(b"x")
                probe["file_created"] = True
                created.append(("file", probe_dir, "w"))
                emit("created", path=str(probe_dir), kind="probe_directory",
                     **record(probe_dir.lstat()))
                emit("created", path=str(probe_file), kind="probe_file",
                     **record(probe_file.lstat()))
                writable = True
        except OSError as exc:
            probe["dir_created"] = probe.get("dir_created", False)
            probe["file_created"] = probe.get("file_created", False)
            probe["error"] = error(exc)
        finally:
            # Limpiar SOLO los artefactos propios creados (y cuya propiedad se
            # acredita por haberlos creado nosotros), incluso si falló una
            # operación intermedia. Nunca se elimina nada ajeno. Se
            # diferencia la limpieza de archivos y de directorios.
            residue = []
            cleanup_errors = []
            if base_fd is not None:
                if probe_fd is not None and ("file", probe_name, "w") in created:
                    try:
                        os.unlink("w", dir_fd=probe_fd)
                    except OSError as exc:
                        residue.append({"kind": "file",
                                        "path": str(base / probe_name / "w"),
                                        "error": error(exc)})
                        cleanup_errors.append(error(exc))
                if probe_name is not None and ("dir", probe_name) in created:
                    try:
                        os.rmdir(probe_name, dir_fd=base_fd)
                    except OSError as exc:
                        residue.append({"kind": "directory",
                                        "path": str(base / probe_name),
                                        "error": error(exc)})
                        cleanup_errors.append(error(exc))
            else:
                if probe_file is not None:
                    try:
                        probe_file.unlink()
                    except OSError as exc:
                        residue.append({"kind": "file", "path": str(probe_file),
                                        "error": error(exc)})
                        cleanup_errors.append(error(exc))
                if probe_dir is not None:
                    try:
                        os.rmdir(probe_dir)
                    except OSError as exc:
                        residue.append({"kind": "directory",
                                        "path": str(probe_dir),
                                        "error": error(exc)})
                        cleanup_errors.append(error(exc))
            # Cierre de descriptores, registrando los errores de cierre.
            close_errors = []
            for label, fd in (("probe_file_fd", probe_file_fd),
                              ("probe_fd", probe_fd)):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError as exc:
                        close_errors.append({"descriptor": label,
                                             "error": error(exc)})
            if close_errors:
                probe["close_errors"] = close_errors
            if residue:
                # Si la limpieza falla, registrar el residuo y su ubicación.
                probe["self_cleaned"] = False
                probe["clean_error"] = (cleanup_errors[0]
                                        if cleanup_errors else None)
                probe["residue"] = residue
            elif close_errors:
                # El estado de los recursos no puede confirmarse: no se
                # declara autolimpieza completa.
                probe["self_cleaned"] = False
                probe["close_error"] = close_errors[0]["error"]
            else:
                probe["self_cleaned"] = True
        info["writability_probe"] = probe
        verified = writable
    else:
        info["writability_probe"] = {"attempted": False}
    info["verified_writable"] = verified
    # A3: clasificación contra información real de montaje (corrección D).
    # Almacenamiento compartido y genérico no se aprueban por ser escribibles;
    # si no se puede determinar la adecuación, se rechaza.
    detected, mount, caveat = _classify_storage(base, base_fd)
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


def _group_member_uids(gid):
    """UIDs miembros de un grupo, leídos de /etc/group (evidencia verificable).

    Devuelve un conjunto de UIDs miembros, o None si /etc/group no se puede
    leer o el grupo no puede verificarse. No se confía en el nombre o el GID
    por sí mismos: la confianza exige comprobar la composición real. Si no
    puede verificarse, el estado es desconocido y se rechaza.
    """
    try:
        lines = Path("/etc/group").read_text(errors="replace").splitlines()
    except OSError:
        return None
    passwd = {}
    try:
        for line in Path("/etc/passwd").read_text(errors="replace").splitlines():
            fields = line.split(":")
            if len(fields) >= 3:
                try:
                    passwd[fields[2]] = int(fields[2])
                except ValueError:
                    passwd[fields[2]] = fields[2]
    except OSError:
        passwd = {}
    for line in lines:
        fields = line.split(":")
        if len(fields) < 4:
            continue
        try:
            entry_gid = int(fields[2])
        except ValueError:
            continue
        if entry_gid != gid:
            continue
        members = set()
        for member in fields[3].split(","):
            member = member.strip()
            if member:
                members.add(passwd.get(member, member))
        return members
    return set()


def _parent_risk_blockers(row, euid, group_members=None):
    """Política conservadora de riesgo de padres (asunto 1).

    Evalúa conjuntamente propietario UID, permisos globales y de grupo, bit
    sticky y riesgo de sustitución de entradas, diferenciando directorios
    administrados por el sistema de directorios modificables por terceros:

    - Padre globalmente escribible SIN sticky: cualquier tercero puede
      renombrar/sustituir entradas -> bloqueo.
    - Padre globalmente escribible CON sticky: el sticky restringe la
      eliminación, pero el PROPIETARIO conserva facultades especiales sobre
      sus entradas; se acepta solo si el propietario es el usuario efectivo.
    - Padre escribible por grupo: se acepta SOLO con evidencia verificable de
      que el grupo no agrega terceros: la composición del grupo (leída de
      /etc/group) debe contener únicamente al usuario efectivo. Si la
      composición no puede verificarse (desconocida) o contiene otros
      miembros, se bloquea. No se confía en UID/GID ni en nombres, y no
      hay excepciones generales por ruta (/data, /data/data, etc.).

    Devuelve la lista de bloqueos para la fila.
    """
    blockers = []
    label = row.get("path") or f"descriptor {row.get('fd')}"
    if row["world_writable"]:
        if not row["sticky"]:
            blockers.append(
                "directorio padre globalmente escribible sin sticky: "
                f"riesgo de sustitución de entradas: {label}"
            )
        elif row["owner_uid"] != euid:
            blockers.append(
                "directorio padre globalmente escribible con sticky, pero "
                f"propietario no confiable (uid {row['owner_uid']} != "
                f"{euid}): el sticky no demuestra confianza: {label}"
            )
    if row["group_writable"]:
        if group_members is None:
            blockers.append(
                f"directorio padre escribible por grupo: no se pudo verificar "
                f"la composición del grupo (estado desconocido): {label}"
            )
        elif group_members != {euid}:
            blockers.append(
                f"directorio padre escribible por grupo: el grupo contiene "
                f"miembros distintos del usuario efectivo; no se puede "
                f"demostrar aislamiento suficiente: {label}"
            )
    return blockers


def _parent_audit(chain, euid=None):
    """Auditoría de padres ALIADA AL OBJETO ABIERTO (punto 1).

    Recibe la cadena de descriptores (root..base) producida por
    _walk_anchored_chain y inspecciona cada objeto mediante os.fstat sobre el
    propio descriptor: no usa rutas, por lo que no puede examinar un objeto
    distinto del que representa la cadena (sin TOCTOU). Devuelve
    (rows, blockers, complete). Si un descriptor no puede inspeccionarse, la
    auditoría es INCOMPLETA (complete=False) y se rechaza la ubicación.
    """
    if euid is None:
        euid = os.geteuid()
    rows = []
    blockers = []
    complete = True
    for fd in chain:
        try:
            st = os.fstat(fd)
        except OSError as exc:
            rows.append({"fd": fd, "inspection_error": error(exc)})
            complete = False
            break
        if not stat.S_ISDIR(st.st_mode):
            rows.append({"fd": fd, "inspection_error": "no es un directorio"})
            complete = False
            break
        perms = st.st_mode & 0o777
        row = {
            "fd": fd, "mode": oct(perms),
            "owner_uid": st.st_uid, "owner_gid": st.st_gid,
            "world_writable": bool(perms & 0o002),
            "group_writable": bool(perms & 0o020),
            "sticky": bool(st.st_mode & 0o1000),
        }
        rows.append(row)
        group_members = None
        if row["group_writable"]:
            # Evidencia verificable de la composición del grupo; si no se
            # puede obtener, el estado es desconocido y se rechaza.
            group_members = _group_member_uids(row["owner_gid"])
            row["group_members"] = (sorted(map(str, group_members))
                                    if group_members is not None else None)
        blockers.extend(_parent_risk_blockers(row, euid, group_members))
    return rows, blockers, complete


def _acl_state(path, base_fd=None):
    """Detecta ACL POSIX, preferentemente sobre el descriptor (punto 1).

    Reconoce system.posix_acl_access y system.posix_acl_default (y cualquier
    atributo con prefijo system.posix_acl); NO usa comparación exacta con
    system.posix_acl. Cuando se provee base_fd, la consulta se realiza sobre
    el DESCRITOR; si la plataforma o Python no permiten consultar atributos
    por descriptor, el resultado es "unknown" (no se recurre a una ruta para
    presentar la comprobación como protegida contra TOCTOU). Devuelve
    (state, error, method). "unknown" nunca se interpreta como ausencia de
    ACL y rechaza la aprobación automática.
    """
    if base_fd is not None:
        try:
            xattrs = os.listxattr(base_fd, follow_symlinks=False)
            method = "fd"
        except (OSError, AttributeError, TypeError) as exc:
            return "unknown", error(exc), "fd"
    else:
        try:
            xattrs = os.listxattr(str(path), follow_symlinks=False)
            method = "path"
        except (OSError, AttributeError) as exc:
            return "unknown", error(exc), "path"
    if any(str(name).startswith("system.posix_acl") for name in xattrs):
        return "present", None, method
    return "absent", None, method


def _base_blockers(analysis, parents):
    """Decisión de confianza sobre la ubicación (correcciones C/A/B).

    No se considera confiable un grupo simplemente por pertenecer a él: un
    directorio escribible por grupo permite a otros miembros modificarlo, y
    no se puede demostrar el aislamiento de esos miembros, por lo que se
    rechaza. También se rechazan directorios que no sean propiedad del
    usuario efectivo, globalmente escribibles, con ACL presentes o con
    estado de ACL desconocido (no evaluable), y padres con riesgo de
    sustitución o una auditoría de padres incompleta.
    """
    rows, parent_blockers, parent_complete = parents
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
    acl_state = analysis.get("acl_state")
    if acl_state == "present":
        blockers.append(
            "ACL presentes en el directorio: no evaluables por este "
            "diagnóstico; no se puede demostrar aislamiento suficiente"
        )
    elif acl_state == "unknown":
        blockers.append(
            "estado de ACL desconocido: la plataforma no permite verificar "
            "las ACL; no se aprueba automáticamente"
        )
    if not parent_complete:
        blockers.append(
            "auditoría de directorios padre incompleta: no se pudo "
            "inspeccionar todo el camino hasta la raíz; no se aprueba"
        )
    blockers.extend(parent_blockers)
    return blockers


def approved_base(path, location_declared=None):
    """Aprueba el directorio base tras un recorrido anclado por descriptores.

    Devuelve (base, base_fd, analysis). La ruta se recorre con dir_fd y
    O_NOFOLLOW examinando todos sus componentes (finales e intermedios,
    incluido el primero de una ruta relativa frente al anclaje real), de modo
    que no se resuelve ni se atraviesa ningún enlace simbólico y no queda una
    ventana TOCTOU entre inspección y uso. Todas las comprobaciones
    (inspección del base, ACL, auditoría de padres, detección de .git) se
    realizan sobre los DESCRITORES de la cadena anclada (fstat/listxattr/
    stat con dir_fd): ninguna inspecciona un objeto distinto del que
    representa base_fd por una ruta que podría cambiar. Si una comprobación
    no está soportada o la identidad de un objeto no puede verificarse, el
    resultado es desconocido/incompleto y se rechaza la aprobación
    automática. Si cualquier comprobación falla, se cierran todos los
    descriptores de la cadena antes de rechazar. Devuelve el descriptor del
    directorio base para que el llamador realice creaciones sobre él.
    """
    raw = Path(path).expanduser()
    if os.geteuid() == 0:
        raise ValueError("--base no debe ejecutarse como root")
    # 1) Recorrido anclado: cadena de descriptores root..base, sin seguir
    #    enlaces simbólicos. Cualquier enlace final o intermedio se rechaza.
    chain, resolved = _walk_anchored_chain(raw)
    base_fd = chain[-1]
    base = Path(resolved)
    try:
        # 2) La aprobación depende de condiciones verificadas sobre el
        #    descriptor, no solo de registrar la ruta.
        analysis = analyze_base(base, location_declared, probe_writability=True,
                                base_fd=base_fd)
        # Detección de ACL sobre el descriptor (solo lectura; no se modifica
        # nada ajeno). Si la plataforma no lo permite, estado unknown.
        acl_state, acl_error, acl_method = _acl_state(base, base_fd)
        analysis["acl_state"] = acl_state
        analysis["acl_error"] = acl_error
        analysis["acl_method"] = acl_method
        # Auditoría de padres sobre la cadena de descriptores (fstat).
        parents, parent_blockers, parent_complete = _parent_audit(chain,
                                                                  os.geteuid())
        analysis["parents"] = parents
        analysis["parent_audit_complete"] = parent_complete
        if analysis["status"] != "OK":
            raise ValueError(f"--base rechazado: {analysis.get('reason')}")
        if analysis.get("verified_writable") is not True:
            raise ValueError("--base: la capacidad de escritura no pudo verificarse; no se aprueba")
        if not analysis.get("storage_suitable", False):
            raise ValueError(
                "--base: la clase de almacenamiento no es apropiada o no está "
                "fundamentada; no se aprueba"
            )
        # A2/C/A/B: decisión de confianza (propiedad, permisos, ACL, riesgo
        # de terceros y auditoría de padres).
        blockers = _base_blockers(analysis, (parents, parent_blockers,
                                             parent_complete))
        if blockers:
            raise ValueError("--base rechazado: " + "; ".join(blockers))
        if base == base.parent:
            raise ValueError("--base debe ser un directorio de diagnóstico, no la raíz")
        # Detección de árbol Git también por descriptores (dir_fd).
        for fd in chain:
            try:
                os.stat(".git", dir_fd=fd)
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ValueError(
                    f"--base: no se pudo inspeccionar .git en un componente: "
                    f"{error(exc)}"
                ) from exc
            raise ValueError(f"--base está dentro de un árbol Git (descriptor {fd})")
        # Cerrar los descriptores de la cadena excepto el del directorio
        # base, registrando los errores de cierre (asunto 3).
        closed, failed = _close_chain(chain[:-1])
        analysis["chain_close_parents"] = {"closed": closed, "failed": failed}
        if failed:
            emit("chain_close_warning", failed=failed,
                 message="cierres de descriptores de la cadena fallidos; "
                         "estado de algunos descriptores incierto")
        emit("approved_base", **analysis)
        return base, base_fd, analysis
    except BaseException as exc:
        # Cerrar todos los descriptores de la cadena si falla una comprobación,
        # registrando los errores (asunto 3).
        closed, failed = _close_chain(chain)
        if failed:
            emit("chain_close_error", failed=failed,
                 message="cierres de descriptores de la cadena fallidos "
                         "durante el rechazo; estado incierto")
            exc.chain_close_failed = failed
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
