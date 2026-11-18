"""Fase 8: calcular SOLO los residuales cuyos insumos esten completos y validados."""
import os

import numpy as np
import soundfile as sf

from . import validador as V

# role logico -> (etiqueta de formula, expresion exacta, roles requeridos)
FORMULAS = {
    "SDV1":      {"expr": "SDV1 = M - B",              "req": ("B_INSTRUMENT",)},
    "SDV2":      {"expr": "SDV2 = M - A + D",          "req": ("A_RESTORED", "D_DRY_VOCAL")},
    "SDI1":      {"expr": "SDI1 = M - E",              "req": ("E_VOCALS",)},
    "SDI2":      {"expr": "SDI2 = M - C_total - D",    "req": ("C_TOTAL", "D_DRY_VOCAL")},
    "SDV_SIMPLE": {"expr": "SDV_simple = M - Instrumental", "req": ("INSTRUMENTAL",)},
    "SDI_SIMPLE": {"expr": "SDI_simple = M - Vocals",       "req": ("VOCALS",)},
}


def _calc(nombre, M, r, c_total):
    if nombre == "SDV1":
        return M - r["B_INSTRUMENT"]
    if nombre == "SDV2":
        return M - r["A_RESTORED"] + r["D_DRY_VOCAL"]
    if nombre == "SDI1":
        return M - r["E_VOCALS"]
    if nombre == "SDI2":
        return M - c_total - r["D_DRY_VOCAL"]
    if nombre == "SDV_SIMPLE":
        return M - r["INSTRUMENTAL"]
    if nombre == "SDI_SIMPLE":
        return M - r["VOCALS"]
    raise KeyError(nombre)


def planificar(roles_presentes, c_estado, perfil) -> dict:
    """Que formulas se pueden calcular, cuales no y por que."""
    disp = set(roles_presentes)
    if c_estado == "OK":
        disp.add("C_TOTAL")
    plan = {}
    for nombre, spec in FORMULAS.items():
        if not any(r in perfil["roles"] for r in spec["req"]):
            plan[nombre] = {"estado": "NO_APLICA",
                            "motivo": f"el perfil {perfil['model_id']} no declara "
                                      f"{list(spec['req'])}"}
            continue
        falta = [r for r in spec["req"] if r not in disp]
        if falta:
            plan[nombre] = {"estado": "INCOMPLETE",
                            "motivo": f"faltan insumos: {falta}"}
        elif spec["req"].count("C_TOTAL") and c_estado != "OK":
            plan[nombre] = {"estado": "INCOMPLETE", "motivo": f"C_total no valido ({c_estado})"}
        else:
            plan[nombre] = {"estado": "LISTO", "motivo": ""}
    return plan


def generar(plan, roles, M, c_total, sr, out_dir, prefijo) -> list:
    os.makedirs(out_dir, exist_ok=True)
    hechos = []
    for nombre, p in plan.items():
        if p["estado"] != "LISTO":
            continue
        arr = _calc(nombre, M, roles, c_total)
        if not np.all(np.isfinite(arr)):
            hechos.append({"formula": nombre, "estado": "REJECTED",
                           "motivo": "resultado no finito"})
            continue
        ruta = os.path.join(out_dir, f"{prefijo}__{nombre}.wav")
        sf.write(ruta, arr, sr, subtype="FLOAT")     # sin normalizar, sin recortar
        hechos.append({"formula": nombre, "expr": FORMULAS[nombre]["expr"],
                       "ruta": ruta, "frames": int(arr.shape[0]),
                       "canales": int(arr.shape[1]) if arr.ndim == 2 else 1,
                       "rms_L": float(np.sqrt(np.mean(arr[:, 0] ** 2))),
                       "rms_R": float(np.sqrt(np.mean(arr[:, 1] ** 2))) if arr.ndim == 2
                       else None,
                       "estado": "OK"})
    return hechos


def medir_e_vs_c_total_d(E, c_total, D) -> dict:
    """Hipotesis E ~= C_total + D. Solo se MIDE; nunca se usa para fabricar nada."""
    resid = E - c_total - D
    def _canal(x):
        rms = float(np.sqrt(np.mean(x ** 2)))
        pico = float(np.max(np.abs(x)))
        return {"rms": rms, "pico": pico}
    out = {"canales": {}}
    for i, etq in enumerate(("L", "R")[:resid.shape[1]]):
        r = resid[:, i]
        e = E[:, i]
        rms_r = float(np.sqrt(np.mean(r ** 2)))
        rms_e = float(np.sqrt(np.mean(e ** 2)))
        snr = (20 * np.log10(rms_e / rms_r)) if rms_r > 0 else float("inf")
        out["canales"][etq] = {"rms_residuo": rms_r,
                               "pico_residuo": float(np.max(np.abs(r))),
                               "rms_E": rms_e, "snr_db": float(snr)}
    out["max_abs_global"] = float(np.max(np.abs(resid)))
    out["exacta"] = bool(out["max_abs_global"] == 0.0)
    return out
