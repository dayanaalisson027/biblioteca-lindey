#!/usr/bin/env python3
"""Genera la Biblioteca Lindey como sitio estático en la carpeta _site/.

Uso:
    python build.py

Lee:
    sitio.json          configuración general (nombre, URL, WhatsApp, universidades)
    ejercicios/*.md     un archivo por ejercicio (los que empiezan con "_" se ignoran)
    imagenes/           imágenes modo Lindey referenciadas por cada ejercicio
    pdfs/*.md + PDF     documentos propios (un .md por PDF o Word, con su transcripción)
    estaticos/          estilos, scripts, logo e imagen para redes

Genera además:
    (los ejercicios se publican como imagen + texto; solo los PDF que subes a pdfs/ son PDF)
    - las páginas de cada PDF como imágenes para el visor tipo revista
    - la marca de agua Lindey en cada documento propio (PDF descargable y páginas del visor)

Variable opcional:
    SITE_URL=https://www.midominio.com python build.py
(En GitHub Actions la dirección se deduce sola del nombre de la cuenta y del repositorio.)

Funciona con Python 3.8+. Opcionales: Pillow (miniaturas de los carruseles), pypdf (marca de agua),
Poppler (pdftoppm/pdftotext) o PyMuPDF (páginas de los PDFs) y LibreOffice (Word → PDF).
"""

import html
import io
import json
import math
import os
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata
import zlib
from datetime import date
from pathlib import Path
from urllib.parse import quote, urlparse

try:
    from PIL import Image
except ImportError:  # el sitio se genera igual, sin miniaturas
    Image = None

RAIZ = Path(__file__).resolve().parent
SALIDA = RAIZ / "_site"
CARPETA_EJERCICIOS = RAIZ / "ejercicios"
CARPETA_IMAGENES = RAIZ / "imagenes"
CARPETA_PDFS = RAIZ / "pdfs"
CARPETA_ESTATICOS = RAIZ / "estaticos"

CAMPOS_EJERCICIO = ("curso", "tema", "imagen")
CAMPOS_DOCUMENTO = ("titulo", "curso", "archivo")
EXTENSIONES_WORD = (".docx", ".doc", ".odt", ".rtf")

# Traducción automática de etiquetas cortas para la versión en inglés
ETIQUETAS_EN = [("Pregunta", "Question"), ("Problema", "Problem"), ("Ejercicio", "Exercise")]
EVALUACIONES_EN = [("Práctica calificada", "Graded practice"), ("Trabajo grupal", "Group assignment"),
                   ("Examen práctico", "Practical exam"), ("Examen parcial", "Midterm exam"),
                   ("Examen final", "Final exam"), ("Práctica", "Practice"), ("Tarea", "Homework"),
                   ("Laboratorio", "Lab")]

TEXTOS = {
    "es": {
        "lang": "es", "locale": "es_PE", "biblioteca": "Biblioteca", "cursos": "Cursos",
        "universidades": "Universidades", "otro_idioma": "English", "otro_lang": "en",
        "pie": "Ejercicios universitarios de libre consulta, publicados por Lindey Asesoramiento Universitario.",
        "asesoria": "PIDE TU SOLUCIONARIO", "aria_asesoria": "Pide tu solucionario por WhatsApp", "necesitas": "PIDE TU SOLUCIONARIO",
        "compartir": "Compártelo con tus amigos", "copiar": "Copiar enlace", "mas_opciones": "Más opciones",
        "saltar": "Saltar al contenido", "inicio": "Biblioteca Lindey, inicio", "ruta": "Ruta",
        "contacto": "Contacto", "derechos": "Todos los derechos reservados.",
        "anterior": "Anterior", "siguiente": "Siguiente", "principal": "Principal",
    },
    "en": {
        "lang": "en", "locale": "en_US", "biblioteca": "Library", "cursos": "Courses",
        "universidades": "Universities", "otro_idioma": "Español", "otro_lang": "es",
        "pie": "Free university engineering exercises, published by Lindey Asesoramiento Universitario (Peru).",
        "asesoria": "GET YOUR SOLUTION", "aria_asesoria": "Get your solution on WhatsApp", "necesitas": "GET YOUR SOLUTION",
        "compartir": "Share it with your friends", "copiar": "Copy link", "mas_opciones": "More options",
        "saltar": "Skip to content", "inicio": "Lindey Library, home", "ruta": "Breadcrumb",
        "contacto": "Contact", "derechos": "All rights reserved.",
        "anterior": "Previous", "siguiente": "Next", "principal": "Main",
    },
}


def traducir(texto, tabla):
    for es, en in tabla:
        if texto.startswith(es):
            return en + texto[len(es):]
    return texto


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


def tamano_legible(nbytes):
    if nbytes >= 1024 * 1024:
        return f"{nbytes / 1024 / 1024:.1f} MB".replace(".", ",")
    return f"{max(1, round(nbytes / 1024))} KB"


def info_imagen(ruta):
    """Devuelve (ancho, alto, componentes, es_jpeg) sin librerías externas."""
    try:
        with open(ruta, "rb") as f:
            cabecera = f.read(26)
            if cabecera[:8] == b"\x89PNG\r\n\x1a\n":
                ancho, alto = struct.unpack(">II", cabecera[16:24])
                return ancho, alto, 3, False
            if cabecera[:2] != b"\xff\xd8":
                return None, None, None, False
            f.seek(2)
            while True:
                marca = f.read(2)
                if len(marca) < 2 or marca[0] != 0xFF:
                    return None, None, None, True
                tipo = marca[1]
                largo = struct.unpack(">H", f.read(2))[0]
                if tipo in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    f.read(1)
                    alto, ancho = struct.unpack(">HH", f.read(4))
                    componentes = f.read(1)[0]
                    return ancho, alto, componentes, True
                f.seek(largo - 2, 1)
    except (OSError, struct.error, IndexError):
        return None, None, None, False


def escribir(ruta_relativa, contenido):
    destino = SALIDA / ruta_relativa
    destino.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(contenido, bytes):
        destino.write_bytes(contenido)
    else:
        destino.write_text(contenido, encoding="utf-8")


def leer_markdown(ruta):
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
    cuerpo = re.sub(r"<!--.*?-->", "", m.group(2), flags=re.S).strip()
    return datos, cuerpo


