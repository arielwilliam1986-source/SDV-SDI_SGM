# ÍNDICE DOCUMENTAL — PAQUETE R6-R4

**Fecha:** 2026-11-25 (UTC).
**Naturaleza:** documento de navegación y trazabilidad. **Solo lectura** respecto de los cuatro documentos que indexa.
**Estado:** archivo nuevo, **sin commit**.
**Ubicación:** raíz del repositorio.

---

## 0. Advertencia de lectura — leer antes de usar cualquier documento

> **Los cuatro documentos del paquete R6-R4 deben leerse conjuntamente.**
>
> El documento principal **no contiene internamente ninguna señal** de que fue corregido posteriormente. Un lector que abra únicamente `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` encontrará en él **siete formulaciones que ya no son válidas** en los términos en que están escritas (§4 de este índice).
>
> Este índice es el único mecanismo que declara esas correcciones. **No modifica los documentos originales**; no puede hacerlo (§9).

**Regla de lectura:**

1. Leer el **principal** para el análisis caso por caso de los nueve `UNKNOWN`.
2. Consultar la **tabla de correcciones** (§4) antes de citar cualquier cifra, cualquier referencia al *probe* T1/T2, cualquier valor de `euid` o cualquier afirmación sobre la conservación de los JSON.
3. Aplicar la **tabla de precedencia** (§5) cuando dos documentos traten la misma materia con formulaciones distintas.
4. Verificar los **veredictos invariantes** (§6) antes de reutilizar cualquier resultado.

---

## 1. Propósito y alcance

Este índice existe para resolver un problema concreto detectado en la auditoría documental previa: **la cadena de cuatro documentos se corrige a sí misma, pero el punto de entrada no lo advierte.**

| Problema | Consecuencia |
|---|---|
| El principal se escribió antes de las tres adendas | Contiene cifras y formulaciones ya superadas |
| Las adendas sí se autodeclaran correctoras | Un lector que llega por el principal no lo sabe |
| Los nombres de archivo son alfabéticamente engañosos | Ordenar por nombre **no** reproduce el orden de precedencia |

**Alcance incluido:** identificar los cuatro documentos, su orden, sus correcciones recíprocas, sus puntos de prevalencia y el estado de la cadena.

**Alcance excluido expresamente:** modificar, renombrar, reformatear o anotar cualquiera de los cuatro documentos; alterar veredictos; ejecutar pruebas; crear el manifiesto definitivo de evidencias; crear commits o ramas.

---

## 2. Identificación de los cuatro documentos

Los cuatro archivos existen en la raíz del repositorio, **no versionados**, y sus SHA-256 fueron **recalculados en Arena** y coinciden con los previamente comunicados.

| Orden | Rol | Archivo | Líneas | Bytes | SHA-256 | Fecha declarada |
|---|---|---|---|---|---|---|
| 1 | **Principal** | `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` | 428 | 36 103 | `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` | 2026-11-25 |
| 2 | Adenda 1 — Rectificación | `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` | 405 | 27 541 | `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f` | 2026-11-25 |
| 3 | Adenda 2 — Complementaria | `ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md` | 343 | 18 730 | `0a61e9e7533acc114b5631d98e15be36c19d6678b6523a419c4bea1abcf19180` | 2026-11-25 |
| 4 | Adenda 3 — Final | `ADENDA_FINAL_PRECISION_DOCUMENTAL_R6-R4.md` | 326 | 19 596 | `8b8dd2700c495a6f7e56aa810ed34378cc2b7f0ab6ea5a4193d70f5c83f1da2e` | 2026-11-25 |

**Total del paquete:** 1 502 líneas · 101 970 bytes.

### 2.1 Documento principal

`AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md`

Contiene el análisis completo de los nueve casos `UNKNOWN` de D18-R2-R6-R4: criterios leídos del código (§3–§6), verificación por AST de ausencia de cierre forzado (§3.2), tabla consolidada (§7), recomendaciones (§8) y confirmaciones (§9). **Es la base sustantiva del paquete y sigue siendo válido en todo su análisis caso por caso.** Sus defectos son de resumen y de ámbito, no de análisis (§4).

