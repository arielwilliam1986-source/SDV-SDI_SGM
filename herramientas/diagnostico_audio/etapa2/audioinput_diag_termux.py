#!/usr/bin/env python3
"""audioinput_diag_termux.py — Diagnostico AudioInput ETAPA 2 (v0.2.1).

Verifica la alternativa A: SoundFile(fd, closefd=False) + os.pread(fd, n, offset).

PROPIEDADES DEL INSTRUMENTO (v0.2.1 — correcciones finales C1-C7):
  - Script Python independiente. No importa ni depende de motores SDV/SDI.
  - No importa modulos del proyecto.
  - No modifica archivos originales ni datos del usuario.
  - Crea exclusivamente fixtures sinteticos propios.
  - No realiza limpieza automatica (los fixtures y el informe quedan en disco).
  - No utiliza permisos root.
  - No instala paquetes ni modifica la configuracion de Termux.
  - No usa /proc/self/fd como mecanismo de apertura.
  - No usa closefd=True en pruebas de apertura directa.
  - No introduce fallbacks por ruta.
  - No utiliza FLAC (prioridad: validar descriptor + lectura en WAV).

  - C1: Recorrido anclado por descriptores de directorio (dir_fd + O_DIRECTORY
    + O_NOFOLLOW) para crear el directorio de ejecucion y los fixtures cuando
    el entorno lo permita. Si el recorrido anclado no es viable, falla de
    forma conservadora con NOT_EXECUTED o ERROR. No usa Path.resolve() para
    detectar symlinks (resolve los resuelve antes de inspeccionarlos). No
    asume que un directorio padre existente es seguro: comprueba permisos
    y propiedad. validate_environments_distinct() no interpreta un error de
    stat como prueba de que los entornos son distintos. Sin limpieza
    automatica, sin eliminacion de archivos.
  - C2: T14 registra comprobaciones restantes como "no realizadas" si una
    falla impide continuar. No declara PASS si falta cualquier comprobacion.
    Los cierres de recursos se intentan incluso ante retornos anticipados.
  - C3: sha256_pread_v2 diferencia lectura corta, EOF prematuro y error de
    sistema. ZERO_SIZE documentado como caso de archivo vacio legitimo.
    SIZE_CHANGED no se presenta como deteccion completa de modificaciones
    concurrentes (limitacion explicita: cambios de contenido sin cambio
    de tamano pasan inadvertidos).
  - C4: eliminados los except Exception: pass que silencian fallos de cierre.
    Los errores de cierre de SoundFile y de descriptores se registran y
    propagan al resultado. Si un cierre falla, la prueba no permanece en
    PASS. Errores de cierre durante KeyboardInterrupt se conservan cuando
    es posible. No se intenta cerrar dos veces un descriptor de estado
    incierto.
  - C5: excepciones fatales e interrupciones nunca terminan con codigo 0.
    Si no se puede escribir el informe, el codigo tampoco es 0. Las pruebas
    no ejecutadas quedan como NOT_EXECUTED sin inventar resultados.
  - C7: escritura completa del informe con manejo de escrituras parciales
    hasta completar todos los bytes. Si write devuelve 0 antes de completar,
    se registra error. No sobrescribe informe preexistente.

CLASIFICACION DE RESULTADOS:
  PASS          La verificacion se ejecuto y tuvo exito completo.
  FAIL          La verificacion se ejecuto y fallo de manera esperada/anticipada.
  NOT_EXECUTED  La verificacion no se ejecuto por una condicion ambiental
                (falta de permisos, dependencia ausente, almacenamiento no
                disponible, conflicto de directorios, mecanismo no soportado).
  ERROR         La verificacion no pudo completarse por una excepcion no
                anticipada o por interrupcion. Se documenta el traceback.

USO:
    python3 audioinput_diag_termux.py
    python3 audioinput_diag_termux.py --shared /sdcard/audioinput_diag
    python3 audioinput_diag_termux.py --shared /storage/emulated/0/audioinput_diag --output informe.json

SALIDA:
    - Directorio de ejecucion por ejecucion:
      $HOME/.audioinput_diag_etapa2/run-<UTC>-<PID>-<rnd>/ (entorno privado).
      <shared>/run-<UTC>-<PID>-<rnd>/ (entorno compartido, si se especifica).
    - Informe JSON en $HOME/.audioinput_diag_etapa2/report-<UTC>-<PID>-<rnd>.json.
    - Fixtures WAV dentro del directorio de ejecucion correspondiente.
    - Salida legible por stdout con progreso y resumen.
    - Codigo de salida: 0 si todo PASS, 1 si hay FAIL/ERROR, 2 si no se pudo iniciar.
"""

import os
import sys
import errno
import hashlib
import platform
import json
import time
import traceback
import argparse
import struct
import stat
from pathlib import Path

SCRIPT_VERSION = "0.2.11"
SCRIPT_NAME = "audioinput_diag_termux.py"


# ----------------------------------------------------------------------------
# Importes diferidos de dependencias opcionales
# ----------------------------------------------------------------------------

def _import_dependencies():
    """Importa numpy y soundfile. Retorna (np, sf, errors_dict)."""
    errors = {}
    try:
        import numpy as np
    except ImportError as exc:
        np = None
        errors['numpy'] = "ImportError: " + str(exc)
    try:
        import soundfile as sf
    except ImportError as exc:
        sf = None
        errors['soundfile'] = "ImportError: " + str(exc)
    return np, sf, errors


# ----------------------------------------------------------------------------
# Clasificacion de resultados
# ----------------------------------------------------------------------------

class Result:
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EXECUTED = "NOT_EXECUTED"
    ERROR = "ERROR"


# ----------------------------------------------------------------------------
# Constantes de generacion de fixtures
# ----------------------------------------------------------------------------

SAMPLE_RATE = 44100
DURATION_FRAMES = 22050  # 0.5 segundos
CHANNELS = 2

FIXTURE_SPECS = [
    ("pcm16",   "PCM_16"),
    ("pcm24",   "PCM_24"),
    ("pcm32",   "PCM_32"),
    ("float32", "FLOAT"),
]


# ----------------------------------------------------------------------------
# C1: helpers de proteccion contra sobrescritura (v0.2.1)
# ----------------------------------------------------------------------------
# CORRECCION C1.1: NO usar Path.resolve() para detectar symlinks, porque
# resolve() resuelve los enlaces antes de inspeccionarlos. En su lugar, se
# recorre el path componente por componente con os.lstat sobre la ruta
# literal (sin resolver).
# CORRECCION C1.2: No afirmar que lstat + operacion posterior elimina TOCTOU.
#   La proteccion TOCTOU real requiere recorrido anclado por descriptores
#   (dir_fd + O_NOFOLLOW + O_PATH), implementado en safe_open_dir_anchored().
# CORRECCION C1.3: Recorrido anclado por dir_fd cuando el entorno lo permita.
#   Si no es viable, fallar conservadoramente.

def make_run_id():
    """Genera un identificador unico por ejecucion.

    Formato: <UTC-YYYYmmddTHHMMSS>Z-<PID>-<8hex-random>
    """
    utc = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    pid = os.getpid()
    rnd = os.urandom(4).hex()
    return "{0}-pid{1}-{2}".format(utc, pid, rnd)


def check_no_symlink_in_path(path):
    """Verifica que ningun componente de `path` sea un symlink.

    CORRECCION C1.1: NO usa Path.resolve(). Recorre el path literal componente
    por componente con os.lstat.

    ADVERTENCIA: esta funcion NO elimina carreras TOCTOU. Solo detecta symlinks
    en el instante de la comprobacion. Una carrera TOCTOU entre esta comprobacion
    y una operacion posterior sigue siendo posible. Para operaciones criticas,
    usar recorrido anclado por descriptores (safe_open_dir_anchored()).

    Retorna True si no hay symlinks en el path literal.
    Lanza OSError(ELOOP) si encuentra un symlink.
    Lanza OSError si lstat falla por otra razon distinta de FileNotFoundError.
    """
    # Recorrer el path literal (sin resolver symlinks)
    p = Path(path)
    parts = list(p.parts)
    if not parts:
        return True
    # En POSIX, parts[0] es la raiz '/' o un componente relativo
    # Si parts[0] es '/', empezamos ahi; si es relativo, no hay verificacion
    # previa del directorio actual (limitacion documentada).
    if parts[0] == os.sep:
        cumulative = Path(os.sep)
        start_idx = 1
    else:
        # Path relativo: la verificacion empieza en el primer componente.
        # El directorio actual (cwd) no se verifica aqui; el llamador debe
        # usar un path absoluto o verificar el cwd por separado.
        cumulative = Path(parts[0])
        start_idx = 1
    for part in parts[start_idx:]:
        cumulative = cumulative / part
        try:
            st = os.lstat(str(cumulative))
        except FileNotFoundError:
            # Componente no existe todavia (esperable en rutas que se van a crear)
            continue
        except OSError as exc:
            raise OSError(exc.errno,
                          "lstat fallo en {0}: {1}".format(cumulative, os.strerror(exc.errno)))
        if stat.S_ISLNK(st.st_mode):
            raise OSError(errno.ELOOP,
                          "symlink detectado en {0}: rechazado por politica C1".format(cumulative))
    return True


def check_dir_is_safe(dir_path, expected_uid=None, expected_mode_high_bits=0o700):
    """Comprueba que un directorio existente es seguro.

    CORRECCION C1.6: No asumir que un directorio existente es privado y seguro.
    Verifica:
    - El path existe y es un directorio (no symlink, no archivo regular).
    - El modo tiene los permisos esperados (high bits: 0700 o 0755).
    - Si expected_uid se especifica, el propietario coincide.

    Retorna (ok, msg).
    """
    try:
        st = os.lstat(str(dir_path))
    except FileNotFoundError:
        return False, "directorio no existe: {0}".format(dir_path)
    except OSError as exc:
        return False, "lstat errno={0}: {1}".format(exc.errno, os.strerror(exc.errno))

    if stat.S_ISLNK(st.st_mode):
        return False, "directorio es symlink: {0}".format(dir_path)
    if not stat.S_ISDIR(st.st_mode):
        return False, "path no es directorio: {0}".format(dir_path)

    # Verificar permisos: solo el propietario debe tener acceso (mode 0700 o 0755)
    perm_bits = stat.S_IMODE(st.st_mode)
    # Si el grupo u otros tienen permisos de escritura, no es seguro
    if perm_bits & 0o022:
        return False, "directorio con permisos de escritura para grupo/otros: mode={0:o}".format(perm_bits)

    # Verificar propietario si se especifica
    if expected_uid is not None and st.st_uid != expected_uid:
        return False, "directorio no pertenece al uid esperado: actual={0} esperado={1}".format(
            st.st_uid, expected_uid)

    return True, "mode={0:o} uid={1}".format(perm_bits, st.st_uid)


