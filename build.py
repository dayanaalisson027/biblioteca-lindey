#!/usr/bin/env python3
"""Genera la Biblioteca Lindey como sitio estático en la carpeta _site/.

Uso:
    python build.py

Lee:
    sitio.json          configuración general (nombre, URL, WhatsApp, universidades)
    ejercicios/*.md     un archivo por ejercicio (los que empiezan con "_" se ignoran)
    imagenes/           imágenes modo Lindey referenciadas por cada ejercicio
    pdfs/*.md + *.pdf   documentos PDF propios (un .md por PDF)
    estaticos/          estilos, buscador, logo e imagen para redes

Genera además un PDF por ejercicio (enunciado + imagen) en pdfs/ejercicios/.

Variable opcional:
    SITE_URL=https://www.midominio.com python build.py

Funciona solo con Python 3.8+. Si Pillow está instalado (pip install Pillow)
crea miniaturas livianas para los carruseles; si no, usa la imagen original.
"""

import html
import json
import os
import re
import shutil
import struct
import sys
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
    datos, enunciado = leer_markdown(ruta)
    faltan = [c for c in CAMPOS_EJERCICIO if not datos.get(c)]
    if faltan:
        raise ValueError("faltan campos: " + ", ".join(faltan))
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
    ej["pdf_url"] = f"pdfs/ejercicios/{slug}.pdf"
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


def leer_documento(ruta, sitio):
    datos, descripcion = leer_markdown(ruta)
    faltan = [c for c in CAMPOS_DOCUMENTO if not datos.get(c)]
    if faltan:
        raise ValueError("faltan campos: " + ", ".join(faltan))
    origen = CARPETA_PDFS / datos["archivo"]
    if not origen.exists():
        raise ValueError(f"no encuentro el archivo pdfs/{datos['archivo']}")
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
        "descripcion": descripcion,
        "origen": origen,
        "bytes": origen.stat().st_size,
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
        if el["url"] in vistos:
            errores.append(f"  - {carpeta.name}/{el['archivo']}: misma dirección que {vistos[el['url']]}")
        vistos[el["url"]] = el["archivo"]
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
    "gris": "0.290 0.353 0.471", "fondo_cta": "0.945 0.988 0.918",
}


def pdf_plano(texto):
    return "".join(SUSTITUCIONES_PDF.get(c, c) for c in texto)


def pdf_cadena(texto):
    datos = pdf_plano(texto).encode("cp1252", "replace")
    return b"(" + datos.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def pdf_info_cadena(texto):
    return b"<FEFF" + texto.encode("utf-16-be").hex().upper().encode() + b">"


def ancho_pdf(texto, tam, negrita=False):
    total = 0
    for c in pdf_plano(texto):
        base = unicodedata.normalize("NFKD", c)[:1] or c
        total += ANCHOS_HELVETICA.get(base, 556)
    return total * tam / 1000 * (1.07 if negrita else 1)


def envolver_pdf(texto, tam, ancho_max, negrita=False):
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if not actual or ancho_pdf(prueba, tam, negrita) <= ancho_max:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas


def bytes_jpeg(ej):
    """Devuelve (bytes, ancho, alto, espacio_color) de la imagen para incrustar, o None."""
    ancho, alto, comp, es_jpeg = ej["imagen_info"]
    if es_jpeg and ancho and comp in (1, 3):
        return ej["imagen_origen"].read_bytes(), ancho, alto, "/DeviceGray" if comp == 1 else "/DeviceRGB"
    if Image is not None:
        import io
        with Image.open(ej["imagen_origen"]) as im:
            im = im.convert("RGB")
            salida = io.BytesIO()
            im.save(salida, "JPEG", quality=88)
            return salida.getvalue(), im.width, im.height, "/DeviceRGB"
    return None


