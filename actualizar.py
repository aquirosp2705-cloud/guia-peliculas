# -*- coding: utf-8 -*-
"""
ACTUALIZAR.PY
Arma el archivo datos/guia.json con las peliculas que dan los canales de cable
en Ecuador, con sus horarios en hora de Ecuador (UTC-5).

De donde salen los datos:
  1) gatotv.com  -> fuente principal. Marca cada programa como "pelicula" o
                    "programa", asi que la separacion cine / series es exacta.
  2) epgshare01.online -> archivos XMLTV ya armados de Ecuador (EC1) y
                    Colombia (CO1). Sirven para los canales que gatotv no
                    tiene en su edicion de Ecuador (HBO 2, HBO Family, etc.)
                    y como respaldo si gatotv falla.
  3) TMDB -> sinopsis en espanol, anio, puntuacion y poster.

No necesita instalar nada: solo Python estandar.
"""

import datetime as dt
import gzip
import html
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# --------------------------------------------------------------------------
# Ajustes generales
# --------------------------------------------------------------------------

ECUADOR = dt.timezone(dt.timedelta(hours=-5))   # America/Guayaquil, fijo todo el ano
DIAS_ADELANTE = 7                                # cuantos dias intentamos traer
AQUI = os.path.dirname(os.path.abspath(__file__))
CARPETA_DATOS = os.path.join(AQUI, "datos")
ARCHIVO_GUIA = os.path.join(CARPETA_DATOS, "guia.json")
ARCHIVO_CACHE = os.path.join(CARPETA_DATOS, "cache-peliculas.json")

NAVEGADOR = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
             "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# Duracion minima para que algo cuente como pelicula (minutos)
MINUTOS_MINIMOS = 60

# --------------------------------------------------------------------------
# Catalogo de canales
#   clave  : identificador corto que usa la app
#   gato   : identificador en gatotv.com (None si no existe)
#   ec/co  : expresion para encontrarlo en el XMLTV de Ecuador / Colombia
#   cine   : True si es un canal dedicado a peliculas
# --------------------------------------------------------------------------

