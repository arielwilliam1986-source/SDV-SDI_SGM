"""6G.1 (rectificado por auditoría): lectura del Mix desde el mismo descriptor,
guarda final fail-closed y aborto con propiedad acreditada.

El DSP no debe volver a abrir el Mix por su ruta. `abrir_mix` mantiene un
descriptor abierto durante toda la corrida y entrega un objeto con la misma
interfaz que `soundfile.SoundFile`, pero respaldado por ese descriptor
(`/proc/self/fd/N`), de modo que una ruta sustituida no puede alimentar el DSP.

`abortar_6g1` (rectificado C-R1) **no elimina ningún archivo**: las salidas
propias registradas por la corrida quedan invalidadas y conservadas en el
provisional; los archivos ajenos (incluido `candidates/` y los nombres de
salida del motor), los registros internos y los enlaces se conservan con su
motivo. La clasificación se basa en el dictamen de propiedad obtenido en el
momento del barrido y nunca es una decisión de borrado. `ABORT_6G1.json`
(schema `abort-6g1/3`) concentra toda la información del aborto y
`analysis.json` permanece intacto (E-R2). El directorio de aborto se abre
anclado a la identidad acreditada del provisional (H1): `O_DIRECTORY |
O_NOFOLLOW` + verificación `fstat` contra lo registrado por
`acreditar_dir_6g1()` en `create_run_dir()`; si no puede acreditarse, no se
escribe nada en esa ubicación (fail-closed).
"""
import errno
import hashlib
import json
import os
import stat
from pathlib import Path

import soundfile as sf


class MixCambiado(RuntimeError):
    """El Mix no es el objeto validado (sustitución o modificación)."""


class VerificacionFallida6G1(RuntimeError):
    """La guarda final no acreditó la identidad del Mix (VERIFICACIÓN
    INCIERTA = ABORTO). El llamador ya ejecutó el aborto sobre el directorio
    provisional; este error sólo señala que no debe publicarse."""


def _identity(st):
    return dict(device=st.st_dev, inode=st.st_ino, size=st.st_size,
                mtime_ns=st.st_mtime_ns, mode=oct(st.st_mode))


def _sha_fd(fd):
    m = hashlib.sha256()
    g = os.fdopen(os.dup(fd), 'rb')
    try:
        g.seek(0)
        for block in iter(lambda: g.read(1 << 20), b''):
            m.update(block)
    finally:
        g.close()
    return m.hexdigest()


