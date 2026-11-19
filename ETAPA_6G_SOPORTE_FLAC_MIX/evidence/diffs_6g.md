# Diffs 6G frente a las fuentes 6F

Sólo validación, lectura y trazabilidad. `wav_integridad_6f.py` no se modifica.

### diff Hardened (6F -> 6G)

```diff
--- /home/user/SDV-SDI_SGM/ETAPA_6F_CIERRE_CORRECTIVO/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py	2026-11-19 20:15:50.223304319 +0000
+++ /home/user/SDV-SDI_SGM/ETAPA_6G_SOPORTE_FLAC_MIX/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py	2026-11-19 20:25:29.679221436 +0000
@@ -293,6 +293,10 @@
     }
     return table.get(subtype, 0)
 
+from audio_integridad_6g import (check_file_unchanged as _check_unchanged_6g,
+                              container_of as _container_6g,
+                              verify_audio as _verify_audio_6g)
+
 from atribucion_6f import (measure, verify_wave, alignment_gate,
                         analyze_files as _analyze_files_6f,
                         combine_channels as _combine_6f)
@@ -306,7 +310,7 @@
     info.size_bytes = os.path.getsize(path)
     try:
         sfi = sf.info(path)
-        verify_wave(path, sfi)
+        _verify_audio_6g(path, sfi)
     except Exception as exc:
         info.errors.append(f"soundfile no pudo abrir el archivo: {exc}")
         return info
@@ -1398,6 +1402,14 @@
 
     log(f"Validación de entradas OK: Mix {mix_info.sample_rate}Hz/{mix_info.channels}ch ({fmt_size(mix_info.size_bytes)}) | {len(pairs)} Pares")
     ctx["mix_info"] = mix_info
+    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
+    ctx["container_6g"] = {
+        "mix_path": os.path.abspath(mix_path),
+        "container": _container_6g(mix_path),
+        "format": mix_info.format, "subtype": mix_info.subtype,
+        "probe_sha256": mix_info.sha256, "after": None,
+        "policy": "detect_only_no_conversion"}
+
     ctx["pairs"] = pairs
 
     # 2. Modo Dry Run
@@ -1764,6 +1776,19 @@
             run_dir_final = run_dir_final + f"_{stamp}"
         os.rename(run_dir, run_dir_final)
         log(f"Corrida finalizada exitosamente en: {run_dir_final}")
+        ctx["container_6g"]["after"] = _check_unchanged_6g(
+            mix_path, mix_info.sha256)
+        try:
+            with open(os.path.join(run_dir_final, "input_integrity_6g.json"),
+                      "w", encoding="utf-8") as _f6g:
+                json.dump(json_safe(ctx["container_6g"]), _f6g, indent=2,
+                          ensure_ascii=False)
+        except Exception as _exc6g:
+            log("[6G] no se pudo escribir input_integrity_6g.json: %s" % _exc6g)
+        if not ctx["container_6g"]["after"].get("unchanged"):
+            log("[FATAL] El Mix cambió durante el procesamiento: "
+                + str(ctx["container_6g"]["after"]))
+            return EXIT_PROCESSING, None
         return EXIT_OK, run_dir_final
 
     except KeyboardInterrupt:
```

### diff EVO (6F -> 6G)

```diff
--- /home/user/SDV-SDI_SGM/ETAPA_6F_CIERRE_CORRECTIVO/motores/MOTOR_SEP_SDV-SDI_EVO.py	2026-11-19 20:15:50.223304319 +0000
+++ /home/user/SDV-SDI_SGM/ETAPA_6G_SOPORTE_FLAC_MIX/motores/MOTOR_SEP_SDV-SDI_EVO.py	2026-11-19 20:25:29.679221436 +0000
@@ -298,6 +298,10 @@
     }
     return table.get(subtype, 0)
 
+from audio_integridad_6g import (check_file_unchanged as _check_unchanged_6g,
+                              container_of as _container_6g,
+                              verify_audio as _verify_audio_6g)
+
 from atribucion_6f import (measure, verify_wave, alignment_gate,
                         analyze_files as _analyze_files_6f,
                         combine_channels as _combine_6f)
@@ -311,7 +315,7 @@
     info.size_bytes = os.path.getsize(path)
     try:
         sfi = sf.info(path)
-        verify_wave(path, sfi)
+        _verify_audio_6g(path, sfi)
     except Exception as exc:
         info.errors.append(f"soundfile no pudo abrir el archivo: {exc}")
         return info
@@ -1463,6 +1467,14 @@
 
     log(f"Validación de entradas OK: Mix {mix_info.sample_rate}Hz/{mix_info.channels}ch ({fmt_size(mix_info.size_bytes)}) | {len(pairs)} Pares")
     ctx["mix_info"] = mix_info
+    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
+    ctx["container_6g"] = {
+        "mix_path": os.path.abspath(mix_path),
+        "container": _container_6g(mix_path),
+        "format": mix_info.format, "subtype": mix_info.subtype,
+        "probe_sha256": mix_info.sha256, "after": None,
+        "policy": "detect_only_no_conversion"}
+
     ctx["pairs"] = pairs
 
     # 2. Modo Dry Run
@@ -1875,6 +1887,19 @@
             run_dir_final = run_dir_final + f"_{stamp}"
         os.rename(run_dir, run_dir_final)
         log(f"Corrida finalizada exitosamente en: {run_dir_final}")
+        ctx["container_6g"]["after"] = _check_unchanged_6g(
+            mix_path, mix_info.sha256)
+        try:
+            with open(os.path.join(run_dir_final, "input_integrity_6g.json"),
+                      "w", encoding="utf-8") as _f6g:
+                json.dump(json_safe(ctx["container_6g"]), _f6g, indent=2,
+                          ensure_ascii=False)
+        except Exception as _exc6g:
+            log("[6G] no se pudo escribir input_integrity_6g.json: %s" % _exc6g)
+        if not ctx["container_6g"]["after"].get("unchanged"):
+            log("[FATAL] El Mix cambió durante el procesamiento: "
+                + str(ctx["container_6g"]["after"]))
+            return EXIT_PROCESSING, None
         return EXIT_OK, run_dir_final
 
     except KeyboardInterrupt:
```