def pdf_ejercicio(sitio, ej):
    """PDF A4 con encabezado Lindey, enunciado en texto, imagen y enlace a WhatsApp."""
    ANCHO_P, ALTO_P, M = 595.0, 842.0, 48.0
    ANCHO_UTIL = ANCHO_P - 2 * M
    wa = enlace_whatsapp(sitio, f"Hola Lindey, vi el ejercicio «{ej['tema']}» ({ej['curso']}) en la Biblioteca Lindey y necesito asesoría.")
    url_pagina = f"{sitio['url']}/{ej['url']}"
    paginas = []  # cada una: {"ops": [bytes], "links": [(x1, y1, x2, y2, uri)], "imagen": bool}

    def nueva_pagina():
        p = {"ops": [], "links": [], "imagen": False}
        ops = p["ops"]
        ops.append(f"{COLORES['marino']} rg 0 {ALTO_P - 64} {ANCHO_P} 64 re f".encode())
        ops.append(b"BT /F2 14 Tf " + COLORES["lima"].encode() + f" rg {M} {ALTO_P - 34} Td ".encode()
                   + pdf_cadena("BIBLIOTECA LINDEY") + b" Tj ET")
        ops.append(b"BT /F1 8.5 Tf " + COLORES["celeste"].encode() + f" rg {M} {ALTO_P - 48} Td ".encode()
                   + pdf_cadena("Lindey Asesoramiento Universitario") + b" Tj ET")
        etiqueta = f"WhatsApp {sitio['whatsapp_visible']}"
        x = ANCHO_P - M - ancho_pdf(etiqueta, 11, True)
        ops.append(b"BT /F2 11 Tf " + COLORES["lima"].encode() + f" rg {x:.2f} {ALTO_P - 38} Td ".encode()
                   + pdf_cadena(etiqueta) + b" Tj ET")
        p["links"].append((x - 4, ALTO_P - 46, ANCHO_P - M + 4, ALTO_P - 26, wa))
        pie = f"Biblioteca Lindey · {url_pagina}"
        ops.append(b"BT /F1 8 Tf " + COLORES["gris"].encode() + f" rg {M} 28 Td ".encode() + pdf_cadena(pie) + b" Tj ET")
        p["links"].append((M, 24, M + ancho_pdf(pie, 8), 36, url_pagina))
        paginas.append(p)
        return p

    def linea_texto(p, y, texto, fuente, tam, color, x=M):
        p["ops"].append(f"BT /{fuente} {tam} Tf {COLORES[color]} rg {x:.2f} {y:.2f} Td ".encode()
                        + pdf_cadena(texto) + b" Tj ET")

    p = nueva_pagina()
    y = ALTO_P - 64 - 40
    for linea in envolver_pdf(ej["tema"], 20, ANCHO_UTIL, True):
        linea_texto(p, y, linea, "F2", 20, "marino_medio")
        y -= 24
    linea_texto(p, y + 4, meta_ejercicio(ej), "F1", 10, "celeste_osc")
    y -= 22
    p["ops"].append(f"{COLORES['celeste']} RG 0.8 w {M} {y + 8} m {ANCHO_P - M} {y + 8} l S".encode())
    y -= 10
    linea_texto(p, y, "ENUNCIADO", "F2", 9, "celeste_osc")
    y -= 17
    for parrafo in re.split(r"\n\s*\n", ej["enunciado"]):
        parrafo = " ".join(parrafo.split())
        negrita = parrafo.startswith("Datos de la figura:")
        for linea in envolver_pdf(parrafo, 10.5, ANCHO_UTIL):
            if y < 90:
                p = nueva_pagina()
                y = ALTO_P - 64 - 36
            linea_texto(p, y, linea, "F1", 10.5, "gris" if negrita else "texto")
            y -= 15
        y -= 6

    # Recuadro de asesoría
    y -= 4
    cta_a, cta_b = "¿Necesitas asesoría? ", f"WhatsApp {sitio['whatsapp_visible']}"
    p["ops"].append(f"{COLORES['fondo_cta']} rg {M} {y - 10} {ANCHO_UTIL} 28 re f".encode())
    p["ops"].append(f"{COLORES['lima']} rg {M} {y - 10} 4 28 re f".encode())
    linea_texto(p, y, cta_a, "F1", 11, "texto", M + 14)
    xb = M + 14 + ancho_pdf(cta_a, 11)
    linea_texto(p, y, cta_b, "F2", 11, "marino_medio", xb)
    p["links"].append((M, y - 10, M + ANCHO_UTIL, y + 18, wa))
    y -= 30

    imagen = bytes_jpeg(ej)
    if imagen:
        _, iw, ih, _ = imagen
        disponible = y - 52
        if disponible < 330:
            p = nueva_pagina()
            disponible = ALTO_P - 64 - 30 - 52
            y = ALTO_P - 64 - 24
        escala = min(ANCHO_UTIL / iw, disponible / ih)
        dw, dh = iw * escala, ih * escala
        x0, y0 = (ANCHO_P - dw) / 2, y - dh
        p["ops"].append(f"q {dw:.2f} 0 0 {dh:.2f} {x0:.2f} {y0:.2f} cm /Im1 Do Q".encode())
        p["imagen"] = True

    # Ensamblar objetos: 1 catálogo, 2 páginas, 3-4 fuentes, 5 info, 6 imagen, luego página+contenido
    objetos = [None] * 6
    objetos[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    objetos[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    objetos[4] = (b"<< /Title " + pdf_info_cadena(f"{ej['tema']} – {ej['curso']}")
                  + b" /Author " + pdf_info_cadena("Lindey Asesoramiento Universitario")
                  + b" /Subject " + pdf_info_cadena(recortar(ej["enunciado"], 240))
                  + b" /Keywords " + pdf_info_cadena(", ".join([ej["curso"], ej["tema"]] + ej["palabras"]))
                  + b" /Creator " + pdf_info_cadena("Biblioteca Lindey") + b" >>")
    if imagen:
        datos, iw, ih, espacio = imagen
        objetos[5] = (f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} /ColorSpace {espacio} "
                      f"/BitsPerComponent 8 /Filter /DCTDecode /Length {len(datos)} >>\nstream\n").encode() + datos + b"\nendstream"
    else:
        objetos[5] = b"<< >>"
    kids = []
    for pag in paginas:
        contenido = zlib.compress(b"\n".join(pag["ops"]))
        n_pag, n_cont = len(objetos) + 1, len(objetos) + 2
        kids.append(f"{n_pag} 0 R")
        anotaciones = b" ".join(
            f"<< /Type /Annot /Subtype /Link /Rect [{a:.2f} {b:.2f} {c:.2f} {d:.2f}] /Border [0 0 0] /A << /S /URI /URI ".encode()
            + b"(" + uri.encode("ascii").replace(b"(", b"\\(").replace(b")", b"\\)") + b") >> >>"
            for a, b, c, d, uri in pag["links"])
        recursos = b"<< /Font << /F1 3 0 R /F2 4 0 R >>" + (b" /XObject << /Im1 6 0 R >>" if pag["imagen"] else b"") + b" >>"
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO_P:g} {ALTO_P:g}] /Contents {n_cont} 0 R /Resources ".encode()
                       + recursos + b" /Annots [" + anotaciones + b"] >>")
        objetos.append(f"<< /Length {len(contenido)} /Filter /FlateDecode >>\nstream\n".encode() + contenido + b"\nendstream")
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R /Lang (es) >>"
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()

    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posiciones = []
    for i, cuerpo in enumerate(objetos, start=1):
        posiciones.append(len(salida))
        salida += f"{i} 0 obj\n".encode() + cuerpo + b"\nendobj\n"
    inicio_xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for pos in posiciones:
        salida += f"{pos:010d} 00000 n \n".encode()
    salida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R /Info 5 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n".encode()
    return bytes(salida)


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
    wa = esc(enlace_whatsapp(sitio, mensaje_wa))
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
      <a href="{raiz}pdfs/">PDFs</a>
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
      <a href="{wa}" rel="noopener">WhatsApp {esc(sitio['whatsapp_visible'])}</a>
      <a href="{esc(sitio['facebook'])}" rel="noopener">Facebook</a>
      <a href="{raiz}ejercicios/">Índice de ejercicios</a>
      <a href="{raiz}pdfs/">Repositorio de PDFs</a>
    </p>
  </div>
