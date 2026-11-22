# 6G.1 — SEGUNDA REVISIÓN PDA-1: PROTECCIÓN INTEGRAL DEL CICLO (Hallazgos A y B)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador técnico.
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.
- **Estado:** informe complementario de diseño propuesto para adjudicación. **NO IMPLEMENTADO en producción** (prohibición §6). 6G.1 ABIERTA. Parada obligatoria ejecutada.
- **Fecha:** 22 de noviembre de 2026.
- **Base:** adjudicación de Cris — PDA-1 aceptado como **base arquitectónica** (`9975f507a70466ea70369bca9fba053888e63353`); dos cuestiones pendientes (Hallazgos A y B) antes del diseño definitivo.

---

## 1. Análisis de PDA-1 y las dos cuestiones pendientes

### 1.1 Hallazgo A — las escrituras anteriores a la publicación

**Pregunta de Cris:** ¿puede PDA-1 publicar correctamente el directorio acreditado aunque sus artefactos hayan sido desviados al árbol sustituto?

**Respuesta experimental (A1, `DEMOSTRADO`): SÍ.** Con el componente intermedio sustituido y escrituras por ruta nominal (como los motores hoy), `publicar_anclada` devolvió `exito=True` con `traslado_verificado=True` (el publicado ES el acreditado) y el contenido del publicado quedó **vacío**, mientras el sustituto del atacante contenía `analysis.json`, `mix SDV.wav` y `mix SDI.wav`. La identidad correcta del directorio **no** implica contenidos correctos: PDA-1 resuelve **quién se publica**, no **dónde se escribió**.

**Conclusión:** PDA-1 necesita un complemento de **escrituras ancladas (EA)** y una **guarda de completitud** antes de publicar (§2 y §3). El Hallazgo A queda reproducido como `EXPERIMENTAL_RESULT`.

### 1.2 Hallazgo B — sustitución posterior a la verificación

**Pregunta de Cris:** tras `renameat2` correcto + verificación post del inodo, un proceso de la misma uid sustituye el destino antes del EXIT_OK. ¿Qué garantía ofrece PDA-1 y cuál es su límite?

**Respuesta experimental (B1, `DEMOSTRADO`):** después de una publicación verificada (`exito=True`, inodo correcto), la sustitución del destino por la misma uid **no es impedida** por PDA-1: el motor emitiría EXIT_OK igualmente y la ruta final pasaría a designar el impostor. La garantía de PDA-1 **termina en el instante de la verificación post**: garantiza que el objeto renombrado y verificado fue el acreditado **en ese instante**; no protege la ruta después.

**Mitigación demostrada (B2, `PASS`):** una re-verificación de la identidad del destino (por el descriptor del padre, `fstatat` sin seguir enlaces) **inmediatamente antes del EXIT_OK** detecta la sustitución y permite fail-closed (sin EXIT_OK). La ventana residual restante es la comprendida entre esa re-verificación y la terminación del proceso — **inalienable desde el espacio de usuario** (dos syscalls no pueden encerrarse en un lock) y se cubre con **evidencia forense** (registro del `(dev,ino)` publicado, verificable por auditoría posterior), no con prevención.

**Límite declarado con honestidad:** PDA-1 (+B2) garantiza (i) que el objeto publicado y verificado es el acreditado, (ii) fail-closed ante toda desviación detectable hasta el return, y (iii) evidencia forense de identidad; **no** garantiza la persistencia de la identidad de la ruta tras el EXIT_OK frente a la misma uid.

## 2. Arquitectura propuesta para proteger las escrituras (EA — escrituras ancladas)

**Inventario real de escrituras por ruta en los tres motores (hecho comprobado por código, motores sin modificar):** los tres usan exactamente cuatro APIs sobre rutas derivadas de `run_dir`:

