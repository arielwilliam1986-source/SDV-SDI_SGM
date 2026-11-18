"""Inventario del intérprete que se usará; no instala paquetes."""
import argparse
import ctypes.util
import importlib
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'SwapTotal'):
            mem[key + '_bytes'] = int(value.split()[0]) * 1024
    versions = {}
    for mod in ('numpy', 'scipy', 'soundfile'):
        try:
            lib = importlib.import_module(mod)
            versions[mod] = lib.__version__
            if mod == 'soundfile':
                versions['libsndfile'] = lib.__libsndfile_version__
        except (ImportError, OSError) as e:
            versions[mod] = None
            versions[mod + '_error'] = repr(e)
    versions.setdefault('libsndfile', None)
    return dict(utc=datetime.now(timezone.utc).isoformat(), python=sys.version, executable=sys.executable,
                platform=platform.platform(), versions=versions, system_sndfile=ctypes.util.find_library('sndfile'),
                memory=mem, disk_free_bytes=shutil.disk_usage(ROOT).free,
                threads={k: os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT / 'environment.json')
    path = parser.parse_args().output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot(), indent=2) + '\n', encoding='utf-8')
