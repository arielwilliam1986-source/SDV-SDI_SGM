# Reserva sintética posterior al congelamiento

Independiente respecto del ajuste del candidato: no usa estímulos ni oráculos de 6D. No equivale a una validación por un tercero. La semilla, fórmulas de construcción y expectativas por caso están en `scripts/validar.py`; el repositorio conserva la receta y los SHA-256 de los WAV en vez de binarios reproducibles. Los casos son controles de un segundo, con ruido discreto, DC, impulsos periódicos, réplicas, silencio y mutaciones de contenedor; comparten portadoras y no son 51 observaciones estadísticamente independientes.

**Atribución: 42/51; CLI: 39/39 en la matriz ejecutada.** Los tres motores coincidieron en los tres fallos. La reproducción no oculta fallos: la matriz incluye `ok=False`, y la salida del script confirma que la ejecución terminó, no que todos los oráculos pasaron.

| Caso | Esperado | Observado |
|---|---|---|
| `right_rival` | AMBIGUOUS | UNIQUE, `k=0`, ALIGNED: bloqueante |
| `shift` | UNIQUE, `k=-567` | INSUFFICIENT_SIGNAL: abstención conservadora |
| `different_lr` | AMBIGUOUS | INSUFFICIENT_SIGNAL: abstiene sin identificar el conflicto |

La geometría de ventanas completas excluye candidatos que de otro modo necesitarían solape parcial al borde. Réplicas débiles pueden quedar bajo la cota incluso tras la proyección. No se optimizó sobre estos resultados. Requerir nueva reserva después de cualquier cambio, incluyendo cobertura de recortes, controles de largo alcance, tasa de falsos positivos en señales correlacionadas y réplicas con niveles variados. No se ensayaron canciones ni se pretende generalizar.

Desde este directorio, con Python 3.11:

```sh
python -m venv /tmp/sdv6e-env
/tmp/sdv6e-env/bin/pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 /tmp/sdv6e-env/bin/python scripts/validar.py
```

La ejecución regenera evidencias e incluye tiempos y rutas temporales que pueden variar. Para comprobar un expediente publicado sin regenerarlo: `sha256sum -c SHA256SUMS.txt`.
