import streamlit as st
import pandas as pd
import json

from ai_logic import client, SYSTEM_PROMPT, extraer_json
from github_utils import obtener_github, enviar_github
from inventory_engine import calcular_stock_web

st.set_page_config(layout="wide")

st.title("🧠 LAIA")

if "messages" not in st.session_state:
    st.session_state.messages = []

if prompt := st.chat_input("Describe movimiento..."):
    st.session_state.messages.append({"role":"user","content":prompt})

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":SYSTEM_PROMPT},
            {"role":"user","content":prompt}
        ]
    )

    raw = response.choices[0].message.content
    texto, js = extraer_json(raw)

    st.write(texto)
    if js:
        st.code(js, language="json")
