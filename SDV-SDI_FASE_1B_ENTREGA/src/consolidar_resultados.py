"""Consolida los resultados de los cuatro bloques en el formato de entrega:
`results/results.csv`, `results/results.json` y `results/raw.jsonl`.

No recalcula nada: lee los artefactos ya producidos y los normaliza. Los registros que
faltan se declaran como tales en lugar de inventarse.
"""
import csv
import glob
import json
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, "results")

COLS = ["bloque", "conjunto", "caso", "clave", "valor", "estado", "fuente"]


def _cargar(nombre):
    p = os.path.join(RES, nombre)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        if nombre.endswith(".jsonl"):
            return [json.loads(x) for x in fh if x.strip()]
        return json.load(fh)


def _csv(nombre):
    p = os.path.join(RES, nombre)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def registros():
    reg = []

    def add(bloque, conjunto, caso, filas):
        for k, v, est in filas:
            reg.append({"bloque": bloque, "conjunto": conjunto, "caso": caso,
                        "clave": k, "valor": v, "estado": est,
                        "fuente": f"results/{conjunto}"})

    # ---------------------------------------------------------------- A
    inv = _cargar("consenso_inventario.json")
    if isinstance(inv, dict):
        for motor, f in inv.items():
            add("A", "consenso_inventario.json", motor,
                [("fichero", f.get("fichero"), "DOCUMENTED_FACT"),
                 ("n_lineas", f.get("n_lineas"), "DOCUMENTED_FACT"),
                 ("cli_consensus_linea", f.get("cli_consensus_linea"), "DOCUMENTED_FACT"),
                 ("cli_consensus_order_linea", f.get("cli_consensus_order_linea"),
                  "DOCUMENTED_FACT")])
    for f in _csv("consenso_e2e.csv"):
        caso = f"{f.get('motor','?')}__{f.get('order','?')}__{f.get('metodo','?')}__K{f.get('K','?')}"
        add("A", "consenso_e2e.csv", caso,
            [("rc", f.get("rc"), "EXPERIMENTAL_RESULT"),
             ("elapsed_s", f.get("elapsed_s"), "EXPERIMENTAL_RESULT"),
             ("sha_audio_sdv", (f.get("sha_audio_sdv") or "")[:16], "EXPERIMENTAL_RESULT"),
             ("sha_audio_sdi", (f.get("sha_audio_sdi") or "")[:16], "EXPERIMENTAL_RESULT"),
             ("sha_fichero_sdv", (f.get("sha_fichero_sdv") or "")[:16],
              "EXPERIMENTAL_RESULT")])
    for f in _csv("consenso_mallas.csv"):
        caso = f"{f.get('modelo','?')}__K{f.get('K','?')}"
        add("A", "consenso_mallas.csv", caso,
            [("identicos_3", f.get("identicos_3"), "EXPERIMENTAL_RESULT"),
             ("max_abs_wm_vs_cwm", f.get("max_abs_wm_vs_cwm"), "EXPERIMENTAL_RESULT"),
             ("max_abs_wm_vs_med", f.get("max_abs_wm_vs_med"), "EXPERIMENTAL_RESULT"),
             ("c_k_media", f.get("c_k_media"), "EXPERIMENTAL_RESULT"),
             ("c_k_min", f.get("c_k_min"), "EXPERIMENTAL_RESULT")])
    for f in _csv("consenso_complejo.csv"):
        caso = f"{f.get('modelo','?')}__K{f.get('K','?')}"
        add("A", "consenso_complejo.csv", caso,
            [("n_metodos", f.get("n_metodos"), "EXPERIMENTAL_RESULT"),
             ("max_dif_entre_metodos", f.get("max_dif_entre_metodos"),
              "EXPERIMENTAL_RESULT"),
             ("identicos_4", f.get("identicos_4"), "EXPERIMENTAL_RESULT")])
    met = _cargar("consenso_e2e_metodo.json")
    if met:
        add("A", "consenso_e2e_metodo.json", "sha_fichero_no_sirve",
            [("metodo", met.get("conclusion", met.get("nota", "")), "DOCUMENTED_FACT")])

    # ---------------------------------------------------------------- B
    res_b = _cargar("alineacion_resumen.json")
    if res_b:
        for k, v in res_b.items():
            if isinstance(v, (int, float, str, bool)):
                add("B", "alineacion_resumen.json", "global",
                    [(k, v, "EXPERIMENTAL_RESULT")])
    for i, f in enumerate(_csv("alineacion_casos.csv")):
        caso = (f"{f.get('motor','?')}|{f.get('contenido','?')}|{f.get('dur_s','?')}s"
                f"|d{f.get('retardo_real_ms','?')}|{i}")
        add("B", "alineacion_casos.csv", caso,
            [("retardo_real_muestras", f.get("retardo_real_muestras"),
              "EXPERIMENTAL_RESULT"),
             ("lag_esperado_muestras", f.get("lag_esperado_muestras"),
              "EXPERIMENTAL_RESULT"),
             ("lag_ganador_env", f.get("lag_ganador_env"), "EXPERIMENTAL_RESULT"),
             ("clase", f.get("clase"), "EXPERIMENTAL_RESULT"),
             ("acierto_1muestra", f.get("acierto_1muestra"), "EXPERIMENTAL_RESULT"),
             ("falso_positivo", f.get("falso_positivo"), "EXPERIMENTAL_RESULT"),
             ("falso_negativo", f.get("falso_negativo"), "EXPERIMENTAL_RESULT"),
             ("ratio_real_vs_max", f.get("ratio_real_vs_max"), "EXPERIMENTAL_RESULT"),
             ("solape_ganador", f.get("solape_ganador"), "EXPERIMENTAL_RESULT")])

    # ---------------------------------------------------------------- C
    aud = _cargar("mix_delta_auditoria.json")
    if aud:
        add("C", "mix_delta_auditoria.json", "sdi_f2",
            [("presente", aud.get("sdi_f2_presente"), "UNKNOWN"),
             ("apariciones", aud.get("sdi_f2_apariciones"), "UNKNOWN")])
    tri = _cargar("complementariedad_trivial.json") or []
    for c in tri:
        add("C", "complementariedad_trivial.json", c.get("caso", "?"),
            [("snr_e_db", c.get("snr_e_db"), "EXPERIMENTAL_RESULT"),
             ("complementaria", c.get("complementaria_100dB"), "EXPERIMENTAL_RESULT"),
             ("separacion", c.get("separacion_real"), "EXPERIMENTAL_RESULT")])
    for nombre in ("complementariedad.json", "complementariedad_guias_degradadas.json"):
        for c in _cargar(nombre) or []:
            add("C", nombre, c.get("rama") or c.get("caso", "?"),
                [("snr_e_db", c.get("snr_e_db"), "EXPERIMENTAL_RESULT"),
                 ("max_abs_e", c.get("max_abs_e"), "EXPERIMENTAL_RESULT")])
    for c in _cargar("mix_delta_guardas.json") or []:
        add("C", "mix_delta_guardas.json", c.get("caso", "?"),
            [("rc", c.get("rc"), "EXPERIMENTAL_RESULT"),
             ("salida_escrita", c.get("out_existe"), "EXPERIMENTAL_RESULT")])
    for c in _cargar("delta_identidad_residuo.json") or []:
        add("C", "delta_identidad_residuo.json", c.get("caso", "?"),
            [("max_abs_residuo", c.get("max_abs_residuo"), "EXPERIMENTAL_RESULT"),
             ("residuo_igual_e_id", c.get("identidad_exacta"), "EXPERIMENTAL_RESULT")])

    # ---------------------------------------------------------------- D
    d = _cargar("bloque_d_orquestador.json")
    if d:
        for h in d.get("auditoria", {}).get("hallazgos", []):
            add("D", "bloque_d_orquestador.json", h["id"],
                [("afirmacion", h["afirmacion"], "DOCUMENTED_FACT"),
                 ("linea", h.get("linea"), "DOCUMENTED_FACT"),
                 ("confirmado", h.get("confirmado"), "DOCUMENTED_FACT")])
        for x in d.get("demos_original", []):
            add("D", "bloque_d_orquestador.json", x.get("demo", "?"),
                [("rc", x.get("rc"), "EXPERIMENTAL_RESULT"),
                 ("pares", x.get("n_pares"), "EXPERIMENTAL_RESULT"),
                 ("observado", x.get("observado"), "EXPERIMENTAL_RESULT")])
        for f in d.get("fixtures", []):
            add("D", "bloque_d_orquestador.json", f.get("caso", "?"),
                [("estado", f.get("estado"), "EXPERIMENTAL_RESULT"),
                 ("esperado", f.get("esperado"), "EXPERIMENTAL_RESULT"),
                 ("pasa", f.get("pasa"), "EXPERIMENTAL_RESULT"),
                 ("formulas", ",".join(f.get("formulas") or []), "EXPERIMENTAL_RESULT")])
        for t in d.get("tests_unitarios", []):
            add("D", "bloque_d_orquestador.json", t.get("test", "?"),
                [("pasa", t.get("pasa"), "EXPERIMENTAL_RESULT")])
        lr = d.get("verificaciones_extra", {}).get("lr")
        if lr:
            for k, v in lr.items():
                add("D", "bloque_d_orquestador.json", "lr_asimetrico",
                    [(k, v, "EXPERIMENTAL_RESULT")])
    for nombre in ("bloque_d_demos_medidos.json", "bloque_d_demo_sr48_real.json"):
        x = _cargar(nombre)
        if isinstance(x, dict):
            for k, v in x.items():
                if isinstance(v, (int, float, str, bool)):
                    add("D", nombre, "global", [(k, v, "EXPERIMENTAL_RESULT")])
    return reg


