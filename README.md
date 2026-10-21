# TikTok Scraper (proyecto educativo)

Programa en **Python + Playwright** que extrae los datos públicos de una cuenta
de TikTok y los guarda en archivos **JSON** y **CSV**.

---

## Índice

1. [Objetivo](#1-objetivo)
2. [Datos que obtiene](#2-datos-que-obtiene)
3. [Herramienta elegida y por qué](#3-herramienta-elegida-y-por-qué)
4. [Estructura del proyecto](#4-estructura-del-proyecto)
5. [Instalación](#5-instalación)
6. [Uso](#6-uso)
7. [Resultados que genera](#7-resultados-que-genera)
8. [Cómo funciona por dentro](#8-cómo-funciona-por-dentro)
9. [Explicación de cada archivo](#9-explicación-de-cada-archivo)
10. [Limitaciones](#10-limitaciones)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Aviso legal y ético](#12-aviso-legal-y-ético)
13. [Mejoras posibles](#14-mejoras-posibles)


---

## 1. Objetivo

Dada una cuenta pública de TikTok, el programa abre la página con un navegador
real, recorre el perfil y los últimos videos, y entrega toda la información en
archivos que se pueden abrir con Excel o analizar con otros programas.

---

## 2. Datos que obtiene

| Dato | ¿Se obtiene? | Observación |
|---|---|---|
| Username | Sí | |
| Nombre (name) | Sí | Nombre visible del perfil |
| Biografía | Sí | |
| Número de seguidores | Sí | |
| Número de seguidos | Sí | |
| Likes totales y cantidad de videos | Sí | Datos extra del perfil |
| Últimos 10 TikToks | Sí | Enlace, descripción, fecha, duración |
| Vistas, likes, comentarios y compartidos de cada video | Sí | Se leen de la página de cada video |
| Comentarios de cada video | Parcial | Depende de lo que TikTok cargue (ver sección 10) |
| **Notificaciones** | **No** | Son privadas (ver sección 10) |

---

## 3. Herramienta elegida y por qué

TikTok construye la página con **JavaScript**: el HTML inicial casi no trae
datos y estos aparecen después. Por eso se necesita un navegador real.

| Herramienta | Decisión | Motivo |
|---|---|---|
| **Playwright** | **Elegida** | Controla un navegador real, espera a que cargue el contenido, hace scroll y puede leer las respuestas de red que recibe la página. |
| Selenium | Descartada | Funciona, pero es más lenta y más fácil de detectar. |
| Puppeteer | Descartada | Es equivalente, pero solo funciona con Node.js; este proyecto está en Python. |
| Scrapy | Descartada | No ejecuta JavaScript, recibiría la página casi vacía. |
| Requests | Descartada | Solo descarga HTML, sin el contenido dinámico. |
| BeautifulSoup | Descartada | Solo analiza HTML ya descargado; no abre páginas por sí sola. |

---

## 4. Estructura del proyecto

```
tiktok-scraper/
├── main.py            # Punto de entrada: recibe argumentos, guarda resultados, muestra resumen
├── scraper.py         # Lógica del scraping con Playwright
├── models.py          # Estructura de los datos (Profile, Video, Comment)
├── requirements.txt   # Dependencias (solo playwright)
├── README.md          # Este documento
└── data/              # Resultados, capturas de depuración y perfil del navegador (browser_profile)
```

---

## 5. Instalación

Requisito: **Python 3.9 o superior** y tener **Chrome o Edge** instalado.

```bash
# 1) Instalar la dependencia
python -m pip install -r requirements.txt
```

**No es obligatorio** ejecutar `playwright install chromium`. El programa
intenta usar primero Chrome, luego Edge (ya instalados en el equipo) y, solo si
no encuentra ninguno, el Chromium de Playwright. Si necesitas ese Chromium:

```bash
python -m playwright install chromium
```

> Se usa `python -m pip` en lugar de `pip` para asegurar que se instala en la
> misma versión de Python con la que se ejecutará el programa.

Opcional: entorno virtual.

```bash
python -m venv venv
venv\Scripts\activate           # Windows
source venv/bin/activate        # Linux / macOS
```

---

## 6. Uso

```bash
python main.py usuario
python main.py usuario --videos 10 --comments 20
```

Escribe el usuario **sin** el `@`.

| Opción | Descripción | Por defecto |
|---|---|---|
| `usuario` | Usuario de TikTok (con o sin @) | obligatorio |
| `--videos` | Cantidad de videos a extraer | 10 |
| `--comments` | Comentarios máximos por video | 20 |
| `--headless` | Ejecutar sin ventana visible | desactivado |
| `--out` | Carpeta de salida | `data` |

**Recomendaciones al ejecutar**

- **No uses `--headless`.** Con la ventana visible TikTok bloquea menos y puedes
  resolver un captcha o cerrar un login a mano.
- **No cierres la ventana** del navegador hasta que el programa termine.
- Tarda entre **4 y 6 minutos** con 10 videos, por las pausas entre acciones.
- Si aparece un captcha, el programa espera hasta 60 segundos para que lo
  resuelvas.

---

## 7. Resultados que genera

Para el usuario `ejemplo` se crea la carpeta `data/ejemplo/` con:

| Archivo | Contenido |
|---|---|
| `profile.json` | Todo junto: perfil + videos + comentarios + notas |
| `videos.csv` | Una fila por video (abre bien en Excel) |
| `comments.csv` | Una fila por comentario; la columna `video_id` lo relaciona con su video |

Al terminar, el programa imprime un resumen en pantalla:

```
=== RESUMEN ===
Usuario:     @ejemplo
Nombre:      Cuenta Ejemplo
Biografía:   Texto de la biografía
Seguidores:  12500
Seguidos:    150
Likes total: 340000
Videos extraídos: 10
   1. vistas=50000 likes=3200 comentarios_total=120 extraídos=20 | Mi primer video
   ...
Comentarios extraídos: 187
[nota] Las notificaciones son privadas y requieren sesión: ...
```

Ejemplo simplificado de `profile.json`:

```json
{
  "username": "ejemplo",
  "name": "Cuenta Ejemplo",
  "bio": "Texto de la biografía",
  "followers": 12500,
  "following": 150,
  "likes_total": 340000,
  "notifications": null,
  "videos": [
    {
      "id": "7300000000000000000",
      "url": "https://www.tiktok.com/@ejemplo/video/7300000000000000000",
      "description": "Mi primer video",
      "created_at": "2026-10-01T15:30:00+00:00",
      "views": 50000,
      "likes": 3200,
      "comments_count": 120,
      "shares": 45,
      "comments": [
        { "author": "usuario1", "text": "¡Genial!", "likes": 4 }
      ]
    }
  ],
  "notes": ["Las notificaciones son privadas..."]
}
```

El campo `notes` registra todo lo que no se pudo obtener o se obtuvo de forma
aproximada. Así los resultados son honestos y fáciles de explicar.

---

## 8. Cómo funciona por dentro

El programa sigue estos pasos (lo hace `scraper.py`):

```
Abrir navegador ─► Abrir perfil ─► Leer perfil ─► Cargar videos
                                                       │
        Guardar JSON / CSV ◄─ Abrir cada video ◄───────┘
                              (datos + comentarios)
```

**Paso 1. Abrir el navegador.** Playwright lanza Chrome o Edge con un
user-agent y un tamaño de pantalla normales, y oculta la señal de "navegador
automatizado".

**Paso 2. Leer el perfil.** TikTok incrusta un JSON en la página
(`#__UNIVERSAL_DATA_FOR_REHYDRATION__`). De ahí salen el username, nombre,
biografía, seguidores, seguidos y likes totales. Si el programa no encuentra el
perfil, espera hasta 60 segundos para que resuelvas un captcha o cierres un
login.

**Paso 3. Cargar los videos.** Se espera la cuadrícula de videos y se hace
scroll. Si TikTok muestra un error, el programa pulsa "actualizar" o recarga la
página (hasta 3 intentos). Los videos se obtienen por dos vías:

1. Escuchando la respuesta de red `/api/post/item_list` que la página pide al
   cargar.
2. Si no llega, leyendo los enlaces `/video/<id>` de la cuadrícula.

Como TikTok muestra primero los videos **fijados**, la lista se ordena por fecha
para quedarse con los más recientes.

**Paso 4. Abrir cada video.** Se entra a la página de cada video y se lee su
JSON incrustado (`webapp.video-detail`): vistas, likes, comentarios,
compartidos, fecha y descripción. Luego se hace scroll en la zona de comentarios
y se capturan las respuestas de red `/api/comment/list`.

**Paso 5. Guardar.** Todo se escribe en `profile.json`, `videos.csv` y
`comments.csv`.

### Sistema de "planes" (respaldo)

Si una fuente falla, el programa usa la siguiente. Así no se queda sin datos
por un cambio pequeño en la página.

| Dato | Plan A (más fiable) | Plan B |
|---|---|---|
| Perfil | JSON incrustado en la página | Selectores HTML (`data-e2e`) |
| Lista de videos | Respuesta de red `item_list` | Enlaces de la cuadrícula |
| Datos del video | JSON incrustado de la página del video | Contadores visibles en pantalla |
| Comentarios | Respuesta de red `comment/list` | Leer los comentarios del HTML |

### Otras decisiones de diseño

- **Pausas aleatorias** entre acciones: evitan saturar el servidor y reducen el
  riesgo de bloqueo.
- **Números aproximados:** cuando un dato viene del HTML llega como `1.2M`. El
  programa lo convierte a número (`1200000`) y lo anota en `notes`.
- **Perfil de navegador persistente:** el programa usa su propio perfil de Chrome/Edge en
  `data/browser_profile`. Así un captcha resuelto o un login se recuerdan en la
  siguiente ejecución. Esa carpeta contiene cookies: **no la compartas** y bórrala
  cuando termines.
- **Captura de depuración:** si el perfil o los videos no cargan, se guarda una
  imagen y el HTML en `data/debug/` para ver qué mostró TikTok realmente.

---

## 9. Explicación de cada archivo

### `models.py`: ¿qué datos guardamos?
Define tres clases con `dataclass`: `Profile` (cuenta), `Video` y `Comment`.
Una dataclass es una clase que solo guarda datos y se convierte fácil a
diccionario (y de ahí a JSON) con `asdict`. Un `Profile` contiene una lista de
`Video` y cada `Video` una lista de `Comment`.

### `scraper.py`: ¿cómo se obtienen?
Contiene la clase `TikTokScraper`. Funciones principales:

| Función | Qué hace |
|---|---|
| `_launch_browser` | Abre Chrome, Edge o Chromium (en ese orden) |
| `_wait_for_profile` | Espera y lee el perfil; permite resolver captcha a mano |
| `_profile_from_json` / `_profile_from_dom` | Perfil por plan A / plan B |
| `_load_grid` | Espera la cuadrícula de videos y reintenta si falla |
| `_videos_from_grid` | Plan B para la lista de videos |
| `_video_detail_from_json` / `_from_dom` | Vistas, likes y demás datos del video |
| `_scrape_video` | Abre un video, completa sus datos y extrae comentarios |
| `scrape_profile` | Función principal que coordina todo |

El uso `with TikTokScraper(...) as scraper:` abre el navegador al entrar y lo
cierra solo al salir, aunque ocurra un error.

### `main.py`: ¿cómo se usa?
Lee los argumentos de la consola (`argparse`), llama al scraper, guarda los
archivos JSON y CSV y muestra el resumen.

---

## 10. Limitaciones

- **Notificaciones: no se pueden obtener.** Son privadas, pertenecen a una
  sesión iniciada y TikTok no las muestra en perfiles públicos. El campo
  `notifications` queda en `null` y se anota en `notes`. Para tus propios datos,
  TikTok ofrece la descarga oficial: *Ajustes y privacidad → Cuenta → Descargar
  tus datos*.
- **Comentarios parciales.** TikTok limita cuántos carga y a veces pide iniciar
  sesión. Algunos videos pueden salir con pocos o cero comentarios.
- **Cuentas privadas:** no se puede ver su contenido.
- **Captcha y bloqueos.** TikTok protege sus páginas contra programas
  automatizados y puede pedir verificación o bloquear temporalmente.
- **El sitio cambia.** Si TikTok modifica su estructura, los selectores o el
  JSON pueden dejar de funcionar y habrá que actualizar `scraper.py`.
- **Cifras aproximadas** cuando se leen del HTML (`1.2M`).

---

## 11. Solución de problemas

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `Fatal error in launcher` al usar `pip` | Hay Python movido o reinstalado | Usar `python -m pip install -r requirements.txt` |
| `playwright install` falla con `ECONNRESET` | Red, antivirus, VPN o proxy | No hace falta: el programa usa Chrome/Edge instalados. O probar otra red |
| `No se encontró Chrome, Edge ni Chromium` | No hay navegador compatible | Instalar Chrome o ejecutar `python -m playwright install chromium` |
| Todo sale `None` y 0 videos | Usuario inexistente o privado, o bloqueo | Verificar el usuario en el navegador; ver `data/debug/*.png` |
| Perfil sale pero 0 videos | La cuadrícula no cargó | Ejecutar sin `--headless`, resolver captcha, revisar `data/debug/videos_*.png` |
| Mensaje "Captcha VISIBLE" y 0 videos | TikTok pide verificación | Resolverlo a mano en la ventana (hasta 120 s) y volver a ejecutar: el perfil guardado recuerda la verificación |
| Videos sin comentarios | TikTok no los cargó o pide login | Es una limitación conocida; queda anotada en el resumen |
| `AttributeError` por un método inexistente | Error de sangría al editar el código | Revisar que los `def` estén con 4 espacios dentro de la clase |

---

## 12. Aviso legal y ético

- Los términos de uso de TikTok restringen el scraping automatizado.
- Usa este proyecto **solo con fines educativos**, con **cuentas públicas** y
  con pocas peticiones.
- Prefiere cuentas propias, de marcas o de figuras públicas.
- Los perfiles y comentarios son **datos de personas reales**: no los
  publiques, no los vendas y no los uses para acosar o identificar a nadie.
- Los datos se guardan solo en tu computador.

---
## 13. Mejoras posibles

- Iniciar sesión con una cuenta propia para obtener más comentarios.
- Descargar también los archivos de video.
- Guardar los datos en una base de datos (SQLite).
- Analizar los datos con pandas (por ejemplo, el video con más likes).
- Procesar varias cuentas desde un archivo de texto.
