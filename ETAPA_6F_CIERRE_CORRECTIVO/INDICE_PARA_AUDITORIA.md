# 6F · Índice para auditoría externa

Punto de entrada único para revisión independiente de la etapa 6F.

## Lectura en dos enlaces (todo el texto, sin navegar el repositorio)

| Tomo | Contenido | URL raw |
|---|---|---|
| 1 | los nueve informes, este índice y el informe de entrega | `https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/89d5c189-sdv-sdi-sgm/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_6F_TOMO_1_INFORMES.md` |
| 2 | hashes, matrices completas (atribución, CLI, WAV) | `https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/89d5c189-sdv-sdi-sgm/ETAPA_6F_CIERRE_CORRECTIVO/AUDITORIA_6F_TOMO_2_EVIDENCIA.md` |

Ambos tomos se regeneran con `scripts/empaquetar_auditoria_6f.py`. Este índice
solo no contiene los informes: es un mapa con resumen y advertencias.

| Dato | Valor |
|---|---|
| Repositorio | `arielwilliam1986-source/SDV-SDI_SGM` (público) |
| Rama | `arena/89d5c189-sdv-sdi-sgm` |
| Commit base exigido | `b72ce49ae787c72a1148bbec95db35dba460d279` |
| Congelamiento de implementación | `5d344e1` |
| Cierre 6F (este árbol) | ver el commit que contiene este índice |
| Dictamen | **APROBADO CON LIMITACIONES** |
| Informe de entrega (16 puntos + confirmaciones) | `ENTREGA_6F.md` |

## Informes

| Documento | Ruta |
|---|---|
| Implementación | `INFORME_IMPLEMENTACION_6F.md` |
| Validación con reserva independiente | `INFORME_VALIDACION_INDEPENDIENTE_6F.md` |
| Auditoría CLI y bloqueos | `AUDITORIA_CLI_6F.md` |
| Auditoría de integridad WAV | `AUDITORIA_WAV_6F.md` |
| Diagnóstico MQR S7 | `DIAGNOSTICO_MQR_S7_6F.md` |
| Estéreo L/R | `ANALISIS_ESTEREO_LR_6F.md` |
| No regresión DSP | `NO_REGRESION_DSP_6F.md` |
| Recursos y duraciones | `RECURSOS_Y_DURACIONES_6F.md` |
| Limitaciones y casos fuera de capacidad | `LIMITACIONES_Y_CASOS_UNKNOWN_6F.md` |

## Evidencia y matrices

| Artefacto | Ruta |
|---|---|
| Manifiesto (hashes, entorno, estímulos, resultados) | `MANIFEST_6F.json` |
| Hashes verificables (`sha256sum -c`) | `SHA256SUMS.txt` |
| Matriz de atribución (177 filas, desarrollo + reserva) | `MATRIZ_RESULTADOS_6F.csv` |
| Matriz de CLI | `MATRIZ_CLI_6F.csv` |
| Matriz de WAV | `MATRIZ_WAV_6F.csv` |
| Evidencia JSON | `evidence/*.json`, `evidence/matriz_*.csv` |
| Motores 6F | `motores/MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py`, `motores/MOTOR_SEP_SDV-SDI_EVO.py`, `motores/sdv_sdi_mqr_engine.py` |
| Módulos nuevos | `motores/atribucion_6f.py`, `motores/wav_integridad_6f.py` |
| Reproducción | `README.md`, `requirements.txt`, `scripts/*.py` |

## Resumen numérico

* Atribución: 31/31 por motor en desarrollo (93 filas) y 28/28 por motor en
  reserva (84 filas).
* CLI: 57/57 (desarrollo) y 30/30 (reserva); bloqueo con exit 1, 0 WAV y sin
  informe; permiso registrado sin shift ni cambio de polaridad.
* WAV: 39/39 y 10/10; perfil admitido PCM 8/16/24/32, float 32/64 y
  `WAVE_FORMAT_EXTENSIBLE` con GUID PCM/FLOAT.
* MQR S7: 6C aborta (`ZeroDivisionError`, exit 2); 6E y 6F publican `null`
  explícito; 6F bloquea sin permiso por guía periódica no identificable.
* DSP: PCM idéntico a 6E en 24/24 y a 6C en 23/24 (1 no comparable).

## Advertencias para el auditor

1. Los tres motores comparten `atribucion_6f.measure`: sus coincidencias no son
   validaciones independientes.
2. La reserva se definió después del congelamiento y no se usó para ajustar,
   pero fue construida por el mismo autor y comparte portadora de ruido.
3. No se usaron canciones reales; no se probó Termux ARM64 ni archivos largos.
4. `UNIQUE` significa «no se detectó réplica por encima del piso publicado», no
   unicidad matemática.
5. La detección TOCTOU no previene escrituras concurrentes.