def json_en_html(dato):
    return json.dumps(dato, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# --------------------------------------------------------------- configuración

def url_github_pages():
    """En GitHub Actions, deduce la dirección pública del nombre de la cuenta y del repositorio.
    Así, si cambias el nombre de usuario o del repositorio, el sitio se corrige solo."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if os.environ.get("GITHUB_ACTIONS") != "true" or "/" not in repo:
        return None
    duenio, nombre = repo.split("/", 1)
    duenio = duenio.lower()
    if nombre.lower() == f"{duenio}.github.io":
        return f"https://{duenio}.github.io"
    return f"https://{duenio}.github.io/{nombre}"


def cargar_sitio():
    sitio = json.loads((RAIZ / "sitio.json").read_text(encoding="utf-8-sig"))
    url = sitio["url"]
    if "github.io" in url and url_github_pages():  # con dominio propio se respeta sitio.json
        url = url_github_pages()
    sitio["url"] = os.environ.get("SITE_URL", url).rstrip("/")
    sitio["dominio"] = re.sub(r"^https?://", "", sitio["url"])
    marca = sitio.setdefault("marca_agua", {})
    marca.setdefault("texto", "LINDEY")
    marca.setdefault("subtexto", f"Asesoramiento Universitario · WhatsApp {sitio['whatsapp_visible']}")
    marca.setdefault("pie", f"Biblioteca Lindey · {sitio['dominio']} · PIDE TU SOLUCIONARIO: WhatsApp {sitio['whatsapp_visible']}")
    marca.setdefault("proteger", True)
    contador = sitio.setdefault("contador_vistas", {})
    contador.setdefault("servicio", "https://abacus.jasoncameron.dev")
    contador.setdefault("espacio", "biblioteca-lindey")
    sitio["ruta_base"] = (urlparse(sitio["url"]).path.rstrip("/") + "/") or "/"
    sitio.setdefault("universidades", {})
    sitio.setdefault("orden_cursos", [])
    sitio.setdefault("cursos_en", {})
    sitio.setdefault("nombre_en", sitio["nombre"])
    sitio.setdefault("descripcion_en", sitio["descripcion"])
    return sitio


# ------------------------------------------------------------------ ejercicios

def leer_ejercicio(ruta, sitio):
    datos, enunciado = leer_markdown(ruta)
    faltan = [c for c in CAMPOS_EJERCICIO if not datos.get(c)]
    if faltan:
        raise ValueError("faltan campos: " + ", ".join(faltan))
    partes = re.split(r"^\[en\]\s*$", enunciado, maxsplit=1, flags=re.M)
    enunciado = partes[0].strip()
    enunciado_en = partes[1].strip() if len(partes) > 1 else ""
    if not enunciado:
        raise ValueError("falta el enunciado (texto debajo del segundo ---)")

    slug = slugify(ruta.stem)
    curso = datos["curso"]
    sigla = datos.get("universidad", "")
    curso_en = sitio["cursos_en"].get(curso, curso)
    etiqueta_en = traducir(datos.get("etiqueta", ""), ETIQUETAS_EN)
    tema_en = datos.get("tema_en", "")
    slug_en = slugify(datos.get("slug_en") or " ".join(p for p in (tema_en, sigla, etiqueta_en) if p))
    tiene_en = bool(tema_en and enunciado_en)
    ej = {
        "tiene_en": tiene_en,
        "tema_en": tema_en,
        "enunciado_en": enunciado_en,
        "palabras_en": [p.strip() for p in datos.get("palabras_en", "").split(",") if p.strip()],
        "curso_en": curso_en,
        "curso_en_slug": slugify(curso_en),
        "etiqueta_en": etiqueta_en,
        "evaluacion_en": traducir(datos.get("evaluacion", ""), EVALUACIONES_EN),
        "url_en": f"en/{slugify(curso_en)}/{slug_en}/" if tiene_en else "",
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
        ej[campo + "_info"] = info_imagen(origen)
        ej[campo + "_medidas"] = ej[campo + "_info"][:2]
    return ej


def programa_office():
    return shutil.which("soffice") or shutil.which("libreoffice")


def leer_documento(ruta, sitio):
    datos, cuerpo = leer_markdown(ruta)
    faltan = [c for c in CAMPOS_DOCUMENTO if not datos.get(c)]
    if faltan:
        raise ValueError("faltan campos: " + ", ".join(faltan))
    origen = CARPETA_PDFS / datos["archivo"]
    if not origen.exists():
        raise ValueError(f"no encuentro el archivo pdfs/{datos['archivo']}")
    extension = origen.suffix.lower()
    if extension in EXTENSIONES_WORD and not programa_office():
        raise ValueError(f"{origen.name} es un archivo de Word: guárdalo como PDF (Archivo → Guardar como → PDF) y sube ese PDF")
    if extension != ".pdf" and extension not in EXTENSIONES_WORD:
        raise ValueError(f"{origen.name}: solo se aceptan PDF o Word")
    slug = slugify(ruta.stem)
    sigla = datos.get("universidad", "")
    return {
        "archivo": ruta.name,
        "slug": slug,
        "titulo": datos["titulo"],
        "curso": datos["curso"],
        "curso_slug": slugify(datos["curso"]),
        "universidad": sigla,
        "universidad_nombre": sitio["universidades"].get(sigla, ""),
        "tipo": datos.get("tipo", "Documento"),
        "fecha": datos.get("fecha") or date.today().isoformat(),
        "palabras": [p.strip() for p in datos.get("palabras", "").split(",") if p.strip()],
        "descripcion": datos.get("descripcion", ""),
        "cuerpo": cuerpo,
        "origen": origen,
        "auto": False,
        "vistas": ("pdf-" + slug)[:64].rstrip("-"),
        "orden": numero_natural(datos.get("orden") or ruta.stem),
        "url": f"pdfs/{slug}/",
        "pdf_url": f"pdfs/archivos/{slug}.pdf",
    }


def cargar(carpeta, lector, sitio):
    elementos, errores = [], []
    if not carpeta.exists():
        return elementos
    for ruta in sorted(carpeta.glob("*.md")):
        if ruta.name.startswith("_"):
            continue
        try:
            elementos.append(lector(ruta, sitio))
        except ValueError as e:
            errores.append(f"  - {carpeta.name}/{ruta.name}: {e}")
    vistos = {}
    for el in elementos:
        for clave in ("url", "url_en"):
            if not el.get(clave):
                continue
            if el[clave] in vistos:
                errores.append(f"  - {carpeta.name}/{el['archivo']}: misma dirección que {vistos[el[clave]]}")
            vistos[el[clave]] = el["archivo"]
    if errores:
        print("No se pudo generar el sitio. Revisa estos archivos:\n" + "\n".join(errores))
        sys.exit(1)
    return elementos


def orden_curso(sitio, curso):
    orden = sitio["orden_cursos"]
    return (orden.index(curso) if curso in orden else len(orden), curso)


def orden_ejercicio(sitio):
    return lambda e: (orden_curso(sitio, e["curso"]), e["evaluacion"], numero_natural(e["etiqueta"]), e["tema"])


# ------------------------------------------------------------ miniaturas

def crear_miniatura(ej, ancho=480):
    """Miniatura WebP para carruseles. Sin Pillow, usa la imagen original."""
    ej["mini_url"], ej["mini_medidas"] = ej["imagen_url"], ej["imagen_medidas"]
    if Image is None:
        return
    destino = SALIDA / "img" / "mini" / f"{ej['slug']}.webp"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(ej["imagen_origen"]) as im:
        im = im.convert("RGB")
        alto = round(im.height * ancho / im.width)
        im.resize((ancho, alto), Image.LANCZOS).save(destino, "WEBP", quality=80, method=6)
    ej["mini_url"], ej["mini_medidas"] = f"img/mini/{ej['slug']}.webp", (ancho, alto)


# ------------------------------------------------------------------- PDF

ANCHOS_HELVETICA = dict(zip(
    " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
    [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556,
     556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778,
     722, 278, 500, 667, 556, 833, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
     278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
     556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584]))

SUSTITUCIONES_PDF = {
    "θ": "theta", "μ": "µ", "σ": "sigma_", "ω": "w", "γ": "gamma_", "δ": "delta", "Δ": "Delta",
    "ν": "nu", "α": "alfa", "β": "beta", "π": "pi", "ρ": "rho", "τ": "tau", "ε": "epsilon",
    "−": "-", "≈": "~", "→": "->", "≤": "<=", "≥": ">=", "√": "raiz", "∑": "Suma", "Σ": "Suma",
    "⁰": "^0", "⁴": "^4", "⁵": "^5", "⁶": "^6", "⁷": "^7", "⁸": "^8", "⁹": "^9", "⁻": "^-",
}
SUSTITUCIONES_PDF.update({chr(0x2080 + i): str(i) for i in range(10)})

COLORES = {
    "marino": "0.024 0.059 0.153", "marino_medio": "0.043 0.114 0.290", "lima": "0.518 1 0.247",
    "celeste": "0.686 0.847 0.973", "celeste_osc": "0.102 0.392 0.659", "texto": "0.075 0.129 0.247",
    "gris": "0.290 0.353 0.471", "fondo_cta": "0.945 0.988 0.918", "blanco": "1 1 1",
}


def pdf_plano(texto):
    return "".join(SUSTITUCIONES_PDF.get(c, c) for c in texto)


def pdf_cadena(texto):
    datos = pdf_plano(texto).encode("cp1252", "replace")
    return b"(" + datos.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def ancho_pdf(texto, tam, negrita=False):
    total = 0
    for c in pdf_plano(texto):
        base = unicodedata.normalize("NFKD", c)[:1] or c
        total += ANCHOS_HELVETICA.get(base, 556)
    return total * tam / 1000 * (1.07 if negrita else 1)


# --------------------------------------------------- páginas de los documentos

def convertir_a_pdf(origen):
    """Devuelve la ruta de un PDF: el mismo archivo o el Word convertido con LibreOffice."""
    if origen.suffix.lower() == ".pdf":
        return origen
    carpeta = Path(tempfile.mkdtemp(prefix="lindey-"))
    subprocess.run([programa_office(), "--headless", "--convert-to", "pdf", "--outdir", str(carpeta), str(origen)],
                   check=True, capture_output=True, timeout=300)
    return carpeta / (origen.stem + ".pdf")


def pdf_marca_agua(ancho, alto, sitio):
    """PDF de una página (ancho × alto) con la marca de agua: sello diagonal translúcido y pie con la web."""
    marca = sitio["marca_agua"]
    angulo = math.atan2(alto, ancho)
    c, s = math.cos(angulo), math.sin(angulo)
    diagonal = math.hypot(ancho, alto)
    cx, cy = ancho / 2, alto / 2

    def linea(texto, tam, desplazamiento, fuente):
        """Texto centrado en la diagonal; desplazamiento = distancia de la línea base al centro (perpendicular)."""
        w = ancho_pdf(texto, tam, fuente == "FLb")
        x = cx - c * w / 2 - s * desplazamiento
        y = cy - s * w / 2 + c * desplazamiento
        return (f"BT /{fuente} {tam:.2f} Tf {c:.5f} {s:.5f} {-s:.5f} {c:.5f} {x:.2f} {y:.2f} Tm ".encode()
                + pdf_cadena(texto) + b" Tj ET\n")

    grande = marca["texto"]
    tam = min(diagonal * 0.55 / (ancho_pdf(grande, 1, True) or 1), alto * 0.22)
    tam_sub = max(9.0, min(tam * 0.2, diagonal * 0.6 / (ancho_pdf(marca["subtexto"], 1, True) or 1)))
    tam_pie = 6.8 if ancho < 700 else 8.5
    pie = marca["pie"]
    while ancho_pdf(pie, tam_pie) > ancho - 24 and tam_pie > 4:
        tam_pie -= 0.2
    contenido = (b"q /GLa gs " + COLORES["marino_medio"].encode() + b" rg\n"
                 + linea(grande, tam, -tam * 0.36, "FLb")
                 + b"/GLb gs\n" + linea(marca["subtexto"], tam_sub, -tam * 0.36 - tam_sub * 1.9, "FLb")
                 + b"Q\nq /GLc gs " + COLORES["celeste_osc"].encode() + b" rg BT /FLr " + f"{tam_pie:.2f}".encode()
                 + f" Tf {(ancho - ancho_pdf(pie, tam_pie)) / 2:.2f} 9 Td ".encode() + pdf_cadena(pie) + b" Tj ET Q\n")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ancho:.2f} {alto:.2f}] /Contents 4 0 R "
        f"/Resources << /Font << /FLb 5 0 R /FLr 6 0 R >> /ExtGState << /GLa 7 0 R /GLb 8 0 R /GLc 9 0 R >> >> >>".encode(),
        f"<< /Length {len(contenido)} >>\nstream\n".encode() + contenido + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /ExtGState /ca 0.09 /CA 0.09 >>",
        b"<< /Type /ExtGState /ca 0.16 /CA 0.16 >>",
        b"<< /Type /ExtGState /ca 0.9 /CA 0.9 >>",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    posiciones = []
    for n, obj in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += f"{n} 0 obj\n".encode() + obj + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    salida += b"".join(f"{p:010d} 00000 n \n".encode() for p in posiciones)
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return bytes(salida), (ancho - ancho_pdf(pie, tam_pie)) / 2, ancho_pdf(pie, tam_pie), tam_pie


def marcar_pdf(origen, sitio, d):
    """Pone la marca de agua Lindey en cada página.
    Devuelve (pdf_para_el_visor, pdf_para_descargar) o None si no se pudo (se publica el original)."""
    try:
        from pypdf import PdfReader, PdfWriter, Transformation
        from pypdf.annotations import Link
        from pypdf.constants import UserAccessPermissions as Permiso
    except ImportError:
        print("Aviso: instala pypdf para poner la marca de agua en los PDF (pip install pypdf)")
        return None
    try:
        lector = PdfReader(str(origen))
        if lector.is_encrypted and not lector.decrypt(""):
            raise ValueError("el PDF tiene contraseña")
        escritor = PdfWriter(clone_from=lector)
        if escritor.is_encrypted:
            escritor._encryption = None
        sellos = {}
        wa = enlace_whatsapp(sitio, f"Hola Lindey, vi el PDF «{d['titulo']}» y quiero pedir mi solucionario.")
        for i, hoja in enumerate(escritor.pages):
            if hoja.get("/Rotate", 0) % 360:
                hoja.transfer_rotation_to_content()
            caja = hoja.cropbox
            ancho, alto = float(caja.width), float(caja.height)
            clave = (round(ancho, 1), round(alto, 1))
            if clave not in sellos:
                datos, x_pie, w_pie, tam_pie = pdf_marca_agua(ancho, alto, sitio)
                sellos[clave] = (PdfReader(io.BytesIO(datos)).pages[0], x_pie, w_pie, tam_pie)
            sello, x_pie, w_pie, tam_pie = sellos[clave]
            izq, abajo = float(caja.left), float(caja.bottom)
            hoja.merge_transformed_page(sello, Transformation().translate(izq, abajo), over=True)
            escritor.add_annotation(i, Link(rect=(izq + x_pie, abajo + 6, izq + x_pie + w_pie, abajo + 10 + tam_pie),
                                            url=wa, border=[0, 0, 0]))
        escritor.add_metadata({"/Title": d["titulo"], "/Author": "Lindey Asesoramiento Universitario",
                               "/Subject": f"{d['tipo']} de {d['curso']} – Biblioteca Lindey ({sitio['dominio']})",
                               "/Keywords": ", ".join([d["curso"], *d["palabras"], "Lindey"]),
                               "/Creator": f"Biblioteca Lindey – {sitio['url']}/"})
        visor = io.BytesIO()
        escritor.write(visor)
        if not sitio["marca_agua"].get("proteger"):
            return visor.getvalue(), visor.getvalue()
        # Se puede leer e imprimir, pero no editar ni copiar (para que no quiten la marca de agua).
        permisos = Permiso.all()
        for quitar in (Permiso.MODIFY, Permiso.EXTRACT, Permiso.ADD_OR_MODIFY, Permiso.ASSEMBLE_DOC):
            permisos &= ~quitar
        for algoritmo in ("AES-256", "RC4-128"):
            try:
                escritor.encrypt(user_password="", owner_password=secrets.token_hex(16),
                                 permissions_flag=permisos, algorithm=algoritmo)
                break
            except Exception:
                continue
        descarga = io.BytesIO()
        escritor.write(descarga)
        return visor.getvalue(), descarga.getvalue()
    except Exception as e:  # el documento se publica igual, sin marca
        print(f"Aviso: no se pudo poner la marca de agua en {Path(origen).name}: {e}")
        return None


def renderizar_paginas(ruta_pdf, slug, ruta_texto=None):
    """Convierte cada página del PDF en imagen (grande y miniatura) y extrae su texto (de ruta_texto si se da)."""
    ruta_texto = ruta_texto or ruta_pdf
    carpeta_rel = f"pdfs/paginas/{slug}"
    destino = SALIDA / carpeta_rel
    destino.mkdir(parents=True, exist_ok=True)
    paginas, textos = [], []
    if shutil.which("pdftoppm"):
        for prefijo, ancho, calidad in (("g", 1000, 82), ("m", 360, 76)):
            subprocess.run(["pdftoppm", "-jpeg", "-jpegopt", f"quality={calidad}", "-scale-to-x", str(ancho),
                            "-scale-to-y", "-1", str(ruta_pdf), str(destino / prefijo)], check=True, capture_output=True)
        def numero(r):
            return int(r.stem.rsplit("-", 1)[-1])
        grandes = sorted(destino.glob("g-*.jpg"), key=numero)
        minis = sorted(destino.glob("m-*.jpg"), key=numero)
        for i, (g, m) in enumerate(zip(grandes, minis), 1):
            g.rename(destino / f"pagina-{i}.jpg")
            m.rename(destino / f"mini-{i}.jpg")
            ancho, alto = info_imagen(destino / f"pagina-{i}.jpg")[:2]
            paginas.append({"i": f"{carpeta_rel}/pagina-{i}.jpg", "m": f"{carpeta_rel}/mini-{i}.jpg", "w": ancho, "h": alto})
        if shutil.which("pdftotext"):
            salida = subprocess.run(["pdftotext", "-enc", "UTF-8", str(ruta_texto), "-"], capture_output=True)
            textos = [t.strip() for t in salida.stdout.decode("utf-8", "replace").split("\f")]
        return paginas, textos
    try:
        import fitz  # PyMuPDF, alternativa si no hay Poppler (por ejemplo en Cloudflare Pages)
    except ImportError:
        return paginas, textos
    try:
        with fitz.open(str(ruta_pdf)) as pdf, fitz.open(str(ruta_texto)) as pdf_texto:
            for i, hoja in enumerate(pdf, 1):
                for nombre, ancho in (("pagina", 1000), ("mini", 360)):
                    zoom = ancho / hoja.rect.width
                    hoja.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).save(str(destino / f"{nombre}-{i}.png"))
                ancho, alto = info_imagen(destino / f"pagina-{i}.png")[:2]
                paginas.append({"i": f"{carpeta_rel}/pagina-{i}.png", "m": f"{carpeta_rel}/mini-{i}.png", "w": ancho, "h": alto})
                textos.append(pdf_texto[i - 1].get_text().strip() if i <= len(pdf_texto) else "")
    except Exception as e:  # el documento se publica igual, con el visor del navegador
        print(f"Aviso: no se pudieron generar las páginas de {ruta_pdf.name}: {e}")
    return paginas, textos


def markdown_simple(texto):
    """Convierte la transcripción (## títulos, párrafos, listas con -, tablas con |, **negrita**) a HTML."""
    def en_linea(t):
        return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc(t))
    salida = []
    for bloque in re.split(r"\n\s*\n", texto.strip()):
        lineas = [l.strip() for l in bloque.split("\n") if l.strip()]
        if not lineas:
            continue
        if lineas[0].startswith("#"):
            nivel = len(lineas[0]) - len(lineas[0].lstrip("#"))
            etiqueta = "h3" if nivel <= 2 else "h4"
            salida.append(f"<{etiqueta}>{en_linea(lineas[0].lstrip('#').strip())}</{etiqueta}>")
            lineas = lineas[1:]
            if not lineas:
                continue
        if all(l.startswith("|") for l in lineas):  # tabla: | a | b | (2.ª fila |---| = encabezado)
            filas = [[c.strip() for c in l.strip("|").split("|")] for l in lineas]
            cab = []
            if len(filas) > 1 and all(re.fullmatch(r":?-{2,}:?", c) for c in filas[1] if c):
                cab, filas = filas[0], filas[2:]
            html = '<div class="tabla-datos"><table>'
            if cab:
                html += "<thead><tr>" + "".join(f"<th>{en_linea(c)}</th>" for c in cab) + "</tr></thead>"
            html += "<tbody>" + "".join("<tr>" + "".join(f"<td>{en_linea(c)}</td>" for c in f) + "</tr>" for f in filas)
            salida.append(html + "</tbody></table></div>")
        elif all(l.startswith(("- ", "* ")) for l in lineas):
            salida.append("<ul>" + "".join(f"<li>{en_linea(l[2:])}</li>" for l in lineas) + "</ul>")
        elif lineas[0].startswith("Datos de la figura:"):
            salida.append('<p class="datos"><strong>Datos de la figura:</strong>' + en_linea(" ".join(lineas))[len("Datos de la figura:"):] + "</p>")
        else:
            salida.append(f"<p>{en_linea(' '.join(lineas))}</p>")
    return "\n".join(salida)


def texto_paginas_html(textos):
    bloques = []
    for i, t in enumerate(textos, 1):
        parrafos_pag = [" ".join(p.split()) for p in re.split(r"\n\s*\n", t) if p.strip()]
        if parrafos_pag:
            bloques.append(f"<h3>Página {i}</h3>" + "".join(f"<p>{esc(p)}</p>" for p in parrafos_pag))
    return "\n".join(bloques)


def preparar_documento(sitio, d):
    """Copia el PDF al sitio, genera sus páginas y arma la transcripción."""
    destino = SALIDA / d["pdf_url"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    original = para_visor = convertir_a_pdf(d["origen"])
    marcado = marcar_pdf(original, sitio, d)
    if marcado:
        para_visor = Path(tempfile.mkdtemp(prefix="lindey-")) / "visor.pdf"
        para_visor.write_bytes(marcado[0])
        destino.write_bytes(marcado[1])
        d["con_marca"] = True
    else:
        shutil.copy2(original, destino)
    d["bytes"] = destino.stat().st_size
    d["paginas"], textos = renderizar_paginas(para_visor, d["slug"], original)
    d["n_paginas"] = len(d["paginas"])
    d["portada"] = d["paginas"][0] if d["paginas"] else None
    if d.get("cuerpo"):
        d["contenido_html"] = markdown_simple(d["cuerpo"])
        d["texto_plano"] = d["cuerpo"]
    elif any(textos):
        d["contenido_html"] = texto_paginas_html(textos)
        d["texto_plano"] = "\n\n".join(textos)
    else:
        d["contenido_html"] = ""
        d["texto_plano"] = ""
    if not d["descripcion"]:
        limpio = re.sub(r"^#+\s.*$", "", d["texto_plano"], flags=re.M)
        d["descripcion"] = recortar(limpio or f"{d['tipo']} de {d['curso']} en PDF.", 158)


# ------------------------------------------------------------- banderitas

def _estrella(cx, cy, r, color):
    puntos = []
    for i in range(10):
        radio = r if i % 2 == 0 else r * 0.4
        ang = math.radians(-90 + i * 36)
        puntos.append(f"{cx + radio * math.cos(ang):.2f},{cy + radio * math.sin(ang):.2f}")
    return f'<polygon points="{" ".join(puntos)}" fill="{color}"/>'


def _franjas(colores, vertical=False):
    n = len(colores)
    paso = (30 if vertical else 20) / n
    if vertical:
        return "".join(f'<rect x="{i * paso:.3f}" y="0" width="{paso + .05:.3f}" height="20" fill="{c}"/>' for i, c in enumerate(colores))
    return "".join(f'<rect x="0" y="{i * paso:.3f}" width="30" height="{paso + .05:.3f}" fill="{c}"/>' for i, c in enumerate(colores))


def _bandas(lista):
    """lista de (color, alto) de arriba hacia abajo"""
    y, salida = 0.0, ""
    for color, alto in lista:
        salida += f'<rect x="0" y="{y:.3f}" width="30" height="{alto + .05:.3f}" fill="{color}"/>'
        y += alto
    return salida


# Banderas simplificadas (sin escudos) en 30 × 20
BANDERAS = {
    "chile": '<rect width="30" height="20" fill="#fff"/><rect y="10" width="30" height="10" fill="#D52B1E"/>'
             '<rect width="10" height="10" fill="#0039A6"/>' + _estrella(5, 5, 3, "#fff"),
    "ecuador": _bandas([("#FFDD00", 10), ("#034EA2", 5), ("#ED1C24", 5)]) + '<circle cx="15" cy="10" r="2.6" fill="#8C6A2E"/>',
    "uruguay": "".join(f'<rect y="{i * 20 / 9:.3f}" width="30" height="{20 / 9 + .05:.3f}" fill="{"#fff" if i % 2 == 0 else "#0038A8"}"/>' for i in range(9))
               + f'<rect width="11.5" height="{20 / 9 * 5:.3f}" fill="#fff"/><circle cx="5.7" cy="5.6" r="3" fill="#FCD116"/>',
    "peru": _franjas(["#D91023", "#fff", "#D91023"], vertical=True),
    "espana": _bandas([("#AA151B", 5), ("#F1BF00", 10), ("#AA151B", 5)]),
    "mexico": _franjas(["#006847", "#fff", "#CE1126"], vertical=True) + '<circle cx="15" cy="10" r="2.6" fill="#8C5A2B"/>',
    "argentina": _franjas(["#74ACDF", "#fff", "#74ACDF"]) + '<circle cx="15" cy="10" r="2.3" fill="#F6B40E"/>',
    "costa-rica": _bandas([("#002B7F", 3.33), ("#fff", 3.33), ("#CE1126", 6.68), ("#fff", 3.33), ("#002B7F", 3.33)]),
    "colombia": _bandas([("#FCD116", 10), ("#003893", 5), ("#CE1126", 5)]),
    "bolivia": _franjas(["#D52B1E", "#F9E300", "#007934"]),
    "venezuela": _franjas(["#FFCC00", "#00247D", "#CF142B"])
                 + "".join(f'<circle cx="{15 + 6.2 * math.cos(math.radians(a)):.2f}" cy="{12.6 - 4.4 * math.sin(math.radians(a)):.2f}" r=".75" fill="#fff"/>'
                           for a in (160, 140, 120, 100, 80, 60, 40, 20)),
    "paraguay": _franjas(["#D52B1E", "#fff", "#0038A8"]) + '<circle cx="15" cy="10" r="2" fill="none" stroke="#2E7D32" stroke-width=".8"/>',
    "panama": '<rect width="30" height="20" fill="#fff"/><rect x="15" width="15" height="10" fill="#DA121A"/>'
              '<rect y="10" width="15" height="10" fill="#072357"/>' + _estrella(7.5, 5, 2.8, "#072357") + _estrella(22.5, 15, 2.8, "#DA121A"),
    "guatemala": _franjas(["#4997D0", "#fff", "#4997D0"], vertical=True) + '<circle cx="15" cy="10" r="2.4" fill="#6DA544"/>',
    "honduras": _franjas(["#18C3DF", "#fff", "#18C3DF"])
                + "".join(f'<circle cx="{x}" cy="{y}" r=".9" fill="#18C3DF"/>' for x, y in ((15, 10), (11, 8.4), (11, 11.6), (19, 8.4), (19, 11.6))),
    "el-salvador": _franjas(["#0F47AF", "#fff", "#0F47AF"]) + '<circle cx="15" cy="10" r="2.2" fill="#FFCC00"/>',
    "nicaragua": _franjas(["#0067C6", "#fff", "#0067C6"]) + '<circle cx="15" cy="10" r="2.2" fill="none" stroke="#0067C6" stroke-width=".8"/>',
    "republica-dominicana": '<rect width="30" height="20" fill="#fff"/><rect width="13" height="8.5" fill="#002D62"/>'
                            '<rect x="17" width="13" height="8.5" fill="#CE1126"/><rect y="11.5" width="13" height="8.5" fill="#CE1126"/>'
                            '<rect x="17" y="11.5" width="13" height="8.5" fill="#002D62"/>',
    "cuba": "".join(f'<rect y="{i * 4}" width="30" height="4.05" fill="{"#002A8F" if i % 2 == 0 else "#fff"}"/>' for i in range(5))
            + '<polygon points="0,0 15,10 0,20" fill="#CF142B"/>' + _estrella(5, 10, 2.8, "#fff"),
}


def bandera(pais):
    figura = BANDERAS.get(slugify(pais))
    if not figura:
        return '<span class="pais__bandera pais__bandera--vacia" aria-hidden="true"></span>'
    return (f'<span class="pais__bandera" aria-hidden="true"><svg viewBox="0 0 30 20" width="27" height="18" '
            f'preserveAspectRatio="none">{figura}</svg></span>')


def franja_paises(sitio):
    """Banderitas que desfilan en la portada; cada una abre WhatsApp con el país en el mensaje."""
    paises = sitio.get("paises") or []
    if not paises:
        return ""
    def items(oculto):
        extra = ' tabindex="-1"' if oculto else ""
        return "".join(
            f'<li><a class="pais" href="{esc(enlace_whatsapp(sitio, f"Hola Lindey, soy de {p} y quiero pedir mi solucionario."))}" '
            f'rel="noopener"{extra}>{bandera(p)}<span>{esc(p)}</span></a></li>' for p in paises)
    return f"""<div class="paises">
      <p class="paises__titulo">Atendemos estudiantes de toda Latinoamérica y España</p>
      <div class="paises__marco">
        <ul class="paises__pista" aria-label="Países que atendemos">{items(False)}</ul>
        <ul class="paises__pista paises__pista--copia" aria-hidden="true">{items(True)}</ul>
      </div>
    </div>"""


# --------------------------------------------------------------- piezas HTML

ICONO_CHAT = (
    '<svg aria-hidden="true" viewBox="0 0 24 24" width="26" height="26">'
    '<path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.3-.4.7-1.4.1-.2 0-.3 0-.5l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.7 11.8 11.8 0 0 0 4.5 4c1.7.7 2.3.8 3.2.6a2.7 2.7 0 0 0 1.8-1.2 2.2 2.2 0 0 0 .1-1.3c0-.1-.2-.2-.5-.3z"/>'
    "</svg>"
)

ICONO_PDF = (
    '<svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" '
    'd="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2zm7 1.5V9h5.5L13 3.5zM7.5 13v5h1.2v-1.6h.7a1.7 1.7 0 0 0 0-3.4H7.5zm1.2 1h.7a.7.7 0 0 1 0 1.4h-.7V14zm3-1v5h1.6a2.5 2.5 0 0 0 0-5h-1.6zm1.2 1h.4a1.5 1.5 0 0 1 0 3h-.4v-3zm3.1-1v5h1.2v-2h1.6v-1h-1.6v-1h1.8v-1h-3z"/></svg>'
)


def icono(trazo):
    return f'<svg aria-hidden="true" viewBox="0 0 24 24" width="18" height="18"><path fill="currentColor" d="{trazo}"/></svg>'


ICONO_FACEBOOK = icono("M14 8h3V4h-3c-2.8 0-4.5 1.8-4.5 4.6V11H7v4h2.5v7h4v-7H17l.5-4h-4V8.9c0-.6.4-.9 1-.9z")
ICONO_TELEGRAM = icono("M21.4 3.6 2.9 10.8c-1.3.5-1.2 1.2-.2 1.5l4.7 1.5 1.8 5.6c.2.6.4.8.9.8.4 0 .6-.2.9-.5l2.3-2.2 4.7 3.5c.9.5 1.5.2 1.7-.8l3.1-14.6c.3-1.3-.5-1.8-1.4-1.5zm-12.8 10 9.2-5.8c.4-.3.8-.1.5.2l-7.6 6.9-.3 3.3-1.8-4.6z")
ICONO_ENLACE = icono("M10.6 13.4a1 1 0 0 1 0-1.4l3.4-3.4a1 1 0 1 1 1.4 1.4L12 13.4a1 1 0 0 1-1.4 0zM8.5 19a4.5 4.5 0 0 1-3.2-7.7l2.1-2.1a1 1 0 0 1 1.4 1.4l-2.1 2.1a2.5 2.5 0 0 0 3.5 3.5l2.1-2.1a1 1 0 0 1 1.4 1.4l-2.1 2.1A4.5 4.5 0 0 1 8.5 19zm7.6-4.8a1 1 0 0 1-.7-1.7l2.1-2.1a2.5 2.5 0 0 0-3.5-3.5L11.9 9a1 1 0 0 1-1.4-1.4l2.1-2.1a4.5 4.5 0 0 1 6.4 6.4l-2.1 2.1a1 1 0 0 1-.8.2z")
ICONO_COMPARTIR = icono("M18 16a3 3 0 0 0-2.4 1.2l-6.7-3.4a3 3 0 0 0 0-1.6l6.7-3.4A3 3 0 1 0 15 7l-6.7 3.4a3 3 0 1 0 0 3.2L15 17a3 3 0 1 0 3-1z")


def enlace_whatsapp(sitio, mensaje):
    return f"https://wa.me/{sitio['whatsapp']}?text={quote(mensaje)}"


def compartir(url_abs, texto, idioma="es"):
    """Botones para compartir con amigos: WhatsApp, Facebook, Telegram, copiar enlace y menú del celular."""
    t = TEXTOS[idioma]
    wa = f"https://wa.me/?text={quote(f'{texto} 👉 {url_abs}')}"
    fb = f"https://www.facebook.com/sharer/sharer.php?u={quote(url_abs, safe='')}"
    tg = f"https://t.me/share/url?url={quote(url_abs, safe='')}&text={quote(texto)}"
    return f"""<div class="compartir" data-compartir data-url="{esc(url_abs)}" data-texto="{esc(texto)}">
  <span class="compartir__titulo">{ICONO_COMPARTIR}{t['compartir']}</span>
  <div class="compartir__botones">
    <a class="compartir__btn compartir__btn--wa" href="{esc(wa)}" target="_blank" rel="noopener">{ICONO_CHAT}WhatsApp</a>
    <a class="compartir__btn compartir__btn--fb" href="{esc(fb)}" target="_blank" rel="noopener">{ICONO_FACEBOOK}Facebook</a>
    <a class="compartir__btn compartir__btn--tg" href="{esc(tg)}" target="_blank" rel="noopener">{ICONO_TELEGRAM}Telegram</a>
    <button class="compartir__btn compartir__btn--copiar" type="button" data-copiar>{ICONO_ENLACE}<span>{t['copiar']}</span></button>
    <button class="compartir__btn compartir__btn--mas" type="button" data-nativo hidden>{ICONO_COMPARTIR}{t['mas_opciones']}</button>
  </div>
</div>"""


def pagina(sitio, *, raiz, ruta, titulo, descripcion, contenido, imagen_social=None,
           tipo_og="website", jsonld=None, mensaje_wa=None, indexar=True, cuerpo_clase="",
           idioma="es", alternos=None):
    """Plantilla común. alternos = {"es": ruta, "en": ruta} enlaza las dos versiones del mismo contenido."""
    t = TEXTOS[idioma]
    en = idioma == "en"
    canonical = f"{sitio['url']}/{ruta}"
    imagen_social = imagen_social or f"{sitio['url']}/og-biblioteca-lindey.jpg"
    mensaje_wa = mensaje_wa or ("Hi Lindey, I found the Lindey Library and I'd like to get the solution." if en
                                else "Hola Lindey, vi la Biblioteca Lindey y quiero pedir mi solucionario.")
    bloques_ld = "".join(
        f'\n<script type="application/ld+json">{json.dumps(b, ensure_ascii=False).replace("<", "\\u003c")}</script>'
        for b in (jsonld or [])
    )
    verificacion = (
        f'\n<meta name="google-site-verification" content="{esc(sitio["google_verificacion"])}">'
        if sitio.get("google_verificacion") else ""
    )
    alternos = alternos or {}
    hreflang = ""
    if alternos.get("es") is not None and alternos.get("en") is not None:
        hreflang = "".join(f'\n<link rel="alternate" hreflang="{l}" href="{esc(sitio["url"])}/{esc(alternos[c])}">'
                           for l, c in (("es", "es"), ("en", "en"), ("x-default", "es")))
    otro = alternos.get(t["otro_lang"])
    enlace_otro = raiz + (otro if otro is not None else ("" if en else "en/"))
    inicio = raiz + ("en/" if en else "")
    robots = "index, follow, max-image-preview:large" if indexar else "noindex"
    wa = esc(enlace_whatsapp(sitio, mensaje_wa))
    nombre = sitio["nombre_en"] if en else sitio["nombre"]
    if en:
        nav = (f'<a href="{inicio}#cursos">{t["cursos"]}</a>\n      <a href="{raiz}pdfs/">PDFs</a>')
        enlaces_pie = [(f"{raiz}", "Versión en español"), (f"{raiz}pdfs/", "PDF repository (Spanish)")]
    else:
        nav = (f'<a href="{inicio}#cursos">{t["cursos"]}</a>\n      <a href="{inicio}#universidades">{t["universidades"]}</a>'
               f'\n      <a href="{raiz}pdfs/">PDFs</a>')
        enlaces_pie = [(f"{raiz}ejercicios/", "Índice de ejercicios"), (f"{raiz}pdfs/", "Repositorio de PDFs"),
                       (f"{raiz}en/", "English version")]
    return f"""<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self' {esc(sitio['contador_vistas']['servicio'].rstrip('/'))}; object-src 'none'; base-uri 'self'; form-action 'self'; upgrade-insecure-requests">
<meta name="referrer" content="strict-origin-when-cross-origin">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descripcion)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">{hreflang}
<meta property="og:site_name" content="{esc(nombre)}">
<meta property="og:locale" content="{t['locale']}">
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
<body class="{cuerpo_clase}" data-raiz="{raiz}" data-vistas-api="{esc(sitio['contador_vistas']['servicio'].rstrip('/'))}" data-vistas-espacio="{esc(sitio['contador_vistas']['espacio'])}">
<a class="saltar" href="#contenido">{t['saltar']}</a>
<header class="cabecera">
  <div class="envoltura cabecera__in">
    <a class="marca" href="{inicio}" aria-label="{t['inicio']}">
      <img src="{raiz}logo-lindey.png" alt="Lindey Asesoramiento Universitario" width="184" height="56">
      <span class="marca__bib">{t['biblioteca']}</span>
    </a>
    <nav class="cabecera__nav" aria-label="{t['principal']}">
      {nav}
      <a class="cabecera__idioma" href="{enlace_otro}" hreflang="{t['otro_lang']}" lang="{t['otro_lang']}">{t['otro_idioma']}</a>
    </nav>
  </div>
</header>
<main id="contenido">
{contenido}
</main>
{pie_de_pagina(sitio, t, raiz, en, wa, enlaces_pie)}
<a class="flotante" href="{wa}" rel="noopener" aria-label="{t['aria_asesoria']} {esc(sitio['whatsapp_visible'])}">{ICONO_CHAT}<span>{t['asesoria']}</span></a>
<script src="{raiz}buscador.js" defer></script>
</body>
</html>
"""


def pie_de_pagina(sitio, t, raiz, en, wa, enlaces):
    """Pie de página grande: marca y botón, cursos, universidades y contacto."""
    datos = sitio.get("pie_datos", {})
    if en:
        cursos = [(f"{raiz}en/{slugify(sitio['cursos_en'].get(c, c))}/", sitio["cursos_en"].get(c, c))
                  for c in datos.get("cursos_en", [])]
    else:
        cursos = ([(f"{raiz}{slugify(c)}/", c) for c in datos.get("cursos", [])]
                  + [(f"{raiz}pdfs/#{slugify(c)}", c) for c in datos.get("cursos_pdf", [])])
    lista_cursos = "".join(f'<li><a href="{esc(h)}">{esc(n)}</a></li>' for h, n in cursos)
    lista_unis = "".join(
        f'<li><a class="pie__uni" href="{raiz}universidad/{slugify(u)}/"><strong>{esc(u)}</strong>'
        f'{f"<small>{esc(sitio["universidades"][u])}</small>" if sitio["universidades"].get(u) else ""}</a></li>'
        for u in datos.get("universidades", []))
    lista_contacto = (f'<li><a href="{wa}" rel="noopener">WhatsApp {esc(sitio["whatsapp_visible"])}</a></li>'
                      f'<li><a href="{esc(sitio["facebook"])}" rel="noopener">Facebook</a></li>'
                      + "".join(f'<li><a href="{esc(h)}">{esc(n)}</a></li>' for h, n in enlaces))
    columnas = [(t["cursos"], lista_cursos), (t["universidades"], lista_unis), (t["contacto"], lista_contacto)]
    bloques = "".join(f"""
    <nav class="pie__col" aria-label="{esc(titulo)}">
      <h2>{esc(titulo)}</h2>
      <ul>{lista}</ul>
    </nav>""" for titulo, lista in columnas if lista)
    nombre = sitio["nombre_en"] if en else sitio["nombre"]
    return f"""<footer class="pie">
  <div class="envoltura pie__rejilla">
    <div class="pie__marca">
      <img src="{raiz}logo-lindey.png" alt="Lindey Asesoramiento Universitario" width="184" height="56" loading="lazy">
      <p><strong>{esc(nombre)}</strong> · {t['pie']}</p>
      <a class="pie__cta" href="{wa}" rel="noopener">{ICONO_CHAT}<span>{t['asesoria']}</span></a>
    </div>{bloques}
  </div>
  <div class="envoltura pie__base">
    <p>© {date.today().year} Lindey Asesoramiento Universitario · {t['derechos']}</p>
  </div>
</footer>"""


def migas(raiz, pasos, idioma="es"):
    t = TEXTOS[idioma]
    inicio = raiz + ("en/" if idioma == "en" else "")
    partes = [f'<a href="{inicio}">{t["biblioteca"]}</a>']
    for texto, enlace in pasos:
        partes.append(f'<a href="{enlace}">{esc(texto)}</a>' if enlace else f'<span aria-current="page">{esc(texto)}</span>')
    return f'<nav class="migas" aria-label="{t["ruta"]}">' + '<span class="migas__sep">›</span>'.join(partes) + "</nav>"


def migas_jsonld(sitio, pasos, idioma="es"):
    inicio = (sitio["url"] + "/en/") if idioma == "en" else (sitio["url"] + "/")
    elementos = [{"@type": "ListItem", "position": 1, "name": TEXTOS[idioma]["biblioteca"], "item": inicio}]
    for i, (nombre, ruta) in enumerate(pasos, start=2):
        elementos.append({"@type": "ListItem", "position": i, "name": nombre, "item": f"{sitio['url']}/{ruta}"})
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": elementos}


def meta_ejercicio(ej, con_curso=True, idioma="es"):
    s = "_en" if idioma == "en" else ""
    partes = [ej["curso" + s]] if con_curso else []
    partes += [p for p in (ej["universidad"], ej["evaluacion" + s], ej["etiqueta" + s]) if p]
    return " · ".join(partes)


def resumen_enunciado(ej, limite=170):
    return recortar(ej["enunciado"].split("\n\n")[0], limite)


def ficha(ej, raiz, con_curso=True, carga="lazy", idioma="es"):
    ancho, alto = ej["mini_medidas"]
    dims = f' width="{ancho}" height="{alto}"' if ancho else ""
    s = "_en" if idioma == "en" else ""
    return f"""<li class="ficha">
  <a href="{raiz}{ej['url' + s]}">
    <img src="{raiz}{ej['mini_url']}" alt="{esc(ej['tema' + s])} – {esc(meta_ejercicio(ej, True, idioma))}"{dims} loading="{carga}" decoding="async">
    <span class="ficha__cuerpo">
      <span class="ficha__meta">{esc(meta_ejercicio(ej, con_curso, idioma))}</span>
      <span class="ficha__titulo">{esc(ej['tema' + s])}</span>
    </span>
  </a>
</li>"""


def meta_documento(d):
    paginas = f"{d['n_paginas']} {'página' if d['n_paginas'] == 1 else 'páginas'}" if d.get("n_paginas") else "PDF"
    return " · ".join(p for p in (d["tipo"], d["universidad"], paginas) if p)


ICONO_OJO = ('<svg aria-hidden="true" viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" '
             'd="M12 5C6.5 5 2.7 9.3 1.5 12c1.2 2.7 5 7 10.5 7s9.3-4.3 10.5-7C21.3 9.3 17.5 5 12 5zm0 11.5a4.5 4.5 0 1 1 0-9 '
             '4.5 4.5 0 0 1 0 9zm0-2.3a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4z"/></svg>')


def etiqueta_vistas(d, clase, contar=False):
    """Contador de vistas tipo Calaméo; lo llena buscador.js (queda oculto si el servicio no responde)."""
    if not d.get("vistas"):
        return ""
    return (f'<span class="{clase}" data-vistas="{esc(d["vistas"])}"{" data-contar" if contar else ""} hidden>'
            f'{ICONO_OJO}<span class="vistas__n">0</span> <span class="vistas__txt">vistas</span></span>')


def ficha_documento(d, raiz, carga="lazy"):
    if d.get("portada"):
        dims = f' width="{d["portada"]["w"]}" height="{d["portada"]["h"]}"' if d["portada"]["w"] else ""
        tapa = f'<img src="{raiz}{d["portada"]["m"]}" alt="Portada: {esc(d["titulo"])}"{dims} loading="{carga}" decoding="async">'
    else:
        tapa = f'<span class="libro-tapa__vacia">{ICONO_PDF}<span>PDF</span></span>'
    return f"""<li class="ficha ficha--doc" data-fecha="{esc(d['fecha'])}" data-orden="{d.get('orden', 0)}">
  <a href="{raiz}{d['url']}">
    <span class="libro-tapa">{tapa}</span>
    <span class="ficha__cuerpo">
      <span class="ficha__meta">{esc(meta_documento(d))}</span>
      <span class="ficha__titulo">{esc(d['titulo'])}</span>
      {etiqueta_vistas(d, "ficha__vistas")}
    </span>
  </a>
</li>"""


def carrusel(items_html, etiqueta, idioma="es"):
    t = TEXTOS[idioma]
    return f"""<div class="carrusel" data-carrusel>
  <button class="carrusel__btn carrusel__btn--prev" type="button" aria-label="{t['anterior']}: {esc(etiqueta)}" data-dir="-1">‹</button>
  <ul class="carrusel__pista" aria-label="{esc(etiqueta)}">
{items_html}
  </ul>
  <button class="carrusel__btn carrusel__btn--next" type="button" aria-label="{t['siguiente']}: {esc(etiqueta)}" data-dir="1">›</button>
</div>"""


def carrusel_ejercicios(ejercicios, raiz, etiqueta, con_curso=False, primeros_visibles=0, idioma="es"):
    return carrusel("\n".join(ficha(e, raiz, con_curso, "eager" if i < primeros_visibles else "lazy", idioma)
                              for i, e in enumerate(ejercicios)), etiqueta, idioma)


def grilla(ejercicios, raiz, con_curso=True, idioma="es"):
    return '<ul class="fichas">' + "\n".join(ficha(e, raiz, con_curso, "lazy", idioma) for e in ejercicios) + "</ul>"


def grilla_documentos(documentos, raiz):
    return '<ul class="fichas fichas--docs">' + "\n".join(ficha_documento(d, raiz) for d in documentos) + "</ul>"


def parrafos(texto):
    salida = []
    for bloque in re.split(r"\n\s*\n", texto.strip()):
        linea = esc(" ".join(l.strip() for l in bloque.splitlines()))
        rotulo = next((r for r in ("Datos de la figura:", "Figure data:") if linea.startswith(r)), None)
        if linea.startswith("* "):
            salida.append(f'<p class="nota">{linea}</p>')
        elif rotulo:
            salida.append(f'<p class="datos"><strong>{rotulo}</strong>' + linea[len(rotulo):] + "</p>")
        else:
            salida.append(f"<p>{linea}</p>")
    return "\n".join(salida)


def figura(ej, campo, raiz, alt, carga="eager"):
    ancho, alto = ej[campo + "_medidas"]
    dims = f' width="{ancho}" height="{alto}"' if ancho else ""
    return (f'<img src="{raiz}{ej[campo + "_url"]}" alt="{esc(alt)}"{dims} '
            f'loading="{carga}" decoding="async">')


def asesoria(sitio, mensaje, idioma="es"):
    t = TEXTOS[idioma]
    return f"""<aside class="asesoria" aria-label="{t['asesoria']}">
  <p><strong>{t['necesitas']}</strong> <a href="{esc(enlace_whatsapp(sitio, mensaje))}" rel="noopener">WhatsApp {esc(sitio['whatsapp_visible'])}</a></p>
</aside>"""


def visor_libro(d, raiz):
    """Visor tipo revista: hojas que se pasan, miniaturas y pantalla completa."""
    if not d.get("paginas"):
        return f"""<object class="visor" data="{raiz}{d['pdf_url']}" type="application/pdf" aria-label="Vista previa de {esc(d['titulo'])}">
  <p>Tu navegador no muestra el PDF aquí. <a href="{raiz}{d['pdf_url']}">Ábrelo o descárgalo</a>.</p>
</object>"""
    datos = [{"i": raiz + p["i"], "w": p["w"], "h": p["h"]} for p in d["paginas"]]
    miniaturas = "".join(
        f'<button class="libro__mini" type="button" data-pagina="{i}" aria-label="Ir a la página {i + 1}">'
        f'<img src="{raiz}{p["m"]}" alt="" loading="lazy" decoding="async"><span>{i + 1}</span></button>'
        for i, p in enumerate(d["paginas"]))
    respaldo = "".join(
        f'<img src="{raiz}{p["i"]}" alt="{esc(d["titulo"])} – página {i + 1}" loading="lazy">'
        for i, p in enumerate(d["paginas"]))
    return f"""<div class="libro" data-libro tabindex="0" aria-label="Visor de {esc(d['titulo'])}">
  <div class="libro__escenario">
    <div class="libro__hojas" aria-live="polite"></div>
    <noscript><div class="libro__respaldo">{respaldo}</div></noscript>
  </div>
  <div class="libro__barra">
    <button class="libro__btn" type="button" data-ir="-1" aria-label="Página anterior">‹</button>
    <span class="libro__contador">1 / {len(datos)}</span>
    <button class="libro__btn" type="button" data-ir="1" aria-label="Página siguiente">›</button>
    <button class="libro__btn libro__btn--txt" type="button" data-pantalla>⛶ Pantalla completa</button>
    <a class="libro__btn libro__btn--txt" href="{raiz}{d['pdf_url']}" download>{ICONO_PDF}Descargar</a>
  </div>
  <div class="libro__miniaturas">{miniaturas}</div>
  <script type="application/json" class="libro__datos">{json_en_html(datos)}</script>
</div>"""


# ------------------------------------------------------------------- páginas

def pagina_ejercicio(sitio, ej, relacionados):
    raiz = "../../"
    uni_txt = f" ({ej['universidad']})" if ej["universidad"] else ""
    titulo = f"{ej['tema']} – {ej['curso']}{uni_txt} | {sitio['nombre']}"
    contexto = " de ".join(p for p in (ej["etiqueta"], ej["curso"]) if p)
    if ej["universidad"]:
        contexto += f", {ej['universidad']}"
    descripcion = ej["descripcion"] or recortar(f"{contexto}: {ej['enunciado'].split(chr(10) * 2)[0]}")
    alt = f"Enunciado y figura: {ej['tema']} – {meta_ejercicio(ej)}"
    mensaje = f"Hola Lindey, vi el ejercicio «{ej['tema']}» ({ej['curso']}) en la Biblioteca Lindey y quiero pedir mi solucionario."
    url_abs = f"{sitio['url']}/{ej['url']}"

    chips = [f'<a class="chip chip--curso" href="{raiz}{ej["curso_slug"]}/">{esc(ej["curso"])}</a>']
    if ej["universidad"]:
        nombre = ej["universidad_nombre"]
        etiqueta_uni = f"{ej['universidad']} · {nombre}" if nombre else ej["universidad"]
        chips.append(f'<a class="chip" href="{raiz}universidad/{ej["universidad_slug"]}/">{esc(etiqueta_uni)}</a>')
    for extra in (ej["evaluacion"], ej["etiqueta"]):
        if extra:
            chips.append(f'<span class="chip chip--suave">{esc(extra)}</span>')

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
  <div class="seccion__cabecera">
    <h2 id="t-mas">Más ejercicios de {esc(ej['curso'])}</h2>
    <a class="enlace-flecha" href="{raiz}{ej['curso_slug']}/">Ver todos</a>
  </div>
  {carrusel_ejercicios(relacionados, raiz, f"Más ejercicios de {ej['curso']}")}
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
      <p class="acciones">
        <a class="boton boton--suave" href="{raiz}{ej['imagen_url']}">Ver imagen completa</a>
      </p>
      {compartir(url_abs, f"Mira este ejercicio de {ej['curso']}: {ej['tema']}")}
    </section>
    <figure class="figura figura--principal">
      {figura(ej, "imagen", raiz, alt)}
      <figcaption>Figura del ejercicio · {esc(meta_ejercicio(ej))}</figcaption>
    </figure>
  </div>
  {solucion}
  {asesoria(sitio, mensaje)}
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
        "url": url_abs,
        "datePublished": ej["fecha"],
        "isAccessibleForFree": True,
        "isPartOf": {"@type": "Course", "name": ej["curso"], "url": f"{sitio['url']}/{ej['curso_slug']}/",
                     "provider": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario"}},
        "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario",
                      "sameAs": [sitio["facebook"]]},
    }
    if ej["universidad"]:
        recurso["audience"] = {"@type": "EducationalAudience", "educationalRole": "student",
                               "audienceType": ej["universidad_nombre"] or ej["universidad"]}
    ld = [recurso, migas_jsonld(sitio, [(ej["curso"], f"{ej['curso_slug']}/"), (ej["tema"], ej["url"])])]
    alternos = {"es": ej["url"], "en": ej["url_en"]} if ej["tiene_en"] else {"es": ej["url"]}
    return pagina(sitio, raiz=raiz, ruta=ej["url"], titulo=titulo, descripcion=descripcion,
                  contenido=contenido, imagen_social=imagen_abs, tipo_og="article", jsonld=ld,
                  mensaje_wa=mensaje, cuerpo_clase="pag-ejercicio", alternos=alternos)


def pagina_ejercicio_en(sitio, ej, relacionados):
    """Versión en inglés de la página del ejercicio."""
    raiz = "../../../"
    uni_txt = f" ({ej['universidad']})" if ej["universidad"] else ""
    titulo = f"{ej['tema_en']} – {ej['curso_en']} exercise{uni_txt} | {sitio['nombre_en']}"
    contexto = " – ".join(p for p in (ej["curso_en"], ej["universidad"], ej["etiqueta_en"]) if p)
    descripcion = recortar(f"{contexto}: {ej['enunciado_en'].split(chr(10) * 2)[0]}")
    alt = f"Problem statement and figure: {ej['tema_en']} – {meta_ejercicio(ej, True, 'en')}"
    mensaje = f"Hi Lindey, I saw the exercise «{ej['tema_en']}» ({ej['curso_en']}) on the Lindey Library and I'd like to get the solution."
    url_abs = f"{sitio['url']}/{ej['url_en']}"
    curso_url = f"{raiz}en/{ej['curso_en_slug']}/"

    chips = [f'<a class="chip chip--curso" href="{curso_url}">{esc(ej["curso_en"])}</a>']
    if ej["universidad"]:
        nombre = ej["universidad_nombre"]
        chips.append(f'<span class="chip">{esc(ej["universidad"] + (" · " + nombre if nombre else ""))}</span>')
    for extra in (ej["evaluacion_en"], ej["etiqueta_en"]):
        if extra:
            chips.append(f'<span class="chip chip--suave">{esc(extra)}</span>')
    palabras = ""
    if ej["palabras_en"]:
        palabras = '<p class="palabras"><span>Concepts:</span> ' + ", ".join(esc(p) for p in ej["palabras_en"]) + "</p>"
    solucion = ""
    if ej.get("solucion_imagen"):
        solucion = f"""<section class="bloque solucion" aria-labelledby="t-solucion">
  <h2 id="t-solucion">Step-by-step solution</h2>
  <figure class="figura">{figura(ej, "solucion_imagen", raiz, "Step-by-step solution: " + ej["tema_en"], "lazy")}</figure>
</section>"""
    mas = ""
    if relacionados:
        mas = f"""<section class="bloque" aria-labelledby="t-mas">
  <div class="seccion__cabecera">
    <h2 id="t-mas">More {esc(ej['curso_en'])} exercises</h2>
    <a class="enlace-flecha" href="{curso_url}">See all</a>
  </div>
  {carrusel_ejercicios(relacionados, raiz, f"More {ej['curso_en']} exercises", idioma="en")}
</section>"""
    contenido = f"""<div class="envoltura">
{migas(raiz, [(ej['curso_en'], curso_url), (ej['tema_en'], None)], "en")}
<article class="ejercicio">
  <header class="ejercicio__cabecera">
    <p class="antetitulo">{esc(meta_ejercicio(ej, True, 'en'))}</p>
    <h1>{esc(ej['tema_en'])}</h1>
    <div class="chips">{"".join(chips)}</div>
  </header>
  <div class="ejercicio__cuerpo">
    <section class="enunciado" aria-labelledby="t-enunciado">
      <h2 id="t-enunciado">Problem statement</h2>
      {parrafos(ej['enunciado_en'])}
      {palabras}
      <p class="acciones">
        <a class="boton boton--suave" href="{raiz}{ej['imagen_url']}">View full image</a>
        <a class="boton boton--suave" href="{raiz}{ej['url']}" hreflang="es" lang="es">Ver en español</a>
      </p>
      {compartir(url_abs, f"Check out this {ej['curso_en']} exercise: {ej['tema_en']}", "en")}
    </section>
    <figure class="figura figura--principal">
      {figura(ej, "imagen", raiz, alt)}
      <figcaption>Exercise figure · {esc(meta_ejercicio(ej, True, 'en'))}</figcaption>
    </figure>
  </div>
  {solucion}
  {asesoria(sitio, mensaje, "en")}
</article>
{mas}
</div>"""
    recurso = {
        "@context": "https://schema.org", "@type": "LearningResource", "name": ej["tema_en"],
        "headline": f"{ej['tema_en']} – {ej['curso_en']}", "description": descripcion, "text": ej["enunciado_en"],
        "inLanguage": "en", "learningResourceType": "Exercise", "educationalLevel": "University",
        "teaches": ej["tema_en"], "about": [ej["curso_en"], ej["tema_en"]] + ej["palabras_en"],
        "keywords": ", ".join([ej["curso_en"], ej["tema_en"]] + ej["palabras_en"]),
        "image": f"{sitio['url']}/{ej['imagen_url']}", "url": url_abs, "datePublished": ej["fecha"],
        "isAccessibleForFree": True, "translationOfWork": {"@id": f"{sitio['url']}/{ej['url']}"},
        "isPartOf": {"@type": "Course", "name": ej["curso_en"], "url": f"{sitio['url']}/en/{ej['curso_en_slug']}/"},
        "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario", "sameAs": [sitio["facebook"]]},
    }
    ld = [recurso, migas_jsonld(sitio, [(ej["curso_en"], f"en/{ej['curso_en_slug']}/"), (ej["tema_en"], ej["url_en"])], "en")]
    return pagina(sitio, raiz=raiz, ruta=ej["url_en"], titulo=titulo, descripcion=descripcion,
                  contenido=contenido, imagen_social=f"{sitio['url']}/{ej['imagen_url']}", tipo_og="article",
                  jsonld=ld, mensaje_wa=mensaje, cuerpo_clase="pag-ejercicio", idioma="en",
                  alternos={"es": ej["url"], "en": ej["url_en"]})


