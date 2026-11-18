"""Composicion de las 9 fases: inventario -> clasificacion -> agrupacion ->
validacion -> C_total -> residuales -> manifiesto.

No importa `orquestador_maestro.py` ni escribe dentro del arbol de entrada.
"""
import os
import re

import numpy as np

from . import agrupador, c_total, clasificador, inventario, manifiesto
from . import perfiles as P
from . import residuales as R
from . import validador as V

PRECEDENCIA = ["ACCEPT", "INCOMPLETE", "AMBIGUOUS", "INCOMPATIBLE", "REJECTED"]


_ALIAS = {"OK": "ACCEPT", "NO_APLICA": None, "LISTO": "ACCEPT"}


def _peor(estados):
    peor = "ACCEPT"
    for e in estados:
        e = _ALIAS.get(e, e)
        if e is None:
            continue
        if e not in PRECEDENCIA:
            raise ValueError(f"estado fuera de vocabulario: {e!r}")
        if peor not in PRECEDENCIA or PRECEDENCIA.index(e) > PRECEDENCIA.index(peor):
            peor = e
    return peor


def _mix_candidatos(ficheros, patrones):
    regs = [re.compile(p) for p in patrones]
    return [f for f in ficheros if any(r.search(f["nombre"]) for r in regs)]


def ejecutar(dirbase, perfiles_path, mix_nombre=None, out_dir=None,
             estricto_subtype=True, generar=True, solo_grupos=None,
             mix_sha_esperado=None) -> dict:
    doc = P.cargar_perfiles(perfiles_path)
    ext = doc.get("extensiones", [".wav"])
    inv = inventario.inventariar(dirbase, ext)
    cands = _mix_candidatos(inv["ficheros"], doc.get("mix_patrones", ["^Mix"]))
    vm = V.validar_mix(dirbase, mix_nombre, {"candidatos": cands},
                       sha_esperado=mix_sha_esperado)
    if not vm["ok"]:
        return {"estado": "REJECTED", "motivo": vm["motivo"],
                "mix": vm, "inventario": _inv_resumen(inv), "grupos": [], "manifiesto": None}

    mix_meta = V.meta(vm["ruta"])
    mix_sha = inventario.sha256(vm["ruta"])
    if not V.es_finito(vm["ruta"]):
        return {"estado": "REJECTED", "motivo": "el Mix contiene NaN/Inf",
                "mix": vm, "inventario": _inv_resumen(inv), "grupos": [], "manifiesto": None}
    M, sr_mix = V.leer(vm["ruta"])

    resto = [f for f in inv["ficheros"] if f["ruta"] != vm["ruta"]]
    clas = clasificador.clasificar(resto, doc)
    grupos = agrupador.agrupar(clas)
    perfiles_por_id = {p["model_id"]: p for p in doc["perfiles"]}

    salidas, grupos_man = [], []
    for g in grupos:
        if g["perfil"] not in perfiles_por_id:
            if g["sin_rol"] or g["perfil"] == "":
                grupos_man.append({"grupo_id": "SIN_PERFIL", "estado": "REJECTED",
                                   "motivos": ["ficheros sin rol semantico: no se procesan"],
                                   "ficheros": [f["rel"] for f in g["sin_rol"]]})
            continue
        perfil = perfiles_por_id[g["perfil"]]
        if solo_grupos and g["run"] not in solo_grupos:
            continue
        salidas.append(_procesar_grupo(g, perfil, M, sr_mix, mix_meta,
                                      vm['ruta'], dirbase, out_dir, generar))
        grupos_man.append(salidas[-1])

    estados = [x["estado"] for x in salidas] or ["ACCEPT"]
    man = manifiesto.construir(dirbase, {
        "ruta": vm.get("rel"), "sha256": mix_sha, **mix_meta}, grupos_man, doc,
        {"estricto_subtype": estricto_subtype, "generar": generar})
    return {"estado": _peor(estados), "motivo": "",
            "inventario": _inv_resumen(inv), "mix": {"ruta": vm.get("rel"),
            "sha256": mix_sha, **mix_meta}, "grupos": salidas,
            "manifiesto": manifiesto.escribir(
                os.path.join(out_dir, "manifest_orquestador.json"), man) if out_dir else None}


def _inv_resumen(inv):
    return {"n_ficheros": inv["n_ficheros"], "n_ignorados": inv["n_ignorados"],
            "ignorados": [{"rel": x["rel"], "motivo": x.get("motivo")}
                          for x in inv["ignorados"]]}


