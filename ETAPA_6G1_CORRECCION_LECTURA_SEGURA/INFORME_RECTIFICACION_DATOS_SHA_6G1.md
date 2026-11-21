# INFORME DE RECTIFICACIÓN DOCUMENTAL — SHA-256 DE `lectura_segura_6g1.py` (E-R2)

**Implementador**: Arena.ai · **Solicitado por**: Cris (tras auditoría favorable de E-R2)
**Fecha**: 2026-11-21 · **Naturaleza**: exclusivamente trazabilidad documental
**Base**: `03c6a800a197100e82455ca58d49b12c7e625d78` (padre del commit de esta entrega)
**Archivo auditado**: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py`
**Sin cambios de código, pruebas, motores ni entregas anteriores. Sin repetir baterías.**

---

## 1. Los dos SHA-256 solicitados (valores completos y verificados)

| Estado | Commit | SHA-256 real (completo) |
|---|---|---|
| **Tras E-R2** | `03c6a800a197100e82455ca58d49b12c7e625d78` | `271131772f696bd96162ed54dc0ce72da7010651692f43162fe6182a61209957` |
| **Base previa** | `97d1bd0bd3c430470fa6fa1058fdbcbb61c778f2` | `20bb996bf323531e818173f7c8044de9f148707eef68c6d61842dacbc734f07a` |

## 2. Contraste con el manifiesto y veredicto

- `SHA256SUMS_E_R2.txt` (publicado en `03c6a80`) registra para este archivo exactamente `271131772f…209957` con `# previo: 20bb996bf3…f07a`: **el manifiesto publicado es CORRECTO** en ambos valores.
- Re-verificación **al nivel del commit** (hash sobre el blob exacto de `03c6a80`, no sobre el árbol de trabajo): **4/4 OK** para las cuatro entradas del manifiesto E-R2 (módulo, batería, JSON y CSV de evidencia).
- El árbol de trabajo en HEAD (`03c6a80`) coincide con el blob (`271131772f…`).
- **Dato incorrecto identificado**: los prefijos abreviados «47377601…» (nuevo) y «6b8b3f2b…» (previo) citados en el **resumen de ejecución por chat** de E-R2 no corresponden a ningún estado real del archivo; fueron un error de abreviación al redactar ese resumen. Ningún artefacto publicado (manifiesto, informe E-R2, evidencia, commits) contiene esos valores (verificado por búsqueda en toda la carpeta 6G.1). La corrección documental se materializa en este informe; los SHA-256 de referencia son los del manifiesto y los de la tabla §1.

## 3. Cadena completa del archivo (todos los estados verificados)

Cada valor obtenido con `git show <commit>:<ruta> | sha256sum`; contraste con el manifiesto publicado en el mismo commit:

| Entrega | Commit | SHA-256 del archivo | Manifiesto | Coherente |
|---|---|---|---|---|
| 6G.1 auditado (base técnica) | `015e2f8e2b215c1d4dc5b9360988b42063e28533` | `a70a4782d953bb5e7bb2d1cb9542930e382671459935a979cbd88bf97671f1db` | `SHA256SUMS_CORRECCION.txt` (comentario «auditado») | Sí |
| Corrección A–D | `64b3c2d5052355cdcba411149bf9b8f8da1e3fdd` | `969cb8cb986399d52d07baafb397c0cfc83dc6cffb37dd8baece04d7b26e9ba9` | `SHA256SUMS_CORRECCION.txt` (nuevo) | Sí |
| E–G | `2248e2e21e44b279d57f9d0163f3f11b474a75e2` | `4bb9e5b78cd405016ddcb2231ea9f219ce07b59d6311fe92f6dbfe6181a26722` | `SHA256SUMS_SEGURIDAD.txt` (nuevo) | Sí |
| E-R1/G-R1 | `97d1bd0bd3c430470fa6fa1058fdbcbb61c778f2` | `20bb996bf323531e818173f7c8044de9f148707eef68c6d61842dacbc734f07a` | `SHA256SUMS_ER1_GR1.txt` (nuevo) | Sí |
| E-R2 | `03c6a800a197100e82455ca58d49b12c7e625d78` | `271131772f696bd96162ed54dc0ce72da7010651692f43162fe6182a61209957` | `SHA256SUMS_E_R2.txt` (nuevo) | Sí |

Cada «nuevo» de una entrega coincide con el «previo» de la siguiente: la cadena es continua y sin saltos.

**Otros datos documentales de resúmenes por chat corregidos en esta oportunidad** (mismo archivo; los manifiestos publicados siempre fueron correctos):
- Resumen E–G: «nuevo 96d1d8c5…» → correcto es `4bb9e5b78c…` («previo 969cb8cb…» era correcto).
- Resumen E-R1/G-R1: «nuevo 6b8b3f2b… (previo 96d1d8c5…)» → correctos son `20bb996bf3…` (nuevo) y `4bb9e5b78c…` (previo).
- Resumen A–D: «969cb8cb… (auditado a70a4782…)» → era correcto.

## 4. Comprobación realizada (método)

1. `git show <commit>:<ruta> | sha256sum` sobre cada commit de la cadena (blob exacto, no árbol de trabajo).
2. Contraste línea a línea contra cada manifiesto publicado en su commit correspondiente (`git show <commit>:SHA256SUMS_*.txt`).
3. Re-verificación blob a blob del manifiesto E-R2 en `03c6a80`: 4/4 OK.
4. Búsqueda en toda la carpeta 6G.1 de los prefijos erróneos: ausentes en todos los artefactos publicados.
5. Nota de entorno: tras la restauración del sandbox el objeto del commit auditado `015e2f8` no estaba en el almacén local; se recuperó con `git fetch origin arena/89d5c189-sdv-sdi-sgm` (solo lectura; la rama de referencia no fue modificada).

## 5. Confirmaciones

- **No se modificó** código, pruebas, motores, evidencia ni entregas anteriores; este commit añade únicamente este informe. Sin repetir baterías (34/26/17/12) ni abrir ronda técnica.
- **Padre del commit de esta entrega**: `03c6a800a197100e82455ca58d49b12c7e625d78` (verificado con `git rev-parse HEAD^`); HEAD remoto verificado igual al local tras el push.
- **No se declara 6G.1 cerrada** (la aceptación funcional de E-R2 por Cris no cierra la etapa; aprobación final: Cris).

## 6. Enlaces (URLs completas)

Informe de rectificación (este documento):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_RECTIFICACION_DATOS_SHA_6G1.md

Manifiesto E-R2 (correcto, en el commit 03c6a80):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_E_R2.txt

Archivo auditado en su estado actual (03c6a80):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/03c6a800a197100e82455ca58d49b12c7e625d78/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/motores/lectura_segura_6g1.py

Informe E-R2 (antecedente, sin cambios):
https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/arena/441a4bf8-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/INFORME_E_R2_6G1.md
