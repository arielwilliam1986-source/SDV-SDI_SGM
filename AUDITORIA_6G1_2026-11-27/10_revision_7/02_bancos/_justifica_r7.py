"""Revision 7: tabla de firmas y argumentos analizados, por cada admitido.

NO usa numpy. Documenta, para cada entrada de las listas blancas, QUE argumento
puede cambiar la naturaleza del resultado y QUE hace el detector con el.
"""
import sys
sys.dont_write_bytecode = True

# (metodo, firma documentada relevante, argumentos que alteran el resultado, tratamiento)
FILAS = [
  # --- _METODOS_VISTA: reducciones a escalar ---
  ('sum',    'sum(axis=None, dtype=None, out=None, keepdims=False, initial=, where=)',
             'out', 'out presente (kw, posicional o *args/**kwargs) -> NO_CONCLUYENTE'),
  ('mean',   'mean(axis=None, dtype=None, out=None, keepdims=False, where=)',
             'out', 'idem'),
  ('std',    'std(axis=None, dtype=None, out=None, ddof=0, keepdims=False, where=)',
             'out', 'idem'),
  ('var',    'var(axis=None, dtype=None, out=None, ddof=0, keepdims=False, where=)',
             'out', 'idem'),
  ('prod',   'prod(axis=None, dtype=None, out=None, keepdims=False, initial=, where=)',
             'out', 'idem'),
  ('min',    'min(axis=None, out=None, keepdims=False, initial=, where=)',
             'out', 'posicion de out = 2a; >=2 posicionales -> NO_CONCLUYENTE'),
  ('max',    'max(axis=None, out=None, keepdims=False, initial=, where=)',
             'out', 'idem'),
  ('argmin', 'argmin(axis=None, out=None, *, keepdims=False)',
             'out', 'posicion de out = 2a; >=2 posicionales -> NO_CONCLUYENTE'),
  ('argmax', 'argmax(axis=None, out=None, *, keepdims=False)',
             'out', 'idem'),
  ('any',    'any(axis=None, out=None, keepdims=False, *, where=)',
             'out', 'posicion de out = 2a; >=2 posicionales -> NO_CONCLUYENTE'),
  ('all',    'all(axis=None, out=None, keepdims=False, *, where=)',
             'out', 'idem'),
  ('item',   'item(*args)  (sin argumentos: escalar; con args: indice)',
             'args posicionales', 'no se pasa out; el resultado sigue siendo escalar'),
  ('tolist', 'tolist()  (SIN argumentos en ndarray)',
             'ninguno propio', '*args/**kwargs -> NO_CONCLUYENTE'),
  ('tobytes', 'tobytes(order="C")',
             'order', 'order no cambia la identidad: devuelve bytes nuevos'),
  # --- _METODOS_COPIA ---
  ('copy',   'copy(order="C")',
             'order', 'order no cambia la identidad: .base es None siempre'),
  ('flatten', 'flatten(order="C")',
             'order', 'SIEMPRE copia; order solo cambia el orden de recorrido'),
  # --- _METODOS_SEGUROS (del alias) ---
  ('flush',  'flush()  (SIN argumentos)',
             'ninguno', '*args/**kwargs -> NO_CONCLUYENTE'),
  ('close',  'close()  (SIN argumentos)',
             'ninguno', '*args/**kwargs -> NO_CONCLUYENTE'),
  # --- astype (caso especial) ---
  ('astype', 'astype(dtype, order="K", casting="unsafe", subok=True, copy=True)',
             'copy  (la UNICA que cambia la identidad)', 'exige copy=True DEMOSTRADO'),
]
ATRIBUTOS = [
  ('shape',    'tupla de enteros',      'inmutable, sin buffer'),
  ('strides',  'tupla de enteros',      'inmutable, sin buffer'),
  ('ndim',     'entero',                'inmutable'),
  ('size',     'entero',                'inmutable'),
  ('nbytes',   'entero',                'inmutable'),
  ('itemsize', 'entero',                'inmutable'),
  ('dtype',    'numpy.dtype',           'objeto inmutable, sin ref al array'),
]
RETIRADOS = [
  ('ravel',     'ravel(order="C")',    'PUEDE devolver vista'),
  ('reshape',   'reshape(*shape)',     'PUEDE devolver vista'),
  ('transpose', 'transpose(*axes)',    'SIEMPRE vista'),
  ('swapaxes',  'swapaxes(a1, a2)',    'SIEMPRE vista'),
  ('clip',      'clip(min=, max=, out=None)', 'out= escribe fuera; puede devolver el propio array'),
  ('round',     'round(decimals=0, out=None)', 'out= escribe fuera'),
  ('take',      'take(indices, axis=None, out=None, mode=)', 'out= escribe fuera'),
  ('repeat',    'repeat(repeats, axis=None)', 'contrato no simple'),
  ('count',     '(NO EXISTE en ndarray)', '-'),
  ('index',     '(NO EXISTE en ndarray)', '-'),
]
NO_ADMITIDOS = ['data', '__array_interface__', 'base', 'T', 'real', 'imag', 'flat']

