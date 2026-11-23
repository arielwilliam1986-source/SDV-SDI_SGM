# FEASIBILITY-1 (6G.1) — VALIDACIÓN EMPÍRICA AISLADA DE LOS MECANISMOS DEL PLAN HARDENED v2.3

- **Destinatario:** Cris (ChatGPT), responsable técnico y adjudicador. **Agente ejecutor:** Arena.
- **Naturaleza:** fase de **validación empírica aislada** de los mecanismos propuestos en el plan v2.3. **NO implementa ni integra** el diseño en los motores. Cero modificaciones de producción; cero ejecución de motores; cero audio real; cero Android/Termux; cero FLOW-5..8; cero EVO/MQR; cero `main`; sin merge ni cherry-pick; PR #2 intacto.
- **Fecha de ejecución:** 2026-11-23 (ts de la corrida final: `2026-11-23T23:01:31Z`).
- **Rama:** `arena/f1c5739f-sdv-sdi-sgm`.

---

## 1. Commit padre exacto

`22748622830d1579d7814c51b1f048c58b121110` — verificado ANTES de trabajar: local = origin = `gh api` = `2274862…` CONFORME, árbol limpio.

## 2. Commit final y archivos modificados

- **Commit de esta fase:** hijo directo de `2274862…`; SHA completo declarado en el informe de entrega (un commit no puede contener su propio hash) y verificable vía `git`/`gh api`.
- **Archivos del commit (2; nada de producción, según la autorización §6 «únicamente el arnés aislado y su informe de resultados»):**
  - `ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py` (A) — arnés aislado; **no importa ni ejecuta** ningún módulo de producción.
  - `INFORME_FEASIBILITY_1_6G1.md` (A) — este informe.
- La evidencia JSON cruda (`feas1_f{1..6}.json` + `consolidado_feasibility_1.json`) permanece en el espacio aislado `/tmp/feas1_6g1/evidence/` (efímero por diseño); este informe es el registro y el arnés regenera todo de forma reproducible.

## 3. Entorno

| Componente | Valor observado |
|---|---|
| Plataforma | `Linux-6.1.158+-x86_64-with-glibc2.36` (sandbox Arena; euid 1001, single-uid) |
| Kernel | `6.1.158+` (x86_64) |
| Python | `3.11.2` (`/tmp/venv_i1/bin/python`) |
| numpy | `1.26.4` |
| soundfile | `0.13.1` (libsndfile `1.2.2`) |
| glibc | 2.36 (con símbolo `renameat2` disponible) |

**No se extrapola a Android/Termux ni a ningún otro entorno:** los veredictos son válidos para ESTE entorno y estas condiciones.

## 4. Comandos y procedimientos reproducibles

```
# venv (si el sandbox lo limpia):
python3 -m venv /tmp/venv_i1 && /tmp/venv_i1/bin/pip install numpy==1.26.4 scipy==1.13.1 soundfile==0.13.1
# corrida completa (F1..F6):
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_6g1
# corrida parcial (p. ej. sólo F5):
/tmp/venv_i1/bin/python -B ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/arnes_feasibility_1_6g1.py --raiz /tmp/feas1_6g1 --pruebas F5
```

El arnés (`--pruebas F1..F6`) ejecuta experimentos independientes en subdirectorios limpios de `/tmp/feas1_6g1/f{1..6}/`, con `-B`, sin importar código de producción, y emite JSON por prueba + consolidado. Procedimiento por prueba (resumen; detalle exacto en el código, que es el procedimiento):

