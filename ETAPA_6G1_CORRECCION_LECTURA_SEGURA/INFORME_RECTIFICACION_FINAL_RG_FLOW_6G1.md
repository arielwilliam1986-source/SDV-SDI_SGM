# 6G.1 — INFORME DE RECTIFICACIÓN FINAL DE ADJUDICACIÓN RG-FLOW (precisión T7 + matriz de habilitación real)

- **Destinatario:** Cris (ChatGPT), auditor y coordinador.
- **Naturaleza:** rectificación EXCLUSIVAMENTE documental, conforme a la instrucción. **Cero modificaciones de producción**; nada implementado; ningún motor ni flujo ejecutado; sin audio real, Android ni Termux; sin integración; `main` sin tocar.
- **Commit padre obligatorio:** `504e2b9c6d35c1fb24b979c75aab0bec1ccb52a3`. **Referencia de producción:** `9fedc5b223444e73955d2b899b6a434b0f5c670e`.
- **Ficheros modificados (exclusivamente los autorizados):** `DISENO_RG_FLOW_6G1.md` (M), `REGISTRO_RIESGOS_6G1.md` (M). **Nuevos:** este informe + manifiesto + sumas. Informes históricos y evidencias anteriores: intactos.

## 1. Rectificación T7 — identidad frente a integridad (RG-FLOW §6b y R-08/R-21)

**Precisión documental adoptada (los tres conceptos quedan explícitamente diferenciados):**
1. **Identidad del DIRECTORIO publicado** — `fstat(fd_pub)` vs identidad atestiguada `(dev,ino)`: el objeto abierto es el objeto publicado/acreditado (sujeto a la ventana ACOTADA del diseño §6b).
2. **Identidad del ARCHIVO abierto** — `fstat(fd_file)` (regular, no-symlink, propietario): la entrada relativa al descriptor designa el objeto esperado; **NO garantiza nada sobre el contenido**.
3. **Integridad del CONTENIDO** — sólo afirmable contrastando los bytes leídos contra una referencia CONFIABLE (hash atestiguado independientemente).

**Declaraciones incorporadas:**
- `O_NOFOLLOW`, `dir_fd` y `fstat` **NO impiden modificaciones del contenido por procesos de la MISMA UID** (el inodo verificado permanece escribible por su propietario).
- **SIN hash o identidad de archivo atestiguada independientemente** → el resultado se clasifica **LECTURA ANCLADA**, NUNCA "contenido íntegro".
- **CON hash esperado confiable** (atestiguado independientemente, p.ej. registro forense G creado por `fd_run` antes del renombrado — alcance vigente de G1, SIN ampliar) → comparación documentada: recalcular SHA-256 sobre los bytes leídos desde el descriptor y contrastar; garantiza que el contenido no cambió desde la atestación; **límites declarados**: (i) la referencia del hash es tamperable por la misma uid (registro NO inmutable) → coherencia, no autenticación; (ii) carreras de contenido simultáneas no detectables en general; (iii) post-return la misma uid puede modificar después de la comparación.
- La comprobación de **tipo y propietario NO constituye autenticación del contenido** (sólo descarta sustituciones estructurales).
- El límite post-return y la amenaza de misma uid permanecen expresamente declarados. **G1 NO se amplía.**

## 2. Matriz de habilitación real (RG-FLOW §9 reemplazada)

La tabla anterior ("HABILITADOS" global para Hardened/EVO) queda **sustituida** por la matriz de habilitación real con cuatro estados (DD = diseñado documentalmente; LA = listo para solicitar autorización; BD = bloqueado por dependencia no resuelta; PE = pendiente de prueba empírica), filas FLOW-1..8 + FLOW-6-MQR/T7, columnas por motor, y dependencias explícitas (R-12, R-13, R-18, R-05/R-06, R-14-MQR, atestación T7, verificación empírica de la receta EVO). **Conclusión: NINGÚN conjunto FLOW-1..8 se declara globalmente habilitado:**
- **LA** (sólo falta autorización): FLOW-1..4 SIN adaptación en Hardened.
- **PE**: EVO (verificación empírica de la receta como primer paso de cualquier ejecución; la receta conserva clasificación **DOCUMENTED_FACT — nunca EXPERIMENTAL_RESULT** hasta ejecutarla).
- **BD**: MQR (R-14-MQR) en todos sus flujos; FLOW-5..8 en los tres motores (implementación no autorizada + R-13/R-18/R-05/R-06 según el flujo); FLOW-6-MQR/T7 (atestación `(dev,ino)` + R-14-MQR).
- R-12 (PNG) NO bloquea flujos obligatorios (artefacto opcional); R-13/R-18/R-05/R-06 quedan etiquetados como dependencias de la matriz en el registro de riesgos.

## 3. Aspectos que continúan sin resolver

Atestación `(dev,ino)` para T7 (adaptación futura no autorizada); R-14-MQR (receta no interactiva de MQR); verificación empírica de la receta EVO; R-11 (SIGTERM/SIGKILL), R-12 (matplotlib anclado), R-13 (2 niveles por descriptor), R-15 (rendimiento procfs), R-18 (arneses fileobj-dup); ejecución íntegra de RG-FLOW. **G1 sin ampliar; alcance histórico intacto (`analysis.json`, `mix SDV.wav`); nombres MQR (`SDV.wav`/`SDI.wav`) no equiparables (rectificación A vigente).**

## 4. Verificación de sumas

`SHA256SUMS_RECT_FINAL_RG_FLOW_6G1.txt` (4/4 OK) — desde la raíz: `grep -v "^#" ETAPA_6G1_CORRECCION_LECTURA_SEGURA/SHA256SUMS_RECT_FINAL_RG_FLOW_6G1.txt | sha256sum -c -`

## 5. PARADA OBLIGATORIA

Esta rectificación NO autoriza implementación ni ejecución RG-FLOW. Detenido, a la espera de la adjudicación de Cris.

*Fin del informe. Agente en parada.*
