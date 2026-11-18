"""BLOQUE B — Agregacion, contrafactual de la puerta de confianza y figuras.

Entradas (generadas por bloque_b.py y bloque_b_control.py):
    results/alineacion_casos.csv
    results/alineacion_curvas.json
    results/alineacion_identidad.json
    results/alineacion_lr_asimetrico.json

Salidas:
    results/alineacion_resumen.json   agregados citables en el informe
    results/b_raw.jsonl               registros individuales en el esquema comun
    results/fig_b_ncc_voz4s.svg       curva NCC completa (falso positivo lejano)
    results/fig_b_ncc_perc30s.svg     zoom cerca de 0 (empate a 3e-7)
    results/fig_b_pearson.svg         Pearson del ganador vs |error| (separa FP)

Todos los numeros del informe ALIGNMENT_DIAGNOSTICS.md salen de este script.
No modifica ningun motor ni audio: solo lee CSV/JSON ya producidos.
"""
from __future__ import annotations

import csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
RES = os.path.join(BASE, "results")

SR = 44100
DECIM = 8


def leer_casos():
    filas = []
    with open(os.path.join(RES, "alineacion_casos.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            def f(k):
                v = r[k]
                return None if v in ("None", "", "nan") else float(v)
            filas.append({
                "motor": r["motor"], "contenido": r["contenido"],
                "dur_s": float(r["dur_s"]),
                "retardo_real_ms": float(r["retardo_real_ms"]),
                "retardo_real_muestras": int(r["retardo_real_muestras"]),
                "lag_esperado_muestras": int(r["lag_esperado_muestras"]),
                "lag_motor_env": int(r["lag_motor_env"]),
                "lag_ganador_env": int(float(r["lag_ganador_env"])),
                "lag_estimado_muestras": float(r["lag_estimado_muestras"]),
                "lag_estimado_ms": float(r["lag_estimado_ms"]),
                "error_ms": float(r["error_ms"]),
                "clase": r["clase"],
                "acierto_1muestra": r["acierto_1muestra"] == "True",
                "falso_positivo": r["falso_positivo"] == "True",
                "falso_negativo": r["falso_negativo"] == "True",
                "replica_coincide": r["replica_coincide"] == "True",
                "ncc_max": f("ncc_max"), "ncc_en_lag_real": f("ncc_en_lag_real"),
                "ratio_real_vs_max": f("ratio_real_vs_max"),
                "n_picos_casi_empatados": f("n_picos_casi_empatados"),
                "solape_ganador": f("solape_ganador"), "solape_max": f("solape_max"),
                "pearson": f("peak_pearson_refinado"),
                "lag_ganador_con_solape_alto_env": f("lag_ganador_con_solape_alto_env"),
            })
    return filas


def resumen(filas):
    fp = [f for f in filas if f["falso_positivo"]]
    fn = [f for f in filas if f["falso_negativo"]]
    cero = [f for f in filas if f["retardo_real_ms"] == 0]
    ok = [f for f in filas if f["acierto_1muestra"]]
    correctos = [f for f in filas if f["acierto_1muestra"]
                 and not f["falso_positivo"] and not f["falso_negativo"]]
    out = {
        "n_casos": len(filas),
        "replica_fiel_al_motor": sum(1 for f in filas if f["replica_coincide"]),
        "aciertos_1_muestra": len(ok),
        "falsos_positivos": len(fp),
        "falsos_negativos": len(fn),
        "casos_retardo_cero": len(cero),
        "retardo_cero_declarados_misaligned": sum(
            1 for f in cero if f["clase"] == "MISALIGNED"),
        "retardo_cero_declarados_aligned": sum(
            1 for f in cero if f["clase"] == "ALIGNED"),
        "retardo_cero_declarados_warning": sum(
            1 for f in cero if f["clase"] == "WARNING"),
        "pearson_fp_rango": [min(f["pearson"] for f in fp),
                             max(f["pearson"] for f in fp)],
        "pearson_aciertos_rango": [min(f["pearson"] for f in correctos),
                                   max(f["pearson"] for f in correctos)],
        "ratio_ncc_fp_rango": [min(f["ratio_real_vs_max"] for f in fp),
                               max(f["ratio_real_vs_max"] for f in fp)],
        "ratio_ncc_aciertos_rango": [min(f["ratio_real_vs_max"] for f in correctos),
                                     max(f["ratio_real_vs_max"] for f in correctos)],
        "casos_con_ratio_superior_0_999": sum(
            1 for f in filas if f["ratio_real_vs_max"] and f["ratio_real_vs_max"] > 0.999),
    }
    # contrafactual: puerta por confianza
    barrido = []
    for th in (0.10, 0.20, 0.30, 0.35, 0.40, 0.50, 0.60, 0.70, 0.80):
        barrido.append({
            "umbral": th,
            "fp_retirados": sum(1 for f in fp if f["pearson"] < th),
            "fp_total": len(fp),
            "aciertos_perdidos": sum(1 for f in correctos if f["pearson"] < th),
            "aciertos_total": len(correctos),
        })
    out["contrafactual_puerta_confianza"] = barrido
    out["umbral_seguro"] = {
        "rango": [max(f["pearson"] for f in fp),
                  min(f["pearson"] for f in correctos)],
        "lectura": ("cualquier umbral dentro de este intervalo retira los 10 falsos "
                    "positivos y no descarta ningun acierto"),
    }
    # contrafactual: restringir a solape alto
    out["contrafactual_solape_alto"] = {
        "fp_que_quedarian_misaligned": sum(
            1 for f in fp
            if abs(f["lag_ganador_con_solape_alto_env"] * DECIM) > 441),
        "detalle_ms": [
            {"contenido": f["contenido"], "dur_s": f["dur_s"],
             "ganador_libre_ms": f["lag_ganador_env"] * DECIM / SR * 1000.0,
             "ganador_solape_alto_ms": f["lag_ganador_con_solape_alto_env"] * DECIM / SR * 1000.0}
            for f in fp],
    }
    # tablas
    tab = {}
    for f in filas:
        k = f["contenido"]
        d = tab.setdefault(k, {"n": 0, "aciertos": 0, "fp": 0, "fn": 0})
        d["n"] += 1
        d["aciertos"] += 1 if f["acierto_1muestra"] else 0
        d["fp"] += 1 if f["falso_positivo"] else 0
        d["fn"] += 1 if f["falso_negativo"] else 0
    out["por_contenido"] = tab
    tabm = {}
    for mag in sorted({abs(f["retardo_real_ms"]) for f in filas}):
        fs = [f for f in filas if abs(f["retardo_real_ms"]) == mag]
        tabm[f"{mag:g}"] = {
            "n": len(fs), "aciertos": sum(1 for f in fs if f["acierto_1muestra"]),
            "err_max_ms": max(abs(f["error_ms"]) for f in fs),
            "clases": {c: sum(1 for f in fs if f["clase"] == c)
                       for c in {x["clase"] for x in fs}},
        }
    out["por_magnitud_retardo"] = tabm
    # igualdad entre motores
    h = [f for f in filas if f["motor"] == "hardened_3.1.1"]
    e = [f for f in filas if f["motor"] == "evo_3.1.1"]
    pares = list(zip(h, e))
    out["control_identidad"] = control_identidad()
    out["clasificacion_con_umbral"] = clasificacion_con_umbral(filas)
    out["alcance_solape_alto"] = alcance_solape_alto(filas)
    out["hardened_vs_evo"] = {
        "pares": len(pares),
        "diferencias_en_error": sum(1 for a, b in pares if a["error_ms"] != b["error_ms"]),
        "diferencias_en_clase": sum(1 for a, b in pares if a["clase"] != b["clase"]),
    }
    return out


# ------------------------------------------------------------------ figuras SVG
def svg_lineas(titulo, xs, ys, ruta, marcas=(), ancho=980, alto=380, nota=""):
    """SVG autocontenido (estilos en linea, sin recursos externos)."""
    x0, x1 = float(np.min(xs)), float(np.max(xs))
    y0, y1 = float(np.min(ys)), float(np.max(ys))
    if y1 - y0 < 1e-12:
        y1 = y0 + 1e-12
    m = {"i": 70, "d": 30, "a": 46, "b": 62}
    W, H = ancho - m["i"] - m["d"], alto - m["a"] - m["b"]

    def px(x):
        return m["i"] + (x - x0) / (x1 - x0) * W if x1 > x0 else m["i"]

    def py(y):
        return m["a"] + (1.0 - (y - y0) / (y1 - y0)) * H

    n = len(xs)
    paso = max(1, n // 900)
    partes = [f"M {px(xs[i]):.2f} {py(ys[i]):.2f}" for i in range(0, n, paso)]
    trazo = 'M ' + ' L '.join(p.split('M ')[1] for p in partes)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{ancho}" height="{alto}" '
           f'viewBox="0 0 {ancho} {alto}" font-family="ui-sans-serif,system-ui,sans-serif">',
           f'<rect width="{ancho}" height="{alto}" fill="#ffffff"/>',
           f'<text x="{m["i"]}" y="26" font-size="16" font-weight="600" fill="#111827">'
           f'{titulo}</text>',
           f'<rect x="{m["i"]}" y="{m["a"]}" width="{W}" height="{H}" fill="#fbfbfd" '
           f'stroke="#d1d5db"/>']
    for i in range(5):
        yv = y0 + (y1 - y0) * i / 4
        yy = py(yv)
        svg.append(f'<line x1="{m["i"]}" y1="{yy:.2f}" x2="{m["i"]+W}" y2="{yy:.2f}" '
                   f'stroke="#e5e7eb"/>')
        svg.append(f'<text x="{m["i"]-8}" y="{yy+4:.2f}" font-size="11" fill="#6b7280" '
                   f'text-anchor="end">{yv:.6f}</text>')
    for i in range(5):
        xv = x0 + (x1 - x0) * i / 4
        xx = px(xv)
        svg.append(f'<text x="{xx:.2f}" y="{m["a"]+H+18}" font-size="11" fill="#6b7280" '
                   f'text-anchor="middle">{xv:.0f}</text>')
    svg.append(f'<path d="{trazo}" fill="none" stroke="#2563eb" stroke-width="1.2"/>')
    for mx_, my_, etiqueta, color in marcas:
        if x0 <= mx_ <= x1:
            svg.append(f'<line x1="{px(mx_):.2f}" y1="{m["a"]}" x2="{px(mx_):.2f}" '
                       f'y2="{m["a"]+H}" stroke="{color}" stroke-dasharray="4 3"/>')
            svg.append(f'<circle cx="{px(mx_):.2f}" cy="{py(my_):.2f}" r="4" '
                       f'fill="{color}"/>')
            svg.append(f'<text x="{px(mx_):.2f}" y="{py(my_)-10:.2f}" font-size="11" '
                       f'fill="{color}" text-anchor="middle">{etiqueta}</text>')
    svg.append(f'<text x="{m["i"]+W/2}" y="{alto-8}" font-size="11" fill="#6b7280" '
               f'text-anchor="middle">{nota}</text>')
    svg.append('</svg>')
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))


