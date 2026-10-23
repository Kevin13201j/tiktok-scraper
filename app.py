"""
app.py
------
Interfaz web del producto "Afinador de voz de marca" (Streamlit).
Permite analizar textos pegados a mano o cargar datos de perfiles de TikTok ya scrapeados.
"""
import glob
import json
import os

import pandas as pd
import streamlit as st

from brand_voice import (KEYS, LABELS, MAX_CHARS, MAX_TEXTS, PRESETS, analyze_voice,
                         build_markdown_report, clean_texts, suggest_rewrites)
from personality import load_api_key


def show_table(df):
    """Muestra una tabla ancha compatible con versiones nuevas y antiguas de Streamlit."""
    try:
        st.dataframe(df, hide_index=True, width="stretch")
    except TypeError:
        st.dataframe(df, hide_index=True, use_container_width=True)


st.set_page_config(page_title="Afinador de voz de marca", page_icon="🎯", layout="wide")
st.title("🎯 Afinador de voz de marca")
st.caption("Mide cómo suena tu contenido y qué tanto se parece a la voz que quieres transmitir.")

# Clave detectada del archivo .env
env_key = load_api_key()

# ---------------- Barra lateral: configuración ----------------
with st.sidebar:
    st.header("Configuración")
    brand = st.text_input("Nombre de la marca")
    
    api_key_input = st.text_input(
        "Clave de Gemini (opcional si ya está en .env)",
        value=env_key or "",
        type="password",
        help="Consíguela gratis en aistudio.google.com"
    )
    final_api_key = api_key_input.strip() or env_key

    st.subheader("Voz objetivo")
    preset = st.selectbox("Voz que quieres transmitir", list(PRESETS) + ["Personalizada"])
    if preset == "Personalizada":
        st.caption("Reparte 100 % entre los cinco rasgos.")
        target = {k: st.slider(LABELS[k], 0, 100, 20, key="target_" + k) for k in KEYS}
    else:
        target = dict(PRESETS[preset])
        show_table(pd.DataFrame({"Rasgo": [LABELS[k] for k in KEYS],
                                 "%": [target[k] for k in KEYS]}))

    total = sum(target.values())
    if total == 100:
        st.success("La voz objetivo suma 100 %.")
    else:
        st.error(f"Los porcentajes suman {total} %. Deben sumar 100 %.")

    threshold = st.slider("Alineación mínima aceptable (%)", 50, 95, 80)
    st.caption("Neuroticismo = tono tenso o negativo. En una marca normalmente se busca bajo.")

# ---------------- Selección de fuente de datos ----------------
st.subheader("1. Contenido a auditar")
tab_saved, tab_manual = st.tabs(["📂 Cargar desde TikTok (datos guardados)", "✍️ Pegar textos manualmente"])

if "extracted_texts" not in st.session_state:
    st.session_state["extracted_texts"] = ""

# Buscar perfiles guardados en la carpeta data/
available_profiles = glob.glob("data/*/profile.json")

with tab_saved:
    st.write("Selecciona una cuenta scrapeada para cargar su biografía y las descripciones de sus videos:")
    if available_profiles:
        profile_options = {p.replace("\\", "/").split("/")[1]: p for p in available_profiles}
        selected_account = st.selectbox("Cuenta disponible", list(profile_options.keys()))
        
        if st.button("Cargar textos de esta cuenta"):
            path = profile_options[selected_account]
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                texts_list = []
                bio = (data.get("bio") or "").strip()
                if bio:
                    texts_list.append(f"Biografía: {bio}")
                
                for v in data.get("videos") or []:
                    desc = (v.get("description") or "").strip()
                    if desc:
                        texts_list.append(desc)
                
                if texts_list:
                    st.session_state["extracted_texts"] = "\n\n".join(texts_list[:MAX_TEXTS])
                    st.success(f"¡Se cargaron {len(texts_list[:MAX_TEXTS])} textos de @{selected_account}!")
                else:
                    st.warning("Ese perfil no contiene descripciones ni biografía.")
            except Exception as e:
                st.error(f"Error al leer el archivo: {e}")
    else:
        st.info("No se encontraron carpetas dentro de 'data/'. Ejecuta primero main.py para scrapear una cuenta.")

with tab_manual:
    st.write("Escribe o edita los textos directamente:")

texts_raw = st.text_area(
    f"Textos a evaluar (separados por línea en blanco; máx. {MAX_TEXTS} textos de {MAX_CHARS} caracteres):",
    value=st.session_state["extracted_texts"],
    height=220,
    placeholder="Pega aquí textos o cárgalos desde la pestaña de datos guardados..."
)

