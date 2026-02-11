import streamlit as st
import pandas as pd
import json
import datetime
import time
import io
from github_utils import obtener_github, enviar_github, enviar_github_directo
from hardware_utils import extraer_gen
from ai_logic import extraer_json, aprender_leccion, client, SYSTEM_PROMPT
from inventory_engine import calcular_stock_web
from glpi_utils import solicitar_busqueda_glpi, revisar_respuesta_glpi

# Configuración y Estilos
st.set_page_config(page_title="LAIA v91.2 - Auditora Senior", page_icon="🧠", layout="wide")
st.markdown("<style>.stApp { background-color: #0e1117; color: #e0e0e0; }</style>", unsafe_allow_html=True)

# Variables de Estado
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
            with st.spinner("LAIA auditando información..."):
                lecciones, _ = obtener_github("lecciones.json")
                memoria_err = "\n".join([f"- {l['lo_que_hizo_mal']} -> {l['como_debe_hacerlo']}" for l in lecciones]) if lecciones else ""
                contexto_tabla = json.dumps(st.session_state.draft, ensure_ascii=False)
                
                mensajes_api = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "system", "content": f"LECCIONES TÉCNICAS:\n{memoria_err}"},
                    {"role": "system", "content": f"ESTADO ACTUAL: {contexto_tabla}"}
                ]
                for m in st.session_state.messages[-10:]: mensajes_api.append(m)

                response = client.chat.completions.create(model="gpt-4o-mini", messages=mensajes_api, temperature=0)
                texto_fuera, res_txt = extraer_json(response.choices[0].message.content)
                res_json = json.loads(res_txt) if res_txt else {}
                
                msg_laia = res_json.get("missing_info", "Instrucción técnica procesada.")
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"): st.markdown(msg_laia)

                if "items" in res_json:
                    st.session_state.draft = res_json["items"]
                    st.session_state.status = res_json.get("status", "QUESTION")
                    st.rerun()
        except Exception as e:
            st.error(f"Error: {str(e)}")

    if st.session_state.draft:
        st.divider()
        df_editor = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True)
        
        c1, c2 = st.columns([1, 4])
        with c1: forzar = st.checkbox("🔓 Forzar")
        with c2:
            if st.session_state.status == "READY" or forzar:
                if st.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):
                    ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                    for d in st.session_state.draft: d["fecha_registro"] = ahora
                    if enviar_github("buzon.json", st.session_state.draft, "Registro LAIA"):
                        st.success("✅ ¡Guardado!")
                        st.session_state.draft = []; st.session_state.messages = []; st.rerun()

with t2:
    st.subheader("📊 Control de Stock e Historial")
    hist, _ = obtener_github("historico.json")
    if hist:
        st_res, bod_res, danados_res, df_h = calcular_stock_web(pd.DataFrame(hist))
        st.metric("📦 Periféricos en Stock", int(st_res['val'].sum()) if not st_res.empty else 0)
        st.dataframe(df_h.tail(20), use_container_width=True)

with t3:
    st.subheader("🗑️ Limpieza")
    txt_borrar = st.text_input("¿Qué deseas eliminar?")
    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            order = {"accion": "borrar_filtro", "valor": txt_borrar}
            enviar_github("buzon.json", order, "Orden de Borrado")
            st.success("Orden enviada.")