def safe_open_dir_anchored(abs_path):
    """Recorrido anclado por descriptores para abrir un directorio de forma segura.

    CORRECCION C1.3: implementa recorrido anclado por dir_fd + O_DIRECTORY +
    O_NOFOLLOW. Esto elimina la carrera TOCTOU entre comprobacion y apertura
    porque cada componente se abre por descriptor relativo al padre.

    Estrategia:
    1. Empezar desde AT_FDCWD o desde el primer componente absoluto que exista.
    2. Para cada componente intermedio, abrir con O_PATH|O_NOFOLLOW|O_DIRECTORY
       via os.open(relativo a dir_fd_padre).
    3. Cerrar el descriptor del padre y avanzar.
    4. El descriptor final es el del directorio objetivo.

    Retorna (fd_dir, msg) donde fd_dir es el descriptor del directorio final,
    o (-1, msg) si no se pudo abrir de forma anclada.

    Limitaciones:
    - Requiere O_PATH disponible (Linux 2.6.39+). En Android/Termux deberia
      estar disponible, pero si no lo esta, retorna -1.
    - Solo funciona para paths absolutos. Para paths relativos, usar AT_FDCWD.
    """
    if not hasattr(os, 'O_PATH'):
        return -1, "O_PATH no disponible en este entorno"
    if not hasattr(os, 'O_DIRECTORY'):
        return -1, "O_DIRECTORY no disponible en este entorno"

    p = Path(abs_path)
    parts = list(p.parts)
    if not parts or parts[0] != os.sep:
        return -1, "path no absoluto: {0}".format(abs_path)

    # Empezar desde AT_FDCWD y abrir '/' relativo? No es posible en POSIX puro.
    # Estrategia: abrir '/' primero, luego descendemos.
    try:
        fd = os.open(os.sep, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        return -1, "no se pudo abrir raiz '/': errno={0}".format(exc.errno)

    chain = [fd]
    try:
        for part in parts[1:]:  # parts[0] == '/', partes restantes
            if not part:
                continue
            # Abrir el siguiente componente relativo al fd actual
            try:
                fd_next = os.open(part, os.O_PATH | os.O_NOFOLLOW | os.O_DIRECTORY, dir_fd=fd)
            except OSError as exc:
                # Si es el ultimo componente y no existe, puede que el llamador
                # quiera crearlo; dejamos que el llamador lo maneje.
                if exc.errno == errno.ENOENT:
                    return -1, "componente no existe: {0}".format(part)
                return -1, "fallo abrir {0}: errno={1} ({2})".format(
                    part, exc.errno, os.strerror(exc.errno))
            chain.append(fd_next)
            # Cerrar el descriptor anterior y avanzar.
            # C4 (v0.2.4): no se silencia el error de cierre.
            _close_fd_tracked(fd, 'anchored_chain_parent')
            fd = fd_next
        return fd, "anchored chain length={0}".format(len(chain))
    except Exception as exc:
        # Cerrar todos los descriptores abiertos en caso de error.
        # C4 (v0.2.4): los errores de cierre se conservan, no se silencian.
        for open_fd in reversed(chain):
            _close_fd_tracked(open_fd, 'anchored_chain_cleanup')
        return -1, "excepcion durante recorrido anclado: {0}: {1}".format(
            type(exc).__name__, str(exc)[:80])


def _ensure_parents_anchored(path):
    """Crea los componentes padre faltantes de forma anclada (C1, v0.2.3).

    Recorre la ruta componente a componente abriendo cada directorio
    existente con O_PATH|O_NOFOLLOW|O_DIRECTORY relativo al descriptor del
    padre (dir_fd). Si un componente no existe, se crea con
    os.mkdir(name, mode=0o700, dir_fd=padre) — nunca por ruta completa.
    Los symlinks en componentes existentes se rechazan por O_NOFOLLOW.

    Si el recorrido anclado no es viable (O_PATH/O_DIRECTORY ausentes o
    apertura fallida), lanza OSError: falla de forma conservadora, sin
    recurrir a operaciones inseguras por ruta.

    Retorna el Path del ultimo directorio asegurado.
    """
    p = Path(path)
    if not p.is_absolute():
        raise OSError(errno.EINVAL,
                      "_ensure_parents_anchored requiere path absoluto: {0}".format(p))
    if not hasattr(os, 'O_PATH') or not hasattr(os, 'O_DIRECTORY'):
        raise OSError(errno.EOPNOTSUPP,
                      "O_PATH/O_DIRECTORY no disponibles: recorrido anclado "
                      "no viable")
    fd, msg = safe_open_dir_anchored(os.sep)
    if fd < 0:
        raise OSError(errno.EIO, "no se pudo abrir '/' de forma anclada: {0}".format(msg))
    try:
        for part in p.parts[1:]:
            if not part:
                continue
            try:
                fd_next = os.open(part, os.O_PATH | os.O_NOFOLLOW
                                  | os.O_DIRECTORY, dir_fd=fd)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise OSError(
                        exc.errno,
                        "apertura anclada fallo en {0}: {1}".format(
                            part, os.strerror(exc.errno))) from exc
                # Componente ausente: crearlo anclado al padre actual.
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except OSError as exc2:
                    raise OSError(
                        exc2.errno,
                        "creacion anclada fallo en {0}: {1}".format(
                            part, os.strerror(exc2.errno))) from exc2
                fd_next = os.open(part, os.O_PATH | os.O_NOFOLLOW
                                  | os.O_DIRECTORY, dir_fd=fd)
            # C4 (v0.2.4): no se silencia el error de cierre del padre.
            _close_fd_tracked(fd, 'ensure_parents_chain_parent')
            fd = fd_next
        return p
    except BaseException:
        # Cerrar los descriptores abiertos antes de propagar.
        # C4 (v0.2.4): los errores de cierre se conservan, no se silencian.
        _close_fd_tracked(fd, 'ensure_parents_chain_cleanup')
        raise


def safe_makedirs_exclusive_anchored(path):
    """Crea un directorio de forma exclusiva con recorrido anclado (C1.3).

    CORRECCION C1.5: No reutiliza directorios de ejecucion preexistentes.
    CORRECCION C1.6: Comprueba permisos del directorio padre existente.
    CORRECCION C1 (v0.2.3): eliminado el fallback por ruta directa
    (os.mkdir(str(p))). La creacion del componente final se realiza
    siempre anclada (os.mkdir con dir_fd); si el recorrido anclado no es
    viable, la funcion falla de forma conservadora con OSError.

    Estrategia:
    1. Verifica que el path sea absoluto.
    2. Si el path completo ya existe (lstat), falla con EEXIST.
    3. Asegura los componentes padre existentes/creables con recorrido
       anclado (_ensure_parents_anchored) y verifica seguridad del padre.
    4. Crea el componente final con os.mkdir(name, mode=0o700,
       dir_fd=parent_fd).
    5. Verifica por descriptor que el creado es un directorio (no symlink).

    Lanza OSError si no puede garantizarse la propiedad exclusiva o si el
    mecanismo anclado no es viable. Retorna el Path del directorio creado.
    """
    p = Path(path)
    if not p.is_absolute():
        raise OSError(errno.EINVAL,
                      "safe_makedirs_exclusive_anchored requiere path absoluto: {0}".format(p))

    # Paso 1: verificar que el path completo NO existe previamente
    try:
        st = os.lstat(str(p))
        # Si llegamos aqui, ya existe (no importa si es dir, file o symlink)
        if stat.S_ISLNK(st.st_mode):
            raise OSError(errno.ELOOP,
                          "path destino es symlink preexistente: {0}".format(p))
        raise OSError(errno.EEXIST,
                      "directorio de ejecucion preexistente: {0}".format(p))
    except FileNotFoundError:
        pass  # OK, no existe, podemos crearlo

    # Paso 2: asegurar los padres de forma anclada (C1, v0.2.3)
    parent = p.parent
    try:
        _ensure_parents_anchored(parent)
    except OSError as exc:
        raise OSError(exc.errno,
                      "creacion de padres anclada fallo: {0}: {1}".format(parent, exc))

    # Verificar que el padre existente es seguro (C1.6)
    ok, msg = check_dir_is_safe(parent,
                                expected_uid=os.geteuid() if hasattr(os, 'geteuid') else None)
    if not ok:
        raise OSError(errno.EPERM,
                      "directorio padre inseguro: {0}: {1}".format(parent, msg))

    # Paso 3: crear el directorio final de forma exclusiva, siempre anclada
    parent_fd, anchor_msg = safe_open_dir_anchored(str(parent))
    if parent_fd < 0:
        # Falla conservadora: no hay fallback por ruta (C1, v0.2.3).
        raise OSError(errno.EIO,
                      "apertura anclada del padre fallo: {0} (path: {1})".format(
                          anchor_msg, parent))
    try:
        try:
            os.mkdir(p.name, mode=0o700, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                raise OSError(errno.EEXIST,
                              "directorio de ejecucion preexistente (anclado): {0}".format(p))
            raise
        # Paso 4: verificar por descriptor que el creado es un directorio
        check_fd = os.open(p.name, os.O_PATH | os.O_NOFOLLOW
                           | os.O_DIRECTORY, dir_fd=parent_fd)
        try:
            st_final = os.fstat(check_fd)
        finally:
            # C4 (v0.2.4): error de cierre del descriptor de verificacion conservado.
            _close_fd_tracked(check_fd, 'makedirs_verify_fd')
        if not stat.S_ISDIR(st_final.st_mode):
            raise OSError(errno.ENOTDIR,
                          "path creado no es directorio: {0}".format(p))
    finally:
        # C4 (v0.2.4): error de cierre del descriptor del padre conservado.
        _close_fd_tracked(parent_fd, 'makedirs_parent_fd')
    return p


def safe_create_file_exclusive_anchored(path, content_bytes):
    """Crea un archivo de forma exclusiva con creacion anclada (C1.7 + C7).

    CORRECCION C7: escritura completa con manejo de escrituras parciales.
    CORRECCION C1 (v0.2.3): eliminada la creacion por ruta completa
    (os.open(str(p))). El archivo se crea siempre anclado: se abre el
    directorio padre con safe_open_dir_anchored() y se crea el archivo con
    os.open(name, ..., dir_fd=parent_fd). Si el recorrido anclado no es
    viable, la funcion falla de forma conservadora (no hay fallback por
    ruta). La comprobacion previa de symlinks del padre se mantiene como
    rejection anticipado, no como sustituto del mecanismo anclado.

    - Crea el archivo con O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, mode 0600,
      relativa al descriptor del padre.
    - Escribe content_bytes en bucle hasta completar o detectar escritura cero.
    - Cierra el fd y el descriptor del padre, conservando errores de cierre.
    - Si la escritura no se completa, retorna error y el archivo queda
      potencialmente incompleto (no se elimina automaticamente).

    Retorna (ok, error_or_None, close_error_or_None).
    """
    p = Path(path)
    if not p.is_absolute():
        return False, "safe_create_file_exclusive_anchored requiere path absoluto: {0}".format(p), None
    parent = p.parent
    try:
        check_no_symlink_in_path(parent)
    except OSError as exc:
        return False, "symlink en padre: {0}".format(exc), None

    parent_fd, anchor_msg = safe_open_dir_anchored(str(parent))
    if parent_fd < 0:
        # Falla conservadora: no hay fallback por ruta (C1, v0.2.3).
        return False, "apertura anclada del padre fallo: {0} (path: {1})".format(
            anchor_msg, parent), None

    # C4 (v0.2.5): propiedad por apertura — el descriptor del archivo se
    # registra con token y se cierra asociado a el; el descriptor del
    # directorio padre se cierra con _close_fd_tracked. Los errores de
    # cierre se conservan y se reportan (sin silencio).
    closer = CloseErrorLogger()
    close_error = None
    parent_close_error = None
    ok = False
    err = None
    fd = None
    fd_token = None
    try:
        try:
            fd = os.open(p.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                err = "archivo ya existe: {0}".format(p)
            else:
                err = "os.open anclado errno={0}: {1}".format(
                    exc.errno, os.strerror(exc.errno))
        else:
            # C4 (v0.2.5): registro de propiedad por apertura (token).
            fd_token = closer.register_fd(fd, 'create_file_fd')
            try:
                if content_bytes:
                    # C7: escritura completa con manejo de escrituras parciales
                    total = len(content_bytes)
                    written = 0
                    zero_write_count = 0
                    while written < total:
                        try:
                            n = os.write(fd, content_bytes[written:])
                        except OSError as exc:
                            err = "write errno={0}: {1} en offset={2}".format(
                                exc.errno, os.strerror(exc.errno), written)
                            break
                        if n == 0:
                            zero_write_count += 1
                            if zero_write_count > 3:
                                err = "write devolvio 0 repetidamente en offset={0}".format(written)
                                break
                        else:
                            zero_write_count = 0
                        written += n
                    if err is None and written != total:
                        err = "escritura incompleta: written={0} total={1}".format(written, total)
                if err is None:
                    ok = True
            finally:
                # C4 (v0.2.5): cierre asociado al token; error conservado.
                exc_close = closer.close_fd(fd, 'create_file_fd', token=fd_token)
                if exc_close is not None:
                    close_error = "close errno={0}: {1}".format(
                        exc_close.errno, os.strerror(exc_close.errno))
                    # Si la escritura fue OK pero el cierre fallo, se conserva
                    # el error de cierre (el archivo no se invalida).
                fd = None
                fd_token = None
    finally:
        # C4 (v0.2.5): cierre del descriptor del padre conservado (sin silencio).
        exc_parent = _close_fd_tracked(parent_fd, 'create_file_parent_fd')
        if exc_parent is not None:
            parent_close_error = "parent_fd close errno={0}: {1}".format(
                exc_parent.errno, os.strerror(exc_parent.errno))
    close_errors = [e for e in (close_error, parent_close_error) if e]
    if not ok:
        if err is None:
            err = "escritura incompleta"
        if close_errors:
            err = err + " | " + " | ".join(close_errors)
        return False, err, close_errors[0] if close_errors else None
    if close_errors:
        return True, None, " | ".join(close_errors)
    return True, None, None


def validate_environments_distinct(private_path, shared_path):
    """Verifica que privado y compartido no sean el mismo directorio.

    CORRECCION C1.7: un error al comprobar identidad NO se interpreta como
    prueba de que los entornos son distintos. Si stat falla, se retorna
    (None, msg) indicando que no se pudo verificar, y el llamador debe decidir.

    Compara por (st_dev, st_ino) con os.stat (resuelve symlinks).

    Retorna:
    - (True, None) si los entornos son distintos.
    - (False, msg) si son el mismo objeto filesystem.
    - (None, msg) si no se pudo verificar (uno o ambos no existen, o stat fallo).
    """
    if shared_path is None:
        return True, None
    priv_str = str(private_path)
    shared_str = str(shared_path)
    # Comparacion por path resuelto
    priv_real = os.path.realpath(priv_str)
    shared_real = os.path.realpath(shared_str)
    if priv_real == shared_real:
        return False, "privado y compartido resuelven al mismo path: {0}".format(priv_real)
    # Comparacion por identidad de filesystem (st_dev, st_ino)
    try:
        priv_stat = os.stat(priv_real)
    except OSError as exc:
        return None, "no se pudo stat privado {0}: errno={1} ({2})".format(
            priv_real, exc.errno, os.strerror(exc.errno))
    try:
        shared_stat = os.stat(shared_real)
    except OSError as exc:
        return None, "no se pudo stat compartido {0}: errno={1} ({2})".format(
            shared_real, exc.errno, os.strerror(exc.errno))
    if priv_stat.st_dev == shared_stat.st_dev and priv_stat.st_ino == shared_stat.st_ino:
        return False, ("privado y compartido son el mismo objeto filesystem "
                       "(dev={0}, ino={1})".format(priv_stat.st_dev, priv_stat.st_ino))
    return True, None


# ----------------------------------------------------------------------------
# C2/C3: helpers de verificacion con reporte detallado
# ----------------------------------------------------------------------------

def sha256_canonical(path):
    """SHA-256 del archivo completo por lectura binaria estandar (open).

    Retorna una tupla (hex_digest, size, error_or_None).
    Si error es None, el hash se computo correctamente.
    """
    h = hashlib.sha256()
    size = 0
    try:
        with open(path, "rb") as f:
            while True:
                block = f.read(1 << 20)
                if not block:
                    break
                h.update(block)
                size += len(block)
        return h.hexdigest(), size, None
    except OSError as exc:
        return None, size, "OSError errno={0}: {1}".format(exc.errno, os.strerror(exc.errno))


class PreadHashResult:
    """Resultado estructurado de sha256_pread_v2 (C3 — v0.2.1)."""
    def __init__(self, status, hex_digest=None, bytes_read=0, size_observed=0,
                 size_final=0, error=None, error_class=None):
        self.status = status
        # status ∈ {'COMPLETE', 'ZERO_SIZE', 'EMPTY_UNEXPECTED', 'PARTIAL',
        #           'SIZE_CHANGED', 'SYSTEM_ERROR'}
        self.hex_digest = hex_digest
        self.bytes_read = bytes_read
        self.size_observed = size_observed
        self.size_final = size_final
        self.error = error
        self.error_class = error_class

    def is_pass(self):
        return self.status in ('COMPLETE', 'ZERO_SIZE')

    def summary(self):
        return ("status={0} bytes_read={1} size_observed={2} size_final={3} "
                "hash={4} error={5}".format(
                    self.status, self.bytes_read, self.size_observed, self.size_final,
                    (self.hex_digest[:16] + '...') if self.hex_digest else 'None',
                    self.error))


def sha256_pread_v2(fd, blocksize=1 << 20):
    """SHA-256 del contenido accesible por fd mediante os.pread (C3 — v0.2.1).

    No mueve el offset del descriptor. Lee desde offset 0 hasta el final
    usando os.pread(fd, n, offset) en cada bloque.

    Clasifica el resultado:
    - COMPLETE: se leyeron exactamente size bytes (size > 0). hash es valido.
    - ZERO_SIZE: fstat devolvio size == 0. Hash del contenido vacio. El hash
      es valido (sha256 de b''), pero no hay contenido que verificar.
    - EMPTY_UNEXPECTED: size > 0 pero pread devolvio b'' en offset 0 sin error
      del sistema. EOF prematuro antes de leer ningun byte.
    - PARTIAL: se leyeron menos bytes que size sin que pread devolviera b''.
      Lectura corta: pread devolvio menos bytes de los solicitados sin ser EOF.
    - SIZE_CHANGED: el size observado al inicio difiere del size observado al
      final. NO se garantiza que el hash corresponda a un estado coherente.
      LIMITACION EXPLICITA (C3.4, C3.5): un cambio de contenido que conserve
      el tamano pasa inadvertido. SIZE_CHANGED no es un mecanismo completo de
      deteccion de modificaciones concurrentes.
    - SYSTEM_ERROR: OSError durante fstat o pread. error contiene el errno.

    No afirma estabilidad o coherencia de captura frente a escritores
    concurrentes. Solo clasifica el resultado de la lectura.
    """
    # Paso 1: fstat inicial
    try:
        st = os.fstat(fd)
        size_initial = st.st_size
    except OSError as exc:
        return PreadHashResult('SYSTEM_ERROR', error="fstat: errno={0}".format(exc.errno),
                               error_class='OSError')

    # Caso: archivo vacio legitimo
    if size_initial == 0:
        h = hashlib.sha256()
        return PreadHashResult('ZERO_SIZE', hex_digest=h.hexdigest(),
                              bytes_read=0, size_observed=0, size_final=0)

    # Paso 2: lectura por bloques con pread
    h = hashlib.sha256()
    offset = 0
    bytes_read = 0
    while offset < size_initial:
        n_requested = min(blocksize, size_initial - offset)
        try:
            data = os.pread(fd, n_requested, offset)
        except OSError as exc:
            return PreadHashResult('SYSTEM_ERROR',
                                   hex_digest=h.hexdigest() if bytes_read > 0 else None,
                                   bytes_read=bytes_read, size_observed=size_initial,
                                   error="pread offset={0} n={1}: errno={2}".format(
                                       offset, n_requested, exc.errno),
                                   error_class='OSError')

        if not data:
            # EOF prematuro inesperado (pread devolvio b'' antes de leer size_initial)
            if offset == 0:
                return PreadHashResult('EMPTY_UNEXPECTED',
                                       hex_digest=None, bytes_read=0,
                                       size_observed=size_initial,
                                       error="pread devolvio b'' en offset 0 sin error del sistema")
            else:
                return PreadHashResult('PARTIAL',
                                       hex_digest=h.hexdigest(),
                                       bytes_read=bytes_read,
                                       size_observed=size_initial,
                                       error="pread devolvio b'' en offset={0} (size={1}); "
                                             "lectura corta antes de EOF".format(
                                                 offset, size_initial))

        # Verificar que leimos exactamente lo solicitado (diferenciar lectura corta)
        if len(data) != n_requested:
            # Lectura corta: pread devolvio menos bytes de los solicitados sin ser EOF
            return PreadHashResult('PARTIAL',
                                   hex_digest=h.hexdigest(),
                                   bytes_read=bytes_read + len(data),
                                   size_observed=size_initial,
                                   error="pread devolvio {0} bytes, esperados {1}, en offset={2} "
                                         "(lectura corta)".format(len(data), n_requested, offset))

        h.update(data)
        bytes_read += len(data)
        offset += len(data)

    # Paso 3: fstat final para detectar cambio de tamano
    try:
        st_final = os.fstat(fd)
        size_final = st_final.st_size
    except OSError as exc:
        # No podemos verificar cambio de tamano, pero el hash se computo
        return PreadHashResult('SYSTEM_ERROR',
                               hex_digest=h.hexdigest(),
                               bytes_read=bytes_read, size_observed=size_initial,
                               error="fstat final: errno={0}".format(exc.errno),
                               error_class='OSError')

    # Paso 4: clasificar resultado final
    if size_final != size_initial:
        # LIMITACION: solo detecta cambios de tamano. Un cambio de contenido
        # que conserve el tamano pasa inadvertido.
        return PreadHashResult('SIZE_CHANGED',
                               hex_digest=h.hexdigest(),
                               bytes_read=bytes_read,
                               size_observed=size_initial,
                               size_final=size_final,
                               error="tamano cambio de {0} a {1} durante la operacion; "
                                     "LIMITACION: cambios de contenido sin cambio de tamano "
                                     "pasan inadvertidos".format(size_initial, size_final))

    if bytes_read == size_initial:
        return PreadHashResult('COMPLETE', hex_digest=h.hexdigest(),
                              bytes_read=bytes_read, size_observed=size_initial,
                              size_final=size_final)
    else:
        return PreadHashResult('PARTIAL',
                               hex_digest=h.hexdigest(),
                               bytes_read=bytes_read, size_observed=size_initial,
                               size_final=size_final,
                               error="bytes_read={0} != size={1}".format(
                                   bytes_read, size_initial))


# ----------------------------------------------------------------------------
# C4 (v0.2.3): sink de errores de cierre. Los errores de cierre que se
# producen mientras una prueba se desenvolve por una excepcion o una
# interrupcion se acumulan aquí, para que run_environment pueda
# conservarlos en el resultado (los closers de las pruebas son locales y
# no son accesibles desde el llamador). Se drena antes de cada prueba y
# al capturar una excepcion/interrupcion.
_close_error_sink = []
# C4-B (v0.2.9): acumulador PERSISTENTE por ejecucion. Cada error de cierre se
# incorpora aqui en el momento del registro (con identificador unico), ANTES de
# cualquier drenaje, de modo que una reconstruccion del informe no pierda los
# errores ya recogidos y ningun drenaje provoque perdida irreversible.
_close_error_ledger = []
_close_error_seq = [0]
# Identificadores de errores ya incorporados a una estructura persistente
# (resultado de prueba u operacion): no se repiten en environment_close_errors.
_attributed_close_error_ids = set()


def _reset_close_error_accounting():
    """C4-B (v0.2.9): reinicia la contabilidad de errores de cierre de la
    ejecucion (se invoca al inicio de main). No altera la propiedad ni el
    ciclo de vida de los recursos (C4-A congelado)."""
    del _close_error_sink[:]
    del _close_error_ledger[:]
    _attributed_close_error_ids.clear()
    _close_error_seq[0] = 0


def _record_close_error(entry):
    """Registra un error de cierre: cola pendiente + acumulador persistente.

    C4-B (v0.2.9): cada entrada recibe un identificador unico al registrarse;
    la incorporacion al acumulador persistente ocurre en el registro, por lo
    que ningun drenaje posterior puede provocar perdida irreversible.
    """
    if isinstance(entry, dict) and '_close_err_id' not in entry:
        _close_error_seq[0] += 1
        entry['_close_err_id'] = _close_error_seq[0]
    _close_error_sink.append(entry)
    _close_error_ledger.append(entry)


def _drain_close_error_sink():
    """Extrae la cola pendiente de errores de cierre (compatibilidad v0.2.3+).

    C4-B (v0.2.9): el drenaje NO provoca perdida: todas las entradas ya fueron
    incorporadas al acumulador persistente en el registro y quedan disponibles
    para reconstrucciones del informe aunque la cola quede vacia.
    """
    errors = list(_close_error_sink)
    _close_error_sink.clear()
    return errors


def _mark_close_errors_attributed(errors):
    """C4-B (v0.2.9): marca errores como incorporados a una estructura
    persistente (resultado de prueba u operacion) para que no se dupliquen
    en environment_close_errors. No convierte advertencias en errores ni
    viceversa: solo marca atribucion por identificador."""
    for e in errors or []:
        if isinstance(e, dict) and '_close_err_id' in e:
            _attributed_close_error_ids.add(e['_close_err_id'])


def _close_errors_unattributed():
    """C4-B (v0.2.9): errores de cierre NO atribuidos a resultados concretos.

    Incorpora primero cualquier pendiente de la cola (no se asume que este
    vacia por drenajes anteriores) y retorna las entradas del acumulador
    persistente sin identificador de atribucion. Lectura NO destructiva:
    llamadas sucesivas no pierden ni duplican entradas.
    """
    if _close_error_sink:
        _close_error_sink.clear()  # ya estan en el acumulador persistente
    return [e for e in _close_error_ledger
            if isinstance(e, dict)
            and e.get('_close_err_id') not in _attributed_close_error_ids]


# ----------------------------------------------------------------------------
# C5 (v0.2.11): coherencia de interrupciones, finalizacion e informe.
# ----------------------------------------------------------------------------

def _close_pair_conserving_interrupt(closer, sfile, sfile_label,
                                     fd, fd_label, fd_token):
    """Limpieza conservadora ante interrupcion (C5 — v0.2.11).

    Intenta cerrar el SoundFile (si aplica) y DESPUES el descriptor
    propietario (si aplica), de modo que una KeyboardInterrupt durante el
    cierre de SoundFile NO impida intentar el cierre independiente del
    descriptor propietario.

    Contratos intactos:
    - C4-A: los cierres se solicitan por el canal del propietario
      (close_fd con token / close_soundfile); el estado del recurso
      (CLOSING/CLOSED/UNCERTAIN) impide reintentos y cierres duplicados
      por diseno; aqui no se emite ninguna declaracion de exito.
    - C4-B: los errores de limpieza siguen registrandose en el acumulador
      persistente via _append_error/_record_close_error.

    Retorna True si se absorbio una KeyboardInterrupt durante la limpieza
    (el llamador debe propagarla tras los intentos), False en caso
    contrario.
    """
    ki_absorbida = False
    if sfile is not None:
        try:
            closer.close_soundfile(sfile, sfile_label)
        except KeyboardInterrupt:
            # Resultado del cierre incierto: NO se reintenta; la
            # interrupcion se propaga tras los intentos de limpieza.
            ki_absorbida = True
    if fd is not None:
        try:
            closer.close_fd(fd, fd_label, token=fd_token)
        except KeyboardInterrupt:
            # Cierre con resultado incierto (el recurso queda en estado
            # CLOSING): NO se reintenta (contrato C4-A); la interrupcion
            # se propaga tras los intentos de limpieza.
            ki_absorbida = True
    return ki_absorbida


def _reconcile_pending_tests(results, env_names, detail):
    """Reconciliacion idempotente de pruebas planificadas (C5 — v0.2.11).

    Registra NOT_EXECUTED para toda prueba planificada (por entorno:
    T11-T14 por fixture y T15/T16 sin fixture) que carezca de registro en
    results (por ejemplo, una interrupcion fuera de los bloques protegidos
    o una excepcion fatal durante la fase de entornos). Idempotente:
    llamadas sucesivas no anaden ni modifican registros; los resultados
    ya obtenidos se conservan intactos.

    Retorna el numero de registros anadidos (0 en una segunda llamada).
    """
    existing = set()
    for r in results:
        existing.add((r.get('env'), r.get('test'), r.get('fixture')))
    anadidos = 0
    for env in env_names:
        for fname, _subtype in FIXTURE_SPECS:
            for tid in ['T11', 'T12', 'T13', 'T14']:
                if (env, tid, fname) not in existing:
                    results.append({'env': env, 'test': tid, 'fixture': fname,
                                    'status': Result.NOT_EXECUTED,
                                    'detail': detail,
                                    'close_errors': []})
                    anadidos += 1
        for tid in ['T15', 'T16']:
            if (env, tid, None) not in existing:
                results.append({'env': env, 'test': tid, 'fixture': None,
                                'status': Result.NOT_EXECUTED,
                                'detail': detail,
                                'close_errors': []})
                anadidos += 1
    return anadidos


def _publication_state_after_interrupt(report_path):
    """Determina el estado real de publicacion del informe tras una
    KeyboardInterrupt (C5 — v0.2.11).

    Verificacion de SOLO LECTURA (ninguna escritura, ningun reintento de
    publicacion, ninguna limpieza): compara la identidad (st_dev, st_ino)
    del informe final con la del provisional creado por esta ejecucion
    (el enlace duro de C1 comparte inode; un archivo ajeno preexistente
    con el mismo nombre NO lo comparte y no se confunde).

    Retorna (estado, detalle) con estado en:
      'PUBLICADO'     — el informe final existe y es el enlace de esta
                        ejecucion (o el provisional fue eliminado tras un
                        enlace exitoso: la unica ruta del flujo que lo
                        elimina).
      'NO_PUBLICADO'  — el provisional de esta ejecucion sigue en disco y
                        el informe final no existe, o existe un archivo
                        ajeno con identidad distinta.
      'INDETERMINADO' — el estado no pudo verificarse (error de acceso
                        distinto de inexistencia).
    """
    ruta_final = str(report_path)
    ruta_prov = ruta_final + '.tmp'
    st_final = None
    st_prov = None
    try:
        st_final = os.stat(ruta_final)
    except FileNotFoundError:
        st_final = None
    except OSError as exc:
        return ('INDETERMINADO',
                'no se pudo verificar el informe final (errno={0})'.format(
                    exc.errno))
    try:
        st_prov = os.stat(ruta_prov)
    except FileNotFoundError:
        st_prov = None
    except OSError as exc:
        return ('INDETERMINADO',
                'no se pudo verificar el provisional (errno={0})'.format(
                    exc.errno))
    if st_final is not None and st_prov is not None:
        if ((st_final.st_dev, st_final.st_ino)
                == (st_prov.st_dev, st_prov.st_ino)):
            return ('PUBLICADO',
                    'el informe comparte identidad (st_dev, st_ino) con el '
                    'provisional de esta ejecucion: el enlace se completo; '
                    'el provisional se conserva (sin limpieza automatica)')
        return ('NO_PUBLICADO',
                'el informe no se publica: existe un archivo con el nombre '
                'del informe pero su identidad no coincide con el '
                'provisional de esta ejecucion (archivo ajeno preexistente); '
                'provisional conservado')
    if st_final is not None and st_prov is None:
        return ('PUBLICADO',
                'provisional ausente: la unica ruta del flujo que lo '
                'elimina es la eliminacion posterior a un enlace exitoso')
    if st_final is None and st_prov is not None:
        return ('NO_PUBLICADO',
                'el informe no se publica: provisional de esta ejecucion en '
                'disco; informe final inexistente; sin segunda publicacion')
    return ('NO_PUBLICADO',
            'el informe no se publica: ni el informe final ni el provisional '
            'existen')


def _reconcile_interrupted(interrupt_flag, interrupted, interrupt_msg):
    """Reconcilia el estado global de interrupcion (C5 — v0.2.4).

    Una interrupcion absorbida a nivel de prueba o de entorno puede no
    haber propagado el KeyboardInterrupt al llamador, pero el flag mutable
    es el estado real de la ejecucion. Si el flag esta seteado y
    `interrupted` no, se fija y se registra el motivo, de modo que el
    resumen, el informe JSON y el codigo de salida reflejen la
    interrupcion real (nunca PASS).

    Retorna (interrupted, interrupt_msg).
    """
    if interrupt_flag and interrupt_flag[0] and not interrupted:
        interrupted = True
        interrupt_msg = (interrupt_msg + "; " if interrupt_msg else "") + \
            "interrupcion detectada via interrupt_flag"
    return interrupted, interrupt_msg


def _close_fd_tracked(fd, label):
    """Cierra un descriptor conservando el error (C4 — v0.2.4).

    Sustituye los `except OSError: pass`: todo error de cierre se
    conserva en el sink y se devuelve, nunca se silencia.

    Retorna None si el cierre fue OK (o fd es None/invalido sin cierre
    posible), o el OSError si fallo.
    """
    if fd is None or fd < 0:
        return None
    try:
        os.close(fd)
        return None
    except OSError as exc:
        _record_close_error({"label": label, "errno": exc.errno,
                             "strerror": os.strerror(exc.errno)})
        return exc


# C4-A (v0.2.6): modelo de propiedad por recurso con ciclo de vida explicito.
# ----------------------------------------------------------------------------

class OwnedFdResource(object):
    """Recurso de propiedad: UNA apertura concreta de un descriptor (C4-A v0.2.6).

    Encapsula el numero de descriptor y su estado. La identidad de la
    apertura es el objeto recurso creado en el registro, NO un predicado
    observable del numero de fd: Python no expone una identidad portatil
    del open-file-description (OFD) del kernel, y fstat() no permite
    distinguir la reapertura del mismo archivo con el mismo numero de fd
    (limitacion documentada del contrato de propiedad).

    CONTRATO DE PROPIEDAD: el descriptor de un recurso SOLO se cierra a
    traves de su recurso, una unica vez. Ningun otro componente debe
    invocar os.close() sobre el numero ni cerrarlo por via externa. Si el
    contrato se viola, el estado se considera incierto
    (CLOSE_FAILED_UNCERTAIN) y no se reintenta ningun cierre con ese
    numero a traves del token.

    ESTADOS Y TRANSICIONES:
      OPEN                    apertura registrada; propiedad vigente.
      CLOSING                 cierre iniciado (transitorio; solo se alcanza
                              desde OPEN y una unica vez).
      CLOSED                  cierre confirmado: os.close() retorno sin
                              error para el recurso del propietario.
      CLOSE_FAILED_UNCERTAIN  el resultado no permite garantizar que el
                              numero de fd siga perteneciendo al recurso
                              original: EBADF en la guardia previa (cierre
                              externo o numero reutilizado y re-cerrado),
                              identidad distinta en la guardia previa, o
                              error de os.close(). Estado terminal: el
                              cierre NUNCA se reintenta.

        OPEN --cierre unico--> CLOSING --os.close OK--> CLOSED
                                      |-- guardia EBADF / identidad
                                      |   distinta / error de os.close
                                      v
                           CLOSE_FAILED_UNCERTAIN

    Guardia previa al cierre (defensiva, NO prueba de identidad): la
    comparacion (st_dev, st_ino) contra la registrada detecta la
    reutilizacion del numero por OTRO archivo. NO detecta la reutilizacion
    por el MISMO archivo (mismo dev, ino): ese caso es indetectable de
    forma portatil y queda cubierto solo por el contrato de propiedad
    (limitacion documentada; no se presenta como deteccion).

    Acceso por clave (compatibilidad con harness v0.2.4/v0.2.5): las
    claves 'token', 'fd', 'label', 'dev', 'ino', 'state' y 'close_result'
    leen los atributos homonimos.
    """
    STATE_OPEN = 'open'
    STATE_CLOSING = 'closing'
    STATE_CLOSED = 'closed'
    STATE_UNCERTAIN = 'close_failed_uncertain'

    _COMPAT_KEYS = ('token', 'fd', 'label', 'dev', 'ino', 'state',
                    'close_result')

    __slots__ = ('token', 'fd', 'label', 'dev', 'ino', 'state',
                 'close_result')

    def __init__(self, token, fd, label, dev, ino):
        self.token = token
        self.fd = fd
        self.label = label
        self.dev = dev
        self.ino = ino
        self.state = self.STATE_OPEN
        self.close_result = None

    def __getitem__(self, key):
        if key in self._COMPAT_KEYS:
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key):
        return key in self._COMPAT_KEYS

    def __repr__(self):
        return ("OwnedFdResource(token={0}, fd={1}, label={2}, state={3}, "
                "close_result={4})".format(self.token, self.fd, self.label,
                                           self.state, self.close_result))


class _ResourceSnapshot(object):
    """Instantanea INMUTABLE del estado de consulta de un recurso (v0.2.8).

    get_resource(token) retorna una copia puntual de los campos de
    consulta (token, fd, label, dev, ino, state, close_result) del
    recurso interno; NO expone ni conserva referencia alguna al objeto
    OwnedFdResource (no existe _res ni ningun atributo de reenvio), de
    modo que ningun consumidor externo puede modificar el estado, el
    descriptor o la propiedad del recurso a traves del objeto retornado.

    - Lectura por atributo y por clave (compatibilidad de consulta).
    - Los intentos de asignacion de atributos o claves son rechazados:
      la instantanea es de solo lectura.
    - La instantanea es una COPIA: incluso una mutacion hostil de sus
      campos (p. ej. via object.__setattr__, fuera del alcance exigido)
      no altera el recurso interno.
    - Cada nueva llamada a get_resource(token) toma una instantanea que
      refleja el estado ACTUAL del recurso en ese momento; una
      instantanea obtenida antes de una transicion no se actualiza
      (semantica de fotografia).

    No se modifica la maquina de estados ni la logica de cierre
    (OwnedFdResource y close_fd permanecen intactos).
    """
    _FIELDS = ('token', 'fd', 'label', 'dev', 'ino', 'state', 'close_result')
    __slots__ = _FIELDS

    def __init__(self, resource):
        # Copia puntual de los campos; sin referencia al objeto interno.
        for field in self._FIELDS:
            object.__setattr__(self, field, getattr(resource, field))

    def __setattr__(self, name, value):
        raise AttributeError(
            "la instantanea es de solo lectura; el estado y la propiedad "
            "del recurso solo se modifican dentro del logger propietario")

    def __getitem__(self, key):
        if key in self._FIELDS:
            return getattr(self, key)
        raise KeyError(key)

    def __contains__(self, key):
        return key in self._FIELDS

    def __repr__(self):
        return ("_ResourceSnapshot(token={0}, fd={1}, label={2}, state={3}, "
                "close_result={4})".format(self.token, self.fd, self.label,
                                           self.state, self.close_result))


class CloseErrorLogger:
    """Acumula errores de cierre de descriptores y SoundFile (C4).

    CORRECCION C4.1: eliminados except Exception: pass que silencian fallos.
    CORRECCION C4.2: registra errores de cierre de SoundFile y descriptores.
    CORRECCION C4.3: propaga errores al resultado final de cada prueba.
    CORRECCION C4.6: no intenta cerrar dos veces un descriptor de estado incierto.

    CORRECCION C4 (v0.2.4): propiedad por apertura con token unico.

    CORRECCION C4-A (v0.2.6): modelo de propiedad por RECURSO con ciclo de
    vida explicito (OwnedFdResource). Cada apertura registrada crea un
    recurso que encapsula el numero de descriptor y su estado; el token es
    el identificador externo del recurso. La identidad de la apertura es el
    objeto recurso creado en el registro, NO un predicado observable: ni el
    numero de fd (reutilizable) ni (st_dev, st_ino) (que no distingue dos
    aperturas del mismo archivo) prueban identidad. fstat() se usa solo
    como GUARDIA defensiva previa al cierre (detecta reutilizacion por
    otro archivo y detecta cierre externo por EBADF); NO como prueba de
    identidad (limitacion documentada; no se presenta como solucion).

    CONTRATO DE PROPIEDAD (C4-A): el descriptor registrado SOLO se cierra
    a traves de su recurso, una unica vez. Dentro del instrumento, ningun
    otro componente invoca os.close() sobre un descriptor registrado y
    SoundFile opera con closefd=False por contrato, de modo que el
    propietario conserva la responsabilidad del cierre. Si el contrato se
    viola por via externa y la violacion es observable (EBADF, identidad
    distinta), el recurso pasa a CLOSE_FAILED_UNCERTAIN y ningun cierre
    posterior se intenta con ese numero a traves del token. La violacion
    indetectable (cierre externo + reutilizacion del MISMO numero para el
    MISMO archivo) no es detectable de forma portatil: limitacion
    documentada, no una deteccion.

    REGLAS (C4-A, v0.2.7):
      - solo el propietario inicia el cierre de su recurso, una unica vez
        (OPEN -> CLOSING), SIEMPRE mediante el token de su apertura;
      - close_fd() SIN token (o con token no valido) NO cierra ningun
        descriptor, ni siquiera uno registrado como OPEN (contrato
        estricto; aviso, no operacion);
      - un token obsoleto (CLOSED, CLOSE_FAILED_UNCERTAIN o desconocido)
        nunca inicia un segundo cierre (aviso, no operacion);
      - un cierre incierto nunca se reintenta automaticamente;
      - un descriptor no registrado no se cierra mediante el logger (aviso);
      - get_resource(token) retorna una vista de SOLO LECTURA: el estado
        y la propiedad solo se modifican dentro del logger propietario;
      - los errores de cierre se conservan en self.errors y en el sink
        global para su posterior propagacion (la propagacion completa ante
        KeyboardInterrupt corresponde a C4-B, fuera de esta etapa).

    LIMITE DOCUMENTADO (EXPECTED_LIMITATION): la violacion indetectable del
    contrato (cierre externo + reutilizacion del MISMO numero para el
    MISMO archivo) no es detectable de forma portable; no se presenta como
    una proteccion conseguida (ver INFORME_CIERRE_C4_A.md).

    Los avisos van a `warnings`; los fallos reales a `errors`.
    """
    def __init__(self):
        self.errors = []
        self.warnings = []
        # token -> OwnedFdResource (C4-A v0.2.6; acceso tipo dict compatible)
        self._entries = {}
        self._by_fd = {}  # fd -> set(tokens)
        self._next_token = 0
        # (id(sfile), sfile) ya cerrados; se guarda la referencia para
        # evitar que el id sea reutilizado por el recolector.
        self._closed_sfiles = set()

    @staticmethod
    def _identity(fd):
        """Guardia de identidad observable: (st_dev, st_ino) o None.

        NOTA C4-A: NO es una prueba de identidad de la apertura (no
        distingue dos aperturas del mismo archivo ni la reapertura con el
        mismo numero). Solo sirve para la guardia previa al cierre
        (reutilizacion por otro archivo) y para detectar cierres externos
        (EBADF).
        """
        try:
            st = os.fstat(fd)
            return st.st_dev, st.st_ino
        except OSError:
            return None

    def _append_error(self, entry):
        self.errors.append(entry)
        _record_close_error(entry)  # sink para errores durante excepciones

    def get_resource(self, token):
        """Retorna una INSTANTANEA INMUTABLE del recurso del token (v0.2.8).

        Copia puntual de los campos de consulta (token, fd, label, dev,
        ino, state, close_result). NO expone ni conserva referencia al
        objeto OwnedFdResource interno: ningun consumidor puede modificar
        el estado, el descriptor o la propiedad a traves del objeto
        retornado. Cada nueva llamada refleja el estado ACTUAL del
        recurso en ese momento; una instantanea previa no se actualiza
        (semantica de fotografia).

        Retorna la instantanea, o None si el token es desconocido.
        """
        resource = self._entries.get(token)
        if resource is None:
            return None
        return _ResourceSnapshot(resource)

    def register_fd(self, fd, label):
        """Registra la propiedad de una apertura concreta (C4, v0.2.4).

        C4-A (v0.2.6): crea un OwnedFdResource que encapsula el numero de
        descriptor y su estado (OPEN inicial). El token retornado es el
        identificador externo del recurso; el cierre debe solicitarse
        asociado al token. La identidad de la apertura es el objeto recurso
        creado aqui (no un predicado observable del numero de fd).

        Retorna el token, o None si fd es None o invalido (error registrado).
        """
        if fd is None:
            return None
        identity = self._identity(fd)
        if identity is None:
            self._append_error({"label": label, "errno": errno.EBADF,
                                "strerror": "descriptor no valido al registrar"})
            return None
        self._next_token += 1
        token = self._next_token
        self._entries[token] = OwnedFdResource(token, fd, label,
                                               identity[0], identity[1])
        self._by_fd.setdefault(fd, set()).add(token)
        return token

    def close_fd(self, fd, label, token=None):
        """Solicita el cierre de un recurso de propiedad (C4-A cierre, v0.2.7).

        CONTRATO ESTRICTO: solo el propietario, mediante el token de SU
        apertura, puede iniciar el cierre; una unica vez.

        - Sin token: NO se cierra NINGUN descriptor (ni siquiera uno
          registrado como OPEN). Aviso y retorno inmediato: el cierre sin
          token esta rechazado por el contrato de propiedad.
        - Token desconocido: aviso; no se cierra nada.
        - Estados del recurso identificado por el token:
            OPEN: unico camino de cierre (una sola vez): guardias previas
              y os.close(); termina en CLOSED o CLOSE_FAILED_UNCERTAIN.
            CLOSING: aviso (cierre ya iniciado); no se duplica.
            CLOSED: aviso (token obsoleto); no se reintenta.
            CLOSE_FAILED_UNCERTAIN: aviso (resultado incierto previo);
              NUNCA se reintenta.
        - El cierre opera sobre resource.fd (la verdad del propietario);
          el argumento fd es informativo por compatibilidad de firma.
        - Guardias previas al os.close (defensivas, NO prueba de identidad):
            EBADF en fstat: cierre externo (contrato violado) o numero
              reutilizado y re-cerrado -> CLOSE_FAILED_UNCERTAIN, error
              conservado, os.close NO se invoca, no se reintenta.
            (st_dev, st_ino) distinto del registrado: el numero fue
              reutilizado por otro archivo -> NO se cierra el recurso
              ajeno -> CLOSE_FAILED_UNCERTAIN, anomalia conservada.
            Coincidencia: NO prueba que sea la misma apertura (limite
              documentado, EXPECTED_LIMITATION); el cierre procede bajo el
              contrato de propiedad.
        - Un error de os.close() deja el recurso en CLOSE_FAILED_UNCERTAIN
          (no se reintenta) y el error se conserva y se devuelve.

        Retorna None si OK o si hubo aviso (no operacion); el OSError si
        fallo el cierre.
        """
        # C4-A cierre (v0.2.7): contrato estricto. Sin token valido no se
        # cierra ningun descriptor. El cierre solo puede iniciarlo el
        # propietario con el token de SU apertura concreta.
        if token is None:
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "cierre sin token rechazado por el contrato de "
                             "propiedad; el cierre requiere el token de la "
                             "apertura"})
            return None
        resource = self._entries.get(token)
        if resource is None:
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "token de apertura desconocido; no se cierra nada"})
            return None
        if resource.state == resource.STATE_CLOSED:
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "apertura ya cerrada (token obsoleto); no se reintenta"})
            return None
        if resource.state == resource.STATE_UNCERTAIN:
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "cierre previo de resultado incierto; "
                             "no se reintenta (contrato de propiedad)"})
            return None
        if resource.state == resource.STATE_CLOSING:
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "cierre ya iniciado para este recurso; no se duplica"})
            return None
        fd = resource.fd

        # Unico camino de cierre: OPEN -> CLOSING (una sola vez).
        resource.state = resource.STATE_CLOSING

        # Guardia 1 (defensiva; NO prueba de identidad): el numero sigue
        # abierto. EBADF => cierre externo (contrato violado) o numero
        # reutilizado y vuelto a cerrar. Estado incierto; os.close NO se
        # invoca; no se reintenta.
        try:
            st = os.fstat(fd)
        except OSError as exc:
            resource.state = resource.STATE_UNCERTAIN
            resource.close_result = "uncertain:cerrado_externamente_o_reutilizado"
            self._append_error({"label": label, "errno": exc.errno,
                                "strerror": "descriptor cerrado externamente "
                                            "(contrato de propiedad violado) o "
                                            "numero reutilizado; cierre no "
                                            "realizado (estado incierto)"})
            return OSError(errno.EBADF, "descriptor no valido o cerrado")

        # Guardia 2 (defensiva; NO prueba de identidad): identidad del
        # archivo distinta a la registrada => el numero fue reutilizado por
        # otro archivo. No cerrar ajeno; estado incierto.
        if (st.st_dev != resource.dev) or (st.st_ino != resource.ino):
            resource.state = resource.STATE_UNCERTAIN
            resource.close_result = "uncertain:identidad_distinta"
            self.warnings.append(
                {"label": label, "errno": None,
                 "strerror": "identidad distinta tras registro; numero de "
                             "descriptor reutilizado por otro archivo; no se "
                             "cierra"})
            self._append_error({"label": label, "errno": None,
                                "strerror": "contrato de propiedad violado: "
                                            "numero reutilizado por otro "
                                            "archivo; cierre no realizado "
                                            "(estado incierto)"})
            return None

        # Intento unico de cierre del propietario.
        # LIMITE DOCUMENTADO (C4-A): si el contrato fue violado de forma
        # indetectable (cierre externo + reutilizacion del MISMO numero para
        # el MISMO archivo), esta operacion cerraria el recurso ajeno; la
        # coincidencia (dev, ino) NO es prueba de identidad. El diseno
        # depende del contrato de propiedad: dentro del instrumento,
        # ningun otro componente cierra descriptores registrados.
        try:
            os.close(fd)
        except OSError as exc:
            resource.state = resource.STATE_UNCERTAIN
            resource.close_result = "uncertain:close_errno={0}".format(exc.errno)
            self._append_error({"label": label, "errno": exc.errno,
                                "strerror": os.strerror(exc.errno)})
            return exc
        resource.state = resource.STATE_CLOSED
        resource.close_result = "ok"
        return None

    def close_soundfile(self, sfile, label):
        """Cierra un SoundFile de forma segura (C4, v0.2.4).

        CORRECCION C4.2: registra errores de cierre de SoundFile.
        CORRECCION C4.1: no usa except Exception: pass.
        CORRECCION C4 (v0.2.4): evita dobles cierres por reutilizacion de
        id(); los skips son avisos, no errores.
        """
        if sfile is None:
            return None
        key = (id(sfile), sfile)
        if key in self._closed_sfiles:
            self.warnings.append(
                {"label": label + "_duplicate_skipped", "errno": None,
                 "strerror": "SoundFile ya cerrado; no se reintenta"})
            return None
        try:
            sfile.close()
        except Exception as exc:
            self._closed_sfiles.add(key)
            self._append_error({"label": label, "errno": None,
                                "strerror": "{0}: {1}".format(
                                    type(exc).__name__, str(exc)[:80])})
            return exc
        self._closed_sfiles.add(key)
        return None

    def summary(self):
        if not self.errors:
            return None
        return "; ".join("{0} ({1})".format(e['label'], e.get('strerror', 'errno=' + str(e.get('errno')))) for e in self.errors)


