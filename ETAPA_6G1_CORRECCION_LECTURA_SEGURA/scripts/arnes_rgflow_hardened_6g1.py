#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ARNÉS DE PRUEBAS RG-FLOW-1..4 / MOTOR HARDENED SIN ADAPTACIÓN (6G.1).

Autorización Cris 22-11-2026: ejecución EXCLUSIVA de FLOW-1..4 sobre Hardened
sin adaptación, con fixtures sintéticos. NO implementa PDA-1/EA/E1/F1/G1 ni
modifica producción. La inyección de FLOW-2 es EN MEMORIA (import del módulo
real + monopatch del punto documentado RG-FLOW L1398: segundo sf.SoundFile en
modo escritura), sin alterar el fichero del motor en disco.

Uso:
  python -B scripts/arnes_rgflow_hardened_6g1.py --raiz /tmp/rgflow_h1 \
      --salida <evidence_dir> [--flujos 1,2,3,4] [--duracion 30]
"""
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
ETAPA = os.path.dirname(HERE)
MOTOR_H = os.path.join(ETAPA, 'motores',
                       'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py')
PY = sys.executable

SR = 44100
TS = lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def listado_relativo(raiz):
    """Inventario recursivo: rel, tipo, dev, ino, size (lstat, sin seguir)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(raiz, followlinks=False):
        for n in sorted(dirnames + filenames):
            p = os.path.join(dirpath, n)
            rel = os.path.relpath(p, raiz)
            try:
                st = os.lstat(p)
            except OSError:
                out.append(dict(rel=rel, tipo='inaccesible'))
                continue
            import stat as _s
            tipo = ('symlink' if _s.S_ISLNK(st.st_mode) else
                    'directorio' if _s.S_ISDIR(st.st_mode) else
                    'regular' if _s.S_ISREG(st.st_mode) else 'otro')
            item = dict(rel=rel, tipo=tipo, dev=st.st_dev, ino=st.st_ino,
                        size=st.st_size)
            if tipo == 'symlink':
                item['destino'] = os.readlink(p)
            out.append(item)
    return sorted(out, key=lambda x: x['rel'])


def fds_bajo(raiz):
    """Descriptores de ESTE proceso cuyo objetivo cae bajo `raiz`."""
    res = []
    for f in os.listdir('/proc/self/fd'):
        try:
            obj = os.readlink('/proc/self/fd/%s' % f)
            if raiz and (obj == raiz or obj.startswith(raiz + os.sep)):
                res.append(dict(fd=int(f), objetivo=obj))
        except OSError:
            pass
    return sorted(res, key=lambda x: x['fd'])


def gen_fixtures(fix_dir, duracion, n_pares=1):
    """Fixtures SINTÉTICOS deterministas (sin audio real): ruido blanco
    determinista por PRNG con semilla (autocorrelación tipo delta -> pico NCC
    único, sin rivales estructurales); mix = 0.5*(vocal+instrumental),
    estéreo PCM_16."""
    os.makedirs(fix_dir, exist_ok=True)
    n = int(SR * duracion)
    rs_v = np.random.RandomState(20261122)
    rs_i = np.random.RandomState(19480720)
    voc = 0.30 * rs_v.standard_normal(n)
    ins = 0.30 * rs_i.standard_normal(n)
    mix = 0.5 * (voc + ins)
    stereo = lambda x: np.column_stack([x, x]).astype('float32')
    fij = {}
    for nombre, datos in (('mix_sintetico.wav', stereo(mix)),
                          ('vocal.wav', stereo(voc)),
                          ('instrumental.wav', stereo(ins))):
        p = os.path.join(fix_dir, nombre)
        sf.write(p, datos, SR, subtype='PCM_16')
        fij[nombre] = dict(ruta=p, sha256=sha256(p), bytes=os.path.getsize(p),
                           segundos=duracion, sr=SR, canales=2, subtipo='PCM_16')
    man = dict(source_mix_file='mix_sintetico.wav', guide_pairs=[
        dict(pair_id='gp%02d' % i, vocal_guide='vocal.wav',
             instrumental_guide='instrumental.wav', family='SYNTH',
             variant='ARENA_6G1', configuration='standard')
        for i in range(1, n_pares + 1)], calibration_parameters={})
    pm = os.path.join(fix_dir, 'MANIFEST_RGFLOW.json')
    with open(pm, 'w', encoding='utf-8') as f:
        json.dump(man, f, indent=1)
    fij['MANIFEST_RGFLOW.json'] = dict(ruta=pm, sha256=sha256(pm),
                                       bytes=os.path.getsize(pm))
    return fij, pm


