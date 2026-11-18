"""Generador determinista de senales sinteticas con ground truth.

NO son voces ni instrumentos reales: son SUSTITUTOS CONTROLADOS. Toda conclusion
sobre musica real queda fuera del alcance de estas senales.

Convenio:
    M = V_true + I_true            (identidad exacta, float64)
    V_true, I_true: (n, 2) float64, 44100 Hz por defecto.

Todo es reproducible con la semilla indicada; no hay estado global.
"""
from __future__ import annotations

import numpy as np

SR_DEF = 44100


# ---------------------------------------------------------------- utilidades
def _t(n: int, sr: int) -> np.ndarray:
    return np.arange(n, dtype=np.float64) / sr


def _fade(x: np.ndarray, ms: float = 5.0, sr: int = SR_DEF) -> np.ndarray:
    """Rampas de entrada/salida para evitar clics en el borde (no altera el interior)."""
    k = max(1, int(ms * 1e-3 * sr))
    n = x.shape[0]
    if n < 2 * k:
        return x
    w = np.ones(n)
    w[:k] = np.linspace(0.0, 1.0, k)
    w[-k:] = np.linspace(1.0, 0.0, k)
    return x * (w[:, None] if x.ndim == 2 else w)


def _pan(mono: np.ndarray, pan: float) -> np.ndarray:
    """pan en [-1, 1]: -1 = solo L, 0 = centro, +1 = solo R. Ley constante de potencia."""
    th = (pan + 1.0) * np.pi / 4.0
    return np.stack([mono * np.cos(th), mono * np.sin(th)], axis=1)


# ---------------------------------------------------------------- fuentes
def voz_armonica(n: int, sr: int, f0: float, rng: np.random.Generator,
                 vibrato_hz: float = 5.2, vibrato_ct: float = 28.0,
                 formantes=(700.0, 1220.0, 2600.0), deriva_ct: float = 60.0,
                 n_armonicos: int = 26) -> np.ndarray:
    """Sustituto vocal: armonicos con F0 con vibrato + deriva lenta, y formantes moviles.

    No es una voz humana. Solo conserva dos rasgos utiles para el experimento:
    estructura armonica con F0 variable y envolvente espectral con picos moviles.
    """
    t = _t(n, sr)
    f0_t = f0 * 2.0 ** ((deriva_ct / 1200.0) * np.sin(2 * np.pi * 0.11 * t)
                        + (vibrato_ct / 1200.0) * np.sin(2 * np.pi * vibrato_hz * t))
    fase = 2 * np.pi * np.cumsum(f0_t) / sr
    x = np.zeros(n)
    for k in range(1, n_armonicos + 1):
        fk = k * f0
        if fk > 0.45 * sr:
            break
        # envolvente de formantes: picos gaussianos en frecuencia, movidos en el tiempo
        env = np.zeros(n)
        for i, f in enumerate(formantes):
            fc = f * (1.0 + 0.06 * np.sin(2 * np.pi * (0.13 + 0.04 * i) * t + i))
            ancho = 120.0 + 40.0 * i
            env += np.exp(-0.5 * ((fk - fc) / ancho) ** 2)
        env /= (1.0 + 0.25 * k)
        amp = 0.55 + 0.45 * np.sin(2 * np.pi * 0.7 * t + 0.3 * k)
        x += env * amp * np.sin(k * fase + 0.11 * k)
    # respiracion/aire: ruido coloreado suave
    aire = rng.standard_normal(n) * 0.004
    return x / (np.abs(x).max() + 1e-12) * 0.7 + aire


def instrumento_armonico(n: int, sr: int, f0: float, rng: np.random.Generator,
                         acorde=(1.0, 1.26, 1.5), n_armonicos: int = 14) -> np.ndarray:
    """Sustituto instrumental armonico: acorde con armonicos y ligero chorus."""
    t = _t(n, sr)
    x = np.zeros(n)
    for j, ratio in enumerate(acorde):
        f = f0 * ratio
        for k in range(1, n_armonicos + 1):
            fk = k * f
            if fk > 0.45 * sr:
                break
            amp = 1.0 / (k ** 1.1)
            det = 1.0 + 0.0007 * (j + 1)
            x += amp * np.sin(2 * np.pi * fk * det * t + 0.4 * k + j)
    return x / (np.abs(x).max() + 1e-12) * 0.6


def instrumento_inarmonico(n: int, sr: int, rng: np.random.Generator,
                           golpes_por_s: float = 6.0,
                           jitter: float = 0.0) -> np.ndarray:
    """Sustituto percusivo inarmonico: transitorios con decaimiento exponencial.

    jitter: 0.0 => onsets estrictamente periodicos (envolvente periodica exacta);
            >0  => cada onset se desplaza uniformemente en +-jitter*periodo. Sirve
            para separar el efecto de la periodicidad de la envolvente del efecto
            del estimador de alineacion (ver Etapa A, sub-experimento AL).
    """
    t = _t(n, sr)
    x = np.zeros(n)
    periodo = int(sr / golpes_por_s)
    for ini in range(0, n, periodo):
        if jitter > 0:
            ini = int(ini + rng.uniform(-jitter, jitter) * periodo)
            if ini < 0:
                continue
        fin = min(n, ini + int(0.18 * sr))
        m = fin - ini
        if m <= 0:
            continue
        tt = np.arange(m) / sr
        # inarmonico: varias parciales no enteras
        golpe = sum(np.sin(2 * np.pi * f * tt + rng.uniform(0, 6.28)) *
                    np.exp(-tt / (0.02 + 0.006 * i))
                    for i, f in enumerate((180.0, 271.3, 397.7, 611.9)))
        golpe *= (0.5 + 0.5 * rng.random())
        x[ini:fin] += golpe
    return x / (np.abs(x).max() + 1e-12) * 0.5