| API | Uso | Hardened | EVO | MQR |
|---|---|---|---|---|
| `Tee(path)` → `open(path,'w')` | `engine_log.txt` | L1614 (init_tee L215) | L1683 (L220) | L2358 (L363) |
| `sf.SoundFile(join(run_dir,…), mode="w")` | WAV SDV/SDI de candidatos | L1396/L1398 | L1396/L1398 | L2115/L2120 |
| `np.lib.format.open_memmap(path, "w+")` | `masks/*.npy` (memmaps) | L1456→L1628–1639 | L1456→L1698–1709 | L2190→L2469–2484 |
| `open(join(run_dir,…), 'w'/'r')` | `analysis.json`, `analysis.txt`, `input_integrity_6g.json` | L2130, L1957/1963 | L2241, L2068/2074 | L3191, L3578 (re-lectura), L2805/2811 |
| `os.makedirs` | `masks/`, `candidates/<sub>` | L1616, L1654/L1672 | L1685, L1724/L1742 | L2361, L2512/L2529 |
| `write_pngs` (matplotlib) | opcional `--png` | L2185 | L2296 | L3626 |
| Lecturas post (`post_wav_identity`) | verificación de salidas | L1464/L1889 | L1464 | L2857 |

**Mecanismo EA (variante de producción propuesta, no implementada):**

1. **`fd_run` conservado desde la creación**: `crear_y_acreditar_dir_6g1` v2, además del `fd_padre`, abre y conserva `fd_run = os.open(nombre, O_RDONLY|O_DIRECTORY|O_NOFOLLOW, dir_fd=fd_padre)` — descriptor del **objeto** provisional, inmune a cualquier sustitución de rutas (demostrado A3: sustitución en pleno procesamiento no afecta).
2. **Subdirectorios relativos**: `os.mkdir('masks', dir_fd=fd_run)` y, si se requieren, `fd_candidates` análogo para `candidates/<sub>` (patrón probado en A2 para un nivel; dos niveles = segunda apertura relativa, riesgo bajo).
3. **Escrituras de bibliotecas por ruta procfs**: donde la API exige una cadena (soundfile, numpy open_memmap, matplotlib), la ruta pasa a ser `'/proc/self/fd/<fd_run>/<rel>'`. El kernel resuelve el symlink mágico de procfs **contra el objeto designado por el descriptor** (no re-resuelve rutas de disco) — el mismo patrón que `MixHandle` ya usa en producción desde H2-R. **Demostrado en A2 con las versiones reales**: soundfile 0.13.1 (libsndfile 1.2.2) escritura WAV completa (44.100 frames leídos de vuelta vía la ruta publicada), numpy 1.26.4 `open_memmap` con flush, `open()` builtin y log.
4. **Escrituras builtin por `openat`**: donde el código es propio (`Tee` v2, JSON/txt), usar `os.open(rel, O_CREAT|O_WRONLY|O_TRUNC, dir_fd=fd_run)` + `os.fdopen`, eliminando incluso el paso por procfs.
5. **Lecturas post ancladas**: `post_wav_identity` y la re-lectura de `analysis.json` (MQR L3578) por la misma ruta procfs.
6. **Trazabilidad**: `run_dir` nominal se conserva **sólo** para registros/logs/ABORT (texto); toda E/S usa la ruta anclada. Regla de diseño: «ninguna `open*`/`sf.SoundFile`/`open_memmap` recibe `os.path.join(run_dir, …)`».
7. **Cierre determinista**: `fd_run` (y `fd_padre`) se cierran y acreditan en los tres caminos (éxito, excepción, interrupción) integrándolos en `preparar_aborto_6g1` y en el cierre normal acreditado — `C` demostrado (0 fds residuales en los 3 caminos, verificado por `/proc/self/fd`).
8. **Compatibilidad con el protocolo de aborto vigente**: `abortar_6g1` re-ancla por ruta `O_NOFOLLOW`+fstat (H1) — sigue válido y, con EA, el acreditado contiene SIEMPRE las salidas reales de la corrida, por lo que el inventario de invalidación/conservación opera sobre el contenido correcto. Mejora opcional futura: anclar el aborto sobre `fd_run` directamente (compatibilidad mínima garantizada sin cambiarlo).
9. **Guarda de completitud (nueva, antes de publicar)**: verificación por descriptor de que **todos** los artefactos esperados del modo en curso (analysis.json/txt, input_integrity, WAVs de los candidatos en `full_processing`, masks si aplica) existen dentro del acreditado (`fstatat` relativo a `fd_run`); cualquier ausencia → `FalloCorrida6G1` (sin EXIT_OK). Cierra el «identidad ≠ contenido» del Hallazgo A.
10. **Sin cambios DSP**: las llamadas DSP reciben los mismos arrays; EA sólo cambia **dónde** se abren/truncan los ficheros de salida. No se tocan fórmulas ni procesamiento.

