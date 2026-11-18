"""Registro de perfiles semanticos por modelo.

Un perfil declara, en datos, como se llaman los ficheros de cada ROL en una familia
de modelos. El codigo de calculo no conoce ningun nombre de modelo: solo roles.
"""
import json
import re

ESQUEMA = "orchestrator_profile/1"

ROLES = {
    "INSTRUMENTAL", "VOCALS",
    "A_RESTORED", "B_INSTRUMENT", "C_AGGREGATE", "C_REVERB", "C_OTHERS",
    "D_DRY_VOCAL", "E_VOCALS",
}
ESTRATEGIAS_C = {"single_aggregate", "split_reverb_others"}
CAMPOS_OBLIGATORIOS = {"model_id", "version", "roles"}


class PerfilInvalido(ValueError):
    pass


def validar_perfil(p: dict, i: int) -> list:
    err = []
    falta = CAMPOS_OBLIGATORIOS - set(p)
    if falta:
        err.append(f"perfil[{i}]: faltan campos {sorted(falta)}")
        return err
    if not isinstance(p["roles"], dict) or not p["roles"]:
        err.append(f"perfil[{i}] ({p.get('model_id')}): 'roles' vacio")
    for rol, patrones in p["roles"].items():
        if rol not in ROLES:
            err.append(f"perfil[{i}]: rol desconocido '{rol}' (validos: {sorted(ROLES)})")
            continue
        if not isinstance(patrones, list) or not patrones:
            err.append(f"perfil[{i}]: rol {rol} sin patrones")
            continue
        for j, pat in enumerate(patrones):
            if "regex" not in pat:
                err.append(f"perfil[{i}] {rol}[{j}]: falta 'regex'")
                continue
            try:
                re.compile(pat["regex"])
            except re.error as e:
                err.append(f"perfil[{i}] {rol}[{j}]: regex invalida ({e})")
            for ex in pat.get("excluye", []):
                try:
                    re.compile(ex)
                except re.error as e:
                    err.append(f"perfil[{i}] {rol}[{j}]: 'excluye' invalida ({e})")
    est = p.get("estrategia_c")
    if est is not None and est not in ESTRATEGIAS_C:
        err.append(f"perfil[{i}]: estrategia_c '{est}' no valida")
    return err


def cargar_perfiles(ruta: str) -> dict:
    with open(ruta, encoding="utf-8") as fh:
        doc = json.load(fh)
    if doc.get("schema") != ESQUEMA:
        raise PerfilInvalido(f"esquema {doc.get('schema')!r} != {ESQUEMA!r}")
    perfiles = doc.get("perfiles") or []
    if not perfiles:
        raise PerfilInvalido("no hay perfiles")
    errores = []
    for i, p in enumerate(perfiles):
        errores += validar_perfil(p, i)
    ids = [p["model_id"] for p in perfiles]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup:
        errores.append(f"model_id duplicado: {sorted(dup)}")
    if errores:
        raise PerfilInvalido("; ".join(errores))
    return doc