def pagina_curso_en(sitio, curso, ejercicios):
    raiz = "../../"
    curso_en = sitio["cursos_en"].get(curso, curso)
    slug_en = slugify(curso_en)
    descripcion = recortar(f"{len(ejercicios)} university {curso_en} exercises with full problem statement and figure: "
                           + ", ".join(e["tema_en"].lower() for e in ejercicios[:6]) + ".")
    contenido = f"""<div class="envoltura">
{migas(raiz, [(curso_en, None)], "en")}
<header class="encabezado">
  <p class="antetitulo">Course</p>
  <h1>{esc(curso_en)} exercises</h1>
  <p class="bajada">{len(ejercicios)} {"exercise" if len(ejercicios) == 1 else "exercises"} with full problem statement and figure. Tap an exercise to open it.</p>
</header>
{grilla(ejercicios, raiz, con_curso=False, idioma="en")}
</div>"""
    ld = [migas_jsonld(sitio, [(curso_en, f"en/{slug_en}/")], "en"),
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"{curso_en} exercises",
           "url": f"{sitio['url']}/en/{slug_en}/", "inLanguage": "en", "description": descripcion}]
    return pagina(sitio, raiz=raiz, ruta=f"en/{slug_en}/", titulo=f"{curso_en} exercises with problem statement and figure | {sitio['nombre_en']}",
                  descripcion=descripcion, contenido=contenido, jsonld=ld, idioma="en",
                  alternos={"es": f"{slugify(curso)}/", "en": f"en/{slug_en}/"})


