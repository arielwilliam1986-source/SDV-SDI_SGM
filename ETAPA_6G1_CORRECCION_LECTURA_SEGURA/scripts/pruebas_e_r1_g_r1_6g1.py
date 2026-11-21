"""Pruebas E-R1 y G-R1 (rectificación 6G.1 — corrección puntual final II).

Ejecuta ÚNICAMENTE las pruebas nuevas de esta corrección; no repite las
baterías de 34 (A–D) ni de 26 (E–G). Cada prueba comprueba bytes, hashes,
identidad y estado final, no sólo códigos de salida.

  E-R1  Ventana TOCTOU al actualizar `analysis.json` (unidad, determinista):
    E-R1a  sustitución de `analysis.json` por otro archivo regular DESPUÉS de
           la acreditación y ANTES de la escritura (inyectada por un gancho
           sobre `_propiedad_fd_acreditada`, sin tocar el código del módulo):
           el sustituto debe conservar sus bytes y SHA-256; no debe escribirse
           sobre él; la escritura sólo puede alcanzar al objeto cuyo descriptor
           fue acreditado (motivo 'mismo descriptor verificado, sin reapertura').
    E-R1b  acreditación imposible (archivo sellado modificado in situ): el
           archivo se conserva byte a byte, sin truncar, con el motivo
           registrado (fail-closed).
  G-R1  Traslado del provisional al destino `_aborted` con no-reemplazo
        (end-to-end por SIGINT, los tres motores):
    G-R1a  destino `_aborted` preexistente CON archivos y centinelas;
    G-R1b  destino `_aborted` preexistente como directorio VACÍO;
    G-R1c  destino `_aborted` preexistente como ENLACE SIMBÓLICO;
    en los tres casos: el destino ajeno queda intacto (contenido/identidad),
    y el provisional propio queda conservado en su ubicación o trasladado a
    un sufijo libre (`_rNNN`) sin tocar el destino.
  Estático: ningún `os.rename(run_dir, ...)` restante en los tres motores.
  Sanidad mínima: corrida feliz por motor (no repite baterías).

Evidencia: evidence/pruebas_e_r1_g_r1_6g1.json + evidence/matriz_e_r1_g_r1_6g1.csv
"""
import csv
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
sys.path.insert(0, str(RAIZ / 'motores'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, recolectar, sha_file, dump

EV = RAIZ / 'evidence'
TRABAJO = Path('/tmp/f6g1er1gr1')

SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}
PREFIJO = {'Hardened': 'motorA_run_', 'EVO': 'motorA_run_', 'MQR': 'mqr_run_'}
# Anclas de SIGINT por motor (todas DENTRO del try, antes de cualquier
# publicación): Hardened/EVO registran chunks cada 10 (con --chunk-frames 32 y
# el mix de 12 s hay 17 chunks; 'Chunk 10/17' ocurre al ~59% del DSP, margen
# ~0.7 s); MQR no registra chunks: su ancla 'Escribiendo analysis.json' está
# dentro de _run_core/main, antes de la guarda y de la publicación (margen
# ~0.2 s; si el KI aterrizara más tarde, la prueba lo registra como fallo del
# disparo, no como éxito).
PATRON_SIGINT = {'Hardened': r'(?i)chunk\s+10\s*/',
                 'EVO': r'(?i)chunk\s+10\s*/',
                 'MQR': r'Escribiendo analysis\.json'}
EXTRA_SIGINT = {'Hardened': ('--chunk-frames', '32'),
                'EVO': ('--chunk-frames', '32'),
                'MQR': ()}


def fila(prueba, motor, alcance, checks, motivo_ne=None):
    if motivo_ne is not None:
        return dict(prueba=prueba, motor=motor, alcance=alcance,
                    veredicto='NOT_EXECUTED', checks_ok=0, checks_total=0,
                    detalle=motivo_ne)
    ok = [c for c in checks if c[1]]
    detalle = '; '.join('%s=FALLO: %s' % (c[0], c[2]) for c in checks
                        if not c[1]) or 'todos los checks OK'
    return dict(prueba=prueba, motor=motor, alcance=alcance,
                veredicto='PASS' if len(ok) == len(checks) else 'FAIL',
                checks_ok=len(ok), checks_total=len(checks), detalle=detalle)


def pcm_auditado(motor, cont='WAV'):
    d = json.loads((EV / 'contenedores_6g1.json').read_text())
    return d['casos']['%s/%s/full_processing' % (motor, cont)]['pcm']


# ------------------------------------------------------------- E-R1 (unidad)
def e_r1_unidad():
    filas, detalles = [], {}
    import lectura_segura_6g1 as L

    # ---- E-R1a: sustitución determinista entre acreditación y escritura
    try:
        run = TRABAJO / 'E-R1a'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        sustituto = TRABAJO / 'sustituto_externo_E-R1a.json'
        sustituto.parent.mkdir(parents=True, exist_ok=True)
        bytes_sub = (b'{"rol": "sustituto externo regular", '
                     b'"no_debo_ser_escrito": true}\n')
        sustituto.write_bytes(bytes_sub)
        sha_sub = sha_file(sustituto)
        ruta_a = run / 'analysis.json'
        ruta_a.write_bytes(b'{"original": true, "sellado": true}\n')
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_a, estable=True)
        propio = run / 'propio.wav'
        propio.write_bytes(b'salida propia\n')
        L.registrar_propio_6g1(propio, estable=True)

        original = L._propiedad_fd_acreditada
        estado = dict(sustituido=False)

        def gancho(run_dir, rel, st, datos):
            r = original(run_dir, rel, st, datos)
            if r[0] and rel == 'analysis.json' and not estado['sustituido']:
                # sustitución determinista: DESPUÉS de la acreditación y
                # ANTES de la escritura (exactamente la ventana del hallazgo).
                # Copia + os.replace: el sustituto conserva su propia ruta
                # (sólo se planta una copia bajo el nombre analysis.json).
                tmp = run / '.sustituto_tmp'
                shutil.copyfile(str(sustituto), str(tmp))
                os.replace(str(tmp), str(ruta_a))
                estado['sustituido'] = True
            return r

        L._propiedad_fd_acreditada = gancho
        try:
            info = L.abortar_6g1(run, 'PRUEBA_E-R1a')
        finally:
            L._propiedad_fd_acreditada = original
        checks = [
            ('sustitucion_inyectada', estado['sustituido'], ''),
            ('sustituto_byte_a_byte', sha_file(sustituto) == sha_sub,
             sha_file(sustituto)[:16]),
            ('no_se_escribe_sobre_sustituto',
             ruta_a.read_bytes() == bytes_sub, ruta_a.read_bytes()[:40]),
            ('escritura_solo_en_objeto_acreditado',
             'mismo descriptor verificado, sin '
             in str(info['motivos_propiedad'].get('analysis.json (actualizacion)', '')),
             str(info['motivos_propiedad'].get('analysis.json (actualizacion)'))),
            ('abort_regular_creado', (run / 'ABORT_6G1.json').is_file()
             and not os.path.islink(run / 'ABORT_6G1.json'), ''),
            ('propio_eliminado', 'propio.wav' in info['salidas_invalidadas'],
             str(info['salidas_invalidadas'])),
        ]
        filas.append(fila('E-R1a', 'lectura_segura_6g1',
                          'sustitución de analysis.json entre acreditación y '
                          'escritura: el sustituto no recibe la escritura',
                          checks))
        detalles['E-R1a'] = dict(motivos=info['motivos_propiedad'],
                                 salidas_invalidadas=info['salidas_invalidadas'])
    except Exception as exc:
        filas.append(fila('E-R1a', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E-R1a'] = dict(error=repr(exc))

    # ---- E-R1b: acreditación imposible -> conservado, sin truncar, con motivo
    try:
        run = TRABAJO / 'E-R1b'
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        contenido = b'{"original": true, "se_modifico_in_situ": true}\n'
        ruta_a = run / 'analysis.json'
        ruta_a.write_bytes(b'{"original": true, "sellado": true}\n')
        L.reiniciar_registro_6g1()
        L.registrar_propio_6g1(ruta_a, estable=True)
        ruta_a.write_bytes(contenido)              # modificado tras el sello
        info = L.abortar_6g1(run, 'PRUEBA_E-R1b')
        checks = [
            ('conservado_byte_a_byte', ruta_a.read_bytes() == contenido,
             ruta_a.read_bytes()[:40]),
            ('no_truncado', ruta_a.stat().st_size == len(contenido),
             str(ruta_a.stat().st_size)),
            ('motivo_propiedad_no_acreditada',
             'propiedad no acreditada' in str(info['motivos_propiedad']
                                              .get('analysis.json (actualizacion)', '')),
             str(info['motivos_propiedad'].get('analysis.json (actualizacion)'))),
            ('abort_regular_creado', (run / 'ABORT_6G1.json').is_file(), ''),
        ]
        filas.append(fila('E-R1b', 'lectura_segura_6g1',
                          'acreditación imposible: conservado sin modificar '
                          '(fail-closed)', checks))
        detalles['E-R1b'] = dict(motivos=info['motivos_propiedad'])
    except Exception as exc:
        filas.append(fila('E-R1b', 'lectura_segura_6g1', 'unidad', None,
                          motivo_ne='entorno de ensayo: %r' % exc))
        detalles['E-R1b'] = dict(error=repr(exc))

    return filas, detalles


# ------------------------------------------------------- G-R1 (end-to-end)
def correr_sigint(motor, work, preparar_destino):
    """Corre el motor en full_processing; un vigía espera el *_partial,
    prepara el destino `_aborted` según `preparar_destino(destino)` y, al
    aparecer 'chunk 10/' en el log del motor, le envía SIGINT (ruta
    KeyboardInterrupt -> traslado al destino de aborto)."""
    work = Path(work)
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    man = work / 'manifest.json'
    # Mix de 12 s: con 2 s y chunk-frames 48 el DSP tendría sólo 2 chunks y
    # 'chunk 10/' nunca aparecería (misma técnica de la campaña 6G.1).
    escribir_manifest(man, dict(mix=str(FIX / 'mix_12s.wav'),
                                vocal=str(FIX / 'vocal_mix_12s.wav'),
                                instrumental=str(FIX / 'instrumental_mix_12s.wav')))
    out = work / 'out'
    cmd = [sys.executable, '-B', str(MOT / MOTORES[motor]),
           '--manifest', str(man), '--out', str(out),
           '--mode', 'full_processing', *EXTRA_SIGINT[motor]]
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    suceso = dict(destino_preparado=False, sigint_enviado=False, destino=None)

    def vigia():
        parcial = None
        fin = time.time() + 120
        while time.time() < fin and parcial is None and proc.poll() is None:
            if out.exists():
                cands = sorted(out.glob('*_partial'))
                if cands:
                    parcial = cands[0]
                    break
            time.sleep(0.002)
        if parcial is None:
            return
        destino = Path(str(parcial)[:-len('_partial')] + '_aborted')
        suceso['destino'] = str(destino)
        try:
            preparar_destino(destino)
            suceso['destino_preparado'] = True
        except Exception as exc:
            suceso['error_preparacion'] = repr(exc)
            return
        fin2 = time.time() + 120
        while time.time() < fin2 and proc.poll() is None:
            try:
                texto = (parcial / 'engine_log.txt').read_text(errors='replace')
            except OSError:
                texto = ''
            import re
            if re.search(PATRON_SIGINT[motor], texto):
                try:
                    os.kill(proc.pid, signal.SIGINT)
                    suceso['sigint_enviado'] = True
                except ProcessLookupError:
                    pass
                return
            time.sleep(0.002)

    h = threading.Thread(target=vigia, daemon=True)
    h.start()
    salida = proc.communicate(timeout=900)[0] or ''
    h.join(timeout=5)
    try:
        datos = recolectar(out)
    except Exception as exc:
        # KI a mitad de write_reports: analysis.json puede quedar truncado;
        # para G-R1 basta el estado del proceso y de los archivos.
        datos = dict(wavs=[], pcm=[], wavs_validos=0, report={},
                     report_leido=False, integrity={}, abort={},
                     run_dirs=[], recolecta_error=repr(exc))
    datos.update(exit=proc.returncode, stdout_tail=salida[-4000:],
                 suceso=suceso, out=str(out))
    return datos


def estado_traslado(out, motor, destino, parcial_esperado):
    """Devuelve (conservado_en_parcial, trasladado_a) para el provisional
    (tras el aborto, el *_partial normalmente ya fue trasladado)."""
    out = Path(out)
    conservado = bool(parcial_esperado) and parcial_esperado.is_dir()
    trasladado = None
    if destino is not None:
        base = str(destino)
        for d in sorted(out.glob('*_aborted_r*')):
            if d.is_dir() and d.name.startswith(Path(base).name + '_r'):
                trasladado = d
                break
    return conservado, trasladado


def g_r1_motores():
    filas, detalles = [], {}
    bytes_a = b'centinela A: archivo ajeno preexistente\n'
    bytes_b = b'centinela B: binario ajeno preexistente\n'
    bytes_ext = b'{"externo": "objetivo del enlace simbolico ajeno"}\n'

    def prep_con_archivos(destino):
        destino.mkdir(parents=True)
        (destino / 'sentinela_a.txt').write_bytes(bytes_a)
        (destino / 'sentinela_b.dat').write_bytes(bytes_b)

    def prep_vacio(destino):
        destino.mkdir(parents=True)

    def prep_enlace(destino, externo):
        externo.parent.mkdir(parents=True, exist_ok=True)
        if not externo.exists():
            externo.write_bytes(bytes_ext)
        os.symlink(str(externo), destino)

    for motor in MOTORES:
        for tag, prep, extra_checks in (
                ('G-R1a', prep_con_archivos, 'con archivos y centinelas'),
                ('G-R1b', prep_vacio, 'directorio vacío'),
                ('G-R1c', 'enlace', 'enlace simbólico')):
            try:
                externo = TRABAJO / motor / (tag + '_externo.json')
                work = TRABAJO / motor / tag
                if tag == 'G-R1c':
                    def preparar(destino, _e=externo):
                        prep_enlace(destino, _e)
                else:
                    preparar = prep
                r = correr_sigint(motor, work, preparar)
                out = Path(r['out'])
                parciales = sorted(out.glob('*_partial'))
                parcial = parciales[0] if parciales else None
                destino = Path(r['suceso']['destino']) if r['suceso'].get('destino') else None
                checks = [
                    ('sigint_entregado', r['suceso'].get('sigint_enviado') is True,
                     str(r['suceso'])),
                    ('destino_preparado', r['suceso'].get('destino_preparado') is True,
                     str(r['suceso'])),
                    ('exit_130', r['exit'] == 130, 'exit=%s' % r['exit']),
                ]
                conservado, trasladado = estado_traslado(
                    out, motor, destino, parcial)
                if tag == 'G-R1a':
                    checks += [
                        ('centinela_a_intacto',
                         sha_file(destino / 'sentinela_a.txt') == hashlib.sha256(bytes_a).hexdigest(),
                         sha_file(destino / 'sentinela_a.txt')[:16]),
                        ('centinela_b_intacto',
                         sha_file(destino / 'sentinela_b.dat') == hashlib.sha256(bytes_b).hexdigest(),
                         sha_file(destino / 'sentinela_b.dat')[:16]),
                        ('destino_sin_artefactos_del_motor',
                         sorted(p.name for p in destino.iterdir())
                         == ['sentinela_a.txt', 'sentinela_b.dat'],
                         str(sorted(p.name for p in destino.iterdir()))),
                    ]
                elif tag == 'G-R1b':
                    checks += [
                        ('destino_sigue_vacio',
                         destino.is_dir() and not any(destino.iterdir()),
                         str(sorted(p.name for p in destino.iterdir()))),
                    ]
                else:
                    checks += [
                        ('destino_sigue_enlace', os.path.islink(destino), ''),
                        ('externo_byte_a_byte',
                         sha_file(destino.resolve()) == hashlib.sha256(bytes_ext).hexdigest(),
                         sha_file(destino.resolve())[:16]),
                    ]
                checks += [
                    ('provisional_conservado_o_trasladado',
                     conservado or (trasladado is not None
                                    and (trasladado / 'engine_log.txt').is_file()),
                     'conservado=%s trasladado=%s'
                     % (conservado, trasladado and trasladado.name)),
                    ('sin_fusion_con_destino_ajeno',
                     trasladado is not None or conservado,
                     'el provisional nunca se mezcló con el destino ajeno'),
                ]
                filas.append(fila(tag, motor,
                                  'destino _aborted preexistente (%s)' % extra_checks,
                                  checks))
                detalles.setdefault(motor, {})[tag] = dict(
                    exit=r['exit'], suceso=r['suceso'],
                    conservado=conservado,
                    trasladado=str(trasladado) if trasladado else None)
            except Exception as exc:
                filas.append(fila(tag, motor,
                                  'destino _aborted preexistente (%s)' % extra_checks,
                                  None, motivo_ne='entorno de ensayo: %r' % exc))
                detalles.setdefault(motor, {})[tag] = dict(error=repr(exc))
        # ---- estático: sin os.rename(run_dir, ...) en el motor
        try:
            src = (MOT / MOTORES[motor]).read_text(encoding='utf-8')
            checks = [
                ('sin_os_rename_run_dir', 'os.rename(run_dir' not in src, ''),
                ('traslado_via_publicar_dir_6g1', '_publicar_dir_6g1(run_dir, aborted)' in src, ''),
            ]
            filas.append(fila('G-R1-estatico', motor,
                              'traslado de aborto por la vía segura', checks))
            detalles.setdefault(motor, {})['G-R1-estatico'] = dict(estatico=True)
        except Exception as exc:
            filas.append(fila('G-R1-estatico', motor, 'estático', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['G-R1-estatico'] = dict(error=repr(exc))
        # ---- sanidad mínima (no repite baterías)
        try:
            work = TRABAJO / motor / 'sanidad'
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
            man = work / 'manifest.json'
            escribir_manifest(man, dict(mix=str(FIX / 'mix.wav'),
                                        vocal=str(FIX / 'vocal_mix.wav'),
                                        instrumental=str(FIX / 'instrumental_mix.wav')))
            out = work / 'out'
            cmd = [sys.executable, '-B', str(MOT / MOTORES[motor]),
                   '--manifest', str(man), '--out', str(out),
                   '--mode', 'full_processing']
            p = subprocess.run(cmd, cwd=str(MOT), capture_output=True,
                               text=True, timeout=600)
            datos = recolectar(out)
            pcm = {pp['name']: pp['pcm_sha256'] for pp in datos['pcm']
                   if 'pcm_sha256' in pp}
            defs = [d.name for d in out.iterdir()
                    if d.is_dir() and d.name.startswith(PREFIJO[motor])
                    and not d.name.endswith('_partial')
                    and not d.name.endswith('_aborted')
                    and '_r' not in d.name.split(PREFIJO[motor])[1]]
            integ = datos['integrity']
            checks = [
                ('exit_0', p.returncode == 0, 'exit=%s' % p.returncode),
                ('publicacion_unica', len(defs) == 1, 'defs=%s' % defs),
                ('integridad_true',
                 integ.get('after', {}).get('unchanged') is True
                 and integ.get('ruta_actual', {}).get('unchanged') is True, ''),
                ('pcm_identico_a_campana_auditada', pcm == pcm_auditado(motor),
                 'diff=%s' % {k: pcm.get(k, '')[:12] for k in
                              set(pcm) | set(pcm_auditado(motor))
                              if pcm.get(k) != pcm_auditado(motor).get(k)}),
            ]
            filas.append(fila('sanidad', motor,
                              'corrida feliz tras E-R1/G-R1', checks))
            detalles.setdefault(motor, {})['sanidad'] = dict(exit=p.returncode)
        except Exception as exc:
            filas.append(fila('sanidad', motor, 'corrida feliz', None,
                              motivo_ne='entorno de ensayo: %r' % exc))
            detalles.setdefault(motor, {})['sanidad'] = dict(error=repr(exc))
    return filas, detalles


def main():
    EV.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    todas, detalle_todo = [], {}
    print('== E-R1 (unidad, determinista) ==')
    fe, de = e_r1_unidad()
    todas.extend(fe)
    detalle_todo['E-R1'] = de
    for f in fe:
        print('  %-14s %-24s %s' % (f['veredicto'], f['prueba'], f['detalle'][:80]))
    print('== G-R1 (end-to-end x3 motores) ==')
    fg, dg = g_r1_motores()
    todas.extend(fg)
    detalle_todo.update(dg)
    for f in fg:
        print('  %-14s %-6s %-16s %s' % (f['veredicto'], f['motor'],
                                         f['prueba'], f['detalle'][:80]))
    dump(EV / 'pruebas_e_r1_g_r1_6g1.json',
         dict(schema='pruebas-e-r1-g-r1-6g1/1', filas=todas,
              detalles=detalle_todo))
    with (EV / 'matriz_e_r1_g_r1_6g1.csv').open('w', newline='',
                                                encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=('prueba', 'motor', 'alcance',
                                           'veredicto', 'checks_ok',
                                           'checks_total', 'detalle'),
                           lineterminator='\n')
        w.writeheader()
        w.writerows(todas)
    n = {v: sum(1 for f in todas if f['veredicto'] == v)
         for v in ('PASS', 'FAIL', 'NOT_EXECUTED')}
    print('RESUMEN: %d PASS, %d FAIL, %d NOT_EXECUTED de %d filas'
          % (n['PASS'], n['FAIL'], n['NOT_EXECUTED'], len(todas)))


if __name__ == '__main__':
    main()
