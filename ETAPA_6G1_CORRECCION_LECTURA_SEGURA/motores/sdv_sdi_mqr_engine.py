#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
SDV-SDI MQR ENGINE v1.0.0
Multi-Model Multi-Variant Consensus Time-Frequency Masking Engine
============================================================================
Implementacion integran del spec: "Prompt Mask MVSEP.json" (v1.3.0,
status experimental_calibration). Proyecto SDV-SDI MQR.
Pista de calibracion de referencia: Elis - Die Stadt.

PROPOSITO ------------------------------------------------------------------
Construir mascaras tiempo-frecuencia (TF) de alta precision usando multiples
pares de stems guia (guides) obtenidos EXTERNAMENTE mediante MVSEP --
posiblemente de distintas familias, variantes o configuraciones -- analizar
su concordancia, construir mascaras consensuadas y aplicarlas
EXCLUSIVAMENTE al Mix Original para producir:

    SDV.wav  (salida vocal)   y   SDI.wav  (salida instrumental)

con minima contaminacion (bleeding) y maxima conservacion del material
original (source fidelity).

ARQUITECTURA FUNDAMENTAL ---------------------------------------------------
    GUIDE DOMAIN -> MASK ANALYSIS -> CONSENSUS MASK
        -> ORIGINAL SOURCE DOMAIN RECONSTRUCTION

  1. GUIDE DOMAIN:   los stems MVSEP son guias ANALITICAS, jamas audio final.
  2. MASK ANALYSIS:  cada par vocal/instrumental produce una mascara
                     independiente:
                         Mv = V^power / (V^power + I^power + epsilon)
                         Mi = 1 - Mv
                     complementarias, rango [0, 1], sin clipping indep.
  3. CONSENSUS:      comparacion pairwise entre todas las mascaras,
                     mapa de confianza y desacuerdo por region TF,
                     fusion por: weighted_mean / median /
                     confidence_weighted_mean (default para la fase inicial
                     de investigacion).
  4. RECONSTRUCTION: SDV_STFT = Mix_STFT * Mv_consensus
                     SDI_STFT = Mix_STFT * (1 - Mv_consensus)
                     La FASE es SIEMPRE la del STFT complejo del Mix Original.
                     PROHIBIDO mezclar guides directamente como audio final.

IDENTIDAD DE RECONSTRUCCION (invariante analitica) -------------------------
Como Mi = 1 - Mv:
    SDV_STFT + SDI_STFT = Mix_STFT * (Mv + 1 - Mv) = Mix_STFT
La identidad es EXACTA por construccion en dominio float. El identity test
del spec (reconstruction_validation) mide unicamente el costo del camino
numerico (overlap-add + cuantizacion PCM), NO la calidad de separacion.
SNR post-WAV esperado: > 100 dB (con salida PCM_24). Un valor menor indica
un BUG del motor, no un fenomeno acustico.

QUE NO HACE ESTE SCRIPT (frontera declarada, spec scope_and_responsibility)
----------------------------------------------------------------------------
  - NO ejecuta MVSEP, NO descarga modelos, NO hace inferencia neuronal.
  - NO requiere API de MVSEP ni acceso a red.
  - NO selecciona modelos automaticamente.
  - NO usa modelos Premium/Ensemble (responsabilidad del usuario).
  - NO corrige alineacion automaticamente ("detectar no significa corregir").
  - NO normaliza, NO aplica gain/limiter/compressor/EQ/noise-reduction
    (ni al Mix ni a las salidas; estas funciones NO existen en el codigo).
  - NO optimiza mascaras complementarias por separado (Mi = 1 - Mv siempre).
  - NO declara ganadores globales automaticos (eso lo decide la escucha
    critica + MQR, no el script).
  - NO resamplea (SR requerido 44100 exacto; allow_resampling declarado
    pero NO implementado en v1 -> NotImplementedError).

DECISIONES DE DISENO ACTIVAS (reconciliadas con el operador) ---------------
  D1  Cobertura: frames TF sin cobertura de guides -> mascara neutra 0.5
      + warning registrado (la identidad SDV+SDI=Mix sigue exacta).
  D2  Mascaras: calculo en float64 (spec mask_precision), almacenamiento
      .npy en float32 (config MASK_SAVE_DTYPE; ~1/2 de disco).
  D3  Salida de audio: PCM_24 fijo por defecto (OUTPUT_SUBTYPE), sin dither.
  D4  Mix en FLOAT (32-bit float WAV): aceptado con nota registrada.
  D5  Desalineacion graduada: |off| <= 1 muestra ALIGNED; <= 10 ms WARNING;
      > 10 ms MISALIGNED -> aborto salvo confirmacion explicita
      (interactivo) o flag --allow-misaligned (scriptado).
  D6  Guide mono: permitido con warning (sin duplicacion automatica).
  D7  Visualizaciones PNG: flag --png, degradacion elegante sin matplotlib.
  D8  allow_resampling: declarado y NO implementado (frontera v1).
  D9  Suavizado de mascara: mediana 3x3 opcional, default OFF, medido si ON.
  D10 Modo single_file = un solo par (N=1): consenso trivialmente igual a la
      mascara individual, degeneracion documentada en el informe.
  D11 Median pairwise global por submuestreo uniforme en grilla (documentado
      como aproximacion); mean/RMSE/correlacion/perfiles: exactos streaming.
  D12 Archivo unico Python (Termux/Android friendly).
  D13 Manifest JSON opcional (--manifest) para reproducibilidad exacta.

MAPA DE SECCIONES DEL CODIGO -----------------------------------------------
   1. Header y contrato del motor (este docstring)
   2. Imports y verificacion de dependencias
   3. Configuracion global (constantes de spec + decisiones activas)
   4. Utilidades basicas (log, sha256, formato, json-safe)
   5. Probe y validacion de entradas (integridad, politicas SR/canales)
   6. Metadatos de pares + manifest + prompts interactivos
   7. Analisis de alineacion (xcorr 2 etapas, deteccion sin correccion)
   8. Analisis de escala de guides (metricas + factores, dominio mascara)
   9. Motor STFT (framing manual COLA-exacto + OLA streaming por chunks)
  10. Mascaras individuales (formula, smoothing opcional, estadisticas)
  11. Analisis multi-modelo (pairwise streaming, confidence, disagreement)
  12. Motor de consenso (3 metodos del spec)
  13. Reconstruccion (candidatos, OLA, true peak, escritura WAV)
  14. Metricas MQR streaming (identity, bleeding, fidelity, stereo)
  15. Orquestador single-pass chunked (pipeline principal)
  16. analysis.json builder (24 secciones exigidas por el spec)
  17. analysis.txt builder (informe legible)
  18. Self-test sintetico interno (--self-test)
  19. CLI (modos, manifest, interactivo) + main

PLATAFORMA OBJETIVO --------------------------------------------------------
Android + Termux. Dependencias requeridas (spec memory_and_android_strategy):
numpy, scipy, soundfile. Opcional: ffmpeg (NO requerido en v1).
Prohibidas por el spec: PyTorch, torchaudio, librosa (no se usan).
Estrategia de memoria: single-pass chunked streaming; los STFT completos
NUNCA se mantienen en RAM simultaneamente; las mascaras se escriben
incrementalmente a .npy via memmap.

USO -------------------------------------------------------------------------
  Interactivo:        python3 sdv_sdi_mqr_engine.py
  Manifiesto:         python3 sdv_sdi_mqr_engine.py --manifest exp.json \
                          --mode full_processing
  Solo analisis:      --mode analysis_only   (mascaras + informes, sin WAV)
  Plan previo:        --mode dry_run         (validacion + plan, sin computo)
  Un par:             --mode single_file     (N=1, degenerado documentado)
  Autodiagnostico:    --self-test
  PNGs:               --png
  Forzar desalineado: --allow-misaligned

NOTA PARA CONTINUACION POR OTRO MODELO (DeepSeek-V4) -----------------------
  - El contrato critico es la IDENTIDAD DE RECONSTRUCCION (ver arriba).
  - El pipeline es SINGLE-PASS: cualquier cambio debe preservar que cada
    chunk procese: lectura -> STFT -> mascara -> consenso -> reconstruccion
    -> metricas -> descarte, sin acumular STFT en RAM.
  - OlaStream.push() emite EXACTAMENTE F*hop muestras por chunk; el carry
    es de n_fft muestras. No alterar la geometria sin re-validar roundtrip
    con --self-test (error debe ser < 1e-12).
  - Las 24 secciones de analysis.json son contrato del spec; agregar campos
    nuevos al final de cada seccion, nunca renombrar los existentes.
  - Convencion de offset de alineacion: lag > 0 significa que el CONTENIDO
    del guide aparece lag muestras DESPUES en el mix (mix[t] ~ guide[t-lag]);
    para alinear habria que ADELANTAR el guide lag muestras. El motor nunca
    aplica esa correccion (spec: detectar no significa corregir).
============================================================================
"""

# ============================================================================
# SECCION 2: IMPORTS Y VERIFICACION DE DEPENDENCIAS
# ============================================================================

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

MIN_PYTHON = (3, 8)
if sys.version_info < MIN_PYTHON:
    sys.stderr.write(
        "[FATAL] Python >= %d.%d requerido. Detectado: %s\n"
        % (MIN_PYTHON[0], MIN_PYTHON[1], sys.version.split()[0])
    )
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    sys.stderr.write("[FATAL] numpy no disponible. Instalar: pip install numpy\n")
    sys.exit(1)

try:
    from scipy.fft import rfft, irfft
    from scipy.signal import get_window, resample_poly
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False
    sys.stderr.write(
        "[FATAL] scipy no disponible. El spec lo exige "
        "(memory_and_android_strategy.required_libraries).\n"
        "        Instalar: pip install scipy\n"
    )
    sys.exit(1)

try:
    import soundfile as sf
except ImportError:
    sys.stderr.write(
        "[FATAL] soundfile no disponible. El spec lo exige.\n"
        "        Instalar: pip install soundfile\n"
    )
    sys.exit(1)

# matplotlib es OPCIONAL (spec outputs.optional_visualizations, decision D7)
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    MATPLOTLIB_OK = True
except ImportError:
    MATPLOTLIB_OK = False


# ============================================================================
# SECCION 3: CONFIGURACION GLOBAL (constantes del spec + decisiones activas)
# ============================================================================

ENGINE_NAME = "SDV-SDI MQR Engine"
ENGINE_VERSION = "1.0.0"
SPEC_NAME = "Prompt Mask MVSEP.json"
SPEC_VERSION = "1.3.0"

# --- Entradas (spec input_architecture / input_validation) ------------------
REQUIRED_SAMPLE_RATE = 44100          # mix y guides: reject_if_mismatch
MIX_ALLOWED_EXTENSIONS = (".wav", ".flac")  # 6G: contenedor verificado
GUIDE_ALLOWED_EXTENSIONS = (".wav", ".flac")
MIX_ALLOWED_SUBTYPES = ("PCM_16", "PCM_24", "PCM_32", "FLOAT")  # D4: FLOAT ok con nota
GUIDE_ALLOWED_SUBTYPES = None         # None = cualquier subtipo WAV/FLAC legible
GUIDE_MAX_CHANNELS = 2                # >2 canales: reject (sin politica en spec)
MIX_MAX_CHANNELS = 2

# --- STFT (spec stft_configuration) ------------------------------------------
N_FFT_ALLOWED = (2048, 4096, 8192)
N_FFT_DEFAULT = 4096
HOP_LENGTH_DEFAULT = 1024             # default del spec (n_fft/4, COLA exacta)
STFT_WINDOW = "hann"
STFT_CENTER = True                    # implementado como pad de n_fft//2
MASK_PRECISION = np.float64           # spec: float64
SOURCE_PRECISION = np.float64         # spec: float32|float64 -> v1 usa float64

# --- Mascaras (spec individual_model_masks) ----------------------------------
POWER_DEFAULT = 2.0                   # power configurable
EPSILON_DEFAULT = 1e-9                # epsilon: small_positive_float
NEUTRAL_MASK_VALUE = 0.5              # D1: cobertura fuera de guides
SMOOTHING_DEFAULT = False             # D9
SMOOTHING_KERNEL = (3, 3)             # median filter 2D (freq, time)
MASK_SAVE_DTYPE = np.float32          # D2 (calculo en float64)

# --- Consenso (spec consensus_engine) ----------------------------------------
CONSENSUS_METHODS = ("weighted_mean", "median", "confidence_weighted_mean")
CONSENSUS_DEFAULT = "confidence_weighted_mean"
CONFIDENCE_BETA = 1.0                 # exponente de pesos c_k^beta
CONFIDENCE_WEIGHT_FLOOR = 1e-6        # piso anti-deadlock

# --- Alineacion (spec alignment_analysis, decision D5) -----------------------
ALIGN_COARSE_DECIMATION = 8           # envolvente decimada x8 (~5512 Hz)
ALIGN_ENVELOPE_MS = 50.0              # moving RMS de la envolvente
ALIGN_SEARCH_SECONDS = 30.0           # busqueda gruesa +-30 s
ALIGN_REFINE_HALFSPAN = 12            # refinado +-12 muestras alrededor del coarse
ALIGNED_TOL_SAMPLES = 1               # |off| <= 1 muestra -> ALIGNED
MISALIGNED_TOL_MS = 10.0              # |off| <= 10 ms -> WARNING; > -> MISALIGNED

# --- Escala de guides (spec guide_scale_analysis) -----------------------------
GUIDE_SCALE_COMPENSATION = "none"     # "none" | "rms_match" (solo dominio mascara)

# --- Motor de ejecucion (spec memory_and_android_strategy) --------------------
CHUNK_FRAMES_DEFAULT = 256            # frames STFT por chunk (~5.9 s audio)
MAX_PAIRS = 16                        # guard sanitario (spec: max configurable)
PAIRWISE_SUBSAMPLE_TARGET = 4_000_000 # elementos por combinacion (D11)
PAIRWISE_PROFILE_ACCUM_DTYPE = np.float64

# --- Analisis espectral -------------------------------------------------------
BAND_EDGES_HZ = (0.0, 100.0, 200.0, 500.0, 1000.0, 2000.0,
                 4000.0, 8000.0, 12000.0, 16000.0, 20000.0, 22050.0)
TRUEPEAK_UPSAMPLE = 4                 # decision previa: 4x oversampling BS.1770-style
TRUEPEAK_CONTEXT = 256                # contexto entre chunks para el filtro FIR

# --- Salidas (spec outputs / decision D3) -------------------------------------
OUTPUT_SUBTYPE = "FLOAT"   # 32-bit float: preserva muestras >1.0 sin clipping
OUTPUT_AUDIO_BLOCKSIZE = 1 << 18      # bloque de escritura/lectura post-wav
IDENTITY_SNR_EXPECTED_DB = 100.0      # umbral de sanidad (no un veredicto)

# --- Duracion (spec input_validation.duration) --------------------------------
DURATION_WARN_SAMPLES = 1             # > 1 muestra de diferencia -> warning

# --- Modos CLI (spec cli.required_modes) --------------------------------------
MODE_DRY_RUN = "dry_run"
MODE_ANALYSIS_ONLY = "analysis_only"
MODE_SINGLE_FILE = "single_file"
MODE_FULL_PROCESSING = "full_processing"
REQUIRED_MODES = (MODE_DRY_RUN, MODE_ANALYSIS_ONLY, MODE_SINGLE_FILE,
                  MODE_FULL_PROCESSING)

# --- Interpretacion cientifica (spec scientific_status, verbatim) ------------
CLAIMS_NOT_ALLOWED = (
    "perfect separation",
    "perfect phase separation",
    "lossless source recovery",
    "universal superiority of consensus",
    "universal superiority of any individual model",
    "proof that more models always improve the result",
)

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_PROCESSING = 2
EXIT_ABORTED = 130


# ============================================================================
# SECCION 4: UTILIDADES BASICAS
# ============================================================================

class Tee:
    """Duplica stdout hacia un archivo de log de corrida (engine_log.txt)."""

    def __init__(self, path=None):
        self._console = sys.stdout
        self._file = None
        if path is not None:
            try:
                self._file = open(path, "w", encoding="utf-8")
            except OSError as exc:
                self._console.write("[WARN] No se pudo abrir log %s: %s\n" % (path, exc))

    def write(self, data):
        self._console.write(data)
        if self._file is not None:
            try:
                self._file.write(data)
                self._file.flush()
            except OSError:
                pass

    def flush(self):
        self._console.flush()
        if self._file is not None:
            try:
                self._file.flush()
            except OSError:
                pass

    def close(self):
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
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
    """Log con timestamp relativo de corrida (segundos desde el inicio)."""
    elapsed = time.monotonic() - _G_T0
    print("[%9.2fs] %s" % (elapsed, msg), flush=True)


def utc_now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path, blocksize=1 << 20):
    """SHA-256 por streaming (spec input_validation.integrity.calculate_sha256)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(blocksize)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def fmt_size(num_bytes):
    if num_bytes >= 1 << 30:
        return "%.2f GiB" % (num_bytes / float(1 << 30))
    if num_bytes >= 1 << 20:
        return "%.2f MiB" % (num_bytes / float(1 << 20))
    if num_bytes >= 1 << 10:
        return "%.2f KiB" % (num_bytes / float(1 << 10))
    return "%d B" % num_bytes


def safe_name(text, max_len=64):
    """Sanea un identificador para uso en nombres de archivo."""
    out = []
    for ch in str(text):
        if ch.isalnum() or ch in "-_.":
            out.append(ch)
        else:
            out.append("_")
    name = "".join(out).strip("._") or "unnamed"
    return name[:max_len]