def cola_reverb(mono: np.ndarray, sr: int, rng: np.random.Generator,
                rt60: float = 0.6, mezcla: float = 0.25) -> np.ndarray:
    """Reverberacion sintetica por convolucion con ruido exponencial (no es una sala real)."""
    m = int(rt60 * sr)
    if m < 2:
        return mono
    ir = rng.standard_normal(m) * np.exp(-np.arange(m) / (rt60 * sr / 6.9))
    ir /= (np.abs(ir).sum() + 1e-12)
    seco = mono
    mojado = np.convolve(mono, ir, mode="full")[: len(mono)]
    mojado /= (np.abs(mojado).max() + 1e-12) * (1 / (np.abs(seco).max() + 1e-12))
    return (1 - mezcla) * seco + mezcla * mojado


# ---------------------------------------------------------------- escenarios
def escenario(nombre: str, dur: float = 4.0, sr: int = SR_DEF, seed: int = 20261117,
              pan_voz: float = 0.0, pan_inst: float = 0.0,
              reverb_voz: float = 0.0, reverb_inst: float = 0.0,
              solapamiento: float = 0.0, jitter: float = 0.0) -> dict:
    """Devuelve dict con V_true, I_true, M y metadatos del escenario.

    Tipos minimos exigidos por la especificacion (§4), todos SUSTITUTOS CONTROLADOS:
      voz_armonica        : voz con formantes moviles + instrumento armonico simple
      varias_voces        : dos voces simultaneas en V (F0 y pan distintos)
      instrumentos        : dos instrumentos armonicos en I (acorde + bajo)
      percusivo           : percusion inarmonica dominante en I
      percusivo_aperiodico: igual que percusivo pero con onsets no periodicos (jitter)
      aire_reverb         : ruido de aire + colas de reverb largas en ambas fuentes
      estereo             : fuentes con posiciones estereo distintas y reverb distinta
      solapamiento        : F0 instrumental llevada a la F0 vocal (solapamiento severo)

    solapamiento: 0..1, acerca la F0 instrumental a la vocal.
    """
    rng = np.random.default_rng(seed)
    n = int(dur * sr)

    f0v = 196.0
    f0i = 98.0 * (1.0 + solapamiento * 1.0)          # 98 Hz -> hasta 196 Hz
    acorde = (1.0, 1.26, 1.5)

    xv = voz_armonica(n, sr, f0v, rng)
    xi = instrumento_armonico(n, sr, f0i, rng, acorde=acorde) * (1.0 - 0.5 * solapamiento)
    perc = instrumento_inarmonico(n, sr, rng)
    ruido = rng.standard_normal(n) * 0.002

    if nombre == "varias_voces":
        v2 = voz_armonica(n, sr, 233.08, rng, deriva_ct=80.0)
        xv = 0.85 * xv + 0.85 * v2
    elif nombre == "instrumentos":
        xi = xi + instrumento_armonico(n, sr, 65.4, rng, acorde=(1.0, 1.5, 2.0)) * 0.8
    elif nombre == "percusivo":
        xi = 0.7 * xi + 1.6 * perc + ruido
    elif nombre == "percusivo_aperiodico":
        perc = instrumento_inarmonico(n, sr, rng, jitter=max(jitter, 0.45))
        xi = 0.7 * xi + 1.6 * perc + ruido
    elif nombre == "aire_reverb":
        ruido = rng.standard_normal(n) * 0.01
    elif nombre == "solapamiento":
        pass                                          # lo controla el parametro
    elif nombre not in ("voz_armonica", "estereo"):
        raise ValueError(f"escenario desconocido: {nombre}")

    if nombre != "percusivo" and nombre != "percusivo_aperiodico":
        xi = xi + 0.6 * perc
    xi = xi + ruido

    if nombre == "estereo":
        pan_voz, pan_inst = -0.7, 0.6
        reverb_voz, reverb_inst = 0.35, 0.15
    if nombre == "aire_reverb":
        reverb_voz, reverb_inst = 0.55, 0.45

    if reverb_voz > 0:
        xv = cola_reverb(xv, sr, rng, rt60=0.55, mezcla=reverb_voz)
    if reverb_inst > 0:
        xi = cola_reverb(xi, sr, rng, rt60=0.8, mezcla=reverb_inst)

    V = _pan(xv, pan_voz)
    I = _pan(xi, pan_inst)
    V = _fade(V, sr=sr)
    I = _fade(I, sr=sr)
    M = V + I                                        # identidad exacta
    return {
        "nombre": nombre, "sr": sr, "n": n, "seed": seed,
        "V_true": V, "I_true": I, "M": M,
        "pan_voz": pan_voz, "pan_inst": pan_inst,
        "reverb_voz": reverb_voz, "reverb_inst": reverb_inst,
        "solapamiento": solapamiento, "jitter": jitter,
        "f0_voz": f0v, "f0_inst": f0i,
    }


def fuente_ausente(sc: dict, cual: str = "voz") -> dict:
    """Control negativo: una de las dos fuentes se elimina (Mix coherente, no truncado)."""
    out = dict(sc)
    if cual == "voz":
        out["V_true"] = np.zeros_like(sc["V_true"])
    elif cual == "inst":
        out["I_true"] = np.zeros_like(sc["I_true"])
    else:
        raise ValueError("cual debe ser 'voz' o 'inst'")
    out["M"] = out["V_true"] + out["I_true"]
    out["nombre"] = sc["nombre"] + f"__sin_{cual}"
    return out
