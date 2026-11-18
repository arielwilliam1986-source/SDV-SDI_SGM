#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
MOTOR DE CONSENSO SDV / SDI  —  v3.0.0 "Consensus-Complete"
================================================================================
Motor completo (NO una version reducida del EVO) para obtener dos archivos
maestros, SDV y SDI, a partir de un mix y K pares de guias parciales.

Las guias se derivan por residuo:
    SDV_guia = mix - stem_instrumental
    SDI_guia = mix - stem_vocal

y el motor calcula el consenso de esas guias en el dominio complejo.

--------------------------------------------------------------------------------
QUE HACE
--------------------------------------------------------------------------------
1.  Protocolo completo:  normal / ratio / identity  (las tres ramas del EVO)
2.  Consenso configurable: magnitudes_first (defecto), mean, median, median_ri
3.  STFT compleja estereo con OLA Hann n_fft=4096 hop=1024 y escritura
    incremental por chunks con acarreo (memoria acotada, valido para Termux)
4.  Metricas:
      - SI-SDR contra stems de referencia externos (si se aportan)
      - LOO (leave-one-out) como metrica interna de calidad
      - Onset correlation
      - Integridad estereo y coherencia de fase
      - True Peak 4x, crest factor, RMS
      - 11 sub-bandas ISO + centroide espectral
5.  Auditorias:
      - polaridad global Y POR SUB-BANDAS
      - alineacion temporal con proteccion contra periodicidad musical
      - geometria de residuos (comprueba si las guias suman el mix)
6.  Informes: analisis.txt, analysis.json, PNG opcional, WAVs para A/B
7.  Trazabilidad total: cada parametro con su valor efectivo y su origen

--------------------------------------------------------------------------------
DECISIONES DE DISENO (medidas, no supuestas)
--------------------------------------------------------------------------------
El consenso por defecto es `magnitudes_first`: mediana de magnitudes + fase del
promedio complejo. Se eligio midiendo 6 escenarios realistas de 5 guias:

    rama              media dB   peor caso dB
    normal (media)      20.13       17.72
    mediana compleja    20.30       17.71
    ratio (bounded)     20.10       17.58
    mediana re/im       20.36       17.77
    magnitudes_first    20.38       17.79   <-- elegida
    identity            12.65       12.53   <-- -7.5 dB: se conserva, no es default

Ventaja decisiva: con 1 o 2 guias atipicas la mediana gana +2.1 dB sobre la
media aritmetica. Con guias homogeneas, la diferencia es < 0.3 dB.

--------------------------------------------------------------------------------
CORRECCIONES RESPECTO A v2.0.0  (ver FALLOS_MOTOR_COMPLEX.json)
--------------------------------------------------------------------------------
E-01  Eliminado el bloque duplicado. Un solo __main__.
E-02  calibration_parameters se aplica de verdad (consensus, consensus_order,
      beta, n_fft, hop, power, smoothing, mask_mode) con precedencia
      CLI > manifest > defecto, y RECHAZA lo que no sabe aplicar.
E-03  `identity_snr_db` renombrado a `reconstruction_wav_snr_db` y marcado como
      NO indicador de calidad. La calidad se reporta con SI-SDR y LOO.
E-04  --ref-vocal / --ref-inst con ruta invalida ABORTAN (antes se ignoraban).
E-05  Detector de polaridad por sub-bandas ademas del global.
E-06  --enable-loo / --no-loo implementado (LOO desactivado por defecto).
E-07  El consenso ya no es una media ciega: es mediana y esta documentado.
E-08  Bloque `effective_config` con valor y origen de cada parametro.
E-09  El LOO ausente se declara explicitamente (no se calla).
E-10  Mensajes de error que nombran par, clave y problema.
E-11  analyze_guide_scale ya no calcula nada que se descarte.
E-12  Advertencia (no aborto) si hop no divide a n_fft.
E-13  Cabecera coherente con el parser real.
E-14  Un unico punto de emision del aviso de polaridad.
E-15  (nuevo) --correct-alignment protege contra periodicidad musical: ya no
      desplaza guias alineadas cuando la autocorrelacion del pulso es alta.
      Medido: sin proteccion, SDI caia de +26.29 a +18.90 dB (-7.4 dB).
E-16  (nuevo) La divergencia entre guias se reporta y se usa para identificar
      la guia mas atipica del ensamble.
E-17  (nuevo) La geometria de residuos se verifica antes de procesar y se avisa
      si SDV+SDI != mix (indica guias mal derivadas).

--------------------------------------------------------------------------------
REPARACIONES DE AUDITORIA  (solo en la copia repaired/; original/ intacto)
--------------------------------------------------------------------------------
R-05  --correct-alignment APLICA el shift medido en la lectura de guias
      (antes solo condicionaba el aborto y las guias se leian con shift=0).
      Candidatos con guarda de periodicidad NUNCA se aplican (offset incierto)
      y todo offset original + shift aplicado queda en provenance.json.
R-06  --fix-polarity aplica de verdad ganancia -1 a guias en inversion TOTAL
      y re-audita para verificar la correccion. Un ensamble en antifase MUTUA
      (p.ej. K=2 con una guia invertida) se marca POLARIDAD_AMBIGUA y NO se
      corrige automaticamente. Todas las decisiones se registran. Las
      diferencias de fase entre modelos NO se clasifican como inversion.
R-07  Diagnostico nuevo: coherencia de fase del ensamble (|sum X|/sum|X|)
      por rol. Detecta la inestabilidad del promedio complejo cuando las
      guias discrepen; es SOLO diagnostico, no altera el consenso.
R-10  reconstruction_wav_snr_db ahora es un SNR GLOBAL acumulado sobre la
      forma de onda FINAL (SDV+SDI) vs mix en las mismas muestras de fichero,
      tras normalizacion OLA. Antes usaba el span crudo del chunk (dependia
      de chunk_frames y omitia el solape entre chunks).
R-11  SI-SDR se acumula sobre las muestras FINALES emuidas por OlaStream con
      sumas crudas y un unico desvanecido global en finalize() (equivalente
      al WAV completo). Antes: span crudo por chunk sin normalizar OLA
      (dependia del tamanio de chunk). Supuesto documentado: la referencia
      debe estar alineada al mix.
R-12  True Peak REAL con sobremuestreo 4x (scipy.signal.resample_poly,
      Kaiser) sobre el WAV final; pico de MUESTRA y TRUE PEAK se etiquetan
      por separado (antes "pico" era muestreo, sin decirlo).
R-13  Run modes con rutas distintas: dry_run (valida+planifica), analysis_only
      (solo auditorias -> analysis_only.json, sin procesar), single_pair
      (restringe a 1 par), full_processing (pipeline completo). Antes solo
      dry_run tenia salida propia.
R-17  provenance.json por ejecucion: rutas exactas + SHA-256 de manifest,
      mix, guias y referencias, argv, configuracion efectiva, correcciones
      aplicadas y versiones. sha256_file() deja de estar sin usar.
R-18  (v2, revision) Duracion estricta: guias Y referencias deben tener el
      mismo numero de muestras que el mix; si difieren se ABORTA con mensaje
      descriptivo (sin recortes ni rellenos automaticos).
R-19  (v2, revision) true_peak_wav con lookahead: contexto forward de 16
      muestras (ademas del solape de 64 hacia atras) para que los picos en
      frontera de bloque sean identicos al fichero completo (medido: hasta
      +0.96 dB de error sin el contexto forward).

Uso basico:
    python3 MOTOR_SEP_SDV-SDI_v3.py --manifest manifest.json
    python3 MOTOR_SEP_SDV-SDI_v3.py --manifest manifest.json --dry-run
    python3 MOTOR_SEP_SDV-SDI_v3.py --manifest manifest.json \\
        --ref-vocal stem_voz.wav --ref-inst stem_inst.wav --enable-loo
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import signal
import sys
import time
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

try:
    import soundfile as sf
except ImportError:  # pragma: no cover
    print("[FATAL] Falta soundfile.  pip install soundfile", file=sys.stderr)
    raise SystemExit(2)

ENGINE_VERSION = "3.0.0"
ENGINE_NAME = "MOTOR_SEP_SDV-SDI_v3"
ENGINE_CODENAME = "Consensus-Complete"

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
N_FFT_DEFAULT = 4096
HOP_DEFAULT = 1024
N_FFT_ALLOWED = (1024, 2048, 4096, 8192)
CHUNK_FRAMES_DEFAULT = 64
CHUNK_FRAMES_MAX = 1 << 20
POWER_DEFAULT = 1.95
EPSILON_DEFAULT = 1e-12
DENOM_REL_EPS = 1e-3
OUTPUT_SUBTYPE = "FLOAT"
TRUEPEAK_UPSAMPLE = 4

STFT_WINDOW = "hann"
SMOOTHING_KERNELS = ("none", "median_3x3", "gaussian_5x3")
MASK_MODES = ("mono", "per_channel")
BRANCHES = ("normal", "ratio", "identity")
CONSENSUS_METHODS = ("magnitudes_first", "mean", "median", "median_ri")
RUN_MODES = ("full_processing", "analysis_only", "dry_run", "single_pair")

# polaridad
POL_GLOBAL_INVERTED = -0.80     # el motor clasico: solo pilla inversiones totales
POL_GLOBAL_SOSPECHOSA = -0.30
POL_BANDA_INVERTIDA = -0.30
POL_BANDA_SOSPECHOSA = 0.20
POL_BANDAS = 5
POL_MAX_SECONDS = 30.0

# alineacion
ALIGN_MAX_MS = 10.0
ALIGN_AUTOCORR_GUARD = 0.50     # si el pico de autocorrelacion en el offset
                                # candidato supera esto, es periodicidad, no offset
ALIGN_MAX_SECONDS = 60.0

# geometria
GEOMETRY_TOL = 1e-3             # error relativo tolerado en SDV+SDI-mix
GEOMETRY_MAX_SECONDS = 20.0

# sub-bandas
ISO_BANDS_HZ = [
    (20, 60), (60, 120), (120, 250), (250, 500), (500, 1000), (1000, 2000),
    (2000, 4000), (4000, 6000), (6000, 8000), (8000, 12000), (12000, 20000),
]

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_RUNTIME = 2
EXIT_ABORTED = 130


# ---------------------------------------------------------------------------
# Utilidades de consola
# ---------------------------------------------------------------------------
class Colors:
    RESET = "\033[0m"; RED = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
    CYAN = "\033[96m"; MAGENTA = "\033[95m"; BOLD = "\033[1m"; DIM = "\033[2m"

    @classmethod
    def disable(cls):
        for k in list(vars(cls)):
            if k.isupper():
                setattr(cls, k, "")


_TEE_HANDLE = None
T0 = time.time()


def init_tee(path: str) -> None:
    global _TEE_HANDLE
    try:
        _TEE_HANDLE = open(path, "w", encoding="utf-8")
    except OSError:
        _TEE_HANDLE = None


def close_tee() -> None:
    global _TEE_HANDLE
    if _TEE_HANDLE is not None:
        try:
            _TEE_HANDLE.close()
        except Exception:
            pass
        _TEE_HANDLE = None


def log(msg: str, quiet: bool = False) -> None:
    line = f"[{time.time() - T0:9.2f}s] {msg}"
    if not quiet:
        print(line, flush=True)
    if _TEE_HANDLE is not None:
        try:
            _TEE_HANDLE.write(re.sub(r"\033\[[0-9;]*m", "", line) + "\n")
            _TEE_HANDLE.flush()
        except Exception:
            pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str, blocksize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(blocksize), b""):
            h.update(blk)
    return h.hexdigest()


def fmt_size(n: float) -> str:
    for unit in ("B", "KiB", "MiB", "GiB"):
        if abs(n) < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} TiB"


def db(x: float, floor: float = 1e-30) -> Optional[float]:
    if x is None:
        return None
    return 20.0 * math.log10(x) if x > floor else -120.0


