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
_out = os.environ.get('SDVSDI_6G1_OUT', '')
_plantar = os.environ.get('SDVSDI_6G1_PLANTAR', '')


def _plantar_6g1():
    """[E1/E2/E3 end-to-end] Siembra determinista en el instante de la guarda:
    crea enlaces simbólicos o reemplaza archivos dentro del *_partial de la
    corrida (simula el estado atacado justo antes del aborto, sin tocar el
    código del motor). Formato: modo:nombre@ruta, separado por ';'.
    modos: enlace (symlink hacia @ruta) | archivo (copia regular de @ruta)."""
    import glob as _glob
    parciales = sorted(_glob.glob(os.path.join(_out, '*_partial')))
    if not parciales:
        return
    base = parciales[0]
    for spec in [x for x in _plantar.split(';') if x]:
        modo, resto = spec.split(':', 1)
        nombre, ruta = resto.split('@', 1)
        if modo == 'enlace':
            tmp = base + '.__lnk__'
            if os.path.lexists(tmp):
                os.unlink(tmp)
            os.symlink(ruta, tmp)
            os.replace(tmp, os.path.join(base, nombre))
        elif modo == 'archivo':
            tmp = base + '.__cop__'
            with open(ruta, 'rb') as fsrc, open(tmp, 'wb') as fdst:
                fdst.write(fsrc.read())
            os.replace(tmp, os.path.join(base, nombre))


if _inj and _dir:
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    import lectura_segura_6g1 as _L

    if _inj == 'verificar_raise':
        def _verificar_rota(self, *a, **k):
            if _plantar:
                _plantar_6g1()
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