def json_safe(obj):
    """Convierte tipos numpy a nativos para json.dump; NaN/inf -> None.
    (Nunca fabrica valores: los no finitos se declaran como null y el
    validation_status registra la incidencia.)"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, bool)):
        return obj
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if (math.isnan(val) or math.isinf(val)) else val
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [json_safe(x) for x in obj.tolist()]
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    return str(obj)


def next_pow2(n):
    p = 1
    while p < n:
        p <<= 1
    return p


def mono_downmix(x2d):
    """(S, ch) -> (S,) mono float64. Promedio de canales.
    Para guide mono (1 canal) es identidad. Sin duplicaciones artificiales."""
    arr = np.asarray(x2d, dtype=np.float64)
    if arr.ndim == 1:
        return arr
    if arr.shape[1] == 1:
        return arr[:, 0]
    return arr.mean(axis=1)


# ============================================================================
# SECCION 5: PROBE Y VALIDACION DE ENTRADAS
# ============================================================================

@dataclass
class FileInfo:
    path: str
    role: str                  # "mix" | "vocal_guide" | "instrumental_guide"
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


def _nominal_bit_depth(subtype):
    table = {
        "PCM_U8": 8, "PCM_S8": 8,
        "PCM_16": 16, "PCM_24": 24, "PCM_32": 32,
        "FLOAT": 32, "DOUBLE": 64,
    }
    return table.get(subtype, 0)


from audio_integridad_6g import (container_of as _container_6g,
                              verify_audio as _verify_audio_6g)
from lectura_segura_6g1 import (MixCambiado as _MixCambiado_6g1,
                                 abrir_mix as _abrir_mix_6g1,
                                 abortar_6g1 as _abortar_6g1,
                                 VerificacionFallida6G1 as _VerifFallida_6g1,
                                 registrar_propio_6g1 as _registrar_propio_6g1,
                                 reiniciar_registro_6g1 as _reiniciar_registro_6g1,
                                 acreditar_dir_6g1 as _acreditar_dir_6g1,
                                 publicar_dir_6g1 as _publicar_dir_6g1)

from atribucion_6f import (measure, verify_wave, alignment_gate,
                        analyze_files as _analyze_files_6f,
                        combine_channels as _combine_6f)

def probe_file(path, role):
    """Lee metadatos con soundfile y calcula integridad (spec
    input_validation.integrity). NO modifica el archivo (solo lectura)."""
    info = FileInfo(path=os.path.abspath(path), role=role)
    if not os.path.isfile(path):
        info.errors.append("archivo no encontrado: %s" % path)
        return info
    info.exists = True
    info.size_bytes = os.path.getsize(path)
    try:
        sfi = sf.info(path)
        _verify_audio_6g(path, sfi)
    except Exception as exc:  # soundfile error generico
        info.errors.append("soundfile no pudo abrir el archivo: %s" % exc)
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
        info.errors.append("fallo calculando sha256: %s" % exc)
    info.valid = len(info.errors) == 0
    return info


def validate_mix(info):
    """Politica estricta del spec para el Mix Original:
    WAV, 44100 Hz exacto (reject_if_mismatch), 16/24/32-bit (FLOAT aceptado
    con nota, decision D4), canales <= 2 (mono -> warning)."""
    if not info.valid:
        return info
    ext = os.path.splitext(info.path)[1].lower()
    if ext not in MIX_ALLOWED_EXTENSIONS:
        info.errors.append("mix: formato %r fuera de politica (solo WAV)" % ext)
    if info.sample_rate != REQUIRED_SAMPLE_RATE:
        info.errors.append(
            "mix: sample_rate=%d != %d requerido (policy reject_if_mismatch)"
            % (info.sample_rate, REQUIRED_SAMPLE_RATE)
        )
    if info.channels < 1 or info.channels > MIX_MAX_CHANNELS:
        info.errors.append(
            "mix: canales=%d fuera de politica (1-2; >2 sin politica en spec)"
            % info.channels
        )
    elif info.channels == 1:
        info.warnings.append("mix es mono (se esperaba preferentemente stereo)")
    if info.subtype not in MIX_ALLOWED_SUBTYPES:
        info.errors.append(
            "mix: subtype=%r fuera de politica %s"
            % (info.subtype, str(MIX_ALLOWED_SUBTYPES))
        )
    elif info.subtype == "FLOAT":
        info.notes.append("mix es 32-bit float (aceptado con nota, decision D4)")
    info.valid = len(info.errors) == 0
    return info


def validate_guide(info):
    """Politica estricta para guides: WAV o FLAC, 44100 Hz (reject_by_default,
    allow_resampling=false -> D8 sin resampling en v1), canales <= 2
    (mono -> warning, decision D6)."""
    if not info.valid:
        return info
    ext = os.path.splitext(info.path)[1].lower()
    if ext not in GUIDE_ALLOWED_EXTENSIONS:
        info.errors.append(
            "guide: formato %r fuera de politica (solo WAV/FLAC)" % ext
        )
    if info.sample_rate != REQUIRED_SAMPLE_RATE:
        info.errors.append(
            "guide: sample_rate=%d != %d requerido (policy reject_by_default; "
            "allow_resampling NO implementado en v1)"
            % (info.sample_rate, REQUIRED_SAMPLE_RATE)
        )
    if info.channels < 1 or info.channels > GUIDE_MAX_CHANNELS:
        info.errors.append(
            "guide: canales=%d fuera de politica (1-2)" % info.channels
        )
    elif info.channels == 1:
        info.warnings.append("guide mono (permitido con warning, decision D6)")
    info.valid = len(info.errors) == 0
    return info


def compare_durations(mix_info, guide_info):
    """Diferencia de duracion en muestras y ms (spec input_validation.duration:
    verify_all_files + warning_if_difference; sin trimming automatico)."""
    diff_samples = guide_info.frames - mix_info.frames
    diff_ms = 1000.0 * diff_samples / float(REQUIRED_SAMPLE_RATE)
    rec = {
        "guide": os.path.basename(guide_info.path),
        "guide_frames": guide_info.frames,
        "mix_frames": mix_info.frames,
        "difference_samples": diff_samples,
        "difference_ms": diff_ms,
        "status": "ok" if abs(diff_samples) <= DURATION_WARN_SAMPLES else "warning",
    }
    return rec


# ============================================================================
# SECCION 6: METADATOS DE PARES + MANIFEST + PROMPTS INTERACTIVOS
# ============================================================================

@dataclass
class PairMeta:
    pair_id: str
    family: str
    variant: str
    configuration: str
    vocal_path: str
    instrumental_path: str
    source: str = "MVSEP"
    overlap: str = ""          # spec polarformer_policy: must_be_recorded
    vocal: FileInfo = None
    instrumental: FileInfo = None

    def as_dict(self):
        return {
            "pair_id": self.pair_id,
            "family": self.family,
            "variant": self.variant,
            "configuration": self.configuration,
            "vocal_guide": os.path.abspath(self.vocal_path),
            "instrumental_guide": os.path.abspath(self.instrumental_path),
            "source": self.source,
            "overlap": self.overlap,
        }


def load_manifest(manifest_path):
    """Carga el manifest (decision D13). Formato:
    {
      "mix_original": "ruta/al/mix.wav",
      "pairs": [
        {"pair_id": "guide_pair_01", "family": "BS_Roformer",
         "variant": "USER_DEFINED", "configuration": "USER_DEFINED",
         "vocal_guide": "v01.wav", "instrumental_guide": "i01.wav",
         "source": "MVSEP", "overlap": "USER_DEFINED"}, ...
      ]
    }
    Las rutas relativas se resuelven contra el directorio del manifest.
    La identidad del modelo JAMAS se infiere del nombre de archivo
    (spec file_selection.critical_rule): proviene solo del manifest/prompt."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    base = os.path.dirname(os.path.abspath(manifest_path))

    def resolve(p):
        return p if os.path.isabs(p) else os.path.join(base, p)

    mix_path = resolve(data["mix_original"])
    pairs = []
    for i, item in enumerate(data.get("pairs", []), start=1):
        pair_id = str(item.get("pair_id") or ("guide_pair_%02d" % i))
        pairs.append(PairMeta(
            pair_id=pair_id,
            family=str(item.get("family") or "USER_DEFINED"),
            variant=str(item.get("variant") or "USER_DEFINED"),
            configuration=str(item.get("configuration") or "USER_DEFINED"),
            vocal_path=resolve(item["vocal_guide"]),
            instrumental_path=resolve(item["instrumental_guide"]),
            source=str(item.get("source") or "MVSEP"),
            overlap=str(item.get("overlap") or ""),
        ))
    return mix_path, pairs


def _prompt_required(label, default=None):
    while True:
        suffix = " [%s]" % default if default else ""
        try:
            val = input("  %s%s: " % (label, suffix)).strip()
        except EOFError:
            sys.exit(EXIT_ABORTED)
        if val:
            return val
        if default:
            return default
        print("    valor obligatorio; reintentar.")


def _prompt_optional(label, default=""):
    try:
        val = input("  %s [%s]: " % (label, default)).strip()
    except EOFError:
        sys.exit(EXIT_ABORTED)
    return val or default


def interactive_collect_inputs(mode):
    """Flujo interactivo del spec cli.workflow (pasos 1-4):
    select_mix_original -> define_number_of_guide_pairs ->
    per pair: vocal/instrumental/family/variant/configuration."""
    print("")
    print("=" * 76)
    print("%s v%s  (spec %s v%s)" % (ENGINE_NAME, ENGINE_VERSION,
                                     SPEC_NAME, SPEC_VERSION))
    print("=" * 76)
    print("Modo: %s" % mode)
    print("")
    print("[Paso 1] Mix Original (WAV 44100 Hz; unica fuente de audio final)")
    mix_path = _prompt_required("Ruta del Mix Original")
    print("")
    print("[Paso 2] Numero de pares de guides (min 1, recomendado 3, max %d)"
          % MAX_PAIRS)
    while True:
        try:
            n = int(_prompt_required("Numero de pares", "3"))
            if 1 <= n <= MAX_PAIRS:
                break
        except ValueError:
            pass
        print("    valor invalido; enter 1-%d." % MAX_PAIRS)
    print("")
    pairs = []
    for i in range(1, n + 1):
        print("[Paso 3] Par %d/%d" % (i, n))
        default_id = "guide_pair_%02d" % i
        pair_id = _prompt_optional("pair_id", default_id)
        family = _prompt_required("  family (ej. BS_Roformer|MelBand_Roformer|"
                                  "BS_PolarFormer|otra)")
        variant = _prompt_required("  variant (USER_DEFINED; ej. '124 bands')")
        configuration = _prompt_required("  configuration (USER_DEFINED; "
                                         "ej. overlap=8)")
        overlap = _prompt_optional("  overlap (opcional; se registra, nunca "
                                   "se asume)")
        vocal = _prompt_required("  vocal_guide (WAV/FLAC 44100)")
        instrumental = _prompt_required("  instrumental_guide (WAV/FLAC 44100)")
        source = _prompt_optional("  source", "MVSEP")
        pairs.append(PairMeta(
            pair_id=pair_id, family=family, variant=variant,
            configuration=configuration, vocal_path=vocal,
            instrumental_path=instrumental, source=source, overlap=overlap,
        ))
        print("")
    return mix_path, pairs


# ============================================================================
# SECCION 7: ANALISIS DE ALINEACION (deteccion SIN correccion)
# ============================================================================

def _moving_rms(x, win_samples):
    """RMS movil por cumsum (box filter exacto, O(N)). x: (S,) float64."""
    x2 = np.square(x)
    csum = np.concatenate(([0.0], np.cumsum(x2)))
    half = win_samples // 2
    S = len(x2)
    idx_hi = np.minimum(np.arange(S) + half, S)
    idx_lo = np.maximum(np.arange(S) - (win_samples - half), 0)
    energy = (csum[idx_hi] - csum[idx_lo]) / np.maximum(idx_hi - idx_lo, 1)
    return np.sqrt(np.maximum(energy, 0.0))


