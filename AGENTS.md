AGENTS.md

REGLAMENTO GENERAL DE AGENTES — SDV-SDI_SGM

**Proyecto:** SDV-SDI_SGM  
**Responsable:** Propietario del repositorio  
**Versión:** 1.1  
**Estado:** Aprobado por el propietario, pendiente de incorporación a GitHub.

1. PROPÓSITO Y AUTORIDAD

Este documento establece las reglas permanentes para todos los agentes de IA que trabajen, analicen o colaboren en el repositorio SDV-SDI_SGM.

Su finalidad es proteger las fuentes originales, mantener la integridad técnica, evitar regresiones y garantizar que los experimentos no se confundan con resultados aprobados.

La autoridad final sobre decisiones arquitectónicas, modificaciones, aceptación de resultados e integración corresponde exclusivamente al propietario del proyecto.

Ningún agente puede interpretar sus propias recomendaciones como autorización para implementar cambios.

2. ESTRUCTURA DE TRABAJO Y PROTECCIÓN DE GITHUB

2.1. Rama principal

- `main` es la fuente oficial del proyecto.
- Está protegida mediante las reglas de GitHub configuradas por el propietario.
- Ningún agente debe modificarla directamente.
- Está prohibido eludir sus protecciones mediante force push, reemplazos, sincronizaciones destructivas o mecanismos equivalentes.

2.2. Política de creación y reutilización de ramas

No es obligatorio crear una rama nueva para cada tarea, conversación o modificación.

La creación de ramas debe ser proporcional al alcance, riesgo y necesidad de aislamiento del trabajo.

**A. Trabajos que no necesitan una rama nueva:**

- Consultas e inspecciones.
- Auditorías de solo lectura.
- Revisiones de documentación.
- Análisis de código sin modificaciones.

**B. Modificaciones pequeñas:**

- Pueden agruparse en una rama de mantenimiento existente y autorizada.
- Se puede reutilizar una rama activa cuando pertenezca al mismo objetivo y no interfiera con otros trabajos.
- No crear ramas adicionales por cada corrección pequeña o archivo modificado.
- No mezclar tareas independientes únicamente para evitar crear ramas.

**C. Trabajos que justifican una rama nueva:**

- Nuevas etapas de desarrollo.
- Cambios arquitectónicos.
- Modificaciones que afecten varios módulos.
- Experimentos que necesiten aislamiento.
- Correcciones de riesgo elevado.
- Modificaciones DSP autorizadas.
- Trabajos paralelos que puedan interferir entre sí.

Antes de crear o reutilizar una rama, el agente debe comprobar su estado, rama de origen, commit base y modificaciones pendientes.

Formato orientativo:

`arena/etapa-XX-descripcion`

`gemini/etapa-XX-descripcion`

No crear ramas innecesarias ni reutilizar ramas que contengan cambios ajenos al objetivo actual.

2.3. Pull Requests

- Los cambios destinados a integrarse deben presentarse mediante Pull Request cuando las reglas de GitHub lo requieran.
- Ningún agente puede fusionar un Pull Request sin autorización explícita.
- Todo PR debe identificar su commit base, cambios realizados, pruebas ejecutadas, resultados y limitaciones.
- No presentar como aprobado un cambio que solamente haya sido implementado o probado por su autor.

2.4. Conservación y limpieza de ramas

- No eliminar ramas que contengan resultados experimentales o evidencias pendientes de auditoría.
- Las ramas fusionadas pueden eliminarse cuando ya no sean necesarias y exista autorización o una política de limpieza previamente aprobada.
- Evitar acumular ramas obsoletas sin justificación.
- Conservar los commits y referencias necesarios para reconstruir el historial de cada etapa.

2.5. Prohibiciones

Está prohibido:

- Modificar directamente `main`.
- Hacer force push.
- Reemplazar el repositorio con una copia externa.
- Eliminar archivos o directorios sin autorización.
- Ejecutar operaciones destructivas sobre archivos cuyo origen no esté identificado.
- Modificar permisos, reglas de protección o configuración de GitHub.
- Sobrescribir el trabajo de otro agente.

3. PROTOCOLO OBLIGATORIO ANTES DE IMPLEMENTAR

Todo trabajo complejo debe seguir este procedimiento:

**Fase A — Inspección**

