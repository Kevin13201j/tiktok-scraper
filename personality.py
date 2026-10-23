"""
personality.py
--------------
Motor de análisis Big Five (OCEAN) con la API GRATUITA de Gemini (Google AI Studio).

Sirve para dos cosas:
  1) Estimar el Big Five de una cuenta a partir de su biografía y descripciones
     (flujo del scraping):  python personality.py data/usuario/profile.json
  2) Ser el "motor" que usa el producto (brand_voice.py / app.py) mediante
     las funciones genéricas ask_json() y to_percentages().

La clave (token) se lee de la variable de entorno GEMINI_API_KEY o de un
archivo .env (que NUNCA se sube a GitHub). Nunca la escribas en el código.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://generativelanguage.googleapis.com/v1beta"

TRAITS = [
    ("openness", "Apertura a la experiencia"),
    ("conscientiousness", "Responsabilidad"),
    ("extraversion", "Extraversión"),
    ("agreeableness", "Amabilidad"),
    ("neuroticism", "Neuroticismo"),
]

SYSTEM_PROMPT = """Eres un asistente de psicología de la personalidad que ayuda en un trabajo universitario.
Estimas los Cinco Grandes rasgos (Big Five / OCEAN) a partir de textos que escribió una cuenta pública.

Reglas obligatorias:
- Basa cada puntaje SOLO en evidencia del texto recibido. Si no hay evidencia suficiente para un rasgo,
  usa un puntaje cercano a 50 y dilo en la explicación.
- Puntajes de 0 a 100 (0 = muy bajo, 50 = promedio, 100 = muy alto).
- Neuroticismo alto significa baja estabilidad emocional.
- No hagas diagnósticos clínicos ni menciones trastornos mentales.
- Recuerda que el texto puede haberlo escrito un equipo de comunicación y que refleja la imagen PÚBLICA,
  no necesariamente la personalidad real.
- En "evidence" parafrasea; si citas, máximo 12 palabras literales por cita.
- Responde en español y SOLO con JSON válido, sin texto extra, con exactamente este esquema:

