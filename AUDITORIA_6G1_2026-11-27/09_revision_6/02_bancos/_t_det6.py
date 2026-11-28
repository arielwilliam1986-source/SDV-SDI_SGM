"""Banco REVISION 5: subindices/vistas, atributos y llamadas indirectas.

Solo parsea texto. No ejecuta motores, ni main(), ni bateria().

Tesis que verifica: una lectura mediante Subscript NO es inocua por defecto
(puede devolver una VISTA que comparte el almacenamiento), y un Attribute
tampoco (arr.data devuelve el buffer; arr.flush devuelve el metodo ligado).
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


# ===================== A. SUBINDICES Y VISTAS =====================
neg('V01', 'vista', 'view = arr[:]', '''
    view = arr[:]
    arr = None
    del mm
''')
neg('V02', 'vista', 'view = arr[lo:hi]', '''
    view = arr[lo:hi]
    arr = None
    del mm
''')
neg('V03', 'vista', 'view = arr[i] (escalar, pero Subscript)', '''
    view = arr[i]
    arr = None
    del mm
''')
neg('V04', 'vista', 'vista guardada en un contenedor', '''
    cache["v"] = arr[lo:hi]
    arr = None
    del mm
''')
neg('V05', 'vista', 'vista devuelta al llamador', '''
    arr = None
    del mm
    return arr[lo:hi]
''')
neg('V06', 'vista', 'vista pasada a una funcion', '''
    registrar(arr[lo:hi])
    arr = None
    del mm
''')
pos('V07', 'vista', 'CONTROL: consumo inmediato que no asigna ni pasa', '''
    total = int(arr[lo:hi].sum())
    arr = None
    del mm
''')
pos('V08', 'vista', 'CONTROL: vista dentro de comprehension SOMBREADO (motor)', '''
    regs = {pid: arr[lo:hi] for pid, arr in v_regs.items()}
    arr.flush()
    arr = None
    del mm
''')
# ===================== B. ATRIBUTOS =====================
neg('A01', 'atributo', 'data = arr.data (buffer subyacente)', '''
    data = arr.data
    arr = None
    del mm
''')
neg('A02', 'atributo', 'method = arr.flush (metodo ligado)', '''
    method = arr.flush
    arr = None
    del mm
''')
neg('A03', 'atributo', 'cb = arr.__array_interface__', '''
    cb = arr.__array_interface__
    arr = None
    del mm
''')
neg('A04', 'atributo', 'arr.base (memmap de origen)', '''
    b = arr.base
    arr = None
    del mm
''')
# REVISION 6: A05 era 'arr.dtype como valor'. Expectativa ERRONEA: numpy.dtype
# es inmutable y no referencia el array. Se sustituye por los atributos que SI
# devuelven vistas del array o el buffer.
neg('A10', 'atributo', 'arr.T como valor devuelve una VISTA', '''
    d = arr.T
    arr = None
    del mm
''')
neg('A11', 'atributo', 'arr.real / arr.imag devuelven VISTAS', '''
    d = arr.real
    e = arr.imag
    arr = None
    del mm
''')
neg('A12', 'atributo', 'arr.flat: iterador VIVO sobre el array', '''
    d = arr.flat
    arr = None
    del mm
''')
pos('A06', 'atributo', 'CONTROL: arr.flush() como llamada inmediata', '''
    arr.flush()
    arr = None
    del mm
''')
pos('A07', 'atributo', 'CONTROL: arr.close() como llamada inmediata', '''
    arr.close()
    arr = None
    del mm
''')
neg('A08', 'atributo', 'metodo NO seguro llamado (arr.copy)', '''
    c = arr.copy()
    arr = None
    del mm
''')
neg('A09', 'atributo', 'metodo NO seguro llamado (arr.reshape)', '''
    r6 = arr.reshape(-1)
    arr = None
    del mm
''')
# ===================== C. LLAMADAS INDIRECTAS =====================
neg('I01', 'indirecta', 'getattr(arr, "data")', '''
    g = getattr(arr, "data")
    arr = None
    del mm
''')
neg('I02', 'indirecta', 'vars(arr)', '''
    v = vars(arr)
    arr = None
    del mm
''')
neg('I03', 'indirecta', 'hasattr(arr, "x")', '''
    h = hasattr(arr, "x")
    arr = None
    del mm
''')
neg('I04', 'indirecta', 'dir(arr)', '''
    d = dir(arr)
    arr = None
    del mm
''')
neg('I05', 'indirecta', 'iter(arr)', '''
    it = iter(arr)
    arr = None
    del mm
''')
pos('I06', 'indirecta', 'CONTROL: len(arr), id(arr), repr(arr) puras', '''
    n = len(arr)
    i2 = id(arr)
    s2 = repr(arr)
    arr = None
    del mm
''')
# ===================== D. AMBITO: SOMBRA vs CAPTURA =====================
neg('S01', 'ambito', 'comprehension que CAPTURA el alias  [arr for _ in z]', '''
    xs = [arr for _ in z]
    arr = None
    del mm
''')
neg('S02', 'ambito', 'genexp que captura', '''
    g = (arr for _ in z)
    arr = None
    del mm
''')
neg('S03', 'ambito', 'dictcomp que captura en el valor', '''
    d = {k: arr for k in z}
    arr = None
    del mm
''')
pos('S04', 'ambito', 'CONTROL: comprehension con su PROPIO arr (sombra)', '''
    regs = [arr[0] for arr in v_regs]
    arr.flush()
    arr = None
    del mm
''')
neg('S05', 'ambito', 'lambda que captura el alias', '''
    g = lambda: arr
    arr = None
    del mm
''')
pos('S06', 'ambito', 'CONTROL: lambda con su propio parametro arr', '''
    g = lambda arr: arr[0]
    arr.flush()
    arr = None
    del mm
''')
# ===================== E. CONTROLES GENERALES =====================
pos('G01', 'control', 'sin alias, libera y borra', '''
    arr = None
    del mm
''')
pos('G02', 'control', 'patron COMPLETO de motor (vistas sombreadas + flush)', '''
    v_regs_r = {pid: arr[lo:hi] for pid, arr in v_regs.items()}
    i_regs_r = {pid: arr[lo:hi] for pid, arr in i_regs.items()}
    for arr in mm.values():
        arr.flush()
    arr = None
    del mm
''')
pos('G03', 'control', 'alias creado y liberado', '''
    b = arr
    b = None
    arr = None
    del mm
''')
neg('G04', 'control', 'del mm solo en una rama', '''
    arr = None
    if c:
        del mm
''', exacto=NO)

print('=' * 100)
print('BANCO REVISION 5: subindices/vistas, atributos y llamadas indirectas')
print('propuesta: %s' % RUTA)
print('=' * 100)
print()
print('  ID    familia      caso                                                esperado        obtenido        res')
print('  ----  -----------  --------------------------------------------------  --------------  --------------  ----')
res, fallos = [], []
for n, fam, desc, exacto, src in CASOS:
    try:
        r = m._analizar_cadena(ast.parse(src))
        estado, motivo = r['estado_global'], str(r['motivo'])
    except Exception as exc:
        estado, motivo = 'EXC', repr(exc)[:40]
    if exacto is not None:
        ok, esp = (estado == exacto), exacto.replace('CONCLUYENTE_', 'C_')
    else:
        ok, esp = (estado != OK), '!= C_TRUE'
    res.append(ok)
    if not ok:
        fallos.append((n, desc, estado, motivo))
    print('  %-4s  %-11s  %-50s  %-13s   %-13s   %s' % (
        n, fam, desc[:50], esp, str(estado).replace('CONCLUYENTE_', 'C_'),
        'PASS' if ok else 'FAIL -> ' + motivo[:24]))
print()
neg_total = sum(1 for c in CASOS if c[3] is None)
print('TOTAL: %d/%d PASS' % (sum(res), len(res)))
print('  negativos (nunca C_TRUE): %d' % neg_total)
print('  positivos (deben ser C_TRUE): %d' % (len(CASOS) - neg_total))
if fallos:
    print()
    print('FALLOS:')
    for n, d, e, mo in fallos:
        print('  - %s %s -> %s (%s)' % (n, d, e, mo[:46]))
sys.exit(0 if all(res) else 1)
