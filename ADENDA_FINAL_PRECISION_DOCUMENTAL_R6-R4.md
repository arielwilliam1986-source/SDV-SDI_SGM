# ADENDA FINAL — PRECISIÓN DOCUMENTAL R6-R4

**Fecha:** 2026-11-25 (UTC).
**Naturaleza:** corrección documental. **Solo lectura** respecto del repositorio y de los documentos anteriores.
**Estado:** archivo nuevo, **sin commit**.

**Propósito único:** corregir dos matices de la documentación anterior:

1. La descripción del **respaldo** de los tres JSON R6-R4.
2. La **trazabilidad** del mecanismo externo que pudo determinar sus directorios finales.

**Documentos que NO se modifican ni se sobrescriben** (verificados intactos por SHA-256 en §7):

- `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` — `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678`
- `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` — `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f`
- `ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md` — `0a61e9e7533acc114b5631d98e15be36c19d6678b6523a419c4bea1abcf19180`

---

## 1. Fecha y alcance

| Elemento | Valor |
|---|---|
| Fecha | 2026-11-25 (UTC) |
| Rama | `arena/a2d9ac2e-sdv-sdi-sgm` |
| HEAD | `0ae2c10c472e2e9941320fa1dd2727f1a044701c` |
| Commit funcional R6-R4 | `bbc1aab50ab1487f81c03697a7f10390088302e5` |

**Alcance incluido:** las dos precisiones de §2 y §3, la delimitación de lo acreditado (§4), el estado de hashes y evidencias (§5), y las confirmaciones finales (§6, §7).

**Alcance excluido expresamente:** modificar código, archivos versionados, los tres JSON, sus copias o los tres documentos anteriores; recalcular o inventar hashes; ejecutar el arnés; repetir pruebas; cambiar veredictos; ejecutar D18-R1 `C5`; usar `_mmap.close()` con referencias vivas; crear commits o ramas; tocar PR #3 o PR #4; iniciar R6-R5, Hardened, producción o pruebas de audio real.

---

## 2. Primera precisión — naturaleza del respaldo

### 2.1 Enunciado que se corrige

La adenda complementaria anterior (`ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md`, §2.2) afirmó:

> «La copia en esa ubicación constituye un **segundo soporte físico distinto**, lo que da valor real al respaldo.»

### 2.2 Por qué es incorrecto

`/storage/emulated/0` es una **ubicación lógica** del almacenamiento compartido de Android. Está gestionada por el framework de Android (FUSE/sdcardfs/`/mnt/user/0` según versión) y **puede residir en la misma partición física** que el directorio privado de la aplicación Termux (`/data/data/com.termux/files/home`), o no.

**No existe en esta sesión —ni en el repositorio— evidencia sobre la disposición física del almacenamiento del dispositivo del usuario.** Determinar si ambos caminos están en soportes físicos distintos requeriría inspeccionar el dispositivo (puntos de montaje, `df`, tabla de particiones), lo que está fuera del alcance y de las capacidades de esta sesión.

Por tanto, afirmar «segundo soporte físico independiente» **excede la evidencia disponible**.

### 2.3 Formulación correcta

> **Los tres JSON constan como conservados en el directorio privado de Termux y con copias en una segunda ubicación de almacenamiento del dispositivo Android. La independencia física de ambos soportes no está acreditada.**

### 2.4 Lo que sí se mantiene del respaldo

La corrección **no resta valor** al respaldo, solo precisa su naturaleza:

| Aspecto | Estado |
|---|---|
| Existen dos **ubicaciones lógicas distintas** con copia de los JSON | **Comunicado** |
| Son **rutas independientes** (directorio privado de app vs. almacenamiento compartido) | **Comunicado**; verificado conceptualmente: son árboles de directorios distintos |
| La copia protege frente a borrado/desinstalación de la app Termux (que típicamente elimina `/data/data/...`) | **Razonable como propiedad de la ubicación**, no como garantía acreditada |
| La copia protege frente a un **fallo del medio físico** | **NO acreditado** — requeriría conocer la disposición de particiones |
| Los tres hashes coinciden entre original y copia | **Comunicado** como verificado previamente en el dispositivo; **no recalculado en esta sesión** |

---

## 3. Segunda precisión — trazabilidad del directorio de evidencias