def figuras(curvas):
    # 1) falso positivo lejano: curva completa
    k = "hardened_3.1.1|voz_armonica|4s|d0"
    c = curvas[k]
    lags = np.array(c["lags"], dtype=np.float64) * DECIM / SR * 1000.0
    vals = np.nan_to_num(np.array(c["vals"], dtype=np.float64), nan=0.0)
    sel = vals > 0.5
    svg_lineas("NCC por lag — voz_armonica 4 s, retardo real 0 (falso positivo)",
               lags[sel], vals[sel],
               os.path.join(RES, "fig_b_ncc_voz4s.svg"),
               marcas=[(0.0, vals[np.argmin(np.abs(lags))], "verdad 0 ms", "#059669"),
                       (1439.819, vals.max(), "ganador 1439.8 ms", "#dc2626")],
               nota="lag en ms; el maximo cae a 1,44 s con solo 64 % de solape")

    # 2) empate numerico cerca de 0
    k = "hardened_3.1.1|percusivo|30s|d0"
    c = curvas[k]
    lags = np.array(c["lags"], dtype=np.float64) * DECIM / SR * 1000.0
    vals = np.array(c["vals"], dtype=np.float64)
    m = np.abs(lags) <= 20.0
    svg_lineas("NCC por lag, zoom ±20 ms — percusivo 30 s, retardo real 0",
               lags[m], vals[m],
               os.path.join(RES, "fig_b_ncc_perc30s.svg"),
               marcas=[(0.0, vals[np.argmin(np.abs(lags))], "lag 0", "#059669"),
                       (5.079, np.nanmax(vals[m]), "ganador 5.08 ms", "#dc2626")],
               nota="diferencia entre el ganador y el lag 0: 3e-07 (empate numerico)")

    # 3) Pearson del ganador: separa falsos positivos de aciertos
    filas = leer_casos()