- **F1 (R-13):** base acreditada (`O_DIRECTORY|O_NOFOLLOW`+fstat) → `candidates/` creado con `mkdir(dir_fd)` y abierto/acreditado → dos grupos de DOS niveles creados/apiertos componente a componente (`individual_gp01`, `consensus_confidence_weighted_mean`) con fstat y archivo vía `openat O_EXCL` → descenso por `listdir(fd)+lstat(dir_fd)` clasificando tipos → symlink con objetivo real existente + archivo suelto como inesperados → sustitución misma-uid del nombre de un grupo (rename+recrear) y comparación identidad del fd vs lstat del nombre → cierre ordenado (grupos→candidates→base) y comprobación de fugas por `stat` directo de `/proc/self/fd/N`.
- **F2 (R-29):** disponibilidad de `/proc/self/fd` → el magic-link designa el objeto del fd (fstat igual; lectura igual) → el objeto sigue vivo tras `unlink` del nombre nominal → tras cerrar el fd el magic-link desaparece (ENOENT) → alternativa sin procfs: cabecera `.npy` con `np.lib.format.write_array_header_1_0` sobre `os.fdopen(fd,'r+b')` + `np.memmap(file object, mode='r+', offset, shape)` + verificación de identidad y contenido.
- **F3 (R-34):** escritor WAV por descriptor (`closefd=False`) → identidad antes/después → lector por descriptor (formato auto-detectado) con verificación de frames/canales → comportamiento observado con `closefd=True` (el fd propio queda cerrado por libsndfile) → `open_memmap` vía `/proc/self/fd/<fd retenido>` con verificación de identidad y valor → snapshot final de fds.
- **F4 (P-08/R-28):** `masks/` abierto por descriptor → el nombre nominal sustituido por symlink NO redirige las operaciones por fd (contenido vía fd intacto) → `unlinkat` de entradas relativas a `fd_masks` → errores documentados (ENOENT, ENOTEMPTY) → `rmdir` relativo al padre cuando vacío → symlink sustituto intacto y no seguido.
- **F5 (R-D):** disponibilidad de `renameat2` (glibc; la sonda con nombres inexistentes devuelve ENOENT = syscall ejecutada) → publicación `renameat2(fd_padre, 'prov', fd_padre, 'final', RENAME_NOREPLACE)` + `fstat(fd_pub)` == identidad registrada → colisión → EEXIST con destino intacto → sustitución de la entrada origen (mismo-uid): el impostor es renombrado y **detectado** por `fstat(fd_pub) != identidad` (R-31 observado); el real sigue localizable por su descriptor → real movido fuera del padre: ENOENT y el fd del real sobrevive.
- **F6 (cierre):** apertura en orden del plan (anclas→log→2 writers→2 memmaps→2 lectores; 9 fds) → anclas conservadas (fstat) durante las comprobaciones → cierre en orden P-08 (writers→memmaps→lectores→aux→anclas en orden inverso de apertura) con verificación por etapas del desaparecimiento de fds → cero residuos.

## 5. Fixtures sintéticos utilizados

- WAV sintético: ruido blanco PRNG (`np.random.default_rng(20261122)` en F3; `19480720` en F6), amplitud 0.30, 44100 Hz (F3) / 8000 Hz (F6), estéreo, `PCM_16` (escritura por descriptor), 1 s.
- NPY sintéticos: `float32`, formas `(1024,2048)` (F3), `(256,512)` (F2/F6), con valores sembrados y verificados por re-lectura.
- Payload ASCII `payload-feas1` (F2), archivos `dato.txt`/`salida.wav`/`sentinela.txt` de contenido sintético (F1/F4/F5).
- Ningún audio real; fixtures 100 % sintéticos y aislados de los archivos de producción.

## 6. Resultado individual PASS / FAIL / UNKNOWN

