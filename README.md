# Biblioteca Lindey

Biblioteca abierta de ejercicios universitarios de ingeniería (Estática, Dinámica, Resistencia de Materiales, Mecánica de Materiales, Mecánica de Fluidos…) publicada por **Lindey Asesoramiento Universitario** · WhatsApp +51 970 302 148.

Sitio: https://dayanaalisson027.github.io/biblioteca-lindey/

## Cómo agregar un ejercicio nuevo (desde la web de GitHub)

1. Entra a la carpeta `imagenes/` → **Add file → Upload files** → sube la imagen modo Lindey (por ejemplo `Lindey_Estatica_UCSUR_Pregunta4.jpg`) → **Commit changes**.
2. Entra a la carpeta `ejercicios/` → abre `_PLANTILLA.md` → copia su contenido.
3. En `ejercicios/` → **Add file → Create new file**. Ponle de nombre el tema + universidad + número, en minúsculas y con guiones, terminado en `.md`
   (ejemplo: `momento-de-una-fuerza-ucsur-pregunta-4.md`). Ese nombre será la dirección de la página.
4. Pega la plantilla, completa los datos y el enunciado, y pulsa **Commit changes**.
5. En 1 o 2 minutos la página aparece publicada. Puedes ver el avance en la pestaña **Actions** (círculo verde = publicado; cruz roja = abre el detalle y lee el mensaje, casi siempre es una imagen con otro nombre o un campo vacío).

Campos de cada ejercicio:

| Campo | ¿Obligatorio? | Ejemplo |
|---|---|---|
| `curso` | sí | Estática |
| `tema` | sí | Zapata combinada |
| `imagen` | sí | Lindey_Estatica_UCSUR_Pregunta1.jpg |
| `universidad` | no | UCSUR |
| `etiqueta` | no | Pregunta 1 |
| `evaluacion` | no | Práctica calificada 2 |
| `fecha` | no | 2026-11-06 |
| `palabras` | no | equilibrio, carga distribuida |
| `solucion_imagen` | no | imagen de solución paso a paso |

Para que una universidad muestre su nombre completo, agrégala en `sitio.json` dentro de `"universidades"`.

Cada ejercicio genera solo su PDF (enunciado + figura + enlace a WhatsApp), aparece en el carrusel de su curso en la portada y entra en el **Banco de ejercicios** en PDF de su curso.

### Versión en inglés

Cada ejercicio puede tener su página en inglés (`/en/...`): agrega `tema_en:` y `palabras_en:` en el encabezado y escribe el enunciado en inglés debajo de una línea que diga solo `[en]`. Los nombres de los cursos en inglés están en `sitio.json` → `"cursos_en"`.

## Cómo agregar un documento (PDF o Word) al repositorio

1. Entra a la carpeta `pdfs/` → **Add file → Upload files** → sube el PDF o Word → **Commit changes**.
2. Copia `pdfs/_PLANTILLA.md` en un archivo nuevo de `pdfs/` (ejemplo: `examen-parcial-estatica-ucsur-2026-1.md`), escribe el nombre del archivo en `archivo:`, completa título y curso, y debajo pega la transcripción de los ejercicios → **Commit changes**.
3. El documento aparece en el **Repositorio de PDFs** con portada, visor tipo revista (pasa hojas, miniaturas y pantalla completa), su transcripción y botones para compartir.

## Cómo funciona

- `ejercicios/*.md` — un archivo por ejercicio.
- `imagenes/` — imágenes modo Lindey.
- `pdfs/` — PDFs propios, cada uno con su `.md`.
- `estaticos/` — estilos, buscador, logo.
- `sitio.json` — nombre, URL pública, WhatsApp, universidades y orden de cursos.
- `build.py` — genera el sitio en `_site/` (Python; usa Pillow para miniaturas, Poppler para las páginas de los PDF y LibreOffice si hay archivos Word).
- `.github/workflows/publicar.yml` — cada cambio en `main` vuelve a generar y publicar el sitio en GitHub Pages.

Para generarlo en tu PC: `python build.py` y abre `_site/index.html`.

## Mudarlo a Cloudflare Pages

En Cloudflare Pages → *Create a project* → conecta este repositorio y usa:

- **Build command:** `pip install -r requirements.txt pymupdf && python build.py`
  (en Cloudflare los documentos Word deben subirse ya convertidos a PDF)
- **Build output directory:** `_site`
- **Variable de entorno:** `SITE_URL` = la dirección nueva (por ejemplo `https://biblioteca-lindey.pages.dev` o tu dominio `.com`)

## Dominio propio (.com)

Cambia `"url"` en `sitio.json` por tu dominio (por ejemplo `https://www.lindey.com`) y configúralo en *Settings → Pages → Custom domain* (GitHub) o en *Custom domains* (Cloudflare).