def main():
    reg = registros()
    os.makedirs(RES, exist_ok=True)

    with open(os.path.join(RES, "raw.jsonl"), "w", encoding="utf-8") as fh:
        for r in reg:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open(os.path.join(RES, "results.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in reg:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in COLS})

    por_bloque = {}
    for r in reg:
        b = por_bloque.setdefault(r["bloque"], {"registros": 0, "claves": set(),
                                                "estados": {}})
        b["registros"] += 1
        b["claves"].add(r["conjunto"])
        b["estados"][r["estado"]] = b["estados"].get(r["estado"], 0) + 1

    d = _cargar("bloque_d_orquestador.json") or {}
    resumen = {
        "fase": "1B",
        "generado_desde": "resultados crudos de los bloques A-D",
        "n_registros": len(reg),
        "por_bloque": {k: {"registros": v["registros"], "claves": sorted(v["claves"]),
                           "estados": v["estados"]} for k, v in sorted(por_bloque.items())},
        "veredictos": {
            "A": {"estado": "cerrado",
                  "hecho": "solo masks_first/hybrid_asymmetric/v3 cambian la operacion"},
            "B": {"estado": "diagnostico experimental cerrado",
                  "cifra": "554/780 aciertos; 2 propuestas NO aplicadas"},
            "C": {"SDI_F2": "UNKNOWN",
                  "hecho": "residuo de la identidad = e_id exacto"},
            "D": {"fixtures_ok": sum(1 for f in d.get("fixtures", []) if f.get("pasa")),
                  "fixtures_total": len(d.get("fixtures", [])),
                  "auditoria_confirmados": d.get("auditoria", {}).get("confirmados"),
                  "auditoria_total": d.get("auditoria", {}).get("total")},
        },
        "faltantes_declarados": [],
    }
    for esperado in ("consenso_inventario.json", "alineacion_resumen.json",
                     "mix_delta_auditoria.json", "bloque_d_orquestador.json",
                     "consenso_e2e.csv", "alineacion_casos.csv"):
        if not os.path.isfile(os.path.join(RES, esperado)):
            resumen["faltantes_declarados"].append(esperado)

    with open(os.path.join(RES, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, indent=1, ensure_ascii=False)

    print(f"raw.jsonl  : {len(reg)} registros")
    print(f"results.csv: {len(reg)} filas x {len(COLS)} columnas")
    for b, v in sorted(por_bloque.items()):
        print(f"  bloque {b}: {v['registros']:5d} registros  {sorted(v['claves'])}")
    if resumen["faltantes_declarados"]:
        print("  FALTAN:", resumen["faltantes_declarados"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
