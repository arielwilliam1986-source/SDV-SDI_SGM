# ADENDA COMPLEMENTARIA — ESTADO DE CONSERVACIÓN DE EVIDENCIAS LOCALES R6-R4

**Fecha:** 2026-11-25 (UTC).
**Naturaleza:** corrección documental complementaria. **Solo lectura** respecto de los archivos y del repositorio.
**Estado:** archivo nuevo, **sin commit**.
**Documento corregido:** `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` (sha256 `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f`), que **no se modifica ni se sobrescribe**.

---

## 1. Propósito y alcance

### 1.1 Propósito

Corregir la formulación de la adenda anterior en un punto concreto y limitado: **el estado de conservación de las tres evidencias JSON de las repeticiones R6-R4 en Android/Termux**.

La adenda anterior (§3.2 y §5.4, y su tabla de limitaciones en §8) clasificaba esas evidencias como «sin artefacto persistente». **Esa formulación era demasiado amplia y esta adenda la corrige.**

### 1.2 Alcance

| Incluido | Excluido |
|---|---|
| Corrección del enunciado sobre el artefacto persistente | Modificar la adenda anterior |
| Distinción conservación local ↔ versionado Git | Modificar los tres JSON o sus copias |
| Registro de rutas y hashes **comunicados** | Incorporar los JSON al repositorio |
| Declaración de qué pudo verificarse y qué no en esta sesión | Ejecutar el arnés o importarlo |
| Estado Git final | Repetir pruebas o generar evidencias nuevas |
| — | Cambiar cualquier veredicto `UNKNOWN` |
| — | Crear commits o ramas; tocar PR #3 / PR #4 |
| — | Iniciar R6-R5, Hardened, producción o pruebas de audio real |

---

## 2. Rutas de los tres JSON (declaradas por el usuario)

### 2.1 Originales en el dispositivo Android/Termux

```
$HOME/feas_d18_r2_r4_repeat_1/evidence_d18_r2.json
$HOME/feas_d18_r2_r4_repeat_2/evidence_d18_r2.json
$HOME/feas_d18_r2_r4_repeat_3/evidence_d18_r2.json
```

En el entorno Termux del proyecto, `$HOME` corresponde a `/data/data/com.termux/files/home`.

### 2.2 Copias de respaldo

Directorio:

```
/storage/emulated/0/Download/GitHub Store/lab_sgm/Proyecto SDV-SDI_SGM Diciembre/
```

Nombres:

```
R6R4_repeat_1.json
R6R4_repeat_2.json
R6R4_repeat_3.json
```

`/storage/emulated/0` es el almacenamiento compartido de Android (visible como «almacenamiento interno»), independiente del `$HOME` privado de Termux. La copia en esa ubicación constituye un **segundo soporte físico distinto**, lo que da valor real al respaldo.

### 2.3 Accesibilidad de estas rutas en la sesión actual

**Declaración expresa: ninguna de las seis rutas anteriores es accesible en esta sesión.**

Verificación ejecutada:

| Comprobación | Resultado |
|---|---|
| `uname -s` | `Linux` |
| `id -u` / `id -un` | `1001` / `user` |
| `$HOME` en el sandbox | `/home/user` (Linux, **no** Termux) |
| `/home/user/feas_d18_r2_r4_repeat_{1,2,3}/evidence_d18_r2.json` | **NO EXISTEN** |
| `/storage` | **NO EXISTE** (`No such file or directory`) |
| `/storage/emulated/0` | **NO EXISTE** |
| `find / -maxdepth 6 -name "R6R4_repeat_*.json"` | 0 resultados |
| `find $HOME -maxdepth 5 -name "evidence_d18_r2.json"` | 0 resultados |
| `ls -d /home/user/feas_d18*` | ningún directorio |

El sandbox de esta sesión es un contenedor Linux x86_64 **sin acceso al dispositivo Android del usuario ni a su almacenamiento compartido**. La coincidencia de `$HOME` en la notación **no implica** que `/home/user` (Linux) y `$HOME` (Termux) sean la misma ubicación: son sistemas de archivos distintos en máquinas distintas.

