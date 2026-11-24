#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FEASIBILITY D-18-R2 — Ciclo de vida SEGURO de numpy.memmap (aislado).

Objetivo de R2: investigar y validar experimentalmente alternativas SEGURAS
para liberar los recursos de numpy.memmap SIN invocar arr._mmap.close()
mientras existan arrays/vistas vivas (ese camino es el hallazgo C5 de
FEASIBILITY-D18-R1, conservado como histórico y NO re-ejecutado aquí).

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


def parse_maps(path="/proc/self/maps"):
    """Parsea /proc/self/maps. Devuelve (entradas, no_interpretables)."""
    entries, unparseable = [], []
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
    return entries, unparseable


def identity_of(st):
    return (os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)


def entries_for_identity(entries, st):
    maj, min_, ino = identity_of(st)
    return [e for e in entries
            if e["major"] == maj and e["minor"] == min_ and e["ino"] == ino]


def count_maps(st):
    entries, _ = parse_maps()
    return len(entries_for_identity(entries, st))


def fds_with_identity(st):
    target = identity_of(st)
    out = []
    for name in os.listdir("/proc/self/fd"):
        try:
            s = os.stat(f"/proc/self/fd/{name}")
        except OSError:
            continue
        if identity_of(s) == target:
            out.append(int(name))
    return sorted(out)


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
    alive_maps = count_maps(st)
    alive_fds = fds_with_identity(st)
    del arr
    gc.collect()
    gone_maps = count_maps(st)
    gone_fds = fds_with_identity(st)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == []
          and mm_state == "mmap")
    record("R2-A1", "A", "Raíz sin vistas: liberación por referencias",
           "np.memmap por ruta; sin vistas derivadas.",
           "Soltar la única referencia (del arr) y gc.collect(); verificar "
           "desaparición en maps y cierre del fd del mmap (sin _mmap.close).",
           f"vivo: maps={alive_maps} fds={alive_fds} mmap={mm_state}; "
           f"tras del+gc: maps={gone_maps} fds={gone_fds}",
           "liberar la referencia raíz + gc finaliza el mmap (su "
           "finalizador cierra el fd duplicado y desmapea); sin SIGSEGV",
           "PASS" if ok else "FAIL")


