/* Biblioteca Lindey — scripts del sitio.
   1. Carruseles: se mueven solos sin parar (catálogo en movimiento), con flechas.
      Se detienen mientras el mouse está encima o al tocarlos, y siguen solos después.
   2. Visor de PDFs tipo revista: pasa hojas, miniaturas, pantalla completa, teclado y deslizar.
   3. Compartir: copiar enlace y menú de compartir del celular.
   4. Buscador de la portada: busca en buscar.json ignorando tildes; acepta frases de Google Lens. */
(function () {
  "use strict";

  var raiz = document.body.getAttribute("data-raiz") || "";
  var EN = document.documentElement.lang === "en";
  var TXT = EN ? {
    copiado: "Link copied!", resultados: "Results", nada: "We couldn't find that exercise yet. ",
    escribenos: "Message us on WhatsApp", ayudamos: " and we'll help you find it.",
    uno: " result.", varios: " results.", error: "The search could not load. Check your connection and try again."
  } : {
    copiado: "¡Enlace copiado!", resultados: "Resultados", nada: "No encontramos ese ejercicio todavía. ",
    escribenos: "Escríbenos por WhatsApp", ayudamos: " y te ayudamos a encontrarlo.",
    uno: " resultado.", varios: " resultados.", error: "No se pudo cargar el buscador. Revisa tu conexión e inténtalo de nuevo."
  };
  var menosMovimiento = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------- carruseles */

  var VELOCIDAD = 42; // píxeles por segundo

  function activarCarrusel(caja) {
    var pista = caja.querySelector(".carrusel__pista");
    var botones = caja.querySelectorAll(".carrusel__btn");
    if (!pista) return;
    var originales = Array.prototype.slice.call(pista.children);
    var automatico = !menosMovimiento && originales.length > 1;
    var periodo = 0;

    function clonar() {
      originales.forEach(function (li) {
        var copia = li.cloneNode(true);
        copia.setAttribute("aria-hidden", "true");
        copia.querySelectorAll("a, button").forEach(function (el) { el.tabIndex = -1; });
        pista.appendChild(copia);
      });
    }

    if (automatico) {
      clonar();
      periodo = pista.children[originales.length].offsetLeft - originales[0].offsetLeft;
      var vueltas = 1;
      while (periodo > 0 && pista.scrollWidth - periodo < pista.clientWidth * 2 + 40 && vueltas < 12) {
        clonar();
        vueltas++;
      }
      if (periodo <= 0) automatico = false;
    }

    function enRango() {
      var x = pista.scrollLeft;
      if (periodo > 0 && x >= periodo) {
        x = x % periodo;
        pista.scrollLeft = x;
      }
      return x;
    }

    function actualizarFlechas() {
      if (automatico) return;
      var max = pista.scrollWidth - pista.clientWidth - 2;
      botones.forEach(function (b) {
        b.disabled = b.getAttribute("data-dir") === "-1" ? pista.scrollLeft <= 2 : pista.scrollLeft >= max;
      });
    }

    var encima = false, foco = false, manualHasta = 0, visible = true, pausadoAntes = true, pos = 0, ultimo = null;

    function detenidoAhora(t) { return encima || foco || t < manualHasta || !visible || document.hidden; }

    function avanzar(t) {
      if (ultimo !== null) {
        var detenido = detenidoAhora(t);
        if (!detenido) {
          if (pausadoAntes) pos = enRango();
          pos += VELOCIDAD * Math.min(t - ultimo, 64) / 1000;
          if (pos >= periodo) pos -= periodo;
          pista.scrollLeft = pos;
        }
        pausadoAntes = detenido;
      }
      ultimo = t;
      window.requestAnimationFrame(avanzar);
    }

    botones.forEach(function (b) {
      b.addEventListener("click", function () {
        var dir = Number(b.getAttribute("data-dir"));
        var paso = Math.max(pista.clientWidth * 0.8, 240);
        if (automatico) {
          manualHasta = performance.now() + 4000;
          var x = enRango();
          if (dir < 0 && x < paso) pista.scrollLeft = x + periodo;
        }
        pista.scrollBy({ left: paso * dir, behavior: "smooth" });
      });
    });

    if (automatico) {
      caja.classList.add("carrusel--auto");
      caja.addEventListener("mouseenter", function () { encima = true; });
      caja.addEventListener("mouseleave", function () { encima = false; });
      caja.addEventListener("focusin", function (ev) {
        foco = ev.target.matches && ev.target.matches(":focus-visible");
      });
      caja.addEventListener("focusout", function () { foco = false; });
      ["touchstart", "wheel", "pointerdown"].forEach(function (tipo) {
        pista.addEventListener(tipo, function () { manualHasta = performance.now() + 3500; }, { passive: true });
      });
      pista.addEventListener("scroll", function () {
        if (performance.now() < manualHasta) manualHasta = Math.max(manualHasta, performance.now() + 2500);
      }, { passive: true });
      if ("IntersectionObserver" in window) {
        var cargadas = false;
        new IntersectionObserver(function (entradas) {
          visible = entradas[0].isIntersecting;
          if (visible && !cargadas) {
            cargadas = true;
            pista.querySelectorAll("img[loading='lazy']").forEach(function (im) { im.loading = "eager"; });
          }
        }, { rootMargin: "300px 0px" }).observe(caja);
      }
      window.requestAnimationFrame(avanzar);
    } else {
      pista.addEventListener("scroll", function () { window.requestAnimationFrame(actualizarFlechas); }, { passive: true });
      window.addEventListener("resize", actualizarFlechas);
      actualizarFlechas();
    }
  }

  document.querySelectorAll("[data-carrusel]").forEach(activarCarrusel);

  /* ------------------------------------------------- visor tipo revista */

  function activarLibro(libro) {
    var nodoDatos = libro.querySelector(".libro__datos");
    if (!nodoDatos) return;
    var paginas = JSON.parse(nodoDatos.textContent);
    var n = paginas.length;
    var hojas = libro.querySelector(".libro__hojas");
    var contador = libro.querySelector(".libro__contador");
    var minis = libro.querySelectorAll("[data-pagina]");
    var proporcion = (paginas[0].w && paginas[0].h) ? paginas[0].w / paginas[0].h : 0.707;
    var vista = 0, animando = false, modoDoble = null;

    function doble() { return n > 1 && libro.clientWidth >= 760; }
    function totalVistas() { return doble() ? Math.floor(n / 2) + 1 : n; }
    function paginasDe(v) { return doble() ? [2 * v - 1, 2 * v] : [v]; }
    function vistaDe(p) { return doble() ? Math.ceil(p / 2) : p; }
    function primeraReal(v) { var ps = paginasDe(v).filter(function (p) { return p >= 0 && p < n; }); return ps.length ? ps[0] : 0; }

    function imagen(i) {
      if (i < 0 || i >= n) return null;
      var im = new Image();
      im.src = paginas[i].i;
      im.alt = "Página " + (i + 1);
      im.decoding = "async";
      im.draggable = false;
      return im;
    }

    function poner(caja, i) {
      caja.textContent = "";
      var im = imagen(i);
      caja.classList.toggle("vacia", !im);
      if (im) caja.appendChild(im);
    }

    function medir() {
      var factor = doble() ? 2 : 1;
      var alto = document.fullscreenElement === libro ? 84 : 76;
      hojas.style.aspectRatio = String(factor * proporcion);
      hojas.style.width = "min(100%, " + (alto * factor * proporcion).toFixed(2) + "vh)";
    }

    function pintar() {
      modoDoble = doble();
      medir();
      hojas.textContent = "";
      hojas.classList.toggle("es-doble", modoDoble);
      paginasDe(vista).forEach(function (i, k) {
        var cara = document.createElement("div");
        cara.className = "libro__pag " + (modoDoble ? (k === 0 ? "izq" : "der") : "unica");
        poner(cara, i);
        hojas.appendChild(cara);
      });
      var visibles = paginasDe(vista).filter(function (p) { return p >= 0 && p < n; }).map(function (p) { return p + 1; });
      contador.textContent = visibles.join("–") + " / " + n;
      minis.forEach(function (m) {
        var activa = visibles.indexOf(Number(m.getAttribute("data-pagina")) + 1) !== -1;
        m.classList.toggle("es-activa", activa);
        if (activa && m === minis[visibles[0] - 1]) {
          var tira = m.parentNode;
          tira.scrollTo({ left: m.offsetLeft - tira.clientWidth / 2 + m.clientWidth / 2, behavior: "smooth" });
        }
      });
      [-1, 1].forEach(function (d) {
        paginasDe(vista + d).forEach(function (p) { if (p >= 0 && p < n) new Image().src = paginas[p].i; });
      });
    }

    function ir(destino) {
      if (animando || destino < 0 || destino >= totalVistas() || destino === vista) return;
      var dir = destino > vista ? 1 : -1;
      if (!doble() || menosMovimiento || Math.abs(destino - vista) > 1) {
        vista = destino;
        pintar();
        if (!doble() && !menosMovimiento) {
          var unica = hojas.querySelector(".unica");
          if (unica) unica.classList.add(dir > 0 ? "entra-der" : "entra-izq");
        }
        return;
      }
      animando = true;
      var actuales = paginasDe(vista), nuevas = paginasDe(destino);
      var izq = hojas.querySelector(".izq"), der = hojas.querySelector(".der");
      var hoja = document.createElement("div");
      hoja.className = "libro__volteo " + (dir > 0 ? "hacia-izq" : "hacia-der");
      var frente = document.createElement("div");
      frente.className = "libro__cara";
      var dorso = document.createElement("div");
      dorso.className = "libro__cara libro__cara--dorso";
      poner(frente, dir > 0 ? actuales[1] : actuales[0]);
      poner(dorso, dir > 0 ? nuevas[0] : nuevas[1]);
      hoja.appendChild(frente);
      hoja.appendChild(dorso);
      if (dir > 0) poner(der, nuevas[1]); else poner(izq, nuevas[0]);
      hojas.appendChild(hoja);
      var terminado = false;
      function terminar() {
        if (terminado) return;
        terminado = true;
        vista = destino;
        animando = false;
        pintar();
      }
      window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () { hoja.classList.add("girando"); });
      });
      hoja.addEventListener("transitionend", terminar);
      setTimeout(terminar, 1100);
    }

    libro.querySelectorAll("[data-ir]").forEach(function (b) {
      b.addEventListener("click", function () { ir(vista + Number(b.getAttribute("data-ir"))); });
    });
    minis.forEach(function (m) {
      m.addEventListener("click", function () { ir(vistaDe(Number(m.getAttribute("data-pagina")))); });
    });
    hojas.addEventListener("click", function (ev) {
      var caja = hojas.getBoundingClientRect();
      ir(vista + (ev.clientX - caja.left > caja.width / 2 ? 1 : -1));
    });
    libro.addEventListener("keydown", function (ev) {
      if (ev.key === "ArrowRight") { ir(vista + 1); ev.preventDefault(); }
      if (ev.key === "ArrowLeft") { ir(vista - 1); ev.preventDefault(); }
    });
    var inicioX = null;
    hojas.addEventListener("touchstart", function (ev) { inicioX = ev.touches[0].clientX; }, { passive: true });
    hojas.addEventListener("touchend", function (ev) {
      if (inicioX === null) return;
      var dx = ev.changedTouches[0].clientX - inicioX;
      if (Math.abs(dx) > 40) ir(vista + (dx < 0 ? 1 : -1));
      inicioX = null;
    });
    var botonPantalla = libro.querySelector("[data-pantalla]");
    if (botonPantalla) {
      if (!libro.requestFullscreen) botonPantalla.hidden = true;
      botonPantalla.addEventListener("click", function () {
        if (document.fullscreenElement) document.exitFullscreen();
        else libro.requestFullscreen().catch(function () {});
      });
    }
    document.addEventListener("fullscreenchange", medir);
    window.addEventListener("resize", function () {
      if (doble() !== modoDoble) {
        var pagina = primeraReal(vista);
        modoDoble = doble();
        vista = vistaDe(pagina);
        pintar();
      } else {
        medir();
      }
    });
    pintar();
  }

  document.querySelectorAll("[data-libro]").forEach(activarLibro);

  /* ----------------------------------------------------------- compartir */

  document.querySelectorAll("[data-compartir]").forEach(function (caja) {
    var url = caja.getAttribute("data-url");
    var texto = caja.getAttribute("data-texto");
    var nativo = caja.querySelector("[data-nativo]");
    if (nativo && navigator.share) {
      nativo.hidden = false;
      nativo.addEventListener("click", function () {
        navigator.share({ title: document.title, text: texto, url: url }).catch(function () {});
      });
    }
    var copiar = caja.querySelector("[data-copiar]");
    if (!copiar) return;
    copiar.addEventListener("click", function () {
      var etiqueta = copiar.querySelector("span");
      var original = etiqueta.textContent;
      function listo() {
        etiqueta.textContent = TXT.copiado;
        copiar.classList.add("es-ok");
        setTimeout(function () { etiqueta.textContent = original; copiar.classList.remove("es-ok"); }, 2200);
      }
      function respaldo() {
        var area = document.createElement("textarea");
        area.value = url;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        try { document.execCommand("copy"); listo(); } catch (e) { /* sin portapapeles */ }
        document.body.removeChild(area);
      }
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(listo, respaldo);
      else respaldo();
    });
  });

  /* ------------------------------------------------------------ buscador */

  var form = document.getElementById("buscar");
  var input = document.getElementById("q");
  var caja = document.getElementById("resultados");
  if (!form || !input || !caja) return;

  var flotante = document.querySelector(".flotante");
  var enlaceWa = flotante ? flotante.href : "";
  var datos = null;
  var cargando = null;
  var espera = null;

  var VACIAS = {};
  ("a al con de del el en es la las lo los o para por que se su sus un una y e u le les como este esta " +
   "cual cuales cada si sin sobre entre muestra mostrada figura determine determinar calcular halle " +
   "the of an and in on at to is are for with by from as shown that this its it find calculate")
    .split(" ").forEach(function (p) { VACIAS[p] = true; });

  function normalizar(texto) {
    return (texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }

  function palabras(texto) {
    return normalizar(texto).split(/[^a-z0-9]+/).filter(function (p) { return p && !VACIAS[p]; });
  }

  function cargar() {
    if (datos) return Promise.resolve(datos);
    if (!cargando) {
      cargando = fetch(raiz + (form.getAttribute("data-indice") || "buscar.json"))
        .then(function (r) { return r.json(); })
        .then(function (lista) {
          datos = lista.map(function (d) {
            d._titulo = " " + palabras([d.t, d.c, d.u, d.un, d.k].join(" ")).join(" ") + " ";
            d._todo = " " + palabras([d.t, d.c, d.u, d.un, d.v, d.e, d.k, d.d].join(" ")).join(" ") + " ";
            return d;
          });
          return datos;
        });
    }
    return cargando;
  }

  function elemento(etiqueta, clase, texto) {
    var el = document.createElement(etiqueta);
    if (clase) el.className = clase;
    if (texto) el.textContent = texto;
    return el;
  }

  function ficha(d) {
    var esDoc = d.e === "PDF";
    var li = elemento("li", esDoc ? "ficha ficha--doc" : "ficha");
    var a = elemento("a");
    a.href = raiz + d.url;
    if (d.m) {
      var img = elemento("img");
      img.src = raiz + d.m;
      img.alt = d.t;
      img.loading = "lazy";
      if (d.mw) { img.width = d.mw; img.height = d.mh; }
      if (esDoc) {
        var tapa = elemento("span", "libro-tapa");
        tapa.appendChild(img);
        a.appendChild(tapa);
      } else {
        a.appendChild(img);
      }
    } else {
      var vacia = elemento("span", "libro-tapa");
      vacia.appendChild(elemento("span", "libro-tapa__vacia", "PDF"));
      a.appendChild(vacia);
    }
    var cuerpo = elemento("span", "ficha__cuerpo");
    cuerpo.appendChild(elemento("span", "ficha__meta", [d.c, d.u, d.v, d.e].filter(Boolean).join(" · ")));
    cuerpo.appendChild(elemento("span", "ficha__titulo", d.t));
    a.appendChild(cuerpo);
    li.appendChild(a);
    return li;
  }

  function mostrar(consulta) {
    var tokens = palabras(consulta);
    if (!tokens.length) {
      caja.hidden = true;
      caja.textContent = "";
      return;
    }
    cargar().then(function (lista) {
      var minimo = tokens.length <= 3 ? tokens.length : Math.ceil(tokens.length * 0.6);
      var encontrados = [];
      lista.forEach(function (d) {
        var aciertos = 0, puntos = 0;
        tokens.forEach(function (t) {
          var clave = " " + t;
          if (d._todo.indexOf(clave) !== -1) {
            aciertos++;
            puntos += d._titulo.indexOf(clave) !== -1 ? 3 : 1;
          }
        });
        if (aciertos >= minimo) encontrados.push({ d: d, puntos: puntos + aciertos * 2 });
      });
      encontrados.sort(function (a, b) { return b.puntos - a.puntos; });

      caja.textContent = "";
      caja.appendChild(elemento("h2", "", TXT.resultados));
      var n = encontrados.length;
      var estado = elemento("p", "resultados__estado", n === 0 ? TXT.nada : n + (n === 1 ? TXT.uno : TXT.varios));
      if (n === 0 && enlaceWa) {
        var wa = elemento("a", "", TXT.escribenos);
        wa.href = enlaceWa;
        wa.rel = "noopener";
        estado.appendChild(wa);
        estado.appendChild(document.createTextNode(TXT.ayudamos));
      }
      caja.appendChild(estado);
      if (n) {
        var ul = elemento("ul", "fichas");
        encontrados.slice(0, 40).forEach(function (r) { ul.appendChild(ficha(r.d)); });
        caja.appendChild(ul);
      }
      caja.hidden = false;
    }).catch(function () {
      caja.hidden = false;
      caja.textContent = TXT.error;
    });
  }

  function actualizarDireccion(consulta) {
    if (!window.history || !history.replaceState) return;
    var url = new URL(window.location.href);
    if (consulta) url.searchParams.set("q", consulta); else url.searchParams.delete("q");
    history.replaceState(null, "", url);
  }

  input.addEventListener("input", function () {
    clearTimeout(espera);
    espera = setTimeout(function () {
      mostrar(input.value);
      actualizarDireccion(input.value.trim());
    }, 180);
  });

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    mostrar(input.value);
    actualizarDireccion(input.value.trim());
    if (!caja.hidden) caja.scrollIntoView({ block: "start" });
  });

  var inicial = new URLSearchParams(window.location.search).get("q");
  if (inicial) {
    input.value = inicial;
    mostrar(inicial);
  }
})();