# ---------------- Botón de análisis ----------------
if st.button("Analizar voz", type="primary", disabled=(total != 100)):
    if not final_api_key:
        st.error("Falta la clave de Gemini. Ingrésala en la barra lateral o en tu archivo .env.")
    else:
        texts = clean_texts(texts_raw)
        if not texts:
            st.error("Pega o carga al menos un texto.")
        else:
            if len(texts) < 3:
                st.warning("Con menos de 3 textos el resultado es poco fiable.")
            try:
                with st.spinner("Analizando el tono de tus textos con Gemini..."):
                    st.session_state["result"] = analyze_voice(
                        texts, target, threshold, brand=brand, api_key=final_api_key
                    )
                st.session_state.pop("extras", None)
            except RuntimeError as e:
                st.error(str(e))

# ---------------- Resultados ----------------
res = st.session_state.get("result")
if res:
    overall = res["overall"]
    n_ok = sum(1 for it in res["items"] if it["aligned"])

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Alineación global", f"{overall['alignment']} %")
    c2.metric("Textos alineados", f"{n_ok} de {len(res['items'])}")
    c3.metric("Textos fuera de voz", len(res["flagged_ids"]))

    st.subheader("Tu voz vs la voz objetivo (cada una suma 100 %)")
    df = pd.DataFrame(
        {"Tu contenido (%)": [overall["percentages"][k] for k in KEYS],
         "Voz objetivo (%)": [res["target"][k] for k in KEYS]},
        index=[LABELS[k] for k in KEYS])
    st.bar_chart(df)

    def diagnosis(diff):
        if diff >= 3:
            return f"Sobra ({diff:+d} pts)"
        if diff <= -3:
            return f"Falta ({diff:+d} pts)"
        return f"En línea ({diff:+d} pts)"

    show_table(pd.DataFrame({
        "Rasgo": [LABELS[k] for k in KEYS],
        "Tu contenido (%)": [overall["percentages"][k] for k in KEYS],
        "Objetivo (%)": [res["target"][k] for k in KEYS],
        "Diagnóstico": [diagnosis(overall["gaps"][k]) for k in KEYS]}))

    st.subheader("Análisis por texto")
    for it in res["items"]:
        icon = "✅" if it["aligned"] else "⚠️"
        with st.expander(f"{icon} Texto {it['id']} · alineación {it['alignment']} %"):
            st.write(it["text"])
            st.caption(it["reason"])
            st.write("Composición: " + " · ".join(
                f"{LABELS[k]} {it['percentages'][k]} %" for k in KEYS))

    st.divider()
    st.subheader("Reescrituras y guía de estilo")
    if st.button("Generar reescrituras y guía de estilo"):
        try:
            with st.spinner("Escribiendo propuestas..."):
                st.session_state["extras"] = suggest_rewrites(res, brand=brand, api_key=final_api_key)
        except RuntimeError as e:
            st.error(str(e))

    extras = st.session_state.get("extras")
    if extras:
        by_id = {it["id"]: it for it in res["items"]}
        if not extras["rewrites"]:
            st.info("Todos tus textos están alineados: no hay nada que reescribir.")
        for r in extras["rewrites"]:
            st.markdown(f"**Texto {r['id']}**")
            left, right = st.columns(2)
            left.markdown("*Original*")
            left.write(by_id[r["id"]]["text"])
            right.markdown("*Propuesta*")
            right.write(r["rewrite"])
            st.caption(r["why"])

        guide = extras["style_guide"]
        st.markdown("### Guía de estilo")
        st.write(guide["tone_summary"])
        g1, g2 = st.columns(2)
        g1.markdown("**Sí**\n" + "\n".join(f"- {x}" for x in guide["do"]))
        g2.markdown("**No**\n" + "\n".join(f"- {x}" for x in guide["dont"]))

    st.download_button("Descargar informe (Markdown)",
                       data=build_markdown_report(res, extras, brand),
                       file_name="informe_voz_de_marca.md", mime="text/markdown")
    st.download_button("Descargar datos (JSON)",
                       data=json.dumps({"analisis": res, "propuestas": extras}, ensure_ascii=False, indent=2),
                       file_name="voz_de_marca.json", mime="application/json")

st.divider()
st.caption("Perfil de tono estimado por IA con el modelo Big Five. Es un método heurístico de marketing, "
           "no un test psicológico. Revisa siempre las propuestas antes de publicar.")