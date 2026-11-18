"""BLOQUE C — mix_delta.py y SDI_F2.

Pregunta del encargo: formulas exactas de mix_delta, la complementariedad
e = M - SDV - SDI SIN confundirla con separacion, los casos de desfase / polaridad /
canales / SR / longitudes, y la identidad
    Delta_indirecta = (SDV_norm - SDV_id) + e_norm
Si SDI_F2 no esta en el codigo, se declara explicitamente y queda UNKNOWN.

Nada se modifica: mix_delta.py se ejecuta como proceso y los motores tambien.

Partes:
  1. auditoria estatica (formulas + lineas verificadas + busqueda de SDI_F2)
  2. complementariedad MEDIDA sobre salidas reales del motor v3 (3 ramas)
  3. mix_delta extremo a extremo + verificacion numerica de la identidad
  4. guardas: SR / canales / longitudes / --allow-crop / desfase / polaridad / ambiguedad

Uso: python3 -u src/bloque_c.py [--saltar-e2e]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import senales as S          # noqa: E402
import adaptadores as A      # noqa: E402

RES = os.path.join(BASE, "results")
WORK = os.path.join(BASE, "work", "c")
FUENTES = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"
MIX_DELTA = os.path.join(FUENTES, "mix_delta.py")
SR = 44100


# ============================================================ utilidades
def lineas(ruta):
    with open(ruta, encoding="utf-8", errors="replace") as fh:
        return fh.read().splitlines()


def buscar(ruta, patron):
    return [i + 1 for i, l in enumerate(lineas(ruta)) if patron in l]


def snr_db(ref, err):
    r = float(np.square(ref).sum())
    e = float(np.square(err).sum())
    return 10.0 * np.log10(r / max(e, 1e-30))


def escribir(path, x, sr=SR):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.asarray(x, dtype=np.float64), sr, subtype="FLOAT")
    return path


def correr_mix_delta(args, timeout=300):
    cmd = [sys.executable, MIX_DELTA] + args
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return {"cmd": cmd, "rc": p.returncode,
            "stdout": p.stdout[-6000:], "stderr": p.stderr[-6000:]}


# ============================================================ 1. auditoria
def auditoria():
    """Formulas exactas + verificacion de lineas + busqueda de SDI_F2."""
    L = lineas(MIX_DELTA)
    d = {
        "fichero": "mix_delta.py",
        "n_lineas": len(L),
        "sha256": A.__dict__.get("sha256_file") and None,
        "formulas": {
            "SDI_x": "SDI_x = mix - V_hat_x",
            "complementariedad_e": "e_norm := mix - SDV_norm - SDI_norm",
            "Delta_indirecta": "Delta = SDI_identity - SDI_normal",
            "identidad": ("Delta_indirecta = (SDV_norm - SDV_id) + e_norm "
                          "= Delta_directa + e_norm"),
            "hibrido": "SDV_hibrido = SDV_norm + gain*Delta",
            "hibrido_desarrollado": ("SDV_hibrido = SDV_norm + gain*(SDV_norm - SDV_id)"
                                     " + gain*e_norm"),
        },
        "lineas": {
            "docstring_formulas": (3, 40),
            "umbral_complementariedad": (buscar(MIX_DELTA, "COMPLEMENTARY_SNR_MIN_DB =") or [None])[0],
            "check_compatibility": (buscar(MIX_DELTA, "def check_compatibility") or [None])[0],
            "estimate_lag_ms": (buscar(MIX_DELTA, "def estimate_lag_ms") or [None])[0],
            "calculo_e_norm": (buscar(MIX_DELTA, "e_norm = mix_data - sdv_norm - sdi_norm") or [None])[0],
            "calculo_delta": (buscar(MIX_DELTA, "delta_vocal =") or [None])[0],
            "calculo_hibrido": (buscar(MIX_DELTA, "sdv_hybrid = sdv_norm +") or [None])[0],
            "aviso_desfase": (buscar(MIX_DELTA, "Delta puede dominar por DESFASE") or [None])[0],
            "fatal_largos": (buscar(MIX_DELTA, "duraciones distintas (NO se trunca en silencio)") or [None])[0],
            "fatal_ambiguo": (buscar(MIX_DELTA, "candidatos ambiguos") or [None])[0],
        },
    }
    # el calculo real del Delta (no solo el docstring)
    for i, l in enumerate(L):
        if l.strip().startswith("delta_vocal ="):
            d["lineas"]["calculo_delta"] = i + 1
            d["texto_delta"] = l.strip()
        if l.strip().startswith("sdv_hybrid ="):
            d["texto_hibrido"] = l.strip()
    # busqueda de SDI_F2 en TODAS las fuentes y manifiestos
    patrones = ["SDI_F2", "SDI_F", "F2"]
    hallazgos = {}
    for f in sorted(os.listdir(FUENTES)):
        ruta = os.path.join(FUENTES, f)
        if not os.path.isfile(ruta) or not f.endswith((".py", ".json", ".md", ".txt")):
            continue
        try:
            txt = open(ruta, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for p in patrones:
            if p in txt:
                hallazgos.setdefault(p, {})[f] = txt.count(p)
    d["busqueda_sdi_f2"] = {
        "patrones": patrones,
        "hallazgos": hallazgos,
        "SDI_F2_presente": "SDI_F2" in (hallazgos.get("SDI_F2") or {}),
        "conclusion": ("SDI_F2 NO aparece en ninguna fuente ni manifiesto del paquete"
                       if "SDI_F2" not in (hallazgos.get("SDI_F2") or {})
                       else "SDI_F2 aparece; revisar contexto"),
    }
    return d


# ============================================================ 2. complementariedad
def corrida_v3(branch, dur=4.0, tag=""):
    """Corre v3 con una rama y devuelve (mix_path, sdv_path, sdi_path, rc)."""
    base = os.path.join(WORK, f"v3_{branch}{tag}")
    sc = S.escenario("voz_armonica", dur=dur, seed=20261117)
    g = {"vocal_1": sc["V_true"], "instrum_1": sc["I_true"]}
    rut = A.escribir_fixture(base, sc, g)
    man = A.manifiesto(rut["mix"], [("p1", rut["guias"]["vocal_1"],
                                     rut["guias"]["instrum_1"])], os.path.join(base, "out"),
                       mask_mode="mono")
    mp = A.escribir_manifiesto(os.path.join(base, "manifest.json"), man)
    r = A.ejecutar("v3_3.0.0", mp, os.path.join(base, "out"),
                   extra=["--allow-misaligned", "--branch", branch])
    sal = A.buscar_salidas(os.path.join(base, "out"))
    return rut["mix"], sal.get("sdv"), sal.get("sdi"), r


def complementariedad():
    """e = M - SDV - SDI medido sobre salidas reales, por rama."""
    filas = []
    for branch in ("normal", "ratio", "identity"):
        mix_p, sdv_p, sdi_p, r = corrida_v3(branch)
        if r["rc"] != 0 or not sdv_p or not sdi_p:
            filas.append({"rama": branch, "rc": r["rc"], "error": r["stdout"][-400:]})
            continue
        M, _ = sf.read(mix_p, dtype="float64")
        V, _ = sf.read(sdv_p, dtype="float64")
        I, _ = sf.read(sdi_p, dtype="float64")
        n = min(len(M), len(V), len(I))
        M, V, I = M[:n], V[:n], I[:n]
        e = M - V - I
        filas.append({
            "rama": branch, "n_muestras": int(n),
            "rms_e": float(np.sqrt(np.mean(e ** 2))),
            "rms_mix": float(np.sqrt(np.mean(M ** 2))),
            "pct_del_mix": float(100.0 * np.sqrt(np.mean(e ** 2)) /
                                 max(np.sqrt(np.mean(M ** 2)), 1e-30)),
            "snr_db": float(snr_db(M, e)),
            "max_abs_e": float(np.max(np.abs(e))),
            "complementaria_umbral_100dB": bool(snr_db(M, e) >= 100.0),
            "sdv_mas_sdi_igual_mix_exacto": bool(np.array_equal(M, V + I)),
            "mix_path": mix_p, "sdv_path": sdv_p, "sdi_path": sdi_p,
        })
        print(f"  rama {branch:<9} SNR(e)={filas[-1]['snr_db']:9.2f} dB  "
              f"rms(e)={filas[-1]['rms_e']:.3e}  max|e|={filas[-1]['max_abs_e']:.3e}  "
              f"complementaria={filas[-1]['complementaria_umbral_100dB']}", flush=True)
    return filas


# ============================================================ 3. delta + identidad
def delta_e_identidad():
    """Ejecuta mix_delta con --mix y verifica la identidad numerica."""
    # corridas normal e identity sobre el MISMO mix
    mix_p, sdv_n, sdi_n, r1 = corrida_v3("normal")
    _, sdv_i, sdi_i, r2 = corrida_v3("identity")
    if r1["rc"] != 0 or r2["rc"] != 0:
        return {"error": "fallo de corridas base", "rc": [r1["rc"], r2["rc"]]}
    out = os.path.join(WORK, "hibrido", "SDV_hibrido.wav")
    args = ["--dir_norm", os.path.dirname(sdv_n), "--dir_id", os.path.dirname(sdv_i),
            "--mix", mix_p, "--gain", "0.5", "--out", out,
            "--sdv-norm", sdv_n, "--sdi-norm", sdi_n, "--sdi-id", sdi_i]
    r = correr_mix_delta(args)
    res = {"cmd": r["cmd"], "rc": r["rc"], "stdout": r["stdout"], "stderr": r["stderr"]}

    M, _ = sf.read(mix_p, dtype="float64")
    Vn, _ = sf.read(sdv_n, dtype="float64")
    In, _ = sf.read(sdi_n, dtype="float64")
    Vi, _ = sf.read(sdv_i, dtype="float64")
    Ii, _ = sf.read(sdi_i, dtype="float64")
    n = min(len(M), len(Vn), len(In), len(Vi), len(Ii))
    M, Vn, In, Vi, Ii = M[:n], Vn[:n], In[:n], Vi[:n], Ii[:n]

    e_norm = M - Vn - In
    delta_ind = Ii - In
    delta_dir = Vn - Vi
    ident = delta_dir + e_norm
    res["identidad"] = {
        "n_muestras": int(n),
        "max_abs_diferencia": float(np.max(np.abs(delta_ind - ident))),
        "rms_diferencia": float(np.sqrt(np.mean((delta_ind - ident) ** 2))),
        "rms_delta_indirecta": float(np.sqrt(np.mean(delta_ind ** 2))),
        "se_cumple": bool(np.allclose(delta_ind, ident, atol=1e-12)),
        "error_relativo": float(np.sqrt(np.mean((delta_ind - ident) ** 2)) /
                                max(np.sqrt(np.mean(ident ** 2)), 1e-30)),
    }
    # el hibrido escrito, contrastado con la formula
    if os.path.isfile(out):
        H, _ = sf.read(out, dtype="float64")
        H = H[:n]
        formula = Vn + 0.5 * delta_ind
        res["hibrido"] = {
            "max_abs_vs_formula": float(np.max(np.abs(H - formula))),
            "se_cumple": bool(np.allclose(H, formula, atol=1e-9)),
            "rms_hibrido": float(np.sqrt(np.mean(H ** 2))),
        }
        prov = out + ".provenance.json"
        if os.path.isfile(prov):
            with open(prov, encoding="utf-8") as fh:
                pj = json.load(fh)
            res["provenance"] = {"existe": True,
                                 "claves": sorted(pj.keys()),
                                 "complementarity": pj.get("complementarity"),
                                 "delta_directa": pj.get("delta_directa")}
        else:
            res["provenance"] = {"existe": False, "ruta_esperada": prov}
    print(f"  identidad Delta_indirecta = (SDV_norm-SDV_id) + e_norm: "
          f"max|d|={res['identidad']['max_abs_diferencia']:.3e} "
          f"-> {res['identidad']['se_cumple']}")
    return res


# ============================================================ 4. guardas
def guardas():
    """Cada caso de incompatibilidad, probado contra el CLI real."""
    base = os.path.join(WORK, "guardas")
    sc = S.escenario("voz_armonica", dur=2.0, seed=20261117)
    M = sc["M"]
    n = M.shape[0]
    rng = np.random.default_rng(3)
    sdv = 0.6 * M + 0.01 * rng.standard_normal(M.shape)
    sdi = M - sdv
    sdi_id = M - (0.5 * M)                       # distinto del normal, a proposito
    p_sdv = escribir(os.path.join(base, "norm", "SDV.wav"), sdv)
    p_sdi = escribir(os.path.join(base, "norm", "SDI.wav"), sdi)
    p_id = escribir(os.path.join(base, "id", "SDI.wav"), sdi_id)
    p_sdvid = escribir(os.path.join(base, "id", "SDV.wav"), 0.5 * M)
    p_mix = escribir(os.path.join(base, "mix.wav"), M)

    def ejecutar(tag, extra=None, dir_norm=None, dir_id=None):
        out = os.path.join(base, "out_" + tag, "hib.wav")
        a = ["--dir_norm", dir_norm or os.path.dirname(p_sdv),
             "--dir_id", dir_id or os.path.dirname(p_id),
             "--out", out, "--mix", p_mix]
        a += (extra or [])
        r = correr_mix_delta(a)
        return {"caso": tag, "rc": r["rc"],
                "stdout": r["stdout"], "stderr": r["stderr"],
                "out_existe": os.path.isfile(out)}

    casos = []
    # 0) linea base: todo compatible
    casos.append(ejecutar("base_compatible"))

    # 1) SR distinto
    p_id_48 = os.path.join(base, "id48", "SDI.wav")
    escribir(p_id_48, sdi_id, sr=48000)
    os.makedirs(os.path.dirname(p_id_48), exist_ok=True)
    escribir(os.path.join(base, "id48", "SDV.wav"), 0.5 * M, sr=48000)
    casos.append(ejecutar("sr_distinto", dir_id=os.path.dirname(p_id_48)))

    # 2) canales distintos (mono vs estereo)
    p_id_mono = os.path.join(base, "idmono", "SDI.wav")
    escribir(p_id_mono, sdi_id[:, 0])
    escribir(os.path.join(base, "idmono", "SDV.wav"), (0.5 * M)[:, 0])
    casos.append(ejecutar("canales_distintos", dir_id=os.path.dirname(p_id_mono)))

    # 3) longitudes distintas sin --allow-crop
    p_id_corto = os.path.join(base, "idcorto", "SDI.wav")
    escribir(p_id_corto, sdi_id[: n - 1000])
    escribir(os.path.join(base, "idcorto", "SDV.wav"), (0.5 * M)[: n - 1000])
    casos.append(ejecutar("longitudes_distintas", dir_id=os.path.dirname(p_id_corto)))

    # 4) longitudes distintas CON --allow-crop (recorte explicito)
    casos.append(ejecutar("longitudes_allow_crop",
                          extra=["--allow-crop"], dir_id=os.path.dirname(p_id_corto)))

    # 5) desfase temporal de 5 ms en el Delta
    d5 = int(0.005 * SR)
    sh = np.zeros_like(sdi_id)
    sh[d5:] = sdi_id[:-d5]
    p_id_fase = os.path.join(base, "iddesfase", "SDI.wav")
    escribir(p_id_fase, sh)
    escribir(os.path.join(base, "iddesfase", "SDV.wav"), 0.5 * M)
    casos.append(ejecutar("desfase_5ms", dir_id=os.path.dirname(p_id_fase)))

    # 6) polaridad invertida (no hay guarda declarada: se mide que pasa)
    p_id_pol = os.path.join(base, "idpolaridad", "SDI.wav")
    escribir(p_id_pol, -sdi_id)
    escribir(os.path.join(base, "idpolaridad", "SDV.wav"), 0.5 * M)
    casos.append(ejecutar("polaridad_invertida", dir_id=os.path.dirname(p_id_pol)))

    # 7) ambiguedad: dos candidatos SDI en la misma carpeta
    amb = os.path.join(base, "ambiguo")
    escribir(os.path.join(amb, "SDI.wav"), sdi_id)
    escribir(os.path.join(amb, "SDI_copia.wav"), sdi_id)
    escribir(os.path.join(amb, "SDV.wav"), 0.5 * M)
    casos.append(ejecutar("ambiguedad_2_candidatos", dir_id=amb))

    # 8) sin candidatos
    vacio = os.path.join(base, "vacio")
    os.makedirs(vacio, exist_ok=True)
    casos.append(ejecutar("sin_candidatos", dir_id=vacio))

    # 9) --mix con longitud distinta (opcional: igualdad EXACTA exigida)
    p_mix_corto = os.path.join(base, "mix_corto.wav")
    escribir(p_mix_corto, M[: n - 500])
    out = os.path.join(base, "out_mix_corto", "hib.wav")
    r = correr_mix_delta(["--dir_norm", os.path.dirname(p_sdv),
                          "--dir_id", os.path.dirname(p_id),
                          "--out", out, "--mix", p_mix_corto])
    casos.append({"caso": "mix_longitud_distinta", "rc": r["rc"],
                  "stdout": r["stdout"], "stderr": r["stderr"],
                  "out_existe": os.path.isfile(out)})

    for c in casos:
        msg = (c["stderr"].strip().splitlines() or c["stdout"].strip().splitlines() or [""])
        print(f"  {c['caso']:<26} rc={c['rc']:<3} out={c['out_existe']!s:<5} "
              f"| {msg[0][:96]}", flush=True)
    return casos


# ============================================================ 5. controles extra
def complementariedad_trivial():
    """CONTROL: la complementariedad NO dice nada sobre la separacion.

    Se toma SDV = mix y SDI = 0. Entonces e = M - SDV - SDI = 0 EXACTO: la
    reconstruccion es perfecta. Y la separacion es nula. Cualquier lectura de
    'e = 0' como 'separacion correcta' queda refutada por este caso.
    """
    sc = S.escenario("voz_armonica", dur=2.0, seed=20261117)
    M = sc["M"]
    casos = {
        "trivial_SDV=mix_SDI=0": (M.copy(), np.zeros_like(M)),
        "trivial_SDV=0_SDI=mix": (np.zeros_like(M), M.copy()),
        "correcto_SDV=V_SDI=I": (sc["V_true"], sc["I_true"]),
    }
    filas = []
    for nombre, (V, I) in casos.items():
        e = M - V - I
        filas.append({
            "caso": nombre,
            "snr_e_db": float(snr_db(M, e)),
            "max_abs_e": float(np.max(np.abs(e))),
            "complementaria_100dB": bool(snr_db(M, e) >= 100.0),
            "separacion_real": ("nula" if "trivial" in nombre else "ground truth exacta"),
        })
        print(f"  {nombre:<24} SNR(e)={filas[-1]['snr_e_db']:9.2f} dB  "
              f"complementaria={filas[-1]['complementaria_100dB']}  "
              f"separacion={filas[-1]['separacion_real']}", flush=True)
    return filas


def guias_degradadas_e_norm():
    """Reproduce el caso NO complementario: guias inexactas en la rama normal.

    Con guias exactas (V_true, I_true) la rama normal es complementaria por
    construccion, porque las guias suman el mix. Con guias reales no.
    """
    filas = []
    for etiqueta, factor, ruido in (("guias_exactas", 1.0, 0.0),
                                    ("guias_atenuadas_0.8", 0.8, 0.0),
                                    ("guias_0.8_mas_ruido", 0.8, 0.02)):
        base = os.path.join(WORK, f"v3_deg_{etiqueta}")
        sc = S.escenario("voz_armonica", dur=4.0, seed=20261117)
        rng = np.random.default_rng(11)
        V = factor * sc["V_true"] + ruido * rng.standard_normal(sc["V_true"].shape)
        I = factor * sc["I_true"] + ruido * rng.standard_normal(sc["I_true"].shape)
        g = {"vocal_1": V, "instrum_1": I}
        rut = A.escribir_fixture(base, sc, g)
        man = A.manifiesto(rut["mix"], [("p1", rut["guias"]["vocal_1"],
                                         rut["guias"]["instrum_1"])],
                           os.path.join(base, "out"), mask_mode="mono")
        mp = A.escribir_manifiesto(os.path.join(base, "manifest.json"), man)
        r = A.ejecutar("v3_3.0.0", mp, os.path.join(base, "out"),
                       extra=["--allow-misaligned", "--branch", "normal"])
        sal = A.buscar_salidas(os.path.join(base, "out"))
        if r["rc"] != 0 or not sal.get("sdv"):
            filas.append({"caso": etiqueta, "rc": r["rc"]})
            continue
        M, _ = sf.read(rut["mix"], dtype="float64")
        Vh, _ = sf.read(sal["sdv"], dtype="float64")
        Ih, _ = sf.read(sal["sdi"], dtype="float64")
        e = M - Vh - Ih
        filas.append({"caso": etiqueta, "rc": r["rc"],
                      "snr_e_db": float(snr_db(M, e)),
                      "rms_e": float(np.sqrt(np.mean(e ** 2))),
                      "max_abs_e": float(np.max(np.abs(e))),
                      "complementaria_100dB": bool(snr_db(M, e) >= 100.0)})
        print(f"  {etiqueta:<22} SNR(e)={filas[-1]['snr_e_db']:9.2f} dB  "
              f"max|e|={filas[-1]['max_abs_e']:.3e}  "
              f"complementaria={filas[-1]['complementaria_100dB']}", flush=True)
    return filas


def residuo_identidad_es_e_id():
    """El residuo de la identidad es EXACTAMENTE (SDV_id + SDI_id - mix) = e_id.

    Algebra: residuo := Delta_ind - (Delta_dir + e_norm) = (SDV_id + SDI_id) - mix = e_id.
    (El signo se comprobo numericamente: con el signo opuesto el doble del residuo no
    se anula, y con este si.)
    Se verifica sobre los casos de guarda ya generados (base, desfase, polaridad).
    """
    base = os.path.join(WORK, "guardas")
    pares = {
        "base_compatible": ("norm", "id"),
        "desfase_5ms": ("norm", "iddesfase"),
        "polaridad_invertida": ("norm", "idpolaridad"),
    }
    filas = []
    for caso, (dn, di) in pares.items():
        M, _ = sf.read(os.path.join(base, "mix.wav"), dtype="float64")
        Vn, _ = sf.read(os.path.join(base, dn, "SDV.wav"), dtype="float64")
        In, _ = sf.read(os.path.join(base, dn, "SDI.wav"), dtype="float64")
        Vi, _ = sf.read(os.path.join(base, di, "SDV.wav"), dtype="float64")
        Ii, _ = sf.read(os.path.join(base, di, "SDI.wav"), dtype="float64")
        n = min(len(M), len(Vn), len(In), len(Vi), len(Ii))
        M, Vn, In, Vi, Ii = M[:n], Vn[:n], In[:n], Vi[:n], Ii[:n]
        e_norm = M - Vn - In
        residuo = (Ii - In) - ((Vn - Vi) + e_norm)
        e_id = (Vi + Ii) - M
        filas.append({
            "caso": caso,
            "max_abs_residuo": float(np.max(np.abs(residuo))),
            "max_abs_residuo_menos_e_id": float(np.max(np.abs(residuo - e_id))),
            "rms_e_id": float(np.sqrt(np.mean(e_id ** 2))),
            "identidad_exacta": bool(np.max(np.abs(residuo - e_id)) < 1e-12),
        })
        print(f"  {caso:<22} max|residuo|={filas[-1]['max_abs_residuo']:.3e}  "
              f"max|residuo - e_id|={filas[-1]['max_abs_residuo_menos_e_id']:.3e}  "
              f"-> identidad con e_id: {filas[-1]['identidad_exacta']}", flush=True)
    return filas


def allow_crop_sin_sdv_id():
    """Aisla la causa del aborto: --allow-crop funciona si NO hay SDV_id."""
    base = os.path.join(WORK, "guardas")
    os.makedirs(os.path.join(base, "idcorto_solo"), exist_ok=True)
    sdi = sf.read(os.path.join(base, "idcorto", "SDI.wav"), dtype="float64")[0]
    escribir(os.path.join(base, "idcorto_solo", "SDI.wav"), sdi)
    out = os.path.join(base, "out_crop_sin_sdvid", "hib.wav")
    r = correr_mix_delta(["--dir_norm", os.path.join(base, "norm"),
                          "--dir_id", os.path.join(base, "idcorto_solo"),
                          "--out", out, "--mix", os.path.join(base, "mix.wav"),
                          "--allow-crop"])
    res = {"caso": "allow_crop_sin_sdv_id", "rc": r["rc"],
           "out_existe": os.path.isfile(out),
           "stdout": r["stdout"], "stderr": r["stderr"]}
    print(f"  {res['caso']:<26} rc={res['rc']}  out={res['out_existe']}", flush=True)
    return res


# ============================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saltar-e2e", action="store_true")
    a = ap.parse_args()
    os.makedirs(RES, exist_ok=True)
    os.makedirs(WORK, exist_ok=True)

    print("### 1. auditoria estatica")
    aud = auditoria()
    with open(os.path.join(RES, "mix_delta_auditoria.json"), "w", encoding="utf-8") as fh:
        json.dump(aud, fh, indent=1, ensure_ascii=False)
    print(f"  SDI_F2 presente: {aud['busqueda_sdi_f2']['SDI_F2_presente']}")
    print(f"  -> {aud['busqueda_sdi_f2']['conclusion']}")
    print(f"  formulas: {aud['formulas']['hibrido']}")
    print(f"  lineas: {aud['lineas']}")

    if a.saltar_e2e:
        return 0

    print("\n### 2. complementariedad e = M - SDV - SDI por rama")
    comp = complementariedad()
    with open(os.path.join(RES, "complementariedad.json"), "w", encoding="utf-8") as fh:
        json.dump(comp, fh, indent=1, ensure_ascii=False)

    print("\n### 3. mix_delta + identidad Delta_indirecta")
    d = delta_e_identidad()
    with open(os.path.join(RES, "delta_identidad.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, indent=1, ensure_ascii=False)

    print("\n### 3b. control: complementariedad NO es separacion")
    ct = complementariedad_trivial()
    with open(os.path.join(RES, "complementariedad_trivial.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ct, fh, indent=1, ensure_ascii=False)

    print("\n### 3c. guias degradadas -> e_norm deja de ser cero")
    gd = guias_degradadas_e_norm()
    with open(os.path.join(RES, "complementariedad_guias_degradadas.json"), "w",
              encoding="utf-8") as fh:
        json.dump(gd, fh, indent=1, ensure_ascii=False)

    print("\n### 4. guardas")
    g = guardas()
    with open(os.path.join(RES, "mix_delta_guardas.json"), "w", encoding="utf-8") as fh:
        json.dump(g, fh, indent=1, ensure_ascii=False)

    print("\n### 4b. el residuo de la identidad es exactamente e_id")
    re_ = residuo_identidad_es_e_id()
    with open(os.path.join(RES, "delta_identidad_residuo.json"), "w",
              encoding="utf-8") as fh:
        json.dump(re_, fh, indent=1, ensure_ascii=False)

    print("\n### 4c. aislando el aborto de --allow-crop")
    ac = allow_crop_sin_sdv_id()
    with open(os.path.join(RES, "allow_crop_sin_sdv_id.json"), "w",
              encoding="utf-8") as fh:
        json.dump(ac, fh, indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
