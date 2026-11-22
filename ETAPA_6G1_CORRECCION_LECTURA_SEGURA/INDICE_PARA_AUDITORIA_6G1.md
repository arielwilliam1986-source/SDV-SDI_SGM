# Índice para auditoría — Etapa 6G.1

**Base:** `ee19fe208449249a20e194b09c9452b782c7de70` (cierre de 6G).
**Alcance:** sólo `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/`.
**Datos:** fixtures sintéticos; ninguna canción real, ningún piloto.

---

## 1. Orden de lectura sugerido

| # | Documento | Para qué sirve |
|---|---|---|
| 1 | `INFORME_IMPLEMENTACION_6G1.md` | Qué se corrigió, dónde y con qué superficie de cambio. |
| 2 | `INFORME_VALIDACION_6G1.md` | Pruebas 1–10, tabla de veredictos, casos no ejecutados. |
| 3 | `NO_REGRESION_DSP_6G1.md` | Evidencia de que el DSP es idéntico a 6G. |
| 4 | `evidence/matriz_global_6g1.csv` | 64 filas de resultados, una por escenario. |
| 5 | `evidence/resumen_6g1.json` | Conteos, no ejecutadas, equivalencias, hashes de fuentes. |
| 6 | `MANIFEST_6G1.json` + `SHA256SUMS.txt` | Integridad de la entrega. |

---

## 2. Archivos por función

### Motores (copias 6G.1)

| Archivo | Cambio respecto de 6G |
|---|---|
| `motores/lectura_segura_6g1.py` | **nuevo**: `MixHandle`, `abrir_mix`, `abortar_6g1`. |
| `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py` | apertura vigilada, cierre diferido, guarda final, escala sobre el descriptor (+29/−9). |
| `motores/MOTOR_SEP_SDV-SDI_EVO.py` | ídem (+29/−9). |
| `motores/sdv_sdi_mqr_engine.py` | ídem; el handle se publica en `ctx` porque el bucle vive en `_run_core` (+33/−10). |
| `motores/wav_integridad_6f.py` | comparación de identidad por claves de objeto (+25/−3): corrige el falso negativo en FLAC de 6G. |
| `motores/audio_integridad_6g.py` | misma normalización (+13/−2). |
| `motores/atribucion_6f.py` | sin cambios (hash idéntico a 6G). |

### Scripts

| Script | Qué produce |
|---|---|
| `scripts/preparar_fixtures_6g1.py` | 11 fixtures sintéticos + `fixtures/fixtures_manifest.json`. |
| `scripts/aplicar_cambios_6g1.py` | Aplicación idempotente de los parches a las copias (trazabilidad del cambio). |
| `scripts/comun_6g1.py` | Ejecución de motores, hashes de PCM real, vigía de sustitución, siembra de archivos ajenos. |
| `scripts/validar_contenedores_6g1.py` | Pruebas 1, 2, 3, 8, 9. |
| `scripts/sustituciones_6g1.py` | Pruebas 4, 5, 6, 7. |
| `scripts/no_regresion_dsp_6g1.py` | Prueba 10 (AST + huella + PCM vs 6G). |
| `scripts/consolidar_6g1.py` | Matriz global, resumen, `SHA256SUMS.txt`, `MANIFEST_6G1.json`. |

### Evidencia

| Archivo | Contenido |
|---|---|
| `evidence/matriz_global_6g1.csv` | Todas las filas de las pruebas 1–10, con enum de veredicto. |
| `evidence/matriz_contenedores_6g1.csv` | Pruebas 1, 2, 3, 8, 9. |
| `evidence/matriz_sustituciones_6g1.csv` | Pruebas 4, 5, 6, 7. |
| `evidence/contenedores_6g1.json` | Hashes de PCM por salida, informes normalizados, integridad de cada corrida. |
| `evidence/sustituciones_6g1.json` | Intentos de sustitución, motivo del aborto, archivos conservados. |
| `evidence/no_regresion_dsp_6g1.csv/.json` | Definiciones y constantes que cambian, huella DSP, PCM vs 6G. |
| `evidence/resumen_6g1.json` | Conteos, `NOT_EXECUTED`, equivalencias, hashes de fuentes 6G/6G.1. |
| `fixtures/fixtures_manifest.json` | Hashes y geometría de todos los fixtures. |

---

## 3. Preguntas que la auditoría puede responder con estos archivos

1. **¿El DSP leyó el mismo objeto que se validó?**
   `evidence/contenedores_6g1.json` → `casos[*].integrity` (`after`,
   `ruta_actual`) y `casos[*].pcm` con el hash por salida.
