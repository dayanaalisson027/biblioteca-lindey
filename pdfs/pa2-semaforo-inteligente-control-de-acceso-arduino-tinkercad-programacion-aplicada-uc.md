---
titulo: Evaluación Parcial PA2 de Programación Aplicada: semáforo inteligente y control de acceso con Arduino en Tinkercad
curso: Programación Aplicada
universidad: UC
tipo: Evaluación
archivo: pa2-evaluacion-parcial-programacion-aplicada-uc.pdf
fecha: 2026-11-13
palabras: programación aplicada PA2, producto académico 2, evaluación parcial, Arduino Uno, Tinkercad, semáforo vehicular y peatonal, botón peatonal, digitalRead, estructuras de control, if switch for while, teclado matricial 4x4, LCD 16x2, LiquidCrystal, Keypad, verificarCodigo, mostrarMensaje, arreglos, microcontrolador, Universidad Continental
descripcion: Evaluación Parcial (Producto Académico 2) de Programación Aplicada, Universidad Continental: semáforo vehicular y peatonal inteligente y control de acceso por código con teclado 4x4 y LCD, en Arduino Uno con Tinkercad.
---
## Indicaciones

Utilice Tinkercad para la implementación del circuito y el programa correspondiente. Adjunte un video donde demuestre el funcionamiento de cada circuito implementado y los requerimientos funcionales.

Temas de la unidad: tipos de datos, entradas y salidas de datos, funciones y librerías, y arreglos.

## Problema 1: Semáforo vehicular y peatonal inteligente

Diseñar e implementar en Tinkercad un semáforo vehicular y peatonal inteligente utilizando un Arduino Uno. El sistema debe integrar los tres tipos de estructuras de control de la unidad:

- Estructura secuencial: ciclo normal del semáforo (rojo → verde → amarillo → rojo).
- Estructura selectiva (if / switch): detección de un botón peatonal que interrumpe el ciclo y activa una fase de cruce.
- Estructura repetitiva (for / while): parpadeo del LED peatonal verde durante 5 ciclos antes de pasar a rojo.

Requerimientos funcionales del programa:

- 1. El ciclo normal del semáforo vehicular debe ser: rojo (5 s) → verde (4 s) → amarillo (1 s).
- 2. Al presionar el botón peatonal, el sistema debe detectarlo con digitalRead() y una estructura if.
- 3. Al activarse la fase peatonal: vehículos pasan a rojo, peatones a verde parpadeante (for con 5 ciclos de 500 ms) y luego a rojo.
- 4. Usar al menos un bucle for o while para el parpadeo del LED peatonal verde.
- 5. El programa debe reiniciar el ciclo vehicular automáticamente al finalizar la fase peatonal.

## Problema 2: Control de acceso por código numérico

Implementar en Tinkercad un sistema de control de acceso por código numérico usando un Arduino Uno, un teclado matricial 4x4 y una pantalla LCD 16x2. El proyecto debe demostrar el manejo de los siguientes contenidos de la unidad:

- Tipos de datos: uso de int, char, String, bool y arreglos.
- Entradas y salidas: lectura de teclado (analogRead / digitalRead) y escritura en LCD (librería LiquidCrystal).
- Funciones y librerías: creación de funciones propias (verificarCodigo(), mostrarMensaje()) y uso de la librería Keypad.
- Arreglos: almacenamiento del código de acceso y del historial de intentos en arreglos.

Requerimientos:

- 1. Definir el código de acceso como un arreglo de caracteres: char codigoCorrecto[] = "1234".
- 2. Leer las teclas presionadas y almacenarlas en otro arreglo char intentoUsuario[4].
- 3. Implementar la función bool verificarCodigo() que compare los dos arreglos carácter a carácter con un bucle for.
- 4. Implementar la función void mostrarMensaje(String msg) que escriba en el LCD.
- 5. Mostrar en el LCD: "Ingrese codigo:" al inicio, "ACCESO OK" o "CODIGO INCORRECTO" según el resultado.
- 6. Encender el LED verde 2 s si el código es correcto; LED rojo 2 s si es incorrecto.
- 7. Guardar en un arreglo int historial[5] la cantidad de intentos fallidos consecutivos; bloquear el sistema a los 3 intentos seguidos mostrando "BLOQUEADO" en el LCD.

## Criterios de la rúbrica

Implementación del circuito, uso de variables, configuración de entradas y salidas, uso de estructuras de control selectivas (if, if-else, switch), uso de estructuras de control repetitivas (while, for) y uso de funciones, librerías y arreglos.
