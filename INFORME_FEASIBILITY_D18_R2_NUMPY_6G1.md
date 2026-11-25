# FEASIBILITY-D18-R2 + R1..R6 + R6-R1 + R6-R3 + R6-R4 — CICLO DE VIDA SEGURO DE NUMPY.MEMMAP Y CORRECCIÓN DE ENUMERACIÓN DE DESCRIPTORES (PRIORIDAD ANDROID/TERMUX)

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena (sesión R6-R3 `arena/83102fa6-sdv-sdi-sgm`, PR #3 abierto hacia `arena/9a32cda8-sdv-sdi-sgm`; sesión R6-R4 `arena/a2d9ac2e-sdv-sdi-sgm`, rama independiente con PR nuevo separado del PR #3, ver §13).
- **Naturaleza:** validación empírica **aislada** del ciclo de vida **seguro** de `numpy.memmap` (liberación de recursos **sin** invocar `arr._mmap.close()` mientras existan arrays/vistas vivas) junto con la corrección de enumeración de descriptores en `fds_with_identity()` autorizada en **R6-R3**. **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #1 y PR #2 intactos.
- **Prioridad de plataforma (R6-R3):**
  1. **Prioridad 1 — Android/Termux:** objetivo principal de diseño y portabilidad del proyecto (base Python `3.11` / NumPy `1.26.4` y entorno objetivo `/data/data/com.termux/files/home/SDV-SDI_SGM`). **Importante:** en este sandbox solo existe entorno Linux x86_64; **no se dispone de runtime Android/Termux real**, por lo que la portabilidad Android/Termux se razona y documenta técnicamente y su ejecución real queda pendiente de validación directa en dispositivo Termux (§3 y §9).
  2. **Prioridad 2 — Linux:** entorno auxiliar de desarrollo, diagnóstico empírico (`LD_PRELOAD`) y regresión ejecutado en esta sesión (`Linux 6.1.158+ x86_64`, glibc `2.36`, Python `3.11.2`).
  3. **Fuera de alcance:** Windows.
- **Alcance de ESTA entrega (R6-R3 sobre R6-R1):**
  - Sustituye `os.listdir()` en `fds_with_identity()` por enumeración e inspección **en línea** mediante `with os.scandir(scan_target) as it:`, eliminando el cierre prematuro del descriptor de enumeración antes de `os.stat()` (origen demostrado en R6-R2 del falso `ENOENT` en `/proc/self/fd`), **sin** `list(it)`, **sin** filtrar descriptores por número, **sin** ignorar `ENOENT` y **sin** `ctypes`/syscalls/ABI dependiente de arquitectura.
  - Conserva íntegramente `R4-A`, `R4-B`, `R5-A`, `R6` (inyección real de fallo de cierre en `R2-C13`), `R6-R1` (`adjudicate_r2c13_verdict` + `R2-C14`), clasificación conservadora `R3-D`, precedencia `FAIL > UNKNOWN > PASS` y el hallazgo histórico `C5 = FAIL` de `FEASIBILITY-D18-R1`.
- **Veredicto global R2+R1..R6+R6-R1+R6-R3 (histórico, preservado):** **UNKNOWN** en Linux (precedencia `FAIL > UNKNOWN > PASS`). **30 PASS · 0 FAIL · 9 UNKNOWN** (39 subpruebas; 10/10 ejecuciones idénticas). Todos los escenarios reales que dependían del inventario completo de `/proc/self/fd` (`A1`, `B1`, `B2`, `B5`, `C-A`, `C-B`, `C-C`, `R2-C8`, `R2-C13`) pasan a `PASS` al desaparecer el falso `ENOENT` de `os.listdir()`, mientras que los 9 `UNKNOWN` conservados corresponden estrictamente a casos diseñados para ser `UNKNOWN` (referencia retenida `B6/D1/D2`, desapariciones/permisos controlados `R2-C2/R2-C3`, ausencia de fallo real de `procfs` en `R2-C5`, y pruebas `R1-A3/A4/B2`).
- **Veredicto global R6-R3 en Android/Termux (histórico, preservado):** **FAIL**. **29 PASS · 1 FAIL · 9 UNKNOWN**. Único `FAIL`: `R2-C9`, por la expectativa de enumeración tras eliminar el directorio (ver §13). **No se presenta retroactivamente este `FAIL` como `PASS`.**
- **Veredicto R6-R4 (esta entrega):** corrección metodológica de `R2-C9` por identidad `fstat` (§13). En Linux Arena se ejecutaron de forma aislada `R2-C9` (corregida), `R2-C8`, `R2-C12` y `R2-C14`: **4 PASS · 0 FAIL · 0 UNKNOWN** en esa selección aislada. **No se declara nuevo veredicto global completo de 39 subpruebas ni `D18-R2` global `PASS`**: la batería completa requiere `numpy==1.26.4` (no instalado en Arena, ver §13.4) y la validación definitiva en Android/Termux real. `C5` histórico `FAIL` permanece intacto; **D18 sigue `FAIL`**.

---

## 1. Commit padre exacto

- **Padre obligatorio de R6-R3:** `8487d9cdd54c9f5e584cec5b1a788c891f00aed5` (FEASIBILITY-D18-R2-R6-R1, hijo directo de `779485acf4b9116a2f1e055f320382beb2c51799` FEASIBILITY-D18-R2-R6, que a su vez es hijo directo de `ac82b6c3cc46f6f5202c1a14c4aa70c7a67c87e2` FEASIBILITY-D18-R2-R5).
- Verificado ANTES de trabajar: `HEAD = 8487d9cdd54c9f5e584cec5b1a788c891f00aed5`, rama activa `arena/83102fa6-sdv-sdi-sgm`, árbol limpio (`git status --porcelain` vacío), rama destino `arena/9a32cda8-sdv-sdi-sgm` apuntando en GitHub a `ac82b6c3cc46f6f5202c1a14c4aa70c7a67c87e2`, y PR #3 abierto y sin fusionar. **TODO CONFORME**.
- **Secuencia en PR #3 desde base R5 (`ac82b6c3...`):** **3 commits** (`R6 = 779485a...` + `R6-R1 = 8487d9c...` conservados intactos + **1 único commit R6-R3** hijo directo de `8487d9c...`); **exactamente 2 archivos modificados** (los dos autorizados).

## 2. Archivos modificados (exactamente los 2 autorizados, ambos existentes)

| Archivo | Rol | Cambio en R6-R3 |
|---|---|---|
| `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` | Arnés R2+R1..R6+R6-R1+R6-R3+R6-R4 (39 subpruebas) | **R6-R3:** sustituye `_enumerate_fd_dir()`/`os.listdir()` en `fds_with_identity()` por enumeración e inspección en línea `with os.scandir(...)`, añade `_supports_anchored_scandir()` con fallback explícito `"path"`, actualiza mocks/verificaciones `R2-C2` (Caso B en FS regular y `/proc/self/fd` real), `R2-C6`, `R2-C7`, `R2-C8` (Caso A), `R2-C11` (`os.scandir(dirfd)`) y `R2-C13`. **R6-R4:** reescribe exclusivamente `test_r2c_persistent_dirfd()` (`R2-C9`) por identidad `fstat` sin `os.listdir`/`os.scandir` tras la eliminación; actualiza docstring del módulo y registro `main()`/`scope`/`r6_r4_correction` (documentación estrictamente necesaria). No modifica `fds_with_identity()`, `_supports_anchored_scandir()`, controladores ni ninguna otra prueba |
| `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` | Este informe | Documenta el origen R6-R2, la solución R6-R3, análisis completo de portabilidad Android/Termux, separación ejecución Linux vs pendiente en dispositivo real, recuentos históricos R6-R3 (`30 PASS · 0 FAIL · 9 UNKNOWN` en Linux; `29 PASS · 1 FAIL · 9 UNKNOWN` en Android/Termux) y trazabilidad. **R6-R4 (§13):** añade cronológicamente el `FAIL` histórico de `R2-C9` en Termux, la explicación técnica, el cambio metodológico y los resultados aislados R6-R4 en Linux, sin borrar ni reemplazar los resultados R6-R3 |

Evidencia JSON cruda: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera en `/tmp`; el arnés la regenera). Entorno Python efímero: `/tmp/feas_d18_venv` (`numpy==1.26.4`). Artefactos de diagnóstico temporal fuera del repositorio en `/tmp/r6_r2_diag/` (no versionados). SHA-256 de los dos archivos en el mensaje de commit y en la entrega a Cris.

