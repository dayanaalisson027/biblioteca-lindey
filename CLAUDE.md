# Biblioteca Lindey — instrucciones para Claude

Sitio estático bilingüe (es/en) de Lindey Asesoramiento Universitario.
Público en **https://solucionariouni.com** (GitHub Pages, repo `elsolucionario/biblioteca-lindey`).
`build.py` genera `_site/` y GitHub Actions (`.github/workflows/publicar.yml`) lo publica en cada push a `main` (2–3 min).

## Reglas de la dueña (no romperlas)

- **Si te da imágenes → se publican como imágenes** (ejercicio = imagen + enunciado en texto). Nunca convertir imágenes en PDF.
- **Si te da PDF o Word → van al repositorio de PDFs** (`pdfs/`). La marca de agua LINDEY, la protección, el visor tipo revista y el contador de vistas se generan solos.
- El botón y los avisos dicen **"PIDE TU SOLUCIONARIO"** (en inglés "GET YOUR SOLUTION"), nunca "asesoría".
- Todo se publica en español e inglés.
- No tocar los registros DNS de Hostinger (incluido el TXT `google-site-verification`) ni el dominio en `sitio.json`.

## Agregar un ejercicio (imágenes)

1. Copiar la imagen a `imagenes/` con nombre `Lindey_<Curso>_<UNIVERSIDAD>_Pregunta<N>.jpg` (sin tildes ni espacios).
   Si hay imagen de solución: `Lindey_<Curso>_<UNIVERSIDAD>_Solucion_P<N>.jpg` y en el .md `solucion_imagen:`.
2. Crear `ejercicios/<tema>-<universidad>-pregunta-<n>.md` copiando `ejercicios/_PLANTILLA.md`.
   Leer la imagen y **transcribir el enunciado completo** (más "Datos de la figura:" si hay valores solo en el dibujo),
   y escribir la versión en inglés debajo de `[en]` con `tema_en` y `palabras_en`.
3. `fecha:` = día de hoy (AAAA-MM-DD).

## Agregar un PDF o Word

1. Copiar el archivo a `pdfs/` con nombre en minúsculas y guiones.
2. Crear `pdfs/<mismo-nombre>.md` copiando `pdfs/_PLANTILLA.md` (`titulo`, `curso`, `universidad`, `tipo`, `archivo`, `fecha`, `palabras`, `descripcion`).
3. Debajo del front matter, transcribir solo **el caso/enunciado y lo que pide cada pregunta** con `## Pregunta N`
   (si es escaneado, leer las páginas como imagen). **No copiar tablas de datos** ni instrucciones administrativas: no hace falta para Google.

## Curso o universidad nuevos

En `sitio.json`: universidad nueva → `universidades` (`"SIGLA": "Nombre completo"`);
curso nuevo → `cursos_en` (traducción) y `orden_cursos`.

## Comprobar y publicar

```bash
pip install -r requirements.txt   # Pillow, pypdf, cryptography (+ poppler-utils para páginas de PDF)
python build.py                   # debe terminar en "Listo: ..." sin errores
git add -A && git commit -m "..." && git push origin HEAD:main
```

`_site/` no se sube (está en `.gitignore`). Tras el push, esperar al workflow y revisar la página nueva en
https://solucionariouni.com (los ejercicios en `/<curso>/<archivo>/`, los PDF en `/pdfs/<archivo>/`).
