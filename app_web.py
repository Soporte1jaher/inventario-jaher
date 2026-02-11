import streamlit as st
import pandas as pd
import json
import datetime
import time

# Importaciones de tus archivos
from github_utils import obtener_github, enviar_github
from hardware_utils import extraer_gen
from ai_logic import extraer_json, client, SYSTEM_PROMPT
from inventory_engine import calcular_stock_web
from glpi_utils import solicitar_busqueda_glpi, revisar_respuesta_glpi

st.set_page_config(page_title="LAIA v91.2", layout="wide")

if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = []
if "status" not in st.session_state: st.session_state.status = "NEW"

t1, t2, t3 = st.tabs(["💬 Chat", "📊 Stock", "🗑️ Limpieza"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Escribe aquí..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.spinner("LAIA pensando..."):
            ctx = json.dumps(st.session_state.draft)
            msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"ESTADO: {ctx}"}]
            msgs.extend(st.session_state.messages[-5:])
            
            res = client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
            txt, js_txt = extraer_json(res.choices[0].message.content)
            
            if js_txt:
                data = json.loads(js_txt)
                st.session_state.draft = data.get("items", [])
                st.session_state.status = data.get("status", "QUESTION")
                st.session_state.messages.append({"role": "assistant", "content": data.get("missing_info", "OK")})
                st.rerun()

    if st.session_state.draft:
        df = pd.DataFrame(st.session_state.draft)
        st.data_editor(df, key="editor_final")
        if st.button("🚀 GUARDAR"):
            if enviar_github("buzon.json", st.session_state.draft):
                st.success("Guardado"); st.session_state.draft = []; st.rerun()

with t2:
    hist, _ = obtener_github("historico.json")
    if hist:
        s, b, d, h = calcular_stock_web(pd.DataFrame(hist))
        st.write("Historial", h.tail(10))

with t3:
    st.write("Panel de limpieza")
