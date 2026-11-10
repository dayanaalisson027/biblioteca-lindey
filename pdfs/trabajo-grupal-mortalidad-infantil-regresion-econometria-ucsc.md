---
titulo: Trabajo grupal: problema econométrico y mortalidad infantil con regresión múltiple
curso: Econometría
universidad: UCSC
tipo: Trabajo grupal
archivo: trabajo-grupal-econometria-ucsc.pdf
fecha: 2026-11-09
palabras: econometría, regresión lineal simple, regresión múltiple, mortalidad infantil, Gujarati tabla 6.4, child_mortality, prueba t, prueba F, R2 ajustado, VIF, Breusch-Pagan, White, heterocedasticidad, errores robustos, RStudio
descripcion: Trabajo de aplicación econométrica (UCSC): plantear un modelo de regresión con fuentes de datos y estimar en R la mortalidad infantil de 64 países (Gujarati 6.4) con pruebas t, F, VIF, Breusch-Pagan y errores robustos.
---
## Pregunta 1. Planteamiento de un problema econométrico (20 puntos)

Planteen un problema econométrico que pueda estudiarse con un modelo de regresión. Puede referirse a Chile, a la Región del Biobío o a otro contexto, y a temas como el mercado laboral, el consumo, las ventas de una empresa, la educación, la salud, el medio ambiente o las finanzas personales.

- a) (3 puntos) Pregunta de investigación. Formulen la pregunta que quieren responder y expliquen por qué es relevante y para quién sería útil la respuesta.
- b) (4 puntos) Variables. Definan la variable dependiente y al menos tres variables explicativas, incluyendo al menos una variable dummy. Para cada una, indiquen su unidad de medida y el signo esperado de su coeficiente, con una justificación económica.
- c) (3 puntos) Modelo. Escriban la función de regresión poblacional, incluyendo el término de error.
- d) (2 puntos) Tipo de datos. Indiquen si se trataría de datos de corte transversal, de series de tiempo o de panel, cuál sería la unidad de observación (personas, hogares, empresas, comunas, países, meses, etc.) y el período que se estudiaría.
- e) (5 puntos) Fuentes de datos. Propongan al menos dos bases de datos reales que podrían utilizar. Para cada una, indiquen: nombre, institución responsable, enlace, qué variables de su modelo contiene y qué limitaciones tiene. Si alguna variable no está disponible, expliquen cómo la reemplazarían.
- f) (3 puntos) Posibles problemas. Considerando los supuestos del modelo lineal clásico, indiquen qué problemas econométricos podrían aparecer en su modelo (por ejemplo, multicolinealidad, heterocedasticidad, autocorrelación o una forma funcional incorrecta), por qué podrían ocurrir y cómo los detectarían.

## Pregunta 2. Mortalidad infantil y desarrollo (40 puntos)

Se desea estudiar qué factores explican las diferencias en mortalidad infantil entre países. Se dispone de datos de 64 países (Gujarati y Porter, Econometría, 5.ª ed., Tabla 6.4), que se entregan en el archivo child_mortality.csv, con las variables CM (mortalidad infantil: muertes de menores de 5 años por cada 1.000 nacidos vivos), FLR (tasa de alfabetización femenina, en porcentaje), PGNP (producto nacional bruto per cápita en 1980, en dólares) y TFR (tasa global de fecundidad 1980–1985: número promedio de hijos por mujer). Las estimaciones se realizan en RStudio u otro software estadístico (Stata, Gretl o Python).

### 2.1 Regresión simple (6 puntos)

- a) (2 puntos) Elaboren un diagrama de dispersión con PGNP en el eje horizontal y CM en el eje vertical. ¿Qué tipo de relación observan? ¿Parece lineal?
- b) (2 puntos) Estimen el modelo CMi = β1 + β2·PGNPi + ui. Escriban la función de regresión muestral con los errores estándar bajo cada coeficiente e interpreten β̂2.
- c) (2 puntos) Agreguen al diagrama de dispersión la recta de regresión estimada. ¿Se ajusta bien la recta a los datos? ¿Observan algún país que se aleje mucho del resto?

### 2.2 Regresión múltiple (8 puntos)

Se agrega la tasa de alfabetización femenina: CMi = β1 + β2·PGNPi + β3·FLRi + ui.

- a) (2 puntos) Antes de estimar, indiquen el signo esperado de β2 y de β3 y justifíquenlo.
- b) (2 puntos) Estimen el modelo y escriban la función de regresión muestral con los errores estándar bajo cada coeficiente.
- c) (2 puntos) Interpreten cada coeficiente de pendiente. ¿Qué significa "manteniendo constantes las demás variables" en este contexto?
- d) (2 puntos) Interpreten el R² y el R² ajustado.

### 2.3 Inferencia (6 puntos)

Utilizando el modelo de 2.2:

- a) (3 puntos) Planteen las hipótesis y realicen la prueba t de significancia individual para cada coeficiente de pendiente.
- b) (3 puntos) Planteen las hipótesis e interpreten la prueba F de significancia global.

### 2.4 Ampliación del modelo (6 puntos)

- a) (3 puntos) Agreguen la tasa global de fecundidad (TFR) al modelo de 2.2. Interpreten su coeficiente y su significancia.
- b) (3 puntos) Comparen este modelo con el de 2.2 utilizando el R² ajustado. ¿Qué modelo prefieren? Justifiquen.

### 2.5 Validación del modelo (8 puntos)

Para el modelo de 2.2:

- a) (2 puntos) Grafiquen los residuos (ûi) contra los valores estimados (CM̂i). ¿Observan algún patrón en su dispersión?
- b) (4 puntos) Apliquen e interpreten las pruebas de multicolinealidad (VIF) y heterocedasticidad (Breusch-Pagan y/o White). Para cada prueba, indiquen la hipótesis nula y su conclusión.
- c) (2 puntos) Estimen el modelo con errores estándar robustos a la heterocedasticidad y compárenlos con los de 2.2. ¿Cambian los coeficientes? ¿Cambian las conclusiones sobre significancia? ¿Era necesaria esta corrección?

### 2.6 Análisis final (6 puntos)

- a) (3 puntos) ¿Qué modelo recomendarían para explicar la mortalidad infantil? ¿Qué tan bien la explica? Justifiquen con los resultados obtenidos.
- b) (3 puntos) A partir de sus resultados, propongan una política pública para reducir la mortalidad infantil. ¿Qué limitaciones tiene su recomendación?