CANALES = [
    # ---- Canales de cine ------------------------------------------------
    dict(clave="cinecanal", nombre="CineCanal", grupo="Cine", cine=True,
         color="#e11d48", gato="cinecanal_ecuador",
         ec=r"^Canal\.Cinecanal\.", co=r"^Cinecanal\.co$"),
    # HBO: comprobado el 11/09/2026 contra la senal real. gatotv daba una
    # parrilla equivocada ("En el camino") y el archivo de Colombia daba la
    # correcta ("La posesion de la momia"), igual que en HBO Family. Por eso
    # este canal no usa gatotv.
    dict(clave="hbo", nombre="HBO", grupo="Cine", cine=True,
         color="#7c3aed", gato=None,
         ec=None, co=r"^HBO\.co$"),
    dict(clave="hbo2", nombre="HBO 2", grupo="Cine", cine=True,
         color="#8b5cf6", gato=None, ec=None, co=r"^HBO\.2\.co$"),
    dict(clave="hbofamily", nombre="HBO Family", grupo="Cine", cine=True,
         color="#a78bfa", gato=None, ec=None, co=r"^HBO\.Family\.co$"),
    dict(clave="hbopop", nombre="HBO Pop", grupo="Cine", cine=True,
         color="#c084fc", gato=None, ec=None, co=r"^HBO\.POP\.co$"),
    dict(clave="hboxtreme", nombre="HBO Xtreme", grupo="Cine", cine=True,
         color="#9333ea", gato=None, ec=None, co=r"^HBO\.XTREME\.co$"),
    dict(clave="cinemax", nombre="Cinemax", grupo="Cine", cine=True,
         color="#0891b2", gato="cinemax_ecuador",
         ec=r"^Canal\.Cinemax\.", co=r"^Cinemax\.co$"),
    dict(clave="golden", nombre="Golden", grupo="Cine", cine=True,
         color="#ca8a04", gato="golden_ecuador",
         ec=r"^Canal\.Golden\.", co=r"^GOLDEN\.HD\.co$"),
    dict(clave="studiouniversal", nombre="Studio Universal", grupo="Cine", cine=True,
         color="#0f766e", gato="studio_universal_ecuador",
         ec=r"^Canal\.Studio\.Universal\.", co=r"^Studio\.Universal\.co$"),
    dict(clave="tcm", nombre="TCM", grupo="Cine", cine=True,
         color="#b45309", gato="tcm_ecuador",
         ec=r"^Canal\.TCM\.", co=None),
    # AMC: gatotv no tiene la parrilla de Ecuador ("Canal no disponible") y la
    # de Colombia va 1 hora atrasada respecto a la senal real (comprobado el
    # 11/09/2026: "Veneno en la sangre" se veia a las 23:37 y la guia la ponia
    # a las 00:30). Por eso se le resta una hora.
    dict(clave="amc", nombre="AMC", grupo="Cine", cine=True,
         color="#334155", gato=None,
         ec=r"^Canal\.AMC\.", co=r"^AMC\.co$", desfase=-1),

    # ---- Canales con peliculas y series ---------------------------------
    dict(clave="tnt", nombre="TNT", grupo="Peliculas y series", cine=False,
         color="#dc2626", gato="tnt_ecuador",
         ec=r"^Canal\.TNT\.\(", co=r"^TNT\.co$"),
    dict(clave="axn", nombre="AXN", grupo="Peliculas y series", cine=False,
         color="#1d4ed8", gato="axn_ecuador",
         ec=r"^Canal\.AXN\.", co=r"^AXN\.co$"),
    dict(clave="space", nombre="Space", grupo="Peliculas y series", cine=False,
         color="#4338ca", gato="space_ecuador",
         ec=r"^Canal\.Space\.", co=r"^Space\.co$"),
    dict(clave="starchannel", nombre="Star Channel", grupo="Peliculas y series", cine=False,
         color="#0284c7", gato="star_channel_ecuador",
         ec=None, co=r"^STAR\.CHANNEL\.co$"),
    dict(clave="fx", nombre="FX", grupo="Peliculas y series", cine=False,
         color="#111827", gato="fx_ecuador",
         ec=r"^Canal\.FX\.", co=r"^FX\.co$"),
    dict(clave="warner", nombre="Warner TV", grupo="Peliculas y series", cine=False,
         color="#0369a1", gato="warner_tv_ecuador",
         ec=r"^Canal\.Warner\.TV\.", co=r"^Warner\.Channel\.co$"),
    dict(clave="sony", nombre="Sony", grupo="Peliculas y series", cine=False,
         color="#be123c", gato="sony_ecuador",
         ec=None, co=r"^Sony\.co$"),
    dict(clave="universal", nombre="Universal TV", grupo="Peliculas y series", cine=False,
         color="#065f46", gato="universal_tv_ecuador",
         ec=r"^Canal\.Universal\.TV\.", co=r"^Universal\.TV\.co$"),

    # ---- Mas cine (extras que tambien vienen en el cable) ----------------
    dict(clave="sonymovies", nombre="Sony Movies", grupo="Mas cine", cine=True,
         color="#9f1239", gato="sony_movies_ecuador", ec=None, co=None),
    dict(clave="fxm", nombre="FXM", grupo="Mas cine", cine=True,
         color="#374151", gato="fxm_ecuador", ec=None, co=None),
    dict(clave="cinelatino", nombre="Cinelatino", grupo="Mas cine", cine=True,
         color="#a16207", gato="cinelatino", ec=r"^Canal\.Cinelatino", co=None),
    dict(clave="depelicula", nombre="De Pelicula", grupo="Mas cine", cine=True,
         color="#7c2d12", gato="de_pelicula", ec=r"^Canal\.De\.Pel", co=None),
    dict(clave="multipremier", nombre="Multipremier", grupo="Mas cine", cine=True,
         color="#166534", gato="multipremier", ec=r"^Canal\.Multipremier", co=None),
    dict(clave="europaeuropa", nombre="Europa Europa", grupo="Mas cine", cine=True,
         color="#1e40af", gato="europa_europa", ec=r"^Canal\.Europa\.Europa", co=None),
    dict(clave="eurochannel", nombre="Eurochannel", grupo="Mas cine", cine=True,
         color="#155e75", gato="eurochannel", ec=r"^Canal\.Eurochannel", co=None),
]


# --------------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------------

def aviso(*partes):
    print(*partes, flush=True)


def bajar(url, intentos=3, espera=2.0, datos=None, cabeceras=None):
    """Descarga una URL y devuelve los bytes. Devuelve None si no se pudo."""
    cab = {"User-Agent": NAVEGADOR, "Accept-Language": "es-EC,es;q=0.9"}
    if cabeceras:
        cab.update(cabeceras)
    for intento in range(intentos):
        try:
            pedido = urllib.request.Request(url, data=datos, headers=cab)
            with urllib.request.urlopen(pedido, timeout=45) as r:
                return r.read()
        except Exception as e:
            if intento == intentos - 1:
                aviso(f"    ! no se pudo bajar {url[:90]} ({e})")
                return None
            time.sleep(espera * (intento + 1))
    return None