def lanzar_motor(cmd, cwd, stdout_path, stderr_path):
    fo = open(stdout_path, 'wb')
    fe = open(stderr_path, 'wb')
    return subprocess.Popen(cmd, cwd=cwd, stdout=fo, stderr=fe), fo, fe


def esperar_dir(padre, patron, timeout, poll=0.1, proc=None):
    fin = time.time() + timeout
    while time.time() < fin:
        if proc is not None and proc.poll() is not None:
            return None          # el motor terminó: no esperar más
        if os.path.isdir(padre):
            cand = [d for d in sorted(os.listdir(padre)) if d.endswith(patron)]
            for c in cand:
                p = os.path.join(padre, c)
                if os.path.isdir(p):
                    return p
        time.sleep(poll)
    return None


def log_tail(p, n=60):
    try:
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            return f.read().splitlines()[-n:]
    except OSError:
        return None


def filtrar_log(p, claves):
    try:
        with open(p, 'r', encoding='utf-8', errors='replace') as f:
            return [ln for ln in f if any(k in ln for k in claves)]
    except OSError:
        return None


def escribir(outdir, nombre, obj):
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, nombre)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
    print('  ->', p)
    return p


# ---------------------------------------------------------------------------
ATTACKER_SRC = r'''
import json, os, sys, time
modo, watch, objetivo, logp = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
delay = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
evento = dict(modo=modo, delay_s=delay, eventos=[], ts=time.time())
fin = time.time() + 600
hecho = False
while time.time() < fin and not hecho:
    if modo == 'intermedio':
        base = watch                      # .../user/base
        user = os.path.dirname(watch)     # .../user
        parciales = []
        if os.path.isdir(base):
            parciales = [d for d in os.listdir(base) if d.endswith('_partial')]
        if parciales:
            par = parciales[0]
            time.sleep(delay)             # swap temporizado respecto a la deteccion
            user_orig = user + '.orig'
            if not os.path.isdir(user_orig):
                os.rename(user, user_orig)
            os.makedirs(os.path.join(user, 'base', par), 0o700)
            evento['eventos'].append(dict(accion='sustitucion_intermedio',
                ts=time.time(), parcial=par, user_orig=user_orig,
                recreated=os.path.join(user, 'base', par)))
            hecho = True
    else:                                  # 'entrada_final'
        base = watch
        parciales = []
        if os.path.isdir(base):
            parciales = [d for d in os.listdir(base) if d.endswith('_partial')]
        if parciales:
            anal = os.path.join(base, parciales[0], 'analysis.json')
            if os.path.isfile(anal) and not os.path.islink(anal):
                st_pre = os.lstat(anal)
                time.sleep(delay)
                os.unlink(anal)
                os.symlink(objetivo, anal)
                evento['eventos'].append(dict(accion='sustitucion_entrada_final',
                    ts=time.time(), ino_original=st_pre.st_ino, symlink=objetivo))
                hecho = True
    time.sleep(0.05)
evento['ejecutado'] = hecho
with open(logp, 'w', encoding='utf-8') as f:
    json.dump(evento, f, indent=1)
'''


