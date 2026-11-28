"""Banco REVISION 3: formas de alias que el detector debe DESCONFIAR.

Solo parsea texto. No ejecuta motores, ni main(), ni bateria().

Regla que se comprueba: ninguna construccion que pueda conservar el memmap
puede dar CONCLUYENTE_TRUE. Si el detector no puede seguirla, NO_CONCLUYENTE.
"""
import sys, ast, textwrap, os
from pathlib import Path
sys.dont_write_bytecode = True


def _localizar_propuesta():
    """PROPUESTA_6G1, junto al banco, 01_propuesta vecina, o /tmp/prop6g1."""
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
    """comun_6g1.py vive en scripts/ del proyecto; la PROPUESTA lo importa."""
    aqui = Path(__file__).resolve().parent
    for cand in (aqui, aqui.parent / 'papelera_no_usar',
                 Path('/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')):
        if (cand / 'comun_6g1.py').is_file():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            return cand
    return None


_asegurar_dependencias()
import importlib.util
_spec = importlib.util.spec_from_file_location('propuesta_6g1', str(_localizar_propuesta()))
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


def caso(n, desc, esperado, cuerpo):
    CASOS.append((n, desc, esperado, textwrap.dedent(CAB + cuerpo).strip()))


# ================= grupo OBLIGATORIO de Cris =================
caso('R3-A', 'OBLIGATORIO A: asignacion anotada  b: object = arr', DUD, '''
    b: object = arr
    arr = None
    del mm
''')
caso('R3-B', 'OBLIGATORIO B: asignacion encadenada  b = c = arr', DUD, '''
    b = c = arr
    arr = None
    del mm
''')
# ================= otras formas exigidas =================
caso('R3-C', 'desempaquetado  b, = (arr,)', DUD, '''
    b, = (arr,)
    arr = None
    del mm
''')
caso('R3-C2', 'desempaquetado multiple  b, c = (arr, arr)', DUD, '''
    b, c = (arr, arr)
    arr = None
    del mm
''')
caso('R3-D', 'NamedExpr  (b := arr)', DUD, '''
    if (b := arr) is not None:
        pass
    arr = None
    del mm
''')
caso('R3-E', 'atributo  obj.ref = arr', DUD, '''
    obj.ref = arr
    arr = None
    del mm
''')
caso('R3-F', 'contenedor  lista.append(arr)', DUD, '''
    lista.append(arr)
    arr = None
    del mm
''')
caso('R3-G', 'subscript  d["k"] = arr', DUD, '''
    d["k"] = arr
    arr = None
    del mm
''')
caso('R3-H', 'alias dentro de rama if', NO, '''
    if c:
        b = arr
    arr = None
    del mm
''')
caso('R3-I', 'alias dentro de try', NO, '''
    try:
        b = arr
    finally:
        pass
    arr = None
    del mm
''')
caso('R3-J', 'alias DESPUES de arr = None desde b viva', DUD, '''
    b = arr
    arr = None
    c = b
    del mm
''')
caso('R3-K', 'alias despues de liberar desde k viva', DUD, '''
    k = arr
    arr = None
    d = k
    del mm
''')
# ================= controles: deben seguir funcionando =================
caso('R3-M', 'CONTROL: sin alias, libera -> C_TRUE', OK, '''
    arr = None
    del mm
''')
caso('R3-N', 'CONTROL: alias simple b = arr -> C_FALSE', NO, '''
    b = arr
    arr = None
    del mm
''')
caso('R3-O', 'CONTROL: alias liberado despues -> C_TRUE', OK, '''
    b = arr
    arr = None
    b = None
    del mm
''')
caso('R3-P', 'CONTROL: alias creado y liberado sin ramas -> C_TRUE', OK, '''
    b = arr
    b = None
    arr = None
    del mm
''')

print('=' * 90)
print('BANCO REVISION 3: formas de alias no reconocidas')
print('propuesta: %s' % _localizar_propuesta())
print('=' * 90)
print()
print('  ID      caso                                                  esperado        obtenido        res')
print('  ------  ----------------------------------------------------  --------------  --------------  ----')
res = []
for n, desc, esperado, src in CASOS:
    try:
        r = m._analizar_cadena(ast.parse(src))
        estado, motivo = r['estado_global'], str(r['motivo'])
    except Exception as exc:
        estado, motivo = 'EXC', repr(exc)[:40]
    ok = (estado == esperado)
    res.append(ok)
    print('  %-6s  %-52s  %-13s   %-13s   %s' % (
        n, desc[:52], esperado.replace('CONCLUYENTE_', 'C_'),
        str(estado).replace('CONCLUYENTE_', 'C_'), 'PASS' if ok else 'FAIL -> ' + motivo[:34]))
print()
print('TOTAL: %d/%d PASS' % (sum(res), len(res)))
if not all(res):
    print('FALLAN:')
    for (n, desc, _e, _s), ok in zip(CASOS, res):
        if not ok:
            print('  - %s  %s' % (n, desc))
sys.exit(0 if all(res) else 1)
