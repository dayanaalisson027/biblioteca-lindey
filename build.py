#!/usr/bin/env python3
"""Genera la Biblioteca Lindey como sitio estático en la carpeta _site/.

Uso:
    python build.py

Lee:
    sitio.json          configuración general (nombre, URL, WhatsApp, universidades)
    ejercicios/*.md     un archivo por ejercicio (los que empiezan con "_" se ignoran)
    imagenes/           imágenes modo Lindey referenciadas por cada ejercicio
    estaticos/          estilos, buscador, logo e imagen para redes

Variable opcional:
    SITE_URL=https://www.midominio.com python build.py
    (cambia la URL pública usada en canonical, sitemap y redes; útil en Cloudflare Pages)

Solo usa la biblioteca estándar de Python 3.8+, así que funciona igual en
GitHub Actions, Cloudflare Pages o en tu PC.
"""

import html
import json
import os
import re
import shutil
import struct
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"
CARPETA_EJERCICIOS = RAIZ / "ejercicios"
CARPETA_IMAGENES = RAIZ / "imagenes"
CARPETA_ESTATICOS = RAIZ / "estaticos"

CAMPOS_OBLIGATORIOS = ("curso", "tema", "imagen")


# ----------------------------------------------------------------- utilidades

def esc(texto):
    return html.escape(str(texto or ""), quote=True)


def slugify(texto):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()


def recortar(texto, limite=158):
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) <= limite:
        return texto
    corte = texto[: limite - 1].rsplit(" ", 1)[0].rstrip(",;:.")
    return corte + "…"


def numero_natural(texto):
    m = re.search(r"\d+", texto or "")
    return int(m.group()) if m else 0