def _decimate_block_mean(x, factor):
    """Decimacion por media de bloques (anti-aliasing generoso para
    envolventes; resolucion temporal factor muestras)."""
    usable = (len(x) // factor) * factor
    if usable <= 0:
        return np.zeros(1, dtype=np.float32)
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
    return [(0,len(a),0,len(b))], {'coverage':'full_files'}


def analyze_alignment(mix_info, guide_info, mix_mono_cache=None):
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

# ============================================================================
# SECCION 8: ANALISIS DE ESCALA DE GUIDES (solo metricas y factores)
# ============================================================================

def stream_level_stats(path, limit_frames=None):
    """RMS/peak/energy/crest por streaming (sin cargar el archivo completo)."""
    total_sq = 0.0
    total_n = 0
    peak = 0.0
    with sf.SoundFile(path) as h:
        if limit_frames is not None:
            h.seek(0)
        remaining = limit_frames if limit_frames is not None else h.frames
        while remaining > 0:
            block = h.read(min(1 << 20, remaining), dtype="float64",
                           always_2d=True)
            if block.shape[0] == 0:
                break
            m = mono_downmix(block)
            total_sq += float(np.square(m).sum())
            total_n += len(m)
            peak = max(peak, float(np.abs(block).max()))
            remaining -= block.shape[0]
    rms = math.sqrt(total_sq / total_n) if total_n > 0 else 0.0
    energy = total_sq  # suma de cuadrados (unidades normalizadas)
    crest = (peak / rms) if rms > 0 else None
    return {
        "rms": rms,
        "peak": peak,
        "peak_dbfs": 20.0 * math.log10(peak) if peak > 0 else None,
        "energy": energy,
        "crest_factor": crest,
        "frames_measured": total_n,
    }


def analyze_guide_scale(mix_info, pair):
    """Metricas de escala por par (spec guide_scale_analysis):
    RMS, peak, energy y robust_scale_estimate por guide contra el Mix,
    medidos en la region comun [0, min(N_mix, N_guide)).
    Los factores se aplican SOLO dentro del calculo de la mascara
    (scale_compensation.domain = mask_calculation_only) y SOLO si
    GUIDE_SCALE_COMPENSATION == 'rms_match'. Los archivos jamas se tocan."""
    rec = {"pair_id": pair.pair_id, "family": pair.family,
           "variant": pair.variant, "compensation_policy":
           GUIDE_SCALE_COMPENSATION}
    with _abrir_mix_6g1(mix_info.path, mix_info.sha256) as _hm6g1:
        mix_common = stream_level_stats(_hm6g1.ruta_lectura(),
                                        limit_frames=mix_info.frames)
    rec["mix_common_region"] = mix_common
    factors = {}
    for role in ("vocal", "instrumental"):
        info = pair.vocal if role == "vocal" else pair.instrumental
        common_frames = min(mix_info.frames, info.frames)
        stats = stream_level_stats(info.path, limit_frames=common_frames)
        rec[role] = stats
        if stats["rms"] > 0 and mix_common["rms"] > 0:
            g = math.sqrt(mix_common["rms"] / stats["rms"])
        else:
            g = 1.0
        factors[role] = g
    rec["robust_scale_estimate"] = {
        "vocal_factor": factors["vocal"],
        "instrumental_factor": factors["instrumental"],
        "definition": "sqrt(rms_mix_common / rms_guide_common) en region comun",
        "applied_to_mask_domain_only": True,
        "files_modified": False,
    }
    if GUIDE_SCALE_COMPENSATION == "rms_match":
        rec["applied_factors"] = factors
    else:
        rec["applied_factors"] = {"vocal": 1.0, "instrumental": 1.0}
        rec["note"] = ("compensacion deshabilitada (politica 'none'): la "
                       "formula de mascara es un ratio invariante a escalado "
                       "comun del par; factores registrados para auditoria")
    return rec, rec["applied_factors"]


# ============================================================================
# SECCION 9: MOTOR STFT (framing manual COLA-exacto + OLA streaming)
# ============================================================================

class FramePlan:
    """Plan de frames STFT center=True (pad = n_fft//2), cobertura garantizada
    de TODAS las muestras del archivo. Implementacion NumPy-compatible del
    spec (stft_configuration.alternative) con backend scipy.fft.
    Invariante COLA: con hann periodica y hop = n_fft/4, la suma de ventanas
    al cuadrado es constante 1.5 en el interior -> OLA exacto."""

    def __init__(self, n_samples, n_fft, hop):
        if n_fft % hop != 0:
            raise ValueError("n_fft debe ser multiplo de hop")
        if n_fft not in N_FFT_ALLOWED:
            raise ValueError("n_fft %d fuera de los permitidos por el spec %s"
                             % (n_fft, str(N_FFT_ALLOWED)))
        self.N = int(n_samples)
        self.n_fft = int(n_fft)
        self.hop = int(hop)
        self.pad = self.n_fft // 2
        last_needed = self.pad + self.N - 1
        self.K = last_needed // self.hop + 1
        self.window = get_window(STFT_WINDOW, self.n_fft,
                                 fftbins=True).astype(np.float64)
        self.win_sq = self.window * self.window
        self.bins = self.n_fft // 2 + 1

    def span_for_frames(self, f0, f1):
        """Coords de archivo [start, end) necesarias para frames [f0, f1)."""
        start = f0 * self.hop - self.pad
        end = (f1 - 1) * self.hop + self.n_fft - self.pad
        return start, end


def read_span(handle, start, end):
    """Lee [start, end) en coords de archivo con zero-pad fuera de rango.
    Devuelve (S, ch) float64. NO modifica el archivo (solo lectura)."""
    S = end - start
    channels = handle.channels
    if S <= 0:
        return np.zeros((0, channels), dtype=np.float64)
    out = np.zeros((S, channels), dtype=np.float64)
    a = max(start, 0)
    b = min(end, handle.frames)
    if b > a:
        handle.seek(a)
        data = handle.read(b - a, dtype="float64", always_2d=True)
        out[a - start:b - start, :] = data
    return out


def stft_span_frames(x2d, n_frames, plan):
    """STFT de un span ya leido. x2d: (S, ch) con
    S >= (n_frames-1)*hop + n_fft. Frame i usa x2d[i*hop : i*hop+n_fft].
    Devuelve (ch, bins, n_frames) complex128."""
    win = plan.window
    sw = np.lib.stride_tricks.sliding_window_view(x2d, plan.n_fft, axis=0)
    fr = sw[::plan.hop][:n_frames]            # (F, ch, n_fft)
    fr = np.ascontiguousarray(fr.transpose(1, 0, 2))   # (ch, F, n_fft)
    X = rfft(fr * win, n=plan.n_fft, axis=-1)          # (ch, F, bins)
    return np.ascontiguousarray(X.transpose(0, 2, 1))  # (ch, bins, F)


class OlaStream:
    """Overlap-add streaming EXACTO por chunks.
    Contrato: push() con el STFT de F frames emite EXACTAMENTE F*hop
    muestras por canal (coords de archivo, recortadas a [0, N)).
    Carry interno: n_fft muestras. La normalizacion usa la suma real de
    ventanas al cuadrado (hann/hop=n_fft/4 -> 1.5 en el interior).
    El roundtrip stft->istft es exacto (~1e-15): lo verifica --self-test."""

    def __init__(self, plan, n_channels, writer=None, label=""):
        self.plan = plan
        self.ch = n_channels
        self.writer = writer
        self.label = label
        self.carry_y = np.zeros((plan.n_fft, n_channels), dtype=np.float64)
        self.carry_w = np.zeros(plan.n_fft, dtype=np.float64)
        self.pos = 0
        self.emitted_frames = 0

    def push(self, X):
        """X: (ch, bins, F) complex. Devuelve (audio_out, a, b):
        audio_out = (S, ch) emitido en coords de archivo [a, b) (o None)."""
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
            seg = irfft(X[:, :, i], n=n_fft, axis=-1)      # (ch, n_fft)
            y[i * hop:i * hop + n_fft] += seg.T * win[:, None]
            w[i * hop:i * hop + n_fft] += plan.win_sq
        emitted_len = F * hop
        w_emit = w[:emitted_len]
        safe = np.where(w_emit > 1e-12, w_emit, 1.0)
        y_emit = y[:emitted_len] / safe[:, None]
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

    def flush(self):
        """Emite el carry final (defensivo; con la geometria estandar todo el
        contenido util ya fue emitido por push)."""
        plan = self.plan
        w = self.carry_w
        safe = np.where(w > 1e-12, w, 1.0)
        y_emit = self.carry_y / safe[:, None]
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


def read_span_from_array(x2d, start, end):
    """Equivalente a read_span pero sobre un array en memoria (self-test)."""
    S = end - start
    ch = x2d.shape[1] if x2d.ndim > 1 else 1
    out = np.zeros((S, ch), dtype=np.float64)
    a = max(start, 0)
    b = min(end, len(x2d))
    if b > a:
        seg = x2d[a:b]
        if seg.ndim == 1:
            seg = seg[:, None]
        out[a - start:b - start, :] = seg
    return out


# ============================================================================
# SECCION 10: MASCARAS INDIVIDUALES (spec individual_model_masks)
# ============================================================================

def compute_vocal_mask(v_mag, i_mag, power, epsilon):
    """Mv = V^power / (V^power + I^power + epsilon)
    Rango [0, 1). Mi = 1 - Mv (complementariedad por construccion;
    NUNCA se optimiza Mi independientemente: spec
    implementation_prohibitions.independently_optimize_complementary_masks).
    v_mag/i_mag: (bins, F) float64 magnitudes."""
    vp = np.power(v_mag, power)
    ip = np.power(i_mag, power)
    return vp / (vp + ip + epsilon)


def apply_optional_smoothing(mask, enabled):
    """D9: suavizado opcional (mediana 2D 3x3), default OFF; si se aplica,
    se MIDE (spec: must_be_measured) devolviendo el cambio medio absoluto."""
    if not enabled:
        return mask, None
    try:
        from scipy.ndimage import median_filter
    except ImportError:
        return mask, {"error": "scipy.ndimage no disponible"}
    smoothed = median_filter(mask, size=SMOOTHING_KERNEL, mode="nearest")
    delta = float(np.abs(smoothed - mask).mean())
    return smoothed, {
        "kernel": list(SMOOTHING_KERNEL),
        "mode": "median",
        "mean_abs_change": delta,
        "enabled": True,
    }


def mask_stats_stream_init():
    return {"sum": 0.0, "sumsq": 0.0, "n": 0, "min": float("inf"),
            "max": float("-inf"), "sub": []}


def mask_stats_stream_update(acc, mask, stride):
    acc["sum"] += float(mask.sum())
    acc["sumsq"] += float(np.square(mask).sum())
    acc["n"] += mask.size
    acc["min"] = min(acc["min"], float(mask.min()))
    acc["max"] = max(acc["max"], float(mask.max()))
    if stride > 1:
        acc["sub"].append(mask[::stride, ::stride].ravel())


def mask_stats_stream_finalize(acc):
    n = max(acc["n"], 1)
    mean = acc["sum"] / n
    var = max(acc["sumsq"] / n - mean * mean, 0.0)
    out = {
        "mean": mean,
        "std": math.sqrt(var),
        "min": acc["min"] if acc["n"] else 0.0,
        "max": acc["max"] if acc["n"] else 0.0,
        "n_bins": acc["n"],
    }
    if acc["sub"]:
        sub = np.concatenate(acc["sub"])
        out["median"] = float(np.median(sub))
        out["p01"] = float(np.percentile(sub, 1))
        out["p99"] = float(np.percentile(sub, 99))
    else:
        out["median"] = out["mean"]
        out["p01"] = out["min"]
        out["p99"] = out["max"]
    return out


# ============================================================================
# SECCION 11: ANALISIS MULTI-MODELO (pairwise, confidence, disagreement)
# ============================================================================

def compute_pairwise_stride(K_total, bins, num_combos):
    """Stride de submuestreo para la median pairwise (D11): presupuesto
    global ~64 MiB en float32; min/RMSE/correlacion/perfiles son EXACTOS
    (streaming); solo la median es aproximada y se declara como tal."""
    budget_elements = 16_000_000
    per_combo = max(100_000, budget_elements // max(1, num_combos))
    stride = math.ceil(math.sqrt(float(K_total * bins) / per_combo))
    return max(2, int(stride))


class PairwiseAccum:
    """Acumulador streaming para una combinacion (a, b) de mascaras.
    Metricas del spec (multi_model_analysis.pairwise_analysis):
      - mean_absolute_mask_difference (exacto)
      - RMSE_mask_difference (exacto)
      - correlation (exacto, Pearson global)
      - median_absolute_difference (submuestreo uniforme, D11)
      - frequency_dependent_difference (perfil por bin, exacto)
      - time_dependent_difference (perfil por frame, exacto)
    """

    def __init__(self, bins, K_total):
        self.bins = bins
        self.per_bin_sum = np.zeros(bins, dtype=np.float64)
        self.per_frame_sum = np.zeros(K_total, dtype=np.float64)
        self.sub = []
        self.sum_abs = 0.0
        self.sum_sq = 0.0
        self.n = 0
        self.sa = 0.0
        self.sb = 0.0
        self.saa = 0.0
        self.sbb = 0.0
        self.sab = 0.0

    def update(self, a, b, f0, stride):
        d = np.abs(a - b)
        self.sum_abs += float(d.sum())
        self.sum_sq += float(np.square(d).sum())
        self.n += d.size
        self.sa += float(a.sum())
        self.sb += float(b.sum())
        self.saa += float(np.square(a).sum())
        self.sbb += float(np.square(b).sum())
        self.sab += float((a * b).sum())
        self.per_bin_sum += d.sum(axis=1)
        self.per_frame_sum[f0:f0 + d.shape[1]] += d.sum(axis=0)
        if stride > 1:
            self.sub.append(d[::stride, ::stride].ravel())

    def finalize(self, pair_a_id, pair_b_id, n_frames_total):
        n = max(self.n, 1)
        mean_abs = self.sum_abs / n
        rmse = math.sqrt(self.sum_sq / n)
        cov = self.sab / n - (self.sa / n) * (self.sb / n)
        va = max(self.saa / n - (self.sa / n) ** 2, 0.0)
        vb = max(self.sbb / n - (self.sb / n) ** 2, 0.0)
        corr = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0
        median_val = None
        if self.sub:
            median_val = float(np.median(np.concatenate(self.sub)))
        return {
            "pair_a": pair_a_id,
            "pair_b": pair_b_id,
            "mean_absolute_mask_difference": mean_abs,
            "rmse_mask_difference": rmse,
            "correlation": corr,
            "median_absolute_difference": median_val,
            "median_method": "uniform_grid_subsample_approximation",
            "n_bins_compared": self.n,
            "frequency_dependent_difference_per_bin_mean":
                (self.per_bin_sum / max(n_frames_total, 1)).tolist(),
            "time_dependent_difference_per_frame_mean":
                (self.per_frame_sum / max(self.bins, 1)).tolist(),
        }


class GlobalMaskAccum:
    """Acumulador streaming para mapas globales (confidence, disagreement):
    media exacta + submuestreo para percentiles."""

    def __init__(self, stride):
        self.stride = stride
        self.sum = 0.0
        self.sumsq = 0.0
        self.n = 0
        self.sub = []

    def update(self, chunk_map):
        self.sum += float(chunk_map.sum())
        self.sumsq += float(np.square(chunk_map).sum())
        self.n += chunk_map.size
        if self.stride > 1:
            self.sub.append(chunk_map[::self.stride, ::self.stride].ravel())

    def finalize(self):
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


def confidence_and_disagreement(masks):
    """Mapas por region TF (spec confidence_model + model_disagreement):
      - disagreement_map = std entre mascaras por bin (N>=2)
      - confidence_map   = clip(1 - 2*std, 0, 1)  (concordancia entre modelos;
        NO verdad fisica absoluta: spec confidence_model.principle)
      - c_k = agreement leave-one-out por modelo: 1 - mean_{j!=k}|Mv_k - Mv_j|
    Caso degenerado N=1 (D10): std=0 -> confidence 1.0 constante, c_1 = 1.0;
    se documenta en el informe como medible pero trivial."""
    stack = np.stack(masks, axis=0)  # (N, bins, F) float64
    n_models = stack.shape[0]
    if n_models == 1:
        conf = np.ones_like(stack[0])
        dis = np.zeros_like(stack[0])
        c_k = np.ones_like(stack)
        return conf, dis, c_k
    dis = stack.std(axis=0, ddof=0)
    conf = np.clip(1.0 - 2.0 * dis, 0.0, 1.0)
    # leave-one-out agreement por modelo:
    c_k = np.empty_like(stack)
    for k in range(n_models):
        others = [j for j in range(n_models) if j != k]
        dsum = np.zeros_like(stack[0])
        for j in others:
            dsum += np.abs(stack[k] - stack[j])
        c_k[k] = 1.0 - dsum / len(others)
    return conf, dis, c_k


# ============================================================================
# SECCION 12: MOTOR DE CONSENSO (spec consensus_engine)
# ============================================================================

def consensus_from_masks(masks, c_k, beta=CONFIDENCE_BETA,
                         floor=CONFIDENCE_WEIGHT_FLOOR):
    """Metodos del spec:
      - weighted_mean: media con pesos iniciales iguales (= media aritmetica)
      - median: mediana por bin (resistente a artefactos de un modelo aislado)
      - confidence_weighted_mean: pesos w_k ~ c_k^beta (default investigacion)
    Mi_consensus = 1 - Mv_consensus SIEMPRE (sin optimizacion independiente).
    No se declara ganador automatico: los 3 metodos se entregan completos."""
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
            "n_models": n_models,
            "beta": beta,
            "weight_floor": floor,
            "weight_definition": "w_k = clip(c_k, floor)^beta / sum_j (...)",
            "c_k_definition": "1 - mean_{j!=k} |Mv_k - Mv_j| (leave-one-out)",
        }
    return {
        "weighted_mean": mean_m,
        "median": median_m,
        "confidence_weighted_mean": conf_m,
    }, weights_summary


def consensus_cross_diffs_init(methods):
    return {(a, b): {"sum": 0.0, "n": 0}
            for i, a in enumerate(methods) for b in methods[i + 1:]}


def consensus_cross_diffs_update(acc, consensus_dict, methods):
    for i, a in enumerate(methods):
        for b in methods[i + 1:]:
            key = (a, b)
            if key not in acc:
                continue
            d = np.abs(consensus_dict[a] - consensus_dict[b])
            acc[key]["sum"] += float(d.sum())
            acc[key]["n"] += d.size


def consensus_cross_diffs_finalize(acc):
    out = {}
    for (a, b), v in acc.items():
        out["%s__vs__%s" % (a, b)] = {
            "mean_absolute_difference": v["sum"] / max(v["n"], 1),
            "n_bins": v["n"],
        }
    return out


# ============================================================================
# SECCION 13: RECONSTRUCCION (candidatos, OLA, true peak, escritura WAV)
# ============================================================================

class TruePeakStream:
    """True peak por sobremuestreo 4x (decision previa #4, estilo BS.1770)
    con contexto entre chunks para evitar transitorios del filtro FIR
    (resample_poly). Se aplica por canal sobre las senales emitidas."""

    def __init__(self, channels, up=TRUEPEAK_UPSAMPLE,
                 context=TRUEPEAK_CONTEXT):
        self.ch = channels
        self.up = up
        self.ctx = context
        self.carry = np.zeros((context, channels), dtype=np.float64)
        self.peak = 0.0
        self.initial = True

    def push(self, block):
        if block.shape[0] == 0:
            return
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
            self.carry = np.concatenate(
                [self.carry, block], axis=0)[-self.ctx:]

    def finalize(self):
        up = resample_poly(self.carry, self.up, 1, axis=0)
        if up.size:
            self.peak = max(self.peak, float(np.abs(up).max()))
        return self.peak

    def peak_dbtp(self):
        return 20.0 * math.log10(self.peak) if self.peak > 0 else None


def build_band_masks(bins, n_fft, sample_rate):
    """Matriz (n_bands, bins) de proyeccion de energia por banda (one-sided).
    Definicion documentada: energia espectral por banda = suma de |X_k|^2
    de los bins dentro de la banda (comparable entre senales del mismo
    analisis; no es energia temporal RMS)."""
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sample_rate)
    edges = [e for e in BAND_EDGES_HZ if e < freqs[-1]]
    if edges[-1] < freqs[-1]:
        edges.append(freqs[-1])
    labels = []
    masks = np.zeros((len(edges) - 1, bins), dtype=np.float64)
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        sel = (freqs >= lo) & (freqs < hi) if i < len(edges) - 2 \
            else (freqs >= lo) & (freqs <= hi)
        masks[i, sel] = 1.0
        labels.append("%.0f-%.0fHz" % (lo, hi))
    return masks, labels, freqs


class PearsonAccum:
    """Sumas para Pearson exacto por streaming entre dos senales."""

    def __init__(self):
        self.sa = 0.0
        self.sb = 0.0
        self.saa = 0.0
        self.sbb = 0.0
        self.sab = 0.0
        self.n = 0

    def update(self, a, b):
        a = np.asarray(a, dtype=np.float64).ravel()
        b = np.asarray(b, dtype=np.float64).ravel()
        if a.size == 0:
            return
        self.sa += float(a.sum())
        self.sb += float(b.sum())
        self.saa += float(np.square(a).sum())
        self.sbb += float(np.square(b).sum())
        self.sab += float((a * b).sum())
        self.n += a.size

    def finalize(self):
        if self.n < 8:
            return {"correlation": None, "n": self.n}
        ma = self.sa / self.n
        mb = self.sb / self.n
        va = max(self.saa / self.n - ma * ma, 0.0)
        vb = max(self.sbb / self.n - mb * mb, 0.0)
        cov = self.sab / self.n - ma * mb
        corr = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else 0.0
        return {"correlation": corr, "n": self.n,
                "rms_a": math.sqrt(self.saa / self.n),
                "rms_b": math.sqrt(self.sbb / self.n)}


class StereoAccum:
    """Correlacion inter-canaly energia mid/side por streaming (estereo)."""

    def __init__(self):
        self.ll = 0.0
        self.rr = 0.0
        self.lr = 0.0
        self.mid2 = 0.0
        self.side2 = 0.0
        self.n = 0

    def update(self, x):
        # x: (S, 2)
        if x.ndim != 2 or x.shape[1] < 2 or x.shape[0] == 0:
            return
        l = x[:, 0]
        r = x[:, 1]
        self.ll += float(np.square(l).sum())
        self.rr += float(np.square(r).sum())
        self.lr += float((l * r).sum())
        self.mid2 += float(np.square(l + r).sum())
        self.side2 += float(np.square(l - r).sum())
        self.n += len(l)

    def finalize(self):
        if self.n == 0:
            return {"inter_channel_correlation": None, "available": False}
        denom = math.sqrt(max(self.ll * self.rr, 0.0))
        icc = self.lr / denom if denom > 0 else None
        width = self.side2 / self.mid2 if self.mid2 > 0 else None
        return {
            "available": True,
            "inter_channel_correlation": icc,
            "side_to_mid_energy_ratio": width,
            "n_samples": self.n,
        }


class IPDAccum:
    """Relacion de fase inter-canaly alteracion de fase respecto al Mix.
    Con shared mask REAL, IPD(salida) == IPD(mix) exactamente -> este bloque
    funciona como test de sanidad estructural (spec phase_relationship)."""

    def __init__(self):
        self.coh = 0.0 + 0.0j   # suma de L*conj(R) normalizada
        self.dphi_abs_sum = 0.0
        self.n = 0

    def update(self, L_mix, R_mix, L_out, R_out, compute_diff):
        pl = L_mix * np.conj(R_mix)
        self.coh += complex(pl.sum())
        if compute_diff and L_out is not None:
            po = L_out * np.conj(R_out)
            dphi = np.angle(po) - np.angle(pl)
            self.dphi_abs_sum += float(np.abs(np.angle(
                np.exp(1j * dphi))).sum())
        self.n += pl.size

    def finalize(self):
        if self.n == 0:
            return {"available": False}
        out = {
            "available": True,
            "mix_inter_channel_coherence": float(np.abs(self.coh) / self.n),
            "mix_inter_channel_phase_rad": float(np.angle(self.coh)),
            "output_minus_mix_mean_abs_dphi_rad": self.dphi_abs_sum / self.n,
        }
        return out


class OnsetAccum:
    """Diferencia transitoria (proxy documentado): envolvente de onset por
    diferencias positivas de energia por frame; compara Mix vs salida."""

    def __init__(self):
        self.prev_mix = None     # escalar: energia del ultimo frame previo
        self.prev_out = None
        self.pearson = PearsonAccum()
        self.sum_diff2 = 0.0
        self.sum_mix2 = 0.0
        self.n = 0

    def update(self, mix_energy, out_energy):
        # frame_energy: (F,) energia por frame; carry ESCALAR entre chunks
        # (robusto a ultimo chunk con menos frames)
        if self.prev_mix is not None and len(mix_energy) > 0:
            e_m = np.concatenate(([mix_energy[0] - self.prev_mix],
                                  np.diff(mix_energy)))
            e_o = np.concatenate(([out_energy[0] - self.prev_out],
                                  np.diff(out_energy)))
            on_m = np.maximum(0.0, e_m)
            on_o = np.maximum(0.0, e_o)
            self.pearson.update(on_m, on_o)
            self.sum_diff2 += float(np.square(on_m - on_o).sum())
            self.sum_mix2 += float(np.square(on_m).sum())
            self.n += len(on_m)
        if len(mix_energy) > 0:
            self.prev_mix = float(mix_energy[-1])
            self.prev_out = float(out_energy[-1])

    def finalize(self):
        p = self.pearson.finalize()
        rel = math.sqrt(self.sum_diff2 / self.n) if self.n else None
        ref = math.sqrt(self.sum_mix2 / self.n) if self.n else None
        rel_err = (rel / ref) if (rel is not None and ref) else None
        return {
            "onset_correlation": p.get("correlation"),
            "onset_rms_relative_difference": rel_err,
            "definition": "proxy: half-wave rectified frame-energy differences",
            "n_frames": self.n,
        }