def pagina_portada_en(sitio, ejercicios, cursos):
    raiz = "../"
    secciones = []
    for i, curso in enumerate(cursos):
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        if not del_curso:
            continue
        curso_en = sitio["cursos_en"].get(curso, curso)
        slug_en = slugify(curso_en)
        secciones.append(f"""<section class="seccion-curso" aria-labelledby="c-{slug_en}">
  <div class="seccion__cabecera">
    <h2 id="c-{slug_en}"><a href="{slug_en}/">{esc(curso_en)}</a> <span class="contador">{len(del_curso)}</span></h2>
    <a class="enlace-flecha" href="{slug_en}/">See all</a>
  </div>
  {carrusel("".join(ficha(e, raiz, False, "eager" if i < 2 and k < 4 else "lazy", "en") for k, e in enumerate(del_curso)).replace(f'href="{raiz}en/', 'href="'), f"{curso_en} exercises", "en")}
</section>""")
    contenido = f"""<section class="portada">
  <div class="envoltura">
    <h1>{esc(sitio['nombre_en'])}</h1>
    <p class="portada__bajada">University engineering exercises with full problem statement and figure — free to browse. Search by topic or course, or paste part of the problem statement.</p>
    <form class="buscador" id="buscar" role="search" action="./" method="get" data-indice="buscar-en.json">
      <label class="oculto" for="q">Search exercises</label>
      <input id="q" name="q" type="search" autocomplete="off" placeholder="E.g.: combined footing, buckling, conjugate beam…">
      <button type="submit">Search</button>
    </form>
    <p class="portada__cifras">{len(ejercicios)} exercises · {len(secciones)} courses · <a href="../">Versión en español</a></p>
  </div>
</section>
<div class="envoltura">
  <section class="resultados" id="resultados" aria-live="polite" hidden></section>
  <div id="cursos">
    {"".join(secciones)}
  </div>
</div>"""
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": sitio["nombre_en"], "url": sitio["url"] + "/en/",
           "inLanguage": "en", "description": sitio["descripcion_en"],
           "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario",
                         "sameAs": [sitio["facebook"]], "logo": f"{sitio['url']}/logo-lindey.png"}}]
    return pagina(sitio, raiz=raiz, ruta="en/", titulo=f"{sitio['nombre_en']} – University engineering exercises",
                  descripcion=sitio["descripcion_en"], contenido=contenido, jsonld=ld, cuerpo_clase="pag-portada",
                  idioma="en", alternos={"es": "", "en": "en/"})


