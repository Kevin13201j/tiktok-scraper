"""
report.py
---------
Genera un REPORTE VISUAL (reporte.html) a partir de los datos extraídos.
Es un solo archivo HTML: se abre con doble clic en cualquier navegador.

Se puede usar de dos formas:
  1) Automático: main.py lo genera al terminar el scraping.
  2) Manual (sin volver a hacer scraping):
         python report.py data/usuario/profile.json
"""
import html
import json
import os
import sys
import webbrowser
from datetime import datetime


def _n(x):
    """Número con separador de miles: 746100 -> 746.100"""
    if x is None:
        return "—"
    try:
        return f"{int(x):,}".replace(",", ".")
    except (TypeError, ValueError):
        return html.escape(str(x))


def _short(x):
    """Número abreviado: 1700000 -> 1,7 M"""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "—"
    for limit, suffix in ((1e9, " B"), (1e6, " M"), (1e3, " K")):
        if x >= limit:
            return f"{x / limit:.1f}".replace(".", ",") + suffix
    return str(int(x))


def _date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return "—"


def _e(text):
    return html.escape(text or "")


CSS = """
:root{--bg:#f5f6fa;--card:#fff;--text:#1c1e26;--muted:#6b7280;--line:#e5e7eb;--accent:#fe2c55;--accent2:#25f4ee;--bar:#fe2c55}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--text:#eceef3;--muted:#9aa1b0;--line:#2a2f3a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:24px 16px 56px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px;margin-bottom:20px}
.hero{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
.avatar{width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:grid;place-items:center;color:#fff;font-size:30px;font-weight:700;flex:none}
h1{margin:0;font-size:24px}
.user{color:var(--muted);margin:2px 0 8px}
.bio{margin:0;color:var(--text)}
.badge{display:inline-block;background:var(--accent);color:#fff;border-radius:999px;font-size:12px;padding:1px 8px;margin-left:6px;vertical-align:middle}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:18px}
.stat{border:1px solid var(--line);border-radius:12px;padding:14px}
.stat b{display:block;font-size:24px}
.stat span{color:var(--muted);font-size:13px}
h2{font-size:18px;margin:0 0 14px}
.row{display:grid;grid-template-columns:96px 1fr 70px;gap:10px;align-items:center;margin:7px 0;font-size:13px}
.row .lbl{color:var(--muted)}
.track{background:var(--line);border-radius:6px;height:14px;overflow:hidden}
.fill{height:100%;background:linear-gradient(90deg,var(--accent),#ff7a93);border-radius:6px}
.row .val{text-align:right;font-weight:600}
.video{border-top:1px solid var(--line);padding:16px 0}
.video:first-of-type{border-top:0}
.vhead{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:13px}
.desc{white-space:pre-wrap;margin:6px 0 10px;font-weight:500}
.metrics{display:flex;gap:16px;flex-wrap:wrap;font-size:14px}
.metrics span b{margin-left:4px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
details{margin-top:10px}
summary{cursor:pointer;color:var(--muted);font-size:14px}
ul.comments{list-style:none;padding:0;margin:10px 0 0}
ul.comments li{padding:8px 10px;border-radius:10px;background:var(--bg);margin-bottom:6px;font-size:14px}
ul.comments .au{font-weight:700}
ul.comments .lk{color:var(--muted);font-size:12px;margin-left:8px;white-space:nowrap}
.notes{color:var(--muted);font-size:13px;padding-left:18px}
footer{color:var(--muted);font-size:12px;text-align:center;margin-top:24px}
"""


CSS += """
.trait{margin:16px 0}
.thead{display:flex;justify-content:space-between;gap:10px;font-size:14px;margin-bottom:4px}
.thead span{color:var(--muted)}
.texpl{margin:6px 0 0;color:var(--muted);font-size:14px}
.aviso{border-left:4px solid var(--accent);background:var(--bg);padding:10px 14px;border-radius:8px;font-size:13px;color:var(--muted);margin-top:16px}
.stack{display:flex;height:22px;border-radius:8px;overflow:hidden;margin:12px 0 6px}
.stack div{height:100%}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13px;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
"""

TRAIT_ORDER = [
    ("openness", "Apertura a la experiencia"),
    ("conscientiousness", "Responsabilidad"),
    ("extraversion", "Extraversión"),
    ("agreeableness", "Amabilidad"),
    ("neuroticism", "Neuroticismo"),
]
STACK_COLORS = ["#8b5cf6", "#06b6d4", "#fe2c55", "#f59e0b", "#64748b"]