## 3. Entorno ejecutado y análisis de portabilidad Android/Termux

### 3.1 Entorno efectivamente ejecutado (Linux auxiliar)

| Componente | Valor medido |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (`x86_64`) |
| Python | `3.11.2` (`os.scandir in os.supports_fd == True`, `os.stat in os.supports_dir_fd == True`) |
| NumPy | `1.26.4` |
| libc | `glibc 2.36` |
| Android/Termux en sandbox | **NO disponible** (ninguna ejecución real en dispositivo Android/Termux en esta sesión) |

### 3.2 Auditoría técnica de `os.scandir(dirfd)` con prioridad Android/Termux

1. **Disponibilidad en Python:** `os.scandir(path='.')` acepta un descriptor abierto (`int`) desde **Python 3.7** siempre que la compilación POSIX disponga de `HAVE_FDOPENDIR` (verificado en tiempo de ejecución mediante `os.scandir in os.supports_fd` y `os.stat in os.supports_dir_fd`). La línea base del proyecto es **Python 3.11** (`ETAPA_6G1_CORRECCION_LECTURA_SEGURA/README.md`).
2. **Respaldo en Android/Termux (Bionic libc):** en CPython (`Modules/posixmodule.c`), `os.scandir(dirfd)` duplica el descriptor vía `fcntl(dirfd, F_DUPFD_CLOEXEC, 0)` (o `dup()`), abre el flujo de directorio mediante `fdopendir(dup_fd)` y lee entradas con `readdir()` hasta agotamiento o `ScandirIterator.close()` (`closedir()`). En Android, `fdopendir()`, `readdir()` y `closedir()` forman parte estable de **Bionic libc** (desde API 15; Termux opera sobre API 24+, `aarch64`/`arm`/`x86_64`). No requiere `ctypes`, `libc.so` ni llamadas directas al kernel.
3. **Diferencias ARM64 (`aarch64`) vs `x86_64`:** utilizar `os.scandir(dirfd)` y `os.stat(name, dir_fd=dirfd)` encapsula completamente en CPython/Bionic la numeración de syscalls (`__NR_getdents64` = `61` en `aarch64` vs `217` en `x86_64`; `openat` vs `open`) y el alineamiento/tamaño de `struct dirent`/`struct stat`, evitando cualquier fragilidad ABI que tendría un camino con `ctypes` o `syscall()`.
4. **Ciclo de vida y propiedad de descriptores:**
   - `os.open(fd_dir, os.O_RDONLY | os.O_DIRECTORY)` abre `dirfd` bajo propiedad de `fds_with_identity()`.
   - `with os.scandir(dirfd) as it:` crea internamente `dup_fd` + `DIR*` (`fdopendir(dup_fd)`), lo mantiene **abierto durante toda la iteración** mientras `os.stat(entry.name, dir_fd=dirfd)` inspecciona cada entrada en el cuerpo del bucle `for entry in it:`, y lo cierra deterministamente al salir del bloque `with` (incluyendo ante `break` o `OSError` a mitad de iteración; verificado en Linux: `before=8 -> during=9 -> after=8`).
   - La traza `LD_PRELOAD` confirma exactamente: `open64("/proc/self/fd") = 3` → `fcntl64(3, F_DUPFD_CLOEXEC) = 5` → `fdopendir(5)` → intercalado `readdir64(5) -> '5'` seguido inmediatamente por `fstatat64(3, "5") = 0` mientras `fd=5` sigue abierto → al agotar todas las entradas, `closedir(5)` → `close(3)` en `finally`.
   - `dirfd` se cierra inmediatamente en `except OSError` si falla `os.scandir(dirfd)` o su iteración (`R4-A`), o al finalizar en `finally` registrando cualquier fallo de `os.close(dirfd)` en `phase="cierre"` sin reintentos ciegos (`R5-A`).
5. **Dependencias de `/proc/self/fd` y permisos en Android/Termux:**
   - En Android/Termux, la lectura de `/proc/self/fd` dentro del propio proceso suele estar permitida para el UID de la aplicación Termux, pero depende de la política SELinux del fabricante/ROM (`untrusted_app` vs shell ADB) y de opciones de montaje `proc` (`hidepid`).
   - Si en un dispositivo concreto `os.open("/proc/self/fd", O_RDONLY | O_DIRECTORY)` o `os.scandir(...)` devuelve `EACCES`/`EPERM`, o `os.scandir not in os.supports_fd`, `fds_with_identity()`:
     - cae al modo `"path"` no anclado si solo falló `O_DIRECTORY` / `supports_fd` (sin atribuir garantías de `dirfd`), y
     - si falla `os.scandir` o `os.stat` en cualquier entrada, marca `complete=False`, clasifica conservadoramente y fuerza **`UNKNOWN`** (nunca `PASS` silencioso).
6. **Validación pendiente en dispositivo Termux real:** como no hay runtime Android en este sandbox, quedan pendientes de ejecución directa en el dispositivo Termux objetivo (`/data/data/com.termux/files/home/SDV-SDI_SGM`): (a) ejecución completa de `arnes_feasibility_d18_r2_numpy_6g1.py` con `-B`; (b) verificación de `R2-C8`, `R2-C2` (Caso B), `R2-C12` y `R2-C13` sobre el `procfs` y SELinux reales de Android; (c) comprobación de Bionic `fdopendir`/`readdir` en `/proc/self/fd`; y (d) verificación específica de comportamiento de `mmap`/`munmap` y `/proc/self/maps` en ARM64 (incluyendo dispositivos con tamaño de página de 16 KB si aplica).

