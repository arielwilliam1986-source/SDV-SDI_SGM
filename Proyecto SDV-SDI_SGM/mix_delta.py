#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mix_delta.py — inyecta el Delta Vocal al SDV Normal (copia reparada, v2).

================================================================================
INTERPRETACION MATEMATICA EXPLICITA (AUDIT_014 — corregido en revision v2)
================================================================================
Definiciones por residuo (V_hat = estimador vocal):
    SDI_x = mix - V_hat_x     [cierto para ramas complementarias]

ADVERTENCIA v2 (no es una equivalencia universal):
    El motor en la rama `normal` devuelve (Vc, Ic) directamente. La salida
    real de esa rama cumple:
        SDV_norm + SDI_norm = mix + e_norm
    con  e_norm := mix - SDV_norm - SDI_norm   (error de reconstruccion).
    Solo las ramas identity/ratio (y normal+mean/median con K impar) cumplen
    e_norm = 0. Con el DEFAULT normal+magnitudes_first, e_norm NO es cero.

Identidad EXACTA (vale siempre, sin supuestos):
    Delta_indirecta = SDI_identity - SDI_normal
                    = (SDV_norm - SDV_id) + e_norm
                    = Delta_directa + e_norm
    donde Delta_directa = SDV_norm - SDV_id (diferencia directa de
    estimadores vocales, reportada como diagnostico cuando esta disponible).

Solo si e_norm = 0 (complementariedad verificada):
    Delta_indirecta = V_hat_norm - V_hat_id

El funcionamiento actual (SE CONSERVA identico, sin cambios de formula):

    Delta        = SDI_identity - SDI_normal          [Delta_indirecta]
    SDV_hibrido  = SDV_norm + gain * Delta
                = SDV_norm + gain*(SDV_norm - SDV_id) + gain*e_norm

    Solo si e_norm = 0:
                = (1 + gain) * V_hat_norm - gain * V_hat_id

Interpretacion CORRECTA: extrapolacion lineal del estimador vocal normal en
la direccion opuesta al estimador identity, CONTAMINADA por gain*e_norm
cuando la rama Normal no es complementaria. Lo que NO es:
  * NO es "informacion vocal recuperada" — sin evidencia de que V_hat_id
    contenga informacion vocal ausente en V_hat_norm (claim RECHAZADO).
  * La equivalencia con la diferencia de estimadores NO es universal:
    requiere complementariedad verificada.

Verificacion de complementariedad (revision v2):
  * Con --mix: se calcula e_norm exacto, se reporta SNR/rms/veredicto
    (umbral 100 dB: FLOAT ronda 140 dB; ramas complementarias medidas >=147
    dB; el default normal+mf mide ~49 dB) y se registra en la procedencia.
  * Sin --mix: se advierte EXPLICITAMENTE que la complementariedad NO ha
    sido verificada y no se presenta la equivalencia como universal.

================================================================================
REPARACIONES DE AUDITORIA (solo en repaired/; original/ intacto)
================================================================================
AUDIT_014  - Ver arriba: interpretacion corregida con e_norm; formula del
             hibrido inalterada; reporte de Delta_directa como diagnostico.
AUDIT_015  - Sin matches[0] silencioso: 0 -> FATAL; >1 -> FATAL listando
             candidatos (resolver con rutas explicitas --sdv-norm/--sdi-norm/
             --sdi-id). Compatibilidad sr/canales/duracion estricta; largos
             distintos -> ERROR salvo --allow-crop (recorte EXPLICITO y
             reportado). Desfase entre corridas medido y avisado (>2 ms).
             Opcionales (mix, SDV_id): igualdad EXACTA de muestras o FATAL
             (proteccion contra mezcla de ejecuciones distintas).
AUDIT_017  - Procedencia: rutas absolutas + SHA-256 de cada entrada; sidecar
             <out>.provenance.json con configuracion, veredicto de
             complementariedad y diagnostico Delta_directa.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import soundfile as sf

