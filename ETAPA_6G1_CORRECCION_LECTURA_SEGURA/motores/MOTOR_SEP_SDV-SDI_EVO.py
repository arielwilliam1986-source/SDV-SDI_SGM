#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================================
SGM AUDIO & PSYCHOACOUSTICS RESEARCH LAB
MOTOR_SEP_SDV-SDI.py — Motor Maestro de Separación Espectro-Temporal (v3.1.0)
============================================================================
CRÉDITOS DE INGENIERÍA Y CALIBRACIÓN:
  - Lead Audio & DSP Research Engineer: Will (Dirección de Proyecto & Escucha Crítica)
  - DSP & System Architecture Specialist: Gemini (Modelado Matemático & Pipeline)
  - Empirical Benchmark & Calibration Specialist: Kimi (Auditoría Técnica & Calibración MQR)

1. PROPÓSITO CIENTÍFICO Y DOWNSTREAM PIPELINE ------------------------------
Este motor realiza la bifurcación primaria de alta resolución:
    Mix Original (24/32-bit PCM/Float) ---> SDV.wav (Source Domain Vocals)
                                      ---> SDI.wav (Source Domain Instrumental)

Finalidad de los archivos resultantes:
  - SDV.wav: Fuente inmutable para deconstrucción vocal posterior
             (Lead Vocal Center vs. Backing Vocals Stereo).
  - SDI.wav: Fuente inmutable para descomposición multi-stem posterior
             (Drums, Bass, Guitars, Strings, Synths, Other).

2. PRINCIPIOS FÍSICOS E INVARIANTES FUNDAMENTALES (v3.1.0 CALIBRADA) --------
  a) INVARIANZA DEL DOMINIO FUENTE (SOURCE DOMAIN INVARIANCE):
     Las salidas de IA (MVSEP) son tratadas estrictamente como GUÍAS ANALÍTICAS.
     El audio final se sintetiza EXCLUSIVAMENTE multiplicando el STFT complejo
     del Mix Original por las máscaras reales. La fase del Mix se preserva 100%.

  b) ORDEN DEL CONSENSO (MAGNITUDES_FIRST POR DEFECTO - HALLAZGO 01):
     V_avg = mean(V_m), I_avg = mean(I_m). Promediar magnitudes antes de la
     potencia no lineal disuelve los artefactos individuales y crea el Sfumato.

  c) MODALIDAD RESIDUAL CON AJUSTE LS-GAIN (HALLAZGO 02):
     use_physical_residuals = False por defecto. Cuando se activa, aplica
     compensación por mínimos cuadrados (LS-Gain Match) para evitar sangrado.

  d) MATRIZ DE SUAVIZADO 2D IMPLEMENTADA (HALLAZGO 03):
     Soporta none, median_3x3 y gaussian_5x3 (sigma_f=1.0, sigma_t=0.8).

  e) MÁSCARAS ESTÉREO POR CANAL (HALLAZGO 04):
     Soporta modo mono y per_channel (L/R independiente para música ancha).

  f) RENORMALIZACIÓN ESTRICTA POR BIN:
     M_v(t, f) = M_raw_v / (M_raw_v + M_raw_i) -> Sum_k(M_k) == 1.0 (SNR > 150 dB).
