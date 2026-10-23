"""
Pruebas automáticas de la lógica del producto (no necesitan internet ni clave).

Ejecutar:   python -m unittest -v
"""
import json
import unittest
from unittest import mock

import brand_voice as bv
from personality import to_percentages


def fake_ask_json(payload):
    """Simula a la IA: devuelve el JSON dado, pasado por el validador real."""
    def _ask(system_prompt, user_text, validator, api_key=None, temperature=0.2):
        return validator(json.dumps(payload)), "modelo-falso"
    return _ask


class TestPercentages(unittest.TestCase):
    def test_siempre_suman_100(self):
        casos = [
            {"a": 62, "b": 81, "c": 70, "d": 75, "e": 30},
            {"a": 50, "b": 50, "c": 50, "d": 50, "e": 50},
            {"a": 1, "b": 1, "c": 1, "d": 0, "e": 0},
            {"a": 100, "b": 0, "c": 0, "d": 0, "e": 0},
            {"a": 0, "b": 0, "c": 0, "d": 0, "e": 0},
        ]
        for scores in casos:
            self.assertEqual(sum(to_percentages(scores).values()), 100, scores)

    def test_cada_porcentaje_cerca_del_exacto(self):
        scores = {"a": 62, "b": 81, "c": 70, "d": 75, "e": 30}
        total = sum(scores.values())
        for k, p in to_percentages(scores).items():
            self.assertLess(abs(p - scores[k] / total * 100), 1)

    def test_orden_se_conserva(self):
        p = to_percentages({"a": 10, "b": 80, "c": 10})
        self.assertGreater(p["b"], p["a"])


class TestAlignment(unittest.TestCase):
    def test_voz_identica_es_100(self):
        t = bv.PRESETS["Cercana y divertida"]
        self.assertEqual(bv.alignment(t, t), 100.0)

    def test_voz_opuesta_es_0(self):
        a = {k: 0 for k in bv.KEYS}
        b = {k: 0 for k in bv.KEYS}
        a["openness"], b["neuroticism"] = 100, 100
        self.assertEqual(bv.alignment(a, b), 0.0)

    def test_presets_suman_100(self):
        for nombre, preset in bv.PRESETS.items():
            self.assertEqual(sum(preset.values()), 100, nombre)


class TestTextos(unittest.TestCase):
    def test_separa_por_linea_en_blanco(self):
        self.assertEqual(bv.clean_texts("uno\n\n  dos  \n\n\n"), ["uno", "dos"])

    def test_limites(self):
        raw = "\n\n".join("x" * 2000 for _ in range(30))
        texts = bv.clean_texts(raw)
        self.assertEqual(len(texts), bv.MAX_TEXTS)
        self.assertTrue(all(len(t) <= bv.MAX_CHARS for t in texts))


class TestFlujoConIASimulada(unittest.TestCase):
    ANALISIS = {"texts": [
        {"id": 1, "scores": {"openness": 55, "conscientiousness": 30, "extraversion": 85,
                             "agreeableness": 80, "neuroticism": 15}, "reason": "Tono cálido y enérgico."},
        {"id": 2, "scores": {"openness": 10, "conscientiousness": 90, "extraversion": 10,
                             "agreeableness": 20, "neuroticism": 50}, "reason": "Tono formal y rígido."},
    ]}

    def test_marca_el_texto_fuera_de_voz(self):
        target = bv.PRESETS["Cercana y divertida"]
        with mock.patch.object(bv, "ask_json", fake_ask_json(self.ANALISIS)):
            res = bv.analyze_voice(["Hola, ¡pasa por tu café!", "Estimado cliente, se le informa..."],
                                   target, threshold=80)
        self.assertTrue(res["items"][0]["aligned"])
        self.assertFalse(res["items"][1]["aligned"])
        self.assertEqual(res["flagged_ids"], [2])
        self.assertEqual(sum(res["overall"]["percentages"].values()), 100)
        for it in res["items"]:
            self.assertEqual(sum(it["percentages"].values()), 100)

    def test_rechaza_objetivo_que_no_suma_100(self):
        mala = dict(bv.PRESETS["Cercana y divertida"], openness=50)
        with self.assertRaises(RuntimeError):
            bv.analyze_voice(["hola"], mala)

    def test_respuesta_con_cantidad_incorrecta_es_invalida(self):
        with self.assertRaises(ValueError):
            bv._parse_analysis(json.dumps(self.ANALISIS), 3)

    def test_reescrituras_solo_de_textos_marcados(self):
        target = bv.PRESETS["Cercana y divertida"]
        with mock.patch.object(bv, "ask_json", fake_ask_json(self.ANALISIS)):
            res = bv.analyze_voice(["Hola, ¡pasa por tu café!", "Estimado cliente, se le informa..."], target)
        propuesta = {"rewrites": [{"id": 2, "rewrite": "¡Hola! Te contamos el nuevo horario 😊", "why": "Más cercano"},
                                  {"id": 1, "rewrite": "no debería aparecer", "why": "x"}],
                     "style_guide": {"tone_summary": "Cálido.", "do": ["Saluda"], "dont": ["Frases rígidas"]}}
        with mock.patch.object(bv, "ask_json", fake_ask_json(propuesta)):
            extras = bv.suggest_rewrites(res, brand="Café Sol")
        self.assertEqual([r["id"] for r in extras["rewrites"]], [2])
        informe = bv.build_markdown_report(res, extras, "Café Sol")
        self.assertIn("Guía de estilo", informe)
        self.assertIn("Alineación global", informe)


if __name__ == "__main__":
    unittest.main()
