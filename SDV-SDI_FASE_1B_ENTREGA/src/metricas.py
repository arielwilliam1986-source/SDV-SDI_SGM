"""Metricas con formula y convencion declaradas.

Todas se calculan en float64 sobre senales SIN normalizar. No se aplica ninguna
ganancia, normalizacion ni recorte antes de medir (§7 de la especificacion).

Convenios:
  * Senales: (n, canales).
  * SNR y SI-SDR se calculan por canal y luego se promedian ponderando energia;
    se informan tambien por canal separado.
  * SI-SDR usa la convencion clasica (Le Roux et al. 2019):
        alpha = <s_hat, s> / ||s||^2
        SI-SDR = 10 log10( ||alpha s||^2 / ||alpha s - s_hat||^2 )
    Es invariante a escala; por eso se informa junto a la ganancia optima alpha.
  * La fuga cruzada se mide por PROYECCION de minimos cuadrados sobre [s, x].
    Limitacion explicita: si las dos fuentes estan correlacionadas o no son
    ortogonales, la proyeccion NO separa de forma unica la energia "propia" de
    la "ajena"; se informa el residuo no explicado para que la limitacion sea
    visible.
"""
from __future__ import annotations

import numpy as np

EPS = 1e-300


def _flat(x: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64).reshape(x.shape[0], -1)


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    a, b = _flat(a), _flat(b)
    return float(np.sqrt(np.mean((a - b) ** 2)))


def max_abs(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(_flat(a) - _flat(b))))


LIMITE_CERO = 1e-20   # por debajo de esto la estimacion es indistinguible de silencio exacto


def snr_db(estimado: np.ndarray, objetivo: np.ndarray):
    """SNR de error: 10log10(||objetivo||^2 / ||estimado-objetivo||^2). NO invariante a escala.

    Devuelve None si el error es EXACTAMENTE cero (SNR infinito no es un numero) o si
    el objetivo es exactamente cero (SNR indefinido). Se prefiere None a un 999.0 falso.
    """
    e, t = _flat(estimado), _flat(objetivo)
    num = float(np.sum(t ** 2))
    den = float(np.sum((e - t) ** 2))
    if den <= LIMITE_CERO:
        return None
    if num <= LIMITE_CERO:
        return None
    return float(10 * np.log10(num / den))


def si_sdr_db(estimado: np.ndarray, objetivo: np.ndarray) -> dict:
    """SI-SDR con alpha optimo. Devuelve valor y alpha (ganancia implicita)."""
    e, t = _flat(estimado), _flat(objetivo)
    num_a = float(np.sum(e * t))
    den_a = float(np.sum(t ** 2))
    if np.sum(e ** 2) <= LIMITE_CERO:
        # estimacion = silencio exacto: SI-SDR indefinido (no 0 dB), alpha no identificable
        return {"si_sdr_db": None, "alpha": None, "degenerado": "estimado_silencio"}
    if den_a <= LIMITE_CERO:
        return {"si_sdr_db": None, "alpha": None, "degenerado": "objetivo_silencio"}
    alpha = num_a / den_a
    proj = alpha * t
    num = float(np.sum(proj ** 2))
    den = float(np.sum((proj - e) ** 2))
    if den <= LIMITE_CERO:
        return {"si_sdr_db": None, "alpha": float(alpha), "degenerado": "error_exactamente_cero"}
    return {"si_sdr_db": float(10 * np.log10(num / den)),
            "alpha": float(alpha), "degenerado": None}


def correlacion(a: np.ndarray, b: np.ndarray) -> float:
    a, b = _flat(a).ravel(), _flat(b).ravel()
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt(np.sum(a ** 2) * np.sum(b ** 2))
    return float(np.sum(a * b) / max(d, EPS))


def energia(x: np.ndarray) -> float:
    return float(np.sum(_flat(x) ** 2))


def rms_db(x: np.ndarray) -> float:
    return float(10 * np.log10(max(np.mean(_flat(x) ** 2), EPS)))


def fuga_por_proyeccion(estimado: np.ndarray, propia: np.ndarray, ajena: np.ndarray) -> dict:
    """Descompone `estimado` sobre el span {propia, ajena} por minimos cuadrados.

    Devuelve:
      coef_propia : ganancia aplicada a la fuente que deberia contener
      coef_ajena  : ganancia aplicada a la fuente que NO deberia contener
      residuo_rel : fraccion de la energia del estimado no explicada por el span
                    (si es alta, la estimacion contiene algo que no es ni V ni I,
                     y la lectura de "fuga" deja de ser interpretable)
      fuga_db     : 20log10(|coef_ajena| / |coef_propia|)  -> cuanto mas negativo, menos fuga
    """
    e = _flat(estimado).ravel()
    v = _flat(propia).ravel()
    i = _flat(ajena).ravel()
    A = np.stack([v, i], axis=1)
    coef, *_ = np.linalg.lstsq(A, e, rcond=None)
    pred = A @ coef
    resid = e - pred
    e_tot = float(np.sum(e ** 2))
    resid_rel = float(np.sum(resid ** 2) / max(e_tot, EPS))
    cp, ca = float(coef[0]), float(coef[1])
    e_prop = float(np.sum(v ** 2)); e_aje = float(np.sum(i ** 2))
    if e_aje <= 1e-20 or e_prop <= 1e-20:
        return {"coef_propia": cp, "coef_ajena": ca, "residuo_rel": resid_rel,
                "fuga_db": None, "fuga_energia_rel": None,
                "motivo": "fuente_propia_o_ajena_ausente"}
        fuga = None            # estimado nulo: la fuga relativa no esta definida
    elif abs(cp) <= 1e-12:
        fuga = None            # no hay componente propia: la razon explota, no se informa
    else:
        fuga = float(20 * np.log10(abs(ca) / abs(cp)))
    return {"coef_propia": cp, "coef_ajena": ca,
            "residuo_rel": resid_rel, "fuga_db": fuga,
            "fuga_energia_rel": float(ca ** 2 * np.sum(i ** 2) / max(e_tot, EPS))}


