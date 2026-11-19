# Etapa 6F · Auditoría de integridad WAV

Ejecutado: `scripts/auditoria_wav_6f.py` (39 casos construidos byte a byte) y
el bloque WAV de `scripts/validar_reserva_6f.py` (10 casos nuevos). Evidencia:
`evidence/wav_auditoria.json`, `evidence/reserva_wav.json`,
`MATRIZ_WAV_6F.csv`.

## 1. Perfil admitido

| Aceptado | Condición |
|---|---|
| RIFF/WAVE little-endian clásico | tamaño RIFF = tamaño físico − 8, sin bytes extra |
| PCM entero 8/16/24/32 | `block_align = canales·ancho`, `byte_rate = rate·align` |
| IEEE float 32/64 | `fact`, si existe, igual a frames |
| `WAVE_FORMAT_EXTENSIBLE` | `cbSize ≥ 22`, GUID PCM (`01…`) o FLOAT (`03…`), `valid_bits ≤ bits`, máscara coherente |
| `valid_bits` < contenedor | se escala por bits válidos (p. ej. 24 en 32) |
| Chunks adicionales (`LIST`, `fact`, …) | tamaño y padding dentro del RIFF |

| Rechazado | Motivo |
|---|---|
| RF64, RIFX | fuera de perfil |
| Formatos comprimidos (A-law, µ-law, ADPCM…) | sólo PCM/float |
| GUID de subformato distinto de PCM/FLOAT y alias `00000000-…` | no verificable |
| PCM 64 bits, float de 16 bits, profundidades no admitidas | fuera de perfil |
| `data` antes de `fmt`, `fmt` o `data` duplicados, falta de alguno | estructura inválida |
| `data` de tamaño 0 | sin muestras |
| `data` no múltiplo de `block_align` | geometría incoherente |
| Chunk que desborda el RIFF, sin byte de padding, tamaño > 2³¹−1 | límites físicos |
| `RIFF` declarado distinto del tamaño físico, bytes extra al final | truncamiento o relleno |
| `valid_bits > bits`, `cbSize < 22`, máscara con popcount ≠ canales o bits fuera de las 18 posiciones estándar | cabecera incoherente |
| `block_align` o `byte_rate` erróneos | geometría incoherente |
| `fact` distinto de frames | metadato incoherente |
| Muestras float no finitas | datos inválidos |
| Geometría distinta de la que reporta libsndfile, o subtipo distinto del `fmt` | desacuerdo cabecera/decodificador |

## 2. Resultados

* Desarrollo: **39/39** expectativas (13 válidos aceptados, 26 inválidos
  rechazados).
* Reserva: **10/10** (3 válidos, 7 inválidos).
* Todos los rechazos informan el motivo concreto; ninguno se aceptó por el
  simple hecho de que el decodificador pudiera abrir el archivo.
* Los archivos válidos decodifican con la misma forma y finitud que
  libsndfile, y el PCM se obtiene del mismo descriptor validado.

## 3. TOCTOU

`open_validated` abre el archivo una vez, hace `fstat`, valida el contenedor,
hashea los bytes y decodifica el payload **desde ese mismo descriptor**.
Después:

| Escenario | Resultado observado | Alcance |
|---|---|---|
| Reemplazo de la ruta tras abrir | las muestras leídas siguen siendo las del objeto validado; `check_unchanged` detecta identidad y SHA distintos | detecta, no previene |
| Modificación en sitio tras abrir | `check_unchanged` detecta identidad (mtime) y SHA distintos | detecta, no previene |
| Sustitución entre `probe_file` y `analyze_alignment` | `sha256` del sondeo ≠ `sha256` leído → `ERROR` → CLI bloquea | detecta y bloquea |

**No se afirma** que la validación elimine cualquier manipulación concurrente:
no hay bloqueo de archivo, ni copia inmutable, ni autenticación criptográfica del
contenido. Una escritura concurrente *durante* la lectura puede producir un
error de lectura (que se rechaza) o un contenido mixto que sólo se detectaría
por la comparación de SHA al final de la alineación.

## 4. Límites

* No se probaron todos los chunks posibles ni combinaciones de `LIST`/`bext`.
* No se probaron archivos > 2 GB ni RF64 (rechazado por perfil).
* No se validó la coherencia de `channel mask` contra convenciones de orden de
  canales más allá del popcount y el conjunto estándar.
* La decodificación carga el payload completo en memoria; el pico de memoria
  crece con la duración del archivo y no se midió a escala larga.