</footer>
<a class="flotante" href="{wa}" rel="noopener" aria-label="Asesoría por WhatsApp {esc(sitio['whatsapp_visible'])}">{ICONO_CHAT}<span>Asesoría</span></a>
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


def meta_ejercicio(ej, con_curso=True):
    partes = [ej["curso"]] if con_curso else []
    partes += [p for p in (ej["universidad"], ej["evaluacion"], ej["etiqueta"]) if p]
    return " · ".join(partes)


def resumen_enunciado(ej, limite=170):
    return recortar(ej["enunciado"].split("\n\n")[0], limite)


def ficha(ej, raiz, con_curso=True, carga="lazy"):
    ancho, alto = ej["mini_medidas"]
    dims = f' width="{ancho}" height="{alto}"' if ancho else ""
    return f"""<li class="ficha">
  <a href="{raiz}{ej['url']}">
    <img src="{raiz}{ej['mini_url']}" alt="{esc(ej['tema'])} – {esc(meta_ejercicio(ej))}"{dims} loading="{carga}" decoding="async">
    <span class="ficha__cuerpo">
      <span class="ficha__meta">{esc(meta_ejercicio(ej, con_curso))}</span>
      <span class="ficha__titulo">{esc(ej['tema'])}</span>
    </span>
  </a>
</li>"""


