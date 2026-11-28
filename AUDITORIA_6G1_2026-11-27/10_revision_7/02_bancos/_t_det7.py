"""Banco REVISION 6: lista blanca de metodos sobre VISTAS.

Solo parsea texto. No ejecuta motores, ni main(), ni bateria(), ni numpy.

Tesis que verifica:
  1. Un metodo NO es seguro por su NOMBRE. `arr[a:b].ravel()` puede devolver una
     vista; `astype(copy=False)` puede devolver el mismo array.
  2. La revision 5 delegaba la decision del Subscript en la rama del Attribute,
     pero esa rama nunca ve el Name de `arr[a:b].metodo()`. El resultado era que
     CUALQUIER metodo sobre una vista pasaba como inocuo (incluso uno inventado).
  3. Solo se admite un metodo sobre una vista si su RESULTADO es demostrablemente
     independiente: reduccion a escalar, copia por contrato, o astype con
     copy=True demostrado en los ARGUMENTOS.
"""
import sys, ast, textwrap, os
from pathlib import Path
sys.dont_write_bytecode = True


def _localizar_propuesta():
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


def _asegurar_dependencias():
    aqui = Path(__file__).resolve().parent
    for cand in (aqui, Path('/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')):
        if (cand / 'comun_6g1.py').is_file():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return cand
    return None


_asegurar_dependencias()
import importlib.util
RUTA = _localizar_propuesta()
_spec = importlib.util.spec_from_file_location('propuesta_6g1', str(RUTA))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

OK, NO, DUD = m.F_OK, m.F_NO, m.F_DUDOSO
CARGA = 'np.load(p / "m.npy", mmap_mode="r")'
CAB = f'''def f():
    mm = {{}}
    for i in r:
        mm[i] = {CARGA}
    for arr in mm.values():
        arr.flush()
'''
CASOS = []


def neg(n, familia, desc, cuerpo, exacto=None):
    CASOS.append((n, familia, desc, exacto, textwrap.dedent(CAB + cuerpo).strip()))


def pos(n, familia, desc, cuerpo):
    CASOS.append((n, familia, desc, OK, textwrap.dedent(CAB + cuerpo).strip()))


# ===== M. METODOS SOBRE VISTA: retirados de la lista blanca =====
neg('M01', 'metodo', 'arr[lo:hi].ravel() asignado', '''
    v = arr[lo:hi].ravel()
    arr = None
    del mm
''')
neg('M02', 'metodo', 'arr[lo:hi].ravel(order="K") asignado', '''
    v = arr[lo:hi].ravel(order="K")
    arr = None
    del mm
''')
neg('M03', 'metodo', 'arr[lo:hi].astype(copy=False) asignado', '''
    v = arr[lo:hi].astype(copy=False)
    arr = None
    del mm
''')
neg('M04', 'metodo', 'arr[lo:hi].astype(arr.dtype, copy=False)', '''
    v = arr[lo:hi].astype(arr.dtype, copy=False)
    arr = None
    del mm
''')
neg('M05', 'metodo', 'arr[lo:hi].astype(copy=flag) no literal', '''
    v = arr[lo:hi].astype(np.float32, copy=flag)
    arr = None
    del mm
''')
neg('M06', 'metodo', 'arr[lo:hi].astype(np.float32, copy=None)', '''
    v = arr[lo:hi].astype(np.float32, copy=None)
    arr = None
    del mm
''')
neg('M07', 'metodo', 'arr[lo:hi].reshape(-1) (vista posible)', '''
    v = arr[lo:hi].reshape(-1)
    arr = None
    del mm
''')
neg('M08', 'metodo', 'arr[lo:hi].round(2) retirado por prudencia', '''
    v = arr[lo:hi].round(2)
    arr = None
    del mm
''')
neg('M09', 'metodo', 'arr[lo:hi].clip(0, 1) (no demostrado)', '''
    v = arr[lo:hi].clip(0, 1)
    arr = None
    del mm
''')
neg('M10', 'metodo', 'arr[lo:hi].transpose() (vista posible)', '''
    v = arr[lo:hi].transpose()
    arr = None
    del mm
''')
neg('M11', 'metodo', 'METODO INVENTADO arr[lo:hi].zzz()', '''
    v = arr[lo:hi].zzz()
    arr = None
    del mm
''')
neg('M12', 'metodo', 'arr[lo:hi].count(1) (no existe en ndarray)', '''
    v = arr[lo:hi].count(1)
    arr = None
    del mm
''')
neg('M13', 'metodo', 'arr[lo:hi].index(1) (no existe en ndarray)', '''
    v = arr[lo:hi].index(1)
    arr = None
    del mm
''')
neg('M14', 'metodo', 'atributo de vista SIN llamada: arr[lo:hi].real', '''
    v = arr[lo:hi].real
    arr = None
    del mm
''')
neg('M15', 'metodo', 'metodo ligado de vista guardado: arr[lo:hi].sum', '''
    v = arr[lo:hi].sum
    arr = None
    del mm
''')
neg('M16', 'metodo', 'arr[lo:hi].ravel() como sentencia suelta', '''
    arr[lo:hi].ravel()
    arr = None
    del mm
''')
neg('M17', 'metodo', 'arr[lo:hi].ravel() pasado a otra funcion', '''
    registrar(arr[lo:hi].ravel())
    arr = None
    del mm
''')
neg('M18', 'metodo', 'arr[lo:hi].astype(np.float32) sin copy explicito', '''
    v = arr[lo:hi].astype(np.float32, order="C", casting="unsafe")
    arr = None
    del mm
''')