2. **¿Una sustitución puede alimentar el DSP?**
   `evidence/sustituciones_6g1.json` → `unitaria` (guarda determinista) y
   `casos[*]` (4c antes del DSP, 5 durante, 6 después).
3. **¿Qué ocurre con las salidas parciales al abortar?** (comportamiento
   vigente C-R1)
   `ABORT_6G1.json` (`schema=abort-6g1/3`): **ningún archivo se elimina**;
   las salidas de la corrida quedan **invalidadas y conservadas** en el
   provisional (`salidas_invalidadas` + `estado_salidas_invalidadas`) y
   `resultados_validos` permanece vacío; `casos[*].estado` y las filas de
   prueba `7` son registro **histórico** de la semántica `abort-6g1/2` (que
   entonces eliminaba las salidas acreditadas).
4. **¿Se borraron archivos ajenos?**
   `casos[*].estado.ajenos_presentes` (tres archivos sembrados, los tres
   presentes tras el aborto) y `conservados` en `ABORT_6G1.json`.
5. **¿El DSP cambió?**
   `evidence/no_regresion_dsp_6g1.json` → `motores[*]` (`dsp_ok`, `pcm`), y
   `NO_REGRESION_DSP_6G1.md` §2–§4.
6. **¿La matriz vuelve a comparar diccionarios vacíos?**
   `INFORME_VALIDACION_6G1.md` §1 (`_pcm_real`, enum) y el código en
   `scripts/validar_contenedores_6g1.py` (`pcm_real`, `_pcm_real`).
7. **¿Qué no se ejecutó?**
   `evidence/resumen_6g1.json` → `no_ejecutadas`; `INFORME_VALIDACION_6G1.md` §7.

---

## 4. Comprobaciones de integridad

```bash
cd ETAPA_6G1_CORRECCION_LECTURA_SEGURA
sha256sum -c SHA256SUMS.txt            # entrega 6G.1
cd ..
sha256sum -c ETAPA_6G_SOPORTE_FLAC_MIX/SHA256SUMS.txt   # 6G sigue intacta
git status --porcelain -- . ':(exclude)ETAPA_6G1_CORRECCION_LECTURA_SEGURA'   # vacío
```

---

## 5. Bloque para auditoría externa (copiar y pegar en ChatGPT)

```
Audita la Etapa 6G.1 del repositorio arielwilliam1986-source/SDV-SDI_SGM.

Contexto: 6G añadió soporte WAV/FLAC para el Mix y quedó publicada en
ee19fe208449249a20e194b09c9452b782c7de70. 6G.1 corrige tres cosas:
(1) el Mix se valida una vez y se lee siempre del mismo descriptor
(/proc/self/fd/N), sin reabrir la ruta; (2) si el archivo o la ruta cambian,
el motor aborta, invalida sus salidas y registra el motivo sin borrar archivos
ajenos; (3) la matriz de validación exige PCM real con hash y usa el enum
ACCEPTED / REJECTED / PCM_IDENTICAL / PCM_DIFFERENT / NOT_APPLICABLE /
NOT_EXECUTED. El DSP no debe cambiar.

Lee, en este orden:
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INDICE_PARA_AUDITORIA_6G1.md
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_IMPLEMENTACION_6G1.md
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_VALIDACION_6G1.md
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/NO_REGRESION_DSP_6G1.md
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/matriz_global_6g1.csv
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/resumen_6g1.json
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py
  (busca _abrir_mix_6g1, hmix.verificar, ruta_actual)
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/validar_contenedores_6g1.py
- ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/sustituciones_6g1.py

Verifica en particular:
1. Que no queda ninguna reapertura del Mix por ruta después de la validación
   (grep de "sf.SoundFile(mix_info.path)" y "mix_info.path" en los tres motores).
2. Que la guarda final exige contenido Y ruta (after.unchanged y
   ruta_actual.unchanged) y que aborta sin presentar salidas parciales.
3. Que abortar_6g1 **no elimina ningún archivo** (C-R1): las salidas de la
   corrida quedan invalidadas y conservadas en el provisional, los archivos
   ajenos se conservan con su motivo y `resultados_validos` permanece vacío
   (`schema=abort-6g1/3`).
4. Que un veredicto PCM_IDENTICAL sólo aparece con archivos PCM reales y hashes.
5. Que la prueba 10 demuestra DSP idéntico (constantes, huella de literales y
   llamadas, PCM byte a byte) frente a las copias 6G.
6. Que todo lo no ejecutado está marcado NOT_EXECUTED con su motivo.

Señala cualquier discrepancia entre lo que dicen los informes y lo que muestran
los CSV/JSON, y cualquier debilidad que permita sustituir el Mix sin aborto.
```
