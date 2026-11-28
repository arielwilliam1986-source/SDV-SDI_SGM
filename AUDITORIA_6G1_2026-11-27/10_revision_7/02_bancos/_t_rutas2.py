"""Banco REVISION 2: asegurar_dirs / escribir_nuevo / copiar_nuevo.

Solo funciones aisladas sobre un arbol temporal propio en /tmp. No toca el repo,
no ejecuta main()/bateria()/ejecutar(), no escribe en el proyecto.
"""
import sys, os, tempfile, shutil, traceback
from pathlib import Path
sys.dont_write_bytecode = True
def _localizar_propuesta():
    """Localiza pruebas_auditoria_cierre_6g1.PROPUESTA.py.

    1) variable de entorno PROPUESTA_6G1;
    2) junto a este banco (carpeta 01_propuesta de la entrega);
    3) /tmp/prop6g1 (entorno de trabajo del auditor).
    """
    import os
    cand = []
    if os.environ.get('PROPUESTA_6G1'):
        cand.append(Path(os.environ['PROPUESTA_6G1']))
    aqui = Path(__file__).resolve().parent
    cand += [aqui / 'pruebas_auditoria_cierre_6g1.PROPUESTA.py',
             aqui.parent / '01_propuesta' / 'pruebas_auditoria_cierre_6g1.PROPUESTA.py',
             aqui.parent.parent / '01_propuesta' / 'pruebas_auditoria_cierre_6g1.PROPUESTA.py',
             Path('/tmp/prop6g1/pruebas_auditoria_cierre_6g1.PROPUESTA.py')]
    for c in cand:
        if c.is_file():
            return c
    raise SystemExit('No encuentro la PROPUESTA; define PROPUESTA_6G1=<ruta>')


def _cargar_propuesta():
    import importlib.util
    ruta = _localizar_propuesta()
    spec = importlib.util.spec_from_file_location('propuesta_6g1', str(ruta))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, ruta

def _asegurar_dependencias():
    """comun_6g1.py vive en scripts/ del proyecto. Se anade al sys.path si existe,
    sin importarlo aqui: solo la PROPUESTA lo necesita."""
    import sys
    aqui = Path(__file__).resolve().parent
    for cand in (aqui.parent / 'papelera_no_usar',
                 aqui,
                 Path('/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')):
        if (cand / 'comun_6g1.py').is_file():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return cand
    return None

_asegurar_dependencias()
m, RUTA_PROPUESTA = _cargar_propuesta()

asegurar_dirs, escribir_nuevo, copiar_nuevo = (
    m.asegurar_dirs, m.escribir_nuevo, m.copiar_nuevo)
Rechazo, EXIT_RECHAZO = m.RechazoRutas, m.EXIT_RECHAZO

BASE = Path(tempfile.mkdtemp(prefix='rutas2_'))
OK, FALLOS = 0, []
def chk(nombre, cond, detalle=''):
    global OK
    if cond:
        OK += 1; print('  %-58s PASS' % nombre[:58])
    else:
        FALLOS.append(nombre); print('  %-58s FAIL  %s' % (nombre[:58], detalle[:60]))

def rechaza(fn, *a, **k):
    """True si la llamada lanza RechazoRutas."""
    try:
        fn(*a, **k)
    except Rechazo:
        return True
    except Exception:
        return False
    return False


def falla(fn, *a, **k):
    """True si la llamada lanza CUALQUIER excepcion (incluida OSError de E/S)."""
    try:
        fn(*a, **k)
    except Exception:
        return True
    return False

print('=' * 78)
print('BANCO REVISION 2: asegurar_dirs / escribir_nuevo / copiar_nuevo')
print('propuesta: %s' % RUTA_PROPUESTA)
print('=' * 78)
print()

