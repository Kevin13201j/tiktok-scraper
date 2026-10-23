"""
brand_voice.py
--------------
Lógica de negocio del producto "Afinador de voz de marca".

El cliente (pyme o agencia) pega los textos que publica y elige la voz que
quiere transmitir. El sistema:

  1. Estima, para cada texto, cuánto expresa cada rasgo Big Five EN SU TONO.
  2. Convierte esos puntajes en porcentajes que suman 100 (to_percentages).
  3. Mide la ALINEACIÓN con la voz objetivo:
         alineación = 100 - 0,5 * suma(|actual% - objetivo%|)
     (100 = voz idéntica a la objetivo, 0 = totalmente distinta).
  4. Marca los textos que se salen de la voz (alineación < umbral).
  5. Propone reescrituras y una guía de estilo.

Importante: el Big Five describe personas. Aquí se aplica al TONO de un texto
como método heurístico de marketing, no como test psicológico.
"""
import re

from personality import TRAITS, ask_json, parse_json_text, to_percentages

KEYS = [k for k, _ in TRAITS]
LABELS = dict(TRAITS)

MAX_TEXTS = 15
MAX_CHARS = 700

# Voces objetivo de ejemplo (cada una suma exactamente 100).
PRESETS = {
    "Cercana y divertida": {"openness": 22, "conscientiousness": 12, "extraversion": 30,
                            "agreeableness": 28, "neuroticism": 8},
    "Profesional y confiable": {"openness": 14, "conscientiousness": 34, "extraversion": 14,
                                "agreeableness": 28, "neuroticism": 10},
    "Inspiradora y creativa": {"openness": 34, "conscientiousness": 14, "extraversion": 26,
                               "agreeableness": 20, "neuroticism": 6},
}

TRAIT_MEANING = (
    "Apertura: creativo, original, curioso. "
    "Responsabilidad: ordenado, preciso, confiable. "
    "Extraversión: enérgico, social, expresivo. "
    "Amabilidad: cálido, empático, cercano. "
    "Neuroticismo: tono ansioso, tenso o negativo (en una marca normalmente se busca bajo)."
)


# ---------- Utilidades puras (se pueden probar sin IA) ----------
def clean_texts(raw):
    """Separa los textos por línea en blanco, recorta espacios y aplica los límites."""
    blocks = re.split(r"\n\s*\n", raw or "")
    texts = [b.strip()[:MAX_CHARS] for b in blocks if b.strip()]
    return texts[:MAX_TEXTS]


def alignment(actual, target):
    """Alineación (0-100) entre dos distribuciones de porcentajes."""
    distance = 0.5 * sum(abs(actual[k] - target[k]) for k in KEYS)
    return round(100 - distance, 1)


def gaps(actual, target):
    """Diferencia por rasgo en puntos porcentuales (positivo = sobra, negativo = falta)."""
    return {k: actual[k] - target[k] for k in KEYS}


def _mean_scores(rows):
    return {k: round(sum(r["scores"][k] for r in rows) / len(rows)) for k in KEYS}


def _target_text(target):
    return ", ".join(f"{LABELS[k]} {target[k]} %" for k in KEYS)


# ---------- Paso 1: analizar el tono de los textos ----------
SYSTEM_ANALYSIS = """Eres un analista de tono de marca (copywriting). Aplicas la escala Big Five al TONO de cada texto,
no a la persona que lo escribió. Para cada texto, da un puntaje de 0 a 100 por rasgo según cuánto
se EXPRESA ese rasgo en el tono. Si un rasgo casi no aparece, usa un valor cercano a 50 o más bajo según la evidencia.

Significado de los rasgos en el tono: """ + TRAIT_MEANING + """

Reglas:
- Devuelve exactamente un resultado por texto, en el mismo orden y con el mismo "id".
- "reason": una frase en español que explique qué rasgos dominan y por qué (menciona palabras o recursos del texto).
- No hagas diagnósticos ni juzgues a ninguna persona.
- Responde SOLO con JSON válido con este esquema:

{"texts": [{"id": 1,
            "scores": {"openness": 0, "conscientiousness": 0, "extraversion": 0, "agreeableness": 0, "neuroticism": 0},
            "reason": "..."}]}"""


def _parse_analysis(raw, n):
    rows = parse_json_text(raw)["texts"]
    if not isinstance(rows, list) or len(rows) != n:
        got = len(rows) if isinstance(rows, list) else 0
        raise ValueError(f"se esperaban {n} resultados y llegaron {got}")
    out = []
    for row in rows:
        scores = {k: max(0, min(100, int(round(float(row["scores"][k]))))) for k in KEYS}
        out.append({"scores": scores, "reason": str(row.get("reason") or "")})
    return out


