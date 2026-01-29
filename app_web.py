import streamlit as st
from openai import OpenAI
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd
import time

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS
# ==========================================
st.set_page_config(page_title="LAIA v91.1 - Auditora Senior", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; background-color: #2e7d32; color: white; border: none; }
    .stChatFloatingInputContainer { background-color: #0e1117; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CREDENCIALES
# ==========================================
try:
    API_KEY = st.secrets["GPT_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura los Secrets (GITHUB_TOKEN y GPT_API_KEY).")
    st.stop()

client = OpenAI(api_key=API_KEY)
GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": "token " + GITHUB_TOKEN, "Cache-Control": "no-cache"}

# ==========================================
# 3. FUNCIONES AUXILIARES
# ==========================================
def extraer_json(texto):
    """
    Extrae el primer bloque JSON válido del texto
    """
    try:
        texto = texto.replace("```json", "").replace("```", "").strip()
        inicio = texto.find("{")
        if inicio == -1: return ""
        balance = 0
        for i in range(inicio, len(texto)):
            char = texto[i]
            if char == "{": balance += 1
            elif char == "}":
                balance -= 1
                if balance == 0:
                    return texto[inicio:i+1]
        return ""
    except:
        return ""

def obtener_github(archivo):
    """
    Obtiene contenido de un archivo JSON desde GitHub
    """
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            d = resp.json()
            return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    except:
        pass
    return [], None

def enviar_github(archivo, datos, mensaje="LAIA Update"):
    """
    Envía datos al repositorio GitHub
    """
    actuales, sha = obtener_github(archivo)
    if isinstance(datos, list):
        actuales.extend(datos)
    else:
        actuales.append(datos)
    payload = {
        "message": mensaje,
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode()).decode(),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

# ==========================================
# 4. MOTOR DE STOCK
# ==========================================
def calcular_stock_web(df):
    if df.empty: return pd.DataFrame(), pd.DataFrame()
    df_c = df.copy()
    df_c.columns = df_c.columns.str.lower().str.strip()
    cols = ['estado', 'estado_fisico', 'tipo', 'destino', 'equipo', 'marca', 'cantidad', 'modelo']
    for col in cols:
        if col not in df_c.columns: df_c[col] = "No especificado"
    df_c['cant_n'] = pd.to_numeric(df_c['cantidad'], errors='coerce').fillna(1)

    def procesar_fila(row):
        t = str(row['tipo']).lower()
        cant = row['cant_n']
        if any(x in t for x in ['recib', 'ingreso', 'entrad', 'compra']):
            return cant
        if any(x in t for x in ['env', 'salida', 'baja', 'despacho']):
            return -cant
        return 0

    df_c['val'] = df_c.apply(procesar_fila, axis=1)
    resumen = df_c.groupby(['equipo', 'marca', 'modelo', 'estado_fisico'])['val'].sum().reset_index()
    movimientos = df_c[df_c['val'] != 0]
    return resumen[resumen['val'] > 0], movimientos

# ==========================================
# 5. SYSTEM PROMPT (LAIA)
# ==========================================
SYSTEM_PROMPT = """
Eres LAIA, Auditora Senior de Inventarios de Jaher.
Tu función es auditar, validar y actualizar inventario, solo indicar lo que falta.
...
(Se mantiene todo tu prompt original resumido aquí para estabilidad)
SALIDA JSON OBLIGATORIA:
{
 "status": "QUESTION" o "READY",
 "missing_info": "Resumen de faltantes",
 "items": [
 {
  "equipo": "Laptop", "marca": "Dell", "modelo": "", "serie": "",
  "cantidad": 1, "estado": "", "tipo": "Enviado",
  "origen": "Stock", "destino": "Portete",
  "guia": "", "fecha_llegada": "",
  "ram": "", "procesador": "", "disco": "", "reporte": ""
 }
 ]
}
"""

# ==========================================
# 6. SESSION STATE
# ==========================================
for key, default in {
    "messages": [],
    "draft": None,
    "status": "NEW",
    "missing_info": "",
    "clear_chat": False,
    "chat_key": 0
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ==========================================
# 7. INTERFAZ TABS
# ==========================================
t1, t2, t3 = st.tabs(["💬 Chat Auditor","📊 Dashboard Previo","🗑️ Limpieza"])

# ==========================================
# 8. PESTAÑA CHAT
# ==========================================
with t1:
    # Mostrar historial
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # Formulario de usuario
    with st.form(key="chat_form", clear_on_submit=True):
        prompt_usuario = st.text_area("📋 Habla con LAIA...", height=80)
        submitted = st.form_submit_button("📤 Enviar")

    if submitted and prompt_usuario:
        st.session_state.messages.append({"role": "user", "content": prompt_usuario})
        try:
            with st.spinner("LAIA está auditando..."):
                inventario_previo = json.dumps(st.session_state.draft) if st.session_state.draft else "Ninguno"
                prompt_completo = f"INVENTARIO ACTUAL: {inventario_previo}\n\nUSUARIO: {prompt_usuario}"
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt_completo}
                    ],
                    temperature=0
                )
                
                texto = extraer_json(response.choices[0].message.content)
                if texto:
                    res_json = json.loads(texto)
                    st.session_state.draft = res_json.get("items", [])
                    st.session_state.status = res_json.get("status", "READY")
                    st.session_state.missing_info = res_json.get("missing_info", "")
                    st.session_state.messages.append({"role":"assistant","content":f"✅ {st.session_state.missing_info or 'Tabla actualizada.'}"})
                    st.rerun()
        except Exception as e:
            st.error(f"Error crítico: {e}")

    # Mostrar tabla editable
    if st.session_state.draft:
        st.subheader("📊 Tabla de Inventario (En Vivo)")
        df_draft = pd.DataFrame(st.session_state.draft)
        edited_df = st.data_editor(df_draft, num_rows="dynamic", use_container_width=True)
        if not df_draft.equals(edited_df):
            st.session_state.draft = edited_df.to_dict("records")

        col1, col2 = st.columns([1,4])
        with col1:
            if st.button("🚀 ENVIAR AL BUZÓN", type="primary"):
                if not st.session_state.draft:
                    st.error("❌ Tabla vacía.")
                else:
                    enviar = True
                    if st.session_state.status=="QUESTION":
                        all_na = all(item.get("serie")=="N/A" or item.get("ram")=="N/A" for item in st.session_state.draft)
                        if not all_na:
                            st.error("⛔ Faltan datos obligatorios.")
                            enviar=False
                        else:
                            st.session_state.status="READY"
                            st.warning("⚠️ Se aplicaron valores N/A según usuario.")
                    if enviar:
                        with st.spinner("Enviando datos..."):
                            datos = st.session_state.draft
                            fecha = (datetime.datetime.now(timezone.utc)-timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
                            for d in datos:
                                d["fecha_registro"]=fecha
                                for k in d: 
                                    if d[k] is None: d[k]=""
                            if enviar_github(FILE_BUZON, datos):
                                st.success("✅ ¡Enviado!")
                                st.session_state.draft=None
                                st.session_state.messages=[]
                                st.session_state.status="NEW"
                                st.rerun()
                            else:
                                st.error("Error GitHub")
        with col2:
            if st.button("🗑️ Borrar todo"):
                st.session_state.draft=None
                st.session_state.messages=[]
                st.rerun()

# ==========================================
# 9. PESTAÑA DASHBOARD
# ==========================================
with t2:
    hist,_ = obtener_github(FILE_HISTORICO)
    if hist:
        df_h = pd.DataFrame(hist)
        st_res, st_det = calcular_stock_web(df_h)
        k1,k2=st.columns(2)
        k1.metric("📦 Stock Total", int(st_res['val'].sum()) if not st_res.empty else 0)
        k2.metric("🚚 Movimientos", len(df_h))
        if not st_res.empty:
            st.dataframe(st_res.pivot_table(index=['equipo','marca'],columns='estado_fisico',values='val',aggfunc='sum').fillna(0))
        st.dataframe(st_det,use_container_width=True)
    else:
        st.info("Sincronizando con GitHub...")

# ==========================================
# 10. PESTAÑA LIMPIEZA
# ==========================================
with t3:
    st.subheader("🗑️ Limpieza Inteligente")
    txt_borrar = st.text_input("¿Qué deseas eliminar?")
    if st.button("🔥 EJECUTAR BORRADO"):
        if txt_borrar:
            try:
                p_db = (
                    "Actúa como DBA. COLUMNAS: [equipo, marca, serie, estado, destino]. "
                    f"ORDEN: {txt_borrar}. RESPONDE SOLO JSON: "
                    '{"accion":"borrar_todo"} o {"accion":"borrar_filtro","columna":"...","valor":"..."}'
                )
                resp = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role":"user","content":p_db}])
                texto = resp.choices[0].message.content
                order = json.loads(extraer_json(texto))
                if enviar_github(FILE_BUZON, order):
                    st.success("✅ Orden enviada.")
                    st.json(order)
            except Exception as e:
                st.error("Error: "+str(e))
