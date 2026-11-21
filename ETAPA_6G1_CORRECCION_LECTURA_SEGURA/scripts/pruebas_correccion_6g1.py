"""Pruebas obligatorias de la rectificación 6G.1 (auditoría: correcciones A, B y C).

Batería por motor (Hardened, EVO, MQR) — cada veredicto exige estado de
archivos y publicación, no sólo el código de salida:

  T1 excepción de hmix.verificar()          -> aborto en provisional, sin publicación
  T2 excepción de comprobación de ruta      -> ídem
  T3 sustitución del Mix tras abrir el descriptor (durante el DSP) -> ídem
  T4 verificación fallida (sin excepción)   -> ídem
  T5 ausencia de directorio definitivo tras los abortos T1–T4
  T6 conservación de ajenos con colisión de nombres (SDV.wav, nombre exacto de
     salida del motor, candidates/, archivo suelto) + eliminación de salidas
     propias acreditadas
  T7 eliminación de salidas propias acreditadas (de T1) con motivos del registro
  T8 procesamiento normal con verificación satisfactoria (WAV y FLAC) y PCM
     idéntico a la campaña auditada (confirmación de DSP intacto)

Unidad (sin DSP) sobre lectura_segura_6g1 — los cinco casos de la corrección C:
  UC1 ajeno dentro de candidates/
  UC2 ajeno llamado SDV.wav
  UC3 ajeno con el nombre exacto de una salida del motor
  UC4 propio acreditado que debe eliminarse
  UC5 propio sustituido tras su creación (identidad distinta -> se conserva)
  UC6 propio en curso (inodo continuo) que debe eliminarse
  UC7 propio sellado modificado in situ (se conserva)

Resultados: evidence/pruebas_correccion_6g1.json + evidence/matriz_correccion_6g1.csv
Veredictos: PASS / FAIL / NOT_EXECUTED (con motivo). Nada se declara PASS sin
ejecución real.
"""
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comun_6g1 import (FIX, MOT, MOTORES, escribir_manifest, recolectar,
                       sha_file, dump)

sys.path.insert(0, str(MOT))

RAIZ = Path(__file__).resolve().parent.parent
EV = RAIZ / 'evidence'
INJ = Path(__file__).resolve().parent / 'inyeccion_6g1'
TRABAJO = Path('/tmp/f6g1corr')

MOTIVO = 'MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO'
PATRON_DSP = {'Hardened': r'(?i)chunk\s+10\s*/', 'EVO': r'(?i)chunk\s+10\s*/',
              'MQR': r'(?i)chunk\s+10\s*/'}
PATRON_SIEMBRA = r'(?i)post-wav identity'
EXTRA_DSP = ('--chunk-frames', '48')
SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
PREFIJO_FINAL = {'Hardened': 'motorA_run_', 'EVO': 'motorA_run_', 'MQR': 'mqr_run_'}
AJENOS_T6 = {'Hardened': ('SDV.wav', 'candidates/ajeno_cand.wav',
                          'otro_ajeno.txt'),
             'EVO': ('SDV.wav', 'candidates/ajeno_cand.wav',
                     'otro_ajeno.txt'),
             'MQR': ('mix SDV.wav', 'candidates/ajeno_cand.wav',
                     'otro_ajeno.txt')}
REEMPLAZO_T6 = {'Hardened': ('mix SDV.wav',), 'EVO': ('mix SDV.wav',),
                'MQR': ('SDV.wav',)}
ESPERADO_NEG = {'T1': ('after', 'ruta'), 'T2': ('after', 'ruta'),
                'T4': ('after',)}


def dirs_definitivos(out, motor):
    pref = PREFIJO_FINAL[motor]
    if not Path(out).exists():
        return []
    return [d.name for d in Path(out).iterdir()
            if d.is_dir() and d.name.startswith(pref)
            and not d.name.endswith('_partial')
            and not d.name.endswith('_aborted')]