## 4. Correcciones metodológicas (incluyendo diagnóstico R6-R2 y corrección R6-R3)

### R1..R6-R1 (fases previas, conservadas íntegramente)
- **R1-A/B/C/D, R2-A/B, R3-A..F:** lectura completa/incompleta/ilegible de `/proc/self/maps`, captura y clasificación conservadora de errores en `fds_with_identity()`, propagación de `UNKNOWN`, ausencia de `FAIL` artificial, `C5` histórico conservado, sin `_mmap.close()` forzado y sin atribuir garantías universales a `gc.collect()`.
- **R4-A/B, R5-A:** cierre garantizado de `dirfd` si falla la enumeración (`R4-A`), inspección anclada relativa a `dirfd` mediante `os.stat(name, dir_fd=dirfd)` (`R4-B`), y registro sin descarte ni reintentos ciegos si falla el `os.close(dirfd)` final (`R5-A`).
- **R6 / R6-R1:** controlador real `run_controller()` / `aggregate_verdicts()` compartido entre `main()` y `R2-C13`, inyección real de `os.close(dirfd)` sobre los 7 escenarios reales A/B/C conservando `id(inv)` intacto, adjudicación local estricta `FAIL > UNKNOWN > PASS` en `adjudicate_r2c13_verdict(...)` y matriz reproducible `R2-C14`.

### Diagnóstico R6-R2 y Corrección R6-R3 (causa raíz del falso `fd 3/5/6/9/10` y resolución)
1. **Causa raíz probada (R6-R2, no era fallo del sandbox):**
   - `os.listdir("/proc/self/fd")` ejecuta en CPython `opendir()` (abriendo el menor fd libre, típicamente `3`), lee la lista con `readdir64()` (registrando el propio `3` aún abierto) y llama `closedir()` **antes de retornar**.
   - `os.open("/proc/self/fd") + os.listdir(dirfd)` ejecuta `fcntl64(dirfd, F_DUPFD_CLOEXEC, 0)` → `dup_fd` (`min(free_fd > dirfd)`, p.ej. `5`/`6`/`9`/`10`), `fdopendir(dup_fd)`, `readdir64()` (registrando `dup_fd`) y `closedir(dup_fd)` **antes de retornar**.
   - Cuando el bucle posterior de `fds_with_identity()` ejecutaba `os.stat(name, dir_fd=dirfd)` sobre la entrada del propio `dup_fd` ya cerrado, el kernel devolvía deterministamente **`ENOENT (errno=2)`** sin entrada en `/proc/self/fdinfo`. Repeticiones en R6-R2: `os.listdir(path)` `50/50` `ENOENT`, `os.listdir(dirfd)` `50/50` `ENOENT`, incluso en subprocesos limpios con `close_fds=True` (`10/10` `'4'`).
2. **Solución implementada en R6-R3 (`fds_with_identity()`):**
   - Elimina `_enumerate_fd_dir()` (que retornaba `names` materializados) e integra la enumeración e inspección **en el mismo bloque**:
     - Comprueba `_supports_anchored_scandir()` usando las referencias nativas `_REAL_OS_SCANDIR` y `_REAL_OS_STAT` en `os.supports_fd` / `os.supports_dir_fd` (de modo que wrappers de prueba sobre `os.stat`/`os.scandir` no desactiven el modo `"dirfd"`, manteniendo comprobación dinámica de `os.supports_fd`/`os.supports_dir_fd`).
     - Si el soporte está disponible y `os.open(fd_dir, os.O_RDONLY | os.O_DIRECTORY)` tiene éxito, entra en `with os.scandir(dirfd) as it:` e inspecciona cada `entry` con `os.stat(entry.name, dir_fd=dirfd)` **dentro del bucle** antes de agotar el iterador. En modo `"path"` (fallback explícito), usa `with os.scandir(fd_dir) as it:` y `os.stat(os.path.join(fd_dir, entry.name))`.
     - Ante cualquier `OSError` en `os.scandir` o en su iteración (`except OSError`), cierra `dirfd` vía `_close_dirfd(dirfd)` (`R4-A`), registra `phase="enumeracion"` y retorna `complete=False`.
     - En `finally`, cierra `dirfd` registrando cualquier error en `phase="cierre"` (`R5-A`).
3. **Reglas de integridad verificadas (prohibiciones respetadas al 100%):**
   - **Prohibido ignorar `ENOENT`:** verificado en `R2-C2` Subcaso B1 (FS regular → `DESCRIPTOR_DESAPARECIDO`) y Subcaso B2 (`/proc/self/fd` real con cierre concurrente de `victim_fd` → `ENOENT`, `UNKNOWN_CAUSE`, `complete=False`).
   - **Prohibido filtrar descriptores por número o autoexcluir el iterador:** `fds_with_identity()` inspecciona sin exclusiones todas las entradas devueltas por `ScandirIterator`.
   - **Prohibido `list(it)`:** el bucle consume directamente `for entry in it:` manteniendo el `DIR*` abierto hasta el final del bucle.
   - **Actualización de pruebas dependientes de `os.listdir` (`R2-C2`, `R2-C6`, `R2-C7`, `R2-C8`, `R2-C11`, `R2-C13`):**
     - `R2-C2`: elimina el mock de `os.listdir` estancado; prueba Caso B1 (`os.scandir` real + `os.unlink('5')` justo antes de `os.stat`) y Caso B2 (`/proc/self/fd` real abriendo `victim_fd` y cerrándolo durante el primer `os.stat` distinto a `victim_fd`) → verifica detección real del único `ENOENT` esperado y clasificación conservadora → `UNKNOWN`.
     - `R2-C6`: usa `os.scandir` real + `os.unlink('3')` antes de `os.stat` → `complete=False` → A/B/C = `UNKNOWN` → `PASS`.
     - `R2-C7`: inyecta `OSError(EIO)` en `os.scandir` tanto en apertura como a mitad de iteración (`next(it)`) → P1 no propaga y P2 controlador asigna `UNKNOWN` → `PASS`.
     - `R2-C8`: demuestra la reproducción en comparadores (`os.listdir(path)` 3/3 con `'3'` `ENOENT` y `os.listdir(dirfd)` 1/1 con `'5'` `ENOENT`) frente a `fds_with_identity()` con `os.scandir(dirfd)` en línea (**Caso A**: `enum_mode="dirfd"`, `complete=True`, `errors=[]`) → `PASS`.
     - `R2-C11`: adapta la inyección de `OSError(EIO)` a `os.scandir(dirfd)` (apertura y mitad de iteración) + fallo de `os.close(dirfd)` (`"cierre fallido"` en `note`, limpiando al final cualquier fd retenido por el mock) → `leaked=[]`, `complete=False` → `PASS`.
     - `R2-C13`: con la corrección R6-R3 activa, Etapa 2 aísla `phase='cierre'` (`errno=9`) como **causa única** (`13/13` llamadas en A/B/C, 0 errores en `inspeccion`, `7/7 UNKNOWN`) y Etapa 3 (contraste real A/B/C sobre `/proc/self/fd` sin fallo de cierre) logra **`13/13 complete=True` y `7/7 PASS`** (`con_global='PASS'`), por lo que `adjudicate_r2c13_verdict(...)` devuelve **`PASS`**.

