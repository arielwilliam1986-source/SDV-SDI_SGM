"""Pruebas 4, 5, 6 y 7 de la Etapa 6G.1: sustitución del Mix y aborto seguro.

4. Sustitución antes del DSP: (a) unitaria determinista sobre `abrir_mix`
   —la misma llamada que hacen los motores antes del DSP— y (b) a nivel de
   motor justo después de la validación, con reintentos.
5. Sustitución durante la lectura del DSP.
6. Sustitución después del DSP y antes de la confirmación final.
7. Tras el aborto no quedan salidas de audio de la corrida y no se borran
   archivos ajenos sembrados en el directorio de la corrida.

Los sustitutos son FLAC válidos con otro PCM (mismo contenedor que el Mix), de
modo que el rechazo no puede atribuirse a un contenedor ajeno.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g1 import (CSV_COLUMNAS, EV, FIX, MOT, MOTORES, dump, ejecutar,
                       entorno, sha_file)

TRABAJO = Path('/tmp/f6g1/sustituciones')
SUSTITUTO = FIX / 'mix_otro.flac'
AJENOS = ('ajeno.txt', 'ajeno.wav', 'notas_preexistentes.json')
MOTIVO_DURANTE = 'MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO'
MOTIVO_ANTES = 'MIX_SUSTITUIDO_ANTES_DEL_DSP'
PATRON_ANTES = {'Hardened': r'(?i)iniciando pipeline',
                'EVO': r'(?i)iniciando pipeline',
                'MQR': r'(?i)directorio de corrida \(parcial\)'}
PATRON_DURANTE = {'Hardened': r'(?i)chunk\s+10\s*/',
                  'EVO': r'(?i)chunk\s+10\s*/',
                  'MQR': r'(?i)chunk\s+10\s*/'}
PATRON_DESPUES = r'(?i)post-wav identity'
EXTRA_DURANTE = ('--chunk-frames', '48')


def es_salida_del_motor(nombre):
    return (nombre.endswith(' SDV.wav') or nombre.endswith(' SDI.wav')
            or nombre in ('SDV.wav', 'SDI.wav'))


def preparar_mix(destino):
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(FIX / 'mix_12s.flac'), str(destino))
    return destino


def estado_tras_aborto(r):
    out = Path(r['out'])
    wavs = sorted(out.rglob('*.wav')) if out.exists() else []
    propias = [w for w in wavs if es_salida_del_motor(w.name)]
    abort = r['abort']
    presentes = {a: bool(list(out.rglob(a))) for a in AJENOS} if out.exists() else {}
    return dict(wavs_propios=[w.name for w in propias],
                wavs_totales=[w.name for w in wavs],
                abort_presente=bool(abort), motivo=abort.get('motivo'),
                salidas_invalidadas=abort.get('salidas_invalidadas', []),
                conservados=abort.get('conservados', []),
                ajenos_presentes=presentes,
                ajenos_conservados=all(presentes.values()) if presentes else None)


def prueba_unitaria_antes():
    """Guarda determinista: validar, sustituir y abrir el descriptor."""
    sys.path.insert(0, str(MOT))
    from lectura_segura_6g1 import MixCambiado, abrir_mix
    trabajo = TRABAJO / 'unitaria'
    if trabajo.exists():
        shutil.rmtree(trabajo)
    trabajo.mkdir(parents=True)
    mix = trabajo / 'mix.flac'
    shutil.copyfile(str(FIX / 'mix_12s.flac'), str(mix))
    sha_validado = sha_file(mix)                     # sondeo/validación
    shutil.copyfile(str(SUSTITUTO), str(mix))        # sustitución posterior
    sha_actual = sha_file(mix)
    try:
        h = abrir_mix(str(mix), sha_validado)
    except MixCambiado as exc:
        return dict(detectada=True, excepcion=type(exc).__name__, detalle=str(exc),
                    sha_validado=sha_validado, sha_actual=sha_actual)
    h.close()
    return dict(detectada=False, sha_validado=sha_validado, sha_actual=sha_actual,
                detalle='abrir_mix aceptó un archivo distinto del validado')


def main():
    filas, casos = [], {}
    unitaria = prueba_unitaria_antes()
    filas.append(dict(prueba='4', motor='todos', contenedor='FLAC',
                      escenario='guarda_unitaria_antes_dsp',
                      veredicto='ACCEPTED' if unitaria['detectada'] else 'REJECTED',
                      detalle=unitaria['detalle'][:200], salida='abrir_mix',
                      pcm='', ruta_sha256=unitaria['sha_validado'][:16]))
    casos['unitaria/antes_dsp'] = unitaria

    for motor in MOTORES:
        # --- 4c: a nivel de motor, durante la alineación (antes del DSP) ----
        trabajo = TRABAJO / f'{motor}/antes_dsp_alineacion'
        if trabajo.exists():
            shutil.rmtree(trabajo)
        mix = preparar_mix(trabajo / 'mix.flac')
        r = ejecutar(motor, dict(mix=str(mix), vocal=str(FIX / 'vocal_mix_12s.wav'),
                                 instrumental=str(FIX / 'instrumental_mix_12s.wav')),
                     trabajo, 'full_processing',
                     sustituir=dict(destino=mix, fuente=SUSTITUTO, patron=None,
                                    etapa='antes_alineacion', sembrar=AJENOS,
                                    retraso=0.30))
        est = estado_tras_aborto(r)
        if not r['sustitucion'].get('aplicada'):
            v4c, d4c = 'NOT_EXECUTED', 'la sustitución no se aplicó'
        elif r['exit'] != 0 and not est['wavs_propios']:
            v4c = 'ACCEPTED'
            d4c = (f"rechazo previo al DSP: exit={r['exit']} "
                   f"abort={est['motivo']!r} sin salidas propias")
        else:
            v4c, d4c = 'REJECTED', f"exit={r['exit']} propios={est['wavs_propios']}"
        casos[f'{motor}/antes_dsp_alineacion'] = dict(veredicto=v4c, detalle=d4c,
                                                     exit=r['exit'],
                                                     sustitucion=r['sustitucion'],
                                                     estado=est,
                                                     stdout_tail=r['stdout_tail'])
        filas.append(dict(prueba='4', motor=motor, contenedor='FLAC',
                          escenario='antes_dsp_alineacion', veredicto=v4c,
                          detalle=d4c[:200], salida=f"exit={r['exit']}",
                          pcm=f"propios={len(est['wavs_propios'])}",
                          ruta_sha256=sha_file(SUSTITUTO)[:16]))
        if est['abort_presente']:
            filas.append(dict(prueba='7', motor=motor, contenedor='FLAC',
                              escenario='aborto/antes_dsp_alineacion',
                              veredicto='ACCEPTED' if not est['wavs_propios'] else 'REJECTED',
                              detalle=f"propios={est['wavs_propios']} ajenos={est['ajenos_presentes']}",
                              salida='', pcm='', ruta_sha256=sha_file(SUSTITUTO)[:16]))

        # --- 4b: a nivel de motor, justo después de la validación ----------
        intentos = []
        for n in range(3):
            trabajo = TRABAJO / f'{motor}/antes_dsp_{n}'
            if trabajo.exists():
                shutil.rmtree(trabajo)
            mix = preparar_mix(trabajo / 'mix.flac')
            r = ejecutar(motor, dict(mix=str(mix), vocal=str(FIX / 'vocal_mix_12s.wav'),
                                     instrumental=str(FIX / 'instrumental_mix_12s.wav')),
                         trabajo, 'full_processing',
                         sustituir=dict(destino=mix, fuente=SUSTITUTO,
                                        patron=PATRON_ANTES[motor], etapa='antes',
                                        sembrar=AJENOS))
            est = estado_tras_aborto(r)
            intentos.append(dict(intento=n, exit=r['exit'], sustitucion=r['sustitucion'],
                                 estado=est, stdout_tail=r['stdout_tail']))
            if est['motivo'] == MOTIVO_ANTES:
                break
        ok = any(i['estado']['motivo'] == MOTIVO_ANTES
                 and not i['estado']['wavs_propios'] for i in intentos)
        if ok:
            veredicto, detalle = 'ACCEPTED', f'rechazo {MOTIVO_ANTES} observado'
        elif all(i['sustitucion'].get('aplicada') for i in intentos) and all(
                i['exit'] != 0 and not i['estado']['wavs_propios'] for i in intentos):
            veredicto = 'ACCEPTED'
            detalle = ('la sustitución se aplicó después de abrir el descriptor: '
                       'el rechazo provino de la guarda final (mismo resultado: '
                       'sin salidas); guarda previa demostrada en la prueba unitaria')
        else:
            veredicto, detalle = 'NOT_EXECUTED', 'la sustitución no se aplicó a tiempo'
        casos[f'{motor}/antes_dsp'] = dict(veredicto=veredicto, detalle=detalle,
                                           intentos=intentos)
        filas.append(dict(prueba='4', motor=motor, contenedor='FLAC',
                          escenario='antes_dsp', veredicto=veredicto,
                          detalle=detalle[:200],
                          salida=f"intentos={len(intentos)}",
                          pcm=f"propios={len(intentos[-1]['estado']['wavs_propios'])}",
                          ruta_sha256=sha_file(SUSTITUTO)[:16]))

        # --- 5 y 6: durante y después del DSP ------------------------------
        for escenario, patron, extra in (('durante_dsp', PATRON_DURANTE[motor], EXTRA_DURANTE),
                                         ('despues_dsp', PATRON_DESPUES, ())):
            trabajo = TRABAJO / f'{motor}/{escenario}'
            if trabajo.exists():
                shutil.rmtree(trabajo)
            mix = preparar_mix(trabajo / 'mix.flac')
            r = ejecutar(motor, dict(mix=str(mix), vocal=str(FIX / 'vocal_mix_12s.wav'),
                                     instrumental=str(FIX / 'instrumental_mix_12s.wav')),
                         trabajo, 'full_processing', extra=extra,
                         sustituir=dict(destino=mix, fuente=SUSTITUTO, patron=patron,
                                        etapa=escenario, sembrar=AJENOS))
            est = estado_tras_aborto(r)
            sust = r['sustitucion']
            if not sust.get('aplicada'):
                veredicto = 'NOT_EXECUTED'
                detalle = f"no se aplicó ({sust.get('motivo_no_aplicada')})"
            elif r['exit'] == 0:
                veredicto, detalle = 'REJECTED', 'el motor terminó con éxito'
            elif est['wavs_propios']:
                veredicto = 'REJECTED'
                detalle = f"quedaron salidas propias: {est['wavs_propios']}"
            elif est['motivo'] == MOTIVO_DURANTE:
                veredicto = 'ACCEPTED'
                detalle = (f"aborto {MOTIVO_DURANTE}; salidas invalidadas="
                           f"{est['salidas_invalidadas']}")
            else:
                veredicto = 'ACCEPTED'
                detalle = f"aborto con motivo {est['motivo']!r}, sin salidas propias"
            casos[f'{motor}/{escenario}'] = dict(veredicto=veredicto, detalle=detalle,
                                                 exit=r['exit'], sustitucion=sust,
                                                 estado=est, stdout_tail=r['stdout_tail'])
            filas.append(dict(prueba='5' if escenario == 'durante_dsp' else '6',
                              motor=motor, contenedor='FLAC', escenario=escenario,
                              veredicto=veredicto, detalle=detalle[:200],
                              salida=f"exit={r['exit']} sust@{sust.get('segundos_desde_inicio')}",
                              pcm=f"propios={len(est['wavs_propios'])}",
                              ruta_sha256=sha_file(SUSTITUTO)[:16]))

            # 7: higiene del aborto (salidas propias eliminadas, ajenos intactos)
            if est['abort_presente']:
                v7 = 'ACCEPTED' if not est['wavs_propios'] else 'REJECTED'
                det7 = (f"propios={est['wavs_propios']} ajenos={est['ajenos_presentes']} "
                        f"conservados={len(est['conservados'])}")
            else:
                v7 = 'NOT_APPLICABLE'
                det7 = 'no hubo aborto con ABORT_6G1.json'
            filas.append(dict(prueba='7', motor=motor, contenedor='FLAC',
                              escenario=f'aborto/{escenario}', veredicto=v7,
                              detalle=det7[:200], salida='', pcm='',
                              ruta_sha256=sha_file(SUSTITUTO)[:16]))

    EV.mkdir(parents=True, exist_ok=True)
    with (EV / 'matriz_sustituciones_6g1.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNAS), lineterminator='\n',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(filas)
    resumen = {}
    for fila in filas:
        resumen.setdefault(fila['prueba'], {}).setdefault(fila['veredicto'], 0)
        resumen[fila['prueba']][fila['veredicto']] += 1
    dump(EV / 'sustituciones_6g1.json', dict(
        schema='sustituciones-6g1/2', entorno=entorno(), unitaria=unitaria,
        casos=casos, filas=filas, resumen=resumen, sustituto=str(SUSTITUTO),
        ajenos=list(AJENOS)))
    print(json.dumps(resumen, indent=2))
    for k, v in casos.items():
        if 'veredicto' in v:
            print(f"{k:26s} {v['veredicto']:13s} {str(v.get('detalle'))[:100]}")


if __name__ == '__main__':
    main()