## 3. Diagrama de secuencia integral (PDA-1 + EA + B2)

```text
Motor                                          Kernel / FS                    Atacante otra uid
─────                                          ──────────                     ─────────────────
create_run_dir(out_base):
  fd_padre = open(out_base, O_DIR|O_NOFOLLOW) ─▶ padre validado (privacidad euid)
  mkdir(nombre, dir_fd=fd_padre)             ─▶ crea PROV
  fd_run = open(nombre, O_DIR|O_NOFOLLOW,
                dir_fd=fd_padre)             ─▶ ancla del OBJETO   ◀── no puede mutar
  acredita (dev,ino) por fstat                  [conserva fd_padre+fd_run+nombre]
 corrida:
  Tee v2: os.open(rel, dir_fd=fd_run)        ─▶ escribe EN el acreditado
  sf.SoundFile('/proc/self/fd/fd_run/x')     ─▶ idem (biblioteca)
  open_memmap('/proc/self/fd/fd_run/masks')  ─▶ idem
  [inyección determinista de sustitución]      — la ruta nominal queda secuestrada —
  … resto de escrituras                      ─▶ SIGUEN en el acreditado (A3)
 guarda final del Mix (descriptor)           ─▶ inmune (H2 vigente)
 checklist de completitud (fstatat fd_run)   ─▶ ¿todos los artefactos dentro?  → si no: aborto
 close_tee acreditado
 publicar_anclada:
   fstat(fd_padre) re-verificación           ─▶ privacidad + identidad de creación
   fstatat(fd_padre, nombre, NOFOLLOW)       ─▶ identidad del provisional
   renameat2(fd_padre,nombre→final,NOREPLACE)─▶ publica LA ENTRADA del padre
   fstatat(fd_padre, final)                  ─▶ identidad publicada == acreditada
 B2 re-verificación tardía (antes del EXIT_OK)─▶ detecta secuestro del destino  → si no: aborto
 registrar (dev,ino) publicado [forense]
 EXIT_OK
 finally: close(fd_run); close(fd_padre)     ─▶ 0 fds residuales (C)
 ── post-return: la misma uid podría secuestrar la ruta (B1): fuera del modelo
    de prevención; detección forense por el (dev,ino) registrado ──
```

## 4. Modelo de amenazas y límites (declaración explícita)

| Adversario | Capacidad | Cobertura PDA-1+EA+B2 | Límite |
|---|---|---|---|
| **Otra uid** con escritura sobre componente intermedio | rename + reconstrucción de rutas | **Sin efecto**: EA no resuelve rutas (fd_run designa el objeto); PDA-1 publica la entrada del padre validado; no puede mutar el padre 0700 del euid → **no puede desviar escrituras ni provocar EXIT_OK desviado** | Ninguno identificado (modelo razonado por permisos + experimentos single-uid) |
| **Misma uid** (cooperativa o comprometida) | crear/renombrar/borrar cualquier entrada accesible, incl. dentro del padre validado y del destino publicado | Sustitución de la entrada nominal → **detectada** (fstatat previo, P4); microventana fstatat→renameat2 → **detectada** (post-verificación, P5); sustitución post-publicación → **detectada por B2** hasta el return; escrituras desviadas → **imposibles** (EA) | **Post-return**: puede secuestrar la ruta publicada (B1). Prevención imposible desde userspace → **evidencia forense** ((dev,ino) registrado) + aceptación explícita: procesos de la misma uid se consideran **fuera del modelo de prevención persistente** (mismo propietario que el motor) |
| **Root / kernel comprometido** | total | Ninguna (fuera del modelo, estándar del proyecto) | — |
| **Entorno sin `renameat2`** | — | Fail-closed ya vigente (G) | — |
| **Entorno sin `/proc`** | — | MixHandle ya exige `/proc` (requisito vigente); EA reutiliza el mismo requisito | Documentado desde 6G |