def carrusel(ejercicios, raiz, etiqueta, con_curso=False, primeros_visibles=0):
    fichas = "\n".join(
        ficha(e, raiz, con_curso, "eager" if i < primeros_visibles else "lazy") for i, e in enumerate(ejercicios))
    return f"""<div class="carrusel" data-carrusel>
  <button class="carrusel__btn carrusel__btn--prev" type="button" aria-label="Anterior: {esc(etiqueta)}" data-dir="-1">‹</button>
  <ul class="carrusel__pista" aria-label="{esc(etiqueta)}">
{fichas}
  </ul>
  <button class="carrusel__btn carrusel__btn--next" type="button" aria-label="Siguiente: {esc(etiqueta)}" data-dir="1">›</button>
</div>"""


def grilla(ejercicios, raiz, con_curso=True):
    return '<ul class="fichas">' + "\n".join(ficha(e, raiz, con_curso) for e in ejercicios) + "</ul>"


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


def asesoria(sitio, mensaje):
    return f"""<aside class="asesoria" aria-label="Asesoría">
  <p>¿Necesitas asesoría? <a href="{esc(enlace_whatsapp(sitio, mensaje))}" rel="noopener">WhatsApp {esc(sitio['whatsapp_visible'])}</a></p>
</aside>"""


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
    mensaje = f"Hola Lindey, vi el ejercicio «{ej['tema']}» ({ej['curso']}) en la Biblioteca Lindey y necesito asesoría."

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
  {carrusel(relacionados, raiz, f"Más ejercicios de {ej['curso']}")}
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
        <a class="boton boton--pdf" href="{raiz}{ej['pdf_url']}" download>{ICONO_PDF}Descargar PDF</a>
        <a class="boton boton--suave" href="{raiz}{ej['imagen_url']}">Ver imagen completa</a>
      </p>
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
        "url": f"{sitio['url']}/{ej['url']}",
        "encoding": {"@type": "MediaObject", "contentUrl": f"{sitio['url']}/{ej['pdf_url']}",
                     "encodingFormat": "application/pdf"},
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
    return pagina(sitio, raiz=raiz, ruta=ej["url"], titulo=titulo, descripcion=descripcion,
                  contenido=contenido, imagen_social=imagen_abs, tipo_og="article", jsonld=ld,
                  mensaje_wa=mensaje, cuerpo_clase="pag-ejercicio")


