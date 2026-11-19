# Etapa 6E · Candidatos experimentales congelados

**Resultado: parcial. Atribución no aprobada.** La reserva reveló una falsa alineación ante una réplica débil exclusiva de R. Se detiene esa línea de corrección en el candidato congelado: no se reajusta con la reserva, no se lo promueve ni se recomienda su uso como validador fiable. El expediente también conserva las reparaciones comprobadas de integridad y de MQR.

- Base `ceae641aaa60e4545ac3ebadf393b01bf090b7ca`; rama `arena/9ce94b15-sdv-sdi-sgm`; verificación de escritura conservada.
- Implementación congelada en `b50d30e` antes de definir y ejecutar la nueva reserva. Tres copias de 6C y un módulo de evidencia común, sin integrar los pipelines. El [manifiesto](MANIFEST_6E.json) identifica fuentes, candidatos, semilla y huellas de los estímulos.
- El detector examina bloques contiguos y comprueba el retardo en dos mitades de cada bloque. Busca rivales también tras sustraer del **test estadístico** la proyección de la copia dominante; jamás sustrae muestras de las entradas del DSP. Requiere cobertura y concordancia; usa autocorrelación y una cota heurística de Fisher con multiplicidad por búsqueda y cobertura. No es una garantía estadística sobre audio correlacionado o estacionariedad por tramos.
- `attribution`: `UNIQUE`, `AMBIGUOUS`, `INSUFFICIENT_SIGNAL`, `NON_INFORMATIVE` o `ERROR`. Sólo `UNIQUE` tiene un retardo; por separado, `classification` conserva `ALIGNED`, `WARNING` o `MISALIGNED` para indicar magnitud de un retardo estimado. Convención `k=-d`. No hay corrección de reloj ni polaridad.
- Cambios de integración detallados por símbolo en [auditoría AST](evidence/auditoria_ast.json); el diff contra 6C se obtiene comparando los mismos nombres en `motores/`. Se conservaron los auxiliares históricos de 6C para minimizar el diff; el camino activo usa `measure`.

Sin canciones reales, selección de motor, integración ni promoción. Se entrega para auditoría independiente.