def _vigia(out, proc, sembrar, patron_siembra, sustituir, patron_sustitucion,
           reemplazar=None):
    """Siembra ajenos, reemplaza salidas propias del motor (os.replace, inodo
    distinto) y/o sustituye el Mix cuando el log del motor alcanza el patrón.
    Misma política que la campaña 6G.1: os.replace atómico tras pre-copia;
    ajenos con padres creados si faltan."""
    evento = dict(sembrados=[], sustitucion_aplicada=False, reemplazados=[])
    destino = Path(sustituir['destino']) if sustituir else None
    if sustituir:
        shutil.copyfile(str(sustituir['fuente']), str(destino) + '.sustituto')
    repl_pre = {}
    for nombre, fuente in (reemplazar or {}).items():
        repl_pre[nombre] = str(fuente) + '.reemplazo'
        shutil.copyfile(str(fuente), repl_pre[nombre])
    vistos = ''
    t0 = time.perf_counter()
    while proc.poll() is None and time.perf_counter() - t0 < 600:
        logs = sorted(Path(out).glob('*/engine_log.txt')) if Path(out).exists() else []
        if logs:
            try:
                texto = logs[0].read_text(errors='replace')
            except OSError:
                texto = ''
            if len(texto) > len(vistos):
                nuevo = texto[len(vistos):]
                vistos = texto
                disparo = None
                if sembrar and patron_siembra and re.search(patron_siembra, nuevo) \
                        and not evento['sembrados']:
                    base = logs[0].parent
                    for nombre in sembrar:
                        objetivo = base / nombre
                        objetivo.parent.mkdir(parents=True, exist_ok=True)
                        objetivo.write_text('archivo ajeno a la corrida 6G.1 '
                                            '(rectificación)\n', encoding='utf-8')
                        evento['sembrados'].append(nombre)
                    for nombre, pre in repl_pre.items():
                        objetivo = base / nombre
                        if objetivo.exists() and Path(pre).exists():
                            os.replace(pre, objetivo)
                            evento['reemplazados'].append(nombre)
                    disparo = 'siembra' if sembrar else 'reemplazo'
                if sustituir and re.search(patron_sustitucion, nuevo) \
                        and not evento['sustitucion_aplicada']:
                    os.replace(str(destino) + '.sustituto', str(destino))
                    evento['sustitucion_aplicada'] = True
                    evento['sha_mix_tras_sustitucion'] = sha_file(destino)
                    disparo = (disparo + '+sustitucion') if disparo else 'sustitucion'
                if disparo:
                    evento['disparo'] = disparo
                    evento['segundos'] = round(time.perf_counter() - t0, 3)
                if evento['sembrados'] and (not sustituir or evento['sustitucion_aplicada']):
                    break
        time.sleep(0.002)
    sobra = Path(str(destino) + '.sustituto') if destino else None
    if sobra and sobra.exists():
        sobra.unlink()
    for pre in repl_pre.values():
        if Path(pre).exists():
            Path(pre).unlink()
    return evento


def correr(motor, mixdict, work, mode='full_processing', inject=None,
           sembrar=None, patron_siembra=None, sustituir=None,
           patron_sustitucion=None, extra=(), reemplazar=None):
    work = Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    man = work / 'manifest.json'
    escribir_manifest(man, mixdict)
    out = work / 'out'
    cmd = [sys.executable, '-B', str(MOT / MOTORES[motor]),
           '--manifest', str(man), '--out', str(out), '--mode', mode, *extra]
    env = dict(os.environ, PYTHONPATH=str(INJ))
    if inject:
        env['SDVSDI_6G1_INJECT'] = inject
        env['SDVSDI_6G1_MOTORES'] = str(MOT)
    else:
        env.pop('SDVSDI_6G1_INJECT', None)
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, env=env)
    evento = {}
    if sembrar or sustituir or reemplazar:
        evento = _vigia(out, proc, sembrar or [], patron_siembra, sustituir,
                        patron_sustitucion, reemplazar=reemplazar)
    salida = proc.communicate(timeout=900)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, stdout_tail=salida[-4000:],
                 evento=evento, out=str(out))
    return datos