| Prueba | Riesgo/mecanismo | Veredicto | Sub-pasos |
|---|---|---|---|
| **F1** | R-13 (subdirectorios dos niveles por descriptores) | **PASS** | 9/9 ok (creación/acreditación candidates y grupos; descenso sin rutas; symlink rechazado; sustitución detectada por identidad; inesperados clasificados; cierre sin fugas) |
| **F2** | R-29 (procfs + alternativa sin procfs) | **PASS** | 5/5 ok (magic-link designa objeto; vivo tras unlink; desaparece al cerrar; alternativa np.memmap(fileobj) viable con identidad y contenido verificados) |
| **F3** | R-34 (soundfile/numpy por descriptor) | **PASS** | 5/5 ok (escritor closefd=False con identidad conservada; lector por fd con contenido esperado; closefd=True cierra el fd propio — observado; open_memmap vía procfs; snapshot) |
| **F4** | P-08/R-28 (limpieza masks por descriptores) | **PASS** | 7/7 ok (fd no redirigido por symlink; unlinkat completo; ENOENT y ENOTEMPTY documentados; rmdir por descriptor del padre; symlink sustituto intacto) |
| **F5** | R-D/P-06 (renameat2 dirfd + acreditación post-rename) | **PASS** | 5/5 ok (disponible vía glibc; publicación con identidad verificada; colisión EEXIST sin tocar destino; sustitución origen detectada; real fuera del padre ENOENT con fd sobreviviente) |
| **F6** | P-08/P-09 (cierre ordenado y fugas) | **PASS** | 8/8 ok (apertura en orden; anclas conservadas; cierre por etapas con desaparición verificada; cero residuos) |

**No hay FAIL ni UNKNOWN en el entorno ensayado.** Un FAIL local no sería garantía universal y un PASS local **no se extrapola**: los veredictos valen para el entorno de §3 y las condiciones declaradas.

## 7. Evidencia de los fallos y excepciones (todas documentadas, ninguna silenciada)

Excepciones observadas y registradas (en la corrida final forman parte de sub-pasos ok; en iteraciones previas del arnés provocaron ajustes documentados en §9):

| Excepción observada | errno | Dónde | Lectura |
|---|---|---|---|
| `NotADirectoryError: Not a directory: 'evil'` | 20 | F1, `open(O_DIRECTORY\|O_NOFOLLOW)` sobre symlink | rechazo garantizado; errno **ENOTDIR** (no ELOOP) con O_DIRECTORY en este kernel |
| `PermissionError: Permission denied` | 13 | F2, `mmap` sobre fd abierto **O_WRONLY** | mmap ACCESS_WRITE exige fd **O_RDWR** (hallazgo → precisión de diseño) |
| `OSError: Bad file descriptor` | 9 | F3, `fstat` tras `sf.close()` con `closefd=True` | libsndfile **cierra el fd propio** con closefd=True (el diseño fija closefd=False) |
| `FileNotFoundError: '/proc/self/fd/6'` | 2 | F2, magic-link tras cerrar el fd | el magic-link vive mientras el fd vive |
| `TypeError: No format specified…: 14` | — | F3/F6 (iteración previa), SoundFile por fd en **escritura** | por fd **exige `format='WAV'`** (no hay extensión que inferir) |
| `TypeError: Not allowed for existing files…` | — | F3/F6 (iteración previa), SoundFile por fd en **lectura** | en lectura **no se permite** format/samplerate/channels (auto-detección de cabecera) |
| `FileExistsError: destino existente: 'final2'` | 17 | F5, colisión | RENAME_NOREPLACE: EEXIST, destino intacto (sentinela verificada) |
| `FileNotFoundError: 'prov4' -> 'final4'` | 2 | F5, real movido fuera del padre | ENOENT; el descriptor del real sobrevive (identidad verificada) |
| `FileNotFoundError: 'no_esta.npy'` | 2 | F4, unlink inexistente | ENOENT documentado |
| `OSError: Directory not empty: 'masks_real'` | 39 | F4, rmdir con contenido | ENOTEMPTY documentado |

## 8. Limitaciones y amenazas no cubiertas

