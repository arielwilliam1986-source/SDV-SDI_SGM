"""Banco REVISION 2 del detector F. Solo parsea texto: no ejecuta motores."""
import sys, ast, textwrap, os
from pathlib import Path
sys.dont_write_bytecode = True
def _localizar_propuesta():
    """Localiza pruebas_auditoria_cierre_6g1.PROPUESTA.py.

    1) variable de entorno PROPUESTA_6G1;
    2) junto a este banco (carpeta 01_propuesta de la entrega);
    3) /tmp/prop6g1 (entorno de trabajo del auditor).
    """
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

# ---- R: el bloqueo 2 y su familia ----
caso('R4', 'BLOQUEO 2: if con del / else pass', NO, '''
    mm = {}
    for arr in mm.values():
        arr.flush()
    arr = None
    if condicion:
        del mm
    else:
        pass
''')
caso('R5', 'del mm solo en una rama (sin else)', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        if c:
            del mm
''')
caso('R6', 'del mm en ambas ramas', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        if c:
            del mm
        else:
            del mm
''')
caso('R7', 'ramas anidadas: solo la interna borra', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        if a:
            if b:
                del mm
        else:
            pass
''')
caso('R8', 'ramas anidadas: todas borran', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        if a:
            if b:
                del mm
            else:
                del mm
        else:
            del mm
''')
# ---- V: dos variables de bucle distintas ----
caso('V1', 'dos variables de bucle sobre mm.values()', DUD, BASE + '''
        for x in mm.values():
            x.flush()
        for y in mm.values():
            y.flush()
        x = None
        del mm
''')
caso('V2', 'dos variables, ambas liberadas', OK, BASE + '''
        for x in mm.values():
            x.flush()
        for y in mm.values():
            y.flush()
        x = None
        y = None
        del mm
''')
# ---- A: alias y cadenas ----
caso('A5', 'cadena de alias, todos liberados', OK, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        c = b
        arr = None
        b = None
        c = None
        del mm
''')
caso('A6', 'cadena de alias, solo el ultimo liberado', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        b = arr
        c = b
        arr = None
        del mm
''')
# ---- H: helpers ----
caso('H3', 'helper que recibe y NO libera: no demostrable', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
            registrar(arr)
        arr = None
        del mm
''')
caso('H4', 'helper fuera del bucle', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        registrar(arr)
        arr = None
        del mm
''')
# ---- D: varios del ----
caso('D3', 'tres del mm, el segundo incompleto', NO, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        del mm
        mm = {}
        if w2:
            for i in r:
                mm[i] = np.load(q, mmap_mode="r")
        del mm
        mm = {}
        if w3:
            for i in r:
                mm[i] = np.load(q, mmap_mode="r")
            for arr in mm.values():
                arr.flush()
            arr = None
        del mm
''')
# ---- T: try/except/finally ----
caso('T3', 'try/except/finally completo', DUD, BASE + '''
        try:
            for arr in mm.values():
                arr.flush()
            arr = None
        except Exception:
            arr = None
        finally:
            del mm
''')
# ---- M: reasignaciones ----
caso('M1', 'mm reasignado antes del del', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        mm = {}
        del mm
''')
caso('M2', 'variable de bucle reasignada con otro memmap', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = np.load(q, mmap_mode="r")
        arr = None
        del mm
''')
caso('M3', 'variable de bucle reasignada tras liberar', DUD, BASE + '''
        for arr in mm.values():
            arr.flush()
        arr = None
        arr = np.load(q, mmap_mode="r")
        del mm
''')

print('  ID   caso                                                  esperado       obtenido       res')
print('  ---  ----------------------------------------------------  -------------  -------------  ----')
res = []
for n, desc, esperado, src in CASOS:
    try:
        r = m._analizar_cadena(ast.parse(src))
        estado, motivo = r['estado_global'], r['motivo']
    except Exception as exc:
        estado, motivo = 'EXC', repr(exc)[:40]
    ok = (estado == esperado)
    res.append(ok)
    print('  %-4s %-52s %-13s  %-13s  %s' % (n, desc[:52],
          esperado.replace('CONCLUYENTE_', 'C_'), str(estado).replace('CONCLUYENTE_', 'C_'),
          'PASS' if ok else 'FAIL -> ' + motivo[:30]))
print()
print('TOTAL: %d/%d PASS' % (sum(res), len(res)))