def fila(prueba, motor, alcance, checks, motivo_ne=None):
    if motivo_ne is not None:
        return dict(prueba=prueba, motor=motor, alcance=alcance,
                    veredicto='NOT_EXECUTED', checks_ok=0, checks_total=0,
                    detalle=motivo_ne)
    ok = [c for c in checks if c[1]]
    detalle = '; '.join('%s=%s' % (c[0], 'OK' if c[1] else 'FALLO: %s' % c[2])
                        for c in checks if not c[1]) or 'todos los checks OK'
    return dict(prueba=prueba, motor=motor, alcance=alcance,
                veredicto='PASS' if len(ok) == len(checks) else 'FAIL',
                checks_ok=len(ok), checks_total=len(checks), detalle=detalle)


# ---------------------------------------------------------------- unidad (C)
def pruebas_unidad():
    filas, detalles = [], {}
    casos = [
        ('UC1', 'ajeno dentro de candidates/', 'candidates/ajeno_cand.wav',
         'ajeno', None),
        ('UC2', 'ajeno llamado SDV.wav', 'SDV.wav', 'ajeno', None),
        ('UC3', 'ajeno con nombre exacto de salida del motor', 'mix SDV.wav',
         'ajeno', None),
        ('UC4', 'propio acreditado (sellado) debe eliminarse', 'propio.wav',
         'propio_estable', None),
        ('UC5', 'propio sustituido tras su creación se conserva',
         'sustituido.wav', 'propio_sustituido', None),
        ('UC6', 'propio en curso (inodo continuo) debe eliminarse',
         'en_curso.wav', 'propio_curso', None),
        ('UC7', 'propio sellado modificado in situ se conserva',
         'sellado.json', 'propio_modificado', None),
    ]
    import lectura_segura_6g1 as L
    for cid, desc, rel, clase, _ in casos:
        run = TRABAJO / 'UC' / cid
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        L.reiniciar_registro_6g1()
        p = run / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'contenido original del archivo\n')
        info = None
        try:
            if clase == 'propio_estable':
                L.registrar_propio_6g1(p, estable=True)
            elif clase == 'propio_sustituido':
                L.registrar_propio_6g1(p, estable=True)
                otro = run / 'otro_contenido.bin'
                otro.write_bytes(b'contenido ajeno de reemplazo\n')
                os.replace(otro, p)
            elif clase == 'propio_curso':
                L.registrar_propio_6g1(p, estable=False)
            elif clase == 'propio_modificado':
                L.registrar_propio_6g1(p, estable=True)
                p.write_bytes(b'contenido ALTERADO in situ\n')
            info = L.abortar_6g1(run, 'PRUEBA_' + cid)
            if clase in ('ajeno', 'propio_sustituido', 'propio_modificado'):
                ok_borrado = rel not in info['salidas_invalidadas']
                ok_cons = rel in info['conservados']
                motivo = info['motivos_propiedad'].get(rel, '(sin motivo)')
                if clase == 'ajeno':
                    ok_motivo = motivo == 'ajeno_no_registrado'
                elif clase == 'propio_sustituido':
                    ok_motivo = motivo.startswith('identidad_distinta')
                else:
                    ok_motivo = motivo in ('contenido modificado tras el registro',
                                           'tamaño/mtime distintos de los registrados')
                checks = [('no_eliminado', ok_borrado, motivo),
                          ('conservado', ok_cons, motivo),
                          ('motivo_correcto', ok_motivo, motivo)]
            else:
                ok_borrado = rel in info['salidas_invalidadas']
                checks = [('eliminado', ok_borrado,
                           info['motivos_propiedad'].get(rel, '(sin motivo)'))]
            ok_schema = info.get('schema') == 'abort-6g1/2'
            checks.append(('schema_abort_6g1_2', ok_schema, info.get('schema')))
            filas.append(fila(cid, 'lectura_segura_6g1', desc, checks))
            detalles[cid] = dict(descripcion=desc, rel=rel, clase=clase,
                                 abort=info)
        except Exception as exc:
            filas.append(fila(cid, 'lectura_segura_6g1', desc, None,
                              motivo_ne='excepción del propio ensayo: %r' % exc))
            detalles[cid] = dict(descripcion=desc, rel=rel, clase=clase,
                                 error=repr(exc))
    return filas, detalles