def medidas_imagen(ruta):
    """Devuelve (ancho, alto) de un JPG o PNG sin librerías externas, o (None, None)."""
    try:
        with open(ruta, "rb") as f:
            cabecera = f.read(26)
            if cabecera[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", cabecera[16:24])
            if cabecera[:2] != b"\xff\xd8":
                return None, None
            f.seek(2)
            while True:
                marca = f.read(2)
                if len(marca) < 2 or marca[0] != 0xFF:
                    return None, None
                tipo = marca[1]
                largo = struct.unpack(">H", f.read(2))[0]
                if tipo in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(1)
                    alto, ancho = struct.unpack(">HH", f.read(4))
                    return ancho, alto
                f.seek(largo - 2, 1)
    except (OSError, struct.error):
        return None, None


def escribir(ruta_relativa, contenido):
    destino = SALIDA / ruta_relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(contenido, encoding="utf-8")


# --------------------------------------------------------------- configuración

def cargar_sitio():
    sitio = json.loads((RAIZ / "sitio.json").read_text(encoding="utf-8-sig"))
    sitio["url"] = os.environ.get("SITE_URL", sitio["url"]).rstrip("/")
    sitio["ruta_base"] = (urlparse(sitio["url"]).path.rstrip("/") + "/") or "/"
    sitio.setdefault("universidades", {})
    sitio.setdefault("orden_cursos", [])
    return sitio


# ------------------------------------------------------------------ ejercicios

def leer_ejercicio(ruta, sitio):
    texto = ruta.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", texto, re.S)
    if not m:
        raise ValueError("falta el encabezado entre las dos líneas ---")
    datos = {}
    for n, linea in enumerate(m.group(1).split("\n"), start=2):
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if ":" not in linea:
            raise ValueError(f"línea {n} sin «clave: valor»: {linea!r}")
        clave, valor = linea.split(":", 1)
        datos[clave.strip().lower()] = valor.strip()
    faltan = [c for c in CAMPOS_OBLIGATORIOS if not datos.get(c)]
    if faltan:
        raise ValueError("faltan campos: " + ", ".join(faltan))

    enunciado = re.sub(r"<!--.*?-->", "", m.group(2), flags=re.S).strip()
    if not enunciado:
        raise ValueError("falta el enunciado (texto debajo del segundo ---)")

    slug = slugify(ruta.stem)
    curso = datos["curso"]
    sigla = datos.get("universidad", "")
    ej = {
        "archivo": ruta.name,
        "slug": slug,
        "curso": curso,
        "curso_slug": slugify(curso),
        "tema": datos.get("titulo") or datos["tema"],
        "universidad": sigla,
        "universidad_nombre": sitio["universidades"].get(sigla, ""),
        "universidad_slug": slugify(sigla) if sigla else "",
        "etiqueta": datos.get("etiqueta", ""),
        "evaluacion": datos.get("evaluacion", ""),
        "imagen": datos["imagen"],
        "solucion_imagen": datos.get("solucion_imagen", ""),
        "fecha": datos.get("fecha") or date.today().isoformat(),
        "palabras": [p.strip() for p in datos.get("palabras", "").split(",") if p.strip()],
        "descripcion": datos.get("descripcion", ""),
        "enunciado": enunciado,
    }
    ej["url"] = f"{ej['curso_slug']}/{slug}/"
    for campo, sufijo in (("imagen", ""), ("solucion_imagen", "-solucion")):
        nombre = ej[campo]
        if not nombre:
            continue
        origen = CARPETA_IMAGENES / nombre
        if not origen.exists():
            raise ValueError(f"no encuentro la imagen imagenes/{nombre}")
        ej[campo + "_origen"] = origen
        ej[campo + "_url"] = f"img/{slug}{sufijo}{origen.suffix.lower()}"
        ej[campo + "_medidas"] = medidas_imagen(origen)
    return ej


def cargar_ejercicios(sitio):
    ejercicios, errores = [], []
    for ruta in sorted(CARPETA_EJERCICIOS.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        try:
            ejercicios.append(leer_ejercicio(ruta, sitio))
        except ValueError as e:
            errores.append(f"  - ejercicios/{ruta.name}: {e}")
    vistos = {}
    for ej in ejercicios:
        if ej["url"] in vistos:
            errores.append(f"  - ejercicios/{ej['archivo']}: misma URL que {vistos[ej['url']]}")
        vistos[ej["url"]] = ej["archivo"]
    if errores:
        print("No se pudo generar el sitio. Revisa estos archivos:\n" + "\n".join(errores))
        sys.exit(1)
    return ejercicios


def orden_curso(sitio, curso):
    orden = sitio["orden_cursos"]
    return (orden.index(curso) if curso in orden else len(orden), curso)


def orden_ejercicio(sitio):
    return lambda e: (orden_curso(sitio, e["curso"]), e["evaluacion"], numero_natural(e["etiqueta"]), e["tema"])


# --------------------------------------------------------------- piezas HTML

ICONO_CHAT = (
    '<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18">'
    '<path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.4.1-.2 0-.3 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.3c0-.1-.2-.2-.5-.3z"/>'
    "</svg>"
)


def enlace_whatsapp(sitio, mensaje):
    return f"https://wa.me/{sitio['whatsapp']}?text={quote(mensaje)}"


def pagina(sitio, *, raiz, ruta, titulo, descripcion, contenido, imagen_social=None,
           tipo_og="website", jsonld=None, mensaje_wa=None, indexar=True, cuerpo_clase=""):
    canonical = f"{sitio['url']}/{ruta}"
    imagen_social = imagen_social or f"{sitio['url']}/og-biblioteca-lindey.jpg"
    mensaje_wa = mensaje_wa or "Hola Lindey, vi la Biblioteca Lindey y necesito asesoría."
    bloques_ld = "".join(
        f'\n<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>'
        for b in (jsonld or [])
    )
    verificacion = (
        f'\n<meta name="google-site-verification" content="{esc(sitio["google_verificacion"])}">'
        if sitio.get("google_verificacion") else ""
    )
    robots = "index, follow, max-image-preview:large" if indexar else "noindex"
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descripcion)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:site_name" content="{esc(sitio['nombre'])}">
<meta property="og:locale" content="es_PE">
<meta property="og:type" content="{tipo_og}">
<meta property="og:title" content="{esc(titulo)}">
<meta property="og:description" content="{esc(descripcion)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(imagen_social)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#060f27">{verificacion}
<link rel="icon" href="{raiz}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{raiz}estilos.css">{bloques_ld}
</head>
<body class="{cuerpo_clase}" data-raiz="{raiz}">
<a class="saltar" href="#contenido">Saltar al contenido</a>
<header class="cabecera">
  <div class="envoltura cabecera__in">
    <a class="marca" href="{raiz}" aria-label="Biblioteca Lindey, inicio">
      <img src="{raiz}logo-lindey.png" alt="Lindey Asesoramiento Universitario" width="184" height="56">
      <span class="marca__bib">Biblioteca</span>
    </a>
    <nav class="cabecera__nav" aria-label="Principal">
      <a href="{raiz}#cursos">Cursos</a>
      <a href="{raiz}#universidades">Universidades</a>
      <a href="{raiz}ejercicios/">Todos</a>
    </nav>
  </div>
</header>
<main id="contenido">
{contenido}
</main>
<footer class="pie">
  <div class="envoltura pie__in">
    <p><strong>{esc(sitio['nombre'])}</strong> · Ejercicios universitarios de libre consulta, publicados por Lindey Asesoramiento Universitario.</p>
    <p class="pie__enlaces">
      <a href="{esc(enlace_whatsapp(sitio, mensaje_wa))}" rel="noopener">WhatsApp {esc(sitio['whatsapp_visible'])}</a>
      <a href="{esc(sitio['facebook'])}" rel="noopener">Facebook</a>
      <a href="{raiz}ejercicios/">Índice de ejercicios</a>
    </p>
  </div>
</footer>
<a class="flotante" href="{esc(enlace_whatsapp(sitio, mensaje_wa))}" rel="noopener" aria-label="Escribir a Lindey por WhatsApp">{ICONO_CHAT}<span>Asesoría</span></a>
<script src="{raiz}buscador.js" defer></script>
</body>
</html>
"""


def migas(raiz, pasos):
    partes = [f'<a href="{raiz}">Biblioteca</a>']
    for texto, enlace in pasos:
        partes.append(f'<a href="{enlace}">{esc(texto)}</a>' if enlace else f'<span aria-current="page">{esc(texto)}</span>')
    return '<nav class="migas" aria-label="Ruta">' + '<span class="migas__sep">›</span>'.join(partes) + "</nav>"


def migas_jsonld(sitio, pasos):
    elementos = [{"@type": "ListItem", "position": 1, "name": "Biblioteca", "item": sitio["url"] + "/"}]
    for i, (nombre, ruta) in enumerate(pasos, start=2):
        elementos.append({"@type": "ListItem", "position": i, "name": nombre, "item": f"{sitio['url']}/{ruta}"})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": elementos}


def meta_ejercicio(ej):
    partes = [ej["curso"]]
    if ej["universidad"]:
        partes.append(ej["universidad"])
    if ej["evaluacion"]:
        partes.append(ej["evaluacion"])
    if ej["etiqueta"]:
        partes.append(ej["etiqueta"])
    return " · ".join(partes)


def resumen_enunciado(ej, limite=170):
    primer_parrafo = ej["enunciado"].split("\n\n")[0]
    return recortar(primer_parrafo, limite)


def tarjeta(ej, raiz, mostrar_curso=True):
    meta = meta_ejercicio(ej) if mostrar_curso else " · ".join(
        p for p in (ej["universidad"], ej["evaluacion"], ej["etiqueta"]) if p)
    return f"""<li class="tarjeta">
  <a href="{raiz}{ej['url']}">
    <span class="tarjeta__meta">{esc(meta)}</span>
    <span class="tarjeta__titulo">{esc(ej['tema'])}</span>
    <span class="tarjeta__texto">{esc(resumen_enunciado(ej, 150))}</span>
  </a>
</li>"""


def lista_tarjetas(ejercicios, raiz, mostrar_curso=True):
    return '<ul class="tarjetas">' + "\n".join(tarjeta(e, raiz, mostrar_curso) for e in ejercicios) + "</ul>"


def parrafos(texto):
    salida = []
    for bloque in re.split(r"\n\s*\n", texto.strip()):
        linea = esc(" ".join(l.strip() for l in bloque.splitlines()))
        if linea.startswith("* "):
            salida.append(f'<p class="nota">{linea}</p>')
        elif linea.startswith("Datos de la figura:"):
            salida.append('<p class="datos"><strong>Datos de la figura:</strong>' + linea[len("Datos de la figura:"):] + "</p>")
        else:
            salida.append(f"<p>{linea}</p>")
    return "\n".join(salida)


def figura(ej, campo, raiz, alt, carga="eager"):
    ancho, alto = ej[campo + "_medidas"]
    dims = f' width="{ancho}" height="{alto}"' if ancho else ""
    return (f'<img src="{raiz}{ej[campo + "_url"]}" alt="{esc(alt)}"{dims} '
            f'loading="{carga}" decoding="async">')


# ------------------------------------------------------------------- páginas

def pagina_ejercicio(sitio, ej, relacionados):
    raiz = "../../"
    uni_txt = f" ({ej['universidad']})" if ej["universidad"] else ""
    titulo = f"{ej['tema']} – {ej['curso']}{uni_txt} | {sitio['nombre']}"
    contexto = " de ".join(p for p in (ej["etiqueta"], ej["curso"]) if p)
    if ej["universidad"]:
        contexto += f", {ej['universidad']}"
    descripcion = ej["descripcion"] or recortar(f"{contexto}: {ej['enunciado'].split(chr(10)*2)[0]}")
    alt = f"Enunciado y figura: {ej['tema']} – {meta_ejercicio(ej)}"
    mensaje = f"Hola Lindey, vi el ejercicio «{ej['tema']}» ({ej['curso']}) en la Biblioteca Lindey y necesito asesoría."
    wa = enlace_whatsapp(sitio, mensaje)

    chips = [f'<a class="chip chip--curso" href="{raiz}{ej["curso_slug"]}/">{esc(ej["curso"])}</a>']
    if ej["universidad"]:
        nombre = ej["universidad_nombre"]
        etiqueta_uni = f"{ej['universidad']} · {nombre}" if nombre else ej["universidad"]
        chips.append(f'<a class="chip" href="{raiz}universidad/{ej["universidad_slug"]}/">{esc(etiqueta_uni)}</a>')
    if ej["evaluacion"]:
        chips.append(f'<span class="chip chip--suave">{esc(ej["evaluacion"])}</span>')
    if ej["etiqueta"]:
        chips.append(f'<span class="chip chip--suave">{esc(ej["etiqueta"])}</span>')

    palabras = ""
    if ej["palabras"]:
        palabras = ('<p class="palabras"><span>Conceptos:</span> '
                    + ", ".join(esc(p) for p in ej["palabras"]) + "</p>")

    solucion = ""
    if ej.get("solucion_imagen"):
        solucion = f"""<section class="bloque solucion" aria-labelledby="t-solucion">
  <h2 id="t-solucion">Solución paso a paso</h2>
  <figure class="figura">{figura(ej, "solucion_imagen", raiz, "Solución paso a paso: " + ej["tema"], "lazy")}</figure>
</section>"""

    mas = ""
    if relacionados:
        mas = f"""<section class="bloque" aria-labelledby="t-mas">
  <h2 id="t-mas">Más ejercicios de {esc(ej['curso'])}</h2>
  {lista_tarjetas(relacionados, raiz, mostrar_curso=False)}
  <p><a class="enlace-flecha" href="{raiz}{ej['curso_slug']}/">Ver todos los ejercicios de {esc(ej['curso'])}</a></p>
</section>"""

    contenido = f"""<div class="envoltura">
{migas(raiz, [(ej['curso'], f"{raiz}{ej['curso_slug']}/"), (ej['tema'], None)])}
<article class="ejercicio">
  <header class="ejercicio__cabecera">
    <p class="antetitulo">{esc(meta_ejercicio(ej))}</p>
    <h1>{esc(ej['tema'])}</h1>
    <div class="chips">{"".join(chips)}</div>
  </header>
  <div class="ejercicio__cuerpo">
    <section class="enunciado" aria-labelledby="t-enunciado">
      <h2 id="t-enunciado">Enunciado</h2>
      {parrafos(ej['enunciado'])}
      {palabras}
    </section>
    <figure class="figura figura--principal">
      {figura(ej, "imagen", raiz, alt)}
      <figcaption>Figura del ejercicio · {esc(meta_ejercicio(ej))}</figcaption>
    </figure>
  </div>
  {solucion}
  <aside class="asesoria" aria-label="Asesoría">
    <p>¿Necesitas asesoría? <a href="{esc(wa)}" rel="noopener">WhatsApp {esc(sitio['whatsapp_visible'])}</a></p>
  </aside>
</article>
{mas}
</div>"""

    imagen_abs = f"{sitio['url']}/{ej['imagen_url']}"
    recurso = {
        "@context": "https://schema.org",
        "@type": "LearningResource",
        "name": ej["tema"],
        "headline": f"{ej['tema']} – {ej['curso']}",
        "description": descripcion,
        "text": ej["enunciado"],
        "inLanguage": "es",
        "learningResourceType": "Ejercicio",
        "educationalLevel": "Universitario",
        "teaches": ej["tema"],
        "about": [ej["curso"], ej["tema"]] + ej["palabras"],
        "keywords": ", ".join([ej["curso"], ej["tema"]] + ej["palabras"]),
        "image": imagen_abs,
        "url": f"{sitio['url']}/{ej['url']}",
        "datePublished": ej["fecha"],
        "isAccessibleForFree": True,
        "isPartOf": {"@type": "Course", "name": ej["curso"], "url": f"{sitio['url']}/{ej['curso_slug']}/",
                     "provider": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario"}},
        "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario",
                      "sameAs": [sitio["facebook"]]},
    }
    if ej["universidad_nombre"] or ej["universidad"]:
        recurso["audience"] = {"@type": "EducationalAudience", "educationalRole": "student",
                               "audienceType": ej["universidad_nombre"] or ej["universidad"]}
    ld = [recurso, migas_jsonld(sitio, [(ej["curso"], f"{ej['curso_slug']}/"), (ej["tema"], ej["url"])])]
    return pagina(sitio, raiz=raiz, ruta=ej["url"], titulo=titulo, descripcion=descripcion,
                  contenido=contenido, imagen_social=imagen_abs, tipo_og="article", jsonld=ld,
                  mensaje_wa=mensaje, cuerpo_clase="pag-ejercicio")


def pagina_curso(sitio, curso, ejercicios):
    raiz = "../"
    slug = slugify(curso)
    unis = sorted({e["universidad"] for e in ejercicios if e["universidad"]})
    uni_txt = f" de {', '.join(unis)}" if unis else ""
    titulo = f"Ejercicios de {curso} con enunciado y figura | {sitio['nombre']}"
    descripcion = recortar(
        f"{len(ejercicios)} ejercicios universitarios de {curso}{uni_txt} con enunciado completo en texto y figura: "
        + ", ".join(e["tema"].lower() for e in ejercicios[:6]) + ".")
    contenido = f"""<div class="envoltura">
{migas(raiz, [(curso, None)])}
<header class="encabezado">
  <p class="antetitulo">Curso</p>
  <h1>Ejercicios de {esc(curso)}</h1>
  <p class="bajada">{len(ejercicios)} {"ejercicio" if len(ejercicios) == 1 else "ejercicios"} con enunciado completo y figura.</p>
</header>
{lista_tarjetas(ejercicios, raiz, mostrar_curso=False)}
</div>"""
    ld = [migas_jsonld(sitio, [(curso, f"{slug}/")]),
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"Ejercicios de {curso}",
           "url": f"{sitio['url']}/{slug}/", "inLanguage": "es", "description": descripcion}]
    return pagina(sitio, raiz=raiz, ruta=f"{slug}/", titulo=titulo, descripcion=descripcion,
                  contenido=contenido, jsonld=ld)


def pagina_universidad(sitio, sigla, ejercicios):
    raiz = "../../"
    slug = slugify(sigla)
    nombre = sitio["universidades"].get(sigla, "")
    nombre_largo = f"{sigla} ({nombre})" if nombre else sigla
    titulo = f"Ejercicios de la {sigla}{' – ' + nombre if nombre else ''} | {sitio['nombre']}"
    cursos = sorted({e["curso"] for e in ejercicios}, key=lambda c: orden_curso(sitio, c))
    descripcion = recortar(
        f"Ejercicios universitarios de la {nombre_largo}: {', '.join(cursos)}. Enunciado completo y figura.")
    grupos = []
    for curso in cursos:
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        grupos.append(f'<section class="bloque"><h2>{esc(curso)}</h2>{lista_tarjetas(del_curso, raiz, mostrar_curso=False)}</section>')
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Universidades", f"{raiz}#universidades"), (sigla, None)])}
<header class="encabezado">
  <p class="antetitulo">Universidad</p>
  <h1>Ejercicios de la {esc(sigla)}</h1>
  {f'<p class="bajada">{esc(nombre)}</p>' if nombre else ''}
</header>
{"".join(grupos)}
</div>"""
    ld = [migas_jsonld(sitio, [(sigla, f"universidad/{slug}/")])]
    return pagina(sitio, raiz=raiz, ruta=f"universidad/{slug}/", titulo=titulo, descripcion=descripcion,
                  contenido=contenido, jsonld=ld)


def pagina_indice(sitio, ejercicios, cursos):
    raiz = "../"
    bloques = []
    for curso in cursos:
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        items = "".join(
            f'<li><a href="{raiz}{e["url"]}">{esc(e["tema"])}</a> <span>{esc(" · ".join(p for p in (e["universidad"], e["evaluacion"], e["etiqueta"]) if p))}</span></li>'
            for e in del_curso)
        bloques.append(f'<section class="bloque"><h2><a href="{raiz}{slugify(curso)}/">{esc(curso)}</a></h2><ul class="indice">{items}</ul></section>')
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Todos los ejercicios", None)])}
<header class="encabezado">
  <h1>Todos los ejercicios</h1>
  <p class="bajada">{len(ejercicios)} ejercicios ordenados por curso.</p>
</header>
{"".join(bloques)}
</div>"""
    return pagina(sitio, raiz=raiz, ruta="ejercicios/", titulo=f"Índice de ejercicios | {sitio['nombre']}",
                  descripcion=recortar(f"Índice completo de los {len(ejercicios)} ejercicios de la {sitio['nombre']}: {', '.join(cursos)}."),
                  contenido=contenido, jsonld=[migas_jsonld(sitio, [("Todos los ejercicios", "ejercicios/")])])


def pagina_portada(sitio, ejercicios, cursos, universidades):
    raiz = ""
    tarjetas_curso = []
    for curso in cursos:
        n = sum(1 for e in ejercicios if e["curso"] == curso)
        temas = [e["tema"] for e in ejercicios if e["curso"] == curso][:3]
        tarjetas_curso.append(f"""<li class="curso">
  <a href="{slugify(curso)}/">
    <span class="curso__nombre">{esc(curso)}</span>
    <span class="curso__n">{n} {"ejercicio" if n == 1 else "ejercicios"}</span>
    <span class="curso__temas">{esc(" · ".join(temas))}</span>
  </a>
</li>""")
    chips_uni = []
    for sigla in universidades:
        n = sum(1 for e in ejercicios if e["universidad"] == sigla)
        nombre = sitio["universidades"].get(sigla, "")
        chips_uni.append(
            f'<li><a class="uni" href="universidad/{slugify(sigla)}/"><strong>{esc(sigla)}</strong>'
            f'{f"<span>{esc(nombre)}</span>" if nombre else ""}<em>{n}</em></a></li>')
    recientes = sorted(ejercicios, key=lambda e: e["fecha"], reverse=True)[:9]

    contenido = f"""<section class="portada">
  <div class="envoltura">
    <h1>Biblioteca Lindey</h1>
    <p class="portada__bajada">Ejercicios universitarios de ingeniería con su enunciado completo y figura, de libre consulta. Busca por tema, curso, universidad o pega parte del enunciado.</p>
    <form class="buscador" id="buscar" role="search" action="./" method="get">
      <label class="oculto" for="q">Buscar ejercicio</label>
      <input id="q" name="q" type="search" autocomplete="off" placeholder="Ej.: zapata combinada, pandeo, viga conjugada…">
      <button type="submit">Buscar</button>
    </form>
    <p class="portada__cifras">{len(ejercicios)} ejercicios · {len(cursos)} cursos · {len(universidades)} universidades</p>
  </div>
</section>
<div class="envoltura">
  <section class="resultados" id="resultados" aria-live="polite" hidden></section>
  <section class="bloque" id="cursos" aria-labelledby="t-cursos">
    <h2 id="t-cursos">Cursos</h2>
    <ul class="cursos">{"".join(tarjetas_curso)}</ul>
  </section>
  <section class="bloque" id="universidades" aria-labelledby="t-unis">
    <h2 id="t-unis">Universidades</h2>
    <ul class="unis">{"".join(chips_uni)}</ul>
  </section>
  <section class="bloque" aria-labelledby="t-recientes">
    <h2 id="t-recientes">Ejercicios recientes</h2>
    {lista_tarjetas(recientes, raiz)}
    <p><a class="enlace-flecha" href="ejercicios/">Ver los {len(ejercicios)} ejercicios</a></p>
  </section>
</div>"""
    ld = [{
        "@context": "https://schema.org", "@type": "WebSite", "name": sitio["nombre"], "url": sitio["url"] + "/",
        "inLanguage": "es", "description": sitio["descripcion"],
        "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario",
                      "sameAs": [sitio["facebook"]], "logo": f"{sitio['url']}/logo-lindey.png"},
    }]
    return pagina(sitio, raiz=raiz, ruta="", titulo=f"{sitio['nombre']} – Ejercicios universitarios de ingeniería",
                  descripcion=sitio["descripcion"], contenido=contenido, jsonld=ld, cuerpo_clase="pag-portada")


def pagina_404(sitio):
    base = sitio["ruta_base"]
    contenido = f"""<div class="envoltura">
<header class="encabezado">
  <h1>No encontramos esa página</h1>
  <p class="bajada">Puede que el ejercicio haya cambiado de dirección. Búscalo desde la <a href="{base}">portada de la Biblioteca</a> o revisa el <a href="{base}ejercicios/">índice de ejercicios</a>.</p>
</header>
</div>"""
    return pagina(sitio, raiz=base, ruta="404.html", titulo=f"Página no encontrada | {sitio['nombre']}",
                  descripcion="Página no encontrada.", contenido=contenido, indexar=False)


# ------------------------------------------------------------ archivos extra

def indice_busqueda(ejercicios):
    return json.dumps([{
        "t": e["tema"], "c": e["curso"], "u": e["universidad"], "un": e["universidad_nombre"],
        "v": e["evaluacion"], "e": e["etiqueta"], "k": ", ".join(e["palabras"]),
        "d": e["enunciado"], "r": resumen_enunciado(e, 150), "url": e["url"],
    } for e in ejercicios], ensure_ascii=False, separators=(",", ":"))


def sitemap(sitio, ejercicios, cursos, universidades):
    hoy = max((e["fecha"] for e in ejercicios), default=date.today().isoformat())
    filas = [(f"{sitio['url']}/", hoy, None), (f"{sitio['url']}/ejercicios/", hoy, None)]
    for curso in cursos:
        fecha = max(e["fecha"] for e in ejercicios if e["curso"] == curso)
        filas.append((f"{sitio['url']}/{slugify(curso)}/", fecha, None))
    for sigla in universidades:
        fecha = max(e["fecha"] for e in ejercicios if e["universidad"] == sigla)
        filas.append((f"{sitio['url']}/universidad/{slugify(sigla)}/", fecha, None))
    for e in ejercicios:
        imagenes = [f"{sitio['url']}/{e['imagen_url']}"]
        if e.get("solucion_imagen_url"):
            imagenes.append(f"{sitio['url']}/{e['solucion_imagen_url']}")
        filas.append((f"{sitio['url']}/{e['url']}", e["fecha"], imagenes))
    partes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for loc, fecha, imagenes in filas:
        imgs = "".join(f"<image:image><image:loc>{esc(i)}</image:loc></image:image>" for i in imagenes or [])
        partes.append(f"<url><loc>{esc(loc)}</loc><lastmod>{fecha}</lastmod>{imgs}</url>")
    partes.append("</urlset>\n")
    return "\n".join(partes)


# ------------------------------------------------------------------- principal

def main():
    sitio = cargar_sitio()
    ejercicios = sorted(cargar_ejercicios(sitio), key=orden_ejercicio(sitio))
    cursos = sorted({e["curso"] for e in ejercicios}, key=lambda c: orden_curso(sitio, c))
    universidades = sorted({e["universidad"] for e in ejercicios if e["universidad"]})

    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    SALIDA.mkdir()
    for archivo in CARPETA_ESTATICOS.iterdir():
        if archivo.is_file():
            shutil.copy2(archivo, SALIDA / archivo.name)
    (SALIDA / "img").mkdir()
    for e in ejercicios:
        for campo in ("imagen", "solucion_imagen"):
            if e.get(campo + "_origen"):
                shutil.copy2(e[campo + "_origen"], SALIDA / e[campo + "_url"])

    for e in ejercicios:
        relacionados = [o for o in ejercicios if o["curso"] == e["curso"] and o is not e][:6]
        escribir(f"{e['url']}index.html", pagina_ejercicio(sitio, e, relacionados))
    for curso in cursos:
        escribir(f"{slugify(curso)}/index.html", pagina_curso(sitio, curso, [e for e in ejercicios if e["curso"] == curso]))
    for sigla in universidades:
        escribir(f"universidad/{slugify(sigla)}/index.html",
                 pagina_universidad(sitio, sigla, [e for e in ejercicios if e["universidad"] == sigla]))
    escribir("ejercicios/index.html", pagina_indice(sitio, ejercicios, cursos))
    escribir("index.html", pagina_portada(sitio, ejercicios, cursos, universidades))
    escribir("404.html", pagina_404(sitio))
    escribir("buscar.json", indice_busqueda(ejercicios))
    escribir("sitemap.xml", sitemap(sitio, ejercicios, cursos, universidades))
    escribir("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {sitio['url']}/sitemap.xml\n")
    escribir(".nojekyll", "")

    print(f"Listo: {len(ejercicios)} ejercicios, {len(cursos)} cursos, {len(universidades)} universidades → _site/")
    print(f"URL pública: {sitio['url']}/")


if __name__ == "__main__":
    main()