def flujo1(raiz, duracion, outdir):
    """FLOW-1 — éxito normal: EXIT_OK, artefactos, identidad, protocolo."""
    print('=== FLOW-1 ===', flush=True)
    d = os.path.join(raiz, 'f1')
    if os.path.isdir(d):
        shutil.rmtree(d)          # re-ejecución limpia del flujo
    fij, man = gen_fixtures(os.path.join(d, 'fixtures'), duracion)
    out = os.path.join(d, 'out')
    cmd = [PY, '-B', MOTOR_H, '--manifest', man, '--mode',
           'full_processing', '--out', out, '--allow-misaligned']
    t0 = time.time()
    pr, fo, fe = lanzar_motor(cmd, ETAPA, os.path.join(d, 'consola.txt'),
                              os.path.join(d, 'stderr.txt'))
    parcial = esperar_dir(out, '_partial', 120, proc=pr)
    id_parcial = None
    if parcial:
        st = os.lstat(parcial)
        id_parcial = dict(ruta=parcial, dev=st.st_dev, ino=st.st_ino)
    rc = pr.wait()
    fo.close(); fe.close()
    dur = round(time.time() - t0, 2)
    dirs = sorted(os.listdir(out)) if os.path.isdir(out) else []
    finales = [x for x in dirs if not x.endswith('_partial')]
    publicado = os.path.join(out, finales[0]) if finales else None
    id_pub = None
    if publicado:
        st = os.lstat(publicado)
        id_pub = dict(ruta=publicado, dev=st.st_dev, ino=st.st_ino)
    logp = os.path.join(publicado, 'engine_log.txt') if publicado else None
    artefactos_esperados = ['analysis.json', 'analysis.txt',
                            'input_integrity_6g.json', 'engine_log.txt',
                            'mix_sintetico SDV.wav', 'mix_sintetico SDI.wav']
    inv = listado_relativo(publicado) if publicado else []
    presentes = {a: any(x['rel'] == a and x.get('tipo') == 'regular'
                        for x in inv) for a in artefactos_esperados}
    ab = any(x['rel'] == 'ABORT_6G1.json' for x in inv)
    identidad_conservada = bool(id_parcial and id_pub
                                and (id_parcial['dev'], id_parcial['ino'])
                                == (id_pub['dev'], id_pub['ino']))
    exito = (rc == 0 and publicado is not None
             and all(presentes.values()) and not ab
             and identidad_conservada
             and not any(x['rel'] == 'masks' for x in inv))
    res = dict(flujos='FLOW-1', motor='Hardened sin adaptacion', ts=TS(),
               comando=cmd, config=dict(duracion_s=duracion, flags='--mode full_processing',
                                        keep_masks=False),
               returncode=rc, duracion_s=dur,
               dir_parcial=id_parcial, dir_publicado=id_pub,
               identidad_conservada=identidad_conservada,
               inventario_publicado=inv,
               artefactos_obligatorios=presentes,
               abort_en_publicado=ab, masks_en_publicado=any(
                   x['rel'] == 'masks' for x in inv),
               log_lineas_6g1=filtrar_log(logp, ['6G.1']) if logp else None,
               log_cola=log_tail(logp) if logp else None,
               consola_cola=log_tail(os.path.join(d, 'consola.txt'), 15))
    res['resultado'] = ('PASS' if exito else 'FAIL')
    res['criterio'] = ('EXIT_OK + todos los artefactos obligatorios regulares '
                       'en el publicado + identidad (dev,ino) conservada '
                       'parcial->publicado + sin ABORT_6G1.json + masks '
                       'eliminadas post-publicacion (comportamiento vigente)')
    res['clasificacion'] = 'EXPERIMENTAL_RESULT'
    res['alcance'] = ('caracterizacion del comportamiento VIGENTE; NO es una '
                      'afirmacion de seguridad ni valida adaptaciones')
    escribir(outdir, 'flow1_hardened.json', res)
    return res