def pagina_curso(sitio, curso, ejercicios, documentos):
    raiz = "../"
    slug = slugify(curso)
    unis = sorted({e["universidad"] for e in ejercicios if e["universidad"]})
    uni_txt = f" de {', '.join(unis)}" if unis else ""
    titulo = f"Ejercicios de {curso} con enunciado y figura | {sitio['nombre']}"
    descripcion = recortar(
        f"{len(ejercicios)} ejercicios universitarios de {curso}{uni_txt} con enunciado completo en texto, figura y PDF: "
        + ", ".join(e["tema"].lower() for e in ejercicios[:6]) + ".")
    docs = ""
    if documentos:
        docs = f'<section class="bloque"><h2>PDFs de {esc(curso)}</h2>{lista_documentos(documentos, raiz)}</section>'
    contenido = f"""<div class="envoltura">
{migas(raiz, [(curso, None)])}
<header class="encabezado">
  <p class="antetitulo">Curso</p>
  <h1>Ejercicios de {esc(curso)}</h1>
  <p class="bajada">{len(ejercicios)} {"ejercicio" if len(ejercicios) == 1 else "ejercicios"} con enunciado completo, figura y PDF. Toca un ejercicio para verlo.</p>
</header>
{grilla(ejercicios, raiz, con_curso=False)}
{docs}
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
        f"Ejercicios universitarios de la {nombre_largo}: {', '.join(cursos)}. Enunciado completo, figura y PDF.")
    grupos = []
    for curso in cursos:
        del_curso = [e for e in ejercicios if e["curso"] == curso]
        grupos.append(f'<section class="bloque"><h2>{esc(curso)}</h2>{grilla(del_curso, raiz, con_curso=False)}</section>')
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Universidades", f"{raiz}#universidades"), (sigla, None)])}
<header class="encabezado">
  <p class="antetitulo">Universidad</p>
  <h1>Ejercicios de la {esc(sigla)}</h1>
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


def lista_documentos(documentos, raiz):
    filas = []
    for d in documentos:
        meta = " · ".join(p for p in (d["tipo"], d["universidad"], tamano_legible(d["bytes"])) if p)
        filas.append(f"""<li class="doc">
  <span class="doc__icono">{ICONO_PDF}</span>
  <span class="doc__texto"><a class="doc__titulo" href="{raiz}{d['url']}">{esc(d['titulo'])}</a><span class="doc__meta">{esc(meta)}</span></span>
  <a class="boton boton--pdf boton--chico" href="{raiz}{d['pdf_url']}" download>Descargar</a>
</li>""")
    return '<ul class="docs">' + "".join(filas) + "</ul>"


def lista_pdfs_ejercicios(ejercicios, raiz):
    filas = []
    for e in ejercicios:
        filas.append(f"""<li class="doc">
  <span class="doc__icono">{ICONO_PDF}</span>
  <span class="doc__texto"><a class="doc__titulo" href="{raiz}{e['url']}">{esc(e['tema'])}</a><span class="doc__meta">{esc(meta_ejercicio(e, False) or e['curso'])} · Enunciado + figura</span></span>
  <a class="boton boton--pdf boton--chico" href="{raiz}{e['pdf_url']}" download>PDF</a>
</li>""")
    return '<ul class="docs">' + "".join(filas) + "</ul>"


def pagina_repositorio(sitio, ejercicios, documentos, cursos):
    raiz = "../"
    secciones = []
    if documentos:
        cursos_docs = sorted({d["curso"] for d in documentos}, key=lambda c: orden_curso(sitio, c))
        grupos = "".join(
            f'<h3>{esc(c)}</h3>{lista_documentos([d for d in documentos if d["curso"] == c], raiz)}' for c in cursos_docs)
        secciones.append(f'<section class="bloque" id="documentos"><h2>Documentos</h2>{grupos}</section>')
    grupos = "".join(
        f'<h3>{esc(c)}</h3>{lista_pdfs_ejercicios([e for e in ejercicios if e["curso"] == c], raiz)}' for c in cursos)
    secciones.append(f'<section class="bloque" id="ejercicios-pdf"><h2>Ejercicios en PDF</h2>{grupos}</section>')
    total = len(documentos) + len(ejercicios)
    contenido = f"""<div class="envoltura">
{migas(raiz, [("Repositorio de PDFs", None)])}
<header class="encabezado">
  <p class="antetitulo">Repositorio</p>
  <h1>Repositorio de PDFs</h1>
  <p class="bajada">{total} PDFs para descargar gratis: enunciados con su figura{" y documentos de apoyo" if documentos else ""}, ordenados por curso.</p>