### diff MQR (6F -> 6G)

```diff
--- /home/user/SDV-SDI_SGM/ETAPA_6F_CIERRE_CORRECTIVO/motores/sdv_sdi_mqr_engine.py	2026-11-19 20:15:50.223304319 +0000
+++ /home/user/SDV-SDI_SGM/ETAPA_6G_SOPORTE_FLAC_MIX/motores/sdv_sdi_mqr_engine.py	2026-11-19 20:25:29.687221476 +0000
@@ -216,7 +216,7 @@
 
 # --- Entradas (spec input_architecture / input_validation) ------------------
 REQUIRED_SAMPLE_RATE = 44100          # mix y guides: reject_if_mismatch
-MIX_ALLOWED_EXTENSIONS = (".wav",)
+MIX_ALLOWED_EXTENSIONS = (".wav", ".flac")  # 6G: contenedor verificado
 GUIDE_ALLOWED_EXTENSIONS = (".wav", ".flac")
 MIX_ALLOWED_SUBTYPES = ("PCM_16", "PCM_24", "PCM_32", "FLOAT")  # D4: FLOAT ok con nota
 GUIDE_ALLOWED_SUBTYPES = None         # None = cualquier subtipo WAV/FLAC legible
@@ -486,6 +486,10 @@
     return table.get(subtype, 0)
 
 
+from audio_integridad_6g import (check_file_unchanged as _check_unchanged_6g,
+                              container_of as _container_6g,
+                              verify_audio as _verify_audio_6g)
+
 from atribucion_6f import (measure, verify_wave, alignment_gate,
                         analyze_files as _analyze_files_6f,
                         combine_channels as _combine_6f)
@@ -501,7 +505,7 @@
     info.size_bytes = os.path.getsize(path)
     try:
         sfi = sf.info(path)
-        verify_wave(path, sfi)
+        _verify_audio_6g(path, sfi)
     except Exception as exc:  # soundfile error generico
         info.errors.append("soundfile no pudo abrir el archivo: %s" % exc)
         return info
@@ -2108,6 +2112,14 @@
            len(pairs)))
 
     ctx["mix_info"] = mix_info
+    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
+    ctx["container_6g"] = {
+        "mix_path": os.path.abspath(mix_path),
+        "container": _container_6g(mix_path),
+        "format": mix_info.format, "subtype": mix_info.subtype,
+        "probe_sha256": mix_info.sha256, "after": None,
+        "policy": "detect_only_no_conversion"}
+
     ctx["pairs"] = pairs
 
     # --- dry_run: plan sin computo (spec cli.required_modes) -----------------
@@ -2230,6 +2242,19 @@
 
     close_tee()
     log("Corrida COMPLETA: %s" % run_dir_final)
+    ctx["container_6g"]["after"] = _check_unchanged_6g(
+        mix_path, mix_info.sha256)
+    try:
+        with open(os.path.join(run_dir_final, "input_integrity_6g.json"),
+                  "w", encoding="utf-8") as _f6g:
+            json.dump(json_safe(ctx["container_6g"]), _f6g, indent=2,
+                      ensure_ascii=False)
+    except Exception as _exc6g:
+        log("[6G] no se pudo escribir input_integrity_6g.json: %s" % _exc6g)
+    if not ctx["container_6g"]["after"].get("unchanged"):
+        log("[FATAL] El Mix cambió durante el procesamiento: "
+            + str(ctx["container_6g"]["after"]))
+        return EXIT_PROCESSING, None
     return EXIT_OK, run_dir_final
 
 
```

### diff atribucion_6f.py (6F -> 6G)

```diff
--- /home/user/SDV-SDI_SGM/ETAPA_6F_CIERRE_CORRECTIVO/motores/atribucion_6f.py	2026-11-19 20:15:50.223304319 +0000
+++ /home/user/SDV-SDI_SGM/ETAPA_6G_SOPORTE_FLAC_MIX/motores/atribucion_6f.py	2026-11-19 20:25:48.463316319 +0000
@@ -27,8 +27,8 @@
 import numpy as np
 from scipy.signal import correlate
 
-from wav_integridad_6f import (WaveError, check_unchanged, open_validated,
-                               verify_wave)
+from wav_integridad_6f import WaveError, check_unchanged, verify_wave  # verify_wave: reexport 6F
+from audio_integridad_6g import open_audio as open_validated
 
 WINDOWS = 6
 MIN_HALF = 2048
```