print('=' * 118)
print('REVISION 7 - JUSTIFICACION INDIVIDUAL DE CADA ADMITIDO')
print('Criterio: se admite <=> NINGUN argumento puede hacer que el resultado')
print('retenga el memmap. Todo argumento que pueda cambiarlo -> NO_CONCLUYENTE.')
print('=' * 118)
print()
print('A) _METODOS_VISTA y _METODOS_COPIA  (sobre una VISTA arr[a:b])')
print()
print('  %-8s  %-62s  %s' % ('metodo', 'firma documentada (resumida)', 'tratamiento'))
print('  %-8s  %-62s  %s' % ('-'*8, '-'*62, '-'*11))
for met, firma, peligro, trato in FILAS:
    if met in ('copy', 'flatten', 'flush', 'close', 'astype'):
        continue
    print('  %-8s  %-62s  %s' % (met, firma[:62], trato))
print()
print('B) _METODOS_COPIA  (sobre una VISTA)')
print()
print('  %-8s  %-62s  %s' % ('metodo', 'firma documentada', 'tratamiento'))
print('  %-8s  %-62s  %s' % ('-'*8, '-'*62, '-'*11))
for met, firma, peligro, trato in FILAS:
    if met not in ('copy', 'flatten'):
        continue
    print('  %-8s  %-62s  %s' % (met, firma[:62], trato))
print()
print('C) _METODOS_SEGUROS  (sobre el ALIAS arr)')
print()
for met, firma, peligro, trato in FILAS:
    if met not in ('flush', 'close'):
        continue
    print('  %-8s  %-62s  %s' % (met, firma[:62], trato))
print()
print('D) astype  (caso especial: se analizan los ARGUMENTOS)')
print()
for met, firma, peligro, trato in FILAS:
    if met != 'astype':
        continue
    print('  %-8s  %s' % (met, firma))
    print('           argumento que cambia la identidad: %s' % peligro)
    print('           tratamiento: %s' % trato)
print()
print('E) _ATRIBUTOS_METADATO  (sobre el ALIAS)')
print()
print('  %-10s  %-20s  %s' % ('atributo', 'tipo del resultado', 'por que no retiene'))
print('  %-10s  %-20s  %s' % ('-'*10, '-'*20, '-'*20))
for a, t, why in ATRIBUTOS:
    print('  %-10s  %-20s  %s' % (a, t, why))
print()
print('F) _METODOS_VISTA_RETIRADOS (NO_CONCLUYENTE, con motivo)')
print()
print('  %-11s  %-40s  %s' % ('metodo', 'firma', 'motivo del rechazo'))
print('  %-11s  %-40s  %s' % ('-'*11, '-'*40, '-'*22))
for a, t, why in RETIRADOS:
    print('  %-11s  %-40s  %s' % (a, t[:40], why))
print()
print('G) ATRIBUTOS NO ADMITIDOS')
print()
print('  %s' % ', '.join(NO_ADMITIDOS))
print('  motivo: devuelven el BUFFER (data, __array_interface__), el objeto del')
print('  que se tomo la vista (base) o VISTAS (T, real, imag) o un iterador VIVO')
print('  sobre el array (flat).')
print()
print('=' * 118)
