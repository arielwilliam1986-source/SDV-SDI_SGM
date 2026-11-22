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
`crear_y_acreditar_dir_6g1()` en `create_run_dir()` (H1-R2/A: creación y
acreditación por descriptores, con el padre validado como propiedad del euid
y sin escritura para terceros); el inventario y la clasificación de propiedad
se realizan exclusivamente por descriptores, sin re-consultar rutas
(H1-R2/B); si el anclaje no puede acreditarse, no se escribe nada en esa
ubicación (fail-closed).

La apertura del Mix validado es segura (H2): `probe_file()` de los motores
captura la identidad (st_dev, st_ino, tamaño, mtime_ns, ctime_ns) del objeto
validado y verifica su estabilidad durante la validación y el cálculo del
SHA (H2-C); `MixHandle` abre con `O_NONBLOCK` (H2-B: una sustitución por FIFO
no puede bloquear la llamada), exige por `fstat` un archivo regular cuya
identidad coincida con la validada (H2-A: un archivo DISTINTO con SHA
idéntico no es aceptable) y calcula el SHA con verificación de estabilidad.
POLÍTICA DE ENLACES SIMBÓLICOS SIN CAMBIO: la apertura sigue enlaces
legítimos (como toda la fase de validación) y el anclaje se logra por
identidad del objeto abierto, no con `O_NOFOLLOW`; rechazarlos rompería
instalaciones legítimas y no aporta seguridad adicional frente a sustitución.

[H2-R] Los probes de los motores validan el Mix ANCLADO AL MISMO OBJETO
desde el inicio: una única apertura O_NONBLOCK + fstat (regular); metadatos,
validaciones de contenedor y SHA-256 operan sobre ese descriptor (vía
`/proc/self/fd/N` donde la API exige ruta, y con `sha_fd_estable_6g1` para
el hash); la ruta del usuario no se reabre durante la validación y el fstat
final falla cerrado si el objeto cambió.

