# ADENDA DE RECTIFICACIÓN DOCUMENTAL — AUDITORÍA UNKNOWN R6-R4

**Fecha:** 2026-11-25 (UTC).
**Naturaleza:** adenda documental, de solo lectura respecto del código y las evidencias originales.
**Estado:** archivo nuevo, **sin commit**.

**Propósito.** Corregir y precisar cuatro puntos detectados en la revisión de `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md`, **sin modificar el informe original**, sin alterar ningún veredicto histórico y sin tocar código, pruebas, evidencias, ramas ni PR.

> **Advertencia de alcance.** Esta adenda **no reemplaza** el informe original, que permanece byte a byte intacto (§7). No cambia ningún veredicto. No convierte ningún `UNKNOWN` en `PASS`. No declara `D18` ni `D18-R2` globalmente `PASS`.

---

## 1. Identificación del material

| Elemento | Valor |
|---|---|
| Repositorio | `https://github.com/arielwilliam1986-source/SDV-SDI_SGM` |
| Rama | `arena/a2d9ac2e-sdv-sdi-sgm` |
| HEAD verificado | `0ae2c10c472e2e9941320fa1dd2727f1a044701c` |
| Commit funcional R6-R4 | `bbc1aab50ab1487f81c03697a7f10390088302e5` |
| Informe auditado (original) | `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` |
| SHA-256 del informe original | `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` |
| SHA-256 verificado en esta fase | `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` — **coincide**, original no modificado |
| Arnés R6-R4 | `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` |
| SHA-256 del arnés | `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18` — **sin cambios** |
| Informe de evidencia D18-R2 | `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` |
| SHA-256 del informe de evidencia | `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db` — **sin cambios** |

---

## 2. Rectificación 4.1 — Distribución de categorías

### 2.1 Naturaleza del defecto

El informe original contiene **dos enunciados mutuamente inconsistentes**:

1. En la **tabla consolidada (§7)**, cada una de las nueve filas tiene asignada una categoría. El detalle de las filas es verificable y es el siguiente:

| # | ID | Categoría asignada en la tabla |
|---|---|---|
| 1 | R2-B6 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 2 | R2-D1 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 3 | R2-D2 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 4 | R2-C2 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 5 | R2-C3 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 6 | R2-C5 | `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` |
| 7 | R1-A3 | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` |
| 8 | R1-A4 | `LIMITACION_DEL_ENTORNO_DOCUMENTADA` |
| 9 | R1-B2 | `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` |

2. Sin embargo, la **línea de resumen inmediatamente inferior** a la tabla afirmaba: «`5 ADJUDICABLE_CON_EVIDENCIA_EXISTENTE`».

### 2.2 Verificación

Recuento de las filas de la tabla: **6** casos con `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` (filas 1, 2, 3, 4, 5 y 7). La línea de resumen decía **5**.

**El error es exclusivamente aritmético y está localizado en la línea de resumen.** La tabla, que es el contenido sustantivo, siempre fue correcta y coherente con el análisis caso por caso desarrollado en las secciones 3, 4, 5 y 6 del informe original.

### 2.3 Distribución corregida

| Categoría | Nº | Casos |
|---|---|---|
| `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **6** | R2-B6, R2-D1, R2-D2, R2-C2, R2-C3, R1-A3 |
| `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` | **1** | R2-C5 |
| `LIMITACION_DEL_ENTORNO_DOCUMENTADA` | **1** | R1-A4 |
| `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` | **1** | R1-B2 |
| `NO_DETERMINABLE` | **0** | — |
| **TOTAL** | **9** | — |

### 2.4 Aclaración expresa sobre el significado de las categorías

Estas cinco categorías **describen el grado de explicación documental alcanzado**, no los veredictos del arnés. Son un metanivel de análisis, no un nivel de adjudicación.

En particular, `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` significa que **la razón por la que el veredicto es `UNKNOWN` está completamente determinada y documentada** y no requiere nueva evidencia para ser explicada. **No significa** que el veredicto sea incorrecto, ni que pueda promoverse, ni que exista evidencia que lo contradiga.