# ---------------------------------------------------------------- motores
def estado_aborto(r, motor, esperado_neg=('after', 'ruta'),
                  propias_esperadas=None):
    """Checks comunes de aborto: código, motivo, sin publicación, propia
    eliminada, ajeno conservado y evidencia de integridad desfavorable en los
    componentes indicados (la guarda exige after AND ruta; con una inyección
    en un solo componente, el otro puede ser legítimamente True)."""
    out = Path(r['out'])
    abort = r['abort']
    propios = propias_esperadas if propias_esperadas is not None else SALIDAS[motor]
    checks = [
        ('exit_2', r['exit'] == 2, 'exit=%s' % r['exit']),
        ('abort_json', bool(abort), 'ABORT_6G1.json %s' % ('presente' if abort else 'ausente')),
        ('motivo', abort.get('motivo') == MOTIVO,
         'motivo=%s' % abort.get('motivo')),
        ('schema_abort_6g1_2', abort.get('schema') == 'abort-6g1/2',
         'schema=%s' % abort.get('schema')),
        ('sin_dir_definitivo', not dirs_definitivos(r['out'], motor),
         'definitivos=%s' % dirs_definitivos(r['out'], motor)),
    ]
    nom = sorted(p.name for p in out.rglob('*.wav')) if out.exists() else []
    faltan = [s for s in propios if s in nom]
    checks.append(('salidas_propias_eliminadas', not faltan,
                   'presentes=%s' % faltan))
    inv = abort.get('salidas_invalidadas', [])
    checks.append(('salidas_invalidadas_acreditadas',
                   all(s in inv for s in propios),
                   'invalidadas=%s' % inv))
    integ = r['integrity']
    after_ok = (integ.get('after', {}).get('unchanged') is False)
    ruta_ok = (integ.get('ruta_actual', {}).get('unchanged') is False)
    neg = {'after': after_ok, 'ruta': ruta_ok}
    checks.append(('evidencia_integridad_negativa_en_provisional',
                   all(neg[c] for c in esperado_neg),
                   'after=%s ruta=%s esperado_neg=%s'
                   % (integ.get('after', {}).get('unchanged'),
                      integ.get('ruta_actual', {}).get('unchanged'),
                      esperado_neg)))
    return checks, abort