[CV] Ciclo de vida (hallazgo A): `abortar_corrida_6g1()` es el protocolo
ÚNICO de aborto de los tres motores (interrupción, excepción general, fallo
de apertura del Mix, guarda final, publicación segura y fallos de preparación
posteriores a la creación del provisional): registra primero con
`abortar_6g1()`; sólo con el directorio acreditado y `ABORT_6G1.json` escrito
y verificado sobre el descriptor anclado, y si el motor solicita traslado
(interrupción, excepción general, fallos de preparación), traslada a
`_aborted*` con `publicar_dir_6g1()` (sin reemplazo); los fallos de
integridad del Mix (apertura, guarda final) y de publicación registran el
aborto SIN traslado (contrato histórico); en cualquier otro caso conserva el
provisional en su ubicación. `FalloCorrida6G1` encauza los fallos conocidos
hacia ese manejador.
"""
import errno
import hashlib
import json
import os
import stat
import sys
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


def _sha_fd_estable(fd):
    """[H2-C] SHA-256 de un descriptor con verificación de ESTABILIDAD:
    `fstat()` antes y después de la lectura; comparación de identidad
    (st_dev/st_ino), tamaño, mtime_ns y ctime_ns entre ambos estados. Si
    cualquier dato cambia, el archivo se modificó durante la lectura y el
    SHA NO se acredita. Lectura incremental (sin acumular en memoria) sobre
    un duplicado con seek(0) (no altera el offset del descriptor original).
    Compatible con Python 3.8. Devuelve (sha256, None) o (None, motivo)."""
    st0 = os.fstat(fd)
    m = hashlib.sha256()
    g = os.fdopen(os.dup(fd), 'rb')
    try:
        g.seek(0)
        for block in iter(lambda: g.read(1 << 20), b''):
            m.update(block)
    finally:
        g.close()
    st1 = os.fstat(fd)
    if (st1.st_dev, st1.st_ino) != (st0.st_dev, st0.st_ino) or \
            (st1.st_size, st1.st_mtime_ns, st1.st_ctime_ns) != \
            (st0.st_size, st0.st_mtime_ns, st0.st_ctime_ns):
        return None, ('archivo modificado durante la lectura del SHA '
                      '(H2-C): SHA no acreditable')
    return m.hexdigest(), None


def sha_fd_estable_6g1(fd):
    """[H2-R] API pública para probes anclados al descriptor: SHA-256 con
    verificación de estabilidad (misma garantía que `_sha_fd_estable`: fstat
    antes/después de la lectura incremental — identidad, tamaño, mtime_ns,
    ctime_ns) sobre un descriptor YA ABIERTO. Devuelve (sha256, None) o
    (None, motivo) si el objeto cambió durante la lectura."""
    return _sha_fd_estable(fd)


def _sha_archivo(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            m.update(block)
    return m.hexdigest()


class MixHandle:
    """Descriptor del Mix validado + lector SoundFile sobre el mismo inodo."""

    def __init__(self, path, sha_esperado=None, identidad_esperada=None):
        object.__setattr__(self, '_snd', None)
        self.path = os.path.abspath(path)
        # [6G.1-R/H2-B] O_NONBLOCK: una sustitución por FIFO entre la
        # validación y esta apertura no puede bloquear la llamada (el
        # descriptor se obtiene al instante y el fstat siguiente clasifica el
        # objeto). POLÍTICA DE ENLACES SIMBÓLICOS SIN CAMBIO (documentada):
        # la apertura sigue enlaces legítimos como toda la fase de
        # validación; el anclaje se logra por identidad (H2-A), no con
        # O_NOFOLLOW.
        self.fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            st = os.fstat(self.fd)
            if not stat.S_ISREG(st.st_mode):
                raise MixCambiado('El Mix no es un archivo regular (H2-B: '
                                  'apertura no bloqueante ante FIFO)')
            self.identity = _identity(st)
            # [6G.1-R/H2-A] La identidad del objeto ABIERTO debe coincidir con
            # la del objeto VALIDADO (probe_file): un archivo distinto con
            # contenido idéntico NO es aceptable aunque el SHA coincida.
            if identidad_esperada is not None and \
                    (st.st_dev, st.st_ino) != tuple(identidad_esperada):
                raise MixCambiado(
                    'La identidad del Mix abierto no coincide con la validada '
                    f'(H2-A): abierto dev/ino ({st.st_dev}, {st.st_ino}) != '
                    f'validado {tuple(identidad_esperada)}; un archivo distinto '
                    'con SHA idéntico no es aceptable')
            self.identity_expected = (tuple(identidad_esperada)
                                      if identidad_esperada is not None
                                      else None)
            # [6G.1-R/H2-A] Bandera de apertura segura: la identidad del
            # descriptor fue exigida y coincide con la del objeto validado.
            self.identity_validada = identidad_esperada is not None
            # [6G.1-R/H2-C] SHA estable: fstat antes/después de la lectura
            # (identidad/tamaño/mtime_ns/ctime_ns); si cambió, no se acredita.
            self.digest, motivo = _sha_fd_estable(self.fd)
            if motivo is not None:
                raise MixCambiado(f'H2-C: {motivo}')
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
        """Relee el descriptor, compara bytes e identidad con la apertura y
        verifica la ESTABILIDAD del objeto durante la relectura (H2-C: fstat
        antes y después; identidad, tamaño, mtime_ns y ctime_ns)."""
        if self.fd is None:
            return dict(unchanged=False, reason='descriptor cerrado')
        st = os.fstat(self.fd)
        ident = _identity(st)
        digest, motivo = _sha_fd_estable(self.fd)
        estable = motivo is None
        ok = (estable and digest == self.digest and ident == self.identity)
        if motivo is not None:
            razon = f'H2-C: {motivo}'
        elif ok:
            razon = 'sha256 e identidad revalidados (estables, H2-C)'
        elif digest != self.digest:
            razon = 'contenido distinto'
        else:
            razon = 'identidad fstat distinta'
        return dict(unchanged=ok,
                    reason=razon,
                    sha256=(digest or ''), expected=self.digest,
                    identity=ident, identity_expected=self.identity,
                    estable=estable)

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


def abrir_mix(path, sha_esperado=None, identidad_esperada=None):
    """Abre el Mix validado.
    [H2-A] `identidad_esperada` = (st_dev, st_ino) capturado en `probe_file()`
    del motor: exigida por `fstat` antes de aceptar el descriptor (un archivo
    distinto con SHA idéntico es rechazado).
    [H2-B] Apertura con O_NONBLOCK (una FIFO no bloquea).
    [H2-C] SHA estable (fstat antes/después de la lectura)."""
    return MixHandle(path, sha_esperado, identidad_esperada)


# ---------------------------------------------------------------------------
# Registro de propiedad de la corrida (corrección C, rectificación 6G.1)
# ---------------------------------------------------------------------------

_PROPIOS_6G1 = {}


# [6G.1-R/H1] Identidad acreditada del directorio provisional de la corrida:
# (st_dev, st_ino) registrados por acreditar_dir_6g1() en create_run_dir() y
# verificados con fstat() al abrir el directorio durante el aborto.
_DIR_6G1 = {}


def acreditar_dir_6g1(path):
    """[H1] Acredita la identidad de un directorio existente (por ruta).

    Registra (st_dev, st_ino) vía `lstat` (sin seguir enlaces). Uso en
    arneses de pruebas sobre directorios ya creados; la producción usa
    `crear_y_acreditar_dir_6g1()` (H1-R2/A), que crea y acredita por
    descriptores sin depender de la ruta tras la creación. Fail-closed: si
    la ruta no es un directorio real, eleva RuntimeError.
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