**Consecuencia obligatoria:** las seis `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` **siguen siendo `UNKNOWN`**. Las nueve subpruebas conservan su veredicto `UNKNOWN` sin excepción (§4 de esta adenda y §6 del informe original).

---

## 3. Rectificación 4.2 — Estado probatorio del probe T1/T2

### 3.1 Qué afirmaba el informe original y qué había de cierto

El informe original (§2) afirmaba: «La evidencia auxiliar "Probe T1/T2 independiente: 3/3 PASS" no existe en el repositorio».

Esa afirmación **es correcta y se mantiene en su ámbito**, que es el de los **archivos versionados** y las búsquedas efectivamente realizadas:

| Búsqueda | Resultado |
|---|---|
| `grep -rn "[Pp]robe"` en los dos informes D18 | 0 coincidencias |
| `grep -rn "3/3 PASS" --include="*.md"` en todo el repo | 0 coincidencias |
| `grep -rn "vivo="` en `*.md`/`*.json`/`*.txt` | 0 coincidencias |
| `grep -rn "\bT1\b"`/`"\bT2\b"` en `*.md` | Solo 6G.1 (MixHandle), ajenas a D18 |

### 3.2 Lo que el informe original no distinguía (y ahora se precisa)

La formulación del informe original era **demasiado amplia**: al decir «no existe en el repositorio» podía leerse como «el probe nunca se ejecutó». **Esa lectura sería incorrecta y esta adenda la corrige expresamente.**

Se distinguen tres niveles probatorios distintos:

| Nivel | Estado | Descripción |
|---|---|---|
| **1. Ejecución comunicada** | **SÍ existe constancia** | El historial de trabajo registra que el usuario ejecutó una comprobación independiente en Android/Termux con tres escenarios: `B6_external_reference`, `D1_retained_view`, `D2_retained_reference`. Resultado comunicado: `maps_while_reference_alive=1`, `maps_after_last_reference_released=0`, `unparsed_maps_lines=0`, `pass=True` en los tres ⇒ **3/3 PASS**. Sin cierre forzado de `mmap`. |
| **2. Artefacto persistente** | **NO disponible** | No se generó ni se conserva JSON, log independiente ni archivo verificable de esa ejecución. No hay nada en el repositorio que permita a un tercero inspeccionar los datos crudos. |
| **3. Reproducibilidad independiente** | **NO certificable** | No puede reproducirse a partir del repositorio ni de un artefacto persistente. No hay script versionado de ese probe ni parámetros registrados que permitan repetirlo de forma equivalente. |

### 3.3 Corrección de la formulación

**No se afirma que el probe nunca se ejecutó.** Se afirma que:

- **Hubo una ejecución real comunicada** por el usuario en su dispositivo Android/Termux, con resultado 3/3 PASS.
- Esa ejecución **no dejó artefacto persistente** verificable.
- Por tanto, **no puede certificarse su reproducibilidad independiente**.

### 3.4 Conclusión correcta y su efecto sobre la auditoría

El probe T1/T2 constituye un **antecedente auxiliar comunicado**: útil como contexto, coherente con el resto de la evidencia, y consistente con lo que el arnés demuestra en `R2-B2` (liberación natural cuando no hay referencias vivas).

**Pero es insuficiente para:**
- reemplazar los registros originales del arnés;
- alterar los veredictos `UNKNOWN` de `R2-B6`, `R2-D1` y `R2-D2`;
- servir como prueba primaria en una adjudicación formal.

**Las categorías de `R2-B6`, `R2-D1` y `R2-D2` no cambian** (§4). Su clasificación como `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` sigue apoyándose, como en el informe original, en el **código del arnés y en las tablas de su informe de evidencia**, no en el probe.

**Nota sobre el escenario O_DIRECTORY:** una asimetría relevante es que en Termux el probe reportó `maps_after_last_reference_released=0` (el mapeo desaparece al liberar la referencia), mientras que `R2-B6`/`R2-D1`/`R2-D2` **no liberan** la referencia y por eso el mapeo persiste en Linux. Son escenarios distintos, no contradictorios. Esta asimetría no se resuelve con el probe y refuerza que su valor es contextual, no adjudicador.

---

## 4. Rectificación 4.3 — Discrepancia de EUID

