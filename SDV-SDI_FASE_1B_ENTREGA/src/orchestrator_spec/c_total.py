"""Fase 7: construir C_total SOLO con la estrategia declarada.

Tabla de decision (ESPECIFICACION 4.4):
  agregado solo                -> C_total = agregado            (single_aggregate)
  Reverb + Others exactamente  -> C_total = Reverb + Others     (split_reverb_others)
  agregado Y subcomponentes    -> CONFICTO => AMBIGUOUS, salvo que el perfil
                                  declare representaciones alternativas y cual usar
  un solo subcomponente        -> INCOMPLETE: NUNCA se infiere C_total
  ninguno                      -> ausente
Jamas se suma el agregado con sus subcomponentes.
"""
from . import validador as V


def _unico(lista):
    return lista[0] if len(lista) == 1 else None


def construir(roles: dict, perfil: dict) -> dict:
    agg = roles.get("C_AGGREGATE", [])
    rev = roles.get("C_REVERB", [])
    oth = roles.get("C_OTHERS", [])
    base = {"sumandos": [], "estrategia": None, "motivos": []}

    decl = perfil.get("representaciones_alternativas") or {}
    if agg and (rev or oth):
        if decl.get("declara") and decl.get("usar") in {"aggregate", "split"}:
            base["motivos"].append(
                f"conflicto resuelto por el perfil: usar='{decl['usar']}'")
            if decl["usar"] == "aggregate":
                rev, oth = [], []
            else:
                agg = []
        else:
            return dict(base, estado="AMBIGUOUS", estrategia="conflicto",
                        motivos=["C agregado Y subcomponentes presentes sin declaracion "
                                 "de alternativas: no se elige ni se suma"])
    if len(agg) > 1 or len(rev) > 1 or len(oth) > 1:
        return dict(base, estado="AMBIGUOUS", estrategia="duplicado",
                    motivos=[f"varios candidatos para un mismo rol C: "
                             f"agg={len(agg)} rev={len(rev)} oth={len(oth)}"])
    if agg:
        f = agg[0]
        x, sr = V.leer(f["ruta"])
        return dict(base, estado="OK", estrategia="single_aggregate",
                    C_total=x, sr=sr,
                    sumandos=[{"rol": "C_AGGREGATE", "rel": f["rel"]}],
                    formula="C_total = C_aggregate")
    if rev and oth:
        v = V.validar_entradas([("C_REVERB", rev[0]["ruta"]),
                                ("C_OTHERS", oth[0]["ruta"])])
        if not v["ok"]:
            return dict(base, estado="INCOMPATIBLE", estrategia="split_reverb_others",
                        motivos=v["motivos"])
        a, sr = V.leer(rev[0]["ruta"])
        b, sr2 = V.leer(oth[0]["ruta"])
        if sr != sr2:
            return dict(base, estado="INCOMPATIBLE", estrategia="split_reverb_others",
                        motivos=[f"sr distinto entre subcomponentes {sr} vs {sr2}"])
        return dict(base, estado="OK", estrategia="split_reverb_others",
                    C_total=a + b, sr=sr,
                    sumandos=[{"rol": "C_REVERB", "rel": rev[0]["rel"]},
                              {"rol": "C_OTHERS", "rel": oth[0]["rel"]}],
                    formula="C_total = C_reverb + C_others")
    if rev or oth:
        presente = "C_REVERB" if rev else "C_OTHERS"
        return dict(base, estado="INCOMPLETE", estrategia="parcial",
                    motivos=[f"solo existe {presente} sin el otro subcomponente: "
                             "no se infiere C_total"])
    return dict(base, estado="INCOMPLETE", estrategia="ausente",
                motivos=["no hay ningun componente C"])