# ---------------- A. asegurar_dirs: CREACION ----------------
print('A. asegurar_dirs -> creacion de directorios')
raiz = BASE / 'A_raiz'; raiz.mkdir()
casos = [
    ('A1  raiz existente + un nivel',            raiz, 'n1'),
    ('A2  raiz existente + cuatro niveles',      raiz, 'a/b/c/d'),
    ('A3  ruta anidada con nombre repetido',     raiz, 'x/x/x'),
    ('A4  ruta con espacios y guiones',          raiz, 'dir con espacios/sub-dir'),
    ('A5  ruta con punto inicial',               raiz, '.oculto/dentro'),
]
for nombre, r, rel in casos:
    destino = r / rel
    try:
        asegurar_dirs(destino, r)
        creado = destino.is_dir()
        prof = all((r / Path(*rel.split('/')[:i])).is_dir()
                   for i in range(1, len(rel.split('/')) + 1))
        chk(nombre, creado and prof, 'creado=%s profundidad=%s' % (creado, prof))
    except Exception as exc:
        chk(nombre, False, repr(exc)[:50])
print()

# ---------------- B. asegurar_dirs: IDEMPOTENCIA ----------------
print('B. asegurar_dirs -> directorios ya existentes')
r = BASE / 'B_raiz'; r.mkdir(); (r / 'ya' / 'existe').mkdir(parents=True)
for nombre, dest in [
    ('B1  carpeta ya existente (un nivel)',   r / 'ya'),
    ('B2  cadena ya existente',               r / 'ya' / 'existe'),
    ('B3  repetir sobre cadena ya existente', r / 'ya' / 'existe'),
    ('B4  crear parcial sobre cadena mixta',  r / 'ya' / 'existe' / 'nuevo'),
]:
    try:
        asegurar_dirs(dest, r)
        chk(nombre, dest.is_dir())
    except Exception as exc:
        chk(nombre, False, repr(exc)[:50])
chk('B5  B1 dejo un directorio real (no enlace)', not (r / 'ya').is_symlink())
print()

# ---------------- C. asegurar_dirs: p == raiz ----------------
print('C. asegurar_dirs -> relacion p == raiz')
r = BASE / 'C_raiz'
chk('C1  p == raiz inexistente -> RechazoRutas', rechaza(asegurar_dirs, r, r))
chk('C2  C1 NO creo la raiz', not r.exists())
r.mkdir()
try:
    asegurar_dirs(r, r); chk('C3  p == raiz existente -> no-op sin error', True)
except Exception as exc:
    chk('C3  p == raiz existente -> no-op sin error', False, repr(exc)[:50])
chk('C4  p == raiz existente sigue siendo directorio', r.is_dir())
print()

# ---------------- D. asegurar_dirs: RECHAZOS ----------------
print('D. asegurar_dirs -> rutas que NO cuelgan de la raiz')
r = BASE / 'D_raiz'; r.mkdir()
fuera = BASE / 'D_fuera'; fuera.mkdir()
chk('D1  ruta hermana de la raiz -> Rechazo', rechaza(asegurar_dirs, fuera / 'sub', r))
chk('D2  D1 no creo nada fuera', not (fuera / 'sub').exists())
chk('D3  raiz relativa .. -> Rechazo', rechaza(asegurar_dirs, r / '..' / 'otro', r))
chk('D4  ruta con ../ dentro -> Rechazo', rechaza(asegurar_dirs, r / 'a/../../x', r))
chk('D5  ruta absoluta distinta -> Rechazo', rechaza(asegurar_dirs, Path('/etc/x'), r))
chk('D6  raiz que es un fichero -> Rechazo',
    rechaza(asegurar_dirs, BASE / 'D_f' / 'sub', (lambda p: (p.write_text('x'), p)[1])(BASE / 'D_f')))
print()

# ---------------- E. asegurar_dirs: ENLACES SIMBOLICOS ----------------
print('E. asegurar_dirs -> enlaces simbolicos')
r = BASE / 'E_raiz'; r.mkdir()
real = BASE / 'E_real'; real.mkdir()
os.symlink(str(real), str(r / 'enlace_dir'))
chk('E1  componente que es enlace a directorio -> Rechazo',
    rechaza(asegurar_dirs, r / 'enlace_dir' / 'sub', r))