### 3.1 Lo que el arnés versionado hace por sí solo

Verificado por lectura directa del código en HEAD:

| Elemento | Valor | Línea |
|---|---|---|
| Directorio de evidencia | `EVIDENCE_DIR = "/tmp/feas_d18_r2_evidence"` | 227 |
| Creación del directorio | `os.makedirs(EVIDENCE_DIR, exist_ok=True)` | 2952 |
| Nombre del archivo | `evidence_d18_r2.json` | 3155 |

Verificado además por búsqueda exhaustiva:

| Comprobación | Resultado |
|---|---|
| `os.environ` / `getenv` en el arnés | **0 coincidencias** |
| `argparse` / `sys.argv` en el arnés | **0 coincidencias** |
| `def main` acepta parámetros | **No** — `def main():` sin argumentos (línea 2903) |
| Alguna función recibe `evidence_dir`/`out_dir`/`evidence_path` | **0 coincidencias** |

**Conclusión parcial:** ejecutado con su configuración predeterminada versionada, **el arnés escribe siempre en `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json`** y **no ofrece ningún punto de configuración interno** (ni variable de entorno, ni argumento, ni parámetro de función).

### 3.2 El mecanismo externo: patrón documentado en el repositorio

**Existe un patrón de lanzador externo documentado y efectivamente utilizado en este repositorio.** Consiste en cargar un módulo desde su ruta y **sustituir atributos del módulo después de cargarlo**.

Ejemplo verificado, en `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_h2_6g1.py`:

```python
def cargar_motor(clave):                      # línea 94
    ruta = MOT / NOMBRE_MOTOR[clave]
    spec = importlib.util.spec_from_file_location('eng_h2_%s' % clave, ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)                # línea 99
    return m
```

Y la sustitución de atributo tras la carga, en el mismo archivo:

```python
m._sha_fd_estable_6g1 = sha_con_muta           # línea 388
try:
    info = m.probe_file(str(copia), 'mix')
finally:
    m._sha_fd_estable_6g1 = original_sha       # línea 392
```

**El mismo patrón (cargar módulo + asignar atributos) está presente en al menos tres lanzadores más del repositorio:**

| Lanzador | `spec_from_file_location` | Asignaciones post-carga |
|---|---|---|
| `pruebas_h2_6g1.py` | 1 | varias (líneas 148, 163, 246, 255, 388, 392) |
| `pruebas_h2_r_6g1.py` | 1 | 3 |
| `pruebas_protocolo_cierre_cr_r1_6g1.py` | 1 | 2 |
| `pruebas_seguridad_6g1.py` | 1 | 1 |

**Consecuencia técnica:** el patrón

```python
module.EVIDENCE_DIR = evidence_dir
```

**es técnicamente viable y coherente con la práctica documentada del proyecto**, aunque la asignación concreta a `EVIDENCE_DIR` no aparezca en el árbol versionado (§3.3).

### 3.3 Lo que NO consta en el repositorio

Búsquedas realizadas, con resultado negativo:

| Búsqueda | Resultado |
|---|---|
| `grep -rn "module\.EVIDENCE_DIR\|\.EVIDENCE_DIR *="` en todo el árbol | **0 coincidencias** |
| `git log --all -S "module.EVIDENCE_DIR" -- "*.py"` | **0 commits** — el patrón nunca existió en el historial versionado |
| `grep -rn "evidence_dir"` en `*.py`/`*.sh` | Solo una coincidencia ajena: `arnes_rgflow_hardened_6g1.py` línea 13, que la usa como **documentación de su propia opción `--salida <evidence_dir>`**, sin relación con D18-R2 |

**Por tanto:** el lanzador concreto que asignaba `module.EVIDENCE_DIR = evidence_dir` **no está versionado** en el repositorio, ni en HEAD ni en ningún commit alcanzable del historial.

### 3.4 Distinción expresa de los cuatro niveles

