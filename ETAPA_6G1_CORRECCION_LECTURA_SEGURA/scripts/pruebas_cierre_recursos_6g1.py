#!/usr/bin/env python3
"""Batería 6G.1 / CR: cierre determinista de recursos en abortos ocurridos
DURANTE el procesamiento (instrucción de Cris sobre c38d00d).

Escenarios, cada uno sobre los 3 motores:
  R1  KeyboardInterrupt durante el procesamiento con escritores abiertos.
  R2  Excepción general durante el procesamiento con escritores abiertos.
  R3  (complementario) R2 con un memmap imposible de cerrar de forma segura
      (el arnés retiene una vista viva). Debe quedar el error documentado,
      el ABORT registrado y el provisional SIN trasladar.
  R4  (complementario) apertura del Mix fallida DESPUÉS de construir los
      CandidateRunner (escritores y memmaps abiertos, 0 frames): ejercita el
      manejador de FalloCorrida6G1; registro sin traslado.
  R5  [CR-R1] R2 con un fallo de cierre del lector del Mix (OSError en
      MixHandle.close; el lector queda abierto). Debe quedar el error
      documentado en engine_log.txt, completo=False, el ABORT registrado y el
      provisional SIN trasladar.
  E0  (complementario) corrida feliz con los argumentos por defecto: código
      0, publicación única sin ABORT, PCM idéntico al registrado en
      evidence/no_regresion_dsp_6g1.json (sólo lectura) y ningún descriptor
      ni mapeo vivo bajo la salida al terminar main().

La inyección (scripts/inyeccion_cierre_6g1/ejecutar_motor_cierre.py) se
dispara dentro de OlaStream.push, a mitad del bucle por bloques. En ese
momento existen:
  - varios CandidateRunner con escritores WAV abiertos (--write-all-candidates);
  - al menos dos bloques escritos en el flujo que dispara;
  - los memmaps de máscaras vivos (--keep-masks en Hardened y EVO; MQR los
    crea siempre).
Se usa --chunk-frames 16: con el fixture de 89 tramas da 6 bloques, de modo
que el fallo cae en mitad del procesamiento. Es un argumento de línea de
órdenes de tamaño de bloque; no cambia código y la corrida aborta, así que
no se evalúa ninguna salida de audio.

Comprobaciones por caso:
  - código de salida y retorno real de run_experiment (nunca EXIT_OK);
  - condiciones de la inyección;
  - en la ENTRADA de abortar_6g1:
      * todos los escritores WAV cerrados;
      * lectores cerrados;
      * memmaps con el mmap cerrado y el array liberado;
      * ningún descriptor ni mapeo bajo la salida ni sobre las entradas;
  - orden temporal de eventos: inyección → cierres → registro → traslado,
    sin ningún cierre después del registro;
  - ABORT_6G1.json con schema /3, motivo correcto, resultados_validos=[] y
    directorio acreditado;
  - salidas parciales (WAV y .npy) invalidadas y conservadas;
  - cabecera RIFF finalizada: tamaño RIFF y del chunk data coherentes con
    el archivo y con los frames escritos;
  - contenido lógico de los memmaps igual al del instante de la inyección;
  - analysis.json intacto (si no existía, el aborto no lo crea);
  - archivo ajeno conservado y destino preexistente no reemplazado;
  - nada escrito fuera, e identidad del directorio conservada;
  - SHA-256 estable entre la entrada al registro, la salida del registro, el
    final de main() y DESPUÉS de terminar el proceso (aquí ya actuaron los
    finalizadores del intérprete);
  - ningún descriptor de escritura vivo al terminar main();
  - engine_log.txt documenta el cierre.

`--base DIR --etiqueta-base X` ejecuta la MISMA batería sobre otra copia de los
motores. Es sólo un diagnóstico y no cambia el veredicto.

Evidencia (por defecto): evidence/pruebas_cierre_recursos_6g1.json y
           evidence/matriz_cierre_recursos_6g1.csv; `--json`/`--csv` permiten
           otra ruta (la rectificación CR-R1 escribe archivos propios para no
           sobrescribir la evidencia de 8e773df).
Salida 0 sólo si todos los casos de los motores corregidos dan PASS.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / 'scripts'))
from comun_6g1 import FIX, MOT, MOTORES, escribir_manifest, sha_file, entorno  # noqa: E402

EV = RAIZ / 'evidence'
EJECUTOR = RAIZ / 'scripts' / 'inyeccion_cierre_6g1' / 'ejecutar_motor_cierre.py'
TRABAJO = Path('/tmp/f6g1cr')
EXIT_OK, EXIT_PROCESSING, EXIT_ABORTED = 0, 2, 130
AJENO_EXTERNO = b'archivo ajeno junto al directorio de salida (CR 6G.1)\n'
ENTRADAS = [FIX / 'mix.wav', FIX / 'vocal_mix.wav', FIX / 'instrumental_mix.wav']

# escenario: (condición, código, motivo, trasladado, cierre completo)
ESCENARIOS = {
    'R1': ('KeyboardInterrupt durante el procesamiento con escritores abiertos',
           EXIT_ABORTED, 'INTERRUPCION_DEL_USUARIO', True, True),
    'R2': ('Excepción general durante el procesamiento con escritores abiertos',
           EXIT_PROCESSING, 'EXCEPCION_DURANTE_EL_PROCESAMIENTO', True, True),
    'R3': ('Excepción general con un memmap no cerrable de forma segura '
           '(complementario)', EXIT_PROCESSING,
           'EXCEPCION_DURANTE_EL_PROCESAMIENTO', False, False),
    'R4': ('Apertura del Mix fallida con CandidateRunner y memmaps abiertos '
           '(complementario)', EXIT_PROCESSING, 'MIX_NO_ABIERTO_ANTES_DEL_DSP',
           False, True),
    'R5': ('Excepción general con fallo de cierre del lector del Mix (CR-R1)',
           EXIT_PROCESSING, 'EXCEPCION_DURANTE_EL_PROCESAMIENTO', False, False),
    'E0': ('Corrida feliz instrumentada, argumentos por defecto (complementario)',
           EXIT_OK, None, False, True),
}
# recurso que queda sin cerrar en los escenarios con cierre incompleto
INCOMPLETO = {'R3': 'memmap', 'R5': 'lector'}
SALIDAS = {'Hardened': ('mix SDV.wav', 'mix SDI.wav'),
           'EVO': ('mix SDV.wav', 'mix SDI.wav'),
           'MQR': ('SDV.wav', 'SDI.wav')}


def args_motor(motor, man, out, esc):
    a = ['--manifest', str(man), '--out', str(out), '--mode', 'full_processing']
    if esc == 'E0':
        return a                    # argumentos por defecto (PCM de referencia)
    a += ['--chunk-frames', '16', '--write-all-candidates']
    if motor in ('Hardened', 'EVO'):
        a.append('--keep-masks')
    return a


def ejecutar(motores_dir, motor, esc, etiqueta):
    work = TRABAJO / etiqueta / motor / esc
    if work.exists():
        shutil.rmtree(work)
    out = work / 'out'
    out.mkdir(parents=True, mode=0o700)
    externo = out / 'AJENO_EXTERNO.txt'
    externo.write_bytes(AJENO_EXTERNO)
    man = escribir_manifest(work / 'manifest.json',
                            dict(mix=str(ENTRADAS[0]), vocal=str(ENTRADAS[1]),
                                 instrumental=str(ENTRADAS[2])))
    snap = work / 'estado.json'
    env = dict(os.environ, SDVSDI_CR_SNAP=str(snap), SDVSDI_CR_OUT=str(out),
               SDVSDI_CR_ENTRADAS=os.pathsep.join(str(p) for p in ENTRADAS),
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('PYTHONPATH', None)
    cmd = [sys.executable, '-B', str(EJECUTOR), esc,
           str(motores_dir / MOTORES[motor])] + args_motor(motor, man, out, esc)
    p = subprocess.run(cmd, cwd=str(motores_dir), env=env, capture_output=True,
                       text=True, timeout=600)
    estado = json.loads(snap.read_text()) if snap.exists() else {}
    return dict(work=work, out=out, externo=externo, codigo=p.returncode,
                stdout=(p.stdout or '')[-4000:], stderr=(p.stderr or '')[-4000:],
                estado=estado, cmd=cmd[3:])


# ------------------------------------------------------------------- helpers
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


def riff(path):
    """Coherencia de la cabecera RIFF/WAVE con el archivo en disco."""
    b = Path(path).read_bytes()
    if len(b) < 12 or b[:4] != b'RIFF' or b[8:12] != b'WAVE':
        return dict(ok=False, motivo='sin cabecera RIFF/WAVE')
    riff_size = int.from_bytes(b[4:8], 'little')
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(b):
        cid = b[pos:pos + 4]
        size = int.from_bytes(b[pos + 4:pos + 8], 'little')
        if cid == b'fmt ':
            fmt = b[pos + 8:pos + 8 + size]
        if cid == b'data':
            data = (pos + 8, size)
            break
        pos += 8 + size + (size & 1)
    if fmt is None or data is None:
        return dict(ok=False, motivo='sin chunk fmt/data', riff_size=riff_size)
    return dict(ok=True, tamano=len(b), riff_size=riff_size, data_offset=data[0],
                data_size=data[1], block_align=int.from_bytes(fmt[12:14], 'little'))


def sha_logico_npy(path):
    import numpy as np
    a = np.load(str(path), mmap_mode=None, allow_pickle=False)
    return hashlib.sha256(a.tobytes()).hexdigest(), list(a.shape), str(a.dtype)


def leer_abort(d):
    p = Path(d) / 'ABORT_6G1.json'
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return None


def sha_pcm(path):
    import soundfile as sf
    x, _ = sf.read(str(path), dtype='float64', always_2d=True)
    return hashlib.sha256(x.astype('<f8').tobytes()).hexdigest()


def pcm_registrado():
    d = json.loads((EV / 'no_regresion_dsp_6g1.json').read_text(encoding='utf-8'))
    return {m: v['pcm']['WAV']['pcm_6g1'] for m, v in d['motores'].items()}


def verificar_e0(motor, r):
    e = r['estado']
    ch = {}

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), str(detalle)[:600])

    out = r['out']
    ret = e.get('retorno_run_experiment') or {}
    c('codigo_salida', r['codigo'] == EXIT_OK, r['codigo'])
    c('run_experiment_EXIT_OK_con_ruta_publicada', ret.get('codigo') == EXIT_OK
      and ret.get('ruta_es_directorio') is True, ret)
    entradas = sorted(os.listdir(out))
    dirs = [x for x in entradas if (out / x).is_dir()]
    c('publicacion_unica', len(dirs) == 1 and not dirs[0].endswith(('_partial', '_aborted'))
      and '_aborted_r' not in dirs[0], entradas)
    c('externo_intacto', r['externo'].read_bytes() == AJENO_EXTERNO)
    c('sin_registro_de_aborto', not [x for x in e.get('eventos', [])
                                     if x['tipo'].startswith('abortar')])
    if len(dirs) == 1:
        fin = out / dirs[0]
        c('sin_ABORT', not (fin / 'ABORT_6G1.json').exists())
        ref = pcm_registrado()[motor]
        h = {n: sha_pcm(fin / n) for n in SALIDAS[motor] if (fin / n).is_file()}
        c('pcm_igual_al_registrado', h == {n: ref[n] for n in SALIDAS[motor]}, h)
    ff = e.get('fotos', {}).get('fin_proceso')
    c('sin_descriptores_ni_mapeos_al_terminar_main', ff is not None
      and ff['descriptores_salida_o_entradas'] == [] and ff['mapeos_bajo_salida'] == [],
      ff and (ff['descriptores_salida_o_entradas'], ff['mapeos_bajo_salida']))
    c('escritores_cerrados_al_terminar_main', ff is not None
      and all(w['cerrado'] for w in ff['escritores']) and ff['escritores'],
      ff and ff['escritores'])
    return ch, {}


# --------------------------------------------------------------- verificación
def verificar(motor, esc, r):
    if esc == 'E0':
        return verificar_e0(motor, r)
    cond, cod_esp, motivo_esp, tras_esp, completo_esp = ESCENARIOS[esc]
    fallo = INCOMPLETO.get(esc)
    e = r['estado']
    ch = {}

    def c(nombre, ok, detalle=''):
        ch[nombre] = (bool(ok), str(detalle)[:600])

    out = r['out']
    c('codigo_salida', r['codigo'] == cod_esp, 'obtenido %s, esperado %s' % (r['codigo'], cod_esp))
    c('nunca_EXIT_OK', r['codigo'] != EXIT_OK, r['codigo'])
    ret = e.get('retorno_run_experiment') or {}
    c('run_experiment_nunca_EXIT_OK', bool(ret) and ret.get('codigo') == cod_esp
      and ret.get('codigo') != EXIT_OK, ret)
    c('ki_no_escapa_del_motor', not e.get('ki_escapo', False))
    c('externo_intacto', r['externo'].is_file() and r['externo'].read_bytes() == AJENO_EXTERNO)

    inj = e.get('inyeccion')
    c('inyeccion_realizada', bool(inj), 'sin inyección' if not inj else inj['flujo'])
    if not inj:
        return ch, {}
    prov, final = Path(inj['provisional']), Path(inj['final'])
    escr_inj = inj['escritores']
    abiertos = [w for w in escr_inj if w['abierto']]
    if esc == 'R4':
        c('inyeccion_antes_del_dsp_con_escritores_y_memmaps_abiertos',
          inj['flujo_pushes'] == 0 and len(inj['memmaps']) >= 1
          and all(w['frames'] == 0 for w in escr_inj),
          'memmaps=%d escritores=%d' % (len(inj['memmaps']), len(escr_inj)))
    else:
        c('inyeccion_durante_procesamiento',
          inj['flujo_pushes'] >= 2 and inj['flujo_frames'] > 0
          and any(w['frames'] > 0 for w in abiertos)
          and all(t > 44 for t in inj['tamanos'].values()) and len(inj['memmaps']) >= 1,
          'flujo=%s pushes=%s frames=%s memmaps=%d tamanos=%s'
          % (inj['flujo'], inj['flujo_pushes'], inj['flujo_frames'], len(inj['memmaps']),
             inj['tamanos']))
    c('varios_candidaterunner_con_escritores_abiertos', len(abiertos) >= 4,
      '%d escritores abiertos: %s' % (len(abiertos),
                                      [os.path.relpath(w['ruta'], prov) for w in abiertos]))

    eventos = e.get('eventos', [])
    n_of = lambda t: [x['n'] for x in eventos if x['tipo'] == t]  # noqa: E731
    n_inj = (n_of('inyeccion') or [None])[0]
    n_ab_in = (n_of('abortar_6g1_entrada') or [None])[0]
    n_ab_out = (n_of('abortar_6g1_salida') or [None])[0]
    n_tr = n_of('traslado_entrada')
    cierres_esc = [x for x in eventos if x['tipo'] == 'escritor_cerrado']
    rutas_abiertas = {w['ruta'] for w in abiertos}
    cerrados_por_ruta = {x['ruta']: x for x in cierres_esc}
    fe = e.get('fotos', {}).get('entrada_abortar')
    fs = e.get('fotos', {}).get('salida_abortar')
    ff = e.get('fotos', {}).get('fin_proceso')
    c('registro_de_aborto_invocado', n_ab_in is not None and fe is not None)
    if fe is None:
        return ch, {}

    # --- estado en la ENTRADA de abortar_6g1
    c('escritores_cerrados_antes_de_abortar',
      all(w['cerrado'] for w in fe['escritores'])
      and rutas_abiertas <= {w['ruta'] for w in fe['escritores']},
      [(os.path.basename(w['ruta']), w['cerrado']) for w in fe['escritores']])
    lector_fallido = e.get('lector_fallido')
    if fallo == 'lector':
        c('fallo_de_cierre_de_lector_inyectado',
          lector_fallido is not None and lector_fallido == ENTRADAS[0].resolve().as_posix(),
          lector_fallido)
        c('unico_lector_abierto_es_el_fallido', fe['lectores_abiertos'] == [lector_fallido],
          fe['lectores_abiertos'])
    else:
        c('lectores_cerrados_antes_de_abortar', fe['lectores_abiertos'] == [],
          fe['lectores_abiertos'])
    retenido = inj.get('memmap_retenido')
    mm_ok = [m for m in fe['memmaps'] if m['mmap_cerrado'] is True and not m['array_vivo']]
    mm_no = [m for m in fe['memmaps'] if m not in mm_ok]
    if fallo != 'memmap':
        c('memmaps_vaciados_y_cerrados_antes_de_abortar',
          fe['memmaps'] and not mm_no, 'cerrados %d/%d; abiertos %s'
          % (len(mm_ok), len(fe['memmaps']), [os.path.basename(m['ruta']) for m in mm_no]))
        # en R5 sólo se toleran los descriptores de SÓLO LECTURA del lector
        # fallido (sobre la entrada, fuera del provisional)
        desc = [d for d in fe['descriptores_salida_o_entradas']
                if not (fallo == 'lector' and d['destino'] == lector_fallido
                        and d['escritura'] is False)]
        c('sin_descriptores_ni_mapeos_al_abortar',
          desc == [] and fe['mapeos_bajo_salida'] == [],
          '%s %s' % (fe['descriptores_salida_o_entradas'], fe['mapeos_bajo_salida']))
    else:
        c('memmap_no_cerrable_detectado_resto_cerrado',
          [m['ruta'] for m in mm_no] == [retenido],
          'no cerrados: %s' % [os.path.basename(m['ruta']) for m in mm_no])
        c('unico_recurso_abierto_es_el_retenido',
          fe['mapeos_bajo_salida'] == [retenido]
          and all(d['destino'] == retenido for d in fe['descriptores_salida_o_entradas']),
          '%s %s' % (fe['descriptores_salida_o_entradas'], fe['mapeos_bajo_salida']))

    # --- orden temporal
    orden_ok = (n_inj is not None and n_ab_in is not None and n_ab_out is not None
                and rutas_abiertas <= set(cerrados_por_ruta)
                and all(n_inj < cerrados_por_ruta[p]['n'] < n_ab_in for p in rutas_abiertas)
                and not [x for x in eventos if x['n'] > n_ab_in
                         and x['tipo'] in ('escritor_cerrado', 'lector_cerrado')]
                and n_ab_in < n_ab_out)
    if tras_esp:
        orden_ok = orden_ok and len(n_tr) == 1 and n_tr[0] > n_ab_out
    else:
        orden_ok = orden_ok and not n_tr
    secuencia = [(x['n'], x['tipo'], os.path.basename(x.get('ruta', '') or ''))
                 for x in eventos if x['n'] >= (n_inj or 0)]
    c('orden_cierre_registro_traslado', orden_ok, secuencia)

    # --- ubicación final
    tr = [x for x in eventos if x['tipo'] == 'traslado_salida']
    ubic = Path(tr[-1]['ruta']) if tr else prov
    entradas = sorted(os.listdir(out))
    if tras_esp:
        c('trasladado_sin_reemplazo', ubic == Path(str(final) + '_aborted_r001')
          and ubic.is_dir() and not prov.exists(), ubic.name)
    else:
        c('provisional_conservado_sin_traslado', ubic == prov and prov.is_dir()
          and not any(x.startswith(final.name + '_aborted_r') for x in entradas), entradas)
    c('identidad_del_directorio_conservada', ident(ubic) == inj['identidad'], ubic.name)
    dp = inj['destino_preexistente']
    try:
        dp_ok = (ident(dp['ruta']) == dp['identidad']
                 and sorted(os.listdir(dp['ruta'])) == ['MARCA_DESTINO.txt']
                 and sha_file(Path(dp['ruta']) / 'MARCA_DESTINO.txt') == dp['marca_sha256'])
    except OSError:
        dp_ok = False
    c('destino_preexistente_no_reemplazado', dp_ok, dp['ruta'])
    permitidas = {'AJENO_EXTERNO.txt', os.path.basename(dp['ruta']), ubic.name}
    c('sin_escritura_fuera', set(entradas) <= permitidas, entradas)
    c('sin_publicacion_exitosa', not [x for x in entradas if x == final.name
                                      or x.startswith(final.name + '_r')], entradas)

    # --- ABORT
    ab = leer_abort(ubic) or {}
    c('ABORT_6G1_valido_schema_3', ab.get('schema') == 'abort-6g1/3', ab.get('schema'))
    c('motivo', ab.get('motivo') == motivo_esp, ab.get('motivo'))
    c('resultados_validos_vacio', ab.get('resultados_validos') == [])
    c('directorio_acreditado', ab.get('directorio_acreditado') is True)
    inval = ab.get('salidas_invalidadas') or []
    wav_rel = sorted(os.path.relpath(w['ruta'], prov) for w in escr_inj)
    npy_rel = sorted(os.path.relpath(m['ruta'], prov) for m in inj['memmaps'])
    c('salidas_parciales_invalidadas', all(x in inval for x in wav_rel + npy_rel),
      'faltan %s' % [x for x in wav_rel + npy_rel if x not in inval])
    c('salidas_parciales_conservadas', all((ubic / x).is_file() for x in wav_rel + npy_rel))

    # --- cabeceras WAV y memmaps
    det_wav, wav_ok = {}, True
    for w in escr_inj:
        rel = os.path.relpath(w['ruta'], prov)
        frames = cerrados_por_ruta.get(w['ruta'], {}).get('frames')
        h = riff(ubic / rel) if (ubic / rel).is_file() else dict(ok=False, motivo='ausente')
        ok = (h.get('ok') and frames is not None
              and h['riff_size'] == h['tamano'] - 8
              and h['data_offset'] + h['data_size'] == h['tamano']
              and h['data_size'] == frames * h['block_align'])
        wav_ok &= bool(ok)
        det_wav[rel] = dict(h, frames_escritos=frames, ok=bool(ok))
    c('cabeceras_wav_finalizadas', wav_ok, {k: (v.get('data_size'), v.get('frames_escritos'),
                                                v.get('ok')) for k, v in det_wav.items()})
    mm_det, mm_ok2 = {}, True
    for m in inj['memmaps']:
        rel = os.path.relpath(m['ruta'], prov)
        try:
            sha, shape, dtype = sha_logico_npy(ubic / rel)
            ok = sha == m['sha_logico'] and shape == m['shape'] and dtype == m['dtype']
        except Exception as exc:
            ok, sha = False, repr(exc)
        mm_ok2 &= ok
        mm_det[rel] = ok
    c('memmaps_contenido_logico_intacto', mm_ok2, mm_det)

    # --- analysis.json / ajeno
    an = inj.get('analysis_sha256')
    c('analysis_json_intacto', (not (ubic / 'analysis.json').exists()) if an is None
      else (ubic / 'analysis.json').is_file() and sha_file(ubic / 'analysis.json') == an,
      'no existía en la inyección; el aborto no lo crea' if an is None else an)
    aj = ubic / 'AJENO_CV.txt'
    c('ajeno_intacto_y_conservado', aj.is_file() and sha_file(aj) == inj['ajeno_sha256']
      and 'AJENO_CV.txt' in (ab.get('conservados') or []))

    # --- estabilidad SHA y escritura tras el registro
    post = inventario(ubic)
    a_ent = fe['archivos']
    a_sal = dict(fs['archivos']) if fs else {}
    abort_sha = a_sal.pop('ABORT_6G1.json', None)
    a_fin = dict(ff['archivos']) if ff else {}
    c('sha_estable_registro', fs is not None and a_ent == a_sal and abort_sha is not None,
      'diferencias: %s' % sorted(k for k in set(a_ent) | set(a_sal) if a_ent.get(k) != a_sal.get(k)))
    c('sha_estable_fin_de_main', ff is not None and a_fin == dict(a_sal, **{'ABORT_6G1.json': abort_sha}),
      sorted(k for k in set(a_fin) | set(a_sal) if a_fin.get(k) != dict(a_sal, **{'ABORT_6G1.json': abort_sha}).get(k)))
    ref = dict(a_sal, **{'ABORT_6G1.json': abort_sha})
    c('sha_estable_tras_terminar_el_proceso', post == ref,
      sorted(k for k in set(post) | set(ref) if post.get(k) != ref.get(k)))
    c('ningun_archivo_eliminado', set(inj['archivos']) <= set(post),
      'faltan %s' % sorted(set(inj['archivos']) - set(post)))
    if ff is not None:
        esc_vivos = [d for d in ff['descriptores_salida_o_entradas'] if d['escritura'] is not False]
        if fallo != 'memmap':
            c('sin_descriptores_de_escritura_tras_registro', not esc_vivos and not ff['mapeos_bajo_salida'],
              '%s %s' % (esc_vivos, ff['mapeos_bajo_salida']))
        else:
            ret_rel = os.path.relpath(retenido, prov)
            c('sin_escritura_tras_registro_salvo_mapeo_retenido',
              all(d['destino'].endswith('/' + ret_rel) for d in esc_vivos)
              and all(m.endswith('/' + ret_rel) for m in ff['mapeos_bajo_salida']),
              '%s %s' % (esc_vivos, ff['mapeos_bajo_salida']))
    else:
        c('sin_descriptores_de_escritura_tras_registro', False, 'sin foto final')

    # --- documentación del cierre en engine_log.txt
    lg = (ubic / 'engine_log.txt').read_text(encoding='utf-8', errors='replace') \
        if (ubic / 'engine_log.txt').is_file() else ''
    if completo_esp:
        c('log_documenta_cierre_completo',
          '[6G.1-R/CR] cierre de recursos previo al aborto' in lg and 'completo=True' in lg)
    elif fallo == 'lector':
        c('log_documenta_error_de_cierre_del_lector',
          'completo=False' in lg and 'ERROR de cierre' in lg
          and 'inyeccion CR R5: fallo de E/S al cerrar el lector del Mix' in lg
          and ('lector ' + str(lector_fallido)) in lg, 'lector %s' % lector_fallido)
        c('resultado_del_aborto_traslado_bloqueado',
          'trasladado=False' in r['stdout'] and 'cierre de recursos incompleto' in r['stdout'],
          r['stdout'][-400:])
    else:
        c('log_documenta_error_de_cierre',
          'completo=False' in lg and 'ERROR de cierre' in lg and 'referencias activas' in lg
          and os.path.basename(retenido) in lg)
    extra = dict(secuencia=secuencia, wav=det_wav, memmaps=mm_det,
                 entrada_abortar=dict(escritores=fe['escritores'], memmaps=fe['memmaps'],
                                      lectores_abiertos=fe['lectores_abiertos'],
                                      descriptores=fe['descriptores_salida_o_entradas'],
                                      mapeos=fe['mapeos_bajo_salida']),
                 ubicacion_final=str(ubic))
    return ch, extra


def bateria(motores_dir, etiqueta):
    filas, detalle = [], {}
    for motor in MOTORES:
        for esc in ESCENARIOS:
            r = ejecutar(motores_dir, motor, esc, etiqueta)
            try:
                ch, extra = verificar(motor, esc, r)
            except Exception as exc:          # fallo del verificador = FAIL
                ch, extra = {'verificador': (False, repr(exc))}, {}
            ok = all(v[0] for v in ch.values())
            fallos = [k for k, v in ch.items() if not v[0]]
            detalle['%s/%s' % (motor, esc)] = dict(
                condicion=ESCENARIOS[esc][0], codigo=r['codigo'],
                codigo_esperado=ESCENARIOS[esc][1], argumentos=r['cmd'],
                comprobaciones={k: dict(ok=v[0], detalle=v[1]) for k, v in ch.items()},
                veredicto='PASS' if ok else 'FAIL', fallos=fallos, **extra,
                stdout_tail=r['stdout'][-1500:], stderr_tail=r['stderr'][-1500:])
            filas.append(dict(prueba=esc, motor=motor, condicion=ESCENARIOS[esc][0],
                              codigo_esperado=ESCENARIOS[esc][1], codigo=r['codigo'],
                              comprobaciones='%d/%d' % (sum(v[0] for v in ch.values()), len(ch)),
                              fallos=';'.join(fallos), veredicto='PASS' if ok else 'FAIL'))
            print('%-8s %-3s codigo=%-4s %s %s' % (motor, esc, r['codigo'],
                                                  'PASS' if ok else 'FAIL', ','.join(fallos)),
                  flush=True)
    return filas, detalle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default=None)
    ap.add_argument('--etiqueta-base', default='base')
    ap.add_argument('--json', default=str(EV / 'pruebas_cierre_recursos_6g1.json'))
    ap.add_argument('--csv', default=str(EV / 'matriz_cierre_recursos_6g1.csv'))
    a = ap.parse_args()
    res = dict(schema='pruebas-cierre-recursos-6g1/2', entorno=entorno(),
               motores_sha256={m: sha_file(MOT / n) for m, n in MOTORES.items()},
               modulo_sha256=sha_file(MOT / 'lectura_segura_6g1.py'),
               escenarios={k: dict(condicion=v[0], codigo_esperado=v[1], motivo=v[2],
                                   trasladado=v[3], cierre_completo=v[4])
                           for k, v in ESCENARIOS.items()},
               argumentos_motor='--mode full_processing --chunk-frames 16 '
                                '--write-all-candidates [--keep-masks en Hardened/EVO]')
    if a.base:
        bdir = Path(a.base).resolve()
        print('== diagnóstico sobre %s (%s)' % (bdir, a.etiqueta_base))
        fb, db = bateria(bdir, a.etiqueta_base)
        res['diagnostico_base'] = dict(
            etiqueta=a.etiqueta_base, carpeta=str(bdir),
            motores_sha256={m: sha_file(bdir / n) for m, n in MOTORES.items()},
            filas=fb, detalle=db,
            resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in fb), total=len(fb)))
    print('== motores corregidos (%s)' % MOT)
    filas, det = bateria(MOT, 'corregido')
    res.update(filas=filas, detalle=det,
               resumen=dict(pass_=sum(f['veredicto'] == 'PASS' for f in filas), total=len(filas)))
    EV.mkdir(parents=True, exist_ok=True)
    Path(a.json).write_text(
        json.dumps(res, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    base_idx = {(f['prueba'], f['motor']): f for f in res.get('diagnostico_base', {}).get('filas', [])}
    with open(a.csv, 'w', newline='', encoding='utf-8') as fh:
        cols = ['prueba', 'motor', 'condicion', 'codigo_esperado', 'codigo', 'comprobaciones',
                'fallos', 'veredicto', 'codigo_base', 'veredicto_base', 'fallos_base']
        wr = csv.DictWriter(fh, fieldnames=cols)
        wr.writeheader()
        for f in filas:
            b = base_idx.get((f['prueba'], f['motor']), {})
            wr.writerow(dict(f, codigo_base=b.get('codigo', ''), veredicto_base=b.get('veredicto', ''),
                             fallos_base=b.get('fallos', '')))
    print('RESUMEN corregido: %d/%d PASS' % (res['resumen']['pass_'], res['resumen']['total']))
    if 'diagnostico_base' in res:
        print('RESUMEN base (%s): %d/%d PASS' % (a.etiqueta_base, res['diagnostico_base']['resumen']['pass_'],
                                                res['diagnostico_base']['resumen']['total']))
    return 0 if res['resumen']['pass_'] == res['resumen']['total'] else 1


if __name__ == '__main__':
    sys.exit(main())