# ===== P. CONTROLES POSITIVOS: el resultado SI es independiente =====
pos('P01', 'control', 'CONTROL: arr[lo:hi].sum() -> escalar nuevo', '''
    v = arr[lo:hi].sum()
    arr = None
    del mm
''')
pos('P02', 'control', 'CONTROL: int(arr[lo:hi].sum()) envuelto en pura', '''
    v = int(arr[lo:hi].sum())
    arr = None
    del mm
''')
pos('P03', 'control', 'CONTROL: arr[lo:hi].copy() -> copia independiente', '''
    v = arr[lo:hi].copy()
    arr = None
    del mm
''')
pos('P04', 'control', 'CONTROL: arr[lo:hi].flatten() -> copia independiente', '''
    v = arr[lo:hi].flatten()
    arr = None
    del mm
''')
# REVISION 7: P05 era 'arr[lo:hi].astype(np.float32) default copy=True' y lo
# daba por seguro. Es una expectativa DEBIL: el default es documentacion, no
# analisis del codigo. La revision 7 exige que copy=True este DEMOSTRADO en
# los argumentos. Pasa a negativo (M19) en el banco de la revision 7.
pos('P06', 'control', 'CONTROL: arr[lo:hi].astype(np.float32, copy=True) explicito', '''
    v = arr[lo:hi].astype(np.float32, copy=True)
    arr = None
    del mm
''')
pos('P07', 'control', 'CONTROL: arr[lo:hi].astype(dtype=x, copy=True) por keyword', '''
    v = arr[lo:hi].astype(dtype=np.float32, copy=True)
    arr = None
    del mm
''')
pos('P08', 'control', 'CONTROL: arr[lo:hi].tolist() -> list de Python', '''
    v = arr[lo:hi].tolist()
    arr = None
    del mm
''')
pos('P09', 'control', 'CONTROL: arr[lo:hi].tobytes() -> bytes', '''
    v = arr[lo:hi].tobytes()
    arr = None
    del mm
''')
pos('P10', 'control', 'CONTROL: arr[lo:hi].mean(), .std(), .argmax() escalares', '''
    a = arr[lo:hi].mean()
    b = arr[lo:hi].std()
    c = arr[lo:hi].argmax()
    d = arr[lo:hi].item()
    arr = None
    del mm
''')
pos('P11', 'control', 'CONTROL: metodos seguros del alias siguen admitidos', '''
    arr.flush()
    n = arr.nbytes
    s = arr.shape
    arr.close()
    arr = None
    del mm
''')
pos('P12', 'control', 'CONTROL: ninguna vista, solo flush -> motor tipico', '''
    arr.flush()
    arr = None
    del mm
''')

# ===== G. CONTROL GENERAL =====
pos('G01', 'control', 'CONTROL: patron completo de motor con comprehension', '''
    v = {pid: arr[lo:hi] for pid, arr in regs.items()}
    arr.flush()
    arr = None
    del mm
''')

FALLOS = 0
print('=' * 118)
print('BANCO REVISION 6  -  metodos sobre vistas (lista blanca por RESULTADO, no por nombre)')
print('Detector cargado desde: %s' % RUTA.name)
print('sha256 detector: %s' % __import__('hashlib').sha256(Path(RUTA).read_bytes()).hexdigest())
print('=' * 118)
print()
print('  ID    familia   caso                                                  esperado         obtenido         res')
print('  ----  --------  ----------------------------------------------------  ---------------  ---------------  ----')
for n, familia, desc, exacto, src in CASOS:
    fn = ast.parse(src).body[0]
    r = m._analizar_funcion(fn)
    obt = r['estado']
    if exacto is not None:
        ok = (obt == exacto)
    else:
        ok = (obt != OK)
    if not ok:
        FALLOS += 1
    print('  %-4s  %-8s  %-52s  %-15s  %-15s  %s'
          % (n, familia, desc[:52], (exacto or '!= C_TRUE')[:15], obt[:15], 'PASS' if ok else 'FALLO'))
    if not ok:
        print('        motivo: %s' % (r.get('motivo') or ''))
        for f in r.get('formas', {}) or {}:
            print('        formas: %s' % str(f)[:100])

print()
nneg = sum(1 for c in CASOS if c[3] is None)
npos = len(CASOS) - nneg
print('  TOTAL: %d/%d PASS   negativos (nunca C_TRUE): %d   positivos (deben ser C_TRUE): %d'
      % (len(CASOS) - FALLOS, len(CASOS), nneg, npos))
print('=' * 118)
sys.exit(1 if FALLOS else 0)