def pruebas_motor(motor):
    filas, detalles = {}, {}
    mix_local_wav = {}
    # ---- T1 / T2 / T4 (inyección determinista en la guarda final)
    escenarios = [('T1', 'verificar_raise', 'excepción de hmix.verificar()'),
                  ('T2', 'ruta_raise',
                   'excepción de comprobación de ruta'),
                  ('T4', 'verificar_false',
                   'verificación fallida sin excepción')]
    for tid, inj, desc in escenarios:
        try:
            r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / tid, inject=inj)
            checks, abort = estado_aborto(r, motor,
                                          esperado_neg=ESPERADO_NEG[tid])
            filas[tid] = fila(tid, motor, desc, checks)
            detalles[tid] = dict(descripcion=desc, abort=abort,
                                 exit=r['exit'], wavs=r['wavs'],
                                 dirs_definitivos=dirs_definitivos(r['out'], motor))
        except Exception as exc:
            filas[tid] = fila(tid, motor, desc, None,
                              motivo_ne='entorno de ensayo: %r' % exc)
            detalles[tid] = dict(descripcion=desc, error=repr(exc))

    # ---- T3: sustitución del Mix tras abrir el descriptor (durante el DSP)
    try:
        work = TRABAJO / motor / 'T3'
        # el Mix sustituible vive FUERA del directorio de trabajo (que `correr`
        # recrea desde cero); nunca se toca el fixture del repositorio.
        mix_local = TRABAJO / 'mezclas' / ('T3_%s_mix_12s.flac' % motor)
        mix_local.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(FIX / 'mix_12s.flac'), str(mix_local))
        r = correr(motor, dict(mix=str(mix_local),
                               vocal=str(FIX / 'vocal_mix_12s.wav'),
                               instrumental=str(FIX / 'instrumental_mix_12s.wav')),
                   work, sustituir=dict(destino=mix_local,
                                        fuente=FIX / 'mix_otro.flac'),
                   patron_sustitucion=PATRON_DSP[motor],
                   extra=EXTRA_DSP)
        # Hardened/EVO nombran sus salidas '<stem> SDV.wav'; MQR usa SDV.wav.
        # En sustitución por os.replace el descriptor retiene el contenido
        # original (after=True legítimo); la ruta es la que deja de coincidir.
        if motor == 'MQR':
            propias_esp = SALIDAS['MQR']
        else:
            stem = Path(mix_local).stem
            propias_esp = ('%s SDV.wav' % stem, '%s SDI.wav' % stem)
        checks, abort = estado_aborto(r, motor, esperado_neg=('ruta',),
                                      propias_esperadas=propias_esp)
        checks.append(('sustitucion_aplicada',
                       r['evento'].get('sustitucion_aplicada') is True,
                       'evento=%s' % r['evento']))
        filas['T3'] = fila('T3', motor,
                           'sustitución del Mix tras abrir el descriptor (DSP)',
                           checks)
        detalles['T3'] = dict(descripcion='sustitución durante el DSP',
                              abort=abort, exit=r['exit'], evento=r['evento'])
    except Exception as exc:
        filas['T3'] = fila('T3', motor,
                           'sustitución del Mix tras abrir el descriptor (DSP)',
                           None, motivo_ne='entorno de ensayo: %r' % exc)
        detalles['T3'] = dict(error=repr(exc))

    # ---- T5: ausencia de directorio definitivo en TODOS los abortos T1–T4
    try:
        definitiva = []
        for tid in ('T1', 'T2', 'T3', 'T4'):
            det = detalles.get(tid, {})
            definitiva.extend(det.get('dirs_definitivos',
                                      dirs_definitivos(TRABAJO / motor / tid / 'out',
                                                       motor)))
        filas['T5'] = fila('T5', motor,
                           'ausencia de directorio definitivo tras los abortos',
                           [('ningun_directorio_definitivo_en_T1_T4',
                             not definitiva, 'definitivos=%s' % definitiva)])
        detalles['T5'] = dict(descripcion='agregado sobre T1–T4',
                              definitivos=definitiva)
    except Exception as exc:
        filas['T5'] = fila('T5', motor,
                           'ausencia de directorio definitivo tras los abortos',
                           None, motivo_ne='entorno de ensayo: %r' % exc)
        detalles['T5'] = dict(error=repr(exc))

    # ---- T6: conservación de ajenos con colisiones + eliminación de propias.
    # Siembra por creación (nombres que el motor no usa) y, además, REEMPLAZO
    # por os.replace de la salida propia ya cerrada del motor (inodo distinto:
    # propiedad indemostrable -> se conserva, caso 'sustituido tras creación').
    try:
        ajenos = AJENOS_T6[motor]
        reempl = REEMPLAZO_T6[motor]
        r = correr(motor, dict(mix=str(FIX / 'mix.wav'),
                               vocal=str(FIX / 'vocal_mix.wav'),
                               instrumental=str(FIX / 'instrumental_mix.wav')),
                   TRABAJO / motor / 'T6', inject='verificar_raise',
                   sembrar=ajenos, patron_siembra=PATRON_SIEMBRA,
                   reemplazar={n: FIX / 'mix_otro.flac' for n in reempl})
        propias_esp = [s for s in SALIDAS[motor] if s not in reempl]
        checks, abort = estado_aborto(r, motor,
                                      propias_esperadas=propias_esp)
        cons = abort.get('conservados', [])
        mot = abort.get('motivos_propiedad', {})
        checks.append(('siembra_aplicada',
                       sorted(r['evento'].get('sembrados', [])) == sorted(ajenos),
                       'sembrados=%s' % r['evento'].get('sembrados')))
        for a in ajenos:
            checks.append(('ajeno_conservado:%s' % a, a in cons,
                           'motivo=%s' % mot.get(a, '(sin motivo)')))
            checks.append(('ajeno_motivo_ajeno_no_registrado:%s' % a,
                           mot.get(a) == 'ajeno_no_registrado',
                           'motivo=%s' % mot.get(a, '(sin motivo)')))
        for n in reempl:
            checks.append(('propia_reemplazada_conservada:%s' % n,
                           n in cons and n not in abort.get('salidas_invalidadas', []),
                           'motivo=%s' % mot.get(n, '(sin motivo)')))
            checks.append(('reemplazo_motivo_identidad_distinta:%s' % n,
                           str(mot.get(n, '')).startswith('identidad_distinta'),
                           'motivo=%s' % mot.get(n, '(sin motivo)')))
        propias_inv = [s for s in propias_esp
                       if s in abort.get('salidas_invalidadas', [])]
        checks.append(('propias_eliminadas_con_acreditacion',
                       len(propias_inv) == len(propias_esp),
                       'invalidadas=%s' % abort.get('salidas_invalidadas', [])))
        filas['T6'] = fila('T6', motor,
                           'colisiones de nombre, candidates/ y sustitución '
                           'de salida propia en aborto', checks)
        detalles['T6'] = dict(descripcion='sembrados=%s reemplazados=%s'
                              % (ajenos, reempl), abort=abort,
                              evento=r['evento'])
    except Exception as exc:
        filas['T6'] = fila('T6', motor,
                           'colisiones de nombre, candidates/ y sustitución '
                           'de salida propia en aborto',
                           None, motivo_ne='entorno de ensayo: %r' % exc)
        detalles['T6'] = dict(error=repr(exc))

    # ---- T7: eliminación de salidas propias acreditadas (de T1)
    try:
        abort = detalles['T1']['abort']
        inv = abort.get('salidas_invalidadas', [])
        mot = abort.get('motivos_propiedad', {})
        checks = []
        for s in SALIDAS[motor]:
            checks.append(('propia_eliminada:%s' % s, s in inv,
                           'motivo=%s' % mot.get(s, '(sin motivo)')))
        filas['T7'] = fila('T7', motor,
                           'eliminación de salidas propias acreditadas', checks)
        detalles['T7'] = dict(descripcion='derivado de T1 (mismo ensayo, '
                                          'aserciones específicas de propiedad)',
                              salidas_invalidadas=inv,
                              motivos_propiedad={k: v for k, v in mot.items()
                                                 if k in SALIDAS[motor]})
    except Exception as exc:
        filas['T7'] = fila('T7', motor,
                           'eliminación de salidas propias acreditadas',
                           None, motivo_ne='entorno de ensayo: %r' % exc)
        detalles['T7'] = dict(error=repr(exc))

    return filas, detalles


