# Auditoría estática de cierre — AudioInput ETAPA 2 (v0.2.1)

**Proyecto:** SDV-SDI_SGM
**Archivo auditado:** `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py`
**Versión de referencia:** v0.2.1
**Rama:** `arena/audioinput-diag-etapa2` (commit de publicación `ae1aa24046cc2aa2cbd04576c53acc40c6ef251d`)
**Ejecutor de inspección:** Arena (auditoría estática; el instrumento NO fue ejecutado)
**Auditor responsable:** Cris (decisiones de autorización)

## 1. Identidad del archivo y referencia exacta

| Item | Valor |
|---|---|
| Archivo | `herramientas/diagnostico_audio/etapa2/audioinput_diag_termux.py` |
| Tamaño | 86575 bytes |
| Líneas | 1922 |
| SHA-256 | `9d89712877787148120ca249d4de32c36f26a38ed56591ae5cddd025f6ad7f81` |
| Blob Git (rama) | `28fa0f68ea12972252b4ec87cc734a040fc91d00` |
| Commit de publicación | `ae1aa24046cc2aa2cbd04576c53acc40c6ef251d` (padre `b64f15ae8b28e46eef3c024dc62c85fe27c69494`) |

Método: inspección estática por lectura del archivo. No se ejecutó el instrumento, no se realizaron pruebas, no se modificó ningún archivo, no se crearon commits ni ramas.

**Enumeración de funciones relevantes** (líneas): `safe_open_dir_anchored` (246), `safe_makedirs_exclusive_anchored` (319), `safe_create_file_exclusive_anchored` (431), `check_no_symlink_in_path` (161), `check_dir_is_safe` (209), `CloseErrorLogger` (707), `create_fixture` (789), `run_environment` (1349), `write_report_json_robust` (1535), `main` (1615).

---

## 2. Auditoría — seis áreas

### 2.1. C1 — Fallback de creación de directorios mediante rutas directas cuando falla la apertura anclada

**Función y líneas:** `safe_makedirs_exclusive_anchored`, líneas **382–402** (fallback en **395–401**); apertura anclada en **384–385**.

**Evidencia de código:**

```python
384:        parent_fd, anchor_msg = safe_open_dir_anchored(str(parent))
385:        if parent_fd >= 0:
...
394:        else:
395:            # Fallback: crear con path directo + verificacion posterior
396:            # No es tan robusto como el anclado, pero sigue siendo exclusivo.
397:            try:
398:                os.mkdir(str(p), mode=0o700)
399:            except FileExistsError:
400:                raise OSError(errno.EEXIST,
401:                              "directorio de ejecucion preexistente (no anclado): {0}".format(p))
```

**Comportamiento real:** Cuando `safe_open_dir_anchored()` falla (O_PATH/O_DIRECTORY ausentes, o cualquier error al abrir la cadena del padre: permisos, componente inexistente, ENOTDIR, etc.), la función **no falla cerrado**: crea el directorio con `os.mkdir(str(p))` por ruta directa. `os.mkdir` no tiene flag `O_NOFOLLOW`; la creación por ruta sigue simbólicamente cualquier componente intermedio que sea enlace. La verificación posterior (paso 4, `os.lstat(str(p))` + `S_ISLNK`) solo inspecciona el **componente final**, no la cadena intermedia.

**Riesgos y condiciones que los producen:**
- **Travesía por symlink intermedio (TOCTOU):** entre el último `check_no_symlink_in_path(parent)` (línea 369) y el `os.mkdir` (398) existe una ventana. Un symlink plantada en un componente intermedio hace que `mkdir` cree el directorio **dentro del destino del enlace** (controlado por un tercero); el `lstat` posterior del componente final succeede y el control de `S_ISLNK` del final no detecta la travesía.
- **Fins del diseño:** el fallback existe para entornos sin O_PATH/O_DIRECTORY (Android/Termux antiguos); sin él, la función sería inútil en esos entornos. Es una decisión de disponibilidad vs. rigor.
- **Silencioso:** el fallback no emite advertencia ni registra en el resultado que la creación no fue anclada; el llamador no puede distinguir ambas rutas.
- **Inconsistencia documental:** la nota del reporte (línea **1867**) afirma `'NO introduce fallbacks por ruta.'`, pero el código **sí tiene** un fallback por ruta explícito. El comportamiento real contradice el documento entregado.

