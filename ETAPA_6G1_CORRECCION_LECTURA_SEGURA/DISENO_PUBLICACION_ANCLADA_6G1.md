# 6G.1 — DISEÑO DE PUBLICACIÓN ANCLADA (I-1/D, mecanismo PDA-1)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** diseño y prototipo experimental propuestos para adjudicación. **NO IMPLEMENTADO en producción** (prohibición §6 de la instrucción). 6G.1 permanece ABIERTA. Parada obligatoria ejecutada.
- **Fecha:** 22 de noviembre de 2026.

---

## 1. Adjudicación registrada

| Elemento | Adjudicación de Cris |
|---|---|
| I-1 | **VULNERABILIDAD REPRODUCIDA EN EL FLUJO REAL DE HARDENED**, bajo las condiciones documentadas |
| R1 original | **NO aprobada como solución suficiente** (reabrir la ruta y comprobar identidad antes de `renameat2` sigue resolviendo la cadena absoluta) |
| EVO y MQR | Permanecen **pendientes de validación experimental** |
| 6G.1 | Continúa **ABIERTA**; sin autorización de integración |

## 2. Identidades Git

| Elemento | Identidad |
|---|---|
| Referencia de producción (autorizada) | `9fedc5b223444e73955d2b899b6a434b0f5c670e` |
| Diagnóstico I-1 (adjudicado) | `88a3ea2b9e41938db7c4a894370f2d68033ccbe8` |
| HEAD sobre el que se trabajó | `88a3ea2b9e41938db7c4a894370f2d68033ccbe8` (árbol limpio) |
| Commit de este diseño | hijo directo de `88a3ea2…`; contiene **exclusivamente** documentación, prototipo de diagnóstico y evidencia (0 cambios de producción). Identidad exacta en `MANIFEST_DISENO_PUBLICACION_ANCLADA.json` (`commit_padre`) y en el historial Git |
| Entorno del prototipo | Python 3.11.2 (venv con numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2), Linux x86_64, kernel 6.1.158+, euid 1001, `protected_hardlinks=1` |

## 3. El problema que el diseño debe resolver

El diseño vigente publica con `publicar_dir_6g1(origen, destino)`: rutas **absolutas** resueltas por `renameat2(AT_FDCWD, …)` en el momento de la llamada. La credibilidad de esa operación depende de **toda la cadena de componentes intermedios** en cada instante entre la acreditación y el `renameat2` — una dependencia que el atacante puede secuestrar (I-1: sustitución efectiva reproducida en el flujo real de Hardened).

**Requisito de Cris (§2):** «No basta con demostrar que una comprobación detecta una sustitución. Debe demostrarse que la operación de publicación **no puede** terminar renombrando un objeto distinto del acreditado.»

## 4. Mecanismo propuesto: PDA-1 (par anclado por descriptores)

Respuesta punto por punto a los 7 análisis exigidos en la instrucción:

**4.1 Conservación del descriptor del directorio padre validado desde la creación.**
`crear_y_acreditar_dir_6g1` ya abre el padre con `O_DIRECTORY|O_NOFOLLOW`, verifica su privacidad (euid propietario, sin escritura grupo/otros) y crea el provisional con `mkdir(dir_fd=…)`. El diseño propone que esa función (variante de producción, p. ej. `crear_y_acreditar_dir_6g1_v2`) **no cierre el descriptor del padre** y lo devuelva como parte del ancla. El motor conserva ese `fd_padre` desde `create_run_dir()` hasta el `finally` final (se incorpora su cierre acreditado al protocolo de recursos, `preparar_aborto_6g1`/cierre normal). Un descriptor abierto **no puede ser re-dirigido**: designa el inodo del padre validado para toda la vida del proceso, sin importar qué ocurra con las rutas.

**4.2 Conservación y acreditación del nombre relativo del provisional.**
El nombre (`motorA_run_…_partial` / `mqr_run_…_partial`) es creado por la propia función y su identidad `(st_dev, st_ino)` se acredita por descriptor. El ancla es el par **(fd_padre, nombre_relativo, identidad)**. Nada de la cadena absoluta interviene en las operaciones de publicación.

**4.3 Publicación mediante operación relativa a descriptores.**
`renameat2(src_dir_fd=fd_padre, src=nombre_prov, dst_dir_fd=fd_padre, dst=nombre_final, RENAME_NOREPLACE)`. El destino final vive **en el mismo padre validado** por construcción (`create_run_dir` de los tres motores: `final_dir = join(out_base, …)`, `partial = final_dir + "_partial"`) → la operación es íntegramente relativa a un único descriptor, y **no existe resolución de componentes intermedios** (uno o varios): el kernel recorre una única entrada del directorio designado por el descriptor.

