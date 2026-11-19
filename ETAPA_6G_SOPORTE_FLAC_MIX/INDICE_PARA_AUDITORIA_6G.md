# 6G · Índice para auditoría externa

Punto de entrada de la etapa 6G (soporte nativo WAV/FLAC del Mix original).

| Dato | Valor |
|---|---|
| Repositorio | `arielwilliam1986-source/SDV-SDI_SGM` (público) |
| Rama | `arena/89d5c189-sdv-sdi-sgm` |
| Commit base exigido | `663fb5f8b4d53c8445d482ecec4df6a0208c59f0` |
| Commit de implementación | el commit que contiene esta carpeta |
| Desviación declarada | rama nueva pedida no creada por restricción de Arena; sustituida por la rama activa con autorización expresa del usuario |

## Informes

| Documento | Contenido |
|---|---|
| `INFORME_IMPLEMENTACION_6G.md` | qué se cambió, por qué, qué no se hizo, límites |
| `INFORME_VALIDACION_6G.md` | 52 filas de contenedores, 12/12 motores, TOCTOU, recursos |
| `NO_REGRESION_DSP_6G.md` | AST, diffs (+26/−1, +27/−2, +2/−2), PCM 6F vs 6G |
| `README.md` | ejecución reproducible |

## Evidencia

| Artefacto | Contenido |
|---|---|
| `MANIFEST_6G.json` | base, rama, hashes de motores y fuentes 6F, fixtures, entorno |
| `SHA256SUMS.txt` | hashes verificables de toda la carpeta |
| `evidence/matriz_contenedores_6g.csv` | 52 filas: caso × (módulo + 3 motores) |
| `evidence/matriz_motores_6g.csv` | 24 filas: motor × modo × contenedor |
| `evidence/matriz_no_regresion_6g.csv` | AST y PCM por motor |
| `evidence/contenedores_6g.json` | detalle de validación de contenedores |
| `evidence/motores_6g.json` | comparaciones WAV vs FLAC por modo |
| `evidence/no_regresion_6g.json` | AST + PCM 6F vs 6G |
| `evidence/toctou_6g.json` | sustitución entre validación y lectura |
| `evidence/diffs_6g.md` | diff unificado 6F → 6G |

## Resumen numérico

* Contenedores: **13/13** en el módulo y **13/13** en cada uno de los tres motores.
* Motores: **12/12** combinaciones motor×modo con PCM, geometría, alineación e
  informe idénticos entre WAV y FLAC equivalentes.
* Muestras de entrada WAV vs FLAC: `numpy.array_equal` = **True**.
* TOCTOU: detectado; los tres motores abortan con **0 WAV** y **0 informes**.
* DSP: `probe_file` y `run_experiment` son las únicas definiciones cambiadas;
  PCM idéntico a 6F en los tres motores.

## Advertencias para el auditor

1. MQR mantiene su limitación histórica: máscaras derivadas por downmix mono de
   las guías; no es equivalente al modo L/R independiente de Hardened/EVO.
2. La lectura FLAC desde el mismo inodo usa `/proc/self/fd`; sin `/proc` el
   archivo se rechaza (no se lee por ruta).
3. El MD5 de PCM de STREAMINFO sólo se verifica si está presente; un FLAC sin
   MD5 se registra con `md5_checked = false`.
4. `NOT_EXECUTED`: canciones reales, archivos > 2 GB, FLAC 32 bits, > 2 canales,
   modos/flags no listados (ver §6 del informe de validación).
5. No se declara aptitud de producción ni se elige motor ganador.
