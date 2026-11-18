"""Familias de guias degradadas (10) con niveles explicita y numericamente definidos.

Contrato de cada funcion generadora:
    f(sc, rng, nivel, **kw) -> (pares, meta)
      pares : lista de (V_guide, I_guide) con la MISMA forma que (sc["V_true"], sc["I_true"])
      meta  : dict con familia, nivel, parametros efectivos y la degradacion medida
              respecto a la verdad (SNR de la guia), para no depender del nombre del nivel.

Ninguna guia se normaliza ni se le aplica ganancia posterior: la degradacion es la
unica transformacion, y queda registrada. Los niveles (pequeno/moderado/severo) se
declaran en `NIVELES` y se guardan en configs/guias.json.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import hilbert

EPS = 1e-12

# Niveles en unidades fisicas, no adjetivos. dB relativos a la fuente interferente
# salvo donde se indique (dBFS de la guia, o ms de desplazamiento).
NIVELES = {
    "bleeding":            {"pequeno": -20.0, "moderado": -12.0, "severo": -6.0},   # dB de fuga ajena
    "atenuacion":          {"pequeno": -1.5,  "moderado": -6.0,  "severo": -12.0},  # dB de ganancia
    "desfase_temporal":    {"pequeno": 5.0,   "moderado": 25.0,  "severo": 100.0},  # ms
    "error_fase":          {"pequeno": 15.0,  "moderado": 45.0,  "severo": 90.0},   # grados (constante, magnitud intacta)
    "perdida_espectral":   {"pequeno": 0.25,  "moderado": 0.5,   "severo": 1.0},    # fraccion de banda eliminada (1 kHz-4 kHz)
    "error_localizado":    {"pequeno": 0.25,  "moderado": 1.0,   "severo": 2.0},    # segundos sustituidos por el mix
    "desacuerdo":          {"pequeno": -30.0, "moderado": -18.0, "severo": -9.0},   # dB del ruido de desacuerdo
    "asimetria_estereo":   {"pequeno": -1.5,  "moderado": -6.0,  "severo": -12.0},  # dB de diferencia L/R
    "correlacion_errores": {"pequeno": 0.0,   "moderado": 0.6,   "severo": 0.95},   # rho del error compartido
    "todos_iguales":       {"pequeno": 0,     "moderado": 0,     "severo": 0},      # control negativo, sin nivel
}


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2) + EPS))


def _snr(ref: np.ndarray, test: np.ndarray) -> float:
    k = min(len(ref), len(test))          # guias mas cortas: prefijo comun
    ref, test = ref[:k], test[:k]
    n = float(np.sum(ref ** 2))
    d = float(np.sum((test - ref) ** 2))
    return float(10 * np.log10(max(n, EPS) / max(d, EPS)))


def _meta(familia, nivel, pares, sc, params):
    vs = [_snr(sc["V_true"], g[0]) for g in pares]
    ins = [_snr(sc["I_true"], g[1]) for g in pares]
    def _suman(g):
        k = min(len(g[0]), len(sc["M"]))
        if len(g[0]) != len(sc["M"]):
            return None            # longitudes distintas: la identidad no aplica
        return bool(np.max(np.abs((g[0] + g[1]) - sc["M"])) < 1e-12)
    return {"familia": familia, "nivel": nivel, "parametros": params,
            "snr_guia_vocal_db": vs, "snr_guia_instrumental_db": ins,
            "K": len(pares), "formas": [list(g[0].shape) for g in pares],
            "guias_suman_mix": (None if any(_suman(g) is None for g in pares)
                                else bool(all(_suman(g) for g in pares)))}


# ---------------------------------------------------------------- 1. ideal
def g_ideal(sc, rng, nivel=None, **kw):
    pares = [(sc["V_true"].copy(), sc["I_true"].copy())]
    return pares, _meta("ideal", "ideal", pares, sc, {})


# ---------------------------------------------------------------- 2. bleeding
def g_bleeding(sc, rng, nivel="moderado", escala_por_canal=False, **kw):
    """G_v = V + a*I, G_i = I + a*V.  a = 10^(dB/20) * rms(V)/rms(I) (fuga relativa)."""
    dB = NIVELES["bleeding"][nivel]
    V, I = sc["V_true"], sc["I_true"]
    a = 10 ** (dB / 20.0)
    if escala_por_canal:
        av = np.array([[a * _rms(V[:, 0]) / _rms(I[:, 0])], [a * _rms(V[:, 1]) / _rms(I[:, 1])]])
        gv = V + I * av.T
        gi = I + V * av.T
    else:
        gv = V + a * (_rms(V) / _rms(I)) * I
        gi = I + a * (_rms(I) / _rms(V)) * V
    pares = [(gv, gi)]
    return pares, _meta("bleeding", nivel, pares, sc, {"fuga_db": dB, "por_canal": escala_por_canal})


# ---------------------------------------------------------------- 3. atenuacion
def g_atenuacion(sc, rng, nivel="moderado", cual="ambas", canal=None, **kw):
    """Ganancia uniforme. `canal`!=None aplica la ganancia SOLO a ese canal."""
    dB = NIVELES["atenuacion"][nivel]
    g = 10 ** (dB / 20.0)
    V, I = sc["V_true"].copy(), sc["I_true"].copy()
    def aplicar(x):
        if canal is None:
            return x * g
        y = x.copy()
        y[:, canal] = y[:, canal] * g
        return y
    V = aplicar(V) if cual in ("ambas", "voz") else V
    I = aplicar(I) if cual in ("ambas", "inst") else I
    pares = [(V, I)]
    return pares, _meta("atenuacion", nivel, pares, sc,
                        {"ganancia_db": dB, "cual": cual, "canal": canal})


# ---------------------------------------------------------------- 4. desfase temporal
def g_desfase_temporal(sc, rng, nivel="moderado", signo=+1, **kw):
    """Desplazamiento entero de muestras (delay puro). signo +1 = retardo, -1 = adelanto."""
    ms = NIVELES["desfase_temporal"][nivel]
    d = int(round(signo * ms * 1e-3 * sc["sr"]))
    def shift(x):
        y = np.zeros_like(x)
        if d >= 0:
            y[d:] = x[:len(x) - d] if d > 0 else x
        else:
            y[:len(x) + d] = x[-d:]
        return y
    pares = [(shift(sc["V_true"]), shift(sc["I_true"]))]
    return pares, _meta("desfase_temporal", nivel, pares, sc,
                        {"ms": ms, "muestras": d, "signo": signo})


# ---------------------------------------------------------------- 5. error de fase
def g_error_fase(sc, rng, nivel="moderado", signo=+1, **kw):
    """Rotacion de fase CONSTANTE theta en todas las frecuencias (magnitud intacta).

    x_rot = Re( e^{j*theta} * Hilbert(x) )
    No es un retardo: |X_rot(w)| = |X(w)| en todas las frecuencias EXCEPTO DC y Nyquist
    (donde la proyeccion a real introduce un factor cos(theta); medido 2.8e-16 de
    desviacion relativa en el resto de las bandas). Se distingue del delay porque
    el delay introduce fase LINEAL en w; aqui la fase introducida es plana.
    """
    th = np.deg2rad(signo * NIVELES["error_fase"][nivel])
    def rot(x):
        return np.real(np.exp(1j * th) * hilbert(x, axis=0))
    pares = [(rot(sc["V_true"]), rot(sc["I_true"]))]
    m = _meta("error_fase", nivel, pares, sc, {"grados": float(np.rad2deg(th)), "signo": signo})
    m["magnitud_intacta"] = True
    return pares, m


# ---------------------------------------------------------------- 6. perdida espectral
def g_perdida_espectral(sc, rng, nivel="moderado", banda=(1000.0, 4000.0), atenuar_db=-60.0, **kw):
    """Atenua una banda en la guia. fraccion=1.0 => banda eliminada del todo."""
    frac = NIVELES["perdida_espectral"][nivel]
    g = 10 ** (atenuar_db / 20.0) if frac >= 1.0 else 1.0 - frac * (1.0 - 10 ** (atenuar_db / 20.0))
    def filtrar(x):
        X = np.fft.rfft(x, axis=0)
        f = np.fft.rfftfreq(len(x), 1.0 / sc["sr"])
        sel = (f >= banda[0]) & (f < banda[1])
        X[sel] *= g
        return np.fft.irfft(X, n=len(x), axis=0)
    pares = [(filtrar(sc["V_true"]), filtrar(sc["I_true"]))]
    return pares, _meta("perdida_espectral", nivel, pares, sc,
                        {"banda_hz": list(banda), "fraccion": frac, "ganancia_db": float(20 * np.log10(g))})


# ---------------------------------------------------------------- 7. error localizado
def g_error_localizado(sc, rng, nivel="moderado", inicio_rel=0.4, modo="sustituir_por_mix", **kw):
    """Sustituye un tramo de la guia por el Mix (o lo silencia), dejando el resto intacto."""
    dur = NIVELES["error_localizado"][nivel]
    n = len(sc["M"])
    i0 = int(inicio_rel * n)
    i1 = min(n, i0 + int(dur * sc["sr"]))
    V, I = sc["V_true"].copy(), sc["I_true"].copy()
    if modo == "sustituir_por_mix":
        V[i0:i1] = sc["M"][i0:i1]
        I[i0:i1] = sc["M"][i0:i1]
    elif modo == "silenciar":
        V[i0:i1] = 0.0
        I[i0:i1] = 0.0
    pares = [(V, I)]
    return pares, _meta("error_localizado", nivel, pares, sc,
                        {"segundos": dur, "muestras": [i0, i1], "inicio_rel": inicio_rel, "modo": modo})


# ---------------------------------------------------------------- 8. desacuerdo entre K
def _ruido(rng, forma, rms_objetivo):
    n = rng.standard_normal(forma)
    return n / (_rms(n) / max(rms_objetivo, EPS))


def g_desacuerdo(sc, rng, nivel="moderado", K=3, n_outliers=1, rho=0.0, **kw):
    """K guias con desacuerdo controlado.

    Cada guia k recibe un ruido n_k con RMS fijado por el nivel (relativo a la fuente).
    rho controla la parte COMUN del ruido:
        n_k = sqrt(rho)*c + sqrt(1-rho)*e_k
    con c comun a todas las guias y e_k independiente. rho=0 => errores independientes;
    rho->1 => el mismo error en las K guias (las K guias degeneran en una sola).
    Los `n_outliers` primeros reciben el ruido multiplicado por OUTLIER_FACTOR (>1).
    """
    dB = NIVELES["desacuerdo"][nivel]
    amp = 10 ** (dB / 20.0)
    V, I = sc["V_true"], sc["I_true"]
    forma = V.shape
    c_v = _ruido(rng, forma, _rms(V))
    c_i = _ruido(rng, forma, _rms(I))
    pares = []
    for k in range(K):
        e_v = _ruido(rng, forma, _rms(V))
        e_i = _ruido(rng, forma, _rms(I))
        nv = np.sqrt(rho) * c_v + np.sqrt(1.0 - rho) * e_v
        ni = np.sqrt(rho) * c_i + np.sqrt(1.0 - rho) * e_i
        f = 4.0 if k < n_outliers else 1.0
        # nv/ni ya tienen RMS = RMS(V)/RMS(I); amp es la razon pedida (10^(dB/20))
        pares.append((V + amp * f * nv, I + amp * f * ni))
    return pares, _meta("desacuerdo", nivel, pares, sc,
                        {"K": K, "ruido_db": dB, "rho": rho, "n_outliers": n_outliers,
                         "factor_outlier": 4.0, "semilla_rng": int(rng.integers(0, 2 ** 31))})


# ---------------------------------------------------------------- 9. asimetria estereo
def g_asimetria_estereo(sc, rng, nivel="moderado", canal=1, cual="ambas", **kw):
    """Un canal de la guia queda degradado (atenuado) y el otro intacto. Solo tiene
    sentido con senales estereo; con senales identicas L/R el efecto es el mismo que
    una atenuacion global sobre ese canal (se comprueba en la Etapa D)."""
    dB = NIVELES["asimetria_estereo"][nivel]
    g = 10 ** (dB / 20.0)
    V, I = sc["V_true"].copy(), sc["I_true"].copy()
    if cual in ("ambas", "voz"):
        V[:, canal] *= g
    if cual in ("ambas", "inst"):
        I[:, canal] *= g
    pares = [(V, I)]
    return pares, _meta("asimetria_estereo", nivel, pares, sc,
                        {"ganancia_db": dB, "canal_degradado": canal, "cual": cual})


# ---------------------------------------------------------------- 10. correlacion de errores
def g_correlacion_errores(sc, rng, nivel="moderado", K=3, **kw):
    """Variante de desacuerdo con ruido a nivel fijo y rho variable: a igual magnitud
    de error, cambia solo la estructura de correlacion. Sirve para aislar el efecto
    de la correlacion del efecto de la magnitud."""
    rho = NIVELES["correlacion_errores"][nivel]
    pares, meta = g_desacuerdo(sc, rng, nivel="moderado", K=K, n_outliers=0, rho=rho)
    meta["familia"] = "correlacion_errores"
    meta["nivel"] = nivel
    meta["parametros"]["rho"] = rho
    meta["nota"] = "magnitud de ruido fijada a moderado (-18 dB); solo cambia rho"
    return pares, meta


# ---------------------------------------------------------------- controles negativos
def c_intercambiadas(sc, rng, **kw):
    pares = [(sc["I_true"].copy(), sc["V_true"].copy())]
    return pares, _meta("control_intercambiadas", "control", pares, sc, {})


def c_duplicadas(sc, rng, K=3, **kw):
    pares = [(sc["V_true"].copy(), sc["I_true"].copy()) for _ in range(K)]
    return pares, _meta("control_duplicadas", "control", pares, sc, {"K": K,
                                                                     "identicas": True})


def c_todas_iguales_a_verdad(sc, rng, K=3, **kw):
    """K guias distintas en apariencia pero todas iguales a la verdad (control de
    'una guia repetida K veces' frente a 'K guias independientes')."""
    return c_duplicadas(sc, rng, K=K)


def c_guias_silenciosas(sc, rng, **kw):
    z = np.zeros_like(sc["V_true"])
    pares = [(z.copy(), z.copy())]
    return pares, _meta("control_guias_silenciosas", "control", pares, sc, {})


def c_inversion_polaridad(sc, rng, **kw):
    pares = [(-sc["V_true"], -sc["I_true"])]
    return pares, _meta("control_inversion_polaridad", "control", pares, sc, {})


def c_nan_inf(sc, rng, **kw):
    """Inyecta un NaN y un Inf en la guia vocal (posiciones fijas, documentadas)."""
    V, I = sc["V_true"].copy(), sc["I_true"].copy()
    V[len(V) // 3, 0] = np.nan
    V[len(V) // 2, 1] = np.inf
    pares = [(V, I)]
    m = _meta("control_nan_inf", "control", pares, sc,
              {"pos_nan": [len(V) // 3, 0], "pos_inf": [len(V) // 2, 1]})
    m["snr_guia_vocal_db"] = None      # no calculable con NaN/Inf
    m["guias_suman_mix"] = None
    return pares, m


def c_guia_corta(sc, rng, recorte_s=1.0, **kw):
    """Guias mas cortas que el Mix (recorte de cola). Prueba el manejo de longitudes."""
    k = int(min(recorte_s, 0.25 * sc["n"] / sc["sr"]) * sc["sr"])
    k = max(1, min(k, sc["n"] // 2))
    pares = [(sc["V_true"][:-k], sc["I_true"][:-k])]
    m = _meta("control_guia_corta", "control", pares, sc, {"recorte_muestras": k})
    m["snr_guia_vocal_db"] = None
    return pares, m


def c_desacuerdo_total(sc, rng, **kw):
    """K=2 con desacuerdo total: una guia afirma (V,I) y la otra (I,V)."""
    pares = [(sc["V_true"].copy(), sc["I_true"].copy()),
             (sc["I_true"].copy(), sc["V_true"].copy())]
    return pares, _meta("control_desacuerdo_total", "control", pares, sc, {"K": 2})


REGISTRO = {
    "ideal": g_ideal,
    "bleeding": g_bleeding,
    "atenuacion": g_atenuacion,
    "desfase_temporal": g_desfase_temporal,
    "error_fase": g_error_fase,
    "perdida_espectral": g_perdida_espectral,
    "error_localizado": g_error_localizado,
    "desacuerdo": g_desacuerdo,
    "asimetria_estereo": g_asimetria_estereo,
    "correlacion_errores": g_correlacion_errores,
    "control_intercambiadas": c_intercambiadas,
    "control_duplicadas": c_duplicadas,
    "control_guias_silenciosas": c_guias_silenciosas,
    "control_inversion_polaridad": c_inversion_polaridad,
    "control_nan_inf": c_nan_inf,
    "control_guia_corta": c_guia_corta,
    "control_desacuerdo_total": c_desacuerdo_total,
}


def construir(familia: str, sc: dict, rng, nivel: str | None = "moderado", **kw):
    if familia not in REGISTRO:
        raise KeyError(f"familia desconocida: {familia}")
    return REGISTRO[familia](sc, rng, nivel=nivel, **kw)