**4.4 `renameat2(RENAME_NOREPLACE)` sin re-resolver la cadena absoluta.**
Idéntico al vigente en garantía de no-reemplazo atómico (EEXIST ante destino existente, sin tocarlo; ante colisión el motor elige sufijo — cada intento es igualmente relativo y re-verificado). La diferencia es que ni origen ni destino atraviesan la cadena secuestrable.

**4.5 Acreditación y protección del directorio de destino.**
El destino se crea siempre **dentro del mismo padre validado**: comparte su protección (privacidad euid verificada en la creación y **re-verificada por `fstat` justo antes de publicar** — un `chmod` posterior del propietario deja la publicación fail-closed, evidencia P6). `RENAME_NOREPLACE` impide sustituir cualquier objeto preexistente en ese padre. El nombre final y sus sufijos son elegidos por el motor, nunca por rutas externas.

**4.6 Comportamiento ante sustitución de componentes intermedios (antes / durante / después).**
- **Antes de la publicación** (el caso reproducido en I-1): **sin efecto** — la operación no lee ninguna ruta; renombra la entrada correcta del padre real, aunque la ruta nominal esté secuestrada (evidencia P1: publicado en el árbol real, señuelo del atacante intacto).
- **Entre comprobación y renombrado** (microventana `fstatat`→`renameat2`): para un atacante **de otra uid es inexploitable** — no puede crear, renombrar ni eliminar entradas dentro de un padre `0700` del euid. Para un atacante **de la misma uid** sigue existiendo una ventana residual de dos syscalls (evidencia P5: el impostor puede ser renombrado), pero el diseño **nunca declara éxito** si el objeto publicado no es el acreditado (paso post-verificación).
- **Después de obtener el descriptor del padre, antes de publicar:** el descriptor se conserva **desde la creación** (no se obtiene al publicar); no hay nueva obtención que atacar. La única mutabilidad restante es la interna del padre (cubierta arriba).
- **Sustitución de la entrada nominal DENTRO del padre validado** (renombrar el provisional y dejar un impostor): imposible para otra uid; para misma uid el `fstatat(AT_SYMLINK_NOFOLLOW)` previo la detecta (evidencia P4: fail-closed, impostor no publicado, provisional robado conservado).

**4.7 Fail-closed siempre.**
Cada paso se registra; cualquier fallo (padre no válido o no privado, entrada ausente/symlink/identidad distinta, `renameat2` con error, verificación post negativa) devuelve `exito=False` **sin excepción de éxito posible**. El motor sólo declara `EXIT_OK` si `exito=True` **y** `traslado_verificado=True` (identidad del destino == acreditada, verificada por descriptor tras el renombrado). Ante fallo: protocolo único de aborto vigente (C-R1/CV), provisional conservado, sin publicación.

## 5. Diagrama de secuencia de la operación propuesta

```text
Motor (run_experiment / _run_core)          Kernel                    Atacante (otra uid)
─────────────────────────────────────────   ─────                     ────────────────────
create_run_dir(out_base):
  fd_padre=open(out_base, O_DIR|O_NOFOLLOW)──▶ objeto PADRE
  fstat(fd_padre): euid propietario,
    sin IWGRP/IWOTH                ─────────▶ OK (privacidad)
  mkdir(nombre, dir_fd=fd_padre)  ─────────▶ crea PROV en el padre
  fstat(nombre, dir_fd)           ─────────▶ acredita (dev,ino)
  [conserva: fd_padre, nombre, (dev,ino)]                (sin rutas)

… corrida real (escrituras por ruta, sin cambios) …

publicar_anclada(fd_padre, nombre, final, ident):
  1. fstat(fd_padre)              ─────────▶ ¿directorio privado,
                                               identidad de la creación? ──▶ no puede
  2. fstatat(fd_padre, nombre,                                              mutar el
       AT_SYMLINK_NOFOLLOW)      ─────────▶ ¿dir regular, identidad      padre (0700
                                               == acreditada?               euid)
  3. [inyección determinista:     ◀────── sólo en pruebas]
       sólo con la MISMA uid
  4. renameat2(fd_padre,nombre,   ─────────▶ renombra LA ENTRADA del
      fd_padre, final, NOREPLACE)             padre validado (0 rutas)
                                               EEXIST → sufijo re-verificado
  5. fstatat(fd_padre, final)     ─────────▶ ¿identidad == acreditada?
       sí  → exito=True (motor: EXIT_OK)
       no  → fail-closed (motor: protocolo de aborto, sin éxito)
finally:
  close(fd_padre) ── acreditado ──▶ cerrado (normal y aborto)
```

