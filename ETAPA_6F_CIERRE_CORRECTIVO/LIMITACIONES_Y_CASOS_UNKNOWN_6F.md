# Etapa 6F · Limitaciones y casos fuera de capacidad

Registro de lo que 6F **no** puede sostener. No hay garantía de unicidad
absoluta: se documenta lo detectado y lo que queda fuera de capacidad.

## 1. Ambigüedades fuera de capacidad

| Situación | Comportamiento 6F | Fundamento |
|---|---|---|
| Réplica por debajo del piso (≈0,05–0,09 según duración) | `UNIQUE` con `replica_detection_floor` publicado, o abstención si el piso > 0,35 | el estadístico no puede separarla del nulo |
| Guía periódica o de banda estrecha (tonos, bucles) | `AMBIGUOUS` siempre | la autocorrelación de la guía es ≈1 en el retardo candidato |
| Réplica que sólo aparece en una mitad del archivo | `RIVAL_NOT_CORROBORATED`; la ventana no cuenta como medida | no se acepta un único testimonio |
| Retardo mayor que la ventana de búsqueda (±30 s) o que el solape disponible | no examinado; cobertura < 1 publicada | límite de plantilla |
| Diferencia L/R con un canal insuficiente | abstención parcial (`partial.measured`) | no se infiere del otro canal |
| Contenido no estacionario con guía que cambia de carácter | puede declararse `AMBIGUOUS` pese a existir un retardo dominante por tramo | se publica `piecewise` cuando aplica |
| Silencio, DC o constante | `NON_INFORMATIVE` | no hay información de reloj |
| Muestras no finitas | `ERROR`, bloqueo incondicional | no se procesa |

## 2. Afirmaciones que 6F **no** hace

* No afirma que la validación WAV elimine la manipulación concurrente: sólo la
  detecta cuando el objeto cambia (identidad, SHA-256, tamaño).
* No afirma que `UNIQUE` signifique «no existe réplica»: significa «no se
  detectó réplica por encima del piso publicado».
* No afirma aptitud de producción, ni elige motor ganador, ni integra nada en el
  orquestador.
* No afirma que 6F sea estable en archivos largos ni en Termux ARM64.
* No afirma que las tres coincidencias de motores sean tres validaciones
  independientes: comparten `atribucion_6f.measure`.

## 3. Cobertura no realizada

* Canciones reales: prohibidas en esta etapa.
* Modos de CLI distintos de `full_processing` (`dry_run`, `analysis_only`,
  `single_file`, `self_test`) no se auditaron en 6F.
* Archivos > 2 GB, RF64, multicanal > 2, WAV con `channel mask` no FL/FR.
* Carreras TOCTOU durante una corrida CLI completa (sólo a nivel de módulo).
* Barrido fino de `σ_ρ`, del umbral `z`, del solape 50 % y del criterio de
  corroboración: se fijaron con el conjunto de desarrollo y no se optimizaron.
* Cerca de Mid ≈ 0 (no exactamente 0) en MQR: no caracterizado.
* El ajuste de escala de guías (`g_vocal`, `g_instr`) queda como estaba en 6E.

## 4. Riesgos residuales

1. **Falso `UNIQUE` por réplica bajo el piso**: mitigado con el piso publicado,
   no eliminado. El caso `res_replica_bajo_piso` admite ambos resultados para no
   ocultar el límite.
2. **Falso `AMBIGUOUS` en material periódico**: se prefiere abstención a una
   afirmación errónea; el coste es que material musical con bucles nunca se
   procesará sin permiso explícito.
3. **Carga en memoria** proporcional a la duración; no medida a escala real.
4. **Acoplamiento** de los tres motores al mismo estimador compartido.
