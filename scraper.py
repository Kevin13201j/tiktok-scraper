"""
scraper.py
----------
Lógica principal del scraping con Playwright.

IDEA CLAVE: TikTok carga los datos con JavaScript, por eso usamos un
navegador real (Playwright). Los datos se obtienen por varias vías, de la
más fiable a la menos fiable ("planes"):

  PERFIL   -> JSON incrustado en la página  (plan B: selectores HTML)
  VIDEOS   -> respuesta de red /api/post/item_list  (plan B: enlaces de la cuadrícula)
  DETALLE  -> JSON incrustado en la página de CADA video (vistas, likes, fecha...)
  COMENTS  -> respuesta de red /api/comment/list    (plan B: leer el HTML)
"""
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from typing import List, Optional

from playwright.sync_api import sync_playwright

from models import Comment, Profile, Video

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _iso(timestamp) -> Optional[str]:
    """Convierte un timestamp (segundos) a fecha ISO legible."""
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def _abbr_to_int(text) -> Optional[int]:
    """Convierte textos como '1.2M', '345K' o '1,2 M' en números (aproximados)."""
    if text is None:
        return None
    t = str(text).strip().upper().replace(" ", "")
    if re.search(r"[KMB]$", t):
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "").replace(".", "")
    m = re.match(r"^(\d+(?:\.\d+)?)([KMB]?)$", t)
    if not m:
        return None
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2)]
    return int(float(m.group(1)) * mult)