def flujo2(raiz, duracion, outdir):
    """FLOW-2 — excepción tras varios recursos (inyección EN MEMORIA en el
    punto documentado: 2º sf.SoundFile EN MODO ESCRITURA, L1398)."""
    print('=== FLOW-2 ===', flush=True)
    import importlib.util
    d = os.path.join(raiz, 'f2')
    if os.path.isdir(d):
        shutil.rmtree(d)          # re-ejecución limpia del flujo
    fij, man = gen_fixtures(os.path.join(d, 'fixtures'), duracion)
    out = os.path.join(d, 'out')
    argv = ['--manifest', man, '--mode', 'full_processing', '--out', out,
            '--keep-masks', '--allow-misaligned']
    before = fds_bajo(out)
    sys.path.insert(0, os.path.dirname(MOTOR_H))   # hermanos del motor
    spec = importlib.util.spec_from_file_location(
        'hardened_rgflow2', MOTOR_H)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    orig_sf = M.sf.SoundFile
    llamadas_w = []

    def envolvente(*a, **k):
        modo = k.get('mode', 'r')
        if modo == 'w':
            llamadas_w.append(str(a[0] if a else k))
            if len(llamadas_w) == 2:
                raise RuntimeError(
                    'INYECTOR_FLOW2: excepcion controlada en el 2o '
                    'sf.SoundFile de escritura (punto documentado L1398)')
        return orig_sf(*a, **k)

    M.sf.SoundFile = envolvente
    t0 = time.time()
    try:
        code = M.main(argv)               # main devuelve el código EXIT
    finally:
        M.sf.SoundFile = orig_sf          # restauración inmediata
    dur = round(time.time() - t0, 2)
    dirs = sorted(os.listdir(out)) if os.path.isdir(out) else []
    abortado = os.path.join(out, next((x for x in dirs
                                       if x.endswith('_aborted')), ''))
    parcial = os.path.join(out, next((x for x in dirs
                                      if x.endswith('_partial')), ''))
    objetivo_dir = abortado or parcial
    inv = listado_relativo(objetivo_dir) if objetivo_dir else []
    abort_json = None
    for x in inv:
        if x['rel'] == 'ABORT_6G1.json':
            abort_json = json.load(open(os.path.join(objetivo_dir,
                                                     'ABORT_6G1.json'),
                                        encoding='utf-8'))
    logp = os.path.join(objetivo_dir, 'engine_log.txt') if objetivo_dir else None
    cierre = filtrar_log(logp, ['[6G.1-R/CR]']) if logp else None
    fatal = filtrar_log(logp, ['[FATAL]', '[ABORT]']) if logp else None
    publicacion = [x for x in dirs if not x.endswith(('_partial', '_aborted'))]
    residuos = fds_bajo(out)
    exito = (code == 2 and abort_json is not None
             and abort_json.get('schema') == 'abort-6g1/3'
             and abort_json.get('resultados_validos') == []
             and not publicacion and not residuos
             and bool(cierre))
    res = dict(flujos='FLOW-2', motor='Hardened sin adaptacion (inyeccion en memoria)',
               ts=TS(), argv=argv, config=dict(duracion_s=duracion,
                   keep_masks=True, punto_inyeccion='2o sf.SoundFile modo w (L1398), monopatch en memoria'),
               escrituras_soundfile_vistas=llamadas_w,
               returncode_inprocess=code, duracion_s=dur,
               dirs_en_out=dirs, dir_objetivo=objetivo_dir,
               inventario=inv, abort_6g1=abort_json,
               log_cierre_6g1=cierre, log_fatal=fatal,
               publicacion_indebida=publicacion,
               fds_residuales_proceso=residuos,
               fds_antes=before)
    res['resultado'] = ('PASS' if exito else 'FAIL' if code is not None
                        else 'UNKNOWN')
    res['criterio'] = ('EXIT_PROCESSING + ABORT_6G1.json (schema abort-6g1/3, '
                       'resultados_validos=[]) + cierre [6G.1-R/CR] en log + '
                       'sin publicacion + 0 descriptores residuales del '
                       'proceso bajo out; recursos adquiridos al inyectar: '
                       'engine_log.txt (Tee), masks/ y memmaps (--keep-masks) '
                       'y writer_sdv abierto')
    res['clasificacion'] = 'EXPERIMENTAL_RESULT'
    escribir(outdir, 'flow2_hardened.json', res)
    return res


