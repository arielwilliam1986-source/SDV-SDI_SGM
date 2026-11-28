"""Banco REVISION 4: cierre conservador de formas AST no soportadas.

Solo parsea texto. No ejecuta motores, ni main(), ni bateria().

Dos familias de casos:
  NEGATIVOS  una construccion que PUEDE retener el alias -> no puede dar
             CONCLUYENTE_TRUE (debe dar NO_CONCLUYENTE o CONCLUYENTE_FALSE).
  POSITIVOS  un control legitimo SIN fuga -> debe seguir dando CONCLUYENTE_TRUE.
             Si el endurecimiento los tumba, el endurecimiento es erroneo.
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
    """Caso NEGATIVO: nunca CONCLUYENTE_TRUE."""
    CASOS.append((n, familia, desc, exacto, textwrap.dedent(CAB + cuerpo).strip()))


def pos(n, familia, desc, cuerpo):
    """Caso POSITIVO: control legitimo, debe seguir dando CONCLUYENTE_TRUE."""
    CASOS.append((n, familia, desc, OK, textwrap.dedent(CAB + cuerpo).strip()))


# ============ 1. FORMAS DE LA REVISION 3 (deben seguir cubiertas) ============
neg('N01', 'rev3', 'anotada  b: object = arr', '''
    b: object = arr
    arr = None
    del mm
''')
neg('N02', 'rev3', 'encadenada  b = c = arr', '''
    b = c = arr
    arr = None
    del mm
''')
neg('N03', 'rev3', 'desempaquetado  b, = (arr,)', '''
    b, = (arr,)
    arr = None
    del mm
''')
neg('N04', 'rev3', 'NamedExpr  (b := arr)', '''
    if (b := arr) is not None:
        pass
    arr = None
    del mm
''')
neg('N05', 'rev3', 'atributo  obj.ref = arr', '''
    obj.ref = arr
    arr = None
    del mm
''')
neg('N06', 'rev3', 'subscript  d["k"] = arr', '''
    d["k"] = arr
    arr = None
    del mm
''')
neg('N07', 'rev3', 'paso a llamada  registrar(arr)', '''
    registrar(arr)
    arr = None
    del mm
''')
# ============ 2. LAMBDA Y CLOSURES ============
neg('N08', 'lambda', 'lambda que captura el alias', '''
    g = lambda: arr
    arr = None
    del mm
''')
neg('N09', 'closure', 'def interna que retorna el alias', '''
    def usar():
        return arr
    usar()
    arr = None
    del mm
''')
neg('N10', 'lambda', 'lambda como default que captura', '''
    def h(x=arr):
        return x
    arr = None
    del mm
''')
# ============ 3. COMPREHENSIONS Y GENERADORES ============
neg('N11', 'comp', 'listcomp que captura', '''
    xs = [arr for _ in z]
    arr = None
    del mm
''')
neg('N12', 'comp', 'genexp que captura', '''
    g = (arr for _ in z)
    arr = None
    del mm
''')
neg('N13', 'comp', 'setcomp que captura', '''
    s = {arr for _ in z}
    arr = None
    del mm
''')
neg('N14', 'comp', 'dictcomp que captura', '''
    d2 = {k: arr for k in z}
    arr = None
    del mm
''')
# ============ 4. GLOBAL Y NONLOCAL ============
neg('N15', 'global', 'global arr', '''
    global arr
    arr = None
    del mm
''')
neg('N16', 'nonlocal', 'nonlocal arr', '''
    nonlocal arr
    arr = None
    del mm
''')
# ============ 5. YIELD ============
neg('N17', 'yield', 'yield arr', '''
    yield arr
    arr = None
    del mm
''')
neg('N18', 'yield', 'yield from arr', '''
    yield from arr
    arr = None
    del mm
''')
# ============ 6. WITH ... AS ============
neg('N19', 'with', 'alias dentro del cuerpo de with', '''
    with abrir() as q:
        b = arr
    arr = None
    del mm
''')
neg('N20', 'with', 'with ... as arr liga el nombre', '''
    with abrir() as arr:
        pass
    arr = None
    del mm
''')
# N21: `with abrir() as q` NO liga el alias, y liberar dentro del with es
# seguro (__exit__ se ejecuta aunque el cuerpo falle). Es un CONTROL, no un
# negativo: se mueve a la familia de positivos.
pos('P09', 'with', 'libera dentro del with (no liga el alias)', '''
    with abrir() as q:
        arr = None
    del mm
''')
# ============ 7. MATCH / CASE ============
neg('N22', 'match', 'alias en un case', '''
    match v:
        case 1:
            b = arr
        case _:
            pass
    arr = None
    del mm
''')
neg('N23', 'match', 'match con un case que libera y otro que no', '''
    match v:
        case 1:
            arr = None
        case _:
            pass
    del mm
''')
neg('N24', 'match', 'del mm dentro de un case', '''
    match v:
        case 1:
            arr = None
            del mm
        case _:
            pass
''')
# ============ 8. RETORNO O CAPTURA POR FUNCIONES ============
neg('N25', 'retorno', 'return arr', '''
    arr = None
    del mm
    return arr
''')
neg('N26', 'retorno', 'return de un alias vivo', '''
    b = arr
    arr = None
    del mm
    return b
''')
neg('N27', 'captura', 'metodo de objeto recibe el alias', '''
    obj.guardar(arr)
    arr = None
    del mm
''')
# ============ 9. OTRAS CONSTRUCCIONES AST ============
neg('N28', 'fstring', 'el alias interpolado en f-string', '''
    t = f"{arr}"
    arr = None
    del mm
''')
neg('N29', 'dict_key', 'el alias como clave de diccionario', '''
    d2[arr] = 1
    arr = None
    del mm
''')
neg('N30', 'starred', 'el alias desempaquetado en una llamada', '''
    g2(*arr)
    arr = None
    del mm
''')
neg('N31', 'compare', 'comparacion que retiene en una expresion', '''
    if arr is not None:
        pass
    arr = None
    del mm
''')
neg('N32', 'contenedor', 'el alias dentro de una lista literal', '''
    l2 = [arr]
    arr = None
    del mm
''')
neg('N33', 'contenedor', 'el alias dentro de un dict literal', '''
    d3 = {"k": arr}
    arr = None
    del mm
''')
neg('N34', 'augassign', 'augassign sobre el alias', '''
    arr += 1
    del mm
''')
neg('N35', 'while', 'alias creado dentro de un while', '''
    while c:
        b = arr
        break
    arr = None
    del mm
''')
# ============ 10. CONTROLES POSITIVOS: DEBEN SEGUIR EN TRUE ============
pos('P01', 'control', 'sin alias, libera y borra', '''
    arr = None
    del mm
''')
pos('P02', 'control', 'atributo leido  arr.flush()', '''
    arr.flush()
    arr = None
    del mm
''')
# P03: una vista ASIGNADA retiene el almacenamiento -> ya NO es positivo.
# Se convierte en negativo. El consumo inmediato sin asignar es lo que prueba
# que el detector no rechaza operaciones realmente inocuas.
neg('N39', 'vista', 'vista asignada  x = arr[lo:hi]  retiene', '''
    x = arr[lo:hi]
    arr = None
    del mm
''')
# P04: el patron real de los motores. Las vistas viven dentro de un
# comprehension que liga su propio `arr` (sombreado), y arr.flush() es un
# metodo seguro. Este es el control que debe seguir dando C_TRUE.
pos('P04', 'control', 'patron real de motor: vistas en comprehension sombreado', '''
    regs = {pid: arr[lo:hi] for pid, arr in v_regs.items()}
    arr.flush()
    arr = None
    del mm
''')
# P05: solo funciones puras. `arr.dtype` en un descriptor, no un metodo de la
# lista segura: se retira del control (se prueba aparte como negativo).
pos('P05', 'control', 'len(), id(), repr() puras', '''
    n = len(arr)
    r5 = repr(arr)
    i5 = id(arr)
    arr = None
    del mm
''')
# REVISION 6: N40 era 'arr.dtype como valor' -> NO_CONCLUYENTE. Expectativa
# ERRONEA: arr.dtype devuelve un numpy.dtype, INMUTABLE, sin referencia al
# array. El detector ahora lo admite como metadato. Se sustituye por arr.T,
# que SI devuelve una VISTA, conservando el espiritu del caso: un atributo
# no es inocuo por ser atributo.
neg('N41', 'atributo', 'arr.T como valor devuelve una VISTA', '''
    t = arr.T
    arr = None
    del mm
''')
pos('P06', 'control', 'alias creado y liberado', '''
    b = arr
    b = None
    arr = None
    del mm
''')
neg('N36', 'control', 'alias en rama: la liberacion de b es condicional', '''
    if c:
        b = arr
        b = None
    b = None
    arr = None
    del mm
''')
neg('N37', 'control', 'del mm solo en el else: el otro camino no borra', '''
    arr = None
    if c:
        pass
    else:
        del mm
''', exacto=NO)
neg('N38', 'control', 'alias en rama: b sobrevive en el camino que no entra', '''
    if c:
        b = arr
        b = None
    arr = None
    del mm
''')

print('=' * 104)
print('BANCO REVISION 4: cierre conservador de formas AST no soportadas')
print('propuesta: %s' % RUTA)
print('=' * 104)
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
        ok = (estado == exacto)
        esp = exacto.replace('CONCLUYENTE_', 'C_')
    else:
        ok = (estado != OK)          # NEGATIVO: nunca TRUE
        esp = '!= C_TRUE'
    res.append(ok)
    if not ok:
        fallos.append((n, desc, estado, motivo))
    print('  %-4s  %-11s  %-50s  %-13s   %-13s   %s' % (
        n, fam, desc[:50], esp, str(estado).replace('CONCLUYENTE_', 'C_'),
        'PASS' if ok else 'FAIL -> ' + motivo[:26]))
print()
print('TOTAL: %d/%d PASS' % (sum(res), len(res)))
neg_total = sum(1 for c in CASOS if c[3] is None)
print('  negativos (nunca C_TRUE): %d' % neg_total)
print('  positivos (deben ser C_TRUE): %d' % (len(CASOS) - neg_total))
if fallos:
    print()
    print('FALLOS:')
    for n, desc, est, mot in fallos:
        print('  - %s %s -> %s (%s)' % (n, desc, est, mot[:50]))
sys.exit(0 if all(res) else 1)