def sin_tildes(texto):
    texto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def clave_titulo(titulo):
    """Clave para comparar titulos ignorando tildes, signos y mayusculas."""
    return re.sub(r"[^a-z0-9]", "", sin_tildes(titulo))


def limpiar(texto):
    texto = html.unescape(texto or "")
    return re.sub(r"\s+", " ", texto).strip()


# --------------------------------------------------------------------------
# Fuente 1: gatotv.com
# --------------------------------------------------------------------------

FILA = re.compile(r'<tr class="tbl_EPG_row[^"]*">(.*?)</tr>', re.S)
HORA = re.compile(r'<time datetime="(\d{1,2}:\d{2})"')
COLUMNA = re.compile(r'<div class="tbl_EPG_ProgramsColumn ([a-z_]+)"', re.S)
TITULO = re.compile(r'<div class="div_program_title_on_channel">(.*?)</div>', re.S)
ETIQUETAS = re.compile(r"<[^>]+>")
FICHA = re.compile(r'href="https://www\.gatotv\.com/pelicula/([a-z0-9_\-]+)"')
FUERA = re.compile(r"tbl_EPG_TimesColumnOutOfSchedule")
EPISODIO = re.compile(r"div_episode_programa_on_channel")

# Textos de relleno que usa gatotv cuando no tiene la parrilla de un canal
RELLENO = re.compile(r"^(canal no disponible|se[nñ]al no disponible|sin programaci|"
                     r"programaci[oó]n no disponible|programa no disponible|no disponible|"
                     r"fin de (la )?transmisi|cierre de transmisi|infomercial|publicidad|"
                     r"contin[uú]a|sin t[ií]tulo|por confirmar)", re.I)


def leer_gatotv(slug, fecha):
    """Devuelve la parrilla de un canal para un dia. Lista de diccionarios."""
    url = f"https://www.gatotv.com/canal/{slug}/{fecha.isoformat()}"
    crudo = bajar(url, intentos=2, espera=1.5)
    if not crudo:
        return []
    pagina = crudo.decode("utf-8", errors="replace")

    programas = []
    desfase_dia = None
    hora_previa = None

    for contenido in FILA.findall(pagina):
        horas = HORA.findall(contenido)
        if len(horas) < 2:
            continue
        h_ini, h_fin = horas[0], horas[1]

        col = COLUMNA.search(contenido)
        tipo = col.group(1) if col else ""

        bloque = TITULO.search(contenido)
        if not bloque:
            continue
        titulo = limpiar(ETIQUETAS.sub(" ", bloque.group(1)))
        if not titulo or RELLENO.match(titulo):
            continue          # relleno: dejamos que lo cubra el XMLTV

        # Texto que sigue al titulo: puede traer "(Titulo original) sinopsis"
        resto = limpiar(ETIQUETAS.sub(" ", contenido[bloque.end():]))
        titulo_original, sinopsis = None, None
        m = re.match(r"\(([^)]{2,80})\)\s*(.*)", resto)
        if m:
            titulo_original = m.group(1).strip()
            sinopsis = m.group(2).strip() or None
        elif resto and not re.match(r"^Temporada|^Episodio", resto):
            sinopsis = resto

        ficha = FICHA.search(contenido)

        # Fecha real de inicio: la primera fila puede venir del dia anterior
        if desfase_dia is None:
            desfase_dia = -1 if FUERA.search(contenido) else 0
        elif hora_previa is not None and h_ini < hora_previa:
            desfase_dia += 1
        hora_previa = h_ini

        dia_ini = fecha + dt.timedelta(days=desfase_dia)
        hi, mi = (int(x) for x in h_ini.split(":"))
        hf, mf = (int(x) for x in h_fin.split(":"))
        inicio = dt.datetime.combine(dia_ini, dt.time(hi, mi), ECUADOR)
        fin = dt.datetime.combine(dia_ini, dt.time(hf, mf), ECUADOR)
        if fin <= inicio:
            fin += dt.timedelta(days=1)

        programas.append(dict(
            inicio=inicio, fin=fin, titulo=titulo,
            titulo_original=titulo_original, sinopsis=sinopsis,
            es_pelicula=(tipo == "pelicula"),
            tipo_crudo=tipo,
            episodio=bool(EPISODIO.search(contenido)),
            ficha=ficha.group(1) if ficha else None,
            fuente="gatotv",
        ))
    return programas