class TikTokScraper:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self._pw = None
        self.context = None
        self.page = None

    # ---------- Ciclo de vida del navegador (with ... as scraper) ----------
    def _launch_context(self):
        """
        Abre Chrome/Edge con un perfil PROPIO y persistente (data/browser_profile).
        Así las cookies y un captcha ya resuelto se recuerdan entre ejecuciones,
        y TikTok desconfía menos que de un navegador "nuevo" cada vez.
        """
        user_dir = os.path.abspath("data/browser_profile")
        os.makedirs(user_dir, exist_ok=True)
        last_error = None
        for channel in ("chrome", "msedge", None):
            try:
                kwargs = dict(
                    user_data_dir=user_dir,
                    headless=self.headless,
                    args=["--disable-blink-features=AutomationControlled"],
                    locale="es-ES",
                    viewport={"width": 1280, "height": 900},
                )
                if channel:
                    kwargs["channel"] = channel
                return self._pw.chromium.launch_persistent_context(**kwargs)
            except Exception as e:
                last_error = e
        raise RuntimeError(f"No se pudo abrir Chrome, Edge ni Chromium: {last_error}")

    def __enter__(self):
        self._pw = sync_playwright().start()
        self.context = self._launch_context()
        # Oculta la señal de "navegador automatizado".
        self.context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self

    def __exit__(self, *exc):
        if self.context:
            self.context.close()
        if self._pw:
            self._pw.stop()

    # ---------- Utilidades ----------
    @staticmethod
    def _pause(a: float = 1.5, b: float = 3.5):
        """Pausa aleatoria: es más educado con el servidor y menos sospechoso."""
        time.sleep(random.uniform(a, b))

    def _captcha_visible(self) -> bool:
        """True solo si hay un captcha realmente VISIBLE (evita falsos positivos)."""
        sel = '#captcha-verify-container-main-page, [id*="captcha" i], [class*="captcha" i]'
        try:
            loc = self.page.locator(sel)
            for i in range(min(loc.count(), 10)):
                if loc.nth(i).is_visible():
                    return True
        except Exception:
            pass
        return False

    def _handle_captcha(self):
        """Si aparece un captcha, avisa y espera (hasta 120 s) a que lo resuelvas a mano."""
        if not self._captcha_visible():
            return
        if self.headless:
            print("[!] Captcha detectado. Ejecuta sin --headless para resolverlo.")
            return
        print("[!] Captcha VISIBLE. Resuélvelo en la ventana (hasta 120 s)...")
        for _ in range(40):
            time.sleep(3)
            if not self._captcha_visible():
                print("[ok] Captcha resuelto, continuando...")
                self._pause(2, 3)
                return
        print("[!] El captcha sigue visible; los datos pueden quedar incompletos.")

    def _dismiss_popups(self):
        """Cierra banners de cookies y ventanas de login si aparecen."""
        try:
            btn = self.page.get_by_role(
                "button", name=re.compile(r"rechazar|decline all|reject|permitir todo|allow all", re.I))
            if btn.count():
                btn.first.click(timeout=2000)
        except Exception:
            pass
        try:
            close = self.page.locator('[data-e2e="modal-close-inner-button"]')
            if close.count():
                close.first.click(timeout=2000)
        except Exception:
            pass

    def _debug_dump(self, tag: str):
        """Guarda captura y HTML para ver QUÉ cargó realmente TikTok."""
        os.makedirs("data/debug", exist_ok=True)
        try:
            self.page.screenshot(path=f"data/debug/{tag}.png", full_page=False)
            with open(f"data/debug/{tag}.html", "w", encoding="utf-8") as f:
                f.write(self.page.content())
            print(f"[debug] Captura guardada en data/debug/{tag}.png")
            print(f"[debug] URL final: {self.page.url} | Título: {self.page.title()}")
        except Exception as e:
            print(f"[debug] No se pudo guardar la captura: {e}")

    def _page_json(self) -> Optional[dict]:
        """Devuelve el JSON que TikTok incrusta en la página (o None)."""
        try:
            raw = self.page.locator("#__UNIVERSAL_DATA_FOR_REHYDRATION__").text_content(timeout=3000)
            return json.loads(raw)["__DEFAULT_SCOPE__"]
        except Exception:
            return None

    # ---------- 1) PERFIL ----------
    def _profile_from_json(self, profile: Profile) -> bool:
        scope = self._page_json()
        if not scope:
            return False
        detail = scope.get("webapp.user-detail") or {}

        code = detail.get("statusCode")
        if code not in (None, 0):
            note = f"TikTok devolvió statusCode={code} ({detail.get('statusMsg') or 'sin mensaje'})."
            if note not in profile.notes:
                profile.notes.append(note)

        info = detail.get("userInfo") or {}
        user = info.get("user")
        if not user:
            return False
        stats = info.get("stats") or info.get("statsV2") or {}

        profile.username = user.get("uniqueId")
        profile.name = user.get("nickname")
        profile.bio = user.get("signature")
        profile.verified = user.get("verified")
        profile.followers = stats.get("followerCount")
        profile.following = stats.get("followingCount")
        profile.likes_total = stats.get("heartCount")
        profile.videos_count = stats.get("videoCount")
        return True

    def _profile_from_dom(self, profile: Profile):
        """Plan B: leer los textos visibles en la página (vienen como '1.2M')."""
        def txt(selector):
            loc = self.page.locator(selector)
            return loc.first.inner_text().strip() if loc.count() else None

        profile.username = txt('[data-e2e="user-title"]')
        profile.name = txt('[data-e2e="user-subtitle"]')
        profile.followers = _abbr_to_int(txt('[data-e2e="followers-count"]'))
        profile.following = _abbr_to_int(txt('[data-e2e="following-count"]'))
        profile.likes_total = _abbr_to_int(txt('[data-e2e="likes-count"]'))
        profile.bio = txt('[data-e2e="user-bio"]')
        profile.notes.append("Perfil leído desde el HTML: los números son aproximados (1.2M).")

    def _wait_for_profile(self, profile: Profile) -> bool:
        """
        Intenta leer el perfil. Si no se puede y hay ventana visible, espera
        hasta 60 s para que resuelvas un captcha / cierres un login a mano.
        """
        for attempt in range(20):  # 20 x 3 s = 60 s
            self._dismiss_popups()
            if self._profile_from_json(profile):
                return True
            if self.page.locator('[data-e2e="user-title"]').count():
                self._profile_from_dom(profile)
                return True
            if self.headless:
                break
            if attempt == 0:
                print("[!] No se ve el perfil todavía. Si hay captcha o login en la ventana,")
                print("    resuélvelo/ciérralo. Esperando hasta 60 s...")
            time.sleep(3)
        return False

    # ---------- 2) VIDEOS ----------
    @staticmethod
    def _item_to_video(item: dict, username: str) -> Video:
        stats = item.get("stats", {})
        vid = str(item.get("id"))
        return Video(
            id=vid,
            url=f"https://www.tiktok.com/@{username}/video/{vid}",
            description=item.get("desc"),
            created_at=_iso(item.get("createTime")),
            views=stats.get("playCount"),
            likes=stats.get("diggCount"),
            comments_count=stats.get("commentCount"),
            shares=stats.get("shareCount"),
            duration_seconds=(item.get("video") or {}).get("duration"),
        )

    def _load_grid(self) -> bool:
        """Espera la cuadrícula de videos; si TikTok muestra error, reintenta."""
        sel = '[data-e2e="user-post-item"], a[href*="/video/"]'
        for _ in range(3):
            try:
                self.page.wait_for_selector(sel, timeout=15000)
                return True
            except Exception:
                btn = self.page.get_by_role(
                    "button", name=re.compile(r"actualizar|refresh|reintentar|retry", re.I))
                try:
                    if btn.count():
                        btn.first.click(timeout=2000)
                    else:
                        self.page.reload(wait_until="domcontentloaded")
                except Exception:
                    pass
                self._pause(3, 5)
                self._dismiss_popups()
                self._handle_captcha()
        return False

    def _videos_from_grid(self, limit: int) -> List[Video]:
        """Plan B: leer enlaces (y vistas visibles) de la cuadrícula del perfil."""
        rows = self.page.eval_on_selector_all(
            'a[href*="/video/"]',
            """els => els.map(e => {
                const box = e.closest('[data-e2e="user-post-item"]') || e.parentElement || e;
                const v = box.querySelector('[data-e2e="video-views"]');
                const img = e.querySelector('img');
                return {href: e.href, views: v ? v.innerText : null, alt: img ? img.alt : null};
            })""",
        )
        videos, seen = [], set()
        for r in rows:
            m = re.search(r"/video/(\d+)", r["href"])
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            videos.append(Video(
                id=m.group(1), url=r["href"],
                description=r.get("alt"), views=_abbr_to_int(r.get("views")),
            ))
            if len(videos) >= limit:
                break
        return videos

    # ---------- 3) DETALLE + COMENTARIOS DE CADA VIDEO ----------
    def _video_detail_from_json(self, video: Video) -> bool:
        """Lee el JSON de la página del video: vistas, likes, fecha, descripción..."""
        scope = self._page_json()
        try:
            item = scope["webapp.video-detail"]["itemInfo"]["itemStruct"]
        except Exception:
            return False
        stats = item.get("stats", {})
        video.description = item.get("desc") or video.description
        video.created_at = _iso(item.get("createTime")) or video.created_at
        video.views = stats.get("playCount", video.views)
        video.likes = stats.get("diggCount", video.likes)
        video.comments_count = stats.get("commentCount", video.comments_count)
        video.shares = stats.get("shareCount", video.shares)
        video.duration_seconds = (item.get("video") or {}).get("duration", video.duration_seconds)
        return True

    def _video_detail_from_dom(self, video: Video):
        """Plan B: leer contadores visibles en la página del video."""
        def num(selector):
            loc = self.page.locator(selector)
            return _abbr_to_int(loc.first.inner_text()) if loc.count() else None

        video.likes = video.likes if video.likes is not None else num('[data-e2e="like-count"]')
        video.comments_count = (video.comments_count if video.comments_count is not None
                                else num('[data-e2e="comment-count"]'))
        video.shares = video.shares if video.shares is not None else num('[data-e2e="share-count"]')
        if not video.description:
            d = self.page.locator('[data-e2e="browse-video-desc"]')
            video.description = d.first.inner_text() if d.count() else None

    def _comments_from_dom(self, limit: int) -> List[Comment]:
        """Plan B: leer los comentarios que se ven en pantalla."""
        rows = self.page.eval_on_selector_all(
            '[data-e2e="comment-level-1"]',
            """els => els.map(e => {
                const box = e.closest('[class*="CommentItemContainer"]') || e.parentElement.parentElement;
                const u = box ? box.querySelector('[data-e2e^="comment-username"]') : null;
                const l = box ? box.querySelector('[data-e2e="comment-like-count"]') : null;
                return {text: e.innerText, author: u ? u.innerText : null, likes: l ? l.innerText : null};
            })""",
        )
        return [Comment(author=r["author"], text=r["text"], likes=_abbr_to_int(r["likes"]))
                for r in rows[:limit]]

    def _scrape_video(self, video: Video, max_comments: int):
        """Abre un video, completa sus datos y extrae sus comentarios."""
        captured: List[dict] = []

        def on_response(resp):
            if "/api/comment/list" in resp.url:
                try:
                    captured.extend(resp.json().get("comments") or [])
                except Exception:
                    pass

        self.page.on("response", on_response)
        try:
            self.page.goto(video.url, wait_until="domcontentloaded", timeout=60000)
            self._pause(3, 5)
            self._dismiss_popups()
            self._handle_captcha()

            if not self._video_detail_from_json(video):
                self._video_detail_from_dom(video)

            # Abrir el panel de comentarios (en algunos diseños está cerrado).
            icon = self.page.locator('[data-e2e="comment-icon"]')
            if icon.count():
                try:
                    icon.first.click(timeout=3000)
                except Exception:
                    pass
            try:
                self.page.wait_for_selector('[data-e2e="comment-level-1"]', timeout=8000)
            except Exception:
                pass

            # Scroll en la zona de comentarios para que cargue más.
            self.page.mouse.move(1000, 600)
            for _ in range(8):
                if len(captured) >= max_comments:
                    break
                self.page.mouse.wheel(0, 1500)
                self._pause(1.2, 2.2)
        finally:
            self.page.remove_listener("response", on_response)

        comments, seen = [], set()
        for c in captured:
            cid = c.get("cid")
            if cid in seen:
                continue
            seen.add(cid)
            comments.append(Comment(
                author=(c.get("user") or {}).get("unique_id"),
                text=c.get("text"),
                likes=c.get("digg_count"),
                created_at=_iso(c.get("create_time")),
            ))
            if len(comments) >= max_comments:
                break

        if not comments:  # plan B
            comments = self._comments_from_dom(max_comments)
        video.comments = comments

    # ---------- FUNCIÓN PRINCIPAL ----------
    def scrape_profile(self, username: str, max_videos: int = 10,
                       max_comments: int = 20) -> Profile:
        username = username.lstrip("@")
        url = f"https://www.tiktok.com/@{username}"
        profile = Profile(profile_url=url,
                          scraped_at=datetime.now(timezone.utc).isoformat())
        profile.notifications = None
        profile.notes.append(
            "Las notificaciones son privadas y requieren sesión: no se pueden obtener por scraping."
        )

        # Escuchamos la lista de videos que TikTok pide al cargar/scroll.
        items: List[dict] = []

        def on_response(resp):
            if "/api/post/item_list" in resp.url:
                try:
                    items.extend(resp.json().get("itemList") or [])
                except Exception:
                    pass

        self.page.on("response", on_response)
        print(f"[1/3] Abriendo perfil: {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        self._pause(3, 5)
        self._handle_captcha()

        if not self._wait_for_profile(profile):
            profile.username = username
            profile.notes.append("No se pudo leer el perfil (¿cuenta privada, inexistente o bloqueo?).")
            self._debug_dump(f"perfil_{username}")

        # Cargar los videos.
        print(f"[2/3] Cargando los últimos {max_videos} videos...")
        if not self._load_grid():
            profile.notes.append("La cuadrícula de videos no cargó (TikTok pudo bloquearla).")
            self._debug_dump(f"videos_{username}")
        else:
            for _ in range(8):
                n_links = self.page.locator('a[href*="/video/"]').count()
                if n_links >= max_videos + 3 and len(items) >= max_videos:
                    break
                self.page.mouse.wheel(0, 2000)
                self._pause(1.5, 3)
        self.page.remove_listener("response", on_response)

        # Quitamos duplicados manteniendo el orden.
        unique, seen = [], set()
        for it in items:
            if it.get("id") not in seen:
                seen.add(it.get("id"))
                unique.append(it)

        uname = profile.username or username
        if unique:
            videos = [self._item_to_video(i, uname) for i in unique]
            # Los videos "fijados" salen primero: ordenamos por fecha (más nuevos primero).
            if all(v.created_at for v in videos):
                videos.sort(key=lambda v: v.created_at, reverse=True)
            profile.videos = videos[:max_videos]
        else:
            profile.videos = self._videos_from_grid(max_videos)
            if profile.videos:
                profile.notes.append(
                    "Videos leídos desde la cuadrícula: pueden incluir videos fijados primero.")

        if not profile.videos:
            profile.notes.append("No se encontraron videos (cuenta sin videos o bloqueo de TikTok).")
            return profile

        # Detalle + comentarios de cada video.
        print(f"[3/3] Extrayendo datos y comentarios (máx. {max_comments} por video)...")
        for i, video in enumerate(profile.videos, 1):
            print(f"      video {i}/{len(profile.videos)}")
            try:
                self._scrape_video(video, max_comments)
            except Exception as e:
                profile.notes.append(f"Error en el video {video.id}: {e}")
            self._pause(2, 4)

        return profile
