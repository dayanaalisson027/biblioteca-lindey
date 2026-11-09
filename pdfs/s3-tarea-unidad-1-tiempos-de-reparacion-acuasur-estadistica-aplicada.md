---
titulo: Tarea S3 (Unidad 1): tiempos de reparación en AcuaSur con Infostat
curso: Estadística Aplicada
universidad: IACC
tipo: Tarea
archivo: s3-estadistica-aplicada-iacc.pdf
fecha: 2026-11-09
palabras: estadística descriptiva, población y muestra, tipos de variables, tabla de frecuencias, histograma, media mediana moda, cuartiles, percentil 90, box plot, varianza, desviación estándar, coeficiente de variación, Infostat
descripcion: Tarea de Estadística Aplicada (IACC, semana 3, unidad 1): caso AcuaSur con 20 órdenes de trabajo; frecuencias, tendencia central, cuartiles, percentil 90, box plot y dispersión en Infostat.
---
## Caso: tiempos de reparación en los centros de cultivo de AcuaSur

AcuaSur es una empresa acuícola ficticia que opera once centros de cultivo de salmón en la Región de Los Lagos, a entre 40 minutos y dos horas de navegación desde Puerto Montt. Cada centro depende de bombas de alimentación, aireadores, compresores de oxígeno y generadores diésel que funcionan de manera continua. El área de mantenimiento, con 23 técnicos repartidos en turnos de día y de noche, registra cada intervención en una orden de trabajo (OT).

Durante el último semestre se registraron 286 OT correctivas. La jefatura de mantenimiento recibió reclamos de los jefes de centro: cuando un aireador queda detenido de noche, la concentración de oxígeno en las balsas baja en pocas horas y la mortalidad de peces sube. El contrato con la aseguradora exige que el 90 % de las reparaciones correctivas se cierre en seis horas o menos, y nadie en la empresa sabe con certeza si hoy se cumple esa meta. En el turno de noche, además, trabaja menos personal y el traslado en lancha es más lento.

La jefatura te encarga, en tu rol dentro del área de mantenimiento, analizar una muestra aleatoria de 20 OT del semestre, que se presenta en la Tabla 1. Tu informe debe describir cuánto se demoran las reparaciones, qué tan estables son esos tiempos y si la meta del contrato se está cumpliendo, procesando los datos en Infostat.

Con la aseguradora pidiendo cifras antes de renovar la póliza, ¿qué dirían estos 20 registros sobre la forma en que hoy responde el equipo de mantenimiento?

### Tabla 1. Muestra de 20 órdenes de trabajo correctivas de AcuaSur

| N° OT | Equipo | Tipo de falla | Turno | Repuestos usados | Horas de reparación |
|---|---|---|---|---|---|
| OT-1051 | Compresor de oxígeno | Mecánica | Día | 4 | 2,0 |
| OT-1064 | Aireador | Eléctrica | Noche | 2 | 5,0 |
| OT-1077 | Aireador | Eléctrica | Día | 1 | 1,8 |
| OT-1090 | Aireador | Eléctrica | Noche | 4 | 4,5 |
| OT-1103 | Compresor de oxígeno | Instrumentación | Día | 3 | 5,6 |
| OT-1116 | Aireador | Mecánica | Noche | 4 | 2,2 |
| OT-1129 | Aireador | Hidráulica | Día | 2 | 2,9 |
| OT-1142 | Bomba de alimentación | Hidráulica | Noche | 1 | 3,8 |
| OT-1155 | Aireador | Mecánica | Día | 2 | 1,5 |
| OT-1168 | Bomba de alimentación | Mecánica | Noche | 2 | 6,2 |
| OT-1181 | Bomba de alimentación | Hidráulica | Día | 1 | 2,6 |
| OT-1194 | Aireador | Mecánica | Noche | 0 | 2,3 |
| OT-1207 | Compresor de oxígeno | Eléctrica | Día | 1 | 6,8 |
| OT-1220 | Compresor de oxígeno | Eléctrica | Noche | 0 | 14,5 |
| OT-1233 | Aireador | Instrumentación | Día | 0 | 3,4 |
| OT-1246 | Compresor de oxígeno | Eléctrica | Noche | 3 | 3,8 |
| OT-1259 | Aireador | Hidráulica | Día | 1 | 3,0 |
| OT-1272 | Generador diésel | Eléctrica | Noche | 1 | 4,6 |
| OT-1285 | Bomba de alimentación | Eléctrica | Día | 3 | 5,4 |
| OT-1298 | Bomba de alimentación | Eléctrica | Noche | 2 | 4,2 |

