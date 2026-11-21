"""Inyector de fallos para las pruebas T1/T2/T4 de la rectificación 6G.1.

Se activa sólo si el entorno define SDVSDI_6G1_INJECT (y SDVSDI_6G1_MOTORES).
Carga el MISMO módulo lectura_segura_6g1 que importará el motor (queda en
sys.modules) y sustituye el método indicado de MixHandle:

- verificar_raise : verificar() lanza excepción (T1: excepción de verificación).
- ruta_raise      : ruta_apunta_al_mismo_objeto() lanza excepción (T2).
- verificar_false : verificar() devuelve un dict no satisfactorio (T4:
                    verificación fallida sin excepción).

La guarda final fail-closed debe tratar los tres casos igual: aborto, sin
publicación. No se modifica ningún archivo del motor ni del módulo.
"""
import os
import sys

_inj = os.environ.get('SDVSDI_6G1_INJECT', '')
_dir = os.environ.get('SDVSDI_6G1_MOTORES', '')
if _inj and _dir:
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    import lectura_segura_6g1 as _L

    if _inj == 'verificar_raise':
        def _verificar_rota(self, *a, **k):
            raise RuntimeError('inyeccion de prueba T1: verificar() fallo')
        _L.MixHandle.verificar = _verificar_rota
    elif _inj == 'ruta_raise':
        def _ruta_rota(self, *a, **k):
            raise RuntimeError('inyeccion de prueba T2: ruta_apunta_al_mismo_objeto() fallo')
        _L.MixHandle.ruta_apunta_al_mismo_objeto = _ruta_rota
    elif _inj == 'verificar_false':
        def _verificar_falso(self, *a, **k):
            return dict(unchanged=False,
                        reason='inyeccion de prueba T4: verificacion no satisfactoria')
        _L.MixHandle.verificar = _verificar_falso