## 5. Pruebas de regresión propuestas (diseño; deterministas, con inyección por envolventes)

### 5.1 RG-EA — pruebas del MECANISMO (nivel prototipo, ya ejecutadas como A1–C; versión de regresión para la implementación)

| ID | Inyección / condición | Veredicto exigido |
|---|---|---|
| EA-1 | Sustitución del intermedio antes de escribir | Todas las escrituras en el acreditado (A2) |
| EA-2 | Sustitución del intermedio entre artefactos | Escrituras posteriores en el acreditado (A3) |
| EA-3 | Borrar un artefacto del acreditado tras escribirlo (por fd) | Checklist de completitud falla → sin EXIT_OK |
| EA-4 | Colisión de destino / destino ajeno | EEXIST fail-closed / ajeno intacto (P2/P3) |
| EA-5 | Sustitución del destino post-verificación (misma uid) | B2 la detecta → sin EXIT_OK (B1 sin B2: DEMOSTRADO como límite) |
| EA-6 | Salidas por éxito / excepción / interrupción | 0 fds residuales (C) |

### 5.2 RG-FLOW — pruebas del FLUJO REAL de cada motor (corrida real + envolventes tipo batería AI)

| ID | Inyección / condición | Veredicto exigido |
|---|---|---|
| FLOW-1 | Sustitución temprana (antes de los escritores) — Hardened | EXIT_OK con TODOS los artefactos dentro del acreditado (a diferencia de I-1 C4r) o fallo detectado; jamás éxito con contenido desviado |
| FLOW-2 | Sustitución en el interior de `write_reports` — Hardened | Ídem |
| FLOW-3 | Sustitución del destino post-verificación — Hardened | Sin EXIT_OK (B2 integrado) |
| FLOW-4 | Checklist: artefacto eliminado del acreditado antes de publicar | FalloCorrida, sin EXIT_OK, provisional conservado |
| FLOW-5 | No-regresión DSP: AST + huella + PCM vs `9fedc5b` | ACCEPTED (EA no toca DSP) |
| FLOW-6 | Re-lectura de `analysis.json` anclada (punto propio de MQR) | MQR: EXIT_OK normal o fallo detectado; sin desvío |
| FLOW-7 | Corrida real completa con sustitución — **EVO** | Validación experimental propia (adjudicación pendiente: no por similitud) |
| FLOW-8 | Corrida real completa con sustitución — **MQR** | Ídem |
| FLOW-9 | Cierre de fd_padre/fd_run en los 3 caminos de cada motor | 0 fds residuales, acreditado en los protocolos vigentes |

## 6. Diferencias entre los tres motores (análisis individual — sin asumir compatibilidad por similitud)

| Punto | Hardened | EVO | MQR |
|---|---|---|---|
| Inventario de escrituras | Sección §2 (líneas verificadas) | Mismas cuatro APIs en líneas propias verificadas L1396/1398, L1683–1709, L2068/2074, L2241, L2296 — **verificación individual realizada sobre su código**, no inferida | Cuatro APIs + punto propio: **re-lectura de `analysis.json` L3578** (única lectura post por ruta además de post_wav) y `masks/` SIEMPRE (no condicionada a `--png/--keep-masks`) |
| Writers WAV | L1396/1398 (`CandidateRunner`) | L1396/1398 (clase propia idéntica por inspección) | L2115/L2120 (formato multilínea, `CandidateRunner` MQR) |
| Subdirectorios | `candidates/<sub>` L1654/L1672 | L1724/L1742 | L2512/L2529 |
| Punto de publicación | `run_experiment` L1984 | L2095 | `_run_core` L2838 (close_tee L2830 antes de publicar, ya por CV) |
| `masks/` | Sólo con `--png`/`--keep-masks` | Ídem | Siempre (L2361) → EA requiere `fd_masks` siempre en MQR |
| `shutil.rmtree(masks)` post-publicación | L1997 | L2108 | (no tiene rmtree) |
| Adaptación EA | `create_run_dir`→ancla completa; `init_tee`, writers, memmaps, JSON, post_wav, PNG por rutas ancladas; checklist de completitud | Igual, verificado sobre su código | Igual + re-lectura anclada L3578 + fd_masks siempre |
| Estado de compatibilidad | Diseñada (RG-FLOW 1–5 pendientes de implementación) | **Pendiente de validación experimental** (FLOW-7) — no considerada demostrada | **Pendiente de validación experimental** (FLOW-6/8) — no considerada demostrada |

