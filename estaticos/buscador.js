/* Biblioteca Lindey — buscador de la portada.
   Lee buscar.json y filtra por tema, curso, universidad, conceptos y enunciado.
   Ignora tildes y mayúsculas; acepta frases largas pegadas desde Google Lens. */
(function () {
  "use strict";

  var form = document.getElementById("buscar");
  var input = document.getElementById("q");
  var caja = document.getElementById("resultados");
  if (!form || !input || !caja) return;

  var raiz = document.body.getAttribute("data-raiz") || "";
  var flotante = document.querySelector(".flotante");
  var enlaceWa = flotante ? flotante.href : "";
  var datos = null;
  var cargando = null;
  var espera = null;

  var VACIAS = {};
  ("a al con de del el en es la las lo los o para por que se su sus un una y e u le les como este esta " +
   "cual cuales cada si sin sobre entre muestra mostrada figura determine determinar calcular halle")
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
      cargando = fetch(raiz + "buscar.json")
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

  function tarjeta(d) {
    var li = elemento("li", "tarjeta");
    var a = elemento("a");
    a.href = raiz + d.url;
    var meta = [d.c, d.u, d.v, d.e].filter(Boolean).join(" · ");
    a.appendChild(elemento("span", "tarjeta__meta", meta));
    a.appendChild(elemento("span", "tarjeta__titulo", d.t));
    a.appendChild(elemento("span", "tarjeta__texto", d.r));
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
      caja.appendChild(elemento("h2", "", "Resultados"));
      var n = encontrados.length;
      var estado = elemento("p", "resultados__estado",
        n === 0 ? "No encontramos ese ejercicio todavía. "
                : n + (n === 1 ? " ejercicio encontrado." : " ejercicios encontrados."));
      if (n === 0 && enlaceWa) {
        var wa = elemento("a", "", "Escríbenos por WhatsApp");
        wa.href = enlaceWa;
        wa.rel = "noopener";
        estado.appendChild(wa);
        estado.appendChild(document.createTextNode(" y te ayudamos a encontrarlo."));
      }
      caja.appendChild(estado);
      if (n) {
        var ul = elemento("ul", "tarjetas");
        encontrados.slice(0, 40).forEach(function (r) { ul.appendChild(tarjeta(r.d)); });
        caja.appendChild(ul);
      }
      caja.hidden = false;
    }).catch(function () {
      caja.hidden = false;
      caja.textContent = "No se pudo cargar el buscador. Revisa tu conexión e inténtalo de nuevo.";
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
