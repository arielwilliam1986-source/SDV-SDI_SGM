"""Fase 3: agrupar solo ficheros de la misma ejecucion/modelo/corrida."""
from collections import defaultdict


def agrupar(clasificacion, mix_meta=None) -> list:
    """Clave de grupo = (perfil, run, carpeta). Nunca se mezclan corridas distintas."""
    grupos = defaultdict(lambda: {"roles": defaultdict(list), "ambiguos": [],
                                  "sin_rol": []})
    for f in clasificacion["ficheros"]:
        if f["estado"] == "AMBIGUO":
            clave = (str(f.get("perfil")), f.get("run") or "", f["dir"])
            grupos[clave]["ambiguos"].append(f)
            continue
        if f["estado"] == "SIN_ROL":
            clave = ("", "", f["dir"])
            grupos[clave]["sin_rol"].append(f)
            continue
        grupos[(f["perfil"], f["run"], f["dir"])]["roles"][f["rol"]].append(f)

    out = []
    for (perfil, run, carpeta), g in sorted(grupos.items()):
        roles = {r: sorted(v, key=lambda x: x["rel"]) for r, v in g["roles"].items()}
        duplicados = {r: [x["rel"] for x in v] for r, v in roles.items() if len(v) > 1}
        out.append({
            "grupo_id": f"{perfil or 'SIN_PERFIL'}::{run or '-'}::{carpeta or '.'}",
            "perfil": perfil, "run": run, "carpeta": carpeta,
            "roles": roles,
            "roles_presentes": sorted(roles),
            "roles_ausentes_esperados": [],
            "duplicados": duplicados,
            "ambiguos": g["ambiguos"],
            "sin_rol": g["sin_rol"],
        })
    return out


def roles_esperados(perfil: dict) -> list:
    return sorted(perfil.get("roles", {}))


def estado_preliminar(grupo: dict) -> str:
    """AMBIGUOUS si hay duplicados o ficheros ambiguos o Sin rol en la carpeta."""
    if grupo["duplicados"] or grupo["ambiguos"] or grupo["sin_rol"]:
        return "AMBIGUOUS"
    return "OK"