**Propuesta de corrección mínima:**
1. Emitir un registro explícito (stdout/resultado) cuando se usa el fallback: `"creacion no anclada: <motivo>"`, para transparencia.
2. En el fallback, antes del `mkdir`, re-verificar la cadena intermedia **una vez más** y, si un componente intermedio resulta ser symlink, fallar con `ELOOP` (no crear).
3. Tras el `mkdir` por ruta, verificar con `os.stat(str(p))` **y** confirmar que ningún componente intermedio sea symlink (comparar `os.lstat` de cada componente); si se detecta, eliminar solo lo creado por esta llamada y fallar.

**Efectos secundarios:** La verificación extra añade latencia (pocas `lstat`); en sistemas lentos o con muchos componentes, el costo es negociable. Eliminar el fallback (fail-closed) haría el instrumento inusable en entornos sin O_PATH — **requiere decisión de Cris**.

**Estado:** **Confirmado** (el fallback existe y sus riesgos son reales; la inconsistencia con la nota del reporte es objetiva).

### 2.2. C1 — Creación de archivos mediante rutas en lugar de operaciones ancladas por descriptor

**Funciones y líneas:** `safe_create_file_exclusive_anchored` (**452**), `create_fixture` (**799–800**), `write_report_json_robust` (**1566–1568**).

**Evidencia de código:**

```python
452:        fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
...
799:        fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
...
1566:        fd = os.open(str(report_path),
1567:                     os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
```

**Comportamiento real:** Ninguna de las tres creaciones de archivo intenta apertura/creación anclada por `dir_fd` (`os.open(name, ..., dir_fd=parent_fd)`). Todas son aperturas por **ruta字符串 completa**. El nombre `safe_create_file_exclusive_anchored` es **engañoso**: no hay nada anclado en su implementación; lo que sí hace es verificar previamente symlinks en el padre (`check_no_symlink_in_path(parent)`, línea 445) y usar `O_EXCL|O_NOFOLLOW` en el componente final, lo que cierra la carrera sobre el **componente final** (si es un enlace, `open` falla con `EEXIST`/`ELOOP`).

**Riesgos y condiciones:**
- **Travesía por symlink intermedio:** entre `check_no_symlink_in_path(parent)` (445) y `os.open(str(p))` (452) hay una ventana TOCTOU; un symlink plantada en un componente intermedio deriva la creación al destino del enlace. En `create_fixture` y `write_report_json_robust` **ni siquiera** hay verificación previa del padre.
- **Asincronía con el modelo de directorios:** los directorios se crean/abren con modelo anclado (C1.3) pero los archivos no — el modelo de seguridad es mixto y no uniforme.

**Propuesta de corrección mínima:**
1. Renombrar `safe_create_file_exclusive_anchored` a un nombre que refleje la realidad (p. ej. `safe_create_file_exclusive_path`) o, mejor, implementar la creación anclada: abrir el padre con `safe_open_dir_anchored`, crear con `os.open(name, O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW, 0o600, dir_fd=parent_fd)` y cerrar el padre.
2. En `create_fixture` y `write_report_json_robust`, añadir al menos `check_no_symlink_in_path(parent)` antes de la apertura (contención mínima, no solución completa).

**Efectos secundarios:** La creación anclada exige mantener el descriptor del padre abierto durante la creación y cerrarlo después; cambia el ciclo de vida de descriptores y requiere ajustes en las rutas de error. La verificación previa añade latencias pequeñas.

**Estado:** **Confirmado** (las aperturas son por ruta; la nomenclatura "anchored" no corresponde a la implementación).

### 2.3. C1 — Consistencia de `create_fixture()` con el modelo de seguridad de directorios y archivos

**Función y líneas:** `create_fixture`, líneas **789–827** (apertura en **799–803**, escritura y cierre en **806–827**).

**Evidencia de código:**

```python
798:    out_path = Path(dir_path) / "fixture_{0}.wav".format(fixture_name)
799:    arr = generate_audio_array(np)
800:    try:
801:        fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
802:    except OSError as exc:
803:        if exc.errno == errno.EEXIST:
804:            return None, "fixture ya existe: {0}".format(out_path)
...
806:    sfile = None
807:    try:
808:        sfile = sf.SoundFile(fd, mode='w', samplerate=SAMPLE_RATE, channels=CHANNELS,
809:                            format='WAV', subtype=subtype, closefd=False)
810:        try:
811:            sfile.write(arr)
812:        except Exception as exc:
813:            return None, "sf.write fallo: {0}: {1}".format(type(exc).__name__, str(exc)[:80])
...
821:    finally:
822:        if sfile is not None:
823:            closer.close_soundfile(sfile, 'fixture_writer_' + fixture_name)
824:        closer.close_fd(fd, 'fixture_fd_' + fixture_name)
```

