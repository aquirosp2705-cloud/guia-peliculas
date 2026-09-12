# Cartelera del Cable

Una app para el iPad que muestra **qué películas dan hoy** en los canales de
cable, con el horario en hora de Ecuador, la sinopsis, el año y la puntuación.

---

## Cómo instalarla en el iPad

1. Abre **Safari** en el iPad (tiene que ser Safari, no Chrome).
2. Entra a la dirección de la app.
3. Toca el botón **Compartir** (el cuadrito con la flecha hacia arriba, arriba
   a la derecha).
4. Baja en la lista y toca **Agregar a pantalla de inicio**.
5. Ponle el nombre que quieras y toca **Agregar**.

Listo: te queda el ícono en la pantalla del iPad como cualquier otra app, y al
abrirlo no se ve la barra del navegador.

---

## Cómo se usa

- **Arriba** eliges el día: HOY, Mañana, y los siguientes.
- **Abajo de la lupa** eliges el canal. Si no eliges ninguno, salen todos.
- Al abrirla, te lleva directo a la **franja horaria en la que estás**
  (mañana, tarde o noche), no al principio del día.
- Las películas que están **al aire en este momento** salen con un borde verde
  y la etiqueta "Al aire".
- **Toca una película** para ver la sinopsis completa.
- La **lupa** busca en los 7 días a la vez. Sirve para saber cuándo vuelven a
  pasar una película que te interesa.
- **"Solo la noche"** deja únicamente lo que empieza de las 18:00 en adelante.

Si el iPad se queda sin internet, la app igual abre y te muestra la última
programación que alcanzó a descargar.

---

## Cómo se actualiza

Sola. **No tienes que hacer nada.**

Todos los días, a las 05:00 y a las 15:00 de Ecuador, un robot de GitHub:

1. Descarga la programación de los canales.
2. Busca cada película para traer su sinopsis, año, puntuación y afiche.
3. Guarda todo en el archivo `datos/guia.json`.

La próxima vez que abras la app, ya está actualizada.

También se puede lanzar a mano: en GitHub, pestaña **Actions** →
**Actualizar cartelera** → botón **Run workflow**.

---

## De dónde salen los datos

| Qué | De dónde |
|---|---|
| La parrilla de los canales | gatotv.com (edición de Ecuador) |
| Los canales que gatotv no tiene (HBO 2, HBO Family, HBO Pop, HBO Xtreme) | archivos XMLTV de epgshare01.online |
| Sinopsis, año, puntuación y afiche | TMDB (themoviedb.org) |

Los horarios ya vienen en hora de Ecuador (UTC-5). Los del archivo de Colombia
se convierten restando 5 horas; esto está comprobado comparando la misma
película en los dos archivos.

---

## Los canales que trae

**Cine:** CineCanal, HBO, HBO 2, HBO Family, HBO Pop, HBO Xtreme, Cinemax,
Golden, Studio Universal, TCM, AMC.

**Películas y series:** TNT, AXN, Space, Star Channel, FX, Warner TV, Sony,
Universal TV.

**Más cine:** Sony Movies, Cinelatino, De Película, Multipremier,
Europa Europa, Eurochannel.

En la app solo aparecen los canales que ese día tienen películas. Si un canal
esa semana solo pasa series (le pasa a AXN y a Universal TV), no sale en la
lista: no es un error.

---

## Si algo falla

**La app dice "No se pudo cargar la programación"**
No hay internet, o todavía no se ha generado el archivo. Revisa la conexión y
vuelve a abrirla.

**Los datos están viejos**
Entra a GitHub → pestaña **Actions** y mira si la última ejecución salió con
una marca verde. Si salió roja, algo falló; avísame.

**Falta el año o la puntuación de una película**
Pasa con el cine mexicano y europeo de catálogo, que TMDB no tiene bien
registrado. La película se muestra igual, solo sin esos datos. Preferí dejar
un dato en blanco antes que poner uno equivocado.

**Quiero agregar o quitar un canal**
Se cambia la lista `CANALES` que está al principio del archivo
`actualizar.py`.

---

## La clave de TMDB

La clave está guardada en dos lugares y **nunca** aparece en la página
publicada:

- En esta computadora: el archivo `clave-tmdb.txt`, que está en el
  `.gitignore` y por eso jamás se sube a GitHub.
- En GitHub: en *Settings → Secrets and variables → Actions*, con el nombre
  `TMDB_API_KEY`. Solo la usa el robot cuando arma la guía.

---

## Los archivos

| Archivo | Para qué sirve |
|---|---|
| `index.html` | La app entera (pantalla, botones y lógica) |
| `actualizar.py` | El programa que arma la guía |
| `datos/guia.json` | La programación ya lista que lee la app |
| `datos/cache-peliculas.json` | Fichas ya buscadas, para no repetir consultas |
| `sw.js` | Hace que la app abra sin internet |
| `manifest.webmanifest` | Hace que se vea como app en el iPad |
| `.github/workflows/actualizar.yml` | Las instrucciones del robot diario |
