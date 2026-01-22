import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Inteligente Jaher", page_icon="🤖", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("Configura GITHUB_TOKEN y GOOGLE_API_KEY en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

# --- FUNCIONES DE APOYO ---
def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        return json.loads(base64.b64decode(data['content']).decode('utf-8')), data['sha']
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {"message":"Update","content":base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),"sha":sha}
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        i = texto.find("[")
        if i == -1: i = texto.find("{")
        f = texto.rfind("]") + 1
        if f <= 0: f = texto.rfind("}") + 1
        return texto[i:f]
    except: return ""

# --- INTERFAZ ---
st.title("🤖 Asistente de Inventario Inteligente")

t1, t2, t3, t4 = st.tabs(["📝 Registrar Equipo", "💬 Chat con la IA", "🗑️ Gestionar Borrado", "📊 Historial"])

# --- TAB 1: REGISTRAR CON AUTO-CORRECCIÓN ---
with t1:
    st.subheader("Entrada de Inventario con IA")
    txt = st.text_area("Describe el ingreso (La IA corregirá tu ortografía):", placeholder="ej: llega una latop del con su cargador desde manta")
    
    if st.button("✨ Procesar e Ingresar"):
        if txt:
            client = genai.Client(api_key=API_KEY)
            prompt = f"""
            Actúa como un experto en inventarios. Analiza: "{txt}"
            1. Corrige la ortografía y gramática (ej: 'latop' -> 'Laptop', 'manta' -> 'Manta').
            2. Devuelve los datos en este formato JSON exacto:
            [{{'serie': '...', 'equipo': '...', 'accion': '...', 'ubicacion': '...', 'reporte': '...'}}]
            JSON:
            """
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            datos_ia = json.loads(extraer_json(resp.text))
            
            fecha = obtener_fecha_ecuador()
            if isinstance(datos_ia, dict): datos_ia = [datos_ia]
            for d in datos_ia: d["fecha"] = fecha
            
            if enviar_buzon(datos_ia):
                st.success(f"✅ Registrado correctamente. Texto corregido por la IA.")
                st.json(datos_ia)

# --- TAB 2: CHAT INTELIGENTE ---
with t2:
    st.subheader("Pregúntame lo que sea sobre el Inventario")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt_chat := st.chat_input("¿Cuántos equipos hay en Manta?"):
        st.session_state.messages.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"):
            st.markdown(prompt_chat)

        # Consultar historial para darle contexto a la IA
        historial, _ = obtener_github(FILE_HISTORICO)
        contexto = json.dumps(historial, indent=2)
        
        full_prompt = f"Contexto de Inventario:\n{contexto}\n\nPregunta: {prompt_chat}\nResponde de forma amable y profesional."
        
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=full_prompt)
        
        with st.chat_message("assistant"):
            st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

# --- TAB 3: BORRADO SEGURO ---
with t3:
    st.subheader("Eliminación de Equipos")
    borrar_txt = st.text_input("Dime qué serie quieres eliminar:")
    if st.button("🗑️ Enviar Orden de Borrado"):
        if borrar_txt:
            orden = [{"serie": borrar_txt, "accion": "borrar"}]
            if enviar_buzon(orden):
                st.warning(f"Orden de borrado para '{borrar_txt}' enviada. Se procesará en 20 segundos.")

# --- TAB 4: VISUALIZACIÓN ---
with t4:
    if st.button("🔄 Cargar Tabla Actualizada"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos:
            df = pd.DataFrame(datos)
            st.dataframe(df, use_container_width=True)
