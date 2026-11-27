#!/usr/bin/env python3
"""Batería 6G.1 / AI: auditoría integral — cierre real de wrappers y retención
de abortos (instrucción de Cris sobre 6a93e4e).

Escenarios (inyector: scripts/inyeccion_auditoria_6g1/ejecutar_motor_auditoria.py),
cada uno sobre Hardened, EVO y MQR:
  A1/A2  fallo real del cierre de un escritor WAV en la finalización normal
         (A1: antes del cierre físico; A2: después, como soundfile cuando
         sf_close devuelve error) -> aborto, completo=False, sin traslado.
  B1/B2  fallo del cierre interno del lector del Mix (MixHandle) en la
         guarda final -> aborto, completo=False, sin traslado.
  C1/C2  fallo de Tee.close() en el camino normal (antes / después del
         cierre físico) -> aborto, completo=False, log_cerrado=False, error en
         el informe y en el motivo de conservación, sin traslado.
  D1     fallo al abrir el segundo escritor de un CandidateRunner después de
         abrir el primero -> el primer escritor se conoce, se cierra y se
         invalida; con todo cerrado y acreditado el aborto se traslada.
  D2     D1 + fallo del cierre de ese primer escritor -> completo=False, sin
         traslado.
  E1     fallo de la guarda final de integridad del Mix después de generar
         masks/ -> aborto sin traslado y masks/ CONSERVADA.

Todas las corridas usan una COPIA del Mix en la carpeta de trabajo (E1 la
altera; los fixtures no se tocan) y `--mode full_processing`
(+ `--keep-masks` en Hardened/EVO sólo en E1, para que exista masks/; MQR la
crea siempre).

Comprobaciones por caso: código (nunca EXIT_OK); inyección realizada;
protocolo de aborto ejecutado; `completo` y `log_cerrado` esperados; error
inyectado en el informe de cierre y (sin traslado) en el motivo de
conservación; ABORT_6G1.json schema /3, motivo, resultados_validos=[];
traslado sólo si cierre e integridad están acreditados; provisional
conservado; ningún archivo eliminado; ninguna publicación como éxito; en la
ENTRADA del registro ningún descriptor ni mapeo bajo la salida ni sobre las
entradas, escritores y lectores cerrados y memmaps liberados (/proc); ningún
cierre después del registro; SHA estable tras el registro (y tras terminar el
proceso); recolector cíclico deshabilitado en todo el proceso
(gc.disable(); 0 colecciones posteriores, vía gc.callbacks).

`--base DIR --etiqueta-base X` repite la batería sobre otra copia de los
motores (diagnóstico; no cambia el veredicto).
Evidencia: evidence/pruebas_auditoria_cierre_6g1.json,
           evidence/matriz_auditoria_cierre_6g1.csv,
           evidence/inyecciones_auditoria_6g1/<motor>_<esc>.json (estado
           completo de cada inyección sobre los motores corregidos).
Salida 0 sólo si todos los casos sobre los motores corregidos dan PASS.

ADAPTACIÓN SEGURA (esta propuesta, PENDIENTE_REVISION_CRIS)
--------------------------------------------------------------------------
Parte exclusivamente de este mismo archivo original (31f724b3...). Cambios,
todos documentados en el informe:

  1. Se eliminan las rutas globales EV, EV_INY y TRABAJO. Las tres llegan por
     argumento obligatorio: --evidence-dir y --work-root.
  2. Se anade --raiz-oficial obligatorio. NO se infiere con RAIZ.parent: se
     verifica por contenido (.git) y por dev/ino.
  3. Se eliminan los dos shutil.rmtree (el del arbol de trabajo por escenario
     y el de EV_INY). No se introduce ninguna otra eliminacion recursiva.
  4. Toda escritura pasa a ser exclusiva: no se sobrescribe nada.
  5. ejecutar() y bateria() reciben las rutas como parametro.
  6. Se anade el detector estatico del hallazgo F con estado no concluyente.
  7. ESCENARIOS, CHECKS_F, atribucion_f, args_motor, verificar y el orden de las
     comprobaciones NO cambian. Los motores y el inyector no se tocan.
"""
import argparse
import ast
import csv
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, sha_file, entorno  # noqa: E402
from pruebas_cierre_recursos_6g1 import riff, inventario, ident, leer_abort  # noqa: E402

# Rutas de datos: NINGUNA global. EV/EV_INY/TRABAJO se han eliminado.
# Llegan por argumento obligatorio y se validan antes de escribir nada.
EJECUTOR = RAIZ / 'scripts' / 'inyeccion_auditoria_6g1' / 'ejecutar_motor_auditoria.py'
# ---------------------------------------------------------------------------
# AISLAMIENTO. Nada de este bloque escribe: solo inspecciona el sistema de archivos.
# La raíz oficial NO se infiere nunca de este archivo; llega por argumento
# obligatorio y se verifica antes de usarse.
# ---------------------------------------------------------------------------
EXIT_OK, EXIT_PROCESSING, EXIT_RECHAZO = 0, 2, 2
EXC = 'EXCEPCION_DURANTE_EL_PROCESAMIENTO'
MIXC = 'MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO'
HISTORICO = ('/', 'tmp', 'f6g1ai')


class RechazoRutas(Exception):
    """Ruta rechazada. Siempre se traduce a EXIT_RECHAZO sin haber escrito."""


def _abs_sin_puntos(valor, etiqueta):
    """Absoluta y sin '..'. Un '..' textual es ambiguo frente a enlaces:
    abspath lo colapsa en texto y realpath lo resuelve de verdad. Se rechaza."""
    s = str(valor)
    if not s:
        raise RechazoRutas('%s: ruta vacia' % etiqueta)
    p = Path(s)
    if '..' in p.parts:
        raise RechazoRutas('%s: contiene ".." (%s)' % (etiqueta, s))
    if not p.is_absolute():
        raise RechazoRutas('%s: no es absoluta (%s)' % (etiqueta, s))
    return Path(os.path.abspath(s))


def _partes_resueltas(p):
    """Componentes de p resolviendo enlaces SOLO en la parte que ya existe.

    Path.resolve() con strict=False devuelve la cola sin resolver y hace pasar
    por limpia una comparacion que no lo es. Aqui se resuelve el ancestro
    existente mas profundo y se le anaden los componentes pendientes tal cual.
    """
    actual, pendiente = Path(p), []
    while True:
        if os.path.lexists(str(actual)):
            real = Path(os.path.realpath(str(actual)))
            return tuple(real.parts) + tuple(reversed(pendiente))
        if actual.parent == actual:
            return tuple(Path(p).parts)
        pendiente.append(actual.name)
        actual = actual.parent


def _solapan(a, b):
    """True si a y b son iguales o uno esta contenido en el otro, comparando
    COMPONENTES. '/a/bc' no cuelga de '/a/b': con texto daria falso positivo."""
    n = min(len(a), len(b))
    return a[:n] == b[:n]


def _censo(p):
    """(st_dev, st_ino) o None. Identidad estable frente a renombrados."""
    try:
        st = os.stat(str(p))
        return (st.st_dev, st.st_ino)
    except OSError:
        return None


def _inodo_en_ancestros(p, objetivo):
    """True si algun ancestro existente de p tiene el inodo de `objetivo`.
    Detecta 'el padre es un enlace al protegido' sin que p exista aun."""
    if objetivo is None:
        return False
    actual = Path(p)
    while True:
        if _censo(actual) == objetivo:
            return True
        if actual.parent == actual:
            return False
        actual = actual.parent


