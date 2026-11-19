"""Utilidades comunes de la etapa 6F (rutas, motores, hashes, evidencia)."""
import hashlib
import importlib.util
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

for _k in ('OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'OMP_NUM_THREADS'):
    os.environ.setdefault(_k, '1')

import numpy as np
import scipy
import soundfile as sf

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
EV = HERE / 'evidence'
MOT = HERE / 'motores'
BASE = 'b72ce49ae787c72a1148bbec95db35dba460d279'
SR = 44100

MOTORES = {
    'Hardened': ('MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py', 'classic'),
    'EVO': ('MOTOR_SEP_SDV-SDI_EVO.py', 'classic'),
    'MQR': ('sdv_sdi_mqr_engine.py', 'mqr'),
}
REFS = {
    '6C': ROOT / 'ETAPA_6C_CORRECCION_EXPERIMENTAL' / 'motores',
    '6E': ROOT / 'ETAPA_6E_CORRECCION_ATRIBUCION_INTEGRIDAD' / 'motores',
    '6F': MOT,
}
ORIG = ROOT / 'Proyecto SDV-SDI_SGM'


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    with open(p, 'rb') as f:
        return sha_bytes(f.read())


def dump(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False, ensure_ascii=False,
                               default=_json_default) + '\n', encoding='utf-8')


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    return str(o)


def load_engine(path, tag=None):
    path = Path(path)
    sys.path.insert(0, str(path.parent))
    name = (tag or path.stem)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def engine_path(label, which='6F'):
    name, _ = MOTORES[label]
    return REFS[which] / name


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode().strip()


def entorno():
    return dict(platform=platform.platform(), python=sys.version,
                machine=platform.machine(), cpu_visible=os.cpu_count(),
                numpy=np.__version__, scipy=scipy.__version__,
                soundfile=sf.__version__, libsndfile=sf.__libsndfile_version__,
                threads='OPENBLAS/MKL/OMP=1')


class Cronometro:
    def __enter__(self):
        self.t0 = time.perf_counter()
        self.r0 = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return self

    def __exit__(self, *exc):
        self.seconds = time.perf_counter() - self.t0
        self.maxrss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        self.child_rss_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return False
