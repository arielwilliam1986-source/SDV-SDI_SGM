#!/usr/bin/env python3
"""6G.1 / CR-R1: prueba focalizada del PROTOCOLO de cierre previo al aborto
(preparar_aborto_6g1 -> abortar_corrida_6g1), sin motores ni DSP.

Cada caso crea un provisional acreditado con crear_y_acreditar_dir_6g1(),
con un WAV parcial propio (registrado como en curso), un archivo ajeno,
engine_log.txt abierto por la "corrida" y un destino `<final>_aborted`
PREEXISTENTE. Después invoca el protocolo con trasladar=True:

  P0  control: lector y log se cierran bien -> completo=True, ABORT
      registrado y traslado sin reemplazo a `<final>_aborted_r001`.
  P1  fallo de cierre de un LECTOR (OSError en close(); el SoundFile real
      sobre el fixture queda abierto, sólo lectura y fuera del provisional)
      -> error documentado en engine_log.txt (el log aún está disponible),
      completo=False, ABORT registrado, SIN traslado.
  P2  fallo al cerrar el LOG: cerrar_log() cierra el archivo y luego eleva
      OSError (p. ej. error al vaciar) -> no queda ningún descriptor abierto,
      pero el cierre debe quedar incompleto: completo=False, ABORT
      registrado, SIN traslado; el error queda en el informe y en el motivo
      de conservación (el log ya no está disponible).
  P3  fallo al cerrar el LOG dejando el descriptor ABIERTO -> completo=False,
      SIN traslado (control: la comprobación en /proc ya lo detectaba).

Comprobaciones por caso: completo esperado; error documentado; ABORT_6G1.json
con schema abort-6g1/3, motivo y resultados_validos=[]; WAV parcial
invalidado y conservado; ajeno conservado; provisional en su ubicación (o
trasladado sólo en P0); destino preexistente intacto; ningún `_aborted_r*`
creado salvo en P0; sin publicación como éxito; ningún archivo eliminado.

`--base DIR --etiqueta-base X` repite los casos sobre otra copia del módulo
(diagnóstico; no cambia el veredicto).
Evidencia: evidence/pruebas_protocolo_cierre_cr_r1_6g1.json y
           evidence/matriz_protocolo_cierre_cr_r1_6g1.csv
Salida 0 sólo si todos los casos sobre el módulo corregido dan PASS.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from comun_6g1 import FIX, MOT, entorno, sha_file  # noqa: E402

import numpy as np            # noqa: E402
import soundfile as sf        # noqa: E402

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1cr_r1_protocolo')
MOTIVO = 'EXCEPCION_DURANTE_EL_PROCESAMIENTO'
AJENO = b'archivo ajeno (CR-R1 protocolo)\n'
MARCA = b'destino preexistente: no debe reemplazarse\n'
ERR_LECTOR = 'inyeccion CR-R1 P1: fallo de E/S al cerrar el lector'
ERR_LOG = 'inyeccion CR-R1: fallo al cerrar engine_log.txt'

CASOS = {
    'P0': ('Control: lector y log se cierran correctamente', True, True),
    'P1': ('Fallo de cierre de un lector (queda abierto)', False, False),
    'P2': ('Fallo al cerrar el log tras cerrar el archivo (sin descriptor vivo)',
           False, False),
    'P3': ('Fallo al cerrar el log dejando el descriptor abierto', False, False),
}


def cargar_modulo(carpeta, nombre):
    spec = importlib.util.spec_from_file_location(
        nombre, str(Path(carpeta) / 'lectura_segura_6g1.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LectorQueFalla:
    """Lector real (SoundFile sobre el fixture) cuyo close() eleva OSError sin
    cerrar nada: su estado `closed` sigue siendo verificable (False)."""

    def __init__(self, path):
        self._f = sf.SoundFile(str(path))
        self.name = str(path)

    @property
    def closed(self):
        return self._f.closed

    def close(self):
        raise OSError(5, ERR_LECTOR)

    def cerrar_de_verdad(self):
        self._f.close()


def inventario(d):
    res = {}
    for raiz, _dirs, archivos in os.walk(d):
        for a in archivos:
            p = os.path.join(raiz, a)
            if os.path.isfile(p) and not os.path.islink(p):
                res[os.path.relpath(p, d)] = sha_file(Path(p))
    return res


def ident(p):
    try:
        st = os.lstat(p)
        return [st.st_dev, st.st_ino]
    except OSError:
        return None


def caso(L, etiqueta, cid):
    cond, completo_esp, tras_esp = CASOS[cid]
    work = TRABAJO / etiqueta / cid
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, mode=0o700)
    os.chmod(work, 0o700)
    L.reiniciar_registro_6g1()
    final = work / 'run_cr_r1'
    prov, _ident = L.crear_y_acreditar_dir_6g1(str(work), final.name + '_partial')
    prov = Path(prov)
    # salida parcial propia (WAV cerrado, registrado como en curso)
    wav = prov / 'mix SDV.wav'
    with sf.SoundFile(str(wav), 'w', samplerate=44100, channels=2,
                      subtype='PCM_24') as w:
        w.write(np.zeros((64, 2), dtype='float64'))
    L.registrar_propio_6g1(str(wav), estable=False)
    (prov / 'AJENO.txt').write_bytes(AJENO)
    dest = Path(str(final) + '_aborted')
    dest.mkdir(mode=0o700)
    (dest / 'MARCA_DESTINO.txt').write_bytes(MARCA)
    id_dest = ident(dest)
    # log de la corrida
    fh = open(prov / 'engine_log.txt', 'a', encoding='utf-8')

    def log(msg):
        fh.write(msg + '\n')
        fh.flush()

    log('[prueba CR-R1] corrida sintética %s' % cid)

    def cerrar_ok():
        fh.close()

    def cerrar_falla_cerrado():
        fh.close()
        raise OSError(28, ERR_LOG + ' (tras cerrar el archivo)')

    def cerrar_falla_abierto():
        raise OSError(28, ERR_LOG + ' (descriptor abierto)')

    cerrar = {'P0': cerrar_ok, 'P1': cerrar_ok, 'P2': cerrar_falla_cerrado,
              'P3': cerrar_falla_abierto}[cid]
    lector = (LectorQueFalla(FIX / 'mix.wav') if cid == 'P1'
              else sf.SoundFile(str(FIX / 'mix.wav')))
    id_prov = ident(prov)
    antes = inventario(prov)
    try:
        inf = L.preparar_aborto_6g1(str(prov), log, cerrar, runners=[], memmaps={},
                                    lectores=(lector,))
        res = L.abortar_corrida_6g1(str(prov), str(dest), MOTIVO, 'prueba CR-R1 %s' % cid,
                                    trasladar=True, cierre=inf)
    finally:
        if cid == 'P1':
            lector.cerrar_de_verdad()
        if not fh.closed:
            fh.close()

    ch = {}

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), str(detalle)[:600])

    entradas = sorted(os.listdir(work))
    ubic = Path(res.get('ruta_final') or prov)
    c('completo_esperado', inf.get('completo') is completo_esp,
      'completo=%s errores=%s' % (inf.get('completo'), inf.get('errores')))
    c('abort_registrado', res.get('abort_registrado') is True, res.get('abort_registrado'))
    if tras_esp:
        c('trasladado_sin_reemplazo', res.get('trasladado') is True
          and ubic == Path(str(final) + '_aborted_r001') and not prov.exists()
          and ident(ubic) == id_prov, (res.get('trasladado'), ubic.name))
    else:
        c('sin_traslado', res.get('trasladado') is False and ubic == prov,
          (res.get('trasladado'), res.get('motivo_conservacion')))
        c('provisional_en_su_ubicacion', prov.is_dir() and ident(prov) == id_prov, prov.name)
        c('ningun_aborted_r_creado', not [x for x in entradas if '_aborted_r' in x], entradas)
        c('traslado_bloqueado_por_cierre_incompleto',
          'cierre de recursos incompleto' in str(res.get('traslado_bloqueado'))
          and 'cierre de recursos incompleto' in str(res.get('motivo_conservacion')),
          res.get('motivo_conservacion'))
    c('destino_preexistente_intacto', ident(dest) == id_dest
      and sorted(os.listdir(dest)) == ['MARCA_DESTINO.txt']
      and (dest / 'MARCA_DESTINO.txt').read_bytes() == MARCA)
    c('sin_publicacion_exitosa', final.name not in entradas, entradas)
    ab = {}
    try:
        ab = json.loads((ubic / 'ABORT_6G1.json').read_text(encoding='utf-8'))
    except Exception as exc:
        ab = {'_error': repr(exc)}
    c('ABORT_6G1_schema_3', ab.get('schema') == 'abort-6g1/3', ab.get('schema'))
    c('motivo', ab.get('motivo') == MOTIVO, ab.get('motivo'))
    c('resultados_validos_vacio', ab.get('resultados_validos') == [])
    c('wav_parcial_invalidado_y_conservado',
      'mix SDV.wav' in (ab.get('salidas_invalidadas') or []) and (ubic / 'mix SDV.wav').is_file())
    c('ajeno_conservado', (ubic / 'AJENO.txt').read_bytes() == AJENO
      and 'AJENO.txt' in (ab.get('conservados') or []))
    despues = inventario(ubic)
    c('ningun_archivo_eliminado', set(antes) <= set(despues),
      'faltan %s' % sorted(set(antes) - set(despues)))
    c('archivos_previos_sin_modificar_salvo_log',
      all(despues.get(k) == v for k, v in antes.items() if k != 'engine_log.txt'))
    lg = (ubic / 'engine_log.txt').read_text(encoding='utf-8', errors='replace')
    if cid == 'P0':
        c('log_documenta_cierre_completo', 'completo=True' in lg, lg[-300:])
    elif cid == 'P1':
        c('error_del_lector_documentado_en_log', 'completo=False' in lg
          and 'ERROR de cierre' in lg and ERR_LECTOR in lg, lg[-500:])
    else:
        c('error_del_log_documentado_en_informe_y_resultado',
          any(ERR_LOG in x for x in inf.get('errores') or [])
          and ERR_LOG in str(res.get('motivo_conservacion')),
          inf.get('errores'))
        c('log_cerrado_marcado_false', inf.get('log_cerrado') is False, inf.get('log_cerrado'))
    resumen = dict(completo=inf.get('completo'), errores=inf.get('errores'),
                   log_cerrado=inf.get('log_cerrado'),
                   escritura_abierta_al_registrar=inf.get('escritura_abierta_al_registrar'),
                   abort_registrado=res.get('abort_registrado'),
                   trasladado=res.get('trasladado'), ruta_final=res.get('ruta_final'),
                   traslado_bloqueado=res.get('traslado_bloqueado'),
                   motivo_conservacion=res.get('motivo_conservacion'),
                   orden_cierre=inf.get('orden'))
    return ch, resumen


def serie(L, etiqueta):
    filas, det = [], {}
    for cid in CASOS:
        try:
            ch, resumen = caso(L, etiqueta, cid)
        except Exception as exc:
            ch, resumen = {'ejecucion': (False, repr(exc))}, {}
        ok = all(v[0] for v in ch.values())
        fallos = [k for k, v in ch.items() if not v[0]]
        det[cid] = dict(condicion=CASOS[cid][0], completo_esperado=CASOS[cid][1],
                        traslado_esperado=CASOS[cid][2], veredicto='PASS' if ok else 'FAIL',
                        fallos=fallos, resultado=resumen,
                        comprobaciones={k: dict(ok=v[0], detalle=v[1]) for k, v in ch.items()})
        filas.append(dict(prueba=cid, condicion=CASOS[cid][0],
                          completo_esperado=CASOS[cid][1], traslado_esperado=CASOS[cid][2],
                          completo=resumen.get('completo'), trasladado=resumen.get('trasladado'),
                          comprobaciones='%d/%d' % (sum(v[0] for v in ch.values()), len(ch)),
                          fallos=';'.join(fallos), veredicto='PASS' if ok else 'FAIL'))
        print('%-3s completo=%-5s trasladado=%-5s %s %s'
              % (cid, resumen.get('completo'), resumen.get('trasladado'),
                 'PASS' if ok else 'FAIL', ','.join(fallos)), flush=True)
    return filas, det


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=None)
    ap.add_argument('--etiqueta-base', default='base')
    a = ap.parse_args()
    res = dict(schema='pruebas-protocolo-cierre-cr-r1-6g1/1', entorno=entorno(),
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               casos={k: dict(condicion=v[0], completo_esperado=v[1], traslado_esperado=v[2])
                      for k, v in CASOS.items()})
    if a.base:
        bdir = Path(a.base).resolve()
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = serie(cargar_modulo(bdir, 'lectura_segura_base'), a.etiqueta_base)
        res['diagnostico_base'] = dict(
            etiqueta=a.etiqueta_base, modulo_sha256=sha_file(bdir / 'lectura_segura_6g1.py'),
            filas=fb, detalle=db,
            resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb), total=len(fb)))
    print('== módulo corregido (%s)' % MOT)
    filas, det = serie(cargar_modulo(MOT, 'lectura_segura_corregido'), 'corregido')
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas)))
    EV.mkdir(parents=True, exist_ok=True)
    (EV / 'pruebas_protocolo_cierre_cr_r1_6g1.json').write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    bidx = {f['prueba']: f for f in res.get('diagnostico_base', {}).get('filas', [])}
    with open(EV / 'matriz_protocolo_cierre_cr_r1_6g1.csv', 'w', newline='',
              encoding='utf-8') as fh:
        cols = ['prueba', 'condicion', 'completo_esperado', 'traslado_esperado', 'completo',
                'trasladado', 'comprobaciones', 'fallos', 'veredicto', 'completo_base',
                'trasladado_base', 'veredicto_base', 'fallos_base']
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for f in filas:
            b = bidx.get(f['prueba'], {})
            wr.writerow(dict(f, completo_base=b.get('completo', ''),
                             trasladado_base=b.get('trasladado', ''),
                             veredicto_base=b.get('veredicto', ''),
                             fallos_base=b.get('fallos', '')))
    print('RESUMEN corregido: %d/%d PASS' % (res['resumen']['pass_'], res['resumen']['total']))
    if 'diagnostico_base' in res:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base,
                                                res['diagnostico_base']['resumen']['pass_'],
                                                res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