Fuente: elaboración propia.

## Pregunta 1

Identifica los conceptos básicos de estadística presentes en el estudio que te encargó AcuaSur.

- a) Señala cuál es la población y cuál es la muestra del estudio, indicando el tamaño de cada una.
- b) Clasifica cada una de las cinco variables de la Tabla 1 (sin contar el N° OT) como cualitativa nominal, cualitativa ordinal, cuantitativa discreta o cuantitativa continua.
- c) Justifica la clasificación que asignaste a las variables repuestos usados y horas de reparación.
- d) Explica una limitación de concluir sobre todas las OT del semestre a partir de esta muestra.

## Pregunta 2

Construye en Infostat las tablas de distribución de frecuencias y los gráficos que describen la muestra.

- a) Construye la tabla de frecuencias de la variable tipo de falla, con frecuencia absoluta, relativa y porcentual.
- b) Construye la tabla de frecuencias de horas de reparación agrupada en intervalos, indicando cuántos intervalos usaste y su amplitud.
- c) Elabora un gráfico de sectores (circular) para tipo de falla, seleccionando categorías en filas, y un histograma para horas de reparación, e incorpora las capturas de Infostat.
- d) Indica qué tipo de falla concentra más OT y en qué intervalo se ubica la mayor cantidad de reparaciones.

Procedimiento sugerido: Infostat → Estadísticas → Frecuencias ("Tipo de falla") → Gráficos → Sectores (categorías en filas); luego Frecuencias de "Horas de reparación" con 5 intervalos → Gráficos → Histograma.

## Pregunta 3

Calcula las medidas de tendencia central de las horas de reparación por medio de Infostat y planillas de cálculo.

- a) Calcula la media, la mediana y la moda de las horas de reparación e incorpora la salida del software.
- b) Calcula nuevamente la media sin considerar la OT-1220 y compara ambos resultados.
- c) Determina cuál de las tres medidas representa mejor el tiempo típico de reparación en este caso y justifica tu elección con los resultados obtenidos.

## Pregunta 4

Determina las medidas de posición de las horas de reparación utilizando las funciones estadísticas de Infostat.

- a) Determina el primer, segundo y tercer cuartil, e interpreta cada uno en horas de reparación.
- b) Determina el decil 9 y el percentil 90.
- c) Compara el percentil 90 con la meta de seis horas e indica si la muestra sugiere que la meta se cumple.
- d) Señala cuántas de las 20 OT superan la meta y qué porcentaje representan.

## Pregunta 5

Representa la distribución de las horas de reparación mediante box plot en Infostat o en una planilla de cálculo.

- a) Elabora el box plot de las horas de reparación de la muestra completa e incorpora la captura.
- b) Identifica en el gráfico si existen valores atípicos y a qué OT corresponden.
- c) Elabora un box plot por turno (día y noche) y compara sus medianas y la longitud de sus cajas.
- d) Describe si la distribución es simétrica o asimétrica y qué significa eso para la planificación del mantenimiento.

## Pregunta 6

Relaciona la variabilidad de las horas de reparación interpretando el rango, la varianza y la desviación estándar obtenidos en Infostat.

- a) Calcula el rango, la varianza y la desviación estándar de la muestra completa e incorpora la salida de Infostat.
- b) Calcula la desviación estándar y el coeficiente de variación de cada turno.
- c) Compara la dispersión absoluta y relativa entre turnos e indica cuál tiene tiempos más estables.
- d) Formula una recomendación a la jefatura de AcuaSur a partir de la relación entre la variabilidad observada y el cumplimiento de la meta.

## Indicadores de evaluación

- Identifica conceptos básicos de estadística, a partir de la distinción entre población, muestra y variables.
- Construye tablas de distribución de frecuencias y gráficos a partir de conjuntos de datos simples, considerando Infostat.
- Calcula medidas de tendencia central (media, mediana y moda) por medio de Infostat y planillas de cálculo.
- Determina medidas de posición (cuartiles, deciles y percentiles) con funciones estadísticas en Infostat.
- Representa la distribución de datos mediante box plot en Infostat y/o planillas de cálculo.
- Relaciona la variabilidad de un conjunto de datos interpretando el rango, la varianza y la desviación estándar obtenidos en Infostat.
