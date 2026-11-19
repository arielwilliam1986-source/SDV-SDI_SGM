"""Utilidades comunes 6G: rutas, motores, ejecución y medidas."""
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault('OMP_NUM_THREADS', '1')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('MKL_NUM_THREADS', '1')

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parent
EV = HERE / 'evidence'
MOT = HERE / 'motores'
SIX = ROOT / 'ETAPA_6F_CIERRE_CORRECTIVO' / 'motores'

MOTORES = {
    'Hardened': 'MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
    'EVO': 'MOTOR_SEP_SDV-SDI_EVO.py',
    'MQR': 'sdv_sdi_mqr_engine.py',
}
SINGLE_MODE = {'Hardened': 'single_pair', 'EVO': 'single_pair', 'MQR': 'single_file'}
MODOS = ('dry_run', 'analysis_only', None, 'full_processing')  # None -> modo de un solo par
SR = 44100


def sha_file(path):
    import hashlib
    m = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            m.update(b)
    return m.hexdigest()


def sha_bytes(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, ensure_ascii=False,
                                    sort_keys=False, default=str) + '\n',
                          encoding='utf-8')


def engine_path(label, version='6g'):
    if version == '6f':
        return SIX / MOTORES[label]
    return MOT / MOTORES[label]


def entorno():
    import numpy
    import scipy
    import soundfile
    return dict(python=sys.version.split()[0], numpy=numpy.__version__,
                scipy=scipy.__version__, soundfile=soundfile.__version__,
                libsndfile=soundfile.__libsndfile_version__,
                platform=sys.platform, machine=os.uname().machine,
                cpu_count=os.cpu_count(),
                ram_mb=round(os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2**20))


class Cronometro:
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t0
        ru = resource.getrusage(resource.RUSAGE_SELF)
        self.maxrss_kib = ru.ru_maxrss
        return False


def escribir_manifest(path, rutas):
    data = dict(
        mix_original=str(rutas['mix']),
        pairs=[dict(pair_id='P01', family='6G', variant='V01',
                    configuration='synthetic', source='synthetic',
                    vocal_path=str(rutas['vocal']), vocal_guide=str(rutas['vocal']),
                    instrumental_path=str(rutas['instrumental']),
                    instrumental_guide=str(rutas['instrumental']))])
    Path(path).write_text(json.dumps(data), encoding='utf-8')
    return path


def ejecutar(label, mix, work, mode, version='6g', extra=(), timeout=600):
    """Corre un motor en subprocess y devuelve artefactos observados."""
    import numpy as np
    import soundfile as sf
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    man = work / 'manifest.json'
    escribir_manifest(man, mix)
    out = work / 'out'
    cmd = [sys.executable, '-B', str(engine_path(label, version)),
           '--manifest', str(man), '--out', str(out), '--mode', mode, *extra]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(MOT),
                          timeout=timeout)
    seg = time.perf_counter() - t0
    reports = sorted(out.rglob('analysis.json'))
    wavs = sorted(out.rglob('*.wav'))
    report = json.loads(reports[0].read_text()) if len(reports) == 1 else {}
    pcm = {}
    shapes = {}
    for w in wavs:
        x, s = sf.read(w, dtype='float64', always_2d=True)
        pcm[w.name] = sha_bytes(x.astype('<f8').tobytes())
        shapes[w.name] = [int(x.shape[0]), int(x.shape[1]), int(s)]
    integ = {}
    files = sorted(out.rglob('input_integrity_6g.json'))
    if files:
        integ = json.loads(files[0].read_text())
    align = report.get('alignment_analysis') or report.get('alignment')
    first = align[0] if isinstance(align, list) and align else (align or {})
    return dict(exit=proc.returncode, seconds=round(seg, 3), wavs=len(wavs),
                wav_names=sorted(pcm), pcm=pcm, shapes=shapes,
                report=bool(report), report_obj=report,
                attribution=first.get('attribution') if isinstance(first, dict) else None,
                classification=first.get('classification') if isinstance(first, dict) else None,
                k=first.get('estimated_offset_samples') if isinstance(first, dict) else None,
                channel_lags=first.get('channel_lags') if isinstance(first, dict) else None,
                input_integrity_6g=integ,
                stdout_tail=(proc.stdout or '')[-1500:],
                stderr_tail=(proc.stderr or '')[-3000:])
