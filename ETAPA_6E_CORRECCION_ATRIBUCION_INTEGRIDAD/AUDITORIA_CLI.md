# CLI

39/39 expectativas de proceso en la batería: se comprobaron código de salida y presencia de WAV e informe. Los casos `dual`, `unrelated` y `silent` vetados por defecto, y los archivos truncados y con NaN vetados incluso con permiso. `dual` puede continuar explícitamente sin cambio del diagnóstico ni shift. MQR ya no acepta una confirmación interactiva como sustituto del flag para vetos temporales. Las modalidades y permisos heredados que no ejecutan DSP no equivalen a una auditoría de alineación.

**Límite bloqueante:** el veto depende del diagnóstico. El falso `ALIGNED` de `right_rival` en el estimador no sería vetado por su diagnóstico vocal. No se certifica el bloqueo de todas las ambigüedades físicas. No se ejecutaron en este expediente pruebas de carrera de sustitución del archivo, pruebas interactivas de extremo a extremo ni toda la matriz de modos. Los argumentos, manifest por ejecución, stdout, stderr e informes nativos están en `evidence/ejecuciones.json`.
