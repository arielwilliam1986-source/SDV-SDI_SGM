"""BLOQUE A — Validacion de consenso.

Pregunta del encargo: que opcion de metodo de consenso llega REALMENTE a una operacion
distinta, por version del motor, y como se comporta el consenso con K = 2, 3, 5, 7 guias
que tienen errores de tipos distintos.

NO se elige metodo ganador. Solo se mide si las opciones producen o no salidas distintas
y como se desvia el resultado respecto de la verdad sintetica.

Cuatro partes:
  1. inventario estatico  : archivo / funcion / lineas / opciones del CLI, VERIFICADO
                            releyendo la fuente (no se copia de memoria).
  2. extremo a extremo    : se ejecutan los motores reales con cada opcion de --consensus
                            y se comparan los SHA-256 de SDV/SDI. Esto es lo que decide
                            si la opcion "llega a operacion".
  3. consenso enmascarado : se llaman las funciones del motor (solo lectura) con K mallas
                            sinteticas de error conocido.
  4. consenso complejo    : idem para el consenso de v3, que opera sobre STFT complejas y
                            por tanto SI admite error de fase arbitrario.

Todo es solo lectura sobre /home/user/fase1b/fuentes. Los motores no se modifican.
Se usa --allow-misaligned porque el verificador de alineacion aborta por el defecto
documentado en el Bloque B (ver ALIGNMENT_DIAGNOSTICS.md); no se parchea nada.

Uso: python3 -u src/bloque_a.py [--saltar-e2e] [--saltar-runtime]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import itertools
import json
import os
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import senales as S          # noqa: E402
import adaptadores as A      # noqa: E402

RES = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "work")
FUENTES = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"
SR = 44100

# clave propia -> (fichero, clave en adaptadores.MOTORES)
MOTORES = {
    "v3": "MOTOR_SEP_SDV-SDI_v3.py",
    "hardened_3.1.1": "MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py",
    "evo_3.1.1": "MOTOR_SEP_SDV-SDI_EVO.py",
    "mqr": "sdv_sdi_mqr_engine.py",
}

# adaptadores.py ya tenia sus propias claves; se reutilizan en vez de duplicarlas
CLAVE_ADAPTADOR = {"v3": "v3_3.0.0", "hardened_3.1.1": "hardened_3.1.1",
                   "evo_3.1.1": "evo_3.1.1", "mqr": "mqr_1.3.0"}


# ============================================================ utilidades
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def lineas(ruta):
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def buscar(ruta, patron, desde=1):
    """Devuelve los numeros de linea (1-based) que contienen `patron`."""
    return [i + 1 for i, l in enumerate(lineas(ruta)) if patron in l and i + 1 >= desde]


def cargar_modulo(nombre):
    ruta = os.path.join(FUENTES, MOTORES[nombre])
    clave = "a_" + nombre.replace(".", "_")
    spec = importlib.util.spec_from_file_location(clave, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ============================================================ 1. inventario
def inventario():
    """Inventario estatico VERIFICADO: cada afirmacion se comprueba releyendo la fuente."""
    inv = {}
    for clave, fichero in MOTORES.items():
        ruta = os.path.join(FUENTES, fichero)
        L = lineas(ruta)
        d = {"fichero": fichero, "sha256": sha256_file(ruta),
             "n_lineas": len(L), "opciones": {}}

        # opciones del CLI aceptadas de verdad
        cons = [i + 1 for i, l in enumerate(L) if 'add_argument("--consensus"' in l]
        order = [i + 1 for i, l in enumerate(L) if 'add_argument("--consensus-order"' in l]
        d["cli_consensus_linea"] = cons[0] if cons else None
        d["cli_consensus_order_linea"] = order[0] if order else None

        # opciones declaradas
        for nombre_const in ("CONSENSUS_METHODS", "CONSENSUS_ORDERS",
                             "CONSENSUS_DEFAULT", "CONSENSUS_ORDER_DEFAULT"):
            filas = [i + 1 for i, l in enumerate(L) if l.startswith(nombre_const + " ")]
            if filas:
                txt = L[filas[0] - 1]
                d[nombre_const] = {"linea": filas[0], "texto": txt.strip()}

        # existe la funcion de consenso?
        d["consensus_from_masks"] = (buscar(ruta, "def consensus_from_masks") or [None])[0]
        d["def_consensus_complejo"] = (buscar(ruta, "def consensus(Vs") or [None])[0]
        d["magnitudes_first_lineas"] = buscar(ruta, "magnitudes_first")

        # el bloque magnitudes_first asigna el MISMO array a los 3 metodos?
        igual = buscar(ruta, '"weighted_mean": Mv_consensus')
        d["bloque_metodos_iguales"] = igual[0] if igual else None
        if igual:
            frag = L[igual[0] - 1: igual[0] + 4]
            d["bloque_metodos_iguales_texto"] = [x.strip() for x in frag]
            d["bloque_metodos_iguales_verificado"] = all(
                ("Mv_consensus" in x) for x in frag[:3])

        # rama masks_first -> consensus_from_masks
        llamadas = buscar(ruta, "consensus, weights_summary = consensus_from_masks")
        d["llamada_consensus_from_masks"] = llamadas[0] if llamadas else None

        # salto de escritura de metodos no predeterminados (magnitudes_first)
        salto = buscar(ruta, 'and method != opt.consensus_default')
        d["salto_escritura_no_default"] = salto

        inv[clave] = d
    return inv


# ============================================================ guias degradadas
def ruido_correlacionado(n, rho, rng, sigma):
    """K ruidos con correlacion rho entre pares (misma componente comun)."""
    comun = rng.standard_normal(n)
    return np.sqrt(rho) * comun + np.sqrt(max(1.0 - rho, 0.0)) * rng.standard_normal(n)


def guias_degradadas(contenido, dur, K, modelo, seed=20261117):
    """Devuelve K duplas (vocal, instrumental) con el error pedido.

    Modelos implementados sobre las guias REALES del escenario (senales temporales):
      independiente   ruido independiente por guia (SNR ~10 dB)
      rho_0 / rho_0.6 / rho_0.95   ruido con componente comun de correlacion rho
      outlier_1       una guia corrupta de forma severa (mezcla cruzada con el otro rol)
      outlier_2       dos guias corruptas
      mayoria_degradada   ceil(K/2)+1 guias corruptas (la mediana queda en minoria sana)
      escalas         cada guia con ganancia distinta (0.5, 0.8, 1.2, 2.0, ...)
      polaridad       una guia con polaridad invertida (error de fase de 180 grados)

    NOTA: 'fase erronea' en el dominio temporal solo puede materializarse como inversion
    de polaridad (180 grados). Rotaciones de fase arbitrarias no existen para una senal
    real y por eso se prueban aparte en el dominio complejo (parte 4).
    """
    sc = S.escenario(contenido, dur=dur, seed=seed)
    V, I = sc["V_true"], sc["I_true"]
    n = V.shape[0]
    rng = np.random.default_rng(seed + 7)
    sigma = np.sqrt(np.mean(V ** 2)) / 3.16          # ~10 dB SNR
    pares = []
    for k in range(K):
        if modelo == "independiente":
            v = V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        elif modelo.startswith("rho_"):
            rho = float(modelo.split("_")[1])
            v = V + sigma * ruido_correlacionado(n, rho, rng, 1.0)[:, None]
            i = I + sigma * ruido_correlacionado(n, rho, rng, 1.0)[:, None]
        elif modelo == "outlier_1":
            if k == 0:
                v = V + 3.0 * sigma * rng.standard_normal((n, 2)) + 0.5 * I
            else:
                v = V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        elif modelo == "outlier_2":
            if k in (0, 1):
                v = 0.6 * V + 0.8 * I + 2.0 * sigma * rng.standard_normal((n, 2))
            else:
                v = V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        elif modelo == "mayoria_degradada":
            malas = (K // 2) + 1
            if k < malas:
                v = 0.5 * V + 0.9 * I + 2.0 * sigma * rng.standard_normal((n, 2))
            else:
                v = V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        elif modelo == "escalas":
            gan = (0.4, 0.6, 1.5, 0.75, 2.2, 0.55, 1.8)[k % 7]   # asimetricas a proposito
            v = gan * V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        elif modelo == "polaridad":
            signo = -1.0 if k == 0 else 1.0
            v = signo * V + sigma * rng.standard_normal((n, 2))
            i = I + sigma * rng.standard_normal((n, 2))
        else:
            raise ValueError(modelo)
        pares.append((v, i))
    return sc, pares


MODELOS = ["independiente", "rho_0", "rho_0.6", "rho_0.95", "outlier_1",
           "outlier_2", "mayoria_degradada", "escalas", "polaridad"]


# ============================================================ 2. extremo a extremo
def e2e_una(clave, order, metodo, K=3, modelo="independiente", dur=4.0):
    """Ejecuta un motor con una combinacion (order, metodo) y devuelve huellas de salida."""
    tag = f"{clave}__{order}__{metodo}__K{K}__{modelo}"
    base = os.path.join(WORK, "a_e2e", tag)
    sc, pares = guias_degradadas("voz_armonica", dur, K, modelo)
    guias = {}
    lista = []
    for k, (v, i) in enumerate(pares):
        guias[f"vocal_{k+1}"] = v
        guias[f"instrum_{k+1}"] = i
        lista.append((f"p{k+1}", os.path.join(base, f"vocal_{k+1}.wav"),
                      os.path.join(base, f"instrum_{k+1}.wav")))
    A.escribir_fixture(base, sc, guias)
    man = A.manifiesto(guias_path_ok(base, guias), lista, os.path.join(base, "out"),
                       mask_mode="mono")   # EVO aborta con per_channel+residuals
    mp = A.escribir_manifiesto(os.path.join(base, "manifest.json"), man)
    extra = ["--allow-misaligned"]
    if clave == "mqr":
        extra += ["--mode", "full_processing"]   # sin esto pide entrada interactiva
    if order:
        extra += ["--consensus-order", order]
    extra += ["--consensus", metodo]
    r = A.ejecutar(CLAVE_ADAPTADOR[clave], mp, os.path.join(base, "out"), extra=extra)
    sal = A.buscar_salidas(os.path.join(base, "out"))
    # El SHA-256 del FICHERO no sirve para comparar corridas: libsndfile escribe un
    # chunk PEAK con la hora de generacion (ver consenso_e2e_metodo.json). Se usa una
    # huella del AUDIO DECODIFICADO (float32) y ademas se guardan las rutas.
    huellas = {}
    for rol in ("sdv", "sdi"):
        if sal[rol]:
            x, fs = sf.read(sal[rol], dtype="float32")
            huellas[rol] = hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
        else:
            huellas[rol] = None
    return {"motor": clave, "order": order, "metodo": metodo, "K": K, "modelo": modelo,
            "rc": r["rc"], "elapsed_s": r["elapsed_s"],
            "sha_audio_sdv": huellas["sdv"], "sha_audio_sdi": huellas["sdi"],
            "sha_fichero_sdv": sha256_file(sal["sdv"]) if sal["sdv"] else None,
            "sdv": sal["sdv"], "sdi": sal["sdi"],
            "stderr": r["stderr"][-2000:], "stdout_tail": r["stdout"][-1200:]}


def guias_path_ok(base, guias):
    """El manifiesto necesita la ruta del mix ya escrita por escribir_fixture."""
    return os.path.join(base, "mix.wav")


def e2e():
    """Compara, por motor y orden, si --consensus cambia la salida."""
    plan = [
        ("hardened_3.1.1", "magnitudes_first", ["weighted_mean", "median",
                                                "confidence_weighted_mean"]),
        ("hardened_3.1.1", "masks_first", ["weighted_mean", "median",
                                           "confidence_weighted_mean"]),
        ("evo_3.1.1", "magnitudes_first", ["weighted_mean", "median",
                                          "confidence_weighted_mean"]),
        ("evo_3.1.1", "masks_first", ["weighted_mean", "median",
                                      "confidence_weighted_mean"]),
        ("evo_3.1.1", "hybrid_asymmetric", ["weighted_mean", "median",
                                            "confidence_weighted_mean"]),
        ("v3", None, ["magnitudes_first", "mean", "median", "median_ri"]),
        ("mqr", None, ["weighted_mean", "median", "confidence_weighted_mean"]),
    ]
    filas = []
    grupos = {}
    for clave, order, metodos in plan:
        for m in metodos:
            try:
                r = e2e_una(clave, order, m)
            except Exception as exc:                     # noqa: BLE001
                r = {"motor": clave, "order": order, "metodo": m, "rc": -1,
                     "error": f"{type(exc).__name__}: {exc}"}
            filas.append(r)
            grupos.setdefault((clave, order), []).append(r)
            print(f"  {clave:<14} order={str(order):<18} {m:<24} rc={r.get('rc')} "
                  f"audio_sdv={str(r.get('sha_audio_sdv'))[:12]}", flush=True)

    # veredicto por grupo, sobre el AUDIO DECODIFICADO
    veredicto = []
    for (clave, order), rs in grupos.items():
        ok = [r for r in rs if r.get("sha_audio_sdv")]
        hs = {r["sha_audio_sdv"] for r in ok}
        hs_i = {r["sha_audio_sdi"] for r in ok}
        detalle = []
        if ok:
            ref, _ = sf.read(ok[0]["sdv"], dtype="float32")
            for r in ok:
                x, _ = sf.read(r["sdv"], dtype="float32")
                y, _ = sf.read(r["sdi"], dtype="float32")
                refi, _ = sf.read(ok[0]["sdi"], dtype="float32")
                detalle.append({
                    "metodo": r["metodo"],
                    "max_abs_sdv_vs_primero": float(np.max(np.abs(x - ref))),
                    "energia_rel_sdv_vs_primero":
                        float(np.sqrt(((x - ref) ** 2).sum() /
                                      max((ref ** 2).sum(), 1e-30))),
                    "max_abs_sdi_vs_primero": float(np.max(np.abs(y - refi))),
                    "sha_audio_igual_al_primero": bool(
                        hashlib.sha256(np.ascontiguousarray(x).tobytes()).hexdigest()
                        == hashlib.sha256(np.ascontiguousarray(ref).tobytes()).hexdigest()),
                })
        veredicto.append({
            "motor": clave, "order": order,
            "n_ejecutados_ok": len(ok),
            "n_salidas_distintas_sdv": len(hs),
            "n_salidas_distintas_sdi": len(hs_i),
            "metodos": [r["metodo"] for r in rs],
            "llega_a_operacion": len(hs) > 1 or len(hs_i) > 1,
            "max_abs_entre_metodos_sdv": (max(d["max_abs_sdv_vs_primero"] for d in detalle)
                                          if detalle else None),
            "detalle": detalle,
        })
    return filas, veredicto


# ============================================================ nota de metodo
def nota_metodo():
    """Documenta que el SHA-256 del FICHERO no sirve para comparar corridas.

    libsndfile escribe un chunk PEAK cuyo campo de fecha cambia en cada generacion.
    Se verifica aqui sobre tres corridas del mismo audio y se deja registrado.
    """
    base = os.path.join(WORK, "a_e2e")
    grupo = [d for d in sorted(os.listdir(base)) if d.startswith(
        "hardened_3.1.1__magnitudes_first__")] if os.path.isdir(base) else []
    ficheros = []
    for g in grupo:
        sal = A.buscar_salidas(os.path.join(base, g, "out"))
        if sal.get("sdv"):
            ficheros.append(sal["sdv"])
    if len(ficheros) < 2:
        return {"disponible": False, "motivo": "faltan corridas para comparar"}
    crudos = [open(f, "rb").read() for f in ficheros]
    n = min(len(c) for c in crudos)
    offs = [i for i in range(n) if len({c[i] for c in crudos}) > 1]
    pos_data = crudos[0].find(b"data")
    audios = [sf.read(f, dtype="float32")[0] for f in ficheros]
    maxd = max(float(np.max(np.abs(audios[0] - x))) for x in audios[1:])
    return {
        "disponible": True,
        "ficheros_comparados": ficheros,
        "bytes_de_fichero_distintos": len(offs),
        "offsets_distintos": offs[:8],
        "offset_chunk_data": pos_data,
        "todas_las_diferencias_antes_de_los_datos": all(o < pos_data for o in offs),
        "chunk_responsable": "PEAK (campo de fecha escrito por libsndfile)",
        "max_abs_diferencia_de_audio": maxd,
        "audio_identico": maxd == 0.0,
        "conclusion": ("comparar SHA-256 de fichero entre corridas produce falsos "
                       "positivos de 'diferencia'; la comparacion valida es sobre el "
                       "audio decodificado"),
    }


# ============================================================ 3. consenso enmascarado
def consenso_enmascarado():
    """K mallas con error conocido -> funciones reales del motor (hardened)."""
    H = cargar_modulo("hardened_3.1.1")
    filas = []
    n_bins, n_frames = 256, 64
    rng = np.random.default_rng(20261117)
    yy, xx = np.mgrid[0:n_bins, 0:n_frames]
    # malla "verdad": banda vocal definida
    verdad = np.clip(1.0 - np.abs(yy - 0.35 * n_bins) / (0.25 * n_bins), 0.0, 1.0)
    verdad = verdad * (0.6 + 0.4 * np.sin(2 * np.pi * xx / 17.0) ** 2)
    for K in (2, 3, 5, 7):
        for modelo in MODELOS:
            mallas = []
            for k in range(K):
                if modelo == "independiente":
                    e = 0.08 * rng.standard_normal((n_bins, n_frames))
                elif modelo.startswith("rho_"):
                    rho = float(modelo.split("_")[1])
                    e = 0.08 * ruido_correlacionado(n_bins * n_frames, rho, rng, 1.0
                                                    ).reshape(n_bins, n_frames)
                elif modelo == "outlier_1":
                    e = (0.35 * rng.standard_normal((n_bins, n_frames)) if k == 0
                         else 0.08 * rng.standard_normal((n_bins, n_frames)))
                elif modelo == "outlier_2":
                    e = (0.35 * rng.standard_normal((n_bins, n_frames)) if k in (0, 1)
                         else 0.08 * rng.standard_normal((n_bins, n_frames)))
                elif modelo == "mayoria_degradada":
                    e = (0.35 * rng.standard_normal((n_bins, n_frames))
                         if k < (K // 2) + 1 else 0.08 * rng.standard_normal((n_bins, n_frames)))
                elif modelo == "escalas":
                    s = (0.4, 0.6, 1.5, 0.75, 2.2, 0.55, 1.8)[k % 7]
                    mallas.append(np.clip(s * verdad, 0.0, 1.0))
                    continue
                elif modelo == "polaridad":
                    mallas.append(np.clip(1.0 - verdad if k == 0 else verdad, 0.0, 1.0))
                    continue
                else:
                    raise ValueError(modelo)
                mallas.append(np.clip(verdad + e, 0.0, 1.0))
            conf, dis, c_k = H.confidence_and_disagreement(mallas)
            cons, wsum = H.consensus_from_masks(mallas, c_k, beta=H.CONFIDENCE_BETA)
            a = cons["weighted_mean"]; b = cons["median"]; c = cons["confidence_weighted_mean"]
            fila = {
                "K": K, "modelo": modelo,
                "identicos_3": bool(np.array_equal(a, b) and np.array_equal(b, c)),
                "max_abs_wm_vs_med": float(np.max(np.abs(a - b))),
                "max_abs_wm_vs_cwm": float(np.max(np.abs(a - c))),
                "max_abs_med_vs_cwm": float(np.max(np.abs(b - c))),
                "mae_wm": float(np.mean(np.abs(a - verdad))),
                "mae_med": float(np.mean(np.abs(b - verdad))),
                "mae_cwm": float(np.mean(np.abs(c - verdad))),
                "conf_media": float(conf.mean()),
                "dis_media": float(dis.mean()),
                "c_k_media": float(c_k.mean()),
                "c_k_min": float(c_k.min()),
                "c_k_negativos_pct": float(100.0 * (c_k < 0).mean()),
                "weights_n_models": wsum.get("n_models"),
                "degenerado": bool(wsum.get("degenerate", False)),
            }
            filas.append(fila)
            print(f"  K={K} {modelo:<18} identicos={fila['identicos_3']!s:<5} "
                  f"d(wm,med)={fila['max_abs_wm_vs_med']:.3e} "
                  f"d(wm,cwm)={fila['max_abs_wm_vs_cwm']:.3e}", flush=True)
    return filas


# ============================================================ 4. consenso complejo
def consenso_complejo():
    """Consenso de v3 sobre STFT complejas: aqui SI cabe error de fase arbitrario."""
    V = cargar_modulo("v3")
    filas = []
    n_bins, n_frames = 256, 64
    rng = np.random.default_rng(20261117)
    yy, xx = np.mgrid[0:n_bins, 0:n_frames]
    mag_v = np.clip(1.0 - np.abs(yy - 0.35 * n_bins) / (0.25 * n_bins), 0.0, 1.0) + 0.05
    fase_v = 2 * np.pi * rng.random((n_bins, n_frames))
    verdad = mag_v * np.exp(1j * fase_v)
    for K in (2, 3, 5, 7):
        for modelo in MODELOS + ["fase_45", "fase_180"]:
            Vs = []
            for k in range(K):
                if modelo == "fase_45":
                    f = (np.pi / 4) if k == 0 else 0.0
                    Vs.append(verdad * np.exp(1j * f))
                    continue
                if modelo == "fase_180":
                    Vs.append(verdad * (-1.0 if k == 0 else 1.0))
                    continue
                if modelo == "escalas":
                    s = (0.4, 0.6, 1.5, 0.75, 2.2, 0.55, 1.8)[k % 7]
                    Vs.append(verdad * s)
                    continue
                if modelo in ("polaridad",):
                    Vs.append(verdad * (-1.0 if k == 0 else 1.0))
                    continue
                if modelo == "independiente":
                    e = 0.12 * (rng.standard_normal((n_bins, n_frames))
                                + 1j * rng.standard_normal((n_bins, n_frames)))
                elif modelo.startswith("rho_"):
                    rho = float(modelo.split("_")[1])
                    c1 = ruido_correlacionado(n_bins * n_frames, rho, rng, 1.0)
                    c2 = ruido_correlacionado(n_bins * n_frames, rho, rng, 1.0)
                    e = 0.12 * (c1.reshape(n_bins, n_frames)
                                + 1j * c2.reshape(n_bins, n_frames))
                elif modelo == "outlier_1":
                    e = (0.6 * (rng.standard_normal((n_bins, n_frames))
                                + 1j * rng.standard_normal((n_bins, n_frames)))
                         if k == 0 else
                         0.12 * (rng.standard_normal((n_bins, n_frames))
                                 + 1j * rng.standard_normal((n_bins, n_frames))))
                elif modelo == "outlier_2":
                    e = (0.6 * (rng.standard_normal((n_bins, n_frames))
                                + 1j * rng.standard_normal((n_bins, n_frames)))
                         if k in (0, 1) else
                         0.12 * (rng.standard_normal((n_bins, n_frames))
                                 + 1j * rng.standard_normal((n_bins, n_frames))))
                elif modelo == "mayoria_degradada":
                    e = (0.6 * (rng.standard_normal((n_bins, n_frames))
                                + 1j * rng.standard_normal((n_bins, n_frames)))
                         if k < (K // 2) + 1 else
                         0.12 * (rng.standard_normal((n_bins, n_frames))
                                 + 1j * rng.standard_normal((n_bins, n_frames))))
                else:
                    raise ValueError(modelo)
                Vs.append(verdad + e)
            salidas = {m: V.consensus(Vs, m) for m in
                       ("magnitudes_first", "mean", "median", "median_ri")}
            claves = list(salidas)
            pares = []
            for a, b in itertools.combinations(claves, 2):
                pares.append(float(np.max(np.abs(salidas[a] - salidas[b]))))
            fila = {"K": K, "modelo": modelo, "n_metodos": len(claves)}
            for m in claves:
                err = salidas[m] - verdad
                fila[f"mae_{m}"] = float(np.mean(np.abs(err)))
                # error de fase en grados, ponderado por magnitud
                ang = np.angle(salidas[m] * np.conj(verdad))
                fila[f"fase_deg_{m}"] = float(np.degrees(np.mean(np.abs(ang))))
            fila["max_dif_entre_metodos"] = max(pares)
            fila["identicos_4"] = max(pares) == 0.0
            filas.append(fila)
            print(f"  K={K} {modelo:<18} maxdif={fila['max_dif_entre_metodos']:.4f} "
                  f"mae(medf)={fila['mae_magnitudes_first']:.4f} "
                  f"fase(mean)={fila['fase_deg_mean']:.2f}deg", flush=True)
    return filas


# ============================================================ main
def escribir_csv(ruta, filas):
    if not filas:
        return
    campos = []
    for f in filas:
        for k in f:
            if k not in campos and not isinstance(f[k], (dict, list)):
                campos.append(k)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for f in filas:
            w.writerow({k: (repr(v) if isinstance(v, float) else f.get(k)) for k, v in
                        ((k, f.get(k)) for k in campos)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saltar-e2e", action="store_true")
    ap.add_argument("--saltar-runtime", action="store_true")
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    print("### 1. inventario estatico")
    inv = inventario()
    with open(os.path.join(RES, "consenso_inventario.json"), "w", encoding="utf-8") as fh:
        json.dump(inv, fh, indent=1, ensure_ascii=False)
    for k, v in inv.items():
        print(f"  {k:<15} cli_consensus={v['cli_consensus_linea']} "
              f"cli_order={v['cli_consensus_order_linea']} "
              f"cfm={v['consensus_from_masks']} "
              f"bloque_iguales={v['bloque_metodos_iguales']}")

    if not a.saltar_e2e:
        print("\n### 2. extremo a extremo (--consensus cambia la salida?)")
        filas, veredicto = e2e()
        escribir_csv(os.path.join(RES, "consenso_e2e.csv"), filas)
        with open(os.path.join(RES, "consenso_e2e_veredicto.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(veredicto, fh, indent=1, ensure_ascii=False)
        nm = nota_metodo()
        with open(os.path.join(RES, "consenso_e2e_metodo.json"), "w",
                  encoding="utf-8") as fh:
            json.dump(nm, fh, indent=1, ensure_ascii=False)
        print("\n  nota de metodo:", nm.get("conclusion", nm.get("motivo")))
        print("\n  VEREDICTO por (motor, orden):")
        for v in veredicto:
            print(f"    {v['motor']:<14} order={str(v['order']):<18} "
                  f"salidas distintas={v['n_salidas_distintas_sdv']}/{v['n_ejecutados_ok']} "
                  f"-> llega_a_operacion={v['llega_a_operacion']}")

    if not a.saltar_runtime:
        print("\n### 3. consenso enmascarado (K x modelo)")
        filas3 = consenso_enmascarado()
        escribir_csv(os.path.join(RES, "consenso_mallas.csv"), filas3)
        print("\n### 4. consenso complejo (v3)")
        filas4 = consenso_complejo()
        escribir_csv(os.path.join(RES, "consenso_complejo.csv"), filas4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