### 2.2 Adenda 1 — Rectificación

`ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md`

Corrige y precisa cuatro puntos del principal (§2, §3, §4, §5) y aporta la **tabla consolidada corregida** (§6), que es la lista autorizada de categorías de los nueve casos. Es el documento que **fija la distribución 6/1/1/1/0**.

### 2.3 Adenda 2 — Complementaria

`ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md`

Corrige el estado de conservación de las evidencias: los JSON **existen** localmente y en el respaldo, pero **no están versionados**. Corrige expresamente tres pasajes de la Rectificación (§6.1). Contiene, a su vez, **una formulación que la Adenda Final posteriormente corrige** (§2.2, «segundo soporte físico distinto»).

### 2.4 Adenda 3 — Final

`ADENDA_FINAL_PRECISION_DOCUMENTAL_R6-R4.md`

Corrige dos matices: la **naturaleza del respaldo** (§2) y la **trazabilidad del mecanismo externo** de escritura de evidencias (§3). Es la **última de la cadena** y **no ha sido corregida por ningún documento posterior**.

---

## 3. Orden cronológico y de precedencia

### 3.1 El orden no se deduce de la fecha

Los cuatro documentos declaran **la misma fecha**: `2026-11-25 (UTC)`. Por tanto, **la fecha no permite ordenarlos** y no debe usarse para inferir precedencia.

### 3.2 El orden se deduce de las referencias cruzadas verificadas

El orden es determinable por evidencia interna de los propios documentos:

| Documento | Referencia cruzada que lo sitúa | Estado |
|---|---|---|
| Principal | No referencia a ninguna adenda | — |
| Rectificación | Declara corregir cuatro puntos «detectados en la revisión de `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md`» | Verificado |
| Complementaria | Declara «**Documento corregido:** `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` (sha256 `72141b76…6d8f`)» | Verificado |
| Final | Declara qué documentos **no** modifica, citando los **tres SHA-256 anteriores** | Verificado |

**Conclusión:** la cadena es `Principal → Rectificación → Complementaria → Final`. La dirección se acredita internamente, no por convención de nombres.

### 3.3 Advertencia sobre el orden alfabético

Ordenar los archivos alfabéticamente produce:

```
ADENDA_COMPLEMENTARIA_...   (adenda 2)
ADENDA_FINAL_...            (adenda 3)
ADENDA_RECTIFICACION_...    (adenda 1)   ← fuera de orden
AUDITORIA_...               (principal)  ← queda el último
```

**El orden alfabético es incorrecto en dos posiciones.** La Rectificación aparece después de la Final, y el principal aparece al final cuando en realidad es el punto de partida. **No usar el orden alfabético para determinar precedencia.**

---

## 4. Afirmaciones corregidas — tabla de correcciones

Siete formulaciones de los documentos 1, 2 y 3 han sido corregidas o precisadas por un documento posterior del paquete. **Todas siguen presentes literalmente en el archivo de origen**, porque ninguno de los cuatro documentos ha sido modificado.

