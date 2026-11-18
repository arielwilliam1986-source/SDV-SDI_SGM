"""Fase 2: asignar a cada fichero un ROL semantico con evidencia del patron.

Reglas duras:
  * Nunca se clasifica por substring generico. Cada patron es una regex anclada
    declarada en el perfil.
  * Un patron puede declarar `excluye`: si alguna de esas regex casa, el patron NO
    aplica. Asi `[C]` agregado no puede tragarse `Reverb [C]` ni `Others [C]`.
  * Si dos patrones de igual prioridad asignan el mismo fichero a roles distintos,
    el fichero queda AMBIGUO (no se elige el primero que aparezca).
"""
import re


def _compilar(perfiles):
    comp = []
    for p in perfiles:
        pid = p["model_id"]
        for rol, patrones in p["roles"].items():
            for i, pat in enumerate(patrones):
                comp.append({
                    "perfil": pid, "rol": rol, "indice": i,
                    "re": re.compile(pat["regex"]),
                    "exc": [re.compile(x) for x in pat.get("excluye", [])],
                    "prio": int(pat.get("prioridad", 0)),
                    "regex": pat["regex"],
                })
    return comp


def clasificar(ficheros, doc_perfiles) -> dict:
    """Devuelve por fichero el rol asignado, la evidencia y los descartados."""
    comp = _compilar(doc_perfiles["perfiles"])
    reglas_prioridad = doc_perfiles.get("resolucion", {})
    resultados, ambiguos = [], []

    for it in ficheros:
        nombre = it["nombre"]
        cands = []
        for c in comp:
            m = c["re"].search(nombre)
            if not m:
                continue
            if any(x.search(nombre) for x in c["exc"]):
                continue                      # exclusion explicita del perfil
            try:
                run = m.group("run") or ""
            except IndexError:
                run = ""
            cands.append({"perfil": c["perfil"], "rol": c["rol"], "prio": c["prio"],
                          "regex": c["regex"], "run": run})
        if not cands:
            resultados.append(dict(it, rol=None, estado="SIN_ROL", evidencia=None,
                                   descartados=[]))
            continue
        # prioridad: mayor primero; empate entre roles distintos => AMBIGUO
        top = max(c["prio"] for c in cands)
        mejores = [c for c in cands if c["prio"] == top]
        roles = {(c["perfil"], c["rol"]) for c in mejores}
        descartados = [c for c in cands if c["prio"] < top]
        if len(roles) > 1:
            fila = dict(it, rol=None, estado="AMBIGUO", evidencia=mejores,
                        descartados=descartados)
            resultados.append(fila)
            ambiguos.append({"rel": it["rel"], "candidatos": mejores})
            continue
        g = mejores[0]
        resultados.append(dict(it, rol=g["rol"], perfil=g["perfil"], run=g["run"],
                               estado="CLASIFICADO", prioridad=g["prio"],
                               evidencia={"regex": g["regex"], "perfil": g["perfil"]},
                               descartados=descartados))
    return {"ficheros": resultados, "ambiguos": ambiguos,
            "resolucion": reglas_prioridad}
