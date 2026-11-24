# FEASIBILITY-D18 (6G.1) — VALIDACIÓN EMPÍRICA AISLADA DE IDENTIDAD Y CIERRE DE MMAP

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena.
- **Naturaleza:** validación empírica **aislada** de D-18 (acreditación de identidad y cierre efectivo de mapeos `mmap`, vía `/proc/self/maps` por `(dev,ino)`). **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción (`motores/`, `lectura_segura_6g1.py`, plan v2.3, diseño v5, adjudicación final intactos); cero ejecución de motores; cero audio real; cero Android/Termux; cero DSP/algoritmos; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Estado previo de D-18:** **UNKNOWN** (decisión `ADJUDICACION_FINAL` §5 y matriz D-18 en diseño v5). Esta fase no presupone que el mecanismo supere la prueba.
- **Corrida original:** única, ts `2026-11-22` (entorno aislado `/tmp/feas_d18_7aruaclz`); los fixtures son sintéticos y efímeros (se regeneran en cada ejecución).
- **Rectificación FEASIBILITY-D18-R1:** commit hijo directo de `91ebfd0…` (esta revisión). Corrige discrepancias metodológicas y documentales detectadas en auditoría (R1-A duplicación del fd + `lseek`; R1-B `OpenRecorder`; R1-C reproducibilidad C5 ×3; R1-D integridad del barrido de maps). Reejecución: **27 subpruebas**. Veredicto global **FAIL mantenido** (hallazgo C5 conservado). **24 PASS · 1 FAIL · 2 UNKNOWN**.
- **Veredicto global obtenido:** **FAIL** (precedencia FAIL > UNKNOWN > PASS). 24 PASS · 1 FAIL · 2 UNKNOWN (27 subpruebas).

---

## 1. Commit padre exacto

- **Padre obligatorio de esta fase (FEASIBILITY-D18-R1):** `91ebfd0358db1796373320bf4818b377ea9eddf0` (FEASIBILITY-D18 original).
- Verificado ANTES de trabajar: local = origin = `gh api` = `91ebfd0…` CONFORME, rama `arena/f1c5739f-sdv-sdi-sgm`, árbol limpio salvo el arnés D-18 y este informe aún sin commit (esta R1).

## 2. Commit final y archivos modificados

