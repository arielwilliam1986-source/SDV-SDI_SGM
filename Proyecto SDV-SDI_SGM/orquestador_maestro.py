import os
import glob
import json
import argparse
import soundfile as sf
import numpy as np

parser = argparse.ArgumentParser(description="Orquestador Maestro SGM (Fórmula Will)")
parser.add_argument("--dir", required=True, help="Ruta a la carpeta maestra de la canción.")
parser.add_argument("--mix", required=True, help="Nombre exacto del archivo Mix (ej. Mix.wav).")
args = parser.parse_args()

base_dir = args.dir
mix_path = os.path.join(base_dir, args.mix)
dir_simples = os.path.join(base_dir, "Stems Masks Simples")
dir_reverb = os.path.join(base_dir, "Stems Masks Reverb Removal")
out_dir = os.path.join(base_dir, "Residuales_Finales")

os.makedirs(out_dir, exist_ok=True)

print(f"[*] Iniciando orquestación en: {base_dir}")
mix, sr = sf.read(mix_path, dtype='float64', always_2d=True)
manifest_pairs = []

# 1. Modelos simples
if os.path.exists(dir_simples):
    for instrum_path in glob.glob(os.path.join(dir_simples, "*_instrum.wav")):
        model_name = os.path.basename(instrum_path).replace("_instrum.wav", "")
        vocals_path = instrum_path.replace("_instrum.wav", "_vocals.wav")
        if os.path.exists(vocals_path):
            print(f"  [>] Resta simple: {model_name}")
            instrum, _ = sf.read(instrum_path, dtype='float64', always_2d=True)
            vocals, _ = sf.read(vocals_path, dtype='float64', always_2d=True)
            min_len = min(len(mix), len(instrum), len(vocals))
            sdv = mix[:min_len] - instrum[:min_len]
            sdi = mix[:min_len] - vocals[:min_len]
            
            out_sdv = os.path.join(out_dir, f"{model_name}_RESIDUAL_SDV.wav")
            out_sdi = os.path.join(out_dir, f"{model_name}_RESIDUAL_SDI.wav")
            sf.write(out_sdv, sdv, sr, subtype='FLOAT')
            sf.write(out_sdi, sdi, sr, subtype='FLOAT')
            
            manifest_pairs.append({"pair_id": f"simple_{model_name}", "vocal_path": out_sdv, "instrumental_path": out_sdi})

# 2. Modelos Reverb Removal
if os.path.exists(dir_reverb):
    for model in ["sucial", "anvuew"]:
        path_A, path_C, path_D = None, None, None
        for f in os.listdir(dir_reverb):
            if model in f and f.endswith('.wav'):
                if "_[A]" in f: path_A = os.path.join(dir_reverb, f)
                elif "_[C]" in f: path_C = os.path.join(dir_reverb, f)
                elif "_[D]" in f: path_D = os.path.join(dir_reverb, f)
                
        if path_A and path_C and path_D:
            print(f"  [>] Fórmula Will: {model}")
            A, _ = sf.read(path_A, dtype='float64', always_2d=True)
            C, _ = sf.read(path_C, dtype='float64', always_2d=True)
            D, _ = sf.read(path_D, dtype='float64', always_2d=True)
            min_len = min(len(mix), len(A), len(C), len(D))
            sdv = mix[:min_len] - A[:min_len] + D[:min_len]
            sdi = mix[:min_len] - C[:min_len] - D[:min_len]
            
            out_sdv = os.path.join(out_dir, f"{model}_custom_RESIDUAL_SDV.wav")
            out_sdi = os.path.join(out_dir, f"{model}_custom_RESIDUAL_SDI.wav")
            sf.write(out_sdv, sdv, sr, subtype='FLOAT')
            sf.write(out_sdi, sdi, sr, subtype='FLOAT')
            
            manifest_pairs.append({"pair_id": f"custom_{model}", "vocal_path": out_sdv, "instrumental_path": out_sdi})

manifest_path = os.path.join(base_dir, "manifest_maestro.json")
with open(manifest_path, 'w') as f:
    json.dump({"source_mix_file": mix_path, "pairs": manifest_pairs}, f, indent=4)
    
print(f"\n[✓] Manifiesto guardado: {manifest_path} ({len(manifest_pairs)} pares).")