---

## 3. Tabla de SHA-256 de las tres parejas

Los tres hashes fueron **comunicados por el usuario** como previamente verificados. **Esta sesión no pudo recalcularlos** (§2.3).

| # | Original (Termux, `$HOME`) | Copia (almacenamiento compartido) | SHA-256 comunicado |
|---|---|---|---|
| R1 | `feas_d18_r2_r4_repeat_1/evidence_d18_r2.json` | `R6R4_repeat_1.json` | `e438b19c1ffd15945538132392e5b62f274d8aee4a58074d8ed0129e6a32f653` |
| R2 | `feas_d18_r2_r4_repeat_2/evidence_d18_r2.json` | `R6R4_repeat_2.json` | `7bef8eb2d474b920ef558128ed8efcccd32af81ad7a07aa659ed8c147226407e` |
| R3 | `feas_d18_r2_r4_repeat_3/evidence_d18_r2.json` | `R6R4_repeat_3.json` | `e5c9cab23ec32d7125405a2863d8ab9ebe6b6e0feb278ccd990b75518123fd23` |

**Estatus de estos tres valores: COMUNICADOS, no re-verificados en esta sesión.**

---

## 4. Resultado de la verificación de identidad entre originales y copias

### 4.1 Resultado en esta sesión

**NO VERIFICABLE.**

No se pudo comparar original contra copia porque **ninguna de las seis rutas es accesible** desde este sandbox (§2.3). **No se inventa ningún resultado de comparación.**

### 4.2 Lo que consta previamente

El encargo declara que «la auditoría anterior comprobó que los originales y sus copias son idénticos mediante comparación de archivos y SHA-256».

**Precisión necesaria sobre el alcance de esa comprobación previa:** esa verificación se realizó **en el dispositivo del usuario**, no en este sandbox. Se registra como **hecho comunicado y previamente verificado por el usuario**, con el mismo estatus probatorio que los propios hashes.

### 4.3 Contraste con el repositorio (esto sí verificado)

Aunque los JSON no son accesibles, **sí se pudo verificar su ausencia en el repositorio**, que es la mitad Git de la cuestión:

| Comprobación | Resultado |
|---|---|
| `git ls-tree -r --name-only 0ae2c10 \| grep -iE "evidence_d18_r2\|R6R4_repeat\|feas_d18_r2"` | **0 coincidencias** |
| `git grep -l <cada uno de los 3 hashes> HEAD` | **0 coincidencias** en los tres casos |
| Recálculo de sha256 de **todos** los `*.json` versionados en HEAD y comparación con los 3 hashes | **0 coincidencias** |
| `find . -name "*r4_repeat*" -o -name "feas_d18*"` | **0 resultados** |

**Conclusión verificada:** **ninguno de los tres JSON, ni sus copias, está incorporado al repositorio**, ni como contenido ni como referencia textual a sus hashes. Esto se cumple en HEAD `0ae2c10c472e2e9941320fa1dd2727f1a044701c`.

---

## 5. Distinción entre conservación local y versionado Git

Esta es la distinción central que la adenda anterior no formuló con suficiente precisión.

| Nivel | Estado | Fundamento |
|---|---|---|
| **1. Conservación local** | **SÍ** — los tres JSON existen en el dispositivo Android/Termux, con copias de respaldo verificadas en un segundo soporte físico (`/storage/emulated/0`). | Declarado por el usuario; verificado previamente en el dispositivo. **No re-verificado en esta sesión** por inaccesibilidad (§2.3). |
| **2. Presencia en el repositorio** | **NO** — los tres JSON no forman parte de los archivos versionados en HEAD `0ae2c10`. | **Verificado en esta sesión** (§4.3): 0 coincidencias por ruta, por hash y por contenido de todos los `.json` versionados. |
| **3. Verificación independiente** | **Limitada por el canal** — los artefactos locales permiten inspeccionar los registros originales **en el dispositivo**; su ausencia del repositorio **no significa que no existan ni que no se hayan conservado**. | Consecuencia lógica de 1 y 2. |