## 6. ¿Bastaría con conservar sólo el descriptor del provisional, sin el descriptor del padre?

**No. Justificación técnica con evidencia experimental (P7):**

1. **No existe rename por fd de objeto.** En Linux, `rename*` identifica el objeto por **(dirfd_padre, nombre)** — no hay llamada que mueva un objeto designado por su propio descriptor. Sin el padre, la única vía de renombrado es **re-resolver la ruta nominal** — exactamente la operación vulnerable de I-1.
2. **Re-resolución reproducida como vulnerable** (P7-A, `EXPERIMENTAL_RESULT`): con el componente intermedio sustituido, el renombrado por ruta absolvió el **objeto del atacante** (`publicado_es_acreditado=False`, provisional real conservado en el árbol real) — idéntico al defecto adjudicado.
3. **Alternativa `linkat(fd, "", dirfd, nombre, AT_EMPTY_PATH)` cerrada empíricamente** (P7-B): el kernel devuelve **ENOENT** tanto con fd `O_RDONLY|O_DIRECTORY` como con fd `O_PATH` para un euid sin `CAP_DAC_READ_SEARCH` (syscall directo al kernel; glibc además rechaza la cadena vacía con ENOENT propio antes de la llamada). Y aunque estuviera disponible, su semántica sería **insuficiente**: crea un **segundo nombre** del inodo (no mueve nada) — el atacante retendría el nombre original del provisional en el árbol secuestrado, y el diseño actual requiere que el provisional **desaparezca** de su ubicación al publicarse.

**Conclusión:** el par (fd_padre, nombre) es **irreducible**: el descriptor del padre es lo que elimina la cadena secuestrable, y el nombre es lo que identifica la entrada a renombrar dentro de ese padre. «Sólo fd del provisional» no puede garantizar la operación.

## 7. Comparación: R1 original vs PDA-1

| Aspecto | R1 original (NO aprobada) | PDA-1 (propuesta) |
|---|---|---|
| Verificación previa | Re-abre la **ruta absoluta** con `O_NOFOLLOW` y compara identidad | `fstatat` **relativo al fd del padre** conservado |
| Resolución de componentes intermedios | **Sigue resolviendo la cadena** en la re-apertura y en el `renameat2` (`AT_FDCWD`) | **Cero** resoluciones: todo relativo al descriptor |
| Ventana tras la verificación | La ruta puede ser sustituida entre la comprobación y el `renameat2` por un atacante con escritura en la cadena | Para otra uid: **no explotable** (el padre es privado); para misma uid: residual declarado + post-verificación |
| Sustitución del intermedio antes de publicar | Se detecta (comprobación) | **Sin efecto por construcción** (no participa ninguna ruta) |
| Destino | Ruta absoluta (`AT_FDCWD`) | Entrada del mismo padre validado; `RENAME_NOREPLACE` |
| Éxito declarado | Con la comprobación previa OK | Sólo con **post-verificación de identidad por descriptor** (`traslado_verificado`) |
| Cambio en producción | 3 sitios (verificación previa) | `crear_y_acreditar_dir_6g1` v2 (devuelve fd), 3 sitios de publicación, cierre del fd en protocolos; superficie comparable, cambio aislado por motor |
| Demostración exigida por Cris | No la satisface | P0–P7: la operación renombra la entrada del padre validado aun con la ruta secuestrada (P1) y jamás declara éxito sobre un objeto distinto (P5) |

## 8. Matriz de amenazas y escenarios (resultados del prototipo)