## 5. Resultados individuales (39 subpruebas)

### R2-A — Liberación de referencias

| ID | Título | maps / fds vivo→muerto | Veredicto |
|---|---|---|---|
| A1 | Raíz sin vistas | 1→0 (maps); fd vivo→`[]` (`complete=True`) | **PASS** |
| A2 | Raíz + slice | 1→1→0 | PASS |
| A3 | Vistas encadenadas | 1→1→1→0 | PASS |
| A4 | Contenedores | 1→1→0 | PASS |
| A5 | Referencia exportada | 1→1→0 | PASS |
| A6 | Liberación progresiva | 1→1→1→0 | PASS |

**Conclusión A:** con la corrección R6-R3, A1 acredita completamente tanto `/proc/self/maps` (`1→0`) como el inventario de `/proc/self/fd` (`complete=True`, `[]` residuales) cuando todas las referencias se liberan y corre `gc.collect()`.

### R2-B — Cierre seguro (sin `_mmap.close()`)

| ID | Título | maps / fds | Veredicto |
|---|---|---|---|
| B1 | Secuencia segura, raíz | 1→0; fds `complete=True`, residuales `[]` | **PASS** |
| B2 | Con vistas | 1→0; fds `complete=True`, residuales `[]` | **PASS** |
| B3 | Recolección controlada | 1→0 | PASS |
| B4 | Todas las entradas por (dev,ino) | 1→0 | PASS |
| B5 | Fds residuales y propiedad (ruta) | fd vivo→`[]` (`complete=True`) | **PASS** |
| B6 | Referencia externa viva | maps persiste | **UNKNOWN** (referencia retenida, por diseño) |

**Conclusión B:** cuando todas las referencias se liberan + `gc.collect()`, B1, B2 y B5 acreditan desaparición del mapping y cierre del fd duplicado (`complete=True`, 0 residuales) sin `SIGSEGV`. Si persiste cualquier referencia externa viva (B6), la liberación sigue sin poder acreditarse → **UNKNOWN** por diseño.

### R2-C — Alternativas A/B/C (cierre seguro, diferenciando fds)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| C-A | fd motor + magic-link | fd motor abierto; dup cerrado (`complete=True`) | **PASS** |
| C-B | NumPy por ruta | solo dup de NumPy cerrado (`complete=True`) | **PASS** |
| C-C | fileobj entregado | fd fileobj abierto; dup cerrado (`complete=True`) | **PASS** |

**Conclusión C (observado, no inferido):** en A/B/C el **único** recurso que cierra el camino seguro es el fd duplicado interno del objeto `mmap`, vía su finalizador. El fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor; B no tiene fd_mm.

### R2-D — Fallos y excepciones

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| D1 | Liberación incompleta (vista retenida) | maps persiste | **UNKNOWN** |
| D2 | Referencia retenida impide acreditar | maps persiste | **UNKNOWN** |
| D3 | Flush no bloquea la liberación | flush persiste; sin flush→maps=0 | PASS |
| D4 | Cierre seguro sin errores | `del arr; gc` → sin excepción, maps=0 | PASS |

### R2-C controladas (obligatorias, R2-C1..R2-C14)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R2-C1 | Inventario COMPLETO de fds | `complete=True; matched=[3]; errors=[]; enum_mode='dirfd'` | PASS |
| R2-C2 | Entrada que desaparece durante el recorrido (Caso B) | B1 (dir sintético, `os.scandir` real + `unlink('5')`): `DESCRIPTOR_DESAPARECIDO`, `errno=2`, `complete=False`. B2 (`/proc/self/fd` real + cierre concurrente de `victim_fd=5`): `closed_victim=True`, único error `'5'`, `ENOENT`, `UNKNOWN_CAUSE`, `complete=False` | **UNKNOWN** |
| R2-C3 | Entrada inaccesible (permisos) | `complete=False`; `DESCRIPTOR_INACCESIBLE`, `errno=13`, `PermissionError`, `'9'` | **UNKNOWN** |
| R2-C4 | Error de enumeración del directorio | no propaga; `complete=False`; `phase=enumeracion`; `/proc` → `ERROR_PROCFS`, no-procfs → `UNKNOWN_CAUSE` | PASS |
| R2-C5 | Error de procfs durante la inspección (R3-C) | mecánica unitaria 4/4 correcta; inventario real `/proc/self/fd` `complete=True, errors=0` → **sin evidencia real** de `ERROR_PROCFS` en este entorno → **UNKNOWN** honesto | **UNKNOWN** |
| R2-C6 | Propagación de UNKNOWN a escenarios dependientes | `os.scandir` real + `unlink('3')` antes de `os.stat` → `complete=False` → A/B/C = UNKNOWN | PASS |
| R2-C7 | Sin FAIL artificial (R3-A) | `OSError(EIO)` en `os.scandir` (apertura y mid-iter): P1 no propaga = True; P2 controlador → UNKNOWN = True | PASS |
| R2-C8 | Origen del descriptor fantasma y eliminación Caso A (R6-R2/R6-R3) | Comparadores `os.listdir(path)` (3/3 `'3'` `ENOENT`) y `os.listdir(dirfd)` (1/1 `'5'` `ENOENT`) vs `fds_with_identity()` con `os.scandir(dirfd)` en línea: `enum_mode='dirfd'`, `complete=True`, `errors=[]` | **PASS** |
| R2-C9 | Descriptor de directorio mantenido abierto **(R6-R3, histórico Linux)** | `dirfd` estable/identificable; tras borrado externo, ruta falla y `dirfd` no; `enum_mode='dirfd'` | PASS (Linux R6-R3) / **FAIL (Android/Termux R6-R3, ver §13)** |
| R2-C9 | Descriptor mantenido tras eliminar su ruta: identidad por `fstat` **(R6-R4, nueva definición)** | `open_ok=True; dev_before=65024; ino_before=529127; path_gone=True; dev_after=65024; ino_after=529127; fstat_after_ok=True; identity_same=True; close_ok=True` (Linux Arena, ejecución aislada) | **PASS (Linux Arena aislado, ver §13)** |
| R2-C10 | Propagación en escenarios REALES A/B/C (R3-E) | incompleto → `UNKNOWN` en A1/B1/B5/C-B; completo → A1/B1/C-B = `PASS` (B5 = `FAIL` con `matched=[]` simulado, sin cambio) | PASS |
| R2-C11 | Cierre de dirfd ante error de enumeración (R4-A) | fallo en apertura y mid-iter de `os.scandir(dirfd)`: `leaked=[]`, `complete=False`, `phase='enumeracion'`; fallo de cierre registrado (`"cierre fallido"`) | PASS |
| R2-C12 | Inspección relativa al dirfd vs recorrido por ruta (R4-B) | modo `dirfd`: `inspecciones_ancladas=[('5', 3)]`, `inspecciones_por_ruta=[]`, `descriptor_cerrado=True`; modo `path`: no anclado | PASS |
| R2-C13 | Propagación real del fallo de cierre final de dirfd en A/B/C y controlador (R5-B/R6/R6-R1) | Etapa 1 (`fd_dir=d`): `dirfd`+cierre+`phase='cierre'` (`errno=9`)+contraste limpio (`complete=True`). Etapa 2 (7 escenarios A/B/C vía `run_controller`, 13 llamadas con `id(inv)` único): **causa única** `error_phases=['cierre']`, `error_errnos=[9]`, `7/7 UNKNOWN`, `global=UNKNOWN`. Etapa 3 (contraste real `/proc/self/fd` sin fallo `close`): **`13/13 complete=True`**, `0` errores, `7/7 PASS`, `con_global='PASS'` → `adjudicate_r2c13_verdict()` | **PASS** |
| R2-C14 | Regresión de precedencia local `FAIL > UNKNOWN > PASS` de R2-C13 (R6-R1) | `run_controller()` + `adjudicate_r2c13_verdict()` en 8 casos: `all_ok=True` (8/8) | PASS |