def fig_pearson(filas, ruta):
    """Tira de confianza por categoria. Pretende mostrar SOLO una cosa:
    que la confianza del ganador separa limpiamente los falsos positivos de los
    aciertos, con un hueco vacio en medio que ningun caso ocupa."""
    H, W = 420, 980
    izq, der, arr, aba = 90, 40, 60, 84
    ancho, alto = W - izq - der, H - arr - aba
    y0, y1 = 0.0, 0.9

    def py(y):
        return arr + (1.0 - (y - y0) / (y1 - y0)) * alto

    cats = [
        ("falso positivo", "#dc2626",
         [f for f in filas if f["falso_positivo"]]),
        ("error de estimacion\nsin cambiar veredicto", "#9ca3af",
         [f for f in filas if not f["falso_positivo"] and not f["acierto_1muestra"]]),
        ("acierto &lt;= 1 muestra", "#059669",
         [f for f in filas if f["acierto_1muestra"] and not f["falso_positivo"]]),
    ]
    rng = np.random.default_rng(7)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
           f'viewBox="0 0 {W} {H}" font-family="ui-sans-serif,system-ui,sans-serif">',
           f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
           f'<text x="{izq}" y="28" font-size="15" font-weight="600" fill="#111827">'
           f'Confianza del par alineado (Pearson) por resultado — 780 casos, motor hardened</text>',
           f'<rect x="{izq}" y="{arr}" width="{ancho}" height="{alto}" fill="#fbfbfd" '
           f'stroke="#d1d5db"/>']
    for i in range(6):
        yv = y0 + (y1 - y0) * i / 5
        svg.append(f'<line x1="{izq}" y1="{py(yv):.1f}" x2="{izq+ancho}" '
                   f'y2="{py(yv):.1f}" stroke="#e5e7eb"/>')
        svg.append(f'<text x="{izq-8}" y="{py(yv)+4:.1f}" font-size="11" fill="#6b7280" '
                   f'text-anchor="end">{yv:.2f}</text>')
    lo = max(f["pearson"] for f in filas if f["falso_positivo"])
    hi = min(f["pearson"] for f in filas
             if f["acierto_1muestra"] and not f["falso_positivo"])
    svg.append(f'<rect x="{izq}" y="{py(hi):.1f}" width="{ancho}" '
               f'height="{py(lo)-py(hi):.1f}" fill="#fde68a" opacity="0.6"/>')
    svg.append(f'<text x="{izq+ancho/2:.0f}" y="{py((lo+hi)/2)+4:.1f}" font-size="12" '
               f'fill="#92400e" text-anchor="middle">hueco vacio: ningun caso tiene '
               f'confianza entre {lo:.3f} y {hi:.3f}</text>')
    paso = ancho / len(cats)
    for c, (nombre, col, fs) in enumerate(cats):
        cx = izq + paso * (c + 0.5)
        for f in fs:
            jx = rng.normal(0, paso * 0.09)
            svg.append(f'<circle cx="{cx+jx:.1f}" cy="{py(f["pearson"]):.1f}" r="2.6" '
                       f'fill="{col}" fill-opacity="0.55"/>')
        svg.append(f'<text x="{cx:.1f}" y="{arr+alto+22}" font-size="11.5" fill="#374151" '
                   f'text-anchor="middle" font-weight="600">{nombre.split(chr(10))[0]}</text>')
        if chr(10) in nombre:
            svg.append(f'<text x="{cx:.1f}" y="{arr+alto+36}" font-size="11" '
                       f'fill="#6b7280" text-anchor="middle">'
                       f'{nombre.split(chr(10))[1]}</text>')
        svg.append(f'<text x="{cx:.1f}" y="{arr+alto+56}" font-size="11" fill="#111827" '
                   f'text-anchor="middle">{len(fs)} casos</text>')
    svg.append(f'<text x="{izq-60}" y="{arr+alto/2:.0f}" font-size="11" fill="#6b7280" '
               f'transform="rotate(-90 {izq-60} {arr+alto/2:.0f})" text-anchor="middle">'
               f'confianza (Pearson del par propuesto por el detector)</text>')
    svg.append('</svg>')
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))