### 5.1 La inferencia que debe evitarse

> **Ausencia en el repositorio ≠ ausencia de artefacto.**

La adenda anterior, al escribir «sin artefacto persistente», permitía la lectura contraria. **Esa lectura es incorrecta:** los artefactos **existen y están conservados en dos ubicaciones**, simplemente **no están versionados en Git**.

### 5.2 La consecuencia que sí se mantiene

Que los artefactos existan **en el dispositivo** no los convierte en **verificables desde el repositorio**. Un tercero que audite únicamente el repositorio sigue sin poder inspeccionarlos, y **esta sesión tampoco pudo hacerlo**.

Por tanto:

- **Se corrige** la afirmación de inexistencia (§6).
- **Se mantiene** la conclusión de que la reproducibilidad independiente **no puede certificarse desde el repositorio**.
- **Se mantiene** que las tres repeticiones constan como **resultado comunicado**, no como evidencia reproducible en el repositorio.

---

## 6. Corrección explícita de la formulación de la adenda anterior

### 6.1 Texto que se corrige

En `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md`:

| Ubicación | Texto de la adenda anterior | Problema |
|---|---|---|
| §3.2, tabla, nivel 2 | «**Artefacto persistente** \| **NO disponible** \| No se generó ni se conserva JSON, log independiente ni archivo verificable de esa ejecución.» | Correcto **solo** para el probe T1/T2, **no** para las tres repeticiones R6-R4 |
| §5.4, tabla, nivel 2 | «**Artefacto persistente** \| **NO** \| No se conserva JSON, log ni archivo verificable de esas tres repeticiones en el repositorio.» | **Ambiguo**: mezcla «en el repositorio» con «no se conserva» |
| §8, tabla de limitaciones | «R6-R4 en Android/Termux … Resultado **comunicado**; **sin artefacto persistente**; **no certificable** desde el repositorio» | **Incorrecto en la primera parte**: el artefacto **sí** persiste, localmente |

### 6.2 Formulación corregida

> **Los artefactos existen localmente y en el respaldo, pero no están versionados en el repositorio.**

Desglose de la formulación corregida:

| Aspecto | Estado correcto |
|---|---|
| ¿Existen los JSON? | **SÍ** — tres archivos, en el dispositivo Android/Termux |
| ¿Están respaldados? | **SÍ** — copias en `/storage/emulated/0/Download/GitHub Store/lab_sgm/Proyecto SDV-SDI_SGM Diciembre/` |
| ¿Son idénticos original y copia? | **Comunicado como verificado** en auditoría previa en el dispositivo; **no re-verificado aquí** |
| ¿Están versionados en Git? | **NO** — verificado en esta sesión (0 coincidencias) |
| ¿Son verificables desde el repositorio? | **NO** |
| ¿Son verificables desde esta sesión? | **NO** — el sandbox no accede al dispositivo |
| ¿Constituyen evidencia reproducible en la auditoría? | **NO** — pero **sí** son antecedente documental conservado y localizable |

### 6.3 Nota técnica sobre la ruta de escritura del arnés

Se registra un dato verificado en esta sesión que conviene dejar documentado para evitar confusiones futuras:

El arnés versionado declara, en la línea 227:

```python
EVIDENCE_DIR = "/tmp/feas_d18_r2_evidence"
```

y escribe, en la línea 3155:

```python
with open(os.path.join(EVIDENCE_DIR, "evidence_d18_r2.json"), "w") as fh:
```

**Verificado además por búsqueda:** el arnés **no** contiene `os.environ`, `getenv`, `argparse` ni `sys.argv` (0 coincidencias). Es decir, **la ruta de evidencia no es configurable por variable de entorno ni por argumento de línea de comandos**.