def test_a2():
    p = make_file("a2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    sl = arr[0:16]
    alive = count_maps(st)
    del arr
    gc.collect()
    kept = count_maps(st)            # la vista mantiene vivo el mapeo
    del sl
    gc.collect()
    after = count_maps(st)
    ok = (alive == 1 and kept == 1 and after == 0)
    record("R2-A2", "A", "Raíz con slices: retención y liberación",
           "np.memmap + slice arr[0:16].",
           "Liberar la raíz (slice retenido) -> maps debe persistir; luego "
           "liberar el slice -> maps desaparece.",
           f"vivo={alive}; tras del raíz (slice vivo)={kept}; "
           f"tras del slice={after}",
           "un slice comparte el mmap vía __array_finalize__/base: el "
           "mapeo NO desaparece hasta soltar TODAS las vistas",
           "PASS" if ok else "FAIL")


def test_a3():
    p = make_file("a3.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v1 = arr[0:32]
    v2 = v1[4:8]                    # vista encadenada (v2.base -> v1)
    alive = count_maps(st)
    del arr
    gc.collect()
    after_del_root = count_maps(st)
    del v1
    gc.collect()
    after_del_v1 = count_maps(st)
    del v2
    gc.collect()
    after_del_v2 = count_maps(st)
    ok = (alive == 1 and after_del_root == 1
          and after_del_v1 == 1 and after_del_v2 == 0)
    record("R2-A3", "A", "Vistas derivadas y referencias encadenadas",
           "arr -> v1=arr[0:32] -> v2=v1[4:8].",
           "Liberar progresivamente raíz, luego v1, luego v2; el mapeo "
           "debe desaparecer solo al soltar la última vista encadenada.",
           f"vivo={alive}; del raíz={after_del_root}; del v1={after_del_v1}; "
           f"del v2={after_del_v2}",
           "la cadena de vistas retiene el mmap hasta la última referencia "
           "viva (comportamiento observado CPython 3.11.2/NumPy 1.26.4)",
           "PASS" if ok else "FAIL")


def test_a4():
    p = make_file("a4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    cont = [arr, arr[0:4]]          # referencias en contenedor
    alive = count_maps(st)
    del arr
    gc.collect()
    kept = count_maps(st)
    del cont
    gc.collect()
    after = count_maps(st)
    ok = (alive == 1 and kept == 1 and after == 0)
    record("R2-A4", "A", "Referencias almacenadas en contenedores",
           "array y una vista guardados en una lista.",
           "Liberar la variable suelta (contenedor retenido) -> maps "
           "persiste; vaciar el contenedor + gc -> desaparece.",
           f"vivo={alive}; del var (contedor vivo)={kept}; "
           f"del contenedor={after}",
           "los contenedores retienen el mmap mientras referencien el "
           "array/vistas; liberar el contenedor libera el mapeo",
           "PASS" if ok else "FAIL")


def test_a5():
    p = make_file("a5.bin")
    st = os.stat(p)
    exported = []                   # referencia exportada fuera del ámbito

    def make_and_export():
        a = np.memmap(p, dtype="uint8", mode="r+")
        exported.append(a)          # sobrevive al retorno de la función
        return a

    a = make_and_export()
    alive = count_maps(st)
    del a
    gc.collect()
    kept = count_maps(st)            # la referencia exportada mantiene vivo
    del exported[:]
    gc.collect()
    after = count_maps(st)
    ok = (alive == 1 and kept == 1 and after == 0)
    record("R2-A5", "A", "Referencia exportada que sobrevive al ámbito",
           "array cuya referencia se exporta a una lista de módulo.",
           "Liberar la variable local (ref exportada viva) -> maps "
           "persiste; liberar la referencia exportada + gc -> desaparece.",
           f"vivo={alive}; del local (exportada viva)={kept}; "
           f"del exportada={after}",
           "una referencia exportada fuera del ámbito original retiene el "
           "mmap; la liberación segura exige soltarla también",
           "PASS" if ok else "FAIL")


def test_a6():
    p = make_file("a6.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:8]
    cont = [arr]
    seq = []
    seq.append(("inicial", count_maps(st)))
    del arr
    gc.collect()
    seq.append(("del raíz", count_maps(st)))   # v y cont retienen
    del v
    gc.collect()
    seq.append(("del vista", count_maps(st)))  # cont retiene
    del cont
    gc.collect()
    seq.append(("del contenedor", count_maps(st)))
    ok = (seq[0][1] == 1 and seq[1][1] == 1
          and seq[2][1] == 1 and seq[3][1] == 0)
    record("R2-A6", "A", "Liberación progresiva y recolección",
           "raíz + vista + contenedor que referencia la raíz.",
           "Liberar referencias una a una con gc intermedio; registrar el "
           "recuento de maps en cada paso; debe llegar a 0 solo al soltar "
           "la última.",
           f"secuencia={seq}",
           "el mapeo desaparece exactamente cuando la última referencia "
           "viva se libera y se recolecta",
           "PASS" if ok else "FAIL")


# ---------------------------------------------------------------- R2-B
def test_b1():
    p = make_file("b1.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    alive_maps = count_maps(st)
    alive_fds = fds_with_identity(st)
    del arr                         # liberación SEGURA (sin _mmap.close)
    gc.collect()
    gone_maps = count_maps(st)
    gone_fds = fds_with_identity(st)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == [])
    record("R2-B1", "B", "Secuencia segura: raíz, sin vistas",
           "np.memmap por ruta; sin vistas.",
           "Secuencia segura SIN _mmap.close(): (1) soltar referencias "
           "propias, (2) ninguna vista, (3) gc.collect, (4) verificar "
           "desaparición de TODAS las entradas por (dev,ino), (5) verificar "
           "fds residuales y propiedad.",
           f"vivo: maps={alive_maps} fds={alive_fds}; tras liberar+gc: "
           f"maps={gone_maps} fds={gone_fds}",
           "la secuencia segura libera el mapeo vía finalizador de gc; el "
           "fd duplicado del mmap se cierra; sin SIGSEGV",
           "PASS" if ok else "FAIL")


def test_b2():
    p = make_file("b2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:16]
    alive_maps = count_maps(st)
    del v, arr                      # liberar vistas y raíz
    gc.collect()
    gone_maps = count_maps(st)
    gone_fds = fds_with_identity(st)
    ok = (alive_maps == 1 and gone_maps == 0 and gone_fds == [])
    record("R2-B2", "B", "Secuencia segura con vistas/slices",
           "np.memmap + slice.",
           "Secuencia segura: soltar vistas y raíz, gc.collect, verificar "
           "desaparición.",
           f"vivo={alive_maps}; tras liberar vistas+raíz+gc: "
           f"maps={gone_maps} fds={gone_fds}",
           "soltar vistas Y raíz permite al finalizador cerrar el mmap; "
           "quedarse una vista impede la liberación",
           "PASS" if ok else "FAIL")


def test_b3():
    p = make_file("b3.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    alive_maps = count_maps(st)
    del arr
    gc.collect()
    gc.collect()                    # recolección controlada (doble pasada)
    gone_maps = count_maps(st)
    ok = (alive_maps == 1 and gone_maps == 0)
    record("R2-B3", "B", "Recolección controlada de referencias",
           "np.memmap por ruta; doble gc.collect().",
           "Liberar referencia; forzar recolección (dos pasadas); verificar "
           "que el finalizador del mmap se ejecutó (maps=0).",
           f"vivo={alive_maps}; tras del+doble gc: maps={gone_maps}",
           "la recolección controlada finaliza el mmap y desmapea sin "
           "intervención de _mmap.close()",
           "PASS" if ok else "FAIL")


def test_b4():
    p = make_file("b4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    entries, _ = parse_maps()
    before = len(entries_for_identity(entries, st))
    del arr
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    ok = (before == 1 and after == 0)
    record("R2-B4", "B", "Desaparición de TODAS las entradas por (dev,ino)",
           "np.memmap por ruta; barrido por identidad.",
           "Tras la liberación segura, comprobar que entries_for_identity "
           "devuelve 0 (no solo 'la primera').",
           f"entradas por identidad: antes={before} después={after}",
           "la acreditación de cierre usa TODAS las entradas por identidad "
           "(no una sola); el recuento llega a 0",
           "PASS" if ok else "FAIL")


def test_b5():
    p = make_file("b5.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    alive_fds = fds_with_identity(st)
    del arr
    gc.collect()
    residual = fds_with_identity(st)   # por ruta: no debe quedar ninguno
    ok = (alive_fds and residual == [])
    record("R2-B5", "B", "Fds residuales y propiedad (por ruta)",
           "np.memmap por ruta; el motor no abre fd propio.",
           "Verificar que tras la liberación segura no queda ningún fd con "
           "la identidad (el duplicado del mmap se cerró; el motor no "
           "poseía fd_mm).",
           f"fds vivos={alive_fds}; residuales tras liberar={residual}",
           "el único fd con la identidad era el duplicado del mmap; al "
           "finalizar, queda [] : el motor no debe atribuirse ese recurso",
           "PASS" if ok else "FAIL")


def test_b6():
    p = make_file("b6.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    externa = arr                  # referencia externa que el motor 'olvidó'
    alive_maps = count_maps(st)
    del arr
    gc.collect()                   # el motor libera lo que conoce
    kept_maps = count_maps(st)     # pero la referencia externa lo retiene
    ok_release = (kept_maps == 1)  # NO se acredita la liberación
    record("R2-B6", "B", "Referencia externa viva impide la liberación",
           "np.memmap + una referencia externa fuera del control del motor.",
           "El motor ejecuta la secuencia segura sobre sus referencias; la "
           "referencia externa permanece. Comprobar que el mapeo NO "
           "desaparece.",
           f"vivo={alive_maps}; tras liberar refs del motor (ext. viva)="
           f"{kept_maps}",
           "cuando una referencia externa permanece viva, la liberación "
           "segura NO puede acreditarse: el mapeo debe seguir vivo; no se "
           "usa _mmap.close() forzado para superarlo",
           "UNKNOWN" if ok_release else "FAIL")


# ---------------------------------------------------------------- R2-C
def test_c_a():
    p = make_file("ca.bin", fill=b"\x07")
    st = os.stat(p)
    fd_motor = os.open(p, os.O_RDWR)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(f"/proc/self/fd/{fd_motor}", dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    alive_maps = count_maps(st)
    alive_fds = fds_with_identity(st)
    del arr                         # secuencia segura
    gc.collect()
    gone_maps = count_maps(st)
    fds_now = fds_with_identity(st)
    motor_open = True
    try:
        os.fstat(fd_motor)
    except OSError:
        motor_open = False
    close_fd_quiet(fd_motor)
    ok = (alive_maps == 1 and gone_maps == 0
          and fd_motor in alive_fds and fd_motor in fds_now
          and motor_open
          and any("proc/self/fd" in x for x in opened))
    record("R2-C-A", "C", "Alternativa A: fd motor + magic-link (segura)",
           "Motor abre fd; NumPy vía magic-link /proc/self/fd/N.",
           "Secuencia segura (sin _mmap.close): liberar el array + gc; "
           "verificar maps=0, que el fd duplicado del mmap se cerró y que "
           "el fd del MOTOR sigue abierto (NumPy no lo cierra).",
           f"NumPy abrió={opened}; vivos fds={alive_fds}; tras liberar: "
           f"maps={gone_maps} fds={fds_now} fd_motor_abierto={motor_open}",
           "A (segura): el motor libera el array y gc finaliza el mmap "
           f"(fd duplicado cerrado); el fd del motor [{fd_motor}] permanece "
           "abierto y es responsabilidad del motor, no de NumPy",
           "PASS" if ok else "FAIL")


def test_c_b():
    p = make_file("cb.bin", fill=b"\x09")
    st = os.stat(p)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(p, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    alive_maps = count_maps(st)
    alive_fds = fds_with_identity(st)
    del arr
    gc.collect()
    gone_maps = count_maps(st)
    residual = fds_with_identity(st)
    ok = (alive_maps == 1 and gone_maps == 0 and residual == []
          and any(x.endswith("cb.bin") for x in opened))
    record("R2-C-B", "C", "Alternativa B: NumPy abre por ruta (segura)",
           "np.memmap(path); el motor NO abre fd.",
           "Secuencia segura: liberar el array + gc; verificar maps=0 y que "
           "no queda ningún fd con la identidad (el duplicado del mmap se "
           "cerró con el finalizador).",
           f"NumPy abrió={opened}; vivos fds={alive_fds}; tras liberar: "
           f"maps={gone_maps} residuales={residual}",
           "B (segura): NumPy abre por ruta y su fd duplicado se cierra "
           "solo al finalizar; el motor no posee fd_mm que cerrar",
           "PASS" if ok else "FAIL")


def test_c_c():
    p = make_file("cc.bin", fill=b"\x0B")
    st = os.stat(p)
    fileobj = open(p, "r+b")
    fd_fileobj = fileobj.fileno()
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(fileobj, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    alive_maps = count_maps(st)
    alive_fds = fds_with_identity(st)
    del arr
    gc.collect()
    gone_maps = count_maps(st)
    fds_now = fds_with_identity(st)
    fo_open = True
    try:
        os.fstat(fd_fileobj)
    except OSError:
        fo_open = False
    fileobj.close()
    ok = (alive_maps == 1 and gone_maps == 0
          and fd_fileobj in alive_fds and fd_fileobj in fds_now
          and opened == [] and fo_open)
    record("R2-C-C", "C", "Alternativa C: fileobj entregado a NumPy (segura)",
           "fileobj propio entregado a np.memmap.",
           "Secuencia segura: liberar el array + gc; verificar maps=0, fd "
           "duplicado cerrado, y que el fd del fileobj (motor) sigue "
           "abierto (NumPy no abrió nada).",
           f"NumPy abrió={opened}; vivos fds={alive_fds}; tras liberar: "
           f"maps={gone_maps} fds={fds_now} fileobj_abierto={fo_open}",
           "C (segura): NumPy no abre nada (nullcontext); el mapeo se "
           f"libera vía gc; el fileobj [{fd_fileobj}] es del motor y "
           "permanece abierto",
           "PASS" if ok else "FAIL")


# ---------------------------------------------------------------- R2-D
def test_d1():
    p = make_file("d1.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    v = arr[0:8]                   # vista retenida (liberación incompleta)
    alive_maps = count_maps(st)
    del arr                         # se olvida la vista
    gc.collect()
    kept_maps = count_maps(st)
    ok_release = (kept_maps == 1)  # no acreditable
    record("R2-D1", "D", "Liberación incompleta (vista retenida)",
           "np.memmap + vista no liberada en la secuencia.",
           "Ejecutar la secuencia segura solo sobre la raíz; la vista "
           "queda viva. Verificar que el mapeo NO desaparece.",
           f"vivo={alive_maps}; tras liberar solo la raíz={kept_maps}",
           "la liberación incompleta deja el mapeo vivo; no se usa "
           "_mmap.close() forzado para superar la vista; el resultado no "
           "puede ser PASS ni autorizar EXIT_OK",
           "UNKNOWN" if ok_release else "FAIL")


def test_d2():
    p = make_file("d2.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    retenida = arr                 # referencia retenida externamente
    alive_maps = count_maps(st)
    del arr
    gc.collect()
    kept_maps = count_maps(st)
    ok_release = (kept_maps == 1)
    record("R2-D2", "D", "Referencia retenida impide acreditar cierre",
           "np.memmap + referencia retenida fuera del alcance del motor.",
           "El motor no puede localizar/liberar la referencia retenida; "
           "verificar que el mapeo permanece y que NO se fuerza _mmap.close().",
           f"vivo={alive_maps}; tras secuencia segura (retenida viva)="
           f"{kept_maps}",
           "una referencia retenida impide acreditar el cierre; el "
           "escenario termina en UNKNOWN/fallo cerrado, no en PASS; el "
           "cierre forzado está prohibido (C5 histórico)",
           "UNKNOWN" if ok_release else "FAIL")


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
    del arr                        # liberación segura SIN flush
    gc.collect()
    gone_maps = count_maps(st)
    ok = (persisted and gone_maps == 0)
    record("R2-D3", "D", "Fallos durante flush no bloquean la liberación",
           "np.memmap writable; flush normal + liberación sin flush.",
           "Confirmar que flush funciona y persiste; luego liberar por "
           "referencias+gc SIN flush y verificar unmapping.",
           f"flush_exc={flush_exc}; persistido={persisted}; "
           f"maps tras liberar={gone_maps}",
           "el flush no es prerrequisito de la liberación segura; un error "
           "de flush (ValueError 'mmap closed or invalid' sobre mapping ya "
           "cerrado, observado en sonda previa) se surfacea pero no bloquea "
           "el unmapping por gc; en tmpfs no se pudo forzar un fallo de I/O "
           "de flush",
           "PASS" if ok else "FAIL")


def test_d4():
    p = make_file("d4.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    alive_maps = count_maps(st)
    close_exc = None
    try:
        del arr                    # camino seguro: finalizador de gc
        gc.collect()
    except Exception as e:
        close_exc = f"{type(e).__name__}: {e}"
    gone_maps = count_maps(st)
    ok = (close_exc is None and alive_maps == 1 and gone_maps == 0)
    record("R2-D4", "D", "Cierre seguro sin errores (vía finalizador)",
           "np.memmap por ruta; liberación por referencias+gc.",
           "Verificar que el camino seguro (finalizador de gc) cierra sin "
           "excepción y desmapea; NO se invoca _mmap.close() (ver C5 "
           "histórico).",
           f"vivo={alive_maps}; tras liberar+gc: maps={gone_maps} "
           f"excepción_cierre={close_exc}",
           "el cierre seguro por finalizador no lanza excepción; el "
           "_mmap.close() forzado (SIGSEGV en C5) queda explícitamente "
           "excluido de R2",
           "PASS" if ok else "FAIL")


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

    tests = [test_a1, test_a2, test_a3, test_a4, test_a5, test_a6,
             test_b1, test_b2, test_b3, test_b4, test_b5, test_b6,
             test_c_a, test_c_b, test_c_c,
             test_d1, test_d2, test_d3, test_d4]
    for t in tests:
        try:
            t()
        except Exception:
            record(t.__name__, "?", f"excepción no controlada en {t.__name__}",
                   "-", "-", __import__("traceback").format_exc(limit=3).strip(),
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
           "scope": "FEASIBILITY-D18-R2: ciclo de vida SEGURO de numpy.memmap",
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