def _personality_card(p):
    """Tarjeta del análisis Big Five (solo si existe en los datos)."""
    if not p:
        return ""

    # Porcentajes que suman 100 (si el JSON es antiguo, se calculan aquí).
    pcts = p.get("percentages")
    if not pcts:
        try:
            from personality import to_percentages
            traits = p.get("traits") or {}
            pcts = to_percentages({k: (traits.get(k) or {}).get("score") or 0 for k, _ in TRAIT_ORDER})
        except Exception:
            pcts = {}

    segs, legend = "", ""
    for (key, label), color in zip(TRAIT_ORDER, STACK_COLORS):
        v = pcts.get(key)
        if v is None:
            continue
        segs += ('<div style="width:' + str(v) + "%;background:" + color + '" title="'
                 + _e(label) + ": " + str(v) + ' %"></div>')
        legend += '<span><i style="background:' + color + '"></i>' + _e(label) + " " + str(v) + " %</span>"
    stack_html = ""
    if segs:
        stack_html = ('<div class="stack">' + segs + '</div><div class="legend">' + legend + "</div>"
                      '<div class="legend" style="margin-top:4px"><span><b>Total: '
                      + str(sum(pcts.values())) + " %</b></span></div>")

    rows = ""
    for key, label in TRAIT_ORDER:
        t = (p.get("traits") or {}).get(key) or {}
        score = t.get("score")
        pct = score if isinstance(score, (int, float)) else 0
        share = pcts.get(key)
        share_txt = " · " + str(share) + " % del perfil" if share is not None else ""
        ev = "".join("<li>" + _e(x) + "</li>" for x in t.get("evidence") or [])
        ev_html = '<ul class="notes">' + ev + "</ul>" if ev else ""
        rows += (
            '<div class="trait"><div class="thead"><b>' + label + "</b>"
            "<span>" + _n(score) + "/100 · " + _e(t.get("level")) + share_txt + "</span></div>"
            '<div class="track"><div class="fill" style="width:' + str(pct) + '%"></div></div>'
            '<p class="texpl">' + _e(t.get("explanation")) + "</p>" + ev_html + "</div>"
        )
    limits = "".join("<li>" + _e(x) + "</li>" for x in p.get("limitations") or [])
    limits_html = '<ul class="notes">' + limits + "</ul>" if limits else ""
    return (
        '<div class="card"><h2>Perfil Big Five (estimación)</h2>'
        "<p>" + _e(p.get("summary")) + "</p>" + stack_html + rows +
        '<div class="aviso"><b>Confianza: ' + _e(p.get("confidence")) + "</b> · textos analizados: "
        + _n(p.get("texts_used")) + " · palabras: " + _n(p.get("words_used")) +
        " · modelo: " + _e(p.get("model")) + "<br>Estimación orientativa generada por IA a partir de "
        "la biografía y las descripciones públicas. Refleja la imagen pública de la cuenta, no es un "
        "test psicológico ni un diagnóstico. La barra superior muestra la composición del perfil "
        "(suma 100 %); cada rasgo también conserva su puntaje original de 0 a 100." + limits_html + "</div></div>"
    )