def flujo3(raiz, duracion, outdir):
    """FLOW-3 — SIGINT tras detectar runners/memmaps abiertos (masks/*.npy +
    WAV del runner presentes). NO se amplía a SIGTERM/SIGKILL."""
    print('=== FLOW-3 ===', flush=True)
    d = os.path.join(raiz, 'f3')
    if os.path.isdir(d):
        shutil.rmtree(d)          # re-ejecución limpia del flujo
    fij, man = gen_fixtures(os.path.join(d, 'fixtures'), duracion)
    out = os.path.join(d, 'out')
    cmd = [PY, '-B', MOTOR_H, '--manifest', man, '--mode',
           'full_processing', '--out', out, '--keep-masks',
           '--allow-misaligned']
    pr, fo, fe = lanzar_motor(cmd, ETAPA, os.path.join(d, 'consola.txt'),
                              os.path.join(d, 'stderr.txt'))
    parcial = esperar_dir(out, '_partial', 120, proc=pr)
    disparo = None
    if parcial:
        fin = time.time() + 600
        while time.time() < fin:
            hay_masks = os.path.isdir(os.path.join(parcial, 'masks')) and \
                any(f.endswith('.npy') for f in
                    os.listdir(os.path.join(parcial, 'masks')))
            hay_wav = any(f.endswith(' SDV.wav') for f in
                          os.listdir(parcial))
            if hay_masks and hay_wav:
                time.sleep(1.5)          # margen: runners/writers abiertos
                os.kill(pr.pid, signal.SIGINT)
                disparo = dict(cuando='tras masks/*.npy y WAV del runner',
                               ts=TS())
                break
            if pr.poll() is not None:
                break
            time.sleep(0.1)
    rc = pr.wait()
    fo.close(); fe.close()
    dirs = sorted(os.listdir(out)) if os.path.isdir(out) else []
    abortado = os.path.join(out, next((x for x in dirs
                                       if x.endswith('_aborted')), ''))
    parcial_q = os.path.join(out, next((x for x in dirs
                                        if x.endswith('_partial')), ''))
    objetivo_dir = abortado or parcial_q
    inv = listado_relativo(objetivo_dir) if objetivo_dir else []
    abort_json = None
    for x in inv:
        if x['rel'] == 'ABORT_6G1.json':
            abort_json = json.load(open(os.path.join(objetivo_dir,
                                                     'ABORT_6G1.json'),
                                        encoding='utf-8'))
    logp = os.path.join(objetivo_dir, 'engine_log.txt') if objetivo_dir else None
    exito = (disparo is not None and rc == 130 and abort_json is not None
             and not [x for x in dirs
                      if not x.endswith(('_partial', '_aborted'))])
    res = dict(flujos='FLOW-3', motor='Hardened sin adaptacion', ts=TS(),
               comando=cmd, config=dict(duracion_s=duracion, keep_masks=True,
                   senal='SIGINT (unicamente; SIGTERM/SIGKILL fuera de alcance)'),
               disparo=disparo, returncode=rc,
               dirs_en_out=dirs, dir_objetivo=objetivo_dir,
               inventario=inv, abort_6g1=abort_json,
               log_fatal=filtrar_log(logp, ['[FATAL]', '[ABORT]',
                                            '[6G.1-R/CR]']) if logp else None,
               masks_conservadas=any(x['rel'].startswith('masks/')
                                     for x in inv) if inv else False)
    res['resultado'] = 'PASS' if exito else ('UNKNOWN' if disparo is None
                                             else 'FAIL')
    res['criterio'] = ('SIGINT en el punto documentado + EXIT_ABORTED(130) + '
                       'ABORT_6G1.json verificado + artefactos conservados '
                       'sin eliminacion (AI-E) + sin publicacion')
    res['clasificacion'] = 'EXPERIMENTAL_RESULT'
    escribir(outdir, 'flow3_hardened.json', res)
    return res


