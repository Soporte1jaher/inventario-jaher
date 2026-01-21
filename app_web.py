import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

st.set_page_config(page_title="Inventario Jaher", layout="wide")

# --- CREDENCIALES ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Configura las llaves en los Secrets de Streamlit.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

def obtener_archivo_github(nombre_archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{nombre_archivo}"
    try:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(texto) if texto.strip() else [], sha
        return [], None
    except: return [], None

def enviar_al_buzon(lista_datos):
    """La Web SOLO escribe en el buzón, NUNCA en el histórico"""
    if not isinstance(lista_datos, list): lista_datos = [lista_datos]
    actuales, sha = obtener_archivo_github(FILE_BUZON)
    actuales.extend(lista_datos)
    payload = {
        "message": "Nueva orden desde Web",
        "content": base64.b64encode(json.dumps(actuales, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha
    }
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}"
    return requests.put(url, headers=HEADERS, json=payload).status_code in [200, 201]

def extraer_json(texto):
    try:
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin <= 0: fin = texto.rfind("}") + 1
        return texto[inicio:fin]
    except: return ""

# --- INTERFAZ ---
st.title("🌐 Inventario Inteligente Jaher")
tab1, tab2, tab3 = st.tabs(["📝 Registrar", "💬 Consultar/Borrar", "📊 Ver Historial"])

with tab1:
    st.subheader("Registrar Movimiento")
    texto_input = st.text_area("Describe el equipo:")
    if st.button("Procesar y Enviar"):
        client = genai.Client(api_key=API_KEY)
        prompt = f"Analiza y devuelve JSON lista: {texto_input}"
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
        datos = json.loads(extraer_json(resp.text))
        # Fecha Ecuador
        fecha_ec = (datetime.datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        if isinstance(datos, dict): datos = [datos]
        for d in datos: d["fecha"] = fecha_ec
        
        if enviar_al_buzon(datos):
            st.success("✅ Orden enviada. Tu PC la procesará en segundos.")

with tab2:
    st.subheader("IA y Borrado")
    pregunta = st.text_input("¿Qué deseas hacer? (Ej: Borra la serie 12345)")
    if st.button("Ejecutar"):
        historial, _ = obtener_archivo_github(FILE_HISTORICO)
        contexto = json.dumps(historial)
        prompt = f"Datos: {contexto}. Si el usuario quiere BORRAR, responde JSON: [{{'serie': '...', 'accion': 'borrar'}}]. Usuario: {pregunta}"
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
        
        if '"accion": "borrar"' in resp.text:
            datos_b = json.loads(extraer_json(resp.text))
            if enviar_al_buzon(datos_b):
                st.warning("🗑️ Orden de borrado enviada al buzón.")
        else:
            st.info(resp.text)

with tab3:
    if st.button("Actualizar Tabla"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