| Nivel | Afirmación | Estado |
|---|---|---|
| **A** | El arnés, **por sí solo y con su configuración predeterminada versionada**, escribe en `/tmp/feas_d18_r2_evidence`. | **ACREDITADO** — verificado por lectura directa del código (§3.1) |
| **B** | **Existe un mecanismo externo documentado** que permite sustituir `EVIDENCE_DIR` después de cargar el módulo. | **ACREDITADO como patrón** — el patrón cargar-módulo-y-asignar-atributo está documentado y en uso en el repositorio (§3.2); la asignación concreta a `EVIDENCE_DIR` **no está versionada** (§3.3) |
| **C** | Ese mecanismo **demuestra que una ubicación externa es técnicamente posible**. | **ACREDITADO** — consecuencia directa de (A) y (B): si `EVIDENCE_DIR` es un atributo de módulo mutable y el módulo se carga desde otro script, la ruta puede sustituirse antes de invocar `main()` |
| **D** | Ese **mismo lanzador concreto** fue utilizado en **cada una de las tres repeticiones**. | **NO ACREDITADO** — no existe evidencia específica que lo demuestre (§3.5) |

### 3.5 Conclusión normativa

> **La ubicación final de los tres JSON requiere una intervención externa respecto de la configuración predeterminada del arnés. Existe un mecanismo de lanzador externo documentado, pero no se ha acreditado de forma individual que ese mecanismo concreto se utilizara en las tres repeticiones.**

### 3.6 Corrección de la formulación de la adenda complementaria anterior

La adenda complementaria (`ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md`, §6.3) concluyó:

> «…requirió alguna acción externa al arnés (copia, movimiento o ejecución con un `cwd`/wrapper distinto), que **no está documentada en el repositorio**.»

**Corrección:** la parte «no está documentada en el repositorio» es **demasiado amplia**. Lo correcto es:

- El **patrón técnico** (lanzador externo que sustituye atributos del módulo tras cargarlo) **sí está documentado** en el repositorio y se usa en al menos cuatro lanzadores (§3.2).
- Lo que **no está documentado** es la **instancia concreta** de ese patrón aplicada a `EVIDENCE_DIR` para las tres repeticiones R6-R4 (§3.3).

Es decir: **no se puede concluir que la ubicación final carezca de mecanismo técnico conocido.** El mecanismo existe, es conocido y está en uso en el proyecto; lo que falta es la acreditación de que **esa instancia concreta** se aplicó en **esas tres ejecuciones concretas**.

---

## 4. Qué está acreditado y qué sigue sin acreditarse

### 4.1 Acreditado

| # | Afirmación | Cómo |
|---|---|---|
| 1 | El arnés versionado escribe en `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` con su configuración predeterminada | Lectura directa del código, líneas 227, 2952, 3155 |
| 2 | El arnés no admite override por entorno, argumento ni parámetro de función | Búsqueda exhaustiva: 0 coincidencias de `os.environ`/`getenv`/`argparse`/`sys.argv`; `def main():` sin parámetros |
| 3 | El patrón cargar-módulo-y-asignar-atributo está documentado y en uso en el repositorio | 4 lanzadores verificados (§3.2), con líneas citadas |
| 4 | `EVIDENCE_DIR` es un atributo de módulo mutable, sustituible tras la carga | Consecuencia de 1 y 3; el propio arnés lo declara como global de módulo (línea 227) |
| 5 | Ninguno de los tres JSON está versionado en HEAD `0ae2c10` | 0 coincidencias por ruta, por hash (`git grep` de los 3 SHA-256) y por recálculo de sha256 de **todos** los `*.json` versionados |
| 6 | HEAD sigue en `0ae2c10`; 0 archivos versionados modificados | `git rev-parse HEAD`; `git status --porcelain` |
| 7 | Los tres documentos anteriores están intactos | SHA-256 verificados (§7) |

### 4.2 No acreditado

| # | Afirmación | Estado | Qué haría falta |
|---|---|---|---|
| 1 | Que el lanzador concreto con `module.EVIDENCE_DIR = evidence_dir` se usara en las tres repeticiones | **NO ACREDITADO** | El script del lanzador o su registro de ejecución |
| 2 | El contenido de los tres JSON (`counts`, `global_verdict`, `tests`) | **NO VERIFICABLE aquí** | Acceso al dispositivo o a los archivos |
| 3 | Que los tres SHA-256 comunicados correspondan al contenido real | **NO VERIFICABLE aquí** | Acceso a los archivos para recalcular |
| 4 | Que cada original sea idéntico a su copia | **NO VERIFICABLE aquí** | Acceso a ambos |
| 5 | La **independencia física** de los dos soportes de almacenamiento | **NO ACREDITADO** | Inspección de particiones/montajes del dispositivo |
| 6 | El `euid` real del entorno Android/Termux | **NO ACREDITADO** | Registro de entorno de las ejecuciones |
| 7 | Que las tres repeticiones se ejecutaran con `numpy==1.26.4` y Python 3.11 | **NO ACREDITADO en el repositorio** | Salida de `environment` de los JSON |

