# 6G.1 — DIAGNÓSTICO I-1: enlaces simbólicos en componentes intermedios de la ruta del directorio provisional

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** diagnóstico propuesto para adjudicación. **I-1 no se declara cerrado.** No se ha implementado ninguna corrección. 6G.1 permanece ABIERTA. Nada fusionado ni integrado.
- **Fecha:** 22 de noviembre de 2026.

---

## 1. Identidad exacta del HEAD utilizado

| Elemento | Identidad |
|---|---|
| HEAD técnico autorizado por la instrucción | `9fedc5b223444e73955d2b899b6a434b0f5c670e` (corrección F, batería AI 27/27) |
| HEAD del árbol donde se ejecutó el diagnóstico | `72a935c711d530b89952bbe9317482a18144ac19` |
| Diferencia entre ambos | **Sólo dos informes Markdown** de la nueva sesión (`INFORME_PARA_CHATGPT_ETAPA_6G1.md`, `INFORME_PARA_CHATGPT_CONTINUACION_SESION.md`); `git diff --name-only 9fedc5b..HEAD -- '*.py' '*.json'` = **0 ficheros**. Ningún código, motor, DSP, fixture o validador cambió entre el HEAD autorizado y el diagnóstico. |
| Árbol de trabajo | limpio (`git status --porcelain` vacío) al inicio y al cierre del diagnóstico |
| Entorno de ejecución | Python 3.11.2, numpy 1.26.4, scipy 1.13.1, soundfile 0.13.1, libsndfile 1.2.2, Linux x86_64, kernel 6.1.158+, euid 1001 (uid único del sandbox), `/proc` disponible |

## 2. Identidad del commit padre (del nuevo commit publicado)

El commit que contiene este diagnóstico es hijo directo del HEAD actual de la rama y contiene **exclusivamente** documentación y evidencia diagnóstica (informe, arnés, JSON/CSV de evidencia, manifiesto y sumas). Sin correcciones de producción. La identidad exacta del commit queda registrada en `MANIFEST_DIAGNOSTICO_I1.json` (`commit_padre`) y en el propio historial Git.

## 3. Escenario y amenaza examinada

**Objeto de la instrucción:** determinar si el tratamiento de enlaces simbólicos en componentes intermedios de la ruta del directorio provisional permite una **sustitución efectiva** o una **escritura fuera del directorio previsto**, demostrando las consecuencias en el flujo real de 6G.1 y bajo qué condiciones.

**Mecanismo del diseño (inspección estática de `motores/lectura_segura_6g1.py` y de los tres motores, sin modificarlos):**

1. `create_run_dir(out_base)` hace `os.makedirs(out_base, exist_ok=True)` por **ruta** y luego `_crear_y_acreditar_dir_6g1(out_base, nombre)` (H1-R2/A): abre el padre con `O_DIRECTORY|O_NOFOLLOW` (que protege **sólo el componente final** de la ruta del padre), verifica la **privacidad del padre resuelto** (propiedad del euid, sin escritura grupo/otros), crea el provisional con `mkdir(dir_fd=...)` exclusivo y acredita su identidad `(st_dev, st_ino)` por descriptor; registra en `_DIR_6G1` la clave **cadena de ruta nominal**.
2. Tras la acreditación, **todo el motor escribe por ruta** (`os.path.join(run_dir, ...)`: `engine_log.txt` (Tee), `masks/`, escritores WAV de candidatos, `analysis.json`, `analysis.txt`, `input_integrity_6g.json`), y la reapertura de los WAV finales (`post_wav_identity`) también es por ruta. Cada `open()` resuelve de nuevo **toda la cadena de componentes intermedios**.
3. El **aborto** re-ancla por ruta con `O_NOFOLLOW` y verifica `fstat` contra lo acreditado (H1), con doble verificación y comparación `lstat` vs `fstat` antes del traslado (`abortar_corrida_6g1`).
4. La **publicación de éxito** (`publicar_dir_6g1(origen, destino)`, usada por los tres motores: Hardened L1984, EVO L2095, MQR L2838) hace `renameat2(RENAME_NOREPLACE)` con rutas absolutas vía `AT_FDCWD`, **sin ninguna verificación previa de la identidad acreditada del origen**. La guarda final que la precede verifica el **Mix** (por descriptor, inmune a la sustitución de componentes intermedios del provisional), no el directorio.