### 4.1 Dónde aparece exactamente el valor 1001

El valor `1001` aparece **una sola vez** en el informe de auditoría original, en §4.2 (R2-C3), con esta redacción:

> «En este entorno auditado `euid = 1001` (`user`), por lo que la precondición se cumple…»

Es decir, el informe original **sí lo atribuía correctamente** al entorno auditado (el sandbox Linux donde se ejecutó la auditoría), **no** al dispositivo Android.

### 4.2 Qué ejecución o entorno describe ese 1001

El valor está **plenamente acreditado como perteneciente al sandbox Linux Arena**. Evidencia verificable:

| Fuente | Contenido |
|---|---|
| Medición directa en esta sesión | `id -u` → `1001`; `id -un` → `user` |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md`, línea 39 | «`Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; **euid 1001**)» |
| `INFORME_FEASIBILITY_D18_MMAP_6G1.md`, líneas 29, 162, 163 | «sandbox Arena; euid 1001»; «euid 1001 sin `CAP_SYS_ADMIN`»; «euid 1001. **No extrapolable** a Android/Termux» |
| `INFORME_FEASIBILITY_1_6G1.md`, línea 26 | «sandbox Arena; euid 1001» |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DIAGNOSTICO_I1_6G1.md`, línea 18 | «euid 1001 (uid único del sandbox)» |
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/DISENO_PUBLICACION_ANCLADA_6G1.md`, línea 27 | «euid 1001» |
| `INFORME_PDA1_HALLAZGOS_CDEFG_6G1.md`, `INFORME_RECTIFICACION_E1G1C6F1_6G1.md`, `INFORME_RECTIFICACION_FINAL_E1_6G1.md` | «euid 1001 (single-uid; declarado)» |
| `ADJUDICACION_FINAL_DISENO_PREINTEGRACION_HARDENED_6G1.md`, línea 128 | «euid 1001» en el entorno Linux documentado |

**Conclusión:** `1001` es el `euid` del **sandbox Linux Arena**, documentado en diez archivos versionados y confirmado por medición directa en esta sesión.

### 4.3 Contraste con el registro de entorno Android/Termux R6-R4

| Valor | Origen | ¿Acreditado en el repositorio? |
|---|---|---|
| `1001` | Sandbox **Linux Arena** (UID de usuario sin privilegios en Debian/Arena) | **SÍ** — diez documentos versionados + medición directa |
| `10070` | **Android/Termux** (rango de UID de aplicación Android, 10000–19999) | **NO** — `grep -rn "10070"` sobre `*.md`/`*.txt`/`*.csv` no devuelve ninguna coincidencia como euid; no consta en ningún documento versionado |

### 4.4 Declaración de la discrepancia y su tratamiento

**No se asume que ambos valores pertenezcan al mismo entorno.** Son entornos distintos y los valores son coherentes con esa distinción: `1001` en Linux Arena, `10070` en la app Android.

**Estado de la discrepancia:**

1. **`1001` está acreditado y localizado:** pertenece al sandbox Linux Arena, no a Android. **No se reemplaza por `10070`**, porque no hay demostración de que fuera un error; al contrario, hay evidencia positiva de que describe correctamente el entorno de la auditoría.
2. **`10070` es un valor comunicado** en el historial de trabajo del usuario, **no acreditado en ningún artefacto versionado**. Se registra como tal, sin elevarlo a hecho verificado.
3. **No existe evidencia en el repositorio que permita resolver la discrepancia** más allá de lo anterior, porque `10070` no dejó rastro persistente. **Se declara como discrepancia no resuelta en su segundo término.**
4. **No se ejecutaron pruebas para resolverla**, conforme a la restricción 4.3 del encargo.

### 4.5 Conclusión mínima obligatoria

La **observación de portabilidad sobre `euid == 0` se mantiene íntegra como advertencia técnica**: si el proceso fuera `root`, `chmod(0o000)` no bloquearía el acceso y `R2-C3` fallaría por causa ambiental, no por defecto del código.

Sin embargo, **la atribución del valor `1001` al entorno Android R6-R4 no está acreditada — y además es incorrecta**: `1001` corresponde al sandbox Linux Arena, acreditado por diez documentos y por medición directa. **El `euid` del entorno Android/Termux R6-R4 no está acreditado en el repositorio.**