def crear_y_acreditar_dir_6g1(padre, nombre):
    """[H1-R2/A] Crea el directorio provisional y acredita su identidad sin
    depender de la ruta tras la creación.

    Secuencia fail-closed en cada paso:
    1. Abre el padre de forma segura (`O_DIRECTORY | O_NOFOLLOW`; un enlace
       simbólico en la ruta del padre no se sigue).
    2. Verifica la condición de seguridad del padre: propiedad del euid y sin
       permisos de escritura para grupo/otros ("privado y no modificable por
       terceros"). Si no se cumple, NO crea nada y eleva RuntimeError.
    3. Crea el provisional con `os.mkdir(nombre, 0o700, dir_fd=fd_padre)`
       (exclusivo respecto del padre validado; modo privado).
    4. Abre el provisional relativo al padre VALIDADO con `O_NOFOLLOW` y
       acredita su identidad mediante `fstat`: la identidad registrada es la
       del objeto creado dentro del padre validado, no la de una re-consulta
       por ruta. La ventana POSIX residual entre mkdir y la apertura (sólo
       alcanzable por procesos de la misma uid) queda cubierta por la
       condición del padre verificada en el paso 2.
    Devuelve (ruta_absoluta, (st_dev, st_ino)) y registra en `_DIR_6G1`.
    """
    p_padre = os.path.abspath(str(padre))
    fd_padre = os.open(p_padre, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st_padre = os.fstat(fd_padre)
        if not stat.S_ISDIR(st_padre.st_mode):
            raise RuntimeError('[H1-R2/A] el padre no es un directorio: %s'
                               % p_padre)
        if st_padre.st_uid != os.geteuid():
            raise RuntimeError('[H1-R2/A] padre sin propiedad del euid '
                               '(no privado): %s' % p_padre)
        if st_padre.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise RuntimeError('[H1-R2/A] padre modificable por terceros '
                               '(escritura grupo/otros): %s' % p_padre)
        os.mkdir(str(nombre), 0o700, dir_fd=fd_padre)
        fd_dir = os.open(str(nombre), os.O_RDONLY | os.O_DIRECTORY
                         | os.O_NOFOLLOW, dir_fd=fd_padre)
        try:
            st = os.fstat(fd_dir)
            if not stat.S_ISDIR(st.st_mode):
                raise RuntimeError('[H1-R2/A] lo creado no es un directorio')
        finally:
            os.close(fd_dir)
        ruta = os.path.join(p_padre, str(nombre))
        _DIR_6G1[ruta] = dict(device=st.st_dev, inode=st.st_ino)
        return ruta, (st.st_dev, st.st_ino)
    finally:
        os.close(fd_padre)


def _sha_via_descriptor_6g1(nombre, fd_dir, st):
    """[H1-R2/B, reforzado H1-R2-R1] SHA-256 de un archivo del directorio
    anclado, con verificación de ESTABILIDAD durante toda la lectura:

    1. `fstat()` al abrir el descriptor (O_NOFOLLOW + dir_fd, sin rutas) y
       comprobación de que es el mismo archivo REGULAR identificado por el
       `lstat` relativo (identidad st_dev/st_ino).
    2. SHA-256 por actualización incremental de `hashlib` (sin acumular el
       contenido completo en memoria).
    3. SEGUNDO `fstat()` al terminar la lectura.
    4. Comparación de identidad, tamaño, mtime y ctime entre ambos estados:
       si cualquier dato cambia, el archivo se modificó durante la lectura y
       el SHA NO se acredita como válido (se devuelve (None, motivo)).

    Compatible con Python 3.8 (st_mtime_ns/st_ctime_ns). Devuelve
    (sha256, None) o (None, motivo).

    [H1-R2-R2] La apertura incorpora `O_NONBLOCK`: cierra la ventana entre el
    `lstat` previo y la apertura — si la entrada regular fue sustituida por
    una FIFO, la apertura de sólo lectura NO se bloquea (con O_NONBLOCK el
    descriptor se obtiene al instante); el `fstat` siguiente la clasifica
    como no regular y el SHA no se acredita (fail-closed)."""
    # [H1-R2-R2] O_NONBLOCK: cierra la ventana entre el lstat previo y esta
    # apertura — si la entrada regular fue sustituida por una FIFO, la
    # apertura de sólo lectura NO se bloquea (con O_NONBLOCK el descriptor se
    # obtiene al instante); el fstat siguiente detecta que no es regular y el
    # hash se rechaza (fail-closed, sin leer el objeto no regular).
    fd = os.open(str(nombre),
                 os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=fd_dir)
    try:
        st0 = os.fstat(fd)                                  # estado inicial
        if not stat.S_ISREG(st0.st_mode):
            return None, 'no_es_archivo_regular (H1-R2-R1)'
        if (st0.st_dev, st0.st_ino) != (st.st_dev, st.st_ino):
            return None, 'identidad_distinta'
        h = hashlib.sha256()                                # incremental
        while True:
            bloque = os.read(fd, 1 << 20)
            if not bloque:
                break
            h.update(bloque)
        st1 = os.fstat(fd)                                  # estado final
        if (st1.st_dev, st1.st_ino) != (st0.st_dev, st0.st_ino):
            return None, ('identidad cambiada durante la lectura '
                          '(H1-R2-R1)')
        if (st1.st_size, st1.st_mtime_ns, st1.st_ctime_ns) != \
                (st0.st_size, st0.st_mtime_ns, st0.st_ctime_ns):
            return None, ('archivo modificado durante la lectura '
                          '(H1-R2-R1): SHA no acreditable')
        return h.hexdigest(), None
    finally:
        os.close(fd)


def _clasificar_entrada_6g1(nombre, st, fd_dir, ruta_esperada):
    """[H1-R2/B] Clasificación de propiedad de una entrada del directorio
    anclado, EXCLUSIVAMENTE por descriptor: identidad (st_dev, st_ino) del
    `lstat` relativo cotejada contra el registro de la corrida y sellado
    (tamaño/mtime/SHA-256) verificado por `dir_fd` + `O_NOFOLLOW` + `fstat`.
    `ruta_esperada` se usa SOLO como clave de comparación del registro (para
    distinguir un sustituido de un ajeno) — NUNCA para re-consultar el
    sistema de archivos. Devuelve (es_propia, motivo) con semántica C-R1
    (fail-closed: cualquier duda conserva).
    """
    match = [(k, reg) for k, reg in _PROPIOS_6G1.items()
             if (reg.get('device'), reg.get('inode'))
             == (st.st_dev, st.st_ino)]
    if not match:
        if ruta_esperada in _PROPIOS_6G1:
            return False, ('identidad_distinta (sustituido o reemplazado '
                           'tras el registro)')
        return False, 'ajeno_no_registrado'
    if len(match) > 1:
        return False, 'identidad_ambigua_en_registro'
    reg = match[0][1]
    if not reg.get('estable'):
        # [H1-R2/B] Registro dinámico del motor (archivo en escritura al
        # registrarse): la propiedad se acredita por IDENTIDAD, igual que la
        # semántica C-R1 de `propiedad_de_6g1` (el sello sólo se exige en
        # registros estable=True). Sin identidad no habría propiedad.
        return True, 'propiedad_acreditada (registro dinámico sin sello)'
    if st.st_size != reg.get('size') or st.st_mtime_ns != reg.get('mtime_ns'):
        return False, 'tamaño/mtime distintos de los registrados'
    sha, err = _sha_via_descriptor_6g1(nombre, fd_dir, st)
    if err:
        return False, err
    if sha != reg.get('sha256'):
        return False, 'contenido modificado tras el registro'
    return True, 'propiedad_acreditada'


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
                # [6G.1-R/H1-R2/B] Clasificación EXCLUSIVAMENTE por
                # descriptor (sin re-consultar rutas): identidad relativa al
                # descriptor contra el registro; `ruta_esperada` sólo como
                # clave de comparación del registro.
                ruta_esperada = os.path.join(str(run_dir), rel)
                propia, motivo_p = _clasificar_entrada_6g1(nombre, st,
                                                           fd_base,
                                                           ruta_esperada)
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


# ---------------------------------------------------------------------------
# [6G.1-R/CV] Ciclo de vida: protocolo ÚNICO de aborto de corrida (hallazgo A)
# ---------------------------------------------------------------------------

class FalloCorrida6G1(RuntimeError):
    """[6G.1-R/CV] Fallo de corrida ya clasificado por el motor.

    Lo eleva el motor en los puntos de fallo conocidos (apertura del Mix antes
    del DSP, guarda final de integridad, publicación segura) para que TODOS
    los fallos converjan en el mismo manejador y en `abortar_corrida_6g1()`.
    `trasladar=False` conserva el provisional en su ubicación aunque el
    registro del aborto haya podido escribirse (p. ej. si falló el propio
    mecanismo de publicación atómica)."""

    def __init__(self, motivo, detalle=None, trasladar=True):
        RuntimeError.__init__(self, motivo if detalle is None
                              else '%s: %s' % (motivo, detalle))
        self.motivo = motivo
        self.detalle = detalle
        self.trasladar = bool(trasladar)


def cerrar_recursos_6g1(*recursos):
    """[6G.1-R/CV] Cierra, sin propagar errores, descriptores de lectura
    (MixHandle, SoundFile) o colecciones de ellos (dict/list). No toca
    archivos en disco; sólo libera descriptores antes del aborto."""
    for r in recursos:
        if r is None:
            continue
        if isinstance(r, dict):
            cerrar_recursos_6g1(*list(r.values()))
            continue
        if isinstance(r, (list, tuple)):
            cerrar_recursos_6g1(*list(r))
            continue
        try:
            r.close()
        except Exception:
            pass


def _registro_aborto_verificado_6g1(fd_dir, motivo):
    """[6G.1-R/CV] Relee `ABORT_6G1.json` ANCLADO al descriptor del
    directorio acreditado (O_NOFOLLOW + fstat regular) y comprueba que es el
    registro de ESTE aborto: schema abort-6g1/3, mismo motivo,
    resultados_validos=[] y directorio_acreditado=True."""
    try:
        fd = os.open('ABORT_6G1.json',
                     os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd_dir)
    except OSError as exc:
        return False, 'ABORT_6G1.json no legible de forma segura: %s' % exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            return False, 'ABORT_6G1.json no es un archivo regular'
        partes = []
        while True:
            b = os.read(fd, 1 << 16)
            if not b:
                break
            partes.append(b)
        datos = json.loads(b''.join(partes).decode('utf-8'))
    except (OSError, ValueError) as exc:
        return False, 'ABORT_6G1.json no verificable: %s' % exc
    finally:
        os.close(fd)
    if not isinstance(datos, dict):
        return False, 'ABORT_6G1.json sin objeto JSON'
    if (datos.get('schema') != 'abort-6g1/3' or datos.get('motivo') != motivo
            or datos.get('resultados_validos') != []
            or datos.get('directorio_acreditado') is not True):
        return False, 'ABORT_6G1.json no corresponde a este aborto'
    return True, 'ABORT_6G1.json escrito y verificado sobre el descriptor acreditado'


def abortar_corrida_6g1(run_dir, destino_aborto, motivo, detalle=None,
                        trasladar=True, cierre=None):
    """[6G.1-R/CV] Protocolo ÚNICO de aborto de los tres motores.

    1. Registra SIEMPRE primero el aborto con `abortar_6g1()` (C-R1: sin
       eliminación; salidas propias invalidadas y conservadas;
       `resultados_validos=[]`; `analysis.json` intacto; schema abort-6g1/3;
       anclaje H1 del directorio).
    2. Sólo si el directorio quedó acreditado Y `ABORT_6G1.json` se escribió
       de forma segura (y se relee y verifica sobre el MISMO descriptor
       acreditado) se considera el aborto registrado.
    3. Sólo si el aborto quedó registrado, se solicitó traslado y la ruta
       sigue designando el MISMO directorio acreditado (lstat vs fstat del
       descriptor anclado, justo antes de renombrar), el provisional se
       traslada a `destino_aborto` exclusivamente con `publicar_dir_6g1()`
       (renameat2 RENAME_NOREPLACE: nunca reemplaza un destino existente;
       ante colisión, sufijo libre; sin degradación a os.rename).
    4. En cualquier otro caso el provisional se CONSERVA en su ubicación
       original: no se intenta trasladar una ruta cuya identidad no pudo
       acreditarse ni un directorio sin registro de aborto.

    Nunca publica la corrida como exitosa ni elimina archivos. Devuelve un
    dict de resultado (no se escribe en disco: el registro en disco es
    `ABORT_6G1.json`, schema abort-6g1/3 sin cambios)."""
    origen = os.path.abspath(str(run_dir))
    res = dict(motivo=motivo, provisional=origen,
               destino_solicitado=(os.path.abspath(str(destino_aborto))
                                   if destino_aborto else None),
               traslado_solicitado=bool(trasladar and destino_aborto),
               abort_registrado=False, trasladado=False,
               traslado_verificado=False, ruta_final=origen,
               salidas_invalidadas=[], motivo_conservacion=None)
    # [6G.1-R/CR] El registro del aborto exige el cierre previo de los
    # recursos de escritura (preparar_aborto_6g1). Si el cierre quedó
    # incompleto o aún hay descriptores de escritura / mapeos abiertos bajo el
    # provisional, el aborto SE REGISTRA igualmente, pero el directorio NUNCA
    # se traslada (un descriptor abierto seguiría escribiendo en la ruta
    # trasladada).
    try:
        abiertos = escritura_abierta_bajo_dir_6g1(origen)
    except Exception as exc:
        abiertos = ['no observable: %s: %s' % (type(exc).__name__, exc)]
    res['escritura_abierta_al_registrar'] = abiertos
    if cierre is not None:
        res['cierre_recursos_completo'] = bool(cierre.get('completo'))
        if not cierre.get('completo'):
            res['traslado_bloqueado'] = ('cierre de recursos incompleto: %s'
                                         % '; '.join(cierre.get('errores') or ['?']))
    if abiertos and not res.get('traslado_bloqueado'):
        res['traslado_bloqueado'] = ('descriptores de escritura o mapeos '
                                     'abiertos bajo el provisional: %s' % abiertos)
    try:
        info = abortar_6g1(origen, motivo, detalle)
    except Exception as exc:
        res['motivo_conservacion'] = ('abortar_6g1 no completó (%s: %s); '
                                      'provisional conservado en su ubicación'
                                      % (type(exc).__name__, exc))
        return res
    res['salidas_invalidadas'] = list(info.get('salidas_invalidadas', []))
    res['anclaje_directorio'] = info.get('anclaje_directorio')
    if not info.get('directorio_acreditado'):
        res['motivo_conservacion'] = ('directorio no acreditado (%s): sin '
                                      'escritura y sin traslado'
                                      % info.get('anclaje_directorio'))
        return res
    if 'ABORT_6G1.json' in (info.get('motivos_propiedad') or {}):
        res['motivo_conservacion'] = ('registro de aborto no escrito de forma '
                                      'segura (%s): provisional conservado en '
                                      'su ubicación'
                                      % info['motivos_propiedad']['ABORT_6G1.json'])
        return res
    fd_dir, motivo_anclaje = _anclar_dir_aborto_6g1(origen)
    if fd_dir is None:
        res['motivo_conservacion'] = ('identidad no re-acreditada tras el '
                                      'registro (%s): sin traslado'
                                      % motivo_anclaje)
        return res
    try:
        ok, motivo_reg = _registro_aborto_verificado_6g1(fd_dir, motivo)
        res['verificacion_registro'] = motivo_reg
        if not ok:
            res['motivo_conservacion'] = ('registro de aborto no verificable '
                                          '(%s): provisional conservado en su '
                                          'ubicación' % motivo_reg)
            return res
        res['abort_registrado'] = True
        if res['traslado_solicitado'] and res.get('traslado_bloqueado'):
            res['motivo_conservacion'] = ('%s: provisional conservado en su '
                                          'ubicación' % res['traslado_bloqueado'])
            return res
        if not res['traslado_solicitado']:
            res['motivo_conservacion'] = ('traslado no solicitado: provisional '
                                          'conservado en su ubicación')
            return res
        st_dir = os.fstat(fd_dir)
        try:
            st_ruta = os.lstat(origen)
        except OSError as exc:
            res['motivo_conservacion'] = ('ruta del provisional no observable '
                                          '(%s): sin traslado' % exc)
            return res
        if (not stat.S_ISDIR(st_ruta.st_mode)
                or (st_ruta.st_dev, st_ruta.st_ino) != (st_dir.st_dev, st_dir.st_ino)):
            res['motivo_conservacion'] = ('la ruta ya no designa el directorio '
                                          'acreditado: sin traslado')
            return res
        try:
            destino = publicar_dir_6g1(origen, res['destino_solicitado'])
        except Exception as exc:
            res['motivo_conservacion'] = ('traslado atómico sin reemplazo no '
                                          'garantizado (%s: %s): provisional '
                                          'conservado en su ubicación'
                                          % (type(exc).__name__, exc))
            return res
        res['trasladado'] = True
        res['ruta_final'] = destino
        try:
            st_dest = os.lstat(destino)
            res['traslado_verificado'] = (
                (st_dest.st_dev, st_dest.st_ino) == (st_dir.st_dev, st_dir.st_ino))
        except OSError:
            res['traslado_verificado'] = False
        return res
    finally:
        os.close(fd_dir)


def resumen_aborto_6g1(res):
    """[6G.1-R/CV] Línea de log del resultado de `abortar_corrida_6g1()`."""
    return ('motivo=%s abort_registrado=%s trasladado=%s ruta=%s '
            'salidas_invalidadas=%d%s'
            % (res.get('motivo'), res.get('abort_registrado'),
               res.get('trasladado'), res.get('ruta_final'),
               len(res.get('salidas_invalidadas') or []),
               '' if not res.get('motivo_conservacion')
               else ' conservacion=%s' % res['motivo_conservacion']))


# ---------------------------------------------------------------------------
# [6G.1-R/CR] Cierre DETERMINISTA de recursos antes del aborto
# ---------------------------------------------------------------------------
# Orden obligatorio en los tres motores:
#   1. escritores WAV de todos los CandidateRunner construidos (close():
#      cabecera RIFF finalizada);
#   2. memmaps: flush() y cierre EXPLÍCITO del mmap subyacente;
#   3. descriptores de lectura (MixHandle, SoundFile de guías);
#   4. registro del resultado en engine_log.txt y cierre del log;
#   5. comprobación en /proc/self/fd y /proc/self/maps;
#   6. sólo entonces abortar_corrida_6g1() (registro -> eventual traslado).
# No se confía en __del__ ni en la recolección: cada recurso se cierra con una
# llamada explícita y su estado se verifica. Ningún error de cierre se
# propaga: queda documentado y el aborto continúa. [CR-R1] CUALQUIER fallo o
# cierre no verificado de un escritor, memmap, lector o del log marca el
# cierre como incompleto (`completo=False`): ABORT_6G1.json se registra igual,
# pero el provisional NO se traslada (fail-closed; nunca publicación ni
# eliminación).


def _bajo_dir_6g1(ruta):
    base = os.path.realpath(str(ruta))
    return base, base.rstrip(os.sep) + os.sep


def descriptores_bajo_dir_6g1(ruta):
    """Descriptores abiertos del proceso cuyo destino es `ruta` o está bajo
    ella (Linux: /proc/self/fd + flags de /proc/self/fdinfo). Devuelve una
    lista de dicts (fd, ruta relativa, escritura) o None si no es observable."""
    base, pref = _bajo_dir_6g1(ruta)
    try:
        nombres = os.listdir('/proc/self/fd')
    except OSError:
        return None
    res = []
    for s in nombres:
        try:
            dest = os.readlink('/proc/self/fd/' + s)
        except OSError:
            continue
        if dest != base and not dest.startswith(pref):
            continue
        escritura = None
        try:
            with open('/proc/self/fdinfo/' + s, encoding='ascii') as f:
                for linea in f:
                    if linea.startswith('flags:'):
                        fl = int(linea.split()[1], 8)
                        escritura = (fl & os.O_ACCMODE) in (os.O_WRONLY, os.O_RDWR)
        except (OSError, ValueError):
            pass
        res.append(dict(fd=int(s), ruta=os.path.relpath(dest, base),
                        escritura=escritura))
    return res


def mapeos_bajo_dir_6g1(ruta):
    """Archivos bajo `ruta` con un mapeo de memoria vivo en el proceso
    (/proc/self/maps). None si no es observable."""
    base, pref = _bajo_dir_6g1(ruta)
    try:
        with open('/proc/self/maps', encoding='utf-8', errors='replace') as f:
            lineas = f.read().splitlines()
    except OSError:
        return None
    res = set()
    for linea in lineas:
        partes = linea.split(None, 5)
        if len(partes) == 6:
            p = partes[5].strip()
            if p.endswith(' (deleted)'):
                p = p[:-len(' (deleted)')]
            if p == base or p.startswith(pref):
                res.add(os.path.relpath(p, base))
    return sorted(res)


def escritura_abierta_bajo_dir_6g1(ruta, excluir=()):
    """Lista legible de descriptores con permiso de escritura (o de modo no
    determinable) y de mapeos vivos bajo `ruta`; [] si no hay ninguno."""
    out = []
    for d in descriptores_bajo_dir_6g1(ruta) or []:
        if d['ruta'] in excluir or d['escritura'] is False:
            continue
        out.append('fd %d (%s): %s' % (d['fd'], 'escritura' if d['escritura']
                                        else 'modo desconocido', d['ruta']))
    for m in mapeos_bajo_dir_6g1(ruta) or []:
        if m not in excluir:
            out.append('mapeo: %s' % m)
    return out


def _cerrado_6g1(obj):
    """True/False si el estado de cierre es verificable; None si no."""
    if isinstance(obj, MixHandle):
        return (object.__getattribute__(obj, '_snd') is None
                and getattr(obj, 'fd', None) is None)
    c = getattr(obj, 'closed', None)
    return c if isinstance(c, bool) else None


def _cerrar_idempotente_6g1(obj):
    """close() sólo si no está ya cerrado; un segundo cierre nunca falla.
    Devuelve (cerrado_verificado, error_o_None)."""
    err = None
    try:
        if _cerrado_6g1(obj) is not True:
            obj.close()
    except Exception as exc:
        err = '%s: %s' % (type(exc).__name__, exc)
    return _cerrado_6g1(obj), err


def cerrar_recursos_corrida_6g1(runners=None, memmaps=None, lectores=None):
    """[6G.1-R/CR] Cierra de forma determinista e idempotente los recursos
    de una corrida, en orden: escritores WAV de los CandidateRunner (cabecera
    finalizada por close()), memmaps (flush() + close() explícito del mmap
    subyacente; las entradas se retiran del diccionario del motor para soltar
    su referencia, el contenido lógico no se toca) y descriptores de lectura.
    Nunca propaga errores: devuelve un informe con el orden de los pasos, los
    errores y `completo`.

    [CR-R1] `completo` es True sólo si TODOS los recursos recibidos quedaron
    cerrados y verificados: cada escritor WAV, cada memmap (flush + mmap
    cerrado; un memmap con referencias activas NO se cierra y cuenta como
    incompleto) y cada lector. Un fallo de cierre de un lector, o un lector
    cuyo estado de cierre no es verificable, también deja `completo=False`.
    (El cierre del log y la comprobación en /proc se añaden en
    preparar_aborto_6g1.)"""
    inf = dict(orden=[], errores=[], completo=True, escritores=0,
               memmaps=0, lectores=0)

    def paso(tipo, recurso, accion, ok, error=None, critico=True):
        e = dict(paso=len(inf['orden']) + 1, tipo=tipo, recurso=recurso,
                 accion=accion, ok=ok)
        if error:
            e['error'] = error
            inf['errores'].append('%s %s (%s): %s' % (tipo, recurso, accion, error))
        if critico and ok is not True:
            inf['completo'] = False
            if not error:
                inf['errores'].append('%s %s (%s): cierre no verificado'
                                      % (tipo, recurso, accion))
        inf['orden'].append(e)

    # 1. escritores WAV de todos los CandidateRunner ya construidos
    for r in list(runners or []):
        for attr in ('writer_sdv', 'writer_sdi'):
            w = getattr(r, attr, None)
            if w is None:
                continue
            nombre = getattr(w, 'name', None) or '%s/%s' % (
                getattr(r, 'cand_id', '?'), attr)
            ok, err = _cerrar_idempotente_6g1(w)
            inf['escritores'] += 1
            paso('escritor_wav', str(nombre), 'close (cabecera finalizada)', ok, err)
    # 2. memmaps: flush + cierre explícito del mmap subyacente
    if isinstance(memmaps, dict):
        for clave in sorted(memmaps, key=str):
            arr = memmaps.pop(clave)
            nombre = str(getattr(arr, 'filename', None) or clave)
            inf['memmaps'] += 1
            try:
                arr.flush()
                paso('memmap', nombre, 'flush', True)
            except Exception as exc:
                paso('memmap', nombre, 'flush', False,
                     '%s: %s' % (type(exc).__name__, exc))
            m = getattr(arr, '_mmap', None)
            # mmap.close() NO falla aunque existan arrays que apunten a la
            # región (numpy no retiene el buffer exportado): cerrar con otras
            # referencias vivas dejaría memoria inválida en uso. Por eso se
            # exige ser el ÚNICO titular (esta variable + el argumento de
            # getrefcount); si no, sólo flush, error documentado y sin cierre.
            refs = sys.getrefcount(arr) - 2
            del arr
            if m is None:
                paso('memmap', nombre, 'close (sin mmap subyacente)', True)
                continue
            if refs > 0:
                paso('memmap', nombre, 'close mmap', False,
                     'referencias activas al memmap (%d); no se cierra para no '
                     'invalidar memoria en uso; sigue mapeado' % refs)
                del m
                continue
            try:
                m.close()               # idempotente: cerrar dos veces no falla
                paso('memmap', nombre, 'close mmap', bool(m.closed))
            except Exception as exc:
                paso('memmap', nombre, 'close mmap', False,
                     '%s: %s' % (type(exc).__name__, exc))
            del m
    elif memmaps:
        paso('memmap', repr(type(memmaps)), 'close', False,
             'colección no soportada (se esperaba dict)')
    # 3. descriptores de lectura. [CR-R1] Críticos como el resto: un lector que
    #    no se cierra (o cuyo cierre no es verificable) marca el cierre como
    #    incompleto y bloquea el traslado.
    pendientes = [lectores]
    while pendientes:
        x = pendientes.pop(0)
        if x is None:
            continue
        if isinstance(x, dict):
            pendientes.extend(x.values())
            continue
        if isinstance(x, (list, tuple)):
            pendientes.extend(x)
            continue
        nombre = str(getattr(x, 'path', None) or getattr(x, 'name', None) or repr(x))
        ok, err = _cerrar_idempotente_6g1(x)
        inf['lectores'] += 1
        paso('lector', nombre, 'close', ok, err)
    return inf


def resumen_cierre_6g1(inf):
    return ('escritores=%d memmaps=%d lectores=%d completo=%s errores=%d'
            % (inf.get('escritores', 0), inf.get('memmaps', 0),
               inf.get('lectores', 0), inf.get('completo'),
               len(inf.get('errores') or [])))


def preparar_aborto_6g1(run_dir, log=None, cerrar_log=None, runners=None,
                        memmaps=None, lectores=None):
    """[6G.1-R/CR] Paso previo OBLIGATORIO a abortar_corrida_6g1() en los
    tres motores: cierra los recursos (cerrar_recursos_corrida_6g1), deja el
    resultado y cualquier error en engine_log.txt, cierra el log y verifica
    que no queda ningún descriptor de escritura ni mapeo bajo el
    provisional. Nunca propaga errores. Devuelve el informe que se pasa como
    `cierre=` a abortar_corrida_6g1().

    [CR-R1] `completo` describe TODOS los recursos exigidos antes del registro:
    es True sólo si (a) cerrar_recursos_corrida_6g1 cerró y verificó cada
    escritor, memmap y lector; (b) el cierre del log (`cerrar_log`) no
    falló; y (c) no queda ningún descriptor de escritura ni mapeo bajo el
    provisional, ni antes ni después de cerrar el log. Con `completo=False`
    abortar_corrida_6g1() registra el aborto pero NO traslada."""
    try:
        inf = cerrar_recursos_corrida_6g1(runners, memmaps, lectores)
    except Exception as exc:        # defensa: nunca impedir el aborto
        inf = dict(orden=[], errores=['cierre de recursos interrumpido: %s: %s'
                                      % (type(exc).__name__, exc)],
                   completo=False, escritores=0, memmaps=0, lectores=0)
    try:
        previo = escritura_abierta_bajo_dir_6g1(run_dir, excluir=('engine_log.txt',))
    except Exception as exc:
        previo = ['no observable: %s' % exc]
    if previo:
        inf['completo'] = False
        inf['errores'].append('escritura abierta tras el cierre: %s' % previo)
    if log is not None:
        try:
            log('[6G.1-R/CR] cierre de recursos previo al aborto: %s'
                % resumen_cierre_6g1(inf))
            for e in inf['errores']:
                log('[6G.1-R/CR] ERROR de cierre (documentado; el aborto '
                    'continúa sin traslado): %s' % e)
            log('[6G.1-R/CR] se cierra engine_log.txt; a continuación se '
                'registra el aborto')
        except Exception:
            pass
    if cerrar_log is not None:
        try:
            cerrar_log()
            inf['log_cerrado'] = True
        except Exception as exc:
            # [CR-R1] el log ya no está disponible para documentarlo: queda en
            # el informe (y en el motivo de conservación del resultado del
            # aborto) y el cierre pasa a incompleto -> sin traslado.
            inf['log_cerrado'] = False
            inf['completo'] = False
            inf['errores'].append('cierre del log: %s: %s' % (type(exc).__name__, exc))
    try:
        final = escritura_abierta_bajo_dir_6g1(run_dir)
    except Exception as exc:
        final = ['no observable: %s' % exc]
    inf['escritura_abierta_al_registrar'] = final
    if final:
        inf['completo'] = False
        inf['errores'].append('escritura abierta al registrar: %s' % final)
    return inf