# Umbral de complementariedad (ver docstring): FLOAT ~140 dB piso;
# ramas complementarias medidas >=147 dB; default normal+mf ~49 dB.
COMPLEMENTARY_SNR_MIN_DB = 100.0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str, blocksize: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(blocksize), b""):
            h.update(blk)
    return h.hexdigest()


def find_file(directory: str, suffix: str, explicit: str | None,
              label: str) -> str:
    """Identificacion UNICA de entrada (AUDIT_015/017)."""
    if explicit:
        if not os.path.isfile(explicit):
            print(f"[FATAL] {label}: no existe el archivo: {explicit}",
                  file=sys.stderr)
            sys.exit(1)
        return os.path.abspath(explicit)
    matches = sorted(glob.glob(os.path.join(directory, "**", f"*{suffix}*.wav"),
                               recursive=True))
    if not matches:
        print(f"[FATAL] No se encontro ningun archivo *{suffix}*.wav en: "
              f"{directory}", file=sys.stderr)
        sys.exit(1)
    if len(matches) > 1:
        print(f"[FATAL] {label}: {len(matches)} candidatos ambiguos para "
              f"*{suffix}*.wav en {directory}. Nadie elige el primero:",
              file=sys.stderr)
        for m in matches:
            print(f"    - {os.path.abspath(m)}", file=sys.stderr)
        print("        Resuelve con el argumento explicito del paso "
              f"(p.ej. --{label.replace('_', '-')} RUTA).", file=sys.stderr)
        sys.exit(2)
    return os.path.abspath(matches[0])


def find_file_optional(directory: str, suffix: str, label: str):
    """Identificacion OPCIONAL (diagnostico): 0 -> None; >1 -> None + aviso
    (nunca se elige el primero); 1 -> ruta."""
    if not directory:
        return None
    matches = sorted(glob.glob(os.path.join(directory, "**", f"*{suffix}*.wav"),
                               recursive=True))
    if not matches:
        return None
    if len(matches) > 1:
        print(f"[!] {label}: {len(matches)} candidatos *{suffix}*.wav en "
              f"{directory}: diagnostico OMITIDO (sin primer-match):")
        for m in matches:
            print(f"    - {os.path.abspath(m)}")
        return None
    return os.path.abspath(matches[0])


def probe(path: str) -> dict:
    info = sf.info(path)
    return {"path": os.path.abspath(path), "samplerate": info.samplerate,
            "channels": info.channels, "frames": info.frames,
            "subtype": info.subtype, "duration_s":
                round(info.frames / max(info.samplerate, 1), 6),
            "sha256": sha256_file(path)}


def check_compatibility(inputs: dict, allow_crop: bool) -> tuple[dict, int]:
    """AUDIT_015: sr/canales estrictos; largos -> error salvo --allow-crop."""
    srs = {k: v["samplerate"] for k, v in inputs.items()}
    chs = {k: v["channels"] for k, v in inputs.items()}
    if len(set(srs.values())) != 1:
        print(f"[FATAL] sample_rate incompatible entre entradas: {srs}",
              file=sys.stderr)
        sys.exit(1)
    if len(set(chs.values())) != 1:
        print(f"[FATAL] numero de canales incompatible entre entradas: {chs}",
              file=sys.stderr)
        sys.exit(1)
    lens = {k: v["frames"] for k, v in inputs.items()}
    min_len = min(lens.values())
    if len(set(lens.values())) != 1:
        if not allow_crop:
            print(f"[FATAL] duraciones distintas (NO se trunca en silencio): "
                  f"{lens} muestras. Re-aligna las corridas o repite con "
                  f"--allow-crop para recortar explicitamente a {min_len}.",
                  file=sys.stderr)
            sys.exit(1)
        print(f"[!] --allow-crop: recorte EXPLICITO a {min_len} muestras "
              f"(originales: {lens}).")
        for k, v in inputs.items():
            print(f"    {k}: {v['frames']} -> {min_len} "
                  f"({v['frames'] - min_len} muestras fuera)")
    return inputs, min_len