class FreqProfileAccum:
    """Perfiles espectrales por streaming: suma de magnitud media por bin
    y sumas de cuadrados para Pearson por banda entre dos espectros medios."""

    def __init__(self, bins):
        self.bins = bins
        self.sx = np.zeros(bins)
        self.sy = np.zeros(bins)
        self.sxx = np.zeros(bins)
        self.syy = np.zeros(bins)
        self.sxy = np.zeros(bins)
        self.n = 0

    def update(self, x_bin_mean, y_bin_mean):
        # x_bin_mean/y_bin_mean: (bins,) magnitud media del chunk
        self.sx += x_bin_mean
        self.sy += y_bin_mean
        self.sxx += np.square(x_bin_mean)
        self.syy += np.square(y_bin_mean)
        self.sxy += x_bin_mean * y_bin_mean
        self.n += 1

    def per_band_pearson(self, band_masks, band_labels):
        n = max(self.n, 1)
        xm = self.sx / n
        ym = self.sy / n
        out = []
        for i in range(band_masks.shape[0]):
            sel = band_masks[i] > 0
            if sel.sum() < 8:
                out.append({"band": band_labels[i], "correlation": None})
                continue
            x = xm[sel]
            y = ym[sel]
            vx = float(np.square(x - x.mean()).sum())
            vy = float(np.square(y - y.mean()).sum())
            c = float(((x - x.mean()) * (y - y.mean())).sum()) \
                if vx > 0 and vy > 0 else 0.0
            corr = c / math.sqrt(vx * vy) if vx > 0 and vy > 0 else 0.0
            out.append({"band": band_labels[i], "correlation": corr})
        return out


class CandidateMetrics:
    """Agrega TODAS las metricas MQR de un candidato (spec mqr_evaluation,
    bleeding_analysis, source_fidelity_analysis, stereo_policy,
    reconstruction_validation). Todo por streaming; nunca se retiene audio."""

    def __init__(self, cand_id, plan, band_masks, band_labels,
                 guide_refs, channels):
        self.cand_id = cand_id
        self.plan = plan
        self.band_masks = band_masks
        self.band_labels = band_labels
        self.guide_refs = guide_refs       # {role: [pair_ids]}
        self.channels = channels
        # identidad / energia (time domain):
        self.n_samples = 0
        self.sum_mix2 = 0.0
        self.sum_sdv2 = 0.0
        self.sum_sdi2 = 0.0
        self.sum_err2 = 0.0
        self.peak_mix = 0.0
        self.peak_sdv = 0.0
        self.peak_sdi = 0.0
        # correlaciones con guias y entre salidas:
        self.corr_sdv_vguide = {pid: PearsonAccum() for pid in
                                guide_refs.get("vocal", [])}
        self.corr_sdi_iguide = {pid: PearsonAccum() for pid in
                                guide_refs.get("instrumental", [])}
        self.corr_sdv_sdi = PearsonAccum()
        # estereo:
        self.st_mix = StereoAccum()
        self.st_sdv = StereoAccum()
        self.st_sdi = StereoAccum()
        # fase:
        self.ipd_mix = IPDAccum()
        self.ipd_sdv = IPDAccum()
        self.ipd_sdi = IPDAccum()
        # transitorios:
        self.onset_sdv = OnsetAccum()
        self.onset_sdi = OnsetAccum()
        # espectro:
        self.band_energy = {"mix": np.zeros(len(band_labels)),
                            "sdv": np.zeros(len(band_labels)),
                            "sdi": np.zeros(len(band_labels))}
        self.centroid = {"mix": [0.0, 0.0], "sdv": [0.0, 0.0],
                         "sdi": [0.0, 0.0]}  # [sum f*mag, sum mag]
        self.freq_prof_sdv_v = {pid: FreqProfileAccum(plan.bins) for pid in
                                guide_refs.get("vocal", [])}
        self.freq_prof_sdi_i = {pid: FreqProfileAccum(plan.bins) for pid in
                                guide_refs.get("instrumental", [])}
        # error espectral de identidad (dominio STFT):
        self.sum_spec_err2 = 0.0
        self.sum_spec_ref2 = 0.0
        # true peak:
        self.tp_mix = TruePeakStream(channels)
        self.tp_sdv = TruePeakStream(channels)
        self.tp_sdi = TruePeakStream(channels)
        # energia de mascara aplicada (auditoria):
        self.mask_mean_sum = 0.0
        self.mask_frames = 0

    # ---------------------------------------------------------------- #
    def update_freq(self, mix_stft, sdv_stft, sdi_stft, freqs,
                    pair_mags=None):
        """Metricas de dominio STFT. pair_mags: {pair_id: (v_mag, i_mag)}."""
        def band_e(X):
            m2 = np.square(np.abs(X)).sum(axis=0)   # (bins,)
            per_bin = m2.sum(axis=1) if m2.ndim == 2 else m2
            return self.band_masks @ per_bin

        def cent(X, key):
            mag = np.abs(X).mean(axis=0)            # (bins, F) -> mean ch
            if mag.ndim == 2:
                mag = mag.sum(axis=1)               # (bins,)
            self.centroid[key][0] += float((freqs * mag).sum())
            self.centroid[key][1] += float(mag.sum())

        self.band_energy["mix"] += band_e(mix_stft)
        self.band_energy["sdv"] += band_e(sdv_stft)
        self.band_energy["sdi"] += band_e(sdi_stft)
        cent(mix_stft, "mix")
        cent(sdv_stft, "sdv")
        cent(sdi_stft, "sdi")
        # identidad espectral: |Mix|*|1-(Mv+Mi)|
        ref = np.abs(mix_stft)
        err = ref * np.abs(1.0 - (np.abs(sdv_stft) + np.abs(sdi_stft))
                           / np.maximum(ref, 1e-30))
        self.sum_spec_err2 += float(np.square(err).sum())
        self.sum_spec_ref2 += float(np.square(ref).sum())
        if pair_mags:
            for pid, (v_mag, i_mag) in pair_mags.items():
                if pid in self.freq_prof_sdv_v:
                    x = np.abs(sdv_stft).mean(axis=0)
                    x = x.sum(axis=1) if x.ndim == 2 else x
                    self.freq_prof_sdv_v[pid].update(x, v_mag.mean(axis=1))
                if pid in self.freq_prof_sdi_i:
                    x = np.abs(sdi_stft).mean(axis=0)
                    x = x.sum(axis=1) if x.ndim == 2 else x
                    self.freq_prof_sdi_i[pid].update(x, i_mag.mean(axis=1))

    # ---------------------------------------------------------------- #
    def update_time(self, mix_reg, sdv_reg, sdi_reg, v_regs, i_regs,
                    mix_stft=None, sdv_stft=None, sdi_stft=None):
        """Metricas de dominio temporal sobre la region emitida por OLA.
        v_regs/i_regs: {pair_id: region_mono_del_guide} para las
        correlaciones guide-referenciadas de este candidato."""
        if sdv_reg is None or sdv_reg.shape[0] == 0:
            return
        m_mono = mono_downmix(mix_reg)
        v_mono = mono_downmix(sdv_reg)
        i_mono = mono_downmix(sdi_reg)
        self.n_samples += len(m_mono)
        self.sum_mix2 += float(np.square(m_mono).sum())
        self.sum_sdv2 += float(np.square(v_mono).sum())
        self.sum_sdi2 += float(np.square(i_mono).sum())
        err = m_mono - v_mono - i_mono
        self.sum_err2 += float(np.square(err).sum())
        self.peak_mix = max(self.peak_mix, float(np.abs(mix_reg).max()))
        self.peak_sdv = max(self.peak_sdv, float(np.abs(sdv_reg).max()))
        self.peak_sdi = max(self.peak_sdi, float(np.abs(sdi_reg).max()))
        self.tp_mix.push(mix_reg)
        self.tp_sdv.push(sdv_reg)
        self.tp_sdi.push(sdi_reg)
        # correlaciones con guias:
        for pid, acc in self.corr_sdv_vguide.items():
            reg = v_regs.get(pid)
            if reg is not None and len(reg) == len(v_mono):
                acc.update(v_mono, reg)
        for pid, acc in self.corr_sdi_iguide.items():
            reg = i_regs.get(pid)
            if reg is not None and len(reg) == len(i_mono):
                acc.update(i_mono, reg)
        self.corr_sdv_sdi.update(v_mono, i_mono)
        # estereo:
        self.st_mix.update(mix_reg)
        self.st_sdv.update(sdv_reg)
        self.st_sdi.update(sdi_reg)
        # fase (solo estereo):
        if mix_stft is not None and mix_stft.shape[0] >= 2:
            self.ipd_mix.update(mix_stft[0], mix_stft[1], None, None, False)
            self.ipd_sdv.update(mix_stft[0], mix_stft[1],
                                sdv_stft[0], sdv_stft[1], True)
            self.ipd_sdi.update(mix_stft[0], mix_stft[1],
                                sdi_stft[0], sdi_stft[1], True)
        # transitorios (energia por frame desde STFT):
        if mix_stft is not None:
            e_mix = np.square(np.abs(mix_stft)).sum(axis=(0, 1))
            e_sdv = np.square(np.abs(sdv_stft)).sum(axis=(0, 1))
            e_sdi = np.square(np.abs(sdi_stft)).sum(axis=(0, 1))
            self.onset_sdv.update(e_mix, e_sdv)
            self.onset_sdi.update(e_mix, e_sdi)

    # ---------------------------------------------------------------- #
    def mask_audit(self, mv_chunk):
        self.mask_mean_sum += float(mv_chunk.mean())
        self.mask_frames += 1

    # ---------------------------------------------------------------- #
    def finalize(self):
        snr_db = None
        rms_err = None
        if self.n_samples > 0:
            rms_err = math.sqrt(self.sum_err2 / self.n_samples)
            if self.sum_err2 > 0:
                snr_db = 10.0 * math.log10(self.sum_mix2 / self.sum_err2)
            else:
                snr_db = float("inf")
        corr_id = None
        # correlacion identidad via energias (aprox): se usa Pearson de err
        band_ref = self.band_energy["mix"].sum()
        band_rel_err = None
        if band_ref > 0:
            band_rel_err = math.sqrt(max(self.sum_spec_err2, 0.0)) / \
                math.sqrt(band_ref)
        tp_mix = self.tp_mix.finalize()
        tp_sdv = self.tp_sdv.finalize()
        tp_sdi = self.tp_sdi.finalize()

        def band_fracs(key):
            tot = self.band_energy[key].sum()
            if tot <= 0:
                return None
            return (self.band_energy[key] / tot).tolist()

        cent = {}
        for key in self.centroid:
            s = self.centroid[key]
            cent[key] = (s[0] / s[1]) if s[1] > 0 else None
        out = {
            "candidate_id": self.cand_id,
            "reconstruction_accuracy": {
                "rms_error": rms_err,
                "peak_error": max(0.0, self.peak_mix - max(self.peak_sdv,
                                                           self.peak_sdi)),
                "identity_snr_db": snr_db,
                "spectral_error_rms_relative": band_rel_err,
                "definition": ("SDV + SDI vs Mix Original; identidad exacta "
                               "por construccion: mide camino numerico"),
            },
            "energy": {
                "mix_rms": math.sqrt(self.sum_mix2 / max(self.n_samples, 1)),
                "sdv_rms": math.sqrt(self.sum_sdv2 / max(self.n_samples, 1)),
                "sdi_rms": math.sqrt(self.sum_sdi2 / max(self.n_samples, 1)),
                "n_samples": self.n_samples,
            },
            "peaks": {
                "mix_sample_peak": self.peak_mix,
                "sdv_sample_peak": self.peak_sdv,
                "sdi_sample_peak": self.peak_sdi,
                "mix_true_peak_dbtp": 20.0 * math.log10(tp_mix)
                    if tp_mix > 0 else None,
                "sdv_true_peak_dbtp": 20.0 * math.log10(tp_sdv)
                    if tp_sdv > 0 else None,
                "sdi_true_peak_dbtp": 20.0 * math.log10(tp_sdi)
                    if tp_sdi > 0 else None,
            },
            "bleeding_metrics": {
                "sdv_vs_vocal_guide_correlation": {
                    pid: acc.finalize() for pid, acc in
                    self.corr_sdv_vguide.items()},
                "sdi_vs_instrumental_guide_correlation": {
                    pid: acc.finalize() for pid, acc in
                    self.corr_sdi_iguide.items()},
                "sdv_vs_sdi_cross_correlation": self.corr_sdv_sdi.finalize(),
                "sdv_band_energy_fraction": band_fracs("sdv"),
                "sdi_band_energy_fraction": band_fracs("sdi"),
                "frequency_dependent_correlation_sdv_vguide": {
                    pid: prof.per_band_pearson(self.band_masks,
                                               self.band_labels)
                    for pid, prof in self.freq_prof_sdv_v.items()},
                "frequency_dependent_correlation_sdi_iguide": {
                    pid: prof.per_band_pearson(self.band_masks,
                                               self.band_labels)
                    for pid, prof in self.freq_prof_sdi_i.items()},
                "critical_rule": ("una correlacion baja no demuestra por si "
                                  "sola separacion perfecta (spec)"),
            },
            "source_fidelity_metrics": {
                "spectral_centroid": cent,
                "centroid_difference_sdv_mix":
                    (cent["sdv"] - cent["mix"])
                    if cent["sdv"] is not None and cent["mix"] is not None
                    else None,
                "centroid_difference_sdi_mix":
                    (cent["sdi"] - cent["mix"])
                    if cent["sdi"] is not None and cent["mix"] is not None
                    else None,
                "band_energy_mix": self.band_energy["mix"].tolist(),
                "band_energy_sdv": self.band_energy["sdv"].tolist(),
                "band_energy_sdi": self.band_energy["sdi"].tolist(),
                "transient_sdv": self.onset_sdv.finalize(),
                "transient_sdi": self.onset_sdi.finalize(),
                "crest_factor_sdv": (self.peak_sdv / math.sqrt(
                    self.sum_sdv2 / max(self.n_samples, 1)))
                    if self.n_samples and self.sum_sdv2 > 0 else None,
                "crest_factor_mix": (self.peak_mix / math.sqrt(
                    self.sum_mix2 / max(self.n_samples, 1)))
                    if self.n_samples and self.sum_mix2 > 0 else None,
                "crest_factor_basis": "LR peak / Mid RMS; null if undefined",
            },
            "stereo_metrics": {
                "mix": self.st_mix.finalize(),
                "sdv": self.st_sdv.finalize(),
                "sdi": self.st_sdi.finalize(),
                "phase_mix": self.ipd_mix.finalize(),
                "phase_sdv": self.ipd_sdv.finalize(),
                "phase_sdi": self.ipd_sdi.finalize(),
            },
            "mask_audit_mean": self.mask_mean_sum /
                               max(self.mask_frames, 1),
        }
        return out


class CandidateRunner:
    """Ejecuta un candidato: aplica la mascara al STFT del Mix, reconstruye
    por OLA streaming (SDV y SDI), acumula metricas y opcionalmente escribe
    los WAV. La fase proviene SIEMPRE del STFT del Mix Original."""

    def __init__(self, cand_id, mask_source, plan, channels, run_dir=None,
                 band_masks=None, band_labels=None, guide_refs=None,
                 write_audio=False, output_subtype=OUTPUT_SUBTYPE):
        self.cand_id = cand_id
        self.mask_source = mask_source      # ("individual", k) | ("consensus", method)
        self.plan = plan
        self.write_audio = write_audio
        self.writer_sdv = None
        self.writer_sdi = None
        if write_audio and run_dir is not None:
            self.writer_sdv = sf.SoundFile(
                os.path.join(run_dir, "SDV.wav"), mode="w",
                samplerate=REQUIRED_SAMPLE_RATE, channels=channels,
                subtype=output_subtype)
            self.writer_sdi = sf.SoundFile(
                os.path.join(run_dir, "SDI.wav"), mode="w",
                samplerate=REQUIRED_SAMPLE_RATE, channels=channels,
                subtype=output_subtype)
            _registrar_propio_6g1(os.path.join(run_dir, "SDV.wav"), estable=False)
            _registrar_propio_6g1(os.path.join(run_dir, "SDI.wav"), estable=False)
        self.ola_sdv = OlaStream(plan, channels, writer=self.writer_sdv,
                                 label="%s/SDV" % cand_id)
        self.ola_sdi = OlaStream(plan, channels, writer=self.writer_sdi,
                                 label="%s/SDI" % cand_id)
        self.metrics = CandidateMetrics(cand_id, plan, band_masks,
                                        band_labels, guide_refs or {},
                                        channels)

    def close(self):
        for w in (self.writer_sdv, self.writer_sdi):
            if w is not None:
                try:
                    w.close()
                except Exception:
                    pass
        self.writer_sdv = None
        self.writer_sdi = None


# ============================================================================
# SECCION 15: ORQUESTADOR SINGLE-PASS CHUNKED (pipeline principal)
# ============================================================================

def create_run_dir(out_base):
    """Directorio de corrida en dos fases: *_partial -> final al exito.
    Si el motor falla, el parcial se conserva como *_aborted (evidencia
    cientifica; nunca se destruye trabajo parcial silenciosamente).

    [6G.1-R/F] Provisional EXCLUSIVO: nunca reutilizar un _partial
    preexistente (los writers abren en modo 'w' y truncarian contenido ajeno
    antes de poder registrar propiedad). mkdir exclusivo; si el nombre existe
    se genera otro identificador SIN tocar su contenido. El registro de
    propiedad se reinicia: aislado por corrida; los archivos preexistentes no
    son propios por el mero hecho de estar en el directorio."""
    _reiniciar_registro_6g1()
    os.makedirs(out_base, exist_ok=True)
    intento = 0
    while True:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sufijo = "" if intento == 0 else "_%03d" % intento
        final = os.path.join(out_base, "mqr_run_%s%s" % (stamp, sufijo))
        partial = final + "_partial"
        try:
            os.mkdir(partial)
            _acreditar_dir_6g1(partial)  # [6G.1-R/H1] anclaje del aborto
            return partial, final
        except FileExistsError:
            intento += 1
            if intento > 999:
                raise RuntimeError("[6G.1-R/F] no se pudo crear un directorio "
                                   "provisional exclusivo en %s" % out_base)