# ----------------------------------------------------------------------------
# Generacion de fixtures
# ----------------------------------------------------------------------------

def generate_audio_array(np):
    """Genera array determinista (frames, channels) float64 en [-1, 1).

    Seed fija para reproducibilidad. Incluye casos extremos para detectar
    saturacion o clamping.
    """
    rng = np.random.default_rng(seed=42)
    arr = rng.uniform(-1.0, 1.0, (DURATION_FRAMES, CHANNELS))
    arr[0, 0] = -1.0
    arr[0, 1] = -0.5
    arr[-1, 0] = 0.999999
    arr[-1, 1] = 0.5
    return arr


def create_fixture(np, sf, dir_path, fixture_name, subtype, closer):
    """Crea un fixture WAV sintetico de forma exclusiva (C1 — v0.2.1).

    Usa os.open con O_CREAT|O_EXCL|O_NOFOLLOW. Pasa el fd a SoundFile con
    closefd=False y cierra el fd explicitamente.

    Retorna (Path al archivo creado, None) si OK, o (None, error_msg) si fallo.
    Los errores de cierre se registran en closer.
    """
    out_path = Path(dir_path) / "fixture_{0}.wav".format(fixture_name)
    arr = generate_audio_array(np)
    # C1 (v0.2.3): creacion anclada del fixture. Se abre el directorio
    # padre con recorrido anclado y se crea el archivo relativo al
    # descriptor del padre. Si el mecanismo anclado no es viable, se
    # falla de forma conservadora (no hay creacion por ruta completa).
    try:
        check_no_symlink_in_path(dir_path)
    except OSError as exc:
        return None, "symlink en directorio fixture: {0}".format(exc)
    parent_fd, anchor_msg = safe_open_dir_anchored(str(dir_path))
    if parent_fd < 0:
        return None, "apertura anclada del directorio fixture fallo: {0}".format(anchor_msg)
    try:
        try:
            fd = os.open(out_path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                         | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                return None, "fixture ya existe: {0}".format(out_path)
            return None, "os.open anclado errno={0}: {1}".format(
                exc.errno, os.strerror(exc.errno))
        # C4 (v0.2.4): registro de propiedad por apertura (token) para el
        # descriptor del fixture, de modo que el cierre se asocie a esta
        # apertura concreta y no a un numero de fd reutilizable.
        fd_token = closer.register_fd(fd, 'fixture_fd_' + fixture_name)
    finally:
        # C4 (v0.2.4): error de cierre del descriptor del padre conservado.
        _close_fd_tracked(parent_fd, 'fixture_parent_fd_' + fixture_name)

    sfile = None
    try:
        sfile = sf.SoundFile(fd, mode='w', samplerate=SAMPLE_RATE, channels=CHANNELS,
                            format='WAV', subtype=subtype, closefd=False)
        try:
            sfile.write(arr)
        except Exception as exc:
            return None, "sf.write fallo: {0}: {1} (archivo parcial queda en disco)".format(
                type(exc).__name__, str(exc)[:80])
        return out_path, None
    except Exception as exc:
        return None, "SoundFile open fallo: {0}: {1}".format(type(exc).__name__, str(exc)[:80])
    finally:
        # C4 (v0.2.4): registrar errores de cierre de SoundFile y del fd.
        # El cierre del fd se asocia al token de apertura registrado.
        # C5 (v0.2.11): una KI durante el cierre de SoundFile no impide
        # intentar el cierre independiente del descriptor propietario; la
        # KI se propaga despues de los intentos de limpieza posibles. Sin
        # reintentos de cierres inciertos ni cierres duplicados (estado
        # C4-A); errores secundarios conservados (C4-B).
        if _close_pair_conserving_interrupt(
                closer, sfile, 'fixture_writer_' + fixture_name,
                fd, 'fixture_fd_' + fixture_name, fd_token):
            raise KeyboardInterrupt()


# ----------------------------------------------------------------------------
# Pruebas individuales
# ----------------------------------------------------------------------------

def test_t11_soundfile_fd_closefd_false(np, sf, fixture_path):
    """T11: SoundFile(fd, closefd=False) abre correctamente y NO cierra el fd.

    Verifica:
    - Apertura por descriptor con closefd=False.
    - Metadatos accesibles (samplerate, channels, frames).
    - Tras sfile.close(), el fd original sigue abierto (closefd=False funciona).
    - Cierre exitoso del fd por el propietario (C4: errores de cierre registrados).
    """
    closer = CloseErrorLogger()
    fd = None
    fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    sfile = None
    try:
        fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
        # C4 (v0.2.5): registrar la propiedad de la apertura; todos los
        # cierres de este descriptor en la prueba se asocian al token.
        fd_token = closer.register_fd(fd, 'fd')
        st = os.fstat(fd)
        try:
            sfile = sf.SoundFile(fd, mode='r', closefd=False)
        except Exception as exc:
            closer.close_fd(fd, 'fd', token=fd_token)
            fd = None
            fd_token = None
            return (Result.FAIL,
                    "SoundFile open fallo: {0}: {1}".format(type(exc).__name__, str(exc)[:80]),
                    closer.errors)
        try:
            sr = sfile.samplerate
            ch = sfile.channels
            fr = sfile.frames
            ok_meta = (sr == SAMPLE_RATE and ch == CHANNELS and fr > 0)
            if not ok_meta:
                # C2: cierre incluso ante retorno anticipado
                closer.close_soundfile(sfile, 'sfile')
                sfile = None
                closer.close_fd(fd, 'fd', token=fd_token)
                fd = None
                fd_token = None
                return (Result.FAIL,
                        "metadatos incorrectos: sr={0}, ch={1}, fr={2}".format(sr, ch, fr),
                        closer.errors)
        finally:
            # sfile.close() se hace aqui explicitamente para poder verificar fd despues
            pass

        # Cerrar sfile y verificar que fd sigue abierto
        # C5 (v0.2.11): si la KI cae durante este cierre, el resultado es
        # incierto y NO se reintenta en el finally (sfile=None); el cierre
        # del descriptor se intenta en el finally y la interrupcion se
        # propaga tras los intentos de limpieza.
        try:
            closer.close_soundfile(sfile, 'sfile')
        except KeyboardInterrupt:
            sfile = None
            raise
        sfile = None
        try:
            os.fstat(fd)
            fd_alive = True
        except OSError as exc:
            fd_alive = False
            closer.close_fd(fd, 'fd', token=fd_token)
            fd = None
            fd_token = None
            return (Result.FAIL,
                    "fd cerrado por SoundFile.close() pese a closefd=False: errno={0}".format(exc.errno),
                    closer.errors)

        # Cierre del fd por el propietario (C4 v0.2.5: asociado al token)
        close_err = closer.close_fd(fd, 'fd', token=fd_token)
        fd = None
        fd_token = None
        if close_err is not None:
            return (Result.FAIL,
                    "cierre del fd fallo: errno={0}".format(close_err.errno),
                    closer.errors)
        if not fd_alive:
            return (Result.FAIL, "fd no estaba vivo tras sfile.close()", closer.errors)
        return (Result.PASS,
                "sr={0}, ch={1}, fr={2}, st_size={3}".format(sr, ch, fr, st.st_size),
                closer.errors)
    finally:
        # C5/C4: intento de cierre conservador ante excepcion o interrupcion
        # C4 (v0.2.5): el cierre conservador tambien se asocia al token.
        # C5 (v0.2.11): la KI durante el cierre de SoundFile no impide
        # intentar el cierre del descriptor propietario; se propaga tras
        # los intentos de limpieza.
        if _close_pair_conserving_interrupt(closer, sfile, 'sfile_finally',
                                            fd, 'fd_finally', fd_token):
            raise KeyboardInterrupt()


def test_t12_pread_works(np, sf, fixture_path):
    """T12: os.pread funciona en el almacenamiento objetivo.

    Verifica:
    - pread devuelve los bytes solicitados en offset 0 y en offset (size-100).
    - El offset del fd NO se mueve por las llamadas pread (sigue en 0).
    - Cierre exitoso del fd (C4: errores registrados).
    """
    closer = CloseErrorLogger()
    fd = None
    fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    try:
        fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
        # C4 (v0.2.5): registrar la propiedad de la apertura; todos los
        # cierres de este descriptor en la prueba se asocian al token.
        fd_token = closer.register_fd(fd, 'fd')
        size = os.fstat(fd).st_size
        if size < 200:
            closer.close_fd(fd, 'fd', token=fd_token)
            fd = None
            fd_token = None
            return (Result.FAIL, "archivo demasiado pequeno: {0} bytes".format(size),
                    closer.errors)
        first = os.pread(fd, 100, 0)
        last = os.pread(fd, 100, max(0, size - 100))
        pos = os.lseek(fd, 0, os.SEEK_CUR)
        offset_ok = (pos == 0)
        reads_ok = (len(first) == 100 and len(last) == 100)
        status = Result.PASS if (offset_ok and reads_ok) else Result.FAIL
        detail = ("pread(0,100)={0}B, pread(size-100,100)={1}B, fd_pos={2}, "
                  "offset_ok={3}, reads_ok={4}").format(
                      len(first), len(last), pos, offset_ok, reads_ok)
        close_err = closer.close_fd(fd, 'fd', token=fd_token)
        fd = None
        fd_token = None
        if close_err is not None:
            status = Result.FAIL
            detail += "; cierre_fd_fallo: errno={0}".format(close_err.errno)
        return (status, detail, closer.errors)
    finally:
        if fd is not None:
            closer.close_fd(fd, 'fd_finally', token=fd_token)


def test_t13_pread_hash_matches_canonical(np, sf, fixture_path):
    """T13: SHA-256 por pread == SHA-256 canónico (open binario).

    Verifica:
    - sha256_pread_v2 clasifica como COMPLETE o ZERO_SIZE (archivos vacios legitimos).
    - El hash coincide con el hash canónico por open().
    - El offset del fd NO se mueve tras el cálculo por pread.
    - sizes coinciden.
    - Cierre exitoso del fd (C4: errores registrados).
    """
    closer = CloseErrorLogger()
    fd = None
    fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    try:
        fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
        # C4 (v0.2.5): registrar la propiedad de la apertura; todos los
        # cierres de este descriptor en la prueba se asocian al token.
        fd_token = closer.register_fd(fd, 'fd')
        pread_result = sha256_pread_v2(fd)
        pos_after = os.lseek(fd, 0, os.SEEK_CUR)
        offset_preserved = (pos_after == 0)
        sha_canon, canon_size, canon_err = sha256_canonical(str(fixture_path))
        # Verificaciones completas
        checks = []
        # C3: ZERO_SIZE es legitimo (archivo vacio), pero nuestros fixtures
        # tienen contenido, asi que esperamos COMPLETE. Si llega ZERO_SIZE,
        # es inesperado para nuestros fixtures.
        if not pread_result.is_pass():
            checks.append("pread_status={0}".format(pread_result.status))
        elif pread_result.status == 'ZERO_SIZE':
            # Para nuestros fixtures (que si tienen contenido), ZERO_SIZE es anomalia
            checks.append("pread_status=ZERO_SIZE inesperado para fixture con contenido")
        if not offset_preserved:
            checks.append("offset_preserved=False pos={0}".format(pos_after))
        if canon_err is not None:
            checks.append("canon_error={0}".format(canon_err))
        elif pread_result.hex_digest is None:
            checks.append("pread_hash=None")
        elif pread_result.hex_digest != sha_canon:
            checks.append("hashes_differ pread={0} canon={1}".format(
                (pread_result.hex_digest or '')[:16], (sha_canon or '')[:16]))
        if canon_size != pread_result.bytes_read:
            checks.append("sizes_differ canon={0} pread={1}".format(
                canon_size, pread_result.bytes_read))
        close_err = closer.close_fd(fd, 'fd', token=fd_token)
        fd = None
        fd_token = None
        if close_err is not None:
            checks.append("cierre_fd_fallo errno={0}".format(close_err.errno))
        if checks:
            return (Result.FAIL, "; ".join(checks), closer.errors)
        return (Result.PASS,
                "pread_status={0} sha={1}..., canon_sha={2}..., offset_ok=True, sizes_match=True".format(
                    pread_result.status, pread_result.hex_digest[:16], sha_canon[:16]),
                closer.errors)
    finally:
        if fd is not None:
            closer.close_fd(fd, 'fd_finally', token=fd_token)


def test_t14_pread_coexists_with_soundfile(np, sf, fixture_path):
    """T14: pread y SoundFile(fd, closefd=False) coexisten sin conflicto (C2 — v0.2.1).

    Secuencia (11 pasos conforme al requerimiento):
    1. Apertura del descriptor original.
    2. Calculo inicial del SHA-256 mediante os.pread().
    3. Apertura de SoundFile sobre ese mismo descriptor con closefd=False.
    4. Lectura de bloques mediante SoundFile.
    5. Repeticion del SHA-256 mediante os.pread() mientras SoundFile permanece abierto.
    6. Comparacion de los hashes.
    7. Lecturas adicionales de SoundFile.
    8. Comprobacion de que el contenido decodificado continua siendo identico al esperado.
    9. Cierre explicito de SoundFile.
    10. Verificacion de que el descriptor original continua abierto.
    11. Cierre explicito del descriptor por su propietario.

    CORRECCION C2.2: cuando una comprobacion falle y no sea posible continuar,
    las comprobaciones restantes se registran como "no realizadas".
    CORRECCION C2.3: no declara PASS si falta cualquier comprobacion.
    CORRECCION C2.4: los cierres de recursos se intentan incluso ante retornos anticipados.
    CORRECCION C2.5: no oculta fallos de cierre (C4: registrados en closer).
    CORRECCION C2.6: diferencia comprobacion superada / fallida / no ejecutada.

    NO verifica coherencia de captura frente a escritores concurrentes.
    """
    closer = CloseErrorLogger()
    fd = None
    fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    sfile = None
    checks_status = []  # Lista de (name, status, detail) donde status ∈ {OK, FAIL, NOT_DONE}

    # Lista de todas las comprobaciones obligatorias (en orden)
    ALL_CHECKS = [
        '01_open_fd',
        '02_sha_before_pread',
        '02b_pread_did_not_move_offset',
        '03_soundfile_open',
        '04_read_block1',
        '05_sha_during_pread',
        '06_hashes_match',
        '07_seek_read_block2',
        '08_blocks_identical',
        '09_soundfile_close',
        '10_fd_alive_after_soundfile_close',
        '11_fd_close',
    ]
    checks_done = set()

    def record_check(name, status, detail=""):
        """Registra una comprobacion. status ∈ {OK, FAIL, NOT_DONE}."""
        checks_status.append((name, status, detail))
        checks_done.add(name)

    def mark_remaining_not_done(failed_at, reason):
        """C2.2: marca comprobaciones restantes como NOT_DONE."""
        idx = ALL_CHECKS.index(failed_at)
        for chk in ALL_CHECKS[idx + 1:]:
            if chk not in checks_done:
                record_check(chk, 'NOT_DONE', "no realizada porque {0} fallo".format(failed_at))

    try:
        # 1. Apertura del descriptor original
        try:
            fd = os.open(str(fixture_path), os.O_RDONLY | os.O_NOFOLLOW)
            # C4 (v0.2.5): registrar la propiedad de la apertura; el cierre
            # de este descriptor se asocia al token en toda la prueba.
            fd_token = closer.register_fd(fd, 'fd')
            st_open = os.fstat(fd)
            record_check('01_open_fd', 'OK', "fd={0} size={1}".format(fd, st_open.st_size))
        except OSError as exc:
            record_check('01_open_fd', 'FAIL', "errno={0}: {1}".format(exc.errno, os.strerror(exc.errno)))
            mark_remaining_not_done('01_open_fd', "apertura fd")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 2. Calculo inicial del SHA-256 mediante os.pread()
        try:
            pread_before = sha256_pread_v2(fd)
            record_check('02_sha_before_pread',
                         'OK' if pread_before.is_pass() else 'FAIL',
                         pread_before.summary())
            sha_before = pread_before.hex_digest
            if not pread_before.is_pass():
                mark_remaining_not_done('02_sha_before_pread', "sha_before")
                return (Result.FAIL, format_checks(checks_status), closer.errors)
        except Exception as exc:
            record_check('02_sha_before_pread', 'FAIL', "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('02_sha_before_pread', "sha_before")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 2b. Verificar que pread no movio el offset del fd
        pos_after_pread = os.lseek(fd, 0, os.SEEK_CUR)
        if pos_after_pread == 0:
            record_check('02b_pread_did_not_move_offset', 'OK', "pos={0}".format(pos_after_pread))
        else:
            record_check('02b_pread_did_not_move_offset', 'FAIL', "pos={0} (esperado 0)".format(pos_after_pread))
            mark_remaining_not_done('02b_pread_did_not_move_offset', "offset movido por pread")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 3. Apertura de SoundFile sobre ese mismo descriptor con closefd=False
        try:
            sfile = sf.SoundFile(fd, mode='r', closefd=False)
            record_check('03_soundfile_open', 'OK', "sr={0} ch={1} fr={2}".format(
                sfile.samplerate, sfile.channels, sfile.frames))
        except Exception as exc:
            record_check('03_soundfile_open', 'FAIL',
                         "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('03_soundfile_open', "apertura SoundFile")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 4. Lectura de bloques mediante SoundFile
        try:
            block1 = sfile.read(500, dtype='float64', always_2d=True)
            if block1.shape == (500, CHANNELS):
                record_check('04_read_block1', 'OK', "shape={0}".format(block1.shape))
            else:
                record_check('04_read_block1', 'FAIL', "shape={0} esperado (500, {1})".format(block1.shape, CHANNELS))
                mark_remaining_not_done('04_read_block1', "lectura block1")
                return (Result.FAIL, format_checks(checks_status), closer.errors)
        except Exception as exc:
            record_check('04_read_block1', 'FAIL',
                         "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('04_read_block1', "lectura block1")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 5. Repeticion del SHA-256 mediante os.pread() mientras SoundFile esta abierto
        try:
            pread_during = sha256_pread_v2(fd)
            record_check('05_sha_during_pread',
                         'OK' if pread_during.is_pass() else 'FAIL',
                         pread_during.summary())
            sha_during = pread_during.hex_digest
            if not pread_during.is_pass():
                mark_remaining_not_done('05_sha_during_pread', "sha_during")
                return (Result.FAIL, format_checks(checks_status), closer.errors)
        except Exception as exc:
            record_check('05_sha_during_pread', 'FAIL', "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('05_sha_during_pread', "sha_during")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 6. Comparacion de los hashes
        if sha_before is not None and sha_during is not None and sha_before == sha_during:
            record_check('06_hashes_match', 'OK', "hashes idénticos")
        else:
            record_check('06_hashes_match', 'FAIL',
                         "before={0} during={1}".format(
                             (sha_before or '')[:16], (sha_during or '')[:16]))
            mark_remaining_not_done('06_hashes_match', "hashes no coinciden")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 7. Lecturas adicionales de SoundFile (seek + read)
        try:
            sfile.seek(0)
            block2 = sfile.read(500, dtype='float64', always_2d=True)
            if block2.shape == (500, CHANNELS):
                record_check('07_seek_read_block2', 'OK', "shape={0}".format(block2.shape))
            else:
                record_check('07_seek_read_block2', 'FAIL', "shape={0}".format(block2.shape))
                mark_remaining_not_done('07_seek_read_block2', "lectura block2")
                return (Result.FAIL, format_checks(checks_status), closer.errors)
        except Exception as exc:
            record_check('07_seek_read_block2', 'FAIL',
                         "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('07_seek_read_block2', "lectura block2")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 8. Comprobacion de que el contenido decodificado es identico
        try:
            blocks_match = bool(np.array_equal(block1, block2))
            if blocks_match:
                record_check('08_blocks_identical', 'OK', "block1 == block2")
            else:
                record_check('08_blocks_identical', 'FAIL', "block1 != block2")
                mark_remaining_not_done('08_blocks_identical', "bloques no identicos")
                return (Result.FAIL, format_checks(checks_status), closer.errors)
        except Exception as exc:
            record_check('08_blocks_identical', 'FAIL',
                         "{0}: {1}".format(type(exc).__name__, str(exc)[:80]))
            mark_remaining_not_done('08_blocks_identical', "comparacion bloques")
            return (Result.FAIL, format_checks(checks_status), closer.errors)

        # 9. Cierre explicito de SoundFile
        # C5 (v0.2.11): KI durante este cierre => resultado incierto, sin
        # reintento (sfile=None); el cierre del fd se intenta en el finally
        # y la interrupcion se propaga tras la limpieza.
        try:
            close_sf_err = closer.close_soundfile(sfile, 'sfile')
        except KeyboardInterrupt:
            sfile = None
            raise
        sfile = None
        if close_sf_err is None:
            record_check('09_soundfile_close', 'OK', "cierre OK")
        else:
            record_check('09_soundfile_close', 'FAIL',
                         "{0}: {1}".format(type(close_sf_err).__name__, str(close_sf_err)[:80]))
            # Continuamos para intentar verificar fd_alive, pero el test va a fallar

        # 10. Verificacion de que el descriptor original continua abierto
        # ESTA COMPROBACION ES OBLIGATORIA — se ejecuta siempre tras sfile.close()
        try:
            st_after = os.fstat(fd)
            fd_alive = (st_after.st_ino == st_open.st_ino
                        and st_after.st_dev == st_open.st_dev)
            if fd_alive:
                record_check('10_fd_alive_after_soundfile_close', 'OK',
                             "st_ino_match=True st_dev_match=True")
            else:
                record_check('10_fd_alive_after_soundfile_close', 'FAIL',
                             "st_ino_match={0} st_dev_match={1}".format(
                                 st_after.st_ino == st_open.st_ino,
                                 st_after.st_dev == st_open.st_dev))
        except OSError as exc:
            record_check('10_fd_alive_after_soundfile_close', 'FAIL',
                         "OSError errno={0}: {1}".format(exc.errno, os.strerror(exc.errno)))

        # 11. Cierre explicito del descriptor por el propietario
        # C4 (v0.2.5): asociado al token de la apertura registrada.
        close_err = closer.close_fd(fd, 'fd', token=fd_token)
        fd = None
        fd_token = None
        if close_err is None:
            record_check('11_fd_close', 'OK', "cierre OK")
        else:
            record_check('11_fd_close', 'FAIL',
                         "errno={0}".format(close_err.errno))

        # Determinar resultado final: PASS solo si TODAS las comprobaciones son OK
        any_fail = any(s == 'FAIL' for _, s, _ in checks_status)
        any_not_done = any(s == 'NOT_DONE' for _, s, _ in checks_status)
        if any_fail or any_not_done:
            return (Result.FAIL, format_checks(checks_status), closer.errors)
        return (Result.PASS, format_checks(checks_status), closer.errors)
    finally:
        # C2.4 / C5 / C4: intento de cierre conservador ante excepcion o interrupcion
        # C4 (v0.2.5): el cierre conservador tambien se asocia al token.
        # C5 (v0.2.11): la KI durante el cierre de SoundFile no impide
        # intentar el cierre del descriptor propietario; se propaga tras
        # los intentos de limpieza.
        if _close_pair_conserving_interrupt(closer, sfile, 'sfile_finally',
                                            fd, 'fd_finally', fd_token):
            raise KeyboardInterrupt()


def format_checks(checks_status):
    """Formatea la lista de comprobaciones para el detalle del resultado."""
    parts = []
    for name, status, detail in checks_status:
        marker = {'OK': '+', 'FAIL': 'X', 'NOT_DONE': '-'}[status]
        parts.append("{0}[{1}] {2}".format(marker, name, detail[:50]))
    return "; ".join(parts)


def test_t15_libsndfile_error_raised(np, sf, fixture_dir):
    """T15: SoundFile rechaza fd invalido lanzando LibsndfileError (no OSError).

    Verifica:
    - Al pasar un fd de directorio a SoundFile(fd, closefd=False), se lanza
      sf.LibsndfileError (no OSError, no Exception genérica).
    - Cierre exitoso del fd de directorio (C4: errores registrados).
    """
    closer = CloseErrorLogger()
    dir_fd = None
    dir_fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    try:
        dir_fd = os.open(str(fixture_dir), os.O_RDONLY)
        # C4 (v0.2.5): registrar la propiedad de la apertura; los cierres
        # de este descriptor se asocian al token en toda la prueba.
        dir_fd_token = closer.register_fd(dir_fd, 'dir_fd')
        try:
            sfile = sf.SoundFile(dir_fd, mode='r', closefd=False)
            # Si llegamos aqui, no fallo como esperabamos
            # C5 (v0.2.11): la KI durante el cierre de SoundFile no impide
            # intentar el cierre del fd de directorio; se propaga tras la
            # limpieza (el finally conserva el intento por token).
            if _close_pair_conserving_interrupt(
                    closer, sfile, 'sfile_unexpected',
                    dir_fd, 'dir_fd', dir_fd_token):
                dir_fd = None
                dir_fd_token = None
                raise KeyboardInterrupt()
            dir_fd = None
            dir_fd_token = None
            return (Result.FAIL, "SoundFile acepto fd de directorio (no esperado)",
                    closer.errors)
        except sf.LibsndfileError as exc:
            close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
            dir_fd = None
            dir_fd_token = None
            detail = "LibsndfileError capturada: {0}".format(str(exc)[:80])
            if close_err is not None:
                detail += "; cierre_dir_fd_fallo errno={0}".format(close_err.errno)
                return (Result.FAIL, detail + " (cierre fallo)", closer.errors)
            return (Result.PASS, detail, closer.errors)
        except OSError as exc:
            close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
            dir_fd = None
            dir_fd_token = None
            return (Result.FAIL,
                    "Se lanzo OSError en lugar de LibsndfileError: errno={0}".format(exc.errno),
                    closer.errors)
        except Exception as exc:
            close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
            dir_fd = None
            dir_fd_token = None
            return (Result.FAIL,
                    "Excepcion no esperada: {0}: {1}".format(type(exc).__name__, str(exc)[:80]),
                    closer.errors)
    finally:
        if dir_fd is not None:
            closer.close_fd(dir_fd, 'dir_fd_finally', token=dir_fd_token)


def test_t16_fd_survives_closefd_false_failure(np, sf, fixture_dir):
    """T16: con closefd=False, el fd permanece abierto tras un fallo de SoundFile.

    Verifica:
    - Tras un fallo de SoundFile(fd, closefd=False), el fd sigue siendo utilizable
      (fstat funciona).
    - Cierre exitoso del fd por el propietario (C4: errores registrados).
    """
    closer = CloseErrorLogger()
    dir_fd = None
    dir_fd_token = None  # C4 (v0.2.5): token de propiedad de esta apertura
    try:
        dir_fd = os.open(str(fixture_dir), os.O_RDONLY)
        # C4 (v0.2.5): registrar la propiedad de la apertura; los cierres
        # de este descriptor se asocian al token en toda la prueba.
        dir_fd_token = closer.register_fd(dir_fd, 'dir_fd')
        try:
            sfile = sf.SoundFile(dir_fd, mode='r', closefd=False)
            # Si llegamos aqui, no fallo como esperabamos
            # C5 (v0.2.11): la KI durante el cierre de SoundFile no impide
            # intentar el cierre del fd de directorio; se propaga tras la
            # limpieza (el finally conserva el intento por token).
            if _close_pair_conserving_interrupt(
                    closer, sfile, 'sfile_unexpected',
                    dir_fd, 'dir_fd', dir_fd_token):
                dir_fd = None
                dir_fd_token = None
                raise KeyboardInterrupt()
            dir_fd = None
            dir_fd_token = None
            return (Result.FAIL, "SoundFile acepto fd de directorio (no esperado)",
                    closer.errors)
        except sf.LibsndfileError:
            pass  # Esperado
        except Exception as exc:
            close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
            dir_fd = None
            dir_fd_token = None
            return (Result.FAIL,
                    "Excepcion no esperada: {0}: {1}".format(type(exc).__name__, str(exc)[:80]),
                    closer.errors)

        # Verificar que el fd sigue abierto
        fd_alive = False
        try:
            os.fstat(dir_fd)
            fd_alive = True
        except OSError as exc:
            if exc.errno == errno.EBADF:
                detail = "fd cerrado por libsndfile pese a closefd=False (EBADF)"
            else:
                detail = "fstat errno={0}: {1}".format(exc.errno, os.strerror(exc.errno))
            close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
            dir_fd = None
            dir_fd_token = None
            if close_err is not None:
                detail += "; cierre fallo errno={0}".format(close_err.errno)
            return (Result.FAIL, detail, closer.errors)

        # Cierre exitoso del fd por el propietario
        # C4 (v0.2.5): asociado al token de la apertura registrada.
        close_err = closer.close_fd(dir_fd, 'dir_fd', token=dir_fd_token)
        dir_fd = None
        dir_fd_token = None
        if close_err is not None:
            return (Result.FAIL,
                    "cierre fd fallo: errno={0}".format(close_err.errno),
                    closer.errors)
        return (Result.PASS, "fd sobrevive al fallo de SoundFile con closefd=False",
                closer.errors)
    finally:
        if dir_fd is not None:
            closer.close_fd(dir_fd, 'dir_fd_finally', token=dir_fd_token)


# ----------------------------------------------------------------------------
# Orquestador por entorno
# ----------------------------------------------------------------------------

TEST_FUNCTIONS = {
    'T11': test_t11_soundfile_fd_closefd_false,
    'T12': test_t12_pread_works,
    'T13': test_t13_pread_hash_matches_canonical,
    'T14': test_t14_pread_coexists_with_soundfile,
}


def run_environment(np, sf, env_name, env_parent_dir, results, run_id, interrupt_flag):
    """Ejecuta todas las pruebas en un entorno dado.

    Crea un subdirectorio exclusivo por ejecucion dentro de env_parent_dir.
    interrupt_flag es una lista mutable que el llamador puede usar para señalizar
    interrupcion.
    """
    run_dir = Path(env_parent_dir) / ("run-{0}".format(run_id))
    print("\n=== Entorno {0}: {1} ===".format(env_name, run_dir))

    # C1: crear directorio de ejecucion exclusivo (anclado)
    try:
        safe_makedirs_exclusive_anchored(run_dir)
    except KeyboardInterrupt:
        # C5 (v0.2.5): interrupcion durante la creacion del directorio de
        # ejecucion. Coherente con la ruta OSError: todas las pruebas del
        # entorno se registran NOT_EXECUTED (nunca PASS, no se inventan
        # resultados), el flag global de interrupcion se setea y los
        # errores de cierre acumulados se conservan en la primera entrada.
        interrupt_flag[0] = True
        msg = ("KeyboardInterrupt durante creacion del directorio de "
               "ejecucion; prueba no ejecutada")
        close_errs = _drain_close_error_sink()
        first_entry = True
        for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED, 'detail': msg,
                                'close_errors': close_errs if first_entry else []})
                first_entry = False
        for tid in ['T15', 'T16']:
            results.append({'env': env_name, 'test': tid, 'fixture': None,
                            'status': Result.NOT_EXECUTED, 'detail': msg,
                            'close_errors': []})
        # C4-B (v0.2.9): los errores conservados quedan atribuidos a la
        # primera entrada; no se duplican en environment_close_errors.
        _mark_close_errors_attributed(close_errs)
        print("  [NOT_EXECUTED] {0}".format(msg))
        return None  # Sin run_dir creado
    except OSError as exc:
        msg = "No se pudo crear directorio de ejecucion {0}: errno={1} ({2})".format(
            run_dir, exc.errno, os.strerror(exc.errno) if exc.errno else str(exc))
        print("  [NOT_EXECUTED] {0}".format(msg))
        for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED, 'detail': msg,
                                'close_errors': []})
        for tid in ['T15', 'T16']:
            results.append({'env': env_name, 'test': tid, 'fixture': None,
                            'status': Result.NOT_EXECUTED, 'detail': msg,
                            'close_errors': []})
        return None  # Sin run_dir creado

    # Generar fixtures
    fixtures = {}
    for idx, (fname, subtype) in enumerate(FIXTURE_SPECS):
        # C5 (v0.2.4): interrupcion previa: el fixture no se crea y las
        # pruebas asociadas quedan NOT_EXECUTED (no se inventan resultados).
        if interrupt_flag and interrupt_flag[0]:
            for rest_fname, _ in FIXTURE_SPECS[idx:]:
                for tid in ['T11', 'T12', 'T13', 'T14']:
                    results.append({'env': env_name, 'test': tid, 'fixture': rest_fname,
                                    'status': Result.NOT_EXECUTED,
                                    'detail': "interrupcion previa; fixture no creado; prueba no ejecutada",
                                    'close_errors': []})
            print("  fixture {0}: NOT_EXECUTED - interrupcion previa".format(fname))
            break
        closer = CloseErrorLogger()  # Closer dedicado para fixture creation
        try:
            fpath, ferr = create_fixture(np, sf, run_dir, fname, subtype, closer)
        except KeyboardInterrupt:
            # C5 (v0.2.4): interrupcion durante la creacion del fixture.
            # Se propaga al estado global (interrupt_flag), se registra
            # ERROR (nunca PASS), se conservan los errores de cierre y las
            # pruebas asociadas posteriores quedan NOT_EXECUTED.
            # C4-B (v0.2.9): los errores drenados ya estan en el acumulador
            # persistente (incorporados al registrarse); no se pierden.
            for entry in _drain_close_error_sink():
                closer.errors.append(entry)
            interrupt_flag[0] = True
            print("  fixture {0}: ERROR - KeyboardInterrupt durante creacion".format(fname))
            results.append({'env': env_name, 'test': 'T11', 'fixture': fname,
                            'status': Result.ERROR,
                            'detail': "KeyboardInterrupt durante creacion de fixture; no se declara PASS",
                            'close_errors': closer.errors})
            _mark_close_errors_attributed(closer.errors)  # C4-B (v0.2.9)
            for tid in ['T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED,
                                'detail': "interrupcion durante creacion de fixture; prueba no ejecutada",
                                'close_errors': []})
            for rest_fname, _ in FIXTURE_SPECS[idx + 1:]:
                for tid in ['T11', 'T12', 'T13', 'T14']:
                    results.append({'env': env_name, 'test': tid, 'fixture': rest_fname,
                                    'status': Result.NOT_EXECUTED,
                                    'detail': "interrupcion durante creacion de fixture anterior; prueba no ejecutada",
                                    'close_errors': []})
            break
        if fpath is None:
            print("  ERROR creando fixture {0}: {1}".format(fname, ferr))
            for tid in ['T11', 'T12', 'T13', 'T14']:
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.ERROR,
                                'detail': "fixture creation failed: {0}".format(ferr),
                                'close_errors': closer.errors})
            _mark_close_errors_attributed(closer.errors)  # C4-B (v0.2.9)
        else:
            fixtures[fname] = fpath
            # C4-B (v0.2.9): los errores de cierre de la creacion del fixture
            # ya estan conservados en el acumulador persistente (incorporados
            # al registrarse via _append_error -> _record_close_error) y se
            # reportan al nivel de entorno; re-registrarlos aqui duplicaria
            # entradas en el acumulador y en el informe.
            print("  fixture creado: {0} ({1} bytes) close_errors={2}".format(
                fpath.name, fpath.stat().st_size, len(closer.errors)))

    # Ejecutar pruebas T11-T14 sobre cada fixture
    for fname, fpath in fixtures.items():
        print("\n  --- {0} ({1}) ---".format(fname, fpath.name))
        for tid, test_fn in TEST_FUNCTIONS.items():
            if interrupt_flag and interrupt_flag[0]:
                # C5: si ya hubo interrupcion, marcar como NOT_EXECUTED sin inventar
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.NOT_EXECUTED,
                                'detail': "interrupcion previa; prueba no ejecutada",
                                'close_errors': []})
                print("  {0}: NOT_EXECUTED - interrupcion previa".format(tid))
                continue
            try:
                ret = test_fn(np, sf, fpath)
                if len(ret) == 3:
                    status, detail, close_errors = ret
                else:
                    status, detail = ret
                    close_errors = []
            except KeyboardInterrupt:
                # C5: interrupcion durante esta prueba
                # C4 (v0.2.3): conservar errores de cierre acumulados,
                # no devolver close_errors: [] si hubo errores.
                # C4-B (v0.2.9): el drenaje no pierde (acumulador persistente)
                # y los errores se atribuyen al resultado (sin duplicar).
                ki_close_errors = _drain_close_error_sink()
                results.append({'env': env_name, 'test': tid, 'fixture': fname,
                                'status': Result.ERROR,
                                'detail': "KeyboardInterrupt: prueba interrumpida, "
                                          "no se declara PASS",
                                'close_errors': ki_close_errors})
                _mark_close_errors_attributed(ki_close_errors)
                print("  {0}: ERROR - KeyboardInterrupt".format(tid))
                interrupt_flag[0] = True
                # No propagar inmediatamente; dejar que el bucle marque las
                # siguientes como NOT_EXECUTED
                continue
            except Exception as exc:
                status = Result.ERROR
                detail = "{0}: {1}\n{2}".format(
                    type(exc).__name__, str(exc)[:120],
                    traceback.format_exc()[-400:])
                close_errors = _drain_close_error_sink()
            results.append({'env': env_name, 'test': tid, 'fixture': fname,
                            'status': status, 'detail': detail,
                            'close_errors': close_errors})
            _mark_close_errors_attributed(close_errors)  # C4-B (v0.2.9)
            print("  {0}: {1} - {2}".format(tid, status, str(detail)[:70]))

    # Ejecutar T15 y T16 (usan directorio, no fixture)
    print("\n  --- pruebas con fd de directorio (T15, T16) ---")
    for tid, test_fn in [('T15', test_t15_libsndfile_error_raised),
                         ('T16', test_t16_fd_survives_closefd_false_failure)]:
        if interrupt_flag and interrupt_flag[0]:
            results.append({'env': env_name, 'test': tid, 'fixture': None,
                            'status': Result.NOT_EXECUTED,
                            'detail': "interrupcion previa; prueba no ejecutada",
                            'close_errors': []})
            print("  {0}: NOT_EXECUTED - interrupcion previa".format(tid))
            continue
        try:
            ret = test_fn(np, sf, run_dir)
            if len(ret) == 3:
                status, detail, close_errors = ret
            else:
                status, detail = ret
                close_errors = []
        except KeyboardInterrupt:
            # C5: interrupcion durante esta prueba
            # C4 (v0.2.3): conservar errores de cierre, no [] fijo.
            # C4-B (v0.2.9): el drenaje no pierde y se atribuye al resultado.
            ki_close_errors = _drain_close_error_sink()
            results.append({'env': env_name, 'test': tid, 'fixture': None,
                            'status': Result.ERROR,
                            'detail': "KeyboardInterrupt: prueba interrumpida, "
                                      "no se declara PASS",
                            'close_errors': ki_close_errors})
            _mark_close_errors_attributed(ki_close_errors)
            print("  {0}: ERROR - KeyboardInterrupt".format(tid))
            interrupt_flag[0] = True
            continue
        except Exception as exc:
            status = Result.ERROR
            detail = "{0}: {1}\n{2}".format(
                type(exc).__name__, str(exc)[:120],
                traceback.format_exc()[-400:])
            close_errors = _drain_close_error_sink()
        results.append({'env': env_name, 'test': tid, 'fixture': None,
                        'status': status, 'detail': detail,
                        'close_errors': close_errors})
        _mark_close_errors_attributed(close_errors)  # C4-B (v0.2.9)
        print("  {0}: {1} - {2}".format(tid, status, str(detail)[:70]))

    return run_dir


