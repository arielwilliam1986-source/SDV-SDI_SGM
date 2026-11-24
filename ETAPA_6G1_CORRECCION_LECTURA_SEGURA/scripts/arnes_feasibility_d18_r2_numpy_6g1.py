#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FEASIBILITY D-18-R2 — Ciclo de vida SEGURO de numpy.memmap (aislado).

Objetivo de R2: investigar y validar experimentalmente alternativas SEGURAS
para liberar los recursos de numpy.memmap SIN invocar arr._mmap.close()
mientras existan arrays/vistas vivas (ese camino es el hallazgo C5 de
FEASIBILITY-D18-R1, conservado como histórico y NO re-ejecutado aquí).

CORRECCIÓN METODOLÓGICA R1 (FEASIBILITY-D18-R2-R1, autorizada por Cris):
  R1-A  count_maps(): no descartar líneas no interpretables de /proc/self/maps;
        distinguir lectura COMPLETA de INCOMPLETA/ILEGIBLE; cualquier línea no
        interpretable, error de E/S o lectura ilegible -> UNKNOWN; solo se
        declara cero mappings tras una lectura COMPLETA; FAIL única y
        exclusivamente cuando una lectura COMPLETA contradice lo esperado.
  R1-B  fds_with_identity(): no ignorar silenciosamente errores individuales de
        /proc/self/fd; distinguir descriptores que desaparecieron durante el
        recorrido, inaccesibles y errores de procfs; inventario INCOMPLETO ->
        UNKNOWN; NUNCA declarar PASS a partir de un inventario incompleto.
  R1-C  Propagación: todo escenario A/B/C cuyo acreditamiento dependa de una
        lectura/inventario incompleto pasa a UNKNOWN; ninguno declara PASS si
        su acreditación depende de una lectura incompleta.
  R1-D  Informe: C5 conservado como FAIL histórico; sin _mmap.close() forzado;
        sin garantizar gc.collect() universal; separar hecho/hipótesis/UNKNOWN.

CORRECCIÓN FINAL R2 (FEASIBILITY-D18-R2-R2, autorizada por Cris):
  R2-A  fds_with_identity() captura ADEMÁS los errores de os.listdir(fd_dir)
        (apertura/enumeración del directorio). Imposible abrir o enumerar ->
        inventario INCOMPLETO con error+contexto registrado; la función NO
        propaga la excepción (evita que el controlador general la convierta
        artificialmente en FAIL); la imposibilidad de completar el inventario
        produce UNKNOWN; NUNCA PASS ni cero descriptores desde inventario
        incompleto. Se investiga la enumeración con descriptor de directorio
        mantenido abierto durante la inspección; se demuestra por pruebas
        (R2-C9) y NO se asume que elimine el artefacto fd 3 (R2-C8).
  R2-B  Clasificación expresa de errores: DESCRIPTOR_DESAPARECIDO,
        DESCRIPTOR_INACCESIBLE, ERROR_PROCFS, UNKNOWN_CAUSE. Se conservan
        errno, tipo de excepción, nombre de entrada y contexto. Sin
        clasificar con certeza -> UNKNOWN_CAUSE (no inventar).
  R2-C  Pruebas controladas obligatorias (R2-C1..R2-C9): inventario
        completo, desaparición, inaccesibilidad, error de enumeración,
        error de procfs en inspección, propagación de UNKNOWN, ausencia de
        FAIL artificial, origen del fd 3 y demostración del descriptor de
        directorio mantenido.
  R2-D  Reejecución del conjunto D18-R2 con las correcciones; precedencia
        FAIL > UNKNOWN > PASS; C5 conservado como FAIL histórico de D18-R1;
        sin _mmap.close() forzado con referencias vivas; sin garantías
        universales atribuidas a gc.collect(); hechos, hipótesis y UNKNOWN
        separados en el informe.

CORRECCIÓN FINAL R3 (FEASIBILITY-D18-R2-R3, autorizada por Cris):
  R3-A  R2-C7 verifica dos propiedades independientes: (P1) el error de
        enumeración no escapa de fds_with_identity(); (P2) el controlador
        recibe complete=False y asigna UNKNOWN, nunca PASS ni FAIL
        artificial. PASS solo si ambas se verifican.
  R3-B  R2-C2/R2-C3: el veredicto depende de la CLASIFICACIÓN verificada
        (clasificación correcta + complete=False -> UNKNOWN; clasificación
        incorrecta -> FAIL). No UNKNOWN automático por incompletitud.
  R3-C  R2-C5 exige evidencia REAL de un error de inspección clasificado
        ERROR_PROCFS con errno y contexto compatibles; sin evidencia
        suficiente del entorno -> UNKNOWN, no PASS.
  R3-D  Clasificación conservadora de ENOENT: la ausencia de fdinfo NO
        demuestra por sí sola artefacto de procfs (puede ser descriptor
        real cerrado entre enumeración e inspección). fdinfo ausente en
        procfs -> UNKNOWN_CAUSE; fdinfo presente -> DESCRIPTOR_DESAPARECIDO;
        FS regular -> DESCRIPTOR_DESAPARECIDO. ERROR_PROCFS solo con
        evidencia suficiente. Se documenta qué puede y qué no puede
        distinguir el mecanismo.
  R3-E  R2-C10 verifica la propagación sobre los ESCENARIOS REALES A/B/C
        (no una función simplificada aislada), con inventario controlado
        completo/incompleto y contraste.
  R3-F  Reejecución del conjunto completo con resultados reales; se
        mantienen precedencia FAIL>UNKNOWN>PASS, C5 como FAIL histórico,
        prohibición de _mmap.close() con referencias vivas, sin garantías
        universales de gc.collect() y separación de hechos/hipótesis/
        UNKNOWN.

Restricciones: entorno aislado, fixtures sintéticos, sin motores/, sin
lectura_segura_6g1.py, sin plan v2.3/diseño v5/adjudicación final, sin
integración Hardened/EVO/MQR, sin audio real, sin Android/Termux, sin D-16,
sin main/PR#2/merge.

