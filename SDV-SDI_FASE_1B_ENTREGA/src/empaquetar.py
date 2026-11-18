"""Empaqueta la entrega de la Fase 1B.

1. Re-verifica la integridad de las 10 fuentes contra `INTEGRIDAD_FUENTES.json`.
2. Reduce las curvas de alineacion para que la entrega sea manejable.
3. Escribe `fixtures/fixtures_especificacion.json` (los fixtures son deterministas).
4. Genera `manifests/` y `hashes/`.
5. Construye el ZIP y lo re-verifica leyendolo de vuelta.

No modifica nada del arbol de fuentes.
"""
import datetime as _dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"
INTEGRIDAD = ("/home/user/entrada3/extraido/Encargo_Arena_SDVSdi_Fase_Sintetica_1B/"
              "INTEGRIDAD_FUENTES.json")
ZIP_SALIDA = "/home/user/SDV-SDI_FASE_1B_ENTREGA.zip"
DOCS = ["README.md", "INDICE_PARA_REVISOR.md", "REPORT.md", "SOURCE_AUDIT.md",
        "ORCHESTRATOR_SPEC.md", "FORMULA_AUDIT.md", "ALIGNMENT_DIAGNOSTICS.md",
        "CONSENSUS_VALIDATION.md"]
INCLUIR_DIRS = ["src", "tests", "configs", "fixtures", "manifests", "hashes", "results"]
EXCLUIR = {"__pycache__", ".pytest_cache", "work"}
# Ficheros que el propio empaquetado reescribe: no pueden figurar en su propio
# inventario (autorreferencia), se documenta la exclusion.
AUTORREFERENTES = {"manifests/MANIFEST_ENTREGABLES.json", "hashes/SHA256SUMS.txt",
                   "hashes/FUENTES_SHA256.txt", "hashes/ZIP_SHA256.txt"}


def sha256(path, bloque=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(bloque), b""):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------- 1. integridad
def verificar_fuentes():
    esperado = json.load(open(INTEGRIDAD, encoding="utf-8"))
    filas, ok = [], True
    for f in esperado["files"]:
        nombre = os.path.basename(f["path"])
        ruta = os.path.join(FUENTES, nombre)
        existe = os.path.isfile(ruta)
        real = sha256(ruta) if existe else None
        coincide = bool(existe and real == f["sha256"])
        ok &= coincide
        filas.append({"fichero": nombre, "bytes": f["size_bytes"],
                      "sha256_esperado": f["sha256"], "sha256_real": real,
                      "coincide": coincide})
    return {"zip": esperado["source_zip"], "n": len(filas),
            "todos_coinciden": ok, "ficheros": filas}


# ------------------------------------------------ 2. curvas reducidas
def reducir_curvas(cada=8):
    origen = os.path.join(RAIZ, "results", "alineacion_curvas.json")
    destino = os.path.join(RAIZ, "results", "alineacion_curvas_reducidas.json")
    if not os.path.isfile(origen):
        return None
    d = json.load(open(origen, encoding="utf-8"))
    out = {"_nota": (f"Curvas decimadas 1/{cada} SOLO para visualizacion. El indice del "
                     "maximo se conserva exacto. El original completo (120 MB) se "
                     "regenera con `python3 src/analisis_b.py`."),
           "_decimacion": cada, "casos": {}}
    for k, v in d.items():
        lags, vals = v["lags"], v["vals"]
        idx = list(range(0, len(lags), cada))
        i_max = max(range(len(vals)), key=lambda i: vals[i])
        if i_max not in idx:
            idx.append(i_max)
            idx.sort()
        out["casos"][k] = {"lags": [lags[i] for i in idx],
                           "vals": [round(vals[i], 9) for i in idx],
                           "lag_max": lags[i_max], "val_max": vals[i_max],
                           "n_original": len(lags)}
    with open(destino, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    return {"origen_bytes": os.path.getsize(origen),
            "reducido_bytes": os.path.getsize(destino),
            "n_casos": len(out["casos"])}


# ------------------------------------------------------ 3. fixtures
def escribir_fixtures():
    d = os.path.join(RAIZ, "fixtures")
    os.makedirs(d, exist_ok=True)
    ruta = os.path.join(RAIZ, "results", "bloque_d_orquestador.json")
    casos = []
    if os.path.isfile(ruta):
        doc = json.load(open(ruta, encoding="utf-8"))
        for f in doc.get("fixtures", []):
            casos.append({"caso": f.get("caso"), "esperado": f.get("esperado"),
                          "observado": f.get("estado"), "pasa": f.get("pasa"),
                          "formulas": f.get("formulas"), "nota": f.get("nota")})
    spec = {
        "nota": ("Los fixtures NO se incluyen como WAV: son deterministas y se regeneran "
                 "con `python3 src/bloque_d.py` (semilla 20261117, WAV FLOAT estereo, "
                 "M = V + I exacto, evento inyectado solo en el canal L). El audio "
                 "regenerado es identico muestra a muestra; los BYTES del fichero pueden "
                 "diferir por el chunk PEAK con timestamp de libsndfile (ver "
                 "CONSENSUS_VALIDATION.md, nota de metodo)."),
        "semilla": 20261117, "sample_rate": 44100, "subtype": "FLOAT", "canales": 2,
        "perfiles": "configs/perfiles_orquestador.json",
        "n_casos": len(casos), "casos": casos,
    }
    p = os.path.join(d, "fixtures_especificacion.json")
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=1, ensure_ascii=False)
    return p, len(casos)