**Precisión sobre el informe original:** el informe original **no cometió** el error de atribuir `1001` a Android; lo atribuyó explícitamente «a este entorno auditado». Esta adenda **no rectifica un error inexistente**, sino que precisa el ámbito del dato y declara que no describe Termux.

---

## 5. Rectificación 4.4 — Separación entre R6-R3 y R6-R4

### 5.1 El problema de mezcla

La sección §9.2 del informe original mezclaba en una sola lista resultados de dos revisiones distintas, lo que podía inducir a atribuir el `FAIL` de `R2-C9` a R6-R4:

> «Los `30 PASS` / `0 FAIL` de R6-R3 Linux siguen intactos. — El `1 FAIL` de R6-R3 Android/Termux (`R2-C9`) sigue intacto… — El veredicto global de D18-R2 en Linux sigue siendo `UNKNOWN` (30/0/9); en Android/Termux `FAIL` (29/1/9).»

Los recuentos eran correctos, pero la presentación no separaba con suficiente claridad **qué revisión produjo qué resultado**.

### 5.2 R6-R3 — Resultados históricos (dispositivo real + Linux)

| Entorno | PASS | FAIL | UNKNOWN | Global | Observación |
|---|---|---|---|---|---|
| **Linux** (sandbox Arena, R6-R3) | 30 | 0 | 9 | `UNKNOWN` | 39 subpruebas; 10/10 ejecuciones idénticas |
| **Android/Termux** (dispositivo del usuario, R6-R3) | 29 | 1 | 9 | `FAIL` | **El único `FAIL` era `R2-C9`** |

**Causa de ese `FAIL`:** la `R2-C9` de R6-R3 exigía `os.listdir(dirfd)` tras `shutil.rmtree(d)`; en Bionic/Android produjo `FileNotFoundError` con el descriptor abierto. Expectativa no portable.

### 5.3 R6-R4 — Alcance declarado en el repositorio (HEAD `0ae2c10`)

**Aquí es necesario ser explícito, porque el encargo y el repositorio no coinciden en este punto.**

El informe de evidencia en HEAD (`INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md`) **declara la validación Termux de R6-R4 como pendiente**, en tres lugares inequívocos:

| Ubicación | Texto literal |
|---|---|
| §13.4, tabla de plataforma, línea 323 | «Android/Termux en sandbox \| **NO disponible** (ninguna ejecución real en dispositivo Android/Termux en esta sesión)» |
| §13.5, punto 1 | «**Qué permanece pendiente de validar en Android/Termux real:** 1. Ejecución completa del arnés corregido en el dispositivo Termux objetivo…» |
| Línea 239 | «…sin batería completa en Arena (falta `numpy`, ver §13.4) y **sin validación Termux aún**» |

**Lo único que el repositorio acredita de R6-R4 es la validación aislada en Linux Arena:** `R2-C8`, `R2-C9` (corregida), `R2-C12`, `R2-C14` ⇒ **4 PASS · 0 FAIL · 0 UNKNOWN**; y `R2-C9` **5/5 PASS** consecutivas sin fuga de fds.

### 5.4 R6-R4 en Android/Termux — lo comunicado y su estatus probatorio

El encargo de esta adenda aporta un resultado de R6-R4 en Android/Termux que **no consta en ningún archivo versionado**. Aplicando a este caso **el mismo marco de tres niveles** que el propio encargo exige en el punto 4.2 (§3.2 de esta adenda), se registra así:

| Nivel | Estado | Contenido |
|---|---|---|
| **1. Ejecución comunicada** | **SÍ** | Tres repeticiones completas independientes en Android/Termux. En cada una: **30 PASS / 0 FAIL / 9 UNKNOWN**, con `R2-C9` en **PASS**. El resultado global de D18-R2 **sigue siendo `UNKNOWN`** en los tres casos. |
| **2. Artefacto persistente** | **NO** | No se conserva JSON, log ni archivo verificable de esas tres repeticiones en el repositorio. |
| **3. Reproducibilidad independiente** | **NO certificable** | No puede verificarse desde el repositorio. |