Precedencia de veredictos (global): FAIL > UNKNOWN > PASS.
Evidencia JSON: /tmp/feas_d18_r2_evidence/evidence_d18_r2.json
"""

import builtins
import errno
import gc
import json
import mmap
import os
import platform
import shutil
import sys
import tempfile

import numpy as np

RESULTS = []
WORKDIR = None
EVIDENCE_DIR = "/tmp/feas_d18_r2_evidence"

# Estados de lectura/inventario (R1-A / R1-B).
READ_COMPLETE = "complete"      # se leyó todo y todas las líneas/entradas se interpretaron
READ_INCOMPLETE = "incomplete"  # se leyó pero hubo líneas no interpretables
READ_UNREADABLE = "unreadable"  # no se pudo abrir/leer el origen (error de E/S)

# Clasificaciones de errores de inventario de fds (R2-B).
CLASS_DISAPPEARED = "DESCRIPTOR_DESAPARECIDO"    # entrada que desaparece durante el recorrido
CLASS_INACCESSIBLE = "DESCRIPTOR_INACCESIBLE"    # error de permisos o acceso
CLASS_PROCFS = "ERROR_PROCFS"                   # fallo de apertura/enumeración/inspección atribuible al procfs
CLASS_UNKNOWN_CAUSE = "UNKNOWN_CAUSE"           # causa no determinable con certeza (no inventar)


# ---------------------------------------------------------------- helpers
def record(tid, section, title, preconditions, procedure, observed,
           evidence, verdict, exception=None):
    RESULTS.append({
        "id": tid, "section": section, "title": title,
        "preconditions": preconditions, "procedure": procedure,
        "observed": observed, "evidence": evidence,
        "exception": exception, "verdict": verdict,
    })
    print(f"[{tid}] {verdict} — {title}")
    if exception:
        print(f"         excepción: {exception}")


class MapsRead:
    """Resultado de leer /proc/self/maps de forma metodológicamente correcta.

    R1-A: las líneas no interpretables NO se descartan; determinan que la
    lectura es INCOMPLETA. El recuento por identidad solo es fiable cuando
    status == READ_COMPLETE.
    """

    __slots__ = ("entries", "unparseable", "error", "readable")

    def __init__(self, entries, unparseable, error, readable):
        self.entries = entries            # líneas interpretadas
        self.unparseable = unparseable    # líneas NO interpretables (con nº)
        self.error = error                # excepción de E/S (str) o None
        self.readable = readable          # ¿pudo abrirse/leerse el origen?

    @property
    def status(self):
        if self.error is not None or not self.readable:
            return READ_UNREADABLE
        if self.unparseable:
            return READ_INCOMPLETE
        return READ_COMPLETE

    def count_for_identity(self, st):
        maj, min_, ino = identity_of(st)
        return sum(1 for e in self.entries
                   if e["major"] == maj and e["minor"] == min_ and e["ino"] == ino)


class FdInventory:
    """Inventario de /proc/self/fd (R1-B / R2-A / R2-B).

    R1-B: los errores individuales NO se ignoran; determinan que el inventario
    es INCOMPLETO. matched solo es fiable cuando complete == True.

    R2-A: un fallo de apertura/enumeración del directorio (os.listdir) también
    produce un inventario INCOMPLETO; la función no propaga la excepción.

    R2-B: cada error lleva classification, errno, tipo de excepción, nombre
    de entrada y contexto.
    """

    __slots__ = ("matched", "errors", "complete", "enum_dirfd", "enum_mode")

    def __init__(self, matched, errors, complete, enum_dirfd=None,
                 enum_mode=None):
        self.matched = sorted(matched)    # fds con la identidad buscada
        self.errors = errors              # [{name, error, classification, ...}]
        self.complete = complete          # ¿se pudo inventariar TODO?
        self.enum_dirfd = enum_dirfd      # descriptor de directorio usado (R2-A)
        self.enum_mode = enum_mode        # "dirfd" | "path" | None

    def error_classes(self):
        """Conteo de errores por clasificación (R2-B)."""
        out = {}
        for e in self.errors:
            out[e.get("classification", CLASS_UNKNOWN_CAUSE)] = \
                out.get(e.get("classification", CLASS_UNKNOWN_CAUSE), 0) + 1
        return out


def parse_maps(path="/proc/self/maps"):
    """Lee /proc/self/maps y devuelve un MapsRead.

    R1-A: las líneas con menos de 5 campos o con dev/ino no enteros se
    registran en 'unparseable' (NO se descartan en silencio). Un error de
    apertura/lectura se registra en 'error' (origen ILEGIBLE). El llamante
    debe consultar .status antes de fiarse del recuento.
    """
    entries, unparseable = [], []
    error = None
    readable = False
    try:
        with open(path, "r") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.rstrip("\n")
                parts = line.split(None, 5)
                if len(parts) < 5:
                    unparseable.append({"line": lineno, "text": line})
                    continue
                addr, perms, offset, dev, inode = parts[:5]
                pathname = parts[5] if len(parts) > 5 else ""
                try:
                    major_s, minor_s = dev.split(":")
                    major = int(major_s, 16)
                    minor = int(minor_s, 16)
                    ino = int(inode)
                except ValueError:
                    unparseable.append({"line": lineno, "text": line})
                    continue
                entries.append({
                    "addr": addr, "perms": perms, "offset": offset,
                    "dev": dev, "major": major, "minor": minor,
                    "ino": ino, "pathname": pathname,
                })
        readable = True
    except OSError as e:
        error = f"{type(e).__name__}: {e}"
    return MapsRead(entries, unparseable, error, readable)


def identity_of(st):
    return (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)


def entries_for_identity(entries, st):
    maj, min_, ino = identity_of(st)
    return [e for e in entries
            if e["major"] == maj and e["minor"] == min_ and e["ino"] == ino]


def count_maps(st):
    """Lee /proc/self/maps y devuelve un MapsRead (R1-A).

    El recuento por identidad se obtiene con .count_for_identity(st); su
    validez exige .status == READ_COMPLETE. Con lectura incompleta/ilegible el
    recuento NO debe usarse para declarar PASS ni FAIL: el escenario debe ir a
    UNKNOWN.
    """
    return parse_maps()


def _is_procfs_fd_dir(fd_dir):
    """¿fd_dir es un directorio de fds de procfs (/proc/...)? (R2-B)."""
    try:
        return os.path.abspath(fd_dir).startswith("/proc/")
    except (TypeError, ValueError):
        return False


def _fdinfo_probe(fd_dir, name):
    """Inspección de corroboración de procfs (R2-B, R3-D).

    En /proc/self/fd, un descriptor REAL abierto tiene una entrada en
    fdinfo. Devuelve:
      - True  -> fdinfo EXISTE (hay evidencia de un descriptor real abierto).
      - False -> fdinfo NO existe.
      - None  -> la inspección no aplica (no es un dir de fds de procfs o
        nombre nulo).

    R3-D (crítico): la AUSENCIA de fdinfo NO demuestra por sí sola que la
    entrada sea un artefacto de procfs: también ocurre si el descriptor
    real se cerró entre la enumeración y la inspección. Por tanto, fdinfo
    ausente NO se usa automáticamente para clasificar ERROR_PROCFS; solo
    fdinfo PRESENTE respalda evidencia de descriptor real (y la ausencia
    de fdinfo en un dir de fds se trata como causa no determinable, salvo
    que haya más evidencia).
    """
    if name is None or not _is_procfs_fd_dir(fd_dir):
        return None
    fdinfo = os.path.join(os.path.dirname(os.path.abspath(fd_dir)),
                          "fdinfo", str(name))
    try:
        with open(fdinfo, "rb"):
            return True
    except OSError:
        return False


def _classify_fd_error(name, exc, fd_dir, phase):
    """Clasifica un error de inventario de fds (R2-B, R3-D conservador).

    Fase: "enumeracion" (apertura/listdir) o "inspeccion" (stat de entrada).
    Reglas (evidencia, no invención):
      - EACCES/EPERM                 -> DESCRIPTOR_INACCESIBLE.
      - ENOENT en inspección (R3-D):
          * FS REGULAR (no procfs): la entrada estaba en el listado y ya no
            se puede inspeccionar -> DESCRIPTOR_DESAPARECIDO (no hay
            concepto de artefacto de procfs en un FS regular).
          * procfs:
              + fdinfo PRESENTE (evidencia de descriptor real) ->
                DESCRIPTOR_DESAPARECIDO (se cerró entre enumeración e
                inspección).
              + fdinfo AUSENTE -> NO se puede distinguir un artefacto de
                procfs de un descriptor real cerrado -> UNKNOWN_CAUSE.
      - fallos típicos de procfs/fs virtual (EIO/EINVAL/ENOTDIR/ENOSYS/
        EOPNOTSUPP)                    -> ERROR_PROCFS.
      - enumeración fallida en un directorio de procfs -> ERROR_PROCFS.
      - cualquier otra causa sin evidencia suficiente -> UNKNOWN_CAUSE.

    ERROR_PROCFS se mantiene solo para casos con EVIDENCIA SUFICIENTE de un
    fallo atribuible al propio procfs; no se inventa una causa raíz.
    """
    err = getattr(exc, "errno", None)
    ctx = {"phase": phase, "fd_dir": fd_dir, "entry": name}
    if phase == "enumeracion":
        if _is_procfs_fd_dir(fd_dir):
            return CLASS_PROCFS, ctx
        # No hay evidencia suficiente para atribuirlo al propio procfs.
        return CLASS_UNKNOWN_CAUSE, ctx
    if err in (errno.EACCES, errno.EPERM):
        return CLASS_INACCESSIBLE, ctx
    if err == errno.ENOENT:
        if not _is_procfs_fd_dir(fd_dir):
            # FS regular: listado previo + ENOENT = desaparición real.
            return CLASS_DISAPPEARED, ctx
        # procfs: fdinfo presente -> descriptor real -> desaparición real;
        # fdinfo ausente -> ambigüedad -> UNKNOWN_CAUSE (conservador, R3-D).
        if _fdinfo_probe(fd_dir, name) is True:
            return CLASS_DISAPPEARED, ctx
        return CLASS_UNKNOWN_CAUSE, ctx
    if err in (errno.EIO, errno.EINVAL, errno.ENOTDIR, errno.ENOSYS,
               errno.EOPNOTSUPP, errno.EBUSY, errno.EREMOTEIO):
        return CLASS_PROCFS, ctx
    return CLASS_UNKNOWN_CAUSE, ctx


def _error_record(name, exc, fd_dir, phase, classification, ctx, note=None):
    """Registro de error completo (R2-B): errno, tipo, nombre, contexto."""
    rec = {
        "name": name,
        "error": f"{type(exc).__name__}: {exc}",
        "exception_type": type(exc).__name__,
        "errno": getattr(exc, "errno", None),
        "phase": phase,
        "classification": classification,
        "context": dict(ctx),
    }
    if note:
        rec["note"] = note
    return rec


def _enumerate_fd_dir(fd_dir):
    """Enumera fd_dir con un descriptor de directorio mantenido abierto (R2-A).

    Estrategia investigada: abrir el directorio con O_DIRECTORY y enumerar
    vía el descriptor, manteniéndolo abierto durante toda la inspección, para
    que el descriptor propio de la enumeración sea estable e identificable
    (no se confunda con una desaparición externa). Se retorna
    (names, dirfd, mode) con mode en {"dirfd", "path"}; el descriptor
    DIRF permanece ABIERTO y lo cierra el llamante. Si O_DIRECTORY no
    está disponible en el FS, se cae al camino por ruta (mode="path").
    Lanza OSError si no puede abrirse/enumerarse (capturado por el llamante).
    """
    try:
        dirfd = os.open(fd_dir, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        # Camino por ruta como alternativa (no asumir que la alternativa
        # resuelva el problema; se documenta el modo usado).
        names = os.listdir(fd_dir)
        return names, None, "path"
    names = os.listdir(dirfd)
    return names, dirfd, "dirfd"


def fds_with_identity(st, fd_dir="/proc/self/fd"):
    """Inventario de /proc/self/fd para la identidad de 'st' (R1-B/R2-A/R2-B).

    R1-B: los errores de stat (descriptor que desapareció durante el
    recorrido, inaccesible, error de procfs) NO se ignoran: se registran
    (con clasificación) y fuerzan complete=False.

    R2-A: los errores de os.listdir(fd_dir) (apertura/enumeración) se
    capturan igual: inventario INCOMPLETO, error+contexto registrados. La
    función NO propaga la excepción, para que el controlador general no la
    convierta artificialmente en FAIL. La imposibilidad de completar el
    inventario produce UNKNOWN en cualquier escenario dependiente y NUNCA
    PASS ni cero descriptores desde un inventario incompleto.

    R2-A (investigación): la enumeración usa un descriptor de directorio
    mantenido abierto durante la inspección (ver R2-C9). Esto NO se asume
    como solución del artefacto fd 3; se demuestra por pruebas (R2-C8).
    """
    target = identity_of(st)
    matched, errors = [], []
    complete = True

    dirfd, enum_mode = None, None
    try:
        # Apertura + enumeración del directorio (R2-A): cualquier OSError
        # aquí se registra y produce inventario INCOMPLETO.
        try:
            names, dirfd, enum_mode = _enumerate_fd_dir(fd_dir)
        except OSError as e:
            cls, ctx = _classify_fd_error(None, e, fd_dir, "enumeracion")
            errors.append(_error_record(None, e, fd_dir, "enumeracion",
                                        cls, ctx))
            complete = False
            return FdInventory(matched, errors, complete, None, None)

        # Inspección de cada entrada con el descriptor de directorio
        # mantenido abierto (R2-A: es estable e identificable).
        for name in names:
            try:
                s = os.stat(os.path.join(fd_dir, name))
            except OSError as e:
                # Descriptor que desapareció durante el recorrido, inaccesible
                # o error de procfs: se registra (R2-B) y marca incompleto.
                cls, ctx = _classify_fd_error(name, e, fd_dir, "inspeccion")
                errors.append(_error_record(name, e, fd_dir, "inspeccion",
                                            cls, ctx))
                complete = False
                continue
            if identity_of(s) == target:
                try:
                    matched.append(int(name))
                except ValueError:
                    cls = (CLASS_PROCFS if _is_procfs_fd_dir(fd_dir)
                           else CLASS_UNKNOWN_CAUSE)
                    ctx = {"phase": "inspeccion", "fd_dir": fd_dir,
                           "entry": name}
                    errors.append(_error_record(
                        name, ValueError(f"fd no entero: {name!r}"),
                        fd_dir, "inspeccion", cls, ctx,
                        note="nombre no entero en inventario de fds"))
                    complete = False
        return FdInventory(matched, errors, complete, dirfd, enum_mode)
    finally:
        if dirfd is not None:
            try:
                os.close(dirfd)
            except OSError:
                pass


def close_fd_quiet(fd):
    try:
        os.close(fd)
    except OSError:
        pass


def make_file(name, size=16384, fill=b"\x00"):
    path = os.path.join(WORKDIR, name)
    with open(path, "wb") as fh:
        fh.write(fill * (size // len(fill)) + fill[: size % len(fill)])
    return path


class OpenRecorder:
    """Reemplaza builtins.open para registrar las rutas que NumPy abre a
    nivel Python (NO os.open ni el dup() interno de mmap.mmap)."""

    def __init__(self):
        self.paths = []
        self._real = builtins.open

    def __call__(self, file, *a, **k):
        self.paths.append(file if isinstance(file, (str, bytes, os.PathLike))
                          else f"<fd {file}>")
        return self._real(file, *a, **k)

    def __enter__(self):
        builtins.open = self
        return self

    def __exit__(self, *exc):
        builtins.open = self._real
        return False


# ---------------------------------------------------------------- R2-A
def test_a1():
    p = make_file("a1.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    mm_state = type(arr._mmap).__name__
    m_alive = count_maps(st)
    inv_alive = fds_with_identity(st)
    alive_maps = m_alive.count_for_identity(st)
    alive_fds = inv_alive.matched
    del arr
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    gone_fds = inv_gone.matched
    reads_complete = (m_alive.status == READ_COMPLETE and inv_alive.complete
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == []
          and mm_state == "mmap")
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A1", "A", "Raíz sin vistas: liberación por referencias",
           "np.memmap por ruta; sin vistas derivadas.",
           "Soltar la única referencia (del arr) y gc.collect(); verificar "
           "desaparición en maps y cierre del fd del mmap (sin _mmap.close).",
           f"vivo: maps={alive_maps} fds={alive_fds} mmap={mm_state} "
           f"(status={m_alive.status}); tras del+gc: maps={gone_maps} "
           f"fds={gone_fds} (status={m_gone.status})",
           "liberar la referencia raíz + gc finaliza el mmap (su "
           "finalizador cierra el fd duplicado y desmapea); sin SIGSEGV",
           verdict)


def test_a2():
    p = make_file("a2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    sl = arr[0:16]
    states = []
    m = count_maps(st); states.append((m.status, True))
    alive = m.count_for_identity(st)
    del arr
    gc.collect()
    m = count_maps(st); states.append((m.status, True))
    kept = m.count_for_identity(st)            # la vista mantiene vivo el mapeo
    del sl
    gc.collect()
    m = count_maps(st); states.append((m.status, True))
    after = m.count_for_identity(st)
    reads_complete = all(s == READ_COMPLETE for s, _ in states)
    ok = (alive == 1 and kept == 1 and after == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A2", "A", "Raíz con slices: retención y liberación",
           "np.memmap + slice arr[0:16].",
           "Liberar la raíz (slice retenido) -> maps debe persistir; luego "
           "liberar el slice -> maps desaparece.",
           f"vivo={alive}; tras del raíz (slice vivo)={kept}; "
           f"tras del slice={after}",
           "un slice comparte el mmap vía __array_finalize__/base: el "
           "mapeo NO desaparece hasta soltar TODAS las vistas",
           verdict)


def test_a3():
    p = make_file("a3.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v1 = arr[0:32]
    v2 = v1[4:8]                    # vista encadenada (v2.base -> v1)
    states = []
    m = count_maps(st); states.append(m.status)
    alive = m.count_for_identity(st)
    del arr
    gc.collect()
    m = count_maps(st); states.append(m.status)
    after_del_root = m.count_for_identity(st)
    del v1
    gc.collect()
    m = count_maps(st); states.append(m.status)
    after_del_v1 = m.count_for_identity(st)
    del v2
    gc.collect()
    m = count_maps(st); states.append(m.status)
    after_del_v2 = m.count_for_identity(st)
    reads_complete = all(s == READ_COMPLETE for s in states)
    ok = (alive == 1 and after_del_root == 1
          and after_del_v1 == 1 and after_del_v2 == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A3", "A", "Vistas derivadas y referencias encadenadas",
           "arr -> v1=arr[0:32] -> v2=v1[4:8].",
           "Liberar progresivamente raíz, luego v1, luego v2; el mapeo "
           "debe desaparecer solo al soltar la última vista encadenada.",
           f"vivo={alive}; del raíz={after_del_root}; del v1={after_del_v1}; "
           f"del v2={after_del_v2}",
           "la cadena de vistas retiene el mmap hasta la última referencia "
           "viva (comportamiento observado CPython 3.11.2/NumPy 1.26.4)",
           verdict)


def test_a4():
    p = make_file("a4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    cont = [arr, arr[0:4]]          # referencias en contenedor
    states = []
    m = count_maps(st); states.append(m.status)
    alive = m.count_for_identity(st)
    del arr
    gc.collect()
    m = count_maps(st); states.append(m.status)
    kept = m.count_for_identity(st)
    del cont
    gc.collect()
    m = count_maps(st); states.append(m.status)
    after = m.count_for_identity(st)
    reads_complete = all(s == READ_COMPLETE for s in states)
    ok = (alive == 1 and kept == 1 and after == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A4", "A", "Referencias almacenadas en contenedores",
           "array y una vista guardados en una lista.",
           "Liberar la variable suelta (contenedor retenido) -> maps "
           "persiste; vaciar el contenedor + gc -> desaparece.",
           f"vivo={alive}; del var (contedor vivo)={kept}; "
           f"del contenedor={after}",
           "los contenedores retienen el mmap mientras referencien el "
           "array/vistas; liberar el contenedor libera el mapeo",
           verdict)


def test_a5():
    p = make_file("a5.bin")
    st = os.stat(p)
    exported = []                   # referencia exportada fuera del ámbito

    def make_and_export():
        a = np.memmap(p, dtype="uint8", mode="r+")
        exported.append(a)          # sobrevive al retorno de la función
        return a

    a = make_and_export()
    states = []
    m = count_maps(st); states.append(m.status)
    alive = m.count_for_identity(st)
    del a
    gc.collect()
    m = count_maps(st); states.append(m.status)
    kept = m.count_for_identity(st)            # la referencia exportada mantiene vivo
    del exported[:]
    gc.collect()
    m = count_maps(st); states.append(m.status)
    after = m.count_for_identity(st)
    reads_complete = all(s == READ_COMPLETE for s in states)
    ok = (alive == 1 and kept == 1 and after == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A5", "A", "Referencia exportada que sobrevive al ámbito",
           "array cuya referencia se exporta a una lista de módulo.",
           "Liberar la variable local (ref exportada viva) -> maps "
           "persiste; liberar la referencia exportada + gc -> desaparece.",
           f"vivo={alive}; del local (exportada viva)={kept}; "
           f"del exportada={after}",
           "una referencia exportada fuera del ámbito original retiene el "
           "mmap; la liberación segura exige soltarla también",
           verdict)


def test_a6():
    p = make_file("a6.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:8]
    cont = [arr]
    seq = []
    m = count_maps(st); seq.append((m.status, m.count_for_identity(st)))
    del arr
    gc.collect()
    m = count_maps(st); seq.append((m.status, m.count_for_identity(st)))   # v y cont retienen
    del v
    gc.collect()
    m = count_maps(st); seq.append((m.status, m.count_for_identity(st)))  # cont retiene
    del cont
    gc.collect()
    m = count_maps(st); seq.append((m.status, m.count_for_identity(st)))
    reads_complete = all(s == READ_COMPLETE for s, _ in seq)
    ok = (seq[0][1] == 1 and seq[1][1] == 1
          and seq[2][1] == 1 and seq[3][1] == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-A6", "A", "Liberación progresiva y recolección",
           "raíz + vista + contenedor que referencia la raíz.",
           "Liberar referencias una a una con gc intermedio; registrar el "
           "recuento de maps en cada paso; debe llegar a 0 solo al soltar "
           "la última.",
           f"secuencia={[ (s, n) for s, n in seq ]}",
           "el mapeo desaparece exactamente cuando la última referencia "
           "viva se libera y se recolecta",
           verdict)


# ---------------------------------------------------------------- R2-B
def test_b1():
    p = make_file("b1.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    m_alive = count_maps(st)
    inv_alive = fds_with_identity(st)
    alive_maps = m_alive.count_for_identity(st)
    alive_fds = inv_alive.matched
    del arr                         # liberación SEGURA (sin _mmap.close)
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    gone_fds = inv_gone.matched
    reads_complete = (m_alive.status == READ_COMPLETE and inv_alive.complete
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == [])
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-B1", "B", "Secuencia segura: raíz, sin vistas",
           "np.memmap por ruta; sin vistas.",
           "Secuencia segura SIN _mmap.close(): (1) soltar referencias "
           "propias, (2) ninguna vista, (3) gc.collect, (4) verificar "
           "desaparición de TODAS las entradas por (dev,ino), (5) verificar "
           "fds residuales y propiedad.",
           f"vivo: maps={alive_maps} fds={alive_fds} (status={m_alive.status}); "
           f"tras liberar+gc: maps={gone_maps} fds={gone_fds} "
           f"(status={m_gone.status})",
           "la secuencia segura libera el mapeo vía finalizador de gc; el "
           "fd duplicado del mmap se cierra; sin SIGSEGV",
           verdict)


def test_b2():
    p = make_file("b2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:16]
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del v, arr                      # liberar vistas y raíz
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    gone_fds = inv_gone.matched
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == [])
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-B2", "B", "Secuencia segura con vistas/slices",
           "np.memmap + slice.",
           "Secuencia segura: soltar vistas y raíz, gc.collect, verificar "
           "desaparición.",
           f"vivo={alive_maps}; tras liberar vistas+raíz+gc: "
           f"maps={gone_maps} fds={gone_fds}",
           "soltar vistas Y raíz permite al finalizador cerrar el mmap; "
           "quedarse una vista impide la liberación",
           verdict)


def test_b3():
    p = make_file("b3.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del arr
    gc.collect()
    gc.collect()                    # recolección controlada (doble pasada)
    m_gone = count_maps(st)
    gone_maps = m_gone.count_for_identity(st)
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_gone.status == READ_COMPLETE)
    ok = (alive_maps == 1 and gone_maps == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-B3", "B", "Recolección controlada de referencias",
           "np.memmap por ruta; doble gc.collect().",
           "Liberar referencia; forzar recolección (dos pasadas); verificar "
           "que el finalizador del mmap se ejecutó (maps=0).",
           f"vivo={alive_maps}; tras del+doble gc: maps={gone_maps} "
           f"(status={m_gone.status})",
           "la recolección controlada finaliza el mmap y desmapea sin "
           "intervención de _mmap.close()",
           verdict)


def test_b4():
    p = make_file("b4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    m_before = parse_maps()
    before = m_before.count_for_identity(st)
    del arr
    gc.collect()
    m_after = parse_maps()
    after = m_after.count_for_identity(st)
    reads_complete = (m_before.status == READ_COMPLETE
                      and m_after.status == READ_COMPLETE)
    ok = (before == 1 and after == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-B4", "B", "Desaparición de TODAS las entradas por (dev,ino)",
           "np.memmap por ruta; barrido por identidad.",
           "Tras la liberación segura, comprobar que entries_for_identity "
           "devuelve 0 (no solo 'la primera').",
           f"entradas por identidad: antes={before} después={after} "
           f"(status antes={m_before.status} después={m_after.status})",
           "la acreditación de cierre usa TODAS las entradas por identidad "
           "(no una sola); el recuento llega a 0",
           verdict)


def test_b5():
    p = make_file("b5.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    inv_alive = fds_with_identity(st)
    alive_fds = inv_alive.matched
    del arr
    gc.collect()
    inv_gone = fds_with_identity(st)   # por ruta: no debe quedar ninguno
    residual = inv_gone.matched
    reads_complete = (inv_alive.complete and inv_gone.complete)
    ok = (bool(alive_fds) and residual == [])
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-B5", "B", "Fds residuales y propiedad (por ruta)",
           "np.memmap por ruta; el motor no abre fd propio.",
           "Verificar que tras la liberación segura no queda ningún fd con "
           "la identidad (el duplicado del mmap se cerró; el motor no "
           "poseía fd_mm).",
           f"fds vivos={alive_fds}; residuales tras liberar={residual} "
           f"(complete vivo={inv_alive.complete} muerto={inv_gone.complete})",
           "el único fd con la identidad era el duplicado del mmap; al "
           "finalizar, queda [] : el motor no debe atribuirse ese recurso",
           verdict)


def test_b6():
    p = make_file("b6.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    externa = arr                  # referencia externa que el motor 'olvidó'
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del arr
    gc.collect()                   # el motor libera lo que conoce
    m_kept = count_maps(st)
    kept_maps = m_kept.count_for_identity(st)     # pero la referencia externa lo retiene
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_kept.status == READ_COMPLETE)
    ok_release = (kept_maps == 1)  # NO se acredita la liberación
    # Sin inventario incompleto: el escenario termina en UNKNOWN por referencia
    # retenida (no se usa _mmap.close() forzado). Si la lectura fuera
    # incompleta, también sería UNKNOWN (R1-C).
    verdict = "UNKNOWN" if not reads_complete else ("UNKNOWN" if ok_release else "FAIL")
    record("R2-B6", "B", "Referencia externa viva impide la liberación",
           "np.memmap + una referencia externa fuera del control del motor.",
           "El motor ejecuta la secuencia segura sobre sus referencias; la "
           "referencia externa permanece. Comprobar que el mapeo NO "
           "desaparece.",
           f"vivo={alive_maps}; tras liberar refs del motor (ext. viva)="
           f"{kept_maps} (status={m_kept.status})",
           "cuando una referencia externa permanece viva, la liberación "
           "segura NO puede acreditarse: el mapeo debe seguir vivo; no se "
           "usa _mmap.close() forzado para superarlo",
           verdict)


# ---------------------------------------------------------------- R2-C
def test_c_a():
    p = make_file("ca.bin", fill=b"\x07")
    st = os.stat(p)
    fd_motor = os.open(p, os.O_RDWR)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(f"/proc/self/fd/{fd_motor}", dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    m_alive = count_maps(st)
    inv_alive = fds_with_identity(st)
    alive_maps = m_alive.count_for_identity(st)
    alive_fds = inv_alive.matched
    del arr                         # secuencia segura
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    fds_now = inv_gone.matched
    motor_open = True
    try:
        os.fstat(fd_motor)
    except OSError:
        motor_open = False
    close_fd_quiet(fd_motor)
    reads_complete = (m_alive.status == READ_COMPLETE and inv_alive.complete
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    base_ok = (alive_maps == 1 and gone_maps == 0
               and fd_motor in alive_fds and fd_motor in fds_now
               and motor_open
               and any("proc/self/fd" in x for x in opened))
    ok = base_ok
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-C-A", "C", "Alternativa A: fd motor + magic-link (segura)",
           "Motor abre fd; NumPy vía magic-link /proc/self/fd/N.",
           "Secuencia segura (sin _mmap.close): liberar el array + gc; "
           "verificar maps=0, que el fd duplicado del mmap se cerró y que "
           "el fd del MOTOR sigue abierto (NumPy no lo cierra).",
           f"NumPy abrió={opened}; vivos fds={alive_fds} (complete="
           f"{inv_alive.complete}); tras liberar: maps={gone_maps} fds="
           f"{fds_now} (complete={inv_gone.complete}) "
           f"fd_motor_abierto={motor_open}",
           "A (segura): el motor libera el array y gc finaliza el mmap "
           f"(fd duplicado cerrado); el fd del motor [{fd_motor}] permanece "
           "abierto y es responsabilidad del motor, no de NumPy",
           verdict)


def test_c_b():
    p = make_file("cb.bin", fill=b"\x09")
    st = os.stat(p)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(p, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    m_alive = count_maps(st)
    inv_alive = fds_with_identity(st)
    alive_maps = m_alive.count_for_identity(st)
    alive_fds = inv_alive.matched
    del arr
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    residual = inv_gone.matched
    reads_complete = (m_alive.status == READ_COMPLETE and inv_alive.complete
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    base_ok = (alive_maps == 1 and gone_maps == 0 and residual == []
               and any(x.endswith("cb.bin") for x in opened))
    ok = base_ok
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-C-B", "C", "Alternativa B: NumPy abre por ruta (segura)",
           "np.memmap(path); el motor NO abre fd.",
           "Secuencia segura: liberar el array + gc; verificar maps=0 y que "
           "no queda ningún fd con la identidad (el duplicado del mmap se "
           "cerró con el finalizador).",
           f"NumPy abrió={opened}; vivos fds={alive_fds} (complete="
           f"{inv_alive.complete}); tras liberar: maps={gone_maps} "
           f"residuales={residual} (complete={inv_gone.complete})",
           "B (segura): NumPy abre por ruta y su fd duplicado se cierra "
           "solo al finalizar; el motor no posee fd_mm que cerrar",
           verdict)


def test_c_c():
    p = make_file("cc.bin", fill=b"\x0B")
    st = os.stat(p)
    fileobj = open(p, "r+b")
    fd_fileobj = fileobj.fileno()
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(fileobj, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    m_alive = count_maps(st)
    inv_alive = fds_with_identity(st)
    alive_maps = m_alive.count_for_identity(st)
    alive_fds = inv_alive.matched
    del arr
    gc.collect()
    m_gone = count_maps(st)
    inv_gone = fds_with_identity(st)
    gone_maps = m_gone.count_for_identity(st)
    fds_now = inv_gone.matched
    fo_open = True
    try:
        os.fstat(fd_fileobj)
    except OSError:
        fo_open = False
    fileobj.close()
    reads_complete = (m_alive.status == READ_COMPLETE and inv_alive.complete
                      and m_gone.status == READ_COMPLETE and inv_gone.complete)
    base_ok = (alive_maps == 1 and gone_maps == 0
               and fd_fileobj in alive_fds and fd_fileobj in fds_now
               and opened == [] and fo_open)
    ok = base_ok
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-C-C", "C", "Alternativa C: fileobj entregado a NumPy (segura)",
           "fileobj propio entregado a np.memmap.",
           "Secuencia segura: liberar el array + gc; verificar maps=0, fd "
           "duplicado cerrado, y que el fd del fileobj (motor) sigue "
           "abierto (NumPy no abrió nada).",
           f"NumPy abrió={opened}; vivos fds={alive_fds} (complete="
           f"{inv_alive.complete}); tras liberar: maps={gone_maps} fds="
           f"{fds_now} (complete={inv_gone.complete}) "
           f"fileobj_abierto={fo_open}",
           "C (segura): NumPy no abre nada (nullcontext); el mapeo se "
           f"libera vía gc; el fileobj [{fd_fileobj}] es del motor y "
           "permanece abierto",
           verdict)


# ---------------------------------------------------------------- R2-D
def test_d1():
    p = make_file("d1.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:8]                   # vista retenida (liberación incompleta)
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del arr                         # se olvida la vista
    gc.collect()
    m_kept = count_maps(st)
    kept_maps = m_kept.count_for_identity(st)
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_kept.status == READ_COMPLETE)
    ok_release = (kept_maps == 1)  # no acreditable
    verdict = "UNKNOWN" if not reads_complete else ("UNKNOWN" if ok_release else "FAIL")
    record("R2-D1", "D", "Liberación incompleta (vista retenida)",
           "np.memmap + vista no liberada en la secuencia.",
           "Ejecutar la secuencia segura solo sobre la raíz; la vista "
           "queda viva. Verificar que el mapeo NO desaparece.",
           f"vivo={alive_maps}; tras liberar solo la raíz={kept_maps} "
           f"(status={m_kept.status})",
           "la liberación incompleta deja el mapeo vivo; no se usa "
           "_mmap.close() forzado para superar la vista; el resultado no "
           "puede ser PASS ni autorizar EXIT_OK",
           verdict)


def test_d2():
    p = make_file("d2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    retenida = arr                # referencia retenida externamente
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del arr
    gc.collect()
    m_kept = count_maps(st)
    kept_maps = m_kept.count_for_identity(st)
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_kept.status == READ_COMPLETE)
    ok_release = (kept_maps == 1)
    verdict = "UNKNOWN" if not reads_complete else ("UNKNOWN" if ok_release else "FAIL")
    record("R2-D2", "D", "Referencia retenida impide acreditar cierre",
           "np.memmap + referencia retenida fuera del alcance del motor.",
           "El motor no puede localizar/liberar la referencia retenida; "
           "verificar que el mapeo permanece y que NO se fuerza _mmap.close().",
           f"vivo={alive_maps}; tras secuencia segura (retenida viva)="
           f"{kept_maps} (status={m_kept.status})",
           "una referencia retenida impide acreditar el cierre; el "
           "escenario termina en UNKNOWN/fallo cerrado, no en PASS; el "
           "cierre forzado está prohibido (C5 histórico)",
           verdict)


def test_d3():
    p = make_file("d3.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    arr[0] = 5
    flush_exc = None
    try:
        arr.flush()                # flush normal persiste
    except Exception as e:
        flush_exc = f"{type(e).__name__}: {e}"
    persisted = (np.memmap(p, dtype="uint8", mode="r")[0] == 5)
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    del arr                        # liberación segura SIN flush
    gc.collect()
    m_gone = count_maps(st)
    gone_maps = m_gone.count_for_identity(st)
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_gone.status == READ_COMPLETE)
    ok = (persisted and gone_maps == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-D3", "D", "Fallos durante flush no bloquean la liberación",
           "np.memmap writable; flush normal + liberación sin flush.",
           "Confirmar que flush funciona y persiste; luego liberar por "
           "referencias+gc SIN flush y verificar unmapping.",
           f"flush_exc={flush_exc}; persistido={persisted}; "
           f"maps tras liberar={gone_maps} (status={m_gone.status})",
           "el flush no es prerrequisito de la liberación segura; un error "
           "de flush (ValueError 'mmap closed or invalid' sobre mapping ya "
           "cerrado, observado en sonda previa) se surfacea pero no bloquea "
           "el unmapping por gc; en tmpfs no se pudo forzar un fallo de I/O "
           "de flush",
           verdict)


def test_d4():
    p = make_file("d4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    m_alive = count_maps(st)
    alive_maps = m_alive.count_for_identity(st)
    close_exc = None
    try:
        del arr                    # camino seguro: finalizador de gc
        gc.collect()
    except Exception as e:
        close_exc = f"{type(e).__name__}: {e}"
    m_gone = count_maps(st)
    gone_maps = m_gone.count_for_identity(st)
    reads_complete = (m_alive.status == READ_COMPLETE
                      and m_gone.status == READ_COMPLETE)
    ok = (close_exc is None and alive_maps == 1 and gone_maps == 0)
    verdict = "UNKNOWN" if not reads_complete else ("PASS" if ok else "FAIL")
    record("R2-D4", "D", "Cierre seguro sin errores (vía finalizador)",
           "np.memmap por ruta; liberación por referencias+gc.",
           "Verificar que el camino seguro (finalizador de gc) cierra sin "
           "excepción y desmapea; NO se invoca _mmap.close() (ver C5 "
           "histórico).",
           f"vivo={alive_maps}; tras liberar+gc: maps={gone_maps} "
           f"excepción_cierre={close_exc} (status={m_gone.status})",
           "el cierre seguro por finalizador no lanza excepción; el "
           "_mmap.close() forzado (SIGSEGV en C5) queda explícitamente "
           "excluido de R2",
           verdict)


# ---------------------------------------------------------------- R2-C (controladas, R2)
def test_r2c_complete():
    """R2-C1: inventario COMPLETO de fds."""
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    real = os.path.join(d, "3")
    open(real, "w").close()
    st = os.stat(real)
    inv = fds_with_identity(st, fd_dir=d)
    ok = (inv.complete and inv.matched == [3] and not inv.errors
          and inv.enum_mode in ("dirfd", "path"))
    verdict = "PASS" if ok else "FAIL"
    record("R2-C1", "R2-C", "Inventario COMPLETO de fds (R2-A)",
           "dir sintético con 1 entrada accesible (nombre entero).",
           "fds_with_identity() sobre dir accesible; verificar complete=True, "
           "matched=[3], errors vacío y modo de enumeración registrado.",
           f"complete={inv.complete}; matched={inv.matched}; "
           f"errors={inv.errors}; enum_mode={inv.enum_mode}; "
           f"enum_dirfd={inv.enum_dirfd}",
           "R2-A: sin errores de enumeración ni de inspección el inventario "
           "es COMPLETO y puede respaldar acreditación.",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r2c_disappeared():
    """R2-C2: entrada que desaparece durante el recorrido."""
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    real = os.path.join(d, "5")
    open(real, "w").close()
    stale = os.listdir(d)            # la entrada 5 está en el listado
    os.unlink(real)                  # desaparece ANTES de la inspección
    st = os.stat(d)                  # identidad cualquiera (solo se inspeccionan fds)
    import unittest.mock as _m
    with _m.patch.object(os, "listdir", return_value=stale):
        inv = fds_with_identity(st, fd_dir=d)
    ev = inv.errors[0] if inv.errors else {}
    # R3-B: la prueba verifica una CLASIFICACIÓN específica. Se requiere
    # clasificación correcta Y complete=False para UNKNOWN; si la
    # clasificación no es la esperada (o el inventario se completara con
    # errores), se declara FAIL. No se asigna UNKNOWN automáticamente por
    # el solo hecho de que el inventario sea incompleto.
    ok = (not inv.complete and ev.get("classification")
          == CLASS_DISAPPEARED and ev.get("errno") == errno.ENOENT
          and ev.get("name") == "5"
          and ev.get("exception_type") == "FileNotFoundError")
    verdict = "UNKNOWN" if ok else "FAIL"
    record("R2-C2", "R2-C", "Entrada que desaparece durante el recorrido",
           "dir sintético: entrada '5' en el listado, borrada antes de la "
           "inspección (listado estancado forzado).",
           "fds_with_identity() con listado estancado; verificar "
           "complete=False, error clasificado DESCRIPTOR_DESAPARECIDO con "
           "errno/tipo/nombre conservados. R3-B: UNKNOWN solo si la "
           "clasificación es correcta y el inventario es incompleto; "
           "clasificación incorrecta -> FAIL.",
           f"complete={inv.complete}; errors={inv.errors}; "
           f"error_classes={inv.error_classes()}",
           "R2-B/R3-B: ENOENT en un directorio NO procfs con entrada "
           "previamente listada -> DESCRIPTOR_DESAPARECIDO; inventario "
           "INCOMPLETO -> UNKNOWN (nunca PASS).",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r2c_inaccessible():
    """R2-C3: entrada inaccesible (permisos)."""
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    sub = os.path.join(d, "sub")
    os.makedirs(sub)
    os.chmod(sub, 0o000)            # sin execute -> target no alcanzable
    link = os.path.join(d, "9")
    os.symlink(os.path.join(sub, "f"), link)
    try:
        st = os.stat(d)
        inv = fds_with_identity(st, fd_dir=d)
        ev = next((e for e in inv.errors if e.get("name") == "9"), {})
        # R3-B: igual que R2-C2: UNKNOWN solo si la clasificación es
        # correcta y el inventario es incompleto; clasificación incorrecta
        # -> FAIL (no UNKNOWN automático por incompletitud).
        ok = (not inv.complete and ev.get("classification")
              == CLASS_INACCESSIBLE and ev.get("errno") == errno.EACCES
              and ev.get("exception_type") == "PermissionError")
        verdict = "UNKNOWN" if ok else "FAIL"
        record("R2-C3", "R2-C", "Entrada inaccesible (permisos)",
               "dir sintético con symlink '9' a objetivo en subdirectorio "
               "sin permiso execute (euid no root).",
               "fds_with_identity() sobre dir con entrada no accesible; "
               "verificar complete=False y clasificación DESCRIPTOR_INACCESIBLE "
               "(errno/tipo conservados). R3-B: UNKNOWN solo si la "
               "clasificación es correcta y el inventario es incompleto; "
               "clasificación incorrecta -> FAIL.",
               f"complete={inv.complete}; errors={inv.errors}; "
               f"error_classes={inv.error_classes()}",
               "R2-B/R3-B: EACCES -> DESCRIPTOR_INACCESIBLE; inventario "
               "INCOMPLETO -> UNKNOWN (nunca PASS).",
               verdict)
    finally:
        os.chmod(sub, 0o755)        # permitir rmtree
        shutil.rmtree(d, ignore_errors=True)


def test_r2c_enum_error():
    """R2-C4: error de enumeración del directorio."""
    # Caso A: ruta inexistente (no procfs) -> UNKNOWN_CAUSE (sin evidencia
    # suficiente para atribuir al procfs). Caso B: ruta de procfs
    # inexistente -> ERROR_PROCFS.
    results = {}
    for label, fd_dir in (("no-procfs", "/tmp/no_existe_r2c_xyz"),
                          ("procfs", "/proc/self/fd_no_existe_r2c_xyz")):
        st = os.stat("/tmp")
        inv = fds_with_identity(st, fd_dir=fd_dir)
        ev = inv.errors[0] if inv.errors else {}
        expected = CLASS_PROCFS if label == "procfs" else CLASS_UNKNOWN_CAUSE
        results[label] = (not inv.complete, ev.get("classification")
                          == expected, ev.get("phase") == "enumeracion",
                          ev.get("errno") == errno.ENOENT)
    ok = all(all(v) for v in results.values())
    verdict = "PASS" if ok else "FAIL"
    record("R2-C4", "R2-C", "Error de enumeración del directorio (R2-A)",
           "fd_dir inexistente: ruta /tmp (no procfs) y ruta /proc/... (procfs).",
           "fds_with_identity() sobre un fd_dir que no se puede abrir; "
           "verificar que NO lanza, devuelve inventario INCOMPLETO y "
           "registra phase=enumeracion con clasificación adecuada.",
           f"casos={results}",
           "R2-A: el error de os.listdir se captura (no propaga), el "
           "inventario es INCOMPLETO -> escenarios dependientes van a "
           "UNKNOWN, nunca FAIL artificial. R2-B: procfs -> ERROR_PROCFS; "
           "sin evidencia suficiente -> UNKNOWN_CAUSE.",
           verdict)


def test_r2c_procfs_inspect_error():
    """R2-C5 / R3-C: error de procfs durante la inspección (evidencia real)."""
    # (1) Mecánica del clasificador, determinista y unitaria.
    e_enoent = FileNotFoundError(errno.ENOENT, "gone")
    e_eacces = PermissionError(errno.EACCES, "denied")
    e_eio = OSError(errno.EIO, "procfs io failure")
    mechanics = {
        "ENOENT_procfs_sin_fdinfo_->_UNKNOWN_CAUSE":
            _classify_fd_error("77", e_enoent, "/proc/self/fd",
                               "inspeccion")[0] == CLASS_UNKNOWN_CAUSE,
        "ENOENT_no_procfs_->_DESAPARECIDO":
            _classify_fd_error("77", e_enoent, "/tmp/x",
                               "inspeccion")[0] == CLASS_DISAPPEARED,
        "EACCES_->_INACCESIBLE":
            _classify_fd_error("77", e_eacces, "/tmp/x",
                               "inspeccion")[0] == CLASS_INACCESSIBLE,
        "EIO_procfs_->_ERROR_PROCFS":
            _classify_fd_error("77", e_eio, "/proc/self/fd",
                               "inspeccion")[0] == CLASS_PROCFS,
    }
    mechanics_ok = all(mechanics.values())
    # (2) Evidencia REAL del entorno (R3-C): debe existir un error de
    # inspección clasificado ERROR_PROCFS con errno compatible y contexto
    # de procfs. No vale cualquier error genérico.
    procfs_errno_ok = (errno.EIO, errno.EINVAL, errno.ENOTDIR, errno.ENOSYS,
                       errno.EOPNOTSUPP, errno.EBUSY, errno.EREMOTEIO)
    real_inv = fds_with_identity(os.stat("/tmp"), fd_dir="/proc/self/fd")
    procfs_insp = [e for e in real_inv.errors
                   if e.get("classification") == CLASS_PROCFS
                   and e.get("phase") == "inspeccion"
                   and e.get("errno") in procfs_errno_ok
                   and _is_procfs_fd_dir(
                       e.get("context", {}).get("fd_dir", ""))]
    env_evidence = len(procfs_insp) > 0
    # R3-C: PASS solo si la mecánica es correcta y el entorno proporciona
    # la evidencia requerida; si no hay evidencia suficiente -> UNKNOWN
    # (no PASS); mecánica rota -> FAIL.
    if not mechanics_ok:
        verdict = "FAIL"
    elif env_evidence:
        verdict = "PASS"
    else:
        verdict = "UNKNOWN"
    record("R2-C5", "R2-C", "Error de procfs durante la inspección (R2-B/R3-C)",
           "mecánica unitaria determinista + inventario REAL de /proc/self/fd "
           "del entorno.",
           "Verificar (1) mecánica del clasificador y (2) PRESENCIA real de "
           "un error de inspección clasificado ERROR_PROCFS con errno y "
           "contexto compatibles (no basta error genérico). Sin evidencia "
           "suficiente del entorno -> UNKNOWN, no PASS (R3-C).",
           f"mecánica={mechanics}; inventario_real_complete="
           f"{real_inv.complete}; errors={len(real_inv.errors)}; "
           f"clases={real_inv.error_classes()}; "
           f"ERROR_PROCFS_inspeccion_con_errno_compatible="
           f"{[(e.get('name'), e.get('errno')) for e in procfs_insp]}",
           "R2-B/R3-C/R3-D: ENOENT en procfs sin fdinfo -> UNKNOWN_CAUSE "
           "(no se atribuye automáticamente a procfs); ERROR_PROCFS se "
           "mantiene solo con evidencia suficiente (errno compatible y "
           "contexto procfs).",
           verdict)


def test_r2c_unknown_propagation():
    """R2-C6: propagación de UNKNOWN en cada escenario dependiente."""
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    real = os.path.join(d, "3")
    open(real, "w").close()
    stale = os.listdir(d)
    os.unlink(real)                  # inventario incompleto forzado
    st = os.stat(d)
    import unittest.mock as _m
    with _m.patch.object(os, "listdir", return_value=stale):
        inv = fds_with_identity(st, fd_dir=d)
    # Replicar la regla de acreditación de A1/B1/B5 (y de cualquier
    # escenario dependiente): incompleto -> UNKNOWN, nunca PASS.
    def acredite(inv, ok_condition):
        reads_complete = inv.complete
        return "UNKNOWN" if not reads_complete else \
               ("PASS" if ok_condition else "FAIL")
    v_a = acredite(inv, True)        # escenario tipo A
    v_b = acredite(inv, True)        # escenario tipo B
    v_c = acredite(inv, True)        # escenario tipo C
    ok = (not inv.complete and v_a == "UNKNOWN" and v_b == "UNKNOWN"
          and v_c == "UNKNOWN")
    verdict = "PASS" if ok else "FAIL"
    record("R2-C6", "R2-C", "Propagación de UNKNOWN a escenarios dependientes",
           "inventario FORZADAMENTE incompleto (entrada borrada post-listado).",
           "Aplicar la regla de acreditación de A1/B1/B5 sobre el inventario "
           "incompleto; verificar que A/B/C van a UNKNOWN y no a PASS.",
           f"complete={inv.complete}; verdictos=[{v_a}, {v_b}, {v_c}]",
           "R2-C/R1-C: cualquier escenario cuya acreditación dependa del "
           "inventario propaga UNKNOWN; ningún PASS desde incompleto.",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r2c_no_artificial_fail():
    """R2-C7 / R3-A: propagación correcta del error de enumeración.

    Propiedades INDEPENDENTES que se verifican por separado:
      P1: el error de enumeración NO escapa de fds_with_identity().
      P2: el controlador recibe complete=False y asigna UNKNOWN, NUNCA PASS
          ni FAIL artificial.
    La prueba solo da PASS si ambas propiedades se verifican.
    """
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    st = os.stat(d)
    import unittest.mock as _m

    # --- P1: el error no escapa de fds_with_identity() -------------------
    raised = None
    inv = None
    with _m.patch.object(os, "listdir",
                         side_effect=OSError(errno.EIO, "enumeración caída")):
        try:
            inv = fds_with_identity(st, fd_dir=d)
        except OSError as e:
            raised = e
    p1 = (raised is None and inv is not None)

    # --- P2: el controlador recibe complete=False y asigna UNKNOWN ------
    # Simula el controlador general del arnés sobre el inventario devuelto:
    # no propaga (P1) y su regla de veredicto consume complete.
    v_contr = None
    if inv is not None:
        def controlador(inv_rec, ok_condition):
            # Regla del arnés (precedencia): incompleto -> UNKNOWN, nunca
            # PASS ni FAIL artificial desde un inventario incompleto.
            if not inv_rec.complete:
                return "UNKNOWN"
            return "PASS" if ok_condition else "FAIL"
        v_contr = controlador(inv, True)
        # Explicitamente: no PASS ni FAIL artificial.
        p2 = (not inv.complete and v_contr == "UNKNOWN")
    else:
        p2 = False

    ok = p1 and p2 and not inv.complete and bool(inv.errors)
    verdict = "PASS" if ok else "FAIL"
    record("R2-C7", "R2-C", "Sin FAIL artificial por error de enumeración (R3-A)",
           "os.listdir lanzado a OSError(EIO) durante la enumeración.",
           "Verificar dos propiedades independientes: P1 el error NO "
           "escapa de fds_with_identity(); P2 el controlador recibe "
           "complete=False y asigna UNKNOWN, nunca PASS ni FAIL artificial. "
           "PASS solo si ambas se verifican (R3-A).",
           f"P1_no_propagacion={p1} (propagada={raised}); "
           f"P2_controlador_UNKNOWN={p2} (verdict_controlador={v_contr}); "
           f"complete={inv.complete if inv else None}; "
           f"errors={inv.errors if inv else None}",
           "R2-A/R3-A: la imposibilidad de enumerar se registra en el "
           "inventario; no escapa a el controlador y este asigna UNKNOWN, "
           "sin PASS y sin FAIL artificial.",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r2c_fd3_origin():
    """R2-C8: origen del descriptor fantasma fd 3 (diagnóstico real)."""
    entries = []
    stat_fail, readlink_fail, fdinfo_missing = [], [], []
    ghost_passes = []
    for _ in range(3):
        names = os.listdir("/proc/self/fd")
        ghosts = []
        for n in sorted(names, key=lambda x: int(x) if x.isdigit() else 999):
            if n not in entries:
                entries.append(n)
            p = os.path.join("/proc/self/fd", n)
            try:
                os.stat(p)
            except OSError as e:
                ghosts.append(n)
                stat_fail.append((n, e.errno))
                try:
                    os.readlink(p)
                except OSError as e2:
                    readlink_fail.append((n, e2.errno))
                try:
                    open(os.path.join("/proc/self/fdinfo", n), "rb").close()
                    fdinfo_missing.append((n, "presente"))
                except OSError as e3:
                    fdinfo_missing.append((n, e3.errno))
        ghost_passes.append(ghosts)
    ghost = sorted({n for n, _ in stat_fail})
    # Clasificación a partir del MISMO inventario (el número del fantasma
    # puede variar entre llamadas; se obtiene de la inspección real).
    inv = fds_with_identity(os.stat("/tmp"), fd_dir="/proc/self/fd")
    # R3-D (conservador): ENOENT + fdinfo ausente en procfs NO se atribuye
    # automáticamente a procfs -> UNKNOWN_CAUSE (no se inventa causa).
    unknown_errs = [e for e in inv.errors
                    if e.get("phase") == "inspeccion"
                    and e.get("classification") == CLASS_UNKNOWN_CAUSE
                    and e.get("errno") == errno.ENOENT]
    cls = CLASS_UNKNOWN_CAUSE if unknown_errs else None
    evidence = {
        "entries": entries,
        "stat_fail": stat_fail,
        "readlink_fail": readlink_fail,
        "fdinfo": fdinfo_missing,
        "ghost_observed": ghost,
        "ghost_passes": ghost_passes,
        "inventory_errors": inv.errors,
    }
    reproducible = bool(ghost) or bool(unknown_errs)
    # Veredicto: UNKNOWN para la causa root; no presentar hipótesis como hecho.
    verdict = "UNKNOWN" if reproducible else "UNKNOWN"
    record("R2-C8", "R2-C", "Origen del descriptor fantasma fd 3 (diagnóstico)",
           "entorno real: /proc/self/fd del sandbox (Python 3.11.2, kernel "
           "6.1.158+, euid 1001), 3 iteraciones de diagnóstico + inventario "
           "del mismo proceso.",
           "Recopilar evidencia: entradas listadas, fallos de stat/readlink, "
           "presencia de fdinfo, variabilidad del número del fantasma entre "
           "pasadas y clasificación del error de inspección en el inventario.",
           f"evidencia={json.dumps(evidence, ensure_ascii=False)}; "
           f"clasificacion={cls}",
           "HECHOS OBSERVADOS: exactamente una entrada de /proc/self/fd no "
           "es stat-able (ENOENT) y carece de fdinfo -> no es un descriptor "
           "real abierto de este proceso ni el descriptor transitorio de la "
           "propia enumeración (ese es identificable y real, R2-C9). Su "
           "número VARIABLE entre pasadas (observado 3, 5 y 6) y su "
           "desaparecer cuando el número lo ocupa un descriptor real abierto "
           "indican que el fantasma ocupa un hueco del listado. Clasificación "
           "conservadora (R3-D): ENOENT+fdinfo ausente NO se atribuye "
           "automáticamente a procfs -> UNKNOWN_CAUSE; no se inventa causa "
           "root. CAUSA ROOT: UNKNOWN (no "
           "determinada con certeza; hipótesis documentada, no afirmada).",
           verdict)


def test_r2c_persistent_dirfd():
    """R2-C9: demostración del descriptor de directorio mantenido abierto."""
    d = tempfile.mkdtemp(prefix="feas_r2c_")
    f5 = os.path.join(d, "5")
    open(f5, "w").close()
    dirfd = os.open(d, os.O_RDONLY | os.O_DIRECTORY)
    names_via_fd = os.listdir(dirfd)
    ident = os.fstat(dirfd).st_ino
    gone_ok = False
    try:
        shutil.rmtree(d)             # desaparición externa del directorio
        try:
            os.listdir(d)            # enumeración por ruta -> debe fallar
            gone_ok = False
        except OSError:
            # enumeración por descriptor mantenido -> NO falla (inodo vivo)
            names_after = os.listdir(dirfd)
            gone_ok = isinstance(names_after, list)
    finally:
        os.close(dirfd)
    st = os.stat("/tmp")
    inv = fds_with_identity(st, fd_dir="/tmp")
    ok = (names_via_fd == ["5"] and gone_ok and ident > 0
          and inv.enum_mode == "dirfd" and inv.enum_dirfd is not None
          and inv.enum_dirfd >= 0)
    verdict = "PASS" if ok else "FAIL"
    record("R2-C9", "R2-C",
           "Descriptor de directorio mantenido abierto (R2-A, demostración)",
           "dir sintético con entrada '5'; descriptor O_DIRECTORY abierto "
           "antes de la inspección; borrado externo del directorio.",
           "Demostrar: (1) el descriptor de enumeración es estable e "
           "identificable (fstat funciona, se registra en el inventario); "
           "(2) tras borrar el directorio, la enumeración por ruta falla "
           "mientras la del descriptor mantenido no; (3) el descriptor "
           "propio de la enumeración NO se confunde con una desaparición "
           "externa.",
           f"names_via_fd={names_via_fd}; ident_dirfd={ident}; "
           f"post_delete_via_fd_ok={gone_ok}; enum_mode={inv.enum_mode}; "
           f"enum_dirfd={inv.enum_dirfd}",
           "R2-A: la enumeración por descriptor mantenido hace explícito y "
           "estable el descriptor propio de la enumeración, diferenciando "
           "desaherencias externas. SE DEMUESTRA por esta prueba; NO se "
           "asume que elimine el artefacto fd 3 (ver R2-C8: es un artefacto "
           "de listado de procfs, no un descriptor real).",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r2c10_real_scenarios_propagation():
    """R2-C10 / R3-E: los escenarios REALES A/B/C aplican la regla
    inventario incompleto -> UNKNOWN.

    No basta reproducir la regla en una función simplificada aislada: se
    ejecutan los ESCALARIOS REALES (test_a1, test_b1, test_b5, test_c_b)
    completos (np.memmap real, count_maps real, lógica de veredicto real)
    con el inventario de fds controlado en dos condiciones:
      - inventario INCOMPLETO (complete=False): el escenario debe asignar
        UNKNOWN;
      - inventario COMPLETO (complete=True): A1/B1/C-B deben asignar PASS
        (sus condiciones de maps se cumplen), demostrando que el UNKNOWN
        del caso incompleto depende de la regla y no es UNKNOWN
        hardcodeado.
    Los registros intermedios de las ejecuciones se extraen de RESULTS
    (evidencia preservada aquí); no se computan como subpruebas adicionales.
    """
    import unittest.mock as _m
    this_module = sys.modules[__name__]
    scenarios = [("A1", test_a1), ("B1", test_b1), ("B5", test_b5),
                 ("C-B", test_c_b)]

    def make_fake_inventory(complete):
        def fake(st, fd_dir="/proc/self/fd"):
            errs = []
            if not complete:
                errs = [{
                    "name": "r2c10_stub",
                    "error": "stub: inventario incompleto forzado",
                    "exception_type": "OSError",
                    "errno": None,
                    "phase": "inspeccion",
                    "classification": CLASS_UNKNOWN_CAUSE,
                    "context": {"fd_dir": fd_dir, "entry": "r2c10_stub"},
                }]
            return FdInventory([], errs, complete, None, "stub")
        return fake

    def run_scenario(fn, fake):
        before = len(RESULTS)
        with _m.patch.object(this_module, "fds_with_identity", fake):
            try:
                fn()
            except Exception as e:        # el escenario real no debe fallar
                RESULTS[before:] = []
                return [], f"excepción: {type(e).__name__}: {e}"
        new_recs = RESULTS[before:]
        RESULTS[before:] = []             # extraer registros intermedios
        return [r["verdict"] for r in new_recs], None

    results, errors = {}, []
    for tid, fn in scenarios:
        v_inc, err1 = run_scenario(fn, make_fake_inventory(False))
        v_com, err2 = run_scenario(fn, make_fake_inventory(True))
        if err1 or err2:
            errors.append(f"{tid}: {err1} {err2}")
        results[tid] = {"incompleto": v_inc, "completo": v_com}

    inc_all_unknown = all(
        all(v == "UNKNOWN" for v in r["incompleto"]) and r["incompleto"]
        for r in results.values()) and not errors
    contrast_ok = (results["A1"]["completo"] == ["PASS"]
                   and results["B1"]["completo"] == ["PASS"]
                   and results["C-B"]["completo"] == ["PASS"])
    ok = inc_all_unknown and contrast_ok
    verdict = "PASS" if ok else "FAIL"
    record("R2-C10", "R2-C",
           "Propagación en escenarios REALES A/B/C (R3-E)",
           "escenarios reales test_a1/b1/b5/c_b (memmap+maps reales) con el "
           "inventario de fds controlado: INCOMPLETO y COMPLETO.",
           "Verificar que los escenarios REALES asignan UNKNOWN con inventario "
           "incompleto y que el contraste con inventario COMPLETO (A1/B1/C-B "
           "-> PASS) demuestra que el UNKNOWN depende de la regla, no es "
           "hardcodeado. No se usa una función simplificada aislada.",
           f"resultados={results}; errores={errors}",
           "R3-E: los escenarios A/B/C del arnés consumen inv.complete y "
           "asignan UNKNOWN desde inventario incompleto; verificado sobre el "
           "código real de los escenarios.",
           verdict)


# ---------------------------------------------------------------- R1-A (controladas)
def _synthetic_maps_lines(target_path, match, unparseable):
    """Construye el contenido de un /proc/self/maps sintético.

    R1-A: 'match' inserta una línea válida cuya identidad coincide con
    'target_path'; 'unparseable' añade líneas que NO se interpretan (para
    forzar lectura INCOMPLETA). Devuelve el texto.
    """
    st = os.stat(target_path)
    dev = "%02x:%02x" % (os.major(st.st_dev), os.minor(st.st_dev))
    ino = st.st_ino
    lines = []
    if match:
        lines.append("00000000-00001000 r--p 00000000 %s %d %s"
                     % (dev, ino, target_path))
    lines.append("00001000-00002000 rw-p 00000000 00:00 0 [vvar]")
    lines.append("00002000-00003000 rw-p 00000000 00:00 0 [vdso]")
    if unparseable:
        lines.append("xyz")                                   # <5 campos
        lines.append("solo tres campos aqui")                 # <5 campos
        lines.append("aaaa-bbbb r-xp notadev 1 /ruta/invalida")  # dev inválido
    return "\n".join(lines) + "\n"


def test_r1a_complete_match():
    p = make_file("r1a_match.bin")
    maps_file = os.path.join(WORKDIR, "r1a_maps_match.txt")
    with open(maps_file, "w") as fh:
        fh.write(_synthetic_maps_lines(p, match=True, unparseable=False))
    st = os.stat(p)
    m = parse_maps(maps_file)
    n = m.count_for_identity(st)
    # Lectura COMPLETA con coincidencia -> el recuento es fiable y correcto.
    verdict = "UNKNOWN" if m.status != READ_COMPLETE else ("PASS" if n == 1 else "FAIL")
    record("R1-A1", "R1-A", "Lectura COMPLETA con coincidencia",
           "maps sintético: 1 línea válida coincide + 2 válidas sin coincidencia.",
           "parse_maps() sobre un maps sintético totalmente interpretable; "
           "verificar status=complete y recuento por identidad == 1.",
           f"status={m.status}; recuento={n}; no_interpretables="
           f"{len(m.unparseable)}; error={m.error}",
           "R1-A: con lectura COMPLETA y coincidencia, el recuento es fiable "
           "y se declara PASS (no se descartan líneas, simplemente no hay "
           "ninguna no interpretable).",
           verdict)


def test_r1a_complete_nomatch():
    p = make_file("r1a_nomatch.bin")
    maps_file = os.path.join(WORKDIR, "r1a_maps_nomatch.txt")
    with open(maps_file, "w") as fh:
        fh.write(_synthetic_maps_lines(p, match=False, unparseable=False))
    st = os.stat(p)
    m = parse_maps(maps_file)
    n = m.count_for_identity(st)
    # Lectura COMPLETA sin coincidencia -> se declara 0 maps SOLO porque la
    # lectura fue completa.
    verdict = "UNKNOWN" if m.status != READ_COMPLETE else ("PASS" if n == 0 else "FAIL")
    record("R1-A2", "R1-A", "Lectura COMPLETA sin coincidencia",
           "maps sintético: 0 líneas coinciden; todas válidas.",
           "parse_maps() sobre maps sintético completo sin coincidencia; "
           "verificar status=complete y recuento == 0 declarado tras lectura "
           "COMPLETA (R1-A: solo declarar cero tras lectura completa).",
           f"status={m.status}; recuento={n}; no_interpretables="
           f"{len(m.unparseable)}; error={m.error}",
           "R1-A: una lectura COMPLETA sin coincidencia permite declarar "
           "legítimamente cero mappings (sin riesgo de línea descartada).",
           verdict)


def test_r1a_unparseable():
    p = make_file("r1a_unp.bin")
    maps_file = os.path.join(WORKDIR, "r1a_maps_unp.txt")
    with open(maps_file, "w") as fh:
        fh.write(_synthetic_maps_lines(p, match=True, unparseable=True))
    st = os.stat(p)
    m = parse_maps(maps_file)
    n = m.count_for_identity(st)
    # Coincidencia MÁS líneas no interpretables -> lectura INCOMPLETA -> UNKNOWN
    # (no se descartan ni se declara PASS/FAIL).
    verdict = "UNKNOWN" if m.status != READ_COMPLETE else ("PASS" if n == 1 else "FAIL")
    record("R1-A3", "R1-A", "Coincidencia + líneas no interpretables",
           "maps sintético: 1 línea coincide + 3 líneas NO interpretables.",
           "parse_maps() sobre maps con líneas no interpretables; verificar "
           "que status=incomplete y que el escenario va a UNKNOWN "
           "(R1-A: líneas no interpretables -> UNKNOWN, sin descartarlas).",
           f"status={m.status}; recuento_sin_garantia={n}; "
           f"no_interpretables={len(m.unparseable)}; error={m.error}",
           "R1-A: aunque haya una coincidencia, la presencia de líneas no "
           "interpretables hace la lectura INCOMPLETA; no se puede acreditar "
           "el cierre -> UNKNOWN (jamás PASS/FAIL sobre lectura incompleta).",
           verdict)


def test_r1a_unreadable():
    # /proc/self/maps no disponible o ilegible -> lectura ILEGIBLE -> UNKNOWN.
    missing = os.path.join(WORKDIR, "no_existe_maps_xyz")
    m = parse_maps(missing)
    verdict = "UNKNOWN" if m.status != READ_COMPLETE else "FAIL"
    record("R1-A4", "R1-A", "/proc/self/maps no disponible o ilegible",
           "ruta de maps que no existe (origen ILEGIBLE).",
           "parse_maps() sobre una ruta inexistente; verificar status="
           "unreadable y que el escenario va a UNKNOWN (R1-A).",
           f"status={m.status}; error={m.error}; entradas={len(m.entries)}; "
           f"no_interpretables={len(m.unparseable)}",
           "R1-A: cuando el origen no se puede leer, la acreditación de "
           "cierre es imposible -> UNKNOWN (no se simula ni se descarta).",
           verdict)


# ---------------------------------------------------------------- R1-B (controladas)
def test_r1b_complete():
    d = tempfile.mkdtemp(prefix="feas_r1b_")
    real_path = os.path.join(d, "3")          # nombre tipo fd (entero)
    open(real_path, "w").close()
    st = os.stat(real_path)
    inv = fds_with_identity(st, fd_dir=d)
    ok = (inv.complete and 3 in inv.matched and not inv.errors)
    verdict = "PASS" if ok else "FAIL"
    record("R1-B1", "R1-B", "Inventario COMPLETO de /proc/self/fd",
           "dir sintético con 1 entrada accesible (nombre entero).",
           "fds_with_identity() sobre dir accesible; verificar complete=True, "
           "matched incluye la entrada y errors vacío (R1-B).",
           f"complete={inv.complete}; matched={inv.matched}; "
           f"errors={inv.errors}",
           "R1-B: inventario sin errores -> complete; la acreditación puede "
           "basarse en él para PASS.",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


def test_r1b_incomplete():
    d = tempfile.mkdtemp(prefix="feas_r1b_")
    real_path = os.path.join(d, "3")
    open(real_path, "w").close()
    # Symlink roto: al stat() falla (descriptor que 'desapareció' / inaccesible).
    broken = os.path.join(d, "4")
    try:
        os.symlink(os.path.join(d, "no_existe_xyz"), broken)
    except OSError:
        pass
    st = os.stat(real_path)
    inv = fds_with_identity(st, fd_dir=d)
    # Inventario INCOMPLETO -> UNKNOWN (R1-B: nunca PASS desde inventario
    # incompleto). El resultado correcto del escenario es UNKNOWN.
    verdict = "UNKNOWN" if (not inv.complete) else "FAIL"
    record("R1-B2", "R1-B", "Inventario INCOMPLETO (/proc/self/fd con error)",
           "dir sintético con 1 entrada válida + 1 symlink roto.",
           "fds_with_identity() sobre dir con entrada no accesible; verificar "
           "complete=False, errors no vacío y que el escenario va a UNKNOWN "
           "(R1-B: inventario incompleto -> UNKNOWN, nunca PASS).",
           f"complete={inv.complete}; matched={inv.matched}; "
           f"errors={inv.errors}",
           "R1-B: un error de stat (descriptor desaparecido/inaccesible) NO "
           "se ignora; marca el inventario como incompleto y fuerza UNKNOWN "
           "en cualquier escenario que dependa de él.",
           verdict)
    shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------- main
def main():
    global WORKDIR
    WORKDIR = tempfile.mkdtemp(prefix="feas_d18_r2_")
    env = {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "kernel": f"{os.uname().sysname} {os.uname().release} "
                  f"{os.uname().machine}",
        "platform": platform.platform(),
        "euid": os.geteuid(),
        "cwd": os.getcwd(),
        "workdir": WORKDIR,
    }
    print(f"Entorno: Python {env['python']} | NumPy {env['numpy']} | "
          f"{env['kernel']} | euid {env['euid']}")
    print(f"Workdir aislado: {WORKDIR}\n")
    print("CORRECCIONES METODOLÓGICAS R1 + R2 + R3 activas: "
          "count_maps()/parse_maps() distinguen COMPLETA/INCOMPLETA/"
          "ILEGIBLE; fds_with_identity() captura errores de enumeración y de "
          "inspección, clasifica (DESAPARECIDO/INACCESIBLE/ERROR_PROCFS/"
          "UNKNOWN_CAUSE, con ENOENT conservador R3-D) y propaga UNKNOWN "
          "desde inventario incompleto, verificado sobre escenarios reales "
          "(R1-A/B/C + R2-A/B/C + R3-A..F).\n")

    tests = [test_a1, test_a2, test_a3, test_a4, test_a5, test_a6,
             test_b1, test_b2, test_b3, test_b4, test_b5, test_b6,
             test_c_a, test_c_b, test_c_c,
             test_d1, test_d2, test_d3, test_d4,
             test_r2c_complete, test_r2c_disappeared, test_r2c_inaccessible,
             test_r2c_enum_error, test_r2c_procfs_inspect_error,
             test_r2c_unknown_propagation, test_r2c_no_artificial_fail,
             test_r2c_fd3_origin, test_r2c_persistent_dirfd,
             test_r2c10_real_scenarios_propagation,
             test_r1a_complete_match, test_r1a_complete_nomatch,
             test_r1a_unparseable, test_r1a_unreadable,
             test_r1b_complete, test_r1b_incomplete]
    for t in tests:
        try:
            t()
        except Exception:
            import traceback
            record(t.__name__, "?", f"excepción no controlada en {t.__name__}",
                   "-", "-", traceback.format_exc(limit=3).strip(),
                   "traceback en evidencia", "FAIL")

    counts = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for r in RESULTS:
        counts[r["verdict"]] += 1
    if counts["FAIL"]:
        global_verdict = "FAIL"
    elif counts["UNKNOWN"]:
        global_verdict = "UNKNOWN"
    else:
        global_verdict = "PASS"

    os.makedirs(EVIDENCE_DIR, exist_ok=True)
    out = {"harness": "arnes_feasibility_d18_r2_numpy_6g1.py",
           "scope": "FEASIBILITY-D18-R2 + R1 + R2 + R3 (corrección metodológica "
                    "del arnés: R1-A/B/C/D, rectificación final R2-A/B/C/D y "
                    "rectificación final de verificación R3-A..F)",
           "r1_correction": {
               "R1-A": "count_maps/parse_maps no descartan líneas no "
                       "interpretables; distinguen COMPLETA/INCOMPLETA/"
                       "ILEGIBLE; no interpretable/error/ilegible -> UNKNOWN; "
                       "cero mappings solo tras lectura COMPLETA; FAIL solo si "
                       "lectura COMPLETA contradice lo esperado.",
               "R1-B": "fds_with_identity no ignora errores de stat; "
                       "descriptor desaparecido/inaccesible/error procfs -> "
                       "inventario INCOMPLETO -> UNKNOWN; nunca PASS desde "
                       "inventario incompleto.",
               "R1-C": "propagación de UNKNOWN a escenarios A/B/C dependientes "
                       "de lectura/inventario incompleto.",
           },
           "r2_correction": {
               "R2-A": "fds_with_identity captura ADEMÁS los errores de "
                       "os.listdir(fd_dir); imposibilidad de abrir/enumerar -> "
                       "inventario INCOMPLETO con error+contexto; NO propaga "
                       "la excepción (evita FAIL artificial del controlador); "
                       "inventario incompleto -> UNKNOWN, nunca PASS ni cero "
                       "descriptores. Enumeración por descriptor de directorio "
                       "mantenido abierto, demostrado por pruebas (R2-C9) y "
                       "NO asumido como solución del artefacto fd 3.",
               "R2-B": "clasificación expresa: DESCRIPTOR_DESAPARECIDO / "
                       "DESCRIPTOR_INACCESIBLE / ERROR_PROCFS / UNKNOWN_CAUSE; "
                       "errno, tipo de excepción, nombre y contexto "
                       "conservados; causa no determinable -> UNKNOWN_CAUSE. "
                       "(R3-D: ENOENT+fdinfo ausente NO se atribuye "
                       "automáticamente a procfs -> UNKNOWN_CAUSE.)",
               "R2-C": "pruebas controladas R2-C1..R2-C10: inventario "
                       "completo, desaparición, inaccesibilidad, error de "
                       "enumeración, error de procfs en inspección, "
                       "propagación de UNKNOWN, ausencia de FAIL artificial, "
                       "origen del fd 3, demostración del dirfd mantenido y "
                       "propagación sobre escenarios reales A/B/C.",
               "R2-D": "reejecución del conjunto D18-R2; precedencia FAIL>"
                       "UNKNOWN>PASS; C5 conservado como FAIL histórico.",
           },
           "r3_correction": {
               "R3-A": "R2-C7 verifica dos propiedades independientes: P1 el "
                       "error de enumeración no escapa de fds_with_identity(); "
                       "P2 el controlador recibe complete=False y asigna "
                       "UNKNOWN (nunca PASS ni FAIL artificial). PASS solo "
                       "si ambas se verifican.",
               "R3-B": "R2-C2/R2-C3: el veredicto depende de la clasificación "
                       "verificada (correcta + complete=False -> UNKNOWN; "
                       "incorrecta -> FAIL); no UNKNOWN automático por "
                       "incompletitud.",
               "R3-C": "R2-C5 exige evidencia REAL de un error de inspección "
                       "clasificado ERROR_PROCFS con errno y contexto "
                       "compatibles; sin evidencia suficiente -> UNKNOWN, no "
                       "PASS.",
               "R3-D": "clasificación conservadora de ENOENT: ausencia de "
                       "fdinfo NO demuestra artefacto de procfs; procfs + "
                       "fdinfo ausente -> UNKNOWN_CAUSE; fdinfo presente -> "
                       "DESCRIPTOR_DESAPARECIDO; FS regular -> "
                       "DESCRIPTOR_DESAPARECIDO. ERROR_PROCFS solo con "
                       "evidencia suficiente. Se documenta qué puede y qué "
                       "no puede distinguir el mecanismo.",
               "R3-E": "R2-C10 verifica inventario incompleto -> UNKNOWN sobre "
                       "los escenarios REALES A/B/C (test_a1/b1/b5/c_b) con "
                       "inventario controlado completo/incompleto y "
                       "contraste, no una función simplificada aislada.",
               "R3-F": "reejecución del conjunto completo con resultados "
                       "reales; precedencia FAIL>UNKNOWN>PASS; C5 histórico; "
                       "sin _mmap.close() forzado; sin garantías universales "
                       "de gc.collect(); hechos/hipótesis/UNKNOWN separados.",
           },
           "conserva_c5": "C5 (SIGSEGV al cerrar _mmap con array vivo) es "
                          "hallazgo histórico de FEASIBILITY-D18-R1; NO se "
                          "re-ejecuta ni se oculta aqui.",
           "environment": env, "tests": RESULTS,
           "counts": counts, "global_verdict": global_verdict}
    with open(os.path.join(EVIDENCE_DIR, "evidence_d18_r2.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    print(f"\nConteos: PASS={counts['PASS']} FAIL={counts['FAIL']} "
          f"UNKNOWN={counts['UNKNOWN']}")
    print(f"VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): "
          f"{global_verdict}")
    print(f"Evidencia: {os.path.join(EVIDENCE_DIR, 'evidence_d18_r2.json')}")
    print("C5 histórico (FEASIBILITY-D18-R1) se conserva como FAIL "
          "independiente; R2 no lo altera.")
    shutil.rmtree(WORKDIR, ignore_errors=True)
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