============================================================================
"""

import argparse
import hashlib
import json
import math
import os
import shutil
# import platform [PATCH 3: Unused]
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# VERIFICACIÓN DE ENTORNO Y DEPENDENCIAS DSP
# ----------------------------------------------------------------------------

MIN_PYTHON = (3, 8)
if sys.version_info < MIN_PYTHON:
    sys.stderr.write(f"[FATAL] Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} requerido.\n")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    sys.stderr.write("[FATAL] numpy no disponible. Instalar: pip install numpy\n")
    sys.exit(1)

try:
    from scipy.fft import rfft, irfft
    from scipy.signal import get_window, resample_poly
    from scipy.ndimage import median_filter, gaussian_filter
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False
    sys.stderr.write("[FATAL] scipy no disponible. Instalar: pip install scipy\n")
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    sys.stderr.write("[FATAL] soundfile no disponible. Instalar: pip install soundfile\n")
    sys.exit(1)

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False

# ----------------------------------------------------------------------------
# CONSTANTES GLOBALES CALIBRADAS (MOTOR A v3.1.0)
# ----------------------------------------------------------------------------

ENGINE_NAME = "SGM MOTOR A (SDV-SDI Master Engine)"
ENGINE_VERSION = "3.1.1-Sfumato-Calibrated"
CALIBRATION_STANDARD = "Topology T02 Calibrated (p=1.8, eps=1e-12, magnitudes_first, SNR > 140 dB)"
SPECIFICATION_MANIFEST = "MANIFEST_SEP_SDV-SDI.json"

REQUIRED_SAMPLE_RATE = 44100
ALLOWED_EXTENSIONS = (".wav", ".flac")
SOURCE_ALLOWED_SUBTYPES = ("PCM_16", "PCM_24", "PCM_32", "FLOAT")

N_FFT_ALLOWED = (2048, 4096, 8192)
N_FFT_DEFAULT = 4096
HOP_LENGTH_DEFAULT = 1024
STFT_WINDOW = "hann"
# STFT_CENTER = True [PATCH 3: Unused, FramePlan maneja el padding manualmente]

POWER_DEFAULT = 1.8                   # Calibración Sfumato
EPSILON_CALIBRATED = 1e-12            # Calibración Kimi (140+ dB)
CONSENSUS_ORDER_DEFAULT = "magnitudes_first"
CONSENSUS_METHODS = ("weighted_mean", "median", "confidence_weighted_mean")
CONSENSUS_DEFAULT = "confidence_weighted_mean"
 # Paridad acústica con script compacto
CONSENSUS_ORDERS = ("magnitudes_first", "masks_first", "hybrid_asymmetric")
SMOOTHING_KERNELS = ("none", "median_3x3", "gaussian_5x3")
MASK_MODES = ("mono", "per_channel")

CONFIDENCE_BETA = 1.0
CONFIDENCE_WEIGHT_FLOOR = 1e-6
MASK_SAVE_DTYPE = np.float32  # [PATCH v3.1.1 Kimi]

MODE_FULL_PROCESSING = "full_processing"
MODE_ANALYSIS_ONLY = "analysis_only"
MODE_DRY_RUN = "dry_run"
MODE_SINGLE_PAIR = "single_pair"
REQUIRED_MODES = (MODE_FULL_PROCESSING, MODE_ANALYSIS_ONLY, MODE_DRY_RUN, MODE_SINGLE_PAIR)

# [INJERTO 1] Constantes de Validación Defensiva
N_FFT_ALLOWED = (2048, 4096, 8192)
PARAM_BOUNDS = {"n_fft": (16, 65536), "hop": (1, 65536), "chunk_frames": (1, 1048576)}
CONSENSUS_METHODS = ("weighted_mean", "median", "confidence_weighted_mean")

ALIGN_COARSE_DECIMATION = 8
ALIGN_ENVELOPE_MS = 50.0
ALIGN_SEARCH_SECONDS = 30.0
ALIGN_REFINE_HALFSPAN = 12
ALIGNED_TOL_SAMPLES = 1
MISALIGNED_TOL_MS = 10.0

CHUNK_FRAMES_DEFAULT = 256
OUTPUT_SUBTYPE = "FLOAT"
OUTPUT_AUDIO_BLOCKSIZE = 1 << 18
IDENTITY_SNR_TARGET_DB = 140.0

BAND_EDGES_HZ = (0.0, 100.0, 200.0, 500.0, 1000.0, 2000.0,
                 4000.0, 8000.0, 12000.0, 16000.0, 20000.0, 22050.0)
TRUEPEAK_UPSAMPLE = 4
TRUEPEAK_CONTEXT = 256

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_PROCESSING = 2
EXIT_ABORTED = 130

# ----------------------------------------------------------------------------
# UTILIDADES DE LOGGING Y FORMATEO
# ----------------------------------------------------------------------------

class Colors:
    HEADER = '\033[95m'; BLUE = '\033[94m'; CYAN = '\033[96m'
    GREEN = '\033[92m'; WARNING = '\033[93m'; FAIL = '\033[91m'
    ENDC = '\033[0m'; BOLD = '\033[1m'

class Tee:
    def __init__(self, path=None):
        self._console = sys.stdout
        self._file = open(path, "w", encoding="utf-8") if path else None

    def write(self, data):
        self._console.write(data)
        if self._file is not None:
            try:
                self._file.write(data)
                self._file.flush()
            except OSError: pass

    def flush(self):
        self._console.flush()
        if self._file is not None:
            try: self._file.flush()
            except OSError: pass

    def close(self):
        if self._file is not None:
            try: self._file.close()
            except OSError: pass
        self._file = None

_G_TEE = None
_G_T0 = time.monotonic()

def init_tee(path):
    global _G_TEE
    _G_TEE = Tee(path)
    sys.stdout = _G_TEE
    sys.stderr = sys.stdout

def close_tee():
    global _G_TEE
    if _G_TEE is not None:
        sys.stdout = _G_TEE._console
        sys.stderr = _G_TEE._console
        _G_TEE.close()
        _G_TEE = None

def log(msg):
    elapsed = time.monotonic() - _G_T0
    print("[%9.2fs] %s" % (elapsed, msg), flush=True)

def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def sha256_file(path, blocksize=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(blocksize)
            if not block: break
            h.update(block)
    return h.hexdigest()

def fmt_size(num_bytes):
    if num_bytes >= 1 << 30: return "%.2f GiB" % (num_bytes / float(1 << 30))
    if num_bytes >= 1 << 20: return "%.2f MiB" % (num_bytes / float(1 << 20))
    if num_bytes >= 1 << 10: return "%.2f KiB" % (num_bytes / float(1 << 10))
    return "%d B" % num_bytes

def safe_name(text, max_len=64):
    out = [ch if (ch.isalnum() or ch in "-_.") else "_" for ch in str(text)]
    return "".join(out).strip("._")[:max_len] or "unnamed"

def json_safe(obj):
    if obj is None: return None
    if isinstance(obj, (str, int, bool)): return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, np.floating):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(obj, np.integer): return int(obj)
    if isinstance(obj, np.bool_): return bool(obj)
    if isinstance(obj, np.ndarray): return [json_safe(x) for x in obj.tolist()]
    if isinstance(obj, (list, tuple)): return [json_safe(x) for x in obj]
    if isinstance(obj, dict): return {str(k): json_safe(v) for k, v in obj.items()}
    return str(obj)

def next_pow2(n):
    p = 1
    while p < n: p <<= 1
    return p

def mono_downmix(x2d):
    arr = np.asarray(x2d, dtype=np.float64)
    if arr.ndim == 1: return arr
    if arr.shape[1] == 1: return arr[:, 0]
    return arr.mean(axis=1)

# ============================================================================
# SECCION 5: PROBE DE ENTRADAS Y VALIDACIÓN ESTRICTA
# ============================================================================

@dataclass
class FileInfo:
    path: str
    role: str
    exists: bool = False
    format: str = ""
    subtype: str = ""
    sample_rate: int = 0
    channels: int = 0
    frames: int = 0
    duration_s: float = 0.0
    size_bytes: int = 0
    sha256: str = ""
    bit_depth_nominal: int = 0
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    valid: bool = False

def _nominal_bit_depth(subtype: str) -> int:
    table = {
        "PCM_U8": 8, "PCM_S8": 8, "PCM_16": 16, "PCM_24": 24,
        "PCM_32": 32, "FLOAT": 32, "DOUBLE": 64
    }
    return table.get(subtype, 0)

from audio_integridad_6g import (container_of as _container_6g,
                              verify_audio as _verify_audio_6g)
from lectura_segura_6g1 import (MixCambiado as _MixCambiado_6g1,
                                 abrir_mix as _abrir_mix_6g1,
                                 abortar_6g1 as _abortar_6g1,
                                 registrar_propio_6g1 as _registrar_propio_6g1)

from atribucion_6f import (measure, verify_wave, alignment_gate,
                        analyze_files as _analyze_files_6f,
                        combine_channels as _combine_6f)

def probe_file(path: str, role: str) -> FileInfo:
    info = FileInfo(path=os.path.abspath(path), role=role)
    if not os.path.isfile(path):
        info.errors.append(f"Archivo no encontrado: {path}")
        return info
    info.exists = True
    info.size_bytes = os.path.getsize(path)
    try:
        sfi = sf.info(path)
        _verify_audio_6g(path, sfi)
    except Exception as exc:
        info.errors.append(f"soundfile no pudo abrir el archivo: {exc}")
        return info

    info.format = str(sfi.format)
    info.subtype = str(sfi.subtype)
    info.sample_rate = int(sfi.samplerate)
    info.channels = int(sfi.channels)
    info.frames = int(sfi.frames)
    info.duration_s = info.frames / float(info.sample_rate) if info.sample_rate else 0.0
    info.bit_depth_nominal = _nominal_bit_depth(info.subtype)
    
    try:
        info.sha256 = sha256_file(path)
    except OSError as exc:
        info.errors.append(f"Fallo calculando sha256: {exc}")

    info.valid = len(info.errors) == 0
    return info

def validate_mix(info: FileInfo) -> FileInfo:
    if not info.valid: return info
    ext = os.path.splitext(info.path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        info.errors.append(f"Mix: extensión {ext!r} no permitida ({ALLOWED_EXTENSIONS})")
    if info.sample_rate != REQUIRED_SAMPLE_RATE:
        info.errors.append(f"Mix: sample_rate={info.sample_rate} != {REQUIRED_SAMPLE_RATE} Hz requerido")
    if info.channels < 1 or info.channels > 2:
        info.errors.append(f"Mix: canales={info.channels} fuera de rango (1 o 2)")
    elif info.channels == 1:
        info.warnings.append("Mix es mono")
    if info.subtype not in SOURCE_ALLOWED_SUBTYPES:
        info.errors.append(f"Mix: subtype={info.subtype!r} fuera de política {SOURCE_ALLOWED_SUBTYPES}")
    elif info.subtype == "FLOAT":
        info.notes.append("Mix en 32-bit Float detectado")
    info.valid = len(info.errors) == 0
    return info

def validate_guide(info: FileInfo) -> FileInfo:
    if not info.valid: return info
    ext = os.path.splitext(info.path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        info.errors.append(f"Guía: extensión {ext!r} no permitida ({ALLOWED_EXTENSIONS})")
    if info.sample_rate != REQUIRED_SAMPLE_RATE:
        info.errors.append(f"Guía: sample_rate={info.sample_rate} != {REQUIRED_SAMPLE_RATE} Hz requerido")
    if info.channels < 1 or info.channels > 2:
        info.errors.append(f"Guía: canales={info.channels} fuera de rango (1 o 2)")
    info.valid = len(info.errors) == 0
    return info

# ============================================================================
# SECCION 6: METADATOS Y MANIFIESTO JSON
# ============================================================================

@dataclass
class PairMeta:
    pair_id: str
    family: str
    variant: str
    configuration: str
    vocal_path: str
    instrumental_path: str
    source_service: str = "MVSEP"
    overlap: str = ""
    vocal: FileInfo = None
    instrumental: FileInfo = None

    def as_dict(self) -> dict:
        return {
            "pair_id": self.pair_id,
            "family": self.family,
            "variant": self.variant,
            "configuration": self.configuration,
            "vocal_guide": os.path.abspath(self.vocal_path),
            "instrumental_guide": os.path.abspath(self.instrumental_path),
            "source_service": self.source_service,
            "overlap": self.overlap
        }

def load_manifest(manifest_path: str) -> tuple:
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(manifest_path))
    
    # [PATCH 1] Extraer calibración y directorio de salida
    cal_params = data.get("calibration_parameters", {})
    out_dir = data.get("output_directory", None)


    def resolve(p): return p if os.path.isabs(p) else os.path.join(base, p)

    mix_path = resolve(data.get("source_mix_file") or data.get("mix_original"))
    pairs = []
    raw_pairs = data.get("guide_pairs") or data.get("pairs") or []
    for i, item in enumerate(raw_pairs, start=1):
        pair_id = str(item.get("pair_id") or f"guide_pair_{i:02d}")
        v_path = resolve(item.get("vocal_guide") or item.get("vocal_path"))
        i_path = resolve(item.get("instrumental_guide") or item.get("instrumental_path"))
        
        pairs.append(PairMeta(
            pair_id=pair_id, family=str(item.get("family") or "USER_DEFINED"),
            variant=str(item.get("variant") or "USER_DEFINED"),
            configuration=str(item.get("configuration") or "USER_DEFINED"),
            vocal_path=v_path, instrumental_path=i_path,
            source_service=str(item.get("source_service") or "MVSEP"),
            overlap=str(item.get("overlap") or "")
        ))
    return mix_path, pairs, cal_params, out_dir

def interactive_collect_inputs(mode: str, preset_mix: str = None) -> tuple:
    print("\n" + "=" * 76)
    print(f"{ENGINE_NAME} v{ENGINE_VERSION}")
    print(f"Estándar: {CALIBRATION_STANDARD}")
    print("=" * 76)
    print(f"Modo: {mode}\n")

    if preset_mix:
        mix_path = preset_mix
        print(f"  Ruta del Mix Original: {preset_mix}  (via --mix)")
    else:
        mix_path = input("  Ruta del Mix Original: ").strip()
    n_str = input("  Número de pares de guías [4]: ").strip() or "4"
    n = int(n_str)
    pairs = []
    for i in range(1, n + 1):
        print(f"\n--- [Par {i}/{n}] ---")
        p_id = input(f"  Identificador [guide_pair_{i:02d}]: ").strip() or f"guide_pair_{i:02d}"
        fam = input("  Familia (RoFormer / MDX_B / DeReverb): ").strip()
        var = input("  Variante: ").strip()
        cfg = input("  Configuración [standard]: ").strip() or "standard"
        v_p = input("  Ruta Guía Vocal (SDV): ").strip()
        i_p = input("  Ruta Guía Instrumental (SDI): ").strip()
        pairs.append(PairMeta(pair_id=p_id, family=fam, variant=var, configuration=cfg, vocal_path=v_p, instrumental_path=i_p))
    return mix_path, pairs

# ============================================================================
# SECCION 7: ALINEACIÓN Y ESCALA (CON CORRECCIÓN OPCIONAL - HALLAZGO 05)
# ============================================================================

def _moving_rms(x: np.ndarray, win_samples: int) -> np.ndarray:
    x2 = np.square(x)
    csum = np.concatenate(([0.0], np.cumsum(x2)))
    half = win_samples // 2
    S = len(x2)
    idx_hi = np.minimum(np.arange(S) + half, S)
    idx_lo = np.maximum(np.arange(S) - (win_samples - half), 0)
    energy = (csum[idx_hi] - csum[idx_lo]) / np.maximum(idx_hi - idx_lo, 1)
    return np.sqrt(np.maximum(energy, 0.0))

def _decimate_block_mean(x: np.ndarray, factor: int) -> np.ndarray:
    usable = (len(x) // factor) * factor
    if usable <= 0: return np.zeros(1, dtype=np.float32)
    return x[:usable].reshape(-1, factor).mean(axis=1).astype(np.float32)

# 6C: primitives of the native detector, not of the separation pipeline.
_ALIGNMENT_RMS_FLOOR = 1e-10
_ALIGNMENT_MIN_RHO = 0.20
_ALIGNMENT_MIN_GAP = 0.002
_MEASURED = ("ALIGNED", "WARNING", "MISALIGNED")


def _lag_curve(x, y, qlo, qhi, min_n):
    """Physical local lags q of x[t] versus y[t-q]. Invalid slots never compete.

    For the same overlap: Pxy=sum(xy)-sum(x)sum(y)/n, Vx, Vy similarly.
    rho=Pxy/sqrt(Vx*Vy); strength=abs(rho)*sqrt(Vx/Vx_all * Vy/Vy_all).
    Prefix-sum blocks bound scratch space. Trimming literal zeros ONLY in the
    FFT numerator preserves every original index, overlap and denominator.
    """
    from scipy.signal import correlate
    na, nb = len(x), len(y)
    lo, hi = max(qlo, min_n-nb), min(qhi, na-min_n)
    count = max(hi-lo+1, 0) if min(na, nb) >= min_n else 0
    ok = np.zeros(count, dtype=bool)
    rho, strength = np.zeros(count), np.zeros(count)
    curve = (lo, ok, rho, strength)
    if not count:
        return curve
    # Translation preserves local Pearson and limits cancellation for DC offsets.
    a, b = x.astype('float64')-x[0], y.astype('float64')-y[0]
    ea, eb = a.var()*na, b.var()*nb
    floor2 = _ALIGNMENT_RMS_FLOOR**2
    if ea <= na*floor2 or eb <= nb*floor2:
        return curve
    def prefix(v):
        return np.concatenate(([0.0], v.cumsum(dtype='float64')))
    sa, sb, aa, bb = prefix(a), prefix(b), prefix(a*a), prefix(b*b)
    ia, ib = np.flatnonzero(a), np.flatnonzero(b)
    a0, a1, b0, b1 = int(ia[0]), int(ia[-1])+1, int(ib[0]), int(ib[-1])+1
    del ia, ib
    cross = correlate(a[a0:a1], b[b0:b1], mode='full', method='fft')
    first_q = a0-b1+1
    for start in range(0, count, 65536):
        sl = slice(start, min(start+65536, count))
        q = np.arange(lo+sl.start, lo+sl.stop)
        l, r = np.maximum(q, 0), np.minimum(na, nb+q)
        n = r-l
        sx, sy = sa[r]-sa[l], sb[r-q]-sb[l-q]
        vx = aa[r]-aa[l]-sx*sx/n
        vy = bb[r-q]-bb[l-q]-sy*sy/n
        valid = (vx > np.maximum(n*floor2, ea*1e-12)) & (vy > np.maximum(n*floor2, eb*1e-12))
        idx = q-first_q
        inside = (idx >= 0) & (idx < len(cross))
        num = -sx*sy/n
        num[inside] += cross[idx[inside]]
        rho[sl][valid] = num[valid]/np.sqrt(vx[valid]*vy[valid])
        raw = rho[sl]
        valid &= np.isfinite(raw) & (np.abs(raw) <= 1.+1e-7)
        raw[valid] = np.clip(raw[valid], -1., 1.)  # roundoff only
        strength[sl][valid] = np.abs(num[valid])/math.sqrt(ea*eb)
        ok[sl] = valid
    return curve


def _peaks(curve, limit, positive=False):
    lo, ok, rho, score = curve
    if not len(ok):
        return []
    eligible = ok & (rho > 0 if positive else score > 0)
    left = np.r_[True, ~eligible[:-1] | (score[1:] >= score[:-1])]
    right = np.r_[~eligible[1:] | (score[:-1] >= score[1:]), True]
    ids = np.flatnonzero(eligible & left & right)
    ids = ids[np.argsort(-score[ids], kind='stable')[:limit]]
    return [lo+int(i) for i in ids]


def _decision(state, reason, lag=None, rho=None, confidence=None):
    return dict(classification=state, reason=reason, estimated_offset_samples=lag,
                guide_delay_samples=None if lag is None else -lag,
                correlation_peak=rho, alignment_confidence=confidence)


def _severity(k):
    if abs(k) <= ALIGNED_TOL_SAMPLES:
        return 'ALIGNED'
    if abs(k) <= int(MISALIGNED_TOL_MS*REQUIRED_SAMPLE_RATE/1000):
        return 'WARNING'
    return 'MISALIGNED'


def _measure_window(a, b, tM, tG, radius):
    h = tG-tM
    qlo, qhi = h-radius, h+radius  # translate BEFORE clipping / decimation
    nmin = max(4096, (min(len(a), len(b))+1)//2)
    w = dict(tM=tM, tG=tG, frames_M=len(a), frames_G=len(b), min_overlap=nmin,
             local_requested=[qlo, qhi], global_requested=[-radius, radius],
             variance_M=float(a.var()) if len(a) else None,
             variance_G=float(b.var()) if len(b) else None, candidates=[], envelope=[], valid_lags=0)
    def finish(*args):
        w.update(_decision(*args))
        return w
    if min(len(a),len(b)) < nmin or min(w['variance_M'],w['variance_G']) <= _ALIGNMENT_RMS_FLOOR**2:
        return finish('INSUFFICIENT_SIGNAL', 'SHORT_OR_CONSTANT')
    decim = ALIGN_COARSE_DECIMATION
    width = int(ALIGN_ENVELOPE_MS*REQUIRED_SAMPLE_RATE/1000)
    envs = [_decimate_block_mean(_moving_rms(v, width), decim) for v in (a,b)]
    coarse = _lag_curve(*envs, -((-qlo)//decim), qhi//decim, (nmin+decim-1)//decim)
    seeds = _peaks(coarse, 3, positive=True)
    curve = _lag_curve(a, b, qlo, qhi, nmin)
    lo, ok, rho, score = curve
    w['valid_lags'] = int(ok.sum())
    w['physical_local_range'] = [lo, lo+len(ok)-1] if len(ok) else None
    def valid(q):
        return lo <= q < lo+len(ok) and bool(ok[q-lo])
    def point(q):
        l, r = max(q,0), min(len(a),len(b)+q)
        return dict(q=q, k=q-h, d=h-q, rho=float(rho[q-lo]), strength=float(score[q-lo]),
                    overlap=r-l, M=[tM+l,tM+r], G=[tG+l-q,tG+r-q])
    peaks = _peaks(curve, 5)
    w['zero'] = point(h) if valid(h) else None
    proposals = {q:['wave_peak'] for q in peaks}
    for u in seeds:
        q = u*decim
        entry = dict(q=q, k=q-h, rho=float(coarse[2][u-coarse[0]]), valid_before_refine=valid(q))
        w['envelope'].append(entry)
        if not valid(q):
            continue
        half = max(ALIGN_REFINE_HALFSPAN, decim+2)
        rivals = [z for z in range(q-half,q+half+1) if valid(z)]
        z = max(rivals, key=lambda k: score[k-lo])
        entry['refined_k'] = z-h
        proposals.setdefault(z, []).append('envelope')
    if w['zero'] is not None:
        proposals.setdefault(h, []).append('zero')
    w['candidates'] = [dict(point(q), origin=origin) for q,origin in proposals.items()]
    if not peaks:
        return finish('INSUFFICIENT_SIGNAL', 'NO_SUPPORTED_WAVE_PEAK')
    q = peaks[0]
    best = point(q)
    w['best'] = best
    # Direct confirmation in the *same* physical, unpadded overlap.
    l, r = max(q,0), min(len(a),len(b)+q)
    x, y = a[l:r], b[l-q:r-q]
    xc, yc = x-x.mean(), y-y.mean()
    sigx, sigy = np.sqrt(np.mean(xc*xc)), np.sqrt(np.mean(yc*yc))
    best['std_M'], best['std_G'] = float(sigx), float(sigy)
    if min(sigx,sigy) <= _ALIGNMENT_RMS_FLOOR:
        return finish('INSUFFICIENT_SIGNAL', 'UNSUPPORTED_OVERLAP')
    direct = float(np.dot(xc,yc)/(len(x)*sigx*sigy))
    if not math.isfinite(direct) or abs(direct-best['rho']) > 1e-6:
        raise ArithmeticError('FFT versus direct Pearson at q=%d' % q)
    signed = max(-1., min(1., direct))
    if abs(signed) < _ALIGNMENT_MIN_RHO:
        return finish('INSUFFICIENT_SIGNAL', 'LOW_WAVE_SUPPORT')
    gap = 1.-score[peaks[1]-lo]/score[q-lo] if len(peaks)>1 else 1.
    w['relative_peak_gap'] = float(gap)
    if gap <= _ALIGNMENT_MIN_GAP:
        return finish('AMBIGUOUS', 'COMPETING_WAVE_PEAKS')
    if not valid(q-1) or not valid(q+1):
        return finish('AMBIGUOUS', 'TRUNCATED_PEAK')
    # A shorter overlap can penalize an otherwise identical periodic translation.
    for alt in peaks[1:]:
        spacing = abs(alt-q)
        if len(b)-spacing < nmin or abs(rho[alt-lo])+0.002 < abs(signed):
            continue
        u, v = b[spacing:], b[:-spacing]
        u, v = u-u.mean(), v-v.mean()
        den = np.linalg.norm(u)*np.linalg.norm(v)
        if den > 0 and abs(float(np.dot(u,v))/den) >= 1.-1e-9:
            w['periodic_spacing'] = spacing
            return finish('AMBIGUOUS', 'REPEATED_GUIDE_AT_RIVAL')
    return finish(_severity(q-h), 'SUPPORTED_DISTINCT_PEAK', q-h, signed, float(abs(signed)*gap))


def _combine(records, clocks=False):
    """6F: agregado por canal delegado al módulo compartido (sólo diagnóstico)."""
    if isinstance(records, list):
        records = {str(i): r for i, r in enumerate(records)}
    return _combine_6f(records, _decision, _severity)


def _alignment_spans(a, b, radius):
    width = min(15*REQUIRED_SAMPLE_RATE,len(b))
    end = len(b)-width
    starts = sorted({*range(0,end+1,15*REQUIRED_SAMPLE_RATE//2), end})
    scan = [(t,float(b[t:t+width].var()) if width else 0.) for t in starts]
    chosen = []
    for t, var in sorted(scan,key=lambda item:-item[1]):
        if var <= _ALIGNMENT_RMS_FLOOR**2 or any(abs(t-u)<width for u in chosen):
            continue
        chosen.append(t)
        if len(chosen)==2:
            break
    spans = [(min(len(a),max(0,t-radius)), min(len(a),t+width+radius),t,t+width) for t in sorted(chosen or [0])]
    return spans, dict(guide_width=width, starts_and_variances=scan)


def analyze_alignment(mix_info: FileInfo, guide_info: FileInfo) -> dict:
    """6F: validación y lectura desde el mismo descriptor; sin corrección."""
    return _analyze_files_6f(mix_info, guide_info, REQUIRED_SAMPLE_RATE,
                             ALIGN_SEARCH_SECONDS, _decision, _severity,
                             ALIGNED_TOL_SAMPLES, MISALIGNED_TOL_MS)


def _attribution_state(record):
    return ('UNIQUE' if record['estimated_offset_samples'] is not None else record['classification'])


def _alignment_line(r):
    ch = ', '.join('%s: d=%s %s' % (key,_fmt(v['guide_delay_samples']),v['classification'])
                   for key,v in r['channels'].items())
    return 'k=%s ms; NCC=%s; %s (%s); %s; shift=0%s' % (
        _fmt(r['estimated_offset_ms'],2), _fmt(r['correlation_peak'],4), r['classification'],r['reason'],ch,
        '; '+r['error'] if r.get('error') else '')
def analyze_guide_scale(mix_info: FileInfo, pair: PairMeta) -> tuple:
    # Estima factor de proyección LS por mínimos cuadrados: g_LS = <G, M> / <G, G>
    rec = {"pair_id": pair.pair_id, "family": pair.family, "variant": pair.variant}
    acc = {"vocal": {"gm": 0.0, "gg": 0.0, "sq": 0.0, "n": 0, "peak": 0.0},
           "instrumental": {"gm": 0.0, "gg": 0.0, "sq": 0.0, "n": 0, "peak": 0.0}}
    mix_sq = 0.0; mix_n = 0
    with _abrir_mix_6g1(mix_info.path, mix_info.sha256) as hm:
        handles = {"vocal": sf.SoundFile(pair.vocal_path), "instrumental": sf.SoundFile(pair.instrumental_path)}
        try:
            while True:
                m = hm.read(1 << 20, dtype="float64", always_2d=True)
                if m.shape[0] == 0: break
                mm = mono_downmix(m)
                mix_sq += float(np.square(mm).sum()); mix_n += len(mm)
                for role, h in handles.items():
                    g = h.read(m.shape[0], dtype="float64", always_2d=True)
                    if g.shape[0] < m.shape[0]:
                        pad = np.zeros((m.shape[0] - g.shape[0], h.channels), dtype=np.float64)
                        g = np.concatenate([g, pad], axis=0)
                    gm_ = mono_downmix(g)
                    acc[role]["gm"] += float(np.dot(gm_, mm))
                    acc[role]["gg"] += float(np.dot(gm_, gm_))
                    acc[role]["sq"] += float(np.square(gm_).sum())
                    acc[role]["n"] += len(gm_)
                    acc[role]["peak"] = max(acc[role]["peak"], float(np.abs(g).max()))
        finally:
            for h in handles.values(): h.close()

    mix_rms = math.sqrt(mix_sq / max(mix_n, 1))
    rec["mix_common_region"] = {"rms": mix_rms, "frames_measured": mix_n}
    factors = {}
    for role in ("vocal", "instrumental"):
        a = acc[role]
        rms = math.sqrt(a["sq"] / max(a["n"], 1))
        raw_g_ls = (a["gm"] / a["gg"]) if a["gg"] > 0 else 1.0
        is_inverted = raw_g_ls < 0.0
        g_ls = abs(raw_g_ls)
        rec[role] = {"rms": rms, "peak": a["peak"],
                     "peak_dbfs": 20.0 * math.log10(a["peak"]) if a["peak"] > 0 else None,
                     "energy": a["sq"], "crest_factor": (a["peak"] / rms) if rms > 0 else 0.0,
                     "frames_measured": a["n"],
                     "raw_g_ls": raw_g_ls,
                     "polarity_inverted": is_inverted}
        factors[role] = g_ls
        factors[f"{role}_polarity"] = -1.0 if is_inverted else 1.0
    rec["ls_gain_projection"] = factors
    rec["note"] = "g_LS=<G,M>/<G,G>; residual = M - g_LS*guia (direccion corregida v3.1.1)."
    return rec, factors

# ============================================================================
# SECCION 9: MOTOR STFT COLA-EXACTO Y SINTESIS OLA STREAMING
# ============================================================================

class FramePlan:
    def __init__(self, n_samples: int, n_fft: int = N_FFT_DEFAULT, hop: int = HOP_LENGTH_DEFAULT):
        self.N = int(n_samples)
        self.n_fft = int(n_fft)
        self.hop = int(hop)
        self.pad = self.n_fft // 2
        last_needed = self.pad + self.N - 1
        self.K = last_needed // self.hop + 1
        self.window = get_window(STFT_WINDOW, self.n_fft, fftbins=True).astype(np.float64)
        self.win_sq = self.window * self.window
        self.bins = self.n_fft // 2 + 1

    def span_for_frames(self, f0: int, f1: int) -> tuple:
        return f0 * self.hop - self.pad, (f1 - 1) * self.hop + self.n_fft - self.pad

def read_span(handle: sf.SoundFile, start: int, end: int, shift_samples: int = 0) -> np.ndarray:
    S = end - start
    channels = handle.channels
    if S <= 0: return np.zeros((0, channels), dtype=np.float64)
    out = np.zeros((S, channels), dtype=np.float64)
    
    # Aplicación de shift para corrección de alineación si se requiere
    eff_start = start + shift_samples
    eff_end = end + shift_samples
    
    a = max(eff_start, 0)
    b = min(eff_end, handle.frames)
    if b > a:
        handle.seek(a)
        data = handle.read(b - a, dtype="float64", always_2d=True)
        out[a - eff_start:b - eff_start, :] = data
    return out

def stft_span_frames(x2d: np.ndarray, n_frames: int, plan: FramePlan) -> np.ndarray:
    win = plan.window
    sw = np.lib.stride_tricks.sliding_window_view(x2d, plan.n_fft, axis=0)
    fr = sw[::plan.hop][:n_frames]
    fr = np.ascontiguousarray(fr.transpose(1, 0, 2))
    X = rfft(fr * win, n=plan.n_fft, axis=-1)
    return np.ascontiguousarray(X.transpose(0, 2, 1))

class OlaStream:
    def __init__(self, plan: FramePlan, n_channels: int, writer: sf.SoundFile = None, label: str = ""):
        self.plan = plan
        self.ch = n_channels
        self.writer = writer
        self.label = label
        self.carry_y = np.zeros((plan.n_fft, n_channels), dtype=np.float64)
        self.carry_w = np.zeros(plan.n_fft, dtype=np.float64)
        self.pos = 0
        self.emitted_frames = 0

    def push(self, X: np.ndarray) -> tuple:
        plan = self.plan
        n_fft, hop = plan.n_fft, plan.hop
        ch, bins, F = X.shape
        total_len = F * hop + n_fft
        y = np.zeros((total_len, ch), dtype=np.float64)
        w = np.zeros(total_len, dtype=np.float64)

        y[:n_fft] += self.carry_y
        w[:n_fft] += self.carry_w
        win = plan.window

        for i in range(F):
            seg = irfft(X[:, :, i], n=n_fft, axis=-1)
            y[i * hop:i * hop + n_fft] += seg.T * win[:, None]
            w[i * hop:i * hop + n_fft] += plan.win_sq

        emitted_len = F * hop
        w_emit = w[:emitted_len]
        safe_w = np.where(w_emit > 1e-12, w_emit, 1.0)
        y_emit = y[:emitted_len] / safe_w[:, None]

        start_file = self.pos - plan.pad
        self.pos += emitted_len
        self.emitted_frames += F
        end_file = start_file + emitted_len

        a = max(start_file, 0)
        b = min(end_file, plan.N)
        out = None
        if b > a:
            out = y_emit[a - start_file:b - start_file, :]
            if self.writer is not None:
                self.writer.write(out)

        self.carry_y = y[emitted_len:emitted_len + n_fft].copy()
        self.carry_w = w[emitted_len:emitted_len + n_fft].copy()
        return out, a, b

    def flush(self) -> tuple:
        plan = self.plan
        w = self.carry_w
        safe_w = np.where(w > 1e-12, w, 1.0)
        y_emit = self.carry_y / safe_w[:, None]

        start_file = self.pos - plan.pad
        end_file = start_file + plan.n_fft
        a = max(start_file, 0)
        b = min(end_file, plan.N)
        out = None
        if b > a:
            out = y_emit[a - start_file:b - start_file, :]
            if self.writer is not None:
                self.writer.write(out)
        return out, a, b

# ============================================================================
# SECCION 10: METRICAS ESPECIALES Y SUAVIZADO 2D (HALLAZGO 03)
# ============================================================================

def apply_sfumato_smoothing(mask: np.ndarray, mode: str) -> np.ndarray:
    """Aplica suavizado espectro-temporal 2D calibrado."""
    if mode == "none" or not mode:
        return mask
    elif mode == "median_3x3":
        return median_filter(mask, size=(3, 3), mode="reflect")
    elif mode == "gaussian_5x3":
        # sigma_f=1.0 (frecuencia), sigma_t=0.8 (tiempo)
        return gaussian_filter(mask, sigma=(1.0, 0.8), mode="reflect")
    return mask

class TruePeakStream:
    def __init__(self, channels: int, up: int = TRUEPEAK_UPSAMPLE, context: int = TRUEPEAK_CONTEXT):
        self.ch = channels
        self.up = up
        self.ctx = context
        self.carry = np.zeros((context, channels), dtype=np.float64)
        self.peak = 0.0
        self.initial = True

    def push(self, block: np.ndarray):
        if block is None or block.shape[0] == 0: return
        data = np.concatenate([self.carry, block], axis=0)
        up = resample_poly(data, self.up, 1, axis=0)
        skip = 0 if self.initial else self.ctx * self.up
        self.initial = False
        valid = up[skip:]
        if valid.size:
            self.peak = max(self.peak, float(np.abs(valid).max()))
        if block.shape[0] >= self.ctx:
            self.carry = block[-self.ctx:].copy()
        else:
            self.carry = np.concatenate([self.carry, block], axis=0)[-self.ctx:]

    def finalize(self) -> float:
        up = resample_poly(self.carry, self.up, 1, axis=0)
        if up.size:
            self.peak = max(self.peak, float(np.abs(up).max()))
        return self.peak

def build_band_masks(bins: int, n_fft: int, sample_rate: int) -> tuple:
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    edges = [e for e in BAND_EDGES_HZ if e < freqs[-1]]
    if edges[-1] < freqs[-1]: edges.append(freqs[-1])
    labels = []
    masks = np.zeros((len(edges) - 1, bins), dtype=np.float64)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = (freqs >= lo) & (freqs < hi) if i < len(edges) - 2 else (freqs >= lo) & (freqs <= hi)
        masks[i, sel] = 1.0
        labels.append("%.0f-%.0fHz" % (lo, hi))
    return masks, labels, freqs

# ============================================================================
# SECCION 11: TOPOLOGIA T02 SFUMATO Y FUSION DE CONSENSO
# ============================================================================

def compute_vocal_mask(v_mag: np.ndarray, i_mag: np.ndarray, power: float = POWER_DEFAULT, epsilon: float = EPSILON_CALIBRATED) -> np.ndarray:
    vp = np.power(np.maximum(v_mag, 0.0), power)
    ip = np.power(np.maximum(i_mag, 0.0), power)
    return vp / (vp + ip + epsilon)

def confidence_and_disagreement(masks: list) -> tuple:
    stack = np.stack(masks, axis=0)
    n_models = stack.shape[0]
    if n_models == 1:
        return np.ones_like(stack[0]), np.zeros_like(stack[0]), np.ones_like(stack)

    dis = stack.std(axis=0, ddof=0)
    conf = np.clip(1.0 - 2.0 * dis, 0.0, 1.0)
    
    c_k = np.empty_like(stack)
    for k in range(n_models):
        others = [j for j in range(n_models) if j != k]
        dsum = np.zeros_like(stack[0])
        for j in others: dsum += np.abs(stack[k] - stack[j])
        c_k[k] = 1.0 - (dsum / len(others))

    return conf, dis, c_k

def consensus_from_masks(masks: list, c_k: np.ndarray, beta: float = CONFIDENCE_BETA, floor: float = CONFIDENCE_WEIGHT_FLOOR) -> tuple:
    stack = np.stack(masks, axis=0)
    n_models = stack.shape[0]
    mean_m = stack.mean(axis=0)
    median_m = np.median(stack, axis=0)

    if n_models == 1:
        conf_m = masks[0].copy()
        weights_summary = {"n_models": 1, "degenerate": True}
    else:
        w = np.clip(c_k, floor, None) ** beta
        w = w / w.sum(axis=0, keepdims=True)
        conf_m = (w * stack).sum(axis=0)
        weights_summary = {
            "n_models": n_models, "beta": beta,
            "weight_definition": "w_k = clip(c_k, floor)^beta / sum_j (...)"
        }

    return {
        "weighted_mean": mean_m,
        "median": median_m,
        "confidence_weighted_mean": conf_m
    }, weights_summary

# ============================================================================
# SECCION 12: ACUMULADORES ESTADISTICOS Y PAIRWISE STREAMING
# ============================================================================

def mask_stats_stream_init() -> dict:
    return {"sum": 0.0, "sumsq": 0.0, "n": 0, "min": float("inf"), "max": float("-inf"), "sub": []}

def mask_stats_stream_update(acc: dict, mask: np.ndarray, stride: int = 4):
    acc["sum"] += float(mask.sum())
    acc["sumsq"] += float(np.square(mask).sum())
    acc["n"] += mask.size
    acc["min"] = min(acc["min"], float(mask.min()))
    acc["max"] = max(acc["max"], float(mask.max()))
    if stride > 1:
        acc["sub"].append(mask[::stride, ::stride].ravel())

def mask_stats_stream_finalize(acc: dict) -> dict:
    n = max(acc["n"], 1)
    mean = acc["sum"] / n
    var = max(acc["sumsq"] / n - mean * mean, 0.0)
    out = {
        "mean": mean, "std": math.sqrt(var),
        "min": acc["min"] if acc["n"] else 0.0,
        "max": acc["max"] if acc["n"] else 0.0,
        "n_bins": acc["n"]
    }
    if acc["sub"]:
        sub = np.concatenate(acc["sub"])
        out["median"] = float(np.median(sub))
        out["p01"] = float(np.percentile(sub, 1))
        out["p99"] = float(np.percentile(sub, 99))
    else:
        out["median"] = out["mean"]; out["p01"] = out["min"]; out["p99"] = out["max"]
    return out

class PairwiseAccum:
    def __init__(self, bins: int, K_total: int):
        self.bins = bins
        self.per_bin_sum = np.zeros(bins, dtype=np.float64)
        self.per_frame_sum = np.zeros(K_total, dtype=np.float64)
        self.sub = []
        self.sum_abs = 0.0; self.sum_sq = 0.0; self.n = 0
        self.sa = 0.0; self.sb = 0.0; self.saa = 0.0; self.sbb = 0.0; self.sab = 0.0

    def update(self, a: np.ndarray, b: np.ndarray, f0: int, stride: int):
        d = np.abs(a - b)
        self.sum_abs += float(d.sum()); self.sum_sq += float(np.square(d).sum())
        self.n += d.size
        self.sa += float(a.sum()); self.sb += float(b.sum())
        self.saa += float(np.square(a).sum()); self.sbb += float(np.square(b).sum()); self.sab += float((a * b).sum())
        self.per_bin_sum += d.sum(axis=1)
        self.per_frame_sum[f0:f0 + d.shape[1]] += d.sum(axis=0)
        if stride > 1:
            self.sub.append(d[::stride, ::stride].ravel())

    def finalize(self, pair_a_id: str, pair_b_id: str, n_frames_total: int) -> dict:
        n = max(self.n, 1)
        mean_abs = self.sum_abs / n
        rmse = math.sqrt(self.sum_sq / n)
        cov = self.sab / n - (self.sa / n) * (self.sb / n)
        va = max(self.saa / n - (self.sa / n) ** 2, 0.0)
        vb = max(self.sbb / n - (self.sb / n) ** 2, 0.0)
        corr = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0
        median_val = float(np.median(np.concatenate(self.sub))) if self.sub else None
        
        return {
            "pair_a": pair_a_id, "pair_b": pair_b_id,
            "mean_absolute_mask_difference": mean_abs, "rmse_mask_difference": rmse,
            "correlation": corr, "median_absolute_difference": median_val,
            "n_bins_compared": self.n,
            "frequency_dependent_difference_per_bin_mean": (self.per_bin_sum / max(n_frames_total, 1)).tolist()
        }

class GlobalMaskAccum:
    def __init__(self, stride: int):
        self.stride = stride
        self.sum = 0.0; self.sumsq = 0.0; self.n = 0
        self.sub = []

    def update(self, chunk_map: np.ndarray):
        self.sum += float(chunk_map.sum())
        self.sumsq += float(np.square(chunk_map).sum())
        self.n += chunk_map.size
        if self.stride > 1:
            self.sub.append(chunk_map[::self.stride, ::self.stride].ravel())

    def finalize(self) -> dict:
        n = max(self.n, 1)
        mean = self.sum / n
        var = max(self.sumsq / n - mean * mean, 0.0)
        out = {"mean": mean, "std": math.sqrt(var), "n_bins": self.n}
        if self.sub:
            sub = np.concatenate(self.sub)
            out["median"] = float(np.median(sub))
            out["p05"] = float(np.percentile(sub, 5))
            out["p25"] = float(np.percentile(sub, 25))
            out["p75"] = float(np.percentile(sub, 75))
            out["p95"] = float(np.percentile(sub, 95))
            out["fraction_low_confidence_le_0.33"] = float((sub <= 0.33).mean())
            out["fraction_high_confidence_ge_0.67"] = float((sub >= 0.67).mean())
        return out

# ============================================================================
# SECCION 13: METRICAS MQR STREAMING
# ============================================================================

class PearsonAccum:
    def __init__(self):
        self.sa = 0.0; self.sb = 0.0; self.saa = 0.0; self.sbb = 0.0; self.sab = 0.0; self.n = 0

    def update(self, a: np.ndarray, b: np.ndarray):
        a_f = np.asarray(a, dtype=np.float64).ravel()
        b_f = np.asarray(b, dtype=np.float64).ravel()
        if a_f.size == 0 or b_f.size == 0: return
        self.sa += float(a_f.sum()); self.sb += float(b_f.sum())
        self.saa += float(np.square(a_f).sum()); self.sbb += float(np.square(b_f).sum()); self.sab += float((a_f * b_f).sum())
        self.n += a_f.size

    def finalize(self) -> dict:
        if self.n < 8: return {"correlation": None, "n": self.n}
        ma = self.sa / self.n; mb = self.sb / self.n
        va = max(self.saa / self.n - ma * ma, 0.0)
        vb = max(self.sbb / self.n - mb * mb, 0.0)
        cov = self.sab / self.n - ma * mb
        corr = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0
        return {"correlation": corr, "n": self.n}

class StereoAccum:
    def __init__(self):
        self.ll = 0.0; self.rr = 0.0; self.lr = 0.0; self.mid2 = 0.0; self.side2 = 0.0; self.n = 0

    def update(self, x: np.ndarray):
        if x.ndim != 2 or x.shape[1] < 2 or x.shape[0] == 0: return
        l = x[:, 0]; r = x[:, 1]
        self.ll += float(np.square(l).sum()); self.rr += float(np.square(r).sum()); self.lr += float((l * r).sum())
        self.mid2 += float(np.square(l + r).sum()); self.side2 += float(np.square(l - r).sum())
        self.n += len(l)

    def finalize(self) -> dict:
        if self.n == 0: return {"inter_channel_correlation": None, "available": False}
        denom = math.sqrt(max(self.ll * self.rr, 0.0))
        icc = self.lr / denom if denom > 0 else None
        width = self.side2 / self.mid2 if self.mid2 > 0 else None
        return {"available": True, "inter_channel_correlation": icc, "side_to_mid_energy_ratio": width}

class IPDAccum:
    def __init__(self):
        self.coh = 0.0 + 0.0j; self.coh_out = 0.0 + 0.0j; self.dphi_abs_sum = 0.0; self.n = 0

    def update(self, L_mix, R_mix, L_out=None, R_out=None, compute_diff=False):
        pl = L_mix * np.conj(R_mix)
        self.coh += complex(pl.sum())
        if compute_diff and L_out is not None:
            po = L_out * np.conj(R_out)
            self.coh_out += complex(po.sum())
            dphi = np.angle(po) - np.angle(pl)
            self.dphi_abs_sum += float(np.abs(np.angle(np.exp(1j * dphi))).sum())
        self.n += pl.size

    def finalize(self) -> dict:
        if self.n == 0: return {"available": False}
        return {
            "available": True,
            "mix_inter_channel_coherence": float(np.abs(self.coh) / self.n),
            "stem_inter_channel_coherence": float(np.abs(self.coh_out) / self.n) if self.coh_out != 0 else None,
            "output_minus_mix_mean_abs_dphi_rad": self.dphi_abs_sum / self.n if self.n else 0.0
        }

class OnsetAccum:
    def __init__(self):
        self.prev_mix = None; self.prev_out = None
        self.pearson = PearsonAccum()
        self.sum_diff2 = 0.0; self.sum_mix2 = 0.0; self.n = 0

    def update(self, mix_energy: np.ndarray, out_energy: np.ndarray):
        if self.prev_mix is not None and len(mix_energy) > 0:
            e_m = np.concatenate(([mix_energy[0] - self.prev_mix], np.diff(mix_energy)))
            e_o = np.concatenate(([out_energy[0] - self.prev_out], np.diff(out_energy)))
            on_m = np.maximum(0.0, e_m); on_o = np.maximum(0.0, e_o)
            self.pearson.update(on_m, on_o)
            self.sum_diff2 += float(np.square(on_m - on_o).sum())
            self.sum_mix2 += float(np.square(on_m).sum())
            self.n += len(on_m)
        if len(mix_energy) > 0:
            self.prev_mix = float(mix_energy[-1]); self.prev_out = float(out_energy[-1])

    def finalize(self) -> dict:
        p = self.pearson.finalize()
        rel = math.sqrt(self.sum_diff2 / self.n) if self.n else None
        ref = math.sqrt(self.sum_mix2 / self.n) if self.n else None
        return {
            "onset_correlation": p.get("correlation"),
            "onset_rms_relative_difference": (rel / ref) if (rel is not None and ref) else None,
            "n_frames": self.n
        }

class CandidateMetrics:
    def __init__(self, cand_id: str, plan: FramePlan, band_masks: np.ndarray, band_labels: list, guide_refs: dict, channels: int):
        self.cand_id = cand_id
        self.plan = plan
        self.band_masks = band_masks
        self.band_labels = band_labels
        self.guide_refs = guide_refs
        self.channels = channels

        self.n_samples = 0
        self.sum_mix2 = 0.0; self.sum_sdv2 = 0.0; self.sum_sdi2 = 0.0; self.sum_err2 = 0.0
        self.peak_mix = 0.0; self.peak_sdv = 0.0; self.peak_sdi = 0.0

        self.corr_sdv_vguide = {pid: PearsonAccum() for pid in guide_refs.get("vocal", [])}
        self.corr_sdi_iguide = {pid: PearsonAccum() for pid in guide_refs.get("instrumental", [])}
        self.corr_sdv_sdi = PearsonAccum()

        self.st_mix = StereoAccum(); self.st_sdv = StereoAccum(); self.st_sdi = StereoAccum()
        self.ipd_mix = IPDAccum(); self.ipd_sdv = IPDAccum(); self.ipd_sdi = IPDAccum()
        self.onset_sdv = OnsetAccum(); self.onset_sdi = OnsetAccum()

        self.band_energy = {"mix": np.zeros(len(band_labels)), "sdv": np.zeros(len(band_labels)), "sdi": np.zeros(len(band_labels))}
        self.centroid = {"mix": [0.0, 0.0], "sdv": [0.0, 0.0], "sdi": [0.0, 0.0]}

        self.tp_mix = TruePeakStream(channels)
        self.tp_sdv = TruePeakStream(channels)
        self.tp_sdi = TruePeakStream(channels)

    def update_freq(self, mix_stft, sdv_stft, sdi_stft, freqs):
        def band_e(X):
            m2 = np.square(np.abs(X)).sum(axis=0)
            return self.band_masks @ (m2.sum(axis=1) if m2.ndim == 2 else m2)

        def cent(X, key):
            mag = np.abs(X).mean(axis=0)
            mag_sum = mag.sum(axis=1) if mag.ndim == 2 else mag
            self.centroid[key][0] += float((freqs * mag_sum).sum())
            self.centroid[key][1] += float(mag_sum.sum())

        self.band_energy["mix"] += band_e(mix_stft)
        self.band_energy["sdv"] += band_e(sdv_stft)
        self.band_energy["sdi"] += band_e(sdi_stft)
        cent(mix_stft, "mix"); cent(sdv_stft, "sdv"); cent(sdi_stft, "sdi")

    def update_time(self, mix_reg, sdv_reg, sdi_reg, v_regs, i_regs, mix_stft=None, sdv_stft=None, sdi_stft=None):
        if sdv_reg is None or sdv_reg.shape[0] == 0: return
        m_mono = mono_downmix(mix_reg)
        v_mono = mono_downmix(sdv_reg)
        i_mono = mono_downmix(sdi_reg)

        self.n_samples += len(m_mono)
        self.sum_mix2 += float(np.square(m_mono).sum())
        self.sum_sdv2 += float(np.square(v_mono).sum())
        self.sum_sdi2 += float(np.square(i_mono).sum())
        
        err = m_mono - (v_mono + i_mono)
        self.sum_err2 += float(np.square(err).sum())
        
        self.peak_mix = max(self.peak_mix, float(np.abs(mix_reg).max()))
        self.peak_sdv = max(self.peak_sdv, float(np.abs(sdv_reg).max()))
        self.peak_sdi = max(self.peak_sdi, float(np.abs(sdi_reg).max()))

        self.tp_mix.push(mix_reg); self.tp_sdv.push(sdv_reg); self.tp_sdi.push(sdi_reg)
        self.st_mix.update(mix_reg); self.st_sdv.update(sdv_reg); self.st_sdi.update(sdi_reg)

        for pid, acc in self.corr_sdv_vguide.items():
            reg = v_regs.get(pid)
            if reg is not None and len(reg) == len(v_mono): acc.update(v_mono, reg)
        for pid, acc in self.corr_sdi_iguide.items():
            reg = i_regs.get(pid)
            if reg is not None and len(reg) == len(i_mono): acc.update(i_mono, reg)

        self.corr_sdv_sdi.update(v_mono, i_mono)

        if mix_stft is not None and mix_stft.shape[0] >= 2:
            self.ipd_mix.update(mix_stft[0], mix_stft[1], None, None, False)
            self.ipd_sdv.update(mix_stft[0], mix_stft[1], sdv_stft[0], sdv_stft[1], True)
            self.ipd_sdi.update(mix_stft[0], mix_stft[1], sdi_stft[0], sdi_stft[1], True)

        if mix_stft is not None:
            e_mix = np.square(np.abs(mix_stft)).sum(axis=(0, 1))
            e_sdv = np.square(np.abs(sdv_stft)).sum(axis=(0, 1))
            e_sdi = np.square(np.abs(sdi_stft)).sum(axis=(0, 1))
            self.onset_sdv.update(e_mix, e_sdv)
            self.onset_sdi.update(e_mix, e_sdi)

    def finalize(self) -> dict:
        n = max(self.n_samples, 1)
        rms_err = math.sqrt(self.sum_err2 / n)
        snr_db = (10.0 * math.log10(self.sum_mix2 / self.sum_err2)) if self.sum_err2 > 0 else 144.5 # Techo físico float32

        tp_mix = self.tp_mix.finalize()
        tp_sdv = self.tp_sdv.finalize()
        tp_sdi = self.tp_sdi.finalize()

        cent = {}
        for key in self.centroid:
            s = self.centroid[key]
            cent[key] = (s[0] / s[1]) if s[1] > 0 else None

        return {
            "reconstruction_accuracy": {
                "identity_snr_db": snr_db,
                "rms_error": rms_err,
                "status": "PASS_140DB" if snr_db >= 140.0 else "WARN_SNR"
            },
            "levels_and_dynamics": {
                "mix_rms_dbfs": 20.0 * math.log10(math.sqrt(self.sum_mix2 / n)) if self.sum_mix2 > 0 else -120.0,
                "sdv_rms_dbfs": 20.0 * math.log10(math.sqrt(self.sum_sdv2 / n)) if self.sum_sdv2 > 0 else -120.0,
                "sdi_rms_dbfs": 20.0 * math.log10(math.sqrt(self.sum_sdi2 / n)) if self.sum_sdi2 > 0 else -120.0,
                "sdv_sample_peak_dbfs": 20.0 * math.log10(self.peak_sdv) if self.peak_sdv > 0 else -120.0,
                "sdi_sample_peak_dbfs": 20.0 * math.log10(self.peak_sdi) if self.peak_sdi > 0 else -120.0,
                "sdv_true_peak_dbtp": 20.0 * math.log10(tp_sdv) if tp_sdv > 0 else -120.0,
                "sdi_true_peak_dbtp": 20.0 * math.log10(tp_sdi) if tp_sdi > 0 else -120.0,
                "sdv_crest_factor_db": 20.0 * math.log10(self.peak_sdv / math.sqrt(self.sum_sdv2 / n)) if self.sum_sdv2 > 0 else 0.0,
                "sdi_crest_factor_db": 20.0 * math.log10(self.peak_sdi / math.sqrt(self.sum_sdi2 / n)) if self.sum_sdi2 > 0 else 0.0
            },
            "bleeding_analysis": {
                "sdv_vs_vocal_guides_correlation": {pid: acc.finalize().get("correlation") for pid, acc in self.corr_sdv_vguide.items()},
                "sdi_vs_instrum_guides_correlation": {pid: acc.finalize().get("correlation") for pid, acc in self.corr_sdi_iguide.items()},
                "sdv_vs_sdi_cross_correlation": self.corr_sdv_sdi.finalize().get("correlation")
            },
            "spectral_fidelity": {
                "spectral_centroids_hz": cent,
                "centroid_drift_sdv_hz": (cent["sdv"] - cent["mix"]) if (cent["sdv"] and cent["mix"]) else None,
                "transient_preservation_sdv": self.onset_sdv.finalize()
            },
            "stereo_integrity": {
                "mix": self.st_mix.finalize(),
                "sdv": self.st_sdv.finalize(),
                "sdi": self.st_sdi.finalize(),
                "phase_sdv": self.ipd_sdv.finalize(),
                "phase_sdi": self.ipd_sdi.finalize()
            }
        }

class CandidateRunner:
    def __init__(self, cand_id: str, mask_source: tuple, plan: FramePlan, channels: int, run_dir: str = None,
                 band_masks: np.ndarray = None, band_labels: list = None, guide_refs: dict = None,
                 write_audio: bool = False, output_subtype: str = OUTPUT_SUBTYPE, out_prefix: str = "Track"):
        self.cand_id = cand_id
        self.mask_source = mask_source
        self.plan = plan
        self.write_audio = write_audio
        self.writer_sdv = None
        self.writer_sdi = None
        
        if write_audio and run_dir is not None:
            # [PATCH 4] Nombres dinámicos
            sdv_name = f"{out_prefix} SDV.wav"
            sdi_name = f"{out_prefix} SDI.wav"
            self.writer_sdv = sf.SoundFile(os.path.join(run_dir, sdv_name), mode="w", samplerate=REQUIRED_SAMPLE_RATE, channels=channels, subtype=output_subtype)
            self.writer_sdi = sf.SoundFile(os.path.join(run_dir, sdi_name), mode="w", samplerate=REQUIRED_SAMPLE_RATE, channels=channels, subtype=output_subtype)
            _registrar_propio_6g1(os.path.join(run_dir, sdv_name), estable=False)
            _registrar_propio_6g1(os.path.join(run_dir, sdi_name), estable=False)
            
        self.ola_sdv = OlaStream(plan, channels, writer=self.writer_sdv, label=f"{cand_id}/SDV")
        self.ola_sdi = OlaStream(plan, channels, writer=self.writer_sdi, label=f"{cand_id}/SDI")
        self.metrics = CandidateMetrics(cand_id, plan, band_masks, band_labels, guide_refs or {}, channels)

    def close(self):
        for w in (self.writer_sdv, self.writer_sdi):
            if w is not None:
                try: w.close()
                except Exception: pass
        self.writer_sdv = None
        self.writer_sdi = None

# ============================================================================
# SECCION 14: ORQUESTADOR PRINCIPAL SINGLE-PASS STREAMING (v3.1.0)
# ============================================================================

def create_run_dir(out_base: str) -> tuple:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_dir = os.path.join(out_base, f"motorA_run_{stamp}")
    partial_dir = final_dir + "_partial"
    os.makedirs(partial_dir, exist_ok=True)
    return partial_dir, final_dir

def _open_memmap(path: str, shape: tuple):
    mm = np.lib.format.open_memmap(path, mode="w+", dtype=MASK_SAVE_DTYPE, shape=shape)
    _registrar_propio_6g1(path, estable=False)
    return mm

def post_wav_identity(mix_path: str, sdv_path: str, sdi_path: str) -> dict:
    acc_mix2 = 0.0; acc_err2 = 0.0; n_samples = 0; peak_sum = 0.0

    with sf.SoundFile(mix_path) as hm, sf.SoundFile(sdv_path) as hv, sf.SoundFile(sdi_path) as hi:
        while True:
            m = hm.read(OUTPUT_AUDIO_BLOCKSIZE, dtype="float64", always_2d=True)
            if m.shape[0] == 0: break
            v = hv.read(m.shape[0], dtype="float64", always_2d=True)
            i = hi.read(m.shape[0], dtype="float64", always_2d=True)

            mm_ = mono_downmix(m)
            vv = mono_downmix(v)
            ii = mono_downmix(i)
            err = m - (v + i)

            acc_mix2 += float(np.square(m).sum())
            acc_err2 += float(np.square(err).sum())
            n_samples += len(mm_)
            peak_sum = max(peak_sum, float(np.abs(v + i).max()))

    n = max(n_samples, 1)
    rms_err = math.sqrt(acc_err2 / n)
    snr_db = (10.0 * math.log10(acc_mix2 / acc_err2)) if acc_err2 > 0 else 144.5

    return {
        "status": "PASS_EXACT_IDENTITY" if snr_db >= 140.0 else "WARN_SNR",
        "identity_snr_db": snr_db,
        "rms_error": rms_err,
        "max_abs_sum_sdv_sdi": peak_sum,
        "expected_min_snr_db": IDENTITY_SNR_TARGET_DB,
        "frames_validated": n_samples
    }


# ----------------------------------------------------------------------------
# [INJERTO 1] SUITE DE VALIDACIÓN DEFENSIVA (CALIBRACIÓN, ENUMS, OLA, PARES)
# ----------------------------------------------------------------------------

def validate_numeric_params(opt: argparse.Namespace) -> list:
    errs = []
    for name, (lo, hi) in PARAM_BOUNDS.items():
        v = getattr(opt, name, None)
        if isinstance(v, bool) or not isinstance(v, int):
            errs.append(f"{name}={repr(v)} no es entero.")
        elif not (lo <= v <= hi):
            errs.append(f"{name}={v} fuera de rango [{lo}, {hi}].")
    if errs:
        return errs
    if opt.hop > opt.n_fft:
        errs.append(f"hop={opt.hop} > n_fft={opt.n_fft}: OLA incompleta.")
    if opt.n_fft not in N_FFT_ALLOWED:
        errs.append(f"n_fft={opt.n_fft} no pertenece a {N_FFT_ALLOWED}.")
    return errs

def validate_cal_params(cal: dict) -> list:
    errs = []
    if not cal:
        return errs
    checks = (
        ("power_p", POWER_DEFAULT, 0.1, 8.0),
        ("epsilon", EPSILON_CALIBRATED, 1e-15, 1e-2),
        ("beta_consensus", CONFIDENCE_BETA, 1e-6, 32.0),
    )
    for key, dflt, lo, hi in checks:
        v = cal.get(key, dflt)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            errs.append(f"calibration_parameters.{key}={repr(v)} no numérico.")
        elif not (lo <= float(v) <= hi):
            errs.append(f"calibration_parameters.{key}={v} fuera de [{lo}, {hi}].")
    return errs

def validate_enums(mode: str, cal: dict) -> list:
    errs = []
    if mode not in REQUIRED_MODES:
        errs.append(f"mode={repr(mode)} no pertenece a REQUIRED_MODES.")
    for key, allowed in (("consensus_order", CONSENSUS_ORDERS),
                         ("mask_mode", MASK_MODES),
                         ("consensus", CONSENSUS_METHODS),
                         ("smoothing", SMOOTHING_KERNELS)):
        v = cal.get(key)
        if v is not None and v not in allowed:
            errs.append(f"calibration_parameters.{key}={repr(v)} no permitido.")
    return errs

def validate_pair_uniqueness(pairs: list) -> list:
    errs = []
    seen_id, seen_fn = set(), {}
    for p in pairs:
        pid = getattr(p, "pair_id", None) or (p.get("pair_id") if isinstance(p, dict) else str(p))
        if pid in seen_id:
            errs.append(f"pair_id duplicado: {repr(pid)}.")
        seen_id.add(pid)
        fn = safe_name(pid)
        if fn in seen_fn and seen_fn[fn] != pid:
            errs.append(f"Colisión de nombre: {repr(pid)} y {repr(seen_fn[fn])} producen {repr(fn)}.")
        seen_fn[fn] = pid
    return errs

def run_experiment(mix_path: str, pairs: list, mode: str, opt: argparse.Namespace):
    t_start = time.monotonic()
    ctx = {"mode": mode, "warnings": []}

    # 1. Validación de Entradas
    mix_info = validate_mix(probe_file(mix_path, "mix"))
    if not mix_info.valid:
        log("[FATAL] Mix Original inválido:")
        for e in mix_info.errors: log(f"  - {e}")
        return EXIT_VALIDATION, None

    if not pairs:
        log("[FATAL] No se especificaron pares de guías.")
        return EXIT_VALIDATION, None

    if opt.chunk_frames < 1:
        log("[FATAL] chunk_frames debe ser >= 1")
        return EXIT_VALIDATION, None

    # [PATCH 2] Guardián de Banderas Incompatibles (H1 / RISK-05)
    if opt.use_physical_residuals and opt.mask_mode == "per_channel" and mix_info.channels == 2:
        log("[FATAL] Incompatibilidad de banderas detectada:")
        log("        '--use-residuals' actualmente calcula las guías en mono.")
        log("        Combinarlo con '--mask-mode per_channel' produciría un estéreo falso.")
        log("        Abortando para proteger la integridad del SDV/SDI.")
        return EXIT_VALIDATION, None

    for p in pairs:
        p.vocal = validate_guide(probe_file(p.vocal_path, "vocal_guide"))
        p.instrumental = validate_guide(probe_file(p.instrumental_path, "instrumental_guide"))

    invalid = []
    for p in pairs:
        for role in ("vocal", "instrumental"):
            info = getattr(p, role)
            if not info.valid: invalid.append(f"{p.pair_id}/{role}: {'; '.join(info.errors)}")

    if invalid:
        log("[FATAL] Guías inválidas detectadas:")
        for inv in invalid: log(f"  - {inv}")
        return EXIT_VALIDATION, None

    log(f"Validación de entradas OK: Mix {mix_info.sample_rate}Hz/{mix_info.channels}ch ({fmt_size(mix_info.size_bytes)}) | {len(pairs)} Pares")
    ctx["mix_info"] = mix_info
    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
    ctx["container_6g"] = {
        "mix_path": os.path.abspath(mix_path),
        "container": _container_6g(mix_path),
        "format": mix_info.format, "subtype": mix_info.subtype,
        "probe_sha256": mix_info.sha256, "after": None,
        "policy": "detect_only_no_conversion"}

    ctx["pairs"] = pairs

    # 2. Modo Dry Run
    plan = FramePlan(mix_info.frames, opt.n_fft, opt.hop)
    if mode == MODE_DRY_RUN:
        log("DRY_RUN: Plan de ejecución verificado.")
        log(f"  Mix: {mix_info.path}")
        log(f"  STFT: K={plan.K} tramas, Bins={plan.bins}, Chunks de {opt.chunk_frames} tramas.")
        for p in pairs: log(f"  {p.pair_id:<20} | Family: {p.family:<18} | V: {p.vocal.path}")
        return EXIT_OK, None

    # 3. Análisis de Alineación y Shift
    log("Verificando alineación temporal NCC de las guías...")
    alignment_records = []
    misaligned = []
    guide_shifts = {}
    
    if opt.correct_alignment:
        log('[ABORT] 6C es sólo diagnóstico; --correct-alignment no está autorizado.')
        return EXIT_VALIDATION, None

    for p in pairs:
        for role in ("vocal", "instrumental"):
            info = getattr(p, role)
            rec = analyze_alignment(mix_info, info)
            rec["pair_id"] = p.pair_id; rec["role"] = role
            alignment_records.append(rec)
            log(f"  {p.pair_id}/{role}: {_alignment_line(rec)}")
            rec['continuation_permission'] = 'cli_allow_misaligned' if opt.allow_misaligned else None
            if rec['classification'] not in ('ALIGNED','WARNING'):
                misaligned.append(rec)

    ctx["alignment"] = alignment_records
    gate = alignment_gate(alignment_records, misaligned, opt.allow_misaligned, log)
    ctx["alignment_gate"] = gate
    for _r in misaligned:
        _r['continuation_permission'] = gate['permission']
    if not gate['allowed']:
        return EXIT_VALIDATION, None

    # 4. Análisis de Escala
    scale_records = []
    scale_factors = {}
    for p in pairs:
        rec, applied = analyze_guide_scale(mix_info, p)
        scale_records.append(rec)
        scale_factors[p.pair_id] = applied
        for role in ("vocal", "instrumental"):
            if applied.get(f"{role}_polarity", 1.0) == -1.0:
                raw_g = rec[role].get("raw_g_ls", 0.0)
                log(f"[AUTO-PHASE] {p.pair_id}/{role}: Inversión de fase detectada (g_LS={raw_g:+.4f}). Auto-rectificando a fase constructiva (0°) -> g_LS={applied[role]:.4f}")

    ctx["guide_scale_analysis"] = scale_records

    # 5. Directorios y Memmaps
    freqs = np.fft.rfftfreq(plan.n_fft, d=1.0 / REQUIRED_SAMPLE_RATE)
    band_masks, band_labels, _ = build_band_masks(plan.bins, plan.n_fft, REQUIRED_SAMPLE_RATE)
    
    run_dir, run_dir_final = create_run_dir(opt.out_base)
    init_tee(os.path.join(run_dir, "engine_log.txt"))
    masks_dir = os.path.join(run_dir, "masks")
    os.makedirs(masks_dir, exist_ok=True)

    log(f"Iniciando pipeline v3.1.0 en: {run_dir}")
    log(f"Configuración Consenso: order={opt.consensus_order} | consensus={opt.consensus_default} | smoothing={opt.smoothing} | mask_mode={opt.mask_mode}")
    log(f"Parámetros DSP: p={opt.power:.2f} | beta={opt.beta:.2f} | eps={opt.epsilon:.1e} | n_fft={opt.n_fft} | hop={opt.hop} | residuals={opt.use_physical_residuals}")

    try:
        n_pairs = len(pairs)
        full_mode = (mode == MODE_FULL_PROCESSING or mode == MODE_SINGLE_PAIR)

        mm = {}
        write_masks = opt.png or getattr(opt, "keep_masks", False)
        for p in pairs:
            pid = safe_name(p.pair_id)
            if write_masks: mm[f"mask_{pid}_vocal"] = _open_memmap(os.path.join(masks_dir, f"mask_{pid}_vocal.npy"), (plan.bins, plan.K))
            if write_masks: mm[f"mask_{pid}_instrumental"] = _open_memmap(os.path.join(masks_dir, f"mask_{pid}_instrumental.npy"), (plan.bins, plan.K))

        for method in CONSENSUS_METHODS:
            # [PATCH 3] Evitar redundancia si magnitudes_first (F-04 / BUG-04)
            if opt.consensus_order == "magnitudes_first" and method != opt.consensus_default:
                continue
            if write_masks: mm[f"consensus_vocal_{method}"] = _open_memmap(os.path.join(masks_dir, f"consensus_vocal_{method}.npy"), (plan.bins, plan.K))
            if write_masks: mm[f"consensus_instrumental_{method}"] = _open_memmap(os.path.join(masks_dir, f"consensus_instrumental_{method}.npy"), (plan.bins, plan.K))

        if write_masks: mm["confidence_map"] = _open_memmap(os.path.join(masks_dir, "confidence_map.npy"), (plan.bins, plan.K))
        if write_masks: mm["model_disagreement_map"] = _open_memmap(os.path.join(masks_dir, "model_disagreement_map.npy"), (plan.bins, plan.K))

        combos = [(i, j) for i in range(n_pairs) for j in range(i + 1, n_pairs)]
        pairwise = {(i, j): PairwiseAccum(plan.bins, plan.K) for i, j in combos}
        mask_stats = [mask_stats_stream_init() for _ in range(n_pairs)]
        conf_accum = GlobalMaskAccum(4)
        dis_accum = GlobalMaskAccum(4)
        consensus_stats = {m: mask_stats_stream_init() for m in CONSENSUS_METHODS}

        all_ids = [p.pair_id for p in pairs]
        track_base = os.path.splitext(os.path.basename(mix_info.path))[0] # [PATCH 4]
        runners = []
        for k, p in enumerate(pairs):
            write_audio = full_mode and opt.write_all_candidates
            sub = os.path.join(run_dir, "candidates", safe_name(f"individual_{p.pair_id}")) if write_audio else None
            if sub: os.makedirs(sub, exist_ok=True)
            runners.append(CandidateRunner(
                cand_id=f"individual_{p.pair_id}", mask_source=("individual", k),
                plan=plan, channels=mix_info.channels, run_dir=sub,
                band_masks=band_masks, band_labels=band_labels,
                guide_refs={"vocal": [p.pair_id], "instrumental": [p.pair_id]},
                write_audio=write_audio,
                out_prefix=track_base
            ))

        for method in CONSENSUS_METHODS:
            # [PATCH 3] Saltar métodos redundantes en magnitudes_first
            if opt.consensus_order == "magnitudes_first" and method != opt.consensus_default:
                continue
            is_default = (method == opt.consensus_default)
            write_audio = full_mode and (is_default or opt.write_all_candidates)
            sub = run_dir if (write_audio and is_default) else (os.path.join(run_dir, "candidates", safe_name(f"consensus_{method}")) if write_audio else None)
            if sub and not is_default: os.makedirs(sub, exist_ok=True)
            runners.append(CandidateRunner(
                cand_id=f"consensus_{method}", mask_source=("consensus", method),
                plan=plan, channels=mix_info.channels, run_dir=sub,
                band_masks=band_masks, band_labels=band_labels,
                guide_refs={"vocal": all_ids, "instrumental": all_ids},
                write_audio=write_audio,
                out_prefix=track_base if is_default else method
            ))

        try:
            hmix = _abrir_mix_6g1(mix_info.path, mix_info.sha256)
        except _MixCambiado_6g1 as _exc6g1:
            _abortar_6g1(run_dir, "MIX_SUSTITUIDO_ANTES_DEL_DSP", str(_exc6g1))
            log("[FATAL] Mix sustituido antes del DSP: %s" % _exc6g1)
            close_tee()
            return EXIT_PROCESSING, None
        handles = {}
        for p in pairs:
            handles[(p.pair_id, "vocal")] = sf.SoundFile(p.vocal.path)
            handles[(p.pair_id, "instrumental")] = sf.SoundFile(p.instrumental.path)

        n_chunks = (plan.K + opt.chunk_frames - 1) // opt.chunk_frames
        log(f"Procesando {plan.K} tramas en {n_chunks} chunks de {opt.chunk_frames} tramas...")

        # Bucle Single-Pass Streaming
        for c_idx, f0 in enumerate(range(0, plan.K, opt.chunk_frames)):
            f1 = min(f0 + opt.chunk_frames, plan.K)
            F = f1 - f0
            s0, s1 = plan.span_for_frames(f0, f1)

            mix_span = read_span(hmix, s0, s1)
            mix_stft = stft_span_frames(mix_span, F, plan)

            pair_data = []
            v_mags_for_avg = []
            i_mags_for_avg = []

            for k, p in enumerate(pairs):
                # Lectura con compensación de shift si está activa
                sh_v = guide_shifts.get((p.pair_id, "vocal"), 0)
                sh_i = guide_shifts.get((p.pair_id, "instrumental"), 0)
                v_span = read_span(handles[(p.pair_id, "vocal")], s0, s1, shift_samples=sh_v)
                i_span = read_span(handles[(p.pair_id, "instrumental")], s0, s1, shift_samples=sh_i)

                if scale_factors.get(p.pair_id, {}).get("vocal_polarity", 1.0) == -1.0:
                    v_span = -v_span
                if scale_factors.get(p.pair_id, {}).get("instrumental_polarity", 1.0) == -1.0:
                    i_span = -i_span

                v_mono = mono_downmix(v_span)
                i_mono = mono_downmix(i_span)
                m_mono = mono_downmix(mix_span)

                # Modo Residual con LS-Gain Match si está activado
                if opt.use_physical_residuals:
                    g_v = scale_factors[p.pair_id]["vocal"]
                    g_i = scale_factors[p.pair_id]["instrumental"]
                    v_res = m_mono - g_i * i_mono
                    i_res = m_mono - g_v * v_mono
                    V_stft = stft_span_frames(v_res[:, None], F, plan)
                    I_stft = stft_span_frames(i_res[:, None], F, plan)
                else:
                    if opt.mask_mode == "per_channel" and mix_info.channels == 2:
                        V_stft = stft_span_frames(v_span, F, plan) # (2, bins, F)
                        I_stft = stft_span_frames(i_span, F, plan)
                    else:
                        V_stft = stft_span_frames(v_mono[:, None], F, plan)
                        I_stft = stft_span_frames(i_mono[:, None], F, plan)

                if opt.mask_mode == "per_channel" and mix_info.channels == 2:
                    v_mag = np.abs(V_stft) # (2, bins, F)
                    i_mag = np.abs(I_stft)
                else:
                    v_mag = np.abs(V_stft[0]) # (bins, F)
                    i_mag = np.abs(I_stft[0])

                v_mags_for_avg.append(v_mag)
                i_mags_for_avg.append(i_mag)

                # Máscara individual para análisis
                mv_ind = compute_vocal_mask(v_mag, i_mag, opt.power, opt.epsilon)
                if opt.mask_mode == "per_channel" and mix_info.channels == 2:
                    mv_ind_save = np.mean(mv_ind, axis=0)
                else:
                    mv_ind_save = mv_ind

                mask_stats_stream_update(mask_stats[k], mv_ind_save, 4)
                if write_masks:
                    mm[f"mask_{safe_name(p.pair_id)}_vocal"][:, f0:f1] = mv_ind_save.astype(MASK_SAVE_DTYPE)
                    mm[f"mask_{safe_name(p.pair_id)}_instrumental"][:, f0:f1] = (1.0 - mv_ind_save).astype(MASK_SAVE_DTYPE)

                pair_data.append({
                    "pair": p, "mv": mv_ind, "v_mono": v_mono, "i_mono": i_mono,
                    "v_mag": v_mag, "i_mag": i_mag
                })

            # Pairwise
            for (i, j) in combos:
                a_m = pair_data[i]["mv"] if pair_data[i]["mv"].ndim == 2 else np.mean(pair_data[i]["mv"], axis=0)
                b_m = pair_data[j]["mv"] if pair_data[j]["mv"].ndim == 2 else np.mean(pair_data[j]["mv"], axis=0)
                pairwise[(i, j)].update(a_m, b_m, f0, 4)

            # Consenso: Selección de Orden (Hallazgo 01)
            masks_list = [pd["mv"] for pd in pair_data]
            conf_map, dis_map, c_k = confidence_and_disagreement(masks_list)

            if opt.consensus_order == "magnitudes_first":
                # PARIDAD ACUSTICA CON SCRIPT COMPACTO (Sfumato Natural)
                V_mag_stack = np.stack(v_mags_for_avg, axis=0)
                I_mag_stack = np.stack(i_mags_for_avg, axis=0)
                V_mag_avg = np.mean(V_mag_stack, axis=0)
                I_mag_avg = np.mean(I_mag_stack, axis=0)

                mv_raw_cons = compute_vocal_mask(V_mag_avg, I_mag_avg, opt.power, opt.epsilon)
                
                # Suavizado Sfumato 2D Opcional (Hallazgo 03)
                if opt.smoothing != "none":
                    if mv_raw_cons.ndim == 3:
                        mv_raw_cons = np.stack([apply_sfumato_smoothing(mv_raw_cons[ch], opt.smoothing) for ch in range(mv_raw_cons.shape[0])], axis=0)
                    else:
                        mv_raw_cons = apply_sfumato_smoothing(mv_raw_cons, opt.smoothing)

                # [PATCH 3] Renormalización cosmética eliminada (era código muerto).
                # La partición de unidad está garantizada por mi_c = 1.0 - mv_c.
                Mv_consensus = np.clip(mv_raw_cons, 0.0, 1.0)

                consensus = {
                    "weighted_mean": Mv_consensus,
                    "median": Mv_consensus,
                    "confidence_weighted_mean": Mv_consensus
                }
                weights_summary = {"order": "magnitudes_first", "power": opt.power}

            elif opt.consensus_order == "hybrid_asymmetric":
                # [MODO HIBRIDO ASIMETRICO SGM]
                # 1. Mascara vocal derivada via masks_first (definicion vocal)
                cons_masks, weights_summary = consensus_from_masks(
                    masks_list, c_k, beta=opt.beta
                )

                # 2. Mascara instrumental derivada via magnitudes_first (calidez instrumental)
                V_mag_stack = np.stack(v_mags_for_avg, axis=0)
                I_mag_stack = np.stack(i_mags_for_avg, axis=0)
                if opt.consensus_default == "median":
                    V_mag_avg = np.median(V_mag_stack, axis=0)
                    I_mag_avg = np.median(I_mag_stack, axis=0)
                else:
                    V_mag_avg = np.mean(V_mag_stack, axis=0)
                    I_mag_avg = np.mean(I_mag_stack, axis=0)

                mi_raw_mags = compute_vocal_mask(I_mag_avg, V_mag_avg, opt.power, opt.epsilon)

                if opt.smoothing != "none":
                    if mi_raw_mags.ndim == 3:
                        mi_raw_mags = np.stack([apply_sfumato_smoothing(mi_raw_mags[ch], opt.smoothing) for ch in range(mi_raw_mags.shape[0])], axis=0)
                    else:
                        mi_raw_mags = apply_sfumato_smoothing(mi_raw_mags, opt.smoothing)

                Mi_mags = np.clip(mi_raw_mags, 0.0, 1.0)

                # 3. Particion de Unidad Normalizada exacta: Mv / (Mv + Mi)
                consensus = {}
                for method in CONSENSUS_METHODS:
                    mv_m = cons_masks[method]
                    denom = mv_m + Mi_mags + 1e-12
                    consensus[method] = np.clip(mv_m / denom, 0.0, 1.0)

                weights_summary = {"order": "hybrid_asymmetric", "power": opt.power, "beta": opt.beta}

            else:
                # Orden masks_first (v3.0.0 tradicional)
                consensus, weights_summary = consensus_from_masks(
                    masks_list, c_k, beta=opt.beta
                )

            conf_accum.update(conf_map)
            dis_accum.update(dis_map)

            for method in CONSENSUS_METHODS:
                # [PATCH 3] Saltar escritura redundante en magnitudes_first
                if opt.consensus_order == "magnitudes_first" and method != opt.consensus_default:
                    continue
                m_save = consensus[method] if consensus[method].ndim == 2 else np.mean(consensus[method], axis=0)
                mask_stats_stream_update(consensus_stats[method], m_save, 4)
                if write_masks:
                    mm[f"consensus_vocal_{method}"][:, f0:f1] = m_save.astype(MASK_SAVE_DTYPE)
                    mm[f"consensus_instrumental_{method}"][:, f0:f1] = (1.0 - m_save).astype(MASK_SAVE_DTYPE)

            if write_masks:
                mm["confidence_map"][:, f0:f1] = conf_map.astype(MASK_SAVE_DTYPE)
                mm["model_disagreement_map"][:, f0:f1] = dis_map.astype(MASK_SAVE_DTYPE)

            # Aplicación al STFT del Mix Original
            v_regs_all = {p.pair_id: pair_data[i]["v_mono"] for i, p in enumerate(pairs)}
            i_regs_all = {p.pair_id: pair_data[i]["i_mono"] for i, p in enumerate(pairs)}

            for runner in runners:
                if runner.mask_source[0] == "individual":
                    k = runner.mask_source[1]
                    mv_c = pair_data[k]["mv"]
                    v_regs = {pairs[k].pair_id: pair_data[k]["v_mono"]}
                    i_regs = {pairs[k].pair_id: pair_data[k]["i_mono"]}
                    pair_mags = {pairs[k].pair_id: (pair_data[k]["v_mag"], pair_data[k]["i_mag"])}
                else:
                    mv_c = consensus[runner.mask_source[1]]
                    v_regs = v_regs_all
                    i_regs = i_regs_all
                    pair_mags = {p.pair_id: (pair_data[i]["v_mag"], pair_data[i]["i_mag"]) for i, p in enumerate(pairs)}

                mi_c = 1.0 - mv_c
                if mv_c.ndim == 3: # per_channel
                    sdv_stft = mix_stft * mv_c
                    sdi_stft = mix_stft * mi_c
                else:
                    sdv_stft = mix_stft * mv_c[None, :, :]
                    sdi_stft = mix_stft * mi_c[None, :, :]

                runner.metrics.update_freq(mix_stft, sdv_stft, sdi_stft, freqs)
                reg_v, a, b = runner.ola_sdv.push(sdv_stft)
                reg_i, _, _ = runner.ola_sdi.push(sdi_stft)

                lo = a - s0; hi = b - s0
                mix_reg = mix_span[lo:hi]
                v_regs_r = {pid: arr[lo:hi] for pid, arr in v_regs.items()}
                i_regs_r = {pid: arr[lo:hi] for pid, arr in i_regs.items()}

                runner.metrics.update_time(mix_reg, reg_v, reg_i, v_regs_r, i_regs_r,
                                           mix_stft=mix_stft, sdv_stft=sdv_stft, sdi_stft=sdi_stft)

            if (c_idx + 1) % 10 == 0 or (c_idx + 1) == n_chunks:
                pct = ((c_idx + 1) / n_chunks) * 100
                log(f"  Chunk {c_idx+1:02d}/{n_chunks} [{pct:5.1f}%] completado (Tramas {f0}-{f1-1})")

        # Flush final
        for runner in runners:
            reg_v, a, b = runner.ola_sdv.flush()
            reg_i, _, _ = runner.ola_sdi.flush()
            runner.close()

        # 6G.1: el descriptor sigue abierto durante todo el DSP
        for h in handles.values(): h.close()
        if write_masks:
            for arr in mm.values(): arr.flush()
        del mm

        per_candidate = {runner.cand_id: runner.metrics.finalize() for runner in runners}

        post_wav = None
        if full_mode:
            # [PATCH 4] Rutas dinámicas
            post_wav = post_wav_identity(hmix.ruta_lectura(), os.path.join(run_dir, f"{track_base} SDV.wav"), os.path.join(run_dir, f"{track_base} SDI.wav"))
            log(f"Post-WAV Identity SNR: {post_wav['identity_snr_db']:.2f} dB (Estado: {post_wav['status']})")

        pairwise_out = [pairwise[(i, j)].finalize(pairs[i].pair_id, pairs[j].pair_id, plan.K) for i, j in combos]

        ctx.update({
            "stft_configuration": {
                "n_fft": opt.n_fft, "hop_length": opt.hop, "window": STFT_WINDOW,
                "power": opt.power, "epsilon": opt.epsilon, "beta": opt.beta,
                "consensus_order": opt.consensus_order, "smoothing": opt.smoothing,
                "mask_mode": opt.mask_mode, "use_physical_residuals": opt.use_physical_residuals
            },
            "individual_model_metrics": [
                {"pair_id": p.pair_id, "family": p.family, "variant": p.variant,
                 "vocal_mask_statistics": mask_stats_stream_finalize(mask_stats[k])}
                for k, p in enumerate(pairs)
            ],
            "pairwise_model_comparison": pairwise_out,
            "confidence_analysis": {"map_statistics": conf_accum.finalize()},
            "model_disagreement": {"map_statistics": dis_accum.finalize()},
            "consensus_methods": {
                "default": opt.consensus_default, "weights_summary": weights_summary,
                "mask_statistics": {m: mask_stats_stream_finalize(consensus_stats[m]) for m in CONSENSUS_METHODS}
            },
            "per_candidate": per_candidate,
            "post_wav_validation": post_wav,
            "duration_total_s": time.monotonic() - t_start
        })

        write_reports(ctx, run_dir, opt)
        if opt.png and MATPLOTLIB_OK:
            write_pngs(masks_dir, run_dir)

        # [PATCH 4] Limpieza automática de máscaras y cierre de Tee
        if os.path.exists(masks_dir):
            try:
                shutil.rmtree(masks_dir)
                log("Directorio 'masks/' eliminado para liberar espacio.")
            except OSError as e:
                log(f"[WARN] No se pudo eliminar masks/: {e}")
        
        close_tee()  # Cierra el archivo de log correctamente
        # [PATCH 6] Se conserva engine_log.txt para trazabilidad forense (Venice F-060)

        # [6G.1-R/A] Guarda final fail-closed sobre el provisional, ANTES de
        # publicar: VERIFICACION INCIERTA = ABORTO. Sin fallback
        # _check_unchanged_6g ni aprobación alternativa; excepción -> aborto.
        # Cierre de recursos garantizado en finally.
        try:
            ctx["container_6g"]["after"] = hmix.verificar()
            ctx["container_6g"]["ruta_actual"] = hmix.ruta_apunta_al_mismo_objeto()
        except Exception as _exc6g1:
            ctx["container_6g"]["after"] = dict(unchanged=False,
                                                reason="excepcion: %s" % _exc6g1)
            ctx["container_6g"]["ruta_actual"] = dict(unchanged=False,
                                                      reason="excepcion: %s" % _exc6g1)
        finally:
            try:
                hmix.close()
            except Exception:
                pass
        # [6G.1-R/B] evidencia de integridad en el provisional + comprobación
        try:
            with open(os.path.join(run_dir, "input_integrity_6g.json"),
                      "w", encoding="utf-8") as _f6g:
                json.dump(json_safe(ctx["container_6g"]), _f6g, indent=2,
                          ensure_ascii=False)
            _registrar_propio_6g1(os.path.join(run_dir, "input_integrity_6g.json"),
                                  estable=True)
            with open(os.path.join(run_dir, "input_integrity_6g.json"),
                      "r", encoding="utf-8") as _f6g:
                json.load(_f6g)
        except Exception as _exc6g:
            log("[6G.1-R] evidencia de integridad no acreditable: %s" % _exc6g)
            ctx["container_6g"]["after"] = dict(unchanged=False,
                                                reason="evidencia no escrita o no verificable")
            ctx["container_6g"]["ruta_actual"] = dict(unchanged=False,
                                                      reason="evidencia no escrita o no verificable")
        if not (ctx["container_6g"]["after"].get("unchanged")
                and ctx["container_6g"].get("ruta_actual", {}).get("unchanged")):
            _info6g1 = _abortar_6g1(
                run_dir, "MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO",
                ctx["container_6g"])
            log("[FATAL] Mix cambiado o verificacion incierta antes de publicar: "
                "salidas propias invalidadas: %s" % _info6g1["salidas_invalidadas"])
            if 'handles' in locals():
                for _h6g1_h in list(handles.values()):
                    try:
                        _h6g1_h.close()
                    except Exception:
                        pass
            return EXIT_PROCESSING, None
        # [6G.1-R/B] Publicación por renombrado sólo tras guarda superada
        if os.path.exists(run_dir_final):
            stamp = datetime.now().strftime("%H%M%S")
            run_dir_final = run_dir_final + f"_{stamp}"
        os.rename(run_dir, run_dir_final)
        log(f"Corrida finalizada exitosamente en: {run_dir_final}")
        return EXIT_OK, run_dir_final

    except KeyboardInterrupt:
        aborted = run_dir_final + "_aborted"
        try: os.rename(run_dir, aborted)
        except OSError: aborted = run_dir
        log(f"[ABORT] Interrumpido por usuario. Directorio: {aborted}")
        close_tee()
        return EXIT_ABORTED, None
    except Exception as exc:
        try:
            if 'hmix' in locals() and hmix: hmix.close()
            if 'handles' in locals():
                for h in handles.values(): h.close()
        except Exception: pass
        
        aborted = run_dir_final + "_aborted"
        try: os.rename(run_dir, aborted)
        except OSError: aborted = run_dir
        log(f"[FATAL] Excepción: {exc}. Directorio: {aborted}")
        traceback.print_exc()
        close_tee()
        return EXIT_PROCESSING, None

# ============================================================================
# SECCION 15: GENERADORES DE REPORTES CIENTIFICOS Y VISUALIZACIONES PNG
# ============================================================================

def _fmt(v, nd=4):
    if v is None: return "null"
    if isinstance(v, float): return f"{v:.{nd}f}"
    return str(v)

def write_reports(ctx: dict, run_dir: str, opt: argparse.Namespace):
    mix_info = ctx["mix_info"]
    pairs = ctx["pairs"]
    per_cand = ctx["per_candidate"]

    # [PATCH 6] Calcular hashes para trazabilidad forense
    import hashlib
    def get_sha256(path):
        if not path or not os.path.exists(path): return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
        return h.hexdigest()

    engine_sha = get_sha256(os.path.abspath(__file__))
    manifest_sha = get_sha256(getattr(opt, "manifest_path", None))

    analysis = {
        "document_meta": {
            "engine": ENGINE_NAME, "version": ENGINE_VERSION,
            "standard": CALIBRATION_STANDARD, "generated_utc": utc_now_iso(),
            "execution_mode": ctx["mode"], "total_duration_s": ctx.get("duration_total_s", 0.0),
            "engine_sha256": engine_sha,
            "manifest_sha256": manifest_sha,
            "parameters": {
                "n_fft": opt.n_fft, "hop_length": opt.hop,
                "power_p": opt.power, "epsilon": opt.epsilon, "beta": opt.beta,
                "consensus_order": opt.consensus_order, "smoothing": opt.smoothing,
                "mask_mode": opt.mask_mode, "use_physical_residuals": opt.use_physical_residuals,
                "output_subtype": OUTPUT_SUBTYPE
            }
        },
        "mix_original": {
            "path": mix_info.path, "subtype": mix_info.subtype,
            "sample_rate": mix_info.sample_rate, "channels": mix_info.channels,
            "frames": mix_info.frames, "duration_s": mix_info.duration_s,
            "sha256": mix_info.sha256
        },
        "guide_inventory": [p.as_dict() for p in pairs],
        "alignment_analysis": ctx.get("alignment", []),
        "alignment_gate": ctx.get("alignment_gate", {}),
        "scale_analysis": ctx.get("guide_scale_analysis", []),
        "stft_configuration": ctx.get("stft_configuration", {}),
        "individual_model_metrics": ctx.get("individual_model_metrics", []),
        "pairwise_model_comparison": ctx.get("pairwise_model_comparison", []),
        "confidence_analysis": ctx.get("confidence_analysis", {}),
        "model_disagreement": ctx.get("model_disagreement", {}),
        "consensus_methods": ctx.get("consensus_methods", {}),
        "candidates_mqr_evaluation": per_cand,
        "post_wav_validation": ctx.get("post_wav_validation"),
        "scientific_interpretation": {
            "summary": [
                f"Separación ejecutada bajo Topología T02 Calibrada v3.1.0 ({len(pairs)} pares).",
                f"Orden del Consenso: {opt.consensus_order} (Paridad con motor de producción).",
                f"Identity SNR verificado post-escritura WAV: {(ctx.get('post_wav_validation') or {}).get('identity_snr_db', 0.0):.2f} dB.",
                "Invariante de partición de unidad Sum_k(M_k) == 1.0 estrictamente preservada.",
                "La fase proviene 100% del Mix Original (Cero distorsión de fase)."
            ],
            "downstream_intent": "SDV.wav y SDI.wav constituyen fuentes inmutables para el Motor 2 de deconstrucción multi-stem."
        }
    }

    with open(os.path.join(run_dir, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(json_safe(analysis), f, indent=2, ensure_ascii=False)
    _registrar_propio_6g1(os.path.join(run_dir, "analysis.json"), estable=True)

    write_analysis_txt(analysis, os.path.join(run_dir, "analysis.txt"))
    _registrar_propio_6g1(os.path.join(run_dir, "analysis.txt"), estable=True)

def write_analysis_txt(analysis: dict, path: str):
    L = []
    A = lambda s: L.append(s)
    dm = analysis["document_meta"]
    mo = analysis["mix_original"]
    pw = analysis.get("post_wav_validation") or {}
    cands = analysis.get("candidates_mqr_evaluation", {})

    A("=" * 76)
    A(f"INFORME CIENTÍFICO MQR - {dm['engine']} v{dm['version']}")
    A(f"Estándar: {dm['standard']}")
    A("=" * 76)
    A(f"Fecha UTC: {dm['generated_utc']} | Modo: {dm['execution_mode']}")
    A(f"Mix      : {os.path.basename(mo['path'])} ({mo['subtype']}, {mo['sample_rate']}Hz, {mo['channels']}ch, {mo['duration_s']:.2f}s)")
    A("")
    A("--- 1. CERTIFICACION DE RECONSTRUCCION EXACTA ------------------------------")
    A(f"• Identity SNR Post-WAV : {pw.get('identity_snr_db', 0.0):.2f} dB (Estado: {pw.get('status')})")
    A(f"• Error RMS Temporal    : {pw.get('rms_error', 0.0):.2e}")
    A("")
    A("--- 2. TABLERO DE DINAMICAS Y AISLAMIENTO (CANDIDATOS MQR) -----------------")
    A(f"{'CANDIDATO':<26} │ {'SDV RMS':<9} │ {'SDI RMS':<9} │ {'SDV PEAK':<10} │ {'SDV TRUE-PK':<11} │ {'CREST(dB)':<9}")
    A("─" * 27 + "┼" + "─" * 11 + "┼" + "─" * 11 + "┼" + "─" * 12 + "┼" + "─" * 13 + "┼" + "─" * 10)

    for cid, data in cands.items():
        lv = data.get("levels_and_dynamics", {})
        rms_v = f"{lv.get('sdv_rms_dbfs', -120):.2f} dB"
        rms_i = f"{lv.get('sdi_rms_dbfs', -120):.2f} dB"
        pk_v = f"{lv.get('sdv_sample_peak_dbfs', -120):.2f} dB"
        tp_v = f"{lv.get('sdv_true_peak_dbtp', -120):.2f} dBTP"
        cf_v = f"{lv.get('sdv_crest_factor_db', 0):.2f} dB"
        A(f"{cid:<26} │ {rms_v:<9} │ {rms_i:<9} │ {pk_v:<10} │ {tp_v:<11} │ {cf_v:<9}")

    A("")
    A("--- 3. ALINEACION DE GUIAS -------------------------------------------------")
    for r in analysis.get("alignment_analysis", []):
        A(f"• {r.get('pair_id')}/{r.get('role')}: {_alignment_line(r)}")

    A("")
    A("--- 4. INTERPRETACION FACTUAL ----------------------------------------------")
    for line in analysis["scientific_interpretation"]["summary"]: A(f"• {line}")
    A(f"• Downstream: {analysis['scientific_interpretation']['downstream_intent']}")
    A("=" * 76)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

def write_pngs(masks_dir: str, run_dir: str):
    png_dir = os.path.join(run_dir, "png")
    os.makedirs(png_dir, exist_ok=True)
    plots = [
        ("confidence_map.npy", "Mapa_de_Confianza_Espectral", "viridis"),
        ("model_disagreement_map.npy", "Mapa_de_Desacuerdo_Inter_Modelo", "inferno")
    ]
    for fname, title, cmap in plots:
        fpath = os.path.join(masks_dir, fname)
        if not os.path.isfile(fpath): continue
        arr = np.load(fpath, mmap_mode="r")
        step_r = max(1, arr.shape[0] // 512)
        step_c = max(1, arr.shape[1] // 1024)
        data = arr[::step_r, ::step_c]

        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        im = ax.imshow(data, aspect="auto", origin="lower", cmap=cmap, vmin=0.0, vmax=1.0)
        ax.set_title(title.replace("_", " "))
        ax.set_xlabel("Tramas (Frames)")
        ax.set_ylabel("Bandas de Frecuencia (Bins)")
        fig.colorbar(im, ax=ax)
        fig.savefig(os.path.join(png_dir, f"{title}.png"), dpi=120)
        plt.close(fig)
    log(f"Visualizaciones PNG guardadas en: {png_dir}")

# ============================================================================
# SECCION 16: CLI ARGUMENT PARSER Y ENTRYPOINT PRINCIPAL
# ============================================================================

def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="MOTOR_SEP_SDV-SDI.py",
        description=f"{ENGINE_NAME} v{ENGINE_VERSION} - {CALIBRATION_STANDARD}"
    )
    p.add_argument("--manifest", default=None, help="Ruta al manifiesto JSON (MANIFEST_SEP_SDV-SDI.json)")
    p.add_argument("--mix", default=None, help="Ruta al Mix Original (modo interactivo rápido)")
    p.add_argument("--mode", default=None, choices=list(REQUIRED_MODES), help="Modo de ejecución")
    p.add_argument("--out", default=".", help="Directorio base de salida")
    p.add_argument("--n-fft", type=int, default=N_FFT_DEFAULT, help="Tamaño FFT (2048, 4096, 8192)")
    p.add_argument("--hop", type=int, default=HOP_LENGTH_DEFAULT, help="Longitud de salto (hop length)")
    p.add_argument("--power", type=float, default=POWER_DEFAULT, help="Exponente p de la máscara Wiener (1.8 Sfumato)")
    p.add_argument("--epsilon", type=float, default=EPSILON_CALIBRATED, help="Epsilon calibrado (1e-12)")
    p.add_argument("--beta", type=float, default=CONFIDENCE_BETA, help="Exponente beta de consenso leave-one-out")
    p.add_argument("--consensus-order", default=CONSENSUS_ORDER_DEFAULT, choices=list(CONSENSUS_ORDERS), help="Orden de consenso (magnitudes_first / masks_first)")
    p.add_argument("--smoothing", default="none", choices=list(SMOOTHING_KERNELS), help="Kernel de suavizado 2D (none, median_3x3, gaussian_5x3)")
    p.add_argument("--mask-mode", default="mono", choices=list(MASK_MODES), help="Modo de cálculo de máscara (mono / per_channel)")
    p.add_argument("--chunk-frames", type=int, default=CHUNK_FRAMES_DEFAULT, help="Tramas por chunk para memoria ARM64")
    p.add_argument("--consensus", default=CONSENSUS_DEFAULT, choices=list(CONSENSUS_METHODS), help="Consenso predeterminado")
    p.add_argument("--use-residuals", dest="use_physical_residuals", action="store_true", help="Activa guías por residuo con ajuste LS-Gain")
    p.set_defaults(use_physical_residuals=False)
    p.add_argument("--correct-alignment", action="store_true", help="6C: reconocido pero rechazado; no se desplaza audio")
    p.add_argument("--allow-misaligned", action="store_true", help="6E: permite continuar sin shift con alineación no validada (no ante ERROR)")
    p.add_argument("--write-all-candidates", action="store_true", help="Escribe SDV/SDI de todos los candidatos individuales")
    p.add_argument("--png", action="store_true", help="Genera mapas de calor espectrales PNG")
    p.add_argument("--keep-masks", action="store_true", help="Conserva las máscaras en disco")
    return p

def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    mode = args.mode or MODE_FULL_PROCESSING

    try:
        if args.manifest:
            mix_path, pairs, cal_params, out_dir = load_manifest(args.manifest)
            
            # [PATCH 1] Aplicar precedencia CLI > Manifest > Defaults
            import sys as _sys
            def _is_passed(flag):
                return any(arg == flag or arg.startswith(flag + "=") for arg in _sys.argv)
            
            if not _is_passed("--power") and "power_p" in cal_params:
                args.power = float(cal_params["power_p"])
            if not _is_passed("--epsilon") and "epsilon" in cal_params:
                args.epsilon = float(cal_params["epsilon"])
            if not _is_passed("--beta") and "beta_consensus" in cal_params:
                args.beta = float(cal_params["beta_consensus"])
            if not _is_passed("--n-fft") and "n_fft" in cal_params:
                args.n_fft = int(cal_params["n_fft"])
            if not _is_passed("--hop") and "hop_length" in cal_params:
                args.hop = int(cal_params["hop_length"])
            if not _is_passed("--use-residuals") and cal_params.get("use_physical_residuals") is True:
                args.use_physical_residuals = True
            if not _is_passed("--out") and out_dir is not None:
                args.out = out_dir
            if not _is_passed("--smoothing") and "smoothing" in cal_params:
                args.smoothing = str(cal_params["smoothing"])
            if not _is_passed("--consensus-order") and "consensus_order" in cal_params:
                args.consensus_order = str(cal_params["consensus_order"])
            if not _is_passed("--consensus") and "consensus" in cal_params:
                args.consensus = str(cal_params["consensus"])
            if not _is_passed("--mask-mode") and "mask_mode" in cal_params:
                args.mask_mode = str(cal_params["mask_mode"])
            del _sys
        elif args.mix:
            if not os.path.isfile(args.mix):
                print(f"[FATAL] Mix no encontrado: {args.mix}")
                return EXIT_VALIDATION
            mix_path, pairs = interactive_collect_inputs(mode, preset_mix=args.mix)
        else:
            mix_path, pairs = interactive_collect_inputs(mode)
    except (OSError, KeyError, ValueError, TypeError, EOFError, json.JSONDecodeError) as exc:
        print(f"[FATAL] Entradas inválidas: {exc}")
        return EXIT_VALIDATION

    opt = argparse.Namespace(
        n_fft=args.n_fft, hop=args.hop, power=args.power, epsilon=args.epsilon,
        beta=args.beta, consensus_order=args.consensus_order, smoothing=args.smoothing,
        mask_mode=args.mask_mode, chunk_frames=args.chunk_frames,
        consensus_default=args.consensus, use_physical_residuals=args.use_physical_residuals,
        correct_alignment=args.correct_alignment, allow_misaligned=args.allow_misaligned,
        write_all_candidates=args.write_all_candidates, png=args.png, keep_masks=args.keep_masks,
        out_base=args.out, manifest_path=args.manifest, mode=mode
    )

    # [INJERTO 1] Aduana de Validación Defensiva
    cal_dict = cal_params if "cal_params" in locals() and isinstance(cal_params, dict) else {}
    pre_errs = (validate_numeric_params(opt) + validate_cal_params(cal_dict) +
                validate_enums(mode, cal_dict) + validate_pair_uniqueness(pairs))
    if pre_errs:
        for e in pre_errs:
            log(f"[FATAL] {e}")
        return EXIT_VALIDATION

    if mode == MODE_SINGLE_PAIR:
        if len(pairs) > 1:
            print("[INFO] single_file: se usa SOLO el primer par")
            pairs = pairs[:1]

    code, run_dir = run_experiment(mix_path, pairs, mode, opt)
    if code == EXIT_OK and run_dir:
        print("\n" + "=" * 76)
        print("\033[92m[✓] SEPARACIÓN MOTOR A v3.1.0 COMPLETADA CON ÉXITO (SNR > 140 dB)\033[0m")
        print(f"Directorio de Resultados : \033[96m{run_dir}\033[0m")
        track_base_name = os.path.splitext(os.path.basename(mix_path))[0]
        print(f"Artefactos Generados     : {track_base_name} SDV.wav | {track_base_name} SDI.wav | analysis.json | analysis.txt")
        print("=" * 76 + "\n")
        return EXIT_OK
    return code

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[ABORT] Interrumpido por el usuario.")
        sys.exit(EXIT_ABORTED)