# --------------------------------------------------------------------------
# Fuente 2: archivos XMLTV de epgshare01.online
# --------------------------------------------------------------------------

SELLO = re.compile(r"(\d{14})\s*([+-]\d{4})?")


def a_hora_ecuador(sello):
    m = SELLO.match(sello or "")
    if not m:
        return None
    base = dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    desfase = m.group(2) or "+0000"
    signo = 1 if desfase[0] == "+" else -1
    zona = dt.timezone(signo * dt.timedelta(hours=int(desfase[1:3]),
                                            minutes=int(desfase[3:5])))
    return base.replace(tzinfo=zona).astimezone(ECUADOR)


def bajar_xmltv(pais):
    url = f"https://epgshare01.online/epgshare01/epg_ripper_{pais}.xml.gz"
    aviso(f"  bajando guia XMLTV de {pais} ...")
    crudo = bajar(url)
    if not crudo:
        return None
    try:
        return ET.parse(io.BytesIO(gzip.decompress(crudo))).getroot()
    except Exception as e:
        aviso(f"    ! no se pudo leer el XMLTV de {pais}: {e}")
        return None


def indexar_xmltv(raiz):
    """Agrupa los programas por identificador de canal."""
    if raiz is None:
        return {}
    por_canal = {}
    for p in raiz.findall("programme"):
        inicio = a_hora_ecuador(p.get("start"))
        fin = a_hora_ecuador(p.get("stop"))
        if not inicio or not fin:
            continue
        categorias = [limpiar(c.text) for c in p.findall("category") if c.text]
        nota = None
        estrella = p.find("star-rating")
        if estrella is not None:
            valor = estrella.findtext("value") or ""
            m = re.match(r"([\d.]+)", valor.strip())
            if m:
                try:
                    nota = float(m.group(1))
                except ValueError:
                    nota = None
        anio = None
        if p.findtext("date"):
            m = re.search(r"(19|20)\d{2}", p.findtext("date"))
            if m:
                anio = int(m.group(0))
        por_canal.setdefault(p.get("channel"), []).append(dict(
            inicio=inicio, fin=fin,
            titulo=limpiar(p.findtext("title")),
            titulo_original=limpiar(p.findtext("sub-title")) or None,
            sinopsis=limpiar(p.findtext("desc")) or None,
            categorias=categorias, anio=anio, nota=nota,
            es_pelicula=None, fuente="xmltv",
        ))
    return por_canal


def buscar_canal(indice, patron):
    """Encuentra el identificador de canal que cumple el patron."""
    if not patron:
        return None
    rx = re.compile(patron, re.I)
    for cid in indice:
        if rx.search(cid):
            return cid
    return None


# --------------------------------------------------------------------------
# Decidir que es pelicula
# --------------------------------------------------------------------------

PISTA_SERIE = re.compile(
    r"\b(temporada|episodio|cap[ií]tulo|serie|noticias|noticiero|deporte|"
    r"f[uú]tbol|magazine|informativo|entrevista|reality|talk\s?show)\b", re.I)
PISTA_PELICULA = re.compile(r"pel[ií]cula|cine|film|largometraje", re.I)

# Bloques de programacion que duran como una pelicula pero no lo son
BLOQUE = re.compile(r"series block|bloque|marat[oó]n|back to back|programaci[oó]n|"
                    r"especial de series|lo mejor de", re.I)