# ----------------------------------------------------------------------------
# Recoleccion de metadatos del entorno
# ----------------------------------------------------------------------------

def collect_environment_metadata(np, sf):
    """Recolecta versiones de Python, SoundFile, libsndfile, arquitectura, kernel, SO.

    Nota: los except Exception en la obtencion de subtipos disponibles son
    defensivos: si libsndfile falla al listar subtipos, no es fatal para
    el diagnostico. No son except Exception: pass; el resultado se documenta
    como lista vacia y se reporta explicitamente en el metadata.
    """
    bits = struct.calcsize("P") * 8
    wav_subtypes = []
    wav_subtypes_error = None
    try:
        wav_subtypes = list(sf.available_subtypes('WAV').keys())
    except Exception as exc:
        wav_subtypes_error = "{0}: {1}".format(type(exc).__name__, str(exc)[:80])
    flac_subtypes = []
    flac_subtypes_error = None
    try:
        flac_subtypes = list(sf.available_subtypes('FLAC').keys())
    except Exception as exc:
        flac_subtypes_error = "{0}: {1}".format(type(exc).__name__, str(exc)[:80])
    return {
        'script_name': SCRIPT_NAME,
        'script_version': SCRIPT_VERSION,
        'python_version': sys.version,
        'python_bits': bits,
        'platform': sys.platform,
        'machine': platform.machine(),
        'processor': platform.processor(),
        'system': platform.system(),
        'release': platform.release(),
        'kernel_version': platform.uname().release,
        'uname_version': platform.uname().version,
        'soundfile_version': getattr(sf, '__version__', 'unknown'),
        'libsndfile_version': getattr(sf, '__libsndfile_version__', 'unknown'),
        'numpy_version': getattr(np, '__version__', 'unknown'),
        'wav_subtypes_available': wav_subtypes,
        'wav_subtypes_error': wav_subtypes_error,
        'flac_subtypes_available': flac_subtypes,
        'flac_subtypes_error': flac_subtypes_error,
        'home_dir': str(Path.home()),
        'cwd': os.getcwd(),
        'uid': os.getuid() if hasattr(os, 'getuid') else None,
        'gid': os.getgid() if hasattr(os, 'getgid') else None,
        'euid': os.geteuid() if hasattr(os, 'geteuid') else None,
        'o_path_available': hasattr(os, 'O_PATH'),
        'o_directory_available': hasattr(os, 'O_DIRECTORY'),
    }