def validar_rutas(oficial, copia, work, ev, base=None):
    """Valida las rutas de la corrida. NO escribe nada y NO borra nada.

    Devuelve dict(ok, motivo, oficial, oficial_id, copia, work, ev, base).
    Cierra de forma segura: cualquier duda deja ok=False y motivo explicito.
    """
    r = dict(ok=False, motivo='', oficial=None, oficial_id=None, copia=None,
             work=None, ev=None, base=None)

    def fallo(msg):
        r['motivo'] = msg
        return r

    # 1. Raiz oficial: explicita, existente, y verificada por contenido (.git).
    try:
        of = _abs_sin_puntos(oficial, 'raiz-oficial')
    except RechazoRutas as exc:
        return fallo(str(exc))
    of_real = Path(os.path.realpath(str(of)))
    if not of_real.is_dir():
        return fallo('raiz-oficial: no es un directorio (%s)' % of_real)
    if not os.path.lexists(str(of_real / '.git')):
        return fallo('raiz-oficial: no es un repositorio, falta .git (%s)' % of_real)
    of_id = _censo(of_real)
    if of_id is None:
        return fallo('raiz-oficial: no se pudo leer dev/ino (%s)' % of_real)
    of_p = tuple(of_real.parts)

    # 2. Copia desechable = la carpeta que contiene este script.
    try:
        cp = _abs_sin_puntos(copia, 'copia')
    except RechazoRutas as exc:
        return fallo(str(exc))
    cp_real = Path(os.path.realpath(str(cp)))
    cp_p = tuple(cp_real.parts)
    cp_id = _censo(cp_real)
    if of_p == cp_p:
        return fallo('copia: la copia ES la raiz oficial (%s)' % cp_real)
    if _solapan(of_p, cp_p):
        return fallo('copia: la copia esta dentro de la raiz oficial (%s)' % cp_real)

    # 3. Destinos: absolutos, sin '..', inexistentes (incluye symlink roto).
    for etiqueta, clave in (('work-root', 'work'), ('evidence-dir', 'ev')):
        try:
            p = _abs_sin_puntos(dict(work=work, ev=ev)[clave], etiqueta)
        except RechazoRutas as exc:
            return fallo(str(exc))
        if os.path.lexists(str(p)):
            que = 'enlace simbolico' if os.path.islink(str(p)) else 'preexistente'
            return fallo('%s: el destino ya existe y es %s (%s)' % (etiqueta, que, p))
        partes = _partes_resueltas(p)
        if _solapan(partes, of_p):
            return fallo('%s: destino dentro de la raiz oficial (%s)' % (etiqueta, p))
        if _solapan(partes, cp_p):
            return fallo('%s: destino dentro de la copia desechable (%s)' % (etiqueta, p))
        if _solapan(partes, HISTORICO):
            return fallo('%s: destino historico prohibido /tmp/f6g1ai (%s)' % (etiqueta, p))
        if _inodo_en_ancestros(p, of_id):
            return fallo('%s: un ancestro resuelve al repositorio oficial (%s)' % (etiqueta, p))
        if _inodo_en_ancestros(p, cp_id):
            return fallo('%s: un ancestro resuelve a la copia desechable (%s)' % (etiqueta, p))
        r[clave] = p

    # 4. Trabajo y evidencias: ni iguales ni anidados.
    if _solapan(_partes_resueltas(r['work']), _partes_resueltas(r['ev'])):
        return fallo('work-root y evidence-dir se solapan (%s / %s)' % (r['work'], r['ev']))
    if _censo(r['work']) is not None or _censo(r['ev']) is not None:
        return fallo('work-root o evidence-dir aparecieron durante la validacion')

    # 5. --base: tampoco puede caer en zona protegida.
    if base is not None:
        try:
            b = _abs_sin_puntos(base, 'base')
        except RechazoRutas as exc:
            return fallo(str(exc))
        if not b.is_dir():
            return fallo('base: no es un directorio (%s)' % b)
        b_p = tuple(Path(os.path.realpath(str(b))).parts)
        if _solapan(b_p, of_p):
            return fallo('base: dentro de la raiz oficial (%s)' % b)
        if _solapan(b_p, cp_p):
            return fallo('base: dentro de la copia desechable (%s)' % b)
        r['base'] = b

    r.update(ok=True, motivo='', oficial=of_real, oficial_id=of_id, copia=cp_real)
    return r


def crear_dir_exclusivo(p, protegidos):
    """Crea p con mkdir atomico (falla si algo aparecio entretanto) y re-verifica
    la cadena de ancestros por dev/ino. Reduce la ventana TOCTOU; no la elimina
    por completo (ver limitaciones). No borra ni sobrescribe nada."""
    p = Path(p)
    if not p.parent.is_dir():
        raise RechazoRutas('%s: el padre no existe (%s)' % (p, p.parent))
    try:
        os.mkdir(str(p), 0o700)
    except FileExistsError:
        raise RechazoRutas('%s: aparecio durante la validacion' % p)
    fd = os.open(str(p), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0)
                 | getattr(os, 'O_NOFOLLOW', 0))
    try:
        st = os.fstat(fd)
        for nombre, objetivo in protegidos:
            if _inodo_en_ancestros(p, objetivo):
                raise RechazoRutas('%s: acabo dentro de %s tras crearse' % (p, nombre))
        return (st.st_dev, st.st_ino)
    finally:
        os.close(fd)


def asegurar_dirs(p, raiz):
    """Crea la cadena de p colgando de raiz, componente a componente. Nunca borra.

    raiz debe EXISTIR y ser directorio. Si p es igual a raiz no hay nada que
    crear y se devuelve sin error (comportamiento idempotente). El caso p == raiz
    solo era un no-op silencioso cuando raiz tampoco existia; aqui se exige.

    Contencion: la ruta se normaliza ANTES de comparar. Path.parents compara la
    forma textual, de modo que 'raiz/../otro' pasaba el filtro y luego se creaba
    fuera de la raiz. Se rechaza cualquier '..' textual y se resuelve la ruta.
    """
    crudo = Path(p)
    if '..' in crudo.parts:
        raise RechazoRutas('%s contiene "..": no se admite' % crudo)
    p = crudo.resolve()
    raiz = Path(raiz).resolve()
    if not raiz.is_dir():
        raise RechazoRutas('%s: la raiz no existe o no es un directorio' % raiz)
    if p == raiz:
        return
    if raiz not in p.parents:
        raise RechazoRutas('%s no cuelga de %s' % (p, raiz))
    actual = raiz
    for parte in p.relative_to(raiz).parts:
        actual = actual / parte
        try:
            os.mkdir(str(actual), 0o700)
        except FileExistsError:
            if os.path.islink(str(actual)) or not actual.is_dir():
                raise RechazoRutas('%s existe y no es un directorio normal' % actual)


def escribir_nuevo(destino, texto):
    """Escribe en exclusiva ('x'): falla si el destino ya existe. Sin sobrescrituras."""
    destino = Path(destino)
    if os.path.lexists(str(destino)):
        raise RechazoRutas('no se sobrescribe: %s ya existe' % destino)
    with open(str(destino), 'x', encoding='utf-8', newline='') as fh:
        fh.write(texto)


def copiar_nuevo(origen, destino):
    """Copia binaria en exclusiva ('xb'): falla si el destino ya existe."""
    destino = Path(destino)
    if os.path.lexists(str(destino)):
        raise RechazoRutas('no se sobrescribe: %s ya existe' % destino)
    with open(str(origen), 'rb') as fi, open(str(destino), 'xb') as fo:
        shutil.copyfileobj(fi, fo)

# esc: (condición, motivo, completo, trasladado, fallo de cierre, log_cerrado,
#       tipo de inyección esperado)
ESCENARIOS = {
    'A1': ('Cierre WAV fallido en la finalización normal (antes del cierre físico)',
           EXC, False, False, True, True, 'cierre_escritor_fallido'),
    'A2': ('Cierre WAV fallido en la finalización normal (después del cierre físico)',
           EXC, False, False, True, True, 'cierre_escritor_fallido'),
    'B1': ('Cierre interno de MixHandle fallido en la guarda final (antes del cierre físico)',
           EXC, False, False, True, True, 'cierre_lector_fallido'),
    'B2': ('Cierre interno de MixHandle fallido en la guarda final (después del cierre físico)',
           EXC, False, False, True, True, 'cierre_lector_fallido'),
    'C1': ('Tee.close() fallido en el camino normal (antes del cierre físico)',
           EXC, False, False, True, False, 'cierre_log_fallido'),
    'C2': ('Tee.close() fallido en el camino normal (después del cierre físico)',
           EXC, False, False, True, False, 'cierre_log_fallido'),
    'D1': ('Construcción de CandidateRunner fallida tras abrir el primer escritor',
           EXC, True, True, False, True, 'apertura_segundo_escritor_fallida'),
    'D2': ('D1 + cierre fallido del primer escritor',
           EXC, False, False, True, True, 'apertura_segundo_escritor_fallida'),
    'E1': ('Guarda final de integridad del Mix fallida tras generar masks/',
           MIXC, True, False, False, True, 'mix_alterado_tras_masks'),
}
ENTRADAS_GUIAS = [FIX / 'vocal_mix.wav', FIX / 'instrumental_mix.wav']
# Hallazgo F (preexistente en 6a93e4e, fuera de A-E, NO corregido): tras
# `for arr in mm.values(): arr.flush()` + `del mm`, la variable de bucle `arr`
# conserva el ÚLTIMO memmap (masks/model_disagreement_map.npy) mapeado y con
# escritura hasta que la función retorna. Comprobaciones que ese recurso afecta:
CHECKS_F = {'completo_esperado', 'informe_sin_errores_de_cierre', 'log_cerrado_esperado',
            'sin_descriptores_ni_mapeos_al_registrar', 'memmaps_liberados_al_registrar',
            'sin_escritura_al_terminar'}
RECURSO_F = 'masks/model_disagreement_map.npy'


def atribucion_f(r, fallos):
    """True si TODOS los fallos están en CHECKS_F y el único recurso con
    escritura abierto al registrar (fd y mapeo) es RECURSO_F."""
    if not fallos:
        return None
    fe = (r['estado'].get('fotos') or {}).get('entrada_abortar') or {}
    abiertos = {os.path.relpath(d['destino'], (r['estado'].get('inyeccion') or {})
                                .get('provisional') or '/')
                for d in fe.get('descriptores_salida_o_entradas', []) if d.get('escritura')}
    abiertos |= {os.path.relpath(m, (r['estado'].get('inyeccion') or {}).get('provisional')
                                 or '/') for m in fe.get('mapeos_bajo_salida', [])}
    vivos = {os.path.basename(m['ruta']) for m in fe.get('memmaps', []) if m['vivo']}
    return (set(fallos) <= CHECKS_F and abiertos == {RECURSO_F}
            and vivos == {os.path.basename(RECURSO_F)})


def args_motor(motor, esc, man, out):
    # masks/ sólo donde el escenario lo exige (E1): en Hardened/EVO se escriben
    # con --keep-masks; MQR las escribe siempre. A-D prueban su objetivo sin
    # el hallazgo F (memmap retenido por la variable de bucle `arr`).
    a = ['--manifest', str(man), '--out', str(out), '--mode', 'full_processing']
    if motor in ('Hardened', 'EVO') and esc == 'E1':
        a.append('--keep-masks')
    return a

