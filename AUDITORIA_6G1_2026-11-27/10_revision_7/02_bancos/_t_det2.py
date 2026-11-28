"""Banco adversarial del detector F. Solo parsea texto: no ejecuta motores."""
import sys, ast, textwrap
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')
import importlib.util
spec = importlib.util.spec_from_file_location('prop', '/tmp/prop6g1/pruebas_auditoria_cierre_6g1.PROPUESTA.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

OK, NO, DUD = m.F_OK, m.F_NO, m.F_DUDOSO
C = 'np.load(p / "m.npy", mmap_mode="r")'
BASE = f'''
    mm = {{}}
    if w:
        for i in r:
            mm[i] = {C}
'''
CASOS = []


def caso(n, desc, esperado, cuerpo):
    CASOS.append((n, desc, esperado, textwrap.dedent('def f():\n' + cuerpo).strip()))


# --- orden de liberacion respecto al ultimo flush ---
caso('R1', 'liberacion DESPUES del ultimo flush (patron real)', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
''')
caso('R2', 'liberacion ANTES del ultimo flush (caso 16)', DUD, BASE + '''
        arr = None
        for arr in mm.values():
            arr.flush()
        del mm
''')
caso('R3', 'reenganche de arr despues de arr = None', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        arr = mm["x"]
        del mm
''')
# --- alias antes y despues de la liberacion ---
caso('A1', 'alias b = arr ANTES de liberar, b sobrevive (fuga)', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        arr = None
        del mm
''')
caso('A2', 'alias ANTES de liberar, b liberado despues de arr (correccion manual)', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        arr = None
        b = None
        del mm
''')
caso('A3', 'alias DESPUES de liberar: arr ya es None, b no retiene nada (pero no se puede probar)', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        b = arr
        del mm
''')
caso('A4', 'alias en cadena: b = arr; c = b; solo b liberado', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        c = b
        arr = None
        b = None
        del mm
''')
# --- ramas ---
caso('B1', 'if/else: una rama libera, otra no', NO, BASE + '''
        if x:
            for arr in mm.values():
                arr.flush()
            arr = None
        else:
            for arr in mm.values():
                arr.flush()
        del mm
''')
caso('B2', 'if/else: ambas ramas liberan y borran', OK, BASE + '''
        if x:
            for arr in mm.values():
                arr.flush()
            arr = None
            del mm
        else:
            for arr in mm.values():
                arr.flush()
            arr = None
            del mm
''')
caso('B3', 'liberacion condicional sin `del` asociado', DUD, BASE + '''
        if x:
            arr = None
        for arr in mm.values():
            arr.flush()
        del mm
''')
# --- varios del ---
caso('D1', 'segundo del mm sin liberar entre medias', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
        mm = {}
        for i in r:
            mm[i] = np.load(q, mmap_mode="r")
        del mm
''')
caso('D2', 'dos del mm, ambos con secuencia completa', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
        mm = {}
        if w2:
            for i in r:
                mm[i] = np.load(q, mmap_mode="r")
            for arr in mm.values():
                arr.flush()
            arr = None
        del mm
''')
# --- flush en try ---
caso('T1', 'flush dentro de try, del en finally', DUD, BASE + '''
        try:
            for arr in mm.values():
                arr.flush()
            arr = None
        finally:
            del mm
''')
caso('T2', 'flush dentro de try, del fuera', DUD, BASE + '''
        try:
            for arr in mm.values():
                arr.flush()
            arr = None
        except Exception:
            pass
        del mm
''')
# --- helpers ---
caso('H1', 'referencia transferida a una funcion', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
            guardar(arr)
        arr = None
        del mm
''')
caso('H2', 'liberacion en una funcion distinta', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        del mm

def g():
    mm = {}
    if w:
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
''')
# --- sin del / sintaxis / no demostrable ---
caso('X1', 'sintaxis invalida', NO, 'def f(:\n        pass\n')
CASOS[-1] = ('X1', 'sintaxis invalida', NO, 'def f(:\n    pass')
caso('X2', 'sin del mm', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
''')
caso('X3', 'guardián vacío (cero aperturas y cero liberaciones)', DUD, '''
    mm = {}
    if x:
        del mm
''')
caso('X4', 'contenedor reenganchado tras liberar', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
        mm = {}
        if q:
            del mm
''')


# --- casos heredados del banco anterior, revalidados ---
caso('C1', 'secuencia correcta simple (legado 1)', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
''')
caso('C2', 'ausencia de arr = None (legado 2)', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        del mm
''')
caso('C3', 'arr = None solo en una rama (legado 3)', NO, BASE + '''
        if x:
            for arr in mm.values():
                arr.flush()
            arr = None
            del mm
        else:
            del mm
''')
caso('C4', 'aperturas de mm dentro de bucles (legado 6)', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
''')
caso('C5', 'arr = None antes del bucle (legado 16 corregido)', DUD, BASE + '''
        arr = None
        for arr in mm.values():
            arr.flush()
        del mm
''')
caso('C6', 'alias b = arr sin liberar, b sobrevive (legado 8)', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        arr = None
        del mm
''')

print('  ID   caso                                                  esperado       obtenido       res')
print('  ---  ----------------------------------------------------  -------------  -------------  ----')
res = []
for n, desc, esperado, src in CASOS:
    if n == 'X1':
        try:
            ast.parse(src); estado = 'NO_PARSEA'
        except SyntaxError:
            estado = NO
        motivo = 'SyntaxError'
    else:
        try:
            r = m._analizar_cadena(ast.parse(src))
            estado, motivo = r['estado_global'], r['motivo']
        except Exception as exc:
            estado, motivo = 'EXC', repr(exc)[:40]
    ok = (estado == esperado)
    res.append(ok)
    print('  %-4s %-52s %-13s  %-13s  %s' % (n, desc[:52], esperado.replace('CONCLUYENTE_', 'C_'),
                                             str(estado).replace('CONCLUYENTE_', 'C_'),
                                             'PASS' if ok else 'FAIL -> ' + motivo[:34]))
print()
print('TOTAL: %d/%d PASS' % (sum(res), len(res)))