1. Identificar repositorio, rama y commit.
2. Leer los archivos originales relevantes.
3. Consultar documentación y resultados de etapas anteriores.
4. Identificar dependencias y relaciones entre módulos.
5. Comprobar si existen modificaciones pendientes de otros agentes.

**Fase B — Diagnóstico**

1. Describir el problema.
2. Diferenciar defectos confirmados, riesgos, hipótesis y cuestiones desconocidas.
3. Identificar los archivos afectados.
4. Determinar posibles regresiones.
5. Proponer una solución técnicamente justificada.

**Fase C — Autorización**

- Entregar el diagnóstico y la propuesta.
- Esperar aprobación explícita del propietario.
- No comenzar la implementación antes de recibirla.

**Fase D — Implementación autorizada**

- Seleccionar una rama existente adecuada o crear una nueva cuando el alcance y riesgo lo justifiquen.
- Modificar únicamente los archivos autorizados.
- Conservar las fuentes originales.
- Ejecutar las pruebas pertinentes.
- Documentar todos los cambios.

**Fase E — Entrega**

- Presentar los resultados.
- Proporcionar enlaces GitHub directos.
- Identificar el commit final.
- Entregar un informe de auditoría.
- Esperar autorización para cualquier integración.

Una autorización para diagnosticar no equivale a una autorización para implementar.

4. INTEGRIDAD DE LAS FUENTES

Las fuentes originales del proyecto deben conservarse.

Antes de modificar cualquier archivo:

- Registrar su ruta.
- Identificar su versión.
- Registrar SHA-256 cuando corresponda.
- Comparar contra el estado base.
- Determinar si es una fuente original, una copia experimental o un artefacto generado.

No sustituir silenciosamente archivos originales por versiones corregidas.

Los cambios deben ser trazables y reversibles.

Cuando una tarea requiera modificar una fuente original, debe existir autorización expresa y un registro de las modificaciones.

5. PROTECCIÓN ABSOLUTA DEL DSP

En las tareas de infraestructura, lectura, validación, seguridad, orquestación o compatibilidad, el DSP debe permanecer inalterado.

Se consideran elementos protegidos:

- STFT e ISTFT.
- FFT y hop.
- Chunking.
- Máscaras.
- Fórmulas SDV y SDI.
- Consensus.
- Power y epsilon.
- Smoothing.
- Reconstrucción.
- Ganancias y polaridad.
- Parámetros de separación.
- Tratamiento de canales.
- Operaciones de alineación.

No modificar estos elementos como consecuencia indirecta de una corrección de infraestructura.

Cualquier modificación DSP requiere una tarea específica, diagnóstico independiente y autorización explícita.

La igualdad algebraica o una reconstrucción numéricamente perfecta no demuestra por sí sola una separación perceptualmente correcta.

6. PRINCIPIOS DE AUDIO Y PROCESAMIENTO

El proyecto prioriza:

1. Fidelidad al Mix original.
2. Naturalidad tímbrica.
3. Conservación de dinámica.
4. Preservación de la espacialidad estéreo.
5. Reducción de bleeding perjudicial.
6. Ausencia de degradaciones innecesarias.

Reglas permanentes:

- No convertir silenciosamente estéreo a mono.
- No intercambiar canales L/R.
- No asumir que ambos canales contienen información idéntica.
- No truncar archivos para forzar compatibilidad.
- No resamplear automáticamente.
- No normalizar.
- No modificar ganancia o polaridad.
- No aplicar limitación, EQ, dither o procesamiento adicional sin autorización.
- No asumir equivalencias entre stems por sus nombres.
- No confundir una métrica favorable con una mejora perceptual.

El Mix original es la referencia fundamental.

Los resultados de SDV, SDI y SDV+SDI deben evaluarse por separado. La decisión perceptual final corresponde al usuario.

7. SEGURIDAD DE LECTURA E INTEGRIDAD DE ARCHIVOS

Para cualquier trabajo sobre lectura de audio:

- Validar WAV y FLAC sin conversiones innecesarias.
- Conservar frecuencia de muestreo, canales y frames.
- Comprobar finitud de muestras.
- Detectar archivos corruptos o modificados.
- Evitar reaperturas inseguras por ruta después de validar un descriptor.
- No aceptar verificaciones positivas fabricadas después de una excepción.
- No publicar resultados definitivos antes de superar las verificaciones finales.
- No eliminar archivos ajenos durante abortos o errores.
- Identificar claramente archivos parciales y resultados incompletos.