# ---------------------------------------------------------------------------
# Detector estatico del hallazgo F.
#
# Analiza la FORMA del codigo. NO ejecuta el motor y NO demuestra nada en
# tiempo de ejecucion. Sigue dos nombres a la vez, que es el punto del hallazgo:
#   cont = diccionario de memmaps (mm)   |   var = variable del bucle y alias
# `del mm` libera el diccionario, pero `arr` retiene el ultimo memmap hasta que
# la funcion retorna. El detector exige la tres cosas y desconfia si duda.
#
# Regla de oro: PASS (CONCLUYENTE_TRUE) solo si TODOS los caminos prueban la
# secuencia. Cualquier camino dudoso impide PASS; nunca se convierte duda en OK.
# ---------------------------------------------------------------------------
F_OK, F_NO, F_DUDOSO = 'CONCLUYENTE_TRUE', 'CONCLUYENTE_FALSE', 'NO_CONCLUYENTE'
_RUIDO, _MUTA, _DEL, _LIB = 'ruido', 'mutacion', 'del', 'liberacion'
_FUGA, _PASA, _COND, _TRY, _INCOMP = 'fuga', 'pasa', 'condicional', 'try', 'incompleto'


def _es_none(nodo):
    return isinstance(nodo, ast.Constant) and nodo.value is None


def _nombres_del(nodo):
    out = set()
    for t in nodo.targets:
        if isinstance(t, ast.Name):
            out.add(t.id)
        elif isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
            out.add(t.value.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                if isinstance(e, ast.Name):
                    out.add(e.id)
    return out


def _raiz(nodo):
    while isinstance(nodo, (ast.Subscript, ast.Attribute)):
        nodo = nodo.value
    return nodo.id if isinstance(nodo, ast.Name) else None


def _alias_de(cuerpo, var):
    """Variables que acaban referenciando el mismo objeto que var (b = arr)."""
    alias, cambio = {var}, True
    while cambio:
        cambio = False
        for s in ast.walk(ast.Module(body=list(cuerpo), type_ignores=[])):
            if isinstance(s, ast.Assign) and len(s.targets) == 1 \
                    and isinstance(s.targets[0], ast.Name) and isinstance(s.value, ast.Name) \
                    and s.value.id in alias and s.targets[0].id not in alias:
                alias.add(s.targets[0].id)
                cambio = True
    return alias


def _pasa_a_funcion(nodo, alias, puras=None):
    """True si el nodo pasa alguna referencia seguida a una llamada.

    Las llamadas de la lista cerrada `puras` (len, id, isinstance, ...) LEEN el
    objeto y no guardan su referencia: no constituyen fuga.
    """
    puras = _LLAMADAS_PURAS if puras is None else puras
    for sub in ast.walk(nodo):
        if isinstance(sub, ast.Call):
            if isinstance(sub.func, ast.Name) and sub.func.id in puras \
                    and not sub.keywords:
                continue
            for arg in list(sub.args) + [k.value for k in sub.keywords]:
                if isinstance(arg, ast.Name) and arg.id in alias:
                    return True
    return False


def _simple(s, cont, alias):
    """Eventos de una sentencia simple."""
    ev = []
    if isinstance(s, ast.Delete) and cont in _nombres_del(s):
        ev.append((_DEL, s.lineno, ''))
    if isinstance(s, ast.Assign):
        t = s.targets[0] if len(s.targets) == 1 else None
        if isinstance(t, ast.Name):
            if _es_none(s.value) and t.id in alias:
                ev.append((_LIB, s.lineno, t.id))
            elif t.id in alias and not isinstance(s.value, ast.Name):
                # Se reasigna con una expresion que puede no ser el memmap.
                ev.append((_MUTA, s.lineno, '%s = expresion' % t.id))
        if _raiz(t) == cont and isinstance(t, (ast.Subscript, ast.Attribute)):
            ev.append((_RUIDO, s.lineno, 'contenido de %s modificado' % cont))
    # Un nombre NUEVO que referencia el mismo objeto retiene el memmap.
    if isinstance(s, ast.Assign) and len(s.targets) == 1 \
            and isinstance(s.targets[0], ast.Name) and isinstance(s.value, ast.Name) \
            and s.value.id in alias and s.targets[0].id in alias \
            and s.targets[0].id != s.value.id:
        ev.append((_FUGA, s.lineno, '%s = %s conserva la referencia'
                   % (s.targets[0].id, s.value.id)))
    if _pasa_a_funcion(s, alias):
        ev.append((_PASA, s.lineno, 'referencia pasada a una funcion'))
    return ev


def alias_base(alias):
    """Conjunto de nombres originales; el primero es la variable de bucle."""
    return set(alias)


def _recorre_iter(nodo, var, cont):
    """True si el bucle itera sobre `cont` con destino `var` (for arr in mm.values)."""
    if not isinstance(nodo, (ast.For, ast.AsyncFor)):
        return False
    if not (isinstance(nodo.target, ast.Name) and nodo.target.id == var):
        return False
    return any(isinstance(x, ast.Name) and x.id == cont for x in ast.walk(nodo.iter))


def _solo_usa(cuerpo, nombre):
    """True si el bucle solo LEE `nombre` (p.ej. solo llama a metodos suyos)."""
    for s in cuerpo:
        for n in ast.walk(s):
            if isinstance(n, ast.Name) and n.id == nombre \
                    and isinstance(n.ctx, (ast.Store, ast.Del)):
                return False
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) \
                    and n.func.id in ('del', 'setattr'):
                return False
    return True


def _tiene(evs, tipo):
    return any(e[0] == tipo for e in evs)


def _flat(cuerpo, cont, alias, avisos):
    """Aplana un bloque en una lista de eventos, marcando la incertidumbre.
    Se usa para bloques que NO contienen el `del`."""
    ev = []
    for s in cuerpo:
        if isinstance(s, ast.Delete) and cont in _nombres_del(s):
            ev.append((_DEL, s.lineno, ''))
            continue
        if isinstance(s, ast.If):
            b = _flat(s.body, cont, alias, avisos)
            o = _flat(s.orelse, cont, alias, avisos)
            rb, ro = _tiene(b, _LIB), _tiene(o, _LIB)
            if s.orelse:
                if rb and ro:
                    ev.extend(b)
                elif rb != ro:
                    ev.append((_INCOMP, s.lineno, 'una rama no libera'))
                    ev.extend(b if rb else o)
                else:
                    ev.extend(b)
                    ev.extend(o)
            elif rb:
                ev.append((_COND, s.lineno, ast.dump(s.test)))
                ev.extend(b)
            else:
                ev.extend(b)
                ev.extend(o)
            continue
        if isinstance(s, ast.Try):
            b = _flat(s.body, cont, alias, avisos)
            if _tiene(b, _LIB):
                avisos.append('la linea %d libera dentro de try: si el cuerpo falla '
                              'antes, la liberacion no se completa' % s.lineno)
                ev.append((_TRY, s.lineno, 'liberacion dentro de try'))
            ev.extend(b)
            for h in s.handlers:
                ev.extend(_flat(h.body, cont, alias, avisos))
            ev.extend(_flat(s.finalbody, cont, alias, avisos))
            continue
        if isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
            if isinstance(s, (ast.For, ast.AsyncFor)) and isinstance(s.target, ast.Name) \
                    and s.target.id in alias:
                # Un bucle con destino `arr` SIEMPRE reasigna arr en cada vuelta.
                # Es lo que hace el flush, pero tambien lo que revive la referencia
                # si ocurre despues de liberarla.
                ev.append((_MUTA, s.lineno, 'el bucle reasigna %s' % s.target.id))
            ev.extend(_flat(s.body, cont, alias, avisos))
            ev.extend(_flat(s.orelse, cont, alias, avisos))
            continue
        if isinstance(s, (ast.With, ast.AsyncWith)):
            # Revision 4: el cuerpo de un `with` es un bloque de sentencias
            # que el detector NO recorria. Un alias creado dentro se perdia y
            # el resultado salia CONCLUYENTE_TRUE. Se evalua cada item como
            # una rama (el __enter__ puede lanzar) y el cuerpo como bloque.
            for it in s.items:
                ev.extend(_flat([ast.Expr(value=it.context_expr)], cont, alias, avisos))
                if it.optional_vars is not None:
                    ev.append((_MUTA, s.lineno,
                               'with ... as liga %s' % ast.unparse(it.optional_vars)))
            ev.extend(_flat(s.body, cont, alias, avisos))
            continue
        if isinstance(s, ast.Match):
            # Revision 4: igual que `with`. Cada `case` es una rama; si alguna
            # no libera, es camino invalido. El sujeto se evalua como ruido.
            ev.extend(_flat([ast.Expr(value=s.subject)], cont, alias, avisos))
            ramas = [_flat(c.body, cont, alias, avisos) for c in s.cases]
            liberan = [_tiene(r, _LIB) for r in ramas]
            if any(liberan) and not all(liberan):
                ev.append((_INCOMP, s.lineno, 'un case no libera'))
            for r in ramas:
                ev.extend(r)
            continue
        ev.extend(_simple(s, cont, alias))
    return ev


