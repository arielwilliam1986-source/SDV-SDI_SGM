# MQR · división indefinida al finalizar

La métrica histórica reporta pico L/R dividido por RMS de Mid. Con Mid cero, el cociente no está definido, sea el pico cero o positivo. Se conserva el cociente para denominadores positivos y se reporta JSON `null` en caso contrario (sin epsilon y sin sustituir Mid por RMS de canales). Se aplica de forma explícita también a la cresta de niveles streaming. No se modifica el cálculo de audio.

En controles sintéticos `side` y `side_output`, original y 6C devolvieron 2; 6E devolvió 0 y completó informe y WAV. En `side` no se necesitó override y la validación MQR fue `pass`; en `side_output` se usó override y la validación técnica fue `fail`, que no equivale a un aborto de procesamiento. Las crestas Mix y SDV son nulas en los informes de esos controles. No se ejecutó el estímulo histórico S7 de 6D ni se equiparan los WAV parciales de un aborto con entregas finales.
