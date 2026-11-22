# 6G.1 — RECTIFICACIÓN DOCUMENTAL del diagnóstico I-1 (commit 88a3ea2)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Fecha:** 22 de noviembre de 2026.
- **Naturaleza:** rectificación documental pura. **Las evidencias históricas originales NO se alteran** (§5 de la instrucción): ningún fichero del commit `88a3ea2` fue modificado, renombrado ni eliminado.
- **Origen de la revisión:** instrucción de Cris (§5), dos puntos señalados en la revisión del diagnóstico I-1.

---

## R-1. Campo `caso` de `evidence/diagnostico_i1_6g1/caso_c4rt_a1.json` dice `C4r`

**Hecho señalado:** el fichero del intento 1 del escenario C4rt (sustitución TARDÍA en flujo real) lleva internamente `caso: 'C4r'`.

**Causa raíz (DOCUMENTED_FACT, verificable en `scripts/diagnostico_i1_6g1.py`):** el arnés genera la etiqueta del caso en `nuevo_caso('C0' if not activar_sustitucion else 'C4r', …)` dentro de `_correr_motor(..., modo='temprano')`: la etiqueta distingue sólo «sin sustitución» vs «con sustitución», sin considerar el parámetro `modo`. El escenario C4rt llamó al mismo `_correr_motor(..., True, modo='tardio')` y guardó su intento como `caso_c4rt_a1.json`, con la etiqueta genérica de sustitución. El consolidado `caso_c4rt.json` (etiqueta correcta C4rt) sí fue generado por la función dedicada `caso_c4rt`.

**Identidad real del fichero (verificable por contenido, sin alterarlo):**
- Nombre `caso_c4rt_a1.json` y referencia explícita en `caso_c4rt.json` → `intentos[0]` con `fichero='caso_c4rt_a1.json'` (intento 1 de 5).
- Eventos del observador en el JSON: `analysis_json_visto` (existe sólo en modo tardío; el modo temprano sustituye sin esperar `analysis.json`) y `sustitucion.delta_ms_desde_deteccion ≈ 534 ms` (característico de la ventana tardía `write_reports`; el temprano medido fue ≈ 0,48 ms).
- El veredicto adjudicado a C4rt (VULNERABILIDAD_REPRODUCIDA_EN_FLUJO_REAL, intento 1/5) se basa en este fichero correctamente identificado.

**Impacto en los resultados adjudicados:** ninguno. Los informes (DIAGNOSTICO_I1_6G1.md §5/§6, matriz CSV, informe al usuario) citan `caso_c4rt_a1.json` como intento 1 de C4rt; la etiqueta interna `C4r` es un defecto de etiquetado del arnés, no una confusión de escenario en los resultados.

**Decisión:** la evidencia histórica se conserva byte a byte. La corrección del etiquetado del arnés se difiere a la implementación futura autorizada (el arnés recibirá el parámetro de etiqueta; se evita tocarlo ahora para no desalinear los manifiestos SHA-256 del diagnóstico ya publicado y auditado).

## R-2. Discrepancia del número de ficheros añadidos del commit 88a3ea2

**Hecho señalado:** el mensaje del commit y parte de la documentación dijeron «13 ficheros nuevos»; la comparación de GitHub muestra otro número.

**Números reales (verificados en ambas fuentes):**

| Fuente | Ficheros | Añadidos | Eliminados |
|---|---|---|---|
| `git show --stat 88a3ea2` (local) | 14 files changed | +2295 | −0 |
| API GitHub (`/commits/88a3ea2`): `files=14`, `stats.additions=2295`, `stats.deletions=0`, `stats.total=2295` | 14 | 2295 | 0 |

Local y GitHub **coinciden**: 14 ficheros añadidos, +2295/−0.

**Explicación del «13» (DOCUMENTED_FACT):** `SHA256SUMS_DIAGNOSTICO_I1.txt` lista **13 ficheros** con hash (informe, arnés y 10 de evidencia, más el propio `MANIFEST_DIAGNOSTICO_I1.json`); el 14.º fichero del commit es el **propio fichero de sumas**, que por diseño estándar no se auto-lista (ni el manifiesto ni el fichero de sumas se auto-referencian; sus identidades quedan ancladas por el historial Git y por esta rectificación). El «13 ficheros nuevos» del mensaje se refería a los ficheros cubiertos por el manifiesto de sumas, pero la redacción era ambigua frente al total del commit.

**Rectificación:** el commit `88a3ea2` añade **14 ficheros nuevos** (+2295/−0), todos documentación y evidencia diagnóstica, 0 cambios de producción: 12 listados en `MANIFEST_DIAGNOSTICO_I1.json`, el propio manifiesto y el fichero de sumas. La integridad verificable del conjunto sigue siendo completa: `grep -v "^#" …SHA256SUMS_DIAGNOSTICO_I1.txt | sha256sum -c -` → **13/13 OK** (re-verificado para esta rectificación).

**Decisión:** sin alteración de las evidencias ni del mensaje histórico del commit; este documento constituye la rectificación independiente.

---

## Registro de verificación

- `git show --stat 88a3ea2` y API GitHub ejecutados el 22-11-2026 (resultados arriba).
- Contenido de `caso_c4rt_a1.json` y `caso_c4rt.json` re-leídos sin modificaciones (`git status` limpio).
- Ningún fichero histórico modificado en el commit que contiene esta rectificación.

*Fin de la rectificación documental.*