**Consecuencias, declaradas sin ambigüedad:**

1. **Se registra** que, según lo comunicado, R6-R4 en Android/Termux produce **30 PASS / 0 FAIL / 9 UNKNOWN** en cada una de **tres repeticiones independientes**, con `R2-C9` en **PASS** en las tres.
2. **Esta adenda NO puede certificar** esos resultados como evidencia reproducible: **no existe artefacto persistente** que los respalde en el repositorio. Constan como **resultado comunicado**, con el mismo estatus que el probe T1/T2 (§3.2).
3. **El informe de evidencia en HEAD no los recoge** y sigue declarando la validación Termux **pendiente** (§5.3). La incorporación formal de esas tres repeticiones al informe requeriría **un commit posterior con autorización expresa**, fuera del alcance de esta adenda (que no crea commits).
4. **Queda declarada la discrepancia** entre el encargo y el estado documental del repositorio. No se resuelve aquí ni se oculta.

### 5.5 El FAIL de R2-C9 pertenece a R6-R3 — corrección definitiva

**Afirmación que sí queda establecida sin reservas:**

> **El `FAIL` de `R2-C9` pertenece exclusivamente al resultado histórico de R6-R3 en Android/Termux. No debe atribuirse a R6-R4.**

Fundamento: (i) R6-R3 en Termux registró `29 PASS · 1 FAIL · 9 UNKNOWN` con `R2-C9` como único `FAIL`; (ii) R6-R4 sustituyó precisamente esa expectativa por identidad `fstat`; (iii) en Linux Arena, la `R2-C9` corregida da `PASS` 5/5. La causa del `FAIL` histórico —la expectativa no portable de enumeración tras eliminación— **fue eliminada por R6-R4**.

### 5.6 Referencias históricas de Linux, siempre identificadas por revisión

| Revisión | Entorno | PASS | FAIL | UNKNOWN | Global |
|---|---|---|---|---|---|
| R6-R3 | Linux Arena | 30 | 0 | 9 | `UNKNOWN` |
| R6-R4 | Linux Arena — **selección aislada de 4 subpruebas** (no batería completa) | 4 | 0 | 0 | `PASS` (solo de la selección) |
| R6-R4 | Linux Arena — `R2-C9` repetida 5 veces | 5/5 `PASS` | 0 | 0 | n/a |

**Advertencia:** el `4 PASS · 0 FAIL · 0 UNKNOWN` de R6-R4 **no es comparable** con el `30/0/9` de R6-R3: la primera es una **selección de cuatro subpruebas**, la segunda es la **batería completa de 39**. Presentarlas como equivalentes sería un error.

### 5.7 Estado global de D18 — sin cambios

- **`D18` sigue `FAIL`** (hallazgo histórico `C5`: `SIGSEGV` al cerrar `_mmap` con array vivo, reproducido 3/3).
- **`D18-R2` no es `PASS` global.** En Linux, el único global acreditado en el repositorio sigue siendo `UNKNOWN` (30/0/9, R6-R3).
- **No se declara `D18` ni `D18-R2` globalmente `PASS`** en ninguna interpretación de esta adenda.

---

## 6. Tabla consolidada corregida (nueve casos)

| # | ID | Título | Criterio que produce el `UNKNOWN` | Categoría | Veredicto |
|---|---|---|---|---|---|
| 1 | R2-B6 | Referencia externa viva impide la liberación | `kept_maps == 1` ⇒ rama `UNKNOWN` por diseño (el mapping **debe** persistir) | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 2 | R2-D1 | Liberación incompleta (vista retenida) | Ídem | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 3 | R2-D2 | Referencia retenida impide acreditar cierre | Ídem | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 4 | R2-C2 | Entrada que desaparece durante el recorrido (Caso B) | `complete=False` + clasificación correcta (B1 `DESAPARECIDO`, B2 `UNKNOWN_CAUSE`) | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 5 | R2-C3 | Entrada inaccesible (permisos) | `complete=False` + `EACCES` → `DESCRIPTOR_INACCESIBLE` correcta | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 6 | R2-C5 | Error de procfs durante la inspección | `mechanics_ok` correcto pero **sin** `env_evidence` (no hubo `ERROR_PROCFS` real) | `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` | **UNKNOWN** |
| 7 | R1-A3 | Coincidencia + líneas no interpretables | `status == incomplete` ⇒ lectura no acreditable | `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` | **UNKNOWN** |
| 8 | R1-A4 | `/proc/self/maps` no disponible o ilegible | `status == unreadable` sobre ruta **sintética**, no `/proc` real | `LIMITACION_DEL_ENTORNO_DOCUMENTADA` | **UNKNOWN** |
| 9 | R1-B2 | Inventario incompleto (symlink roto) | `complete=False`; `DESAPARECIDO` no distingue symlink roto de borrado | `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` | **UNKNOWN** |

