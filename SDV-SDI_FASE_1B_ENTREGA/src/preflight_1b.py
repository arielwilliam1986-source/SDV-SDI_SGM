"""Preflight de la Fase 1B: integridad de las 10 fuentes y entorno.

Solo lee. No escribe nada fuera de stdout.
"""
import hashlib
import json
import os
import platform
import sys

INTEGRIDAD = ("/home/user/entrada3/extraido/Encargo_Arena_SDVSdi_Fase_Sintetica_1B/"
              "INTEGRIDAD_FUENTES.json")
FUENTES = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ok = True
    print("[*] Entorno")
    print(f"    python      : {sys.version.split()[0]}")
    print(f"    plataforma  : {platform.platform()}")
    for mod in ("numpy", "scipy", "soundfile"):
        try:
            m = __import__(mod)
            extra = ""
            if mod == "soundfile":
                extra = f" (libsndfile {m.__libsndfile_version__})"
            print(f"    {mod:<12}: {m.__version__}{extra}")
        except Exception as e:                                   # noqa: BLE001
            print(f"    {mod:<12}: NO DISPONIBLE ({e})")
            ok = False
    try:
        import librosa                                               # noqa: F401
        print("    librosa     : PRESENTE (el encargo pide no usarla)")
    except ImportError:
        print("    librosa     : ausente, como se pidio")

    print("\n[*] Integridad de las 10 fuentes")
    doc = json.load(open(INTEGRIDAD, encoding="utf-8"))
    esperado_zip = doc["source_zip"]["sha256"]
    print(f"    ZIP fuente  : {esperado_zip}")
    for f in doc["files"]:
        nombre = os.path.basename(f["path"])
        ruta = os.path.join(FUENTES, nombre)
        real = sha256(ruta) if os.path.isfile(ruta) else None
        bien = real == f["sha256"]
        ok &= bien
        print(f"    [{'ok' if bien else 'MAL'}] {nombre:<44} {str(real)[:16]}")
    print(f"\n[{'OK' if ok else 'FALLO'}] preflight")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