def pagina_curso(sitio, curso, ejercicios, documentos):
    raiz = "../"
    slug = slugify(curso)
    unis = sorted({e["universidad"] for e in ejercicios if e["universidad"]})
    uni_txt = f" de {', '.join(unis)}" if unis else ""
    titulo = f"Ejercicios de {curso} con enunciado y figura | {sitio['nombre']}"
    descripcion = recortar(
        f"{len(ejercicios)} ejercicios universitarios de {curso}{uni_txt} con enunciado completo en texto y figura: "
        + ", ".join(e["tema"].lower() for e in ejercicios[:6]) + ".")
    docs = ""
    if documentos:
        docs = f'<section class="bloque"><h2>PDFs de {esc(curso)}</h2>{grilla_documentos(documentos, raiz)}</section>'
    contenido = f"""<div class="envoltura">
{migas(raiz, [(curso, None)])}
<header class="encabezado">
  <p class="antetitulo">Curso</p>
  <h1>Ejercicios de {esc(curso)}</h1>
  <p class="bajada">{len(ejercicios)} {"ejercicio" if len(ejercicios) == 1 else "ejercicios"} con enunciado completo y figura. Toca un ejercicio para verlo.</p>
</header>
{grilla(ejercicios, raiz, con_curso=False)}
{docs}
</div>"""
    ld = [migas_jsonld(sitio, [(curso, f"{slug}/")]),
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": f"Ejercicios de {curso}",
           "url": f"{sitio['url']}/{slug}/", "inLanguage": "es", "description": descripcion}]
    alternos = {"es": f"{slug}/"}
    if any(e["tiene_en"] for e in ejercicios):
        alternos["en"] = f"en/{slugify(sitio['cursos_en'].get(curso, curso))}/"
    return pagina(sitio, raiz=raiz, ruta=f"{slug}/", titulo=titulo, descripcion=descripcion,
                  contenido=contenido, jsonld=ld, alternos=alternos)