**Distribución corregida:** **6** `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` · **1** `UNKNOWN_CORRECTO_POR_EVIDENCIA_INSUFICIENTE` · **1** `LIMITACION_DEL_ENTORNO_DOCUMENTADA` · **1** `REQUIERE_NUEVA_EVIDENCIA_NO_DESTRUCTIVA` · **0** `NO_DETERMINABLE`. **TOTAL: 9.**

(Esta línea sustituye a la línea de resumen defectuosa del informe original, que decía «5». La tabla del original ya contenía 6 y no se modifica.)

---

## 7. Declaración expresa sobre los nueve UNKNOWN

> **Los nueve resultados `UNKNOWN` permanecen intactos: R2-B6, R2-D1, R2-D2, R2-C2, R2-C3, R2-C5, R1-A3, R1-A4 y R1-B2 siguen siendo `UNKNOWN`.**
>
> Ninguno se convierte en `PASS`. Ninguno se convierte en `FAIL`. Ninguno se reclasifica.
>
> Las categorías de §6 son un **metanivel de explicación documental**: describen cuánto se ha comprendido del `UNKNOWN`, no lo que el `UNKNOWN` vale. Un caso `ADJUDICABLE_CON_EVIDENCIA_EXISTENTE` sigue siendo `UNKNOWN` y seguiría siéndolo aunque su causa estuviera completamente esclarecida, porque el veredicto depende del criterio de la prueba, no de la claridad de la explicación.

---

## 8. Limitaciones probatorias que permanecen

| Limitación | Estado |
|---|---|
| JSON de evidencia del arnés (`/tmp/feas_d18_r2_evidence/`) | **No versionado.** No persistió entre sesiones. Toda evidencia primaria es el registro textual del informe §6 + el código fuente |
| Probe T1/T2 (3/3 PASS en Termux) | Ejecución **comunicada**; **sin artefacto persistente**; **no reproducible** desde el repositorio |
| R6-R4 en Android/Termux (3 × `30/0/9`, `R2-C9` PASS) | Resultado **comunicado**; **sin artefacto persistente**; **no certificable** desde el repositorio; el informe en HEAD sigue declarándolo **pendiente** |
| `euid` del entorno Android/Termux (`10070`) | **No acreditado** en ningún archivo versionado |
| `euid = 1001` | **Acreditado** como sandbox Linux Arena (10 documentos + medición directa). **No describe Android** |
| Validación Termux de R6-R4 | **Pendiente** según el informe en HEAD (§13.5). Declarada como tal sin excepción |

---

## 9. Confirmación: no se ejecutaron pruebas ni se modificó código

| Verificación | Resultado |
|---|---|
| Ejecución del arnés (`main()`, `run_controller()`, baterías, controladores, probes) | **Ninguna** |
| Importación del arnés | **Ninguna** |
| Uso de `python` | **Solo `python3 -B`**, exclusivamente para conteo de texto y `re`/`Counter` sobre el informe de auditoría. Sin `__pycache__` |
| Modificación del arnés R6-R4 | **Ninguna** — sha256 `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18` sin cambios |
| Modificación del informe de evidencia D18-R2 | **Ninguna** — sha256 `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db` sin cambios |
| Modificación del informe de auditoría original | **Ninguna** — sha256 `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` sin cambios |
| `_mmap.close()` / `mmap.close()` con referencias vivas | **No utilizado** |
| Errores artificiales de procfs, permisos o carreras | **No provocados** |
| D18-R1 `C5` histórico | **No ejecutado** |
| Instalación de dependencias | **Ninguna** (`numpy` no requerido en fase documental) |
| Carpetas `/proc` falsas o symlinks alterados | **Ninguno** |