Ninguna de estas ausencias se sustituye por inferencia.

---

## 5. Estado de los hashes y de las evidencias locales

### 5.1 Los tres hashes comunicados — sin recalcular

| # | SHA-256 comunicado | Estado |
|---|---|---|
| R1 | `e438b19c1ffd15945538132392e5b62f274d8aee4a58074d8ed0129e6a32f653` | **COMUNICADO** — no recalculado en esta sesión |
| R2 | `7bef8eb2d474b920ef558128ed8efcccd32af81ad7a07aa659ed8c147226407e` | **COMUNICADO** — no recalculado en esta sesión |
| R3 | `e5c9cab23ec32d7125405a2863d8ab9ebe6b6e0feb278ccd990b75518123fd23` | **COMUNICADO** — no recalculado en esta sesión |

**No se recalculan ni se presentan como verificados en esta sesión.** Los archivos no son accesibles desde este sandbox (Linux x86_64; `/storage` y `/storage/emulated/0` no existen; no hay ningún `feas_d18_r2_r4_repeat_*` en el sistema de archivos).

### 5.2 Localización comunicada

| Ubicación | Rutas |
|---|---|
| Directorio privado de Termux | `$HOME/feas_d18_r2_r4_repeat_{1,2,3}/evidence_d18_r2.json` |
| Almacenamiento compartido de Android | `/storage/emulated/0/Download/GitHub Store/lab_sgm/Proyecto SDV-SDI_SGM Diciembre/R6R4_repeat_{1,2,3}.json` |

### 5.3 Ausencia en el repositorio — resultado independiente y verificado

Este resultado es **independiente de la existencia local** y **se conserva íntegro**:

> **Los tres JSON no forman parte del repositorio en HEAD `0ae2c10c472e2e9941320fa1dd2727f1a044701c`.**

Verificado en esta y en la sesión anterior por tres vías concordantes: ausencia de rutas coincidentes en `git ls-tree`, ausencia de los tres hashes en `git grep` sobre HEAD, y ausencia de coincidencia al recalcular el sha256 de todos los `*.json` versionados.

### 5.4 Las tres repeticiones — resultado comunicado

| Repetición | PASS | FAIL | UNKNOWN | `R2-C9` | Global D18-R2 |
|---|---|---|---|---|---|
| R6-R4 Termux — repetición 1 | 30 | 0 | 9 | PASS | `UNKNOWN` |
| R6-R4 Termux — repetición 2 | 30 | 0 | 9 | PASS | `UNKNOWN` |
| R6-R4 Termux — repetición 3 | 30 | 0 | 9 | PASS | `UNKNOWN` |

**Estatus:** resultado **comunicado**, con artefactos **conservados en dos ubicaciones lógicas del dispositivo** y **no versionados** en el repositorio.

---

## 6. Confirmación: los nueve UNKNOWN no cambian

> **Ningún veredicto se modifica en esta adenda.**
>
> **Los nueve `UNKNOWN` permanecen intactos:**
> `R2-B6`, `R2-D1`, `R2-D2`, `R2-C2`, `R2-C3`, `R2-C5`, `R1-A3`, `R1-A4`, `R1-B2`.
>
> **Estado global, sin cambios:**
> - D18-R2 en Android/Termux: **`UNKNOWN`** (30/0/9 en las tres repeticiones comunicadas).
> - D18-R2 en Linux: **`UNKNOWN`** (30/0/9, R6-R3, batería completa de 39 subpruebas).
> - El **`FAIL` de `R2-C9` pertenece a R6-R3**, no a R6-R4.
> - **`D18` sigue `FAIL`** (hallazgo histórico `C5`, intacto, no re-ejecutado).
> - **No se declara `D18` ni `D18-R2` globalmente `PASS`.**