| Escenario de la instrucción | Evidencia | Resultado |
|---|---|---|
| Publicación normal | P0 (PASS) | Publicado == acreditado; provisional desaparece del padre; artefacto interior conservado |
| Sustitución del componente intermedio **antes** de la publicación | P1 (PASS) | Publicado en el árbol real (ino acreditado); árbol del atacante sin publicación; señuelo intacto — **vulnerabilidad eliminada por diseño** |
| **Colisión** del destino | P2 (PASS) | `EEXIST` fail-closed con destino original intacto; variante con sufijo `run_final_r001` re-verificada por identidad |
| **Destino sustituido por objeto ajeno** preexistente | P3 (PASS) | Fail-closed sin tocar el objeto ajeno |
| Sustitución de la entrada nominal **dentro del padre validado** antes de publicar | P4 (PASS) | `fstatat` previo detecta (identidad distinta); impostor no publicado; provisional robado conservado |
| Sustitución **entre comprobación y renombrado** (inyección determinista, misma uid) | P5 (PASS) | El impostor puede ser renombrado en la microventana (residual misma-uid), pero `traslado_verificado=False` → **sin éxito declarado**; provisional robado conservado |
| **Imposibilidad de verificar la identidad** | P4/P6 (PASS) | Padre sin privacidad (`chmod 0777`), entrada ausente/symlink/identidad distinta, `renameat2` con error → fail-closed en todos los casos |
| Atacante **de otra uid** con permisos sobre el directorio intermedio | P1 + P5/P4 (por construcción) | Irrelevante para la publicación (no se resuelven rutas) e impotente contra el padre validado (`0700` euid): no puede crear/sustituir entradas → **no puede provocar renombrado de objeto distinto** |
| Atacante de la **misma uid** | P4/P5 (medido) | Residual: puede renombrar entradas dentro del padre y actuar en la microventana de dos syscalls; el diseño lo convierte en **fallo detectado sin éxito** (nunca `EXIT_OK` con objeto distinto); límite técnico declarado, no eliminable sin soporte del kernel |
| ¿Sólo fd del provisional? | P7 (CONCLUIDO) | No: re-resolución vulnerable (reproducida); `linkat/AT_EMPTY_PATH` cerrado empíricamente (ENOENT sin `CAP_DAC_READ_SEARCH`, incluido O_PATH; `protected_hardlinks=1`) y semántica de doble nombre insuficiente |

Clasificación global: `EXPERIMENTAL_RESULT` (P0–P7 ejecutados); `THEORETICAL_DEDUCTION` la extensión a EVO/MQR (mismo mecanismo, sin corrida propia de esos motores); `UNKNOWN`/limitaciones: explotación real por otra uid en sistemas con `protected_hardlinks=0` o atacante root (fuera del modelo), kernel sin `renameat2` (ya fail-closed en el diseño vigente).

## 9. Análisis individual: Hardened, EVO, MQR

| Elemento | Hardened | EVO | MQR |
|---|---|---|---|
| `create_run_dir` | L1430 (`motorA_run_…`) | L1430, **byte a byte idéntico a Hardened** (diff vacío) | L2159, propio (`mqr_run_…`), misma mecánica H1-R2/A |
| Punto de anclaje del fd padre | Retorno de `create_run_dir` → `run_experiment` | Ídem | Retorno → `_run_core` vía `run_experiment` (contrato CV) |
| Guarda final del Mix | En `run_experiment`, por descriptor (`hmix.verificar`) | Idéntica | En `_run_core`, por descriptor |
| `close_tee` antes de publicar | En `run_experiment` (tras `write_reports`) | Idéntico | En `_run_core` (L2830) **antes** de publicar — diferencia estructural ya aplicada por CV |
| Publicación (patrón idéntico, sin verificación de origen) | L1984 `_publicar_dir_6g1(run_dir, run_dir_final)` | L2095, mismo patrón | L2838, mismo patrón |
| Destino final | `join(out_base, nombre)` → **mismo padre** que el provisional | Ídem | Ídem (`final` y `partial` comparten `out_base`) |
| Traslados de aborto | `run_dir_final + "_aborted"` → mismo padre | Ídem | Ídem (protocolo CV único) |
| Adaptación PDA-1 | `create_run_dir` devuelve ancla; `run_experiment` la conserva y cierra en `finally`; publicación → `publicar_anclada`; fd añadido a `preparar_aborto_6g1` | Idéntico a Hardened (funciones idénticas) | Igual, con el ancla propagada a `_run_core` (por parámetro o `ctx`), publicación en `_run_core` |

**Hechos comprobados por código:** estructura y líneas anteriores (inspección estática, motores sin modificar); `create_run_dir` H==E byte a byte; destino en el mismo padre en los tres; único punto de publicación por motor; `publicar_dir_6g1` compartido de `lectura_segura_6g1` (L769–837).
**Deducciones arquitectónicas:** la adaptación de EVO es idéntica a Hardened por identidad de sus funciones; MQR requiere propagar el ancla a `_run_core` (patrón ya usado por el módulo para `ctx`).
**No probado:** corrida real de EVO/MQR con PDA-1 (sólo prototipo del mecanismo); interacción de PDA-1 con la batería AI existente.
**Limitaciones de seguridad:** residual de la misma uid (microventana de dos syscalls, detectado y sin éxito); root y `protected_hardlinks=0` fuera del modelo; el `out_base` sigue debiendo ser privado (R3 operacional vigente).