**Comportamiento real:** `create_fixture` **no** invoca `check_no_symlink_in_path` sobre el directorio padre, **no** invoca `check_dir_is_safe`, **no** verifica con `lstat`/`fstat` que el objeto creado sea un archivo regular, y **no** intenta creación anclada. Es inconsistente con `safe_create_file_exclusive_anchored`, que sí verifica symlinks en el padre. La creation del directorio `run_dir` sigue el modelo anclado-exclusivo, pero el archivo dentro se crea con un modelo más débil.

**Riesgos y condiciones:**
- **Inconsistencia del modelo:** si el modelo de seguridad exige que toda creación verifique la cadena de padres, `create_fixture` no lo cumple; queda expuesta a la misma ventana TOCTOU del punto 2.2 (aunque el padre `run_dir` fue creado por la misma ejecución, un atacante con acceso al sistema podría plantar un enlace en `run_dir` entre su creación y la creación del fixture).
- **Archivo parcial sin limpieza:** si `sf.SoundFile` abre pero `sfile.write` falla a mitad (línea 813), la función devuelve error pero **deja el archivo WAV parcial en disco** (sin verificar ni eliminar). El docstring de `safe_create_file_exclusive_anchored` documenta este comportamiento; `create_fixture` lo reproduce sin documentarlo explícitamente.
- **Error de cierre:** los errores de cierre sí se registran vía `closer` (líneas 822–824) — este aspecto es correcto.

**Propuesta de corrección mínima:**
1. Añadir `check_no_symlink_in_path(dir_path)` al inicio de `create_fixture` (contención mínima).
2. Tras la creación exitosa, verificar `os.fstat(fd)` que el objeto es regular (`stat.S_ISREG`) y que su tamaño/mombre corresponde; en caso contrario, cerrar y fallar.
3. En el caso de `sfile.write` fallo, registrar en el mensaje que el archivo parcial quedó en disco (documentación del comportamiento real), o eliminar el archivo creado solo en esa ruta de error (**requiere decisión de Cris**: eliminar o conservar para diagnóstico).

**Efectos secundarios:** La verificación de padre añade latencias pequeñas. Eliminar archivos parciales podría borrar evidencia útil para diagnóstico forense; conservarlos expone un artefacto incompleto que podría ser confundido con un fixture válido.

**Estado:** **Confirmado** (las omisiones son objetivas; el riesgo de inconsistencia con el modelo es real).

### 2.4. C4 — Reutilización de números de FD en `CloseErrorLogger`

**Clase y líneas:** `CloseErrorLogger`, líneas **707–772**; seguimiento por número en **717, 730, 737, 740**.

**Evidencia de código:**

```python
717:        self._closed_fds = set()  # Track de fds ya cerrados para evitar dobles cierres
...
730:        if fd in self._closed_fds:
731:            # Ya cerrado, no intentar de nuevo (C4.6)
732:            self.errors.append({"label": label + "_duplicate_skipped",
733:                                "errno": None, "strerror": "fd ya cerrado, no se reintenta"})
734:            return None
...
737:            os.close(fd)
738:            self._closed_fds.add(fd)
739:            return None
740:        except OSError as exc:
741:            self._closed_fds.add(fd)  # Asumimos que ya no es utilizable
```

**Comportamiento real:** La clase registra **números de descriptor** (`int`), no identidades de objeto (`(dev, ino)`). Los números de fd son reutilizables por el sistema: si el mismo número se asigna posteriormente a un **archivo distinto**, `close_fd` con ese número será **erróneamente skipeado** como "duplicado": el nuevo descriptor **queda abierto** (fuga de descriptor) y se registra una entrada `"_duplicate_skipped"` que, además, se añade a `self.errors` — una **false positive** que contamina el reporte de errores de cierre. La inversa también ocurre: si un fd fue cerrado por otro mecanismo (no por este logger), el logger no lo sabe y registra un error `EBADF` espurio al intentar cerrarlo de nuevo.