**Amenaza:** un proceso con permiso de escritura sobre el directorio que contiene algún componente intermedio de la ruta del provisional (directorio compartido sin `sticky`, o un componente poseído por el atacante) **renomina ese componente y reconstruye la ruta** después de la acreditación. Los procesos de la misma uid siempre pueden hacerlo (residual ya documentado en H1-R2/A).

**Hipótesis sometida a prueba:** (i) las escrituras posteriores del motor caen fuera del provisional acreditado; (ii) el aborto lo detecta (fail-closed); (iii) la publicación de éxito **no** lo detecta y publica un objeto no acreditado como corrida exitosa.

## 4. Procedimiento reproducible de cada prueba

Arnés: `scripts/diagnostico_i1_6g1.py` (nuevo; no modifica ningún fichero existente). Todo el trabajo ocurre en el directorio temporal `--work` (en estas ejecuciones, `/tmp/i1_6g1`); los fixtures del repositorio se usan **sólo lectura** (`fixtures/mix.wav` copiado, `vocal_mix.wav`/`instrumental_mix.wav` como guías del manifiesto).

```bash
# entorno: Python 3.11 + numpy 1.26.4 + scipy 1.13.1 + soundfile 0.13.1 (libsndfile 1.2.2)
python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/diagnostico_i1_6g1.py \
    --casos c1,c2,c3,c4,c0,c4r,c4rt \
    --work /tmp/i1_6g1 \
    --out ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/diagnostico_i1_6g1
```

| Caso | Procedimiento |
|---|---|
| **C1** | `crear_y_acreditar_dir_6g1(base, prov)` en base 0700 sin enlaces; escrituras por ruta (como el motor); `abortar_corrida_6g1` con traslado; fotografías de árbol (C6) y comparación de identidad `(dev,ino)` del trasladado vs acreditado. |
| **C2** | Enlace simbólico preexistente en el **nombre** del provisional (`base/prov → evil`); intento de `crear_y_acreditar_dir_6g1`; `os.open` directo con `O_NOFOLLOW`; fotografía de `evil` antes/después. |
| **C3** | (a) padre = enlace simbólico (componente final); (b) componente **intermedio** enlazado hacia un padre real 0700 del euid; (c) padre resuelto 0777. Comparación de identidad nominal vs resuelta por `lstat`. |
| **C4** (módulo, determinista) | Acreditar; escribir `analysis.json` por ruta; **sustituir** (`rename user → user.orig`; recrear `user` 0777 + `base` + `prov` del atacante); escribir `candidates.json` por ruta (¿dónde cae?); el atacante manipula el contenido (propietario del directorio); `abortar_corrida_6g1` (¿detecta?); `publicar_dir_6g1` (¿re-verifica?); medición C5 (identidades) y C6 (fotografías). |
| **C0** (flujo real, línea base) | Corrida real del motor Hardened (`python -B MOTOR --manifest ... --mode full_processing --out base`) con observador externo (hilo, *polling* 2 ms) que registra la identidad `(dev,ino)` del provisional al aparecer; sin sustitución. Comparación identidad publicada vs acreditada. |
| **C4r** (flujo real, sustitución **temprana**) | Ídem C0 con sustitución inmediata tras detectar el provisional (medido: 0,48 ms tras la creación; capacidad: escritura sobre `shared` 0777). El atacante reconstruye la ruta con su propio árbol. |
| **C4rt** (flujo real, sustitución **tardía**) | Ídem, pero el observador dispara cuando `analysis.json` **aparece** dentro del provisional (`write_reports` en curso; *polling* 0,5 ms), dentro de la ventana entre las últimas escrituras por ruta y la publicación por ruta. Hasta 5 reintentos en directorios nuevos (la ventana es estrecha); se conservan todos los intentos. |
| **C5** (integrado) | En C4/C4r/C4rt: identidad acreditada vs `lstat` de la ruta tras la sustitución vs `fstat` de la re-apertura `O_NOFOLLOW`. |
| **C6** (integrado) | Fotografías de árbol recursivas antes/después de cada escenario (tipo, `dev`, `ino`, modo, uid/gid, tamaño, SHA-256 por fichero, destinos de enlaces sin seguir); enumeración de escrituras fuera del previsto. |

