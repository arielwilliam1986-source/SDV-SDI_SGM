"""Fase 9: manifiesto de procedencia (ESPECIFICACION 4.10)."""
import datetime as _dt
import json
import os

from . import __version__
from .inventario import sha256


def construir(dirbase, mix_info, grupos_out, perfiles_doc, parametros) -> dict:
    return {
        "prototipo": {"nombre": "orchestrator_spec", "version": __version__},
        "generado_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "dir_entrada": os.path.abspath(dirbase),
        "transformaciones_aplicadas": "none",
        "politica": {
            "primer_match": False, "truncar": False, "resamplear": False,
            "convertir_mono_estereo": False, "alinear": False,
            "normalizar": False, "cambiar_ganancia": False, "cambiar_polaridad": False,
        },
        "perfiles": {"schema": perfiles_doc.get("schema"),
                     "model_ids": [p["model_id"] for p in perfiles_doc["perfiles"]]},
        "parametros": parametros,
        "mix": mix_info,
        "grupos": grupos_out,
    }


def escribir(path: str, man: dict) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False, default=str)
    return path
