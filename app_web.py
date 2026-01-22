import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta, timezone
import pandas as pd

st.set_page_config(page_title="Inventario Jaher", layout="wide")

try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("Faltan llaves en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Cache-Control": "no-cache"}

def obtener_fecha_ecuador():
    # UTC-5
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

st.title("🌐 Inventario Inteligente Jaher")
t1, t2, t3 = st.tabs(["📝 Registrar", "💬 Consultar/Borrar", "📊 Ver Historial"])

with t1:
    txt = st.text_area("Descripción del equipo:")
    if st.button("Procesar y Registrar"):
        if txt:
            client = genai.Client(api_key=API_KEY)
            prompt = f"Analiza y devuelve JSON LISTA (serie, equipo, accion, ubicacion, reporte): {txt}"
            resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
            datos_ia = json.loads(extraer_json(resp.text))
            if isinstance(datos_ia, dict): datos_ia = [datos_ia]
            
            fecha = obtener_fecha_ecuador()
            for d in datos_ia: d["fecha"] = fecha
            
            if enviar_buzon(datos_ia):
                st.success(f"✅ Registrado a las {fecha}. Espera a que tu PC lo procese.")

with t2:
    pregunta = st.text_input("¿Qué deseas hacer?")
    if st.button("Ejecutar"):
        historial, _ = obtener_github(FILE_HISTORICO)
        prompt = f"Datos: {json.dumps(historial)}. Si pide borrar, responde JSON: [{{'serie': '...', 'accion': 'borrar'}}]. Pregunta: {pregunta}"
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
        
        if '"accion": "borrar"' in resp.text:
            datos_b = json.loads(extraer_json(resp.text))
            if enviar_buzon(datos_b): st.warning("🗑️ Orden de borrado enviada.")
        else:
            st.info(resp.text)

with t3:
    if st.button("Cargar Tabla"):
        datos, _ = obtener_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