Las comprobaciones de integridad deben demostrar lo que realmente verifican.

No afirmar que existe identidad PCM cuando no se dispone de datos PCM reales y comparables.

8. ENTORNOS Y COMPATIBILIDAD

Distinguir siempre entre:

- Linux x86_64.
- Android ARM64 mediante Termux.
- Otros entornos de ejecución.

Una prueba exitosa en Linux x86_64 no demuestra compatibilidad con Termux ARM64.

Documentar versiones de Python, bibliotecas, dependencias y características del entorno cuando sean relevantes.

No imponer límites arbitrarios de memoria o duración sin mediciones reales.

No asumir que una biblioteca o mecanismo disponible en un entorno funciona de la misma manera en otro.

9. PRUEBAS Y EVIDENCIA

Toda afirmación técnica debe clasificarse cuando corresponda:

- `DOCUMENTED_FACT`: hecho respaldado documentalmente.
- `EXPERIMENTAL_RESULT`: resultado obtenido mediante ejecución.
- `THEORETICAL_DEDUCTION`: deducción técnica razonada.
- `HYPOTHESIS`: hipótesis pendiente de demostrar.
- `UNKNOWN`: información desconocida o no verificada.

Los informes deben diferenciar:

1. Pruebas diseñadas.
2. Pruebas ejecutadas.
3. Pruebas aprobadas.
4. Pruebas fallidas.
5. Pruebas no ejecutadas.
6. Limitaciones de cobertura.

No inventar resultados, hashes, logs, commits ni verificaciones.

No utilizar reconstrucción algebraica, SI-SDR, correlación u otra métrica aislada como certificado universal de calidad perceptual.

10. DOCUMENTACIÓN Y ENTREGABLES

Cada etapa debe producir documentación suficiente para que otro agente pueda auditar el trabajo sin depender de explicaciones verbales.

El informe debe incluir:

- Objetivo.
- Rama y commit base.
- Archivos inspeccionados.
- Archivos modificados.
- Diagnóstico.
- Cambios realizados.
- Pruebas ejecutadas.
- Resultados.
- Limitaciones.
- Riesgos pendientes.
- SHA-256 de entregables relevantes.
- Commit final.
- Enlaces directos a GitHub.

Formato preferido: Markdown (`.md`).

No generar ZIP, RAR, TAR u otros paquetes comprimidos como método de entrega habitual.

No obligar al usuario a descargar paquetes para que ChatGPT pueda inspeccionar el trabajo.

Cuando sea posible, proporcionar enlaces directos a los archivos y commits de GitHub.

Los informes deben estar dirigidos a facilitar la auditoría técnica de ChatGPT, no a trasladar al usuario la interpretación de resultados complejos.

11. COORDINACIÓN ENTRE AGENTES

Los agentes deben respetar la separación de responsabilidades:

- **Arena:** experimentación técnica, implementación autorizada y pruebas controladas.
- **Gemini:** análisis, documentación, experimentación independiente y tareas compatibles con su entorno.
- **ChatGPT (Cris):** revisión arquitectónica, auditoría independiente, contraste de evidencias y recomendaciones.
- **Propietario:** decisiones finales y autorización de modificaciones e integraciones.

Ningún agente debe asumir que el trabajo de otro agente está aprobado por el simple hecho de existir en GitHub.

Antes de continuar una etapa anterior, consultar su informe y verificar el estado real del repositorio.

Evitar modificaciones simultáneas sobre los mismos archivos.

12. REGLA FINAL

La prioridad del proyecto no es producir más código ni completar etapas rápidamente.

La prioridad es construir un sistema técnicamente confiable, reproducible, verificable y que preserve la integridad del material musical.

Ante una duda importante:

**Detenerse, documentar el problema y solicitar autorización.**

Es preferible no implementar una mejora todavía que introducir una modificación cuya seguridad, equivalencia o impacto sobre el DSP no pueda demostrarse.

**FIN DEL DOCUMENTO**

**Estado:** Aprobado por el propietario para su incorporación al repositorio, sujeto a las condiciones de autorización e implementación aquí establecidas.
