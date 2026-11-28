"""BANCO DE INTEGRIDAD (punto 6 de la revision 4).

Comprueba que los bancos cargan EXACTAMENTE el detector de la propuesta:
  1. hay una sola PROPUESTA en el arbol de trabajo y en la carpeta publicada;
  2. el modulo que cargan los bancos es el de esa ruta;
  3. el hash del fichero cargado coincide con el declarado;
  4. las funciones del detector provienen de ese fichero (__code__.co_filename);
  5. no hay copias divergentes del detector con el mismo nombre.
"""
import sys, os, hashlib, importlib.util
from pathlib import Path
sys.dont_write_bytecode = True

ESPERADO = sys.argv[1] if len(sys.argv) > 1 else None
NOMBRE = 'pruebas_auditoria_cierre_6g1.PROPUESTA.py'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


print('=' * 88)
print('BANCO DE INTEGRIDAD: una sola fuente para el detector')
print('=' * 88)
print()

# --- 1. todas las copias con ese nombre en el sistema de trabajo ---
raices = [Path('/tmp/prop6g1'),
          Path('/tmp/r2/AUDITORIA_6G1_2026-11-27'),
          Path('/tmp/r3/AUDITORIA_6G1_2026-11-27'),
          Path('/tmp/r4/AUDITORIA_6G1_2026-11-27'),
          Path('/tmp/r5/AUDITORIA_6G1_2026-11-27'),
          Path('/tmp/r6/AUDITORIA_6G1_2026-11-27'),
          Path('/home/user/SDV-SDI_SGM')]
encontradas = {}
for r in raices:
    if not r.is_dir():
        continue
    for p in r.rglob(NOMBRE):
        encontradas[str(p)] = sha(p)

print('1. Copias encontradas con el nombre %s:' % NOMBRE)
for p, h in sorted(encontradas.items()):
    print('     %s  %s' % (h[:16], p))
print()

# --- 2. agrupar por hash: debe haber UN solo hash vigente ---
por_hash = {}
for p, h in encontradas.items():
    por_hash.setdefault(h, []).append(p)
print('2. Hashes distintos: %d' % len(por_hash))
for h, ps in sorted(por_hash.items()):
    print('     %s  -> %d copia(s)' % (h[:16], len(ps)))
    if len(ps) > 1:
        for p in ps:
            print('          %s' % p)
print()

# --- 3. cargar la propuesta y comprobar de donde vienen las funciones ---
def localizar():
    cand = [Path('/tmp/prop6g1') / NOMBRE]
    cand.append(Path('/tmp/r4/AUDITORIA_6G1_2026-11-27/07_revision_4/01_propuesta') / NOMBRE)
    cand.append(Path('/tmp/r5/AUDITORIA_6G1_2026-11-27/08_revision_5/01_propuesta') / NOMBRE)
    cand.append(Path('/tmp/r6/AUDITORIA_6G1_2026-11-27/09_revision_6/01_propuesta') / NOMBRE)
    for c in cand:
        if c.is_file():
            return c
    raise SystemExit('no encuentro la propuesta')

ruta = localizar()
sys.path.insert(0, '/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')
spec = importlib.util.spec_from_file_location('propuesta_6g1', str(ruta))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

print('3. Propuesta cargada: %s' % ruta)
print('   sha256: %s' % sha(ruta))
if ESPERADO:
    coincide = sha(ruta).startswith(ESPERADO) or sha(ruta) == ESPERADO
    print('   esperado %s -> %s' % (ESPERADO, 'OK' if coincide else 'NO COINCIDE'))
    if not coincide:
        sys.exit(1)
print()

print('4. Origen real de las funciones del detector (__code__.co_filename):')
for nom in ('_formas_conservadoras', '_clasificar_contexto', '_caminos', '_juzgar',
            '_veredicto', '_analizar_funcion', '_analizar_cadena', '_flat',
            '_reasignaciones_previas', '_alias_de', '_pasa_a_funcion'):
    f = getattr(m, nom, None)
    if f is None:
        print('     %-24s AUSENTE' % nom)
        continue
    origen = Path(f.__code__.co_filename).resolve()
    ok = origen == Path(ruta).resolve()
    print('     %-24s %s  %s' % (nom, 'OK ' if ok else 'MAL', origen))
print()

# --- 5. no hay modulo `prop` alternativo ya cargado en sys.modules ---
print('5. Modulos del detector en sys.modules:')
for k, v in sorted(sys.modules.items()):
    if k in ('prop', 'propuesta_6g1') or 'PROPUESTA' in str(getattr(v, '__file__', '')):
        print('     %-18s -> %s' % (k, getattr(v, '__file__', '(sin fichero)')))
print()
print('=' * 88)
print('FIN DEL BANCO DE INTEGRIDAD')
print('=' * 88)