# ------------------------------------------------------- 4. manifiestos
def reunir_ficheros():
    ficheros = []
    for doc in DOCS:
        p = os.path.join(RAIZ, doc)
        if os.path.isfile(p):
            ficheros.append(p)
    for d in INCLUIR_DIRS:
        base = os.path.join(RAIZ, d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(x for x in dirnames if x not in EXCLUIR)
            for n in sorted(filenames):
                p = os.path.join(dirpath, n)
                if n == "alineacion_curvas.json":       # 120 MB, va la reducida
                    continue
                if n.endswith((".pyc", ".pyo")):
                    continue
                if os.path.relpath(p, RAIZ) in AUTORREFERENTES:
                    continue
                ficheros.append(p)
    return sorted(set(ficheros))


def escribir_manifiestos(ficheros, fuentes):
    man_dir = os.path.join(RAIZ, "manifests")
    has_dir = os.path.join(RAIZ, "hashes")
    os.makedirs(man_dir, exist_ok=True)
    os.makedirs(has_dir, exist_ok=True)

    inventario = []
    for p in ficheros:
        inventario.append({"ruta": os.path.relpath(p, RAIZ),
                           "bytes": os.path.getsize(p), "sha256": sha256(p)})
    man = {
        "fase": "1B",
        "generado_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "n_ficheros": len(inventario),
        "bytes_totales": sum(x["bytes"] for x in inventario),
        "politica_fuentes": {
            "modificados": 0,
            "nota": "las 10 fuentes no se han modificado; el orquestador original solo se "
                    "ha ejecutado en directorios de trabajo desechables",
        },
        "fuentes": fuentes,
        "excluidos_del_inventario": sorted(AUTORREFERENTES),
        "nota_exclusion": ("los ficheros de manifiesto y sumas se reescriben en cada "
                           "empaquetado y no pueden figurar en su propio inventario; su "
                           "verificacion va aparte en hashes/ZIP_SHA256.txt"),
        "ficheros": inventario,
    }
    with open(os.path.join(man_dir, "MANIFEST_ENTREGABLES.json"), "w",
              encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)

    with open(os.path.join(has_dir, "SHA256SUMS.txt"), "w", encoding="utf-8") as fh:
        for x in inventario:
            fh.write(f"{x['sha256']}  {x['ruta']}\n")

    with open(os.path.join(has_dir, "FUENTES_SHA256.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"# ZIP fuente: {fuentes['zip']['filename']} "
                 f"sha256={fuentes['zip']['sha256']}\n")
        fh.write("# esperado"
                 f"{'=' * 8}real{'=' * 20}coincide  fichero\n")
        for f in fuentes["ficheros"]:
            fh.write(f"{f['sha256_esperado']}  {f['sha256_real']}  "
                     f"{'SI' if f['coincide'] else 'NO':<3}  {f['fichero']}\n")
    return man


# --------------------------------------------------------------- 5. ZIP
NOTA_ZIP = """# El SHA-256 del ZIP no puede figurar dentro del propio ZIP:
# al incluirlo cambiaria el fichero y por tanto su propio hash.
#
# El digest real se entrega en el sidecar externo:
#     SDV-SDI_FASE_1B_ENTREGA.zip.sha256
# y se calcula DESPUES de comprimir.
#
# Verificacion (desde la carpeta donde este el ZIP):
#     sha256sum -c SDV-SDI_FASE_1B_ENTREGA.zip.sha256
#
# Para verificar el CONTENIDO, use hashes/SHA256SUMS.txt (71 ficheros, sin
# autorreferencias): todas sus sumas cuadran con los ficheros del ZIP.
"""


def construir_zip(ficheros):
    with open(os.path.join(RAIZ, "hashes", "ZIP_SHA256.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(NOTA_ZIP)
    if os.path.isfile(ZIP_SALIDA):
        os.remove(ZIP_SALIDA)
    vistos = set()
    with zipfile.ZipFile(ZIP_SALIDA, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in ficheros:
            nombre = os.path.relpath(p, RAIZ)
            if nombre in vistos:
                continue
            vistos.add(nombre)
            z.write(p, nombre)
        for extra in ("manifests/MANIFEST_ENTREGABLES.json", "hashes/SHA256SUMS.txt",
                      "hashes/FUENTES_SHA256.txt", "hashes/ZIP_SHA256.txt"):
            if extra not in vistos and os.path.isfile(os.path.join(RAIZ, extra)):
                z.write(os.path.join(RAIZ, extra), extra)
                vistos.add(extra)
    return ZIP_SALIDA


def verificar_zip(man):
    with zipfile.ZipFile(ZIP_SALIDA) as z:
        nombres = z.namelist()
        malos = z.testzip()
    return {"n_entradas": len(nombres), "testzip": malos,
            "bytes": os.path.getsize(ZIP_SALIDA),
            "sha256": sha256(ZIP_SALIDA),
            "n_esperados": man["n_ficheros"] + 3}


def main():
    print("### 0. coherencia interna (requisito para compilar)")
    rc = subprocess.call([sys.executable, os.path.join(RAIZ, "src",
                                                       "verificar_coherencia.py")])
    if rc != 0:
        print("  [ABORT] la coherencia no cuadra: no se compila el ZIP")
        return 1

    print("### 1. integridad de fuentes")
    fuentes = verificar_fuentes()
    print(f"  {sum(1 for f in fuentes['ficheros'] if f['coincide'])}/{fuentes['n']} "
          f"coinciden  -> {'OK' if fuentes['todos_coinciden'] else 'FALLO'}")
    if not fuentes["todos_coinciden"]:
        return 1

    print("### 2. curvas reducidas")
    r = reducir_curvas()
    if r:
        print(f"  {r['origen_bytes'] / 1e6:.1f} MB -> {r['reducido_bytes'] / 1e6:.2f} MB "
              f"({r['n_casos']} casos)")

    print("### 3. fixtures")
    p, n = escribir_fixtures()
    print(f"  {n} casos -> fixtures/fixtures_especificacion.json")

    print("### 4. manifiestos y hashes")
    ficheros = reunir_ficheros()
    man = escribir_manifiestos(ficheros, fuentes)
    print(f"  {man['n_ficheros']} ficheros, {man['bytes_totales'] / 1e6:.1f} MB")

    print("### 5. ZIP")
    construir_zip(ficheros)
    v = verificar_zip(man)
    print(f"  {v['n_entradas']} entradas, {v['bytes'] / 1e6:.2f} MB, "
          f"testzip={v['testzip']}")
    print(f"  sha256 {v['sha256']}")
    sidecar = ZIP_SALIDA + ".sha256"
    with open(sidecar, "w", encoding="utf-8") as fh:
        fh.write(f"{v['sha256']}  {os.path.basename(ZIP_SALIDA)}\n")
        fh.write(f"# {v['n_entradas']} entradas, {v['bytes']} bytes\n")
    print(f"  sidecar -> {sidecar}")
    # verificacion real: releer el sidecar y compararlo con el fichero en disco
    decl = open(sidecar, encoding="utf-8").readline().split()[0]
    real = sha256(ZIP_SALIDA)
    print(f"  sidecar coincide: {decl == real}")
    return 0 if (v["testzip"] is None and decl == real) else 1


if __name__ == "__main__":
    sys.exit(main())