def pagina_universidad(sitio, sigla, ejercicios, documentos=()):
    raiz = "../../"
    slug = slugify(sigla)
    nombre = sitio["universidades"].get(sigla, "")
    de = "del" if nombre.lower().startswith(("instituto", "centro")) else "de la"
    que = " y ".join(p for p in ("ejercicios" if ejercicios else "", "PDFs" if documentos else "") if p) or "ejercicios"
    que = que[0].upper() + que[1:]
    titulo = f"{que} {de} {sigla}{' – ' + nombre if nombre else ''} | {sitio['nombre']}"
    cursos = sorted({e["curso"] for e in ejercicios} | {d["curso"] for d in documentos}, key=lambda c: orden_curso(sitio, c))
    tipos = sorted({d["tipo"].lower() for d in documentos})
    descripcion = recortar(
        f"{que} {de} {sigla}{f' ({nombre})' if nombre else ''}: {', '.join(cursos)}. "
        + ("Enunciado completo y figura. " if ejercicios else "")
        + (f"PDFs de {', '.join(tipos)} para leer en línea o descargar." if documentos else ""))
    grupos = []
    for curso in cursos:
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        docs = [d for d in documentos if d["curso"] == curso]
        cuerpo = (grilla(del_curso, raiz, con_curso=False) if del_curso else "") + (grilla_documentos(docs, raiz) if docs else "")
        grupos.append(f'<section class="bloque"><h2>{esc(curso)}</h2>{cuerpo}</section>')
    cifras = " · ".join(p for p in (
        f"{len(ejercicios)} {'ejercicio' if len(ejercicios) == 1 else 'ejercicios'}" if ejercicios else "",
        f"{len(documentos)} {'PDF' if len(documentos) == 1 else 'PDFs'}" if documentos else "") if p)
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Universidades", f"{raiz}#universidades"), (sigla, None)])}
<header class="encabezado">
  <p class="antetitulo">Universidad · {esc(cifras)}</p>
  <h1>{esc(que)} {de} {esc(sigla)}</h1>
  {f'<p class="bajada">{esc(nombre)}</p>' if nombre else ''}