def _open_memmap(path, shape):
    mm = np.lib.format.open_memmap(path, mode="w+", dtype=MASK_SAVE_DTYPE,
                                   shape=shape)
    _registrar_propio_6g1(path, estable=False)
    return mm


def _confirm_interactive(question):
    try:
        ans = input("%s [si/no]: " % question).strip().lower()
    except EOFError:
        return False
    return ans in ("si", "s", "y", "yes")


def run_experiment(mix_path, pairs, mode, opt):
    """Pipeline completo del spec cli.workflow, un solo pase sobre chunks.
    opt: namespace con n_fft, hop, power, epsilon, chunk_frames, smoothing,
    allow_misaligned, write_all_candidates, png, out_base, consensus_default,
    interactive, manifest_path, spec_path."""
    t_start = time.monotonic()
    ctx = {"mode": mode}
    ctx["warnings"] = []

    # --- [Paso 5 del workflow] validacion estricta de entradas ---------------
    mix_info = validate_mix(probe_file(mix_path, "mix"))
    if not mix_info.valid:
        log("[FATAL] Mix Original invalido:")
        for e in mix_info.errors:
            log("  - %s" % e)
        return EXIT_VALIDATION, None
    if not pairs:
        log("[FATAL] no hay pares de guides definidos")
        return EXIT_VALIDATION, None
    if len(pairs) > MAX_PAIRS:
        log("[FATAL] pares=%d excede MAX_PAIRS=%d" % (len(pairs), MAX_PAIRS))
        return EXIT_VALIDATION, None
    for p in pairs:
        p.vocal = validate_guide(probe_file(p.vocal_path, "vocal_guide"))
        p.instrumental = validate_guide(
            probe_file(p.instrumental_path, "instrumental_guide"))
    invalid = []
    for p in pairs:
        for role in ("vocal", "instrumental"):
            info = getattr(p, role)
            if not info.valid:
                invalid.append("%s/%s: %s" % (p.pair_id, role,
                                              "; ".join(info.errors)))
    if invalid:
        log("[FATAL] guides invalidos (policy reject_by_default):")
        for e in invalid:
            log("  - %s" % e)
        return EXIT_VALIDATION, None
    log("Validacion de entradas: OK (mix %d Hz / %d ch / %d frames; %d pares)"
        % (mix_info.sample_rate, mix_info.channels, mix_info.frames,
           len(pairs)))

    ctx["mix_info"] = mix_info
    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
    ctx["container_6g"] = {
        "mix_path": os.path.abspath(mix_path),
        "container": _container_6g(mix_path),
        "format": mix_info.format, "subtype": mix_info.subtype,
        "probe_sha256": mix_info.sha256, "after": None,
        "policy": "detect_only_no_conversion"}

    ctx["pairs"] = pairs

    # --- dry_run: plan sin computo (spec cli.required_modes) -----------------
    if mode == MODE_DRY_RUN:
        plan = FramePlan(mix_info.frames, opt.n_fft, opt.hop)
        log("DRY_RUN - plan de ejecucion:")
        log("  mix: %s" % mix_info.path)
        log("  frames STFT K=%d, bins=%d, chunks de %d frames"
            % (plan.K, plan.bins, opt.chunk_frames))
        for p in pairs:
            log("  %s | family=%s variant=%s config=%s" %
                (p.pair_id, p.family, p.variant, p.configuration))
            log("     vocal: %s (%d frames)" % (p.vocal.path, p.vocal.frames))
            log("     instr: %s (%d frames)" % (p.instrumental.path,
                                                p.instrumental.frames))
        log("  consenso default: %s" % opt.consensus_default)
        log("  dry_run terminado: sin computo (spec cli.required_modes)")
        return EXIT_OK, None

    # --- [Paso 6] analisis de alineacion (deteccion sin correccion) ----------
    log("Analisis de alineacion (detect_only_no_correction)...")
    alignment_records = []
    misaligned = []
    for p in pairs:
        for role in ("vocal", "instrumental"):
            info = getattr(p, role)
            rec = analyze_alignment(mix_info, info)
            rec["pair_id"] = p.pair_id
            rec["role"] = role
            alignment_records.append(rec)
            log('  %s/%s: %s' % (p.pair_id,role,_alignment_line(rec)))
            if rec['classification'] not in ('ALIGNED','WARNING'):
                misaligned.append(rec)
    ctx['alignment'] = alignment_records
    gate = alignment_gate(alignment_records, misaligned, opt.allow_misaligned, log)
    ctx['alignment_gate'] = gate
    for _r in misaligned:
        _r['continuation_permission'] = gate['permission']
    if not gate['allowed']:
        return EXIT_VALIDATION, ctx
    if gate['permission']:
        ctx['misalignment_user_authorized'] = True
        ctx['alignment_permission'] = gate['permission']

    # --- [Paso 7] analisis de escala de guides --------------------------------
    log("Analisis de escala de guides (metricas + factores)...")
    scale_records = []
    scale_factors = {}
    for p in pairs:
        rec, applied = analyze_guide_scale(mix_info, p)
        scale_records.append(rec)
        scale_factors[p.pair_id] = applied
        log("  %s: g_vocal=%.4f g_instr=%.4f (politica=%s)"
            % (p.pair_id, applied["vocal"], applied["instrumental"],
               GUIDE_SCALE_COMPENSATION))
    ctx["guide_scale_analysis"] = scale_records

    # --- plan de frames y cobertura -------------------------------------------
    plan = FramePlan(mix_info.frames, opt.n_fft, opt.hop)
    freqs = np.fft.rfftfreq(plan.n_fft, d=1.0 / REQUIRED_SAMPLE_RATE)
    band_masks, band_labels, _ = build_band_masks(plan.bins, plan.n_fft,
                                                  REQUIRED_SAMPLE_RATE)
    coverage_K = {}
    for p in pairs:
        coverage_K[p.pair_id] = {
            "vocal": FramePlan(p.vocal.frames, opt.n_fft, opt.hop).K,
            "instrumental": FramePlan(p.instrumental.frames, opt.n_fft,
                                      opt.hop).K,
        }
    ctx["stft_configuration"] = {
        "implementation": "NumPy-compatible (framing manual + scipy.fft), "
                          "spec stft_configuration.alternative",
        "library": "scipy.fft (rfft/irfft) + numpy",
        "n_fft": opt.n_fft,
        "hop_length": opt.hop,
        "window": STFT_WINDOW,
        "center": STFT_CENTER,
        "mask_precision": "float64",
        "mask_storage_precision": str(np.dtype(MASK_SAVE_DTYPE)),
        "source_processing_precision": "float64",
        "phase_source": "Mix Original complex STFT",
        "frames_total": plan.K,
        "bins": plan.bins,
        "chunk_frames": opt.chunk_frames,
        "cola_note": "hann periodica + hop=n_fft/4: sum(w^2)=1.5 constante",
    }

    # --- directorio de corrida + log ------------------------------------------
    run_dir, run_dir_final = create_run_dir(opt.out_base)
    init_tee(os.path.join(run_dir, "engine_log.txt"))
    log("Directorio de corrida (parcial): %s" % run_dir)
    masks_dir = os.path.join(run_dir, "masks")
    os.makedirs(masks_dir, exist_ok=True)

    try:
        run_dir_final = _run_core(mix_info, pairs, mode, opt, plan, freqs,
                                  band_masks, band_labels, coverage_K,
                                  scale_factors, run_dir, run_dir_final,
                                  masks_dir, ctx, t_start)
    except KeyboardInterrupt:
        aborted = run_dir_final + "_aborted"
        # [6G.1-R/G-R1] Traslado al destino de aborto con no-reemplazo atómico
        # (renameat2 RENAME_NOREPLACE): nunca reemplaza un destino preexistente
        # (ni vacío, ni enlace simbólico); ante colisión elige un sufijo libre;
        # si el entorno no garantiza la operación, conserva el provisional en su
        # ubicación original. Sin degradación a os.rename.
        try:
            aborted = _publicar_dir_6g1(run_dir, aborted)
        except Exception as _exc_ab:
            aborted = run_dir
            log("[ABORT] traslado seguro no garantizado (%s); provisional "
                "conservado en: %s" % (_exc_ab, run_dir))
        log("[ABORT] interrupcion del usuario; corrida en %s" % aborted)
        close_tee()
        return EXIT_ABORTED, None
    except _VerifFallida_6g1 as _exc6g1:
        # [6G.1-R/A] La guarda final ya abortó sobre el provisional y no hay
        # publicación; no se renombra ni se publica nada.
        log("[FATAL] guarda final no superada (fail-closed): %s" % _exc6g1)
        close_tee()
        return EXIT_PROCESSING, None
    except Exception:
        aborted = run_dir_final + "_aborted"
        # [6G.1-R/G-R1] Traslado al destino de aborto con no-reemplazo atómico
        # (renameat2 RENAME_NOREPLACE): nunca reemplaza un destino preexistente
        # (ni vacío, ni enlace simbólico); ante colisión elige un sufijo libre;
        # si el entorno no garantiza la operación, conserva el provisional en su
        # ubicación original. Sin degradación a os.rename.
        try:
            aborted = _publicar_dir_6g1(run_dir, aborted)
        except Exception as _exc_ab:
            aborted = run_dir
            log("[ABORT] traslado seguro no garantizado (%s); provisional "
                "conservado en: %s" % (_exc_ab, run_dir))
        log("[FATAL] excepcion en el pipeline; corrida preservada en %s"
            % aborted)
        traceback.print_exc()
        close_tee()
        return EXIT_PROCESSING, None

    close_tee()
    log("Corrida COMPLETA: %s" % run_dir_final)
    # [6G.1-R/A+B] La guarda final fail-closed, la evidencia de integridad y la
    # publicación por renombrado viven ahora en _run_core (verificación ANTES de
    # publicar; aborto sobre el provisional). Aquí sólo se registra el éxito:
    # ninguna verificación alternativa ni fallback.
    return EXIT_OK, run_dir_final


