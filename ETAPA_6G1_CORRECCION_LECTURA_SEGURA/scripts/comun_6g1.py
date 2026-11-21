"""Utilidades comunes de la Etapa 6G.1: rutas, ejecución, PCM y sustitución."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
MOT = HERE / 'motores'
G6 = ROOT / 'ETAPA_6G_SOPORTE_FLAC_MIX' / 'motores'
FIX = HERE / 'fixtures'
EV = HERE / 'evidence'

MOTORES = {
    'Hardened': 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
    'EVO': 'MOTOR_SEP_SDV-SDI_EVO.py',
    'MQR': 'sdv_sdi_mqr_engine.py',
}
MODO_UN_PAR = {'Hardened': 'single_pair', 'EVO': 'single_pair', 'MQR': 'single_file'}
SR = 44100


def sha_file(path):
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            m.update(b)
    return m.hexdigest()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                                     sort_keys=False, default=str) + '\n',
                          encoding='utf-8')


def engine_path(label, version='6g1'):
    if version == '6g':
        return G6 / MOTORES[label]
    return MOT / MOTORES[label]


def entorno():
    import numpy
    import scipy
    import soundfile
    return dict(python=sys.version.split()[0], numpy=numpy.__version__,
                scipy=scipy.__version__, soundfile=soundfile.__version__,
                libsndfile=soundfile.__libsndfile_version__,
                platform=sys.platform, machine=os.uname().machine,
                cpu_count=os.cpu_count())


def escribir_manifest(path, mix, vocal=None, instrumental=None, extra=None):
    if not isinstance(mix, dict):
        mix = dict(mix=str(mix))
    vocal = vocal or mix.get('vocal') or (FIX / 'vocal.wav')
    instrumental = instrumental or mix.get('instrumental') or (FIX / 'instrumental.wav')
    data = dict(
        mix_original=str(mix['mix']),
        pairs=[dict(pair_id='P01', family='6G1', variant='V01',
                    configuration='synthetic', source='synthetic',
                    vocal_path=str(vocal), vocal_guide=str(vocal),
                    instrumental_path=str(instrumental),
                    instrumental_guide=str(instrumental))])
    if extra:
        data.update(extra)
    Path(path).write_text(json.dumps(data), encoding='utf-8')
    return path


def _pcm_de_wav(path):
    import numpy as np
    import soundfile as sf
    x, sr = sf.read(str(path), dtype='float64', always_2d=True)
    return dict(name=Path(path).name, frames=int(x.shape[0]),
                channels=int(x.shape[1]), sr=int(sr),
                finite=bool(np.all(np.isfinite(x))),
                peak=float(np.max(np.abs(x))) if x.size else 0.0,
                rms=float(np.sqrt(np.mean(x ** 2))) if x.size else 0.0,
                pcm_sha256=sha_bytes(x.astype('<f8').tobytes()),
                file_sha256=sha_file(path), bytes=Path(path).stat().st_size)


def recolectar(out):
    """Salidas reales de la corrida: WAV válidos, informe e integridad."""
    out = Path(out)
    wavs = sorted(out.rglob('*.wav'))
    pcm = []
    for w in wavs:
        try:
            pcm.append(_pcm_de_wav(w))
        except Exception as exc:                     # WAV presente pero ilegible
            pcm.append(dict(name=w.name, error=str(exc),
                            file_sha256=sha_file(w),
                            bytes=w.stat().st_size))
    informes = sorted(out.rglob('analysis.json'))
    report = json.loads(informes[0].read_text()) if len(informes) == 1 else {}
    integ = sorted(out.rglob('input_integrity_6g.json'))
    abort = sorted(out.rglob('ABORT_6G1.json'))
    run_dirs = sorted({w.parent for w in wavs} | {i.parent for i in informes})
    return dict(wavs=[w.name for w in wavs], pcm=pcm,
                wavs_validos=sum(1 for p in pcm if 'error' not in p),
                report=report, report_leido=bool(report),
                integrity=json.loads(integ[0].read_text()) if integ else {},
                abort=json.loads(abort[0].read_text()) if abort else {},
                run_dirs=[str(d) for d in run_dirs])


def ejecutar(label, mix, work, mode=None, version='6g1', extra=(),
             timeout=1800, sustituir=None):
    """Corre un motor y devuelve artefactos observados.

    `sustituir` = dict(destino=Path, fuente=Path, patron=str, etapa=str): un
    hilo vigila `engine_log.txt` y, al aparecer el patrón, reemplaza la ruta del
    Mix por otro archivo (mismo contenedor) registrando la etapa observada.
    """
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    man = work / 'manifest.json'
    escribir_manifest(man, mix)  # acepta Path o dict(mix=..., vocal=..., instrumental=...)
    out = work / 'out'
    if out.exists():
        shutil.rmtree(out)
    cmd = [sys.executable, '-B', str(engine_path(label, version)),
           '--manifest', str(man), '--out', str(out), '--mode', mode or MODO_UN_PAR[label],
           *extra]
    evento = {}
    if sustituir:
        # pre-copia del sustituto: en el disparo sólo se hace un rename atómico
        shutil.copyfile(str(sustituir['fuente']), str(sustituir['destino']) + '.sustituto')
    proc = subprocess.Popen(cmd, cwd=str(MOT), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    if sustituir:
        evento = _vigilar_y_sustituir(out, proc, **sustituir)
    salida = proc.communicate(timeout=timeout)[0] or ''
    datos = recolectar(out)
    datos.update(exit=proc.returncode, stdout_tail=salida[-4000:],
                 sustitucion=evento, out=str(out))
    return datos


def _vigilar_y_sustituir(out, proc, destino, fuente, patron, etapa, sembrar=(),
                         retraso=None):
    destino, fuente = Path(destino), Path(fuente)
    evento = dict(patron=patron, etapa=etapa, aplicada=False)
    t0 = time.perf_counter()
    vistos = ''
    while proc.poll() is None:
        if retraso is not None:
            if time.perf_counter() - t0 >= float(retraso):
                logs = sorted(Path(out).glob('*/engine_log.txt')) if Path(out).exists() else []
                sembrados = []
                for nombre in sembrar:
                    if logs:
                        (logs[0].parent / nombre).write_text(
                            'archivo ajeno a la corrida 6G.1\n', encoding='utf-8')
                        sembrados.append(nombre)
                os.replace(str(destino) + '.sustituto', str(destino))
                evento.update(aplicada=True,
                              segundos_desde_inicio=round(time.perf_counter() - t0, 3),
                              sha_destino_nuevo=sha_file(destino), sembrados=sembrados,
                              disparo=f'retraso {retraso}s')
                break
            time.sleep(0.002)
            continue
        logs = sorted(Path(out).glob('*/engine_log.txt')) if Path(out).exists() else []
        if logs:
            try:
                texto = logs[0].read_text(errors='replace')
            except OSError:
                texto = ''
            if len(texto) > len(vistos):
                nuevo = texto[len(vistos):]
                inicio = max(0, len(vistos) - 200)
                vistos = texto
                if re.search(patron, texto[inicio:]):
                    sembrados = []
                    for nombre in sembrar:
                        objetivo = logs[0].parent / nombre
                        objetivo.write_text('archivo ajeno a la corrida 6G.1\n',
                                            encoding='utf-8')
                        sembrados.append(nombre)
                    os.replace(str(destino) + '.sustituto', str(destino))
                    evento.update(aplicada=True,
                                  segundos_desde_inicio=round(time.perf_counter() - t0, 3),
                                  sha_destino_nuevo=sha_file(destino),
                                  log_previo=nuevo.strip().splitlines()[-3:],
                                  sembrados=sembrados)
                    break
        time.sleep(0.002)
    sustituto = Path(str(destino) + '.sustituto')
    if sustituto.exists():
        sustituto.unlink()
    if not evento.get('aplicada'):
        evento['motivo_no_aplicada'] = 'el patrón no apareció antes del fin del proceso'
    return evento


def copia_segura(origen, destino):
    """Copia binaria verificada (se usa para los sustitutos y las copias 6G)."""
    shutil.copyfile(str(origen), str(destino))
    if sha_file(origen) != sha_file(destino):
        raise RuntimeError(f'copia no idéntica: {origen} -> {destino}')
    return destino


CSV_COLUMNAS = ('prueba', 'motor', 'contenedor', 'escenario', 'veredicto',
                'detalle', 'salida', 'pcm', 'ruta_sha256')
