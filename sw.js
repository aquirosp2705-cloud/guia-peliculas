/*
  Service worker de la Cartelera del Cable.
  Sirve para dos cosas:
   1) que la app abra al instante, sin esperar a la red
   2) que si no hay internet, se vea la ultima programacion descargada
*/

var VERSION = "cartelera-v2";
var BASICOS = [
  "./",
  "./index.html",
  "./manifest.webmanifest",
  "./icono-180.png",
  "./icono-192.png",
  "./icono-512.png"
];

// Al instalar, guardamos los archivos de la app
self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(VERSION)
      .then(function (c) { return c.addAll(BASICOS); })
      .then(function () { return self.skipWaiting(); })
      .catch(function () { /* si algo falla, seguimos igual */ })
  );
});

// Al activarse, borramos versiones viejas
self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (nombres) {
      return Promise.all(nombres.map(function (n) {
        if (n !== VERSION) return caches.delete(n);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function (e) {
  var pedido = e.request;
  if (pedido.method !== "GET") return;

  var url = new URL(pedido.url);

  // Los posters vienen de fuera: los guardamos segun se van viendo
  if (url.origin !== self.location.origin) {
    e.respondWith(
      caches.match(pedido).then(function (guardado) {
        return guardado || fetch(pedido).then(function (r) {
          if (r && r.status === 200) {
            var copia = r.clone();
            caches.open(VERSION).then(function (c) { c.put(pedido, copia); });
          }
          return r;
        }).catch(function () { return guardado; });
      })
    );
    return;
  }

  // La app en si (index.html): siempre la version de internet, para que
  // cualquier mejora se vea de inmediato. Si no hay red, la guardada.
  var esLaApp = pedido.mode === "navigate" ||
                url.pathname.indexOf("index.html") >= 0 ||
                url.pathname === "/" || /\/$/.test(url.pathname);
  if (esLaApp) {
    e.respondWith(
      fetch(pedido).then(function (r) {
        if (r && r.status === 200) {
          var copia = r.clone();
          caches.open(VERSION).then(function (c) {
            c.put(new Request("./index.html"), copia);
          });
        }
        return r;
      }).catch(function () {
        return caches.match("./index.html") || caches.match("./");
      })
    );
    return;
  }

  // La programacion: primero la de internet, y si no hay, la guardada
  if (url.pathname.indexOf("guia.json") >= 0) {
    e.respondWith(
      fetch(pedido).then(function (r) {
        if (r && r.status === 200) {
          var copia = r.clone();
          caches.open(VERSION).then(function (c) {
            c.put(new Request("./datos/guia.json"), copia);
          });
        }
        return r;
      }).catch(function () {
        return caches.match("./datos/guia.json");
      })
    );
    return;
  }

  // El resto de la app: primero lo guardado, y de fondo se actualiza
  e.respondWith(
    caches.match(pedido).then(function (guardado) {
      var desdeRed = fetch(pedido).then(function (r) {
        if (r && r.status === 200) {
          var copia = r.clone();
          caches.open(VERSION).then(function (c) { c.put(pedido, copia); });
        }
        return r;
      }).catch(function () { return guardado; });
      return guardado || desdeRed;
    })
  );
});