def _caminos(cuerpo, cont, alias, avisos, acc=None):
    """Caminos completos hasta `del cont`.

    Regla unica: cada sentencia aporta eventos al camino, sea simple o compuesta.
    Las ramas que pueden contener el `del` se EXPLOTAN (un camino por rama).
    Las que no, se aplanan con _flat y sus eventos se acumulan. Asi el `if
    write_masks:` aporta su `arr = None` al camino que luego ve el `del mm`.
    """
    acc = [] if acc is None else list(acc)
    out = []
    for s in cuerpo:
        if isinstance(s, ast.Delete) and cont in _nombres_del(s):
            out.append(acc + [(_DEL, s.lineno, '')])
            acc = []
            continue
        if isinstance(s, (ast.If, ast.Try)):
            ramas = [('body', s.body), ('orelse', getattr(s, 'orelse', []))]
            if isinstance(s, ast.Try):
                ramas += [('except', h.body) for h in s.handlers]
                ramas.append(('finally', s.finalbody))
            con_del = [(n, b) for n, b in ramas if b and _contiene_del(b, cont)]
            if not con_del:
                ev = _flat([s], cont, alias, avisos)
                if isinstance(s, ast.Try) and _tiene(ev, _LIB):
                    # Solo importa el try si DENTRO se libera: si el cuerpo falla
                    # antes, la liberacion no se completa.
                    avisos.append('try en la linea %d: la rama de exito no prueba '
                                  'que se complete' % s.lineno)
                    acc.append((_TRY, s.lineno, 'body'))
                acc.extend(ev)
                continue
            if isinstance(s, ast.Try):
                avisos.append('la linea %d decide dentro de try: el cuerpo puede '
                              'no completarse' % s.lineno)
            for n, b in con_del:
                base = list(acc)
                if isinstance(s, ast.Try):
                    if n != 'body':
                        # El `del` esta en except/finally: el cuerpo del try
                        # aporta su liberacion, si la hay, antes de llegar ahi.
                        base.extend(_flat(s.body, cont, alias, avisos))
                        base.append((_TRY, s.lineno, n))
                out.extend(_caminos(b, cont, alias, avisos, base))
            # Las ramas que NO contienen el `del` son caminos validos que
            # terminan SIN borrar `mm`. Si la referencia sigue viva ahi, el
            # `del` no esta garantizado y no se puede concluir nada.
            sin_del = [(n, b) for n, b in ramas if n not in [x[0] for x in con_del]]
            for n, b in sin_del:
                ev = _flat(b, cont, alias, avisos) if b else []
                # Esa rama NO borra `mm`. Si la referencia pudo quedar viva en
                # ella (porque ya se libero antes, o porque hay un alias), es un
                # camino completo que termina SIN `del`: no se puede concluir.
                # Y aunque la rama este vacia (`else: pass`), el camino existe.
                con_finally = isinstance(s, ast.Try) and s.finalbody
                if not con_finally and (
                        _tiene(acc, _LIB) or _tiene(ev, _LIB)
                        or _tiene(acc, _FUGA) or _tiene(ev, _FUGA)):
                    out.append(list(acc) + ev
                               + [(_INCOMP, s.lineno, 'rama sin `del` con la referencia viva')])
                    continue
                # Con `finally`, el cuerpo del try no termina el camino: el
                # finally se ejecuta siempre y alli puede estar el `del`.
                # Si no toca la referencia (o solo la crea), su efecto se acumula
                # y el camino sigue hacia el `del` que venga despues.
                if isinstance(s, ast.Try):
                    acc = list(acc) + ev + [(_TRY, s.lineno, n)]
                else:
                    acc = list(acc) + ev
            acc = []
            continue
        if isinstance(s, (ast.For, ast.AsyncFor, ast.While)):
            if _contiene_del(s.body, cont) or _contiene_del(s.orelse, cont):
                out.extend(_caminos(s.body, cont, alias, avisos, list(acc)))
                out.extend(_caminos(s.orelse, cont, alias, avisos, list(acc)))
                acc = []
                continue
            acc.extend(_flat([s], cont, alias, avisos))
            continue
        if isinstance(s, (ast.With, ast.AsyncWith)):
            # Revision 4: el cuerpo de un `with` NO se recorria; sus eventos se
            # perdian y el resultado salia CONCLUYENTE_TRUE aunque dentro se
            # creara un alias. Si el cuerpo contiene el `del`, se explota.
            if _contiene_del(s.body, cont):
                if any(it.optional_vars is not None for it in s.items):
                    acc.append((_MUTA, s.lineno, 'with ... as dentro del bloque'))
                out.extend(_caminos(s.body, cont, alias, avisos, list(acc)))
                acc = []
                continue
            acc.extend(_flat([s], cont, alias, avisos))
            continue
        if isinstance(s, ast.Match):
            # Revision 4: idem con `match`. Cada `case` es una rama; la que no
            # borra y deja viva la referencia es un camino valido sin `del`.
            ramas = [c.body for c in s.cases]
            con_del = [b for b in ramas if b and _contiene_del(b, cont)]
            sin_del = [b for b in ramas if b not in con_del]
            for b in con_del:
                # El `del` de un `case` SOLO se ejecuta si ese case coincide.
                # El camino que lo alcanza es condicional: se marca para que
                # _juzgar no lo de por seguro.
                out.extend(_caminos(b, cont, alias, avisos,
                                    list(acc) + [(_COND, s.lineno,
                                                  'match/case %d' % len(con_del))]))
            for b in sin_del:
                ev = _flat(b, cont, alias, avisos) if b else []
                if _tiene(acc, _LIB) or _tiene(ev, _LIB) \
                        or _tiene(acc, _FUGA) or _tiene(ev, _FUGA):
                    out.append(list(acc) + ev + [(_INCOMP, s.lineno,
                               'case sin `del` con la referencia viva')])
                else:
                    acc.extend(ev)
            if con_del:
                acc = []
            continue
        acc.extend([x for x in _simple(s, cont, alias) if x[0] != _DEL])
    return out


def _contiene_del(cuerpo, cont):
    for s in cuerpo:
        for n in ast.walk(s):
            if isinstance(n, ast.Delete) and cont in _nombres_del(n):
                return True
    return False


def _guarda_de(evento):
    return evento[2] if evento[0] == _COND else None


def _juzgar(camino, guardas_creacion=()):
    """(veredicto, motivo). 'malo' es definitivo; 'dudoso' impide PASS.

    El indice de referencia es la ULTIMA LIBERACION. Todo lo que ocurre DESPUES
    de liberar y ANTES de borrar importa: si la referencia vuelve a quedar viva
    (un bucle que reasigna la variable, un alias que se la queda, una
    reasignacion), el memmap sigue retenido y no se puede concluir.

    No hay excepcion para ningun ejemplo concreto: la regla es "nada puede
    reavivar la referencia entre la liberacion y el borrado".
    """
    tipos = [e[0] for e in camino]
    if _INCOMP in tipos:
        return 'malo', 'hay un camino que termina sin borrar `mm`'
    if _DEL not in tipos:
        return 'malo', 'camino sin `del`'
    if _LIB not in tipos:
        return 'malo', 'no hay liberacion antes de `del`'
    idx_lib = len(tipos) - 1 - tipos[::-1].index(_LIB)
    idx_del = tipos.index(_DEL)
    if idx_lib > idx_del:
        return 'malo', 'la liberacion ocurre despues de `del`'
    posteriores = camino[idx_lib + 1:idx_del + 1]
    reviven = [e for e in posteriores if e[0] in (_FUGA, _MUTA)]
    if reviven:
        cual = 'el bucle' if 'bucle' in reviven[0][2] else reviven[0][2]
        return 'dudoso', ('la referencia puede quedar viva tras liberarla: %s '
                          '(linea %d)' % (cual, reviven[0][1]))
    # Un alias creado antes de la ultima liberacion sigue apuntando al memmap
    # salvo que se libere a si mismo ANTES del `del`. Se sigue nombre a nombre.
    vivas = {}
    for e in camino[:idx_del + 1]:
        if e[0] == _FUGA or (e[0] == _MUTA and ' = ' in e[2]):
            nombre = e[2].split()[0]
            vivas[nombre] = True
        elif e[0] == _LIB and e[2]:
            vivas[e[2]] = False
    quedan = [n for n, v in vivas.items() if v]
    if quedan:
        return 'malo', 'alias vivos al borrar: %s' % ', '.join(sorted(quedan))
    condicionales = [e for e in camino if e[0] == _COND]
    eximidas = [e for e in condicionales if _guarda_de(e) in set(guardas_creacion)]
    if len(eximidas) < len(condicionales):
        return 'dudoso', 'la liberacion depende de una guarda distinta de la creacion'
    if _TRY in tipos:
        return 'dudoso', 'la liberacion esta dentro de try'
    if any(e[0] == _PASA for e in camino):
        return 'dudoso', 'la referencia se pasa a una funcion que puede retenerla'
    if eximidas:
        return 'bueno', 'libera antes de `del` bajo la misma guarda que la creacion'
    return 'bueno', 'libera antes de `del`'


def _veredicto(caminos, aperturas, guardas_creacion=()):
    if not caminos:
        return F_DUDOSO, 'no hay ningun camino que llegue a `del`'
    juicios = [_juzgar(c, guardas_creacion) for c in caminos]
    if all(j[0] == 'bueno' for j in juicios):
        return F_OK, 'todos los caminos (%d) liberan antes de `del`' % len(caminos)
    malos = [j for j in juicios if j[0] == 'malo']
    if malos:
        return F_NO, malos[0][1]
    if aperturas == 0:
        return F_DUDOSO, 'cero aperturas de memmap: exencion vacia'
    return F_DUDOSO, [j for j in juicios if j[0] == 'dudoso'][0][1]


def _es_apertura(nodo):
    """Apertura de memmap: np.load(..., mmap_mode=...) o *_open_memmap(...)."""
    if not isinstance(nodo, ast.Call):
        return False
    if isinstance(nodo.func, ast.Attribute):
        if nodo.func.attr == 'load' and any(k.arg == 'mmap_mode' for k in nodo.keywords):
            return True
        if 'memmap' in nodo.func.attr:
            return True
    if isinstance(nodo.func, ast.Name) and 'memmap' in nodo.func.id:
        return True
    return False


