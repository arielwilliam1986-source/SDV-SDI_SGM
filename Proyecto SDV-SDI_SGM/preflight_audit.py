#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import argparse
import soundfile as sf
import numpy as np

def load_audio(path):
    data, sr = sf.read(path, dtype='float64', always_2d=True)
    return data, sr

def check_duplicates(residuals, names):
    """Comprueba si dos guías son idénticas (diferencia menor a -90 dB)."""
    n = len(names)
    duplicates = []
    print("  [*] Analizando duplicados entre las guías...")
    for i in range(n):
        for j in range(i + 1, n):
            sr = 44100
            mid = len(residuals[i]) // 2
            slice_i = residuals[i][mid:mid+sr*10, 0]
            slice_j = residuals[j][mid:mid+sr*10, 0]
            
            diff = np.abs(slice_i - slice_j)
            rms_diff = 20 * np.log10(np.sqrt(np.mean(diff**2)) + 1e-12)
            
            if rms_diff < -90.0:
                print(f"    [!] DUPLICADO: {names[i]} == {names[j]} (Dif: {rms_diff:.1f} dB)")
                duplicates.append(names[j])
    return list(set(duplicates))

def main():
    parser = argparse.ArgumentParser(description="Pre-vuelo SGM: Resta y filtro de duplicados.")
    parser.add_argument("--dir", required=True, help="Ruta absoluta de la carpeta del proyecto.")
    parser.add_argument("--mix", default="02. Ice Queen.wav", help="Nombre del archivo Mix original.")
    args = parser.parse_args()

    carpeta = args.dir
    out_dir = os.path.join(carpeta, "Resultados_Consenso")
    os.makedirs(out_dir, exist_ok=True)

    print(f"[*] Iniciando auditoría en: {carpeta}")
    mix_path = os.path.join(carpeta, args.mix)
    
    if not os.path.exists(mix_path):
        print(f"[FATAL] No se encontró el Mix: {mix_path}")
        return

    mix_data, sr = load_audio(mix_path)

    models = []
    for f in os.listdir(carpeta):
        if f.endswith("_instrum.wav"):
            model_name = f.replace("_instrum.wav", "")
            v_path = os.path.join(carpeta, f"{model_name}_vocals.wav")
            if os.path.exists(v_path):
                models.append(model_name)
    
    print(f"[*] Detectados {len(models)} modelos válidos.")

    residuals_sdv = {}
    residuals_sdi = {}
    
    for model in models:
        print(f"  [>] Restando stems de: {model}")
        instrum, _ = load_audio(os.path.join(carpeta, f"{model}_instrum.wav"))
        vocals, _ = load_audio(os.path.join(carpeta, f"{model}_vocals.wav"))
        
        sdv = mix_data - instrum
        sdi = mix_data - vocals
        
        residuals_sdv[model] = sdv
        residuals_sdi[model] = sdi
        
        sf.write(os.path.join(out_dir, f"{model}_RESIDUAL_SDV.wav"), sdv, sr, subtype='FLOAT')
        sf.write(os.path.join(out_dir, f"{model}_RESIDUAL_SDI.wav"), sdi, sr, subtype='FLOAT')

    print("\n[*] Filtro de duplicados (SDV)...")
    dups_sdv = check_duplicates(list(residuals_sdv.values()), list(residuals_sdv.keys()))
    
    print("\n[*] Filtro de duplicados (SDI)...")
    dups_sdi = check_duplicates(list(residuals_sdi.values()), list(residuals_sdi.keys()))

    duplicados_totales = set(dups_sdv + dups_sdi)
    modelos_finales = [m for m in models if m not in duplicados_totales]

    manifest = {
        "source_mix_file": mix_path,
        "pairs": []
    }
    
    print(f"\n[*] Creando manifiesto con {len(modelos_finales)} modelos...")
    for i, model in enumerate(modelos_finales):
        manifest["pairs"].append({
            "pair_id": f"modelo_{i+1}_{model}",
            "vocal_path": os.path.join(out_dir, f"{model}_RESIDUAL_SDV.wav"),
            "instrumental_path": os.path.join(out_dir, f"{model}_RESIDUAL_SDI.wav")
        })

    manifest_path = os.path.join(carpeta, "manifest_final_pruned.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=4)
        
    print(f"\n[✓] Proceso completado. Manifiesto listo para el motor de Arenita.")

if __name__ == "__main__":
    main()