def _arbol(base_dir):
    """Inventario de un árbol de corrida (user/base o user.orig/base): dirs
    de primer nivel, published/aborted/partial y artefactos clave."""
    out = dict(existe=os.path.isdir(base_dir), niveles=[], analisis=None,
               engine_log=None, abort=None)
    if not out['existe']:
        return out
    out['niveles'] = sorted(os.listdir(base_dir))
    for d in out['niveles']:
        ruta_d = os.path.join(base_dir, d)
        a = os.path.join(ruta_d, 'analysis.json')
        if os.path.exists(a) or os.path.islink(a):
            out['analisis'] = dict(dir=d,
                tipo=('symlink' if os.path.islink(a) else 'regular'),
                destino=os.readlink(a) if os.path.islink(a) else None)
        e = os.path.join(ruta_d, 'engine_log.txt')
        if os.path.isfile(e):
            out['engine_log'] = dict(dir=d, bytes=os.path.getsize(e))
        ab = os.path.join(ruta_d, 'ABORT_6G1.json')
        if os.path.isfile(ab):
            try:
                out['abort'] = dict(dir=d, schema=json.load(
                    open(ab, encoding='utf-8')).get('schema'))
            except Exception:
                out['abort'] = dict(dir=d, schema='ILEGIBLE')
    return out


def flujo4b(raiz, duracion, d):
    """Caso (b) DETERMINISTA: sustitución de la ENTRADA FINAL analysis.json
    en la frontera de publicación (mismo objetivo C; inyección EN MEMORIA del
    arnés — mismo uid — en el límite publicar_dir_6g1; el motor NO se
    modifica)."""
    import importlib.util
    if os.path.isdir(d):
        shutil.rmtree(d)
    fij, man = gen_fixtures(os.path.join(d, 'fixtures'), duracion)
    user = os.path.join(d, 'user')
    base = os.path.join(user, 'base')
    os.makedirs(base, 0o700)
    obj = os.path.join(d, 'objetivo')
    os.makedirs(obj, 0o700)
    ruta_imp = os.path.join(obj, 'impostor.json')
    with open(ruta_imp, 'w') as f:
        f.write('{"impostor": true}\n')
    sys.path.insert(0, os.path.dirname(MOTOR_H))
    spec = importlib.util.spec_from_file_location('hardened_rgflow4b', MOTOR_H)
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    orig_pub = M._publicar_dir_6g1
    swap = dict(ejecutado=False)

    def pub_envuelto(origen, destino, max_intentos=64):
        anal = os.path.join(origen, 'analysis.json')
        if os.path.isfile(anal) and not os.path.islink(anal):
            st = os.lstat(anal)
            os.unlink(anal)
            os.symlink(ruta_imp, anal)
            swap.update(ejecutado=True, ts=time.time(),
                        ino_original=st.st_ino, destino_symlink=ruta_imp,
                        ventana='pre-publicacion (frontera publicar_dir_6g1)')
        return orig_pub(origen, destino, max_intentos=max_intentos)

    M._publicar_dir_6g1 = pub_envuelto
    t0 = time.time()
    try:
        code = M.main(['--manifest', man, '--mode', 'full_processing',
                       '--out', base, '--allow-misaligned'])
    finally:
        M._publicar_dir_6g1 = orig_pub
    dur = round(time.time() - t0, 2)
    dirs = sorted(os.listdir(base)) if os.path.isdir(base) else []
    final = next((x for x in dirs if not x.endswith(('_partial', '_aborted'))),
                 None)
    publicado = os.path.join(base, final) if final else None
    anal = None
    if publicado:
        ruta_a = os.path.join(publicado, 'analysis.json')
        if os.path.islink(ruta_a):
            anal = dict(tipo='symlink', destino=os.readlink(ruta_a),
                        apunta_al_impostor=os.readlink(ruta_a) == ruta_imp)
        elif os.path.isfile(ruta_a):
            anal = dict(tipo='regular')
    impostor = dict(sha256=sha256(ruta_imp),
                    contenido=open(ruta_imp, encoding='utf-8').read())
    inv = listado_relativo(publicado) if publicado else []
    res = dict(modo_ataque='entrada_final', mecanismo='inyeccion en memoria '
               'del arnes en la frontera de publicacion (mismo uid; motor sin '
               'modificar)', returncode=code, duracion_s=dur,
               dirs_en_base=dirs, publicado=publicado,
               inventario_publicado=inv,
               analisis_publicado=anal, sustitucion=swap, impostor=impostor,
               symlink_publicado=bool(anal and anal.get('tipo') == 'symlink'),
               exit_ok_con_symlink=bool(code == 0 and anal
                                        and anal.get('tipo') == 'symlink'),
               impostor_sin_alterar=impostor['contenido'].strip()
               == '{"impostor": true}',
               resultado='OBSERVADO (caracterizacion C: brecha de la entrada '
                         'final vigente; NO es un veredicto de seguridad)',
               clasificacion='EXPERIMENTAL_RESULT (caracterizacion)')
    escribir(d, 'flow4b_hardened.json', res)
    return res