def _guardas_de_creacion(fn):
    """Dumps de las condiciones `if` que encierran alguna apertura de memmap.
    Si la liberacion esta bajo la MISMA guarda, no es una liberacion dudosa:
    se crea y se libera bajo la misma condicion."""
    out = set()

    def es_apertura(nodo):
        return _es_apertura(nodo)

    def recorrer(nodos, guardas, prof=0):
        for n in nodos:
            if prof > 12:
                continue
            nuevas = list(guardas)
            if isinstance(n, ast.If):
                # TODAS las guardas que encierran una apertura cuentan, no solo
                # la inmediata: `if w: ... if w2: mm[...] = _open_memmap(...)`.
                nuevas.append(ast.dump(n.test))
                if any(es_apertura(x) for x in ast.walk(n)):
                    for g in nuevas:
                        out.add(g)
            for campo in ('body', 'orelse', 'finalbody'):
                sub = getattr(n, campo, None)
                if sub:
                    recorrer(sub, nuevas, prof + 1)
            for h in getattr(n, 'handlers', []) or []:
                recorrer(h.body, nuevas, prof + 1)

    recorrer(fn.body, [])
    return sorted(out)


def _contar_aperturas(fn):
    return sum(1 for nodo in ast.walk(fn) if _es_apertura(nodo))


def _recorre(fn, var, cont):
    for n in ast.walk(fn):
        if isinstance(n, (ast.For, ast.AsyncFor)) and isinstance(n.target, ast.Name) \
                and n.target.id == var:
            for x in ast.walk(n.iter):
                if isinstance(x, ast.Name) and x.id == cont:
                    return True
    return False


def _reasignaciones_previas(fn, cont):
    """Rebindings del contenedor o de sus variables de bucle.

    Un nombre queda "vivo" desde su definicion hasta su `del`. Una asignacion a un
    nombre vivo es un rebinding, salvo que sea `= None` (liberacion). Un nombre
    borrado que se vuelve a asignar comienza una vida nueva: eso NO es rebinding
    (es el patron mm = {}; del mm; mm = {}; del mm)."""
    de_bucle = {n.target.id for n in ast.walk(fn)
                if isinstance(n, (ast.For, ast.AsyncFor))
                and isinstance(n.target, ast.Name)}
    nombres = {cont} | de_bucle
    eventos = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id in nombres:
            eventos.append((n.lineno, 1, n.targets[0].id, n.value))
        elif isinstance(n, ast.Delete):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id in nombres:
                    eventos.append((n.lineno, 0, t.id, None))
    eventos.sort(key=lambda e: (e[0], e[1]))
    vivos, fuera = set(de_bucle), []
    for _lineno, es_asig, nombre, valor in eventos:
        if not es_asig:
            vivos.discard(nombre)
            continue
        if nombre not in vivos:
            vivos.add(nombre)
            continue
        if _es_none(valor):
            continue
        fuera.append((nombre, _lineno))
    return fuera


# ---------------------------------------------------------------------------
# Revision 4: contexto de cada REFERENCIA al alias.
#
# El fallo de la revision 3 era que _formas_conservadoras() era una lista
# CERRADA de patrones: lo que no estaba en la lista se ignoraba EN SILENCIO.
# Aqui se invierte la carga de la prueba: para cada aparicion del alias se
# examina su nodo PADRE. Solo se considera INOCUO un conjunto cerrado y
# pequeno de contextos demostrablemente incapaces de retener la referencia.
# Cualquier otro contexto -> construccion no soportada -> NO_CONCLUYENTE.
# ---------------------------------------------------------------------------

# Usos que NO entregan la referencia a nadie:
#   - lectura del objeto para un atributo:   arr.flush  /  arr.shape
#   - lectura del objeto para un subindice:  arr[lo:hi] /  arr[i]
#   - lecturas basicas: len(arr), arr.dtype, ...
# El objeto sigue vivo, pero su referencia NO se ha copiado a otro sitio; el
# detector ya modela la liberacion con `arr = None`. Si el atributo se
# ESCRIBE, el padre es un Assign y cae fuera de esta lista (no inocuo).
# Funciones que LEEN el objeto y no guardan su referencia. Lista cerrada y
# conservadora: solo las que no pueden almacenar el argumento.
_LLAMADAS_PURAS = frozenset({'len', 'id', 'hash', 'repr', 'str', 'type', 'bool',
                             'int', 'float', 'isinstance', 'callable', 'iter',
                             'abs', 'hex', 'oct', 'bin', 'format', 'ascii',
                             'vars', 'dir', 'getattr', 'hasattr', 'sizeof'})

_CONTEXTO_INOCUO = (
    (ast.Attribute, 'value'),      # arr.attr        (lectura)
    (ast.Subscript, 'value'),      # arr[i]          (lectura)
)

