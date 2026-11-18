"""BLOQUE B — Diagnostico del verificador de alineacion.

Que hace
--------
1. Carga el modulo `MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` SOLO LECTURA (importlib)
   y usa SUS funciones y SUS constantes (`_moving_rms`, `_decimate_block_mean`,
   `_ncc_fft_coarse`, `_refine_alignment`). No se reimplementa la matematica del motor.
2. Replica el bucle de `_ncc_fft_coarse` para poder guardar la CURVA COMPLETA por lag
   (el motor solo devuelve el argmax). La replica se VERIFICA contra el motor: si el
   argmax de la curva no coincide con el que devuelve `_ncc_fft_coarse`, el caso se
   marca `REPLICA_DISCREPA` y no se usa como evidencia.
3. Barre retardos conocidos, duraciones y contenidos, y calcula FP/FN con una
   tolerancia DECLARADA ANTES DE EJECUTAR (abajo).

Tolerancia declarada antes de ejecutar (no se ajusta despues)
-------------------------------------------------------------
    ACIERTO      : |lag_est - lag_real| <= 1 muestra  (ALIGNED_TOL_SAMPLES = 1)
    FP           : lag_real == 0 y clase == MISALIGNED
    FP_SEVERO    : lag_real == 0 y |lag_est| > 10 ms  (MISALIGNED_TOL_MS = 10)
    FN           : |lag_real| > 10 ms y clase == ALIGNED
    ERROR_LAG_MS : (lag_est - lag_real)/sr*1000

No se modifica ningun audio de entrada ni la salida del motor: solo se leen senales
sinteticas propias, se desplazan (eso ES el experimento) y se mide. `--correct-alignment`
no se usa nunca. El detector NO se parchea (lo prohibe §2.8 de la especificacion).

Uso
---
    python3 src/bloque_b.py            # barrido completo
    python3 src/bloque_b.py --rapido   # subconjunto para humo
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import senales as S  # noqa: E402

RES = os.path.join(BASE, "results")
FUENTES = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"

MOTORES_ALINEACION = {
    "hardened_3.1.1": "MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py",
    "evo_3.1.1": "MOTOR_SEP_SDV-SDI_EVO.py",
}

# ---------------------------------------------------------------- configuracion
CONF = {
    "sr": 44100,
    "duraciones_s": [4.0, 10.0, 15.0, 20.0, 30.0],
    "retardos_ms": [0, 1, -1, 5, -5, 10, -10, 25, -25, 50, -50, 100, -100],
    "contenidos": ["voz_armonica", "percusivo", "percusivo_aperiodico",
                   "aire_reverb", "estereo", "silencio_inicial_final"],
    "seed": 20261117,
    "tolerancia_acierto_muestras": 1,     # ALIGNED_TOL_SAMPLES del motor
    "tolerancia_misaligned_ms": 10.0,     # MISALIGNED_TOL_MS del motor
    "umbral_empate_rel": 0.99,            # picos a >=99% del maximo = casi empatados
}


def cargar_motor(nombre):
    ruta = os.path.join(FUENTES, MOTORES_ALINEACION[nombre])
    spec = importlib.util.spec_from_file_location(f"alineacion_{nombre}", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)          # el fichero tiene guarda __main__
    return mod


# ---------------------------------------------------------------- senales
def construir_senal(contenido: str, dur: float):
    if contenido == "silencio_inicial_final":
        sc = S.escenario("voz_armonica", dur=dur, seed=CONF["seed"])
        n = sc["n"]
        k = int(0.2 * n)
        w = np.ones(n)
        w[:k] = 0.0
        w[-k:] = 0.0
        sc = dict(sc)
        sc["V_true"] = sc["V_true"] * w[:, None]
        sc["I_true"] = sc["I_true"] * w[:, None]
        sc["M"] = sc["V_true"] + sc["I_true"]
        sc["nombre"] = "silencio_inicial_final"
        return sc
    return S.escenario(contenido, dur=dur, seed=CONF["seed"])


def desplazar(x: np.ndarray, muestras: int) -> np.ndarray:
    """y[t] = x[t - muestras]. Positivo = la guia llega TARDE (retardo)."""
    if muestras == 0:
        return x.copy()
    y = np.zeros_like(x)
    if muestras > 0:
        y[muestras:] = x[:len(x) - muestras]
    else:
        y[:len(x) + muestras] = x[-muestras:]
    return y


# ---------------------------------------------------------------- curva NCC
def curva_ncc(H, env_mix, env_guide, max_lag):
    """Replica EXACTA del bucle de H._ncc_fft_coarse, VECTORIZADA, guardando todo por lag.

    Misma formula del motor:
        vals[j] = corr[k] / sqrt(energia_a_ventana * energia_b_ventana)
    con energias calculadas SOLO sobre la ventana de solape, y el mismo
    min_overlap = max(64, 0.5*min(A,B)). Solo cambia que se guarda el vector entero
    en vez de solo el argmax; el argmax se verifica contra el motor en cada caso.
    """
    a = np.asarray(env_mix, dtype=np.float64)
    b = np.asarray(env_guide, dtype=np.float64)
    A, B = len(a), len(b)
    max_lag = int(min(max_lag, min(A, B) - 1))
    n = 1
    while n < A + B:
        n <<= 1
    fa = np.fft.rfft(a, n)
    fb = np.fft.rfft(b, n)
    corr = np.fft.irfft(fa * np.conj(fb), n)
    sa2 = np.concatenate(([0.0], np.cumsum(np.square(a))))
    sb2 = np.concatenate(([0.0], np.cumsum(np.square(b))))
    lags = np.arange(-max_lag, max_lag + 1)
    min_overlap = max(64, int(0.5 * min(A, B)))

    lo_t = np.clip(lags, 0, None)
    hi_t = np.minimum(A, B + lags)
    solape = np.maximum(0, hi_t - lo_t)
    lo_b = np.clip(-lags, 0, None)
    hi_b = np.minimum(B, A - lags)
    ea = sa2[hi_t] - sa2[lo_t]
    eb = sb2[hi_b] - sb2[lo_b]
    denom = np.sqrt(np.maximum(ea, 0.0) * np.maximum(eb, 0.0))

    idx = np.where(lags >= 0, lags, n + lags)
    valido = (solape >= min_overlap) & (denom > 0)
    vals = np.full(len(lags), np.nan)
    vals[valido] = corr[idx[valido]] / denom[valido]
    return {"lags": lags, "vals": vals, "solape": solape,
            "min_overlap": min_overlap, "A": A, "B": B}


def diagnostico_curva(cur, lag_real_env: int) -> dict:
    """Metricas causales sobre la curva: donde esta el maximo, donde esta la verdad,
    cuantos picos casi empatan y con cuanto solape gana el ganador."""
    lags, vals = cur["lags"], cur["vals"]
    v = np.nan_to_num(vals, nan=-2.0)
    j_max = int(np.argmax(v))
    lag_gan = int(lags[j_max])
    # picos locales por encima del umbral de empate
    umbral = CONF["umbral_empate_rel"] * v[j_max] if v[j_max] > 0 else np.inf
    picos = []
    for j in range(1, len(v) - 1):
        if v[j] >= umbral and v[j] >= v[j - 1] and v[j] >= v[j + 1]:
            picos.append(int(lags[j]))
    j_real = int(np.where(lags == lag_real_env)[0][0]) if lag_real_env in lags else None
    ncc_real = float(vals[j_real]) if j_real is not None else None
    # curva restringida a solape alto (>=90% del maximo): alternativa propuesta
    sol = cur["solape"]
    mask_alto = sol >= 0.9 * sol.max()
    j_alto = int(np.argmax(np.where(mask_alto, v, -2.0)))
    return {
        "lag_ganador_env": lag_gan,
        "ncc_max": float(v[j_max]),
        "solape_ganador": int(sol[j_max]),
        "solape_max": int(sol.max()),
        "ncc_en_lag_real": ncc_real,
        "ratio_real_vs_max": (None if ncc_real is None or v[j_max] == 0
                              else float(ncc_real / v[j_max])),
        "n_picos_casi_empatados": len(picos),
        "picos_casi_empatados_env": picos[:12],
        "lag_ganador_con_solape_alto_env": int(lags[j_alto]),
    }


def evaluar_caso(H, sc, retardo_ms: float, guardar_curva=False) -> dict:
    sr = sc["sr"]
    d = int(round(retardo_ms * 1e-3 * sr))
    guia = desplazar(sc["V_true"], d)          # la guia vocal llega desplazada
    mix_mono = H.mono_downmix(sc["M"])
    guia_mono = H.mono_downmix(guia)

    win_env = int(H.ALIGN_ENVELOPE_MS * 1e-3 * sr)
    decim = H.ALIGN_COARSE_DECIMATION
    env_mix = H._decimate_block_mean(H._moving_rms(mix_mono, win_env), decim)
    env_g = H._decimate_block_mean(H._moving_rms(guia_mono, win_env), decim)
    max_lag_env = int(H.ALIGN_SEARCH_SECONDS * sr / decim)

    # 1) veredicto del motor (su propia funcion)
    lag_motor, val_motor = H._ncc_fft_coarse(env_mix, env_g, max_lag_env)
    # 2) replica con curva completa
    cur = curva_ncc(H, env_mix, env_g, max_lag_env)
    # CONVENCION DEL MOTOR: el lag que devuelve es el indice k de
    #     corr[k] = sum_t env_mix[t] * env_guide[t-k]
    # Para una guia retardada d muestras el maximo cae en k = -d. Por eso el valor
    # esperado es -d y NO +d. (Verificado en este bloque, no asumido.)
    lag_esperado_env = int(round(-d / decim))
    diag = diagnostico_curva(cur, lag_esperado_env)
    replica_ok = (diag["lag_ganador_env"] == int(lag_motor))

    coarse_samples = int(lag_motor) * decim
    half = max(H.ALIGN_REFINE_HALFSPAN, decim + 2)
    best_lag, peak_val, sub = H._refine_alignment(mix_mono, guia_mono, coarse_samples, half)
    est_muestras = float(sub)
    err_muestras = est_muestras - (-d)      # esperado = -d, ver nota de convencion
    off_ms = 1000.0 * est_muestras / sr
    abs_off = abs(int(round(est_muestras)))
    if abs_off <= H.ALIGNED_TOL_SAMPLES:
        clase = "ALIGNED"
    elif abs_off <= int(CONF["tolerancia_misaligned_ms"] * 1e-3 * sr):
        clase = "WARNING"
    else:
        clase = "MISALIGNED"

    real_abs_ms = abs(retardo_ms)
    if real_abs_ms == 0:
        fp = (clase == "MISALIGNED")
        fn = None
    elif real_abs_ms > CONF["tolerancia_misaligned_ms"]:
        fp = None
        fn = (clase == "ALIGNED")
    else:
        fp = fn = None
    acierto = abs(err_muestras) <= CONF["tolerancia_acierto_muestras"]

    out = {
        "motor": H.__name__, "contenido": sc["nombre"], "dur_s": sc["n"] / sr,
        "retardo_real_ms": float(retardo_ms), "retardo_real_muestras": int(d),
        "lag_esperado_muestras": int(-d),
        "lag_motor_env": int(lag_motor), "val_motor": float(val_motor),
        "replica_coincide": bool(replica_ok),
        "lag_estimado_muestras": est_muestras, "lag_estimado_ms": off_ms,
        "error_muestras": err_muestras, "error_ms": 1000.0 * err_muestras / sr,
        "clase": clase, "acierto_1muestra": bool(acierto),
        "falso_positivo": fp, "falso_negativo": fn,
        "peak_pearson_refinado": float(peak_val),
        "ncc_ventana_env_muestras": win_env, "decimacion": decim,
        "max_lag_env": max_lag_env, "longitud_env": int(len(env_mix)),
        "min_overlap_env": cur["min_overlap"],
        **{k: v for k, v in diag.items()},
    }
    if guardar_curva:
        out["_curva"] = {"lags": cur["lags"].tolist(), "vals": cur["vals"].tolist(),
                         "solape": cur["solape"].tolist()}
    return out


# ---------------------------------------------------------------- caso especial L/R
def caso_lr_asimetrico(H, dur=20.0) -> dict:
    """Retardo DISTINTO por canal (+10 ms en L, -10 ms en R).

    El motor decide sobre un downmix mono. Aqui se mide: (a) su veredicto sobre el
    downmix; (b) la curva por canal, para mostrar que un desfase simetrico opuesto
    se cancela en el downmix. NO se usa el mono para el resultado principal: se
    informan las tres cosas.
    """
    sc = S.escenario("estereo", dur=dur, seed=CONF["seed"])
    sr = sc["sr"]
    dL = int(round(10e-3 * sr))
    dR = int(round(-10e-3 * sr))
    guia = np.stack([desplazar(sc["V_true"][:, [0]], dL)[:, 0],
                     desplazar(sc["V_true"][:, [1]], dR)[:, 0]], axis=1)
    mix_mono = H.mono_downmix(sc["M"])
    guia_mono = H.mono_downmix(guia)
    win_env = int(H.ALIGN_ENVELOPE_MS * 1e-3 * sr)
    decim = H.ALIGN_COARSE_DECIMATION
    env_mix = H._decimate_block_mean(H._moving_rms(mix_mono, win_env), decim)
    env_g = H._decimate_block_mean(H._moving_rms(guia_mono, win_env), decim)
    lag_motor, val_motor = H._ncc_fft_coarse(env_mix, env_g,
                                             int(H.ALIGN_SEARCH_SECONDS * sr / decim))
    por_canal = {}
    for c, nombre in ((0, "L"), (1, "R")):
        e_m = H._decimate_block_mean(H._moving_rms(sc["M"][:, c], win_env), decim)
        e_g = H._decimate_block_mean(H._moving_rms(guia[:, c], win_env), decim)
        lagc, valc = H._ncc_fft_coarse(e_m, e_g, int(H.ALIGN_SEARCH_SECONDS * sr / decim))
        por_canal[nombre] = {"lag_env": int(lagc), "lag_ms": lagc * decim / sr * 1000.0,
                             "ncc": float(valc), "retardo_real_ms": 10.0 if c == 0 else -10.0}
    return {"caso": "L/R asimetrico (+10 ms L, -10 ms R)", "dur_s": dur,
            "veredicto_sobre_downmix_mono": {"lag_env": int(lag_motor),
                                             "lag_ms": lag_motor * decim / sr * 1000.0,
                                             "ncc": float(val_motor)},
            "por_canal_sin_downmix": por_canal,
            "nota": ("el motor decide sobre downmix mono; los desfases opuestos de "
                     "igual magnitud se restan en el downmix")}


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    args = ap.parse_args()
    os.makedirs(RES, exist_ok=True)

    conf = dict(CONF)
    if args.rapido:
        conf["duraciones_s"] = [4.0, 20.0]
        conf["contenidos"] = ["voz_armonica", "percusivo"]
        conf["retardos_ms"] = [0, 25, -25]

    # Memoria: el entorno tiene ~1,5 GB. Se mantiene UNA sola senal viva por vez y se
    # libera antes de construir la siguiente (retener las 30 provocaba OOM, exit 137).
    MODS = {n: cargar_motor(n) for n in MOTORES_ALINEACION}
    for n, H in MODS.items():
        print(f"motor {n}: ALIGN_SEARCH_SECONDS={H.ALIGN_SEARCH_SECONDS}, "
              f"DECIM={H.ALIGN_COARSE_DECIMATION}, ENV_MS={H.ALIGN_ENVELOPE_MS}, "
              f"TOL_SAMPLES={H.ALIGNED_TOL_SAMPLES}, MISALIGNED_TOL_MS={H.MISALIGNED_TOL_MS}")

    filas = []
    curvas = {}
    for contenido in conf["contenidos"]:
        for dur in conf["duraciones_s"]:
            sc = construir_senal(contenido, dur)
            for nombre_motor, H in MODS.items():
                n_ok = 0
                for ret in conf["retardos_ms"]:
                    guardar = (ret == 0 and dur in (4.0, 30.0))
                    r = evaluar_caso(H, sc, ret, guardar_curva=guardar)
                    r["motor"] = nombre_motor
                    if guardar:
                        curvas[f"{nombre_motor}|{contenido}|{dur:g}s|d{ret}"] = r.pop("_curva")
                    else:
                        r.pop("_curva", None)
                    filas.append(r)
                    n_ok += 1 if r["acierto_1muestra"] else 0
                    if not r["replica_coincide"]:
                        print(f"  [REPLICA_DISCREPA] {contenido} {dur:g}s d={ret:+.0f}ms")
                print(f"  {nombre_motor:<14} {contenido:<23} {dur:>4.0f}s  "
                      f"|err|<=1 muestra: {n_ok}/{len(conf['retardos_ms'])}  "
                      f"(acum {len(filas)})", flush=True)
            del sc

    # ---- CSV crudo
    campos = [k for k in filas[0] if not k.startswith("_")]
    with open(os.path.join(RES, "alineacion_casos.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for f in filas:
            w.writerow({k: (repr(f[k]) if isinstance(f[k], float) else f[k])
                        for k in campos})

    # ---- matriz de confusion: retardo real x duracion, por contenido y motor
    matriz = []
    for motor in MOTORES_ALINEACION:
        for contenido in conf["contenidos"]:
            for ret in conf["retardos_ms"]:
                fs = [f for f in filas if f["motor"] == motor
                      and f["contenido"] == contenido and f["retardo_real_ms"] == ret]
                if not fs:
                    continue
                aciertos = sum(1 for f in fs if f["acierto_1muestra"])
                fps = sum(1 for f in fs if f["falso_positivo"])
                fns = sum(1 for f in fs if f["falso_negativo"])
                err = [abs(f["error_ms"]) for f in fs]
                matriz.append({
                    "motor": motor, "contenido": contenido,
                    "retardo_real_ms": ret, "n_duraciones": len(fs),
                    "aciertos_1muestra": aciertos,
                    "falsos_positivos": fps, "falsos_negativos": fns,
                    "error_medio_ms": float(np.mean(err)),
                    "error_max_ms": float(np.max(err)),
                    "clases": "/".join(sorted({f["clase"] for f in fs})),
                })
    with open(os.path.join(RES, "alineacion_matriz.csv"), "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(matriz[0]))
        w.writeheader()
        for m in matriz:
            w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in m.items()})

    # ---- caso L/R asimetrico
    lr = {m: caso_lr_asimetrico(cargar_motor(m)) for m in MOTORES_ALINEACION}
    with open(os.path.join(RES, "alineacion_lr_asimetrico.json"), "w",
              encoding="utf-8") as fh:
        json.dump(lr, fh, indent=1, ensure_ascii=False)

    # ---- curvas representativas
    with open(os.path.join(RES, "alineacion_curvas.json"), "w", encoding="utf-8") as fh:
        json.dump(curvas, fh)

    # ---- resumen por consola
    total = len(filas)
    rep = sum(1 for f in filas if not f["replica_coincide"])
    fps = sum(1 for f in filas if f["falso_positivo"])
    fns = sum(1 for f in filas if f["falso_negativo"])
    cero = [f for f in filas if f["retardo_real_ms"] == 0]
    cero_mal = sum(1 for f in cero if f["clase"] == "MISALIGNED")
    print(f"\n=== RESUMEN B ===")
    print(f"casos: {total}  | replica disiente del motor: {rep}")
    print(f"retardo real 0: {len(cero)} casos, {cero_mal} declarados MISALIGNED "
          f"({100.0*cero_mal/max(len(cero),1):.1f}%)")
    print(f"falsos positivos: {fps}  | falsos negativos: {fns}")
    print(f"aciertos |error|<=1 muestra: {sum(1 for f in filas if f['acierto_1muestra'])}/{total}")
    print(f"escrito: results/alineacion_casos.csv, alineacion_matriz.csv, "
          f"alineacion_curvas.json, alineacion_lr_asimetrico.json")
    return 0 if rep == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