</header>
{"".join(secciones)}
</div>"""
    return pagina(sitio, raiz=raiz, ruta="pdfs/", titulo=f"Repositorio de PDFs de ingeniería | {sitio['nombre']}",
                  descripcion=recortar(f"Descarga en PDF ejercicios universitarios de {', '.join(cursos)}: enunciado completo y figura."),
                  contenido=contenido, jsonld=[migas_jsonld(sitio, [("Repositorio de PDFs", "pdfs/")])])


def pagina_documento(sitio, d):
    raiz = "../../"
    mensaje = f"Hola Lindey, vi el PDF «{d['titulo']}» en la Biblioteca Lindey y necesito asesoría."
    meta = " · ".join(p for p in (d["curso"], d["tipo"], d["universidad"]) if p)
    descripcion = recortar(d["descripcion"] or f"{d['tipo']} de {d['curso']} en PDF para descargar.")
    cuerpo = parrafos(d["descripcion"]) if d["descripcion"] else ""
    contenido = f"""<div class="envoltura">
{migas(raiz, [("PDFs", f"{raiz}pdfs/"), (d['titulo'], None)])}
<article class="documento">
  <header class="ejercicio__cabecera">
    <p class="antetitulo">{esc(meta)}</p>
    <h1>{esc(d['titulo'])}</h1>
  </header>
  <div class="enunciado">
    {cuerpo}
    <p class="acciones">
      <a class="boton boton--pdf" href="{raiz}{d['pdf_url']}" download>{ICONO_PDF}Descargar PDF ({tamano_legible(d['bytes'])})</a>
      <a class="boton boton--suave" href="{raiz}{d['pdf_url']}">Abrir en el navegador</a>
    </p>
  </div>
  <object class="visor" data="{raiz}{d['pdf_url']}" type="application/pdf" aria-label="Vista previa de {esc(d['titulo'])}">
    <p>Tu navegador no muestra el PDF aquí. <a href="{raiz}{d['pdf_url']}">Ábrelo o descárgalo</a>.</p>
  </object>
  {asesoria(sitio, mensaje)}