## 5. Resultado observado

| Caso | Resultado | Clasificación |
|---|---|---|
| C1 | Creación, acreditación, aborto y traslado correctos; identidad del trasladado == acreditada; **cero escrituras fuera**. | Comportamiento permitido por el diseño |
| C2 | `FileExistsError` (mkdir exclusivo con `dir_fd`); `O_NOFOLLOW` → `ELOOP`; `evil` intacto y sin escrituras. | **Comportamiento rechazado** |
| C3a | `ELOOP` (el padre-enlace es componente final). | **Comportamiento rechazado** |
| C3b | **Aceptado**: se sigue el componente intermedio; la privacidad se verifica sobre el padre **resuelto** (0700 euid) y la acreditación ancla el objeto resuelto. Divergencia nominal/resuelta documentada. | Comportamiento permitido por el diseño, con salvedad |
| C3c | `RuntimeError` (padre modificable por terceros), sin crear nada. | **Comportamiento rechazado** |
| C4 | Las escrituras post-sustitución caen en el árbol del atacante (`candidates.json` en el atacante, ausente en el acreditado); el atacante manipula contenido (propietario del directorio sustituido); el **aborto DETECTA** (`identidad_distinta (H1)`: sin `ABORT_6G1.json`, sin traslado, fail-closed); **`publicar_dir_6g1` PUBLICA el objeto del atacante** (`SIN_ERROR`; inode publicado 534849 ≠ acreditado 534845; contenido manipulado incluido). | **Vulnerabilidad reproducida** (módulo) + rechazo correcto en el aborto |
| C0 | EXIT_OK; publicado == provisional acreditado (ino 534859); artefactos completos. | Comportamiento permitido por el diseño (línea base) |
| C4r | Sustitución a 0,48 ms de la creación: **EXIT_OK**; TODOS los artefactos de la corrida (`analysis.json`, `analysis.txt`, `mix SDV.wav`, `mix SDI.wav`, `input_integrity_6g.json`) se escribieron en el árbol del atacante; publicado (ino 534879) ≠ acreditado (534874); el provisional acreditado queda huérfano con `engine_log.txt` y `masks/`. | **Vulnerabilidad reproducida** (flujo real) |
| C4rt | Intento 1/5: sustitución en el interior de `write_reports` (534 ms tras la creación): **EXIT_OK y «Corrida finalizada exitosamente»**; publicado (ino 534899) ≠ acreditado (534891); el directorio publicado **NO contiene los artefactos reales** (`mix SDV.wav`, `mix SDI.wav`, `analysis.json`, `engine_log.txt` quedan huérfanos en `user.orig`) y **SÍ contiene `ATAQUE_I1.txt`** introducido por el atacante. | **Vulnerabilidad reproducida** (flujo real) |
| C5 | Identidades medidas: módulo 534845→534849; real temprana 534874→534879; real tardía 534891→534899. La verificación de identidad funciona donde existe (aborto) y **no existe en la publicación**. | Medido |
| C6 | Fotografías: C1 sin fugas; C4/C4r/C4rt con las escrituras en el árbol del atacante enumeradas. | Medido |

**Nota de observación preparatoria (no publicada como evidencia):** en una corrida de calibración previa a la batería final, una sustitución temprana que llegó antes de la apertura de los escritores produjo el camino opuesto: aborto controlado con código 2 (la reapertura por ruta de los WAV falló con ENOENT en el árbol del atacante). Ambos caminos son coherentes con la mecánica descrita: la detección es incidental (depende de dónde caiga la sustitución), no una verificación de identidad de la publicación.