chk('E2  E1 no escribio a traves del enlace', not (real / 'sub').exists())
f = BASE / 'E_f.txt'; f.write_text('x')
os.symlink(str(f), str(r / 'enlace_fichero'))
chk('E3  componente que es enlace a fichero -> Rechazo',
    rechaza(asegurar_dirs, r / 'enlace_fichero' / 'sub', r))
os.symlink(str(BASE / 'E_roto'), str(r / 'enlace_roto'))
chk('E4  componente enlace roto -> Rechazo',
    rechaza(asegurar_dirs, r / 'enlace_roto' / 'sub', r))
# E5: si la raiz es un enlace, se resuelve y p==raiz -> no-op legitimo (no crea).
chk('E5  raiz que es enlace + p==raiz -> no-op sin error',
    not rechaza(asegurar_dirs, r / 'enlace_dir', r / 'enlace_dir'))
chk('E6  E5 no creo nada', not (real / 'enlace_dir').exists())
# E7: si la RAIZ es un enlace, se resuelve y se opera sobre el destino. La
# invariante que importa es que nada salga del arbol resuelto de la raiz.
# Se comparan rutas RESUELTAS: rglob sigue los enlaces y veria el mismo
# directorio dos veces (por el enlace y por su destino real).
antes = {x.resolve() for x in BASE.rglob('*')}
try:
    asegurar_dirs(r / 'enlace_dir' / 'sub2', r / 'enlace_dir')
    dentro = (real / 'sub2').is_dir()
    fuera = {x.resolve() for x in BASE.rglob('*')} - antes - {(real / 'sub2').resolve()}
except Exception:
    dentro, fuera = False, set()
chk('E7  raiz enlace -> escribe DENTRO del destino resuelto', dentro)
chk('E8  E7 no creo nada fuera del arbol de la raiz', not fuera)
print()

# ---------------- F. escribir_nuevo ----------------
print('F. escribir_nuevo -> destinos nuevos y existentes')
d = BASE / 'F'; d.mkdir()
try:
    escribir_nuevo(d / 'nuevo.txt', 'hola')
    chk('F1  destino nuevo -> escribe', (d / 'nuevo.txt').read_text() == 'hola')
except Exception as exc:
    chk('F1  destino nuevo -> escribe', False, repr(exc)[:50])
chk('F2  destino existente -> Rechazo',
    rechaza(escribir_nuevo, d / 'nuevo.txt', 'otra'))
chk('F3  F2 no sobrescribio', (d / 'nuevo.txt').read_text() == 'hola')
os.symlink(str(d / 'nuevo.txt'), str(d / 'enlace.txt'))
chk('F4  destino enlace a existente -> Rechazo', rechaza(escribir_nuevo, d / 'enlace.txt', 'x'))
chk('F5  F4 no sobrescribio el original', (d / 'nuevo.txt').read_text() == 'hola')
os.symlink(str(d / 'fantasma.txt'), str(d / 'roto.txt'))
chk('F6  destino enlace roto -> Rechazo', rechaza(escribir_nuevo, d / 'roto.txt', 'x'))
chk('F7  F6 no creo el destino del enlace', not (d / 'fantasma.txt').exists())
chk('F8  destino en carpeta inexistente -> excepcion de E/S',
    falla(escribir_nuevo, d / 'no' / 'hay' / 'x.txt', 'x'))
chk('F8b F8 no creo las carpetas intermedias', not (d / 'no').exists())
try:
    escribir_nuevo(d / 'vacio.txt', '')
    chk('F9  contenido vacio -> escribe fichero vacio',
        (d / 'vacio.txt').exists() and (d / 'vacio.txt').read_text() == '')
except Exception as exc:
    chk('F9  contenido vacio -> escribe fichero vacio', False, repr(exc)[:50])