**Consecuencia:** que las tres repeticiones se conserven en `$HOME/feas_d18_r2_r4_repeat_{1,2,3}/` **no se explica por el comportamiento del arnés versionado en HEAD**. Esa organización por directorios requirió alguna acción externa al arnés (copia, movimiento o ejecución con un `cwd`/wrapper distinto), que **no está documentada en el repositorio**.

**Esto no cuestiona la existencia ni la validez de los JSON.** Es una **observación de trazabilidad**: la cadena entre la ejecución del arnés y la ubicación final de los tres archivos no es reproducible a partir del código versionado. Se registra como limitación documental, **sin inferir nada sobre cómo se generaron**.

---

## 7. Resultados comunicados — sin cambio de veredictos

### 7.1 Las tres repeticiones

Según lo comunicado por el usuario, y **sin que esta sesión pueda re-verificarlo**:

| Repetición | PASS | FAIL | UNKNOWN | `R2-C9` | Global D18-R2 |
|---|---|---|---|---|---|
| R6-R4 Termux — repetición 1 | 30 | 0 | 9 | **PASS** | `UNKNOWN` |
| R6-R4 Termux — repetición 2 | 30 | 0 | 9 | **PASS** | `UNKNOWN` |
| R6-R4 Termux — repetición 3 | 30 | 0 | 9 | **PASS** | `UNKNOWN` |

**Estatus:** resultado **comunicado**, con artefactos **conservados localmente y respaldados**, pero **no versionados** en el repositorio.

### 7.2 Veredictos — declaración de no alteración

> **No se modifica ningún veredicto.**
>
> - Los **nueve `UNKNOWN`** de D18-R2 (R2-B6, R2-D1, R2-D2, R2-C2, R2-C3, R2-C5, R1-A3, R1-A4, R1-B2) **siguen siendo `UNKNOWN`**.
> - El veredicto global de **D18-R2 en Android/Termux sigue siendo `UNKNOWN`** (30/0/9 en las tres repeticiones comunicadas).
> - El **`FAIL` de `R2-C9` pertenece a R6-R3**, no a R6-R4.
> - **`D18` sigue `FAIL`** (hallazgo histórico `C5`, intacto).
> - **No se declara `D18` ni `D18-R2` globalmente `PASS`.**

### 7.3 Lo que esta corrección **no** cambia

Es importante delimitar el efecto real de esta adenda:

| Pregunta | Respuesta |
|---|---|
| ¿Los `UNKNOWN` dejan de ser `UNKNOWN`? | **No.** |
| ¿Las tres repeticiones pasan a ser evidencia **reproducible desde el repositorio**? | **No.** |
| ¿Mejora la **trazabilidad** de las repeticiones? | **Sí**, parcialmente: ahora consta que existen tres JSON conservados y respaldados, con rutas y hashes comunicados. |
| ¿Se resuelve la falta de versionado? | **No.** Requiere decisión de Cris y del usuario. |

---

## 8. Estado Git final

```
Rama:                     arena/a2d9ac2e-sdv-sdi-sgm
HEAD:                     0ae2c10c472e2e9941320fa1dd2727f1a044701c    (sin cambios)
Archivos versionados modificados:  0
Commits creados:                   0
Ramas creadas:                     0
PR #3:  no modificado, no fusionado, no cerrado
PR #4:  no modificado, no fusionado, no cerrado
```

**Archivos no versionados (`??`) tras esta fase:**

| Archivo | Origen |
|---|---|
| `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` | Fase de auditoría (preexistente, no tocada) — sha256 `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` |
| `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` | Fase de rectificación (preexistente, no tocada) — sha256 `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f` |
| `ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md` | **Esta fase** (nueva) |

**Archivos versionados modificados:** **NINGUNO**.

---

## 9. Confirmación: no se ejecutaron pruebas ni se modificó nada

