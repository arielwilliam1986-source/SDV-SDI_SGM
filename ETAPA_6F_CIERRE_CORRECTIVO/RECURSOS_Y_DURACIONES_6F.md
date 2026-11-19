# Etapa 6F · Recursos, tiempos y errores

Todas las mediciones son del entorno **Arena** (no de Termux ARM64). Se
obtuvieron con el arnés en subprocess y `resource.getrusage`; no se impusieron
límites de RAM teóricos.

## 1. Entorno

| Elemento | Valor |
|---|---|
| SO / arquitectura | Linux x86_64 (contenedor Arena) |
| CPU | 2 vCPU; hilos OpenMP/OpenBLAS/MKL fijados a 1 |
| Memoria del sistema | 3 939 MB |
| Python | 3.11.2 (`/tmp/sdv6f-env`, `-B`, sin `__pycache__`) |
| numpy / scipy / soundfile / cffi / pycparser | 1.26.4 / 1.13.1 / 0.13.1 / 2.1.1 / 3.12 |
| libsndfile | 1.2.2 |
| Fecha de ejecución | 2026-11-19 |

## 2. Duración y pico de memoria

| Prueba | Duración | RSS del arnés | RSS de hijos |
|---|---|---|---|
| Atribución desarrollo (93 filas) | 14,5 s | 153 544 KiB | — |
| Atribución reserva (84 filas) | 37,1 s | 144 464 KiB | — |
| CLI desarrollo (57 filas) | 41,0 s | 57 472 KiB | 139 980 KiB |
| CLI reserva (30 filas) | incluida en reserva | — | — |
| Integridad WAV (49 casos) | 0,21 s | 90 600 KiB | — |
| MQR S7 (13 corridas) | 12,9 s | 51 740 KiB | 250 044 KiB |
| No regresión DSP (24 comparaciones) | 66,8 s | 86 876 KiB | 253 372 KiB |

## 3. Tamaños de archivo

| Estímulo | Frames | Canales | Formato | Tamaño |
|---|---|---|---|---|
| Caso de 1 s | 44 100 | 2 | float32 WAV | ≈353 KiB |
| Caso de 2 s (reserva) | 88 200 | 2 | float32 WAV | ≈706 KiB |
| Caso de 4 s | 176 400 | 2 | float32 WAV | ≈1,4 MiB |
| S7 | 176 400 | 2 | float32 WAV | ≈1,4 MiB |
| WAV válidos de auditoría | 16–1 024 frames | 1–2 | PCM/float | 44 B–4,1 KiB |

Los WAV de trabajo se generan en directorios temporales; el repositorio sólo
contiene código y evidencia JSON/CSV.

## 4. Errores y excepciones observados

| Dónde | Error | Tratamiento |
|---|---|---|
| 6C, MQR, S7 | `ZeroDivisionError` en `crest_factor_sdv` | reproducido, no corregido en 6C (protegido) |
| 6F, S7 sin permiso | bloqueo por `AMBIGUOUS` | comportamiento esperado |
| Arneses | `AttributeError` con `Cronometro.seconds` antes de salir del `with` | corregido en el arnés |
| Arneses | `ModuleNotFoundError: medidas` al importar el generador de S5 | fixture S7 reescrito autónomo |
| Arneses | `StopIteration` al elegir casos inexistentes en CLI/DSP | corregido en el arnés |
| WAV inválidos | `WaveError` con motivo concreto | esperado |

Ninguna excepción no controlada en los motores 6F durante las 138 corridas de
CLI ni en las 177 filas de atribución.

## 5. Extrapolación

No se extrapolan tiempos ni memoria a Termux ARM64. Los archivos largos
(audio completo) cargan el payload en memoria y no se midieron; el coste de
`correlate` es O(n log n) por ventana y por canal.