def flujo4(raiz, duracion, outdir):
    """FLOW-4 — sustitución de entrada (CARACTERIZACIÓN del comportamiento
    vigente, sin presuponer detección): (a1) intermedio swap inmediato,
    (a2) intermedio swap a mitad de procesamiento (D1), (b) entrada final
    analysis.json (C)."""
    print('=== FLOW-4 ===', flush=True)
    r4 = {}
    att = os.path.join(raiz, 'atacante_rgflow.py')
    with open(att, 'w', encoding='utf-8') as f:
        f.write(ATTACKER_SRC)
    casos = [('a1_intermedio_inmediato', 'intermedio', 0.05),
             ('a2_intermedio_procesamiento', 'intermedio', 4.0),
             ('b_entrada_final', 'entrada_final', 0.05)]
    for nombre, modo, delay in casos:
        if nombre == 'b_entrada_final':
            continue                  # caso b: in-process determinista (abajo)
        d = os.path.join(raiz, 'f4_' + nombre)
        if os.path.isdir(d):
            shutil.rmtree(d)          # re-ejecución limpia del sub-caso
        fij, man = gen_fixtures(os.path.join(d, 'fixtures'), duracion)
        user = os.path.join(d, 'user')
        base = os.path.join(user, 'base')
        os.makedirs(base, 0o700)
        obj = os.path.join(d, 'objetivo')
        os.makedirs(obj, 0o700)
        with open(os.path.join(obj, 'impostor.json'), 'w') as f:
            f.write('{"impostor": true}\n')
        loga = os.path.join(d, 'atacante.json')
        pa = subprocess.Popen([PY, '-B', att, modo, base,
                               os.path.join(obj, 'impostor.json'), loga,
                               str(delay)])
        cmd = [PY, '-B', MOTOR_H, '--manifest', man, '--mode',
               'full_processing', '--out', base, '--allow-misaligned']
        pr, fo, fe = lanzar_motor(cmd, ETAPA,
                                  os.path.join(d, 'consola.txt'),
                                  os.path.join(d, 'stderr.txt'))
        rc = pr.wait()
        fo.close(); fe.close()
        pa.wait()
        ataq = json.load(open(loga, encoding='utf-8')) \
            if os.path.exists(loga) else dict(ejecutado=False)
        real = _arbol(os.path.join(user + '.orig', 'base')) \
            if os.path.isdir(user + '.orig') else dict(existe=False)
        atac = _arbol(base)
        # ¿dónde quedó el resultado final publicado (no _partial/_aborted)?
        publicado_en = None
        for etiqueta, arbol in (('user.orig', real), ('user', atac)):
            fins = [x for x in arbol.get('niveles', [])
                    if not x.endswith(('_partial', '_aborted'))]
            if arbol.get('existe') and fins:
                publicado_en = dict(arbol=etiqueta, dir=fins[0],
                                    analisis=arbol.get('analisis'),
                                    engine_log=arbol.get('engine_log'))
        impostor = dict(sha256=sha256(os.path.join(obj, 'impostor.json')),
                        contenido=open(os.path.join(obj, 'impostor.json'),
                                       encoding='utf-8').read())
        r4[nombre] = dict(modo_ataque=modo, delay_s=delay, returncode=rc,
                          atacante=ataq, arbol_real=real, arbol_atacante=atac,
                          publicado_en=publicado_en, impostor=impostor)
        det = False
        if modo == 'intermedio':
            det = bool(rc != 0)   # el motor interrumpió el flujo (caracterización)
            r4[nombre]['publicacion_fail_open'] = bool(
                rc == 0 and publicado_en and publicado_en['arbol'] == 'user')
            r4[nombre]['abort_escrito_en_algun_arbol'] = bool(
                real.get('abort') or atac.get('abort'))
            r4[nombre]['anclaje_h1'] = ('sin_ABORT_en_ningun_arbol (D1: '
                'identidad_distinta impide escribir en el impostor y el '
                'protocolo no localiza el real)'
                if not (real.get('abort') or atac.get('abort'))
                else 'ABORT_escrito')
        else:
            anal = (publicado_en or {}).get('analisis') or \
                atac.get('analisis') or real.get('analisis')
            r4[nombre]['analysis_json_estado'] = anal
            r4[nombre]['symlink_publicado'] = bool(
                anal and anal.get('tipo') == 'symlink')
            det = bool(rc != 0 or (anal and anal.get('tipo') == 'regular'))
        r4[nombre]['flujo_interrumpido_o_detectado'] = det
        r4[nombre]['clasificacion'] = \
            'EXPERIMENTAL_RESULT (caracterizacion, no veredicto de seguridad)'
    r4['b_entrada_final'] = flujo4b(raiz, duracion, os.path.join(raiz, 'f4_b_entrada_final'))
    consolidado = dict(
        flujos='FLOW-4 (a1/a2 intermedio D1 con timings; b entrada final C)',
        motor='Hardened sin adaptacion', ts=TS(), casos=r4,
        resultado=('OBSERVADO (caracterizacion): documenta el comportamiento '
                   'VIGENTE ante sustituciones de misma uid; NO es un '
                   'veredicto de seguridad ni presupone deteccion'),
        criterio=('registro fiel de: deteccion/interrupcion por el motor, '
                  'continuidad del flujo, arbol que recibe los artefactos, '
                  'ABORT_6G1.json presente/ausente en cada arbol, estado del '
                  'analysis.json publicado e integridad del impostor'),
        clasificacion='EXPERIMENTAL_RESULT')
    consolidado['resultado_por_caso'] = {
        k: dict(returncode=v['returncode'],
                ejecutado=v.get('atacante', v.get('sustitucion', {})).get('ejecutado'),
                deteccion_o_interrupcion=v.get('flujo_interrumpido_o_detectado'),
                publicado_en=v.get('publicado_en', v.get('publicado')),
                abort=(v.get('arbol_real', {}).get('abort') or
                       v.get('arbol_atacante', {}).get('abort')))
        for k, v in r4.items()}
    escribir(outdir, 'flow4_hardened.json', consolidado)
    return consolidado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--raiz', default='/tmp/rgflow_h1')
    ap.add_argument('--salida', required=True)
    ap.add_argument('--flujos', default='1,2,3,4')
    ap.add_argument('--duracion', type=float, default=30.0)
    ap.add_argument('--duracion3', type=float, default=None,
                    help='duracion del fixture de FLOW-3 (ventana SIGINT)')
    a = ap.parse_args()
    res = {}
    orden = {'1': flujo1, '2': flujo2, '3': flujo3, '4': flujo4}
    for k in a.flujos.split(','):
        k = k.strip()
        if k == '3':
            res['FLOW-3'] = flujo3(a.raiz, a.duracion3 or (a.duracion * 3),
                                   a.salida)
        else:
            res['FLOW-' + k] = orden[k](a.raiz, a.duracion, a.salida)
    con = dict(schema='rgflow-hardened-14/1', generado=TS(),
               autorizacion='Cris 22-11-2026: solo FLOW-1..4 Hardened sin '
                            'adaptacion, fixtures sinteticos',
               resultados={k: v['resultado'] for k, v in res.items()})
    escribir(a.salida, 'consolidado_rgflow_hardened14.json', con)
    print('RESULTADOS:', con['resultados'])


if __name__ == '__main__':
    main()
