"""BLOQUE B — Control de identidad (guia == mezcla).

El caso mas duro posible: se le pasa al verificador la MISMA senal como mezcla y como
guia. El retardo verdadero es 0 por construccion, no por eleccion. Si el verificador
devuelve algo distinto de 0 aqui, el error es del estimador y no del contenido.

Este control separa dos explicaciones que de otro modo se confunden:
  (i)  el estimador tiene un sesgo interno (p.ej. desfase de la envolvente); o
  (ii) la superficie de correlacion se aplana cuando la guia no es identica a la mezcla.
Resultado (ver results/alineacion_identidad.json): 22/22 con lag 0 y Pearson 1.0000
exacto -> no hay sesgo interno; el desplazamiento aparece al introducir el acompanamiento.

Uso: python3 src/bloque_b_control.py
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from bloque_b import CONF, cargar_motor, construir_senal  # noqa: E402

RES = os.path.join(BASE, "results")


def estimar(H, mix_mono, guia_mono):
    sr = CONF["sr"]
    win = int(H.ALIGN_ENVELOPE_MS * 1e-3 * sr)
    dec = H.ALIGN_COARSE_DECIMATION
    em = H._decimate_block_mean(H._moving_rms(mix_mono, win), dec)
    eg = H._decimate_block_mean(H._moving_rms(guia_mono, win), dec)
    le, ncc = H._ncc_fft_coarse(em, eg, int(H.ALIGN_SEARCH_SECONDS * sr / dec))
    bl, pv, sub = H._refine_alignment(mix_mono, guia_mono, le * dec,
                                      max(H.ALIGN_REFINE_HALFSPAN, dec + 2))
    off_ms = 1000.0 * sub / sr
    abs_off = abs(int(round(sub)))
    if abs_off <= H.ALIGNED_TOL_SAMPLES:
        cls = "ALIGNED"
    elif abs_off <= int(H.MISALIGNED_TOL_MS * 1e-3 * sr):
        cls = "WARNING"
    else:
        cls = "MISALIGNED"
    return {"lag_env": int(le), "ncc_coarse": float(ncc),
            "offset_ms": float(off_ms), "pearson": float(pv),
            "clase": cls, "error_verdadero_ms": 0.0}


def main():
    os.makedirs(RES, exist_ok=True)
    salida = {}
    for nombre in ("hardened_3.1.1", "evo_3.1.1"):
        H = cargar_motor(nombre)
        casos = []
        for contenido in CONF["contenidos"]:
            for dur in CONF["duraciones_s"]:
                sc = construir_senal(contenido, dur)
                mm = H.mono_downmix(sc["M"])
                r = estimar(H, mm, mm.copy())
                r.update({"contenido": contenido, "dur_s": dur,
                          "n": int(sc["n"])})
                casos.append(r)
                del sc, mm
        perfectos = sum(1 for c in casos if c["lag_env"] == 0
                        and abs(c["offset_ms"]) < 1e-9)
        maximos = [c["pearson"] for c in casos]
        salida[nombre] = {
            "descripcion": "guia identica a la mezcla; retardo verdadero 0",
            "n_casos": len(casos), "n_exactos": perfectos,
            "pearson_min": min(maximos), "pearson_max": max(maximos),
            "clases": {c: sum(1 for x in casos if x["clase"] == c)
                       for c in {x["clase"] for x in casos}},
            "casos": casos,
        }
        print(f"{nombre}: {perfectos}/{len(casos)} exactos, "
              f"pearson [{min(maximos):.4f}, {max(maximos):.4f}], "
              f"clases={salida[nombre]['clases']}")
    with open(os.path.join(RES, "alineacion_identidad.json"), "w",
              encoding="utf-8") as fh:
        json.dump(salida, fh, indent=1, ensure_ascii=False)
    print("escrito: results/alineacion_identidad.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