| Verificación | Resultado |
|---|---|
| Ejecución del arnés (`main()`, `run_controller()`, baterías) | **Ninguna** |
| Importación de módulos del arnés | **Ninguna** |
| Generación de evidencias nuevas | **Ninguna** |
| Repetición de pruebas | **Ninguna** |
| Modificación de los tres JSON originales | **No se accedió a ellos** (§2.3) |
| Modificación de las tres copias de respaldo | **No se accedió a ellas** (§2.3) |
| Incorporación de los JSON al repositorio | **No realizada** |
| Modificación de código o informes versionados | **Ninguna** — arnés verificado en `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18`, informe de evidencia en `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db` |
| Modificación de la adenda anterior | **Ninguna** — `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f` sin cambios |
| Modificación de la auditoría original | **Ninguna** — `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` sin cambios |
| `_mmap.close()` con referencias vivas | **No utilizado** |
| Errores artificiales de procfs, permisos o carreras | **No provocados** |
| D18-R1 `C5` histórico | **No ejecutado** |
| R6-R5 / Hardened / producción / audio real | **No iniciados** |
| `python -B` | Usado solo para lectura estática de texto, si aplicó. Sin `__pycache__` |

---

## 10. Resumen de verificaciones de esta fase

| # | Condición | Estado |
|---|---|---|
| 1 | Adenda anterior no modificada | **CUMPLIDA** |
| 2 | Documento nuevo creado, sin commit | **CUMPLIDA** |
| 3 | SHA-256 de los 3 JSON registrados como comunicados | **CUMPLIDA** (§3) |
| 4 | Identidad original↔copia: declarada **no verificable aquí** sin inventar resultado | **CUMPLIDA** (§4.1) |
| 5 | Ausencia en el repositorio verificada de forma positiva | **CUMPLIDA** (§4.3) |
| 6 | Distinción conservación local ↔ versionado Git | **CUMPLIDA** (§5) |
| 7 | Corrección explícita de la formulación anterior | **CUMPLIDA** (§6) |
| 8 | Resultados 30/0/9 por repetición registrados sin cambio de veredictos | **CUMPLIDA** (§7) |
| 9 | Estado Git final sin cambios | **CUMPLIDA** (§8) |
| 10 | Sin commits, sin ramas, sin tocar PR | **CUMPLIDA** |

**Condiciones NO verificables en esta sesión:**

- Existencia física de los tres JSON en el dispositivo Android/Termux.
- Existencia física de las tres copias en `/storage/emulated/0/...`.
- Correspondencia real de los tres SHA-256 comunicados con el contenido de los archivos.
- Identidad efectiva entre cada original y su copia.
- Contenido de los registros (`counts`, `global_verdict`, `tests`) de las tres repeticiones.

Todas ellas **se declaran no verificables en esta sesión** y **no se sustituyen por inferencias**.

---

## 11. Enlaces de GitHub

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama y HEAD (`0ae2c10`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit funcional R6-R4 (`bbc1aab`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/bbc1aab50ab1487f81c03697a7f10390088302e5
- Arnés R6-R4 en HEAD (origen de `EVIDENCE_DIR`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe de evidencia D18-R2: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- PR #3 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3
- PR #4 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4

---

## 12. Decisión reservada

> **La decisión de incorporar las evidencias al repositorio queda reservada a Cris y al usuario.**
>
> Vías posibles, **ninguna ejecutada ni recomendada aquí**:
> - versionar los tres JSON en el repositorio (cambia el tamaño del árbol y requiere decisión sobre política de evidencias);
> - versionar solo un `SHA256SUMS` con los tres hashes (no incorpora los artefactos, pero deja constancia verificable);
> - mantener los JSON fuera del repositorio y registrar únicamente su existencia y localización en un informe versionado.
>
> Cada opción exige **una autorización y un commit propios**, fuera del alcance de esta fase documental.

---

**Fin de la adenda complementaria. No se ejecutaron pruebas. No se modificó código ni ningún archivo versionado. No se incorporaron evidencias al repositorio. No se creó ningún commit ni rama. No se alteró ningún veredicto `UNKNOWN`. La decisión sobre la incorporación de evidencias queda reservada a Cris y al usuario.**
