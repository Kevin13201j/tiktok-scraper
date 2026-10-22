"""
personality.py
--------------
Estimación del perfil de personalidad Big Five (OCEAN) a partir de los TEXTOS
que escribe la cuenta (biografía + descripciones de sus videos), usando la API
GRATUITA de Gemini (Google AI Studio).

Por qué estos textos y no los comentarios:
  - Los comentarios los escriben OTRAS personas (la audiencia), no el dueño
    de la cuenta; mezclarlos daría un resultado sin sentido.

Uso:
    # 1) Dentro del flujo completo
    python main.py usuario --bigfive

    # 2) Sobre datos ya guardados (sin repetir el scraping)
    python personality.py data/usuario/profile.json

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


# ---------- Textos a analizar ----------
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


def _generate(model, key, user_text):
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    data = _http(f"{API}/models/{model}:generateContent", key, body)
    parts = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


# ---------- Validación de la respuesta ----------
def _level(score):
    return "bajo" if score < 40 else ("alto" if score > 60 else "medio")


def _parse(raw):
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    data = json.loads(raw)
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
        "summary": str(data.get("summary") or ""),
        "confidence": str(data.get("confidence") or "baja").lower(),
        "limitations": [str(x) for x in (data.get("limitations") or [])],
    }


# ---------- Función principal ----------
def analyze(profile):
    key = load_api_key()
    if not key:
        raise RuntimeError(
            "Falta la clave de Gemini. Defínela con:  $env:GEMINI_API_KEY=\"tu_clave\"  "
            "o crea un archivo .env con la línea GEMINI_API_KEY=tu_clave"
        )
    texts, words = build_corpus(profile)
    if not texts:
        raise RuntimeError("No hay textos (biografía o descripciones) para analizar.")

    prompt = "Estos son los textos públicos de la cuenta:\n\n" + "\n".join(texts)
    errors = []
    for model in pick_models(key):
        try:
            result = _parse(_generate(model, key, prompt))
        except GeminiError as e:
            errors.append(f"{model} -> {e}")
            if e.code == 429:
                time.sleep(20)
            continue
        except (KeyError, IndexError, TypeError, ValueError) as e:
            errors.append(f"{model} -> respuesta no válida ({e})")
            continue

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

    raise RuntimeError("No se pudo obtener el análisis. Detalles: " + " | ".join(errors))


def print_summary(result):
    print("\n=== BIG FIVE (estimación) ===")
    for key, label in TRAITS:
        t = result["traits"][key]
        bar = "█" * (t["score"] // 5)
        print(f"{label:<26} {t['score']:>3}/100  {bar} ({t['level']})")
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