# ----------------------------------------------------------------------------
# C5/C7: escritura del informe JSON con manejo robusto
# ----------------------------------------------------------------------------

def write_report_json_robust(report_path, report_dict):
    """Escribe el informe JSON en disco de forma exclusiva y completa (C1.7 + C7).

    CORRECCION C7: sustituye escritura unica os.write por procedimiento que
    gestiona escrituras parciales hasta completar todos los bytes.
    CORRECCION C7.2: si write devuelve 0 antes de completar, registra error.
    CORRECCION C7.3: cierra el descriptor y conserva errores de cierre.
    CORRECCION C7.4: si el informe no se completo, devuelve codigo != 0.
    CORRECCION C7.5: no sobrescribe informe preexistente (O_CREAT|O_EXCL).

    CORRECCION C1 (v0.2.3): eliminada la creacion por ruta completa
    (os.open(str(report_path))). El informe se crea como provisional
    exclusivo y anclado (os.open con dir_fd sobre el descriptor del
    directorio padre).

    CORRECCION C1 (v0.2.4): la publicacion se realiza con os.link usando
    nombres RELATIVOS a los descriptores del directorio (src_dir_fd /
    dst_dir_fd), que es atómica y no sobrescribe: si el destino ya
    existe, falla con EEXIST y no se sobrescribe. Se elimina el
    comprobacion previa de existencia + rename (carrera TOCTOU). Si el
    mecanismo anclado no esta disponible (NotImplementedError u otro
    error), se conserva el provisional y se reporta explicitamente que
    el informe no pudo publicarse. Los errores de cierre del descriptor
    del directorio se conservan y se reportan.

    CORRECCION C5 (v0.2.3/v0.2.4): se verifica fsync + tamano tras la
    escritura antes de cerrar, se verifica el cierre (identidad del
    descriptor) y el estado del informe se informa explicitamente:
    publicado, o provisional/incompleto/no publicado con el motivo.

    Retorna (ok, error_or_None, close_error_or_None).
    """
    try:
        check_no_symlink_in_path(report_path.parent)
    except OSError as exc:
        return False, "symlink en directorio padre del informe: {0}".format(exc), None

    try:
        content = json.dumps(report_dict, indent=2, ensure_ascii=False).encode('utf-8')
    except Exception as exc:
        return False, "json.dumps fallo: {0}: {1}".format(type(exc).__name__, str(exc)[:80]), None

    # C1 (v0.2.3): apertura anclada del directorio padre del informe.
    parent_fd, anchor_msg = safe_open_dir_anchored(str(report_path.parent))
    if parent_fd < 0:
        return False, "apertura anclada del directorio del informe fallo: {0}".format(anchor_msg), None

    tmp_name = report_path.name + ".tmp"
    close_err = None
    result = None  # resultado final; se fija antes de retornar (C4, v0.2.4)
    try:
        try:
            tmp_fd = os.open(tmp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            if exc.errno == errno.EEXIST:
                return False, ("informe provisional ya existe (no se sobrescribe): "
                               "{0}".format(report_path.parent / tmp_name)), None
            return False, "os.open anclado errno={0}: {1}".format(
                exc.errno, os.strerror(exc.errno)), None

        closer = CloseErrorLogger()
        tmp_token = closer.register_fd(tmp_fd, 'report_tmp_fd')
        err = None
        try:
            # C7.1: bucle de escritura hasta completar
            total = len(content)
            written = 0
            zero_write_count = 0
            while written < total:
                try:
                    n = os.write(tmp_fd, content[written:])
                except OSError as exc:
                    err = "write errno={0}: {1} en offset={2}".format(
                        exc.errno, os.strerror(exc.errno), written)
                    break
                if n == 0:
                    # C7.2: write devolvio 0 antes de completar
                    zero_write_count += 1
                    if zero_write_count > 3:
                        err = "write devolvio 0 repetidamente en offset={0} de {1}".format(
                            written, total)
                        break
                else:
                    zero_write_count = 0
                written += n
            if err is None and written != total:
                err = "escritura incompleta: written={0} total={1}".format(written, total)
            if err is None:
                # C5 (v0.2.3): flush al disco y verificacion del tamano
                try:
                    os.fsync(tmp_fd)
                except OSError as exc:
                    err = "fsync errno={0}: {1}".format(exc.errno, os.strerror(exc.errno))
            if err is None:
                try:
                    st = os.fstat(tmp_fd)
                    if st.st_size != total:
                        err = "verificacion de tamano fallo: st_size={0} != total={1}".format(
                            st.st_size, total)
                except OSError as exc:
                    err = "fstat errno={0}: {1}".format(exc.errno, os.strerror(exc.errno))
        finally:
            # C7.3: cerrar el descriptor y conservar errores de cierre.
            # C4-B (v0.2.10): close_fd ya registra el error como propietario
            # (_append_error -> _record_close_error); un registro adicional
            # aqui duplicaria el mismo evento en el acumulador con otro id.
            # El detalle se conserva en el retorno via close_err
            # (closer.summary()) y en el acumulador persistente.
            exc_close = closer.close_fd(tmp_fd, 'report_tmp_fd', token=tmp_token)
        close_err = closer.summary()

        result = None
        if err is not None:
            # C5 (v0.2.4): informe incompleto: no se publica; queda provisional.
            result = (False, ("informe incompleto, no publicado; provisional queda en "
                              "disco: {0} ({1})".format(report_path.parent / tmp_name, err)),
                      close_err)
        else:
            # C1 (v0.2.4): publicacion atómica sin sobrescritura. Se usa
            # os.link con nombres RELATIVOS a los descriptores del directorio
            # (src_dir_fd/dst_dir_fd): la operacion es atoma y falla con
            # EEXIST si el destino ya existe. NO hay comprobacion previa de
            # existencia ni rename (carrera TOCTOU). Si el mecanismo no
            # esta disponible, se conserva el provisional y se reporta
            # explicitamente que el informe no pudo publicarse.
            try:
                os.link(tmp_name, report_path.name,
                        src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno == errno.EEXIST:
                    result = (False, ("informe preexistente; no se sobrescribe: {0} "
                                      "(provisional queda en disco)".format(report_path)),
                              close_err)
                else:
                    result = (False, ("informe no publicado (link errno={0}: {1}); "
                                      "provisional queda en disco".format(
                                          exc.errno, os.strerror(exc.errno))),
                              close_err)
            except NotImplementedError:
                result = (False, ("informe no publicado: enlace duro anclado no "
                                  "disponible en este sistema; provisional queda en "
                                  "disco: {0}").format(report_path.parent / tmp_name),
                          close_err)
            else:
                # Se elimina solo el provisional creado por este proceso
                # (origen acreditado: O_CREAT|O_EXCL anclado en esta llamada)
                # tras la publicacion exitosa. Un fallo del unlink no
                # invalida la publicacion, pero se conserva para trazabilidad.
                try:
                    os.unlink(tmp_name, dir_fd=parent_fd)
                except OSError as exc:
                    _record_close_error({"label": 'report_tmp_unlink',
                                         "errno": exc.errno,
                                         "strerror": os.strerror(exc.errno)})
                result = (True, None, close_err)
    finally:
        # C4 (v0.2.4): error de cierre del descriptor del directorio
        # conservado y reportado en el resultado del informe.
        exc_parent = _close_fd_tracked(parent_fd, 'report_parent_fd')
        if exc_parent is not None:
            # C4-B (v0.2.10): _close_fd_tracked ya registra el error en el
            # acumulador persistente; un registro adicional aqui duplicaria
            # el mismo evento con otro id. El detalle se conserva en el
            # retorno (parent_close_err se agrega a close_err).
            parent_close_err = "parent_fd close errno={0}: {1}".format(
                exc_parent.errno, os.strerror(exc_parent.errno))
            if result is not None:
                ok, rerr, rcerr = result
                if rcerr:
                    rcerr = rcerr + " | " + parent_close_err
                else:
                    rcerr = parent_close_err
                result = (ok, rerr, rcerr)
        if result is None:
            result = (False, "informe no publicado (excepcion inesperada)", None)
    return result


# ----------------------------------------------------------------------------
# Programa principal
# ----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Diagnostico AudioInput ETAPA 2: SoundFile(fd, closefd=False) + os.pread")
    parser.add_argument('--shared', type=str, default=None,
                        help='Ruta al directorio de almacenamiento compartido Android '
                             '(p. ej. /sdcard/audioinput_diag)')
    parser.add_argument('--output', type=str, default=None,
                        help='Ruta al archivo JSON de salida (por defecto: '
                             '$HOME/.audioinput_diag_etapa2/report-<runid>.json)')
    parser.add_argument('--private-dir', type=str, default=None,
                        help='Directorio padre privado (por defecto: '
                             '$HOME/.audioinput_diag_etapa2)')
    args = parser.parse_args()

    # Directorio privado padre
    if args.private_dir:
        private_parent = Path(args.private_dir)
    else:
        private_parent = Path.home() / '.audioinput_diag_etapa2'

    # Generar run_id unico por ejecucion (C1)
    run_id = make_run_id()

    # C4-B (v0.2.9): reinicia la contabilidad de errores de cierre de esta
    # ejecucion (cola pendiente, acumulador persistente y atribuciones).
    _reset_close_error_accounting()

    # C1: validar que privado y compartido no son el mismo directorio
    shared_parent = Path(args.shared) if args.shared else None
    if shared_parent is not None:
        ok_distinct, distinct_msg = validate_environments_distinct(private_parent, shared_parent)
        if ok_distinct is False:
            print("[FATAL] Conflicto de entornos: {0}".format(distinct_msg))
            sys.exit(2)
        if ok_distinct is None:
            # No se pudo verificar — fallar conservadoramente
            print("[FATAL] No se pudo verificar que privado y compartido sean distintos: {0}".format(distinct_msg))
            sys.exit(2)

    # Crear directorio padre privado si no existe (con verificacion de seguridad)
    try:
        check_no_symlink_in_path(private_parent)
    except OSError as exc:
        print("[FATAL] Symlink en directorio padre privado {0}: errno={1}".format(
            private_parent, exc.errno))
        sys.exit(2)

    if not private_parent.exists():
        # C1 (v0.2.3): creacion de padres anclada (no Path.mkdir por ruta).
        try:
            _ensure_parents_anchored(private_parent)
        except OSError as exc:
            print("[FATAL] No se pudo crear directorio padre privado {0}: {1}".format(
                private_parent, exc))
            sys.exit(2)
    else:
        # C1.6: verificar que el directorio padre existente es seguro
        ok, msg = check_dir_is_safe(private_parent,
                                     expected_uid=os.geteuid() if hasattr(os, 'geteuid') else None)
        if not ok:
            print("[FATAL] Directorio padre privado inseguro: {0}: {1}".format(private_parent, msg))
            sys.exit(2)

    # Si se especifico shared, crear padre compartido con verificacion
    if shared_parent is not None:
        try:
            check_no_symlink_in_path(shared_parent)
        except OSError as exc:
            print("[FATAL] Symlink en directorio padre compartido {0}: errno={1}".format(
                shared_parent, exc.errno))
            sys.exit(2)
        if not shared_parent.exists():
            # C1 (v0.2.3): creacion de padres anclada (no Path.mkdir por ruta).
            try:
                _ensure_parents_anchored(shared_parent)
            except OSError as exc:
                print("[FATAL] No se pudo crear directorio padre compartido {0}: {1}".format(
                    shared_parent, exc))
                sys.exit(2)
        else:
            ok, msg = check_dir_is_safe(shared_parent,
                                        expected_uid=os.geteuid() if hasattr(os, 'geteuid') else None)
            if not ok:
                print("[FATAL] Directorio padre compartido inseguro: {0}: {1}".format(
                    shared_parent, msg))
                sys.exit(2)

    # Informe JSON con run_id unico
    if args.output:
        report_path = Path(args.output)
    else:
        report_path = private_parent / "report-{0}.json".format(run_id)

    # Mensaje inicial
    print("=== Diagnostico AudioInput ETAPA 2 ===")
    print("Script: {0} v{1}".format(SCRIPT_NAME, SCRIPT_VERSION))
    print("Run ID: {0}".format(run_id))
    print("Directorio padre privado: {0}".format(private_parent))
    print("Directorio padre compartido: {0}".format(shared_parent or '(no especificado)'))
    print("Reporte JSON: {0}".format(report_path))
    print()

    # Importar dependencias
    np, sf, dep_errors = _import_dependencies()
    if dep_errors:
        print("[FATAL] Dependencias no disponibles:")
        for k, v in dep_errors.items():
            print("  {0}: {1}".format(k, v))
        print("Instala con: pip install numpy soundfile  (decision del usuario)")
        sys.exit(2)

    # Metadatos del entorno
    try:
        meta = collect_environment_metadata(np, sf)
    except Exception as exc:
        print("[FATAL] No se pudieron recolectar metadatos: {0}".format(exc))
        sys.exit(2)

    print("=== Metadatos del entorno ===")
    for k in ['python_version', 'python_bits', 'platform', 'machine', 'system',
              'release', 'kernel_version', 'soundfile_version', 'libsndfile_version',
              'numpy_version']:
        v = meta.get(k)
        if isinstance(v, str) and len(v) > 80:
            v = v[:77] + '...'
        print("  {0}: {1}".format(k, v))
    print("  wav_subtypes_available: {0} subtipos".format(len(meta['wav_subtypes_available'])))
    print("  flac_subtypes_available: {0} subtipos".format(len(meta['flac_subtypes_available'])))
    print("  home_dir: {0}".format(meta['home_dir']))
    print("  uid: {0}, gid: {1}, euid: {2}".format(meta['uid'], meta['gid'], meta['euid']))
    print("  o_path_available: {0}".format(meta['o_path_available']))
    print("  o_directory_available: {0}".format(meta['o_directory_available']))
    print()

    # Ejecutar pruebas
    results = []
    started_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    interrupted = False
    interrupt_msg = None
    fatal_exception = None

    private_run_dir = None
    shared_run_dir = None

    # Flag mutable para señalizar interrupcion entre entornos
    interrupt_flag = [False]

    try:
        # Entorno A: privado
        private_run_dir = run_environment(np, sf, 'A_private', private_parent, results, run_id, interrupt_flag)

        # Entorno B: compartido (si se especifico)
        if shared_parent is not None and not interrupt_flag[0]:
            shared_run_dir = run_environment(np, sf, 'B_shared', shared_parent, results, run_id, interrupt_flag)
        elif shared_parent is not None and interrupt_flag[0]:
            msg = "interrupcion previa; entorno B no ejecutado"
            print("\n=== Entorno B_shared: NOT_EXECUTED ({0}) ===".format(msg))
            for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
                for tid in ['T11', 'T12', 'T13', 'T14']:
                    results.append({'env': 'B_shared', 'test': tid, 'fixture': fname,
                                    'status': Result.NOT_EXECUTED, 'detail': msg,
                                    'close_errors': []})
            for tid in ['T15', 'T16']:
                results.append({'env': 'B_shared', 'test': tid, 'fixture': None,
                                'status': Result.NOT_EXECUTED, 'detail': msg,
                                'close_errors': []})
        else:
            msg = "No se especifico --shared PATH; entorno B omitido"
            print("\n=== Entorno B_shared: NOT_EXECUTED ({0}) ===".format(msg))
            for fname in ['pcm16', 'pcm24', 'pcm32', 'float32']:
                for tid in ['T11', 'T12', 'T13', 'T14']:
                    results.append({'env': 'B_shared', 'test': tid, 'fixture': fname,
                                    'status': Result.NOT_EXECUTED, 'detail': msg,
                                    'close_errors': []})
            for tid in ['T15', 'T16']:
                results.append({'env': 'B_shared', 'test': tid, 'fixture': None,
                                'status': Result.NOT_EXECUTED, 'detail': msg,
                                'close_errors': []})

    except KeyboardInterrupt as exc:
        # C5 (v0.2.4): interrupcion durante la ejecucion. El estado global
        # y el flag mutable se fijan de forma coherente, para que el
        # segundo entorno no se inicie y el informe refleje la interrupcion.
        interrupted = True
        interrupt_flag[0] = True
        interrupt_msg = "KeyboardInterrupt: el usuario interrumpio la ejecucion"
        print("\n[{0}]".format(interrupt_msg))
        print("Conservando {0} resultados ya obtenidos.".format(len(results)))
        # C5.3: las pruebas que no llegaron a ejecutarse quedan como NOT_EXECUTED
        # (no se inventan resultados; las que no estan en `results` simplemente no estan)
    except Exception as exc:
        # C5.1: excepcion fatal durante la ejecucion
        interrupted = True
        interrupt_flag[0] = True
        fatal_exception = exc
        interrupt_msg = "{0}: {1}".format(type(exc).__name__, str(exc)[:120])
        print("\n[ERROR FATAL durante ejecucion] {0}".format(interrupt_msg))
        traceback.print_exc()

    # C5 (v0.2.4): coherencia del estado global. Una interrupcion absorbida
    # a nivel de prueba o de entorno (creacion de fixtures, escritura del
    # informe) puede no haber propagado el KeyboardInterrupt al llamador.
    # El flag mutable es el estado real de la ejecucion: si se seteio, el
    # resumen y el informe deben reflejar interrupcion, nunca PASS. Se
    # conservan los resultados previos.
    interrupted, interrupt_msg = _reconcile_interrupted(
        interrupt_flag, interrupted, interrupt_msg)

    # C5 (v0.2.11): reconciliacion idempotente de las pruebas planificadas:
    # toda prueba que no llego a ejecutarse (interrupcion fuera de los
    # bloques protegidos, excepcion fatal u omision) queda registrada como
    # NOT_EXECUTED, sin duplicados y sin alterar resultados anteriores.
    envs_planificadas = ['A_private']
    if shared_parent is not None:
        envs_planificadas.append('B_shared')
    pendientes = _reconcile_pending_tests(
        results, envs_planificadas,
        "prueba planificada no ejecutada (reconciliacion C5 tras "
        "interrupcion o fin anticipado)")
    if pendientes:
        print("\n[Reconciliacion C5: {0} pruebas planificadas sin registro "
              "quedaron NOT_EXECUTED]".format(pendientes))

    # C5 (v0.2.5): la construccion del informe se realiza en una funcion
    # auxiliar para poder reconstruirlo de forma consistente si una
    # interrupcion cae en la fase de resumen. El contenido del informe
    # definido en v0.2.4 no se modifica (solo se anaden las notas v0.2.5).
    def _finalize_report(interrupted_state, interrupt_message):
        """Construye el informe final a partir de los resultados obtenidos.

        Retorna (env_close_errors, finished_at, counts, total, report).
        """
        # C4-B (v0.2.9): lectura NO destructiva de los errores de cierre no
        # atribuidos desde el acumulador persistente: una reconstruccion del
        # informe no pierde los errores ya recogidos ni los duplica. Los
        # errores atribuidos a resultados de pruebas no se repiten aqui.
        env_close_errors_local = _close_errors_unattributed()

        # C4-B (v0.2.9): un fallo que no sea interrupcion en la fecha de
        # finalizacion no debe impedir construir el informe ni borrar errores
        # de cierre (KeyboardInterrupt sigue propagando: gestion C5 congelada;
        # except Exception no captura KeyboardInterrupt).
        try:
            finished_at_local = time.strftime('%Y-%m-%dT%H:%M:%S%z')
        except Exception as exc:
            finished_at_local = "DESCONOCIDO ({0}: {1})".format(
                type(exc).__name__, str(exc)[:60])
        counts_local = {'PASS': 0, 'FAIL': 0, 'NOT_EXECUTED': 0, 'ERROR': 0}
        for r in results:
            counts_local[r['status']] = counts_local.get(r['status'], 0) + 1
        total_local = len(results)
        report_local = {
            'metadata': meta,
            'started_at': started_at,
            'finished_at': finished_at_local,
            'run_id': run_id,
            'interrupted': interrupted_state,
            'interrupt_message': interrupt_message,
            'fatal_exception': (str(type(fatal_exception).__name__) + ": " + str(fatal_exception)[:200])
                               if fatal_exception else None,
            'fatal_traceback': traceback.format_exception(type(fatal_exception), fatal_exception,
                                                          fatal_exception.__traceback__) if fatal_exception else None,
            'private_parent_dir': str(private_parent),
            'shared_parent_dir': str(shared_parent) if shared_parent else None,
            'private_run_dir': str(private_run_dir) if private_run_dir else None,
            'shared_run_dir': str(shared_run_dir) if shared_run_dir else None,
            # C4 (v0.2.3): errores de cierre acumulados a nivel de entorno
            'environment_close_errors': env_close_errors_local,
            'results': results,
            'summary': {
                'total': total_local,
                'pass': counts_local.get('PASS', 0),
                'fail': counts_local.get('FAIL', 0),
                'not_executed': counts_local.get('NOT_EXECUTED', 0),
                'error': counts_local.get('ERROR', 0),
                'interrupted': interrupted_state,
            },
            'notes': [
                'Este diagnostico NO ejecuta codigo del proyecto SDV-SDI_SGM.',
                'NO modifica archivos originales del usuario.',
                'Crea exclusivamente fixtures sinteticos en directorios de ejecucion exclusivos.',
                'NO realiza limpieza automatica: los fixtures y el informe quedan en disco.',
                'NO usa /proc/self/fd como mecanismo de apertura.',
                'NO usa closefd=True en pruebas de apertura directa.',
                'NO introduce fallbacks por ruta.',
                'NO declara compatibilidad general de Android basada en estas pruebas.',
                'Los resultados son especificos al dispositivo, entorno y versiones utilizadas.',
                'C1: directorios de ejecucion y archivos creados con O_CREAT|O_EXCL|O_NOFOLLOW.',
                'C1: recorrido anclado por dir_fd + O_DIRECTORY + O_NOFOLLOW cuando es viable.',
                'C1 (v0.2.4): eliminados fallbacks por ruta; creaciones ancladas por dir_fd; '
                'publicacion del informe por os.link anclado (nombres relativos), atomica y '
                'sin sobrescritura; si el mecanismo no es viable, se conserva el provisional '
                'y se reporta explicitamente.',
                'C2: T14 ejecuta todas las comprobaciones obligatorias antes de declarar PASS; '
                'comprobaciones no realizadas se registran como NOT_DONE.',
                'C3: sha256_pread_v2 clasifica COMPLETE/ZERO_SIZE/EMPTY_UNEXPECTED/PARTIAL/SIZE_CHANGED/SYSTEM_ERROR.',
                'C3: SIZE_CHANGED no es deteccion completa de modificaciones concurrentes; '
                'cambios de contenido sin cambio de tamano pasan inadvertidos.',
                'C4: errores de cierre registrados en cada resultado (campo close_errors).',
                'C4 (v0.2.4): modelo de propiedad por apertura: cada descriptor se registra '
                'con un token único de apertura; el numero de fd y (st_dev, st_ino) no se '
                'consideran identidad suficiente; no se cierra un recurso ajeno por '
                'reutilizacion del numero de fd y no hay silencio de errores de cierre.',
                'C4 (v0.2.4): errores de cierre conservados en todos los cierres revisados '
                '(no hay except OSError: pass); se distingue el error primario del '
                'secundario de cierre.',
                'C4 (v0.2.5): registro de propiedad por token en todas las aperturas de '
                'descriptores de las pruebas T11-T16 y en safe_create_file_exclusive_anchored; '
                'los cierres se asocian al token de su apertura concreta; verificado sin '
                'fuga de descriptores por prueba.',
                'C5 (v0.2.4): toda interrupcion (prueba, creacion de fixture, escritura del '
                'informe) se refleja en el estado global; interrupcion nunca PASS; pruebas '
                'posteriores NOT_EXECUTED; rc no nulo; segundo entorno no iniciado.',
                'C5 (v0.2.5): la fase de resumen/construccion del informe y la publicacion '
                'estan protegidas contra KeyboardInterrupt: los resultados obtenidos se '
                'conservan y el informe se publica con interrupted=true; una KI durante la '
                'publicacion deja el provisional en disco y sale con rc 130; la creacion '
                'anclada del directorio de ejecucion interrumpida registra el entorno '
                'NOT_EXECUTED.',
                'C4-A cierre (v0.2.8): contrato estricto de propiedad por recurso '
                '(OwnedFdResource; estados OPEN/CLOSING/CLOSED/CLOSE_FAILED_UNCERTAIN): '
                'solo el propietario inicia el cierre, una unica vez y siempre con el '
                'token de su apertura (close_fd sin token no cierra nada); '
                'get_resource retorna una instantanea inmutable sin referencia al '
                'recurso interno; la reutilizacion del numero por el mismo archivo '
                'tras un cierre externo no es detectable por fstat (EXPECTED_LIMITATION '
                'documentada, no una proteccion conseguida).',
                'C4-B (v0.2.9): propagacion completa de errores de cierre: acumulador '
                'persistente por ejecucion con identificadores unicos y atribucion por '
                'resultado (sin perdida en reconstrucciones del informe, sin duplicacion '
                'prueba/entorno, errores posteriores a la construccion del informe '
                'visibles en la salida de diagnostico); un fallo que no sea interrupcion '
                'en la fecha de finalizacion no impide construir el informe ni borrar '
                'errores de cierre.',
                'C4-B (v0.2.10): registro unico por evento de cierre fallido en la '
                'escritura del informe (el propietario ya registra; sin doble registro '
                'del temporal ni del directorio padre) y errores de cierre informados '
                'tambien ante interrupcion durante la escritura/publicacion (codigo 130 '
                'conservado, provisional sin borrar, sin segunda publicacion).',
                'C5 (v0.2.11): coherencia de interrupciones: la KI durante el cierre '
                'de SoundFile no impide intentar el cierre del descriptor propietario '
                '(se propaga tras la limpieza, sin reintentos ni duplicados); las '
                'pruebas planificadas sin registro quedan NOT_EXECUTED por '
                'reconciliacion idempotente; el estado real de publicacion tras una '
                'KI se verifica por identidad (st_dev, st_ino) frente al provisional '
                '(PUBLICADO / NO_PUBLICADO / INDETERMINADO, nunca una afirmacion '
                'falsa); una KI durante la reconstruccion del informe registra la '
                'limitacion explicitamente y sale con codigo no nulo.',
                'C5: KeyboardInterrupt y excepciones fatales nunca terminan con codigo 0.',
                'C7: escritura completa del informe con manejo de escrituras parciales.',
            ],
        }
        return (env_close_errors_local, finished_at_local, counts_local,
                total_local, report_local)

    # C5 (v0.2.5): la fase de resumen y construccion del informe queda
    # protegida contra KeyboardInterrupt: una interrupcion en esta ventana
    # conserva los resultados ya obtenidos y publica el informe con
    # interrupted=true y codigo de salida no nulo.
    try:
        env_close_errors, finished_at, counts, total, report = _finalize_report(
            interrupted, interrupt_msg)

        # Resumen
        print("\n" + "=" * 60)
        print("=== RESUMEN ===")
        print("=" * 60)
        print("Total: {0}".format(total))
        for k in ['PASS', 'FAIL', 'NOT_EXECUTED', 'ERROR']:
            print("  {0}: {1}".format(k, counts.get(k, 0)))
        if interrupted:
            print("  INTERRUMPIDO: {0}".format(interrupt_msg))
        print()

        # Detalle por entorno
        for env in ['A_private', 'B_shared']:
            print("\n--- {0} ---".format(env))
            env_results = [r for r in results if r['env'] == env]
            for r in env_results:
                fx = r['fixture'] or '-'
                detail_short = str(r['detail'])[:60]
                close_errs = r.get('close_errors', [])
                close_str = ""
                if close_errs:
                    close_str = " close_errs={0}".format(len(close_errs))
                print("  {0} [{1:12}] {2:10} {3}{4}".format(
                    r['test'], r['status'], fx, detail_short, close_str))
    except KeyboardInterrupt:
        # C5 (v0.2.5): KI en la fase de resumen/construccion del informe:
        # estado global coherente y reconstruccion del informe (los
        # resultados obtenidos no se pierden).
        interrupted = True
        interrupt_flag[0] = True
        interrupt_msg = ((interrupt_msg + "; ") if interrupt_msg else "") + \
            "KeyboardInterrupt durante la preparacion del resumen/informe; " \
            "resultados conservados"
        interrupted, interrupt_msg = _reconcile_interrupted(
            interrupt_flag, interrupted, interrupt_msg)
        print("\n[KI durante la preparacion del informe: resultados "
              "conservados; informe con interrupted=true]")
        try:
            env_close_errors, finished_at, counts, total, report = \
                _finalize_report(interrupted, interrupt_msg)
        except KeyboardInterrupt:
            # C5 (v0.2.11): la reconstruccion del informe fue interrumpida:
            # no puede completarse ni publicarse. Se registra explicitamente
            # la limitacion y se sale con codigo no nulo (130); no se
            # declara terminacion normal ni publicacion, y no se intenta
            # una tercera construccion.
            print("\n[LIMITACION] La reconstruccion del informe fue "
                  "interrumpida (KeyboardInterrupt): el informe no pudo "
                  "completarse ni publicarse; los {0} resultados obtenidos "
                  "se conservaron en memoria pero no se escriben en un "
                  "informe.".format(len(results)))
            sys.exit(130)

    # C5/C7: escribir reporte JSON de forma robusta
    # C5 (v0.2.5): una KI durante la publicacion no publica el informe
    # (el provisional queda en disco; mecanismo C1 de v0.2.4 sin cambios)
    # y sale con codigo no nulo y mensaje explicito.
    try:
        ok_write, write_err, close_err = write_report_json_robust(report_path, report)
    except KeyboardInterrupt:
        # C5 (v0.2.11): la KI puede caer despues de que os.link completo la
        # publicacion (o durante/despues de la eliminacion del provisional).
        # Se verifica el estado real por identidad (st_dev, st_ino) del
        # informe frente al provisional de esta ejecucion: nunca se afirma
        # falsamente que se publico o que no se publico; si el estado no
        # puede determinarse se declara INDETERMINADO. Sin segunda
        # publicacion, sin sobrescritura, sin limpieza automatica; codigo
        # de salida 130 (C5 intacto).
        estado_pub, detalle_pub = _publication_state_after_interrupt(report_path)
        print("\n[INTERRUMPIDO] KeyboardInterrupt durante la publicacion del "
              "informe.")
        print("[ESTADO DE PUBLICACION: {0}] {1}".format(estado_pub, detalle_pub))
        # C4-B (v0.2.10): los errores de cierre producidos durante la
        # escritura/publicacion interrumpida se informan ANTES de finalizar
        # con 130: conservados en el acumulador persistente y en la salida
        # de diagnostico.
        for entry in _drain_close_error_sink():
            print("  [cierre pendiente] {0}: {1}".format(
                entry.get('label', '?'), entry.get('strerror', '')))
        sys.exit(130)
    if ok_write:
        print("\nReporte JSON: {0}".format(report_path))
    else:
        print("\n[ERROR] No se pudo escribir el reporte JSON: {0}".format(write_err))
        if close_err:
            print("  Adicionalmente, error de cierre: {0}".format(close_err))

    # C4-B (v0.2.9): los errores de cierre producidos durante la escritura o
    # publicacion del informe quedan en el acumulador persistente y se
    # muestran en la salida de diagnostico: no se pierden aunque el informe
    # no se publique (no se afirma publicacion si no ocurrio).
    for entry in _drain_close_error_sink():
        print("  [cierre pendiente] {0}: {1}".format(
            entry.get('label', '?'), entry.get('strerror', '')))

    # C5: codigo de salida
    # - Si interrumpido o fatal: nunca 0
    # - Si fallo escritura del informe: nunca 0
    # - Si hay FAIL o ERROR: 1
    # - Si todo PASS (sin interrupcion): 0
    if interrupted:
        # C5.1, C5.4: interrupcion o fatal => codigo != 0
        # Si fatal_exception, codigo 2; si solo interrupcion, 130 (convencion SIGINT)
        if fatal_exception is not None:
            sys.exit(2)
        sys.exit(130)
    if not ok_write:
        # C5.5: si no se puede escribir el informe, codigo != 0
        sys.exit(2)
    if counts.get('FAIL', 0) > 0 or counts.get('ERROR', 0) > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # C5: si la interrupcion ocurre fuera del main, salir con codigo 130
        print("\n[Interrumpido por usuario fuera del flujo principal]")
        sys.exit(130)
    except Exception as exc:
        # C5.1: excepcion fatal reflejada como ERROR en stderr
        print("\n[ERROR FATAL] {0}: {1}".format(type(exc).__name__, exc))
        traceback.print_exc()
        sys.exit(2)
