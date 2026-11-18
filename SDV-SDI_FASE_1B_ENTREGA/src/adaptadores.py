"""Adaptadores EXTERNOS de prueba.

No se importa ni se edita ningun motor: se ejecutan como proceso, con su CLI
documentada, y se les entrega un manifiesto generado por nosotros.

Motivos (documentados en el informe):
  * `MOTOR_SEP_SDV-SDI.py` y los dos 3.1.1 declaran `if __name__` normal, pero
    importarlos arrastra matplotlib y estado global; el proceso aislado es mas
    fiel y permite medir rc, stderr y tiempo.
  * Los cinco ficheros declaran funciones con estado global (constantes, caches) y
    arrastran matplotlib; el proceso aislado permite ademas medir rc, stderr y
    tiempo sin contaminar el proceso del banco de pruebas. Los cinco tienen guarda
    `if __name__` (v3:2271), de modo que el proceso aislado no es una obligacion
    tecnica sino una decision metodologica.

Un solo manifiesto sirve para las cuatro familias porque todas aceptan
`vocal_guide`/`vocal_path` e `instrumental_guide`/`instrumental_path`; se
escriben las dos claves para no depender de detalles de cada version.
"""
from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import soundfile as sf

SRC = "/home/user/fase1b/fuentes/Proyecto SDV-SDI_SGM"   # FASE 1B: copia verificada 10/10

MOTORES = {
    "v3_3.0.0": "MOTOR_SEP_SDV-SDI_v3.py",
    "sfumato_3.1.1_base": "MOTOR_SEP_SDV-SDI.py",
    "hardened_3.1.1": "MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py",
    "evo_3.1.1": "MOTOR_SEP_SDV-SDI_EVO.py",
    "mqr_1.3.0": "sdv_sdi_mqr_engine.py",
}


# Motores PARCHEADOS por nosotros: viven fuera del directorio de fuentes originales.
# Cada clave lleva el numero de parche (R-xx) en el nombre para que ningun registro
# pueda confundirse con el fichero recibido. Ver PATCHES.md.
PARCHEADOS = {
    "sfumato_3.1.1_R24": "/home/user/fase1/parcheados/MOTOR_SEP_SDV-SDI_R24.py",
}


def ruta_motor(clave: str) -> str:
    if clave in PARCHEADOS:
        return PARCHEADOS[clave]
    return os.path.join(SRC, MOTORES[clave])


def escribir_wav(path: str, x: np.ndarray, sr: int, subtype: str = "FLOAT") -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.asarray(x, dtype=np.float64), sr, subtype=subtype)
    return path


def escribir_fixture(dirbase: str, sc: dict, guias: dict, subtype: str = "FLOAT") -> dict:
    """Escribe mix y guias. `guias` = {"vocal_1": array, "instrum_1": array, ...}."""
    os.makedirs(dirbase, exist_ok=True)
    sr = sc["sr"]
    mix_p = escribir_wav(os.path.join(dirbase, "mix.wav"), sc["M"], sr, subtype)
    rutas = {}
    for nombre, arr in guias.items():
        rutas[nombre] = escribir_wav(os.path.join(dirbase, f"{nombre}.wav"), arr, sr, subtype)
    return {"mix": mix_p, "guias": rutas}


def manifiesto(mix_path: str, pares: list, out_dir: str,
               power_p: float = 1.8, epsilon: float = 1e-12, beta: float = 1.0,
               use_residuals: bool = True, n_fft: int = 4096, hop: int = 1024,
               smoothing: str = "none", mask_mode: str = "per_channel",
               window: str = "hann", subtype: str = "FLOAT") -> dict:
    gp = []
    for i, (pid, v, ins) in enumerate(pares, 1):
        gp.append({
            "pair_id": pid,
            "family": "synthetic",
            "variant": f"mt_{i}",
            "configuration": "USER_DEFINED",
            "source": "SYNTHETIC_LAB",
            "overlap": "USER_DEFINED",
            "vocal_guide": os.path.abspath(v),
            "instrumental_guide": os.path.abspath(ins),
            "vocal_path": os.path.abspath(v),
            "instrumental_path": os.path.abspath(ins),
        })
    # claves duplicadas a proposito: cada version lee un nombre distinto
    #   v3 / 3.1.1 : source_mix_file (o mix_original) + guide_pairs (o pairs)
    #   mqr 1.3.0  : mix_original + pairs  (load_manifest, linea 644)
    return {
        "manifest_version": "3.1.1-test",
        "project_name": "laboratorio_sintetico",
        "source_mix_file": os.path.abspath(mix_path),
        "mix_original": os.path.abspath(mix_path),
        "pairs": gp,
        "output_directory": os.path.abspath(out_dir),
        "calibration_parameters": {
            "power_p": power_p,
            "epsilon": epsilon,
            "beta_consensus": beta,
            "use_physical_residuals": use_residuals,
            "n_fft": n_fft,
            "hop_length": hop,
            "window": window,
            "output_subtype": subtype,
            "smoothing": smoothing,
            "mask_mode": mask_mode,
        },
        "guide_pairs": gp,
    }


def escribir_manifiesto(path: str, man: dict) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(man, fh, indent=1, ensure_ascii=False)
    return path


def ejecutar(clave: str, man_path: str, out_dir: str, extra: list | None = None,
             timeout: int = 900) -> dict:
    """Ejecuta un motor como proceso. Nunca lanza excepcion por rc!=0."""
    motor = ruta_motor(clave)
    extra = extra or []
    cmd = [sys.executable, motor, "--manifest", man_path, "--out", out_dir] + extra
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        rc, so, se = p.returncode, p.stdout, p.stderr
        timedout = False
    except subprocess.TimeoutExpired as e:
        rc, so, se, timedout = -99, (e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), "TIMEOUT", True
    return {
        "motor": clave, "cmd": cmd, "rc": rc,
        "stdout": so[-8000:], "stderr": se[-8000:],
        "elapsed_s": round(time.time() - t0, 3), "timeout": timedout,
        "out_dir": out_dir,
    }


def buscar_salidas(out_dir: str) -> dict:
    """Localiza los WAV de salida (SDV / SDI) sea cual sea la estructura interna."""
    res = {"sdv": None, "sdi": None, "todos": []}
    for p in sorted(glob.glob(os.path.join(out_dir, "**", "*.wav"), recursive=True)):
        res["todos"].append(p)
        b = os.path.basename(p).upper()
        if "SDV" in b and res["sdv"] is None:
            res["sdv"] = p
        elif "SDI" in b and res["sdi"] is None:
            res["sdi"] = p
    return res


def leer(path: str):
    x, sr = sf.read(path, dtype="float64", always_2d=True)
    return x, sr


def huellas_fuentes() -> dict:
    """SHA-256 de los ficheros fuente en el momento de ejecutar (trazabilidad §10)."""
    import hashlib
    out = {}
    for f in sorted(os.listdir(SRC)):
        p = os.path.join(SRC, f)
        if os.path.isfile(p):
            out[f] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return out