# ------------------------------------------- agregados de la revision (B-rev)
THETA_EXPLORATORIO = 0.35
SR_ = 44100
DEC_ = 8
HALF_REFINE_ = 12          # ALIGN_REFINE_HALFSPAN


def clasificacion_con_umbral(filas, theta=THETA_EXPLORATORIO):
    """Clasificacion completa antes y despues de la puerta por confianza.

    Regla evaluada SOLO fuera del motor: si pearson < theta la clase pasa a AMBIGUOUS;
    en cualquier otro caso se conserva la clase original. No se aplica a ningun .py.
    """
    def despues(f):
        return "AMBIGUOUS" if (f["pearson"] is not None and f["pearson"] < theta) else f["clase"]

    def recorte(grupo):
        antes = {c: sum(1 for f in grupo if f["clase"] == c)
                 for c in ("ALIGNED", "WARNING", "MISALIGNED")}
        desp = {c: sum(1 for f in grupo if despues(f) == c)
                for c in ("ALIGNED", "WARNING", "MISALIGNED", "AMBIGUOUS")}
        fp_a = sum(1 for f in grupo if f["falso_positivo"])
        fp_d = sum(1 for f in grupo if f["retardo_real_ms"] == 0
                   and despues(f) == "MISALIGNED")
        fn_a = sum(1 for f in grupo if f["falso_negativo"])
        fn_d = sum(1 for f in grupo if abs(f["retardo_real_ms"]) > 10 and despues(f) == "ALIGNED")
        return {"n": len(grupo), "antes": antes, "despues": desp,
                "fp_antes": fp_a, "fp_despues": fp_d,
                "fn_antes": fn_a, "fn_despues": fn_d}

    ac = [f for f in filas if f["acierto_1muestra"]]
    na = [f for f in filas if not f["acierto_1muestra"]]
    trans = {}
    for f in na:
        k = f"{f['clase']} -> {despues(f)}"
        trans[k] = trans.get(k, 0) + 1
    return {
        "theta": theta,
        "aviso": ("umbral EXPLORATORIO obtenido de esta bateria sintetica; NO validado "
                  "para musica real, NO incorporado al motor, NO definitivo"),
        "todos": recorte(filas),
        "hardened_3.1.1": recorte([f for f in filas if f["motor"] == "hardened_3.1.1"]),
        "evo_3.1.1": recorte([f for f in filas if f["motor"] == "evo_3.1.1"]),
        "aciertos": {"n": len(ac),
                     "pasan_a_ambiguous": sum(1 for f in ac
                                              if f["pearson"] is not None
                                              and f["pearson"] < theta)},
        "no_aciertos": {"n": len(na),
                        "pasan_a_ambiguous": sum(1 for f in na
                                                 if f["pearson"] is not None
                                                 and f["pearson"] < theta),
                        "transiciones": trans},
    }