# Contextos que se modelan aparte y se informan con su propio nombre.
def _clasificar_contexto(padre, campo, alias):
    """Devuelve (tipo, descripcion) para una referencia al alias en `padre`."""
    # --- formas que RETIENEN la referencia: no soportadas, dudoso ---
    if isinstance(padre, ast.AnnAssign) and campo == 'value':
        return ('anotada', '%s: T = ...' % ast.unparse(padre.target))
    if isinstance(padre, ast.Assign):
        if campo == 'value':
            if len(padre.targets) > 1:
                return ('encadenada', '%s = ...' % ' = '.join(
                    ast.unparse(t) for t in padre.targets))
            t = padre.targets[0]
            if isinstance(t, (ast.Tuple, ast.List)):
                return ('desempaquetado', '%s = ...' % ast.unparse(t))
            if isinstance(t, (ast.Attribute, ast.Subscript)):
                return ('atributo/contenedor', '%s = ...' % ast.unparse(t))
            # `b = arr` (Name simple) NO es una construccion no soportada: es
            # exactamente la fuga que el detector modela con _FUGA. Marcarla
            # aqui la degradaria a "no soportada" y perderia la distincion
            # entre fuga demostrable (CONCLUYENTE_FALSE) y no demostrable.
            return (None, None)
        return ('alias_ensanchado', '... = ... %s ...' % ast.unparse(padre)[:40])
    if isinstance(padre, ast.AugAssign) and campo == 'value':
        return ('augassign', '%s %s= ...' % (ast.unparse(padre.target),
                                             type(padre.op).__name__))
    if isinstance(padre, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) \
            and campo == 'body':
        return ('retorno', 'return ... %s' % ast.unparse(padre)[:40])
    if isinstance(padre, ast.Return) and campo == 'value':
        return ('retorno', 'return ...')
    if isinstance(padre, ast.Yield) and campo == 'value':
        return ('yield', 'yield ...')
    if isinstance(padre, ast.YieldFrom) and campo == 'value':
        return ('yield_from', 'yield from ...')
    if isinstance(padre, ast.NamedExpr) and campo == 'value':
        return ('namedexpr', '%s := ...' % ast.unparse(padre.target))
    if isinstance(padre, ast.Call):
        if campo in ('args', 'keywords'):
            # Funciones PURAS conocidas sobre el objeto: leen, no retienen.
            if isinstance(padre.func, ast.Name) and padre.func.id in _LLAMADAS_PURAS \
                    and campo == 'args' and len(padre.args) == 1 \
                    and not padre.keywords:
                return (None, None)
            return ('paso_a_llamada', '%s(...)' % ast.unparse(padre.func))
        return ('llamada_callee', '%s(...)' % ast.unparse(padre.func))
    if isinstance(padre, (ast.List, ast.Tuple, ast.Set)):
        return ('contenedor_literal', '[...] / (...) / {...}')
    if isinstance(padre, ast.Dict):
        return ('dict_literal', '{...}')
    if isinstance(padre, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        return ('comprehension', type(padre).__name__)
    if isinstance(padre, ast.comprehension):
        return ('comprehension', 'for ... in ...')
    if isinstance(padre, ast.Compare) or isinstance(padre, ast.BoolOp) \
            or isinstance(padre, ast.UnaryOp) or isinstance(padre, ast.IfExp):
        return ('expresion_derivada', ast.unparse(padre)[:38])
    if isinstance(padre, ast.BinOp):
        return ('expresion_derivada', ast.unparse(padre)[:38])
    if isinstance(padre, (ast.Global, ast.Nonlocal)):
        return ('global_nonlocal', ast.unparse(padre))
    if isinstance(padre, ast.With) and campo == 'items':
        return ('with_as', 'with ... as ...')
    if isinstance(padre, ast.keyword):
        return ('paso_a_llamada', '%s=...' % padre.arg)
    # --- lecturas modeladas: no retienen ---
    for tipo, campito in _CONTEXTO_INOCUO:
        if isinstance(padre, tipo) and campo == campito:
            return (None, None)
    # --- cualquier otra cosa: no soportada (fallo cerrado) ---
    return ('contexto_desconocido', '%s.%s' % (type(padre).__name__, campo))


def _formas_conservadoras(fn, alias):
    """Toda referencia al alias debe caer en un contexto INOCUO conocido.

    Devuelve la lista de (tipo, linea, descripcion) de las referencias cuyo
    contexto NO esta modelado como inocuo. Si la lista no esta vacia, no se
    puede emitir CONCLUYENTE_TRUE.

    A diferencia de la revision 3, esto NO es una lista de patrones a buscar:
    es un recorrido de TODAS las apariciones del alias. Lo que no encaje en
    el conjunto cerrado de contextos inocuos, sale aqui. Asi no hay nodo que
    pase inadvertido.
    """
    alias = set(alias)
    fuera = []

    # global/nonlocal guardan NOMBRES EN TEXTO (campos .names), no nodos Name:
    # un recorrido de nodos Name jamas los veria. Se comprueban aparte.
    for nodo in ast.walk(fn):
        if isinstance(nodo, (ast.Global, ast.Nonlocal)):
            for nom in nodo.names:
                if nom in alias:
                    fuera.append(('global_nonlocal', nodo.lineno,
                                  '%s %s' % (type(nodo).__name__.lower(), nom)))
        # `with ... as <alias>` re-liga el propio nombre del alias al objeto que
        # devuelve el contexto: el memmap deja de estar donde el detector cree.
        if isinstance(nodo, (ast.With, ast.AsyncWith)):
            for it in nodo.items:
                if it.optional_vars is not None:
                    objetivos = {n.id for n in ast.walk(it.optional_vars)
                                 if isinstance(n, ast.Name)}
                    choca = objetivos & alias
                    if choca:
                        fuera.append(('with_as_alias', nodo.lineno,
                                      'with ... as %s' % ', '.join(sorted(choca))))

    for padre in ast.walk(fn):
        for campo, valor in ast.iter_fields(padre):
            hijos = valor if isinstance(valor, list) else [valor]
            for h in hijos:
                if not isinstance(h, ast.Name) or h.id not in alias:
                    continue
                if not isinstance(h.ctx, ast.Load):
                    continue          # store/del: los modela el detector
                tipo, desc = _clasificar_contexto(padre, campo, alias)
                if tipo is None:
                    continue          # contexto inocuo demostrado
                fuera.append((tipo, getattr(h, 'lineno', 0), desc))
    return fuera



def _analizar_funcion(fn, cont='mm'):
    out = dict(funcion=fn.name, contenedor=cont, motivo='', avisos=[], variables=[],
               aperturas=_contar_aperturas(fn), caminos=0, vistas={},
               lineas_del=sorted(n.lineno for n in ast.walk(fn)
                                 if isinstance(n, ast.Delete) and cont in _nombres_del(n)))
    if not out['lineas_del']:
        # Solo es relevante si la funcion TRATA `mm` como contenedor de memmaps:
        # un diccionario y un bucle sobre sus valores. Una variable local que se
        # llame `mm` no es el contenedor del hallazgo.
        es_dict = any(isinstance(n, ast.Assign) and len(n.targets) == 1
                      and isinstance(n.targets[0], ast.Name) and n.targets[0].id == cont
                      and isinstance(n.value, ast.Dict) for n in ast.walk(fn))
        itera = any(isinstance(n, (ast.For, ast.AsyncFor))
                    and any(isinstance(x, ast.Name) and x.id == cont
                            for x in ast.walk(n.iter)) for n in ast.walk(fn))
        toca = es_dict and itera
        return dict(out, estado=(F_DUDOSO if toca else 'NO_APLICA'),
                    motivo=('usa `%s` como contenedor y no lo libera' % cont) if toca
                    else 'no usa `%s` como contenedor de memmaps' % cont)
    variables = sorted({n.target.id for n in ast.walk(fn)
                        if isinstance(n, (ast.For, ast.AsyncFor))
                        and isinstance(n.target, ast.Name) and n.target.id != cont})
    variables = [v for v in variables if _recorre(fn, v, cont)]
    if not variables:
        return dict(out, estado=F_DUDOSO,
                    motivo='no se identifico variable de bucle que recorra %s' % cont)
    # Formas que pueden retener el memmap y que el detector no sigue.
    # Se evaluan POR variable de bucle, con su conjunto de alias. Desconfiar
    # siempre es preferible a ignorar en silencio una construccion que conserve
    # la referencia y luego declarar CONCLUYENTE_TRUE.
    formas = {}
    for var in variables:
        f = _formas_conservadoras(fn, _alias_de(fn.body, var))
        if f:
            formas[var] = f
    rebind = _reasignaciones_previas(fn, cont)
    if rebind:
        return dict(out, estado=F_DUDOSO,
                    motivo='reasignaciones que impiden seguir la traza: %s'
                           % ', '.join('%s@%d' % (n, l) for n, l in rebind))
    # Se evaluan TODAS las variables antes de decidir: si hay mas de una sobre el
    # contenedor y alguna no cumple, no se puede saber cual retiene la ultima
    # referencia y el resultado es dudoso, nunca TRUE.
    peor = None
    for var in variables:
        alias = _alias_de(fn.body, var)
        avisos = []
        caminos = _caminos(fn.body, cont, alias, avisos)
        estado, motivo = _veredicto(caminos, out['aperturas'],
                                    _guardas_de_creacion(fn))
        out['avisos'].extend(avisos)
        out['vistas'][var] = dict(estado=estado, motivo=motivo, caminos=len(caminos))
        out['caminos'] = max(out['caminos'], len(caminos))
        if estado == F_OK:
            out['variables'].append(var)
        else:
            orden = {F_DUDOSO: 0, F_NO: 1}
            if peor is None or orden[estado] > orden[peor[0]]:
                peor = (estado, motivo, len(caminos))
    if formas:
        detalle = '; '.join('%s: %s@%d' % (v, f[0][0], f[0][1])
                            for v, f in sorted(formas.items()))
        out['formas'] = {v: [(x, l, d) for x, l, d in f] for v, f in formas.items()}
        return dict(out, estado=F_DUDOSO,
                    motivo='formas no seguidas que pueden retener la referencia: %s'
                           % detalle)
    if out['variables'] and len(variables) > 1:
        malas = [v for v in variables if out['vistas'].get(v, {}).get('estado') != F_OK]
        if malas:
            return dict(out, estado=F_DUDOSO,
                        motivo='varias variables de bucle sobre %s y no todas '
                               'cumplen: %s' % (cont, ', '.join(sorted(malas))))
    if out['variables']:
        v = out['variables'][0]
        return dict(out, estado=F_OK, motivo=out['vistas'][v]['motivo'])
    if peor is None:
        return dict(out, estado=F_DUDOSO, motivo='no se pudo evaluar')
    return dict(out, estado=peor[0], motivo=peor[1])


def _analizar_cadena(fuente, cont='mm'):
    cadena = {}
    for fn in ast.walk(fuente):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cadena[fn.name] = _analizar_funcion(fn, cont)
    con_seq = [n for n, r in cadena.items() if r['estado'] == F_OK]
    con_del = [n for n, r in cadena.items() if r['lineas_del']]
    dudosas = [n for n, r in cadena.items() if r['estado'] == F_DUDOSO]
    aplicables = [n for n, r in cadena.items() if r['estado'] != 'NO_APLICA']
    if dudosas:
        global_, motivo = F_DUDOSO, 'funciones sin decidir: %s' % ', '.join(sorted(dudosas))
    elif con_del and all(n in con_seq for n in con_del):
        global_, motivo = F_OK, 'todas las funciones con `del %s` cumplen' % cont
    elif con_del:
        global_ = F_NO
        motivo = 'no cumplen: %s' % ', '.join(sorted(set(con_del) - set(con_seq)))
    else:
        global_, motivo = F_DUDOSO, 'no se encontro `del %s`' % cont
    return dict(funciones=cadena, con_secuencia=sorted(con_seq), con_del=sorted(con_del),
                dudosas=sorted(dudosas), funciones_aplicables=len(aplicables),
                aperturas_total=sum(r['aperturas'] for r in cadena.values()),
                estado_global=global_, motivo=motivo)


def adjudicacion_hallazgo_f(motores):
    """Adjudica F sobre {nombre: ruta}. Lee y analiza; NO ejecuta.
    La validacion dinamica NO se cierra aqui: queda PENDIENTE."""
    por_motor = {}
    for nombre, ruta in sorted(motores.items()):
        try:
            fuente = ast.parse(Path(ruta).read_text(encoding='utf-8', errors='replace'))
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            por_motor[nombre] = dict(estado_global=F_DUDOSO,
                                     motivo='no analizable: %r' % exc)
            continue
        por_motor[nombre] = _analizar_cadena(fuente)
    estados = {n: r['estado_global'] for n, r in por_motor.items()}
    if not estados or any(e != F_OK for e in estados.values()):
        global_ = F_DUDOSO
        motivo = 'no todos los motores son concluyentes'
    else:
        global_, motivo = F_OK, 'los motores analizados muestran la secuencia completa'
    return dict(es_analisis_estatico=True, motores=por_motor, estados=estados,
                estado_global=global_, motivo=motivo, validacion_dinamica='PENDIENTE',
                nota='El analisis estatico NO cierra la validacion dinamica.')
def ejecutar(motores_dir, motor, esc, etiqueta, trabajo, protegidos=()):
    """Ejecuta UN escenario sobre UN motor. Las rutas llegan como parametro:
    no hay destino global implicito. Sustituye el rmtree original por la
    exigencia de un arbol nuevo (verificacion en bateria())."""
    trabajo = Path(trabajo)
    rel = Path(etiqueta) / motor / esc
    work = trabajo / rel
    if os.path.lexists(str(work)):
        raise RechazoRutas('%s ya existe: no se reutiliza, no se borra' % work)
    asegurar_dirs(work, trabajo)
    out = work / 'out'
    os.mkdir(str(out), 0o700)
    mix = work / 'mix_copia.wav'
    copiar_nuevo(FIX / 'mix.wav', mix)
    # escribir_manifest() de comun_6g1 usa Path.write_text(), que SOBRESCRIBE.
    # El manifiesto se compone en memoria con su misma estructura y se publica
    # en exclusiva: el destino no puede existir antes ni quedar sobrescrito.
    # (Misma forma que comun_6g1.escribir_manifest; no se modifica el original.)
    man = work / 'manifest.json'
    escribir_nuevo(man, json.dumps(dict(
        mix_original=str(mix),
        pairs=[dict(pair_id='P01', family='6G1', variant='V01',
                    configuration='synthetic', source='synthetic',
                    vocal_path=str(ENTRADAS_GUIAS[0]),
                    vocal_guide=str(ENTRADAS_GUIAS[0]),
                    instrumental_path=str(ENTRADAS_GUIAS[1]),
                    instrumental_guide=str(ENTRADAS_GUIAS[1]))])) )
    snap = work / 'estado.json'
    entradas = [mix] + ENTRADAS_GUIAS
    env = dict(os.environ, SDVSDI_AI_SNAP=str(snap), SDVSDI_AI_OUT=str(out),
               SDVSDI_AI_MIX=str(mix),
               SDVSDI_AI_ENTRADAS=os.pathsep.join(str(p) for p in entradas),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    cmd = [sys.executable, '-B', str(EJECUTOR), esc,
           str(Path(motores_dir) / MOTORES[motor])] + args_motor(motor, esc, man, out)
    p = subprocess.run(cmd, cwd=str(motores_dir), env=env, capture_output=True,
                       text=True, timeout=600)
    estado = json.loads(snap.read_text()) if snap.exists() else {}
    return dict(work=work, out=out, codigo=p.returncode, stdout=p.stdout or '',
                stderr=p.stderr or '', estado=estado, cmd=cmd[3:], snap=snap)

def verificar(motor, esc, r):
    cond, motivo_esp, completo_esp, tras_esp, fallo_cierre, logc_esp, tipo_esp = ESCENARIOS[esc]
    e = r['estado']
    ch = {}

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), str(detalle)[:700])

    marca = 'inyeccion AI-%s' % esc
    c('codigo_salida', r['codigo'] == EXIT_PROCESSING, r['codigo'])
    c('nunca_EXIT_OK', r['codigo'] != EXIT_OK, r['codigo'])
    ret = e.get('retorno_run_experiment') or {}
    c('run_experiment_sin_exito', ret.get('codigo') == EXIT_PROCESSING
      and ret.get('ruta_str') is None, ret)
    inj = e.get('inyeccion')
    c('inyeccion_realizada', bool(inj) and inj['detalle'].get('tipo') == tipo_esp,
      inj and inj['detalle'])
    if not inj or not inj.get('provisional'):
        return ch, {}
    prov, final = Path(inj['provisional']), Path(inj['final'])
    pre = e.get('preparar')
    c('protocolo_de_aborto_ejecutado', pre is not None)
    if pre is None:
        return ch, {}
    c('completo_esperado', pre.get('completo') is completo_esp,
      'completo=%s errores=%s' % (pre.get('completo'), pre.get('errores')))
    if fallo_cierre:
        c('error_de_cierre_en_informe', any(marca in str(x) for x in pre.get('errores') or []),
          pre.get('errores'))
    else:
        c('informe_sin_errores_de_cierre', not pre.get('errores'), pre.get('errores'))
    c('log_cerrado_esperado', pre.get('log_cerrado') is logc_esp, pre.get('log_cerrado'))
    ra = e.get('resultado_aborto') or {}
    c('abort_registrado', ra.get('abort_registrado') is True, ra.get('motivo_conservacion'))
    c('traslado_esperado', ra.get('trasladado') is tras_esp,
      (ra.get('trasladado'), ra.get('motivo_conservacion')))
    if not tras_esp and fallo_cierre:
        c('error_en_motivo_de_conservacion', marca in str(ra.get('motivo_conservacion'))
          and 'cierre de recursos incompleto' in str(ra.get('motivo_conservacion')),
          ra.get('motivo_conservacion'))
    if esc == 'E1':
        c('conservacion_por_integridad_sin_traslado',
          ra.get('traslado_solicitado') is False
          and 'traslado no solicitado' in str(ra.get('motivo_conservacion')),
          ra.get('motivo_conservacion'))
    ubic = Path(ra.get('ruta_final') or prov)
    entradas = sorted(os.listdir(r['out']))
    if tras_esp:
        c('trasladado_sin_reemplazo', ubic == Path(str(final) + '_aborted')
          and ubic.is_dir() and not prov.exists() and ident(ubic) == inj['identidad'], ubic.name)
    else:
        c('provisional_conservado_en_su_ubicacion', ubic == prov and prov.is_dir()
          and ident(prov) == inj['identidad'], entradas)
        c('ningun_aborted_creado', not [x for x in entradas if '_aborted' in x], entradas)
    pubs = [x for x in e.get('eventos', []) if x['tipo'] == 'publicar_entrada'
            and not str(x.get('destino', '')).endswith('_aborted')]
    c('sin_publicacion_exitosa', not pubs and final.name not in entradas
      and set(entradas) <= {prov.name, final.name + '_aborted'}, (entradas, pubs))

    ab = leer_abort(ubic) or {}
    c('ABORT_6G1_schema_3', ab.get('schema') == 'abort-6g1/3', ab.get('schema'))
    c('motivo', ab.get('motivo') == motivo_esp, ab.get('motivo'))
    c('resultados_validos_vacio', ab.get('resultados_validos') == [])
    post = inventario(ubic)
    c('ningun_archivo_eliminado', set(inj['archivos']) <= set(post),
      'faltan %s' % sorted(set(inj['archivos']) - set(post)))
    masks = sorted(k for k in inj['archivos'] if k.startswith('masks/'))
    if esc == 'E1':
        c('masks_generadas_y_conservadas', masks and all(k in post for k in masks)
          and all(k in (ab.get('salidas_invalidadas') or []) + (ab.get('conservados') or [])
                  for k in masks), '%d npy: %s' % (len(masks), masks[:4]))

    fe = e.get('fotos', {}).get('entrada_abortar')
    fs = e.get('fotos', {}).get('salida_abortar')
    ff = e.get('fotos', {}).get('fin_proceso')
    c('registro_invocado', fe is not None)
    if fe is None:
        return ch, {}
    c('sin_descriptores_ni_mapeos_al_registrar', fe['descriptores_salida_o_entradas'] == []
      and fe['mapeos_bajo_salida'] == [],
      (fe['descriptores_salida_o_entradas'], fe['mapeos_bajo_salida']))
    c('escritores_cerrados_al_registrar', all(w['cerrado'] for w in fe['escritores']),
      [(os.path.basename(w['ruta']), w['cerrado']) for w in fe['escritores']])
    c('lectores_cerrados_al_registrar', fe['lectores_abiertos'] == [], fe['lectores_abiertos'])
    c('memmaps_liberados_al_registrar', not any(m['vivo'] for m in fe['memmaps']),
      [os.path.basename(m['ruta']) for m in fe['memmaps'] if m['vivo']])
    ev = e.get('eventos', [])
    n_ab = min([x['n'] for x in ev if x['tipo'] == 'abortar_6g1_entrada'] or [10 ** 9])
    n_pre = min([x['n'] for x in ev if x['tipo'] == 'preparar_aborto_entrada'] or [10 ** 9])
    tarde = [x for x in ev if x['n'] > n_ab and x['tipo'] in ('escritor_cerrado', 'lector_cerrado',
                                                              'log_cerrado')]
    c('orden_cierre_antes_del_registro', n_pre < n_ab and not tarde,
      [(x['n'], x['tipo'], os.path.basename(x.get('ruta', '') or '')) for x in ev
       if x['n'] >= inj['n_evento']])
    if ff is not None and fs is not None:
        a_sal = dict(fs['archivos'])
        c('sha_estable_tras_registro', ff['archivos'] == a_sal and post == a_sal,
          sorted(k for k in set(a_sal) | set(post) if a_sal.get(k) != post.get(k)))
        c('sin_escritura_al_terminar', not [d for d in ff['descriptores_salida_o_entradas']
                                            if d['escritura'] is not False]
          and ff['mapeos_bajo_salida'] == [], ff['descriptores_salida_o_entradas'])
    else:
        c('sha_estable_tras_registro', False, 'sin fotos')
    c('sin_gc_en_todo_el_proceso', e.get('gc_deshabilitado_al_inicio') is True
      and e.get('gc_habilitado_al_final') is False
      and all(f.get('gc_habilitado') is False for f in e.get('fotos', {}).values())
      and e.get('gc_colecciones') == e.get('gc_colecciones_al_deshabilitar')
      and e.get('gc_colecciones_posteriores') == [],
      dict(al_deshabilitar=e.get('gc_colecciones_al_deshabilitar'),
           al_final=e.get('gc_colecciones'),
           posteriores=len(e.get('gc_colecciones_posteriores') or [])))

    if esc in ('D1', 'D2'):
        primer = inj['detalle'].get('primer_escritor')
        rel = os.path.relpath(primer, prov) if primer else None
        h = riff(ubic / rel) if rel and (ubic / rel).is_file() else dict(ok=False)
        c('primer_escritor_conocido_cerrado_e_invalidado', rel is not None
          and any(x['tipo'] == 'escritor_cerrado' and x.get('ruta') == primer and x['n'] < n_ab
                  for x in ev)
          and rel in (ab.get('salidas_invalidadas') or [])
          and h.get('ok') and h['riff_size'] == h['tamano'] - 8
          and h['data_offset'] + h['data_size'] == h['tamano'],
          dict(rel=rel, riff=h))
    if esc in ('A1', 'A2'):
        wavs = [k for k in inj['archivos'] if k.endswith('.wav')]
        c('wavs_conservados_e_invalidados', wavs and all(k in post for k in wavs)
          and all(k in (ab.get('salidas_invalidadas') or []) for k in wavs), wavs)
    c('resultado_del_aborto_en_consola', ('trasladado=%s' % tras_esp) in r['stdout'],
      r['stdout'][-300:])
    secuencia = [(x['n'], x['tipo'], os.path.basename(x.get('ruta', '') or ''))
                 for x in ev if x['n'] >= inj['n_evento']]
    extra = dict(inyeccion=inj['detalle'], preparar=dict(completo=pre.get('completo'),
                 log_cerrado=pre.get('log_cerrado'), errores=pre.get('errores')),
                 resultado_aborto=dict(trasladado=ra.get('trasladado'),
                                       ruta_final=ra.get('ruta_final'),
                                       motivo_conservacion=ra.get('motivo_conservacion')),
                 secuencia=secuencia, ubicacion_final=str(ubic),
                 masks_en_inyeccion=len(masks))
    return ch, extra
