"""Revision 6: comprobacion de la lista blanca por RESULTADO, no por nombre.

NO usa numpy. NO importa el proyecto (solo el detector). Compara, variante por
variante, la semantica DOCUMENTADA de NumPy con lo que el detector decide.
"""
import sys, ast, importlib.util
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts')
spec = importlib.util.spec_from_file_location('P', '/tmp/prop6g1/pruebas_auditoria_cierre_6g1.PROPUESTA.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
CAB = '''def f():
    mm = {}
    for i in r:
        mm[i] = np.load(p / "m.npy", mmap_mode="r")
    for arr in mm.values():
        {cuerpo}
'''
# (variante, cuerpo, INDEPENDIENTE segun la documentacion de NumPy)
VARIANTES = [
  ("ravel()",                      "v = arr[lo:hi].ravel()",                      False),
  ("ravel(order='C')",             "v = arr[lo:hi].ravel(order='C')",             False),
  ("ravel(order='K')",             "v = arr[lo:hi].ravel(order='K')",             False),
  ("reshape(-1)",                  "v = arr[lo:hi].reshape(-1)",                  False),
  ("transpose()",                  "v = arr[lo:hi].transpose()",                  False),
  ("astype(copy=False)",           "v = arr[lo:hi].astype(copy=False)",           False),
  ("astype(arr.dtype, copy=False)","v = arr[lo:hi].astype(arr.dtype, copy=False)",False),
  ("clip(0,1)",                    "v = arr[lo:hi].clip(0, 1)",                   False),
  ("round(2)",                     "v = arr[lo:hi].round(2)",                     False),
  ("zzz() (no existe)",            "v = arr[lo:hi].zzz()",                        False),
  ("copy()",                       "v = arr[lo:hi].copy()",                        True),
  ("flatten()",                    "v = arr[lo:hi].flatten()",                     True),
  ("astype(np.float32)",           "v = arr[lo:hi].astype(np.float32)",            True),
  ("astype(np.float32, copy=True)","v = arr[lo:hi].astype(np.float32, copy=True)", True),
  ("tolist()",                     "v = arr[lo:hi].tolist()",                      True),
  ("tobytes()",                    "v = arr[lo:hi].tobytes()",                     True),
  ("sum()",                        "v = arr[lo:hi].sum()",                         True),
  ("mean()/std()/argmax()/item()", "a=arr[lo:hi].mean(); b=arr[lo:hi].std(); "
                                   "c=arr[lo:hi].argmax(); d=arr[lo:hi].item()",   True),
]
print('=' * 104)
print('LISTA BLANCA POR RESULTADO  (revision 6)')
print('Comparacion entre la semantica documentada de NumPy y la decision del detector.')
print('=' * 104)
print()
print('  %-32s %-8s %-18s %s' % ('variante', 'indep.?', 'veredicto', 'correcto?'))
print('  %-32s %-8s %-18s %s' % ('-'*32, '-'*8, '-'*18, '-'*9))
malos = 0
for titulo, cuerpo, indep in VARIANTES:
    src = CAB.replace('{cuerpo}', cuerpo + '\n        arr.flush()\n        arr = None\n    del mm\n')
    r = m._analizar_funcion(ast.parse(src).body[0])
    admite = r['estado'] == 'CONCLUYENTE_TRUE'
    ok = (admite == indep)
    if not ok: malos += 1
    print('  %-32s %-8s %-18s %s'
          % (titulo, 'SI' if indep else 'NO', r['estado'][:18],
             'OK' if ok else '*** INCORRECTO ***'))
print()
print('  %d variantes, %d incorrectas.' % (len(VARIANTES), malos))
print()
print('  Criterio aplicado: se admite <=> el RESULTADO documentado no comparte')
print('  almacenamiento con el memmap. Es una condicion sobre el resultado, no')
print('  sobre el nombre del metodo, y en astype se comprueban los ARGUMENTOS.')
print('=' * 104)
sys.exit(1 if malos else 0)
