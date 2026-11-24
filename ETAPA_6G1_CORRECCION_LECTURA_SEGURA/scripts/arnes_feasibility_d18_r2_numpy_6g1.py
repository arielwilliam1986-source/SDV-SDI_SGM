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
    """Inventario de /proc/self/fd (R1-B).

    R1-B: los errores individuales NO se ignoran; determinan que el inventario
    es INCOMPLETO. matched solo es fiable cuando complete == True.
    """

    __slots__ = ("matched", "errors", "complete")

    def __init__(self, matched, errors, complete):
        self.matched = sorted(matched)    # fds con la identidad buscada
        self.errors = errors              # [{name, error}] por entrada fallida
        self.complete = complete          # ¿se pudo inventariar TODO?


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


def fds_with_identity(st, fd_dir="/proc/self/fd"):
    """Inventario de /proc/self/fd para la identidad de 'st' (R1-B).

    R1-B: los errores de stat (descriptor que desapareció durante el recorrido,
    inaccesible, error de procfs) NO se ignoran: se registran y fuerzan
    complete=False. Así, un inventario incompleto nunca respalda un PASS.
    """
    target = identity_of(st)
    matched, errors = [], []
    complete = True
    for name in os.listdir(fd_dir):
        try:
            s = os.stat(os.path.join(fd_dir, name))
        except OSError as e:
            # Descriptor que desapareció durante el recorrido, inaccesible o
            # error de procfs: se registra y marca el inventario como
            # incompleto (R1-B).
            errors.append({"name": name,
                           "error": f"{type(e).__name__}: {e}"})
            complete = False
            continue
        if identity_of(s) == target:
            try:
                matched.append(int(name))
            except ValueError:
                errors.append({"name": name, "error": "fd no entero"})
                complete = False
    return FdInventory(matched, errors, complete)


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
    print("CORRECCIÓN METODOLÓGICA R1 activa: count_maps()/parse_maps() "
          "distinguen COMPLETA/INCOMPLETA/ILEGIBLE; fds_with_identity() "
          "marca inventario INCOMPLETO y propaga UNKNOWN (R1-A/R1-B/R1-C).\n")

    tests = [test_a1, test_a2, test_a3, test_a4, test_a5, test_a6,
             test_b1, test_b2, test_b3, test_b4, test_b5, test_b6,
             test_c_a, test_c_b, test_c_c,
             test_d1, test_d2, test_d3, test_d4,
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
           "scope": "FEASIBILITY-D18-R2 + R1 (corrección metodológica del arnés)",
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