def bateria(motores_dir, etiqueta, trabajo, ev_iny, guardar_estados=False, ev_raiz=None):
    """Recorre los 27 casos. `trabajo` y `ev_iny` llegan como parametro y se
    propagan: ninguno de los dos es global. Los escenarios, las condiciones y
    `verificar` NO cambian.

    `ev_raiz` es el evidence-dir ya creado. `ev_iny` (inyecciones_auditoria_6g1)
    se crea SIEMPRE bajo `ev_raiz`, nunca pasandose a si misma como raiz: eso
    era un no-op silencioso que dejaba la carpeta sin crear.
    """
    trabajo, ev_iny = Path(trabajo), Path(ev_iny)
    ev_raiz = Path(ev_raiz) if ev_raiz is not None else ev_iny.parent
    filas, detalle = [], {}
    for motor in MOTORES:
        for esc in ESCENARIOS:
            r = ejecutar(motores_dir, motor, esc, etiqueta, trabajo)
            try:
                ch, extra = verificar(motor, esc, r)
            except Exception as exc:
                ch, extra = {'verificador': (False, repr(exc))}, {}
            ok = all(v[0] for v in ch.values())
            fallos = [k for k, v in ch.items() if not v[0]]
            af = atribucion_f(r, fallos)
            detalle['%s/%s' % (motor, esc)] = dict(atribuible_solo_a_hallazgo_F=af,
                condicion=ESCENARIOS[esc][0], codigo=r['codigo'], argumentos=r['cmd'],
                comprobaciones={k: dict(ok=v[0], detalle=v[1]) for k, v in ch.items()},
                veredicto='PASS' if ok else 'FAIL', fallos=fallos, **extra,
                stdout_tail=r['stdout'][-1500:], stderr_tail=r['stderr'][-1500:])
            filas.append(dict(prueba=esc, motor=motor, condicion=ESCENARIOS[esc][0],
                              codigo=r['codigo'],
                              completo=(extra.get('preparar') or {}).get('completo'),
                              log_cerrado=(extra.get('preparar') or {}).get('log_cerrado'),
                              trasladado=(extra.get('resultado_aborto') or {}).get('trasladado'),
                              comprobaciones='%d/%d' % (sum(v[0] for v in ch.values()), len(ch)),
                              fallos=';'.join(fallos), veredicto='PASS' if ok else 'FAIL',
                              atribuible_solo_a_F='' if af is None else af))
            if guardar_estados and r['snap'].exists():
                asegurar_dirs(ev_iny, ev_raiz)
                escribir_nuevo(ev_iny / ('%s_%s.json' % (motor, esc)),
                               r['snap'].read_text(encoding='utf-8'))
            print('%-8s %-3s codigo=%-4s %s %s%s' % (motor, esc, r['codigo'],
                                                     'PASS' if ok else 'FAIL', ','.join(fallos),
                                                     '' if af is None else ' [solo F=%s]' % af),
                  flush=True)
    return filas, detalle


