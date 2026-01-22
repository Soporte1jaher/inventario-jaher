import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Inteligente Jaher", page_icon="🤖", layout="wide")

try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("Configura los Secrets en Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

def obtener_fecha_ecuador():
    return (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")

def obtener_github(archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{archivo}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        d = resp.json()
        return json.loads(base64.b64decode(d['content']).decode('utf-8')), d['sha']
    return [], None

def enviar_buzon(datos):
    if not isinstance(datos, list): datos = [datos]
    actuales, sha = obtener_github(FILE_BUZON)
    actuales.extend(datos)
    payload = {"message":"Web Update","content":base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),"sha":sha}
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
st.title("🤖 Asistente Jaher Inteligente")
t1, t2, t3, t4 = st.tabs(["📝 Registrar", "💬 Chat IA", "🗑️ Borrar", "📊 Historial"])

with t1:
    st.subheader("Ingreso de Equipos (Corrección Automática)")
    txt = st.text_area("Describe el equipo (la IA corregirá errores):")
    if st.button("✨ Procesar e Ingresar"):
        if txt:
            client = genai.Client(api_key=API_KEY)
            prompt = f"Corrige ortografía y devuelve JSON LISTA (serie, equipo, accion, ubicacion, reporte): {txt}"
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            datos_ia = json.loads(extraer_json(resp.text))
            if isinstance(datos_ia, dict): datos_ia = [datos_ia]
            fecha = obtener_fecha_ecuador()
            for d in datos_ia: d["fecha"] = fecha
            if enviar_buzon(datos_ia):
                st.success("✅ Registro enviado. La IA corrigió los textos.")

with t2:
    st.subheader("Chat sobre el Inventario")
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if prompt_chat := st.chat_input("¿Qué deseas saber?"):
        st.session_state.messages.append({"role": "user", "content": prompt_chat})
        with st.chat_message("user"): st.markdown(prompt_chat)
        
        historial, _ = obtener_github(FILE_HISTORICO)
        full_p = f"Datos inventario: {json.dumps(historial)}. Pregunta: {prompt_chat}"
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=full_p)
        
        with st.chat_message("assistant"): st.markdown(resp.text)
        st.session_state.messages.append({"role": "assistant", "content": resp.text})

with t3:
    st.subheader("Eliminar por Serie")
    ser_b = st.text_input("Escribe la serie exacta a eliminar:")
    if st.button("🗑️ Eliminar Equipo"):
        if ser_b:
            if enviar_buzon([{"serie": ser_b, "accion": "borrar"}]):
                st.warning(f"Orden de borrado para {ser_b} enviada.")

with t4:
    if st.button("🔄 Cargar Datos"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
