# ETAPA 6G.1 — Corrección de lectura segura del Mix

Corrección sobre la entrega 6G (`ee19fe208449249a20e194b09c9452b782c7de70`).
Todo el contenido de esta carpeta es autónomo: no modifica 6G ni etapas
anteriores.

## Qué resuelve

1. El Mix se valida **una vez** y se lee siempre desde **el mismo descriptor**
   (`/proc/self/fd/N`), durante todo el DSP. Ningún componente vuelve a abrirlo
   por su ruta.
2. Si el archivo o la ruta cambian, el motor **aborta**, invalida las salidas de
   audio de esa corrida, registra el motivo en `ABORT_6G1.json` y **no borra**
   archivos preexistentes ni ajenos.
3. La matriz de validación exige PCM real, con hash, para declarar igualdad, y
   distingue `ACCEPTED`, `REJECTED`, `PCM_IDENTICAL`, `PCM_DIFFERENT`,
   `NOT_APPLICABLE` y `NOT_EXECUTED`.
4. El DSP no cambia: se verificó por AST, por huella de literales/llamadas y por
   PCM idéntico byte a byte frente a 6G en WAV y FLAC.

## Contenido

```
ETAPA_6G1_CORRECCION_LECTURA_SEGURA/
├── motores/            copias 6G.1 de los tres motores + módulo lectura_segura_6g1.py
├── scripts/            generación de fixtures, pruebas 1–10, consolidación
├── fixtures/           fixtures sintéticos (WAV/FLAC equivalentes y sustitutos)
├── evidence/           CSV y JSON de las pruebas
├── INFORME_IMPLEMENTACION_6G1.md
├── INFORME_VALIDACION_6G1.md
├── NO_REGRESION_DSP_6G1.md
├── INDICE_PARA_AUDITORIA_6G1.md
├── MANIFEST_6G1.json
└── SHA256SUMS.txt
```

## Requisitos

Python 3.11 con numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1 (libsndfile 1.2.2).
Los motores leen el Mix desde `/proc/self/fd/`, por lo que el entorno debe
exponer `/proc` (Linux).

## Reproducir

```bash
cd ETAPA_6G1_CORRECCION_LECTURA_SEGURA
python -B scripts/preparar_fixtures_6g1.py
python -B scripts/validar_contenedores_6g1.py
python -B scripts/sustituciones_6g1.py
python -B scripts/no_regresion_dsp_6g1.py
python -B scripts/consolidar_6g1.py
cd .. && sha256sum -c ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS.txt
```

Los scripts escriben sus salidas en `/tmp/f6g1/…`; sólo `evidence/`,
`fixtures/`, `SHA256SUMS.txt` y `MANIFEST_6G1.json` se actualizan dentro del
repositorio.

## Leer por dónde empezar

1. `INFORME_IMPLEMENTACION_6G1.md` — qué se cambió y por qué.
2. `INFORME_VALIDACION_6G1.md` — pruebas 1–10, veredictos y casos no ejecutados.
3. `NO_REGRESION_DSP_6G1.md` — por qué el DSP es el mismo.
4. `INDICE_PARA_AUDITORIA_6G1.md` — mapa de archivos y comandos de auditoría.

## Estado

* Pruebas ejecutadas: 1–10 con fixtures sintéticos.
* Canciones reales: ninguna.
* Integración con el piloto: ninguna.
* Cambios de parámetros por defecto: ninguno.
* `Hardened` en `analysis_only` no se ejecutó: defecto preexistente de 6F/6G,
  documentado y marcado `NOT_EXECUTED`.