</header>
{"".join(grupos)}
</div>"""
    return pagina(sitio, raiz=raiz, ruta=f"universidad/{slug}/", titulo=titulo, descripcion=descripcion,
                  contenido=contenido, jsonld=[migas_jsonld(sitio, [(sigla, f"universidad/{slug}/")])])


def pagina_indice(sitio, ejercicios, cursos):
    raiz = "../"
    bloques = []
    for curso in cursos:
        items = "".join(
            f'<li><a href="{raiz}{e["url"]}">{esc(e["tema"])}</a> <span>{esc(meta_ejercicio(e, False))}</span></li>'
            for e in ejercicios if e["curso"] == curso)
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


def pagina_repositorio(sitio, ejercicios, documentos, cursos):
    raiz = "../"
    propios = [d for d in documentos if not d["auto"]]
    secciones = []
    if propios:
        cursos_docs = sorted({d["curso"] for d in propios}, key=lambda c: orden_curso(sitio, c))
        grupos = "".join(
            f'<h3 id="{slugify(c)}">{esc(c)}</h3>{grilla_documentos([d for d in propios if d["curso"] == c], raiz)}'
            for c in cursos_docs)
        orden = """<div class="ordenar" data-ordenar hidden>
    <span>Ordenar:</span>
    <button type="button" data-orden="curso" aria-pressed="true">Por curso</button>
    <button type="button" data-orden="vistas" aria-pressed="false">Más vistos</button>
    <button type="button" data-orden="fecha" aria-pressed="false">Más recientes</button>
  </div>"""
        secciones.append(f"""<section class="bloque" id="documentos">
  <div class="seccion__cabecera"><h2>Documentos <span class="contador">{len(propios)}</span></h2>{orden}</div>
  <div class="documentos__grupos">{grupos}</div>
  <ul class="fichas fichas--docs documentos__plano" hidden></ul>
</section>""")
    if not propios:
        secciones.append('<p class="bajada">Pronto habrá documentos aquí.</p>')
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Repositorio de PDFs", None)])}
<header class="encabezado">
  <p class="antetitulo">Repositorio</p>
  <h1>Repositorio de PDFs</h1>
  <p class="bajada">Documentos para leer en línea como una revista o descargar gratis, con todo su contenido transcrito. Ordenados por curso.</p>
</header>
{"".join(secciones)}
</div>"""
    return pagina(sitio, raiz=raiz, ruta="pdfs/", titulo=f"Repositorio de PDFs de ingeniería | {sitio['nombre']}",
                  descripcion=recortar("Lee en línea como una revista o descarga en PDF exámenes, tareas y prácticas universitarias de "
                                       + ", ".join(sorted({d["curso"] for d in propios}) or cursos) + ", con su contenido transcrito."),
                  contenido=contenido, jsonld=[migas_jsonld(sitio, [("Repositorio de PDFs", "pdfs/")])])


def pagina_documento(sitio, d, cursos_con_pagina=()):
    raiz = "../../"
    mensaje = f"Hola Lindey, vi el PDF «{d['titulo']}» en la Biblioteca Lindey y quiero pedir mi solucionario."
    url_abs = f"{sitio['url']}/{d['url']}"
    # Los cursos que solo tienen PDFs (sin ejercicios) no tienen página propia: se enlaza su grupo en /pdfs/
    destino_curso = f"{raiz}{d['curso_slug']}/" if d["curso"] in cursos_con_pagina else f"{raiz}pdfs/#{d['curso_slug']}"
    chips = [f'<a class="chip chip--curso" href="{destino_curso}">{esc(d["curso"])}</a>']
    if d["universidad"]:
        etiqueta_uni = f"{d['universidad']} · {d['universidad_nombre']}" if d["universidad_nombre"] else d["universidad"]
        chips.append(f'<a class="chip" href="{raiz}universidad/{slugify(d["universidad"])}/">{esc(etiqueta_uni)}</a>')
    for extra in (d["tipo"], f"{d['n_paginas']} páginas" if d.get("n_paginas") else ""):
        if extra:
            chips.append(f'<span class="chip chip--suave">{esc(extra)}</span>')
    chips.append(etiqueta_vistas(d, "chip chip--vistas", contar=True))
    transcripcion = (d["contenido_html"] or
                     "<p>La transcripción de este documento estará disponible pronto.</p>")
    contenido = f"""<div class="envoltura">
{migas(raiz, [("PDFs", f"{raiz}pdfs/"), (d['titulo'], None)])}
<article class="documento">
  <header class="ejercicio__cabecera">
    <p class="antetitulo">{esc(d['tipo'])} · {esc(d['curso'])}</p>
    <h1>{esc(d['titulo'])}</h1>
    <div class="chips">{"".join(chips)}</div>
  </header>
  {visor_libro(d, raiz)}
  <div class="documento__acciones">
    <a class="boton boton--pdf" href="{raiz}{d['pdf_url']}" download>{ICONO_PDF}Descargar PDF ({tamano_legible(d['bytes'])})</a>
    {compartir(url_abs, f"Mira este PDF de {d['curso']}: {d['titulo']}")}
  </div>
  <section class="enunciado transcripcion" aria-labelledby="t-contenido">
    <h2 id="t-contenido">Contenido del documento</h2>
    {transcripcion}
  </section>
  {asesoria(sitio, mensaje)}
</article>
</div>"""
    imagen_social = f"{sitio['url']}/{d['portada']['i']}" if d.get("portada") else None
    ld = [migas_jsonld(sitio, [("PDFs", "pdfs/"), (d["titulo"], d["url"])]),
          {"@context": "https://schema.org", "@type": "DigitalDocument", "name": d["titulo"], "description": d["descripcion"],
           "inLanguage": "es", "encodingFormat": "application/pdf", "url": f"{sitio['url']}/{d['pdf_url']}",
           "about": d["curso"], "datePublished": d["fecha"], "isAccessibleForFree": True,
           "text": recortar(d.get("texto_plano", ""), 5000), **({"image": imagen_social} if imagen_social else {})}]
    return pagina(sitio, raiz=raiz, ruta=d["url"], titulo=f"{d['titulo']} (PDF) – {d['curso']} | {sitio['nombre']}",
                  descripcion=d["descripcion"], contenido=contenido, jsonld=ld, mensaje_wa=mensaje,
                  imagen_social=imagen_social, tipo_og="article")