**Esta adenda es exclusivamente documental:** no ejecuta pruebas, no genera evidencias, no reclasifica. Ninguna de las dos precisiones que introduce (§2 y §3) afecta al criterio de ninguna subprueba ni puede alterar un veredicto.

---

## 7. Estado Git final y confirmaciones

### 7.1 Estado Git

```
Rama:                              arena/a2d9ac2e-sdv-sdi-sgm
HEAD:                              0ae2c10c472e2e9941320fa1dd2727f1a044701c
Archivos versionados modificados:  0
Commits creados:                   0
Ramas creadas:                     0
```

### 7.2 Archivos no versionados

| Archivo | Origen | SHA-256 |
|---|---|---|
| `AUDITORIA_DE_RESOLUBILIDAD_UNKNOWN_R6-R4.md` | Fase de auditoría (preexistente, **no tocada**) | `28bb335a571cd2a13b0720db3b0fbfa598da79dc478a9ab3d1dff660463f1678` |
| `ADENDA_RECTIFICACION_AUDITORIA_UNKNOWN_R6-R4.md` | Fase de rectificación (preexistente, **no tocada**) | `72141b76d9cea1595167677fd3d3537974358facc271d9a84cdc0da4c5a56d8f` |
| `ADENDA_COMPLEMENTARIA_EVIDENCIA_LOCAL_R6-R4.md` | Fase complementaria (preexistente, **no tocada**) | `0a61e9e7533acc114b5631d98e15be36c19d6678b6523a419c4bea1abcf19180` |
| `ADENDA_FINAL_PRECISION_DOCUMENTAL_R6-R4.md` | **Esta fase** (nueva) | se informa en la entrega (§9) |

### 7.3 Confirmación expresa: no se ejecutaron pruebas ni se modificaron archivos anteriores

| Verificación | Resultado |
|---|---|
| Ejecución del arnés (`main()`, `run_controller()`, baterías) | **Ninguna** |
| Importación de módulos del arnés | **Ninguna** |
| Repetición de pruebas / generación de evidencias | **Ninguna** |
| Recálculo de los tres hashes | **No realizado** (§5.1) |
| Modificación de los tres JSON o de sus copias | **No se accedió a ellos** |
| Modificación de los tres documentos anteriores | **Ninguna** — SHAs idénticos a los registrados (§7.2) |
| Modificación de código o archivos versionados | **Ninguna** — arnés en `0cbba1ba7facc990ace21cc631fec55066b308857737d883bf25665f90dcaf18`; informe de evidencia en `31201d369c6a3a568f5e39ee77603411fb19c2144416103d3f489bc1ff0811db` |
| D18-R1 `C5` histórico | **No ejecutado** |
| `_mmap.close()` con referencias vivas | **No utilizado** |
| R6-R5 / Hardened / producción / audio real | **No iniciados** |
| `__pycache__` generado | **Ninguno** |

### 7.4 PR

| PR | Estado |
|---|---|
| **PR #3** — https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3 | **Abierto. Sin fusionar. No modificado.** |
| **PR #4** — https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4 | **Abierto. Sin fusionar. No modificado.** |

---

## 8. Enlaces de GitHub

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Rama y HEAD (`0ae2c10`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit funcional R6-R4 (`bbc1aab`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/bbc1aab50ab1487f81c03697a7f10390088302e5
- Arnés R6-R4 en HEAD (`EVIDENCE_DIR`, línea 227): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Lanzador con patrón documentado (`pruebas_h2_6g1.py`, líneas 94-99 y 388-392): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_h2_6g1.py
- Informe de evidencia D18-R2: https://github.com/arielwilliam1986-source/SDV-SDI_SGM/blob/0ae2c10c472e2e9941320fa1dd2727f1a044701c/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- PR #3 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3
- PR #4 (abierto, sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/4

---

## 9. Nota sobre el SHA-256 de este documento

El valor se calcula **después** de escribir el archivo y se informa en la entrega, no dentro del propio archivo, porque un documento no puede contener su propio hash de forma autorreferente sin invalidarlo.

---

**Fin de la adenda final. No se ejecutaron pruebas. No se modificó código, archivo versionado, JSON ni documento anterior. No se recalculó ningún hash. No se creó ningún commit ni rama. No se alteró ningún veredicto `UNKNOWN`. Se espera revisión de Cris y autorización del usuario.**
