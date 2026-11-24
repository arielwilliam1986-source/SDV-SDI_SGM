#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FEASIBILITY D-18 — Validación empírica aislada de identidad y cierre
efectivo de mapeos mmap vía /proc/self/maps.

Alcance: D-18 (UNKNOWN en la adjudicación final). NO integra nada en el
motor Hardened; NO toca motores/, lectura_segura_6g1.py, plan v2.3,
diseño v5 ni la adjudicación final. Fixtures 100% sintéticos en un
directorio temporal aislado (/tmp). Sin audio real, sin Android/Termux,
sin DSP, sin EVO/MQR, sin FLOW-5..8, sin D-16.

Precedencia de veredictos (global): FAIL > UNKNOWN > PASS.
Evidencia JSON: /tmp/feas_d18_evidence/evidence_d18.json
"""

import builtins
import errno
import gc
import json
import mmap
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import textwrap
import traceback

import numpy as np

RESULTS = []
WORKDIR = None
EVIDENCE_DIR = "/tmp/feas_d18_evidence"


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
    """Parsea /proc/self/maps. Devuelve (entradas, no_interpretables).

    Formato de línea: inicio-fin permisos offset dev(in hex) inodo ruta?
    La ruta puede contener espacios (p. ej. ' (deleted)').
    """
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
    """TODAS las entradas cuyo (dev,ino) coincide con la identidad del
    archivo. Nunca por nombre de ruta."""
    maj, min_, ino = identity_of(st)
    return [e for e in entries
            if e["major"] == maj and e["minor"] == min_ and e["ino"] == ino]


def fds_with_identity(st):
    """Fds abiertos del proceso cuyo objeto tiene la identidad dada."""
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


def accredit_identity(entries, st, maps_available=True, unparseable=None):
    """Lógica de decisión de acreditación (D18-E4 / R1-D).

    - maps no disponible -> UNKNOWN (nunca PASS por defecto).
    - barrido con líneas no interpretables (integridad del barrido no
      asegurada) -> UNKNOWN.
    - barrido completo y hay entradas por identidad -> PASS.
    - barrido completo y NO hay entradas cuando el mapeo debería seguir
      vivo -> FAIL (falso negativo del mecanismo).

    `unparseable` es la lista de líneas que parse_maps() no pudo
    interpretar; si no está vacía, el barrido no puede considerarse
    íntegro y la acreditación es UNKNOWN (nunca PASS por omisión).
    """
    if not maps_available:
        return "UNKNOWN"
    if unparseable:
        return "UNKNOWN"
    return "PASS" if entries_for_identity(entries, st) else "FAIL"


class OpenRecorder:
    """Registra las rutas abiertas vía builtins.open (evidencia de qué
    abre NumPy internamente)."""

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


# ---------------------------------------------------------------- D18-A
def test_a1():
    p = make_file("a1.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        entries, unp = parse_maps()
        found = entries_for_identity(entries, st)
        ok = (len(found) == 1 and found[0]["ino"] == st.st_ino
              and found[0]["major"] == os.major(st.st_dev)
              and found[0]["minor"] == os.minor(st.st_dev))
        record("D18-A1", "A", "Identidad del mapeo (fstat vs maps)",
               "Archivo sintético de 16384 bytes; un mmap de 4096 bytes "
               "sobre fd propio (ACCESS_WRITE).",
               "fstat -> (dev,ino); parsear /proc/self/maps; buscar TODAS "
               "las entradas por (major,minor,ino) equivalentes a "
               "os.major()/os.minor(); no usar la ruta.",
               f"entradas por identidad: {len(found)}; "
               f"dev={found[0]['dev'] if found else None} "
               f"ino={found[0]['ino'] if found else None} "
               f"pathname={found[0]['pathname'] if found else None!r}; "
               f"no_interpretables={len(unp)}",
               f"st_dev={st.st_dev} major={os.major(st.st_dev)} "
               f"minor={os.minor(st.st_dev)} ino={st.st_ino}",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


def test_a2():
    p = make_file("a2.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m1 = mmap.mmap(fd, 4096, offset=0, access=mmap.ACCESS_WRITE)
    m2 = mmap.mmap(fd, 4096, offset=8192, access=mmap.ACCESS_WRITE)
    try:
        entries, _ = parse_maps()
        found = entries_for_identity(entries, st)
        offsets = sorted(int(e["offset"], 16) for e in found)
        ok = len(found) == 2 and offsets == [0, 8192]
        record("D18-A2", "A", "Múltiples mapeos del mismo archivo",
               "Dos mmaps del mismo archivo (offsets 0 y 8192, 4096 bytes "
               "cada uno).",
               "Buscar TODAS las entradas por identidad; verificar que no "
               "se considera sólo la primera.",
               f"entradas por identidad: {len(found)}; offsets={offsets}",
               "offsets en maps: 0x0 y 0x2000 (8192)",
               "PASS" if ok else "FAIL")
    finally:
        m1.close(); m2.close()
        close_fd_quiet(fd)


def test_a3():
    p1 = make_file("a3a.bin")
    p2 = make_file("a3b.bin")
    st1, st2 = os.stat(p1), os.stat(p2)
    fd1 = os.open(p1, os.O_RDWR)
    fd2 = os.open(p2, os.O_RDWR)
    m1 = mmap.mmap(fd1, 4096, access=mmap.ACCESS_WRITE)
    m2 = mmap.mmap(fd2, 4096, access=mmap.ACCESS_WRITE)
    try:
        entries, _ = parse_maps()
        f1 = entries_for_identity(entries, st1)
        f2 = entries_for_identity(entries, st2)
        ok = (len(f1) == 1 and len(f2) == 1
              and f1[0]["ino"] != f2[0]["ino"]
              and f1[0]["pathname"].endswith("a3a.bin")
              and f2[0]["pathname"].endswith("a3b.bin"))
        record("D18-A3", "A", "Dos archivos distintos, sin confusión",
               "Dos archivos sintéticos, un mmap de cada uno.",
               "Acreditar cada archivo por su identidad; verificar que "
               "ninguna entrada del otro se atribuye (sin falsos "
               "positivos cruzados).",
               f"f1={len(f1)} entrada(s) ino={f1[0]['ino'] if f1 else None}; "
               f"f2={len(f2)} entrada(s) ino={f2[0]['ino'] if f2 else None}",
               f"ino1={st1.st_ino} ino2={st2.st_ino}",
               "PASS" if ok else "FAIL")
    finally:
        m1.close(); m2.close()
        close_fd_quiet(fd1); close_fd_quiet(fd2)


def test_a4():
    p = make_file("a4 con espacios.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        entries, unp = parse_maps()
        anon = [e for e in entries if e["pathname"] == ""]
        bracket = [e for e in entries if e["pathname"].startswith("[")]
        found = entries_for_identity(entries, st)
        anon_attributed = [e for e in anon
                           if (e["major"], e["minor"], e["ino"])
                           == identity_of(st)]
        ok = (len(unp) == 0 and len(found) == 1
              and found[0]["pathname"].endswith("a4 con espacios.bin")
              and len(anon_attributed) == 0)
        record("D18-A4", "A", "Parser robusto: anónimas, [heap], espacios",
               "Archivo con espacios en el nombre; proceso con mapeos "
               "anónimos y [heap]/[stack] habituales.",
               "Parsear todo /proc/self/maps; contar anónimas y "
               "corcheteadas; verificar que ninguna entrada anónima se "
               "atribuye al archivo y que la ruta con espacios se parsea.",
               f"entradas={len(entries)} anónimas={len(anon)} "
               f"corcheteadas={len(bracket)} no_interpretables={len(unp)}; "
               f"anónimas atribuidas al archivo={len(anon_attributed)}; "
               f"pathname parseado={found[0]['pathname'] if found else None!r}",
               "las anónimas tienen dev 00:00 e ino 0 (excluidas por "
               "identidad, no por nombre)",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


def test_a5():
    p = make_file("a5.bin")
    st = os.stat(p)
    anon = mmap.mmap(-1, 4096,
                     flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                     prot=mmap.PROT_READ | mmap.PROT_WRITE)
    try:
        entries, _ = parse_maps()
        anon_entries = [e for e in entries
                        if e["dev"] == "00:00" and e["ino"] == 0]
        found = entries_for_identity(entries, st)
        ok = len(anon_entries) >= 1 and len(found) == 0
        record("D18-A5", "A", "Mapeo anónimo no atribuido a ningún archivo",
               "Un mmap anónimo (fileno=-1) vivo junto a un archivo real "
               "sin mapear.",
               "Verificar que la entrada anónima (00:00/0) existe y que "
               "la búsqueda por identidad del archivo NO la incluye.",
               f"entradas anónimas 00:00/0: {len(anon_entries)}; "
               f"atribuidas al archivo: {len(found)}",
               "riesgo de falso positivo por ino=0 descartado: la "
               "identidad exige (dev,ino) completo",
               "PASS" if ok else "FAIL")
    finally:
        anon.close()


def test_a6():
    p = make_file("a6.bin")
    fd = os.open(p, os.O_RDWR)
    try:
        s_fd = os.fstat(fd)
        s_path = os.stat(p)
        same = identity_of(s_fd) == identity_of(s_path)
        record("D18-A6", "A", "fstat(fd) == stat(path): base del método",
               "fd abierto sobre archivo sintético.",
               "Comparar identidad (dev,ino) vía fstat del fd y stat de "
               "la ruta.",
               f"fstat={identity_of(s_fd)} stat={identity_of(s_path)}",
               "la acreditación por identidad no depende de la ruta "
               "nominal",
               "PASS" if same else "FAIL")
    finally:
        close_fd_quiet(fd)


# ---------------------------------------------------------------- D18-B
def test_b1():
    p = make_file("b1_viejo.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        q = os.path.join(WORKDIR, "b1_nuevo.bin")
        os.rename(p, q)
        entries, _ = parse_maps()
        found = entries_for_identity(entries, st)
        ok = (len(found) == 1 and found[0]["pathname"].endswith("b1_nuevo.bin")
              and identity_of(os.stat(q)) == identity_of(st))
        record("D18-B1", "B", "Renombrado tras mmap: identidad acreditable",
               "Mmap creado; después rename del nombre del archivo.",
               "Buscar por identidad tras el rename; verificar pathname "
               "actualizado y que stat del nuevo nombre conserva la "
               "identidad.",
               f"entradas={len(found)} pathname="
               f"{found[0]['pathname'] if found else None!r}",
               "la identidad (dev,ino) sobrevive al rename; la ruta "
               "nominal cambió",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


def test_b2():
    p = make_file("b2.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    m[0] = 0x5A
    try:
        os.unlink(p)
        entries, _ = parse_maps()
        found = entries_for_identity(entries, st)
        try:
            os.stat(p)
            stat_err = "sin error (inesperado)"
        except OSError as e:
            stat_err = f"{type(e).__name__} errno={e.errno}"
        still_readable = (m[0] == 0x5A)
        ok = (len(found) == 1
              and found[0]["pathname"].endswith(" (deleted)")
              and still_readable)
        record("D18-B2", "B", "Eliminado tras mmap: entrada '(deleted)'",
               "Mmap creado y escrito (byte 0x5A); después unlink del "
               "nombre.",
               "Buscar por identidad; examinar la entrada '(deleted)'; "
               "verificar stat(path) y que el mapeo sigue legible.",
               f"entradas={len(found)} pathname="
               f"{found[0]['pathname'] if found else None!r}; "
               f"stat(path)={stat_err}; mapeo legible={still_readable}",
               "la desaparición del nombre NO significa desaparición del "
               "mapeo: la identidad sigue acreditable",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


def test_b3():
    p = make_file("b3_viejo.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        q = os.path.join(WORKDIR, "b3_nuevo.bin")
        os.rename(p, q)
        os.unlink(q)
        entries, _ = parse_maps()
        found = entries_for_identity(entries, st)
        ok = len(found) == 1 and found[0]["pathname"].endswith(" (deleted)")
        record("D18-B3", "B", "Renombrado + eliminado tras mmap",
               "Mmap creado; rename y después unlink.",
               "Buscar por identidad; verificar '(deleted)' e identidad "
               "acreditable.",
               f"entradas={len(found)} pathname="
               f"{found[0]['pathname'] if found else None!r}",
               "identidad acreditable pese a rename+unlink",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


# ---------------------------------------------------------------- D18-C
def test_c1():
    p = make_file("c1.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    entries, _ = parse_maps()
    before = len(entries_for_identity(entries, st))
    del m
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    close_fd_quiet(fd)
    ok = before == 1 and after == 0
    record("D18-C1", "C", "Liberación de referencias (del + gc)",
           "Un mmap vivo; se elimina la única referencia Python.",
           "Contar entradas por identidad antes; del m; gc.collect(); "
           "contar de nuevo. (No se acepta del/gc como prueba por sí "
           "solo: se verifica en maps.)",
           f"antes={before} después={after}",
           "la desaparición en maps es la evidencia de cierre efectivo, "
           "no la ausencia de excepción",
           "PASS" if ok else "FAIL")


def test_c2():
    p = make_file("c2.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    m[0] = 0x33
    m.flush()
    entries, _ = parse_maps()
    present = len(entries_for_identity(entries, st))
    usable = (m[0] == 0x33)
    m.close()
    close_fd_quiet(fd)
    ok = present == 1 and usable
    record("D18-C2", "C", "flush() solo NO cierra",
           "Mmap escrito y flusheado, sin close.",
           "flush(); verificar que la entrada en maps persiste y el "
           "objeto sigue usable.",
           f"entradas tras flush={present}; usable={usable}",
           "flush != cierre efectivo",
           "PASS" if ok else "FAIL")


def test_c3():
    p = make_file("c3.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    m.close()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    try:
        m[0]
        access = "sin excepción (inesperado)"
    except Exception as e:
        access = f"{type(e).__name__}: {e}"
    try:
        os.fstat(fd)
        fd_state = "fd SIGUE ABIERTO tras m.close() (mmap no lo cierra)"
        fd_open = True
    except OSError as e:
        fd_state = f"fd cerrado por mmap ({type(e).__name__} errno={e.errno})"
        fd_open = False
    closed_attr = m.closed
    close_fd_quiet(fd)
    ok = after == 0 and closed_attr and "ValueError" in access
    record("D18-C3", "C", "Cierre explícito del objeto mmap",
           "Mmap vivo sobre fd propio.",
           "close(); verificar desaparición en maps, acceso posterior y "
           "estado del fd (¿mmap cierra el fd que recibió?).",
           f"entradas tras close={after}; m.closed={closed_attr}; "
           f"acceso={access}; {fd_state}",
           "evidencia de cierre: maps + estado del objeto + fd",
           "PASS" if ok else "FAIL")


def test_c4():
    p = make_file("c4.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    view = memoryview(m)
    try:
        m.close()
        close_result = "close() SIN excepción con vista viva"
        blocked = False
    except BufferError as e:
        close_result = f"BufferError: {e}"
        blocked = True
    except Exception as e:
        close_result = f"{type(e).__name__}: {e}"
        blocked = False
    entries, _ = parse_maps()
    present_while_blocked = len(entries_for_identity(entries, st))
    view.release()
    m.close()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    close_fd_quiet(fd)
    ok = blocked and present_while_blocked == 1 and after == 0
    record("D18-C4", "C", "Referencias exportadas impiden cerrar",
           "memoryview viva sobre el mmap (exportación del buffer).",
           "Intentar close() con la vista viva; verificar que la entrada "
           "persiste; liberar la vista; cerrar; verificar desaparición.",
           f"resultado={close_result}; entradas con vista viva="
           f"{present_while_blocked}; tras release+close={after}",
           "el cierre efectivo exige liberar vistas/slices/arrays "
           "exportados antes",
           "PASS" if ok else "FAIL")


def test_c5():
    p = make_file("c5.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    entries, _ = parse_maps()
    before = len(entries_for_identity(entries, st))
    has_close = hasattr(arr, "close")
    close_exc = None
    try:
        arr._mmap.close()
    except Exception as e:
        close_exc = f"{type(e).__name__}: {e}"
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    # Escenario adversarial: acceso al array tras cerrar el mmap
    # subyacente. TRES ejecuciones independientes (R1-C); cada SIGSEGV
    # queda confinado a su subproceso. Se escribe un script auxiliar para
    # evitar problemas de quoting.
    probe = os.path.join(WORKDIR, "c5_probe.py")
    with open(probe, "w") as fh:
        fh.write(textwrap.dedent("""
            import sys, numpy as np
            arr = np.memmap(sys.argv[1], dtype="uint8", mode="r+")
            arr._mmap.close()
            print("BEFORE_ACCESS", flush=True)
            try:
                v = int(arr[0])
                print("ACCESS_OK", v)
            except Exception as e:
                print("ACCESS_EXC", type(e).__name__, str(e))
            print("DONE")
        """))
    runs = []
    for i in range(3):
        r = subprocess.run([sys.executable, probe, p],
                           capture_output=True, text=True, timeout=30)
        runs.append({"i": i, "rc": r.returncode,
                     "stdout": r.stdout.strip(),
                     "stderr": r.stderr.strip()[:200],
                     "segv": r.returncode < 0})
    segv_count = sum(1 for x in runs if x["segv"])
    del arr
    gc.collect()
    # Veredicto individual de C5 (R1-C): el FAIL se fundamenta en el
    # SIGSEGV reproducible. Si no todas las ejecuciones lo reproducen, se
    # refleja exactamente y se revisa el veredicto.
    if segv_count == 3:
        verdict = "FAIL"
        note = "SIGSEGV reproducible 3/3 (crash exacto en arr[0])"
    elif segv_count == 0:
        verdict = "UNKNOWN"
        note = ("SIGSEGV NO reproducido en 3/3: la afirmación de SEGV no "
                "queda demostrada en esta corrida")
    else:
        verdict = "FAIL"
        note = (f"SIGSEGV reproducido en {segv_count}/3 (no determinista "
                f"en este entorno): peligro confirmado pero intermitente")
    ok = (before == 1 and after == 0 and not has_close and close_exc is None)
    record("D18-C5", "C", "NumPy memmap: sin close(); _mmap.close()",
           "np.memmap por ruta (mode r+); array vivo; TRES ejecuciones "
           "independientes del escenario adversarial en subprocesos "
           "aislados.",
           "Verificar ausencia de close() en el array; cerrar el mmap "
           "subyacente con el array vivo; verificar desaparición en "
           "maps; acceso posterior en 3 subprocesos aislados (cada SEGV "
           "confinado).",
           f"hasattr close={has_close}; excepción al cerrar={close_exc}; "
           f"entradas antes={before} después={after}; "
           f"check_estructural={ok}; segv_count={segv_count}/3; runs={runs}",
           "sin BufferError con el array vivo (el ndarray no mantiene "
           "exportación activa); el acceso posterior al array tras "
           "_mmap.close() provoca SIGSEGV: cerrar el mmap subyacente con "
           "el array vivo NO es seguro; el cierre efectivo seguro es "
           "liberar el array (del+gc) y acreditar la desaparición en "
           "maps. " + note,
           verdict)


def test_c6():
    p = make_file("c6.bin")
    st = os.stat(p)
    arr = np.memmap(p, dtype="uint8", mode="r+")
    view = arr[0:16]
    del arr
    gc.collect()
    entries, _ = parse_maps()
    while_view = len(entries_for_identity(entries, st))
    del view
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    ok = while_view == 1 and after == 0
    record("D18-C6", "C", "Vista de NumPy mantiene vivo el mmap",
           "Vista arr[0:16] creada; se elimina la referencia al array "
           "padre.",
           "del padre + gc: la entrada debe persistir (la vista comparte "
           "_mmap vía __array_finalize__); del vista + gc: debe "
           "desaparecer.",
           f"con vista viva={while_view}; tras del vista={after}",
           "las referencias derivadas (vistas/slices) impiden el cierre "
           "efectivo aunque el padre se libere",
           "PASS" if ok else "FAIL")


def test_c7():
    p = make_file("c7.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    m[0:4] = b"\xDE\xAD\xBE\xEF"
    m.close()  # sin flush previo
    double_close_exc = None
    try:
        m.close()
    except Exception as e:
        double_close_exc = f"{type(e).__name__}: {e}"
    flush_after_exc = None
    try:
        m.flush()
    except Exception as e:
        flush_after_exc = f"{type(e).__name__} errno={getattr(e, 'errno', None)}"
    close_fd_quiet(fd)
    with open(p, "rb") as fh:
        data = fh.read(4)
    ok = (data == b"\xDE\xAD\xBE\xEF" and double_close_exc is None
          and flush_after_exc is not None)
    record("D18-C7", "C", "Orden de cierre y errores",
           "Escritura vía mmap; close sin flush; doble close; flush "
           "tras close.",
           "Verificar persistencia de datos por I/O normal, "
           "idempotencia del doble close y excepción del flush tras "
           "close.",
           f"datos leídos={data.hex()}; doble close excepción="
           f"{double_close_exc}; flush tras close={flush_after_exc}",
           "close implica visibilidad de los datos escritos (page "
           "cache); doble close idempotente; flush tras close falla",
           "PASS" if ok else "FAIL")


def test_c8():
    """R1-A: el descriptor duplicado que mmap.mmap crea internamente es un
    dup() de la misma descripción de archivo abierto, NO una reapertura
    independiente. Se demuestra empíricamente con os.lseek: mover el
    offset de uno de los fds debe reflejarse en el otro (offset
    compartido)."""
    p = make_file("c8.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        fds = fds_with_identity(st)
        extra = [x for x in fds if x != fd]
        if len(extra) != 1:
            record("D18-C8", "C",
                   "Descriptor duplicado de mmap.mmap comparte el offset (dup)",
                   "mmap.mmap sobre fd propio; identificar ambos fds por "
                   "(dev,ino).",
                   "Localizar el fd duplicado; registrar offset de ambos; "
                   "mover el offset de uno con os.lseek; verificar que el "
                   "otro refleja el mismo offset (descripción compartida).",
                   f"fds={fds}; fd original={fd}; duplicado={extra}",
                   "no se pudo aislar exactamente un único fd duplicado",
                   "FAIL")
            return
        dup_fd = extra[0]
        before_orig = os.lseek(fd, 0, os.SEEK_CUR)
        before_dup = os.lseek(dup_fd, 0, os.SEEK_CUR)
        os.lseek(fd, 1234, os.SEEK_SET)  # mover el original
        after_orig = os.lseek(fd, 0, os.SEEK_CUR)
        after_dup = os.lseek(dup_fd, 0, os.SEEK_CUR)
        shared = (before_orig == before_dup == 0
                  and after_orig == after_dup == 1234)
        record("D18-C8", "C",
               "Descriptor duplicado de mmap.mmap comparte el offset (dup)",
               "mmap.mmap sobre fd propio; identificar ambos fds por "
               "(dev,ino).",
               "Localizar el fd duplicado; registrar offset de ambos; "
               "mover el offset de uno con os.lseek; verificar que el "
               "otro refleja el mismo offset (descripción compartida).",
               f"fds={fds}; fd original={fd}; duplicado={dup_fd}; "
               f"offset antes orig={before_orig} dup={before_dup}; "
               f"tras lseek(1234) orig={after_orig} dup={after_dup}",
               "el fd duplicado de mmap.mmap es un dup() de la misma "
               "descripción de archivo abierto: comparte el offset del fd "
               "original (comprobado con os.lseek); por eso "
               "fds_with_identity cuenta dos fds con la misma identidad "
               "(ver D18-D-A/B/C y hallazgo §9.2 del informe)",
               "PASS" if shared else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


# ---------------------------------------------------------------- D18-D
def test_d_a():
    p = make_file("da.bin", fill=b"\x07")
    st = os.stat(p)
    fd_motor = os.open(p, os.O_RDWR)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(f"/proc/self/fd/{fd_motor}", dtype="uint8",
                        mode="r+")
    opened = [str(x) for x in rec.paths]
    entries, _ = parse_maps()
    found = entries_for_identity(entries, st)
    fds_now = fds_with_identity(st)
    arr[0] = 0x42
    via_fd = os.pread(fd_motor, 1, 0)[0]
    close_fd_quiet(fd_motor)  # el motor cierra SU fd
    fds_after_motor_close = fds_with_identity(st)
    still_readable = (int(arr[0]) == 0x42)
    del arr
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    fds_final = fds_with_identity(st)
    ok = (len(found) == 1 and len(fds_now) == 2 and fd_motor in fds_now
          and via_fd == 0x42 and len(fds_after_motor_close) == 1
          and fd_motor not in fds_after_motor_close
          and still_readable and after == 0 and fds_final == []
          and any("proc/self/fd" in x for x in opened))
    record("D18-D-A", "D", "Alternativa A: fd motor + /proc/self/fd/N",
           "fd propio del motor; NumPy abre vía magic-link "
           "/proc/self/fd/N.",
           "Registrar qué abre NumPy (hook de open); verificar identidad "
           "del mapeo == identidad del fd motor; fds con identidad; "
           "escritura visible vía fd; cerrar el fd motor (mapeo sigue "
           "válido); del array -> mapeo desaparece.",
           f"NumPy abrió: {opened}; fds con identidad tras crear={fds_now} "
           f"(fd motor={fd_motor} + duplicado del mmap); byte vía "
           f"fd={via_fd:#x}; tras cerrar fd motor, fds="
           f"{fds_after_motor_close}, arr legible={still_readable}; "
           f"entradas tras del array={after}; fds finales={fds_final}",
           "A: el motor abre/posee/cierra su fd; NumPy abre vía "
           "magic-link y cierra SU fd (with); mmap.mmap() duplica el fd "
           "internamente (offset compartido, verificado): el objeto "
           "mmap posee un fd duplicado adicional que se cierra al "
           "cerrar el mmap; el mapeo sobrevive al cierre del fd del "
           "motor; el motor NO posee fd_mm de NumPy",
           "PASS" if ok else "FAIL")


def test_d_b():
    p = make_file("db.bin", fill=b"\x09")
    st = os.stat(p)
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(p, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    fds_now = fds_with_identity(st)
    entries, _ = parse_maps()
    found = entries_for_identity(entries, st)
    del arr
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    fds_final = fds_with_identity(st)
    ok = (len(found) == 1 and len(fds_now) == 1 and after == 0
          and fds_final == []
          and any(x.endswith("db.bin") for x in opened))
    record("D18-D-B", "D", "Alternativa B: NumPy abre por ruta",
           "np.memmap(path); el motor NO abre ningún fd.",
           "Registrar qué abre NumPy; verificar 0 fds con identidad "
           "(el motor no posee fd_mm); identidad acreditable en maps; "
           "del+gc elimina el mapeo.",
           f"NumPy abrió: {opened}; fds con identidad={fds_now} "
           f"(duplicado del mmap); entradas={len(found)}; tras "
           f"del+gc={after}; fds finales={fds_final}",
           "B: NumPy abre por ruta y cierra su fd (with); mmap.mmap() "
           "duplica el fd: existe UN fd con la identidad, poseído por "
           "el objeto mmap (no por el motor); el motor NO tiene fd_mm "
           "que cerrar directamente; no atribuir al motor un recurso "
           "que no posee; el único cierre seguro es liberar el array "
           "(del+gc) y acreditarlo en maps (cerrar _mmap con el array "
           "vivo = SIGSEGV, ver D18-C5)",
           "PASS" if ok else "FAIL")


def test_d_c():
    p = make_file("dc.bin", fill=b"\x0B")
    st = os.stat(p)
    fileobj = open(p, "r+b")
    fd_fileobj = fileobj.fileno()
    rec = OpenRecorder()
    with rec:
        arr = np.memmap(fileobj, dtype="uint8", mode="r+")
    opened = [str(x) for x in rec.paths]
    fds_now = fds_with_identity(st)
    entries, _ = parse_maps()
    found = entries_for_identity(entries, st)
    fileobj.close()  # el motor cierra SU fileobj
    still_readable = (int(arr[0]) == 0x0B)
    del arr
    gc.collect()
    entries, _ = parse_maps()
    after = len(entries_for_identity(entries, st))
    fds_final = fds_with_identity(st)
    ok = (len(found) == 1 and len(fds_now) == 2 and fd_fileobj in fds_now
          and opened == [] and still_readable and after == 0
          and fds_final == [])
    record("D18-D-C", "D", "Alternativa C: fileobj entregado a NumPy",
           "fileobj propio (open r+b) entregado a np.memmap.",
           "Verificar que NumPy NO abre nada (nullcontext); fd del "
           "fileobj permanece; cerrar el fileobj no invalida el mapeo; "
           "del array elimina el mapeo.",
           f"NumPy abrió: {opened}; fds con identidad={fds_now} "
           f"(fd fileobj={fd_fileobj} + duplicado del mmap); tras "
           f"cerrar fileobj, arr legible={still_readable}; entradas "
           f"tras del={after}; fds finales={fds_final}",
           "C: el motor abre/posee/cierra el fileobj; NumPy no abre ni "
           "cierra nada (nullcontext); mmap.mmap() duplica el fd: el "
           "objeto mmap posee un duplicado adicional que se cierra al "
           "cerrar el mmap; el mapeo sobrevive al cierre del fileobj; "
           "el motor SÍ posee fd_mm (vía fileobj)",
           "PASS" if ok else "FAIL")


# ---------------------------------------------------------------- D18-E
def test_e1():
    fake = os.path.join(WORKDIR, "no_existe", "maps")
    try:
        parse_maps(fake)
        obs = "sin excepción (inesperado)"
        exc = None
    except OSError as e:
        obs = f"{type(e).__name__} errno={e.errno}"
        exc = f"{type(e).__name__} errno={e.errno}"
    verdict = accredit_identity([], None, maps_available=False)
    record("D18-E1", "E", "maps inexistente (SIMULACIÓN controlada)",
           "Ruta de maps inexistente (no es una ausencia real de "
           "procfs: /proc no puede desmontarse en este entorno).",
           "Intentar parsear; verificar que la acreditación de "
           "identidad resulta UNKNOWN (nunca PASS por defecto).",
           f"parse_maps -> {obs}; acreditación={verdict}",
           "SIMULACIÓN: distingue de una ausencia real; el resultado "
           "de identidad no acreditable es UNKNOWN",
           "UNKNOWN", exception=exc)


def test_e2():
    p = os.path.join(WORKDIR, "maps_ilegible")
    with open(p, "w") as fh:
        fh.write("00400000-00401000 rw-p 00000000 00:00 0\n")
    os.chmod(p, 0o000)
    try:
        try:
            with open(p, "r") as fh:
                fh.read()
            obs = "lectura permitida (inesperado)"
            exc = None
        except OSError as e:
            obs = f"{type(e).__name__} errno={e.errno}"
            exc = f"{type(e).__name__} errno={e.errno}"
        verdict = accredit_identity([], None, maps_available=False)
        record("D18-E2", "E", "maps ilegible (SIMULACIÓN controlada)",
               "Archivo con modo 0000 (euid no-root) como sustituto de "
               "un maps ilegible.",
               "Intentar leer; verificar acreditación UNKNOWN.",
               f"lectura -> {obs}; acreditación={verdict}",
               "SIMULACIÓN de EACCES; ausencia real de procfs no "
               "reproducida",
               "UNKNOWN", exception=exc)
    finally:
        os.chmod(p, 0o644)


def test_e3():
    p = os.path.join(WORKDIR, "maps_basura")
    with open(p, "w") as fh:
        fh.write("\n")
        fh.write("esto no es una línea de maps\n")
        fh.write("zz:zz nohex\n")
        fh.write("00400000-00401000 rw-p 00000000 08:01 12345 /ruta/con espacios/x\n")
    entries, unp = parse_maps(p)
    ok = len(unp) == 3 and len(entries) == 1
    record("D18-E3", "E", "Contenido malformado (SIMULACIÓN controlada)",
           "Archivo con líneas basura, dev no-hex y una línea válida "
           "con espacios en la ruta.",
           "Parsear; verificar que el parser no rompe y reporta las "
           "líneas no interpretables.",
           f"entradas={len(entries)} no_interpretables={len(unp)} "
           f"líneas={sorted(u['line'] for u in unp)}",
           "el parser es robusto; la acreditación desde contenido "
           "basura sería UNKNOWN (no PASS)",
           "PASS" if ok else "FAIL")


def test_e4():
    p = make_file("e4.bin")
    st = os.stat(p)
    fd = os.open(p, os.O_RDWR)
    m = mmap.mmap(fd, 4096, access=mmap.ACCESS_WRITE)
    try:
        entries, unp = parse_maps()
        v_present = accredit_identity(entries, st, maps_available=True,
                                      unparseable=unp)
        v_absent = accredit_identity(entries, st, maps_available=False)
        v_missing = accredit_identity([], st, maps_available=True)
        ok = (v_present == "PASS" and v_absent == "UNKNOWN"
              and v_missing == "FAIL")
        record("D18-E4", "E", "Lógica de decisión de acreditación",
               "Mmap vivo; función de decisión pura.",
               "maps disponible + entradas -> PASS; maps no disponible "
               "-> UNKNOWN; maps disponible sin entradas (falso "
               "negativo) -> FAIL.",
               f"presente={v_present} no_disponible={v_absent} "
               f"ausente={v_missing}",
               "la evidencia del objeto mmap (vivo) se distingue de la "
               "evidencia procfs (ausente): sin procfs no hay PASS",
               "PASS" if ok else "FAIL")
    finally:
        m.close()
        close_fd_quiet(fd)


def test_e5():
    try:
        with open("/proc/1/maps", "r") as fh:
            data = fh.read()
        obs = f"legible, {len(data)} bytes, {data.count(chr(10))} líneas"
        exc = None
        ok = len(data) > 0
    except OSError as e:
        obs = f"{type(e).__name__} errno={e.errno}"
        exc = f"{type(e).__name__} errno={e.errno}"
        ok = True  # observación definitiva obtenida (denegado)
    record("D18-E5", "E", "Legibilidad de /proc/1/maps (observación real)",
           "Proceso PID 1 del entorno (mismo usuario).",
           "Intentar leer /proc/1/maps y registrar el resultado.",
           obs,
           "observación real del entorno, no simulación",
           "PASS" if ok else "FAIL", exception=exc)


def test_e6():
    mounted = os.path.isdir("/proc")
    readable = False
    err = None
    try:
        with open("/proc/self/maps", "r") as fh:
            readable = len(fh.read()) > 0
    except OSError as e:
        err = f"{type(e).__name__} errno={e.errno}"
    ok = mounted and readable
    record("D18-E6", "E", "/proc montado y maps legible (observación real)",
           "Entorno de ejecución del arnés.",
           "Verificar /proc y legibilidad de /proc/self/maps.",
           f"/proc existe={mounted}; maps legible={readable}; error={err}",
           "observación real del entorno",
           "PASS" if ok else "FAIL", exception=err)


def test_e7():
    """R1-D: combina una entrada válida coincidente con líneas no
    interpretables. La función de acreditación NO debe otorgar PASS a un
    barrido incompleto: la integridad del barrido no está asegurada."""
    p = make_file("e7.bin")
    st = os.stat(p)
    maj, min_ = os.major(st.st_dev), os.minor(st.st_dev)
    dev_hex = f"{maj:02x}:{min_:02x}"
    fake = os.path.join(WORKDIR, "maps_e7")
    with open(fake, "w") as fh:
        fh.write("\n")  # línea vacía
        fh.write("esto no es una línea de maps\n")
        fh.write(f"7f0000000000-7f0000001000 rw-p 00000000 {dev_hex} "
                 f"{st.st_ino} /ruta/real/e7.bin\n")
        fh.write("zz:zz nohex\n")
    entries, unp = parse_maps(fake)
    verdict = accredit_identity(entries, st, maps_available=True,
                                unparseable=unp)
    ok = (len(entries) == 1 and len(unp) >= 1 and verdict == "UNKNOWN")
    record("D18-E7", "E",
           "Barrido incompleto (entrada válida + no interpretables) ⇒ UNKNOWN",
           "Archivo maps sintético con UNA entrada válida coincidente y "
           "varias líneas no interpretables.",
           "parsear; acreditar identidad con el listado de no "
           "interpretables; verificar que NO se otorga PASS a un barrido "
           "incompleto.",
           f"entradas válidas={len(entries)} no_interpretables="
           f"{len(unp)} líneas={sorted(u['line'] for u in unp)}; "
           f"acreditación={verdict}",
           "una entrada coincidente no basta si el barrido tiene líneas "
           "no interpretables: la integridad del barrido no está "
           "asegurada ⇒ UNKNOWN (no PASS por omisión)",
           "PASS" if ok else "FAIL")


# ---------------------------------------------------------------- main
def main():
    global WORKDIR
    WORKDIR = tempfile.mkdtemp(prefix="feas_d18_")
    env = {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "kernel": f"{os.uname().sysname} {os.uname().release} "
                  f"{os.uname().machine}",
        "platform": platform.platform(),
        "euid": os.geteuid(),
        "cwd": os.getcwd(),
        "workdir": WORKDIR,
        "tmp_fs": os.statvfs(WORKDIR),
    }
    env["tmp_fs"] = {
        "f_bsize": env["tmp_fs"].f_bsize,
        "f_namemax": env["tmp_fs"].f_namemax,
    }
    print(f"Entorno: Python {env['python']} | NumPy {env['numpy']} | "
          f"{env['kernel']} | euid {env['euid']}")
    print(f"Workdir aislado: {WORKDIR}\n")

    tests = [test_a1, test_a2, test_a3, test_a4, test_a5, test_a6,
             test_b1, test_b2, test_b3,
             test_c1, test_c2, test_c3, test_c4, test_c5, test_c6, test_c7,
             test_c8,
             test_d_a, test_d_b, test_d_c,
             test_e1, test_e2, test_e3, test_e4, test_e5, test_e6,
             test_e7]
    for t in tests:
        try:
            t()
        except Exception:
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
    out = {"harness": "arnes_feasibility_d18_mmap_6g1.py",
           "environment": env, "tests": RESULTS,
           "counts": counts, "global_verdict": global_verdict}
    with open(os.path.join(EVIDENCE_DIR, "evidence_d18.json"), "w") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)

    print(f"\nConteos: PASS={counts['PASS']} FAIL={counts['FAIL']} "
          f"UNKNOWN={counts['UNKNOWN']}")
    print(f"VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): "
          f"{global_verdict}")
    print(f"Evidencia: {os.path.join(EVIDENCE_DIR, 'evidence_d18.json')}")
    shutil.rmtree(WORKDIR, ignore_errors=True)
    return 0 if counts["FAIL"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