### R1 controladas (conservadas)

| ID | Título | Observado | Veredicto |
|---|---|---|---|
| R1-A1 | Lectura COMPLETA con coincidencia | status=complete; recuento=1 | PASS |
| R1-A2 | Lectura COMPLETA sin coincidencia | status=complete; recuento=0 | PASS |
| R1-A3 | Coincidencia + líneas no interpretables | status=incomplete | **UNKNOWN** |
| R1-A4 | `/proc/self/maps` no disponible/ilegible | status=unreadable | **UNKNOWN** |
| R1-B1 | Inventario COMPLETO de /proc/self/fd | complete=True; matched=[3]; errors=[] | PASS |
| R1-B2 | Inventario INCOMPLETO (/proc/self/fd con error) | complete=False; error registrado | **UNKNOWN** |

## 6. Conteos, comparativa R6-R1 → R6-R3 y repetibilidad

```
Subpruebas: 39 (19 R2 + 14 R2-C controladas + 6 R1 controladas)
Conteos:    PASS=30 FAIL=0 UNKNOWN=9
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): UNKNOWN
Repetibilidad verificada (R6-R3): 10/10 ejecuciones idénticas
  - 5 ejecuciones con fds heredados del shell/runner
  - 5 ejecuciones con subprocess(close_fds=True)
```

Desglose de `PASS` (30):
- R2-A: `A1, A2, A3, A4, A5, A6` (6)
- R2-B: `B1, B2, B3, B4, B5` (5)
- R2-C alt: `C-A, C-B, C-C` (3)
- R2-D: `D3, D4` (2)
- R2-C controladas: `R2-C1, R2-C4, R2-C6, R2-C7, R2-C8, R2-C9, R2-C10, R2-C11, R2-C12, R2-C13, R2-C14` (11)
- R1 controladas: `R1-A1, R1-A2, R1-B1` (3)

Desglose de `UNKNOWN` (9):
- `B6` (referencia externa viva retenida), `D1`, `D2` (liberación incompleta / vista retenida)
- `R2-C2` (Caso B: desaparición real en FS regular y en `/proc/self/fd` → clasificación verificada + `complete=False`)
- `R2-C3` (entrada inaccesible `EACCES` → clasificación verificada + `complete=False`)
- `R2-C5` (mecánica `ERROR_PROCFS` correcta, sin error real `ERROR_PROCFS` en el entorno)
- `R1-A3`, `R1-A4`, `R1-B2` (lectura de maps / inventario fd incompletos por diseño)

**Evolución respecto a R6-R1 (`21 PASS · 0 FAIL · 18 UNKNOWN`):**
- Transicionan de `UNKNOWN` → `PASS` **9 subpruebas** por la eliminación del falso `ENOENT` de `os.listdir()`: `A1`, `B1`, `B2`, `B5`, `C-A`, `C-B`, `C-C`, `R2-C8` (Caso A resuelto tras demostrar origen y eliminación) y `R2-C13` (Etapa 3 contraste real A/B/C `13/13 complete=True` y `7/7 PASS` aislando el fallo de `os.close(dirfd)` como causa única en Etapa 2).
- Ningún veredicto fue forzado artificialmente: `R2-C5` sigue en `UNKNOWN` (al no haber fallo real de `procfs` en el entorno), `R2-C2` sigue en `UNKNOWN` (probando además Caso B real sobre `/proc/self/fd`) y `C5 = FAIL` histórico de D18-R1 permanece intacto.

## 7. Hallazgos (observado vs garantía documentada vs hipótesis)

1. **Ciclo de vida seguro VIABLE vía referencias + `gc` (observado CPython 3.11.2 / NumPy 1.26.4 Linux):** al desaparecer el falso `ENOENT` de `os.listdir()`, los escenarios `A1`, `B1`, `B2`, `B5`, `C-A`, `C-B`, `C-C` acreditan simultáneamente `maps` (`1→0`) y `/proc/self/fd` (`complete=True`, 0 fds residuales) sin `SIGSEGV` cuando se sueltan todas las referencias y se ejecuta `gc.collect()`. Sigue siendo **observación de comportamiento** en CPython 3.11.2 / NumPy 1.26.4 Linux, **NO** garantía universal ni validación en dispositivo Android/Termux.
2. **Cierre del fd duplicado interno por el finalizador, NO por el motor:** el fd propio del motor (A vía magic-link, C vía fileobj) **no** lo cierra NumPy y **debe** cerrarlo el motor.
3. **Condición de seguridad (hipótesis de diseño):** liberar **todas** las referencias y conservar inventario completo; cualquier referencia olvidada (`B6/D1/D2`) o inventario incompleto impide acreditar el cierre → `UNKNOWN`.
4. **Resolución del antiguo artefacto `fd 3/5/6/9/10` (R6-R2 + R6-R3, hecho demostrado):** la entrada no estadizable de `/proc/self/fd` **no** era emulación defectuosa de `e2b` sino el descriptor propio de `os.listdir()` (`opendir` o `F_DUPFD_CLOEXEC`) cerrado con `closedir()` antes de retornar. Al reemplazar `os.listdir()` por `with os.scandir(dirfd) as it:` + inspección en línea (`os.stat(entry.name, dir_fd=dirfd)`), `dup_fd` sigue vivo durante todo el bucle y `/proc/self/fd` alcanza `complete=True, errors=[]` (**Caso A**), manteniendo intacta la detección real de `ENOENT` concurrentes (**Caso B** en `R2-C2`).
5. **Ciclo de vida y anclaje (`R4-A`, `R4-B`, `R5-A`, `R6`, `R6-R1`):** todos preservados íntegramente bajo `os.scandir(dirfd)`. En `R2-C13`, Etapa 2 ahora aísla `error_phases=['cierre']` (`errno=9`) como causa única en las 13 llamadas y Etapa 3 logra `13/13 complete=True` y `7/7 PASS`.
6. **`C5` se conserva (histórico):** `arr._mmap.close()` con array vivo ⇒ `SIGSEGV` (3/3) sigue siendo el fallo independiente de `FEASIBILITY-D18-R1`.