def _run_core(mix_info, pairs, mode, opt, plan, freqs, band_masks,
              band_labels, coverage_K, scale_factors, run_dir,
              run_dir_final, masks_dir, ctx, t_start):
    """Bucle single-pass + escritura de artefactos. Toda excepcion se
    propaga al orquestador (que preserva el directorio parcial).
    Devuelve el directorio final (con sufijo anti-colision si aplica)."""
    n_pairs = len(pairs)
    full_mode = (mode == MODE_FULL_PROCESSING)
    log("Pipeline: mode=%s, %d pares, K=%d frames en chunks de %d"
        % (mode, n_pairs, plan.K, opt.chunk_frames))

    # --- memmaps de mascaras (spec outputs; D2: float32 en disco) ------------
    mm = {}
    for p in pairs:
        pid = safe_name(p.pair_id)
        mm["mask_%s_vocal" % pid] = _open_memmap(
            os.path.join(masks_dir, "mask_%s_vocal.npy" % pid),
            (plan.bins, plan.K))
        mm["mask_%s_instrumental" % pid] = _open_memmap(
            os.path.join(masks_dir, "mask_%s_instrumental.npy" % pid),
            (plan.bins, plan.K))
    for method in CONSENSUS_METHODS:
        mm["consensus_vocal_%s" % method] = _open_memmap(
            os.path.join(masks_dir, "consensus_vocal_%s.npy" % method),
            (plan.bins, plan.K))
        mm["consensus_instrumental_%s" % method] = _open_memmap(
            os.path.join(masks_dir, "consensus_instrumental_%s.npy" % method),
            (plan.bins, plan.K))
    mm["confidence_map"] = _open_memmap(
        os.path.join(masks_dir, "confidence_map.npy"), (plan.bins, plan.K))
    mm["model_disagreement_map"] = _open_memmap(
        os.path.join(masks_dir, "model_disagreement_map.npy"),
        (plan.bins, plan.K))

    # --- acumuladores globales ------------------------------------------------
    combos = [(i, j) for i in range(n_pairs) for j in range(i + 1, n_pairs)]
    stride_pairwise = compute_pairwise_stride(plan.K, plan.bins,
                                              max(1, len(combos)))
    stride_maps = 1 if plan.K * plan.bins <= 4_000_000 else 3
    pairwise = {(i, j): PairwiseAccum(plan.bins, plan.K) for i, j in combos}
    mask_stats = [mask_stats_stream_init() for _ in range(n_pairs)]
    conf_accum = GlobalMaskAccum(stride_maps)
    dis_accum = GlobalMaskAccum(stride_maps)
    mad_accum = GlobalMaskAccum(stride_maps)
    consensus_stats = {m: mask_stats_stream_init()
                       for m in CONSENSUS_METHODS}
    cross_diffs = consensus_cross_diffs_init(CONSENSUS_METHODS)
    coverage_warnings = set()

    # --- candidatos ------------------------------------------------------------
    all_ids = [p.pair_id for p in pairs]
    runners = []
    for k, p in enumerate(pairs):
        write_audio = full_mode and opt.write_all_candidates
        if write_audio:
            sub = os.path.join(run_dir, "candidates",
                               safe_name("individual_%s" % p.pair_id))
            os.makedirs(sub, exist_ok=True)
        else:
            sub = None
        runners.append(CandidateRunner(
            cand_id="individual_%s" % p.pair_id, mask_source=("individual", k),
            plan=plan, channels=mix_info.channels, run_dir=sub,
            band_masks=band_masks, band_labels=band_labels,
            guide_refs={"vocal": [p.pair_id], "instrumental": [p.pair_id]},
            write_audio=write_audio))
    for method in CONSENSUS_METHODS:
        is_default = (method == opt.consensus_default)
        write_audio = full_mode and (is_default or opt.write_all_candidates)
        if write_audio and is_default:
            sub = run_dir            # SDV.wav / SDI.wav requeridos por spec
        elif write_audio:
            sub = os.path.join(run_dir, "candidates",
                               safe_name("consensus_%s" % method))
            os.makedirs(sub, exist_ok=True)
        else:
            sub = None
        runners.append(CandidateRunner(
            cand_id="consensus_%s" % method, mask_source=("consensus", method),
            plan=plan, channels=mix_info.channels, run_dir=sub,
            band_masks=band_masks, band_labels=band_labels,
            guide_refs={"vocal": all_ids, "instrumental": all_ids},
            write_audio=write_audio))
    default_runner = [r for r in runners
                      if r.mask_source == ("consensus",
                                           opt.consensus_default)][0]

    # --- bucle single-pass ------------------------------------------------------
    try:
        hmix = _abrir_mix_6g1(mix_info.path, mix_info.sha256)
    except _MixCambiado_6g1 as _exc6g1:
        _abortar_6g1(run_dir, "MIX_SUSTITUIDO_ANTES_DEL_DSP", str(_exc6g1))
        log("[FATAL] Mix sustituido antes del DSP: %s" % _exc6g1)
        close_tee()
        return EXIT_PROCESSING, None
    ctx["_mix_handle_6g1"] = hmix
    handles = {}
    for p in pairs:
        handles[(p.pair_id, "vocal")] = sf.SoundFile(p.vocal.path)
        handles[(p.pair_id, "instrumental")] = sf.SoundFile(
            p.instrumental.path)
    last_span_ctx = None
    try:
        n_chunks = (plan.K + opt.chunk_frames - 1) // opt.chunk_frames
        for c_idx, f0 in enumerate(range(0, plan.K, opt.chunk_frames)):
            f1 = min(f0 + opt.chunk_frames, plan.K)
            F = f1 - f0
            s0, s1 = plan.span_for_frames(f0, f1)
            mix_span = read_span(hmix, s0, s1)
            mix_stft = stft_span_frames(mix_span, F, plan)

            pair_data = []
            for k, p in enumerate(pairs):
                v_span = read_span(handles[(p.pair_id, "vocal")], s0, s1)
                i_span = read_span(handles[(p.pair_id, "instrumental")],
                                   s0, s1)
                v_mono = mono_downmix(v_span)
                i_mono = mono_downmix(i_span)
                V_stft = stft_span_frames(v_mono[:, None], F, plan)
                I_stft = stft_span_frames(i_mono[:, None], F, plan)
                v_mag = np.abs(V_stft[0])
                i_mag = np.abs(I_stft[0])
                fac = scale_factors[p.pair_id]
                mv = compute_vocal_mask(v_mag * fac["vocal"],
                                        i_mag * fac["instrumental"],
                                        opt.power, opt.epsilon)
                # D1: cobertura (guia mas corta que el mix)
                gv_frames = np.arange(f0, f1)
                no_cov = (gv_frames >= coverage_K[p.pair_id]["vocal"]) | \
                         (gv_frames >= coverage_K[p.pair_id]["instrumental"])
                if no_cov.any():
                    mv[:, no_cov] = NEUTRAL_MASK_VALUE
                    if p.pair_id not in coverage_warnings:
                        coverage_warnings.add(p.pair_id)
                        ctx["warnings"].append(
                            "par %s: guia mas corta que el mix; frames sin "
                            "cobertura usan mascara neutra 0.5 (D1)"
                            % p.pair_id)
                mv, smooth_info = apply_optional_smoothing(mv,
                                                           opt.smoothing)
                if smooth_info:
                    pair_data.append({"pair": p, "mv": mv, "v_mono": v_mono,
                                      "i_mono": i_mono, "v_mag": v_mag,
                                      "i_mag": i_mag,
                                      "smoothing": smooth_info})
                else:
                    pair_data.append({"pair": p, "mv": mv, "v_mono": v_mono,
                                      "i_mono": i_mono, "v_mag": v_mag,
                                      "i_mag": i_mag, "smoothing": None})
                mask_stats_stream_update(mask_stats[k], mv, stride_maps)
                mm["mask_%s_vocal" % safe_name(p.pair_id)][:, f0:f1] = \
                    mv.astype(MASK_SAVE_DTYPE)
                mm["mask_%s_instrumental" % safe_name(p.pair_id)][:, f0:f1] = \
                    (1.0 - mv).astype(MASK_SAVE_DTYPE)

            # pairwise (spec multi_model_analysis)
            for (i, j) in combos:
                pairwise[(i, j)].update(pair_data[i]["mv"],
                                        pair_data[j]["mv"], f0,
                                        stride_pairwise)

            # confianza + desacuerdo + consenso
            masks_list = [pd["mv"] for pd in pair_data]
            conf_map, dis_map, c_k = confidence_and_disagreement(masks_list)
            consensus, weights_summary = consensus_from_masks(
                masks_list, c_k)
            consensus_cross_diffs_update(cross_diffs, consensus,
                                         CONSENSUS_METHODS)
            conf_accum.update(conf_map)
            dis_accum.update(dis_map)
            med_map = consensus["median"]
            mad_map = np.median(np.stack(
                [np.abs(m - med_map) for m in masks_list]), axis=0) \
                if n_pairs > 1 else np.zeros_like(med_map)
            mad_accum.update(mad_map)
            for method in CONSENSUS_METHODS:
                mask_stats_stream_update(consensus_stats[method],
                                         consensus[method], stride_maps)
                mm["consensus_vocal_%s" % method][:, f0:f1] = \
                    consensus[method].astype(MASK_SAVE_DTYPE)
                mm["consensus_instrumental_%s" % method][:, f0:f1] = \
                    (1.0 - consensus[method]).astype(MASK_SAVE_DTYPE)
            mm["confidence_map"][:, f0:f1] = conf_map.astype(MASK_SAVE_DTYPE)
            mm["model_disagreement_map"][:, f0:f1] = \
                dis_map.astype(MASK_SAVE_DTYPE)

            # candidatos: aplicar SIEMPRE al STFT del Mix Original
            v_regs_all = {p.pair_id: pair_data[i]["v_mono"]
                          for i, p in enumerate(pairs)}
            i_regs_all = {p.pair_id: pair_data[i]["i_mono"]
                          for i, p in enumerate(pairs)}
            for runner in runners:
                if runner.mask_source[0] == "individual":
                    k = runner.mask_source[1]
                    mv_c = pair_data[k]["mv"]
                    v_regs = {pairs[k].pair_id: pair_data[k]["v_mono"]}
                    i_regs = {pairs[k].pair_id: pair_data[k]["i_mono"]}
                    pair_mags = {pairs[k].pair_id: (pair_data[k]["v_mag"],
                                                    pair_data[k]["i_mag"])}
                else:
                    mv_c = consensus[runner.mask_source[1]]
                    v_regs = v_regs_all
                    i_regs = i_regs_all
                    pair_mags = {p.pair_id: (pair_data[i]["v_mag"],
                                             pair_data[i]["i_mag"])
                                 for i, p in enumerate(pairs)}
                runner.metrics.mask_audit(mv_c)
                mi_c = 1.0 - mv_c
                sdv_stft = mix_stft * mv_c[None, :, :]
                sdi_stft = mix_stft * mi_c[None, :, :]
                runner.metrics.update_freq(mix_stft, sdv_stft, sdi_stft,
                                           freqs, pair_mags)
                reg_v, a, b = runner.ola_sdv.push(sdv_stft)
                reg_i, _, _ = runner.ola_sdi.push(sdi_stft)
                lo = a - s0
                hi = b - s0
                mix_reg = mix_span[lo:hi]
                v_regs_r = {pid: arr[lo:hi] for pid, arr in v_regs.items()}
                i_regs_r = {pid: arr[lo:hi] for pid, arr in i_regs.items()}
                runner.metrics.update_time(mix_reg, reg_v, reg_i,
                                           v_regs_r, i_regs_r,
                                           mix_stft=mix_stft,
                                           sdv_stft=sdv_stft,
                                           sdi_stft=sdi_stft)
            last_span_ctx = {"s0": s0, "s1": s1, "v_regs": v_regs_all,
                             "i_regs": i_regs_all, "mix_span": mix_span}
            if (c_idx + 1) % 10 == 0 or (c_idx + 1) == n_chunks:
                log("  chunk %d/%d (frames %d-%d) listo"
                    % (c_idx + 1, n_chunks, f0, f1 - 1))

        # flush defensivo de streams OLA
        for runner in runners:
            reg_v, a, b = runner.ola_sdv.flush()
            reg_i, _, _ = runner.ola_sdi.flush()
            if reg_v is not None and reg_v.shape[0] > 0 and last_span_ctx:
                s0 = last_span_ctx["s0"]
                lo = max(a - s0, 0)
                hi = min(b - s0, len(last_span_ctx["mix_span"]))
                if hi > lo:
                    mix_reg = last_span_ctx["mix_span"][lo:hi]
                    v_regs_r = {pid: arr[lo:hi]
                                for pid, arr in last_span_ctx["v_regs"].items()}
                    i_regs_r = {pid: arr[lo:hi]
                                for pid, arr in last_span_ctx["i_regs"].items()}
                    runner.metrics.update_time(mix_reg, reg_v, reg_i,
                                               v_regs_r, i_regs_r)
    finally:
        # 6G.1: el descriptor sigue abierto durante todo el DSP
        for h in handles.values():
            h.close()

    # flush de memmaps
    for arr in mm.values():
        arr.flush()
    del mm

    # cierre de writers y metricas finales por candidato
    per_candidate = {}
    for runner in runners:
        runner.close()
        per_candidate[runner.cand_id] = runner.metrics.finalize()

    # validacion post-WAV (spec reconstruction_validation.post_wav_test)
    post_wav = None
    if full_mode:
        post_wav = post_wav_identity(hmix.ruta_lectura(),
                                     os.path.join(run_dir, "SDV.wav"),
                                     os.path.join(run_dir, "SDI.wav"))
        log("Post-WAV identity: SNR=%.2f dB (esperado > %.0f dB)"
            % (post_wav["identity_snr_db"], IDENTITY_SNR_EXPECTED_DB))

    # --- armado de contexto para informes --------------------------------------
    pairwise_out = [pairwise[(i, j)].finalize(pairs[i].pair_id,
                                              pairs[j].pair_id, plan.K)
                    for i, j in combos]
    ctx.update({
        "document_meta": build_document_meta(opt, pairs),
        "guide_inventory": [p.as_dict() for p in pairs],
        "guide_family_inventory": build_family_inventory(pairs),
        "guide_variant_inventory": build_variant_inventory(pairs),
        "input_integrity": build_input_integrity(mix_info, pairs),
        "individual_model_metrics": build_individual_metrics(pairs,
                                                             mask_stats),
        "pairwise_model_comparison": pairwise_out,
        "family_comparison": build_family_comparison(pairwise_out, pairs),
        "variant_comparison": build_variant_comparison(pairwise_out, pairs),
        "model_agreement": build_model_agreement(pairwise_out),
        "model_disagreement": {
            "map_statistics": dis_accum.finalize(),
            "mad_across_models": mad_accum.finalize(),
            "interpretation": "incertidumbre ENTRE modelos, no error "
                              "absoluto (spec model_disagreement)",
        },
        "confidence_analysis": {
            "map_statistics": conf_accum.finalize(),
            "definition": "concordancia entre modelos por region TF "
                          "(1 - 2*std); NO verdad fisica absoluta",
        },
        "consensus_methods": {
            "default": opt.consensus_default,
            "weights_summary": weights_summary,
            "mask_statistics": {m: mask_stats_stream_finalize(
                consensus_stats[m]) for m in CONSENSUS_METHODS},
            "cross_method_differences":
                consensus_cross_diffs_finalize(cross_diffs),
        },
        "per_candidate": per_candidate,
        "post_wav_validation": post_wav,
        "coverage_warnings": sorted(coverage_warnings),
    })
    log("Escribiendo analysis.json / analysis.txt ...")
    write_reports(ctx, run_dir, opt)
    if opt.png:
        write_pngs(ctx, masks_dir, run_dir, opt)

    # [6G.1-R/A] Guarda final fail-closed sobre el provisional, ANTES de
    # publicar: VERIFICACION INCIERTA = ABORTO. Sin fallback
    # _check_unchanged_6g ni aprobación alternativa; excepción -> aborto.
    # Cierre de recursos garantizado en finally.
    _h6g1 = ctx.get("_mix_handle_6g1")
    try:
        ctx["container_6g"]["after"] = _h6g1.verificar()
        ctx["container_6g"]["ruta_actual"] = _h6g1.ruta_apunta_al_mismo_objeto()
    except Exception as _exc6g1:
        ctx["container_6g"]["after"] = dict(unchanged=False,
                                            reason="excepcion: %s" % _exc6g1)
        ctx["container_6g"]["ruta_actual"] = dict(unchanged=False,
                                                  reason="excepcion: %s" % _exc6g1)
    finally:
        try:
            _h6g1.close()
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
        raise _VerifFallida_6g1("guarda final no superada; no se publica")
    # [6G.1-R/G] Publicación con no-reemplazo atómico (renameat2
    # RENAME_NOREPLACE): nunca sustituye un destino existente; ante colisión
    # elige otro identificador sin tocarlo; si el entorno no garantiza la
    # operación, NO publica (fail-closed) y conserva el provisional.
    try:
        run_dir_final = _publicar_dir_6g1(run_dir, run_dir_final)
    except Exception as _exc_pub:
        log("[FATAL] publicacion segura no garantizada (%s); sin publicar; "
            "corrida conservada en: %s" % (_exc_pub, run_dir))
        raise _VerifFallida_6g1("publicacion no garantizada; no se publica")
    log("Directorio final: %s" % run_dir_final)
    log("Duracion total: %.1f s" % (time.monotonic() - t_start))
    return run_dir_final


def post_wav_identity(mix_path, sdv_path, sdi_path):
    """Test de identidad tras escritura y relectura del WAV
    (spec reconstruction_validation.post_wav_test). Streaming."""
    acc = {"sum_mix2": 0.0, "sum_err2": 0.0, "n": 0,
           "sab": 0.0, "sa": 0.0, "sb": 0.0, "saa": 0.0, "sbb": 0.0}
    peak = {"mix": 0.0, "sdv": 0.0, "sdi": 0.0, "sum": 0.0}
    frames_seen = None
    with sf.SoundFile(mix_path) as hm, \
         sf.SoundFile(sdv_path) as hv, \
         sf.SoundFile(sdi_path) as hi:
        if not (hm.frames == hv.frames == hi.frames):
            return {"status": "length_mismatch",
                    "mix_frames": hm.frames, "sdv_frames": hv.frames,
                    "sdi_frames": hi.frames}
        frames_seen = hm.frames
        while True:
            m = hm.read(OUTPUT_AUDIO_BLOCKSIZE, dtype="float64",
                        always_2d=True)
            if m.shape[0] == 0:
                break
            v = hv.read(m.shape[0], dtype="float64", always_2d=True)
            i = hi.read(m.shape[0], dtype="float64", always_2d=True)
            mm_ = mono_downmix(m)
            vv = mono_downmix(v)
            ii = mono_downmix(i)
            err = mm_ - vv - ii
            acc["sum_mix2"] += float(np.square(mm_).sum())
            acc["sum_err2"] += float(np.square(err).sum())
            acc["n"] += len(mm_)
            acc["sa"] += float(vv.sum())
            acc["sb"] += float(ii.sum())
            acc["saa"] += float(np.square(vv).sum())
            acc["sbb"] += float(np.square(ii).sum())
            acc["sab"] += float((vv * ii).sum())
            peak["mix"] = max(peak["mix"], float(np.abs(m).max()))
            peak["sdv"] = max(peak["sdv"], float(np.abs(v).max()))
            peak["sdi"] = max(peak["sdi"], float(np.abs(i).max()))
            peak["sum"] = max(peak["sum"], float(np.abs(v + i).max()))
    n = max(acc["n"], 1)
    rms_err = math.sqrt(acc["sum_err2"] / n)
    snr = (10.0 * math.log10(acc["sum_mix2"] / acc["sum_err2"])
           if acc["sum_err2"] > 0 else float("inf"))
    ma = acc["sa"] / n
    mb = acc["sb"] / n
    va = max(acc["saa"] / n - ma * ma, 0.0)
    vb = max(acc["sbb"] / n - mb * mb, 0.0)
    cov = acc["sab"] / n - ma * mb
    corr_mix_sdv = cov / math.sqrt(va * vb) if va > 0 and vb > 0 else None
    return {
        "status": "ok",
        "identity_snr_db": snr,
        "rms_error": rms_err,
        "sdv_vs_mix_correlation_proxy": corr_mix_sdv,
        "max_abs_sum_sdv_sdi": peak["sum"],
        "expected_min_snr_db": IDENTITY_SNR_EXPECTED_DB,
        "definition": "SDV.wav + SDI.wav (releidos) vs Mix Original",
        "frames": frames_seen,
    }


# ============================================================================
# SECCION 16: ANALYSIS.JSON BUILDER (24 secciones exigidas por el spec)
# ============================================================================

def build_document_meta(opt, pairs):
    meta = {
        "engine": ENGINE_NAME,
        "engine_version": ENGINE_VERSION,
        "spec_name": SPEC_NAME,
        "spec_version": SPEC_VERSION,
        "spec_file_sha256": getattr(opt, "spec_sha256", None),
        "manifest_path": opt.manifest_path,
        "mode": opt.mode,
        "generated_utc": utc_now_iso(),
        "primary_test_track_reference": "Elis - Die Stadt (spec)",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "soundfile": sf.__version__,
            "platform": platform.platform(),
            "matplotlib_available": MATPLOTLIB_OK,
        },
        "config_snapshot": {
            "n_fft": opt.n_fft,
            "hop_length": opt.hop,
            "power": opt.power,
            "epsilon": opt.epsilon,
            "chunk_frames": opt.chunk_frames,
            "smoothing_enabled": opt.smoothing,
            "consensus_default": opt.consensus_default,
            "guide_scale_compensation": GUIDE_SCALE_COMPENSATION,
            "output_subtype": OUTPUT_SUBTYPE,
            "mask_save_dtype": str(np.dtype(MASK_SAVE_DTYPE)),
            "allow_misaligned": opt.allow_misaligned,
            "write_all_candidates": opt.write_all_candidates,
        },
        "active_design_decisions": {
            "D1": "mascara neutra 0.5 fuera de cobertura de guides",
            "D2": "calculo float64 / almacenamiento float32",
            "D3": "salida %s sin dither" % OUTPUT_SUBTYPE,
            "D4": "mix FLOAT aceptado con nota",
            "D5": "6C: alineación por canal (ver schema y estados); "
                  "abort-confirmable, sin correccion",
            "D6": "guide mono permitido con warning",
            "D7": "PNGs opcionales (--png) con degradacion elegante",
            "D8": "allow_resampling NO implementado en v1",
            "D9": "smoothing mediana 3x3 opcional medido",
            "D10": "single_file = N=1 degenerado documentado",
            "D11": "median pairwise por submuestreo documentado",
            "D12": "archivo unico",
            "D13": "manifest opcional para reproducibilidad",
        },
    }
    return meta


def build_family_inventory(pairs):
    inv = {}
    for p in pairs:
        inv.setdefault(p.family, []).append(p.pair_id)
    return inv


def build_variant_inventory(pairs):
    inv = {}
    for p in pairs:
        inv.setdefault(p.family, {}).setdefault(p.variant, []).append(
            p.pair_id)
    return inv


def build_input_integrity(mix_info, pairs):
    def rec(info):
        return {
            "path": info.path,
            "role": info.role,
            "format": info.format,
            "subtype": info.subtype,
            "bit_depth_nominal": info.bit_depth_nominal,
            "sample_rate": info.sample_rate,
            "channels": info.channels,
            "frames": info.frames,
            "duration_s": info.duration_s,
            "size_bytes": info.size_bytes,
            "sha256": info.sha256,
            "warnings": info.warnings,
            "notes": info.notes,
        }
    return {
        "mix_original": rec(mix_info),
        "guides": [rec(getattr(p, role)) for p in pairs
                   for role in ("vocal", "instrumental")],
        "policies": {
            "mix_sample_rate": "reject_if_mismatch (44100)",
            "guide_sample_rate": "reject_by_default (44100); "
                                 "allow_resampling NO implementado (D8)",
            "duration": "verify_all + warning_if_difference; sin trimming",
            "channels": "stereo esperado; mono warn (D6); sin duplicacion",
        },
        "duration_comparisons": [compare_durations(mix_info,
                                                   getattr(p, role))
                                 for p in pairs
                                 for role in ("vocal", "instrumental")],
    }


def build_individual_metrics(pairs, mask_stats):
    out = []
    for k, p in enumerate(pairs):
        out.append({
            "pair_id": p.pair_id,
            "family": p.family,
            "variant": p.variant,
            "configuration": p.configuration,
            "source": p.source,
            "overlap": p.overlap,
            "vocal_mask_statistics": mask_stats_stream_finalize(
                mask_stats[k]),
            "instrumental_mask_definition": "Mi = 1 - Mv (complementaria)",
            "mask_formula": "Mv = V^p / (V^p + I^p + eps); Mi = 1 - Mv",
        })
    return out


def build_family_comparison(pairwise_out, pairs):
    """Agrupa pairwise por familia SIN eliminar la identidad de cada
    variante (spec multi_model_analysis.family_analysis)."""
    fam_of = {p.pair_id: p.family for p in pairs}
    intra, inter = [], []
    for rec in pairwise_out:
        if fam_of.get(rec["pair_a"]) == fam_of.get(rec["pair_b"]):
            intra.append(rec["correlation"])
        else:
            inter.append(rec["correlation"])
    return {
        "intra_family_pairs_count": len(intra),
        "intra_family_mean_correlation":
            float(np.mean(intra)) if intra else None,
        "inter_family_pairs_count": len(inter),
        "inter_family_mean_correlation":
            float(np.mean(inter)) if inter else None,
        "purpose": "medir si la diversidad entre arquitecturas aporta "
                   "informacion complementaria",
    }


def build_variant_comparison(pairwise_out, pairs):
    """Variantes de una misma familia: comportamiento complementario o
    redundante (spec multi_model_analysis.variant_analysis).
    Umbral operativo documentado: corr > 0.995 => 'redundant_like'
    (es una etiqueta operativa de comparacion, NO un veredicto)."""
    var_of = {p.pair_id: (p.family, p.variant) for p in pairs}
    out = []
    for rec in pairwise_out:
        fa, va = var_of.get(rec["pair_a"], (None, None))
        fb, vb = var_of.get(rec["pair_b"], (None, None))
        if fa is not None and fa == fb and va != vb:
            out.append({
                "family": fa,
                "variant_a": va, "variant_b": vb,
                "pair_a": rec["pair_a"], "pair_b": rec["pair_b"],
                "mask_correlation": rec["correlation"],
                "operational_label":
                    "redundant_like" if rec["correlation"] > 0.995
                    else "complementary_like",
            })
    return {"same_family_variant_comparisons": out,
            "note": "etiquetas operativas de comparacion; no veredictos"}