def clasificar(programa, canal):
    """
    Decide si un programa es pelicula. Devuelve:
      "si"     -> es pelicula, seguro
      "quiza"  -> parece pelicula; lo confirmaremos consultando TMDB
      "no"     -> no es pelicula
    """
    minutos = int((programa["fin"] - programa["inicio"]).total_seconds() // 60)

    # Texto de relleno de la fuente ("Canal no disponible", "Sin programacion")
    if RELLENO.match(programa["titulo"] or ""):
        return "no"

    # Nada demasiado corto ni demasiado largo (los bloques largos suelen ser
    # maratones de series o rellenos del canal)
    if minutos < MINUTOS_MINIMOS or minutos > 300:
        return "no"

    # --- Programas que vienen de gatotv: la pagina ya los etiqueta --------
    if programa.get("es_pelicula") is not None:
        if programa.get("episodio"):
            return "no"                       # trae "Temporada X | Episodio Y"
        if programa["es_pelicula"]:
            return "si"
        if programa.get("tipo_crudo") in ("documental", "deporte", "noticias"):
            return "no"
        if PISTA_SERIE.search(programa["titulo"]) or BLOQUE.search(programa["titulo"]):
            return "no"
        # gatotv marca como "programa" muchas peliculas de verdad: pasa en TNT,
        # Space y FX (Jumanji, La Mascara, Plan de Escape...). Si dura como
        # pelicula, no trae marca de episodio y no es un bloque de series,
        # la damos por buena aunque TMDB no la encuentre.
        return "si" if minutos >= 80 else "no"

    # --- Programas que vienen del XMLTV ----------------------------------
    categorias = " ".join(programa.get("categorias") or [])
    if PISTA_PELICULA.search(categorias):
        return "si"
    if PISTA_SERIE.search(categorias) or PISTA_SERIE.search(programa["titulo"]):
        return "no"
    if canal["cine"]:
        return "si"
    if minutos >= 80 and programa.get("anio"):
        return "si"
    return "quiza" if minutos >= 80 else "no"


# --------------------------------------------------------------------------
# TMDB: sinopsis, anio, puntuacion y poster
# --------------------------------------------------------------------------

def leer_clave_tmdb():
    clave = (os.environ.get("TMDB_API_KEY") or "").strip()
    if clave:
        return clave
    local = os.path.join(AQUI, "clave-tmdb.txt")
    if os.path.exists(local):
        with open(local, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def pedir_tmdb(ruta, parametros, clave, intentos=2):
    """
    Llama a TMDB. Acepta los dos tipos de credencial:
      - clave v3 (texto corto)      -> va en la direccion como api_key
      - token v4 (empieza con eyJ)  -> va en la cabecera Authorization
    """
    parametros = dict(parametros or {})
    cabeceras = None
    if clave.startswith("eyJ"):
        cabeceras = {"Authorization": "Bearer " + clave,
                     "Accept": "application/json"}
    else:
        parametros["api_key"] = clave
    url = (f"https://api.themoviedb.org/3/{ruta}?"
           + urllib.parse.urlencode(parametros))
    crudo = bajar(url, intentos=intentos, espera=1.0, cabeceras=cabeceras)
    if not crudo:
        return None
    try:
        return json.loads(crudo)
    except Exception:
        return None


def generos_tmdb(clave):
    datos = pedir_tmdb("genre/movie/list", {"language": "es-MX"}, clave)
    if not datos:
        return {}
    return {g["id"]: g["name"] for g in datos.get("genres", [])}


def buscar_en_tmdb(texto, anio, clave):
    """Una busqueda en TMDB. Devuelve la lista de resultados."""
    partes = {"query": texto, "language": "es-MX", "include_adult": "false"}
    if anio:
        partes["year"] = str(anio)
    datos = pedir_tmdb("search/movie", partes, clave)
    resultados = (datos or {}).get("results", [])
    if not resultados and anio:
        # Reintento sin el ano, por si el ano que trae el canal esta mal
        partes.pop("year")
        datos = pedir_tmdb("search/movie", partes, clave)
        resultados = (datos or {}).get("results", [])
    return resultados


def consultar_tmdb(titulo, anio, clave, mapa_generos, titulo_original=None):
    """
    Busca la pelicula en TMDB. Devuelve la ficha o None.
    Prueba primero con el titulo en espanol y, si falla, con el titulo
    original: TMDB no tiene indexados todos los titulos latinos, pero si
    los originales.
    """
    resultados = buscar_en_tmdb(titulo, anio, clave)
    objetivo = clave_titulo(titulo)

    if not resultados and titulo_original:
        resultados = buscar_en_tmdb(titulo_original, anio, clave)
        objetivo = clave_titulo(titulo_original)

    if not resultados and ":" in titulo:
        # "Pelicula: subtitulo" -> probamos solo con la primera parte
        corto = titulo.split(":")[0].strip()
        if len(corto) >= 4:
            resultados = buscar_en_tmdb(corto, anio, clave)
            objetivo = clave_titulo(corto)

    if not resultados:
        return None
    mejor, mejor_puntos = None, -1
    for r in resultados[:8]:
        anio_r = None
        if r.get("release_date"):
            m = re.match(r"(\d{4})", r["release_date"])
            if m:
                anio_r = int(m.group(1))
        puntos = 0
        if anio and anio_r:
            if anio_r == anio:
                puntos += 100
            elif abs(anio_r - anio) == 1:
                puntos += 60
            else:
                puntos -= 40
        titulos = {clave_titulo(r.get("title")), clave_titulo(r.get("original_title"))}
        if objetivo in titulos:
            puntos += 50
        elif any(objetivo and objetivo in t for t in titulos if t):
            puntos += 20
        puntos += min(r.get("vote_count", 0), 2000) / 200.0
        if puntos > mejor_puntos:
            mejor, mejor_puntos = r, puntos

    if mejor is None:
        return None

    anio_m = None
    if mejor.get("release_date"):
        m = re.match(r"(\d{4})", mejor["release_date"])
        if m:
            anio_m = int(m.group(1))

    # Solo damos la ficha por buena si el ano cuadra, o si el titulo coincide
    # exacto y la pelicula tiene votos suficientes. Preferimos quedarnos sin
    # ficha antes que mostrar la pelicula equivocada.
    titulo_exacto = objetivo in {clave_titulo(mejor.get("title")),
                                 clave_titulo(mejor.get("original_title"))}
    if anio and anio_m:
        confiable = abs(anio_m - anio) <= 1
    else:
        confiable = titulo_exacto and mejor.get("vote_count", 0) >= 30
    if not confiable:
        return None

    return dict(
        tmdb_id=mejor.get("id"),
        titulo_tmdb=mejor.get("title"),
        titulo_original=mejor.get("original_title"),
        anio=anio_m,
        sinopsis=(mejor.get("overview") or "").strip() or None,
        puntuacion=round(mejor.get("vote_average") or 0, 1) or None,
        votos=mejor.get("vote_count") or 0,
        poster=(f"https://image.tmdb.org/t/p/w342{mejor['poster_path']}"
                if mejor.get("poster_path") else None),
        generos=[mapa_generos.get(g) for g in (mejor.get("genre_ids") or [])
                 if mapa_generos.get(g)],
    )


FICHA_ANIO = re.compile(r'itemprop="copyrightYear"[^>]*>\s*(?:<[^>]+>\s*)*((?:19|20)\d{2})')
FICHA_NOTA = re.compile(r'itemprop="ratingValue"[^>]*content="([\d.]+)"')
FICHA_DESC = re.compile(r'itemprop="(?:description|summary)"[^>]*>(.*?)</', re.S)
FICHA_GENERO = re.compile(r'itemprop="genre"[^>]*>([^<]{2,30})<')
FICHA_IMG = re.compile(r'(https://imagenes\.gatotv\.com/categorias/peliculas/'
                       r'(?:poster|miniatura)/[a-z0-9_\-]+\.jpg)')


def ficha_gatotv(slug):
    """
    Respaldo cuando TMDB no encuentra la pelicula: la propia ficha de
    gatotv trae ano, puntuacion, sinopsis y generos.
    """
    crudo = bajar(f"https://www.gatotv.com/pelicula/{slug}", intentos=2, espera=1.0)
    if not crudo:
        return None
    pagina = crudo.decode("utf-8", errors="replace")

    anio = FICHA_ANIO.search(pagina)
    nota = FICHA_NOTA.search(pagina)
    desc = FICHA_DESC.search(pagina)
    img = FICHA_IMG.search(pagina)
    generos = [limpiar(g) for g in FICHA_GENERO.findall(pagina)[:3]]

    sinopsis = limpiar(ETIQUETAS.sub(" ", desc.group(1))) if desc else None
    if not (anio or nota or sinopsis):
        return None

    return dict(
        tmdb_id=None,
        titulo_tmdb=None,
        titulo_original=None,
        anio=int(anio.group(1)) if anio else None,
        sinopsis=sinopsis,
        puntuacion=round(float(nota.group(1)), 1) if nota else None,
        votos=None,
        poster=img.group(1) if img else None,
        generos=[g for g in generos if g],
        origen="gatotv",
    )


# --------------------------------------------------------------------------
# Construccion de la guia
# --------------------------------------------------------------------------

def cargar_json(ruta, por_defecto):
    if not os.path.exists(ruta):
        return por_defecto
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return por_defecto


def guardar_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, separators=(",", ":"))


def main():
    ahora = dt.datetime.now(ECUADOR)
    hoy = ahora.date()
    fechas = [hoy + dt.timedelta(days=i) for i in range(DIAS_ADELANTE)]

    aviso("=" * 62)
    aviso(f"Armando la guia de peliculas — {ahora:%d/%m/%Y %H:%M} (Ecuador)")
    aviso("=" * 62)

    # ---- 1. Archivos XMLTV -------------------------------------------
    indice_ec = indexar_xmltv(bajar_xmltv("EC1"))
    indice_co = indexar_xmltv(bajar_xmltv("CO1"))
    aviso(f"  XMLTV listo: {len(indice_ec)} canales de Ecuador, "
          f"{len(indice_co)} de Colombia")

    # ---- 2. Recorrer canales -----------------------------------------
    crudos = []          # (canal, programa)
    for canal in CANALES:
        encontrados = 0

        # 2a. gatotv, dia por dia (trae la marca exacta de pelicula)
        dias_con_datos = set()
        if canal["gato"]:
            for fecha in fechas:
                programas = leer_gatotv(canal["gato"], fecha)
                if programas:
                    dias_con_datos.add(fecha)
                for p in programas:
                    if p["inicio"].date() in fechas:
                        crudos.append((canal, p))
                        encontrados += 1
                time.sleep(0.25)      # cortesia con el servidor

        # 2b. XMLTV para los dias que gatotv no cubrio
        for etiqueta, indice, patron in (("EC", indice_ec, canal["ec"]),
                                         ("CO", indice_co, canal["co"])):
            cid = buscar_canal(indice, patron)
            if not cid:
                continue
            dias_utiles = set()
            for p in indice[cid]:
                dia = p["inicio"].date()
                if dia not in fechas or dia in dias_con_datos:
                    continue
                # El relleno ("Canal no disponible") no cuenta como dato: si
                # lo dejaramos pasar, taparia la otra fuente, que si sirve.
                if RELLENO.match(p["titulo"] or ""):
                    continue
                crudos.append((canal, dict(p)))
                dias_utiles.add(dia)
                encontrados += 1
            if canal["gato"] is None:
                # Canal sin gatotv: con la primera fuente que dio datos basta
                dias_con_datos |= dias_utiles

        aviso(f"  {canal['nombre']:<18} {encontrados:>4} programas")

    # ---- 3. Quedarnos solo con las peliculas --------------------------
    peliculas, vistos = [], set()
    dudosas = 0
    for canal, p in crudos:
        veredicto = clasificar(p, canal)
        if veredicto == "no":
            continue
        if veredicto == "quiza":
            dudosas += 1

        # Correccion de horario para los canales cuya senal en Ecuador va
        # adelantada o atrasada respecto a la guia publicada
        if canal.get("desfase"):
            ajuste = dt.timedelta(hours=canal["desfase"])
            p = dict(p, inicio=p["inicio"] + ajuste, fin=p["fin"] + ajuste)
        llave = (canal["clave"], p["inicio"].isoformat(), clave_titulo(p["titulo"]))
        if llave in vistos:
            continue
        vistos.add(llave)
        minutos = int((p["fin"] - p["inicio"]).total_seconds() // 60)
        peliculas.append(dict(
            canal=canal["clave"],
            dia=p["inicio"].date().isoformat(),
            inicio=p["inicio"].strftime("%H:%M"),
            fin=p["fin"].strftime("%H:%M"),
            inicio_iso=p["inicio"].isoformat(),
            fin_iso=p["fin"].isoformat(),
            minutos=minutos,
            titulo=p["titulo"],
            titulo_original=p.get("titulo_original"),
            sinopsis=p.get("sinopsis"),
            anio=p.get("anio"),
            puntuacion=p.get("nota"),
            fuente=p.get("fuente"),
            ficha_slug=p.get("ficha"),
            dudosa=(veredicto == "quiza"),
        ))

    peliculas.sort(key=lambda x: (x["dia"], x["inicio"], x["canal"]))
    aviso(f"\n  Candidatas: {len(peliculas)} "
          f"({dudosas} por confirmar con TMDB)")

    # ---- 4. Enriquecer con TMDB ---------------------------------------
    def llave_ficha(pel):
        return "|".join([clave_titulo(pel["titulo"]),
                         clave_titulo(pel.get("titulo_original") or ""),
                         str(pel.get("anio") or "")])

    clave = leer_clave_tmdb()
    cache = cargar_json(ARCHIVO_CACHE, {})
    mapa_generos = generos_tmdb(clave) if clave else {}

    # Una sola entrada por pelicula distinta, aunque se repita en la semana
    titulos = {}
    for pel in peliculas:
        titulos.setdefault(llave_ficha(pel), pel)

    pendientes = [k for k in titulos if k not in cache]
    aviso(f"  Fichas: {len(titulos)} peliculas distintas, "
          f"{len(cache)} ya guardadas, {len(pendientes)} por buscar")

    if not clave:
        aviso("  ! Sin clave de TMDB: se usara solo la ficha de gatotv.")

    de_tmdb, de_gato, sin_nada = 0, 0, 0
    for k in pendientes:
        pel = titulos[k]
        ficha = None
        if clave:
            ficha = consultar_tmdb(pel["titulo"], pel.get("anio"), clave,
                                   mapa_generos, pel.get("titulo_original"))
            if ficha:
                ficha["origen"] = "tmdb"
                de_tmdb += 1
            time.sleep(0.06)
        # Respaldo: la ficha del propio gatotv
        if not ficha and pel.get("ficha_slug"):
            ficha = ficha_gatotv(pel["ficha_slug"])
            if ficha:
                de_gato += 1
            time.sleep(0.15)
        if not ficha:
            sin_nada += 1
        cache[k] = ficha               # guardamos incluso los fallos (None)

    aviso(f"  Resultado: {de_tmdb} de TMDB, {de_gato} de gatotv, "
          f"{sin_nada} sin ficha")
    guardar_json(ARCHIVO_CACHE, cache)

    for pel in peliculas:
        ficha = cache.get(llave_ficha(pel))
        if not ficha:
            pel["ficha"] = False
            continue
        pel["ficha"] = True
        pel["anio"] = ficha.get("anio") or pel.get("anio")
        pel["puntuacion"] = ficha.get("puntuacion") or pel.get("puntuacion")
        pel["votos"] = ficha.get("votos")
        pel["poster"] = ficha.get("poster")
        pel["generos"] = ficha.get("generos") or []
        pel["titulo_original"] = ficha.get("titulo_original") or pel.get("titulo_original")
        if ficha.get("sinopsis"):
            pel["sinopsis"] = ficha["sinopsis"]
        pel["origen_ficha"] = ficha.get("origen")

    # Las dudosas solo se quedan si TMDB confirmo que existe la pelicula.
    # Preferimos perder alguna antes que colar una serie en la cartelera.
    antes = len(peliculas)
    peliculas = [p for p in peliculas if not (p.get("dudosa") and not p.get("ficha"))]
    confirmadas = sum(1 for p in peliculas if p.get("dudosa"))
    for p in peliculas:
        p.pop("dudosa", None)
    aviso(f"  Dudosas: {confirmadas} confirmadas, {antes - len(peliculas)} descartadas")

    # ---- 5. Unir con lo que ya teniamos (para no perder dias) ----------
    # Solo conservamos de la guia anterior los dias/canales que esta vez no
    # trajeron nada (por ejemplo, dias que la fuente ya dejo de publicar).
    # Donde si hay datos nuevos, mandan los nuevos: asi las correcciones
    # borran de verdad lo que estaba mal.
    frescos = {(pel["canal"], pel["dia"]) for pel in peliculas}
    anterior = cargar_json(ARCHIVO_GUIA, {})
    guardadas, rescatadas = {}, 0
    for pel in anterior.get("peliculas", []):
        if pel.get("dia", "") < hoy.isoformat():
            continue
        if (pel["canal"], pel["dia"]) in frescos:
            continue
        guardadas[(pel["canal"], pel["dia"], pel["inicio"])] = pel
        rescatadas += 1
    for pel in peliculas:
        guardadas[(pel["canal"], pel["dia"], pel["inicio"])] = pel
    if rescatadas:
        aviso(f"  Conservadas de la guia anterior: {rescatadas}")

    finales = sorted(guardadas.values(), key=lambda x: (x["dia"], x["inicio"], x["canal"]))
    dias = sorted({p["dia"] for p in finales})

    # Canales que realmente tienen algo
    con_datos = {p["canal"] for p in finales}
    catalogo = [dict(clave=c["clave"], nombre=c["nombre"], grupo=c["grupo"],
                     color=c["color"], cine=c["cine"])
                for c in CANALES if c["clave"] in con_datos]

    guia = dict(
        generado=ahora.isoformat(),
        generado_texto=f"{ahora:%d/%m/%Y a las %H:%M}",
        zona="America/Guayaquil (UTC-5)",
        dias=dias,
        canales=catalogo,
        peliculas=finales,
        total=len(finales),
    )
    guardar_json(ARCHIVO_GUIA, guia)

    aviso("\n" + "=" * 62)
    aviso(f"  Guia guardada: {len(finales)} peliculas, {len(dias)} dias, "
          f"{len(catalogo)} canales")
    aviso(f"  Dias cubiertos: {', '.join(dias)}")
    aviso(f"  Archivo: {ARCHIVO_GUIA}")
    aviso("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