- **Commit de esta fase (FEASIBILITY-D18-R1):** hijo directo de `91ebfd0…`; **exactamente los 2 archivos existentes MODIFICADOS** (sin crear ni modificar otros archivos); SHA completo en el mensaje de entrega (verificable vía `git`/`gh api`).
- **Archivos (exactamente los 2 autorizados, ambos M):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_mmap_6g1.py` (M) — arnés D-18, **27 subpruebas** A1–A6 / B1–B3 / C1–C8 / D-A / D-B / D-C / E1–E7 (se añaden **C8** y **E7**; se revisa C5 a 3 subprocesos; `accredit_identity` evalúa ahora líneas no interpretables).
  - `INFORME_FEASIBILITY_D18_MMAP_6G1.md` (M) — este informe.
- Evidencia JSON cruda: `/tmp/feas_d18_evidence/evidence_d18.json` (efímera; el arnés la regenera).

## 3. Entorno y versiones exactas

| Componente | Valor |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (`/tmp/venv_i1/bin/python`) |
| numpy | `1.26.4` |
| glibc | 2.36 |
| tmpfs de trabajo | `f_bsize=4096`, `f_namemax=255` |

Veredictos válidos para ESTE entorno y condiciones; sin extrapolación a Android/Termux ni a otros entornos. El `tmp_fs` se inspeccionó con `os.statvfs(...).f_namemax` (no `f_type`, que no existe en `os.statvfs_result`).

## 4. Comando reproducible

```
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_mmap_6g1.py
```

El arnés crea un directorio aislado efímero (`/tmp/feas_d18_*` con `mkdtemp`), registra entorno, ejecuta las 27 subpruebas y vuelca `evidence_d18.json` con todos los veredictos individuales y el global.

## 5. Fixtures sintéticos

- Archivos binarios de 16384 bytes (`\x00`), con nombre único por subprueba; variantes con byte sembrado (`0x5A`, `0x42`, `0x0B`, `deadbeef`) y un nombre con espacios (`a4 con espacios.bin`) para probar el parser.
- Mapeos `mmap.mmap(...)` y `np.memmap(...)` por fd propio, por ruta y por `fileobj`. Cero audio real; cero red; cero archivos del proyecto.

## 6. Método (helpers del arnés)

- `parse_maps()`: lee `/proc/self/maps`, separa `addr`, `perms`, `offset`, `dev (major:minor)`, `ino`, `pathname`; descarta líneas no interpretables y las reporta (sin romper).
- `identity_of(st)`: devuelve `(os.major(st.st_dev), os.minor(st.st_dev), st.st_ino)` — **nunca usa la ruta**.
- `entries_for_identity(entries, st)`: filtra TODAS las entradas cuyo `(major,minor,ino)` coincide (no sólo la primera).
- `fds_with_identity(st)`: lista los `/proc/self/fd/N` cuyo `os.stat` tiene la misma identidad (distingue fd del llamante del fd duplicado que crea `mmap.mmap`, ver §9).
- `OpenRecorder`: **reemplaza `builtins.open`** (NO `os.open`) para registrar la(s) ruta(s) que NumPy pasa a la apertura de archivos a nivel Python. **Qué captura:** las cadenas de ruta que NumPy abre vía `open()` de Python — p. ej. el magic-link `/proc/self/fd/N` en D-A, la ruta real en D-B, y nada en D-C (NumPy usa `nullcontext` con el `fileobj` entregado). **Qué queda FUERA de esta instrumentación:** (i) cualquier `os.open()` de nivel C/system; (ii) el **`dup()` interno que `mmap.mmap` realiza a nivel C** para crear su fd duplicado — ese fd NO pasa por `builtins.open` y por tanto NO es registrado por `OpenRecorder`; se detecta aparte vía inspección de `/proc/self/fd` (`fds_with_identity`). No se afirma que se registren TODAS las aperturas: `OpenRecorder` instrumenta sólo el nivel `builtins.open` de NumPy, no el fd duplicado interno de `mmap.mmap`. (Rectificación R1-B: el informe original decía erróneamente "hook sobre `os.open`".)

Criterio de cierre efectivo: **no** se acepta `del`/gc ni la ausencia de excepción como prueba; se acredita por (a) desaparición de la entrada en `/proc/self/maps`, (b) estado del objeto mmap, (c) estado de los fd (procfs). La acreditación de identidad es siempre por `(dev,ino)`, nunca por coincidencia textual de ruta.

## 7. Resultados individuales por sección

### D18-A — Identidad del mapeo

| ID | Título | Procedimiento | Resultado observado | Evidencia | Exc/errno | Veredicto |
|---|---|---|---|---|---|---|
| A1 | Identidad fstat vs maps | fstat→(dev,ino); buscar TODAS las entradas por (major,minor,ino) | 1 entrada por identidad; 0 no interpretables | st_dev=65024 major=254 minor=0 ino=535432 | — | PASS |
| A2 | Múltiples mapeos mismo archivo | dos mmap (offsets 0 y 8192); buscar TODAS | 2 entradas; offsets=[0, 8192] | 0x0 y 0x2000 | — | PASS |
| A3 | Dos archivos distintos | acreditar cada uno; sin cruces | f1=1 (ino 535436); f2=1 (ino 535437) | ino1≠ino2 | — | PASS |
| A4 | Parser robusto (anónimas, [heap], espacios) | parsear todo maps; ruta con espacios | 218 entradas; 22 anónimas; 5 corcheteadas; 0 atribuidas al archivo | las anónimas tienen dev 00:00 ino 0 | — | PASS |
| A5 | Mapeo anónimo NO atribuido | mmap anónimo vivo + archivo sin mapear | 28 anónimas 00:00/0; 0 atribuidas al archivo | ino=0 descartado por identidad completa | — | PASS |
| A6 | fstat(fd) == stat(path) | comparar identidades fd vs ruta | fstat=(254,0,535440); stat=(254,0,535440) | acreditación no depende de la ruta nominal | — | PASS |

**Conclusión A:** la acreditación de identidad por `(dev,ino)` sobre TODAS las entradas de `/proc/self/maps` es **viable y robusta**; resiste rename, unlink, rutas con espacios y descarta anónimos/falsos positivos por ino=0. (Esto refuerza B.7.2.2-(b) del diseño v5: barrido por identidad, no por nombre.)

### D18-B — Renombrado y eliminación

| ID | Título | Procedimiento | Resultado observado | Evidencia | Exc/errno | Veredicto |
|---|---|---|---|---|---|---|
| B1 | Renombrado tras mmap | mmap; rename; buscar por identidad | 1 entrada, pathname actualizado | identidad sobrevive al rename; ruta nominal cambió | — | PASS |
| B2 | Eliminado tras mmap | mmap+escritura; unlink; buscar | 1 entrada `(deleted)`; stat(path)=FileNotFoundError; mapeo legible | desaparición del NOMBRE ≠ desaparición del MAPEO | FileNotFoundError (2) | PASS |
| B3 | Renombrado + eliminado | mmap; rename; unlink; buscar | 1 entrada `…b3_nuevo.bin (deleted)` | identidad acreditable pese a rename+unlink | — | PASS |

**Conclusión B:** tras rename/unlink, `/proc/self/maps` sigue acreditando la identidad por `(dev,ino)`; la entrada `(deleted)` persiste y el mapeo sigue vivo. La desaparición del nombre no implica desaparición del mapeo (coherente con B.7.2.2-(b)).

### D18-C — Cierre efectivo

| ID | Título | Procedimiento | Resultado observado | Evidencia | Exc/errno | Veredicto |
|---|---|---|---|---|---|---|
| C1 | Liberación de referencias (del+gc) | contar entradas antes/después de `del m; gc.collect()` | antes=1, después=0 | la desaparición en maps ES la evidencia (no la ausencia de excepción) | — | PASS |
| C2 | flush() solo NO cierra | flush; verificar persistencia | tras flush: 1 entrada; usable=True | flush ≠ cierre | — | PASS |
| C3 | Cierre explícito del mmap | close(); verificar maps/estado/fd | tras close: 0 entradas; closed=True; acceso=ValueError; **fd del llamante SIGUE ABIERTO** | mmap NO cierra el fd recibido | ValueError ("mmap closed or invalid") | PASS |
| C4 | Referencias exportadas impiden cerrar | memoryview viva; close() | BufferError; con vista viva=1; tras release+close=0 | cierre efectivo exige liberar vistas/slices/arrays primero | BufferError ("cannot close exported pointers exist") | PASS |
| C5 | NumPy memmap: sin close(); `_mmap.close()` | np.memmap por ruta; cerrar `_mmap` con array vivo; acceso posterior en **3 subprocesos aislados independientes** (R1-C) | hasattr close=False; cierre sin BufferError; maps 1→0; **3/3 subprocesos rc=-11** (SIGSEGV), cada uno confinado; check_estructural=True | acceso posterior al array ⇒ **SIGSEGV reproducible 3/3** (tres ejecuciones independientes, crash exacto en `arr[0]`); cerrar `_mmap` con el array vivo NO es seguro | rc=-11 (SIGSEGV) ×3 | **FAIL** |
| C6 | Vista de NumPy mantiene vivo el mmap | vista `arr[0:16]`; `del` padre; luego `del` vista | con vista viva=1; tras del vista=0 | referencias derivadas impiden el cierre aunque el padre se libere | — | PASS |
| C7 | Orden de cierre y errores | write; close sin flush; doble close; flush tras close | datos=deadbeef; doble close=None; flush tras close=ValueError | close implica visibilidad de datos; doble close idempotente; flush tras close falla | ValueError (flush tras close) | PASS |
| C8 | Descriptor duplicado de mmap.mmap comparte el offset (dup) | mmap.mmap sobre fd propio; identificar ambos fds por (dev,ino); demostrar offset compartido con `os.lseek` (R1-A) | fds=[3,5]; fd original=3; duplicado=5; offset antes orig=0 dup=0; tras `lseek(1234)` orig=1234 dup=1234 | el fd duplicado de `mmap.mmap` es un `dup()` de la misma descripción de archivo abierto: comparte el offset del fd original (comprobado con `os.lseek`) | — | PASS |

**Conclusión C:** el cierre efectivo de un `mmap.mmap` (Python puro) es acreditable por maps+objeto+fd. **PERO** para `np.memmap` el cierre seguro NO es `arr._mmap.close()` con el array vivo: produce **SIGSEGV** (C5, reproducible 3/3 en subprocesos aislados). El cierre seguro para NumPy es liberar el array (`del arr; gc.collect()`) y acreditar la desaparición en maps (C1/C6). El descriptor duplicado que `mmap.mmap` crea internamente es un `dup()` real (offset compartido demostrado en C8, no mera inferencia). Ver §9.

### D18-D — Alternativas de propiedad A/B/C

| ID | Título | Procedimiento | Resultado observado | Evidencia | Exc/errno | Veredicto |
|---|---|---|---|---|---|---|
| D-A | A: fd motor + /proc/self/fd/N | motor abre fd; NumPy vía magic-link; cerrar fd motor; del array | NumPy abrió `['/proc/self/fd/3']`; fds con identidad=**[3, 6]** (motor + duplicado del mmap); byte vía fd=0x42; tras cerrar motor fds=[6], arr legible; tras del=0; fds finales=[] | A: motor abre/posee/cierra SU fd; NumPy abre y cierra SU fd (with); mmap.mmap **duplica** el fd (offset compartido, verificado); el mapeo sobrevive al cierre del fd motor; motor NO posee fd_mm de NumPy | — | PASS |
| D-B | B: NumPy abre por ruta | np.memmap(path); motor NO abre fd | NumPy abrió `['…/db.bin']`; fds con identidad=**[5]** (duplicado del mmap); tras del+gc=0; fds finales=[] | B: NumPy abre por ruta y cierra su fd (with); mmap.mmap duplica el fd: existe UN fd con la identidad, poseído por el objeto mmap (no por el motor); motor NO tiene fd_mm que cerrar; cierre seguro = liberar array (del+gc)+acreditar en maps (cerrar `_mmap` vivo = SIGSEGV, ver C5) | — | PASS |
| D-C | C: fileobj entregado a NumPy | fileobj propio entregado a np.memmap; cerrar fileobj; del array | NumPy abrió `[]`; fds con identidad=**[3, 5]** (fileobj + duplicado del mmap); tras cerrar fileobj arr legible; tras del=0; fds finales=[] | C: motor abre/posee/cierra el fileobj; NumPy no abre ni cierra nada (nullcontext); mmap.mmap duplica el fd; mapeo sobrevive al cierre del fileobj; motor SÍ posee fd_mm (vía fileobj) | — | PASS |

**Conclusión D:** en las tres alternativas, **`mmap.mmap` crea internamente un fd duplicado** (mismo `st_dev`/`st_ino`, offset compartido vía `lseek` comprobado) que se cierra al cerrar el objeto mmap. Contabilización de propiedad:
- **A:** motor posee su fd; NumPy abre su propio fd (magic-link) y lo cierra; el fd duplicado del mmap es de NumPy. Motor NO posee fd_mm.
- **B:** motor NO abre ningún fd; el único fd con la identidad es el duplicado del mmap (de NumPy). Motor NO posee fd_mm.
- **C:** motor posee el fileobj (y por ende el fd_mm); NumPy no abre nada; el duplicado del mmap es del objeto mmap.

No se atribuye a ninguna alternativa garantía demostrada sólo para otra.

### D18-E — Procfs no disponible

| ID | Título | Procedimiento | Resultado observado | Evidencia | Exc/errno | Veredicto |
|---|---|---|---|---|---|---|
| E1 | maps inexistente (**SIMULACIÓN controlada**) | parsear ruta inexistente | FileNotFoundError; acreditación=UNKNOWN | SIMULACIÓN (no es ausencia real de procfs); identidad no acreditable ⇒ UNKNOWN | FileNotFoundError (2) | UNKNOWN |
| E2 | maps ilegible (**SIMULACIÓN controlada**) | leer archivo modo 0000 (euid no-root) | PermissionError; acreditación=UNKNOWN | SIMULACIÓN de EACCES; ausencia real no reproducida | PermissionError (13) | UNKNOWN |
| E3 | Contenido malformado (**SIMULACIÓN controlada**) | líneas basura + dev no-hex + 1 válida con espacios | 1 entrada; 3 no interpretables reportadas | parser robusto; acreditación desde basura sería UNKNOWN (no PASS) | — | PASS |
| E4 | Lógica de decisión de acreditación | función pura: maps+entradas⇒PASS; no disponible⇒UNKNOWN; disponible sin entradas (falso negativo)⇒FAIL | presente=PASS; no_disponible=UNKNOWN; ausente=FAIL | evidencia objeto mmap (vivo) se distingue de evidencia procfs (ausente); sin procfs NO hay PASS | — | PASS |
| E5 | Legibilidad /proc/1/maps (**OBSERVACIÓN REAL**) | leer /proc/1/maps | PermissionError | observación real del entorno, no simulación | PermissionError (13) | PASS |
| E6 | /proc montado y maps legible (**OBSERVACIÓN REAL**) | verificar /proc y /proc/self/maps | /proc existe; maps legible | observación real del entorno | — | PASS |
| E7 | Barrido incompleto (entrada válida + no interpretables) ⇒ UNKNOWN | maps sintético con 1 entrada válida coincidente + 3 líneas no interpretables; acreditar con el listado de no interpretables (R1-D) | entradas válidas=1; no_interpretables=3 (líneas 1,2,4); acreditación=**UNKNOWN** | una entrada coincidente NO basta si el barrido es incompleto: la integridad no está asegurada ⇒ UNKNOWN (no PASS por omisión) | — | PASS |

**Conclusión E:** una ausencia real de procfs **no se reprodujo** en este entorno (no se puede desmontar `/proc` sin privilegios). Se documentan **dos simulaciones controladas** (E1/E2) que arrojan UNKNOWN explícito, nunca PASS por defecto, y se **distinguen expresamente** de las observaciones reales (E5/E6). La regla de decisión (E4) garantiza que sin procfs no hay PASS y que un falso negativo (maps disponible pero la entrada desaparece sin motivo) se clasifica FAIL, no UNKNOWN. **R1-D:** `accredit_identity` ahora recibe y evalúa las líneas no interpretables de `parse_maps()`: si las hay, el barrido no se considera íntegro y la acreditación es UNKNOWN (E7 lo demuestra — una entrada válida coincidente no otorga PASS a un barrido incompleto). Se mantiene la distinción entre «el parser no rompe» (E3) y «la identidad queda íntegramente acreditada» (E4/E7).

## 8. Conteos y veredicto global

```
Conteos: PASS=24 FAIL=1 UNKNOWN=2   (27 subpruebas)
VEREDICTO GLOBAL (precedencia FAIL>UNKNOWN>PASS): FAIL
```

La precedencia es **FAIL > UNKNOWN > PASS**. El único FAIL (C5, SIGSEGV real, reproducible 3/3 en subprocesos aislados) arrastra el veredicto global a **FAIL**; los dos UNKNOWN (E1/E2, simulaciones de procfs ausente) son fail-closed y no ocultan el fallo. La rectificación R1 **no convierte** el FAIL en PASS: el hallazgo C5 se conserva porque se reproduce.

## 9. Hallazgos críticos (deducciones y observaciones reales)

1. **C5 — CIERRE DE `np.memmap` POR `_mmap.close()` ES INSEGURO (FAIL):** `np.memmap` no expone `close()`; el cierre del mapeo subyacente es `arr._mmap.close()`. Con el array (`ndarray`) aún vivo, `_mmap.close()` **no** lanza `BufferError` (el ndarray no mantiene una exportación de buffer activa), pero el acceso posterior al array (`arr[0]`) provoca **SIGSEGV** (rc=-11, reproducible 3/3, crash exacto en `arr[0]`). Esto es un defecto real del mecanismo: cerrar el mmap subyacente mientras el array vive corrompe el acceso. El cierre efectivo seguro para NumPy es **liberar el array** (`del arr; gc.collect()`) y acreditar la desaparición en `/proc/self/maps` (C1/C6), NO invocar `_mmap.close()` con el array vivo.

2. **`mmap.mmap` DUPLICA EL FD INTERNAMENTE (observación real, verificada empíricamente en C8):** al crear `mmap.mmap(fd, …)`, aparece un fd adicional con la misma identidad `(st_dev, st_ino)` del archivo, poseído por el objeto mmap y cerrado al cerrar el mmap. Es un **`dup()` real** (no una reapertura independiente): C8 lo demuestra con `os.lseek` — mover el offset de uno de los fds refleja el mismo offset en el otro (offset compartido, compartido=1234/1234). **Rectificación R1-A:** el informe original afirmaba "offset compartido verificado con lseek" sin subprueba; ahora existe la subprueba aislada **C8** que lo demuestra (antes era una inferencia no instrumentada). Consecuencia para el diseño: en A/B/C el conteo de "fds con la identidad" incluye siempre este duplicado; el fd del llamante NO lo cierra `mmap` (C3: fd del llamante sigue abierto tras `m.close()`). La contabilidad de propiedad en B.7.1/B.7.2 del diseño v5 debe reconocer este fd duplicado para no atribuir al motor un recurso que posee el objeto mmap.

3. **Acreditación por identidad = viable (A/B); cierre efectivo de mmap Python = acreditable (C1–C4, C6, C7); cierre de NumPy = sólo vía liberación del array (C5).** La barrera de D-18 no es la identidad (que funciona) sino el cierre seguro del mmap de NumPy sin SIGSEGV.

## 10. Rectificaciones FEASIBILITY-D18-R1 (R1-A … R1-D)

Esta revisión corrige las discrepancias metodológicas y documentales señaladas en la auditoría, **sin alterar el veredicto global (FAIL)** ni el hallazgo C5.

| ID | Discrepancia | Corrección aplicada en el arnés / informe |
|---|---|---|
| **R1-A** | El informe afirmaba que el fd duplicado de `mmap.mmap` comparte offset vía `lseek`, pero el arnés no lo comprobaba. | **Añadida la subprueba aislada C8** que identifica ambos fds por `(dev,ino)` y demuestra el offset compartido con `os.lseek` (antes=0/0, tras `lseek(1234)`=1234/1234). La afirmación pasa de inferencia a observación experimental registrada. |
| **R1-B** | El informe §6 decía que `OpenRecorder` intercepta `os.open`. | **Corregido el informe §6**: `OpenRecorder` reemplaza `builtins.open` (no `os.open`). Se documenta qué captura (rutas a nivel Python que NumPy abre: magic-link en D-A, ruta real en D-B, nada en D-C) y qué queda fuera (cualquier `os.open` de nivel C y el `dup()` interno de `mmap.mmap`, detectado aparte vía `/proc/self/fd`). No se afirma instrumentación total de aperturas. |
| **R1-C** | C5 ejecutaba un único subproceso mientras el informe afirmaba 3/3. | **C5 ahora ejecuta tres ejecuciones independientes** del escenario adversarial; registra rc y stdout de cada una; cada SIGSEGV queda confinado a su subproceso. Si no todas reproducen, el veredicto se revisa y se refleja exactamente (aquí: 3/3 SIGSEGV ⇒ FAIL conservado). El FAIL no se reduce por conveniencia. |
| **R1-D** | `parse_maps()` devolvía líneas no interpretables, pero `accredit_identity()` no las evaluaba. | **`accredit_identity(entries, st, maps_available, unparseable)`** ahora devuelve UNKNOWN si hay líneas no interpretables (barrido incompleto), UNKNOWN si maps no disponible, PASS si el barrido está completo y hay coincidencias, FAIL si completo y no hay coincidencias estando el mapeo vivo. **Añadida la subprueba E7** (entrada válida + 3 no interpretables ⇒ UNKNOWN, no PASS). E4 ahora pasa el listado real de no interpretables. Se mantiene la distinción «parser no rompe» (E3) vs «identidad íntegramente acreditada» (E4/E7). |

Todas las subpruebas se reejecutaron; los resultados anteriores se conservan y se explican las diferencias (se añaden C8 y E7; C5 pasa a 3 subprocesos; el recuento pasa a 24 PASS / 1 FAIL / 2 UNKNOWN sobre 27 subpruebas). No se inventan ejecuciones ni evidencia.

## 11. Limitaciones y escenarios no reproducidos

- **Ausencia real de procfs (E1/E2): SIMULADA.** No se pudo desmontar `/proc` ni hacer ilegible `/proc/self/maps` realmente en este entorno (euid 1001 sin `CAP_SYS_ADMIN`). Las dos entradas UNKNOWN son simulaciones controladas y se distinguen de observaciones reales (E5/E6). Una ausencia real de procfs queda como **UNKNOWN / fail-closed** por diseño (E4), no validada empíricamente aquí.
- **Entorno único:** Linux 6.1.158+ x86_64, glibc 2.36, Python 3.11.2, numpy 1.26.4, euid 1001. **No extrapolable** a Android/Termux, a otros kernels/versiones de numpy, ni a `mmap.ACCESS_COPY`/`MAP_PRIVATE` con comportamientos distintos de page cache.
- **`np.memmap` en modo lectura/escritura:** probado `mode="r+"`. No se probó `mode="r"`/`"w+"`/`"c"` exhaustivamente salvo la ruta de cierre (el defecto C5 es independiente del modo de acceso del buffer).
- **No se ejecutó el motor Hardened ni `lectura_segura_6g1.py`:** esto es validación aislada de mecanismos, no de la integración. Las conclusiones son sobre el comportamiento de `mmap`/`numpy`/procfs, no sobre el código de producción.
- **SIGSEGV reproducido en subproceso aislado:** para no contaminar el arnés principal; el rc=-11 y la impresión `BEFORE_ACCESS` antes del crash confirman que el fallo ocurre exactamente en el acceso al array tras `close()`.
- **Hashes:** los sha256 de los dos archivos nuevos se calculan realmente y se entregan en el mensaje de entrega (no se afirman aquí valores no calculados).

## 12. Declaración expresa

- Este informe y su arnés son validación empírica aislada de D-18. **No autorizan, ni implementan, ni integran** cambios en `motores/`, `lectura_segura_6g1.py`, el plan v2.3, el diseño v5 ni la adjudicación final. El árbol de producción permanece intacto.
- D-18 parte de **UNKNOWN**; tras esta validación aislada su veredicto empírico es **FAIL** (debido al hallazgo C5: cierre de `np.memmap` vía `_mmap.close()` con el array vivo ⇒ SIGSEGV reproducible 3/3). La rectificación R1 mantiene el FAIL y el hallazgo C5; **24 PASS · 1 FAIL · 2 UNKNOWN** sobre 27 subpruebas. Las subpruebas de identidad (A/B) y de cierre de mmap Python (C1–C4, C6, C7, C8) y de propiedad A/B/C (D) son PASS; las de procfs-ausente son UNKNOWN controlados (E1/E2) y la integridad del barrido se acredita en E4/E7.
- La decisión sobre D-18 (aceptar, requerir mitigación del cierre de NumPy, o mantener UNKNOWN/PROPOSED) corresponde a Cris. La fase siguiente (implementación, D-16, regresión de `single_pair`) requiere **nueva adjudicación expresa** de Cris.

## 13. Trazabilidad

- Padre (FEASIBILITY-D18 original): `91ebfd0358db1796373320bf4818b377ea9eddf0`.
- Arnés: `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_d18_mmap_6g1.py` (modificado en R1; 27 subpruebas).
- Informe: `INFORME_FEASIBILITY_D18_MMAP_6G1.md` (modificado en R1, este archivo).
- Evidencia cruda: `/tmp/feas_d18_evidence/evidence_d18.json` (efímera).
- Commit hijo directo de `91ebfd0…` (R1): SHA en mensaje de entrega; verificable vía `gh api`.