**Riesgos y condiciones:**
- **Reutilización del número:** ocurre cuando, tras cerrar fd N, el proceso abre otro archivo y el kernel asigna de nuevo el número N. En el flujo actual, cada prueba crea su propio `CloseErrorLogger` y guarda el fd en variable local (p. ej. T11, líneas 838–895: `fd = None` tras el cierre), lo que reduce —pero no elimina— el riesgo: una interrupción o un cierre parcial por otro mecanismo puede reintroducir el número.
- **Registro de "skip" como error:** `"_duplicate_skipped"` es una entrada en `self.errors`; su `summary()` lo contará como error de cierre, inflando el conteo y confundiendo la interpretación.

**Propuesta de corrección mínima:**
1. Etiquetar cada fd con su identidad: al registrar, asociar `(fd, os.fstat(fd).st_dev, os.fstat(fd).st_ino)` (capturado **antes** del cierre); al recibir un fd, verificar la identidad actual; si el número coincide pero la identidad no, cerrar normalmente (no es duplicado).
2. Separar avisos de errores: los skips por duplicado deben ir a una lista de `warnings` distinta de `errors` (o con un campo `kind: "skip"`), para no inflar el reporte de fallos.

**Efectos secundarios:** La captura de `fstat` antes del cierre exige que el fd aún esté abierto (siempre es así en el flujo actual). La identidad por `(dev, ino)` no distingue dos aperturas distintas del mismo archivo — para eso basta (la preocupación es el número, no el objeto). Añade dos llamadas `fstat` por cierre.

**Estado:** **Confirmado** (el mecanismo de seguimiento por número es insuficiente; el escenario de reutilización es real en Python/Linux, aunque el flujo actual lo mitiga parcialmente con guardas locales).

### 2.5. C4 — Conservación de errores de cierre durante `KeyboardInterrupt`

**Funciones y líneas:** `run_environment`, handlers de interrupción en **1413–1421** (pruebas T11–T14) y **1454–1461** (T15–T16); handler genérico de excepciones en **1422–1429**.

**Evidencia de código:**

```python
1413:            except KeyboardInterrupt:
1414:                # C5: interrupcion durante esta prueba
1415:                results.append({'env': env_name, 'test': tid, 'fixture': fname,
1416:                                'status': Result.ERROR,
1417:                                'detail': "KeyboardInterrupt: prueba interrumpida, "
1418:                                          "no se declara PASS",
1419:                                'close_errors': []})
...
1422:            except Exception as exc:
1423:                status = Result.ERROR
1424:                detail = "{0}: {1}\n{2}".format(
1425:                    type(exc).__name__, str(exc)[:120],
1426:                    traceback.format_exc()[-400:])
1427:                close_errors = []
```

**Comportamiento real:** Cuando una prueba levanta `KeyboardInterrupt`, las pruebas T11–T16 ejecutan su `finally` (p. ej. T11 líneas 897–901: `closer.close_soundfile(..., 'sfile_finally')` y `closer.close_fd(..., 'fd_finally')`), por lo que **sí pueden ocurrir cierres y errores de cierre durante el desenvolvimiento de la interrupción**. Sin embargo, `run_environment` **no tiene acceso al `closer` de la prueba** y hardcodea `'close_errors': []`: **todos los errores de cierre acumulados por el closer de la prueba (incluidos los ocurridos durante la interrupción) se descartan**. Lo mismo ocurre con cualquier excepción genérica (`close_errors = []`, línea 1427). Esto contradice el objetivo de C4.3 ("propaga errores al resultado final de cada prueba") en las rutas de interrupción/error.

**Riesgos y condiciones:**
- **Ocultamiento de fallos de cierre reales:** un error de cierre durante la interrupción queda invisible en el reporte JSON; el resultado muestra `close_errors: []`.
- **Confusión en la interpretación:** el reporte sugiere que no hubo problemas de cierre, cuando pudieron ocurrir.
- **Severidad acotada:** los cierres durante el `finally` son "intentos conservadores"; el error perdido informa sobre un cierre fallido, no invalida el resultado de la prueba (que ya es ERROR por la interrupción).

