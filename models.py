"""
models.py
---------
Define la ESTRUCTURA de los datos que vamos a extraer.
Usamos 'dataclasses' porque son clases simples que solo guardan datos
y se convierten fácilmente a diccionario (y luego a JSON).
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Comment:
    """Un comentario de un video."""
    author: Optional[str] = None      # @usuario de quien comenta
    text: Optional[str] = None        # texto del comentario
    likes: Optional[int] = None       # likes del comentario
    created_at: Optional[str] = None  # fecha en formato ISO


@dataclass
class Video:
    """Un TikTok (video) de la cuenta."""
    id: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    created_at: Optional[str] = None
    views: Optional[int] = None
    likes: Optional[int] = None
    comments_count: Optional[int] = None
    shares: Optional[int] = None
    duration_seconds: Optional[int] = None
    comments: List[Comment] = field(default_factory=list)


@dataclass
class Profile:
    """Todos los datos de una cuenta."""
    username: Optional[str] = None     # @usuario (unique id)
    name: Optional[str] = None         # nombre visible (nickname)
    followers: Optional[Any] = None    # número de seguidores
    following: Optional[Any] = None    # a cuántos sigue
    likes_total: Optional[Any] = None  # likes totales recibidos
    videos_count: Optional[Any] = None # cantidad total de videos
    bio: Optional[str] = None          # biografía
    verified: Optional[bool] = None    # cuenta verificada
    profile_url: Optional[str] = None
    # Las notificaciones son privadas: no se pueden obtener por scraping.
    notifications: Optional[str] = None
    videos: List[Video] = field(default_factory=list)
    scraped_at: Optional[str] = None
    notes: List[str] = field(default_factory=list)  # avisos sobre lo que no se pudo obtener
    personality: Optional[dict] = None  # análisis Big Five (opcional, ver personality.py)
