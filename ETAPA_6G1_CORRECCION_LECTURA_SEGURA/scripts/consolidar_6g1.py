"""Consolida la evidencia de 6G.1: matriz global, resumen, hashes y manifiesto."""
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g1 import EV, HERE, MOTORES, dump, entorno, sha_file

COLUMNAS = ('prueba', 'motor', 'contenedor', 'escenario', 'veredicto',
            'detalle', 'salida', 'pcm', 'ruta_sha256')
ORDEN = {'1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
         '9': 9, '10': 10}


def leer_csv(nombre):
    ruta = EV / nombre
    with ruta.open(encoding='utf-8') as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def filas_no_regresion():
    salida = []
    for f in leer_csv('no_regresion_dsp_6g1.csv'):
        salida.append(dict(
            prueba='10', motor=f['motor'], contenedor='WAV/FLAC',
            escenario='no_regresion_dsp',
            veredicto=f['veredicto'],
            detalle=(f"defs_cambiadas={f['defs_cambiadas'] or '-'} "
                     f"defs_eliminadas={f['defs_quitadas'] or '-'} "
                     f"constantes={f['constantes_cambiadas'] or '-'} "
                     f"huella_dsp={f['huella_dsp_ok']} "
                     f"pcm_wav={f['pcm_wav']} pcm_flac={f['pcm_flac']}"),
            salida=f"pcm_wav={f['pcm_wav']};pcm_flac={f['pcm_flac']}",
            pcm='hash por rol idéntico' if f['pcm_wav'] == 'IDENTICO' else '',
            ruta_sha256=''))
    return salida


def main():
    cont = json.loads((EV / 'contenedores_6g1.json').read_text(encoding='utf-8'))
    sust = json.loads((EV / 'sustituciones_6g1.json').read_text(encoding='utf-8'))
    noreg = json.loads((EV / 'no_regresion_dsp_6g1.json').read_text(encoding='utf-8'))

    filas = (leer_csv('matriz_contenedores_6g1.csv')
             + leer_csv('matriz_sustituciones_6g1.csv')
             + filas_no_regresion())
    filas.sort(key=lambda f: (ORDEN.get(f['prueba'], 99), f['motor'], f['escenario']))
    with (EV / 'matriz_global_6g1.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(COLUMNAS), lineterminator='\n',
                           extrasaction='ignore')
        w.writeheader()
        w.writerows(filas)

    resumen, no_ejecutadas = {}, []
    for f in filas:
        resumen.setdefault(f['prueba'], {}).setdefault(f['veredicto'], 0)
        resumen[f['prueba']][f['veredicto']] += 1
        if f['veredicto'] == 'NOT_EXECUTED':
            no_ejecutadas.append(dict(prueba=f['prueba'], motor=f['motor'],
                                      escenario=f['escenario'], detalle=f['detalle']))
    veredictos = {}
    for f in filas:
        veredictos[f['veredicto']] = veredictos.get(f['veredicto'], 0) + 1

    hashes_origen = json.loads((HERE / 'fixtures' / 'fixtures_manifest.json')
                               .read_text(encoding='utf-8'))
    fuentes = {}
    for etiqueta, carpeta in (('6G', HERE.parent / 'ETAPA_6G_SOPORTE_FLAC_MIX' / 'motores'),
                              ('6G1', HERE / 'motores')):
        fuentes[etiqueta] = {n: sha_file(carpeta / n) for n in sorted(
            p.name for p in carpeta.glob('*.py'))}

    dump(EV / 'resumen_6g1.json', dict(
        schema='resumen-6g1/1', entorno=entorno(),
        pruebas={k: resumen[k] for k in sorted(resumen, key=lambda x: ORDEN.get(x, 99))},
        veredictos=veredictos, total_filas=len(filas),
        no_ejecutadas=no_ejecutadas,
        bloqueos_conocidos=cont.get('bloqueos_conocidos', {}),
        equivalencias=cont.get('equivalencias', {}),
        sustituciones={k: dict(veredicto=v.get('veredicto'), detalle=v.get('detalle'))
                       for k, v in sust.get('casos', {}).items() if 'veredicto' in v},
        no_regresion={m: dict(veredicto=v['veredicto'], dsp_ok=v['dsp_ok'],
                              pcm={k: vv['identicos'] for k, vv in v['pcm'].items()})
                      for m, v in noreg['motores'].items()},
        fuentes=fuentes, fixtures=hashes_origen.get('archivos', {})))

    archivos = sorted(p for p in HERE.rglob('*')
                      if p.is_file() and '__pycache__' not in p.parts
                      and p.name not in ('SHA256SUMS.txt', 'MANIFEST_6G1.json'))
    dump(HERE / 'MANIFEST_6G1.json', dict(
        schema='manifest-6g1/1',
        etapa='6G.1 corrección de lectura segura y validación de evidencias',
        base='ee19fe208449249a20e194b09c9452b782c7de70',
        archivos={p.relative_to(HERE).as_posix(): dict(
            bytes=p.stat().st_size, sha256=sha_file(p)) for p in archivos},
        total=len(archivos), resumen=veredictos, pruebas=resumen,
        no_ejecutadas=no_ejecutadas,
        nota='MANIFEST_6G1.json no se incluye a sí mismo; su hash está en SHA256SUMS.txt'))
    hasheados = archivos + [HERE / 'MANIFEST_6G1.json']
    lineas = [f'{sha_file(p)}  {p.relative_to(HERE).as_posix()}\n'
              for p in sorted(hasheados)]
    (HERE / 'SHA256SUMS.txt').write_text(''.join(lineas), encoding='utf-8')
    print(json.dumps(dict(filas=len(filas), veredictos=veredictos,
                          archivos_hasheados=len(hasheados),
                          pruebas={k: resumen[k] for k in sorted(resumen, key=lambda x: ORDEN.get(x, 99))}),
                     indent=2, ensure_ascii=False))
    print('no ejecutadas:', json.dumps(no_ejecutadas, ensure_ascii=False))
    print('fuentes 6G/6G1:')
    for n in MOTORES.values():
        igual = fuentes['6G'][n] == fuentes['6G1'][n]
        print(f'  {n}: {"igual" if igual else "cambiada"} {fuentes["6G1"][n][:16]}')


if __name__ == '__main__':
    main()