## 7. Riesgos y cuestiones todavía desconocidas

1. **matplotlib/PNG por ruta procfs**: no probado en prototipo (`UNKNOWN`); esperado viable (usa `open()` interno); alternativa de diseño: generar PNGs después de la publicación o vía `openat`.
2. **Rendimiento del pathwalk procfs**: presumiblemente insignificante frente al DSP; medir en implementación (criterio: delta < 1 % de duración total en fixture).
3. **Subdirectorios de dos niveles** (`candidates/<par>`): patrón idéntico a `masks` probado en A2 para un nivel; dos niveles sin probar (riesgo bajo).
4. **Compatibilidad de envolventes de la batería AI** con rutas procfs: las envolventes instrumentan objetos (SoundFile, Tee), no rutas — probablemente compatibles; verificar en implementación.
5. **`shutil.rmtree(masks)` post-publicación** (Hardened/EVO L1997/L2108): opera sobre el publicado tras EXIT_OK — riesgo bajo (post-verificación); decisión de implementación: ruta normal, procfs o conservar masks.
6. **Termux/Android**: fuera de alcance por prohibición; `/proc` existe en Android pero es `UNKNOWN` hasta prueba autorizada.
7. **Checklist de completitud**: la lista de artefactos esperados depende del modo y motor; definirla por motor en la implementación (riesgo de falsos positivos si el modo cambia).
8. **Atacante otra uid real**: no ejecutable en este entorno (single-uid) — la cobertura se razona por permisos del padre validado y marcada como tal.
9. **Post-return misma-uid**: irreducible desde userspace (B1); la mitigación forense (registro `(dev,ino)`) debe incorporarse al `input_integrity`/`analysis` en la implementación.

## 8. Entregables, SHA-256 y enlaces

| Fichero | Contenido |
|---|---|
| `INFORME_PDA1_PROTECCION_CICLO_6G1.md` | Este informe |
| `scripts/prototipo_escrituras_ancladas_6g1.py` | Prototipo A1–C (reutiliza PDA-1) |
| `evidence/prototipo_escrituras_ancladas_6g1/escenario_A1..C.json` + `consolidado_prototipo_ea_1.json` | Evidencia (schema `prototipo-ea-1/1`) |
| `MANIFEST_PDA1_PROTECCION_CICLO.json` + `SHA256SUMS_PDA1_PROTECCION_CICLO.txt` | Manifiesto y sumas (verificar desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_PDA1_PROTECCION_CICLO.txt \| sha256sum -c -`) |

## 9. Declaración explícita de qué NO se hizo

- **Nada implementado en producción**: motores, `lectura_segura_6g1.py`, DSP, fixtures, validadores intactos (0 cambios de producción; sólo informe + prototipo de diagnóstico + evidencia).
- No se ejecutaron corridas reales de EVO ni MQR (FLOW-7/8 pendientes de autorización).
- No se repitieron baterías históricas ni pruebas DSP. Sin audio real, Android ni Termux.
- No se fusionó ni integró nada. 6G.1 ABIERTA.

## 10. PARADA OBLIGATORIA

El diseño definitivo queda sometido a la adjudicación de Cris. Sin autorización expresa no se modificará producción.

*Fin del informe complementario. Agente en parada.*
