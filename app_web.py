import streamlit as st
from google import genai
import json
import requests
import base64
import datetime
from datetime import timedelta
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Jaher", layout="wide")

try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except:
    st.error("❌ Faltan las claves en Secrets.")
    st.stop()

GITHUB_USER = "Soporte1jaher"
GITHUB_REPO = "inventario-jaher"
FILE_BUZON = "buzon.json"
FILE_HISTORICO = "historico.json"
HEADERS_GITHUB = {"Authorization": f"token {GITHUB_TOKEN}"}

def obtener_archivo_github(nombre_archivo):
    url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{nombre_archivo}"
    try:
        resp = requests.get(url, headers=HEADERS_GITHUB)
        if resp.status_code == 200:
            content = resp.json()
            sha = content['sha']
            texto = base64.b64decode(content['content']).decode('utf-8')
            return json.loads(texto) if texto.strip() else [], sha
        return [], None
    except:
        return [], None

def guardar_datos_en_buzon(lista_datos):
    # Asegurar que sea una lista
    if isinstance(lista_datos, dict): lista_datos = [lista_datos]
    
    datos_buzon, sha_buzon = obtener_archivo_github(FILE_BUZON)
    datos_buzon.extend(lista_datos)
    payload = {
        "message": "Orden IA",
        "content": base64.b64encode(json.dumps(datos_buzon, indent=4).encode('utf-8')).decode('utf-8'),
        "sha": sha_buzon
    }
    res = requests.put(f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/contents/{FILE_BUZON}", 
                       headers=HEADERS_GITHUB, json=payload)
    return res.status_code in [200, 201]

def extraer_json(texto):
    try:
        inicio = texto.find("[")
        if inicio == -1: inicio = texto.find("{")
        fin = texto.rfind("]") + 1
        if fin <= 0: fin = texto.rfind("}") + 1
        return texto[inicio:fin]
    except: return texto

# --- INTERFAZ ---
st.title("🌐 Inventario Inteligente")
tab1, tab2, tab3 = st.tabs(["📝 Registrar", "💬 Consultar/Borrar", "📊 Ver Historial"])

with tab1:
    texto_input = st.text_area("Registro rápido:")
    if st.button("Procesar"):
        client = genai.Client(api_key=API_KEY)
        prompt = f"Analiza: {texto_input}. Devuelve JSON: [{{'serie': '...', 'equipo': '...', 'accion': 'llega', 'ubicacion': '...', 'reporte': '...'}}]"
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt)
        datos_ia = json.loads(extraer_json(resp.text))
        hora_ec = (datetime.datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")
        if isinstance(datos_ia, dict): datos_ia = [datos_ia]
        for item in datos_ia: item["fecha"] = hora_ec
        if guardar_datos_en_buzon(datos_ia): st.success("Registrado.")

with tab2:
    pregunta = st.text_input("¿Qué quieres hacer?")
    if st.button("Ejecutar"):
        historial, _ = obtener_archivo_github(FILE_HISTORICO)
        contexto = json.dumps(historial)
        prompt_ia = f"""
        Datos: {contexto}
        Si el usuario quiere BORRAR, responde solo JSON: [{{"serie": "NUMERO_DE_SERIE", "accion": "borrar"}}]
        Si solo pregunta, responde normal.
        Usuario dice: {pregunta}
        """
        client = genai.Client(api_key=API_KEY)
        resp = client.models.generate_content(model="gemini-2.0-flash-exp", contents=prompt_ia)
        
        if '"accion": "borrar"' in resp.text:
            datos_borrado = json.loads(extraer_json(resp.text))
            if guardar_datos_en_buzon(datos_borrado):
                st.warning("🗑️ Orden de borrado enviada.")
        else:
            st.info(resp.text)

with tab3:
    if st.button("Cargar Datos"):
        datos, _ = obtener_archivo_github(FILE_HISTORICO)
        if datos: st.dataframe(pd.DataFrame(datos), use_container_width=True)