def _procesar_grupo(g, perfil, M, sr_mix, mix_meta, mix_ruta, dirbase,
                    out_dir, generar) -> dict:
    roles_f = g["roles"]
    out = {"grupo_id": g["grupo_id"], "perfil": perfil["model_id"],
           "run": g["run"], "carpeta": g["carpeta"],
           "roles_presentes": g["roles_presentes"], "duplicados": g["duplicados"],
           "ambiguos": [x["rel"] for x in g["ambiguos"]],
           "sin_rol": [x["rel"] for x in g["sin_rol"]],
           "residuales": [], "no_generados": {}, "motivos": []}

    # ---- C_total (fase 7) ----
    ct = c_total.construir(roles_f, perfil)
    out["c_total"] = {"estado": ct["estado"], "estrategia": ct["estrategia"],
                      "formula": ct.get("formula"), "sumandos": ct["sumandos"],
                      "motivos": ct["motivos"]}

    # ---- ambiguedad estructural ----
    if g["duplicados"] or g["ambiguos"]:
        out["estado"] = "AMBIGUOUS"
        out["motivos"].append("duplicados o ficheros con rol ambiguo: no se elige ninguno")
        return out
    if ct["estado"] == "AMBIGUOUS":
        out["estado"] = "AMBIGUOUS"
        out["motivos"] += ct["motivos"]
        return out

    # ---- plan de formulas (fase 8) ----
    plan = R.planificar(g["roles_presentes"], ct["estado"], perfil)
    for nombre, p in plan.items():
        if p["estado"] not in ("LISTO", "NO_APLICA"):
            out["no_generados"][nombre] = p
        elif p["estado"] == "NO_APLICA":
            out.setdefault("no_aplica", {})[nombre] = p["motivo"]
    listos = [n for n, p in plan.items() if p["estado"] == "LISTO"]
    if not listos:
        out["estado"] = "INCOMPLETE"
        out["motivos"] += ["ninguna formula tiene insumos completos"]
        return out

    # ---- validacion estricta por formula (fase 5) ----
    validos, incompat = [], {}
    for nombre in listos:
        req = list(R.FORMULAS[nombre]["req"])
        items = [("MIX", mix_ruta)]
        faltan = []
        for r in req:
            if r == "C_TOTAL":
                for s in ct["sumandos"]:
                    items.append((f"C_TOTAL/{s['rol']}", os.path.join(dirbase, s["rel"])))
                continue
            items.append((r, os.path.join(dirbase, roles_f[r][0]["rel"])))
        faltan = [e for e, p in items if not os.path.isfile(p)]
        if faltan:
            incompat[nombre] = {"estado": "INCOMPATIBLE",
                                "motivo": f"ruta de insumo inexistente: {faltan}"}
            continue
        v = V.validar_entradas(items)
        if not v["ok"]:
            estado = "REJECTED" if v.get("rechazado") else "INCOMPATIBLE"
            incompat[nombre] = {"estado": estado, "motivos": v["motivos"]}
            continue
        validos.append(nombre)
    for nombre, info in incompat.items():
        out["no_generados"][nombre] = info
    if not validos:
        out["estado"] = "INCOMPATIBLE"
        out["motivos"] += sorted({m for x in incompat.values()
                                  for m in x.get("motivos", [x.get("motivo", "")])})
        return out

    # ---- carga SELECTIVA de los insumos necesarios, con guardas ----
    # Nunca se cargan roles que no intervienen, para que un fichero corrupto o
    # incomensurable no tumbe formulas que no lo usan.
    def _ruta_rol(rol):
        return os.path.join(dirbase, roles_f[rol][0]["rel"])

    necesarios = set()
    for nombre in validos:
        necesarios.update(r for r in R.FORMULAS[nombre]["req"] if r != "C_TOTAL")

    roles_arr, errores = {}, {}
    for r in sorted(necesarios):
        try:
            arr = V.leer(_ruta_rol(r))[0]
        except Exception as e:                                    # noqa: BLE001
            errores[r] = ("REJECTED", f"{r}: no se puede leer ({type(e).__name__})")
            continue
        if arr.shape != M.shape:
            errores[r] = ("INCOMPATIBLE",
                          f"{r}: forma {arr.shape} != mix {tuple(M.shape)} "
                          "(no se trunca ni se emite")
            continue
        roles_arr[r] = arr

    c_arr = ct.get("C_total")
    if c_arr is not None and c_arr.shape != M.shape:
        errores["C_TOTAL"] = ("INCOMPATIBLE",
                              f"C_total: forma {c_arr.shape} != mix {tuple(M.shape)}")
        c_arr = None

    validos2 = []
    for nombre in validos:
        req = [r for r in R.FORMULAS[nombre]["req"] if r != "C_TOTAL"]
        if "C_TOTAL" in R.FORMULAS[nombre]["req"] and "C_TOTAL" in errores:
            req = req + ["C_TOTAL"]
        fallos = [r for r in req if r in errores]
        if fallos:
            estado = ("REJECTED" if any(errores[r][0] == "REJECTED" for r in fallos)
                      else "INCOMPATIBLE")
            incompat[nombre] = {"estado": estado,
                                "motivos": [errores[r][1] for r in fallos]}
            out["no_generados"][nombre] = incompat[nombre]
        else:
            validos2.append(nombre)
    validos = validos2
    if not validos:
        out["estado"] = _peor([incompat[n]["estado"] for n in incompat] or ["INCOMPATIBLE"])
        out["motivos"] += sorted({m for x in incompat.values() for m in x["motivos"]})
        return out

    plan_valido = {n: dict(plan[n], estado="LISTO") for n in validos}
    if generar:
        pref = f"{perfil['model_id']}__{g['run'] or 'run'}"
        out["residuales"] = R.generar(plan_valido, roles_arr, M, c_arr, sr_mix,
                                      os.path.join(out_dir, _slug(pref)), pref)

    # ---- E vs C_total + D (solo medicion) ----
    if ({"E_VOCALS", "D_DRY_VOCAL"} <= set(roles_arr) and c_arr is not None
            and all(roles_arr[r].shape == M.shape for r in ("E_VOCALS", "D_DRY_VOCAL"))):
        out["e_vs_c_total_d"] = R.medir_e_vs_c_total_d(
            roles_arr["E_VOCALS"], c_arr, roles_arr["D_DRY_VOCAL"])

    est_nombres = [x.get("estado", "ACCEPT") for x in out["residuales"]]
    est_nombres += [v.get("estado", "ACCEPT") for v in out["no_generados"].values()]
    out["estado"] = _peor(est_nombres) if est_nombres else "INCOMPLETE"
    if not out["residuales"] and out["estado"] == "ACCEPT":
        out["estado"] = "INCOMPLETE"
    return out


def _slug(s):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s)