def build_model_agreement(pairwise_out):
    if not pairwise_out:
        return {"note": "N=1: agreement trivialmente total (D10); "
                        "pairwise no aplica"}
    corrs = [r["correlation"] for r in pairwise_out]
    diffs = [r["mean_absolute_mask_difference"] for r in pairwise_out]
    return {
        "pairwise_count": len(pairwise_out),
        "mean_pairwise_correlation": float(np.mean(corrs)),
        "min_pairwise_correlation": float(np.min(corrs)),
        "max_pairwise_correlation": float(np.max(corrs)),
        "mean_pairwise_absolute_difference": float(np.mean(diffs)),
        "principle": "la confianza representa concordancia entre modelos, "
                     "no verdad fisica absoluta (spec)",
    }


def write_reports(ctx, run_dir, opt):
    """Genera analysis.json (24 secciones, orden del spec) y analysis.txt."""
    per_cand = ctx["per_candidate"]
    reconstruction_metrics = {}
    bleeding_metrics = {}
    fidelity_metrics = {}
    stereo_metrics = {}
    mqr_table = {}
    for cid, mc in per_cand.items():
        reconstruction_metrics[cid] = mc["reconstruction_accuracy"]
        bleeding_metrics[cid] = mc["bleeding_metrics"]
        fidelity_metrics[cid] = mc["source_fidelity_metrics"]
        stereo_metrics[cid] = mc["stereo_metrics"]
        mqr_table[cid] = {
            "primary_dimensions": {
                "reconstruction_accuracy":
                    mc["reconstruction_accuracy"],
                "vocal_bleeding": {
                    "sdv_vs_instrumental_guide_correlation":
                        mc["bleeding_metrics"][
                            "sdv_vs_vocal_guide_correlation"],
                },
                "instrumental_bleeding": {
                    "sdi_vs_vocal_guide_correlation":
                        mc["bleeding_metrics"][
                            "sdi_vs_instrumental_guide_correlation"],
                },
                "spectral_preservation": {
                    "centroid_difference_sdv_mix":
                        mc["source_fidelity_metrics"][
                            "centroid_difference_sdv_mix"],
                    "centroid_difference_sdi_mix":
                        mc["source_fidelity_metrics"][
                            "centroid_difference_sdi_mix"],
                },
                "phase_coherence": {
                    "sdv_mean_abs_dphi_rad":
                        mc["stereo_metrics"]["phase_sdv"].get(
                            "output_minus_mix_mean_abs_dphi_rad"),
                    "sdi_mean_abs_dphi_rad":
                        mc["stereo_metrics"]["phase_sdi"].get(
                            "output_minus_mix_mean_abs_dphi_rad"),
                },
                "transient_preservation": {
                    "sdv": mc["source_fidelity_metrics"]["transient_sdv"],
                    "sdi": mc["source_fidelity_metrics"]["transient_sdi"],
                },
                "stereo_integrity": {
                    "sdv": mc["stereo_metrics"]["sdv"],
                    "sdi": mc["stereo_metrics"]["sdi"],
                },
            },
            "secondary_dimensions": {
                "rms_error": mc["reconstruction_accuracy"]["rms_error"],
                "peak_error": mc["reconstruction_accuracy"]["peak_error"],
                "identity_snr_db":
                    mc["reconstruction_accuracy"]["identity_snr_db"],
                "spectral_distance_relative":
                    mc["reconstruction_accuracy"][
                        "spectral_error_rms_relative"],
            },
        }

    reconstruction_metrics["post_wav_test"] = ctx["post_wav_validation"]

    analysis = {}
    # Orden EXACTO de las 24 secciones del spec analysis_json.required_sections
    analysis["document_meta"] = ctx["document_meta"]
    analysis["mix_original"] = build_input_integrity(ctx["mix_info"], [])[
        "mix_original"]
    analysis["guide_inventory"] = ctx["guide_inventory"]
    analysis["guide_family_inventory"] = ctx["guide_family_inventory"]
    analysis["guide_variant_inventory"] = ctx["guide_variant_inventory"]
    analysis["input_integrity"] = ctx["input_integrity"]
    analysis["alignment"] = ctx["alignment"]
    analysis["guide_scale_analysis"] = ctx["guide_scale_analysis"]
    analysis["stft_configuration"] = ctx["stft_configuration"]
    analysis["individual_model_metrics"] = ctx["individual_model_metrics"]
    analysis["pairwise_model_comparison"] = ctx["pairwise_model_comparison"]
    analysis["family_comparison"] = ctx["family_comparison"]
    analysis["variant_comparison"] = ctx["variant_comparison"]
    analysis["model_agreement"] = ctx["model_agreement"]
    analysis["model_disagreement"] = ctx["model_disagreement"]
    analysis["confidence_analysis"] = ctx["confidence_analysis"]
    analysis["consensus_methods"] = ctx["consensus_methods"]
    analysis["reconstruction_metrics"] = reconstruction_metrics
    analysis["bleeding_metrics"] = bleeding_metrics
    analysis["source_fidelity_metrics"] = fidelity_metrics
    analysis["stereo_metrics"] = stereo_metrics
    analysis["mqr_evaluation"] = mqr_table
    analysis["validation_status"] = build_validation_status(ctx, opt)
    analysis["scientific_interpretation"] = build_interpretation(ctx, opt)

    with open(os.path.join(run_dir, "analysis.json"), "w",
              encoding="utf-8") as f:
        json.dump(json_safe(analysis), f, indent=2, ensure_ascii=False,
                  allow_nan=False)
    _registrar_propio_6g1(os.path.join(run_dir, "analysis.json"), estable=True)
    write_analysis_txt(analysis, os.path.join(run_dir, "analysis.txt"))
    _registrar_propio_6g1(os.path.join(run_dir, "analysis.txt"), estable=True)


def build_validation_status(ctx, opt):
    """Fail closed; permission to run is not a validation result."""
    items = []
    def check(name, status, **detail):
        items.append(dict(check=name, status=status, **detail))
    def check_info(name, info):
        check(name+'_valid', 'pass' if info.valid and not info.errors else 'fail', errors=list(info.errors))
        check(name+'_sample_rate_44100','pass' if info.sample_rate==REQUIRED_SAMPLE_RATE else 'fail')
        for w in info.warnings:
            check(name+'_warning','warning',detail=w)
    check_info('mix',ctx['mix_info'])
    expected = []
    for p in ctx['pairs']:
        for role in ('vocal','instrumental'):
            expected.append((p.pair_id,role))
            check_info(p.pair_id+'/'+role,getattr(p,role))
    seen = []
    for rec in ctx.get('alignment',[]):
        pair,role = rec.get('pair_id'),rec.get('role')
        seen.append((pair,role))
        name = 'alignment_%s/%s' % (pair,role)
        state = rec.get('classification','ERROR')
        check(name,state,offset_samples=rec.get('estimated_offset_samples'),error=rec.get('error'),
              reason=rec.get('reason'),channels={ch:v['classification'] for ch,v in rec.get('channels',{}).items()})
        if state not in (*_MEASURED,'AMBIGUOUS','INSUFFICIENT_SIGNAL','ERROR'):
            check(name+'_unknown_class','fail',detail=state)
        if rec.get('error') or any(v.get('error') for v in rec.get('channels',{}).values()):
            check(name+'_error','fail',detail=rec)
        if state in ('ALIGNED','WARNING') and (rec.get('estimated_offset_samples') is None or
                not (rec.get('alignment_confidence') or 0)>0 or not rec.get('channels') or
                any(v['classification'] not in ('ALIGNED','WARNING') for v in rec['channels'].values())):
            check(name+'_evidence','fail')
    if not expected or len(expected)!=len(set(expected)) or len(seen)!=len(expected) or set(seen)!=set(expected):
        check('alignment_inventory','fail',expected=expected,observed=seen)
    for w in ctx.get('warnings',[]):
        check('warning','warning',detail=w)
    for e in ctx.get('errors',[]):
        check('error','fail',detail=e)
    if ctx.get('misalignment_user_authorized'):
        check('misalignment_user_authorized','recorded',source=ctx.get('alignment_permission'))
    gate = ctx.get('alignment_gate')
    if gate:
        check('alignment_gate', 'pass' if gate.get('allowed') else 'fail',
              verdict=gate.get('verdict'), permission=gate.get('permission'),
              blocking=gate.get('blocking'))
    post = ctx.get('post_wav_validation')
    if post is not None or opt.mode==MODE_FULL_PROCESSING:
        check('post_wav','pass' if post and post.get('status')=='ok' else 'fail',detail=post)
    statuses = {i['status'] for i in items}
    overall = ('fail' if statuses-{'pass','ALIGNED','WARNING','warning','recorded'} else
               'pass_with_warnings' if statuses & {'WARNING','warning'} else 'pass')
    return dict(overall=overall, items=items, engine_exit_mode=opt.mode)


def build_interpretation(ctx, opt):
    facs = []
    for rec in ctx.get("guide_scale_analysis", []):
        af = rec.get("applied_factors", {})
        facs.append("%s(g_v=%.3f, g_i=%.3f)" % (rec.get("pair_id"),
                                                af.get("vocal", 1.0),
                                                af.get("instrumental", 1.0)))
    conf_stats = ctx["confidence_analysis"]["map_statistics"]
    lines = [
        "Resumen factual de la corrida (sin veredictos):",
        "- Pares procesados: %d | metodo de consenso entregado por defecto: "
        "%s (los 3 metodos se generaron completos)"
        % (len(ctx["pairs"]), opt.consensus_default),
        "- Factores de escala aplicados: %s" % ", ".join(facs),
        "- Confianza media del mapa: %.4f (concordancia entre modelos, no "
        "verdad fisica)" % conf_stats.get("mean", float("nan")),
        "- Los 6+ candidatos (individuales + consensos) fueron evaluados "
        "con MQR en un solo pase; solo SDV/SDI del consenso default se "
        "escribieron como audio (spec outputs.required_audio).",
        "- La identidad SDV+SDI=Mix es exacta por construccion; las "
        "metricas de reconstruccion cuantifican el camino numerico "
        "(OLA + cuantizacion), no la calidad de separacion.",
        "- La escucha critica (calibration_protocol fase 08) es HUMANA y "
        "queda fuera del alcance de este script.",
    ]
    return {
        "summary": lines,
        "claims_not_allowed_without_measurement": list(CLAIMS_NOT_ALLOWED),
        "interpretation_policy": "Este informe reporta mediciones y "
                                 "estados. Ninguna afirmacion de la lista "
                                 "claims_not_allowed puede formularse sin "
                                 "medicion experimental dedicada (spec "
                                 "scientific_status).",
    }


# ============================================================================
# SECCION 17: ANALYSIS.TXT BUILDER (informe legible)
# ============================================================================

def _fmt(v, nd=4):
    if v is None:
        return "null"
    if isinstance(v, float):
        return ("%.*f" % (nd, v))
    return str(v)


def write_analysis_txt(analysis, path):
    L = []
    A = lambda s: L.append(s)
    A("=" * 76)
    A("INFORME MQR - %s v%s (spec %s v%s)" % (ENGINE_NAME, ENGINE_VERSION,
                                               SPEC_NAME, SPEC_VERSION))
    A("=" * 76)
    dm = analysis["document_meta"]
    A("Modo: %s | generado: %s" % (dm.get("mode"), dm.get("generated_utc")))
    A("Entorno: python %s | numpy %s | scipy %s | soundfile %s"
      % (dm["environment"]["python"], dm["environment"]["numpy"],
         dm["environment"]["scipy"], dm["environment"]["soundfile"]))
    A("")
    A("--- MIX ORIGINAL -------------------------------------------------------")
    mo = analysis["mix_original"]
    A("%s | %s | %d Hz | %d ch | %d frames (%.2f s) | %s"
      % (os.path.basename(mo["path"]), mo["subtype"], mo["sample_rate"],
         mo["channels"], mo["frames"], mo["duration_s"], mo["sha256"][:16]))
    A("")
    A("--- GUIDES -------------------------------------------------------------")
    for g in analysis["guide_inventory"]:
        A("%s | family=%s | variant=%s | config=%s | overlap=%s"
          % (g["pair_id"], g["family"], g["variant"], g["configuration"],
             g.get("overlap") or "-"))
    A("")
    A("--- ALINEACION (deteccion sin correccion) ------------------------------")
    for r in analysis["alignment"]:
        A('%s/%s: %s' % (r.get('pair_id'), r.get('role'), _alignment_line(r)))
    A("")
    A("--- ESCALA DE GUIDES ----------------------------------------------------")
    for r in analysis["guide_scale_analysis"]:
        af = r.get("applied_factors", {})
        A("%s: g_vocal=%s g_instr=%s (politica=%s)"
          % (r.get("pair_id"), _fmt(af.get("vocal")),
             _fmt(af.get("instrumental")), r.get("compensation_policy")))
    A("")
    A("--- STFT ----------------------------------------------------------------")
    sc = analysis["stft_configuration"]
    A("n_fft=%s hop=%s window=%s center=%s | K=%s frames x %s bins | "
      "chunk=%s"
      % (sc["n_fft"], sc["hop_length"], sc["window"], sc["center"],
         sc["frames_total"], sc["bins"], sc["chunk_frames"]))
    A("")
    A("--- COMPARACION PAIRWISE ------------------------------------------------")
    for r in analysis["pairwise_model_comparison"]:
        A("%s vs %s: mean|dM|=%s RMSE=%s corr=%s median|dM|~%s"
          % (r["pair_a"], r["pair_b"],
             _fmt(r["mean_absolute_mask_difference"]),
             _fmt(r["rmse_mask_difference"]),
             _fmt(r["correlation"]),
             _fmt(r["median_absolute_difference"])))
    if not analysis["pairwise_model_comparison"]:
        A("(N=1: pairwise no aplica - D10)")
    A("")
    A("--- CONFIANZA / DESACUERDO -----------------------------------------------")
    cs = analysis["confidence_analysis"]["map_statistics"]
    A("confidence map: mean=%s median=%s | high(>=0.67)=%.1f%% | "
      "low(<=0.33)=%.1f%%"
      % (_fmt(cs.get("mean")), _fmt(cs.get("median")),
         100.0 * (cs.get("fraction_high_confidence_ge_0.67") or 0.0),
         100.0 * (cs.get("fraction_low_confidence_le_0.33") or 0.0)))
    ds = analysis["model_disagreement"]["map_statistics"]
    A("disagreement map: mean=%s median=%s"
      % (_fmt(ds.get("mean")), _fmt(ds.get("median"))))
    A("")
    A("--- CONSENSO -------------------------------------------------------------")
    cm = analysis["consensus_methods"]
    A("default=%s | cross-method differences: %s"
      % (cm["default"], json.dumps(json_safe(cm["cross_method_differences"]),
                                   ensure_ascii=False)))
    A("")
    A("--- MQR POR CANDIDATO -----------------------------------------------------")
    for cid, table in analysis["mqr_evaluation"].items():
        prim = table["primary_dimensions"]
        sec = table["secondary_dimensions"]
        A("%s:" % cid)
        A("  identity: SNR=%s dB | rms_err=%s | spectral_err_rel=%s"
          % (_fmt(sec["identity_snr_db"], 2), _fmt(sec["rms_error"]),
             _fmt(sec["spectral_distance_relative"])))
        st = prim["stereo_integrity"]["sdv"]
        A("  stereo SDV: ICC=%s | S/M=%s | dphi=%s rad"
          % (_fmt((st or {}).get("inter_channel_correlation")),
             _fmt((st or {}).get("side_to_mid_energy_ratio")),
             _fmt(prim["phase_coherence"]["sdv_mean_abs_dphi_rad"], 6)))
        tr = prim["transient_preservation"]["sdv"]
        A("  transient SDV: corr=%s | rel_diff=%s"
          % (_fmt((tr or {}).get("onset_correlation")),
             _fmt((tr or {}).get("onset_rms_relative_difference"))))
    A("")
    A("--- VALIDACION POST-WAV ----------------------------------------------------")
    pw = analysis["reconstruction_metrics"].get("post_wav_test")
    if pw:
        A("status=%s | SNR=%s dB (esperado > %s) | rms_err=%s"
          % (pw.get("status"), _fmt(pw.get("identity_snr_db"), 2),
             pw.get("expected_min_snr_db"), _fmt(pw.get("rms_error"))))
    else:
        A("(no computado en este modo)")
    A("")
    A("--- INTERPRETACION CIENTIFICA -----------------------------------------------")
    for line in analysis["scientific_interpretation"]["summary"]:
        A(line)
    A("PROHIBIDO sin medicion dedicada: %s"
      % "; ".join(analysis["scientific_interpretation"]
                  ["claims_not_allowed_without_measurement"]))
    A("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")


# ============================================================================
# SECCION 18: SELF-TEST SINTETICO INTERNO (--self-test)
# ============================================================================

def _st_write(path, data, subtype="PCM_16"):
    sf.write(path, data, REQUIRED_SAMPLE_RATE, subtype=subtype)


