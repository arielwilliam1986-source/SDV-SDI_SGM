"""Verificación de coherencia interna de la entrega de la Fase 1B.

Tres familias de comprobaciones, todas re-ejecutables por un tercero:

  A. ESTRUCTURA      — la estructura sugerida por la matriz del encargo existe.
  B. CIFRAS          — cada cifra que los documentos afirman se RECALCULA desde los
                       artefactos crudos y se compara con lo declarado.
  C. REFERENCIAS     — toda ruta mencionada en los .md existe realmente en el paquete.

No escribe nada salvo `results/coherencia.json`. Devuelve 0 solo si todo cuadra.
"""
import csv
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, "results")

ESTRUCTURA = [
    "README.md", "REPORT.md", "SOURCE_AUDIT.md", "ORCHESTRATOR_SPEC.md",
    "FORMULA_AUDIT.md", "ALIGNMENT_DIAGNOSTICS.md", "CONSENSUS_VALIDATION.md",
    "src", "tests", "configs", "fixtures",
    "results/results.csv", "results/results.json", "results/raw.jsonl",
    "results/logs", "manifests", "hashes",
]

# rutas que aparecen en los documentos pero que NO deben existir en el paquete,
# con el motivo declarado.
EXCEPCIONES = {
    "results/alineacion_curvas.json": "120 MB; va la version reducida 1/8 y se regenera",
    "work/": "scratch regenerable, fuera del paquete por diseno",
    "SDV-SDI_FASE_1B_ENTREGA.zip": "el propio ZIP contenedor; su hash va en el sidecar .sha256",
}


def _json(nombre):
    with open(os.path.join(RES, nombre), encoding="utf-8") as fh:
        return json.load(fh)