def analyze_voice(texts, target, threshold=80, brand="", api_key=None):
    """
    Analiza los textos y calcula alineación, brechas y textos fuera de voz.
    `target` son porcentajes por rasgo que suman 100.
    """
    if not texts:
        raise RuntimeError("Pega al menos un texto para analizar.")
    if sum(target.values()) != 100:
        raise RuntimeError("La voz objetivo debe sumar 100 %.")

    prompt = f"Marca: {brand or 'sin nombre'}\n\nTEXTOS:\n" + "\n".join(
        f"[{i}] {t}" for i, t in enumerate(texts, 1))
    rows, model = ask_json(SYSTEM_ANALYSIS, prompt, lambda raw: _parse_analysis(raw, len(texts)),
                           api_key=api_key)

    items = []
    for i, (text, row) in enumerate(zip(texts, rows), 1):
        pct = to_percentages(row["scores"])
        al = alignment(pct, target)
        items.append({"id": i, "text": text, "scores": row["scores"], "percentages": pct,
                      "alignment": al, "aligned": al >= threshold, "reason": row["reason"],
                      "gaps": gaps(pct, target)})

    overall_pct = to_percentages(_mean_scores(rows))
    return {
        "model": model,
        "threshold": threshold,
        "target": dict(target),
        "overall": {"percentages": overall_pct, "alignment": alignment(overall_pct, target),
                    "gaps": gaps(overall_pct, target)},
        "items": items,
        "flagged_ids": [it["id"] for it in items if not it["aligned"]],
    }


# ---------- Paso 2: reescrituras y guía de estilo ----------
SYSTEM_REWRITE = """Eres un redactor publicitario experto en voz de marca en español de Latinoamérica.
Recibirás la voz objetivo de la marca (porcentajes Big Five aplicados al tono), textos que se alejan de ella
y la diferencia por rasgo. Significado de los rasgos en el tono: """ + TRAIT_MEANING + """

Reglas:
- Reescribe SOLO los textos marcados, acercándolos a la voz objetivo. Conserva el mensaje, el idioma y una
  longitud parecida. No inventes datos (precios, promociones, fechas) que no estén en el texto original.
- "why": una frase que explique qué cambiaste del tono.
- Crea además una guía de estilo breve de la voz objetivo: resumen del tono, 4 a 5 hábitos recomendados ("do")
  y 4 a 5 cosas por evitar ("dont"), en frases cortas.
- Responde SOLO con JSON válido con este esquema:

{"rewrites": [{"id": 1, "rewrite": "...", "why": "..."}],
 "style_guide": {"tone_summary": "...", "do": ["..."], "dont": ["..."]}}"""


def _parse_rewrites(raw, flagged_ids):
    data = parse_json_text(raw)
    rewrites = []
    for r in data.get("rewrites") or []:
        rid = int(r["id"])
        if rid in flagged_ids and str(r.get("rewrite") or "").strip():
            rewrites.append({"id": rid, "rewrite": str(r["rewrite"]).strip(),
                             "why": str(r.get("why") or "")})
    guide = data["style_guide"]
    return {
        "rewrites": rewrites,
        "style_guide": {
            "tone_summary": str(guide.get("tone_summary") or ""),
            "do": [str(x) for x in (guide.get("do") or [])][:6],
            "dont": [str(x) for x in (guide.get("dont") or [])][:6],
        },
    }


def suggest_rewrites(result, brand="", api_key=None):
    """Genera reescrituras de los textos fuera de voz y una guía de estilo."""
    flagged = [it for it in result["items"] if not it["aligned"]]
    flagged_ids = {it["id"] for it in flagged}

    lines = [f"Marca: {brand or 'sin nombre'}",
             f"Voz objetivo: {_target_text(result['target'])}", "", "TEXTOS MARCADOS PARA REESCRIBIR:"]
    if not flagged:
        lines.append("(ninguno: todos los textos están alineados; devuelve rewrites vacío y solo la guía de estilo)")
    for it in flagged:
        diff = ", ".join(f"{LABELS[k]} {it['gaps'][k]:+d}" for k in KEYS)
        lines.append(f"[{it['id']}] {it['text']}\n    Diferencia vs objetivo (puntos): {diff}")

    extras, model = ask_json(SYSTEM_REWRITE, "\n".join(lines),
                             lambda raw: _parse_rewrites(raw, flagged_ids),
                             api_key=api_key, temperature=0.5)
    extras["model"] = model
    return extras


# ---------- Informe descargable ----------
def build_markdown_report(result, extras=None, brand=""):
    ov = result["overall"]
    out = [f"# Informe de voz de marca{': ' + brand if brand else ''}", "",
           f"**Alineación global con la voz objetivo: {ov['alignment']} %**  "
           f"(umbral: {result['threshold']} %)", "",
           "## Composición de la voz (suma 100 %)", "",
           "| Rasgo | Tu contenido | Objetivo | Diferencia |", "|---|---|---|---|"]
    for k in KEYS:
        out.append(f"| {LABELS[k]} | {ov['percentages'][k]} % | {result['target'][k]} % | {ov['gaps'][k]:+d} |")

    out += ["", "## Textos analizados", ""]
    for it in result["items"]:
        estado = "alineado" if it["aligned"] else "fuera de voz"
        out.append(f"- **[{it['id']}] {it['alignment']} % ({estado})**: {it['text']}")
        out.append(f"  - {it['reason']}")

    if extras:
        if extras["rewrites"]:
            out += ["", "## Reescrituras sugeridas", ""]
            for r in extras["rewrites"]:
                out.append(f"- **[{r['id']}]** {r['rewrite']}  \n  _{r['why']}_")
        g = extras["style_guide"]
        out += ["", "## Guía de estilo", "", g["tone_summary"], "", "**Sí:**"]
        out += [f"- {x}" for x in g["do"]]
        out += ["", "**No:**"] + [f"- {x}" for x in g["dont"]]

    out += ["", "---", "_Perfil de tono estimado por IA con el modelo Big Five. Es un método heurístico de "
            "marketing, no un test psicológico._"]
    return "\n".join(out)
