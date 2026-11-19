# Estéreo L/R

El detector mide cada canal por separado y nunca usa Mid. Sólo agrega un retardo si cada canal tiene uno, y si éstos son exactamente iguales. Una ambigüedad detectada por un canal no es resuelta por el otro; un canal insuficiente impide la afirmación conjunta. Un error domina. La cobertura se registra por canal y bloque en `evidence/atribucion.json`.

`side` (L=-R) es informativo y da UNIQUE ambos canales con k=0. `side_output` muestra L alineado y R insuficiente. En `different_lr` L quedó alineado y R insuficiente por cobertura; no se inferió un reloj común. En `right_rival` R **no detectó** su réplica y el agregado fue falsamente ALIGNED. No confundir una regla de agregación conservadora con la detección fiable de todos los rivales.
