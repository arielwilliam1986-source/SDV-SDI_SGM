"""Auditoria ESTATICA de los tres motores para la revision 5.

NO ejecuta los motores. Solo lee su AST desde el commit publicado y enumera
cada aparicion de la variable de bucle, su contexto y si el detector puede
demostrar que no retiene el recurso.

Los ficheros se leen con `git show fcc2792:<ruta>`: no se copian, no se
modifican y no se importan.
"""
import sys, ast, subprocess, collections
from pathlib import Path
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')
import importlib.util
_spec = importlib.util.spec_from_file_location(
    'propuesta_6g1', '/tmp/prop6g1/pruebas_auditoria_cierre_6g1.PROPUESTA.py')
m = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(m)

RAIZ = '/home/user/SDV-SDI_SGM'
COMMIT = 'fcc2792'
MOTORES = [
    ('Hardened', 'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py'),
    ('EVO',      'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_EVO.py'),
    ('MQR',      'ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/sdv_sdi_mqr_engine.py'),
]


def leer(rel):
    return subprocess.run(['git', 'show', '%s:%s' % (COMMIT, rel)],
                          capture_output=True, text=True, cwd=RAIZ).stdout


def funciones_con_del(t):
    out = []
    for fn in ast.walk(t):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(isinstance(n, ast.Delete)
               and any(isinstance(x, ast.Name) and x.id == 'mm' for x in n.targets)
               for n in ast.walk(fn)):
            out.append(fn)
    return out


print('=' * 100)
print('AUDITORIA ESTATICA DE LOS TRES MOTORES  (revision 5)')
print('Fuente: git show %s:<ruta>   (lectura, sin copia ni ejecucion)' % COMMIT)
print('=' * 100)
print()

resumen = {}
for nombre, rel in MOTORES:
    txt = leer(rel)
    t = ast.parse(txt)
    print('=' * 100)
    print('MOTOR %s' % nombre)
    print('  fichero: %s' % rel)
    print('  lineas:  %d' % len(txt.split('\n')))
    print('=' * 100)
    for fn in funciones_con_del(t):
        vars_ = sorted({n.target.id for n in ast.walk(fn)
                        if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
                        and any(isinstance(x, ast.Name) and x.id == 'mm' for x in ast.walk(n.iter))})
        print('  funcion %s  (lineas %d-%d)   variable(s) de bucle: %s'
              % (fn.name, fn.lineno, fn.end_lineno, ', '.join(vars_)))
        print()
        # mapa de padres
        cam = {}
        for p in ast.walk(fn):
            for h in ast.iter_child_nodes(p):
                cam[h] = p
        for var in vars_:
            print('    Usos de `%s`:' % var)
            print('      linea  ctx     contexto real                              ambito  veredicto')
            print('      -----  ------  -----------------------------------------  ------  ---------')
            for nodo in ast.walk(fn):
                if not (isinstance(nodo, ast.Name) and nodo.id == var):
                    continue
                padre = cam.get(nodo)
                abuelo = cam.get(padre) if padre else None
                campo = None
                if padre is not None:
                    for c, v in ast.iter_fields(padre):
                        if v is nodo or (isinstance(v, list) and any(x is nodo for x in v)):
                            campo = c
                            break
                campo_ab = None
                if abuelo is not None:
                    for c, v in ast.iter_fields(abuelo):
                        if v is padre:
                            campo_ab = c
                            break
                if isinstance(nodo.ctx, (ast.Store, ast.Del)):
                    tipo = 'store/del'
                    ver = 'modelado por el detector'
                    amb = 'n/a'
                else:
                    amb = 'propio' if m._ambito(fn, nodo, var) else 'SOMBREADO'
                    tipo, desc = m._clasificar_contexto(padre, campo, {var}, abuelo, campo_ab)
                    ver = 'INOCUO' if tipo is None else tipo
                # El fragmento debe ser la sentencia que CONTIENE el uso, no
                # el nodo padre (para un Store el padre es el `for`, y para un
                # Load dentro de un Subscript seria solo `arr[lo:hi]`).
                frag = ast.unparse(padre)[:41] if padre is not None else '?'
                if isinstance(nodo.ctx, (ast.Store, ast.Del)):
                    _cont = padre
                    for _ in range(3):
                        if isinstance(_cont, ast.stmt):
                            frag = ast.unparse(_cont)[:41].replace('\n', ' ')
                            break
                        _cont = cam.get(_cont)
                    else:
                        frag = ast.unparse(padre)[:41].replace('\n', ' ')
                print('      %-5d  %-6s  %-41s  %-6s  %s'
                      % (nodo.lineno, type(nodo.ctx).__name__[:6], frag, amb[:6], ver))
            print()
        # veredicto del detector
        r = m._analizar_funcion(fn)
        resumen.setdefault(nombre, []).append((fn.name, r['estado'], r['motivo']))
        print('    Veredicto del detector: %s' % r['estado'])
        print('      motivo: %s' % r['motivo'])
        print('      caminos: %s | aperturas: %s' % (r['caminos'], r['aperturas']))
        print()

print('=' * 100)
print('RESUMEN DE ADJUDICACION ESTATICA')
print('=' * 100)
for nombre, _ in MOTORES:
    txt = leer(dict(MOTORES)[nombre])
    r = m._analizar_cadena(ast.parse(txt))
    print('  %-9s %s' % (nombre, r['estado_global']))
    print('            %s' % r['motivo'])
todos = []
for nombre, _ in MOTORES:
    todos.append(m._analizar_cadena(ast.parse(leer(dict(MOTORES)[nombre])))['estado_global'])
print()
print('  GLOBAL: %s' % ('CONCLUYENTE_TRUE' if set(todos) == {'CONCLUYENTE_TRUE'}
                        else ' / '.join(sorted(set(todos)))))
print()
print('  ADVERTENCIA: esta adjudicacion es ESTATICA. NO demuestra nada en tiempo')
print('  de ejecucion. validacion_dinamica sigue PENDIENTE. No se han ejecutado')
print('  los motores.')
print('=' * 100)
