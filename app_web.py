import streamlit as st
from openai import OpenAI
import json
import pandas as pd
import datetime
import time
import io

# Importaciones de los otros archivos
from github_utils import *
from hardware_utils import *
from ai_logic import *
from glpi_utils import *

# CONFIGURACIÓN
st.set_page_config(page_title="LAIA v91.2", page_icon="🧠", layout="wide")

# Estilos simples para evitar errores de sintaxis
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
</style>
""", unsafe_allow_html=True)

# CREDENCIALES
try:
    API_KEY = st.secrets["GPT_API_KEY"]
    client = OpenAI(api_key=API_KEY)
    FILE_BUZON, FILE_HISTORICO, FILE_LECCIONES = "buzon.json", "historico.json", "lecciones.json"
except Exception as e:
    st.error(f"❌ Error de configuración: {}")
    st.stop()

# ESTADO DE SESIÓN
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
                if not msg_laia: msg_laia = "Instrucción técnica procesada."
                
                st.session_state.messages.append({"role": "assistant", "content": msg_laia})
                with st.chat_message("assistant"): st.markdown(msg_laia)

                if "items" in res_json and res_json["items"]:
                    nuevos_items = res_json["items"]
                    dict_actual = { (i.get('serie') or i.get('modelo') or i.get('equipo')): i for i in st.session_state.draft }
                    for item in nuevos_items:
                        key = item.get('serie') or item.get('modelo') or item.get('equipo')
                        dict_actual[key] = item
                    st.session_state.draft = list(dict_actual.values())
                    st.session_state.status = res_json.get("status", "QUESTION")
                    if st.session_state.status == "READY": st.rerun()
        except Exception as e:
            st.error(f"Error en el motor de LAIA: {str(e)}")

    if st.session_state.draft:
        st.divider()
        st.subheader("📊 Borrador de Movimientos")
        for d in st.session_state.draft:
            if extraer_gen(d.get("procesador", "")) == "obsoleto":
                d["estado"] = "Obsoleto / Pendiente Chatarrización"
                d["destino"] = "CHATARRA / BAJA"
        
        df_editor = pd.DataFrame(st.session_state.draft)
        cols_base = ["categoria_item", "equipo", "marca", "modelo", "serie", "cantidad", "estado", "tipo", "origen", "destino", "pasillo", "estante", "repisa", "guia", "fecha_llegada", "ram", "disco", "procesador", "reporte"]
        for c in cols_base:
            if c not in df_editor.columns: df_editor[c] = ""
        df_editor = df_editor.reindex(columns=cols_base).fillna("N/A")
        
        edited_df = st.data_editor(df_editor, num_rows="dynamic", use_container_width=True, key="editor_v12")
        if not df_editor.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        c1, c2 = st.columns([1, 4])
        forzar = c1.checkbox("🔓 Forzar")
        if st.session_state.status == "READY" or forzar:
            if c2.button("🚀 GUARDAR EN HISTÓRICO", type="primary", use_container_width=True):
                ahora = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                for d in st.session_state.draft: d["fecha_registro"] = ahora
                if enviar_github(FILE_BUZON, st.session_state.draft, "Registro LAIA"):
                    st.success("✅ ¡Guardado!"); st.session_state.draft = []; st.session_state.messages = []; st.session_state.status = "NEW"; time.sleep(1); st.rerun()

with t2:
    st.subheader("📊 Control de Stock e Historial")
    if st.button("🔄 Sincronizar"): st.rerun()
    hist, _ = obtener_github(FILE_HISTORICO)
    if hist:
        st_res, bod_res, danados_res, df_h = calcular_stock_web(pd.DataFrame(hist))
        k1, k2 = st.columns(2)
        k1.metric("📦 Periféricos en Stock", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos Totales", len(df_h))
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_h.to_excel(writer, index=False, sheet_name='Historial')
            if not st_res.empty: st_res.to_excel(writer, index=False, sheet_name='Stock')
            if not bod_res.empty: bod_res.to_excel(writer, index=False, sheet_name='BODEGA')
            if not danados_res.empty: danados_res.to_excel(writer, index=False, sheet_name='DAÑADOS')
        
        st.download_button("📥 DESCARGAR EXCEL", buffer.getvalue(), f"Inventario_{datetime.datetime.now().strftime('%d_%m')}.xlsx", type="primary")
        st.dataframe(df_h.tail(20), use_container_width=True)

with t3:
    st.subheader("Limpieza")
    st.info("Panel de limpieza inteligente activado.")
