import streamlit as st
from openai import OpenAI
import json
import pandas as pd
import datetime
import time
import io

# Importaciones de nuestros módulos locales
from github_utils import *
from hardware_utils import *
from ai_logic import *
from glpi_utils import *

# 1. CONFIGURACIÓN
st.set_page_config(page_title="LAIA v91.2 - Auditora Senior", page_icon="🧠", layout="wide")
st.markdown("<style>.stApp { background-color: #0e1117; color: #e0e0e0; } .stButton>button { width: 100%; border-radius: 10px; background-color: #2e7d32; color: white; }</style>", unsafe_allow_html=True)

# 2. CREDENCIALES
try:
    client = OpenAI(api_key=st.secrets["GPT_API_KEY"])
    FILE_BUZON, FILE_HISTORICO, FILE_LECCIONES = "buzon.json", "historico.json", "lecciones.json"
except:
    st.error("❌ Configura los Secrets.")
    st.stop()

# 3. SESIÓN
if "messages" not in st.session_state: st.session_state.messages = []
if "draft" not in st.session_state: st.session_state.draft = []
if "status" not in st.session_state: st.session_state.status = "NEW"

t1, t2, t3 = st.tabs(["💬 Chat Auditor", "📊 Stock Real", "🗑️ Limpieza"])

with t1:
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt := st.chat_input("Dime qué llegó o qué enviaste..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        try:
            with st.spinner("LAIA auditando..."):
                lecciones, _ = obtener_github(FILE_LECCIONES)
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False)
                
                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{}"},
                    {"role": "system", "content": f"ESTADO ACTUAL: {}"}
                ]
                for m in st.session_state.messages[-10:]: mensajes_api.append(m)

                response = client.chat.completions.create(model="gpt-4o-mini", messages=mensajes_api, temperature=0)
                texto_fuera, res_txt = extraer_json(response.choices[0].message.content)
                res_json = json.loads(res_txt) if res_txt else {}

                msg_laia = f"{}\n{res_json.get('missing_info', '')}".strip()
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"): st.markdown(msg_laia)

                if "items" in res_json:
                    dict_actual = { (i.get('serie') or i.get('modelo')): i for i in st.session_state.draft }
                    for item in res_json["items"]:
                        key = item.get('serie') or item.get('modelo')
                        dict_actual[key] = item
                    st.session_state.draft = list(dict_actual.values())
                    st.session_state.status = res_json.get("status", "QUESTION")
                    if st.session_state.status == "READY": st.rerun()
        except Exception as e:
            st.error(f"Error LAIA: {}")

    if st.session_state.draft:
        st.divider()
        for d in st.session_state.draft:
            if extraer_gen(d.get("procesador")) == "obsoleto":
                d["estado"], d["destino"] = "Obsoleto / Pendiente Chatarrización", "CHATARRA / BAJA"
        
        df_editor = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True)
        st.session_state.draft = edited_df.to_dict("records")

        c1, c2 = st.columns([1, 4])
        forzar = c1.checkbox("🔓 Forzar")
        if st.session_state.status == "READY" or forzar:
            if c2.button("🚀 GUARDAR EN HISTÓRICO", type="primary"):
                ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for d in st.session_state.draft: d["fecha_registro"] = ahora
                if enviar_github(FILE_BUZON, st.session_state.draft):
                    st.success("Guardado!"); st.session_state.draft = []; st.session_state.messages = []; st.rerun()

with t2:
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        st_res, bod_res, danados_res, df_h = calcular_stock_web(pd.DataFrame(hist))
        st.metric("📦 Periféricos en Stock", int(st_res['val'].sum()) if not st_res.empty else 0)
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_h.to_excel(writer, sheet_name='Historial')
            st_res.to_excel(writer, sheet_name='Stock')
            bod_res.to_excel(writer, sheet_name='Bodega')
            danados_res.to_excel(writer, sheet_name='Chatarra')
        st.download_button("📥 Descargar Excel", buffer.getvalue(), "Inventario.xlsx")
        st.dataframe(df_h.tail(20))