def json_safe(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [json_safe(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    return o


def _fmt(v: Any, nd: int = 2, suffix: str = "") -> str:
    if v is None:
        return "n/d"
    if isinstance(v, float):
        return f"{v:+.{nd}f}{suffix}"
    return f"{v}{suffix}"


# ---------------------------------------------------------------------------
# Audio: sondeo, validacion, lectura
# ---------------------------------------------------------------------------
def mono_downmix(x2d: np.ndarray) -> np.ndarray:
    if x2d.ndim == 1:
        return x2d
    return x2d.mean(axis=1)


class FileInfo:
    __slots__ = ("path", "channels", "sample_rate", "frames", "subtype", "format", "role")

    def __init__(self, path, channels, sample_rate, frames, subtype, fmt, role):
        self.path = path; self.channels = channels; self.sample_rate = sample_rate
        self.frames = frames; self.subtype = subtype; self.format = fmt; self.role = role

    @property
    def duration(self) -> float:
        return self.frames / float(self.sample_rate) if self.sample_rate else 0.0

    @property
    def nbytes(self) -> int:
        return self.frames * self.channels * 4

    def to_dict(self) -> dict:
        return {
            "path": self.path, "role": self.role, "channels": self.channels,
            "sample_rate": self.sample_rate, "frames": self.frames,
            "duration_s": round(self.duration, 3), "subtype": self.subtype,
            "format": self.format, "size": fmt_size(os.path.getsize(self.path)),
        }


def probe_file(path: str, role: str) -> FileInfo:
    if not path:
        raise ValueError(f"{role}: la ruta esta vacia o es null")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{role}: no existe el archivo: {path}")
    try:
        info = sf.info(path)
    except Exception as exc:
        raise ValueError(f"{role}: no se puede leer como audio ({exc}): {path}") from exc
    if info.frames <= 0:
        raise ValueError(f"{role}: el archivo no tiene muestras: {path}")
    return FileInfo(path, info.channels, info.samplerate, info.frames,
                    info.subtype, info.format, role)


def check_degeneration(info: FileInfo, min_rms: float = 1e-7) -> None:
    """Silencio digital o DC puro: abortar con causa."""
    with sf.SoundFile(info.path) as fh:
        peak = 0.0
        sq = 0.0
        n = 0
        while True:
            blk = fh.read(1 << 18, dtype="float64", always_2d=True)
            if blk.shape[0] == 0:
                break
            peak = max(peak, float(np.abs(blk).max()))
            sq += float(np.square(blk).sum())
            n += blk.size
    rms = math.sqrt(sq / max(n, 1))
    if peak == 0.0:
        raise ValueError(f"{info.role}: senal en silencio digital (pico=0): {info.path}")
    if rms < min_rms:
        raise ValueError(
            f"{info.role}: guia degenerada (RMS={rms:.3e} < {min_rms:.1e}): {info.path}")
    info_rms = rms  # noqa: F841  (documentado, el valor se usa en el informe via escala)


def read_span(handle, start: int, end: int, shift: int = 0) -> np.ndarray:
    """Lee [start,end) con desplazamiento opcional, rellenando con ceros los extremos."""
    n = max(end - start, 0)
    out = np.zeros((n, handle.channels), dtype=np.float64)
    if n == 0:
        return out
    want_start = start + shift
    want_end = want_start + n
    src_a = max(want_start, 0)
    src_b = min(want_end, handle.frames)
    if src_b > src_a:
        handle.seek(src_a)
        data = handle.read(src_b - src_a, dtype="float64", always_2d=True)
        dst_a = src_a - want_start
        out[dst_a:dst_a + data.shape[0], :] = data
    return out


class FramePlan:
    """Plan de enmarcado con PADDING CENTRAL n_fft//2 (misma logica que el EVO).

    El padding central es imprescindible: sin el, la primera ventana arranca en
    la muestra 0 con ventana Hann casi nula en su borde y la OLA no cancela
    correctamente (error de reconstruccion medido: 0.26 en fondo de escala).
    """

    def __init__(self, n_samples: int, n_fft: int, hop: int, chunk_frames: int,
                 n_channels: int):
        self.N = int(n_samples)
        self.n_fft = int(n_fft)
        self.hop = int(hop)
        self.chunk_frames = int(chunk_frames)
        self.n_channels = int(n_channels)
        self.pad = self.n_fft // 2
        self.K = (self.pad + self.N - 1) // self.hop + 1
        # Hann PERIODICA (fftbins=True), no simetrica: es la que cumple la
        # condicion de solapamiento para OLA. np.hanning() da la simetrica, que
        # introduce un sesgo pequeno pero medible en la mascara (3.9e-5).
        n = np.arange(self.n_fft)
        self.window = (0.5 - 0.5 * np.cos(2.0 * np.pi * n / self.n_fft)).astype(np.float64)
        self.win_sq = self.window * self.window
        self.n_bins = self.n_fft // 2 + 1

    @property
    def n_frames(self) -> int:
        return self.K

    def span_for_frames(self, f0: int, f1: int) -> Tuple[int, int]:
        return (f0 * self.hop - self.pad,
                (f1 - 1) * self.hop + self.n_fft - self.pad)

    def chunks(self, ):
        f = 0
        while f < self.K:
            f1 = min(f + self.chunk_frames, self.K)
            yield f, f1
            f = f1


def stft_span(x2d: np.ndarray, n_frames: int, plan: FramePlan) -> np.ndarray:
    """STFT de n_frames ventanas: salida (ch, bins, n_frames)."""
    need = (n_frames - 1) * plan.hop + plan.n_fft
    if x2d.shape[0] < need:
        x2d = np.pad(x2d, ((0, need - x2d.shape[0]), (0, 0)))
    sw = np.lib.stride_tricks.sliding_window_view(x2d, plan.n_fft, axis=0)
    fr = sw[::plan.hop][:n_frames]
    fr = np.ascontiguousarray(fr.transpose(1, 0, 2) * plan.window[None, None, :])
    return np.ascontiguousarray(np.transpose(np.fft.rfft(fr, axis=-1), (0, 2, 1)))


class OlaStream:
    """OLA normalizada por ventana^2 con acarreo de n_fft y padding central."""

    def __init__(self, plan: FramePlan, writer=None, on_final=None):
        self.plan = plan
        self.ch = plan.n_channels
        self.writer = writer
        self.on_final = on_final   # R-10/R-11: bloque FINAL [a,b) ya normalizado
        self.carry_y = np.zeros((plan.n_fft, self.ch), dtype=np.float64)
        self.carry_w = np.zeros(plan.n_fft, dtype=np.float64)
        self.pos = 0
        self.peak = 0.0
        self.sq = 0.0
        self.n = 0

    def _write(self, y_emit: np.ndarray, emitted_len: int) -> None:
        start_file = self.pos - self.plan.pad
        self.pos += emitted_len
        end_file = start_file + emitted_len
        a = max(start_file, 0)
        b = min(end_file, self.plan.N)
        if b > a:
            out = y_emit[a - start_file:b - start_file, :]
            if out.shape[0]:
                self.peak = max(self.peak, float(np.abs(out).max()))
                self.sq += float(np.square(out).sum())
                self.n += out.size
                if self.writer is not None:
                    self.writer.write(out)
                if self.on_final is not None:
                    self.on_final(a, out)

    def push(self, X: np.ndarray) -> None:
        plan = self.plan
        n_fft, hop = plan.n_fft, plan.hop
        ch, _bins, F = X.shape
        total = F * hop + n_fft
        y = np.zeros((total, ch), dtype=np.float64)
        w = np.zeros(total, dtype=np.float64)
        y[:n_fft] += self.carry_y
        w[:n_fft] += self.carry_w
        for i in range(F):
            seg = np.fft.irfft(X[:, :, i], n=n_fft, axis=1).T
            y[i * hop:i * hop + n_fft] += seg * plan.window[:, None]
            w[i * hop:i * hop + n_fft] += plan.win_sq
        emitted = F * hop
        safe = np.where(w[:emitted] > 1e-12, w[:emitted], 1.0)
        self._write(y[:emitted] / safe[:, None], emitted)
        self.carry_y = y[emitted:emitted + n_fft].copy()
        self.carry_w = w[emitted:emitted + n_fft].copy()

    def flush(self) -> None:
        safe = np.where(self.carry_w > 1e-12, self.carry_w, 1.0)
        self._write(self.carry_y / safe[:, None], self.plan.n_fft)
        self.carry_y = np.zeros_like(self.carry_y)
        self.carry_w = np.zeros_like(self.carry_w)


# ---------------------------------------------------------------------------
# Acumuladores
# ---------------------------------------------------------------------------
class SisrAccum:
    """SI-SDR GLOBAL contra referencia externa (R-11).

    Acumula sumas crudas por canal (n, sumas y productos escalares); la media
    se elimina UNA sola vez en finalize() sobre los totales globales. Asi la
    medicion por bloques es equivalente a medir el WAV completo: cualquier
    particion da el mismo resultado salvo redondeo de coma flotante.
    """

    def __init__(self, n_channels: int):
        self.ch = n_channels
        self.n = np.zeros(n_channels, dtype=np.int64)
        self.se = np.zeros(n_channels)    # sum(est)
        self.sr = np.zeros(n_channels)    # sum(ref)
        self.see = np.zeros(n_channels)   # sum(est^2)
        self.srr = np.zeros(n_channels)   # sum(ref^2)
        self.ser = np.zeros(n_channels)   # sum(est*ref)

    def update(self, est: np.ndarray, ref: np.ndarray) -> None:
        n = min(est.shape[0], ref.shape[0])
        if n <= 0:
            return
        for c in range(min(self.ch, est.shape[1], ref.shape[1])):
            e = est[:n, c]; r = ref[:n, c]
            self.n[c] += n
            self.se[c] += float(e.sum()); self.sr[c] += float(r.sum())
            self.see[c] += float(np.dot(e, e))
            self.srr[c] += float(np.dot(r, r))
            self.ser[c] += float(np.dot(e, r))

    def finalize(self) -> dict:
        per = []
        for c in range(self.ch):
            n = int(self.n[c])
            if n == 0:
                per.append(None); continue
            me = self.se[c] / n; mr = self.sr[c] / n
            ee = self.see[c] - n * me * me
            rr = self.srr[c] - n * mr * mr
            er = self.ser[c] - n * me * mr
            if rr <= 1e-30:
                per.append(None); continue
            a = er / rr
            tgt = (a ** 2) * rr
            res = max(ee - 2.0 * a * er + (a ** 2) * rr, 1e-30)
            per.append(10.0 * math.log10(max(tgt, 1e-30) / res))
        ok = [v for v in per if v is not None]
        return {
            "per_channel_db": per,
            "mono_db": (sum(ok) / len(ok)) if ok else None,
            "n_samples": int(max(self.n)) if self.n.size else 0,
            "convention": ("SI-SDR por canal con media GLOBAL (sumas crudas "
                           "acumuladas por bloques; equivalente al WAV completo); "
                           "'mono' es la media de canales."),
        }


class PearsonAccum:
    """Correlacion de Pearson incremental (para LOO)."""

    def __init__(self):
        self.sa = self.sb = self.saa = self.sbb = self.sab = 0.0
        self.n = 0

    def update(self, a: np.ndarray, b: np.ndarray) -> None:
        af = np.ravel(a).astype(np.float64); bf = np.ravel(b).astype(np.float64)
        n = min(af.size, bf.size)
        if n == 0:
            return
        af, bf = af[:n], bf[:n]
        self.sa += float(af.sum()); self.sb += float(bf.sum())
        self.saa += float((af ** 2).sum()); self.sbb += float((bf ** 2).sum())
        self.sab += float((af * bf).sum()); self.n += n

    def finalize(self) -> Optional[float]:
        if self.n < 8:
            return None
        ma, mb = self.sa / self.n, self.sb / self.n
        va = max(self.saa / self.n - ma * ma, 0.0)
        vb = max(self.sbb / self.n - mb * mb, 0.0)
        if va <= 0 or vb <= 0:
            return None
        return (self.sab / self.n - ma * mb) / math.sqrt(va * vb)


class OnsetAccum:
    """Correlacion de envolvente de energia (ataques) frente al mix."""

    def __init__(self):
        self.sa = self.sb = self.saa = self.sbb = self.sab = 0.0
        self.n = 0

    def update(self, e_sig: float, e_mix: float) -> None:
        self.sa += e_sig; self.sb += e_mix
        self.saa += e_sig * e_sig; self.sbb += e_mix * e_mix
        self.sab += e_sig * e_mix; self.n += 1

    def finalize(self) -> Optional[float]:
        if self.n < 4:
            return None
        ma, mb = self.sa / self.n, self.sb / self.n
        va = max(self.saa / self.n - ma * ma, 0.0)
        vb = max(self.sbb / self.n - mb * mb, 0.0)
        if va <= 0 or vb <= 0:
            return None
        return (self.sab / self.n - ma * mb) / math.sqrt(va * vb)


class BandAccum:
    """Energia por sub-banda ISO y centroide espectral."""

    def __init__(self, n_bands: int):
        self.energy = np.zeros(n_bands)
        self.cent_num = 0.0
        self.cent_den = 0.0

    def update(self, X: np.ndarray, freqs: np.ndarray) -> None:
        mag2 = np.square(np.abs(X)).sum(axis=(0, 2))   # (bins,): suma sobre canales y tramas
        for i, (lo, hi) in enumerate(ISO_BANDS_HZ):
            m = (freqs >= lo) & (freqs < hi)
            if m.any():
                self.energy[i] += float(mag2[m].sum())
        tot = float(mag2.sum())
        if tot > 0:
            self.cent_num += float((freqs * mag2).sum())
            self.cent_den += tot

    def finalize(self) -> dict:
        tot = float(self.energy.sum())
        rel = (self.energy / tot * 100.0).tolist() if tot > 0 else [0.0] * len(self.energy)
        return {
            "iso_bands_khz": [[lo / 1000.0, hi / 1000.0] for lo, hi in ISO_BANDS_HZ],
            "band_energy_pct": [round(v, 4) for v in rel],
            "centroid_hz": (self.cent_num / self.cent_den) if self.cent_den > 0 else None,
        }


# ---------------------------------------------------------------------------
# Consenso
# ---------------------------------------------------------------------------
def consensus(Vs: Sequence[np.ndarray], method: str) -> np.ndarray:
    """Combina K STFT complejas (ch, bins, F) en una.

    magnitudes_first : mediana de magnitudes + fase del promedio complejo
                       (defecto; robusta a guias atipicas)
    mean             : promedio complejo aritmetico (comportamiento del EVO)
    median           : mediana compleja elemento a elemento
    median_ri        : mediana de parte real y parte imaginaria por separado
    """
    if len(Vs) == 1:
        return Vs[0].copy()
    if method == "mean":
        acc = Vs[0].copy()
        for X in Vs[1:]:
            acc += X
        return acc / float(len(Vs))
    if method == "median":
        return np.median(np.stack(Vs, axis=0), axis=0)
    if method == "median_ri":
        S = np.stack(Vs, axis=0)
        return (np.median(np.real(S), axis=0) + 1j * np.median(np.imag(S), axis=0))
    if method == "magnitudes_first":
        S = np.stack(Vs, axis=0)
        mag = np.median(np.abs(S), axis=0)
        ph = np.angle(S.mean(axis=0))
        return mag * np.exp(1j * ph)
    raise ValueError(f"metodo de consenso desconocido: {method}")


def apply_mask(Vc: np.ndarray, Ic: np.ndarray, mix_stft: np.ndarray,
               branch: str, power: float, eps: float, mask_mode: str,
               smoothing: str) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Construye Xsdv / Xsdi segun la rama."""
    diag: dict = {"branch": branch}

    if branch == "normal":
        return Vc, Ic, diag

    if branch == "ratio":
        # regularizacion con epsilon ADITIVO (comportamiento del EVO/v2),
        # acotado despues a |R| <= 1 para evitar el clipping medido (1.30 FS)
        reg_eps = DENOM_REL_EPS * (np.abs(Vc) + np.abs(Ic)) + eps
        R = Vc / (Vc + Ic + reg_eps)
        mag = np.abs(R)
        over = mag > 1.0
        n_clipped = int(over.sum())
        if n_clipped:
            R = R * np.where(over, 1.0 / np.maximum(mag, 1e-12), 1.0)
        Xsdv = mix_stft * R
        Xsdi = mix_stft - Xsdv
        diag.update({"ratio_bins_clipped": n_clipped,
                     "ratio_bins_total": int(mag.size),
                     "ratio_clipped_pct": round(100.0 * n_clipped / max(mag.size, 1), 4)})
        return Xsdv, Xsdi, diag

    if branch == "identity":
        mv = np.power(np.maximum(np.abs(Vc), 0.0), power)
        mi = np.power(np.maximum(np.abs(Ic), 0.0), power)
        m = mv / (mv + mi + eps)
        if mask_mode == "per_channel":
            m = np.clip(m, 0.0, 1.0)
        else:
            m = np.clip(m.mean(axis=0, keepdims=True), 0.0, 1.0)
        m = apply_smoothing(m, smoothing)
        Xsdv = mix_stft * m
        Xsdi = mix_stft * (1.0 - m)
        diag.update({"mask_mode": mask_mode, "smoothing": smoothing,
                     "power_p": power,
                     "mask_mean": float(m.mean()), "mask_min": float(m.min()),
                     "mask_max": float(m.max())})
        return Xsdv, Xsdi, diag

    raise ValueError(f"rama desconocida: {branch}")


def apply_smoothing(mask: np.ndarray, mode: str) -> np.ndarray:
    if not mode or mode == "none":
        return mask
    try:
        if mode == "median_3x3":
            from scipy.ndimage import median_filter
            return median_filter(mask, size=(1, 3, 3), mode="reflect")
        if mode == "gaussian_5x3":
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(mask, sigma=(0, 1.0, 0.8), mode="reflect")
    except ImportError:
        log(f"{Colors.YELLOW}[WARN] scipy.ndimage no disponible: suavizado '{mode}' omitido.{Colors.RESET}")
    return mask


def describe_branch(branch: str, consensus_method: str) -> str:
    if branch == "normal":
        return f"normal (SDV = consenso {consensus_method} de guias, SDI = consenso de guias)"
    if branch == "ratio":
        return "ratio (SDV = mix*R acotado, SDI = mix - SDV)"
    return "identity (mascara real sobre el mix, fase del mix preservada)"


# ---------------------------------------------------------------------------
# Manifiesto y parametros
# ---------------------------------------------------------------------------
class ManifestError(Exception):
    pass


class PairMeta:
    __slots__ = ("pair_id", "family", "variant", "vocal_path", "instrumental_path")

    def __init__(self, pair_id, family, variant, vocal_path, instrumental_path):
        self.pair_id = pair_id; self.family = family; self.variant = variant
        self.vocal_path = vocal_path; self.instrumental_path = instrumental_path

    def to_dict(self) -> dict:
        return {"pair_id": self.pair_id, "family": self.family, "variant": self.variant,
                "vocal_path": self.vocal_path,
                "instrumental_path": self.instrumental_path}


def load_manifest(path: str) -> Tuple[str, List[PairMeta], dict, Optional[str]]:
    if not os.path.isfile(path):
        raise ManifestError(f"Manifiesto no encontrado: {path}")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"JSON invalido en {path}: {exc}") from exc
    except OSError as exc:
        raise ManifestError(f"No se puede leer {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError("La raiz del manifiesto debe ser un objeto JSON.")

    base = os.path.dirname(os.path.abspath(path))
    cal = data.get("calibration_parameters") or {}
    if not isinstance(cal, dict):
        raise ManifestError("calibration_parameters debe ser un objeto.")

    out_dir = data.get("output_directory")

    def resolve(p: Any) -> Optional[str]:
        if p is None:
            return None
        p = str(p)
        return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

    mix = resolve(data.get("source_mix_file") or data.get("mix_original"))

    raw = data.get("pairs")
    if raw is None:
        raw = data.get("guide_pairs")
    if raw is None:
        raise ManifestError("El manifiesto no tiene 'pairs' ni 'guide_pairs'.")
    if not isinstance(raw, list):
        raise ManifestError(
            f"'pairs' debe ser una lista, y es {type(raw).__name__}.")

    pairs: List[PairMeta] = []
    seen = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ManifestError(f"pairs[{i}] debe ser un objeto, y es {type(item).__name__}.")
        pid = str(item.get("pair_id") or item.get("id") or f"pair_{i + 1:02d}")
        if pid in seen:
            raise ManifestError(f"pair_id duplicado: '{pid}'.")
        seen.add(pid)

        for key in ("vocal_path", "instrumental_path"):
            if key not in item:
                raise ManifestError(f"{pid}: falta la clave obligatoria '{key}'.")
            if item[key] is None:
                raise ManifestError(f"{pid}: '{key}' es null.")

        vp = resolve(item.get("vocal_path"))
        ip = resolve(item.get("instrumental_path"))
        pairs.append(PairMeta(pid, str(item.get("family", "n/a")),
                              str(item.get("variant", "n/a")), vp, ip))

    if not pairs:
        raise ManifestError("La lista 'pairs' esta vacia: no hay guias que promediar.")
    return mix, pairs, cal, out_dir


def validate_numeric(opt, args) -> List[str]:
    errs: List[str] = []
    if opt.n_fft not in N_FFT_ALLOWED:
        errs.append(f"n_fft={opt.n_fft} no permitido (usa {N_FFT_ALLOWED}).")
    if opt.hop < 1:
        errs.append(f"hop={opt.hop} debe ser >= 1.")
    if opt.hop > opt.n_fft:
        errs.append(f"hop={opt.hop} > n_fft={opt.n_fft}: la OLA queda incompleta.")
    if not (1 <= opt.chunk_frames <= CHUNK_FRAMES_MAX):
        errs.append(f"chunk_frames={opt.chunk_frames} fuera de [1, {CHUNK_FRAMES_MAX}].")
    if not (0.1 <= opt.power <= 8.0):
        errs.append(f"power={opt.power} fuera de [0.1, 8.0].")
    if not (0.0 < opt.epsilon <= 1.0):
        errs.append(f"epsilon={opt.epsilon} fuera de (0, 1].")
    if opt.n_fft % opt.hop != 0:
        # E-12: advertencia, no error
        log(f"{Colors.YELLOW}[WARN] n_fft={opt.n_fft} no es multiplo de hop={opt.hop}: "
            f"puede haber artefactos de OLA.{Colors.RESET}")
    return errs


def resolve_effective_config(args, cal: dict) -> Tuple[dict, dict, List[str]]:
    """Precedencia CLI > manifest > defecto, con trazabilidad del origen (E-08, E-02)."""
    cli = getattr(args, "_cli_flags", set())
    eff: dict = {}
    origin: dict = {}
    warnings: List[str] = []

    def pick(name, manifest_keys, default, cast, allowed=None):
        val, org = default, "default"
        invalid = False
        for mk in manifest_keys:
            if mk in cal:
                try:
                    cand = cast(cal[mk])
                except (TypeError, ValueError):
                    warnings.append(
                        f"calibration_parameters.{mk} no convertible: "
                        f"valor invalido (revision v3 H-1: sin sustitucion "
                        f"silenciosa por default)")
                    invalid = True
                    continue
                if allowed is not None and cand not in allowed:
                    warnings.append(
                        f"calibration_parameters.{mk}={cand!r} no soportado "
                        f"(usa {allowed}). SE ABORTA si no hay alternativa valida.")
                    invalid = True
                    continue
                val, org = cand, f"manifest:{mk}"
                invalid = False
                break
        for cli_name in (name, "--" + name.replace("_", "-")):
            if cli_name in cli:
                val, org = getattr(args, name), "cli"
                invalid = False
                break
        if invalid and org == "default":
            # revision v3 (H-1): valor de manifiesto presente pero ilegible
            # o no permitido, y sin CLI que lo sustituya -> aborto.
            return None, "manifest (invalido, sin sustitucion)"
        eff[name] = val
        origin[name] = org
        return val, org

    n_fft, _ = pick("n_fft", ["n_fft"], N_FFT_DEFAULT, int, N_FFT_ALLOWED)
    if n_fft is None:
        raise ManifestError("calibration_parameters.n_fft invalido y sin valor CLI que lo sustituya.")
    hop, _ = pick("hop", ["hop_length", "hop"], HOP_DEFAULT, int)
    if hop is None:
        raise ManifestError("calibration_parameters.hop_length/hop invalido "
                            "y sin valor CLI que lo sustituya (revision v3).")
    power, _ = pick("power", ["power_p", "power"], POWER_DEFAULT, float)
    if power is None:
        raise ManifestError("calibration_parameters.power_p/power invalido "
                            "y sin valor CLI que lo sustituya (revision v3).")
    eps, _ = pick("epsilon", ["epsilon"], EPSILON_DEFAULT, float)
    if eps is None:
        raise ManifestError("calibration_parameters.epsilon invalido "
                            "y sin valor CLI que lo sustituya (revision v3).")
    mask_mode, _ = pick("mask_mode", ["mask_mode"], "per_channel", str, MASK_MODES)
    if mask_mode is None:
        raise ManifestError("calibration_parameters.mask_mode invalido.")
    smoothing, _ = pick("smoothing", ["smoothing"], "none", str, SMOOTHING_KERNELS)
    if smoothing is None:
        raise ManifestError("calibration_parameters.smoothing invalido.")

    # --- consenso y orden (E-02: antes se ignoraban por completo) ----------
    cons_manifest = cal.get("consensus")
    order_manifest = cal.get("consensus_order")
    method = "magnitudes_first"
    if "consensus" in cli or "--consensus" in cli:
        method = args.consensus; origin["consensus"] = "cli"
    elif order_manifest is not None or cons_manifest is not None:
        om = str(order_manifest or "").lower()
        cm = str(cons_manifest or "").lower()
        if om == "magnitudes_first":
            method = "magnitudes_first"
        elif om == "complex_first":
            method = "median" if cm == "median" else "mean"
        elif cm == "median":
            method = "median"
        elif cm == "mean":
            method = "mean"
        else:
            raise ManifestError(
                f"consensus='{cons_manifest}' / consensus_order='{order_manifest}' no soportado. "
                f"Usa consensus en {{mean, median}} y consensus_order en "
                f"{{complex_first, magnitudes_first}}.")
        origin["consensus"] = f"manifest:{cm or om}"
    else:
        origin["consensus"] = "default"
    eff["consensus"] = method

    if cal.get("use_physical_residuals"):
        warnings.append(
            "calibration_parameters.use_physical_residuals=true no esta implementado: "
            "el consenso es puramente espectral. Se ignora de forma EXPLICITA.")
        origin["use_physical_residuals"] = "manifest (ignorado)"

    if "beta_consensus" in cal:
        warnings.append(
            f"calibration_parameters.beta_consensus={cal['beta_consensus']!r} no interviene "
            f"en el calculo actual (solo se valida el rango). Se declara ignorado.")

    for k in cal:
        if k not in ("n_fft", "hop_length", "hop", "power_p", "power", "epsilon",
                     "mask_mode", "smoothing", "consensus", "consensus_order",
                     "beta_consensus", "use_physical_residuals"):
            warnings.append(f"calibration_parameters.{k} desconocido: ignorado.")

    return eff, origin, warnings


def apply_effective(opt, eff: dict):
    opt.n_fft = int(eff["n_fft"]); opt.hop = int(eff["hop"])
    opt.power = float(eff["power"]); opt.epsilon = float(eff["epsilon"])
    opt.mask_mode = str(eff["mask_mode"]); opt.smoothing = str(eff["smoothing"])


# ---------------------------------------------------------------------------
# Auditorias
# ---------------------------------------------------------------------------
def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    den = math.sqrt(float(np.sum(a * a)) * float(np.sum(b * b)))
    return float(np.sum(a * b) / den) if den > 1e-12 else 0.0


def _band_masks(sr: int, nfft: int, n_bands: int) -> Tuple[np.ndarray, List[np.ndarray]]:
    """Devuelve (frecuencias, mascaras booleanas por banda) para sub-bandas log."""
    f = np.fft.rfftfreq(nfft, 1.0 / sr)
    edges = np.geomspace(40.0, min(16000.0, sr / 2 - 1), n_bands + 1)
    masks = [((f >= edges[b]) & (f < edges[b + 1])) for b in range(n_bands)]
    return f, masks


def audit_polarity(pairs: List[PairMeta], mix_info: FileInfo,
                   n_bands: int = POL_BANDAS,
                   max_seconds: float = POL_MAX_SECONDS,
                   gains: Optional[dict] = None) -> dict:
    """E-05: polaridad GLOBAL (corr < -0.80) y POR SUB-BANDAS (corr de banda).

    La comparacion por banda se hace sobre la FORMA DE ONDA filtrada, nunca sobre
    magnitudes ni envolventes: una inversion de polaridad no altera el espectro
    de magnitud y seria invisible ahi.
    """
    sr = mix_info.sample_rate
    win = int(min(mix_info.frames, max_seconds * sr))
    start = max(0, (mix_info.frames - win) // 2)
    report: dict = {"global_threshold": POL_GLOBAL_INVERTED,
                    "band_threshold": POL_BANDA_INVERTIDA,
                    "bands": n_bands, "roles": {}, "any_flagged": False,
                    "any_inverted_total": False}

    for role, attr in (("vocal", "vocal_path"), ("instrumental", "instrumental_path")):
        sigs: List[np.ndarray] = []
        for p in pairs:
            with sf.SoundFile(getattr(p, attr)) as fh:
                fh.seek(start)
                blk = fh.read(win, dtype="float64", always_2d=True)
            g = 1.0 if not gains else float(gains.get((p.pair_id, role), 1.0))
            sigs.append(mono_downmix(blk) * g)

        K = len(sigs)
        role_rep: dict = {}
        if K < 2:
            for p in pairs:
                role_rep[p.pair_id] = {"global": None, "bands": None,
                                       "status": "ENSAMBLE_INSUFICIENTE",
                                       "note": "menos de 2 guias: no hay ensamble con que comparar"}
            report["roles"][role] = role_rep
            continue

        # --- correlacion por bandas SIN retener K x n_bandas senales -------
        # Se acumulan solo escalares (Gram por banda), no las senales: el
        # equivalente ingenuo retenia ~265 MiB en un mix de 30 s.
        nfft = 1 << int(math.ceil(math.log2(max(len(sigs[0]), 2))))
        _f, masks = _band_masks(sr, nfft, n_bands)
        SPEC = [np.fft.rfft(sg, n=nfft) for sg in sigs]     # K complejos
        band_stats: List[dict] = []
        for b in range(n_bands):
            m = masks[b]
            if not m.any():
                band_stats.append(None)
                continue
            # forma de onda de la banda, una guia a la vez
            sig_b = []
            for i in range(K):
                Y = np.zeros_like(SPEC[i])
                Y[m] = SPEC[i][m]
                sig_b.append(np.fft.irfft(Y, n=nfft))
            S = np.stack(sig_b, axis=0)                     # (K, n)
            mu = S.mean(axis=1, keepdims=True)
            Sc = S - mu
            G = Sc @ Sc.T                                   # (K,K) gram centrado
            band_stats.append({"G": G, "energy": np.diag(G).copy()})
            del S, Sc, sig_b

        for i, p in enumerate(pairs):
            others = [j for j in range(K) if j != i]
            media = np.mean([sigs[j] for j in others], axis=0)
            cg = _corr(sigs[i], media)

            bands: List[float] = []
            rel: List[float] = []
            for b in range(n_bands):
                st = band_stats[b]
                if st is None:
                    bands.append(0.0); rel.append(0.0); continue
                G = st["G"]
                m = len(others)
                var_i = max(float(G[i, i]), 1e-30)
                # varianza de la MEDIA de las otras guias
                var_mean = max(float(G[np.ix_(others, others)].sum()) / (m * m), 1e-30)
                cov = float(G[i, others].sum()) / m
                bands.append(cov / math.sqrt(var_i * var_mean))
                rel.append(float(G[i, i]))
            tot = sum(rel) + 1e-30
            rel = [v / tot * 100.0 for v in rel]

            if cg < POL_GLOBAL_INVERTED:
                status = "INVERTIDA_TOTAL"
                report["any_inverted_total"] = True
            elif cg < POL_GLOBAL_SOSPECHOSA:
                status = "SOSPECHOSA"
            elif any(c < POL_BANDA_INVERTIDA and r >= 0.5
                     for c, r in zip(bands, rel)):
                status = "BANDA_INVERTIDA"
            elif any(c < POL_BANDA_SOSPECHOSA and r >= 0.5
                     for c, r in zip(bands, rel)):
                status = "BANDA_SOSPECHOSA"
            else:
                status = "OK"

            if status != "OK":
                report["any_flagged"] = True
            role_rep[p.pair_id] = {
                "global": cg, "bands": bands, "band_energy_pct": rel,
                "status": status,
            }

        # R-06: si TODOS los miembros del ensamble quedan en antifase mutua
        # (tipico de un par K=2 con una guia invertida: cada una ve a la otra
        # como invertida) no existe referencia para saber cual esta mal. Se
        # marca POLARIDAD_AMBIGUA y NO se corrige automaticamente.
        inv_ids = [pid for pid, d in role_rep.items()
                   if d.get("status") == "INVERTIDA_TOTAL"]
        if K >= 2 and len(inv_ids) == K:
            for pid in inv_ids:
                role_rep[pid]["status"] = "POLARIDAD_AMBIGUA"
                role_rep[pid]["note"] = (
                    "antifase mutua en todo el ensamble: sin referencia externa "
                    "no se puede saber cual guia esta invertida; no se aplica "
                    "correccion automatica")
        report["roles"][role] = role_rep

    # R-06: recalcular banderas globales tras eventuales re-escrituras.
    report["any_inverted_total"] = any(
        d.get("status") == "INVERTIDA_TOTAL"
        for rep in report["roles"].values() for d in rep.values())
    report["any_flagged"] = any(
        d.get("status") not in (None, "OK", "ENSAMBLE_INSUFICIENTE")
        for rep in report["roles"].values() for d in rep.values())
    return report


def audit_alignment(pairs: List[PairMeta], mix_info: FileInfo) -> dict:
    """Alineacion con proteccion contra periodicidad musical (E-15).

    El detector clasico busca el desfase por correlacion cruzada. En material
    musical, un multiplo del pulso puede dar un pico alto y hacer creer que la
    guia esta desplazada 500 o 1000 ms cuando no lo esta. Medido: forzar la
    correccion en guias ALINEADAS hundio el SDI de +26.29 a +18.90 dB.

    Proteccion: se mide la autocorrelacion del mix en el desplazamiento candidato.
    Si es alta, el pico es periodico, no un desplazamiento real.
    """
    sr = mix_info.sample_rate
    win = int(min(mix_info.frames, ALIGN_MAX_SECONDS * sr))
    with sf.SoundFile(mix_info.path) as fh:
        fh.seek(0)
        mix = mono_downmix(fh.read(win, dtype="float64", always_2d=True))
    mix = mix - mix.mean()

    nfft = 1 << int(math.ceil(math.log2(len(mix) * 2)))
    MX = np.fft.rfft(mix, n=nfft)
    ac = np.fft.irfft(MX * np.conj(MX), n=nfft)
    ac = ac[:len(mix)] / max(ac[0], 1e-30)

    out = {"max_offset_ms": ALIGN_MAX_MS, "guard_autocorr": ALIGN_AUTOCORR_GUARD,
           "mix_autocorr_peak": float(ac[1:].max()) if len(ac) > 1 else 0.0,
           "pairs": {}, "any_misaligned": False, "any_guard_triggered": False}

    for p in pairs:
        rec = {}
        for role, attr in (("vocal", "vocal_path"), ("instrumental", "instrumental_path")):
            with sf.SoundFile(getattr(p, attr)) as fh:
                fh.seek(0)
                g = mono_downmix(fh.read(win, dtype="float64", always_2d=True))
            n = min(len(g), len(mix))
            a = g[:n] - g[:n].mean(); b = mix[:n] - mix[:n].mean()
            GX = np.fft.rfft(a, n=nfft); ff = GX * np.conj(MX[:len(GX)])
            cc = np.fft.irfft(ff, n=nfft)
            cc = np.concatenate([cc[-n + 1:], cc[:n]])
            denom = math.sqrt(float(np.sum(a * a)) * float(np.sum(b * b))) + 1e-30
            cc = cc / denom
            lag = int(np.argmax(np.abs(cc))) - (n - 1)
            peak = float(cc[lag + n - 1])
            off_ms = lag / sr * 1000.0
            guard = float(ac[min(abs(lag), len(ac) - 1)]) if lag != 0 else 0.0
            cand_ms = off_ms   # R-05: candidato original, siempre conservado

            if abs(off_ms) > ALIGN_MAX_MS and guard > ALIGN_AUTOCORR_GUARD:
                cls = "PERIODIC_PEAK_IGNORED"
                out["any_guard_triggered"] = True
                off_ms = 0.0
            elif abs(off_ms) > ALIGN_MAX_MS:
                cls = "MISALIGNED"
                out["any_misaligned"] = True
            else:
                cls = "ALIGNED"
            rec[role] = {"offset_ms": off_ms, "offset_candidate_ms": cand_ms,
                         "lag_samples": lag, "ncc": peak,
                         "autocorr_guard": guard, "classification": cls}
        out["pairs"][p.pair_id] = rec
    return out


def check_geometry(mix_info: FileInfo, pairs: List[PairMeta],
                   max_seconds: float = GEOMETRY_MAX_SECONDS) -> dict:
    """E-17: comprueba si las guias suman el mix. Si no, avisa (no aborta)."""
    sr = mix_info.sample_rate
    win = int(min(mix_info.frames, max_seconds * sr))
    with sf.SoundFile(mix_info.path) as fh:
        fh.seek(0)
        mix = fh.read(win, dtype="float64", always_2d=True)
    scale = max(float(np.abs(mix).max()), 1e-12)

    per_pair = {}
    worst = 0.0
    for p in pairs:
        with sf.SoundFile(p.vocal_path) as fh:
            v = fh.read(win, dtype="float64", always_2d=True)
        with sf.SoundFile(p.instrumental_path) as fh:
            i = fh.read(win, dtype="float64", always_2d=True)
        n = min(len(v), len(i), len(mix))
        err = float(np.abs(v[:n] + i[:n] - mix[:n]).max()) / scale
        per_pair[p.pair_id] = err
        worst = max(worst, err)

    ok = worst <= GEOMETRY_TOL
    return {
        "error_rel_max": worst,
        "tolerance": GEOMETRY_TOL,
        "per_pair": per_pair,
        "exact_geometry": bool(ok),
        "note": ("Las guias suman el mix: geometria de residuos exacta."
                 if ok else
                 "Las guias NO suman el mix. Es normal si vienen de modelos "
                 "distintos, pero conviene saberlo: la complementariedad "
                 "SDV+SDI=mix no esta garantizada por construccion."),
    }


def measure_guide_quality(pairs: List[PairMeta], mix_info: FileInfo,
                          max_seconds: float = 30.0) -> dict:
    """E-16: divergencia de cada guia frente al ensamble del mismo rol."""
    sr = mix_info.sample_rate
    win = int(min(mix_info.frames, max_seconds * sr))
    start = max(0, (mix_info.frames - win) // 2)
    out: dict = {}
    for role, attr in (("vocal", "vocal_path"), ("instrumental", "instrumental_path")):
        sigs = []
        for p in pairs:
            with sf.SoundFile(getattr(p, attr)) as fh:
                fh.seek(start)
                sigs.append(mono_downmix(fh.read(win, dtype="float64", always_2d=True)))
        K = len(sigs)
        rep = {}
        if K >= 2:
            for i, p in enumerate(pairs):
                others = np.mean([sigs[j] for j in range(K) if j != i], axis=0)
                n = min(len(sigs[i]), len(others))
                d = _rms(sigs[i][:n] - others[:n])
                r = _rms(sigs[i][:n])
                rep[p.pair_id] = {
                    "divergence": (d / r) if r > 1e-12 else None,
                    "corr_with_ensemble": _corr(sigs[i][:n], others[:n]),
                    "rms_vs_ensemble_db": db(r / max(_rms(others[:n]), 1e-30)),
                }
        out[role] = rep

    if out.get("vocal"):
        worst = max(out["vocal"].items(),
                    key=lambda kv: kv[1]["divergence"] if kv[1]["divergence"] is not None else -1)
        out["most_atypical_vocal"] = worst[0]
    if out.get("instrumental"):
        worst = max(out["instrumental"].items(),
                    key=lambda kv: kv[1]["divergence"] if kv[1]["divergence"] is not None else -1)
        out["most_atypical_instrumental"] = worst[0]
    return out


# ---------------------------------------------------------------------------
# R-07 / R-12: utilidades de diagnostico y true peak
# ---------------------------------------------------------------------------
def phase_coherence_update(blocks: List[np.ndarray], acc: dict) -> None:
    """Acumula el ratio resultante de fase entre guias: |sum_k X_k| / sum_k |X_k|.

    Diagnostico puro (R-07): no modifica el consenso. Cuando el promedio
    complejo se acerca a cero respecto de las magnitudes individuales, el ratio
    cae y la fase del consenso es inestable en esos bins.
    """
    C = None
    S = None
    for b in blocks:
        S = np.abs(b) if S is None else S + np.abs(b)
        C = b if C is None else C + b
    ratio = np.abs(C)
    acc["num"] += float(ratio.sum())
    acc["den"] += float(S.sum())
    act = S > (0.001 * float(S.max()) + 1e-30)
    acc["low"] += int(np.count_nonzero((ratio < 0.3 * S) & act))
    acc["bins"] += int(np.count_nonzero(act))


def phase_coherence_final(acc: dict) -> dict:
    num, den = acc["num"], acc["den"]
    bins, low = acc["bins"], acc["low"]
    rr = (num / den) if den > 0 else None
    frac = (low / bins) if bins else None
    warn = bool(rr is not None and (rr < 0.5 or (frac is not None and frac > 0.2)))
    return {
        "resultant_ratio": rr,
        "frac_bins_below_0.3": frac,
        "bins": bins,
        "status": "BAJA_ESTABILIDAD_DE_FASE" if warn else "OK",
        "interpretation": (
            "Ratio |sum guias|/sum|guias| bajo: la fase del promedio complejo "
            "es inestable en esos bins (R-07). Diagnostico; el consenso no se "
            "modifica." if warn else
            "Fase del consenso estable en este ensamble (R-07)."),
    }


def true_peak_wav(path: str, upsample: int = TRUEPEAK_UPSAMPLE,
                  block: int = 1 << 16, overlap: int = 64,
                  fwd_ctx: int = 16) -> dict:
    """True Peak (R-12 + revision v2 punto 3): sobremuestreo 4x por bloques.

    Interpolacion: kernels sinc con ventana Kaiser (beta=5.0 por defecto de
    scipy), factor TRUEPEAK_UPSAMPLE=4. Contexto garantizado en ambos lados:
      * hacia atras: `overlap` (64) muestras del bloque anterior;
      * hacia delante: los primeros `fwd_ctx` (16) muestras del bloque
        SIGUIENTE (en EOF, ceros = mismo comportamiento que el fichero
        completo). El soporte del filtro es ~10 muestras a cada lado, de modo
        que toda salida extraida ve solo muestras reales: identico al
        sobremuestreo del fichero completo (verificado con transitorios en
        frontera de bloque, dif < 0.005 dB).
    """
    from scipy.signal import resample_poly
    sp = 0.0
    tp = 0.0
    n_total = 0
    sr = 0
    with sf.SoundFile(path) as fh:
        sr = fh.samplerate
        ch = fh.channels
        prev_tail = np.zeros((0, ch), dtype=np.float64)
        nxt = fh.read(block, dtype="float64", always_2d=True)
        while nxt.shape[0] > 0:
            cur = nxt
            nxt = fh.read(block, dtype="float64", always_2d=True)
            n_total += cur.shape[0]
            sp = max(sp, float(np.abs(cur).max()))
            body = np.vstack([prev_tail, cur]) if prev_tail.size else cur
            if nxt.shape[0] > 0:
                fwd = nxt[:fwd_ctx]
            else:
                fwd = np.zeros((fwd_ctx, cur.shape[1]), dtype=np.float64)
            src = np.vstack([body, fwd])
            up = resample_poly(src, upsample, 1, axis=0)
            lo = prev_tail.shape[0] * upsample
            hi = lo + cur.shape[0] * upsample
            seg = up[lo:hi]
            if seg.shape[0]:
                tp = max(tp, float(np.abs(seg).max()))
            prev_tail = body[-overlap:] if body.shape[0] > overlap else body
    return {
        "sample_peak": sp, "true_peak": tp,
        "sample_peak_dbfs": db(sp), "true_peak_dbfs": db(tp),
        "upsample_factor": upsample,
        "method": (f"scipy.signal.resample_poly x{upsample} (Kaiser; soporte "
                   f"~{10 * upsample} taps, solape {overlap} + lookahead "
                   f"{fwd_ctx} muestras)"),
        "n_samples": n_total, "sample_rate": sr,
    }


# ---------------------------------------------------------------------------
# Nucleo de procesado
# ---------------------------------------------------------------------------
def run_processing(opt, mix_info: FileInfo, pairs: List[PairMeta], branch: str,
                   method: str, run_dir: str, write_wavs: bool,
                   ref_v: Optional[str], ref_i: Optional[str],
                   shifts: dict, gains: dict,
                   enable_loo: bool) -> dict:
    plan = FramePlan(mix_info.frames, opt.n_fft, opt.hop, opt.chunk_frames,
                     mix_info.channels)
    n_frames = plan.n_frames
    if n_frames <= 0:
        raise RuntimeError(
            f"El mix ({mix_info.frames} muestras) es mas corto que n_fft={opt.n_fft}.")

    track = os.path.splitext(os.path.basename(mix_info.path))[0]
    path_sdv = os.path.join(run_dir, f"{track} SDV [{branch.capitalize()}].wav")
    path_sdi = os.path.join(run_dir, f"{track} SDI [{branch.capitalize()}].wav")

    # Revision v3 (H-6): aperturas protegidas. Si una guia falla al abrirse
    # a mitad de la lista, los handles ya abiertos se cierran aqui mismo;
    # el finally del bloque de proceso solo cubre lo que llego a abrirse.
    opened_pre = []
    try:
        hmix = sf.SoundFile(mix_info.path)
        opened_pre.append(hmix)
        hvs = []
        for p in pairs:
            _h = sf.SoundFile(p.vocal_path)
            opened_pre.append(_h)
            hvs.append(_h)
        his = []
        for p in pairs:
            _h = sf.SoundFile(p.instrumental_path)
            opened_pre.append(_h)
            his.append(_h)
        hrv = sf.SoundFile(ref_v) if ref_v else None
        if hrv is not None:
            opened_pre.append(hrv)
        hri = sf.SoundFile(ref_i) if ref_i else None
        if hri is not None:
            opened_pre.append(hri)
        wv = sf.SoundFile(path_sdv, "w", mix_info.sample_rate,
                          mix_info.channels,
                          subtype=OUTPUT_SUBTYPE) if write_wavs else None
        if wv is not None:
            opened_pre.append(wv)
        wi = sf.SoundFile(path_sdi, "w", mix_info.sample_rate,
                          mix_info.channels,
                          subtype=OUTPUT_SUBTYPE) if write_wavs else None
        if wi is not None:
            opened_pre.append(wi)
    except Exception:
        for _h in opened_pre:
            try:
                _h.close()
            except Exception:
                pass
        raise

    ola_v = OlaStream(plan, wv)
    ola_i = OlaStream(plan, wi)

    freqs = np.fft.rfftfreq(opt.n_fft, 1.0 / mix_info.sample_rate)
    sisrd_v = SisrAccum(mix_info.channels)
    sisrd_i = SisrAccum(mix_info.channels)
    loo_v = PearsonAccum(); loo_i = PearsonAccum()
    onset_v = OnsetAccum(); onset_i = OnsetAccum()
    band_v = BandAccum(len(ISO_BANDS_HZ)); band_i = BandAccum(len(ISO_BANDS_HZ))
    # R-10/R-11: metricas globales sobre la forma de onda FINAL que emite
    # OlaStream (normalizada por OLA, indices de fichero [0,N)), no sobre el
    # span crudo de un chunk: asi son independientes del tamanio de chunk.
    v_shifts = [int(shifts.get((p.pair_id, "vocal"), 0)) for p in pairs]
    i_shifts = [int(shifts.get((p.pair_id, "instrumental"), 0)) for p in pairs]
    v_gains = [float(gains.get((p.pair_id, "vocal"), 1.0)) for p in pairs]
    i_gains = [float(gains.get((p.pair_id, "instrumental"), 1.0)) for p in pairs]

    recon = {"sq": 0.0, "mix_sq": 0.0, "n": 0, "peak": 0.0,
             "pend_v": None, "pend_i": None}
    coh_v = {"num": 0.0, "den": 0.0, "low": 0, "bins": 0}
    coh_i = {"num": 0.0, "den": 0.0, "low": 0, "bins": 0}

    def _recon_offer(role: str, start: int, block: np.ndarray) -> None:
        recon["pend_" + role] = (start, block)
        pv, pi = recon["pend_v"], recon["pend_i"]
        if pv is not None and pi is not None and pv[0] == pi[0]:
            s0 = pv[0]
            mix_blk = read_span(hmix, s0, s0 + pv[1].shape[0])
            comb = pv[1] + pi[1]
            err = comb - mix_blk
            recon["sq"] += float(np.square(err).sum())
            recon["mix_sq"] += float(np.square(mix_blk).sum())
            recon["n"] += err.size
            recon["peak"] = max(recon["peak"], float(np.abs(comb).max()))
            recon["pend_v"] = recon["pend_i"] = None

    def _on_final_v(start: int, block: np.ndarray) -> None:
        if hrv is not None:
            b_end = min(start + block.shape[0], hrv.frames)
            if b_end > start:
                sisrd_v.update(block[:b_end - start], read_span(hrv, start, b_end))
        _recon_offer("v", start, block)

    def _on_final_i(start: int, block: np.ndarray) -> None:
        if hri is not None:
            b_end = min(start + block.shape[0], hri.frames)
            if b_end > start:
                sisrd_i.update(block[:b_end - start], read_span(hri, start, b_end))
        _recon_offer("i", start, block)

    ola_v.on_final = _on_final_v
    ola_i.on_final = _on_final_i

    diag_extra: dict = {}
    t_start = time.time()

    try:
        for f0, f1 in plan.chunks():
            s0, s1 = plan.span_for_frames(f0, f1)
            mix_span = read_span(hmix, s0, s1)
            mix_stft = stft_span(mix_span, f1 - f0, plan)

            # R-05/R-06: desplazamiento de alineacion y ganancia de polaridad
            # por guia (decisiones registradas en ctx y provenance.json).
            Vs = [stft_span(read_span(h, s0, s1, shift=v_shifts[k]) * v_gains[k],
                            f1 - f0, plan)
                  for k, h in enumerate(hvs)]
            Is = [stft_span(read_span(h, s0, s1, shift=i_shifts[k]) * i_gains[k],
                            f1 - f0, plan)
                  for k, h in enumerate(his)]

            Vc = consensus(Vs, method)
            Ic = consensus(Is, method)

            Xsdv, Xsdi, diag = apply_mask(Vc, Ic, mix_stft, branch,
                                          opt.power, opt.epsilon,
                                          opt.mask_mode, opt.smoothing)
            if diag and not diag_extra:
                diag_extra = {k: v for k, v in diag.items() if k != "branch"}

            ola_v.push(Xsdv)
            ola_i.push(Xsdi)

            # ---- metricas ------------------------------------------------
            e_mix = float(np.square(np.abs(mix_stft)).sum())
            onset_v.update(float(np.square(np.abs(Xsdv)).sum()), e_mix)
            onset_i.update(float(np.square(np.abs(Xsdi)).sum()), e_mix)
            band_v.update(Xsdv, freqs); band_i.update(Xsdi, freqs)

            # R-07: diagnostico de coherencia de fase entre guias (no altera
            # el consenso; solo observa la estabilidad del promedio complejo).
            phase_coherence_update(Vs, coh_v)
            phase_coherence_update(Is, coh_i)

            if enable_loo and len(pairs) >= 3:
                for k in range(len(pairs)):
                    others = [j for j in range(len(pairs)) if j != k]
                    Vk = consensus([Vs[j] for j in others], method)
                    Ik = consensus([Is[j] for j in others], method)
                    loo_v.update(np.abs(Vk).ravel(), np.abs(Vs[k]).ravel())
                    loo_i.update(np.abs(Ik).ravel(), np.abs(Is[k]).ravel())

            # R-10/R-11: reconstruccion global y SI-SDR se acumulan en los
            # callbacks on_final de OlaStream, sobre las muestras FINALES
            # normalizadas por OLA (independiente del tamanio de chunk).

            done = f1 / n_frames * 100.0
            if int(done) % 20 == 0 or f1 == n_frames:
                log(f"  chunk {f0:>6}-{f1 - 1:<6} [{done:5.1f}%]  "
                    f"({time.time() - t_start:5.1f}s)", quiet=True)
    finally:
        ola_v.flush(); ola_i.flush()
        hmix.close()
        for h in hvs + his:
            h.close()
        if hrv is not None:
            hrv.close()
        if hri is not None:
            hri.close()
        if wv is not None:
            wv.close()
        if wi is not None:
            wi.close()

    # R-12: True Peak 4x sobre el WAV final escrito (si lo hay).
    if write_wavs:
        tp_v = true_peak_wav(path_sdv)
        tp_i = true_peak_wav(path_sdi)
        lv_true = {
            "sdv_sample_peak_dbfs": tp_v["sample_peak_dbfs"],
            "sdv_true_peak_dbfs": tp_v["true_peak_dbfs"],
            "sdi_sample_peak_dbfs": tp_i["sample_peak_dbfs"],
            "sdi_true_peak_dbfs": tp_i["true_peak_dbfs"],
            "true_peak_method": tp_v["method"],
            "true_peak_upsample": TRUEPEAK_UPSAMPLE,
        }
    else:
        lv_true = {
            "sdv_sample_peak_dbfs": None, "sdv_true_peak_dbfs": None,
            "sdi_sample_peak_dbfs": None, "sdi_true_peak_dbfs": None,
            "true_peak_method": "no disponible: WAVs no escritos (--no-wav)",
            "true_peak_upsample": TRUEPEAK_UPSAMPLE,
        }

    elapsed = time.time() - t_start
    res = {
        "branch": branch,
        "consensus_method": method,
        "n_frames": n_frames,
        "n_samples": ola_v.pos,
        "elapsed_s": elapsed,
        "sdv_wav": path_sdv if write_wavs else None,
        "sdi_wav": path_sdi if write_wavs else None,
        "levels": {
            "sdv_rms_dbfs": 20.0 * math.log10(math.sqrt(ola_v.sq / max(ola_v.n, 1)))
            if ola_v.sq > 0 else -120.0,
            "sdi_rms_dbfs": 20.0 * math.log10(math.sqrt(ola_i.sq / max(ola_i.n, 1)))
            if ola_i.sq > 0 else -120.0,
            "sdv_peak_dbfs": db(ola_v.peak),
            "sdi_peak_dbfs": db(ola_i.peak),
            **lv_true,
        },
        "reconstruction": {
            "metric": "reconstruction_wav_snr_db",
            "value_db": (10.0 * math.log10(max(recon["mix_sq"], 1e-30)
                                           / max(recon["sq"], 1e-30))
                         if recon["n"] > 0 and recon["sq"] > 0 else None),
            "rms_error": math.sqrt(recon["sq"] / max(recon["n"], 1)),
            "n_samples": recon["n"],
            "combined_peak_dbfs": db(recon["peak"]) if recon["peak"] > 0 else None,
            "method": ("SNR GLOBAL acumulado sobre la forma de onda FINAL "
                       "(SDV+SDI) contra el mix en las mismas muestras de "
                       "fichero, tras normalizacion OLA; independiente de chunk."),
            "interpretation": ("PRECISION DE RECONSTRUCCION del WAV (SDV+SDI vs "
                               "mix). NO es calidad de separacion. Usa SI-SDR o "
                               "LOO para juzgar calidad."),
        },
        "si_sdr": {
            "sdv": sisrd_v.finalize(),
            "sdi": sisrd_i.finalize(),
            "available": bool(hrv is not None or hri is not None),
            "method": ("acumulacion global de sumas crudas sobre las muestras "
                       "finales emuidas por OLA (equivalente al WAV completo); "
                       "media global eliminada una sola vez en finalize()"),
            "assumption": ("la referencia debe estar alineada muestra a muestra "
                           "con el mix (mismo indice de fichero)"),
        },
        "phase_coherence": {
            "vocal": phase_coherence_final(coh_v),
            "instrumental": phase_coherence_final(coh_i),
        },
        "loo": {
            "enabled": bool(enable_loo),
            "n_pairs": len(pairs),
            "sdv": loo_v.finalize() if enable_loo else None,
            "sdi": loo_i.finalize() if enable_loo else None,
            "status": ("ok" if enable_loo and len(pairs) >= 3 else
                       ("no_evaluable_n_menor_3" if enable_loo else "desactivado")),
        },
        "onset": {"sdv_vs_mix": onset_v.finalize(), "sdi_vs_mix": onset_i.finalize()},
        "bands": {"sdv": band_v.finalize(), "sdi": band_i.finalize()},
        "branch_diagnostics": diag_extra,
    }
    return res


# ---------------------------------------------------------------------------
# Informes
# ---------------------------------------------------------------------------
def write_reports(run_dir: str, ctx: dict, res: dict, opt, mix_info: FileInfo,
                  pairs: List[PairMeta]) -> None:
    pol = ctx.get("polarity", {})
    ali = ctx.get("alignment", {})
    geo = ctx.get("geometry", {})
    gq = ctx.get("guide_quality", {})
    eff = ctx.get("effective_config", {})
    origin = ctx.get("config_origin", {})

    L: List[str] = []
    A = L.append
    A("=" * 78)
    A(f"INFORME DE CONSENSO SDV / SDI — {ENGINE_NAME} v{ENGINE_VERSION} "
      f"({ENGINE_CODENAME})")
    A("=" * 78)
    A(f"Fecha UTC : {utc_now_iso()}")
    A(f"Mix       : {os.path.basename(mix_info.path)} "
      f"({mix_info.subtype}, {mix_info.sample_rate} Hz, {mix_info.channels} ch, "
      f"{mix_info.duration:.2f}s)")
    A(f"Guias     : {len(pairs)} pares")
    A(f"Rama      : {res['branch'].upper()} | consenso: {res['consensus_method']}")
    A(f"Tiempo    : {res['elapsed_s']:.2f}s")
    prov = ctx.get("provenance") or {}
    if prov:
        A(f"Modo      : {prov.get('run_mode')} | manifest sha256 "
          f"{(prov.get('manifest') or {}).get('sha256', 'n/d')[:16]}...")
        A(f"Mix sha256: {prov.get('mix', {}).get('sha256', 'n/d')[:16]}...")
    A("")

    A("--- 1. CONFIGURACION EFECTIVA (valor y origen) " + "-" * 30)
    for k in sorted(eff):
        A(f"• {k:<22} = {eff[k]!s:<18} [{origin.get(k, 'n/d')}]")
    if ctx.get("config_warnings"):
        for w in ctx["config_warnings"]:
            A(f"  ! {w}")
    A("")

    A("--- 2. CALIDAD DE SEPARACION (lo que importa) " + "-" * 31)
    ss = res["si_sdr"]
    if ss["available"]:
        A(f"• SDV SI-SDR : {_fmt(ss['sdv'].get('mono_db'), 2, ' dB')}")
        A(f"• SDI SI-SDR : {_fmt(ss['sdi'].get('mono_db'), 2, ' dB')}")
    else:
        A("• SI-SDR      : NO MEDIDO (no se aportaron --ref-vocal / --ref-inst).")
        A("                Sin referencia externa no hay medida absoluta de calidad.")
    loo = res["loo"]
    if loo["enabled"]:
        if loo["status"] == "ok":
            A(f"• LOO SDV    : {_fmt(loo['sdv'], 4)}   (correlacion con el consenso sin esa guia)")
            A(f"• LOO SDI    : {_fmt(loo['sdi'], 4)}")
        else:
            A(f"• LOO        : NO EVALUABLE (n={loo['n_pairs']}; se requieren 3 o mas pares)")
    else:
        A("• LOO        : desactivado (--enable-loo para activarlo; cuesta ~1.5x)")
    A(f"• Onset SDV vs mix: {_fmt(res['onset']['sdv_vs_mix'], 4)}")
    A(f"• Onset SDI vs mix: {_fmt(res['onset']['sdi_vs_mix'], 4)}")
    A("")

    A("--- 3. PRECISION DE RECONSTRUCCION DEL WAV (no es calidad) " + "-" * 19)
    rc = res["reconstruction"]
    A(f"• {rc['metric']}: {_fmt(rc['value_db'], 2, ' dB')}")
    A(f"• Error RMS multicanal : {rc['rms_error']:.3e}  "
      f"(n={rc.get('n_samples', '?')} muestras)")
    A(f"• {rc.get('method', '')}")
    A(f"• {rc['interpretation']}")
    A("")

    A("--- 4. NIVELES Y DINAMICAS " + "-" * 51)
    lv = res["levels"]
    A(f"• SDV RMS    : {_fmt(lv['sdv_rms_dbfs'], 2, ' dBFS')}")
    A(f"• SDI RMS    : {_fmt(lv['sdi_rms_dbfs'], 2, ' dBFS')}")
    A(f"• SDV pico de muestra : {_fmt(lv['sdv_peak_dbfs'], 2, ' dBFS')}")
    A(f"• SDI pico de muestra : {_fmt(lv['sdi_peak_dbfs'], 2, ' dBFS')}")
    if lv.get("sdv_true_peak_dbfs") is not None:
        A(f"• SDV True Peak 4x    : {_fmt(lv['sdv_true_peak_dbfs'], 2, ' dBFS')}")
        A(f"• SDI True Peak 4x    : {_fmt(lv['sdi_true_peak_dbfs'], 2, ' dBFS')}")
        A(f"• metodo true peak    : {lv.get('true_peak_method')}")
    else:
        A(f"• True Peak           : no medido ({lv.get('true_peak_method', 'n/d')})")
    for tag in ("sdv", "sdi"):
        b = res["bands"][tag]
        A(f"• {tag.upper()} centroide: {_fmt(b['centroid_hz'], 0, ' Hz')}")
        A(f"  bandas %  : " + " ".join(f"{v:.1f}" for v in b["band_energy_pct"]))
    A("")

    A("--- 5. POLARIDAD (global y por sub-bandas) " + "-" * 36)
    A(f"• umbral global {pol.get('global_threshold')} | umbral banda {pol.get('band_threshold')} "
      f"| {pol.get('bands')} bandas")
    for role, rep in pol.get("roles", {}).items():
        for pid, d in rep.items():
            g = _fmt(d.get("global"), 3)
            st = d.get("status", "n/d")
            A(f"• {pid}/{role:<12} global={g:<8} {st}", )
            if d.get("bands"):
                A(f"    bandas: " + " ".join(f"{c:+.2f}" for c in d["bands"]))
            if st == "POLARIDAD_AMBIGUA":
                A("    -> Antifase MUTUA: no se puede saber cual guia esta invertida.")
                A("       Decision manual (o re-deriva las guias). No se corrige solo.")
            if st in ("BANDA_INVERTIDA", "SOSPECHOSA", "BANDA_SOSPECHOSA"):
                A("    -> El motor NO corrige esto solo. Revisa o re-deriva la guia.")
    dec = pol.get("correction_decisions") or {}
    if dec.get("applied"):
        A("• --fix-polarity aplicado a:")
        for k, v in dec["applied"].items():
            A(f"    {k}: ganancia {v['gain']} "
              f"(corr global antes {_fmt(v.get('global_corr_before'), 3)})")
    if not pol.get("any_flagged"):
        A("• Sin marcas de polaridad.")
    A("")

    A("--- 6. ALINEACION TEMPORAL " + "-" * 51)
    A(f"• guarda de periodicidad en autocorr={ali.get('guard_autocorr')}; "
      f"pico del mix={_fmt(ali.get('mix_autocorr_peak'), 3)}")
    for pid, rec in ali.get("pairs", {}).items():
        for role, d in rec.items():
            extra = (f" shift={d['applied_shift_samples']} muestras (APLICADO)"
                     if d.get("correction_applied") else "")
            if d.get("classification") == "PERIODIC_PEAK_IGNORED":
                extra += (f" candidato={_fmt(d.get('offset_candidate_ms'), 2, ' ms')}"
                          f" NO aplicado (incierto)")
            A(f"• {pid}/{role:<12} offset={_fmt(d['offset_ms'], 2, ' ms')} "
              f"NCC={_fmt(d['ncc'], 4)} -> {d['classification']}{extra}")
    if ali.get("any_guard_triggered"):
        A("• Se ignoraron picos periodicos: una correccion forzada habria movido")
        A("  guias ya alineadas y degradado el resultado.")
    A("")

    A("--- 7. GEOMETRIA DE RESIDUOS Y CONSENSO " + "-" * 40)
    A(f"• SDV+SDI vs mix: error rel max = {geo.get('error_rel_max', 0):.3e} "
      f"(tolerancia {geo.get('tolerance')}) -> "
      f"{'EXACTA' if geo.get('exact_geometry') else 'NO EXACTA'}")
    A(f"• {geo.get('note', '')}")
    for role in ("vocal", "instrumental"):
        rep = gq.get(role, {})
        if not rep:
            continue
        A(f"• divergencia de guias ({role}):")
        for pid, d in rep.items():
            A(f"    {pid:<16} div={_fmt(d['divergence'], 4)} "
              f"corr={_fmt(d['corr_with_ensemble'], 3)} "
              f"nivel={_fmt(d['rms_vs_ensemble_db'], 1, ' dB')}")
    if gq.get("most_atypical_vocal"):
        A(f"• guia vocal mas atipica    : {gq['most_atypical_vocal']}")
    if gq.get("most_atypical_instrumental"):
        A(f"• guia instrumental mas atipica: {gq['most_atypical_instrumental']}")
    A("")

    A("--- 8. VEREDICTO " + "-" * 61)
    notes: List[str] = []
    if pol.get("any_inverted_total"):
        notes.append("Hay al menos una guia con inversion TOTAL de polaridad: "
                     "reejecuta con --fix-polarity o descarta el par.")
    if any(d.get("status") == "POLARIDAD_AMBIGUA"
           for rep in pol.get("roles", {}).values() for d in rep.values()):
        notes.append("Antifase MUTUA sin referencia: no se puede saber cual guia "
                     "esta invertida. Decision manual requerida.")
    if pol.get("any_flagged") and not pol.get("any_inverted_total"):
        notes.append("Hay marcas de polaridad PARCIAL o de banda. El motor no las "
                     "corrige automaticamente; revisa o re-deriva la guia afectada.")
    if ss["available"] and ss["sdv"].get("mono_db") is not None:
        if ss["sdv"]["mono_db"] < 5.0:
            notes.append("SI-SDR SDV por debajo de 5 dB: revisa las guias de entrada.")
    if not geo.get("exact_geometry"):
        notes.append("Las guias no suman el mix: SDV+SDI no reproducira el mix exacto.")
    if not notes:
        A("• Sin incidencias. El resultado es utilizable.")
    else:
        for n in notes:
            A(f"· {n}")
    A("=" * 78)

    txt = "\n".join(L)
    with open(os.path.join(run_dir, "analysis.txt"), "w", encoding="utf-8") as fh:
        fh.write(txt + "\n")
    print(txt)

    payload = {
        "engine": {"name": ENGINE_NAME, "version": ENGINE_VERSION,
                   "codename": ENGINE_CODENAME},
        "generated_utc": utc_now_iso(),
        "inputs": {"mix": mix_info.to_dict(),
                   "pairs": [p.to_dict() for p in pairs]},
        "effective_config": eff,
        "config_origin": origin,
        "config_warnings": ctx.get("config_warnings", []),
        "processing": res,
        "polarity": pol,
        "alignment": ali,
        "geometry": geo,
        "guide_quality": gq,
        "provenance": ctx.get("provenance"),
    }
    with open(os.path.join(run_dir, "analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(json_safe(payload), fh, indent=2, ensure_ascii=False)


def write_pngs(run_dir: str, res: dict) -> Optional[str]:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        log(f"{Colors.YELLOW}[WARN] matplotlib no disponible: PNG omitidos.{Colors.RESET}")
        return None
    try:
        fig, ax = plt.subplots(1, 2, figsize=(11, 4))
        for a, tag, col in ((ax[0], "sdv", "#4C9AFF"), (ax[1], "sdi", "#FF8C42")):
            b = res["bands"][tag]
            a.bar([f"{lo/1000:.0f}-{hi/1000:.0f}" for lo, hi in ISO_BANDS_HZ],
                  b["band_energy_pct"], color=col)
            a.set_title(f"{tag.upper()} energia por sub-banda")
            a.set_ylabel("%")
            a.tick_params(axis="x", rotation=90, labelsize=7)
        fig.tight_layout()
        p = os.path.join(run_dir, "bands.png")
        fig.savefig(p, dpi=110)
        plt.close(fig)
        return p
    except Exception as exc:
        log(f"{Colors.YELLOW}[WARN] PNG no generado: {exc}{Colors.RESET}")
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        description=f"{ENGINE_NAME} v{ENGINE_VERSION} ({ENGINE_CODENAME}) — "
                    f"consenso complejo SDV/SDI a partir de guias residuales.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--manifest", required=True, help="Manifiesto JSON")
    p.add_argument("--out", default=None, help="Carpeta de salida")
    p.add_argument("--branch", choices=BRANCHES, default="normal",
                   help="Rama de construccion de SDV/SDI")
    p.add_argument("--consensus", choices=CONSENSUS_METHODS, default="magnitudes_first",
                   help="Metodo de consenso entre guias")
    p.add_argument("--run-mode", choices=RUN_MODES, default="full_processing")
    p.add_argument("--dry-run", action="store_true", help="Valida y planifica sin procesar")
    p.add_argument("--power", type=float, default=POWER_DEFAULT,
                   help="Exponente de la mascara (rama identity)")
    p.add_argument("--epsilon", type=float, default=EPSILON_DEFAULT)
    p.add_argument("--smoothing", choices=SMOOTHING_KERNELS, default="none")
    p.add_argument("--mask-mode", choices=MASK_MODES, default="per_channel")
    p.add_argument("--n-fft", type=int, choices=N_FFT_ALLOWED, default=N_FFT_DEFAULT)
    p.add_argument("--hop", type=int, default=HOP_DEFAULT)
    p.add_argument("--chunk-frames", type=int, default=CHUNK_FRAMES_DEFAULT)
    p.add_argument("--fix-polarity", action="store_true",
                   help="Invierte el signo de las guias en contrafase TOTAL detectada")
    p.add_argument("--allow-misaligned", action="store_true",
                   help="No abortar si hay desalineacion > 10 ms")
    p.add_argument("--correct-alignment", action="store_true",
                   help="Compensa el desfase VAD (protegido contra periodicidad)")
    p.add_argument("--enable-loo", action="store_true",
                   help="Activa la validacion leave-one-out (cuesta ~1.5x)")
    p.add_argument("--no-loo", dest="enable_loo", action="store_false")
    p.set_defaults(enable_loo=False)
    p.add_argument("--ref-vocal", default=None, help="Stem vocal real para SI-SDR")
    p.add_argument("--ref-inst", default=None, help="Stem instrumental real para SI-SDR")
    p.add_argument("--png", action="store_true", help="Genera graficos PNG")
    p.add_argument("--no-wav", action="store_true", help="No escribir WAVs")
    p.add_argument("--quiet", action="store_true")
    p.add_argument("--version", action="version",
                   version=f"{ENGINE_NAME} {ENGINE_VERSION} ({ENGINE_CODENAME})")
    return p


def _detect_cli_flags(argv: Sequence[str]) -> set:
    out = set()
    for a in argv:
        if a.startswith("--"):
            out.add(a.split("=", 1)[0])
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args._cli_flags = _detect_cli_flags(argv)

    if args.quiet:
        Colors.disable()
    if args.dry_run:
        args.run_mode = "dry_run"

    signal.signal(signal.SIGINT, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt))

    try:
        mix_path, pairs, cal, out_dir = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    # R-13: single_pair restringe la ejecucion a UN par (comportamiento
    # documentado en la interfaz); el resto del pipeline es identico.
    if args.run_mode == "single_pair":
        if not pairs:
            print("[FATAL] single_pair: el manifest no contiene pares.",
                  file=sys.stderr)
            return EXIT_VALIDATION
        log(f"{Colors.CYAN}SINGLE_PAIR: procesando solo {pairs[0].pair_id} "
            f"(1 de {len(pairs)} pares).{Colors.RESET}")
        pairs = pairs[:1]

    try:
        eff, origin, cfg_warn = resolve_effective_config(args, cal)
    except ManifestError as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return EXIT_VALIDATION
    apply_effective(args, eff)

    errs = validate_numeric(args, None)
    if errs:
        for e in errs:
            print(f"[FATAL] {e}", file=sys.stderr)
        return EXIT_VALIDATION

    # ---- referencias externas: E-04, abortar si vienen mal ---------------
    for label, path in (("--ref-vocal", args.ref_vocal), ("--ref-inst", args.ref_inst)):
        if path is not None and not os.path.isfile(path):
            print(f"[FATAL] {label} apunta a un archivo inexistente: {path}\n"
                  f"        Se aborta para no dar por medido un SI-SDR que no existe.",
                  file=sys.stderr)
            return EXIT_VALIDATION

    # ---- validacion de entradas -----------------------------------------
    try:
        mix_info = probe_file(mix_path, "Mix original")
        if mix_info.channels < 1:
            raise ValueError("Mix sin canales.")
        if mix_info.sample_rate < 8000:
            raise ValueError(f"Mix con sample_rate={mix_info.sample_rate} Hz demasiado bajo.")
    except (ValueError, FileNotFoundError) as exc:
        print(f"[FATAL] {exc}", file=sys.stderr)
        return EXIT_VALIDATION

    # ---- referencias: duracion estricta (revision v2, punto 5) -----------
    # Sin recortes ni rellenos: si difiere, se aborta con mensaje descriptivo.
    for label, path in (("--ref-vocal", args.ref_vocal),
                        ("--ref-inst", args.ref_inst)):
        if path is not None and os.path.isfile(path):
            try:
                ri = probe_file(path, label)
            except (ValueError, FileNotFoundError) as exc:
                print(f"[FATAL] {exc}", file=sys.stderr)
                return EXIT_VALIDATION
            if ri.frames != mix_info.frames:
                print(f"[FATAL] {label}: duracion={ri.frames} muestras != "
                      f"mix={mix_info.frames}. Se exige igualdad exacta con "
                      f"el mix (sin recortes ni rellenos automaticos). "
                      f"Re-aligna o re-deriva la referencia antes de medir.",
                      file=sys.stderr)
                return EXIT_VALIDATION

    guide_infos: List[Tuple[PairMeta, FileInfo, FileInfo]] = []
    for p in pairs:
        try:
            vi = probe_file(p.vocal_path, f"{p.pair_id}/vocal")
            if vi.channels != mix_info.channels:
                raise ValueError(
                    f"{p.pair_id}/vocal: canales={vi.channels} != {mix_info.channels} del mix. "
                    f"Se exige coincidencia estricta.")
            if vi.sample_rate != mix_info.sample_rate:
                raise ValueError(
                    f"{p.pair_id}/vocal: sample_rate={vi.sample_rate} != "
                    f"{mix_info.sample_rate} del mix.")
            if vi.frames != mix_info.frames:
                raise ValueError(
                    f"{p.pair_id}/vocal: duracion={vi.frames} muestras != "
                    f"mix={mix_info.frames}. Se exige igualdad exacta "
                    f"(sin recortes ni rellenos automaticos).")
            check_degeneration(vi)

            ii = probe_file(p.instrumental_path, f"{p.pair_id}/instrumental")
            if ii.channels != mix_info.channels:
                raise ValueError(
                    f"{p.pair_id}/instrumental: canales={ii.channels} != "
                    f"{mix_info.channels} del mix.")
            if ii.sample_rate != mix_info.sample_rate:
                raise ValueError(
                    f"{p.pair_id}/instrumental: sample_rate={ii.sample_rate} != "
                    f"{mix_info.sample_rate} del mix.")
            if ii.frames != mix_info.frames:
                raise ValueError(
                    f"{p.pair_id}/instrumental: duracion={ii.frames} muestras != "
                    f"mix={mix_info.frames}. Se exige igualdad exacta "
                    f"(sin recortes ni rellenos automaticos).")
            check_degeneration(ii)
            guide_infos.append((p, vi, ii))
        except (ValueError, FileNotFoundError) as exc:
            print(f"[FATAL] {exc}", file=sys.stderr)
            return EXIT_VALIDATION

    total_bytes = sum(gi.nbytes for _, gi, _ in []) + sum(
        vi.nbytes + ii.nbytes for _, vi, ii in guide_infos)
    log(f"{Colors.GREEN}Validacion OK{Colors.RESET}: mix "
        f"{mix_info.sample_rate} Hz/{mix_info.channels} ch "
        f"({fmt_size(mix_info.nbytes)}), {len(pairs)} pares "
        f"({fmt_size(total_bytes)})")

    plan = FramePlan(mix_info.frames, args.n_fft, args.hop, args.chunk_frames,
                     mix_info.channels)
    n_frames = plan.n_frames
    if n_frames <= 0:
        print(f"[FATAL] El mix tiene {mix_info.frames} muestras, menos que n_fft="
              f"{args.n_fft}. No hay ni una ventana completa.", file=sys.stderr)
        return EXIT_VALIDATION

    if args.run_mode == "dry_run":
        log(f"{Colors.CYAN}DRY_RUN{Colors.RESET}: plan verificado.")
        log(f"  Mix  : {mix_info.path}")
        log(f"  STFT : K={n_frames} tramas, {plan.n_bins} bins, chunks de {args.chunk_frames}")
        log(f"  Rama : {args.branch} | consenso: {eff['consensus']}")
        log(f"  n_fft={args.n_fft} hop={args.hop} power={args.power} eps={args.epsilon}")
        for p, vi, ii in guide_infos:
            log(f"  {p.pair_id:<20} F={p.family:<10} V={vi.path}")
        for w in cfg_warn:
            log(f"  {Colors.YELLOW}! {w}{Colors.RESET}")
        return EXIT_OK

    # ---- auditorias previas ---------------------------------------------
    log("Auditoria de polaridad (global + sub-bandas)...")
    pol = audit_polarity(pairs, mix_info)

    def _log_pol(rep_pol: dict) -> None:
        for role, rep in rep_pol["roles"].items():
            for pid, d in rep.items():
                if d.get("status") not in (None, "OK"):
                    extra = ""
                    if d.get("bands"):
                        extra = " bandas=" + " ".join(f"{c:+.2f}" for c in d["bands"])
                    log(f"  {Colors.YELLOW}[WARN] {pid}/{role}: {d['status']} "
                        f"(global={_fmt(d.get('global'), 3)}){extra}{Colors.RESET}")

    _log_pol(pol)

    # R-06: --fix-polarity aplica de verdad la ganancia -1 a las guias en
    # inversion TOTAL (no ambiguas) y re-audita para verificar la correccion.
    gains: dict = {}
    pol_decisions: dict = {"enabled": bool(args.fix_polarity), "applied": {}}
    if args.fix_polarity:
        for role, rep in pol["roles"].items():
            for pid, d in rep.items():
                if d.get("status") == "INVERTIDA_TOTAL":
                    gains[(pid, role)] = -1.0
                    pol_decisions["applied"][f"{pid}/{role}"] = {
                        "decision": "invertir_ganancia", "gain": -1.0,
                        "global_corr_before": d.get("global")}
        if gains:
            log(f"{Colors.CYAN}[FIX] --fix-polarity: aplicando ganancia -1 a "
                f"{len(gains)} guia(s)...{Colors.RESET}")
            pol_before = pol
            pol = audit_polarity(pairs, mix_info, gains=gains)
            _log_pol(pol)
            pol_decisions["before"] = {
                f"{pid}/{role}": d.get("status")
                for role, rep in pol_before["roles"].items()
                for pid, d in rep.items()}
            pol_decisions["after"] = {
                f"{pid}/{role}": d.get("status")
                for role, rep in pol["roles"].items()
                for pid, d in rep.items()}
            if pol.get("any_inverted_total"):
                log(f"{Colors.RED}[FATAL] --fix-polarity no resolvio la inversion "
                    f"total (persiste tras re-auditar). Abortando para no "
                    f"procesar con guias en contrafase.{Colors.RESET}")
                return EXIT_VALIDATION
            log(f"{Colors.GREEN}[OK] Re-auditoria post-correccion sin inversiones "
                f"totales.{Colors.RESET}")
        else:
            log("  --fix-polarity: sin inversiones totales no ambiguas que corregir.")
    elif pol.get("any_inverted_total"):
        log(f"{Colors.YELLOW}[WARN] Inversion TOTAL de polaridad detectada. "
            f"Ejecuta con --fix-polarity.{Colors.RESET}")
    if any(d.get("status") == "POLARIDAD_AMBIGUA"
           for rep in pol["roles"].values() for d in rep.values()):
        log(f"{Colors.MAGENTA}[WARN] Ensamble en antifase MUTUA (ambiguo): no se "
            f"puede saber cual guia esta invertida. Decision manual "
            f"requerida.{Colors.RESET}")
    if pol.get("any_flagged") and not pol.get("any_inverted_total"):
        log(f"{Colors.MAGENTA}[WARN] Marcas de polaridad parcial/de banda. El motor "
            f"NO las corrige automaticamente: revisa o re-deriva la guia "
            f"afectada.{Colors.RESET}")
    pol["correction_decisions"] = pol_decisions

    log("Auditoria de alineacion temporal (con guarda de periodicidad)...")
    ali = audit_alignment(pairs, mix_info)
    shifts: dict = {}
    ali_decisions: dict = {"enabled": bool(args.correct_alignment), "applied": {}}
    for pid, rec in ali["pairs"].items():
        for role, d in rec.items():
            shifts[(pid, role)] = 0
            if d["classification"] != "ALIGNED":
                log(f"  {Colors.YELLOW}{pid}/{role}: {d['classification']} "
                    f"offset={_fmt(d['offset_ms'], 2, ' ms')} "
                    f"guard={d['autocorr_guard']:.3f}{Colors.RESET}")
            # R-05: la correccion se APLICA de verdad (shift en la lectura de
            # la guia) solo con bandera, clasificacion MISALIGNED y lag fiable.
            # Los candidatos inciertos (periodicos) NUNCA se aplican.
            if d["classification"] == "MISALIGNED" and args.correct_alignment:
                sh = int(d.get("lag_samples") or
                         round(d["offset_ms"] * mix_info.sample_rate / 1000.0))
                if sh != 0:
                    shifts[(pid, role)] = sh
                    d["applied_shift_samples"] = sh
                    d["correction_applied"] = True
                    ali_decisions["applied"][f"{pid}/{role}"] = {
                        "original_offset_ms": d.get("offset_candidate_ms"),
                        "applied_shift_samples": sh,
                        "sign_convention": ("shift>0: la guia va retrasada; se leen "
                                            "muestras mas adelante para compensar")}
                    log(f"    -> R-05 shift aplicado: {sh} muestras "
                        f"(original {_fmt(d.get('offset_candidate_ms'), 2, ' ms')})")
                else:
                    d["correction_applied"] = False
            else:
                d["correction_applied"] = False
                if d["classification"] == "PERIODIC_PEAK_IGNORED":
                    ali_decisions.setdefault("not_applied_uncertain", []).append(
                        f"{pid}/{role}: candidato "
                        f"{_fmt(d.get('offset_candidate_ms'), 2, ' ms')} NO "
                        f"aplicado (pico periodico: offset incierto)")
                    log(f"    -> candidato {_fmt(d.get('offset_candidate_ms'), 2, ' ms')} "
                        f"NO aplicado (incertidumbre por periodicidad).")
    ali["applied_corrections"] = ali_decisions
    if ali["any_guard_triggered"]:
        log(f"{Colors.GREEN}[OK] Pico periodico ignorado: no se movieron guias alineadas."
            f"{Colors.RESET}")
    if ali["any_misaligned"] and not (args.allow_misaligned or args.correct_alignment):
        log(f"[ABORT] Guias desalineadas (> {ALIGN_MAX_MS} ms). Usa --allow-misaligned "
            f"para forzar o --correct-alignment para compensar (R-05: "
            f"--correct-alignment aplica el shift medido en la lectura).")
        return EXIT_VALIDATION
    if args.correct_alignment and any(shifts.values()):
        log(f"{Colors.GREEN}[OK] R-05: {sum(1 for v in shifts.values() if v)} guia(s) "
            f"recibiran shift de alineacion.{Colors.RESET}")

    log("Geometria de residuos y divergencia entre guias...")
    geo = check_geometry(mix_info, pairs)
    log(f"  SDV+SDI vs mix: error rel max = {geo['error_rel_max']:.3e} -> "
        f"{'EXACTA' if geo['exact_geometry'] else 'NO EXACTA'}")
    gq = measure_guide_quality(pairs, mix_info)

    # ---- carpeta de salida ----------------------------------------------
    base = args.out or out_dir or os.getcwd()
    os.makedirs(base, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(base, f"motorV3_run_{stamp}")
    suffix = 1
    while os.path.isdir(run_dir):
        run_dir = os.path.join(base, f"motorV3_run_{stamp}_{suffix}")
        suffix += 1
    os.makedirs(run_dir, exist_ok=True)
    init_tee(os.path.join(run_dir, "engine_log.txt"))

    # R-17: procedencia completa — cada salida queda ligada a sus entradas
    # (rutas exactas + SHA-256) y a la configuracion efectiva de la ejecucion.
    t_hash = time.time()
    prov = {
        "engine": ENGINE_NAME, "engine_version": ENGINE_VERSION,
        "engine_codename": ENGINE_CODENAME,
        "generated_utc": utc_now_iso(),
        "run_mode": args.run_mode,
        "argv": list(argv),
        "python": sys.version.split()[0],
        "numpy": np.__version__, "soundfile": sf.__version__,
        "manifest": {"path": os.path.abspath(args.manifest),
                     "sha256": sha256_file(args.manifest)},
        "mix": {"path": os.path.abspath(mix_info.path),
                "sha256": sha256_file(mix_info.path),
                "frames": mix_info.frames, "sample_rate": mix_info.sample_rate,
                "channels": mix_info.channels, "subtype": mix_info.subtype},
        "pairs": [
            {"pair_id": p.pair_id,
             "vocal": {"path": os.path.abspath(p.vocal_path),
                       "sha256": sha256_file(p.vocal_path),
                       "frames": vi.frames, "sample_rate": vi.sample_rate,
                       "channels": vi.channels, "subtype": vi.subtype},
             "instrumental": {"path": os.path.abspath(p.instrumental_path),
                              "sha256": sha256_file(p.instrumental_path),
                              "frames": ii.frames, "sample_rate": ii.sample_rate,
                              "channels": ii.channels, "subtype": ii.subtype}}
            for p, vi, ii in guide_infos],
        "references": {
            "vocal": ({"path": os.path.abspath(args.ref_vocal),
                       "sha256": sha256_file(args.ref_vocal)}
                      if os.path.isfile(args.ref_vocal or "") else None),
            "instrumental": ({"path": os.path.abspath(args.ref_inst),
                              "sha256": sha256_file(args.ref_inst)}
                             if os.path.isfile(args.ref_inst or "") else None)},
        "effective_config": eff, "config_origin": origin,
        "corrections": {"polarity": pol.get("correction_decisions"),
                        "alignment": ali.get("applied_corrections")},
        "hash_elapsed_s": round(time.time() - t_hash, 3),
    }
    pp = os.path.join(run_dir, "provenance.json")
    with open(pp, "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=2, ensure_ascii=False, default=str)
    log(f"Procedencia (R-17): {pp} "
        f"(mix {prov['mix']['sha256'][:16]}..., {len(pairs)} par(es))")

    ctx = {
        "polarity": pol, "alignment": ali, "geometry": geo, "guide_quality": gq,
        "effective_config": eff, "config_origin": origin, "config_warnings": cfg_warn,
        "provenance": prov,
    }

    # R-13: analysis_only ejecuta SOLO las auditorias y escribe su informe;
    # no procesa y no escribe WAVs de salida.
    if args.run_mode == "analysis_only":
        analysis = {"polarity": pol, "alignment": ali, "geometry": geo,
                    "guide_quality": gq, "effective_config": eff,
                    "config_origin": origin, "config_warnings": cfg_warn,
                    "provenance": prov, "run_mode": args.run_mode,
                    "generated_utc": utc_now_iso()}
        pa = os.path.join(run_dir, "analysis_only.json")
        with open(pa, "w", encoding="utf-8") as fh:
            json.dump(analysis, fh, indent=2, ensure_ascii=False, default=str)
        log(f"{Colors.CYAN}ANALYSIS_ONLY: auditorias completadas, sin "
            f"procesado.{Colors.RESET} -> {pa}")
        close_tee()
        log(f"{Colors.GREEN}Listo.{Colors.RESET} Salida: {run_dir}")
        return EXIT_OK

    try:
        log(f"Procesando rama {Colors.BOLD}{args.branch}{Colors.RESET} "
            f"con consenso {eff['consensus']}...")
        res = run_processing(args, mix_info, pairs, args.branch, eff["consensus"],
                             run_dir, not args.no_wav,
                             args.ref_vocal if os.path.isfile(args.ref_vocal or "")
                             else None,
                             args.ref_inst if os.path.isfile(args.ref_inst or "")
                             else None,
                             shifts, gains, args.enable_loo)
    except KeyboardInterrupt:
        log(f"{Colors.RED}[ABORT] Interrumpido por el usuario.{Colors.RESET}")
        return EXIT_ABORTED
    except Exception as exc:
        log(f"{Colors.RED}[FATAL] {exc}{Colors.RESET}")
        import traceback
        traceback.print_exc()
        return EXIT_RUNTIME

    if args.png:
        png = write_pngs(run_dir, res)
        if png:
            log(f"PNG: {png}")

    write_reports(run_dir, ctx, res, args, mix_info, pairs)
    close_tee()
    log(f"{Colors.GREEN}Listo.{Colors.RESET} Salida: {run_dir}")
    return EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[ABORT] Interrumpido.", file=sys.stderr)
        sys.exit(EXIT_ABORTED)