def reconstruccion(sdv: np.ndarray, sdi: np.ndarray, M: np.ndarray) -> dict:
    """Error de SDV_est + SDI_est frente a M. Identifica si es identidad por diseno."""
    s = _flat(sdv) + _flat(sdi)
    m = _flat(M)
    dif = s - m
    return {"rec_max_abs": float(np.max(np.abs(dif))),
            "rec_rmse": float(np.sqrt(np.mean(dif ** 2))),
            "rec_snr_db": snr_db(sdv + sdi, M),
            "rec_rms_db": rms_db(dif),
            "identidad_exacta": bool(np.all(dif == 0.0))}


def por_canal(estimado: np.ndarray, objetivo: np.ndarray) -> list:
    out = []
    for c in range(estimado.shape[1]):
        out.append({
            "canal": c,
            "rmse": rmse(estimado[:, [c]], objetivo[:, [c]]),
            "snr_db": snr_db(estimado[:, [c]], objetivo[:, [c]]),
            "si_sdr_db": si_sdr_db(estimado[:, [c]], objetivo[:, [c]])["si_sdr_db"],
            "corr": correlacion(estimado[:, [c]], objetivo[:, [c]]),
            "rms_est_db": rms_db(estimado[:, [c]]),
            "rms_obj_db": rms_db(objetivo[:, [c]]),
        })
    return out


def estereo(x: np.ndarray) -> dict:
    """Metricas estereo: balance, correlacion intercanal, diferencia lateral."""
    l, r = x[:, 0], x[:, 1]
    mid = (l + r) / 2.0
    side = (l - r) / 2.0
    el, er = float(np.sum(l ** 2)), float(np.sum(r ** 2))
    return {"balance_db": float(10 * np.log10(max(el, EPS) / max(er, EPS))),
            "corr_lr": correlacion(l, r),
            "side_energy_rel": float(np.sum(side ** 2) / max(np.sum(mid ** 2), EPS)),
            "mid_rms_db": rms_db(mid[:, None]), "side_rms_db": rms_db(side[:, None])}


def bandas(x: np.ndarray, sr: int, cortes=(125, 250, 500, 1000, 2000, 4000, 8000)) -> dict:
    """Energia relativa por banda de octava (mono downmix SOLO para este diagnostico)."""
    m = _flat(x).mean(axis=1)
    X = np.fft.rfft(m)
    f = np.fft.rfftfreq(len(m), 1.0 / sr)
    P = np.abs(X) ** 2
    tot = max(float(P.sum()), EPS)
    out = {}
    prev = 0.0
    for c in cortes:
        sel = (f >= prev) & (f < c)
        out[f"{int(prev)}-{int(c)}Hz"] = float(P[sel].sum() / tot)
        prev = c
    sel = f >= prev
    out[f">{int(prev)}Hz"] = float(P[sel].sum() / tot)
    return out


def finitud(*arrs: np.ndarray) -> dict:
    n_nan = n_inf = 0
    tot = 0
    for a in arrs:
        a = _flat(a)
        n_nan += int(np.isnan(a).sum())
        n_inf += int(np.isinf(a).sum())
        tot += a.size
    return {"n_nan": n_nan, "n_inf": n_inf, "n_total": tot,
            "todo_finito": (n_nan == 0 and n_inf == 0)}


def sanitizar(obj, contador=None):
    """Convierte NaN/+-Inf en None para que results.json sea JSON valido.

    No oculta el problema: cuenta cuantos valores no finitos habia y los deja
    accesibles en `contador` (clave 'n').
    """
    if contador is None:
        contador = {"n": 0}
    if isinstance(obj, dict):
        return {k: sanitizar(v, contador) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitizar(v, contador) for v in obj]
    if isinstance(obj, float):
        if not np.isfinite(obj):
            contador["n"] += 1
            return None
        return obj
    return obj


def resumen(estimado: np.ndarray, objetivo: np.ndarray,
            propia: np.ndarray, ajena: np.ndarray) -> dict:
    """Paquete completo de metricas de fidelidad + fuga para una salida."""
    d = {
        "rmse": rmse(estimado, objetivo),
        "max_abs": max_abs(estimado, objetivo),
        "snr_db": snr_db(estimado, objetivo),
        "corr": correlacion(estimado, objetivo),
        "rms_est_db": rms_db(estimado),
        "rms_obj_db": rms_db(objetivo),
        "pico_est": float(np.max(np.abs(estimado))),
        "pico_obj": float(np.max(np.abs(objetivo))),
    }
    d.update(si_sdr_db(estimado, objetivo))
    d["fuga"] = fuga_por_proyeccion(estimado, propia, ajena)
    d["por_canal"] = por_canal(estimado, objetivo)
    d["estereo_est"] = estereo(estimado)
    d["estereo_obj"] = estereo(objetivo)
    d["finitud"] = finitud(estimado)
    return d