## 6. Evidencia JSON de las pruebas

Todo en `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/evidence/diagnostico_i1_6g1/` (schema `diagnostico-i1/1`, con procedimiento, condiciones, resultado, clasificación y fotografías de árbol):

| Fichero | Contenido |
|---|---|
| `caso_c1.json` | C1 completo (fotos antes/escrituras/final, aborto, identidad) |
| `caso_c2.json` | C2 (rechazo del componente final, evil intacto) |
| `caso_c3.json` | C3 a/b/c (ELOOP, aceptado con identidad resuelta, RuntimeError 0777) |
| `caso_c4.json` | C4 módulo (C5+C6, aborto, publicación con contenido manipulado) |
| `caso_c0.json` | C0 flujo real línea base (identidad preservada) |
| `caso_c4r.json` | C4r flujo real temprana (EXIT_OK, publicado ≠ acreditado) |
| `caso_c4rt.json` | C4rt consolidado de intentos (éxito en intento 1/5) |
| `caso_c4rt_a1.json` | C4rt intento 1 completo (eventos, fotos, provisional huérfano) |
| `matriz_diagnostico_i1_6g1.csv` | Matriz resumen de todos los casos |
| `consolidado_diagnostico_i1.json` | Índice de casos y veredictos |

## 7. Hashes SHA-256 de los artefactos

`ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_DIAGNOSTICO_I1.txt` (verificación desde la raíz del repositorio: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_DIAGNOSTICO_I1.txt | sha256sum -c -`). Cubre el informe, el arnés, la matriz, los 9 JSON y el manifiesto. Re-verificado en el momento de la publicación (§ Manifiesto).

## 8. Impacto real y alcance del riesgo

**Vulnerabilidad reproducida, con condiciones.** En el flujo real de 6G.1 (motor Hardened, `full_processing`), una sustitución de un componente intermedio posterior a la acreditación produce, según el momento:

1. **Ventana tardía (entre `write_reports` y la publicación):** la corrida termina **EXIT_OK** y se publica como éxito un directorio que **no es el provisional acreditado** — con contenido del atacante y sin los artefactos reales, que quedan huérfanos e invalidados de facto. El motor declara «Artefactos Generados: mix SDV.wav | mix SDI.wav | analysis.json» para un directorio que no los contiene. La sustitución es **efectiva**: el producto publicado no procede del objeto cuya identidad quedó acreditada.
2. **Ventana temprana:** toda la corrida se ensambla dentro del árbol controlado por el atacante (escrituras fuera del directorio previsto reproducidas) y se publica igualmente como éxito. Si la sustitución además llega antes de las aperturas por ruta de los escritores, la corrida puede abortar de forma controlada (código 2) — detección incidental, no garantizada.
3. **El aborto sí detecta** (doble verificación H1/CV): ante sustitución, no escribe `ABORT_6G1.json`, no traslada y conserva el provisional. La brecha es específicamente la **ruta de éxito** (y las escrituras por ruta previas, que caen fuera antes de cualquier detección).

**Condiciones de explotación (medidas y declaradas):**
- Requiere **permiso de escritura sobre el directorio que contiene algún componente intermedio** de la ruta del provisional (medido con `shared` 0777): atacante de otra uid si un componente intermedio reside en un directorio escribible por él (compartido sin `sticky` o poseído por el atacante); atacante de la misma uid siempre (residual ya documentado).
- La comprobación de privacidad de `crear_y_acreditar_dir_6g1` cubre **sólo el padre resuelto inmediato**, no la cadena intermedia completa: un padre inmediato privado no impide la sustitución de un componente superior.
- Con `out_base` bajo una cadena de directorios totalmente privada del usuario (p. ej. `$HOME` 0700), no se identificó vía de explotación para atacante de otra uid: la sustitución exigiría escribir sobre un directorio privado. El riesgo queda condicionado a `--out` elegidos dentro de árboles compartidos/controlados por terceros, o a procesos de la misma uid.
- En el sandbox el atacante se simula con el mismo uid del motor; la capacidad relevante (escritura sobre el directorio del componente) es independiente del uid cuando el modo lo permite. No se ejecutó prueba con cambio real de uid.

**Clasificación de lo hallado:** `EXPERIMENTAL_RESULT` (reproducido dinámicamente en el flujo real) para C4/C4r/C4rt; `DOCUMENTED_FACT` (inspección estática verificable) para la ausencia de verificación en `publicar_dir_6g1` y su uso idéntico en los tres motores; `THEORETICAL_DEDUCTION` la extrapolación a EVO/MQR sin corrida propia; `UNKNOWN` el comportamiento bajo uids distintas (no probado).

## 9. Recomendación técnica (propuesta — NO implementada; sujeta a autorización expresa de Cris)

**R1 (mínima, cierra la sustitución efectiva al publicar):** en la ruta de éxito de los tres motores, inmediatamente antes de `_publicar_dir_6g1(run_dir, run_dir_final)`, re-anclar y verificar la identidad acreditada del provisional reutilizando el mecanismo existente (`_anclar_dir_aborto_6g1(run_dir)` + `fstat` vs `_DIR_6G1`): si no coincide, fail-closed → protocolo único de aborto (`directorio no acreditado: sin publicación`), sin fusionar nada. Es exactamente la verificación que `abortar_corrida_6g1` ya hace antes de su traslado (comparación `lstat`-ruta vs `fstat`-descriptor), llevada también a la publicación. Cambio aislado por motor (3 sitios), prueba de regresión dedicada (inyección de sustitución tardía → EXIT != 0, provisional conservado) + repetición de la batería AI y de las regresiones focalizadas vigentes, hashes antes/después.

**R2 (opcional, cierra el confinamiento de escrituras):** abrir y anclar el provisional por descriptor tras la acreditación y hacer las escrituras de las fases finales relativas al descriptor (`dir_fd`) — coste mayor, toca más superficie; con R1, una sustitución tardía deja de publicarse aunque las escrituras intermedias hayan caído fuera (la corrida se declara fallida y el provisional acreditado conserva su contenido hasta el punto de la sustitución). R1 convierte la sustitución efectiva en **fallo detectado**; R2 reduce además la ventana de escritura fuera. Se recomienda decidir R2 tras la adjudicación de R1, no simultáneamente.

**R3 (operacional, sin cambio de código):** documentar en la etapa el requisito de `--out` bajo cadena de directorios privada del usuario (los componentes intermedios no deben residir en directorios escribibles por terceros ni poseídos por otros), explícitamente como condición de la garantía H1-R2/A (que hoy cubre sólo el padre resuelto inmediato).

## 10. Declaración explícita de qué NO se ejecutó

- **No se implementó ninguna corrección** (ni R1 ni R2 ni R3): sólo diagnóstico.
- No se modificó código de producción, motores, DSP, fixtures, validadores ni ningún fichero existente de la etapa; el arnés y la evidencia son ficheros nuevos.
- Sólo se ejecutó el motor **Hardened** en el flujo real (C0/C4r/C4rt). **EVO y MQR no se ejecutaron**; para ellos hay únicamente inspección estática del punto de publicación (idéntico patrón en L2095 y L2838) — extrapolación clasificada como deducción teórica.
- No se ejecutaron las baterías históricas (H1, C-R1, H2, CV, CR), la prueba de no regresión DSP, la batería AI, audio real, Android ni Termux.
- No se probó la explotación con cambio real de uid (atacante en uid distinta); la capacidad se razonó sobre los modos medidos.
- No se evaluó el comportamiento de `masks/` memmap, PNG ni `--keep-masks` (fuera del alcance I-1).
- No se ejecutaron las 5 ventanas de reintento completas en todos los escenarios (C4rt detuvo en el primer éxito, conservando ese intento; los intentos restantes no se corrieron).
- Nada fusionado, integrado ni declarado ganador. 6G.1 permanece abierta; I-1 queda sometido a su adjudicación.

---

*Fin del diagnóstico I-1. Parada obligatoria: se detiene aquí el trabajo pendiente la adjudicación de Cris.*