| # | Afirmación tal como figura en el archivo | Ubicación exacta | Corregida / precisada por | Formulación vigente |
|---|---|---|---|---|
| **C-1** | «**Distribución:** 5 `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` · 1 · 1 · 1 · 0» | Principal §7, línea de resumen bajo la tabla | **Rectificación §2** (2.1–2.3) | **6** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` (R2-B6, R2-D1, R2-D2, R2-C2, R2-C3, R1-A3) · 1 · 1 · 1 · 0. Defecto **aritmético y localizado**; la tabla de nueve filas del principal **siempre fue correcta** |
| **C-2** | «La evidencia auxiliar "Probe T1/T2 independiente: 3/3 PASS" **no existe** en el repositorio» — legible como «nunca se ejecutó» | Principal §2 | **Rectificación §3** (3.1–3.4) | **Hubo una ejecución real comunicada** en Android/Termux con 3/3 PASS; **no dejó artefacto persistente**; **no es reproducible de forma independiente**. Es **antecedente auxiliar**, no prueba primaria, y no adjudica nada |
| **C-3** | «En este entorno auditado `euid = 1001`», sin delimitar el ámbito respecto de Android | Principal §4.2 (R2-C3) | **Rectificación §4** (4.3–4.5) | `1001` es el `euid` del **sandbox Linux Arena** (10 documentos versionados + medición directa). **El `euid` de Android/Termux no está acreditado**; `10070` es un valor **comunicado, no acreditado** y **no reemplaza** a `1001` |
| **C-4** | Resultados de R6-R3 presentados junto a R6-R4 sin separación explícita de revisión | Principal §9.2 y contexto general | **Rectificación §5** (5.1–5.7) | El `FAIL` de `R2-C9` pertenece **exclusivamente a R6-R3 en Android/Termux**. R6-R4 Linux solo acredita una **selección aislada de 4 subpruebas** (4/0/0), **no comparable** con el 30/0/9 |
| **C-5** | «**sin artefacto persistente**» aplicado a las tres repeticiones R6-R4 | Rectificación §3.2 (nivel 2), §5.4 (nivel 2) y §8 (tabla de limitaciones) | **Complementaria §6** (6.1–6.2) | «**Los artefactos existen localmente y en el respaldo, pero no están versionados en el repositorio.**» Correcto para el *probe* T1/T2; **incorrecto** para las tres repeticiones R6-R4 |
| **C-6** | «La copia en esa ubicación constituye un **segundo soporte físico distinto**, lo que da valor real al respaldo» | Complementaria §2.2 | **Final §2** (2.1–2.4) | «Los tres JSON constan como conservados en el directorio privado de Termux y con copias en una segunda ubicación de almacenamiento del dispositivo Android. **La independencia física de ambos soportes no está acreditada.**» |
| **C-7** | «…requirió alguna acción externa al arnés (copia, movimiento o ejecución con un `cwd`/wrapper distinto), que **no está documentada en el repositorio**» | Complementaria §6.3 | **Final §3** (3.3, 3.6) | El **patrón técnico** (lanzador externo que sustituye atributos del módulo tras cargarlo) **sí está documentado** y en uso en al menos **cuatro lanzadores** del repositorio. Lo **no acreditado** es la **instancia concreta** `module.EVIDENCE_DIR = …` (0 coincidencias en árbol e historial) y su uso en **esas tres ejecuciones** |

### 4.1 Nota crítica sobre C-7

La corrección C-7 **no es una precisión menor**. La formulación original de la Complementaria permitía concluir que la ubicación final de los JSON carecía de explicación técnica conocida. **Esa conclusión es incorrecta** y la Adenda Final la desmonta en cuatro niveles explícitos (§3.4): el nivel **A** (el arnés escribe en `/tmp`) está acreditado; el nivel **B** (existe mecanismo externo documentado) está acreditado **como patrón**; el nivel **C** (una ruta externa es técnicamente posible) está acreditado; **solo el nivel D** (que ese lanzador concreto se usara en las tres repeticiones) **no está acreditado**.

**No debe citarse la Complementaria §6.3 sin citar la Final §3.6.**

---

## 5. Puntos en los que prevalece una adenda posterior

Cuando dos documentos del paquete tratan la misma materia con formulaciones distintas, **prevalece el documento de número mayor** en los puntos que ese documento trata expresamente. En los puntos que la adenda posterior **no** trata, prevalece el documento anterior que los trate.

| Materia | Prevalece | Dispositivo concreto |
|---|---|---|
| **Distribución de categorías de los nueve casos** | **Rectificación** §2.3 + tabla §6 | 6 · 1 · 1 · 1 · 0. Sustituye la línea de resumen del principal (`C-1`) |
| **Análisis caso por caso** (criterios, causas, código) | **Principal** §3–§6 | No corregido en lo sustantivo por ninguna adenda |
| **Estado probatorio del *probe* T1/T2** | **Rectificación** §3 | Tres niveles: ejecución comunicada / sin artefacto persistente / no reproducible (`C-2`) |
| **Atribución del `euid`** | **Rectificación** §4 | `1001` = Linux Arena; Android/Termux no acreditado (`C-3`) |
| **Atribución del `FAIL` de `R2-C9`** | **Rectificación** §5.5 | Pertenece **exclusivamente a R6-R3** (`C-4`) |
| **Conservación de los tres JSON** | **Complementaria** §6.2, **corregida por Final** §2 | Existen localmente y en el respaldo; no versionados (`C-5`) |
| **Naturaleza del respaldo e independencia física** | **Final** §2 | Independencia física **NO acreditada** (`C-6`) |
| **Trazabilidad del mecanismo externo de escritura** | **Final** §3 | Patrón acreditado; instancia concreta no acreditada (`C-7`) |
| **Cifras de R6-R4 en Linux** | **Rectificación** §5.6 | 4/0/0 es **selección aislada**, no batería completa; no comparable con 30/0/9 |
| **Veredictos** | **Ningún documento los modifica** | Ver §6 |

### 5.1 Regla de resolución de conflictos

1. Identificar la materia exacta del conflicto.
2. Localizarla en esta tabla (§5).
3. Si la materia **no** aparece en la tabla: **no hay conflicto resuelto**. Se trata de una **discrepancia abierta** y debe declararse como tal, no resolverse por preferencia de documento.

---

## 6. Veredictos invariantes — estado que ningún documento del paquete altera

Los cuatro documentos **no modifican ningún veredicto**. Este índice lo declara expresamente y lo deja verificado:

| Elemento | Estado | Fuente que lo declara |
|---|---|---|
| Los **nueve `UNKNOWN`** de D18-R2 (R2-B6, R2-D1, R2-D2, R2-C2, R2-C3, R2-C5, R1-A3, R1-A4, R1-B2) | **Siguen siendo `UNKNOWN`** | Rectificación §7 · Complementaria §7.2 · Final §6 |
| **`D18`** | **`FAIL`** — hallazgo histórico `C5` (`SIGSEGV`, 3/3) | Rectificación §5.7 · Principal §9.2 |
| **`C5`** | **`FAIL` histórico, intacto** | Rectificación §5.7 |
| **`D18-R2` global en Linux** | **`UNKNOWN`** (30/0/9, R6-R3) | Rectificación §5.6–§5.7 |
| **`D18-R2` global en Android/Termux** | **`UNKNOWN`** (30/0/9 comunicado, 3 repeticiones) | Complementaria §7.1 · Final §5.4 |
| **`FAIL` de `R2-C9`** | Pertenece a **R6-R3 Android/Termux**, no a R6-R4 | Rectificación §5.5 |

> **Declaración expresa:** **ninguno de los nueve `UNKNOWN` ha sido convertido a `PASS`**, ni por los documentos del paquete ni por este índice. Las categorías de la auditoría (`ADJUDICABLE_CON_EVIDENCIA_EXISTENTE`, `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE`, `LIMITACION_DEL_ENTORNO_DOCUMENTADA`, `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA`) describen **el grado de explicación documental alcanzado**, no el veredicto. Seis casos son `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` y **los seis siguen siendo `UNKNOWN`**.

---

## 7. Estado de la cadena documental: CERRADA

> **La cadena documental R6-R4 se declara CERRADA en la Adenda Final.**
>
> No se prevé, y no se autoriza en este índice, una cuarta adenda.

### 7.1 Justificación del cierre

| Condición | Estado |
|---|---|
| Todas las correcciones detectadas han sido incorporadas en un documento de la cadena | Sí — siete correcciones (`C-1`…`C-7`) |
| La última adenda no contiene formulaciones corregidas por otro documento | Sí — la Final no ha sido corregida |
| Los hashes de los cuatro documentos están fijados y son reproducibles | Sí — recalculados en Arena, coincidentes |
| Ningún documento requiere modificación para ser comprensible | Sí, **a condición de leer este índice** |

### 7.2 Que la cadena esté cerrada NO significa que el asunto esté resuelto

Debe distinguirse con precisión:

| Cuestión | Estado |
|---|---|
| **Cadena documental** (auditoría + correcciones) | **CERRADA** |
| **Adjudicación de los nueve `UNKNOWN`** | **NO CERRADA** — los nueve siguen `UNKNOWN`; requiere decisión del responsable |
| **Validación Android/Termux de R6-R4** | **PENDIENTE** — el informe en HEAD (§13.5) la sigue declarando pendiente; las tres repeticiones constan como **comunicadas**, no certificadas |
| **D18 / D18-R2 global** | **NO RESUELTO** — `D18` sigue `FAIL`; `D18-R2` global sigue `UNKNOWN` |
| **Conservación de las evidencias** | **ABIERTA** — las tres vías de la Complementaria §12 siguen sin decidir |
| **PR #3 y PR #4** | **ABIERTOS, sin fusionar** — decisión exclusiva del responsable |

**Una cuarta adenda estaría justificada solo si apareciera un defecto nuevo en el contenido de los cuatro documentos.** Ninguno se ha detectado. Cualquier cuestión posterior pertenece a **fases nuevas**, no a esta cadena.

---

## 8. Advertencia operativa del entorno — procedimiento Git

Esta advertencia se incorpora al procedimiento operativo del proyecto y **no depende de R6-R4**. Se deriva de un patrón observado de forma repetida en el entorno Arena: el sandbox puede reprovisionarse y presentar un clon nuevo con el puntero en un commit anterior, **sin que ello signifique que el repositorio haya cambiado ni que se haya perdido trabajo**.

### 8.1 Regla obligatoria — comprobación previa

**Antes de cualquier recuperación de estado Git**, comprobar y registrar, en este orden:

| # | Comprobación | Comando |
|---|---|---|
| 1 | Rama actual | `git branch --show-current` |
| 2 | `HEAD` y su correspondencia con el commit esperado | `git rev-parse HEAD` |
| 3 | Estado del árbol de trabajo | `git status --porcelain` |
| 4 | Archivos no versionados presentes | incluidos en la salida anterior (`??`) |
| 5 | Historial del puntero | `git reflog` — una secuencia `clone:` + `checkout:` indica reprovisión del entorno, no cambio del repositorio |

**Registrar el resultado de las cinco comprobaciones antes de tocar nada.**

### 8.2 `git reset --hard` — restricción

> **No ejecutar `git reset --hard` como método rutinario de alineación.**
>
> Si se considera **imprescindible**:
>
> 1. **Evaluación previa del riesgo** documentada: qué archivos no versionados existen, cuáles quedarían afectados y qué se perdería si el árbol no coincidiera con el destino.
> 2. **Verificación previa del contenido**: `git diff --stat <commit_destino> -- .` debe devolver **salida vacía**. Sin salida, el árbol ya coincide y el `reset` solo mueve el puntero; con salida, **el `reset` destruiría diferencias** y está prohibido.
> 3. **Autorización expresa.**

### 8.3 Archivos no versionados — prohibición y alcance real de la protección

> **No eliminar ni sobrescribir archivos no versionados.**

**Corrección de una formulación anterior de este apartado.** Una versión previa de §8.3 afirmaba que «un `reset --hard` no elimina archivos `??`». Esa afirmación era **demasiado categórica** y **no describe con exactitud** el comportamiento de `git reset --hard`. Se corrige aquí.

**Qué hace y qué no hace `git reset --hard`:**

| Afirmación | Estado |
|---|---|
| `git reset --hard` **no equivale** a `git clean` y **no elimina indiscriminadamente** todos los archivos no versionados | **Correcto** |
| `git reset --hard` **puede sobrescribir o eliminar** archivos no versionados cuando estos **obstaculizan la actualización de rutas versionadas** hacia el árbol de destino | **Correcto — es el riesgo real de este paquete** |
| Los archivos `??` están **siempre** protegidos frente a `git reset --hard` | **FALSO — no debe garantizarse** |

**Por tanto: no se debe garantizar que los archivos `??` estén siempre protegidos frente a `git reset --hard`.** Cuando un archivo no versionado ocupa una ruta que el árbol de destino necesita escribir como archivo versionado, la operación **puede sobrescribirlo o eliminarlo**. El hecho de que `reset --hard` no sea `clean` **no convierte la operación en segura**.

**Regla obligatoria — preservación previa:**

> **Antes de cualquier operación de recuperación de estado Git debe preservarse todo el contenido no versionado mediante una copia recuperable fuera del árbol de trabajo.**

Un hash **no** es una copia: `SHA256SUMS_AUDITORIA_R6-R4.txt` permite **detectar** una pérdida o alteración, **no recuperarla** (§8.4).

**Prohibiciones que se mantienen y no se suavizan:**

1. **No usar `git reset --hard` como procedimiento rutinario** de alineación (§8.2).
2. **No ejecutarlo sin evaluación previa del riesgo y autorización expresa** (§8.2).
3. **`git clean` y todas sus variantes** —incluidas `git clean -fd`, `git clean -fdx` y cualquier forma de limpieza— **eliminan archivos no versionados por diseño** y **permanecen prohibidas en esta fase**.

**Aplicado a este paquete:** los cuatro documentos de auditoría, este índice, el manifiesto de evidencias y `SHA256SUMS_AUDITORIA_R6-R4.txt` **no están versionados**. Un `reset --hard` que necesitara escribir en sus rutas **podría destruirlos**, y `git clean -fd` **los destruiría con certeza**. Ninguna de las dos operaciones es segura para este paquete, y ninguna de las dos está autorizada.

### 8.4 Riesgo específico de este paquete

Los cuatro documentos de auditoría, este índice, el manifiesto de evidencias y el archivo `SHA256SUMS` están **sin commit**. En consecuencia:

- **no están protegidos por Git**;
- **no son recuperables desde el remoto**;
- su protección exige **dos cosas a la vez**:
  1. **no ejecutar operaciones destructivas** (§8.2 y §8.3), y
  2. **mantener una copia recuperable fuera del árbol de trabajo** (§8.3).

> **El `SHA256SUMS` no sustituye una copia.** Permite **detectar** una alteración o pérdida; **no permite recuperarla**. Por sí solo, **no constituye una protección**: una pérdida detectada sin copia sigue siendo una pérdida definitiva.

---

## 9. Lo que este índice NO hace

| # | Declaración |
|---|---|
| 1 | **No modifica** ninguno de los cuatro documentos. No añade cabeceras, no renombra, no reformatea, no corrige in situ. |
| 2 | **No invalida** los SHA-256 previamente comunicados: los cuatro hashes de §2 son **los mismos** que se comunicaron y fueron recalculados en Arena. |
| 3 | **No altera** ningún veredicto. Los nueve `UNKNOWN` siguen `UNKNOWN`; `D18` sigue `FAIL`; `C5` sigue `FAIL`. |
| 4 | **No convierte** ninguna categoría de auditoría en veredicto. |
| 5 | **No incorpora** evidencias al repositorio ni crea el manifiesto definitivo. |
| 6 | **No ejecuta** pruebas ni recalcula los hashes de las evidencias externas. |
| 7 | **No crea** commits, ramas ni modifica PR #3 ni PR #4. |
| 8 | **No declara** `D18` ni `D18-R2` globalmente `PASS`. |
| 9 | **No autoriza** ninguna fase posterior (R6-R5, Hardened, producción, audio real). |

### 9.1 Nota sobre los hashes de este índice y del manifiesto

Este índice **no puede contener su propio SHA-256** de forma autorreferente sin invalidarlo. Los hashes de `INDICE_R6-R4.md` y de `MANIFEST_EVIDENCIAS_EXTERNAS_R6-R4.json` se registran en:

```
SHA256SUMS_AUDITORIA_R6-R4.txt
```

Ese archivo incluye **exclusivamente** los seis documentos del paquete documental (los cuatro originales + índice + manifiesto) y **no incluye** los seis JSON de evidencia externa, inaccesibles desde Arena.

---

## 10. Enlaces

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama y HEAD de referencia (`0ae2c10`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit funcional R6-R4 (`bbc1aab`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/bbc1aab50ab1487f81c03697a7f10390088302e5
- Arnés R6-R4: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe de evidencia D18-R2: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- PR #3 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3
- PR #4 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4

---

**Fin del índice. No se modificó ninguno de los cuatro documentos originales. No se ejecutaron pruebas. No se alteró ningún veredicto `UNKNOWN`. No se creó ningún commit ni rama. No se modificó ningún PR. La cadena documental queda CERRADA; las decisiones de adjudicación, conservación de evidencias e integración quedan reservadas a Cris y al usuario.**