## 10. Propuesta de pruebas de regresión (diseño — NO implementadas en producción)

Batería propuesta **RG-PDA** (por motor: Hardened, EVO, MQR), con inyección determinista reutilizando la infraestructura de envolventes de la batería AI (wrappers en memoria, sin modificar motores):

| ID | Inyección / condición | Veredicto exigido |
|---|---|---|
| RG-1 | Sin sustitución (línea base) | EXIT_OK; `traslado_verificado=True`; publicado == acreditado |
| RG-2 | Sustitución del componente intermedio en el momento de `write_reports` (inyección tipo I-1 tardía) | EXIT_OK con publicado == acreditado **en el árbol real** (o fallo detectado); jamás éxito sobre objeto del atacante |
| RG-3 | Sustitución del intermedio tras la acreditación y antes de `write_reports` | Ídem RG-2 |
| RG-4 | Sustitución de la entrada nominal dentro del padre validado (misma uid) | Publicación fail-closed; protocolo de aborto; sin EXIT_OK; provisional robado conservado |
| RG-5 | Inyector entre `fstatat` y `renameat2` (misma uid) | `traslado_verificado=False` → fail-closed; sin EXIT_OK |
| RG-6 | Destino preexistente (colisión) | `EEXIST` → sufijo re-verificado o `PUBLICACION_SEGURA_FALLIDA`; destino intacto |
| RG-7 | `chmod` del padre validado antes de publicar | Fail-closed (privacidad perdida) |
| RG-8 | Regresión no-DSP: AST + PCM idéntico vs `9fedc5b` (el renombrado no altera el DSP) | ACCEPTED |
| RG-9 | Cierre del fd padre: normal, excepción e interrupción | fd cerrado y acreditado en los tres caminos (0 fds residuales, `/proc`) |

Criterios: cada caso determinista (inyecciones por hooks, no por carreras); matriz + evidencia JSON + hashes; parada tras la batería para adjudicación.

## 11. Rectificaciones documentales

Fichero independiente `RECTIFICACION_DOCUMENTAL_I1_6G1.md` (evidencias históricas **sin alterar**): (a) campo `caso: 'C4r'` en `caso_c4rt_a1.json` — causa raíz y identidad real verificable por contenido; (b) número real de ficheros del commit `88a3ea2` (14 añadidos, +2295/−0; git local y API de GitHub coinciden; el "13" del mensaje se refería a los ficheros con hash en las sumas, que no se auto-listan).

## 12. Entregables y verificación de integridad

| Fichero | Contenido |
|---|---|
| `DISENO_PUBLICACION_ANCLADA_6G1.md` | Este informe |
| `scripts/prototipo_publicacion_anclada_6g1.py` | Prototipo PDA-1 (crear_y_anclar, publicar_anclada, escenarios P0–P7) |
| `evidence/prototipo_publicacion_anclada_6g1/escenario_P0..P7.json` | Evidencia por escenario (schema `prototipo-pda-1/1`) |
| `evidence/prototipo_publicacion_anclada_6g1/consolidado_prototipo_pda_1.json` | Índice y veredictos |
| `RECTIFICACION_DOCUMENTAL_I1_6G1.md` | Rectificaciones documentales §5 |
| `MANIFEST_DISENO_PUBLICACION_ANCLADA.json` + `SHA256SUMS_DISENO_PUBLICACION_ANCLADA.txt` | Manifiesto y sumas (verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_DISENO_PUBLICACION_ANCLADA.txt \| sha256sum -c -`) |

## 13. Declaración explícita de qué NO se hizo

- **No se implementó PDA-1 ni R1/R2/R3 en producción**: el prototipo es un módulo de diagnóstico independiente; motores, DSP, fixtures, validadores y `lectura_segura_6g1.py` sin modificar (0 cambios de producción en el commit).
- No se ejecutaron corridas reales de EVO ni MQR (pendientes de validación experimental, según la propia adjudicación).
- No se ejecutaron baterías históricas (H1, C-R1, H2, CV, CR, AI, DSP) ni pruebas de audio real, Android o Termux.
- No se probaron atacantes con uid distinta real ni root (modelo de amenazas razonado por permisos y marcado como tal).
- No se fusionó, integró ni hizo cherry-pick nada. 6G.1 ABIERTA.

## 14. PARADA OBLIGATORIA

El trabajo se detiene aquí. La autorización para implementar (y la elección de PDA-1 frente a alternativas) corresponde a Cris tras revisar este diseño.

*Fin del informe de diseño. Agente en parada.*
