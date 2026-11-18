"""Fase 1: inventariar ficheros SIN procesarlos (solo stat + os.scandir)."""
import hashlib
import os


def inventariar(raiz: str, extensiones) -> dict:
    ext = tuple(e.lower() for e in extensiones)
    ficheros, ignorados = [], []
    for dirpath, dirnames, filenames in os.walk(raiz):
        dirnames.sort()                       # determinismo
        for nombre in sorted(filenames):
            ruta = os.path.join(dirpath, nombre)
            rel = os.path.relpath(ruta, raiz)
            try:
                st = os.stat(ruta)
            except OSError as e:
                ignorados.append({"ruta": rel, "motivo": f"stat falló: {e}"})
                continue
            item = {"ruta": ruta, "rel": rel, "nombre": nombre,
                    "dir": os.path.dirname(rel), "bytes": st.st_size}
            if not nombre.lower().endswith(ext):
                item["motivo"] = "extension no declarada"
                ignorados.append(item)
            else:
                ficheros.append(item)
    return {"raiz": raiz, "ficheros": ficheros, "ignorados": ignorados,
            "n_ficheros": len(ficheros), "n_ignorados": len(ignorados)}


def sha256(path: str, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(bloque), b""):
            h.update(chunk)
    return h.hexdigest()