---

## 10. Confirmación: PR #3 y PR #4 sin modificar y sin fusionar

| PR | Estado declarado |
|---|---|
| **PR #3** — `https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3` | **No modificado. No fusionado. No cerrado.** |
| **PR #4** — `https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4` | **No modificado. No fusionado. No cerrado.** |

Ninguna operación de Git o de GitHub se ejecutó contra ninguno de los dos PR en esta fase. No se creó ningún commit ni ninguna rama.

---

## 11. Estado final de Git

```
Rama:            arena/a2d9ac2e-sdv-sdi-sgm
HEAD:            0ae2c10c472e2e9941320fa1dd2727f1a044701c   (sin cambios)
git status:      solo archivos no versionados (??) ; 0 archivos versionados modificados
Commits creados: NINGUNO
Ramas creadas:   NINGUNA
```

**Archivos no versionados (nuevos) de esta fase:**

- `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` — **este archivo**

**Archivos no versionados preexistentes (de la fase anterior, no tocados):**

- `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md`

**Archivos versionados modificados:** **NINGUNO**.

---

## 12. SHA-256 del archivo nuevo

Calculado después de escribir el archivo. El valor se entrega en el mensaje de entrega (§13) y se registra aquí mediante la verificación `sha256sum` ejecutada en la misma fase:

```
sha256sum ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md
```

> El valor exacto se transcribe en la entrega, por coherencia con la restricción de no inventar hashes: un archivo no puede contener su propio hash de forma autorreferente sin invalidarlo. Se documenta en la entrega y en el resumen de verificaciones.

---

## 13. Resumen de verificaciones de esta fase

| # | Condición exigida | Estado |
|---|---|---|
| 1 | HEAD continúa en `0ae2c10c472e2e9941320fa1dd2727f1a044701c` | **CUMPLIDA** |
| 2 | Arnés R6-R4 conserva `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18` | **CUMPLIDA** |
| 3 | Informe original no fue modificado (`28bb335a…`) | **CUMPLIDA** |
| 4 | Sin cambios en archivos versionados | **CUMPLIDA** |
| 5 | Único archivo nuevo de esta fase: la adenda | **CUMPLIDA** |
| 6 | Ningún commit creado | **CUMPLIDA** |
| 7 | PR #3 y PR #4 sin modificar ni fusionar | **CUMPLIDA** |
| 8 | Ningún veredicto histórico alterado | **CUMPLIDA** |
| 9 | Ningún `UNKNOWN` convertido en `PASS` | **CUMPLIDA** |
| 10 | Discrepancia EUID declarada | **CUMPLIDA** (§4.4) |
| 11 | Probe T1/T2 declarado con sus tres niveles | **CUMPLIDA** (§3.2) |
| 12 | R6-R4 Termux declarado con sus tres niveles y la discrepancia con HEAD | **CUMPLIDA** (§5.4) |

**Condiciones no verificables en este entorno:**

- El `euid` real del dispositivo Android/Termux del usuario (`10070` comunicado, no acreditado). **Declarado como no resuelto.**
- La existencia de artefactos de las tres repeticiones de R6-R4 en Termux. **No disponibles.**
- La existencia de artefactos del probe T1/T2. **No disponibles.**

---

## 14. Enlaces de GitHub

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama y HEAD (`0ae2c10`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit funcional R6-R4 (`bbc1aab`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/bbc1aab50ab1487f81c03697a7f10390088302e5
- Arnés R6-R4 en HEAD: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe de evidencia D18-R2: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- Informe histórico D18-R1 (fuente de `C5`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_MMAP_6G1.md
- PR #3 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3
- PR #4 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4

---

**Fin de la adenda. No se implementaron recomendaciones. No se inició R6-R5. No se realizó ninguna integración. No se creó ningún commit. La siguiente decisión técnica queda reservada a Cris / ChatGPT y al usuario.**