**Propuesta de corrección mínima:**
1. Que las pruebas expongan su closer ante interrupción: alternativa A — que `run_environment` pase un closer **compartido** a las pruebas (cambio de API mayor); alternativa B — que las pruebas, en su `except KeyboardInterrupt` interno, capturen `closer.errors` y los adjunten a una excepción custom (p. ej. `InterruptedWithCloseErrors(exc, closer.errors)`) que `run_environment` consuma y incluya en `close_errors`.
2. En `run_environment`, usar ese atributo si existe: `ce = getattr(exc, 'close_errors', [])`.

**Efectos secundarios:** La alternativa A (closer compartido) simplifica la propagación pero centraliza el estado de cierre y puede introducir dobles registros entre cierres explícitos y de `finally`. La alternativa B es menos invasiva y preserva el diseño actual.

**Estado:** **Confirmado** (la pérdida de `close_errors` en las rutas de interrupción y de excepción genérica es objetiva en el código).

### 2.6. C5 — Propagación de interrupciones y excepciones hasta el resultado global y el informe JSON

**Funciones y líneas:** `run_environment` (captura a prueba, 1413/1454), `main` (captura global, **1788–1803**), informe JSON (**1829–1863**), códigos de salida (**1895–1908**), wrapper `__main__` (**1912–1919**).

**Evidencia de código:**

```python
1788:    except KeyboardInterrupt as exc:
1789:        # C5: interrupcion durante la ejecucion
1790:        interrupted = True
1791:        interrupt_msg = "KeyboardInterrupt: el usuario interrumpio la ejecucion"
...
1796:    except Exception as exc:
1797:        # C5.1: excepcion fatal durante la ejecucion
1798:        interrupted = True
1799:        fatal_exception = exc
...
1895:    if interrupted:
1896:        # C5.1, C5.4: interrupcion o fatal => codigo != 0
1897:        # Si fatal_exception, codigo 2; si solo interrupcion, 130 (convencion SIGINT)
1898:        if fatal_exception is not None:
1899:            sys.exit(2)
1900:        sys.exit(130)
```

**Comportamiento real:** El diseño global es **mayormente correcto**:
- `main` captura `KeyboardInterrupt` y excepciones fatales alrededor de `run_environment`, conserva los resultados ya obtenidos, y el reporte JSON incluye `interrupted`, `interrupt_message`, `fatal_exception`, `fatal_traceback` (líneas 1833–1840).
- Códigos de salida: interrupción → 130, fatal → 2, fallo de escritura del informe → 2, FAIL/ERROR → 1, todo PASS → 0. El wrapper `__main__` también convierte una interrupción fuera del flujo a 130.

**Riesgos y condiciones (hallazgos):**
1. **Interrupción absorbida a nivel de prueba no marca el flag global** (líneas 1413–1421): un `KeyboardInterrupt` durante una prueba es capturado en `run_environment`, se registra como resultado ERROR y se setea `interrupt_flag[0] = True`, pero **no se propaga a `main`**. Consecencia: `interrupted` en el reporte JSON queda **False** aunque hubo una interrupción real (visible solo como un resultado ERROR individual). El código de salida sigue siendo correcto (ERROR > 0 → 1), **no** hay PASS/0 fabricado, pero el campo `interrupted` del reporte es **engañoso**.
2. **Interrupción durante la escritura del reporte** (línea 1891, `write_report_json_robust` llamada **fuera** del `try`): una `KeyboardInterrupt` en ese instante se propaga al wrapper `__main__` → salida 130, pero el archivo JSON puede quedar **parcial/corrupt** (creado con `O_EXCL`, escritura interrumpida a mitad del bucle) y **ningún mensaje** informa que el reporte quedó incompleto. La función sí cierra el descriptor en su `finally` (línea 1597), pero el error no se reporta.
3. **Correcto:** interrupción durante la creación del `run_dir` o de fixtures **sí** propaga a `main` (no hay captura local) → `interrupted=True`, salida 130, reporte completo con el flag.

**Propuesta de corrección mínima:**
1. En `run_environment`, al capturar `KeyboardInterrupt` a nivel de prueba, **además** de setear `interrupt_flag[0]`, propagar una señal al llamador (p. ej. raise una `InterruptedRun` custom o devolver un indicador) para que `main` setee `interrupted = True`.
2. Envolver la llamada a `write_report_json_robust` en un `try/except KeyboardInterrupt` que, ante interrupción, informe explícitamente ("informe JSON incompleto/ausente") y salga con 130; o escribir a un archivo temporal y renombrar atomicamente (**requiere decisión de Cris**: atomizar la escritura implica un renombrado que puede fallar en algunos filesystems).