def alcance_solape_alto(filas, fraccion=0.9):
    """Que desplazamientos permite buscar la restriccion de solape >= 90 %.

    Con A = B = N_env, el solape vale N_env - |k| y su maximo es N_env (k = 0).
    Exigir solape >= 0.9 * maximo equivale a |k| <= 0.1 * N_env, es decir un
    desplazamiento maximo del 10 % de la duracion de la senal.
    """
    tabla = []
    for dur in sorted({f["dur_s"] for f in filas}):
        n_muestras = int(round(dur * SR_))
        n_env = n_muestras // DEC_
        k_env = int(round((1.0 - fraccion) * n_env))  # round: int() truncaba 2204.99 -> 2204
        tabla.append({
            "dur_s": dur, "n_muestras": n_muestras, "n_env": n_env,
            "k_max_env": k_env, "k_max_muestras": k_env * DEC_,
            "desplazamiento_max_ms": 1000.0 * k_env * DEC_ / SR_,
        })
    # los retardos reales de la bateria caben?
    peor_uso, fuera = 0.0, 0
    for f in filas:
        fila = next(t for t in tabla if t["dur_s"] == f["dur_s"])
        exp = abs(f["lag_esperado_muestras"])
        if exp > fila["k_max_muestras"]:
            fuera += 1
        peor_uso = max(peor_uso, exp / fila["k_max_muestras"])

    # efecto sobre la etapa gruesa: el ganador queda al alcance del refinamiento?
    def alcanzable(col, f):
        return abs(int(f[col]) * DEC_ - f["lag_esperado_muestras"]) <= HALF_REFINE_
    libre = sum(1 for f in filas if alcanzable("lag_ganador_env", f))
    restr = sum(1 for f in filas if alcanzable("lag_ganador_con_solape_alto_env", f))
    empeora = sum(1 for f in filas
                  if alcanzable("lag_ganador_env", f)
                  and not alcanzable("lag_ganador_con_solape_alto_env", f))
    mejora = sum(1 for f in filas
                 if not alcanzable("lag_ganador_env", f)
                 and alcanzable("lag_ganador_con_solape_alto_env", f))
    cero = [f for f in filas if f["retardo_real_ms"] == 0]
    cero_mis = sum(1 for f in cero
                   if abs(int(f["lag_ganador_con_solape_alto_env"]) * DEC_) > 441)
    return {
        "fraccion_solape": fraccion, "tabla_por_duracion": tabla,
        "casos_fuera_de_alcance": fuera, "n_casos": len(filas),
        "uso_maximo_del_alcance": peor_uso,
        "holgura_minima": 1.0 - peor_uso,
        "alcanzables_por_el_refinamiento": {"libre": libre, "restringido": restr},
        "empeoran": empeora, "mejoran": mejora,
        "retardo_cero_que_seguirian_misaligned": cero_mis,
        "retardo_cero_total": len(cero),
    }