def generate_html(profile: dict, path: str) -> str:
    videos = profile.get("videos") or []
    name = profile.get("name") or profile.get("username") or "—"
    initial = (name.strip()[:1] or "?").upper()
    verified = '<span class="badge">verificada</span>' if profile.get("verified") else ""
    bio = _e(profile.get("bio")).replace("\n", "<br>") or "Sin biografía"

    total_views = sum(v.get("views") or 0 for v in videos)
    total_likes = sum(v.get("likes") or 0 for v in videos)
    total_comments = sum(len(v.get("comments") or []) for v in videos)
    best = max(videos, key=lambda v: v.get("views") or 0, default=None)
    engagement = (total_likes / total_views * 100) if total_views else 0

    # --- tarjetas de estadísticas del perfil ---
    stats = [
        ("Seguidores", _n(profile.get("followers"))),
        ("Seguidos", _n(profile.get("following"))),
        ("Likes totales", _short(profile.get("likes_total"))),
    ]
    if profile.get("videos_count") is not None:
        stats.append(("Videos en la cuenta", _n(profile.get("videos_count"))))
    stats_html = "".join(f'<div class="stat"><b>{v}</b><span>{k}</span></div>' for k, v in stats)

    # --- resumen de los videos analizados ---
    summary = [
        (f"Vistas en {len(videos)} videos", _short(total_views)),
        ("Likes en esos videos", _short(total_likes)),
        ("Likes / vistas", f"{engagement:.1f} %".replace(".", ",")),
        ("Comentarios extraídos", _n(total_comments)),
    ]
    summary_html = "".join(f'<div class="stat"><b>{v}</b><span>{k}</span></div>' for k, v in summary)

    # --- gráfico de vistas (barras con CSS) ---
    max_views = max((v.get("views") or 0 for v in videos), default=0) or 1
    bars = ""
    for i, v in enumerate(videos, 1):
        pct = (v.get("views") or 0) / max_views * 100
        bars += (f'<div class="row"><span class="lbl">#{i} · {_date(v.get("created_at"))}</span>'
                 f'<div class="track"><div class="fill" style="width:{pct:.1f}%"></div></div>'
                 f'<span class="val">{_short(v.get("views"))}</span></div>')

    # --- lista de videos ---
    cards = ""
    for i, v in enumerate(videos, 1):
        comments = v.get("comments") or []
        items = "".join(
            f'<li><span class="au">@{_e(c.get("author")) or "anónimo"}</span> {_e(c.get("text"))}'
            f'<span class="lk">♥ {_n(c.get("likes"))}</span></li>'
            for c in comments
        )
        comments_html = (f'<details><summary>Ver {len(comments)} comentarios</summary>'
                         f'<ul class="comments">{items}</ul></details>') if comments else \
                        '<div class="vhead">Sin comentarios extraídos</div>'
        cards += f"""
        <div class="video">
          <div class="vhead"><span>#{i} · {_date(v.get("created_at"))}</span>
            <a href="{_e(v.get("url"))}" target="_blank" rel="noopener">Abrir en TikTok ↗</a></div>
          <div class="desc">{_e(v.get("description")) or "<i>(sin descripción)</i>"}</div>
          <div class="metrics">
            <span>👁 Vistas<b>{_n(v.get("views"))}</b></span>
            <span>♥ Likes<b>{_n(v.get("likes"))}</b></span>
            <span>💬 Comentarios<b>{_n(v.get("comments_count"))}</b></span>
            <span>↗ Compartidos<b>{_n(v.get("shares"))}</b></span>
          </div>
          {comments_html}
        </div>"""

    best_html = ""
    if best and best.get("views"):
        best_html = (f'<p style="margin:14px 0 0;color:var(--muted)">Video más visto: '
                     f'<a href="{_e(best.get("url"))}" target="_blank" rel="noopener">'
                     f'{_short(best.get("views"))} vistas</a> ({_date(best.get("created_at"))})</p>')

    notes = "".join(f"<li>{_e(n)}</li>" for n in profile.get("notes") or [])
    notes_html = f'<div class="card"><h2>Notas</h2><ul class="notes">{notes}</ul></div>' if notes else ""

    personality_html = _personality_card(profile.get("personality"))

    page = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte de @{_e(profile.get("username"))}</title><style>{CSS}</style></head>
<body><div class="wrap">
  <div class="card">
    <div class="hero">
      <div class="avatar">{_e(initial)}</div>
      <div>
        <h1>{_e(name)}{verified}</h1>
        <div class="user">@{_e(profile.get("username"))} ·
          <a href="{_e(profile.get("profile_url"))}" target="_blank" rel="noopener">ver perfil ↗</a></div>
        <p class="bio">{bio}</p>
      </div>
    </div>
    <div class="stats">{stats_html}</div>
  </div>

  <div class="card"><h2>Resumen de los últimos {len(videos)} videos</h2>
    <div class="stats">{summary_html}</div>{best_html}</div>

  <div class="card"><h2>Vistas por video</h2>{bars or "Sin videos"}</div>

  <div class="card"><h2>Detalle de cada video</h2>{cards or "Sin videos"}</div>

  {personality_html}

  {notes_html}
  <footer>Extraído el {_date(profile.get("scraped_at"))} · Proyecto educativo · Datos públicos de TikTok</footer>
</div></body></html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    return path


def open_in_browser(path: str):
    webbrowser.open("file:///" + os.path.abspath(path).replace("\\", "/"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python report.py data/usuario/profile.json")
        sys.exit(1)
    json_path = sys.argv[1]
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    out = os.path.join(os.path.dirname(json_path), "reporte.html")
    generate_html(data, out)
    print(f"Reporte generado: {out}")
    open_in_browser(out)
