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
10. [Análisis Big Five (extensión)](#10-análisis-big-five-extensión)
11. [Producto: Afinador de voz de marca](#11-producto-afinador-de-voz-de-marca)
12. [Limitaciones](#12-limitaciones)
13. [Solución de problemas](#13-solución-de-problemas)
14. [Aviso legal y ético](#14-aviso-legal-y-ético)
15. [Guía rápida para la exposición](#15-guía-rápida-para-la-exposición)
16. [Mejoras posibles](#16-mejoras-posibles)

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
| Comentarios de cada video | Parcial | Depende de lo que TikTok cargue (ver sección 12) |
| **Notificaciones** | **No** | Son privadas (ver sección 12) |

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
├── report.py          # Genera el reporte visual reporte.html
├── personality.py     # Motor Big Five con la API gratuita de Gemini (+ porcentajes que suman 100)
├── brand_voice.py     # Lógica de negocio del producto "Afinador de voz de marca"
├── app.py             # Interfaz web del producto (Streamlit)
├── test_brand_voice.py# Pruebas automáticas de la lógica
├── .env.example       # Ejemplo para guardar la clave (la real va en .env, NO se sube)
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
| `--bigfive` | Estimar el perfil Big Five (necesita clave de Gemini, ver sección 10) | desactivado |
| `--no-report` | No generar ni abrir el reporte visual | desactivado |

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
| `reporte.html` | **Reporte visual**: perfil, estadísticas, gráfico de vistas y detalle de cada video con sus comentarios |

### Reporte visual

Al terminar, el programa genera `reporte.html` y lo abre en el navegador. También
puedes generarlo **sin volver a hacer scraping** a partir de un `profile.json` ya guardado:

```bash
python report.py data/usuario/profile.json
```

Para no generarlo automáticamente usa `--no-report`.

### Resumen en pantalla

Al terminar, el programa imprime un resumen en la consola:

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
archivos JSON y CSV, muestra el resumen y genera el reporte visual.

### `personality.py`: ¿cómo se estima la personalidad?
Toma la biografía y las descripciones de los videos, las envía a la API de Gemini con un
prompt que pide el Big Five en formato JSON, valida la respuesta (puntajes de 0 a 100) y la
guarda en `profile.json` dentro del campo `personality`. Ver sección 10.

### `report.py`: ¿cómo se muestra?
Convierte el `profile.json` en una página HTML autocontenida (sin librerías
externas): tarjetas de estadísticas, gráfico de barras con las vistas de cada
video y la lista de videos con sus comentarios desplegables. Todo el texto se
escapa (`html.escape`) para que un comentario con símbolos no rompa la página.

---

## 10. Análisis Big Five (extensión)

### ¿Qué es el Big Five?
Es el modelo de personalidad más usado en psicología. Describe a una persona con cinco rasgos
(sigla **OCEAN**), cada uno en una escala de bajo a alto:

| Rasgo | Alto significa… | Bajo significa… |
|---|---|---|
| **O**penness (Apertura a la experiencia) | Curiosidad, creatividad, gusto por lo nuevo | Preferencia por lo conocido y lo práctico |
| **C**onscientiousness (Responsabilidad) | Orden, disciplina, constancia | Espontaneidad, flexibilidad |
| **E**xtraversion (Extraversión) | Sociabilidad, energía, expresividad | Reserva, preferencia por la calma |
| **A**greeableness (Amabilidad) | Empatía, cooperación, confianza | Competitividad, escepticismo |
| **N**euroticism (Neuroticismo) | Más sensibilidad al estrés y emociones negativas | Estabilidad emocional |

### ¿Qué textos se analizan?
La **biografía** y las **descripciones de los videos** de la cuenta, porque son textos que escribe
el dueño de la cuenta. **No se usan los comentarios**: los escribe la audiencia, y mezclarlos
atribuiría a la cuenta rasgos de otras personas.

### ¿Cómo funciona?
1. Se juntan los textos de la cuenta (`build_corpus`).
2. Se envían a **Gemini** con instrucciones claras: puntuar de 0 a 100, citar evidencia, no hacer
   diagnósticos y declarar su nivel de confianza (`SYSTEM_PROMPT`).
3. La respuesta llega en JSON y se **valida** (`_parse`): los puntajes se limitan a 0-100 y el
   nivel (bajo/medio/alto) se recalcula a partir del puntaje.
4. El resultado se guarda en `profile.json` y se muestra como una tarjeta en `reporte.html`.

### ¿Por qué un modelo de lenguaje (LLM)?
Los modelos clásicos entrenados para Big Five suelen funcionar solo en inglés y con textos largos.
Un LLM entiende español, emojis y contexto, y además explica **por qué** da cada puntaje.

### Cómo obtener la clave gratuita (token)
1. Entra a **aistudio.google.com** con tu cuenta de Google.
2. Pulsa **Get API key** y crea una clave. No requiere tarjeta de crédito.
3. Guárdala **sin escribirla en el código**, de una de estas dos formas:

```powershell
# Opción A: solo para la ventana actual de PowerShell
$env:GEMINI_API_KEY="tu_clave"
```
```
# Opción B: crear un archivo .env en la carpeta del proyecto con esta línea
GEMINI_API_KEY=tu_clave
```

> **Seguridad:** la clave es personal. El archivo `.env` está en `.gitignore` para que nunca se
> suba a GitHub. Si la subes por error, bórrala en AI Studio y crea otra.

### Uso
```bash
# Dentro del flujo completo (scraping + Big Five + reporte)
python main.py usuario --bigfive

# Sobre datos ya guardados, sin repetir el scraping
python personality.py data/usuario/profile.json
```

Los nombres de los modelos de Gemini cambian con frecuencia. El programa consulta a la API los
modelos disponibles y prueba hasta 4. Si quieres fijar uno, define `GEMINI_MODEL`:

```powershell
$env:GEMINI_MODEL="nombre-del-modelo"
```

### Porcentajes que suman 100 %
Además del puntaje de cada rasgo (0 a 100), el programa calcula la **composición del perfil**:
cada puntaje dividido entre la suma de los cinco, expresado en porcentaje, con los decimales
repartidos (método del "mayor resto") para que el total sea exactamente **100 %**.

Ejemplo: puntajes 62, 81, 70, 75 y 30 (suman 318) → 20 %, 25 %, 22 %, 24 % y 9 % (suman 100).

> Los rasgos Big Five son escalas independientes, no partes de un total. Por eso se conservan
> **ambos** valores: el puntaje original y el porcentaje de composición. Está en `to_percentages()`.

### Ejemplo de resultado (en `profile.json`)
```json
"personality": {
  "traits": {
    "conscientiousness": {
      "score": 81, "level": "alto",
      "evidence": ["Habla de trabajo y disciplina"],
      "explanation": "Enfoque constante en el esfuerzo."
    }
  },
  "summary": "Perfil público orientado al esfuerzo y la gratitud.",
  "confidence": "media",
  "limitations": ["Pocos textos"]
}
```

### Limitaciones del análisis (importante para la exposición)
- **No es un test psicológico ni un diagnóstico.** Es una estimación orientativa hecha por una IA.
- **Poco texto = poca fiabilidad.** Diez descripciones cortas son muy pocas palabras. Si hay menos de
  150 palabras, el programa fuerza la confianza a "baja". Con más videos (`--videos 30`) mejora.
- **Mide la imagen pública, no la persona.** Las cuentas de figuras públicas suelen ser gestionadas
  por un equipo de comunicación.
- **El modelo puede equivocarse o ser sesgado.** Por eso se pide evidencia y se declara la confianza.
- **Privacidad:** según la documentación de Google, el uso gratuito de la API puede servir para
  mejorar sus productos. Solo se envían textos públicos de la cuenta, nunca datos privados.
- **Ética:** no uses este análisis para juzgar, acosar o tomar decisiones sobre personas reales.

---

## 11. Producto: Afinador de voz de marca

### La idea de negocio
Una herramienta para **pymes y agencias** que publican contenido en redes. El cliente pega los
textos que publica (descripciones, captions, guiones) y elige la voz que quiere transmitir
(por ejemplo "cercana y divertida"). El sistema mide cómo suena realmente el contenido, marca los
textos que se salen de la voz, propone reescrituras y genera una guía de estilo.

**Problema que resuelve:** cuando varias personas escriben para una misma marca, el tono cambia de un
texto a otro y se pierde la identidad.

**Por qué es viable:** el cliente entrega sus propios textos, así que no hace falta scraping ni se
perfila a ninguna persona. Se evitan los problemas con los términos de TikTok y casi todos los de
privacidad.

### Modelo de ingresos (precios de referencia supuestos)

| Plan | Para quién | Incluye | Precio de referencia |
|---|---|---|---|
| Gratis | Quien quiere probar | 3 análisis al mes | $0 |
| Equipo | Pymes con 1 a 3 personas en redes | Análisis ilimitados, reescritura, guía de estilo | $29 a $49 al mes |
| Agencia | Agencias con varias marcas | Hasta 10 marcas, reportes con su logo, comparación | $99 a $249 al mes |
| A medida | Empresas medianas | Integraciones y soporte | Cotización |

### Cómo funciona la lógica (`brand_voice.py`)
1. **Entrada:** textos separados por una línea en blanco (`clean_texts`, máx. 15 de 700 caracteres).
2. **Análisis del tono:** la IA estima, para cada texto, cuánto expresa cada rasgo Big Five en su
   **tono** (no en la persona).
3. **Porcentajes que suman 100:** los puntajes se convierten en una distribución (`to_percentages`).
4. **Alineación con la voz objetivo:**

   ```
   alineación = 100 - 0,5 × suma( |% actual - % objetivo| de los 5 rasgos )
   ```
   100 % significa voz idéntica a la objetivo; 0 %, totalmente distinta. Se calcula en código, no la
   inventa la IA, así que es repetible y fácil de explicar.
5. **Alerta:** los textos con alineación menor al umbral (80 % por defecto) quedan marcados.
6. **Propuestas:** una segunda consulta a la IA reescribe solo los textos marcados y genera una guía de
   estilo (tono, hábitos recomendados y cosas por evitar).
7. **Salida:** gráfico "tu voz vs voz objetivo", diagnóstico por rasgo (sobra, falta o en línea),
   análisis por texto e informe descargable (Markdown y JSON).

### Cómo ejecutarlo
```bash
python -m pip install -r requirements.txt
streamlit run app.py
```
Se abre en el navegador (normalmente `http://localhost:8501`). Pega la clave de Gemini en la barra
lateral o defínela en `.env` / `GEMINI_API_KEY`.

### Pruebas automáticas
```bash
python -m unittest -v
```
Verifican, sin internet ni clave, que los porcentajes siempre suman 100, que la alineación va de
0 a 100, que se marca el texto fuera de voz, que se rechaza una voz objetivo que no suma 100 y que las
reescrituras solo se aplican a los textos marcados. La IA se reemplaza por una respuesta simulada.

### Qué haría falta para vender el producto
- **Clave en el servidor:** en un producto real la clave de la IA no se pide al cliente.
- **Plan de pago de la API de IA:** el uso gratuito tiene límites bajos y, según la documentación de Google,
  puede servir para mejorar sus productos. Con textos confidenciales de clientes eso no es aceptable.
- **Cuentas de usuario, historial y cobro** (suscripciones).
- **Política de privacidad** y revisar con un abogado la ley de protección de datos de Ecuador.
- **Validar con clientes reales:** probar con textos de 5 a 10 negocios y comprobar que el resultado les
  sirve para decidir.
- **Revisar la competencia:** existen herramientas de voz de marca; la ventaja posible es el español
  latinoamericano, el precio y el enfoque en pymes.

### Límites del método
- El Big Five se creó para describir **personas**. Aplicarlo al **tono de un texto** es un método
  heurístico de marketing, no un test psicológico validado. Preséntalo como "perfil de tono".
- Con pocos textos el resultado es poco fiable; la app avisa cuando hay menos de 3.
- La IA puede equivocarse con ironía, jerga local o emojis. Las reescrituras deben revisarse antes de
  publicar.

---

## 12. Limitaciones

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

## 13. Solución de problemas

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

## 14. Aviso legal y ético

- Los términos de uso de TikTok restringen el scraping automatizado.
- Usa este proyecto **solo con fines educativos**, con **cuentas públicas** y
  con pocas peticiones.
- Prefiere cuentas propias, de marcas o de figuras públicas.
- Los perfiles y comentarios son **datos de personas reales**: no los
  publiques, no los vendas y no los uses para acosar o identificar a nadie.
- Los datos se guardan solo en tu computador.

---

## 15. Guía rápida para la exposición

**¿Qué hace el proyecto?**
Extrae automáticamente los datos públicos de una cuenta de TikTok y los guarda
en JSON y CSV.

**¿Por qué Playwright y no Requests o BeautifulSoup?**
Porque TikTok carga sus datos con JavaScript. Requests y BeautifulSoup solo ven
el HTML inicial, casi vacío. Playwright usa un navegador real que ejecuta ese
JavaScript, hace scroll y permite leer las respuestas de red.

**¿De dónde salen los datos?**
De dos lugares: del JSON que TikTok incrusta en la página y de las respuestas de
red que la propia página solicita al cargar videos y comentarios.

**¿Qué es el plan B?**
Un método de respaldo (leer el HTML) por si falla el método principal.

**¿Por qué no hay notificaciones?**
Porque son privadas y solo existen dentro de una sesión iniciada. Por scraping
de perfiles públicos no se puede acceder a ellas.

**¿Qué problemas encontraste?**
Bloqueos y captchas de TikTok, errores de instalación en Windows, y la
necesidad de usar Chrome o Edge instalados al fallar la descarga del navegador
de Playwright. Se resolvió con pausas aleatorias, planes de respaldo y la
captura de depuración.

**¿Qué es el Big Five y cómo lo calculaste?**
Es un modelo de cinco rasgos de personalidad (apertura, responsabilidad, extraversión, amabilidad y
neuroticismo). Se estima enviando la biografía y las descripciones de los videos a la API gratuita de
Gemini, que devuelve un puntaje de 0 a 100 por rasgo con su evidencia y su nivel de confianza.

**¿Por qué no usaste los comentarios para el Big Five?**
Porque los escriben otras personas. El Big Five describe a quien escribe, así que se usan solo los
textos del dueño de la cuenta.

**¿Qué tan confiable es el resultado?**
Es orientativo. Hay poco texto, puede estar escrito por un equipo de comunicación y lo genera una IA.
Por eso el programa declara una confianza y las limitaciones.

**¿Dónde guardas la clave de la API y por qué?**
En una variable de entorno o en un archivo `.env` que está en `.gitignore`. Una clave en el código
que se sube a GitHub puede ser usada por cualquiera.

**¿Cuál es el modelo de negocio?**
Una suscripción mensual para pymes y agencias: el cliente pega sus textos, elige la voz de marca
que busca y recibe el análisis, las alertas de textos fuera de voz, reescrituras y una guía de estilo.

**¿Cómo se calcula la alineación con la voz objetivo?**
Se comparan dos distribuciones de porcentajes (la del contenido y la objetivo): 100 menos la mitad de
la suma de las diferencias absolutas por rasgo. Es una fórmula simple, hecha en código y repetible.

**¿Por qué los porcentajes suman 100 %?**
Para poder comparar el contenido con la voz objetivo como dos distribuciones. Se conserva también el
puntaje original de cada rasgo porque los rasgos Big Five son escalas independientes.

**¿Cómo sabes que tu lógica funciona sin depender de la IA?**
Con pruebas automáticas (`python -m unittest`) que reemplazan la IA por una respuesta simulada y
verifican los cálculos, las validaciones y las reglas del producto.

**¿Es legal?**
El scraping de TikTok va contra sus términos de uso, por eso el proyecto es
solo educativo y se limita a cuentas públicas con pocas peticiones.

---

## 16. Mejoras posibles

- Analizar más videos o transcribir el audio para tener más texto en el Big Five.
- Analizar el sentimiento de los comentarios (audiencia) en lugar de su personalidad.
- Iniciar sesión con una cuenta propia para obtener más comentarios.
- Descargar también los archivos de video.
- Guardar los datos en una base de datos (SQLite).
- Analizar los datos con pandas (por ejemplo, el video con más likes).
- Procesar varias cuentas desde un archivo de texto.