def main(argv=None):
    """Valida las rutas ANTES de tocar nada. Cualquier rechazo sale con codigo 2.
    `--raiz-oficial` es obligatorio: no se infiere de RAIZ.parent."""
    ap = argparse.ArgumentParser()
    ap.add_argument('--raiz-oficial', required=True)
    ap.add_argument('--work-root', required=True)
    ap.add_argument('--evidence-dir', required=True)
    ap.add_argument('--base', default=None)
    ap.add_argument('--etiqueta-base', default='base')
    a = ap.parse_args(argv)
    v = validar_rutas(a.raiz_oficial, RAIZ, a.work_root, a.evidence_dir, a.base)
    if not v['ok']:
        print('RECHAZO de rutas: %s' % v['motivo'], file=sys.stderr)
        return EXIT_RECHAZO
    try:
        crear_dir_exclusivo(v['work'], [('la raiz oficial', v['oficial_id'])])
        crear_dir_exclusivo(v['ev'], [('la raiz oficial', v['oficial_id'])])
        ev_iny = v['ev'] / 'inyecciones_auditoria_6g1'
        asegurar_dirs(ev_iny, v['ev'])   # bajo evidence-dir, ya creado arriba
    except (RechazoRutas, OSError) as exc:
        print('RECHAZO al crear destinos: %s' % exc, file=sys.stderr)
        return EXIT_RECHAZO
    res = dict(schema='pruebas-auditoria-cierre-6g1/2', entorno=entorno(),
               motores_sha256={m: sha_file(MOT / n) for m, n in MOTORES.items()},
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               escenarios={k: dict(condicion=v_[0], motivo=v_[1], completo=v_[2],
                                   trasladado=v_[3], fallo_de_cierre=v_[4],
                                   log_cerrado=v_[5], inyeccion=v_[6])
                           for k, v_ in ESCENARIOS.items()},
               argumentos_motor='--mode full_processing [+ --keep-masks en Hardened/EVO sólo en E1]; '
                                'Mix = copia en la carpeta de trabajo',
               aislamiento=dict(raiz_oficial=str(v['oficial']), copia=str(v['copia']),
                                work_root=str(v['work']), evidence_dir=str(v['ev']),
                                reglas='rutas obligatorias; sin rmtree; destinos nuevos; '
                                       'componentes, no prefijos; sin solape ni anidamiento; '
                                       'enlaces y ancestros resueltos; sin sobrescrituras'))
    if a.base:
        bdir = v['base']
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = bateria(bdir, a.etiqueta_base, v['work'], ev_iny, ev_raiz=v['ev'])
        res['diagnostico_base'] = dict(
            etiqueta=a.etiqueta_base, carpeta=str(bdir),
            motores_sha256={m: sha_file(bdir / n) for m, n in MOTORES.items()},
            filas=fb, detalle=db,
            resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb), total=len(fb)))
    print('== motores corregidos (%s)' % MOT)
    filas, det = bateria(MOT, 'corregido', v['work'], ev_iny,
                         guardar_estados=True, ev_raiz=v['ev'])
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas),
                            fail_atribuibles_solo_a_F=sum(f['atribuible_solo_a_F'] is True
                                                          for f in filas),
                            fail_no_atribuibles=sum(f['atribuible_solo_a_F'] is False
                                                    for f in filas)),
               hallazgo_F=dict(recurso=RECURSO_F, comprobaciones_afectadas=sorted(CHECKS_F),
                               causa='variable de bucle `arr` de `for arr in mm.values(): '
                                     'arr.flush()` retiene el último memmap tras `del mm`',
                               detector=_analizar_cadena(ast.parse(
                                   (MOT / 'lectura_segura_6g1.py').read_text(
                                       encoding='utf-8', errors='replace'))),
                               corregido_en_codigo=None,
                               validacion_dinamica='PENDIENTE'))
    escribir_nuevo(v['ev'] / 'pruebas_auditoria_cierre_6g1.json',
                   json.dumps(res, indent=2, ensure_ascii=False, default=str) + '\n')
    bidx = {(f['prueba'], f['motor']): f for f in res.get('diagnostico_base', {}).get('filas', [])}
    cols = ['prueba', 'motor', 'condicion', 'codigo', 'completo', 'log_cerrado', 'trasladado',
            'comprobaciones', 'fallos', 'veredicto', 'atribuible_solo_a_F', 'codigo_base',
            'veredicto_base', 'fallos_base']
    salida = io.StringIO()
    wr = csv.DictWriter(salida, fieldnames=cols)
    wr.writeheader()
    for f in filas:
        b = bidx.get((f['prueba'], f['motor']), {})
        wr.writerow(dict(f, codigo_base=b.get('codigo', ''), veredicto_base=b.get('veredicto', ''),
                         fallos_base=b.get('fallos', '')))
    escribir_nuevo(v['ev'] / 'matriz_auditoria_cierre_6g1.csv', salida.getvalue())
    print('RESUMEN corregido: %d/%d PASS (FAIL sólo-F=%d, FAIL otros=%d)'
          % (res['resumen']['pass_'], res['resumen']['total'],
             res['resumen']['fail_atribuibles_solo_a_F'], res['resumen']['fail_no_atribuibles']))
    if 'diagnostico_base' in res:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base,
                                                 res['diagnostico_base']['resumen']['pass_'],
                                                 res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