{
  "traits": {
    "openness":          {"score": 0, "level": "bajo|medio|alto", "evidence": ["..."], "explanation": "..."},
    "conscientiousness": {"score": 0, "level": "bajo|medio|alto", "evidence": ["..."], "explanation": "..."},
    "extraversion":      {"score": 0, "level": "bajo|medio|alto", "evidence": ["..."], "explanation": "..."},
    "agreeableness":     {"score": 0, "level": "bajo|medio|alto", "evidence": ["..."], "explanation": "..."},
    "neuroticism":       {"score": 0, "level": "bajo|medio|alto", "evidence": ["..."], "explanation": "..."}
  },
  "summary": "resumen de 2 o 3 frases",
  "confidence": "baja|media|alta",
  "limitations": ["..."]
}"""


class GeminiError(Exception):
    def __init__(self, code, detail):
        super().__init__(f"HTTP {code}: {detail}")
        self.code = code


# ---------- Clave (token) ----------
def load_api_key():
    """Lee GEMINI_API_KEY del entorno o de un archivo .env en la carpeta actual."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    if os.path.exists(".env"):
        with open(".env", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


# ---------- Porcentajes que suman 100 ----------
def to_percentages(scores):
    """
    Convierte puntajes (0-100) en porcentajes ENTEROS que suman exactamente 100.
    porcentaje = puntaje / suma_de_puntajes * 100, y los decimales sobrantes se
    reparten con el método del "mayor resto" para que el total sea 100.
    """
    keys = list(scores)
    total = sum(max(0, scores[k] or 0) for k in keys)
    if total <= 0:  # sin información: reparto parejo
        base = 100 // len(keys)
        out = {k: base for k in keys}
        out[keys[0]] += 100 - base * len(keys)
        return out
    raw = {k: max(0, scores[k] or 0) / total * 100 for k in keys}
    out = {k: int(raw[k]) for k in keys}
    remainder = 100 - sum(out.values())
    for k in sorted(keys, key=lambda x: raw[x] - out[x], reverse=True)[:remainder]:
        out[k] += 1
    return out


# ---------- Textos de una cuenta ----------
def build_corpus(profile):
    """Devuelve (lista de textos, cantidad de palabras): biografía + descripciones."""
    texts, seen = [], set()
    bio = (profile.get("bio") or "").strip()
    if bio:
        texts.append("BIOGRAFÍA: " + bio)
    for i, v in enumerate(profile.get("videos") or [], 1):
        d = (v.get("description") or "").strip()
        if d and d not in seen:
            seen.add(d)
            texts.append(f"VIDEO {i}: {d}")
    words = len(" ".join(texts).split())
    return texts, words


# ---------- Llamadas HTTP a Gemini ----------
def _http(url, key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if body is not None else "GET")
    req.add_header("x-goog-api-key", key)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise GeminiError(e.code, detail)
    except urllib.error.URLError as e:
        raise GeminiError(0, f"sin conexión ({e.reason})")


def pick_models(key):
    """
    Los nombres de modelos cambian con frecuencia. Si defines GEMINI_MODEL se usa ese;
    si no, se piden a la API los modelos 'flash' disponibles (primero los estables).
    """
    forced = os.environ.get("GEMINI_MODEL")
    if forced:
        return [forced]
    data = _http(f"{API}/models?pageSize=200", key)
    banned = ("image", "tts", "live", "audio", "embedding", "robotics", "computer")
    names = []
    for m in data.get("models", []):
        n = m.get("name", "").replace("models/", "")
        if ("flash" in n and "generateContent" in m.get("supportedGenerationMethods", [])
                and not any(b in n for b in banned)):
            names.append(n)
    stable = sorted([n for n in names if not re.search(r"preview|exp|latest", n)], reverse=True)
    others = sorted([n for n in names if n not in stable], reverse=True)
    return (stable + others)[:4]


def _generate(model, key, system_prompt, user_text, temperature=0.2):
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
    }
    data = _http(f"{API}/models/{model}:generateContent", key, body)
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def parse_json_text(raw):
    """Convierte la respuesta de la IA en un diccionario (quita ```json si lo trae)."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw)


def ask_json(system_prompt, user_text, validator, api_key=None, temperature=0.2):
    """
    Pregunta a Gemini y devuelve (resultado_validado, modelo_usado).
    Prueba hasta 4 modelos; si uno falla o responde mal, pasa al siguiente.
    `validator` convierte el texto JSON en el resultado final (o lanza ValueError).
    """
    key = api_key or load_api_key()
    if not key:
        raise RuntimeError(
            "Falta la clave de Gemini. Defínela con:  $env:GEMINI_API_KEY=\"tu_clave\"  "
            "o crea un archivo .env con la línea GEMINI_API_KEY=tu_clave"
        )
    try:
        models = pick_models(key)
    except GeminiError as e:
        raise RuntimeError(f"No se pudo consultar la API de Gemini ({e}). Revisa tu clave y tu conexión.")

    errors = []
    for model in models:
        try:
            raw = _generate(model, key, system_prompt, user_text, temperature)
            return validator(raw), model
        except GeminiError as e:
            errors.append(f"{model} -> {e}")
            if e.code == 429:
                time.sleep(20)
        except (KeyError, IndexError, TypeError, ValueError) as e:
            errors.append(f"{model} -> respuesta no válida ({e})")
    raise RuntimeError("No se pudo obtener el análisis. Detalles: " + " | ".join(errors))


# ---------- Validación de la respuesta Big Five ----------
def _level(score):
    return "bajo" if score < 40 else ("alto" if score > 60 else "medio")


def _parse(raw):
    data = parse_json_text(raw)
    traits = {}
    for key, _ in TRAITS:
        t = data["traits"][key]
        score = max(0, min(100, int(round(float(t["score"])))))
        traits[key] = {
            "score": score,
            "level": _level(score),  # se recalcula para que sea coherente con el puntaje
            "evidence": [str(x) for x in (t.get("evidence") or [])][:4],
            "explanation": str(t.get("explanation") or ""),
        }
    return {
        "traits": traits,
        # Porcentajes que suman 100 (composición del perfil). El puntaje original se conserva.
        "percentages": to_percentages({k: traits[k]["score"] for k, _ in TRAITS}),
        "summary": str(data.get("summary") or ""),
        "confidence": str(data.get("confidence") or "baja").lower(),
        "limitations": [str(x) for x in (data.get("limitations") or [])],
    }


# ---------- Análisis de una cuenta ----------
def analyze(profile, api_key=None):
    texts, words = build_corpus(profile)
    if not texts:
        raise RuntimeError("No hay textos (biografía o descripciones) para analizar.")

    prompt = "Estos son los textos públicos de la cuenta:\n\n" + "\n".join(texts)
    result, model = ask_json(SYSTEM_PROMPT, prompt, _parse, api_key=api_key)

    if words < 150:
        result["confidence"] = "baja"
        result["limitations"].append(
            f"Solo se analizaron {words} palabras: es muy poco texto para un Big Five fiable."
        )
    result["model"] = model
    result["texts_used"] = len(texts)
    result["words_used"] = words
    result["generated_at"] = datetime.now(timezone.utc).isoformat()
    return result


def print_summary(result):
    print("\n=== BIG FIVE (estimación) ===")
    pcts = result.get("percentages") or to_percentages(
        {k: result["traits"][k]["score"] for k, _ in TRAITS})
    for key, label in TRAITS:
        t = result["traits"][key]
        bar = "█" * (t["score"] // 5)
        print(f"{label:<26} {t['score']:>3}/100  {pcts[key]:>3} %  {bar} ({t['level']})")
    print(f"{'Suma de porcentajes':<26} {'':>9} {sum(pcts.values()):>3} %")
    print(f"\nResumen: {result['summary']}")
    print(f"Confianza: {result['confidence']} | Textos: {result['texts_used']} | "
          f"Palabras: {result['words_used']} | Modelo: {result['model']}")
    print("Aviso: estimación orientativa de la imagen pública, no un test psicológico.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python personality.py data/usuario/profile.json")
        sys.exit(1)
    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        profile = json.load(f)
    try:
        profile["personality"] = analyze(profile)
    except RuntimeError as e:
        print(f"[!] {e}")
        sys.exit(1)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    print_summary(profile["personality"])

    from report import generate_html, open_in_browser
    out = os.path.join(os.path.dirname(path), "reporte.html")
    generate_html(profile, out)
    print(f"\nReporte actualizado: {out}")
    open_in_browser(out)