def audited_pcm():
    d = json.loads((EV / 'contenedores_6g1.json').read_text())
    out = {}
    for m in MOTORES:
        for c in ('WAV', 'FLAC'):
            out[(m, c)] = d['casos']['%s/%s/full_processing' % (m, c)]['pcm']
    return out


def prueba_t8(motor, pcm_auditado):
    filas, detalles = {}, {}
    for cont, archivo in (('WAV', 'mix.wav'), ('FLAC', 'mix.flac')):
        try:
            r = correr(motor, dict(mix=str(FIX / archivo),
                                   vocal=str(FIX / 'vocal_mix.wav'),
                                   instrumental=str(FIX / 'instrumental_mix.wav')),
                       TRABAJO / motor / ('T8_' + cont), 'full_processing')
            defs = dirs_definitivos(r['out'], motor)
            integ = r['integrity']
            checks = [
                ('exit_0', r['exit'] == 0, 'exit=%s' % r['exit']),
                ('sin_abort', not r['abort'], 'abort=%s' % bool(r['abort'])),
                ('dir_definitivo_unico', len(defs) == 1, 'defs=%s' % defs),
                ('publicado_en_definitivo',
                 bool(defs) and all(d in r['run_dirs'][0] for d in defs[:1])
                 and len(r['run_dirs']) == 1 and defs[0] in r['run_dirs'][0],
                 'run_dirs=%s' % r['run_dirs']),
                ('integridad_after_true',
                 integ.get('after', {}).get('unchanged') is True,
                 'after=%s' % integ.get('after', {}).get('unchanged')),
                ('integridad_ruta_true',
                 integ.get('ruta_actual', {}).get('unchanged') is True,
                 'ruta=%s' % integ.get('ruta_actual', {}).get('unchanged')),
            ]
            pcm = {p['name']: p['pcm_sha256'] for p in r['pcm']
                   if 'pcm_sha256' in p}
            esperado = pcm_auditado.get((motor, cont), {})
            reales = bool(pcm) and len(pcm) == len(esperado) and len(esperado) > 0
            checks.append(('pcm_reales', reales, 'pcm=%s' % sorted(pcm)))
            checks.append(('pcm_identico_a_campana_auditada',
                           reales and pcm == esperado,
                           'diff=%s' % {k: (pcm.get(k, '')[:12],
                                            esperado.get(k, '')[:12])
                                        for k in set(pcm) | set(esperado)
                                        if pcm.get(k) != esperado.get(k)}))
            tid = 'T8 (%s)' % cont
            filas[tid] = fila('T8', motor,
                              'procesamiento normal + PCM vs campaña auditada (%s)' % cont,
                              checks)
            detalles[tid] = dict(descripcion='full_processing %s' % cont,
                                 exit=r['exit'], pcm=pcm,
                                 esperado=esperado, run_dirs=r['run_dirs'],
                                 dirs_definitivos=defs)
        except Exception as exc:
            filas['T8 (%s)' % cont] = fila('T8', motor,
                                           'procesamiento normal (%s)' % cont,
                                           None,
                                           motivo_ne='entorno de ensayo: %r' % exc)
            detalles['T8 (%s)' % cont] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    entorno_de_ejecucion = dict(python=sys.version.split()[0])
    todas, detalle_todo = [], {}
    print('== Unidad: propiedad y limpieza (corrección C) ==')
    fu, du = pruebas_unidad()
    todas.extend(fu)
    detalle_todo['unidad'] = du
    for f in fu:
        print('  %-4s %-14s %s' % (f['veredicto'], f['prueba'], f['detalle'][:90]))
    pa = audited_pcm()
    for motor in MOTORES:
        print('== Motor %s ==' % motor)
        fm, dm = pruebas_motor(motor)
        f8, d8 = prueba_t8(motor, pa)
        fm.update(f8)
        dm.update(d8)
        for tid, f in fm.items():
            todas.append(f)
            print('  %-14s %-18s %s' % (f['veredicto'], tid, f['detalle'][:90]))
        detalle_todo[motor] = dm
    dump(EV / 'pruebas_correccion_6g1.json',
         dict(schema='pruebas-correccion-6g1/1', entorno=entorno_de_ejecucion,
              filas=todas, detalles=detalle_todo))
    with (EV / 'matriz_correccion_6g1.csv').open('w', newline='',
                                                 encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=('prueba', 'motor', 'alcance',
                                           'veredicto', 'checks_ok',
                                           'checks_total', 'detalle'),
                           lineterminator='\n')
        w.writeheader()
        w.writerows(todas)
    npass = sum(1 for f in todas if f['veredicto'] == 'PASS')
    nfail = sum(1 for f in todas if f['veredicto'] == 'FAIL')
    nne = sum(1 for f in todas if f['veredicto'] == 'NOT_EXECUTED')
    print('RESUMEN: %d PASS, %d FAIL, %d NOT_EXECUTED de %d filas'
          % (npass, nfail, nne, len(todas)))


if __name__ == '__main__':
    main()
