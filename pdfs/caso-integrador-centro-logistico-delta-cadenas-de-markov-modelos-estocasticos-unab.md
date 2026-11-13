---
titulo: Caso integrador Centro Logístico Delta: cadenas de Markov, proceso de Poisson y distribución triangular
curso: Modelos Estocásticos
universidad: UNAB
tipo: Evaluación
archivo: caso-integrador-centro-logistico-delta-unab.docx
fecha: 2026-11-13
palabras: Centro Logístico Delta, caso integrador, modelos estocásticos, optimización en redes, cadena de Markov en tiempo discreto, matriz de transición, distribución estacionaria, tiempo medio de recurrencia, Chapman-Kolmogorov, proceso de Poisson, 15 pedidos por hora, distribución triangular, proceso de renovación, aproximación normal, simulación, UNAB Chile, Universidad Andrés Bello
descripcion: Caso integrador Centro Logístico Delta (UNAB, Chile): cadena de Markov de cuatro estados con distribución estacionaria y tiempo de recurrencia, llegadas Poisson de 15 pedidos por hora y fallas con distribución triangular y proceso de renovación.
---
## Caso integrador: Centro Logístico Delta

El Centro Logístico Delta S.A. es una empresa dedicada a la distribución nacional de productos farmacéuticos que enfrenta importantes niveles de variabilidad en su operación diaria. Los registros históricos muestran que los pedidos llegan de manera irregular, con un promedio cercano a 15 pedidos por hora, lo que provoca que, según el momento del día, el centro pueda encontrarse en periodos de baja carga, carga media o alta carga, especialmente antes de los despachos programados cada 30 minutos. Además, el equipo de clasificación presenta fallas ocasionales, generando un cuarto estado operativo en el que el sistema queda detenido hasta completar la reparación.

Durante un proceso interno de levantamiento de información, los analistas registraron cómo el sistema cambiaba entre estos cuatro estados en intervalos consecutivos de tiempo. Cuando el centro está en baja carga, aproximadamente un 60% de las veces se mantiene igual, un 30% pasa a carga media y un 10% a carga alta. En carga media, cerca de un 50% de los intervalos permanece igual, un 20% baja a baja carga, otro 20% sube a alta carga y un 10% termina en falla. En alta carga, el sistema tiende a mantenerse en ese estado el 40% de las veces, bajar a carga media un 30%, bajar a baja carga un 10% y fallar un 20%. Finalmente, cuando el sistema está en falla, alrededor de un 30% de los intervalos vuelve a baja carga, un 30% a carga media, un 20% a alta carga y un 20% permanece fallado.

La llegada de pedidos ocurre de manera aleatoria pero con un patrón estadístico estable, en promedio alrededor de 15 pedidos por hora. Los pedidos no tienden a agruparse ni a llegar en lotes grandes, sino que ocurren de manera independiente entre sí, lo que ha permitido describir su comportamiento mediante un proceso de conteo que modela cuántas solicitudes ingresan en intervalos específicos, como los 30 minutos que transcurren entre la salida de un camión y el siguiente.

El equipo de mantenimiento ha registrado los tiempos (en minutos) entre la reparación de una falla del sistema de clasificación y la aparición de la siguiente: en los periodos más estables los equipos han operado poco más de 2,6 minutos antes de volver a fallar, mientras que en momentos de mayor exigencia se han registrado intervalos cercanos a 17,3 minutos; el intervalo más frecuente se ubica cerca de los 10 minutos. Por ello se decidió modelar los tiempos entre fallas mediante una distribución triangular.

## Pregunta 1. Análisis de la incertidumbre y selección del modelo

Examine los principales factores de incertidumbre que afectan la operación del Centro Logístico Delta y explique cómo cada uno influye en la eficiencia del sistema y en la optimización de la red logística. Seleccione un modelo estocástico (analítico o de simulación) que permita representar adecuadamente el comportamiento del sistema y analizar distintos escenarios operativos. Incluya un diagrama o esquema que represente su propuesta y argumente por qué este modelo resulta más adecuado que otras alternativas.

## Pregunta 2. Modelación probabilística del sistema

- 1. Formule un modelo probabilístico integrado que describa la dinámica del sistema. Modele la evolución operativa del Centro Logístico Delta mediante una cadena de Markov en tiempo discreto. Identifique los estados relevantes del sistema, construya el diagrama de transiciones y elabore la matriz de transición asociada. Determine la distribución estacionaria del sistema e interprete los resultados en el contexto operativo del centro. Finalmente, calcule el tiempo medio de recurrencia del estado que represente condiciones de alta carga y explique el significado de este valor para la gestión del sistema.
- 2. Con los tiempos entre fallas modelados mediante una distribución triangular, determine el valor esperado y la varianza del intervalo entre fallas y proyecte cuántas interrupciones podrían registrarse durante una jornada típica de 420 minutos de operación continua. Evalúe la probabilidad de que el sistema experimente 40 o más fallas en dicho periodo, utilizando una aproximación normal del proceso de renovación, y estime cuántas fallas podrían esperarse en un horizonte de 2.500 minutos de funcionamiento, con una confianza del 95%, para apoyar la planificación de la mantención preventiva.

## Condiciones de entrega

Evaluación sumativa individual, ponderación 30%. Documento Word de máximo 6 páginas, sin anexos; se evalúa con rúbrica.