## 8. Hechos observados · hipótesis · UNKNOWN

- **HECHOS OBSERVADOS (en Linux 6.1.158+ x86_64, Python 3.11.2, NumPy 1.26.4):**
  - `os.listdir("/proc/self/fd")` y `os.listdir(dirfd)` cierran su descriptor de enumeración antes de retornar, produciendo `ENOENT` determinista (`50/50`) al inspeccionar después.
  - `with os.scandir(dirfd) as it:` mantiene abierto `dup_fd` (`fdopendir`) durante todo `for entry in it:` hasta que termina o sale del `with` (`closedir(dup_fd)` posterior a todas las `fstatat64(dirfd, name)`), eliminando el falso `ENOENT` (**Caso A**: `R2-C8 = PASS`, `A1/B1/B2/B5/C-A/C-B/C-C = PASS`).
  - Una desaparición real entre enumeración e inspección sigue fallando en `os.stat(..., dir_fd=dirfd)` con `ENOENT` tanto en FS regular (`DESCRIPTOR_DESAPARECIDO`) como cerrando `victim_fd` en `/proc/self/fd` real (`UNKNOWN_CAUSE`, `complete=False`) (**Caso B**: `R2-C2`).
  - Ante fallo en apertura o mitad de iteración de `os.scandir(dirfd)`, `dirfd` se cierra sin fugas (`R2-C11 = PASS`), modo `dirfd` inspecciona relativo al descriptor mientras modo `path` es no anclado (`R2-C12 = PASS`), el fallo final de `os.close(dirfd)` se aísla como causa única con contraste real A/B/C `7/7 PASS` (`R2-C13 = PASS`), y `adjudicate_r2c13_verdict()` cumple `8/8` (`R2-C14 = PASS`).
  - 10/10 ejecuciones repetidas (5 estándar + 5 con `close_fds=True`) producen exactamente `30 PASS · 0 FAIL · 9 UNKNOWN`, `global_verdict = UNKNOWN`.
- **HIPÓTESIS DE PORTABILIDAD / DISEÑO (razonadas, pendientes de verificación en dispositivo Android/Termux real):**
  - Dado que `os.scandir(dirfd)` se basa en POSIX/Bionic `fdopendir`/`readdir`/`closedir` disponible desde Python 3.7 (baseline proyecto 3.11) y Android API 15+ (Termux API 24+), debería funcionar de forma equivalente entre `aarch64` (ARM64) y `x86_64` sin fragilidad de syscalls ni ABI, salvo restricciones específicas de `/proc/self/fd` por SELinux/`hidepid` o particularidades de `mmap`/`gc` en ARM64/16 KB page size.
- **UNKNOWN:**
  - (a) referencia retenida (`B6`, `D1`, `D2`);
  - (b) desaparición real (`R2-C2` Caso B) e inaccesibilidad (`R2-C3`);
  - (c) evidencia real de error de `procfs` en inspección (`R2-C5`: no existe fallo `ERROR_PROCFS` real en este entorno Linux);
  - (d) lectura incompleta/ilegible de `/proc/self/maps` (`R1-A3`, `R1-A4`) e inventario incompleto simulado (`R1-B2`);
  - (e) **validación empírica en dispositivo Android/Termux real**: no ejecutada en esta sesión por ausencia de entorno Android/Termux en el sandbox.

## 9. Límites y lo que NO se afirma

- **No ejecutado en Android/Termux real:** **no se afirma** que el arnés haya sido ejecutado ni validado empíricamente en Android/Termux. Queda explícitamente pendiente ejecutar `python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` en el dispositivo Termux objetivo (`/data/data/com.termux/files/home/SDV-SDI_SGM`) y verificar `/proc/self/fd`, SELinux, `R2-C2`, `R2-C8`, `R2-C12`, `R2-C13`, `/proc/self/maps` y desmapeo ARM64.
- **`gc.collect()` NO es una garantía universal:** sigue siendo comportamiento observado en CPython 3.11.2 / NumPy 1.26.4 Linux; requiere verificación en Termux y no garantiza liberación si existe cualquier referencia retenida.
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** validación aislada de mecanismo, sin integración en producción.
- **Mecanismo de clasificación (`R3-D`) y modo `"path"` (`R4-B`):** `ENOENT` + `fdinfo` ausente en `procfs` sigue clasificándose conservadoramente como `UNKNOWN_CAUSE`; el modo `"path"` no tiene garantías de anclaje `dirfd`.
- **Cierre final (`R5-A`):** si `os.close(dirfd)` falla, el inventario es `complete=False` y **no se afirma** que el descriptor quede cerrado ni se reintenta `close()`.
- **Hashes:** los `sha256` exactos de los dos archivos modificados se entregan en el mensaje de commit y en la entrega a Cris.

## 10. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18-R2 **con correcciones R1..R6, R6-R1, R6-R3 y R6-R4 (§13)**. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 sigue **FAIL** (`C5` histórico). R6-R3 resuelve en Linux el falso `ENOENT` de enumeración de `os.listdir()` usando `os.scandir(dirfd)` en línea con diseño portable para Android/Termux, logrando `30 PASS · 0 FAIL · 9 UNKNOWN` en Linux (`global_verdict = UNKNOWN`) y `29 PASS · 1 FAIL · 9 UNKNOWN` en Android/Termux (`global_verdict = FAIL`, único `FAIL`: `R2-C9`). R6-R4 corrige metodológicamente `R2-C9` por identidad `fstat` (§13) con `PASS` aislado en Linux Arena para `R2-C9`/`R2-C8`/`R2-C12`/`R2-C14`, sin batería completa en Arena (falta `numpy`, ver §13.4) y sin validación Termux aún. La validación real en dispositivo Termux corresponde a la fase en dispositivo objetivo y las decisiones sobre D-18 / PR #3 / PR nuevo R6-R4 corresponden exclusivamente a Cris. **Esta entrega no adjudica D18 como PASS, no cierra D18-R2, no aprueba el merge de PR #3 ni del PR nuevo y no autoriza integración en producción.**

## 11. Trazabilidad

- Base del PR #3: `ac82b6c3cc46f6f5202c1a14c4aa70c7a67c87e2` (FEASIBILITY-D18-R2-R5).
- Commits previos en PR #3 conservados intactos:
  - R6: `779485acf4b9116a2f1e055f320382beb2c51799`
  - R6-R1 (padre obligatorio de R6-R3): `8487d9cdd54c9f5e584cec5b1a788c891f00aed5`
