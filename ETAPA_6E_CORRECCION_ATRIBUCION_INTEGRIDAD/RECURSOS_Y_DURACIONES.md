# Recursos medidos en Arena

La corrida duró unos 36.5 s en Linux x86_64, Python 3.11, con dos CPU visibles y bibliotecas numéricas configuradas a un hilo. RSS máxima del arnés 116628 KiB y máximo de hijos 138776 KiB según `getrusage` de Linux; no son suma de procesos ni presupuesto de RAM. Ver `evidence/recursos.json` y tiempos por CLI en `evidence/cli_dsp.json`.

Se decodifican pares completos y hay múltiples FFT por bloque; no se estableció un tope de duración de archivo ni se probó escala larga. La ventana de búsqueda heredada es un límite del modelo de reloj, no una estimación de capacidad de memoria. No hay medición de disco pico ni prueba de Termux ARM64. No se extrapolan tiempos, memoria ni capacidad a Termux.
