"""
main.py
-------
Punto de entrada. Recibe el usuario por consola, ejecuta el scraper
y guarda los resultados en la carpeta data/ (JSON y CSV).

Ejemplo:
    python main.py nombre_de_usuario --videos 10 --comments 20
"""
import argparse
import csv
import json
import os
from dataclasses import asdict

from scraper import TikTokScraper


def save_json(profile, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(profile), f, ensure_ascii=False, indent=2)


def save_csvs(profile, folder):
    """videos.csv (1 fila por video) y comments.csv (1 fila por comentario)."""
    vfields = ["id", "url", "description", "created_at", "views", "likes",
               "comments_count", "shares", "duration_seconds"]
    with open(os.path.join(folder, "videos.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=vfields)
        w.writeheader()
        for v in profile.videos:
            w.writerow({k: getattr(v, k) for k in vfields})

    cfields = ["video_id", "author", "text", "likes", "created_at"]
    with open(os.path.join(folder, "comments.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cfields)
        w.writeheader()
        for v in profile.videos:
            for c in v.comments:
                w.writerow({"video_id": v.id, "author": c.author, "text": c.text,
                            "likes": c.likes, "created_at": c.created_at})


def main():
    p = argparse.ArgumentParser(description="Scraper educativo de cuentas públicas de TikTok")
    p.add_argument("username", help="usuario de TikTok (con o sin @)")
    p.add_argument("--videos", type=int, default=10, help="cantidad de videos (default 10)")
    p.add_argument("--comments", type=int, default=20, help="comentarios por video (default 20)")
    p.add_argument("--headless", action="store_true", help="sin ventana (más fácil de bloquear)")
    p.add_argument("--out", default="data", help="carpeta de salida (default data)")
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    with TikTokScraper(headless=args.headless) as scraper:
        profile = scraper.scrape_profile(args.username, args.videos, args.comments)

    base = args.username.lstrip("@")
    folder = os.path.join(args.out, base)
    os.makedirs(folder, exist_ok=True)
    save_json(profile, os.path.join(folder, "profile.json"))
    save_csvs(profile, folder)

    print("\n=== RESUMEN ===")
    print(f"Usuario:     @{profile.username}")
    print(f"Nombre:      {profile.name}")
    print(f"Biografía:   {profile.bio}")
    print(f"Seguidores:  {profile.followers}")
    print(f"Seguidos:    {profile.following}")
    print(f"Likes total: {profile.likes_total}")
    print(f"Videos extraídos: {len(profile.videos)}")
    for i, v in enumerate(profile.videos, 1):
        desc = (v.description or "").replace("\n", " ")[:50]
        print(f"  {i:>2}. vistas={v.views} likes={v.likes} "
              f"comentarios_total={v.comments_count} extraídos={len(v.comments)} | {desc}")
    print(f"Comentarios extraídos: {sum(len(v.comments) for v in profile.videos)}")
    for n in profile.notes:
        print(f"[nota] {n}")
    print(f"\nArchivos guardados en: {folder}/")


if __name__ == "__main__":
    main()