1. **Entorno único:** todo veredicto PASS es válido para Linux 6.1.158+/x86_64/glibc 2.36/Python 3.11.2/numpy 1.26.4/soundfile 0.13.1, euid 1001. No se probó Android/Termux, ni kernels sin `renameat2`, ni `/proc` ausente (la variante sin procfs SÍ se probó, F2).
2. **Atacante same-uid:** los experimentos simulan sustituciones misma-uid controladas; no cubren root, post-return sobre publicados, DoS (disco/renames/fd exhaustion) ni señales.
3. **R-31 observado empíricamente (F5):** ante sustitución de la entrada origen, el impostor queda renombrado al nombre final; la detección es POST-rename (`fstat(fd_pub)`) — sin esa verificación, el comportamiento sería indetectable.
4. **R-13:** los experimentos validan el MECANISMO por descriptores en un arnés aislado; la observación NOTORIA (motor real con `candidates/<grupo>/`) sigue pendiente de una fase con motor autorizado — este resultado no la sustituye.
5. **Fugas:** la ausencia de fugas se verificó para los casos ensayados (F1/F6), no como propiedad general del diseño.
6. **Rendimiento:** no medido (fuera de alcance de esta fase; R-15 sigue abierto).

## 9. Diferencias entre comportamiento documentado (plan v2.3) y comportamiento observado

Estas diferencias son precisión de diseño, NO contradicciones funcionales; el plan no se modifica en esta fase (quedan registradas para la siguiente adjudicación):

1. **soundfile por descriptor en ESCRITURA exige `format='WAV'`** (el plan P-03 no lo explicitaba: `sf.SoundFile(fd, mode='w', …)` sin format eleva TypeError). Precisión: `format='WAV'` + `subtype` obligatorios al escribir por fd.
2. **soundfile por descriptor en LECTURA NO acepta `format`/`samplerate`/`channels`** (TypeError «Not allowed for existing files»): la lectura por fd auto-detecta el formato de la cabecera — aún más anclado que por ruta.
3. **`closefd=True` cierra el fd propio del motor** (EBADF observado tras `sf.close()`): confirma que el diseño debe fijar **`closefd=False`** para retener y acreditar el fd (como ya establecía P-03; ahora con evidencia).
4. **`np.memmap(file object)` exige fd O_RDWR** (EACCES con O_WRONLY): la precisión de P-03 para la variante sin procfs debe especificar `openat(..., O_RDWR)` para los fds destinados a memmap por file object. La variante `open_memmap('/proc/self/fd/N')` NO exige O_RDWR en el fd retenido (numpy abre su propio fd vía magic-link; se verificó).
5. **El errno de rechazo de symlink con `O_DIRECTORY|O_NOFOLLOW` es ENOTDIR (20) en este kernel**, no ELOOP: el rechazo fail-closed se mantiene (la apertura NUNCA sigue el enlace), pero las condiciones de error documentadas del plan deben citar ENOTDIR como errno observado aquí.
6. **La verificación de fugas por listado de `/proc/self/fd` produce falsos positivos** (el propio listado abre un fd transitorio que puede reusar un número cerrado): el arnés usó `os.stat('/proc/self/fd/N')` (syscall directo, sin fd). Precisión metodológica para los arneses futuros.
7. Confirmaciones sin diferencia: identidad (dev,ino) conservada en todas las operaciones por descriptor; magic-link designa el objeto; renameat2 RENAME_NOREPLACE atómico con EEXIST; detección post-rename; orden de cierre verificable por etapas.

**Alcance de las veredictos de identidad/hashes:** las identidades comparadas en esta fase fueron pares `(st_dev, st_ino)` por `fstat` y contenidos por re-lectura exacta (F2/F3); **no se calcularon ni compararon SHA-256** (el mecanismo de hash G1 no forma parte de F1..F6) — no se declara verificación de hashes.

## 10. Declaración expresa

**No se modificó ni ejecutó producción.** El arnés no importa ningún módulo de producción (`motores/`, `lectura_segura_6g1.py`); ningún archivo bajo `motores/` fue tocado (acreditado por `gh api` en el commit: 0 archivos bajo `motores/`); ningún motor fue ejecutado; no hubo audio real, Android/Termux, FLOW-5..8, EVO/MQR, `main`, merge ni cherry-pick; PR #2 intacto; el plan v2.3 y los documentos de adjudicación anteriores NO fueron modificados en este commit.

— Fin del informe FEASIBILITY-1. Parada obligatoria: se detiene tras publicar y queda a la espera de la auditoría de Cris.