def estimate_lag_ms(path_a: str, path_b: str, max_seconds: float = 5.0) -> float:
    """Desfase (ms) entre dos archivos por correlacion FFT en mono (015)."""
    with sf.SoundFile(path_a) as fa, sf.SoundFile(path_b) as fb:
        n = int(min(fa.frames, fb.frames, max_seconds * fa.samplerate))
        if n < 256:
            return 0.0
        sr = fa.samplerate
        a = fa.read(n, dtype="float64", always_2d=True).mean(axis=1)
        b = fb.read(n, dtype="float64", always_2d=True).mean(axis=1)
    a = a - a.mean(); b = b - b.mean()
    nfft = 1 << int(np.ceil(np.log2(2 * n)))
    cc = np.fft.irfft(np.fft.rfft(a, nfft) * np.conj(np.fft.rfft(b, nfft)),
                      nfft)
    cc = np.concatenate([cc[-n + 1:], cc[:n]])
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-30
    cc = cc / denom
    lag = int(np.argmax(np.abs(cc))) - (n - 1)
    return lag / sr * 1000.0


def snr_db(ref: np.ndarray, err: np.ndarray) -> float:
    r = float(np.square(ref).sum())
    e = float(np.square(err).sum())
    return 10.0 * np.log10(r / max(e, 1e-30))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inyecta el Delta Vocal al SDV Normal "
                    "(SDV_hib = SDV_norm + gain*(SDI_id - SDI_norm)).")
    parser.add_argument("--dir_norm", required=True,
                        help="Carpeta de la corrida Normal.")
    parser.add_argument("--dir_id", required=True,
                        help="Carpeta de la corrida Identity.")
    parser.add_argument("--mix", default=None,
                        help="Mix original (v2, OPCIONAL): con el se verifica "
                             "la complementariedad de la rama Normal (e_norm).")
    parser.add_argument("--sdv-norm", default=None,
                        help="Ruta explicita del SDV Normal (evita el glob).")
    parser.add_argument("--sdi-norm", default=None,
                        help="Ruta explicita del SDI Normal (evita el glob).")
    parser.add_argument("--sdi-id", default=None,
                        help="Ruta explicita del SDI Identity (evita el glob).")
    parser.add_argument("--gain", type=float, default=0.5,
                        help="Ganancia del Delta Vocal.")
    parser.add_argument("--allow-crop", action="store_true",
                        help="Recorta EXPLICITAMENTE a la duracion minima "
                             "(si no, largos distintos son FATAL).")
    parser.add_argument("--out", required=True,
                        help="Ruta del archivo SDV Hibrido de salida.")
    args = parser.parse_args()

    print("[*] Buscando archivos (identificacion unica; sin primer-match)...")
    sdv_norm_path = find_file(args.dir_norm, "SDV", args.sdv_norm, "sdv_norm")
    sdi_norm_path = find_file(args.dir_norm, "SDI", args.sdi_norm, "sdi_norm")
    sdi_id_path = find_file(args.dir_id, "SDI", args.sdi_id, "sdi_id")
    # diagnostico opcional: SDV de la corrida identity (Delta_directa)
    sdv_id_path = find_file_optional(args.dir_id, "SDV", "sdv_id")

    print(f"    [Base]   SDV Normal: {sdv_norm_path}")
    print(f"    [Base]   SDI Normal: {sdi_norm_path}")
    print(f"    [Delta]  SDI Identity: {sdi_id_path}")
    if sdv_id_path:
        print(f"    [Diag]   SDV Identity: {sdv_id_path}")
    else:
        print("    [Diag]   SDV Identity: no disponible "
              "(Delta_directa no reportable)")

    inputs = {"sdv_norm": probe(sdv_norm_path),
              "sdi_norm": probe(sdi_norm_path),
              "sdi_id": probe(sdi_id_path)}
    if args.mix:
        if not os.path.isfile(args.mix):
            print(f"[FATAL] --mix no existe: {args.mix}", file=sys.stderr)
            sys.exit(1)
        inputs["mix"] = probe(args.mix)
    if sdv_id_path:
        inputs["sdv_id"] = probe(sdv_id_path)

    # Los 3 insumos originales: compatibilidad con recorte explicito opcional.
    core = {k: inputs[k] for k in ("sdv_norm", "sdi_norm", "sdi_id")}
    _, min_len = check_compatibility(core, args.allow_crop)
    # Opcionales (--mix, SDV_id): igualdad EXACTA con sdv_norm (proteccion
    # contra mezcla de ejecuciones distintas; nunca se recortan).
    for key in ("mix", "sdv_id"):
        if key in inputs and (
                inputs[key]["frames"] != inputs["sdv_norm"]["frames"]
                or inputs[key]["samplerate"] != inputs["sdv_norm"]["samplerate"]
                or inputs[key]["channels"] != inputs["sdv_norm"]["channels"]):
            print(f"[FATAL] {key}: frames/sr/ch "
                  f"({inputs[key]['frames']}/{inputs[key]['samplerate']}/"
                  f"{inputs[key]['channels']}) != SDV normal "
                  f"({inputs['sdv_norm']['frames']}/"
                  f"{inputs['sdv_norm']['samplerate']}/"
                  f"{inputs['sdv_norm']['channels']}). Posible mezcla de "
                  f"ejecuciones distintas: se aborta.", file=sys.stderr)
            sys.exit(1)

    lag_ms = estimate_lag_ms(sdi_norm_path, sdi_id_path)
    print(f"[*] Desfase estimado SDI_norm vs SDI_id: {lag_ms:+.3f} ms")
    if abs(lag_ms) > 2.0:
        print(f"[!] AVISO: las corridas parecen desalineadas (>2 ms). El "
              f"Delta puede dominar por DESFASE, no por informacion vocal.")

    sdv_norm, sr = sf.read(sdv_norm_path, dtype="float64", always_2d=True)
    sdi_norm, _ = sf.read(sdi_norm_path, dtype="float64", always_2d=True)
    sdi_id, _ = sf.read(sdi_id_path, dtype="float64", always_2d=True)
    sdv_norm = sdv_norm[:min_len]
    sdi_norm = sdi_norm[:min_len]
    sdi_id = sdi_id[:min_len]

    # ---- Delta e hibrido (formula ACTUAL, inalterada) --------------------
    print("[*] Delta_indirecta = SDI_identity - SDI_normal  "
          "(= (SDV_norm - SDV_id) + e_norm; ver docstring AUDIT_014 v2)")
    delta_vocal = sdi_id - sdi_norm

    print(f"[*] SDV_hib = SDV_norm + {args.gain} * Delta_indirecta  "
          f"(extrapolacion lineal; NO es afirmacion de recuperacion vocal)")
    sdv_hybrid = sdv_norm + (args.gain * delta_vocal)

    # ---- Punto 1: verificacion de complementariedad ----------------------
    complementarity = {
        "verified": False, "method": None, "recon_snr_db": None,
        "recon_rms": None, "relative_pct": None,
        "verdict": "NOT_CHECKED",
        "note": ("sin --mix la complementariedad NO ha sido verificada; la "
                 "equivalencia Delta = SDV_norm - SDV_id no es universal"),
    }
    e_norm = None
    if args.mix:
        mix_data, _ = sf.read(args.mix, dtype="float64", always_2d=True)
        mix_data = mix_data[:min_len]
        e_norm = mix_data - sdv_norm - sdi_norm
        snr_e = snr_db(mix_data, e_norm)
        rms_e = float(np.sqrt(np.mean(np.square(e_norm))))
        rms_mix = float(np.sqrt(np.mean(np.square(mix_data))))
        rel = 100.0 * rms_e / max(rms_mix, 1e-30)
        ok = snr_e >= COMPLEMENTARY_SNR_MIN_DB
        complementarity = {
            "verified": bool(ok), "method": "mix_direct",
            "recon_snr_db": snr_e, "recon_rms": rms_e,
            "relative_pct": rel, "threshold_db": COMPLEMENTARY_SNR_MIN_DB,
            "verdict": ("COMPLEMENTARIA" if ok else "CONTAMINADA"),
            "note": ("e_norm = mix - SDV_norm - SDI_norm; si CONTAMINADA, "
                     "Delta_indirecta incluye e_norm: no presentar la "
                     "equivalencia como universal"),
        }
        print(f"[*] Complementariedad de la rama Normal (--mix):")
        print(f"    e_norm rms = {rms_e:.6e}  ({rel:.4f}% del mix)  "
              f"SNR = {snr_e:.2f} dB  -> {complementarity['verdict']}")
        if ok:
            print("    [OK] Normal complementaria dentro del umbral "
                  f"({COMPLEMENTARY_SNR_MIN_DB:.0f} dB): la equivalencia "
                  "Delta_indirecta ~= Delta_directa se sostiene.")
        else:
            print("    [!] Normal NO complementaria: Delta_indirecta esta "
                  "contaminada por e_norm (gain*e_norm entra al hibrido).")
    else:
        print("[!] ADVERTENCIA: complementariedad NO verificada (sin --mix).")
        print("    La equivalencia Delta_indirecta = SDV_norm - SDV_id NO "
              "esta verificada y no debe presentarse como universal.")

    # ---- Punto 1: Delta_directa como diagnostico -------------------------
    delta_direct = {"available": False}
    if sdv_id_path:
        sdv_id, _ = sf.read(sdv_id_path, dtype="float64", always_2d=True)
        sdv_id = sdv_id[:min_len]
        d_dir = sdv_norm - sdv_id
        delta_direct = {
            "available": True, "path": inputs["sdv_id"]["path"],
            "rms": float(np.sqrt(np.mean(np.square(d_dir)))),
            "max_abs": float(np.abs(d_dir).max()),
        }
        print(f"[*] Diagnostico Delta_directa = SDV_norm - SDV_id: "
              f"rms={delta_direct['rms']:.6e} max={delta_direct['max_abs']:.6e}")
        if e_norm is not None:
            cons = delta_vocal - d_dir - e_norm
            delta_direct["consistency_max_abs"] = float(np.abs(cons).max())
            print(f"    Consistencia Delta_ind = Delta_dir + e_norm: "
                  f"max|residuo| = {delta_direct['consistency_max_abs']:.3e}")
    else:
        print("[*] Diagnostico Delta_directa: no disponible (dir_id sin SDV).")

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    sf.write(out_path, sdv_hybrid, sr, subtype="FLOAT")
    print(f"[OK] SDV Hibrido guardado en: {out_path}")

    # ---- Procedencia (AUDIT_017) ----------------------------------------
    prov = {
        "tool": "mix_delta.py", "version": "2.0", "generated_utc": utc_now(),
        "argv": sys.argv, "gain": args.gain, "min_len_used": min_len,
        "allow_crop": bool(args.allow_crop), "lag_sdi_norm_vs_id_ms": lag_ms,
        "inputs": inputs,
        "output": {"path": out_path, "sha256": sha256_file(out_path),
                   "frames": int(sdv_hybrid.shape[0]),
                   "samplerate": int(sr),
                   "channels": int(sdv_hybrid.shape[1])},
        "complementarity": complementarity,
        "delta_direct": delta_direct,
        "delta_math": {
            "delta_indirect": "SDI_id - SDI_norm = (SDV_norm - SDV_id) + e_norm",
            "e_norm": "mix - SDV_norm - SDI_norm",
            "delta_direct": "SDV_norm - SDV_id",
            "hybrid": ("SDV_norm + gain*Delta_indirect; solo si e_norm=0: "
                       "(1 + gain) * V_hat_norm - gain * V_hat_id"),
            "universal_equivalence": False,
            "claim": "sin evidencia adicional NO se afirma recuperacion vocal"},
    }
    prov_path = out_path + ".provenance.json"
    with open(prov_path, "w", encoding="utf-8") as fh:
        json.dump(prov, fh, indent=2, ensure_ascii=False, default=str)
    print(f"[*] Procedencia: {prov_path}")
    for k, v in inputs.items():
        print(f"    {k}: {v['path']}  sha256={v['sha256'][:16]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