**Efectos secundarios:** Propagar la interrupción a nivel de prueba cambia el comportamiento actual (que deliberatemente continuaba marcando pruebas posteriores como NOT_EXECUTED); una interrupción global inmediata saltaría esa marcación de NOT_EXECUTED posterior (que es informativa). La atomización del reporte añade una fase de renombrado y un archivo temporal.

**Estado:** **Parcialmente confirmado** (la propagación global es correcta para las rutas principales; el flag global no refleja interrupciones absorbidas a nivel de prueba, y la interrupción durante la escritura del reporte puede dejar un informe corrupto sin aviso).

---

## 3. Resumen de estados de confirmación

| Área | Hallazgo | Estado |
|---|---|---|
| 2.1 | Fallback por ruta en creación de directorios (TOCTOU/travesía por symlink intermedio; silencioso; inconsistente con la nota del reporte) | **Confirmado** |
| 2.2 | Creación de archivos por ruta (no anclada) en las tres funciones; nombre "anchored" inexacto | **Confirmado** |
| 2.3 | `create_fixture` omite verificación de padre, de tipo de archivo y de creación anclada; archivo parcial sin limpieza ni documento | **Confirmado** |
| 2.4 | `CloseErrorLogger` sigue números de fd: reutilización → skip erróneo + fuga de descriptor; skip registrado como error | **Confirmado** |
| 2.5 | Errores de cierre durante `KeyboardInterrupt`/excepción genérica se descartan (`close_errors: []`) | **Confirmado** |
| 2.6 | Propagación global correcta en rutas principales; flag `interrupted` no refleja interrupciones absorbidas a nivel de prueba; interrupción durante la escritura del reporte puede corruptlo sin aviso | **Parcialmente confirmado** |

## 4. Riesgos residuales

1. **Tolerancia a fallos del entorno:** las correctiones propuestas (verificación extra, cierres con identidad) añaden llamadas syscall; en dispositivos Android/Termux lentos, el costo es pequeño pero no nulo.
2. **Compatibilitad de flags:** `O_PATH`/`O_DIRECTORY`/`O_NOFOLLOW` dependen del kernel; el fallback existe precisamente por eso. Cualquier corrección debe conservar un camino funcional en entornos sin `O_PATH` (decision de Cris).
3. **Archivos parciales:** el instrumento no limpia; si se decide eliminar archivos parciales, podría borrar evidencia útil.
4. **Reporte JSON corrupto:** sin atomización, una interrupción durante la escritura puede dejar un JSON inválido que un lector automático podría malinterpretar o ignorar.
5. **La auditoría es estática:** los hallazgos se basan en la lectura del código; no se ejecutó el instrumento, por lo que no se observaron comportamientos dinámicos ni timing real.

## 5. Decisiones que requieren autorización de Cris

1. **2.1:** ¿Conservar el fallback por ruta en la creación de directorios (con advertencia y verificación adicional) o eliminarlo (fail-closed) a costa de inutilizar el instrumento en entornos sin `O_PATH`/`O_DIRECTORY`?
2. **2.2:** ¿Implementar creación de archivos anclada por `dir_fd` (cambio mayor de ciclo de vida de descriptores) o simplemente corregir la nomenclatura y añadir verificaciones previas mínimas?
3. **2.3:** ¿Eliminar el archivo WAV parcial cuando `sfile.write` falla, o conservarlo y documentar explícitamente su existencia?
4. **2.4:** ¿Aceptar la corrección de `CloseErrorLogger` a seguimiento por identidad `(fd, dev, ino)` y separar warnings de errors?
5. **2.5:** ¿Propagar los `close_errors` de la prueba en caso de interrupción mediante closer compartido (alternativa A) o excepción custom con atributo (alternativa B)?
6. **2.6:** ¿Hacer que una interrupción absorbida a nivel de prueba marque `interrupted=True` en el reporte global (y cómo afecta a la marcación NOT_EXECUTED de pruebas posteriores)?
7. **2.6:** ¿Atomizar la escritura del reporte JSON (temp + renombrado) o simplemente añadir manejo de interrupción con aviso explícito?

**Esta auditoría es de inspección estática; no se implementó ninguna corrección y no se solicita aprobación de ninguna.**