def run_self_test():
    """Autodiagnostico sin dependencias externas (decision previa #6,
    reinterpretada). Verifica invariantes criticas del motor:
      T1 roundtrip STFT->ISTFT exacto (< 1e-12)
      T2 invariancia de escala de la mascara (ratio)
      T3 complementariedad Mi=1-Mv e identidad de reconstruccion
      T4 consenso degenerado N=1 (D10)
      T5 pesos de consenso normalizados y acotados
      T6 convencion de signo del alineamiento (lags conocidos)
      T7 pipeline e2e minimo con senales sinteticas (2 pares)
    Devuelve True si TODAS pasan."""
    rng = np.random.default_rng(20260916)
    results = []

    # --- T1: roundtrip --------------------------------------------------------
    N = int(2.7 * REQUIRED_SAMPLE_RATE)
    x = rng.standard_normal((N, 2)) * 0.3
    plan = FramePlan(N, 4096, 1024)
    n_frames = plan.K
    s0, s1 = plan.span_for_frames(0, n_frames)
    span = read_span_from_array(x, s0, s1)
    X = stft_span_frames(span, n_frames, plan)
    ola = OlaStream(plan, 2)
    out, a, b = ola.push(X)
    out2, a2, b2 = ola.flush()
    recon = np.zeros((N, 2), dtype=np.float64)
    recon[a:b] = out
    overlap_ok = True
    if out2 is not None and b2 > a2:
        if a2 < b:
            overlap_ok = False
        else:
            recon[a2:b2] = out2
    err1 = float(np.abs(recon - x).max()) if overlap_ok else float("inf")
    results.append(("T1 roundtrip STFT->ISTFT < 1e-12", err1 < 1e-12,
                    "max_err=%.2e" % err1))

    # --- T2: invariancia de escala ---------------------------------------------
    Am = rng.random((33, 7)) + 0.1
    Bm = rng.random((33, 7)) + 0.1
    m1 = compute_vocal_mask(Am, Bm, 2.0, 1e-9)
    m2 = compute_vocal_mask(Am * 7.3, Bm * 7.3, 2.0, 1e-9)
    err2 = float(np.abs(m1 - m2).max())
    results.append(("T2 mascara invariante a escala comun (< 1e-6)",
                    err2 < 1e-6, "max_err=%.2e" % err2))

    # --- T3: complementariedad e identidad --------------------------------------
    mi = 1.0 - m1
    err3a = float(np.abs(m1 + mi - 1.0).max())
    mix_spec = (rng.standard_normal((33, 7))
                + 1j * rng.standard_normal((33, 7)))
    ident = mix_spec * (m1 + mi)
    err3b = float(np.abs(ident - mix_spec).max())
    results.append(("T3 Mi=1-Mv e identidad Mix*(Mv+Mi)=Mix (< 1e-14)",
                    err3a < 1e-14 and err3b < 1e-14,
                    "err_a=%.2e err_b=%.2e" % (err3a, err3b)))

    # --- T4: consenso N=1 (D10) ---------------------------------------------------
    cons1, wsum = consensus_from_masks([m1], np.ones_like(m1)[None, :, :])
    err4 = float(np.abs(cons1["weighted_mean"] - m1).max())
    err4 += float(np.abs(cons1["median"] - m1).max())
    err4 += float(np.abs(cons1["confidence_weighted_mean"] - m1).max())
    results.append(("T4 consenso N=1 trivial e identico (< 1e-15)",
                    err4 < 1e-15 and wsum.get("degenerate") is True,
                    "max_err=%.2e" % err4))

    # --- T5: pesos del consenso -----------------------------------------------------
    masks3 = [m1, m1 * 0.5, np.clip(m1 + 0.2, 0.0, 1.0)]
    conf, dis, c_k = confidence_and_disagreement(masks3)
    cons3, _ = consensus_from_masks(masks3, c_k)
    cw = cons3["confidence_weighted_mean"]
    lo = np.stack(masks3).min(axis=0)
    hi = np.stack(masks3).max(axis=0)
    inside = bool(np.all(cw >= lo - 1e-12) and np.all(cw <= hi + 1e-12))
    results.append(("T5 confidence_weighted_mean dentro de [min,max]",
                    inside, "ok=%s" % inside))

    # --- T6: convencion de alineacion -----------------------------------------
    # NOTA DE DISENO: el alineamiento exige estructura transitoria en la
    # envolvente (como musica real). Con envolventes puramente lentas o
    # tonos puros la NCC es plana (problema inherentemente mal planteado,
    # no defecto del motor). Rafagas gaussianas de 4 ms sobre ruido.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        sr = REQUIRED_SAMPLE_RATE
        t = np.arange(int(10.0 * sr)) / sr
        env = np.full(len(t), 0.15)
        for p_m in rng.uniform(0.2, 9.8, size=40):
            env += 0.8 * np.exp(-0.5 * np.square((t - p_m) / 0.004))
        mix = (env * rng.standard_normal(len(t)))[:, None]
        D1 = 1500   # guide ATRASADO 1500 muestras -> offset esperado -1500
        D2 = -800   # guide ADELANTADO 800 muestras -> offset esperado +800
        g_delayed = np.zeros_like(mix)
        g_delayed[D1:] = mix[:len(mix) - D1]
        g_advanced = np.zeros_like(mix)
        g_advanced[:len(mix) + D2] = mix[-D2:]
        p_mix = os.path.join(td, "mix.wav")
        p_g1 = os.path.join(td, "g_delayed.wav")
        p_g2 = os.path.join(td, "g_advanced.wav")
        _st_write(p_mix, mix)
        _st_write(p_g1, g_delayed)
        _st_write(p_g2, g_advanced)
        mi_mix = probe_file(p_mix, "mix")
        mi_g1 = probe_file(p_g1, "vocal_guide")
        mi_g2 = probe_file(p_g2, "vocal_guide")
        r1 = analyze_alignment(mi_mix, mi_g1)
        r2 = analyze_alignment(mi_mix, mi_g2)
        ok6 = (all(r.get("estimated_offset_samples") is not None for r in (r1,r2))
               and abs(r1["estimated_offset_samples"] + D1) <= 2
               and abs(r2["estimated_offset_samples"] - (-D2)) <= 2
               and r1["classification"] == "MISALIGNED")
        results.append(("T6 convencion de offset (delay->-1500, "
                        "advance->+800)", ok6,
                        "r1=%s r2=%s" % (r1["estimated_offset_samples"],
                                           r2["estimated_offset_samples"])))

    # --- T7: pipeline e2e minimo -------------------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        sr = REQUIRED_SAMPLE_RATE
        dur = 2.0
        n = int(dur * sr)
        t = np.arange(n) / sr
        vocal = (0.4 * np.sin(2 * math.pi * 440.0 * t)
                 * (0.6 + 0.4 * np.sin(2 * math.pi * 3.0 * t)))
        instr = 0.3 * np.sin(2 * math.pi * 110.0 * t) \
            + 0.05 * rng.standard_normal(n)
        mix = np.stack([vocal + instr, vocal + instr], axis=1) * 0.5
        p_mix = os.path.join(td, "mix.wav")
        _st_write(p_mix, mix)
        pairs = []
        for i, noise in enumerate((0.02, 0.08), start=1):
            vg = np.stack([vocal + noise * rng.standard_normal(n)] * 2,
                          axis=1) * 0.5
            ig = np.stack([instr + noise * rng.standard_normal(n)] * 2,
                          axis=1) * 0.5
            pv = os.path.join(td, "v%d.wav" % i)
            pi_ = os.path.join(td, "i%d.wav" % i)
            _st_write(pv, vg)
            _st_write(pi_, ig)
            pairs.append(PairMeta(
                pair_id="guide_pair_%02d" % i,
                family="Synth_Family", variant="v%d" % i,
                configuration="test", vocal_path=pv,
                instrumental_path=pi_, source="SYNTH"))
        opt = argparse.Namespace(
            n_fft=2048, hop=512, power=2.0, epsilon=1e-9, chunk_frames=32,
            smoothing=False, allow_misaligned=True, write_all_candidates=False,
            png=False, out_base=td, consensus_default="confidence_weighted_mean",
            interactive=False, manifest_path=None, spec_sha256=None,
            mode=MODE_FULL_PROCESSING)
        code, run_dir = run_experiment(p_mix, pairs, MODE_FULL_PROCESSING, opt)
        ok_files = False
        snr_ok = False
        sections_ok = False
        if code == EXIT_OK and run_dir:
            ok_files = (os.path.isfile(os.path.join(run_dir, "SDV.wav"))
                        and os.path.isfile(os.path.join(run_dir, "SDI.wav"))
                        and os.path.isfile(os.path.join(run_dir,
                                                        "analysis.json")))
            with open(os.path.join(run_dir, "analysis.json"), "r",
                      encoding="utf-8") as f:
                aj = json.load(f)
            required = ["document_meta", "mix_original", "guide_inventory",
                        "guide_family_inventory", "guide_variant_inventory",
                        "input_integrity", "alignment", "guide_scale_analysis",
                        "stft_configuration", "individual_model_metrics",
                        "pairwise_model_comparison", "family_comparison",
                        "variant_comparison", "model_agreement",
                        "model_disagreement", "confidence_analysis",
                        "consensus_methods", "reconstruction_metrics",
                        "bleeding_metrics", "source_fidelity_metrics",
                        "stereo_metrics", "mqr_evaluation",
                        "validation_status", "scientific_interpretation"]
            sections_ok = all(k in aj for k in required)
            pw = aj["reconstruction_metrics"].get("post_wav_test") or {}
            snr = pw.get("identity_snr_db")
            snr_ok = snr is not None and snr > 80.0
        results.append(("T7 pipeline e2e (exit=0, archivos, 24 secciones, "
                        "SNR post-wav > 80 dB)",
                        code == EXIT_OK and ok_files and sections_ok
                        and snr_ok,
                        "exit=%s files=%s sections=%s snr_ok=%s"
                        % (code, ok_files, sections_ok, snr_ok)))

    # --- resumen --------------------------------------------------------------------------
    print("")
    print("=" * 72)
    print("SELF-TEST %s v%s" % (ENGINE_NAME, ENGINE_VERSION))
    print("=" * 72)
    all_ok = True
    for name, ok, info in results:
        print("  [%s] %s  (%s)" % ("PASS" if ok else "FAIL", name, info))
        all_ok = all_ok and ok
    print("=" * 72)
    print("  RESULTADO GLOBAL: %s" % ("PASS" if all_ok else "FAIL"))
    print("=" * 72)
    return all_ok


def write_pngs(ctx, masks_dir, run_dir, opt):
    """Visualizaciones opcionales (spec outputs.optional_visualizations,
    decision D7: degradacion elegante sin matplotlib)."""
    if not MATPLOTLIB_OK:
        log("[WARN] matplotlib no disponible; PNGs omitidos (D7)")
        return
    try:
        png_dir = os.path.join(run_dir, "png")
        os.makedirs(png_dir, exist_ok=True)

        def _load_down(name, max_dim=1024):
            arr = np.load(os.path.join(masks_dir, name), mmap_mode="r")
            a = np.asarray(arr, dtype=np.float32)
            step_r = max(1, a.shape[0] // max_dim)
            step_c = max(1, a.shape[1] // max_dim)
            return a[::step_r, ::step_c]

        plots = [
            ("consensus_vocal_%s.npy" % opt.consensus_default,
             "consensus_vocal_%s" % opt.consensus_default, "magma"),
            ("consensus_instrumental_%s.npy" % opt.consensus_default,
             "consensus_instrumental_%s" % opt.consensus_default, "magma"),
            ("confidence_map.npy", "confidence_map", "viridis"),
            ("model_disagreement_map.npy", "model_disagreement_map",
             "inferno"),
        ]
        for fname, title, cmap in plots:
            path = os.path.join(masks_dir, fname)
            if not os.path.isfile(path):
                continue
            a = _load_down(os.path.basename(fname))
            fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
            im = ax.imshow(a, aspect="auto", origin="lower", cmap=cmap,
                           vmin=0.0, vmax=1.0)
            ax.set_title(title)
            ax.set_xlabel("frame")
            ax.set_ylabel("bin")
            fig.colorbar(im, ax=ax)
            fig.savefig(os.path.join(png_dir, "%s.png" % title), dpi=120)
            plt.close(fig)
        # comparacion de candidatos (identity SNR por candidato)
        cands = ctx.get("per_candidate", {})
        names = list(cands.keys())
        vals = [cands[c]["reconstruction_accuracy"]["identity_snr_db"]
                for c in names]
        vals = [float(v) if v is not None and not math.isinf(v)
                else 0.0 for v in vals]
        if names:
            fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
            ax.barh(names, vals, color="#3B6EA5")
            ax.set_xlabel("identity SNR (dB)")
            ax.set_title("model_comparison: SDV+SDI vs Mix")
            fig.savefig(os.path.join(png_dir, "model_comparison.png"),
                        dpi=120)
            plt.close(fig)
        log("PNGs generados en %s" % png_dir)
    except Exception as exc:
        log("[WARN] fallo generando PNGs (degradacion elegante D7): %s"
            % exc)


# ============================================================================
# SECCION 19: CLI (modos, manifest, interactivo) + MAIN
# ============================================================================

def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="sdv_sdi_mqr_engine.py",
        description="%s v%s - consenso de mascaras TF aplicado "
                    "exclusivamente al Mix Original (spec %s v%s)"
                    % (ENGINE_NAME, ENGINE_VERSION, SPEC_NAME, SPEC_VERSION))
    p.add_argument("--manifest", default=None,
                   help="JSON con mix_original + pairs (D13); rutas "
                        "relativas al propio manifest")
    p.add_argument("--mix", default=None,
                   help="ruta del Mix Original (los pares se piden "
                        "interactivamente)")
    p.add_argument("--mode", default=None, choices=list(REQUIRED_MODES),
                   help="dry_run | analysis_only | single_file | "
                        "full_processing (default: menu interactivo)")
    p.add_argument("--out", default=".", help="directorio base de salida")
    p.add_argument("--n-fft", type=int, default=N_FFT_DEFAULT,
                   help="permitidos por el spec: %s" % (N_FFT_ALLOWED,))
    p.add_argument("--hop", type=int, default=HOP_LENGTH_DEFAULT)
    p.add_argument("--power", type=float, default=POWER_DEFAULT)
    p.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    p.add_argument("--chunk-frames", type=int, default=CHUNK_FRAMES_DEFAULT,
                   help="frames STFT por chunk (memoria Android)")
    p.add_argument("--consensus", default=CONSENSUS_DEFAULT,
                   choices=list(CONSENSUS_METHODS),
                   help="candidato escrito como SDV.wav/SDI.wav (los 3 "
                        "metodos se calculan siempre)")
    p.add_argument("--smoothing", action="store_true",
                   help="suavizado mediana 3x3 (D9, default OFF)")
    p.add_argument("--allow-misaligned", action="store_true",
                   help="6C: continuar sin shift con alineación no validada, excepto ERROR")
    p.add_argument("--write-all-candidates", action="store_true",
                   help="escribir SDV/SDI de TODOS los candidatos en "
                        "candidates/")
    p.add_argument("--png", action="store_true",
                   help="visualizaciones PNG opcionales (D7)")
    p.add_argument("--spec-json", default=None,
                   help="ruta del spec para registrar su sha256 en "
                        "document_meta (trazabilidad)")
    p.add_argument("--self-test", action="store_true",
                   help="autodiagnostico sintetico del motor")
    return p


def _interactive_mode():
    print("Modo de ejecucion (spec cli.required_modes):")
    print("  [1] full_processing  (mascaras + consenso + SDV/SDI + MQR)")
    print("  [2] analysis_only    (mascaras + consenso + informes, sin WAV)")
    print("  [3] dry_run          (validacion + plan, sin computo)")
    print("  [4] single_file      (un solo par, N=1 degenerado - D10)")
    choice = _prompt_optional("Seleccion", "1")
    return {
        "1": MODE_FULL_PROCESSING, "2": MODE_ANALYSIS_ONLY,
        "3": MODE_DRY_RUN, "4": MODE_SINGLE_FILE,
    }.get(choice, MODE_FULL_PROCESSING)


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        ok = run_self_test()
        return EXIT_OK if ok else EXIT_PROCESSING

    if args.n_fft not in N_FFT_ALLOWED:
        print("[FATAL] n_fft=%d fuera de politica del spec %s"
              % (args.n_fft, N_FFT_ALLOWED))
        return EXIT_VALIDATION
    if args.n_fft % args.hop != 0:
        print("[FATAL] hop=%d debe dividir n_fft=%d"
              % (args.hop, args.n_fft))
        return EXIT_VALIDATION
    if args.power <= 0 or args.epsilon <= 0:
        print("[FATAL] power y epsilon deben ser positivos")
        return EXIT_VALIDATION
    if args.chunk_frames < 8:
        print("[FATAL] chunk_frames >= 8 requerido")
        return EXIT_VALIDATION

    mode = args.mode or _interactive_mode()
    if mode == MODE_SINGLE_FILE and args.manifest is None:
        pass  # la coleccion interactiva limitara a 1 par
    try:
        if args.manifest:
            mix_path, pairs = load_manifest(args.manifest)
        else:
            if args.mix:
                mix_path = args.mix
                print("[Paso 2-3] pares de guides (interactivo)")
                n_default = "1" if mode == MODE_SINGLE_FILE else "3"
                while True:
                    try:
                        n = int(_prompt_required("Numero de pares",
                                                 n_default))
                        if 1 <= n <= MAX_PAIRS:
                            break
                    except ValueError:
                        pass
                    print("    valor invalido; enter 1-%d." % MAX_PAIRS)
                pairs = []
                for i in range(1, n + 1):
                    print("Par %d/%d" % (i, n))
                    pairs.append(PairMeta(
                        pair_id=_prompt_optional("  pair_id",
                                                 "guide_pair_%02d" % i),
                        family=_prompt_required("  family"),
                        variant=_prompt_required("  variant"),
                        configuration=_prompt_required("  configuration"),
                        vocal_path=_prompt_required("  vocal_guide"),
                        instrumental_path=_prompt_required(
                            "  instrumental_guide"),
                        source=_prompt_optional("  source", "MVSEP"),
                        overlap=_prompt_optional("  overlap", ""),
                    ))
            else:
                mix_path, pairs = interactive_collect_inputs(mode)
    except (OSError, KeyError, ValueError, json.JSONDecodeError) as exc:
        print("[FATAL] entradas invalidas: %s" % exc)
        return EXIT_VALIDATION

    if mode == MODE_SINGLE_FILE:
        if len(pairs) > 1:
            print("[INFO] single_file: se usa SOLO el primer par (D10)")
            pairs = pairs[:1]

    opt = argparse.Namespace(
        n_fft=args.n_fft, hop=args.hop, power=args.power,
        epsilon=args.epsilon, chunk_frames=args.chunk_frames,
        smoothing=args.smoothing, allow_misaligned=args.allow_misaligned,
        write_all_candidates=args.write_all_candidates, png=args.png,
        out_base=args.out, consensus_default=args.consensus,
        interactive=args.manifest is None, manifest_path=args.manifest,
        spec_sha256=None, mode=mode)
    if args.spec_json:
        try:
            opt.spec_sha256 = sha256_file(args.spec_json)
        except OSError as exc:
            print("[WARN] no se pudo hashear el spec: %s" % exc)

    code, run_dir = run_experiment(mix_path, pairs, mode, opt)
    if code == EXIT_OK and run_dir:
        print("")
        print("RESULTADO: OK")
        print("  salida: %s" % run_dir)
        print("  SDV.wav / SDI.wav / analysis.json / analysis.txt / masks/")
        return EXIT_OK
    if code == EXIT_ABORTED:
        return EXIT_ABORTED
    return code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[ABORT] interrumpido por el usuario")
        sys.exit(EXIT_ABORTED)