def _sha_archivo(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            m.update(block)
    return m.hexdigest()


class MixHandle:
    """Descriptor del Mix validado + lector SoundFile sobre el mismo inodo."""

    def __init__(self, path, sha_esperado=None):
        object.__setattr__(self, '_snd', None)
        self.path = os.path.abspath(path)
        self.fd = os.open(self.path, os.O_RDONLY)
        try:
            st = os.fstat(self.fd)
            if not stat.S_ISREG(st.st_mode):
                raise MixCambiado('El Mix no es un archivo regular')
            self.identity = _identity(st)
            self.digest = _sha_fd(self.fd)
            if sha_esperado is not None and self.digest != sha_esperado:
                raise MixCambiado(
                    'SHA-256 del Mix distinto del sondeo: sustitución antes del DSP '
                    f'({self.digest[:16]} != {str(sha_esperado)[:16]})')
            proc = '/proc/self/fd/%d' % self.fd
            if not os.path.exists(proc):
                raise MixCambiado('Sin /proc/self/fd: no se puede leer el mismo inodo')
            self._snd = sf.SoundFile(proc)
        except Exception:
            self.close()
            raise

    # --- interfaz SoundFile -------------------------------------------------
    def __getattr__(self, nombre):
        snd = object.__getattribute__(self, '_snd')
        if snd is None:
            raise AttributeError(nombre)
        return getattr(snd, nombre)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self):
        snd = object.__getattribute__(self, '_snd')
        if snd is not None:
            try:
                snd.close()
            except Exception:
                pass
            object.__setattr__(self, '_snd', None)
        fd = getattr(self, 'fd', None)
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
            self.fd = None

    # --- integridad ---------------------------------------------------------
    def verificar(self):
        """Relee el descriptor y compara bytes e identidad con la apertura."""
        if self.fd is None:
            return dict(unchanged=False, reason='descriptor cerrado')
        st = os.fstat(self.fd)
        ident = _identity(st)
        digest = _sha_fd(self.fd)
        ok = (digest == self.digest and ident == self.identity)
        return dict(unchanged=ok,
                    reason='sha256 e identidad revalidados' if ok
                    else ('contenido distinto' if digest != self.digest
                          else 'identidad fstat distinta'),
                    sha256=digest, expected=self.digest,
                    identity=ident, identity_expected=self.identity)

    def ruta_lectura(self):
        """Ruta al mismo inodo (para funciones que exigen un nombre de archivo)."""
        if self.fd is None:
            raise MixCambiado('descriptor cerrado')
        return '/proc/self/fd/%d' % self.fd

    def ruta_apunta_al_mismo_objeto(self):
        try:
            st = os.stat(self.path)
        except OSError as exc:
            return dict(unchanged=False, reason=f'ruta inaccesible: {exc}')
        ident = _identity(st)
        return dict(unchanged=ident == self.identity,
                    reason='ruta e inodo de apertura coinciden' if ident == self.identity
                    else 'la ruta ya no apunta al inodo validado',
                    identity=ident, identity_expected=self.identity)


def abrir_mix(path, sha_esperado=None):
    return MixHandle(path, sha_esperado)


# ---------------------------------------------------------------------------
# Registro de propiedad de la corrida (corrección C, rectificación 6G.1)
# ---------------------------------------------------------------------------

_PROPIOS_6G1 = {}


# [6G.1-R/H1] Identidad acreditada del directorio provisional de la corrida:
# (st_dev, st_ino) registrados por acreditar_dir_6g1() en create_run_dir() y
# verificados con fstat() al abrir el directorio durante el aborto.
_DIR_6G1 = {}


def acreditar_dir_6g1(path):
    """[H1] Acredita la identidad del directorio provisional de la corrida.

    Registra (st_dev, st_ino) del directorio creado por `create_run_dir()`
    (lstat, sin seguir enlaces). Debe llamarse inmediatamente después del
    mkdir exclusivo del provisional. Fail-closed: si la ruta no es un
    directorio real, eleva RuntimeError.
    """
    p = os.path.abspath(str(path))
    st = os.lstat(p)
    if not stat.S_ISDIR(st.st_mode):
        raise RuntimeError('[H1] la ruta a acreditar no es un directorio: %s' % p)
    _DIR_6G1[p] = dict(device=st.st_dev, inode=st.st_ino)
    return p