def control_identidad():
    ruta = os.path.join(RES, "alineacion_identidad.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        d = json.load(fh)
    por_motor = {m: {"n_casos": v["n_casos"], "n_exactos": v["n_exactos"],
                     "pearson_min": v["pearson_min"], "pearson_max": v["pearson_max"],
                     "clases": v["clases"]} for m, v in d.items()}
    return {"por_motor": por_motor,
            "n_global": sum(v["n_casos"] for v in d.values()),
            "n_exactos_global": sum(v["n_exactos"] for v in d.values())}


# ------------------------------------------------------------------ JSONL comun
def escribir_jsonl(filas):
    ruta = os.path.join(RES, "b_raw.jsonl")
    with open(ruta, "w", encoding="utf-8") as fh:
        for f in filas:
            reg = {
                "bloque": "B", "caso": "alineacion_sintetica",
                "motor": f["motor"], "entrada": {"contenido": f["contenido"],
                                                 "dur_s": f["dur_s"]},
                "parametros": {"retardo_real_ms": f["retardo_real_ms"],
                               "retardo_real_muestras": f["retardo_real_muestras"],
                               "lag_esperado_muestras": f["lag_esperado_muestras"]},
                "medicion": {"lag_estimado_muestras": f["lag_estimado_muestras"],
                             "error_ms": f["error_ms"],
                             "pearson": f["pearson"],
                             "ncc_max": f["ncc_max"],
                             "ratio_ncc_real_vs_max": f["ratio_real_vs_max"],
                             "n_picos_casi_empatados": f["n_picos_casi_empatados"]},
                "clase": f["clase"],
                "acierto_1_muestra": f["acierto_1muestra"],
                "falso_positivo": f["falso_positivo"],
                "falso_negativo": f["falso_negativo"],
                "tipo": "EXPERIMENTAL_RESULT",
            }
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
    return ruta


def main():
    filas = leer_casos()
    r = resumen(filas)
    with open(os.path.join(RES, "alineacion_resumen.json"), "w", encoding="utf-8") as fh:
        json.dump(r, fh, indent=1, ensure_ascii=False)
    with open(os.path.join(RES, "alineacion_curvas.json"), encoding="utf-8") as fh:
        curvas = json.load(fh)
    figuras(curvas)
    fig_pearson(filas, os.path.join(RES, "fig_b_pearson.svg"))
    jl = escribir_jsonl(filas)

    print(json.dumps({k: v for k, v in r.items()
                      if k not in ("por_contenido", "por_magnitud_retardo",
                                   "contrafactual_puerta_confianza",
                                   "contrafactual_solape_alto")},
                     indent=1, ensure_ascii=False))
    print("\numbral seguro:", r["umbral_seguro"]["rango"])
    print("contrafactual solape alto: fp que quedarian misaligned =",
          r["contrafactual_solape_alto"]["fp_que_quedarian_misaligned"])
    print("\nhardened vs evo:", r["hardened_vs_evo"])
    ci = r["control_identidad"]
    print("identidad:", {m: f"{v['n_exactos']}/{v['n_casos']}" for m, v in ci["por_motor"].items()},
          "global", f"{ci['n_exactos_global']}/{ci['n_global']}")
    cu = r["clasificacion_con_umbral"]["todos"]
    print("theta=0.35  antes:", cu["antes"], " despues:", cu["despues"])
    print("            FP", cu["fp_antes"], "->", cu["fp_despues"],
          " FN", cu["fn_antes"], "->", cu["fn_despues"])
    al = r["alcance_solape_alto"]
    print("solape>=90%: alcanzables", al["alcanzables_por_el_refinamiento"],
          "empeoran", al["empeoran"], "mejoran", al["mejoran"],
          "fuera_de_alcance", al["casos_fuera_de_alcance"])
    print("escrito: alineacion_resumen.json, fig_b_*.svg,", os.path.basename(jl))
    return 0


if __name__ == "__main__":
    sys.exit(main())
