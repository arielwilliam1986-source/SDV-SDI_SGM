"""Fase 5: validacion estricta de metadatos y geometria.

Politica: NO se trunca, NO se resamplea, NO se convierte mono/estéreo, NO se alinea,
NO se normaliza. Cualquier discrepancia => INCOMPATIBLE para ese grupo.
"""
import numpy as np
import soundfile as sf


class Incompatible(Exception):
    pass


def meta(path: str) -> dict:
    i = sf.info(path)
    return {"sr": i.samplerate, "ch": i.channels, "frames": i.frames,
            "subtype": i.subtype, "format": i.format,
            "duracion_s": round(i.frames / i.samplerate, 6)}


def es_finito(path: str, bloque: int = 1 << 18) -> bool:
    with sf.SoundFile(path) as fh:
        for b in fh.blocks(blocksize=bloque, dtype="float64", always_2d=True):
            if b.size and not np.all(np.isfinite(b)):
                return False
    return True


def leer(path: str):
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    return x, sr


def validar_entradas(items: list, estricto_subtype: bool = True) -> dict:
    """items = [(etiqueta, ruta)]. Todas deben coincidir en sr/ch/frames/subtype."""
    if not items:
        return {"ok": False, "motivos": ["sin entradas"], "meta": {}}
    metas, motivos = {}, []
    for etq, ruta in items:
        try:
            metas[etq] = meta(ruta)
        except Exception as e:                       # noqa: BLE001
            return {"ok": False, "motivos": [f"{etq}: no legible como WAV ({e})"],
                    "meta": metas, "rechazado": True}
    ref_etq, ref = items[0][0], metas[items[0][0]]
    for etq, m in metas.items():
        if m["sr"] != ref["sr"]:
            motivos.append(f"sample_rate distinto: {etq}={m['sr']} vs {ref_etq}={ref['sr']}")
        if m["ch"] != ref["ch"]:
            motivos.append(f"canales distintos: {etq}={m['ch']} vs {ref_etq}={ref['ch']}")
        if m["frames"] != ref["frames"]:
            motivos.append(f"frames distintos: {etq}={m['frames']} vs {ref_etq}={ref['frames']}"
                           " (no se trunca)")
        if estricto_subtype and m["subtype"] != ref["subtype"]:
            motivos.append(f"subtype distinto: {etq}={m['subtype']} vs {ref_etq}={ref['subtype']}")
    no_finitos = [etq for etq, ruta in items if not es_finito(ruta)]
    for etq in no_finitos:
        motivos.append(f"{etq}: contiene NaN/Inf")
    return {"ok": not motivos, "motivos": motivos, "meta": metas,
            "no_finitos": no_finitos, "rechazado": bool(no_finitos)}


def validar_mix(dirbase: str, nombre_mix: str | None, busqueda: dict,
                sha_esperado: str | None = None) -> dict:
    """Exige un unico Mix identificable. Cero => REJECTED. Varios => REJECTED."""
    cands = busqueda.get("candidatos", [])
    if nombre_mix:
        exactos = [c for c in cands if c["nombre"] == nombre_mix]
        if not exactos:
            return {"ok": False, "estado": "REJECTED",
                    "motivo": f"Mix declarado '{nombre_mix}' no existe", "candidatos": []}
        if len(exactos) > 1:
            return {"ok": False, "estado": "REJECTED",
                    "motivo": f"Mix declarado '{nombre_mix}' aparece {len(exactos)} veces",
                    "candidatos": [c["rel"] for c in exactos]}
        return _cerrar(exactos[0], sha_esperado)
    if len(cands) == 0:
        return {"ok": False, "estado": "REJECTED", "motivo": "no hay ningun Mix candidato",
                "candidatos": []}
    if len(cands) > 1:
        return {"ok": False, "estado": "REJECTED",
                "motivo": f"{len(cands)} mixes candidatos: no se elige el primero",
                "candidatos": [c["rel"] for c in cands]}
    return _cerrar(cands[0], sha_esperado)


def _cerrar(cand, sha_esperado):
    from .inventario import sha256
    real = sha256(cand["ruta"])
    if sha_esperado and real != sha_esperado:
        return {"ok": False, "estado": "REJECTED",
                "motivo": f"hash del Mix no coincide: declarado {sha_esperado[:16]}... "
                          f"real {real[:16]}...",
                "sha256_real": real, "candidatos": [cand["rel"]]}
    return {"ok": True, "ruta": cand["ruta"], "rel": cand["rel"], "sha256": real}
