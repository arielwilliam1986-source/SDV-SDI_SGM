# CORRECCIÓN FINAL DE LA RECTIFICACIÓN — INFORME PILOTO ELIS / TRISTANIA

- **Fecha**: 2026-11-21
- **Rama**: `arena/441a4bf8-sdv-sdi-sgm` · **Base**: `b309c7ff366389ac9d7b1eca584fb8e7cc7152b6` · **Documento corregido**: `INFORME_RECTIFICACION_PILOTO_ELIS_TRISTANIA.md`
- **Modalidad**: solo documentación (dos ediciones puntuales del informe de rectificación; cero código, motores, DSP, AudioInput, S5, 6G.1 o material musical tocados).
- **Origen**: auditoría de la rectificación (Cris, contenido principal SATISFACTORIO) con tres ajustes puntuales, comunicados por el usuario como instrucción.
- **Estado**: última corrección documental de esta rectificación, salvo discrepancia material nueva. Pendiente de decisión de Will.

---

## 1. Cifras de S5 corregidas (§3.1 del informe de rectificación)

**Antes** (incorrecto): «26 WAV de entrada, 116 corridas completadas + 2 del aborto (144 WAV conservados), 59 máscaras en NPY» — mezclaba archivos, corridas e intentos.

**Después** (corregido):
- **59 intentos totales; 58 corridas completas; 1 corrida abortada** (MQR S7).
- WAV conservados: **26 de entrada + 116 de pares completos + 2 parciales del aborto** (144 en total).
- **59 máscaras vocales aplicadas** (una por corrida, incluida la abortada).

**Fuente verificada verbatim** — `INFORME_AUDITORIA_S5.md` (rama `arena/89d5c189-sdv-sdi-sgm`, `S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/`): «**58 completas de 59 intentos**. A: 16/16; B: 16/16; C: 19/19; D: 7/8», «26 entradas, 116 WAV de pares completos, 2 del aborto», «**59 máscaras vocales aplicadas** … una por corrida, incluida la abortada».

## 2. Salvedad de limpieza de 6G.1 incorporada (§2.2 del informe de rectificación)

**Antes**: «y **no borra** archivos preexistentes ni ajenos» — formulación absoluta sin la salvedad documentada.

**Después**: se conserva el resultado de la prueba 7 (6/6 ACCEPTED) pero se incorpora la **salvedad documentada**: `abortar_6g1` borra sólo nombres que el motor escribe en esa corrida; **un archivo ajeno que apareciera con exactamente el mismo nombre que una salida reconocida** (p. ej. `SDV.wav`) dentro del directorio de una corrida **sería tratado como salida propia**. El directorio de corrida lo crea el motor **vacío** en cada ejecución, pero esta condición constituye una **limitación del mecanismo**.

**Fuente verificada verbatim** — `INFORME_IMPLEMENTACION_6G1.md` («Limpieza del aborto», líneas 196–199): «`abortar_6g1` borra sólo nombres que el motor escribe en esa corrida. Un archivo ajeno con exactamente el mismo nombre (`SDV.wav`) dentro del directorio de una corrida sería tratado como salida propia; el directorio de corrida lo crea el motor, vacío, en cada ejecución». **No se modificó código ni se reabrió 6G.1.**

## 3. Identidad Git verificada

| Verificación pedida | Resultado |
|---|---|
| SHA completo del HEAD remoto actual | `b309c7ff366389ac9d7b1eca584fb8e7cc7152b6` — local = remoto, ambos en este SHA |
| ¿El commit de rectificación pertenece a la rama? | **SÍ** — `git merge-base --is-ancestor` confirma que `b309c7f` es ancestro de `origin/arena/441a4bf8-sdv-sdi-sgm`; fecha 2026-11-21 19:08:57 UTC |
| ¿Los dos cambios documentales están incluidos? | **SÍ** — el commit contiene exactamente 2 ficheros, +191/−0: `INFORME_RECTIFICACION_PILOTO_ELIS_TRISTANIA.md` (nuevo, 189 líneas) + `INFORME_PREPARACION_PILOTO_ELIS_TRISTANIA.md` (+2 líneas) |
| ¿El informe original conserva su contenido salvo la nota? | **SÍ** — `git diff --numstat 152957a b309c7f` sobre ese fichero = **2 insertions, 0 deletions**: únicamente la nota de cabecera de rectificación prevista |

**Explicación de la discrepancia del SHA**: el SHA citado en la instrucción de auditoría (`b309c7ff366389ac9d7b1eca584fb8e7cc715b6`) tiene **39 caracteres** — le falta un «2» en el segmento final (`...cc715b6` en lugar de `...cc7152b6`). Un SHA de 39 caracteres no es un nombre de objeto válido y la consulta independiente de GitHub no puede recuperarlo; el documento, en cambio, sí se leyó desde la rama porque la rama contiene el commit real. **El SHA comunicado en los entregables de Arena era correcto (40 caracteres, verificado local = remoto en su momento y re-verificado ahora)**; la discrepancia es un error de transcripción en la instrucción recibida, no en los entregables. No hubo corrección que aplicar sobre el SHA en los documentos: los entregables nunca contuvieron el SHA de 39 caracteres.

---

## Enlaces (URLs completas y visibles)

Documento actualizado (este commit):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/INFORME_RECTIFICACION_PILOTO_ELIS_TRISTANIA.md

Informe original con nota de rectificación:
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/herramientas/diagnostico_audio/INFORME_PREPARACION_PILOTO_ELIS_TRISTANIA.md

Commit de la rectificación original (verificado):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b309c7ff366389ac9d7b1eca584fb8e7cc7152b6

Fuentes citadas (rama `arena/89d5c189-sdv-sdi-sgm`, leída en solo lectura):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/89d5c189-sdv-sdi-sgm/S5_STEREO_VALIDATION/AUDIT_INDEPENDIENTE/INFORME_AUDITORIA_S5.md
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/89d5c189-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_IMPLEMENTACION_6G1.md

---

**Límites respetados**: solo documentación; no se modificaron motores, DSP, AudioInput ni pruebas; no se ejecutó S5 ni 6G.1; no se abrió ni procesó Elis o Tristania; no se tocó `main`, no se fusionó ni modificó rama ajena; no se inició otra ronda de correcciones de AudioInput.