def pagina_portada(sitio, ejercicios, documentos, cursos, universidades):
    raiz = ""
    secciones_curso = []
    for i, curso in enumerate(cursos):
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        n = len(del_curso)
        secciones_curso.append(f"""<section class="seccion-curso" aria-labelledby="c-{slugify(curso)}">
  <div class="seccion__cabecera">
    <h2 id="c-{slugify(curso)}"><a href="{slugify(curso)}/">{esc(curso)}</a> <span class="contador">{n}</span></h2>
    <a class="enlace-flecha" href="{slugify(curso)}/">Ver todos</a>
  </div>
  {carrusel_ejercicios(del_curso, raiz, f"Ejercicios de {curso}", primeros_visibles=4 if i < 2 else 0)}
</section>""")
    chips_uni = []
    for sigla in universidades:
        n = (sum(1 for e in ejercicios if e["universidad"] == sigla)
             + sum(1 for d in documentos if d["universidad"] == sigla))
        nombre = sitio["universidades"].get(sigla, "")
        chips_uni.append(
            f'<li><a class="uni" href="universidad/{slugify(sigla)}/"><strong>{esc(sigla)}</strong>'
            f'{f"<span>{esc(nombre)}</span>" if nombre else ""}<em>{n}</em></a></li>')
    # Solo los PDF subidos por Lindey (los ejercicios se publican como imagen + texto)
    propios = [d for d in documentos if not d["auto"]]
    seccion_docs = ""
    if propios:
        seccion_docs = f"""<section class="seccion-curso" aria-labelledby="c-pdfs">
  <div class="seccion__cabecera">
    <h2 id="c-pdfs"><a href="pdfs/">PDFs para leer y descargar</a> <span class="contador">{len(propios)}</span></h2>
    <a class="enlace-flecha" href="pdfs/">Ver repositorio</a>
  </div>
  {carrusel("".join(ficha_documento(d, raiz) for d in propios), "PDFs para leer y descargar")}
</section>"""

    contenido = f"""<section class="portada">
  <div class="envoltura">
    <h1>Biblioteca Lindey</h1>
    <p class="portada__bajada">Ejercicios universitarios de ingeniería con su enunciado completo y figura, de libre consulta. También PDFs para leer y descargar. Busca por tema, curso, universidad o pega parte del enunciado.</p>
    <form class="buscador" id="buscar" role="search" action="./" method="get">
      <label class="oculto" for="q">Buscar ejercicio</label>
      <input id="q" name="q" type="search" autocomplete="off" placeholder="Ej.: zapata combinada, pandeo, viga conjugada…">
      <button type="submit">Buscar</button>
    </form>
    <p class="portada__cifras">{len(ejercicios)} ejercicios · {len(cursos)} cursos · {len(propios)} documentos PDF</p>
    {franja_paises(sitio)}
  </div>
</section>
<div class="envoltura">
  <section class="resultados" id="resultados" aria-live="polite" hidden></section>
  <div id="cursos">
    {"".join(secciones_curso)}
  </div>
  {seccion_docs}
  <section class="bloque" id="universidades" aria-labelledby="t-unis">
    <h2 id="t-unis">Universidades</h2>
    <ul class="unis">{"".join(chips_uni)}</ul>
  </section>
</div>"""
    ld = [{
        "@context": "https://schema.org", "@type": "WebSite", "name": sitio["nombre"], "url": sitio["url"] + "/",
        "inLanguage": "es", "description": sitio["descripcion"],
        "publisher": {"@type": "Organization", "name": "Lindey Asesoramiento Universitario",
                      "sameAs": [sitio["facebook"]], "logo": f"{sitio['url']}/logo-lindey.png"},
    }]
    return pagina(sitio, raiz=raiz, ruta="", titulo=f"{sitio['nombre']} – Ejercicios universitarios de ingeniería",
                  descripcion=sitio["descripcion"], contenido=contenido, jsonld=ld, cuerpo_clase="pag-portada",
                  alternos={"es": "", "en": "en/"})


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

def indice_busqueda(ejercicios, documentos):
    filas = [{
        "t": e["tema"], "c": e["curso"], "u": e["universidad"], "un": e["universidad_nombre"],
        "v": e["evaluacion"], "e": e["etiqueta"], "k": ", ".join(e["palabras"]),
        "d": e["enunciado"], "url": e["url"], "m": e["mini_url"],
        "mw": e["mini_medidas"][0], "mh": e["mini_medidas"][1],
    } for e in ejercicios]
    filas += [{
        "t": d["titulo"], "c": d["curso"], "u": d["universidad"], "un": d["universidad_nombre"],
        "v": d["tipo"], "e": "PDF", "k": ", ".join(d["palabras"]), "d": recortar(d.get("texto_plano", ""), 6000),
        "url": d["url"], "m": d["portada"]["m"] if d.get("portada") else "",
        "mw": d["portada"]["w"] if d.get("portada") else 0, "mh": d["portada"]["h"] if d.get("portada") else 0,
    } for d in documentos]
    return json.dumps(filas, ensure_ascii=False, separators=(",", ":"))


def indice_busqueda_en(ejercicios):
    return json.dumps([{
        "t": e["tema_en"], "c": e["curso_en"], "u": e["universidad"], "un": e["universidad_nombre"],
        "v": e["evaluacion_en"], "e": e["etiqueta_en"], "k": ", ".join(e["palabras_en"]),
        "d": e["enunciado_en"], "url": e["url_en"], "m": e["mini_url"],
        "mw": e["mini_medidas"][0], "mh": e["mini_medidas"][1],
    } for e in ejercicios if e["tiene_en"]], ensure_ascii=False, separators=(",", ":"))


def sitemap(sitio, ejercicios, documentos, cursos, universidades):
    u = sitio["url"]
    hoy = max([e["fecha"] for e in ejercicios] + [d["fecha"] for d in documentos] or [date.today().isoformat()])
    # (dirección, fecha, imágenes, {idioma: dirección alternativa})
    filas = [(f"{u}/", hoy, None, {"es": f"{u}/", "en": f"{u}/en/"}),
             (f"{u}/en/", hoy, None, {"es": f"{u}/", "en": f"{u}/en/"}),
             (f"{u}/ejercicios/", hoy, None, None), (f"{u}/pdfs/", hoy, None, None)]
    for curso in cursos:
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        fecha = max(e["fecha"] for e in del_curso)
        alt = None
        if any(e["tiene_en"] for e in del_curso):
            alt = {"es": f"{u}/{slugify(curso)}/", "en": f"{u}/en/{slugify(sitio['cursos_en'].get(curso, curso))}/"}
            filas.append((alt["en"], fecha, None, alt))
        filas.append((f"{u}/{slugify(curso)}/", fecha, None, alt))
    for sigla in universidades:
        fecha = max([e["fecha"] for e in ejercicios if e["universidad"] == sigla]
                    + [d["fecha"] for d in documentos if d["universidad"] == sigla])
        filas.append((f"{u}/universidad/{slugify(sigla)}/", fecha, None, None))
    for e in ejercicios:
        imagenes = [f"{u}/{e['imagen_url']}"]
        if e.get("solucion_imagen_url"):
            imagenes.append(f"{u}/{e['solucion_imagen_url']}")
        alt = {"es": f"{u}/{e['url']}", "en": f"{u}/{e['url_en']}"} if e["tiene_en"] else None
        filas.append((f"{u}/{e['url']}", e["fecha"], imagenes, alt))
        if alt:
            filas.append((alt["en"], e["fecha"], imagenes, alt))
    for d in documentos:
        imagenes = [f"{u}/{p['i']}" for p in d.get("paginas", [])[:50]]
        filas.append((f"{u}/{d['url']}", d["fecha"], imagenes, None))
        filas.append((f"{u}/{d['pdf_url']}", d["fecha"], None, None))
    partes = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
              'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1" '
              'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for loc, fecha, imagenes, alt in filas:
        enlaces = "".join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{esc(h)}"/>' for l, h in (alt or {}).items())
        imgs = "".join(f"<image:image><image:loc>{esc(i)}</image:loc></image:image>" for i in imagenes or [])
        partes.append(f"<url><loc>{esc(loc)}</loc><lastmod>{fecha}</lastmod>{enlaces}{imgs}</url>")
    partes.append("</urlset>\n")
    return "\n".join(partes)


# ------------------------------------------------------------------- principal

def main():
    sitio = cargar_sitio()
    ejercicios = sorted(cargar(CARPETA_EJERCICIOS, leer_ejercicio, sitio), key=orden_ejercicio(sitio))
    propios = sorted(cargar(CARPETA_PDFS, leer_documento, sitio),
                     key=lambda d: (orden_curso(sitio, d["curso"]), d["orden"], d["titulo"]))
    cursos = sorted({e["curso"] for e in ejercicios}, key=lambda c: orden_curso(sitio, c))
    universidades = sorted({e["universidad"] for e in ejercicios if e["universidad"]}
                           | {d["universidad"] for d in propios if d["universidad"]})
    sitio["pie_datos"] = {
        "cursos": cursos,
        "cursos_en": [c for c in cursos if any(e["tiene_en"] for e in ejercicios if e["curso"] == c)],
        "cursos_pdf": sorted({d["curso"] for d in propios} - set(cursos), key=lambda c: orden_curso(sitio, c)),
        "universidades": universidades,
    }

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
        crear_miniatura(e)

    documentos = propios  # solo los PDF que se suben a pdfs/
    for d in documentos:
        preparar_documento(sitio, d)

    for e in ejercicios:
        relacionados = [o for o in ejercicios if o["curso"] == e["curso"] and o is not e]
        escribir(f"{e['url']}index.html", pagina_ejercicio(sitio, e, relacionados))
    for curso in cursos:
        escribir(f"{slugify(curso)}/index.html",
                 pagina_curso(sitio, curso, [e for e in ejercicios if e["curso"] == curso],
                              [d for d in documentos if d["curso"] == curso]))
    for sigla in universidades:
        escribir(f"universidad/{slugify(sigla)}/index.html",
                 pagina_universidad(sitio, sigla, [e for e in ejercicios if e["universidad"] == sigla],
                                    [d for d in documentos if d["universidad"] == sigla]))
    for d in documentos:
        escribir(f"{d['url']}index.html", pagina_documento(sitio, d, cursos))
    con_en = [e for e in ejercicios if e["tiene_en"]]
    for e in con_en:
        relacionados = [o for o in con_en if o["curso"] == e["curso"] and o is not e]
        escribir(f"{e['url_en']}index.html", pagina_ejercicio_en(sitio, e, relacionados))
    for curso in cursos:
        del_curso = [e for e in con_en if e["curso"] == curso]
        if del_curso:
            escribir(f"en/{slugify(sitio['cursos_en'].get(curso, curso))}/index.html", pagina_curso_en(sitio, curso, del_curso))
    escribir("en/index.html", pagina_portada_en(sitio, con_en, cursos))
    escribir("buscar-en.json", indice_busqueda_en(ejercicios))
    escribir("pdfs/index.html", pagina_repositorio(sitio, ejercicios, documentos, cursos))
    escribir("ejercicios/index.html", pagina_indice(sitio, ejercicios, cursos))
    escribir("index.html", pagina_portada(sitio, ejercicios, documentos, cursos, universidades))
    escribir("404.html", pagina_404(sitio))
    escribir("buscar.json", indice_busqueda(ejercicios, documentos))
    escribir("sitemap.xml", sitemap(sitio, ejercicios, documentos, cursos, universidades))
    escribir("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {sitio['url']}/sitemap.xml\n")
    escribir(".nojekyll", "")
    if "github.io" not in sitio["dominio"]:  # dominio propio (p. ej. solucionariouni.com)
        escribir("CNAME", sitio["dominio"].split("/")[0] + "\n")

    sin_paginas = [d["titulo"] for d in documentos if not d.get("paginas")]
    con_marca = sum(1 for d in propios if d.get("con_marca"))
    if propios:
        print(f"Marca de agua: {con_marca} de {len(propios)} documentos propios")
    sin_ingles = [e["archivo"] for e in ejercicios if not e["tiene_en"]]
    if sin_ingles:
        print("Aviso: sin versión en inglés (faltan tema_en o [en]): " + ", ".join(sin_ingles))
    print(f"Listo: {len(ejercicios)} ejercicios ({len(con_en)} en inglés), {len(propios)} documentos propios, {len(cursos)} cursos, "
          f"{len(universidades)} universidades{'' if Image else ' (sin miniaturas: instala Pillow)'} → _site/")
    if sin_paginas:
        print("Aviso: sin vista de páginas (instala Poppler o PyMuPDF): " + ", ".join(sin_paginas))
    print(f"URL pública: {sitio['url']}/")


if __name__ == "__main__":
    main()