</article>
</div>"""
    ld = [migas_jsonld(sitio, [("PDFs", "pdfs/"), (d["titulo"], d["url"])]),
          {"@context": "https://schema.org", "@type": "DigitalDocument", "name": d["titulo"], "description": descripcion,
           "inLanguage": "es", "encodingFormat": "application/pdf", "url": f"{sitio['url']}/{d['pdf_url']}",
           "about": d["curso"], "datePublished": d["fecha"], "isAccessibleForFree": True}]
    return pagina(sitio, raiz=raiz, ruta=d["url"], titulo=f"{d['titulo']} (PDF) – {d['curso']} | {sitio['nombre']}",
                  descripcion=descripcion, contenido=contenido, jsonld=ld, mensaje_wa=mensaje)


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
  {carrusel(del_curso, raiz, f"Ejercicios de {curso}", primeros_visibles=4 if i < 2 else 0)}
</section>""")
    chips_uni = []
    for sigla in universidades:
        n = sum(1 for e in ejercicios if e["universidad"] == sigla)
        nombre = sitio["universidades"].get(sigla, "")
        chips_uni.append(
            f'<li><a class="uni" href="universidad/{slugify(sigla)}/"><strong>{esc(sigla)}</strong>'
            f'{f"<span>{esc(nombre)}</span>" if nombre else ""}<em>{n}</em></a></li>')
    total_pdfs = len(ejercicios) + len(documentos)

    contenido = f"""<section class="portada">
  <div class="envoltura">
    <h1>Biblioteca Lindey</h1>
    <p class="portada__bajada">Ejercicios universitarios de ingeniería con su enunciado completo, figura y PDF, de libre consulta. Busca por tema, curso, universidad o pega parte del enunciado.</p>
    <form class="buscador" id="buscar" role="search" action="./" method="get">
      <label class="oculto" for="q">Buscar ejercicio</label>
      <input id="q" name="q" type="search" autocomplete="off" placeholder="Ej.: zapata combinada, pandeo, viga conjugada…">
      <button type="submit">Buscar</button>
    </form>
    <p class="portada__cifras">{len(ejercicios)} ejercicios · {len(cursos)} cursos · {total_pdfs} PDFs</p>
  </div>
</section>
<div class="envoltura">
  <section class="resultados" id="resultados" aria-live="polite" hidden></section>
  <div id="cursos">
    {"".join(secciones_curso)}
  </div>
  <section class="bloque" id="universidades" aria-labelledby="t-unis">
    <h2 id="t-unis">Universidades</h2>
    <ul class="unis">{"".join(chips_uni)}</ul>
  </section>
  <section class="bloque" aria-labelledby="t-pdfs">
    <a class="banda-pdf" href="pdfs/">
      <span class="banda-pdf__icono">{ICONO_PDF}</span>
      <span><strong id="t-pdfs">Repositorio de PDFs</strong><span>{total_pdfs} PDFs para descargar gratis, ordenados por curso.</span></span>
      <span class="enlace-flecha">Entrar</span>
    </a>
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

def indice_busqueda(ejercicios, documentos):
    filas = [{
        "t": e["tema"], "c": e["curso"], "u": e["universidad"], "un": e["universidad_nombre"],
        "v": e["evaluacion"], "e": e["etiqueta"], "k": ", ".join(e["palabras"]),
        "d": e["enunciado"], "url": e["url"], "m": e["mini_url"],
        "mw": e["mini_medidas"][0], "mh": e["mini_medidas"][1],
    } for e in ejercicios]
    filas += [{
        "t": d["titulo"], "c": d["curso"], "u": d["universidad"], "un": d["universidad_nombre"],
        "v": d["tipo"], "e": "PDF", "k": ", ".join(d["palabras"]), "d": d["descripcion"], "url": d["url"], "m": "",
    } for d in documentos]
    return json.dumps(filas, ensure_ascii=False, separators=(",", ":"))


def sitemap(sitio, ejercicios, documentos, cursos, universidades):
    hoy = max([e["fecha"] for e in ejercicios] + [d["fecha"] for d in documentos] or [date.today().isoformat()])
    filas = [(f"{sitio['url']}/", hoy, None), (f"{sitio['url']}/ejercicios/", hoy, None), (f"{sitio['url']}/pdfs/", hoy, None)]
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
        filas.append((f"{sitio['url']}/{e['pdf_url']}", e["fecha"], None))
    for d in documentos:
        filas.append((f"{sitio['url']}/{d['url']}", d["fecha"], None))
        filas.append((f"{sitio['url']}/{d['pdf_url']}", d["fecha"], None))
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
    ejercicios = sorted(cargar(CARPETA_EJERCICIOS, leer_ejercicio, sitio), key=orden_ejercicio(sitio))
    documentos = sorted(cargar(CARPETA_PDFS, leer_documento, sitio),
                        key=lambda d: (orden_curso(sitio, d["curso"]), d["titulo"]))
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
        crear_miniatura(e)
        escribir(e["pdf_url"], pdf_ejercicio(sitio, e))
    for d in documentos:
        destino = SALIDA / d["pdf_url"]
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(d["origen"], destino)

    for e in ejercicios:
        relacionados = [o for o in ejercicios if o["curso"] == e["curso"] and o is not e]
        escribir(f"{e['url']}index.html", pagina_ejercicio(sitio, e, relacionados))
    for curso in cursos:
        escribir(f"{slugify(curso)}/index.html",
                 pagina_curso(sitio, curso, [e for e in ejercicios if e["curso"] == curso],
                              [d for d in documentos if d["curso"] == curso]))
    for sigla in universidades:
        escribir(f"universidad/{slugify(sigla)}/index.html",
                 pagina_universidad(sitio, sigla, [e for e in ejercicios if e["universidad"] == sigla]))
    for d in documentos:
        escribir(f"{d['url']}index.html", pagina_documento(sitio, d))
    escribir("pdfs/index.html", pagina_repositorio(sitio, ejercicios, documentos, cursos))
    escribir("ejercicios/index.html", pagina_indice(sitio, ejercicios, cursos))
    escribir("index.html", pagina_portada(sitio, ejercicios, documentos, cursos, universidades))
    escribir("404.html", pagina_404(sitio))
    escribir("buscar.json", indice_busqueda(ejercicios, documentos))
    escribir("sitemap.xml", sitemap(sitio, ejercicios, documentos, cursos, universidades))
    escribir("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {sitio['url']}/sitemap.xml\n")
    escribir(".nojekyll", "")

    print(f"Listo: {len(ejercicios)} ejercicios, {len(documentos)} PDFs propios, {len(cursos)} cursos, "
          f"{len(universidades)} universidades{'' if Image else ' (sin miniaturas: instala Pillow)'} → _site/")
    print(f"URL pública: {sitio['url']}/")


if __name__ == "__main__":
    main()