- Rama de trabajo y publicación: `arena/83102fa6-sdv-sdi-sgm` (PR #3 abierto hacia `arena/9a32cda8-sdv-sdi-sgm`, sin fusionar ni modificar la rama de destino).
- Únicos 2 archivos modificados en el commit R6-R3:
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py`
  - `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md`
- Evidencia cruda regenerable: `/tmp/feas_d18_r2_evidence/evidence_d18_r2.json` (efímera en `/tmp`).
- Documentos históricos previos y código de producción: **no modificados**.

## 12. Enlaces de GitHub (para auditoría de Cris)

- Repositorio: https://github.com/arielwilliam1986-source/SDV-SDI_SGM
- Pull Request #3 (R6 + R6-R1 + R6-R3, abierto sin fusionar): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/pull/3
- Rama de trabajo (`arena/83102fa6-sdv-sdi-sgm`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/83102fa6-sdv-sdi-sgm
- Rama destino del PR / base R5 (`arena/9a32cda8-sdv-sdi-sgm`, HEAD = `ac82b6c3...`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/9a32cda8-sdv-sdi-sgm
- Commit R6-R1 (padre directo de R6-R3, `8487d9cd`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/8487d9cdd54c9f5e584cec5b1a788c891f00aed5
- Commit R6 (`779485ac`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/779485acf4b9116a2f1e055f320382beb2c51799
- Base R5 (`ac82b6c3`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/ac82b6c3cc46f6f5202c1a14c4aa70c7a67c87e2
- `main` intacta (`b64f15ae`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/b64f15ae8b28e46eef3c024dc62c85fe27c69494
- Arnés (raw en `arena/83102fa6-sdv-sdi-sgm`): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/83102fa6-sdv-sdi-sgm/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py
- Informe (raw en `arena/83102fa6-sdv-sdi-sgm`, este archivo): https://raw.githubusercontent.com/arielwilliam1986-source/SDV-SDI_SGM/arena/83102fa6-sdv-sdi-sgm/INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md
- Rama de trabajo R6-R4 (`arena/a2d9ac2e-sdv-sdi-sgm`, PR nuevo separado del PR #3): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/tree/arena/a2d9ac2e-sdv-sdi-sgm
- Commit base R6-R4 / R6-R3 (`c80f7f11`): https://github.com/arielwilliam1986-source/SDV-SDI_SGM/commit/c80f7f11651e08267a4929527b3035ae40c39e13

## 13. R6-R4 — Corrección metodológica de R2-C9 (adenda cronológica, autorizada por Cris)

> Esta sección **añade** el registro R6-R4 sin borrar ni reemplazar los resultados históricos R6-R3 (§§1–12). El `FAIL` de `R2-C9` en Android/Termux bajo R6-R3 **no** se presenta retroactivamente como `PASS`. **No se declara `D18-R2` global `PASS`. `C5` histórico `FAIL` permanece intacto. D18 sigue `FAIL`.**

### 13.1 Resultados históricos R6-R3 (preservados, no modificados)

- **Linux (sandbox Arena, R6-R3):** **30 PASS · 0 FAIL · 9 UNKNOWN**; veredicto global **UNKNOWN** (precedencia `FAIL > UNKNOWN > PASS`); 39 subpruebas; 10/10 ejecuciones idénticas.
- **Android/Termux real (dispositivo del usuario, R6-R3):** **29 PASS · 1 FAIL · 9 UNKNOWN**; veredicto global **FAIL**.
- **Único `FAIL` de esa ejecución en Termux:** `R2-C9`.
- Causa del `FAIL`: la prueba R6-R3 eliminaba un directorio con `shutil.rmtree(d)` y después exigía que `os.listdir(dirfd)` pudiera seguir enumerándolo. En Android/Termux real esa operación produjo `FileNotFoundError`, aunque el descriptor permanecía abierto.

### 13.2 Explicación técnica: por qué la expectativa R6-R3 de R2-C9 no es portable

La persistencia de un descriptor y la posibilidad de enumerar un directorio después de eliminar su entrada de ruta son **propiedades diferentes**:

1. **Persistencia del descriptor (propiedad POSIX garantizada mientras el fd está abierto):** un descriptor abierto con `os.open(..., O_RDONLY | O_DIRECTORY)` sigue identificando el mismo objeto (mismo `st_dev`/`st_ino` vía `os.fstat(dirfd)`) aunque la entrada de ruta haya sido eliminada, hasta que se cierre explícitamente. Esto es lo que `R2-C9` debe demostrar.
2. **Enumerabilidad tras la eliminación (no garantizada):** `os.listdir(dirfd)` / `os.scandir(dirfd)` tras `rmtree` dependen de la implementación de `readdir`/`fdopendir` de la libc (glibc en Linux vs Bionic en Android), del estado del `DIR*` interno y de la política del sistema de archivos. En glibc/Linux la enumeración tras la eliminación pudo funcionar en el sandbox, pero en Bionic/Android/Termux produjo `FileNotFoundError` con el descriptor abierto. Exigirla como condición de `PASS` convierte una diferencia de implementación no portable en un `FAIL` espurio, sin que el descriptor haya dejado de persistir.

Por tanto, la expectativa R6-R3 era metodológicamente incorrecta: medía enumerabilidad cuando el objetivo declarado de `R2-C9` (R2-A) era demostrar un descriptor de directorio **mantenido abierto, estable e identificable**.

### 13.3 Cambio metodológico R6-R4 (único cambio funcional)

Se conserva el identificador `R2-C9` y su función demostrativa, y se sustituye la expectativa incorrecta. La nueva `test_r2c_persistent_dirfd()`:

1. Crea un directorio temporal y lo abre con `os.open(..., os.O_RDONLY | os.O_DIRECTORY)`.
2. Obtiene `os.fstat(dirfd)` antes de eliminar la ruta y guarda `st_dev` y `st_ino`.
3. Elimina la entrada de directorio con `shutil.rmtree(d)`.
4. Verifica que la ruta ya no existe (`not os.path.exists(d) and not os.path.lexists(d)`).
5. Ejecuta `os.fstat(dirfd)` después de eliminar la ruta.
6. Comprueba que el descriptor sigue identificando el mismo objeto: igualdad de `st_dev` y `st_ino`.
7. Cierra explícitamente el descriptor en `finally` (y limpia el directorio temporal con `shutil.rmtree(d, ignore_errors=True)` si quedó residuo por un error previo a la eliminación, sin dejar descriptores abiertos).

**Prohibiciones respetadas:** sin `os.listdir(dirfd)` ni `os.scandir(dirfd)` tras la eliminación (verificado por inspección del código: solo menciones en docstring/registro, ninguna llamada); sin asumir enumerabilidad tras la eliminación; sin ignorar errores inesperados (se registran con fase, tipo, `errno` y mensaje); sin convertir excepciones inesperadas en `PASS`; sin modificar `fds_with_identity()` para acomodar la prueba.

**Adjudicación conservadora de la nueva R2-C9:**

- `PASS` solo si se acreditan **todas** las condiciones: apertura válida, identidad inicial válida (`st_ino > 0`), desaparición efectiva de la ruta, `fstat` posterior exitoso con la misma identidad y cierre explícito correcto, sin error inesperado.
- `UNKNOWN` si la apertura o la identidad inicial no pueden acreditarse (p. ej. `O_DIRECTORY` no disponible en el entorno): tratamiento conservador, sin inventar garantías de portabilidad.
- `FAIL` probado si la identidad difiere, la ruta persiste tras la eliminación, el `fstat` posterior falla o el cierre falla.

La enumeración anclada mientras el directorio sigue existiendo permanece cubierta por `R2-C8`/`R2-C12`; `R2-C9` ya no la duplica (se eliminó su comprobación de inventario `fds_with_identity()` sobre `/tmp`, sin modificar la implementación de `fds_with_identity()`).

**Elementos intactos (verificados por diff):** `fds_with_identity()`, `_supports_anchored_scandir()`, estrategia `os.scandir(dirfd)` en línea, fallback `path`, clasificación `R3-D`, registro de cierre `R5-A`, controladores reales A/B/C, `R2-C13`, `R2-C14`, precedencia `FAIL > UNKNOWN > PASS`, fallo histórico `C5` y cualquier prueba distinta de `R2-C9` (salvo docstring del módulo y registro `main()`/`scope`/`r6_r4_correction`, ajustes estrictamente necesarios de documentación).

### 13.4 Resultados de las pruebas ejecutadas para R6-R4 y plataforma

**Plataforma de ejecución (Arena, Linux auxiliar — NO Android):**

| Componente | Valor medido |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena) |
| Kernel | `6.1.158+` (`x86_64`) |
| Python | `3.11.2` |
| NumPy | **NO instalado en el entorno Arena** (`ModuleNotFoundError: No module named 'numpy'`). **No se instaló ninguna dependencia**, conforme a la instrucción de informar primero si se requiere instalación fuera del entorno disponible. La batería completa del arnés (que importa `numpy` en el nivel superior y usa `np.memmap` en escenarios A/B/C y en `R2-C13`) **no pudo ejecutarse** en Arena. Se informa a Cris que la ejecución completa en Arena requeriría instalar `numpy==1.26.4` (entorno efímero `/tmp/feas_d18_venv` usado en R6-R3) y queda pendiente de su autorización. |
| Android/Termux en sandbox | **NO disponible** (ninguna ejecución real en dispositivo Android/Termux en esta sesión) |

**Ejecución aislada realizada (solo biblioteca estándar, sin `numpy` real):** se cargó el arnés con un stub de `numpy` únicamente para permitir su importación (sin ejecutar ningún escenario `memmap`), y se ejecutaron vía el controlador real `run_controller()` las pruebas que no dependen de `numpy`: `R2-C8`, `R2-C9` (corregida), `R2-C12` y `R2-C14`. Evidencia efímera (no versionada): `/tmp/feas_d18_r2_evidence/evidence_r6r4_isolated.json`.

| ID | Resultado aislado (Linux Arena) | Observado |
|---|---|---|
| R2-C8 | **PASS** | `enum_mode='dirfd'`, `complete=True`, `errors=[]` (Caso A preservado) |
| R2-C9 (R6-R4) | **PASS** | `open_ok=True; dev_before=65024; ino_before=529127; initial_identity_valid=True; path_gone=True; dev_after=65024; ino_after=529127; fstat_after_ok=True; identity_same=True; close_ok=True; close_error=None; unexpected_error=None; phase_reached=completado` |
| R2-C12 | **PASS** | modo `dirfd` anclado, descriptor cerrado; modo `path` no anclado (preservado) |
| R2-C14 | **PASS** | `all_ok=True` (8/8 casos de precedencia `FAIL > UNKNOWN > PASS`) |

- **Desglose de la selección aislada:** **4 PASS · 0 FAIL · 0 UNKNOWN** (global de la selección: `PASS`). **Este recuento NO es el veredicto global de 39 subpruebas** y no sustituye la batería completa.
- **Repetibilidad de R2-C9 corregida:** 5/5 ejecuciones `PASS` consecutivas en Linux Arena, sin fuga de descriptores (fds en `/proc/self/fd`: 7 antes → 7 después).
- **R2-C13 no ejecutada en esta sesión:** requiere escenarios reales A/B/C con `np.memmap` real y por tanto `numpy` real; queda pendiente de la batería completa con `numpy==1.26.4` autorizado. Su código y adjudicación (`adjudicate_r2c13_verdict`) permanecen intactos y su regresión de precedencia (`R2-C14`) sí se ejecutó y pasó.
- **Batería completa (39 subpruebas) no ejecutada en Arena** por ausencia de `numpy` (ver arriba). No se presentan estos resultados como validación Android.

### 13.5 Qué permanece pendiente de validar en Android/Termux real

1. Ejecución completa del arnés corregido en el dispositivo Termux objetivo (`/data/data/com.termux/files/home/SDV-SDI_SGM`) con `python -B .../arnes_feasibility_d18_r2_numpy_6g1.py` (Python 3.11 / NumPy 1.26.4), verificando que la nueva `R2-C9` pasa por identidad `fstat` sin enumeración tras la eliminación.
2. Verificación en el `procfs`/SELinux reales de Android de `R2-C8`, `R2-C12`, `R2-C13` y del resto de la batería (39 subpruebas), con recuento completo y veredicto global bajo precedencia `FAIL > UNKNOWN > PASS`.
3. Comprobación específica de `os.fstat(dirfd)` tras `rmtree` en Bionic (identidad `st_dev`/`st_ino` estable) y de `mmap`/`/proc/self/maps` en ARM64 (incluyendo página de 16 KB si aplica).
4. Hasta disponer de (1)–(3), **no se afirma** validación Android/Termux de R6-R4 ni se declara `D18-R2` global `PASS`.

### 13.6 Trazabilidad R6-R4

- Base obligatoria: `c80f7f11651e08267a4929527b3035ae40c39e13` (R6-R3). Padre histórico confirmado en el objeto Git: `8487d9cdd54c9f5e584cec5b1a788c891f00aed5` (R6-R1). El clon de sesión es superficial (`--is-shallow-repository = true`, `c80f7f1` marcado `grafted`), lo que explica que `c80f7f1^` no se resuelva localmente; **no** se interpreta como ausencia de padre y no se reescribe el historial.
- Rama independiente de trabajo: `arena/a2d9ac2e-sdv-sdi-sgm` (hija directa de `c80f7f1...`, sin commits anteriores modificados).
- PR nuevo separado del PR #3, con base en la rama de referencia R6-R3 `arena/83102fa6-sdv-sdi-sgm` (`c80f7f1...`). PR #3 permanece intacto, abierto y sin fusionar. Ningún PR fusionado.
- Únicos 2 archivos modificados en R6-R4 (los autorizados): `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_r2_numpy_6g1.py` e `INFORME_FEASIBILITY_D18_R2_NUMPY_6G1.md` (este archivo). Sin archivos auxiliares versionados, sin cambios de producción, sin integración Hardened.
- SHA-256 de ambos archivos en el mensaje de commit R6-R4 y en la entrega a Cris.