def _csv(nombre):
    with open(os.path.join(RES, nombre), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ B. cifras
def cifras():
    filas = []

    def chk(bloque, afirmacion, declarado, recalculado, fuente, tolerancia=1e-9):
        if isinstance(declarado, (int, float)) and isinstance(recalculado, (int, float)):
            ok = abs(declarado - recalculado) <= tolerancia * max(1.0, abs(declarado))
        else:
            ok = str(declarado) == str(recalculado)
        filas.append({"bloque": bloque, "afirmacion": afirmacion,
                      "declarado": declarado, "recalculado": recalculado,
                      "fuente": fuente, "cuadra": bool(ok)})

    # ---------------- A ----------------
    e2e = {(x["motor"], x["order"]): x for x in _json("consenso_e2e_veredicto.json")}
    for motor, orden, esperado, max_abs in (
            ("hardened_3.1.1", "magnitudes_first", 1, 0.0),
            ("hardened_3.1.1", "masks_first", 3, 2.283e-3),
            ("evo_3.1.1", "magnitudes_first", 1, 0.0),
            ("evo_3.1.1", "masks_first", 3, 2.283e-3),
            ("evo_3.1.1", "hybrid_asymmetric", 3, 2.072e-3)):
        v = e2e.get((motor, orden)) or {}
        chk("A", f"{motor}/{orden}: metodos distintos en operacion", esperado,
            v.get("n_salidas_distintas_sdv"), "consenso_e2e_veredicto.json")
        if max_abs:
            chk("A", f"{motor}/{orden}: max|delta| de audio", max_abs,
                round(v.get("max_abs_entre_metodos_sdv", -1), 6),
                "consenso_e2e_veredicto.json", tolerancia=5e-3)
        else:
            chk("A", f"{motor}/{orden}: max|delta| EXACTAMENTE 0", 0.0,
                v.get("max_abs_entre_metodos_sdv"), "consenso_e2e_veredicto.json",
                tolerancia=0)

    # ---------------- B ----------------
    def alcanza(c, columna):
        """Regla del laboratorio: |lag_env * decimacion - lag_esperado_muestras| <= 12.

        `lag_esperado_muestras` ya almacena -d (convencion del verificador).
        """
        try:
            lag = float(c[columna]) * float(c["decimacion"])
            esp = float(c["lag_esperado_muestras"])
        except (KeyError, TypeError, ValueError):
            return None
        return abs(lag - esp) <= 12

    r = _json("alineacion_resumen.json")
    chk("B", "casos totales", 780, r.get("n_casos"), "alineacion_resumen.json")
    chk("B", "aciertos", 554, r.get("aciertos_1_muestra"), "alineacion_resumen.json")
    chk("B", "falsos positivos", 10, r.get("falsos_positivos"), "alineacion_resumen.json")
    chk("B", "falsos negativos", 0, r.get("falsos_negativos"), "alineacion_resumen.json")

    casos = _csv("alineacion_casos.csv")
    casi = sum(1 for c in casos if (_f(c.get("ratio_real_vs_max")) or 0) > 0.999)
    chk("B", "casos con ratio_real_vs_max > 0.999", 752, casi, "alineacion_casos.csv")

    base = sum(1 for c in casos if alcanza(c, "lag_ganador_env"))
    con_sol = sum(1 for c in casos if alcanza(c, "lag_ganador_con_solape_alto_env"))
    mejoran = sum(1 for c in casos
                  if not alcanza(c, "lag_ganador_env")
                  and alcanza(c, "lag_ganador_con_solape_alto_env"))
    empeoran = sum(1 for c in casos
                   if alcanza(c, "lag_ganador_env")
                   and not alcanza(c, "lag_ganador_con_solape_alto_env"))
    for etq, esp, rec in (("alcance etapa gruesa libre", 554, base),
                          ("alcance con solape >= 90 %", 602, con_sol),
                          ("casos que mejoran", 48, mejoran),
                          ("casos que empeoran", 0, empeoran)):
        filas.append({"bloque": "B", "afirmacion": etq, "declarado": esp,
                      "recalculado": rec, "fuente": "alineacion_casos.csv",
                      "cuadra": esp == rec})

    # L/R del bloque B
    lr = _json("alineacion_lr_asimetrico.json")
    txt = json.dumps(lr)
    for clave, esperado in (("-9.98", -9.98), ("+15.06", 15.06)):
        vals = [v for k, v in _aplanar(lr) if isinstance(v, (int, float))]
        cercano = min(vals, key=lambda x: abs(x - esperado)) if vals else None
        chk("B", f"L/R: valor cercano a {clave} ms", esperado, cercano,
            "alineacion_lr_asimetrico.json", tolerancia=1e-3)

    # ---------------- C ----------------
    aud = _json("mix_delta_auditoria.json")
    busq = aud.get("busqueda_sdi_f2", {})
    chk("C", "SDI_F2 presente en el codigo", False, busq.get("SDI_F2_presente"),
        "mix_delta_auditoria.json")
    chk("C", "patrones buscados para SDI_F2", 3, len(busq.get("patrones", [])),
        "mix_delta_auditoria.json")
    tri = {x["caso"]: x for x in _json("complementariedad_trivial.json")}
    chk("C", "control trivial SDV=mix,SDI=0: SNR de e", 336.87,
        round(tri["trivial_SDV=mix_SDI=0"]["snr_e_db"], 2),
        "complementariedad_trivial.json", tolerancia=1e-3)
    chk("C", "control trivial: e exactamente 0", 0.0,
        tri["trivial_SDV=mix_SDI=0"]["max_abs_e"], "complementariedad_trivial.json",
        tolerancia=0)
    chk("C", "separacion perfecta (SDV=V, SDI=I): SNR de e", 325.83,
        round(tri["correcto_SDV=V_SDI=I"]["snr_e_db"], 2),
        "complementariedad_trivial.json", tolerancia=1e-3)
    deg = _json("complementariedad_guias_degradadas.json")
    d = {x["caso"]: x for x in deg}
    chk("C", "guias atenuadas 0,8", 13.98, round(d["guias_atenuadas_0.8"]["snr_e_db"], 2),
        "complementariedad_guias_degradadas.json", tolerancia=1e-3)
    chk("C", "guias atenuadas + ruido", 11.41,
        round(d["guias_0.8_mas_ruido"]["snr_e_db"], 2),
        "complementariedad_guias_degradadas.json", tolerancia=1e-3)
    rp = _json("delta_identidad_residuo.json")
    peor = max(x["max_abs_residuo_menos_e_id"] for x in rp)
    chk("C", "residuo de la identidad == e_id (max en 3 casos)", 0.0, peor,
        "delta_identidad_residuo.json", tolerancia=0)
    di = _json("delta_identidad.json")["identidad"]["max_abs_diferencia"]
    chk("C", "identidad en caso real: max|d|", 2.98e-08, di, "delta_identidad.json",
        tolerancia=5e-3)

    # ---------------- D ----------------
    dd = _json("bloque_d_orquestador.json")
    chk("D", "fixtures que pasan", 27,
        sum(1 for f in dd["fixtures"] if f["pasa"]), "bloque_d_orquestador.json")
    chk("D", "fixtures totales", 27, len(dd["fixtures"]), "bloque_d_orquestador.json")
    chk("D", "afirmaciones de auditoria confirmadas", 16,
        dd["auditoria"]["confirmados"], "bloque_d_orquestador.json")
    chk("D", "afirmaciones de auditoria totales", 16,
        dd["auditoria"]["total"], "bloque_d_orquestador.json")
    lr = dd["verificaciones_extra"]["lr"]
    chk("D", "max|SDV1 - V_true|", 6.06e-08, lr["max_abs_SDV1_menos_Vtrue"],
        "bloque_d_orquestador.json", tolerancia=5e-3)
    chk("D", "max|SDI1 - I_true|", 5.62e-08, lr["max_abs_SDI1_menos_Itrue"],
        "bloque_d_orquestador.json", tolerancia=5e-3)
    chk("D", "error si se intercambiaran L/R", 0.350,
        round(lr["max_abs_si_se_intercambiaran_LR"], 3), "bloque_d_orquestador.json",
        tolerancia=1e-3)
    chk("D", "frames de salida == frames del mix", True, lr["duracion_igual"],
        "bloque_d_orquestador.json")
    chk("D", "sr de salida == sr del mix", True, lr["sr_salida"] == lr["sr_mix"],
        "bloque_d_orquestador.json")
    chk("D", "subtype de salida", "FLOAT", lr["subtype_salida"],
        "bloque_d_orquestador.json")
    return filas


def literales():
    """Comprueba que la cifra recalculada APAREZCA en el texto del documento.

    Cierra el hueco del resto de comprobaciones: `cifras()` contrasta los artefactos
    entre si; esto contrasta artefacto -> documento (formato espanol, coma decimal).
    """
    def es(x, dec=2):
        return f"{x:.{dec}f}".replace(".", ",")

    pruebas = []

    def p(doc, valor, fuente, dec=2, alias=None):
        ruta = os.path.join(RAIZ, doc)
        if not os.path.isfile(ruta):
            pruebas.append({"documento": doc, "literal": None, "aparece": False,
                            "valor": valor, "fuente": fuente, "motivo": "doc ausente"})
            return
        txt = open(ruta, encoding="utf-8").read()
        cand = alias or [es(valor, dec)]
        hit = next((c for c in cand if c in txt), None)
        pruebas.append({"documento": doc, "literal": hit, "candidatos": cand,
                        "aparece": hit is not None, "valor": valor, "fuente": fuente})

    tri = {x["caso"]: x for x in _json("complementariedad_trivial.json")}
    p("FORMULA_AUDIT.md", tri["trivial_SDV=mix_SDI=0"]["snr_e_db"],
      "complementariedad_trivial.json")
    p("REPORT.md", tri["trivial_SDV=mix_SDI=0"]["snr_e_db"],
      "complementariedad_trivial.json")
    p("FORMULA_AUDIT.md", tri["correcto_SDV=V_SDI=I"]["snr_e_db"],
      "complementariedad_trivial.json")
    deg = {x["caso"]: x for x in _json("complementariedad_guias_degradadas.json")}
    p("FORMULA_AUDIT.md", deg["guias_atenuadas_0.8"]["snr_e_db"],
      "complementariedad_guias_degradadas.json")
    p("REPORT.md", deg["guias_atenuadas_0.8"]["snr_e_db"],
      "complementariedad_guias_degradadas.json")
    p("FORMULA_AUDIT.md", deg["guias_0.8_mas_ruido"]["snr_e_db"],
      "complementariedad_guias_degradadas.json")

    casos = _csv("alineacion_casos.csv")
    for doc in ("ALIGNMENT_DIAGNOSTICS.md", "REPORT.md", "README.md"):
        p(doc, 780, "alineacion_casos.csv", dec=0)
    p("ALIGNMENT_DIAGNOSTICS.md", 554, "alineacion_casos.csv", dec=0)
    p("ALIGNMENT_DIAGNOSTICS.md", 602, "alineacion_casos.csv", dec=0)
    p("REPORT.md", 554, "alineacion_casos.csv", dec=0)
    p("REPORT.md", 602, "alineacion_casos.csv", dec=0)

    dd = _json("bloque_d_orquestador.json")
    lr = dd["verificaciones_extra"]["lr"]
    p("ORCHESTRATOR_SPEC.md", lr["max_abs_si_se_intercambiaran_LR"],
      "bloque_d_orquestador.json", dec=3)
    p("REPORT.md", lr["max_abs_si_se_intercambiaran_LR"], "bloque_d_orquestador.json",
      dec=3)

    sr48 = _json("bloque_d_demo_sr48_real.json")
    p("ORCHESTRATOR_SPEC.md", 100 * (1 - sr48["factor_pitch"]),
      "bloque_d_demo_sr48_real.json", dec=2)

    for doc in ("ORCHESTRATOR_SPEC.md", "REPORT.md", "README.md"):
        n_ok = sum(1 for f in dd["fixtures"] if f["pasa"])
        p(doc, n_ok, "bloque_d_orquestador.json", dec=0, alias=[f"{n_ok}/{n_ok}"])
    return pruebas


def _aplanar(o, pref=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _aplanar(v, f"{pref}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _aplanar(v, f"{pref}[{i}]")
    else:
        yield pref, o


# ------------------------------------------------------------- C. referencias
PATRON = re.compile(r"`([A-Za-z0-9_./-]+\.(?:py|md|json|csv|jsonl|txt|svg|zip))`")

# Nombres que designan FUENTES INMUTABLES: viven en el ZIP de origen, no en este paquete.
FUENTES_EXTERNAS = {
    "MOTOR_SEP_SDV-SDI.py", "MOTOR_SEP_SDV-SDI_EVO.py",
    "MOTOR_SEP_SDV-SDI_v3.py", "MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py",
    "sdv_sdi_mqr_engine.py", "mix_delta.py", "orquestador_maestro.py",
    "preflight_audit.py", "MANIFEST_SEP_SDV-SDI.json", "manifest_genio.json",
    "INTEGRIDAD_FUENTES.json",
}
# Nombres generados en tiempo de ejecucion, no distribuidos.
GENERADOS = {"manifest_orquestador.json"}
# Busqueda de nombres sueltos en estas carpetas del paquete.
BUSCAR_EN = ["", "results", "src", "src/orchestrator_spec", "configs", "tests",
             "fixtures", "hashes", "manifests", "results/logs"]


def referencias():
    faltan, vistas = [], 0
    externas, generados = set(), set()
    for doc in sorted(x for x in os.listdir(RAIZ) if x.endswith(".md")):
        with open(os.path.join(RAIZ, doc), encoding="utf-8") as fh:
            texto = fh.read()
        for m in PATRON.finditer(texto):
            ruta = m.group(1)
            if ruta.startswith(("http", "/home")):
                continue
            vistas += 1
            base = os.path.basename(ruta)
            if os.path.exists(os.path.join(RAIZ, ruta)):
                continue
            if base in FUENTES_EXTERNAS:
                externas.add(base)
                continue
            if base in GENERADOS:
                generados.add(base)
                continue
            if any(os.path.isfile(os.path.join(RAIZ, d, base)) for d in BUSCAR_EN):
                continue
            if any(ruta.startswith(e) or ruta == e for e in EXCEPCIONES):
                continue
            faltan.append({"documento": doc, "ruta": ruta})
    return {"referencias_comprobadas": vistas, "faltantes": faltan,
            "referencias_externas": sorted(externas),
            "referencias_generadas_al_ejecutar": sorted(generados)}


# -------------------------------------------------------------- A. estructura
def estructura():
    faltan = [p for p in ESTRUCTURA if not os.path.exists(os.path.join(RAIZ, p))]
    return {"exigidos": len(ESTRUCTURA), "faltan": faltan}


def main():
    est = estructura()
    cif = cifras()
    ref = referencias()
    lit = literales()
    lit_mal = [x for x in lit if not x["aparece"]]

    malas = [c for c in cif if not c["cuadra"]]
    print(f"[A] estructura : {est['exigidos'] - len(est['faltan'])}/{est['exigidos']}"
          f"{'' if not est['faltan'] else '  FALTAN: ' + str(est['faltan'])}")
    print(f"[B] cifras      : {len(cif) - len(malas)}/{len(cif)} cuadran")
    for m in malas:
        print(f"     NO CUADRA  [{m['bloque']}] {m['afirmacion']}: "
              f"declarado {m['declarado']} vs recalculado {m['recalculado']}")
    print(f"[C] referencias : {ref['referencias_comprobadas']} comprobadas, "
          f"{len(ref['faltantes'])} rotas, "
          f"{len(ref['referencias_externas'])} a fuentes externas (esperadas), "
          f"{len(ref['referencias_generadas_al_ejecutar'])} generadas al ejecutar")
    for f in ref["faltantes"]:
        print(f"     ROTA  {f['documento']} -> {f['ruta']}")

    print(f"[D] literales   : {len(lit) - len(lit_mal)}/{len(lit)} cifras aparecen en su "
          f"documento")
    for x in lit_mal:
        print(f"     NO APARECE  {x['documento']}: se esperaba "
              f"{x.get('literal') or x.get('candidatos')} ({x['fuente']})")

    doc = {"estructura": est, "cifras": cif, "referencias": ref, "literales": lit}
    with open(os.path.join(RES, "coherencia.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    ok = (not est["faltan"] and not malas and not ref["faltantes"] and not lit_mal)
    print(f"\n[{'OK' if ok else 'FALLO'}] coherencia -> results/coherencia.json")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
