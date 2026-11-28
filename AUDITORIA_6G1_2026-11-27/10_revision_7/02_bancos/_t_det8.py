"""Banco REVISION 7: argumentos de SALIDA (out) en metodos de reduccion.

Solo parsea texto. No ejecuta motores, ni main(), ni bateria(), ni numpy.

Tesis que verifica:
  1. Un metodo de reduccion NO es seguro por su nombre: con out= escribe en un
     array EXTERNO y devuelve una referencia a el. Si ese array es el memmap o
     un alias suyo, la referencia retenida mantiene vivo el recurso.
  2. No basta con comprobar que out no sea literalmente "arr": puede haber otro
     alias (b = arr). Cualquier out= produce NO_CONCLUYENTE.
  3. Si la llamada usa *args o **kwargs, no se puede saber si esconden un out:
     se rechaza.
  4. El argumento POSICIONAL en la posicion de out se rechaza tambien.
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
import importlib.util, hashlib
RUTA = _localizar_propuesta()
_spec = importlib.util.spec_from_file_location('propuesta_6g1', str(RUTA))
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

OK, NO, DUD = m.F_OK, m.F_NO, m.F_DUDOSO
CARGA = 'np.load(p / "m.npy", mmap_mode="r")'
CAB = ('''def f():
    mm = {}
    for i in r:
        mm[i] = ''' + CARGA + '''
    for arr in mm.values():
%s
        arr.flush()
''')
CASOS = []


def neg(n, familia, desc, cuerpo, exacto=None):
    CASOS.append((n, familia, desc, exacto, CAB % textwrap.indent(textwrap.dedent(cuerpo).strip(), '        ')))


def pos(n, familia, desc, cuerpo):
    CASOS.append((n, familia, desc, OK, CAB % textwrap.indent(textwrap.dedent(cuerpo).strip(), '        ')))


# ===== O. `out=` EXPLICITO EN CADA METODO DE REDUCCION (los 11 del encargo) =====
for _n, _m in [('O01', 'sum'), ('O02', 'mean'), ('O03', 'std'), ('O04', 'var'),
               ('O05', 'prod'), ('O06', 'min'), ('O07', 'max'),
               ('O08', 'argmin'), ('O09', 'argmax'),
               ('O10', 'any'), ('O11', 'all')]:
    neg(_n, 'out', 'arr[lo:hi].%s(out=arr)' % _m, '''
    view = arr[lo:hi].%s(out=arr)
    arr = None
    del mm
''' % _m)

# ===== O12-O20. VARIANTES DE FORMA DEL out =====
neg('O12', 'out', 'out= con ALIAS distinto (b = arr)', '''
    b = arr
    view = arr[lo:hi].sum(out=b)
    b = None
    arr = None
    del mm
''')
neg('O13', 'out', 'out= con un objeto ARBITRARIO (no demostrable)', '''
    view = arr[lo:hi].sum(out=buf)
    arr = None
    del mm
''')
neg('O14', 'out', 'out como POSICIONAL (sum: axis, dtype, out)', '''
    view = arr[lo:hi].sum(None, None, arr)
    arr = None
    del mm
''')
neg('O15', 'out', 'out como POSICIONAL (mean)', '''
    view = arr[lo:hi].mean(None, None, buf)
    arr = None
    del mm
''')
neg('O16', 'out', 'out como POSICIONAL (min: axis, out)', '''
    view = arr[lo:hi].min(None, arr)
    arr = None
    del mm
''')
neg('O17', 'out', '*args puede esconder un out', '''
    view = arr[lo:hi].sum(*argv)
    arr = None
    del mm
''')
neg('O18', 'out', '**kwargs puede esconder un out', '''
    view = arr[lo:hi].sum(**kw)
    arr = None
    del mm
''')
neg('O19', 'out', 'out en otra EXPRESION (dentro de int)', '''
    view = int(arr[lo:hi].sum(out=arr))
    arr = None
    del mm
''')
neg('O20', 'out', 'out SIN asignar (sentencia suelta)', '''
    arr[lo:hi].sum(out=arr)
    arr = None
    del mm
''')
neg('O21', 'out', 'out= con VISTA del alias (arr[0:1])', '''
    view = arr[lo:hi].sum(out=arr[0:1])
    arr = None
    del mm
''')
neg('O22', 'out', 'out= en any/all', '''
    a = arr[lo:hi].any(out=buf)
    b = arr[lo:hi].all(out=buf)
    arr = None
    del mm
''')
neg('O23', 'out', 'out= en argmin/argmax', '''
    a = arr[lo:hi].argmin(out=buf)
    b = arr[lo:hi].argmax(out=buf)
    arr = None
    del mm
''')

# ===== M. REVISION COMPLETA DE LAS DEMAS LISTAS BLANCAS =====
neg('M19', 'metodo', 'astype SIN copy=True demostrado (default)', '''
    v = arr[lo:hi].astype(np.float32)
    arr = None
    del mm
''')
neg('M20', 'metodo', 'astype con *args', '''
    v = arr[lo:hi].astype(*argv)
    arr = None
    del mm
''')
neg('M21', 'metodo', 'astype con **kwargs', '''
    v = arr[lo:hi].astype(np.float32, copy=True, **kw)
    arr = None
    del mm
''')
neg('M22', 'metodo', 'astype con kwarg NO permitido', '''
    v = arr[lo:hi].astype(np.float32, copy=True, casting="no", where=True)
    arr = None
    del mm
''')
neg('M23', 'metodo', 'copy() con *args', '''
    v = arr[lo:hi].copy(*argv)
    arr = None
    del mm
''')
neg('M24', 'metodo', 'tolist() con *args', '''
    v = arr[lo:hi].tolist(*argv)
    arr = None
    del mm
''')
neg('M25', 'metodo', 'tobytes() con **kwargs', '''
    v = arr[lo:hi].tobytes(**kw)
    arr = None
    del mm
''')
neg('M26', 'metodo', 'item() con *args', '''
    v = arr[lo:hi].item(*argv)
    arr = None
    del mm
''')
neg('M27', 'metodo', 'flush() con *args (alias)', '''
    arr.flush(*argv)
    arr = None
    del mm
''')
neg('M28', 'metodo', 'close() con **kwargs (alias)', '''
    arr.close(**kw)
    arr = None
    del mm
''')
neg('M29', 'metodo', 'sum() posicional MAS ALLA de out', '''
    v = arr[lo:hi].sum(0, None, None, True)
    arr = None
    del mm
''')

# ===== P. CONTROLES POSITIVOS =====
pos('P13', 'control', 'CONTROL: los 11 metodos SIN out siguen admitidos', '''
    a1 = arr[lo:hi].sum()
    b1 = arr[lo:hi].mean()
    c1 = arr[lo:hi].std()
    d1 = arr[lo:hi].var()
    e1 = arr[lo:hi].prod()
    f1 = arr[lo:hi].min()
    g1 = arr[lo:hi].max()
    h = arr[lo:hi].argmin()
    r9 = arr[lo:hi].argmax()
    j = arr[lo:hi].any()
    k = arr[lo:hi].all()
    arr = None
    del mm
''')
pos('P14', 'control', 'CONTROL: sum(axis=0) / sum(dtype=...) sin out', '''
    a = arr[lo:hi].sum(axis=0)
    b = arr[lo:hi].sum(dtype=np.float64)
    c = arr[lo:hi].mean(axis=0)
    arr = None
    del mm
''')
pos('P15', 'control', 'CONTROL: copy() / flatten() sin expansion', '''
    a = arr[lo:hi].copy()
    b = arr[lo:hi].flatten()
    arr = None
    del mm
''')
pos('P16', 'control', 'CONTROL: tolist() / tobytes() / item()', '''
    a = arr[lo:hi].tolist()
    b = arr[lo:hi].tobytes()
    c = arr[lo:hi].item()
    arr = None
    del mm
''')
pos('P17', 'control', 'CONTROL: astype(x, copy=True) explicito', '''
    v = arr[lo:hi].astype(np.float32, copy=True)
    arr = None
    del mm
''')
pos('P18', 'control', 'CONTROL: astype(dtype=x, order="K", copy=True)', '''
    v = arr[lo:hi].astype(dtype=np.float32, order="K", copy=True)
    arr = None
    del mm
''')
pos('P19', 'control', 'CONTROL: astype(x, order, casting, copy=True)', '''
    v = arr[lo:hi].astype(np.float32, "C", True)
    arr = None
    del mm
''')
pos('P20', 'control', 'CONTROL: flush() / close() sin argumentos', '''
    arr.flush()
    arr.close()
    arr = None
    del mm
''')
pos('P21', 'control', 'CONTROL: metadatos del alias (nbytes, shape, dtype)', '''
    a = arr.nbytes
    b = arr.shape
    c = arr.dtype
    arr = None
    del mm
''')
pos('P22', 'control', 'CONTROL: patron real de motor (flush + comprehension)', '''
    v = {pid: arr[lo:hi] for pid, arr in regs.items()}
    arr.flush()
    arr = None
    del mm
''')
pos('P23', 'control', 'CONTROL: no se rechaza indiscriminadamente (mezcla)', '''
    a = arr[lo:hi].sum()
    b = arr[lo:hi].copy()
    c = int(arr[lo:hi].max())
    arr.flush()
    arr = None
    del mm
''')

FALLOS = 0
print('=' * 122)
print('BANCO REVISION 7  -  argumentos de SALIDA (out) y expansion de argumentos')
print('Detector cargado desde: %s' % RUTA.name)
print('sha256 detector: %s' % hashlib.sha256(Path(RUTA).read_bytes()).hexdigest())
print('=' * 122)
print()
print('  ID    familia   caso                                                  esperado         obtenido         res')
print('  ----  --------  ----------------------------------------------------  ---------------  ---------------  ----')
for n, familia, desc, exacto, src in CASOS:
    fn = ast.parse(src).body[0]
    r = m._analizar_funcion(fn)
    obt = r['estado']
    ok = (obt == exacto) if exacto is not None else (obt != OK)
    if not ok:
        FALLOS += 1
    print('  %-4s  %-8s  %-52s  %-15s  %-15s  %s'
          % (n, familia, desc[:52], (exacto or '!= C_TRUE')[:15], obt[:15],
             'PASS' if ok else 'FALLO'))
    if not ok:
        print('        motivo: %s' % (r.get('motivo') or ''))

print()
nneg = sum(1 for c in CASOS if c[3] is None)
npos = len(CASOS) - nneg
print('  TOTAL: %d/%d PASS   negativos (nunca C_TRUE): %d   positivos (deben ser C_TRUE): %d'
      % (len(CASOS) - FALLOS, len(CASOS), nneg, npos))
print('=' * 122)
sys.exit(1 if FALLOS else 0)