try:
    escribir_nuevo(d / 'utf8.txt', 'a\u00f1o \u00e9 \u4e2d')
    chk('F10 UTF-8 se conserva', (d / 'utf8.txt').read_text() == 'a\u00f1o \u00e9 \u4e2d')
except Exception as exc:
    chk('F10 UTF-8 se conserva', False, repr(exc)[:50])
print()

# ---------------- G. copiar_nuevo ----------------
print('G. copiar_nuevo -> destinos nuevos y existentes')
g = BASE / 'G'; g.mkdir()
origen = g / 'origen.bin'; origen.write_bytes(bytes(range(256)) * 40)
try:
    copiar_nuevo(origen, g / 'copia.bin')
    chk('G1  destino nuevo -> copia identica',
        (g / 'copia.bin').read_bytes() == origen.read_bytes())
except Exception as exc:
    chk('G1  destino nuevo -> copia identica', False, repr(exc)[:50])
chk('G2  destino existente -> Rechazo', rechaza(copiar_nuevo, origen, g / 'copia.bin'))
chk('G3  G2 no sobrescribio', (g / 'copia.bin').read_bytes() == origen.read_bytes())
os.symlink(str(g / 'copia.bin'), str(g / 'enlace.bin'))
chk('G4  destino enlace -> Rechazo', rechaza(copiar_nuevo, origen, g / 'enlace.bin'))
chk('G5  G4 no sobrescribio', (g / 'copia.bin').read_bytes() == origen.read_bytes())
chk('G6  origen inexistente -> excepcion', falla(copiar_nuevo, g / 'nada.bin', g / 'x.bin'))
chk('G7  G6 no dejo destino a medias', not (g / 'x.bin').exists())
try:
    vacio = g / 'vacio.bin'; vacio.write_bytes(b'')
    copiar_nuevo(vacio, g / 'copia_vacia.bin')
    chk('G8  origen vacio -> copia vacia',
        (g / 'copia_vacia.bin').exists() and (g / 'copia_vacia.bin').stat().st_size == 0)
except Exception as exc:
    chk('G8  origen vacio -> copia vacia', False, repr(exc)[:50])
print()

# ---------------- H. COHERENCIA CON EL FLUJO REAL ----------------
print('H. coherencia: crear dir + escribir + copiar en el mismo arbol')
h = BASE / 'H_ev'; h.mkdir()
try:
    iny = h / 'inyecciones_auditoria_6g1'
    asegurar_dirs(iny, h)
    escribir_nuevo(iny / 'registro.txt', 'ok')
    copiar_nuevo(g / 'copia.bin', iny / 'copia.bin')
    chk('H1  dir creado bajo evidence-dir', iny.is_dir() and iny.parent == h)
    chk('H2  escritura en el dir creado', (iny / 'registro.txt').read_text() == 'ok')
    chk('H3  copia en el dir creado',
        (iny / 'copia.bin').read_bytes() == (g / 'copia.bin').read_bytes())
    within = [p for p in BASE.rglob('*') if 'H_ev' not in p.parts]
    chk('H4  el evidence-dir no se salio de si mismo',
        all(str(p).startswith(str(h)) for p in h.rglob('*')))
    chk('H5  H no escribio fuera de H_ev', all(not str(p).startswith(str(iny))
                                               for p in within))
except Exception as exc:
    chk('H1  flujo completo', False, repr(exc)[:60])
print()

# ---------------- I. LIMPIEZA ----------------
shutil.rmtree(str(BASE), ignore_errors=True)
print('  arbol temporal eliminado:', not BASE.exists())
print()
print('=' * 78)
print('RESULTADO: %d/%d correctos' % (OK, OK + len(FALLOS)))
if FALLOS:
    print('FALLOS:')
    for f in FALLOS:
        print('  -', f)
else:
    print('TODOS LOS CASOS CORRECTOS')
print('=' * 78)
sys.exit(0 if not FALLOS else 1)
