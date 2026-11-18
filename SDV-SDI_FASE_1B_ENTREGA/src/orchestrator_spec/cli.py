"""CLI del prototipo: python3 -m orchestrator_spec.cli --dir ... --perfiles ..."""
import argparse
import json
import sys

from . import orquestador


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Orquestador prototipo (perfiles semanticos)")
    ap.add_argument("--dir", required=True, help="carpeta de la cancion")
    ap.add_argument("--perfiles", required=True, help="JSON de perfiles")
    ap.add_argument("--mix", default=None, help="nombre exacto del Mix")
    ap.add_argument("--out", required=True, help="carpeta de salida (fuera del arbol de entrada)")
    ap.add_argument("--no-generar", action="store_true", help="solo auditar, sin escribir WAV")
    ap.add_argument("--subtype-laxo", action="store_true",
                    help="no exigir subtype identico entre entradas")
    a = ap.parse_args(argv)
    r = orquestador.ejecutar(a.dir, a.perfiles, mix_nombre=a.mix, out_dir=a.out,
                             estricto_subtype=not a.subtype_laxo,
                             generar=not a.no_generar)
    print(json.dumps({"estado": r["estado"], "motivo": r["motivo"],
                      "grupos": [{"grupo_id": g["grupo_id"], "estado": g["estado"],
                                  "residuales": [x["formula"] for x in g["residuales"]]}
                                 for g in r["grupos"]]}, indent=1, ensure_ascii=False))
    return 0 if r["estado"] in ("ACCEPT", "INCOMPLETE") else 1


if __name__ == "__main__":
    sys.exit(main())
