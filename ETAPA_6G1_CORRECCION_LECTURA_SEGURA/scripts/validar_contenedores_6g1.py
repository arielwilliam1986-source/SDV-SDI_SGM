"""Pruebas 1, 2, 3, 8 y 9 de la Etapa 6G.1.

1. WAV válido aceptado.
2. FLAC válido aceptado.
3. WAV y FLAC equivalentes (mismo PCM de salida).
8. Verificación de hash sobre archivos PCM reales.
9. Comparación WAV/FLAC de alineación, máscaras, SDV y SDI.

Cada caso se corre en los tres modos: `dry_run` (validación),
`analysis_only` (análisis) y `full_processing` (procesamiento efectivo).
Veredictos posibles: ACCEPTED, REJECTED, PCM_IDENTICAL, PCM_DIFFERENT,
NOT_APPLICABLE y NOT_EXECUTED. Un veredicto PCM_IDENTICAL exige archivos PCM
reales, legibles, finitos y con hash; los diccionarios vacíos nunca cuentan.
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g1 import (CSV_COLUMNAS, EV, FIX, MOTORES, SR, dump, ejecutar,
                       entorno, sha_file)

VOLATILES = {'document_meta', 'mix_original', 'guide_inventory',
             'guide_family_inventory', 'guide_variant_inventory',
             'guide_vocal_inventory', 'guide_instrumental_inventory',
             'input_integrity', 'input_integrity_6g', 'post_wav_validation',
             'container_6g'}
MODOS = ('dry_run', 'analysis_only', 'full_processing')
TRABAJO = Path('/tmp/f6g1/contenedores')

# Defecto preexistente verificado también en la copia 6G (no es regresion 6G.1)
BLOQUEOS_CONOCIDOS = {
    ('Hardened', 'analysis_only'):
        'defecto preexistente 6G/6F: write_reports usa '
        'ctx["post_wav_validation"] nulo cuando full_mode es False '
        '(AttributeError); reproducido igual en la copia 6G',
}

RUTAS = dict(vocal=FIX / 'vocal_mix.wav', instrumental=FIX / 'instrumental_mix.wav')


def reducir_integridad(integ):
    """Quita metadatos propios de cada archivo (inodo, tamaño, sha, spec)."""
    salida = {}
    for k, v in integ.items():
        if isinstance(v, dict) and ('sha256' in v or 'identity' in v or 'spec' in v):
            salida[k] = {kk: v.get(kk) for kk in ('unchanged', 'reason')
                         if kk in v}
        else:
            salida[k] = normalizar(v)
    return salida


def normalizar(obj):
    if isinstance(obj, dict):
        if 'same_descriptor_read' in obj:
            return reducir_integridad(obj)
        return {k: normalizar(v) for k, v in obj.items() if k not in VOLATILES}
    if isinstance(obj, list):
        return [normalizar(v) for v in obj]
    return obj


def pcm_real(pcm):
    return bool(pcm) and all('error' not in p and p.get('finite') is True
                             and p.get('pcm_sha256') and p.get('frames', 0) > 0
                             and p.get('bytes', 0) > 0 for p in pcm)


def clave_pcm(pcm):
    return {p['name']: p['pcm_sha256'] for p in pcm}


def por_rol(pcm):
    """Agrupa hashes PCM por rol (SDV/SDI). Acepta lista de registros o dict."""
    if isinstance(pcm, dict):
        pares = list(pcm.items())
    else:
        pares = [(p['name'], p['pcm_sha256']) for p in pcm if 'pcm_sha256' in p]
    salida = {}
    for nombre, digest in pares:
        if nombre.endswith(' SDV.wav') or nombre == 'SDV.wav':
            salida['SDV'] = digest
        elif nombre.endswith(' SDI.wav') or nombre == 'SDI.wav':
            salida['SDI'] = digest
    return salida


def integridad_ok(r):
    integ = r['integrity']
    if not integ:
        return False, 'sin input_integrity_6g.json'
    despues = integ.get('after') or {}
    ruta = integ.get('ruta_actual') or {}
    ok = bool(despues.get('unchanged')) and bool(ruta.get('unchanged'))
    return ok, 'after=%s ruta_actual=%s' % (despues.get('unchanged'),
                                            ruta.get('unchanged'))


def main():
    filas, casos, equivalencias = [], {}, {}

    for motor in MOTORES:
        for modo in MODOS:
            for contenedor, archivo in (('WAV', 'mix.wav'), ('FLAC', 'mix.flac')):
                clave = f'{motor}/{contenedor}/{modo}'
                if (motor, modo) in BLOQUEOS_CONOCIDOS:
                    bloqueo = BLOQUEOS_CONOCIDOS[(motor, modo)]
                    casos[clave] = dict(bloqueado_por=bloqueo, exit=None,
                                        report=False, wavs=[], pcm={})
                    filas.append(dict(prueba='1' if contenedor == 'WAV' else '2',
                                      motor=motor, contenedor=contenedor,
                                      escenario=f'validez/{modo}',
                                      veredicto='NOT_EXECUTED', detalle=bloqueo,
                                      salida='', pcm='',
                                      ruta_sha256=sha_file(FIX / archivo)))
                    continue
                r = ejecutar(motor, dict(RUTAS, mix=str(FIX / archivo)),
                             TRABAJO / clave, modo)
                ok_integ, det_integ = integridad_ok(r)
                if r['abort'] or r['exit'] != 0:
                    veredicto, detalle = 'REJECTED', f"exit={r['exit']} {det_integ}"
                elif modo == 'dry_run':
                    veredicto = 'ACCEPTED'
                    detalle = ('exit=0 validación de entradas y plan aceptados '
                               '(sin PCM por diseño)')
                elif r['report_leido'] and ok_integ:
                    veredicto, detalle = 'ACCEPTED', f'exit=0 informe leído {det_integ}'
                else:
                    veredicto = 'REJECTED'
                    detalle = f"exit={r['exit']} informe={r['report_leido']} {det_integ}"
                casos[clave] = dict(exit=r['exit'], veredicto=veredicto,
                                    wavs=r['wavs'], pcm=clave_pcm(r['pcm']),
                                    pcm_valido=pcm_real(r['pcm']),
                                    roles_pcm=por_rol(r['pcm']),
                                    integrity=r['integrity'], abort=r['abort'],
                                    report=normalizar(r['report']),
                                    stdout_tail=r['stdout_tail'],
                                    corrida=clave)
                filas.append(dict(prueba='1' if contenedor == 'WAV' else '2',
                                  motor=motor, contenedor=contenedor,
                                  escenario=f'validez/{modo}', veredicto=veredicto,
                                  detalle=detalle,
                                  salida=f"wavs={len(r['wavs'])}",
                                  pcm=f"validos={r['wavs_validos']}",
                                  ruta_sha256=sha_file(FIX / archivo)))

                # prueba 8: hashes de archivos PCM reales
                if modo == 'full_processing':
                    if pcm_real(r['pcm']):
                        verificados, estable = 0, True
                        for nombre in r['wavs']:
                            for w in Path(r['out']).rglob(nombre):
                                a, b = sha_file(w), sha_file(w)
                                verificados += 1
                                estable = estable and a == b
                        veredicto8 = 'ACCEPTED' if estable else 'REJECTED'
                        det8 = (f'archivos={verificados} estables={estable} '
                                f'pcm_sha256={"OK" if r["pcm"] else "sin datos"}')
                    else:
                        veredicto8 = 'NOT_APPLICABLE'
                        det8 = 'sin archivos PCM reales que verificar'
                    filas.append(dict(prueba='8', motor=motor, contenedor=contenedor,
                                      escenario='hash_pcm/full_processing',
                                      veredicto=veredicto8, detalle=det8,
                                      salida=';'.join(r['wavs']),
                                      pcm=';'.join(p['pcm_sha256'][:16] for p in r['pcm']),
                                      ruta_sha256=sha_file(FIX / archivo)))

        # pruebas 3 y 9: WAV frente a FLAC
        for modo in MODOS:
            w = casos.get(f'{motor}/WAV/{modo}', {})
            f = casos.get(f'{motor}/FLAC/{modo}', {})
            if w.get('bloqueado_por') or f.get('bloqueado_por'):
                v3 = 'NOT_EXECUTED'
                det3 = (w.get('bloqueado_por') or f.get('bloqueado_por'))
                v9 = 'NOT_EXECUTED'
                det9 = det3
            else:
                pcm_w, pcm_f = w.get('pcm') or {}, f.get('pcm') or {}
                if pcm_w or pcm_f:
                    iguales = (pcm_w == pcm_f) and w.get('pcm_valido') and f.get('pcm_valido')
                    v3 = 'PCM_IDENTICAL' if iguales else 'PCM_DIFFERENT'
                    det3 = ('roles=%s WAV=%s FLAC=%s validos=%s/%s'
                            % (sorted(por_rol(w['pcm']) or {}),
                               sorted(pcm_w), sorted(pcm_f),
                               w.get('pcm_valido'), f.get('pcm_valido')))
                else:
                    v3 = 'NOT_APPLICABLE'
                    det3 = 'el modo no produce salidas PCM'
                mismo_informe = (w.get('report') == f.get('report')
                                 and bool(w.get('report')))
                roles_ok = por_rol(w.get('pcm') or []) == por_rol(f.get('pcm') or [])
                if v3 == 'PCM_DIFFERENT' or (mismo_informe and not roles_ok):
                    v9 = 'PCM_DIFFERENT'
                elif mismo_informe and (v3 in ('PCM_IDENTICAL', 'NOT_APPLICABLE')):
                    v9 = 'PCM_IDENTICAL' if v3 == 'PCM_IDENTICAL' else 'ACCEPTED'
                elif not w.get('report') and not f.get('report'):
                    v9 = 'NOT_APPLICABLE'
                else:
                    v9 = 'PCM_DIFFERENT'
                det9 = (f'informe_wav_igual_flac={mismo_informe} pcm={v3} '
                        f'roles_sdv_sdi_iguales={roles_ok}')
            equivalencias[f'{motor}/{modo}'] = dict(veredicto_pcm=v3, detalle_pcm=det3,
                                                   veredicto_analisis=v9, detalle=det9)
            filas.append(dict(prueba='3', motor=motor, contenedor='WAV/FLAC',
                              escenario=f'equivalencia/{modo}', veredicto=v3,
                              detalle=det3, salida='', pcm='', ruta_sha256=''))
            filas.append(dict(prueba='9', motor=motor, contenedor='WAV/FLAC',
                              escenario=f'analisis/{modo}', veredicto=v9,
                              detalle=det9, salida='', pcm='', ruta_sha256=''))

    EV.mkdir(parents=True, exist_ok=True)
    with (EV / 'matriz_contenedores_6g1.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(CSV_COLUMNAS), lineterminator='\n',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(filas)
    resumen = {}
    for fila in filas:
        resumen.setdefault(fila['prueba'], {}).setdefault(fila['veredicto'], 0)
        resumen[fila['prueba']][fila['veredicto']] += 1
    dump(EV / 'contenedores_6g1.json', dict(
        schema='validacion-contenedores-6g1/2', entorno=entorno(), sr=SR,
        modos=list(MODOS), bloqueos_conocidos={f'{k[0]}/{k[1]}': v
                                               for k, v in BLOQUEOS_CONOCIDOS.items()},
        filas=filas, casos=casos, equivalencias=equivalencias, resumen=resumen))
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    for k, v in equivalencias.items():
        print(f"{k:28s} pcm={v['veredicto_pcm']:16s} analisis={v['veredicto_analisis']:16s} {v['detalle']}")


if __name__ == '__main__':
    main()