def _anclar_dir_aborto_6g1(run_dir):
    """[H1] Abre el directorio de aborto sin seguir enlaces y verifica su
    identidad contra la acreditada por la corrida.

    Devuelve `(fd, motivo)`. Fail-closed: `fd` es None si la corrida no
    acreditó este directorio, si la apertura segura falla (ENOENT, ELOOP por
    enlace simbólico en la ruta, etc.), si el descriptor no es un directorio
    o si `fstat` no coincide con la identidad acreditada. En todos esos
    casos el llamador NO debe escribir `ABORT_6G1.json` en esa ubicación ni
    seguir el enlace.
    """
    p = os.path.abspath(str(run_dir))
    reg = _DIR_6G1.get(p)
    if reg is None:
        return None, ('directorio_no_acreditado_para_esta_corrida (H1): '
                      'sin escritura en esta ubicación')
    try:
        fd = os.open(p, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        return None, ('apertura_segura_fallo (H1): %s (un enlace simbólico '
                      'en la ruta no se sigue)' % exc)
    try:
        st = os.fstat(fd)
    except OSError as exc:
        os.close(fd)
        return None, 'fstat_fallo (H1): %s' % exc
    if not stat.S_ISDIR(st.st_mode):
        os.close(fd)
        return None, 'no_es_directorio (H1)'
    if (st.st_dev, st.st_ino) != (reg['device'], reg['inode']):
        os.close(fd)
        return None, ('identidad_distinta (H1): el directorio de la ruta no '
                      'coincide con el provisional acreditado')
    return fd, 'directorio_acreditado (H1)'


def reiniciar_registro_6g1():
    """Limpia los registros de propiedad y de directorio acreditado (uso en
    pruebas y al iniciar corrida)."""
    _PROPIOS_6G1.clear()
    _DIR_6G1.clear()


def registrar_propio_6g1(path, estable=True):
    """Registra un archivo creado por esta corrida con su identidad.

    `estable=True`: archivo finalizado (informes); se sella tamaño, mtime y
    SHA-256 en el registro. `estable=False`: archivo en curso (WAV/memmap
    abiertos por el motor); la propiedad se acredita por ruta registrada +
    continuidad de inodo (el contenido crece legítimamente mientras el motor
    lo escribe). Si el archivo no puede observarse, NO se registra y, por
    tanto, la limpieza lo conservará (fail-closed, sin interrumpir al motor).
    """
    p = os.path.abspath(str(path))
    try:
        st = os.stat(p)
    except OSError:
        return False
    _PROPIOS_6G1[p] = dict(device=st.st_dev, inode=st.st_ino,
                           size=st.st_size, mtime_ns=st.st_mtime_ns,
                           sha256=_sha_archivo(p) if estable else None,
                           estable=bool(estable))
    return True


def propiedad_de_6g1(path):
    """Dictamen de propiedad de un archivo para esta corrida.

    Devuelve `(es_propia, motivo)`. Fail-closed: cualquier duda conserva el
    archivo (`ajeno_no_registrado`, `identidad_distinta`, `modificado`,
    `no_accesible`).

    [6G.1-R/C-R1] El dictamen es SOLO para clasificar y registrar: el aborto
    NO elimina archivos, así que una carrera entre este dictamen y cualquier
    operación posterior ya no puede provocar el borrado de un archivo ajeno.
    """
    p = os.path.abspath(str(path))
    reg = _PROPIOS_6G1.get(p)
    if reg is None:
        return False, 'ajeno_no_registrado'
    try:
        # [6G.1-R/E] lstat: sin seguir enlaces; un enlace nunca puede acreditar
        # la identidad de un archivo regular registrado.
        st = os.lstat(p)
    except OSError as exc:
        return False, 'no_accesible: %s' % exc
    if stat.S_ISLNK(st.st_mode):
        return False, 'enlace_simbolico_no_propio'
    if (st.st_dev, st.st_ino) != (reg['device'], reg['inode']):
        return False, 'identidad_distinta (sustituido o reemplazado tras el registro)'
    if reg['estable']:
        if st.st_size != reg['size'] or st.st_mtime_ns != reg['mtime_ns']:
            return False, 'tamaño/mtime distintos de los registrados'
        if _sha_archivo(p) != reg['sha256']:
            return False, 'contenido modificado tras el registro'
    return True, 'propiedad_acreditada'


def _es_registro_interno(nombre):
    """Archivos de registro forense que el aborto conserva siempre."""
    return nombre in ('ABORT_6G1.json', 'engine_log.txt',
                      'analysis.json', 'input_integrity_6g.json')


def abortar_6g1(run_dir, motivo, detalle=None):
    """Registra el aborto de la corrida conservando TODOS los archivos (C-R1).

    [6G.1-R/C-R1] **Sin eliminación de archivos**: el aborto no borra nada.
    Las salidas propias registradas por la corrida quedan **invalidadas y
    conservadas** en el provisional (listadas en `salidas_invalidadas`, con
    `estado_salidas_invalidadas`); los archivos ajenos —incluido uno que
    coincida con un nombre de salida del motor o que esté dentro de
    `candidates/`—, los registros internos y los enlaces se **conservan**
    con su motivo; `resultados_validos` es siempre vacío. La clasificación
    usa el registro de la corrida (ruta + identidad) SOLO para registrar,
    nunca como decisión de borrado: la ventana TOCTOU entre la comprobación
    y `os.unlink` (hallazgo C-R1) deja de existir por construcción. Un
    directorio con `ABORT_6G1.json` nunca puede publicarse como corrida
    exitosa (la publicación sólo ocurre por `publicar_dir_6g1` en la ruta de
    éxito tras la guarda, y los traslados de aborto usan nombres
    `_aborted*`).

    [6G.1-R/E] Seguridad frente a enlaces simbólicos en los archivos internos:
    - el inventario usa `lstat` (los enlaces se conservan, nunca se siguen);
    - `ABORT_6G1.json` se crea de forma **exclusiva y no-follow** anclada al
      descriptor del directorio (`O_CREAT|O_EXCL|O_NOFOLLOW` + `dir_fd`): no
      sobrescribe preexistente ni simbólico y nunca escribe fuera del
      directorio de corrida;
    - `analysis.json` **no se modifica durante el aborto** [6G.1-R/E-R2]:
      toda la información del aborto se registra exclusivamente en
      `ABORT_6G1.json`; `analysis.json` permanece byte a byte intacto. Esto
      elimina la ventana de pérdida de contenido que existía si write()/
      fsync() fallaba tras ftruncate() (hallazgo E-R2), sin reintroducir
      escrituras por nombre ni ventanas TOCTOU.

    [6G.1-R/H1] Anclaje del directorio de aborto: la identidad (st_dev,
    st_ino) del provisional queda acreditada por `acreditar_dir_6g1()` en
    `create_run_dir()` de los tres motores; el aborto abre el directorio con
    `O_DIRECTORY | O_NOFOLLOW` y verifica con `fstat()` que coincide. Si la
    ruta fue sustituida por un enlace simbólico o por otro directorio, o la
    acreditación no existe, NO se escribe `ABORT_6G1.json` en esa ubicación
    ni se sigue el enlace: fail-closed, sin eliminaciones y sin salidas
    válidas declaradas. El inventario y la escritura de `ABORT_6G1.json`
    operan sobre EL MISMO descriptor de directorio ya validado (sin
    reapertura por ruta).
    """
    run_dir = Path(run_dir)
    invalidadas, conservados, motivos = [], [], {}
    # [6G.1-R/H1] Anclaje del directorio de aborto: apertura sin seguir
    # enlaces y verificación fstat contra la identidad acreditada por
    # create_run_dir(). Fail-closed: si el anclaje falla NO se escribe
    # ABORT_6G1.json en esa ubicación (podría ser un enlace simbólico o un
    # directorio sustituido), no se sigue el enlace, no se elimina nada y no
    # se declara ninguna salida válida.
    fd_dir, motivo_anclaje = _anclar_dir_aborto_6g1(run_dir)
    if fd_dir is None:
        info = dict(schema='abort-6g1/3', motivo=motivo, detalle=detalle,
                    salidas_invalidadas=[],
                    estado_salidas_invalidadas=('conservadas en el provisional; '
                                                'sin eliminación (C-R1)'),
                    resultados_validos=[],
                    conservados=[],
                    motivos_propiedad={},
                    analysis_intacto=True,
                    directorio_acreditado=False,
                    anclaje_directorio=motivo_anclaje,
                    politica='sin_eliminacion (C-R1): ningún archivo se elimina '
                             'durante el aborto; anclaje H1: sin escritura de '
                             'ABORT_6G1.json si el directorio no pudo '
                             'acreditarse; analysis.json intacto (E-R2); un '
                             'directorio con ABORT_6G1.json nunca es una '
                             'corrida exitosa')
        return info
    try:
        # --- inventario anclado al DESCRIPTOR validado (sin recorrer rutas):
        # reproduce la semántica del barrido anterior (lstat por entrada;
        # enlaces conservados sin seguir; regulares clasificados; el resto
        # omitido) pero descendiendo sólo por directorios reales abiertos con
        # O_NOFOLLOW, de modo que ninguna parte del aborto recorre la ruta
        # después de la acreditación (H1).
        def _inventariar(fd_base, prefijo=''):
            try:
                nombres = sorted(os.listdir(fd_base))
            except OSError:
                return
            for nombre in nombres:
                rel = prefijo + nombre
                try:
                    st = os.lstat(nombre, dir_fd=fd_base)
                except OSError:
                    continue
                if stat.S_ISLNK(st.st_mode):
                    conservados.append(rel)
                    motivos[rel] = 'enlace_simbolico_conservado (sin seguir)'
                    continue
                if stat.S_ISDIR(st.st_mode):
                    try:
                        fd_sub = os.open(nombre, os.O_RDONLY | os.O_DIRECTORY
                                         | os.O_NOFOLLOW, dir_fd=fd_base)
                    except OSError:
                        continue
                    try:
                        _inventariar(fd_sub, rel + '/')
                    finally:
                        os.close(fd_sub)
                    continue
                if not stat.S_ISREG(st.st_mode):
                    continue
                if _es_registro_interno(nombre):
                    conservados.append(rel)
                    motivos[rel] = 'registro_interno_conservado'
                    continue
                propia, motivo_p = propiedad_de_6g1(os.path.join(str(run_dir),
                                                                 rel))
                if propia:
                    # [6G.1-R/C-R1] Sin eliminación: la salida propia
                    # registrada queda INVALIDADA y CONSERVADA en el
                    # provisional (clasificación basada en el dictamen
                    # obtenido antes de la sustitución si la hubiera; no
                    # identifica necesariamente la identidad posterior).
                    invalidadas.append(rel)
                    motivos[rel] = ('salida_parcial_invalidada_y_conservada '
                                    '(sin eliminación; C-R1)')
                else:
                    conservados.append(rel)
                    motivos[rel] = motivo_p
        _inventariar(fd_dir)
        # [6G.1-R/C-R1] Esquema versionado: abort-6g1/3 (la semántica de
        # salidas_invalidadas cambia respecto de /2: quedan CONSERVADAS, no
        # eliminadas). Consumidores actualizados en compatibilidad y
        # documentación. [H1] campos de anclaje añadidos (aditivos).
        info = dict(schema='abort-6g1/3', motivo=motivo, detalle=detalle,
                    salidas_invalidadas=invalidadas,
                    estado_salidas_invalidadas=('conservadas en el provisional; '
                                                'sin eliminación (C-R1)'),
                    resultados_validos=[],
                    conservados=conservados,
                    motivos_propiedad=motivos,
                    analysis_intacto=True,
                    directorio_acreditado=True,
                    anclaje_directorio=motivo_anclaje,
                    politica='sin_eliminacion (C-R1): ningún archivo se elimina '
                             'durante el aborto; las salidas propias registradas '
                             'quedan invalidadas y conservadas; sin borrado por '
                             'patrón de nombre ni por ubicación; sin escritura a '
                             'través de enlaces simbólicos; analysis.json no se '
                             'modifica durante el aborto (E-R2): toda la '
                             'información del aborto vive en ABORT_6G1.json; un '
                             'directorio con ABORT_6G1.json nunca es una corrida '
                             'exitosa; anclaje H1: directorio acreditado y E/S '
                             'sobre el descriptor validado')
        # --- ABORT_6G1.json: creación exclusiva y no-follow sobre EL MISMO
        # descriptor de directorio ya validado (H1: sin reapertura por ruta).
        try:
            fd = os.open('ABORT_6G1.json',
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o644, dir_fd=fd_dir)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(json.dumps(info, indent=2, ensure_ascii=False,
                                   default=str))
        except FileExistsError:
            motivos['ABORT_6G1.json'] = ('colision: ABORT_6G1.json preexistente '
                                         '(o enlace); sin sobrescribir')
        except OSError as exc:
            motivos['ABORT_6G1.json'] = ('no escribible de forma segura: %s' % exc)
        # --- analysis.json: SIN MODIFICAR durante el aborto [6G.1-R/E-R2]
        # La actualización con descriptor único (E-R1) dejaba una pérdida de
        # contenido si write()/fsync() fallaba después de ftruncate(): el
        # original no era recuperable. Por decisión del responsable se aplica
        # la solución preferida: analysis.json NO se modifica durante el
        # aborto; la información completa del aborto (schema, motivo,
        # salidas_invalidadas, conservados, motivos_propiedad) se registra
        # exclusivamente en ABORT_6G1.json, que ya tiene creación exclusiva y
        # no-follow anclada al dirfd. Así la conservación de analysis.json es
        # estructural (no hay ninguna escritura dirigida a él) y no se
        # reintroducen escrituras por nombre ni ventanas TOCTOU.
    finally:
        os.close(fd_dir)
    return info


# ---------------------------------------------------------------------------
# Publicación con no-reemplazo atómico (corrección G, rectificación 6G.1)
# ---------------------------------------------------------------------------

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1
_NR_RENAMEAT2 = {'x86_64': 316, 'aarch64': 276, 'armv7l': 382, 'armv8l': 382,
                 'ppc64le': 357, 's390x': 347, 'riscv64': 276}


def _renameat2_noreplace(origen, destino):
    """[6G.1-R/G] renameat2(..., RENAME_NOREPLACE): operación atómica de
    no-reemplazo. Falla con EEXIST si `destino` existe; nunca lo reemplaza.
    Eleva OSError si el entorno no puede garantizar la operación (el llamador
    NO debe publicar en ese caso: fail-closed, sin degradación silenciosa)."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    fn = None
    if hasattr(libc, 'renameat2'):
        fn = libc.renameat2
        fn.restype = ctypes.c_int
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                       ctypes.c_char_p, ctypes.c_uint]
        r = fn(_AT_FDCWD, os.fsencode(origen), _AT_FDCWD,
               os.fsencode(destino), _RENAME_NOREPLACE)
    elif os.uname().machine in _NR_RENAMEAT2:
        sysc = libc.syscall
        sysc.restype = ctypes.c_long
        sysc.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p,
                         ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        r = sysc(_NR_RENAMEAT2[os.uname().machine], _AT_FDCWD,
                 os.fsencode(origen), _AT_FDCWD, os.fsencode(destino),
                 _RENAME_NOREPLACE)
    else:
        raise OSError('renameat2 indisponible: la publicación no puede '
                      'garantizarse sin reemplazo')
    if r != 0:
        e = ctypes.get_errno()
        if e == errno.EEXIST:
            raise FileExistsError(e, 'destino existente', destino)
        raise OSError(e, 'renameat2 RENAME_NOREPLACE: %s' % os.strerror(e),
                      origen, None, destino)


def publicar_dir_6g1(origen, destino, max_intentos=64):
    """[6G.1-R/G] Publica `origen` renombrándolo a `destino` SIN reemplazo.

    Devuelve la ruta definitiva publicada. Si `destino` existe (colisión o
    carrera), prueba con sufijos incrementales — jamás toca el contenido del
    destino existente. Si el entorno no garantiza el no-reemplazo, eleva
    OSError: el motor NO publica y conserva el provisional (fail-closed).
    """
    origen = os.path.abspath(origen)
    destino = os.path.abspath(destino)
    ultimo = None
    for i in range(max_intentos):
        candidato = destino if i == 0 else '%s_r%03d' % (destino, i)
        try:
            _renameat2_noreplace(origen, candidato)
            return candidato
        except FileExistsError as exc:
            ultimo = exc
            continue
    raise ultimo or OSError('agotados los intentos de publicación segura')
